// `usc/agency.py`. Social-power primitives the deliberative layer lacked.
//
// Resources and a budget; reactive rules that preempt deliberation ("when
// injured AND threatened, summon the sons"); an ally-response model where
// calling in backup is an ACTION whose outcome depends on each ally's loyalty,
// kinship, favour and authority minus cost and arrival latency, and which costs
// social capital; leverage as asymmetric power; and graded resolution --
// full / partial-at-a-cost / failure-with-consequence.
//
// Social standing is woven through: status gates mobilisation REACH
// (institutional allies need standing), raises AUTHORITY over others, and
// amplifies LEVERAGE.
#pragma once

#include <algorithm>
#include <functional>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "usc/actions.hpp"
#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/determinism.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/pyround.hpp"
#include "usc/pysum.hpp"
#include "usc/types.hpp"
#include "usc/world.hpp"

namespace usc {

/// True when the two belong to the same CONCRETE group -- comparing the group,
/// not just the identity label, because two people can both be "workers" in
/// different plants and that is not a shared circle.
inline bool shared_group(const Agent& a, const Agent& b) {
    auto groups = [](const Agent& who) {
        std::set<std::string> out;
        for (const Json& identity : who.identities) {
            const Json* group = identity.find("group");
            // `if i.get("group")` -- truthiness, so an empty group is no group.
            if (group && !group->is_null() && !group->py_str().empty())
                out.insert(group->py_str());
        }
        return out;
    };
    std::set<std::string> mine = groups(a), theirs = groups(b);
    for (const std::string& one : mine) if (theirs.count(one)) return true;
    return false;
}

/// The caller's authority over an ally: the organisation chart plus a status gap.
inline double authority(const Agent& caller, const Agent& ally) {
    double status_gap = clamp01((caller.social_status - ally.social_status) + 0.5);
    bool leads = false;
    if (shared_group(caller, ally))
        for (const Json& role : caller.roles) {
            const Json* name = role.find("role");
            if (!name) continue;
            std::string which = name->py_str();
            if (which == "role:boss" || which == "role:officer" || which == "role:fixer") {
                leads = true;
                break;
            }
        }
    return clamp01(0.6 * status_gap + (leads ? 0.4 : 0.0));
}

/// `a`'s leverage over `b`: dependence, secrets held, resource control, status.
inline double leverage(const Agent& a, const Agent& b) {
    const OrderedMap<double>* rel = b.relationships.find(a.id);
    double dependence = rel ? rel->get("dependence", 0.0) : 0.0;
    // "I know something about you": a structured secret DECLARES who it
    // concerns, instead of the substring search for the target's id inside the
    // secret's text that this used to do.
    double holds_secret = 0.0;
    for (const Json& row : a.secrets) {
        Secret secret = Secret::from_json(row);
        if (std::find(secret.about.begin(), secret.about.end(), b.id) != secret.about.end()) {
            holds_secret = 1.0;
            break;
        }
    }
    double resource_control = clamp01(a.resources - b.resources + 0.3);
    double status_gap = clamp01(a.social_status - b.social_status);
    return clamp01(0.4 * dependence + 0.3 * holds_secret
                   + 0.2 * resource_control + 0.1 * status_gap);
}

struct AllyResponse {
    std::string ally_id;
    double probability = 0.0;
    long long latency = 0;      // world-minutes until arrival
    bool will_come = false;
};

/// Allies the caller could mobilise.
///
/// Standing gates institutional reach: kin, the loyal and one's own group are
/// always reachable, and an officer only if the caller has standing to call one.
inline std::vector<const Agent*> potential_allies(const Agent& caller, const World& world) {
    std::vector<const Agent*> allies;
    for (const auto& entry : world.agents) {
        const Agent& other = entry.second;
        if (other.id == caller.id) continue;
        const OrderedMap<double>* rel = other.relationships.find(caller.id);
        double kin = rel ? rel->get("kinship", 0.0) : 0.0;
        double loyal = rel ? rel->get("loyalty", rel->get("liking", 0.0)) : 0.0;
        bool same_group = shared_group(caller, other);
        bool institutional = false;
        for (const Json& role : other.roles) {
            const Json* name = role.find("role");
            if (name && name->py_str() == "role:officer") { institutional = true; break; }
        }
        bool reachable = kin > 0 || loyal > 0.3 || same_group
                      || (institutional && caller.social_status >= 0.6);
        if (reachable) allies.push_back(&other);
    }
    return allies;
}

inline AllyResponse ally_response(const Agent& caller, const Agent& ally, const World& world,
                                  double urgency, long long event_id) {
    const OrderedMap<double>* rel = ally.relationships.find(caller.id);
    double kin = rel ? rel->get("kinship", 0.0) : 0.0;
    double loyal = rel ? rel->get("loyalty", rel->get("liking", 0.0)) : 0.0;
    double favor = rel ? rel->get("favor_debt", rel->get("owes_favor", 0.0)) : 0.0;
    double auth = authority(caller, ally);
    // What it costs the ally to answer. A disagreeable person needs more reason.
    double cost = 0.5 * (1 - ally.big_five.get("agreeableness", 0.5));
    double x = 2.0 * loyal + 2.5 * kin * (0.5 + 0.5 * urgency)
             + 1.5 * favor + 1.2 * auth - 1.0 * cost;
    double probability = sigmoid(x - 1.0);
    std::vector<std::uint8_t> seed = derive_seed(world.global_seed, ally.id, event_id,
                                                 world.world_time, "ally_response", caller.id);
    bool will = seeded_uniform(seed) < probability;
    // Co-located is fast; anywhere else is not. Deliberately coarse -- this is a
    // model of "are they here", not of pathfinding.
    long long latency = (ally.location().py_str() == caller.location().py_str()) ? 2 : 15;
    return {ally.id, py_round(probability, 3), latency, will};
}

struct Mobilization {
    ActionDefinition action;
    std::vector<AllyResponse> responses;
};

/// A `mobilize_allies` action whose expected payoff is the summed ally response,
/// scaled by standing -- institutional muscle is heavier.
inline std::optional<Mobilization> mobilization_candidate(
        const Agent& caller, const World& world, double urgency, long long event_id) {
    std::vector<const Agent*> allies = potential_allies(caller, world);
    if (allies.empty()) return std::nullopt;

    std::vector<AllyResponse> responses;
    for (const Agent* ally : allies)
        responses.push_back(ally_response(caller, *ally, world, urgency, event_id));

    // `sum(r.probability for r in responses)`, and `sum` compensates. NOT
    // distinguishable here from a naive loop, and measured rather than assumed:
    // fifteen probabilities all in [0,1] are of similar magnitude, which is the
    // case where Neumaier and a plain addition give the same answer. It is
    // written this way because it is what Python does, and because the guarantee
    // is demonstrated where it does bite -- the identity softmax in
    // `relationship.hpp`, where a naive loop gives 0.99999999999999989 for a
    // distribution Python normalises by exactly 1.0.
    PySum expected;
    for (const AllyResponse& one : responses) expected.add(one.probability);
    double total = expected.value();

    double reach = 0.7 + 0.6 * caller.social_status;
    double safety_gain = clamp01(0.2 * total * reach);

    ActionDefinition action;
    action.action_id = "mobilize_allies";
    action.action_class = "seek_safety";
    action.is_dialogue = false;
    action.outcomes = {{"safety", safety_gain, std::min(1.0, 0.4 + 0.4 * total), 0.0, "backup"}};
    return Mobilization{action, responses};
}

// ---------- reactive rules: trigger -> priority action, preempting deliberation

struct ReactiveRule {
    std::string rule_id;
    /// `(agent, context) -> bool`. Rules come from packs and from studios, so
    /// they will throw.
    std::function<bool(const Agent&, const Json&)> condition;
    std::string action_id;
    /// Added as a utility floor. High priority means near-deterministic.
    double priority = 1.0;
    std::string reason;
};

inline std::vector<ReactiveRule> default_reactive_rules() {
    return {
        {"summon_kin_when_hurt",
         [](const Agent&, const Json& ctx) {
             return ctx.get("injured").as_bool() && ctx.get("threatened").as_bool();
         },
         "mobilize_allies", 2.0, "injured_and_threatened -> call for help"},
        {"flee_when_outmatched",
         [](const Agent&, const Json& ctx) {
             const Json* severity = ctx.find("threat_severity");
             return ctx.get("threatened").as_bool()
                 && (severity ? severity->as_double() : 0.0) > 0.7
                 && !ctx.get("has_backup").as_bool();
         },
         "flee", 1.5, "overwhelming_threat -> flee"},
    };
}

using AgencyReason = Reason;

/// Which rules apply here. A rule that throws is REPORTED, not swallowed.
///
/// This used to catch every exception and pass. A rule whose condition had a bug
/// simply never fired -- no trace, no warning, and a designer looking at a
/// character who does not react to being attacked had nothing to go on. The
/// catch stays, because one broken rule must not stop the others being
/// evaluated. What changed is that it says so.
inline std::vector<ReactiveRule> fire_reactive_rules(
        const Agent& agent, const Json& context, const std::vector<ReactiveRule>& rules,
        std::vector<AgencyReason>* reasons = nullptr) {
    std::vector<ReactiveRule> fired;
    for (const ReactiveRule& rule : rules) {
        try {
            if (rule.condition && rule.condition(agent, context)) fired.push_back(rule);
        } catch (const std::exception& error) {
            if (!reasons) continue;
            Json detail = Json::object();
            detail["rule"] = rule.rule_id;
            detail["agent"] = agent.id;
            detail["error"] = std::string(error.what());
            detail["note"] = std::string("the rule was skipped; the others still ran");
            reasons->push_back({"agency.rule_failed", 0.0, detail});
        }
    }
    return fired;
}

/// full / partial (success at a cost) / consequence (failure with a twist) / miss.
inline std::string resolve(double success_prob, const std::vector<std::uint8_t>& seed) {
    double draw = seeded_uniform(seed);
    double p = clamp01(success_prob);
    if (draw < p * 0.6) return "full";
    if (draw < p) return "partial";
    if (draw < p + (1 - p) * 0.4) return "consequence";
    return "miss";
}

/// The aspiration level outcomes are evaluated against.
///
/// Outcomes short of aspiration read as LOSSES, which makes a character
/// risk-seeking -- desperation. At or above it they read as gains, which makes
/// them risk-averse. The reference is the strongest UNMET NEED, not liquid
/// wealth: the previous version used `resources`, and the value function then
/// computed v(delta - resources), mixing an outcome FLOW with a wealth STOCK so
/// that any gain looked like a loss to a wealthy character.
inline double risk_reference_point(const Agent& agent) {
    if (agent.needs.empty()) return 0.0;
    double highest = 0.0;
    bool first = true;
    for (const auto& entry : agent.needs) {
        if (first || entry.second > highest) { highest = entry.second; first = false; }
    }
    return clamp01(highest);
}

}  // namespace usc
