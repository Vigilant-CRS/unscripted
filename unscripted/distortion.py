"""How a claim changes shape as it is passed along.

Distortion used to be a coin flip that inverted a claim: either the rumour
survived intact or it became its own negation. That is not what happens to
information in a society, and it is not what the literature describes.

Allport & Postman (*The Psychology of Rumor*, 1947), following Bartlett's serial
reproduction work (*Remembering*, 1932), identified three processes that operate
together every time a story is retold:

**Levelling** — detail drops out. The message gets shorter and less specific with
each retelling, and this is by far the largest effect: most of what is lost is
simply lost, not changed.

**Sharpening** — the few details that survive become more prominent, and
quantities grow in the telling.

**Assimilation** — the message drifts toward the teller's own frame. Unfamiliar
people and places are replaced by familiar ones; the story becomes about the
teller's world.

A proposition is predicate + slots + polarity, so each process has a precise
structural meaning here:

    was_at(agent=agent:okada, place=place:clinic, when=last_night)

    levelling     -> was_at(agent=agent:okada, place=place:clinic, when=None)
    sharpening    -> economy:owes_amount(amount=300) becomes amount=450
    assimilation  -> was_at(agent=agent:okada, ...) becomes agent=<someone the
                     teller actually knows>
    inversion     -> NOT was_at(...)                      (rare; the old default)

Two properties make this epistemically interesting rather than merely noisy:

- A distorted claim is a *different proposition* with a different canonical key,
  so the listener forms a genuinely separate belief. A town can end up confidently
  believing something that never happened.
- The claim still carries the **original origin**. It is one source, and that
  source is now wrong. Correlation discounting keeps working, so a distorted
  rumour repeated ten times is still one distorted rumour.

Everything here is deterministic given a seed, and every change is reported so
the inspector can show what was lost and where.
"""
from __future__ import annotations

import re

from .determinism import derive_seed, seeded_uniform
from .ontology import PREDICATE_CATALOG, Proposition

LEVELLING = "levelling"
SHARPENING = "sharpening"
ASSIMILATION = "assimilation"
INVERSION = "inversion"

#: Relative frequency of each process. Levelling dominates, which is Allport &
#: Postman's central finding: retelling mostly *loses* information rather than
#: changing it. Inversion is rare -- a story rarely becomes its own opposite,
#: which is exactly why the previous coin-flip model was wrong.
DEFAULT_WEIGHTS = {
    LEVELLING: 0.55,
    SHARPENING: 0.20,
    ASSIMILATION: 0.20,
    INVERSION: 0.05,
}

#: How much a quantity grows when sharpened. Kept modest; runaway exaggeration
#: over several hops is produced by repetition, not by one large step.
SHARPEN_FACTOR = 1.5

_NUMBER = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def _kind_for(seed: bytes, weights: dict) -> str:
    total = sum(max(0.0, w) for w in weights.values()) or 1.0
    draw = seeded_uniform(seed) * total
    running = 0.0
    for kind in (LEVELLING, SHARPENING, ASSIMILATION, INVERSION):
        running += max(0.0, weights.get(kind, 0.0))
        if draw <= running:
            return kind
    return LEVELLING


def _slot_order(proposition: Proposition) -> list:
    declared = (PREDICATE_CATALOG.get(proposition.predicate) or {}).get("slots")
    return list(declared) if declared else sorted(proposition.slots)


def _looks_like(value, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix)


def distort(proposition: Proposition, *, speaker, world, seed: bytes,
            weights: dict | None = None, protected: set | None = None):
    """Return ``(distorted, kind, detail)`` or ``None`` if nothing changed.

    Never returns a proposition the speaker is protecting: a character must not
    leak a secret by accidentally garbling a different claim into it.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    protected = protected or set()
    kind = _kind_for(derive_seed(seed.hex(), "kind", 0, 0, "distortion"), weights)

    for attempt, candidate_kind in enumerate([kind] + [k for k in
                                             (LEVELLING, SHARPENING, ASSIMILATION, INVERSION)
                                             if k != kind]):
        result = _apply(candidate_kind, proposition, speaker, world,
                        derive_seed(seed.hex(), candidate_kind, attempt, 0, "distortion"))
        if result is None:
            continue
        distorted, detail = result
        if distorted.core_key() == proposition.core_key() and \
                distorted.polarity == proposition.polarity:
            continue                      # nothing actually changed
        if distorted.core_key() in protected:
            continue                      # would garble a different claim into a secret
        return distorted, candidate_kind, detail
    return None


def _apply(kind, proposition, speaker, world, seed):
    if kind == LEVELLING:
        return _level(proposition, seed)
    if kind == SHARPENING:
        return _sharpen(proposition, seed)
    if kind == ASSIMILATION:
        return _assimilate(proposition, speaker, world, seed)
    if kind == INVERSION:
        return proposition.negated(), {"note": "retold as its own opposite"}
    return None


def _level(proposition: Proposition, seed) -> tuple | None:
    """Drop a detail. The first slot is the subject of the claim and is kept:
    losing it would not make the story vaguer, it would make it about nobody."""
    order = _slot_order(proposition)
    droppable = [name for name in order[1:] if proposition.slots.get(name) is not None]
    if not droppable:
        return None
    name = droppable[int(seeded_uniform(seed) * len(droppable)) % len(droppable)]
    slots = dict(proposition.slots)
    lost = slots[name]
    slots[name] = None
    return (Proposition(proposition.predicate, slots, proposition.polarity,
                        proposition.valid_start, proposition.valid_end,
                        proposition.spatial, proposition.degree),
            {"lost_detail": name, "was": lost})


def _sharpen(proposition: Proposition, seed) -> tuple | None:
    """Quantities grow in the telling."""
    numeric = [name for name, value in proposition.slots.items()
               if _NUMBER.match(str(value or ""))]
    if numeric:
        name = numeric[int(seeded_uniform(seed) * len(numeric)) % len(numeric)]
        original = str(proposition.slots[name]).replace(",", ".")
        try:
            grown = float(original) * SHARPEN_FACTOR
        except ValueError:
            return None
        value = str(int(grown)) if float(original).is_integer() else f"{grown:.2f}"
        slots = dict(proposition.slots)
        slots[name] = value
        return (Proposition(proposition.predicate, slots, proposition.polarity,
                            proposition.valid_start, proposition.valid_end,
                            proposition.spatial, proposition.degree),
                {"exaggerated": name, "from": proposition.slots[name], "to": value})
    if proposition.degree is not None:
        degree = min(1.0, float(proposition.degree) * SHARPEN_FACTOR)
        return (Proposition(proposition.predicate, dict(proposition.slots),
                            proposition.polarity, proposition.valid_start,
                            proposition.valid_end, proposition.spatial, degree),
                {"exaggerated": "degree", "from": proposition.degree, "to": degree})
    return None


def _assimilate(proposition: Proposition, speaker, world, seed) -> tuple | None:
    """The story drifts toward people and places the teller actually knows.

    An unfamiliar name becomes a familiar one; a place they never go becomes one
    they do. This is the process that makes a rumour become about the teller's own
    world rather than about what happened.
    """
    candidates = []
    for name, value in proposition.slots.items():
        if _looks_like(value, "agent:"):
            familiar = _familiar_agents(speaker, world, exclude=value)
            if familiar:
                candidates.append((name, familiar, "person"))
        elif _looks_like(value, "place:"):
            familiar = _familiar_places(speaker, world, exclude=value)
            if familiar:
                candidates.append((name, familiar, "place"))
    if not candidates:
        return None
    name, options, category = candidates[int(seeded_uniform(seed) * len(candidates))
                                         % len(candidates)]
    pick = options[int(seeded_uniform(derive_seed(seed.hex(), name, 0, 0, "pick"))
                      * len(options)) % len(options)]
    slots = dict(proposition.slots)
    was = slots[name]
    slots[name] = pick
    return (Proposition(proposition.predicate, slots, proposition.polarity,
                        proposition.valid_start, proposition.valid_end,
                        proposition.spatial, proposition.degree),
            {"assimilated": name, "category": category, "was": was, "became": pick})


def _familiar_agents(speaker, world, *, exclude) -> list:
    """People the speaker knows best -- who they would confuse a stranger with."""
    ranked = sorted(
        ((relation.get("familiarity", 0.0) + relation.get("liking", 0.0), other)
         for other, relation in (speaker.relationships or {}).items()
         if other != exclude and other != speaker.id and other in (world.agents or {})),
        reverse=True)
    return [other for score, other in ranked if score > 0][:3]


def _familiar_places(speaker, world, *, exclude) -> list:
    """Places the speaker's own day takes them to."""
    routine = getattr(speaker, "routine", None)
    seen = []
    if routine:
        for _minute, place, _activity in getattr(routine, "blocks", ()):
            if place != exclude and place not in seen:
                seen.append(place)
    if speaker.location and speaker.location != exclude and speaker.location not in seen:
        seen.append(speaker.location)
    return seen[:3]


def describe(kind: str, detail: dict) -> str:
    """One line an inspector or a designer can read."""
    if kind == LEVELLING:
        return f"the {detail.get('lost_detail')} was forgotten (was {detail.get('was')})"
    if kind == SHARPENING:
        return f"{detail.get('exaggerated')} grew from {detail.get('from')} to {detail.get('to')}"
    if kind == ASSIMILATION:
        return (f"{detail.get('was')} became {detail.get('became')} — a "
                f"{detail.get('category')} the teller knows")
    if kind == INVERSION:
        return "retold as its own opposite"
    return kind
