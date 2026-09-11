"""Daily routines: what makes a cast a society rather than a tableau.

Characters never moved. Whoever a world pack placed somewhere stood there for the
rest of the session, so in two of the three reference packs no two characters
ever shared a place, and the diffusion layer -- the thing that makes information
travel -- could not fire at all. The benchmark reported it honestly as SKIP
rather than as a pass, which is how it surfaced.

That is not a small omission. A social simulation whose social graph is frozen at
load time cannot produce the behaviour it is sold on: a rumour needs someone to
be somewhere they were not before. Shadows of Doubt gives citizens jobs and
shifts; Bannerlord's lords travel. Without movement, "living world" is a label.

The model here is deliberately the small one that buys the most: **a schedule of
places by time of day**, authored per character. It is not pathfinding, not
needs-driven planning, not GOAP. It gets people into the same room at the same
time for reasons an author chose, which is the precondition for everything the
runtime already does well.

    "routine": [
      {"from": "06:00", "place": "place:schmiede", "activity": "arbeiten"},
      {"from": "12:00", "place": "place:dorfplatz", "activity": "essen"},
      {"from": "19:00", "place": "place:schmiede", "activity": "schlafen"}
    ]

A block runs until the next one starts, wrapping past midnight. A character with
no routine stays where the pack put them, exactly as before.

Movement is emitted as a real ``move`` event, so an arrival is perceived, is
remembered, and is on the ledger: "who was in the bar at 21:00" is a query.
"""
from __future__ import annotations

import re

from .events import Event

MINUTES_PER_DAY = 1440

_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")

#: Defaults, overridable per pack via ``world.json: {"routine": {...}}``.
DEFAULT_PARAMS = {
    # Emit a world event when someone arrives somewhere. On by default: an arrival
    # is observable, and "who was where when" is the raw material of a detective
    # scene. Importance is low so these consolidate away before anything that
    # matters to a character.
    "emit_events": True,
    "arrival_importance": 0.15,
}


def parse_clock(value) -> int:
    """"07:30" -> 450 minutes past midnight. Accepts a plain integer too."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value) % MINUTES_PER_DAY
    match = _CLOCK.match(str(value).strip())
    if not match:
        raise ValueError(f"Routine time must be HH:MM or minutes past midnight, got {value!r}")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise ValueError(f"Routine time out of range: {value!r}")
    return hours * 60 + minutes


class Routine:
    """One character's schedule: which place, at which time of day."""

    __slots__ = ("blocks",)

    def __init__(self, blocks):
        # (start_minute, place, activity), sorted by start
        self.blocks = tuple(sorted(blocks, key=lambda b: b[0]))

    def __bool__(self):
        return bool(self.blocks)

    @staticmethod
    def from_list(entries) -> "Routine":
        blocks = []
        for entry in entries or []:
            blocks.append((parse_clock(entry["from"]),
                           entry["place"],
                           entry.get("activity", "")))
        return Routine(blocks)

    def block_at(self, world_time: int):
        """The block in force at this world time, wrapping past midnight.

        Before the first block of the day a character is still in the last block
        of the previous one -- which is what makes an overnight block work without
        the author having to write it twice.
        """
        if not self.blocks:
            return None
        minute = world_time % MINUTES_PER_DAY
        chosen = self.blocks[-1]           # yesterday's last block, until today's first
        for block in self.blocks:
            if block[0] <= minute:
                chosen = block
            else:
                break
        return chosen


class RoutineEngine:
    """Moves characters through their day, deterministically."""

    module_id = "routine"
    version = "1.0.0"

    def __init__(self, params=None):
        self.params = dict(DEFAULT_PARAMS)
        if params:
            self.params.update(params)
        #: agent id -> the block start we last applied, so a character is moved on a
        #: transition rather than re-placed on every tick.
        self._applied = {}

    @classmethod
    def for_world(cls, world) -> "RoutineEngine":
        return cls(getattr(world, "routine_params", None))

    def seed(self, world) -> list:
        """Place everyone where their routine says they should be right now.

        Called once at startup so a session does not begin with the whole cast
        standing wherever the character files happened to list, which for an
        overnight start time is the wrong place by several hours.
        """
        reasons = []
        for agent in sorted(world.agents.values(), key=lambda a: a.id):
            block = agent.routine.block_at(world.world_time) if agent.routine else None
            if block is None:
                continue
            self._applied[agent.id] = block[0]
            if agent.location != block[1]:
                reasons.append(("routine.placed", float(block[0]),
                                {"agent": agent.id, "from": agent.location,
                                 "place": block[1], "activity": block[2]}))
                agent.location = block[1]
        return reasons

    def step(self, world, runtime, delta_minutes: int) -> list:
        """Advance routines over the elapsed window and move whoever is due.

        A window longer than a day still lands everyone correctly: the block in
        force at the END of the window is where they belong, and intermediate
        blocks they would have passed through are skipped rather than replayed --
        a week-long time skip must not emit a week of arrivals.
        """
        if delta_minutes <= 0:
            return []
        reasons = []
        for agent in sorted(world.agents.values(), key=lambda a: a.id):
            routine = agent.routine
            if not routine:
                continue
            block = routine.block_at(world.world_time)
            if block is None:
                continue
            start, place, activity = block
            if self._applied.get(agent.id) == start and agent.location == place:
                continue
            self._applied[agent.id] = start
            if agent.location == place:
                continue
            origin = agent.location

            # With an engine attached, the runtime does not move anyone: it asks,
            # and the character stays where the player can see him until the
            # engine says otherwise. `_applied` is stamped above either way, so a
            # character the engine could not walk is late for this block rather
            # than being asked again every tick for the rest of it.
            bridge = getattr(runtime, "actions_out", None)
            if bridge is not None and bridge.enabled:
                if bridge.has_pending(agent.id, "MOVE_TO"):
                    continue
                intent = bridge.issue(
                    actor=agent.id, type="MOVE_TO",
                    params={"place": place, "from": origin, "activity": activity},
                    reason=f"routine block {start // 60:02d}:{start % 60:02d}"
                           f"{' (' + activity + ')' if activity else ''}",
                    world_time=world.world_time)
                reasons.append(("routine.move_requested", float(start),
                                {"agent": agent.id, "from": origin, "to": place,
                                 "activity": activity, "intent": intent.intent_id}))
                continue

            reasons.extend(self.perform_move(world, runtime, agent, place,
                                             activity=activity, start=start))
        return reasons

    def perform_move(self, world, runtime, agent, place, *, activity="",
                     start: int | None = None) -> list:
        """Actually relocate a character and let the world notice.

        The one place a routine move happens, so a move the engine confirmed and a
        move the runtime made itself are the same event with the same perception,
        memory and ledger consequences -- only the moment differs.
        """
        origin = agent.location
        agent.location = place
        # Whoever walks brings the mood of where they came from. Nothing happens
        # here when the climate layer is off.
        climate = getattr(runtime, "climate", None)
        carried = climate.carried(origin, place) if climate is not None else []
        when = start if start is not None else world.world_time % MINUTES_PER_DAY
        # The return value used to be discarded. The mood really did travel --
        # the drift is measurable -- but nothing could SEE it happen, so the one
        # mechanism the climate layer is documented around was invisible in every
        # trace, and a designer had to infer it from a number three screens away.
        reasons = list(carried) + [("routine.moved", float(when),
                    {"agent": agent.id, "from": origin, "to": place,
                     "activity": activity,
                     "time_of_day": f"{when // 60:02d}:{when % 60:02d}"})]
        if self.params["emit_events"] and runtime is not None:
            runtime.process_event(Event(
                event_id=world.new_event_id(),
                world_time=world.world_time,
                type="move",
                actor=agent.id,
                location=place,
                payload={"summary": f"{agent.public_name or agent.id} arrives"
                                    f"{' to ' + activity if activity else ''}",
                         "importance": self.params["arrival_importance"],
                         "routine": {"from": origin, "activity": activity}},
            ))
        return reasons

    def whereabouts(self, world, world_time: int) -> dict:
        """Where every character is scheduled to be at a given time.

        The query a detective scene is built on, and the one an author needs to
        see whether their cast ever actually meets.
        """
        out = {}
        for agent in world.agents.values():
            block = agent.routine.block_at(world_time) if agent.routine else None
            out[agent.id] = block[1] if block else agent.location
        return out

    def meeting_opportunities(self, world, *, samples: int = 24) -> dict:
        """Places where two or more characters coincide over a day.

        Authoring aid and validation input: a pack whose cast never shares a place
        cannot produce a rumour, and that should be visible before playtesting
        rather than after.
        """
        found = {}
        step = max(1, MINUTES_PER_DAY // max(1, samples))
        for minute in range(0, MINUTES_PER_DAY, step):
            where = self.whereabouts(world, minute)
            occupancy = {}
            for agent_id, place in where.items():
                occupancy.setdefault(place, []).append(agent_id)
            for place, occupants in occupancy.items():
                if len(occupants) >= 2:
                    found.setdefault(place, set()).update(occupants)
        return {place: sorted(agents) for place, agents in found.items()}
