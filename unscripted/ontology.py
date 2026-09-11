"""Typed propositions and the contradiction / relevance logic
(Ontology v0.4 §1; Technical Core v0.2 §1).

A proposition is predicate + named slots + polarity + qualifier, over a closed,
versioned predicate catalog. This is what makes contradiction detection and
relevance scoring deterministic (instead of opaque strings).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math
import json


# --- Predicate catalog -------------------------------------------------------
# The catalog is a SCHEMA, not content: it fixes slot names, slot order (which
# determines a proposition's canonical core key) and which slot is functionally
# determined by the others (used for C2 contradiction detection; None = not
# functional).
#
# CORE_PREDICATES are domain-neutral and ship with the engine. Anything specific
# to one world -- "is the clinic open", "is this agent connected to the attack" --
# belongs to that world pack and is registered from its canon.json at load time.
# Registering the same predicate twice with a different shape is an authoring
# error and raises, so two packs cannot silently disagree about what a
# proposition means.
CORE_PREDICATES = {
    "space:exactly_at":   {"slots": ["entity", "place"], "functional_in": 1},
    "core:holds_role":    {"slots": ["agent", "role", "context"], "functional_in": None},
    "body:alive":         {"slots": ["agent"], "functional_in": None},
    "economy:owes_amount":{"slots": ["debtor", "creditor", "amount"], "functional_in": None},
    "looking_for":        {"slots": ["seeker", "target"], "functional_in": None},
    "was_at":             {"slots": ["agent", "place", "when"], "functional_in": None},
    "place:has_surveillance": {"slots": ["place", "level"], "functional_in": 1},
    "place:has_privacy":  {"slots": ["place", "level"], "functional_in": 1},
    "place:has_noise":    {"slots": ["place", "level"], "functional_in": 1},
}

# Live registry: core predicates plus whatever loaded packs have registered.
PREDICATE_CATALOG = dict(CORE_PREDICATES)

# Where each non-core predicate came from, for error messages and validation.
_PREDICATE_SOURCES: dict = {}


def _normalized(spec: dict) -> dict:
    return {"slots": list(spec.get("slots") or []),
            "functional_in": spec.get("functional_in")}


def register_predicate(name: str, spec: dict, *, source: str = "world pack") -> None:
    """Add a pack-declared predicate to the schema.

    Idempotent for an identical definition; raises when a pack redefines a
    predicate incompatibly, because slot order determines the canonical core key
    and a silent disagreement would make two worlds' beliefs unmergeable.
    """
    incoming = _normalized(spec)
    if not incoming["slots"]:
        raise ValueError(f"Predicate {name!r} from {source} declares no slots.")
    existing = PREDICATE_CATALOG.get(name)
    if existing is not None and _normalized(existing) != incoming:
        origin = "the engine core" if name in CORE_PREDICATES else _PREDICATE_SOURCES.get(name, "?")
        raise ValueError(
            f"Predicate {name!r} from {source} conflicts with the definition from "
            f"{origin}: {incoming} vs {_normalized(existing)}. Slot order defines the "
            f"canonical proposition key, so the two cannot coexist.")
    PREDICATE_CATALOG[name] = incoming
    if name not in CORE_PREDICATES:
        _PREDICATE_SOURCES[name] = source


def register_predicates(specs: dict, *, source: str = "world pack") -> None:
    for name, spec in (specs or {}).items():
        register_predicate(name, spec, source=source)


def reset_predicates() -> None:
    """Drop pack-registered predicates, keeping the engine core. For tests."""
    PREDICATE_CATALOG.clear()
    PREDICATE_CATALOG.update(CORE_PREDICATES)
    _PREDICATE_SOURCES.clear()

# Declared mutually exclusive cores (C3). Each entry: frozenset of (predicate, value-token).
MUTEX_PAIRS = [
    (("body:alive", "+"), ("body:alive", "-")),
]

# Optional predicate taxonomy distance for graded relevance (0 = identical predicate).
PREDICATE_TAXONOMY_DISTANCE = {
    ("was_at", "space:exactly_at"): 1,
}


@dataclass
class Proposition:
    predicate: str
    slots: dict                      # name -> entity/value id
    polarity: str = "+"              # "+" or "-"
    valid_start: Optional[int] = None
    valid_end: Optional[int] = None
    spatial: Optional[str] = None
    degree: Optional[float] = None   # for gradable predicates

    # ---- canonicalization ----
    def core_key(self) -> str:
        """Everything but polarity, in canonical form (used for equality / C1)."""
        sig = PREDICATE_CATALOG.get(self.predicate, {}).get("slots", sorted(self.slots))
        ordered = [f"{s}={self.slots.get(s)}" for s in sig]
        q = f"[{self.valid_start},{self.valid_end},{self.spatial}]"
        return f"{self.predicate}({','.join(ordered)}){q}"

    def key(self) -> str:
        return f"{self.polarity}{self.core_key()}"

    def negated(self) -> "Proposition":
        p = Proposition(self.predicate, dict(self.slots), "-" if self.polarity == "+" else "+",
                        self.valid_start, self.valid_end, self.spatial, self.degree)
        return p

    def as_dict(self):
        # dict(self.slots): callers serialise, store and compare these; handing out
        # the live slot mapping let a later mutation reach into an old record.
        return {"predicate": self.predicate, "slots": dict(self.slots), "polarity": self.polarity,
                "valid_start": self.valid_start, "valid_end": self.valid_end,
                "spatial": self.spatial, "degree": self.degree}

    @staticmethod
    def from_dict(d):
        return Proposition(d["predicate"], d["slots"], d.get("polarity", "+"),
                           d.get("valid_start"), d.get("valid_end"),
                           d.get("spatial"), d.get("degree"))

    def __str__(self):
        args = ", ".join(f"{k}={v}" for k, v in self.slots.items())
        sign = "" if self.polarity == "+" else "NOT "
        return f"{sign}{self.predicate}({args})"


def _qualifiers_overlap(a: Proposition, b: Proposition) -> bool:
    # Spatial: disjoint scopes do not contradict.
    if a.spatial and b.spatial and a.spatial != b.spatial:
        return False
    # Temporal: if both have intervals and they don't intersect, no contradiction.
    if None not in (a.valid_start, a.valid_end, b.valid_start, b.valid_end):
        if a.valid_end < b.valid_start or b.valid_end < a.valid_start:
            return False
    return True


def contradicts(a: Proposition, b: Proposition) -> Optional[str]:
    """Return contradiction kind 'C1'/'C2'/'C3' or None."""
    if not _qualifiers_overlap(a, b):
        return None
    # C1: direct negation (same core, opposite polarity)
    if a.core_key() == b.core_key() and a.polarity != b.polarity:
        return "C1"
    # C2: functional conflict (same predicate, same key slots, different value slot)
    meta = PREDICATE_CATALOG.get(a.predicate)
    if (meta and meta.get("functional_in") is not None and a.predicate == b.predicate
            and a.polarity == "+" and b.polarity == "+"):
        vi = meta["functional_in"]
        names = meta["slots"]
        key_names = [n for i, n in enumerate(names) if i != vi]
        val_name = names[vi]
        if all(a.slots.get(n) == b.slots.get(n) for n in key_names):
            if a.slots.get(val_name) != b.slots.get(val_name):
                return "C2"
    # C3: declared mutual exclusion
    for (pa, pol_a), (pb, pol_b) in MUTEX_PAIRS:
        if a.predicate == pa and a.polarity == pol_a and b.predicate == pb and b.polarity == pol_b:
            # require same primary entity (first slot)
            if list(a.slots.values())[:1] == list(b.slots.values())[:1]:
                return "C3"
    return None


def predicate_similarity(pa: str, pb: str, lam: float = 0.7) -> float:
    if pa == pb:
        return 1.0
    d = PREDICATE_TAXONOMY_DISTANCE.get((pa, pb)) or PREDICATE_TAXONOMY_DISTANCE.get((pb, pa))
    if d is None:
        return 0.0
    return math.exp(-lam * d)


def relevance(prop: Proposition, topic: Proposition, beta: float = 0.5) -> float:
    """rel(phi, topic) in [0,1] (Technical Core v0.2 §1.7). Topic slots set to None are wildcards."""
    psim = predicate_similarity(prop.predicate, topic.predicate)
    if psim == 0.0:
        return 0.0
    names = PREDICATE_CATALOG.get(topic.predicate, {}).get("slots", list(topic.slots))
    if not names:
        argmatch = 1.0
    else:
        score = 0.0
        for n in names:
            tv = topic.slots.get(n)
            if tv is None:
                score += beta            # wildcard
            elif prop.slots.get(n) == tv:
                score += 1.0
            else:
                score += 0.0
        argmatch = score / len(names)
    qualmatch = 1.0
    if topic.spatial and prop.spatial and topic.spatial != prop.spatial:
        qualmatch = 0.0
    return psim * argmatch * qualmatch
