// The C ABI, implemented over the C++ core.
//
// Everything here is marshalling and refusing to throw. There is no simulation
// in this file and there must never be: a behaviour that lives only behind the
// ABI is a behaviour the probes do not compare, and the whole value of this port
// is that they compare everything.
//
// The one rule worth stating twice: NOTHING THROWS. An exception crossing a C
// boundary is undefined behaviour, and on a console it is a crash report with no
// stack. Every entry point is wrapped, every failure becomes a status code, and
// the message is kept where `usc_last_error` can read it.
#include "usc.h"

#include <exception>
#include <memory>
#include <new>
#include <string>
#include <vector>

#include "usc/pack_loader.hpp"
#include "usc/sdk.hpp"
#include "usc/state_view.hpp"

namespace {

/// The last error from a call that had no handle to put it on.
std::string& global_error() {
    static std::string message;
    return message;
}

}  // namespace

/// One world, one player, one simulation -- plus the buffer every returned
/// string lives in until the next call.
struct usc_runtime {
    usc::World world;
    std::unique_ptr<usc::UnscriptedRuntime> sdk;
    /// Owned by the runtime and valid until the NEXT call on this handle. A
    /// caller marshals out of it and never frees it, which is the part of a C
    /// ABI that otherwise needs an allocator contract nobody agrees on.
    std::string answer;
    std::string error;
};

namespace {

/// Run something, and turn anything it throws into a status code.
template <typename Body>
usc_status guarded(usc_runtime* runtime, Body body) {
    std::string& error = runtime ? runtime->error : global_error();
    try {
        error.clear();
        return body();
    } catch (const usc::StateImportError& failure) {
        error = failure.what();
        return USC_ERR_SAVE;
    } catch (const usc::UnknownIntent& failure) {
        // Not an argument error: the id is well formed and the runtime simply
        // does not hold that intent any more. An integrator reads the difference.
        error = failure.what();
        return USC_ERR_STATE;
    } catch (const usc::InvalidResult& failure) {
        error = failure.what();
        return USC_ERR_ARGUMENT;
    } catch (const std::invalid_argument& failure) {
        error = failure.what();
        return USC_ERR_ARGUMENT;
    } catch (const std::exception& failure) {
        error = failure.what();
        return USC_ERR_RUNTIME;
    } catch (...) {
        error = "the runtime refused the call and said nothing about why";
        return USC_ERR_RUNTIME;
    }
}

usc_status hand_back(usc_runtime* runtime, const usc::Json& value,
                     const char** out_json) {
    if (!out_json) return USC_ERR_ARGUMENT;
    runtime->answer = value.dump();
    *out_json = runtime->answer.c_str();
    return USC_OK;
}

usc_status hand_back(usc_runtime* runtime, const std::string& text,
                     const char** out_text) {
    if (!out_text) return USC_ERR_ARGUMENT;
    runtime->answer = text;
    *out_text = runtime->answer.c_str();
    return USC_OK;
}

usc::Json reasons_json(const std::vector<usc::Reason>& reasons) {
    usc::Json out = usc::Json::array();
    for (const usc::Reason& one : reasons) out.push(one.as_json());
    return out;
}

}  // namespace

extern "C" {

int usc_abi_version(void) { return USC_ABI_VERSION; }

const char* usc_runtime_version(void) { return usc::RUNTIME_VERSION; }

const char* usc_last_error(const usc_runtime* runtime) {
    return runtime ? runtime->error.c_str() : global_error().c_str();
}

usc_status usc_open(const char* pack_path, const char* const* character_files,
                    const char* config_json, usc_runtime** out_runtime) {
    if (!pack_path || !character_files || !out_runtime) {
        global_error() = "usc_open needs a pack path, a character list and a "
                         "place to put the handle";
        return USC_ERR_ARGUMENT;
    }
    *out_runtime = nullptr;
    return guarded(nullptr, [&]() -> usc_status {
        std::vector<std::string> characters;
        for (const char* const* name = character_files; *name; ++name)
            characters.emplace_back(*name);

        usc::RuntimeConfig config;
        config.world_pack_path = pack_path;
        if (config_json && *config_json) {
            usc::Json declared = usc::Json::parse(config_json);
            if (declared.kind() != usc::Json::Kind::Object) {
                global_error() = "config_json must be a JSON object";
                return USC_ERR_ARGUMENT;
            }
            auto text = [&declared](const char* key, std::string& into) {
                const usc::Json* found = declared.find(key);
                if (found && found->truthy()) into = found->py_str();
            };
            auto flag = [&declared](const char* key, bool& into) {
                const usc::Json* found = declared.find(key);
                if (found) into = found->truthy();
            };
            text("player_id", config.player_id);
            text("canon_mode", config.canon_mode);
            text("projection_scope", config.projection_scope);
            flag("population_lod", config.population_lod);
            flag("load_initial_state", config.load_initial_state);
            for (const auto& layer : usc::optional_layers()) {
                const usc::Json* found = declared.find(layer.first);
                if (found) config.set_layer(layer.first, found->truthy());
            }
            const usc::Json* start = declared.find("player_start_location");
            if (start && start->truthy()) config.player_start_location = start->py_str();
            const usc::Json* timeout = declared.find("action_timeout_minutes");
            if (timeout && timeout->is_number())
                config.action_timeout_minutes = static_cast<int>(timeout->as_int());
        }

        auto fresh = std::unique_ptr<usc_runtime>(new usc_runtime());
        // Reading the pack has its OWN failure code. A caller that passed a
        // wrong path and one that passed a null pointer have different problems
        // and different fixes, and collapsing them into one status is how an
        // integrator ends up checking a string.
        try {
            fresh->world = usc::load_world_pack(pack_path, characters);
        } catch (const std::exception& failure) {
            global_error() = std::string("cannot read the world pack at ")
                           + pack_path + ": " + failure.what();
            return USC_ERR_PACK;
        }
        if (fresh->world.agents.empty() && fresh->world.places.fields().empty()) {
            global_error() = std::string("no world at ") + pack_path
                           + ": neither places nor characters were readable";
            return USC_ERR_PACK;
        }
        fresh->sdk.reset(new usc::UnscriptedRuntime(config, fresh->world));
        fresh->sdk->attach();
        *out_runtime = fresh.release();
        return USC_OK;
    });
}

void usc_close(usc_runtime* runtime) { delete runtime; }

long long usc_world_time(const usc_runtime* runtime) {
    return runtime ? runtime->world.world_time : 0;
}

usc_status usc_advance_time(usc_runtime* runtime, long long minutes) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        runtime->sdk->advance_time(minutes);
        return USC_OK;
    });
}

usc_status usc_submit_player_text(usc_runtime* runtime, const char* text,
                                  const char** out_json) {
    if (!runtime || !text) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        usc::TurnResult result = runtime->sdk->submit_player_text(text);
        usc::Json out = usc::Json::object();
        out["world_time"] = result.world_time;
        out["location"] = result.location_id;
        out["message"] = result.message;
        out["done"] = result.done;
        usc::Json parsed = usc::Json::object();
        parsed["intent"] = result.parsed.intent;
        parsed["confidence"] = result.parsed.confidence;
        parsed["target"] = result.parsed.target_id;
        parsed["topic"] = result.parsed.topic;
        parsed["location"] = result.parsed.location_id;
        parsed["minutes"] = result.parsed.minutes;
        parsed["metadata"] = result.parsed.metadata;
        out["parsed"] = parsed;
        usc::Json receipts = usc::Json::array();
        for (const usc::EventReceipt& r : result.receipts) {
            usc::Json row = usc::Json::object();
            row["event_id"] = r.event_id;
            row["type"] = r.event_type;
            row["world_time"] = r.world_time;
            usc::Json seen = usc::Json::array();
            for (const std::string& who : r.observed_by) seen.push(who);
            row["observed_by"] = seen;
            receipts.push(row);
        }
        out["receipts"] = receipts;
        if (result.npc_response) {
            usc::Json npc = usc::Json::object();
            npc["speaker"] = result.npc_response->speaker_id;
            npc["text"] = result.npc_response->text;
            npc["act"] = result.npc_response->act;
            npc["verdict"] = result.npc_response->verdict;
            npc["style"] = result.npc_response->style;
            usc::Json reasons = usc::Json::array();
            for (const usc::Json& one : result.npc_response->reasons) reasons.push(one);
            npc["reasons"] = reasons;
            out["npc"] = npc;
        } else {
            out["npc"] = usc::Json();
        }
        return hand_back(runtime, out, out_json);
    });
}

usc_status usc_respond(usc_runtime* runtime, const char* agent_id,
                       const char* topic, const char** out_json) {
    if (!runtime || !agent_id) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        if (!runtime->world.agents.find(agent_id)) {
            runtime->error = std::string("no such character: ") + agent_id;
            return USC_ERR_STATE;
        }
        usc::DialogueResponse said =
            runtime->sdk->respond(agent_id, topic ? topic : "");
        usc::Json out = usc::Json::object();
        out["speaker"] = said.speaker_id;
        out["text"] = said.text;
        out["act"] = said.act;
        out["verdict"] = said.verdict;
        out["utility"] = said.utility;
        out["style"] = said.style;
        usc::Json reasons = usc::Json::array();
        for (const usc::Json& one : said.reasons) reasons.push(one);
        out["reasons"] = reasons;
        return hand_back(runtime, out, out_json);
    });
}

usc_status usc_agent_state(usc_runtime* runtime, const char* agent_id,
                           const char** out_json) {
    if (!runtime || !agent_id) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        if (!runtime->world.agents.find(agent_id)) {
            runtime->error = std::string("no such character: ") + agent_id;
            return USC_ERR_STATE;
        }
        return hand_back(runtime, usc::state_view::agent_state(*runtime->sdk, agent_id),
                         out_json);
    });
}

usc_status usc_knowledge_state(usc_runtime* runtime, long long limit,
                               const char** out_json) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime,
                         usc::state_view::knowledge_state(*runtime->sdk,
                                                          limit > 0 ? limit : 40),
                         out_json);
    });
}

usc_status usc_world_state(usc_runtime* runtime, const char** out_json) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime, usc::state_view::world_state(*runtime->sdk), out_json);
    });
}

usc_status usc_scene_state(usc_runtime* runtime, const char** out_json) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime, usc::state_view::scene_state(*runtime->sdk), out_json);
    });
}

usc_status usc_face_packet(usc_runtime* runtime, const char* agent_id,
                           const char* gaze_target, const char** out_json) {
    if (!runtime || !agent_id) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        usc::Agent* agent = runtime->world.agents.find(agent_id);
        if (!agent) {
            runtime->error = std::string("no such character: ") + agent_id;
            return USC_ERR_STATE;
        }
        runtime->sdk->core.catch_up(*agent);   // LOD: a face needs a current mood
        usc::OrderedMap<double> tendencies =
            runtime->sdk->core.affect.action_tendencies(agent->affect);
        usc::Json target = gaze_target ? usc::Json(std::string(gaze_target))
                                       : usc::Json(runtime->sdk->config.player_id);
        return hand_back(runtime,
                         usc::metahuman::affect_to_face(agent->affect, &tendencies,
                                                        target),
                         out_json);
    });
}

usc_status usc_export_state(usc_runtime* runtime, const char** out_json) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime, runtime->sdk->export_state(), out_json);
    });
}

usc_status usc_inspect_state(usc_runtime* runtime, const char* blob_json,
                             const char** out_json) {
    if (!runtime || !blob_json) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime,
                         runtime->sdk->inspect_state(usc::Json::parse(blob_json)),
                         out_json);
    });
}

usc_status usc_import_state(usc_runtime* runtime, const char* blob_json,
                            const char** out_json) {
    if (!runtime || !blob_json) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        usc::ImportResult back =
            runtime->sdk->import_state(usc::Json::parse(blob_json));
        usc::Json out = usc::Json::object();
        out["report"] = back.report;
        out["reasons"] = reasons_json(back.reasons);
        return hand_back(runtime, out, out_json);
    });
}

usc_status usc_pending_actions(usc_runtime* runtime, const char** out_json) {
    if (!runtime) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        usc::Json out = usc::Json::array();
        for (const usc::ActionIntent& intent : runtime->sdk->core.actions_out.pending())
            out.push(intent.as_json());
        return hand_back(runtime, out, out_json);
    });
}

usc_status usc_resolve_action(usc_runtime* runtime, const char* intent_id,
                              const char* status, const char* detail,
                              const char** out_json) {
    if (!runtime || !intent_id || !status) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        return hand_back(runtime,
                         runtime->sdk->core.resolve_action(intent_id, status,
                                                           detail ? detail : ""),
                         out_json);
    });
}

usc_status usc_discredit(usc_runtime* runtime, const char* source_id, double factor,
                         const char* reason, const char** out_json) {
    if (!runtime || !source_id) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        std::vector<usc::Reason> reasons = runtime->sdk->discredit(
            source_id, factor, reason ? reason : "exposed");
        return hand_back(runtime, reasons_json(reasons), out_json);
    });
}

usc_status usc_inspect_agent(usc_runtime* runtime, const char* agent_id,
                             const char** out_text) {
    if (!runtime || !agent_id) return USC_ERR_ARGUMENT;
    return guarded(runtime, [&]() -> usc_status {
        if (!runtime->world.agents.find(agent_id)) {
            runtime->error = std::string("no such character: ") + agent_id;
            return USC_ERR_STATE;
        }
        return hand_back(runtime, runtime->sdk->inspect_agent(agent_id), out_text);
    });
}

}  // extern "C"
