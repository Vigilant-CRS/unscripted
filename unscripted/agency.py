"""Agency & Mobilization layer.

Tabletop-inspired social-power primitives the deliberative layer lacked:
  - resources/budget -> affordability + Prospect risk reference point;
  - ReactiveRule: condition -> priority action that preempts deliberation
    (e.g. "when injured AND threatened, summon the sons");
  - ally-response model: calling in allies (gang / police / kin) is an action whose
    outcome depends on each ally's loyalty/kinship/favor/authority minus cost and
    arrival latency, and it COSTS social capital;
  - leverage: asymmetric power (dependence + secrets + resources + status gap);
  - graded resolution: full / partial-at-a-cost / failure-with-consequence (PbtA-style).

Social standing is woven through: status gates mobilization REACH (institutional
allies need status/membership), raises AUTHORITY over others, and amplifies LEVERAGE.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
from .types import clamp01, sigmoid
from .determinism import derive_seed, seeded_uniform
from .actions import ActionDefinition, ActionOutcome


# ---------- authority & leverage (social standing matters here) ----------

def _shared_group(a, b) -> bool:
    """True if a and b belong to the same concrete group (compare group, not just identity label)."""
    ga = {i.get("group") for i in a.identities if i.get("group")}
    gb = {i.get("group") for i in b.identities if i.get("group")}
    return bool(ga & gb)


def authority(caller, ally) -> float:
    """caller's authority over ally: org chain + status gap."""
    status_gap = clamp01((caller.social_status - ally.social_status) + 0.5)
    # org rank: a simple proxy -- same group and caller has a leadership role
    rank = 0.4 if (_shared_group(caller, ally) and any(r.get("role") in ("role:boss", "role:officer", "role:fixer")
                                                       for r in caller.roles)) else 0.0
    return clamp01(0.6 * status_gap + rank)


def leverage(a, b, world=None) -> float:
    """a's leverage over b: dependence + secrets-held + resource control + status gap."""
    rel_b = b.relationships.get(a.id, {})
    dep = rel_b.get("dependence", 0.0)
    # "I know something about you": a structured secret declares who it concerns,
    # instead of the old substring search for the target's id inside the secret text.
    holds_secret = 1.0 if any(b.id in secret.about for secret in a.secrets) else 0.0
    res_control = clamp01(a.resources - b.resources + 0.3)
    status_gap = clamp01(a.social_status - b.social_status)
    return clamp01(0.4 * dep + 0.3 * holds_secret + 0.2 * res_control + 0.1 * status_gap)


# ---------- ally response (mobilization) ----------

@dataclass
class AllyResponse:
    ally_id: str
    probability: float
    latency: int            # world-minutes until arrival
    will_come: bool


def potential_allies(caller, world):
    """Allies the caller could mobilize. Social standing gates institutional reach:
    only sufficiently high-status / affiliated agents can call institutions."""
    allies = []
    for other in world.agents.values():
        if other.id == caller.id:
            continue
        rel = other.relationships.get(caller.id, {})
        kin = rel.get("kinship", 0.0)
        loyal = rel.get("loyalty", rel.get("liking", 0.0))
        same_group = _shared_group(caller, other)
        institutional = any(r.get("role") in ("role:officer",) for r in other.roles)
        # reach: kin/loyal/group always reachable; institutions only if caller has standing/affiliation
        reachable = (kin > 0 or loyal > 0.3 or same_group
                     or (institutional and caller.social_status >= 0.6))
        if reachable:
            allies.append(other)
    return allies


def ally_response(caller, ally, world, *, urgency: float, event_id: int):
    rel = ally.relationships.get(caller.id, {})
    kin = rel.get("kinship", 0.0)
    loyal = rel.get("loyalty", rel.get("liking", 0.0))
    favor = rel.get("favor_debt", rel.get("owes_favor", 0.0))
    auth = authority(caller, ally)
    # cost/risk to the ally of responding (lower if they fear/respect the caller's enemies little)
    cost = 0.5 * (1 - ally.big_five.get("agreeableness", 0.5))
    x = 2.0 * loyal + 2.5 * kin * (0.5 + 0.5 * urgency) + 1.5 * favor + 1.2 * auth - 1.0 * cost
    prob = sigmoid(x - 1.0)
    seed = derive_seed(world.global_seed, ally.id, event_id, world.world_time, "ally_response", caller.id)
    will = seeded_uniform(seed) < prob
    # latency: co-located fast, adjacent medium, else far
    if ally.location == caller.location:
        latency = 2
    else:
        latency = 15
    return AllyResponse(ally.id, round(prob, 3), latency, will)


def mobilization_candidate(caller, world, *, urgency: float, event_id: int):
    """Build a 'mobilize_allies' action whose expected payoff is the summed ally response,
    scaled by social standing (reach). Returns (ActionDefinition, response_list) or None."""
    allies = potential_allies(caller, world)
    if not allies:
        return None
    responses = [ally_response(caller, a, world, urgency=urgency, event_id=event_id) for a in allies]
    expected = sum(r.probability for r in responses)
    # social standing raises effective backup (institutional muscle is heavier)
    reach = 0.7 + 0.6 * caller.social_status
    safety_gain = clamp01(0.2 * expected * reach)
    act = ActionDefinition("mobilize_allies", "seek_safety", target=None, is_dialogue=False,
                           outcomes=[ActionOutcome("safety", +safety_gain, min(1.0, 0.4 + 0.4 * expected),
                                                   source="backup")])
    return act, responses


# ---------- reactive rules (trigger -> priority action, preempts deliberation) ----------

@dataclass
class ReactiveRule:
    rule_id: str
    condition: Callable          # (agent, ctx) -> bool
    action_id: str               # action class to inject as a high-priority candidate
    priority: float = 1.0        # added as a utility floor; high priority -> near-deterministic
    reason: str = ""


def default_reactive_rules():
    return [
        ReactiveRule(
            "summon_kin_when_hurt",
            condition=lambda ag, ctx: ctx.get("injured", False) and ctx.get("threatened", False),
            action_id="mobilize_allies", priority=2.0,
            reason="injured_and_threatened -> call for help"),
        ReactiveRule(
            "flee_when_outmatched",
            condition=lambda ag, ctx: ctx.get("threatened", False) and ctx.get("threat_severity", 0) > 0.7
            and not ctx.get("has_backup", False),
            action_id="flee", priority=1.5, reason="overwhelming_threat -> flee"),
    ]


def fire_reactive_rules(agent, ctx, rules, reasons=None):
    """Which rules apply here. A rule that throws is reported, not swallowed.

    This used to catch every exception and `pass`. A rule whose condition had a
    bug simply never fired -- no trace, no warning, and a designer looking at a
    character who does not react to being attacked has nothing to go on. Rules
    come from packs and from studios, so they WILL have bugs; the catch stays,
    because one broken rule must not stop the others from being evaluated. What
    changes is that it says so.
    """
    fired = []
    for r in rules:
        try:
            if r.condition(agent, ctx):
                fired.append(r)
        except Exception as exc:
            if reasons is not None:
                reasons.append(("agency.rule_failed", 0.0, {
                    "rule": getattr(r, "rule_id", getattr(r, "name", repr(r))),
                    "agent": agent.id, "error": f"{type(exc).__name__}: {exc}",
                    "note": "the rule was skipped; the others still ran"}))
    return fired


# ---------- graded resolution (PbtA-style) ----------

def resolve(success_prob: float, seed: bytes):
    """full / partial (success at a cost) / consequence (failure with a twist) / miss."""
    r = seeded_uniform(seed)
    p = clamp01(success_prob)
    if r < p * 0.6:
        return "full"
    if r < p:
        return "partial"          # success, but at a cost
    if r < p + (1 - p) * 0.4:
        return "consequence"      # failure with a complication
    return "miss"


# ---------- needs -> Prospect aspiration / risk reference point ----------

def risk_reference_point(agent) -> float:
    """Aspiration level the agent evaluates outcomes against (Prospect Theory framing).

    Outcomes that fall short of aspiration read as losses -> risk-seeking
    (desperation); outcomes at or above it read as gains -> risk-averse (protect
    gains). The reference is the agent's strongest UNMET NEED, not liquid wealth.

    Review P0/§7.1 fix: the previous version set the reference to ``agent.resources``
    and the value function then computed ``v(delta - resources)`` -- mixing an
    outcome *flow* (delta) with a wealth *stock*, which made any gain look like a
    loss for a wealthy agent. Need pressure is the correct, dimensionally consistent
    aspiration: a desperate agent reaches higher and so gambles, a satisfied agent
    (no unmet need -> reference 0) treats prospective gains as gains.
    """
    needs = getattr(agent, "needs", None) or {}
    if not needs:
        return 0.0
    return clamp01(max(float(v) for v in needs.values()))
