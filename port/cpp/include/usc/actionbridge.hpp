// `usc/actionbridge.py`. Intents out, results back.
//
// Everything the runtime decides is otherwise a belief or a sentence, and both
// are cheap to be wrong about because nothing visible depends on them. Movement
// is not: the routine layer sets `agent.location` directly, and an engine that
// renders the same character somewhere else now has two worlds -- one the player
// sees, one the simulation reasons about. Nothing detected the split, because
// nothing ever asked the engine whether the character actually got there.
//
// So a physical act is a two-step exchange:
//
//     runtime            engine
//       |  MOVE_TO(dock)   |      the runtime states an INTENT and does not move
//       | ---------------> |      anyone; the character is still where he was
//       |                  |      the engine walks him, or fails to
//       |   SUCCEEDED      |
//       | <--------------- |      only now does the world change
//
// The four results are the ones an engine can actually distinguish. A fifth,
// TIMED_OUT, is the runtime's own: an engine that never answers must not pin a
// character in a pending state forever. An expired intent is a failure -- the
// character stays put, which is what the engine is showing -- and it is COUNTED,
// because a build quietly timing out every intent looks identical from the
// outside to a build with no bridge attached.
//
// OFF BY DEFAULT, AND OFF MEANS UNCHANGED. A studio without an integration is
// not made to build one.
//
// This module converts and records. It never decides what to issue and never
// applies an effect -- the world layer does both.
#pragma once

#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"

namespace usc {

/// The closed catalogue of what the runtime asks an engine to do.
///
/// One entry, deliberately. `MOVE_TO` is emitted because relocation is the one
/// physical act the runtime already decides on its own. `WARN` and `GIVE` are in
/// the roadmap and are NOT here: an intent type that is declared but never issued
/// reads to an integrator as a channel they have to handle, and it would never
/// fire.
inline const std::vector<std::string>& intent_types() {
    static const std::vector<std::string>* types =
        new std::vector<std::string>{"MOVE_TO"};
    return *types;
}

/// What an engine may report back.
inline const std::vector<std::string>& engine_results() {
    static const std::vector<std::string>* results = new std::vector<std::string>{
        "SUCCEEDED", "FAILED", "INTERRUPTED", "UNREACHABLE"};
    return *results;
}

/// What the runtime concludes when nobody reports at all.
inline constexpr const char* TIMED_OUT = "TIMED_OUT";

inline const std::vector<std::string>& all_results() {
    static const std::vector<std::string>* results = [] {
        auto* fresh = new std::vector<std::string>(engine_results());
        fresh->push_back(TIMED_OUT);
        return fresh;
    }();
    return *results;
}

/// Results after which the intended effect is applied. Exactly one.
inline const std::vector<std::string>& applied_results() {
    static const std::vector<std::string>* results =
        new std::vector<std::string>{"SUCCEEDED"};
    return *results;
}

/// One thing the runtime has asked the engine to do and has not seen resolved.
struct ActionIntent {
    std::string intent_id;
    std::string actor;
    std::string type;
    Json params = Json::object();
    std::string reason;
    long long issued_at = 0;      // world time, minutes
    long long expires_at = 0;     // world time after which it is TIMED_OUT

    Json as_json() const {
        Json out = Json::object();
        out["intent_id"] = intent_id;
        out["actor"] = actor;
        out["type"] = type;
        out["params"] = params;
        out["reason"] = reason;
        out["issued_at"] = issued_at;
        out["expires_at"] = expires_at;
        return out;
    }
};

struct ResolvedIntent {
    ActionIntent intent;
    std::string status;
    std::string detail;
    long long resolved_at = 0;
    bool applied = false;

    Json as_json() const {
        Json out = intent.as_json();
        out["status"] = status;
        out["detail"] = detail;
        out["resolved_at"] = resolved_at;
        out["applied"] = applied;
        return out;
    }
};

/// Asked about an intent this runtime never issued, or already resolved.
///
/// A distinct type rather than a missing-key error, because the message is shown
/// to an integrator: a second result for one intent is a bug in the integration,
/// not a state this runtime holds.
class UnknownIntent : public std::runtime_error {
public:
    explicit UnknownIntent(const std::string& what) : std::runtime_error(what) {}
};

/// An engine reported something outside the closed result set.
class InvalidResult : public std::invalid_argument {
public:
    explicit InvalidResult(const std::string& what) : std::invalid_argument(what) {}
};

/// Pending intents and their outcomes. Deterministic, serialisable, off by default.
class ActionBridge {
public:
    bool enabled = false;
    /// World minutes an intent may stay pending. A day-long routine block with a
    /// sixty-minute window means a character who cannot be walked is late for one
    /// block, not stuck forever.
    long long timeout_minutes = 60;

    ActionBridge() { for (const std::string& one : all_results()) counts_[one] = 0; }
    explicit ActionBridge(bool on, long long timeout = 60) : ActionBridge() {
        enabled = on;
        timeout_minutes = timeout;
    }

    /// Record an intent and return it. Applies nothing.
    ActionIntent issue(const std::string& actor, const std::string& type,
                       const Json& params, const std::string& reason,
                       long long world_time) {
        if (std::find(intent_types().begin(), intent_types().end(), type)
            == intent_types().end())
            throw std::invalid_argument(
                "not an intent this runtime issues: '" + type + "'. Known: "
                + joined(intent_types()));
        ++counter_;
        // Derived from actor, time and an ordinal: replaying the same session
        // reproduces the same ids, so a recorded engine result still matches.
        ActionIntent intent;
        intent.intent_id = "intent:" + actor + ":" + std::to_string(world_time) + ":"
                         + std::to_string(counter_);
        intent.actor = actor;
        intent.type = type;
        intent.params = params;
        intent.reason = reason;
        intent.issued_at = world_time;
        intent.expires_at = world_time + timeout_minutes;
        pending_[intent.intent_id] = intent;
        return intent;
    }

    /// Everything the engine still owes an answer for, oldest first.
    std::vector<ActionIntent> pending() const {
        std::vector<ActionIntent> out;
        for (const auto& entry : pending_) out.push_back(entry.second);
        // `key=(issued_at, intent_id)`. The id breaks the tie, so two intents
        // issued in the same minute have an order that survives a reload.
        std::stable_sort(out.begin(), out.end(),
                         [](const ActionIntent& a, const ActionIntent& b) {
                             if (a.issued_at != b.issued_at)
                                 return a.issued_at < b.issued_at;
                             return a.intent_id < b.intent_id;
                         });
        return out;
    }

    std::vector<ActionIntent> pending_for(const std::string& actor) const {
        std::vector<ActionIntent> out;
        for (const ActionIntent& intent : pending())
            if (intent.actor == actor) out.push_back(intent);
        return out;
    }

    /// Whether this character is already mid-act, so nothing issues twice.
    bool has_pending(const std::string& actor, const std::string& type) const {
        for (const auto& entry : pending_)
            if (entry.second.actor == actor && entry.second.type == type) return true;
        return false;
    }

    /// Close an intent with what the engine reported.
    ///
    /// The caller decides what, if anything, to apply -- `applied` says whether
    /// the effect should happen.
    ResolvedIntent resolve(const std::string& intent_id, const std::string& status,
                           long long world_time, const std::string& detail = "") {
        std::string upper;
        for (char c : status)
            upper += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (std::find(engine_results().begin(), engine_results().end(), upper)
            == engine_results().end())
            throw InvalidResult("'" + upper + "' is not a result an engine may "
                                "report. Use one of: " + joined(engine_results()) + ".");
        return close(intent_id, upper, world_time, detail);
    }

    /// Time out every intent past its window. Deterministic in world time.
    std::vector<ResolvedIntent> expire(long long world_time) {
        std::vector<std::string> overdue;
        for (const ActionIntent& intent : pending())
            if (world_time > intent.expires_at) overdue.push_back(intent.intent_id);
        std::vector<ResolvedIntent> out;
        for (const std::string& id : overdue)
            out.push_back(close(id, TIMED_OUT, world_time,
                                "no result was reported before the intent expired"));
        return out;
    }

    std::vector<ResolvedIntent> recent(std::size_t limit = 20) const {
        std::size_t from = resolved_.size() > limit ? resolved_.size() - limit : 0;
        return std::vector<ResolvedIntent>(resolved_.begin() + static_cast<long>(from),
                                           resolved_.end());
    }

    /// What an integrator needs to see at a glance.
    Json report() const {
        long long issued = static_cast<long long>(pending_.size());
        for (const auto& entry : counts_) issued += entry.second;
        Json out = Json::object();
        out["enabled"] = enabled;
        out["issued"] = issued;
        out["pending"] = static_cast<long long>(pending_.size());
        out["timeout_minutes"] = timeout_minutes;
        for (const std::string& status : all_results()) {
            const long long* found = counts_.find(status);
            out[py_lower(status)] = found ? *found : 0LL;
        }
        return out;
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled;
        out["timeout_minutes"] = timeout_minutes;
        out["counter"] = counter_;
        Json tally = Json::object();
        for (const auto& entry : counts_) tally[entry.first] = entry.second;
        out["counts"] = tally;
        Json rows = Json::array();
        for (const ActionIntent& intent : pending()) rows.push(intent.as_json());
        out["pending"] = rows;
        return out;
    }

    static ActionBridge from_json(const Json& data) {
        const Json* on = data.find("enabled");
        const Json* timeout = data.find("timeout_minutes");
        ActionBridge bridge(on ? on->truthy() : false,
                            timeout ? timeout->as_int() : 60);
        const Json* counter = data.find("counter");
        bridge.counter_ = counter ? counter->as_int() : 0;
        // Rebuilt from the closed result set rather than from the stored keys, so
        // a snapshot written by an older build cannot leave a tally missing.
        const Json* tally = data.find("counts");
        for (const std::string& status : all_results()) {
            const Json* value = tally ? tally->find(status) : nullptr;
            bridge.counts_[status] = value ? value->as_int() : 0;
        }
        const Json* rows = data.find("pending");
        if (rows) for (const Json& raw : rows->items()) {
            ActionIntent intent;
            intent.intent_id = raw.at("intent_id").as_string();
            intent.actor = raw.at("actor").as_string();
            intent.type = raw.at("type").as_string();
            const Json* params = raw.find("params");
            intent.params = (params && params->truthy()) ? *params : Json::object();
            const Json* reason = raw.find("reason");
            intent.reason = reason ? reason->py_str() : std::string();
            intent.issued_at = raw.at("issued_at").as_int();
            intent.expires_at = raw.at("expires_at").as_int();
            bridge.pending_[intent.intent_id] = intent;
        }
        return bridge;
    }

    /// Kept as a tally rather than derived from the resolved list, which is
    /// trimmed: a long session would otherwise forget what it had already done.
    const OrderedMap<long long>& counts() const { return counts_; }

private:
    static std::string joined(const std::vector<std::string>& words) {
        std::string out;
        for (std::size_t i = 0; i < words.size(); ++i) {
            if (i) out += ", ";
            out += words[i];
        }
        return out;
    }

    ResolvedIntent close(const std::string& intent_id, const std::string& status,
                         long long world_time, const std::string& detail) {
        const ActionIntent* found = pending_.find(intent_id);
        if (!found)
            throw UnknownIntent(
                "no pending intent '" + intent_id + "'. It was never issued, or it "
                "has already been resolved -- a second result for one intent is a "
                "bug in the integration, not a state this runtime holds.");
        ResolvedIntent record;
        record.intent = *found;
        record.status = status;
        record.detail = detail;
        record.resolved_at = world_time;
        record.applied = std::find(applied_results().begin(), applied_results().end(),
                                   status) != applied_results().end();
        pending_.erase(intent_id);
        counts_[status] = counts_.get(status, 0) + 1;
        resolved_.push_back(record);
        // The ledger is the audit trail; this list only has to answer "what
        // happened recently" for the inspector, so it stays bounded.
        if (resolved_.size() > 256)
            resolved_.erase(resolved_.begin(),
                            resolved_.end() - 256);
        return record;
    }

    OrderedMap<ActionIntent> pending_;
    std::vector<ResolvedIntent> resolved_;
    long long counter_ = 0;
    OrderedMap<long long> counts_;
};

}  // namespace usc
