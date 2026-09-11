"""World snapshot capture and restore (spec v0.5 §8.5).

A snapshot is the complete *mutable* state needed to resume a session exactly:

- per-agent projections: belief (with provenance), memory (with presentation
  history), affect;
- per-agent cross-cutting owned state: relationships, reputation, identity
  salience and theory-of-mind models -- the social state a game actually needs
  back after a load;
- the scheduled timeline (pending scenario events) and the event-id watermark;
- director state: faction influence, resources, heat and progress clocks;
- runtime conversation state and the population-LOD decay watermarks.

It deliberately does NOT copy the append-only event ledger, the provider-call
log or reason traces. Those are audit streams: they live in their own tables,
grow monotonically, and embedding them made each snapshot O(session length) and
the snapshot table O(saves x session length). The snapshot records the event-id
watermark instead, so an audit tool reconstructs "the ledger as of this
snapshot" with one range query (`WHERE entry <= ledger_watermark`).

Capture and restore are pure functions over (world, runtime). Keeping them here
rather than in the Store means the persistence layer stores an opaque blob and
the round-trip is testable without a database.
"""
from __future__ import annotations

from .affect import AffectState
from .contracts import DEFAULT_PLAYER_ID
from .belief import Belief
from .dialogue import ConversationState
from .events import Event
from .factions import Faction, ProgressClock
from .memory import Memory

# Bump when the snapshot JSON shape changes incompatibly; restore reports a
# mismatch as a reason entry rather than crashing.
#   1 -> initial shape
#   2 -> added conversations
#   3 -> added relationships/reputation/identity salience/theory-of-mind and
#        director state; dropped the embedded ledger/provider/trace copies
# 7: when each character last acted on a goal.
# 10: how threatened each character's belongings feel. A load that dropped it
#     would calm a district that had just watched one of its own attacked.
# 9: open and settled promises. A load that dropped them would forgive every
#    undertaking a player had not yet honoured.
# 8: what is common knowledge and in front of whom, and what is lying unread in
#    each place. A load that dropped it would
#    hand a character back a secret the town had already watched come out.
# 6: per-place climate. A load that dropped it would quietly undo what a player
# did to a room.
# 5: pending action intents. A save taken mid-act has to remember what the engine
# still owes an answer for, or a load silently drops a character's errand.
#: 11: the belief arithmetic ledger and its source bound, the standing ledger,
#: judgement provenance, the map and world id a loader checks, and a ledger
#: watermark that survives branching. Older saves still load -- every new field
#: has a documented fallback -- and a save from a newer build is still refused.
SNAPSHOT_SCHEMA_VERSION = 11


# ---------------------------------------------------------------- capture ----

def capture(world, core) -> dict:
    """Serialise everything needed to resume this session into a JSON-safe dict."""
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "global_seed": world.global_seed,
        "world_time": world.world_time,
        "next_event_id": world._next_event_id,
        # watermark instead of a ledger copy: the ledger is an append-only audit
        # stream in its own table, not part of resumable state.
        # The ledger's own high-water mark, which a reload cannot rewind.
        #
        # This replaces `event_id_watermark`, which marked a point in the
        # SIMULATION and was read as though it marked one in the audit stream.
        # Event ids are minted by the simulation and `restore` rewinds the
        # counter, so after a reload the abandoned branch and the new one share
        # them: the history "as of snapshot A" answered A, and later A and B.
        # `Store.ledger_up_to` went with it -- an API whose contract could not be
        # met is worse than one that does not exist.
        "ledger_watermark": (core.store.ledger_position()
                             if getattr(core, "store", None) is not None else 0),
        "scenario_events": [_event_state(e) for e in world.scenario_events],
        "agents": {aid: _agent_state(a) for aid, a in world.agents.items()},
        "factions": {fid: f.as_dict() for fid, f in core.director.factions.items()},
        "conversations": {cid: c.as_dict() for cid, c in core.conversations.items()},
        "last_decay": dict(core._last_decay),
        # What the engine has been asked to do and has not answered. Restoring
        # without it would leave the runtime waiting on intents no engine knows
        # about, and the characters holding them frozen until they time out.
        "actions_out": core.actions_out.as_dict(),
        "climate": core.climate.as_dict(),
        "pursuit": core.pursuit.as_dict(),
        "common_knowledge": core.common_knowledge.as_dict(),
        "notes": core.notes.as_dict(),
        "promises": core.promises.as_dict(),
    }


def _event_state(e: Event) -> dict:
    return {"event_id": e.event_id, "world_time": e.world_time, "type": e.type,
            "actor": e.actor, "location": e.location, "payload": e.payload,
            "canonical": e.canonical}


def _agent_state(agent) -> dict:
    return {
        "location": agent.location,
        "beliefs": [b.as_dict() for b in agent.beliefs.values()],
        "memory": [m.as_dict() for m in agent.memory],
        "affect": agent.affect.as_dict() if agent.affect else None,
        # cross-cutting owned state (Part C) -- the social consequences a player
        # produced. Losing this on load is losing the game's whole social layer.
        "relationships": {other: dict(vec) for other, vec in agent.relationships.items()},
        "reputation": {subject: dict(dims) for subject, dims in agent.reputation.items()},
        "identity_threat": dict(agent.identity_threat),
        "identity_salience": dict(agent.identity_salience),
        # A day's intake. Losing it on load hands everyone a fresh, empty day and
        # a reloaded save absorbs information the same session would have refused.
        "attention_day": agent.attention_day,
        "attention_spent": agent.attention_spent,
        # How far each believed act has already moved this character's standing
        # towards whoever did it. Without it a reload re-applies every judgement
        # the save had already paid out.
        "standing_applied": dict(agent.standing_applied),
        # tom_models is keyed by a (other, proposition_key) tuple, which JSON cannot
        # express as an object key -- store it as an explicit triple list.
        "tom_models": [{"other": other, "proposition": prop_key, "model": dict(model)}
                       for (other, prop_key), model in agent.tom_models.items()],
    }


# ---------------------------------------------------------------- restore ----

def restore(data: dict, world, core) -> list:
    """Apply a captured snapshot to a live world + runtime.

    Returns reason entries describing anything the caller should know about
    (schema mismatch, seed mismatch, agents present in one side but not the
    other). Unknown agents are skipped rather than fabricated: a snapshot must
    never invent world content that the loaded world pack does not define.
    """
    reasons = []

    version = data.get("snapshot_schema_version", 1)
    if version != SNAPSHOT_SCHEMA_VERSION:
        reasons.append(("snapshot.version_mismatch", float(version),
                        {"found": version, "expected": SNAPSHOT_SCHEMA_VERSION,
                         "note": "restored on a best-effort basis"}))

    seed = data.get("global_seed")
    if seed is not None and seed != world.global_seed:
        # Determinism is seed-derived; restoring across seeds silently changes
        # every future stochastic draw, so surface it loudly.
        reasons.append(("snapshot.seed_mismatch", 0.0,
                        {"snapshot": seed, "world": world.global_seed}))

    world.world_time = data["world_time"]
    world._next_event_id = data.get("next_event_id", world._next_event_id)
    world.scenario_events = [
        Event(e["event_id"], e["world_time"], e["type"], e.get("actor"),
              e.get("location"), e.get("payload", {}), e.get("canonical", True))
        for e in data.get("scenario_events", [])
    ]

    agents_data = data.get("agents", {})
    for agent_id, state in agents_data.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            reasons.append(("snapshot.unknown_agent", 0.0,
                            {"agent": agent_id, "note": "not in the loaded world pack"}))
            continue
        _apply_agent_state(agent, state, places=set(world.places), reasons=reasons)

    missing = sorted(set(world.agents) - set(agents_data))
    if missing:
        # Agents the world pack defines but the snapshot never saw (e.g. the pack
        # gained characters since the save). They keep their authored start state.
        reasons.append(("snapshot.agent_not_in_snapshot", float(len(missing)),
                        {"agents": missing}))

    _apply_director_state(core, data.get("factions", {}), reasons)

    core.conversations = {cid: ConversationState.from_dict(c)
                          for cid, c in data.get("conversations", {}).items()}

    # LOD decay watermarks: fall back to the snapshot's world time for any agent
    # the snapshot did not carry, so nothing is decayed twice or skipped.
    last_decay = data.get("last_decay") or {}
    core._last_decay = {aid: last_decay.get(aid, data["world_time"]) for aid in world.agents}

    if "actions_out" in data:
        from .actionbridge import ActionBridge
        core.actions_out = ActionBridge.from_dict(data["actions_out"])
    if "climate" in data:
        core.climate.restore(data["climate"])
    if "pursuit" in data:
        core.pursuit.restore(data["pursuit"])
    if "common_knowledge" in data:
        core.common_knowledge.restore(data["common_knowledge"])
    if "notes" in data:
        core.notes.restore(data["notes"])
    if "promises" in data:
        core.promises.restore(data["promises"])

    # Per-turn debug traces describe the turn that produced them, not the restored
    # state; keeping them would attach stale explanations to a rewound world.
    core.last_traces = {}
    if reasons:
        core.last_traces["_snapshot"] = list(reasons)
    return reasons


def _apply_agent_state(agent, state: dict, *, places=None, reasons=None) -> None:
    if "location" in state:
        where = state["location"]
        if places is not None and where is not None and where not in places:
            # A place this world does not have. Leaving the character standing in
            # it makes every later query about the room they are in answer with a
            # room that is not there, so they keep where the pack put them and the
            # loss is reported rather than discovered later.
            if reasons is not None:
                reasons.append(("snapshot.unknown_place", 0.0, {
                    "agent": agent.id, "place": where,
                    "kept": agent.location,
                    "note": "not in the loaded world pack; the authored "
                            "location was kept"}))
        else:
            agent.location = where

    agent.beliefs = {}
    for bdata in state.get("beliefs", []):
        belief = Belief.from_dict(bdata)
        agent.beliefs[belief.proposition.core_key()] = belief

    agent.memory = [Memory.from_dict(m, owner=agent.id) for m in state.get("memory", [])]

    adata = state.get("affect")
    if adata:
        agent.affect = AffectState.from_dict(adata)

    agent.relationships = {other: dict(vec)
                           for other, vec in (state.get("relationships") or {}).items()}
    agent.identity_threat = {str(k): float(v) for k, v in
                            (state.get("identity_threat") or {}).items()}
    agent.reputation = {subject: dict(dims)
                        for subject, dims in (state.get("reputation") or {}).items()}
    agent.identity_salience = dict(state.get("identity_salience") or {})
    agent.attention_day = int(state.get("attention_day", -1))
    agent.attention_spent = int(state.get("attention_spent", 0))
    agent.standing_applied = {str(k): float(v) for k, v in
                              (state.get("standing_applied") or {}).items()}
    agent.tom_models = {(entry["other"], entry["proposition"]): dict(entry["model"])
                        for entry in (state.get("tom_models") or [])}


def _apply_director_state(core, factions_data: dict, reasons: list) -> None:
    for faction_id, fdata in factions_data.items():
        faction = core.director.factions.get(faction_id)
        if faction is None:
            # The snapshot knows a faction the loaded pack does not define. Restore
            # it so heat/clock history is not silently dropped, and say so.
            core.director.add_faction(Faction.from_dict(fdata))
            reasons.append(("snapshot.unknown_faction", 0.0, {"faction": faction_id}))
            continue
        faction.influence = fdata.get("influence", faction.influence)
        faction.resources = fdata.get("resources", faction.resources)
        faction.heat = fdata.get("heat", 0.0)
        if "territory" in fdata:
            faction.territory = list(fdata["territory"])
        if "goals" in fdata:
            faction.goals = list(fdata["goals"])
        faction.clocks = {name: ProgressClock.from_dict(clock)
                          for name, clock in (fdata.get("clocks") or {}).items()}


# ------------------------------------------------------- portable export ----
#
# `capture`/`restore` above are the runtime's internal round trip: they assume
# the same process, the same world pack, the same code. That is the right shape
# for `/snapshot` and `/restore`, which hand back an id and put it back.
#
# It is the wrong shape for the thing a game actually has to do, which is put the
# world INTO ITS OWN SAVE FILE. A game's save is a file the player owns, copies,
# syncs to a cloud and restores onto a different machine six months and two
# patches later. A snapshot id pointing into the runtime's own store cannot do
# that: it makes the runtime a second save file that has to be kept in step with
# the first, and the two will drift the first time somebody copies a save.
#
# So: one blob, out and in, with enough about itself that a load can tell what it
# is looking at. 142 kB raw and about 11 kB gzipped for eight characters, which
# is small enough to embed in any save format without anybody thinking about it.

#: Bumped when the ENVELOPE changes, which is separate from
#: `SNAPSHOT_SCHEMA_VERSION` (the state inside it). Two versions because they
#: move for different reasons and a loader wants to fail differently: an
#: unreadable envelope is "this is not our file", an unreadable payload is "this
#: save is from a newer build".
STATE_FORMAT = "unscripted-state"
#: What this marker used to be. A save written before the project was renamed is
#: still a valid save -- the envelope changed its name, not its shape -- so it is
#: accepted on read and rewritten under the current marker. Nothing writes this.
STATE_FORMAT_LEGACY = ("lwr-state",)
STATE_FORMAT_VERSION = 1


def _is_state_envelope(marker) -> bool:
    """Whether this `format` field names a state blob this build can open."""
    return marker == STATE_FORMAT or marker in STATE_FORMAT_LEGACY


def world_fingerprint(world) -> str:
    """A stable short hash of the world's SHAPE -- who and where, not what happened.

    Deliberately over the immutable cast and map rather than over the pack files:
    a studio reformats JSON, renames a directory or regenerates a pack, and none
    of that should invalidate a player's save. What must match is that the
    characters and places a save talks about are the ones this world has.
    """
    import hashlib
    material = "|".join((
        str(getattr(world, "global_seed", "")),
        ",".join(sorted(world.agents)),
        ",".join(sorted(world.places)),
        ",".join(sorted(getattr(world, "topics", None) or ())),
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def export_state(world, core) -> dict:
    """The whole mutable world as one JSON-safe blob a game can save itself.

    Everything a loader needs to decide whether it can use this is in the
    envelope, so it never has to parse the payload to find out.
    """
    from .contracts import RUNTIME_VERSION
    return {
        "format": STATE_FORMAT,
        "format_version": STATE_FORMAT_VERSION,
        # Informational: which build wrote it. NOT a compatibility gate -- the
        # schema version is that, and tying saves to a runtime version would
        # break every save on a patch that changed nothing about the state.
        "runtime_version": RUNTIME_VERSION,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "world_fingerprint": world_fingerprint(world),
        # The map, named. Agent overlap alone cannot tell "the same world,
        # patched" from "somebody else's game": every pack ships the same default
        # player id, so ANY two worlds overlapped by one agent and every save
        # loaded into every world. Places are what a save's positions and
        # routines refer to, so places are what has to be the same place.
        "places": sorted(world.places),
        # What the pack says this world IS. Empty when it has not said, and the
        # loader then falls back to the cast and the map.
        "world_id": getattr(world, "world_id", ""),
        # Named here as well as inside the payload so a loader can report what
        # would be dropped BEFORE committing to the import.
        "agents": sorted(world.agents),
        "world_time": world.world_time,
        "state": capture(world, core),
    }


class StateImportError(ValueError):
    """A blob that cannot be imported, with a reason a person can act on."""


def inspect_state(blob: dict, world) -> dict:
    """What would happen if this were imported, without importing it.

    The call a load screen makes: it can offer "continue" or "start over" on the
    strength of this, and never has to catch an exception to find out which.
    """
    if not isinstance(blob, dict) or not _is_state_envelope(blob.get("format")):
        return {"usable": False, "code": "not_a_state_blob",
                "detail": "missing the unscripted-state marker"}
    if int(blob.get("format_version", 0)) > STATE_FORMAT_VERSION:
        return {"usable": False, "code": "envelope_too_new",
                "detail": f"envelope v{blob.get('format_version')} against "
                          f"v{STATE_FORMAT_VERSION} here"}
    saved_schema = int(blob.get("snapshot_schema_version", 0))
    if saved_schema > SNAPSHOT_SCHEMA_VERSION:
        return {"usable": False, "code": "save_from_newer_build",
                "detail": f"state schema {saved_schema} against "
                          f"{SNAPSHOT_SCHEMA_VERSION} here"}

    saved_agents = set(blob.get("agents") or ())
    here = set(world.agents)
    known = saved_agents & here
    if saved_agents and not known:
        return {"usable": False, "code": "different_world",
                "detail": "not one character in this save exists in this world"}

    # WHICH WORLD IS THIS. A pack that says so is believed, and nothing else is
    # consulted: an id is an identity, and every other test here is a proxy for
    # one.
    saved_id = str(blob.get("world_id") or "")
    here_id = str(getattr(world, "world_id", "") or "")
    if saved_id and here_id and saved_id != here_id:
        return {"usable": False, "code": "different_world",
                "detail": f"this save belongs to {saved_id!r}, not {here_id!r}"}

    # A PACK THAT HAS NOT SAID leaves the loader comparing what it can see, and
    # the standard is overlap that could not be coincidence. ONE shared id always
    # is one somewhere: every pack ships `agent:player_1`, so a cyberpunk save
    # loaded cleanly into a noir harbour -- and two unrelated worlds that both
    # name a room `place:spawn` did it again once the map was added. So: a
    # character who is not the player, or more than one place.
    saved_places = set(blob.get("places") or ())
    shared_places = saved_places & set(world.places)
    shared_cast = set(known) - {DEFAULT_PLAYER_ID}
    unverified = not (saved_id and here_id)
    if unverified:
        # NO DECLARED IDENTITY, so the loader is guessing and says so. The bar is
        # a character who is not the player: place names are the part two
        # unrelated worlds are most likely to share by accident, and raising the
        # threshold from one shared place to two only moved the accident rather
        # than removing it. Every shipped pack declares an id now, so this is the
        # compatibility path for saves and packs written before it existed.
        if saved_places and not shared_places:
            return {"usable": False, "code": "different_world",
                    "detail": "not one place in this save exists in this world"}
        if not shared_cast and len(saved_agents) > 1:
            return {"usable": False, "code": "different_world",
                    "detail": "this save shares no character but the player with "
                              "this world, and neither side declares a `world_id`. "
                              "Declare one in scenario.json to say what a world is "
                              "rather than leaving it to be inferred"}

    # A PATCH IS NOT A CORRUPTION. A studio ships an update that adds an NPC or
    # retires one, and every existing save must keep working -- so a fingerprint
    # mismatch is reported and proceeded through rather than refused. What is
    # refused is a save with no overlap at all, which is somebody's other game.
    return {
        "usable": True,
        # `world_unverified` is not a warning about the cast -- it says the
        # identity was inferred rather than checked, which a loader may well want
        # to refuse on its own.
        "code": ("world_unverified" if unverified else
                 "ok" if blob.get("world_fingerprint") == world_fingerprint(world)
                 else "world_changed"),
        "detail": "",
        "saved_at_world_time": int(blob.get("world_time", 0)),
        "written_by": blob.get("runtime_version"),
        "restored": sorted(known),
        # Characters the save knows and this build does not: their state is
        # dropped, and saying so is the difference between a load that lost
        # something and a load that lost something quietly.
        "dropped": sorted(saved_agents - here),
        # Characters this build has that the save predates: they keep whatever
        # the world pack authored, which is the only defensible answer.
        "unsaved": sorted(here - saved_agents),
    }


def import_state(blob: dict, world, core) -> tuple:
    """Put a blob back. Returns `(report, reasons)`.

    Raises :class:`StateImportError` only for a blob that cannot be used at all;
    everything survivable is reported in `report` and applied.
    """
    report = inspect_state(blob, world)
    if not report["usable"]:
        raise StateImportError(f"{report['code']}: {report['detail']}")
    # ALL OF IT OR NONE OF IT. The envelope can be sound and the payload rotten:
    # a belief that will not parse used to raise half way through, AFTER the
    # world clock and the schedule had already been overwritten, leaving a live
    # session in a state that was neither the old one nor the new one. A load
    # that fails must leave the game exactly as it found it.
    rollback = capture(world, core)
    try:
        reasons = restore(blob.get("state") or {}, world, core)
    except Exception as exc:
        restore(rollback, world, core)
        raise StateImportError(
            f"invalid_payload: {type(exc).__name__}: {exc}") from exc
    if report["code"] == "world_changed":
        reasons.append(("state.world_changed", float(len(report["dropped"])), {
            "dropped": report["dropped"], "unsaved": report["unsaved"],
            "note": "the cast has changed since this save; it was loaded anyway "
                    "and the differences are listed"}))
    return report, reasons
