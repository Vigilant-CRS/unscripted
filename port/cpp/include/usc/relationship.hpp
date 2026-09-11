// `usc/relationship.py`. The three cross-cutting state owners: the relationship
// vector, audience-specific reputation, and which identity is currently salient.
//
// The interesting asymmetry is in `RelationshipEngine`: trust rises at 0.10 and
// falls at 0.40. Positive and negative deltas are summed separately and applied
// with different gains, so somebody who helps you four times and betrays you
// once is not back where they started. That is a modelling claim, not an
// implementation detail, and a port that averaged the two would produce a world
// where trust is cheap to rebuild.
//
// `IdentityEngine.salience` is the one place a tie matters: Python's `max` over
// `sal.items()` returns the FIRST maximum in iteration order. With an unordered
// container the winner on a tie is whichever identity happened to hash lowest,
// which is a different character deciding they are a docker rather than a
// father, silently, on one machine and not another.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/pysum.hpp"
#include "usc/statekey.hpp"
#include "usc/types.hpp"
#include "usc/knob.hpp"

namespace usc {

using RelationshipReason = Reason;

class RelationshipEngine {
public:
    struct Params {
        /// Slow up, fast down. Not symmetrical on purpose.
        double eta_up = 0.10;
        double eta_down = 0.40;
        double eta_other = 0.20;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("eta_up", &Params::eta_up),
            knob("eta_down", &Params::eta_down),
            knob("eta_other", &Params::eta_other),
        };
        return table;
    }

    RelationshipEngine() = default;
    explicit RelationshipEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    void apply(Agent& agent, const std::vector<ProposedDelta>& deltas,
               std::vector<RelationshipReason>& reasons) const {
        // Group by (subject, field), preserving first-appearance order. The
        // grouping is not cosmetic: the sums below are floating-point additions
        // and a different order gives a different last bit.
        OrderedMap<std::vector<const ProposedDelta*>> grouped;
        OrderedMap<std::pair<std::string, std::string>> parts;
        for (const ProposedDelta& delta : deltas) {
            std::string subject = delta.key.subject_id ? *delta.key.subject_id : "None";
            std::string group = subject + "\x1f" + delta.key.field;
            grouped[group].push_back(&delta);
            parts[group] = {subject, delta.key.field};
        }

        for (const auto& entry : grouped) {
            const std::string& subject = parts.find(entry.first)->first;
            const std::string& field = parts.find(entry.first)->second;
            OrderedMap<double>& relation = agent.relationships[subject];
            double current = relation.get(field, field == "trust" ? 0.3 : 0.0);

            // Two compensated sums, because `sum()` compensates. And two that
            // may be EMPTY: `sum()` over nothing returns the integer 0, not
            // 0.0, and the reason trace carries that difference into the
            // exported state as `0` rather than `0.0`.
            PySum positive, negative;
            for (const ProposedDelta* delta : entry.second) {
                if (delta->amount >= 0) positive.add(delta->amount);
                else                    negative.add(delta->amount);
            }
            double up = positive.value(), down = negative.value();

            double updated = (field == "trust")
                ? current + params_.eta_up * up + params_.eta_down * down
                : current + params_.eta_other * (up + down);

            // Which fields are one-sided and which are bipolar. `fear` and
            // `respect` cannot go below zero -- there is no such thing as
            // negative fear here, only its absence.
            bool unipolar = field == "trust" || field == "respect"
                         || field == "fear" || field == "dependence";
            updated = unipolar ? clamp01(updated) : clamp_signed(updated);
            relation[field] = updated;

            Json why = Json::array();
            for (const ProposedDelta* delta : entry.second) why.push(Json(delta->reason));
            Json detail = Json::object();
            detail["subject"] = subject;
            detail["field"] = field;
            detail["pos"] = positive.empty() ? Json(0LL) : Json(py_round(up, 3));
            detail["neg"] = negative.empty() ? Json(0LL) : Json(py_round(down, 3));
            detail["reasons"] = why;
            reasons.push_back({"relationship.applied",
                               py_round(updated - current, 4), detail});
        }
    }

private:
    Params params_;
};

class ReputationEngine {
public:
    struct Params {
        double eta_image = 0.25;
        double eta_rep = 0.10;
        double decay = 0.001;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("eta_image", &Params::eta_image),
            knob("eta_rep", &Params::eta_rep),
            knob("decay", &Params::decay),
        };
        return table;
    }

    ReputationEngine() = default;
    explicit ReputationEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    void apply(Agent& agent, const std::vector<ProposedDelta>& deltas,
               std::vector<RelationshipReason>& reasons) const {
        for (const ProposedDelta& delta : deltas) {
            std::string subject = delta.key.subject_id ? *delta.key.subject_id : "None";
            OrderedMap<double>& store = agent.reputation[subject];
            std::string dimension = delta.key.dimension && !delta.key.dimension->empty()
                                  ? *delta.key.dimension : "general";
            double current = store.get(dimension, 0.0);
            double updated = clamp_signed(current + delta.amount);
            store[dimension] = updated;

            Json detail = Json::object();
            detail["subject"] = subject;
            detail["dimension"] = dimension;
            detail["reason"] = delta.reason;
            reasons.push_back({"reputation.applied",
                               py_round(updated - current, 4), detail});
        }
    }

private:
    Params params_;
};

class IdentityEngine {
public:
    struct Params {
        double beta = 4.0;
        double w_acc = 1.0;
        double w_comp = 1.0;
        double w_norm = 1.0;
        double w_threat = 1.0;
        /// An absolute baseline meaning "no identity is strongly salient". Without
        /// it a softmax always elects a winner, however weak the field.
        double neutral_fit = 0.4;
        /// Inertia toward the previous salience, so a character does not switch
        /// who they are between two consecutive sentences.
        double inertia = 0.5;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("beta", &Params::beta),
            knob("w_acc", &Params::w_acc),
            knob("w_comp", &Params::w_comp),
            knob("w_norm", &Params::w_norm),
            knob("w_threat", &Params::w_threat),
            knob("neutral_fit", &Params::neutral_fit),
            knob("inertia", &Params::inertia),
        };
        return table;
    }

    IdentityEngine() = default;
    explicit IdentityEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// Returns the winning identity id, and writes the full distribution onto
    /// the agent.
    std::string salience(Agent& agent, const Json& context,
                         const OrderedMap<double>& threat_by_identity = {}) const {
        OrderedMap<double> fits;
        const Json& comparative = context.at("comparative_fit");
        const Json& normative = context.at("normative_fit");
        for (const Json& identity : agent.identities) {
            // `ident["id"]` and `ident.get("accessibility", 0.5)` -- the id is
            // required and the rest is optional, which is what a pack writes.
            const std::string id = identity.at("id").as_string();
            const Json* accessibility = identity.find("accessibility");
            const Json* comp = comparative.find(id);
            const Json* norm = normative.find(id);
            double threat = threat_by_identity.get(id, 0.0);
            fits[id] = params_.w_acc * (accessibility ? accessibility->as_double() : 0.5)
                     + params_.w_comp * (comp ? comp->as_double() : 0.0)
                     + params_.w_norm * (norm ? norm->as_double() : 0.0)
                     + params_.w_threat * threat;
        }
        fits["_neutral"] = params_.neutral_fit;

        double highest = -std::numeric_limits<double>::infinity();
        for (const auto& entry : fits) highest = std::max(highest, entry.second);

        OrderedMap<double> weights;
        for (const auto& entry : fits)
            weights[entry.first] = std::exp(params_.beta * (entry.second - highest));

        // Compensated, like `sum(exps.values())`. A naive loop here gave
        // 0.99999999999999989 for a distribution Python normalises by exactly
        // 1.0 -- one bit, every round, compounding through the inertia blend.
        PySum total;
        for (const auto& entry : weights) total.add(entry.second);

        OrderedMap<double> distribution;
        for (const auto& entry : weights)
            distribution[entry.first] = entry.second / total.value();

        if (!agent.identity_salience.empty()) {
            OrderedMap<double> blended;
            for (const auto& entry : distribution) {
                double previous = agent.identity_salience.get(entry.first, 0.0);
                blended[entry.first] = params_.inertia * previous
                                     + (1 - params_.inertia) * entry.second;
            }
            PySum renormal;
            for (const auto& entry : blended) renormal.add(entry.second);
            double z2 = renormal.value();
            for (auto& entry : blended) entry.second /= z2;
            distribution = blended;
        }
        agent.identity_salience = distribution;

        // Python's `max` keeps the FIRST maximum, so a tie goes to whichever
        // identity was inserted first -- and insertion order is the pack's
        // order. Deliberate: `>` rather than `>=`.
        const std::string* winner = nullptr;
        double best = -std::numeric_limits<double>::infinity();
        for (const auto& entry : distribution) {
            if (entry.second > best) { best = entry.second; winner = &entry.first; }
        }
        return winner ? *winner : std::string();
    }

private:
    Params params_;
};

}  // namespace usc
