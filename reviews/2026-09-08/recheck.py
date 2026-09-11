#!/usr/bin/env python3
"""Recheck of commit 56d77bf. Offline counterexamples, no product mutations.

Run from the repository root. Exit 1 means a reproduced invariant violation;
probe_error means the probe itself failed. Provider answers are synthetic.
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from unscripted import Agent, Event, Proposition, Runtime, World
from unscripted.belief import BeliefEngine, _contribution_key
from unscripted.contracts import RuntimeConfig
from unscripted.persistence import Store
from unscripted.provider import ProviderError
from unscripted.sdk import UnscriptedRuntime
from unscripted import snapshot


def sdk(pack="cyberpunk-block"):
    return UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=str(ROOT / "worldpacks" / pack), storage_path=":memory:"))


def speak(line, query="ask Honce about clinic", *, fail=False):
    class Fixed:
        is_deterministic = False
        expressed_commitment = None

        def realize(self, plan, style):
            if fail:
                raise ProviderError("synthetic timeout for review")
            return line

    runtime = sdk()
    try:
        runtime.core.realizer = Fixed()
        answer = runtime.submit_player_text(query).npc_response
        spoken = [s["rendered"] for code, _, detail in answer.reasons
                  if code in ("dialogue.direct_answer", "dialogue.deception")
                  for s in detail.get("spoken", [])]
        return {"input": line, "released": answer.text, "verdict": answer.verdict,
                "spoken": spoken,
                "player_beliefs": sorted(runtime.world.agents[runtime.config.player_id].beliefs),
                "reason_codes": [code for code, _, _ in answer.reasons]}
    finally:
        runtime.close()


def negation_scope():
    # Every input affirms OPEN; each contains a negation outside that proposition
    # or negates CLOSED. The runtime must not publish it while asserting NOT OPEN.
    lines = ["The clinic was open all night, no doubt.",
             "The clinic was not closed last night.",
             "Nobody doubts the clinic was open all night."]
    rows = [speak(line) for line in lines]
    bad = [row for row in rows if row["released"] == row["input"]
           and row["verdict"] == "ACCEPT"
           and any(move.startswith("NOT clinic_open") for move in row["spoken"])]
    return not bad, rows


def provider_failure_changes_state():
    good = speak("The clinic was not open last night.")
    failed = speak(None, fail=True)
    return good["spoken"] == failed["spoken"] and good["player_beliefs"] == failed["player_beliefs"], {
        "valid_provider": good, "provider_failure": failed}


def secret_paraphrase():
    # "room" is guarded now. A positional description of the hiding place
    # without that entity's lexical forms still reaches the player.
    lines = ["Milan went outside the city. Now he hides in a room behind where drinks are served.",
             "Milan went outside the city. Now he hides behind where drinks are served."]
    results = [speak(line, "ask Mr. Okada about milan") for line in lines]
    return not any(row["verdict"] == "ACCEPT" and row["released"] == row["input"]
                   for row in results), results


def recycled_origin():
    engine, beliefs = BeliefEngine(), {}
    prop = Proposition("body:alive", {"agent": "subject"})

    def hear(origin, index, *, neutral=False):
        return engine.update(beliefs, prop, asserter_polarity="+",
            trust=0.0 if neutral else 0.9, competence=0.0 if neutral else 0.9,
            skepticism=1 / 6 if neutral else 0.0,
            claim_id=index, origin_event=origin, world_time=index,
            speaker="speaker")[0]

    hear("first-pinned", 0, neutral=True)
    belief = hear("recycled", 1)
    first = belief.logit_val
    limit = engine.params["origin_limit"]
    for index in range(limit):
        hear(f"filler-{index}", index + 2, neutral=True)
    evicted = "recycled" not in belief.origin_counts
    before = belief.logit_val
    hear("recycled", limit + 2)
    repeated = belief.logit_val - before
    contribution = belief.contributions[_contribution_key("speaker", "recycled")][0]
    ceiling = first * engine.max_origin_contribution()
    return contribution <= ceiling + 1e-10, {
        "origin_limit": limit, "origin_evicted": evicted,
        "first_contribution": first, "repeat_contribution": repeated,
        "source_total": contribution, "advertised_source_ceiling": ceiling,
        "p_before_repeat": 1 / (1 + math.exp(-before)),
        "p_after_repeat": belief.expected_prob}


def snapshot_ledger_changes_later():
    world = World(global_seed="review", world_time=0)
    world.places = {"p": {"noise_level": 0.0}}
    world.agents["observer"] = Agent(id="observer", location="p")
    store = Store()
    runtime = Runtime(world, store)
    try:
        beginning = snapshot.capture(world, runtime)
        runtime.process_event(Event(world.new_event_id(), 1, "incident", location="p",
                                    payload={"summary": "branch A"}))
        saved_a = snapshot.capture(world, runtime)
        watermark = saved_a["event_id_watermark"]

        def history():
            return [{"entry": row["entry"], "event_id": row["event_id"],
                     "summary": json.loads(row["payload"])["summary"]}
                    for row in store.ledger_up_to(watermark)]

        before = history()
        snapshot.restore(beginning, world, runtime)
        runtime.process_event(Event(world.new_event_id(), 1, "incident", location="p",
                                    payload={"summary": "branch B"}))
        after = history()
        return before == after, {"saved_a_watermark": watermark,
            "saved_a_history_before": before, "saved_a_history_after": after,
            "note": "Both audit rows survive, but the same snapshot query now includes a future branch."}
    finally:
        store.close()


def foreign_world_with_shared_place():
    source, target = sdk("cyberpunk-block"), sdk("noir-harbor")
    try:
        # Two unrelated packs can legitimately reuse a generic place id.
        # This changes only these in-memory worlds; no shipped pack is edited.
        for runtime in (source, target):
            runtime.world.places["place:spawn"] = {"label": "Spawn"}
        source.world.world_time += 123
        blob = source.export_state()
        before = target.world.world_time
        report = target.inspect_state(blob)
        target.import_state(blob)
        return not report["usable"], {"source_pack": "cyberpunk-block",
            "target_pack": "noir-harbor", "common_place": "place:spawn",
            "report": report, "target_time_before": before,
            "target_time_after": target.world.world_time}
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    rows = []
    for case in (negation_scope, provider_failure_changes_state, secret_paraphrase,
                 recycled_origin, snapshot_ledger_changes_later,
                 foreign_world_with_shared_place):
        try:
            holds, detail = case()
            rows.append({"case": case.__name__, "invariant_holds": holds, "detail": detail})
        except Exception as exc:
            rows.append({"case": case.__name__, "probe_error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    raise SystemExit(any(row.get("invariant_holds") is not True for row in rows))
