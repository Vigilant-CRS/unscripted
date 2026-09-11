// The Unreal binding's engine-free half, exercised against the real library.
//
// Unreal is not installed on this machine, so this is what stands in for it --
// and it stands in for most of it. Everything the module does with the runtime
// is here; what is NOT covered is the FString conversions and the reflection
// macros in `UnscriptedSubsystem.cpp`, which is a page of mechanical code and
// is marked as unverified where it lives.
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "UscNative.h"

using usc_unreal::Native;
using usc_unreal::Outcome;

static int failures = 0;

static void check(bool ok, const char* what) {
    if (!ok) { std::printf("  FAIL %s\n", what); ++failures; }
}

int main(int argc, char** argv) {
    const std::string root = argc > 1 ? argv[1] : ".";
    const std::string pack = root + "/worldpacks/cyberpunk-block";
    const std::vector<std::string> characters = {
        "barkeep_12.json", "corpo_okada.json", "dima_broke.json",
        "npc_red_jacket.json", "officer_kane.json", "pavel.json",
        "son_ilya.json", "son_marko.json"};

    std::printf("abi %d, runtime %s\n", Native::abi_version(),
                Native::runtime_version().c_str());
    check(Native::abi_version() == Native::expected_abi_version,
          "the library and this binding speak the same ABI");

    {
        Native missing;
        check(missing.open(root + "/nope", characters, "") == Outcome::BadPack,
              "a missing pack is refused by code");
        check(!missing.error().empty(), "and says why");
        check(!missing.is_open(), "and leaves nothing open");
    }

    Native world;
    check(world.open(pack, characters,
                     "{\"player_id\": \"agent:player_1\", \"pursuit\": true,"
                     " \"standing\": true}") == Outcome::Ok,
          "the pack opens");
    check(world.is_open(), "and the handle is live");

    check(world.submit_player_text("look") == Outcome::Ok, "look");
    check(world.answer().find("\"observe\"") != std::string::npos,
          "parses as observe");
    check(world.submit_player_text("ask Vee about Milan") == Outcome::Ok, "ask");
    check(world.answer().find("\"npc\"") != std::string::npos, "and is answered");

    long long before = world.world_time();
    check(world.advance_time(120) == Outcome::Ok, "time advances");
    check(world.world_time() == before + 120, "by what it was given");
    check(world.advance_time(-1) == Outcome::BadArgument, "and only forwards");
    check(world.error().find("monotonic") != std::string::npos,
          "with a reason a person can act on");

    check(world.agent_state("agent:npc_red_jacket") == Outcome::Ok, "a mind");
    check(world.answer().find("\"beliefs\"") != std::string::npos, "with beliefs");
    check(world.agent_state("agent:nobody") == Outcome::BadState,
          "an unknown character is a state error");
    check(world.answer().empty(), "and clears the last answer rather than reusing it");

    check(world.face_packet("agent:npc_red_jacket", "") == Outcome::Ok, "a face");
    check(world.answer().find("blendshapes") != std::string::npos, "with blendshapes");
    check(world.knowledge_state(40) == Outcome::Ok, "who knows what");
    check(world.world_state() == Outcome::Ok, "the world");
    check(world.scene_state() == Outcome::Ok, "the scene");
    check(world.inspect_agent("agent:npc_red_jacket") == Outcome::Ok, "a dump");
    check(world.answer().find("beliefs of") != std::string::npos,
          "a person can read");

    // The answer belongs to THIS object, not to the runtime, so it survives the
    // next call. That is the difference between this wrapper and a raw pointer.
    check(world.scene_state() == Outcome::Ok, "a scene");
    std::string held = world.answer();
    check(world.world_state() == Outcome::Ok, "then a world");
    check(held != world.answer() && held.find("exits") != std::string::npos,
          "and the first answer is still intact");

    check(world.export_state() == Outcome::Ok, "the world exports");
    std::string saved = world.answer();
    check(world.inspect_state(saved) == Outcome::Ok, "and inspects");
    check(world.answer().find("\"usable\":true") != std::string::npos, "as usable");
    check(world.advance_time(600) == Outcome::Ok, "the world moves on");
    long long moved = world.world_time();
    check(world.import_state(saved) == Outcome::Ok, "and the save goes back");
    check(world.world_time() < moved, "putting the clock back");
    check(world.import_state("{\"format\": \"someone-elses-game\"}") == Outcome::BadSave,
          "a foreign blob is refused with a save-specific code");

    check(world.pending_actions() == Outcome::Ok, "pending actions");
    check(world.resolve_action("intent:nobody", "SUCCEEDED", "") == Outcome::BadState,
          "an unknown intent is a state error");
    check(world.resolve_action("intent:nobody", "EXPLODED", "") == Outcome::BadArgument,
          "a status no engine may report is a bad argument");
    check(world.discredit("agent:npc_red_jacket", 0.25, "exposed") == Outcome::Ok,
          "a source can be discredited");

    world.close();
    check(!world.is_open(), "closing twice is safe");
    world.close();

    std::printf(failures ? "%d check(s) failed\n"
                         : "every Unreal-native check passed\n", failures);
    return failures ? 1 : 0;
}
