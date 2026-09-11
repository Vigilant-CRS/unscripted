/*  usc.h -- the C ABI for the Unscripted runtime.
 *
 *  ONE function-call convention, three engines. Unreal links this natively,
 *  Unity reaches it through P/Invoke, Godot loads it as a GDExtension. Nothing
 *  above this line knows C++ exists, and nothing below it knows an engine does.
 *
 *  Rules this header keeps, because a C ABI that breaks any of them is a C ABI
 *  that cannot be shipped in a plugin:
 *
 *    - No C++ types cross the boundary. Everything is an opaque handle, an int,
 *      a double, or a null-terminated UTF-8 string.
 *    - NOTHING THROWS. Every call returns a status code; a call that fails
 *      leaves the runtime untouched and the message readable with
 *      `usc_last_error`. An exception crossing a C boundary is undefined
 *      behaviour, and on a console it is a crash report.
 *    - Every string this library returns is owned by the runtime and stays
 *      valid until the NEXT call on the same handle. Copy it or use it; do not
 *      free it. That rule is what lets a caller marshal a string without an
 *      allocator contract, which is the part of a C ABI that usually leaks.
 *    - Structured answers come back as JSON. A binding that wants typed structs
 *      builds them on its own side, in its own language, where the marshalling
 *      cost is paid once per engine rather than once per field.
 *
 *  Thread safety: a handle is NOT thread-safe. Use one handle per thread, or
 *  serialise calls to it. The simulation is deterministic, so two threads
 *  sharing a handle would not merely race -- they would produce a world neither
 *  of them could reproduce.
 */
#ifndef USC_H
#define USC_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#  if defined(USC_BUILD_SHARED)
#    define USC_API __declspec(dllexport)
#  elif defined(USC_USE_SHARED)
#    define USC_API __declspec(dllimport)
#  else
#    define USC_API
#  endif
#else
#  define USC_API __attribute__((visibility("default")))
#endif

/** ABI version. Bumped when a signature changes, never for behaviour. */
#define USC_ABI_VERSION 1

typedef enum usc_status {
    USC_OK = 0,
    /** The handle was null, or a required argument was. */
    USC_ERR_ARGUMENT = 1,
    /** The world pack could not be read, or does not describe a usable world. */
    USC_ERR_PACK = 2,
    /** The call is not valid in this state -- no player, no such character. */
    USC_ERR_STATE = 3,
    /** A save blob this build cannot use. `usc_last_error` says which reason. */
    USC_ERR_SAVE = 4,
    /** Anything the runtime refused, with the reason in `usc_last_error`. */
    USC_ERR_RUNTIME = 5
} usc_status;

/** An opaque runtime. One world, one player, one simulation. */
typedef struct usc_runtime usc_runtime;

/** The ABI version this library was built with. */
USC_API int usc_abi_version(void);

/** The runtime version string, e.g. "1.18.0". Owned by the library. */
USC_API const char* usc_runtime_version(void);

/**
 * The last error on this handle, or "" when the last call succeeded.
 *
 * Pass NULL to read an error from a call that could not produce a handle --
 * `usc_open` in particular.
 */
USC_API const char* usc_last_error(const usc_runtime* runtime);

/**
 * Open a world pack.
 *
 * `character_files` is a NULL-terminated array of basenames inside the pack's
 * `characters/` directory, and it is REQUIRED: listing a directory is the one
 * thing a console does differently from a desktop, and the host is the right
 * place to answer it.
 *
 * `config_json` may be NULL. When given it is a JSON object with any of the
 * RuntimeConfig fields -- `player_id`, `population_lod`, the nine optional
 * layers, `canon_mode`, `player_start_location`.
 */
USC_API usc_status usc_open(const char* pack_path,
                            const char* const* character_files,
                            const char* config_json,
                            usc_runtime** out_runtime);

/** Close a runtime and release everything it owns. Safe on NULL. */
USC_API void usc_close(usc_runtime* runtime);

/** The world clock, in minutes. */
USC_API long long usc_world_time(const usc_runtime* runtime);

/** Advance the world. Time is monotonic; a negative delta is refused. */
USC_API usc_status usc_advance_time(usc_runtime* runtime, long long minutes);

/**
 * One turn of player text.
 *
 * The answer is a JSON object: the parsed command, the message for the player,
 * the receipts, and the NPC's reply with its reason trace. Valid until the next
 * call on this handle.
 */
USC_API usc_status usc_submit_player_text(usc_runtime* runtime, const char* text,
                                          const char** out_json);

/** What a character says when addressed, as JSON. `topic` may be NULL. */
USC_API usc_status usc_respond(usc_runtime* runtime, const char* agent_id,
                               const char* topic, const char** out_json);

/** One character's mind, as JSON. See `state_view.hpp`. */
USC_API usc_status usc_agent_state(usc_runtime* runtime, const char* agent_id,
                                   const char** out_json);

/** Who knows what, how far from the source, and how it got there. */
USC_API usc_status usc_knowledge_state(usc_runtime* runtime, long long limit,
                                       const char** out_json);

/** Time, factions, heat, clocks, media exposure, capabilities. */
USC_API usc_status usc_world_state(usc_runtime* runtime, const char** out_json);

/** The player's current location: place, NPCs, exits. */
USC_API usc_status usc_scene_state(usc_runtime* runtime, const char** out_json);

/**
 * A MetaHuman-ready face for one character: ARKit blendshapes, gaze, prosody,
 * posture. `gaze_target` may be NULL.
 */
USC_API usc_status usc_face_packet(usc_runtime* runtime, const char* agent_id,
                                   const char* gaze_target, const char** out_json);

/** The whole mutable world as one blob a game puts in its own save file. */
USC_API usc_status usc_export_state(usc_runtime* runtime, const char** out_json);

/**
 * What would happen if this blob were imported, WITHOUT importing it.
 *
 * The call a load screen makes. Always returns USC_OK for a readable blob; the
 * JSON says whether it is usable and why not.
 */
USC_API usc_status usc_inspect_state(usc_runtime* runtime, const char* blob_json,
                                     const char** out_json);

/** Put a blob back. Refuses a blob `usc_inspect_state` calls unusable. */
USC_API usc_status usc_import_state(usc_runtime* runtime, const char* blob_json,
                                    const char** out_json);

/**
 * What the engine still owes an answer for, as a JSON array of intents.
 *
 * Empty unless the action bridge is on. See `actionbridge.hpp`: the runtime
 * states an intent and does not move anybody until the engine reports back.
 */
USC_API usc_status usc_pending_actions(usc_runtime* runtime, const char** out_json);

/**
 * Report what the engine did with an intent.
 *
 * `status` is one of SUCCEEDED, FAILED, INTERRUPTED, UNREACHABLE. `detail` may
 * be NULL.
 */
USC_API usc_status usc_resolve_action(usc_runtime* runtime, const char* intent_id,
                                      const char* status, const char* detail,
                                      const char** out_json);

/** Expose a source: recompute everything they convinced anyone of. */
USC_API usc_status usc_discredit(usc_runtime* runtime, const char* source_id,
                                 double factor, const char* reason,
                                 const char** out_json);

/** A human-readable dump of one character, for a debug overlay. */
USC_API usc_status usc_inspect_agent(usc_runtime* runtime, const char* agent_id,
                                     const char** out_text);

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif /* USC_H */
