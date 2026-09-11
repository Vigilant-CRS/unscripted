/*  A C program, compiled by a C compiler, that drives the runtime through the
 *  ABI and nothing else.
 *
 *  This is the whole point of the exercise: if this file builds and runs, an
 *  Unreal module, a Unity P/Invoke signature and a Godot GDExtension can do the
 *  same, because none of them has anything this file does not.
 *
 *  It is deliberately C99 and not C++. A header that only works when the caller
 *  happens to be a C++ compiler is not a C ABI, and the mistake does not show
 *  up until somebody's plugin will not link.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "usc.h"

static int failures = 0;

static void check(int ok, const char* what) {
    if (!ok) { printf("  FAIL %s\n", what); ++failures; }
}

int main(int argc, char** argv) {
    const char* pack = argc > 1 ? argv[1] : "worldpacks/cyberpunk-block";
    const char* characters[] = {
        "barkeep_12.json", "corpo_okada.json", "dima_broke.json",
        "npc_red_jacket.json", "officer_kane.json", "pavel.json",
        "son_ilya.json", "son_marko.json", NULL};

    printf("abi version %d, runtime %s\n", usc_abi_version(), usc_runtime_version());
    check(usc_abi_version() == USC_ABI_VERSION, "the header and the library agree");

    /* Refusals first: a C ABI that crashes on a null is not shippable. */
    check(usc_open(NULL, characters, NULL, NULL) == USC_ERR_ARGUMENT,
          "a null pack path is refused, not dereferenced");
    usc_close(NULL);
    check(usc_world_time(NULL) == 0, "a null handle answers rather than crashes");
    check(strlen(usc_last_error(NULL)) > 0, "and the reason is readable");

    usc_runtime* rt = NULL;
    usc_status status = usc_open("does/not/exist", characters, NULL, &rt);
    check(status == USC_ERR_PACK, "a missing pack is an error, not a crash");
    check(rt == NULL, "and hands back no handle");

    status = usc_open(pack, characters,
                      "{\"player_id\": \"agent:player_1\", \"pursuit\": true,"
                      " \"standing\": true}", &rt);
    if (status != USC_OK) {
        printf("  FAIL could not open %s: %s\n", pack, usc_last_error(NULL));
        return 1;
    }

    const char* json = NULL;
    check(usc_submit_player_text(rt, "look", &json) == USC_OK, "look");
    check(json && strstr(json, "\"intent\"") != NULL, "the turn comes back as JSON");

    check(usc_submit_player_text(rt, "ask Vee about Milan", &json) == USC_OK, "ask");
    check(json && strstr(json, "\"npc\"") != NULL, "and carries the answer");

    check(usc_advance_time(rt, 120) == USC_OK, "time advances");
    check(usc_advance_time(rt, -1) == USC_ERR_ARGUMENT, "and only forwards");
    check(strstr(usc_last_error(rt), "monotonic") != NULL,
          "with a reason a person can act on");

    check(usc_agent_state(rt, "agent:npc_red_jacket", &json) == USC_OK, "a mind");
    check(json && strstr(json, "\"beliefs\"") != NULL, "with its beliefs");
    check(usc_agent_state(rt, "agent:nobody", &json) == USC_ERR_STATE,
          "an unknown character is refused");

    check(usc_knowledge_state(rt, 40, &json) == USC_OK, "who knows what");
    check(usc_world_state(rt, &json) == USC_OK, "the world");
    check(usc_scene_state(rt, &json) == USC_OK, "the scene");
    check(usc_face_packet(rt, "agent:npc_red_jacket", NULL, &json) == USC_OK, "a face");
    check(json && strstr(json, "blendshapes") != NULL, "with blendshapes on it");
    check(usc_inspect_agent(rt, "agent:npc_red_jacket", &json) == USC_OK, "a dump");
    check(json && strstr(json, "beliefs of") != NULL, "a person can read");

    /* Save, move on, and put it back. */
    check(usc_export_state(rt, &json) == USC_OK, "the world exports");
    /* COPY IT. The buffer belongs to the runtime and the next call overwrites
     * it -- which is the rule this probe exists to demonstrate as much as to
     * obey. `strdup` is POSIX and not C99, so the copy is spelled out. */
    size_t saved_length = strlen(json);
    char* saved = (char*)malloc(saved_length + 1);
    memcpy(saved, json, saved_length + 1);
    check(usc_inspect_state(rt, saved, &json) == USC_OK, "and inspects");
    check(json && strstr(json, "\"usable\":true") != NULL, "as usable");
    check(usc_advance_time(rt, 600) == USC_OK, "the world moves on");
    long long moved = usc_world_time(rt);
    check(usc_import_state(rt, saved, &json) == USC_OK, "and the save goes back");
    check(usc_world_time(rt) < moved, "putting the clock back where it was");
    check(usc_inspect_state(rt, "{\"format\": \"someone-elses-game\"}", &json) == USC_OK,
          "a foreign blob is reported");
    check(json && strstr(json, "not_a_state_blob") != NULL, "by name");
    check(usc_import_state(rt, "{\"format\": \"someone-elses-game\"}", &json)
              == USC_ERR_SAVE,
          "and refused on import");
    free(saved);

    check(usc_pending_actions(rt, &json) == USC_OK, "pending actions");
    check(usc_resolve_action(rt, "intent:nobody", "SUCCEEDED", NULL, &json)
              == USC_ERR_STATE,
          "an unknown intent is a state error, not a bad argument");
    check(usc_resolve_action(rt, "intent:nobody", "EXPLODED", NULL, &json)
              == USC_ERR_ARGUMENT,
          "and a status no engine may report is a bad argument");

    check(usc_discredit(rt, "agent:npc_red_jacket", 0.25, "exposed", &json) == USC_OK,
          "a source can be discredited");

    usc_close(rt);
    printf(failures ? "%d check(s) failed\n" : "every ABI check passed\n", failures);
    return failures ? 1 : 0;
}
