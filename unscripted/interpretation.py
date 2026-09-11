"""Seeing is not understanding. What a character makes of what happened.

Perception decided who *could* observe an event and how clearly. Everything after
that was identical for everyone: a technician and a tourist standing in the same
room acquired the same claim with the same slots, and competence only affected
whether other people believed them afterwards. That is the wrong place for it.
Expertise changes what you *notice* and what you can *identify*, long before it
changes who trusts your account.

Three stages sit between an observation and a belief:

**Attention.** Did they notice? A guard registers a propped service door; a
tourist walks past it. Attention is relevance times novelty times salience, and a
character who was not paying attention forms no belief at all -- which is a
different state from disbelieving.

**Recognition.** Could they identify what they saw? A world declares what a claim
takes to recognise (`requires_competence` on the predicate). Below that, the
observer does not get the claim; they get a coarser one.

**Interpretation.** What did they take it to mean? The coarsening reuses the
distortion processes, because they are the same phenomena: a layman losing the
technical detail is *levelling*, and a suspicious character reading an ambiguous
scene as the thing they already fear is *assimilation*. Modelling them twice
would let them drift apart.

The consequence worth having: several characters witness one event and end up
holding genuinely different claims about it, each traceable to the same origin.
"""

from __future__ import annotations

from . import distortion
from .determinism import derive_seed, seeded_uniform


class InterpretationEngine:
    module_id = "interpretation"
    version = "0.1.0"

    DEFAULTS = {
        #: Below this, an observer does not attend to the event at all.
        "attention_floor": 0.18,
        #: How much an event about a familiar person or place raises attention.
        "familiarity_weight": 0.35,
        #: How much the observer's role domain raises attention.
        "role_weight": 0.40,
        #: How far below the required competence an observer may be and still
        #: identify what they saw.
        "recognition_slack": 0.15,
    }

    def __init__(self, params=None):
        self.params = dict(self.DEFAULTS)
        if params:
            self.params.update(params)

    # -------------------------------------------------------------- attention --
    def attention(self, agent, event, proposition, world, quality: float) -> tuple:
        """How much of this observer's attention this event gets, and why.

        Returns `(score, reasons)`. Deliberately additive and small: this decides
        whether something is noticed, not what it means, and a model with many
        multiplied terms would make "noticed nothing" the common case.
        """
        params = self.params
        importance = float((event.payload or {}).get("importance", 0.5))
        score = 0.35 + 0.5 * importance
        reasons = []

        if proposition is not None:
            about = {str(v) for v in (proposition.slots or {}).values()}
            if agent.id in about:
                score += 0.5
                reasons.append(("attention.about_me", 1.0, {}))
            elif about & set(agent.relationships or {}):
                score += params["familiarity_weight"]
                reasons.append(("attention.familiar_subject", params["familiarity_weight"], {}))

            domain = _domain_of(proposition, world)
            competence = agent.competence_in(domain)
            if competence >= 0.5:
                score += params["role_weight"] * competence
                reasons.append(("attention.professional_interest",
                                round(competence, 3), {"domain": domain}))

        curiosity = agent.trait("curiosity")
        if abs(curiosity - 0.5) > 1e-9:
            bonus = 0.4 * (curiosity - 0.5)
            score += bonus
            reasons.append(("attention.curiosity", round(bonus, 3), {}))

        score *= max(0.1, quality)
        return max(0.0, min(1.5, score)), reasons

    # ------------------------------------------------------------ recognition --
    def recognises(self, agent, proposition, world) -> tuple:
        """Can this observer identify what they are looking at?

        The requirement is world content: a pack declares what a claim takes to
        recognise, because "you need to be an engineer to see that this was
        deliberate" is a fact about a setting, not about an engine.
        """
        need = _required_competence(proposition, world)
        if not need:
            return True, 1.0, "no expertise required"
        domain, level = need
        have = agent.competence_in(domain)
        ok = have >= level - self.params["recognition_slack"]
        return ok, have, f"{domain} {have:.2f} vs {level:.2f} required"

    # ---------------------------------------------------------------- the pass --
    def interpret(self, agent, event, proposition, world, quality: float,
                  modality: str = "sight") -> tuple:
        """Attend, recognise, interpret. Returns `(proposition_or_None, reasons)`.

        `None` means the observer did not take it in at all. A *different*
        proposition means they took in something less specific, or something
        coloured by what they already expect -- which is the interesting case, and
        the one that makes four witnesses genuinely disagree.
        """
        reasons = []
        score, attention_reasons = self.attention(agent, event, proposition, world, quality)
        reasons += attention_reasons
        if score < self.params["attention_floor"]:
            reasons.append(("interpretation.unnoticed", round(score, 3),
                            {"note": "below attention floor; formed no belief"}))
            return None, reasons
        reasons.append(("interpretation.attended", round(score, 3), {}))

        if proposition is None:
            return None, reasons

        # Recognition is about IDENTIFYING something you perceived, not about
        # understanding a sentence. You can disbelieve a radio report that a seal
        # failed in Stores; you do not mishear "Stores" as "the med bay". When a
        # claim arrives in words the speaker has already done the identifying, so
        # competence decides whether you BELIEVE them -- which the belief engine
        # handles -- and not what you took in.
        if modality in ("hearing", "media"):
            reasons.append(("interpretation.told_in_words", 1.0,
                            {"note": "a stated claim needs no identifying; "
                                     "competence bears on credence instead"}))
            return proposition, reasons

        known, have, detail = self.recognises(agent, proposition, world)
        if known:
            reasons.append(("interpretation.recognised", round(have, 3), {"detail": detail}))
            return proposition, reasons

        # Out of their depth. They saw something; they could not say what. The
        # claim they end up holding is a coarser one -- and it is still theirs,
        # first-hand, with the same origin, which is what keeps it accountable.
        seed = derive_seed(world.global_seed, agent.id, event.event_id,
                           world.world_time, self.module_id, "recognise")
        # How a scene you cannot read gets bent is a property of the reader. A
        # character who confirms what they already expect assimilates it towards
        # the familiar; one who does not simply loses the detail.
        bias = agent.trait("confirmation_bias")
        weights = {distortion.LEVELLING: 1.0 - bias, distortion.ASSIMILATION: bias,
                   distortion.SHARPENING: 0.0, distortion.INVERSION: 0.0}
        outcome = distortion.distort(proposition, speaker=agent, world=world,
                                     seed=seed, weights=weights)
        if outcome is None:
            reasons.append(("interpretation.not_recognised", round(have, 3),
                            {"detail": detail,
                             "note": "could not identify it and could not simplify it; "
                                     "took it at face value"}))
            return proposition, reasons
        coarser, kind, note = outcome
        reasons.append(("interpretation.misread", round(have, 3),
                        {"detail": detail, "process": kind,
                         "saw": str(proposition), "understood": str(coarser),
                         "note": note}))
        return coarser, reasons


def _domain_of(proposition, world) -> str:
    declared = getattr(world, "predicate_domains", None) or {}
    return declared.get(proposition.predicate, "street")


def _required_competence(proposition, world):
    """`(domain, level)` a pack declared for identifying this claim, or None."""
    declared = getattr(world, "predicate_competence", None) or {}
    need = declared.get(proposition.predicate)
    if not need:
        return None
    return need.get("domain", "street"), float(need.get("level", 0.5))


def seeded_noise(world, agent_id: str, event_id, salt: str) -> float:
    """Shared helper so any future stage draws from the same stream."""
    return seeded_uniform(derive_seed(world.global_seed, agent_id, event_id,
                                      world.world_time, "interpretation", salt))
