"""Action catalog, outcomes and candidate generation (review P1.6, P0.10).

The utility engine scores candidates; this module produces them. Actions are
drawn from a closed catalog (never invented). Outcomes are explicit (dimension,
delta, probability, reference_point) so the optional Prospect transform applies
to outcomes, not to arbitrary terms.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ActionOutcome:
    dimension: str         # value dimension affected: "safety", "income", "relationship", ...
    delta: float           # raw change, in that dimension's natural scale
    probability: float     # [0,1] chance the outcome occurs
    reference_point: float = 0.0
    source: str = ""


@dataclass
class ActionDefinition:
    action_id: str
    action_class: str      # for emotion action-tendency bias: "flee","attack","evade",...
    target: Optional[str] = None
    outcomes: list = field(default_factory=list)   # list[ActionOutcome]
    preconditions: list = field(default_factory=list)
    is_dialogue: bool = False
    dialogue_act: Optional[str] = None


@dataclass
class ActionCandidate:
    action: ActionDefinition
    # filled by the policy engine:
    utility: float = 0.0
    contributions: list = field(default_factory=list)   # (group, value, weight, contribution)


# Closed reference catalog. Production packs can provide a larger affordance query.
def default_candidates(agent, context):
    """Deterministic candidate set for a guarded-NPC-talking-to-stranger situation.
    A real pack supplies the catalog + affordance query (capability module)."""
    other = context.get("interlocutor")
    cands = [
        ActionDefinition("evade", "evade", other, is_dialogue=True, dialogue_act="evade",
                         outcomes=[ActionOutcome("safety", +0.3, 0.8, source="protect_secret")]),
        ActionDefinition("answer_truthfully", "share", other, is_dialogue=True, dialogue_act="inform",
                         outcomes=[ActionOutcome("relationship", +0.2, 0.6, source="cooperate"),
                                   ActionOutcome("safety", -0.4, 0.7, source="reveal_risk")]),
        ActionDefinition("threaten", "threaten", other, is_dialogue=True, dialogue_act="threaten",
                         outcomes=[ActionOutcome("safety", +0.2, 0.4, source="deter"),
                                   ActionOutcome("relationship", -0.5, 0.8, source="hostility")]),
        ActionDefinition("greet", "affiliate", other, is_dialogue=True, dialogue_act="greet",
                         outcomes=[ActionOutcome("relationship", +0.1, 0.9, source="rapport")]),
    ]
    if context.get("player_owes"):
        cands.append(
            ActionDefinition("ask_for_payment", "assert", other, is_dialogue=True, dialogue_act="request",
                             outcomes=[ActionOutcome("income", +0.4, 0.5, source="collect")])
        )
    if context.get("allow_speculative_work"):
        cands.append(
            ActionDefinition("speculative_side_job", "gamble", other, is_dialogue=True,
                             dialogue_act="request",
                             outcomes=[
                                 ActionOutcome("income", +1.2, 0.55, source="high_variance_payout"),
                                 ActionOutcome("safety", -0.10, 0.30, source="street_risk"),
                             ])
        )
    return cands
