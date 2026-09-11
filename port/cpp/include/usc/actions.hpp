// `usc/actions.py`. The action catalogue, outcomes, and candidate generation.
//
// The policy engine scores candidates; this produces them. Actions come from a
// closed catalogue and are never invented, and outcomes are explicit --
// dimension, delta, probability, reference point -- so the optional Prospect
// transform applies to outcomes rather than to arbitrary terms.
#pragma once

#include <string>
#include <vector>

#include "usc/json.hpp"

namespace usc {

struct ActionOutcome {
    std::string dimension;        // "safety", "income", "relationship", ...
    double delta = 0.0;           // raw change, in that dimension's natural scale
    double probability = 0.0;     // [0,1]
    double reference_point = 0.0;
    std::string source;
};

struct ActionDefinition {
    std::string action_id;
    /// For the emotion action-tendency bias: "flee", "attack", "evade", ...
    std::string action_class;
    Json target;
    std::vector<ActionOutcome> outcomes;
    std::vector<std::string> preconditions;
    bool is_dialogue = false;
    Json dialogue_act;
};

/// What the policy engine returns: the action, its utility, and where the
/// utility came from. The breakdown is not decoration -- a stochastic pick that
/// cannot be explained reads as a bug to whoever is watching it.
struct ActionCandidate {
    ActionDefinition action;
    double utility = 0.0;
    /// (group, group value, weight, contribution)
    std::vector<std::tuple<std::string, double, double, double>> contributions;
};

/// The closed reference catalogue: a guarded NPC talking to a stranger. A real
/// pack supplies its own affordance query, and the shipped set exists so a
/// character always has something they could do -- see the error message in
/// `PolicyEngine::select`.
inline std::vector<ActionDefinition> default_candidates(const Json& context) {
    Json other = context.get("interlocutor");
    std::vector<ActionDefinition> candidates;

    ActionDefinition evade;
    evade.action_id = "evade"; evade.action_class = "evade"; evade.target = other;
    evade.is_dialogue = true; evade.dialogue_act = Json(std::string("evade"));
    evade.outcomes = {{"safety", 0.3, 0.8, 0.0, "protect_secret"}};
    candidates.push_back(evade);

    ActionDefinition truthful;
    truthful.action_id = "answer_truthfully"; truthful.action_class = "share";
    truthful.target = other; truthful.is_dialogue = true;
    truthful.dialogue_act = Json(std::string("inform"));
    truthful.outcomes = {{"relationship", 0.2, 0.6, 0.0, "cooperate"},
                         {"safety", -0.4, 0.7, 0.0, "reveal_risk"}};
    candidates.push_back(truthful);

    ActionDefinition threaten;
    threaten.action_id = "threaten"; threaten.action_class = "threaten";
    threaten.target = other; threaten.is_dialogue = true;
    threaten.dialogue_act = Json(std::string("threaten"));
    threaten.outcomes = {{"safety", 0.2, 0.4, 0.0, "deter"},
                         {"relationship", -0.5, 0.8, 0.0, "hostility"}};
    candidates.push_back(threaten);

    ActionDefinition greet;
    greet.action_id = "greet"; greet.action_class = "affiliate"; greet.target = other;
    greet.is_dialogue = true; greet.dialogue_act = Json(std::string("greet"));
    greet.outcomes = {{"relationship", 0.1, 0.9, 0.0, "rapport"}};
    candidates.push_back(greet);

    if (context.get("player_owes").as_bool()) {
        ActionDefinition ask;
        ask.action_id = "ask_for_payment"; ask.action_class = "assert"; ask.target = other;
        ask.is_dialogue = true; ask.dialogue_act = Json(std::string("request"));
        ask.outcomes = {{"income", 0.4, 0.5, 0.0, "collect"}};
        candidates.push_back(ask);
    }
    if (context.get("allow_speculative_work").as_bool()) {
        ActionDefinition gamble;
        gamble.action_id = "speculative_side_job"; gamble.action_class = "gamble";
        gamble.target = other; gamble.is_dialogue = true;
        gamble.dialogue_act = Json(std::string("request"));
        gamble.outcomes = {{"income", 1.2, 0.55, 0.0, "high_variance_payout"},
                           {"safety", -0.10, 0.30, 0.0, "street_risk"}};
        candidates.push_back(gamble);
    }
    return candidates;
}

}  // namespace usc
