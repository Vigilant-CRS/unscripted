"""A mood is catching, and that is why one rude customer ruins an afternoon.

The runtime has modelled affect per character since the beginning: a threatened
trader's valence drops to -0.95, her stress goes to 0.60, and she speaks faster
to *everybody* afterwards, not only to the person who threatened her. What it
never modelled is the next step, which is the one people actually notice: the
person she serves next is worse off for it, and the one after that a little worse
still.

Hatfield, Cacioppo & Rapson (*Emotional Contagion*, 1994) call it primitive
emotional contagion -- automatic mimicry of expression and posture, followed by
convergence of feeling, below the level of anybody deciding anything. It is fast,
it is small per exchange, and it accumulates.

So: **when two characters exchange a claim, a little of the speaker's mood moves
to the listener.** Three properties make it safe rather than a mood engine that
eats the world:

  * it is **damped by the listener's emotional stability** -- a steady person
    catches less, which is what the trait is for;
  * it is **weighted by how much the listener cares about the speaker**, because
    a stranger's bad afternoon is not contagious and a friend's is;
  * it is **capped per exchange and decays like any other mood**, so a chain of
    conversations converges rather than running away.

It moves *mood*, never *personality*. The baseline a character relaxes toward is
untouched -- as with the climate layer, this is weather, and the same line holds:
who somebody is does not change.

**Off by default**, and off means the multiplication never happens.

It stores nothing of its own. The only thing it writes is a character's mood,
which the snapshot already captures, so there is no restore path here and no
schema bump -- a save taken with the layer on loads with it off and simply stops
transferring.
"""
from __future__ import annotations

#: Most of a mood does not transfer. This is one exchange, not an hour together.
TRANSFER = 0.14

#: Below this the exchange is between people who barely know each other, and a
#: stranger's mood is not catching.
MIN_TIE = 0.08

#: Hard ceiling per exchange on each axis, so no single conversation can move
#: somebody more than this however extreme the speaker is.
MAX_STEP = 0.22


def _clamp(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))


class ContagionEngine:
    """One conversation's worth of somebody else's afternoon."""

    module_id = "contagion"

    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled
        self.params = {"transfer": TRANSFER, "min_tie": MIN_TIE,
                       "max_step": MAX_STEP}

    def between(self, speaker, listener) -> list:
        """Move a little of the speaker's mood onto the listener.

        Returns reason entries, or nothing at all when the layer is off, when the
        two are barely acquainted, or when there is no difference to transfer --
        which is most exchanges, and should be.
        """
        if not self.enabled or speaker is None or listener is None:
            return []
        if speaker.id == listener.id:
            return []
        speaker_affect = getattr(speaker, "affect", None)
        listener_affect = getattr(listener, "affect", None)
        if speaker_affect is None or listener_affect is None:
            return []

        # How much this person's mood is worth to me: familiarity carries most of
        # it, and liking decides whether their bad afternoon lands as sympathy or
        # slides off. Trust is deliberately not in it -- you can catch a mood from
        # somebody you do not believe.
        relationship = (getattr(listener, "relationships", None) or {}).get(
            speaker.id, {})
        familiarity = float(relationship.get("familiarity", 0.0) or 0.0)
        liking = float(relationship.get("liking", 0.0) or 0.0)
        tie = max(0.0, familiarity + 0.35 * max(0.0, liking))
        if tie < self.params["min_tie"]:
            return []

        # A steady person catches less. This is what emotional stability is for,
        # and using it here means the trait does work rather than sitting in a
        # character sheet.
        stability = float(getattr(listener, "big_five", {}).get(
            "emotional_stability", 0.5))
        weight = self.params["transfer"] * min(1.0, tie) * (1.0 - 0.6 * stability)
        if weight <= 0.0:
            return []

        moved = {}
        for axis in ("p", "a", "d"):
            mine = getattr(listener_affect.mood, axis)
            theirs = getattr(speaker_affect.mood, axis)
            step = _clamp((theirs - mine) * weight, self.params["max_step"])
            if abs(step) < 1e-4:
                continue
            setattr(listener_affect.mood, axis, _clamp(mine + step))
            moved[axis] = round(step, 4)

        if not moved:
            return []
        return [("contagion.caught", round(weight, 4), {
            "from": speaker.id, "to": listener.id,
            "tie": round(tie, 3), "moved": moved})]
