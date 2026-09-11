"""Compile the Unity package, and fail on anything the compiler complains about.

Not part of the SDK. Like `scale_bench.py`, it exists so that whoever doubts a
claim can reproduce it rather than take it -- specifically so that "the C#
compiles" stops being an assertion about code nobody has built.

    python3 tools/unity_check.py

IT NEEDS NO UNITY LICENCE, and that is the point worth writing down. The obvious
approach -- open a throwaway project in `-batchmode` and read the log -- refuses
to start:

    No valid Unity Editor license found. Please activate your license.

Activating means signing in with a Unity account, which is the owner's to do and
nobody else's, so a check built that way could never run unattended and the
package would have stayed uncompiled indefinitely.

But an installed editor ships its own Roslyn compiler, its own .NET host and its
own reference assemblies, and invoking a compiler is not using an editor. So
this compiles the package's C# directly against Unity's own `UnityEngine`
assemblies, with warnings as errors, and needs nothing but the files on disk.

What it does NOT do, stated so nobody mistakes the claim: it does not open the
package in Unity, does not check the manifest is well formed to Package Manager,
and does not run anything. It proves the code compiles against the engine's real
API surface, which is exactly the thing that was previously unknown.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "integrations", "unity", "com.vigilant.unscripted")
SOURCES = os.path.join(PACKAGE, "Runtime")
#: The behavioural tests are C# too, and were not compiled by the first version
#: of this check -- so a test file with a typo in it would have looked fine
#: until somebody with a Unity licence tried to run it. They need the test
#: framework, which turns out to ship inside the editor rather than only in a
#: project, so this can check them without a licence as well.
TESTS = os.path.join(PACKAGE, "Tests", "Runtime")

#: Only the modules the package actually uses. Referencing everything would hide
#: an accidental dependency on a module a project might not have installed.
MODULES = ("UnityEngine.CoreModule", "UnityEngine.UnityWebRequestModule",
           "UnityEngine.JSONSerializeModule")


def find_editors() -> list:
    """Every installed editor, newest first."""
    patterns = [os.path.expanduser("~/Unity/Hub/Editor/*/Editor"),
                "/opt/unity/editors/*/Editor",
                "/run/media/*/*/opt/unity-editors/*/Editor"]
    found = []
    for pattern in patterns:
        found += [path for path in glob.glob(pattern) if os.path.isdir(path)]
    return sorted(set(found), reverse=True)


def _test_references(data: str) -> list:
    """nunit and the test runner, wherever this editor keeps them."""
    found = []
    for name in ("nunit.framework.dll", "UnityEngine.TestRunner.dll"):
        matches = sorted(glob.glob(os.path.join(data, "**", name), recursive=True))
        if matches:
            found.append(matches[0])
    return found


def compile_with(editor: str, verbose: bool = False, tests: bool = True) -> tuple:
    """`(returncode, output)` from compiling the package against this editor."""
    data = os.path.join(editor, "Data")
    dotnet = os.path.join(data, "NetCoreRuntime", "dotnet")
    csc = os.path.join(data, "DotNetSdkRoslyn", "csc.dll")
    netstandard = os.path.join(data, "NetStandard", "ref", "2.1.0",
                               "netstandard.dll")
    managed = os.path.join(data, "Managed", "UnityEngine")
    for needed in (dotnet, csc, netstandard, managed):
        if not os.path.exists(needed):
            return 4, f"this editor is missing {needed}"

    argv = [dotnet, csc, "-target:library", "-nologo", "-langversion:9.0",
            "-nostdlib+", "-warnaserror+", f"-r:{netstandard}"]
    for module in MODULES:
        path = os.path.join(managed, f"{module}.dll")
        if not os.path.exists(path):
            return 4, f"this editor is missing {module}.dll"
        argv.append(f"-r:{path}")
    # TWO PASSES, and the reason is not tidiness. The runtime assembly compiles
    # against netstandard 2.1, which is what a Unity package targets. The test
    # assembly cannot: the nunit Unity ships is a net40 build that binds to
    # mscorlib, and mixing mscorlib with netstandard in one compile produces a
    # wall of CS0012. So the tests are compiled separately, against the .NET 4.8
    # reference assemblies Unity also ships, referencing the runtime output.
    import tempfile
    staging = tempfile.mkdtemp(prefix="unscripted-unity-check-")
    try:
        runtime_dll = os.path.join(staging, "Vigilant.Unscripted.dll")
        argv.append("-out:" + runtime_dll)
        argv += sorted(glob.glob(os.path.join(SOURCES, "*.cs")))
        if verbose:
            print("  " + " ".join(argv))
        done = subprocess.run(argv, capture_output=True, text=True, timeout=900)
        output = (done.stdout + done.stderr).strip()
        if done.returncode != 0 or not tests or not os.path.isdir(TESTS):
            return done.returncode, output

        references = _test_references(data)
        api = os.path.join(data, "UnityReferenceAssemblies", "unity-4.8-api")
        if len(references) < 2 or not os.path.isdir(api):
            return done.returncode, output + (
                "\n  (tests not compiled: this editor ships no test framework)")

        test_argv = [dotnet, csc, "-target:library", "-nologo",
                     "-langversion:9.0", "-nostdlib+", "-warnaserror+",
                     "-out:" + os.path.join(staging, "Tests.dll"),
                     f"-r:{runtime_dll}"]
        test_argv += [f"-r:{path}" for path in references]
        test_argv += [f"-r:{path}" for path in
                      sorted(glob.glob(os.path.join(api, "*.dll")))
                      + sorted(glob.glob(os.path.join(api, "Facades", "*.dll")))]
        for module in MODULES:
            test_argv.append(f"-r:{os.path.join(managed, module + '.dll')}")
        test_argv += sorted(glob.glob(os.path.join(TESTS, "*.cs")))
        if verbose:
            print("  " + " ".join(test_argv))
        tested = subprocess.run(test_argv, capture_output=True, text=True,
                                timeout=900)
        return tested.returncode, (output + "\n"
                                   + (tested.stdout + tested.stderr).strip()).strip()
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", default=None,
                        help="Path to an editor's Editor/ directory.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    editors = [args.editor] if args.editor else find_editors()
    if not editors:
        print("No Unity editor found. Install one through Unity Hub, or pass\n"
              "  --editor /path/to/<version>/Editor")
        return 3

    sources = (sorted(glob.glob(os.path.join(SOURCES, "*.cs")))
               + sorted(glob.glob(os.path.join(TESTS, "*.cs"))))
    print(f"  {len(sources)} source file(s), "
          f"{sum(len(open(f, encoding='utf-8').readlines()) for f in sources)} lines")

    failed = 0
    for editor in editors:
        version = os.path.basename(os.path.dirname(editor))
        code, output = compile_with(editor, args.verbose)
        if code == 0:
            print(f"  {version}: compiles clean, warnings as errors")
        else:
            failed += 1
            print(f"  {version}: FAILED ({code})")
            for line in output.splitlines()[:20]:
                print(f"      {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
