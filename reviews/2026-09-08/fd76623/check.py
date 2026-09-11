#!/usr/bin/env python3
"""Independent probes for fd76623. Offline, in-memory worlds only.

Exit 1 means a tested invariant is false; probe_error is a broken probe.
The retention case checks the original global ceiling, a contract now weakened
by the implementation, and is not an assertion that its documented per-cycle
bound was exceeded.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from unscripted import Agent, Event, Proposition, Runtime, World
from unscripted.belief import BeliefEngine
from unscripted.contracts import RuntimeConfig
from unscripted.persistence import Store
from unscripted.provider import ProviderError
from unscripted.sdk import UnscriptedRuntime
from unscripted import snapshot


def sdk(pack="cyberpunk-block", **config):
    return UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=str(ROOT / "worldpacks" / pack), storage_path=":memory:", **config))


class Fixed:
    is_deterministic = False
    expressed_commitment = None

    def __init__(self, line, fail=False):
        self.line, self.fail, self.calls = line, fail, []

    def realize(self, plan, style):
        self.calls.append({"act": plan.dialogue_act, "facts": list(plan.allowed_facts),
                           "avoid": list(plan.avoid_topics)})
        if self.fail:
            raise ProviderError("synthetic review timeout")
        return self.line


def reply(answer):
    return {"text": answer.text, "verdict": answer.verdict,
            "spoken": [move["rendered"] for code, _, detail in answer.reasons
                       if code in ("dialogue.direct_answer", "dialogue.deception", "dialogue.spoken")
                       for move in detail.get("spoken", [])],
            "reason_codes": [code for code, _, _ in answer.reasons]}


def controlled_multiple_facts():
    r = sdk()
    try:
        actor = r.world.agents["agent:barkeep_12"]
        # A valid additional belief, as the simulation may acquire during play.
        r.core.belief.update(actor.beliefs,
            Proposition("clinic_open", {"place": "place:clinic", "when": "today"}),
            asserter_polarity="+", trust=.9, competence=.9, skepticism=0,
            claim_id="review_today", origin_event="review_today",
            world_time=r.world.world_time, speaker=actor.id)
        answer = reply(r.respond(actor.id, topic="clinic"))
        silent_extra = any("when=today" in claim for claim in answer["spoken"])
        return not (silent_extra and answer["text"] ==
                    "Far as I know, the place was shut that night."), answer
    finally:
        r.close()


def controlled_shortening():
    r = sdk()
    try:
        actor = r.world.agents["agent:barkeep_12"]
        actor.affect.mood.p, actor.affect.mood.a = -1.0, 1.0
        topic = r.world.topics["clinic"]
        # Correct authored content with an introductory sentence. No pack file
        # is changed; this exercises supported content and style inputs.
        topic.phrasings["affirm"] = {
            register: "Listen carefully. " + line
            for register, line in topic.phrasings["affirm"].items()}
        answer = reply(r.respond(actor.id, topic="clinic"))
        answer["authored_variants"] = topic.phrasings["affirm"]
        return not (answer["text"] == "Listen carefully." and answer["spoken"]), answer
    finally:
        r.close()


def controlled_nonfactual_plan():
    r = sdk()
    provider = Fixed("He hides behind where drinks are served.")
    try:
        r.core.realizer = provider
        answer = reply(r.respond("agent:corpo_okada"))
        answer["provider_calls"] = provider.calls
        answer["mode"] = r.core.semantic_release
        bad = (answer["verdict"] == "ACCEPT" and answer["text"] == provider.line
               and provider.calls and not provider.calls[0]["facts"])
        return not bad, answer
    finally:
        r.close()


def provider_history_changes_controlled_fact():
    rows = []
    for line in ("Evening.", "Far as I know, the place was shut that night."):
        r, provider = sdk(), Fixed(line)
        try:
            r.core.realizer = provider
            first = reply(r.respond("agent:barkeep_12"))
            second = reply(r.respond("agent:barkeep_12", topic="clinic"))
            rows.append({"provider_line": line, "calls": provider.calls,
                "first": first, "second": second,
                "player_beliefs": sorted(r.world.agents[r.config.player_id].beliefs)})
        finally:
            r.close()
    return (rows[0]["second"]["spoken"] == rows[1]["second"]["spoken"]
            and rows[0]["player_beliefs"] == rows[1]["player_beliefs"]), rows


def origin_over_many_cycles():
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
    belief = hear("one-informative-report")
    initial, first = belief.expected_prob, belief.logit_val
    fillers = [f"filler-{i}" for i in range(engine.params["origin_limit"] - 1)]
    steps = []
    for cycle in range(1, 21):
        for origin in fillers:
            hear(origin, True)  # kappa = .5: exactly zero information
        before = belief.logit_val
        hear("one-informative-report")
        if cycle in (1, 2, 5, 10, 20):
            steps.append({"cycle": cycle, "repeat_delta": belief.logit_val - before,
                          "p": belief.expected_prob})
    ceiling = first * engine.max_origin_contribution()
    return belief.logit_val <= ceiling + 1e-9, {
        "initial_p": initial, "initial_contribution": first,
        "distinct_origins_total": len(fillers) + 2, "cycles": steps,
        "total_logit": belief.logit_val, "global_ceiling_before_eviction": ceiling,
        "scope": "Original global saturation guarantee, not the weaker per-cycle bound."}


def world_identity_fallback():
    source, target = sdk(), sdk("noir-harbor")
    try:
        for r in (source, target):
            for name in ("spawn", "street"):
                r.world.places["place:" + name] = {"label": name}
        before = target.world.world_time
        blob = source.export_state()
        report = target.inspect_state(blob)
        target.import_state(blob)
        return not report["usable"], {"source_pack": "cyberpunk-block",
            "target_pack": "noir-harbor", "source_id": source.world.world_id,
            "target_id": target.world.world_id, "common_places": ["spawn", "street"],
            "report": report, "target_time_before": before,
            "target_time_after": target.world.world_time}
    finally:
        source.close()
        target.close()


def provider_error_recovers_content():
    rows = []
    for fail in (False, True):
        r = sdk(semantic_release="provider")
        provider = Fixed("The clinic was not open last night.", fail=fail)
        try:
            r.core.realizer = provider
            answer = reply(r.respond("agent:barkeep_12", topic="clinic"))
            answer["calls"] = provider.calls
            rows.append(answer)
        finally:
            r.close()
    return bool(rows[0]["spoken"]) and rows[0]["spoken"] == rows[1]["spoken"], rows


def ledger_watermark_stays_fixed():
    world = World(global_seed="review", world_time=0)
    world.places = {"p": {"noise_level": 0.0}}
    world.agents["observer"] = Agent(id="observer", location="p")
    store = Store()
    core = Runtime(world, store)
    try:
        start = snapshot.capture(world, core)
        core.process_event(Event(world.new_event_id(), 1, "incident", location="p",
                                  payload={"summary": "branch A"}))
        watermark = snapshot.capture(world, core)["ledger_watermark"]
        before = store.ledger_as_of(watermark)
        snapshot.restore(start, world, core)
        core.process_event(Event(world.new_event_id(), 1, "incident", location="p",
                                  payload={"summary": "branch B"}))
        after = store.ledger_as_of(watermark)
        return before == after and len(after) == 1, {
            "watermark": watermark, "before": before, "after": after,
            "all_audit_rows": store.event_count()}
    finally:
        store.close()


if __name__ == "__main__":
    rows = []
    for case in (controlled_multiple_facts, controlled_shortening,
                 controlled_nonfactual_plan, provider_history_changes_controlled_fact,
                 origin_over_many_cycles, world_identity_fallback,
                 provider_error_recovers_content, ledger_watermark_stays_fixed):
        try:
            holds, detail = case()
            rows.append({"case": case.__name__, "invariant_holds": bool(holds), "detail": detail})
        except Exception as exc:
            rows.append({"case": case.__name__, "probe_error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    raise SystemExit(any(row.get("invariant_holds") is not True for row in rows))
