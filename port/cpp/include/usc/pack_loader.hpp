// `usc/world.py: load_world_pack`. A directory of JSON becomes a world.
//
// Kept out of `world.hpp` because that header is the container and this is a
// file reader: a world built in memory by a probe, a test or an engine bridge
// has no business dragging <fstream> in behind it.
//
// This IS shippable, unlike the pack VALIDATOR, and the difference is worth
// stating. A shipped game loads its pack every time it starts; nothing in a
// shipped game validates one. Validation is a build-time check against the same
// files on a developer's machine, and it stays in Python for the same reason the
// SQLite store does.
#pragma once

#include <algorithm>
#include <fstream>
#include <stdexcept>
#include <sstream>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/world.hpp"

namespace usc {

namespace detail_ {

/// The JSON in one file, or an empty object when there is none.
///
/// A missing file is NOT an error: a pack that declares no topics simply has no
/// `topics.json`, and every read here is optional in exactly that way.
/// Returning an empty OBJECT rather than null is not catchable, and that is
/// worth saying rather than leaving as a gap: every caller reads this through
/// `find`, which answers the same on a null as on an empty object. It is written
/// this way because Python returns `{}` and because the next reader of this file
/// should not have to work out that null would also have done.
inline Json read_pack_file(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) return Json::object();
    std::ostringstream buffer;
    buffer << file.rdbuf();
    return Json::parse(buffer.str());
}

inline std::string join_path(const std::string& directory, const std::string& name) {
    if (directory.empty()) return name;
    char last = directory.back();
    if (last == '/' || last == '\\') return directory + name;
    return directory + "/" + name;
}

}  // namespace detail_

/// Read a world pack.
///
/// `character_names` is the sorted list of `characters/*.json` basenames. It is
/// a PARAMETER rather than a directory walk because listing a directory is the
/// one thing in this file that a console will not do the way a desktop does --
/// a packed archive, a virtual filesystem, a platform SDK's own reader. The host
/// says what is in there; this reads it.
inline World load_world_pack(const std::string& path,
                             const std::vector<std::string>& character_names) {
    auto read = [&path](const std::string& name) {
        return detail_::read_pack_file(detail_::join_path(path, name));
    };

    Json world_data = read("world.json");
    Json scenario = read("scenario.json");
    Json canon = read("canon.json");
    Json topics_data = read("topics.json");
    Json initial_state = read("initial_state.json");

    World w;
    const Json* seed = scenario.find("global_seed");
    w.global_seed = seed ? seed->py_str() : "unscripted-seed-0";
    const Json* clock = scenario.find("world_time");
    w.world_time = clock ? clock->as_int() : 0;
    w.pack_path = path;

    auto section = [&world_data](const char* name) {
        const Json* found = world_data.find(name);
        return (found && found->truthy()) ? *found : Json::object();
    };
    w.places = section("places");
    w.entities = section("entities");
    w.channels = section("channels");
    w.identity_values = section("identity_values");
    w.command_aliases = section("command_aliases");
    w.standing_conduct = section("standing_conduct");
    // `_note` keys are how every section of a pack carries its own explanation,
    // and they are strings rather than tables. Skipped here rather than special
    // cased at every read.
    Json reactions = Json::object();
    Json authored_reactions = section("appearance_reactions");
    for (const auto& entry : authored_reactions.fields())
        if (!entry.first.empty() && entry.first[0] != '_'
            && entry.second.kind() == Json::Kind::Object)
            reactions[entry.first] = entry.second;
    w.appearance_reactions = reactions;
    w.dialogue_templates = section("dialogue_templates");
    w.slang_lexicon = section("slang_lexicon");
    w.diffusion_params = section("diffusion");
    w.tuning = section("tuning");
    w.routine_params = section("routine");
    w.decorative_vocabulary = section("decorative_vocabulary");

    // Pack-declared predicates must be registered BEFORE any proposition from
    // this pack is parsed: slot order defines a proposition's canonical key.
    const Json* predicates = canon.find("predicates");
    std::string basename = path;
    std::size_t slash = basename.find_last_of("/\\");
    if (slash != std::string::npos) basename = basename.substr(slash + 1);
    if (predicates && predicates->truthy()) {
        OrderedMap<PredicateSpec> specs;
        for (const auto& entry : predicates->fields())
            specs[entry.first] = PredicateSpec::from_json(entry.second);
        register_predicates(specs, "world pack " + basename);
        for (const auto& entry : predicates->fields()) {
            const Json& spec = entry.second;
            // Which competence applies to a claim, and what it takes to
            // recognise one. Both are world content: "you need an engineer to
            // see that this was deliberate" is a fact about a setting.
            const Json* domain = spec.find("domain");
            if (domain && domain->truthy()) w.predicate_domains[entry.first] = *domain;
            const Json* needs = spec.find("requires_competence");
            if (needs && needs->truthy()) w.predicate_competence[entry.first] = *needs;
            w.predicates[entry.first] = spec.truthy() ? spec : Json::object();
        }
    }
    // `canon.get("canon_facts", [])` -- an empty LIST, not null, and the
    // difference reaches the exported state.
    const Json* facts = canon.find("canon_facts");
    w.canon_facts = facts ? *facts : Json::array();

    const Json* topics = topics_data.find("topics");
    if (topics && topics->truthy())
        for (const Json& entry : topics->items()) {
            Topic topic = Topic::from_json(entry);
            w.topics[topic.topic_id] = topic;
        }

    for (const std::string& name : character_names) {
        Json cd = read(detail_::join_path("characters", name));
        Agent agent;
        // Python reads `cd["id"]` and raises when it is not there. Reproduced as
        // a refusal rather than as an agent with an empty name: a file that
        // cannot be read produced exactly that, and the world then had a
        // nameless character in it that no caller had asked for. The C ABI found
        // this by asking for a pack that does not exist.
        const Json* declared_id = cd.find("id");
        if (!declared_id || !declared_id->truthy())
            throw std::invalid_argument(
                "characters/" + name + " has no \"id\", or could not be read at "
                "all. Every character file in " + path + " must name the agent it "
                "describes.");
        agent.id = declared_id->as_string();
        auto numbers = [&cd](const char* key) {
            OrderedMap<double> out;
            const Json* found = cd.find(key);
            if (found) for (const auto& entry : found->fields())
                out[entry.first] = entry.second.as_double();
            return out;
        };
        agent.big_five = numbers("big_five");
        agent.schwartz = numbers("schwartz");
        agent.needs = numbers("needs");
        // `education.get("domains", education)` -- a pack may nest the table or
        // write it flat, and both have shipped.
        const Json* education = cd.find("education");
        const Json* domains = education ? education->find("domains") : nullptr;
        if (domains) for (const auto& entry : domains->fields())
            agent.education[entry.first] = entry.second.as_double();
        else if (education) for (const auto& entry : education->fields())
            agent.education[entry.first] = entry.second.as_double();

        const Json* identities = cd.find("identities");
        if (identities) for (const Json& one : identities->items())
            agent.identities.push_back(one);
        const Json* roles = cd.find("roles");
        if (roles) for (const Json& one : roles->items()) agent.roles.push_back(one);
        // Python's dataclass defaults are EMPTY DICTS, not None, and the
        // difference reaches the exported state as `{}` against `null`.
        const Json* appearance = cd.find("appearance");
        agent.appearance = (appearance && appearance->truthy()) ? *appearance
                                                                : Json::object();
        const Json* relationships = cd.find("relationships");
        if (relationships) for (const auto& entry : relationships->fields()) {
            OrderedMap<double> row;
            for (const auto& field : entry.second.fields())
                row[field.first] = field.second.as_double();
            agent.relationships[entry.first] = row;
        }
        const Json* secrets = cd.find("secrets");
        if (secrets) for (const Json& one : secrets->items())
            agent.secrets.push_back(one);
        const Json* goals = cd.find("goals");
        if (goals) for (const Json& one : goals->items()) agent.goals.push_back(one);
        agent.set_location(cd.get("location"));

        const Json* names = cd.find("names");
        agent.public_name = names ? names->get("public") : Json();
        agent.objective_name = names ? names->get("objective") : Json();
        const Json* aliases = names ? names->find("aliases") : nullptr;
        if (aliases) for (const Json& one : aliases->items())
            agent.aliases.push_back(one.py_str());

        const Json* routine = cd.find("routine");
        if (routine && routine->truthy()) agent.routine = *routine;
        const Json* status = cd.find("social_status");
        agent.social_status = status ? status->as_double() : 0.4;
        const Json* resources = cd.find("resources");
        agent.resources = resources ? resources->as_double() : 0.4;
        agent.dialect = cd.get("dialect");
        const Json* values = cd.find("values");
        if (values) for (const auto& entry : values->fields())
            agent.values[entry.first] = entry.second.as_double();
        const Json* epistemic = cd.find("epistemic");
        agent.epistemic = (epistemic && epistemic->truthy()) ? *epistemic
                                                             : Json::object();
        const Json* networks = cd.find("networks");
        if (networks) for (const Json& one : networks->items())
            agent.networks.push_back(one.py_str());
        const Json* voice = cd.find("voice");
        agent.voice = (voice && voice->truthy()) ? *voice : Json::object();
        const Json* contacts = cd.find("contacts");
        if (contacts) for (const Json& one : contacts->items())
            agent.contacts.push_back(one.py_str());

        // `__post_init__`: a resting mood derived from personality.
        agent.initialise_affect();
        w.agents[agent.id] = agent;
    }

    const Json* exposure = world_data.find("media_exposure");
    if (exposure) for (const Json& row : exposure->items()) {
        Json value = Json::object();
        const Json* attention = row.find("attention");
        value["attention"] = attention ? *attention : Json(0.5);
        w.set_exposure(row.at("agent").as_string(), row.at("channel").as_string(),
                       value);
    }

    // Raw dicts; the runtime builds the factions and their clocks.
    const Json* factions = world_data.find("factions");
    if (factions) for (const Json& row : factions->items()) w.factions.push_back(row);

    const Json* events = scenario.find("events");
    if (events) for (const Json& row : events->items()) {
        Event e;
        // A FRESH id, not the authored one: the loader numbers the scheduled
        // events itself, which is why the runtime's own ids start at 1000.
        e.event_id = w.new_event_id();
        const Json* when = row.find("world_time");
        e.world_time = when ? when->as_int() : w.world_time;
        e.type = row.at("type").as_string();
        e.actor = row.get("actor");
        e.location = row.get("location");
        const Json* payload = row.find("payload");
        e.payload = (payload && payload->truthy()) ? *payload : Json::object();
        const Json* canonical = row.find("canonical");
        e.canonical = canonical ? canonical->truthy() : true;
        w.scenario_events.push_back(e);
    }

    /// What a pack says before its first prompt. Optional.
    const Json* intro = scenario.find("intro");
    w.scenario_intro = (intro && intro->truthy()) ? intro->py_str() : "";
    const Json* focus = scenario.find("focus_agents");
    if (focus) for (const Json& one : focus->items())
        w.focus_agents.push_back(one.py_str());
    const Json* start = scenario.find("player_start");
    if (start && start->truthy()) w.player_start = start->py_str();
    else if (!w.places.fields().empty()) w.player_start = w.places.fields().begin()->first;
    const Json* identity = scenario.find("world_id");
    if (identity && identity->truthy()) w.world_id = identity->py_str();
    const Json* beliefs = initial_state.find("beliefs");
    w.initial_beliefs = beliefs ? *beliefs : Json::array();

    return w;
}

}  // namespace usc
