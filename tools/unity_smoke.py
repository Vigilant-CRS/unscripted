"""Run the Unity package's tests against a live Unscripted service.

The counterpart to `unreal_smoke.py`, and the reason both exist: the Unreal
plugin compiled cleanly for months and still dropped the `honesty` field the
contract promises, and carried a version pin that made the engine refuse to load
it. Neither was findable by compiling. Unity gets the same treatment.

    python3 tools/unity_smoke.py

THIS ONE NEEDS A UNITY LICENCE, and that asymmetry is worth stating rather than
apologising for. `unity_check.py` avoids one by invoking the Roslyn compiler the
editor ships -- invoking a compiler is not using an editor. Running tests IS
using the editor, and Unity's batch mode refuses to start without an activated
licence:

    No valid Unity Editor license found. Please activate your license.

Unreal has no such restriction, which is why its behavioural tests run
unattended here and Unity's do not. Sign in once in Unity Hub -- Personal is
free -- and this becomes a single command.
"""

import argparse
import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "integrations", "unity", "com.vigilant.unscripted")


#: Printed when an editor will not start for want of a system library.
#:
#: Unity 6000.6 wants `libxml2.so.2`; Ubuntu 26.04 ships `libxml2.so.16`, and
#: the two are not the same ABI, so a symlink crashes rather than works. The
#: library goes BESIDE the editor rather than into the system: this is a test
#: rig, and a test rig has no business changing the machine it runs on.
HOW_TO_SUPPLY_A_MISSING_LIBRARY = """
  {library} is not on this system, and this is a fact about the machine
  rather than about the package. Put the old library beside the editor instead
  of installing it -- a test rig should not change the machine it runs on:

      EDITOR=/path/to/Editor            # the directory holding `Unity`
      mkdir -p "$EDITOR/../compat" && cd "$EDITOR/../compat"
      # whichever release still carried it; for libxml2.so.2 on Ubuntu this is
      # noble's libxml2 2.9.14, which itself wants libicu74
      curl -sLO http://archive.ubuntu.com/ubuntu/pool/main/libx/libxml2/libxml2_2.9.14+dfsg-1.3ubuntu3.8_amd64.deb
      curl -sLO http://archive.ubuntu.com/ubuntu/pool/main/i/icu/libicu74_74.2-1ubuntu3.1_amd64.deb
      for d in *.deb; do dpkg-deb -x "$d" .; done
      export LD_LIBRARY_PATH="$PWD/usr/lib/x86_64-linux-gnu"

  Then run this tool again in the same shell. `ldd` on the library itself will
  name anything still missing.
"""


def find_editors() -> list:
    patterns = [os.path.expanduser("~/Unity/Hub/Editor/*/Editor/Unity"),
                "/run/media/*/*/opt/unity-editors/*/Editor/Unity",
                "/opt/unity/editors/*/Editor/Unity"]
    found = []
    for pattern in patterns:
        found += glob.glob(pattern)
    return sorted(set(found), reverse=True)


def start_service(pack: str, work: str):
    announce = os.path.join(work, "announce.json")
    token = secrets.token_urlsafe(18)
    process = subprocess.Popen(
        [sys.executable, "-m", "unscripted", "serve", "--world-pack", pack,
         "--port", "0", "--announce", announce, "--auth-token", token,
         "--parent-pid", str(os.getpid())],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 60
    while time.time() < deadline and not os.path.exists(announce):
        time.sleep(0.2)
    if not os.path.exists(announce):
        process.kill()
        raise SystemExit("the service never came up")
    return process, json.load(open(announce, encoding="utf-8"))["url"], token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", default=None)
    parser.add_argument("--world-pack", default=os.path.join(ROOT, "worldpacks",
                                                             "market-square"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    editors = [args.editor] if args.editor else find_editors()
    if not editors:
        print("No Unity editor found. Install one through Unity Hub.")
        return 3
    editor = editors[0]

    work = tempfile.mkdtemp(prefix="unscripted-unity-smoke-")
    project = os.path.join(work, "LWTest")
    os.makedirs(os.path.join(project, "Packages"), exist_ok=True)
    os.makedirs(os.path.join(project, "Assets"), exist_ok=True)
    shutil.copytree(PACKAGE, os.path.join(project, "Packages",
                                          os.path.basename(PACKAGE)))
    # The test framework has to be a project dependency or the test assembly
    # will not compile, however correct it is.
    with open(os.path.join(project, "Packages", "manifest.json"), "w",
              encoding="utf-8") as handle:
        # `testables` is the part everybody misses. Unity does not run tests that
        # live INSIDE a package unless the package is named here -- it finds
        # them, compiles them, and then runs none of them, reporting "0 passed"
        # with no error. Which is exactly what happened on the first attempt.
        json.dump({"dependencies": {
            "com.unity.test-framework": "1.4.5",
            "com.vigilant.unscripted": "file:com.vigilant.unscripted"},
            "testables": ["com.vigilant.unscripted"]},
            handle, indent=2)

    service, url, token = start_service(args.world_pack, work)
    print(f"  ... service on {url}")
    results = os.path.join(work, "results.xml")
    log = os.path.join(work, "unity.log")
    environment = dict(os.environ, UNSCRIPTED_URL=url, UNSCRIPTED_TOKEN=token)
    try:
        print("  ... running the tests inside Unity (first run imports the "
              "project, which is slow)")
        run = subprocess.run(
            [editor, "-batchmode", "-runTests", "-projectPath", project,
             "-testPlatform", "PlayMode", "-testResults", results,
             "-logFile", log, "-nographics"],
            env=environment, capture_output=True, text=True, timeout=3600)
    finally:
        service.terminate()

    text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""

    # DID THE EDITOR EVEN START?
    #
    # It reported "0 failed, 0 passed" for an editor that never ran: Unity 6000.6
    # exits immediately on this machine with `error while loading shared
    # libraries: libxml2.so.2`, writes no log, and this tool then read no results
    # file and reported the same green-looking nothing it reports for a project
    # with no tests in it. "Nothing ran" and "nothing failed" have to be
    # different sentences, and the second one is the one somebody quotes.
    if not os.path.exists(log) or not text.strip():
        detail = ((run.stderr or run.stdout or "").strip().splitlines() or
                  ["it wrote nothing at all"])[0]
        print(f"\n  THE EDITOR DID NOT START. It exited with code {run.returncode} "
              f"and wrote no log:\n    {detail[:200]}\n"
              f"  This is not a test result. Nothing was run, so nothing passed "
              f"and nothing failed.")
        # The one we actually hit, with the fix, because "missing shared
        # library" is a wall somebody stops at rather than a problem they solve.
        missing = re.search(r"error while loading shared libraries: ([^:]+)", detail)
        if missing:
            print(HOW_TO_SUPPLY_A_MISSING_LIBRARY.format(library=missing.group(1)))
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        return 4
    if "No valid Unity Editor license" in text:
        print("\n  NO LICENCE. Unity's batch mode will not start without one.\n"
              "  Open Unity Hub, sign in once (Personal is free), then run this "
              "again.\n  This is the one thing here that cannot be automated.")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        return 3

    passed = failed = 0
    if os.path.exists(results):
        report = open(results, encoding="utf-8", errors="replace").read()
        # COUNT TEST CASES, NOT NODES. NUnit's XML marks the suites Passed too,
        # so a plain search for result="Passed" reported ten where three had
        # run. A count that inflates is worse than no count: it is the number
        # somebody quotes.
        cases = re.findall(r'<test-case\b[^>]*>', report)
        passed = sum(1 for c in cases if 'result="Passed"' in c)
        failed = sum(1 for c in cases if 'result="Failed"' in c)
        for case in cases:
            if 'result="Failed"' in case:
                name = re.search(r'name="([^"]+)"', case)
                print(f"      FAIL  {name.group(1) if name else case[:80]}")
            elif 'result="Passed"' in case:
                name = re.search(r'name="([^"]+)"', case)
                print(f"      pass  {name.group(1) if name else ''}")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)

    if failed or not passed:
        print(f"\n  {failed} failed, {passed} passed")
        return 1
    print(f"\n  {passed} tests passed inside Unity, against a live service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
