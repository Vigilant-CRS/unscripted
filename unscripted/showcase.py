"""Full SDK showcase for sales demos and regression checks."""
from __future__ import annotations

import json

from .bridge import list_bridge_profiles
from . import content
from .contracts import RuntimeConfig
from .dialogue import DialoguePlan
from .events import Event
from .generator import CharacterGenerationRequest, generate_characters
from .ontology import Proposition
from .pack import validate_world_pack
from .sdk import UnscriptedRuntime
from .service import UnscriptedService
from .validator import Validator


def run_showcase(*, world_pack: str = "worldpacks/cyberpunk-block",
                 secondary_world_pack: str = "worldpacks/noir-harbor",
                 tertiary_world_pack: str = "worldpacks/dorf-thornfeld",
                 storage_path: str = ":memory:") -> dict:
    """Run a deterministic end-to-end tour through the public SDK surface."""
    lines: list[str] = []
    checks: dict[str, bool] = {}
    sections: list[str] = []

    def section(title: str):
        sections.append(title)
        lines.append("")
        lines.append("=" * 72)
        lines.append(title)
        lines.append("=" * 72)

    def emit(text: str = ""):
        lines.append(text)

    cfg = RuntimeConfig(world_pack_path=world_pack, storage_path=storage_path, debug_traces=True)
    sdk = UnscriptedRuntime.create(cfg)
    replay_sdk = None
    second_sdk = None
    third_sdk = None
    try:
        player = cfg.player_id
        vee = "agent:npc_red_jacket"
        honce = "agent:barkeep_12"
        kane = "agent:officer_kane"
        pavel = "agent:pavel"

        section("1. Pack, Capabilities, Initial State")
        report = validate_world_pack(UnscriptedRuntime._resolve_pack_path(world_pack))
        checks["primary_pack_valid"] = report.ok
        emit(f"pack valid: {report.ok}")
        emit("capabilities: " + json.dumps(sdk.capability_plan.resolved, sort_keys=True))
        emit(sdk.describe_location(sdk.world.agents[player].location))
        clinic_prop = Proposition("clinic_open", {"place": "place:clinic", "when": "last_night"}, "-")
        honce_clinic = sdk.query_belief(honce, clinic_prop)
        checks["initial_state_loaded"] = honce_clinic is not None and honce_clinic.expected_prob < 0.5
        emit(f"Honce authored clinic belief p(open)= {honce_clinic.expected_prob:.2f}")

        section("2. Same Topic, Different Knowledge")
        vee_turn = sdk.submit_player_text("ask Vee about Milan")
        honce_turn = sdk.submit_player_text("ask Honce about clinic")
        emit("> ask Vee about Milan")
        emit(vee_turn.message)
        emit("> ask Honce about clinic")
        emit(honce_turn.message)
        checks["vee_protects_secret"] = vee_turn.npc_response is not None and vee_turn.npc_response.act != "inform"
        checks["honce_answers_clinic"] = "shut that night" in honce_turn.message

        section("3. Claim Is Not Truth + Correlation Discount")
        milan_prop = Proposition("looking_for", {"seeker": player, "target": "milan"})
        p_after_player = _belief_prob(sdk, vee, milan_prop)
        same_origin_event = Event(
            sdk.world.new_event_id(), sdk.world.world_time, "claim",
            actor=honce, location="place:main_street",
            payload={"proposition": milan_prop.as_dict(),
                     "summary": "Honce repeats the same rumor source",
                     "origin_event": "evt_same_rumor", "domain": "gossip"},
        )
        sdk.emit_event(same_origin_event)
        p_after_first_origin = _belief_prob(sdk, vee, milan_prop)
        repeat_event = Event(
            sdk.world.new_event_id(), sdk.world.world_time, "claim",
            actor=honce, location="place:main_street",
            payload={"proposition": milan_prop.as_dict(),
                     "summary": "Honce repeats the same rumor source again",
                     "origin_event": "evt_same_rumor", "domain": "gossip"},
        )
        sdk.emit_event(repeat_event)
        p_after_repeat = _belief_prob(sdk, vee, milan_prop)
        independent_event = Event(
            sdk.world.new_event_id(), sdk.world.world_time, "claim",
            actor=kane, location="place:main_street",
            payload={"proposition": milan_prop.as_dict(),
                     "summary": "Kane has an independent duty log",
                     "origin_event": "evt_kane_log", "domain": "law"},
        )
        sdk.emit_event(independent_event)
        p_after_independent = _belief_prob(sdk, vee, milan_prop)
        same_delta = p_after_repeat - p_after_first_origin
        independent_delta = p_after_independent - p_after_repeat
        checks["correlation_discount"] = independent_delta > same_delta
        emit(f"after player claim: p={p_after_player:.2f}")
        emit(f"same origin repeat delta={same_delta:+.3f}")
        emit(f"independent source delta={independent_delta:+.3f}")
        emit("claim stored as belief with provenance, not as canonical truth.")

        section("4. Relationship, Protected Fact Guard, Provider Records")
        promise_turn = sdk.submit_player_text("promise Vee 300")
        emit("> promise Vee 300")
        emit(promise_turn.message)
        trust = sdk.world.agents[vee].trust_in(player)
        checks["relationship_updates"] = trust > 0.25
        checks["provider_records"] = sdk.store.provider_call_count() >= 3
        # the runtime's own validator, loaded with THIS world's protected vocabulary
        leak_plan = DialoguePlan(speaker=vee, addressee=player, dialogue_act="inform",
                                 goal="answer",
                                 avoid_topics=content.avoid_labels(sdk.world.agents[vee].secrets))
        leak = sdk.core.validator.check("Milan is at the clinic back room.", leak_plan,
                                        sdk.world.agents[vee], [])
        checks["secret_guard_blocks_leak"] = leak.verdict == "REJECT_HARD"
        checks["secret_vocabulary_is_authored"] = (
            not sdk.core.validator.unprotected_labels(leak_plan.avoid_topics))
        emit(f"Vee trust in player after promise: {trust:.2f}")
        emit(f"provider records persisted: {sdk.store.provider_call_count()}")
        emit(f"secret-leak validator verdict: {leak.verdict}")

        section("5. Snapshots, Movement, Player Lie")
        snap = sdk.create_snapshot("before_police_route")
        sdk.submit_player_text("go market")
        sdk.submit_player_text("go police post")
        lie_turn = sdk.submit_player_text("tell Kane I am police")
        role_prop = Proposition("core:holds_role",
                                {"agent": player, "role": "role:officer", "context": "faction:badges"})
        kane_belief = sdk.query_belief(kane, role_prop)
        checks["player_lie_uncertain"] = kane_belief is not None and 0.5 < kane_belief.expected_prob < 0.75
        emit("> tell Kane I am police")
        emit(lie_turn.message)
        emit(f"Kane belief that player is officer: p={kane_belief.expected_prob:.2f}")
        sdk.restore_snapshot(snap)
        restored_loc = sdk.world.agents[player].location
        checks["snapshot_restore"] = restored_loc == "place:main_street"
        emit(f"snapshot restore location: {restored_loc}")

        section("6. Media, Social Consequence, Time")
        radio_turn = sdk.submit_player_text("listen radio")
        checks["media_propagates"] = "city-news bulletin" in radio_turn.message
        sdk.submit_player_text("go market")
        attack_turn = sdk.submit_player_text("attack Pavel")
        wait_turn = sdk.submit_player_text("wait 20")
        checks["offscreen_mobilization"] = "mobilize_allies" in attack_turn.message
        checks["time_advance"] = sdk.world.world_time >= 4380
        emit("> listen radio")
        emit(radio_turn.message.splitlines()[0])
        emit("> attack Pavel")
        emit(attack_turn.message)
        emit("> wait 20")
        emit(wait_turn.message.splitlines()[0])
        emit(sdk.inspect_agent(pavel).splitlines()[0])

        section("7. Replay, Bridges, Service ABI")
        replay_sdk = UnscriptedRuntime.create(RuntimeConfig(world_pack_path=world_pack, storage_path=":memory:"))
        replay = replay_sdk.replay_commands(["look", "ask Vee about Milan"], replay_id="showcase")
        profiles = list_bridge_profiles()
        service = UnscriptedService(sdk)
        service_event = service.handle_post("/event", {
            "type": "claim",
            "actor": player,
            "location": sdk.world.agents[player].location,
            "payload": {"summary": "engine-generated social beat"},
        })
        checks["replay_runs"] = len(replay.steps) == 2 and replay.replay_id == "showcase"
        checks["bridge_profiles"] = {"unreal", "unity", "godot", "inworld", "convai"} <= set(profiles)
        checks["service_event_auto_id"] = int(service_event["event_id"]) > 0
        emit(f"replay steps: {len(replay.steps)} final_time={replay.final_world_time}")
        emit("bridge profiles: " + ", ".join(sorted(profiles.keys())))
        emit(f"service /event auto id: {service_event['event_id']}")

        section("8. Automatic Character Generation + Second Pack")
        generated = generate_characters(_world_data(sdk), CharacterGenerationRequest(
            count=2,
            location_id="place:police_post",
            appearances=["uniform"],
            seed="showcase",
        ))
        first = generated.characters[0]
        second_report = validate_world_pack(UnscriptedRuntime._resolve_pack_path(secondary_world_pack))
        second_sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=secondary_world_pack,
            storage_path=":memory:",
        ))
        checks["generated_characters"] = (
            len(generated.characters) == 2
            and first["roles"][0]["role"] == "role:officer"
            and any(b["proposition"]["predicate"] == "place:has_surveillance"
                    for b in generated.initial_beliefs)
        )
        checks["secondary_pack_valid"] = second_report.ok and len(second_sdk.world.agents) >= 2
        emit(f"generated first NPC: {first['id']} role={first['roles'][0]['role']} "
             f"status={first['social_status']}")
        emit(f"generated initial beliefs: {len(generated.initial_beliefs)}")
        emit(f"secondary pack valid: {second_report.ok}; agents={len(second_sdk.world.agents)}")

        section("9. The Same Engine, A Different Genre And Language")
        # The engine ships no world vocabulary, so a pack in another setting and
        # another language is content work, not engine work. This section is the
        # proof a studio actually asks for.
        third_report = validate_world_pack(UnscriptedRuntime._resolve_pack_path(tertiary_world_pack))
        third_sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=tertiary_world_pack, storage_path=":memory:"))
        scene = third_sdk.structured_scene()
        answer = third_sdk.submit_player_text("frage Greta nach dem Korn")
        third_sdk.submit_player_text("geh zur Schmiede")
        gated = third_sdk.submit_player_text("frage Hanns nach seinen Schulden")
        smith = third_sdk.world.agents["agent:schmied_hanns"]
        gate_fired = any(code == "dialogue.secret_gate"
                         for code, _, _ in third_sdk.core.last_traces.get("agent:schmied_hanns", []))
        checks["tertiary_pack_valid"] = third_report.ok
        checks["tertiary_pack_navigable"] = bool(scene["exits"]) and "Schmiede" in [
            e["label"] for e in scene["exits"]]
        checks["tertiary_pack_answers_in_its_own_language"] = "Kein Korn" in answer.message
        checks["tertiary_pack_protects_its_own_secret"] = (
            gate_fired and "heller" not in gated.message.lower())
        emit(f"third pack valid: {third_report.ok}; place={scene['label']}; "
             f"exits={[e['label'] for e in scene['exits']]}")
        emit("> frage Greta nach dem Korn")
        emit(answer.message)
        emit("> frage Hanns nach seinen Schulden")
        emit(gated.message)
        emit(f"secret gate fired: {gate_fired} "
             f"(trust {smith.trust_in(player):.2f} < {smith.secrets[0].min_trust})")

        section("Showcase Checks")
        for key in sorted(checks):
            emit(f"{key}: {'OK' if checks[key] else 'FAIL'}")

    finally:
        sdk.close()
        if replay_sdk:
            replay_sdk.close()
        if second_sdk:
            second_sdk.close()
        if third_sdk:
            third_sdk.close()

    return {"sections": sections, "checks": checks, "output": "\n".join(lines).strip() + "\n"}


def _belief_prob(sdk: UnscriptedRuntime, agent_id: str, proposition: Proposition) -> float:
    belief = sdk.query_belief(agent_id, proposition)
    return belief.expected_prob if belief else 0.5


def _world_data(runtime: UnscriptedRuntime) -> dict:
    return {
        "places": runtime.world.places,
        "entities": runtime.world.entities,
        "channels": runtime.world.channels,
        "factions": runtime.world.factions,
        "media_exposure": [
            {"agent": agent, "channel": channel, **value}
            for (agent, channel), value in runtime.world.media_exposure.items()
        ],
    }


def main() -> int:
    result = run_showcase()
    print(result["output"])
    return 0 if all(result["checks"].values()) else 2
