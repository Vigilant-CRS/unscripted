"""Somebody wants something, so somebody does something.

The tick has five steps and until now none of them asked what anybody wanted.
Scheduled events fire, routines move people, diffusion rolls dice over who
happens to be standing together, everyone decays, and the faction layer
escalates. Characters have goals -- *file the story first*, *close the case*, *not
be arrested for this* -- and nothing in a time advance ever consulted one.

The runtime's own evidence run says what that costs, in the section that was
written before this module existed:

    After saturation, little happens. The rumours are through the population
    within days, everyone becomes a stifler, and the world goes quiet -- across
    75,434 simulated days the long case demonstrates stability, not liveliness.

A world that goes quiet is not a living one. It is a stable one, which is a
different and lesser claim.

**Diffusion is who happens to talk. Pursuit is who has a reason to.** That is the
whole distinction, and it is why this is a separate module rather than a weight
inside the other: the same act -- one character asserting something to another --
is chosen by a different question. Diffusion asks *who is here*; pursuit asks
*who needs this said, and to whom*.

It deliberately invents no new channel. A pursued conversation is an ordinary
claim event, through the ordinary perception path, with the ordinary earshot,
provenance, distortion and hop count. Everything downstream is untouched; what
changes is which conversation happens.

**Off by default.** With `pursuit=False` nothing is scheduled, nothing is
emitted, and a run reproduces exactly as before. Same contract as the climate and
action layers, for the same reason: a studio that wants a quiet world should get
one.
"""
from __future__ import annotations

import re

from .determinism import derive_seed, seeded_uniform
from .medium import contacts_of, for_exchange

#: How often a character with a maximal goal is willing to go and raise it, in
#: world minutes. Deliberately slow: a cast that acts on its goals every twenty
#: minutes is not alive, it is frantic, and it saturates the world faster than
#: the diffusion layer it is meant to complement.
BASE_INTERVAL_MINUTES = 180.0

#: Words that carry no information about what a goal is about.
STOPWORDS = frozenset((
    "the", "a", "an", "of", "to", "for", "and", "or", "not", "be", "is", "it",
    "this", "that", "my", "his", "her", "their", "out", "in", "on", "at", "with",
    "keep", "get", "make", "next", "first", "own", "up", "down", "about",
))


def keywords(text: str) -> frozenset:
    """The words in a goal that could name something in the world."""
    words = re.findall(r"[a-z_]+", str(text or "").lower())
    return frozenset(word for word in words
                     if len(word) > 2 and word not in STOPWORDS)


class PursuitEngine:
    """One purposeful conversation at a time, from whoever most needs to have it."""

    module_id = "pursuit"

    def __init__(self, *, enabled: bool = False, media: bool = False):
        self.enabled = enabled
        #: Whether somebody may reach beyond the room they are standing in.
        self.media = media
        #: Whether somebody who can reach nobody writes it down instead.
        self.notes = False
        self.params = {
            "interval_minutes": BASE_INTERVAL_MINUTES,
            # A character will not go and raise something they are unsure of:
            # pursuit is for what you believe, not for what you suspect.
            "min_confidence": 0.55,
            # Ceiling per tick, for the same reason diffusion has one.
            "max_per_tick": 12,
            # How much MORE somebody elsewhere has to be trusted before a
            # character reaches for the phone instead of talking to whoever is
            # here. An absolute floor was the wrong shape: the default trust
            # between two people who have never met is 0.3, so any floor above it
            # sent everybody to the phone and turned a market square into a call
            # centre.
            "worth_a_call": 0.12,
            # How much MORE somebody out of reach entirely has to be trusted
            # before a character writes it down instead of only saying it to
            # whoever is here. Larger than `worth_a_call` on purpose: ringing
            # somebody is easy and writing to somebody is a decision.
            "worth_writing": 0.20,
        }
        #: When each character last acted on a goal, so a long time skip does not
        #: produce a week of conversations in one step.
        self._last_acted: dict = {}

    # ------------------------------------------------------------- selection --

    def _due(self, agent, world_time: int) -> bool:
        goals = getattr(agent, "goals", None) or []
        if not goals:
            return False
        priority = max(float(goal.get("priority", 0.5)) for goal in goals)
        if priority <= 0.0:
            return False
        # A stronger goal comes round sooner. Priority 1.0 acts every three
        # hours; priority 0.5 every six.
        interval = self.params["interval_minutes"] / max(0.05, priority)
        return world_time - self._last_acted.get(agent.id, -10 ** 9) >= interval

    def _wants(self, agent) -> frozenset:
        """What this character's goals are about, as words to match beliefs on.

        A goal may say so precisely with `"about": [...]`, naming predicates or
        entity ids. Where it does not, the words of the goal itself are used --
        imprecise, and better than the alternative, which is a layer that only
        works for packs written after it.
        """
        wanted = set()
        for goal in getattr(agent, "goals", None) or []:
            for named in goal.get("about", ()) or ():
                wanted |= keywords(named)
            wanted |= keywords(goal.get("content", ""))
        return frozenset(wanted)

    def _relevant(self, agent, wanted: frozenset):
        """The belief this character would most want raised, or None.

        Relevance first, conviction second. Somebody trying not to be arrested
        raises the thing that bears on being arrested, not the thing they happen
        to be surest about.
        """
        best, best_score = None, 0.0
        floor = self.params["min_confidence"]
        for key, belief in agent.beliefs.items():
            confidence = max(belief.expected_prob, 1.0 - belief.expected_prob)
            if confidence < floor:
                continue
            overlap = len(wanted & keywords(key))
            if overlap == 0:
                continue
            score = overlap + confidence
            if score > best_score:
                best, best_score = key, score
        return best

    def _listener(self, agent, occupants, world):
        """Whom to say it to: the person they trust most who they can reach.

        Not the nearest and not a random draw. Somebody acting on a goal picks
        who they think will help, and the relationship layer already knows who
        that is. With media on, "reach" is no longer the same as "in the room":
        somebody whose number they have is a phone call away, which is how a
        claim crosses a district without anybody walking.
        """
        def strongest(pool, medium_of):
            best, best_trust, best_medium = None, -1.0, None
            for other in pool:
                if other.id == agent.id:
                    continue
                medium = medium_of(other)
                if medium is None:
                    continue
                trust = agent.trust_in(other.id)
                if trust > best_trust or (trust == best_trust and best is not None
                                          and other.id < best.id):
                    best, best_trust, best_medium = other, trust, medium
            return best, best_trust, best_medium

        here, here_trust, here_medium = strongest(
            occupants, lambda other: for_exchange(agent, other, enabled=self.media))
        if not self.media:
            return here, here_medium

        # THE PHONE IS A FALLBACK, NOT A PREFERENCE. Somebody with something to
        # say goes to whoever is standing there if that person is worth telling,
        # and rings somebody else when they are not. Ranking every contact in the
        # world against the room turned five days into ninety-eight phone calls
        # and thirty-four conversations, which is not a market square.
        away = [other for other in sorted(world.agents.values(), key=lambda a: a.id)
                if other.location != agent.location]
        called, called_trust, called_medium = strongest(
            away, lambda other: for_exchange(agent, other, enabled=True))
        if called is not None and called_trust >= here_trust + self.params["worth_a_call"]:
            return called, called_medium
        return here, here_medium

    # ------------------------------------------------------------------ tick --

    def step(self, world, runtime, delta_minutes: int, player_id=None) -> list:
        """Let whoever is due act on a goal, once each."""
        if not self.enabled or delta_minutes <= 0:
            return []

        by_place = {}
        for agent in world.agents.values():
            if agent.id == player_id or not agent.location:
                continue
            by_place.setdefault(agent.location, []).append(agent)

        reasons, acted = [], 0
        for place_id in sorted(by_place):
            occupants = sorted(by_place[place_id], key=lambda a: a.id)
            # Somebody alone in a room used to be skipped outright, which was
            # right while the only thing pursuit could do was speak. It is
            # exactly wrong once it can write: a person with something to say
            # and nobody to say it to is the note case, and it was the only
            # case that never reached the code for it.
            if len(occupants) < 2 and not self.notes:
                continue
            for agent in occupants:
                if acted >= self.params["max_per_tick"]:
                    return reasons
                if not self._due(agent, world.world_time):
                    continue

                wanted = self._wants(agent)
                if not wanted:
                    continue
                key = self._relevant(agent, wanted)
                if key is None:
                    continue
                listener, medium = self._listener(agent, occupants, world)

                # THE PERSON THEY ACTUALLY NEEDED. `_listener` answers "who can I
                # reach", which is the right question for a conversation and the
                # wrong one for a note: nobody writes to the person standing next
                # to them. So ask the other question too -- who did they most want
                # this to get to -- and if that person is out of reach entirely,
                # they leave word where they are and hope. That is the whole
                # mechanism, and it needs no new intention or scheduler.
                if self.notes:
                    wanted_them = self._out_of_reach(agent, world, listener)
                    if wanted_them is not None:
                        seed = derive_seed(world.global_seed, agent.id,
                                           wanted_them.id, world.world_time,
                                           self.module_id, "write")
                        if seeded_uniform(seed) < 0.5:
                            self._leave_word(runtime, world, agent, wanted_them.id,
                                             key, place_id, reasons)

                if listener is None:
                    self._last_acted[agent.id] = world.world_time
                    continue

                # Even a due character does not always speak. The draw is seeded,
                # so a replay of the same world produces the same conversations.
                seed = derive_seed(world.global_seed, agent.id, world.world_time,
                                   place_id, self.module_id)
                if seeded_uniform(seed) > 0.75:
                    self._last_acted[agent.id] = world.world_time
                    continue

                told = runtime.diffusion.tell_about(
                    world, runtime, agent, listener, place_id, key, reasons,
                    medium)
                self._last_acted[agent.id] = world.world_time
                if told:
                    acted += 1
                    reasons.append(("pursuit.acted", 1.0, {
                        "agent": agent.id, "listener": listener.id,
                        "place": place_id, "about": key,
                        "medium": medium.name if medium is not None else "in_person",
                        "goal": (agent.goals or [{}])[0].get("content", "")}))
        return reasons

    def _out_of_reach(self, agent, world, reachable):
        """The person they most wanted to tell, if they cannot be told.

        Out of reach means both things at once: not in this room, and not on the
        end of a telephone. Somebody they could simply have rung is not somebody
        they would write to.
        """
        floor = (agent.trust_in(reachable.id) if reachable is not None else 0.0)
        floor += self.params["worth_writing"]
        # Having somebody's number only puts them in reach if telephones exist
        # in this world at all. With `media` off there is nothing to ring, and
        # everybody outside the room is equally out of reach -- which is when a
        # note stops being a curiosity and becomes the only way to reach anyone.
        contacts = contacts_of(agent) if self.media else frozenset()
        best, best_trust = None, floor
        for other in sorted(world.agents.values(), key=lambda a: a.id):
            if other.id == agent.id or other.location == agent.location:
                continue
            if other.id in contacts:
                continue
            trust = agent.trust_in(other.id)
            if trust > best_trust:
                best, best_trust = other, trust
        return best

    def _leave_word(self, runtime, world, agent, recipient_id, key, place_id,
                    reasons) -> bool:
        board = getattr(runtime, "notes", None)
        if board is None or not board.enabled:
            return False
        return board.leave(world, agent, recipient_id, place_id, key,
                           agent.beliefs.get(key), reasons)

    # ----------------------------------------------------------- snapshot ----

    def as_dict(self) -> dict:
        return {"enabled": self.enabled, "last_acted": dict(self._last_acted)}

    def restore(self, data: dict) -> None:
        self._last_acted = {str(key): int(value)
                            for key, value in (data.get("last_acted") or {}).items()}
