// `usc/social.py`. Feature providers, not state owners.
//
// These read state and emit two things: value terms for the policy engine, and
// proposed deltas for the cross-cutting owners in `relationship.hpp`. None of
// them owns mutable relationship, reputation or identity state, which is what
// lets `standing` produce fear and `relationship` still be the only thing that
// writes it.
//
// `InterpersonalEngine` is NOT constructed by the runtime, and that is
// deliberate rather than an oversight -- see its own note. It is ported anyway,
// because a port that silently drops a module makes the two implementations
// differ in surface as well as behaviour, and because the reason it is unwired
// is worth carrying across.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/affect.hpp"
#include "usc/actions.hpp"
#include "usc/agent.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/pyround.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/statekey.hpp"
#include "usc/types.hpp"

namespace usc {

/// Schwartz values: context-activated, gated by the salient identity.
class ValueEngine {
public:
    static constexpr const char* MODULE_ID = "value";

    /// Which values are live right now.
    ///
    /// `identity_values` maps an identity to the values it amplifies. It is
    /// WORLD CONTENT -- what "sister" or "watchman" implies is a fact about a
    /// setting -- and used to be a literal dict naming the reference pack's four
    /// identities, so every other identity in every other pack amplified nothing.
    OrderedMap<double> active_values(const Agent& agent,
                                     const std::string& salient_identity,
                                     const Json& identity_values = Json()) const {
        std::vector<std::string> amplified;
        const Json* named = identity_values.find(salient_identity);
        if (named) for (const Json& one : named->items()) amplified.push_back(one.py_str());

        OrderedMap<double> out;
        for (const auto& entry : agent.schwartz) {
            bool boosted = std::find(amplified.begin(), amplified.end(), entry.first)
                        != amplified.end();
            out[entry.first] = clamp01(entry.second * (boosted ? 1.0 : 0.5));
        }
        return out;
    }
};

/// Reciprocity, fairness and dependence, as trust and liking proposals.
class SocialExchangeEngine {
public:
    static constexpr const char* MODULE_ID = "social_exchange";

    /// A kept promise and a broken one are not mirror images. Trust rises 0.8
    /// and falls 0.7, but the RelationshipEngine then applies them at 0.10 and
    /// 0.40 -- and only a broken promise records a reputation, because a kept
    /// promise is expected and a broken one is news.
    std::vector<ProposedDelta> on_commitment_resolved(const std::string& owner,
                                                      const std::string& other,
                                                      bool fulfilled) const {
        if (fulfilled)
            return {trust_delta(owner, other, +0.8, "commitment_fulfilled", MODULE_ID),
                    liking_delta(owner, other, +0.4, "commitment_fulfilled", MODULE_ID)};
        return {trust_delta(owner, other, -0.7, "commitment_broken", MODULE_ID),
                liking_delta(owner, other, -0.5, "commitment_broken", MODULE_ID),
                reputation_delta(other, owner, "reliable", -0.4, "broke_promise", MODULE_ID)};
    }

    /// A bounded ratio, so it never divides by zero or goes negative.
    double dependence(double current_value, double best_alternative,
                      double eps = 1e-6) const {
        return current_value / (current_value + best_alternative + eps);
    }

    std::vector<std::pair<std::string, double>> value_terms(
            const ActionDefinition& action, const Json& context) const {
        std::vector<std::pair<std::string, double>> terms;
        if (action.action_id == "ask_for_payment" && context.get("player_owes").as_bool())
            terms.emplace_back("exchange", 0.6);
        return terms;
    }
};

/// In-group threat, as an identity-threat proposal plus an appraisal.
class SocialIdentityEngine {
public:
    static constexpr const char* MODULE_ID = "social_identity";

    struct Outcome {
        std::vector<ProposedDelta> proposals;
        Json appraisal_boost = Json::object();
    };

    /// `identity` is passed in by the runtime, which is the only thing that can
    /// know it: whether an event threatens YOUR belonging depends on who you
    /// are, so it cannot be a property of the event. The payload form is kept
    /// for a pack that wants to state it outright.
    Outcome on_event(const Agent& agent, const Event& event,
                     const std::string& identity = "") const {
        Outcome out;
        std::string which = identity;
        if (which.empty()) {
            const Json* declared = event.payload.find("threatens_identity");
            if (declared && !declared->is_null()) which = declared->py_str();
        }
        if (which.empty()) return out;
        out.proposals.push_back(
            identity_threat(agent.id, which, +0.6, "in_group_threat", MODULE_ID));
        out.appraisal_boost["desirability"] = -0.6;
        out.appraisal_boost["agency"] = std::string("other");
        out.appraisal_boost["praiseworthiness"] = -0.3;
        out.appraisal_boost["target"] = event.actor;
        return out;
    }
};

/// Compliance pressure: sanction times observability times legitimacy.
class NormEngine {
public:
    static constexpr const char* MODULE_ID = "norm";

    std::vector<std::pair<std::string, double>> value_terms(
            const ActionDefinition& action, const Json& context) const {
        std::vector<std::pair<std::string, double>> terms;
        const Json* seen = context.find("surveillance_level");
        double observability = seen ? seen->as_double() : 0.0;
        if (action.action_class == "threaten") {
            const Json* legitimate = context.find("authority_legitimacy");
            double legitimacy = legitimate ? legitimate->as_double() : 0.5;
            terms.emplace_back("norm", -(0.6 * observability * legitimacy));
        }
        if (action.action_class == "share" || action.action_class == "affiliate")
            terms.emplace_back("norm", +0.1);
        return terms;
    }
};

/// Tie strength for credibility, and bridge score for diffusion reach.
class SocialNetworkEngine {
public:
    static constexpr const char* MODULE_ID = "social_network";

    double tie_strength(const Agent& agent, const std::string& other) const {
        const OrderedMap<double>* rel = agent.relationships.find(other);
        double familiarity = rel ? rel->get("familiarity", 0.0) : 0.0;
        double liking = rel ? rel->get("liking", 0.0) : 0.0;
        return clamp01(0.5 * familiarity + 0.5 * liking);
    }

    /// High for service roles -- a bartender, a driver, a trader stands where
    /// circles cross. A pack would compute this from its own graph.
    double bridge_score(const Agent& agent) const {
        for (const Json& role : agent.roles) {
            const Json* name = role.find("role");
            if (!name) continue;
            std::string which = name->py_str();
            if (which == "role:bartender" || which == "role:fixer" || which == "role:trader")
                return 0.8;
        }
        return 0.3;
    }
};

/// Depth-1 models of what others believe, with uncertainty.
class TheoryOfMindEngine {
public:
    static constexpr const char* MODULE_ID = "tom";

    /// Will a threat be believed, or will it be answered?
    /// What a character assumes about somebody they have no reading on. The
    /// midpoint on purpose: no opinion, so the threat term comes out at zero.
    static constexpr double UNKNOWN_FEAR = 0.5;

    /// How much `agent` believes `other` is afraid of THEM.
    ///
    /// NOT `agent.relationships[other]["fear"]`, which is the other
    /// relationship -- how much the agent fears the other -- and reading it here
    /// inverted every threat assessment: a character terrified of somebody
    /// concluded their own threats would land, and one who had spent the week
    /// frightening them concluded they would backfire.
    ///
    /// There is no honest way to read the other's actual fear from here. So this
    /// is a MODEL, and it stays at `UNKNOWN_FEAR` until something the agent has
    /// grounds to reason from writes it -- what they have themselves been seen
    /// to do, recorded by `note_own_act`.
    double believed_fear_of_me(const Agent& agent, const std::string& other) const {
        for (const Agent::TheoryOfMind& model : agent.tom_models) {
            if (model.other != other || model.proposition != "fear_of_me") continue;
            double value = model.model.get("value", UNKNOWN_FEAR);
            return std::max(0.0, std::min(1.0, value));
        }
        return UNKNOWN_FEAR;
    }

    /// How far one act of a given kind moves what the actor thinks it did to the
    /// other's wariness of them, at full severity.
    static double own_act_weight(const std::string& kind, bool& known) {
        known = true;
        if (kind == "attack") return 0.25;
        if (kind == "threat") return 0.20;
        if (kind == "crime") return 0.10;
        if (kind == "gift") return -0.15;
        known = false;
        return 0.0;
    }

    /// What the person who DID it may reasonably conclude from having done it.
    std::vector<Reason> note_own_act(Agent& agent, const std::string& other,
                                     const std::string& kind, double severity) const {
        bool known = false;
        double step = own_act_weight(kind, known);
        if (!known || other.empty() || other == agent.id) return {};
        Agent::TheoryOfMind* entry = nullptr;
        for (Agent::TheoryOfMind& model : agent.tom_models)
            if (model.other == other && model.proposition == "fear_of_me") {
                entry = &model;
                break;
            }
        if (entry == nullptr) {
            Agent::TheoryOfMind fresh;
            fresh.other = other;
            fresh.proposition = "fear_of_me";
            fresh.model["value"] = UNKNOWN_FEAR;
            fresh.model["confidence"] = 0.0;
            agent.tom_models.push_back(fresh);
            entry = &agent.tom_models.back();
        }
        double before = entry->model.get("value", UNKNOWN_FEAR);
        double clamped_severity = std::max(0.0, std::min(1.0, severity));
        double now = std::max(0.0, std::min(1.0, before + step * clamped_severity));
        entry->model["value"] = now;
        entry->model["confidence"] =
            std::min(1.0, entry->model.get("confidence", 0.0) + 0.3);
        if (std::fabs(now - before) < 1e-9) return {};
        Json detail = Json::object();
        detail["agent"] = agent.id;
        detail["about"] = other;
        detail["model"] = std::string("fear_of_me");
        detail["was"] = py_round(before, 4);
        detail["now"] = py_round(now, 4);
        detail["because"] = kind;
        detail["note"] = std::string("what they take from having done it, not "
                                     "what the other feels");
        return {{"tom.updated", py_round(now - before, 4), detail}};
    }

    std::pair<std::string, double> expected_reaction(
            const Agent& agent, const std::string& other,
            const std::string& action_class) const {
        if (action_class == "threaten") {
            double fear = believed_fear_of_me(agent, other);
            // Works if they fear you; backfires if they do not.
            return {"tom", 0.4 * fear - 0.4 * (1 - fear)};
        }
        return {"tom", 0.0};
    }
};

/// Front and back stage face management.
class ImpressionManagementEngine {
public:
    static constexpr const char* MODULE_ID = "impression";

    bool front_stage(const Json& context) const {
        const Json* audience = context.find("audience_size");
        const Json* seen = context.find("surveillance_level");
        double size = audience ? audience->as_double() : 0.0;
        double surveillance = seen ? seen->as_double() : 0.0;
        return size > 0 || surveillance > 0.3;
    }

    std::vector<std::pair<std::string, double>> value_terms(
            const ActionDefinition& action, const Json& context) const {
        std::vector<std::pair<std::string, double>> terms;
        if (!front_stage(context)) return terms;
        if (action.action_class == "threaten" && context.get("public_role_formal").as_bool())
            terms.emplace_back("face", -0.4);
        if (action.action_class == "affiliate" || action.action_class == "repair_face")
            terms.emplace_back("face", +0.2);
        return terms;
    }

    double weight(const Json& context) const {
        return 1.0 + (front_stage(context) ? 0.8 : -0.6);
    }
};

/// Situational circumplex stance: agency and communion.
///
/// NOT CONSTRUCTED BY THE RUNTIME, deliberately. It was instantiated on every
/// runtime and never called: nothing consumed the stance it computes, so it cost
/// an object per runtime and implied a feature that did not exist.
///
/// Kept rather than deleted because the mapping is right and the work is real.
/// What is missing is the other half: the sociolinguistic engine would have to
/// take a stance alongside its style vector, and the realizer would have to
/// phrase from it. Until somebody does that this is a component with no socket,
/// and saying so is better than a constructor call that makes it look wired.
class InterpersonalEngine {
public:
    static constexpr const char* MODULE_ID = "interpersonal";

    std::pair<double, double> stance(const Agent& agent, const std::string& other,
                                     const AffectEngine& affect) const {
        const OrderedMap<double>* rel = agent.relationships.find(other);
        double liking = rel ? rel->get("liking", 0.0) : 0.0;
        double fear = rel ? rel->get("fear", 0.0) : 0.0;
        double respect = rel ? rel->get("respect", 0.0) : 0.0;

        double communion = clamp_signed(liking - 0.5 * fear);
        double agency = clamp_signed(0.5 * respect + agent.affect.mood.d);

        // Anger raises agency and lowers communion; fear lowers agency.
        OrderedMap<double> toward;
        if (!other.empty()) toward = AffectEngine::emotions_toward(agent.affect, other);
        (void)affect;
        agency += 0.5 * toward.get("anger", 0.0) - 0.5 * toward.get("fear", 0.0);
        communion -= 0.5 * (toward.get("anger", 0.0) + toward.get("disliking", 0.0));
        return {clamp_signed(agency), clamp_signed(communion)};
    }
};

}  // namespace usc
