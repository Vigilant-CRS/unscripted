// The Unreal binding's engine-free half.
//
// Everything that talks to the C ABI lives here, in plain C++ with no Unreal
// types in sight. The UObject layer above it does nothing but convert `FString`
// to `const char*` and back.
//
// That split is the whole point. Unreal is not installed on the machine this
// port was written on, so a module written as one piece would be entirely
// unverified. Written this way, the unverified part is the FString conversions
// and the reflection macros -- a page of mechanical code -- and everything below
// it is compiled and exercised by `usc_native_test.cpp` on every run of the
// suite, exactly like the Unity and Godot bindings.
#pragma once

#include <string>
#include <vector>

struct usc_runtime;

namespace usc_unreal {

/// What a call did, in terms an engine cares about.
enum class Outcome {
    Ok,
    BadArgument,
    BadPack,
    BadState,
    BadSave,
    Refused,
};

/// One world, one player, one simulation.
///
/// Non-copyable and non-movable: it owns a handle the C side allocated, and a
/// second owner would close it twice. Unreal's garbage collector will hold
/// exactly one of these per subsystem.
class Native {
public:
    Native() = default;
    ~Native();
    Native(const Native&) = delete;
    Native& operator=(const Native&) = delete;

    static int abi_version();
    static std::string runtime_version();
    /// The ABI this binding was written against.
    static constexpr int expected_abi_version = 1;

    /// Open a world pack. `character_files` are basenames inside its
    /// `characters/` directory -- required, because on a cooked build they live
    /// in a pak file and only the game knows what is in it.
    Outcome open(const std::string& pack_path,
                 const std::vector<std::string>& character_files,
                 const std::string& config_json);
    void close();
    bool is_open() const { return runtime_ != nullptr; }

    long long world_time() const;
    Outcome advance_time(long long minutes);

    /// Each of these leaves its answer in `answer()`, copied out of the
    /// runtime's own buffer before anything else can overwrite it.
    Outcome submit_player_text(const std::string& text);
    Outcome respond(const std::string& agent_id, const std::string& topic);
    Outcome agent_state(const std::string& agent_id);
    Outcome inspect_agent(const std::string& agent_id);
    Outcome knowledge_state(long long limit);
    Outcome world_state();
    Outcome scene_state();
    Outcome face_packet(const std::string& agent_id, const std::string& gaze_target);
    Outcome export_state();
    Outcome inspect_state(const std::string& blob_json);
    Outcome import_state(const std::string& blob_json);
    Outcome pending_actions();
    Outcome resolve_action(const std::string& intent_id, const std::string& status,
                           const std::string& detail);
    Outcome discredit(const std::string& source_id, double factor,
                      const std::string& reason);

    /// The last answer. Owned by this object, not by the runtime.
    const std::string& answer() const { return answer_; }
    /// Why the last call failed, or "".
    const std::string& error() const { return error_; }

private:
    Outcome record(int status, const char* json);

    usc_runtime* runtime_ = nullptr;
    std::string answer_;
    std::string error_;
};

}  // namespace usc_unreal
