"""Golden-scenario harness.

A golden scenario is a deterministic multi-step playthrough with assertions on
each step. Unlike the unit tests (which probe single invariants), goldens prove
the runtime behaves correctly across a *sequence* -- multi-turn dialogue, rumour
spread, secret non-leak under low trust, faction mobilization over time, memory
forgetting, save/load mid-run. They are the robustness evidence a studio asks for.

Scenario JSON:
    {
      "name": "...",
      "world_pack": "worldpacks/cyberpunk-block",
      "commands": [
        {"input": "ask Honce about clinic",
         "expect_contains": ["shut that night"],   # substring in the player-facing message
         "expect_absent":   ["password"],           # substring that must NOT appear (e.g. a leaked secret)
         "expect_trace":    ["dialogue.direct_answer"]}  # substring in the developer/reason trace
      ]
    }
"""
from __future__ import annotations

import glob
import json
import os

from .contracts import RuntimeConfig
from .sdk import UnscriptedRuntime


def run_scenario(spec: dict, *, default_pack: str = "worldpacks/cyberpunk-block") -> dict:
    """Run one scenario spec and return {name, steps, failures}."""
    cfg = RuntimeConfig(world_pack_path=spec.get("world_pack", default_pack),
                        storage_path=":memory:",
                        player_start_location=spec.get("player_start"))
    sdk = UnscriptedRuntime.create(cfg)
    failures = []
    steps = spec.get("commands", [])
    try:
        for idx, step in enumerate(steps):
            result = sdk.submit_player_text(step["input"])
            msg = result.message or ""
            trace = result.developer_trace or ""
            label = f"step {idx} '{step['input']}'"
            # CASE-INSENSITIVE, both ways. These scenarios ask whether a line
            # mentions a thing, and whether it leaks one; whether the word
            # happened to land at the start of a sentence is a fact about
            # phrasing, not about what was said. A scenario looking for "seal"
            # failed on "Seal went in Stores, night cycle." -- which is the
            # answer it was asking for.
            #
            # `expect_absent` gains from it too, and that direction matters
            # more: a secret leaked as "Password" was not caught before.
            low_msg = msg.lower()
            for needle in step.get("expect_contains", []):
                if needle.lower() not in low_msg:
                    failures.append(f"{label}: message missing '{needle}' :: got {msg[:120]!r}")
            for needle in step.get("expect_absent", []):
                if needle.lower() in low_msg:
                    failures.append(f"{label}: message LEAKED forbidden '{needle}' :: {msg[:120]!r}")
            for needle in step.get("expect_trace", []):
                if needle not in trace:
                    failures.append(f"{label}: trace missing '{needle}'")
    finally:
        sdk.close()
    return {"name": spec.get("name", "unnamed"), "steps": len(steps), "failures": failures}


def run_scenario_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return run_scenario(json.load(f))


def run_all(directory: str) -> list[dict]:
    """Run every *.json scenario in a directory, sorted by filename."""
    results = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        results.append(run_scenario_file(path))
    return results
