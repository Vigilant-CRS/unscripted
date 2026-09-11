// `usc/policy.py`. Utility aggregation, and the choice.
//
// Three roles kept distinct on purpose: additive value terms, multiplicative
// personality and identity weights, and the emotion action-tendency bias.
//
// THE DIFFERENCE BETWEEN A TERM AND A BIAS, which cost an afternoon in the
// Python and is preserved exactly here. A term is an opinion about an outcome,
// and terms in a group are AVERAGED so a group stays in [-1, 1] however many of
// them there are. That is right for what it was built for and wrong for a
// modifier: a bias meant to make evading a little more attractive, contributed
// as a term worth +0.12 into a group already holding +0.30, LOWERS the group to
// +0.21. Somebody dressed to look dangerous made a character *less* likely to
// back away, while every individual piece of arithmetic was correct.
//
// So a bias is added, exactly as the emotional action tendency always was. A
// port that folded the two channels together would reintroduce the bug in a
// place nobody would look for it twice.
#pragma once

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include "usc/actions.hpp"
#include "usc/affect.hpp"
#include "usc/determinism.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/pysum.hpp"
#include "usc/relationship.hpp"
#include "usc/types.hpp"
#include "usc/knob.hpp"

namespace usc {

inline double prospect_value(double x, double reference, double alpha = 0.88,
                             double beta = 0.88, double lambda = 2.25) {
    double z = x - reference;
    return z >= 0 ? std::pow(z, alpha) : -lambda * std::pow(-z, beta);
}

inline double prospect_weight(double p, double gamma = 0.61) {
    if (p <= 0) return 0.0;
    if (p >= 1) return 1.0;
    double numerator = std::pow(p, gamma);
    return numerator / std::pow(numerator + std::pow(1 - p, gamma), 1 / gamma);
}

/// Average, so a group's value stays in [-1,1] whatever the term count.
inline double bounded_aggregate(const std::vector<double>& values) {
    if (values.empty()) return 0.0;
    return clamp_signed(py_sum(values)
                        / static_cast<double>(std::max<std::size_t>(1, values.size())));
}

/// The slice of a character the policy engine reads. Kept separate from
/// `AgentState` so it is obvious what a decision actually depends on.
struct DecidingAgent {
    std::string id;
    std::string global_seed = "s";
    OrderedMap<double> big_five;
    const AffectState* affect = nullptr;
};

using PolicyReason = Reason;

class PolicyEngine {
public:
    struct Params {
        double temperature = 0.3;
        bool use_prospect = false;
        double w_impulsivity = 0.4;
        double w_arousal = 0.3;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("temperature", &Params::temperature),
            knob("use_prospect", &Params::use_prospect),
            knob("w_impulsivity", &Params::w_impulsivity),
            knob("w_arousal", &Params::w_arousal),
        };
        return table;
    }

    PolicyEngine() = default;
    explicit PolicyEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    double outcome_value(const ActionOutcome& outcome) const {
        double value, weight;
        if (params_.use_prospect) {
            value = prospect_value(outcome.delta, outcome.reference_point);
            weight = prospect_weight(outcome.probability);
        } else {
            value = outcome.delta;
            weight = outcome.probability;
        }
        return clamp_signed(value * weight);
    }

    /// `term_providers(action) -> [(group, value)]`, `bias_providers(action) ->
    /// double` added rather than averaged.
    template <typename TermProvider, typename BiasProvider>
    std::vector<ActionCandidate> score(const std::vector<ActionDefinition>& candidates,
                                       const OrderedMap<double>& weights,
                                       TermProvider term_providers,
                                       const OrderedMap<double>& action_tendencies,
                                       BiasProvider bias_providers,
                                       bool has_bias_providers) const {
        std::vector<ActionCandidate> scored;
        for (const ActionDefinition& definition : candidates) {
            OrderedMap<std::vector<double>> groups;
            // 1. outcomes become a value term in the action's dimensions
            for (const ActionOutcome& outcome : definition.outcomes)
                groups[outcome.dimension].push_back(outcome_value(outcome));
            // 2. module-provided value terms
            for (const auto& term : term_providers(definition))
                groups[term.first].push_back(term.second);

            std::vector<std::tuple<std::string, double, double, double>> contributions;
            double total = 0.0;
            for (const auto& group : groups) {
                double value = bounded_aggregate(group.second);
                double weight = weights.get(group.first, 1.0);
                double contribution = weight * value;
                total += contribution;
                contributions.emplace_back(group.first, py_round(value, 3),
                                           py_round(weight, 3), py_round(contribution, 3));
            }
            // 3. the emotional push -- a push, not a value source
            double emotion = clamp_signed(action_tendencies.get(definition.action_class, 0.0));
            total += emotion;
            contributions.emplace_back("emotion_tendency", py_round(emotion, 3), 1.0,
                                       py_round(emotion, 3));
            // 4. and every other push: what they think of you, what you look
            //    like. Added, for the reason at the top of this file.
            if (has_bias_providers) {
                double pushed = bias_providers(definition);
                if (pushed != 0.0) {       // `if pushed:` -- zero contributes no row
                    total += pushed;
                    contributions.emplace_back("bias", py_round(pushed, 3), 1.0,
                                               py_round(pushed, 3));
                }
            }
            ActionCandidate candidate;
            candidate.action = definition;
            candidate.utility = total;
            candidate.contributions = contributions;
            scored.push_back(candidate);
        }
        // Stable and descending, like Python's. On a tie the catalogue order
        // wins, which is the order a pack declared its actions in.
        std::stable_sort(scored.begin(), scored.end(),
                         [](const ActionCandidate& a, const ActionCandidate& b) {
                             return a.utility > b.utility;
                         });
        return scored;
    }

    /// Choose among scored candidates. Empty is a caller error, said plainly.
    ///
    /// `max()` on an empty sequence would raise from inside here and tell
    /// whoever supplied an empty affordance query nothing at all. A studio
    /// bringing its own action catalogue will hit this, and the message is the
    /// difference between a five-minute fix and an afternoon.
    std::pair<ActionCandidate, std::vector<PolicyReason>> select(
            const DecidingAgent& agent, const std::vector<ActionCandidate>& scored,
            long long event_id, long long world_time) const {
        if (scored.empty())
            throw std::invalid_argument(
                "no action candidates to choose between. The affordance query "
                "for this situation returned nothing -- a character must always "
                "have at least one thing they could do, even if it is to say "
                "nothing. See usc/actions.py: default_candidates().");

        // `agent.big_five.get("impulsivity", 1 - agent.big_five.get("conscientiousness", 0.5))`
        // -- the fallback is computed either way in Python, and is exact here.
        double impulsivity = agent.big_five.get("impulsivity",
                                                1 - agent.big_five.get("conscientiousness", 0.5));
        double arousal = agent.affect ? agent.affect->mood.a : 0.0;
        double temperature = std::max(0.05, params_.temperature
                                            * (1 + params_.w_impulsivity * impulsivity
                                                 + params_.w_arousal * std::max(0.0, arousal)));

        double highest = scored.front().utility;
        for (const ActionCandidate& candidate : scored)
            highest = std::max(highest, candidate.utility);

        std::vector<double> weights;
        weights.reserve(scored.size());
        for (const ActionCandidate& candidate : scored)
            weights.push_back(std::exp((candidate.utility - highest) / temperature));

        std::vector<std::uint8_t> seed = derive_seed(agent.global_seed, agent.id,
                                                     event_id, world_time, "policy");
        std::size_t index = seeded_choice(seed, weights);
        const ActionCandidate& chosen = scored[index];

        // Three distinct facts kept separate so a stochastic pick never reads as
        // a bug: the HIGHEST-RATED action, the one actually SAMPLED, and the
        // selection probability of each.
        double total = py_sum(weights);
        if (total == 0.0) total = 1.0;              // `sum(exps) or 1.0`
        Json probabilities = Json::array();
        for (std::size_t i = 0; i < scored.size(); ++i) {
            Json row = Json::tuple();
            row.push(Json(scored[i].action.action_id));
            row.push(Json(py_round(weights[i] / total, 3)));
            probabilities.push(row);
        }
        const ActionCandidate& top = scored.front();   // sorted descending

        Json contributions = Json::array();
        for (const auto& row : chosen.contributions) {
            Json entry = Json::tuple();
            entry.push(Json(std::get<0>(row)));
            entry.push(Json(std::get<1>(row)));
            entry.push(Json(std::get<2>(row)));
            entry.push(Json(std::get<3>(row)));
            contributions.push(entry);
        }

        Json detail = Json::object();
        detail["sampled_action"] = chosen.action.action_id;
        detail["top_rated_action"] = top.action.action_id;
        detail["top_rated_utility"] = py_round(top.utility, 3);
        detail["stochastic"] = chosen.action.action_id != top.action.action_id;
        detail["T"] = py_round(temperature, 3);
        detail["selection_probs"] = probabilities;
        detail["contributions"] = contributions;

        return {chosen, {{"policy.selected", py_round(chosen.utility, 3), detail}}};
    }

private:
    Params params_;
};

}  // namespace usc
