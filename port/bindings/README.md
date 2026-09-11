# The three bindings

> **Not the same thing as `integrations/`.** That directory holds HTTP clients
> for the runtime running as a SIDECAR process — the right answer on PC, and
> forbidden on a console, which may not ship an interpreter. These bindings are
> the other route: the C++ core compiled into the game, reached through one C
> header. The behaviour is identical, because both are held to the same
> conformance fixtures.


One C++17 core, one C header, three engines. Each binding is marshalling and
nothing else: no simulation lives here, because a behaviour that exists only
behind a binding is a behaviour the probes do not compare.

| | What it is | Tested how |
| --- | --- | --- |
| **Unity** | `unity/Unscripted.cs` — P/Invoke plus a small C# wrapper. Drop it and the native library into `Assets/Plugins/Unscripted/`. | A .NET console program compiled by a real C# compiler and run against the real library. Runs in the suite. |
| **Godot** | `godot/usc_gdextension.cpp` — a GDExtension against the raw C interface, no `godot-cpp`. | A headless Godot loads it and drives it from GDScript. Runs in the suite. |
| **Unreal** | `unreal/` — a plugin, split into an engine-free half and a UObject half. | The engine-free half runs in the suite. The whole plugin **compiles and links against a real Unreal 5.8.2**, reflection macros included: `python3 tools/unreal_check.py --plugin native`. |

All three are exercised by `tests/test_scenarios.py` and skip, rather than fail,
where the toolchain is absent. `UNSCRIPTED_DOTNET` and `UNSCRIPTED_GODOT` point at one that is
installed somewhere unusual.

## What each one is for

The instinct is a port per engine. It is not: **a console forbids an
interpreter, not a language.** All five current consoles compile C++ and all
three engines can call a C function, so there is one implementation, verified
once, and three pieces of marshalling.

Every structured answer crosses as JSON. A binding that wanted typed structs
would be a second schema to keep in step with the one the runtime already
documents, and it would drift the first time a field was added.

## Unity

```csharp
using var world = new Unscripted.World(packPath, characterFiles, configJson);
var turn = JsonDocument.Parse(world.SubmitPlayerText("ask Vee about Milan"));
```

Two mistakes in a P/Invoke layer crash rather than misbehave, and neither shows
up until runtime. Both are avoided deliberately and both are checked:

- **A `string` return value.** `[return: MarshalAs(UnmanagedType.LPUTF8Str)]`
  makes .NET free the pointer with the COM allocator when it comes back. The
  strings this library returns belong to the library; freeing one corrupts its
  heap. Every return is an `IntPtr` copied with `Marshal.PtrToStringUTF8`.
- **A `string[]` argument.** The default marshaller does not add the null
  terminator the C side reads, and no attribute asks it to. The array is built
  by hand.

For IL2CPP on a platform that forbids dynamic loading, define
`USC_STATIC` and link the core statically; the `DllImport` name
becomes `__Internal`.

## Godot

```gdscript
var world = Unscripted.new()
world.open(pack_path, "\n".join(character_files), '{"pursuit": true}')
print(JSON.parse_string(world.submit_player_text("look")))
```

Written against the raw GDExtension C interface rather than `godot-cpp`. That is
a deliberate cost: `godot-cpp` is a large build of its own, rebuilt per Godot
version, and vendoring it into a runtime whose whole claim is "no dependencies"
would be the first exception. The header comes from Godot itself:

    godot --headless --dump-gdextension-interface

The test found the one mistake that matters in a GDExtension on its first run:
`create_instance_func` must return a **Godot object**, not the extension's own
data. Returning the wrong thing segfaults inside the engine with nothing of
yours in the backtrace.

## Unreal

```
python3 tools/unreal_check.py --plugin native
```

That builds a throwaway project containing only this plugin, with
UnrealBuildTool, against a real engine. It compiles every `.cpp`, runs
UnrealHeaderTool over the `UCLASS`/`UFUNCTION` declarations, and links — which
is a stronger claim than "it compiles", because the reflection macros are the
part hand-written Unreal C++ most often gets wrong. Verified against **Unreal
5.8.2**.

What that does NOT claim: nothing has been RUN. It compiles and links; whether
it behaves in a running game is the next thing nobody has checked.

The module is split, and the split is still the point:

- `Source/Unscripted/Public/UscNative.h` and its `.cpp` — everything that
  touches the runtime, in plain C++ with no Unreal types. **Compiled and
  exercised on every run of the suite.**
- `UnscriptedSubsystem.h/.cpp` — a page of `FString` conversions and
  reflection macros. **Unverified.** If something does not build, it is here or
  in `Unscripted.Build.cs`.

**The first compile found three defects, which is what a first compile is for:**

- `check` is a MACRO in Unreal's `AssertionMacros.h`, and the runtime's
  validator has a method called `check`. Every call to it inside the core became
  "too many arguments provided to function-like macro invocation", twenty errors
  deep, in files the author never touched. `UscCore.cpp` now undefines it around
  the include and puts it back. Renaming the core's method to suit one engine
  would have been the wrong repair: the core is held to Python name for name,
  and the next engine will collide with something else.
- The module had exceptions OFF, because the ABI's guarantee — nothing escapes —
  reads like the core does not use them. It does: it refuses things by throwing,
  and the ABI catches them at the boundary. Exceptions are on, with the reason
  written down.
- And that flag looked ignored until the shared PCH was turned off. A shared
  precompiled header is built once per exception setting, and a module that
  needs a different one silently cannot use it.

That split has already paid for itself too. The native half's first version wrote
`record(fn(runtime_, &json), json)`, which compiles and is wrong: C++ does not
order the evaluation of a call's arguments, so the compiler may read `json`
before `fn` has written it — and gcc at `-O2` does. Nine checks failed and the
answer was simply empty. In a version where that code sat inside an Unreal
module, nothing would have caught it until somebody ran the plugin.

To try it: copy `port/bindings/unreal` into a project's `Plugins/` directory,
adjust `PortRoot` in `Unscripted.Build.cs` to point at `port/cpp`, and build.
The runtime is compiled INTO the module rather than linked as a shared library,
because several consoles forbid loading one at all.
