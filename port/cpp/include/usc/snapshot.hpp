// `usc/snapshot.py`. Capture and restore, and the blob a game puts in its own
// save file.
//
// A snapshot is the complete MUTABLE state needed to resume a session exactly:
// per-agent belief with provenance, memory with presentation history, affect,
// the cross-cutting social state a game actually needs back after a load, the
// scheduled timeline, the event-id watermark, director state, conversations and
// the population-LOD watermarks.
//
// It deliberately does NOT copy the append-only event ledger or the reason
// traces. Those are audit streams: they live in their own tables, grow
// monotonically, and embedding them made each snapshot O(session length) and the
// snapshot table O(saves x session length). The watermark is recorded instead, so
// an audit tool reconstructs "the ledger as of this snapshot" with one range
// query.
//
// Capture and restore are pure functions over (world, runtime). Keeping them
// here rather than in a store is what lets the persistence layer hold an opaque
// blob -- and it is the whole reason this module ports to a console at all while
// the SQLite layer does not.
#pragma once

#include <algorithm>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/actionbridge.hpp"
#include "usc/contracts.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/runtime.hpp"
#include "usc/sha256.hpp"
#include "usc/world.hpp"

namespace usc {

/// Bumped when the snapshot JSON shape changes incompatibly; restore reports a
/// mismatch as a reason entry rather than refusing.
inline constexpr long long SNAPSHOT_SCHEMA_VERSION = 11;

namespace detail_ {

inline Json event_state(const Event& e) {
    Json out = Json::object();
    out["event_id"] = e.event_id;
    out["world_time"] = e.world_time;
    out["type"] = e.type;
    out["actor"] = e.actor;
    out["location"] = e.location;
    out["payload"] = e.payload;
    out["canonical"] = e.canonical;
    return out;
}

inline Json numbers(const OrderedMap<double>& values) {
    Json out = Json::object();
    for (const auto& entry : values) out[entry.first] = entry.second;
    return out;
}

inline Json agent_state(const Agent& agent) {
    Json out = Json::object();
    out["location"] = agent.location();
    Json beliefs = Json::array();
    for (const auto& entry : agent.beliefs) beliefs.push(entry.second.as_json());
    out["beliefs"] = beliefs;
    Json memory = Json::array();
    for (const auto& item : agent.memory) memory.push(item->as_json());
    out["memory"] = memory;
    out["affect"] = agent.affect.as_json();
    Json relationships = Json::object();
    for (const auto& entry : agent.relationships)
        relationships[entry.first] = numbers(entry.second);
    out["relationships"] = relationships;
    Json reputation = Json::object();
    for (const auto& entry : agent.reputation)
        reputation[entry.first] = numbers(entry.second);
    out["reputation"] = reputation;
    out["identity_threat"] = numbers(agent.identity_threat);
    out["identity_salience"] = numbers(agent.identity_salience);
    // A day's intake. Losing it on load hands everyone a fresh, empty day, and a
    // reloaded save then absorbs information the same session would have refused.
    out["attention_day"] = agent.attention_day;
    out["attention_spent"] = agent.attention_spent;
    // How far each believed act has already moved this character's standing
    // towards whoever did it. Without it a reload re-applies every judgement the
    // save had already paid out.
    Json applied = Json::object();
    for (const auto& entry : agent.standing_applied)
        applied.fields()[entry.first] = Json(entry.second);
    out["standing_applied"] = applied;
    Json tom = Json::array();
    for (const Agent::TheoryOfMind& row : agent.tom_models) {
        Json entry = Json::object();
        entry["other"] = row.other;
        entry["proposition"] = row.proposition;
        entry["model"] = numbers(row.model);
        tom.push(entry);
    }
    out["tom_models"] = tom;
    return out;
}

inline void apply_agent_state(Agent& agent, const Json& state,
                              const Json* places = nullptr,
                              std::vector<Reason>* reasons = nullptr) {
    if (const Json* where = state.find("location")) {
        // A place this world does not have. Leaving the character standing in it
        // makes every later query about the room they are in answer with a room
        // that is not there, so they keep where the pack put them and the loss is
        // reported rather than discovered later.
        bool unknown = places != nullptr && !where->is_null()
                    && places->find(where->py_str()) == nullptr;
        if (unknown) {
            if (reasons != nullptr) {
                Json why = Json::object();
                why["agent"] = agent.id;
                why["place"] = *where;
                why["kept"] = agent.location();
                why["note"] = std::string("not in the loaded world pack; the "
                                          "authored location was kept");
                reasons->push_back({"snapshot.unknown_place", 0.0, why});
            }
        } else {
            agent.set_location(*where);
        }
    }

    agent.beliefs = OrderedMap<Belief>();
    const Json* beliefs = state.find("beliefs");
    if (beliefs) for (const Json& row : beliefs->items()) {
        Belief belief = Belief::from_json(row);
        agent.beliefs[belief.proposition.core_key()] = belief;
    }

    agent.memory.clear();
    const Json* memory = state.find("memory");
    if (memory) for (const Json& row : memory->items())
        agent.memory.push_back(std::make_shared<MemoryItem>(
            MemoryItem::from_json(row, agent.id)));

    const Json* affect = state.find("affect");
    if (affect && affect->truthy()) agent.affect = AffectState::from_json(*affect);

    auto restore_numbers = [](const Json* doc) {
        OrderedMap<OrderedMap<double>> out;
        if (!doc) return out;
        for (const auto& entry : doc->fields()) {
            OrderedMap<double> row;
            for (const auto& field : entry.second.fields())
                row[field.first] = field.second.as_double();
            out[entry.first] = row;
        }
        return out;
    };
    agent.relationships = restore_numbers(state.find("relationships"));
    agent.reputation = restore_numbers(state.find("reputation"));

    agent.identity_threat = OrderedMap<double>();
    if (const Json* threat = state.find("identity_threat"))
        for (const auto& entry : threat->fields())
            agent.identity_threat[entry.first] = entry.second.as_double();
    agent.identity_salience = OrderedMap<double>();
    if (const Json* salience = state.find("identity_salience"))
        for (const auto& entry : salience->fields())
            agent.identity_salience[entry.first] = entry.second.as_double();

    const Json* day = state.find("attention_day");
    agent.attention_day = day ? day->as_int() : -1;
    const Json* spent = state.find("attention_spent");
    agent.attention_spent = spent ? spent->as_int() : 0;
    agent.standing_applied = OrderedMap<double>();
    const Json* applied_doc = state.find("standing_applied");
    if (applied_doc && !applied_doc->is_null())
        for (const auto& entry : applied_doc->fields())
            agent.standing_applied[entry.first] = entry.second.as_double();

    agent.tom_models.clear();
    if (const Json* tom = state.find("tom_models"))
        for (const Json& row : tom->items()) {
            Agent::TheoryOfMind entry;
            entry.other = row.at("other").as_string();
            entry.proposition = row.at("proposition").as_string();
            for (const auto& field : row.at("model").fields())
                entry.model[field.first] = field.second.as_double();
            agent.tom_models.push_back(entry);
        }
}

inline void apply_director_state(Runtime& core, const Json& factions,
                                 std::vector<Reason>& reasons) {
    for (const auto& entry : factions.fields()) {
        const Json& data = entry.second;
        Faction* faction = core.director.factions().find(entry.first);
        if (!faction) {
            // The snapshot knows a faction the loaded pack does not define.
            // Restore it so heat and clock history is not silently dropped, and
            // say so.
            core.director.add_faction(Faction::from_json(data));
            Json why = Json::object();
            why["faction"] = entry.first;
            reasons.push_back({"snapshot.unknown_faction", 0.0, why});
            continue;
        }
        if (const Json* value = data.find("influence")) faction->influence = value->as_double();
        if (const Json* value = data.find("resources")) faction->resources = value->as_double();
        const Json* heat = data.find("heat");
        faction->heat = heat ? heat->as_double() : 0.0;
        if (const Json* territory = data.find("territory")) {
            faction->territory.clear();
            for (const Json& one : territory->items())
                faction->territory.push_back(one.py_str());
        }
        if (const Json* goals = data.find("goals")) {
            faction->goals.clear();
            for (const Json& one : goals->items()) faction->goals.push_back(one.py_str());
        }
        faction->clocks = OrderedMap<ProgressClock>();
        if (const Json* clocks = data.find("clocks"))
            for (const auto& clock : clocks->fields())
                faction->clocks[clock.first] = ProgressClock::from_json(clock.second);
    }
}

}  // namespace detail_

/// Serialise everything needed to resume this session.
inline Json capture(const World& world, const Runtime& core) {
    Json out = Json::object();
    out["snapshot_schema_version"] = SNAPSHOT_SCHEMA_VERSION;
    out["global_seed"] = world.global_seed;
    out["world_time"] = world.world_time;
    out["next_event_id"] = world.peek_event_id();
    // A watermark instead of a ledger copy: the ledger is an append-only audit
    // stream in its own table, not part of resumable state.
    // The ledger's own high-water mark, not the simulation's event counter:
    // `restore` rewinds the latter, so after a reload the abandoned branch and
    // the new one share event ids and "the history as of this snapshot" grew a
    // future it never had. The C++ core carries no store, so this records the
    // shape the Python side writes.
    out["ledger_watermark"] = 0;
    Json scheduled = Json::array();
    for (const Event& e : world.scenario_events) scheduled.push(detail_::event_state(e));
    out["scenario_events"] = scheduled;
    Json agents = Json::object();
    for (const auto& entry : world.agents)
        agents[entry.first] = detail_::agent_state(entry.second);
    out["agents"] = agents;
    Json factions = Json::object();
    for (const auto& entry : core.director.factions())
        factions[entry.first] = entry.second.as_json();
    out["factions"] = factions;
    Json conversations = Json::object();
    for (const auto& entry : core.conversations)
        conversations[entry.first] = entry.second.as_json();
    out["conversations"] = conversations;
    Json decay = Json::object();
    for (const auto& entry : core.last_decay()) decay[entry.first] = entry.second;
    out["last_decay"] = decay;
    // What the engine has been asked to do and has not answered. Restoring
    // without it would leave the runtime waiting on intents no engine knows
    // about, and the characters holding them frozen until they time out.
    out["actions_out"] = core.actions_out.as_json();
    out["climate"] = core.climate.as_json();
    out["pursuit"] = core.pursuit.as_json();
    out["common_knowledge"] = core.common_knowledge.as_json();
    out["notes"] = core.notes.as_json();
    out["promises"] = core.promises.as_json();
    return out;
}

/// Apply a captured snapshot to a live world and runtime.
///
/// Returns reason entries describing anything the caller should know about --
/// schema mismatch, seed mismatch, agents present on one side and not the other.
/// UNKNOWN AGENTS ARE SKIPPED rather than fabricated: a snapshot must never
/// invent world content the loaded pack does not define.
inline std::vector<Reason> restore(const Json& data, World& world, Runtime& core) {
    std::vector<Reason> reasons;

    const Json* declared = data.find("snapshot_schema_version");
    long long version = declared ? declared->as_int() : 1;
    if (version != SNAPSHOT_SCHEMA_VERSION) {
        Json why = Json::object();
        why["found"] = version;
        why["expected"] = SNAPSHOT_SCHEMA_VERSION;
        why["note"] = std::string("restored on a best-effort basis");
        reasons.push_back({"snapshot.version_mismatch",
                           static_cast<double>(version), why});
    }

    const Json* seed = data.find("global_seed");
    if (seed && !seed->is_null() && seed->py_str() != world.global_seed) {
        // Determinism is seed-derived; restoring across seeds silently changes
        // every future stochastic draw, so surface it loudly.
        Json why = Json::object();
        why["snapshot"] = *seed;
        why["world"] = world.global_seed;
        reasons.push_back({"snapshot.seed_mismatch", 0.0, why});
    }

    world.world_time = data.at("world_time").as_int();
    if (const Json* next = data.find("next_event_id")) world.set_event_id(next->as_int());
    world.scenario_events.clear();
    if (const Json* scheduled = data.find("scenario_events"))
        for (const Json& row : scheduled->items()) {
            Event e;
            e.event_id = row.at("event_id").as_int();
            e.world_time = row.at("world_time").as_int();
            e.type = row.at("type").as_string();
            e.actor = row.get("actor");
            e.location = row.get("location");
            const Json* payload = row.find("payload");
            e.payload = payload ? *payload : Json::object();
            const Json* canonical = row.find("canonical");
            e.canonical = canonical ? canonical->truthy() : true;
            world.scenario_events.push_back(e);
        }

    const Json* agents = data.find("agents");
    std::set<std::string> in_snapshot;
    if (agents) for (const auto& entry : agents->fields()) {
        in_snapshot.insert(entry.first);
        Agent* agent = world.agents.find(entry.first);
        if (!agent) {
            Json why = Json::object();
            why["agent"] = entry.first;
            why["note"] = std::string("not in the loaded world pack");
            reasons.push_back({"snapshot.unknown_agent", 0.0, why});
            continue;
        }
        detail_::apply_agent_state(*agent, entry.second, &world.places, &reasons);
    }

    std::vector<std::string> missing;
    for (const auto& entry : world.agents)
        if (!in_snapshot.count(entry.first)) missing.push_back(entry.first);
    std::sort(missing.begin(), missing.end());
    if (!missing.empty()) {
        // Agents the world pack defines but the snapshot never saw -- the pack
        // gained characters since the save. They keep their authored start state.
        Json who = Json::array();
        for (const std::string& one : missing) who.push(one);
        Json why = Json::object();
        why["agents"] = who;
        reasons.push_back({"snapshot.agent_not_in_snapshot",
                           static_cast<double>(missing.size()), why});
    }

    const Json* factions = data.find("factions");
    detail_::apply_director_state(core, factions ? *factions : Json::object(), reasons);

    core.conversations = OrderedMap<ConversationState>();
    if (const Json* conversations = data.find("conversations"))
        for (const auto& entry : conversations->fields())
            core.conversations[entry.first] = ConversationState::from_json(entry.second);

    // LOD decay watermarks: fall back to the snapshot's world time for any agent
    // the snapshot did not carry, so nothing is decayed twice or skipped.
    const Json* decay = data.find("last_decay");
    OrderedMap<long long> watermarks;
    for (const auto& entry : world.agents) {
        const Json* stored = decay ? decay->find(entry.first) : nullptr;
        watermarks[entry.first] = stored ? stored->as_int()
                                         : data.at("world_time").as_int();
    }
    core.last_decay() = watermarks;

    if (const Json* bridge = data.find("actions_out"))
        core.actions_out = ActionBridge::from_json(*bridge);
    if (const Json* value = data.find("climate")) core.climate.restore(*value);
    if (const Json* value = data.find("pursuit")) core.pursuit.restore(*value);
    if (const Json* value = data.find("common_knowledge"))
        core.common_knowledge.restore(*value);
    if (const Json* value = data.find("notes")) core.notes.restore(*value);
    if (const Json* value = data.find("promises")) core.promises.restore(*value);

    // Per-turn debug traces describe the turn that produced them, not the
    // restored state; keeping them would attach stale explanations to a rewound
    // world.
    core.last_traces = TraceMap();
    if (!reasons.empty()) core.last_traces["_snapshot"] = reasons;
    return reasons;
}

// ---------------------------------------------------------- portable export --
//
// `capture` and `restore` are the runtime's INTERNAL round trip: same process,
// same world pack, same code. That is the right shape for a snapshot id handed
// back and put again.
//
// It is the wrong shape for what a game actually has to do, which is put the
// world into ITS OWN SAVE FILE -- a file the player owns, copies, syncs and
// restores onto a different machine six months and two patches later. A snapshot
// id pointing into the runtime's own store cannot do that: it makes the runtime a
// second save file that has to be kept in step with the first, and the two drift
// the first time somebody copies a save.

/// Bumped when the ENVELOPE changes, which is separate from the schema version
/// of the state inside it. Two versions because they move for different reasons
/// and a loader wants to fail differently: an unreadable envelope is "this is not
/// our file", an unreadable payload is "this save is from a newer build".
inline constexpr const char* STATE_FORMAT = "unscripted-state";
/// What this marker used to be. A save written before the project was renamed is
/// still a valid save -- the envelope changed its name, not its shape -- so it is
/// accepted on read and rewritten under the current marker. Nothing writes this.
/// Kept in step with `STATE_FORMAT_LEGACY` in the Python snapshot module.
inline constexpr const char* STATE_FORMAT_LEGACY = "lwr-state";
inline constexpr long long STATE_FORMAT_VERSION = 1;

/// Whether this `format` field names a state blob this build can open.
inline bool is_state_envelope(const std::string& marker) {
    return marker == STATE_FORMAT || marker == STATE_FORMAT_LEGACY;
}

/// A stable short hash of the world's SHAPE -- who and where, not what happened.
///
/// Deliberately over the immutable cast and map rather than over the pack files:
/// a studio reformats JSON, renames a directory or regenerates a pack, and none
/// of that should invalidate a player's save. What must match is that the
/// characters and places a save talks about are the ones this world has.
inline std::string world_fingerprint(const World& world) {
    std::vector<std::string> agents, places, topics;
    for (const auto& entry : world.agents) agents.push_back(entry.first);
    for (const auto& entry : world.places.fields()) places.push_back(entry.first);
    for (const auto& entry : world.topics) topics.push_back(entry.first);
    std::sort(agents.begin(), agents.end());
    std::sort(places.begin(), places.end());
    std::sort(topics.begin(), topics.end());
    auto joined = [](const std::vector<std::string>& parts) {
        std::string out;
        for (std::size_t i = 0; i < parts.size(); ++i) {
            if (i) out += ',';
            out += parts[i];
        }
        return out;
    };
    std::string material = world.global_seed + "|" + joined(agents) + "|"
                         + joined(places) + "|" + joined(topics);
    return sha256_hex(material).substr(0, 16);
}

/// The whole mutable world as one JSON-safe blob a game can save itself.
///
/// Everything a loader needs in order to decide whether it can use this is in
/// the envelope, so it never has to parse the payload to find out.
inline Json export_state(const World& world, const Runtime& core) {
    Json out = Json::object();
    out["format"] = std::string(STATE_FORMAT);
    out["format_version"] = STATE_FORMAT_VERSION;
    // Informational: which build wrote it. NOT a compatibility gate -- the schema
    // version is that, and tying saves to a runtime version would break every
    // save on a patch that changed nothing about the state.
    out["runtime_version"] = std::string(RUNTIME_VERSION);
    out["snapshot_schema_version"] = SNAPSHOT_SCHEMA_VERSION;
    out["world_fingerprint"] = world_fingerprint(world);
    // The map, named. Agent overlap alone cannot tell "the same world, patched"
    // from "somebody else's game": every pack ships the same default player id.
    Json places = Json::array();
    std::vector<std::string> place_ids;
    for (const auto& entry : world.places.fields()) place_ids.push_back(entry.first);
    std::sort(place_ids.begin(), place_ids.end());
    for (const std::string& one : place_ids) places.push(Json(one));
    out["places"] = places;
    // What the pack says this world IS.
    out["world_id"] = world.world_id;
    // Named here as well as inside the payload so a loader can report what would
    // be dropped BEFORE committing to the import.
    std::vector<std::string> names;
    for (const auto& entry : world.agents) names.push_back(entry.first);
    std::sort(names.begin(), names.end());
    Json listed = Json::array();
    for (const std::string& one : names) listed.push(one);
    out["agents"] = listed;
    out["world_time"] = world.world_time;
    out["state"] = capture(world, core);
    return out;
}

/// A blob that cannot be imported, with a reason a person can act on.
class StateImportError : public std::invalid_argument {
public:
    explicit StateImportError(const std::string& what) : std::invalid_argument(what) {}
};

/// What would happen if this were imported, WITHOUT importing it.
///
/// The call a load screen makes: it can offer "continue" or "start over" on the
/// strength of this, and never has to catch an exception to find out which.
inline Json inspect_state(const Json& blob, const World& world) {
    auto refuse = [](const char* code, const std::string& detail) {
        Json out = Json::object();
        out["usable"] = false;
        out["code"] = std::string(code);
        out["detail"] = detail;
        return out;
    };
    if (blob.kind() != Json::Kind::Object
        || !is_state_envelope(blob.get("format").py_str()))
        return refuse("not_a_state_blob", "missing the unscripted-state marker");
    const Json* envelope = blob.find("format_version");
    long long found = envelope ? envelope->as_int() : 0;
    if (found > STATE_FORMAT_VERSION)
        return refuse("envelope_too_new",
                      "envelope v" + std::to_string(found) + " against v"
                      + std::to_string(STATE_FORMAT_VERSION) + " here");
    const Json* schema = blob.find("snapshot_schema_version");
    long long saved_schema = schema ? schema->as_int() : 0;
    if (saved_schema > SNAPSHOT_SCHEMA_VERSION)
        return refuse("save_from_newer_build",
                      "state schema " + std::to_string(saved_schema) + " against "
                      + std::to_string(SNAPSHOT_SCHEMA_VERSION) + " here");

    std::set<std::string> saved;
    const Json* names = blob.find("agents");
    if (names) for (const Json& one : names->items()) saved.insert(one.py_str());
    std::set<std::string> here;
    for (const auto& entry : world.agents) here.insert(entry.first);

    std::vector<std::string> known, dropped, unsaved;
    for (const std::string& one : saved)
        (here.count(one) ? known : dropped).push_back(one);
    for (const std::string& one : here)
        if (!saved.count(one)) unsaved.push_back(one);

    if (!saved.empty() && known.empty())
        return refuse("different_world",
                      "not one character in this save exists in this world");

    // WHICH WORLD IS THIS. A pack that says so is believed, and nothing else is
    // consulted: an id is an identity, and every other test here is a proxy.
    const Json* saved_identity = blob.find("world_id");
    std::string saved_id = (saved_identity && !saved_identity->is_null())
                         ? saved_identity->py_str() : std::string();
    const std::string& here_id = world.world_id;
    if (!saved_id.empty() && !here_id.empty() && saved_id != here_id)
        return refuse("different_world",
                      "this save belongs to '" + saved_id + "', not '" + here_id + "'");

    // A PACK THAT HAS NOT SAID leaves the loader comparing what it can see, and
    // the standard is overlap that could not be coincidence. ONE shared id
    // always is one somewhere: every pack ships `agent:player_1`, and two
    // unrelated worlds that both name a room `place:spawn` did it again.
    std::set<std::string> saved_places;
    const Json* place_names = blob.find("places");
    if (place_names && !place_names->is_null())
        for (const Json& one : place_names->items()) saved_places.insert(one.py_str());
    std::set<std::string> shared_places;
    for (const std::string& one : saved_places)
        if (world.places.find(one) != nullptr) shared_places.insert(one);
    std::set<std::string> shared_cast(known.begin(), known.end());
    shared_cast.erase(DEFAULT_PLAYER_ID);
    // NO DECLARED IDENTITY, so the loader is guessing and says so. The bar is a
    // character who is not the player: place names are the part two unrelated
    // worlds are most likely to share by accident, and raising the threshold from
    // one shared place to two only moved the accident rather than removing it.
    // Every shipped pack declares an id now, so this is the compatibility path
    // for saves and packs written before it existed.
    bool unverified = saved_id.empty() || here_id.empty();
    if (unverified) {
        if (!saved_places.empty() && shared_places.empty())
            return refuse("different_world",
                          "not one place in this save exists in this world");
        if (shared_cast.empty() && saved.size() > 1)
            return refuse("different_world",
                          "this save shares no character but the player with this "
                          "world, and neither side declares a `world_id`. Declare "
                          "one in scenario.json to say what a world is rather than "
                          "leaving it to be inferred");
    }

    // A PATCH IS NOT A CORRUPTION. A studio ships an update that adds an NPC or
    // retires one, and every existing save must keep working -- so a fingerprint
    // mismatch is REPORTED and proceeded through rather than refused. What is
    // refused is a save with no overlap at all, which is somebody's other game.
    Json out = Json::object();
    out["usable"] = true;
    // `world_unverified` is not a warning about the cast -- it says the identity
    // was inferred rather than checked, which a loader may well want to refuse on
    // its own.
    out["code"] = std::string(
        unverified ? "world_unverified"
                   : blob.get("world_fingerprint").py_str() == world_fingerprint(world)
                       ? "ok" : "world_changed");
    out["detail"] = std::string();
    const Json* when = blob.find("world_time");
    out["saved_at_world_time"] = when ? when->as_int() : 0;
    out["written_by"] = blob.get("runtime_version");
    auto listed = [](const std::vector<std::string>& parts) {
        Json rows = Json::array();
        for (const std::string& one : parts) rows.push(one);
        return rows;
    };
    out["restored"] = listed(known);
    // Characters the save knows and this build does not: their state is dropped,
    // and saying so is the difference between a load that lost something and a
    // load that lost something quietly.
    out["dropped"] = listed(dropped);
    // Characters this build has that the save predates: they keep whatever the
    // world pack authored, which is the only defensible answer.
    out["unsaved"] = listed(unsaved);
    return out;
}

struct ImportResult {
    Json report;
    std::vector<Reason> reasons;
};

/// Put a blob back.
///
/// Throws only for a blob that cannot be used at all; everything survivable is
/// reported and applied.
inline ImportResult import_state(const Json& blob, World& world, Runtime& core) {
    Json report = inspect_state(blob, world);
    if (!report.at("usable").truthy())
        throw StateImportError(report.at("code").py_str() + ": "
                               + report.at("detail").py_str());
    const Json* state = blob.find("state");
    // ALL OF IT OR NONE OF IT. The envelope can be sound and the payload rotten:
    // a belief that will not parse used to throw half way through, AFTER the
    // world clock and the schedule had already been overwritten, leaving a live
    // session in a state that was neither the old one nor the new one.
    Json rollback = capture(world, core);
    std::vector<Reason> reasons;
    try {
        reasons = restore(state ? *state : Json::object(), world, core);
    } catch (const std::exception& failure) {
        restore(rollback, world, core);
        throw StateImportError(std::string("invalid_payload: ") + failure.what());
    }
    if (report.at("code").py_str() == "world_changed") {
        Json why = Json::object();
        why["dropped"] = report.at("dropped");
        why["unsaved"] = report.at("unsaved");
        why["note"] = std::string("the cast has changed since this save; it was "
                                  "loaded anyway and the differences are listed");
        reasons.push_back({"state.world_changed",
                           static_cast<double>(report.at("dropped").items().size()),
                           why});
    }
    return {report, reasons};
}

}  // namespace usc
