# Unscripted — Unity package

Two components. Between them they are the whole integration.

| | |
| --- | --- |
| `UnscriptedHost` | launches the runtime as a child process, takes a free port, reads back where it landed, and shuts it down with the game — including when the game crashes |
| `UnscriptedClient` | every endpoint a game needs: a turn, an event, an advance, pending actions, promises, and save/load into your own save file |

```csharp
var host = gameObject.AddComponent<UnscriptedHost>();
var unscripted   = gameObject.AddComponent<UnscriptedClient>();

host.ReadyAt += (url, token) => {
    unscripted.ConnectTo(url, token);
    unscripted.Say("ask Yara about the shooting");
};
host.Failed  += Debug.LogError;
unscripted.Spoke     += json => Debug.Log(json);

host.StartRuntime(Path.Combine(Application.streamingAssetsPath, "my-town"),
                  new[] { "pursuit", "promises" });
```

## Installing

Package Manager → **Add package from disk** → this folder's `package.json`. Or
copy the folder into `Packages/` in your project.

## What the runtime has to be

Either an installed `unscripted` on PATH, or a bundle. `unscripted bundle --out
unscripted.pyz` writes one ~340 kB file that any Python 3.10+ runs; put it in
`StreamingAssets` and set `bundlePath` on the host. It does **not** remove the
need for a Python interpreter on the player's machine — see
`docs/CONNECTING.md`.

## Why responses are strings

`JsonUtility` cannot represent the runtime's nested, heterogeneous payloads, and
shipping a bespoke parser in this package would create a second definition of
the contract that could drift from the first. So responses arrive as raw JSON
and you parse them with whatever your project already uses. The shapes are in
`integrations/unreal/UnscriptedBridge/contract.v2.json`, which the Python test
suite asserts against a live service.

## Status — what is verified, and what is only reasoned

**Compiles against Unity 6000.0.82f1, warnings as errors.** Verified in this
repository, not asserted:

```bash
python3 tools/unity_check.py
#   2 source file(s), 418 lines
#   6000.0.82f1: compiles clean, warnings as errors
```

It needs **no Unity licence**. Batch mode refuses to start without one, so this
compiles the package directly against the editor's own `UnityEngine` assemblies
using the Roslyn compiler Unity ships — invoking a compiler is not using an
editor. `tests/test_scenarios.py` runs the same check wherever an editor is
installed, and says loudly that it skipped where none is.

### The minimum version is reasoned, not verified

`package.json` declares `"unity": "2021.3"`, and **that has not been compiled
against here** — only 6000.0.82f1 has. The figure comes from reading what the
code uses:

| API | available since |
| --- | --- |
| `UnityWebRequest.Result` / `request.result` | 2020.2 |
| value tuples in method signatures (C# 7) | 2018.3 |
| everything else (`JsonUtility`, `UploadHandlerRaw`, `persistentDataPath`) | far older |

So the true floor is about **2020.2**, and 2021.3 is the first LTS above it —
which makes the declared minimum conservative rather than wrong. It is stated
this way because the Unreal plugin shipped a version claim nobody had checked
and it turned out to make the plugin refuse to load. A claim that has not been
run is worth exactly what it says on the tin.

To verify it properly, install 2021.3 through Unity Hub and run
`python3 tools/unity_check.py` — it compiles against every editor it finds.

### Run

```bash
python3 tools/unity_smoke.py
#   ... service on http://127.0.0.1:34119
#   3 tests passed inside Unity, against a live service
```

It starts a real Unscripted service on a free port, hands the address to the
editor in `UNSCRIPTED_URL` and `UNSCRIPTED_TOKEN`, and runs the tests in `Tests/Runtime/`
against it. **This one needs a Unity licence** — sign in once in Unity Hub,
Personal is free. `unity_check.py` avoids that by invoking the Roslyn compiler
the editor ships, because invoking a compiler is not using an editor; running
tests *is*.

What the three ask, and why those three: does a turn come back **carrying
`honesty`** — the field the Unreal plugin silently dropped, so a game could not
tell whether a character had lied; is a refusal reported as a failure with its
reason rather than swallowed; and can the world be exported and inspected before
a load, which is the save path a shipping game depends on.

Three things had to be right before any of them ran, and none of them announced
itself:

- the package must be listed in `"testables"` in the project manifest, or Unity
  finds the tests, compiles them, and runs none — reporting **0 passed, 0
  failed**, with no error anywhere;
- the test assembly must not reference `UnityEngine.TestRunner` both explicitly
  and through the pre-2019 `optionalUnityReferences`, or the assembly is
  rejected for duplicate references;
- and the runner must count `<test-case>` nodes rather than every
  `result="Passed"` in the NUnit XML, which also marks the suites — that
  reported **ten** where three had run.

Each of those produces a green-looking result that is not one, which is the same
failure the Unreal plugin's version pin produced: no error, just silence.

### Still not claimed

Nothing has been *played*. The package compiles, loads, talks to a real runtime
and parses what comes back. Whether it feels right in a game is the next thing
nobody has checked.
