// `usc/pursuit.py`. Somebody wants something, so somebody does something.
//
// The tick has five steps and until this existed none of them asked what anybody
// wanted. Characters have goals -- file the story first, close the case, not be
// arrested for this -- and nothing in a time advance ever consulted one. The
// evidence run says what that cost:
//
//     After saturation, little happens. The rumours are through the population
//     within days, everyone becomes a stifler, and the world goes quiet.
//
// A world that goes quiet is not a living one. It is a stable one, which is a
// different and lesser claim.
//
// DIFFUSION IS WHO HAPPENS TO TALK. PURSUIT IS WHO HAS A REASON TO. That is the
// whole distinction, and why this is a separate module rather than a weight
// inside the other: the same act is chosen by a different question. Diffusion
// asks who is here; pursuit asks who needs this said, and to whom.
//
// It invents no new channel. A pursued conversation is an ordinary claim event
// through the ordinary perception path, with the ordinary earshot, provenance,
// distortion and hop count. What changes is which conversation happens.
#pragma once

#include <algorithm>
#include <tuple>
#include <cctype>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/determinism.hpp"
#include "usc/diffusion.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/medium.hpp"
#include "usc/notes.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

/// How often a character with a maximal goal will go and raise it. Deliberately
/// slow: a cast that acts on its goals every twenty minutes is not alive, it is
/// frantic, and it saturates the world faster than the diffusion layer it is
/// meant to complement.
inline constexpr double BASE_INTERVAL_MINUTES = 180.0;

/// Words that carry no information about what a goal is about.
inline const std::set<std::string>& stopwords() {
    static const std::set<std::string> words = {
        "the", "a", "an", "of", "to", "for", "and", "or", "not", "be", "is", "it",
        "this", "that", "my", "his", "her", "their", "out", "in", "on", "at", "with",
        "keep", "get", "make", "next", "first", "own", "up", "down", "about"};
    return words;
}

/// The words in a goal that could name something in the world.
///
/// `re.findall(r"[a-z_]+", text.lower())` -- so a digit or a colon SPLITS a
/// token rather than joining it, and `agent:vee` yields `agent` and `vee`.
inline std::set<std::string> keywords(const std::string& text) {
    std::set<std::string> found;
    std::string current;
    auto flush = [&] {
        if (current.size() > 2 && !stopwords().count(current)) found.insert(current);
        current.clear();
    };
    for (char raw : text) {
        char c = static_cast<char>(std::tolower(static_cast<unsigned char>(raw)));
        if ((c >= 'a' && c <= 'z') || c == '_') current += c;
        else flush();
    }
    flush();
    return found;
}

using PursuitReason = Reason;

/// What pursuit reaches through the runtime for.
struct PursuitRuntime {
    DiffusionEngine* diffusion = nullptr;
    DiffusionRuntime* diffusion_runtime = nullptr;
    NoteBoard* notes = nullptr;
    NoteRuntime* note_runtime = nullptr;
};

class PursuitEngine {
public:
    struct Params {
        double interval_minutes = BASE_INTERVAL_MINUTES;
        /// A character will not go and raise something they are unsure of:
        /// pursuit is for what you believe, not for what you suspect.
        double min_confidence = 0.55;
        long long max_per_tick = 12;
        /// How much MORE somebody elsewhere has to be trusted before a character
        /// reaches for the phone instead of talking to whoever is here. An
        /// absolute floor was the wrong shape: the default trust between two
        /// people who have never met is 0.3, so any floor above it sent
        /// everybody to the phone and turned a market square into a call centre.
        double worth_a_call = 0.12;
        /// And before writing it down. Larger on purpose: ringing somebody is
        /// easy and writing to somebody is a decision.
        double worth_writing = 0.20;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("interval_minutes", &Params::interval_minutes),
            knob("min_confidence", &Params::min_confidence),
            knob("max_per_tick", &Params::max_per_tick),
            knob("worth_a_call", &Params::worth_a_call),
            knob("worth_writing", &Params::worth_writing),
        };
        return table;
    }

    static constexpr const char* MODULE_ID = "pursuit";

    PursuitEngine() = default;
    PursuitEngine(bool enabled, bool media) : enabled_(enabled), media_(media) {}
    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }
    void set_notes(bool on) { notes_ = on; }
    void set_media(bool on) { media_ = on; }
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// Let whoever is due act on a goal, once each.
    std::vector<PursuitReason> step(World& world, PursuitRuntime& runtime,
                                    long long delta_minutes,
                                    const std::string& player_id = "") {
        if (!enabled_ || delta_minutes <= 0) return {};

        OrderedMap<std::vector<Agent*>> by_place;
        for (auto& entry : world.agents) {
            Agent& agent = entry.second;
            if (!player_id.empty() && agent.id == player_id) continue;
            if (agent.location().is_null() || agent.location().py_str().empty()) continue;
            by_place[agent.location().py_str()].push_back(&agent);
        }

        std::vector<std::string> places;
        for (const auto& entry : by_place) places.push_back(entry.first);
        std::sort(places.begin(), places.end());

        std::vector<PursuitReason> reasons;
        long long acted = 0;
        for (const std::string& place_id : places) {
            std::vector<Agent*> occupants = *by_place.find(place_id);
            std::sort(occupants.begin(), occupants.end(),
                      [](const Agent* a, const Agent* b) { return a->id < b->id; });
            // Somebody alone in a room used to be skipped outright, which was
            // right while the only thing pursuit could do was speak. It is
            // exactly wrong once it can write: a person with something to say
            // and nobody to say it to IS the note case, and it was the only case
            // that never reached the code for it.
            if (occupants.size() < 2 && !notes_) continue;

            for (Agent* agent : occupants) {
                if (acted >= params_.max_per_tick) return reasons;
                if (!due(*agent, world.world_time)) continue;

                std::set<std::string> wanted = wants(*agent);
                if (wanted.empty()) continue;
                std::string key = relevant(*agent, wanted);
                if (key.empty()) continue;

                auto [listener, medium] = pick_listener(*agent, occupants, world);

                // THE PERSON THEY ACTUALLY NEEDED. `pick_listener` answers "who
                // can I reach", which is right for a conversation and wrong for
                // a note: nobody writes to the person standing next to them. So
                // ask the other question too -- who did they most want this to
                // get to -- and if that person is out of reach entirely, they
                // leave word where they are and hope.
                if (notes_) {
                    Agent* wanted_them = out_of_reach(*agent, world, listener);
                    if (wanted_them) {
                        std::vector<std::uint8_t> seed = derive_seed(
                            world.global_seed, agent->id, wanted_them->id,
                            world.world_time, MODULE_ID, "write");
                        if (seeded_uniform(seed) < 0.5)
                            leave_word(runtime, world, *agent, wanted_them->id,
                                       key, place_id, reasons);
                    }
                }

                if (!listener) {
                    last_acted_[agent->id] = world.world_time;
                    continue;
                }

                // Even a due character does not always speak. The draw is
                // seeded, so a replay of the same world produces the same
                // conversations.
                std::vector<std::uint8_t> seed = derive_seed(
                    world.global_seed, agent->id, world.world_time, place_id,
                    MODULE_ID);
                if (seeded_uniform(seed) > 0.75) {
                    last_acted_[agent->id] = world.world_time;
                    continue;
                }

                bool told = false;
                if (runtime.diffusion && runtime.diffusion_runtime) {
                    std::vector<DiffusionReason> spoken;
                    told = runtime.diffusion->tell_about(world, *runtime.diffusion_runtime,
                                                         *agent, *listener, place_id,
                                                         key, spoken, medium);
                    for (const DiffusionReason& row : spoken)
                        reasons.push_back({row.code, row.amount, row.detail});
                }
                last_acted_[agent->id] = world.world_time;
                if (!told) continue;

                ++acted;
                Json detail = Json::object();
                detail["agent"] = agent->id;
                detail["listener"] = listener->id;
                detail["place"] = place_id;
                detail["about"] = key;
                detail["medium"] = medium ? medium->name : std::string("in_person");
                detail["goal"] = agent->goals.empty()
                    ? std::string() : agent->goals.front().at("content").py_str();
                reasons.push_back({"pursuit.acted", 1.0, detail});
            }
        }
        return reasons;
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled_;
        Json when = Json::object();
        for (const auto& entry : last_acted_) when.fields()[entry.first] = Json(entry.second);
        out["last_acted"] = when;
        return out;
    }

    void restore(const Json& data) {
        last_acted_.clear();
        const Json* rows = data.find("last_acted");
        if (!rows) return;
        for (const auto& entry : rows->fields())
            last_acted_[entry.first] = entry.second.as_int();
    }

private:
    bool due(const Agent& agent, long long world_time) const {
        if (agent.goals.empty()) return false;
        double priority = 0.0;
        bool first = true;
        for (const Json& goal : agent.goals) {
            const Json* declared = goal.find("priority");
            double value = declared ? declared->as_double() : 0.5;
            if (first || value > priority) { priority = value; first = false; }
        }
        if (priority <= 0.0) return false;
        // A stronger goal comes round sooner. Priority 1.0 acts every three
        // hours; priority 0.5 every six.
        double interval = params_.interval_minutes / std::max(0.05, priority);
        const long long* last = last_acted_.find(agent.id);
        // Python's default is -10**9, which is not merely "long ago" -- it is
        // chosen so a world starting at time 0 has everybody due at once.
        long long since = world_time - (last ? *last : -1000000000LL);
        return static_cast<double>(since) >= interval;
    }

    /// What this character's goals are about, as words to match beliefs on.
    ///
    /// A goal may say so precisely with `about`, naming predicates or entity
    /// ids. Where it does not, the words of the goal itself are used --
    /// imprecise, and better than the alternative, which is a layer that only
    /// works for packs written after it.
    std::set<std::string> wants(const Agent& agent) const {
        std::set<std::string> wanted;
        for (const Json& goal : agent.goals) {
            for (const Json& named : goal.at("about").items())
                for (const std::string& word : keywords(named.py_str())) wanted.insert(word);
            const Json* content = goal.find("content");
            if (content)
                for (const std::string& word : keywords(content->py_str())) wanted.insert(word);
        }
        return wanted;
    }

    /// The belief this character would most want raised, or nothing.
    ///
    /// RELEVANCE FIRST, conviction second. Somebody trying not to be arrested
    /// raises the thing that bears on being arrested, not the thing they happen
    /// to be surest about.
    std::string relevant(const Agent& agent, const std::set<std::string>& wanted) const {
        std::string best;
        double best_score = 0.0;
        for (const auto& entry : agent.beliefs) {
            double probability = entry.second.expected_prob();
            double confidence = std::max(probability, 1.0 - probability);
            if (confidence < params_.min_confidence) continue;
            std::set<std::string> in_key = keywords(entry.first);
            std::size_t overlap = 0;
            for (const std::string& word : wanted) if (in_key.count(word)) ++overlap;
            if (overlap == 0) continue;
            double score = static_cast<double>(overlap) + confidence;
            // Strictly greater, so the FIRST belief at a tied score wins -- and
            // the beliefs are in insertion order.
            if (score > best_score) { best = entry.first; best_score = score; }
        }
        return best;
    }

    /// Whom to say it to: the person they trust most who they can reach.
    std::pair<Agent*, const Medium*> pick_listener(const Agent& agent,
                                                   const std::vector<Agent*>& occupants,
                                                   World& world) const {
        auto strongest = [&](const std::vector<Agent*>& pool, bool media) {
            Agent* best = nullptr;
            double best_trust = -1.0;
            const Medium* best_medium = nullptr;
            for (Agent* other : pool) {
                if (other->id == agent.id) continue;
                const Medium* medium = for_exchange(agent, *other, media);
                if (!medium) continue;
                double trust = agent.trust_in(other->id);
                // On a TIE the lower id wins -- and only when there is already a
                // best, which is what the Python's `best is not None` guards.
                if (trust > best_trust
                    || (trust == best_trust && best && other->id < best->id)) {
                    best = other;
                    best_trust = trust;
                    best_medium = medium;
                }
            }
            return std::make_tuple(best, best_trust, best_medium);
        };

        auto [here, here_trust, here_medium] = strongest(occupants, media_);
        if (!media_) return {here, here_medium};

        // THE PHONE IS A FALLBACK, NOT A PREFERENCE. Somebody with something to
        // say goes to whoever is standing there if that person is worth telling,
        // and rings somebody else when they are not. Ranking every contact in
        // the world against the room turned five days into ninety-eight phone
        // calls and thirty-four conversations, which is not a market square.
        std::vector<Agent*> away;
        for (auto& entry : world.agents)
            if (entry.second.location().py_str() != agent.location().py_str())
                away.push_back(&entry.second);
        std::sort(away.begin(), away.end(),
                  [](const Agent* a, const Agent* b) { return a->id < b->id; });

        auto [called, called_trust, called_medium] = strongest(away, true);
        if (called && called_trust >= here_trust + params_.worth_a_call)
            return {called, called_medium};
        return {here, here_medium};
    }

    /// The person they most wanted to tell, if they cannot be told.
    ///
    /// Out of reach means both things at once: not in this room, and not on the
    /// end of a telephone. Somebody they could simply have rung is not somebody
    /// they would write to.
    Agent* out_of_reach(const Agent& agent, World& world, const Agent* reachable) const {
        double floor = reachable ? agent.trust_in(reachable->id) : 0.0;
        floor += params_.worth_writing;
        // Having somebody's number only puts them in reach if telephones exist
        // in this world at all. With media off there is nothing to ring, and
        // everybody outside the room is equally out of reach -- which is when a
        // note stops being a curiosity and becomes the only way to reach anyone.
        std::set<std::string> contacts;
        if (media_) contacts = contacts_of(agent);

        std::vector<Agent*> everybody;
        for (auto& entry : world.agents) everybody.push_back(&entry.second);
        std::sort(everybody.begin(), everybody.end(),
                  [](const Agent* a, const Agent* b) { return a->id < b->id; });

        Agent* best = nullptr;
        double best_trust = floor;
        for (Agent* other : everybody) {
            if (other->id == agent.id) continue;
            if (other->location().py_str() == agent.location().py_str()) continue;
            if (contacts.count(other->id)) continue;
            double trust = agent.trust_in(other->id);
            if (trust > best_trust) { best = other; best_trust = trust; }
        }
        return best;
    }

    bool leave_word(PursuitRuntime& runtime, const World& world, const Agent& agent,
                    const std::string& recipient_id, const std::string& key,
                    const std::string& place_id, std::vector<PursuitReason>& reasons) {
        if (!runtime.notes || !runtime.notes->enabled() || !runtime.note_runtime)
            return false;
        std::vector<NoteReason> written;
        bool ok = runtime.notes->leave(world, agent, recipient_id, place_id, key,
                                       agent.beliefs.find(key), *runtime.note_runtime,
                                       written);
        for (const NoteReason& row : written)
            reasons.push_back({row.code, row.amount, row.detail});
        return ok;
    }

    bool enabled_ = false;
    /// Whether somebody may reach beyond the room they are standing in.
    bool media_ = false;
    /// Whether somebody who can reach nobody writes it down instead.
    bool notes_ = false;
    Params params_;
    /// When each character last acted, so a long time skip does not produce a
    /// week of conversations in one step.
    OrderedMap<long long> last_acted_;
};

}  // namespace usc
