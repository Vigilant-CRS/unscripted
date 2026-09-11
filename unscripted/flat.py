"""Flags: the way NPC knowledge is normally represented, implemented honestly.

Before/after comparisons in technical marketing are usually rigged, and the
reader who can tell is the one whose opinion decides the sale. So this is not a
competitor, not a reconstruction of anybody's product, and not a deliberately
weak thing built to lose. It is **a set of booleans** -- the representation most
shipped games actually use for what characters know, in about eighty lines, with
the source sitting in the repository next to the thing it is compared against.

    if (worldFlags.contains("player_attacked_market")) { ... }

That is the whole model, and it is not stupid. It is fast, it saves and loads,
every designer on the team understands it, and it has shipped a thousand games.
The comparison here is therefore never "flags are bad". It is a list of questions
and which of the two can *answer* them at all -- and every entry where flags
cannot is a structural fact about booleans, not an opinion about anyone's craft.

Two variants exist in the wild and this implements the common one:

  **global flags** -- a broadcast sets a fact and from then on the cast "knows"
  it. Modelled here.

  **per-character flags with authored propagation** -- a designer writes, for
  each pair who might pass something on, that they do. Strictly better, and the
  authoring cost grows with the square of the cast, which is why most games have
  three characters who react and forty who do not. Not modelled, and the
  comparison says so rather than quietly taking credit for the difference.

What a boolean cannot hold is not a defect of this file. It is the point: there
is nowhere to put who said it, how sure you are, which version you heard, when
you heard it, or whether the person who told you turned out to be lying.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .world import load_world_pack


@dataclass
class FlatWorld:
    """One boolean per fact, plus who has been told, which is the generous version."""

    facts: set = field(default_factory=set)
    #: Kept per character rather than purely global, so the comparison is against
    #: the better of the two common practices rather than the worse.
    known: dict = field(default_factory=dict)
    #: Every telling that happened, so this model is not accused of throwing away
    #: information it was handed. It records the event; it just has nowhere to
    #: *use* it -- the flag is the same boolean either way.
    tellings: list = field(default_factory=list)

    def learn(self, agent_id: str, fact: str) -> bool:
        """Set the flag. Returns whether anything changed -- usually nothing does."""
        held = self.known.setdefault(agent_id, set())
        if fact in held:
            return False
        held.add(fact)
        self.facts.add(fact)
        return True

    def broadcast(self, fact: str, agents) -> int:
        """A channel fires. Everyone gets the flag.

        This is the behaviour, not a caricature of it: a boolean has no field for
        who was listening, so a global fact set at a moment is set for everybody
        who can read it. Attention, distance and whether a character was even in
        the room are not representable.
        """
        return sum(1 for agent_id in agents if self.learn(agent_id, fact))

    def tell(self, speaker: str, listener: str, fact: str, *, honest: bool = True) -> bool:
        self.tellings.append({"from": speaker, "to": listener, "fact": fact,
                              "honest": honest})
        return self.learn(listener, fact)

    # ------------------------------------------------- the questions asked ----
    #
    # Each returns either an answer or None, and None means "there is nowhere in
    # this representation to hold that", which is the finding.

    def who_knows(self, fact: str) -> list:
        return sorted(agent for agent, held in self.known.items() if fact in held)

    def how_sure(self, agent_id: str, fact: str):
        """A boolean has two states, and neither of them is 'fairly sure'."""
        return "knows it" if fact in self.known.get(agent_id, ()) else "does not"

    def who_told(self, agent_id: str, fact: str):
        """None. The flag does not record where it came from."""
        return None

    def which_version(self, agent_id: str, fact: str):
        """None. There is one fact; a version that changed on the way is the same
        boolean or a different fact nobody authored."""
        return None

    def told_how_often(self, agent_id: str, fact: str):
        """A boolean cannot be set twice. Repetition is invisible by construction."""
        return None

    def was_it_a_lie(self, agent_id: str, fact: str):
        """None. A lie and an honest report set the identical flag."""
        return None

    def discredit(self, speaker: str) -> int:
        """Nothing changes. There is no edge from a flag back to who caused it.

        This is the one that costs a game the most: exposing a liar cannot undo
        what he convinced people of, because nothing recorded that he was the
        reason anybody believes it. The flag stays set.
        """
        return 0

    def forgets(self) -> int:
        """None do. Flags do not decay, which is why an NPC can quote something
        from forty hours of play ago as though it happened this morning."""
        return 0


def run(pack: str, *, predicate: str, tellings: list, agents: list) -> FlatWorld:
    """Play the same events through the flag model.

    `tellings` is the transmission list from the same recording the runtime
    produced, so both sides see the identical sequence of events. What differs is
    only what each representation can do with them.
    """
    world = load_world_pack(pack)
    flat = FlatWorld()
    fact = predicate

    for event in getattr(world, "scenario_events", []):
        payload = event.payload or {}
        if (payload.get("proposition") or {}).get("predicate") == predicate:
            flat.broadcast(fact, agents)

    for telling in tellings:
        flat.tell(telling["from"], telling["to"], fact,
                  honest=not telling.get("lie", False))
    return flat
