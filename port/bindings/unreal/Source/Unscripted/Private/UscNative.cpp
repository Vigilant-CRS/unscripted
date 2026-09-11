#include "UscNative.h"

#include "usc.h"

namespace usc_unreal {
namespace {

Outcome translate(usc_status status) {
    switch (status) {
        case USC_OK:           return Outcome::Ok;
        case USC_ERR_ARGUMENT: return Outcome::BadArgument;
        case USC_ERR_PACK:     return Outcome::BadPack;
        case USC_ERR_STATE:    return Outcome::BadState;
        case USC_ERR_SAVE:     return Outcome::BadSave;
        default:               return Outcome::Refused;
    }
}

}  // namespace

Native::~Native() { close(); }

int Native::abi_version() { return usc_abi_version(); }

std::string Native::runtime_version() { return usc_runtime_version(); }

Outcome Native::record(int status, const char* json) {
    usc_status code = static_cast<usc_status>(status);
    if (code != USC_OK) {
        // COPIED, because the next call rewrites the runtime's buffer -- and an
        // error message that has been overwritten by the call made to recover
        // from it is worse than none.
        error_ = usc_last_error(runtime_);
        answer_.clear();
        return translate(code);
    }
    error_.clear();
    answer_ = json ? json : "";
    return Outcome::Ok;
}

Outcome Native::open(const std::string& pack_path,
                     const std::vector<std::string>& character_files,
                     const std::string& config_json) {
    close();
    std::vector<const char*> pointers;
    pointers.reserve(character_files.size() + 1);
    for (const std::string& one : character_files) pointers.push_back(one.c_str());
    pointers.push_back(nullptr);

    usc_status status = usc_open(pack_path.c_str(), pointers.data(),
                                 config_json.empty() ? nullptr : config_json.c_str(),
                                 &runtime_);
    if (status != USC_OK) {
        // The handle does not exist yet, so the reason is on the global slot.
        error_ = usc_last_error(nullptr);
        runtime_ = nullptr;
        return translate(status);
    }
    error_.clear();
    return Outcome::Ok;
}

void Native::close() {
    usc_close(runtime_);
    runtime_ = nullptr;
}

long long Native::world_time() const { return usc_world_time(runtime_); }

Outcome Native::advance_time(long long minutes) {
    usc_status status = usc_advance_time(runtime_, minutes);
    if (status != USC_OK) {
        error_ = usc_last_error(runtime_);
        return translate(status);
    }
    error_.clear();
    return Outcome::Ok;
}

// THE STATUS IS TAKEN FIRST, ON ITS OWN LINE. `record(fn(...), json)` compiles
// and is wrong: C++ does not order the evaluation of a call's arguments, so the
// compiler is free to read `json` before `fn` has written it -- and gcc at -O2
// does exactly that. It reads as "the answer is empty" and nothing else, which
// is how the test found it.
#define USC_UNREAL_CALL0(name, fn)                                             \
    Outcome Native::name() {                                                   \
        const char* json = nullptr;                                            \
        const usc_status status = fn(runtime_, &json);                         \
        return record(status, json);                                           \
    }

#define USC_UNREAL_CALL1(name, fn)                                             \
    Outcome Native::name(const std::string& argument) {                        \
        const char* json = nullptr;                                            \
        const usc_status status = fn(runtime_, argument.c_str(), &json);       \
        return record(status, json);                                           \
    }

USC_UNREAL_CALL1(submit_player_text, usc_submit_player_text)
USC_UNREAL_CALL1(agent_state, usc_agent_state)
USC_UNREAL_CALL1(inspect_agent, usc_inspect_agent)
USC_UNREAL_CALL1(inspect_state, usc_inspect_state)
USC_UNREAL_CALL1(import_state, usc_import_state)
USC_UNREAL_CALL0(world_state, usc_world_state)
USC_UNREAL_CALL0(scene_state, usc_scene_state)
USC_UNREAL_CALL0(export_state, usc_export_state)
USC_UNREAL_CALL0(pending_actions, usc_pending_actions)

#undef USC_UNREAL_CALL0
#undef USC_UNREAL_CALL1

Outcome Native::respond(const std::string& agent_id, const std::string& topic) {
    const char* json = nullptr;
    const usc_status status = usc_respond(runtime_, agent_id.c_str(),
                                          topic.empty() ? nullptr : topic.c_str(),
                                          &json);
    return record(status, json);
}

Outcome Native::knowledge_state(long long limit) {
    const char* json = nullptr;
    const usc_status status = usc_knowledge_state(runtime_, limit, &json);
    return record(status, json);
}

Outcome Native::face_packet(const std::string& agent_id,
                            const std::string& gaze_target) {
    const char* json = nullptr;
    const usc_status status = usc_face_packet(
        runtime_, agent_id.c_str(),
        gaze_target.empty() ? nullptr : gaze_target.c_str(), &json);
    return record(status, json);
}

Outcome Native::resolve_action(const std::string& intent_id,
                               const std::string& status,
                               const std::string& detail) {
    const char* json = nullptr;
    const usc_status outcome = usc_resolve_action(
        runtime_, intent_id.c_str(), status.c_str(),
        detail.empty() ? nullptr : detail.c_str(), &json);
    return record(outcome, json);
}

Outcome Native::discredit(const std::string& source_id, double factor,
                          const std::string& reason) {
    const char* json = nullptr;
    const usc_status status = usc_discredit(
        runtime_, source_id.c_str(), factor,
        reason.empty() ? nullptr : reason.c_str(), &json);
    return record(status, json);
}

}  // namespace usc_unreal
