"""What a character commits to saying, before any words exist.

The runtime used to hand a text provider a *list* of facts the character was
permitted to mention. Which of them reached the listener was then the provider's
choice. For a template realizer that is harmless; for a language model it means
the model decides what information enters the society, because a spoken claim is
a real event that moves other characters' beliefs. The claim "the text layer
decides only how it is phrased" was not true.

A commitment is the fix. The runtime selects the exact propositions to assert,
with what force and how openly, and the text layer renders that and nothing else.
Selection is a runtime decision, so it is seeded, replayable and in the event log.

The same structure carries deception (see `believed`): a lie is a move whose
proposition is not what the speaker holds. Nothing else in the pipeline has to
know the difference, which is why the two arrive together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .determinism import derive_seed, seeded_choice

#: How openly a move is made. Affects phrasing, not what is asserted.
DIRECT = "direct"
PARTIAL = "partial"
HEDGED = "hedged"

#: How sure the speaker sounds. Derived from confidence unless overridden.
CERTAIN = "certain"
PROBABLE = "probable"
UNCERTAIN = "uncertain"

#: Why a move's proposition differs from the speaker's belief, if it does.
HONEST = "honest"
LIE = "lie"
EXAGGERATION = "exaggeration"
UNDERSTATEMENT = "understatement"


def certainty_for(confidence: float) -> str:
    """Sound as sure as you are. One place, so every path agrees."""
    if confidence >= 0.85:
        return CERTAIN
    if confidence >= 0.65:
        return PROBABLE
    return UNCERTAIN


@dataclass(frozen=True)
class SemanticMove:
    """One thing a character commits to doing with a sentence.

    `proposition` is what is ASSERTED, which is not necessarily what the speaker
    believes -- `believed_probability` records the latter, and `honesty` says why
    they differ. A listener updates on the assertion; the speaker's own belief is
    untouched by their own speech.
    """

    act: str                                  # assert | deny | evade | advise | greet
    proposition: object | None = None         # Proposition, or None for non-factual acts
    certainty: str = PROBABLE
    disclosure: str = DIRECT
    honesty: str = HONEST
    believed_probability: float | None = None  # what the speaker actually holds

    @property
    def is_factual(self) -> bool:
        return self.proposition is not None and self.act in ("assert", "deny")

    @property
    def is_deceptive(self) -> bool:
        return self.honesty != HONEST

    def rendered(self) -> str:
        return str(self.proposition) if self.proposition is not None else ""

    def as_dict(self) -> dict:
        return {"act": self.act,
                "proposition": (self.proposition.as_dict()
                                if hasattr(self.proposition, "as_dict") else None),
                "rendered": self.rendered(),
                "certainty": self.certainty,
                "disclosure": self.disclosure,
                "honesty": self.honesty,
                "believed_probability": (None if self.believed_probability is None
                                         else round(self.believed_probability, 4))}

    @classmethod
    def from_dict(cls, data: dict, proposition=None) -> "SemanticMove":
        return cls(act=data.get("act", "assert"), proposition=proposition,
                   certainty=data.get("certainty", PROBABLE),
                   disclosure=data.get("disclosure", DIRECT),
                   honesty=data.get("honesty", HONEST),
                   believed_probability=data.get("believed_probability"))


@dataclass
class Candidate:
    """A proposition the character could assert, and how well it fits."""

    proposition: object
    confidence: float                  # how sure they are, in [0.5, 1]
    relevance: float = 1.0             # how well it answers what was asked
    affirmed: bool = True              # assert it, or assert its negation


@dataclass
class Commitment:
    """The complete semantic content of one utterance."""

    moves: tuple = ()
    forbidden: tuple = ()              # avoid labels; never the secret content
    max_sentences: int = 2
    reasons: list = field(default_factory=list)

    @property
    def propositions(self) -> list:
        return [m.proposition for m in self.moves if m.proposition is not None]

    @property
    def factual_moves(self) -> list:
        return [m for m in self.moves if m.is_factual]

    def rendered_facts(self) -> list:
        return [m.rendered() for m in self.factual_moves if m.rendered()]

    def as_dict(self) -> dict:
        return {"moves": [m.as_dict() for m in self.moves],
                "forbidden": list(self.forbidden),
                "max_sentences": self.max_sentences}


def select(candidates, *, act: str = "assert", limit: int = 1,
           seed_parts: tuple = (), forbidden=(), max_sentences: int = 2) -> Commitment:
    """Pick what to say. This is the decision the text layer used to make.

    Candidates are ranked by relevance then confidence. Everything within a small
    band of the best score is treated as equally good -- and among those the choice
    is *seeded*, not first-past-the-post, so different worlds and different moments
    produce different answers while any single world stays replayable.

    That is the whole argument against letting a model pick: seeded selection here
    gives the same unpredictability from the player's side, and stays in the event
    log.
    """
    ranked = sorted(candidates,
                    key=lambda c: (-round(c.relevance, 4), -round(c.confidence, 4),
                                   str(c.proposition)))
    if not ranked:
        return Commitment(moves=(), forbidden=tuple(forbidden), max_sentences=max_sentences)

    reasons = []
    chosen = []
    pool = list(ranked)
    while pool and len(chosen) < max(1, limit):
        best = pool[0]
        band = [c for c in pool
                if abs(c.relevance - best.relevance) < 1e-9
                and abs(c.confidence - best.confidence) <= 0.05]
        if len(band) == 1:
            pick = band[0]
        else:
            seed = derive_seed(*(list(seed_parts) + ["commitment", f"pick{len(chosen)}"])[:6])
            pick = band[seeded_choice(seed, [1.0] * len(band))]
            reasons.append(("commitment.seeded_choice", float(len(band)),
                            {"among": [str(c.proposition) for c in band],
                             "picked": str(pick.proposition)}))
        pool.remove(pick)
        proposition = pick.proposition if pick.affirmed else pick.proposition.negated()
        chosen.append(SemanticMove(
            act=act if pick.affirmed else "deny",
            proposition=proposition,
            certainty=certainty_for(pick.confidence),
            believed_probability=pick.confidence))

    reasons.append(("commitment.selected", float(len(chosen)),
                    {"committed": [m.rendered() for m in chosen],
                     "considered": len(ranked),
                     "note": "the runtime chose; the text layer renders"}))
    return Commitment(moves=tuple(chosen), forbidden=tuple(forbidden),
                      max_sentences=max_sentences, reasons=reasons)


def deceive(move: SemanticMove, *, assert_instead, honesty: str = LIE) -> SemanticMove:
    """Turn an honest move into a deceptive one, keeping the real belief on record.

    The speaker's own belief never changes -- lying is not self-persuasion -- and
    `believed_probability` stays what it was, so the record shows the divergence
    and a later contradiction is findable.
    """
    return SemanticMove(act=move.act, proposition=assert_instead,
                        certainty=move.certainty, disclosure=move.disclosure,
                        honesty=honesty,
                        believed_probability=move.believed_probability)
