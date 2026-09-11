"""A promise that nothing ever checks is not a promise, it is a line of dialogue.

The runtime has taken promises since the beginning. A player types *I promise to
pay you*, the parser recognises it, an event of type `promise` is emitted, and
every witness encodes a memory whose type is `commitment`. Then nothing. No
deadline, no keeping, no breaking, and no consequence -- and `SocialExchangeEngine
.on_commitment_resolved`, which has always known exactly what a kept and a broken
promise are worth, was never called by anything:

    kept    trust +0.8, liking +0.4
    broken  trust -0.7, liking -0.5, reputation "reliable" -0.4

That last line is why three engines in the runtime looked dead. `ReputationEngine`
had no producer, so `agent.reputation` was empty in every world at every time;
`unscripted/sociolinguistics.py` reads it to compute perceived status and was therefore
reading a permanently empty mapping. The missing piece was never those engines.
It was the thing that resolves a promise.

HOW A PROMISE IS JUDGED, AND WHY THAT WAY. Not against the truth. This runtime
holds no ground truth about whether somebody paid -- it holds what people
believe, and inventing an oracle here would contradict the whole design. So:

    a promise is kept when the person it was made to comes to believe it was.

That is the right answer for a social simulation and not a compromise. Reputation
has always been about what people think happened. A promise quietly fulfilled
where the promisee never finds out damages the promiser exactly as much as one
that was broken, which is unfair, true, and the reason people make a point of
being seen to deliver.

WHO LEARNS OF IT. Only the promisee, and whoever was in earshot when the promise
was made -- those are the people for whom it was ever a promise. It does not
become a fact about the town, because a broken promise is not news; it is a
disappointment, and it travels the way disappointments do, through the diffusion
layer if it travels at all.

**Off by default.** With `promises=False` nothing is tracked, nothing resolves,
and a run reproduces exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: How long a promise has, in world minutes, when nothing in it says. Two days:
#: long enough that a player can plausibly act on it within a session, short
#: enough that the consequence lands while they still remember making it.
DEFAULT_HORIZON_MINUTES = 2 * 24 * 60

#: How much MORE the promisee has to believe it happened than they did when the
#: promise was made, for it to count as kept.
#:
#: A margin rather than an absolute threshold, and that is a correction. The
#: first version asked for a fixed 0.55, which measurement showed was the wrong
#: shape: one ordinary piece of evidence about a fresh proposition moves a
#: belief from 0.500 to 0.537, so a fixed 0.55 silently required TWO independent
#: confirmations before anybody was credited with keeping a promise made to them
#: personally. That is the right bar for a bystander weighing a rumour and the
#: wrong one for the person who was owed.
#:
#: Asking about the movement instead says what was actually meant -- *did
#: anything reach them that says you came through* -- and it survives a later
#: recalibration of the belief engine's constants, which an absolute number
#: would not. 0.02 sits above floating-point noise and well below one ordinary
#: piece of evidence.
KEPT_MARGIN = 0.002

#: A cap on how many open promises one character can be carrying. A bound on
#: save size rather than a claim about human nature; the oldest goes first.
MAX_OPEN_PER_AGENT = 24


@dataclass
class Promise:
    """One undertaking, and the moment it stops being open."""
    promise_id: str
    promiser: str
    promisee: str
    key: str
    made_at: int
    due_at: int
    witnesses: list = field(default_factory=list)
    #: What the promisee already believed when it was made. Judging on the
    #: movement from here, rather than on an absolute number, is what keeps this
    #: meaning "something reached them" whatever the belief constants are.
    promisee_prior: float = 0.5
    state: str = "open"          # open | kept | broken
    resolved_at: int | None = None

    def as_dict(self) -> dict:
        return {"promise_id": self.promise_id, "promiser": self.promiser,
                "promisee": self.promisee, "proposition": self.key,
                "made_at": self.made_at, "due_at": self.due_at,
                "witnesses": list(self.witnesses),
                "promisee_prior": round(self.promisee_prior, 6),
                "state": self.state, "resolved_at": self.resolved_at}


class PromiseLedger:
    """What has been undertaken, to whom, and by when."""

    module_id = "promises"

    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled
        self.params = {"horizon_minutes": DEFAULT_HORIZON_MINUTES,
                       "kept_margin": KEPT_MARGIN,
                       "max_open_per_agent": MAX_OPEN_PER_AGENT}
        self.open: list = []
        self.settled: list = []
        self._counter = 0

    # ------------------------------------------------------------- taking --

    def record(self, world, event, witnesses) -> list:
        """A `promise` event becomes something that will be checked.

        `witnesses` are the observers the perception layer says took it in --
        supplied rather than recomputed, so this cannot come to disagree with the
        rest of the runtime about who was there.
        """
        if not self.enabled or getattr(event, "type", "") != "promise":
            return []
        proposition = getattr(event, "proposition", None)
        if proposition is None:
            return []
        promiser = getattr(event, "actor", None)
        payload = getattr(event, "payload", None) or {}
        promisee = payload.get("target") or payload.get("addressee")
        if not promiser or not promisee or promiser == promisee:
            # A promise to nobody in particular is a statement of intent, and
            # this layer has nothing to say about those.
            return []

        # When it comes due: what the promise itself says, or the default. A
        # proposition that names its own end is the author being explicit, and
        # that should win over any constant in this file.
        stated_end = getattr(proposition, "valid_end", None)
        due = (int(stated_end) if stated_end
               else int(world.world_time) + self.params["horizon_minutes"])

        listener = world.agents.get(promisee)
        held = listener.beliefs.get(proposition.core_key()) if listener else None

        self._counter += 1
        promise = Promise(
            promise_id=f"promise_{self._counter}", promiser=promiser,
            promisee=promisee, key=proposition.core_key(),
            made_at=int(world.world_time), due_at=due,
            promisee_prior=(0.5 if held is None else float(held.expected_prob)),
            witnesses=sorted(set(witnesses) | {promiser, promisee}))
        self.open.append(promise)
        self._trim(promiser)
        return [("promise.made", 1.0, {
            "promise": promise.promise_id, "by": promiser, "to": promisee,
            "proposition": promise.key, "due_at": due,
            "heard_by": promise.witnesses})]

    def _trim(self, promiser: str) -> None:
        mine = [p for p in self.open if p.promiser == promiser]
        for stale in mine[:-self.params["max_open_per_agent"]]:
            self.open.remove(stale)

    # ----------------------------------------------------------- settling --

    def settle(self, world, runtime, promise_id: str, kept: bool,
               note: str = "") -> list:
        """The game says what happened. The authoritative path.

        A studio that scripts "the player hands over the money" should not have
        to hope an NPC was paying attention: it knows, and this is how it says
        so. Everything downstream is identical to a promise that came due on its
        own -- same deltas, same reputation, same witnesses -- so a world where
        every promise is settled explicitly and one where none is behave the same
        way apart from *which* answer they arrive at.
        """
        if not self.enabled:
            return []
        promise = next((p for p in self.open if p.promise_id == promise_id), None)
        if promise is None:
            raise KeyError(promise_id)
        self.open.remove(promise)
        return self._settle(world, runtime, promise, forced=bool(kept), note=note)

    def open_ids(self) -> list:
        return [p.promise_id for p in self.open]

    # ---------------------------------------------------------- resolving --

    def step(self, world, runtime, delta_minutes: int) -> list:
        """Settle whatever has come due, and let it cost or earn something."""
        if not self.enabled or delta_minutes <= 0:
            return []
        reasons = []
        still_open = []
        for promise in self.open:
            if world.world_time < promise.due_at:
                still_open.append(promise)
                continue
            reasons += self._settle(world, runtime, promise)
        self.open = still_open
        return reasons

    def _believes_it_happened(self, world, promise) -> float:
        """How sure the promisee is that the promised thing came about."""
        promisee = world.agents.get(promise.promisee)
        if promisee is None:
            return 0.0
        belief = promisee.beliefs.get(promise.key)
        return 0.0 if belief is None else belief.expected_prob

    def _settle(self, world, runtime, promise, forced=None, note="") -> list:
        confidence = self._believes_it_happened(world, promise)
        judged_by = "the engine" if forced is not None else "the promisee"
        kept = (forced if forced is not None
                else confidence - promise.promisee_prior
                     >= self.params["kept_margin"])
        promise.state = "kept" if kept else "broken"
        promise.resolved_at = int(world.world_time)
        self.settled.append(promise)

        promiser = world.agents.get(promise.promiser)
        promisee = world.agents.get(promise.promisee)
        reasons = [("promise.kept" if kept else "promise.broken",
                    round(confidence, 3), {
                        "promise": promise.promise_id, "by": promise.promiser,
                        "to": promise.promisee, "proposition": promise.key,
                        "promisee_confidence": round(confidence, 3),
                        "was": round(promise.promisee_prior, 3),
                        "moved": round(confidence - promise.promisee_prior, 3),
                        "judged_by": judged_by, "engine_note": note,
                        "note": (note or ("the engine said so" if forced is not None
                                 else "judged on what the person it was made to "
                                      "came to believe, because this runtime "
                                      "holds no ground truth about whether it "
                                      "happened"))})]
        if promisee is None or promiser is None:
            return reasons

        # THE DELTAS ARE NOT INVENTED HERE. SocialExchangeEngine has always known
        # what a kept and a broken promise are worth; it simply had no caller.
        deltas = runtime.exchange.on_commitment_resolved(
            promise.promisee, promise.promiser, kept)
        relationship_deltas = [d for d in deltas if d.key.module == "relationship"]
        reputation_deltas = [d for d in deltas if d.key.module == "reputation"]
        runtime.relationship.apply(promisee, relationship_deltas, reasons)
        runtime.reputation.apply(promisee, reputation_deltas, reasons)

        # Everyone who heard it made also sees it come to nothing. Not the town:
        # a broken promise is not news, it is a disappointment, and it reaches
        # the people for whom it was a promise in the first place.
        for witness_id in promise.witnesses:
            if witness_id in (promise.promisee, promise.promiser):
                continue
            witness = world.agents.get(witness_id)
            if witness is None:
                continue
            runtime.reputation.apply(witness, reputation_deltas, reasons)
        return reasons

    # ------------------------------------------------------------ reading --

    def owed_by(self, agent_id: str) -> list:
        return [p.as_dict() for p in self.open if p.promiser == agent_id]

    def owed_to(self, agent_id: str) -> list:
        return [p.as_dict() for p in self.open if p.promisee == agent_id]

    def report(self) -> dict:
        return {"open": [p.as_dict() for p in self.open],
                "settled": [p.as_dict() for p in self.settled[-50:]]}

    # ----------------------------------------------------------- snapshot --

    def as_dict(self) -> dict:
        return {"enabled": self.enabled, "counter": self._counter,
                "open": [p.as_dict() for p in self.open],
                "settled": [p.as_dict() for p in self.settled]}

    def restore(self, data: dict) -> None:
        def build(row):
            return Promise(
                promise_id=str(row["promise_id"]), promiser=str(row["promiser"]),
                promisee=str(row["promisee"]), key=str(row["proposition"]),
                made_at=int(row.get("made_at", 0)), due_at=int(row.get("due_at", 0)),
                witnesses=list(row.get("witnesses") or ()),
                promisee_prior=float(row.get("promisee_prior", 0.5)),
                state=str(row.get("state", "open")),
                resolved_at=row.get("resolved_at"))
        self._counter = int(data.get("counter", 0))
        self.open = [build(r) for r in data.get("open") or ()]
        self.settled = [build(r) for r in data.get("settled") or ()]
