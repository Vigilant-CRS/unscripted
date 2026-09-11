// Runs `engine_cases.json` through the ported affect, relationship, identity and
// memory engines, and prints the result with every double as its raw 64 bits.
//
// The Python side of this (`engine_probe.py`) drives the real modules, not a
// re-implementation, and diffs the two field by field including map order.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

#include "usc/affect.hpp"
#include "usc/agency.hpp"
#include "usc/agent.hpp"
#include "usc/appearance.hpp"
#include "usc/belief.hpp"
#include "usc/climate.hpp"
#include "usc/common_knowledge.hpp"
#include "usc/contagion.hpp"
#include "usc/content.hpp"
#include "usc/medium.hpp"
#include "usc/dialogue.hpp"
#include "usc/contracts.hpp"
#include "usc/diffusion.hpp"
#include "usc/distortion.hpp"
#include "usc/commitment.hpp"
#include "usc/events.hpp"
#include "usc/factions.hpp"
#include "usc/flat.hpp"
#include "usc/grounding.hpp"
#include "usc/tuning.hpp"
#include "usc/interpretation.hpp"
#include "usc/parser.hpp"
#include "usc/actionbridge.hpp"
#include "usc/provider.hpp"
#include "usc/runtime.hpp"
#include "usc/inspect.hpp"
#include "usc/pack_loader.hpp"
#include "usc/sdk.hpp"
#include "usc/state_view.hpp"
#include "usc/snapshot.hpp"
#include "usc/validator.hpp"
#include "usc/json.hpp"
#include "usc/memory.hpp"
#include "usc/perception.hpp"
#include "usc/policy.hpp"
#include "usc/notes.hpp"
#include "usc/promises.hpp"
#include "usc/pursuit.hpp"
#include "usc/relationship.hpp"
#include "usc/revision.hpp"
#include "usc/routine.hpp"
#include "usc/social.hpp"
#include "usc/sociolinguistics.hpp"
#include "usc/standing.hpp"
#include "usc/topology.hpp"

namespace {

std::string read_file(const char* path) {
    std::ifstream file(path);
    std::ostringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

usc::Json bits_of(double value) {
    std::uint64_t raw;
    std::memcpy(&raw, &value, sizeof raw);
    char buffer[32];
    std::snprintf(buffer, sizeof buffer, "b:%016llx",
                  static_cast<unsigned long long>(raw));
    return usc::Json(std::string(buffer));
}

usc::Json to_bits(const usc::Json& value) {
    switch (value.kind()) {
        case usc::Json::Kind::Real: return bits_of(value.as_double());
        case usc::Json::Kind::Array: {
            usc::Json out = usc::Json::array();
            for (const auto& item : value.items()) out.push(to_bits(item));
            return out;
        }
        case usc::Json::Kind::Object: {
            usc::Json out = usc::Json::object();
            for (const auto& entry : value.fields())
                out.fields()[entry.first] = to_bits(entry.second);
            return out;
        }
        default: return value;
    }
}

// Declared here because `run_standing` and `run_appearance` sit above their
// definitions; the sections are ordered to match `engine_cases.json` rather than
// by what happens to reference what.
usc::Json deltas_json(const std::vector<usc::ProposedDelta>& deltas);
usc::Json strings_json(const std::vector<std::string>& values);

usc::Json pad_json(const usc::Vec3& vector) {
    usc::Json out = usc::Json::object();
    out["valence"] = vector.p;
    out["arousal"] = vector.a;
    out["dominance"] = vector.d;
    return out;
}

usc::Json reasons_json(const std::vector<usc::AffectReason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json numbers_json(const usc::OrderedMap<double>& values) {
    usc::Json out = usc::Json::object();
    for (const auto& entry : values) out.fields()[entry.first] = usc::Json(entry.second);
    return out;
}

// ---- affect ---------------------------------------------------------------

usc::Json run_affect(const usc::Json& scenario) {
    usc::OrderedMap<double> traits;
    for (const auto& entry : scenario.at("big_five").fields())
        traits[entry.first] = entry.second.as_double();

    usc::AffectEngine engine;
    usc::AffectState state;
    state.baseline = usc::pad_baseline_from_big_five(traits);
    state.mood = state.baseline;

    usc::Json steps = usc::Json::array();
    for (const usc::Json& step : scenario.at("steps").items()) {
        std::vector<usc::AffectReason> reasons;
        std::vector<std::pair<std::string, double>> fired =
            engine.update(state, step.at("appraisal"), step.get("dt").as_double(), &reasons);

        usc::Json fired_json = usc::Json::array();
        for (const auto& entry : fired) {
            usc::Json row = usc::Json::object();
            row["emotion"] = entry.first;
            row["intensity"] = entry.second;
            fired_json.push(row);
        }
        usc::Json row = usc::Json::object();
        row["fired"] = fired_json;
        row["mood"] = pad_json(state.mood);
        row["active_emotions"] = numbers_json(state.active_emotions);
        row["tendencies"] = numbers_json(engine.action_tendencies(state));
        row["stress"] = engine.stress(state);
        row["reasons"] = reasons_json(reasons);
        steps.push(row);
    }
    usc::Json out = usc::Json::object();
    out["baseline"] = pad_json(state.baseline);
    out["steps"] = steps;
    return out;
}

// ---- relationship, reputation ---------------------------------------------

usc::Json relationship_map(const usc::OrderedMap<usc::OrderedMap<double>>& source) {
    usc::Json out = usc::Json::object();
    for (const auto& entry : source) out.fields()[entry.first] = numbers_json(entry.second);
    return out;
}

usc::Json run_relationship(const usc::Json& scenario) {
    usc::Agent agent;
    agent.id = "agent:self";
    for (const auto& subject : scenario.at("initial").fields())
        for (const auto& field : subject.second.fields())
            agent.relationships[subject.first][field.first] = field.second.as_double();

    std::vector<usc::ProposedDelta> deltas;
    for (const usc::Json& row : scenario.at("deltas").items())
        deltas.push_back(usc::relationship_delta(
            agent.id, row.get("subject").as_string(), row.get("field").as_string(),
            row.get("amount").as_double(), row.get("reason").as_string(), "probe"));

    std::vector<usc::RelationshipReason> reasons;
    usc::RelationshipEngine().apply(agent, deltas, reasons);

    std::vector<usc::ProposedDelta> reputation;
    for (const usc::Json& row : scenario.at("reputation").items()) {
        const usc::Json& dimension = row.at("dimension");
        reputation.push_back(usc::reputation_delta(
            row.get("subject").as_string(), agent.id,
            dimension.is_null() ? "" : dimension.as_string(),
            row.get("amount").as_double(), row.get("reason").as_string(), "probe"));
    }
    usc::ReputationEngine().apply(agent, reputation, reasons);

    usc::Json out = usc::Json::object();
    out["relationships"] = relationship_map(agent.relationships);
    out["reputation"] = relationship_map(agent.reputation);
    usc::Json trace = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        trace.push(row);
    }
    out["reasons"] = trace;
    return out;
}

// ---- identity -------------------------------------------------------------

usc::Json run_identity(const usc::Json& scenario) {
    usc::Agent agent;
    agent.id = "agent:self";
    for (const usc::Json& row : scenario.at("identities").items())
        agent.identities.push_back(row);

    usc::OrderedMap<double> threat;
    for (const auto& entry : scenario.at("threat").fields())
        threat[entry.first] = entry.second.as_double();

    usc::IdentityEngine engine;
    usc::Json rounds = usc::Json::array();
    for (long long round = 0; round < scenario.get("rounds").as_int(1); ++round) {
        std::string winner = engine.salience(agent, scenario.at("context"), threat);
        usc::Json row = usc::Json::object();
        row["winner"] = winner;
        row["salience"] = numbers_json(agent.identity_salience);
        rounds.push(row);
    }
    usc::Json out = usc::Json::object();
    out["rounds"] = rounds;
    return out;
}

// ---- the constants, which are a copy and therefore drift -------------------

/// Dump every single-source-of-truth constant so the Python side can compare
/// them WORD FOR WORD. `OPTIONAL_LAYERS` exists because three copies of the
/// layer list came to disagree about what exists; a second implementation is a
/// fourth copy, and this is the only thing standing between it and the same
/// failure.
usc::Json run_contracts(const usc::Json&) {
    usc::Json out = usc::Json::object();
    out["runtime_version"] = std::string(usc::RUNTIME_VERSION);
    out["default_player_id"] = std::string(usc::DEFAULT_PLAYER_ID);

    usc::Json layers = usc::Json::array();
    for (const auto& entry : usc::optional_layers()) {
        usc::Json row = usc::Json::array();
        row.push(usc::Json(entry.first));
        row.push(usc::Json(entry.second));
        layers.push(row);
    }
    out["optional_layers"] = layers;

    usc::Json requires_ = usc::Json::object();
    for (const auto& entry : usc::layer_requires())
        requires_.fields()[entry.first] = usc::Json(entry.second);
    out["layer_requires"] = requires_;

    usc::Json authored = usc::Json::object();
    for (const auto& entry : usc::authored_only_fields())
        authored.fields()[entry.first] = usc::Json(entry.second);
    out["authored_only_fields"] = authored;

    // And the defaults, because "off is exactly neutral" is only true if off is
    // what a fresh config actually gives you.
    usc::RuntimeConfig config;
    usc::Json defaults = usc::Json::object();
    defaults["runtime_id"] = config.runtime_id;
    defaults["schema_version"] = config.schema_version;
    defaults["world_pack_path"] = config.world_pack_path;
    defaults["storage_path"] = config.storage_path;
    defaults["debug_traces"] = config.debug_traces;
    defaults["strict"] = config.strict;
    defaults["player_id"] = config.player_id;
    defaults["player_start_location"] = config.player_start_location
        ? usc::Json(*config.player_start_location) : usc::Json();
    defaults["load_initial_state"] = config.load_initial_state;
    defaults["population_lod"] = config.population_lod;
    defaults["action_timeout_minutes"] = config.action_timeout_minutes;
    defaults["voice_backend"] = config.voice_backend;
    defaults["voice_model"] = config.voice_model
        ? usc::Json(*config.voice_model) : usc::Json();
    defaults["projection_scope"] = config.projection_scope;
    defaults["canon_mode"] = config.canon_mode;
    usc::Json off = usc::Json::object();
    for (const auto& entry : usc::optional_layers())
        off.fields()[entry.first] = usc::Json(config.layer(entry.first));
    defaults["layers_off_by_default"] = off;
    out["config_defaults"] = defaults;

    // `set_layer` and `layer` are a hand-written switch over nine names, which
    // is exactly the shape that quietly forgets one.
    usc::Json roundtrip = usc::Json::object();
    for (const auto& entry : usc::optional_layers()) {
        usc::RuntimeConfig one;
        one.set_layer(entry.first, true);
        bool only_this = true;
        for (const auto& other : usc::optional_layers())
            if (one.layer(other.first) != (other.first == entry.first)) only_this = false;
        roundtrip.fields()[entry.first] = usc::Json(only_this);
    }
    out["set_layer_sets_exactly_one"] = roundtrip;
    return out;
}

// ---- round-trip, and pack-declared predicates ------------------------------

/// Serialise, restore, serialise again. The second blob must equal the first.
usc::Json run_roundtrip(const usc::Json& scenario) {
    const usc::Json& blob = scenario.at("blob");
    // `at()`, not `get()`. `get()` hands back a copy, and binding a reference
    // into the string inside it leaves that reference dangling the moment the
    // full expression ends -- which compiles, runs, and produced the right
    // answer here until AddressSanitizer was pointed at it. Second time this
    // exact trap appeared in this probe; the first is the reason `at()` exists.
    const std::string& kind = scenario.at("kind").as_string();
    usc::Json out = usc::Json::object();
    if (kind == "belief") {
        out["restored"] = usc::Belief::from_json(blob).as_json();
    } else if (kind == "memory") {
        out["restored"] = usc::MemoryItem::from_json(blob).as_json();
    } else {
        out["restored"] = usc::AffectState::from_json(blob).as_json();
    }
    return out;
}

usc::Json run_predicates(const usc::Json& scenario) {
    usc::reset_predicates();
    usc::Json accepted = usc::Json::array();
    for (const usc::Json& row : scenario.at("register").items()) {
        usc::PredicateSpec spec;
        for (const usc::Json& slot : row.at("slots").items())
            spec.slots.push_back(slot.as_string());
        const usc::Json& functional = row.at("functional_in");
        if (!functional.is_null()) spec.functional_in = static_cast<int>(functional.as_int());
        usc::register_predicate(row.get("name").as_string(), spec, "probe pack");
        accepted.push(row.get("name"));
    }

    // Each of these must be refused. WHICH ones are refused is the assertion --
    // the message text is not compared, because two implementations may word it
    // differently and neither is wrong.
    usc::Json refused = usc::Json::array();
    for (const usc::Json& row : scenario.at("conflicts").items()) {
        usc::PredicateSpec spec;
        for (const usc::Json& slot : row.at("slots").items())
            spec.slots.push_back(slot.as_string());
        const usc::Json& functional = row.at("functional_in");
        if (!functional.is_null()) spec.functional_in = static_cast<int>(functional.as_int());
        bool raised = false;
        try {
            usc::register_predicate(row.get("name").as_string(), spec, "other pack");
        } catch (const std::exception&) {
            raised = true;
        }
        usc::Json entry = usc::Json::object();
        entry["name"] = row.get("name");
        entry["refused"] = raised;
        refused.push(entry);
    }

    // And the core keys the newly registered predicates produce, which is the
    // whole reason the conflict check exists.
    usc::Json keys = usc::Json::array();
    for (const usc::Json& row : scenario.at("core_keys").items())
        keys.push(usc::Json(usc::Proposition::from_json(row).core_key()));

    usc::reset_predicates();
    usc::Json out = usc::Json::object();
    out["accepted"] = accepted;
    out["refused"] = refused;
    out["core_keys"] = keys;
    return out;
}

// ---- grounding -------------------------------------------------------------

usc::Json interp_reasons_json(const std::vector<usc::Reason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json alias_entries_json(const usc::AliasIndex& index) {
    usc::Json out = usc::Json::array();
    for (const auto& entry : index.entries) {
        usc::Json pair = usc::Json::array();
        pair.push(entry.first);
        pair.push(entry.second);
        out.push(pair);
    }
    return out;
}

usc::Json parsed_command_json(const usc::ParsedCommand& command) {
    usc::Json out = usc::Json::object();
    out["raw_text"] = command.raw_text;
    out["intent"] = command.intent;
    out["confidence"] = command.confidence;
    out["actor_id"] = command.actor_id;
    out["target_id"] = command.target_id;
    out["location_id"] = command.location_id;
    out["proposition"] = command.proposition ? command.proposition->as_json() : usc::Json();
    out["amount"] = command.amount;
    out["minutes"] = command.minutes;
    out["topic"] = command.topic;
    out["metadata"] = command.metadata;
    usc::Json reasons = usc::Json::array();
    for (const usc::Json& reason : command.reasons) reasons.push(reason);
    out["reasons"] = reasons;
    return out;
}

usc::Event runtime_event(const usc::Json& row) {
    usc::Event ev;
    ev.event_id = row.get("event_id").as_int();
    ev.world_time = row.get("world_time").as_int();
    ev.type = row.at("type").as_string();
    ev.actor = row.get("actor");
    ev.location = row.get("location");
    ev.payload = row.get("payload");
    if (!ev.payload.truthy()) ev.payload = usc::Json::object();
    return ev;
}

usc::Json plain_reasons(const std::vector<usc::Reason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const usc::Reason& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json trace_map_json(const usc::TraceMap& traces) {
    usc::Json out = usc::Json::object();
    for (const auto& entry : traces) out[entry.first] = plain_reasons(entry.second);
    return out;
}

usc::Json agent_dump(const usc::Agent& agent) {
    usc::Json out = usc::Json::object();
    out["location"] = agent.location();
    usc::Json beliefs = usc::Json::object();
    for (const auto& entry : agent.beliefs) beliefs[entry.first] = entry.second.as_json();
    out["beliefs"] = beliefs;
    usc::Json memory = usc::Json::array();
    for (const auto& item : agent.memory) memory.push(item->as_json());
    out["memory"] = memory;
    out["affect"] = agent.affect.as_json();
    usc::Json relationships = usc::Json::object();
    for (const auto& entry : agent.relationships) {
        usc::Json row = usc::Json::object();
        for (const auto& field : entry.second) row[field.first] = field.second;
        relationships[entry.first] = row;
    }
    out["relationships"] = relationships;
    usc::Json reputation = usc::Json::object();
    for (const auto& entry : agent.reputation) {
        usc::Json row = usc::Json::object();
        for (const auto& field : entry.second) row[field.first] = field.second;
        reputation[entry.first] = row;
    }
    out["reputation"] = reputation;
    usc::Json threat = usc::Json::object();
    for (const auto& entry : agent.identity_threat) threat[entry.first] = entry.second;
    out["identity_threat"] = threat;
    usc::Json salience = usc::Json::object();
    for (const auto& entry : agent.identity_salience) salience[entry.first] = entry.second;
    out["identity_salience"] = salience;
    out["attention_day"] = agent.attention_day;
    out["attention_spent"] = agent.attention_spent;
    return out;
}

usc::Json runtime_dump(const usc::World& world, usc::Runtime& rt) {
    usc::Json out = usc::Json::object();
    out["world_time"] = world.world_time;
    out["next_event_id"] = world.peek_event_id();
    usc::Json scheduled = usc::Json::array();
    for (const usc::Event& e : world.scenario_events) {
        usc::Json row = usc::Json::object();
        row["event_id"] = e.event_id;
        row["world_time"] = e.world_time;
        row["type"] = e.type;
        row["actor"] = e.actor;
        row["location"] = e.location;
        row["payload"] = e.payload;
        scheduled.push(row);
    }
    out["scenario_events"] = scheduled;
    usc::Json agents = usc::Json::object();
    for (const auto& entry : world.agents) agents[entry.first] = agent_dump(entry.second);
    out["agents"] = agents;
    out["traces"] = trace_map_json(rt.last_traces);
    out["actions"] = rt.actions_out.as_json();
    out["climate"] = rt.climate.as_json();
    out["promises"] = rt.promises.as_json();
    out["notes"] = rt.notes.as_json();
    out["common_knowledge"] = rt.common_knowledge.as_json();
    out["pursuit"] = rt.pursuit.as_json();
    usc::Json decay = usc::Json::object();
    for (const auto& entry : rt.last_decay()) decay[entry.first] = entry.second;
    out["last_decay"] = decay;
    usc::Json factions = usc::Json::object();
    for (const auto& entry : rt.director.factions()) factions[entry.first] = entry.second.as_json();
    out["director"] = factions;
    return out;
}

std::string& pack_root() {
    static std::string root = "../../../worldpacks";
    return root;
}

/// Where the probe's own fixtures live: the directory the cases file is in.
std::string& probe_root() {
    static std::string root = ".";
    return root;
}

usc::Json pack_world_dump(const usc::World& w) {
    auto numbers = [](const usc::OrderedMap<double>& values) {
        usc::Json out = usc::Json::object();
        for (const auto& entry : values) out[entry.first] = entry.second;
        return out;
    };
    auto strings = [](const std::vector<std::string>& values) {
        usc::Json out = usc::Json::array();
        for (const std::string& one : values) out.push(one);
        return out;
    };

    usc::Json out = usc::Json::object();
    out["global_seed"] = w.global_seed;
    out["world_time"] = w.world_time;
    out["places"] = w.places;
    out["entities"] = w.entities;
    out["channels"] = w.channels;
    out["identity_values"] = w.identity_values;
    out["command_aliases"] = w.command_aliases;
    out["standing_conduct"] = w.standing_conduct;
    out["appearance_reactions"] = w.appearance_reactions;
    out["dialogue_templates"] = w.dialogue_templates;
    out["slang_lexicon"] = w.slang_lexicon;
    out["diffusion_params"] = w.diffusion_params;
    out["tuning"] = w.tuning;
    out["routine_params"] = w.routine_params;
    out["predicate_domains"] = w.predicate_domains;
    out["predicate_competence"] = w.predicate_competence;
    out["predicates"] = w.predicates;
    out["canon_facts"] = w.canon_facts;

    usc::Json topics = usc::Json::object();
    for (const auto& entry : w.topics) {
        const usc::Topic& t = entry.second;
        usc::Json row = usc::Json::object();
        row["id"] = t.topic_id;
        row["label"] = t.label;
        row["aliases"] = strings(t.aliases);
        row["query"] = t.query;
        row["player_claim"] = t.player_claim;
        row["player_assertion"] = t.player_assertion;
        usc::Json reactions = usc::Json::array();
        for (const usc::Json& one : t.reactions) reactions.push(one);
        row["reactions"] = reactions;
        row["phrasings"] = t.phrasings;
        topics[entry.first] = row;
    }
    out["topics"] = topics;

    usc::Json agents = usc::Json::object();
    for (const auto& entry : w.agents) {
        const usc::Agent& a = entry.second;
        usc::Json row = usc::Json::object();
        row["big_five"] = numbers(a.big_five);
        row["schwartz"] = numbers(a.schwartz);
        row["needs"] = numbers(a.needs);
        usc::Json identities = usc::Json::array();
        for (const usc::Json& one : a.identities) identities.push(one);
        row["identities"] = identities;
        usc::Json roles = usc::Json::array();
        for (const usc::Json& one : a.roles) roles.push(one);
        row["roles"] = roles;
        row["appearance"] = a.appearance;
        row["education"] = numbers(a.education);
        usc::Json relationships = usc::Json::object();
        for (const auto& rel : a.relationships) relationships[rel.first] = numbers(rel.second);
        row["relationships"] = relationships;
        usc::Json secrets = usc::Json::array();
        for (const usc::Json& one : a.secrets)
            secrets.push(usc::Secret::from_json(one).avoid_label);
        row["secrets"] = secrets;
        usc::Json goals = usc::Json::array();
        for (const usc::Json& one : a.goals) goals.push(one);
        row["goals"] = goals;
        row["location"] = a.location();
        row["public_name"] = a.public_name;
        row["objective_name"] = a.objective_name;
        row["aliases"] = strings(a.aliases);
        usc::Json routine = usc::Json::array();
        // NAMED, not `Routine::from_json(...).blocks()` in the range expression:
        // C++17 extends the lifetime of the range expression itself and not of
        // the temporary a sub-expression returns, so the vector being iterated
        // would already be destroyed. Third time this trap has appeared in this
        // port, and the first two also read as "the data is simply missing".
        usc::Routine parsed = usc::Routine::from_json(a.routine);
        for (const usc::RoutineBlock& block : parsed.blocks()) {
            usc::Json one = usc::Json::array();
            one.push(block.start);
            one.push(block.place);
            one.push(block.activity);
            routine.push(one);
        }
        row["routine"] = routine;
        row["social_status"] = a.social_status;
        row["resources"] = a.resources;
        row["dialect"] = a.dialect;
        row["values"] = numbers(a.values);
        row["epistemic"] = a.epistemic;
        row["networks"] = strings(a.networks);
        row["voice"] = a.voice;
        row["contacts"] = strings(a.contacts);
        row["affect"] = a.affect.as_json();
        agents[entry.first] = row;
    }
    out["agents"] = agents;

    usc::Json exposure = usc::Json::array();
    for (const auto& entry : w.media_exposure) {
        std::size_t split = entry.first.find('\x1f');
        usc::Json row = usc::Json::object();
        row["agent"] = entry.first.substr(0, split);
        row["channel"] = entry.first.substr(split + 1);
        row["value"] = entry.second;
        exposure.push(row);
    }
    out["media_exposure"] = exposure;

    usc::Json factions = usc::Json::array();
    for (const usc::Json& one : w.factions) factions.push(one);
    out["factions"] = factions;

    usc::Json events = usc::Json::array();
    for (const usc::Event& e : w.scenario_events) {
        usc::Json row = usc::Json::object();
        row["event_id"] = e.event_id;
        row["world_time"] = e.world_time;
        row["type"] = e.type;
        row["actor"] = e.actor;
        row["location"] = e.location;
        row["payload"] = e.payload;
        row["canonical"] = e.canonical;
        events.push(row);
    }
    out["scenario_events"] = events;
    out["scenario_intro"] = w.scenario_intro;
    out["focus_agents"] = strings(w.focus_agents);
    out["player_start"] = w.player_start;
    out["initial_beliefs"] = w.initial_beliefs;
    out["next_event_id"] = w.peek_event_id();
    return out;
}

usc::Json run_metahuman(const usc::Json& scenario) {
    usc::Json faces = usc::Json::array();
    for (const usc::Json& row : scenario.at("cases").items()) {
        auto vec = [](const usc::Json& parts) {
            return usc::Vec3{parts.items()[0].as_double(), parts.items()[1].as_double(),
                             parts.items()[2].as_double()};
        };
        usc::AffectState affect;
        affect.mood = vec(row.at("mood"));
        affect.baseline = vec(row.at("baseline"));
        for (const auto& e : row.at("emotions").fields())
            affect.active_emotions[e.first] = e.second.as_double();
        usc::OrderedMap<double> tendencies;
        for (const auto& e : row.at("tendencies").fields())
            tendencies[e.first] = e.second.as_double();

        usc::Json entry = usc::Json::object();
        entry["note"] = row.at("note");
        entry["blendshapes"] = usc::metahuman::affect_to_blendshapes(affect);
        auto dominant = usc::metahuman::dominant_emotion(affect);
        usc::Json pair = usc::Json::array();
        pair.push(dominant.first);
        pair.push(dominant.second);
        entry["dominant"] = pair;
        entry["face"] = usc::metahuman::affect_to_face(
            affect, tendencies.empty() ? nullptr : &tendencies,
            usc::Json(std::string("agent:player_1")));
        faces.push(entry);
    }
    usc::Json out = usc::Json::object();
    out["faces"] = faces;
    return out;
}

usc::Json run_sdk(const usc::Json& scenario) {
    usc::Json out = usc::Json::object();
    for (const usc::Json& row : scenario.at("runs").items()) {
        usc::reset_predicates();
        usc::RuntimeConfig config;
        const usc::Json* elsewhere = row.find("root");
        config.world_pack_path = elsewhere
            ? probe_root() + "/" + elsewhere->as_string() + "/"
              + row.at("pack").as_string()
            : pack_root() + "/" + row.at("pack").as_string();
        config.storage_path = ":memory:";
        for (const usc::Json& layer : row.at("layers").items())
            config.set_layer(layer.as_string(), true);

        std::vector<std::string> characters;
        for (const usc::Json& name : row.at("characters").items())
            characters.push_back(name.as_string());
        usc::World world = usc::load_world_pack(config.world_pack_path, characters);

        usc::UnscriptedRuntime sdk(config, world);
        sdk.attach();
        // The seed belongs to the WORLD, and is pinned after the pack is in
        // place -- exactly where the conformance driver pins it.
        world.global_seed = row.at("seed").as_string();

        usc::Json transcript = usc::Json::array();
        for (const usc::Json& command : row.at("commands").items()) {
            usc::TurnResult result = sdk.submit_player_text(command.as_string());
            usc::Json entry = usc::Json::object();
            entry["input"] = command;
            entry["message"] = usc::py_strip(result.message);
            entry["intent"] = result.parsed.intent;
            entry["target"] = result.parsed.target_id;
            entry["topic"] = result.parsed.topic;
            entry["world_time"] = result.world_time;
            entry["next_event_id"] = world.peek_event_id();
            entry["location"] = result.location_id;
            usc::Json receipts = usc::Json::array();
            for (const usc::EventReceipt& r : result.receipts) {
                usc::Json one = usc::Json::object();
                one["event_id"] = r.event_id;
                one["type"] = r.event_type;
                usc::Json seen = usc::Json::array();
                for (const std::string& who : r.observed_by) seen.push(who);
                one["observed_by"] = seen;
                receipts.push(one);
            }
            entry["receipts"] = receipts;
            if (result.npc_response) {
                usc::Json npc = usc::Json::object();
                npc["text"] = result.npc_response->text;
                npc["act"] = result.npc_response->act;
                npc["verdict"] = result.npc_response->verdict;
                usc::Json reasons = usc::Json::array();
                for (const usc::Json& one : result.npc_response->reasons) reasons.push(one);
                npc["reasons"] = reasons;
                entry["npc"] = npc;
            } else {
                entry["npc"] = usc::Json();
            }
            transcript.push(entry);
        }

        usc::Json agents = usc::Json::object();
        std::vector<std::string> ids;
        for (const auto& who : world.agents) ids.push_back(who.first);
        std::sort(ids.begin(), ids.end());
        for (const std::string& aid : ids)
            agents[aid] = usc::state_view::agent_state(sdk, aid);
        usc::Json views = usc::Json::object();
        views["world"] = usc::state_view::world_state(sdk);
        views["scene"] = usc::state_view::scene_state(sdk);
        views["knowledge"] = usc::state_view::knowledge_state(sdk);
        views["agents"] = agents;

        usc::Json entry = usc::Json::object();
        entry["transcript"] = transcript;
        entry["state"] = sdk.export_state();
        entry["views"] = views;
        out[row.at("id").as_string()] = entry;
    }
    usc::reset_predicates();
    return out;
}

usc::Json run_pack_loader(const usc::Json& scenario) {
    usc::Json out = usc::Json::object();
    for (const usc::Json& row : scenario.at("packs").items()) {
        usc::reset_predicates();
        std::vector<std::string> characters;
        for (const usc::Json& name : row.at("characters").items())
            characters.push_back(name.as_string());
        // Where the shipped packs live, relative to the cases file the probe was
        // handed. Passed rather than compiled in, so the probe can be run from
        // anywhere.
        const usc::Json* elsewhere = row.find("root");
        std::string root = elsewhere
            ? probe_root() + "/" + elsewhere->as_string() + "/"
              + row.at("pack").as_string()
            : pack_root() + "/" + row.at("pack").as_string();
        usc::World world = usc::load_world_pack(root, characters);
        usc::Json entry = usc::Json::object();
        entry["world"] = pack_world_dump(world);
        std::vector<std::string> names;
        for (const auto& source : usc::predicate_sources()) names.push_back(source.first);
        std::sort(names.begin(), names.end());
        usc::Json registered = usc::Json::array();
        for (const std::string& name : names) registered.push(name);
        entry["registered"] = registered;
        out[row.at("pack").as_string()] = entry;
    }
    usc::reset_predicates();
    return out;
}

usc::Json run_inspect(const usc::Json& scenario) {
    long long t = scenario.get("world_time").as_int();
    usc::Json views = usc::Json::array();
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.at("id").as_string();
        const usc::Json& a = row.at("affect");
        auto vec = [](const usc::Json& parts) {
            return usc::Vec3{parts.items()[0].as_double(), parts.items()[1].as_double(),
                             parts.items()[2].as_double()};
        };
        agent.affect.mood = vec(a.at("mood"));
        agent.affect.baseline = vec(a.at("baseline"));
        for (const auto& e : a.at("active_emotions").fields())
            agent.affect.active_emotions[e.first] = e.second.as_double();
        for (const usc::Json& b : row.at("beliefs").items()) {
            usc::Proposition claim;
            claim.predicate = b.at("predicate").as_string();
            for (const auto& slot : b.at("slots").fields())
                claim.slots[slot.first] = slot.second;
            usc::Belief belief;
            belief.proposition = claim;
            for (const usc::Json& p : b.at("provenance").items()) {
                usc::ProvenanceEntry entry;
                entry.claim_id = p.get("claim_id");
                entry.origin_event = p.get("origin_event");
                entry.kappa = p.get("kappa").as_double();
                entry.eta = p.get("eta").as_double();
                belief.provenance.push_back(entry);
                belief.support_for += entry.kappa * entry.eta;
            }
            agent.beliefs[claim.core_key()] = belief;
        }
        for (const usc::Json& m : row.at("memory").items()) {
            auto item = std::make_shared<usc::MemoryItem>();
            item->memory_id = m.at("memory_id").as_string();
            item->owner = agent.id;
            item->type = m.at("type").as_string();
            item->content = m.at("content").as_string();
            item->importance = m.get("importance").as_double();
            item->emotional_valence = m.get("emotional_valence").as_double();
            item->source_conf = m.get("source_conf").as_double();
            item->world_time = m.get("world_time");
            agent.memory.push_back(item);
        }
        usc::Json view = usc::Json::object();
        view["agent"] = agent.id;
        view["beliefs"] = usc::format_beliefs(agent);
        view["memory"] = usc::format_memory(agent, t);
        view["affect"] = usc::format_affect(agent);
        views.push(view);
    }

    usc::World empty;
    usc::Runtime runtime(empty);
    for (const auto& entry : scenario.at("traces").fields()) {
        std::vector<usc::Reason> rows;
        for (const usc::Json& row : entry.second.items())
            rows.push_back({row.items()[0].as_string(), row.items()[1].as_double(),
                            row.items()[2]});
        runtime.last_traces[entry.first] = rows;
    }
    usc::Json traces = usc::Json::array();
    for (const char* aid : {"agent:busy", "agent:blank", "agent:missing"}) {
        usc::Json row = usc::Json::object();
        row["agent"] = std::string(aid);
        row["text"] = usc::format_last_trace(runtime, aid);
        traces.push(row);
    }

    usc::Json tuples = usc::Json::array();
    for (const usc::Json& row : scenario.at("tuples").items()) {
        usc::Json as_tuple = usc::Json::tuple();
        for (const usc::Json& one : row.items()) as_tuple.push(one);
        tuples.push(usc::py_repr(as_tuple));
    }

    usc::Json out = usc::Json::object();
    out["views"] = views;
    out["traces"] = traces;
    out["tuples"] = tuples;
    return out;
}

usc::Json run_snapshot(const usc::Json& scenario) {
    usc::Json digests = usc::Json::array();
    for (const usc::Json& text : scenario.at("sha256").items())
        digests.push(usc::sha256_hex(text.as_string()));

    const usc::Json& setup = scenario.at("world");
    usc::World world;
    world.global_seed = setup.at("global_seed").as_string();
    for (const usc::Json& aid : setup.at("agents").items()) {
        usc::Agent agent;
        agent.id = aid.as_string();
        world.agents[agent.id] = agent;
    }
    usc::Json places = usc::Json::object();
    for (const usc::Json& pid : setup.at("places").items())
        places[pid.as_string()] = usc::Json::object();
    world.places = places;
    for (const usc::Json& tid : setup.at("topics").items()) {
        usc::Json row = usc::Json::object();
        row["id"] = tid;
        usc::Topic topic = usc::Topic::from_json(row);
        world.topics[topic.topic_id] = topic;
    }
    std::string fingerprint = usc::world_fingerprint(world);

    std::vector<std::string> names;
    for (const auto& entry : world.agents) names.push_back(entry.first);
    std::sort(names.begin(), names.end());
    usc::Json listed = usc::Json::array();
    for (const std::string& one : names) listed.push(one);

    usc::Json base = usc::Json::object();
    base["format"] = std::string("unscripted-state");
    base["format_version"] = 1LL;
    base["runtime_version"] = std::string("probe");
    base["snapshot_schema_version"] = 10LL;
    base["world_fingerprint"] = fingerprint;
    base["agents"] = listed;
    base["world_time"] = 1234LL;
    usc::Json payload = usc::Json::object();
    payload["world_time"] = 1234LL;
    base["state"] = payload;

    usc::Json checked = usc::Json::array();
    for (const usc::Json& change : scenario.at("variants").items()) {
        usc::Json blob = base.copy();
        for (const auto& field : change.fields()) {
            if (field.first == "note" || field.first == "not_an_object") continue;
            blob[field.first] = field.second;
        }
        if (change.find("not_an_object")) {
            blob = usc::Json::array();
            blob.push(std::string("not"));
            blob.push(std::string("an"));
            blob.push(std::string("object"));
        }
        usc::Json entry = usc::Json::object();
        entry["note"] = change.at("note");
        entry["report"] = usc::inspect_state(blob, world);
        checked.push(entry);
    }

    usc::Json out = usc::Json::object();
    out["sha256"] = digests;
    out["fingerprint"] = fingerprint;
    out["variants"] = checked;
    return out;
}

usc::Json run_runtime(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    world.places = scenario.at("places");
    world.channels = scenario.at("channels");
    world.predicate_domains = scenario.at("predicate_domains");
    world.predicate_competence = scenario.at("predicate_competence");
    world.predicates = scenario.at("predicates");
    world.identity_values = scenario.at("identity_values");
    for (const usc::Json& f : scenario.at("factions").items()) world.factions.push_back(f);
    world.standing_conduct = scenario.at("standing_conduct");
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.at("id").as_string();
        agent.set_location(row.get("location"));
        agent.public_name = row.get("public_name");
        for (const auto& e : row.at("education").fields())
            agent.education[e.first] = e.second.as_double();
        agent.epistemic = row.at("epistemic");
        for (const auto& e : row.at("big_five").fields())
            agent.big_five[e.first] = e.second.as_double();
        for (const auto& e : row.at("relationships").fields()) {
            usc::OrderedMap<double> values;
            for (const auto& f : e.second.fields()) values[f.first] = f.second.as_double();
            agent.relationships[e.first] = values;
        }
        for (const usc::Json& one : row.at("identities").items())
            agent.identities.push_back(one);
        for (const usc::Json& one : row.at("roles").items()) agent.roles.push_back(one);
        agent.routine = row.at("routine");
        for (const usc::Json& one : row.at("goals").items()) agent.goals.push_back(one);
        for (const usc::Json& one : row.at("aliases").items())
            agent.aliases.push_back(one.as_string());
        // `__post_init__`: mood and baseline derived from personality. Setting
        // `big_five` field by field walks straight past it, which leaves every
        // character starting from a flat zero mood.
        agent.initialise_affect();
        world.agents[agent.id] = agent;
    }

    for (const usc::Json& row : scenario.at("media_exposure").items())
        world.set_exposure(row.at("agent").as_string(), row.at("channel").as_string(),
                           row.at("value"));

    usc::Runtime rt(world);
    usc::Json log = usc::Json::array();
    usc::Json dumps = usc::Json::array();
    std::string last_intent;

    for (const usc::Json& step : scenario.at("steps").items()) {
        std::string kind = step.at("do").as_string();
        usc::Json row = usc::Json::object();
        row["step"] = kind;
        if (kind == "process_event") {
            row["traces"] = trace_map_json(rt.process_event(runtime_event(step.at("event"))));
        } else if (kind == "player_says") {
            row["traces"] = trace_map_json(rt.player_says(
                step.at("speaker").as_string(), step.get("location"),
                usc::Proposition::from_json(step.at("proposition")),
                step.get("summary"), usc::Json::object(),
                step.get("importance").as_double()));
        } else if (kind == "advance_time") {
            rt.advance_time(step.get("delta").as_int());
            row["delta"] = step.get("delta");
        } else if (kind == "enable_layers") {
            rt.standing.set_enabled(true);
            rt.climate.set_enabled(true);
            rt.pursuit.set_enabled(true);
            rt.pursuit.set_notes(step.get("notes").truthy());
            rt.contagion.set_enabled(true);
            rt.common_knowledge.set_enabled(true);
            rt.notes.set_enabled(true);
            rt.promises.set_enabled(true);
            rt.actions_out.enabled = true;
        } else if (kind == "inspect") {
            usc::Json views = usc::Json::array();
            for (const usc::Json& aid : step.at("agents").items()) {
                const usc::Agent* agent = world.agents.find(aid.as_string());
                usc::Json view = usc::Json::object();
                view["agent"] = aid;
                view["beliefs"] = agent ? usc::Json(usc::format_beliefs(*agent))
                                        : usc::Json();
                view["memory"] = agent
                    ? usc::Json(usc::format_memory(*agent, world.world_time))
                    : usc::Json();
                view["affect"] = agent ? usc::Json(usc::format_affect(*agent))
                                       : usc::Json();
                view["trace"] = usc::format_last_trace(rt, aid.as_string());
                views.push(view);
            }
            row["views"] = views;
        } else if (kind == "export") {
            row["blob"] = usc::export_state(world, rt);
        } else if (kind == "round_trip") {
            usc::Json saved = usc::export_state(world, rt);
            rt.advance_time(step.get("delta").as_int());
            rt.process_event(runtime_event(step.at("event")));
            const usc::Json& say = step.at("say");
            rt.player_says(say.at("speaker").as_string(), say.get("location"),
                           usc::Proposition::from_json(say.at("proposition")),
                           say.get("summary"), usc::Json::object(),
                           say.get("importance").as_double());
            usc::ImportResult back = usc::import_state(saved, world, rt);
            row["report"] = back.report;
            row["reasons"] = plain_reasons(back.reasons);
        } else if (kind == "restore_variants") {
            usc::Json saved = usc::capture(world, rt);
            usc::Json seen = usc::Json::array();
            for (const usc::Json& change : step.at("changes").items()) {
                usc::Json blob = saved.copy();
                for (const usc::Json& drop : change.at("drop").items())
                    blob.fields().erase(drop.as_string());
                for (const auto& field : change.fields()) {
                    if (field.first == "drop" || field.first == "note"
                        || field.first == "forget_agent"
                        || field.first == "forget_agents"
                        || field.first == "invent_agent") continue;
                    blob[field.first] = field.second;
                }
                std::vector<std::string> gone;
                if (const usc::Json* many = change.find("forget_agents"))
                    for (const usc::Json& one : many->items())
                        gone.push_back(one.as_string());
                if (const usc::Json* forget = change.find("forget_agent"))
                    gone.push_back(forget->as_string());
                if (!gone.empty()) {
                    usc::Json agents = blob.at("agents").copy();
                    for (const std::string& one : gone) agents.fields().erase(one);
                    blob["agents"] = agents;
                }
                if (const usc::Json* invent = change.find("invent_agent")) {
                    usc::Json agents = blob.at("agents").copy();
                    agents[invent->as_string()] = usc::Json::object();
                    blob["agents"] = agents;
                }
                usc::Json entry = usc::Json::object();
                entry["note"] = change.at("note");
                entry["reasons"] = plain_reasons(usc::restore(blob, world, rt));
                usc::Json decay = usc::Json::object();
                for (const auto& mark : rt.last_decay()) decay[mark.first] = mark.second;
                entry["last_decay"] = decay;
                entry["next_event_id"] = world.peek_event_id();
                entry["scheduled"] = static_cast<long long>(world.scenario_events.size());
                seen.push(entry);
            }
            usc::restore(saved, world, rt);
            row["variants"] = seen;
        } else if (kind == "import_variants") {
            usc::Json base = usc::export_state(world, rt);
            usc::Json seen = usc::Json::array();
            std::vector<std::pair<std::string, usc::Json>> changes = {
                {"format", usc::Json(std::string("nope"))},
                {"format_version", usc::Json(99LL)},
                {"snapshot_schema_version", usc::Json(99LL)},
                {"world_fingerprint", usc::Json(std::string("0000000000000000"))},
                {"agents", usc::Json()}};
            changes.back().second = usc::Json::array();
            changes.back().second.push(std::string("agent:nobody"));
            for (const auto& change : changes) {
                // `dict(base)` -- assigning would ALIAS the object and every
                // later variant would inherit the previous one's damage.
                usc::Json blob = base.copy();
                blob[change.first] = change.second;
                usc::Json entry = usc::Json::object();
                usc::Json named = usc::Json::array();
                named.push(change.first);
                entry["change"] = named;
                entry["report"] = usc::inspect_state(blob, world);
                try {
                    usc::ImportResult back = usc::import_state(blob, world, rt);
                    entry["reasons"] = plain_reasons(back.reasons);
                } catch (const usc::StateImportError& error) {
                    entry["error"] = std::string(error.what());
                }
                seen.push(entry);
            }
            row["variants"] = seen;
        } else if (kind == "schedule") {
            world.scenario_events.push_back(runtime_event(step.at("event")));
            row["event_id"] = step.at("event").get("event_id");
        } else if (kind == "population_lod") {
            rt.population_lod = true;
        } else if (kind == "issue_intent") {
            usc::Json params = usc::Json::object();
            params["place"] = step.get("place");
            params["activity"] = step.get("activity");
            usc::ActionIntent intent = rt.actions_out.issue(
                step.at("actor").as_string(), "MOVE_TO", params, "probe",
                world.world_time);
            last_intent = intent.intent_id;
            row["intent"] = intent.as_json();
        } else if (kind == "resolve_action") {
            try {
                row["result"] = rt.resolve_action(last_intent, step.at("status").as_string());
            } catch (const usc::UnknownIntent&) {
                row["error"] = std::string("UnknownIntent");
            } catch (const usc::InvalidResult&) {
                row["error"] = std::string("InvalidResult");
            } catch (const std::invalid_argument&) {
                row["error"] = std::string("ValueError");
            }
        } else if (kind == "decide") {
            usc::Runtime::Decision decision = rt.decide(
                step.at("agent").as_string(), step.at("interlocutor").as_string(),
                step.get("situation"));
            row["chosen"] = decision.chosen.action.action_id;
            row["utility"] = decision.chosen.utility;
            usc::Json scored = usc::Json::array();
            for (const usc::ActionCandidate& one : decision.scored) {
                usc::Json entry = usc::Json::object();
                entry["action"] = one.action.action_id;
                entry["utility"] = one.utility;
                usc::Json contributions = usc::Json::array();
                for (const auto& c : one.contributions) {
                    usc::Json tuple = usc::Json::array();
                    tuple.push(std::get<0>(c));
                    tuple.push(std::get<1>(c));
                    tuple.push(std::get<2>(c));
                    tuple.push(std::get<3>(c));
                    contributions.push(tuple);
                }
                entry["contributions"] = contributions;
                scored.push(entry);
            }
            row["scored"] = scored;
            row["reasons"] = plain_reasons(decision.reasons);
        } else if (kind == "say") {
            usc::Runtime::Spoken spoken = rt.say(step.at("agent").as_string(),
                                                 step.at("interlocutor").as_string());
            row["text"] = spoken.text;
            row["act"] = spoken.act;
            row["style"] = spoken.style;
            row["utility"] = spoken.utility;
            row["verdict"] = spoken.verdict;
            row["salient_identity"] = spoken.salient_identity;
            row["reasons"] = plain_reasons(spoken.reasons);
        } else if (kind == "mobilize") {
            usc::Runtime::Mobilized out = rt.mobilize(step.at("agent").as_string());
            usc::Json who = usc::Json::array();
            for (const usc::AllyResponse& r : out.responders) who.push(r.ally_id);
            row["responders"] = who;
            row["reasons"] = plain_reasons(out.reasons);
        } else if (kind == "dump") {
            dumps.push(runtime_dump(world, rt));
        }
        log.push(row);
    }

    usc::Json out = usc::Json::object();
    out["log"] = log;
    out["dumps"] = dumps;
    return out;
}

usc::Json run_provider(const usc::Json& scenario) {
    usc::TemplateRealizer realizer(scenario.at("templates"), scenario.at("slang"));

    std::vector<usc::DialoguePlan> plans;
    for (const usc::Json& row : scenario.at("plans").items()) {
        usc::DialoguePlan plan;
        plan.speaker = row.at("speaker").as_string();
        plan.addressee = row.at("addressee").as_string();
        plan.dialogue_act = row.at("act").as_string();
        plan.goal = row.at("goal").as_string();
        for (const usc::Json& fact : row.at("allowed_facts").items())
            plan.allowed_facts.push_back(fact.as_string());
        for (const usc::Json& topic : row.at("avoid_topics").items())
            plan.avoid_topics.push_back(topic.as_string());
        plan.phrasing = row.at("phrasing");
        plan.max_length = row.at("max_length").as_int();
        for (const usc::Json& m : row.at("moves").items()) {
            usc::SemanticMove move;
            move.act = m.at("act").as_string();
            move.certainty = m.at("certainty").as_string();
            if (m.at("predicate").truthy()) {
                usc::Proposition claim;
                claim.predicate = m.at("predicate").as_string();
                for (const auto& slot : m.at("slots").fields())
                    claim.slots[slot.first] = slot.second;
                move.proposition = claim;
            }
            plan.moves.push_back(move);
        }
        plans.push_back(plan);
    }

    std::vector<usc::StyleVector> styles;
    for (const usc::Json& row : scenario.at("styles").items()) {
        usc::StyleVector style;
        style.formality = row.at("formality").as_double();
        style.slang_level = row.at("slang_level").as_double();
        style.mean_sentence_length = row.at("mean_sentence_length").as_double();
        styles.push_back(style);
    }

    usc::Json realized = usc::Json::array();
    usc::Json prompts = usc::Json::array();
    for (std::size_t i = 0; i < plans.size(); ++i) {
        for (std::size_t j = 0; j < styles.size(); ++j) {
            usc::Json row = usc::Json::object();
            row["plan"] = static_cast<long long>(i);
            row["style"] = static_cast<long long>(j);
            row["text"] = realizer.realize(plans[i], styles[j]);
            row["expressed_commitment"] = realizer.expressed_commitment;
            row["register"] = usc::TemplateRealizer::register_for(styles[j].formality);
            realized.push(row);
        }
    }
    for (std::size_t i = 0; i < plans.size(); ++i) {
        for (std::size_t j = 0; j < styles.size(); ++j) {
            usc::Json row = usc::Json::object();
            row["plan"] = static_cast<long long>(i);
            row["style"] = static_cast<long long>(j);
            row["prompt"] = usc::chat_realizer::build_user_prompt(plans[i], styles[j]);
            prompts.push(row);
        }
    }

    usc::Json cleaned = usc::Json::array();
    for (const usc::Json& reply : scenario.at("replies").items()) {
        for (const usc::Json& cap : scenario.at("caps").items()) {
            usc::Json row = usc::Json::object();
            row["reply"] = reply;
            row["cap"] = cap;
            row["cleaned"] = usc::chat_realizer::clean_reply(reply.as_string(),
                                                             cap.as_int());
            cleaned.push(row);
        }
    }

    usc::Json table = usc::Json::object();
    for (const auto& act : realizer.templates) {
        usc::Json variants = usc::Json::object();
        for (const auto& variant : act.second) variants[variant.first] = variant.second;
        table[act.first] = variants;
    }

    usc::Json out = usc::Json::object();
    out["templates"] = table;
    out["realized"] = realized;
    out["prompts"] = prompts;
    out["cleaned"] = cleaned;
    out["system"] = std::string(usc::chat_realizer::SYSTEM);
    return out;
}

usc::Json run_actionbridge(const usc::Json& scenario) {
    usc::ActionBridge bridge(true, scenario.at("timeout_minutes").as_int());
    std::vector<usc::ActionIntent> issued;
    usc::Json log = usc::Json::array();

    for (const usc::Json& step : scenario.at("steps").items()) {
        std::string kind = step.at("do").as_string();
        usc::Json row = usc::Json::object();
        row["step"] = kind;
        try {
            if (kind == "issue") {
                usc::ActionIntent intent = bridge.issue(
                    step.at("actor").as_string(), step.at("type").as_string(),
                    step.at("params"), step.at("reason").as_string(),
                    step.at("world_time").as_int());
                issued.push_back(intent);
                row["intent"] = intent.as_json();
            } else if (kind == "resolve") {
                usc::ResolvedIntent record = bridge.resolve(
                    issued[static_cast<std::size_t>(step.at("intent").as_int())].intent_id,
                    step.at("status").as_string(), step.at("world_time").as_int(),
                    step.at("detail").as_string());
                row["record"] = record.as_json();
            } else if (kind == "expire") {
                usc::Json rows = usc::Json::array();
                for (const usc::ResolvedIntent& record :
                     bridge.expire(step.at("world_time").as_int()))
                    rows.push(record.as_json());
                row["expired"] = rows;
            } else if (kind == "pending") {
                usc::Json rows = usc::Json::array();
                for (const usc::ActionIntent& intent : bridge.pending())
                    rows.push(intent.as_json());
                row["pending"] = rows;
            } else if (kind == "pending_for") {
                usc::Json rows = usc::Json::array();
                for (const usc::ActionIntent& intent :
                     bridge.pending_for(step.at("actor").as_string()))
                    rows.push(intent.as_json());
                row["pending"] = rows;
            } else if (kind == "has_pending") {
                row["answer"] = bridge.has_pending(step.at("actor").as_string(),
                                                   step.at("type").as_string());
            } else if (kind == "report") {
                row["report"] = bridge.report();
            } else if (kind == "as_dict") {
                row["state"] = bridge.as_json();
            } else if (kind == "recent") {
                usc::Json rows = usc::Json::array();
                for (const usc::ResolvedIntent& record :
                     bridge.recent(static_cast<std::size_t>(step.at("limit").as_int())))
                    rows.push(record.as_json());
                row["recent"] = rows;
            }
        } catch (const usc::UnknownIntent& error) {
            // The MESSAGE is part of the contract: an integrator reads it over
            // HTTP, so the two implementations have to say the same thing.
            row["error"] = std::string("UnknownIntent");
            row["message"] = std::string(error.what());
        } catch (const usc::InvalidResult& error) {
            row["error"] = std::string("InvalidResult");
            row["message"] = std::string(error.what());
        } catch (const std::invalid_argument& error) {
            row["error"] = std::string("ValueError");
            row["message"] = std::string(error.what());
        }
        log.push(row);
    }

    usc::Json reloaded = usc::Json::array();
    for (const usc::Json& raw : scenario.at("reload").items()) {
        usc::ActionBridge again = usc::ActionBridge::from_json(raw);
        usc::Json row = usc::Json::object();
        row["state"] = again.as_json();
        row["report"] = again.report();
        reloaded.push(row);
    }

    usc::Json out = usc::Json::object();
    out["log"] = log;
    out["reloaded"] = reloaded;
    return out;
}

usc::Json run_validator(const usc::Json& scenario) {
    const usc::Json& setup = scenario.at("world");
    usc::World world;
    world.places = setup.at("places");
    world.entities = setup.at("entities");
    world.predicates = setup.at("predicates");
    world.decorative_vocabulary = setup.at("decorative_vocabulary");
    for (const usc::Json& row : setup.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.at("id").as_string();
        agent.public_name = row.get("public_name");
        agent.objective_name = row.get("objective_name");
        for (const usc::Json& alias : row.at("aliases").items())
            agent.aliases.push_back(alias.as_string());
        for (const usc::Json& secret : row.at("secrets").items())
            agent.secrets.push_back(secret);
        world.agents[agent.id] = agent;
    }
    for (const usc::Json& row : setup.at("topics").items()) {
        usc::Topic topic = usc::Topic::from_json(row);
        world.topics[topic.topic_id] = topic;
    }

    std::vector<usc::DialoguePlan> plans;
    for (const usc::Json& row : scenario.at("plans").items()) {
        usc::DialoguePlan plan;
        plan.speaker = row.at("speaker").as_string();
        plan.addressee = row.at("addressee").as_string();
        plan.dialogue_act = "assert";
        plan.goal = row.at("goal").as_string();
        for (const usc::Json& fact : row.at("allowed_facts").items())
            plan.allowed_facts.push_back(fact.as_string());
        for (const usc::Json& topic : row.at("avoid_topics").items())
            plan.avoid_topics.push_back(topic.as_string());
        plan.phrasing = row.at("phrasing");
        plans.push_back(plan);
    }
    const usc::Agent& speaker = *world.agents.find("agent:byrne");

    std::vector<std::string> recent;
    for (const usc::Json& line : scenario.at("recent").items())
        recent.push_back(line.as_string());

    usc::Json checks = usc::Json::array();
    for (const usc::Json& window : scenario.at("windows").items()) {
        usc::Validator validator = usc::Validator::for_world(
            world, usc::CANON_STRICT, window.as_int());
        for (const usc::Json& mode : scenario.at("modes").items()) {
            std::string which = mode.as_string();
            for (std::size_t index = 0; index < plans.size(); ++index) {
                for (const usc::Json& line : scenario.at("utterances").items()) {
                    usc::ValidationResult result = validator.check(
                        line.as_string(), plans[index], speaker, recent, &which);
                    usc::Json row = usc::Json::object();
                    row["window"] = window;
                    row["mode"] = which;
                    row["plan"] = static_cast<long long>(index);
                    row["utterance"] = line;
                    row["verdict"] = result.verdict;
                    usc::Json reasons = usc::Json::array();
                    for (const usc::Json& reason : result.reasons) reasons.push(reason);
                    row["reasons"] = reasons;
                    usc::Json unlicensed = usc::Json::array();
                    for (const usc::Json& entry : result.unlicensed) unlicensed.push(entry);
                    row["unlicensed"] = unlicensed;
                    checks.push(row);
                }
            }
        }
    }

    usc::Validator validator = usc::Validator::for_world(world);
    usc::Json specifics = usc::Json::array();
    for (std::size_t index = 0; index < plans.size(); ++index) {
        for (const usc::Json& line : scenario.at("utterances").items()) {
            usc::Json row = usc::Json::object();
            row["plan"] = static_cast<long long>(index);
            row["utterance"] = line;
            usc::Json found = usc::Json::array();
            for (const usc::Json& entry :
                 validator.unlicensed_specifics(line.as_string(), plans[index]))
                found.push(entry);
            row["found"] = found;
            specifics.push(row);
        }
    }

    usc::Json terms = usc::Json::object();
    for (const auto& entry : validator.world_terms) terms[entry.first] = entry.second;
    usc::Json forms = usc::Json::object();
    for (const auto& entry : validator.secret_surface_forms) {
        usc::Json words = usc::Json::array();
        for (const std::string& word : entry.second) words.push(word);
        forms[entry.first] = words;
    }
    usc::Json licence = usc::Json::array();
    for (const usc::DialoguePlan& plan : plans)
        licence.push(usc::Validator::licence_text(plan));
    usc::Json unprotected = usc::Json::array();
    for (const usc::Json& rows : scenario.at("unprotected").items()) {
        std::vector<std::string> labels;
        for (const usc::Json& label : rows.items()) labels.push_back(label.as_string());
        usc::Json out = usc::Json::array();
        for (const std::string& label : validator.unprotected_labels(labels))
            out.push(label);
        unprotected.push(out);
    }

    usc::Json out = usc::Json::object();
    out["world_terms"] = terms;
    out["surface_forms"] = forms;
    out["licence"] = licence;
    out["unprotected"] = unprotected;
    out["specifics"] = specifics;
    out["checks"] = checks;
    return out;
}

usc::Json run_parser(const usc::Json& scenario) {
    usc::World world;
    world.places = scenario.at("places");
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.at("id").as_string();
        agent.set_location(row.get("location"));
        for (const usc::Json& alias : row.at("aliases").items())
            agent.aliases.push_back(alias.as_string());
        agent.public_name = row.get("public_name");
        agent.objective_name = row.get("objective_name");
        world.agents[agent.id] = agent;
    }
    for (const usc::Json& row : scenario.at("topics").items()) {
        usc::Topic topic = usc::Topic::from_json(row);
        world.topics[topic.topic_id] = topic;
    }
    world.appearance_reactions = scenario.at("appearance_reactions");
    world.command_aliases = scenario.at("command_aliases");

    usc::RuleBasedParserProvider provider;
    usc::OrderedMap<std::vector<std::string>> lexicon = provider.lexicon(world);
    usc::Json lexicon_json = usc::Json::object();
    for (const auto& entry : lexicon) {
        usc::Json words = usc::Json::array();
        for (const std::string& word : entry.second) words.push(word);
        lexicon_json[entry.first] = words;
    }

    usc::Json normalized = usc::Json::array();
    usc::Json parsed = usc::Json::array();
    for (const usc::Json& line : scenario.at("lines").items()) {
        normalized.push(usc::normalize(line.as_string()));
        usc::Json row = usc::Json::object();
        row["line"] = line;
        row["command"] = parsed_command_json(provider.parse(
            line.as_string(), scenario.at("player_id").as_string(),
            scenario.at("player_location").as_string(), world));
        parsed.push(row);
    }

    usc::Json out = usc::Json::object();
    out["normalized"] = normalized;
    out["lexicon"] = lexicon_json;
    out["places"] = alias_entries_json(world.place_alias_index());
    out["agents"] = alias_entries_json(world.agent_alias_index());
    out["topics"] = alias_entries_json(world.topic_alias_index());
    out["parsed"] = parsed;
    return out;
}

usc::Json run_interpretation(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    world.predicate_domains = scenario.at("predicate_domains");
    world.predicate_competence = scenario.at("predicate_competence");
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.at("id").as_string();
        for (const auto& entry : row.at("education").fields())
            agent.education[entry.first] = entry.second.as_double();
        agent.epistemic = row.at("epistemic");
        for (const auto& entry : row.at("relationships").fields()) {
            usc::OrderedMap<double> row_values;
            for (const auto& value : entry.second.fields())
                row_values[value.first] = value.second.as_double();
            agent.relationships[entry.first] = row_values;
        }
        world.agents[agent.id] = agent;
    }

    // A null entry in the list is a run with NO proposition -- attention still
    // happens, and nothing is ever held.
    std::vector<std::optional<usc::Proposition>> props;
    for (const usc::Json& row : scenario.at("propositions").items())
        props.push_back(row.is_null() ? std::optional<usc::Proposition>()
                                      : usc::Proposition::from_json(row));

    std::vector<usc::Event> events;
    for (const usc::Json& row : scenario.at("events").items()) {
        usc::Event event;
        event.event_id = row.get("event_id").as_int();
        event.world_time = row.get("world_time").as_int();
        event.type = row.get("type").as_string();
        event.actor = row.get("actor");
        event.location = row.get("location");
        event.payload = row.get("payload");
        events.push_back(event);
    }

    usc::InterpretationEngine engine;
    usc::Json outcomes = usc::Json::array();
    for (const usc::Json& row : scenario.at("runs").items()) {
        const usc::Agent& agent = *world.agents.find(row.at("agent").as_string());
        std::size_t which = static_cast<std::size_t>(row.get("proposition").as_int());
        const usc::Proposition* claim = props[which] ? &*props[which] : nullptr;
        const usc::Event& event = events[static_cast<std::size_t>(row.get("event").as_int())];
        double quality = row.get("quality").as_double();
        std::string modality = row.at("modality").as_string();

        usc::InterpretationEngine::Attention attended =
            engine.attention(agent, event, claim, world, quality);
        usc::InterpretationEngine::Interpreted held =
            engine.interpret(agent, event, claim, world, quality, modality);

        usc::Json entry = usc::Json::object();
        entry["agent"] = agent.id;
        entry["event"] = row.get("event");
        entry["proposition"] = row.get("proposition");
        entry["quality"] = quality;
        entry["modality"] = modality;
        entry["attention"] = attended.score;
        entry["attention_reasons"] = interp_reasons_json(attended.reasons);
        entry["held"] = held.proposition ? held.proposition->as_json() : usc::Json();
        entry["core_key"] = held.proposition ? usc::Json(held.proposition->core_key())
                                             : usc::Json();
        entry["reasons"] = interp_reasons_json(held.reasons);
        outcomes.push(entry);
    }

    usc::Json recognised = usc::Json::array();
    for (const usc::Json& row : scenario.at("recognises").items()) {
        std::size_t which = static_cast<std::size_t>(row.get("proposition").as_int());
        usc::InterpretationEngine::Recognition seen = engine.recognises(
            *world.agents.find(row.at("agent").as_string()), *props[which], world);
        usc::Json entry = usc::Json::object();
        entry["agent"] = row.get("agent");
        entry["proposition"] = row.get("proposition");
        entry["known"] = seen.known;
        entry["have"] = seen.have;
        entry["detail"] = seen.detail;
        recognised.push(entry);
    }

    usc::Json noise = usc::Json::array();
    for (const usc::Json& row : scenario.at("noise").items()) {
        usc::Json entry = usc::Json::object();
        entry["agent"] = row.get("agent");
        entry["event_id"] = row.get("event_id");
        entry["salt"] = row.get("salt");
        entry["value"] = usc::interpretation_noise(
            world, row.at("agent").as_string(), row.get("event_id").as_int(),
            row.at("salt").as_string());
        noise.push(entry);
    }

    usc::Json out = usc::Json::object();
    out["outcomes"] = outcomes;
    out["recognises"] = recognised;
    out["noise"] = noise;
    return out;
}

usc::Json run_grounding(const usc::Json& scenario) {
    const usc::Json& setup = scenario.at("world");
    usc::World world;
    world.places = setup.at("places");
    world.entities = setup.at("entities");
    world.predicates = setup.at("predicates");
    for (const usc::Json& row : setup.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.public_name = row.get("public_name");
        agent.objective_name = row.get("objective_name");
        for (const usc::Json& alias : row.at("aliases").items())
            agent.aliases.push_back(alias.as_string());
        world.agents[agent.id] = agent;
    }
    usc::OrderedMap<usc::Topic> topics;
    for (const usc::Json& row : scenario.at("topics").items()) {
        usc::Topic topic = usc::Topic::from_json(row);
        topics[topic.topic_id] = topic;
    }

    usc::WorldLexicon lexicon = usc::WorldLexicon::build(
        world, topics, setup.at("decorative_vocabulary"));

    usc::Json terms = usc::Json::object();
    for (const auto& entry : lexicon.terms()) {
        usc::Json row = usc::Json::array();
        row.push(usc::Json(entry.second.kind));
        row.push(usc::Json(entry.second.target));
        terms.fields()[entry.first] = row;
    }

    usc::Json flagged = usc::Json::array();
    for (const usc::Json& row : scenario.at("sentences").items()) {
        usc::Json entry = usc::Json::object();
        entry["text"] = row.at("text");
        usc::Json rows = usc::Json::array();
        for (const usc::Json& one : usc::unknown_referents(
                 row.at("text").as_string(), lexicon, row.at("licensed").as_string()))
            rows.push(one);
        entry["unknown"] = rows;
        flagged.push(entry);
    }

    std::vector<std::optional<usc::Proposition>> propositions;
    for (const usc::Json& row : scenario.at("propositions").items())
        propositions.push_back(row.is_null() ? std::nullopt
                                             : std::optional<usc::Proposition>(
                                                   usc::Proposition::from_json(row)));

    usc::Json anchor_rows = usc::Json::array();
    for (const auto& one : propositions) {
        usc::Json row = usc::Json::array();
        for (const std::string& anchor : usc::anchors_for(one ? &*one : nullptr, lexicon))
            row.push(usc::Json(anchor));
        anchor_rows.push(row);
    }

    usc::Json said = usc::Json::array();
    for (const usc::Json& row : scenario.at("expresses").items()) {
        const auto& one = propositions[static_cast<std::size_t>(
            row.at("proposition").as_int())];
        usc::Json entry = usc::Json::object();
        entry["text"] = row.at("text");
        entry["proposition"] = row.at("proposition");
        entry["expresses"] = usc::expresses(row.at("text").as_string(),
                                            one ? &*one : nullptr, lexicon);
        said.push(entry);
    }

    usc::Json out = usc::Json::object();
    out["terms"] = terms;
    usc::Json scenery = usc::Json::array();
    for (const std::string& one : lexicon.decorative()) scenery.push(usc::Json(one));
    out["decorative"] = scenery;
    out["unknown_referents"] = flagged;
    out["anchors"] = anchor_rows;
    out["expresses"] = said;
    return out;
}

// ---- flat ------------------------------------------------------------------

usc::Json run_flat(const usc::Json& scenario) {
    std::vector<std::string> agents;
    for (const usc::Json& one : scenario.at("agents").items())
        agents.push_back(one.as_string());
    std::vector<usc::Json> tellings;
    for (const usc::Json& one : scenario.at("tellings").items()) tellings.push_back(one);

    // `broadcast` returns how many flags it actually SET, which is almost never
    // all of them -- a boolean cannot be set twice, and that is the finding.
    usc::FlatWorld flat;
    const std::string predicate = scenario.at("predicate").as_string();
    usc::Json broadcasts = usc::Json::array();
    for (const usc::Json& event : scenario.at("scenario_events").items()) {
        const usc::Json* payload = event.find("payload");
        if (!payload) continue;
        const usc::Json* named = payload->at("proposition").find("predicate");
        if (named && named->py_str() == predicate)
            broadcasts.push(usc::Json(flat.broadcast(predicate, agents)));
    }
    usc::Json told = usc::Json::array();
    for (const usc::Json& telling : tellings) {
        const usc::Json* lie = telling.find("lie");
        told.push(usc::Json(flat.tell(telling.at("from").py_str(),
                                      telling.at("to").py_str(), predicate,
                                      !(lie && lie->as_bool()))));
    }

    usc::Json answers = usc::Json::array();
    for (const usc::Json& pair : scenario.at("questions").items()) {
        const std::string who = pair.items()[0].as_string();
        const std::string fact = pair.items()[1].as_string();
        usc::Json row = usc::Json::object();
        row["agent"] = who;
        row["fact"] = fact;
        row["how_sure"] = flat.how_sure(who, fact);
        row["who_told"] = flat.who_told(who, fact);
        row["which_version"] = flat.which_version(who, fact);
        row["told_how_often"] = flat.told_how_often(who, fact);
        row["was_it_a_lie"] = flat.was_it_a_lie(who, fact);
        usc::Json knows = usc::Json::array();
        for (const std::string& one : flat.who_knows(fact)) knows.push(usc::Json(one));
        row["who_knows"] = knows;
        answers.push(row);
    }

    usc::Json exposures = usc::Json::array();
    for (const usc::Json& who : scenario.at("discredit").items())
        exposures.push(usc::Json(flat.discredit(who.as_string())));

    usc::Json out = usc::Json::object();
    out["state"] = flat.as_json();
    out["questions"] = answers;
    out["discredit"] = exposures;
    out["forgets"] = flat.forgets();
    out["broadcast_changed"] = broadcasts;
    out["tell_changed"] = told;
    return out;
}

// ---- tuning ----------------------------------------------------------------

/// The port's parameter table, written out by hand because C++ has no
/// reflection. The probe compares it against Python's live dictionaries, which
/// is the only thing standing between it and a silent drift.
usc::ParameterTable live_parameters() {
    usc::ParameterTable table;
    usc::BeliefEngine::Params belief;
    table["belief"]["kappa0"] = belief.kappa0;
    table["belief"]["alpha"] = belief.alpha;
    table["belief"]["gamma"] = belief.gamma;
    table["belief"]["delta"] = belief.delta;
    table["belief"]["kappa_min"] = belief.kappa_min;
    table["belief"]["kappa_max"] = belief.kappa_max;
    table["belief"]["rho_correlated"] = belief.rho_correlated;
    table["belief"]["provenance_limit"] = belief.provenance_limit;
    table["belief"]["origin_limit"] = belief.origin_limit;

    usc::MemoryEngine::Params memory;
    table["memory"]["tau_ret"] = memory.tau_ret;
    table["memory"]["noise_s"] = memory.noise_s;
    table["memory"]["working_cap"] = memory.working_cap;
    table["memory"]["w_topic"] = memory.w_topic;
    table["memory"]["w_goal"] = memory.w_goal;
    table["memory"]["w_emotion"] = memory.w_emotion;
    table["memory"]["w_mood_congruence"] = memory.w_mood_congruence;
    table["memory"]["episodic_cap"] = memory.episodic_cap;
    table["memory"]["interference"] = memory.interference;
    table["memory"]["presentation_window"] = memory.presentation_window;
    table["memory"]["total_cap"] = memory.total_cap;
    table["memory"]["summary_cap"] = memory.summary_cap;

    usc::AffectEngine::Params affect;
    table["affect"]["k_impulse"] = affect.k_impulse;
    table["affect"]["tau_mood"] = affect.tau_mood;
    table["affect"]["tau_emotion"] = affect.tau_emotion;
    table["affect"]["epsilon"] = affect.epsilon;

    usc::DiffusionEngine::Params diffusion;
    table["diffusion"]["encounters_per_hour"] = diffusion.encounters_per_hour;
    table["diffusion"]["max_encounters_per_tick"] = diffusion.max_encounters_per_tick;
    table["diffusion"]["min_confidence_to_tell"] = diffusion.min_confidence_to_tell;
    table["diffusion"]["min_tie"] = diffusion.min_tie;
    table["diffusion"]["fidelity_decay"] = diffusion.fidelity_decay;
    table["diffusion"]["distortion_prob"] = diffusion.distortion_prob;
    table["diffusion"]["distortion_weights"] = usc::Json();
    table["diffusion"]["stifle_prob"] = diffusion.stifle_prob;
    table["diffusion"]["include_player"] = diffusion.include_player;
    table["diffusion"]["max_hops"] = diffusion.max_hops;
    table["diffusion"]["bystanders"] = diffusion.bystanders;

    usc::PursuitEngine pursuit_engine;
    usc::PursuitEngine::Params& pursuit = pursuit_engine.params();
    table["pursuit"]["interval_minutes"] = pursuit.interval_minutes;
    table["pursuit"]["min_confidence"] = pursuit.min_confidence;
    table["pursuit"]["max_per_tick"] = pursuit.max_per_tick;
    table["pursuit"]["worth_a_call"] = pursuit.worth_a_call;
    table["pursuit"]["worth_writing"] = pursuit.worth_writing;

    usc::ContagionEngine contagion_engine;
    usc::ContagionEngine::Params& contagion = contagion_engine.params();
    table["contagion"]["transfer"] = contagion.transfer;
    table["contagion"]["min_tie"] = contagion.min_tie;
    table["contagion"]["max_step"] = contagion.max_step;

    table["notes"]["max_per_place"] = static_cast<long long>(usc::MAX_NOTES_PER_PLACE);
    table["notes"]["lifetime_minutes"] = usc::NOTE_LIFETIME_MINUTES;
    table["notes"]["intercept_base"] = usc::INTERCEPT_BASE;

    table["promises"]["horizon_minutes"] = usc::DEFAULT_HORIZON_MINUTES;
    table["promises"]["kept_margin"] = usc::KEPT_MARGIN;
    table["promises"]["max_open_per_agent"] = static_cast<long long>(usc::MAX_OPEN_PER_AGENT);

    table["common_knowledge"]["min_witnesses"] = usc::MIN_WITNESSES;
    table["common_knowledge"]["public_privacy"] = usc::PUBLIC_PRIVACY;
    table["common_knowledge"]["min_quality"] = usc::MIN_QUALITY;

    usc::PolicyEngine::Params policy;
    table["policy"]["temperature"] = policy.temperature;
    table["policy"]["use_prospect"] = policy.use_prospect;
    table["policy"]["w_impulsivity"] = policy.w_impulsivity;
    table["policy"]["w_arousal"] = policy.w_arousal;

    usc::RelationshipEngine::Params relationship;
    table["relationship"]["eta_up"] = relationship.eta_up;
    table["relationship"]["eta_down"] = relationship.eta_down;
    table["relationship"]["eta_other"] = relationship.eta_other;

    usc::ReputationEngine::Params reputation;
    table["reputation"]["eta_image"] = reputation.eta_image;
    table["reputation"]["eta_rep"] = reputation.eta_rep;
    table["reputation"]["decay"] = reputation.decay;

    usc::IdentityEngine::Params identity;
    table["identity"]["beta"] = identity.beta;
    table["identity"]["w_acc"] = identity.w_acc;
    table["identity"]["w_comp"] = identity.w_comp;
    table["identity"]["w_norm"] = identity.w_norm;
    table["identity"]["w_threat"] = identity.w_threat;
    table["identity"]["neutral_fit"] = identity.neutral_fit;
    table["identity"]["inertia"] = identity.inertia;

    usc::SociolinguisticEngine::Params socioling;
    table["socioling"]["w_edu"] = socioling.w_edu;
    table["socioling"]["w_setting"] = socioling.w_setting;
    table["socioling"]["w_status"] = socioling.w_status;
    table["socioling"]["w_role"] = socioling.w_role;
    table["socioling"]["w_arousal"] = socioling.w_arousal;
    table["socioling"]["w_ingroup"] = socioling.w_ingroup;
    table["socioling"]["lambda_accommodation"] = socioling.lambda_accommodation;
    table["socioling"]["base_sentence_len"] = socioling.base_sentence_len;
    table["socioling"]["k_len"] = socioling.k_len;
    table["socioling"]["k_stress"] = socioling.k_stress;
    return table;
}

usc::Json run_tuning(const usc::Json& scenario) {
    usc::Json out = usc::Json::object();

    usc::Json defaults = usc::Json::object();
    for (const auto& engine : live_parameters()) {
        usc::Json values = usc::Json::object();
        for (const auto& entry : engine.second) values.fields()[entry.first] = entry.second;
        defaults.fields()[engine.first] = values;
    }
    out["parameters"] = defaults;

    usc::Json tunable_rows = usc::Json::object();
    for (const auto& entry : usc::tunable())
        tunable_rows.fields()[entry.first] = usc::Json(entry.second);
    out["tunable"] = tunable_rows;

    usc::Json applied = usc::Json::array();
    for (const usc::Json& block : scenario.at("blocks").items()) {
        usc::ParameterTable table = live_parameters();
        usc::Json entry = usc::Json::object();
        entry["block"] = block;
        usc::Json rows = usc::Json::array();
        for (const auto& reason : usc::apply(table, block)) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            rows.push(line);
        }
        entry["reasons"] = rows;
        usc::Json after = usc::Json::object();
        for (const auto& engine : table) {
            usc::Json values = usc::Json::object();
            for (const auto& one : engine.second) values.fields()[one.first] = one.second;
            after.fields()[engine.first] = values;
        }
        entry["after"] = after;
        applied.push(entry);
    }
    out["applied"] = applied;

    // The messages are compared too, because "did you mean" is the entire value
    // of refusing: a rejection that does not say what was meant is a wall.
    usc::Json refusals = usc::Json::array();
    for (const usc::Json& block : scenario.at("refusals").items()) {
        usc::ParameterTable table = live_parameters();
        usc::Json entry = usc::Json::object();
        entry["block"] = block;
        try {
            usc::apply(table, block);
            entry["refused"] = false;
        } catch (const usc::TuningError& error) {
            entry["refused"] = true;
            entry["message"] = std::string(error.what());
        }
        refusals.push(entry);
    }
    out["refusals"] = refusals;

    usc::ParameterTable table = live_parameters();
    out["describe"] = usc::describe(table);

    // A build missing a layer warns rather than refusing, because a studio that
    // declined a mechanic should not be told their pack is broken.
    usc::ParameterTable partial = live_parameters();
    partial = [&] {
        usc::ParameterTable trimmed;
        for (const auto& engine : partial)
            if (engine.first != "contagion") trimmed[engine.first] = engine.second;
        return trimmed;
    }();
    usc::Json missing = usc::Json::object();
    missing["contagion"] = [&] {
        usc::Json values = usc::Json::object();
        values["transfer"] = 0.5;
        return values;
    }();
    usc::Json warned = usc::Json::array();
    for (const std::string& one : usc::check(missing, partial)) warned.push(usc::Json(one));
    out["warnings"] = warned;
    return out;
}

// ---- revision --------------------------------------------------------------

usc::Json run_revision(const usc::Json& scenario) {
    usc::World world;
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        for (const usc::Json& belief_row : row.at("beliefs").items()) {
            usc::Belief belief;
            belief.proposition = usc::Proposition::from_json(belief_row);
            belief.proposition.polarity = "+";
            belief.logit_val = belief_row.at("logit").as_double();
            belief.support_for = belief_row.at("support_for").as_double();
            belief.support_against = belief_row.at("support_against").as_double();
            for (const usc::Json& record : belief_row.at("provenance").items()) {
                usc::ProvenanceEntry entry;
                entry.claim_id = record.get("claim_id");
                entry.origin_event = record.get("origin_event");
                entry.kappa = record.at("kappa").as_double();
                entry.eta = record.at("eta").as_double();
                entry.delta = record.at("delta").as_double();
                entry.speaker = record.get("speaker");
                belief.provenance.push_back(entry);
            }
            // The arithmetic ledger is rebuilt from the provenance, exactly as
            // `from_json` does for a save written before it existed. Without it
            // both sides revise nothing and the case passes vacuously.
            for (const usc::ProvenanceEntry& entry : belief.provenance) {
                if (entry.delta == 0.0) continue;
                std::array<double, 2>& bucket = belief.contributions[
                    usc::contribution_key(entry.speaker, entry.origin_event)];
                bucket[entry.delta > 0.0 ? 0 : 1] += entry.delta;
            }
            agent.beliefs[belief.proposition.core_key()] = belief;
        }
        world.agents[agent.id] = agent;
    }

    usc::Json out = usc::Json::object();

    usc::Json previews = usc::Json::object();
    for (const usc::Json& source : scenario.at("preview_sources").items()) {
        usc::Json rows = usc::Json::array();
        for (const usc::Json& one : usc::would_change(world, source.as_string()))
            rows.push(one);
        previews.fields()[source.as_string()] = rows;
    }
    out["would_change"] = previews;

    usc::Json passes = usc::Json::array();
    for (const usc::Json& row : scenario.at("discredits").items()) {
        const usc::Json& predicate = row.at("predicate");
        usc::Revision revision = usc::discredit(
            world, row.at("source").as_string(), row.at("factor").as_double(),
            row.at("reason").as_string(),
            predicate.is_null() ? std::string() : predicate.as_string());
        usc::Json entry = revision.as_json();
        usc::Json trace = usc::Json::array();
        for (const auto& reason : revision.reasons) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            trace.push(line);
        }
        entry["reasons"] = trace;
        passes.push(entry);
    }
    out["discredits"] = passes;

    usc::Json after = usc::Json::object();
    for (const auto& entry : world.agents) {
        usc::Json rows = usc::Json::object();
        for (const auto& held : entry.second.beliefs)
            rows.fields()[held.first] = held.second.as_json();
        after.fields()[entry.first] = rows;
    }
    out["beliefs_after"] = after;
    return out;
}

// ---- pursuit ---------------------------------------------------------------

usc::Json run_pursuit(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    world.places = scenario.at("places");
    world.predicates = scenario.at("predicates");

    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        for (const usc::Json& one : row.at("contacts").items())
            agent.contacts.push_back(one.as_string());
        for (const usc::Json& goal : row.at("goals").items()) agent.goals.push_back(goal);
        for (const auto& subject : row.at("relationships").fields())
            for (const auto& field : subject.second.fields())
                agent.relationships[subject.first][field.first] = field.second.as_double();
        for (const usc::Json& belief_row : row.at("beliefs").items()) {
            usc::Belief belief;
            belief.proposition = usc::Proposition::from_json(belief_row);
            belief.proposition.polarity = "+";
            belief.logit_val = belief_row.at("logit").as_double();
            belief.hops = belief_row.at("hops").as_int();
            for (const auto& entry : belief_row.at("origin_counts").fields())
                belief.origin_counts[entry.first] = entry.second.as_int();
            agent.beliefs[belief.proposition.core_key()] = belief;
        }
        world.agents[agent.id] = agent;
    }

    usc::Json ledger = usc::Json::array();
    usc::DiffusionEngine diffusion;
    usc::DiffusionRuntime diffusion_runtime;
    diffusion_runtime.process_event = [&](const usc::Event& event) {
        usc::Json row = usc::Json::object();
        row["event_id"] = event.event_id;
        row["actor"] = event.actor;
        row["location"] = event.location;
        row["payload"] = event.payload;
        ledger.push(row);
    };
    usc::NoteBoard board(scenario.get("notes").as_bool());
    usc::NoteRuntime note_runtime;
    note_runtime.fidelity_decay = diffusion.params().fidelity_decay;
    note_runtime.process_event = diffusion_runtime.process_event;

    usc::PursuitRuntime runtime;
    runtime.diffusion = &diffusion;
    runtime.diffusion_runtime = &diffusion_runtime;
    runtime.notes = &board;
    runtime.note_runtime = &note_runtime;

    usc::PursuitEngine engine(scenario.get("enabled").as_bool(),
                              scenario.get("media").as_bool());
    engine.set_notes(scenario.get("notes").as_bool());

    usc::Json steps = usc::Json::array();
    for (const usc::Json& row : scenario.at("steps").items()) {
        world.world_time = row.at("to").as_int();
        usc::Json entry = usc::Json::object();
        entry["to"] = row.at("to");
        usc::Json rows = usc::Json::array();
        for (const auto& reason : engine.step(world, runtime, row.at("delta").as_int(),
                                              scenario.at("player_id").as_string())) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            rows.push(line);
        }
        entry["reasons"] = rows;
        steps.push(entry);
    }

    usc::Json out = usc::Json::object();
    out["steps"] = steps;
    out["events"] = ledger;
    out["notes"] = board.report();
    out["state"] = engine.as_json();

    usc::PursuitEngine restored(scenario.get("enabled").as_bool(),
                                scenario.get("media").as_bool());
    restored.restore(engine.as_json());
    out["restored"] = restored.as_json();
    return out;
}

// ---- notes -----------------------------------------------------------------

usc::Json note_reasons_json(const std::vector<usc::NoteReason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json run_notes(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        usc::Json epistemic = usc::Json::object();
        epistemic["curiosity"] = row.at("curiosity");
        agent.epistemic = epistemic;
        for (const usc::Json& secret : row.at("secrets").items())
            agent.secrets.push_back(secret);
        world.agents[agent.id] = agent;
    }

    std::vector<usc::Belief> beliefs;
    for (const usc::Json& row : scenario.at("beliefs").items()) {
        usc::Belief belief;
        belief.proposition = usc::Proposition::from_json(row);
        belief.proposition.polarity = "+";
        belief.logit_val = row.at("logit").as_double();
        belief.hops = row.at("hops").as_int();
        for (const auto& entry : row.at("origin_counts").fields())
            belief.origin_counts[entry.first] = entry.second.as_int();
        beliefs.push_back(belief);
    }

    usc::Json ledger = usc::Json::array();
    usc::NoteRuntime runtime;
    runtime.process_event = [&](const usc::Event& event) {
        usc::Json row = usc::Json::object();
        row["event_id"] = event.event_id;
        row["actor"] = event.actor;
        row["location"] = event.location;
        row["payload"] = event.payload;
        ledger.push(row);
    };

    usc::NoteBoard board(scenario.get("enabled").as_bool());
    usc::Json out = usc::Json::object();

    usc::Json written = usc::Json::array();
    for (const usc::Json& row : scenario.at("leave").items()) {
        std::vector<usc::NoteReason> reasons;
        const usc::Belief& belief = beliefs[static_cast<std::size_t>(
            row.at("belief").as_int())];
        bool ok = board.leave(world, *world.agents.find(row.at("author").as_string()),
                              row.at("for").as_string(), row.at("place").as_string(),
                              belief.proposition.core_key(), &belief, runtime, reasons);
        usc::Json entry = usc::Json::object();
        entry["left"] = ok;
        entry["reasons"] = note_reasons_json(reasons);
        written.push(entry);
    }
    out["left"] = written;

    usc::Json steps = usc::Json::array();
    long long index = 0;
    for (const usc::Json& row : scenario.at("steps").items()) {
        for (const usc::Json& move : scenario.at("moves").items())
            if (move.at("at_step").as_int() == index) {
                usc::Agent* who = world.agents.find(move.at("agent").as_string());
                if (who) who->set_location(move.at("to"));
            }
        world.world_time = row.at("to").as_int();
        usc::Json entry = usc::Json::object();
        entry["to"] = row.at("to");
        entry["reasons"] = note_reasons_json(
            board.step(world, runtime, row.at("delta").as_int()));
        entry["still_lying"] = board.report();
        steps.push(entry);
        ++index;
    }
    out["steps"] = steps;
    out["events"] = ledger;
    out["board"] = board.as_json();

    usc::NoteBoard restored(scenario.get("enabled").as_bool());
    restored.restore(board.as_json());
    out["restored"] = restored.as_json();
    return out;
}

// ---- promises --------------------------------------------------------------

usc::Json promise_reasons_json(const std::vector<usc::PromiseReason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json run_promises(const usc::Json& scenario) {
    usc::World world;
    world.world_time = scenario.get("world_time").as_int();
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        for (const usc::Json& belief_row : row.at("beliefs").items()) {
            usc::Belief belief;
            belief.proposition = usc::Proposition::from_json(belief_row);
            belief.proposition.polarity = "+";
            belief.logit_val = belief_row.at("logit").as_double();
            agent.beliefs[belief.proposition.core_key()] = belief;
        }
        world.agents[agent.id] = agent;
    }

    usc::PromiseLedger ledger(scenario.get("enabled").as_bool());
    usc::PromiseRuntime runtime;
    usc::Json out = usc::Json::object();

    usc::Json made = usc::Json::array();
    for (const usc::Json& row : scenario.at("promises").items()) {
        usc::Proposition claim;
        claim.predicate = row.at("predicate").as_string();
        for (const auto& slot : row.at("slots").fields()) claim.slots[slot.first] = slot.second;
        claim.valid_end = row.get("valid_end");

        usc::Event event;
        event.type = "promise";
        event.actor = row.get("actor");
        event.world_time = row.at("world_time").as_int();
        event.payload = usc::Json::object();
        event.payload["proposition"] = claim.as_json();
        event.payload["target"] = row.get("target");
        if (const usc::Json* addressee = row.find("addressee"))
            event.payload["addressee"] = *addressee;

        std::vector<std::string> witnesses;
        for (const usc::Json& who : row.at("witnesses").items())
            witnesses.push_back(who.as_string());

        usc::Json entry = usc::Json::object();
        entry["actor"] = row.get("actor");
        entry["target"] = row.get("target");
        entry["reasons"] = promise_reasons_json(ledger.record(world, event, witnesses));
        made.push(entry);
    }
    out["made"] = made;

    usc::Json ids = usc::Json::array();
    for (const std::string& one : ledger.open_ids()) ids.push(usc::Json(one));
    out["open_after_recording"] = ids;

    // The promisee comes to believe it happened, which is the only thing that
    // decides whether the promise was kept.
    for (const usc::Json& row : scenario.at("belief_moves").items()) {
        usc::Agent* who = world.agents.find(row.at("agent").as_string());
        if (!who) continue;
        usc::Belief* belief = who->beliefs.find(row.at("key").as_string());
        if (belief) belief->logit_val = row.at("logit").as_double();
    }

    usc::Json forced = usc::Json::array();
    for (const usc::Json& row : scenario.at("settle_explicitly").items()) {
        usc::Json entry = usc::Json::object();
        entry["promise"] = row.at("promise");
        try {
            entry["reasons"] = promise_reasons_json(
                ledger.settle(world, runtime, row.at("promise").as_string(),
                              row.at("kept").as_bool(), row.at("note").as_string()));
        } catch (const std::exception&) {
            entry["refused"] = true;
        }
        forced.push(entry);
    }
    out["settled_explicitly"] = forced;

    usc::Json steps = usc::Json::array();
    for (const usc::Json& row : scenario.at("steps").items()) {
        world.world_time = row.at("to").as_int();
        usc::Json entry = usc::Json::object();
        entry["to"] = row.at("to");
        entry["reasons"] = promise_reasons_json(
            ledger.step(world, runtime, row.at("delta").as_int()));
        steps.push(entry);
    }
    out["steps"] = steps;

    usc::Json state = usc::Json::object();
    for (const auto& entry : world.agents) {
        usc::Json who = usc::Json::object();
        usc::Json rel = usc::Json::object();
        for (const auto& subject : entry.second.relationships) {
            usc::Json fields = usc::Json::object();
            for (const auto& field : subject.second)
                fields.fields()[field.first] = usc::Json(field.second);
            rel.fields()[subject.first] = fields;
        }
        who["relationships"] = rel;
        usc::Json rep = usc::Json::object();
        for (const auto& subject : entry.second.reputation) {
            usc::Json fields = usc::Json::object();
            for (const auto& field : subject.second)
                fields.fields()[field.first] = usc::Json(field.second);
            rep.fields()[subject.first] = fields;
        }
        who["reputation"] = rep;
        state.fields()[entry.first] = who;
    }
    out["agents"] = state;
    out["report"] = ledger.report();
    out["ledger"] = ledger.as_json();

    usc::PromiseLedger restored(scenario.get("enabled").as_bool());
    restored.restore(ledger.as_json());
    out["restored"] = restored.as_json();
    return out;
}

// ---- common knowledge ------------------------------------------------------

usc::Json run_common_knowledge(const usc::Json& scenario) {
    usc::World world;
    world.places = scenario.at("places");
    for (const usc::Json& id : scenario.at("agents").items()) {
        usc::Agent one;
        one.id = id.as_string();
        world.agents[one.id] = one;
    }

    usc::CommonKnowledgeEngine engine(scenario.get("enabled").as_bool());
    usc::Json rows = usc::Json::array();
    for (const usc::Json& row : scenario.at("events").items()) {
        usc::Event event;
        event.type = row.at("type").as_string();
        event.actor = row.get("actor");
        event.location = row.get("location");
        event.world_time = row.at("world_time").as_int();
        event.payload = row.get("payload");
        event.payload["proposition"] = row.get("proposition");

        std::vector<std::pair<std::string, double>> learned;
        for (const usc::Json& one : row.at("learned").items())
            learned.emplace_back(one.items()[0].as_string(), one.items()[1].as_double());

        usc::Json entry = usc::Json::object();
        entry["at"] = row.at("world_time");
        entry["type"] = row.at("type");
        entry["place"] = row.get("location");
        usc::Json reasons = usc::Json::array();
        for (const auto& reason : engine.observe(world, event, learned)) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            reasons.push(line);
        }
        entry["reasons"] = reasons;
        rows.push(entry);
    }

    usc::Json answers = usc::Json::array();
    for (const usc::Json& query : scenario.at("queries").items()) {
        std::vector<std::string> among;
        for (const usc::Json& one : query.at("among").items()) among.push_back(one.as_string());
        usc::Json entry = usc::Json::object();
        entry["key"] = query.at("key");
        entry["among"] = query.at("among");
        entry["is_common"] = engine.is_common(query.at("key").as_string(), among);
        entry["publics"] = static_cast<long long>(
            engine.publics_for(query.at("key").as_string()).size());
        answers.push(entry);
    }

    usc::Json outs = usc::Json::array();
    for (const usc::Json& pair : scenario.at("out_queries").items())
        outs.push(usc::Json(engine.is_out(pair.items()[0].as_string(),
                                          pair.items()[1].as_string())));

    usc::Json out = usc::Json::object();
    out["observations"] = rows;
    out["queries"] = answers;
    out["is_out"] = outs;
    out["report"] = engine.report();
    out["state"] = engine.as_json();

    usc::CommonKnowledgeEngine restored(scenario.get("enabled").as_bool());
    restored.restore(engine.as_json());
    out["restored"] = restored.as_json();
    return out;
}

// ---- climate ---------------------------------------------------------------

usc::Json climate_reasons_json(const std::vector<usc::ClimateReason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json run_climate(const usc::Json& scenario) {
    usc::ClimateEngine engine(scenario.at("places"), scenario.get("enabled").as_bool());
    usc::Json out = usc::Json::object();

    usc::Json baselines = usc::Json::object();
    for (const auto& entry : scenario.at("places").fields())
        baselines.fields()[entry.first] = usc::baseline_for(entry.second).as_json();
    out["baselines"] = baselines;

    usc::Json before = usc::Json::object();
    for (const auto& entry : scenario.at("places").fields())
        before.fields()[entry.first] = engine.modifiers(entry.first);
    before.fields()["place:nonexistent"] = engine.modifiers("place:nonexistent");
    out["modifiers_before"] = before;

    usc::Json reactions = usc::Json::array();
    for (const usc::Json& row : scenario.at("events").items()) {
        usc::Event event;
        event.type = row.at("type").as_string();
        event.location = row.get("location");
        event.payload = row.get("payload");
        usc::Json entry = usc::Json::object();
        entry["event"] = row;
        entry["reasons"] = climate_reasons_json(engine.react(event));
        reactions.push(entry);
    }
    out["reactions"] = reactions;

    usc::Json walks = usc::Json::array();
    for (const usc::Json& row : scenario.at("walks").items()) {
        usc::Json entry = usc::Json::object();
        entry["walk"] = row;
        entry["reasons"] = climate_reasons_json(
            engine.carried(row.at("from").as_string(), row.at("to").as_string()));
        walks.push(entry);
    }
    out["walks"] = walks;

    usc::Json steps = usc::Json::array();
    for (const usc::Json& delta : scenario.at("steps").items()) {
        engine.step(delta.as_int());
        usc::Json entry = usc::Json::object();
        entry["delta"] = delta;
        entry["state"] = engine.as_json();
        steps.push(entry);
    }
    out["steps"] = steps;

    usc::Json again = usc::Json::array();
    for (const usc::Json& row : scenario.at("walks_after_step").items()) {
        usc::Json entry = usc::Json::object();
        entry["walk"] = row;
        entry["reasons"] = climate_reasons_json(
            engine.carried(row.at("from").as_string(), row.at("to").as_string()));
        again.push(entry);
    }
    out["walks_after_step"] = again;

    usc::Json after = usc::Json::object();
    for (const auto& entry : scenario.at("places").fields())
        after.fields()[entry.first] = engine.modifiers(entry.first);
    out["modifiers_after"] = after;
    out["report"] = engine.report();

    engine.restore(scenario.at("restore"));
    out["restored"] = engine.as_json();
    out["report_after_restore"] = engine.report();
    return out;
}

// ---- contagion -------------------------------------------------------------

usc::Json run_contagion(const usc::Json& scenario) {
    usc::OrderedMap<usc::Agent> cast;
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.affect.mood = usc::Vec3::from_json(row.at("mood"));
        for (const auto& entry : row.at("big_five").fields())
            agent.big_five[entry.first] = entry.second.as_double();
        for (const auto& subject : row.at("relationships").fields())
            for (const auto& field : subject.second.fields())
                agent.relationships[subject.first][field.first] = field.second.as_double();
        cast[agent.id] = agent;
    }

    usc::ContagionEngine engine(scenario.get("enabled").as_bool());
    usc::Json exchanges = usc::Json::array();
    for (const usc::Json& row : scenario.at("exchanges").items()) {
        // A COPY of the speaker, because `between` takes the listener by
        // reference and the two can be the same character -- which is the case
        // the module returns nothing for.
        usc::Agent speaker = *cast.find(row.at("from").as_string());
        usc::Agent& listener = *cast.find(row.at("to").as_string());
        usc::Json rows = usc::Json::array();
        for (const auto& reason : engine.between(speaker, listener)) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            rows.push(line);
        }
        usc::Json entry = usc::Json::object();
        entry["from"] = row.at("from");
        entry["to"] = row.at("to");
        entry["reasons"] = rows;
        entry["listener_mood"] = listener.affect.mood.as_json();
        exchanges.push(entry);
    }

    usc::Json moods = usc::Json::object();
    for (const auto& entry : cast)
        moods.fields()[entry.first] = entry.second.affect.mood.as_json();

    usc::Json out = usc::Json::object();
    out["exchanges"] = exchanges;
    out["final_moods"] = moods;
    return out;
}

// ---- medium ----------------------------------------------------------------

usc::Json run_medium(const usc::Json& scenario) {
    usc::OrderedMap<usc::Agent> cast;
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        for (const usc::Json& one : row.at("contacts").items())
            agent.contacts.push_back(one.as_string());
        for (const auto& subject : row.at("relationships").fields())
            for (const auto& field : subject.second.fields())
                agent.relationships[subject.first][field.first] = field.second.as_double();
        cast[agent.id] = agent;
    }

    usc::Json reach = usc::Json::object();
    for (const auto& entry : cast) {
        usc::Json who = usc::Json::array();
        for (const std::string& one : usc::contacts_of(entry.second)) who.push(usc::Json(one));
        reach.fields()[entry.first] = who;
    }

    usc::Json exchanges = usc::Json::array();
    for (const usc::Json& pair : scenario.at("pairs").items()) {
        const usc::Agent& speaker = *cast.find(pair.items()[0].as_string());
        const usc::Agent& listener = *cast.find(pair.items()[1].as_string());
        for (bool enabled : {true, false}) {
            const usc::Medium* chosen = usc::for_exchange(speaker, listener, enabled);
            usc::Json entry = usc::Json::object();
            entry["speaker"] = pair.items()[0];
            entry["listener"] = pair.items()[1];
            entry["layer_on"] = enabled;
            entry["medium"] = chosen ? usc::Json(chosen->name) : usc::Json();
            exchanges.push(entry);
        }
    }

    usc::Json table = usc::Json::array();
    for (const usc::Json& name : scenario.at("media").items()) {
        const usc::Medium* one = usc::medium_by_name(name.as_string());
        usc::Json entry = usc::Json::object();
        entry["name"] = name;
        if (!one) {
            entry["known"] = false;
        } else {
            entry["known"] = true;
            entry["fidelity"] = one->fidelity;
            entry["audience"] = one->audience;
            entry["needs_colocation"] = one->needs_colocation;
            entry["trust_factor"] = one->trust_factor;
            entry["distortion_scale"] = one->distortion_scale();
            entry["described"] = usc::describe(*one);
        }
        table.push(entry);
    }

    usc::Json out = usc::Json::object();
    out["contacts"] = reach;
    out["exchanges"] = exchanges;
    out["media"] = table;
    return out;
}

// ---- agency ----------------------------------------------------------------

usc::Json run_agency(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        agent.social_status = row.get("social_status").as_double(0.4);
        agent.resources = row.get("resources").as_double(0.4);
        for (const usc::Json& role : row.at("roles").items()) agent.roles.push_back(role);
        for (const usc::Json& one : row.at("identities").items())
            agent.identities.push_back(one);
        for (const auto& entry : row.at("big_five").fields())
            agent.big_five[entry.first] = entry.second.as_double();
        for (const auto& entry : row.at("needs").fields())
            agent.needs[entry.first] = entry.second.as_double();
        for (const usc::Json& one : row.at("secrets").items()) agent.secrets.push_back(one);
        for (const auto& subject : row.at("relationships").fields())
            for (const auto& field : subject.second.fields())
                agent.relationships[subject.first][field.first] = field.second.as_double();
        world.agents[agent.id] = agent;
    }

    usc::Json out = usc::Json::object();

    usc::Json calls = usc::Json::array();
    for (const usc::Json& who : scenario.at("callers").items()) {
        const usc::Agent& caller = *world.agents.find(who.as_string());
        usc::Json reachable = usc::Json::array();
        for (const usc::Agent* ally : usc::potential_allies(caller, world))
            reachable.push(usc::Json(ally->id));
        for (const usc::Json& urgency : scenario.at("urgencies").items())
            for (const usc::Json& event_id : scenario.at("event_ids").items()) {
                auto mobilization = usc::mobilization_candidate(
                    caller, world, urgency.as_double(), event_id.as_int());
                usc::Json entry = usc::Json::object();
                entry["caller"] = who;
                entry["urgency"] = urgency;
                entry["event_id"] = event_id;
                entry["reachable"] = reachable;
                if (!mobilization) {
                    entry["mobilization"] = usc::Json();
                } else {
                    usc::Json answers = usc::Json::array();
                    for (const usc::AllyResponse& one : mobilization->responses) {
                        usc::Json row = usc::Json::object();
                        row["ally"] = one.ally_id;
                        row["probability"] = one.probability;
                        row["latency"] = one.latency;
                        row["will_come"] = one.will_come;
                        answers.push(row);
                    }
                    usc::Json act = usc::Json::object();
                    act["action_id"] = mobilization->action.action_id;
                    act["action_class"] = mobilization->action.action_class;
                    usc::Json outcomes = usc::Json::array();
                    for (const usc::ActionOutcome& outcome : mobilization->action.outcomes) {
                        usc::Json row = usc::Json::object();
                        row["dimension"] = outcome.dimension;
                        row["delta"] = outcome.delta;
                        row["probability"] = outcome.probability;
                        row["source"] = outcome.source;
                        outcomes.push(row);
                    }
                    act["outcomes"] = outcomes;
                    entry["mobilization"] = act;
                    entry["responses"] = answers;
                }
                calls.push(entry);
            }
    }
    out["mobilization"] = calls;

    usc::Json holds = usc::Json::array();
    for (const usc::Json& pair : scenario.at("leverage_pairs").items())
        holds.push(usc::Json(usc::leverage(*world.agents.find(pair.items()[0].as_string()),
                                           *world.agents.find(pair.items()[1].as_string()))));
    out["leverage"] = holds;

    usc::Json ranks = usc::Json::array();
    for (const usc::Json& pair : scenario.at("authority_pairs").items())
        ranks.push(usc::Json(usc::authority(*world.agents.find(pair.items()[0].as_string()),
                                            *world.agents.find(pair.items()[1].as_string()))));
    out["authority"] = ranks;

    std::vector<usc::ReactiveRule> rules = usc::default_reactive_rules();
    // One rule that always throws, because a rule that throws must be reported
    // and must not stop the others being evaluated.
    rules.push_back({"broken_rule",
                     [](const usc::Agent&, const usc::Json&) -> bool {
                         throw std::runtime_error("deliberately broken");
                     },
                     "nothing", 0.0, "a rule from a pack, with a bug in it"});

    usc::Json fired = usc::Json::array();
    for (const usc::Json& context : scenario.at("contexts").items()) {
        std::vector<usc::AgencyReason> reasons;
        auto matched = usc::fire_reactive_rules(*world.agents.find("agent:boss"),
                                                context, rules, &reasons);
        usc::Json names = usc::Json::array();
        for (const usc::ReactiveRule& rule : matched) names.push(usc::Json(rule.rule_id));
        usc::Json entry = usc::Json::object();
        entry["context"] = context;
        entry["fired"] = names;
        entry["failures"] = static_cast<long long>(reasons.size());
        fired.push(entry);
    }
    out["reactive_rules"] = fired;

    usc::Json resolutions = usc::Json::array();
    const usc::Json& setup = scenario.at("resolution");
    for (const usc::Json& probability : setup.at("probabilities").items())
        for (const usc::Json& seed_name : setup.at("seeds").items()) {
            usc::Json row = usc::Json::array();
            row.push(probability);
            row.push(seed_name);
            row.push(usc::Json(usc::resolve(
                probability.as_double(),
                usc::derive_seed(seed_name.as_string(), "probe", 0, 0, "agency"))));
            resolutions.push(row);
        }
    out["resolution"] = resolutions;

    usc::Json aspirations = usc::Json::object();
    for (const auto& entry : world.agents)
        aspirations.fields()[entry.first] = usc::Json(usc::risk_reference_point(entry.second));
    out["risk_reference"] = aspirations;
    return out;
}

// ---- dialogue --------------------------------------------------------------

usc::Json run_dialogue(const usc::Json& scenario) {
    const usc::Json& row = scenario.at("agent");
    usc::Agent agent;
    agent.id = row.get("id").as_string();
    for (const usc::Json& secret : row.at("secrets").items()) agent.secrets.push_back(secret);
    for (const usc::Json& belief_row : row.at("beliefs").items()) {
        usc::Belief belief;
        belief.proposition = usc::Proposition::from_json(belief_row);
        belief.proposition.polarity = "+";
        belief.logit_val = belief_row.at("logit").as_double();
        belief.support_for = belief.logit_val;
        agent.beliefs[belief.proposition.core_key()] = belief;
    }

    usc::StyleVector style;
    style.formality = scenario.at("style").at("formality").as_double();
    style.directness = scenario.at("style").at("directness").as_double();

    const usc::Json& second_row = scenario.at("second_agent");
    usc::Agent second;
    second.id = second_row.get("id").as_string();
    for (const usc::Json& belief_row : second_row.at("beliefs").items()) {
        usc::Belief belief;
        belief.proposition = usc::Proposition::from_json(belief_row);
        belief.proposition.polarity = "+";
        belief.logit_val = belief_row.at("logit").as_double();
        belief.support_for = belief.logit_val;
        second.beliefs[belief.proposition.core_key()] = belief;
    }

    usc::DialoguePlanner planner;
    usc::Json plans = usc::Json::array();
    for (const usc::Agent* speaker : {&agent, &second})
        for (const usc::Json& act : scenario.at("acts").items()) {
            usc::ConversationState conv;
            conv.conv_id = "conv:probe";
            usc::ActionCandidate chosen;
            chosen.action.action_id = "act";
            chosen.action.dialogue_act = act.as_string().empty() ? usc::Json() : act;
            usc::DialoguePlan plan = planner.plan(
                *speaker, conv, chosen, "agent:player_1", style, "goal:find_out",
                scenario.at("world_seed").as_string(), scenario.get("world_time").as_int());
            usc::Json entry = plan.as_json();
            entry["asked_for"] = act;
            entry["committed"] = static_cast<long long>(plan.committed_propositions().size());
            entry["turn_count"] = conv.turn_count;
            plans.push(entry);
        }

    usc::Json loops = usc::Json::array();
    for (const usc::Json& one : scenario.at("anti_loop").items()) {
        usc::ConversationState conv;
        for (const usc::Json& act : one.at("history").items())
            conv.last_acts.push_back(act.as_string());
        usc::Json entry = usc::Json::object();
        entry["history"] = one.at("history");
        entry["act"] = one.at("act");
        entry["ok"] = planner.anti_loop_ok(conv, one.at("act").as_string());
        loops.push(entry);
    }

    const usc::Json& setup = scenario.at("conversation");
    usc::ConversationState conv;
    conv.conv_id = setup.at("conv_id").as_string();
    for (const usc::Json& one : setup.at("participants").items())
        conv.participants.push_back(one.as_string());
    usc::Json counts = usc::Json::array();
    for (const usc::Json& pair : setup.at("topics").items())
        counts.push(usc::Json(conv.note_topic(pair.items()[0].as_string(),
                                              pair.items()[1].as_int())));

    usc::Json out = usc::Json::object();
    out["plans"] = plans;
    out["anti_loop"] = loops;
    out["topic_counts"] = counts;
    out["conversation"] = conv.as_json();
    // And the round-trip, because a conversation has to survive a save.
    out["restored"] = usc::ConversationState::from_json(conv.as_json()).as_json();
    return out;
}

// ---- factions --------------------------------------------------------------

usc::Json run_factions(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();

    usc::Director director;
    for (const usc::Json& row : scenario.at("factions").items())
        director.add_faction(usc::Faction::from_json(row));

    usc::Json out = usc::Json::object();
    std::vector<usc::DirectorReason> heat_reasons;
    for (const usc::Json& row : scenario.at("heat_events").items())
        director.add_heat(row.at("faction").as_string(), row.at("amount").as_double(),
                          row.at("reason").as_string(), &heat_reasons);
    usc::Json heat = usc::Json::array();
    for (const auto& reason : heat_reasons) {
        usc::Json line = usc::Json::object();
        line["code"] = reason.code;
        line["amount"] = reason.amount;
        line["detail"] = reason.detail;
        heat.push(line);
    }
    out["heat"] = heat;

    usc::Json scheduled = usc::Json::array();
    usc::Json steps = usc::Json::array();
    for (const usc::Json& delta : scenario.at("steps").items()) {
        world.world_time += delta.as_int();
        auto reasons = director.step(world, delta.as_int(),
            [&](const usc::Faction& faction, long long latency) {
                usc::Json row = usc::Json::object();
                row["faction"] = faction.faction_id;
                row["latency"] = latency;
                row["at"] = world.world_time;
                scheduled.push(row);
            });
        usc::Json rows = usc::Json::array();
        for (const auto& reason : reasons) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            rows.push(line);
        }
        usc::Json entry = usc::Json::object();
        entry["delta"] = delta;
        entry["reasons"] = rows;
        steps.push(entry);
    }
    out["steps"] = steps;
    out["scheduled"] = scheduled;

    usc::Json state = usc::Json::object();
    for (const auto& entry : director.factions())
        state.fields()[entry.first] = entry.second.as_json();
    out["factions"] = state;

    usc::Json owners = usc::Json::object();
    for (const usc::Json& place : scenario.at("territory_lookups").items()) {
        const usc::Faction* owner = director.faction_controlling(place.as_string());
        owners.fields()[place.as_string()] = owner ? usc::Json(owner->faction_id) : usc::Json();
    }
    out["controlling"] = owners;
    return out;
}

// ---- commitment ------------------------------------------------------------

usc::Json run_commitment(const usc::Json& scenario) {
    std::vector<std::string> seed_parts;
    for (const usc::Json& one : scenario.at("seed_parts").items())
        seed_parts.push_back(one.as_string());

    usc::Json out = usc::Json::object();
    usc::Json rows = usc::Json::array();
    for (const usc::Json& row : scenario.at("cases").items()) {
        std::vector<usc::Candidate> candidates;
        for (const usc::Json& one : row.at("candidates").items()) {
            usc::Candidate candidate;
            candidate.proposition = usc::Proposition::from_json(one);
            candidate.confidence = one.at("confidence").as_double();
            candidate.relevance = one.at("relevance").as_double();
            candidate.affirmed = one.at("affirmed").as_bool();
            candidates.push_back(candidate);
        }
        std::vector<std::string> forbidden;
        for (const usc::Json& one : row.at("forbidden").items())
            forbidden.push_back(one.as_string());

        usc::Commitment commitment = usc::select(
            candidates, row.at("act").as_string(), row.at("limit").as_int(),
            seed_parts, forbidden, row.at("max_sentences").as_int());

        usc::Json entry = commitment.as_json();
        usc::Json facts = usc::Json::array();
        for (const std::string& one : commitment.rendered_facts()) facts.push(usc::Json(one));
        entry["rendered_facts"] = facts;
        entry["factual_moves"] = static_cast<long long>(commitment.factual_moves().size());
        entry["propositions"] = static_cast<long long>(commitment.propositions().size());
        usc::Json trace = usc::Json::array();
        for (const auto& reason : commitment.reasons) {
            usc::Json line = usc::Json::object();
            line["code"] = reason.code;
            line["amount"] = reason.amount;
            line["detail"] = reason.detail;
            trace.push(line);
        }
        entry["reasons"] = trace;
        rows.push(entry);
    }
    out["commitments"] = rows;

    usc::Json grid = usc::Json::array();
    for (const usc::Json& confidence : scenario.at("certainty_grid").items()) {
        usc::Json pair = usc::Json::array();
        pair.push(confidence);
        pair.push(usc::Json(usc::certainty_for(confidence.as_double())));
        grid.push(pair);
    }
    out["certainty"] = grid;

    // A lie keeps the real belief on record: the speaker's own belief never
    // changes, because lying is not self-persuasion.
    const usc::Json& deception = scenario.at("deception");
    usc::Proposition instead = usc::Proposition::from_json(deception.at("assert_instead"));
    usc::SemanticMove honest;
    honest.act = "assert";
    usc::Proposition held;
    held.predicate = "was_at";
    held.slots["agent"] = usc::Json(std::string("agent:vee"));
    held.slots["place"] = usc::Json(std::string("place:clinic"));
    held.slots["when"] = usc::Json(static_cast<long long>(900));
    honest.proposition = held;
    honest.certainty = usc::CERTAIN;
    honest.believed_probability = 0.93;

    usc::Json lies = usc::Json::array();
    for (const usc::Json& honesty : deception.at("honesty").items()) {
        usc::SemanticMove lied = usc::deceive(honest, instead, honesty.as_string());
        usc::Json entry = lied.as_json();
        entry["is_deceptive"] = lied.is_deceptive();
        entry["is_factual"] = lied.is_factual();
        lies.push(entry);
    }
    out["deception"] = lies;
    out["honest_move"] = honest.as_json();
    return out;
}

// ---- sociolinguistics ------------------------------------------------------

usc::Agent speaker_from(const usc::Json& row) {
    usc::Agent agent;
    agent.id = row.get("id").as_string();
    agent.social_status = row.get("social_status").as_double(0.4);
    agent.dialect = row.get("dialect");
    for (const auto& entry : row.at("education").fields())
        agent.education[entry.first] = entry.second.as_double();
    for (const usc::Json& role : row.at("roles").items()) agent.roles.push_back(role);
    for (const usc::Json& one : row.at("identities").items()) agent.identities.push_back(one);
    for (const auto& entry : row.at("big_five").fields())
        agent.big_five[entry.first] = entry.second.as_double();
    agent.affect.mood = usc::Vec3::from_json(row.at("mood"));
    for (const auto& entry : row.at("emotions").fields())
        agent.affect.active_emotions[entry.first] = entry.second.as_double();
    for (const auto& subject : row.at("relationships").fields())
        for (const auto& field : subject.second.fields())
            agent.relationships[subject.first][field.first] = field.second.as_double();
    agent.appearance = row.get("appearance");
    for (const auto& subject : row.at("reputation").fields())
        for (const auto& field : subject.second.fields())
            agent.reputation[subject.first][field.first] = field.second.as_double();
    return agent;
}

usc::Json run_sociolinguistics(const usc::Json& scenario) {
    usc::World world;
    world.places = scenario.at("places");
    for (const usc::Json& row : scenario.at("listeners").items()) {
        usc::Agent one = speaker_from(row);
        world.agents[one.id] = one;
    }

    usc::SociolinguisticEngine engine;
    usc::AppearanceEngine appearance;
    const usc::Json& reactions = scenario.at("reactions");

    usc::Json styles = usc::Json::array();
    for (const usc::Json& speaker_row : scenario.at("speakers").items()) {
        usc::Agent speaker = speaker_from(speaker_row);
        for (const usc::Json& room : scenario.at("rooms").items())
            for (const usc::Json& listener : scenario.at("listeners").items())
                for (const usc::Json& regard_row : scenario.at("regards").items()) {
                    usc::OrderedMap<double> regard;
                    bool has_regard = !regard_row.is_null();
                    if (has_regard)
                        for (const auto& entry : regard_row.fields())
                            regard[entry.first] = entry.second.as_double();
                    usc::StyleVector style = engine.compute_style(
                        speaker, listener.at("id").as_string(), room, &world,
                        has_regard ? &regard : nullptr, &reactions, &appearance, true);
                    usc::Json entry = usc::Json::object();
                    entry["speaker"] = speaker_row.get("id");
                    entry["room"] = room;
                    entry["listener"] = listener.get("id");
                    entry["regard"] = regard_row;
                    entry["style"] = style.as_json();
                    styles.push(entry);
                }
        // And with nobody in front of them, which skips accommodation entirely.
        usc::StyleVector alone = engine.compute_style(speaker, "", usc::Json(), &world);
        usc::Json entry = usc::Json::object();
        entry["speaker"] = speaker_row.get("id");
        entry["room"] = usc::Json();
        entry["listener"] = usc::Json();
        entry["style"] = alone.as_json();
        styles.push(entry);
    }

    usc::Json statuses = usc::Json::array();
    for (const usc::Json& row : scenario.at("status_cases").items()) {
        usc::Agent observer = speaker_from(row.at("observer"));
        usc::Agent subject = speaker_from(row.at("subject"));
        usc::Json entry = usc::Json::object();
        entry["bare"] = engine.social_status(subject);
        entry["perceived"] = engine.social_status(subject, &observer);
        entry["with_appearance"] = engine.social_status(subject, &observer,
                                                        &reactions, &appearance);
        usc::Json none = usc::Json::object();
        entry["without_reactions"] = engine.social_status(subject, &observer,
                                                          &none, &appearance);
        statuses.push(entry);
    }

    // The four politeness strategies are chosen by five comparisons, and a
    // style vector out of the full pipeline lands on one of those boundaries
    // essentially never. A grid does.
    usc::Json grid = usc::Json::array();
    const usc::Json& axes = scenario.at("politeness_grid");
    for (const usc::Json& formality : axes.at("formality").items())
        for (const usc::Json& directness : axes.at("directness").items()) {
            usc::Json row = usc::Json::array();
            row.push(formality);
            row.push(directness);
            row.push(usc::Json(usc::SociolinguisticEngine::politeness(
                formality.as_double(), directness.as_double())));
            grid.push(row);
        }

    usc::Json out = usc::Json::object();
    out["styles"] = styles;
    out["status"] = statuses;
    out["politeness_grid"] = grid;
    return out;
}

// ---- standing --------------------------------------------------------------

usc::Agent viewer_from(const usc::Json& row) {
    usc::Agent agent;
    agent.id = row.get("id").as_string();
    for (const auto& subject : row.at("relationships").fields())
        for (const auto& field : subject.second.fields())
            agent.relationships[subject.first][field.first] = field.second.as_double();
    for (const auto& subject : row.at("reputation").fields())
        for (const auto& field : subject.second.fields())
            agent.reputation[subject.first][field.first] = field.second.as_double();
    return agent;
}

usc::Json run_standing(const usc::Json& scenario) {
    usc::StandingEngine engine(scenario.at("conduct"),
                               scenario.get("enabled").as_bool());
    usc::Json out = usc::Json::object();

    usc::Json judgements = usc::Json::array();
    for (const usc::Json& row : scenario.at("observers").items()) {
        usc::Agent observer = viewer_from(row);
        for (const usc::Json& claim_row : scenario.at("propositions").items()) {
            usc::Proposition claim = usc::Proposition::from_json(claim_row);
            for (const usc::Json& confidence : scenario.at("confidences").items()) {
                auto [deltas, reasons] = engine.judge(observer, claim,
                                                      confidence.as_double());
                usc::Json entry = usc::Json::object();
                entry["observer"] = row.get("id");
                entry["proposition"] = claim.key();
                entry["confidence"] = confidence;
                entry["describes_conduct"] = engine.describes_conduct(claim);
                entry["actor"] = engine.actor_of(claim);
                entry["victim"] = engine.victim_of(claim);
                entry["deltas"] = deltas_json(deltas);
                usc::Json trace = usc::Json::array();
                for (const auto& reason : reasons) {
                    usc::Json line = usc::Json::object();
                    line["code"] = reason.code;
                    line["amount"] = reason.amount;
                    line["detail"] = reason.detail;
                    trace.push(line);
                }
                entry["reasons"] = trace;
                judgements.push(entry);
            }
        }
    }
    out["judgements"] = judgements;

    usc::Json warmths = usc::Json::array();
    std::vector<usc::ActionDefinition> catalogue =
        usc::default_candidates([&] {
            usc::Json context = usc::Json::object();
            context["interlocutor"] = std::string("agent:you");
            return context;
        }());
    for (const usc::Json& row : scenario.at("warmth_cases").items()) {   // absent -> none
        usc::Agent agent = viewer_from(row);
        const std::string other = row.at("other").as_string();
        usc::Json entry = usc::Json::object();
        entry["agent"] = row.get("id");
        entry["warmth"] = engine.warmth(agent, other);
        usc::Json pulls = usc::Json::object();
        for (const usc::ActionDefinition& action : catalogue)
            pulls.fields()[action.action_id] = usc::Json(
                engine.bias_for(agent, action, other));
        entry["bias"] = pulls;
        usc::Json sway = usc::Json::array();
        for (const usc::Json& bridge : scenario.at("bridge_scores").items())
            sway.push(usc::Json(engine.influence(agent, other, bridge.as_double())));
        entry["influence"] = sway;
        warmths.push(entry);
    }
    out["warmth"] = warmths;
    return out;
}

// ---- appearance ------------------------------------------------------------

usc::Json run_appearance(const usc::Json& scenario) {
    usc::AppearanceEngine engine;
    std::vector<usc::Agent> observers, subjects;
    for (const usc::Json& row : scenario.at("observers").items()) {
        usc::Agent one;
        one.id = row.get("id").as_string();
        one.epistemic = row.get("epistemic");
        observers.push_back(one);
    }
    for (const usc::Json& row : scenario.at("subjects").items()) {
        usc::Agent one;
        one.id = row.get("id").as_string();
        one.appearance = row.get("appearance");
        subjects.push_back(one);
    }

    std::vector<usc::ActionDefinition> catalogue;
    for (const usc::Agent& subject : subjects) {
        usc::Json context = usc::Json::object();
        context["interlocutor"] = subject.id;
        for (const usc::ActionDefinition& action : usc::default_candidates(context))
            catalogue.push_back(action);
    }

    auto sweep = [&](const usc::Json& reactions) {
        usc::Json rows = usc::Json::array();
        for (const usc::Agent& observer : observers)
            for (const usc::Agent& subject : subjects) {
                usc::AppearanceReading reading = engine.read(&observer, subject, reactions);
                usc::Json entry = usc::Json::object();
                entry["observer"] = observer.id;
                entry["subject"] = subject.id;
                entry["status"] = reading.status;
                entry["threat"] = reading.threat;
                entry["signals"] = strings_json(reading.signals);
                entry["tokens"] = strings_json(reading.tokens);
                entry["drawn_to"] = engine.drawn_to(&observer, subject);
                // EVERY action, including those aimed at somebody else. The
                // target check inside `bias_for` is what stops a reading of one
                // person colouring what you do to another, and a probe that
                // pre-filters never asks it the question.
                usc::Json pulls = usc::Json::array();
                for (const usc::ActionDefinition& action : catalogue) {
                    usc::Json row = usc::Json::object();
                    row["action"] = action.action_id;
                    row["target"] = action.target;
                    row["pull"] = engine.bias_for(&observer, action, &subject, reactions);
                    pulls.push(row);
                }
                entry["bias"] = pulls;
                rows.push(entry);
            }
        return rows;
    };

    usc::Json out = usc::Json::object();
    out["with_reactions"] = sweep(scenario.at("reactions"));
    // And with none, which is every shipped pack: every read empty, nothing
    // consumed, a run byte-identical to before this module existed.
    out["without_reactions"] = sweep(usc::Json::object());
    return out;
}

// ---- diffusion -------------------------------------------------------------

usc::Belief belief_from(const usc::Json& row) {
    usc::Belief belief;
    belief.proposition = usc::Proposition::from_json(row);
    belief.proposition.polarity = "+";
    belief.logit_val = row.get("logit").as_double();
    belief.support_for = row.get("support_for").as_double();
    belief.support_against = row.get("support_against").as_double();
    for (const auto& entry : row.at("origin_counts").fields())
        belief.origin_counts[entry.first] = entry.second.as_int();
    belief.hops = row.get("hops").as_int();
    belief.spreading = row.get("spreading").as_bool(true);
    belief.txn_time = row.get("txn_time");
    return belief;
}

/// Forty people in one gossipy room, over the encounter cap on purpose.
void build_crowd(usc::World& world) {
    for (int index = 0; index < 40; ++index) {
        usc::Agent one;
        char name[32];
        std::snprintf(name, sizeof name, "agent:c%02d", index);
        one.id = name;
        one.set_location(usc::Json(std::string("place:square")));
        for (int other = 0; other < 40; ++other) {
            if (other == index) continue;
            char who[32];
            std::snprintf(who, sizeof who, "agent:c%02d", other);
            one.relationships[who]["familiarity"] = 0.9;
            one.relationships[who]["liking"] = 0.5;
        }
        usc::Belief belief;
        belief.proposition.predicate = "was_at";
        belief.proposition.slots["agent"] = usc::Json(std::string("agent:x"));
        belief.proposition.slots["place"] = usc::Json(std::string("place:square"));
        belief.proposition.slots["when"] = usc::Json(static_cast<long long>(600));
        belief.logit_val = 2.0;
        belief.support_for = 2.0;
        belief.origin_counts["1"] = 1;
        belief.txn_time = usc::Json(static_cast<long long>(600));
        one.beliefs[belief.proposition.core_key()] = belief;
        world.agents[one.id] = one;
    }
}

usc::Json run_diffusion(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    world.places = scenario.at("places");
    world.predicates = scenario.at("predicates");

    const usc::Json& cast = scenario.at("agents");
    if (cast.kind() == usc::Json::Kind::String) {
        build_crowd(world);
    } else {
        for (const usc::Json& row : cast.items()) {
            usc::Agent agent;
            agent.id = row.get("id").as_string();
            agent.set_location(row.get("location"));
            for (const usc::Json& role : row.at("roles").items()) agent.roles.push_back(role);
            for (const usc::Json& net : row.at("networks").items())
                agent.networks.push_back(net.as_string());
            for (const auto& entry : row.at("education").fields())
                agent.education[entry.first] = entry.second.as_double();
            for (const auto& subject : row.at("relationships").fields())
                for (const auto& field : subject.second.fields())
                    agent.relationships[subject.first][field.first] = field.second.as_double();
            for (const usc::Json& secret : row.at("secrets").items())
                agent.secrets.push_back(secret);
            for (const usc::Json& belief_row : row.at("beliefs").items()) {
                usc::Belief belief = belief_from(belief_row);
                agent.beliefs[belief.proposition.core_key()] = belief;
            }
            world.agents[agent.id] = agent;
        }
    }

    usc::Json ledger = usc::Json::array();
    usc::DiffusionRuntime runtime;
    runtime.process_event = [&](const usc::Event& event) {
        usc::Json row = usc::Json::object();
        row["event_id"] = event.event_id;
        row["world_time"] = event.world_time;
        row["type"] = event.type;
        row["actor"] = event.actor;
        row["location"] = event.location;
        row["payload"] = event.payload;
        ledger.push(row);
    };

    usc::DiffusionEngine engine;
    usc::Json out = usc::Json::object();

    auto run = [&](long long delta) {
        usc::Json rows = usc::Json::array();
        for (const auto& reason : engine.step(world, runtime, delta,
                                              scenario.at("player_id").as_string())) {
            usc::Json row = usc::Json::object();
            row["code"] = reason.code;
            row["amount"] = reason.amount;
            row["detail"] = reason.detail;
            rows.push(row);
        }
        return rows;
    };

    usc::Json steps = usc::Json::array();
    if (const usc::Json* extra = scenario.find("extra_steps")) {
        for (const usc::Json& row : extra->items()) {
            usc::Json entry = usc::Json::object();
            entry["delta"] = row.at("delta");
            entry["reasons"] = run(row.at("delta").as_int());
            steps.push(entry);
        }
    } else {
        usc::Json entry = usc::Json::object();
        entry["delta"] = scenario.at("delta_minutes");
        entry["reasons"] = run(scenario.get("delta_minutes").as_int());
        steps.push(entry);
    }
    out["steps"] = steps;
    out["events"] = ledger;

    // Which beliefs stopped spreading, because stifling is the mechanism that
    // makes a rumour saturate rather than reach everybody.
    usc::Json spreading = usc::Json::object();
    for (const auto& entry : world.agents) {
        usc::Json rows = usc::Json::object();
        for (const auto& belief : entry.second.beliefs)
            rows.fields()[belief.first] = usc::Json(belief.second.spreading);
        spreading.fields()[entry.first] = rows;
    }
    out["spreading"] = spreading;
    return out;
}

// ---- content ---------------------------------------------------------------

usc::Json strings_json(const std::vector<std::string>& values) {
    usc::Json out = usc::Json::array();
    for (const std::string& one : values) out.push(usc::Json(one));
    return out;
}

usc::Json run_content(const usc::Json& scenario) {
    const std::string player = scenario.at("player_id").as_string();
    const std::string addressee = scenario.at("addressee_id").as_string();

    usc::Json topics = usc::Json::array();
    for (const usc::Json& row : scenario.at("topics").items()) {
        usc::Topic topic = usc::Topic::from_json(row);
        usc::Json entry = usc::Json::object();
        entry["topic_id"] = topic.topic_id;
        entry["label"] = topic.label;
        entry["aliases"] = strings_json(topic.aliases);
        entry["query"] = topic.resolved_query(player);
        entry["player_claim"] = topic.resolved_player_claim(player);
        entry["player_assertion"] = topic.resolved_player_assertion(player);
        entry["affirm"] = topic.phrasing_for(true);
        entry["deny"] = topic.phrasing_for(false);
        usc::Json reactions = usc::Json::array();
        for (const usc::Json& one : topic.resolved_reactions(player, addressee))
            reactions.push(one);
        entry["reactions"] = reactions;
        topics.push(entry);
    }

    std::vector<usc::Secret> secrets = usc::secrets_from(scenario.at("secrets"));
    usc::Json rows = usc::Json::array();
    for (const usc::Secret& secret : secrets) {
        usc::Json entry = usc::Json::object();
        entry["secret_id"] = secret.secret_id;
        entry["avoid_label"] = secret.avoid_label;
        entry["guards_topics"] = strings_json(secret.guards_topics);
        entry["summary"] = secret.summary;
        entry["surface_forms"] = strings_json(secret.surface_forms);
        entry["protects"] = strings_json(secret.protects);
        entry["about"] = strings_json(secret.about);
        entry["min_trust"] = secret.min_trust;
        entry["cover_story"] = secret.cover_story;
        entry["cover_phrasings"] = secret.cover_phrasings;
        rows.push(entry);
    }

    usc::Json covers = usc::Json::array();
    for (const usc::Json& pair : scenario.at("covers").items()) {
        usc::Json per_secret = usc::Json::array();
        for (const usc::Secret& secret : secrets)
            per_secret.push(usc::Json(secret.covers(pair.items()[0].as_string(),
                                                    pair.items()[1].as_string())));
        covers.push(per_secret);
    }

    usc::Json guarding = usc::Json::object();
    for (const usc::Json& topic : scenario.at("guarding").items()) {
        usc::Json who = usc::Json::array();
        for (const usc::Secret& secret : usc::secrets_guarding(secrets, topic.as_string()))
            who.push(usc::Json(secret.secret_id));
        guarding.fields()[topic.as_string()] = who;
    }

    usc::Json forms = usc::Json::object();
    for (const auto& entry : usc::surface_forms_by_label(secrets))
        forms.fields()[entry.first] = strings_json(entry.second);

    usc::AliasIndex index = usc::AliasIndex::build(scenario.at("aliases"));
    usc::Json ordered = usc::Json::array();
    for (const auto& entry : index.entries) {
        usc::Json pair = usc::Json::array();
        pair.push(usc::Json(entry.first));
        pair.push(usc::Json(entry.second));
        ordered.push(pair);
    }
    usc::Json matches = usc::Json::array();
    for (const usc::Json& row : scenario.at("lookups").items()) {
        std::vector<std::string> exclude;
        for (const usc::Json& one : row.at("exclude").items()) exclude.push_back(one.as_string());
        std::string found = index.match(row.at("text").as_string(), exclude);
        matches.push(found.empty() ? usc::Json() : usc::Json(found));
    }
    usc::Json clashes = usc::Json::array();
    for (const auto& clash : index.conflicts()) {
        usc::Json row = usc::Json::array();
        row.push(usc::Json(std::get<0>(clash)));
        row.push(usc::Json(std::get<1>(clash)));
        row.push(usc::Json(std::get<2>(clash)));
        clashes.push(row);
    }

    usc::Json out = usc::Json::object();
    out["topics"] = topics;
    out["secrets"] = rows;
    out["protected_keys"] = strings_json(
        [&] {
            std::set<std::string> keys = usc::protected_keys(secrets);
            return std::vector<std::string>(keys.begin(), keys.end());
        }());
    out["covers"] = covers;
    out["guarding"] = guarding;
    out["avoid_labels"] = strings_json(usc::avoid_labels(secrets));
    out["surface_forms_by_label"] = forms;
    out["alias_entries"] = ordered;
    out["alias_matches"] = matches;
    out["alias_conflicts"] = clashes;
    return out;
}

// ---- distortion ------------------------------------------------------------

usc::Json run_distortion(const usc::Json& scenario) {
    const usc::Json& setup = scenario.at("world");
    usc::World world;
    for (const usc::Json& id : setup.at("agents").items()) {
        usc::Agent one;
        one.id = id.as_string();
        world.agents[one.id] = one;
    }
    const usc::Json& row = setup.at("speaker");
    usc::Agent speaker;
    speaker.id = row.get("id").as_string();
    speaker.set_location(row.get("location"));
    for (const auto& subject : row.at("relationships").fields())
        for (const auto& field : subject.second.fields())
            speaker.relationships[subject.first][field.first] = field.second.as_double();
    usc::Routine routine = usc::Routine::from_json(row.at("routine"));

    std::vector<std::string> protect;
    for (const usc::Json& key : scenario.at("protected").items())
        protect.push_back(key.as_string());

    usc::Json out = usc::Json::array();
    for (const usc::Json& claim_row : scenario.at("propositions").items()) {
        usc::Proposition claim = usc::Proposition::from_json(claim_row);
        for (const usc::Json& weight_row : scenario.at("weights").items()) {
            usc::OrderedMap<double> weights;
            bool has_weights = !weight_row.is_null();
            if (has_weights)
                for (const auto& entry : weight_row.fields())
                    weights[entry.first] = entry.second.as_double();
            for (const usc::Json& seed_row : scenario.at("seeds").items()) {
                std::vector<std::uint8_t> seed =
                    usc::derive_seed(seed_row.as_string(), "probe", 0, 0, "distortion");
                auto result = usc::distort(claim, speaker, world, seed,
                                           has_weights ? &weights : nullptr,
                                           protect, &routine);
                usc::Json entry = usc::Json::object();
                entry["proposition"] = claim.core_key();
                entry["weights"] = weight_row;
                entry["seed"] = seed_row;
                if (result) {
                    entry["kind"] = result->kind;
                    entry["retold"] = result->proposition.as_json();
                    entry["core_key"] = result->proposition.core_key();
                    entry["detail"] = result->detail;
                    entry["described"] = usc::describe(result->kind, result->detail);
                } else {
                    entry["kind"] = usc::Json();
                }
                out.push(entry);
            }
        }
    }
    usc::Json wrapper = usc::Json::object();
    wrapper["outcomes"] = out;
    return wrapper;
}

// ---- social ----------------------------------------------------------------

usc::Json terms_json(const std::vector<std::pair<std::string, double>>& terms) {
    usc::Json out = usc::Json::array();
    for (const auto& term : terms) {
        usc::Json row = usc::Json::array();
        row.push(usc::Json(term.first));
        row.push(usc::Json(term.second));
        out.push(row);
    }
    return out;
}

usc::Json deltas_json(const std::vector<usc::ProposedDelta>& deltas) {
    usc::Json out = usc::Json::array();
    for (const auto& delta : deltas) {
        usc::Json row = usc::Json::object();
        row["module"] = delta.key.module;
        row["field"] = delta.key.field;
        row["entity"] = delta.key.entity_id;
        row["subject"] = delta.key.subject_id ? usc::Json(*delta.key.subject_id) : usc::Json();
        row["dimension"] = delta.key.dimension ? usc::Json(*delta.key.dimension) : usc::Json();
        row["amount"] = delta.amount;
        row["reason"] = delta.reason;
        row["source"] = delta.source_module;
        out.push(row);
    }
    return out;
}

usc::Json run_social(const usc::Json& scenario) {
    usc::OrderedMap<usc::Agent> cast;
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        for (const usc::Json& role : row.at("roles").items()) agent.roles.push_back(role);
        for (const auto& entry : row.at("schwartz").fields())
            agent.schwartz[entry.first] = entry.second.as_double();
        for (const auto& subject : row.at("relationships").fields())
            for (const auto& field : subject.second.fields())
                agent.relationships[subject.first][field.first] = field.second.as_double();
        agent.affect.mood = usc::Vec3::from_json(row.at("mood"));
        for (const auto& entry : row.at("emotions").fields())
            agent.affect.active_emotions[entry.first] = entry.second.as_double();
        cast[agent.id] = agent;
    }

    usc::ValueEngine values;
    usc::SocialExchangeEngine exchange;
    usc::SocialIdentityEngine identity;
    usc::NormEngine norms;
    usc::SocialNetworkEngine network;
    usc::TheoryOfMindEngine tom;
    usc::ImpressionManagementEngine impression;
    usc::InterpersonalEngine interpersonal;
    usc::AffectEngine affect;

    usc::Json out = usc::Json::object();

    usc::Json active = usc::Json::object();
    for (const usc::Json& salient : scenario.at("salient").items()) {
        usc::Json per_agent = usc::Json::object();
        for (const auto& entry : cast) {
            usc::Json row = usc::Json::object();
            for (const auto& value : values.active_values(entry.second, salient.as_string(),
                                                          scenario.at("identity_values")))
                row.fields()[value.first] = usc::Json(value.second);
            per_agent.fields()[entry.first] = row;
        }
        active.fields()[salient.as_string()] = per_agent;
    }
    out["active_values"] = active;

    usc::Json ties = usc::Json::array();
    for (const usc::Json& pair : scenario.at("ties").items()) {
        const usc::Agent& who = *cast.find(pair.items()[0].as_string());
        usc::Json row = usc::Json::object();
        row["agent"] = pair.items()[0];
        row["other"] = pair.items()[1];
        row["tie_strength"] = network.tie_strength(who, pair.items()[1].as_string());
        row["bridge_score"] = network.bridge_score(who);
        auto [code, amount] = tom.expected_reaction(who, pair.items()[1].as_string(), "threaten");
        row["tom_threaten"] = amount;
        auto [agency, communion] = interpersonal.stance(who, pair.items()[1].as_string(), affect);
        row["agency"] = agency;
        row["communion"] = communion;
        ties.push(row);
    }
    out["ties"] = ties;

    std::vector<usc::ActionDefinition> catalogue =
        usc::default_candidates(usc::Json::object());
    usc::Json per_context = usc::Json::array();
    for (const usc::Json& context : scenario.at("contexts").items()) {
        usc::Json row = usc::Json::object();
        row["front_stage"] = impression.front_stage(context);
        row["impression_weight"] = impression.weight(context);
        usc::Json actions = usc::Json::object();
        for (const usc::ActionDefinition& action : catalogue) {
            usc::Json entry = usc::Json::object();
            entry["norm"] = terms_json(norms.value_terms(action, context));
            entry["exchange"] = terms_json(exchange.value_terms(action, context));
            entry["face"] = terms_json(impression.value_terms(action, context));
            actions.fields()[action.action_id] = entry;
        }
        row["terms"] = actions;
        per_context.push(row);
    }
    out["contexts"] = per_context;

    usc::Json commitments = usc::Json::array();
    for (const usc::Json& row : scenario.at("commitments").items())
        commitments.push(deltas_json(exchange.on_commitment_resolved(
            "agent:bartender", row.at("other").as_string(), row.at("fulfilled").as_bool())));
    out["commitments"] = commitments;

    usc::Event threat;
    const usc::Json& row = scenario.at("threat_event");
    threat.event_id = row.get("event_id").as_int();
    threat.type = row.get("type").as_string();
    threat.actor = row.get("actor");
    threat.location = row.get("location");
    threat.payload = row.get("payload");
    usc::Json threats = usc::Json::array();
    for (const std::string& named : {std::string(), std::string("id:override")}) {
        auto outcome = identity.on_event(*cast.find("agent:bartender"), threat, named);
        usc::Json entry = usc::Json::object();
        entry["given"] = named.empty() ? usc::Json() : usc::Json(named);
        entry["proposals"] = deltas_json(outcome.proposals);
        entry["appraisal"] = outcome.appraisal_boost;
        threats.push(entry);
    }
    out["identity_threat"] = threats;

    usc::Json dependence = usc::Json::array();
    for (const usc::Json& pair : scenario.at("dependence").items())
        dependence.push(usc::Json(exchange.dependence(pair.items()[0].as_double(),
                                                      pair.items()[1].as_double())));
    out["dependence"] = dependence;
    return out;
}

// ---- routine ---------------------------------------------------------------

usc::Json routine_reasons_json(const std::vector<usc::RoutineReason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        out.push(row);
    }
    return out;
}

usc::Json run_routine(const usc::Json& scenario) {
    usc::World world;
    world.world_time = scenario.get("world_time").as_int();
    usc::OrderedMap<usc::Routine> routines;
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        world.agents[agent.id] = agent;
        routines[agent.id] = usc::Routine::from_json(row.at("routine"));
    }

    usc::RoutineEngine engine;
    usc::Json out = usc::Json::object();

    // Where each block resolves, hour by hour, before anybody is moved.
    usc::Json at_times = usc::Json::array();
    for (const usc::Json& when : scenario.at("times").items()) {
        usc::Json row = usc::Json::object();
        row["at"] = when;
        usc::Json where = usc::Json::object();
        for (const auto& entry : engine.whereabouts(world, routines, when.as_int()))
            where.fields()[entry.first] = usc::Json(entry.second);
        row["whereabouts"] = where;
        at_times.push(row);
    }
    out["whereabouts"] = at_times;

    usc::Json meetings = usc::Json::object();
    for (const auto& entry : engine.meeting_opportunities(
             world, routines, scenario.get("samples").as_int(24))) {
        usc::Json who = usc::Json::array();
        for (const std::string& one : entry.second) who.push(usc::Json(one));
        meetings.fields()[entry.first] = who;
    }
    out["meeting_opportunities"] = meetings;

    out["seeded"] = routine_reasons_json(engine.seed(world, routines));

    usc::Json steps = usc::Json::array();
    for (const usc::Json& row : scenario.at("step").items()) {
        world.world_time = row.at("to").as_int();
        usc::Json entry = usc::Json::object();
        entry["to"] = row.at("to");
        entry["reasons"] = routine_reasons_json(
            engine.step(world, routines, row.at("delta").as_int()));
        usc::Json where = usc::Json::object();
        for (const auto& agent : world.agents)
            where.fields()[agent.first] = agent.second.location();
        entry["locations"] = where;
        steps.push(entry);
    }
    out["steps"] = steps;
    return out;
}

// ---- perception ------------------------------------------------------------

usc::Json run_perception(const usc::Json& scenario) {
    usc::World world;
    world.global_seed = scenario.at("global_seed").as_string();
    world.world_time = scenario.get("world_time").as_int();
    world.places = scenario.at("places");
    for (const usc::Json& row : scenario.at("agents").items()) {
        usc::Agent agent;
        agent.id = row.get("id").as_string();
        agent.set_location(row.get("location"));
        world.agents[agent.id] = agent;
    }
    for (const usc::Json& row : scenario.at("exposure").items())
        world.set_exposure(row.get("agent").as_string(),
                           row.get("channel").as_string(), row.get("value"));

    usc::PerceptionEngine engine;
    usc::Json out = usc::Json::array();
    for (const usc::Json& row : scenario.at("events").items()) {
        if (const usc::Json* move = row.find("move")) {
            // Somebody walks. The occupancy index is cached against the global
            // location epoch, so this is what proves the cache invalidates.
            usc::Agent* who = world.agents.find(move->at("agent").as_string());
            if (who) who->set_location(move->at("to"));
        }
        usc::Event event;
        event.event_id = row.get("event_id").as_int();
        event.world_time = row.get("world_time").as_int();
        event.type = row.get("type").as_string();
        event.actor = row.get("actor");
        event.location = row.get("location");
        event.payload = row.get("payload");

        usc::Json seen = usc::Json::array();
        for (const usc::Observation& observation : engine.filter(event, world)) {
            usc::Json entry = usc::Json::object();
            entry["observer"] = observation.observer;
            entry["modality"] = observation.modality;
            entry["quality"] = observation.quality;
            seen.push(entry);
        }
        usc::Json result = usc::Json::object();
        result["event_id"] = event.event_id;
        result["observations"] = seen;
        out.push(result);
    }
    usc::Json wrapper = usc::Json::object();
    wrapper["events"] = out;
    return wrapper;
}

// ---- topology --------------------------------------------------------------

usc::Agent agent_from(const usc::Json& row) {
    usc::Agent agent;
    agent.id = row.get("id").as_string();
    for (const usc::Json& one : row.at("networks").items())
        agent.networks.push_back(one.as_string());
    for (const usc::Json& one : row.at("roles").items()) agent.roles.push_back(one);
    for (const usc::Json& one : row.at("identities").items()) agent.identities.push_back(one);
    for (const auto& entry : row.at("education").fields())
        agent.education[entry.first] = entry.second.as_double();
    agent.epistemic = row.at("epistemic");
    return agent;
}

usc::Json run_topology(const usc::Json& scenario) {
    const usc::Json& predicates = scenario.at("predicates");
    usc::OrderedMap<usc::Agent> cast;
    for (const usc::Json& row : scenario.at("agents").items())
        cast[row.get("id").as_string()] = agent_from(row);

    usc::Json out = usc::Json::object();

    usc::Json all_circles = usc::Json::object();
    for (const auto& entry : cast) {
        usc::Json names = usc::Json::array();
        for (const std::string& one : usc::circles(entry.second)) names.push(usc::Json(one));
        all_circles.fields()[entry.first] = names;
    }
    out["circles"] = all_circles;

    usc::Json who_bridges = usc::Json::object();
    for (const auto& entry : usc::bridges(cast)) {
        usc::Json names = usc::Json::array();
        for (const std::string& one : entry.second) names.push(usc::Json(one));
        who_bridges.fields()[entry.first] = names;
    }
    out["bridges"] = who_bridges;

    usc::Json passes = usc::Json::array();
    for (const usc::Json& pair : scenario.at("pairs").items()) {
        usc::Proposition claim;
        claim.predicate = pair.at("predicate").as_string();
        claim.slots["subject"] = usc::Json(std::string("agent:x"));
        auto [weight, reason] = usc::may_pass_on(
            predicates, claim, *cast.find(pair.at("speaker").as_string()),
            *cast.find(pair.at("listener").as_string()), pair.at("place"));
        usc::Json row = usc::Json::object();
        row["speaker"] = pair.at("speaker");
        row["listener"] = pair.at("listener");
        row["predicate"] = pair.at("predicate");
        row["weight"] = weight;
        row["code"] = reason.first;
        row["detail"] = reason.second;
        passes.push(row);
    }
    out["may_pass_on"] = passes;

    usc::Json budgets = usc::Json::object();
    for (auto& entry : cast)
        budgets.fields()[entry.first] = usc::Json(usc::attention_budget(entry.second));
    out["attention_budget"] = budgets;

    if (const usc::Json* attention = scenario.find("attention")) {
        // Spending more than anybody's budget at several times of day, so both
        // the cap and the day boundary are exercised.
        usc::Json spending = usc::Json::object();
        for (auto& entry : cast) {
            usc::Json rows = usc::Json::array();
            for (const usc::Json& when : attention->at("spend_at").items()) {
                usc::Json accepted = usc::Json::array();
                for (long long i = 0; i < attention->at("per_time").as_int(); ++i)
                    accepted.push(usc::Json(usc::spend_attention(entry.second, when.as_int())));
                usc::Json row = usc::Json::object();
                row["at"] = when;
                row["accepted"] = accepted;
                row["day"] = entry.second.attention_day;
                row["spent"] = entry.second.attention_spent;
                rows.push(row);
            }
            spending.fields()[entry.first] = rows;
        }
        out["attention_spending"] = spending;
    }
    return out;
}

// ---- policy ---------------------------------------------------------------

usc::Json contributions_json(
        const std::vector<std::tuple<std::string, double, double, double>>& rows) {
    usc::Json out = usc::Json::array();
    for (const auto& row : rows) {
        usc::Json entry = usc::Json::array();
        entry.push(usc::Json(std::get<0>(row)));
        entry.push(usc::Json(std::get<1>(row)));
        entry.push(usc::Json(std::get<2>(row)));
        entry.push(usc::Json(std::get<3>(row)));
        out.push(entry);
    }
    return out;
}

usc::Json run_policy(const usc::Json& scenario) {
    usc::PolicyEngine::Params params;
    if (const usc::Json* found = scenario.at("params").find("use_prospect"))
        params.use_prospect = found->as_bool();
    if (const usc::Json* found = scenario.at("params").find("temperature"))
        params.temperature = found->as_double();
    usc::PolicyEngine engine(params);

    const usc::Json& agent_row = scenario.at("agent");
    usc::DecidingAgent agent;
    agent.id = agent_row.get("id").as_string();
    agent.global_seed = agent_row.get("global_seed").as_string();
    for (const auto& entry : agent_row.at("big_five").fields())
        agent.big_five[entry.first] = entry.second.as_double();

    usc::AffectState affect;
    affect.mood.a = scenario.get("arousal").as_double();
    agent.affect = &affect;

    usc::OrderedMap<double> weights;
    for (const auto& entry : scenario.at("weights").fields())
        weights[entry.first] = entry.second.as_double();
    usc::OrderedMap<double> tendencies;
    for (const auto& entry : scenario.at("tendencies").fields())
        tendencies[entry.first] = entry.second.as_double();

    const usc::Json& terms = scenario.at("terms");
    const usc::Json& bias = scenario.at("bias");
    auto term_provider = [&](const usc::ActionDefinition& action) {
        std::vector<std::pair<std::string, double>> out;
        for (const usc::Json& row : terms.at(action.action_id).items())
            out.emplace_back(row.items()[0].as_string(), row.items()[1].as_double());
        return out;
    };
    auto bias_provider = [&](const usc::ActionDefinition& action) {
        const usc::Json* found = bias.find(action.action_id);
        return found ? found->as_double() : 0.0;
    };
    bool has_bias = !bias.fields().empty();

    std::vector<usc::ActionDefinition> candidates;
    if (scenario.at("catalogue").kind() == usc::Json::Kind::String) {
        // Forty affordances that score identically -- a pack's own catalogue is
        // this size, and the reference one is not.
        for (int index = 0; index < 40; ++index) {
            usc::ActionDefinition action;
            action.action_id = "act_" + std::to_string(index);
            action.action_class = "share";
            action.is_dialogue = true;
            action.outcomes = {{"safety", 0.1, 0.5, 0.0, "tied"}};
            candidates.push_back(action);
        }
    } else {
        candidates = usc::default_candidates(scenario.at("context"));
    }
    std::vector<usc::ActionCandidate> scored =
        engine.score(candidates, weights, term_provider, tendencies, bias_provider, has_bias);

    usc::Json ranked = usc::Json::array();
    for (const usc::ActionCandidate& candidate : scored) {
        usc::Json row = usc::Json::object();
        row["action_id"] = candidate.action.action_id;
        row["utility"] = candidate.utility;
        row["contributions"] = contributions_json(candidate.contributions);
        ranked.push(row);
    }

    auto [chosen, reasons] = engine.select(agent, scored,
                                           scenario.get("event_id").as_int(),
                                           scenario.get("world_time").as_int());
    usc::Json trace = usc::Json::array();
    for (const auto& reason : reasons) {
        usc::Json row = usc::Json::object();
        row["code"] = reason.code;
        row["amount"] = reason.amount;
        row["detail"] = reason.detail;
        trace.push(row);
    }

    usc::Json out = usc::Json::object();
    out["scored"] = ranked;
    out["chosen"] = chosen.action.action_id;
    out["reasons"] = trace;

    // A single seeded pick proves almost nothing: with four candidates a wrong
    // seed agrees one time in four. Sweeping the event id turns that into a
    // distribution, which a wrong seed cannot reproduce by luck.
    if (const usc::Json* sweep = scenario.find("sweep_events")) {
        usc::Json picks = usc::Json::array();
        for (long long event = 0; event < sweep->as_int(); ++event)
            picks.push(usc::Json(engine.select(agent, scored, event,
                                               scenario.get("world_time").as_int())
                                 .first.action.action_id));
        out["sweep"] = picks;
    }
    return out;
}

// ---- memory ---------------------------------------------------------------

std::shared_ptr<usc::MemoryItem> memory_from(const usc::Json& row) {
    auto item = std::make_shared<usc::MemoryItem>();
    item->memory_id = row.get("memory_id").as_string();
    item->owner = "agent:self";
    item->type = row.get("type").as_string();
    item->content = row.get("content").as_string();
    item->importance = row.get("importance").as_double();
    item->emotional_valence = row.get("emotional_valence").as_double();
    for (const usc::Json& when : row.at("presentations").items())
        item->presentations.push_back(when.as_int());
    const usc::Json& proposition = row.at("proposition");
    if (!proposition.is_null()) item->proposition = usc::Proposition::from_json(proposition);
    if (!item->presentations.empty()) item->world_time = usc::Json(item->presentations.front());
    return item;
}

/// The one generated fixture: nine occasions of the same person doing the same
/// thing, plus three unrelated, so consolidation has a pattern to find and
/// something to leave alone.
usc::MemoryList repeating_pattern() {
    usc::MemoryList out;
    for (int index = 0; index < 9; ++index) {
        auto item = std::make_shared<usc::MemoryItem>();
        item->memory_id = "m:seen_" + std::to_string(index);
        item->owner = "agent:self";
        item->type = "episodic";
        item->content = "saw it again";
        item->importance = 0.1 + 0.05 * index;
        item->emotional_valence = -0.2 - 0.05 * index;
        item->presentations = {1000 + 100 * index};
        item->world_time = usc::Json(1000 + 100 * static_cast<long long>(index));
        usc::Proposition prop;
        prop.predicate = "was_at";
        prop.slots["agent"] = usc::Json(std::string("agent:vee"));
        prop.slots["place"] = usc::Json(std::string("place:dock"));
        prop.slots["when"] = usc::Json(static_cast<long long>(1000 + 100 * index));
        item->proposition = prop;
        out.push_back(item);
    }
    for (int index = 0; index < 3; ++index) {
        auto item = std::make_shared<usc::MemoryItem>();
        item->memory_id = "m:other_" + std::to_string(index);
        item->owner = "agent:self";
        item->type = "episodic";
        item->content = "something else";
        item->importance = 0.4;
        item->emotional_valence = 0.1;
        item->presentations = {1500 + 10 * index};
        item->world_time = usc::Json(1500 + 10 * static_cast<long long>(index));
        out.push_back(item);
    }
    return out;
}

/// Forty memories that are identical in every respect that scores. Only the
/// sort's stability decides which seven come back.
usc::MemoryList identical_memories(int count, const char* prefix,
                                   long long when, const char* type) {
    usc::MemoryList out;
    for (int index = 0; index < count; ++index) {
        auto item = std::make_shared<usc::MemoryItem>();
        item->memory_id = std::string(prefix) + std::to_string(index);
        item->owner = "agent:self";
        item->type = type;
        item->content = "identical";
        item->importance = 0.5;
        item->emotional_valence = 0.0;
        item->presentations = {when};
        item->world_time = usc::Json(when);
        out.push_back(item);
    }
    return out;
}

usc::Json run_memory(const usc::Json& scenario) {
    usc::MemoryEngine::Params params;
    const usc::Json& overrides = scenario.at("params");
    if (const usc::Json* found = overrides.find("episodic_cap"))
        params.episodic_cap = found->as_int();
    if (const usc::Json* found = overrides.find("total_cap"))
        params.total_cap = found->as_int();
    if (const usc::Json* found = overrides.find("summary_cap"))
        params.summary_cap = found->as_int();
    usc::MemoryEngine engine(params);

    usc::MemoryList memories;
    const usc::Json& items = scenario.at("items");
    if (items.kind() == usc::Json::Kind::String) {
        const std::string& which = items.as_string();
        if (which == "generated:identical_memories")
            memories = identical_memories(40, "m:same_", 1000, "episodic");
        else if (which == "generated:identical_episodes")
            memories = identical_memories(30, "m:ep_", 5000, "episodic");
        else
            memories = repeating_pattern();
    } else {
        for (const usc::Json& row : items.items()) memories.push_back(memory_from(row));
    }

    usc::Json out = usc::Json::object();
    long long now = scenario.get("now").as_int();

    if (const usc::Json* reinforce = scenario.find("reinforce")) {
        long long times = reinforce->get("times").as_int();
        long long from = reinforce->get("from").as_int();
        long long every = reinforce->get("every").as_int();
        for (long long step = 0; step < times; ++step)
            engine.reinforce(*memories.front(), from + every * step);
    }

    if (const usc::Json* retrieve = scenario.find("retrieve")) {
        std::vector<usc::Proposition> topics;
        for (const usc::Json& topic : retrieve->at("topics").items())
            topics.push_back(usc::Proposition::from_json(topic));
        // Seeded, so the DRAW is exercised rather than the threshold fallback.
        std::vector<usc::Retrieved> found = engine.retrieve(
            memories, retrieve->get("at").as_int(), topics,
            retrieve->get("mood_valence").as_double(),
            {"probe", "agent:recaller", "recall"});
        usc::Json rows = usc::Json::array();
        for (const usc::Retrieved& one : found) {
            usc::Json row = usc::Json::object();
            row["activation"] = one.activation;
            row["probability"] = one.probability;
            row["memory_id"] = one.memory->memory_id;
            rows.push(row);
        }
        out["retrieved"] = rows;
    }

    if (const usc::Json* at = scenario.find("consolidate_at")) {
        std::vector<usc::MemoryReason> reasons = engine.decay_and_consolidate(memories, at->as_int());
        usc::Json trace = usc::Json::array();
        for (const auto& reason : reasons) {
            usc::Json row = usc::Json::object();
            row["code"] = reason.code;
            row["amount"] = reason.amount;
            row["detail"] = reason.detail;
            trace.push(row);
        }
        out["consolidation"] = trace;
    }

    usc::Json stored = usc::Json::array();
    for (const auto& item : memories) stored.push(item->as_json(usc::Json(now)));
    out["memories"] = stored;
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "engine_cases.json";
    // `<cases>/../../../worldpacks` -- the probe lives at port/cpp/probe.
    {
        std::string cases(path);
        std::size_t at = cases.find_last_of("/\\");
        std::string dir = at == std::string::npos ? "." : cases.substr(0, at);
        pack_root() = dir + "/../../../worldpacks";
        probe_root() = dir;
    }
    usc::Json document = usc::Json::parse(read_file(path));

    usc::Json report = usc::Json::object();
    struct Section { const char* name; usc::Json (*run)(const usc::Json&); };
    const Section sections[] = {{"contracts", run_contracts},
                                {"roundtrip", run_roundtrip},
                                {"predicates", run_predicates},
                                {"metahuman", run_metahuman},
                                {"sdk", run_sdk},
                                {"pack_loader", run_pack_loader},
                                {"inspect", run_inspect},
                                {"snapshot", run_snapshot},
                                {"runtime", run_runtime},
                                {"provider", run_provider},
                                {"actionbridge", run_actionbridge},
                                {"validator", run_validator},
                                {"parser", run_parser},
                                {"interpretation", run_interpretation},
                                {"grounding", run_grounding},
                                {"flat", run_flat},
                                {"tuning", run_tuning},
                                {"revision", run_revision},
                                {"pursuit", run_pursuit},
                                {"notes", run_notes},
                                {"promises", run_promises},
                                {"common_knowledge", run_common_knowledge},
                                {"climate", run_climate},
                                {"contagion", run_contagion},
                                {"medium", run_medium},
                                {"agency", run_agency},
                                {"dialogue", run_dialogue},
                                {"factions", run_factions},
                                {"commitment", run_commitment},
                                {"sociolinguistics", run_sociolinguistics},
                                {"standing", run_standing},
                                {"appearance", run_appearance},
                                {"diffusion", run_diffusion},
                                {"content", run_content},
                                {"distortion", run_distortion},
                                {"social", run_social},
                                {"routine", run_routine},
                                {"perception", run_perception},
                                {"topology", run_topology},
                                {"affect", run_affect},
                                {"relationship", run_relationship},
                                {"identity", run_identity},
                                {"policy", run_policy},
                                {"memory", run_memory}};

    for (const Section& section : sections) {
        usc::Json group = usc::Json::object();
        for (const usc::Json& scenario : document.at(section.name).items())
            group.fields()[scenario.get("id").as_string()] = to_bits(section.run(scenario));
        report.fields()[section.name] = group;
    }

    std::printf("%s\n", report.dump(2).c_str());
    return 0;
}
