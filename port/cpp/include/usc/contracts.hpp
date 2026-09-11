// `usc/contracts.py`. The stable, engine-facing objects, and the constants that
// are single sources of truth.
//
// THIS FILE IS A COPY, AND A COPY DRIFTS. That is not a reason to avoid it -- a
// port needs these values -- but it is a reason the probe compares them field by
// field against the Python side rather than trusting that somebody remembered.
// `OPTIONAL_LAYERS` exists in the first place because the command line, the
// `/capabilities` response and the documentation had come to disagree about what
// exists; a second implementation is one more place that can disagree.
//
// The dataclasses that only carry a payload between the runtime and an engine
// -- `ReplayResult`, `ValidationReport` and the rest -- are here as plain
// structs. They have no behaviour to get wrong, and leaving them out would mean
// the port's surface does not match the contract the SDK documents.
#pragma once

#include <map>
#include <optional>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

/// The SDK's default player agent id. Defined once so nothing repeats the
/// literal: a game that names its player differently must keep working, and
/// code comparing against a hardcoded copy is exactly how the parser once made
/// the player addressable as an NPC.
inline constexpr const char* DEFAULT_PLAYER_ID = "agent:player_1";

/// The runtime's version. Reported to an engine as `runtime_version`, so a copy
/// that drifts tells an integrator the wrong thing about which build they are
/// talking to. Unrelated to the snapshot schema version, which moves only when
/// the save format does.
inline constexpr const char* RUNTIME_VERSION = "1.21.0";

/// The mechanics a studio can decline, in one place. Each is a `RuntimeConfig`
/// field defaulting to false, and for each of them off is exactly neutral --
/// asserted by test, not promised.
inline const std::vector<std::pair<std::string, std::string>>& optional_layers() {
    static const std::vector<std::pair<std::string, std::string>> layers = {
        {"action_bridge",
         "the runtime asks your engine to carry out physical acts and waits to be "
         "told what happened"},
        {"climate",
         "places have a mood -- how candid, how suspicious, how open to a stranger "
         "-- moved by what happens in them and carried between rooms by whoever "
         "walks"},
        {"pursuit",
         "characters act on their goals instead of only moving on routines and "
         "gossiping at random"},
        {"media",
         "a claim can travel by telephone as well as by conversation: fewer "
         "bystanders, more detail lost, weighed a little lower (needs pursuit)"},
        {"notes",
         "somebody who cannot reach the person they needed leaves word where they "
         "stand, and a note is still there afterwards (needs pursuit)"},
        {"promises",
         "a promise comes due and is judged on what the person it was made to came "
         "to believe, moving trust, liking and a reputation for reliability"},
        {"contagion",
         "a little of a speaker's mood moves to whoever they are talking to"},
        {"common_knowledge",
         "track not who knows a thing but who watched everyone else find out; a "
         "secret that is out in the open stops working as one"},
        {"standing",
         "how you treat one person changes how the rest of them treat you -- "
         "carried as a claim, so somebody who was only told about it judges you "
         "too, and judges you less far than somebody who watched"},
    };
    return layers;
}

/// Which layers need another one under them to do anything at all.
inline const OrderedMap<std::string>& layer_requires() {
    static const OrderedMap<std::string>* table = [] {
        auto* fresh = new OrderedMap<std::string>();
        (*fresh)["media"] = "pursuit";
        (*fresh)["notes"] = "pursuit";
        return fresh;
    }();
    return *table;
}

/// State an engine READS and nothing in the runtime ever WRITES.
///
/// This runtime produced the same defect six times: a field consulted by three
/// or four engines that only ever holds what a pack authored, so a studio sets
/// it once and watches it stay there for the life of the world. Each took a
/// measurement to find.
///
/// An entry here is a DECISION, not a to-do. Inventing a producer for
/// `dependence` -- which is about needing somebody, not about how they treated
/// you -- would be putting a number where an idea belongs.
inline const OrderedMap<std::string>& authored_only_fields() {
    static const OrderedMap<std::string>* table = [] {
        auto* fresh = new OrderedMap<std::string>();
        (*fresh)["dependence"] =
            "how much you need somebody. Read when deciding whether to call on "
            "them for backup. Authored, because it is about obligation and "
            "circumstance, not about conduct, and nothing in the runtime models "
            "either yet.";
        (*fresh)["kinship"] = "family. A fact about a cast, not a thing play changes.";
        (*fresh)["loyalty"] =
            "who somebody is with when it matters. Authored per world; a faction "
            "layer could move it and none does.";
        (*fresh)["favor_debt"] =
            "what one character owes another. The promises layer moves the "
            "player's debts and not theirs to each other.";
        (*fresh)["owes_favor"] =
            "the same debt, read from the creditor's side when deciding who can be "
            "asked for something. Moved by nothing for the same reason as "
            "favor_debt.";
        (*fresh)["reputation:status"] =
            "prestige as this observer sees it, read by `social_status`. Conduct "
            "moves `decent` and appearance moves how somebody is read; neither is "
            "prestige, and nothing produces prestige.";
        return fresh;
    }();
    return *table;
}

/// Everything a studio can configure. Defaults match the Python dataclass
/// exactly, because "off is neutral" is only true if off is what you get.
struct RuntimeConfig {
    std::string runtime_id = "unscripted:main";
    std::string schema_version = RUNTIME_VERSION;
    std::string world_pack_path = "worldpacks/cyberpunk-block";
    std::string storage_path = ":memory:";
    bool debug_traces = true;
    bool strict = true;
    std::string player_id = DEFAULT_PLAYER_ID;
    /// Where the player begins. Absent means "ask the world pack" -- the default
    /// used to be a place id from the reference scene, so every other pack
    /// started the player somewhere that did not exist.
    std::optional<std::string> player_start_location;
    bool load_initial_state = true;
    bool population_lod = false;

    // The nine optional layers, in the order `optional_layers()` declares them.
    bool action_bridge = false;
    bool climate = false;
    bool pursuit = false;
    bool media = false;
    bool notes = false;
    bool promises = false;
    bool contagion = false;
    bool common_knowledge = false;
    bool standing = false;

    int action_timeout_minutes = 60;
    std::string voice_backend = "none";
    std::optional<std::string> voice_model;
    std::string projection_scope = "all";
    /// capability name -> BUILTIN / EXTERNAL / DISABLED, as a host declares it.
    Json capabilities = Json::object();
    /// `{"provider": "template" | "http", "endpoint": ...}`.
    Json text_realizer = Json::object();
    std::string canon_mode = "strict";
    /// Who writes a sentence that carries a fact. "controlled" (the default)
    /// releases the pack's own phrasing for anything that asserts something;
    /// "provider" lets a text provider write it under a weaker, lexical
    /// contract. See `usc/contracts.py` for the whole argument.
    std::string semantic_release = "controlled";

    /// Read a layer by name, so a caller can walk `optional_layers()` rather
    /// than repeat the list -- which is how the three copies drifted apart.
    bool layer(const std::string& name) const {
        if (name == "action_bridge")    return action_bridge;
        if (name == "climate")          return climate;
        if (name == "pursuit")          return pursuit;
        if (name == "media")            return media;
        if (name == "notes")            return notes;
        if (name == "promises")         return promises;
        if (name == "contagion")        return contagion;
        if (name == "common_knowledge") return common_knowledge;
        if (name == "standing")         return standing;
        return false;
    }

    void set_layer(const std::string& name, bool on) {
        if (name == "action_bridge")         action_bridge = on;
        else if (name == "climate")          climate = on;
        else if (name == "pursuit")          pursuit = on;
        else if (name == "media")            media = on;
        else if (name == "notes")            notes = on;
        else if (name == "promises")         promises = on;
        else if (name == "contagion")        contagion = on;
        else if (name == "common_knowledge") common_knowledge = on;
        else if (name == "standing")         standing = on;
    }
};

struct ParsedCommand {
    std::string raw_text;
    std::string intent;
    double confidence = 0.0;
    std::string actor_id;
    Json target_id;
    Json location_id;
    std::optional<Proposition> proposition;
    Json amount;
    long long minutes = 0;
    Json topic;
    Json metadata;
    std::vector<Json> reasons;
};

struct EventReceipt {
    long long event_id = 0;
    std::string event_type;
    long long world_time = 0;
    std::vector<std::string> observed_by;
    Json reasons;
};

struct DialogueResponse {
    std::string speaker_id;
    std::string text;
    std::string act;
    std::string verdict;
    double utility = 0.0;
    std::vector<Json> reasons;
    Json style;
};

struct TurnResult {
    long long world_time = 0;
    std::string location_id;
    ParsedCommand parsed;
    std::string message;
    std::vector<Json> observations;
    std::vector<EventReceipt> receipts;
    std::optional<DialogueResponse> npc_response;
    std::string developer_trace;
    bool done = false;
};

struct ValidationIssue {
    std::string severity;
    std::string code;
    std::string message;
    std::string path;
};

struct ValidationReport {
    bool ok = true;
    std::vector<ValidationIssue> issues;

    void add(const std::string& severity, const std::string& code,
             const std::string& message, const std::string& path = "") {
        issues.push_back({severity, code, message, path});
        if (severity == "error") ok = false;
    }
};

}  // namespace usc
