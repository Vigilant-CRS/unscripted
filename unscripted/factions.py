"""Faction / Director layer -- the macro 'the society develops' layer
(Blades-in-the-Dark-inspired progress clocks + heat/escalation + off-screen action).

A Faction is a collective agent with resources, an influence/standing score, goals
tracked on progress clocks, and a heat accumulator. The Director advances clocks and
heat on each time step and, when heat crosses a threshold, mobilizes a faction
response (e.g. a police raid) -- which is the ally-response mechanic at faction scale.

Social standing matters: a faction's INFLUENCE scales how fast its clocks fill and
how quickly/heavily it mobilizes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .types import clamp01
from .determinism import derive_seed, seeded_uniform


@dataclass
class ProgressClock:
    name: str
    size: int
    filled: int = 0

    def tick(self, segments: int = 1):
        before = self.filled
        self.filled = min(self.size, self.filled + segments)
        return self.filled > before and self.filled >= self.size  # returns True on completion

    @property
    def complete(self):
        return self.filled >= self.size

    def as_dict(self):
        return {"name": self.name, "filled": self.filled, "size": self.size}

    @staticmethod
    def from_dict(d: dict) -> "ProgressClock":
        return ProgressClock(name=d["name"], size=int(d["size"]), filled=int(d.get("filled", 0)))


@dataclass
class Faction:
    faction_id: str
    influence: float = 0.5            # social standing of the faction [0,1]
    resources: float = 0.5
    heat: float = 0.0                 # [0,1] escalation accumulator
    territory: list = field(default_factory=list)   # place ids
    goals: list = field(default_factory=list)       # clock names
    clocks: dict = field(default_factory=dict)       # name -> ProgressClock

    def as_dict(self):
        # Full precision, all mutable fields: this is the persistence shape.
        # Display code (inspect/state_view) rounds for presentation separately.
        return {"faction_id": self.faction_id, "influence": self.influence,
                "resources": self.resources, "heat": self.heat,
                "territory": list(self.territory), "goals": list(self.goals),
                "clocks": {k: v.as_dict() for k, v in self.clocks.items()}}

    @staticmethod
    def from_dict(d: dict) -> "Faction":
        return Faction(faction_id=d["faction_id"], influence=d.get("influence", 0.5),
                       resources=d.get("resources", 0.5), heat=d.get("heat", 0.0),
                       territory=list(d.get("territory", [])),
                       goals=list(d.get("goals", [])),
                       clocks={k: ProgressClock.from_dict(v)
                               for k, v in (d.get("clocks") or {}).items()})


class Director:
    module_id = "director"
    version = "1.0.0"

    def __init__(self, params=None):
        self.params = {"heat_decay": 0.02, "heat_threshold": 0.6,
                       "clock_base_rate": 0.15, "mobilize_latency": 20}
        if params:
            self.params.update(params)
        self.factions = {}

    def add_faction(self, f: Faction):
        self.factions[f.faction_id] = f

    def add_heat(self, faction_id, amount, reason, reasons=None):
        f = self.factions.get(faction_id)
        if not f:
            return
        before = f.heat
        f.heat = clamp01(f.heat + amount)
        if reasons is not None:
            reasons.append(("director.heat", round(f.heat - before, 3),
                            {"faction": faction_id, "reason": reason, "heat": round(f.heat, 3)}))

    def faction_controlling(self, place_id):
        for f in self.factions.values():
            if place_id in f.territory:
                return f
        return None

    def step(self, world, delta, scheduler_add):
        """Advance clocks + heat, fire threshold mobilizations and clock completions.
        scheduler_add(event) schedules a future event on the world timeline."""
        reasons = []
        for f in self.factions.values():
            # heat decay over time
            f.heat = clamp01(f.heat - self.params["heat_decay"] * (delta / 60.0))
            # goal clocks advance, faster with influence + resources (off-screen progress)
            rate = self.params["clock_base_rate"] * (0.5 + f.influence) * (0.5 + f.resources)
            for name in f.goals:
                clock = f.clocks.setdefault(name, ProgressClock(name, 6))
                if seeded_uniform(derive_seed(world.global_seed, f.faction_id, name,
                                              world.world_time, "clocktick")) < rate:
                    completed = clock.tick(1)
                    reasons.append(("director.clock", 1.0,
                                    {"faction": f.faction_id, "clock": name,
                                     "filled": clock.filled, "size": clock.size}))
                    if completed:
                        reasons.append(("director.clock_complete", 1.0,
                                        {"faction": f.faction_id, "clock": name}))
            # heat threshold -> mobilize a faction response (police raid etc.)
            if f.heat >= self.params["heat_threshold"]:
                latency = int(self.params["mobilize_latency"] * (1.5 - f.influence))  # influence -> faster
                ev = scheduler_add(world, "faction_mobilize", f, latency)
                reasons.append(("director.mobilize", round(f.heat, 3),
                                {"faction": f.faction_id, "latency": latency,
                                 "in_response_to": "heat_threshold"}))
                f.heat = clamp01(f.heat - 0.4)   # mobilizing discharges some heat
        return reasons
