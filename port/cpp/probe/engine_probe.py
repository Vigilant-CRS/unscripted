"""Runs the same engine cases through Python, and compares field by field.

Four engines make up one mind: affect, relationship, reputation-and-identity,
memory. This drives the real modules -- `unscripted.affect`, `unscripted.relationship`,
`unscripted.memory` -- through `engine_cases.json`, serialises the result the way the
C++ side does, and names every field that disagrees.

    python3 port/cpp/probe/engine_probe.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(PORT_ROOT))
CASES = os.path.join(HERE, "engine_cases.json")

sys.path.insert(0, REPO_ROOT)

from unscripted.affect import AffectEngine, AffectState, pad_baseline_from_big_five  # noqa: E402
from unscripted.agency import (ReactiveRule, authority, default_reactive_rules,     # noqa: E402
                        fire_reactive_rules, leverage, mobilization_candidate,
                        potential_allies, resolve, risk_reference_point)
from unscripted.agent import Agent                                                  # noqa: E402
from unscripted.appearance import AppearanceEngine                                  # noqa: E402
from unscripted.belief import Belief, _contribution_key as contribution_key, BeliefEngine                                  # noqa: E402
from unscripted.commitment import (CERTAIN, Candidate, SemanticMove, certainty_for, # noqa: E402
                            deceive, select)
from unscripted.actions import ActionCandidate, ActionDefinition                    # noqa: E402
from unscripted.dialogue import ConversationState, DialoguePlan, DialoguePlanner    # noqa: E402
from unscripted.factions import Director, Faction                                   # noqa: E402
from unscripted.sociolinguistics import StyleVector                                 # noqa: E402
from unscripted.climate import ClimateEngine, baseline_for                          # noqa: E402
from unscripted.common_knowledge import CommonKnowledgeEngine                       # noqa: E402
from unscripted.notes import NoteBoard                                              # noqa: E402
from unscripted.pursuit import PursuitEngine                                        # noqa: E402
from unscripted.flat import FlatWorld                                               # noqa: E402
from unscripted.grounding import (WorldLexicon, anchors_for, expresses,             # noqa: E402
                           unknown_referents)
from unscripted.revision import discredit, would_change                             # noqa: E402
from unscripted.tuning import TUNABLE, TuningError                                   # noqa: E402
from unscripted.tuning import apply as apply_tuning                                 # noqa: E402
from unscripted.tuning import check as check_tuning                                 # noqa: E402
from unscripted.tuning import describe as describe_tuning                           # noqa: E402
from unscripted.promises import PromiseLedger                                       # noqa: E402
from unscripted.contagion import ContagionEngine                                    # noqa: E402
from unscripted.medium import BY_NAME, contacts_of, for_exchange                    # noqa: E402
from unscripted.medium import describe as describe_medium                           # noqa: E402
from unscripted.content import (AliasIndex, Secret, Topic, avoid_labels,            # noqa: E402
                         protected_keys, secrets_from, secrets_guarding,
                         surface_forms_by_label)
from unscripted.determinism import derive_seed                                      # noqa: E402
from unscripted.diffusion import DiffusionEngine                                    # noqa: E402
from unscripted.distortion import describe, distort                                 # noqa: E402
from unscripted.contracts import (AUTHORED_ONLY_FIELDS, DEFAULT_PLAYER_ID,          # noqa: E402
                           LAYER_REQUIRES, OPTIONAL_LAYERS, RUNTIME_VERSION,
                           RuntimeConfig)
from unscripted.affect import AffectEngine as _AffectEngineAlias                    # noqa: E402
from unscripted.memory import Memory, MemoryEngine                                  # noqa: E402
from unscripted.ontology import (_PREDICATE_SOURCES, Proposition,                   # noqa: E402
                          register_predicate, reset_predicates)
from unscripted.relationship import (IdentityEngine, RelationshipEngine,            # noqa: E402
                              ReputationEngine)
from unscripted.actions import default_candidates                                   # noqa: E402
from unscripted.policy import PolicyEngine                                          # noqa: E402
from unscripted.statekey import relationship_delta, reputation_delta                # noqa: E402
from unscripted.events import Event                                                 # noqa: E402
from unscripted.perception import PerceptionEngine                                  # noqa: E402
from unscripted.routine import Routine, RoutineEngine                               # noqa: E402
from unscripted.sociolinguistics import SociolinguisticEngine                       # noqa: E402
from unscripted.standing import StandingEngine                                      # noqa: E402
from unscripted.social import (ImpressionManagementEngine, InterpersonalEngine,     # noqa: E402
                        NormEngine, SocialExchangeEngine, SocialIdentityEngine,
                        SocialNetworkEngine, TheoryOfMindEngine, ValueEngine)
from unscripted.types import Vec3                                                   # noqa: E402
from unscripted.topology import (attention_budget, bridges, circles, may_pass_on,   # noqa: E402
                          spend_attention)
from unscripted.interpretation import InterpretationEngine, seeded_noise           # noqa: E402
from unscripted.parser import RuleBasedParserProvider, normalize                   # noqa: E402
from unscripted.actionbridge import ActionBridge                                    # noqa: E402
from unscripted.provider import HttpChatRealizer, TemplateRealizer                  # noqa: E402
from unscripted.inspect import (fmt_affect, fmt_beliefs, fmt_last_trace,            # noqa: E402
                         fmt_memory)
from unscripted.runtime import Runtime                                              # noqa: E402
from unscripted import state_view                                                   # noqa: E402
from unscripted.sdk import UnscriptedRuntime                                      # noqa: E402
from unscripted.snapshot import (StateImportError, capture, export_state,           # noqa: E402
                          import_state, inspect_state, restore, world_fingerprint)
from unscripted.validator import Validator                                         # noqa: E402
from unscripted.world import World, load_world_pack                                 # noqa: E402

from belief_probe import differences, to_bits                                # noqa: E402


def reasons_of(rows):
    return [{"code": code, "amount": amount, "detail": detail}
            for code, amount, detail in rows]


def run_contracts(_scenario: dict) -> dict:
    """Every single-source-of-truth constant, for a word-for-word comparison.

    `OPTIONAL_LAYERS` exists because three copies of the layer list came to
    disagree about what exists. A second implementation is a fourth copy, and
    this is the only thing standing between it and the same failure.
    """
    config = RuntimeConfig()
    return {
        "runtime_version": RUNTIME_VERSION,
        "default_player_id": DEFAULT_PLAYER_ID,
        "optional_layers": [list(row) for row in OPTIONAL_LAYERS],
        "layer_requires": dict(LAYER_REQUIRES),
        "authored_only_fields": dict(AUTHORED_ONLY_FIELDS),
        "config_defaults": {
            "runtime_id": config.runtime_id,
            "schema_version": config.schema_version,
            "world_pack_path": config.world_pack_path,
            "storage_path": config.storage_path,
            "debug_traces": config.debug_traces,
            "strict": config.strict,
            "player_id": config.player_id,
            "player_start_location": config.player_start_location,
            "load_initial_state": config.load_initial_state,
            "population_lod": config.population_lod,
            "action_timeout_minutes": config.action_timeout_minutes,
            "voice_backend": config.voice_backend,
            "voice_model": config.voice_model,
            "projection_scope": config.projection_scope,
            "canon_mode": config.canon_mode,
            "layers_off_by_default": {name: getattr(config, name)
                                      for name, _why in OPTIONAL_LAYERS},
        },
        # Setting one layer must set exactly that one. A hand-written switch over
        # nine names is the shape that quietly forgets one.
        "set_layer_sets_exactly_one": {
            name: all(getattr(RuntimeConfig(**{name: True}), other) == (other == name)
                      for other, _why in OPTIONAL_LAYERS)
            for name, _why in OPTIONAL_LAYERS},
    }


def run_roundtrip(scenario: dict) -> dict:
    """Serialise, restore, serialise again. The second blob must equal the first."""
    blob, kind = scenario["blob"], scenario["kind"]
    if kind == "belief":
        return {"restored": Belief.from_dict(blob).as_dict()}
    if kind == "memory":
        return {"restored": Memory.from_dict(blob).as_dict()}
    return {"restored": AffectState.from_dict(blob).as_dict()}


def run_predicates(scenario: dict) -> dict:
    reset_predicates()
    accepted = []
    for row in scenario["register"]:
        register_predicate(row["name"],
                           {"slots": row["slots"], "functional_in": row["functional_in"]},
                           source="probe pack")
        accepted.append(row["name"])

    # Each of these must be refused. WHICH ones is the assertion -- the message
    # text is not compared, because two implementations may word it differently
    # and neither is wrong.
    refused = []
    for row in scenario["conflicts"]:
        raised = False
        try:
            register_predicate(row["name"],
                               {"slots": row["slots"], "functional_in": row["functional_in"]},
                               source="other pack")
        except ValueError:
            raised = True
        refused.append({"name": row["name"], "refused": raised})

    keys = [Proposition.from_dict(row).core_key() for row in scenario["core_keys"]]
    reset_predicates()
    return {"accepted": accepted, "refused": refused, "core_keys": keys}


class DiffusionRuntime:
    """What diffusion needs from the rest of the runtime, and nothing else.

    No climate, no common-knowledge, no contagion layer: all three are off by
    default and off is exactly neutral, so their absence here IS the shipped
    configuration rather than a simplification. `getattr(runtime, "climate", None)`
    finds nothing, which is what the Python does when the layer is not enabled.
    """

    def __init__(self):
        self.network = SocialNetworkEngine()
        self.events = []

    def process_event(self, event):
        self.events.append({
            "event_id": event.event_id, "world_time": event.world_time,
            "type": event.type, "actor": event.actor, "location": event.location,
            "payload": event.payload,
        })


def belief_from(row: dict) -> Belief:
    proposition = Proposition.from_dict(row)
    proposition.polarity = "+"
    belief = Belief(proposition=proposition, logit_val=row["logit"],
                    support_for=row["support_for"],
                    support_against=row["support_against"],
                    hops=row["hops"], spreading=row["spreading"],
                    txn_time=row["txn_time"])
    belief.origin_counts = dict(row["origin_counts"])
    return belief


def build_crowd(world) -> None:
    """Forty people in one gossipy room, over the encounter cap on purpose."""
    for index in range(40):
        agent = Agent(id="agent:c%02d" % index, location="place:square")
        for other in range(40):
            if other == index:
                continue
            agent.relationships["agent:c%02d" % other] = {"familiarity": 0.9,
                                                          "liking": 0.5}
        proposition = Proposition("was_at", {"agent": "agent:x",
                                             "place": "place:square", "when": 600})
        belief = Belief(proposition=proposition, logit_val=2.0, support_for=2.0,
                        txn_time=600)
        belief.origin_counts = {"1": 1}
        agent.beliefs[proposition.core_key()] = belief
        world.agents[agent.id] = agent


class FakeWorldLexicon:
    """Everything the lexicon builder reads off a world, and nothing else."""

    def __init__(self, setup, topics):
        self.places = setup["places"]
        self.entities = setup["entities"]
        self.predicates = setup["predicates"]
        self.decorative_vocabulary = setup["decorative_vocabulary"]
        self.agents = {}
        for row in setup["agents"]:
            self.agents[row["id"]] = Agent(
                id=row["id"], public_name=row["public_name"],
                objective_name=row["objective_name"], aliases=tuple(row["aliases"]))
        self.topics = {t.topic_id: t for t in topics}


def _runtime_event(row: dict) -> Event:
    return Event(event_id=row["event_id"], world_time=row["world_time"],
                 type=row["type"], actor=row["actor"], location=row["location"],
                 payload=dict(row["payload"] or {}))


def _agent_dump(agent) -> dict:
    return {
        "location": agent.location,
        "beliefs": {key: b.as_dict() for key, b in agent.beliefs.items()},
        "memory": [m.as_dict() for m in agent.memory],
        "affect": agent.affect.as_dict(),
        "relationships": {o: dict(v) for o, v in agent.relationships.items()},
        "reputation": {s: dict(d) for s, d in agent.reputation.items()},
        "identity_threat": dict(agent.identity_threat),
        "identity_salience": dict(agent.identity_salience),
        "attention_day": agent.attention_day,
        "attention_spent": agent.attention_spent,
    }


def _runtime_dump(world, rt) -> dict:
    return {
        "world_time": world.world_time,
        "next_event_id": world._next_event_id,
        "scenario_events": [{"event_id": e.event_id, "world_time": e.world_time,
                             "type": e.type, "actor": e.actor,
                             "location": e.location, "payload": e.payload}
                            for e in world.scenario_events],
        "agents": {aid: _agent_dump(a) for aid, a in world.agents.items()},
        "traces": {key: reasons_of(entries)
                   for key, entries in rt.last_traces.items()},
        "actions": rt.actions_out.as_dict(),
        "climate": rt.climate.as_dict(),
        "promises": rt.promises.as_dict(),
        "notes": rt.notes.as_dict(),
        "common_knowledge": rt.common_knowledge.as_dict(),
        "pursuit": rt.pursuit.as_dict(),
        "last_decay": dict(rt._last_decay),
        "director": {fid: f.as_dict() for fid, f in rt.director.factions.items()},
    }


class _FakeInspectRuntime:
    """Just enough runtime for `fmt_last_trace`, which reads one attribute."""

    def __init__(self, traces):
        self.last_traces = traces


def _pack_world_dump(w) -> dict:
    """Everything the loader is responsible for, and nothing it is not."""
    return {
        "global_seed": w.global_seed,
        "world_time": w.world_time,
        "places": w.places,
        "entities": w.entities,
        "channels": w.channels,
        "identity_values": {k: list(v) for k, v in w.identity_values.items()},
        "command_aliases": {k: list(v) for k, v in w.command_aliases.items()},
        "standing_conduct": w.standing_conduct,
        "appearance_reactions": w.appearance_reactions,
        "dialogue_templates": w.dialogue_templates,
        "slang_lexicon": w.slang_lexicon,
        "diffusion_params": w.diffusion_params,
        "tuning": w.tuning,
        "routine_params": w.routine_params,
        "predicate_domains": w.predicate_domains,
        "predicate_competence": w.predicate_competence,
        "predicates": w.predicates,
        "canon_facts": w.canon_facts,
        "topics": {tid: {"id": t.topic_id, "label": t.label,
                         "aliases": list(t.aliases), "query": t.query,
                         "player_claim": t.player_claim,
                         "player_assertion": t.player_assertion,
                         "reactions": list(t.reactions), "phrasings": t.phrasings}
                   for tid, t in w.topics.items()},
        "agents": {a.id: {
            "big_five": a.big_five, "schwartz": a.schwartz, "needs": a.needs,
            "identities": list(a.identities), "roles": list(a.roles),
            "appearance": a.appearance, "education": a.education,
            "relationships": {k: dict(v) for k, v in a.relationships.items()},
            "secrets": [s.avoid_label for s in a.secrets],
            "goals": list(a.goals), "location": a.location,
            "public_name": a.public_name, "objective_name": a.objective_name,
            "aliases": list(a.aliases),
            "routine": [list(b) for b in a.routine.blocks],
            "social_status": a.social_status, "resources": a.resources,
            "dialect": a.dialect, "values": a.values, "epistemic": a.epistemic,
            "networks": list(a.networks), "voice": a.voice,
            "contacts": list(a.contacts),
            "affect": a.affect.as_dict(),
        } for a in w.agents.values()},
        "media_exposure": [{"agent": k[0], "channel": k[1], "value": v}
                           for k, v in w.media_exposure.items()],
        "factions": list(w.factions),
        "scenario_events": [{"event_id": e.event_id, "world_time": e.world_time,
                             "type": e.type, "actor": e.actor,
                             "location": e.location, "payload": e.payload,
                             "canonical": e.canonical}
                            for e in w.scenario_events],
        "scenario_intro": w.scenario_intro,
        "focus_agents": list(w.focus_agents),
        "player_start": w.player_start,
        "initial_beliefs": list(w.initial_beliefs),
        "next_event_id": w._next_event_id,
    }


def run_metahuman(scenario: dict) -> dict:
    from unscripted import metahuman
    out = []
    for row in scenario["cases"]:
        affect = AffectState(mood=Vec3(*row["mood"]), baseline=Vec3(*row["baseline"]),
                             active_emotions=dict(row["emotions"]))
        out.append({
            "note": row["note"],
            "blendshapes": metahuman.affect_to_blendshapes(affect),
            "dominant": list(metahuman.dominant_emotion(affect)),
            "face": metahuman.affect_to_face(
                affect, action_tendencies=dict(row["tendencies"]) or None,
                gaze_target="agent:player_1"),
        })
    return {"faces": out}


def run_sdk(scenario: dict) -> dict:
    packs = os.path.join(os.path.dirname(HERE), "..", "..", "worldpacks")
    out = {}
    for row in scenario["runs"]:
        reset_predicates()
        root = os.path.join(HERE, row["root"]) if row.get("root") else packs
        config = RuntimeConfig(world_pack_path=os.path.join(root, row["pack"]),
                               storage_path=":memory:",
                               **{name: True for name in row["layers"]})
        world = load_world_pack(config.world_pack_path)
        start = config.player_start_location or world.player_start
        if config.player_id not in world.agents:
            world.agents[config.player_id] = Agent(
                id=config.player_id, location=start,
                big_five={"agreeableness": 0.5, "emotional_stability": 0.5})
        else:
            world.agents[config.player_id].location = start
        sdk = UnscriptedRuntime(config, world)
        sdk.core.routine.seed(world)
        sdk.load_initial_state()
        # The seed belongs to the WORLD, not to the config: a fixture that did
        # not pin it would be reproducing the pack's seed and calling it proof.
        # Set AFTER the pack is in place, exactly as the conformance driver does.
        world.global_seed = row["seed"]
        transcript = []
        for command in row["commands"]:
            result = sdk.submit_player_text(command)
            transcript.append({
                "input": command,
                "message": (result.message or "").strip(),
                "intent": result.parsed.intent,
                "target": result.parsed.target_id,
                "topic": result.parsed.topic,
                "world_time": result.world_time,
                # The watermark after every turn. A divergence in how many
                # ids a turn consumed is otherwise invisible until it
                # changes a seeded draw two turns later.
                "next_event_id": world._next_event_id,
                "location": result.location_id,
                "receipts": [{"event_id": r.event_id, "type": r.event_type,
                              "observed_by": list(r.observed_by)}
                             for r in result.receipts],
                "npc": (None if result.npc_response is None else {
                    "text": result.npc_response.text,
                    "act": result.npc_response.act,
                    "verdict": result.npc_response.verdict,
                    "reasons": [list(x) for x in result.npc_response.reasons]}),
            })
        views = {"world": state_view.world_state(sdk),
                 "scene": sdk.structured_scene(),
                 "knowledge": state_view.knowledge_state(sdk),
                 "agents": {aid: state_view.agent_state(sdk, aid)
                            for aid in sorted(world.agents)}}
        # The store-backed diffusion log has no counterpart in the port; the key
        # is compared for SHAPE and its contents are not.
        views["knowledge"]["transmissions"] = []
        out[row["id"]] = {"transcript": transcript, "state": sdk.export_state(),
                          "views": views}
    reset_predicates()
    return out


def run_pack_loader(scenario: dict) -> dict:
    packs = os.path.join(os.path.dirname(HERE), "..", "..", "worldpacks")
    out = {}
    for row in scenario["packs"]:
        reset_predicates()
        # `root` is relative to the PROBE directory, not to the repository:
        # a pack written for the probe lives beside it.
        root = os.path.join(HERE, row["root"]) if row.get("root") else packs
        world = load_world_pack(os.path.join(root, row["pack"]))
        out[row["pack"]] = {
            "world": _pack_world_dump(world),
            "registered": sorted(_PREDICATE_SOURCES),
        }
    reset_predicates()
    return out


def run_inspect(scenario: dict) -> dict:
    t = scenario["world_time"]
    views = []
    for row in scenario["agents"]:
        agent = Agent(id=row["id"])
        a = row["affect"]
        agent.affect = AffectState(
            mood=Vec3(*a["mood"]), baseline=Vec3(*a["baseline"]),
            active_emotions=dict(a["active_emotions"]))
        for b in row["beliefs"]:
            claim = Proposition(b["predicate"], dict(b["slots"]))
            belief = Belief(proposition=claim)
            belief.provenance = [dict(p) for p in b["provenance"]]
            for p in b["provenance"]:
                belief.support_for += p["kappa"] * p["eta"]
            agent.beliefs[claim.core_key()] = belief
        for m in row["memory"]:
            agent.memory.append(Memory(
                memory_id=m["memory_id"], owner=agent.id, type=m["type"],
                content=m["content"], importance=m["importance"],
                emotional_valence=m["emotional_valence"],
                source_conf=m["source_conf"], world_time=m["world_time"]))
        views.append({
            "agent": agent.id,
            "beliefs": fmt_beliefs(agent),
            "memory": fmt_memory(agent, t),
            "affect": fmt_affect(agent),
        })

    runtime = _FakeInspectRuntime({
        key: [(code, mag, detail) for code, mag, detail in rows]
        for key, rows in scenario["traces"].items()})
    traces = [{"agent": aid, "text": fmt_last_trace(runtime, aid)}
              for aid in ["agent:busy", "agent:blank", "agent:missing"]]

    return {"views": views, "traces": traces,
            "tuples": [repr(tuple(row)) for row in scenario["tuples"]]}


def run_snapshot(scenario: dict) -> dict:
    import hashlib
    digests = [hashlib.sha256(text.encode("utf-8")).hexdigest()
               for text in scenario["sha256"]]

    setup = scenario["world"]
    world = World()
    world.global_seed = setup["global_seed"]
    for aid in setup["agents"]:
        world.agents[aid] = Agent(id=aid)
    world.places = {pid: {} for pid in setup["places"]}
    world.topics = {tid: Topic.from_dict({"id": tid}) for tid in setup["topics"]}
    fingerprint = world_fingerprint(world)

    base = {"format": "unscripted-state", "format_version": 1,
            "runtime_version": "probe", "snapshot_schema_version": 10,
            "world_fingerprint": fingerprint,
            "agents": sorted(world.agents), "world_time": 1234,
            "state": {"world_time": 1234}}
    checked = []
    for change in scenario["variants"]:
        blob = dict(base)
        for key, value in change.items():
            if key == "note":
                continue
            blob[key] = value
        if "not_an_object" in change:
            blob = ["not", "an", "object"]
        checked.append({"note": change["note"],
                        "report": inspect_state(blob, world)})

    return {"sha256": digests, "fingerprint": fingerprint, "variants": checked}


def run_runtime(scenario: dict) -> dict:
    world = World()
    world.global_seed = scenario["global_seed"]
    world.world_time = scenario["world_time"]
    world.places = {k: dict(v) for k, v in scenario["places"].items()}
    world.channels = {k: dict(v) for k, v in scenario["channels"].items()}
    world.predicate_domains = dict(scenario["predicate_domains"])
    world.predicate_competence = dict(scenario["predicate_competence"])
    world.predicates = dict(scenario["predicates"])
    world.identity_values = dict(scenario["identity_values"])
    world.factions = [dict(f) for f in scenario["factions"]]
    world.standing_conduct = dict(scenario["standing_conduct"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], location=row["location"], public_name=row["public_name"],
            education=dict(row["education"]),
            epistemic=dict(row["epistemic"]), big_five=dict(row["big_five"]),
            relationships={k: dict(v) for k, v in row["relationships"].items()},
            identities=list(row["identities"]), roles=list(row["roles"]),
            routine=Routine.from_list(row["routine"]), goals=list(row["goals"]),
            aliases=tuple(row["aliases"]))

    for row in scenario["media_exposure"]:
        world.media_exposure[(row["agent"], row["channel"])] = dict(row["value"])

    rt = Runtime(world)
    log, dumps = [], []
    last_intent = None
    for step in scenario["steps"]:
        kind = step["do"]
        if kind == "process_event":
            traces = rt.process_event(_runtime_event(step["event"]))
            log.append({"step": kind,
                        "traces": {k: reasons_of(v) for k, v in traces.items()}})
        elif kind == "player_says":
            traces = rt.player_says(step["speaker"], step["location"],
                                    Proposition.from_dict(step["proposition"]),
                                    summary=step["summary"],
                                    importance=step["importance"])
            log.append({"step": kind,
                        "traces": {k: reasons_of(v) for k, v in traces.items()}})
        elif kind == "advance_time":
            rt.advance_time(step["delta"])
            log.append({"step": kind, "delta": step["delta"]})
        elif kind == "enable_layers":
            rt.standing.enabled = True
            rt.climate.enabled = True
            rt.pursuit.enabled = True
            rt.pursuit.notes = bool(step.get("notes"))
            rt.contagion.enabled = True
            rt.common_knowledge.enabled = True
            rt.notes.enabled = True
            rt.promises.enabled = True
            rt.actions_out.enabled = True
            log.append({"step": kind})
        elif kind == "inspect":
            views = []
            for aid in step["agents"]:
                agent = world.agents.get(aid)
                views.append({
                    "agent": aid,
                    "beliefs": fmt_beliefs(agent) if agent else None,
                    "memory": fmt_memory(agent, world.world_time) if agent else None,
                    "affect": fmt_affect(agent) if agent else None,
                    "trace": fmt_last_trace(rt, aid),
                })
            log.append({"step": kind, "views": views})
        elif kind == "export":
            log.append({"step": kind, "blob": export_state(world, rt)})
        elif kind == "round_trip":
            saved = export_state(world, rt)
            rt.advance_time(step["delta"])
            rt.process_event(_runtime_event(step["event"]))
            say = step["say"]
            rt.player_says(say["speaker"], say["location"],
                           Proposition.from_dict(say["proposition"]),
                           summary=say["summary"], importance=say["importance"])
            report, reasons = import_state(saved, world, rt)
            log.append({"step": kind, "report": report,
                        "reasons": reasons_of(reasons)})
        elif kind == "restore_variants":
            saved = capture(world, rt)
            seen = []
            for change in step["changes"]:
                blob = {k: v for k, v in saved.items() if k not in change["drop"]}
                blob.update({k: v for k, v in change.items()
                             if k not in ("drop", "note")})
                gone = set(change.get("forget_agents") or ())
                if change.get("forget_agent"):
                    gone.add(change["forget_agent"])
                if gone:
                    blob["agents"] = {a: v for a, v in blob["agents"].items()
                                      if a not in gone}
                if change.get("invent_agent"):
                    blob["agents"] = dict(blob["agents"])
                    blob["agents"][change["invent_agent"]] = {}
                reasons = restore(blob, world, rt)
                seen.append({"note": change["note"], "reasons": reasons_of(reasons),
                             "last_decay": dict(rt._last_decay),
                             "next_event_id": world._next_event_id,
                             "scheduled": len(world.scenario_events)})
            # Put the real one back, so what follows is not built on a doctored
            # world.
            restore(saved, world, rt)
            log.append({"step": kind, "variants": seen})
        elif kind == "import_variants":
            base = export_state(world, rt)
            seen = []
            for change in [{"format": "nope"}, {"format_version": 99},
                           {"snapshot_schema_version": 99},
                           {"world_fingerprint": "0000000000000000"},
                           {"agents": ["agent:nobody"]}]:
                blob = dict(base)
                blob.update(change)
                report = inspect_state(blob, world)
                entry = {"change": sorted(change), "report": report}
                try:
                    _, reasons = import_state(blob, world, rt)
                    entry["reasons"] = reasons_of(reasons)
                except StateImportError as error:
                    entry["error"] = str(error)
                seen.append(entry)
            log.append({"step": kind, "variants": seen})
        elif kind == "schedule":
            world.scenario_events.append(_runtime_event(step["event"]))
            log.append({"step": kind, "event_id": step["event"]["event_id"]})
        elif kind == "population_lod":
            rt.population_lod = True
            log.append({"step": kind})
        elif kind == "issue_intent":
            intent = rt.actions_out.issue(
                actor=step["actor"], type="MOVE_TO",
                params={"place": step["place"], "activity": step["activity"]},
                reason="probe", world_time=world.world_time)
            last_intent = intent.intent_id
            log.append({"step": kind, "intent": intent.as_dict()})
        elif kind == "resolve_action":
            try:
                result = rt.resolve_action(last_intent, step["status"])
                # The reasons come back as Python TUPLES, and the bit-comparison
                # only recurses into lists and dicts -- so a tuple would sail
                # through with its floats unconverted and compare against
                # nothing.
                result["reasons"] = [list(r) for r in result["reasons"]]
                log.append({"step": kind, "result": result})
            except (ValueError, LookupError) as error:
                log.append({"step": kind, "error": type(error).__name__})
        elif kind == "decide":
            chosen, scored, reasons = rt.decide(
                step["agent"], interlocutor=step["interlocutor"],
                situation=step.get("situation"))
            log.append({"step": kind, "chosen": chosen.action.action_id,
                        "utility": chosen.utility,
                        "scored": [{"action": c.action.action_id, "utility": c.utility,
                                    "contributions": [list(x) for x in c.contributions]}
                                   for c in scored],
                        "reasons": reasons_of(reasons)})
        elif kind == "say":
            spoken = rt.say(step["agent"], interlocutor=step["interlocutor"])
            log.append({"step": kind, "text": spoken["text"], "act": spoken["act"],
                        "style": spoken["style"], "utility": spoken["utility"],
                        "verdict": spoken["verdict"],
                        "salient_identity": spoken["salient_identity"],
                        "reasons": reasons_of(spoken["reasons"])})
        elif kind == "mobilize":
            out = rt.mobilize(step["agent"])
            log.append({"step": kind,
                        "responders": [r.ally_id for r in out["responders"]],
                        "reasons": reasons_of(out["reasons"])})
        elif kind == "dump":
            dumps.append(_runtime_dump(world, rt))
            log.append({"step": kind})
    return {"log": log, "dumps": dumps}


def run_provider(scenario: dict) -> dict:
    realizer = TemplateRealizer(templates=scenario["templates"], slang=scenario["slang"])

    plans = []
    for row in scenario["plans"]:
        moves = []
        for m in row["moves"]:
            prop = (Proposition(m["predicate"], dict(m["slots"]))
                    if m["predicate"] else None)
            moves.append(SemanticMove(act=m["act"], proposition=prop,
                                      certainty=m["certainty"]))
        plans.append(DialoguePlan(
            speaker=row["speaker"], addressee=row["addressee"],
            dialogue_act=row["act"], goal=row["goal"],
            allowed_facts=list(row["allowed_facts"]),
            avoid_topics=list(row["avoid_topics"]), phrasing=dict(row["phrasing"]),
            max_length=row["max_length"], moves=moves))

    realized = []
    for plan_index, plan in enumerate(plans):
        for style_index, style in enumerate(scenario["styles"]):
            text = realizer.realize(plan, style)
            realized.append({"plan": plan_index, "style": style_index, "text": text,
                             "expressed_commitment": realizer.expressed_commitment,
                             "register": TemplateRealizer._register(
                                 style.get("formality", 0.5))})

    prompts = [{"plan": i, "style": j,
                "prompt": HttpChatRealizer._build_user_prompt(plans[i], style)}
               for i in range(len(plans))
               for j, style in enumerate(scenario["styles"])]

    cleaned = [{"reply": reply, "cap": cap,
                "cleaned": HttpChatRealizer._clean(reply, cap)}
               for reply in scenario["replies"] for cap in scenario["caps"]]

    return {
        "templates": {act: dict(v) for act, v in realizer.templates.items()},
        "realized": realized,
        "prompts": prompts,
        "cleaned": cleaned,
        "system": HttpChatRealizer.SYSTEM,
    }


def run_actionbridge(scenario: dict) -> dict:
    bridge = ActionBridge(enabled=True, timeout_minutes=scenario["timeout_minutes"])
    issued, log = [], []

    def note(step, **fields):
        log.append({"step": step["do"], **fields})

    for step in scenario["steps"]:
        kind = step["do"]
        try:
            if kind == "issue":
                intent = bridge.issue(actor=step["actor"], type=step["type"],
                                      params=step["params"], reason=step["reason"],
                                      world_time=step["world_time"])
                issued.append(intent)
                note(step, intent=intent.as_dict())
            elif kind == "resolve":
                record = bridge.resolve(issued[step["intent"]].intent_id,
                                        step["status"], world_time=step["world_time"],
                                        detail=step["detail"])
                note(step, record=record.as_dict())
            elif kind == "expire":
                note(step, expired=[r.as_dict()
                                    for r in bridge.expire(step["world_time"])])
            elif kind == "pending":
                note(step, pending=[i.as_dict() for i in bridge.pending()])
            elif kind == "pending_for":
                note(step, pending=[i.as_dict()
                                    for i in bridge.pending_for(step["actor"])])
            elif kind == "has_pending":
                note(step, answer=bridge.has_pending(step["actor"], step["type"]))
            elif kind == "report":
                note(step, report=bridge.report())
            elif kind == "as_dict":
                note(step, state=bridge.as_dict())
            elif kind == "recent":
                note(step, recent=[r.as_dict() for r in bridge.recent(step["limit"])])
        except (ValueError, LookupError) as error:
            # The MESSAGE is part of the contract: an integrator reads it over
            # HTTP, so the two implementations have to say the same thing.
            note(step, error=type(error).__name__, message=str(error))

    reloaded = []
    for raw in scenario["reload"]:
        again = ActionBridge.from_dict(raw)
        reloaded.append({"state": again.as_dict(), "report": again.report()})

    return {"log": log, "reloaded": reloaded}


def run_validator(scenario: dict) -> dict:
    setup = scenario["world"]
    world = World()
    world.places = {pid: dict(attrs) for pid, attrs in setup["places"].items()}
    world.entities = {eid: dict(attrs) for eid, attrs in setup["entities"].items()}
    world.predicates = dict(setup["predicates"])
    world.decorative_vocabulary = list(setup["decorative_vocabulary"])
    for row in setup["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], public_name=row["public_name"],
            objective_name=row["objective_name"], aliases=tuple(row["aliases"]),
            secrets=secrets_from(row["secrets"], owner=row["id"]))
    world.topics = {row["id"]: Topic.from_dict(row) for row in setup["topics"]}

    plans = [DialoguePlan(speaker=row["speaker"], addressee=row["addressee"],
                          dialogue_act="assert", goal=row["goal"],
                          allowed_facts=list(row["allowed_facts"]),
                          avoid_topics=list(row["avoid_topics"]),
                          phrasing=dict(row["phrasing"]))
             for row in scenario["plans"]]
    speaker = world.agents["agent:byrne"]

    checks = []
    for window in scenario["windows"]:
        validator = Validator.for_world(world, repetition_window=window)
        for mode in scenario["modes"]:
            for plan_index, plan in enumerate(plans):
                for utterance in scenario["utterances"]:
                    result = validator.check(utterance, plan, speaker,
                                             scenario["recent"], canon_mode=mode)
                    checks.append({
                        "window": window, "mode": mode, "plan": plan_index,
                        "utterance": utterance, "verdict": result.verdict,
                        "reasons": [list(r) for r in result.reasons],
                        "unlicensed": result.unlicensed,
                    })

    validator = Validator.for_world(world)
    specifics = [{"plan": i, "utterance": u,
                  "found": validator.unlicensed_specifics(u, plans[i])}
                 for i in range(len(plans)) for u in scenario["utterances"]]

    return {
        "world_terms": dict(validator.world_terms),
        "surface_forms": {k: list(v) for k, v in validator.secret_surface_forms.items()},
        "licence": [Validator._licence_text(p) for p in plans],
        "unprotected": [validator.unprotected_labels(rows)
                        for rows in scenario["unprotected"]],
        "specifics": specifics,
        "checks": checks,
    }


def run_parser(scenario: dict) -> dict:
    world = World()
    world.places = {pid: dict(attrs) for pid, attrs in scenario["places"].items()}
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], location=row["location"], aliases=tuple(row["aliases"]),
            public_name=row["public_name"], objective_name=row["objective_name"])
    world.topics = {row["id"]: Topic.from_dict(row) for row in scenario["topics"]}
    world.appearance_reactions = dict(scenario["appearance_reactions"])
    world.command_aliases = dict(scenario["command_aliases"])

    provider = RuleBasedParserProvider()
    lexicon = provider._lexicon(world)

    parsed = []
    for line in scenario["lines"]:
        command = provider.parse(line, player_id=scenario["player_id"],
                                 player_location=scenario["player_location"],
                                 world=world)
        row = command.as_dict()
        row["reasons"] = [list(reason) for reason in row["reasons"]]
        parsed.append({"line": line, "command": row})

    return {
        "normalized": [normalize(line) for line in scenario["lines"]],
        "lexicon": {intent: list(words) for intent, words in lexicon.items()},
        "places": [list(entry) for entry in world.place_alias_index().entries],
        "agents": [list(entry) for entry in world.agent_alias_index().entries],
        "topics": [list(entry) for entry in world.topic_alias_index().entries],
        "parsed": parsed,
    }


def run_interpretation(scenario: dict) -> dict:
    world = World()
    world.global_seed = scenario["global_seed"]
    world.world_time = scenario["world_time"]
    world.predicate_domains = dict(scenario["predicate_domains"])
    world.predicate_competence = dict(scenario["predicate_competence"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], education=dict(row["education"]),
            epistemic=dict(row["epistemic"]),
            relationships={k: dict(v) for k, v in row["relationships"].items()})

    props = [None if row is None else Proposition.from_dict(row)
             for row in scenario["propositions"]]
    events = [Event(event_id=row["event_id"], world_time=row["world_time"],
                    type=row["type"], actor=row["actor"], location=row["location"],
                    payload=row["payload"]) for row in scenario["events"]]

    engine = InterpretationEngine()
    outcomes = []
    for row in scenario["runs"]:
        agent = world.agents[row["agent"]]
        claim = props[row["proposition"]]
        event = events[row["event"]]
        score, why = engine.attention(agent, event, claim, world, row["quality"])
        held, reasons = engine.interpret(agent, event, claim, world,
                                         row["quality"], modality=row["modality"])
        outcomes.append({
            "agent": row["agent"], "event": row["event"],
            "proposition": row["proposition"], "quality": row["quality"],
            "modality": row["modality"],
            "attention": score, "attention_reasons": reasons_of(why),
            "held": None if held is None else held.as_dict(),
            "core_key": None if held is None else held.core_key(),
            "reasons": reasons_of(reasons),
        })

    recognised = []
    for row in scenario["recognises"]:
        ok, have, detail = engine.recognises(world.agents[row["agent"]],
                                             props[row["proposition"]], world)
        recognised.append({"agent": row["agent"], "proposition": row["proposition"],
                           "known": ok, "have": have, "detail": detail})

    noise = [{"agent": row["agent"], "event_id": row["event_id"], "salt": row["salt"],
              "value": seeded_noise(world, row["agent"], row["event_id"], row["salt"])}
             for row in scenario["noise"]]

    return {"outcomes": outcomes, "recognises": recognised, "noise": noise}


def run_grounding(scenario: dict) -> dict:
    topics = [Topic.from_dict(row) for row in scenario["topics"]]
    world = FakeWorldLexicon(scenario["world"], topics)
    lexicon = WorldLexicon.build(world)

    flagged = [{"text": row["text"],
                "unknown": unknown_referents(row["text"], world,
                                             licensed=row["licensed"])}
               for row in scenario["sentences"]]

    propositions = [None if row is None else Proposition.from_dict(row)
                    for row in scenario["propositions"]]

    said = [{"text": row["text"], "proposition": row["proposition"],
             "expresses": expresses(row["text"],
                                    propositions[row["proposition"]], world)}
            for row in scenario["expresses"]]

    return {
        "terms": {phrase: list(entry) for phrase, entry in lexicon.terms.items()},
        "decorative": sorted(lexicon.decorative),
        "unknown_referents": flagged,
        "anchors": [anchors_for(p, world) for p in propositions],
        "expresses": said,
    }


def run_flat(scenario: dict) -> dict:
    flat = FlatWorld()
    predicate = scenario["predicate"]
    # `run()` loads a world pack; the events are supplied here instead so this
    # tests the model rather than the loader.
    # `broadcast` returns how many flags it actually SET, which is almost never
    # all of them -- a boolean cannot be set twice, and that is the finding.
    broadcasts = []
    for event in scenario["scenario_events"]:
        payload = event["payload"] or {}
        if (payload.get("proposition") or {}).get("predicate") == predicate:
            broadcasts.append(flat.broadcast(predicate, scenario["agents"]))
    told = [flat.tell(telling["from"], telling["to"], predicate,
                      honest=not telling.get("lie", False))
            for telling in scenario["tellings"]]

    answers = []
    for who, fact in scenario["questions"]:
        answers.append({"agent": who, "fact": fact,
                        "how_sure": flat.how_sure(who, fact),
                        "who_told": flat.who_told(who, fact),
                        "which_version": flat.which_version(who, fact),
                        "told_how_often": flat.told_how_often(who, fact),
                        "was_it_a_lie": flat.was_it_a_lie(who, fact),
                        "who_knows": flat.who_knows(fact)})

    return {
        "state": {"facts": sorted(flat.facts),
                  "known": {k: sorted(v) for k, v in flat.known.items()},
                  "tellings": flat.tellings},
        "questions": answers,
        "discredit": [flat.discredit(who) for who in scenario["discredit"]],
        "forgets": flat.forgets(),
        "broadcast_changed": broadcasts,
        "tell_changed": told,
    }


class TuningCore:
    """Every engine that has parameters, so `tuning` can find them by name."""

    def __init__(self):
        self.belief = BeliefEngine()
        self.memory = MemoryEngine()
        self.affect = AffectEngine()
        self.diffusion = DiffusionEngine()
        self.pursuit = PursuitEngine()
        self.contagion = ContagionEngine()
        self.notes = NoteBoard()
        self.promises = PromiseLedger()
        self.common_knowledge = CommonKnowledgeEngine()
        self.policy = PolicyEngine()
        self.relationship = RelationshipEngine()
        self.reputation = ReputationEngine()
        self.identity = IdentityEngine()
        self.socioling = SociolinguisticEngine()


def _table(core) -> dict:
    return {name: dict(getattr(core, name).params) for name in TUNABLE
            if isinstance(getattr(getattr(core, name, None), "params", None), dict)}


def run_tuning(scenario: dict) -> dict:
    out = {"parameters": _table(TuningCore()), "tunable": dict(TUNABLE)}

    applied = []
    for block in scenario["blocks"]:
        core = TuningCore()
        reasons = reasons_of(apply_tuning(core, block))
        applied.append({"block": block, "reasons": reasons, "after": _table(core)})
    out["applied"] = applied

    # The messages are compared too, because "did you mean" is the entire value
    # of refusing: a rejection that does not say what was meant is a wall.
    refusals = []
    for block in scenario["refusals"]:
        core = TuningCore()
        entry = {"block": block}
        try:
            apply_tuning(core, block)
            entry["refused"] = False
        except TuningError as error:
            entry["refused"] = True
            entry["message"] = str(error)
        refusals.append(entry)
    out["refusals"] = refusals

    out["describe"] = describe_tuning(TuningCore())

    # A build missing a layer warns rather than refusing, because a studio that
    # declined a mechanic should not be told their pack is broken.
    class Partial(TuningCore):
        def __init__(self):
            super().__init__()
            self.contagion = object()

    out["warnings"] = check_tuning({"contagion": {"transfer": 0.5}}, Partial())
    return out


def run_revision(scenario: dict) -> dict:
    world = World()
    for row in scenario["agents"]:
        agent = Agent(id=row["id"])
        for belief_row in row["beliefs"]:
            proposition = Proposition.from_dict(belief_row)
            proposition.polarity = "+"
            belief = Belief(proposition=proposition, logit_val=belief_row["logit"],
                            support_for=belief_row["support_for"],
                            support_against=belief_row["support_against"],
                            provenance=[dict(r) for r in belief_row["provenance"]])
            # The arithmetic ledger is rebuilt from the provenance, exactly as
            # `from_dict` does for a save written before it existed. Without
            # it both sides revise nothing and the case passes vacuously --
            # which is what happened the moment revision started reading
            # `contributions` instead of the provenance list.
            for record in belief.provenance:
                delta = float(record.get("delta") or 0.0)
                if not delta:
                    continue
                bucket = belief.contributions.setdefault(
                    contribution_key(record.get("speaker"), record.get("origin_event")),
                    [0.0, 0.0])
                bucket[0 if delta > 0 else 1] += delta
            agent.beliefs[proposition.core_key()] = belief
        world.agents[row["id"]] = agent

    out = {"would_change": {source: would_change(world, source)
                            for source in scenario["preview_sources"]}}

    passes = []
    for row in scenario["discredits"]:
        revision = discredit(world, row["source"], factor=row["factor"],
                             reason=row["reason"], predicate=row["predicate"])
        entry = revision.as_dict()
        entry["reasons"] = reasons_of(revision.reasons)
        passes.append(entry)
    out["discredits"] = passes

    out["beliefs_after"] = {name: {key: b.as_dict() for key, b in a.beliefs.items()}
                            for name, a in world.agents.items()}
    return out


class PursuitRuntime:
    """Diffusion, a note board and an event ledger -- what pursuit reaches for."""

    def __init__(self, notes_enabled):
        self.diffusion = DiffusionEngine()
        self.network = SocialNetworkEngine()
        self.notes = NoteBoard(enabled=notes_enabled)
        self.events = []

    def process_event(self, event):
        self.events.append({"event_id": event.event_id, "actor": event.actor,
                            "location": event.location, "payload": event.payload})


def run_pursuit(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"],
                  places=scenario["places"], predicates=scenario["predicates"])
    for row in scenario["agents"]:
        agent = Agent(id=row["id"], location=row["location"],
                      contacts=tuple(row["contacts"]), goals=list(row["goals"]),
                      relationships={k: dict(v)
                                     for k, v in row["relationships"].items()})
        for belief_row in row["beliefs"]:
            proposition = Proposition.from_dict(belief_row)
            proposition.polarity = "+"
            belief = Belief(proposition=proposition, logit_val=belief_row["logit"],
                            hops=belief_row["hops"])
            belief.origin_counts = dict(belief_row["origin_counts"])
            agent.beliefs[proposition.core_key()] = belief
        world.agents[row["id"]] = agent

    runtime = PursuitRuntime(scenario["notes"])
    engine = PursuitEngine(enabled=scenario["enabled"], media=scenario["media"])
    engine.notes = scenario["notes"]

    steps = []
    for row in scenario["steps"]:
        world.world_time = row["to"]
        steps.append({"to": row["to"],
                      "reasons": reasons_of(engine.step(world, runtime, row["delta"],
                                                        scenario["player_id"] or None))})

    restored = PursuitEngine(enabled=scenario["enabled"], media=scenario["media"])
    restored.restore(engine.as_dict())

    return {"steps": steps, "events": runtime.events,
            "notes": runtime.notes.report(), "state": engine.as_dict(),
            "restored": restored.as_dict()}


class NoteRuntime:
    """What the board reaches through the runtime for: the fidelity curve, and
    somewhere to put the claim a read note becomes."""

    def __init__(self):
        self.diffusion = DiffusionEngine()
        self.events = []

    def process_event(self, event):
        self.events.append({"event_id": event.event_id, "actor": event.actor,
                            "location": event.location, "payload": event.payload})


def run_notes(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], location=row["location"],
            epistemic={"curiosity": row["curiosity"]},
            secrets=secrets_from(row["secrets"]))

    beliefs = []
    for row in scenario["beliefs"]:
        proposition = Proposition.from_dict(row)
        proposition.polarity = "+"
        belief = Belief(proposition=proposition, logit_val=row["logit"],
                        hops=row["hops"])
        belief.origin_counts = dict(row["origin_counts"])
        beliefs.append(belief)

    runtime = NoteRuntime()
    board = NoteBoard(enabled=scenario["enabled"])

    written = []
    for row in scenario["leave"]:
        reasons = []
        belief = beliefs[row["belief"]]
        ok = board.leave(world, world.agents[row["author"]], row["for"],
                         row["place"], belief.proposition.core_key(), belief, reasons)
        written.append({"left": ok, "reasons": reasons_of(reasons)})

    steps = []
    for index, row in enumerate(scenario["steps"]):
        for move in scenario["moves"]:
            if move["at_step"] == index:
                world.agents[move["agent"]].location = move["to"]
        world.world_time = row["to"]
        steps.append({"to": row["to"],
                      "reasons": reasons_of(board.step(world, runtime, row["delta"])),
                      "still_lying": board.report()})

    restored = NoteBoard(enabled=scenario["enabled"])
    restored.restore(board.as_dict())

    return {"left": written, "steps": steps, "events": runtime.events,
            "board": board.as_dict(), "restored": restored.as_dict()}


class PromiseRuntime:
    """What the ledger reaches through the runtime for.

    The deltas are not invented in the ledger: SocialExchangeEngine has always
    known what a kept and a broken promise are worth, and the owners are still
    the only things that write the state.
    """

    def __init__(self):
        self.exchange = SocialExchangeEngine()
        self.relationship = RelationshipEngine()
        self.reputation = ReputationEngine()
        self.identity = IdentityEngine()
        self.socioling = SociolinguisticEngine()


def run_promises(scenario: dict) -> dict:
    world = World(world_time=scenario["world_time"])
    for row in scenario["agents"]:
        agent = Agent(id=row["id"])
        for belief_row in row["beliefs"]:
            proposition = Proposition.from_dict(belief_row)
            proposition.polarity = "+"
            agent.beliefs[proposition.core_key()] = Belief(
                proposition=proposition, logit_val=belief_row["logit"])
        world.agents[row["id"]] = agent

    ledger = PromiseLedger(enabled=scenario["enabled"])
    runtime = PromiseRuntime()

    made = []
    for row in scenario["promises"]:
        claim = Proposition(row["predicate"], dict(row["slots"]))
        claim.valid_end = row["valid_end"]
        event = Event(event_id=0, world_time=row["world_time"], type="promise",
                      actor=row["actor"],
                      payload={"proposition": claim.as_dict(), "target": row["target"],
                               **({"addressee": row["addressee"]}
                                  if "addressee" in row else {})})
        made.append({"actor": row["actor"], "target": row["target"],
                     "reasons": reasons_of(ledger.record(world, event, row["witnesses"]))})

    out = {"made": made, "open_after_recording": ledger.open_ids()}

    # The promisee comes to believe it happened, which is the only thing that
    # decides whether the promise was kept.
    for row in scenario["belief_moves"]:
        agent = world.agents.get(row["agent"])
        belief = agent.beliefs.get(row["key"]) if agent else None
        if belief is not None:
            belief.logit_val = row["logit"]

    forced = []
    for row in scenario["settle_explicitly"]:
        entry = {"promise": row["promise"]}
        try:
            entry["reasons"] = reasons_of(ledger.settle(world, runtime, row["promise"],
                                                        row["kept"], row["note"]))
        except KeyError:
            entry["refused"] = True
        forced.append(entry)
    out["settled_explicitly"] = forced

    steps = []
    for row in scenario["steps"]:
        world.world_time = row["to"]
        steps.append({"to": row["to"],
                      "reasons": reasons_of(ledger.step(world, runtime, row["delta"]))})
    out["steps"] = steps

    out["agents"] = {name: {"relationships": {k: dict(v)
                                              for k, v in a.relationships.items()},
                            "reputation": {k: dict(v) for k, v in a.reputation.items()}}
                     for name, a in world.agents.items()}
    out["report"] = ledger.report()
    out["ledger"] = ledger.as_dict()

    restored = PromiseLedger(enabled=scenario["enabled"])
    restored.restore(ledger.as_dict())
    out["restored"] = restored.as_dict()
    return out


class FakeWorldCrowd:
    """Places and a cast -- what the common-knowledge engine reads off a world."""

    def __init__(self, places, agents):
        self.places = places
        self.agents = agents


def run_common_knowledge(scenario: dict) -> dict:
    world = FakeWorldCrowd(scenario["places"],
                           {name: Agent(id=name) for name in scenario["agents"]})
    engine = CommonKnowledgeEngine(enabled=scenario["enabled"])

    rows = []
    for row in scenario["events"]:
        payload = dict(row["payload"])
        payload["proposition"] = row["proposition"]
        event = Event(event_id=0, world_time=row["world_time"], type=row["type"],
                      actor=row["actor"], location=row["location"], payload=payload)
        learned = [(who, quality) for who, quality in row["learned"]]
        rows.append({"at": row["world_time"], "type": row["type"],
                     "place": row["location"],
                     "reasons": reasons_of(engine.observe(world, event, learned))})

    answers = []
    for query in scenario["queries"]:
        answers.append({"key": query["key"], "among": query["among"],
                        "is_common": engine.is_common(query["key"], *query["among"]),
                        "publics": len(engine.publics_for(query["key"]))})

    restored = CommonKnowledgeEngine(enabled=scenario["enabled"])
    restored.restore(engine.as_dict())

    return {"observations": rows, "queries": answers,
            "is_out": [engine.is_out(key, who) for key, who in scenario["out_queries"]],
            "report": engine.report(), "state": engine.as_dict(),
            "restored": restored.as_dict()}


class FakeWorldPlaces:
    """Only what the climate engine reads off a world at construction."""

    def __init__(self, places):
        self.places = places


def run_climate(scenario: dict) -> dict:
    engine = ClimateEngine(FakeWorldPlaces(scenario["places"]),
                           enabled=scenario["enabled"])
    out = {
        "baselines": {name: baseline_for(place).as_dict()
                      for name, place in scenario["places"].items()},
        "modifiers_before": {**{name: engine.modifiers(name)
                                for name in scenario["places"]},
                             "place:nonexistent": engine.modifiers("place:nonexistent")},
    }

    reactions = []
    for row in scenario["events"]:
        event = Event(event_id=0, world_time=0, type=row["type"],
                      location=row["location"], payload=row["payload"])
        reactions.append({"event": row, "reasons": reasons_of(engine.react(event))})
    out["reactions"] = reactions

    out["walks"] = [{"walk": row,
                     "reasons": reasons_of(engine.carried(row["from"], row["to"]))}
                    for row in scenario["walks"]]

    steps = []
    for delta in scenario["steps"]:
        engine.step(None, delta)
        steps.append({"delta": delta, "state": engine.as_dict()})
    out["steps"] = steps

    out["walks_after_step"] = [
        {"walk": row, "reasons": reasons_of(engine.carried(row["from"], row["to"]))}
        for row in scenario.get("walks_after_step", [])]
    out["modifiers_after"] = {name: engine.modifiers(name) for name in scenario["places"]}
    out["report"] = engine.report()

    engine.restore(scenario["restore"])
    out["restored"] = engine.as_dict()
    out["report_after_restore"] = engine.report()
    return out


def run_contagion(scenario: dict) -> dict:
    cast = {}
    for row in scenario["agents"]:
        agent = Agent(id=row["id"], big_five=dict(row["big_five"]),
                      relationships={k: dict(v)
                                     for k, v in row["relationships"].items()})
        agent.affect.mood = Vec3.from_dict(row["mood"])
        cast[row["id"]] = agent

    engine = ContagionEngine(enabled=scenario["enabled"])
    exchanges = []
    for row in scenario["exchanges"]:
        speaker, listener = cast[row["from"]], cast[row["to"]]
        reasons = engine.between(speaker, listener)
        exchanges.append({"from": row["from"], "to": row["to"],
                          "reasons": reasons_of(reasons),
                          "listener_mood": listener.affect.mood.as_dict()})
    return {"exchanges": exchanges,
            "final_moods": {name: a.affect.mood.as_dict() for name, a in cast.items()}}


def run_medium(scenario: dict) -> dict:
    cast = {}
    for row in scenario["agents"]:
        cast[row["id"]] = Agent(id=row["id"], location=row["location"],
                                contacts=tuple(row["contacts"]),
                                relationships={k: dict(v)
                                               for k, v in row["relationships"].items()})

    exchanges = []
    for speaker_id, listener_id in scenario["pairs"]:
        for enabled in (True, False):
            chosen = for_exchange(cast[speaker_id], cast[listener_id], enabled=enabled)
            exchanges.append({"speaker": speaker_id, "listener": listener_id,
                              "layer_on": enabled,
                              "medium": chosen.name if chosen else None})

    table = []
    for name in scenario["media"]:
        one = BY_NAME.get(name)
        entry = {"name": name, "known": one is not None}
        if one is not None:
            entry.update({"fidelity": one.fidelity, "audience": one.audience,
                          "needs_colocation": one.needs_colocation,
                          "trust_factor": one.trust_factor,
                          "distortion_scale": one.distortion_scale(),
                          "described": describe_medium(one)})
        table.append(entry)

    return {"contacts": {name: sorted(contacts_of(a)) for name, a in cast.items()},
            "exchanges": exchanges, "media": table}


def run_agency(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(
            id=row["id"], location=row["location"],
            social_status=row["social_status"], resources=row["resources"],
            roles=list(row["roles"]), identities=list(row["identities"]),
            big_five=dict(row["big_five"]), needs=dict(row["needs"]),
            secrets=secrets_from(row["secrets"]),
            relationships={k: dict(v) for k, v in row["relationships"].items()})

    calls = []
    for who in scenario["callers"]:
        caller = world.agents[who]
        reachable = [a.id for a in potential_allies(caller, world)]
        for urgency in scenario["urgencies"]:
            for event_id in scenario["event_ids"]:
                built = mobilization_candidate(caller, world, urgency=urgency,
                                               event_id=event_id)
                entry = {"caller": who, "urgency": urgency, "event_id": event_id,
                         "reachable": reachable}
                if built is None:
                    entry["mobilization"] = None
                else:
                    action, responses = built
                    entry["mobilization"] = {
                        "action_id": action.action_id,
                        "action_class": action.action_class,
                        "outcomes": [{"dimension": o.dimension, "delta": o.delta,
                                      "probability": o.probability, "source": o.source}
                                     for o in action.outcomes]}
                    entry["responses"] = [{"ally": r.ally_id, "probability": r.probability,
                                           "latency": r.latency, "will_come": r.will_come}
                                          for r in responses]
                calls.append(entry)

    rules = default_reactive_rules()

    def broken(_agent, _ctx):
        raise RuntimeError("deliberately broken")

    # A rule that throws must be reported and must not stop the others.
    rules.append(ReactiveRule("broken_rule", condition=broken, action_id="nothing",
                              priority=0.0, reason="a rule from a pack, with a bug in it"))

    fired = []
    for context in scenario["contexts"]:
        reasons = []
        matched = fire_reactive_rules(world.agents["agent:boss"], context, rules, reasons)
        fired.append({"context": context, "fired": [r.rule_id for r in matched],
                      "failures": len(reasons)})

    setup = scenario["resolution"]
    resolutions = [[p, seed_name,
                    resolve(p, derive_seed(seed_name, "probe", 0, 0, "agency"))]
                   for p in setup["probabilities"] for seed_name in setup["seeds"]]

    return {
        "mobilization": calls,
        "leverage": [leverage(world.agents[a], world.agents[b])
                     for a, b in scenario["leverage_pairs"]],
        "authority": [authority(world.agents[a], world.agents[b])
                      for a, b in scenario["authority_pairs"]],
        "reactive_rules": fired,
        "resolution": resolutions,
        "risk_reference": {name: risk_reference_point(a)
                           for name, a in world.agents.items()},
    }


def run_dialogue(scenario: dict) -> dict:
    row = scenario["agent"]
    agent = Agent(id=row["id"], secrets=secrets_from(row["secrets"]))
    for belief_row in row["beliefs"]:
        proposition = Proposition.from_dict(belief_row)
        proposition.polarity = "+"
        belief = Belief(proposition=proposition, logit_val=belief_row["logit"],
                        support_for=belief_row["logit"])
        agent.beliefs[proposition.core_key()] = belief

    style = StyleVector(formality=scenario["style"]["formality"],
                        directness=scenario["style"]["directness"])
    second_row = scenario["second_agent"]
    second = Agent(id=second_row["id"], secrets=secrets_from(second_row["secrets"]))
    for belief_row in second_row["beliefs"]:
        proposition = Proposition.from_dict(belief_row)
        proposition.polarity = "+"
        second.beliefs[proposition.core_key()] = Belief(
            proposition=proposition, logit_val=belief_row["logit"],
            support_for=belief_row["logit"])

    planner = DialoguePlanner()

    plans = []
    for speaker in (agent, second):
      for act in scenario["acts"]:
        conv = ConversationState("conv:probe", [])
        chosen = ActionCandidate(action=ActionDefinition(
            "act", "share", is_dialogue=True, dialogue_act=act or None))
        plan = planner.plan(speaker, conv, chosen, addressee="agent:player_1",
                            style=style, goal="goal:find_out",
                            world_seed=scenario["world_seed"],
                            world_time=scenario["world_time"])
        entry = {"speaker": plan.speaker, "addressee": plan.addressee,
                 "dialogue_act": plan.dialogue_act, "goal": plan.goal,
                 "moves": [m.as_dict() for m in plan.moves],
                 "allowed_facts": list(plan.allowed_facts),
                 "avoid_topics": list(plan.avoid_topics), "stance": plan.stance,
                 "style": plan.style,
                 "fallback_template_id": plan.fallback_template_id,
                 "max_length": plan.max_length, "phrasing": plan.phrasing,
                 "request_id": plan.request_id, "asked_for": act,
                 "committed": len(plan.committed_propositions),
                 "turn_count": conv.turn_count}
        plans.append(entry)

    loops = []
    for one in scenario["anti_loop"]:
        conv = ConversationState("conv:loop", [])
        conv.last_acts = list(one["history"])
        loops.append({"history": one["history"], "act": one["act"],
                      "ok": planner.anti_loop_ok(conv, one["act"])})

    setup = scenario["conversation"]
    conv = ConversationState(setup["conv_id"], list(setup["participants"]))
    counts = [conv.note_topic(topic, when) for topic, when in setup["topics"]]

    return {"plans": plans, "anti_loop": loops, "topic_counts": counts,
            "conversation": conv.as_dict(),
            # And the round-trip, because a conversation has to survive a save.
            "restored": ConversationState.from_dict(conv.as_dict()).as_dict()}


def run_factions(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"])
    director = Director()
    for row in scenario["factions"]:
        director.add_faction(Faction.from_dict(row))

    heat = []
    for row in scenario["heat_events"]:
        director.add_heat(row["faction"], row["amount"], row["reason"], heat)

    scheduled = []

    def schedule(_world, _kind, faction, latency):
        scheduled.append({"faction": faction.faction_id, "latency": latency,
                          "at": world.world_time})

    steps = []
    for delta in scenario["steps"]:
        world.world_time += delta
        steps.append({"delta": delta,
                      "reasons": reasons_of(director.step(world, delta, schedule))})

    return {
        "heat": reasons_of(heat),
        "steps": steps,
        "scheduled": scheduled,
        "factions": {name: f.as_dict() for name, f in director.factions.items()},
        "controlling": {
            place: (director.faction_controlling(place).faction_id
                    if director.faction_controlling(place) else None)
            for place in scenario["territory_lookups"]},
    }


def run_commitment(scenario: dict) -> dict:
    seed_parts = tuple(scenario["seed_parts"])

    rows = []
    for row in scenario["cases"]:
        candidates = [Candidate(proposition=Proposition.from_dict(one),
                                confidence=one["confidence"],
                                relevance=one["relevance"], affirmed=one["affirmed"])
                      for one in row["candidates"]]
        commitment = select(candidates, act=row["act"], limit=row["limit"],
                            seed_parts=seed_parts, forbidden=row["forbidden"],
                            max_sentences=row["max_sentences"])
        entry = commitment.as_dict()
        entry["rendered_facts"] = commitment.rendered_facts()
        entry["factual_moves"] = len(commitment.factual_moves)
        entry["propositions"] = len(commitment.propositions)
        entry["reasons"] = reasons_of(commitment.reasons)
        rows.append(entry)

    deception = scenario["deception"]
    instead = Proposition.from_dict(deception["assert_instead"])
    held = Proposition("was_at", {"agent": "agent:vee", "place": "place:clinic",
                                  "when": 900})
    honest = SemanticMove(act="assert", proposition=held, certainty=CERTAIN,
                          believed_probability=0.93)

    lies = []
    for honesty in deception["honesty"]:
        lied = deceive(honest, assert_instead=instead, honesty=honesty)
        entry = lied.as_dict()
        entry["is_deceptive"] = lied.is_deceptive
        entry["is_factual"] = lied.is_factual
        lies.append(entry)

    return {
        "commitments": rows,
        "certainty": [[c, certainty_for(c)] for c in scenario["certainty_grid"]],
        "deception": lies,
        "honest_move": honest.as_dict(),
    }


def speaker_from(row: dict):
    agent = Agent(id=row["id"], social_status=row.get("social_status", 0.4),
                  dialect=row.get("dialect"),
                  education=dict(row.get("education", {})),
                  roles=list(row.get("roles", [])),
                  identities=list(row.get("identities", [])),
                  big_five=dict(row.get("big_five", {})),
                  relationships={k: dict(v)
                                 for k, v in row.get("relationships", {}).items()},
                  appearance=dict(row.get("appearance", {})),
                  reputation={k: dict(v)
                              for k, v in row.get("reputation", {}).items()})
    agent.affect.mood = Vec3.from_dict(row.get("mood", {}))
    agent.affect.active_emotions = dict(row.get("emotions", {}))
    return agent


def run_sociolinguistics(scenario: dict) -> dict:
    world = World(places=scenario["places"])
    for row in scenario["listeners"]:
        world.agents[row["id"]] = speaker_from(row)

    class FakeWorldReactions:
        def __init__(self, reactions):
            self.appearance_reactions = reactions

    engine = SociolinguisticEngine()
    appearance = AppearanceEngine()
    affect = AffectEngine()
    reactions_world = FakeWorldReactions(scenario["reactions"])
    # `world` carries the cast and the room formality; the appearance engine
    # needs `appearance_reactions`, which the real World also carries. Attaching
    # it here keeps one object where the Python signature expects one.
    world.appearance_reactions = scenario["reactions"]

    styles = []
    for speaker_row in scenario["speakers"]:
        speaker = speaker_from(speaker_row)
        for room in scenario["rooms"]:
            for listener in scenario["listeners"]:
                for regard in scenario["regards"]:
                    style = engine.compute_style(
                        speaker, interlocutor=listener["id"], place=room,
                        affect_engine=affect, world=world, regard=regard,
                        appearance=appearance)
                    styles.append({"speaker": speaker_row["id"], "room": room,
                                   "listener": listener["id"], "regard": regard,
                                   "style": style.as_dict()})
        # And with nobody in front of them, which skips accommodation entirely.
        alone = engine.compute_style(speaker, world=world)
        styles.append({"speaker": speaker_row["id"], "room": None,
                       "listener": None, "style": alone.as_dict()})

    statuses = []
    for row in scenario.get("status_cases", []):
        observer = speaker_from(row["observer"])
        subject = speaker_from(row["subject"])
        statuses.append({
            "bare": engine.social_status(subject),
            "perceived": engine.social_status(subject, observer=observer),
            "with_appearance": engine.social_status(subject, observer=observer,
                                                    world=reactions_world,
                                                    appearance=appearance),
            "without_reactions": engine.social_status(
                subject, observer=observer, world=FakeWorldReactions({}),
                appearance=appearance),
        })
    # The four politeness strategies are chosen by five comparisons, and a style
    # vector out of the full pipeline lands on one of those boundaries
    # essentially never. A grid does.
    axes = scenario.get("politeness_grid", {"formality": [], "directness": []})
    grid = [[f, d, SociolinguisticEngine._politeness(f, d)]
            for f in axes["formality"] for d in axes["directness"]]
    return {"styles": styles, "status": statuses, "politeness_grid": grid}


def viewer_from(row: dict):
    return Agent(id=row["id"],
                 relationships={k: dict(v) for k, v in row["relationships"].items()},
                 reputation={k: dict(v) for k, v in row["reputation"].items()})


def run_standing(scenario: dict) -> dict:
    engine = StandingEngine(scenario["conduct"], enabled=scenario["enabled"])

    judgements = []
    for row in scenario["observers"]:
        observer = viewer_from(row)
        for claim_row in scenario["propositions"]:
            claim = Proposition.from_dict(claim_row)
            for confidence in scenario["confidences"]:
                deltas, reasons = engine.judge(observer, claim, confidence)
                judgements.append({
                    "observer": row["id"], "proposition": claim.key(),
                    "confidence": confidence,
                    "describes_conduct": engine.describes_conduct(claim),
                    "actor": engine.actor_of(claim) or "",
                    "victim": engine.victim_of(claim) or "",
                    "deltas": deltas_of(deltas), "reasons": reasons_of(reasons),
                })

    catalogue = default_candidates(None, {"interlocutor": "agent:you"})
    warmths = []
    for row in scenario.get("warmth_cases", []):
        agent = viewer_from(row)
        other = row["other"]
        warmths.append({
            "agent": row["id"], "warmth": engine.warmth(agent, other),
            "bias": {a.action_id: engine.bias_for(agent, a, other) for a in catalogue},
            "influence": [engine.influence(agent, other, b)
                          for b in scenario.get("bridge_scores", [])],
        })
    return {"judgements": judgements, "warmth": warmths}


def run_appearance(scenario: dict) -> dict:
    engine = AppearanceEngine()
    observers = [Agent(id=r["id"], epistemic=dict(r["epistemic"]))
                 for r in scenario["observers"]]
    subjects = [Agent(id=r["id"], appearance=dict(r["appearance"]))
                for r in scenario["subjects"]]

    catalogue = []
    for subject in subjects:
        catalogue += default_candidates(None, {"interlocutor": subject.id})

    class FakeWorldReactions:
        """Only what the appearance engine reads off a world."""

        def __init__(self, reactions):
            self.appearance_reactions = reactions

    def sweep(reactions):
        world = FakeWorldReactions(reactions)
        rows = []
        for observer in observers:
            for subject in subjects:
                reading = engine.read(observer, subject, world)
                rows.append({
                    "observer": observer.id, "subject": subject.id,
                    "status": reading["status"], "threat": reading["threat"],
                    "signals": reading["signals"], "tokens": reading["tokens"],
                    "drawn_to": engine.drawn_to(observer, subject, world),
                    # EVERY action, including those aimed at somebody else. The
                    # target check inside `bias_for` is what stops a reading of
                    # one person colouring what you do to another, and a probe
                    # that pre-filters never asks it the question.
                    "bias": [{"action": a.action_id, "target": a.target,
                              "pull": engine.bias_for(observer, a, subject, world)}
                             for a in catalogue],
                })
        return rows

    return {"with_reactions": sweep(scenario["reactions"]),
            # And with none, which is every shipped pack: every read empty,
            # nothing consumed, a run byte-identical to before this existed.
            "without_reactions": sweep({})}


def run_diffusion(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"],
                  places=scenario["places"], predicates=scenario["predicates"])

    if isinstance(scenario["agents"], str):
        build_crowd(world)
    else:
        for row in scenario["agents"]:
            agent = Agent(id=row["id"], location=row["location"],
                          roles=list(row["roles"]), networks=tuple(row["networks"]),
                          education=dict(row["education"]),
                          relationships={k: dict(v)
                                         for k, v in row["relationships"].items()},
                          secrets=secrets_from(row["secrets"]))
            for belief_row in row["beliefs"]:
                belief = belief_from(belief_row)
                agent.beliefs[belief.proposition.core_key()] = belief
            world.agents[agent.id] = agent

    runtime = DiffusionRuntime()
    engine = DiffusionEngine()

    def run(delta):
        return reasons_of(engine.step(world, runtime, delta,
                                      player_id=scenario["player_id"]))

    if "extra_steps" in scenario:
        steps = [{"delta": row["delta"], "reasons": run(row["delta"])}
                 for row in scenario["extra_steps"]]
    else:
        steps = [{"delta": scenario["delta_minutes"],
                  "reasons": run(scenario["delta_minutes"])}]

    return {
        "steps": steps,
        "events": runtime.events,
        # Which beliefs stopped spreading: stifling is the mechanism that makes a
        # rumour saturate rather than reach everybody.
        "spreading": {name: {key: b.spreading for key, b in agent.beliefs.items()}
                      for name, agent in world.agents.items()},
    }


def run_content(scenario: dict) -> dict:
    player, addressee = scenario["player_id"], scenario["addressee_id"]

    topics = []
    for row in scenario["topics"]:
        topic = Topic.from_dict(row)
        topics.append({
            "topic_id": topic.topic_id, "label": topic.label,
            "aliases": list(topic.aliases),
            "query": topic.resolved_query(player),
            "player_claim": topic.resolved_player_claim(player),
            "player_assertion": topic.resolved_player_assertion(player),
            "affirm": topic.phrasing_for(True), "deny": topic.phrasing_for(False),
            "reactions": topic.resolved_reactions(player, addressee),
        })

    secrets = secrets_from(scenario["secrets"])
    rows = [{"secret_id": s.secret_id, "avoid_label": s.avoid_label,
             "guards_topics": list(s.guards_topics), "summary": s.summary,
             "surface_forms": list(s.surface_forms), "protects": list(s.protects),
             "about": list(s.about), "min_trust": s.min_trust,
             "cover_story": s.cover_story, "cover_phrasings": s.cover_phrasings}
            for s in secrets]

    index = AliasIndex.build(scenario["aliases"])
    return {
        "topics": topics,
        "secrets": rows,
        "protected_keys": sorted(protected_keys(secrets)),
        "covers": [[s.covers(key, rendered) for s in secrets]
                   for key, rendered in scenario["covers"]],
        "guarding": {t: [s.secret_id for s in secrets_guarding(secrets, t)]
                     for t in scenario["guarding"]},
        "avoid_labels": avoid_labels(secrets),
        "surface_forms_by_label": surface_forms_by_label(secrets),
        "alias_entries": [list(pair) for pair in index.entries],
        "alias_matches": [index.match(row["text"], exclude=tuple(row["exclude"]))
                          for row in scenario["lookups"]],
        "alias_conflicts": [list(c) for c in index.conflicts()],
    }


def run_distortion(scenario: dict) -> dict:
    setup = scenario["world"]
    world = World()
    for agent_id in setup["agents"]:
        world.agents[agent_id] = Agent(id=agent_id)
    row = setup["speaker"]
    speaker = Agent(id=row["id"], location=row["location"],
                    relationships={k: dict(v) for k, v in row["relationships"].items()},
                    routine=Routine.from_list(row["routine"]))
    protect = set(scenario["protected"])

    outcomes = []
    for claim_row in scenario["propositions"]:
        claim = Proposition.from_dict(claim_row)
        for weights in scenario["weights"]:
            for seed_name in scenario["seeds"]:
                seed = derive_seed(seed_name, "probe", 0, 0, "distortion")
                result = distort(claim, speaker=speaker, world=world, seed=seed,
                                 weights=weights, protected=protect)
                entry = {"proposition": claim.core_key(), "weights": weights,
                         "seed": seed_name}
                if result is None:
                    entry["kind"] = None
                else:
                    retold, kind, detail = result
                    entry["kind"] = kind
                    entry["retold"] = retold.as_dict()
                    entry["core_key"] = retold.core_key()
                    entry["detail"] = detail
                    entry["described"] = describe(kind, detail)
                outcomes.append(entry)
    return {"outcomes": outcomes}


def deltas_of(deltas) -> list:
    return [{"module": d.key.module, "field": d.key.field,
             "entity": d.key.entity_id, "subject": d.key.subject_id,
             "dimension": d.key.dimension, "amount": d.amount,
             "reason": d.reason, "source": d.source_module}
            for d in deltas]


def run_social(scenario: dict) -> dict:
    cast = {}
    for row in scenario["agents"]:
        agent = Agent(id=row["id"], roles=list(row["roles"]),
                      schwartz=dict(row["schwartz"]),
                      relationships={k: dict(v) for k, v in row["relationships"].items()})
        agent.affect.mood = Vec3.from_dict(row["mood"])
        agent.affect.active_emotions = dict(row["emotions"])
        cast[row["id"]] = agent

    values = ValueEngine()
    exchange = SocialExchangeEngine()
    identity = SocialIdentityEngine()
    norms = NormEngine()
    network = SocialNetworkEngine()
    tom = TheoryOfMindEngine()
    impression = ImpressionManagementEngine()
    interpersonal = InterpersonalEngine()
    affect = AffectEngine()

    out = {"active_values": {
        salient: {name: values.active_values(agent, salient, {},
                                             scenario["identity_values"])
                  for name, agent in cast.items()}
        for salient in scenario["salient"]}}

    ties = []
    for who, other in scenario["ties"]:
        agent = cast[who]
        agency, communion = interpersonal.stance(agent, other, affect)
        ties.append({"agent": who, "other": other,
                     "tie_strength": network.tie_strength(agent, other),
                     "bridge_score": network.bridge_score(agent),
                     "tom_threaten": tom.expected_reaction(agent, other, "threaten", {})[1],
                     "agency": agency, "communion": communion})
    out["ties"] = ties

    catalogue = default_candidates(None, {})
    contexts = []
    for context in scenario["contexts"]:
        contexts.append({
            "front_stage": impression.front_stage(context),
            "impression_weight": impression.weight(context),
            "terms": {action.action_id: {
                "norm": [list(t) for t in norms.value_terms(None, action, context)],
                "exchange": [list(t) for t in
                             exchange.value_terms(cast["agent:bartender"], action, context)],
                "face": [list(t) for t in impression.value_terms(None, action, context)],
            } for action in catalogue},
        })
    out["contexts"] = contexts

    out["commitments"] = [
        deltas_of(exchange.on_commitment_resolved("agent:bartender", row["other"],
                                                  row["fulfilled"]))
        for row in scenario["commitments"]]

    row = scenario["threat_event"]
    threat = Event(event_id=row["event_id"], world_time=row["world_time"],
                   type=row["type"], actor=row["actor"], location=row["location"],
                   payload=row["payload"])
    threats = []
    for named in (None, "id:override"):
        proposals, appraisal = identity.on_event(cast["agent:bartender"], threat, {}, named)
        threats.append({"given": named, "proposals": deltas_of(proposals),
                        "appraisal": appraisal})
    out["identity_threat"] = threats

    out["dependence"] = [exchange.dependence(a, b) for a, b in scenario["dependence"]]
    return out


def run_routine(scenario: dict) -> dict:
    world = World(world_time=scenario["world_time"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(id=row["id"], location=row["location"],
                                        routine=Routine.from_list(row["routine"]))

    engine = RoutineEngine()
    out = {
        "whereabouts": [{"at": when,
                         "whereabouts": engine.whereabouts(world, when)}
                        for when in scenario["times"]],
        "meeting_opportunities": engine.meeting_opportunities(
            world, samples=scenario.get("samples", 24)),
        "seeded": reasons_of(engine.seed(world)),
    }

    steps = []
    for row in scenario["step"]:
        world.world_time = row["to"]
        # `runtime=None`: no action bridge, no climate layer, no ledger. Those
        # are not ported, and the seam is named rather than faked.
        steps.append({"to": row["to"],
                      "reasons": reasons_of(engine.step(world, None, row["delta"])),
                      "locations": {a: world.agents[a].location for a in world.agents}})
    out["steps"] = steps
    return out


def run_perception(scenario: dict) -> dict:
    world = World(global_seed=scenario["global_seed"],
                  world_time=scenario["world_time"],
                  places=scenario["places"])
    for row in scenario["agents"]:
        world.agents[row["id"]] = Agent(id=row["id"], location=row["location"])
    for row in scenario.get("exposure", []):
        world.media_exposure[(row["agent"], row["channel"])] = row["value"]

    engine = PerceptionEngine()
    events = []
    for row in scenario["events"]:
        move = row.get("move")
        if move:
            # Somebody walks. The occupancy index is cached against the global
            # location epoch, so this is what proves the cache invalidates.
            world.agents[move["agent"]].location = move["to"]
        event = Event(event_id=row["event_id"], world_time=row["world_time"],
                      type=row["type"], actor=row["actor"],
                      location=row["location"], payload=row["payload"])
        events.append({
            "event_id": event.event_id,
            "observations": [{"observer": o.observer, "modality": o.modality,
                              "quality": o.quality}
                             for o in engine.filter(event, world)],
        })
    return {"events": events}


def agent_from(row: dict):
    """A character with the fields topology reads, and nothing else."""
    return Agent(id=row["id"], networks=tuple(row["networks"]),
                 roles=list(row["roles"]), identities=list(row["identities"]),
                 education=dict(row["education"]), epistemic=dict(row["epistemic"]))


class FakeWorld:
    """What topology reads off a world: its predicate declarations and the time.

    Deliberately not the real `World`, for the same reason the relationship
    probe does not use the real agent: this case is about one module, and
    dragging in the loader would mean a failure here could be caused by
    something topology does not do.
    """

    def __init__(self, predicates, world_time, agents):
        self.predicates = predicates
        self.world_time = world_time
        self.agents = agents


def run_topology(scenario: dict) -> dict:
    cast = {}
    for row in scenario["agents"]:
        cast[row["id"]] = agent_from(row)
    world = FakeWorld(scenario["predicates"], scenario["world_time"], cast)

    out = {
        "circles": {name: sorted(circles(agent)) for name, agent in cast.items()},
        "bridges": bridges(world),
    }

    passes = []
    for pair in scenario["pairs"]:
        claim = Proposition(pair["predicate"], {"subject": "agent:x"})
        weight, (code, detail) = may_pass_on(world, claim, cast[pair["speaker"]],
                                             cast[pair["listener"]], pair["place"])
        passes.append({"speaker": pair["speaker"], "listener": pair["listener"],
                       "predicate": pair["predicate"], "weight": weight,
                       "code": code, "detail": detail})
    out["may_pass_on"] = passes
    out["attention_budget"] = {name: attention_budget(agent)
                               for name, agent in cast.items()}

    attention = scenario.get("attention")
    if attention:
        # Spending past everybody's budget at several times of day, so both the
        # cap and the day boundary are exercised.
        spending = {}
        for name, agent in cast.items():
            rows = []
            for when in attention["spend_at"]:
                world.world_time = when
                accepted = [spend_attention(agent, world)
                            for _ in range(attention["per_time"])]
                rows.append({"at": when, "accepted": accepted,
                             "day": agent.attention_day,
                             "spent": agent.attention_spent})
            spending[name] = rows
        out["attention_spending"] = spending
    return out


def run_affect(scenario: dict) -> dict:
    engine = AffectEngine()
    state = AffectState()
    state.baseline = pad_baseline_from_big_five(scenario["big_five"])
    state.mood = state.baseline
    steps = []
    for step in scenario["steps"]:
        fired, reasons = engine.update(state, step["appraisal"], step["dt"])
        steps.append({
            "fired": [{"emotion": emotion, "intensity": intensity}
                      for emotion, intensity in fired],
            "mood": state.mood.as_dict(),
            "active_emotions": dict(state.active_emotions),
            "tendencies": engine.action_tendencies(state),
            "stress": engine.stress(state),
            "reasons": reasons_of(reasons),
        })
    return {"baseline": state.baseline.as_dict(), "steps": steps}


def run_relationship(scenario: dict) -> dict:
    agent = Agent(id="agent:self")
    for subject, fields in scenario["initial"].items():
        agent.relationships[subject] = dict(fields)

    reasons = []
    deltas = [relationship_delta(agent.id, row["subject"], row["field"],
                                 row["amount"], row["reason"], "probe")
              for row in scenario.get("deltas", [])]
    RelationshipEngine().apply(agent, deltas, reasons)

    reputation = [reputation_delta(row["subject"], agent.id, row["dimension"],
                                   row["amount"], row["reason"], "probe")
                  for row in scenario.get("reputation", [])]
    ReputationEngine().apply(agent, reputation, reasons)

    return {"relationships": {k: dict(v) for k, v in agent.relationships.items()},
            "reputation": {k: dict(v) for k, v in agent.reputation.items()},
            "reasons": reasons_of(reasons)}


def run_identity(scenario: dict) -> dict:
    agent = Agent(id="agent:self", identities=[dict(row) for row in scenario["identities"]])
    engine = IdentityEngine()
    rounds = []
    for _ in range(scenario["rounds"]):
        winner, salience = engine.salience(agent, scenario["context"],
                                           scenario["threat"])
        rounds.append({"winner": winner, "salience": dict(salience)})
    return {"rounds": rounds}


class Deciding:
    """The slice of a character the policy engine actually reads."""

    def __init__(self, row: dict, arousal: float):
        self.id = row["id"]
        self.big_five = dict(row["big_five"])
        self.affect = AffectState()
        self.affect.mood.a = arousal
        self._global_seed = row["global_seed"]


def run_policy(scenario: dict) -> dict:
    engine = PolicyEngine(scenario.get("params"))
    agent = Deciding(scenario["agent"], scenario.get("arousal", 0.0))

    terms = scenario["terms"]
    bias = scenario["bias"]
    if scenario.get("catalogue"):
        from unscripted.actions import ActionDefinition, ActionOutcome
        candidates = [
            ActionDefinition("act_%d" % index, "share", is_dialogue=True,
                             outcomes=[ActionOutcome("safety", 0.1, 0.5, source="tied")])
            for index in range(40)]
    else:
        candidates = default_candidates(agent, scenario["context"])
    scored = engine.score(
        agent, candidates, weights=scenario["weights"],
        term_providers=lambda action: [tuple(row) for row in terms.get(action.action_id, [])],
        action_tendencies=scenario["tendencies"],
        bias_providers=(lambda action: bias.get(action.action_id, 0.0)) if bias else None)

    chosen, reasons = engine.select(agent, scored, event_id=scenario["event_id"],
                                    world_time=scenario["world_time"])
    out = {
        "scored": [{"action_id": c.action.action_id, "utility": c.utility,
                    "contributions": [list(row) for row in c.contributions]}
                   for c in scored],
        "chosen": chosen.action.action_id,
        "reasons": [{"code": code, "amount": amount,
                     "detail": {**detail,
                                "selection_probs": [list(p) for p in detail["selection_probs"]],
                                "contributions": [list(r) for r in detail["contributions"]]}}
                    for code, amount, detail in reasons],
    }
    # A single seeded pick proves almost nothing: with four candidates a wrong
    # seed agrees one time in four. Sweeping the event id makes it a
    # distribution, which luck cannot reproduce.
    if "sweep_events" in scenario:
        out["sweep"] = [engine.select(agent, scored, event_id=event,
                                      world_time=scenario["world_time"])[0].action.action_id
                        for event in range(scenario["sweep_events"])]
    return out


def memory_from(row: dict) -> Memory:
    proposition = Proposition.from_dict(row["proposition"]) if row.get("proposition") else None
    return Memory(memory_id=row["memory_id"], owner="agent:self", type=row["type"],
                  content=row["content"], proposition=proposition,
                  importance=row["importance"],
                  emotional_valence=row["emotional_valence"],
                  presentations=list(row["presentations"]),
                  world_time=(row["presentations"] or [None])[0])


def repeating_pattern() -> list:
    """Nine occasions of one person doing one thing, plus three unrelated.

    Generated rather than written out so the two sides cannot drift, and so the
    intent stays readable: consolidation needs a pattern to find AND something
    it must leave alone.
    """
    out = []
    for index in range(9):
        out.append(Memory(
            memory_id="m:seen_%d" % index, owner="agent:self", type="episodic",
            content="saw it again", importance=0.1 + 0.05 * index,
            emotional_valence=-0.2 - 0.05 * index,
            presentations=[1000 + 100 * index], world_time=1000 + 100 * index,
            proposition=Proposition("was_at", {"agent": "agent:vee",
                                               "place": "place:dock",
                                               "when": 1000 + 100 * index})))
    for index in range(3):
        out.append(Memory(
            memory_id="m:other_%d" % index, owner="agent:self", type="episodic",
            content="something else", importance=0.4, emotional_valence=0.1,
            presentations=[1500 + 10 * index], world_time=1500 + 10 * index))
    return out


def identical_memories(count: int, prefix: str, when: int, kind: str) -> list:
    """Memories identical in every respect that scores.

    Only the sort's stability decides which come back, or which are destroyed.
    The count matters: libstdc++ falls back to insertion sort below sixteen
    elements and insertion sort is stable, so a small case passes an unstable
    comparator and proves nothing.
    """
    return [Memory(memory_id="%s%d" % (prefix, index), owner="agent:self",
                   type=kind, content="identical", importance=0.5,
                   emotional_valence=0.0, presentations=[when], world_time=when)
            for index in range(count)]


GENERATED = {
    "generated:repeating_pattern": lambda: repeating_pattern(),
    "generated:identical_memories": lambda: identical_memories(40, "m:same_", 1000, "episodic"),
    "generated:identical_episodes": lambda: identical_memories(30, "m:ep_", 5000, "episodic"),
}


def run_memory(scenario: dict) -> dict:
    engine = MemoryEngine(scenario.get("params"))
    items = scenario["items"]
    memories = (GENERATED.get(items, repeating_pattern)() if isinstance(items, str)
                else [memory_from(row) for row in items])

    out = {}
    now = scenario["now"]

    reinforce = scenario.get("reinforce")
    if reinforce:
        for step in range(reinforce["times"]):
            engine.reinforce(memories[0], reinforce["from"] + reinforce["every"] * step)

    retrieve = scenario.get("retrieve")
    if retrieve:
        topics = [Proposition.from_dict(topic) for topic in retrieve.get("topics", [])]
        # Seeded, so the DRAW is exercised rather than the threshold fallback.
        # Without it both sides take the `seed_parts is None` path and the case
        # cannot tell a stochastic retrieval from a deterministic cut-off.
        found = engine.retrieve(memories, retrieve["at"], topics=topics,
                                seed_parts=("probe", "agent:recaller", "recall"),
                                mood_valence=retrieve["mood_valence"])
        out["retrieved"] = [{"activation": activation, "probability": probability,
                             "memory_id": memory.memory_id}
                            for activation, probability, memory in found]

    if "consolidate_at" in scenario:
        out["consolidation"] = reasons_of(
            engine.decay_and_consolidate(memories, scenario["consolidate_at"]))

    out["memories"] = [memory.as_dict(now) for memory in memories]
    return out


SECTIONS = {"metahuman": run_metahuman, "sdk": run_sdk, "pack_loader": run_pack_loader, "inspect": run_inspect, "snapshot": run_snapshot, "runtime": run_runtime, "provider": run_provider, "actionbridge": run_actionbridge, "validator": run_validator, "parser": run_parser, "interpretation": run_interpretation, "contracts": run_contracts, "roundtrip": run_roundtrip, "predicates": run_predicates,
            "grounding": run_grounding, "flat": run_flat, "tuning": run_tuning,
            "revision": run_revision, "pursuit": run_pursuit, "notes": run_notes, "promises": run_promises,
            "common_knowledge": run_common_knowledge, "climate": run_climate,
            "contagion": run_contagion, "medium": run_medium,
            "agency": run_agency, "dialogue": run_dialogue,
            "factions": run_factions, "commitment": run_commitment,
            "sociolinguistics": run_sociolinguistics,
            "standing": run_standing, "appearance": run_appearance,
            "diffusion": run_diffusion,
            "content": run_content, "distortion": run_distortion,
            "social": run_social, "routine": run_routine,
            "perception": run_perception, "topology": run_topology,
            "affect": run_affect, "relationship": run_relationship,
            "identity": run_identity, "policy": run_policy, "memory": run_memory}


def python_side(document: dict) -> dict:
    return {name: {scenario["id"]: to_bits(run(scenario))
                   for scenario in document[name]}
            for name, run in SECTIONS.items()}


def cpp_side() -> dict:
    compiler = os.environ.get("CXX", "g++")
    with tempfile.TemporaryDirectory() as work:
        binary = os.path.join(work, "engine_probe")
        subprocess.run(
            [compiler, "-O2", "-std=c++17", "-I", os.path.join(PORT_ROOT, "include"),
             os.path.join(HERE, "engine_probe.cpp"), "-o", binary],
            check=True)
        out = subprocess.run([binary, CASES], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def main() -> int:
    with open(CASES, encoding="utf-8") as handle:
        document = json.load(handle)

    expected = python_side(document)
    try:
        actual = cpp_side()
    except FileNotFoundError:
        print("no C++ compiler; nothing measured")
        return 0
    except subprocess.CalledProcessError as exc:
        print("the probe would not build or run: %s" % exc)
        return 1

    total = clean = 0
    for name in SECTIONS:
        for scenario in document[name]:
            case = scenario["id"]
            total += 1
            rows = differences(expected[name].get(case),
                               actual.get(name, {}).get(case))
            if not rows:
                clean += 1
                print("  ok    %s / %s" % (name, case))
                continue
            print("  DIFF  %s / %s   %d field(s)" % (name, case, len(rows)))
            for where, exp, act in rows[:6]:
                print("          %s" % where)
                print("            python %s" % exp)
                print("            c++    %s" % act)
            if len(rows) > 6:
                print("          ... and %d more" % (len(rows) - 6))

    print("\n%d of %d cases reproduce the Python engines exactly." % (clean, total))
    if clean != total:
        return 1
    print("Mood, emotions, action tendencies, relationship kinetics, reputation,\n"
          "identity salience, memory activation, retrieval order and the\n"
          "judgements drawn out of forgotten episodes all agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
