"""HTTP/JSON service mode for engine and third-party integrations.

The service is a thin, explicit ABI over :class:`~unscripted.sdk.UnscriptedRuntime`.
Every request is validated before it reaches the runtime, because the runtime
trusts its caller: a negative time delta or a malformed event would otherwise
corrupt world state silently rather than fail loudly.

Three rules hold throughout:

- **Client mistakes are 4xx, not 5xx.** A missing field, a bad type or an
  unknown snapshot id is the caller's error and says so; only genuine internal
  faults return 500.
- **Nothing unbounded is read.** Request bodies are capped before they are read
  into memory, and so are the arguments that drive O(world) work.
- **Safe by default.** Binding anywhere other than loopback requires either an
  auth token or an explicit insecure opt-in, and the state-inspection endpoints
  that expose every NPC's private beliefs can be switched off for a shipping
  build.
"""
from __future__ import annotations

import hmac
import json
import time
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import os

from .bridge import bridge_event_to_world_event, list_bridge_profiles
from .contracts import RUNTIME_VERSION, RuntimeConfig
from .generator import CharacterGenerationRequest, generate_characters
from .sdk import UnscriptedRuntime
from .studio import studio_html
from .webdemo import demo_html

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", ""})

# Endpoints that expose an NPC's full internal state (beliefs with provenance,
# memory, reason traces). Invaluable in development and for the sales demo,
# but a shipping game client has no business reading another character's mind.
DEBUG_ENDPOINTS = frozenset({"/state/agent", "/state/world", "/state/scene",
                             "/state/knowledge", "/v2/state/knowledge",
                             "/v2/resting_on",
                             "/inspect/agent", "/inspect/world", "/avatar/face"})


class ServiceError(Exception):
    """A request the service can reject precisely, with an HTTP status."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def as_response(self):
        return {"error": self.message, "code": self.code}, self.status


@dataclass
class ServiceOptions:
    """Deployment-time settings, kept separate from world/runtime configuration."""

    auth_token: str | None = None
    # /state/* and /inspect/* -- on by default so `unscripted demo` and local integration
    # work out of the box; turn off for a build that ships to players.
    expose_debug_endpoints: bool = True
    max_body_bytes: int = 1 << 20                 # 1 MiB
    max_advance_minutes: int = 60 * 24 * 365      # one world-year per call
    max_text_chars: int = 4000
    max_generated_characters: int = 64
    allow_origin: str | None = None               # CORS; None = no CORS headers
    allow_insecure_bind: bool = False             # required to bind off-loopback unauthenticated
    #: Absolute path of the world pack the authoring UI may edit. None disables
    #: authoring entirely. This is the only surface in the runtime that WRITES to
    #: the filesystem, so it is opt-in, confined to this one directory, and refused
    #: off-loopback regardless of authentication.
    authoring_path: str | None = None

    def check_bind(self, host: str) -> list[str]:
        """Validate a bind address. Returns advisory warnings; raises on unsafe setups."""
        warnings = []
        if host not in LOOPBACK_HOSTS and not self.auth_token and not self.allow_insecure_bind:
            raise ValueError(
                f"Refusing to bind to {host!r} without authentication. The service exposes "
                "world mutation (/turn, /event, /advance, /restore) and, unless disabled, "
                "every NPC's internal state. Pass an auth token, bind to 127.0.0.1, or "
                "opt in explicitly with allow_insecure_bind.")
        if host not in LOOPBACK_HOSTS and self.authoring_path:
            raise ValueError(
                f"Refusing to serve the authoring UI on {host!r}. It writes world-pack "
                "files to disk; bind it to 127.0.0.1.")
        if host not in LOOPBACK_HOSTS and self.expose_debug_endpoints:
            warnings.append(
                f"Bound to {host}: state-inspection endpoints are reachable off-loopback. "
                "Disable them for a shipping build.")
        return warnings


class UnscriptedService:
    def __init__(self, runtime: UnscriptedRuntime, options: ServiceOptions | None = None):
        self.runtime = runtime
        self.options = options or ServiceOptions()

    # ---------------------------------------------------------------- auth ----
    def authorize(self, header_value: str | None, *, query_token: str | None = None) -> None:
        """`query_token` is accepted for the HTML pages and nothing else.

        A browser cannot be made to send an Authorization header by typing a URL,
        and those pages have to be reachable by typing a URL -- so the launcher's
        announced link carries the token and this accepts it there. Every JSON
        route still takes the header only.
        """
        token = self.options.auth_token
        if not token:
            return
        prefix = "Bearer "
        presented = header_value[len(prefix):] if (header_value or "").startswith(prefix) else ""
        if not presented and query_token:
            presented = query_token
        # constant-time compare: token equality must not be probeable by timing
        if not hmac.compare_digest(presented, token):
            raise ServiceError(401, "unauthorized", "Missing or invalid bearer token.")

    def _guard_authoring(self):
        if not self.options.authoring_path:
            raise ServiceError(403, "authoring_disabled",
                               "Authoring is not enabled. Start with `unscripted studio`.")
        return self.options.authoring_path

    def _guard_debug(self, path: str) -> None:
        if path in DEBUG_ENDPOINTS and not self.options.expose_debug_endpoints:
            raise ServiceError(403, "debug_endpoints_disabled",
                               f"{path} is disabled in this deployment.")

    # ------------------------------------------------------------ dispatch ----
    # Public contract: handle_get/handle_post ALWAYS return either a JSON-safe body
    # or a (body, status) tuple -- they never raise for a caller mistake. Native
    # plugins that embed the service call these directly and should not have to
    # translate exceptions. The typed ServiceError is the internal mechanism.
    def handle_get(self, path: str, query: dict):
        try:
            return self._get(path, query)
        except ServiceError as exc:
            return exc.as_response()

    def handle_post(self, path: str, body: dict):
        try:
            return self._post(path, body)
        except ServiceError as exc:
            return exc.as_response()

    # ----------------------------------------------------------------- get ----
    #: Contract versions this service speaks. Version 1 is frozen: a shipped game
    #: keeps working, and nothing under the old paths ever changes name, type or
    #: meaning. Version 2 is additive and lives under /v2/.
    CONTRACT_VERSIONS = ("1.0.0", "2.0.0")
    DEFAULT_CONTRACT = "1.0.0"

    def capabilities(self) -> dict:
        """What this build can actually do, as opposed to what it can parse.

        Version and capability answer different questions. The version says which
        JSON shape is spoken; a capability says whether this runtime supports the
        feature at all. A build without an action bridge reports it, rather than
        returning an empty array that reads like "nothing happened".
        """
        return {
            "runtime_version": self.runtime.config.schema_version,
            "contract_versions": list(self.CONTRACT_VERSIONS),
            "default_contract": self.DEFAULT_CONTRACT,
            "capabilities": {
                "semantic_moves": True,
                "deception": True,
                "retrospective_revision": True,
                "knowledge_topology": True,
                "story_grouping": True,
                "judgements": True,
                # Configuration, not constants: a build with no engine attached
                # runs with the bridge off and must say so, because "no pending
                # intents" and "this build never issues any" look identical on
                # the wire and mean completely different things. The same holds
                # for every other optional layer, so all of them are reported
                # from the one place that knows -- an integrator writing a HUD
                # against a mechanic needs to know whether it is running.
                **self.runtime.layers(),
                # Configured *and* installed. A build that names a backend it
                # cannot run would have an integrator wiring up audio that never
                # arrives, which is worse than reporting no voice at all.
                "tts": self.runtime.voice_available(),
            },
        }

    def _get(self, path: str, query: dict):
        self._guard_debug(path)
        if path == "/capabilities":
            return self.capabilities()
        if path == "/v2/state/knowledge":
            return {**self.runtime.structured_knowledge(),
                    "contract_version": "2.0.0"}
        if path == "/v2/state/export":
            # NOT debug-gated, deliberately, and the distinction is worth stating
            # rather than assuming. The debug gate exists to stop a build that
            # ships to players from putting another character's private beliefs
            # ON THE SCREEN. Saving is the other thing: these bytes go into the
            # game's own save file, never to a display, and a shipping build that
            # could not call this could not save the world at all -- which would
            # make the whole runtime unshippable. The bearer token still applies.
            return {**self.runtime.export_state(), "contract_version": "2.0.0"}
        if path == "/v2/promises":
            # Open and recently settled. Not debug-gated: what a character has
            # undertaken to the player is something the player was told, so a
            # quest log may read it.
            return {**self.runtime.promises_report(), "contract_version": "2.0.0"}
        if path == "/v2/state/public":
            # Deliberately NOT a debug endpoint. Everything here is by definition
            # not private: a fact established in front of a crowd, and a note
            # somebody left lying in a room a player can walk into. A shipping
            # build may read this; `/v2/state/knowledge` it may not.
            place = query.get("place")
            if isinstance(place, list):
                place = place[0] if place else None
            return {"common_knowledge": self.runtime.public_knowledge(),
                    "notes": (self.runtime.notes_at(place) if place else
                              self.runtime.core.notes.report()),
                    "contract_version": "2.0.0"}
        if path == "/v2/state/character":
            # DELIBERATELY NOT A DEBUG ENDPOINT, and deliberately narrow.
            #
            # `/state/agent` carries beliefs, secrets and reason traces, which is
            # why it is gated: a shipping build that served it would let a player
            # datamine the answers. But *how this character feels about me* is
            # not debug output -- it is what a portrait, a greeting, a
            # relationship screen and a companion's face are made of, and until
            # now a shipped game could not read it at all.
            #
            # So this returns exactly the shippable part: who they are, where
            # they are, their mood and face, and their regard for the player.
            # Nothing about what they know, and nothing about anybody else.
            who = query.get("id")
            if isinstance(who, list):
                who = who[0] if who else None
            if not who or who not in self.runtime.world.agents:
                raise ServiceError(404, "no_such_character",
                                   "Give ?id= the id of a character in this world.")
            full = self.runtime.structured_agent(who)
            player = self.runtime.config.player_id
            return {"id": full["id"], "name": full["name"],
                    "location": full["location"],
                    "affect": full["affect"], "face": full["face"],
                    "regard": (full["relationships"].get(player)
                               or {"name": player, "trust": 0.0, "liking": 0.0,
                                   "familiarity": 0.0, "reputation": {}}),
                    "contract_version": "2.0.0"}
        if path == "/v2/actions/pending":
            return {"intents": self.runtime.pending_actions(),
                    "bridge": self.runtime.action_bridge_report(),
                    "contract_version": "2.0.0"}
        if path == "/v2/resting_on":
            source = (query.get("source") or [""])[0] if isinstance(
                query.get("source"), list) else query.get("source")
            if not source:
                raise ServiceError(400, "missing_source",
                                   "give ?source=<agent id> to ask what rests on it")
            return {"source": source, "beliefs": self.runtime.resting_on(source)}
        if path == "/health":
            return {"ok": True, "runtime_id": self.runtime.config.runtime_id,
                    "world_time": self.runtime.world.world_time,
                    "schema_version": self.runtime.config.schema_version}
        if path == "/bridges":
            return {"profiles": list_bridge_profiles()}
        if path == "/snapshots":
            return {"snapshots": self.runtime.list_snapshots()}
        if path == "/inspect/world":
            return {"text": self.runtime.inspect_world()}
        if path == "/inspect/agent":
            return {"text": self.runtime.inspect_agent(self._agent_id(query))}
        if path == "/avatar/face":
            return self.runtime.face_packet(self._agent_id(query),
                                            gaze_target=_first(query, "gaze_target"))
        if path == "/state/scene":
            return self.runtime.structured_scene()
        if path == "/state/world":
            return self.runtime.structured_world()
        if path == "/state/knowledge":
            return self.runtime.structured_knowledge()
        if path == "/authoring/pack":
            from .authoring import PackDocument, authoring_report, predicate_menu
            pack_path = self._guard_authoring()
            document = PackDocument.load(pack_path)
            return {
                "pack": document.as_dict(),
                "report": authoring_report(document),
                "predicates": predicate_menu((document.canon or {}).get("predicates")),
                # The editor offers relationships toward the player, and must not
                # assume what the player is called: a game that renames its player
                # would otherwise be edited against an id that does not exist.
                "player_id": self.runtime.config.player_id,
            }
        if path == "/state/agent":
            return self.runtime.structured_agent(self._agent_id(query))
        raise ServiceError(404, "unknown_endpoint", f"Unknown endpoint: {path}")

    # ---------------------------------------------------------------- post ----
    def _post(self, path: str, body: dict):
        self._guard_debug(path)
        if not isinstance(body, dict):
            raise ServiceError(400, "bad_body", "Request body must be a JSON object.")

        if path == "/turn":
            return self.runtime.submit_player_text(self._text(body)).as_dict()
        if path == "/v2/avatar/turn":
            return {**self.runtime.avatar_turn(self._text(body)),
                    "contract_version": "2.0.0"}
        if path == "/v2/discredit":
            source = (body or {}).get("source")
            if not source:
                raise ServiceError(400, "missing_source",
                                   "discrediting needs a source agent id")
            if source not in self.runtime.world.agents:
                raise ServiceError(404, "no_such_agent", f"no agent {source!r}")
            outcome = self.runtime.discredit(
                source, factor=float((body or {}).get("factor", 0.25)),
                reason=str((body or {}).get("reason") or "exposed"),
                predicate=(body or {}).get("predicate"))
            return {**outcome.as_dict(), "contract_version": "2.0.0"}
        if path.startswith("/v2/actions/") and path.endswith("/result"):
            return self._post_action_result(path, body)
        if path == "/avatar/turn":
            return self.runtime.avatar_turn(self._text(body))
        if path == "/event":
            return self._post_event(body)
        if path == "/advance":
            minutes = _require_int(body, "minutes", minimum=0,
                                   maximum=self.options.max_advance_minutes)
            return self.runtime.advance_time(minutes)
        if path == "/snapshot":
            label = _optional_str(body, "label", max_len=200)
            return self.runtime.create_snapshot(label).__dict__
        if path == "/restore":
            return self._post_restore(body)
        if path in ("/v2/state/import", "/v2/state/inspect"):
            return self._post_state(path, body)
        if path.startswith("/v2/promises/") and path.endswith("/settle"):
            return self._post_promise_settled(path, body)
        if path == "/generate/characters":
            return self._post_generate(body)
        if path == "/authoring/preview":
            return self._authoring_preview(body)
        if path == "/authoring/save":
            return self._authoring_save(body)
        raise ServiceError(404, "unknown_endpoint", f"Unknown endpoint: {path}")

    # ------------------------------------------------------------ handlers ----
    def _post_promise_settled(self, path: str, body: dict):
        """`POST /v2/promises/{id}/settle` -- the game says what became of it.

        The same division of labour as the action bridge: the runtime tracks what
        was undertaken, the engine knows whether it happened. A studio that
        scripts "the player hands over the money" should not have to hope an NPC
        was paying attention.
        """
        promise_id = path[len("/v2/promises/"):-len("/settle")]
        if not promise_id:
            raise ServiceError(400, "promise_id_required",
                               "Use POST /v2/promises/{promise_id}/settle.")
        if "kept" not in body or not isinstance(body["kept"], bool):
            raise ServiceError(400, "kept_required",
                               "Body must include 'kept': true or false.")
        try:
            reasons = self.runtime.settle_promise(
                promise_id, body["kept"],
                _require_str(body, "note", max_len=400, allow_empty=True))
        except KeyError:
            raise ServiceError(404, "unknown_promise",
                               f"No open promise with id {promise_id!r}. "
                               f"GET /v2/promises lists the open ones.") from None
        return {"promise_id": promise_id, "kept": body["kept"],
                "reasons": [{"code": c, "magnitude": m, "detail": d}
                            for c, m, d in reasons],
                "contract_version": "2.0.0"}

    def _post_state(self, path: str, body: dict):
        """`/v2/state/inspect` says what a load would do; `/v2/state/import` does it.

        Two endpoints rather than one with a flag, because a load screen asks the
        first question long before it commits to the second, and an inspect that
        might mutate the world would be useless for that.
        """
        from .snapshot import StateImportError
        blob = body.get("state")
        if not isinstance(blob, dict):
            raise ServiceError(400, "state_required",
                               "Send the blob from GET /v2/state/export as "
                               "{\"state\": {...}}.")
        if path == "/v2/state/inspect":
            return {**self.runtime.inspect_state(blob), "contract_version": "2.0.0"}
        try:
            report = self.runtime.import_state(blob)
        except StateImportError as exc:
            # 409 rather than 400: the request is well formed, and what it
            # conflicts with is the world currently loaded. A client tells those
            # apart to decide between "you sent nonsense" and "wrong save".
            raise ServiceError(409, "state_not_usable", str(exc)) from exc
        return {**report, "contract_version": "2.0.0"}

    def _post_action_result(self, path: str, body: dict):
        """`POST /v2/actions/{intent_id}/result` -- what the engine did with it.

        The id is in the path rather than the body because it identifies the
        thing being closed, and a mistyped one must be a 404 on a URL rather than
        a silently ignored field.
        """
        from .actionbridge import ENGINE_RESULTS, InvalidResult, UnknownIntent
        intent_id = path[len("/v2/actions/"):-len("/result")]
        if not intent_id:
            raise ServiceError(400, "missing_intent", "no intent id in the path")
        status = (body or {}).get("status")
        if not status:
            raise ServiceError(400, "missing_status",
                               "give status: one of " + ", ".join(ENGINE_RESULTS))
        try:
            outcome = self.runtime.report_action_result(
                intent_id, status, str((body or {}).get("detail") or ""))
        except InvalidResult as exc:
            raise ServiceError(400, "bad_status", str(exc)) from exc
        except UnknownIntent as exc:
            raise ServiceError(404, "no_such_intent", str(exc)) from exc
        return {**outcome, "contract_version": "2.0.0"}

    def _post_event(self, body: dict):
        payload = dict(body)
        payload.setdefault("event_id", self.runtime.world.new_event_id())
        if not isinstance(payload.get("type"), str) or not payload["type"].strip():
            raise ServiceError(400, "event_missing_type",
                               "Event requires a non-empty string 'type'.")
        if not isinstance(payload.get("payload", {}), dict):
            raise ServiceError(400, "event_bad_payload", "Event 'payload' must be an object.")
        world_time = payload.get("world_time", self.runtime.world.world_time)
        if not _is_int(world_time) or world_time < self.runtime.world.world_time:
            raise ServiceError(400, "event_time_not_monotonic",
                               f"Event 'world_time' must be an integer >= the current world "
                               f"time ({self.runtime.world.world_time}); world time never "
                               f"runs backwards.")
        try:
            event = bridge_event_to_world_event(
                payload, default_world_time=self.runtime.world.world_time)
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError(400, "event_bad_shape", f"Malformed event: {exc}") from exc
        return self.runtime.emit_event(event).__dict__

    def _post_restore(self, body: dict):
        snapshot_id = _require_str(body, "snapshot_id", max_len=128)
        try:
            reasons = self.runtime.restore_snapshot(snapshot_id)
        except KeyError as exc:
            raise ServiceError(404, "unknown_snapshot", f"Unknown snapshot id: {snapshot_id}") from exc
        return {"ok": True,
                "notes": [{"code": code, "magnitude": mag, "detail": detail}
                          for code, mag, detail in reasons]}

    def _post_generate(self, body: dict):
        count = _require_int(body, "count", default=1, minimum=1,
                             maximum=self.options.max_generated_characters)
        try:
            request = CharacterGenerationRequest.from_dict(
                {"player_id": self.runtime.config.player_id, **body, "count": count})
        except (TypeError, ValueError) as exc:
            raise ServiceError(400, "bad_generation_request", str(exc)) from exc
        return generate_characters(_world_data(self.runtime), request).as_dict()

    # ----------------------------------------------------------- authoring ----
    def _document_from(self, body: dict):
        """Rebuild a PackDocument from an editor payload, without touching disk."""
        from .authoring import PackDocument
        pack_path = self._guard_authoring()
        data = body.get("pack")
        if not isinstance(data, dict):
            raise ServiceError(400, "pack_required", "Body needs a 'pack' object.")
        characters = data.get("characters") or {}
        if not isinstance(characters, dict):
            raise ServiceError(400, "bad_characters", "'characters' must be a filename->object map.")
        for filename in characters:
            # The one place the runtime writes files. A character filename arrives
            # from a browser, so it is treated as hostile: no separators, no
            # traversal, nothing but a plain .json name inside this pack.
            if (os.path.basename(filename) != filename or not filename.endswith(".json")
                    or filename.startswith(".")):
                raise ServiceError(400, "bad_filename",
                                   f"Character filename {filename!r} must be a plain *.json name.")
        return PackDocument(
            path=pack_path,
            world=data.get("world") or {}, scenario=data.get("scenario") or {},
            canon=data.get("canon") or {}, topics=data.get("topics") or {"topics": []},
            initial_state=data.get("initial_state") or {"beliefs": []},
            characters=characters)

    def _authoring_preview(self, body: dict):
        """Report on an edit that has not been saved. Nothing is written."""
        from .authoring import authoring_report
        document = self._document_from(body)
        return {"report": authoring_report(document)}

    def _authoring_save(self, body: dict):
        """Write the pack, then say whether it validates and whether it is playable."""
        from .authoring import authoring_report
        from .pack import validate_world_pack
        document = self._document_from(body)
        written = document.save()
        validation = validate_world_pack(document.path)
        return {
            "saved": [os.path.basename(p) for p in written],
            "valid": validation.ok,
            "issues": [{"severity": i.severity, "code": i.code,
                        "message": i.message, "path": i.path} for i in validation.issues],
            "report": authoring_report(document),
        }

    # ------------------------------------------------------------- helpers ----
    def _text(self, body: dict) -> str:
        # A MISSPELLED FIELD USED TO BE A 200. `{"txt": "look"}` and `{}` both
        # ran an empty turn and answered OK, so an integrator with a typo got a
        # world that quietly did nothing and no clue where to look. An empty
        # `text` is still allowed -- an empty turn is a real thing a client may
        # want -- but the key has to be there, and anything else in the body that
        # nearly spells it is named back.
        if "text" not in body:
            near = [key for key in body
                    if key.lower().replace("_", "") in ("txt", "message", "line",
                                                        "input", "playertext",
                                                        "utterance", "say")]
            hint = f" Did you mean 'text' rather than {near[0]!r}?" if near else ""
            raise ServiceError(400, "text_required",
                               "Body must include 'text' (it may be an empty "
                               "string)." + hint)
        return _require_str(body, "text", max_len=self.options.max_text_chars, allow_empty=True)

    def _agent_id(self, query: dict) -> str:
        agent_id = _first(query, "agent_id")
        if not agent_id:
            raise ServiceError(400, "agent_id_required", "Query parameter 'agent_id' is required.")
        if agent_id not in self.runtime.world.agents:
            raise ServiceError(404, "unknown_agent", f"Unknown agent: {agent_id}")
        return agent_id


# ------------------------------------------------------------- validation ----

def _is_int(value) -> bool:
    # bool is an int subclass in Python; accepting True as 1 minute would be a bug.
    return isinstance(value, int) and not isinstance(value, bool)


def _require_str(body: dict, key: str, *, max_len: int, allow_empty: bool = False) -> str:
    value = body.get(key)
    if value is None and allow_empty:
        return ""
    if not isinstance(value, str):
        raise ServiceError(400, f"{key}_required", f"'{key}' must be a string.")
    if not value.strip() and not allow_empty:
        raise ServiceError(400, f"{key}_required", f"'{key}' must not be empty.")
    if len(value) > max_len:
        raise ServiceError(413, f"{key}_too_long",
                           f"'{key}' exceeds {max_len} characters ({len(value)}).")
    return value


def _optional_str(body: dict, key: str, *, max_len: int) -> str | None:
    if body.get(key) is None:
        return None
    return _require_str(body, key, max_len=max_len)


def _require_int(body: dict, key: str, *, minimum: int, maximum: int, default=None) -> int:
    value = body.get(key, default)
    if value is None:
        raise ServiceError(400, f"{key}_required", f"'{key}' is required.")
    if not _is_int(value):
        raise ServiceError(400, f"{key}_not_an_integer",
                           f"'{key}' must be an integer, got {type(value).__name__}.")
    if value < minimum:
        raise ServiceError(400, f"{key}_out_of_range",
                           f"'{key}' must be >= {minimum}, got {value}.")
    if value > maximum:
        raise ServiceError(400, f"{key}_out_of_range",
                           f"'{key}' must be <= {maximum}, got {value}.")
    return value


def _first(query, key):
    values = query.get(key) or []
    return values[0] if values else None


def _world_data(runtime: UnscriptedRuntime):
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


# ------------------------------------------------------------------ server ----

def create_server(config: RuntimeConfig | None = None, host: str = "127.0.0.1",
                  port: int = 8765, options: ServiceOptions | None = None,
                  runtime: UnscriptedRuntime | None = None):
    """Build a configured, *unstarted* HTTP server.

    Returns the server with ``unscripted_runtime``, ``unscripted_service`` and ``unscripted_warnings``
    attached, so the caller owns the lifecycle. :func:`run_service` is the simple
    blocking wrapper; tests and engine hosts that already have an event loop or a
    live runtime use this directly instead.
    """
    options = options or ServiceOptions()
    warnings = options.check_bind(host)   # raises before a socket is opened

    owns_runtime = runtime is None
    if runtime is None:
        if config is None:
            raise ValueError("create_server needs either a RuntimeConfig or a runtime.")
        runtime = UnscriptedRuntime.create(config)
    service = UnscriptedService(runtime, options)
    # one world == sequential turns; serialise all runtime access across the
    # threading server's workers so state and the SQLite store stay consistent.
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _authorize_page(self, parsed) -> bool:
            """A page that carries the token must not be handed to somebody who
            has not got it.

            `do_GET` served `/demo` and `/studio` outside `_dispatch`, so they
            never reached `authorize` -- while the HTML itself has the configured
            bearer token embedded in it, because the page has to call the API.
            An unauthenticated GET of the demo therefore RETURNED THE CREDENTIAL,
            and the same token then worked against every mutating endpoint.
            """
            try:
                service.authorize(self.headers.get("authorization"),
                                  query_token=_first(parse_qs(parsed.query), "token"))
                return True
            except ServiceError as exc:
                _write(self, exc.as_response(), options)
                return False

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/studio":
                if not self._authorize_page(parsed):
                    return
                if not options.authoring_path:
                    _write(self, ({"error": "Authoring is not enabled. Start with "
                                            "`unscripted studio`.",
                                   "code": "authoring_disabled"}, 403), options)
                    return
                _write_html(self, studio_html(options.auth_token))
                return
            if parsed.path in ("/", "/demo", "/index.html"):
                if not self._authorize_page(parsed):
                    return
                if not options.expose_debug_endpoints:
                    _write(self, ({"error": "Demo UI is disabled in this deployment.",
                                   "code": "demo_disabled"}, 403), options)
                    return
                _write_html(self, demo_html(options.auth_token))
                return
            self._dispatch(lambda: service.handle_get(parsed.path, parse_qs(parsed.query)))

        def do_POST(self):
            body = self._read_body()
            if body is _INVALID:
                return
            parsed = urlparse(self.path)
            self._dispatch(lambda: service.handle_post(parsed.path, body))

        def do_OPTIONS(self):
            # CORS preflight; only answered when an origin is explicitly allowed.
            _write(self, ({}, 204 if options.allow_origin else 405), options)

        def _dispatch(self, call):
            try:
                service.authorize(self.headers.get("authorization"))
                with lock:
                    result = call()   # handle_* already maps client errors to 4xx
            except ServiceError as exc:
                result = exc.as_response()
            except Exception as exc:   # never drop the connection silently
                result = ({"error": f"{type(exc).__name__}: {exc}",
                           "code": "internal_error"}, 500)
            _write(self, result, options)

        def _read_body(self):
            raw_length = self.headers.get("content-length")
            if raw_length is None:
                return {}
            try:
                length = int(raw_length)
            except ValueError:
                _write(self, ({"error": "Malformed Content-Length.",
                               "code": "bad_content_length"}, 400), options)
                return _INVALID
            if length < 0 or length > options.max_body_bytes:
                # reject on the header, before reading anything into memory
                _write(self, ({"error": f"Request body exceeds "
                                        f"{options.max_body_bytes} bytes.",
                               "code": "payload_too_large"}, 413), options)
                return _INVALID
            try:
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                return json.loads(raw)
            except UnicodeDecodeError:
                _write(self, ({"error": "Request body must be UTF-8.",
                               "code": "bad_encoding"}, 400), options)
            except json.JSONDecodeError as exc:
                _write(self, ({"error": f"Malformed JSON: {exc}",
                               "code": "bad_json"}, 400), options)
            return _INVALID

        def log_message(self, fmt, *args):
            return

    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError:
        if owns_runtime:
            runtime.close()
        raise
    server.unscripted_runtime = runtime
    server.unscripted_service = service
    server.unscripted_options = options
    server.unscripted_warnings = warnings
    server.unscripted_owns_runtime = owns_runtime
    return server


def announce(path: str, host: str, port: int, token: str | None) -> None:
    """Tell whoever launched us where we ended up, once, atomically.

    A game cannot hard-code a port. Two copies of the same game, a dev server
    already on 8765, a player with something else on that port -- all ordinary,
    and all fatal to a fixed number. So the launcher passes `--port 0`, the OS
    picks, and this is how the number gets back.

    Written to a temporary file and renamed, because a launcher polling for this
    file must never read half of it. `rename` within a directory is atomic on
    every platform this runs on, so the file either does not exist or is
    complete -- there is no third state for the poller to trip over.
    """
    payload = json.dumps({"url": f"http://{host}:{port}", "host": host,
                          "port": port, "token": token or "",
                          "pid": os.getpid(),
                          "runtime_version": RUNTIME_VERSION}, indent=1)
    temporary = f"{path}.{os.getpid()}.partial"
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _stop_cleanly_on_signals(server) -> None:
    """Turn a termination signal into an orderly shutdown.

    Only installed in `run_service`, which owns the process. A host embedding
    `create_server` in its own loop keeps its own signal handling, because
    stealing SIGTERM from an application that has its own is a rude thing for a
    library to do.
    """
    import signal

    def stop(signum, _frame):
        print(f"signal {signum}; shutting down", flush=True)
        # shutdown() must not run on the serving thread, and a handler runs on
        # the main one, which IS the serving thread here -- so hand it off.
        threading.Thread(target=server.shutdown, daemon=True).start()

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        handler = getattr(signal, name, None)
        if handler is None:
            continue    # SIGHUP does not exist on Windows
        try:
            signal.signal(handler, stop)
        except (ValueError, OSError):
            pass        # not on the main thread, or not permitted: not fatal


def _exit_with_parent(parent_pid: int, server) -> None:
    """Shut down when whoever launched us is gone.

    Without this, a game that crashes -- and games crash -- leaves a service
    holding a port and a save. The next launch then finds the port taken by a
    process nobody remembers starting, and a developer spends an afternoon on
    it. Polling rather than signals because it has to behave the same on Windows,
    where there is no SIGCHLD to inherit and no process group to die with.
    """
    def watch():
        while True:
            time.sleep(2.0)
            try:
                os.kill(parent_pid, 0)
            except OSError:
                print(f"parent process {parent_pid} is gone; shutting down",
                      flush=True)
                server.shutdown()
                return
    thread = threading.Thread(target=watch, name="unscripted-parent-watch", daemon=True)
    thread.start()


def run_service(config: RuntimeConfig, host: str = "127.0.0.1", port: int = 8765,
                options: ServiceOptions | None = None,
                announce_path: str | None = None,
                parent_pid: int | None = None):
    """Build and serve, blocking until interrupted.

    `announce_path` and `parent_pid` are what make this embeddable in a game:
    together with `--port 0` they turn "the developer remembers to start a
    server" into "the game launches a child process and is told where it is".
    """
    server = create_server(config, host=host, port=port, options=options)
    bound_host, bound_port = server.server_address[:2]
    try:
        print(f"Unscripted service listening on http://{bound_host}:{bound_port}", flush=True)
        # Announced only after the socket is bound and listening, so a launcher
        # that sees the file can connect immediately rather than racing us.
        if announce_path:
            announce(announce_path, bound_host, bound_port,
                     server.unscripted_options.auth_token)
            print(f"  announced to {announce_path}", flush=True)
        if parent_pid:
            _exit_with_parent(int(parent_pid), server)
            print(f"  will exit when process {parent_pid} does", flush=True)
        # A GAME STOPS ITS CHILD WITH SIGTERM, and the default handler for that
        # ends the process without unwinding -- so the `finally` below never ran
        # in the one case it exists for, and the announce file was left pointing
        # at a dead port. The next launch would then read it, connect to nothing,
        # and report a mystery. Handled here rather than documented as a caveat.
        _stop_cleanly_on_signals(server)
        if server.unscripted_options.auth_token:
            print("  auth: bearer token required", flush=True)
        if not server.unscripted_options.expose_debug_endpoints:
            print("  state-inspection endpoints and demo UI: disabled", flush=True)
        for warning in server.unscripted_warnings:
            print(f"  WARNING: {warning}", flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        if server.unscripted_owns_runtime:
            server.unscripted_runtime.close()
        # Leaving it behind would tell the next launcher to connect to a port
        # nothing is listening on, which is a worse failure than no file at all.
        if announce_path:
            try:
                os.remove(announce_path)
            except OSError:
                pass


_INVALID = object()   # sentinel: a response was already written for this request


def _write_html(handler, html: str):
    data = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("content-type", "text/html; charset=utf-8")
    handler.send_header("content-length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _write(handler, result, options: ServiceOptions):
    status = 200
    body = result
    if isinstance(result, tuple):
        body, status = result
    data = json.dumps(body, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(data)))
    if options.allow_origin:
        handler.send_header("access-control-allow-origin", options.allow_origin)
        handler.send_header("access-control-allow-headers", "content-type, authorization")
        handler.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
    handler.end_headers()
    if status != 204:
        handler.wfile.write(data)
