// `usc/revision.py`. What to do when a source turns out to have been lying.
//
// Lowering trust in a liar changes what they will manage to convince you of NEXT
// time. It does nothing about what they already convinced you of, and that is
// the part that matters: the whole point of exposing somebody is that the things
// they told you stop counting.
//
// So a belief has to be recomputable. Every piece of evidence records the signed
// log-odds it contributed and who said it, and revision replays that record with
// the discredited entries reweighted. The change then propagates: anyone who
// believed it because YOU told them is holding evidence that traces back to the
// same origin.
//
// A small incremental truth-maintenance system, and deliberately not a general
// one -- no justification lattice, no nogoods, no assumption sets. Those solve a
// harder problem than this has, and the honest description of what happens here
// is: evidence has weights, a weight changed, add it up again.
//
// The one rule that keeps it sane: REVISION ONLY EVER REWEIGHTS EVIDENCE THAT
// EXISTS. It never invents a belief, never removes one, and never touches a
// belief that has an independent source for what it holds. Being caught in one
// lie does not make everything you ever said false.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/pyround.hpp"
#include "usc/pysum.hpp"
#include "usc/world.hpp"

namespace usc {

/// How far a single exposure can discount what a source already contributed.
/// NOT to zero: people who lie about one thing were sometimes telling the truth
/// about another, and a model that erased everything they said would make
/// exposing them strictly better than never having heard them.
inline constexpr double REVISION_FLOOR = 0.1;

using RevisionReason = Reason;

/// One recomputation pass and what it changed.
struct Revision {
    std::string source;
    double factor = 1.0;
    std::string reason;
    std::vector<Json> changes;
    std::vector<RevisionReason> reasons;

    std::size_t touched() const { return changes.size(); }

    Json as_json() const {
        Json out = Json::object();
        out["source"] = source;
        out["factor"] = py_round(factor, 3);
        out["reason"] = reason;
        out["beliefs_revised"] = static_cast<long long>(touched());
        Json rows = Json::array();
        for (const Json& one : changes) rows.push(one);
        out["changes"] = rows;
        return out;
    }
};

/// Characters that may sit either side of an id inside an origin token.
inline bool revision_boundary(char c) {
    return c == '_' || c == ':' || c == '/' || c == '|' || c == '.' || c == '-'
        || c == ' ';
}

/// Does this origin token name `source` as a WHOLE id?
///
/// `source in origin` was a plain substring test, and substrings of ids are
/// other ids: discrediting `agent:ann` also unwound everything relayed from
/// `said_agent:anna_100`. The match now has to end where an id ends.
inline bool names(const std::string& origin, const std::string& source) {
    if (source.empty() || origin.empty()) return false;
    std::size_t at = origin.find(source);
    while (at != std::string::npos) {
        bool left = (at == 0) || revision_boundary(origin[at - 1]);
        std::size_t end = at + source.size();
        bool right = (end >= origin.size()) || revision_boundary(origin[end]);
        if (left && right) return true;
        at = origin.find(source, at + 1);
    }
    return false;
}

/// Did evidence filed under this (speaker, origin) come from `source`?
///
/// Directly: they said it to this listener. Down a chain: the claim carries the
/// origin it started from, which survives retelling -- so a rumour three hops
/// from the liar still names them.
inline bool key_traces_to(const std::string& speaker, const std::string& origin,
                          const std::string& source) {
    return speaker == source || names(origin, source);
}

/// The same question, asked of one provenance record.
inline bool traces_to(const ProvenanceEntry& entry, const std::string& source) {
    const std::string speaker =
        entry.speaker.is_null() ? std::string() : entry.speaker.py_str();
    const std::string origin =
        entry.origin_event.is_null() ? std::string() : entry.origin_event.py_str();
    return key_traces_to(speaker, origin, source);
}

/// Split a contribution key into its two halves, as `key.split(SEP, 1)` does.
inline std::pair<std::string, std::string> split_contribution(const std::string& key) {
    std::size_t at = key.find(CONTRIB_SEP);
    if (at == std::string::npos) return {key, std::string()};
    return {key.substr(0, at), key.substr(at + CONTRIB_SEP.size())};
}

/// Reweight everything `source` convinced anyone of, and recompute.
///
/// `factor` scales their past contributions: 0.25 means "a quarter of the weight
/// it originally had". `predicate` narrows the revision to one kind of claim,
/// because being caught lying about where somebody is says little about your
/// account of the weather.
inline Revision discredit(World& world, const std::string& source,
                          double factor = 0.25, const std::string& reason = "exposed",
                          const std::string& predicate = "") {
    factor = std::max(REVISION_FLOOR, std::min(1.0, factor));
    Revision revision;
    revision.source = source;
    revision.factor = factor;
    revision.reason = reason;

    for (auto& entry : world.agents) {
        Agent& agent = entry.second;
        // A liar's own beliefs are not evidence from them.
        if (agent.id == source) continue;
        for (auto& held : agent.beliefs) {
            Belief& belief = held.second;
            if (!predicate.empty() && belief.proposition.predicate != predicate) continue;

            // THE ARITHMETIC COMES FROM `contributions`, NOT FROM THE
            // PROVENANCE LIST. That list is trimmed to its newest entries for
            // the inspector, so summing it silently under-corrected -- and once
            // a claim had been heard more than the retention limit, exposing the
            // only source who ever supplied it did nothing whatsoever.
            std::vector<std::string> matched;
            for (const auto& entry : belief.contributions) {
                if (entry.first == CONTRIB_FORGOTTEN) continue;
                auto halves = split_contribution(entry.first);
                if (key_traces_to(halves.first, halves.second, source))
                    matched.push_back(entry.first);
            }
            if (matched.empty()) continue;

            double before = belief.expected_prob();
            PySum positives, negatives;
            for (const std::string& key : matched) {
                const std::array<double, 2>* bucket = belief.contributions.find(key);
                positives.add((*bucket)[0]);
                negatives.add((*bucket)[1]);
            }
            double positive = positives.value();
            double negative = negatives.value();
            double adjustment = (positive + negative) * (factor - 1.0);
            if (std::fabs(adjustment) < 1e-9) continue;

            belief.logit_val += adjustment;
            // EACH POOL LOSES WHAT IT WAS GIVEN. Adding a negative adjustment to
            // `support_against` reported the weakening of positive evidence as
            // the arrival of a contradiction, out of nothing.
            belief.support_for = std::max(0.0, belief.support_for
                                          + positive * (factor - 1.0));
            belief.support_against = std::max(0.0, belief.support_against
                                              + (-negative) * (factor - 1.0));
            for (const std::string& key : matched) {
                std::array<double, 2>* bucket = belief.contributions.find(key);
                (*bucket)[0] *= factor;
                (*bucket)[1] *= factor;
            }
            std::vector<ProvenanceEntry*> affected;
            std::size_t independent = 0;
            for (ProvenanceEntry& record : belief.provenance) {
                if (traces_to(record, source)) affected.push_back(&record);
                else ++independent;
            }
            for (ProvenanceEntry* record : affected) {
                record->delta = py_round(record->delta * factor, 6);
                record->revised = Json(reason);
            }
            bool still_supported = false;
            for (const auto& entry : belief.contributions) {
                if (entry.first == CONTRIB_FORGOTTEN) continue;
                if (std::find(matched.begin(), matched.end(), entry.first)
                    != matched.end()) continue;
                if (entry.second[0] != 0.0 || entry.second[1] != 0.0) {
                    still_supported = true;
                    break;
                }
            }

            double after = belief.expected_prob();
            Json change = Json::object();
            change["agent"] = agent.id;
            change["belief"] = held.first;
            change["was"] = py_round(before, 4);
            change["now"] = py_round(after, 4);
            change["entries_reweighted"] = static_cast<long long>(affected.size());
            change["sources_reweighted"] = static_cast<long long>(matched.size());
            change["independent_entries"] = static_cast<long long>(independent);
            change["still_supported"] = still_supported;
            revision.changes.push_back(change);

            Json detail = Json::object();
            detail["agent"] = agent.id;
            detail["belief"] = held.first;
            detail["source"] = source;
            detail["reason"] = reason;
            detail["factor"] = py_round(factor, 3);
            detail["independent_support"] = static_cast<long long>(independent);
            revision.reasons.push_back({"revision.recomputed",
                                        py_round(after - before, 4), detail});
        }
    }
    return revision;
}

/// Which beliefs rest on this source, WITHOUT changing anything.
///
/// The question a player asks before deciding whether exposing somebody is worth
/// it, and the one a designer asks about whether a lie was load-bearing.
inline std::vector<Json> would_change(const World& world, const std::string& source) {
    std::vector<Json> resting;
    for (const auto& entry : world.agents) {
        const Agent& agent = entry.second;
        if (agent.id == source) continue;
        for (const auto& held : agent.beliefs) {
            const Belief& belief = held.second;
            std::size_t matched = 0;
            for (const auto& entry : belief.contributions) {
                if (entry.first == CONTRIB_FORGOTTEN) continue;
                auto halves = split_contribution(entry.first);
                if (key_traces_to(halves.first, halves.second, source)) ++matched;
            }
            if (matched == 0) continue;
            std::size_t affected = 0;
            for (const ProvenanceEntry& record : belief.provenance)
                if (traces_to(record, source)) ++affected;
            Json row = Json::object();
            row["agent"] = agent.id;
            row["belief"] = held.first;
            row["probability"] = py_round(belief.expected_prob(), 4);
            row["from_this_source"] = static_cast<long long>(affected);
            row["sources_from_this_source"] = static_cast<long long>(matched);
            row["independent"] = static_cast<long long>(belief.provenance.size() - affected);
            resting.push_back(row);
        }
    }
    return resting;
}

}  // namespace usc
