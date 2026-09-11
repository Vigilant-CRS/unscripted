"""Part B -- utility aggregation and selection (spec v0.5 §3; review P0.10).

Three roles kept distinct: additive value terms, multiplicative personality/identity
weights, and emotion action-tendency bias. Group aggregation is BOUNDED (terms in a
group are averaged, not summed past [-1,1]). Prospect Theory is OFF by default
(feature flag) and, when on, transforms OUTCOMES, not arbitrary terms.
"""
from __future__ import annotations
import math
from .types import clamp_signed
from .determinism import derive_seed, seeded_choice
from .actions import ActionCandidate


def prospect_value(x, ref, alpha=0.88, beta=0.88, lam=2.25):
    z = x - ref
    return z ** alpha if z >= 0 else -lam * ((-z) ** beta)


def prospect_weight(p, gamma=0.61):
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return (p ** gamma) / ((p ** gamma + (1 - p) ** gamma) ** (1 / gamma))


def bounded_aggregate(values):
    """Average so a group's value stays in [-1,1] regardless of term count (review P0.10)."""
    if not values:
        return 0.0
    return clamp_signed(sum(values) / max(1, len(values)))


class PolicyEngine:
    module_id = "policy"
    version = "0.6.0"

    def __init__(self, params=None):
        self.params = {"temperature": 0.3, "use_prospect": False,
                       "w_impulsivity": 0.4, "w_arousal": 0.3}
        if params:
            self.params.update(params)

    def outcome_value(self, outcome):
        if self.params["use_prospect"]:
            v = prospect_value(outcome.delta, outcome.reference_point)
            w = prospect_weight(outcome.probability)
        else:
            v = outcome.delta
            w = outcome.probability
        return clamp_signed(v * w)

    def score(self, agent, candidates, *, weights, term_providers, action_tendencies,
              bias_providers=None):
        """weights: dict group->weight. term_providers: callable(action)->list[(group,value)].
        action_tendencies: dict action_class->bias.
        bias_providers: callable(action)->float, ADDED rather than averaged.

        THE DIFFERENCE BETWEEN A TERM AND A BIAS, which cost an afternoon.

        A term is an opinion about an outcome, and terms in a group are AVERAGED
        so that a group stays in [-1, 1] however many of them there are. That is
        right for what it was built for and wrong for a modifier: a bias meant to
        make evading a little more attractive, contributed as a term worth +0.12
        into a group already holding +0.30, LOWERS the group to +0.21. Somebody
        dressed to look dangerous made a character *less* likely to back away
        from them, and every number moved the wrong way round while every
        individual piece of arithmetic was correct.

        So a bias is added, exactly as the emotional action tendency below always
        has been -- that channel was the shape the newer modifiers needed, and it
        was already here.
        """
        scored = []
        for cand_def in candidates:
            groups = {}
            # 1. outcomes -> a value term in the action's outcome dimensions
            for oc in cand_def.outcomes:
                groups.setdefault(oc.dimension, []).append(self.outcome_value(oc))
            # 2. module-provided value terms
            for grp, val in term_providers(cand_def):
                groups.setdefault(grp, []).append(val)
            contributions = []
            total = 0.0
            for grp, vals in groups.items():
                gv = bounded_aggregate(vals)
                w = weights.get(grp, 1.0)
                contrib = w * gv
                total += contrib
                contributions.append((grp, round(gv, 3), round(w, 3), round(contrib, 3)))
            # 3. emotion action-tendency bias (a push, not a value source)
            emo_bias = clamp_signed(action_tendencies.get(cand_def.action_class, 0.0))
            total += emo_bias
            contributions.append(("emotion_tendency", round(emo_bias, 3), 1.0, round(emo_bias, 3)))
            # 4. and every other push: what they think of you, what you look
            #    like. Added for the reason in the docstring.
            if bias_providers is not None:
                pushed = float(bias_providers(cand_def))
                if pushed:
                    total += pushed
                    contributions.append(("bias", round(pushed, 3), 1.0, round(pushed, 3)))
            cand = ActionCandidate(action=cand_def, utility=total, contributions=contributions)
            scored.append(cand)
        scored.sort(key=lambda c: c.utility, reverse=True)
        return scored

    def select(self, agent, scored, *, event_id, world_time):
        """Choose among scored candidates. Empty is a caller error, said plainly.

        `max()` on an empty sequence raises `ValueError: max() iterable argument
        is empty` from inside this method, which tells whoever supplied an empty
        affordance query nothing at all. A studio bringing its own action
        catalogue will hit this, and the message is the whole difference between
        a five-minute fix and an afternoon.
        """
        if not scored:
            raise ValueError(
                "no action candidates to choose between. The affordance query "
                "for this situation returned nothing -- a character must always "
                "have at least one thing they could do, even if it is to say "
                "nothing. See unscripted/actions.py: default_candidates().")
        p = self.params
        impuls = agent.big_five.get("impulsivity", 1 - agent.big_five.get("conscientiousness", 0.5))
        arousal = agent.affect.mood.a if agent.affect else 0.0
        T = max(0.05, p["temperature"] * (1 + p["w_impulsivity"] * impuls + p["w_arousal"] * max(0, arousal)))
        utils = [c.utility for c in scored]
        mx = max(utils)
        exps = [math.exp((u - mx) / T) for u in utils]
        seed = derive_seed(agent.__dict__.get("_global_seed", "s"), agent.id, event_id, world_time, self.module_id)
        idx = seeded_choice(seed, exps)
        chosen = scored[idx]
        # Inspector clarity (review P0): keep three distinct facts separate so a
        # stochastic pick never reads as a bug -- the HIGHEST-RATED action, the
        # action actually SAMPLED, and the selection PROBABILITY of each candidate.
        total_exp = sum(exps) or 1.0
        selection_probs = [(c.action.action_id, round(e / total_exp, 3))
                           for c, e in zip(scored, exps)]
        top_rated = scored[0]  # scored is sorted by utility descending
        reasons = [("policy.selected", round(chosen.utility, 3),
                    {"sampled_action": chosen.action.action_id,
                     "top_rated_action": top_rated.action.action_id,
                     "top_rated_utility": round(top_rated.utility, 3),
                     "stochastic": chosen.action.action_id != top_rated.action.action_id,
                     "T": round(T, 3),
                     "selection_probs": selection_probs,
                     "contributions": chosen.contributions})]
        return chosen, reasons
