"""Everybody knowing is not the same as everybody knowing that everybody knows.

The runtime has always tracked who holds which belief. That is *private*
knowledge, and it is only the first of three things a society distinguishes:

    private   I know it.
    mutual    We all know it -- and I have no idea whether you do.
    common    We all know it, we all know we all know, and so on without end.

Lewis (*Convention*, 1969) and Aumann (1976) give the definition; Chwe (*Rational
Ritual*, 2001) gives the mechanism, and it is the part a game can use. Common
knowledge is not produced by more people finding out. It is produced by a
**public event** -- a broadcast, an announcement, something said in the open in
front of a crowd -- because what makes it public is that everybody there can see
everybody else taking it in. A thing whispered to fifty people one at a time is
mutual knowledge fifty times over and common knowledge to nobody.

WHY A GAME SHOULD CARE. Because it decides what can be *done*, not what is
believed. A scandal everyone privately knows is still deniable: raising it means
being the one who raised it. The moment it is common knowledge, denying it stops
working, and that transition is a mechanic -- it is the difference between a
player who has learned something and a player who has *made it public*.

So this module changes **what may be said, and what is still worth saying**:

    a secret that has become common knowledge in a character's own community
    stops functioning as a secret, because concealing what everybody knows
    everybody knows is not concealment; and

    nobody bothers to pass on what is already common knowledge between them,
    which is a categorical stop rather than the Daley-Kendall coin the diffusion
    layer already flips.

WHAT IT DELIBERATELY DOES NOT DO. It does not touch the belief maths. A public
event does not make anybody surer -- it is one origin, weighed once, exactly as
before. Treating publicity as evidence would be the same error as treating
repetition as proof, and this runtime exists partly to not make that error.

It also does not union its groups. Two separate public moments about the same
fact produce two publics, not one merged crowd: somebody who was in the square on
Tuesday does not thereby know about the people who were in the bar on Wednesday.
Overlapping subsets are absorbed; distinct crowds stay distinct.

**Off by default**, and off means nothing is recorded and nothing is consulted.
"""
from __future__ import annotations

from dataclasses import dataclass

#: How many people have to take something in at once before the room counts as a
#: crowd rather than a conversation. Two people talking know that they both know;
#: that is mutual knowledge and it is already what a conversation is. Chwe's
#: argument is about an audience, so three is the smallest honest number.
MIN_WITNESSES = 3

#: A place private enough that what is said in it is not said in the open. Packs
#: already declare `privacy_level`, so no world has to be re-authored for this.
PUBLIC_PRIVACY = 0.35

#: Below this an observer only half caught it, and half catching something is not
#: what a public event means.
MIN_QUALITY = 0.5

#: Media through which no crowd can see itself. A call reaches one person and a
#: note reaches one reader, however many people either eventually reaches.
PRIVATE_MEDIA = frozenset(("phone", "note"))

#: How many distinct publics to keep per fact before the oldest is dropped. A
#: bound rather than a claim: unbounded history here would grow a save file for
#: no gameplay gain.
MAX_PUBLICS_PER_KEY = 6


def public_key(core_key: str, polarity: str = "+") -> str:
    """The key a fact is public UNDER, which includes what was actually said.

    Publics used to be filed under the bare core key, so a broadcast that
    somebody was NOT alive marked the claim that they WERE as out in the open --
    the two are the same proposition and opposite assertions, and a register of
    what a crowd has established cannot conflate them. It decides whether a
    secret has stopped working, and the negation of a secret is not its
    disclosure.

    A bare key normalises to the positive reading, because that is what a pack
    writes when it declares what a secret protects.
    """
    return core_key if core_key[:1] in ("+", "-") else polarity + core_key


@dataclass(frozen=True)
class Public:
    """One crowd, one fact, one moment at which it stopped being deniable."""
    key: str
    members: frozenset
    since: int
    how: str
    place: str | None

    def as_dict(self) -> dict:
        return {"key": self.key, "members": sorted(self.members),
                "since": self.since, "how": self.how, "place": self.place}


class CommonKnowledgeEngine:
    """Which facts are out in the open, and in front of whom."""

    module_id = "common_knowledge"

    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled
        self.params = {"min_witnesses": MIN_WITNESSES,
                       "public_privacy": PUBLIC_PRIVACY,
                       "min_quality": MIN_QUALITY}
        #: fact key -> the crowds in front of which it has been established.
        self.publics: dict = {}

    # ------------------------------------------------------------ recording --

    def observe(self, world, event, learned) -> list:
        """Did this event make something common knowledge, and among whom?

        `learned` is who actually took the claim in, as `(agent_id, quality)` --
        supplied by the perception loop rather than recomputed here, so that this
        cannot disagree with what the rest of the runtime thinks people heard.
        """
        if not self.enabled:
            return []
        proposition = getattr(event, "proposition", None)
        if proposition is None or getattr(event, "type", "") == "question":
            return []

        how = self._how_public(world, event)
        if how is None:
            return []

        members = {agent_id for agent_id, quality in learned
                   if quality >= self.params["min_quality"]}
        # The person who said it is part of the crowd that knows it is out, even
        # though they learned nothing by saying it.
        actor = getattr(event, "actor", None)
        if actor and actor in getattr(world, "agents", {}):
            members.add(actor)
        if len(members) < self.params["min_witnesses"]:
            return []

        asserted = ((getattr(event, "payload", None) or {}).get("asserter_polarity")
                    or getattr(proposition, "polarity", "+"))
        key = public_key(proposition.core_key(), asserted)
        return self._record(Public(key=key, members=frozenset(members),
                                   since=int(getattr(event, "world_time", 0)),
                                   how=how,
                                   place=getattr(event, "location", None)))

    def _how_public(self, world, event) -> str | None:
        """The name of the reason this was in the open, or None if it was not."""
        if getattr(event, "type", "") == "broadcast":
            # Chwe's canonical case. Everybody listening knows the others are
            # listening, which is what a broadcast IS -- and it is why regimes
            # care so much more about a transmitter than about a rumour.
            return "broadcast"

        medium = (getattr(event, "payload", None) or {}).get("medium", "in_person")
        if medium in PRIVATE_MEDIA:
            return None

        place_id = getattr(event, "location", None)
        place = (getattr(world, "places", None) or {}).get(place_id) or {}
        if float(place.get("privacy_level", 0.5)) > self.params["public_privacy"]:
            return None
        return "in_the_open"

    def _record(self, public: Public) -> list:
        # Normalise on the way IN as well as on the way out. `observe` already
        # builds a signed key, and `public_key` is idempotent for one -- but a
        # caller that hands over a bare core key (a test, a restored save from
        # before polarity was recorded) must be filed where the lookups will
        # look, or the register answers "no" about something it is holding.
        if public.key != public_key(public.key):
            public = Public(key=public_key(public.key), members=public.members,
                            since=public.since, how=public.how, place=public.place)
        crowds = self.publics.setdefault(public.key, [])
        for existing in crowds:
            # Already established in front of these people or more of them.
            if public.members <= existing.members:
                return []
        # A larger crowd absorbs the smaller ones it contains: those people were
        # there for this too, and keeping both would be counting one moment twice.
        crowds[:] = [c for c in crowds if not (c.members <= public.members)]
        crowds.append(public)
        del crowds[:-MAX_PUBLICS_PER_KEY]
        return [("common_knowledge.established", float(len(public.members)), {
            "proposition": public.key, "how": public.how, "place": public.place,
            "members": sorted(public.members),
            "note": "not more evidence -- it is now undeniable in front of these people"})]

    # ------------------------------------------------------------- consulting --

    def is_common(self, key: str, *agent_ids) -> bool:
        """Is this common knowledge among all of these people at once?

        One crowd has to contain all of them. Two people who each learned it in
        front of a different crowd do not have it in common with each other, and
        collapsing that distinction would throw away the only thing this module
        models.
        """
        if not self.enabled or not agent_ids:
            return False
        wanted = set(agent_ids)
        return any(wanted <= public.members
                   for public in self.publics.get(public_key(key), ()))

    def is_out(self, key: str, agent_id: str) -> bool:
        """Is this out in the open in front of a crowd this character belongs to?

        The question a secret-holder asks. Not *does my questioner know* -- that
        is what trust is for -- but *is there any point in denying it*, and there
        is not once the people around you have all watched each other find out.
        """
        if not self.enabled:
            return False
        return any(agent_id in public.members
                   for public in self.publics.get(public_key(key), ()))

    def publics_for(self, key: str) -> list:
        return list(self.publics.get(public_key(key), ()))

    def report(self) -> list:
        """What a designer wants to see: what can no longer be denied, and to whom."""
        rows = []
        for key, crowds in sorted(self.publics.items()):
            for public in crowds:
                rows.append(public.as_dict())
        return rows

    # ------------------------------------------------------------- snapshot --

    def as_dict(self) -> dict:
        return {"enabled": self.enabled,
                "publics": [public.as_dict()
                            for key in sorted(self.publics)
                            for public in self.publics[key]]}

    def restore(self, data: dict) -> None:
        self.publics = {}
        for row in data.get("publics") or ():
            public = Public(key=str(row["key"]),
                            members=frozenset(row.get("members") or ()),
                            since=int(row.get("since", 0)),
                            how=str(row.get("how", "in_the_open")),
                            place=row.get("place"))
            self.publics.setdefault(public.key, []).append(public)
