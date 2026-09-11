"""Social theory modules (spec v0.5 §5.8-§5.15).

These are mostly *feature providers*: they read state and emit (a) value terms for
the policy engine (Part B) and (b) proposed deltas for cross-cutting owners (Part C).
They do not own mutable relationship/reputation/identity state.
"""
from __future__ import annotations
from .types import clamp01, clamp_signed
from .statekey import trust_delta, liking_delta, reputation_delta, identity_threat


class ValueEngine:
    """Schwartz values: context-activated, gated by salient identity (spec §5.2)."""
    module_id = "value"

    def active_values(self, agent, salient_identity, context, identity_values=None):
        """Which Schwartz values are live right now, given the salient identity.

        ``identity_values`` maps an identity to the values it amplifies. It is
        world content -- what "sister" or "watchman" implies is a fact about a
        setting -- and is authored in ``world.json: identity_values``. It used to
        be a literal dict here naming the reference pack's four identities, so
        every other identity in every other pack amplified nothing.
        """
        out = {}
        amplified = set((identity_values or {}).get(salient_identity, ()))
        for v, base in agent.schwartz.items():
            factor = 1.0 if v in amplified else 0.5
            out[v] = clamp01(base * factor)
        return out


class SocialExchangeEngine:
    """Reciprocity, fairness, dependence -> trust/liking proposals + exchange value terms."""
    module_id = "social_exchange"

    def on_commitment_resolved(self, owner, other, fulfilled: bool):
        if fulfilled:
            return [trust_delta(owner, other, +0.8, "commitment_fulfilled", self.module_id),
                    liking_delta(owner, other, +0.4, "commitment_fulfilled", self.module_id)]
        return [trust_delta(owner, other, -0.7, "commitment_broken", self.module_id),
                liking_delta(owner, other, -0.5, "commitment_broken", self.module_id),
                reputation_delta(other, owner, "reliable", -0.4, "broke_promise", self.module_id)]

    def dependence(self, current_value, best_alternative, eps=1e-6):
        # bounded ratio (review P1.5): never divides by zero / goes negative
        return current_value / (current_value + best_alternative + eps)

    def value_terms(self, agent, action, context):
        terms = []
        other = action.target
        rel = agent.relationships.get(other, {})
        # repay what you owe; collect what's owed
        if action.action_id == "ask_for_payment" and context.get("player_owes"):
            terms.append(("exchange", 0.6))
        return terms


class SocialIdentityEngine:
    """In/out-group, identity threat -> group-based emotion + identity threat proposals (spec §5.9)."""
    module_id = "social_identity"

    def on_event(self, agent, event, context, identity=None):
        proposals, appraisal_boost = [], {}
        # if the event threatens the in-group / a protected family member, raise identity threat
        #
        # `identity` is passed in by the runtime, which is the only thing that
        # can know it: whether an event threatens YOUR belonging depends on who
        # you are, so it cannot be a property of the event. The payload form is
        # kept for a pack that wants to state it outright.
        iid = identity or event.payload.get("threatens_identity")
        if iid:
            proposals.append(identity_threat(agent.id, iid, +0.6, "in_group_threat", self.module_id))
            appraisal_boost = {"desirability": -0.6, "agency": "other", "praiseworthiness": -0.3,
                               "target": event.actor}
        return proposals, appraisal_boost


class NormEngine:
    """Compliance pressure from internalization + sanction*observability*legitimacy (spec §5.11)."""
    module_id = "norm"

    def value_terms(self, agent, action, context):
        terms = []
        # threatening in public (observable) carries norm cost; cooperating carries small norm credit
        observability = context.get("surveillance_level", 0.0)
        if action.action_class == "threaten":
            sanction, legitimacy = 0.6, context.get("authority_legitimacy", 0.5)
            terms.append(("norm", -(sanction * observability * legitimacy)))
        if action.action_class in ("share", "affiliate"):
            terms.append(("norm", +0.1))
        return terms


class SocialNetworkEngine:
    """Tie strength -> credibility weighting; bridge score -> diffusion reach (spec §5.12)."""
    module_id = "social_network"

    def tie_strength(self, agent, other):
        rel = agent.relationships.get(other, {})
        return clamp01(0.5 * rel.get("familiarity", 0.0) + 0.5 * rel.get("liking", 0.0) + 0.0)

    def bridge_score(self, agent):
        # high for service roles (bartender, driver, trader) -- a pack would compute from the graph
        roles = [r.get("role") for r in agent.roles]
        return 0.8 if any(r in ("role:bartender", "role:fixer", "role:trader") for r in roles) else 0.3


class TheoryOfMindEngine:
    """Depth-1 models of others' beliefs/goals, with uncertainty + decay (spec §5.13)."""
    module_id = "tom"

    #: What a character assumes about somebody they have no reading on. The
    #: midpoint on purpose: no opinion, so the threat term below comes out at
    #: exactly zero rather than guessing in either direction.
    UNKNOWN_FEAR = 0.5

    def believed_fear_of_me(self, agent, other) -> float:
        """How much `agent` believes `other` is afraid of THEM.

        NOT `agent.relationships[other]["fear"]`, which is the other
        relationship -- how much the agent fears the other -- and reading it here
        inverted every threat assessment in the runtime. A character terrified of
        somebody concluded their own threats would land (+0.32); one who had
        spent the week frightening them concluded they would backfire (-0.40).

        There is no honest way to read the other's actual fear from here: that is
        omniscience wearing a theory-of-mind hat, and this engine exists
        precisely because a character does not have it. So this is a MODEL, and
        it stays at `UNKNOWN_FEAR` until something the agent has grounds to
        reason from writes it -- which is what they have themselves been seen to
        do, recorded by `note_own_act`.
        """
        entry = (getattr(agent, "tom_models", None) or {}).get((other, "fear_of_me"))
        if not entry:
            return self.UNKNOWN_FEAR
        return max(0.0, min(1.0, float(entry.get("value", self.UNKNOWN_FEAR))))

    #: How far one act of a given kind moves what the actor thinks it did to the
    #: other's wariness of them, at full severity. Small: this is an inference
    #: from one's own behaviour, not a reading of somebody else's mind.
    OWN_ACT_WEIGHT = {"attack": +0.25, "threat": +0.20, "crime": +0.10,
                      "gift": -0.15}

    def note_own_act(self, agent, other: str, kind: str, severity: float) -> list:
        """What the person who DID it may reasonably conclude from having done it.

        The one thing about another person's state an actor has grounds to
        estimate: they know what they themselves did, and roughly what being on
        the receiving end of it does. Confidence rises with each occasion, so a
        model built from several acts is weighted like one.
        """
        step = self.OWN_ACT_WEIGHT.get(kind)
        if step is None or not other or other == agent.id:
            return []
        models = agent.tom_models
        entry = models.setdefault((other, "fear_of_me"),
                                  {"value": self.UNKNOWN_FEAR, "confidence": 0.0})
        before = entry["value"]
        entry["value"] = max(0.0, min(1.0, before + step * max(0.0, min(1.0, severity))))
        entry["confidence"] = min(1.0, float(entry.get("confidence", 0.0)) + 0.3)
        if abs(entry["value"] - before) < 1e-9:
            return []
        return [("tom.updated", round(entry["value"] - before, 4), {
            "agent": agent.id, "about": other, "model": "fear_of_me",
            "was": round(before, 4), "now": round(entry["value"], 4),
            "because": kind,
            "note": "what they take from having done it, not what the other feels"})]

    def expected_reaction(self, agent, other, action_class, context):
        """Crude depth-1 expectation: will a threat be believed / will they retaliate?"""
        if action_class == "threaten":
            fear = self.believed_fear_of_me(agent, other)
            # works if they fear us; backfires (retaliation) if they don't
            return ("tom", 0.4 * fear - 0.4 * (1 - fear))
        return ("tom", 0.0)

    def models_unaware(self, agent, other, proposition_key):
        m = getattr(agent, "tom_models", {}).get((other, proposition_key))
        return (m is None) or (m.get("confidence", 0.0) < 0.5)


class ImpressionManagementEngine:
    """Front/back stage face management (Goffman, spec §5.14)."""
    module_id = "impression"

    def front_stage(self, context):
        audience = context.get("audience_size", 0)
        surveillance = context.get("surveillance_level", 0.0)
        return audience > 0 or surveillance > 0.3

    def value_terms(self, agent, action, context):
        terms = []
        if self.front_stage(context):
            # actions that threaten face before an audience are penalized; face-repair rewarded
            if action.action_class in ("threaten",) and context.get("public_role_formal"):
                terms.append(("face", -0.4))
            if action.action_class in ("affiliate", "repair_face"):
                terms.append(("face", +0.2))
        return terms

    def weight(self, context):
        return 1.0 + (0.8 if self.front_stage(context) else -0.6)


class InterpersonalEngine:
    """Situational circumplex stance (agency, communion) -> realization style (spec §5.15).

    NOT CONSTRUCTED BY THE RUNTIME, deliberately, and this note is here so the
    next person does not have to work out why. It was instantiated on every
    runtime and never called: nothing consumed the stance it computes, so it cost
    an object per runtime and implied a feature that did not exist.

    It is kept rather than deleted because the mapping is right and the work is
    real -- agency and communion from liking, fear, respect and the emotions felt
    toward the other. What is missing is the other half: `SociolinguisticEngine`
    would have to take a stance alongside its style vector, and the realizer
    would have to phrase from it. Until somebody does that, this is a component
    with no socket, and saying so is better than a constructor call that makes it
    look wired.

    Its two dead siblings are now alive. `ReputationEngine` needed a producer of
    reputation deltas, which arrived with `unscripted/promises.py`; `SocialIdentityEngine`
    needed somebody to decide per observer which belonging an event threatens,
    which is now done in the runtime's perception loop.
    """
    module_id = "interpersonal"

    def stance(self, agent, other, affect_engine):
        rel = agent.relationships.get(other, {})
        communion = clamp_signed(rel.get("liking", 0.0) - 0.5 * rel.get("fear", 0.0))
        agency = clamp_signed(0.5 * rel.get("respect", 0.0) + agent.affect.mood.d)
        # anger raises agency, lowers communion; fear lowers agency
        toward = affect_engine.emotions_toward(agent.affect, other) if other else {}
        agency += 0.5 * toward.get("anger", 0.0) - 0.5 * toward.get("fear", 0.0)
        communion -= 0.5 * (toward.get("anger", 0.0) + toward.get("disliking", 0.0))
        return clamp_signed(agency), clamp_signed(communion)
