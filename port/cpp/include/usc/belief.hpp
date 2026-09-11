// `usc/belief.py`. Subjective probability in log-odds, dual evidence, and the
// correlation discount that stops one rumour repeated ten times from becoming
// certainty.
//
// The first module with a real answer in it, and the one the conformance
// fixtures test hardest. Three things here are easy to port slightly wrong and
// all three are checked by `belief_probe.cpp` against Python:
//
//   - `origin_counts` keys are STRINGS. Origins arrive as raw event ids, often
//     integers, and JSON has only string keys -- so a saved belief that kept
//     them as integers came back not matching, and started treating a repeated
//     rumour as independent evidence again. `_origin_key` normalises, and so
//     does this.
//   - `rho ** heard`, where `heard` is the count BEFORE this hearing. Off by
//     one and the first assertion from a new origin is already discounted.
//   - the provenance trim keeps the NEWEST entries and counts what it dropped.
//     Origin identity is never trimmed, because that is what the arithmetic
//     needs; the entries are for the inspector.
#pragma once

#include <array>
#include <cmath>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/types.hpp"
#include "usc/knob.hpp"

namespace usc {

/// One recorded piece of evidence. Kept for the inspector and for revision:
/// when a source turns out to have been lying, lowering trust going forward is
/// not enough -- what they already convinced people of has to be recomputed,
/// and that needs the signed contribution and the speaker.
struct ProvenanceEntry {
    Json claim_id;
    Json origin_event;
    double kappa = 0.0;
    double eta = 0.0;
    double delta = 0.0;
    Json speaker;
    /// Set by `revision.hpp` when a source is discredited. Absent otherwise --
    /// Python adds the key on write, so a record that was never revised does not
    /// carry it at all, and neither does this.
    Json revised;

    Json as_json() const {
        Json out = Json::object();
        out["claim_id"] = claim_id;
        out["origin_event"] = origin_event;
        out["kappa"] = kappa;
        out["eta"] = eta;
        out["delta"] = delta;
        out["speaker"] = speaker;
        if (!revised.is_null()) out["revised"] = revised;
        return out;
    }
};

inline std::string origin_key(const Json& origin) { return origin.py_str(); }

/// Separates the two halves of a contribution key. A unit separator, because it
/// cannot occur in an agent id or an origin token and so cannot be forged by one.
inline const std::string CONTRIB_SEP = "\x1f";

/// Where contributions go when a belief has heard from more distinct sources
/// than it retains. Still counted in the log-odds -- the evidence was real --
/// but no longer attributable, so revision cannot unwind them.
inline const std::string CONTRIB_FORGOTTEN = CONTRIB_SEP + "forgotten";

/// Who said it and which origin it carried, as one key. Exactly the pair
/// `revision` matches on, which is why the cumulative arithmetic is filed under
/// it rather than under either half alone.
inline std::string contribution_key(const Json& speaker, const Json& origin) {
    return (speaker.is_null() ? std::string() : speaker.py_str()) + CONTRIB_SEP
         + (origin.is_null() ? std::string() : origin_key(origin));
}

struct Belief {
    Proposition proposition;
    double logit_val = 0.0;
    double support_for = 0.0;
    double support_against = 0.0;
    std::vector<ProvenanceEntry> provenance;
    Json valid_start;
    Json txn_time;
    /// Distinct origins already counted, and how often each was heard. Ordered,
    /// because `primary_origin` is the first one.
    OrderedMap<long long> origin_counts;
    long long provenance_dropped = 0;
    /// Cumulative signed log-odds contributed, per (speaker, origin), as
    /// {positive, negative}.
    ///
    /// THE ARITHMETIC RECORD, and it exists because the provenance list is not
    /// one: that list is trimmed to its newest entries for the inspector, and
    /// revision used to sum the deltas *in it*, so once a claim had been heard
    /// often enough the early, heavy entries were gone and exposing the only
    /// source who supplied them changed nothing at all.
    OrderedMap<std::array<double, 2>> contributions;
    /// Distinct origins this belief turned away because its index was full.
    /// They contributed NO evidence -- see `correlation_discount`.
    ///
    /// THE INDEX DOES NOT EVICT, and that is the whole of the global bound.
    /// Two earlier designs kept evicting and tried to pay for it afterwards, and
    /// both leaked: an index that forgets cannot recognise a repeat, so any
    /// correction applied at re-admission bounds one step of a sequence whose
    /// length an adversary chooses. Not evicting makes the bound a consequence of
    /// the arithmetic -- the n-th hearing is worth `rho^(n-1)` for every n, so
    /// the total is a geometric series under `1/(1-rho)` for ANY ordering, across
    /// save and load. The cost is stated: at capacity a genuinely new source is
    /// refused, which over-doubts. Doubt is the safe direction; the alternative
    /// was proof.
    long long origins_refused = 0;
    long long hops = 0;
    bool spreading = true;

    /// The origin this holder would cite -- the first they heard. A retelling
    /// carries this, not the teller, which is what keeps a rumour relayed
    /// through five mouths worth one witness rather than five.
    const std::string* primary_origin() const {
        const auto* first = origin_counts.first();
        return first ? &first->first : nullptr;
    }

    double expected_prob() const { return sigmoid(logit_val); }

    double ignorance() const { return 1.0 / (1.0 + support_for + support_against); }

    double conflict() const {
        double total = support_for + support_against;
        if (total <= 1e-9) return 0.0;
        return (2.0 * std::min(support_for, support_against)) / total;
    }

    void record_provenance(const Json& claim_id, const Json& origin, double kappa,
                           double eta, double delta, const Json& speaker,
                           long long limit = 64, long long origin_limit = 512) {
        if (!origin.is_null()) {
            const std::string key = origin_key(origin);
            if (origin_counts.contains(key)) {
                // A KNOWN ORIGIN ALWAYS COUNTS UP, whatever the index holds --
                // the half that makes `rho ** heard` a real exponent.
                origin_counts[key] += 1;
            } else if (origin_limit <= 0
                       || static_cast<long long>(origin_counts.size()) < origin_limit) {
                origin_counts[key] = 1;
            } else {
                // FULL. The index does not evict, so this source is turned away
                // rather than let in at the price of forgetting another. It also
                // contributed no evidence -- `correlation_discount` returned 0
                // for exactly this case, which is why the bound holds.
                origins_refused += 1;
            }
        }
        if (delta != 0.0) {
            std::string attribution = contribution_key(speaker, origin);
            if (!contributions.contains(attribution) && origin_limit > 0
                && static_cast<long long>(contributions.size()) >= origin_limit) {
                attribution = CONTRIB_FORGOTTEN;
            }
            std::array<double, 2>& bucket = contributions[attribution];
            bucket[delta > 0.0 ? 0 : 1] += delta;
        }
        ProvenanceEntry entry;
        entry.claim_id = claim_id;
        entry.origin_event = origin;
        entry.kappa = py_round(kappa, 3);
        entry.eta = py_round(eta, 3);
        entry.delta = py_round(delta, 6);
        entry.speaker = speaker;
        provenance.push_back(entry);
        if (limit > 0 && static_cast<long long>(provenance.size()) > limit) {
            long long overflow = static_cast<long long>(provenance.size()) - limit;
            provenance.erase(provenance.begin(),
                             provenance.begin() + static_cast<std::size_t>(overflow));
            provenance_dropped += overflow;
        }
    }

    /// Restore a saved belief. Only the primitives round-trip:
    /// `expected_prob`, `ignorance` and `conflict` are derived and recomputed.
    static Belief from_json(const Json& doc) {
        Belief out;
        out.proposition = Proposition::from_json(doc.at("proposition"));
        out.logit_val = doc.get("logit").as_double();
        out.support_for = doc.get("support_for").as_double();
        out.support_against = doc.get("support_against").as_double();
        for (const Json& row : doc.at("provenance").items()) {
            ProvenanceEntry entry;
            entry.claim_id = row.get("claim_id");
            entry.origin_event = row.get("origin_event");
            entry.kappa = row.get("kappa").as_double();
            entry.eta = row.get("eta").as_double();
            entry.delta = row.get("delta").as_double();
            entry.speaker = row.get("speaker");
            entry.revised = row.get("revised");
            out.provenance.push_back(entry);
        }
        const Json* counts = doc.find("origin_counts");
        if (counts && !counts->is_null()) {
            for (const auto& entry : counts->fields())
                out.origin_counts[entry.first] = entry.second.as_int();
        } else {
            // An older record carries no origin index. Rebuild what is
            // recoverable, so a restored belief still discounts repeats from
            // origins it has already heard -- otherwise loading a save quietly
            // turns a saturated rumour back into fresh evidence.
            for (const ProvenanceEntry& entry : out.provenance)
                if (!entry.origin_event.is_null())
                    out.origin_counts[origin_key(entry.origin_event)] += 1;
        }
        const Json* dropped = doc.find("provenance_dropped");
        out.provenance_dropped = dropped ? dropped->as_int() : 0;
        const Json* contributed = doc.find("contributions");
        if (contributed && !contributed->is_null()) {
            for (const auto& entry : contributed->fields()) {
                const std::vector<Json>& pair = entry.second.items();
                std::array<double, 2> bucket{0.0, 0.0};
                if (pair.size() > 0) bucket[0] = pair[0].as_double();
                if (pair.size() > 1) bucket[1] = pair[1].as_double();
                out.contributions[entry.first] = bucket;
            }
        } else {
            // An older record carries no arithmetic ledger. Rebuild what the
            // surviving provenance can still account for; anything already
            // trimmed is unattributable and says so.
            for (const ProvenanceEntry& entry : out.provenance) {
                if (entry.delta == 0.0) continue;
                std::array<double, 2>& bucket =
                    out.contributions[contribution_key(entry.speaker, entry.origin_event)];
                bucket[entry.delta > 0.0 ? 0 : 1] += entry.delta;
            }
        }
        const Json* refused = doc.find("origins_refused");
        out.origins_refused = refused ? refused->as_int() : 0;
        const Json* hops = doc.find("hops");
        out.hops = hops ? hops->as_int() : 0;
        const Json* spreading = doc.find("spreading");
        out.spreading = spreading ? spreading->as_bool(true) : true;
        out.valid_start = doc.get("valid_start");
        out.txn_time = doc.get("txn_time");
        return out;
    }

    Json as_json() const {
        Json out = Json::object();
        out["proposition"] = proposition.as_json();
        out["logit"] = logit_val;
        out["expected_prob"] = expected_prob();
        out["support_for"] = support_for;
        out["support_against"] = support_against;
        out["ignorance"] = ignorance();
        out["conflict"] = conflict();
        Json entries = Json::array();
        for (const auto& entry : provenance) entries.push(entry.as_json());
        out["provenance"] = entries;
        Json counts = Json::object();
        for (const auto& entry : origin_counts)
            counts.fields()[entry.first] = Json(entry.second);
        out["origin_counts"] = counts;
        Json contributed = Json::object();
        for (const auto& entry : contributions) {
            Json pair = Json::array();
            pair.push(Json(entry.second[0]));
            pair.push(Json(entry.second[1]));
            contributed.fields()[entry.first] = pair;
        }
        out["contributions"] = contributed;
        out["origins_refused"] = origins_refused;
        out["provenance_dropped"] = provenance_dropped;
        out["hops"] = hops;
        out["spreading"] = spreading;
        out["valid_start"] = valid_start;
        out["txn_time"] = txn_time;
        return out;
    }
};

class BeliefEngine {
public:
    struct Params {
        double kappa0 = 0.55;
        double alpha = 0.25;
        double gamma = 0.20;
        double delta = 0.30;
        double kappa_min = 0.20;
        double kappa_max = 0.95;
        /// Geometric attenuation per repeat from a known origin. Because it is
        /// below 1 the series converges: one origin can never contribute more
        /// than 1/(1-rho) hearings however often it is repeated. A flat
        /// discount attenuates without saturating, and 200 repetitions of a
        /// single rumour still reached p = 0.995 -- the exact failure this
        /// exists to prevent.
        double rho_correlated = 0.10;
        long long provenance_limit = 64;
        /// How many distinct sources one belief tracks before it starts
        /// forgetting. Bounded because everything per-character here has to be.
        long long origin_limit = 512;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("kappa0", &Params::kappa0),
            knob("alpha", &Params::alpha),
            knob("gamma", &Params::gamma),
            knob("delta", &Params::delta),
            knob("kappa_min", &Params::kappa_min),
            knob("kappa_max", &Params::kappa_max),
            knob("rho_correlated", &Params::rho_correlated),
            knob("provenance_limit", &Params::provenance_limit),
            knob("origin_limit", &Params::origin_limit),
        };
        return table;
    }

    BeliefEngine() = default;
    explicit BeliefEngine(const Params& params) : params_(params) {}

    const Params& params() const { return params_; }
    Params& params() { return params_; }

    double credibility(double trust, double competence, double skepticism) const {
        double kappa = params_.kappa0 + params_.alpha * trust
                     + params_.gamma * competence - params_.delta * skepticism;
        return clamp(kappa, params_.kappa_min, params_.kappa_max);
    }

    double correlation_discount(const Belief& belief, const Json& origin) const {
        if (origin.is_null()) return 1.0;
        long long heard = belief.origin_counts.get(origin_key(origin), 0);
        long long limit = params_.origin_limit;
        if (heard == 0 && limit > 0
                && static_cast<long long>(belief.origin_counts.size()) >= limit) {
            // AT CAPACITY AND UNRECOGNISED: no evidence, because the belief
            // cannot tell this source from one it has already counted. Refusing
            // is the only answer that keeps the bound true for every ordering.
            // `origins_refused` says how often.
            return 0.0;
        }
        return std::pow(params_.rho_correlated, static_cast<double>(heard));
    }

    /// Ceiling on what one origin can ever contribute, in single hearings.
    ///
    /// A THEOREM, not a policy, and it holds for every ordering of events
    /// including save and load: the origin index does not evict, so the n-th
    /// hearing is worth `rho^(n-1)` for every n and the total is a geometric
    /// series under `1/(1-rho)`. A source the index has no room for is worth
    /// exactly zero and is counted in `origins_refused`.
    double max_origin_contribution() const {
        return 1.0 / (1.0 - params_.rho_correlated);
    }

    /// Update the belief about `claim`. Returns the reason trace; the belief is
    /// left in `beliefs` under its core key.
    std::vector<Reason> update(OrderedMap<Belief>& beliefs, const Proposition& claim,
                               const std::string& asserter_polarity, double trust,
                               double competence, double skepticism,
                               const Json& claim_id, const Json& origin,
                               const Json& world_time,
                               const Json& speaker = Json()) const {
        std::vector<Reason> reasons;
        const std::string key = claim.core_key();
        Belief* belief = beliefs.find(key);
        if (belief == nullptr) {
            Belief fresh;
            // The stored proposition is always positive: polarity lives in the
            // log-odds, not in the identity.
            fresh.proposition = claim;
            fresh.proposition.polarity = "+";
            fresh.proposition.degree = Json();   // Python's constructor omits it
            fresh.logit_val = 0.0;
            fresh.valid_start = world_time;
            beliefs[key] = fresh;
            belief = beliefs.find(key);
        }

        double kappa = credibility(trust, competence, skepticism);
        double eta = correlation_discount(*belief, origin);
        double sign = (asserter_polarity == "+") ? 1.0 : -1.0;
        double evidence = eta * std::log(kappa / (1.0 - kappa));
        // WHICH POOL A PIECE OF EVIDENCE LANDS IN IS DECIDED BY WHAT IT DID TO
        // THE LOG-ODDS, not by which way it was asserted. Below kappa = 0.5 the
        // log-odds term is negative, so a positive assertion from a source that
        // discredited LOWERS the probability -- and filing that under
        // `support_for` made the two halves of the record contradict each other.
        double contribution = sign * evidence;
        belief->logit_val += contribution;
        if (contribution >= 0.0) belief->support_for += contribution;
        else                     belief->support_against += -contribution;
        belief->record_provenance(claim_id, origin, kappa, eta, contribution,
                                  speaker, params_.provenance_limit,
                                  params_.origin_limit);
        belief->txn_time = world_time;

        Json detail = Json::object();
        detail["proposition"] = claim.str();
        detail["kappa"] = py_round(kappa, 3);
        detail["eta"] = py_round(eta, 3);
        detail["new_prob"] = py_round(belief->expected_prob(), 3);
        reasons.push_back({"belief.updated", py_round(contribution, 4), detail});

        // Contradictions are surfaced, not collapsed: this model is
        // paraconsistent on purpose. Somebody can hold two beliefs that cannot
        // both be true, and knowing that is the interesting part.
        for (const auto& entry : beliefs) {
            if (&entry.second == belief) continue;
            std::string kind = contradicts(belief->proposition, entry.second.proposition);
            if (kind.empty()) continue;
            Json clash = Json::object();
            clash["kind"] = kind;
            clash["a"] = belief->proposition.str();
            clash["b"] = entry.second.proposition.str();
            reasons.push_back({"belief.contradiction", 0.0, clash});
        }
        return reasons;
    }

private:
    Params params_;
};

}  // namespace usc
