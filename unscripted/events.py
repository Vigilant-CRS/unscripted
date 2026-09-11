"""Events, observations and claims (Technical Core v0.2 §7; spec v0.5 §6).

Event   = the smallest authoritative unit (what happened).
Claim   = a communicated proposition (what was said) -> belief update, NOT truth.
Observation = a subjective perception of an event (quality-weighted).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .ontology import Proposition


@dataclass
class Event:
    event_id: int
    world_time: int
    type: str                          # "claim", "question", "threat", "gift", "broadcast", ...
    #: "claim" asserts its proposition and moves belief. "question" names one
    #: without asserting it: heard, remembered, reacted to -- never evidence.
    actor: Optional[str] = None
    location: Optional[str] = None
    payload: dict = field(default_factory=dict)
    canonical: bool = True

    # convenience accessors
    @property
    def proposition(self) -> Optional[Proposition]:
        p = self.payload.get("proposition")
        return Proposition.from_dict(p) if isinstance(p, dict) else p

    @property
    def appraisal(self) -> dict:
        return self.payload.get("appraisal", {})


@dataclass
class Observation:
    observer: str
    event_id: int
    modality: str
    quality: float                     # [0,1] signal quality after distance/noise/obstruction
    event: Event = None
