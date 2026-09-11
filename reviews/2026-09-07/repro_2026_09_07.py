#!/usr/bin/env python3
"""Independent review probes, not the project's regression suite.

Run from any directory: python3 reviews/2026-09-07/repro_2026_09_07.py
Prints JSON. `invariant_holds: false` is a reproduced defect, exit status 1.
No network, no external model, no changes to shipped packs or runtime code.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from unscripted import Agent, Event, Proposition, Runtime, World
from unscripted.belief import BeliefEngine
from unscripted.common_knowledge import CommonKnowledgeEngine
from unscripted.contracts import RuntimeConfig
from unscripted.memory import Memory
from unscripted.persistence import Store
from unscripted.revision import discredit
from unscripted.routine import Routine
from unscripted.sdk import UnscriptedRuntime
from unscripted import snapshot


def sdk(pack="cyberpunk-block", **config):
    return UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=str(ROOT / "worldpacks" / pack), **config))


def mini():
    w = World(global_seed="review", world_time=0)
    w.places = {"p": {"noise_level": 0.0}, "q": {"noise_level": 0.0}}
    w.agents["observer"] = Agent(id="observer", location="p")
    w.agents["speaker"] = Agent(id="speaker", location="p")
    return w


def update(engine, beliefs, n, *, origin="one", speaker="speaker", trust=0.9,
           competence=0.9, skepticism=0.0):
    return engine.update(beliefs, Proposition("body:alive", {"agent": "subject"}),
        asserter_polarity="+", trust=trust, competence=competence,
        skepticism=skepticism, claim_id=n, origin_event=origin,
        world_time=n, speaker=speaker)[0]


def contradictory_provider():
    class Opposite:
        is_deterministic = False
        def realize(self, plan, style):
            return "The clinic was open all night."
    r = sdk()
    try:
        r.core.realizer = Opposite()
        response = r.submit_player_text("ask Honce about clinic").npc_response
        spoken = [s for code, _, d in response.reasons
                  if code == "dialogue.direct_answer" for s in d["spoken"]]
        return response.verdict != "ACCEPT" or not spoken, {
            "released": response.text, "verdict": response.verdict,
            "propagated": [s["rendered"] for s in spoken]}
    finally:
        r.close()


def paraphrased_secret():
    class Leak:
        is_deterministic = False
        def realize(self, plan, style):
            return "Milan hides in a room behind the bar."
    r = sdk()
    try:
        r.core.realizer = Leak()
        response = r.submit_player_text("ask Mr. Okada about milan").npc_response
        return response.verdict != "ACCEPT", {
            "released": response.text, "verdict": response.verdict,
            "authored_secret": r.world.agents["agent:corpo_okada"].secrets[0].summary}
    finally:
        r.close()


def repeated_lie_origins():
    class VariedCoverStory:
        is_deterministic = False
        count = 0
        def realize(self, plan, style):
            lines = ["Milan went outside the city.", "Milan moved outside the city.",
                     "Milan lives outside the city.", "Milan stays outside the city."]
            text = lines[self.count % len(lines)]
            self.count += 1
            return text
    r = sdk()
    try:
        r.core.realizer = VariedCoverStory()
        # Public respond API, fresh turn times, repeating one authored cover story.
        probabilities, origins = [], []
        for i in range(8):
            r.world.world_time += 1
            response = r.respond("agent:corpo_okada", topic="milan")
            p = r.world.agents[r.config.player_id]
            b = next((b for b in p.beliefs.values()
                      if "outside_the_city" in b.proposition.core_key()), None)
            if b:
                probabilities.append(b.expected_prob)
                origins = list(b.origin_counts)
        assert len(probabilities) == 8, "fixture must produce eight factual replies"
        return len(origins) <= 1, {"probabilities": probabilities, "origins": origins}
    finally:
        r.close()


def revision_retention():
    w, engine = mini(), BeliefEngine()
    for i in range(100):
        belief = update(engine, w.agents["observer"].beliefs, i)
    before = belief.expected_prob
    revised = discredit(w, "speaker", factor=0.1)
    return belief.expected_prob < before - 0.01, {
        "before": before, "after": belief.expected_prob,
        "dropped": belief.provenance_dropped, "touched": revised.touched}


def revision_dual_evidence():
    w, engine = mini(), BeliefEngine()
    belief = update(engine, w.agents["observer"].beliefs, 1)
    before = {"for": belief.support_for, "against": belief.support_against,
              "conflict": belief.conflict}
    discredit(w, "speaker", factor=0.1)
    return belief.support_against == 0 and belief.support_for < before["for"], {
        "before": before, "after": {"for": belief.support_for,
        "against": belief.support_against, "conflict": belief.conflict}}


def negative_evidence_sign():
    belief = update(BeliefEngine(), {}, 1, trust=0, competence=0, skepticism=1)
    return belief.support_against > 0 and belief.support_for == 0, {
        "probability": belief.expected_prob, "logit": belief.logit_val,
        "support_for": belief.support_for, "support_against": belief.support_against}


def standing_repeats():
    w = mini()
    rt = Runtime(w)
    rt.standing.enabled = True
    prop = Proposition("mistreated", {"by": "accused", "who": "victim"})
    rows = []
    for i in range(20):
        rt.process_event(Event(w.new_event_id(), w.world_time, "claim",
            actor="speaker", location="p", payload={"proposition": prop.as_dict(),
                "origin_event": "one-act", "audience": ["observer"]}))
        obs = w.agents["observer"]
        rows.append({"p": obs.beliefs[prop.core_key()].expected_prob,
                     "liking": obs.relationships["accused"]["liking"]})
    return abs(rows[-1]["liking"] - rows[5]["liking"]) < 0.001, {
        "first": rows[0], "sixth": rows[5], "twentieth": rows[-1]}


def foreign_save():
    a, b = sdk("cyberpunk-block"), sdk("noir-harbor")
    try:
        blob = a.export_state()
        report = b.inspect_state(blob)
        b.import_state(blob)
        player = b.world.agents[b.config.player_id]
        return not report["usable"], {"report": report, "player_location": player.location,
            "location_exists": player.location in b.world.places}
    finally:
        a.close()
        b.close()


def corrupt_save_atomicity():
    r = sdk()
    try:
        blob = copy.deepcopy(r.export_state())
        blob["state"]["world_time"] += 1000
        state = next(iter(blob["state"]["agents"].values()))
        state["beliefs"] = [{"invalid": True}]
        before = r.export_state()
        verdict = r.inspect_state(blob)
        error = None
        try:
            r.import_state(blob)
        except Exception as exc:
            error = type(exc).__name__
        after = r.export_state()
        return before == after, {"inspect_usable": verdict["usable"], "error": error,
            "time_before": before["world_time"], "time_after": after["world_time"],
            "state_unchanged": before == after}
    finally:
        r.close()


def ledger_branch_overwrite():
    w, store = mini(), Store()
    rt = Runtime(w, store)
    try:
        initial = snapshot.capture(w, rt)
        eid = w.new_event_id()
        rt.process_event(Event(eid, 1, "incident", location="p", payload={"summary": "branch A"}))
        old = json.loads(store.ledger_up_to(eid)[-1]["payload"])
        snapshot.restore(initial, w, rt)
        rt.process_event(Event(w.new_event_id(), 1, "incident", location="p",
                               payload={"summary": "branch B"}))
        new = json.loads(store.ledger_up_to(eid)[-1]["payload"])
        return old == new, {"event_id": eid, "old": old, "now": new,
                           "ledger_rows": store.event_count()}
    finally:
        store.close()


def judgement_roundtrip():
    original = Memory("judgement", "observer", "judgement", "a pattern",
        about=("agent:speaker", "helped"), evidence=("event:1", "event:2", "event:3"))
    restored = Memory.from_dict(json.loads(json.dumps(original.as_dict())))
    return original.about == restored.about and original.evidence == restored.evidence, {
        "before": {"about": original.about, "evidence": original.evidence},
        "after": {"about": restored.about, "evidence": restored.evidence}}


def unrecognized_memory():
    r = sdk("relay-station")
    try:
        a = r.world.agents["agent:adeyemi"]
        a.epistemic = {"confirmation_bias": 0.05}
        a.beliefs.clear()
        a.memory.clear()
        a.location = "place:store"
        original = Proposition("seal_breached", {"section": "place:store", "when": "night_cycle"})
        r.emit_event(Event(r.world.new_event_id(), r.world.world_time, "incident",
            location="place:store", payload={"proposition": original.as_dict(), "importance": 0.8}))
        beliefs = [b.proposition.as_dict() for b in a.beliefs.values()]
        memories = [m.proposition.as_dict() for _, _, m in r.retrieve_memories(a.id)
                    if m.proposition]
        return original.as_dict() not in memories, {"interpreted_beliefs": beliefs,
                                                    "retrievable_memories": memories}
    finally:
        r.close()


def scheduled_witnesses():
    def run(deltas):
        w = mini()
        a = w.agents["observer"]
        a.routine = Routine.from_list([{"from": 0, "place": "p"},
                                      {"from": 10, "place": "q"}])
        rt = Runtime(w)
        rt.routine.seed(w)
        rt.diffusion.params["enabled"] = False
        prop = Proposition("body:alive", {"agent": "subject"})
        w.scenario_events = [Event(w.new_event_id(), 20, "incident", location="p",
                                  payload={"proposition": prop.as_dict()})]
        for delta in deltas:
            rt.advance_time(delta)
        return {"has_incident_belief": prop.core_key() in a.beliefs,
                "location": a.location, "time": w.world_time}
    big, small = run([30]), run([10, 20])
    return big == small, {"advance_30": big, "advance_10_then_20": small}


def publicity_polarity():
    w = mini()
    ck = CommonKnowledgeEngine(enabled=True)
    prop = Proposition("body:alive", {"agent": "subject"})
    event = Event(1, 0, "broadcast", payload={"proposition": prop.negated().as_dict()})
    ck.observe(w, event, [(name, 1.0) for name in ("observer", "speaker", "third")])
    out = ck.is_out(prop.core_key(), "observer")
    return not out, {"broadcast": str(prop.negated()), "positive_marked_public": out}


def source_id_substring():
    w, engine = mini(), BeliefEngine()
    b = update(engine, w.agents["observer"].beliefs, 1,
               origin="said_agent:anna_100", speaker="relay")
    before = b.expected_prob
    discredit(w, "agent:ann")
    return before == b.expected_prob, {"discredited": "agent:ann",
        "actual_origin": "said_agent:anna_100", "before": before, "after": b.expected_prob}


def occ_fear_confirmation():
    from unscripted.affect import AffectEngine
    engine = AffectEngine()
    confirmed = engine.appraise({"prospect": "confirmed", "prior_fear": 0.8})
    disconfirmed = engine.appraise({"prospect": "disconfirmed", "prior_fear": 0.8})
    return ("relief", 0.8) not in confirmed and ("relief", 0.8) in disconfirmed, {
        "feared_event_confirmed": confirmed, "feared_event_disconfirmed": disconfirmed}


def origin_growth():
    engine, beliefs = BeliefEngine(), {}
    for i in range(2000):
        b = update(engine, beliefs, i, origin=f"independent:{i}")
    return len(b.origin_counts) < 2000, {"updates": 2000,
        "origin_count": len(b.origin_counts), "retained_provenance": len(b.provenance)}


def tom_fear_direction():
    from unscripted.social import TheoryOfMindEngine
    a = Agent(id="a", relationships={"b": {"fear": 0.9}})
    b = Agent(id="b", relationships={"a": {"fear": 0.0}})
    engine = TheoryOfMindEngine()
    when_a_fears_b = engine.expected_reaction(a, b.id, "threaten", {})[1]
    a.relationships["b"]["fear"] = 0.0
    b.relationships["a"]["fear"] = 0.9
    when_b_fears_a = engine.expected_reaction(a, b.id, "threaten", {})[1]
    return when_b_fears_a > when_a_fears_b, {
        "target_unafraid_actor_afraid": when_a_fears_b,
        "target_afraid_actor_unafraid": when_b_fears_a}


def provider_changes_semantic_state():
    class TextProvider:
        is_deterministic = False
        def __init__(self, text):
            self.text = text
        def realize(self, plan, style):
            return self.text
    rows = []
    for text in ("The clinic? Shutters were down all night.", "Long day. I could use a drink."):
        r = sdk()
        try:
            r.core.realizer = TextProvider(text)
            response = r.submit_player_text("ask Honce about clinic").npc_response
            player = r.world.agents[r.config.player_id]
            rows.append({"released": response.text, "verdict": response.verdict,
                         "player_beliefs": sorted(player.beliefs)})
        finally:
            r.close()
    return rows[0]["player_beliefs"] == rows[1]["player_beliefs"], {"runs": rows}


def http_token_disclosure():
    # Optional: binds only an ephemeral loopback port and uses a synthetic token.
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from unscripted.service import ServiceOptions, create_server
    r = sdk()
    token = "review-synthetic-token-not-a-real-credential"
    server = create_server(runtime=r, port=0, options=ServiceOptions(auth_token=token))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        try:
            with urlopen(base + "/capabilities", timeout=5) as response:
                before_status = response.status
        except HTTPError as exc:
            before_status = exc.code
        with urlopen(base + "/demo", timeout=5) as response:
            html = response.read().decode()
            demo_status = response.status
        exposed = token in html
        after_status = None
        if exposed:
            request = Request(base + "/advance", data=b'{"minutes":1}',
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                after_status = response.status
                response.read()
        return not exposed, {"unauthenticated_api_status": before_status,
            "unauthenticated_demo_status": demo_status, "synthetic_token_in_html": exposed,
            "mutation_using_disclosed_token_status": after_status}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        r.close()


CASES = [contradictory_provider, paraphrased_secret, repeated_lie_origins,
         revision_retention, revision_dual_evidence, negative_evidence_sign,
         standing_repeats, foreign_save, corrupt_save_atomicity,
         ledger_branch_overwrite, judgement_roundtrip, unrecognized_memory,
         scheduled_witnesses, publicity_polarity, source_id_substring,
         occ_fear_confirmation, origin_growth, tom_fear_direction,
         provider_changes_semantic_state]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true", help="also test a local HTTP server")
    parser.add_argument("--only", help="run only this named case")
    args = parser.parse_args()
    cases = CASES + ([http_token_disclosure] if args.http else [])
    if args.only:
        cases = [case for case in cases if case.__name__ == args.only]
        if not cases:
            parser.error("unknown case (HTTP case also needs --http)")
    rows = []
    for case in cases:
        try:
            holds, detail = case()
            rows.append({"case": case.__name__, "invariant_holds": holds, "detail": detail})
        except Exception as exc:
            rows.append({"case": case.__name__, "probe_error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    sys.exit(1 if any(row.get("invariant_holds") is not True for row in rows) else 0)
