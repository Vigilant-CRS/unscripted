"""Typed cross-cutting deltas.

State changes move through typed keys and proposed deltas. Owners validate source,
range and target before applying.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StateKey:
    module: str            # owning module, e.g. "relationship"
    field: str             # e.g. "trust", "liking"
    entity_id: str         # owner agent
    subject_id: Optional[str] = None   # the other party (for relationship/reputation)
    dimension: Optional[str] = None    # for reputation dimensions


@dataclass(frozen=True)
class ProposedDelta:
    key: StateKey
    amount: float
    reason: str
    source_module: str


def trust_delta(owner, subject, amount, reason, src):
    return ProposedDelta(StateKey("relationship", "trust", owner, subject), amount, reason, src)


def liking_delta(owner, subject, amount, reason, src):
    return ProposedDelta(StateKey("relationship", "liking", owner, subject), amount, reason, src)


def relationship_delta(owner, subject, field, amount, reason, src):
    """Any relationship dimension by name.

    `trust_delta` and `liking_delta` exist because those two are moved
    constantly. The others -- `fear`, `respect`, `dependence`, and whatever a
    pack authors -- had no constructor, which is a fair part of why three of
    them were read by four engines and written by nothing at all.
    """
    return ProposedDelta(StateKey("relationship", field, owner, subject), amount, reason, src)


def reputation_delta(subject, audience, dimension, amount, reason, src):
    return ProposedDelta(StateKey("reputation", "degree", audience, subject, dimension), amount, reason, src)


def identity_threat(owner, identity_id, amount, reason, src):
    return ProposedDelta(StateKey("identity", "threat", owner, identity_id), amount, reason, src)
