// `usc/state_view.py`. The machine-readable face of the explainability.
//
// The inspector's text dumps are for terminals; this exposes the SAME internal
// state as JSON, so an engine, a debug tool or a web view can render belief
// tables, provenance, memory decay, affect, relationships, faction heat and
// per-turn reason traces. Real runtime objects, no summarisation, no mocks.
//
// The one thing missing against Python is `transmissions`, which reads the
// diffusion log out of the SQLite store. There is no store here, so the list is
// empty rather than absent -- a shape a caller can rely on either way.
#pragma once

#include <algorithm>
#include <cstdio>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "usc/affect.hpp"
#include "usc/capabilities.hpp"
#include "usc/json.hpp"
#include "usc/metahuman.hpp"
#include "usc/pyround.hpp"
#include "usc/sdk.hpp"
#include "usc/topology.hpp"

namespace usc {

namespace state_view {

namespace detail_ {

inline Json provenance_of(const Belief& belief) {
    Json out = Json::array();
    for (const ProvenanceEntry& p : belief.provenance) {
        Json row = Json::object();
        row["claim_id"] = p.claim_id;
        row["origin_event"] = p.origin_event;
        row["kappa"] = p.kappa;
        row["eta"] = p.eta;
        out.push(row);
    }
    return out;
}

inline std::string clock(long long world_time) {
    long long minute = world_time % 1440;
    char buffer[16];
    std::snprintf(buffer, sizeof buffer, "%02lld:%02lld", minute / 60, minute % 60);
    return buffer;
}

}  // namespace detail_

/// Full structured snapshot of one character's mind at the current world time.
inline Json agent_state(UnscriptedRuntime& sdk, const std::string& agent_id) {
    Runtime& core = sdk.core;
    World& world = sdk.world;
    core.catch_up(*world.agents.find(agent_id));   // LOD: realise deferred decay
    Agent& agent = *world.agents.find(agent_id);
    long long t = world.world_time;
    const AffectState& affect = agent.affect;
    OrderedMap<double> tendencies = core.affect.action_tendencies(affect);

    std::vector<Json> beliefs;
    for (const auto& entry : agent.beliefs) {
        const Belief& b = entry.second;
        Json row = Json::object();
        row["text"] = b.proposition.str();
        row["proposition"] = b.proposition.as_json();
        row["prob"] = py_round(b.expected_prob(), 4);
        row["support_for"] = py_round(b.support_for, 4);
        row["support_against"] = py_round(b.support_against, 4);
        row["ignorance"] = py_round(b.ignorance(), 4);
        row["conflict"] = py_round(b.conflict(), 4);
        row["provenance"] = detail_::provenance_of(b);
        beliefs.push_back(row);
    }
    // `key=lambda x: -max(prob, 1 - prob)` -- most settled first, and STABLE, so
    // two equally settled beliefs keep the order they were formed in.
    std::stable_sort(beliefs.begin(), beliefs.end(),
                     [](const Json& a, const Json& b) {
                         double pa = a.at("prob").as_double();
                         double pb = b.at("prob").as_double();
                         return std::max(pa, 1.0 - pa) > std::max(pb, 1.0 - pb);
                     });

    std::vector<const MemoryItem*> items;
    for (const auto& one : agent.memory) items.push_back(one.get());
    std::stable_sort(items.begin(), items.end(),
                     [t](const MemoryItem* a, const MemoryItem* b) {
                         return a->base_activation(t) > b->base_activation(t);
                     });
    Json memory = Json::array();
    for (const MemoryItem* m : items) {
        double activation = m->base_activation(t);
        Json row = Json::object();
        row["type"] = m->type;
        row["content"] = m->content;
        row["activation"] = py_round(activation, 3);
        row["status"] = std::string(activation > 0 ? "vivid"
                                  : (activation > -1.5 ? "faint" : "lost"));
        row["importance"] = py_round(m->importance, 3);
        row["valence"] = py_round(m->emotional_valence, 3);
        row["source_conf"] = py_round(m->source_conf, 3);
        memory.push(row);
    }

    // WHAT THEY THINK OF SOMEBODY, not only how they feel about them. The
    // standing layer's reputation was held in the world and reachable from
    // nowhere: a studio could not put it on screen, which is the same as it not
    // existing.
    bool warm = core.standing.enabled();
    std::set<std::string> others;
    for (const auto& entry : agent.relationships) others.insert(entry.first);
    for (const auto& entry : agent.reputation) others.insert(entry.first);

    Json relationships = Json::object();
    for (const std::string& other : others) {
        const OrderedMap<double>* rel = agent.relationships.find(other);
        Json row = Json::object();
        row["name"] = sdk.agent_name(other);
        row["trust"] = py_round(rel ? rel->get("trust", 0.0) : 0.0, 3);
        row["liking"] = py_round(rel ? rel->get("liking", 0.0) : 0.0, 3);
        row["familiarity"] = py_round(rel ? rel->get("familiarity", 0.0) : 0.0, 3);
        Json reputation = Json::object();
        const OrderedMap<double>* held = agent.reputation.find(other);
        if (held) {
            std::vector<std::string> dimensions;
            for (const auto& entry : *held) dimensions.push_back(entry.first);
            std::sort(dimensions.begin(), dimensions.end());
            for (const std::string& dimension : dimensions)
                reputation[dimension] = py_round(held->get(dimension, 0.0), 3);
        }
        row["reputation"] = reputation;
        // How much pull `other` has over the character being described. Computed,
        // never stored. The first version measured `bridge_score(agent)` -- the
        // OBSERVER's reach -- which says nothing about how much sway the other
        // one has, so every number it produced was about somebody not being asked
        // about.
        const Agent* them = world.agents.find(other);
        double reach = them ? core.network.bridge_score(*them) : 0.0;
        row["influence"] = py_round(core.standing.influence(agent, other, reach), 3);
        if (warm)
            // One number a UI can colour a character by. ABSENT when the layer is
            // off, rather than reported as zero, so nothing implies neutrality
            // where there is simply no opinion being modelled.
            row["warmth"] = py_round(core.standing.warmth(agent, other), 3);
        relationships[other] = row;
    }

    Json face = metahuman::affect_to_face(affect, &tendencies,
                                          Json(sdk.config.player_id));

    Json trace = Json::array();
    const std::vector<Reason>* reasons = core.last_traces.find(agent_id);
    if (reasons) for (const Reason& one : *reasons) {
        Json row = Json::object();
        row["code"] = one.code;
        row["magnitude"] = py_round(one.amount, 4);
        row["detail"] = one.detail;
        trace.push(row);
    }

    Json emotions = Json::object();
    for (const auto& entry : affect.active_emotions)
        emotions[entry.first] = py_round(entry.second, 3);
    Json tendency_json = Json::object();
    for (const auto& entry : tendencies) tendency_json[entry.first] = entry.second;

    Json mood = Json::object();
    mood["valence"] = py_round(affect.mood.p, 4);
    mood["arousal"] = py_round(affect.mood.a, 4);
    mood["dominance"] = py_round(affect.mood.d, 4);
    mood["baseline"] = affect.baseline.as_json();
    mood["dominant_emotion"] = face.at("emotion").at("dominant");
    mood["intensity"] = face.at("emotion").at("intensity");
    mood["stress"] = py_round(core.affect.stress(affect), 3);
    mood["active_emotions"] = emotions;
    mood["action_tendencies"] = tendency_json;

    Json listed_beliefs = Json::array();
    for (const Json& one : beliefs) listed_beliefs.push(one);
    Json goals = Json::array();
    for (const Json& one : agent.goals)
        goals.push(one.kind() == Json::Kind::Object ? one.get("content") : one);

    Json out = Json::object();
    out["id"] = agent_id;
    out["name"] = sdk.agent_name(agent_id);
    out["location"] = agent.location();
    out["affect"] = mood;
    out["face"] = face;
    out["beliefs"] = listed_beliefs;
    out["memory"] = memory;
    out["relationships"] = relationships;
    out["secrets"] = static_cast<long long>(agent.secrets.size());
    out["goals"] = goals;
    out["reason_trace"] = trace;
    return out;
}

/// Who knows what, how far from the source, and how it got there.
///
/// Built from live belief state plus the ledger, not from a separate tracking
/// structure: a second bookkeeping copy is a second thing that can be wrong.
inline Json knowledge_state(UnscriptedRuntime& sdk, long long limit = 40) {
    Runtime& core = sdk.core;
    World& world = sdk.world;

    struct Fact {
        std::string key, text, predicate;
        long long detail = 0;
        std::vector<Json> holders;
        std::set<std::string> origins;
    };
    OrderedMap<Fact> facts;
    for (const auto& who : world.agents) {
        const Agent& agent = who.second;
        for (const auto& entry : agent.beliefs) {
            const Belief& belief = entry.second;
            if (!facts.contains(entry.first)) {
                Fact fresh;
                fresh.key = entry.first;
                fresh.text = belief.proposition.str();
                fresh.predicate = belief.proposition.predicate;
                // How specific this version is: a headline names the place, a
                // witness account names the place AND the shift.
                for (const auto& slot : belief.proposition.slots)
                    if (!slot.second.is_null()) ++fresh.detail;
                facts[entry.first] = fresh;
            }
            Fact& fact = *facts.find(entry.first);
            double probability = belief.expected_prob();
            long long times_heard = 0;
            for (const auto& origin : belief.origin_counts) {
                times_heard += origin.second;
                fact.origins.insert(origin.first);
            }
            Json holder = Json::object();
            holder["agent"] = agent.id;
            holder["name"] = sdk.agent_name(agent.id);
            holder["prob"] = py_round(probability, 4);
            holder["confidence"] = py_round(std::max(probability, 1.0 - probability), 4);
            holder["hops"] = belief.hops;
            const std::string* origin = belief.primary_origin();
            holder["origin"] = origin ? Json(*origin) : Json();
            holder["times_heard"] = times_heard;
            holder["independent_origins"] =
                static_cast<long long>(belief.origin_counts.size());
            fact.holders.push_back(holder);
        }
    }

    std::vector<Json> out;
    for (auto& entry : facts) {
        Fact& fact = entry.second;
        std::stable_sort(fact.holders.begin(), fact.holders.end(),
                         [](const Json& a, const Json& b) {
                             long long ha = a.at("hops").as_int();
                             long long hb = b.at("hops").as_int();
                             if (ha != hb) return ha < hb;
                             return a.at("name").py_str() < b.at("name").py_str();
                         });
        long long first_hand = 0, max_hops = 0;
        for (const Json& holder : fact.holders) {
            if (holder.at("hops").as_int() == 0) ++first_hand;
            max_hops = std::max(max_hops, holder.at("hops").as_int());
        }
        Json row = Json::object();
        row["key"] = fact.key;
        row["text"] = fact.text;
        row["predicate"] = fact.predicate;
        row["detail"] = fact.detail;
        Json holders = Json::array();
        for (const Json& one : fact.holders) holders.push(one);
        row["holders"] = holders;
        Json origins = Json::array();
        for (const std::string& one : fact.origins) origins.push(one);
        row["origins"] = origins;
        row["reach"] = static_cast<long long>(fact.holders.size());
        row["first_hand"] = first_hand;
        row["hearsay"] = static_cast<long long>(fact.holders.size()) - first_hand;
        row["max_hops"] = max_hops;
        out.push_back(row);
    }
    // Widest spread first: that is what a designer wants to look at.
    std::stable_sort(out.begin(), out.end(), [](const Json& a, const Json& b) {
        if (a.at("reach").as_int() != b.at("reach").as_int())
            return a.at("reach").as_int() > b.at("reach").as_int();
        if (a.at("hearsay").as_int() != b.at("hearsay").as_int())
            return a.at("hearsay").as_int() > b.at("hearsay").as_int();
        return a.at("text").py_str() < b.at("text").py_str();
    });

    OrderedMap<std::vector<Json>> occupancy;
    for (const auto& entry : world.agents) {
        const Agent& agent = entry.second;
        if (!agent.location().truthy()) continue;
        Json row = Json::object();
        row["id"] = agent.id;
        row["name"] = sdk.agent_name(agent.id);
        occupancy[agent.location().py_str()].push_back(row);
    }

    // What a debug view needs in order to show the parts of the simulation that
    // were previously reachable only from Python.
    std::vector<std::string> predicate_names;
    for (const auto& entry : world.predicates.fields())
        predicate_names.push_back(entry.first);
    std::sort(predicate_names.begin(), predicate_names.end());
    Json classes = Json::array();
    for (const std::string& name : predicate_names)
        classes.push(class_of(name, world.predicates.find(name)).as_json());

    std::map<std::string, std::vector<std::string>> circle_map;
    for (const auto& entry : world.agents)
        for (const std::string& circle : circles(entry.second))
            circle_map[circle].push_back(entry.first);

    Json contested = Json::array();
    long long kept = 0;
    for (const Json& fact : out) {
        const std::vector<Json>& holders = fact.at("holders").items();
        if (holders.size() < 2) continue;
        double highest = holders.front().at("prob").as_double();
        double lowest = highest;
        for (const Json& holder : holders) {
            highest = std::max(highest, holder.at("prob").as_double());
            lowest = std::min(lowest, holder.at("prob").as_double());
        }
        double spread = highest - lowest;
        if (spread < 0.25) continue;
        Json row = Json::object();
        row["text"] = fact.at("text");
        row["disagreement"] = py_round(spread, 3);
        Json believers = Json::array(), doubters = Json::array();
        for (const Json& holder : holders) {
            if (holder.at("prob").as_double() >= 0.6) believers.push(holder.at("name"));
            if (holder.at("prob").as_double() <= 0.4) doubters.push(holder.at("name"));
        }
        row["believers"] = believers;
        row["doubters"] = doubters;
        contested.push(row);
        ++kept;
    }
    // `sort(key=lambda c: -c["disagreement"])` and then `[:limit]` -- STABLE, so
    // two equally contested claims keep the order the facts were listed in.
    {
        std::vector<Json>& rows = contested.items();
        std::stable_sort(rows.begin(), rows.end(), [](const Json& a, const Json& b) {
            return a.at("disagreement").as_double() > b.at("disagreement").as_double();
        });
        if (static_cast<long long>(rows.size()) > limit)
            rows.resize(static_cast<std::size_t>(limit));
    }
    (void)kept;

    Json judgements = Json::array();
    for (const auto& entry : world.agents) {
        const Agent& agent = entry.second;
        for (const auto& item : agent.memory) {
            if (item->type != "judgement") continue;
            Json row = Json::object();
            row["holder"] = agent.id;
            row["holder_name"] = sdk.agent_name(agent.id);
            std::string about = item->about.empty() ? std::string() : item->about.front();
            row["about"] = about.empty() ? Json() : Json(about);
            row["about_name"] = about.empty() ? Json() : Json(sdk.agent_name(about));
            row["text"] = item->content;
            row["occasions"] = item->episodes;
            Json evidence = Json::array();
            for (const std::string& one : item->evidence) evidence.push(one);
            row["evidence"] = evidence;
            judgements.push(row);
        }
    }

    // ONE INCIDENT, SEVERAL VERSIONS OF IT. A radio headline reaches everybody
    // and says little; a witness holds the detail and only they do; a witness who
    // could not read the scene holds something wrong. All three trace to the same
    // origin, and the runtime has always known that -- it simply never said so,
    // so a view saw three unrelated facts where there is one story.
    OrderedMap<std::vector<Json>> stories;
    for (const Json& fact : out) {
        for (const Json& origin : fact.at("origins").items()) {
            Json version = Json::object();
            version["text"] = fact.at("text");
            version["predicate"] = fact.at("predicate");
            version["detail"] = fact.at("detail");
            version["reach"] = fact.at("reach");
            version["first_hand"] = fact.at("first_hand");
            Json held = Json::array();
            for (const Json& holder : fact.at("holders").items())
                held.push(holder.at("name"));
            version["held_by"] = held;
            stories[origin.py_str()].push_back(version);
        }
    }
    std::vector<Json> story_list;
    for (auto& entry : stories) {
        std::vector<Json>& versions = entry.second;
        std::stable_sort(versions.begin(), versions.end(),
                         [](const Json& a, const Json& b) {
                             if (a.at("reach").as_int() != b.at("reach").as_int())
                                 return a.at("reach").as_int() > b.at("reach").as_int();
                             return a.at("text").py_str() < b.at("text").py_str();
                         });
        if (versions.size() < 2) continue;   // one version is a fact, not a story
        const Json& widest = versions.front();
        // `max(key=(detail, first_hand))` -- the FIRST maximum, so a tie keeps
        // the widest-known version rather than the last one examined.
        const Json* richest = &versions.front();
        for (const Json& one : versions) {
            long long detail = one.at("detail").as_int();
            long long best_detail = richest->at("detail").as_int();
            if (detail > best_detail
                || (detail == best_detail
                    && one.at("first_hand").as_int() > richest->at("first_hand").as_int()))
                richest = &one;
        }
        Json row = Json::object();
        row["origin"] = entry.first;
        Json listed = Json::array();
        for (const Json& one : versions) listed.push(one);
        row["versions"] = listed;
        Json widest_row = Json::object();
        widest_row["text"] = widest.at("text");
        widest_row["reach"] = widest.at("reach");
        row["widest_known"] = widest_row;
        Json richest_row = Json::object();
        richest_row["text"] = richest->at("text");
        richest_row["reach"] = richest->at("reach");
        richest_row["first_hand"] = richest->at("first_hand");
        row["most_detailed"] = richest_row;
        row["note"] = std::string("versions of one incident: reach and detail are "
                                  "not the same thing");
        story_list.push_back(row);
    }
    std::stable_sort(story_list.begin(), story_list.end(),
                     [](const Json& a, const Json& b) {
                         auto widest = [](const Json& s) {
                             long long best = 0;
                             for (const Json& v : s.at("versions").items())
                                 best = std::max(best, v.at("reach").as_int());
                             return best;
                         };
                         return widest(a) > widest(b);
                     });

    Json facts_json = Json::array();
    for (const Json& one : out) facts_json.push(one);
    Json stories_json = Json::array();
    for (const Json& one : story_list) stories_json.push(one);
    Json circles_json = Json::array();
    for (const auto& entry : circle_map) {
        std::vector<std::string> members = entry.second;
        std::sort(members.begin(), members.end());
        Json row = Json::object();
        row["circle"] = entry.first;
        Json who = Json::array();
        for (const std::string& one : members) who.push(one);
        row["members"] = who;
        circles_json.push(row);
    }
    Json bridges_json = Json::array();
    OrderedMap<std::vector<std::string>> found = bridges(world.agents);
    std::vector<std::string> bridge_ids;
    for (const auto& entry : found) bridge_ids.push_back(entry.first);
    std::sort(bridge_ids.begin(), bridge_ids.end());
    for (const std::string& agent_id : bridge_ids) {
        Json row = Json::object();
        row["agent"] = agent_id;
        row["name"] = sdk.agent_name(agent_id);
        Json listed = Json::array();
        for (const std::string& one : *found.find(agent_id)) listed.push(one);
        row["circles"] = listed;
        bridges_json.push(row);
    }
    Json occupancy_json = Json::array();
    std::vector<std::string> places;
    for (const auto& entry : occupancy) places.push_back(entry.first);
    std::sort(places.begin(), places.end());
    for (const std::string& place : places) {
        std::vector<Json> people = *occupancy.find(place);
        std::stable_sort(people.begin(), people.end(),
                         [](const Json& a, const Json& b) {
                             return a.at("name").py_str() < b.at("name").py_str();
                         });
        Json row = Json::object();
        row["place"] = place;
        row["label"] = world.place_label(place);
        Json listed = Json::array();
        for (const Json& one : people) listed.push(one);
        row["people"] = listed;
        occupancy_json.push(row);
    }

    Json result = Json::object();
    result["world_time"] = world.world_time;
    result["time_of_day"] = detail_::clock(world.world_time);
    result["facts"] = facts_json;
    result["stories"] = stories_json;
    // Empty without a store, and present so a caller sees the same shape.
    result["transmissions"] = Json::array();
    result["knowledge_classes"] = classes;
    result["circles"] = circles_json;
    result["bridges"] = bridges_json;
    result["contested"] = contested;
    result["judgements"] = judgements;
    result["occupancy"] = occupancy_json;
    (void)core;
    return result;
}

/// Time, factions, heat, clocks, rumour exposure.
inline Json world_state(UnscriptedRuntime& sdk) {
    Json factions = Json::object();
    for (const auto& entry : sdk.core.director.factions()) {
        const Faction& f = entry.second;
        Json row = Json::object();
        row["influence"] = py_round(f.influence, 3);
        row["heat"] = py_round(f.heat, 3);
        row["resources"] = py_round(f.resources, 3);
        Json clocks = Json::array();
        for (const auto& clock : f.clocks) {
            Json one = Json::object();
            one["name"] = clock.second.name;
            one["filled"] = clock.second.filled;
            one["size"] = clock.second.size;
            clocks.push(one);
        }
        row["clocks"] = clocks;
        factions[entry.first] = row;
    }

    Json media = Json::array();
    for (const auto& entry : sdk.world.media_exposure) {
        std::size_t split = entry.first.find('\x1f');
        Json row = Json::object();
        row["agent"] = entry.first.substr(0, split);
        row["channel"] = entry.first.substr(split + 1);
        if (entry.second.kind() == Json::Kind::Object)
            for (const auto& field : entry.second.fields()) row[field.first] = field.second;
        else
            row["value"] = entry.second;
        media.push(row);
    }

    Json capabilities = Json::object();
    for (const auto& entry : resolve_capabilities(sdk.config).resolved)
        capabilities[entry.first] = entry.second;

    Json out = Json::object();
    out["world_time"] = sdk.world.world_time;
    out["factions"] = factions;
    out["media_exposure"] = media;
    out["capabilities"] = capabilities;
    return out;
}

/// The player's current location, for a UI: place, NPCs, exits.
inline Json scene_state(UnscriptedRuntime& sdk) {
    const Agent& player = *sdk.world.agents.find(sdk.config.player_id);
    std::string location = player.location().py_str();
    const Json* place = sdk.world.places.find(location);
    auto level = [&place](const char* key) {
        const Json* found = place ? place->find(key) : nullptr;
        return py_round(found ? found->as_double() : 0.0, 2);
    };

    std::vector<Json> npcs;
    for (const auto& entry : sdk.world.agents) {
        if (entry.first == sdk.config.player_id) continue;
        if (entry.second.location().py_str() != location) continue;
        Json row = Json::object();
        row["id"] = entry.first;
        row["name"] = sdk.agent_name(entry.first);
        npcs.push_back(row);
    }
    std::stable_sort(npcs.begin(), npcs.end(), [](const Json& a, const Json& b) {
        return a.at("name").py_str() < b.at("name").py_str();
    });

    Json listed = Json::array();
    for (const Json& one : npcs) listed.push(one);
    Json exits = Json::array();
    for (const std::string& one : sdk.world.exits_from(location)) {
        Json row = Json::object();
        row["id"] = one;
        row["label"] = sdk.world.place_label(one);
        exits.push(row);
    }
    Json attributes = Json::object();
    attributes["noise"] = level("noise_level");
    attributes["surveillance"] = level("surveillance_level");
    attributes["privacy"] = level("privacy_level");

    Json out = Json::object();
    out["world_time"] = sdk.world.world_time;
    out["location"] = location;
    out["label"] = sdk.world.place_label(location);
    out["attributes"] = attributes;
    out["npcs"] = listed;
    out["exits"] = exits;
    return out;
}

}  // namespace state_view

}  // namespace usc
