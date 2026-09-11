"""Public SDK facade for studios and engine adapters."""
from __future__ import annotations

import os
import sys
import hashlib
import json
from dataclasses import replace

from .agent import Agent
from .affect import AffectState
from .capabilities import resolve_capabilities
from . import content
from .contracts import (DialogueResponse, EventReceipt, ParsedCommand, RuntimeConfig,
                        ReplayResult, ReplayStep, SnapshotId, TurnResult)
from . import commitment as commitment_mod
from . import grounding
from .determinism import derive_seed, seeded_uniform
from .commitment import Candidate, SemanticMove
from .commitment import select as commit_moves
from .dialogue import ConversationState, DialoguePlan
from .events import Event
from .memory import Memory
from . import metahuman
from . import snapshot
from . import state_view
from .ontology import Proposition, relevance
from .pack import validate_world_pack
from .parser import HELP_TEXT, RuleBasedParserProvider
from .persistence import Store
from .provider import HttpChatRealizer, ProviderError, TemplateRealizer
from .validator import CANON_OFF, is_unsafe
from .runtime import Runtime
from .statekey import trust_delta
from .world import load_world_pack
from . import inspect as views


class UnscriptedRuntime:
    """Small, typed facade over the core implementation.

    Game engines should integrate against this surface: feed events or player
    text in, query structured state out, and keep rendering/action execution in
    the game.
    """

    def __init__(self, config: RuntimeConfig, world, store: Store | None = None,
                 parser: RuleBasedParserProvider | None = None):
        self.config = config
        self.world = world
        self.store = store
        self.core = Runtime(world, store)
        self.core.population_lod = config.population_lod
        self.core.projection_scope = getattr(config, "projection_scope", "all")
        self.core.semantic_release = getattr(config, "semantic_release", "controlled")
        self.core.climate.enabled = bool(getattr(config, "climate", False))
        self.core.pursuit.enabled = bool(getattr(config, "pursuit", False))
        self.core.pursuit.media = bool(getattr(config, "media", False))
        self.core.contagion.enabled = bool(getattr(config, "contagion", False))
        self.core.common_knowledge.enabled = bool(
            getattr(config, "common_knowledge", False))
        self.core.notes.enabled = bool(getattr(config, "notes", False))
        self.core.promises.enabled = bool(getattr(config, "promises", False))
        self.core.standing.enabled = bool(getattr(config, "standing", False))

        # HOW THIS WORLD WORKS IS CONTENT. Applied after every engine exists, so
        # a pack overrides a default rather than racing it, and recorded in the
        # trace -- a scene behaving oddly should not need somebody to diff a
        # JSON file against the source of the runtime.
        from . import tuning as tuning_module
        tuned = tuning_module.apply(self.core, getattr(self.world, "tuning", None))
        if tuned:
            self.core.last_traces["_tuning"] = tuned
        self.core.pursuit.notes = self.core.notes.enabled
        self.core.actions_out.enabled = bool(getattr(config, "action_bridge", False))
        self.core.actions_out.timeout_minutes = int(
            getattr(config, "action_timeout_minutes", 60))
        # The player and whoever the scenario points at are always warm; anyone
        # else joins the moment the player actually meets them.
        self.core.project_for(config.player_id, *getattr(world, "focus_agents", ()) or ())
        self.core.player_id = config.player_id
        self.parser = parser or RuleBasedParserProvider()
        self.capability_plan = resolve_capabilities(config)
        self.core.validator.canon_mode = config.canon_mode
        self._configure_text_realizer()
        self._initial_state_loaded = False

    @classmethod
    def create(cls, config: RuntimeConfig | None = None) -> "UnscriptedRuntime":
        config = config or RuntimeConfig()
        pack_path = cls._resolve_pack_path(config.world_pack_path)
        report = validate_world_pack(pack_path)
        if config.strict and not report.ok:
            detail = "; ".join(f"{i.code}: {i.message}" for i in report.issues)
            raise ValueError(f"Invalid world pack: {detail}")
        world = load_world_pack(pack_path)
        start = config.player_start_location or world.player_start
        if not start:
            raise ValueError(
                f"World pack {pack_path} declares no places, so the player has nowhere "
                f"to start. Set scenario.json: player_start, or RuntimeConfig."
                f"player_start_location.")
        if start not in world.places:
            raise ValueError(f"Player start location {start!r} is not a place in this pack. "
                             f"Known places: {sorted(world.places)}")
        if config.player_id not in world.agents:
            world.agents[config.player_id] = Agent(
                id=config.player_id,
                location=start,
                big_five={"agreeableness": 0.5, "emotional_stability": 0.5},
            )
        else:
            world.agents[config.player_id].location = start
        store = Store(config.storage_path, debug_traces=config.debug_traces)
        sdk = cls(config, world, store)
        # put the cast where their day says they should be, not where the character
        # files happened to list them -- for a scenario starting at 04:00 those are
        # rarely the same place.
        sdk.core.routine.seed(world)
        if config.load_initial_state:
            sdk.load_initial_state()
        return sdk

    @staticmethod
    def _resolve_pack_path(path: str) -> str:
        if os.path.isabs(path) and os.path.exists(path):
            return path
        if os.path.exists(path):
            return path
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(package_root, path)
        if os.path.exists(candidate):
            return candidate

        # NEXT TO THE ARCHIVE, for a standalone build. Inside a `.pyz` the
        # package root is a path inside the zip, and there is no `sys.prefix`
        # share directory because nothing was installed -- so a self-contained
        # bundle could serve a pack given by path and could not find its own
        # reference packs, which made `unscripted smoke` fail on a folder
        # that was otherwise working. Two levels up from `unscripted/sdk.py` inside
        # `.../unscripted.pyz/unscripted/` is the folder the archive sits in.
        for base in (os.path.dirname(package_root),
                     os.path.dirname(os.path.abspath(sys.argv[0]))):
            beside = os.path.join(base, path)
            if os.path.exists(beside):
                return beside

        installed = os.path.join(sys.prefix, "share", "unscripted", path)
        return installed

    @staticmethod
    def validate_world_pack(path: str):
        return validate_world_pack(path)

    def close(self):
        closer = getattr(self.core.realizer, "close", None)
        if callable(closer):
            closer()
        if self.store:
            self.store.close()

    # ---------- deferred model lines ----------
    def poll_line_upgrades(self) -> list:
        """Model lines that arrived after their turn had already been answered.

        A warm local model needs ~300 ms, which is past any frame budget, so a turn
        answers immediately from authored text and the model's version -- if it is
        any good -- shows up here a few frames later. The engine can swap the
        subtitle, or ignore it.

        Nothing is released because it arrived. Every upgrade goes through the same
        validator, with the same canon and secret checks, as a line generated
        inside the budget. A rejected upgrade is simply not offered.
        """
        realizer = self.core.realizer
        take_ready = getattr(realizer, "take_ready", None)
        if not callable(take_ready):
            return []
        upgrades = []
        for request_id, plan, _style, text in take_ready():
            speaker = self.world.agents.get(plan.speaker)
            result = self.core.validator.check(text, plan, speaker, [])
            if result.verdict != "ACCEPT":
                self.core.last_traces[plan.speaker] = (
                    self.core.last_traces.get(plan.speaker, [])
                    + [("provider.late_line_rejected", 1.0,
                        {"request_id": request_id, "verdict": result.verdict,
                         "reasons": [r[0] for r in result.reasons]})])
                continue
            upgrades.append({
                "request_id": request_id,
                "speaker_id": plan.speaker,
                "addressee_id": plan.addressee,
                "text": text,
                "act": plan.dialogue_act,
                "verdict": result.verdict,
            })
            if self.store and hasattr(self.store, "save_provider_call"):
                # A late line is still a model output that reached a player; it
                # belongs in the audit trail like any other.
                self.store.save_provider_call(
                    turn_id=f"upgrade:{request_id}",
                    world_time=self.world.world_time,
                    provider=type(self.core.realizer).__name__,
                    model_id=getattr(self.core.realizer, "model_id", "deferred"),
                    prompt_hash="",
                    raw_output=text,
                    accepted_output=text,
                    validation_result=result.verdict,
                    data={"deferred": True, "act": plan.dialogue_act})
        return upgrades

    def pending_line_count(self) -> int:
        counter = getattr(self.core.realizer, "pending_count", None)
        return counter() if callable(counter) else 0

    def _configure_text_realizer(self):
        cfg = self.config.text_realizer or {}
        provider = cfg.get("provider", "template")
        #: What warm-up and probing found out about the configured model, so a
        #: developer learns at startup that their model cannot voice NPCs rather
        #: than discovering it one fallback line at a time.
        self.provider_report = {}
        if provider == "template":
            self.core.realizer = TemplateRealizer.for_world(self.world)
        elif provider == "http":
            from .edge import build_edge_realizer, probe_model, warm_up
            budget = int(cfg.get("latency_budget_ms", 120))
            realizer = build_edge_realizer(
                endpoint=cfg["endpoint"],
                model_id=cfg.get("model_id") or "external-chat",
                api_key=cfg.get("api_key"),
                budget_ms=budget,
                timeout=float(cfg.get("timeout", 20.0)),
                deferred=bool(cfg.get("deferred", True)),
            )
            self.core.realizer = realizer
            # Warm up and probe against the RAW model, not through the deferred
            # wrapper: these are load-time calls that are allowed to be slow, and
            # measuring them through a 120 ms budget would only measure the budget.
            inner = getattr(realizer, "inner", realizer)
            if cfg.get("warm_up", True):
                self.provider_report["warm_up"] = warm_up(inner)
            if cfg.get("probe", True):
                self.provider_report["probe"] = probe_model(inner, budget_ms=budget)
        else:
            raise ValueError(f"Unsupported text realizer provider: {provider}")

    # ---------- public API ----------
    def interpret_input(self, text: str) -> ParsedCommand:
        player = self.world.agents[self.config.player_id]
        return self.parser.parse(text, player_id=self.config.player_id,
                                 player_location=player.location, world=self.world)

    def emit_event(self, event: Event) -> EventReceipt:
        traces = self.core.process_event(event)
        return EventReceipt(event.event_id, event.type, event.world_time,
                            observed_by=sorted(traces.keys()), reasons=traces)

    # ---------------------------------------------------------------- voice --

    def climate_report(self) -> list:
        """What it is like in each place, and how far that is from normal.

        The number a designer actually wants when a scene stops working: not
        anybody's personality, but whether the room has closed up since the last
        thing that happened in it.
        """
        return self.core.climate.report()

    # ------------------------------------------------------ save and load --

    def export_state(self) -> dict:
        """The whole mutable world as one JSON-safe blob, for YOUR save file.

        This is the save path a game wants, and it is different from
        :meth:`create_snapshot`. A snapshot stays inside the runtime's own store
        and hands you an id; that is right for a debug rewind and wrong for
        shipping, because a player's save gets copied between machines and
        synced to a cloud, and an id pointing into a second database will drift
        away from the file it belongs to.

        Write the returned dict into your own save, alongside everything else you
        persist. It is JSON-safe, self-describing, and about 11 kB gzipped for
        eight characters — small enough that no save format has to be redesigned
        around it.

        >>> blob = runtime.export_state()
        >>> my_save["unscripted"] = blob          # doctest: +SKIP
        """
        return snapshot.export_state(self.world, self.core)

    def inspect_state(self, blob: dict) -> dict:
        """What loading this blob would do, WITHOUT loading it.

        Call this on a load screen before offering "continue": it reports
        ``usable``, and when the cast has changed since the save was written, it
        names exactly which characters would be restored, dropped and left at
        their authored state. No exception has to be caught to find out whether a
        save is good.
        """
        return snapshot.inspect_state(blob, self.world)

    def import_state(self, blob: dict) -> dict:
        """Load a blob produced by :meth:`export_state`. Returns the same report.

        Raises :class:`unscripted.snapshot.StateImportError` only when the blob cannot
        be used at all — a foreign world, or a save from a newer build. A save
        written before the studio patched in a new character loads fine and says
        what changed, because a patch is not a corruption.
        """
        report, reasons = snapshot.import_state(blob, self.world, self.core)
        if reasons:
            self.core.last_traces["_state"] = reasons
        return report

    def promises_report(self) -> dict:
        """What has been undertaken and what became of it.

        `open` is everything still owed; `settled` is the recent past, kept and
        broken. The read a quest log wants, and the one a designer wants when a
        character has gone cold on a player and nobody remembers why.
        """
        return self.core.promises.report()

    def settle_promise(self, promise_id: str, kept: bool, note: str = "") -> list:
        """Tell the runtime what became of a promise. The authoritative path.

        Use this whenever your game KNOWS -- the player handed over the money,
        the escort reached the gate, the crate was delivered. The runtime's own
        judgement is a fallback for promises nobody settles, and it is a model of
        somebody noticing rather than of a transaction completing.

        Raises ``KeyError`` if there is no open promise with that id; ask
        :meth:`promises_report` or :meth:`promises_owed_by` for the open ones.
        """
        reasons = self.core.promises.settle(self.world, self.core, promise_id,
                                            kept, note)
        if reasons:
            self.core.last_traces.setdefault("_promises", []).extend(reasons)
        return reasons

    def promises_owed_by(self, agent_id: str) -> list:
        """What this character has undertaken and not yet made good."""
        return self.core.promises.owed_by(agent_id)

    def promises_owed_to(self, agent_id: str) -> list:
        """What has been undertaken to this character."""
        return self.core.promises.owed_to(agent_id)

    def layers(self) -> dict:
        """Which optional mechanics are running, by name.

        One place, because the command line, `/capabilities` and the
        documentation each need this answer and three copies of it would drift.
        A test asserts this covers exactly `contracts.OPTIONAL_LAYERS`, so a
        layer added without being reportable is a failing test rather than a
        silently invisible feature.
        """
        core = self.core
        return {"standing": bool(core.standing.enabled),
                "action_bridge": bool(core.actions_out.enabled),
                "climate": bool(core.climate.enabled),
                "pursuit": bool(core.pursuit.enabled),
                "media": bool(core.pursuit.media),
                "notes": bool(core.notes.enabled),
                "promises": bool(core.promises.enabled),
                "contagion": bool(core.contagion.enabled),
                "common_knowledge": bool(core.common_knowledge.enabled)}

    def public_knowledge(self) -> list:
        """What is out in the open, and in front of whom.

        Distinct from `/v2/state/knowledge`, which answers who holds a belief.
        This answers the other question -- which of those facts can no longer be
        denied, because a crowd watched each other find out. Empty when the layer
        is off.
        """
        return self.core.common_knowledge.report()

    def is_public_between(self, proposition_key: str, *agent_ids) -> bool:
        """Is this common knowledge among all of these characters at once?

        The check a dialogue system wants before letting somebody bluff.
        """
        return self.core.common_knowledge.is_common(proposition_key, *agent_ids)

    def notes_at(self, place_id: str) -> list:
        """What is lying unread in this place.

        The read a game wants for a searchable desk, a noticeboard or a body's
        pockets: notes are objects, so they can be looked at without anybody
        having to have a conversation.
        """
        return [note.as_dict() for note in self.core.notes.at(place_id)]

    def voice_available(self) -> bool:
        """Whether this build can actually produce audio for a spoken line."""
        from .voice import available
        backend = getattr(self.config, "voice_backend", "none")
        return backend != "none" and bool(available().get(backend))

    def voice_plan(self, packet: dict):
        """What a spoken line should sound like, before any synthesiser sees it.

        Useful without any backend at all: the plan is the runtime's claim about
        the line -- faster, higher, quieter, and why -- and a studio with its own
        voice pipeline wants exactly this and none of the rendering.
        """
        from .voice import VoiceProfile, plan_from_avatar
        speaker = packet.get("speaker_id")
        authored = {}
        if speaker in self.world.agents:
            authored = getattr(self.world.agents[speaker], "voice", None) or {}
        return plan_from_avatar(packet,
                                profile=VoiceProfile.for_agent(speaker or "agent:?",
                                                               authored))

    def speak(self, packet: dict, out_path: str):
        """Render a spoken line to a WAV file with the configured backend."""
        from .voice import synthesize
        return synthesize(self.voice_plan(packet), out_path,
                          backend=getattr(self.config, "voice_backend", "none"),
                          model=getattr(self.config, "voice_model", None))

    # ------------------------------------------------------- the action bridge --

    def pending_actions(self) -> list:
        """What the runtime has asked the engine to do and is still waiting on.

        Poll this after every turn and every time advance. An empty list is the
        normal state; it is also what a build with the bridge switched off always
        returns, which is why `capabilities.action_bridge` exists to tell the two
        apart.
        """
        return [intent.as_dict() for intent in self.core.actions_out.pending()]

    def report_action_result(self, intent_id: str, status: str,
                             detail: str = "") -> dict:
        """Tell the runtime what actually happened in the engine.

        SUCCEEDED applies the effect; FAILED, INTERRUPTED and UNREACHABLE record
        that it did not happen and leave the world as the player saw it. There is
        no fifth answer an engine may give: a status outside that set is rejected
        rather than guessed at, because guessing is how the simulation and the
        screen start to disagree.
        """
        return self.core.resolve_action(intent_id, status, detail=detail)

    def action_bridge_report(self) -> dict:
        """Counts an integrator needs: issued, pending, and how they ended.

        A build that times out every intent behaves like a build with no engine
        attached, and looks like one too -- until you read `timed_out`.
        """
        return self.core.actions_out.report()

    def advance_time(self, minutes: int):
        """Advance world time. Time is monotonic: rewinding it would silently
        corrupt every memory activation (which is a function of elapsed time),
        so a negative delta is rejected here rather than at the HTTP edge -- an
        engine calling the SDK directly gets the same guarantee."""
        if isinstance(minutes, bool) or not isinstance(minutes, int):
            raise TypeError(f"advance_time expects an int, got {type(minutes).__name__}")
        if minutes < 0:
            raise ValueError(f"World time is monotonic; cannot advance by {minutes} minutes. "
                             "Use restore_snapshot() to rewind.")
        before = self.world.world_time
        self.core.advance_time(minutes)
        return {"from": before, "to": self.world.world_time,
                "last_trace": self.core.last_traces}

    def respond(self, agent_id: str, *, topic: str | None = None,
                interlocutor: str | None = None) -> DialogueResponse:
        interlocutor = interlocutor or self.config.player_id
        self.core._catch_up(self.world.agents[agent_id])  # LOD: decay current before speaking
        gate_reasons: list = []
        direct = self._direct_answer(agent_id, interlocutor, topic, gate_reasons)
        if direct:
            return direct
        # Falling through to deliberation must not erase WHY the direct answer was
        # withheld: `say()` overwrites the agent's trace, so a secret gate would have
        # produced an unexplained deflection -- the one line a studio most needs
        # explained. Carry the gate reasons into the final trace.
        raw = self.core.say(agent_id, interlocutor=interlocutor)
        reasons = gate_reasons + raw["reasons"]
        self.core.last_traces[agent_id] = reasons
        return DialogueResponse(agent_id, raw["text"], raw["act"], raw["verdict"],
                                raw["utility"], reasons, raw["style"])

    def structured_agent(self, agent_id: str) -> dict:
        """JSON snapshot of an agent's mind: beliefs+provenance, memory decay,
        affect, relationships and the per-turn reason trace. See :mod:`unscripted.state_view`."""
        self.core._catch_up(self.world.agents[agent_id])  # LOD: realise deferred decay
        return state_view.agent_state(self, agent_id)

    def structured_knowledge(self, *, limit: int = 40) -> dict:
        """Who knows what, how far from the source, and how it travelled.

        See :func:`unscripted.state_view.knowledge_state`. This is the spread map: the
        machine-readable answer to "how does this character know that".
        """
        return state_view.knowledge_state(self, limit=limit)

    def structured_world(self) -> dict:
        """JSON snapshot of world time, factions/heat/clocks and rumour exposure."""
        return state_view.world_state(self)

    def structured_scene(self) -> dict:
        """The player's current location for UI rendering: place, NPCs, exits."""
        player = self.world.agents[self.config.player_id]
        loc = player.location
        place = self.world.places.get(loc, {})
        npcs = [{"id": a.id, "name": self.agent_name(a.id)}
                for a in self.world.agents.values()
                if a.location == loc and a.id != self.config.player_id]
        npcs.sort(key=lambda n: n["name"])
        exits = [{"id": e, "label": self.world.place_label(e)}
                 for e in self.world.exits_from(loc)]
        return {
            "world_time": self.world.world_time,
            "location": loc,
            "label": self.world.place_label(loc),
            "attributes": {
                "noise": round(place.get("noise_level", 0.0), 2),
                "surveillance": round(place.get("surveillance_level", 0.0), 2),
                "privacy": round(place.get("privacy_level", 0.0), 2),
            },
            "npcs": npcs,
            "exits": exits,
        }

    def face_packet(self, agent_id: str, *, gaze_target: str | None = None) -> dict:
        """MetaHuman-ready face state (ARKit blendshapes + gaze + prosody) for an agent.

        Engine adapters poll this to drive a MetaHuman face between dialogue turns
        (e.g. while idle, reacting to off-screen events, or during another NPC's
        line). See :mod:`unscripted.metahuman`.
        """
        agent = self.world.agents[agent_id]
        self.core._catch_up(agent)  # LOD: realise deferred decay before reading the face
        tendencies = self.core.affect.action_tendencies(agent.affect)
        return metahuman.affect_to_face(
            agent.affect, action_tendencies=tendencies,
            gaze_target=gaze_target or self.config.player_id)

    def avatar_turn(self, text: str) -> dict:
        """Like :meth:`submit_player_text`, but returns an Unreal/MetaHuman packet.

        The result carries the normal turn message plus, when an NPC speaks, an
        ``avatar`` block: validated text, emotion, ARKit-52 blendshapes, gaze,
        prosody and posture — everything a MetaHuman plugin needs for one turn.
        """
        result = self.submit_player_text(text)
        data = result.as_dict()
        if result.npc_response is not None:
            speaker = self.world.agents.get(result.npc_response.speaker_id)
            tendencies = (self.core.affect.action_tendencies(speaker.affect)
                          if speaker else None)
            data["avatar"] = metahuman.build_avatar_packet(
                result.npc_response,
                speaker.affect if speaker else AffectState(),
                action_tendencies=tendencies,
                gaze_target=self.config.player_id)
        return data

    def submit_player_text(self, text: str) -> TurnResult:
        parsed = self.interpret_input(text)
        player = self.world.agents[self.config.player_id]
        receipts = []
        npc_response = None
        developer_trace = ""

        if parsed.intent == "quit":
            return TurnResult(self.world.world_time, player.location, parsed,
                              "Session ended.", done=True)
        if parsed.intent == "help":
            return TurnResult(self.world.world_time, player.location, parsed, HELP_TEXT)
        if parsed.intent == "noop":
            return TurnResult(self.world.world_time, player.location, parsed, "")
        if parsed.intent == "unknown":
            return TurnResult(self.world.world_time, player.location, parsed,
                              "I could not map that to a safe action. Try 'help'.")
        if parsed.intent == "observe":
            return TurnResult(self.world.world_time, player.location, parsed,
                              self.describe_location(player.location))
        if parsed.intent == "move":
            return self._move_player(parsed)
        if parsed.intent == "wear":
            garment = (parsed.metadata or {}).get("garment")
            if not garment:
                known = sorted(k for k in (self.world.appearance_reactions or {})
                               if not k.startswith("_"))
                return TurnResult(self.world.world_time, player.location, parsed,
                                  "Nothing here answers to that. This world knows: "
                                  + ", ".join(k.split(":")[-1].replace("_", " ")
                                              for k in known)
                                  if known else
                                  "This world does not say what any garment means.")
            player.appearance = dict(player.appearance or {})
            player.appearance["garment"] = garment
            return TurnResult(self.world.world_time, player.location, parsed,
                              "You are wearing %s. Nobody has been told; they can "
                              "see it." % garment.split(":")[-1].replace("_", " "))
        if parsed.intent == "wait":
            self.advance_time(parsed.minutes)
            return TurnResult(self.world.world_time, player.location, parsed,
                              f"Time advances by {parsed.minutes} minutes.\n"
                              + self.describe_location(player.location),
                              developer_trace=views.fmt_last_trace(self.core, "_director"))
        if parsed.intent == "listen_radio":
            return self._listen_radio(parsed)
        if parsed.intent == "inspect":
            target = parsed.target_id or self._default_target()
            trace = self.inspect_agent(target) if target else self.inspect_world()
            return TurnResult(self.world.world_time, player.location, parsed, trace,
                              developer_trace=trace)

        target = parsed.target_id or self._default_target()
        if not target:
            return TurnResult(self.world.world_time, player.location, parsed,
                              "No reachable NPC target is clear from that command.")
        parsed.target_id = target
        if parsed.intent in {"ask", "say", "claim", "promise", "threaten", "accuse",
                             "attack", "assist"}:
            target_agent = self.world.agents.get(target)
            if target_agent and target_agent.location != player.location:
                return TurnResult(
                    self.world.world_time,
                    player.location,
                    parsed,
                    f"{self.agent_name(target)} is not reachable from "
                    f"{self.world.place_label(player.location)}. Move closer or emit an engine event.",
                )

        if parsed.intent in {"ask", "say", "claim", "promise", "threaten", "accuse",
                             "assist"}:
            receipts += self._handle_social_input(parsed)
            npc_response = self.respond(target, topic=parsed.topic)
            developer_trace = self.inspect_agent(target)
            msg = f'{self.agent_name(target)}: "{npc_response.text}"'
            return TurnResult(self.world.world_time, player.location, parsed, msg,
                              receipts=receipts, npc_response=npc_response,
                              developer_trace=developer_trace)

        if parsed.intent == "attack":
            return self._attack(parsed)

        return TurnResult(self.world.world_time, player.location, parsed,
                          "The command parsed, but no runtime handler is registered for it.")

    def query_belief(self, agent_id: str, proposition: Proposition):
        agent = self.world.agents[agent_id]
        return agent.beliefs.get(proposition.core_key())

    def retrieve_memories(self, agent_id: str, topics=None):
        agent = self.world.agents[agent_id]
        self.core._catch_up(agent)  # LOD: mood-congruent retrieval needs current mood
        return self.core.memory.retrieve(agent.memory, self.world.world_time,
                                         topics=topics,
                                         mood_valence=agent.affect.mood.p,
                                         seed_parts=(self.world.global_seed,
                                                     agent.id, "recall"))

    def explain_knowledge(self, agent_id: str) -> str:
        return views.fmt_beliefs(self.world.agents[agent_id])

    def inspect_agent(self, agent_id: str) -> str:
        agent = self.world.agents[agent_id]
        self.core._catch_up(agent)  # LOD: realise deferred decay before reading
        parts = [
            views.fmt_affect(agent),
            views.fmt_beliefs(agent),
            views.fmt_memory(agent, self.world.world_time),
            views.fmt_last_trace(self.core, agent_id),
        ]
        return "\n".join(parts)

    def inspect_world(self) -> str:
        lines = [f"world_time={self.world.world_time}",
                 f"capabilities={self.capability_plan.resolved}",
                 "factions:"]
        for fid, faction in self.core.director.factions.items():
            clocks = ", ".join(f"{c.name} {c.filled}/{c.size}" for c in faction.clocks.values())
            lines.append(f"  {fid}: influence={faction.influence:.2f} heat={faction.heat:.2f} {clocks}")
        return "\n".join(lines)

    def create_snapshot(self, label: str | None = None) -> SnapshotId:
        if not self.store:
            raise RuntimeError("Snapshots require a storage provider.")
        if self.core.population_lod:  # realise deferred decay so the snapshot is exact
            for agent in self.world.agents.values():
                self.core._catch_up(agent)
        data = snapshot.capture(self.world, self.core)
        return SnapshotId(self.store.save_snapshot(data, label=label))

    def restore_snapshot(self, snapshot_id: SnapshotId | str) -> list:
        """Rewind the world to a snapshot. Returns reason entries for anything notable
        (schema/seed mismatch, agents or factions the snapshot and pack disagree on)."""
        if not self.store:
            raise RuntimeError("Snapshots require a storage provider.")
        sid = snapshot_id.value if isinstance(snapshot_id, SnapshotId) else snapshot_id
        data = self.store.load_snapshot(sid)
        return snapshot.restore(data, self.world, self.core)

    def list_snapshots(self) -> list:
        if not self.store:
            raise RuntimeError("Snapshots require a storage provider.")
        return self.store.list_snapshots()

    def replay_commands(self, commands: list[str], *, replay_id: str = "replay") -> ReplayResult:
        steps = []
        for command in commands:
            result = self.submit_player_text(command)
            trace_hash = hashlib.sha256(result.developer_trace.encode("utf-8")).hexdigest()
            steps.append(ReplayStep(command, self.world.world_time, result.message, trace_hash))
        return ReplayResult(replay_id, steps, self.world.world_time)

    # ---------- terminal client behavior ----------
    def describe_location(self, location_id: str) -> str:
        place = self.world.places.get(location_id, {})
        agents = [a for a in self.world.agents.values()
                  if a.location == location_id and a.id != self.config.player_id]
        exits = self.world.exits_from(location_id)
        lines = [f"{self.world.place_label(location_id)}",
                 f"noise={place.get('noise_level', 0):.2f} surveillance={place.get('surveillance_level', 0):.2f} "
                 f"privacy={place.get('privacy_level', 0):.2f}"]
        if agents:
            lines.append("NPCs: " + ", ".join(self.agent_name(a.id) for a in agents))
        else:
            lines.append("NPCs: none visible")
        lines.append("Exits: " + ", ".join(self.world.place_label(e) for e in exits))
        return "\n".join(lines)

    def agent_name(self, agent_id: str) -> str:
        agent = self.world.agents.get(agent_id)
        return (agent.public_name or agent_id) if agent else agent_id

    def load_initial_state(self):
        if self._initial_state_loaded:
            return
        self._initial_state_loaded = True
        for belief in self.world.initial_beliefs:
            prop = Proposition.from_dict(belief["proposition"])
            self._seed_belief(
                belief["agent"], prop,
                belief.get("summary", str(prop)),
                belief["origin_event"],
                float(belief.get("trust", 0.75)),
                competence=float(belief.get("competence", 0.75)),
                importance=float(belief.get("importance", 0.6)),
            )

    # ---------- handlers ----------
    def _move_player(self, parsed: ParsedCommand) -> TurnResult:
        player = self.world.agents[self.config.player_id]
        if parsed.location_id not in self.world.exits_from(player.location):
            return TurnResult(self.world.world_time, player.location, parsed,
                              f"You cannot move directly to "
                              f"{self.world.place_label(parsed.location_id)}.")
        player.location = parsed.location_id
        ev = Event(self.world.new_event_id(), self.world.world_time, "move",
                   actor=self.config.player_id, location=player.location,
                   payload={"summary": f"player arrives at {player.location}"})
        receipt = self.emit_event(ev)
        return TurnResult(self.world.world_time, player.location, parsed,
                          self.describe_location(player.location), receipts=[receipt])

    def _listen_radio(self, parsed: ParsedCommand) -> TurnResult:
        due = [e.world_time for e in self.world.scenario_events if e.type == "broadcast"]
        if due:
            minutes = max(0, min(due) - self.world.world_time)
            self.advance_time(minutes)
            msg = "You catch the next city-news bulletin."
        else:
            self.advance_time(15)
            msg = "Only recycled adverts and static are on the public band."
        player = self.world.agents[self.config.player_id]
        return TurnResult(self.world.world_time, player.location, parsed,
                          msg + "\n" + self.describe_location(player.location),
                          developer_trace=self.inspect_world())

    def _handle_social_input(self, parsed: ParsedCommand) -> list[EventReceipt]:
        receipts = []
        if parsed.intent == "ask" and parsed.proposition:
            # A question is NOT an assertion. This carried the proposition on a
            # "claim" event, so everyone in earshot -- including the person being
            # asked -- updated their belief as though the player had stated it as
            # fact. Asking Voss about the seal made Voss surer the seal had failed,
            # and asking twenty times would have walked any belief to certainty
            # from nothing. A "question" event is perceived and remembered, so a
            # character knows they were asked and can react to being asked, but it
            # is not evidence and does not move belief.
            ev = Event(self.world.new_event_id(), self.world.world_time, "question",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={"proposition": parsed.proposition.as_dict(),
                                "summary": f"player asks about {parsed.topic}",
                                "importance": 0.45,
                                "origin_event": f"player_turn_{self.world.world_time}"})
            receipts.append(self.emit_event(ev))
            receipts += self._topic_reactions(parsed.topic, parsed.target_id)
        elif parsed.intent == "claim" and parsed.proposition:
            ev = Event(self.world.new_event_id(), self.world.world_time, "claim",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={"proposition": parsed.proposition.as_dict(),
                                "summary": "player makes a claim",
                                "importance": 0.5,
                                "origin_event": f"player_claim_{self.world.world_time}"})
            receipts.append(self.emit_event(ev))
        elif parsed.intent == "promise" and parsed.proposition:
            ev = Event(self.world.new_event_id(), self.world.world_time, "promise",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={"proposition": parsed.proposition.as_dict(),
                                "summary": f"player promised to pay {parsed.amount} credits",
                                "importance": 0.75,
                                # WHO IT WAS MADE TO. Carried on the event rather
                                # than only used for the trust bump below, because
                                # a promise to nobody in particular is a statement
                                # of intent and the ledger has to tell them apart.
                                "target": parsed.target_id,
                                "appraisal": {"desirability": 0.25}})
            receipts.append(self.emit_event(ev))
            # Making one is rewarded immediately, which was fine while nothing
            # ever came due and is the exact asymmetry that made promises free:
            # +0.35 for saying it, nothing for failing it. With the promises
            # layer on, breaking it costs -0.7 and more than undoes this.
            self._apply_trust(parsed.target_id, self.config.player_id, +0.35, "promise_made")
        elif parsed.intent == "assist":
            # The counterpart to `threaten`, and until now there was none. Kind
            # acts are quieter than cruel ones -- lower severity, lower
            # importance -- which is why `standing` weights `helped` below
            # `mistreated` rather than treating decency as symmetrical.
            ev = Event(self.world.new_event_id(), self.world.world_time, "gift",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={**self._conduct_claim("helped", parsed.target_id),
                                "summary": f"player helps {parsed.target_id}",
                                "severity": 0.3, "importance": 0.5,
                                "target": parsed.target_id,
                                "appraisal": {"desirability": 0.5, "agency": "other",
                                              "praiseworthiness": 0.5}})
            receipts.append(self.emit_event(ev))
            self._apply_trust(parsed.target_id, self.config.player_id, +0.30, "helped")
        elif parsed.intent == "threaten":
            ev = Event(self.world.new_event_id(), self.world.world_time, "threat",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={**self._conduct_claim("mistreated", parsed.target_id),
                                "summary": f"player threatens {parsed.target_id}",
                                "severity": 0.6, "importance": 0.7,
                                # Who it was done TO. Previously only in the
                                # summary string, which meant no layer could act
                                # on it -- including the one that exists to make
                                # a group react when one of its own is hurt.
                                "target": parsed.target_id,
                                "appraisal": {"desirability": -0.6, "agency": "other",
                                              "praiseworthiness": -0.4}})
            receipts.append(self.emit_event(ev))
            self._apply_trust(parsed.target_id, self.config.player_id, -0.45, "threatened")
        elif parsed.intent == "accuse":
            ev = Event(self.world.new_event_id(), self.world.world_time, "claim",
                       actor=self.config.player_id,
                       location=self.world.agents[self.config.player_id].location,
                       payload={"summary": f"player accuses {parsed.target_id} about {parsed.topic}",
                                "importance": 0.65,
                                "appraisal": {"desirability": -0.3}})
            receipts.append(self.emit_event(ev))
        return receipts

    #: With `standing` on, an act is put into the world as a claim as well as an
    #: event, so that it is perceived, believed, passed on and doubted by the
    #: machinery that already exists. Off, nothing is attached and the payload is
    #: byte for byte what it was.
    def _conduct_claim(self, predicate: str, victim_id: str) -> dict:
        """The claim an act attaches to the world, as ONE INCIDENT.

        `valid_start` is what individuates it, and leaving it off was a real
        defect rather than a detail. Without it every unkindness the player ever
        did to one person collapsed into a single proposition -- so six separate
        threats were one claim heard six times, the correlation discount
        (correctly) refused to be persuaded by the repetition, and the town could
        not tell a person who did something once from a person who kept doing it.

        With it, a repeated REPORT of one incident is still one incident -- which
        is what `standing.judge` applies once -- while a second act is a second
        incident, because it happened at a different time and is a different
        thing to have done.
        """
        if not self.core.standing.enabled or not victim_id:
            return {}
        return {"proposition": {
            "predicate": predicate,
            "slots": {"who": victim_id, "by": self.config.player_id},
            "polarity": "+",
            "valid_start": self.world.world_time}}

    def _attack(self, parsed: ParsedCommand) -> TurnResult:
        player = self.world.agents[self.config.player_id]
        target = parsed.target_id or self._default_target()
        ev = Event(self.world.new_event_id(), self.world.world_time, "attack",
                   actor=self.config.player_id, location=player.location,
                   payload={**self._conduct_claim("mistreated", target),
                            "summary": f"player attacks {target}",
                            "severity": 0.8, "importance": 0.9,
                            "target": target,
                            "appraisal": {"desirability": -0.8, "agency": "other",
                                          "praiseworthiness": -0.6,
                                          "target": self.config.player_id}})
        receipt = self.emit_event(ev)
        if target in self.world.agents:
            self.core._catch_up(self.world.agents[target])  # LOD: react from current affect
        chosen, _, reasons = self.core.decide(target, interlocutor=self.config.player_id,
                                              situation={"injured": True, "threatened": True,
                                                         "threat_severity": 0.8})
        extra = ""
        if chosen.action.action_id == "mobilize_allies":
            mob = self.core.mobilize(target, urgency=1.0)
            extra = "\n" + "\n".join(f"{r[2]['ally']} {r[2]['outcome']} (p={r[1]:.2f})"
                                     for r in mob["reasons"])
        msg = f"{self.agent_name(target)} reacts with {chosen.action.action_id}.{extra}"
        return TurnResult(self.world.world_time, player.location, parsed, msg,
                          receipts=[receipt],
                          developer_trace="\n".join(str(r) for r in reasons))

    def _topic_reactions(self, topic_id: str | None, addressee_id: str | None) -> list:
        """Fire the events a pack authored for this topic being raised.

        Some subjects are themselves an act: asking a gang fixer about her hidden
        brother is a threat to her. That is a fact about a particular world, so it
        is authored in ``topics.json`` rather than special-cased in the SDK, which
        is where the reference scene's version of it used to live."""
        topic = self.world.topics.get(topic_id) if topic_id else None
        if topic is None:
            return []
        receipts = []
        for spec in topic.resolved_reactions(self.config.player_id, addressee_id):
            payload = dict(spec.get("payload") or {})
            payload.setdefault("topic", topic.topic_id)
            receipts.append(self.emit_event(Event(
                self.world.new_event_id(), self.world.world_time, spec["type"],
                actor=spec.get("actor") or self.config.player_id,
                location=spec.get("location")
                or self.world.agents[self.config.player_id].location,
                payload=payload)))
        return receipts

    # ---------- internal helpers ----------
    def _seed_belief(self, agent_id: str, prop: Proposition, summary: str,
                     origin_event: str, trust: float, *, competence: float = 0.85,
                     importance: float = 0.7):
        agent = self.world.agents.get(agent_id)
        if not agent:
            return
        belief, _ = self.core.belief.update(
            agent.beliefs, prop, asserter_polarity=prop.polarity,
            trust=trust, competence=competence, skepticism=agent.skepticism,
            claim_id=f"seed:{origin_event}", origin_event=origin_event,
            world_time=self.world.world_time)
        mem = Memory(memory_id=f"mem:{origin_event}", owner=agent_id, type="episodic",
                     content=summary, proposition=prop, importance=importance,
                     emotional_valence=0.0, source_conf=trust)
        self.core.memory.encode(agent.memory, mem, self.world.world_time)
        if self.store:
            self.store.save_agent(agent)

    def _direct_answer(self, agent_id: str, interlocutor: str, topic: str | None,
                       gate_reasons: list | None = None):
        if not topic:
            return None
        # The player has now met this character, so their state becomes worth
        # keeping warm for the inspector and any debug HUD.
        self.core.project_for(agent_id)
        agent = self.world.agents[agent_id]
        # multi-turn continuity: this conversation persists across turns (and save/load).
        conv = self.core.conversations.setdefault(
            f"conv_{agent_id}_{interlocutor}",
            ConversationState(f"conv_{agent_id}_{interlocutor}", [agent_id, interlocutor]))
        times_asked = conv.discussed_topics.get(topic, 0)  # before recording this turn
        topic_prop = self._topic_query(topic)

        # 1. Trust gate FIRST. Any secret this character holds that guards this topic
        #    decides whether they will engage with the subject at all -- before, and
        #    independently of, whether they happen to have something sayable. Checking
        #    it after the fact filter hid the gate exactly when the character's only
        #    knowledge of the topic was the protected proposition itself, which is the
        #    case it exists for. The predecessor of this check read `topic == "milan"`,
        #    so the protection existed for one character in one pack.
        guarding = content.secrets_guarding(agent.secrets, topic)
        # A secret that is common knowledge in this character's own community has
        # stopped being one. Chwe's point exactly: concealment is not about who
        # has found out, it is about whether everybody knows that everybody has --
        # and once they do, refusing to discuss it protects nothing and only
        # marks you as the person refusing. Note what this does NOT do: it does
        # not make the character believe anything new, and it does not oblige
        # them to be helpful. It removes the grounds for stonewalling.
        spent = [s for s in guarding if self._secret_is_out(agent, s)]
        if spent:
            guarding = [s for s in guarding if s not in spent]
            self.core.last_traces.setdefault("_common_knowledge", []).append(
                ("common_knowledge.secret_spent", float(len(spent)), {
                    "agent": agent.id, "topic": topic,
                    "secrets": [s.secret_id for s in spent],
                    "note": "it is out in the open; denying it protects nothing"}))
        # How open the room is to a stranger shifts what the player's trust is
        # worth here -- the same person, in a place that has just had a killing
        # in it, gets less. Zero when the climate layer is off.
        trust = max(0.0, min(1.0, agent.trust_in(interlocutor)
                             + self.core.climate.modifiers(agent.location)["stranger_trust"]))
        withholding = [s for s in guarding if trust < s.min_trust]
        if withholding:
            # Refuse, or lie? A character with an authored cover story and little
            # commitment to the truth says something else instead of falling
            # silent -- and what they say is a real claim, from them, which the
            # listener may later find contradicted.
            lying = next((sec for sec in withholding if agent.will_lie_about(sec)), None)
            if lying is not None:
                deceit = self._tell_a_lie(agent, interlocutor, topic, lying, conv)
                if deceit is not None:
                    return deceit
        if withholding:
            # Below the authored threshold the caller falls through to ordinary
            # deliberation (evade/deflect) rather than answering.
            reason = ("dialogue.secret_gate", trust,
                      {"topic": topic, "trust": round(trust, 3),
                       "required": min(s.min_trust for s in withholding),
                       "secrets": [s.secret_id for s in withholding],
                       "note": "below authored trust threshold; will not discuss"})
            if gate_reasons is not None:
                gate_reasons.append(reason)
            self.core.last_traces[agent_id] = [reason]
            return None

        # 2. Collect what they may say. A protected proposition is never an allowed
        #    fact at any trust level -- trust unlocks engagement, not disclosure -- so
        #    it cannot reach a text provider's context at all (spec §4.2 Layer 0).
        protected_keys = content.protected_keys(agent.secrets) - self._keys_out(agent)
        candidates = []
        for belief in agent.beliefs.values():
            confidence = max(belief.expected_prob, 1.0 - belief.expected_prob)
            if confidence < 0.6:
                continue
            fit = relevance(belief.proposition, topic_prop) if topic_prop else 1.0
            if topic_prop and fit == 0.0:
                continue
            affirmed = belief.expected_prob >= 0.5
            fact_prop = belief.proposition if affirmed else belief.proposition.negated()
            if (belief.proposition.core_key() in protected_keys
                    or str(fact_prop) in protected_keys):
                continue
            candidates.append(Candidate(proposition=belief.proposition,
                                        confidence=confidence, relevance=fit,
                                        affirmed=affirmed))
        if not candidates:
            return None

        # THE decision that used to belong to the text layer. The runtime picks
        # which of the relevant things this character says; the realizer renders
        # it. Seeded, so the answer varies between worlds and stays replayable
        # within one.
        commitment = commit_moves(
            candidates, act="assert", limit=2,
            seed_parts=(self.world.global_seed, agent_id, conv.turn_count,
                        self.world.world_time, "dialogue"),
            forbidden=content.avoid_labels(guarding or agent.secrets))
        # NOTHING IS COMMITTED THAT THE ANSWER CANNOT SAY. The phrasing authored
        # for this topic words ONE claim -- the topic's own query -- and the
        # selection above could pick two. The second was propagated to everyone in
        # the room by a sentence that never mentioned it: a character who knew the
        # clinic was shut last night and open today said only the first and taught
        # the room both.
        phrasing = self._answer_phrasing(agent, topic, topic_prop)
        commitment = self._only_what_can_be_said(commitment, phrasing, topic_prop)
        facts = list(commitment.rendered_facts())
        if not facts:
            return None

        style = self.core.style_for(agent, interlocutor)
        plan = DialoguePlan(agent_id, interlocutor, "inform",
                            goal=agent.goals[0]["content"] if agent.goals else "answer",
                            avoid_topics=content.avoid_labels(guarding or agent.secrets),
                            style=style.as_dict(),
                            phrasing=phrasing,
                            request_id=f"direct:{agent_id}:{self.world.world_time}:"
                                       f"{conv.turn_count}").commit(commitment)
        # a re-asked topic gets a terser answer (the NPC already told the player this)
        if times_asked >= 1:
            plan.max_length = max(10, plan.max_length // 2)
        return self._deliver(agent, interlocutor, plan, commitment, conv, topic)

    def _only_what_can_be_said(self, commitment, phrasing: dict, query):
        """Keep only the moves the authored answer actually words.

        A pack authors a phrasing per TOPIC, and it says one thing: whether the
        topic's own query holds. Any other proposition the selection reached for
        has no sentence behind it, so committing to it means asserting something
        nobody says -- which is the mismatch between the player and the room that
        controlled release exists to prevent, arriving from the runtime's own side
        rather than a provider's.

        With no phrasing there is nothing factual to say at all: the realizer
        would fall back to a stance line, and a stance line asserts nothing.
        """
        keep, dropped = [], []
        covered = query.core_key() if query is not None else None
        for move in commitment.moves:
            if not move.is_factual:
                keep.append(move)
            elif phrasing and covered and move.proposition.core_key() == covered:
                keep.append(move)
            else:
                dropped.append(move)
        if not dropped:
            return commitment
        reasons = list(commitment.reasons) + [
            ("commitment.unsayable_dropped", float(len(dropped)), {
                "dropped": [move.rendered() for move in dropped],
                "kept": [move.rendered() for move in keep if move.is_factual],
                "note": "no authored phrasing words these, so nothing commits to "
                        "them and nothing propagates"})]
        return commitment_mod.Commitment(
            moves=tuple(keep), forbidden=commitment.forbidden,
            max_sentences=commitment.max_sentences, reasons=reasons)

    def _deliver(self, agent, interlocutor: str, plan, commitment, conv, topic,
                 *, kind: str = "direct_answer", extra_reasons=()) -> "DialogueResponse":
        """Realize, validate, release, and let the world hear what was committed.

        Both the honest answer and the lie come through here, and they go through
        exactly the same checks. A lie is not a special case of speaking -- it is
        an ordinary commitment whose proposition happens not to be what the
        speaker believes -- so giving it its own release path would be the place a
        bug would hide.
        """
        agent_id = agent.id
        facts = list(plan.allowed_facts)
        provider_reasons = []
        # WHO WROTE THE LINE, kept as the object rather than a flag, because the
        # commitment check has to ask the realizer that actually produced the
        # text. Asking the provider about a sentence the fallback wrote reads a
        # flag left over from a call that never returned.
        text, wrote_it, raw_provider_output, provider_failed = self.core.write_the_line(
            plan, provider_reasons)
        authored = getattr(wrote_it, "is_deterministic", False)
        # A thrown provider costs the WORDING, not the content: the authored
        # phrasing says the same thing, so a commitment it expresses still
        # reaches the world. `fallback_used` used to be set here and voided it,
        # which made a model's failure mode change what the society knew.
        fallback_used = False
        recent = conv.recent_lines
        result = self.core.validator.check(text, plan, agent, recent,
                                           canon_mode=CANON_OFF if authored else None)
        # A REJECTION IS TWO DIFFERENT ANSWERS, and treating them as one was the
        # defect. An UNSAFE line must not be released and its commitment must not
        # reach the world. A REPEATED line is a quality objection: the runtime
        # looks for another complete wording of the same commitment, and failing
        # that says it again -- rather than letting an earlier sentence decide
        # whether a later fact enters the society.
        if result.verdict != "ACCEPT":
            if is_unsafe(result):
                fallback_used = True
                provider_reasons += result.reasons
                provider_reasons.append(("dialogue.validation_fallback", 1.0,
                                         {"from_verdict": result.verdict}))
                plan.dialogue_act = plan.fallback_template_id
                # A deflection has to deflect. `_lookup` prefers the authored
                # phrasing over the act, so leaving it in place released the same
                # sentence again and called it a fallback.
                plan.phrasing = {}
                wrote_it = self.core.fallback_realizer
                text = wrote_it.realize(plan, plan.style)
                result = self.core.validator.check(text, plan, agent, recent,
                                                   canon_mode=CANON_OFF)
            else:
                reworded = False
                for spare in self.core.fallback_realizer.variants(plan, plan.style):
                    if spare == text:
                        continue
                    retry = self.core.validator.check(spare, plan, agent, recent,
                                                      canon_mode=CANON_OFF)
                    if retry.verdict == "ACCEPT":
                        provider_reasons.append(("dialogue.reworded", 1.0, {
                            "was": text, "now": spare,
                            "why": [code for code, _m, _d in result.reasons]}))
                        text, result = spare, retry
                        wrote_it = self.core.fallback_realizer
                        reworded = True
                        break
                if not reworded:
                    provider_reasons += result.reasons
                    provider_reasons.append(("dialogue.released_anyway", 1.0, {
                        "verdict": result.verdict,
                        "note": "a quality objection, not a safety one; the "
                                "commitment stands"}))
                    # AND THE VERDICT SAYS SO. Releasing the line while returning
                    # the rejection left the status, the emission and the audit
                    # disagreeing: from the fourth identical question onward the
                    # claim reached the room, `accepted_output` was blank and the
                    # caller got REJECT_SOFT -- so a client that hides rejected
                    # answers showed the player nothing the room had just heard.
                    # One decision, recorded once. `Runtime.say` already did this;
                    # this path is now the same contract.
                    result = replace(result, verdict="ACCEPT")
        recent.append(text)
        del recent[:-5]  # bound the anti-repeat window
        times_now = conv.note_topic(topic, self.world.world_time) if topic else 0
        # What was COMMITTED enters the world, never what the provider wrote. If
        # the line was replaced by a fallback the commitment is void: nothing was
        # actually asserted, so nothing may propagate.
        # A commitment the text layer could not express is void. The player must
        # never read a deflection while the room hears an assertion.
        expressed = self._carried(wrote_it, text, plan)
        if not expressed and not fallback_used and plan.moves:
            # THE MODEL CHOOSES THE SENTENCE. IT DOES NOT CHOOSE WHETHER THE
            # WORLD HEARS ONE.
            #
            # A line that did not carry the commitment used to void it, so the
            # provider -- and, once there is a latency budget, its RESPONSE TIME
            # -- decided whether a belief entered the society at all. Two
            # accepted answers to the same question in the same world produced
            # two different worlds, and "the model only chooses the wording" was
            # not true in the one sense that matters.
            #
            # What gets replaced is the wording, not the content: the pack's own
            # phrasing for this answer is deterministic and was written to say
            # exactly this. Only if THAT cannot express it is the commitment
            # void -- and that outcome depends on the pack, not on the provider.
            spare = self.core.fallback_realizer.realize(plan, plan.style)
            if spare != text and self._carried(self.core.fallback_realizer, spare, plan):
                recheck = self.core.validator.check(spare, plan, agent, recent,
                                                    canon_mode=CANON_OFF)
                if recheck.verdict == "ACCEPT":
                    provider_reasons.append(("dialogue.wording_replaced", 1.0, {
                        "provider_said": text, "released": spare,
                        "committed": list(plan.allowed_facts),
                        "note": "the provider's line did not carry the "
                                "commitment; the pack's phrasing did"}))
                    text, result, expressed = spare, recheck, True
        if not expressed:
            provider_reasons.append(
                ("dialogue.commitment_unexpressed", 1.0,
                 {"committed": list(plan.allowed_facts),
                  "note": "no authored phrasing carries this; nothing was asserted"}))
        spoken_moves = () if (fallback_used or not expressed) else plan.moves
        spoken = self._speak_aloud(agent, spoken_moves, interlocutor)

        reasons = provider_reasons + list(commitment.reasons) + [
            (f"dialogue.{kind}", 1.0, {"topic": topic, "facts": facts,
                                       "spoken": spoken,
                                       "times_asked": times_now, "turn": conv.turn_count})
        ] + list(extra_reasons) + result.reasons
        if times_now > 1:
            reasons.append(("dialogue.topic_repeated", float(times_now),
                            {"topic": topic, "note": "player re-asked; answer kept terse"}))
        conv.turn_count += 1
        self.core.last_traces[agent_id] = reasons
        if self.store and hasattr(self.store, "save_provider_call"):
            prompt_data = {
                "speaker": plan.speaker,
                "addressee": plan.addressee,
                "act": plan.dialogue_act,
                "allowed_facts": plan.allowed_facts,
                "avoid_topics": plan.avoid_topics,
                "style": plan.style,
            }
            prompt_hash = hashlib.sha256(
                json.dumps(prompt_data, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            self.store.save_provider_call(
                turn_id=f"{kind}:{agent_id}:{self.world.world_time}:{conv.turn_count}",
                world_time=self.world.world_time,
                provider=type(wrote_it).__name__,
                model_id=getattr(wrote_it, "model_id", "deterministic-template"),
                prompt_hash=prompt_hash,
                raw_output=raw_provider_output if raw_provider_output is not None else text,
                accepted_output=text if result.verdict == "ACCEPT" else "",
                validation_result=result.verdict,
                data={"plan": prompt_data, "reasons": reasons,
                      "fallback_used": fallback_used,
                      "provider_failed": provider_failed},
            )
        return DialogueResponse(agent_id, text, plan.dialogue_act, result.verdict, 1.0, reasons, plan.style)

    def discredit(self, source_id: str, *, factor: float = 0.25,
                  reason: str = "exposed", predicate: str | None = None):
        """Expose a source: recompute everything they convinced anyone of.

        Lowering trust changes what they will manage to convince people of next
        time. This is the other half -- what they already convinced people of
        stops counting, in proportion, and only where their word was actually
        carrying it.
        """
        from . import revision
        outcome = revision.discredit(self.world, source_id, factor=factor,
                                     reason=reason, predicate=predicate)
        self.core.last_traces.setdefault("_revision", []).extend(outcome.reasons)
        return outcome

    def resting_on(self, source_id: str) -> list:
        """What currently rests on this source's word, without changing anything."""
        from . import revision
        return revision.would_change(self.world, source_id)

    #: How many bystanders can overhear one exchange. Matches the diffusion
    #: layer's figure, because it is the same physical fact about a room.
    EARSHOT = 3

    def _earshot(self, speaker, addressee: str) -> list:
        """Who is close enough to hear this exchange. Owned by the runtime."""
        return self.core.earshot(speaker, addressee)

    def _keys_out(self, agent) -> set:
        """Which of this character's protected facts are already public.

        Empty whenever the common-knowledge layer is off, which is what keeps the
        secret machinery byte-identical without it.
        """
        public = self.core.common_knowledge
        if not public.enabled:
            return set()
        return {key for key in content.protected_keys(agent.secrets)
                if public.is_out(key, agent.id)}

    def _secret_is_out(self, agent, secret) -> bool:
        """Has this secret stopped working?

        Every fact it protects has to be public, not merely one of them: a secret
        guarding three things is still doing a job while one of them is unknown.
        A secret that protects nothing in particular is never spent this way --
        there is nothing for a crowd to have witnessed.
        """
        public = self.core.common_knowledge
        protects = set(getattr(secret, "protects", ()) or ())
        if not public.enabled or not protects:
            return False
        return all(public.is_out(key, agent.id) for key in protects)

    def _tell_a_lie(self, agent, interlocutor: str, topic, secret, conv):
        """Say the authored cover story instead of refusing.

        Four things are kept apart, and this is where they separate: what the
        speaker BELIEVES, what they WANT, what they SAY, and what they intend the
        listener to believe afterwards. The move carries the cover story as its
        proposition and the speaker's real confidence in it as
        `believed_probability`, so the divergence is on the record rather than
        implied.

        The lie is a real claim from a real person. The listener acquires it with
        this character as its origin -- which is what makes it refutable later,
        and what makes exposing the liar do something.
        """
        template = content.resolve_template(secret.cover_story, self.config.player_id,
                                            interlocutor)
        if not template:
            return None
        try:
            claim = Proposition.from_dict(template)
        except Exception:
            return None

        held = agent.beliefs.get(claim.core_key())
        really_thinks = held.expected_prob if held is not None else 0.0
        move = SemanticMove(act="assert", proposition=claim,
                            certainty=commitment_mod.CERTAIN,
                            disclosure=commitment_mod.DIRECT,
                            honesty=commitment_mod.LIE,
                            believed_probability=really_thinks)
        lie = commitment_mod.Commitment(
            moves=(move,), forbidden=tuple(content.avoid_labels([secret])),
            reasons=[("dialogue.deception", 1.0,
                      {"secret": secret.secret_id,
                       "asserted": str(claim),
                       "speaker_believes_it_with": round(really_thinks, 3),
                       "truthfulness": round(agent.value("truthfulness"), 3),
                       "stake": secret.min_trust,
                       "note": "cover story: the stake outweighed their honesty"})])

        style = self.core.style_for(agent, interlocutor)
        plan = DialoguePlan(agent.id, interlocutor, "inform",
                            goal="protect " + secret.secret_id,
                            avoid_topics=content.avoid_labels([secret]),
                            style=style.as_dict(),
                            phrasing=dict(getattr(secret, "cover_phrasings", {}) or {}),
                            request_id=f"lie:{agent.id}:{self.world.world_time}:"
                                       f"{conv.turn_count}").commit(lie)
        plan.stance = "deceptive"
        return self._deliver(agent, interlocutor, plan, lie, conv, topic, kind="deception")

    def _carried(self, realizer, text: str, plan) -> bool:
        """Did these words make the claim that was committed? Owned by the runtime."""
        return self.core.carried(realizer, text, plan)

    def _speak_aloud(self, agent, moves, addressee: str) -> list:
        """Emit what was committed as a real claim event. Owned by the runtime.

        THERE IS ONE IMPLEMENTATION, and there used to be one and a half: this
        path emitted the claim and `Runtime.say()` did not, so the same runtime
        had two ways to speak and only one of them changed the world.
        """
        return self.core.speak_aloud(agent, moves, addressee)

    def _spoken_origin(self, agent, move) -> str:
        """Which incident a spoken claim traces back to. Owned by the runtime."""
        return self.core.spoken_origin(agent, move)

    def _domain_for(self, proposition) -> str:
        """Which competence applies to this claim. Owned by the runtime."""
        return self.core.domain_for(proposition)

    def _answer_phrasing(self, agent, topic_id: str | None, query: Proposition | None) -> dict:
        """How this character words an answer on this topic, given what they believe.

        The engine ships no factual sentences: an ``inform`` line has to come from
        the pack, because only the pack knows what is true in its world. If a topic
        authors no phrasing the realizer falls back to a deflection, so a character
        can never assert a fact borrowed from another world -- which is what the
        old built-in ``inform`` template did.
        """
        topic = self.world.topics.get(topic_id) if topic_id else None
        if topic is None or query is None or not topic.phrasings:
            return {}
        belief = agent.beliefs.get(query.core_key())
        if belief is None:
            return {}
        holds = belief.expected_prob >= 0.5
        affirmed = holds if query.polarity == "+" else not holds
        return topic.phrasing_for(affirmed)

    def _topic_query(self, topic_id: str | None) -> Proposition | None:
        """The proposition a belief must be relevant to for this topic. Authored."""
        topic = self.world.topics.get(topic_id) if topic_id else None
        if topic is None:
            return None
        query = topic.resolved_query(self.config.player_id)
        return Proposition.from_dict(query) if query else None

    def _apply_trust(self, owner_id: str, subject_id: str, amount: float, reason: str):
        owner = self.world.agents.get(owner_id)
        if not owner:
            return
        reasons = []
        self.core.relationship.apply(owner, [trust_delta(owner_id, subject_id, amount, reason, "sdk")],
                                     reasons)
        self.core.last_traces[owner_id] = self.core.last_traces.get(owner_id, []) + reasons
        if self.store:
            self.store.save_agent(owner)

    def _default_target(self) -> str | None:
        """Who the player means when they address nobody in particular.

        Order: the scene's authored focus agents, then the sole NPC present, then
        the first by id. The focus order used to be three hardcoded character ids
        from the reference pack; it is now ``scenario.json: focus_agents``, which
        is where "who this scene is about" belongs.
        """
        player = self.world.agents[self.config.player_id]
        nearby = {a.id for a in self.world.agents.values()
                  if a.id != self.config.player_id and a.location == player.location}
        for preferred in self.world.focus_agents:
            if preferred in nearby:
                return preferred
        return sorted(nearby)[0] if nearby else None

