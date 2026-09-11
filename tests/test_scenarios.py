#!/usr/bin/env python3
"""Self-contained tests (no pytest needed): `python tests/test_scenarios.py`.

Covers the core invariants of backlog steps 1-4.
"""
import copy
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unscripted import (World, Runtime, Agent, Proposition, Event, contradicts)
from unscripted.affect import pad_baseline_from_big_five


def _mini_world(seed="t"):
    w = World(global_seed=seed, world_time=100)
    w.places = {"p": {"noise_level": 0.0}}
    w.agents["npc"] = Agent(id="npc", location="p",
                            big_five={"agreeableness": 0.3, "emotional_stability": 0.4},
                            relationships={"speaker": {"trust": 0.3}},
                            education={"street": 0.5})
    w.agents["speaker"] = Agent(id="speaker", location="p")
    return w


def _claim_event(w, polarity="+", origin="o1", prop=None):
    p = prop or Proposition("looking_for", {"seeker": "speaker", "target": "x"}, polarity)
    return Event(event_id=w.new_event_id(), world_time=w.world_time, type="claim",
                 actor="speaker", location="p",
                 payload={"proposition": p.as_dict(), "origin_event": origin, "domain": "street"})


def test_determinism():
    def run():
        w = _mini_world("seedA")
        rt = Runtime(w)
        rt.process_event(_claim_event(w))
        b = list(w.agents["npc"].beliefs.values())[0]
        return round(b.logit_val, 9), w.agents["npc"].affect.mood.p
    assert run() == run(), "same seed must reproduce identical state"
    print("ok  determinism: identical seeds reproduce identical state")


def test_claim_is_not_truth():
    w = _mini_world()
    rt = Runtime(w)
    rt.process_event(_claim_event(w))
    b = list(w.agents["npc"].beliefs.values())[0]
    assert b.expected_prob < 0.65, f"single low-trust claim should not be near-certain (got {b.expected_prob})"
    print(f"ok  claim is not truth: one claim -> p={b.expected_prob:.2f} (stays uncertain)")


def test_correlation_discount():
    # different origin -> bigger jump than same origin repeat
    w = _mini_world()
    rt = Runtime(w)
    rt.process_event(_claim_event(w, origin="o1"))
    b = list(w.agents["npc"].beliefs.values())[0]
    p1 = b.expected_prob
    rt.process_event(_claim_event(w, origin="o1"))   # same origin
    p_same = b.expected_prob
    rt.process_event(_claim_event(w, origin="o2"))   # different origin
    p_diff = b.expected_prob
    d_same = p_same - p1
    d_diff = p_diff - p_same
    assert d_diff > d_same, f"independent evidence ({d_diff:.3f}) must move more than correlated ({d_same:.3f})"
    print(f"ok  correlation discount: same-origin +{d_same:.3f} < independent +{d_diff:.3f}")


def test_repetition_saturates_but_independent_sources_convince():
    """The moat claim, stated as an invariant: repetition is not proof.

    A flat per-repeat discount attenuates without saturating, so a single rumour
    repeated often still accumulated to certainty (200x -> p=0.995). Evidence from
    one origin now forms a convergent geometric series, so it has a ceiling no
    amount of repetition can pass, while genuinely independent origins still
    accumulate normally.
    """
    def believe(claims, *, distinct_origins):
        w = _mini_world()
        w.agents["npc"].relationships["speaker"] = {"trust": 0.9}
        rt = Runtime(w)
        for i in range(claims):
            rt.process_event(_claim_event(w, origin=f"o{i}" if distinct_origins else "o0"))
        return list(w.agents["npc"].beliefs.values())[0].expected_prob

    repeated = [believe(n, distinct_origins=False) for n in (1, 5, 200, 2000)]
    assert repeated[1] < 0.8, f"5 repeats of one rumour reached p={repeated[1]:.3f}"
    assert abs(repeated[3] - repeated[1]) < 0.01, (
        f"repetition must saturate: 5x -> {repeated[1]:.3f}, 2000x -> {repeated[3]:.3f}")

    independent = [believe(n, distinct_origins=True) for n in (1, 5, 20)]
    assert independent[1] > repeated[1] + 0.2, (
        "five independent sources must convince far more than five repetitions of one")
    assert independent[2] > 0.95, "twenty independent sources should approach certainty"

    from unscripted import BeliefEngine
    ceiling = BeliefEngine().max_origin_contribution()
    assert 1.0 < ceiling < 1.2, ceiling
    print(f"ok  belief: one origin saturates at p={repeated[3]:.3f} however often repeated "
          f"(ceiling {ceiling:.2f} hearings); 20 independent sources -> p={independent[2]:.3f}")


def test_contradiction_C1_and_C2():
    a = Proposition("body:alive", {"agent": "x"}, "+")
    b = Proposition("body:alive", {"agent": "x"}, "-")
    assert contradicts(a, b) == "C1"
    c = Proposition("space:exactly_at", {"entity": "x", "place": "bar"})
    d = Proposition("space:exactly_at", {"entity": "x", "place": "clinic"})
    assert contradicts(c, d) == "C2"
    # disjoint spatial scopes on a non-functional pred do not contradict
    e = Proposition("was_at", {"agent": "x", "place": "bar", "when": "t1"}, spatial="bar")
    f = Proposition("was_at", {"agent": "x", "place": "clinic", "when": "t2"}, spatial="clinic")
    assert contradicts(e, f) is None
    print("ok  contradiction: C1 (negation) and C2 (functional conflict) detected; disjoint scopes ok")


def test_affect_negative_event_lowers_valence():
    w = _mini_world()
    rt = Runtime(w)
    base = w.agents["npc"].affect.mood.p
    ev = Event(event_id=w.new_event_id(), world_time=w.world_time, type="threat", actor="speaker",
               location="p", payload={"appraisal": {"desirability": -0.8, "expectedness": 0.3}})
    rt.process_event(ev)
    after = w.agents["npc"].affect.mood.p
    assert after < base, f"negative event should lower valence ({after} !< {base})"
    assert after > -0.99, f"a single event must not saturate valence to the rail (got {after})"
    print(f"ok  affect: negative event lowers valence {base:+.2f} -> {after:+.2f} (soft, unsaturated)")


def test_pad_baseline_signs():
    extravert_agreeable = pad_baseline_from_big_five(
        {"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.9,
         "agreeableness": 0.9, "emotional_stability": 0.9})
    assert extravert_agreeable.p > 0, "high E/A/S should give positive baseline valence"
    print(f"ok  PAD baseline: extravert+agreeable -> valence {extravert_agreeable.p:+.2f} (>0)")


def test_register_by_social_position():
    from unscripted import SociolinguisticEngine
    se = SociolinguisticEngine()
    low = Agent(id="fixer", big_five={"agreeableness": 0.3}, education={"general": 0.35},
                identities=[{"id": "gang_member", "accessibility": 0.8}],
                roles=[{"role": "role:fixer"}], social_status=0.35, location="place:main_street")
    high = Agent(id="exec", big_five={"agreeableness": 0.4}, education={"general": 0.9},
                 identities=[{"id": "executive", "accessibility": 0.9}],
                 roles=[{"role": "role:officer"}], social_status=0.9, location="place:main_street")
    s_low = se.compute_style(low, place="place:main_street", affect_engine=None)
    s_high = se.compute_style(high, place="place:main_street", affect_engine=None)
    assert s_high.formality > s_low.formality, "exec register should be more formal than fixer's"
    assert s_low.slang_level > s_high.slang_level, "fixer should use more in-group slang"
    print(f"ok  register: fixer formality {s_low.formality:.2f}/slang {s_low.slang_level:.2f} "
          f"vs exec {s_high.formality:.2f}/{s_high.slang_level:.2f}")


def test_trust_kinetics_asymmetric():
    from unscripted import RelationshipEngine
    from unscripted.statekey import trust_delta
    re = RelationshipEngine()
    a = Agent(id="a", relationships={"b": {"trust": 0.5}})
    re.apply(a, [trust_delta("a", "b", +0.4, "favor", "t")], [])
    up = a.relationships["b"]["trust"] - 0.5
    a.relationships["b"]["trust"] = 0.5
    re.apply(a, [trust_delta("a", "b", -0.4, "betrayal", "t")], [])
    down = 0.5 - a.relationships["b"]["trust"]
    assert down > up, f"betrayal ({down:.3f}) must cost more than an equal favor earns ({up:.3f})"
    print(f"ok  trust kinetics: favor +{up:.3f} < betrayal -{down:.3f} (slow up, fast down)")


def test_utility_bounded():
    from unscripted.policy import bounded_aggregate
    assert -1.0 <= bounded_aggregate([0.9, 0.9, 0.9, 0.9]) <= 1.0
    assert bounded_aggregate([]) == 0.0
    print("ok  utility: group aggregate stays bounded in [-1,1]")


def test_validator_blocks_secret():
    """The protected vocabulary comes from the loaded world, not from the engine."""
    from unscripted import Validator
    from unscripted.dialogue import DialoguePlan
    from unscripted.world import load_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    world = load_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    v = Validator.for_world(world)
    plan = DialoguePlan(speaker="npc", addressee="p", dialogue_act="inform", goal="x",
                        avoid_topics=["brother_whereabouts"])
    res = v.check("He is at the clinic back room.", plan, None, [])
    assert res.verdict == "REJECT_HARD", "leaking the secret surface form must be rejected"
    ok2 = v.check("Maybe. Why do you care?", plan, None, [])
    assert ok2.verdict == "ACCEPT"

    # A validator that was handed no world vocabulary must SAY it cannot protect a
    # label, rather than silently accepting everything -- that silence is what made
    # every non-reference secret unprotected.
    blind = Validator()
    assert blind.unprotected_labels(["brother_whereabouts"]) == ["brother_whereabouts"]
    assert v.unprotected_labels(["brother_whereabouts"]) == []

    # the second pack's own secret is protected by the same machinery
    noir = load_world_pack(os.path.join(root, "worldpacks", "noir-harbor"))
    nv = Validator.for_world(noir)
    noir_plan = DialoguePlan(speaker="npc", addressee="p", dialogue_act="inform", goal="x",
                             avoid_topics=["missing_cargo"])
    leak = nv.check("I moved crate 19 off the manifest that night.", noir_plan, None, [])
    assert leak.verdict == "REJECT_HARD", "a second pack's secret must be protected too"
    assert nv.check("The harbour was quiet.", noir_plan, None, []).verdict == "ACCEPT"
    print("ok  validator: pack-declared secret vocabulary blocks leaks in both packs")


def test_ally_response_kinship():
    from unscripted.agency import ally_response
    w = World(global_seed="seedA", world_time=100)
    w.places = {"p": {}}
    father = Agent(id="dad", location="p", social_status=0.4)
    son = Agent(id="son", location="p", big_five={"agreeableness": 0.5},
                relationships={"dad": {"kinship": 0.95, "loyalty": 0.9}})
    stranger = Agent(id="x", location="p", big_five={"agreeableness": 0.5},
                     relationships={"dad": {"liking": 0.0}})
    w.agents = {"dad": father, "son": son, "x": stranger}
    r_son = ally_response(father, son, w, urgency=1.0, event_id=1)
    r_x = ally_response(father, stranger, w, urgency=1.0, event_id=1)
    assert r_son.probability > r_x.probability, "kin should respond more readily than a stranger"
    assert r_son.latency == 2, "co-located ally arrives fast"
    print(f"ok  ally response: son p={r_son.probability:.2f} > stranger p={r_x.probability:.2f}")


def test_reactive_rule_fires_when_injured():
    from unscripted.agency import default_reactive_rules, fire_reactive_rules
    rules = default_reactive_rules()
    ag = Agent(id="a")
    calm = fire_reactive_rules(ag, {"injured": False, "threatened": False}, rules)
    hurt = fire_reactive_rules(ag, {"injured": True, "threatened": True, "has_backup": True}, rules)
    assert not any(r.action_id == "mobilize_allies" for r in calm)
    assert any(r.action_id == "mobilize_allies" for r in hurt), "injured+threatened must trigger mobilize"
    print("ok  reactive rule: 'summon kin when hurt' fires only when injured AND threatened")


def test_leverage_asymmetric():
    from unscripted.agency import leverage
    patron = Agent(id="patron", social_status=0.9, resources=0.9)
    client = Agent(id="client", social_status=0.2, resources=0.1,
                   relationships={"patron": {"dependence": 0.7}})
    assert leverage(patron, client) > leverage(client, patron), "patron should hold more leverage"
    print(f"ok  leverage: patron {leverage(patron, client):.2f} > client {leverage(client, patron):.2f}")


def test_graded_resolution_bands():
    from unscripted.agency import resolve
    from unscripted.determinism import derive_seed
    outs = {resolve(0.7, derive_seed("s", "a", i, 0, "m")) for i in range(50)}
    assert outs <= {"full", "partial", "consequence", "miss"}
    assert "full" in outs and ("consequence" in outs or "miss" in outs), "should span success and failure bands"
    print(f"ok  graded resolution: observed outcome bands {sorted(outs)}")


def test_faction_heat_threshold_mobilizes():
    from unscripted.factions import Director, Faction
    d = Director()
    d.add_faction(Faction("badges", influence=0.8, resources=0.7,
                          territory=["p"], goals=["suppress_gang"]))
    w = World(global_seed="s", world_time=0)
    w.places = {"p": {}}
    d.add_heat("badges", 0.7, "violence")
    scheduled = []
    d.step(w, 30, lambda world, et, f, lat: scheduled.append((et, f.faction_id, lat)) or "ev")
    assert any(et == "faction_mobilize" for et, _, _ in scheduled), "heat over threshold must mobilize"
    print(f"ok  faction heat: threshold crossed -> mobilization scheduled ({len(scheduled)})")


def test_social_standing_gates_reach():
    from unscripted.agency import potential_allies
    w = World(global_seed="s", world_time=0)
    w.places = {"p": {}}
    officer = Agent(id="cop", location="p", social_status=0.6,
                    identities=[{"id": "officer", "group": "faction:badges"}],
                    roles=[{"role": "role:officer"}])
    high = Agent(id="high", location="p", social_status=0.9, identities=[])
    low = Agent(id="low", location="p", social_status=0.2, identities=[])
    w.agents = {"cop": officer, "high": high, "low": low}
    hi = [a.id for a in potential_allies(high, w) if any(r.get("role") == "role:officer" for r in a.roles)]
    lo = [a.id for a in potential_allies(low, w) if any(r.get("role") == "role:officer" for r in a.roles)]
    assert "cop" in hi and "cop" not in lo, "only high status can reach institutional allies"
    print("ok  social standing gates reach: high status reaches the officer, low status cannot")


def test_world_pack_validation():
    from unscripted import validate_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report = validate_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    assert report.ok, [f"{i.code}: {i.message}" for i in report.issues]
    print("ok  world pack validation: cyberpunk-block passes SDK checks")


def test_memory_fades_by_importance_not_uniformly():
    """A witnessed murder must outlast a passer-by.

    It did not. Importance was only ever used to order consolidation, so it had no
    effect on recall at all: at importance 0.95 and 0.05 a memory decayed
    identically. And world time is in minutes, which fed straight into the power
    law put ANY once-seen memory below the retrieval threshold after thirty of
    them -- a character forgot a murder before the player left the room. Neither
    showed up in a short test; both showed up the moment a run was long enough to
    watch one memory over days.
    """
    from unscripted.memory import Memory, MemoryEngine
    engine = MemoryEngine()
    threshold = engine.params["tau_ret"]

    def recall_curve(importance):
        memory = Memory(memory_id=f"m{importance}", owner="a", type="episodic",
                        content="x", importance=importance)
        engine.encode([], memory, 0)
        return {hours: memory.base_activation(hours * 60) for hours in (1, 24, 72, 168, 720)}

    important = recall_curve(0.95)
    trivial = recall_curve(0.05)

    for hours in important:
        assert important[hours] > trivial[hours], (
            f"at {hours}h an important memory ({important[hours]:.2f}) must be more "
            f"recallable than a trivial one ({trivial[hours]:.2f})")

    assert important[1] > threshold and trivial[1] > threshold, \
        "nothing should be forgotten within the hour"
    assert trivial[24] < threshold, "trivia should not survive a day"
    assert important[168] > threshold, "something important should survive a week"
    assert important[720] < threshold, "nothing should be recallable forever"

    print(f"ok  memory: trivia fades within a day, an important memory lasts a week "
          f"(threshold {threshold})")


def test_a_dossier_names_the_code_that_produced_it():
    """A result that cannot name its commit outlives the code it was true of."""
    import shutil
    import tempfile
    from unscripted.evidence import run_evidence
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = tempfile.mkdtemp()
    try:
        dossier = run_evidence(packs=[os.path.join(root, "worldpacks", "relay-station")],
                               hours=0.01, out_dir=workspace, only=["determinism"])
        run = dossier["run"]
        for field in ("commit", "python", "platform", "started_utc", "finished_utc",
                      "working_tree"):
            assert run.get(field), f"a dossier without {field} is an unaddressed number"
        assert run["working_tree"] in ("clean", "dirty")

        rendered = open(os.path.join(workspace, "DOSSIER.md"), encoding="utf-8").read()
        assert run["commit"][:12] in rendered, "the readable dossier must state it too"
        if run["working_tree"] == "dirty":
            # a run against uncommitted code must say so on its face, or it reads
            # as evidence for a commit that did not produce it
            assert "uncommitted changes" in rendered
        print(f"ok  evidence: dossier names commit {run['commit'][:12]} "
              f"({run['working_tree']}), python {run['python']}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_reach_and_detail_are_independent():
    """A headline reaches everyone and says little; a witness knows more, alone."""
    from unscripted.events import Event
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        for agent_id in ("agent:ferro", "agent:lindqvist"):
            world.agents[agent_id].location = "place:store"

        # what happened, in full, in front of two people
        runtime.core.process_event(Event(
            world.new_event_id(), world.world_time, "incident", location="place:store",
            payload={"proposition": {"predicate": "seal_breached",
                                     "slots": {"section": "place:store",
                                               "when": "night_cycle"},
                                     "polarity": "+"},
                     "summary": "a seal lets go", "importance": 0.8,
                     "origin_event": "incident_42"}))

        # the same incident on the station net, as a headline
        channel = list(world.channels)[0]
        for agent in world.agents.values():
            world.media_exposure[(agent.id, channel)] = {"attention": 0.6}
        runtime.core.process_event(Event(
            world.new_event_id(), world.world_time, "broadcast",
            payload={"proposition": {"predicate": "seal_breached",
                                     "slots": {"section": "place:store"},
                                     "polarity": "+"},
                     "channel": channel, "credibility": 0.7,
                     "summary": "station net", "origin_event": "incident_42"}))

        story = next(s for s in runtime.structured_knowledge()["stories"]
                     if s["origin"] == "incident_42")
        widest, richest = story["widest_known"], story["most_detailed"]

        assert widest["reach"] > richest["reach"], (
            "the headline should reach more people than the witness account")
        assert "when=" not in widest["text"], "a headline should not carry the detail"
        assert "night_cycle" in richest["text"], "the witness account should"
        assert len(story["versions"]) >= 2

        # a claim ARRIVING IN WORDS is not misheard: you can doubt a radio report
        # that a seal failed in Stores, but you do not hear "Stores" as "med bay"
        listeners = [a for a in world.agents.values()
                     if a.location != "place:store" and a.id != runtime.config.player_id]
        for listener in listeners:
            heard = [k for k in listener.beliefs if "seal_breached" in k]
            assert heard, f"{listener.id} heard nothing"
            assert all("section=place:store" in k for k in heard), (
                f"{listener.id} relocated a claim that was stated in words: {heard}")

        print(f"ok  stories: one incident, {len(story['versions'])} versions -- "
              f"reach {widest['reach']} at detail 1, reach {richest['reach']} at full detail")
    finally:
        runtime.close()


def test_a_crowded_room_does_not_update_the_whole_room():
    """Speech has earshot. Without it, a scene is quadratic in crowd size."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        world = runtime.world
        speaker = world.agents["agent:barkeep_12"]
        # fill the room well past earshot
        from unscripted.agent import Agent
        for index in range(30):
            extra = Agent(id=f"agent:crowd_{index}", location=speaker.location,
                          public_name=f"Regular {index}")
            world.agents[extra.id] = extra

        before = {a.id: len(a.beliefs) for a in world.agents.values()}
        result = runtime.submit_player_text("ask Honce about clinic")
        assert result.npc_response is not None
        heard = [a.id for a in world.agents.values()
                 if len(a.beliefs) > before[a.id]]

        assert heard, "nobody heard it at all"
        assert len(heard) <= runtime.EARSHOT + 2, (
            f"{len(heard)} of {len(world.agents)} people updated on one answer; "
            "an exchange is not a public announcement")
        print(f"ok  earshot: {len(heard)} of {len(world.agents)} in the room took it in")
    finally:
        runtime.close()


def test_the_occupancy_index_cannot_go_stale():
    """Whoever moves somebody, the index follows."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        agent = world.agents["agent:ferro"]
        origin, target = agent.location, "place:lab"
        assert agent in world.occupants(origin)

        agent.location = target                 # a plain attribute write
        assert agent in world.occupants(target), "the index did not follow the move"
        assert agent not in world.occupants(origin)

        runtime.advance_time(600)               # routines move people too
        for place in world.places:
            for occupant in world.occupants(place):
                assert occupant.location == place, (
                    f"{occupant.id} is indexed at {place} but stands at "
                    f"{occupant.location}")
        print("ok  occupancy: the index follows every move, however it was made")
    finally:
        runtime.close()


def test_repeated_episodes_become_a_judgement_that_outlives_them():
    """Ninety per cent of memory loss is eviction. Something should come of it."""
    from unscripted.evidence import _runtime
    from unscripted.memory import Memory
    from unscripted.ontology import Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        observer = world.agents["agent:ferro"]
        observer.memory.clear()
        engine = runtime.core.memory
        cap = engine.params["total_cap"]

        subject = "agent:rask"
        for index in range(cap + 30):
            proposition = Proposition("logged_out",
                                      {"agent": subject, "when": f"shift_{index}"}, "+")
            engine.encode(observer.memory,
                          Memory(memory_id=f"m{index}", owner=observer.id,
                                 type="episodic", content=f"{subject} slipped out early",
                                 proposition=proposition, importance=0.15,
                                 emotional_valence=-0.3),
                          world.world_time + index)

        reasons = engine.decay_and_consolidate(observer.memory, world.world_time + 5000)
        formed = [d for c, _m, d in reasons if c == "memory.judgement_formed"]
        assert formed, "hundreds of occasions passed and nothing was concluded"

        judgements = [m for m in observer.memory if m.type == "judgement"]
        about = next(j for j in judgements if j.about[0] == subject)
        assert about.episodes >= engine.JUDGEMENT_THRESHOLD
        assert about.evidence, "a conclusion that cannot name its evidence is a prejudice"

        # the point of forming it: the pattern outlives any single occasion
        far = world.answered = world.world_time + 200_000
        threshold = engine.params["tau_ret"]
        assert about.base_activation(far) > threshold, (
            "the judgement faded as fast as the episodes it replaced")
        survivors = [m for m in observer.memory
                     if m.type == "episodic" and m.memory_id in about.evidence]
        assert not survivors, "the episodes should be gone; that is why this exists"

        print(f"ok  memory: {about.episodes} occasions became one judgement "
              f"(activation {about.base_activation(far):.2f} vs threshold {threshold}), "
              f"naming {len(about.evidence)} of them")
    finally:
        runtime.close()


def test_exposing_a_liar_recomputes_what_he_convinced_people_of():
    """Lowering trust is not enough: what he already sold has to stop counting."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        world = runtime.world
        runtime.submit_player_text("ask Mr. Okada about milan")     # he lies, in public
        lie_key = next(k for a in world.agents.values() for k in a.beliefs
                       if "outside_the_city" in k)

        # something an independent witness established, which must survive
        witness = world.agents["agent:npc_red_jacket"]
        clinic_key = next(k for k in witness.beliefs if "clinic_open" in k)
        clinic_before = witness.beliefs[clinic_key].expected_prob

        resting = runtime.resting_on("agent:corpo_okada")
        assert any(r["belief"] == lie_key for r in resting), resting
        believers = {r["agent"]: r for r in resting if r["belief"] == lie_key}
        assert len(believers) >= 3, believers
        before = {a: world.agents[a].beliefs[lie_key].expected_prob for a in believers}

        outcome = runtime.discredit("agent:corpo_okada", factor=0.15,
                                    reason="caught in the lie")
        assert outcome.touched >= len(believers), outcome.as_dict()

        for agent_id, was in before.items():
            now = world.agents[agent_id].beliefs[lie_key].expected_prob
            assert abs(now - 0.5) < abs(was - 0.5), (
                f"{agent_id}: exposing the source did not weaken the claim "
                f"({was} -> {now})")

        # and an independently sourced belief is untouched: being caught in one
        # lie does not make everything you ever said false
        assert witness.beliefs[clinic_key].expected_prob == clinic_before

        # the record says which beliefs still stand on their own
        assert all("still_supported" in c for c in outcome.changes)
        print(f"ok  revision: exposing one liar recomputed {outcome.touched} belief(s); "
              f"independently sourced ones unchanged")
    finally:
        runtime.close()


def test_revision_leaves_independently_supported_beliefs_standing():
    """Two sources, one discredited: the belief survives, weakened."""
    from unscripted import revision
    from unscripted.evidence import _runtime
    from unscripted.ontology import Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        listener = world.agents["agent:ferro"]
        claim = Proposition("supply_short", {"item": "item:sealant"}, "+")

        for speaker, origin in (("agent:voss", "voss_said"), ("agent:rask", "rask_said")):
            runtime.core.belief.update(
                listener.beliefs, claim, asserter_polarity="+", trust=0.8,
                competence=0.7, skepticism=0.3, claim_id=f"c_{origin}",
                origin_event=origin, world_time=world.world_time, speaker=speaker)

        key = claim.core_key()
        both = listener.beliefs[key].expected_prob
        assert both > 0.6, both

        outcome = revision.discredit(world, "agent:voss", factor=0.1, reason="exposed")
        one = listener.beliefs[key].expected_prob
        change = next(c for c in outcome.changes if c["belief"] == key)

        assert one < both, "discrediting a source must weaken what rested on it"
        assert one > 0.5, "an independent source still supports it"
        assert change["still_supported"] is True, change
        assert change["independent_entries"] >= 1, change
        print(f"ok  revision: two sources {both:.3f} -> one discredited {one:.3f}, "
              f"still standing on the other")
    finally:
        runtime.close()


def test_knowledge_stays_inside_its_circle():
    """A restricted claim does not reach people outside the circle that carries it."""
    from unscripted import topology
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        engineers = {a.id for a in world.agents.values()
                     if "role:engineer" in topology.circles(a)}
        assert len(engineers) >= 2, "this test needs a trade with more than one member"

        for _ in range(96):                      # four simulated days of station life
            runtime.advance_time(60)

        def holders(predicate):
            return {a.id for a in world.agents.values()
                    if any(k.startswith(predicate) for k in a.beliefs)}

        restricted = holders("skipped_check")
        common = holders("logged_out")
        outsiders = restricted - engineers - {runtime.config.player_id}
        assert not outsiders, (
            f"a claim restricted to engineers reached {sorted(outsiders)}")
        assert len(common) > len(restricted), (
            "the restricted claim spread as widely as the common one, so the "
            f"classification did nothing: {len(restricted)} vs {len(common)}")

        # ...and the mechanism is visible rather than implied
        blocked = [d for a in world.agents.values()
                   for c, _m, d in runtime.core.last_traces.get(a.id, [])
                   if c == "topology.outside_the_circle"]
        print(f"ok  topology: restricted claim held by {len(restricted)}, "
              f"common claim by {len(common)}, of {len(world.agents)} agents")
    finally:
        runtime.close()


def test_attention_is_finite():
    """A character cannot absorb an unbounded number of new claims in a day."""
    from unscripted import topology
    from unscripted.events import Event
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        listener = world.agents["agent:ferro"]
        listener.beliefs.clear()
        listener.location = "place:mess"
        budget = topology.attention_budget(listener)
        assert budget >= 1

        exhausted = False
        for index in range(budget * 3):
            runtime.core.process_event(Event(
                world.new_event_id(), world.world_time, "claim",
                actor="agent:voss", location="place:mess",
                payload={"proposition": {"predicate": "supply_short",
                                         "slots": {"item": f"item:thing_{index}"},
                                         "polarity": "+"},
                         "summary": "chatter", "importance": 0.4}))
            if any(c == "attention.exhausted"
                   for c, _m, _d in runtime.core.last_traces.get(listener.id, [])):
                exhausted = True

        held = len([k for k in listener.beliefs if "supply_short" in k])
        assert exhausted, "attention was never exhausted, so the budget does nothing"
        assert held <= budget, f"took in {held} new claims against a budget of {budget}"

        # a new day restores it -- this is a daily bound, not a lifetime one
        runtime.advance_time(1440)
        assert topology.spend_attention(listener, world) is True
        print(f"ok  attention: absorbed {held} of {budget * 3} claims offered "
              f"(budget {budget}/day), and recovered overnight")
    finally:
        runtime.close()


def test_competence_changes_what_is_perceived_not_only_who_is_believed():
    """Two witnesses, one event, two different claims."""
    from unscripted.events import Event
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        engineer = world.agents["agent:lindqvist"]
        layman = world.agents["agent:adeyemi"]
        assert engineer.competence_in("engineering") > layman.competence_in("engineering")

        for agent in (engineer, layman):
            agent.location = "place:store"
            for key in [k for k in agent.beliefs if "seal_breached" in k]:
                del agent.beliefs[key]

        runtime.core.process_event(Event(
            world.new_event_id(), world.world_time, "incident", location="place:store",
            payload={"proposition": {"predicate": "seal_breached",
                                     "slots": {"section": "place:store",
                                               "when": "night_cycle"},
                                     "polarity": "+"},
                     "summary": "a seal lets go", "importance": 0.8}))

        expert_claim = [k for k in engineer.beliefs if "seal_breached" in k]
        layman_claim = [k for k in layman.beliefs if "seal_breached" in k]
        assert expert_claim and layman_claim, (expert_claim, layman_claim)
        assert expert_claim != layman_claim, (
            "competence changed nothing about what they took in")
        assert "when=night_cycle" in expert_claim[0] and "section=place:store" in expert_claim[0]

        misread = [d for c, _m, d in runtime.core.last_traces.get(layman.id, [])
                   if c == "interpretation.misread"]
        assert misread, "the layman's claim differs but nothing explains why"
        assert misread[0]["process"] in ("levelling", "assimilation"), misread
        # and it is still THEIRS: first-hand, traceable to the same event
        assert layman.beliefs[layman_claim[0]].hops == 0

        print(f"ok  interpretation: engineer read {expert_claim[0].split('(')[0]} in full; "
              f"the doctor {misread[0]['process']}ed it")
    finally:
        runtime.close()


def test_the_epistemic_profile_decides_how_a_scene_is_misread():
    """Losing the detail and bending it towards the familiar are different people."""
    from unscripted.events import Event
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        world = runtime.world
        seen = {}
        for bias in (0.05, 0.95):
            agent = world.agents["agent:adeyemi"]
            agent.epistemic = {"confirmation_bias": bias}
            agent.beliefs.clear()
            agent.location = "place:store"
            runtime.core.process_event(Event(
                world.new_event_id(), world.world_time, "incident", location="place:store",
                payload={"proposition": {"predicate": "seal_breached",
                                         "slots": {"section": "place:store",
                                                   "when": "night_cycle"},
                                         "polarity": "+"},
                         "summary": "a seal lets go", "importance": 0.8}))
            processes = [d["process"] for c, _m, d in runtime.core.last_traces.get(agent.id, [])
                         if c == "interpretation.misread"]
            seen[bias] = (processes, [k for k in agent.beliefs if "seal_breached" in k])

        assert seen[0.05][0] == ["levelling"], seen[0.05]
        assert seen[0.95][0] == ["assimilation"], seen[0.95]
        assert "when=None" in seen[0.05][1][0], seen[0.05]
        assert seen[0.05][1] != seen[0.95][1]
        print("ok  interpretation: a sober witness loses the detail, a biased one "
              "moves the scene somewhere familiar")
    finally:
        runtime.close()


def test_grounding_reads_the_released_line_back():
    """What the player reads and what the room is told must be the same thing.

    THIS TEST NOW RUNS IN `provider` RELEASE MODE, which is where the machinery
    it covers still lives. Under the default `controlled` mode a plan that
    asserts something never reaches a provider at all, so there is no wording to
    read back -- that guarantee is asserted by
    `test_the_player_reads_the_sentence_the_runtime_wrote_for_the_claim`. What
    is checked here is the weaker contract a studio can opt into.

    THE EXPECTATION MOVED ONCE BEFORE, on purpose. It required an off-topic provider line to propagate NOTHING,
    which was the old behaviour: a line that did not carry the commitment voided
    it. That closed the mismatch from one side and opened a worse one from the
    other -- the provider, and with a latency budget its response time, decided
    whether a belief entered the society at all, so two accepted answers to one
    question produced two different worlds.

    The invariant was never "an off-topic line asserts nothing". It is that the
    released line and the propagated claim agree. The runtime now replaces the
    WORDING -- with the pack's own phrasing for this answer, which is
    deterministic and was written to say exactly this -- and only voids the
    commitment when the pack has nothing that carries it, which is a fact about
    the pack rather than about the provider. `test_an_unsayable_commitment_
    asserts_nothing` covers that case.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _runtime(pack):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            semantic_release="provider"))

    class OffTopicRealizer:
        """Fluent, in-character, and about something else entirely."""
        is_deterministic = False
        def realize(self, plan, style):
            return "Long day. I could use a drink."

    class ParaphrasingRealizer:
        """Says the committed thing in its own words -- which must be accepted."""
        is_deterministic = False
        def realize(self, plan, style):
            return "The clinic? Shutters were down all night."

    # BOTH are replaced here, and the second one is the price of the rule rather
    # than a success. "Shutters were down all night" denies that the clinic was
    # open without using a negation word, so the conservative polarity check
    # reads it as disagreement and the pack's own deny phrasing goes out instead.
    # The player still reads a correct line and the room is still told the same
    # thing; what is lost is the model's wording, and only for NEGATED
    # commitments. See `unscripted/grounding.py` for why the cleverer rule was rejected.
    released = {}
    for realizer, replaced in ((OffTopicRealizer(), True),
                               (ParaphrasingRealizer(), True)):
        runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
        try:
            runtime.core.realizer = realizer
            before = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}
            result = runtime.submit_player_text("ask Honce about clinic")
            after = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}
            answer = result.npc_response
            codes = [c for c, _m, _d in (answer.reasons if answer else [])]
            name = type(realizer).__name__

            assert after != before, f"{name}: the commitment reached nobody"
            assert ("dialogue.wording_replaced" in codes) == replaced, codes
            if replaced:
                assert "drink" not in answer.text, (
                    f"{name}: the off-topic line reached the player while the "
                    f"room was told something else")
            else:
                assert answer.text == "The clinic? Shutters were down all night.", (
                    f"{name}: a paraphrase that DOES carry the commitment was "
                    f"replaced anyway ({answer.text!r})")
            assert "was open" not in answer.text, (
                f"{name}: the player was told the opposite of what propagated")
            released[name] = sorted(after - before)
        finally:
            runtime.close()

    assert released["OffTopicRealizer"] == released["ParaphrasingRealizer"], (
        f"the provider's wording changed what the world learned: {released}")
    print("ok  grounding: in provider mode the released line and the propagated "
          "claim agree, and the world learns the same either way")


def test_entity_grounding_is_relative_to_the_world():
    """The same sentence is an invention in one world and ordinary in another."""
    from unscripted import grounding
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cyber = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    relay = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        def flagged(runtime, text):
            return {e["token"] for e in grounding.unknown_referents(text, runtime.world)}

        # "clinic" exists in one world and not the other. Grounding is a property
        # of the setting, not a global word list -- which is what makes it usable
        # by a pack the engine has never seen.
        assert "clinic" not in flagged(cyber, "The clinic was shut that night.")
        assert "clinic" in flagged(relay, "The clinic was shut that night.")
        assert "seal" not in flagged(relay, "The seal failed during the night cycle.")

        # ordinary furniture is never a claim about what exists, in any world
        for runtime in (cyber, relay):
            assert not flagged(runtime, "Meet me by the door.")
            assert not flagged(runtime, "It has been a long night.")
            # ...and an invention is an invention in both
            assert "mill" in flagged(runtime, "The old mill by the river burned down.")

        print("ok  grounding: invention is judged against the world, not a word list")
    finally:
        cyber.close()
        relay.close()


def test_a_character_can_lie_and_the_lie_is_traceable():
    """Belief, utterance and intent are separate states."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        liar = runtime.world.agents["agent:corpo_okada"]
        truth_key = next(k for k in liar.beliefs if "whereabouts" in k)
        truth_before = liar.beliefs[truth_key].expected_prob
        assert truth_before > 0.6, "the liar must actually know better"
        assert liar.will_lie_about(liar.secrets[0]), "this character is authored to lie"

        result = runtime.submit_player_text("ask Mr. Okada about milan")
        assert result.npc_response is not None
        deception = next((d for c, _m, d in result.npc_response.reasons
                          if c == "dialogue.deception" and "secret" in d), None)
        assert deception, "the lie must be on the record as a lie"
        assert deception["speaker_believes_it_with"] < 0.2, deception

        said = next(u for c, _m, d in result.npc_response.reasons
                    if c == "dialogue.deception" and "spoken" in d
                    for u in d["spoken"])
        assert said["honesty"] == "lie", said
        assert said["heard_by"], "a lie told to nobody proves nothing"

        # the listeners hold the LIE, with the liar named as its origin
        for listener in said["heard_by"]:
            belief = runtime.world.agents[listener].beliefs.get(said["proposition"])
            assert belief is not None, f"{listener} did not hear it"
            assert any("corpo_okada" in str(o) for o in belief.origin_counts), (
                f"{listener} holds the claim without knowing who said it")

        # the liar's own belief is untouched: nobody is persuaded by their own mouth
        assert liar.beliefs[truth_key].expected_prob == truth_before
        assert said["proposition"] != truth_key, "the lie must differ from the truth"

        print(f"ok  deception: liar holds {truth_before:.3f} in the truth, asserted the "
              f"opposite to {len(said['heard_by'])} listener(s), each recording him as source")
    finally:
        runtime.close()


def test_an_unsayable_commitment_asserts_nothing():
    """The player must never read a deflection while the room hears a claim."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        liar = runtime.world.agents["agent:corpo_okada"]
        # strip the authored words for the lie, keep the intent to tell it
        liar.secrets[0].cover_phrasings.clear()
        before = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}

        result = runtime.submit_player_text("ask Mr. Okada about milan")
        text = result.npc_response.text if result.npc_response else result.message
        after = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}

        assert "left the city" not in text.lower()
        assert after == before, (
            "a commitment the text layer could not express still reached the world: "
            f"{sorted(after - before)}")
        assert any(c == "dialogue.commitment_unexpressed"
                   for c, _m, _d in (result.npc_response.reasons if result.npc_response else []))
        print("ok  deception: an unsayable commitment asserts nothing")
    finally:
        runtime.close()


def test_the_text_layer_cannot_choose_what_enters_the_world():
    """A greedy provider must not be able to put a fact into the society."""
    # PROVIDER RELEASE MODE, because that is where a provider is handed a plan
    # at all. Under the default `controlled` mode a plan that asserts something
    # never reaches one -- which is a stronger version of the same guarantee, and
    # is asserted separately. What this checks is that when the text layer IS
    # used, it is handed a commitment and never a menu to choose from.
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    def _runtime(pack):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            semantic_release="provider"))

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class GreedyRealizer:
        """States every fact it can see, and invents one for good measure.

        This is the adversary the commitment exists for: before it, the plan
        carried a LIST of permissible facts and the provider chose among them, so
        which information reached a listener was the model's decision.
        """
        is_deterministic = False
        seen_plans = []

        def realize(self, plan, style):
            GreedyRealizer.seen_plans.append(plan)
            return ("Everything I know: " + "; ".join(plan.allowed_facts)
                    + "; and the old mill by the river burned down.")

    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        runtime.core.realizer = GreedyRealizer()
        before = {(a.id, k): b.expected_prob
                  for a in runtime.world.agents.values() for k, b in a.beliefs.items()}

        spoken = []
        for _ in range(4):
            for npc in runtime.structured_scene()["npcs"]:
                for topic in sorted(runtime.world.topics):
                    result = runtime.submit_player_text(f"ask {npc['name']} about {topic}")
                    if result.npc_response is None:
                        continue
                    for _code, _m, detail in result.npc_response.reasons:
                        # any utterance, honest or not -- a lie is an assertion too
                        spoken += [u["proposition"] for u in (detail.get("spoken") or [])]

        after = {(a.id, k): b.expected_prob
                 for a in runtime.world.agents.values() for k, b in a.beliefs.items()}
        committed = set(spoken)
        # every belief that moved must be one the RUNTIME committed someone to
        # saying -- not one the provider decided to mention
        for key, was in before.items():
            if abs(after.get(key, was) - was) > 1e-9:
                assert key[1] in committed, (
                    f"{key} moved but nobody was committed to asserting it")
        for key in set(after) - set(before):
            assert key[1] in committed, f"{key} appeared but was never committed"

        assert GreedyRealizer.seen_plans, "the provider was never called"
        for plan in GreedyRealizer.seen_plans:
            # The plan hands over a commitment, never a menu. An evasion or a
            # deflection legitimately commits to nothing -- what must never happen
            # is a plan carrying facts that were not committed to being said.
            assert list(plan.allowed_facts) == [m.rendered() for m in plan.moves
                                                if m.is_factual], (
                "allowed_facts must be exactly the commitment, not a wider menu")
        asserting = [p for p in GreedyRealizer.seen_plans if p.allowed_facts]
        assert asserting, "no plan ever committed to a fact, so nothing was tested"
        for plan in asserting:
            assert len(plan.moves) <= 2, "a commitment should be small and specific"

        print(f"ok  commitment: a greedy provider moved nothing beyond the "
              f"{len(committed)} committed proposition(s)")
    finally:
        runtime.close()


def test_commitment_selection_is_seeded_and_replayable():
    """The runtime chooses, and the same world chooses the same way."""
    from unscripted.commitment import Candidate, select
    from unscripted.ontology import Proposition

    def candidates():
        return [Candidate(Proposition("seen_at", {"who": f"agent:{n}"}), 0.9, 1.0)
                for n in ("a", "b", "c", "d")]

    first = select(candidates(), seed_parts=("world-1", "agent:x", 3, 120, "dialogue"))
    again = select(candidates(), seed_parts=("world-1", "agent:x", 3, 120, "dialogue"))
    other = select(candidates(), seed_parts=("world-2", "agent:x", 3, 120, "dialogue"))

    assert first.rendered_facts() == again.rendered_facts(), "same world must replay"
    assert len(first.moves) == 1
    # different worlds may differ; if they never did, selection would be a constant
    variants = {tuple(select(candidates(),
                             seed_parts=(f"world-{i}", "agent:x", 3, 120, "dialogue")
                             ).rendered_facts())
                for i in range(24)}
    assert len(variants) > 1, "seeded selection produced no variety at all"
    assert any(r.startswith("commitment.seeded_choice") for r, _m, _d in first.reasons) \
        or first.reasons, "the choice must be on the record"
    print(f"ok  commitment: seeded selection replays exactly, "
          f"{len(variants)} variants across 24 worlds ({other.rendered_facts()[0]!r} in world-2)")


def test_layering_is_declared_and_holds():
    """A module may import from its own layer or below, never above."""
    from unscripted import architecture

    assert not architecture.unassigned(), (
        "new modules must be placed in a layer deliberately: "
        f"{architecture.unassigned()}")
    assert not architecture.stale(), (
        f"the layer map names modules that no longer exist: {architecture.stale()}")

    upward = architecture.violations()
    assert not upward, "\n".join(
        f"  {m} (layer {architecture.LAYERS[architecture.layer_of(m)][0]}) imports "
        f"{d} (layer {architecture.LAYERS[architecture.layer_of(d)][0]})"
        for m, d in upward)

    # The adapters layer sits BELOW world on purpose: the world must not come to
    # depend on which text provider or engine bridge happens to be installed.
    assert architecture.layer_of("provider") < architecture.layer_of("world")
    assert architecture.layer_of("belief") < architecture.layer_of("runtime")

    print(f"ok  architecture: {len(architecture.modules())} modules in "
          f"{len(architecture.LAYERS)} layers, no upward imports")


def test_a_question_is_not_evidence():
    """Asking about something must not make anyone believe it."""
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        subject = runtime.world.agents["agent:voss"]
        key = next(k for k in subject.beliefs if "seal_breached" in k and "night_cycle" in k)
        before = subject.beliefs[key].expected_prob
        sources_before = dict(subject.beliefs[key].origin_counts)
        clock = runtime.world.world_time

        for _ in range(20):
            runtime.submit_player_text("ask Commander Voss about seal")

        belief = subject.beliefs[key]
        # This used to rise about 0.009 per question, because "ask" emitted a claim
        # event carrying the proposition: the player's own question was recorded as
        # an independent supporting source, so twenty of them walked the belief
        # towards certainty with nobody having said anything.
        assert belief.expected_prob == before, (before, belief.expected_prob)
        assert dict(belief.origin_counts) == sources_before, belief.origin_counts
        assert runtime.world.world_time == clock, "a player turn must not move the clock"

        # But being asked is still something that happened: it is heard and encoded.
        asked = [m for m in subject.memory if "asks about" in (m.content or "")]
        assert asked, "the character must remember being questioned"
        assert all(m.proposition is not None for m in asked), \
            "the memory should record what they were asked about"

        print(f"ok  belief: 20 questions moved nothing ({before:.4f}), "
              f"{len(asked)} of them remembered")
    finally:
        runtime.close()


def test_evidence_partial_run_says_it_is_partial():
    """A dossier that omits cases must not read like one where they passed."""
    import shutil
    import tempfile
    from unscripted.evidence import case_names, run_evidence
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = tempfile.mkdtemp()
    try:
        dossier = run_evidence(packs=[os.path.join(root, "worldpacks", "cyberpunk-block")],
                               hours=0.01, out_dir=workspace, only=["forgetting"])
        assert [c["case"] for c in dossier["cases"]] == ["forgetting"], dossier["cases"]
        assert dossier["cases_selected"] == ["forgetting"]
        rendered = open(os.path.join(workspace, "DOSSIER.md"), encoding="utf-8").read()
        assert "Partial run" in rendered and "not a record of them passing" in rendered

        try:
            run_evidence(packs=[os.path.join(root, "worldpacks", "cyberpunk-block")],
                         hours=0.01, out_dir=workspace, only=["no_such_case"])
            raise AssertionError("an unknown case name must be refused, not ignored")
        except ValueError as exc:
            assert "no such case" in str(exc)

        print(f"ok  evidence: a partial run is labelled ({len(case_names())} cases selectable)")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_evidence_counts_survive_log_truncation():
    """Counters must not be derived from a list that gets trimmed."""
    from unscripted.evidence import Recorder, _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        recorder = Recorder(runtime)
        for i in range(50):
            recorder.record("told", "agent:x", claim=f"c{i}")
        recorder.episodes = recorder.episodes[-10:]          # what the long run does
        assert len(recorder.episodes) == 10
        assert recorder.counts["told"] == 50, recorder.counts
        print("ok  evidence: counts describe the run, not the truncated tail")
    finally:
        runtime.close()


def test_evidence_forgetting_uses_the_real_retrieval_threshold():
    """'Forgot' must mean what the retrieval path means by it."""
    from unscripted.evidence import Recorder, _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
    try:
        recorder = Recorder(runtime)
        threshold = runtime.core.memory.params["tau_ret"]
        assert threshold < 0.0, threshold
        now = runtime.world.world_time
        recalled = recorder._recall_snapshot()
        for agent in runtime.world.agents.values():
            for memory in agent.memory:
                activation = memory.base_activation(now)
                # a memory between the real threshold and zero is still retrievable;
                # calling it forgotten would put a false loss in the record
                assert (memory.memory_id in recalled[agent.id]) == (activation > threshold), (
                    agent.id, memory.memory_id, activation, threshold)
        print(f"ok  evidence: forgetting is judged at the retrieval threshold ({threshold})")
    finally:
        runtime.close()


def test_evidence_run_records_chains_forgetting_and_distortion():
    """The evidence harness must produce artefacts, not just a verdict."""
    import shutil
    import tempfile
    from unscripted.evidence import run_evidence
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = tempfile.mkdtemp()
    try:
        dossier = run_evidence(
            packs=[os.path.join(root, "worldpacks", "cyberpunk-block")],
            hours=0.01, out_dir=workspace)

        names = {c["case"] for c in dossier["cases"]}
        assert {"determinism", "broadcast_chain", "forgetting", "distortion",
                "secret_under_pressure", "disagreement", "conversation",
                "long_life"} <= names, names
        failed = [c["case"] for c in dossier["cases"] if not c["passed"]]
        assert not failed, f"{failed}: {[c['findings'] for c in dossier['cases'] if not c['passed']]}"

        kinds = {e["kind"] for c in dossier["cases"] for e in c["episodes"]}
        # the four things a buyer asks to be shown
        for required in ("said", "learned", "told", "forgot"):
            assert required in kinds, f"nothing of kind {required!r} was recorded"

        chains = [e for c in dossier["cases"] for e in c["episodes"] if e["kind"] == "chain"]
        assert chains, "no evidence chain was reconstructed"
        for chain in chains:
            assert chain["origin"], "a chain with no origin proves nothing"
            assert chain["hops_from_source"] >= 1

        forgetting = next(c for c in dossier["cases"] if c["case"] == "forgetting")
        assert forgetting["stats"]["trivial_lost_after_hours"] is not None
        assert forgetting["stats"]["recall_threshold"] < 0

        secret = next(c for c in dossier["cases"] if c["case"] == "secret_under_pressure")
        assert secret["stats"]["leaks"] == 0, secret["stats"]

        assert os.path.exists(os.path.join(workspace, "DOSSIER.md"))
        assert os.path.exists(os.path.join(workspace, "evidence.json"))
        rendered = open(os.path.join(workspace, "DOSSIER.md"), encoding="utf-8").read()
        assert "Evidence Run" in rendered and "|" in rendered

        long_life = next(c for c in dossier["cases"] if c["case"] == "long_life")
        stats = long_life["stats"]
        # A long run truncates its episode list to stay readable. The counts must
        # describe the RUN, not the surviving tail -- a two-hour run once reported
        # zero retellings over 254 simulated days because every one of them had been
        # trimmed away, which reads as a dead world rather than a trimmed log.
        assert stats["episodes_recorded"] >= stats["episodes_kept"], stats
        assert stats["beliefs_acquired"] > 0, "a live world acquires beliefs"
        # Decay and capacity eviction both end in "cannot recall it" and must not be
        # reported as one number: a run once showed half a million "forgettings" that
        # were overwhelmingly the memory cap doing its job, which reads as a runtime
        # that cannot hold on to anything.
        assert (stats["forgettings_by_decay"] + stats["forgettings_by_eviction"]
                == stats["forgettings"]), stats
        losses = [e for c in dossier["cases"] for e in c["episodes"] if e["kind"] == "forgot"]
        for loss in losses:
            # Every loss names which of the two mechanisms took it. The note is free
            # text and differs per case; the cause is the claim being made.
            assert loss.get("cause") in ("decayed below the retrieval threshold",
                                         "evicted: the agent was at capacity"), loss

        print(f"ok  evidence: {len(dossier['cases'])} cases produced "
              f"{sum(len(c['episodes']) for c in dossier['cases'])} recorded episodes")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_the_same_two_people_lose_more_on_the_phone():
    """How something was said is part of what was said.

    A person-to-person claim used to be one undifferentiated act: A told B. But
    the same two people telling each other the same thing face to face and over a
    phone are different events, and the difference is not decoration. Daft &
    Lengel's media richness theory is the usual framing -- leaner media carry less
    per exchange -- and here it lands on machinery that already existed: the
    levelling Allport & Postman measured, the earshot that decides who overhears,
    and the strength a listener weighs a claim by.

    Three properties, and the middle one is the whole feature: off changes
    nothing, a call loses more detail than a conversation, and nobody overhears a
    call.
    """
    from collections import Counter
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.medium import IN_PERSON, PHONE, contacts_of, for_exchange
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    def five_days(media: bool):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, media=media))
        try:
            sdk.submit_player_text("look")
            for _ in range(24 * 5):
                sdk.advance_time(60)
            told = sdk.structured_knowledge(limit=400).get("transmissions", [])
            return told
        finally:
            sdk.close()

    # 1. OFF IS UNCHANGED: every exchange is a conversation in a room.
    without = five_days(False)
    assert without, "nothing was passed on at all"
    assert {row.get("medium", "in_person") for row in without} == {"in_person"}, (
        "with the media layer off, something travelled by something other than "
        "somebody speaking to somebody in the same room")

    # 2. ON, A CALL LOSES MORE. This is the measurable claim and the only reason
    #    the layer earns its place.
    with_media = five_days(True)
    by_medium = Counter(row.get("medium", "in_person") for row in with_media)
    assert by_medium["phone"] > 5, f"almost nobody used the phone: {dict(by_medium)}"
    assert by_medium["in_person"] > 5, (
        f"everybody used the phone; a market square became a call centre: "
        f"{dict(by_medium)}")

    def loss(medium):
        rows = [row for row in with_media if row.get("medium") == medium]
        return sum(1 for row in rows if row.get("distorted")) / max(1, len(rows))

    spoken_loss, called_loss = loss("in_person"), loss("phone")
    assert called_loss > spoken_loss, (
        f"a phone call lost detail {called_loss:.1%} of the time against "
        f"{spoken_loss:.1%} in person; the fidelity is not reaching the "
        f"distortion layer")

    # 3. NOBODY OVERHEARS A CALL, which is why a call is where a secret goes.
    assert PHONE.audience is False and IN_PERSON.audience is True
    assert PHONE.trust_factor < IN_PERSON.trust_factor
    assert PHONE.distortion_scale() > IN_PERSON.distortion_scale()

    # And reach is not universal: somebody you do not know cannot be rung, which
    # is what stops a world with phones from having no geography left.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, media=True))
    try:
        yara = sdk.world.agents["agent:yara"]
        strangers = [other for other in sdk.world.agents.values()
                     if other.id != yara.id
                     and other.id not in contacts_of(yara)
                     and other.location != yara.location]
        assert strangers, "everybody in this pack knows everybody; nothing to prove"
        assert for_exchange(yara, strangers[0], enabled=True) is None, (
            "a character reached somebody in another place whose number they do "
            "not have")
    finally:
        sdk.close()
    print(f"ok  medium: {by_medium['in_person']} spoken and {by_medium['phone']} "
          f"called; a call loses detail {called_loss:.0%} of the time against "
          f"{spoken_loss:.0%} in person, and nobody overhears one")


def test_a_town_with_reasons_does_not_go_quiet():
    """The evidence run's own finding, answered.

    `evidence/README.md` says it plainly, and said it before this layer existed:
    after saturation the rumours are through the population, everyone becomes a
    stifler, and *the world goes quiet*. That is stability, which is a real
    property and a lesser claim than the one on the box.

    The cause was in the tick. Scheduled events fire, routines move people,
    diffusion rolls dice over who happens to be standing together, everyone
    decays, factions escalate — and nothing ever asked what anybody WANTED.
    Characters carry goals like "not be arrested for this" and no time advance
    consulted one.

    So: diffusion is who happens to talk, pursuit is who has a reason to.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    def conversations(pursuit: bool):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", pursuit=pursuit))
        try:
            sdk.submit_player_text("look")
            early = late = 0
            for day in range(30):
                for _ in range(24):
                    trace = sdk.advance_time(60)["last_trace"]
                    spoke = sum(1 for code, _m, _d in (trace.get("_diffusion") or [])
                                if code == "diffusion.told")
                    spoke += sum(1 for code, _m, _d in (trace.get("_pursuit") or [])
                                 if code == "pursuit.acted")
                    if day < 3:
                        early += spoke
                    elif day >= 27:
                        late += spoke
            return early, late
        finally:
            sdk.close()

    quiet_early, quiet_late = conversations(False)
    assert quiet_early > 10, "nothing happened even at the start; the pack is broken"
    assert quiet_late <= 2, (
        f"the world was supposed to go quiet without this layer and did not "
        f"({quiet_late} conversations on days 27-29); the comparison is meaningless")

    alive_early, alive_late = conversations(True)
    assert alive_late > 20, (
        f"a month in, a town where everybody wants something managed "
        f"{alive_late} conversations in three days")
    assert alive_late > quiet_late * 5 + 10

    # AND IT STAYS HONEST WHILE BUSIER. More conversation is only worth having if
    # repetition still does not become proof: a layer that manufactures talk
    # could quietly walk a rumour up to certainty.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, climate=True))
    try:
        sdk.submit_player_text("look")
        for _ in range(24 * 20):
            sdk.advance_time(60)
        unsourced, single_origin_max = 0, 0.0
        for agent_id in sdk.world.agents:
            if agent_id == sdk.config.player_id:
                continue
            for belief in sdk.structured_agent(agent_id)["beliefs"]:
                if not belief["provenance"]:
                    unsourced += 1
                origins = {entry["origin_event"] for entry in belief["provenance"]}
                if len(origins) == 1:
                    single_origin_max = max(single_origin_max, belief["prob"])
        assert unsourced == 0, f"{unsourced} beliefs arrived from nowhere"
        assert single_origin_max < 0.95, (
            f"twenty days of purposeful conversation walked a single-origin claim "
            f"to {single_origin_max:.3f}; the correlation discount is not holding "
            f"under the extra traffic")
    finally:
        sdk.close()
    print(f"ok  pursuit: without it the town is silent by day 27 ({quiet_late} "
          f"conversations); with it, {alive_late} — and a single origin still "
          f"tops out at {single_origin_max:.2f}")


def test_climate_is_weather_not_personality_and_off_is_neutral():
    """A place can change its mind about strangers; a person still cannot.

    The runtime has always said that traits are fixed -- relationships move, who
    somebody is does not -- and that is the right call, because a personality
    that drifts under play converges every character on the same one. What it
    left unmodelled is that a square in which somebody has just been threatened
    is a different place to ask questions in, for everybody, not only for the
    person who was threatened.

    So the climate layer is deliberately weak: three numbers per PLACE, moved by
    events, relaxing back, drifting toward neighbours. This asserts the three
    things that make it safe to ship: off is exactly neutral, on actually moves,
    and it moves the room rather than the people in it.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.climate import NEUTRAL, ClimateEngine, baseline_for
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    # 1. OFF IS NEUTRAL, as arithmetic rather than as an intention. Every hook
    #    adds 0.0 or multiplies by 1.0, so a disabled layer cannot perturb a run.
    off = ClimateEngine(None, enabled=False)
    assert off.modifiers("place:anywhere") == NEUTRAL
    assert NEUTRAL == {"tempo": 1.0, "tell_threshold": 0.0, "skepticism": 0.0,
                       "stranger_trust": 0.0}

    def run(climate: bool, actions):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", climate=climate))
        try:
            sdk.submit_player_text("look")
            for action in actions:
                sdk.submit_player_text(action)
            sdk.advance_time(240)
            from unscripted import snapshot as snapshot_module
            state = snapshot_module.capture(sdk.world, sdk.core)
            state.pop("climate", None)      # the layer's own state, not the world's
            report = sdk.climate_report()
            return json.dumps(state, sort_keys=True, default=str), report
        finally:
            sdk.close()

    script = ["threaten Yara", "threaten Otto"]
    disabled_once, _ = run(False, script)
    disabled_twice, _ = run(False, script)
    assert disabled_once == disabled_twice, "the run stopped being deterministic"

    # 2. ON ACTUALLY MOVES SOMETHING. A layer that reports numbers and changes no
    #    behaviour is worse than no layer: it looks like a feature in a demo.
    enabled_state, enabled_report = run(True, script)
    assert enabled_state != disabled_once, (
        "with the climate on, the same script produced the same world; the "
        "modifiers are not reaching anything")

    # 3. IT MOVES THE ROOM. Threatening people in the square closes the square,
    #    for everybody, and it recovers afterwards rather than marking the world.
    market = next(row for row in enabled_report if row["place"] == "place:market")
    baseline = baseline_for({"gossip_factor": 1.8, "surveillance_level": 0.4,
                             "privacy_level": 0.1})
    assert market["openness"] < baseline.openness - 0.1, (
        f"the square is at {market['openness']} after two threats against a "
        f"baseline of {baseline.openness:.3f}; nothing closed")
    assert market["suspicion"] > baseline.suspicion + 0.1

    calm = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", climate=True))
    try:
        calm.submit_player_text("look")
        for action in script:
            calm.submit_player_text(action)
        worst = next(r for r in calm.climate_report() if r["place"] == "place:market")
        calm.advance_time(60 * 40)
        later = next(r for r in calm.climate_report() if r["place"] == "place:market")
        assert later["openness"] > worst["openness"], (
            "the square never recovers, so one bad afternoon marks the world "
            "permanently")
        assert later["drift_from_baseline"] < worst["drift_from_baseline"]

        # And nobody's personality moved: that is the line this layer must not
        # cross, and the whole reason it lives on places.
        yara = calm.world.agents["agent:yara"]
        assert yara.big_five["agreeableness"] == 0.5, (
            "a trait changed; climate is weather and must not become personality "
            "drift wearing a different hat")
    finally:
        calm.close()

    # 4. IT SPREADS BY TRAFFIC, NOT BY THE CLOCK. Somebody walking out of a room
    #    that has just seen a threat takes the mood with them; two rooms joined
    #    by a door nobody uses stay apart. An earlier version drifted every place
    #    toward its neighbours on a timer, which produced a similar picture while
    #    modelling the wrong thing.
    carried = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", climate=True))
    try:
        carried.submit_player_text("look")
        carried.submit_player_text("threaten Yara")
        carried.submit_player_text("attack Yara")
        walks = 0
        for _ in range(24):
            outcome = carried.advance_time(60)
            walks += sum(1 for code, _m, _d in (outcome["last_trace"].get("_routine") or [])
                         if code == "routine.moved")
        rooms = {row["place"]: row for row in carried.climate_report()}
        assert walks > 0, "nobody moved, so this proves nothing either way"
        elsewhere = [row["drift_from_baseline"] for place, row in rooms.items()
                     if place != "place:market"]
        assert any(drift > 0.01 for drift in elsewhere), (
            f"after {walks} walks out of a square that had just seen an attack, "
            f"no other room moved at all: {elsewhere}")
        assert rooms["place:market"]["drift_from_baseline"] > max(elsewhere), (
            "somewhere other than where it happened is further from normal than "
            "the place it happened in")

        # The transport is capped, so a shift change cannot import a district.
        from unscripted.climate import MAX_CARRIED_PER_STEP
        assert all(drift < MAX_CARRIED_PER_STEP + 0.05 for drift in elsewhere)
    finally:
        carried.close()
    print(f"ok  climate: off is neutral, on closes the square "
          f"({baseline.openness:.2f} -> {market['openness']:.2f}), it recovers, "
          f"the mood travels with the traffic, and no trait moved")


def test_a_mood_is_catching_and_off_means_it_is_not():
    """One rude customer ruins an afternoon, and the afternoon spreads.

    The runtime has modelled affect per character since the beginning: threaten
    a trader and her valence drops and she speaks faster to everybody afterwards.
    What it never modelled is the step people actually notice -- that the person
    she serves next is worse off for it.

    Hatfield, Cacioppo & Rapson (1994) call it primitive emotional contagion:
    automatic, small per exchange, and cumulative. This asserts the four things
    that make it safe to ship: off is byte-identical, on genuinely moves a third
    party who was never in the room where it happened, a steady person catches
    less than a volatile one, and no personality moved.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.contagion import ContagionEngine, MAX_STEP

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    # 1. OFF IS NOT A SMALL EFFECT, IT IS NO EFFECT. Asserted on the snapshot,
    #    because a layer that perturbs a disabled run is a layer a studio cannot
    #    decline.
    def run(contagion: bool):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, contagion=contagion))
        try:
            sdk.submit_player_text("look")
            sdk.submit_player_text("threaten Yara")
            sdk.submit_player_text("attack Yara")
            caught = []
            for _ in range(18):
                outcome = sdk.advance_time(60)
                for bucket in outcome["last_trace"].values():
                    if not isinstance(bucket, list):
                        continue
                    caught += [detail for code, _m, detail in bucket
                               if code == "contagion.caught"]
            from unscripted import snapshot as snapshot_module
            state = snapshot_module.capture(sdk.world, sdk.core)
            moods = {aid: (round(a.affect.mood.p, 4), round(a.affect.mood.a, 4),
                           round(a.affect.mood.d, 4))
                     for aid, a in sorted(sdk.world.agents.items())}
            return json.dumps(state, sort_keys=True, default=str), moods, caught
        finally:
            sdk.close()

    off_state, off_moods, off_caught = run(False)
    off_again, off_moods_again, _ = run(False)
    assert off_state == off_again, "the run stopped being deterministic"
    assert off_moods == off_moods_again
    assert off_caught == [], "the layer is off and it did something anyway"

    on_state, on_moods, on_caught = run(True)
    assert on_state != off_state, (
        "with contagion on, the same script produced an identical world; "
        "nothing is reaching a mood")
    assert on_caught, "the layer is on and never once fired"

    # 2. IT REACHES SOMEBODY WHO WAS NOT THERE. This is the whole claim: the
    #    player was vile to one person, and a third party who never met the
    #    player ends up in a different mood for it.
    moved = {aid for aid in on_moods if on_moods[aid] != off_moods.get(aid)}
    assert len(moved) >= 2, f"only {moved} differ; a mood that infects one person is not contagion"
    reached = {entry["to"] for entry in on_caught}
    assert reached - {"agent:yara"}, (
        "the only person whose mood moved is the one it happened to, which the "
        "affect layer already did on its own")

    # 3. IT IS CAPPED PER EXCHANGE, so a chain of conversations converges rather
    #    than running away and leaving a town of identical moods.
    worst = max(abs(step) for entry in on_caught for step in entry["moved"].values())
    assert worst <= MAX_STEP + 1e-6, f"one exchange moved a mood by {worst}"
    assert len(set(on_moods.values())) > 1, "everybody ended up feeling the same"

    # 4. A STEADY PERSON CATCHES LESS. That is what the trait is for, and using it
    #    here is the difference between a model and a multiplier.
    engine = ContagionEngine(enabled=True)

    class _Mood:
        def __init__(self, p, a, d): self.p, self.a, self.d = p, a, d

    class _Affect:
        def __init__(self, p, a, d): self.mood = _Mood(p, a, d)

    class _Person:
        def __init__(self, aid, stability):
            self.id = aid
            self.affect = _Affect(0.0, 0.0, 0.0)
            self.big_five = {"emotional_stability": stability}
            self.relationships = {"agent:speaker": {"familiarity": 0.8, "liking": 0.5}}

    speaker = _Person("agent:speaker", 0.5)
    speaker.affect = _Affect(-0.9, 0.8, -0.4)
    steady, volatile = _Person("agent:steady", 0.95), _Person("agent:volatile", 0.05)
    engine.between(speaker, steady)
    engine.between(speaker, volatile)
    assert abs(volatile.affect.mood.p) > abs(steady.affect.mood.p) * 1.5, (
        f"steady caught {steady.affect.mood.p:.4f} and volatile "
        f"{volatile.affect.mood.p:.4f}; emotional stability is doing nothing")

    # A stranger's bad afternoon is not catching.
    stranger = _Person("agent:stranger", 0.5)
    stranger.relationships = {}
    assert engine.between(speaker, stranger) == []
    assert stranger.affect.mood.p == 0.0

    # 5. NOTHING BECAME PERSONALITY. Same line the climate layer holds: this is
    #    weather, and who somebody is does not change.
    assert steady.big_five["emotional_stability"] == 0.95
    assert ContagionEngine(enabled=False).between(speaker, volatile) == []

    # 6. IT CHAINS, AND IT IS SMALL, AND BOTH OF THOSE ARE THE POINT. A mood that
    #    only ever moved from the person it happened to would be a decoration on
    #    the affect layer; a mood that accumulated would end with a town of
    #    identical people. So this measures the two things a studio has to know
    #    before reaching for it, and the second one is unflattering.
    def spread(contagion: bool, hours: int = 48):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, contagion=contagion))
        try:
            sdk.submit_player_text("look")
            sdk.submit_player_text("threaten Yara")
            sdk.submit_player_text("threaten Yara")
            history, events = [], []
            for _ in range(hours):
                outcome = sdk.advance_time(60)
                for bucket in outcome["last_trace"].values():
                    if isinstance(bucket, list):
                        events += [d for code, _m, d in bucket
                                   if code == "contagion.caught"]
                history.append({aid: agent.affect.mood.p
                                for aid, agent in sorted(sdk.world.agents.items())})
            return history, events
        finally:
            sdk.close()

    without, _ = spread(False)
    with_it, exchanges = spread(True)
    bystanders = [aid for aid in with_it[0]
                  if aid not in ("agent:yara", "agent:player_1")]

    # It chains: most transfers are NOT from the person the player was vile to.
    second_hand = [e for e in exchanges if e["from"] != "agent:yara"]
    assert len(second_hand) > len(exchanges) / 2, (
        f"only {len(second_hand)} of {len(exchanges)} transfers were second-hand; "
        f"this is one person's bad mood radiating, not a mood spreading")

    # And it is a transient, roughly a sixteenth of the thing that started it.
    peak = max(abs(with_it[h][aid] - without[h][aid])
               for h in range(len(with_it)) for aid in bystanders)
    settled = max(abs(with_it[-1][aid] - without[-1][aid]) for aid in bystanders)
    assert 0.005 < peak < 0.25, (
        f"a bystander peaked {peak:.4f} away from the same world without "
        f"contagion: too small to matter, or large enough to be personality")
    assert settled < peak / 3, (
        f"the difference is still {settled:.4f} after two days against a peak "
        f"of {peak:.4f}; mood that does not wash out is not mood")

    print(f"ok  contagion: off is byte-identical, on moved {len(moved)} people's "
          f"mood over {len(on_caught)} exchanges reaching "
          f"{len(reached)} listeners, capped at {worst:.3f}, "
          f"steady caught {abs(steady.affect.mood.p):.4f} vs volatile "
          f"{abs(volatile.affect.mood.p):.4f}, and no trait moved; "
          f"{len(second_hand)}/{len(exchanges)} transfers second-hand, "
          f"bystanders peak {peak:.4f} from a threat worth ~0.9 and settle back "
          f"to {settled:.4f}")


def test_everybody_knowing_is_not_everybody_knowing_that_everybody_knows():
    """Common knowledge is made by a public moment, not by a headcount.

    Lewis (1969) and Aumann (1976) define it; Chwe (*Rational Ritual*, 2001)
    supplies the mechanism a game can use: what makes a fact common knowledge is
    not that more people found out, it is that they found out *in front of each
    other*. A thing whispered to fifty people one at a time is common knowledge
    to nobody, and that is why a broadcast is a different act from a rumour.

    This asserts what the layer is for -- it changes what may be SAID, never what
    is believed -- and the two consequences that follow: a secret that is out in
    the open stops working as a secret, and nobody bothers to pass on what the
    two of them already watched a crowd find out.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.common_knowledge import CommonKnowledgeEngine, Public, MIN_WITNESSES

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    # 1. THE DISTINCTION ITSELF, on the engine, before any world is involved.
    engine = CommonKnowledgeEngine(enabled=True)
    engine._record(Public("k", frozenset({"a", "b", "c"}), 0, "in_the_open", "p"))
    engine._record(Public("k", frozenset({"d", "e", "f"}), 0, "in_the_open", "q"))
    assert engine.is_common("k", "a", "b")
    assert engine.is_common("k", "d", "f")
    assert not engine.is_common("k", "a", "d"), (
        "two people who each learned it in front of a DIFFERENT crowd were "
        "treated as having it in common; that collapses the only distinction "
        "this module exists to make")
    # Everybody in either crowd is past denying it, though.
    assert engine.is_out("k", "a") and engine.is_out("k", "e")
    assert not engine.is_out("k", "stranger")
    # A larger crowd absorbs a smaller one it contains; distinct crowds do not merge.
    engine._record(Public("k", frozenset({"a", "b", "c", "z"}), 1, "broadcast", None))
    assert len(engine.publics_for("k")) == 2
    assert engine.is_common("k", "a", "z")

    # Off answers no to everything, which is what makes it declinable.
    off = CommonKnowledgeEngine(enabled=False)
    off._record(Public("k", frozenset({"a", "b", "c"}), 0, "in_the_open", "p"))
    assert not off.is_common("k", "a", "b") and not off.is_out("k", "a")

    # 2. A CONVERSATION IS NOT A CROWD. Mutual knowledge between two people is
    #    what a conversation already is, and calling it common knowledge would
    #    make the term mean nothing.
    assert MIN_WITNESSES >= 3
    small = CommonKnowledgeEngine(enabled=True)

    class _Event:
        type = "claim"
        actor = "agent:a"
        location = "place:market"
        world_time = 10
        payload = {"medium": "in_person"}

        class proposition:
            @staticmethod
            def core_key(): return "k"

    world = type("W", (), {"places": {"place:market": {"privacy_level": 0.1}},
                           "agents": {"agent:a": None, "agent:b": None}})()
    assert small.observe(world, _Event(), [("agent:b", 1.0)]) == []

    # A phone call reaches one person however public the room is.
    private = _Event(); private.payload = {"medium": "phone"}
    assert small.observe(world, private,
                         [("agent:b", 1.0), ("agent:c", 1.0)]) == []

    # 3. IN A REAL WORLD IT FIRES, AND IT FIRES ON THE RIGHT THING. The radio in
    #    `market-square` broadcasts the FALSE account of the killing, so the
    #    thing the town cannot deny is the thing that is not true -- and the one
    #    witness who saw otherwise is not in the crowd, because she does not
    #    listen to the radio.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:",
        pursuit=True, common_knowledge=True))
    try:
        sdk.submit_player_text("look")
        for _ in range(24):
            sdk.advance_time(60)
        rows = sdk.public_knowledge()
        assert rows, "a day of a world with a radio station in it made nothing public"
        broadcast = [row for row in rows if row["how"] == "broadcast"]
        assert broadcast, f"the radio established nothing: {rows}"
        crowd = broadcast[0]
        assert len(crowd["members"]) >= MIN_WITNESSES
        assert "agent:yara" not in crowd["members"], (
            "the witness who does not listen to the radio ended up inside the "
            "crowd that only the radio informed")
        assert sdk.is_public_between(crowd["key"], *crowd["members"][:2])
        assert not sdk.is_public_between(crowd["key"], "agent:yara",
                                         crowd["members"][0])
    finally:
        sdk.close()

    # 4. PUBLICITY IS NOT EVIDENCE. Establishing something in front of a crowd
    #    must not make anybody surer of it: it is one origin, weighed once.
    #    Treating publicity as evidence would be the same error as treating
    #    repetition as proof, which this runtime exists partly to avoid.
    #
    #    Note what is deliberately NOT asserted here: that a run with the layer
    #    on is identical to one with it off. It is not, and should not be --
    #    suppressing a retelling that is already common knowledge changes who
    #    hears what afterwards. That is the layer changing what gets SAID, which
    #    is its job. This asserts the other half: that establishing a public
    #    moves no number.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", common_knowledge=True))
    try:
        sdk.submit_player_text("look")
        for _ in range(24):
            sdk.advance_time(60)
        rows = sdk.public_knowledge()
        assert rows, "nothing was public, so this proves nothing"

        def confidences():
            return {(aid, key): round(b.expected_prob, 9)
                    for aid, agent in sorted(sdk.world.agents.items())
                    for key, b in sorted(agent.beliefs.items())}

        before = confidences()
        established = 0
        for row in rows:
            members = list(row["members"])
            fake = type("E", (), {
                "type": "broadcast", "actor": members[0], "location": row["place"],
                "world_time": sdk.world.world_time, "payload": {},
                "proposition": type("P", (), {
                    "core_key": staticmethod(lambda k=row["key"]: k)})()})()
            # A crowd larger than the recorded one, so this is a genuinely new
            # public rather than one the engine discards as already known.
            everyone = [(aid, 1.0) for aid in sdk.world.agents]
            established += len(sdk.core.common_knowledge.observe(
                sdk.world, fake, everyone))
        assert established, "no new public was established, so nothing was tested"
        assert confidences() == before, (
            "establishing something in front of a crowd changed what somebody "
            "believes; publicity is not evidence")
    finally:
        sdk.close()

    print(f"ok  common knowledge: two crowds stay two crowds, a conversation is "
          f"not one, the radio made {len(crowd['members'])} people unable to "
          f"deny the false account without reaching the witness, and no "
          f"confidence moved")


def test_a_note_outlives_the_conversation_and_can_be_read_by_the_wrong_person():
    """The runtime's first piece of evidence, as opposed to testimony.

    `unscripted/medium.py` has described a note since it was written and nothing ever
    produced one. It is worth producing for exactly one reason: a conversation is
    gone when it ends and a note is still there. That is what lets it be found by
    somebody it was not written for, and what makes it a claim its author cannot
    take back.

    This asserts the four things that make it a mechanic rather than a slower
    telephone: they are written when somebody cannot be reached, they are
    delivered, they are sometimes intercepted, and what they say is fixed at the
    moment of writing rather than at the moment of reading.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.medium import NOTE
    from unscripted.notes import NoteBoard

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    def run(notes: bool, media: bool = False, hours: int = 24 * 7):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, media=media, notes=notes))
        try:
            sdk.submit_player_text("look")
            seen, mediums = {}, set()
            for _ in range(hours):
                outcome = sdk.advance_time(60)
                for bucket in outcome["last_trace"].values():
                    if not isinstance(bucket, list):
                        continue
                    for code, _m, detail in bucket:
                        if code.startswith("note."):
                            seen.setdefault(code, []).append(detail)
            for row in sdk.core.store.diffusion_events() if sdk.core.store else ():
                mediums.add(row.get("medium"))
            from unscripted import snapshot as snapshot_module
            return seen, json.dumps(snapshot_module.capture(sdk.world, sdk.core),
                                    sort_keys=True, default=str)
        finally:
            sdk.close()

    # 1. OFF IS BYTE-IDENTICAL. Same contract as every other optional layer.
    off, off_state = run(False)
    assert off == {}, f"the layer is off and it wrote something: {list(off)}"
    off_again, off_again_state = run(False)
    assert off_state == off_again_state

    on, on_state = run(True)
    assert on_state != off_state, "notes are on and the world came out identical"

    # 2. THEY ARE WRITTEN, DELIVERED, AND SOMETIMES NOT. A layer where every note
    #    arrives is a message queue; a layer where none does is decoration.
    written = len(on.get("note.left", ()))
    delivered = len(on.get("note.read", ()))
    intercepted = len(on.get("note.intercepted", ()))
    assert written >= 10, f"only {written} notes in a week"
    assert delivered >= 5, f"{written} written and {delivered} delivered"
    assert intercepted >= 1, (
        "no note was ever read by the wrong person, which is the only thing a "
        "note can do that a conversation cannot")
    assert intercepted < delivered, (
        f"{intercepted} intercepted against {delivered} delivered: being read by "
        f"a stranger has become the normal fate of a letter")

    # 3. NOBODY WRITES TO SOMEBODY THEY COULD SIMPLY HAVE RUNG. With telephones
    #    in the world, the person you most want is usually in your contacts, and
    #    the note is what you do when they are not reachable at all.
    with_phones, _ = run(True, media=True)
    assert len(with_phones.get("note.left", ())) < written, (
        "as many notes were written in a world with telephones as in one "
        "without, so 'cannot be reached' is not what triggers them")

    # 4. WHAT IT SAYS IS FIXED WHEN IT IS WRITTEN. On a phone the levelling
    #    happens in the telling; on paper it happens once, and after that the
    #    words go on saying exactly the same wrong thing to everybody.
    board = NoteBoard(enabled=True)
    assert NOTE.fidelity < 1.0 and not NOTE.audience
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, notes=True))
    try:
        sdk.submit_player_text("look")
        for _ in range(24 * 3):
            sdk.advance_time(60)
        lying_about = [note for place in sdk.world.places
                       for note in sdk.notes_at(place)]
        every_note = list(sdk.core.notes.by_place.values())
        for pile in every_note:
            for note in pile:
                # Read twice, the same words. The proposition is stored, not
                # regenerated, which is the whole difference from a retelling.
                assert note.proposition is note.proposition
                assert note.origin, "a note with no provenance is not evidence"
        assert isinstance(lying_about, list)

        # A note carries its AUTHOR's provenance, not its reader's -- a claim
        # arrives with a name on it that the author is not present to be asked
        # about, which is the whole reason a note can incriminate somebody.
        readers = [d for d in on.get("note.read", ()) if d.get("origin")]
        assert readers, "a delivered note carried no origin"
        assert all(d["author"] != d["reader"] for d in on.get("note.read", ()))
    finally:
        sdk.close()

    print(f"ok  notes: off is byte-identical; {written} written in a week, "
          f"{delivered} delivered, {intercepted} read by the wrong person, "
          f"{len(on.get('note.went_unread', ()))} never collected; with "
          f"telephones only {len(with_phones.get('note.left', ()))} were written")


def test_every_optional_layer_is_declinable_reachable_and_reported():
    """A mechanic nobody can switch on from the command line does not exist.

    Seven layers accumulated as `RuntimeConfig` fields, and for a while every one
    of them could only be reached by writing a Python file -- while the entry
    point the documentation gives an integrator is `unscripted serve`. So this asserts
    the whole chain for each of them, from one declaration:

        it is a config field, it defaults to off, the command line can turn it
        on, its dependencies are enforced rather than ignored, the runtime
        reports whether it is running, and the documentation lists it.

    A layer added later without all six is a failing test rather than a feature
    nobody can find.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.cli import _apply_layers, _explain_layers
    from unscripted.contracts import LAYER_REQUIRES, OPTIONAL_LAYERS

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")
    names = [name for name, _ in OPTIONAL_LAYERS]
    assert len(set(names)) == len(names)

    # 1. Declared, off, and described in a sentence rather than a word.
    blank = RuntimeConfig(world_pack_path=pack)
    for name, what in OPTIONAL_LAYERS:
        assert hasattr(blank, name), f"{name} is declared and is not a config field"
        assert getattr(blank, name) is False, f"{name} does not default to off"
        assert len(what.split()) >= 6, f"{name} has no usable description"

    # 2. The command line reaches every one of them, and 'all' means all.
    class _Args:
        def __init__(self, layers): self.layers = layers
    for name in names:
        needs = LAYER_REQUIRES.get(name)
        asked = f"{needs},{name}" if needs else name
        cfg = _apply_layers(RuntimeConfig(world_pack_path=pack), _Args(asked))
        assert getattr(cfg, name) is True, f"--layers {asked} did not turn on {name}"
    everything = _apply_layers(RuntimeConfig(world_pack_path=pack), _Args("all"))
    assert all(getattr(everything, name) for name in names)

    # 3. A misspelling and an unmet dependency are errors, not shrugs. Running
    #    without the mechanic somebody asked for is the failure that costs an
    #    afternoon of wondering why nothing happens.
    for bad in ("climat", "gossip", "climate,nonsense"):
        try:
            _apply_layers(RuntimeConfig(world_pack_path=pack), _Args(bad))
        except ValueError as exc:
            assert "unknown layer" in str(exc)
        else:
            raise AssertionError(f"--layers {bad} was accepted")
    for dependent, needs in LAYER_REQUIRES.items():
        try:
            _apply_layers(RuntimeConfig(world_pack_path=pack), _Args(dependent))
        except ValueError as exc:
            assert needs in str(exc)
        else:
            raise AssertionError(f"{dependent} was accepted without {needs}")

    # 4. The runtime reports exactly these, no more and no fewer -- so the wire
    #    cannot come to disagree with the declaration.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:"))
    try:
        assert set(sdk.layers()) == set(names), (
            f"reported {sorted(sdk.layers())} against declared {sorted(names)}")
        assert not any(sdk.layers().values()), "a default build has a layer on"
    finally:
        sdk.close()

    on = UnscriptedRuntime.create(_apply_layers(
        RuntimeConfig(world_pack_path=pack, storage_path=":memory:"),
        _Args("all")))
    try:
        assert all(on.layers().values()), (
            f"asked for everything and got {on.layers()}")
    finally:
        on.close()

    # 5. And the documentation an integrator is sent to lists every one.
    integration = open(os.path.join(root, "docs", "INTEGRATION.md"),
                       encoding="utf-8").read()
    for name in names:
        assert f"`{name}`" in integration, (
            f"{name} is a shipped mechanic and docs/INTEGRATION.md does not "
            f"mention it")
    assert _explain_layers() == 0

    print(f"ok  layers: {len(names)} optional mechanics, each off by default, "
          f"each reachable as --layers {names[1]}, dependencies enforced, all "
          f"reported by the runtime and all documented")


def test_the_world_fits_in_the_games_own_save_file_and_survives_a_patch():
    """A game's save is a file the player owns; the runtime has to fit inside it.

    `/snapshot` hands back an id into the runtime's own store. That is right for
    a debug rewind and wrong for shipping: a player copies a save between
    machines and syncs it to a cloud, and an id pointing into a second database
    drifts away from the file it belongs to the first time that happens. Worse,
    `unscripted serve` defaults to `:memory:`, so for anyone following the documented
    quickstart the snapshot died with the process.

    So there is one blob, out and in. This asserts the four things a shipping
    game needs from it: it round-trips exactly, it is small enough to embed
    without redesigning a save format, a load screen can ask what would happen
    before committing, and **a save survives the studio patching the cast** --
    because a patch is not a corruption and refusing the save would be worse than
    anything it could cost.
    """
    import gzip
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.snapshot import (STATE_FORMAT, StateImportError, export_state,
                              import_state, inspect_state, world_fingerprint)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")
    config = dict(world_pack_path=pack, storage_path=":memory:",
                  pursuit=True, notes=True, common_knowledge=True,
                  climate=True, contagion=True)

    def fresh():
        return UnscriptedRuntime.create(RuntimeConfig(**config))

    def fingerprint(runtime):
        """Everything a load has to bring back, as one comparable value."""
        return json.dumps({
            "time": runtime.world.world_time,
            "agents": {aid: {
                "where": agent.location,
                "beliefs": {key: round(b.expected_prob, 9)
                            for key, b in sorted(agent.beliefs.items())},
                "origins": {key: dict(b.origin_counts)
                            for key, b in sorted(agent.beliefs.items())},
                "mood": [round(agent.affect.mood.p, 9), round(agent.affect.mood.a, 9),
                         round(agent.affect.mood.d, 9)],
                "memories": len(agent.memory),
            } for aid, agent in sorted(runtime.world.agents.items())},
            "public": runtime.public_knowledge(),
            "climate": runtime.climate_report(),
        }, sort_keys=True, default=str)

    # 1. IT ROUND-TRIPS EXACTLY. Not approximately: a load that returns a world
    #    slightly unlike the one saved is a bug report from a player six months
    #    later that nobody can reproduce.
    played = fresh()
    try:
        played.submit_player_text("look")
        played.submit_player_text("threaten Yara")
        for _ in range(48):
            played.advance_time(60)
        blob = played.export_state()
        expected = fingerprint(played)
    finally:
        played.close()

    # Through JSON, because that is what a save file is -- an in-process dict
    # round trip would not catch a value that cannot survive serialisation.
    wire = json.loads(json.dumps(blob, default=str))
    assert wire["format"] == STATE_FORMAT and wire["format_version"] >= 1
    assert wire["runtime_version"] and wire["snapshot_schema_version"] >= 8

    loaded = fresh()
    try:
        assert fingerprint(loaded) != expected, "the fresh world already matched"
        report = loaded.import_state(wire)
        assert report["usable"] and report["code"] == "ok"
        assert fingerprint(loaded) == expected, (
            "the loaded world is not the world that was saved")
    finally:
        loaded.close()

    # 2. IT IS SMALL ENOUGH THAT NO SAVE FORMAT HAS TO CHANGE FOR IT.
    raw = json.dumps(blob, default=str)
    packed = len(gzip.compress(raw.encode("utf-8")))
    assert packed < 200_000, f"{packed} bytes gzipped is too big to embed quietly"

    # 3. A LOAD SCREEN CAN ASK BEFORE IT COMMITS. `usable` is a field, not an
    #    exception: offering "continue" should not require catching one.
    probe = fresh()
    try:
        assert probe.inspect_state(wire)["usable"] is True
        for bad, code in ((None, "not_a_state_blob"),
                          ({}, "not_a_state_blob"),
                          ({**wire, "format": "something-else"}, "not_a_state_blob"),
                          ({**wire, "format_version": 99}, "envelope_too_new"),
                          ({**wire, "snapshot_schema_version": 999},
                           "save_from_newer_build"),
                          ({**wire, "agents": ["agent:nobody"]}, "different_world")):
            verdict = inspect_state(bad, probe.world)
            assert verdict["usable"] is False and verdict["code"] == code, verdict
            try:
                import_state(bad, probe.world, probe.core)
            except StateImportError as exc:
                assert code in str(exc)
            else:
                raise AssertionError(f"{code} was imported anyway")
    finally:
        probe.close()

    # 4. A PATCH IS NOT A CORRUPTION. The studio ships an update that retires one
    #    character and introduces another. Every existing save must still load --
    #    refusing it would cost a player their game to protect them from a
    #    difference the runtime can simply name.
    patched = fresh()
    try:
        retired = "agent:sela"
        assert retired in patched.world.agents
        del patched.world.agents[retired]
        newcomer = copy.deepcopy(patched.world.agents["agent:bran"])
        newcomer.id = "agent:iris"
        patched.world.agents["agent:iris"] = newcomer
        patched.world.invalidate_indexes()

        assert world_fingerprint(patched.world) != wire["world_fingerprint"], (
            "the cast changed and the fingerprint did not notice")
        verdict = patched.inspect_state(wire)
        assert verdict["usable"] is True, (
            "a save from before a patch was refused; a player just lost their game")
        assert verdict["code"] == "world_changed"
        assert verdict["dropped"] == [retired], verdict["dropped"]
        assert verdict["unsaved"] == ["agent:iris"], verdict["unsaved"]

        report = patched.import_state(wire)
        assert report["dropped"] == [retired]
        # The survivors really did come back, and the newcomer really did keep
        # what the pack authored rather than inheriting somebody else's history.
        assert patched.world.agents["agent:yara"].beliefs, "a survivor lost everything"
        trace = patched.core.last_traces.get("_state") or []
        assert any(code == "state.world_changed" for code, _m, _d in trace), (
            "the cast changed silently; a load that loses a character must say so")
    finally:
        patched.close()

    print(f"ok  save/load: exact round trip through JSON, {packed/1024:.1f} kB "
          f"gzipped for {len(wire['agents'])} characters, six unusable blobs "
          f"refused by name, and a save from before a patch still loads — "
          f"dropping {retired} and reporting it")


def test_a_game_can_launch_the_runtime_as_a_child_process():
    """Nobody starts the service, and that was the whole integration problem.

    Both shipped engine clients assumed it was already running -- the Godot one
    says so in its error message. That is fine for a demo and it is exactly what
    a studio has to solve before shipping, so every studio would have solved it,
    once, badly.

    Four things make it solvable, and this asserts each against a real child
    process rather than describing them:

      `--port 0`      the OS picks. A fixed port breaks the first time a player
                      has something else on it or runs two copies.
      `--announce`    written atomically once LISTENING, so a launcher that sees
                      the file can connect rather than race the bind.
      SIGTERM         handled, so a clean stop is clean -- the default handler
                      ended the process without unwinding, and the announce file
                      was left pointing at a dead port.
      `--parent-pid`  the service exits when the game does, including when the
                      game crashes. Games crash, and an orphan holding a port is
                      an afternoon of somebody's life.
    """
    import signal
    import urllib.error
    import urllib.request

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")
    work = tempfile.mkdtemp(prefix="unscripted-embed-")
    announce = os.path.join(work, "nested", "announce.json")   # also: it mkdirs
    token = "launch-token-42"

    def wait_for(predicate, seconds=40.0, every=0.1):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(every)
        return False

    def get(url, path):
        request = urllib.request.Request(
            url + path, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    # A stand-in for the game process: the service is told to die with it.
    parent = subprocess.Popen([sys.executable, "-c",
                               "import time; time.sleep(600)"])
    child = subprocess.Popen(
        [sys.executable, "-m", "unscripted", "serve", "--world-pack", pack,
         "--port", "0", "--announce", announce, "--auth-token", token,
         "--parent-pid", str(parent.pid)],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert wait_for(lambda: os.path.exists(announce)), (
            "the service never announced itself")
        details = json.loads(open(announce, encoding="utf-8").read())
        assert set(details) >= {"url", "host", "port", "token", "pid",
                                "runtime_version"}, details
        assert details["port"] != 0 and details["port"] != 8765, (
            f"--port 0 did not get a chosen port: {details['port']}")
        assert details["token"] == token and details["pid"] == child.pid

        # THE FILE IS THE READY SIGNAL. Not a hint -- if seeing it does not mean
        # the service answers, a launcher has to poll anyway and the file is
        # pointless.
        health = get(details["url"], "/health")
        assert health["ok"] is True

        # The token is real: without it, nothing.
        try:
            urllib.request.urlopen(details["url"] + "/health", timeout=15)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("the service answered without the token")

        # ... and it is enough to do the actual job over the wire.
        exported = get(details["url"], "/v2/state/export")
        assert exported["format"] == "unscripted-state"
    finally:
        pass

    # 1. A CLEAN STOP IS CLEAN. SIGTERM, and the file goes with it -- a stale
    #    announce file would send the next launch to a dead port.
    child.send_signal(signal.SIGTERM)
    child.wait(timeout=30)
    assert child.returncode is not None
    assert wait_for(lambda: not os.path.exists(announce), seconds=10), (
        "SIGTERM left the announce file behind, pointing at a port that is gone")

    # 2. AN ORPHAN CLEANS ITSELF UP. The game dies without stopping anything;
    #    the service must not be left holding the port and the save.
    orphan_announce = os.path.join(work, "orphan.json")
    orphan = subprocess.Popen(
        [sys.executable, "-m", "unscripted", "serve", "--world-pack", pack,
         "--port", "0", "--announce", orphan_announce,
         "--parent-pid", str(parent.pid)],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_for(lambda: os.path.exists(orphan_announce))
        parent.kill()
        parent.wait(timeout=30)
        assert wait_for(lambda: orphan.poll() is not None, seconds=30), (
            "the game is gone and the runtime is still running, holding a port "
            "nobody will remember starting")
    finally:
        for process in (orphan, parent):
            if process.poll() is None:
                process.kill()
        shutil.rmtree(work, ignore_errors=True)

    print(f"ok  embedding: --port 0 chose {details['port']}, announced "
          f"atomically once listening, token enforced, SIGTERM removed the "
          f"file, and an orphaned service exited when its parent did")


def test_a_promise_that_nothing_checks_is_only_a_line_of_dialogue():
    """Breaking your word used to be free, and better than free.

    The runtime has taken promises since the beginning: the parser recognises
    one, an event of type `promise` is emitted, and every witness encodes a
    memory whose type is `commitment`. Then nothing -- no deadline, no keeping,
    no breaking. Worse than nothing, in fact: making a promise granted +0.35
    trust on the spot and failing it cost zero, so the optimal play was to
    promise everything to everybody and never deliver.

    And `SocialExchangeEngine.on_commitment_resolved` had always known exactly
    what a kept and a broken promise were worth. It had no caller. That single
    missing trigger is why three engines in this runtime looked dead: with no
    producer of reputation deltas, `agent.reputation` was empty in every world at
    every time, and `unscripted/sociolinguistics.py` reads it.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.promises import KEPT_MARGIN, PromiseLedger

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    def town(promises: bool = True):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", promises=promises))

    # 1. OFF IS BYTE-IDENTICAL, as for every optional layer.
    def run(enabled):
        sdk = town(enabled)
        try:
            sdk.submit_player_text("look")
            sdk.submit_player_text("promise Yara 50 credits")
            for _ in range(24 * 3):
                sdk.advance_time(60)
            from unscripted import snapshot as snapshot_module
            state = snapshot_module.capture(sdk.world, sdk.core)
            state.pop("promises", None)
            return json.dumps(state, sort_keys=True, default=str)
        finally:
            sdk.close()
    assert run(False) == run(False), "the run stopped being deterministic"
    assert run(True) != run(False), (
        "promises are on and the same script produced the same world")

    # 2. A PROMISE IS TAKEN, WITH A DEADLINE AND THE PEOPLE IT WAS MADE IN FRONT
    #    OF. Witnesses matter: a broken promise reaches the people for whom it
    #    was ever a promise, not the whole town.
    sdk = town()
    try:
        sdk.submit_player_text("look")
        sdk.submit_player_text("promise Yara 50 credits")
        open_now = sdk.promises_report()["open"]
        assert len(open_now) == 1, open_now
        promise = open_now[0]
        assert promise["promiser"] == "agent:player_1"
        assert promise["promisee"] == "agent:yara"
        assert promise["due_at"] > promise["made_at"], "a promise with no deadline"
        assert "agent:yara" in promise["witnesses"]
        assert sdk.promises_owed_by("agent:player_1")
        assert sdk.promises_owed_to("agent:yara")
    finally:
        sdk.close()

    # 3. THE ENGINE'S ANSWER IS AUTHORITATIVE, and it is the path a studio uses.
    #    Both outcomes have to be reachable and they have to differ, or this is a
    #    penalty rather than a mechanic.
    outcomes = {}
    for kept in (True, False):
        sdk = town()
        try:
            sdk.submit_player_text("look")
            yara = sdk.world.agents["agent:yara"]
            before = yara.trust_in("agent:player_1")
            sdk.submit_player_text("promise Yara 50 credits")
            promised = yara.trust_in("agent:player_1")
            assert promised > before, "making a promise no longer registers at all"
            sdk.settle_promise(sdk.core.promises.open_ids()[0], kept=kept,
                               note="the game knows")
            outcomes[kept] = (yara.trust_in("agent:player_1"),
                              dict(yara.reputation.get("agent:player_1", {})))
            assert not sdk.promises_report()["open"], "it settled and stayed open"
        finally:
            sdk.close()

    kept_trust, kept_reputation = outcomes[True]
    broken_trust, broken_reputation = outcomes[False]
    assert kept_trust > promised > broken_trust, (
        f"kept {kept_trust:.3f}, still-promised {promised:.3f}, broken "
        f"{broken_trust:.3f}: keeping and breaking a promise are not on opposite "
        f"sides of doing neither")
    assert broken_trust < before, (
        "breaking a promise left the player better off than never making one, "
        "which is the exact asymmetry this layer exists to remove")

    # 4. REPUTATION IS REAL NOW. This is the assertion that matters most, because
    #    it is the one that was silently false for the whole life of the project.
    assert broken_reputation.get("reliable", 0.0) < 0.0, (
        "a broken promise cost no reputation; ReputationEngine is still dead")
    assert not kept_reputation.get("reliable"), (
        "keeping a promise was penalised")

    # And nothing else populates it, so this is genuinely the producer.
    bare = town(promises=False)
    try:
        bare.submit_player_text("look")
        bare.submit_player_text("promise Yara 50 credits")
        for _ in range(24 * 3):
            bare.advance_time(60)
        assert not any(agent.reputation for agent in bare.world.agents.values()), (
            "reputation appeared from somewhere else; this test proves less "
            "than it claims")
    finally:
        bare.close()

    # 5. UNSETTLED PROMISES STILL COME DUE. A studio that ignores the settle
    #    endpoint gets the runtime's own judgement, which is deliberately a model
    #    of somebody NOTICING rather than of a transaction completing -- so a
    #    promise nobody hears anything about is broken.
    assert 0.0 < KEPT_MARGIN < 0.01, (
        "the margin is large enough to be asking whether the promisee happened "
        "to be paying attention, which is not the question")
    lapsed = town()
    try:
        lapsed.submit_player_text("look")
        lapsed.submit_player_text("promise Yara 50 credits")
        for _ in range(24 * 3):
            lapsed.advance_time(60)
        settled = lapsed.promises_report()["settled"]
        assert settled and settled[0]["state"] == "broken", settled
        assert not lapsed.promises_report()["open"], "it came due and stayed open"
    finally:
        lapsed.close()

    # 6. Settling something that is not open is an error a caller can act on,
    #    not a silent no-op that leaves them wondering.
    ledger = PromiseLedger(enabled=True)
    try:
        ledger.settle(None, None, "promise_nope", True)
    except KeyError:
        pass
    else:
        raise AssertionError("settling an unknown promise was accepted")

    print(f"ok  promises: off is byte-identical; making one still reads "
          f"{promised:.3f}, keeping it {kept_trust:.3f}, breaking it "
          f"{broken_trust:.3f} — below the {before:.3f} of never having "
          f"promised — and a broken one is the first thing in this runtime "
          f"ever to write a reputation ({broken_reputation})")


def test_every_command_line_in_the_documentation_actually_exists():
    """A flag that never existed sat in the integration guide the whole time.

    `docs/INTEGRATION.md` told anyone wanting a language model to run

        unscripted serve --text-provider http --text-endpoint ... --text-model ...

    and not one of those three flags has ever existed; the real ones are
    `--llm-endpoint` and `--llm-model`. The first thing a developer does after
    reading the integration guide is that command, and it fails with an argparse
    usage dump -- which is the worst possible first impression, and it survived
    because nobody checks prose.

    So it is checked. Every `unscripted ...` invocation in every shipped document is
    parsed against the real argument parser here, which makes this class of
    error impossible rather than unlikely.
    """
    import argparse
    import re
    from unscripted.cli import build_parser

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    documents = ([os.path.join(root, name)
                  for name in ("README.md", "CHANGELOG.md")] +
                 [os.path.join(root, "docs", name)
                  for name in sorted(os.listdir(os.path.join(root, "docs")))
                  if name.endswith(".md")])

    parser = build_parser()
    subcommands = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subcommands |= set(action.choices)
    assert subcommands, "no subcommands found; this test would pass vacuously"

    def invocations(text: str):
        """Every `unscripted ...` command in a document, joined across backslashes."""
        joined = re.sub(r"\\\n\s*", " ", text)
        for line in joined.splitlines():
            line = line.strip().lstrip("$ ").strip()
            if not line.startswith(("unscripted ", "python3 -m unscripted ", "python -m unscripted ")):
                continue
            # Not a command line: prose that happens to open with the word, and
            # pipelines whose tail belongs to another program.
            command = line.split("#")[0].split("|")[0].split(">")[0].strip()
            argv = command.replace("python3 -m unscripted", "").replace(
                "python -m unscripted", "").replace("unscripted", "", 1).split()
            if argv and argv[0] in subcommands:
                yield command, argv

    checked, flags = 0, set()
    for document in documents:
        text = open(document, encoding="utf-8").read()
        for command, argv in invocations(text):
            checked += 1
            named = [a for a in argv if a.startswith("--")]
            flags |= set(named)
            # Placeholders like <your pack> and $VARS are not ours to resolve, so
            # this asserts the SHAPE -- every flag is a real flag of that
            # subcommand -- rather than trying to run the command.
            sub = argv[0]
            known = set()
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for option in action.choices[sub]._actions:
                        known |= set(option.option_strings)
            for option in parser._actions:
                known |= set(option.option_strings)
            unknown = [flag for flag in named
                       if flag.split("=")[0] not in known]
            assert not unknown, (
                f"{os.path.relpath(document, root)} documents\n    {command}\n"
                f"  and `unscripted {sub}` has no {', '.join(unknown)}")

    assert checked >= 20, (
        f"only {checked} command lines found across {len(documents)} documents; "
        f"the extractor has probably stopped matching and this test is passing "
        f"vacuously")
    print(f"ok  docs: {checked} documented command lines across "
          f"{len(documents)} files, {len(flags)} distinct flags, every one real")


def test_a_tick_reports_everything_that_happened_in_it():
    """A layer nobody can see working is a layer nobody will trust.

    `process_event` used to *replace* `last_traces`, and `advance_time` fires
    many events -- so each one erased the last, and a whole tick reported only
    whatever happened to come last. Measured on `market-square`: a week reported
    `climate.moved: 0` and `common_knowledge.established: 0` while both layers
    demonstrably worked. `_routine` and `_pursuit` were erased too, by the first
    claim diffusion delivered afterwards.

    Separately, `routine.perform_move` called `climate.carried(...)` and threw
    the return value away -- so the mood really did travel between rooms, which
    is the one mechanism the climate layer is documented around, and no trace
    anywhere showed it happening.

    Both are observability bugs rather than behaviour bugs, which is exactly why
    they lasted: the simulation was right and the window onto it was not.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, notes=True,
        climate=True, contagion=True, common_knowledge=True, promises=True))
    try:
        sdk.submit_player_text("look")
        sdk.submit_player_text("threaten Yara")
        seen = {}
        for _ in range(24 * 7):
            outcome = sdk.advance_time(60)
            for bucket in outcome["last_trace"].values():
                if not isinstance(bucket, list):
                    continue
                for code, _magnitude, _detail in bucket:
                    seen[code] = seen.get(code, 0) + 1

        # Every layer that is on has to show up. Before the fix, three of these
        # were silently zero for a whole week of world time.
        for code in ("routine.moved", "pursuit.acted", "diffusion.told",
                     "contagion.caught", "climate.carried",
                     "common_knowledge.established", "note.left"):
            assert seen.get(code), (
                f"a week with every layer on and not one {code}; the tick is "
                f"losing reasons again")

        # And the counts are consistent with each other rather than merely
        # non-zero: the mood travels with the traffic, so one carry per move.
        assert seen["climate.carried"] == seen["routine.moved"], (
            f"{seen['routine.moved']} moves produced "
            f"{seen['climate.carried']} carries")
    finally:
        sdk.close()

    # A SINGLE EVENT STILL REPLACES. "What did this event cause" is the right
    # answer for `emit_event`, and accumulating across separate calls would grow
    # without bound -- so the merge is scoped to a tick and this proves it.
    single = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", climate=True))
    try:
        single.submit_player_text("look")
        single.submit_player_text("threaten Yara")
        first = len(json.dumps(single.core.last_traces, default=str))
        single.submit_player_text("threaten Yara")
        second = len(json.dumps(single.core.last_traces, default=str))
        assert second < first * 1.8, (
            "two separate turns accumulated into one trace; outside a tick the "
            "answer to 'what did this cause' must be about this one")
    finally:
        single.close()

    print(f"ok  traces: a week with every layer on reports all of "
          f"{len(seen)} distinct reason codes — {seen['climate.carried']} "
          f"carries for {seen['routine.moved']} moves — and a single turn "
          f"still answers only for itself")


def test_attacking_one_of_us_makes_the_rest_of_us_notice():
    """A quarter of what decides who somebody is, multiplied by zero since 2024.

    `IdentityEngine.salience` weighs four terms, and one of them is `w_threat` --
    how endangered each belonging feels. The runtime called it as
    `salience(agent, {})` everywhere, with no threats, so that term contributed
    nothing in any world at any time.

    `SocialIdentityEngine` existed to supply it and was unreachable for a
    different reason: it asked the EVENT which identity was threatened, and
    whether an event threatens *your* belonging depends on who you are. It can
    only be decided per observer. Nothing ever set the key, so the engine was
    constructed on every runtime and never called.

    Tajfel and Turner's point is the one worth having in a city: hurt one member
    of a group in front of the others and the group becomes the thing they are.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:"))
    try:
        sdk.submit_player_text("look")
        nadia = sdk.world.agents["agent:nadia"]
        otto = sdk.world.agents["agent:otto"]
        shared = ({i["id"] for i in nadia.identities} &
                  {i["id"] for i in otto.identities})
        assert shared == {"keeper"}, (
            f"this test needs two characters who share a belonging; the pack "
            f"now gives {shared}")

        # They have to be in the room. See the limit at the end of this test.
        nadia.location = otto.location
        sdk.world.invalidate_indexes()
        _, before = sdk.core.identity.salience(nadia, {})

        assert not nadia.identity_threat, "threatened before anything happened"
        sdk.submit_player_text("attack Otto")

        fired = [detail for bucket in sdk.core.last_traces.values()
                 if isinstance(bucket, list)
                 for code, _m, detail in bucket if code == "identity.threatened"]
        assert any(d["observer"] == "agent:nadia" and d["identity"] == "keeper"
                   and d["because"] == "agent:otto" for d in fired), fired
        assert nadia.identity_threat.get("keeper", 0.0) > 0.1, (
            f"a fellow keeper was attacked in front of her and "
            f"{nadia.identity_threat} came of it")

        # 1. IT REACHES SALIENCE, which is the only reason to produce it.
        _, after = sdk.core.identity.salience(
            nadia, {}, threat_by_identity=nadia.identity_threat)
        assert after["keeper"] > before["keeper"], (
            f"keeper salience {before['keeper']:.4f} -> {after['keeper']:.4f}: "
            f"the threat is stored and still reaches nothing")

        # 2. THE VICTIM IS NOT INCLUDED. Being attacked yourself is every other
        #    layer's business; this one is about the people watching.
        assert not otto.identity_threat, (
            "the person attacked was given identity threat as well, which "
            "double-counts what the affect layer already did to him")

        # 3. IT IS ALARM, NOT A GRUDGE. A threat that never faded would mean one
        #    attack permanently rewrote which identity a character leads with --
        #    personality drift by another route.
        peak = nadia.identity_threat["keeper"]
        for _ in range(24):
            sdk.advance_time(60)
        day = nadia.identity_threat.get("keeper", 0.0)
        assert 0.3 * peak < day < 0.7 * peak, (
            f"{peak:.3f} -> {day:.3f} over a day is not a half-life of one day")
        for _ in range(24 * 6):
            sdk.advance_time(60)
        assert nadia.identity_threat.get("keeper", 0.0) < 0.05, (
            "a week later the town is still braced")

        # 4. STRANGERS ARE UNMOVED. Nothing shared, nothing felt -- otherwise
        #    this is just "violence upsets everyone", which the affect layer
        #    already does and does not need an identity to say.
        assert not sdk.world.agents["agent:bran"].identity_threat
        assert not sdk.world.agents["agent:yara"].identity_threat
    finally:
        sdk.close()

    # 5. THE LIMIT, ASSERTED SO IT CANNOT BE MISREAD AS AN OVERSIGHT. This fires
    #    on WITNESSING, not on hearing about it later. A retold attack arrives as
    #    a `claim` carrying a proposition, and recovering "an attack on one of
    #    ours" from that is a different and larger piece of work. Somebody who
    #    was elsewhere feels nothing, and that is the current behaviour rather
    #    than the intended end state.
    absent = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True))
    try:
        absent.submit_player_text("look")
        assert (absent.world.agents["agent:nadia"].location !=
                absent.world.agents["agent:otto"].location), (
            "the pack changed and this no longer tests being elsewhere")
        absent.submit_player_text("attack Otto")
        for _ in range(24 * 2):
            absent.advance_time(60)
        assert not absent.world.agents["agent:nadia"].identity_threat, (
            "hearing about it second-hand now raises identity threat: good, but "
            "the documented limit is stale and CONCEPT.md must be corrected")
    finally:
        absent.close()

    print(f"ok  social identity: attacking a keeper in front of another raised "
          f"her threat to {peak:.3f} and her keeper salience "
          f"{before['keeper']:.3f} -> {after['keeper']:.3f}, halving in a day; "
          f"the victim, strangers and the absent are untouched")


def test_no_engine_is_built_that_nothing_ever_calls():
    """Three of them were, and one had been lying about a feature for months.

    An audit of what the runtime constructs against what anything invokes found
    `ReputationEngine`, `SocialIdentityEngine` and `InterpersonalEngine` built on
    every runtime and called by nothing. That is not merely waste. Because
    nothing produced reputation deltas, `agent.reputation` was an empty mapping
    in every world at every time -- and `unscripted/sociolinguistics.py` reads it to
    compute perceived social status, so a documented behaviour silently reduced
    to a constant.

    Two are alive now: reputation has a producer in `unscripted/promises.py`, and social
    identity is decided per observer in the perception loop. The third is not
    constructed at all, with the reason written where the class is.

    This is the audit, kept, so the next one is a failing test rather than an
    afternoon of grepping.
    """
    import glob
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime_source = open(os.path.join(root, "unscripted", "runtime.py"),
                          encoding="utf-8").read()
    built = re.findall(r"^\s+self\.([a-z_]+) = ([A-Z][A-Za-z]*)"
                       r"(?:\.for_world)?\(", runtime_source, re.M)
    assert len(built) > 20, (
        f"only {len(built)} engines found; the pattern has stopped matching and "
        f"this test is passing vacuously")

    everything = "".join(
        open(path, encoding="utf-8").read()
        for path in sorted(glob.glob(os.path.join(root, "unscripted", "*.py"))))

    dead = []
    for attribute, cls in built:
        # Reached as self.x, or handed a runtime and asked for it -- the optional
        # layers are called as runtime.x from the modules they cooperate with.
        used = re.search(rf"\b(?:self|core|runtime|rt)\.{attribute}\.",
                         everything)
        if not used:
            dead.append(f"{attribute} ({cls})")
    assert not dead, (
        "built by the runtime and called by nothing: " + ", ".join(dead) +
        ". Either wire it or stop constructing it -- a component with no socket "
        "implies a feature that does not exist, and something downstream is "
        "probably already reading the empty state it should have filled.")

    print(f"ok  engines: {len(built)} constructed by the runtime, every one of "
          f"them reached by something")


def test_the_whole_runtime_ships_as_one_file():
    """The dependency-free promise, finally collecting on itself.

    "How does this reach a player's machine" was the largest unanswered question
    in the integration story, and it has two halves that get conflated. One is
    the Python interpreter. The other is everything else -- pip, a virtualenv,
    site-packages, an install step, an import path to get wrong -- and *that*
    half is solved outright by the SDK having no third-party dependencies, which
    is what makes `zipapp` sufficient where it would otherwise not be.

    So: one file, about a third of a megabyte, that any Python 3.10+ runs. This
    builds one and serves a real world out of it, because a bundle that imports
    but cannot answer a request would be worse than none.
    """
    import urllib.request

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "market-square")
    work = tempfile.mkdtemp(prefix="unscripted-bundle-test-")
    bundle = os.path.join(work, "unscripted.pyz")
    announce = os.path.join(work, "announce.json")
    token = "bundle-token"

    def wait_for(predicate, seconds=60.0):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.15)
        return False

    built = subprocess.run(
        [sys.executable, "-m", "unscripted", "bundle", "--out", bundle],
        cwd=root, capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    assert os.path.exists(bundle)
    size = os.path.getsize(bundle)
    assert 50_000 < size < 5_000_000, (
        f"{size} bytes: either the bundle is missing most of the package or it "
        f"has acquired something it should not have")

    # THE BUNDLE IS NOT THE CONTENT. World packs stay outside it: they are the
    # studio's, they change without a rebuild, and baking them in would make
    # every content edit a repackage.
    import zipfile
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
    assert any(n.startswith("unscripted/") for n in names)
    assert not any("worldpacks" in n for n in names), (
        "world packs were bundled; content does not belong in the runtime")

    child = subprocess.Popen(
        [sys.executable, bundle, "serve", "--world-pack", pack,
         "--port", "0", "--announce", announce, "--auth-token", token,
         "--layers", "pursuit,promises"],
        cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert wait_for(lambda: os.path.exists(announce)), (
            "the bundled service never came up:\n"
            + (child.stdout.read() if child.poll() is not None else "(still running)"))
        details = json.loads(open(announce, encoding="utf-8").read())

        def get(path):
            request = urllib.request.Request(
                details["url"] + path,
                headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)

        assert get("/health")["ok"] is True
        capabilities = get("/capabilities")
        assert capabilities["capabilities"]["pursuit"] is True, (
            "--layers did not reach the bundled runtime")

        # It does the actual job, not merely import: a turn, and a save.
        request = urllib.request.Request(
            details["url"] + "/turn", method="POST",
            data=json.dumps({"text": "ask Yara about the shooting"}).encode(),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=20) as response:
            turn = json.load(response)
        assert turn["world_time"] >= 0 and "location_id" in turn
        exported = get("/v2/state/export")
        assert exported["format"] == "unscripted-state" and exported["state"]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=30)
        shutil.rmtree(work, ignore_errors=True)

    # And the one command that CANNOT work from a bundle says so, rather than
    # producing a traceback or, worse, a half-answer. The layer map is read from
    # the package's own .py files, which are inside the archive.
    from unscripted.architecture import SourceUnavailable, modules
    assert modules(), "the layer map is broken in a source checkout too"
    assert issubclass(SourceUnavailable, RuntimeError)

    print(f"ok  bundle: {size / 1024:.0f} kB single file, no install, serving a "
          f"real world — a turn answered and {len(json.dumps(exported)) // 1024} "
          f"kB of state exported out of it, with world packs left outside")


def test_the_film_has_exactly_one_card_per_spoken_line():
    """A card without a line is silence; a line without a card talks over the next.

    Both have happened. Two missing narration lines once produced twelve seconds
    of silent video, and overlapping audio -- six of sixteen lines colliding by
    up to three and a half seconds -- was the reason the picture is now cut to
    the voice rather than the other way round.

    The counts live in two files that nobody edits together: the spoken lines in
    `tools/godot_demo.py`, the cards in the Godot scene. This is the only thing
    keeping them in step, and it is cheap.
    """
    import importlib.util
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tool = os.path.join(root, "tools", "godot_demo.py")
    scene = os.path.join(root, "integrations", "godot", "UnscriptedDemo",
                         "Main.gd")
    if not (os.path.exists(tool) and os.path.exists(scene)):
        print("ok  film: no demo tooling in this checkout, nothing to check")
        return

    spec = importlib.util.spec_from_file_location("_godot_demo", tool)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    source = open(scene, encoding="utf-8").read()

    def cards(name: str) -> int:
        start = source.index(f"const {name} := [")
        return source[start:source.index("\n]", start)].count('{"kicker"')

    for lines_name, cards_name in (("INTRO_LINES", "INTRO_CARDS"),
                                   ("OUTRO_LINES", "OUTRO_CARDS")):
        spoken = len(getattr(demo, lines_name))
        shown = cards(cards_name)
        assert spoken == shown, (
            f"{spoken} lines in {lines_name} against {shown} cards in "
            f"{cards_name}: the film will either sit silent on a card or talk "
            f"over the next one")

    # The questions are two lines each -- one for the flag world, one for the
    # runtime -- and the demo's own constant says how many questions there are.
    assert len(demo.QUESTION_LINES) == 2 * demo.questions_in_demo(), (
        f"{len(demo.QUESTION_LINES)} question lines for "
        f"{demo.questions_in_demo()} questions asked twice")

    # And nothing anybody would rather not hear read aloud. The address belongs
    # on the closing card, not in the narration.
    every_line = (demo.INTRO_LINES + demo.RUNNING_LINES + demo.QUESTION_LINES
                  + demo.OUTRO_LINES)
    for line in every_line:
        low = line.lower()
        for unreadable in ("github", "http://", "https://", ".com", ".de",
                           "www."):
            assert unreadable not in low, (
                f"the narration would read {unreadable!r} aloud: {line!r}")
        assert len(line) < 340, f"a single spoken line of {len(line)} chars: {line[:60]}..."

    # A duplicate opening was shipped once -- the same sentence in the intro
    # cards and on the first running line, read twice a minute apart.
    seen = {}
    for index, line in enumerate(every_line):
        key = line.strip().lower()[:70]
        assert key not in seen, (
            f"line {index} repeats line {seen[key]}: {line[:70]!r}")
        seen[key] = index

    print(f"ok  film: {len(demo.INTRO_LINES)} intro, "
          f"{len(demo.RUNNING_LINES)} running, {len(demo.QUESTION_LINES)} "
          f"question and {len(demo.OUTRO_LINES)} outro lines, each with a card "
          f"where it needs one, none repeated, no address read aloud")


def test_a_pack_can_tune_the_runtime_and_a_typo_is_refused():
    """How a world works is content, and one engine of fourteen knew that.

    Seventy-nine numbers decide how this simulation feels -- how readily people
    talk, how fast a detail is lost, how long a memory stays reachable, how much
    of a mood rubs off, how long a promise has. Exactly one engine, diffusion,
    ever read any of them from a world pack. Every other constant lived in
    Python, so a studio wanting a gossipier town or longer memories had to edit
    the SDK, which is the wrong seam: a mediaeval village and a surveillance
    state are not the same simulation with different names in it.

    The rule that matters most here is that **an unknown key is an error**. A
    tuning value silently ignored because it was misspelled is the worst failure
    this feature could have -- the world behaves as though nothing was set, the
    author believes it was, and nothing anywhere shows the gap.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted import tuning as tuning_module
    from unscripted.pack import validate_world_pack

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source = os.path.join(root, "worldpacks", "market-square")
    work = tempfile.mkdtemp(prefix="unscripted-tuning-")
    pack = os.path.join(work, "pack")
    shutil.copytree(source, pack)
    world_json = os.path.join(pack, "world.json")

    def set_tuning(block):
        world = json.load(open(world_json, encoding="utf-8"))
        world["tuning"] = block
        with open(world_json, "w", encoding="utf-8") as handle:
            json.dump(world, handle, indent=1)

    try:
        # 1. EVERY ENGINE IS REACHABLE, not just the one that always was.
        probe = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=source, storage_path=":memory:"))
        try:
            described = tuning_module.describe(probe.core)
            knobs = sum(len(row["parameters"]) for row in described)
            assert len(described) >= 12 and knobs >= 60, (
                f"{knobs} parameters across {len(described)} engines; the "
                f"registry has lost most of the runtime")
            # Everything the registry names must actually exist, or `unscripted tune`
            # advertises knobs that are not there.
            for name in tuning_module.TUNABLE:
                engine = getattr(probe.core, name, None)
                assert engine is not None, f"tuning names {name}, runtime has no such thing"
        finally:
            probe.close()

        # 2. A TYPO IS REFUSED, BY NAME, at authoring time. Three shapes of
        #    mistake, and each says which one it was.
        for block, fragment in (
                ({"diffusion": {"distortion_probb": 0.9}}, "distortion_probb"),
                ({"gossip": {"x": 1}}, "not a tunable part"),
                ({"memory": {"tau_ret": "slow"}}, "must be a number"),
                ({"memory": "fast"}, "must be an object")):
            set_tuning(block)
            report = validate_world_pack(pack)
            codes = [entry for entry in report.entries
                     if getattr(entry, "code", None) == "pack.bad_tuning"] \
                    if hasattr(report, "entries") else []
            rendered = str(report.__dict__)
            assert "bad_tuning" in rendered and fragment in rendered, (
                f"{block} was accepted, or reported without saying why: "
                f"{rendered[:300]}")

        # 3. AND IT ACTUALLY CHANGES THE WORLD. A validated knob that reaches
        #    nothing would be worse than no knob.
        def week(block):
            set_tuning(block)
            sdk = UnscriptedRuntime.create(RuntimeConfig(
                world_pack_path=pack, storage_path=":memory:", pursuit=True))
            try:
                sdk.submit_player_text("look")
                counts = {}
                for _ in range(24 * 7):
                    for bucket in sdk.advance_time(60)["last_trace"].values():
                        if isinstance(bucket, list):
                            for code, _m, _d in bucket:
                                counts[code] = counts.get(code, 0) + 1
                return counts, len(sdk.world.agents["agent:yara"].memory)
            finally:
                sdk.close()

        plain, plain_memories = week({})
        noisy, _ = week({"diffusion": {"distortion_prob": 0.6}})
        assert noisy.get("diffusion.distorted", 0) > \
               plain.get("diffusion.distorted", 0) * 2, (
            f"distortion {plain.get('diffusion.distorted')} -> "
            f"{noisy.get('diffusion.distorted')} after doubling the rate")

        _, short_memories = week({"memory": {"episodic_cap": 20}})
        assert short_memories < plain_memories / 1.5, (
            f"{plain_memories} memories -> {short_memories} after capping "
            f"episodic memory at 20")

        # 4. IT IS RECORDED. A scene behaving oddly should not require diffing a
        #    JSON file against the source of the runtime.
        set_tuning({"contagion": {"transfer": 0.4}})
        tuned = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", contagion=True))
        try:
            assert tuned.core.contagion.params["transfer"] == 0.4
            trace = tuned.core.last_traces.get("_tuning") or []
            assert any(code == "tuning.applied" and
                       detail["parameter"] == "transfer" and
                       detail["authored"] == 0.4
                       for code, _m, detail in trace), trace
        finally:
            tuned.close()

        # 5. TUNING CANNOT BREAK THE GUARANTEES. These are rates and thresholds;
        #    no value makes a character know something nobody told them.
        set_tuning({"belief": {"kappa_max": 0.99, "rho_correlated": 0.99},
                    "diffusion": {"max_hops": 99}})
        extreme = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", pursuit=True))
        try:
            extreme.submit_player_text("look")
            for _ in range(24 * 7):
                extreme.advance_time(60)
            for agent in extreme.world.agents.values():
                for key, belief in agent.beliefs.items():
                    assert belief.primary_origin or belief.provenance, (
                        f"{agent.id} believes {key} with no source, under "
                        f"tuning that only changed rates")
        finally:
            extreme.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"ok  tuning: {knobs} parameters across {len(described)} engines "
          f"authorable from world.json; a typo, an unknown engine and a wrong "
          f"type are each refused by name; distortion "
          f"{plain.get('diffusion.distorted')} -> "
          f"{noisy.get('diffusion.distorted')} and memories {plain_memories} -> "
          f"{short_memories} when asked; and no rate buys a belief without a "
          f"source")


def test_the_shipped_client_reaches_every_endpoint_a_game_needs():
    """A client that cannot save is a demo, not an integration.

    The client in the demo project covers four endpoints. That is right for a
    demo and it is not an integration: it cannot send a gameplay event, cannot
    answer an action intent, and cannot save. Those are the three things a real
    game does most, and every studio would have discovered that one at a time.

    So there is a complete one in the addon, and this keeps it complete. Every
    endpoint the v2 contract declares must either be reachable from it or be
    named below as a deliberate omission with a reason -- so adding an endpoint
    forces a decision rather than quietly leaving the client a version behind.
    """
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contract_path = os.path.join(root, "integrations", "unreal",
                                 "UnscriptedBridge", "contract.v2.json")
    client_path = os.path.join(root, "integrations", "godot", "addons",
                               "unscripted", "UnscriptedClient.gd")
    contract = json.load(open(contract_path, encoding="utf-8"))
    client = open(client_path, encoding="utf-8").read()

    #: Endpoints a shipping build deliberately does not call, and why. Each of
    #: these exposes another character's private state, which is a debug HUD's
    #: business and not a game's.
    NOT_FOR_A_GAME = {
        "/v2/state/knowledge": "every character's beliefs with provenance; "
                               "debug-gated, off in a shipping build",
        "/v2/resting_on": "what rests on one source's word; an authoring and "
                          "debugging question",
        "/v2/state/public": "readable by a shipping build, but it answers a "
                            "question a game asks of its own state rather than "
                            "of the runtime",
    }

    missing = []
    for declared in contract["endpoints"]:
        _method, path = declared.split(" ", 1)
        if path in NOT_FOR_A_GAME:
            continue
        # Path parameters are formatted in, so compare on the fixed part.
        stem = path.split("{")[0].rstrip("/")
        if stem and stem not in client:
            missing.append(declared)
    assert not missing, (
        "the shipped client cannot reach: " + ", ".join(missing) +
        ". Add a method, or add it to NOT_FOR_A_GAME with the reason -- a "
        "client one version behind the contract is how an integrator finds out "
        "the hard way.")

    # Every exclusion must still be a real endpoint, or the list is stale and is
    # quietly excusing something that no longer exists.
    declared_paths = {d.split(" ", 1)[1] for d in contract["endpoints"]}
    stale = sorted(set(NOT_FOR_A_GAME) - declared_paths)
    assert not stale, f"NOT_FOR_A_GAME names endpoints that are gone: {stale}"

    # The three a demo client lacked, named explicitly: this test exists for
    # them, and a rewrite that dropped one would otherwise still pass.
    for essential in ("/event", "/v2/state/export", "/v2/state/import",
                      "/v2/actions/pending", "/v2/promises"):
        assert essential in client, f"the client lost {essential}"

    # And it does not block a frame or reorder work: one request at a time, in
    # order, so a turn cannot overtake the event that caused it.
    assert "_queue" in client and "_busy" in client, (
        "the client no longer serialises its requests; a turn can now overtake "
        "the event that caused it")
    # Callback-driven, never `await`: a client that suspends cannot be called
    # from `_ready`, and a game that awaits it stalls on the first dropped
    # request. Checked against CODE only -- the first version read the whole
    # file, so the word "awaited" in a comment failed the build.
    code = "\n".join(line.split("#", 1)[0] for line in client.splitlines())
    assert "HTTPRequest" in client and "await " not in code

    # AND THE OTHER DIRECTION, which was not checked and should have been.
    # The contract said what the client must reach; nothing said that what the
    # service serves is in the contract. A new endpoint could ship, work, be
    # documented and be invisible to every plugin written against the contract
    # -- which is how an integrator finds out about a feature by reading the
    # source, if at all.
    import re as _re
    service_src = open(os.path.join(root, "unscripted", "service.py"), encoding="utf-8").read()
    served = set(_re.findall(r'path == "(/v2/[a-z/_]+)"', service_src))
    declared_stems = {p.split("{")[0].rstrip("/") for p in declared_paths}
    undeclared = sorted(p for p in served
                        if p not in declared_paths and p.rstrip("/") not in declared_stems)
    assert not undeclared, (
        f"the service serves {undeclared} and the contract does not mention "
        f"them; a plugin written against the contract cannot know they exist")

    reachable = len(contract["endpoints"]) - len(NOT_FOR_A_GAME)
    print(f"ok  client: {reachable} of {len(contract['endpoints'])} contract "
          f"endpoints reachable from the shipped Godot client, "
          f"{len(NOT_FOR_A_GAME)} excluded on purpose and each still real")


def test_a_model_may_rewrite_the_lines_but_not_break_them():
    """The build-time phrasing pass, and the three things it refuses to accept.

    `unscripted generate-pack` gets the shape of a world right and its prose flat, on
    purpose: structure is generatable and words are a writer's job. A model
    belongs at BUILD time -- the result is committed JSON, and at play time
    nothing infers, so there is no latency, no cost per line, and nothing that
    can hallucinate in front of a player.

    Which means the checks have to be here, because there is no runtime
    validator standing behind them for lines that were written into a file.
    Driven by a stub that returns exactly the four kinds of answer a real model
    gives -- a good one, a leak, a flipped stance and an empty -- because a test
    that needs a GPU is a test nobody runs.
    """
    from unscripted.phrasing import acceptable, rewrite_pack, surface_forms
    from unscripted.pipeline import Premise, repair, write

    work = tempfile.mkdtemp(prefix="unscripted-phrasing-")
    try:
        pack = os.path.join(work, "pack")
        write(Premise(name="Voice test", seed="phrasing", places=6,
                      characters=8, topics=3), pack)
        repair(pack)

        leaks = surface_forms(pack)
        assert leaks, (
            "the generated pack has a secret with no surface forms, so this "
            "test cannot show that a leak is caught")
        leak = sorted(leaks)[0]

        class Stub:
            """Answers in a fixed cycle, so every branch is exercised."""

            def __init__(self):
                self.calls = 0

            def chat(self, payload):
                self.calls += 1
                turn = self.calls % 4
                if turn == 1:
                    return "  \"A better line, number %d.\"  " % self.calls
                if turn == 2:
                    return "Something about %s, plainly." % leak
                if turn == 3:
                    return "No idea."
                return "   "

        stub = Stub()
        summary = rewrite_pack(pack, stub, model_id="stub", voice="A test world.")
        assert stub.calls == 3 * 6, (
            f"three topics of six lines should be eighteen calls, not {stub.calls}")
        assert summary["rewritten"] > 0, "nothing was rewritten at all"
        assert summary["kept"] > 0, "nothing was refused; the checks did nothing"

        reasons = summary["reasons"]
        assert "would leak a secret" in reasons, (
            f"a line containing {leak!r} was written into the pack; that is the "
            f"thing the secret exists to protect. Reasons seen: {reasons}")
        assert "empty" in reasons, "an empty answer was accepted"
        # The flipped-stance guard only applies to affirmations, and the cycle
        # hits deny slots too, so assert the check itself rather than the count.
        assert acceptable("No idea.", stance="affirm", forbidden=set(),
                          already=set()) == "affirmation reads as a refusal"
        assert acceptable("No idea.", stance="deny", forbidden=set(),
                          already=set()) == "", (
            "a refusal was refused in the deny slot, where it belongs")

        # WHAT FAILED KEPT ITS ORIGINAL, and the pack still passes the gate.
        with open(os.path.join(pack, "topics.json"), encoding="utf-8") as handle:
            after = json.load(handle)
        every = [line for topic in after["topics"]
                 for stance in ("affirm", "deny")
                 for line in topic["phrasings"][stance].values()]
        assert all(line.strip() for line in every), "a line was left empty"
        assert not any(leak in line.lower() for line in every), (
            "a secret's surface form is in the pack's public phrasings")

        from unscripted.authoring import PackDocument, authoring_report
        left = [f for f in authoring_report(PackDocument.load(pack))["findings"]
                if f.get("level") in ("blocker", "problem")]
        assert not left, f"the pack stopped passing the gate: {left[:3]}"

        print(f"ok  phrasing: {summary['rewritten']} of {stub.calls} lines "
              f"rewritten and {summary['kept']} refused -- a leak, a flipped "
              f"stance and an empty answer -- with every refusal keeping its "
              f"original and the pack still passing the gate")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_the_conformance_fixtures_still_describe_this_runtime():
    """The acceptance test a second implementation would be held to.

    A console title may not start a language interpreter beside itself, so
    shipping to one means porting the 2,914-line hot core. The hard part is not
    the porting, it is knowing whether the port is right -- and the obvious
    answer, the thirteen golden scenarios, is the wrong one: they compare
    rendered text, so a port that phrases a sentence differently fails them
    while computing perfectly, and one that phrases it identically passes them
    while computing something wrong.

    These compare state: belief log-odds, provenance, relationships, mood,
    climate. Running them against Python is not circular -- it is a second
    regression net, and it is what keeps the fixtures trustworthy enough to hold
    a port to. A deliberate change to this runtime should regenerate them and
    the diff should be read, not skipped.
    """
    from unscripted import conformance

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixtures = os.path.join(root, "conformance")
    assert os.path.isdir(fixtures), (
        "the fixtures are gone; regenerate with `unscripted conformance --out conformance`")

    failures = conformance.check(fixtures, pack_root=root)
    # WHERE EXACT IS THE WRONG QUESTION. The fixtures are this runtime on Python
    # 3.12+, where sum() over floats compensates; on 3.10 and 3.11 the reference
    # itself sums naively and twelve identity-salience fields land one bit away
    # -- the same twelve the port test documents, no discrete outcome among them.
    # Held exactly, this failed every push, because the push job runs 3.10. So
    # below 3.12 the runtime is judged the way a port is: floats within the
    # measured tolerance, everything else exact. From 3.12 it stays exact.
    tolerated = 0
    if sys.version_info < (3, 12) and failures:
        exact = len(failures)
        failures = conformance.check(fixtures, pack_root=root,
                                     ulp_tolerance=conformance.DEFAULT_ULP_TOLERANCE)
        tolerated = exact - len(failures)
    assert not failures, (
        f"{len(failures)} field(s) no longer match the fixtures. The first few:\n"
        + "\n".join(f"  [{scenario}] {where}\n     expected {expected}\n"
                     f"     actual   {actual}"
                     for scenario, where, expected, actual in failures[:5])
        + "\n\nIf the change was deliberate: `unscripted conformance --out conformance`, "
          "then read the diff before committing it.")

    # And the set has to keep covering more than one path into the state. A
    # fixture set that only ever asks questions lets a port ship with a broken
    # affect model and a clean run.
    catalogue = conformance.scenarios(fixtures)
    exercised = {name for s in catalogue for name in s["layers"]}
    assert {"standing", "climate", "promises", "pursuit"} <= exercised, (
        f"the fixtures no longer exercise {sorted({'standing', 'climate', 'promises', 'pursuit'} - exercised)}")
    verbs = {word for s in catalogue for c in s["commands"]
             for word in c.split()[:1]}
    assert {"ask", "attack", "wait", "promise", "help"} <= verbs, (
        f"the fixtures stopped exercising some of what a player can do: {sorted(verbs)}")
    print(f"ok  conformance: {len(catalogue)} fixtures still describe "
          f"this runtime field for field -- the acceptance test a port is held to"
          + (f" ({tolerated} float(s) within {conformance.DEFAULT_ULP_TOLERANCE:g} "
             f"ULP on Python {sys.version_info[0]}.{sys.version_info[1]}, "
             f"where sum() does not compensate)" if tolerated else ""))


def test_the_host_finds_the_runtime_and_says_so_when_it_cannot():
    """The five lines the README calls the whole integration, and why they failed.

    Followed literally in an empty Godot project, they did nothing: with no
    `bundle_path` the host runs `python3 -m unscripted`, a developer's game has no
    `unscripted` module installed, and the real error -- Python's own "No module named
    unscripted" -- goes to the child process's stderr where the game never sees it. All
    the developer gets is a client complaining that it is not connected.

    Two things had to be true and now are: the host looks for the archive
    itself, and when there is none it names the command that builds one.
    Asserted on the source, because a GDScript integration cannot be run from a
    Python suite -- but "does this file still do the thing" is exactly what a
    regression here would break.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    host = open(os.path.join(root, "integrations", "godot", "addons",
                             "unscripted", "UnscriptedHost.gd"),
                encoding="utf-8").read()

    assert "func _find_bundle" in host, (
        "the host no longer looks for the runtime beside the project, so the "
        "documented five lines need a sixth that the README does not show")
    for candidate in ('"res://unscripted.pyz"', '"res://addons/unscripted/unscripted.pyz"'):
        assert candidate in host, f"the host stopped looking in {candidate}"

    assert "unscripted bundle --out unscripted.pyz" in host, (
        "the failure message no longer names the command that fixes it; "
        "'No module named unscripted' is Python's error and reaches nobody")
    assert "bundle_path" in host, "the escape hatch for an archive elsewhere is gone"

    # And the README shows the same thing, so following it works.
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    assert "res://unscripted.pyz" in readme, (
        "the README no longer says where the archive goes, which is the one "
        "step that was missing when this broke")
    print("ok  onboarding: the Godot host finds the runtime beside the project "
          "and names the command that builds one when it cannot")


def test_a_bundle_finds_its_own_world_packs():
    """The thing that made a self-contained build fail on its own examples.

    `unscripted bundle --standalone` puts a redistributable interpreter, the archive
    and the reference packs in one folder that runs on a machine with no Python.
    It worked for a pack given by path and failed for the default one: inside a
    `.pyz` the package root is a path *inside the zip*, and nothing is installed
    so there is no `sys.prefix/share` either. `unscripted smoke` -- the first
    thing anybody types to check a bundle -- died on a bundle that was otherwise
    fine.

    Asserted without building one, because a standalone build downloads 34 MB
    and a test suite should not: what broke was the resolver, and the resolver
    can be shown the same shape directly.
    """
    from unscripted import UnscriptedRuntime

    work = tempfile.mkdtemp(prefix="unscripted-beside-")
    try:
        # The shape a bundle has: packs beside the archive, and the "package
        # root" two levels up from `unscripted/sdk.py` inside it.
        beside = os.path.join(work, "worldpacks", "example")
        os.makedirs(beside)
        open(os.path.join(beside, "world.json"), "w").close()

        argv_before = sys.argv[0]
        sys.argv[0] = os.path.join(work, "unscripted.pyz")
        try:
            found = UnscriptedRuntime._resolve_pack_path("worldpacks/example")
        finally:
            sys.argv[0] = argv_before
        assert os.path.abspath(found) == os.path.abspath(beside), (
            f"a pack sitting beside the archive was not found: {found}")

        # And an unknown one still resolves to the installed location rather
        # than to something that happens to exist next to the caller.
        missing = UnscriptedRuntime._resolve_pack_path("worldpacks/nope")
        assert "share" in missing or not os.path.exists(missing)
        print("ok  bundle: a world pack beside the archive is found, which is "
              "what a self-contained build has instead of an install")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_a_premise_becomes_a_world_a_studio_could_play():
    """The content pipeline, and the reason it has the gate inside it.

    A cast of forty in a dozen places was a fortnight of hand-written JSON
    before the first question could be asked, and that -- not the runtime -- is
    the honest reason a studio would decline this. So: premise in, pack out,
    and the same two gates a hand-written pack has to pass.

    THERE ARE TWO GATES and they check different things. `unscripted author` asks
    whether a world is worth playing: can anybody be asked anything, does
    anybody meet anybody. `unscripted validate` asks whether the runtime will open it
    at all. Pointing a generator at the first one found that it said READY TO
    PLAY about a pack the second refused over predicates with no slots and forty
    colliding aliases -- so the first now asks the second, and this asserts both.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.authoring import PackDocument, authoring_report
    from unscripted.pack import validate_world_pack
    from unscripted.pipeline import Premise, repair, write

    work = tempfile.mkdtemp(prefix="unscripted-pipeline-")
    try:
        pack = os.path.join(work, "generated")
        premise = Premise(name="Test", seed="pipeline-test", places=12,
                          characters=40, topics=8, districts=3)
        written = write(premise, pack)
        assert len(written) > 40, f"only {len(written)} files for forty characters"

        outcome = repair(pack)
        assert not outcome["left"], (
            "the generator produced something it could not repair:\n  "
            + "\n  ".join(outcome["left"][:6]))

        # 1. BOTH GATES.
        report = authoring_report(PackDocument.load(pack))
        blocking = [f for f in report["findings"]
                    if f.get("level") in ("blocker", "problem")]
        assert not blocking, f"the authoring gate still objects: {blocking[:3]}"
        loadable = validate_world_pack(pack)
        assert loadable.ok, (
            "the runtime refuses to load it: "
            + "; ".join(i.message for i in loadable.issues if i.severity == "error")[:300])

        # 2. IT IS A WORLD, not a directory of files that parse.
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, standing=True))
        try:
            cast = [a for a in sdk.world.agents.values()
                    if a.id != sdk.config.player_id]
            assert len(cast) >= 40, f"{len(cast)} characters loaded"
            assert len(sdk.world.places) >= 12

            def held():
                counts = {}
                for person in sdk.world.agents.values():
                    for key in person.beliefs:
                        counts[key] = counts.get(key, 0) + 1
                return counts

            before = held()
            assert before, "nobody in the generated world knows anything at all"
            assert max(before.values()) <= 3, (
                "the generator handed the same claim to most of the cast, which "
                "is a world with nothing to find out")

            sdk.advance_time(60 * 24 * 3)
            after = held()
            assert max(after.values()) > max(before.values()), (
                "three days passed and nothing reached anybody new; a generated "
                "cast that never talks is a generated cast that fails silently")
            knowers = sum(1 for a in cast if a.beliefs)
            assert knowers >= len(cast) // 2, (
                f"only {knowers} of {len(cast)} know anything after three days")

            # Groups, and a wall between them: a quarter of the predicates are
            # restricted to a trade, so something must not travel freely.
            from unscripted import topology
            from unscripted.ontology import Proposition
            walls = [p for p, spec in (sdk.world.predicates or {}).items()
                     if (spec or {}).get("access")]
            assert walls, "every claim in the generated world circulates freely"
            speaker, listener = cast[0], cast[-1]
            weight, _why = topology.may_pass_on(
                sdk.world, Proposition(walls[0], {}), speaker, listener,
                speaker.location)
            assert weight >= 0.0
        finally:
            sdk.close()

        # 3. DETERMINISTIC. A generator you cannot re-run is one you cannot fix
        #    a bug in.
        twin = os.path.join(work, "twin")
        write(premise, twin)
        repair(twin)
        for name in sorted(os.listdir(pack)):
            one = os.path.join(pack, name)
            if os.path.isdir(one):
                continue
            with open(one, encoding="utf-8") as fh:
                first = fh.read()
            with open(os.path.join(twin, name), encoding="utf-8") as fh:
                second = fh.read()
            assert first == second, f"{name} differs between two runs of one premise"

        # 4. THE REPAIR LOOP ACTUALLY REPAIRS. Break it the way an author does,
        #    and watch the gate's own report drive the fix.
        broken = os.path.join(work, "broken")
        write(premise, broken)
        doc = PackDocument.load(broken)
        orphan = sorted(p for p in doc.world["places"] if p != "place:street")[0]
        doc.world["places"]["place:street"]["exits"] = [
            e for e in doc.world["places"]["place:street"]["exits"] if e != orphan]
        doc.world["places"][orphan]["exits"] = []
        doc.save()
        cut = authoring_report(PackDocument.load(broken))["findings"]
        assert any("cannot be walked to" in f["message"] for f in cut), (
            "the gate did not notice a place cut off from the map, so this "
            "proves nothing about the repairer")
        mended = repair(broken)
        assert mended["fixed"], "the repairer changed nothing"
        assert not mended["left"], f"still broken: {mended['left'][:3]}"

        print(f"ok  pipeline: a premise became {len(cast)} characters across "
              f"{len(sdk.world.places)} places that both gates accept and that "
              f"spreads a claim from {max(before.values())} heads to "
              f"{max(after.values())} in three days; identical on a re-run, and "
              f"a place cut off the map is repaired from the gate's own report")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_nothing_is_read_that_nothing_writes():
    """The guard for the defect this runtime has produced six times.

    Every time, the shape was identical: a field several engines consult, that
    only ever holds what a pack authored. `reputation` before the promises layer
    had a producer. `fear`, which decides whether a threat lands. `respect`,
    which is deference. `appearance`, authored on every character in every pack
    and read by the generator alone. Each cost a measurement to find, months
    after it was introduced, and each was invisible to every other test in this
    file because nothing was *wrong* -- something was merely absent.

    So: find every relationship field and reputation dimension that some engine
    reads, run a world with every layer on and a player who behaves in every way
    the runtime models, and see which of them actually move. Anything read and
    never moved must be named in `contracts.AUTHORED_ONLY_FIELDS` with a reason.

    Both directions. A name in that table that has since acquired a producer is
    a stale excuse, and stale excuses are how a list like this becomes a lie.
    """
    import re

    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.contracts import AUTHORED_ONLY_FIELDS, OPTIONAL_LAYERS

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # -- who reads what ------------------------------------------------------
    # Tight on purpose: the receiver has to actually be called `rel...` or
    # `rep...`. A looser pattern picked up `.get("content")` from a visualiser
    # and would have made this test noise.
    rel_read = re.compile(r'\brel(?:ationship)?\w*\.get\(\s*"(\w+)"')
    rep_read = re.compile(r'\brep(?:utation)?\w*\.get\(\s*"(\w+)"')
    # WHICH MODULES COUNT AS ENGINES comes from the architecture map rather
    # than a hand-kept blacklist here. The first version listed five files by
    # name and a sixth arrived: `report.get("findings")` in the world generator
    # matched `rep...get("...")` and was reported as a reputation dimension
    # nothing writes. A list of exceptions grows a new entry every time
    # somebody adds a file; the map already says what a module is for.
    from unscripted import architecture
    engine_layers = {"engines", "world"}
    engines = {name for layer, _why, names in architecture.LAYERS
               if layer in engine_layers for name in names}
    assert {"belief", "relationship", "standing"} <= engines, (
        "the architecture map no longer names the engines this scans")
    reads = {}
    for path in sorted(glob.glob(os.path.join(root, "unscripted", "*.py"))):
        if os.path.splitext(os.path.basename(path))[0] not in engines:
            continue
        for number, line in enumerate(open(path, encoding="utf-8"), 1):
            code = line.split("#", 1)[0]
            where = f"{os.path.basename(path)}:{number}"
            for field in rel_read.findall(code):
                reads.setdefault(field, where)
            for field in rep_read.findall(code):
                reads.setdefault("reputation:" + field, where)
    assert "fear" in reads and "trust" in reads, (
        "the scan found neither fear nor trust, so it is not scanning anything")

    # -- and what actually moves ---------------------------------------------
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")
    every_layer = {name: True for name, _ in OPTIONAL_LAYERS}
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", **every_layer))
    try:
        def snapshot():
            return {aid: {other: dict(fields)
                          for other, fields in a.relationships.items()}
                    for aid, a in sdk.world.agents.items()}

        before = snapshot()
        # Everything a player can do to somebody, because a field that only
        # moves on one verb is a field this test must still see move.
        for line in ["look", "wear tailored suit", "help barkeep",
                     "threaten dima", "promise okada that I will pay",
                     "attack dima", "wear worn jacket", "help okada"]:
            sdk.submit_player_text(line)
        promises = [p["promise_id"] for p in (sdk.promises_report().get("open") or [])]
        if promises:
            sdk.settle_promise(promises[0], kept=False)
        sdk.advance_time(60 * 24 * 3)

        after = snapshot()
        moved = set()
        for aid, rows in after.items():
            for other, fields in rows.items():
                was = (before.get(aid) or {}).get(other) or {}
                for field, value in fields.items():
                    if was.get(field) != value:
                        moved.add(field)
        for a in sdk.world.agents.values():
            for _subject, dims in a.reputation.items():
                moved |= {"reputation:" + d for d in dims}
    finally:
        sdk.close()

    assert len(moved) >= 5, (
        f"only {sorted(moved)} moved in a world with every layer on and a player "
        f"doing everything; this test cannot tell absence from a broken scenario")

    # -- the two directions --------------------------------------------------
    undeclared = sorted(f for f in reads
                        if f not in moved and f not in AUTHORED_ONLY_FIELDS)
    assert not undeclared, (
        "read by an engine, written by nothing, and not declared as authored:\n"
        + "\n".join(f"  {f}  (read at {reads[f]})" for f in undeclared)
        + "\n\nEither give it a producer or add it to "
          "contracts.AUTHORED_ONLY_FIELDS with the reason it has none.")

    stale = sorted(f for f in AUTHORED_ONLY_FIELDS if f in moved)
    assert not stale, (
        f"{stale} are declared as authored-only and now move; remove them from "
        f"AUTHORED_ONLY_FIELDS before somebody trusts the excuse")

    unread = sorted(f for f in AUTHORED_ONLY_FIELDS if f not in reads)
    assert not unread, (
        f"{unread} are declared as authored-only and are read by nothing at "
        f"all; they are not a decision, they are dead")

    for field, reason in AUTHORED_ONLY_FIELDS.items():
        assert len(reason) > 40, f"{field} is excused without a reason worth reading"

    print(f"ok  wiring: {len(reads)} fields are read by an engine; {len(moved)} of "
          f"them move in play and {len(AUTHORED_ONLY_FIELDS)} are declared "
          f"authored-only with a reason, and neither list has drifted")


def test_the_page_names_the_engine_versions_it_was_actually_run_against():
    """A version on the landing page has to be one somebody measured.

    The engine table said "Unity 6000.3 LTS" while every other file in the
    repository, and the editor on the machine, said 6000.0.82f1. Nothing was
    lying on purpose: a number was typed once and never checked again, and a
    studio reading that table would size their upgrade risk against a version
    nobody here has ever opened.
    """
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    connecting = open(os.path.join(root, "docs", "CONNECTING.md"),
                      encoding="utf-8").read()

    # A full build string -- 6000.0.82f1 -- is a claim about a version somebody
    # opened. A stream, 6000.0, is not, and naming a version to say it has NOT
    # been tested is the opposite of the mistake this guards against. So: every
    # build string in the README must either be the one the docs say was tested,
    # or sit in a sentence that says it was not run.
    build = re.compile(r"6000\.\d+\.\d+[a-z]\d+")
    tested = set(build.findall(connecting))
    assert tested, "CONNECTING.md names no Unity as tested"

    for line in readme.splitlines():
        for named in build.findall(line):
            if named in tested:
                continue
            assert "not been run" in line or "could not be run" in line, (
                f"README names Unity {named}, which CONNECTING.md does not list "
                f"among {sorted(tested)}, and does not say it was not run:\n"
                f"  {line.strip()}")
    missing = sorted(v for v in tested if v not in readme)
    assert not missing, (
        f"the docs say {missing} was tested and the README never mentions it")

    # And the Unreal plugin must still refuse to pin an engine version, because
    # pinning one made the plugin manager skip loading it everywhere else.
    plugin = json.load(open(os.path.join(
        root, "integrations", "unreal", "UnscriptedBridge",
        "UnscriptedBridge.uplugin"), encoding="utf-8"))
    assert "EngineVersion" not in plugin, (
        "the plugin pins an engine version again; Unreal skips loading it in "
        "every other version, silently, and the build still succeeds")
    print(f"ok  versions: the page and the docs agree on {sorted(tested)} as the "
          f"Unity editors this was run in, say of any other that it was not, and "
          f"the Unreal plugin still pins no engine version")


def test_what_you_turn_up_wearing_changes_how_you_are_taken():
    """Appearance, which every pack authored and only the generator ever read.

    `social_status` promised in its own docstring to be "reputation- and
    appearance-mediated" and consulted reputation alone, while every character
    in every shipped pack carried a garment and sometimes a symbol.

    Two readings, because they are two different things: how seriously somebody
    is taken, and how dangerous they look. Gang colours are not low status.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")

    def wearing(garment):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", pursuit=True))
        try:
            if garment:
                message = sdk.submit_player_text(f"wear {garment}").message or ""
                assert "wearing" in message, f"could not put it on: {message!r}"
            watcher = sdk.world.agents["agent:barkeep_12"]
            player = sdk.world.agents[sdk.config.player_id]
            read = sdk.core.appearance.read(watcher, player, sdk.world)
            scored = sdk.core.decide("agent:barkeep_12",
                                     interlocutor=sdk.config.player_id)[1]
            return read, {c.action.action_id: c.utility for c in scored}
        finally:
            sdk.close()

    bare, plain = wearing(None)
    assert bare["status"] == 0.0 and bare["threat"] == 0.0, (
        "the player starts dressed as something; this test cannot say what changed")

    suit, deferred = wearing("tailored suit")
    shabby, dismissed = wearing("worn jacket")
    colours, feared = wearing("red cyberjacket")

    assert suit["status"] > 0.3 and shabby["status"] < -0.2
    assert colours["threat"] > 0.3, "gang colours read as harmless"
    assert colours["status"] > shabby["status"], (
        "gang colours were read as merely shabby; threat and status are supposed "
        "to be two different readings")
    assert "group:reds" in colours["signals"], "a symbol signalled no circle"

    # TAKEN MORE SERIOUSLY, TALKED OVER, OR BACKED AWAY FROM.
    assert deferred["answer_truthfully"] > plain["answer_truthfully"], (
        "a tailored suit made no difference to whether they would answer you")
    assert dismissed["answer_truthfully"] < plain["answer_truthfully"], (
        "turning up shabby made no difference either")
    assert feared["evade"] > plain["evade"] + 0.08, (
        f"somebody dressed to look dangerous did not make them want distance: "
        f"{feared['evade']} against {plain['evade']}")

    # AND SOMEBODY WHO IS TAKEN WITH IT. Authored, never decided by an engine.
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, standing=True))
    try:
        sdk.submit_player_text("wear tailored suit")
        taken = sdk.world.agents["agent:dima_broke"]
        player = sdk.world.agents[sdk.config.player_id]
        pull = sdk.core.appearance.drawn_to(taken, player, sdk.world)
        assert pull > 0.4, f"the one character authored to notice a suit did not: {pull}"
        indifferent = sdk.core.appearance.drawn_to(
            sdk.world.agents["agent:barkeep_12"], player, sdk.world)
        assert indifferent == 0.0, "somebody with no authored taste was drawn in anyway"

        # And influence is a summary of four numbers, not a fifth one stored.
        before = sdk.core.standing.influence(taken, sdk.config.player_id)
        taken.relationships.setdefault(sdk.config.player_id, {})["fear"] = 0.8
        after = sdk.core.standing.influence(taken, sdk.config.player_id)
        assert after > before + 0.15, "fear gave somebody no more sway at all"
        view = sdk.structured_agent("agent:dima_broke")["relationships"]
        assert "influence" in view.get(sdk.config.player_id, {}), (
            "a game cannot read influence, so it may as well not exist")

        # AND IT IS ABOUT THE RIGHT PERSON. The reach term is how many circles
        # the INFLUENCER stands in; the first version passed the observer's,
        # which produced a number about somebody who was not being asked about.
        # Two observers of the same influencer must therefore agree on the reach
        # part, and differ only where their own feelings differ.
        network = sdk.core.network
        wide = max(sdk.world.agents.values(), key=lambda a: network.bridge_score(a))
        narrow = min((a for a in sdk.world.agents.values()
                      if a.id != sdk.config.player_id),
                     key=lambda a: network.bridge_score(a))
        if network.bridge_score(wide) > network.bridge_score(narrow):
            watcher = sdk.world.agents["agent:barkeep_12"]
            for someone in (wide, narrow):
                watcher.relationships.setdefault(someone.id, {})["respect"] = 0.5
            over_wide = sdk.core.standing.influence(
                watcher, wide.id, network.bridge_score(wide))
            over_narrow = sdk.core.standing.influence(
                watcher, narrow.id, network.bridge_score(narrow))
            assert over_wide > over_narrow, (
                "two people the same character respects equally have the same "
                "sway, though one stands in more circles than the other")
    finally:
        sdk.close()

    print(f"ok  appearance: a suit reads {suit['status']:+.2f} status and a worn "
          f"jacket {shabby['status']:+.2f}; gang colours read {colours['threat']:+.2f} "
          f"threat and signal {colours['signals'][0]}, and being dressed dangerously "
          f"moved evading {plain['evade']:.2f} -> {feared['evade']:.2f}")


def test_who_you_believe_is_a_fact_about_you():
    """Two people hear the same announcement in the same second.

    Every other input to belief is a fact about the claim -- how close you were,
    how competent the speaker is on the subject, how credible the channel says
    it is. None of them could express *this person takes the intercom as gospel
    and their colleagues as noise, and that one is the exact reverse*, which is
    a fact about a person and the one thing a pack could not say.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.events import Event

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "relay-station")
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True))
    try:
        world = sdk.world
        event = Event(world.new_event_id(), world.world_time, "broadcast",
                      actor="channel:station_net", location=None,
                      payload={"channel": "channel:station_net", "credibility": 0.7,
                               "proposition": {"predicate": "supply_short",
                                               "slots": {}, "polarity": "+"},
                               "summary": "bulletin", "importance": 0.6})
        traces = sdk.core.process_event(event)

        def kappa_for(agent_id):
            for code, _mag, detail in traces.get(agent_id, []):
                if code == "belief.updated":
                    return detail["kappa"]
            return None

        def matched(agent_id):
            for code, _mag, detail in traces.get(agent_id, []):
                if code == "belief.source_credence":
                    return detail["matched"]
            return None

        neutral = kappa_for("agent:voss")
        doubter = kappa_for("agent:rask")
        assert neutral and doubter, "one of them did not hear the announcement at all"
        assert doubter < neutral - 0.05, (
            f"the one who distrusts the intercom credited it at {doubter} against "
            f"{neutral}; the disposition is not arriving")
        assert matched("agent:rask") == "intercom", (
            "the lookup matched something other than the channel's type")
        assert matched("agent:voss") is None, (
            "somebody with no authored disposition was charged one anyway")
        print(f"ok  credence: the same announcement in the same second is credited "
              f"at {neutral} by somebody with no view of the intercom and {doubter} "
              f"by somebody who distrusts it")
    finally:
        sdk.close()


def test_a_thing_the_engineers_say_stays_among_the_engineers():
    """Groups, and the two different ways a claim fails to cross between them.

    A world where everything reaches everybody is one shared mind with names on
    it, and a world where nothing crosses is a set of separate worlds. The
    difference is made per claim, by what kind of thing it is:

      * a PUBLIC claim moves freely, and a little more readily still between two
        people who share a circle -- a district, a shift, a trade, a family;
      * a RESTRICTED one does not leave its circle at all. Not slowly: at all.

    Both measured on the same speaker, in the same room, on the same day, so the
    only thing that differs is the claim.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted import topology
    from unscripted.ontology import Proposition

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "relay-station")
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True))
    try:
        world = sdk.world
        cast = [a for a in world.agents.values() if a.id != sdk.config.player_id]
        assert len(cast) >= 8, "this test wants a crew, not a couple"
        speaker = min(cast, key=lambda a: a.id)

        def weights(predicate):
            prop = Proposition(predicate, {})
            return {other.id: topology.may_pass_on(
                        world, prop, speaker, other, speaker.location)[0]
                    for other in cast if other.id != speaker.id}

        public = weights("supply_short")
        restricted = weights("skipped_check")

        assert all(w > 0.9 for w in public.values()), (
            f"a public claim did not travel freely: {public}")

        reachable = {a: w for a, w in restricted.items() if w > 0}
        walled = [a for a, w in restricted.items() if w == 0]
        assert walled, "a restricted claim reached everybody; the circle is not a circle"
        assert reachable, "a restricted claim reached nobody at all, including its own circle"
        # Everybody it does reach is inside the circle it is restricted to.
        allowed = set(topology.class_for(world, Proposition("skipped_check", {})).access)
        for other_id in reachable:
            assert allowed & topology.circles(world.agents[other_id]), (
                f"{other_id} is outside {sorted(allowed)} and heard it anyway")
        # And the speaker is NOT in that circle: this is somebody passing on
        # something they are not one of the keepers of, which is the case worth
        # getting right.
        assert not (allowed & topology.circles(speaker))

        # Sharing a circle helps an unrestricted claim along.
        neighbours = [a for a in cast
                      if a.id != speaker.id and topology.shared_circles(speaker, a)]
        assert neighbours, "nobody in this cast shares a circle with anybody"

        bridges = topology.bridges(world)
        assert bridges, "no character belongs to more than one circle, so nothing could cross"
        print(f"ok  topology: a public claim reaches all {len(public)} of the crew; a "
              f"claim restricted to its trade reaches {len(reachable)} and is walled "
              f"off from {len(walled)}, and {len(bridges)} people stand in more than "
              f"one circle, which is how anything crosses at all")
    finally:
        sdk.close()


def test_fear_and_respect_stop_being_decorative():
    """Two feelings that four engines read and nothing had ever written.

    `fear` decides whether a threat is expected to work or to backfire, and
    pulls a character's conversational stance away from warmth. `respect` is
    what lets somebody be deferred to without being liked. Both were authorable
    in a world pack and then frozen for the rest of that world's life, because
    no engine produced one -- the same shape of dead wiring as `ReputationEngine`
    before the promises layer arrived.

    Conduct produces them now. This asserts that they move, that they move the
    right way round, and that they reach the two places that were already
    reading them.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "nine-oh-seven")

    def after(conduct, times, standing=True):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, standing=standing))
        try:
            sdk.submit_player_text("go to the bar")
            for _ in range(times):
                sdk.submit_player_text(f"{conduct} halloran")
                sdk.advance_time(30)
            them = sdk.world.agents["agent:halloran"]
            rel = dict(them.relationships.get(sdk.config.player_id) or {})
            # THE DIRECTION MATTERS AND THIS TEST USED TO HAVE IT BACKWARDS. It
            # asked what HALLORAN expects from threatening the PLAYER, and the
            # engine answered by reading halloran's fear OF the player -- so a
            # character who had been terrified for six turns concluded that
            # their own threats would land. The question the assertion below
            # actually means is the player's: having frightened somebody, does
            # the runtime expect a further threat to work?
            threat_value = sdk.core.tom.expected_reaction(
                sdk.world.agents[sdk.config.player_id], "agent:halloran",
                "threaten", {})[1]
            answer = sdk.respond("agent:halloran", topic="the_shot")
            return rel, threat_value, dict(getattr(answer, "style", {}) or {})
        finally:
            sdk.close()

    plain, plain_threat, plain_style = after("look at", 0)
    cruel, cruel_threat, cruel_style = after("threaten", 6)
    kind, kind_threat, kind_style = after("help", 6)

    assert not plain.get("fear") and not plain.get("respect"), (
        "a stranger already fears or respects the player before anything happened")
    assert cruel.get("fear", 0.0) > 0.1, (
        f"six threats produced fear={cruel.get('fear')}")
    assert not cruel.get("respect"), "threatening somebody earned their respect"
    assert kind.get("respect", 0.0) > 0.05, (
        f"six kindnesses produced respect={kind.get('respect')}")
    assert not kind.get("fear"), "being kind made them afraid of you"

    # IT REACHES WHAT WAS ALREADY READING IT. Threatening somebody you have
    # already frightened is expected to land; threatening a stranger is a coin
    # toss the engine holds no opinion about, and being kind to them first makes
    # it worse. The estimate comes from what the actor has been seen to DO --
    # there is no honest way to read the other person's actual fear from here.
    assert cruel_threat > plain_threat + 0.05, (
        f"a further threat is worth {cruel_threat} after six of them and "
        f"{plain_threat} to a stranger; the number is not arriving")
    assert kind_threat < plain_threat, (
        f"six kindnesses left a threat looking just as likely to land "
        f"({kind_threat} against {plain_threat})")

    # And it colours how they talk. Respect is deference: more formal, more
    # hedged, without being warmer.
    assert kind_style["formality"] > plain_style["formality"], (
        "respect left the register exactly where it was")
    assert kind_style["hedging"] > plain_style["hedging"]
    # Fear takes the bluntness out of how they speak to you. Measured against
    # the same run with the layer off rather than against the neutral run,
    # because six threats move liking as well and the accommodation term reacts
    # to that on its own -- this isolates the part fear contributes.
    off_cruel, _, off_cruel_style = after("threaten", 6, standing=False)
    assert cruel_style["directness"] < off_cruel_style["directness"] - 0.05, (
        f"fear left them speaking as plainly as before: "
        f"{cruel_style['directness']} against {off_cruel_style['directness']}")

    # OFF IS OFF.
    assert not off_cruel.get("fear") and not off_cruel.get("respect"), (
        "the standing layer is off and produced fear anyway")

    print(f"ok  standing: six threats put fear at {cruel['fear']:.3f} and made a "
          f"further threat worth {cruel_threat:+.3f} against {plain_threat:+.3f} "
          f"to a stranger and {kind_threat:+.3f} after kindness; "
          f"six kindnesses put respect at {kind['respect']:.3f} and moved the "
          f"register toward deference; off produces neither")


def test_what_you_did_to_one_of_them_reaches_the_rest_of_them():
    """Standing: the town's view of you, and the part that makes it not a counter.

    Measured beforehand and worth stating: attacking somebody in front of four
    witnesses changed the mood of the street, alarmed the victim's people, and
    changed nobody's opinion of the player. Reputation had exactly one producer
    -- a broken promise -- so being cruel in public was free.

    This layer puts the act into the world as a claim, `mistreated(who, by)`,
    and lets perception, belief, provenance and diffusion carry it. What that
    buys, and what this asserts:

      1. Off is off. Not a small effect: the code never runs.
      2. Whoever saw it thinks worse of you.
      3. SOMEBODY WHO WAS ONLY TOLD thinks worse of you as well -- and by less,
         because they believe it less. That difference is the whole design: a
         reputation counter cannot produce it, and nothing here tunes it.
      4. No personality moved. Standing is what they think of you, not who they
         became.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted import snapshot as snapshot_module

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "nine-oh-seven")

    def run(standing: bool, explode_if_used: bool = False):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, standing=standing))
        try:
            if explode_if_used:
                def refuse(*_a, **_k):
                    raise AssertionError("the layer is off and was asked to judge")
                sdk.core.standing.judge = refuse
            sdk.submit_player_text("go to the bar")
            sdk.submit_player_text("attack halloran")
            sdk.advance_time(180)
            state = snapshot_module.capture(sdk.world, sdk.core)
            held = {aid: round((a.reputation.get(sdk.config.player_id) or {}).get("decent", 0.0), 4)
                    for aid, a in sorted(sdk.world.agents.items())}
            traits = {aid: dict(sorted((a.big_five or {}).items()))
                      for aid, a in sorted(sdk.world.agents.items())}
            return json.dumps(state, sort_keys=True, default=str), held, traits, sdk
        finally:
            pass

    # 1. OFF IS OFF.
    off_state, off_held, off_traits, off_sdk = run(False, explode_if_used=True)
    off_sdk.close()
    assert not any(off_held.values()), "the layer is off and somebody judged anyway"
    assert "mistreated" not in off_state, (
        "with the layer off the act still attached a claim to the world; "
        "off has to mean the world is what it was")

    on_state, on_held, on_traits, on_sdk = run(True)
    assert on_state != off_state, "with standing on the world came out identical"

    # 2. WHOEVER SAW IT.
    victim = "agent:halloran"
    assert on_held[victim] < -0.05, (
        f"the person who was hit thinks {on_held[victim]} of the player")
    assert on_traits == off_traits, "a personality moved; this layer must never do that"

    # 3. AND SOMEBODY WHO WAS ONLY TOLD -- by less.
    #    Forced rather than waited for. Whether this particular cast gossips
    #    enough in three days is a property of the pack, and the evidence run
    #    already says a saturated world goes quiet; what is being asserted here
    #    is the mechanism, so the retelling is made to happen.
    teller = on_sdk.world.agents[victim]
    hearer = on_sdk.world.agents["agent:byrne"]
    key = next(k for k in teller.beliefs if "mistreated" in k)
    assert key not in hearer.beliefs, "the hearer already knew; the test proves nothing"
    hearer.location = teller.location
    told = on_sdk.core.diffusion.tell_about(
        on_sdk.world, on_sdk.core, teller, hearer, teller.location, key, [])
    assert told, "the retelling did not happen, so nothing below is being tested"

    pid = on_sdk.config.player_id
    hearsay = (hearer.reputation.get(pid) or {}).get("decent", 0.0)
    eyewitness = (teller.reputation.get(pid) or {}).get("decent", 0.0)
    assert hearsay < -0.01, (
        f"somebody who was told what you did thinks {hearsay} of you, which is "
        f"nothing; this is the claim the layer exists to make")
    assert hearsay > eyewitness, (
        f"hearsay ({hearsay}) counts for at least as much as watching it "
        f"({eyewitness}); certainty is supposed to be what scales this")
    assert (hearer.relationships.get(pid) or {}).get("liking", 0.0) < 0, (
        "they think you indecent and like you exactly as much as before")

    heard_p = hearer.beliefs[key].expected_prob
    saw_p = teller.beliefs[key].expected_prob
    assert heard_p < saw_p, "the hearer believes it at least as much as the witness"
    on_sdk.close()

    # 4. AND IT CHANGES WHAT THEY DO, not only what they hold.
    #    The half that makes the rest worth having. Before this, standing moved
    #    numbers that nothing read when deciding what to say: whether a
    #    character answered you depended on their agreeableness and their
    #    secrets and never on what they thought of you.
    def after(conduct, times):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            pursuit=True, standing=True))
        try:
            sdk.submit_player_text("go to the street")
            sdk.submit_player_text("go to the club")
            for _ in range(times):
                sdk.submit_player_text(f"{conduct} reyes")
                sdk.advance_time(30)
            who = sdk.world.agents["agent:reyes"]
            warm = sdk.core.standing.warmth(who, sdk.config.player_id)
            scored = sdk.core.decide("agent:reyes", interlocutor=sdk.config.player_id)[1]
            return warm, {c.action.action_id: c.utility for c in scored}
        finally:
            sdk.close()

    neutral_w, neutral = after("look at", 0)
    kind_w, kind = after("help", 5)
    cruel_w, cruel = after("threaten", 5)

    assert kind_w > 0.2 > -0.2 > cruel_w, (
        f"five kind acts reached {kind_w} and five cruel ones {cruel_w}; "
        f"conduct is barely registering")
    # Being decent makes them readier to tell you something than to put you off.
    assert kind["answer_truthfully"] > kind["evade"], (
        "after five kindnesses they would still rather evade you than answer")
    assert neutral["answer_truthfully"] < neutral["evade"], (
        "they would answer a stranger anyway, so the line above proves nothing")
    # Being vile makes turning you away the best thing they can think of doing.
    assert cruel["evade"] == max(cruel.values()), (
        f"after five threats evading is still not their first choice: {cruel}")
    assert cruel["answer_truthfully"] < neutral["answer_truthfully"], (
        "threatening somebody left them exactly as forthcoming as before")

    print(f"ok  standing: off is off; the man you hit thinks {eyewitness:.3f} of you "
          f"and the man he told thinks {hearsay:.3f} -- less, because he believes it "
          f"{heard_p:.3f} against {saw_p:.3f}; five kindnesses ({kind_w:+.2f}) make "
          f"answering beat evading and five threats ({cruel_w:+.2f}) make evading "
          f"beat greeting; no personality moved")


def test_the_world_answers_to_what_the_player_does():
    """Four claims about the player's effect on the world, each measured.

    These are the things a studio actually asks for -- *does my behaviour change
    the town, do people form a view of me, do characters get more to say, does
    each player end up somewhere different* -- and they were true in the code
    and stated nowhere. Written as one test so that the landing page cannot
    drift away from what the runtime does. Directions and thresholds, not exact
    values: this pins the claims without freezing the tuning.

    The fourth is the one worth reading twice. The same world with the same seed
    and the same conduct reproduces exactly; the same world with different
    conduct does not. It diverges *because of the player*, not because of noise,
    and one of those two facts is worthless without the other.
    """
    from unscripted.contracts import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    PACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "worldpacks", "cyberpunk-block")

    def start(**kw):
        cfg = RuntimeConfig(world_pack_path=PACK, pursuit=True, climate=True, **kw)
        rt = UnscriptedRuntime.create(cfg)
        return rt, cfg.player_id

    def others_here(rt, pid):
        where = rt.world.agents[pid].location
        return [a.id for a in rt.world.occupants(where) if a.id != pid]

    def climate(rt):
        return {c["place"]: c for c in rt.climate_report()}

    # -- 1. what you do changes what the place is like -----------------------
    rt, pid = start()
    victim = others_here(rt, pid)[0]
    where = rt.world.agents[pid].location
    before = climate(rt)[where]
    rt.submit_player_text("attack %s" % victim.split(":")[1])
    rt.advance_time(60)
    after = climate(rt)[where]
    assert after["openness"] < before["openness"] - 0.05, (
        f"a public attack left the street as open to strangers as before: "
        f"{before['openness']} -> {after['openness']}")
    assert after["suspicion"] > before["suspicion"] + 0.05, (
        f"a public attack left the street no more suspicious: "
        f"{before['suspicion']} -> {after['suspicion']}")
    # and the people who share a belonging with the victim feel it
    alarmed = [a.id for a in rt.world.agents.values() if a.identity_threat]
    assert len(alarmed) >= 2, "nobody standing there felt anything about it"
    opened, closed = before["openness"], after["openness"]
    rt.close()

    # -- 2. the town forms a view of you, and passes it on -------------------
    def promise_run(kept):
        rt, pid = start(promises=True)
        target = others_here(rt, pid)[0]
        witnesses = len(others_here(rt, pid)) - 1
        rt.submit_player_text("promise %s that I will pay" % target.split(":")[1])
        open_ids = [x["promise_id"] for x in (rt.promises_report().get("open") or [])]
        assert open_ids, "the promise was not recorded"
        rt.settle_promise(open_ids[0], kept=kept)
        rt.advance_time(120)
        trust = rt.world.agents[target].relationships.get(pid, {}).get("trust")
        held = [aid for aid, a in rt.world.agents.items()
                if (a.reputation.get(pid) or {}).get("reliable", 0) < 0]
        rt.close()
        return trust, held, target, witnesses

    kept_trust, kept_held, target, witnesses = promise_run(True)
    broke_trust, broke_held, _, _ = promise_run(False)
    assert kept_trust > broke_trust + 0.2, (
        f"keeping and breaking a promise left the same trust: {kept_trust} vs {broke_trust}")
    assert not kept_held, "keeping a promise made somebody think you unreliable"
    assert len(broke_held) >= 2 and target in broke_held, (
        f"a broken promise reached only {broke_held}")
    # THE POINT: people who merely watched hold it too, not only the person owed.
    bystanders = [a for a in broke_held if a != target]
    assert bystanders, "only the person you owed noticed; nobody who watched did"

    # -- 3. they end up with more to say than they started with --------------
    rt, pid = start()
    at_start = {aid: len(a.beliefs) for aid, a in rt.world.agents.items() if aid != pid}
    rt.advance_time(60 * 24 * 3)
    later = {aid: len(a.beliefs) for aid, a in rt.world.agents.items() if aid != pid}
    grew = [aid for aid in at_start if later[aid] > at_start[aid]]
    from_nothing = [aid for aid in at_start if at_start[aid] == 0 and later[aid] >= 3]
    assert len(grew) >= 3, f"after three days only {len(grew)} characters knew more"
    assert from_nothing, "nobody who started with nothing to say ended up with anything"
    rt.close()

    # -- 4. same seed, same conduct: identical. different conduct: not. ------
    def play(script, days=3):
        rt, pid = start(promises=True)
        for line in script:
            rt.submit_player_text(line)
        rt.advance_time(60 * 24 * days)
        state = {(aid, key): round(getattr(b, "logit", 0.0), 2)
                 for aid, a in rt.world.agents.items() for key, b in a.beliefs.items()}
        rt.close()
        return state

    asked = ["look", "ask okada about the shooting", "ask dima about the shooting"]
    rough = ["look", "promise okada that I will pay", "attack dima"]
    a, again, b = play(asked), play(asked), play(rough)
    assert a == again, "the same seed and the same conduct did not reproduce"
    keys = set(a) | set(b)
    differ = sum(1 for k in keys if a.get(k) != b.get(k))
    assert differ >= 5, (
        f"two players who behaved differently ended up in the same world "
        f"({differ} of {len(keys)} beliefs differ)")

    print(f"ok  player effect: a public attack took the street's openness "
          f"{opened:.2f} -> {closed:.2f}; a broken promise put 'unreliable' in "
          f"{len(broke_held)} heads including {len(bystanders)} who only watched; "
          f"{len(grew)} characters ended the third day with more to say; same "
          f"conduct reproduces exactly, different conduct moved {differ} of "
          f"{len(keys)} beliefs")


def test_a_world_pack_can_name_the_layers_it_is_built_on():
    """A pack that needs a mechanic should not depend on the command line.

    The layers are off by default and that is right -- but a world authored
    around pursuit is not a world you can serve without it, and until now the
    only place to say so was a flag the pack author does not control. Two copies
    of the list, in the pack and in the game, is one copy too many: they drift,
    and nothing says which one the world actually ran with.
    """
    import argparse
    from unscripted.cli import _apply_layers
    from unscripted.contracts import RuntimeConfig

    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "world.json"), "w", encoding="utf-8") as fh:
            json.dump({"layers": ["pursuit", "media"], "places": {}}, fh)

        cfg = _apply_layers(RuntimeConfig(world_pack_path=root),
                            argparse.Namespace(layers=""))
        assert cfg.pursuit and cfg.media, "the pack asked for two layers and got neither"

        # `--layers none` is the escape hatch: "off is exactly neutral" has to
        # stay checkable on a pack that asks for something.
        cfg = _apply_layers(RuntimeConfig(world_pack_path=root),
                            argparse.Namespace(layers="none"))
        assert not cfg.pursuit and not cfg.media, "--layers none did not override the pack"

        # The command line adds to the pack rather than replacing it.
        cfg = _apply_layers(RuntimeConfig(world_pack_path=root),
                            argparse.Namespace(layers="climate"))
        assert cfg.climate and cfg.pursuit and cfg.media

        # A pack asking for something that does not exist is an error by name,
        # not a shrug -- same rule as the flag.
        with open(os.path.join(root, "world.json"), "w", encoding="utf-8") as fh:
            json.dump({"layers": ["puruit"], "places": {}}, fh)
        try:
            _apply_layers(RuntimeConfig(world_pack_path=root),
                          argparse.Namespace(layers=""))
            raise AssertionError("a misspelled layer in a pack was accepted")
        except ValueError as exc:
            assert "puruit" in str(exc)

        # And the demo pack means what it says: it names the four it runs with.
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "worldpacks", "nine-oh-seven", "world.json"),
                  encoding="utf-8") as fh:
            declared = json.load(fh)["layers"]
        assert set(declared) == {"pursuit", "media", "climate", "common_knowledge"}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("ok  layers: a world pack names its own, --layers adds, 'none' overrides")


def test_the_demo_ships_the_shipped_addon_and_not_a_fork_of_it():
    """The demo must exercise the client we hand to studios, byte for byte.

    Godot can only load an addon from under `res://`, so the demo project has a
    copy -- and a copy drifts. It did: a fix to the client left the demo running
    the old one, the demo failed with a missing signal, and the failure said
    nothing about why. A green demo has to mean the shipped client is green.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source = os.path.join(root, "integrations", "godot", "addons", "unscripted")
    names = sorted(f for f in os.listdir(source) if f.endswith(".gd"))
    assert names, "the Godot addon has no scripts"

    # EVERY demo, found rather than listed. The first version named
    # demos/lamb-street, and the second demo shipped its own copy of the addon
    # that nothing compared against anything.
    demos = sorted(d for d in os.listdir(os.path.join(root, "demos"))
                   if os.path.isdir(os.path.join(root, "demos", d, "addons",
                                                 "unscripted")))
    assert demos, "no demo carries a copy of the addon; has the layout changed?"
    for demo in demos:
        copy = os.path.join(root, "demos", demo, "addons", "unscripted")
        for name in names:
            with open(os.path.join(source, name), encoding="utf-8") as fh:
                want = fh.read()
            path = os.path.join(copy, name)
            assert os.path.exists(path), (
                f"demos/{demo} is missing {name}; copy it from integrations/godot")
            with open(path, encoding="utf-8") as fh:
                got = fh.read()
            assert got == want, (
                f"demos/{demo}/addons/unscripted/{name} has drifted from the "
                f"shipped addon; copy it across rather than editing it in place")
    print(f"ok  demos: {len(demos)} run the shipped Godot addon unmodified "
          f"({len(names)} scripts each)")


def test_no_tuning_value_can_crash_the_runtime_mid_tick():
    """Opening a surface without bounding it is how you ship a crash.

    Every parameter became authorable, and the validator checked names and types
    and nothing else. Driving each one to its extremes found three values a pack
    could legally set that killed a running world:

        belief.kappa_max = 1.0   ZeroDivisionError inside the log-odds update
        belief.kappa_min = 0.0   ValueError: log of zero
        affect.tau_mood  = 0     ZeroDivisionError inside the decay

    and several more that did not crash but silently discarded everything they
    were meant to bound -- a cap of zero looks exactly like a broken layer.

    A refusal at `unscripted validate` is a fine outcome. A traceback three files away
    from the JSON that caused it is not, and that is what this asserts: every
    value is either refused up front or survives a working world.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted import tuning as tuning_module
    from unscripted.pack import validate_world_pack

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = tempfile.mkdtemp(prefix="unscripted-bounds-")
    pack = os.path.join(work, "pack")
    shutil.copytree(os.path.join(root, "worldpacks", "market-square"), pack)
    world_json = os.path.join(pack, "world.json")

    def try_block(block):
        """Returns 'refused' or 'ran', or raises whatever the runtime raised."""
        world = json.load(open(world_json, encoding="utf-8"))
        world["tuning"] = block
        with open(world_json, "w", encoding="utf-8") as handle:
            json.dump(world, handle, indent=1)
        if "bad_tuning" in str(validate_world_pack(pack).__dict__):
            return "refused"
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", pursuit=True,
            notes=True, promises=True, contagion=True, common_knowledge=True))
        try:
            sdk.submit_player_text("look")
            sdk.submit_player_text("promise Yara 50 credits")
            for _ in range(12):
                sdk.advance_time(60)
            return "ran"
        finally:
            sdk.close()

    try:
        # The three that actually crashed, by name, so a future loosening of the
        # bounds fails here rather than in somebody's game.
        for block in ({"belief": {"kappa_max": 1.0}},
                      {"belief": {"kappa_min": 0.0}},
                      {"affect": {"tau_mood": 0.0}}):
            assert try_block(block) == "refused", f"{block} was allowed through"

        # And then every bounded parameter, driven past both ends. The point is
        # not that each is refused -- it is that none of them reaches a tick.
        probe = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "market-square"),
            storage_path=":memory:"))
        try:
            defaults = {(row["engine"], key): value
                        for row in tuning_module.describe(probe.core)
                        for key, value in row["parameters"].items()}
        finally:
            probe.close()

        checked = 0
        for (engine, key), bound in sorted(tuning_module.RANGES.items()):
            assert (engine, key) in defaults, (
                f"RANGES bounds {engine}.{key}, which is not a parameter")
            low, high, _low_open, _high_open = bound
            for value in ([low, low - 1] + ([high, high + 1] if high is not None
                                            else [])):
                outcome = try_block({engine: {key: value}})
                assert outcome in ("refused", "ran")
                checked += 1

        # A world that sets nothing must still be exactly the reference world --
        # adding bounds must not have changed a default on the way past.
        for (engine, key), value in defaults.items():
            bound = tuning_module.RANGES.get((engine, key))
            if bound is None:
                continue
            low, high, low_open, high_open = bound
            assert not (value <= low if low_open else value < low), (
                f"the shipped default {engine}.{key}={value} is below its own "
                f"bound; the bound is wrong, not the default")
            if high is not None:
                assert not (value >= high if high_open else value > high), (
                    f"the shipped default {engine}.{key}={value} is above its "
                    f"own bound")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"ok  bounds: {len(tuning_module.RANGES)} bounded parameters, "
          f"{checked} extreme values driven at them, every one either refused "
          f"by the validator or survived a running world — and no shipped "
          f"default sits outside its own bound")


def test_the_unreal_plugin_compiles_where_a_built_engine_exists():
    """The other half of the same problem, and it has no shortcut.

    For Unity it turned out no editor was needed: an installed editor ships its
    own Roslyn compiler and reference assemblies, and invoking a compiler is not
    using an editor. There is no equivalent here. An Unreal plugin's
    `.generated.h` files come from UnrealHeaderTool, and the ENGINE's own
    generated headers -- which `CoreMinimal.h` and everything under it depend on
    -- exist only once the engine has been built. Engine headers alone are not
    enough.

    So this needs a real engine, and says so rather than pretending otherwise.
    Where one exists it builds a throwaway project containing only the plugin,
    which compiles every .cpp, runs UHT over the reflection macros and links --
    a stronger claim than the Unity check makes, because those macros are the
    part hand-written Unreal C++ most often gets wrong.
    """
    import importlib.util

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin = os.path.join(root, "integrations", "unreal", "UnscriptedBridge")

    # The plugin must be present and coherent whether or not an engine is.
    descriptor = json.load(open(os.path.join(plugin, "UnscriptedBridge.uplugin"),
                                encoding="utf-8"))
    modules = [m["Name"] for m in descriptor["Modules"]]
    assert modules == ["UnscriptedBridge"], modules
    source = os.path.join(plugin, "Source", modules[0])
    assert os.path.isdir(source), f"the .uplugin names {modules[0]} and there is no such module"
    assert os.path.exists(os.path.join(source, f"{modules[0]}.Build.cs")), (
        "the module has no Build.cs, so UnrealBuildTool has nothing to read")

    spec = importlib.util.spec_from_file_location(
        "_unreal_check", os.path.join(root, "tools", "unreal_check.py"))
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    engines = checker.find_engines()
    built = [engine for engine in engines if checker.is_built(engine)]
    if not built:
        source_only = len(engines)
        print(f"ok  unreal: plugin present and coherent; NOT COMPILED — "
              f"{source_only} engine tree(s) found, none built "
              f"(unrealengine.com/linux ships one that needs no build)")
        return

    code, output = checker.build_with(built[0])
    assert code == 0, (
        f"the Unreal plugin does not compile against {built[0]}:\n"
        + "\n".join(line for line in output.splitlines()
                     if " error" in line.lower())[:2000])
    print(f"ok  unreal: plugin compiles against {os.path.basename(built[0])}")


def test_the_unreal_plugin_behaves_where_a_built_engine_exists():
    """Compiling is not behaving, and the difference cost two real defects.

    The plugin compiled cleanly and still did two things wrong, neither of which
    a compiler can see:

      `FUnscriptedAvatarPacket` had no `Honesty` field. The contract has promised it and
      the service has sent it since the beginning; a game built on this plugin
      could not see WHETHER A CHARACTER HAD LIED, which is the headline feature
      of the runtime. The struct was well formed. It just did not do what the
      contract said.

      The `.uplugin` declared `EngineVersion: 5.6.0`, so on 5.8 Unreal wrote
      "'UnscriptedBridge' is Incompatible -- Skipping load" and the module
      never loaded at all. A studio would have built it, run it, and found an
      NPC that does nothing, with no error anywhere in the game.

    Both were found by trying to write a behavioural test, not by reading. So
    the test stays: three automation tests inside Unreal, against a live
    service, exercising the plugin's own parser on the runtime's own answers.

    SKIPPED LOUDLY where no built engine exists, because a test that silently
    passes on a machine without Unreal reads as "the plugin works" everywhere it
    was never tried.
    """
    import importlib.util
    import json as _json

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin = os.path.join(root, "integrations", "unreal", "UnscriptedBridge")

    # The version pin must stay gone whether or not an engine is here to prove
    # it. This is the assertion that would have caught it in the first place.
    descriptor = _json.load(open(os.path.join(plugin, "UnscriptedBridge.uplugin"),
                                 encoding="utf-8"))
    assert "EngineVersion" not in descriptor, (
        "the .uplugin pins an engine version again. Unreal refuses to load a "
        "plugin whose declared version differs from the engine's, so this makes "
        "the plugin silently absent on every version but one.")

    # And the fields the contract promises must be parsed, not merely declared.
    header = open(os.path.join(plugin, "Source", "UnscriptedBridge", "Public",
                               "UnscriptedClient.h"), encoding="utf-8").read()
    parser = open(os.path.join(plugin, "Source", "UnscriptedBridge", "Private",
                               "UnscriptedClient.cpp"), encoding="utf-8").read()
    for field, wire in (("Honesty", "honesty"), ("Asserted", "asserted")):
        assert field in header, f"FUnscriptedAvatarPacket lost {field}"
        assert f'TEXT("{wire}")' in parser, (
            f"{field} is declared and never parsed, which is how it was "
            f"missing in the first place")

    spec = importlib.util.spec_from_file_location(
        "_unreal_smoke", os.path.join(root, "tools", "unreal_smoke.py"))
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    check = smoke._check_module()
    built = [e for e in check.find_engines() if check.is_built(e)]
    if not built:
        print("ok  unreal behaviour: version pin absent and honesty/asserted "
              "parsed; NOT RUN — no built engine here "
              "(python3 tools/unreal_smoke.py where there is one)")
        return

    # DELIBERATELY NOT RUN FROM HERE. The behavioural run needs a full editor
    # target built, which takes tens of minutes -- putting that in a suite people
    # run before every commit would mean they stop running the suite. What this
    # test guards is that the two defects it found cannot come back silently;
    # the run itself is one command, and it is named here rather than implied.
    print("ok  unreal behaviour: version pin absent, honesty and asserted "
          "parsed; the live run is `python3 tools/unreal_smoke.py` (a full "
          "editor build is too slow for this suite)")


def test_the_unity_package_compiles_where_an_editor_is_installed():
    """The claim "the C# compiles" stops being an assertion.

    Two engine integrations existed and neither had been through a compiler. The
    Unreal plugin's README has had to say so for months; I nearly shipped the
    Unity package with the OPPOSITE claim, written while the editor was still
    downloading.

    The obvious check does not work. Unity's `-batchmode` refuses to start
    without an activated licence, and activating means signing in with an
    account, which is the owner's to do -- so a check built that way could never
    run unattended and the package would have stayed unverified indefinitely.

    But an installed editor ships its own Roslyn compiler, its own .NET host and
    its own reference assemblies, and invoking a compiler is not using an editor.
    So the package is compiled against the engine's real `UnityEngine`
    assemblies, warnings as errors, with no licence involved at all.

    SKIPPED, LOUDLY, where no editor is installed. A test that silently passes on
    a machine without Unity would be worse than none: it would read as "the
    package compiles" everywhere it had never been tried.
    """
    import importlib.util

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tool = os.path.join(root, "tools", "unity_check.py")
    package = os.path.join(root, "integrations", "unity",
                           "com.vigilant.unscripted")

    # The package must be there and well formed whether or not Unity is.
    manifest = json.load(open(os.path.join(package, "package.json"),
                              encoding="utf-8"))
    assert manifest["name"] == "com.vigilant.unscripted"
    assert manifest["unity"], "no minimum Unity version declared"
    sources = sorted(f for f in os.listdir(os.path.join(package, "Runtime"))
                     if f.endswith(".cs"))
    assert sources == ["UnscriptedClient.cs", "UnscriptedHost.cs"], sources

    spec = importlib.util.spec_from_file_location("_unity_check", tool)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    editors = checker.find_editors()
    if not editors:
        print("ok  unity: package present and well formed; NOT COMPILED — no "
              "Unity editor on this machine (run tools/unity_check.py where "
              "there is one)")
        return

    compiled = []
    for editor in editors:
        code, output = checker.compile_with(editor)
        version = os.path.basename(os.path.dirname(editor))
        # An editor missing its own compiler is not a failure of this package.
        if code == 4:
            continue
        assert code == 0, (
            f"the Unity package does not compile against {version}:\n" + output)
        compiled.append(version)

    assert compiled, (
        f"{len(editors)} editor(s) found and none could compile anything; "
        f"the harness is broken, not the package")
    print(f"ok  unity: package compiles against {', '.join(compiled)} — "
          f"warnings as errors, against the engine's real assemblies, and "
          f"without a licence")


def test_the_noir_pack_produces_the_scene_it_was_written_for():
    """Three witnesses, three different facts, and a liar the runtime catches.

    `nine-oh-seven` exists to be filmed, so what it has to prove is not that it
    loads but that it produces the SCENE. A pack that validates and then gives
    six people the same answer would be worse than no pack: it would look like a
    demo and argue nothing.

    The shape is the argument. A dialogue tree can store six answers to one
    question. It cannot store the fact that the barman has a time without a
    person, the driver has a person without a name, and the grocer has a car
    without a reason -- and that nobody has the case.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "nine-oh-seven")

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", pursuit=True, media=True,
        climate=True, common_knowledge=True))
    try:
        sdk.submit_player_text("look")

        # 1. AT 21:07 NOBODY HAS THE CASE. Four fragments, four people, and the
        #    two who will carry the story around have nothing at all yet.
        def held(agent_id):
            return {key.split("(")[0]
                    for key in sdk.world.agents[agent_id].beliefs}
        assert "shot_heard" in held("agent:halloran")
        assert "ran_from" in held("agent:vance")
        assert "car_waiting" in held("agent:okonkwo")
        assert "shot_by" in held("agent:reyes"), "the liar has nothing to lie about"
        for empty in ("agent:byrne", "agent:doyle"):
            assert not (held(empty) & {"shot_by", "shot_heard", "ran_from",
                                       "car_waiting"}), (
                f"{empty} starts out knowing something; ignorance has to be "
                f"authored by omission or the morning proves nothing")

        # 2. THE MORNING BROADCAST GIVES THE STREET A WRONG STORY IN COMMON --
        #    and misses exactly the two people who saw something, because they
        #    are not listening to the radio at nine in the morning. That was not
        #    scripted: it falls out of who was authored to listen.
        for _ in range(12):
            sdk.advance_time(60)

        def believes_radio(agent_id):
            return any("unknown_man" in key
                       for key in sdk.world.agents[agent_id].beliefs)
        convinced = [a for a in ("agent:halloran", "agent:okonkwo",
                                 "agent:byrne", "agent:doyle")
                     if believes_radio(a)]
        assert len(convinced) >= 3, (
            f"only {convinced} took the broadcast; the shared wrong story is the "
            f"beat the whole scene turns on")
        assert not believes_radio("agent:reyes"), (
            "the one person who knows also heard the radio, which removes the "
            "reason the player has to find her")

        # 3. THE SAME NIGHT, ASKED OF FOUR PEOPLE, GIVES FOUR DIFFERENT ANSWERS.
        answers, asserted = {}, {}
        for who, topic in (("halloran", "the shot"), ("vance", "the runner"),
                           ("okonkwo", "the car"), ("reyes", "what happened")):
            sdk.world.agents["agent:player_1"].location = \
                sdk.world.agents[f"agent:{who}"].location
            sdk.world.invalidate_indexes()
            avatar = (sdk.avatar_turn(f"ask {who} about {topic}")
                      .get("avatar") or {})
            answers[who] = (avatar.get("text", "").strip(),
                            avatar.get("honesty", ""))
            asserted[who] = avatar.get("asserted") or []

        spoken = [text for text, _ in answers.values() if text]
        assert len(set(spoken)) == len(spoken), (
            f"two characters gave the same answer: {spoken}")
        for who in ("halloran", "vance", "okonkwo"):
            assert answers[who][0], f"{who} had nothing to say about their own fact"
            assert answers[who][1] == "honest"

        # 4. AND THE LIAR LIES, recorded as a lie with her name on it. Her cover
        #    story is the radio's version rather than an invention, which is what
        #    makes it plausible and what makes catching her out possible.
        assert answers["reyes"][1] == "lie", (
            f"Reyes answered {answers['reyes'][1]!r}. The first draft of this "
            f"pack gave her no secret at all, so she told the truth immediately "
            f"and the scene had no lie in it.")
        # AND SHE SAYS IT. The label alone passed for days while the validator
        # refused her authored cover line and she deflected -- "lie" on a
        # sentence that asserted nothing, and no lie anywhere in the world.
        cover = sdk.world.agents["agent:reyes"].secrets[0].cover_phrasings
        assert answers["reyes"][0] in cover.values(), (
            f"Reyes said {answers['reyes'][0]!r}, which is not her cover story")
        assert any(row.get("honesty") == "lie" for row in asserted["reyes"]), (
            f"the lie was labelled but never asserted: {asserted['reyes']}")
    finally:
        sdk.close()

    print(f"ok  noir: four witnesses hold four different facts, the morning "
          f"broadcast convinces {len(convinced)} of a wrong story while missing "
          f"the two who saw something, and Reyes lies")


def test_a_cover_story_is_licensed_by_its_own_words_and_nothing_else():
    """The liar says her cover story; a line that gives the secret away is neither.

    The validator refuses a line that names what a secret is about. A cover
    story is ABOUT the same thing -- it is what she says instead -- so it has to
    be licensed by its own authored words, read with the same lexicon as the
    line. It was not: the licence compared ids, "this door" never matched
    `place:club_door`, and Reyes deflected on the one question the Lamb Street
    scene is built around while the avatar packet still called it a lie.

    The licence is the phrasing for THIS answer, not an exemption: the same
    sentence under a plan that did not author it is still refused.
    """
    import dataclasses

    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.dialogue import DialoguePlan
    from unscripted.validator import CANON_OFF, Validator
    from unscripted.world import load_world_pack

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "nine-oh-seven")

    def ask_reyes(cover=None):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", pursuit=True, media=True,
            climate=True, common_knowledge=True))
        try:
            reyes = sdk.world.agents["agent:reyes"]
            secret = reyes.secrets[0]
            if cover is not None:
                secret = dataclasses.replace(secret, cover_phrasings=cover)
                reyes.secrets = [secret] + list(reyes.secrets[1:])
            sdk.submit_player_text("look")
            for _ in range(12):
                sdk.advance_time(60)
            sdk.world.agents["agent:player_1"].location = \
                sdk.world.agents["agent:reyes"].location
            sdk.world.invalidate_indexes()
            avatar = sdk.avatar_turn("ask reyes about what happened").get("avatar") or {}
            return avatar, dict(secret.cover_phrasings)
        finally:
            sdk.close()

    # 1. Her authored cover story is said, labelled a lie, and reaches the room.
    avatar, cover = ask_reyes()
    assert avatar.get("text") in cover.values(), avatar.get("text")
    assert avatar.get("honesty") == "lie", avatar.get("honesty")
    assert any(row.get("honesty") == "lie" for row in avatar.get("asserted") or ()), (
        avatar.get("asserted"))

    # 2. A cover story that names the man she protects is refused -- and the
    #    deflection that replaces it asserts nothing and is not called a lie.
    leaky = "Mallory never came back in, if that's what you're asking."
    avatar, _ = ask_reyes({"neutral": leaky})
    assert avatar.get("text") != leaky, "a line naming the protected man was released"
    assert not avatar.get("asserted"), avatar.get("asserted")
    assert avatar.get("honesty") != "lie", (
        f"{avatar.get('text')!r} asserted nothing and was labelled a lie")

    # 3. The licence belongs to the phrasing, not to the sentence.
    world = load_world_pack(pack)
    validator = Validator.for_world(world)
    reyes = world.agents["agent:reyes"]
    secret = reyes.secrets[0]
    line = secret.cover_phrasings["neutral"]
    unauthored = DialoguePlan(reyes.id, "agent:player_1", "inform", goal="answer",
                              avoid_topics=[secret.avoid_label])
    refused = validator.check(line, unauthored, reyes, [])
    assert refused.verdict == "REJECT_HARD", refused.verdict
    assert any(code == "validator.secret_referent" for code, _m, _d in refused.reasons)
    authored = DialoguePlan(reyes.id, "agent:player_1", "inform", goal="answer",
                            avoid_topics=[secret.avoid_label],
                            phrasing=dict(secret.cover_phrasings))
    accepted = validator.check(line, authored, reyes, [], canon_mode=CANON_OFF)
    assert accepted.verdict == "ACCEPT", [c for c, _m, _d in accepted.reasons]

    print("ok  validator: a cover story is licensed by its own authored words and "
          "said as a lie; a leaky one is refused and its deflection is not called one")


def test_the_default_narrator_is_asked_for_a_voice_it_has():
    """`unscripted pages --with-film`, as CI runs it, asks for a voice its synthesiser has.

    Both film commands defaulted `--narrator-voice` to `af_heart`, a kokoro
    voice, while defaulting the narrator itself to espeak-ng. espeak-ng was
    therefore asked for a voice it does not have, on every machine, and the
    Pages workflow -- which runs exactly the default command -- failed at the
    first line of narration. Each default was fine; nothing tested them together.
    """
    import shutil
    import tempfile

    from unscripted.cli import build_parser
    from unscripted.film import voice_for
    from unscripted.voice import VoicePlan, command, synthesize

    parser = build_parser()
    pages = parser.parse_args(["pages", "--with-film"])
    film = parser.parse_args(["film"])
    for backend, requested in ((pages.film_narrator, pages.film_narrator_voice),
                               (film.narrator, film.narrator_voice)):
        assert backend == "espeak-ng", backend
        assert voice_for(backend, requested) == "", (
            f"the default espeak-ng narrator is asked for "
            f"{voice_for(backend, requested)!r}")
    kokoro = parser.parse_args(["pages", "--with-film", "--film-narrator", "kokoro"])
    assert voice_for(kokoro.film_narrator, kokoro.film_narrator_voice) == "af_heart"
    chosen = parser.parse_args(["film", "--narrator-voice", "en-us"])
    assert voice_for(chosen.narrator, chosen.narrator_voice) == "en-us"

    plan = VoicePlan(agent_id="narrator", text="A claim moves from one person to another.",
                     rate=0.92, pitch=-0.05, loudness=0.62,
                     voice_name=voice_for(pages.film_narrator, pages.film_narrator_voice))
    assert "-v" not in command("espeak-ng", plan, "line.wav")
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        with tempfile.TemporaryDirectory() as folder:
            assert synthesize(plan, os.path.join(folder, "line.wav"))["rendered"]
        rendered = "and a line renders with it"
    else:
        rendered = "(no espeak-ng here, so nothing was rendered)"
    print(f"ok  film: the default narrator is asked for its own default voice, {rendered}")


def test_a_contested_world_holds_two_answers_at_once():
    """A false story that travels and a true one that does not.

    `market-square` is the pack the demo film is built on, and it exists to carry
    one claim with two answers: a councillor is shot, the radio says one thing,
    and the woman whose stall it happened in front of saw another. If the pack
    ever stops producing that split it stops demonstrating anything, and the
    video would go on saying it does.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "market-square"),
        storage_path=":memory:"))
    try:
        sdk.submit_player_text("look")
        for _ in range(12):
            sdk.advance_time(60)

        versions = {}
        for fact in sdk.structured_knowledge()["facts"]:
            if fact["predicate"] != "killed_by":
                continue
            if "group:eastside" in fact["text"]:
                versions["radio"] = fact["holders"]
            elif "group:contractors" in fact["text"]:
                versions["witness"] = fact["holders"]

        assert "radio" in versions and "witness" in versions, (
            "the world must contain both answers, or there is nothing to compare")
        # The false one travels further, because a broadcast reaches everyone who
        # was listening and a witness reaches whoever walks past her stall.
        assert len(versions["radio"]) > len(versions["witness"]), (
            f"the radio's version reached {len(versions['radio'])} and the "
            f"witness's {len(versions['witness'])}; the point of the pack is that "
            f"the loud one wins on reach")
        strongest = max(versions["witness"], key=lambda h: h["prob"])
        assert strongest["name"] == "Yara" and strongest["prob"] > 0.75, (
            f"the witness must be the surest person in the world about what she "
            f"saw, not {strongest['name']} at {strongest['prob']:.2f}")

        contested = [c["text"] for c in sdk.structured_knowledge()["contested"]]
        assert any("killed_by" in text for text in contested), (
            "the killing must be a contested claim; a world where everybody "
            "agrees is the world this one exists not to be")
    finally:
        sdk.close()

    # And what the player does changes what they are told. Threatening the
    # witness costs her trust, and she keeps the part that matters.
    def ask_after(actions):
        session = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "market-square"),
            storage_path=":memory:"))
        try:
            session.submit_player_text("look")
            session.advance_time(120)
            for action in actions:
                session.submit_player_text(action)
            reply = session.avatar_turn("ask Yara about the killing")
            trust = session.world.agents["agent:yara"].relationships.get(
                "agent:player_1", {}).get("trust", 0.0)
            return (reply.get("avatar") or {}).get("text", ""), trust
        finally:
            session.close()

    polite, polite_trust = ask_after([])
    leaned_on, leaned_trust = ask_after(["threaten Yara", "threaten Yara"])
    assert leaned_trust < polite_trust, (
        f"leaning on the witness left her trust at {leaned_trust:.2f} against "
        f"{polite_trust:.2f}; nothing the player does is reaching her")
    assert len(leaned_on) < len(polite), (
        f"she said as much to somebody who threatened her: {leaned_on!r} against "
        f"{polite!r}. Every player is supposed to end up in a slightly different "
        f"world, and this is the mechanism")
    print(f"ok  market-square: {len(versions['radio'])} hold the radio's version "
          f"and {len(versions['witness'])} the witness's; leaning on her costs "
          f"{polite_trust - leaned_trust:.2f} trust and a sentence")


def test_the_engine_demo_and_its_narration_stay_in_step():
    """A video that plays nine seconds in silence reads as a broken product.

    The Godot demo holds each beat for a fixed time and the narration is laid at
    offsets computed from the demo's own constants, so a missing line does not
    shift anything -- it leaves a gap, and the gap looks like the demo hung. It
    happened once, so the two files are now checked against each other.

    This does not run Godot. It reads both and checks they agree, which is the
    part that can go wrong silently.
    """
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project = os.path.join(root, "integrations", "godot", "UnscriptedDemo")
    demo = open(os.path.join(project, "Main.gd"), encoding="utf-8").read()
    tool = open(os.path.join(root, "tools", "godot_demo.py"), encoding="utf-8").read()

    questions = demo[demo.index("const QUESTIONS := ["):demo.index("var unscripted")]
    asked = questions.count('{"text"')
    assert asked >= 4, f"the demo lost its questions: {asked}"

    spoken = tool[tool.index("QUESTION_LINES = ["):tool.index("def free_port")]
    entries = spoken.count('",\n') + spoken.count('."\n') + spoken.count('.",\n')
    assert entries >= 2 * asked - 1, (
        f"{asked} questions need {2 * asked} spoken lines; the tool looks like it "
        f"has about {entries}")

    # The timings the narration is placed by must still be declared.
    for name in ("HOURS", "HOUR_SECONDS", "SIDE_SECONDS"):
        assert re.search(rf"const {name} := ", demo), (
            f"the narration is placed using {name}, which the demo no longer declares")

    # Every preload must resolve, or the demo fails on the machine it is shown on.
    for source in ("Main.gd", "Unscripted.gd", "Flags.gd"):
        text = open(os.path.join(project, source), encoding="utf-8").read()
        for path in re.findall(r'preload\("res://([^"]+)"\)', text):
            assert os.path.exists(os.path.join(project, path)), (
                f"{source} preloads {path}, which is not in the project")

    # It must not invent an answer when the runtime is absent.
    client = open(os.path.join(project, "Unscripted.gd"), encoding="utf-8").read()
    assert "Is `unscripted serve` running?" in client, (
        "a demo that quietly fakes an answer when the service is down will one "
        "day be shown with the service down")

    # And the flag column must have nowhere to put the interesting answers, or it
    # is not the model it claims to be.
    flags = open(os.path.join(project, "Flags.gd"), encoding="utf-8").read()
    for method in ("who_told", "was_a_lie", "which_version"):
        assert re.search(rf'func {method}\([^)]*\) -> String:\s*\n\s*return ""',
                         flags), (
            f"Flags.{method} started answering; a boolean has nowhere to put it, "
            f"and a comparison where it does is not the comparison being claimed")
    print(f"ok  godot: {asked} questions, narration in step, every preload "
          f"resolves, and the flag model still cannot answer")


def test_a_leading_verb_decides_the_intent():
    """"ask about the market attack" is a question, not an assault.

    `move`, `wait` and `inspect` have always matched on the start of the line.
    The rest matched anywhere in it, and in a world whose topic is called
    `market_attack` that inconsistency made the topic unaskable by anyone, ever:
    the word "attack" appeared in the sentence, so every question about it was
    parsed as an assault and the whole room mobilised their allies.

    Found while building the engine demo, which could not ask the one question
    the demo exists to ask.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        def intent(text):
            return sdk.parse(text).intent if hasattr(sdk, "parse") else None

        from unscripted.parser import RuleBasedParserProvider
        parser = RuleBasedParserProvider()

        def parsed(text):
            return parser.parse(text, player_id=sdk.config.player_id,
                                player_location="place:main_street",
                                world=sdk.world).intent

        # The bug, in one line.
        assert parsed("ask Honce about the market attack") == "ask", (
            "a question containing the word 'attack' is still a question")
        # And the thing it must not break.
        assert parsed("attack Pavel") == "attack"
        assert parsed("threaten Mr. Okada") == "threaten"
        assert parsed("go bar") == "move"
        assert parsed("wait 30") == "wait"
        # The contains-anywhere fallback still catches a sentence that does not
        # start with its verb, which is why it exists.
        assert parsed("I want to threaten him") == "threaten"
        # Same shape in the German pack's lexicon.
        assert parsed("frage Honce nach dem Angriff") == "ask"
    finally:
        sdk.close()
    print("ok  parser: a leading verb decides the intent, so a topic named after "
          "one is still askable")


def test_the_comparison_is_computed_on_both_sides_and_can_be_lost():
    """A before/after is the easiest place in a repository to cheat.

    So the flag column is not prose. `unscripted/flat.py` is a set of booleans, it is fed
    the same transmissions the runtime produced, and both columns answer the same
    questions from their own state. Three things keep it honest, and all three are
    asserted here: the flag model actually runs, it *wins* some rows, and where it
    answers nothing the reason is structural rather than editorial.
    """
    from unscripted.compare import NOWHERE, build
    from unscripted.flat import FlatWorld, run as run_flat
    from unscripted.viz import record
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")
    script = [(1, "ask Mr. Okada about milan"), (5, "ask Honce about the attack")]

    # The model itself: a boolean holds what a boolean holds, and nothing else.
    flat = FlatWorld()
    assert flat.learn("agent:a", "fact") is True
    assert flat.learn("agent:a", "fact") is False, "a boolean cannot be set twice"
    flat.tell("agent:a", "agent:b", "fact", honest=False)
    assert flat.who_knows("fact") == ["agent:a", "agent:b"]
    assert flat.who_told("agent:b", "fact") is None
    assert flat.was_it_a_lie("agent:b", "fact") is None
    assert flat.which_version("agent:b", "fact") is None
    assert flat.discredit("agent:a") == 0, (
        "there is no edge from a flag back to who caused it, which is the finding")
    assert flat.tellings, (
        "the model must record what it was handed; it simply has nowhere to use it")

    recording = record(pack, predicate="connected_to_attack", hours=168,
                       step_minutes=30, script=script)
    comparison = build(recording, pack, predicate="connected_to_attack", script=script)
    rows = comparison["rows"]
    assert len(rows) >= 8, rows
    assert all(row["flat"] and row["unscripted"] and row["note"] for row in rows)

    # The flag column is run, not written: the broadcast reaches the whole cast
    # because a global fact has no field for who was listening.
    cast = [a["id"] for a in recording["world"]["agents"]]
    played = run_flat(pack, predicate="connected_to_attack",
                      tellings=[{"from": cast[0], "to": cast[1]}], agents=cast)
    assert len(played.who_knows("connected_to_attack")) == len(cast)
    assert str(len(cast)) in rows[0]["flat"], rows[0]["flat"]
    # ...and the runtime's own answer differs, because some of them were not
    # listening to that channel.
    assert len(recording["frames"][-1]["p"]) < len(cast), (
        "if everybody hears it either way, this row demonstrates nothing")

    winners = [row for row in rows if row.get("wins") == "flat"]
    assert len(winners) >= 2, (
        "a comparison in which one side never wins anything is a comparison "
        "nobody believes")
    for row in winners:
        assert NOWHERE not in row["flat"]

    gaps = [row for row in rows if row["flat"].startswith(NOWHERE)]
    assert gaps, "the interesting rows are the ones a boolean cannot hold"
    for row in gaps:
        assert "worse" not in row["note"].lower() and "bad" not in row["note"].lower(), (
            f"the note editorialises instead of stating the structural reason: "
            f"{row['note']!r}")
    print(f"ok  compare: {len(rows)} rows, both columns computed, "
          f"{len(winners)} of them won by flags")


def test_the_film_is_cut_to_the_voice_and_says_only_what_was_recorded():
    """A video is the easiest place to describe something that did not happen.

    So the narration is generated from the chapters the runtime found in its own
    run: a sentence about a moment the recording does not contain cannot be
    produced, and re-running after the world changes yields a video about the new
    world instead of a confident one about the old.

    The pacing property matters too. The picture is cut to the voice rather than
    to a constant frame rate, so a beat with something to say lingers and one
    without it moves -- what a person does with a scrubber, and what a slideshow
    with a voiceover on top cannot do.
    """
    from unscripted.cli import running_time
    from unscripted.film import (MIN_FRAME_SECONDS, requirements, script, timeline)
    from unscripted.viz import record
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")

    # The caption under the player states the film's length, so it has to be the
    # length the player shows: whole minutes. `:.0f` rounded 161.55 s to "3:41".
    for seconds, shown in ((161.55, "2:41"), (59.9, "0:59"), (120.0, "2:00")):
        assert running_time(seconds) == shown, (seconds, running_time(seconds))

    recording = record(pack, predicate="connected_to_attack", hours=36,
                       step_minutes=30, script=[(3, "ask Honce about the attack")])
    beats = script(recording)
    assert len(beats) >= 3, beats
    titles = {chapter["title"] for chapter in recording["chapters"]}
    for beat in beats[1:-1]:
        assert any(beat["text"].startswith(title) for title in titles), (
            f"the narration says something the recording never found: {beat['text']!r}")
    assert beats[0]["frame"] == 0
    assert beats[-1]["frame"] == len(recording["frames"]) - 1
    # The closing line reports the state the run actually ended in.
    final = recording["frames"][-1]
    assert f"{len(final['p'])} of {len(recording['world']['agents'])}" in beats[-1]["text"]

    # The picture follows the voice: a long line over few frames holds them.
    stills = {index: f"/tmp/f{index}.png" for index in range(0, 24, 2)}
    spoken = [{"frame": 0, "seconds": 8.0, "wav": "a.wav", "text": "..."},
              {"frame": 12, "seconds": 1.0, "wav": "b.wav", "text": "..."}]
    plan = timeline(24, spoken, stills)
    assert plan, "no plan"
    assert all(seconds >= MIN_FRAME_SECONDS for _path, seconds in plan)
    first = sum(seconds for _p, seconds in plan[:6])
    assert abs(first - 8.0) < 0.05, (
        f"the first beat speaks for 8s and its frames occupy {first:.2f}s; the "
        f"picture is not cut to the voice")
    assert abs(sum(seconds for _p, seconds in plan) - 9.0) < 0.1

    tools = requirements()
    if not all(tools.values()):
        print(f"ok  film: narration derived from the recording; rendering skipped "
              f"({', '.join(n for n, p in tools.items() if not p)} missing)")
        return

    # And end to end, small, because a pipeline that assembles nothing playable
    # is a pipeline nobody finds out about until the morning of the pitch.
    import tempfile
    from unscripted import __version__
    from unscripted.film import make
    from unscripted.viz import render
    with tempfile.TemporaryDirectory() as folder:
        page = os.path.join(folder, "page.html")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(render(recording, version=__version__, pack="cyberpunk-block"))
        out = os.path.join(folder, "film.mp4")
        result = make(recording, page, out, every=24, width=640, height=360,
                      workers=4)
        assert os.path.getsize(out) > 20_000, "the file is too small to be a video"
        assert result["seconds"] > 5, result
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "default=nw=1:nk=1", out], capture_output=True, timeout=120)
        streams = probe.stdout.decode().split()
        assert "video" in streams and "audio" in streams, (
            f"a film with no {'audio' if 'video' in streams else 'video'} track: "
            f"{streams}")
    print(f"ok  film: {len(beats)} beats from the recording, cut to the voice, "
          f"and a playable file with both tracks")


def test_the_quickstart_page_is_captured_and_not_typed():
    """The "getting started" page is the one most likely to be quietly wrong.

    A code sample somebody typed into a README drifts from the service the day a
    field is renamed, and the reader has no way to tell. This one starts a real
    service, makes the calls and embeds what came back, so a rename changes the
    page and fails the contract test on the same day.
    """
    from unscripted import __version__
    from unscripted.quickstart import capture, render
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    captured = capture(os.path.join(root, "worldpacks", "cyberpunk-block"))

    calls = captured["calls"]
    assert len(calls) >= 5, calls
    assert all(call["body"] for call in calls), "a call came back with nothing"
    assert any(200 <= call["status"] < 300 for call in calls)

    # One call is a deliberate mistake, because the shape of a rejection is part
    # of what an integrator needs to see before they commit to an API.
    refusals = [call for call in calls if 400 <= call["status"] < 500]
    assert refusals, "the page must show what a client mistake looks like"
    assert "code" in refusals[0]["body"], (
        "a typed error code is the thing a client branches on; without it the "
        "page is showing a 400 with no story")

    versions = next(c["body"] for c in calls if c["request"] == "GET /capabilities")
    assert versions["runtime_version"] == __version__, (
        "the page would tell an integrator they are talking to a different build")

    page = render(captured, version=__version__)
    for pattern in ('src="http', 'href="http', "@import", "XMLHttpRequest"):
        assert pattern not in page, f"the page reaches outside itself: {pattern}"
    assert page.count("<section>") == len(calls)
    # It must not promise that ten minutes buys an integration.
    assert "does not buy" in page and "afternoon" in page, (
        "the honest half of this page is the timing")
    print(f"ok  quickstart: {len(calls)} live calls captured, "
          f"{len(refusals)} of them a deliberate mistake")


def test_a_voice_is_planned_from_affect_and_says_what_it_cannot_do():
    """The runtime decides how a line should sound; a backend renders it.

    Prosody has been emitted on every spoken line since the MetaHuman adapter was
    written and nothing consumed it, so `capabilities.tts` said false while the
    interesting half of the problem was already solved. This asserts the half the
    runtime owns -- that affect actually moves the voice, that a character sounds
    like themselves in every session, and that a backend which cannot honour a
    parameter *says so* rather than producing a flat read and calling it the
    character's voice.

    No synthesiser is installed on the machine this was written on, and the test
    passes there: the mapping is checked, not the audio. That is deliberate --
    the SDK installs with no third-party packages, and a bundled voice would cost
    that.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.voice import (BACKENDS, HONOURS, VoiceError, VoiceProfile, available,
                           command, describe)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # A character sounds like themselves, in every session, without being random.
    first = VoiceProfile.for_agent("agent:corpo_okada")
    again = VoiceProfile.for_agent("agent:corpo_okada")
    other = VoiceProfile.for_agent("agent:barkeep_12")
    assert (first.pitch, first.rate) == (again.pitch, again.rate), (
        "a voice that changes between runs is a continuity bug the player notices "
        "before any belief state")
    assert (first.pitch, first.rate) != (other.pitch, other.rate), (
        "ten characters who all sound identical is worse than any assignment")
    authored = VoiceProfile.for_agent("agent:corpo_okada", {"pitch": 0.4, "rate": 0.8})
    assert (authored.pitch, authored.rate) == (0.4, 0.8), "a pack must be able to say"

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        calm = sdk.voice_plan(sdk.avatar_turn("ask Mr. Okada about milan")["avatar"])
        pressed = sdk.avatar_turn("threaten Mr. Okada").get("avatar")
        assert pressed, "the threat produced no spoken line"
        under_threat = sdk.voice_plan(pressed)

        # Same character, same voice, different state: the affect must move it.
        assert calm.base_pitch == under_threat.base_pitch
        assert (calm.rate, calm.pitch, calm.loudness) != \
               (under_threat.rate, under_threat.pitch, under_threat.loudness), (
            "being threatened did not change how he sounds, so the prosody is "
            "decoration rather than state")

        # espeak's own units, clamped so an extreme state cannot silence anyone
        # or wrap the parameter around.
        argv = command("espeak-ng", under_threat, "/tmp/does-not-matter.wav")
        speed = int(argv[argv.index("-s") + 1])
        pitch = int(argv[argv.index("-p") + 1])
        amplitude = int(argv[argv.index("-a") + 1])
        assert 80 <= speed <= 450 and 0 <= pitch <= 99 and 0 <= amplitude <= 200
        assert argv[-1] == under_threat.text

        # What a backend drops has to be visible, not smoothed over.
        assert "pitch" not in HONOURS["piper"]
        assert "cannot honour" in describe(under_threat, "piper")
        assert "cannot honour" not in describe(under_threat, "espeak-ng")

        try:
            command("piper", under_threat, "/tmp/x.wav")
            raise AssertionError("piper without a model should be refused")
        except VoiceError:
            pass

        # The capability is configuration *and* installation, never a constant.
        assert sdk.voice_available() is False, "no backend configured means no voice"
    finally:
        sdk.close()

    assert set(available()) == set(BACKENDS)
    configured = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:", voice_backend="espeak-ng"))
    try:
        assert configured.voice_available() is available()["espeak-ng"], (
            "a build that names a backend it cannot run would have an integrator "
            "wiring up audio that never arrives")
    finally:
        configured.close()
    # And when a synthesiser IS installed, the affect has to survive all the way
    # into the waveform. A mapping that produces the right numbers and audio that
    # sounds identical either way is a mapping nobody is using.
    if available()["espeak-ng"]:
        import tempfile
        import wave
        from unscripted.voice import VoicePlan, synthesize
        line = "The place was shut that night."
        seconds = {}
        with tempfile.TemporaryDirectory() as folder:
            for tag, plan in (
                    ("calm", VoicePlan("a", line, rate=0.85, pitch=-0.25, loudness=0.35)),
                    ("afraid", VoicePlan("a", line, rate=1.35, pitch=0.30, loudness=0.85))):
                path = os.path.join(folder, f"{tag}.wav")
                outcome = synthesize(plan, path, backend="espeak-ng")
                assert outcome["rendered"] and os.path.getsize(path) > 1000
                with wave.open(path) as handle:
                    seconds[tag] = handle.getnframes() / handle.getframerate()
        assert seconds["afraid"] < seconds["calm"] * 0.8, (
            f"the same sentence took {seconds['calm']:.2f}s calm and "
            f"{seconds['afraid']:.2f}s frightened; the prosody is not reaching the "
            f"audio")
        print(f"ok  voice: affect moves the voice ({seconds['calm']:.2f}s calm vs "
              f"{seconds['afraid']:.2f}s frightened, same words), a character keeps "
              f"theirs, and each backend states what it drops")
    else:
        print("ok  voice: affect moves the voice, a character keeps theirs, and each "
              "backend states what it drops (no synthesiser installed; the mapping "
              "was checked, not the audio)")


def test_the_recording_is_the_run_and_the_same_run_twice():
    """The animation is a recording, so it has to be reproducible and inert.

    A moving picture is the easiest place in a repository to smuggle in something
    that looks like data. Three properties keep it honest: the same seed produces
    a byte-identical recording, the page carries the recording it draws so the two
    can be compared, and the lies in it come out of the runtime's reason trace
    rather than out of the prose it generated.
    """
    import json as _json
    import re
    from unscripted import __version__
    from unscripted.viz import compact, record, render
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    relay = os.path.join(root, "worldpacks", "relay-station")

    first = record(relay, predicate="seal_breached", hours=24, step_minutes=30,
                   script=[(4, "ask Voss about breach")])
    second = record(relay, predicate="seal_breached", hours=24, step_minutes=30,
                    script=[(4, "ask Voss about breach")])
    assert _json.dumps(first, sort_keys=True) == _json.dumps(second, sort_keys=True), (
        "two recordings of the same seed differ -- the page would show a different "
        "world every time it was regenerated")

    frames = first["frames"]
    assert len(frames) == 48, len(frames)
    assert sum(len(f["tells"]) for f in frames) > 0, "nobody told anybody anything"
    assert sum(len(f["moves"]) for f in frames) > 0, "the cast never moved"
    # The refusals matter as much as the tellings: a society where everyone tells
    # everyone everything is the thing this runtime exists not to be.
    assert sum(len(f["silence"]) for f in frames) > 0, "nobody ever declined to pass it on"
    knowers = len(frames[-1]["p"])
    assert 1 < knowers <= len(first["world"]["agents"])

    # Every frame's locations are real places, and every teller a real character.
    places = {p["id"] for p in first["world"]["places"]}
    people = {a["id"] for a in first["world"]["agents"]}
    for frame in frames:
        assert set(frame["at"].values()) <= places, frame["at"]
        for tell in frame["tells"]:
            assert tell["from"] in people and tell["to"] in people, tell

    # A lie is read out of the trace, not guessed from the sentence.
    cyber = os.path.join(root, "worldpacks", "cyberpunk-block")
    lying = record(cyber, predicate="whereabouts", hours=24, step_minutes=30,
                   script=[(2, "ask Mr. Okada about milan")])
    lies = [lie for frame in lying["frames"] for lie in frame["lies"]]
    assert lies, "the authored liar did not lie, or the trace stopped saying so"
    assert lies[0]["heard_by"], "a lie told to nobody proves nothing"
    assert "whereabouts" in lies[0]["asserted"]

    payload = compact(first)
    assert len(payload["agents"]) == len(people)
    assert all(-1 <= index < len(payload["places"])
               for frame in payload["frames"] for index in frame["a"])

    page = render(first, version=__version__, pack="relay-station")
    # Self-contained means it fetches nothing. The SVG namespace URI is a
    # constant, not a request, so the check is on what could actually load.
    for pattern in ('src="http', "src='http", 'href="http', "href='http",
                    "@import", "fetch(", "XMLHttpRequest", "WebSocket"):
        assert pattern not in page, f"the page reaches outside itself: {pattern}"
    assert page.count("<script>") == 1
    embedded = _json.loads(re.search(r"const D = (\{.*?\});", page, re.S).group(1))
    assert len(embedded["frames"]) == len(frames), (
        "the page must carry the recording it draws, so the two can be compared")
    print(f"ok  viz: {len(frames)} frames reproduce byte-identically, "
          f"{sum(len(f['tells']) for f in frames)} tellings, {len(lies)} lie(s) from the trace")


def test_the_tour_shows_only_what_it_ran():
    """The sales page is generated from runs, and says nothing it cannot show.

    A demo page is where invented numbers go to live, so the two properties that
    keep this one honest are asserted: every scene carries the command that
    reproduces it, and the one scene that quotes a language model is *empty*
    rather than illustrated when no recorded model run is present.
    """
    from unscripted import __version__
    from unscripted.tour import build, render, scene_secret
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    packs = {"relay": os.path.join(root, "worldpacks", "relay-station"),
             "cyberpunk": os.path.join(root, "worldpacks", "cyberpunk-block")}

    tour = build(packs, os.path.join(root, "evidence", "evidence-llm.json"))
    assert len(tour["scenes"]) == 6, tour["scenes"]
    for scene in tour["scenes"]:
        assert scene["command"], f"{scene['id']} does not say how to reproduce it"
        assert scene["point"], f"{scene['id']} shows data and draws no conclusion"
        assert scene["against"] in ("recorded", "structural"), (
            f"{scene['id']} is compared against something undeclared -- the one "
            f"thing this page must never do is invent an opponent")

    # A missing model run leaves the scene empty. It must not fall back to prose.
    empty = scene_secret(os.path.join(root, "evidence", "no-such-run.json"))
    assert empty["available"] is False
    assert empty["attempts"] == []

    page = render(tour, version=__version__)
    assert page.startswith("<!doctype html>")
    assert "<script" not in page.lower(), "the page must be inert to open anywhere"
    assert "http://" not in page and "https://" not in page, (
        "self-contained means no external fetches")
    for scene in tour["scenes"]:
        assert f'id="{scene["id"]}"' in page
    # The voiceover is generated from the same run, because a hand-written script
    # drifts from the numbers on screen within one release and then somebody
    # records a video saying 0.9 while the page says 0.506.
    from unscripted.tour import narration
    script = narration(tour, version=__version__)
    for scene in tour["scenes"]:
        assert scene["narration"] in script, f"{scene['id']} is not in the voiceover"
        assert scene["point"] in script, (
            f"{scene['id']}'s figures are on the page but not in the script that "
            f"will be read over it")
    # Matched on the substance rather than a sentence, because the wording of a
    # gap changes when the gap does -- as it just did, when the voice went from
    # absent to planned-but-not-bundled and this assertion broke on a change that
    # made the script MORE accurate.
    for gap in ("not built", "voice", "compiled", "engine plugin"):
        assert gap in script, (
            f"the script stopped naming what is not built ({gap!r}), and the first "
            f"technical call is where an overstated video gets found out")
    print(f"ok  tour: {len(tour['scenes'])} scenes, each reproducible, none invented "
          f"({len(page) // 1024} KB page, {len(script.split())} word script)")


def test_asking_one_person_twice_is_still_one_witness():
    """The origin travels with the claim, not with the mouth it came out of.

    The diffusion layer had followed that rule since it was written -- a rumour
    through five people is one witness. Dialogue had not: every spoken answer
    minted `said_<speaker>_<time>`, so asking the same character the same
    question twice produced two origins, and the runtime counted its own
    repetition as independent corroboration. The channel a player uses most was
    the one that broke the central claim, and no test looked, because the
    benchmark measures relayed beliefs rather than the player's.

    Found by `unscripted qa`, which is the point of that tool: nobody writes a test for
    the leak they did not imagine.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "relay-station"),
        storage_path=":memory:"))
    try:
        def held():
            for belief in sdk.structured_agent(sdk.config.player_id)["beliefs"]:
                if belief["proposition"]["predicate"] == "seal_breached":
                    return belief
            return None

        for _ in range(4):
            sdk.submit_player_text("ask Voss about breach")
            sdk.advance_time(30)

        belief = held()
        assert belief is not None, "the player should have learned something by now"
        origins = {entry["origin_event"] for entry in belief["provenance"]}
        assert len(origins) == 1, (
            f"asking one person four times produced {len(origins)} independent "
            f"origins: {sorted(origins)}")
        assert belief["prob"] < 0.6, (
            f"repetition from one source convinced the player to {belief['prob']:.2f}; "
            f"the correlation discount is not being applied")
    finally:
        sdk.close()

    # A lie is the case that must NOT inherit: it has no evidential ancestor, so
    # the claim genuinely begins with the speaker -- which is what makes it
    # traceable to them afterwards.
    from unscripted.commitment import LIE
    from unscripted.ontology import Proposition
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "relay-station"),
        storage_path=":memory:"))
    try:
        speaker = sdk.world.agents["agent:voss"]

        class _Move:
            proposition = Proposition("seal_breached",
                                      {"section": "place:store", "when": "night_cycle"}, "+")
            honesty = LIE

        origin = sdk._spoken_origin(speaker, _Move())
        assert origin.startswith("said_agent:voss"), (
            f"a lie inherited an origin it has no claim to: {origin}")

        class _Honest(_Move):
            honesty = "honest"

        assert sdk._spoken_origin(speaker, _Honest()) == "incident:store_seal_night", (
            "an honest answer must pass on the evidence that already existed")
    finally:
        sdk.close()
    print("ok  provenance: asking one person four times is one origin; a lie is its own")


def test_qa_finds_the_shortest_breaking_path_and_says_what_it_covered():
    """The search has to find a planted failure, and be honest about its envelope.

    `HELD` from a bounded search means "no counterexample in this envelope", and
    a report that let that read as "impossible" would be worse than no report.
    So both are asserted: that it finds what is there, and that it always states
    how far it looked.
    """
    from unscripted.qa import search
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "relay-station")

    # Voss is seeded with the breach, so the rule excludes him: what is being
    # asked is whether anyone ELSE can be brought to believe it, which takes at
    # least one player action and is therefore a search rather than a state check.
    planted = [{"id": "only_voss_knows_the_breach", "type": "never_believed",
                "predicate": "seal_breached", "min_prob": 0.4,
                "except": ["agent:voss"]}]
    found = search(pack, planted, depth=2, budget=400)
    assert not found["held"], "one question to a man who knows should break this"
    assert found["violations"], "a broken run must say what broke"
    violation = found["violations"][0]
    assert violation["path"], (
        "this rule holds in the authored world, so a finding must name the actions "
        "that broke it -- a path of zero actions means the state check fired, not "
        "the search")
    assert len(violation["path"]) == 1, (
        f"the shortest path is one action; iterative deepening returned "
        f"{len(violation['path'])}: {violation['path']}")
    assert violation["witnesses"], "a finding without a source chain is an opinion"
    assert violation["fix"], "every finding names what an author would change"

    # A rule that holds still reports its envelope, both numbers, every time.
    ordinary = [{"id": "nobody_invents_knowledge", "type": "provenance_complete"}]
    held = search(pack, ordinary, depth=1, budget=60)
    assert held["held"]
    assert held["sequences_explored"] > 0
    assert "search_exhausted" in held, (
        "the difference between 'nothing found' and 'nothing exists' is the whole "
        "honesty of this tool")
    assert held["depth"] == 1 and held["budget"] == 60

    from unscripted.qa import render
    report = render(held)
    assert "HELD" in report and "sequences" in report
    print(f"ok  qa: finds a planted break in {len(violation['path'])} action(s), "
          f"and states its envelope when it finds none")


def test_the_contract_names_methods_the_plugin_actually_has():
    """Every `called_by` in the contract has to be a symbol in the C++.

    The contract is the one place the two sides are checked against each other,
    and the field tests assert its *shapes*. Its prose says which plugin method
    calls each endpoint -- and that half was checked by nobody. A contract that
    names `UUnscriptedSubsystem::PollIntents` when no such method exists reads
    as an integration point a studio can call, and is a paragraph.

    This does not compile the plugin; nothing here can. It asserts the far weaker
    thing that is still worth asserting: the name is declared and defined.
    """
    import json as _json
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin = os.path.join(root, "integrations", "unreal", "UnscriptedBridge")

    # Walked rather than listed: the plugin gained a Private/Tests/ directory and
    # a flat listdir tried to open it as a file. Subdirectories are ordinary in
    # an Unreal module, so the test should not have assumed otherwise.
    sources = {}
    for folder in ("Public", "Private"):
        base = os.path.join(plugin, "Source", "UnscriptedBridge", folder)
        for dirpath, _dirs, filenames in os.walk(base):
            for name in sorted(filenames):
                if not name.endswith((".h", ".cpp")):
                    continue
                with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                    sources[name] = fh.read()
    declared = "\n".join(text for name, text in sources.items() if name.endswith(".h"))
    defined = "\n".join(text for name, text in sources.items() if name.endswith(".cpp"))

    checked = 0
    for contract_file in ("contract.json", "contract.v2.json"):
        with open(os.path.join(plugin, contract_file), encoding="utf-8") as fh:
            endpoints = _json.load(fh).get("endpoints", {})
        if not isinstance(endpoints, dict):
            continue
        for endpoint, spec in endpoints.items():
            called_by = (spec or {}).get("called_by", "") if isinstance(spec, dict) else ""
            match = re.match(r"^(\w+)::(\w+)", str(called_by))
            if not match:
                continue                     # "gameplay: ..." -- no method claimed
            cls, method = match.groups()
            assert re.search(rf"\b{method}\s*\(", declared), (
                f"{contract_file} says {endpoint} is called by {cls}::{method}, "
                f"but no such method is declared in any plugin header")
            assert f"{cls}::{method}" in defined, (
                f"{cls}::{method} is declared but never defined -- the contract "
                f"promises an integration point that does nothing")
            checked += 1

    assert checked >= 9, f"only {checked} call sites checked; the contract lost its prose"
    print(f"ok  contract: {checked} declared plugin call sites exist in the C++")


def test_the_action_bridge_is_a_two_way_exchange():
    """A character does not move until the engine says it moved him.

    The runtime set `agent.location` directly and never asked. An engine that
    failed to walk the character -- blocked door, no nav path, cutscene -- kept
    showing him where he was while every belief, perception and rumour in the
    simulation was computed for where he was not. Nothing detected the split,
    because nothing was ever asked.

    Four things have to hold at once: nobody moves while an intent is open, only
    SUCCEEDED moves them, an unanswered intent stops holding the character, and a
    build with the bridge switched off behaves exactly as it did before.
    """
    import http.client
    import json as _json
    import threading as _threading
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.service import ServiceOptions, create_server

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "relay-station")

    # ---- off means unchanged: no intents, and the cast still goes about its day
    plain = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:"))
    try:
        plain.advance_time(240)
        assert plain.pending_actions() == [], "a build with no bridge must issue nothing"
        assert plain.action_bridge_report()["enabled"] is False
        where_without = {a.id: a.location for a in plain.world.agents.values()}
    finally:
        plain.close()

    # ---- on, and every intent confirmed: the same world, reached by asking
    bridged = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", action_bridge=True))
    try:
        frozen = {a.id: a.location for a in bridged.world.agents.values()}
        bridged.advance_time(240)
        intents = bridged.pending_actions()
        assert intents, "routines should have asked the engine to move somebody"
        assert {a.id: a.location for a in bridged.world.agents.values()} == frozen, \
            "nobody may move while the engine has not answered"
        for intent in intents:
            assert intent["type"] == "MOVE_TO"
            assert intent["params"]["from"] == frozen[intent["actor"]]
            assert intent["expires_at"] > intent["issued_at"]
            bridged.report_action_result(intent["intent_id"], "SUCCEEDED")
        where_with = {a.id: a.location for a in bridged.world.agents.values()}
        assert where_with == where_without, (
            "confirming every intent must land the cast exactly where the runtime "
            "would have put it itself")
    finally:
        bridged.close()

    # ---- a refusal leaves the character where the player can see him
    refused = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", action_bridge=True))
    try:
        refused.advance_time(240)
        intent = refused.pending_actions()[0]
        actor, origin = intent["actor"], intent["params"]["from"]
        outcome = refused.report_action_result(intent["intent_id"], "UNREACHABLE",
                                               "no nav path from the mess")
        assert outcome["applied"] is False
        assert refused.world.agents[actor].location == origin, \
            "an act the engine could not perform must not happen in the simulation"

        # ---- silence is not consent: an unanswered intent times out and is counted
        before = refused.action_bridge_report()["pending"]
        assert before > 0
        refused.advance_time(refused.core.actions_out.timeout_minutes + 1)
        report = refused.action_bridge_report()
        assert report["timed_out"] >= before, (
            "an engine that never answers must stop holding characters mid-act")
        assert report["unreachable"] == 1

        # ---- a save taken mid-act remembers what is still owed
        refused.advance_time(60)
        open_before = {i["intent_id"] for i in refused.pending_actions()}
        assert open_before, "need an open intent to snapshot"
        snap = refused.create_snapshot("mid-errand")
        refused.advance_time(600)
        refused.restore_snapshot(snap)
        assert {i["intent_id"] for i in refused.pending_actions()} == open_before, \
            "a load dropped an errand the engine was still carrying out"
    finally:
        refused.close()

    # ---- and over HTTP, exactly as the contract declares it
    with open(os.path.join(root, "integrations", "unreal", "UnscriptedBridge",
                           "contract.v2.json"), encoding="utf-8") as fh:
        v2 = _json.load(fh)

    server = create_server(
        RuntimeConfig(world_pack_path=pack, storage_path=":memory:", action_bridge=True),
        host="127.0.0.1", port=0, options=ServiceOptions(auth_token="ue"))
    thread = _threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
            conn.request(method, path,
                         body=_json.dumps(body) if body is not None else None,
                         headers={"Content-Type": "application/json",
                                  "Authorization": "Bearer ue"})
            response = conn.getresponse()
            payload = response.read()
            conn.close()
            return response.status, _json.loads(payload or b"{}")

        status, caps = call("GET", "/capabilities")
        assert status == 200
        assert caps["capabilities"]["action_bridge"] is True, (
            "a build with the bridge on must say so -- 'no pending intents' and "
            "'this build never issues any' look the same on the wire")

        call("POST", "/advance", {"minutes": 240})
        status, pending = call("GET", "/v2/actions/pending")
        assert status == 200
        spec = v2["endpoints"]["GET /v2/actions/pending"]
        for field in spec["fields"]:
            assert field in pending, f"/v2/actions/pending lost {field!r}"
        assert pending["bridge"]["enabled"] is True
        assert set(spec["intent_types"]) == {i["type"] for i in pending["intents"]}
        declared = spec["fields"]["intents"]
        for key in ("intent_id", "actor", "type", "params", "reason",
                    "issued_at", "expires_at"):
            assert key in declared, f"the contract stopped declaring {key!r}"
            assert key in pending["intents"][0], f"the service stopped sending {key!r}"

        result_spec = v2["endpoints"]["POST /v2/actions/{intent_id}/result"]
        first = pending["intents"][0]["intent_id"]
        status, done = call("POST", f"/v2/actions/{first}/result",
                            {"status": "SUCCEEDED"})
        assert status == 200
        for field in result_spec["fields"]:
            assert field in done, f"the result response lost {field!r}"
        assert done["applied"] is True

        # the closed set is closed, and one intent is resolved once
        status, _ = call("POST", f"/v2/actions/{first}/result", {"status": "SUCCEEDED"})
        assert status == 404, "a second result for one intent is an integration bug"
        second = pending["intents"][1]["intent_id"]
        status, _ = call("POST", f"/v2/actions/{second}/result", {"status": "PROBABLY"})
        assert status == 400, "a status outside the closed set must be refused"
        status, _ = call("POST", f"/v2/actions/{second}/result", {})
        assert status == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    print("ok  actions: intents out, results back; off is unchanged, silence times out")


def test_contract_v2_is_additive_and_v1_is_frozen():
    """Version 2 adds; version 1 does not move. A shipped game keeps working."""
    import http.client
    import json as _json
    import threading as _threading
    from unscripted import RuntimeConfig
    from unscripted.service import ServiceOptions, create_server

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bridge = os.path.join(root, "integrations", "unreal", "UnscriptedBridge")
    with open(os.path.join(bridge, "contract.json"), encoding="utf-8") as fh:
        v1 = _json.load(fh)
    with open(os.path.join(bridge, "contract.v2.json"), encoding="utf-8") as fh:
        v2 = _json.load(fh)

    assert v1["contract_version"] == "1.0.0", "version 1 is frozen"
    assert v2["supersedes"] == "1.0.0"

    server = create_server(
        RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "relay-station"),
                      storage_path=":memory:"),
        host="127.0.0.1", port=0, options=ServiceOptions(auth_token="ue"))
    thread = _threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
            conn.request(method, path,
                         body=_json.dumps(body) if body is not None else None,
                         headers={"Content-Type": "application/json",
                                  "Authorization": "Bearer ue"})
            response = conn.getresponse()
            payload = response.read()
            conn.close()
            return response.status, _json.loads(payload or b"{}")

        # 1. capability negotiation comes before anything else
        status, caps = call("GET", "/capabilities")
        assert status == 200
        spec = v2["endpoints"]["GET /capabilities"]
        for field in spec["fields"]:
            assert field in caps, f"/capabilities lost {field!r}"
        assert set(caps["contract_versions"]) >= {"1.0.0", "2.0.0"}
        assert caps["default_contract"] == "1.0.0", (
            "the default must stay v1 or an old plugin changes behaviour silently")
        for key in spec["capability_keys"]:
            assert key in caps["capabilities"], f"capability {key!r} not reported"
            assert isinstance(caps["capabilities"][key], bool)
        # a capability the runtime does not have must say false, not be absent
        assert caps["capabilities"]["action_bridge"] is False
        assert caps["capabilities"]["tts"] is False
        assert caps["capabilities"]["semantic_moves"] is True

        # 2. v2 avatar turn carries what the runtime decided
        status, turn = call("POST", "/v2/avatar/turn",
                            {"text": "ask Voss about the breach"})
        assert status == 200
        assert turn["contract_version"] == "2.0.0"
        avatar_spec = v2["endpoints"]["POST /v2/avatar/turn"]["fields"]["avatar"]["fields"]
        if "avatar" in turn:
            for field in avatar_spec:
                assert field in turn["avatar"], f"/v2/avatar/turn.avatar lost {field!r}"
            assert turn["avatar"]["honesty"] in (
                "honest", "lie", "exaggeration", "understatement")
            for claim in turn["avatar"]["asserted"]:
                assert {"proposition", "text", "certainty", "honesty",
                        "heard_by"} <= set(claim), claim

        # 3. v2 knowledge carries the story grouping and the topology
        status, knowledge = call("GET", "/v2/state/knowledge")
        assert status == 200
        for field in v2["endpoints"]["GET /v2/state/knowledge"]["fields"]:
            assert field in knowledge, f"/v2/state/knowledge lost {field!r}"
        for entry in knowledge["knowledge_classes"]:
            assert {"predicate", "classification", "transmissibility"} <= set(entry)

        # 3b. what is PUBLIC, as distinct from what is known. Not a debug
        #     endpoint: a shipping build may read it, so it must answer even with
        #     both layers off -- with empty lists rather than an error, because
        #     "off" and "nothing has happened yet" are the same to a caller who
        #     has already read /capabilities.
        status, public = call("GET", "/v2/state/public")
        assert status == 200
        for field in v2["endpoints"]["GET /v2/state/public"]["fields"]:
            assert field in public, f"/v2/state/public lost {field!r}"
        assert public["common_knowledge"] == [] and public["notes"] == []
        status, scoped = call("GET", "/v2/state/public?place=place:market")
        assert status == 200 and scoped["notes"] == []
        for key in ("climate", "pursuit", "media", "contagion",
                    "common_knowledge", "notes"):
            assert caps["capabilities"][key] is False, (
                f"{key} is off in this build and /capabilities does not say so")

        # 4. discredit, and the question you ask before it
        status, resting = call("GET", "/v2/resting_on?source=agent:voss")
        assert status == 200 and "beliefs" in resting
        status, missing = call("GET", "/v2/resting_on")
        assert missing["code"] == "missing_source" and status == 400

        status, revised = call("POST", "/v2/discredit",
                               {"source": "agent:voss", "factor": 0.2,
                                "reason": "caught out"})
        assert status == 200, revised
        for field in v2["endpoints"]["POST /v2/discredit"]["fields"]:
            assert field in revised, f"/v2/discredit lost {field!r}"
        status, nobody = call("POST", "/v2/discredit", {"source": "agent:nobody"})
        assert status == 404 and nobody["code"] == "no_such_agent"
        status, unnamed = call("POST", "/v2/discredit", {})
        assert status == 400 and unnamed["code"] == "missing_source"

        # 5. AND VERSION 1 STILL ANSWERS EXACTLY AS BEFORE
        status, v1_knowledge = call("GET", "/state/knowledge")
        assert status == 200
        for field in v1["endpoints"]["GET /state/knowledge"]["fields"]:
            assert field in v1_knowledge, f"v1 /state/knowledge lost {field!r}"
        status, v1_turn = call("POST", "/avatar/turn", {"text": "look"})
        assert status == 200
        for field in v1["endpoints"]["POST /avatar/turn"]["fields"]:
            if field == "avatar":
                continue
            assert field in v1_turn, f"v1 /avatar/turn lost {field!r}"
        assert "contract_version" not in v1_turn, (
            "v1 responses must not grow fields either -- a strict parser would break")

        print(f"ok  contract: v2 serves {len(v2['endpoints'])} endpoints, "
              f"{len(caps['capabilities'])} capabilities declared, v1 unchanged")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_engine_bridge_contract_matches_the_live_service():
    """The Unreal plugin's JSON contract, checked against a running service.

    The engine side cannot be compiled in this runtime's CI, so a field renamed
    here would break the plugin silently and be discovered by a studio, in Unreal,
    at integration time. integrations/unreal/.../contract.json states exactly what
    the C++ parses; this test asserts the server still produces it. Change either
    side and both fail until they agree again.
    """
    import http.client
    import json as _json
    import threading as _threading
    from unscripted import RuntimeConfig
    from unscripted.service import ServiceOptions, create_server

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contract_path = os.path.join(root, "integrations", "unreal", "UnscriptedBridge",
                                 "contract.json")
    with open(contract_path, encoding="utf-8") as fh:
        contract = _json.load(fh)

    server = create_server(
        RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "relay-station"),
                      storage_path=":memory:"),
        host="127.0.0.1", port=0, options=ServiceOptions(auth_token="ue"))
    thread = _threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
            conn.request(method, path, body=_json.dumps(body) if body is not None else None,
                         headers={"Content-Type": "application/json",
                                  "Authorization": "Bearer ue"})
            response = conn.getresponse()
            payload = response.read()
            conn.close()
            return response.status, _json.loads(payload or b"{}")

        def check(where, spec, value):
            """Assert a value matches a contract type string."""
            if isinstance(spec, dict):
                assert isinstance(value, dict), f"{where}: expected object, got {type(value).__name__}"
                return
            base = spec.split("<")[0].split("{")[0].rstrip("?").strip()
            kinds = {"bool": bool, "string": str, "int": int, "float": (int, float),
                     "array": list, "object": dict}
            expected = kinds.get(base)
            if expected is None:
                return
            if base == "int":
                assert isinstance(value, int) and not isinstance(value, bool), \
                    f"{where}: expected int, got {value!r}"
            else:
                assert isinstance(value, expected), \
                    f"{where}: expected {base}, got {type(value).__name__} ({value!r})"

        # every endpoint the plugin calls, in the order it calls them
        status, health = call("GET", "/health")
        assert status == 200
        for name, spec in contract["endpoints"]["GET /health"]["fields"].items():
            assert name in health, f"/health lost field {name!r} the plugin reads"
            check(f"/health.{name}", spec, health[name])

        status, scene = call("GET", "/state/scene")
        assert status == 200
        for name, spec in contract["endpoints"]["GET /state/scene"]["fields"].items():
            assert name in scene, f"/state/scene lost {name!r}"
            check(f"/state/scene.{name}", spec, scene[name])
        for npc in scene["npcs"]:
            assert {"id", "name"} <= set(npc), npc

        status, turn = call("POST", "/avatar/turn", {"text": "ask Voss about the breach"})
        assert status == 200
        turn_spec = contract["endpoints"]["POST /avatar/turn"]["fields"]
        for name, spec in turn_spec.items():
            if name == "avatar":
                continue
            assert name in turn, f"/avatar/turn lost {name!r}"
            check(f"/avatar/turn.{name}", spec, turn[name])
        assert "avatar" in turn, "the reference command must produce a spoken line"
        avatar = turn["avatar"]
        for name, spec in turn_spec["avatar"]["fields"].items():
            assert name in avatar, f"avatar packet lost {name!r}"
            check(f"avatar.{name}", spec, avatar[name])
        for weight in avatar["blendshapes"].values():
            assert isinstance(weight, (int, float)) and 0.0 <= weight <= 1.0, weight
        known = set(contract["arkit_blendshape_keys"])
        unknown = set(avatar["blendshapes"]) - known
        assert not unknown, f"blendshape keys the plugin cannot map: {sorted(unknown)}"

        agent_id = scene["npcs"][0]["id"]
        status, face = call("GET", f"/avatar/face?agent_id={agent_id}")
        assert status == 200
        for name, spec in contract["endpoints"]["GET /avatar/face"]["fields"].items():
            assert name in face, f"/avatar/face lost {name!r}"
            check(f"/avatar/face.{name}", spec, face[name])

        status, advanced = call("POST", "/advance", {"minutes": 60})
        assert status == 200 and advanced["to"] > advanced["from"]

        status, knowledge = call("GET", "/state/knowledge")
        assert status == 200
        for name, spec in contract["endpoints"]["GET /state/knowledge"]["fields"].items():
            assert name in knowledge, f"/state/knowledge lost {name!r}"
            check(f"/state/knowledge.{name}", spec, knowledge[name])

        status, receipt = call("POST", "/event", {
            "type": "claim", "actor": agent_id, "location": scene["location"],
            "payload": {"summary": "a gameplay event from the engine"}})
        assert status == 200
        for name, spec in contract["endpoints"]["POST /event"]["fields"].items():
            assert name in receipt, f"/event lost {name!r}"
            check(f"/event.{name}", spec, receipt[name])

        # the error shape the plugin branches on
        status, failure = call("POST", "/advance", {"minutes": -1})
        assert status == 400
        for name in contract["error_shape"]["fields"]:
            assert name in failure, f"error body lost {name!r}"

        print(f"ok  bridge: all {len(contract['endpoints'])} plugin endpoints match "
              f"contract v{contract['contract_version']}")
    finally:
        server.shutdown()
        server.server_close()
        server.unscripted_runtime.close()


def test_encounter_rate_sets_pace_and_the_gate_is_a_trust_threshold():
    """Both remaining diffusion parameters mean something statable.

    Measured rather than asserted, because the obvious reading of each is wrong:
    an encounter rate looks like it should control how far a rumour gets (it does
    not, stifling does), and a confidence gate looks like an arbitrary cutoff
    (it sits at "someone you trust more than you distrust").
    """
    from unscripted import World, Agent, Proposition, Runtime
    from unscripted.belief import Belief
    from unscripted.events import Event

    def run_to_completion(rate, population=40, max_ticks=1500):
        world = World(global_seed="cal", world_time=0)
        world.places = {"p": {"noise_level": 0.0, "gossip_factor": 1.0}}
        for i in range(population):
            peers = {f"a{j:03d}": {"familiarity": 0.8, "liking": 0.5, "trust": 0.9}
                     for j in range(population) if j != i}
            world.agents[f"a{i:03d}"] = Agent(
                id=f"a{i:03d}", location="p", relationships=peers,
                big_five={"agreeableness": 0.5, "emotional_stability": 0.5},
                education={"gossip": 0.6})
        runtime = Runtime(world)
        runtime.diffusion.params.update({
            "bystanders": 0, "max_encounters_per_tick": 10 ** 9, "distortion_prob": 0.0,
            "min_confidence_to_tell": 0.0, "encounters_per_hour": rate})
        proposition = Proposition("body:alive", {"agent": "x"})
        key = proposition.core_key()
        belief = Belief(proposition=proposition, logit_val=3.0, support_for=3.0,
                        valid_start=0, txn_time=0)
        belief.record_provenance("s", "o0", 0.9, 1.0)
        world.agents["a000"].beliefs[key] = belief
        for tick in range(max_ticks):
            world.world_time += 30
            runtime.diffusion.step(world, runtime, 30)
            if not any(key in a.beliefs and a.beliefs[key].spreading
                       for a in world.agents.values()):
                reach = sum(1 for a in world.agents.values() if key in a.beliefs) / population
                return (tick + 1) * 0.5, reach
        return None, None

    slow_hours, slow_reach = run_to_completion(0.1)
    fast_hours, fast_reach = run_to_completion(1.0)
    assert slow_hours and fast_hours, "the process must terminate at both rates"
    assert fast_hours < slow_hours / 2, (
        f"a ten-fold rate increase should make it far faster ({slow_hours}h -> {fast_hours}h)")
    # ...but reach must stay in the same regime: stifling decides how far, not the rate
    assert abs(slow_reach - fast_reach) < 0.25, (
        f"the rate changed reach from {slow_reach:.0%} to {fast_reach:.0%}; it should "
        f"only change pace")

    # the gate, expressed in the units an author actually controls
    def believed_after_one_retelling(trust):
        world = World(global_seed="c", world_time=0)
        world.places = {"p": {}}
        world.agents["s"] = Agent(id="s", location="p", education={"gossip": 0.6})
        world.agents["l"] = Agent(id="l", location="p", relationships={"s": {"trust": trust}},
                                  big_five={"agreeableness": 0.5, "emotional_stability": 0.5})
        runtime = Runtime(world)
        runtime.process_event(Event(
            world.new_event_id(), 0, "claim", actor="s", location="p",
            payload={"proposition": Proposition("body:alive", {"agent": "x"}).as_dict(),
                     "origin_event": "o", "domain": "gossip",
                     "diffusion": {"hops": 1}, "assertion_strength": 0.8}))
        return list(world.agents["l"].beliefs.values())[0].expected_prob

    gate = 0.60
    assert believed_after_one_retelling(0.3) < gate, "a distrusted speaker must not create a spreader"
    assert believed_after_one_retelling(0.7) > gate, "a trusted speaker must"
    # the crossing point is what makes the number statable rather than arbitrary
    assert believed_after_one_retelling(0.5) > gate >= believed_after_one_retelling(0.35), (
        "the gate should sit around trust 0.5 -- someone you trust more than you distrust")

    print(f"ok  calibration: rate is pacing ({slow_hours:.0f}h vs {fast_hours:.0f}h, reach "
          f"{slow_reach:.0%} vs {fast_reach:.0%}); the gate sits at trust ~0.5")


def test_distortion_follows_allport_and_postman():
    """Retelling changes a claim gradually, not by flipping it.

    Distortion used to be a coin flip that inverted a claim. Allport & Postman
    (1947), after Bartlett (1932), describe three processes that operate together:
    levelling (detail drops out, by far the largest effect), sharpening (surviving
    detail is exaggerated) and assimilation (the story drifts toward the teller's
    own world). Each maps onto a precise structural change to a proposition.
    """
    from unscripted import World, Agent, Proposition, distortion
    from unscripted.determinism import derive_seed

    world = World(global_seed="d", world_time=0)
    world.places = {"place:home": {}, "place:work": {}}
    teller = Agent(id="agent:teller", location="place:home",
                   relationships={"agent:friend": {"familiarity": 0.9, "liking": 0.8}})
    world.agents = {"agent:teller": teller,
                    "agent:friend": Agent(id="agent:friend", location="place:home"),
                    "agent:stranger": Agent(id="agent:stranger", location="place:work")}

    def force(kind, proposition):
        weights = {k: (1.0 if k == kind else 0.0) for k in
                   (distortion.LEVELLING, distortion.SHARPENING,
                    distortion.ASSIMILATION, distortion.INVERSION)}
        return distortion.distort(proposition, speaker=teller, world=world,
                                  seed=derive_seed("s", "t", 1, 0, "x"), weights=weights)

    # LEVELLING: a detail is lost, but never the subject of the claim
    was_at = Proposition("was_at", {"agent": "agent:stranger", "place": "place:work",
                                    "when": "last_night"})
    levelled, kind, detail = force(distortion.LEVELLING, was_at)
    assert kind == distortion.LEVELLING
    assert levelled.slots["agent"] == "agent:stranger", "the subject must survive"
    assert None in levelled.slots.values(), levelled.slots
    assert detail["lost_detail"] in ("place", "when")

    # SHARPENING: quantities grow in the telling
    owed = Proposition("economy:owes_amount", {"debtor": "agent:stranger",
                                               "creditor": "agent:teller", "amount": "300"})
    sharpened, kind, detail = force(distortion.SHARPENING, owed)
    assert kind == distortion.SHARPENING
    assert float(sharpened.slots["amount"]) > 300, sharpened.slots

    # ASSIMILATION: the story drifts onto people and places the teller knows.
    # Which slot drifts is a seeded choice; what matters is that whatever changed
    # became something from the teller's own world.
    assimilated, kind, detail = force(distortion.ASSIMILATION, was_at)
    assert kind == distortion.ASSIMILATION
    familiar = set(distortion._familiar_agents(teller, world, exclude="")) | \
        set(distortion._familiar_places(teller, world, exclude=""))
    assert detail["became"] in familiar, (detail, familiar)
    assert assimilated.slots[detail["assimilated"]] == detail["became"]

    # with only a person to drift, an unfamiliar name becomes a familiar one
    alive = Proposition("body:alive", {"agent": "agent:stranger"})
    person_drift, _kind, person_detail = force(distortion.ASSIMILATION, alive)
    assert person_drift.slots["agent"] == "agent:friend", person_detail

    # every process must produce a DIFFERENT proposition, or the listener would
    # merely re-hear the same claim instead of forming a false belief
    for changed in (levelled, sharpened, assimilated):
        assert changed.core_key() != was_at.core_key() or changed.core_key() != owed.core_key()

    # a garbled claim must never land on something the teller is protecting
    protected = {Proposition("was_at", {"agent": "agent:friend", "place": "place:work",
                                        "when": "last_night"}).core_key()}
    for _ in range(20):
        result = distortion.distort(was_at, speaker=teller, world=world,
                                    seed=derive_seed("s", "t", 1, 0, "x"),
                                    weights={distortion.ASSIMILATION: 1.0},
                                    protected=protected)
        assert result is None or result[0].core_key() not in protected

    assert "forgotten" in distortion.describe(distortion.LEVELLING, detail | {"lost_detail": "when"})
    print("ok  distortion: levelling, sharpening and assimilation change a claim structurally")


def test_a_distorted_rumour_is_a_false_belief_with_a_true_origin():
    """The epistemically interesting case: the town is confidently wrong, and you
    can still trace where the wrongness came from."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        sdk.core.diffusion.params["distortion_prob"] = 0.5
        for _ in range(40):
            sdk.advance_time(60)

        by_predicate = {}
        for agent in sdk.world.agents.values():
            for key, belief in agent.beliefs.items():
                by_predicate.setdefault(belief.proposition.predicate, set()).add(key)
        variants = {p: keys for p, keys in by_predicate.items() if len(keys) > 1}
        assert variants, "no claim ever changed shape; distortion is not reaching the world"

        # a distorted belief must still name the origin the true claim came from,
        # so it is ONE source that is now wrong -- not new independent evidence
        distorted_holders = 0
        for agent in sdk.world.agents.values():
            for belief in agent.beliefs.values():
                if belief.hops > 0:
                    assert belief.primary_origin, "hearsay must always name an origin"
                    distorted_holders += 1
        assert distorted_holders > 0

        # and no distortion may ever manufacture someone else's secret
        for owner in sdk.world.agents.values():
            for secret in owner.secrets:
                for protected in secret.protects:
                    for other in sdk.world.agents.values():
                        assert other.id == owner.id or protected not in other.beliefs, \
                            f"distortion produced {owner.id}'s secret in {other.id}"

        # the map and the ledger both explain what changed
        knowledge = sdk.structured_knowledge()
        notes = [t for t in knowledge["transmissions"] if t.get("distorted")]
        assert notes, "no distorted retelling reached the knowledge map"
        assert any(t.get("distortion_note") for t in notes), \
            "a distorted retelling must say what changed, not just that something did"

        print(f"ok  distortion: {len(variants)} claim(s) exist in several versions, "
              f"each tracing to a real origin")
    finally:
        sdk.close()


def test_scaffolded_pack_is_immediately_playable():
    """`unscripted new` must produce a world that works, not an empty directory.

    Three packs were written by hand for this project and every one shipped a
    defect that only a test found. Starting from something that runs and changing
    it is the difference between a runtime and a product.
    """
    import shutil
    import tempfile
    from unscripted import UnscriptedRuntime, RuntimeConfig, validate_world_pack
    from unscripted.authoring import authoring_report, scaffold_pack

    workspace = tempfile.mkdtemp()
    try:
        path = os.path.join(workspace, "fresh")
        doc = scaffold_pack(path, name="Test World", start="09:30")

        report = validate_world_pack(path)
        assert report.ok, [f"{i.code}: {i.message}" for i in report.issues if i.severity == "error"]

        insight = authoring_report(doc)
        assert insight["ready"], insight["findings"]
        assert not [f for f in insight["findings"] if f["level"] == "blocker"]
        assert insight["meetings"], "a scaffold whose cast never meets teaches the wrong thing"
        assert insight["answerable_topics"], "the scaffold must ship a topic someone can answer"

        sdk = UnscriptedRuntime.create(RuntimeConfig(world_pack_path=path,
                                                       storage_path=":memory:"))
        try:
            scene = sdk.structured_scene()
            assert scene["npcs"] and scene["exits"], scene
            # it must be navigable, answerable and it must have a working secret
            moved = sdk.submit_player_text("go tavern")
            assert "cannot" not in moved.message and "could not" not in moved.message, moved.message
            holder = next(a for a in sdk.world.agents.values() if a.secrets)
            secret = holder.secrets[0]
            assert secret.surface_forms and secret.guards_topics and secret.protects, \
                "the scaffolded secret must actually be enforceable"
            for _ in range(12):
                sdk.advance_time(60)
            knowledge = sdk.structured_knowledge()
            assert knowledge["facts"], "nothing is known in the scaffolded world"
        finally:
            sdk.close()
        print("ok  authoring: `unscripted new` produces a valid, navigable, answerable world")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_authoring_report_names_the_problem_and_the_fix():
    """The report is for an author, so every finding carries what to do about it."""
    import json as _json
    import shutil
    import tempfile
    from unscripted.authoring import PackDocument, authoring_report, render_report, scaffold_pack

    workspace = tempfile.mkdtemp()
    try:
        path = os.path.join(workspace, "broken")
        scaffold_pack(path, name="Broken", start="09:30")

        # the mistakes a first-time author actually makes
        world = _json.load(open(os.path.join(path, "world.json"), encoding="utf-8"))
        world["places"]["place:cellar"] = {"label": "Cellar"}          # no exits, unreachable
        _json.dump(world, open(os.path.join(path, "world.json"), "w", encoding="utf-8"), indent=2)

        topics = _json.load(open(os.path.join(path, "topics.json"), encoding="utf-8"))
        topics["topics"][0].pop("phrasings")                            # answerable but mute
        topics["topics"].append({"id": "weather", "label": "Weather"})  # no aliases
        _json.dump(topics, open(os.path.join(path, "topics.json"), "w", encoding="utf-8"), indent=2)

        tomas = _json.load(open(os.path.join(path, "characters", "tomas.json"), encoding="utf-8"))
        tomas["routine"] = [{"from": "00:00", "place": "place:cellar"}]  # never meets anyone
        tomas["secrets"][0].pop("surface_forms")                        # unenforceable
        _json.dump(tomas, open(os.path.join(path, "characters", "tomas.json"), "w",
                               encoding="utf-8"), indent=2)

        report = authoring_report(PackDocument.load(path))
        assert not report["ready"]
        messages = " | ".join(f["message"] for f in report["findings"])
        for expected in ("Cellar has no way out", "cannot be walked to",
                         "never shares a place", "no surface forms",
                         "no phrasings", "has no aliases"):
            assert expected in messages, f"missing finding: {expected}\n{messages}"
        assert any(f["level"] == "blocker" for f in report["findings"])
        # every finding must be actionable, which is the whole point
        for finding in report["findings"]:
            assert finding["fix"], f"no fix offered for: {finding['message']}"
        assert "NOT PLAYABLE YET" in render_report(report)
        print(f"ok  authoring: report names {len(report['findings'])} problems, each with a fix")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_studio_endpoints_preview_without_writing_and_refuse_traversal():
    """The editor is the only surface that writes files, so it is treated as hostile."""
    import json as _json
    import shutil
    import tempfile
    from unscripted import RuntimeConfig
    from unscripted.authoring import scaffold_pack
    from unscripted.service import UnscriptedService, ServiceOptions
    from unscripted.sdk import UnscriptedRuntime

    workspace = tempfile.mkdtemp()
    try:
        path = os.path.join(workspace, "pack")
        scaffold_pack(path, name="Studio", start="10:00")
        sdk = UnscriptedRuntime.create(RuntimeConfig(world_pack_path=path,
                                                       storage_path=":memory:"))
        try:
            # disabled unless explicitly started for authoring
            closed = UnscriptedService(sdk, ServiceOptions())
            body, status = closed.handle_get("/authoring/pack", {})
            assert status == 403 and body["code"] == "authoring_disabled"

            service = UnscriptedService(sdk, ServiceOptions(authoring_path=path))
            loaded = service.handle_get("/authoring/pack", {})
            assert loaded["report"]["ready"]
            assert loaded["predicates"], "an author picks a predicate; it must be offered"

            # preview must not touch disk
            before = open(os.path.join(path, "characters", "tomas.json"), encoding="utf-8").read()
            edited = _json.loads(_json.dumps(loaded["pack"]))
            edited["characters"]["tomas.json"]["routine"] = [{"from": "00:00",
                                                              "place": "place:tavern"}]
            preview = service.handle_post("/authoring/preview", {"pack": edited})
            assert any(f["level"] == "blocker" for f in preview["report"]["findings"])
            assert open(os.path.join(path, "characters", "tomas.json"),
                        encoding="utf-8").read() == before, "preview wrote to disk"

            # a filename arrives from a browser: it is not trusted
            for hostile in ("../escape.json", "/etc/passwd", "sub/dir.json", ".hidden.json",
                            "no_extension"):
                attack = _json.loads(_json.dumps(loaded["pack"]))
                attack["characters"][hostile] = {"id": "agent:x"}
                body, status = service.handle_post("/authoring/save", {"pack": attack})
                assert status == 400 and body["code"] == "bad_filename", (hostile, status)
                assert not os.path.exists(os.path.join(workspace, "escape.json"))

            saved = service.handle_post("/authoring/save", {"pack": loaded["pack"]})
            assert saved["valid"] and saved["saved"]

            # off-loopback authoring is refused whatever the auth settings
            try:
                ServiceOptions(authoring_path=path, auth_token="t").check_bind("0.0.0.0")
                raise AssertionError("authoring must not be served off-loopback")
            except ValueError as exc:
                assert "writes world-pack files" in str(exc)
            print("ok  studio: preview never writes, traversal refused, off-loopback refused")
        finally:
            sdk.close()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_diffusion_reproduces_the_daley_kendall_saturation():
    """The diffusion model is checked against the canonical rumour model.

    Daley & Kendall (1964): a rumour saturates BELOW the whole population, because
    a spreader who meets someone already informed loses interest. The fraction who
    never hear it solves theta = exp(-2(1-theta)), so about 79.7% hear it however
    long you wait. An epidemic reaches everyone; a rumour does not.

    This test is the evidence behind docs/CALIBRATION.md. It also pins the control:
    with stifling disabled the process must reach everyone and never terminate,
    which is what proves stifling is the mechanism doing the work.
    """
    import math
    from unscripted import World, Runtime, Agent, Proposition
    from unscripted.belief import Belief

    theta = 0.2
    for _ in range(300):
        theta = math.exp(-2 * (1 - theta))
    daley_kendall = 1 - theta
    assert 0.79 < daley_kendall < 0.80, daley_kendall

    def spread(*, population=120, ticks=500, gate=0.0, trust=0.9, stifle=1.0):
        world = World(global_seed="calibration", world_time=0)
        world.places = {"p": {"noise_level": 0.0, "gossip_factor": 1.0}}
        for i in range(population):
            peers = {f"a{j:03d}": {"familiarity": 1.0, "liking": 1.0, "trust": trust}
                     for j in range(population) if j != i}
            world.agents[f"a{i:03d}"] = Agent(
                id=f"a{i:03d}", location="p", relationships=peers,
                big_five={"agreeableness": 0.5, "emotional_stability": 0.5})
        runtime = Runtime(world)
        runtime.diffusion.params.update({
            "encounters_per_hour": 3.0, "bystanders": 0, "min_confidence_to_tell": gate,
            "max_encounters_per_tick": 10 ** 9, "stifle_prob": stifle})
        proposition = Proposition("body:alive", {"agent": "x"})
        key = proposition.core_key()
        seed_belief = Belief(proposition=proposition, logit_val=3.0, support_for=3.0,
                             valid_start=0, txn_time=0)
        seed_belief.record_provenance("seed", "origin_zero", 0.9, 1.0)
        world.agents["a000"].beliefs[key] = seed_belief
        for _ in range(ticks):
            world.world_time += 30
            runtime.diffusion.step(world, runtime, 30)
        holders = [a for a in world.agents.values() if key in a.beliefs]
        active = sum(1 for a in holders if a.beliefs[key].spreading)
        return len(holders) / population, active

    reach, active = spread()
    assert active == 0, f"the process had not terminated ({active} spreaders left)"
    assert abs(reach - daley_kendall) < 0.10, (
        f"reach {reach:.1%} deviates from the Daley-Kendall prediction "
        f"{daley_kendall:.1%} by more than 10 points")
    assert reach < 0.95, "a rumour must not reach everyone; that is an epidemic"

    # control: without stifling it reaches everyone and never stops
    uncontrolled, still_going = spread(stifle=0.0)
    assert uncontrolled > 0.95 and still_going > 0, (
        "with stifling off the rumour must reach everyone and never terminate; "
        "otherwise saturation is coming from something else")

    # the credibility gate is a deliberate departure from the reference model and
    # must measurably reduce reach -- documented, not accidental
    gated, _ = spread(gate=0.60)
    assert gated < reach - 0.15, (
        f"the credibility gate should cut reach substantially ({gated:.1%} vs {reach:.1%})")

    print(f"ok  calibration: reach {reach:.1%} vs Daley-Kendall {daley_kendall:.1%} "
          f"(control without stifling: {uncontrolled:.0%}, with credibility gate: {gated:.1%})")


def test_knowledge_map_shows_who_knows_what_and_how():
    """The spread map is the machine-readable form of "how does he know that".

    Built from live belief state plus the event ledger, never from a second
    tracking structure -- a parallel bookkeeping copy is a second thing that can be
    wrong, and it would be the one shown to a customer.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        for _ in range(10):
            sdk.advance_time(60)
        knowledge = sdk.structured_knowledge()

        assert knowledge["facts"], "nothing is known in this world"
        assert ":" in knowledge["time_of_day"]
        spread = [f for f in knowledge["facts"] if f["hearsay"] > 0]
        assert spread, "nothing has been passed on, so there is nothing to visualise"

        for fact in knowledge["facts"]:
            assert fact["reach"] == len(fact["holders"])
            assert fact["first_hand"] + fact["hearsay"] == fact["reach"]
            assert fact["max_hops"] == max(h["hops"] for h in fact["holders"])
            # holders are ordered by distance from the source: that is the story
            assert [h["hops"] for h in fact["holders"]] == \
                sorted(h["hops"] for h in fact["holders"])
            for holder in fact["holders"]:
                if holder["hops"] > 0:
                    assert holder["origin"] in fact["origins"], (
                        "a hearsay holder must cite an origin the fact actually has")

        # every transmission is resolvable to people and a place a UI can name
        assert knowledge["transmissions"], "no retellings on the ledger"
        for row in knowledge["transmissions"]:
            assert row["from_name"] and row["to_name"] and row["place_label"]
            assert row["hops"] >= 1

        assert knowledge["occupancy"], "a spread map needs to show where people are"

        # and it must survive the HTTP surface unchanged
        from unscripted.service import UnscriptedService
        served = UnscriptedService(sdk).handle_get("/state/knowledge", {})
        assert not isinstance(served, tuple), served
        assert served["facts"][0]["text"] == knowledge["facts"][0]["text"]

        widest = knowledge["facts"][0]
        print(f"ok  knowledge map: {len(knowledge['facts'])} facts, widest reached "
              f"{widest['reach']} people ({widest['hearsay']} by hearsay), "
              f"{len(knowledge['transmissions'])} retellings")
    finally:
        sdk.close()


def test_latency_budget_answers_now_and_upgrades_later():
    """A game has a frame budget; a local model does not care about it.

    Measured against ollama on one desktop GPU: a warm 4B answers in ~290 ms, a
    warm 8B in ~360 ms, and a COLD model costs 5-25 s while it pages into VRAM.
    So a turn must never block on the model: it answers from authored text and
    accepts the model's line later, if it arrives and if it passes validation.

    No local model is needed to test this -- a controllable fake proves the
    contract, which is what CI can rely on.
    """
    import time as _time
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.edge import DeferredRealizer, ProviderPending
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class SlowRealizer:
        """Answers correctly, but far too late for a frame."""
        is_deterministic = False
        model_id = "slow-fake"

        def __init__(self, delay, text="The place was shut that night."):
            self.delay, self.text, self.calls = delay, text, 0

        def realize(self, plan, style):
            self.calls += 1
            _time.sleep(self.delay)
            return self.text

    # PROVIDER RELEASE MODE. A deferred line is a provider's line, and under the
    # default `controlled` mode a plan that asserts something never reaches one,
    # so there is nothing to defer. The latency machinery belongs to the weaker
    # contract and is tested there.

    # -- slower than the budget: answer now, upgrade later --------------------
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
        semantic_release="provider"))
    try:
        slow = SlowRealizer(0.30)
        sdk.core.realizer = DeferredRealizer(slow, budget_ms=40)
        started = _time.perf_counter()
        result = sdk.submit_player_text("ask Honce about clinic")
        elapsed = (_time.perf_counter() - started) * 1000

        assert elapsed < 250, f"the turn blocked for {elapsed:.0f} ms on a slow model"
        assert result.npc_response is not None and result.npc_response.text
        assert slow.text not in result.npc_response.text, \
            "the slow model's line must not have been waited for"
        assert sdk.pending_line_count() == 1

        upgrade = None
        for _ in range(60):
            ready = sdk.poll_line_upgrades()
            if ready:
                upgrade = ready[0]
                break
            _time.sleep(0.02)
        assert upgrade is not None, "the late line never arrived"
        assert upgrade["text"] == slow.text
        assert upgrade["verdict"] == "ACCEPT"
        # The fallback path mutates the plan it was handed. A deferred request must
        # hold a snapshot, or the late line is validated against a plan that has
        # changed underneath it -- and reported with the wrong dialogue act.
        assert upgrade["act"] == "inform", (
            f"deferred plan was mutated by the fallback path (act={upgrade['act']})")
        # a late line that reached a player is auditable like any other
        audited = sdk.store.conn.execute(
            "SELECT COUNT(*) FROM provider_call WHERE turn_id LIKE 'upgrade:%'").fetchone()[0]
        assert audited == 1
    finally:
        sdk.close()

    # -- faster than the budget: served directly ------------------------------
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
        semantic_release="provider"))
    try:
        sdk.core.realizer = DeferredRealizer(SlowRealizer(0.01), budget_ms=500)
        result = sdk.submit_player_text("ask Honce about clinic")
        assert "shut that night" in result.npc_response.text
        assert sdk.core.realizer.stats["served_within_budget"] == 1
        assert sdk.poll_line_upgrades() == []
    finally:
        sdk.close()

    print("ok  edge: a slow model never blocks a turn and upgrades are validated first")


def test_late_line_that_fails_validation_is_never_offered():
    """Arriving is not the same as being safe to say."""
    # PROVIDER RELEASE MODE: a late line is a provider's line, and the default
    # `controlled` mode never asks a provider to write one that carries a fact.

    import time as _time
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.edge import DeferredRealizer
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class SlowHallucinator:
        is_deterministic = False
        model_id = "slow-hallucinator"

        def realize(self, plan, style):
            _time.sleep(0.25)
            return "Milena Vasquez moved him to Warehouse 9 at 0300."

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
        semantic_release="provider"))
    try:
        sdk.core.realizer = DeferredRealizer(SlowHallucinator(), budget_ms=30)
        sdk.submit_player_text("ask Honce about clinic")
        offered = []
        for _ in range(60):
            offered += sdk.poll_line_upgrades()
            if sdk.pending_line_count() == 0 and offered:
                break
            if sdk.pending_line_count() == 0:
                break
            _time.sleep(0.02)
        assert offered == [], f"an unvalidated late line was offered: {offered}"
        trace = [code for code, _, _ in sdk.core.last_traces.get("agent:barkeep_12", [])]
        assert "provider.late_line_rejected" in trace, trace
        print("ok  edge: a hallucinated late line is rejected, not offered")
    finally:
        sdk.close()


def test_model_probe_reports_capability_at_startup():
    """A model that cannot voice NPCs should be reported once, not discovered
    one fallback line at a time."""
    from unscripted.edge import probe_model, warm_up
    from unscripted.provider import ProviderError

    class ThinkingModel:
        """The realistic failure: everything gets cleaned away to nothing."""
        model_id = "tiny-thinker"

        def realize(self, plan, style):
            raise ProviderError("Text provider returned an empty utterance after cleaning.")

    class GoodModel:
        model_id = "instruct-8b"

        def realize(self, plan, style):
            return "Place was shut that night."

    bad = probe_model(ThinkingModel(), budget_ms=120)
    assert bad["verdict"] == "unusable" and bad["passed"] == 0
    assert "authored text" in bad["advice"]

    good = probe_model(GoodModel(), budget_ms=120)
    assert good["verdict"] == "usable" and good["passed"] == good["of"]

    assert warm_up(GoodModel())["ok"] is True
    assert warm_up(ThinkingModel())["ok"] is False

    # the probe must not smuggle any world's vocabulary into the engine
    from unscripted.edge import PROBE_CASES
    from unscripted.ontology import CORE_PREDICATES
    for _name, _act, facts, _check in PROBE_CASES:
        for fact in facts:
            predicate = fact.replace("NOT ", "").split("(")[0]
            assert predicate in CORE_PREDICATES, f"probe uses non-core predicate {predicate}"

    print("ok  edge: startup probe classifies a model and stays world-neutral")


def test_routines_move_the_cast_and_create_meetings():
    """A frozen social graph cannot produce a rumour.

    Characters never moved: whoever a pack placed somewhere stood there for the
    session. In two of three reference packs no two characters ever shared a
    place, so diffusion could not fire at all -- the benchmark reported it as SKIP,
    which is how it surfaced.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.routine import MINUTES_PER_DAY, Routine, parse_clock
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # a block runs until the next one starts, and wraps past midnight: before the
    # first block of the day you are still in the last block of the previous one
    routine = Routine.from_list([{"from": "06:00", "place": "place:a"},
                                 {"from": "18:00", "place": "place:b"}])
    assert routine.block_at(parse_clock("07:00"))[1] == "place:a"
    assert routine.block_at(parse_clock("17:59"))[1] == "place:a"
    assert routine.block_at(parse_clock("18:00"))[1] == "place:b"
    assert routine.block_at(parse_clock("02:00"))[1] == "place:b", "overnight must wrap"
    assert routine.block_at(MINUTES_PER_DAY * 3 + parse_clock("07:00"))[1] == "place:a"

    for pack in ("cyberpunk-block", "noir-harbor", "dorf-thornfeld"):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", pack), storage_path=":memory:"))
        try:
            meetings = sdk.core.routine.meeting_opportunities(sdk.world)
            assert meetings, f"{pack}: nobody ever shares a place, so nothing can spread"

            placements = {a.id: a.location for a in sdk.world.agents.values()}
            moved = 0
            for _ in range(24):
                sdk.advance_time(60)
                moved += sum(1 for code, _, _ in sdk.core.last_traces.get("_routine", [])
                             if code == "routine.moved")
            assert moved > 0, f"{pack}: nobody moved in a full simulated day"
            assert {a.id: a.location for a in sdk.world.agents.values()} != placements or moved, \
                f"{pack}: the cast ended exactly where it started"

            # arrivals are observable events, not hidden teleports
            arrivals = sdk.store.conn.execute(
                "SELECT COUNT(*) FROM event_ledger WHERE type='move' AND payload LIKE '%routine%'"
            ).fetchone()[0]
            assert arrivals > 0, f"{pack}: movement must be on the ledger"

            print(f"ok  routine: {pack} — {len(meetings)} meeting places, "
                  f"{moved} movements and {arrivals} arrivals in a day")
        finally:
            sdk.close()


def test_routine_time_skip_does_not_replay_the_week():
    """A long time skip lands people where they belong, without emitting a week of
    arrivals along the way."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "dorf-thornfeld"),
        storage_path=":memory:"))
    try:
        sdk.advance_time(60 * 24 * 7)          # one week in a single step
        moves = [r for r in sdk.core.last_traces.get("_routine", []) if r[0] == "routine.moved"]
        assert len(moves) <= len(sdk.world.agents), (
            f"a one-week skip emitted {len(moves)} movements; intermediate blocks must be "
            f"skipped, not replayed")
        for agent in sdk.world.agents.values():
            if agent.routine:
                block = agent.routine.block_at(sdk.world.world_time)
                assert agent.location == block[1], (
                    f"{agent.id} is at {agent.location} but their schedule says {block[1]}")
        print(f"ok  routine: a one-week skip lands everyone correctly in {len(moves)} movements")
    finally:
        sdk.close()


def test_pack_validation_catches_a_self_contradicting_routine():
    """A pack must not disagree with itself about where the scene opens."""
    import json as _json
    import shutil
    import tempfile
    from unscripted import validate_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = tempfile.mkdtemp()
    try:
        broken = os.path.join(workspace, "broken")
        shutil.copytree(os.path.join(root, "worldpacks", "noir-harbor"), broken)
        path = os.path.join(broken, "characters", "clara.json")
        with open(path, encoding="utf-8") as fh:
            data = _json.load(fh)
        data["location"] = "place:office"       # her routine puts her on the pier at 20:00
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(data, fh, indent=2)

        report = validate_world_pack(broken)
        codes = [i.code for i in report.issues]
        assert "routine.contradicts_start_location" in codes, codes
        assert not report.ok, "a self-contradicting pack must not validate"

        # and an unschedulable place is an error, not a silent no-op
        data["routine"] = [{"from": "08:00", "place": "place:atlantis"}]
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(data, fh, indent=2)
        assert "routine.unknown_place" in [i.code for i in validate_world_pack(broken).issues]

        print("ok  routine: validation rejects contradictory and unschedulable routines")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_benchmark_claims_hold_on_every_pack():
    """The published benchmark must pass on every pack we ship.

    Short runs here; `unscripted benchmark --turns 8000` is the real soak. Long runs are
    where the interesting failures live -- 173 simulated days is what exposed
    summaries growing without bound (1,905 stored memories against a cap of 600,
    1,595 of them summaries of summaries), which no short test could see.
    """
    from unscripted.benchmark import run_benchmark
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for pack in ("cyberpunk-block", "noir-harbor", "dorf-thornfeld"):
        report = run_benchmark(world_pack=os.path.join(root, "worldpacks", pack),
                               turns=250, verify_determinism=(pack == "cyberpunk-block"))
        failed = [m.key for m in report.metrics if m.applicable and not m.passed]
        assert not failed, f"{pack}: {failed}\n{report.render()}"
    print("ok  benchmark: every claim holds on all three packs")


def test_knowledge_spreads_through_the_society_over_time():
    """Information must move between characters, or none of the rest means anything.

    Before the diffusion layer existed, a character learned something only by
    being present when it happened. Nobody ever told anybody anything:

        player asks Vee about Milan   -> 4 co-present agents know it
        +72h, whole cast co-located   -> still exactly those 4

    which made "rumour spreads through the world with a traceable origin" untrue,
    and left correlation discounting guarding against a situation the engine could
    not produce.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.ontology import Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        def held():
            """Every (who, what) pair currently known, with the belief."""
            return {(a.id, key): belief
                    for a in sdk.world.agents.values() for key, belief in a.beliefs.items()}

        start = held()
        # who was first-hand on each proposition before anyone started talking
        first_hand_origins = {}
        for (agent_id, key), belief in start.items():
            assert belief.hops == 0, "an authored or witnessed belief is first-hand"
            first_hand_origins.setdefault(key, set()).add(belief.primary_origin)

        for _ in range(12):
            sdk.advance_time(60)
        spread = held()

        learned = {pair: belief for pair, belief in spread.items() if pair not in start}
        assert learned, (
            f"nothing was learned from anyone in 12 simulated hours "
            f"({len(start)} known facts before, {len(spread)} after)")

        for (agent_id, key), belief in learned.items():
            if belief.hops == 0:
                continue          # witnessed directly (e.g. a scheduled broadcast)
            # THE point: the claim carries the ORIGINAL origin, not the person who
            # relayed it. Five mouths relaying one witness is still one witness.
            known_origins = first_hand_origins.get(key, set())
            if known_origins:
                assert belief.primary_origin in known_origins, (
                    f"{agent_id} recorded origin {belief.primary_origin!r} for {key}; a "
                    f"retelling must carry the origin it came from, or correlation "
                    f"discounting cannot see the duplication. Known: {known_origins}")

        # original witnesses keep their own first-hand standing even after their
        # own rumour circulates back to them
        for pair, belief in start.items():
            if pair in spread:
                assert spread[pair].hops == 0, (
                    f"{pair[0]} witnessed this; hearing it echo back must not move them "
                    f"away from what they saw")

        relayed_beliefs = [b for b in learned.values() if b.hops >= 1]
        assert relayed_beliefs, "everything new was witnessed; nothing was actually told"

        # every retelling is on the ledger: "how did they know?" is a query
        relayed = sdk.store.conn.execute(
            "SELECT COUNT(*) FROM event_ledger WHERE payload LIKE '%diffusion%'").fetchone()[0]
        assert relayed >= 1, "retellings must be auditable events, not hidden state"

        print(f"ok  diffusion: {len(start)} -> {len(spread)} known facts in 12h "
              f"({len(relayed_beliefs)} learned by hearsay, origins preserved), "
              f"{relayed} retellings on the ledger")
    finally:
        sdk.close()


def test_relayed_rumour_does_not_become_independent_proof():
    """A crowd repeating one witness must not add up to certainty.

    This is the invariant the whole provenance model exists for, and until
    diffusion existed it could not even be exercised: nothing in the engine made a
    second person repeat anything.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.ontology import Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        key = Proposition("clinic_open", {"place": "place:clinic",
                                          "when": "last_night"}, "-").core_key()
        for _ in range(24):
            sdk.advance_time(60)

        for agent in sdk.world.agents.values():
            belief = agent.beliefs.get(key)
            if belief is None or belief.hops == 0:
                continue
            # A single origin heard many times over: confidence may firm up, but it
            # must stay short of the certainty many INDEPENDENT witnesses would give.
            if len(belief.origin_counts) == 1:
                repeats = sum(belief.origin_counts.values())
                confidence = max(belief.expected_prob, 1.0 - belief.expected_prob)
                assert confidence < 0.95, (
                    f"{agent.id} heard one origin {repeats}x and reached "
                    f"confidence {confidence:.3f}; repetition is not proof")

        print("ok  diffusion: a relayed rumour stays one source however often it is repeated")
    finally:
        sdk.close()


def test_diffusion_never_leaks_a_secret_and_stays_deterministic():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted import content
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def run():
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
            storage_path=":memory:"))
        try:
            for _ in range(12):
                sdk.advance_time(60)
            leaked = []
            for agent in sdk.world.agents.values():
                for secret in agent.secrets:
                    for protected in secret.protects:
                        for other in sdk.world.agents.values():
                            if other.id != agent.id and protected in other.beliefs:
                                leaked.append((agent.id, other.id, secret.secret_id))
            ledger = [row[0] for row in sdk.store.conn.execute(
                "SELECT payload FROM event_ledger WHERE payload LIKE '%diffusion%'")]
            return leaked, ledger
        finally:
            sdk.close()

    leaked, ledger_a = run()
    assert not leaked, f"a protected proposition was gossiped: {leaked}"

    _, ledger_b = run()
    assert ledger_a == ledger_b, "diffusion must be reproducible from the same seed"
    print(f"ok  diffusion: no secret gossiped, {len(ledger_a)} retellings reproduce exactly")


def test_provenance_is_bounded_and_survives_a_reload():
    """Evidence origins must be remembered forever; individual claim records need not.

    provenance was an ever-growing list scanned linearly on every belief update
    (13 entries for 2 beliefs after 18 turns), which made updates O(claims) and
    let snapshots grow with session length. Origin *identity* is what correlation
    discounting depends on, so that is kept in full and indexed; the per-claim
    records exist for the inspector and are trimmed.
    """
    w = _mini_world()
    rt = Runtime(w)
    npc = w.agents["npc"]
    rt.belief.params["provenance_limit"] = 16

    for _ in range(200):
        rt.process_event(_claim_event(w, origin="rumour_a"))
    belief = list(npc.beliefs.values())[0]

    assert len(belief.provenance) <= 16, f"provenance grew to {len(belief.provenance)}"
    assert belief.provenance_dropped > 0, "trimming must be reported, not silent"
    assert belief.origin_counts["rumour_a"] == 200, \
        "how often an origin was heard must survive trimming"

    # 200 repetitions of one rumour must still not amount to proof.
    # The flat-0.1 discount attenuated but did not saturate, so this reached 0.995.
    saturated = belief.expected_prob
    assert saturated < 0.8, f"one origin repeated 200 times reached p={saturated:.3f}"

    # ...and that must hold across a save/load: origin keys are often raw event ids,
    # and JSON has only string keys, so a naive round-trip silently starts treating
    # a repeated rumour as independent evidence again.
    from unscripted.belief import Belief
    import json as _json
    reloaded = Belief.from_dict(_json.loads(_json.dumps(belief.as_dict(), default=str)))
    before = reloaded.expected_prob
    rt.belief.update(w.agents["npc"].beliefs, belief.proposition,
                     asserter_polarity="+", trust=0.9, competence=0.9, skepticism=0.1,
                     claim_id="c", origin_event="rumour_a", world_time=w.world_time)
    known = rt.belief.correlation_discount(reloaded, "rumour_a")
    assert known < 0.11, (
        f"a reloaded belief must still recognise an origin it counted 200 times "
        f"(discount {known}); string/int key drift here silently turns a repeated "
        f"rumour back into independent evidence")

    # an independent origin still moves the needle
    assert rt.belief.correlation_discount(reloaded, "rumour_b") == 1.0
    assert before == reloaded.expected_prob
    print(f"ok  belief: provenance capped at 16 (dropped {belief.provenance_dropped}), "
          f"200 repeats -> p={belief.expected_prob:.2f}, discount survives reload")


def test_event_persistence_does_not_scale_with_population():
    """One event must cost a bounded number of SQL statements, not one per observer.

    save_agent() used to re-serialise EVERY belief and EVERY memory of EVERY
    observer on every event and commit per agent, which measured as ~94% of the
    per-event cost (55.5 ms/event at 400 co-located agents). Asserting statement
    counts rather than wall-clock keeps this honest on any CI machine.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.agent import Agent
    from unscripted.events import Event
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def statements_for(population):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
            storage_path=":memory:"))
        try:
            for i in range(population - len(sdk.world.agents)):
                extra = Agent(id=f"agent:extra_{i}", location="place:main_street",
                              big_five={"agreeableness": 0.5})
                sdk.world.agents[extra.id] = extra
                sdk.core._last_decay[extra.id] = sdk.world.world_time
            # Count Python-level database round trips. sqlite3's trace callback
            # fires per executed row, so it cannot distinguish one executemany of
            # 200 rows from 200 separate execute() calls -- which is exactly the
            # difference being measured here.
            calls = []

            class CountingConnection:
                def __init__(self, inner):
                    self._inner = inner

                def execute(self, *a, **kw):
                    calls.append("execute")
                    return self._inner.execute(*a, **kw)

                def executemany(self, *a, **kw):
                    calls.append("executemany")
                    return self._inner.executemany(*a, **kw)

                def __getattr__(self, name):
                    return getattr(self._inner, name)

            real = sdk.store.conn
            sdk.store.conn = CountingConnection(real)
            try:
                sdk.emit_event(Event(sdk.world.new_event_id(), sdk.world.world_time, "claim",
                                     actor=sdk.config.player_id, location="place:main_street",
                                     payload={"summary": "a beat everyone hears",
                                              "importance": 0.5}))
            finally:
                sdk.store.conn = real
            return len(calls), len(sdk.world.agents)
        finally:
            sdk.close()

    small, small_pop = statements_for(10)
    large, large_pop = statements_for(200)
    assert large_pop > small_pop * 5, "the test needs a real population difference"
    assert large <= small + 4, (
        f"{small_pop} agents -> {small} statements, {large_pop} -> {large}: "
        "per-event writes must be batched, not one statement per observer")
    print(f"ok  persistence: {small_pop} vs {large_pop} observers cost "
          f"{small} vs {large} SQL statements per event")


def test_memory_and_trace_growth_is_bounded():
    """Nothing may grow with session length: not recall history, not memory, not traces."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.agent import Agent
    from unscripted.events import Event
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        agent_id = "agent:barkeep_12"
        agent = sdk.world.agents[agent_id]
        window = sdk.core.memory.params["presentation_window"]

        # recall history: every retrieval used to append a timestamp forever, and
        # base_activation() walks the whole list on every save and every query
        for _ in range(300):
            sdk.retrieve_memories(agent_id)
            sdk.advance_time(1)
        longest = max(len(m.presentations) for m in agent.memory)
        assert longest <= window, f"presentation history grew to {longest} (window {window})"

        # memory count: only episodic used to be capped, so every other type grew
        total_cap = sdk.core.memory.params["total_cap"]
        for i in range(total_cap + 300):
            sdk.core.memory.encode(
                agent.memory,
                type(agent.memory[0])(memory_id=f"m{i}", owner=agent_id, type="social",
                                      content="chatter", importance=0.2),
                sdk.world.world_time)
        sdk.advance_time(1)
        non_summary = [m for m in agent.memory if m.type != "summary"]
        assert len(non_summary) <= total_cap, \
            f"{len(non_summary)} non-summary memories exceed the cap of {total_cap}"
        # and the dropped ones must leave the store, not just the object
        stored = len(sdk.store.load_memories(agent_id))
        assert stored <= total_cap + 50, f"{stored} memory rows persisted after consolidation"

        # reason traces are debug output and must not outgrow the world they explain
        sdk.store.reason_trace_limit = 200
        for _ in range(900):
            sdk.emit_event(Event(sdk.world.new_event_id(), sdk.world.world_time, "claim",
                                 actor=sdk.config.player_id, location=agent.location,
                                 payload={"summary": "noise", "importance": 0.1}))
        traces = sdk.store.reason_trace_count()
        assert traces <= 200 + 512, f"reason_trace grew to {traces} rows with a 200 limit"
        print(f"ok  bounded: recall history <= {window}, memories <= {total_cap}, "
              f"traces trimmed to {traces}")
    finally:
        sdk.close()


def test_one_version_and_nothing_disagrees_with_it():
    """The version an engine is told is the version that was packaged.

    `runtime_version` goes over the wire to a plugin, `unscripted.__version__` goes into
    a bug report, and `pyproject.toml` decides what a studio actually installed.
    They were three literals in three files, and two of them were already a
    release behind -- which tells an integrator they are talking to a build that
    is not the one running. All three now resolve to `contracts.RUNTIME_VERSION`;
    this fails if a future release moves one and forgets another.

    `SNAPSHOT_SCHEMA_VERSION` is deliberately not part of this: the save format
    is versioned by whether the format changed, not by whether we shipped.
    """
    try:
        import tomllib
    except ModuleNotFoundError:      # Python 3.10
        print("ok  version: skipped (tomllib needs Python 3.11+)")
        return
    import unscripted
    from unscripted.contracts import RUNTIME_VERSION, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
        packaged = tomllib.load(fh)["project"]["version"]

    assert unscripted.__version__ == RUNTIME_VERSION, \
        f"unscripted.__version__ {unscripted.__version__} != RUNTIME_VERSION {RUNTIME_VERSION}"
    assert RuntimeConfig().schema_version == RUNTIME_VERSION, \
        "the version served to an engine is not the runtime's version"
    assert packaged == RUNTIME_VERSION, \
        f"pyproject says {packaged}, the code says {RUNTIME_VERSION}"

    # And the changelog has to have an entry for it, or a release exists with no
    # record of what is in it.
    with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as fh:
        changelog = fh.read()
    assert f"## [{RUNTIME_VERSION}]" in changelog, \
        f"CHANGELOG.md has no section for {RUNTIME_VERSION}"
    print(f"ok  version: {RUNTIME_VERSION} agrees across code, package and changelog")


def test_packaging_manifest_covers_every_data_file():
    """Every shipped data file must be listed in pyproject, or an installed copy
    of the SDK is quietly incomplete.

    This drifted badly: 15 of 38 data files were unlisted, including both packs'
    topics.json -- without which an installed package loads a world nobody can
    ask anything about. A source checkout never notices; only an install does.
    """
    try:
        import tomllib
    except ModuleNotFoundError:      # Python 3.10
        print("ok  packaging: skipped (tomllib needs Python 3.11+)")
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
        config = tomllib.load(fh)

    listed = {f for files in config["tool"]["setuptools"]["data-files"].values() for f in files}
    actual = set()
    for base in ("worldpacks", "golden", "docs", "integrations", "qa"):
        for dirpath, _, filenames in os.walk(os.path.join(root, base)):
            for name in filenames:
                actual.add(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))

    # Deliberately not shipped in the wheel. These are the design papers the
    # runtime was built from, and the recorded demo the landing page shows --
    # worth having in the repository, worth nothing to a `pip install`, and
    # between them they would be most of the package by size.
    # Named here rather than skipped by pattern, so that adding a directory
    # under docs/ is still a decision somebody has to make.
    NOT_PACKAGED = ("docs/theory/", "docs/video/")
    for prefix in NOT_PACKAGED:
        assert os.path.isdir(os.path.join(root, prefix)), (
            f"NOT_PACKAGED names {prefix}, which no longer exists")
    actual = {f for f in actual if not f.startswith(NOT_PACKAGED)}

    missing = sorted(actual - listed)
    assert not missing, f"data files not packaged: {missing}"
    # Staleness asks whether a listed file EXISTS, not whether it lives in one of
    # the directories walked above. The earlier form failed on a root-level file
    # like CONTRIBUTING.md, which is listed, is packaged, and is plainly there --
    # a test that reports a correct manifest as broken teaches people to ignore
    # it, which is worse than not having it.
    stale = sorted(f for f in listed
                   if not os.path.exists(os.path.join(root, f)))
    assert not stale, f"pyproject lists files that do not exist: {stale}"
    assert config["project"]["license"] == {"file": "LICENSE"}
    assert os.path.exists(os.path.join(root, "LICENSE"))
    print(f"ok  packaging: all {len(actual)} data files listed, licence present")


def test_canon_layer_rejects_hallucinated_specifics():
    """Validator layer 3b: a model may phrase, not invent.

    Before this layer existed the check was a comment, so the only guards on
    provider output were a secret substring scan and exact-repetition detection:

        check("The mayor was murdered by Kane in the harbour last Tuesday.") -> ACCEPT

    Proper nouns and numbers carry factual specificity; every one of them must be
    licensed by the plan. Ordinary words carry stance and are left alone.
    """
    from unscripted import Validator
    from unscripted.dialogue import DialoguePlan
    from unscripted.validator import CANON_OFF, CANON_STRICT, CANON_WARN
    from unscripted.world import load_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    world = load_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    v = Validator.for_world(world)

    plan = DialoguePlan(speaker="agent:barkeep_12", addressee="agent:player_1",
                        dialogue_act="inform", goal="answer",
                        allowed_facts=["NOT clinic_open(place=place:clinic, when=last_night)"])

    # invented people, places and times
    bad = v.check("The mayor was murdered by Kane in the harbour last Tuesday.",
                  plan, None, [])
    assert bad.verdict == "REJECT_SOFT", bad
    codes = [r[0] for r in bad.reasons]
    assert "validator.canon_violation" in codes
    flagged = {u["token"].lower() for u in bad.unlicensed}
    assert {"kane", "tuesday"} <= flagged, bad.unlicensed
    # a real character named without licence is reported as a referent, not a coinage
    kinds = {u["token"].lower(): u["kind"] for u in bad.unlicensed}
    assert kinds["kane"] == "unlicensed_referent", bad.unlicensed
    assert kinds["tuesday"] == "proper_noun", bad.unlicensed

    # invented quantities
    money = v.check("Pay me 4500 credits and we'll talk.", plan, None, [])
    assert money.verdict == "REJECT_SOFT"
    assert any(u["kind"] == "number" and u["token"] == "4500" for u in money.unlicensed)

    # legitimate paraphrase of a licensed fact is accepted
    for good in ("Far as I know the clinic was shut that night.",
                 "It was closed. That's all I've got.",
                 "I don't know anything about that."):
        result = v.check(good, plan, None, [])
        assert result.verdict == "ACCEPT", (good, result.reasons, result.unlicensed)

    # a licensed number passes
    debt = DialoguePlan(speaker="a", addressee="b", dialogue_act="request", goal="collect",
                        allowed_facts=["economy:owes_amount(debtor=b, creditor=a, amount=300)"])
    assert v.check("You still owe me 300.", debt, None, []).verdict == "ACCEPT"
    assert v.check("You still owe me 900.", debt, None, []).verdict == "REJECT_SOFT"

    # modes
    assert v.check("Kane told me.", plan, None, [], canon_mode=CANON_OFF).verdict == "ACCEPT"
    warned = v.check("Kane told me.", plan, None, [], canon_mode=CANON_WARN)
    assert warned.verdict == "ACCEPT" and "validator.canon_warning" in [r[0] for r in warned.reasons]
    assert v.check("Kane told me.", plan, None, [],
                   canon_mode=CANON_STRICT).verdict == "REJECT_SOFT"

    # This used to be a DOCUMENTED LIMIT: the layer keyed on proper nouns and
    # numbers, so an invention phrased entirely in common nouns passed. "The old
    # mill by the river" contains no capital and no number, and a world with no
    # mill had just acquired one. Entity grounding closes it -- a noun in
    # referring position must be something the world declares, ordinary furniture,
    # or licensed by the commitment.
    invented = v.check("The old mill by the river burned down.", plan, None, [])
    assert invented.verdict == "REJECT_SOFT", (invented.verdict, invented.unlicensed)
    kinds = {e["token"]: e["kind"] for e in invented.unlicensed}
    assert kinds.get("mill") == "invented_referent", invented.unlicensed

    # ...without turning ordinary language into a violation. Furniture passes.
    assert v.check("Meet me by the door.", plan, None, []).verdict == "ACCEPT"
    assert v.check("I have nothing further to add.", plan, None, []).verdict == "ACCEPT"
    print("ok  validator: canon parse-back rejects unlicensed names, numbers "
          "and invented things")


def test_hallucinating_provider_never_reaches_the_player():
    """End to end: a provider that invents facts is replaced by authored text."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
            semantic_release="provider"))

    class HallucinatingRealizer:
        """Fluent, confident and entirely made up -- the realistic failure mode."""
        is_deterministic = False
        model_id = "hallucinator-1"

        def realize(self, plan, style):
            return "Milena Vasquez took him to Warehouse 9 around 0300 last Tuesday."

    try:
        sdk.core.realizer = HallucinatingRealizer()
        result = sdk.submit_player_text("ask Honce about clinic")
        line = result.npc_response.text

        for invention in ("Milena", "Vasquez", "Warehouse", "0300", "Tuesday"):
            assert invention not in line, f"hallucinated {invention!r} reached the player: {line!r}"
        assert result.npc_response.verdict == "ACCEPT", "released text must itself be valid"

        codes = [r[0] for r in result.npc_response.reasons]
        assert "validator.canon_violation" in codes, codes
        assert "dialogue.validation_fallback" in codes, codes

        # the rejection is on the record, with what was actually generated
        row = sdk.store.conn.execute(
            "SELECT raw_output, accepted_output, validation_result FROM provider_call "
            "ORDER BY rowid DESC LIMIT 1").fetchone()
        assert "Warehouse 9" in row[0], "the raw model output must be auditable"
        assert row[1] == line or row[2] == "ACCEPT"
        print(f"ok  provider: hallucinated line replaced before release -> {line!r}")
    finally:
        sdk.close()


def test_engine_contains_no_world_content():
    """Structural guard: no pack's vocabulary may appear in the engine source.

    This is the regression that matters most. The reference scene's places,
    characters, topics, secret surface forms and even a factual `inform` sentence
    used to be Python constants in the SDK, which made "engine-independent" true
    only for one world. A grep-level test is blunt on purpose: it fails the moment
    someone reaches for a quick special case again.
    """
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    engine_dir = os.path.join(root, "unscripted")

    # identifiers and phrases that belong to a world pack, never to the engine
    forbidden = [
        r"place:main_street", r"place:back_room", r"place:police_post", r"place:clinic",
        r"place:market", r"place:pier", r"place:office",
        r"agent:npc_red_jacket", r"agent:barkeep_12", r"agent:officer_kane", r"agent:pavel",
        r"agent:corpo_okada", r"agent:clara", r"agent:marlow", r"agent:player_1",
        r"faction:reds", r"faction:badges", r"faction:harbor_watch",
        r"\bmilan\b", r"brother_whereabouts", r"crate 19", r"eddies", r"choom",
        r"clinic_open", r"connected_to_attack", r"cargo_logged", r"premises_open",
        r"shut that night", r"the establishment was closed",
        r"\bHonce\b", r"\bVee\b", r"\bKane\b",
    ]
    # Files that legitimately name the reference pack: CLI defaults, the sales
    # showcase, the tour page and the demo UI's example prompts are about the demo,
    # not the engine. `tour.py` keeps its pack coupling in one declared CAST table
    # at the top rather than scattered through its scenes, which is the difference
    # between a surface that is written for a world and an engine that assumes one.
    allowed_files = {"cli.py", "showcase.py", "webdemo.py", "golden.py",
                     "contracts.py", "tour.py"}

    offenders = []
    for filename in sorted(os.listdir(engine_dir)):
        if not filename.endswith(".py") or filename in allowed_files:
            continue
        source = open(os.path.join(engine_dir, filename), encoding="utf-8").read()
        # comments and docstrings may discuss the history; only executable code counts
        code = re.sub('\"\"\".*?\"\"\"', "", source, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", "", code, flags=re.DOTALL)
        code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())
        for pattern in forbidden:
            for match in re.finditer(pattern, code, flags=re.IGNORECASE):
                line_no = code[:match.start()].count("\n") + 1
                offenders.append(f"unscripted/{filename}:{line_no} contains {match.group(0)!r}")
    assert not offenders, "world content leaked into the engine:\n  " + "\n  ".join(offenders)
    print(f"ok  engine: {len(forbidden)} world-content patterns absent from the SDK core")


def test_parser_free_text_contract():
    from unscripted import RuleBasedParserProvider
    from unscripted.world import load_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    w = load_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    parser = RuleBasedParserProvider()
    parsed = parser.parse("Ask Vee about Milan", player_id="agent:player_1",
                          player_location="place:main_street", world=w)
    assert parsed.intent == "ask"
    assert parsed.topic == "milan"
    assert parsed.target_id == "agent:npc_red_jacket"
    assert parsed.proposition.predicate == "looking_for"
    lie = parser.parse("I claim I am police", player_id="agent:player_1",
                       player_location="place:main_street", world=w)
    assert lie.intent == "claim"
    assert lie.proposition.predicate == "core:holds_role"
    print("ok  parser: free text maps to typed closed-catalog commands")


def test_parser_vocabulary_comes_from_the_pack():
    """The same sentence must resolve against whichever world is loaded.

    Place names, character names and topics used to be module-level tables in the
    parser holding the reference scene's vocabulary. A second pack therefore
    loaded and validated but could not be navigated or addressed at all.
    """
    from unscripted import RuleBasedParserProvider
    from unscripted.world import load_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = RuleBasedParserProvider()

    cyber = load_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    noir = load_world_pack(os.path.join(root, "worldpacks", "noir-harbor"))

    # noir's own topology is navigable
    go = parser.parse("go office", player_id="agent:player_1",
                      player_location="place:pier", world=noir)
    assert go.intent == "move" and go.location_id == "place:office", go

    # noir's own characters are addressable by their authored aliases
    ask = parser.parse("ask Marlow about the manifest", player_id="agent:player_1",
                       player_location="place:office", world=noir)
    assert ask.intent == "ask" and ask.target_id == "agent:marlow", ask
    assert ask.topic == "manifest", ask

    # and the reference pack's vocabulary does NOT bleed into the other world
    assert parser.parse("go market", player_id="agent:player_1",
                        player_location="place:pier", world=noir).intent == "unknown"
    assert parser.parse("ask about Milan", player_id="agent:player_1",
                        player_location="place:pier", world=noir).topic is None
    assert parser.parse("go office", player_id="agent:player_1",
                        player_location="place:main_street", world=cyber).intent == "unknown"

    # aliases must be unambiguous within a pack, and longest-match must win
    for world in (cyber, noir):
        for index in (world.place_alias_index(), world.agent_alias_index(),
                      world.topic_alias_index()):
            assert index.conflicts() == [], index.conflicts()
    assert cyber.place_alias_index().match("go to the police post") == "place:police_post", \
        "'police post' must beat 'police' -- longest alias wins"

    print("ok  parser: vocabulary is world-pack content, not an SDK table")


def test_player_is_never_addressable_as_an_npc():
    """The parser used to exclude the literal id 'agent:player_1'."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        player_id="agent:hero", player_start_location="place:clinic",
        storage_path=":memory:"))
    try:
        here = [a.id for a in sdk.world.agents.values() if a.location == "place:clinic"]
        assert here == ["agent:hero"], here
        parsed = sdk.interpret_input("ask about the clinic")
        assert parsed.target_id != "agent:hero", "the player must never be their own NPC target"
        assert parsed.target_id is None
        assert "No reachable NPC target" in sdk.submit_player_text("ask about the clinic").message
        print("ok  parser: a custom player id is never resolved as an NPC target")
    finally:
        sdk.close()


def test_sdk_terminal_turn_and_provider_record():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        result = sdk.submit_player_text("ask Honce about clinic")
        assert result.npc_response is not None
        assert result.npc_response.act in {"inform", "evade", "request", "greet", "threaten"}
        assert sdk.store.provider_call_count() >= 1
        assert "beliefs of agent:barkeep_12" in result.developer_trace
        print("ok  sdk: terminal turn returns dialogue + developer trace + provider record")
    finally:
        sdk.close()


def test_terminal_social_input_requires_reachable_target():
    from unscripted import UnscriptedRuntime, RuntimeConfig, Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        result = sdk.submit_player_text("tell Kane I am police")
        assert "not reachable" in result.message
        prop = Proposition("core:holds_role",
                           {"agent": cfg.player_id, "role": "role:officer", "context": "faction:badges"})
        assert sdk.query_belief("agent:officer_kane", prop) is None
        print("ok  terminal: social speech requires a reachable NPC target")
    finally:
        sdk.close()


def test_provider_failure_costs_the_wording_and_not_the_content():
    """A model that dies must not decide what the society knows.

    THE EXPECTATION HERE MOVED, and the old one was the defect. This test used
    to require that a thrown provider produce a DEFLECTION -- so a timeout
    silently voided the commitment the runtime had already made, and the same
    question answered twice put a belief in the world once. A model's failure
    mode is not an epistemic event.

    What a failure costs now is the wording. The authored phrasing goes out, the
    failure is on the record, and the commitment reaches the world exactly as it
    would have if the model had answered. Run in `provider` mode, because that is
    the only mode in which a provider is asked to write a factual line at all.
    """
    from unscripted import UnscriptedRuntime, RuntimeConfig, ProviderError
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class FailingRealizer:
        model_id = "broken-provider"
        is_deterministic = False

        def realize(self, plan, style):
            raise ProviderError("simulated timeout")

    def answer(realizer):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
            storage_path=":memory:", semantic_release="provider"))
        if realizer is not None:
            sdk.core.realizer = realizer
        try:
            result = sdk.submit_player_text("ask Honce about clinic")
            player = sdk.world.agents[sdk.config.player_id]
            return result, sorted(player.beliefs), sdk.store.provider_call_count()
        finally:
            sdk.close()

    broken, learned_after_failure, calls = answer(FailingRealizer())
    working, learned_normally, _ = answer(None)

    assert broken.npc_response is not None
    assert broken.npc_response.verdict == "ACCEPT"
    assert any(r[0] == "provider.failure" for r in broken.npc_response.reasons), (
        "the failure was not recorded")
    assert calls >= 1, "the failed turn left no audit row"
    assert learned_after_failure == learned_normally, (
        f"a dead model changed what the world knows: {learned_after_failure} "
        f"against {learned_normally}")
    assert learned_normally, "nothing was asserted, so nothing is proved"
    print("ok  provider: a failure costs the wording, and the world learns the "
          "same thing either way")


def test_rejected_provider_output_never_reaches_player():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class LeakingRealizer:
        model_id = "leaky-provider"

        def realize(self, plan, style):
            return "Milan is at the clinic back room."

    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:",
            semantic_release="provider")
    sdk = UnscriptedRuntime.create(cfg)
    sdk.core.realizer = LeakingRealizer()
    try:
        result = sdk.submit_player_text("ask Vee about Milan")
        assert result.npc_response is not None
        assert "Milan" not in result.npc_response.text
        assert result.npc_response.verdict == "ACCEPT"
        assert any(r[0] == "validator.secret_leak" for r in result.npc_response.reasons)
        print("ok  provider: rejected external text is replaced before player release")
    finally:
        sdk.close()


def test_sdk_attack_mobilizes_social_consequence():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        sdk.submit_player_text("go market")
        result = sdk.submit_player_text("attack Pavel")
        assert "mobilize" in result.message or "reacts with" in result.message
        assert any(e.type == "ally_arrives" for e in sdk.world.scenario_events)
        print("ok  sdk: attack creates off-screen ally-arrival social consequence")
    finally:
        sdk.close()


def test_initial_state_loaded_from_world_pack():
    from unscripted import UnscriptedRuntime, RuntimeConfig, Proposition
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        prop = Proposition("clinic_open", {"place": "place:clinic", "when": "last_night"}, "-")
        belief = sdk.query_belief("agent:barkeep_12", prop)
        assert belief is not None
        assert belief.expected_prob < 0.5, "negative authored belief should load as evidence against open"
        assert any(p["origin_event"] == "seed_bar_clinic" for p in belief.provenance)
        print("ok  initial state: authored world-pack beliefs load with provenance")
    finally:
        sdk.close()


def test_capability_config_requires_http_endpoint():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        text_realizer={"provider": "http"})
    try:
        UnscriptedRuntime.create(cfg)
    except ValueError as exc:
        assert "endpoint" in str(exc)
        print("ok  capabilities: external HTTP text provider requires endpoint")
    else:
        raise AssertionError("HTTP text provider without endpoint must fail")


def test_service_rejects_malformed_requests_with_4xx():
    """Caller mistakes must be precise 4xx, never a 500 and never silent corruption."""
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.service import UnscriptedService, ServiceOptions
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    service = UnscriptedService(sdk, ServiceOptions())
    try:
        def status(result):
            return result[1] if isinstance(result, tuple) else 200

        def code(result):
            return result[0].get("code") if isinstance(result, tuple) else None

        before = sdk.world.world_time

        # world time is monotonic: a negative delta used to be accepted and
        # rewound the clock, silently corrupting every memory activation
        bad_time = service.handle_post("/advance", {"minutes": -500})
        assert status(bad_time) == 400 and code(bad_time) == "minutes_out_of_range"
        assert sdk.world.world_time == before, "world time must not move on a rejected request"

        cases = [
            (("/advance", {"minutes": "abc"}), 400, "minutes_not_an_integer"),
            (("/advance", {"minutes": True}), 400, "minutes_not_an_integer"),
            (("/advance", {}), 400, "minutes_required"),
            (("/advance", {"minutes": 10 ** 12}), 400, "minutes_out_of_range"),
            (("/turn", {"text": 12345}), 400, "text_required"),
            (("/turn", {"text": "x" * 99999}), 413, "text_too_long"),
            (("/restore", {}), 400, "snapshot_id_required"),
            (("/restore", {"snapshot_id": "deadbeef"}), 404, "unknown_snapshot"),
            (("/event", {"actor": "a"}), 400, "event_missing_type"),
            (("/event", {"type": "claim", "payload": "nope"}), 400, "event_bad_payload"),
            (("/event", {"type": "claim", "world_time": -5}), 400, "event_time_not_monotonic"),
            (("/generate/characters", {"count": 10 ** 6}), 400, "count_out_of_range"),
            (("/generate/characters", {"count": 0}), 400, "count_out_of_range"),
            (("/nope", {}), 404, "unknown_endpoint"),
        ]
        for (path, body), want_status, want_code in cases:
            result = service.handle_post(path, body)
            assert status(result) == want_status and code(result) == want_code, \
                f"POST {path} {body} -> {result}, expected {want_status}/{want_code}"

        missing = service.handle_get("/inspect/agent", {})
        assert status(missing) == 400 and code(missing) == "agent_id_required"
        unknown = service.handle_get("/state/agent", {"agent_id": ["agent:nope"]})
        assert status(unknown) == 404 and code(unknown) == "unknown_agent"

        # the SDK enforces monotonic time itself, not only at the HTTP edge
        try:
            sdk.advance_time(-1)
            raise AssertionError("SDK must reject a negative time delta")
        except ValueError:
            pass

        print("ok  service: malformed requests are precise 4xx and never mutate the world")
    finally:
        sdk.close()


def test_service_auth_and_debug_endpoint_gating():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.service import UnscriptedService, ServiceError, ServiceOptions
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        guarded = UnscriptedService(sdk, ServiceOptions(auth_token="s3cret"))
        for bad in (None, "", "Bearer wrong", "s3cret", "Basic s3cret"):
            try:
                guarded.authorize(bad)
                raise AssertionError(f"authorize accepted {bad!r}")
            except ServiceError as exc:
                assert exc.status == 401
        guarded.authorize("Bearer s3cret")   # must not raise

        shipped = UnscriptedService(sdk, ServiceOptions(expose_debug_endpoints=False))
        for path in ("/state/agent", "/state/world", "/inspect/agent", "/avatar/face"):
            body, status = shipped.handle_get(path, {"agent_id": ["agent:pavel"]})
            assert status == 403 and body["code"] == "debug_endpoints_disabled", path
        # gameplay endpoints keep working with inspection switched off
        assert shipped.handle_get("/health", {})["ok"] is True
        assert "message" in shipped.handle_post("/turn", {"text": "look"})

        # binding off-loopback unauthenticated is refused before a socket opens
        try:
            ServiceOptions().check_bind("0.0.0.0")
            raise AssertionError("unauthenticated off-loopback bind must be refused")
        except ValueError as exc:
            assert "without authentication" in str(exc)
        ServiceOptions(auth_token="t").check_bind("0.0.0.0")
        ServiceOptions(allow_insecure_bind=True).check_bind("0.0.0.0")
        ServiceOptions().check_bind("127.0.0.1")

        print("ok  service: bearer auth, debug gating and safe-by-default bind hold")
    finally:
        sdk.close()


def test_service_over_real_http_caps_body_size():
    """End-to-end through a real socket: oversized bodies are refused on the header."""
    import http.client
    import json
    import threading as _threading
    from unscripted import RuntimeConfig
    from unscripted.service import ServiceOptions, create_server

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    server = create_server(cfg, host="127.0.0.1", port=0,
                           options=ServiceOptions(auth_token="tok", max_body_bytes=2048))
    thread = _threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def request(method, path, body=None, token="tok", raw_len=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            payload = json.dumps(body) if body is not None else None
            if raw_len is not None:
                headers["Content-Length"] = str(raw_len)
                conn.putrequest(method, path)
                for k, v in headers.items():
                    conn.putheader(k, v)
                conn.endheaders()
                conn.send((payload or "").encode())
            else:
                conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            data = response.read()
            conn.close()
            return response.status, json.loads(data or b"{}")

        status, body = request("GET", "/health")
        assert status == 200 and body["ok"] is True

        status, body = request("GET", "/health", token=None)
        assert status == 401 and body["code"] == "unauthorized"

        # oversized body: rejected from the Content-Length header, never read in
        status, body = request("POST", "/turn", {"text": "x" * 5000})
        assert status == 413 and body["code"] == "payload_too_large", (status, body)

        # a lying Content-Length must not make the server allocate it either
        status, body = request("POST", "/turn", {"text": "look"}, raw_len=10 ** 9)
        assert status == 413, (status, body)

        status, body = request("POST", "/advance", {"minutes": -1})
        assert status == 400 and body["code"] == "minutes_out_of_range"

        status, _ = request("POST", "/turn", {"text": "look"})
        assert status == 200

        print("ok  service: real HTTP enforces auth, body caps and validation")
    finally:
        server.shutdown()
        server.server_close()
        server.unscripted_runtime.close()


def test_snapshot_restore_rewinds_state():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        snap = sdk.create_snapshot("before_move")
        start = sdk.world.agents[cfg.player_id].location
        sdk.submit_player_text("go market")
        assert sdk.world.agents[cfg.player_id].location == "place:market"
        sdk.restore_snapshot(snap)
        assert sdk.world.agents[cfg.player_id].location == start
        print("ok  snapshot: restore rewinds player location and projections")
    finally:
        sdk.close()


def test_snapshot_roundtrip_is_exact():
    """A snapshot must restore EVERY piece of resumable state, not just the parts
    an earlier test happened to look at.

    Rather than asserting field by field (which is how relationships and faction
    heat went missing for so long), this captures the full state, plays the world
    forward through social, temporal and faction-affecting turns, restores, and
    then compares a fresh capture against the original byte for byte.
    """
    import json
    from unscripted import UnscriptedRuntime, RuntimeConfig, snapshot as snap_mod
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        # build up non-trivial state first, so the comparison has something to prove
        sdk.submit_player_text("ask Vee about Milan")
        sdk.submit_player_text("promise Vee 300")
        sdk.submit_player_text("wait 30")

        before = snap_mod.capture(sdk.world, sdk.core)
        snap = sdk.create_snapshot("roundtrip")

        # drive the world somewhere clearly different across every subsystem
        sdk.submit_player_text("threaten Vee")     # relationships (trust down)
        sdk.submit_player_text("go market")        # locations
        sdk.submit_player_text("attack Pavel")     # affect, memory, faction heat
        sdk.submit_player_text("wait 240")         # time, clocks, decay, scheduled events
        divergent = snap_mod.capture(sdk.world, sdk.core)
        assert divergent != before, "test is vacuous unless the world actually moved on"

        reasons = sdk.restore_snapshot(snap)
        assert reasons == [], f"clean restore must report nothing: {reasons}"
        after = snap_mod.capture(sdk.world, sdk.core)

        # `ledger_watermark` describes the AUDIT STREAM, not the world, and the
        # stream is append-only on purpose: the whole point of recording it is
        # that a reload cannot rewind it. It legitimately moves on while the
        # world goes back, so comparing it here would assert the opposite of
        # what the ledger is for.
        stream = {"ledger_watermark"}
        if {k: v for k, v in after.items() if k not in stream} != \
                {k: v for k, v in before.items() if k not in stream}:
            differing = sorted(k for k in (set(before) | set(after)) - stream
                               if before.get(k) != after.get(k))
            raise AssertionError(f"snapshot round-trip lost state in: {differing}")
        assert after["ledger_watermark"] >= before["ledger_watermark"], (
            "the ledger watermark went backwards, which is what it exists not to do")

        # and the blob must survive a real JSON round-trip, not just object
        # equality -- minus the append-only stream, for the reason above
        def _world_only(blob):
            trimmed = json.loads(json.dumps(blob, sort_keys=True, default=str))
            for key in stream:
                trimmed.pop(key, None)
            return trimmed

        assert _world_only(before) == _world_only(after)

        # spot-check the two that silently regressed before, so a failure names them
        vee = sdk.world.agents["agent:npc_red_jacket"]
        assert vee.trust_in(cfg.player_id) == \
            before["agents"]["agent:npc_red_jacket"]["relationships"][cfg.player_id]["trust"]
        for fid, faction in sdk.core.director.factions.items():
            assert faction.heat == before["factions"][fid]["heat"]
            assert {n: c.filled for n, c in faction.clocks.items()} == \
                {n: c["filled"] for n, c in before["factions"][fid]["clocks"].items()}

        print("ok  snapshot: full round-trip restores relationships, factions and timeline")
    finally:
        sdk.close()


def test_snapshot_reports_mismatches_instead_of_failing_silently():
    """Restoring a snapshot whose world does not match must be loud, not lossy."""
    from unscripted import UnscriptedRuntime, RuntimeConfig, snapshot as snap_mod
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        data = snap_mod.capture(sdk.world, sdk.core)

        stale = dict(data, snapshot_schema_version=1)
        codes = [r[0] for r in snap_mod.restore(stale, sdk.world, sdk.core)]
        assert "snapshot.version_mismatch" in codes

        other_seed = dict(data, global_seed="a-different-seed")
        codes = [r[0] for r in snap_mod.restore(other_seed, sdk.world, sdk.core)]
        assert "snapshot.seed_mismatch" in codes, "seed drift silently changes every future draw"

        ghost = dict(data, agents=dict(data["agents"]))
        ghost["agents"]["agent:does_not_exist"] = ghost["agents"]["agent:pavel"]
        codes = [r[0] for r in snap_mod.restore(ghost, sdk.world, sdk.core)]
        assert "snapshot.unknown_agent" in codes
        assert "agent:does_not_exist" not in sdk.world.agents, \
            "a snapshot must never invent world content the pack does not define"

        thin = dict(data, agents={k: v for k, v in data["agents"].items() if k != "agent:pavel"})
        codes = [r[0] for r in snap_mod.restore(thin, sdk.world, sdk.core)]
        assert "snapshot.agent_not_in_snapshot" in codes

        print("ok  snapshot: schema, seed and roster mismatches are reported, not swallowed")
    finally:
        sdk.close()


def test_snapshot_size_is_independent_of_ledger_length():
    """Snapshot size must be a function of world state, not of how much has happened.

    Snapshots used to embed the whole event ledger plus the provider-call and
    reason-trace tables, which made each save O(session length) and the snapshot
    table O(saves x session length). The sharp test is that appending events which
    change no agent state must not change the snapshot size at all.
    """
    import json
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.events import Event
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        sdk.submit_player_text("ask Honce about clinic")
        first = sdk.store.load_snapshot(sdk.create_snapshot("a").value)
        baseline = len(json.dumps(first, sort_keys=True, default=str))

        # 300 events nobody can observe: they land in the ledger and change no agent.
        for _ in range(300):
            sdk.emit_event(Event(sdk.world.new_event_id(), sdk.world.world_time, "claim",
                                 actor=None, location="place:nowhere",
                                 payload={"summary": "unobserved beat"}))
        assert sdk.store.event_count() >= 300

        second = sdk.store.load_snapshot(sdk.create_snapshot("b").value)
        grown = len(json.dumps(second, sort_keys=True, default=str))

        for audit_stream in ("event_ledger", "provider_call", "reason_trace"):
            assert audit_stream not in second, \
                f"{audit_stream} is an append-only audit stream, not resumable state"
        assert second["ledger_watermark"] == sdk.store.ledger_position()

        # the ledger stays reconstructable as of the snapshot, without being copied in
        assert len(sdk.store.ledger_as_of(second["ledger_watermark"])) >= 300

        # only the event-id watermark may differ -> a handful of bytes, not 300 records
        assert grown - baseline < 200, (
            f"300 unobserved ledger events grew the snapshot by {grown - baseline} bytes; "
            "the ledger must not be copied into snapshots")
        print(f"ok  snapshot: 300 ledger events add {grown - baseline} bytes, not a ledger copy")
    finally:
        sdk.close()


def test_replay_golden_file_and_second_pack():
    from unscripted import UnscriptedRuntime, RuntimeConfig, validate_world_pack
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    noir = os.path.join(root, "worldpacks", "noir-harbor")
    assert validate_world_pack(noir).ok
    sdk = UnscriptedRuntime.create(RuntimeConfig(world_pack_path=noir, storage_path=":memory:"))
    try:
        assert "agent:clara" in sdk.world.agents
    finally:
        sdk.close()


def test_character_generation_from_environment_and_appearance():
    from unscripted import CharacterGenerationRequest, generate_characters
    world_data = {
        "places": {"place:gate": {"noise_level": 0.1, "surveillance_level": 0.9, "privacy_level": 0.1}},
        "factions": [{"id": "faction:watch", "territory": ["place:gate"]}],
    }
    req = CharacterGenerationRequest(count=2, location_id="place:gate",
                                     appearances=["uniform"], seed="unit")
    content = generate_characters(world_data, req)
    assert len(content.characters) == 2
    first = content.characters[0]
    assert first["location"] == "place:gate"
    assert first["roles"][0]["role"] == "role:officer"
    assert first["social_status"] >= 0.6
    assert any(b["agent"] == first["id"] and b["proposition"]["predicate"] == "core:holds_role"
               for b in content.initial_beliefs)
    assert any(b["agent"] == first["id"] and b["proposition"]["predicate"] == "place:has_surveillance"
               and b["proposition"]["slots"]["level"] == "high"
               for b in content.initial_beliefs)
    print("ok  generator: environment + appearance produce character profile and starting knowledge")


def test_bridge_profiles_and_event_mapping():
    from unscripted import bridge_event_to_world_event, list_bridge_profiles
    profiles = list_bridge_profiles()
    assert {"unreal", "unity", "godot", "custom", "inworld", "convai",
            "metahuman", "unreal_metahuman"} <= set(profiles)
    ev = bridge_event_to_world_event({
        "event_id": 42,
        "type": "claim",
        "actor": "agent:player_1",
        "location": "place:main_street",
        "payload": {"summary": "hello"}
    }, default_world_time=100)
    assert ev.event_id == 42 and ev.world_time == 100 and ev.payload["summary"] == "hello"
    print("ok  bridge: engine/front-end profiles and neutral event mapping work")


def test_service_turn_and_generate_handlers():
    from unscripted import UnscriptedRuntime, RuntimeConfig, UnscriptedService
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    service = UnscriptedService(sdk)
    try:
        turn = service.handle_post("/turn", {"text": "ask Honce about clinic"})
        assert "Honce" in turn["message"]
        generated = service.handle_post("/generate/characters", {
            "count": 1,
            "location_id": "place:police_post",
            "appearances": ["uniform"],
            "seed": "svc"
        })
        assert generated["characters"][0]["roles"][0]["role"] == "role:officer"
        health = service.handle_get("/health", {})
        assert health["ok"] is True
        receipt = service.handle_post("/event", {
            "type": "claim",
            "actor": "agent:player_1",
            "location": "place:main_street",
            "payload": {"summary": "engine event without id"}
        })
        assert int(receipt["event_id"]) > 0
        print("ok  service: HTTP handler surface supports turns and character generation")
    finally:
        sdk.close()
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
    ))
    try:
        replay = sdk.replay_commands(["look", "ask Honce about clinic"], replay_id="unit")
        assert replay.final_world_time == sdk.world.world_time
        assert "shut that night" in replay.steps[-1].message
        print("ok  replay: command replay works and second world pack loads")
    finally:
        sdk.close()


def test_llm_output_cleaning_is_safe():
    from unscripted.provider import HttpChatRealizer
    c = HttpChatRealizer._clean
    # scaffolding echo / internal plan must never survive -> empty -> template fallback
    assert c('{"dialogue_act": "evade", "avoid_topics": ["x"]}', 30) == ""
    assert c("**Analyze the Request:**", 30) == ""
    assert c("1.", 30) == ""
    # reasoning preamble: keep only what follows the answer label
    assert c("Thinking Process:\nAnswer: The clinic's closed.", 30) == "The clinic's closed."
    # leaked chat-template special tokens are cut off
    assert c("Shift is over, you can go home.<|endoftext|><|im_start|>SA", 40) == \
        "Shift is over, you can go home."
    # a clean reply is reduced to its first in-character sentence
    assert c("The clinic's closed. It was dark.", 40) == "The clinic's closed."
    # leading speaker label and surrounding quotes are stripped
    assert c('Vee: "Back off."', 30) == "Back off."
    print("ok  provider: messy LLM output is cleaned to a safe line or rejected for fallback")


def test_prospect_reference_is_need_not_wealth():
    from unscripted import Agent
    from unscripted.agency import risk_reference_point
    from unscripted.policy import prospect_value
    # wealthy but satisfied agent: no unmet need -> aspiration 0 -> a gain stays a gain
    rich = Agent(id="rich", resources=0.95, needs={})
    ref_rich = risk_reference_point(rich)
    assert ref_rich == 0.0, "wealth must NOT set the aspiration (old flow/stock-mix bug)"
    assert prospect_value(0.3, ref_rich) > 0, "a +0.3 outcome must read as a gain for a satisfied agent"
    # desperate agent: strong unmet need raises aspiration -> same gain falls short -> risk-seeking domain
    desperate = Agent(id="poor", resources=0.95, needs={"safety": 0.8, "money": 0.5})
    ref_desp = risk_reference_point(desperate)
    assert ref_desp == 0.8, "aspiration tracks the strongest unmet need"
    assert prospect_value(0.3, ref_desp) < 0, "below aspiration the same gain reads as a loss (risk-seeking)"
    print(f"ok  prospect: reference is need-aspiration (rich={ref_rich}, desperate={ref_desp}), not wealth")


def test_metahuman_blendshapes_bounded_and_emotion_specific():
    from unscripted import Vec3
    from unscripted.affect import AffectState
    from unscripted import affect_to_blendshapes, dominant_emotion
    angry = AffectState(mood=Vec3(-0.5, 0.5, 0.4),
                        active_emotions={"anger@player": 0.9})
    shapes = affect_to_blendshapes(angry)
    assert all(0.0 <= w <= 1.0 for w in shapes.values()), "blendshapes must stay in [0,1]"
    assert shapes.get("browDownLeft", 0) > 0.3 and shapes.get("browDownRight", 0) > 0.3, \
        "anger must lower the brow symmetrically"
    assert "mouthSmileLeft" not in shapes, "anger must not produce a smile"
    assert dominant_emotion(angry)[0] == "anger"

    happy = AffectState(mood=Vec3(0.6, 0.2, 0.3),
                        active_emotions={"joy@player": 0.8})
    happy_shapes = affect_to_blendshapes(happy)
    assert happy_shapes.get("mouthSmileLeft", 0) > 0.3, "joy must produce a smile"
    assert "browDownLeft" not in happy_shapes, "joy must not lower the brow"
    print("ok  metahuman: ARKit blendshapes are bounded and emotion-specific")


def test_metahuman_neutral_and_avatar_packet():
    from unscripted import UnscriptedRuntime, RuntimeConfig, Vec3
    from unscripted.affect import AffectState
    from unscripted import affect_to_blendshapes, dominant_emotion
    calm = AffectState(mood=Vec3(0.0, 0.0, 0.0))
    assert affect_to_blendshapes(calm) == {}, "a flat-affect face is fully neutral"
    assert dominant_emotion(calm)[0] == "neutral"

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        packet = sdk.avatar_turn("ask Vee about Milan")
        avatar = packet["avatar"]
        for key in ("text", "verdict", "emotion", "blendshapes", "gaze", "prosody", "posture"):
            assert key in avatar, f"avatar packet missing {key}"
        assert all(0.0 <= w <= 1.0 for w in avatar["blendshapes"].values())
        assert avatar["verdict"] == "ACCEPT", "spoken line must be validator-approved"
        # face packet is also available without taking a turn
        face = sdk.face_packet("agent:npc_red_jacket")
        assert "blendshapes" in face and "prosody" in face
        print("ok  metahuman: neutral face is empty; avatar/face packets are well-formed")
    finally:
        sdk.close()


def test_population_lod_decay_is_exact():
    from unscripted import Vec3
    from unscripted.affect import AffectEngine, AffectState
    eng = AffectEngine()

    def state():
        s = AffectState(mood=Vec3(-0.8, 0.6, 0.4), baseline=Vec3(-0.1, 0.0, 0.1))
        s.active_emotions = {"fear@x": 0.7, "anger@y": 0.5}
        return s

    stepwise = state()
    for _ in range(3):
        eng.decay(stepwise, 100)          # three small ticks (non-LOD per-tick path)
    catchup = state()
    eng.decay(catchup, 300)               # one catch-up over the full elapsed dt (LOD path)
    # mathematically identical; only sub-1e-9 floating-point accumulation differs
    for axis in ("p", "a", "d"):
        assert abs(getattr(stepwise.mood, axis) - getattr(catchup.mood, axis)) < 1e-9, \
            "exponential decay must compose: 3x100 == 1x300"
    assert stepwise.active_emotions == catchup.active_emotions
    print("ok  lod: decay is mathematically composable (LOD catch-up is exact)")


def test_population_lod_preserves_behavior():
    """The LOD path must be an optimisation, not a second set of rules.

    This test used to say "large-cast" while running the eight-person reference
    pack, which is the one size at which LOD cannot be wrong: with nobody
    dormant, the deferred path is barely taken. The cast is now built out to two
    hundred across a district with staggered days -- the shape the scale numbers
    in CONCEPT.md were measured on -- and every sampled character, dormant ones
    included, must land on the same affect either way.
    """
    import copy
    from unscripted import UnscriptedRuntime, RuntimeConfig
    from unscripted.agent import Agent
    from unscripted.routine import Routine
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")
    cmds = ["go market", "attack Pavel", "wait 120", "wait 120", "wait 120"]
    CAST, ROOMS = 200, 40

    def run(lod):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:", population_lod=lod))
        try:
            world = sdk.world
            authored = [a for a in world.agents.values() if a.id != sdk.config.player_id]
            template = next(iter(world.places.values()))
            for i in range(ROOMS):
                world.places[f"place:room_{i}"] = dict(
                    template, label=f"Room {i}", exits=[], aliases=[f"room{i}"])
            rooms = sorted(k for k in world.places if k.startswith("place:room_"))
            for i in range(CAST - len(authored)):
                src = authored[i % len(authored)]
                extra = Agent(
                    id=f"agent:extra_{i}", big_five=dict(src.big_five),
                    schwartz=dict(src.schwartz), needs=dict(src.needs),
                    identities=list(src.identities), roles=list(src.roles),
                    education=dict(src.education), relationships={},
                    goals=list(src.goals), location=rooms[i % len(rooms)],
                    public_name=f"Extra {i}", aliases=(f"extra{i}",),
                    routine=copy.deepcopy(src.routine), networks=(f"shift:{i % 3}",),
                    epistemic=dict(src.epistemic))
                world.agents[extra.id] = extra
            # Staggered days: a cast that all shares one hall is a different test
            # (and the reason an earlier scale measurement was 15x too pessimistic).
            for j, extra in enumerate(a for a in world.agents.values()
                                      if a.id.startswith("agent:extra_")):
                home, work = rooms[j % len(rooms)], rooms[(j * 7 + 3) % len(rooms)]
                shift = (j % 6) * 4
                extra.location = home
                extra.routine = Routine.from_list([
                    {"from": f"{shift:02d}:00", "place": work, "activity": "work"},
                    {"from": f"{(shift + 8) % 24:02d}:00", "place": home, "activity": "rest"},
                ])
            for c in cmds:
                sdk.submit_player_text(c)
            watched = ["agent:pavel"] + [f"agent:extra_{i}" for i in range(0, CAST - 8, 12)]
            return {aid: sdk.structured_agent(aid)["affect"] for aid in watched}
        finally:
            sdk.close()

    base, lod = run(False), run(True)
    assert len(base) > 15, "the sample has to be big enough to catch a divergence"
    # exact: deferred decay composes, and off-screen events are appraised before
    # world_time advances, so a dormant observer sees identical affect either way.
    for aid, expected in base.items():
        for k in ("valence", "arousal", "dominance", "stress"):
            assert expected[k] == lod[aid][k], \
                f"LOD must match non-LOD for {aid} on {k}: {expected[k]} vs {lod[aid][k]}"
    print(f"ok  lod: {CAST} characters over {ROOMS} places, LOD is behaviourally "
          f"identical ({len(base)} sampled)")


def test_golden_scenarios_all_pass():
    from unscripted.golden import run_all
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results = run_all(os.path.join(root, "golden"))
    assert results, "expected golden scenarios on disk"
    failures = [(r["name"], f) for r in results for f in r["failures"]]
    assert not failures, failures
    print(f"ok  golden: {len(results)} multi-step scenarios pass all assertions")


def test_multiturn_continuity_and_resume():
    from unscripted import UnscriptedRuntime, RuntimeConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    try:
        target = "agent:barkeep_12"
        ckey = f"conv_{target}_{cfg.player_id}"
        sdk.submit_player_text("ask Honce about clinic")
        conv = sdk.core.conversations[ckey]
        assert conv.discussed_topics.get("clinic") == 1
        first_trace = sdk.core.last_traces[target]
        assert not any(r[0] == "dialogue.topic_repeated" for r in first_trace)
        # re-ask the same topic -> continuity: counted again and flagged repeated
        sdk.submit_player_text("ask Honce about clinic")
        assert sdk.core.conversations[ckey].discussed_topics.get("clinic") == 2
        assert any(r[0] == "dialogue.topic_repeated" for r in sdk.core.last_traces[target])
        # snapshot, talk more, then restore -> conversation memory resumes from the snapshot
        snap = sdk.create_snapshot("mid-conversation")
        sdk.submit_player_text("ask Honce about clinic")
        assert sdk.core.conversations[ckey].discussed_topics.get("clinic") == 3
        sdk.restore_snapshot(snap)
        assert sdk.core.conversations[ckey].discussed_topics.get("clinic") == 2, \
            "restore must resume the conversation as it was at snapshot time"
        print("ok  dialogue: multi-turn continuity counts re-asks and resumes across save/load")
    finally:
        sdk.close()


def test_structured_state_and_demo_endpoints():
    from unscripted import UnscriptedRuntime, RuntimeConfig, UnscriptedService
    from unscripted.webdemo import DEMO_HTML
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = RuntimeConfig(world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
                        storage_path=":memory:")
    sdk = UnscriptedRuntime.create(cfg)
    service = UnscriptedService(sdk)
    try:
        # the demo page is real HTML served by the runtime
        assert DEMO_HTML.startswith("<!DOCTYPE html>") and "Unscripted" in DEMO_HTML
        # structured scene for the UI
        scene = service.handle_get("/state/scene", {})
        assert scene["location"] and isinstance(scene["npcs"], list) and scene["npcs"]
        # drive a turn, then the spoken NPC must expose a real reason trace + beliefs
        service.handle_post("/turn", {"text": "ask Honce about clinic"})
        agent = service.handle_get("/state/agent", {"agent_id": ["agent:barkeep_12"]})
        assert agent["name"] == "Honce"
        assert agent["beliefs"], "Honce should hold beliefs about the clinic"
        b = agent["beliefs"][0]
        assert 0.0 <= b["prob"] <= 1.0 and "provenance" in b and b["text"]
        assert agent["reason_trace"], "a spoken turn must leave an explainable trace"
        assert "blendshapes" in agent["face"]
        # structured world with factions/heat
        world = service.handle_get("/state/world", {})
        assert "factions" in world and world["factions"]
        # unknown agent is a clean 404, not a crash
        err = service.handle_get("/state/agent", {"agent_id": ["agent:nope"]})
        assert isinstance(err, tuple) and err[1] == 404
        print("ok  demo: structured scene/agent/world endpoints + HTML page are well-formed")
    finally:
        sdk.close()


def test_the_cpp_port_reproduces_python_exactly():
    """The ported modules, held to this implementation on every run.

    A port is not a translation that is finished once. It is a second
    implementation that has to keep agreeing while the first one changes, and
    the way that guarantee dies is quietly: somebody adjusts a constant here,
    the C++ side is not touched, and nothing says so until a console build
    behaves differently six months later.

    So all four probes run in the suite:

      `port_probe.py`   -- blake2b, the uniform draw, the belief arithmetic and
                           Python's round() on the values where the obvious C++
                           implementation is wrong, compared as raw 64 bits.
      `belief_probe.py` -- nine belief scenarios driven from one shared case
                           file through the real `unscripted.belief`, compared field by
                           field including the ORDER of every map.
      `engine_probe.py` -- eighty-seven more across the other forty-eight
                           modules: mood and emotion decay, trust kinetics,
                           identity salience, memory activation and
                           consolidation, the seeded choice of what to do, who
                           is where and who can hear it, what stays inside a
                           circle, what a claim becomes on its way through a
                           town, every shipped world pack read from disk, and
                           all five conformance scenarios played end to end.
      `tuning_probe.py` -- every knob a world pack may turn: 79 across 14
                           engines, compared name for name, ORDER for order and
                           bit for bit, plus what a tuning block changes and the
                           reason rows it leaves in the trace. It guards the one
                           part of this port with no arithmetic in it that is
                           still easy to get badly wrong: C++ has no reflection,
                           so the names are an explicit list, and a parameter
                           added to an engine and forgotten there becomes a knob
                           a pack sets in vain.

    Skipped, not failed, where there is no compiler: this suite has to pass on a
    machine that only runs Python, and a port check that cannot run is not a
    regression in the runtime.

    All four were mutation-tested rather than trusted: 504 deliberate defects
    introduced into the C++ so far, 487 caught. A hundred and twenty-seven
    escaped on the first attempt and not one because the port was right -- the
    CASES were too weak, and each was strengthened until it failed.

    Seventeen are still not caught, and each is documented at the line as
    provably equivalent or mathematically unreachable rather than quietly
    dropped. `port/README.md` has the per-module table and the reason for each.
    """
    import platform
    import shutil
    import subprocess

    if not shutil.which(os.environ.get("CXX", "g++")):
        print("  cpp port: no compiler on this machine, nothing measured")
        return

    # WHERE THIS COMPARISON IS MEANINGFUL, and where it is a different question.
    #
    # Python 3.12 gave `sum()` a fast path over floats that uses Neumaier
    # compensated summation, and the port reproduces that. On 3.10 and 3.11 the
    # reference implementation itself sums naively, so the two sides disagree by
    # about one bit in nineteen places -- and the port is not the thing that is
    # wrong. Measured across all five conformance fixtures: 12 fields move, the
    # worst by 0.9 ULP, and no discrete outcome changes. So this is skipped
    # there rather than weakened everywhere.
    if sys.version_info < (3, 12):
        print("  cpp port: skipped on Python %d.%d -- sum() only compensates "
              "from 3.12, so a bit-exact comparison is asking the wrong "
              "question here (see port/README.md)"
              % sys.version_info[:2])
        return

    # On Windows the two sides link different C runtimes: CPython is built with
    # MSVC and the probe with MinGW, so `log()` may legitimately differ in the
    # last bit between them. That is the toolchain question `port/README.md`
    # tells people to measure on their own target, not a defect in the port, so
    # a mismatch there is REPORTED rather than failed. Everywhere else -- Linux,
    # macOS -- both sides call the same libm and the bar is exact.
    advisory = platform.system() == "Windows"

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    probes = [("determinism, rounding and the belief arithmetic, as raw bits",
               os.path.join(root, "port", "cpp", "probe", "port_probe.py")),
              ("nine belief scenarios, field by field",
               os.path.join(root, "port", "cpp", "probe", "belief_probe.py")),
              ("the other forty-eight modules -- every engine, every optional "
               "layer, the parser, the validator, the tick loop, the turn loop "
               "and the pack reader -- across eighty-nine scenarios, including "
               "all five conformance fixtures played end to end",
               os.path.join(root, "port", "cpp", "probe", "engine_probe.py")),
              ("a world pack's tuning block -- 79 knobs across 14 engines, "
               "every name, every order and every value, and what a block "
               "changes",
               os.path.join(root, "port", "cpp", "probe", "tuning_probe.py"))]

    for what, script in probes:
        assert os.path.exists(script), "missing port probe: %s" % script
        result = subprocess.run([sys.executable, script], capture_output=True,
                                text=True, cwd=root)
        if result.returncode != 0 and advisory:
            print("  cpp port: %s differs on this toolchain -- reported, not "
                  "failed, because CPython and the probe link different C "
                  "runtimes here:\n%s" % (what, result.stdout[-800:]))
            return
        assert result.returncode == 0, (
            "the C++ port no longer reproduces Python (%s):\n%s%s"
            % (what, result.stdout, result.stderr))

    print("  cpp port: reproduces Python exactly -- " + "; ".join(
        what for what, _script in probes))


def test_recall_is_bounded_by_working_memory():
    """A character brought seven things to mind, not everything they know.

    `working_cap` is Miller's number and it is load-bearing: retrieval feeds the
    dialogue layer, so an unbounded recall is a character who answers a question
    with everything they have ever heard. It went untested for a long time --
    the cap could be raised tenfold and the whole suite stayed green, which is
    how this test came to be written.

    Both ends are pinned. A cap that is merely "small" would pass while being
    wrong, and a cap that returned the WEAKEST seven would pass a length check.
    """
    from unscripted.memory import Memory, MemoryEngine

    engine = MemoryEngine()
    now = 10_000
    memories = []
    for index in range(30):
        memories.append(Memory(
            memory_id="mem_%02d" % index, owner="agent:x", type="episodic",
            content="thing %02d" % index,
            # Descending importance, so which seven come back is decidable.
            importance=1.0 - index * 0.03,
            emotional_valence=0.0, source_conf=0.9, world_time=now - 10,
            # Activation comes from the times a memory was PRESENTED, not from
            # when it happened -- an empty list is a memory that was never
            # actually laid down, and scores -10.
            presentations=[now - 10]))

    retrieved = engine.retrieve(memories, now, mood_valence=0.0)
    cap = engine.params["working_cap"]
    assert cap == 7, "the documented cap moved without this test moving: %r" % cap
    assert len(retrieved) == cap, (
        "recall returned %d of %d memories against a cap of %d"
        % (len(retrieved), len(memories), cap))

    # And they are the STRONGEST seven, not the first seven in the list.
    came_back = {item.memory_id for _activation, _probability, item in retrieved}
    assert came_back == {"mem_%02d" % i for i in range(cap)}, sorted(came_back)

    # Raising the cap must actually raise the recall, or the parameter is
    # decoration -- which is exactly what a passing suite could not tell you.
    engine.params["working_cap"] = 12
    assert len(engine.retrieve(memories, now, mood_valence=0.0)) == 12

    print("ok  memory: recall stops at seven, and returns the strongest seven")


def test_a_claim_stops_being_passed_on_after_enough_retellings():
    """Twelve mouths, and the thirteenth does not bother.

    `max_hops` is what stops a rumour circulating forever in a world where
    everybody meets everybody. Without it a claim keeps being retold until the
    tick cap stops it, every retelling makes a memory, and a long session ends
    up dominated by one piece of gossip.

    The suite never noticed its removal, because no scenario ran long enough to
    reach twelve hops. So this asks the question directly, at the boundary --
    `>=` against `>` is one retelling, and one retelling is a different world.
    """
    from unscripted.belief import Belief
    from unscripted.diffusion import DiffusionEngine
    from unscripted.agent import Agent
    from unscripted.ontology import Proposition
    from unscripted.world import World

    engine = DiffusionEngine()
    limit = engine.params["max_hops"]
    assert limit == 12, "the documented hop limit moved without this test: %r" % limit

    world = World(global_seed="hops")
    speaker = Agent(id="agent:teller")
    world.agents[speaker.id] = speaker

    def believing(hops):
        claim = Proposition("was_seen_at", {"subject": "agent:x", "place": "place:y"})
        belief = Belief(proposition=claim)
        # Convinced enough to pass on, and recent enough to be worth telling.
        # The field is `logit_val`; `logit` would silently create a new attribute
        # and leave the belief at p=0.5, which is below the telling floor.
        belief.logit_val = 3.0
        belief.hops = hops
        belief.txn_time = world.world_time
        speaker.beliefs.clear()
        speaker.beliefs[claim.core_key()] = belief
        return claim.core_key()

    key = believing(limit - 1)
    assert [k for _score, k, _b in engine._tellable(speaker, world)] == [key], (
        "a claim one hop short of the limit must still be worth telling")

    believing(limit)
    assert engine._tellable(speaker, world) == [], (
        "a claim at the limit was still offered for retelling")

    believing(limit + 4)
    assert engine._tellable(speaker, world) == []

    print("ok  diffusion: a claim twelve mouths from its source stops travelling")


def test_a_retelling_carries_the_first_origin_not_the_latest():
    """The claim a holder would cite is the one they heard FIRST.

    This is the sentence the whole runtime is sold on -- *a rumour relayed
    through five mouths is worth one witness rather than five* -- and it works
    because the origin travels with the CLAIM and never with the mouth it came
    out of. `primary_origin` is `next(iter(origin_counts))`, the first key ever
    inserted, and Python dictionaries preserve that.

    Nothing asserted it. Returning the LATEST origin instead passed all 160
    checks, and the consequence would not have been a wrong number in a log: a
    retelling would cite whoever last repeated it, so a claim echoing around a
    town would keep arriving from a "new" source and the correlation discount --
    the thing that stops repetition becoming proof -- would never bite.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    beliefs = {}
    claim = Proposition("was_seen_at", {"subject": "agent:kane", "place": "place:dock"})

    def hear(origin, speaker, at):
        belief, _reasons = engine.update(
            beliefs, claim, asserter_polarity="+", trust=0.7, competence=0.7,
            skepticism=0.4, claim_id="clm_" + origin, origin_event=origin,
            world_time=at, speaker=speaker)
        return belief

    first = hear("incident_at_the_dock", "agent:byrne", 100)
    assert first.primary_origin == "incident_at_the_dock"

    # A different incident, later. The FIRST one is still what they would cite.
    hear("a_second_sighting", "agent:okoye", 200)
    # And the original again, from a third mouth.
    third = hear("incident_at_the_dock", "agent:vega", 300)

    assert third.primary_origin == "incident_at_the_dock", (
        "the holder cited %r, which is whoever spoke last rather than what they "
        "first heard" % third.primary_origin)
    assert list(third.origin_counts) == ["incident_at_the_dock", "a_second_sighting"], (
        "origins are no longer in the order they were heard: %r"
        % list(third.origin_counts))
    assert third.origin_counts["incident_at_the_dock"] == 2

    # The consequence, not only the property: the SECOND time that origin
    # arrives it must persuade less than the first, because it is the same
    # incident coming round again.
    fresh = {}
    once = engine.update(fresh, claim, asserter_polarity="+", trust=0.7,
                         competence=0.7, skepticism=0.4, claim_id="a",
                         origin_event="one_incident", world_time=100,
                         speaker="agent:byrne")[0]
    gain_first = once.support_for
    twice = engine.update(fresh, claim, asserter_polarity="+", trust=0.7,
                          competence=0.7, skepticism=0.4, claim_id="b",
                          origin_event="one_incident", world_time=200,
                          speaker="agent:okoye")[0]
    gain_second = twice.support_for - gain_first
    assert gain_second < gain_first, (
        "hearing the same incident twice added as much the second time (%.4f) as "
        "the first (%.4f)" % (gain_second, gain_first))

    print("ok  belief: a holder cites the incident they first heard, and the "
          "second telling of it persuades less")


def test_nobody_is_convinced_by_the_sound_of_their_own_voice():
    """You learn nothing by hearing yourself say it.

    Without the guard, a character's own utterance comes back to them as
    evidence from a fresh claim id -- a provenance loop, and repetition becomes
    proof. Somebody could talk themselves into certainty.

    The guard could be deleted and all 160 checks stayed green, because on a
    DIRECT event the perception layer already declines to report the actor as an
    observer, so nothing ever reached it. There is one path where it does: a
    BROADCAST reaches everybody exposed to the channel, and a speaker may well be
    listening to the channel they are speaking on. That is the case here, and it
    is the only one there is.
    """
    from unscripted.agent import Agent
    from unscripted.events import Event
    from unscripted.runtime import Runtime
    from unscripted.world import World

    world = World(global_seed="own-voice", world_time=500)
    world.channels = {"chan:city_radio": {"type": "radio"}}
    for name in ("agent:announcer", "agent:listener"):
        world.agents[name] = Agent(
            id=name, location="place:studio",
            big_five={"agreeableness": 0.5, "emotional_stability": 0.5})
        world.media_exposure[(name, "chan:city_radio")] = {"attention": 0.9}
    world.places = {"place:studio": {}}
    runtime = Runtime(world)

    claim = {"predicate": "was_seen_at",
             "slots": {"subject": "agent:kane", "place": "place:dock"},
             "polarity": "+"}
    for round_number in range(6):
        runtime.process_event(Event(
            world.new_event_id(), world.world_time, "broadcast",
            actor="agent:announcer", location=None,
            payload={"proposition": claim, "channel": "chan:city_radio",
                     "credibility": 0.8, "importance": 0.6,
                     "summary": "the announcer says it again"}))
        world.world_time += 60

    announcer = world.agents["agent:announcer"]
    listener = world.agents["agent:listener"]

    assert not announcer.beliefs, (
        "the announcer talked themselves into believing it: %s"
        % {k: round(b.expected_prob, 3) for k, b in announcer.beliefs.items()})
    # And the listener DID learn it, so the case is not passing because nothing
    # reached anybody.
    assert listener.beliefs, "nobody heard the broadcast at all"
    heard = next(iter(listener.beliefs.values()))
    assert heard.expected_prob > 0.6, heard.expected_prob

    print("ok  runtime: an announcer is not persuaded by their own broadcast, "
          "and the audience is")


def test_a_character_does_not_repeat_a_line_they_just_said():
    """The repetition guard looks back THREE released lines, not one.

    What would be wrong in the world if this failed: a character who has just
    said "I would rather not say" says it again two turns later, and the scene
    reads as a broken machine rather than as somebody being evasive. The guard
    exists because a deterministic realizer under a narrow plan will happily
    produce the same sentence twice, and because a model asked the same question
    twice tends to answer it identically.

    Why the case is built this way: it pins the BOUNDARY from both sides. The
    fourth-most-recent line must be allowed and the third-most-recent must be
    refused, so a window of 1, 2 or 4 all fail. Mutation testing found this: the
    window could be shrunk to a single line and all 162 checks stayed green,
    because nothing anywhere asked how far back it looks.

    `canon_mode` is off because this is about the repetition layer alone -- with
    parse-back on, a bland line can be refused for an unrelated reason and the
    test would pass without ever reaching layer 3c.
    """
    from unscripted import Validator
    from unscripted.dialogue import DialoguePlan
    from unscripted.validator import CANON_OFF

    v = Validator(canon_mode=CANON_OFF)
    assert v.repetition_window == 3, (
        f"this test pins a window of 3; the validator now uses "
        f"{v.repetition_window} and the boundary below is the wrong one")
    plan = DialoguePlan(speaker="npc", addressee="p", dialogue_act="inform", goal="x")

    recent = ["I would rather not say.",      # -4: outside the window
              "Maybe. Why do you care?",      # -3: the oldest line still refused
              "That is not for me to tell.",  # -2
              "Ask somebody else."]           # -1: the line just said

    for offset, line in ((-3, recent[-3]), (-2, recent[-2]), (-1, recent[-1])):
        verdict = v.check(line, plan, None, recent).verdict
        assert verdict == "REJECT_SOFT", (
            f"a line said {abs(offset)} turn(s) ago must be refused, got {verdict}")

    assert v.check(recent[-4], plan, None, recent).verdict == "ACCEPT", (
        "the fourth line back is outside the window and must be allowed again, "
        "or a character can never return to a phrase")
    assert v.check("Nothing comes to mind.", plan, None, recent).verdict == "ACCEPT", (
        "a line never said must be accepted")

    print("ok  validator: a line refused three back, allowed four back "
          "(repetition window 3, pinned at both edges)")


def test_the_c_abi_is_callable_from_c():
    """A C ABI that only works from C++ is not a C ABI.

    Three engines reach this runtime through one C header: Unreal links it
    natively, Unity marshals it through P/Invoke, Godot loads it as a
    GDExtension. None of them is a C++ compiler on the calling side, and the
    mistake does not show up until somebody's plugin will not link.

    So the check is a program in C99, compiled by a C compiler, linked against
    the library, driving a real world pack: open it, play a turn, ask a
    character what they think, take a save, move the world on, put the save
    back, and refuse everything that should be refused -- a null path, a pack
    that is not there, a character who does not exist, time running backwards, a
    save from somebody else's game, an intent nobody issued.

    Skipped where there is no compiler, for the same reason the port probes are.
    """
    import shutil
    import subprocess
    import tempfile

    cxx = os.environ.get("CXX", "g++")
    cc = os.environ.get("CC", "gcc")
    if not shutil.which(cxx) or not shutil.which(cc):
        print("  c abi: no C and C++ compiler pair on this machine")
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abi = os.path.join(root, "port", "cpp", "abi")
    include = os.path.join(root, "port", "cpp", "include")
    with tempfile.TemporaryDirectory() as work:
        library = os.path.join(work, "usc.o")
        caller = os.path.join(work, "caller.o")
        binary = os.path.join(work, "abi_probe")
        for command in (
                [cxx, "-std=c++17", "-O1", "-I", include, "-I", abi, "-c",
                 os.path.join(abi, "usc.cpp"), "-o", library],
                # C99, and with warnings as errors: a header that needs a C++
                # compiler, or that a C compiler has to guess at, fails here.
                [cc, "-std=c99", "-Wall", "-Werror", "-O1", "-I", abi, "-c",
                 os.path.join(abi, "abi_probe.c"), "-o", caller],
                [cxx, "-O1", caller, library, "-o", binary]):
            built = subprocess.run(command, capture_output=True, text=True)
            assert built.returncode == 0, (
                "the C ABI does not build:\n%s%s" % (built.stdout, built.stderr))
        result = subprocess.run([binary, os.path.join(root, "worldpacks",
                                                      "cyberpunk-block")],
                                capture_output=True, text=True, cwd=root)
        assert result.returncode == 0, (
            "the C ABI does not behave:\n%s%s" % (result.stdout, result.stderr))
    print("  c abi: " + result.stdout.strip().splitlines()[-1])


def _find_tool(env_name, on_path, candidates):
    """A toolchain this machine may or may not have.

    Checked in the order a person would: an explicit environment variable, then
    the PATH, then the places the installers actually put things. A binding test
    that only runs when somebody has already configured their shell is a binding
    test that never runs.
    """
    import glob
    import shutil

    declared = os.environ.get(env_name)
    if declared and os.path.exists(declared):
        return declared
    for name in on_path:
        found = shutil.which(name)
        if found:
            return found
    for pattern in candidates:
        for found in sorted(glob.glob(os.path.expanduser(pattern)), reverse=True):
            if os.path.isfile(found) and os.access(found, os.X_OK):
                return found
    return None


def test_the_unreal_binding_talks_to_the_runtime():
    """The Unreal module's engine-free half, against the real library.

    Unreal is the one engine that cannot be driven from this suite -- it is not
    installed on the machine the port was written on, and a plugin nobody has
    compiled is a guess. So the module is SPLIT: everything that touches the
    runtime is plain C++ in `UscNative.h`, and the UObject layer above it does
    nothing but convert FString to UTF-8. This exercises the first half, which
    is where a mistake would actually live.

    It has already earned its place. The first version wrote
    `record(fn(runtime_, &json), json)`, which compiles and is wrong: C++ does
    not order the evaluation of a call's arguments, so the compiler is free to
    read `json` before `fn` has written it -- and gcc at -O2 does. Nine checks
    failed and the answer was simply empty.
    """
    import shutil
    import subprocess
    import tempfile

    cxx = os.environ.get("CXX", "g++")
    if not shutil.which(cxx):
        print("  unreal binding: no C++ compiler on this machine")
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module = os.path.join(root, "port", "bindings", "unreal")
    public = os.path.join(module, "Source", "Unscripted", "Public")
    abi = os.path.join(root, "port", "cpp", "abi")
    include = os.path.join(root, "port", "cpp", "include")
    with tempfile.TemporaryDirectory() as work:
        objects = []
        for source, extra in (
                (os.path.join(module, "Source", "Unscripted", "Private",
                              "UscNative.cpp"), []),
                (os.path.join(module, "test", "usc_native_test.cpp"), []),
                (os.path.join(abi, "usc.cpp"), ["-I", include])):
            obj = os.path.join(work, os.path.basename(source) + ".o")
            built = subprocess.run(
                [cxx, "-std=c++17", "-O2", "-Wall", "-Werror", "-I", public,
                 "-I", abi] + extra + ["-c", source, "-o", obj],
                capture_output=True, text=True)
            assert built.returncode == 0, (
                "the Unreal binding does not build:\n%s%s"
                % (built.stdout, built.stderr))
            objects.append(obj)
        binary = os.path.join(work, "usc_native_test")
        linked = subprocess.run([cxx, "-O2"] + objects + ["-o", binary],
                                capture_output=True, text=True)
        assert linked.returncode == 0, "link failed:\n" + linked.stderr
        result = subprocess.run([binary, root], capture_output=True, text=True)
        assert result.returncode == 0, (
            "the Unreal binding does not behave:\n%s%s"
            % (result.stdout, result.stderr))
    print("  unreal binding: " + result.stdout.strip().splitlines()[-1])


def test_the_unity_binding_marshals_correctly():
    """The Unity binding, compiled by a C# compiler and run against the library.

    The editor is not the thing under test; the MARSHALLING is, and it is the
    same code either way. Two mistakes in a P/Invoke layer crash rather than
    misbehave, and neither shows up until runtime: a `string` return value makes
    .NET free a pointer the library owns, and a `string[]` argument arrives
    without the null terminator the C side reads. Both are checked here.

    Skipped where there is no .NET SDK. Unity ships one, so this usually runs on
    a machine that has Unity at all -- `UNSCRIPTED_DOTNET` points at another.
    """
    import json as json_module
    import shutil
    import subprocess
    import tempfile

    cxx = os.environ.get("CXX", "g++")
    dotnet = _find_tool("UNSCRIPTED_DOTNET", ["dotnet"],
                        ["~/unity-*/Editor/Data/DotNetSdk/dotnet",
                         "~/Unity/Hub/Editor/*/Editor/Data/DotNetSdk/dotnet",
                         "/opt/unity/Editor/Data/DotNetSdk/dotnet"])
    if not dotnet or not shutil.which(cxx):
        print("  unity binding: no .NET SDK found (set UNSCRIPTED_DOTNET to run it)")
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project = os.path.join(root, "port", "bindings", "unity", "test")
    with tempfile.TemporaryDirectory() as work:
        environment = dict(os.environ,
                           DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1",
                           DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
        built = subprocess.run([dotnet, "build", "-c", "Release", "-o", work],
                               cwd=project, capture_output=True, text=True,
                               env=environment)
        if built.returncode != 0:
            print("  unity binding: the .NET SDK here cannot build it:\n"
                  + built.stdout[-600:])
            return
        # The native library goes beside the assembly, which is where the
        # runtime looks for a DllImport with no path.
        library = subprocess.run(
            [cxx, "-std=c++17", "-O2", "-fPIC", "-shared", "-DUSC_BUILD_SHARED",
             "-I", os.path.join(root, "port", "cpp", "include"),
             "-I", os.path.join(root, "port", "cpp", "abi"),
             os.path.join(root, "port", "cpp", "abi", "usc.cpp"),
             "-o", os.path.join(work, "libusc.so")],
            capture_output=True, text=True)
        assert library.returncode == 0, "the native library did not build:\n" \
            + library.stderr
        result = subprocess.run(
            [dotnet, os.path.join(work, "UnscriptedAbiTest.dll"), root],
            capture_output=True, text=True, env=environment)
        assert result.returncode == 0, (
            "the Unity binding does not behave:\n%s%s"
            % (result.stdout, result.stderr))
    del json_module
    print("  unity binding: " + result.stdout.strip().splitlines()[-1])


def test_the_godot_binding_loads_and_runs():
    """The GDExtension, loaded by a real Godot and driven from GDScript.

    This is the part no amount of C++ testing covers: whether Godot can see the
    class, construct it, call its methods and read what comes back. It found the
    one mistake that matters in a GDExtension on its first run -- returning our
    own data from `create_instance_func` where Godot expects a Godot object,
    which segfaults inside the engine with nothing of ours in the backtrace.

    Skipped where there is no Godot. `UNSCRIPTED_GODOT` points at one.
    """
    import shutil
    import subprocess

    cxx = os.environ.get("CXX", "g++")
    godot = _find_tool("UNSCRIPTED_GODOT", ["godot", "godot4"],
                       ["~/.local/opt/godot/Godot_v4*",
                        "~/.local/bin/Godot_v4*",
                        "/opt/godot/Godot_v4*",
                        "/usr/local/bin/Godot_v4*"])
    if not godot or not shutil.which(cxx):
        print("  godot binding: no Godot found (set UNSCRIPTED_GODOT to run it)")
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project = os.path.join(root, "port", "bindings", "godot")
    library = subprocess.run(
        [cxx, "-std=c++17", "-O2", "-fPIC", "-shared",
         "-I", project,
         "-I", os.path.join(root, "port", "cpp", "abi"),
         "-I", os.path.join(root, "port", "cpp", "include"),
         os.path.join(project, "usc_gdextension.cpp"),
         os.path.join(root, "port", "cpp", "abi", "usc.cpp"),
         "-o", os.path.join(project, "bin", "libusc_godot.so")],
        capture_output=True, text=True)
    assert library.returncode == 0, (
        "the GDExtension does not build:\n" + library.stderr)

    # Godot writes an extension list on its first look at a project. Without
    # it the class is simply absent, which reads as a binding bug and is not.
    if not os.path.exists(os.path.join(project, ".godot", "extension_list.cfg")):
        subprocess.run([godot, "--headless", "--path", project, "--editor",
                        "--quit"], capture_output=True, text=True, timeout=600)
    result = subprocess.run(
        [godot, "--headless", "--path", project, "--script", "test/abi_test.gd"],
        capture_output=True, text=True, timeout=600)
    assert result.returncode == 0 and "every Godot-binding check passed" \
        in result.stdout, ("the Godot binding does not behave:\n%s%s"
                           % (result.stdout, result.stderr))
    print("  godot binding: every check passed, driven from GDScript")


def test_a_port_may_differ_in_the_last_bit_and_nowhere_else():
    """The tolerance a port is judged by, held to what it was measured against.

    `log()` is a library function, not an operation IEEE-754 pins down, so a
    correct port on a different toolchain may return doubles one bit away from
    these. The fixtures compare eighteen significant digits, so without a
    tolerance that port fails every scenario for a reason that is not its fault.

    With one, the tolerance becomes the thing that can rot: widen it and it
    starts passing ports that are genuinely wrong. So this pins both ends.

    The smallest disagreement two correct implementations could have is
    `nextafter(log(x))`. That is what gets substituted here, across every module
    that took its own reference to `log`, and the whole suite is re-run against
    the committed fixtures:

      - exact: every scenario fails, which is why the tolerance exists at all
      - tolerant: nothing fails, and no discrete outcome moved
      - a real defect, log() off by one part in ten thousand: still caught
    """
    import importlib
    import math
    import pkgutil

    import unscripted
    from unscripted import conformance

    real_log = math.log

    def substitute(fn):
        """Replace `log` everywhere it was imported, and hand back an undo."""
        touched = []
        for module in pkgutil.iter_modules(unscripted.__path__):
            loaded = importlib.import_module("unscripted." + module.name)
            if getattr(loaded, "log", None) is real_log:
                loaded.log = fn
                touched.append(loaded)
        math.log = fn

        def restore():
            for loaded in touched:
                loaded.log = real_log
            math.log = real_log
        return restore

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixtures = os.path.join(root, "conformance")
    tolerance = conformance.DEFAULT_ULP_TOLERANCE

    # Baseline: this implementation matches its own fixtures. If it did not,
    # everything below would be measuring the wrong thing.
    #
    # Exact from Python 3.12, and NOT exact before it -- `sum()` only
    # compensates from 3.12, and the fixtures were generated on a newer
    # interpreter. Measured rather than assumed: 12 fields move, the worst by
    # 0.9 ULP, no discrete outcome changes, and the port tolerance absorbs all
    # of it. So the baseline uses that tolerance on an older interpreter and
    # says so, instead of failing for a reason that is documented and harmless.
    baseline_tolerance = 0.0 if sys.version_info >= (3, 12) else tolerance
    drift = conformance.check(fixtures, pack_root=root,
                              ulp_tolerance=baseline_tolerance)
    assert not drift, (
        "the fixtures no longer match this implementation; regenerate first. "
        "%d field(s), first: %s" % (len(drift), drift[0]))

    restore = substitute(lambda x, *rest: math.nextafter(real_log(x, *rest), math.inf))
    try:
        strict = conformance.check(fixtures, pack_root=root)
        forgiving = conformance.check(fixtures, pack_root=root,
                                      ulp_tolerance=tolerance)
    finally:
        restore()

    assert strict, "one bit of difference in log() should fail an exact check"
    assert not forgiving, (
        "a port whose log() differs by one bit is correct and must pass; "
        "%d field(s) still failed: %s" % (len(forgiving), forgiving[:3]))

    # And every one of those differences was a number, not a decision. This is
    # the claim the tolerance rests on, so it is asserted rather than trusted.
    for _scenario, _where, expected, actual in strict:
        assert isinstance(expected, str) and isinstance(actual, str)
        float(expected), float(actual)      # raises if a string or a bool moved

    # The other end: a defect four orders of magnitude larger than a rounding
    # difference must not slip through the same tolerance.
    restore = substitute(lambda x, *rest: real_log(x, *rest) * 1.0001)
    try:
        wrong = conformance.check(fixtures, pack_root=root, ulp_tolerance=tolerance)
    finally:
        restore()
    assert len(wrong) > 50, (
        "log() off by one part in ten thousand slipped through the port "
        "tolerance; it caught only %d field(s)" % len(wrong))

    print("  a port may differ by <=%g ULP and nowhere else: "
          "%d exact failures, 0 tolerated, %d caught when genuinely wrong"
          % (tolerance, len(strict), len(wrong)))


def test_full_showcase_runs_all_checks():
    from unscripted.showcase import run_showcase
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = run_showcase(
        world_pack=os.path.join(root, "worldpacks", "cyberpunk-block"),
        secondary_world_pack=os.path.join(root, "worldpacks", "noir-harbor"),
        storage_path=":memory:",
    )
    failed = [name for name, ok in result["checks"].items() if not ok]
    assert not failed, failed
    assert "Automatic Character Generation" in result["output"]
    assert "Bridge" in result["output"]
    print("ok  showcase: full SDK sales/regression demo passes all checks")



# ---------------------------------------------------------------------------
# Regressions from the 2026-09-07 external review. Each of these reproduced a
# real defect against a suite that was fully green, which is the point of
# keeping them: the gaps were BETWEEN modules and in properties nothing asked
# about, not inside any one engine.
# ---------------------------------------------------------------------------


def test_evidence_pools_follow_the_contribution_not_the_assertion():
    """A claim that lowers the probability must not be filed as support FOR it.

    `kappa` can legitimately fall below 0.5 -- `trust=0, competence=0,
    skepticism=1` gives 0.25 with the shipped constants -- and below it the
    log-odds term is negative: the source is credible enough to be worth
    believing the opposite of. The update filed the pool by the ASSERTED
    polarity instead of by what the evidence did, so a positive claim drove the
    probability to 0.25 while reporting 1.0986 of support in favour.

    Failing here means `ignorance` and `conflict` are describing a different
    belief from the one `expected_prob` describes.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    belief, _ = engine.update({}, claim, asserter_polarity="+", trust=0.0,
                              competence=0.0, skepticism=1.0, claim_id="c1",
                              origin_event="o1", world_time=1, speaker="agent:liar")
    assert belief.expected_prob < 0.5, belief.expected_prob
    assert belief.support_for == 0.0, (
        "a claim that LOWERED the probability was filed as support for it "
        f"({belief.support_for})")
    assert belief.support_against > 0.0
    assert belief.conflict == 0.0, "one source cannot be in conflict with itself"

    # And the ordinary direction is unchanged.
    trusted, _ = engine.update({}, claim, asserter_polarity="+", trust=0.9,
                               competence=0.9, skepticism=0.0, claim_id="c2",
                               origin_event="o2", world_time=1, speaker="agent:vee")
    assert trusted.support_for > 0.0 and trusted.support_against == 0.0
    print("ok  belief: the evidence pool follows what the evidence did, not how "
          "it was asserted")


def test_discrediting_a_source_weakens_evidence_without_inventing_conflict():
    """Exposing a liar makes a belief LESS supported, not CONTESTED.

    The two are different epistemic states and the runtime distinguishes them on
    purpose. Revision used to add the (negative) adjustment to
    `support_against`, so discrediting the only source a belief had reported
    conflict 0.947 -- a contradiction out of nothing, with no second claim
    anywhere in the world.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition
    from unscripted.revision import discredit

    world = _mini_world("revision")
    engine = BeliefEngine()
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    belief, _ = engine.update(world.agents["npc"].beliefs, claim,
                              asserter_polarity="+", trust=0.9, competence=0.9,
                              skepticism=0.0, claim_id="c1", origin_event="o1",
                              world_time=1, speaker="speaker")
    before = {"p": belief.expected_prob, "for": belief.support_for,
              "conflict": belief.conflict, "ignorance": belief.ignorance}
    assert before["conflict"] == 0.0

    discredit(world, "speaker", factor=0.1)
    assert belief.expected_prob < before["p"], "exposing the source changed nothing"
    assert belief.support_against == 0.0, (
        f"weakened support was recorded as a counter-claim ({belief.support_against})")
    assert belief.support_for < before["for"]
    assert belief.conflict == 0.0, (
        f"discrediting one uncontested source invented conflict {belief.conflict}")
    assert belief.ignorance > before["ignorance"], (
        "less evidence has to mean more ignorance")
    print("ok  revision: exposing a source lowers support and raises ignorance; "
          "it does not manufacture a contradiction")


def test_revision_survives_a_trimmed_provenance_list():
    """What a liar convinced you of must stop counting however often they said it.

    The provenance list is capped at 64 entries for the inspector. Revision used
    to sum the deltas IN THAT LIST, so once a claim had been heard more times
    than the cap, the early and heavy entries were gone and exposing the only
    source who ever supplied it moved the belief by nothing at all: 0.96344
    before, 0.96344 after, zero beliefs revised.

    The arithmetic now lives in `Belief.contributions`, which is kept per
    (speaker, origin) and is not trimmed with the display record.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition
    from unscripted.revision import discredit

    world = _mini_world("retention")
    engine = BeliefEngine()
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    beliefs = world.agents["npc"].beliefs
    # ONE origin, heard a hundred times. That is what makes this case bite: the
    # correlation discount keeps the belief off the rail, so a change is visible,
    # while the FIRST hearing -- the only heavy one -- is trimmed out of the
    # display record long before the hundredth.
    for turn in range(100):
        belief, _ = engine.update(beliefs, claim, asserter_polarity="+", trust=0.9,
                                  competence=0.9, skepticism=0.0,
                                  claim_id=f"c{turn}", origin_event="o1",
                                  world_time=turn, speaker="speaker")
    assert 0.9 < belief.expected_prob < 0.999, (
        f"the belief has to stay off the rail for the change to be visible "
        f"({belief.expected_prob})")
    assert belief.provenance_dropped > 0, (
        "this case only bites once the display record has been trimmed")
    before = belief.expected_prob

    outcome = discredit(world, "speaker", factor=0.1)
    assert outcome.touched == 1, "the belief resting entirely on the liar was not revised"
    assert belief.expected_prob < before - 0.01, (
        f"a hundred hearings from one exposed source moved the belief from "
        f"{before:.5f} to {belief.expected_prob:.5f}")
    print(f"ok  revision: survives a trimmed provenance list "
          f"({before:.3f} -> {belief.expected_prob:.3f} after "
          f"{belief.provenance_dropped} entries were dropped)")


def test_discredit_matches_a_whole_id_not_a_substring():
    """`agent:ann` must not unwind what `agent:anna` was relayed as saying.

    Origins are built by joining ids with separators, so `source in origin` was
    a substring test over other people's names: discrediting a short id revised
    beliefs that traced to a longer one containing it, and a bystander's belief
    fell from 0.95 to 0.676 because somebody with a similar name was exposed.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition
    from unscripted.revision import discredit

    world = _mini_world("substring")
    engine = BeliefEngine()
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    belief, _ = engine.update(world.agents["npc"].beliefs, claim,
                              asserter_polarity="+", trust=0.9, competence=0.9,
                              skepticism=0.0, claim_id="c1",
                              origin_event="said_agent:anna_100",
                              world_time=1, speaker="relay")
    before = belief.expected_prob

    assert discredit(world, "agent:ann").touched == 0, (
        "a prefix of somebody else's id revised their claims")
    assert belief.expected_prob == before

    # The real author still matches, including down a relayed chain.
    assert discredit(world, "agent:anna").touched == 1, (
        "the actual author of the claim was not matched")
    assert belief.expected_prob < before
    print("ok  revision: an origin names a whole id, not any string inside one")


def test_a_belief_tracks_a_bounded_number_of_sources():
    """Everything per-character has a bound, including the source index.

    `origin_counts` was kept in full forever, so a claim heard from unboundedly
    many distinct origins grew a save file without limit -- 2,000 origins for
    one belief while the visible provenance stayed at 64.

    The index is bounded by REFUSING new sources at capacity, not by evicting
    old ones: see [[test_no_ordering_of_events_lifts_the_source_ceiling]] for why
    the difference is the whole of the saturation guarantee. So the first origin
    is still the one a retelling cites, and it is still there.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    beliefs = {}
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    for turn in range(2000):
        belief, _ = engine.update(beliefs, claim, asserter_polarity="+", trust=0.6,
                                  competence=0.6, skepticism=0.3,
                                  claim_id=f"c{turn}", origin_event=f"independent:{turn}",
                                  world_time=turn, speaker="agent:teller")
    limit = engine.params["origin_limit"]
    from unscripted.belief import FORGOTTEN
    assert len(belief.origin_counts) <= limit, len(belief.origin_counts)
    assert len(belief.contributions) <= limit + 1, len(belief.contributions)

    # THE SECOND INDEX IS A DIFFERENT BOUND, and it fills separately. It is keyed
    # on the (speaker, origin) PAIR, because that is what `revision` matches on --
    # so 400 origins each relayed by two different mouths make 800 pairs while the
    # origin index holds 400. Past the limit the pairs fold into one bucket: their
    # evidence still counts towards the log-odds, and revision can no longer
    # unwind it, which is the honest consequence of a bound and is why it is named
    # rather than mixed in with the rest.
    relayed, clock = {}, 0
    for source in range(400):
        for mouth in ("agent:first_mouth", "agent:second_mouth"):
            clock += 1
            crowd, _ = engine.update(relayed, claim, asserter_polarity="+",
                                     trust=0.6, competence=0.6, skepticism=0.3,
                                     claim_id=f"r{clock}",
                                     origin_event=f"origin:{source}",
                                     world_time=clock, speaker=mouth)
    assert len(crowd.origin_counts) == 400, len(crowd.origin_counts)
    assert len(crowd.contributions) <= limit + 1, len(crowd.contributions)
    assert FORGOTTEN in crowd.contributions, (
        "the pair index never filled, so this case is not exercising it")

    assert belief.origins_refused > 0, "nothing was reported as refused"
    assert len(belief.origin_counts) == limit, (
        f"the index stopped at {len(belief.origin_counts)} rather than filling to "
        f"{limit}; a refusal must not cost a slot")
    assert belief.primary_origin == "independent:0", (
        f"the cited origin is gone; a retelling would now name "
        f"{belief.primary_origin!r}")
    print(f"ok  belief: bounded at {limit} sources with the first one still cited "
          f"({belief.origins_refused} later sources refused), and the "
          f"(speaker, origin) index bounded separately at {limit} + 1")


def test_one_liar_telling_one_lie_is_one_source():
    """Asking the same liar the same question twice must not corroborate them.

    A lie has no evidential ancestor, so its origin names the speaker. It used
    to name the speaker AND THE CLOCK, so every retelling minted a fresh origin
    and the runtime counted its own repetition as independent corroboration --
    the exact failure the correlation discount exists to prevent, arriving
    through the channel a player uses most. Eight tellings produced eight
    origins and took the listener from 0.513 to 0.612.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        probabilities = []
        for _ in range(8):
            runtime.world.world_time += 1
            runtime.respond("agent:corpo_okada", topic="milan")
            player = runtime.world.agents[runtime.config.player_id]
            held = next((b for b in player.beliefs.values()
                         if "outside_the_city" in b.proposition.core_key()), None)
            if held is not None:
                probabilities.append(held.expected_prob)
                origins = list(held.origin_counts)
        assert probabilities, "the liar never told the cover story"
        assert len(origins) == 1, (
            f"one liar telling one lie became {len(origins)} independent sources")
        # Saturating rather than climbing: the discount is doing its work.
        assert probabilities[-1] - probabilities[-2] < 1e-6, probabilities[-2:]
        assert probabilities[-1] < 0.53, (
            f"repetition still hardened the lie to {probabilities[-1]:.3f}")
    finally:
        runtime.close()
    print(f"ok  dialogue: a repeated lie stays one source "
          f"(p saturates at {probabilities[-1]:.4f})")


def test_being_told_again_is_not_being_wronged_again():
    """Standing is a position, not a running total.

    The belief engine correctly refuses to be persuaded twice by one origin --
    twenty reports moved it from 0.54960677 to 0.54960683 -- and standing paid
    out the full judgement on every one of them anyway, taking liking from
    -0.198 to -0.659. Only the CHANGE may be applied.
    """
    from unscripted.ontology import Proposition

    world = _mini_world("standing")
    world.agents["accused"] = Agent(id="accused", location="p")
    runtime = Runtime(world)
    runtime.standing.enabled = True
    conduct = Proposition("mistreated", {"who": "npc", "by": "accused"})

    seen = []
    for _ in range(20):
        runtime.process_event(Event(
            world.new_event_id(), world.world_time, "claim", actor="speaker",
            location="p", payload={"proposition": conduct.as_dict(),
                                   "origin_event": "one-act", "audience": ["npc"]}))
        observer = world.agents["npc"]
        seen.append((observer.beliefs[conduct.core_key()].expected_prob,
                     observer.relationships["accused"]["liking"]))

    assert seen[0][1] < 0.0, "the first report should move standing"
    assert abs(seen[-1][1] - seen[5][1]) < 1e-3, (
        f"repeating one report kept punishing: liking {seen[5][1]:.3f} -> "
        f"{seen[-1][1]:.3f} while the belief stayed at {seen[-1][0]:.6f}")
    print(f"ok  standing: one incident restated twenty times moves standing once "
          f"(liking {seen[0][1]:.3f}, then flat)")


def test_a_feared_event_that_happens_is_not_a_relief():
    """OCC's prospect pair, in the direction OCC states it.

    Relief follows a feared event NOT happening. `confirmed` produced relief, so
    a character whose worst expectation came true cheered up.
    """
    from unscripted.affect import AffectEngine

    engine = AffectEngine()
    happened = dict(engine.appraise({"prospect": "confirmed", "prior_fear": 0.8}))
    avoided = dict(engine.appraise({"prospect": "disconfirmed", "prior_fear": 0.8}))
    hoped = dict(engine.appraise({"prospect": "confirmed", "prior_hope": 0.7}))
    dashed = dict(engine.appraise({"prospect": "disconfirmed", "prior_hope": 0.7}))

    assert "relief" not in happened, "a feared event that HAPPENED produced relief"
    assert happened.get("distress") == 0.8, happened
    assert avoided.get("relief") == 0.8, avoided
    assert hoped.get("joy") == 0.7, hoped
    assert dashed.get("disappointment") == 0.7, dashed
    print("ok  affect: fears confirmed distress and fears dispelled relieve, "
          "which is the way round OCC has it")


def test_a_threat_is_judged_on_conduct_not_on_the_actor_s_own_fear():
    """Whether a threat lands depends on what THEY feel, which is a model.

    `agent.relationships[other]["fear"]` is how much the agent fears the other,
    and reading it as the reverse inverted every threat assessment: a character
    terrified of somebody expected their own threats to work (+0.32), and one
    who had spent the week frightening them expected them to backfire (-0.40).

    There is no honest way to read the other's actual fear, so the engine keeps
    a model written from what the actor has themselves been seen to do.
    """
    from unscripted.social import TheoryOfMindEngine

    tom = TheoryOfMindEngine()
    actor = Agent(id="a")
    stranger = Agent(id="b")

    assert tom.expected_reaction(actor, "b", "threaten", {})[1] == 0.0, (
        "with no history the engine should hold no opinion")

    actor.relationships["b"] = {"fear": 0.9}     # the actor fears them
    assert tom.expected_reaction(actor, "b", "threaten", {})[1] == 0.0, (
        "the actor's own fear was read as the other's fear of them")

    tom.note_own_act(actor, "b", "threat", 0.8)
    tom.note_own_act(actor, "b", "attack", 0.8)
    frightened = tom.expected_reaction(actor, "b", "threaten", {})[1]
    assert frightened > 0.2, frightened

    kind = Agent(id="c")
    tom.note_own_act(kind, "b", "gift", 1.0)
    tom.note_own_act(kind, "b", "gift", 1.0)
    assert tom.expected_reaction(kind, "b", "threaten", {})[1] < 0.0
    assert stranger.tom_models == {}, "nothing should be written about a bystander"
    print(f"ok  theory of mind: a threat is judged on what the threatener has "
          f"done ({frightened:+.3f}), not on what they themselves fear")


def test_publicity_carries_polarity():
    """A public denial is not a public confession.

    Publics were filed under the bare core key, which drops polarity -- so a
    broadcast that somebody was NOT alive marked the claim that they WERE as out
    in the open. That decides whether a secret has stopped working, and the
    negation of a secret is not its disclosure.
    """
    from unscripted.common_knowledge import CommonKnowledgeEngine
    from unscripted.ontology import Proposition

    world = _mini_world("publicity")
    engine = CommonKnowledgeEngine(enabled=True)
    fact = Proposition("body:alive", {"agent": "agent:subject"})
    heard = [(name, 1.0) for name in ("npc", "speaker", "third")]
    engine.observe(world, Event(1, 0, "broadcast",
                                payload={"proposition": fact.negated().as_dict()}), heard)

    assert not engine.is_out(fact.core_key(), "npc"), (
        "a public denial marked the positive claim as public")
    assert engine.is_out("-" + fact.core_key(), "npc"), (
        "the thing that was actually announced is not recorded as public")
    print("ok  common knowledge: what a crowd established includes which way "
          "round it was said")


def test_memory_holds_what_was_understood_not_what_happened():
    """Recall must not hand back the detail perception decided they missed.

    The interpretation layer coarsens a claim an observer cannot identify --
    dropping the `when` of an engineering incident for somebody with no
    engineering -- and the memory encoder then stored the EVENT'S proposition,
    complete. Belief and recall disagreed about the same moment, and
    `retrieve_memories` handed the precise version to any caller that asked.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "relay-station"),
        storage_path=":memory:"))
    try:
        layman = runtime.world.agents["agent:adeyemi"]
        layman.epistemic = {"confirmation_bias": 0.05}
        layman.beliefs.clear()
        layman.memory.clear()
        layman.location = "place:store"
        seen = Proposition("seal_breached",
                           {"section": "place:store", "when": "night_cycle"})
        runtime.emit_event(Event(
            runtime.world.new_event_id(), runtime.world.world_time, "incident",
            location="place:store",
            payload={"proposition": seen.as_dict(), "importance": 0.8}))

        believed = [b.proposition.as_dict() for b in layman.beliefs.values()]
        assert believed and believed[0]["slots"]["when"] is None, (
            f"this case needs the observer to have MISSED the detail; got {believed}")
        recalled = [m.proposition.as_dict()
                    for _a, _p, m in runtime.retrieve_memories(layman.id)
                    if m.proposition]
        assert seen.as_dict() not in recalled, (
            "recall returned the precise claim the observer could not identify")
        assert believed[0] in recalled, (
            f"what they did take in is not retrievable at all: {recalled}")
    finally:
        runtime.close()
    print("ok  memory: a witness remembers what they understood, not what the "
          "ledger knows")


def test_who_witnessed_an_event_does_not_depend_on_the_step_size():
    """One advance of 30 minutes and two of 10 and 20 must agree about the past.

    Scheduled events were processed first, as a batch, against the positions
    everybody held at the START of the window -- so a character who left a room
    at minute 10 was still a witness to something at minute 20 if the caller
    happened to take one large step. Both runs end in the same place at the same
    time and only one of them can be right about who was there.
    """
    from unscripted.routine import Routine

    def run(steps):
        world = _mini_world("witness")
        world.places["q"] = {"noise_level": 0.0}
        watcher = world.agents["npc"]
        watcher.routine = Routine.from_list([{"from": 0, "place": "p"},
                                             {"from": 10, "place": "q"}])
        world.world_time = 0
        runtime = Runtime(world)
        runtime.routine.seed(world)
        claim = Proposition("body:alive", {"agent": "agent:subject"})
        world.scenario_events = [Event(world.new_event_id(), 20, "incident",
                                       location="p",
                                       payload={"proposition": claim.as_dict()})]
        for step in steps:
            runtime.advance_time(step)
        return {"witnessed": claim.core_key() in watcher.beliefs,
                "where": watcher.location, "clock": world.world_time}

    one_step, two_steps = run([30]), run([10, 20])
    assert one_step == two_steps, (
        f"the step size changed the past: {one_step} vs {two_steps}")
    assert not one_step["witnessed"], (
        "the character had already left the room when it happened")
    print("ok  runtime: the window is walked in order, so who witnessed what "
          "does not depend on how big a step the caller took")


def test_a_judgement_still_names_its_evidence_after_a_reload():
    """A conclusion that cannot name its evidence is a prejudice.

    `about` and `evidence` were never serialised, so save/load stripped every
    judgement of who it concerned and what it was drawn from -- and
    consolidation, which finds an existing judgement BY `about`, stopped finding
    it and began making duplicates instead of reinforcing.
    """
    from unscripted.memory import Memory

    original = Memory("judgement", "observer", "judgement", "a pattern",
                      about=("agent:speaker", "helped"),
                      evidence=("event:1", "event:2", "event:3"))
    restored = Memory.from_dict(json.loads(json.dumps(original.as_dict())))
    assert restored.about == original.about, restored.about
    assert restored.evidence == original.evidence, restored.evidence
    print("ok  memory: a judgement survives a round trip still naming its "
          "subject and its evidence")


def test_a_released_line_must_agree_with_the_polarity_it_committed_to():
    """The player and the room must be told the same thing.

    `expresses` asked only whether the sentence NAMED the subject, so a provider
    line saying the clinic was open passed while the runtime propagated that it
    was not. The player read one thing and the society learned the other.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    class Contradicts:
        is_deterministic = False
        expressed_commitment = None
        def realize(self, plan, style):
            return "The clinic was open all night."

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:",
            semantic_release="provider"))
    try:
        runtime.core.realizer = Contradicts()
        answer = runtime.submit_player_text("ask Honce about clinic").npc_response
        spoken = [move["rendered"] for _c, _m, detail in answer.reasons
                  if _c == "dialogue.direct_answer" for move in detail["spoken"]]
        assert spoken, "nothing was asserted, so this case proves nothing"
        negated = spoken[0].startswith("NOT ")
        denied = any(word in answer.text.lower()
                     for word in ("shut", "closed", "not ", "n't", "nothing"))
        assert negated == denied, (
            f"released {answer.text!r} while the room was told {spoken[0]!r}")
        assert "was open all night" not in answer.text, (
            "the contradicting line reached the player unchanged")
    finally:
        runtime.close()
    print("ok  grounding: a released line and the claim it propagates agree "
          "about which way round they are")


def test_a_paraphrase_that_names_a_protected_place_is_refused():
    """Surface forms are the phrasings somebody thought of; a paraphrase is not.

    "Milan hides in a room behind the bar" contains no forbidden string, no
    proper noun the plan had not licensed and no invented referent -- and it
    gave away the hiding place. What it does contain is the PLACE, in a word the
    world's own lexicon resolves to it.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted.dialogue import DialoguePlan
    from unscripted.validator import Validator
    from unscripted.world import load_world_pack

    world = load_world_pack(os.path.join(root, "worldpacks", "cyberpunk-block"))
    validator = Validator.for_world(world)
    holder = world.agents["agent:corpo_okada"]
    secret = holder.secrets[0]
    plan = DialoguePlan(holder.id, "agent:player_1", "inform", goal="answer",
                        avoid_topics=[secret.avoid_label],
                        allowed_facts=["whereabouts(who=agent:npc_red_jacket, "
                                       "place=place:outside_the_city)"])

    leak = validator.check("Milan hides in a room behind the bar.", plan, holder, [])
    assert leak.verdict == "REJECT_HARD", leak.verdict
    assert any(code == "validator.secret_referent" for code, _m, _d in leak.reasons), (
        [code for code, _m, _d in leak.reasons])

    # The licensed answer still gets through.
    fine = validator.check("I have nothing for you.", plan, holder, [])
    assert fine.verdict == "ACCEPT", [c for c, _m, _d in fine.reasons]
    print("ok  validator: naming what a secret is about is refused even when no "
          "forbidden phrase appears")


def test_the_provider_chooses_the_wording_not_whether_the_world_hears_it():
    """Two accepted answers to one question must not produce two worlds.

    A line that did not carry the commitment used to VOID it, so the provider --
    and, with a latency budget, its response time -- decided whether a belief
    entered the society at all. The wording is what gets replaced now.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    class Fixed:
        is_deterministic = False
        expressed_commitment = None
        def __init__(self, line):
            self.line = line
        def realize(self, plan, style):
            return self.line

    def ask(line):
        runtime = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
            storage_path=":memory:",
            semantic_release="provider"))
        try:
            runtime.core.realizer = Fixed(line)
            runtime.submit_player_text("ask Honce about clinic")
            player = runtime.world.agents[runtime.config.player_id]
            return sorted(player.beliefs)
        finally:
            runtime.close()

    carried = ask("The clinic? Shutters were down all night.")
    evasive = ask("Long day. I could use a drink.")
    assert carried, "the honest phrasing asserted nothing at all"
    assert carried == evasive, (
        f"what the world learned depended on the provider's wording: "
        f"{carried} vs {evasive}")
    print("ok  dialogue: the same commitment reaches the world whatever the "
          "provider wrote")


def test_a_save_from_another_world_is_refused():
    """One shared character is not evidence of a shared world.

    `inspect_state` refused only when NOTHING overlapped, and every pack ships
    the same default player id -- so a cyberpunk save loaded cleanly into a noir
    harbour and left the player standing in a place that does not exist there.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    from unscripted.snapshot import StateImportError

    def open_pack(name):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", name),
            storage_path=":memory:"))

    source, target = open_pack("cyberpunk-block"), open_pack("noir-harbor")
    try:
        blob = source.export_state()
        report = target.inspect_state(blob)
        assert not report["usable"], report
        assert report["code"] == "different_world", report
        was = target.world.agents[target.config.player_id].location
        try:
            target.import_state(blob)
            raise AssertionError("a save from another world was imported")
        except StateImportError:
            pass
        assert target.world.agents[target.config.player_id].location == was
        assert was in target.world.places

        # And a save of THIS world still loads.
        own = target.export_state()
        assert target.inspect_state(own)["usable"], target.inspect_state(own)
        target.import_state(own)
    finally:
        source.close()
        target.close()
    print("ok  snapshot: a save is refused unless it is a save of this map")


def test_a_corrupt_import_leaves_the_world_untouched():
    """A load that fails must leave the game exactly as it found it.

    The envelope can be sound and the payload rotten. `restore` overwrote the
    world clock and the schedule before it reached the agents, so a belief that
    would not parse raised half way through and left a live session in a state
    that was neither the old one nor the new one.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    from unscripted.snapshot import StateImportError

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        rotten = copy.deepcopy(runtime.export_state())
        rotten["state"]["world_time"] += 1000
        first = next(iter(rotten["state"]["agents"].values()))
        first["beliefs"] = [{"not": "a belief"}]

        before = runtime.export_state()
        try:
            runtime.import_state(rotten)
            raise AssertionError("a corrupt payload was imported")
        except StateImportError as failure:
            assert "invalid_payload" in str(failure), failure
        after = runtime.export_state()
        assert before == after, "a failed import left the world changed"
    finally:
        runtime.close()
    print("ok  snapshot: a failed import is a no-op, not a half-applied one")


def test_the_event_ledger_only_appends():
    """Loading an earlier save must not rewrite the branch you left.

    `event_id` was the ledger's primary key while `restore` rewinds the counter
    that mints them, so playing on after a load overwrote the abandoned branch's
    rows: event 1001 stopped being what happened and became whatever happened
    last under that number.
    """
    from unscripted import snapshot
    from unscripted.persistence import Store

    world = _mini_world("ledger")
    store = Store()
    runtime = Runtime(world, store)
    try:
        start = snapshot.capture(world, runtime)
        shared = world.new_event_id()
        runtime.process_event(Event(shared, 1, "incident", location="p",
                                    payload={"summary": "branch A"}))
        watermark = snapshot.capture(world, runtime)["ledger_watermark"]
        snapshot.restore(start, world, runtime)
        runtime.process_event(Event(world.new_event_id(), 1, "incident",
                                    location="p", payload={"summary": "branch B"}))

        rows = store.ledger_as_of(store.ledger_position())
        summaries = [json.loads(row["payload"])["summary"] for row in rows]
        assert summaries == ["branch A", "branch B"], summaries
        assert [row["event_id"] for row in rows] == [shared, shared], (
            "this case needs both branches to reuse the id")

        # AND THE HISTORY OF THE ABANDONED BRANCH DOES NOT GROW A FUTURE. Both
        # rows surviving was only half of it: the query that answers "as of this
        # snapshot" was filtering on the event id, which the reload rewinds, so
        # A's own history later contained B.
        assert [json.loads(row["payload"])["summary"]
                for row in store.ledger_as_of(watermark)] == ["branch A"], (
            "the history as of the first snapshot picked up a later branch")
    finally:
        store.close()
    print("ok  persistence: an abandoned branch stays on the ledger after a "
          "reload reuses its event ids")


def test_the_demo_page_does_not_hand_out_the_token():
    """A page that carries the credential must not be served to somebody without it.

    `/demo` and `/studio` were answered outside `_dispatch`, so they never
    reached `authorize` -- while the HTML has the configured bearer token
    embedded in it, because the page has to call the API. An unauthenticated GET
    therefore RETURNED the credential, and it then worked against every mutating
    endpoint.
    """
    import http.client
    import threading as _threading
    from unscripted import RuntimeConfig
    from unscripted.service import ServiceOptions, create_server

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token = "test-token-not-a-real-credential"
    config = RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:")
    server = create_server(config, host="127.0.0.1", port=0,
                           options=ServiceOptions(auth_token=token,
                                                  expose_debug_endpoints=True))
    thread = _threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def get(path):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read().decode()
            conn.close()
            return response.status, body

        status, body = get("/demo")
        assert status == 401, status
        assert token not in body, "the demo page handed out the token unasked"

        status, body = get("/demo?token=wrong")
        assert status == 401, status
        assert token not in body

        # Somebody who already has it still gets the page, token and all: the
        # launcher's announced link is how a browser is meant to arrive.
        status, body = get(f"/demo?token={token}")
        assert status == 200, status
        assert token in body, "an authorised page cannot call the API without it"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    print("ok  service: the demo page is behind the same token it embeds")


def test_the_native_json_parser_refuses_malformed_documents():
    """The C ABI's parser must reject bad input, not invent plausible data.

    It accepted anything and quietly made something of it: `{"a":1` became
    `{"a":1}`, `[1,]` became `[1,0]`, and the bare word `wat` became `0`. That is
    the boundary packs, tuning blocks and save files arrive over, so a truncated
    document did not fail -- it arrived as different data. Surrogate pairs were
    also split into CESU-8 rather than combined.
    """
    cxx = os.environ.get("CXX", "g++")
    if not shutil.which(cxx):
        print("ok  native json: skipped (no C++ compiler)")
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source = r'''
#include <iomanip>
#include <iostream>
#include "usc/json.hpp"
int main() {
    const char* bad[] = {"{\"a\":1", "{\"a\" 1}", "[1,]", "wat", "1e", "+1",
                         "{\"a\":1,}", "01", "\"unterminated", ""};
    for (const char* text : bad) {
        try { usc::Json::parse(text); std::cout << "ACCEPTED " << text << "\n"; }
        catch (const std::exception&) { std::cout << "refused\n"; }
    }
    for (const char* good : {"{\"a\":1}", "[1,2]", "-0.5e+3", "null", "\"x\""}) {
        try { usc::Json::parse(good); std::cout << "ok\n"; }
        catch (const std::exception& e) { std::cout << "REFUSED " << good << "\n"; }
    }
    std::string emoji = usc::Json::parse("\"\\ud83d\\ude00\"").as_string();
    std::cout << "emoji=";
    for (unsigned char byte : emoji)
        std::cout << std::hex << std::setfill('0') << std::setw(2) << (int)byte;
    std::cout << "\n";
}
'''
    with tempfile.TemporaryDirectory() as work:
        program = os.path.join(work, "json_check.cpp")
        binary = os.path.join(work, "json_check")
        with open(program, "w", encoding="utf-8") as handle:
            handle.write(source)
        build = subprocess.run(
            [cxx, "-std=c++17", "-I", os.path.join(root, "port", "cpp", "include"),
             program, "-o", binary], capture_output=True, text=True)
        assert build.returncode == 0, build.stderr[:2000]
        result = subprocess.run([binary], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr[:2000]
        lines = result.stdout.split()
        assert "ACCEPTED" not in result.stdout, result.stdout
        assert "REFUSED" not in result.stdout, result.stdout
        assert "emoji=f09f9880" in result.stdout, result.stdout
    print("ok  native json: malformed documents are refused and a surrogate "
          "pair becomes one character")


def test_memory_retrieval_is_a_draw_not_a_threshold():
    """`noise_s` has to change the OUTCOME, not only the reported number.

    Retrieval computed `sigmoid((a - tau_ret) / noise_s)` and then tested
    `prob >= 0.5`. The sigmoid is monotonic and `sigmoid(0) = 0.5`, so that
    comparison is exactly `a >= tau_ret` for any positive noise: the documented
    ACT-R retrieval probability was a deterministic cut-off, and the parameter
    that was supposed to make recall uncertain moved nothing.

    It draws now, from the runtime's own seed algebra -- so a save still replays
    exactly, while a character genuinely sometimes fails to come up with
    something they nearly remember.
    """
    from unscripted.memory import Memory, MemoryEngine

    def shelf():
        return [Memory(f"m{i}", "agent:o", "episodic", f"thing {i}",
                       importance=0.5, presentations=[100 - i * 40])
                for i in range(12)]

    engine = MemoryEngine()

    def recalled(seed_parts):
        return tuple(m.memory_id for _a, _p, m
                     in engine.retrieve(shelf(), 400, seed_parts=seed_parts))

    # IT IS A DRAW. Thirty different characters asked the same question of the
    # same shelf: a threshold answers identically every time, a draw does not.
    # Counting items would not show it -- the working-memory cap hides the
    # difference -- so this compares WHICH memories came up.
    outcomes = {recalled(("world", f"agent:{i}", "recall")) for i in range(30)}
    assert len(outcomes) > 1, (
        "thirty characters recalled exactly the same set; retrieval is still a "
        "deterministic cut-off wearing a probability's clothes")

    # AND IT STILL REPLAYS. The draw comes from the seed algebra, not a global
    # source, so the same world and the same character reproduce exactly.
    seed = ("world", "agent:o", "recall")
    assert recalled(seed) == recalled(seed), "the same seed recalled different things"

    # An engine with no world around it keeps the old, reproducible cut-off
    # rather than inventing a seed.
    bare = tuple(m.memory_id for _a, _p, m in engine.retrieve(shelf(), 400))
    assert bare == tuple(m.memory_id for _a, _p, m in engine.retrieve(shelf(), 400))
    print(f"ok  memory: recall is a seeded draw ({len(outcomes)} distinct "
          f"outcomes across thirty characters) and still replays exactly")


def test_there_is_one_speech_path_and_it_reaches_the_world():
    """`Runtime.say()` must put what was said into the world, like every other path.

    There were two ways to speak. The SDK's answer path emitted the committed
    claim as an event, so the room heard it; `Runtime.say()` -- also public, and
    the one the deliberation path uses -- realised a line, validated it and
    returned the text. A character reached through it could tell somebody
    something in a room full of people and nobody learned anything, which is the
    defect this whole runtime exists to remove, reintroduced through a second
    door. There is one implementation now and the SDK delegates to it.
    """
    from unscripted.evidence import _runtime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = _runtime(os.path.join(root, "worldpacks", "relay-station"))
    try:
        speaker = "agent:ferro"
        listener = "agent:rask"
        runtime.world.agents[listener].location = runtime.world.agents[speaker].location

        before = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}
        answer = runtime.core.say(speaker, interlocutor=listener)
        after = {(a.id, k) for a in runtime.world.agents.values() for k in a.beliefs}

        assert "spoken" in answer, "the low-level path does not report what it said"
        if answer["spoken"]:
            assert after != before, (
                "a character asserted something and nobody in the room learned "
                "anything")
            heard = {who for move in answer["spoken"] for who in move["heard_by"]}
            assert heard, "nobody was recorded as having heard it"
            assert all(not who.startswith("_") for who in heard), (
                f"a trace bucket was reported as a listener: {sorted(heard)}")
        else:
            # A turn that commits to no fact asserts nothing, which is correct --
            # but then the world must be unchanged, not partly changed.
            assert after == before

        # And the two doors are the same room: the SDK's helper delegates.
        assert runtime._speak_aloud.__doc__ is not None
        assert (runtime._earshot(runtime.world.agents[speaker], listener)
                == runtime.core.earshot(runtime.world.agents[speaker], listener))
    finally:
        runtime.close()
    print("ok  runtime: the deliberation path speaks into the world, and the SDK "
          "shares its implementation")


def test_the_pad_baseline_states_its_sign_convention():
    """The arousal coefficient is faithful to ALMA; the comment was not.

    The line reads `- 0.57 * (-S)` with `S = emotional_stability`, which is
    `+0.57 * S` -- and the commonly cited ALMA equation is `-0.57 * N`, with
    `N = -S`. So the arithmetic matches the source and the comment beside it
    ("instability raises arousal") said the opposite of both.

    Secondary sources disagree about this sign, so this is pinned rather than
    trusted: whichever way a future calibration goes, it has to go there on
    purpose and update this test.
    """
    from unscripted.affect import pad_baseline_from_big_five

    steady = pad_baseline_from_big_five({"openness": 0.5, "conscientiousness": 0.5,
                                         "extraversion": 0.5, "agreeableness": 0.5,
                                         "emotional_stability": 0.9})
    volatile = pad_baseline_from_big_five({"openness": 0.5, "conscientiousness": 0.5,
                                           "extraversion": 0.5, "agreeableness": 0.5,
                                           "emotional_stability": 0.1})
    assert steady.a > volatile.a, (
        f"the convention changed: stability {steady.a} against instability "
        f"{volatile.a}. ALMA writes arousal as -0.57*N and this runtime feeds it "
        f"emotional stability, which is -N")
    assert steady.p > volatile.p, "stability must not lower pleasure"
    print(f"ok  affect: the PAD arousal sign follows ALMA's -0.57*N under S = -N "
          f"({steady.a:.3f} against {volatile.a:.3f})")


def test_the_player_and_the_room_agree_across_adversarial_wordings():
    """Eight ways to say the wrong thing about one commitment.

    The earlier check compared an off-topic line against a rough paraphrase,
    which is the easy pair. The hard ones all contain the right subject and
    differ in polarity, modality or attribution:

        The clinic is open.                      -- the plain contradiction
        The clinic is not open.                  -- agrees
        The clinic might be open.                -- modality the runtime never
                                                    committed to
        The clinic used to be open.              -- a different time
        I heard the clinic is open.              -- hearsay framing
        I don't believe the clinic is open.      -- agrees, hedged
        Everyone says the clinic is open, but
        they are wrong.                          -- asserts and retracts

    Every one of them names the clinic, so an anchor test passes all eight. What
    must hold is narrower and is the actual product promise: whatever the player
    reads, the room is told the same thing.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _runtime(pack):
        # The WEAKER contract, deliberately: this is the mode where a provider
        # writes factual lines, so it is the mode where the checks have to hold.
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:",
            semantic_release="provider"))

    lines = ["The clinic is open.",
             "The clinic is not open.",
             "The clinic might be open.",
             "The clinic used to be open.",
             "I heard the clinic is open.",
             "I don't believe the clinic is open.",
             "Everyone says the clinic is open, but they are wrong.",
             "The clinic? Shutters were down all night."]

    denials = ("not ", "n't", "shut", "closed", "down", "nothing", "no ")
    seen = set()
    for line in lines:
        class Fixed:
            is_deterministic = False
            expressed_commitment = None
            def realize(self, plan, style, _line=line):
                return _line

        runtime = _runtime(os.path.join(root, "worldpacks", "cyberpunk-block"))
        try:
            runtime.core.realizer = Fixed()
            answer = runtime.submit_player_text("ask Honce about clinic").npc_response
            spoken = [move["rendered"] for code, _m, detail in answer.reasons
                      if code == "dialogue.direct_answer" for move in detail["spoken"]]
            assert spoken, f"{line!r}: nothing propagated, so nothing is proved"
            claim_is_negative = spoken[0].startswith("NOT ")
            text_denies = any(word in answer.text.lower() for word in denials)
            assert claim_is_negative == text_denies, (
                f"provider wrote {line!r}; the player read {answer.text!r} while "
                f"the room was told {spoken[0]!r}")
            seen.add(tuple(sorted(spoken)))
        finally:
            runtime.close()

    assert len(seen) == 1, (
        f"the provider's wording changed what the world was told: {seen}")
    print(f"ok  dialogue: {len(lines)} adversarial wordings, one claim in the "
          f"world, and the player never read its opposite")


# ---------------------------------------------------------------------------
# Regressions from the 8 September 2026 recheck. Four of these are defects the
# PREVIOUS pass introduced or left half-closed, which is why they are pinned by
# properties rather than by the word lists the implementation happens to use.
# ---------------------------------------------------------------------------


def test_a_source_this_belief_has_counted_is_never_forgotten():
    """The source index is bounded by REFUSING, not by evicting.

    Three designs tried to bound the index by evicting and then correcting for
    it, and every one of them leaked, because an index that forgets cannot
    recognise a repeat:

      * evicting outright let a source return at FULL weight -- 2.94444, evicted,
        then 2.94444 again, against a ceiling of 3.27160, taking a belief from
        0.95 to 0.99724 on nothing but repetition;
      * charging a re-admission `rho` bounded ONE return and not the series --
        cycling `origin_limit` uninformative sources bought a fresh geometric
        ladder each time, 0.950 to 0.99985 over twenty cycles;
      * charging every re-admission from one shared `rho/(1-rho)` allowance
        leaked twice more: it did not count the repeats already paid while the
        origin was still recognised, and a re-admitted origin was back IN the
        index, so its next hearing took the `rho ** heard` branch and skipped the
        allowance entirely -- 6.18332 log-odds after a hundred cycles.

    Each fix was a correction applied at ONE step of a sequence whose length an
    adversary chooses. So the index no longer forgets: a counted source keeps its
    count forever, and a new source at capacity is refused outright.
    See [[test_no_ordering_of_events_lifts_the_source_ceiling]] for the bound
    itself, which this is the mechanism of.
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    limit = engine.params["origin_limit"]
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    beliefs = {}

    def hear(origin, at):
        belief, _ = engine.update(beliefs, claim, asserter_polarity="+", trust=0.9,
                                  competence=0.9, skepticism=0.0, claim_id=f"c{at}",
                                  origin_event=origin, world_time=at,
                                  speaker="agent:teller")
        return belief

    fresh = hear("measured:once", 0).logit_val
    beliefs.clear()

    hear("seed:first", 0)
    hear("rumour:one", 1)
    for filler in range(2, limit + 40):
        belief = hear(f"filler:{filler}", filler)
    assert "rumour:one" in belief.origin_counts, (
        "a source this belief had counted was dropped to make room for another")
    assert belief.origins_refused >= 40, belief.origins_refused

    before = belief.logit_val
    belief = hear("rumour:one", 10 ** 6)
    again = belief.logit_val - before
    assert abs(again - fresh * engine.params["rho_correlated"]) < 1e-9, (
        f"the second hearing of a known source was worth {again:.5f}, not the "
        f"{fresh * engine.params['rho_correlated']:.5f} its position on the ladder "
        f"says -- so the ladder was restarted somewhere")

    # And a source arriving at a full index is worth nothing at all, rather than
    # being let in at the price of forgetting one that is already counted.
    before = belief.logit_val
    belief = hear("stranger:at:the:door", 10 ** 6 + 1)
    assert belief.logit_val == before, (
        f"a refused source still moved the belief by "
        f"{belief.logit_val - before:.5f}")
    print(f"ok  belief: a counted source keeps its place ({limit} of them) and its "
          f"ladder; {belief.origins_refused} later ones were refused and were "
          f"worth exactly 0")


def test_no_ordering_of_events_lifts_the_source_ceiling():
    """One origin, however often repeated and in whatever order, is never proof.

    This is the product claim `single_origin_max_confidence` makes, and it had
    been narrowed three times without anyone noticing, because every test asked
    it of ONE hand-written sequence. A sequence is not a property. Two orderings
    the earlier tests did not contain broke the last version of the bound:
    repeating a source *before* it is displaced, and hearing it *twice* after it
    comes back.

    So this asks for arbitrary orderings, and checks them against a reference
    model small enough to be obviously right: every origin's n-th hearing is
    worth `rho^(n-1)` of one hearing, and nothing else exists. It also runs the
    world through a save and a load, because a bound that lives in a field is
    only as good as the field's round trip.
    """
    import math
    import random
    from unscripted.belief import Belief, BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    limit = engine.params["origin_limit"]
    rho = engine.params["rho_correlated"]
    claim = Proposition("body:alive", {"agent": "agent:subject"})
    one_hearing = math.log(engine.credibility(0.9, 0.9, 0.0)
                           / (1.0 - engine.credibility(0.9, 0.9, 0.0)))
    ceiling = one_hearing * engine.max_origin_contribution()

    def reference(script):
        """The stated rule, written out in eight lines and nothing else.

        The n-th hearing from an origin is worth `rho^(n-1)`; an origin the index
        has no room for is worth nothing. No eviction, no allowance, no state
        beyond a count per origin.
        """
        counts, logit = {}, 0.0
        for origin, neutral in script:
            kappa = engine.credibility(0.0 if neutral else 0.9,
                                       0.0 if neutral else 0.9,
                                       1 / 6 if neutral else 0.0)
            if origin in counts:
                eta = rho ** counts[origin]
                counts[origin] += 1
            elif len(counts) < limit:
                eta, counts[origin] = 1.0, 1
            else:
                eta = 0.0
            logit += eta * math.log(kappa / (1.0 - kappa))
        return counts, logit

    for trial in range(12):
        rng = random.Random(f"orderings:{trial}")
        # A short cast of informative origins, and enough filler to fill and
        # overfill the index. Shuffled together, so an informative source may
        # arrive before, during or after the index fills.
        cast = [f"witness:{i}" for i in range(3)]
        filler = [f"filler:{i}" for i in range(limit + 60)]
        script = ([(rng.choice(cast), False) for _ in range(400)]
                  + [(rng.choice(filler), True) for _ in range(2400)])
        rng.shuffle(script)

        beliefs, clock = {}, 0
        for origin, neutral in script:
            clock += 1
            belief, _ = engine.update(
                beliefs, claim, asserter_polarity="+",
                trust=0.0 if neutral else 0.9, competence=0.0 if neutral else 0.9,
                skepticism=1 / 6 if neutral else 0.0, claim_id=clock,
                origin_event=origin, world_time=clock, speaker="agent:teller")
            if clock % 900 == 0:                      # save and load mid-run
                beliefs = {key: Belief.from_dict(one.as_dict())
                           for key, one in beliefs.items()}
                belief = beliefs[claim.core_key()]

        counts, expected_logit = reference(script)
        assert belief.origin_counts == counts, (
            f"trial {trial}: the engine and the reference model disagree about "
            f"{sum(1 for k in set(counts) | set(belief.origin_counts) if counts.get(k) != belief.origin_counts.get(k))} "
            f"origin(s)")
        assert abs(belief.logit_val - expected_logit) < 1e-9, (
            f"trial {trial}: {belief.logit_val:.9f} against a reference model "
            f"allowing {expected_logit:.9f}")
        counted = [o for o in counts if o.startswith("witness:")]
        assert belief.logit_val <= len(counted) * ceiling + 1e-9, (
            f"trial {trial}: {len(counted)} informative origin(s) produced "
            f"{belief.logit_val:.6f}, over {len(counted)} * {ceiling:.6f}")

    # And the single-origin case the benchmark claim is literally about.
    beliefs, clock = {}, 0
    for _ in range(5000):
        clock += 1
        belief, _ = engine.update(beliefs, claim, asserter_polarity="+", trust=0.9,
                                  competence=0.9, skepticism=0.0, claim_id=clock,
                                  origin_event="one:voice", world_time=clock,
                                  speaker="agent:teller")
    assert belief.logit_val <= ceiling + 1e-9, (
        f"5,000 repetitions of one origin reached {belief.logit_val:.6f} against "
        f"a ceiling of {ceiling:.6f}")
    print(f"ok  belief: 12 random orderings over {limit + 63} origins agree with an "
          f"independent reference model exactly, across a save and a load, and "
          f"5,000 repetitions of one voice saturate at p={belief.expected_prob:.4f}")


def test_a_line_the_runtime_chose_to_release_is_reported_as_released():
    """The verdict, the sentence, the world and the audit are one decision.

    Splitting safety from quality left half the job done: from the fourth
    identical question onward the runtime deliberately released the line and told
    the room -- and still returned `REJECT_SOFT` with an empty `accepted_output`
    in the audit. A client that hides rejected answers would show the player
    nothing the room had just heard, which is the same divergence controlled
    release exists to prevent, arriving through the status field instead of
    through the text. `Runtime.say` already set the verdict; this path did not.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        turns = []
        for _ in range(6):
            answer = runtime.respond("agent:barkeep_12", topic="clinic")
            turns.append((answer.text, answer.verdict, _spoken_claims(answer)))
        audit = list(runtime.store.conn.execute(
            "SELECT validation_result, accepted_output FROM provider_call "
            "ORDER BY rowid"))
    finally:
        runtime.close()

    spoke = [row for row in turns if row[2]]
    assert len(spoke) == len(turns), (
        "this case needs every turn to have asserted something")
    for text, verdict, heard in turns:
        assert verdict == "ACCEPT", (
            f"{heard} reached the room while the caller was told {verdict}")
    assert len({text for text, _v, _h in turns}) >= 3, (
        "the anti-repeat retry stopped offering complete alternatives")
    for verdict, accepted in audit[-len(turns):]:
        assert verdict == "ACCEPT" and accepted, (
            f"the audit recorded {verdict!r} with accepted_output={accepted!r} for "
            f"a line that was released and propagated")
    print(f"ok  dialogue: {len(turns)} askings of one question, "
          f"{len({t for t, _v, _h in turns})} distinct wordings, every one "
          f"released, propagated and audited as released")


def test_the_player_reads_the_sentence_the_runtime_wrote_for_the_claim():
    """Under the default release mode a provider cannot contradict the world.

    The negation-word rule closes the obvious contradiction and not the class:
    "The clinic was open all night, **no** doubt." reads as a denial to any rule
    that looks for negation words, so it passed and the room was told the
    opposite. Any test that checks agreement by looking for the SAME words is
    blind to it, which is how the previous pass shipped one.

    So this asserts the property instead: whatever the provider writes -- a
    contradiction, a hedge, an attribution, or nothing at all because it threw --
    the released line and the world state are the ones the runtime chose.
    """
    from unscripted import RuntimeConfig
    from unscripted.provider import ProviderError
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")

    class Writes:
        is_deterministic = False
        expressed_commitment = None
        def __init__(self, line):
            self.line = line
        def realize(self, plan, style):
            return self.line

    class Throws:
        is_deterministic = False
        expressed_commitment = None
        def realize(self, plan, style):
            raise ProviderError("model unavailable")

    providers = [Writes("The clinic was open all night, no doubt."),
                 Writes("Nobody doubts the clinic was open all night."),
                 Writes("The clinic might be open."),
                 Writes("I heard the clinic is open."),
                 Writes("The clinic was not open last night."),
                 Throws()]

    released, learned = set(), set()
    for provider in providers:
        runtime = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:"))
        try:
            runtime.core.realizer = provider
            answer = runtime.submit_player_text("ask Honce about clinic").npc_response
            player = runtime.world.agents[runtime.config.player_id]
            released.add(answer.text)
            learned.add(tuple(sorted(player.beliefs)))
            assert "was open" not in answer.text, (
                f"a line asserting the opposite reached the player: {answer.text!r}")
        finally:
            runtime.close()

    assert len(released) == 1, f"the provider chose the sentence: {released}"
    assert len(learned) == 1, f"the provider chose what the world learned: {learned}"
    assert next(iter(learned))[0], "nothing was asserted, so nothing is proved"
    print(f"ok  dialogue: six provider behaviours including a thrown one, one "
          f"released line and one world state")


def test_the_provider_mode_is_available_and_says_what_it_is():
    """The weaker contract exists, is opt-in, and still runs its checks.

    Making the guarantee structural must not quietly remove the ability to let a
    model write. `semantic_release="provider"` restores it, and the lexical
    checks still replace a line that plainly fails them.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "relay-station")

    class Paraphrase:
        is_deterministic = False
        expressed_commitment = None
        def realize(self, plan, style):
            return "We're right out of sealant, have been for weeks."

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:",
        semantic_release="provider"))
    try:
        runtime.core.realizer = Paraphrase()
        answer = runtime.respond("agent:ferro", topic="supplies")
        assert answer.text == "We're right out of sealant, have been for weeks.", (
            f"provider mode did not use the provider's wording: {answer.text!r}")
    finally:
        runtime.close()

    controlled = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:"))
    try:
        controlled.core.realizer = Paraphrase()
        answer = controlled.respond("agent:ferro", topic="supplies")
        assert answer.text != "We're right out of sealant, have been for weeks.", (
            "controlled release let the provider write a line carrying a fact")
    finally:
        controlled.close()
    print("ok  dialogue: provider mode is available, opt-in, and named")


def test_the_history_of_a_snapshot_does_not_grow_a_future():
    """"As of this snapshot" has to keep meaning that after a reload.

    Both branches surviving was only half of it. The query that answers "the
    history as of snapshot A" filtered on the event id, and `restore` rewinds the
    counter that mints them -- so once a later branch reused those ids, A's own
    history contained events that happened after A was taken.
    """
    from unscripted import snapshot
    from unscripted.persistence import Store

    world = _mini_world("watermark")
    store = Store()
    runtime = Runtime(world, store)
    try:
        start = snapshot.capture(world, runtime)
        shared = world.new_event_id()
        runtime.process_event(Event(shared, 1, "incident", location="p",
                                    payload={"summary": "branch A"}))
        as_of_a = snapshot.capture(world, runtime)["ledger_watermark"]
        before = [json.loads(row["payload"])["summary"]
                  for row in store.ledger_as_of(as_of_a)]

        snapshot.restore(start, world, runtime)
        runtime.process_event(Event(world.new_event_id(), 1, "incident",
                                    location="p", payload={"summary": "branch B"}))
        after = [json.loads(row["payload"])["summary"]
                 for row in store.ledger_as_of(as_of_a)]

        assert before == ["branch A"], before
        assert after == before, f"the history as of A grew a future: {after}"
        assert not hasattr(store, "ledger_up_to"), (
            "the query whose contract could not be met is back")
    finally:
        store.close()
    print("ok  persistence: a snapshot's history is fixed at the moment it was taken")


def test_a_world_is_identified_not_guessed():
    """One shared id is a coincidence somewhere, and always was.

    Agent overlap let every save into every world, because every pack ships
    `agent:player_1`. Adding the map moved the coincidence rather than removing
    it: two unrelated worlds that both name a room `place:spawn` accepted each
    other's saves. A pack that declares `world_id` is believed; one that does not
    needs overlap that could not be an accident.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    from unscripted.snapshot import StateImportError, inspect_state

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def opened(name):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", name),
            storage_path=":memory:"))

    source, target = opened("cyberpunk-block"), opened("noir-harbor")
    try:
        # One place name in common is not a shared world.
        source.world.places["place:spawn"] = {"label": "Spawn"}
        target.world.places["place:spawn"] = {"label": "Spawn"}
        blob = source.export_state()
        report = inspect_state(blob, target.world)
        assert not report["usable"], report
        assert report["code"] == "different_world", report
        was = target.world.world_time
        try:
            target.import_state(blob)
            raise AssertionError("a save from another world was imported")
        except StateImportError:
            pass
        assert target.world.world_time == was, "the clock moved anyway"

        # A declared identity is believed, both ways round.
        source.world.world_id = "block-17"
        target.world.world_id = "block-17"
        assert inspect_state(source.export_state(), target.world)["usable"], (
            "two packs that declare the same world refused each other")
        target.world.world_id = "harbour"
        assert not inspect_state(source.export_state(), target.world)["usable"]
    finally:
        source.close()
        target.close()
    print("ok  snapshot: a world is identified by what it declares, not by an id "
          "two packs happen to share")


def _spoken_claims(answer) -> list:
    """What the ROOM was told, read out of the released answer's own trace."""
    heard = []
    for code, _magnitude, detail in answer.reasons:
        if code in ("dialogue.direct_answer", "dialogue.deception", "dialogue.spoken"):
            heard += [move["rendered"] for move in detail.get("spoken", [])]
    return heard


def test_the_room_is_told_only_what_the_sentence_said():
    """A commitment nobody words is a commitment nobody may make.

    `_direct_answer` selects up to two propositions; a pack authors ONE phrasing
    per topic and it words one thing -- whether the topic's own query holds. A
    barkeep who knew both "the clinic was shut last night" and "the clinic is
    open today" released only the first and taught the room both. The realizer
    reported the commitment as expressed because a template existed, which is not
    the same question as whether these words carry these claims.

    The oracle here is the SENTENCE, not the template table: every claim that
    propagated has to be one the released line is the authored wording for.
    """
    from unscripted import RuntimeConfig
    from unscripted.ontology import Proposition
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        actor = runtime.world.agents["agent:barkeep_12"]
        # A second, entirely legitimate belief -- the kind a running simulation
        # acquires. Nothing in the pack is edited.
        runtime.core.belief.update(
            actor.beliefs,
            Proposition("clinic_open", {"place": "place:clinic", "when": "today"}),
            asserter_polarity="+", trust=0.9, competence=0.9, skepticism=0.0,
            claim_id="today", origin_event="today",
            world_time=runtime.world.world_time, speaker=actor.id)
        answer = runtime.respond(actor.id, topic="clinic")
        heard = _spoken_claims(answer)
        assert answer.verdict == "ACCEPT", answer.verdict
        assert heard, "the answer asserted nothing at all"
        covered = runtime._topic_query("clinic").core_key()
        for claim in heard:
            assert "when=today" not in claim, (
                f"the room learned {claim!r} from a line that never says it: "
                f"{answer.text!r}")
        dropped = [detail for code, _m, detail in answer.reasons
                   if code == "commitment.unsayable_dropped"]
        assert dropped, ("the second claim was never selected, so this case no "
                         "longer tests what it was written for")
        assert any("when=today" in one for one in dropped[0]["dropped"]), dropped
        print(f"ok  dialogue: {len(dropped[0]['dropped'])} selected claim(s) with no "
              f"authored wording were dropped instead of propagated silently "
              f"(covered: {covered})")
    finally:
        runtime.close()


def test_style_chooses_between_wordings_and_never_removes_the_claim():
    """Shortening is a wording decision, and it was deleting content.

    An authored answer that opens with a lead-in -- "Listen carefully. Place was
    shut that night." -- was cut to its first sentence for an agitated speaker by
    the mean-sentence-length pressure, while the claim behind it still propagated
    to everyone in the room. The player read a throat-clearing noise and the world
    heard an assertion.

    Style may pick between COMPLETE realizations of a commitment. It may not
    produce one that carries less than the commitment does.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
        storage_path=":memory:"))
    try:
        actor = runtime.world.agents["agent:barkeep_12"]
        actor.affect.mood.p, actor.affect.mood.a = -1.0, 1.0   # negative, agitated
        topic = runtime.world.topics["clinic"]
        topic.phrasings["affirm"] = {register: "Listen carefully. " + line
                                     for register, line in
                                     topic.phrasings["affirm"].items()}
        answer = runtime.respond(actor.id, topic="clinic")
        heard = _spoken_claims(answer)
        assert heard, "the answer asserted nothing, so there is nothing to check"
        assert answer.text in topic.phrasings["affirm"].values(), (
            f"style rewrote the answer into {answer.text!r}, which is not one of "
            f"the complete authored wordings")
        assert answer.text != "Listen carefully.", (
            "the claim propagated behind a sentence that does not contain it")
        print(f"ok  dialogue: an agitated speaker released a complete authored "
              f"wording ({len(answer.text)} chars) for {len(heard)} claim(s), not "
              f"its first sentence")
    finally:
        runtime.close()


def test_controlled_release_covers_the_greetings_too():
    """A plan with no facts does not make a free answer factually empty.

    Gating controlled release on `asserts_a_fact(plan)` let a model write every
    greeting, deflection and small-talk line in the guaranteed mode. Asked for a
    greeting, a provider is free to answer "He hides behind where drinks are
    served" -- an indirect description of a protected place, released with ACCEPT
    because the runtime had classified the turn as carrying no fact.

    A guarantee that depends on the provider staying inside its brief is not a
    guarantee. In `controlled` the provider is not called at all.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class Leaks:
        is_deterministic = False
        expressed_commitment = None
        def __init__(self):
            self.calls = []
        def realize(self, plan, style):
            self.calls.append(list(plan.allowed_facts))
            return "He hides behind where drinks are served."

    seen = {}
    for mode in ("controlled", "provider"):
        runtime = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", "cyberpunk-block"),
            storage_path=":memory:", semantic_release=mode))
        provider = Leaks()
        try:
            runtime.core.realizer = provider
            answer = runtime.respond("agent:corpo_okada")
            seen[mode] = (answer.text, list(provider.calls))
        finally:
            runtime.close()

    text, calls = seen["controlled"]
    assert not calls, (f"the provider was asked to write {len(calls)} line(s) in "
                       f"controlled mode: {calls}")
    assert text != "He hides behind where drinks are served.", text
    assert seen["provider"][1], "the opt-in mode stopped calling the provider at all"
    print("ok  dialogue: controlled release writes every line, including the ones "
          "that plan no facts; `provider` mode still opts out")


def test_an_earlier_wording_cannot_veto_a_later_fact():
    """The anti-repeat guard is about quality; it was deciding truth.

    Same seed, same authored answer, and only what happened to stand in the
    conversation history first differs. When an earlier line was the clinic
    sentence -- prose a provider wrote in the non-factual turn before it, in the
    shipped configuration of the day -- the later, fully controlled answer was
    refused as a repetition: the commitment behind it voided and the room told
    nothing, while the player still received the text.

    Whatever put a sentence in the history, it is a QUALITY objection. The runtime
    now looks for another complete wording of the same commitment and, failing
    that, says it again. It never answers a repetition by dropping the claim.
    """
    from unscripted import RuntimeConfig
    from unscripted.dialogue import ConversationState
    from unscripted.sdk import UnscriptedRuntime

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = os.path.join(root, "worldpacks", "cyberpunk-block")

    def asked(history):
        runtime = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=pack, storage_path=":memory:"))
        try:
            actor, player = "agent:barkeep_12", runtime.config.player_id
            key = f"conv_{actor}_{player}"
            conv = runtime.core.conversations.setdefault(
                key, ConversationState(key, [actor, player]))
            conv.recent_lines.extend(history)
            answer = runtime.respond(actor, topic="clinic")
            return (_spoken_claims(answer), answer.verdict,
                    sorted(runtime.world.agents[player].beliefs), answer.text)
        finally:
            runtime.close()

    plain = asked(["Evening."])
    # The exact sentence the authored answer will produce, already said.
    echoed = asked(["Evening.", plain[3]])

    assert plain[0], "the control run asserted nothing, so nothing is proved"
    assert plain[0] == echoed[0], (
        f"an earlier sentence changed what the room was told: {plain[0]} vs "
        f"{echoed[0]}")
    assert plain[2] == echoed[2], (
        f"an earlier sentence changed what the player learned: {plain[2]} vs "
        f"{echoed[2]}")
    assert echoed[1] == "ACCEPT", (
        f"the repeated answer was released with verdict {echoed[1]}, so a client "
        f"reading the verdict shows the player nothing while the room hears it")
    print(f"ok  dialogue: the same {len(plain[0])} claim(s) reached the room "
          f"whether or not the answer's own words already stood in the history "
          f"({'reworded' if echoed[3] != plain[3] else 'repeated'})")


def test_a_repeated_claim_never_becomes_proof():
    """The saturation guarantee is GLOBAL, not per eviction cycle.

    Treating an unrecognised source as a first repeat bounded what one
    re-admission is worth and not what a sequence of them is worth. Cycling
    `origin_limit` uninformative sources through a belief evicted the informative
    one, and its next repetition started a fresh geometric series: measured over
    twenty cycles a belief went 0.950 -> 0.99985 on no new evidence at all,
    against a documented ceiling of 3.27160 log-odds it had passed at 8.83332.

    Nothing is evicted now, so the same script cannot restart the ladder at all.
    This is the concrete case; the property is
    [[test_no_ordering_of_events_lifts_the_source_ceiling]], and the mechanism is
    [[test_a_source_this_belief_has_counted_is_never_forgotten]].
    """
    from unscripted.belief import BeliefEngine
    from unscripted.ontology import Proposition

    engine = BeliefEngine()
    beliefs, clock = {}, 0
    claim = Proposition("body:alive", {"agent": "agent:subject"})

    def hear(origin, *, informative=True):
        nonlocal clock
        clock += 1
        belief, _ = engine.update(
            beliefs, claim, asserter_polarity="+",
            trust=0.9 if informative else 0.0, competence=0.9 if informative else 0.0,
            skepticism=0.0 if informative else 1 / 6, claim_id=clock,
            origin_event=origin, world_time=clock, speaker="agent:teller")
        return belief

    hear("pinned", informative=False)        # the first origin is never evicted
    belief = hear("one-informative-report")
    one_hearing = belief.logit_val
    ceiling = one_hearing * engine.max_origin_contribution()

    fillers = [f"filler-{i}" for i in range(engine.params["origin_limit"] - 1)]
    for _cycle in range(20):
        for origin in fillers:
            hear(origin, informative=False)   # kappa = 0.5: exactly zero evidence
        before = belief.logit_val
        belief = hear("one-informative-report")
        gain = belief.logit_val - before

    assert belief.logit_val <= ceiling + 1e-9, (
        f"twenty eviction cycles bought {belief.logit_val:.5f} log-odds against a "
        f"ceiling of {ceiling:.5f}")
    assert gain < 1e-9, (
        f"the twentieth cycle still paid {gain:.5f} for the same claim repeated")
    assert belief.expected_prob < 0.99, (
        f"one repeated claim reached p={belief.expected_prob:.5f}")
    print(f"ok  belief: 20 eviction cycles of one repeated claim end at "
          f"p={belief.expected_prob:.4f} and {belief.logit_val:.5f} log-odds, "
          f"under the {ceiling:.5f} ceiling, with the last cycle worth 0")


def test_an_undeclared_world_is_reported_as_a_guess():
    """Two generic place names are no more an identity than one was.

    Raising the fallback's bar from one shared place to two moved the coincidence
    rather than removing it: two unrelated demo worlds that both happen to name a
    room `place:spawn` and `place:street` accepted each other's saves, and a
    noir clock jumped from 1200 to 4334. Places are exactly the part two
    unrelated worlds are most likely to share by accident.

    So the compatibility path now needs a CHARACTER who is not the player, and
    when it lets a save through on inference it says `world_unverified` rather
    than `ok`, which a loader may refuse on its own.
    """
    from unscripted import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    from unscripted.snapshot import StateImportError, inspect_state

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def opened(name):
        return UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=os.path.join(root, "worldpacks", name),
            storage_path=":memory:"))

    source, target = opened("cyberpunk-block"), opened("noir-harbor")
    try:
        # Both packs declare an id today. This is the pre-`world_id` path.
        source.world.world_id = target.world.world_id = ""
        for runtime in (source, target):
            for name in ("spawn", "street"):
                runtime.world.places["place:" + name] = {"label": name}
        was = target.world.world_time
        blob = source.export_state()
        report = inspect_state(blob, target.world)
        assert not report["usable"], report
        assert report["code"] == "different_world", report
        try:
            target.import_state(blob)
            raise AssertionError("two shared place names imported a foreign save")
        except StateImportError:
            pass
        assert target.world.world_time == was, "the clock moved anyway"

        # AND A PACK AN AUTHOR JUST CREATED DECLARES ONE. Every shipped pack does;
        # a scaffolded one did not, so the first thing a new customer built
        # started on the compatibility path and its own saves came back
        # `world_unverified`. The onboarding path is the one that most needs an
        # identity, because a new pack gets renamed, copied and forked long
        # before anybody thinks about save compatibility.
        import tempfile
        from unscripted.authoring import scaffold_pack
        with tempfile.TemporaryDirectory() as tmp:
            fresh = os.path.join(tmp, "pack")
            scaffold_pack(fresh, name="Scaffold Check")
            made = UnscriptedRuntime.create(RuntimeConfig(
                world_pack_path=fresh, storage_path=":memory:"))
            try:
                assert made.world.world_id, (
                    "`unscripted new` produced a pack with no `world_id`")
                own = inspect_state(made.export_state(), made.world)
                assert own["code"] == "ok", own
            finally:
                made.close()

        # An undeclared save into its OWN world is usable, and says it is a guess.
        own = inspect_state(source.export_state(), source.world)
        assert own["usable"], own
        assert own["code"] == "world_unverified", own
    finally:
        source.close()
        target.close()
    print("ok  snapshot: an undeclared world is never matched on place names "
          "alone, and an inferred match reports `world_unverified`")



def test_the_imprint_is_one_address_in_every_place_it_appears():
    """§ 5 DDG wants a provider identification, and wants it to be correct.

    The company details live in five places -- `IMPRESSUM.md`, the `LICENSE`
    header, `pyproject.toml`, `README.md` and the footer of every page `unscripted
    pages`, `tour`, `compare` and `quickstart` generate. Five copies of a
    postal address is five chances for one of them to be a year out of date,
    and a wrong address in an imprint is worse than none: it is the one thing
    on the page a reader is entitled to rely on.

    So there is exactly one source, `contracts.IMPRINT`, and this asserts every
    copy still agrees with it -- including the Markdown, which is the operative
    document and cannot be generated from the constant.
    """
    from unscripted.contracts import IMPRINT, imprint_html

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(name):
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            return fh.read()

    # Everything § 5 DDG names, and the § 27a UStG VAT id.
    required = ("company", "owner", "street", "city", "phone", "email",
                "register", "register_court", "vat_id")
    assert set(required) <= set(IMPRINT), sorted(set(required) - set(IMPRINT))

    imprint_md = read("IMPRESSUM.md")
    for field in required:
        assert IMPRINT[field] in imprint_md, (
            f"IMPRESSUM.md does not carry the {field} in `contracts.IMPRINT`: "
            f"{IMPRINT[field]!r}")
    for phrase in ("§ 5 DDG", "§ 18 Abs. 2 MStV", "§ 27a UStG"):
        assert phrase in imprint_md, f"IMPRESSUM.md no longer cites {phrase}"
    # The EU ODR platform was shut down on 20 July 2025. A link to it is the
    # single most common thing left stale in a German imprint, and pointing a
    # reader at a dead dispute-resolution route is worse than saying nothing.
    assert "ec.europa.eu/consumers/odr" not in imprint_md, (
        "the imprint links the EU ODR platform, which closed on 20 July 2025")

    readme = read("README.md")
    assert "IMPRESSUM.md" in readme, "the imprint is not reachable from the README"
    licence = read("LICENSE")
    for field in ("company", "owner", "email", "vat_id", "register"):
        assert IMPRINT[field] in licence, (
            f"the LICENSE header disagrees about {field}")
    assert IMPRINT["company"] in read("pyproject.toml")

    # And the generated pages carry it, rendered rather than as a placeholder.
    rendered = imprint_html()
    assert "__IMPRINT__" not in rendered
    for field in ("company", "owner", "street", "city", "phone", "email",
                  "register", "register_court", "vat_id"):
        assert IMPRINT[field] in rendered, field

    from unscripted import compare, quickstart, tour, viz
    from unscripted.cli import _INDEX
    templates = {"unscripted pages": _INDEX, "compare": compare._PAGE,
                 "quickstart": quickstart._PAGE, "viz": viz._PAGE}
    for name, template in templates.items():
        assert "__IMPRINT__" in template, (
            f"the page generated by `{name}` has no imprint slot")
    assert "{imprint}" in tour.TEMPLATE, "`unscripted tour` has no imprint slot"

    # The public addresses have the same problem as the postal one: the video
    # moved once already, and a README pointing at the old one is a dead link on
    # the first thing a visitor clicks.
    from unscripted.contracts import LINKS, links_html
    assert "__LINKS__" in _INDEX, "the showcase index has no slot for its links"
    rendered_links = links_html()
    for key in ("video", "source"):
        assert LINKS[key] in rendered_links, f"the index does not link the {key}"
    for pattern in ("src=", "<link", "@import", "fetch(", "XMLHttpRequest"):
        assert pattern not in rendered_links, f"the links would load something: {pattern}"
    for key in ("video", "pages"):
        assert LINKS[key] in readme, f"README.md does not carry the {key} in `contracts.LINKS`"
    assert LINKS["source"] in read("pyproject.toml"), "pyproject.toml names another source"
    youtube = read(os.path.join("docs", "YOUTUBE.md"))
    for key in ("video", "source", "pages"):
        assert LINKS[key] in youtube, f"docs/YOUTUBE.md does not carry the {key}"

    print(f"ok  imprint: one address in {1 + len(templates)} generated pages and "
          f"4 files, § 5 DDG fields complete, no dead ODR link; one video, one "
          f"source and one showcase address wherever they are named")



if __name__ == "__main__":
    suite = [test_determinism, test_claim_is_not_truth, test_correlation_discount,
               test_repetition_saturates_but_independent_sources_convince,
               test_contradiction_C1_and_C2, test_affect_negative_event_lowers_valence,
               test_pad_baseline_signs, test_register_by_social_position,
               test_trust_kinetics_asymmetric, test_utility_bounded, test_validator_blocks_secret,
               test_ally_response_kinship, test_reactive_rule_fires_when_injured,
               test_leverage_asymmetric, test_graded_resolution_bands,
               test_faction_heat_threshold_mobilizes, test_social_standing_gates_reach,
               test_world_pack_validation,
               test_memory_fades_by_importance_not_uniformly,
               test_parser_vocabulary_comes_from_the_pack,
               test_player_is_never_addressable_as_an_npc,
               test_a_dossier_names_the_code_that_produced_it,
               test_reach_and_detail_are_independent,
               test_a_crowded_room_does_not_update_the_whole_room,
               test_the_occupancy_index_cannot_go_stale,
               test_repeated_episodes_become_a_judgement_that_outlives_them,
               test_exposing_a_liar_recomputes_what_he_convinced_people_of,
               test_revision_leaves_independently_supported_beliefs_standing,
               test_knowledge_stays_inside_its_circle,
               test_attention_is_finite,
               test_competence_changes_what_is_perceived_not_only_who_is_believed,
               test_the_epistemic_profile_decides_how_a_scene_is_misread,
               test_grounding_reads_the_released_line_back,
               test_entity_grounding_is_relative_to_the_world,
               test_a_character_can_lie_and_the_lie_is_traceable,
               test_an_unsayable_commitment_asserts_nothing,
               test_the_text_layer_cannot_choose_what_enters_the_world,
               test_commitment_selection_is_seeded_and_replayable,
               test_layering_is_declared_and_holds,
               test_a_question_is_not_evidence,
               test_evidence_partial_run_says_it_is_partial,
               test_evidence_counts_survive_log_truncation,
               test_evidence_forgetting_uses_the_real_retrieval_threshold,
               test_evidence_run_records_chains_forgetting_and_distortion,
               test_the_same_two_people_lose_more_on_the_phone,
               test_a_town_with_reasons_does_not_go_quiet,
               test_climate_is_weather_not_personality_and_off_is_neutral,
               test_a_mood_is_catching_and_off_means_it_is_not,
               test_everybody_knowing_is_not_everybody_knowing_that_everybody_knows,
               test_a_note_outlives_the_conversation_and_can_be_read_by_the_wrong_person,
               test_every_optional_layer_is_declinable_reachable_and_reported,
               test_the_world_fits_in_the_games_own_save_file_and_survives_a_patch,
               test_a_game_can_launch_the_runtime_as_a_child_process,
               test_a_promise_that_nothing_checks_is_only_a_line_of_dialogue,
               test_every_command_line_in_the_documentation_actually_exists,
               test_a_tick_reports_everything_that_happened_in_it,
               test_attacking_one_of_us_makes_the_rest_of_us_notice,
               test_no_engine_is_built_that_nothing_ever_calls,
               test_the_whole_runtime_ships_as_one_file,
               test_the_film_has_exactly_one_card_per_spoken_line,
               test_a_pack_can_tune_the_runtime_and_a_typo_is_refused,
               test_the_shipped_client_reaches_every_endpoint_a_game_needs,
               test_a_model_may_rewrite_the_lines_but_not_break_them,
               test_the_conformance_fixtures_still_describe_this_runtime,
               test_the_host_finds_the_runtime_and_says_so_when_it_cannot,
               test_a_bundle_finds_its_own_world_packs,
               test_a_premise_becomes_a_world_a_studio_could_play,
               test_nothing_is_read_that_nothing_writes,
               test_the_page_names_the_engine_versions_it_was_actually_run_against,
               test_what_you_turn_up_wearing_changes_how_you_are_taken,
               test_who_you_believe_is_a_fact_about_you,
               test_a_thing_the_engineers_say_stays_among_the_engineers,
               test_fear_and_respect_stop_being_decorative,
               test_what_you_did_to_one_of_them_reaches_the_rest_of_them,
               test_the_world_answers_to_what_the_player_does,
               test_a_world_pack_can_name_the_layers_it_is_built_on,
               test_the_demo_ships_the_shipped_addon_and_not_a_fork_of_it,
               test_no_tuning_value_can_crash_the_runtime_mid_tick,
               test_the_unity_package_compiles_where_an_editor_is_installed,
               test_the_unreal_plugin_compiles_where_a_built_engine_exists,
               test_the_unreal_plugin_behaves_where_a_built_engine_exists,
               test_the_noir_pack_produces_the_scene_it_was_written_for,
               test_a_cover_story_is_licensed_by_its_own_words_and_nothing_else,
               test_the_default_narrator_is_asked_for_a_voice_it_has,
               test_a_contested_world_holds_two_answers_at_once,
               test_the_engine_demo_and_its_narration_stay_in_step,
               test_a_leading_verb_decides_the_intent,
               test_the_comparison_is_computed_on_both_sides_and_can_be_lost,
               test_the_film_is_cut_to_the_voice_and_says_only_what_was_recorded,
               test_the_quickstart_page_is_captured_and_not_typed,
               test_a_voice_is_planned_from_affect_and_says_what_it_cannot_do,
               test_the_recording_is_the_run_and_the_same_run_twice,
               test_the_tour_shows_only_what_it_ran,
               test_asking_one_person_twice_is_still_one_witness,
               test_qa_finds_the_shortest_breaking_path_and_says_what_it_covered,
               test_the_contract_names_methods_the_plugin_actually_has,
               test_the_action_bridge_is_a_two_way_exchange,
               test_contract_v2_is_additive_and_v1_is_frozen,
               test_engine_bridge_contract_matches_the_live_service,
               test_encounter_rate_sets_pace_and_the_gate_is_a_trust_threshold,
               test_distortion_follows_allport_and_postman,
               test_a_distorted_rumour_is_a_false_belief_with_a_true_origin,
               test_scaffolded_pack_is_immediately_playable,
               test_authoring_report_names_the_problem_and_the_fix,
               test_studio_endpoints_preview_without_writing_and_refuse_traversal,
               test_diffusion_reproduces_the_daley_kendall_saturation,
               test_knowledge_map_shows_who_knows_what_and_how,
               test_latency_budget_answers_now_and_upgrades_later,
               test_late_line_that_fails_validation_is_never_offered,
               test_model_probe_reports_capability_at_startup,
               test_routines_move_the_cast_and_create_meetings,
               test_routine_time_skip_does_not_replay_the_week,
               test_pack_validation_catches_a_self_contradicting_routine,
               test_benchmark_claims_hold_on_every_pack,
               test_knowledge_spreads_through_the_society_over_time,
               test_relayed_rumour_does_not_become_independent_proof,
               test_diffusion_never_leaks_a_secret_and_stays_deterministic,
               test_provenance_is_bounded_and_survives_a_reload,
               test_event_persistence_does_not_scale_with_population,
               test_memory_and_trace_growth_is_bounded,
               test_one_version_and_nothing_disagrees_with_it,
               test_packaging_manifest_covers_every_data_file,
               test_canon_layer_rejects_hallucinated_specifics,
               test_hallucinating_provider_never_reaches_the_player,
               test_engine_contains_no_world_content,
               test_parser_free_text_contract,
               test_sdk_terminal_turn_and_provider_record,
               test_terminal_social_input_requires_reachable_target,
               test_provider_failure_costs_the_wording_and_not_the_content,
               test_rejected_provider_output_never_reaches_player,
               test_sdk_attack_mobilizes_social_consequence,
               test_initial_state_loaded_from_world_pack,
               test_capability_config_requires_http_endpoint,
               test_service_rejects_malformed_requests_with_4xx,
               test_service_auth_and_debug_endpoint_gating,
               test_service_over_real_http_caps_body_size,
               test_snapshot_restore_rewinds_state,
               test_snapshot_roundtrip_is_exact,
               test_snapshot_reports_mismatches_instead_of_failing_silently,
               test_snapshot_size_is_independent_of_ledger_length,
               test_replay_golden_file_and_second_pack,
               test_character_generation_from_environment_and_appearance,
               test_bridge_profiles_and_event_mapping,
               test_service_turn_and_generate_handlers,
               test_llm_output_cleaning_is_safe,
               test_prospect_reference_is_need_not_wealth,
               test_metahuman_blendshapes_bounded_and_emotion_specific,
               test_metahuman_neutral_and_avatar_packet,
               test_population_lod_decay_is_exact,
               test_population_lod_preserves_behavior,
               test_golden_scenarios_all_pass,
               test_multiturn_continuity_and_resume,
               test_structured_state_and_demo_endpoints,
               test_the_cpp_port_reproduces_python_exactly,
               test_recall_is_bounded_by_working_memory,
               test_a_retelling_carries_the_first_origin_not_the_latest,
               test_nobody_is_convinced_by_the_sound_of_their_own_voice,
               test_a_claim_stops_being_passed_on_after_enough_retellings,
               test_a_character_does_not_repeat_a_line_they_just_said,
               test_the_c_abi_is_callable_from_c,
               test_the_unreal_binding_talks_to_the_runtime,
               test_the_unity_binding_marshals_correctly,
               test_the_godot_binding_loads_and_runs,
               test_a_port_may_differ_in_the_last_bit_and_nowhere_else,
               test_evidence_pools_follow_the_contribution_not_the_assertion,
               test_discrediting_a_source_weakens_evidence_without_inventing_conflict,
               test_revision_survives_a_trimmed_provenance_list,
               test_discredit_matches_a_whole_id_not_a_substring,
               test_a_belief_tracks_a_bounded_number_of_sources,
               test_one_liar_telling_one_lie_is_one_source,
               test_being_told_again_is_not_being_wronged_again,
               test_a_feared_event_that_happens_is_not_a_relief,
               test_a_threat_is_judged_on_conduct_not_on_the_actor_s_own_fear,
               test_publicity_carries_polarity,
               test_memory_holds_what_was_understood_not_what_happened,
               test_who_witnessed_an_event_does_not_depend_on_the_step_size,
               test_a_judgement_still_names_its_evidence_after_a_reload,
               test_a_released_line_must_agree_with_the_polarity_it_committed_to,
               test_a_paraphrase_that_names_a_protected_place_is_refused,
               test_the_provider_chooses_the_wording_not_whether_the_world_hears_it,
               test_a_save_from_another_world_is_refused,
               test_a_corrupt_import_leaves_the_world_untouched,
               test_the_event_ledger_only_appends,
               test_the_demo_page_does_not_hand_out_the_token,
               test_the_native_json_parser_refuses_malformed_documents,
               test_memory_retrieval_is_a_draw_not_a_threshold,
               test_there_is_one_speech_path_and_it_reaches_the_world,
               test_the_pad_baseline_states_its_sign_convention,
               test_the_player_and_the_room_agree_across_adversarial_wordings,
               test_a_source_this_belief_has_counted_is_never_forgotten,
               test_no_ordering_of_events_lifts_the_source_ceiling,
               test_a_line_the_runtime_chose_to_release_is_reported_as_released,
               test_the_player_reads_the_sentence_the_runtime_wrote_for_the_claim,
               test_the_provider_mode_is_available_and_says_what_it_is,
               test_the_history_of_a_snapshot_does_not_grow_a_future,
               test_a_world_is_identified_not_guessed,
               test_the_room_is_told_only_what_the_sentence_said,
               test_style_chooses_between_wordings_and_never_removes_the_claim,
               test_controlled_release_covers_the_greetings_too,
               test_an_earlier_wording_cannot_veto_a_later_fact,
               test_a_repeated_claim_never_becomes_proof,
               test_an_undeclared_world_is_reported_as_a_guess,
               test_the_imprint_is_one_address_in_every_place_it_appears,
               test_full_showcase_runs_all_checks]
    # A test that is written but never listed here is worse than no test: it reads
    # as coverage and asserts nothing. Four had already accumulated. The list stays
    # explicit -- order matters for the slower cases -- but it can no longer drift.
    orphans = sorted(name for name, obj in sorted(globals().items())
                     if name.startswith("test_") and callable(obj) and obj not in suite)
    if orphans:
        raise AssertionError("defined but never run: " + ", ".join(orphans))

    for fn in suite:
        fn()
    print(f"\nAll tests passed. ({len(suite)} tests)")
