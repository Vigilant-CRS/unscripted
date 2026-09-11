"""Climate: not who anyone is, but what it is like here.

`CONCEPT.md` has said for a long time that characters' traits are fixed --
relationships move, who they are does not -- and that is the right call. A
personality that drifts under play is how every character in a long game
converges on the same one. But it left a real thing unmodelled: **a place can
change its mind about strangers.** After a killing in the square, the square gets
quieter, people are slower to pass things on, and a stranger asking questions is
trusted less. Nobody's personality changed. The weather did.

So this is deliberately not culture and not personality. It is a small vector of
**ambient dispositions attached to a place**, which

  * moves in response to events rather than to who is standing there,
  * relaxes back toward what the pack authored, and
  * drifts slowly toward its neighbours, because people walk between them.

Three numbers, each in [0, 1], each with one job:

    candour    how readily what is known here gets passed on
    suspicion  how much a claim is discounted for coming from outside
    openness   how readily a stranger is spoken to at all

**OFF BY DEFAULT, AND OFF MEANS BYTE-IDENTICAL.** With `climate=False` every
modifier is exactly neutral, nothing is stored, and a run reproduces the same
snapshot it did before this module existed. A test asserts that rather than
asking anyone to believe it. This is the same contract the action bridge has, and
for the same reason: a studio that does not want a mechanic should not have to
pay for it.

WHY THIS IS THE HONEST VERSION OF "CULTURE SPREADS". It does not make anybody
kinder or crueller. It changes the *ambient conditions* they read from where they
are, which is a claim the runtime can support: the modifiers land on the four
places the runtime already computes a number -- how often people talk, how sure
they must be before passing something on, how much a claim persuades, and how far
a stranger gets. Anything stronger than that would be personality drift wearing a
different hat.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

#: Neutral in every direction. What `modifiers()` returns when the layer is off,
#: and what every arithmetic path collapses to.
NEUTRAL = {"tempo": 1.0, "tell_threshold": 0.0, "skepticism": 0.0,
           "stranger_trust": 0.0}

#: How far a full swing of one disposition can move the thing it governs. Kept
#: small on purpose: this is weather, and weather does not rewrite a world.
TEMPO_SWING = 0.45          # +-45% of the encounter rate
THRESHOLD_SWING = 0.12      # +-0.12 on a confidence threshold of 0.60
SKEPTICISM_SWING = 0.18     # +-0.18 on a skepticism in [0, 1]
STRANGER_SWING = 0.15       # +-0.15 on the trust a stranger starts with

#: World hours for a disturbance to decay halfway back to the authored baseline.
#: A day and a bit: long enough that a player feels it for the rest of a session,
#: short enough that a world is not permanently marked by one bad afternoon.
HALF_LIFE_HOURS = 30.0

#: How much of where somebody came from arrives with them. This is the whole
#: spreading mechanism, and it is a person walking through a door rather than an
#: abstract pull between adjacent rooms.
#:
#: An earlier version drifted every place toward its neighbours by the clock,
#: which produced the same picture and modelled the wrong thing: two rooms
#: joined by a door nobody uses would have converged anyway, and a room emptied
#: by a curfew would have kept absorbing its neighbours' mood. The mood travels
#: with the traffic or it does not travel.
CARRIED_PER_ARRIVAL = 0.055

#: Ceiling on how much one room can be moved by arrivals in a single step, so a
#: shift change cannot import a whole district's mood at once.
MAX_CARRIED_PER_STEP = 0.22


@dataclass
class Climate:
    """What it is like in one place, right now."""
    candour: float = 0.5
    suspicion: float = 0.5
    openness: float = 0.5

    def as_dict(self) -> dict:
        return {key: round(value, 4) for key, value in asdict(self).items()}

    def blend(self, other: "Climate", weight: float) -> None:
        for field_name in ("candour", "suspicion", "openness"):
            here = getattr(self, field_name)
            there = getattr(other, field_name)
            setattr(self, field_name, _clamp(here + (there - here) * weight))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def baseline_for(place: dict) -> Climate:
    """What a place is like when nothing has happened.

    Derived from what packs already declare, so an existing world gets a sensible
    climate without anybody authoring one: a gossipy market is candid, a place
    under surveillance is guarded, a private room is closed to strangers. A pack
    may state it outright with `"climate": {...}` and that wins.
    """
    authored = (place or {}).get("climate")
    if isinstance(authored, dict):
        return Climate(
            candour=_clamp(float(authored.get("candour", 0.5))),
            suspicion=_clamp(float(authored.get("suspicion", 0.5))),
            openness=_clamp(float(authored.get("openness", 0.5))))

    gossip = float((place or {}).get("gossip_factor", 1.0))
    surveillance = float((place or {}).get("surveillance_level", 0.3))
    privacy = float((place or {}).get("privacy_level", 0.3))
    return Climate(
        candour=_clamp(0.30 + 0.30 * gossip - 0.25 * surveillance),
        suspicion=_clamp(0.35 + 0.35 * surveillance),
        openness=_clamp(0.65 - 0.45 * privacy))


#: What moves the weather. Event type -> (candour, suspicion, openness) deltas at
#: full severity. Violence closes a place; being helped opens it; catching
#: somebody out makes everyone read the next claim harder.
#: Keyed on the event types the runtime actually emits, which are `threat` and
#: `crime` rather than the verbs a player types. Guessing the names here would
#: have produced a layer that ran, reported, and never once moved.
REACTIONS = {
    "attack": (-0.22, +0.26, -0.24),
    "threat": (-0.14, +0.16, -0.18),
    "crime": (-0.18, +0.22, -0.20),
    "faction_mobilize": (-0.10, +0.14, -0.12),
    "discredit": (-0.04, +0.20, -0.06),
    "promise": (+0.06, -0.04, +0.10),
    "ally_arrives": (+0.04, +0.02, +0.06),
}


class ClimateEngine:
    """Per-place weather, and the four numbers it lends to the rest of the runtime."""

    module_id = "climate"

    def __init__(self, world=None, *, enabled: bool = False):
        self.enabled = enabled
        self.baselines: dict = {}
        self.now: dict = {}
        self._carried_this_step: dict = {}
        if world is not None:
            for place_id, place in (getattr(world, "places", {}) or {}).items():
                self.baselines[place_id] = baseline_for(place)
                self.now[place_id] = Climate(**asdict(self.baselines[place_id]))

    @classmethod
    def for_world(cls, world, *, enabled: bool = False) -> "ClimateEngine":
        return cls(world, enabled=enabled)

    # ------------------------------------------------------------ reading ----

    def at(self, place_id: str) -> Climate:
        return self.now.get(place_id) or Climate()

    def modifiers(self, place_id: str) -> dict:
        """The four numbers the rest of the runtime asks for.

        Expressed as deviations from neutral so that a caller can apply them
        without knowing anything about this module, and so that "off" is exactly
        the same arithmetic as "average".
        """
        if not self.enabled:
            return dict(NEUTRAL)
        climate = self.at(place_id)
        return {
            # A candid place talks more often, which is the speed of the thing.
            "tempo": 1.0 + TEMPO_SWING * (climate.candour - 0.5) * 2.0,
            # A guarded place makes people surer before they pass something on.
            "tell_threshold": -THRESHOLD_SWING * (climate.candour - 0.5) * 2.0,
            # A suspicious place discounts what it is told.
            "skepticism": SKEPTICISM_SWING * (climate.suspicion - 0.5) * 2.0,
            # A closed place gives a stranger less to work with.
            "stranger_trust": STRANGER_SWING * (climate.openness - 0.5) * 2.0,
        }

    # ------------------------------------------------------------ writing ----

    def react(self, event) -> list:
        """Let an event move the weather where it happened."""
        if not self.enabled:
            return []
        place_id = getattr(event, "location", None)
        if place_id is None or place_id not in self.now:
            return []
        deltas = REACTIONS.get(getattr(event, "type", ""))
        if deltas is None:
            return []
        payload = getattr(event, "payload", None) or {}
        severity = abs(float(payload.get("severity", payload.get("importance", 0.5))))
        severity = max(0.0, min(1.0, severity))
        climate = self.now[place_id]
        before = climate.as_dict()
        climate.candour = _clamp(climate.candour + deltas[0] * severity)
        climate.suspicion = _clamp(climate.suspicion + deltas[1] * severity)
        climate.openness = _clamp(climate.openness + deltas[2] * severity)
        return [("climate.moved", severity,
                 {"place": place_id, "event": getattr(event, "type", ""),
                  "before": before, "after": climate.as_dict()})]

    def step(self, world, delta_minutes: int) -> list:
        """A place forgets, slowly, back toward what the pack authored.

        Without this, one bad afternoon marks a world permanently. Spreading is
        not done here -- see :meth:`carried`, which happens when somebody
        actually walks.
        """
        if not self.enabled or delta_minutes <= 0:
            return []
        relax = 1.0 - 0.5 ** ((delta_minutes / 60.0) / HALF_LIFE_HOURS)
        for place_id, climate in self.now.items():
            climate.blend(self.baselines[place_id], relax)
        self._carried_this_step = {}
        return []

    def carried(self, from_place: str, to_place: str) -> list:
        """Somebody walks out of one room and into another, bringing the mood.

        This is the answer to the obvious question about a player who is vile to
        one shopkeeper: the shopkeeper's own affect carries their ruined day into
        how they speak to the next customer, and *this* carries the room's mood
        with whoever leaves it. A square that has just watched a threat sends
        slightly guarded people into the bar, and the bar becomes slightly more
        guarded because they arrived.

        It is deliberately weak and capped. A shift change should not import a
        whole district's mood in one tick, and a single unpleasant afternoon in a
        market should not close a city.
        """
        if not self.enabled or from_place == to_place:
            return []
        if from_place not in self.now or to_place not in self.now:
            return []
        already = getattr(self, "_carried_this_step", {}).get(to_place, 0.0)
        room = MAX_CARRIED_PER_STEP - already
        if room <= 0.0:
            return []
        weight = min(CARRIED_PER_ARRIVAL, room)
        before = self.now[to_place].as_dict()
        self.now[to_place].blend(self.now[from_place], weight)
        if not hasattr(self, "_carried_this_step"):
            self._carried_this_step = {}
        self._carried_this_step[to_place] = already + weight
        return [("climate.carried", weight,
                 {"from": from_place, "to": to_place,
                  "before": before, "after": self.now[to_place].as_dict()})]

    # ----------------------------------------------------------- snapshot ----

    def as_dict(self) -> dict:
        return {"enabled": self.enabled,
                "now": {place_id: climate.as_dict()
                        for place_id, climate in sorted(self.now.items())}}

    def restore(self, data: dict) -> None:
        for place_id, values in (data.get("now") or {}).items():
            if place_id in self.now:
                self.now[place_id] = Climate(
                    candour=float(values.get("candour", 0.5)),
                    suspicion=float(values.get("suspicion", 0.5)),
                    openness=float(values.get("openness", 0.5)))

    def report(self) -> list:
        """What a designer wants to see: where it is tense, and how far from normal."""
        rows = []
        for place_id, climate in sorted(self.now.items()):
            base = self.baselines[place_id]
            drift = max(abs(climate.candour - base.candour),
                        abs(climate.suspicion - base.suspicion),
                        abs(climate.openness - base.openness))
            rows.append({"place": place_id, **climate.as_dict(),
                         "drift_from_baseline": round(drift, 3)})
        return rows
