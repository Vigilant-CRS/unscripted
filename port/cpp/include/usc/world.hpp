// `usc/world.py` -- the container, not yet the loader.
//
// This grows as the port does. What is here is what a ported module actually
// reads, and nothing has been added speculatively: a half-finished port holding
// fields nothing maintains would look further along than it is, and the whole
// value of this exercise is that its state is legible.
//
// The pack LOADER is not here. It parses a directory of JSON into these fields,
// and it belongs with the rest of the world layer -- but a port that can load a
// pack and cannot yet simulate one is the wrong order to build in. The probes
// construct a world directly, which is also what the conformance fixtures will
// need.
#pragma once

#include <algorithm>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"

namespace usc {

struct World {
    std::string global_seed = "unscripted-seed-0";
    long long world_time = 0;
    /// place id -> attributes (noise_level, label, exits, ...)
    Json places = Json::object();
    Json entities = Json::object();
    Json channels = Json::object();
    OrderedMap<Agent> agents;
    /// (agent id, channel) -> {attention}. Python keys this with a TUPLE, which
    /// JSON cannot express, so the two halves are joined with a separator that
    /// cannot occur in an id. The joining is confined to `exposure()` so no
    /// caller has to know it happens.
    OrderedMap<Json> media_exposure;
    Json identity_values = Json::object();
    std::vector<std::string> focus_agents;
    std::string player_start;
    /// What this world IS, as opposed to what it currently contains. Authored
    /// in `scenario.json: world_id`; empty means the loader falls back to
    /// comparing the cast and the map.
    std::string world_id;
    Json predicate_domains = Json::object();
    Json predicate_competence = Json::object();
    /// The raw predicate declarations, for the knowledge-topology layer: what
    /// class a claim is, who may circulate it, where, and how readily.
    Json predicates = Json::object();
    OrderedMap<Topic> topics;
    /// Words a pack adds to the engine's command lexicon, per intent. It may
    /// extend or replace the words; it may NOT invent an intent, because the
    /// catalogue the SDK validates against is closed.
    Json command_aliases = Json::object();
    /// What a garment does to the room. Also the parser's only vocabulary of
    /// things to wear.
    Json appearance_reactions = Json::object();
    /// Ordinary furniture a character may refer to without asserting it into
    /// existence -- this world's additions to the engine's generic nouns.
    Json decorative_vocabulary;
    /// A pack's own stance templates, per act and register. Merged over the
    /// engine's, never replacing the whole table.
    Json dialogue_templates = Json::object();
    /// word -> what this world's in-group says instead.
    Json slang_lexicon = Json::object();
    /// Authored events waiting for their minute. The runtime fires whatever
    /// falls inside a time advance and REMOVES it, which is why this is a plain
    /// list and not a queue: the director appends to it during the same tick.
    std::vector<Event> scenario_events;
    /// Raw faction declarations, for the director.
    std::vector<Json> factions;
    /// Which predicates count as conduct, and what they cost -- world content,
    /// because what a town holds against you is a fact about the town.
    Json standing_conduct;
    /// Where the pack was read from. Informational.
    std::string pack_path;
    Json diffusion_params = Json::object();
    Json routine_params = Json::object();
    Json tuning = Json::object();
    Json canon_facts;
    Json initial_beliefs;
    std::string scenario_intro;

    /// Display name for a place; falls back to the id so an unlabelled pack
    /// still runs.
    std::string place_label(const std::string& place_id) const {
        const Json* place = places.find(place_id);
        const Json* label = place ? place->find("label") : nullptr;
        return (label && label->truthy()) ? label->py_str() : place_id;
    }

    std::vector<std::string> exits_from(const std::string& place_id) const {
        std::vector<std::string> out;
        const Json* place = places.find(place_id);
        const Json* exits = place ? place->find("exits") : nullptr;
        if (exits) for (const Json& one : exits->items()) out.push_back(one.py_str());
        return out;
    }

    /// Setting formality: a police post is formal and a back room is not, IN
    /// THIS WORLD. Authored per place rather than tabulated in the engine,
    /// because which rooms are formal is a fact about a setting.
    double place_formality(const Json& place_id, double fallback = 0.4) const {
        const Json* place = places.find(place_id.py_str());
        if (!place || place->kind() != Json::Kind::Object) return fallback;
        const Json* declared = place->find("formality");
        return (!declared || declared->is_null()) ? fallback : declared->as_double();
    }

    // ---- the authored vocabulary, indexed ----
    //
    // Rebuilt only when the roster changes -- the SDK adds the player agent at
    // startup and the generator can add characters at runtime -- so parsing a
    // line does not pay to re-sort the whole vocabulary every turn.
    const AliasIndex& place_alias_index() const {
        return cached_index(places_index_, [this] {
            Json map = Json::object();
            for (const auto& place : places.fields())
                map[place.first] = place_aliases(place.first, place.second);
            return AliasIndex::build(map);
        });
    }

    const AliasIndex& agent_alias_index() const {
        return cached_index(agents_index_, [this] {
            Json map = Json::object();
            for (const auto& entry : agents)
                map[entry.first] = agent_aliases(entry.second);
            return AliasIndex::build(map);
        });
    }

    const AliasIndex& topic_alias_index() const {
        return cached_index(topics_index_, [this] {
            Json map = Json::object();
            for (const auto& entry : topics) {
                Json names = Json::array();
                // `t.aliases or (t.topic_id,)` -- an empty alias list still
                // leaves the topic addressable by its own id.
                if (entry.second.aliases.empty()) names.push(entry.second.topic_id);
                else for (const std::string& alias : entry.second.aliases) names.push(alias);
                map[entry.second.topic_id] = names;
            }
            return AliasIndex::build(map);
        });
    }

    /// Drop the cached alias indexes. Call after adding places, agents or topics.
    void invalidate_indexes() {
        places_index_.stamp = agents_index_.stamp = topics_index_.stamp = "";
    }

    /// A fresh event id. Monotonic and never reused, because the ledger is the
    /// authoritative record and an id that came round again would merge two
    /// unrelated things in every provenance chain that cites it.
    long long new_event_id() { return ++next_event_id_; }

    /// The watermark, without consuming one. A snapshot records this so an audit
    /// tool can reconstruct the ledger as of that moment with one range query.
    long long peek_event_id() const { return next_event_id_; }
    /// Restore the watermark from a snapshot. The only way it ever moves
    /// backwards, and the only caller is the snapshot layer.
    void set_event_id(long long value) { next_event_id_ = value; }

    void set_exposure(const std::string& agent_id, const std::string& channel,
                      const Json& value) {
        media_exposure[agent_id + "\x1f" + channel] = value;
    }

    const Json* exposure(const std::string& agent_id, const std::string& channel) const {
        return media_exposure.find(agent_id + "\x1f" + channel);
    }

    /// Everyone at a place. Cached, and invalidated by any move.
    ///
    /// Perception used to scan the whole cast for every event. With hundreds of
    /// characters that is quadratic -- more people produce more events AND make
    /// each event more expensive to route -- and it was the dominant cost in a
    /// large world once persistence was out of the way.
    ///
    /// The cache is keyed on the global location epoch rather than invalidated
    /// by whoever moves somebody, so it cannot go stale no matter which of the
    /// half-dozen movers did it.
    const std::vector<Agent*>& occupants(const Json& place_id) {
        if (occupancy_epoch_ != location_epoch()) rebuild_occupancy();
        static const std::vector<Agent*> nobody;
        const std::vector<Agent*>* found = occupancy_.find(place_id.py_str());
        return found ? *found : nobody;
    }

private:
    struct CachedIndex {
        std::string stamp;
        AliasIndex index;
    };

    /// Python stamps on `(len(agents), len(places), len(topics))`, which is a
    /// count and not a hash: renaming a place without changing how many there
    /// are does NOT invalidate the index. Reproduced rather than improved, and
    /// `invalidate_indexes()` is what a caller uses when it edits in place.
    template <typename Build>
    const AliasIndex& cached_index(CachedIndex& slot, Build build) const {
        std::string stamp = std::to_string(agents.size()) + ","
                          + std::to_string(places.fields().size()) + ","
                          + std::to_string(topics.size());
        if (slot.stamp != stamp) {
            slot.index = build();
            slot.stamp = stamp;
        }
        return slot.index;
    }

    /// A pack that authored no aliases still gets a usable one from its label or
    /// id, so `go <place>` works before the vocabulary is filled in.
    ///
    /// The lower-casing here and in `agent_aliases` below is REDUNDANT and
    /// therefore not catchable: `AliasIndex::build` lowers every alias again,
    /// and lowering is idempotent. It is kept because Python has it, and a port
    /// that dropped it would be relying on a caller it does not own. The same
    /// goes for the ORDER of `public_name` and `objective_name`: the index sorts
    /// by length and then alphabetically, so which of the two is appended first
    /// cannot reach any output.
    static Json place_aliases(const std::string& place_id, const Json& attrs) {
        const Json* authored = attrs.find("aliases");
        if (authored && authored->truthy()) return *authored;
        Json names = Json::array();
        const Json* label = attrs.find("label");
        if (label && label->truthy()) {
            names.push(py_lower(label->py_str()));
        } else {
            std::string tail = place_id.substr(place_id.find(':') == std::string::npos
                                               ? 0 : place_id.find(':') + 1);
            std::replace(tail.begin(), tail.end(), '_', ' ');
            names.push(tail);
        }
        return names;
    }

    static Json agent_aliases(const Agent& agent) {
        Json names = Json::array();
        for (const std::string& alias : agent.aliases) names.push(py_lower(alias));
        if (!names.items().empty()) return names;
        // `(public_name, objective_name)` filtered by TRUTHINESS, so a name
        // authored as an empty string is no name at all.
        for (const Json* name : {&agent.public_name, &agent.objective_name})
            if (name->truthy()) names.push(py_lower(name->py_str()));
        if (!names.items().empty()) return names;
        std::string tail = agent.id.substr(agent.id.find(':') == std::string::npos
                                           ? 0 : agent.id.find(':') + 1);
        std::replace(tail.begin(), tail.end(), '_', ' ');
        names.push(tail);
        return names;
    }

    mutable CachedIndex places_index_;
    mutable CachedIndex agents_index_;
    mutable CachedIndex topics_index_;

    void rebuild_occupancy() {
        occupancy_.clear();
        for (auto& entry : agents)
            occupancy_[entry.second.location().py_str()].push_back(&entry.second);
        // Sorted by id, because "everyone here" has no natural order and a
        // seeded draw is about to be made per occupant. Ids are unique, so
        // stability does not arise.
        for (auto& bucket : occupancy_)
            std::sort(bucket.second.begin(), bucket.second.end(),
                      [](const Agent* a, const Agent* b) { return a->id < b->id; });
        occupancy_epoch_ = location_epoch();
    }

    OrderedMap<std::vector<Agent*>> occupancy_;
    long long occupancy_epoch_ = -1;
    /// 1000, not 0. Authored events in a pack occupy the low numbers, so a
    /// runtime-generated id starting at 1 would collide with them -- and the
    /// collision would show up as a provenance chain citing the wrong thing,
    /// which is nowhere near where it was caused.
    long long next_event_id_ = 1000;
};

}  // namespace usc
