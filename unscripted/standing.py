"""Standing: what the town thinks of you, because of what it saw you do.

The runtime already had two thirds of this and nobody had joined them up. Attack
somebody in the open and the place closes up, the victim mobilises, and
bystanders who share a belonging with them feel that belonging threatened. What
did **not** happen -- measured, not assumed -- was that anybody thought worse of
*you*. Only a broken promise moved a player's standing, because `promises` was
the one producer `ReputationEngine` ever had.

So this layer answers one question: **you were seen doing something to somebody
-- what does that do to how you are treated afterwards?**

WHY IT IS DRIVEN BY BELIEF AND NOT BY WITNESSING. The obvious implementation is
a loop over everyone in the room. That gives you a reputation counter, which
every game has had since 1997. This one instead attaches a proposition to the
act -- `mistreated(who=victim, by=actor)` -- and lets the existing machinery
carry it:

  * whoever is in the room perceives it and forms a belief, with provenance;
  * diffusion passes it on, and it decays, and it can be doubted;
  * standing then moves in proportion to **how much the hearer believes it**.

Three things fall out of that for free, and they are the whole difference:

  1. Somebody who was not there can still come to think badly of you, because
     they were told. That is the point of this runtime.
  2. What you saw yourself weighs more than what you heard, because certainty
     is what scales the delta -- not a hop count somebody tuned.
  3. A character can lie about what you did, and the lie moves standing exactly
     as far as it is believed. No extra code: it is a claim like any other.

WHAT IT DOES NOT DO. It does not touch personality, and it does not decay on its
own. Relationships in this runtime move slowly up and fast down and are then
simply where they are; a standing that quietly healed would let a player wait
out a reputation, which is a design decision and not one this layer should make
behind an author's back.

OFF BY DEFAULT, AND OFF IS BYTE-IDENTICAL. With `standing=False` no proposition
is attached to an act, nothing is stored, nothing is judged, and a run
reproduces the snapshot it produced before this module existed. A test asserts
that rather than asking anyone to believe it.
"""
from __future__ import annotations

from .statekey import (liking_delta, relationship_delta, reputation_delta,
                       trust_delta)

#: Predicates this layer understands, and what being believed to have done one
#: is worth. `weight` scales the whole judgement; `dimension` is the reputation
#: axis it moves.
#:
#: Kept deliberately small. Two predicates covering cruelty and kindness are
#: enough to show the mechanic, and a pack that wants "cheated", "stole from" or
#: "stood up for" adds them in `world.json: standing_conduct` rather than here --
#: what counts as decency is a fact about a setting, not about an engine.
DEFAULT_CONDUCT = {
    "mistreated": {"dimension": "decent", "sign": -1.0, "weight": 1.0},
    "helped": {"dimension": "decent", "sign": +1.0, "weight": 0.7},
}

#: Being kind is quieter than being cruel. Not a moral claim: an unkindness in
#: the street is remarked on and a kindness is mostly not, which is why the
#: positive weight above is lower and why nothing here is symmetric.
#:
#: How far a single believed act moves the actor's standing, before certainty
#: and before how much the hearer cared about the victim.
BASE_STEP = 0.5

#: How much of the judgement survives when the hearer has no feeling about the
#: victim at all. Cruelty to a stranger still counts -- most of it does -- but
#: cruelty to someone you like counts for more.
STRANGER_FLOOR = 0.6

#: Standing never moves further than this from one act, however certain and
#: however beloved the victim. A single event should not be able to make
#: somebody's mind up on its own; that is what repetition is for.
MAX_STEP = 0.35

#: Of a believed cruelty, how much becomes WARINESS OF YOU rather than dislike.
#:
#: `fear` was read in three places and written in none: it decides whether a
#: threat is expected to work or to backfire, and it pulls a character's
#: conversational stance away from warmth, which is what makes somebody speak
#: to you carefully. Authorable, and then frozen for the rest of the world's
#: life, because nothing produced one.
#:
#: This is wariness, not fright. Acute fear is an emotion and lives in `affect`,
#: where it decays over an afternoon; this is the part that does not.
FEAR_SHARE = 0.8

#: And of a believed kindness, how much becomes STANDING RATHER THAN AFFECTION.
#: `respect` feeds the same stance from the other side -- it is what lets a
#: character be deferred to without being liked. Lower than fear on purpose:
#: one good turn is noted, one bad one is remembered.
RESPECT_SHARE = 0.5

#: How far what they think of you is allowed to move what they decide to do.
#:
#: Deliberately of the same order as the outcome values already in the action
#: catalogue -- evading is worth +0.3 safety, answering +0.2 relationship -- and
#: not larger. Standing should tip a close call and lose to a character's own
#: judgement about their safety. A number that overrode that would produce an
#: NPC who tells a stranger a secret because they were nice once, which is worse
#: than not modelling this at all.
DECISION_PULL = 0.4

#: Which way each dialogue action is pushed by warmth toward the person in front
#: of you. Positive means "warmth makes this more attractive".
#:
#: A push and not a value term, and the difference is not cosmetic: terms within
#: a group are averaged, so contributing a modifier as a term can lower the very
#: thing it was meant to raise. `PolicyEngine.score` has the whole story.
WARMTH_PULL = {
    "answer_truthfully": +1.0,
    "greet": +0.6,
    "evade": -1.0,
    "threaten": -0.8,
}


class StandingEngine:
    """Turns *believing that somebody did something* into how they are treated."""

    module_id = "standing"
    version = "1.0.0"

    def __init__(self, conduct: dict | None = None, enabled: bool = False):
        #: Off by default, switched on by the SDK from `RuntimeConfig.standing`.
        #: The flag lives on the engine because that is where every other
        #: optional layer in this runtime keeps it, and two conventions for the
        #: same thing is how a layer ends up half on.
        self.enabled = bool(enabled)
        self.conduct = dict(DEFAULT_CONDUCT)
        if conduct:
            # A pack may add predicates or retune the shipped ones. Merged rather
            # than replaced, so adding "stole_from" does not silently delete the
            # two that the demo and the tests rely on.
            for predicate, spec in conduct.items():
                merged = dict(self.conduct.get(predicate, {"dimension": "decent",
                                                           "sign": -1.0, "weight": 1.0}))
                merged.update(spec or {})
                self.conduct[predicate] = merged

    # ------------------------------------------------------------- reading --

    def describes_conduct(self, proposition) -> bool:
        return getattr(proposition, "predicate", None) in self.conduct

    def actor_of(self, proposition):
        """Who is said to have done it. `by` is the slot; no `by`, no judgement."""
        slots = getattr(proposition, "slots", None) or {}
        return slots.get("by")

    def victim_of(self, proposition):
        slots = getattr(proposition, "slots", None) or {}
        return slots.get("who")

    # ------------------------------------------------------------- writing --

    def judge(self, observer, proposition, confidence: float):
        """Move `observer`'s view of whoever is named in `by`.

        `confidence` is how far the observer actually believes it, in [0, 1] --
        the belief engine's number, not a fresh one invented here. Returns
        `(deltas, reasons)`; the deltas are applied through the engines that own
        the state, exactly as the promises layer does, so there is still one
        owner per field.

        Takes no world. It does not need one -- everything it decides is in the
        observer and the proposition -- and that is what keeps it an engine in
        the sense the architecture map means: one mechanism, no knowledge that
        there is a world, a player or a text layer anywhere.
        """
        if not self.enabled:
            return [], []
        actor_id = self.actor_of(proposition)
        victim_id = self.victim_of(proposition)
        if not actor_id or actor_id == observer.id:
            # You do not revise your opinion of yourself by hearing about
            # yourself. Every other layer leaves the actor alone too.
            return [], []
        spec = self.conduct.get(proposition.predicate)
        if spec is None:
            return [], []

        # A claim asserted negatively -- "he did NOT hit her" -- is evidence
        # against the conduct, so it must not be read as evidence for it.
        polarity = 1.0 if getattr(proposition, "polarity", "+") == "+" else -1.0
        care = self._care_about(observer, victim_id)
        amount = (BASE_STEP * float(spec["weight"]) * float(spec["sign"])
                  * polarity * max(0.0, min(1.0, confidence)) * care)
        amount = max(-MAX_STEP, min(MAX_STEP, amount))

        # ONLY THE CHANGE IS APPLIED, and this is the whole difference between a
        # judgement and a counter. A believed act is a STANDING position -- "this
        # is what I now think of you" -- so hearing about it again is not a
        # second act, it is the same one restated. Paying out the full amount on
        # every report made repetition into a punishment the belief engine had
        # already, correctly, refused to be persuaded by: twenty reports of one
        # incident moved the belief from 0.54960677 to 0.54960683 and liking from
        # -0.198 to -0.659.
        #
        # Keyed on the proposition, which is the same granularity the belief
        # engine files it under: two reports that are the same claim are one
        # incident, and a pack that means two incidents qualifies them apart.
        ledger = getattr(observer, "standing_applied", None)
        if ledger is None:
            ledger = {}
            observer.standing_applied = ledger
        incident = proposition.core_key()
        step = amount - float(ledger.get(incident, 0.0))
        if abs(step) < 1e-4:
            return [], []
        ledger[incident] = amount

        # Argument order matters and is easy to get backwards: `reputation_delta`
        # takes (subject, audience, ...) -- who it is ABOUT first, whose view
        # second -- while `trust_delta` and `liking_delta` take (owner, subject).
        deltas = [reputation_delta(actor_id, observer.id, spec["dimension"],
                                   step, "conduct_believed", self.module_id),
                  liking_delta(observer.id, actor_id, step, "conduct_believed",
                               self.module_id)]
        if amount < 0:
            # Cruelty costs trust as well as liking, and the two are not the
            # same thing: you can dislike somebody you would still believe.
            deltas.append(trust_delta(observer.id, actor_id, step * 0.6,
                                      "conduct_believed", self.module_id))
            # And it makes them wary of you, which is a third thing again: fear
            # is not dislike, and a character can be afraid of somebody they
            # like. It is what decides whether your next threat lands or gets
            # you laughed at, and how carefully they speak to you.
            deltas.append(relationship_delta(observer.id, actor_id, "fear",
                                             -step * FEAR_SHARE,
                                             "conduct_believed", self.module_id))
        else:
            # Decency earns standing, which is not the same as being liked --
            # it is what lets somebody be deferred to by a person who is not
            # their friend.
            deltas.append(relationship_delta(observer.id, actor_id, "respect",
                                             step * RESPECT_SHARE,
                                             "conduct_believed", self.module_id))
        return deltas, [("standing.judged", round(step, 4), {
            "observer": observer.id, "about": actor_id, "victim": victim_id,
            "predicate": proposition.predicate,
            "dimension": spec["dimension"],
            "confidence": round(float(confidence), 3),
            "cared_about_victim": round(care, 3),
            "position": round(amount, 4),
            "note": ("how far this moved is how far they believe it, which is "
                     "why hearsay counts for less than what you watched; and "
                     "only the CHANGE is applied, so being told again is not "
                     "being wronged again")})]

    # ------------------------------------------------------------ deciding --

    def bias_for(self, agent, action, other_id) -> float:
        """What they think of you, as a reason to answer you or turn you away.

        THIS IS THE HALF THAT MAKES THE OTHER HALF WORTH HAVING. Before this,
        `agent.relationships[player]` and `agent.reputation[player]` moved and
        nothing anywhere read them when deciding what to say -- whether a
        character answered you depended on their agreeableness, their secrets
        and their safety, and not at all on what they thought of you. Standing
        that nobody acts on is a number in a save file.

        `SocialExchangeEngine.value_terms` has fetched exactly this relationship
        since it was written and then dropped it on the floor, which is a fair
        indication of where it was always meant to go.
        """
        if not self.enabled or not other_id or action.target != other_id:
            return 0.0
        direction = WARMTH_PULL.get(action.action_id)
        if direction is None:
            return 0.0
        warmth = self.warmth(agent, other_id)
        if abs(warmth) < 1e-3:
            return 0.0
        return DECISION_PULL * direction * warmth

    def warmth(self, agent, other_id) -> float:
        """How this character feels about `other_id` right now, in [-1, 1].

        Three sources, because they are three different things: liking is
        affection, trust is whether your word is worth anything, and `decent` is
        what they think of your conduct toward *other people*. The third is the
        one this layer adds, and it is the one that lets somebody who has never
        met you dislike you on sight.
        """
        rel = agent.relationships.get(other_id) or {}
        liking = max(-1.0, min(1.0, float(rel.get("liking", 0.0))))
        trust = max(0.0, min(1.0, float(rel.get("trust", 0.3))))
        decent = max(-1.0, min(1.0, float((agent.reputation.get(other_id) or {}).get("decent", 0.0))))
        # Trust is centred on the 0.3 a stranger starts with, so a stranger is
        # neither warm nor cold and only what you do moves them.
        centred_trust = (trust - 0.3) / 0.7
        attraction = max(0.0, min(1.0, float(rel.get("attraction", 0.0))))
        # `decent` carries half. It is the only one of the three that is about
        # your CONDUCT rather than about your dealings with this particular
        # person -- it is what a bystander has, and what somebody who was told
        # about you has, and weighting it below liking made the layer quietest
        # in exactly the case it exists for. Liking and trust still carry the
        # rest, because a friend forgives more than a stranger does.
        # Attraction is added rather than blended in: it warms you toward
        # somebody without pretending to be liking, trust or approval, and it
        # is zero for everybody in every pack that does not author it.
        return max(-1.0, min(1.0,
                             0.30 * liking + 0.20 * centred_trust + 0.50 * decent
                             + 0.25 * attraction))

    def influence(self, agent, other_id, bridge_score: float = 0.0) -> float:
        """How much sway `other_id` has over `agent`, in [0, 1]. READ ONLY.

        Not a new number in the save file: a summary of four that are already
        there, because "how much pull does this person have over me" is a
        question a game asks constantly and had to assemble by hand every time.

        Four sources, and they are four different kinds of hold:

            respect     they are worth listening to
            dependence  you need something from them
            fear        the hold that works whether or not you like them
            reach       how many circles they stand in, from the social network

        Deliberately not liking. Somebody you are fond of and neither respect
        nor need has no particular sway over you, and a summary that said
        otherwise would flatter every friendship in the world.
        """
        rel = agent.relationships.get(other_id) or {}
        respect = max(0.0, min(1.0, float(rel.get("respect", 0.0))))
        dependence = max(0.0, min(1.0, float(rel.get("dependence", 0.0))))
        fear = max(0.0, min(1.0, float(rel.get("fear", 0.0))))
        reach = max(0.0, min(1.0, float(bridge_score)))
        return max(0.0, min(1.0, 0.35 * respect + 0.30 * dependence
                            + 0.25 * fear + 0.10 * reach))

    def _care_about(self, observer, victim_id) -> float:
        """Between STRANGER_FLOOR and 1: whose treatment you take personally."""
        if not victim_id:
            return STRANGER_FLOOR
        rel = (observer.relationships.get(victim_id) or {})
        warmth = max(0.0, float(rel.get("liking", 0.0)))
        known = max(0.0, float(rel.get("familiarity", 0.0)))
        closeness = min(1.0, 0.5 * warmth + 0.5 * known)
        return STRANGER_FLOOR + (1.0 - STRANGER_FLOOR) * closeness
