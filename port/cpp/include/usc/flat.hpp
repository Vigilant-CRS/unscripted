// `usc/flat.py`. Flags: the way NPC knowledge is normally represented,
// implemented honestly.
//
// Before/after comparisons in technical marketing are usually rigged, and the
// reader who can tell is the one whose opinion decides the sale. So this is not
// a competitor, not a reconstruction of anybody's product, and not a
// deliberately weak thing built to lose. It is A SET OF BOOLEANS -- the
// representation most shipped games actually use -- with the source sitting next
// to the thing it is compared against.
//
//     if (worldFlags.contains("player_attacked_market")) { ... }
//
// That is the whole model, and it is not stupid. It is fast, it saves and loads,
// every designer understands it, and it has shipped a thousand games. The
// comparison is never "flags are bad". It is a list of questions and which of
// the two can ANSWER them -- and every entry where flags cannot is a structural
// fact about booleans, not an opinion about anyone's craft.
//
// Two variants exist in the wild and this implements the common one: global
// flags, where a broadcast sets a fact and the cast then "knows" it. The other
// -- per-character flags with authored propagation -- is strictly better and its
// authoring cost grows with the SQUARE of the cast, which is why most games have
// three characters who react and forty who do not. Not modelled, and said so
// rather than quietly taking credit for the difference.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

/// One boolean per fact, plus who has been told, which is the generous version.
class FlatWorld {
public:
    /// Set the flag. Returns whether anything changed -- usually nothing does.
    bool learn(const std::string& agent_id, const std::string& fact) {
        std::set<std::string>& held = known_[agent_id];
        if (held.count(fact)) return false;
        held.insert(fact);
        facts_.insert(fact);
        return true;
    }

    /// A channel fires. Everyone gets the flag.
    ///
    /// This is the behaviour, not a caricature of it: a boolean has no field for
    /// who was listening, so a global fact set at a moment is set for everybody
    /// who can read it. Attention, distance and whether a character was even in
    /// the room are not representable.
    long long broadcast(const std::string& fact,
                        const std::vector<std::string>& agents) {
        long long changed = 0;
        for (const std::string& agent_id : agents)
            if (learn(agent_id, fact)) ++changed;
        return changed;
    }

    bool tell(const std::string& speaker, const std::string& listener,
              const std::string& fact, bool honest = true) {
        Json row = Json::object();
        row["from"] = speaker;
        row["to"] = listener;
        row["fact"] = fact;
        row["honest"] = honest;
        // Every telling is recorded, so this model is not accused of throwing
        // away information it was handed. It records the event; it just has
        // nowhere to USE it -- the flag is the same boolean either way.
        tellings_.push_back(row);
        return learn(listener, fact);
    }

    // ------------------------------------------------ the questions asked ----
    //
    // Each returns either an answer or nothing, and nothing means "there is
    // nowhere in this representation to hold that", which is the finding.

    std::vector<std::string> who_knows(const std::string& fact) const {
        std::vector<std::string> out;
        for (const auto& entry : known_)
            if (entry.second.count(fact)) out.push_back(entry.first);
        std::sort(out.begin(), out.end());
        return out;
    }

    /// A boolean has two states, and neither of them is "fairly sure".
    std::string how_sure(const std::string& agent_id, const std::string& fact) const {
        const std::set<std::string>* held = known_.find(agent_id);
        return (held && held->count(fact)) ? "knows it" : "does not";
    }

    /// Nothing. The flag does not record where it came from.
    Json who_told(const std::string&, const std::string&) const { return Json(); }

    /// Nothing. There is one fact; a version that changed on the way is the same
    /// boolean, or a different fact nobody authored.
    Json which_version(const std::string&, const std::string&) const { return Json(); }

    /// A boolean cannot be set twice. Repetition is invisible by construction.
    Json told_how_often(const std::string&, const std::string&) const { return Json(); }

    /// Nothing. A lie and an honest report set the identical flag.
    Json was_it_a_lie(const std::string&, const std::string&) const { return Json(); }

    /// Nothing changes. There is no edge from a flag back to who caused it.
    ///
    /// THE ONE THAT COSTS A GAME THE MOST: exposing a liar cannot undo what he
    /// convinced people of, because nothing recorded that he was the reason
    /// anybody believes it. The flag stays set.
    long long discredit(const std::string&) const { return 0; }

    /// None do. Flags do not decay, which is why an NPC can quote something from
    /// forty hours of play ago as though it happened this morning.
    long long forgets() const { return 0; }

    const std::set<std::string>& facts() const { return facts_; }
    const std::vector<Json>& tellings() const { return tellings_; }

    Json as_json() const {
        Json out = Json::object();
        Json all = Json::array();
        for (const std::string& one : facts_) all.push(Json(one));
        out["facts"] = all;
        Json who = Json::object();
        for (const auto& entry : known_) {
            Json held = Json::array();
            for (const std::string& one : entry.second) held.push(Json(one));
            who.fields()[entry.first] = held;
        }
        out["known"] = who;
        Json told = Json::array();
        for (const Json& one : tellings_) told.push(one);
        out["tellings"] = told;
        return out;
    }

private:
    std::set<std::string> facts_;
    /// Kept per character rather than purely global, so the comparison is
    /// against the better of the two common practices rather than the worse.
    OrderedMap<std::set<std::string>> known_;
    std::vector<Json> tellings_;
};

/// Play the same events through the flag model.
///
/// `tellings` is the transmission list from the same recording the runtime
/// produced, so both sides see the identical sequence. What differs is only what
/// each representation can do with them.
inline FlatWorld run_flat(const Json& scenario_events, const std::string& predicate,
                          const std::vector<Json>& tellings,
                          const std::vector<std::string>& agents) {
    FlatWorld flat;
    for (const Json& event : scenario_events.items()) {
        const Json* payload = event.find("payload");
        if (!payload) continue;
        const Json& proposition = payload->at("proposition");
        const Json* named = proposition.find("predicate");
        if (named && named->py_str() == predicate) flat.broadcast(predicate, agents);
    }
    for (const Json& telling : tellings) {
        const Json* lie = telling.find("lie");
        flat.tell(telling.at("from").py_str(), telling.at("to").py_str(), predicate,
                  !(lie && lie->as_bool()));
    }
    return flat;
}

}  // namespace usc
