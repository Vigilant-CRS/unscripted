"""Compile the Unreal plugin against a real engine, and report what breaks.

Not part of the SDK. The counterpart to `unity_check.py`, and the reason both
exist: for months this repository has had to say "the Unreal C++ has never been
compiled here", which is honest and is exactly the sentence a technical lead
stops reading at.

    python3 tools/unreal_check.py

WHY THIS ONE CANNOT TAKE THE SHORTCUT THE UNITY CHECK TAKES. For Unity it turned
out no editor was needed: an installed editor ships its own Roslyn compiler and
reference assemblies, and invoking a compiler is not using an editor. There is no
equivalent here. An Unreal plugin's `.generated.h` files come from
UnrealHeaderTool, and the ENGINE's own generated headers -- which `CoreMinimal.h`
and everything under it depend on -- only exist once the engine has been built.
Engine headers alone are not enough, so this needs a real engine: either a
pre-built one from unrealengine.com/linux, or a source tree that has been
through `Setup.sh` and `make`.

WHAT IT DOES. Builds a throwaway game project whose only content is this plugin,
with UnrealBuildTool, in Development. That compiles every .cpp in the plugin,
runs UHT over its UCLASS/UFUNCTION declarations, and links -- which is a stronger
claim than the Unity check makes, because it proves the reflection macros are
well formed too, and those are the part hand-written C++ most often gets wrong.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: The two Unreal plugins this repository ships, and they are for different
#: things. `UnscriptedBridge` talks HTTP to the runtime running as a sidecar --
#: the right answer on PC. `Unscripted` compiles the C++ core INTO the game and
#: reaches it through the C ABI -- the only answer on a console, which may not
#: ship an interpreter. Both have to compile, and neither proves the other.
PLUGINS = {
    "bridge": (os.path.join(ROOT, "integrations", "unreal", "UnscriptedBridge"),
               "UnscriptedBridge"),
    "native": (os.path.join(ROOT, "port", "bindings", "unreal"), "Unscripted"),
}

#: A throwaway module has to exist for UBT to have a target to build. The plugin
#: alone is not a thing that can be built, only a thing that can be built INTO
#: something.
TARGET_CS = """using UnrealBuildTool;
public class LWTestTarget : TargetRules
{
    public LWTestTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("LWTest");
    }
}
"""

MODULE_CS = """using UnrealBuildTool;
public class LWTest : ModuleRules
{
    public LWTest(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
    }
}
"""

MODULE_CPP = """#include "Modules/ModuleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, LWTest, "LWTest");
"""


def find_engines() -> list:
    """Anything that looks like a usable Unreal engine, newest first."""
    # Matched on what an engine IS, not on what somebody named the directory.
    # The first version looked for "UnrealEngine*" and missed an engine unpacked
    # into UE5.8/, which is the obvious thing to call it.
    patterns = ["/run/media/*/*/opt/*", "/run/media/*/*/*",
                os.path.expanduser("~/*"), os.path.expanduser("~/*/*"),
                "/opt/*", "/usr/local/*"]
    found = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            if os.path.exists(os.path.join(path, "Engine", "Build", "BatchFiles",
                                           "Linux", "Build.sh")):
                found.append(path)
    return sorted(set(found), reverse=True)


def is_built(engine: str) -> bool:
    """Has this engine actually been built, or is it just source?

    Asked before spending an hour finding out the hard way: UnrealBuildTool on an
    unbuilt source tree fails a long way in, with an error about a missing module
    rather than about the engine.
    """
    return bool(glob.glob(os.path.join(engine, "Engine", "Binaries", "Linux",
                                       "UnrealEditor*")))


def build_with(engine: str, keep: bool = False, which: str = "bridge") -> tuple:
    plugin_path, plugin_name = PLUGINS[which]
    work = tempfile.mkdtemp(prefix="unscripted-unreal-")
    project = os.path.join(work, "LWTest")
    os.makedirs(os.path.join(project, "Source", "LWTest"), exist_ok=True)
    os.makedirs(os.path.join(project, "Plugins"), exist_ok=True)
    shutil.copytree(plugin_path, os.path.join(project, "Plugins", plugin_name),
                    ignore=shutil.ignore_patterns("test", "*.md"))

    with open(os.path.join(project, "LWTest.uproject"), "w", encoding="utf-8") as handle:
        json.dump({"FileVersion": 3, "EngineAssociation": "",
                   "Description": "Throwaway project that exists only to compile the plugin.",
                   "Modules": [{"Name": "LWTest", "Type": "Runtime",
                                "LoadingPhase": "Default"}],
                   "Plugins": [{"Name": plugin_name, "Enabled": True}]},
                  handle, indent=2)
    for path, text in (
            (os.path.join(project, "Source", "LWTest.Target.cs"), TARGET_CS),
            (os.path.join(project, "Source", "LWTest", "LWTest.Build.cs"), MODULE_CS),
            (os.path.join(project, "Source", "LWTest", "LWTest.cpp"), MODULE_CPP)):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    build = os.path.join(engine, "Engine", "Build", "BatchFiles", "Linux", "Build.sh")
    # The native plugin's core lives outside the plugin, and the copy above put
    # the plugin somewhere the upward search cannot reach it. So it is pointed at
    # explicitly -- which is also the documented way a studio does it.
    environment = dict(os.environ,
                       UNSCRIPTED_PORT_ROOT=os.path.join(ROOT, "port", "cpp"))
    done = subprocess.run(
        [build, "LWTest", "Linux", "Development",
         f"-project={os.path.join(project, 'LWTest.uproject')}"],
        capture_output=True, text=True, timeout=7200, env=environment)
    output = done.stdout + done.stderr
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return done.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=None, help="Path to an engine root.")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--plugin", default="bridge", choices=sorted(PLUGINS),
                        help="`bridge` is the HTTP sidecar client; `native` "
                             "compiles the C++ core into the module.")
    args = parser.parse_args()

    engines = [args.engine] if args.engine else find_engines()
    if not engines:
        print("No Unreal engine found. Either:\n"
              "  - download the pre-built Linux engine from "
              "unrealengine.com/linux and unpack it, or\n"
              "  - run Setup.sh and make in a source tree,\n"
              "then pass --engine /path/to/engine.")
        return 3

    for engine in engines:
        if not is_built(engine):
            print(f"  {engine}\n      source only, not built — "
                  f"Engine/Binaries/Linux/UnrealEditor is missing")
            continue
        print(f"  {engine}\n      building the {args.plugin} plugin "
              f"(this takes minutes, not hours)")
        code, output = build_with(engine, args.keep, args.plugin)
        errors = [line for line in output.splitlines()
                  if " error" in line.lower() or line.startswith("Error:")]
        if code == 0 and not errors:
            print("      COMPILES CLEAN")
            return 0
        for line in errors[:25]:
            print(f"      {line.strip()[:160]}")
        print(f"      failed ({code}, {len(errors)} error lines)")
        return 1

    print("\n  No BUILT engine among those found. A source tree needs Setup.sh "
          "and make first;\n  the pre-built Linux download from "
          "unrealengine.com/linux needs neither.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
