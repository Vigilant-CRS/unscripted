"""Run the Unreal plugin's automation tests against a live Unscripted service.

The compile check proves the C++ is well formed. This proves it BEHAVES: a real
service on a real port, a real engine running real HTTP through the plugin's own
parser, and assertions about what came back.

    python3 tools/unreal_smoke.py

The difference matters more than it sounds. Compiling would not have noticed
that `FUnscriptedAvatarPacket` had no `honesty` field -- the contract has promised it and
the service has sent it since the beginning, and a game built on the plugin
simply could not see whether a character had lied. That is the headline feature
of the runtime, dropped on the floor by a struct that compiled perfectly. It
took a test that asked for it.

WHAT IT NEEDS. A built engine (see `unreal_check.py`) and nothing else: Unreal's
editor runs headless without a licence, so this is unattended. The service is
started here, on a free port, with a generated token, and stopped afterwards.
"""

import argparse
import importlib.util
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
PLUGIN = os.path.join(ROOT, "integrations", "unreal", "UnscriptedBridge")


def _check_module():
    spec = importlib.util.spec_from_file_location(
        "_unreal_check", os.path.join(ROOT, "tools", "unreal_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def start_service(pack: str, work: str):
    """A real service on a free port. Returns (process, url, token)."""
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
    parser.add_argument("--engine", default=None)
    parser.add_argument("--world-pack", default=os.path.join(ROOT, "worldpacks",
                                                             "market-square"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    check = _check_module()
    engines = [args.engine] if args.engine else [
        e for e in check.find_engines() if check.is_built(e)]
    if not engines:
        print("No built Unreal engine found. See tools/unreal_check.py.")
        return 3
    engine = engines[0]
    editor = os.path.join(engine, "Engine", "Binaries", "Linux", "UnrealEditor-Cmd")
    if not os.path.exists(editor):
        print(f"{engine} has no UnrealEditor-Cmd; it is not a built engine.")
        return 3

    work = tempfile.mkdtemp(prefix="unscripted-unreal-smoke-")
    project = os.path.join(work, "LWTest")
    os.makedirs(os.path.join(project, "Source", "LWTest"), exist_ok=True)
    os.makedirs(os.path.join(project, "Plugins"), exist_ok=True)
    shutil.copytree(PLUGIN, os.path.join(project, "Plugins", "UnscriptedBridge"))
    with open(os.path.join(project, "LWTest.uproject"), "w", encoding="utf-8") as handle:
        json.dump({"FileVersion": 3, "EngineAssociation": "",
                   "Modules": [{"Name": "LWTest", "Type": "Runtime",
                                "LoadingPhase": "Default"}],
                   "Plugins": [{"Name": "UnscriptedBridge", "Enabled": True}]},
                  handle, indent=2)
    # An EDITOR target, which is what automation tests run under. The compile
    # check only needs the Game target; asking Build.sh for LWTestEditor without
    # this file fails with a RulesError that names nothing useful.
    editor_target = check.TARGET_CS.replace("LWTestTarget", "LWTestEditorTarget") \
                                   .replace("TargetType.Game", "TargetType.Editor")
    for path, text in (
            (os.path.join(project, "Source", "LWTestEditor.Target.cs"), editor_target),
            (os.path.join(project, "Source", "LWTest.Target.cs"), check.TARGET_CS),
            (os.path.join(project, "Source", "LWTest", "LWTest.Build.cs"), check.MODULE_CS),
            (os.path.join(project, "Source", "LWTest", "LWTest.cpp"), check.MODULE_CPP)):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    print("  ... building the plugin into a throwaway project")
    build = os.path.join(engine, "Engine", "Build", "BatchFiles", "Linux", "Build.sh")
    done = subprocess.run(
        [build, "LWTestEditor", "Linux", "Development",
         f"-project={os.path.join(project, 'LWTest.uproject')}"],
        capture_output=True, text=True, timeout=7200)
    if done.returncode != 0:
        for line in (done.stdout + done.stderr).splitlines():
            if "error" in line.lower():
                print(f"      {line.strip()[:170]}")
        shutil.rmtree(work, ignore_errors=True)
        return 1

    service, url, token = start_service(args.world_pack, work)
    print(f"  ... service on {url}")
    log = os.path.join(work, "automation.log")
    environment = dict(os.environ, UNSCRIPTED_URL=url, UNSCRIPTED_TOKEN=token)
    try:
        print("  ... running the automation tests inside Unreal")
        editor_process = subprocess.Popen(
            [editor, os.path.join(project, "LWTest.uproject"),
             "-ExecCmds=Automation RunTests Unscripted; Quit",
             "-unattended", "-nopause", "-nullrhi", "-nosplash",
             "-log", f"-abslog={log}"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # WAIT FOR THE LOG, NOT FOR THE PROCESS. The editor writes
        # "TEST COMPLETE" and then, on Linux, does not reliably exit -- it calls
        # RequestExit and sits there. Waiting on the process meant a
        # thirty-minute timeout after a run that had finished in seconds, and
        # the first green result was thrown away by it.
        deadline = time.time() + 1800
        while time.time() < deadline and editor_process.poll() is None:
            if os.path.exists(log):
                with open(log, encoding="utf-8", errors="replace") as handle:
                    if "TEST COMPLETE" in handle.read():
                        break
            time.sleep(1.0)
        if editor_process.poll() is None:
            editor_process.terminate()
            try:
                editor_process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                editor_process.kill()
    finally:
        service.terminate()

    text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    # Unreal writes "Test Completed. Result={Success} Name={X} Path={Y}" -- no
    # full stop after the brace. The first version of this expression demanded
    # one, and would have reported a fully green run as "no tests found".
    passed = re.findall(r"Test Completed\. Result=\{Success\} Name=\{([^}]+)\}", text)
    failed = re.findall(r"Test Completed\. Result=\{(?:Fail|Error)\} Name=\{([^}]+)\}", text)
    warnings = re.findall(r"UNSCRIPTED_URL is not set", text)
    for name in passed:
        print(f"      pass  {name}")
    for name in failed:
        print(f"      FAIL  {name}")
    for line in re.findall(r"^.*LogAutomationController.*Error:.*$", text, re.M)[:15]:
        print(f"        {line.strip()[:170]}")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)

    if warnings:
        print("\n  the tests could not see a service; they were skipped, not passed")
        return 2
    if failed or not passed:
        print(f"\n  {len(failed)} failed, {len(passed)} passed")
        return 1
    print(f"\n  {len(passed)} automation tests passed inside Unreal, against a "
          f"live service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
