"""A claim that outlives the conversation, and can be read by the wrong person.

`unscripted/medium.py` has described three ways of saying something since it was
written, and only two of them ever happened. `NOTE` sat in the table with its
numbers and nothing in the runtime ever produced one.

It is worth producing, because a note is not a slower phone call. It differs in
one way that no other channel does:

    a conversation is gone the moment it ends. A note is still there.

Everything interesting follows from that. A note can be found by somebody it was
not written for, which makes it the runtime's first piece of *evidence* rather
than testimony -- a claim with an author attached that the author cannot take
back. It reaches somebody who was never in the room, without either party
choosing the moment. And it can be left for somebody who cannot be reached at
all, which is precisely when a person writes one.

So the generator is not "sometimes characters write notes". It is:

    somebody has a reason to tell a specific person something, and cannot reach
    them -- not here, and no number for them. They leave word where they are.

That is the honest version, because it uses no knowledge the character does not
have. Nobody writes a note to an address they do not know; they leave it where
they stand and hope the right person comes through.

WHERE THE DETAIL IS LOST. On a phone the levelling happens in the telling, so the
distortion layer runs at the moment of the exchange. A note is the other way
round: whatever is going to be lost is lost when it is *written* -- the tone, the
hesitation, the thing the author decided not to put in writing -- and after that
the words are fixed. So this distorts once, at `leave()`, at the medium's own
rate, and reading is faithful. A note that says the wrong thing goes on saying
exactly the wrong thing to everybody who reads it, which is the difference
between a rumour and a document.

**Off by default**, and it rides on `media`: a world with no telephones has no
notes either, because both are the same claim -- that a message can outrun the
room it was spoken in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import distortion
from .determinism import derive_seed, seeded_uniform
from .events import Event
from .medium import NOTE

#: How many unread notes one place holds before the oldest is thrown out. A
#: bound on save size, not a claim about how many notes a bar can hold.
MAX_PER_PLACE = 12

#: How long an unread note stays where it was left, in world minutes. Five days:
#: long enough to cross a routine, short enough that a world does not silt up
#: with messages nobody ever came for.
LIFETIME_MINUTES = 5 * 24 * 60

#: The chance per hour that somebody it was NOT written for notices it anyway,
#: before their own curiosity is taken into account. Deliberately low, and
#: capped at one interception per note below: a note everybody reads is a
#: poster. At the first value tried, more notes were intercepted than delivered
#: over a week, which made being read by a stranger the normal fate of a letter
#: rather than the thing that goes wrong.
INTERCEPT_BASE = 0.02


@dataclass
class Note:
    """One written claim, sitting where it was left."""
    note_id: str
    author: str
    intended_for: str
    place: str
    key: str
    proposition: object
    polarity: str
    origin: str
    hops: int
    written_at: int
    distorted_as: str | None = None
    read_by: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"note_id": self.note_id, "author": self.author,
                "intended_for": self.intended_for, "place": self.place,
                "key": self.key, "proposition": self.proposition.as_dict(),
                "polarity": self.polarity, "origin": self.origin,
                "hops": self.hops, "written_at": self.written_at,
                "distorted_as": self.distorted_as, "read_by": list(self.read_by)}


class NoteBoard:
    """What has been left lying about, and who picks it up."""

    module_id = "notes"

    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled
        self.params = {"max_per_place": MAX_PER_PLACE,
                       "lifetime_minutes": LIFETIME_MINUTES,
                       "intercept_base": INTERCEPT_BASE}
        #: place id -> notes lying there.
        self.by_place: dict = {}
        self._counter = 0

    # -------------------------------------------------------------- writing --

    def leave(self, world, author, intended_for: str, place_id: str, key: str,
              belief, reasons: list) -> bool:
        """Write it down and leave it here, for somebody who is not here.

        Returns False when the layer is off, so a caller can ask unconditionally.
        """
        if not self.enabled or belief is None:
            return False

        proposition = belief.proposition
        polarity = "+" if belief.expected_prob >= 0.5 else "-"
        distorted_as = None
        # What is lost is lost in the writing. Same layer, same rates as any
        # retelling, scaled by how much this medium carries -- see the module
        # docstring for why it happens here and not at the reading.
        seed = derive_seed(world.global_seed, author.id, intended_for,
                           world.world_time, self.module_id, "write")
        from . import content
        if seeded_uniform(seed) < 0.18 * NOTE.distortion_scale():
            outcome = distortion.distort(
                proposition, speaker=author, world=world,
                seed=derive_seed(world.global_seed, author.id, intended_for,
                                 world.world_time, self.module_id, "kind"),
                protected=content.protected_keys(author.secrets))
            if outcome is not None:
                proposition, kind, detail = outcome
                distorted_as = kind
                if kind == distortion.INVERSION:
                    polarity = "-" if polarity == "+" else "+"

        self._counter += 1
        note = Note(note_id=f"note_{self._counter}", author=author.id,
                    intended_for=intended_for, place=place_id, key=key,
                    proposition=proposition, polarity=polarity,
                    origin=belief.primary_origin or f"origin:{author.id}:{key}",
                    hops=belief.hops + 1, written_at=int(world.world_time),
                    distorted_as=distorted_as)
        pile = self.by_place.setdefault(place_id, [])
        pile.append(note)
        del pile[:-self.params["max_per_place"]]
        reasons.append(("note.left", 1.0, {
            "author": author.id, "for": intended_for, "place": place_id,
            "proposition": str(proposition), "distorted": distorted_as,
            "note": "could not reach them; left word where they were standing"}))
        return True

    # -------------------------------------------------------------- reading --

    def step(self, world, runtime, delta_minutes: int) -> list:
        """Whoever is standing where a note was left may pick it up."""
        if not self.enabled or delta_minutes <= 0:
            return []

        hours = max(1.0, delta_minutes / 60.0)
        reasons = []
        here = {}
        for agent in world.agents.values():
            if agent.location:
                here.setdefault(agent.location, []).append(agent)

        for place_id in sorted(self.by_place):
            pile = self.by_place[place_id]
            occupants = sorted(here.get(place_id, ()), key=lambda a: a.id)
            keep = []
            for note in pile:
                if world.world_time - note.written_at > self.params["lifetime_minutes"]:
                    reasons.append(("note.went_unread", 0.0, {
                        "note": note.note_id, "author": note.author,
                        "for": note.intended_for, "place": place_id,
                        "note_text": "nobody ever came for it"}))
                    continue
                taken = False
                for reader in occupants:
                    if reader.id == note.author or reader.id in note.read_by:
                        continue
                    intended = reader.id == note.intended_for
                    if not intended:
                        # Once somebody has nosed at it, it has been seen. A
                        # second and third stranger reading the same note adds
                        # nothing a game can use and multiplies one slip into a
                        # broadcast.
                        if note.read_by or not self._notices(world, reader, note,
                                                             hours):
                            continue
                    self._deliver(world, runtime, reader, note, place_id,
                                  intended, reasons)
                    note.read_by.append(reader.id)
                    if intended:
                        # It was for them; they take it with them. An interceptor
                        # reads it and puts it back, which is what makes a note
                        # worth intercepting more than once.
                        taken = True
                        break
                if not taken:
                    keep.append(note)
            self.by_place[place_id] = keep
        return reasons

    def _notices(self, world, reader, note, hours: float) -> bool:
        """Does somebody it was not written for spot it?"""
        chance = self.params["intercept_base"] * hours * (
            0.5 + reader.trait("curiosity"))
        seed = derive_seed(world.global_seed, reader.id, note.note_id,
                           world.world_time, self.module_id, "notice")
        return seeded_uniform(seed) < min(0.6, chance)

    def _deliver(self, world, runtime, reader, note, place_id, intended, reasons):
        """A read note is an ordinary claim, through the ordinary path.

        No new belief mechanism: it carries the author's origin and hop count, it
        is weighed at the medium's trust factor, and nobody overhears it. The one
        thing it does that no conversation can is arrive with its author's name on
        it when the author is not there to be asked about it.
        """
        strength = (runtime.diffusion.params["fidelity_decay"] ** note.hops
                    * NOTE.trust_factor)
        event = Event(
            event_id=world.new_event_id(),
            world_time=world.world_time,
            type="claim",
            actor=note.author,
            location=place_id,
            payload={
                "proposition": note.proposition.as_dict(),
                "asserter_polarity": note.polarity,
                "origin_event": note.origin,
                "summary": f"a note from {note.author}",
                "importance": 0.35,
                "domain": "gossip",
                # Nobody overhears a note being read, and the perception layer
                # must not put the author in the room: they are not here.
                "audience": [reader.id],
                "medium": "note",
                "diffusion": {"speaker": note.author, "listener": reader.id,
                              "hops": note.hops, "distorted": bool(note.distorted_as),
                              "distortion_kind": note.distorted_as,
                              "distortion_detail": {},
                              "fidelity": round(strength, 4)},
                "assertion_strength": round(strength, 4),
            },
        )
        runtime.process_event(event)
        reasons.append(("note.read" if intended else "note.intercepted",
                        float(note.hops), {
            "reader": reader.id, "author": note.author,
            "for": note.intended_for, "place": place_id,
            "proposition": str(note.proposition), "origin": note.origin,
            "note": ("read by the person it was for" if intended else
                     "read by somebody it was not written for, and left where "
                     "it was")}))

    # ------------------------------------------------------------- reading ---

    def at(self, place_id: str) -> list:
        return list(self.by_place.get(place_id, ()))

    def report(self) -> list:
        return [note.as_dict() for place_id in sorted(self.by_place)
                for note in self.by_place[place_id]]

    # ------------------------------------------------------------ snapshot ---

    def as_dict(self) -> dict:
        return {"enabled": self.enabled, "counter": self._counter,
                "notes": self.report()}

    def restore(self, data: dict) -> None:
        from .ontology import Proposition
        self.by_place = {}
        self._counter = int(data.get("counter", 0))
        for row in data.get("notes") or ():
            note = Note(note_id=str(row["note_id"]), author=str(row["author"]),
                        intended_for=str(row["intended_for"]),
                        place=str(row["place"]), key=str(row["key"]),
                        proposition=Proposition.from_dict(row["proposition"]),
                        polarity=str(row.get("polarity", "+")),
                        origin=str(row.get("origin", "")),
                        hops=int(row.get("hops", 1)),
                        written_at=int(row.get("written_at", 0)),
                        distorted_as=row.get("distorted_as"),
                        read_by=list(row.get("read_by") or ()))
            self.by_place.setdefault(note.place, []).append(note)
