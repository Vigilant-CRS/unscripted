"""Validator (spec v0.5 §4; review P0.6).

BUFFERED generation: the utterance is generated fully, validated, and only then
released. Never streams unvalidated tokens (review P0.6 -- streaming can leak).

Layers:

  0  context minimisation -- forbidden content never enters the prompt at all
     (the dialogue planner passes an avoid-label, never the secret itself)
  3a secret-token / alias scan over released text
  3b canon -- the speaker may not assert specifics it was not licensed to assert
  3c repetition guard
  4  fallback to a deterministic, validated line

Layer 3b matters only when an external model writes the line, and that is
precisely the case the runtime is sold for. The deterministic realizer emits
authored text and is correct by construction; a language model is not. Before
this layer existed the check was a comment, and the only active guards were a
secret substring scan and exact-repetition detection -- so a model could invent
any name, place, quantity or event and the runtime would hand it to the player:

    check("The mayor was murdered by Kane in the harbour last Tuesday.") -> ACCEPT

The rule enforced here is narrow and deterministic, which is what makes it
trustworthy: **proper nouns and numbers carry factual specificity, and every one
of them in provider output must be licensed by the plan.** Ordinary words carry
stance and are left alone -- the model is free to phrase, not to invent. A line
that fails is rejected softly, so the runtime falls back to authored text rather
than shipping an unsupported claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import grounding


#: Reason codes that mean the LINE WAS UNSAFE, and the commitment behind it must
#: not reach the world.
#:
#: Repetition is deliberately not one. Saying the same thing twice is a quality
#: problem, and treating it as a safety one let an earlier sentence decide
#: whether a later fact entered the society: ask the same question twice and the
#: second answer was released verbatim while the room was told nothing, because
#: the repetition guard had voided the commitment behind it.
SAFETY_CODES = frozenset({
    "validator.secret_leak",
    "validator.secret_referent",
    "validator.canon_violation",
})


def is_unsafe(result) -> bool:
    """Did this verdict mean the line must not be released as it stands?"""
    return any(code in SAFETY_CODES for code, _magnitude, _detail in result.reasons)


ACCEPT = "ACCEPT"
REJECT_HARD = "REJECT_HARD"
REJECT_SOFT = "REJECT_SOFT"

#: Canon enforcement levels.
CANON_OFF = "off"        # no parse-back (deterministic realizer: correct by construction)
CANON_WARN = "warn"      # report unlicensed specifics but release the line
CANON_STRICT = "strict"  # reject unlicensed specifics (default for external providers)

#: Capitalised words that carry no factual reference and must not be mistaken for
#: an invented proper noun. Deliberately small: anything world-specific belongs to
#: a pack, and anything longer would start hiding real hallucinations.
_NEUTRAL_CAPITALS = frozenset({
    "i", "i'm", "i've", "i'll", "i'd", "ok", "okay", "yes", "no", "sir", "ma'am",
    "mr", "mrs", "ms", "miss", "god", "hey", "well", "look", "listen", "sorry",
    "please", "thanks", "thank", "good", "morning", "afternoon", "evening", "night",
})

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ValidationResult:
    verdict: str
    reasons: list
    unlicensed: list = field(default_factory=list)


class Validator:
    module_id = "validator"
    version = "0.7.0"

    def __init__(self, secret_surface_forms=None, repetition_window=3,
                 world_terms=None, canon_mode: str = CANON_STRICT, world=None,
                 protected_ids=None):
        # avoid-label -> surface tokens/aliases that must never appear (spec §4.5).
        # These are WORLD VOCABULARY and come from the loaded pack's secrets:
        # "back room" gives away a secret in one world and means nothing in another.
        # This table used to be hardcoded here for a single character in a single
        # pack, which meant every other secret in every other pack was unprotected.
        self.secret_surface_forms = dict(secret_surface_forms or {})
        self.repetition_window = repetition_window
        # term -> world id, for reporting WHICH referent was used without licence
        self.world_terms = dict(world_terms or {})
        self.canon_mode = canon_mode
        #: The world itself, for grounding checks that need its vocabulary rather
        #: than a flattened term table. Optional: a validator built without one
        #: still does everything else.
        self.world = world
        #: avoid-label -> the world ids its secrets are about. Surface forms
        #: catch the phrasings a pack thought of; this catches the THING, in
        #: whatever words the world itself uses for it.
        self.protected_ids = dict(protected_ids or {})

    @classmethod
    def for_world(cls, world, **kwargs) -> "Validator":
        """Build a validator that knows this world's protected and canonical vocabulary."""
        from .content import protected_ids_by_label, surface_forms_by_label
        secrets = world.all_secrets()
        # What a secret is ABOUT, from both directions a pack can state it.
        #
        # Structurally, when `protects` is a proposition: its slots name the
        # entities. And from the give-away phrases, resolved through the world's
        # own lexicon -- which is the half that matters, because a pack that
        # writes `"surface_forms": ["back room"]` has said which PLACE gives the
        # secret away, and generalising from the phrase to the place is exactly
        # the step a paraphrase takes. Every shipped pack declares `protects` as
        # an opaque key, so without this the layer would be inert in all of them.
        protected = protected_ids_by_label(secrets)
        for secret in secrets:
            named = {target for form in secret.surface_forms
                     for target in grounding.referenced_ids(str(form), world)}
            if named:
                protected.setdefault(secret.avoid_label, set()).update(named)
        return cls(secret_surface_forms=surface_forms_by_label(secrets),
                   protected_ids=protected,
                   world_terms=_world_terms(world), world=world, **kwargs)

    def unprotected_labels(self, avoid_topics) -> list:
        """Avoid-labels with no surface forms -- the scan cannot see them."""
        return [t for t in avoid_topics if not self.secret_surface_forms.get(t)]

    # ------------------------------------------------------------------ check --
    def check(self, utterance: str, plan, agent, recent_utterances, *, canon_mode=None):
        """Validate a fully generated utterance before release.

        ``canon_mode`` overrides the instance default for this call: the runtime
        passes CANON_OFF for its own deterministic output and the configured mode
        for text that came back from a provider.
        """
        reasons = []
        low = utterance.lower()

        # Layer 3a: secret-token / alias scan for avoided topics
        for topic in plan.avoid_topics:
            for form in self.secret_surface_forms.get(topic, []):
                if form in low:
                    reasons.append(("validator.secret_leak", 1.0, {"topic": topic, "form": form}))
                    return ValidationResult(REJECT_HARD, reasons)

        # Layer 3a': the THING a secret is about, named in the world's own words.
        #
        # Surface forms are a list of phrasings somebody thought of, and a
        # paraphrase is by definition a phrasing nobody thought of: "Milan hides
        # in a room behind the bar" contains no forbidden string, no proper noun
        # the plan had not licensed and no invented referent, and it gave away
        # the hiding place. What it does contain is the PLACE -- named in a word
        # this world's own lexicon resolves to it.
        #
        # So a released line may not name an entity a protected proposition is
        # about unless the plan licensed that entity. It is still lexical and
        # still not a semantic guarantee; it closes the gap between "we listed
        # the words" and "we know what it is about", and it costs a deflection
        # when it is wrong.
        if self.world is not None and self.protected_ids:
            guarded = set()
            for topic in plan.avoid_topics:
                guarded |= self.protected_ids.get(topic, set())
            if guarded:
                licence = self._licence_text(plan)
                named = grounding.referenced_ids(utterance, self.world)
                # What the pack's own phrasing for this answer names is licensed,
                # read with the same lexicon as the utterance. The licence text
                # compares ids, and a phrasing names things in the world's words:
                # "Nobody came past this door" never matched `place:club_door`,
                # so an authored cover story refused itself, the liar deflected,
                # and the scene written around her lie had no lie in it.
                authored = grounding.referenced_ids(
                    " ".join((getattr(plan, "phrasing", None) or {}).values()),
                    self.world)
                leaked = sorted(entity for entity in (guarded & named)
                                if entity not in authored
                                and _plain(entity) not in licence)
                if leaked:
                    reasons.append(("validator.secret_referent", float(len(leaked)),
                                    {"named": leaked,
                                     "note": "named something a protected claim is "
                                             "about, without licence to"}))
                    return ValidationResult(REJECT_HARD, reasons)

        # Layer 3b: canon parse-back
        mode = self.canon_mode if canon_mode is None else canon_mode
        unlicensed = []
        if mode != CANON_OFF:
            unlicensed = self.unlicensed_specifics(utterance, plan)
            # Nouns that assert something exists. A proper-noun rule cannot see
            # "the old mill by the river": no capital, no number, and a world with
            # no mill just had one placed in it by a sentence.
            if self.world is not None:
                # One token, one finding. A word can trip both rules -- a
                # capitalised invented noun is a proper noun AND an invented
                # referent -- and reporting it twice makes the record read as
                # two problems where there is one.
                already = {e["token"].lower() for e in unlicensed}
                unlicensed += [e for e in grounding.unknown_referents(
                    utterance, self.world, licensed=self._licence_text(plan))
                    if e["token"].lower() not in already]
            if unlicensed:
                detail = {"unlicensed": unlicensed,
                          "licensed_facts": list(plan.allowed_facts or [])}
                if mode == CANON_STRICT:
                    reasons.append(("validator.canon_violation", float(len(unlicensed)), detail))
                    return ValidationResult(REJECT_SOFT, reasons, unlicensed)
                reasons.append(("validator.canon_warning", float(len(unlicensed)), detail))

        # Layer 3c: repetition guard
        if utterance in recent_utterances[-self.repetition_window:]:
            reasons.append(("validator.repetition", 1.0, {}))
            return ValidationResult(REJECT_SOFT, reasons, unlicensed)

        reasons.append(("validator.accept", 0.0, {}))
        return ValidationResult(ACCEPT, reasons, unlicensed)

    # ------------------------------------------------------------- layer 3b ----
    def unlicensed_specifics(self, utterance: str, plan) -> list:
        """Proper nouns and numbers in the utterance that the plan does not license.

        Licensed by: an allowed fact, the authored phrasing for this answer, the
        speaker or addressee, or being a neutral capitalised word. Everything else
        is a specific claim the speaker had no grounds to make.
        """
        licence = self._licence_text(plan)
        found = []

        for number in _NUMBER.finditer(utterance):
            token = number.group(0)
            if token not in licence:
                found.append({"kind": "number", "token": token})

        for sentence in _SENTENCE_SPLIT.split(utterance):
            for position, match in enumerate(_WORD.finditer(sentence)):
                token = match.group(0)
                if not token[:1].isupper():
                    continue
                lowered = token.lower()
                if lowered in _NEUTRAL_CAPITALS or len(lowered) < 2:
                    continue
                if lowered in licence:
                    continue
                known = self.world_terms.get(lowered)
                if position == 0 and not known:
                    # A sentence-initial capital is usually grammar, and an unknown
                    # word there cannot be told apart from an ordinary one. A NAMED
                    # world referent is different: "Kane told me." is never grammar,
                    # and skipping position 0 wholesale let exactly that through.
                    continue
                entry = {"kind": "proper_noun", "token": token}
                if known:
                    # A real thing in this world that this speaker was not licensed
                    # to bring up -- more serious than an invented word.
                    entry["kind"] = "unlicensed_referent"
                    entry["refers_to"] = known
                found.append(entry)

        # de-duplicate while preserving order, so a repeated word is reported once
        seen, unique = set(), []
        for entry in found:
            key = (entry["kind"], entry["token"].lower())
            if key not in seen:
                seen.add(key)
                unique.append(entry)
        return unique

    @staticmethod
    def _licence_text(plan) -> str:
        """Everything this plan authorises the speaker to be specific about."""
        parts = list(plan.allowed_facts or [])
        parts += [plan.speaker or "", plan.addressee or "", plan.goal or ""]
        parts += list((getattr(plan, "phrasing", None) or {}).values())
        # Ids read like "place:back_room"; separators become spaces so that the word
        # "room" in an utterance matches the id it came from.
        return re.sub(r"[:_\-()=,.]+", " ", " ".join(parts)).lower()


def _plain(identifier: str) -> str:
    """An id as the licence text spells it: separators become spaces."""
    return re.sub(r"[:_\-]+", " ", str(identifier).lower())


def _world_terms(world) -> dict:
    """Every name this world answers to -> the id it refers to.

    Used to tell "the model invented a word" from "the model named a real thing
    this character had no licence to mention", which is the more serious of the two.
    """
    terms = {}

    def add(name, target):
        if name:
            terms.setdefault(str(name).lower(), target)

    for place_id, attrs in (world.places or {}).items():
        add((attrs or {}).get("label"), place_id)
        for alias in (attrs or {}).get("aliases") or ():
            add(alias, place_id)
    for agent in (world.agents or {}).values():
        add(agent.public_name, agent.id)
        add(agent.objective_name, agent.id)
        for alias in agent.aliases or ():
            add(alias, agent.id)
    for entity_id, entity in (world.entities or {}).items():
        add((entity or {}).get("name"), entity_id)
    for topic in (world.topics or {}).values():
        for alias in topic.aliases or ():
            add(alias, topic.topic_id)
    return terms
