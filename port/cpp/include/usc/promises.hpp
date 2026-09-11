// `usc/promises.py`. A promise that nothing ever checks is not a promise, it is
// a line of dialogue.
//
// The runtime has taken promises since the beginning: a player types "I promise
// to pay you", the parser recognises it, a `promise` event is emitted, and every
// witness encodes a `commitment` memory. Then nothing -- no deadline, no
// keeping, no breaking. And `SocialExchangeEngine.on_commitment_resolved`, which
// has always known exactly what a kept and a broken promise are worth, was never
// called by anything.
//
// That is why three engines looked dead. `ReputationEngine` had no producer, so
// `agent.reputation` was empty in every world at every time, and
// `sociolinguistics` reads it to compute perceived status -- so it was reading a
// permanently empty mapping. The missing piece was never those engines. It was
// the thing that resolves a promise.
//
// HOW A PROMISE IS JUDGED, AND WHY THAT WAY. Not against the truth. This runtime
// holds no ground truth about whether somebody paid -- it holds what people
// believe, and inventing an oracle here would contradict the whole design. So a
// promise is kept WHEN THE PERSON IT WAS MADE TO COMES TO BELIEVE IT WAS. A
// promise quietly fulfilled where the promisee never finds out damages the
// promiser exactly as much as one that was broken, which is unfair, true, and
// the reason people make a point of being seen to deliver.
#pragma once

#include <algorithm>
#include <functional>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/pyround.hpp"
#include "usc/relationship.hpp"
#include "usc/social.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

/// How long a promise has when nothing in it says. Two days: long enough that a
/// player can plausibly act on it within a session, short enough that the
/// consequence lands while they still remember making it.
inline constexpr long long DEFAULT_HORIZON_MINUTES = 2 * 24 * 60;

/// How much MORE the promisee has to believe it happened than they did when the
/// promise was made, for it to count as kept.
///
/// A MOVEMENT, not an absolute. One first-hand confirmation moves a belief from
/// 0.500 to 0.537, so a fixed 0.55 silently required TWO independent
/// confirmations before anybody was credited with keeping a promise made to them
/// personally -- the right bar for a bystander weighing a rumour and the wrong
/// one for the person who was owed. Asking about the movement says what was
/// meant, and survives a recalibration of the belief constants that an absolute
/// number would not.
inline constexpr double KEPT_MARGIN = 0.002;

/// A cap on how many open promises one character carries. A bound on save size
/// rather than a claim about human nature; the oldest goes first.
inline constexpr std::size_t MAX_OPEN_PER_AGENT = 24;

struct Promise {
    std::string promise_id;
    std::string promiser;
    std::string promisee;
    std::string key;
    long long made_at = 0;
    long long due_at = 0;
    std::vector<std::string> witnesses;
    /// What the promisee already believed when it was made.
    double promisee_prior = 0.5;
    std::string state = "open";      // open | kept | broken
    Json resolved_at;

    Json as_json() const {
        Json out = Json::object();
        out["promise_id"] = promise_id;
        out["promiser"] = promiser;
        out["promisee"] = promisee;
        out["proposition"] = key;
        out["made_at"] = made_at;
        out["due_at"] = due_at;
        Json heard = Json::array();
        for (const std::string& one : witnesses) heard.push(Json(one));
        out["witnesses"] = heard;
        out["promisee_prior"] = py_round(promisee_prior, 6);
        out["state"] = state;
        out["resolved_at"] = resolved_at;
        return out;
    }
};

using PromiseReason = Reason;

/// What the ledger needs from the rest of the runtime to settle one.
///
/// The deltas are NOT invented here: `SocialExchangeEngine` has always known
/// what a kept and a broken promise are worth, and the owners in
/// `relationship.hpp` are still the only things that write the state.
struct PromiseRuntime {
    SocialExchangeEngine exchange;
    RelationshipEngine relationship;
    ReputationEngine reputation;
};

class PromiseLedger {
public:
    static constexpr const char* MODULE_ID = "promises";

    /// The three numbers a world pack may set. Members rather than the
    /// `constexpr` constants above, which cannot be written at run time -- and a
    /// knob that cannot be written is a knob a pack sets in vain. The constants
    /// stay as the defaults, so each value is still stated exactly once.
    struct Params {
        long long horizon_minutes = DEFAULT_HORIZON_MINUTES;
        double kept_margin = KEPT_MARGIN;
        long long max_open_per_agent = static_cast<long long>(MAX_OPEN_PER_AGENT);
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("horizon_minutes", &Params::horizon_minutes),
            knob("kept_margin", &Params::kept_margin),
            knob("max_open_per_agent", &Params::max_open_per_agent),
        };
        return table;
    }

    PromiseLedger() = default;
    explicit PromiseLedger(bool enabled) : enabled_(enabled) {}

    const Params& params() const { return params_; }
    Params& params() { return params_; }
    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }

    /// A `promise` event becomes something that will be checked.
    ///
    /// `witnesses` come from the perception layer rather than being recomputed,
    /// so this cannot come to disagree with the rest of the runtime about who
    /// was there.
    std::vector<PromiseReason> record(const World& world, const Event& event,
                                      const std::vector<std::string>& witnesses) {
        if (!enabled_ || event.type != "promise") return {};
        std::optional<Proposition> proposition = event.proposition();
        if (!proposition) return {};

        std::string promiser = event.actor.is_null() ? "" : event.actor.py_str();
        const Json* target = event.payload.find("target");
        if (!target || target->is_null()) target = event.payload.find("addressee");
        std::string promisee = (target && !target->is_null()) ? target->py_str() : "";
        // A promise to nobody in particular is a statement of intent, and this
        // layer has nothing to say about those.
        if (promiser.empty() || promisee.empty() || promiser == promisee) return {};

        // When it comes due: what the promise itself says, or the default. A
        // proposition that names its own end is the author being explicit, and
        // that should win over any constant in this file.
        long long due = world.world_time + params_.horizon_minutes;
        // `if stated_end:` -- truthiness, so a `valid_end` of 0 falls through to
        // the horizon rather than making the promise due at the dawn of time.
        if (proposition->valid_end.is_number() && proposition->valid_end.as_int() != 0)
            due = proposition->valid_end.as_int();

        double prior = 0.5;
        const Agent* listener = world.agents.find(promisee);
        if (listener) {
            const Belief* held = listener->beliefs.find(proposition->core_key());
            if (held) prior = held->expected_prob();
        }

        ++counter_;
        Promise promise;
        promise.promise_id = "promise_" + std::to_string(counter_);
        promise.promiser = promiser;
        promise.promisee = promisee;
        promise.key = proposition->core_key();
        promise.made_at = world.world_time;
        promise.due_at = due;
        promise.promisee_prior = prior;
        std::set<std::string> heard(witnesses.begin(), witnesses.end());
        heard.insert(promiser);
        heard.insert(promisee);
        promise.witnesses.assign(heard.begin(), heard.end());
        open_.push_back(promise);
        trim(promiser);

        Json detail = Json::object();
        detail["promise"] = promise.promise_id;
        detail["by"] = promiser;
        detail["to"] = promisee;
        detail["proposition"] = promise.key;
        detail["due_at"] = due;
        Json who = Json::array();
        for (const std::string& one : promise.witnesses) who.push(Json(one));
        detail["heard_by"] = who;
        return {{"promise.made", 1.0, detail}};
    }

    /// The game says what happened. The authoritative path.
    ///
    /// A studio that scripts "the player hands over the money" should not have
    /// to hope an NPC was paying attention: it knows, and this is how it says
    /// so. Everything downstream is identical to a promise that came due on its
    /// own -- same deltas, same reputation, same witnesses.
    std::vector<PromiseReason> settle(World& world, PromiseRuntime& runtime,
                                      const std::string& promise_id, bool kept,
                                      const std::string& note = "") {
        if (!enabled_) return {};
        auto found = std::find_if(open_.begin(), open_.end(),
                                  [&](const Promise& one) {
                                      return one.promise_id == promise_id;
                                  });
        if (found == open_.end())
            throw std::out_of_range("no open promise with id " + promise_id);
        Promise promise = *found;
        open_.erase(found);
        return resolve(world, runtime, promise, &kept, note);
    }

    std::vector<std::string> open_ids() const {
        std::vector<std::string> ids;
        for (const Promise& one : open_) ids.push_back(one.promise_id);
        return ids;
    }

    /// Settle whatever has come due, and let it cost or earn something.
    std::vector<PromiseReason> step(World& world, PromiseRuntime& runtime,
                                    long long delta_minutes) {
        if (!enabled_ || delta_minutes <= 0) return {};
        std::vector<PromiseReason> reasons;
        std::vector<Promise> still_open;
        for (const Promise& promise : open_) {
            if (world.world_time < promise.due_at) { still_open.push_back(promise); continue; }
            Promise copy = promise;
            for (PromiseReason& row : resolve(world, runtime, copy, nullptr, ""))
                reasons.push_back(std::move(row));
        }
        open_ = still_open;
        return reasons;
    }

    std::vector<Json> owed_by(const std::string& agent_id) const {
        std::vector<Json> out;
        for (const Promise& one : open_)
            if (one.promiser == agent_id) out.push_back(one.as_json());
        return out;
    }

    std::vector<Json> owed_to(const std::string& agent_id) const {
        std::vector<Json> out;
        for (const Promise& one : open_)
            if (one.promisee == agent_id) out.push_back(one.as_json());
        return out;
    }

    Json report() const {
        Json out = Json::object();
        Json running = Json::array();
        for (const Promise& one : open_) running.push(one.as_json());
        out["open"] = running;
        Json done = Json::array();
        // `self.settled[-50:]` -- the last fifty, however many there are.
        std::size_t from = settled_.size() > 50 ? settled_.size() - 50 : 0;
        for (std::size_t i = from; i < settled_.size(); ++i)
            done.push(settled_[i].as_json());
        out["settled"] = done;
        return out;
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled_;
        out["counter"] = counter_;
        Json running = Json::array();
        for (const Promise& one : open_) running.push(one.as_json());
        out["open"] = running;
        Json done = Json::array();
        for (const Promise& one : settled_) done.push(one.as_json());
        out["settled"] = done;
        return out;
    }

    void restore(const Json& data) {
        auto build = [](const Json& row) {
            Promise one;
            one.promise_id = row.at("promise_id").py_str();
            one.promiser = row.at("promiser").py_str();
            one.promisee = row.at("promisee").py_str();
            one.key = row.at("proposition").py_str();
            const Json* made = row.find("made_at");
            one.made_at = made ? made->as_int() : 0;
            const Json* due = row.find("due_at");
            one.due_at = due ? due->as_int() : 0;
            for (const Json& who : row.at("witnesses").items())
                one.witnesses.push_back(who.py_str());
            const Json* prior = row.find("promisee_prior");
            one.promisee_prior = prior ? prior->as_double() : 0.5;
            const Json* state = row.find("state");
            one.state = (state && !state->is_null()) ? state->py_str() : "open";
            one.resolved_at = row.get("resolved_at");
            return one;
        };
        const Json* counter = data.find("counter");
        counter_ = counter ? counter->as_int() : 0;
        open_.clear();
        for (const Json& row : data.at("open").items()) open_.push_back(build(row));
        settled_.clear();
        for (const Json& row : data.at("settled").items()) settled_.push_back(build(row));
    }

private:
    void trim(const std::string& promiser) {
        std::vector<const Promise*> mine;
        for (const Promise& one : open_) if (one.promiser == promiser) mine.push_back(&one);
        // `check` refuses anything below 1, and Python's `mine[:-n]` with n == 0
        // is EMPTY rather than everything -- nothing is trimmed. Matching that.
        if (params_.max_open_per_agent <= 0) return;
        const std::size_t cap = static_cast<std::size_t>(params_.max_open_per_agent);
        if (mine.size() <= cap) return;
        std::vector<std::string> stale;
        for (std::size_t i = 0; i + cap < mine.size(); ++i)
            stale.push_back(mine[i]->promise_id);
        open_.erase(std::remove_if(open_.begin(), open_.end(),
                                   [&](const Promise& one) {
                                       return std::find(stale.begin(), stale.end(),
                                                        one.promise_id) != stale.end();
                                   }),
                    open_.end());
    }

    /// How sure the promisee is that the promised thing came about.
    double believes_it_happened(const World& world, const Promise& promise) const {
        const Agent* promisee = world.agents.find(promise.promisee);
        if (!promisee) return 0.0;
        const Belief* belief = promisee->beliefs.find(promise.key);
        return belief ? belief->expected_prob() : 0.0;
    }

    std::vector<PromiseReason> resolve(World& world, PromiseRuntime& runtime,
                                       Promise& promise, const bool* forced,
                                       const std::string& note) {
        double confidence = believes_it_happened(world, promise);
        std::string judged_by = forced ? "the engine" : "the promisee";
        bool kept = forced ? *forced
                           : (confidence - promise.promisee_prior) >= params_.kept_margin;
        promise.state = kept ? "kept" : "broken";
        promise.resolved_at = Json(world.world_time);
        settled_.push_back(promise);

        Json detail = Json::object();
        detail["promise"] = promise.promise_id;
        detail["by"] = promise.promiser;
        detail["to"] = promise.promisee;
        detail["proposition"] = promise.key;
        detail["promisee_confidence"] = py_round(confidence, 3);
        detail["was"] = py_round(promise.promisee_prior, 3);
        detail["moved"] = py_round(confidence - promise.promisee_prior, 3);
        detail["judged_by"] = judged_by;
        detail["engine_note"] = note;
        detail["note"] = note.empty()
            ? (forced ? std::string("the engine said so")
                      : std::string("judged on what the person it was made to came to "
                                    "believe, because this runtime holds no ground "
                                    "truth about whether it happened"))
            : note;
        std::vector<PromiseReason> reasons = {
            {kept ? "promise.kept" : "promise.broken", py_round(confidence, 3), detail}};

        Agent* promiser = world.agents.find(promise.promiser);
        Agent* promisee = world.agents.find(promise.promisee);
        if (!promisee || !promiser) return reasons;

        std::vector<ProposedDelta> deltas =
            runtime.exchange.on_commitment_resolved(promise.promisee, promise.promiser, kept);
        std::vector<ProposedDelta> relationship_deltas, reputation_deltas;
        for (const ProposedDelta& delta : deltas) {
            if (delta.key.module == "relationship") relationship_deltas.push_back(delta);
            else if (delta.key.module == "reputation") reputation_deltas.push_back(delta);
        }

        std::vector<RelationshipReason> applied;
        runtime.relationship.apply(*promisee, relationship_deltas, applied);
        runtime.reputation.apply(*promisee, reputation_deltas, applied);

        // Everyone who heard it made also sees it come to nothing. NOT the town:
        // a broken promise is not news, it is a disappointment, and it reaches
        // the people for whom it was a promise in the first place.
        for (const std::string& witness_id : promise.witnesses) {
            if (witness_id == promise.promisee || witness_id == promise.promiser) continue;
            Agent* witness = world.agents.find(witness_id);
            if (!witness) continue;
            runtime.reputation.apply(*witness, reputation_deltas, applied);
        }
        for (const RelationshipReason& row : applied)
            reasons.push_back({row.code, row.amount, row.detail});
        return reasons;
    }

    bool enabled_ = false;
    Params params_;
    std::vector<Promise> open_;
    std::vector<Promise> settled_;
    long long counter_ = 0;
};

}  // namespace usc
