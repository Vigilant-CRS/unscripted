#!/usr/bin/env python3
"""The review's own checks, re-run after the fix.

ONE word changed from `check.py`: it reported the value of
`unrecognised_spent`, a field the fix removes along with the design that
needed it, so it reads `origins_refused` instead. Every scenario, every
constant and every assertion is theirs.

Original header follows.

Independent checks for 3c4524d; no network or product-file changes.

Exit 1: a reproduced invariant violation. probe_error: a broken test fixture.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from unscripted import Proposition
from unscripted.belief import BeliefEngine
from unscripted.contracts import RuntimeConfig
from unscripted.sdk import UnscriptedRuntime


def origin_scenario(prior_repeats, cycles, repeated_after_reentry):
    engine, beliefs, clock = BeliefEngine(), {}, 0
    prop = Proposition("body:alive", {"agent": "subject"})

    def hear(origin, neutral=False):
        nonlocal clock
        clock += 1
        return engine.update(beliefs, prop, asserter_polarity="+",
            trust=0 if neutral else .9, competence=0 if neutral else .9,
            skepticism=1 / 6 if neutral else 0, claim_id=clock,
            origin_event=origin, world_time=clock, speaker="speaker")[0]

    hear("pinned", True)
    belief = hear("one-report")
    first = belief.logit_val
    for _ in range(prior_repeats):
        hear("one-report")
    before = belief.logit_val
    fillers = [f"filler-{i}" for i in range(engine.params["origin_limit"] - 1)]
    steps = []
    for cycle in range(1, cycles + 1):
        for origin in fillers:
            hear(origin, True)  # kappa .5: no informative evidence
        old = belief.logit_val
        hear("one-report")
        reentry = belief.logit_val - old
        old = belief.logit_val
        for _ in range(repeated_after_reentry):
            hear("one-report")
        if cycle in (1, 2, 20, 100):
            steps.append({"cycle": cycle, "on_reentry": reentry,
                "on_recognised_repeats": belief.logit_val - old,
                "origins_refused": belief.origins_refused,
                "logit": belief.logit_val, "p": belief.expected_prob})
    ceiling = first * engine.max_origin_contribution()
    return belief.logit_val <= ceiling + 1e-9, {
        "origin_limit": engine.params["origin_limit"],
        "distinct_origins": len(fillers) + 2, "prior_repeats": prior_repeats,
        "before_cycles": before, "ceiling": ceiling,
        "extra_hearings_after_reentry": repeated_after_reentry, "steps": steps}


def repeat_allowance_already_spent():
    return origin_scenario(prior_repeats=8, cycles=1, repeated_after_reentry=0)


def recognised_after_budget_exhausted():
    return origin_scenario(prior_repeats=0, cycles=100, repeated_after_reentry=1)


def controlled_repeat_verdict():
    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=str(ROOT / "worldpacks/cyberpunk-block"), storage_path=":memory:"))
    try:
        rows = []
        for index in range(5):
            answer = runtime.respond("agent:barkeep_12", topic="clinic")
            spoken = [move["rendered"] for code, _, detail in answer.reasons
                      if code == "dialogue.direct_answer"
                      for move in detail.get("spoken", [])]
            rows.append({"turn": index + 1, "text": answer.text,
                "verdict": answer.verdict, "spoken": spoken,
                "reason_codes": [code for code, _, _ in answer.reasons]})
        held = all(not row["spoken"] or row["verdict"] == "ACCEPT" for row in rows)
        audit = [{"verdict": verdict, "accepted_output": text}
                 for verdict, text in runtime.store.conn.execute(
                     "SELECT validation_result, accepted_output FROM provider_call ORDER BY rowid")]
        return held, {"turns": rows, "audit": audit}
    finally:
        runtime.close()


if __name__ == "__main__":
    rows = []
    for case in (repeat_allowance_already_spent, recognised_after_budget_exhausted,
                 controlled_repeat_verdict):
        try:
            holds, detail = case()
            rows.append({"case": case.__name__, "invariant_holds": holds, "detail": detail})
        except Exception as exc:
            rows.append({"case": case.__name__, "probe_error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    raise SystemExit(any(row.get("invariant_holds") is not True for row in rows))
