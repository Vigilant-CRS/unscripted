"""World-pack validation utilities for SDK users."""
from __future__ import annotations

import json
import os

from .contracts import ValidationReport
from .ontology import CORE_PREDICATES


REQUIRED_FILES = ("world.json", "scenario.json")


def _tuning_probe():
    """A bare runtime, only to ask what parameters each engine actually has.

    Built without a world so validating stays a pure function of the files: the
    alternative would be validating a pack against itself, which cannot catch a
    name the runtime does not have.
    """
    from .runtime import Runtime
    from .world import World
    return Runtime(World())


def _load_json(report: ValidationReport, path: str, rel: str) -> dict:
    fp = os.path.join(path, rel)
    if not os.path.exists(fp):
        report.add("error", "pack.missing_file", f"Missing required file: {rel}", rel)
        return {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        report.add("error", "pack.invalid_json", f"{rel}: {exc}", rel)
    return {}


def validate_world_pack(path: str) -> ValidationReport:
    report = ValidationReport(ok=True)
    if not os.path.isdir(path):
        report.add("error", "pack.not_directory", f"World pack path is not a directory: {path}", path)
        return report

    for rel in REQUIRED_FILES:
        if not os.path.exists(os.path.join(path, rel)):
            report.add("error", "pack.missing_file", f"Missing required file: {rel}", rel)

    world = _load_json(report, path, "world.json") if os.path.exists(os.path.join(path, "world.json")) else {}
    scenario = _load_json(report, path, "scenario.json") if os.path.exists(os.path.join(path, "scenario.json")) else {}
    canon = (_load_json(report, path, "canon.json")
             if os.path.exists(os.path.join(path, "canon.json")) else {})
    initial_state = (_load_json(report, path, "initial_state.json")
                     if os.path.exists(os.path.join(path, "initial_state.json")) else {})

    # A pack's own predicates are part of its schema: validation must know them
    # without mutating the process-wide registry (validating must have no side effects).
    known_predicates = _predicate_schema(report, canon)

    # SHAPE BEFORE CONTENT. The whole job of this function is to tell somebody
    # what is wrong with their pack, so it must not be the thing that crashes on
    # a malformed one -- and the commonest first mistake is a JSON array where a
    # mapping belongs, because that is how most other formats spell a list.
    # Before this, `"places": [...]` produced
    #     AttributeError: 'list' object has no attribute 'keys'
    # as a traceback out of the validator itself, which is the least helpful
    # thing a validator can do.
    # EVERY section, with the shape it expects. The first version of this check
    # listed three sections and left media_exposure out, so the next pack anybody
    # wrote crashed the validator again -- in a different place, with a different
    # traceback, for the same reason. A guard that covers some of the surface
    # teaches people that the validator is unreliable, which is worse than the
    # crash it prevents.
    SHAPES = {
        ("places", "world.json"): (dict, 'an object keyed by id: {"place:example": {...}}'),
        ("entities", "world.json"): (dict, 'an object keyed by id'),
        ("channels", "world.json"): (dict, 'an object keyed by id'),
        ("factions", "world.json"): (list, 'a list of faction objects'),
        ("media_exposure", "world.json"):
            (list, 'a LIST of {"agent": ..., "channel": ..., "attention": ...} '
                   'records -- not a mapping of agent to channels'),
        ("identity_values", "world.json"): (dict, 'an object keyed by identity id'),
        ("diffusion", "world.json"): (dict, 'an object of parameter names'),
        ("tuning", "world.json"): (dict, 'an object keyed by engine name'),
    }
    for (section, filename), (want, described) in SHAPES.items():
        value = world.get(section)
        if value is not None and not isinstance(value, want):
            report.add("error", "pack.wrong_shape",
                       f"{filename}: '{section}' must be {described}, not a "
                       f"{type(value).__name__}.", filename)
            world[section] = want()

    # A TUNING TYPO IS AN ERROR AT AUTHORING TIME, not a world that quietly
    # behaves as though nothing was set. Checked against the real engine
    # parameters, so `unscripted validate` catches it rather than the first playtest
    # where somebody wonders why the town is still so quiet.
    if world.get("tuning") is not None:
        from . import tuning as tuning_module
        try:
            tuning_module.check(world["tuning"], _tuning_probe())
        except tuning_module.TuningError as exc:
            report.add("error", "pack.bad_tuning", str(exc), "world.json")

    places = set((world.get("places") or {}).keys())
    if not places:
        report.add("error", "pack.no_places", "world.json must define at least one place.", "world.json")

    characters_dir = os.path.join(path, "characters")
    if not os.path.isdir(characters_dir):
        report.add("error", "pack.no_characters_dir", "World pack must include a characters directory.",
                   "characters")
        return report

    seen_agents = set()
    for fn in sorted(os.listdir(characters_dir)):
        if not fn.endswith(".json"):
            continue
        rel = os.path.join("characters", fn)
        data = _load_json(report, path, rel)
        agent_id = data.get("id")
        if not agent_id:
            report.add("error", "character.missing_id", "Character is missing id.", rel)
            continue
        for field in ("big_five", "relationships", "goals", "location"):
            if field not in data:
                report.add("warning", f"character.missing_{field}",
                           f"{agent_id} omits recommended production field {field}.", rel)
        if agent_id in seen_agents:
            report.add("error", "character.duplicate_id", f"Duplicate character id: {agent_id}", rel)
        seen_agents.add(agent_id)
        location = data.get("location")
        if location and location not in places:
            report.add("error", "character.bad_location",
                       f"{agent_id} references unknown location {location}", rel)
        for other_id in (data.get("relationships") or {}):
            if not isinstance(other_id, str):
                report.add("error", "character.bad_relationship",
                           f"{agent_id} has a non-string relationship key.", rel)
        for numeric in ("social_status", "resources"):
            if numeric in data and not _in_unit_interval(data[numeric]):
                report.add("error", f"character.bad_{numeric}",
                           f"{agent_id}.{numeric} must be in [0,1].", rel)

    if not seen_agents:
        report.add("error", "pack.no_characters", "World pack must define at least one character.",
                   "characters")

    for idx, event in enumerate(scenario.get("events") or []):
        epath = f"scenario.json#/events/{idx}"
        if "type" not in event:
            report.add("error", "scenario.event_missing_type", "Scenario event is missing type.", epath)
        loc = event.get("location")
        if loc and loc not in places:
            report.add("error", "scenario.bad_location", f"Event references unknown location {loc}", epath)
        payload = event.get("payload") or {}
        prop = payload.get("proposition")
        _validate_proposition(report, prop, epath, known_predicates)

    for idx, belief in enumerate(initial_state.get("beliefs") or []):
        bpath = f"initial_state.json#/beliefs/{idx}"
        agent = belief.get("agent")
        if agent not in seen_agents:
            report.add("error", "initial_state.unknown_agent",
                       f"Initial belief references unknown agent {agent}.", bpath)
        _validate_proposition(report, belief.get("proposition"), bpath, known_predicates)
        if "origin_event" not in belief:
            report.add("error", "initial_state.missing_origin",
                       "Initial belief must include origin_event for provenance.", bpath)
        for numeric in ("trust", "competence", "importance"):
            if numeric in belief and not _in_unit_interval(belief[numeric]):
                report.add("error", f"initial_state.bad_{numeric}",
                           f"{numeric} must be in [0,1].", bpath)

    _validate_routines(report, path, scenario, places)
    _validate_topology(report, world, places)
    topics = _validate_topics(report, path, places, known_predicates)
    _validate_secrets(report, path, seen_agents, topics, known_predicates)
    _validate_vocabulary(report, world, path, places, seen_agents, topics)

    for focus in scenario.get("focus_agents") or []:
        if focus not in seen_agents:
            report.add("error", "scenario.unknown_focus_agent",
                       f"focus_agents references unknown agent {focus}.", "scenario.json")

    for exposure in world.get("media_exposure") or []:
        agent = exposure.get("agent")
        channel = exposure.get("channel")
        if agent and agent not in seen_agents:
            report.add("warning", "media.unknown_agent",
                       f"Media exposure references unknown agent {agent}.", "world.json")
        if channel and channel not in (world.get("channels") or {}):
            report.add("error", "media.unknown_channel",
                       f"Media exposure references unknown channel {channel}.", "world.json")

    return report


def _validate_routines(report: ValidationReport, path: str, scenario: dict, places: set):
    """Daily schedules: parseable, inside the world, and consistent with the
    opening scene.

    The last one matters most. A character may declare both a starting `location`
    and a `routine`; if they disagree at the scenario's start time, the pack
    contradicts itself and the session begins somewhere the author did not write.
    That is not hypothetical -- it happened the moment routines were introduced,
    and it silently moved a character out of the reference scene.
    """
    from .routine import MINUTES_PER_DAY, Routine, parse_clock

    characters_dir = os.path.join(path, "characters")
    if not os.path.isdir(characters_dir):
        return
    start_minute = int(scenario.get("world_time", 0)) % MINUTES_PER_DAY
    with_routines = 0
    schedules = {}

    for fn in sorted(os.listdir(characters_dir)):
        if not fn.endswith(".json"):
            continue
        rel = os.path.join("characters", fn)
        data = _load_json(report, path, rel)
        agent_id = data.get("id", fn)
        entries = data.get("routine")
        if not entries:
            continue
        with_routines += 1
        seen_starts = set()
        blocks = []
        for idx, entry in enumerate(entries):
            rpath = f"{rel}#/routine/{idx}"
            if "from" not in entry or "place" not in entry:
                report.add("error", "routine.bad_block",
                           f"{agent_id} routine block needs 'from' and 'place'.", rpath)
                continue
            try:
                minute = parse_clock(entry["from"])
            except ValueError as exc:
                report.add("error", "routine.bad_time", f"{agent_id}: {exc}", rpath)
                continue
            if minute in seen_starts:
                report.add("error", "routine.duplicate_time",
                           f"{agent_id} has two blocks starting at {entry['from']}.", rpath)
            seen_starts.add(minute)
            if entry["place"] not in places:
                report.add("error", "routine.unknown_place",
                           f"{agent_id} is scheduled into unknown place {entry['place']}.", rpath)
                continue
            blocks.append((minute, entry["place"], entry.get("activity", "")))

        if not blocks:
            continue
        schedules[agent_id] = Routine(blocks)
        authored = data.get("location")
        scheduled = schedules[agent_id].block_at(start_minute)
        if authored and scheduled and authored != scheduled[1]:
            clock = f"{start_minute // 60:02d}:{start_minute % 60:02d}"
            report.add("error", "routine.contradicts_start_location",
                       f"{agent_id} starts at {authored} but the routine puts them at "
                       f"{scheduled[1]} at {clock}; the pack disagrees with itself about "
                       f"where the scene opens.", rel)

    if with_routines and len(schedules) >= 2:
        occupancy = {}
        for minute in range(0, MINUTES_PER_DAY, 30):
            where = {}
            for agent_id, routine in schedules.items():
                block = routine.block_at(minute)
                if block:
                    where.setdefault(block[1], []).append(agent_id)
            for place, occupants in where.items():
                if len(occupants) >= 2:
                    occupancy.setdefault(place, set()).update(occupants)
        if not occupancy:
            report.add("warning", "routine.no_meetings",
                       "No two scheduled characters ever share a place over a full day, so "
                       "nothing can be told to anyone and rumour cannot spread.",
                       "characters")


def _validate_topology(report: ValidationReport, world: dict, places: set):
    """A pack must be navigable. Exits used to live in the SDK, so a pack could
    load and validate while being impossible to walk through."""
    reachable_targets = set()
    for place_id, attrs in (world.get("places") or {}).items():
        if not isinstance(attrs, dict):
            report.add("error", "place.bad_shape", f"{place_id} must be an object.", "world.json")
            continue
        if not attrs.get("label"):
            report.add("warning", "place.missing_label",
                       f"{place_id} has no label; the id will be shown to players.", "world.json")
        exits = attrs.get("exits")
        if exits is None:
            report.add("warning", "place.no_exits",
                       f"{place_id} declares no exits; players cannot walk out of it.",
                       "world.json")
            continue
        if not isinstance(exits, list):
            report.add("error", "place.bad_exits", f"{place_id}.exits must be a list.", "world.json")
            continue
        for target in exits:
            if target not in places:
                report.add("error", "place.unknown_exit",
                           f"{place_id} exits to unknown place {target}.", "world.json")
            elif target == place_id:
                report.add("warning", "place.self_exit",
                           f"{place_id} exits to itself.", "world.json")
            else:
                reachable_targets.add(target)
        formality = attrs.get("formality")
        if formality is not None and not _in_unit_interval(formality):
            report.add("error", "place.bad_formality",
                       f"{place_id}.formality must be in [0,1].", "world.json")

    orphans = sorted(places - reachable_targets)
    if orphans and len(places) > 1 and len(orphans) == len(places):
        report.add("error", "pack.no_topology",
                   "No place is reachable from any other; the pack has no topology.",
                   "world.json")
    elif len(orphans) > 1:
        report.add("warning", "place.unreachable",
                   f"No exit leads to: {', '.join(orphans)}.", "world.json")


def _validate_topics(report: ValidationReport, path: str, places: set,
                     known_predicates: dict) -> set:
    data = (_load_json(report, path, "topics.json")
            if os.path.exists(os.path.join(path, "topics.json")) else {})
    # topics.json is a LIST of objects with ids, unlike world.json's mappings.
    # An inconsistency worth guarding rather than harmonising: every shipped pack
    # and every pack anyone has authored uses the list, and changing the shape to
    # match world.json would break all of them to satisfy a symmetry nobody asked
    # for. What matters is that the wrong one says so.
    if data.get("topics") is not None and not isinstance(data["topics"], list):
        report.add("error", "pack.wrong_shape",
                   f"topics.json: 'topics' must be a list of topic objects, not "
                   f"a {type(data['topics']).__name__}. Write "
                   f"{{\"topics\": [{{\"id\": \"...\", ...}}]}}.", "topics.json")
        data = {}
    entries = data.get("topics") or []
    if not entries:
        report.add("warning", "pack.no_topics",
                   "No topics.json: players can address characters but ask about nothing.",
                   "topics.json")
    seen = set()
    for idx, topic in enumerate(entries):
        tpath = f"topics.json#/topics/{idx}"
        topic_id = topic.get("id")
        if not topic_id:
            report.add("error", "topic.missing_id", "Topic is missing id.", tpath)
            continue
        if topic_id in seen:
            report.add("error", "topic.duplicate_id", f"Duplicate topic id: {topic_id}", tpath)
        seen.add(topic_id)
        if not topic.get("aliases"):
            report.add("warning", "topic.no_aliases",
                       f"{topic_id} has no aliases; only its id will match player text.", tpath)
        for key in ("query", "player_claim", "player_assertion"):
            _validate_proposition(report, topic.get(key), f"{tpath}/{key}",
                                  known_predicates)
        if topic.get("query") and not topic.get("phrasings"):
            report.add("warning", "topic.no_phrasings",
                       f"{topic_id} is answerable but authors no phrasings; characters will "
                       f"deflect instead of answering (the engine asserts no facts of its own).",
                       tpath)
        for stance, variants in (topic.get("phrasings") or {}).items():
            if stance not in ("affirm", "deny"):
                report.add("error", "topic.bad_phrasing_stance",
                           f"{topic_id}.phrasings key must be 'affirm' or 'deny', got {stance}.",
                           tpath)
            elif not isinstance(variants, dict) or not variants:
                report.add("error", "topic.bad_phrasing",
                           f"{topic_id}.phrasings.{stance} must be a register->line object.", tpath)
        for ridx, reaction in enumerate(topic.get("reactions") or []):
            if not reaction.get("type"):
                report.add("error", "topic.reaction_missing_type",
                           f"{topic_id} reaction {ridx} is missing an event type.", tpath)
            loc = reaction.get("location")
            if loc and loc not in places:
                report.add("error", "topic.reaction_bad_location",
                           f"{topic_id} reaction {ridx} references unknown place {loc}.", tpath)
    return seen


def _validate_secrets(report: ValidationReport, path: str, agents: set, topics: set,
                      known_predicates: dict):
    """A secret without surface forms cannot be enforced against a text provider."""
    characters_dir = os.path.join(path, "characters")
    if not os.path.isdir(characters_dir):
        return
    for fn in sorted(os.listdir(characters_dir)):
        if not fn.endswith(".json"):
            continue
        rel = os.path.join("characters", fn)
        data = _load_json(report, path, rel)
        agent_id = data.get("id", fn)
        for idx, secret in enumerate(data.get("secrets") or []):
            spath = f"{rel}#/secrets/{idx}"
            if isinstance(secret, str):
                report.add("warning", "secret.unstructured",
                           f"{agent_id} declares secret {secret!r} as a bare string: it has no "
                           f"surface forms, so released text is not scanned for it, and no "
                           f"trust gate, so it changes no behaviour.", spath)
                continue
            if not secret.get("id"):
                report.add("error", "secret.missing_id", f"{agent_id} has a secret without id.", spath)
            if not secret.get("surface_forms"):
                report.add("warning", "secret.no_surface_forms",
                           f"{agent_id}/{secret.get('id')} declares no surface_forms; an external "
                           f"text provider phrasing it freely would not be caught.", spath)
            if not secret.get("protects"):
                report.add("warning", "secret.protects_nothing",
                           f"{agent_id}/{secret.get('id')} protects no proposition, so nothing is "
                           f"withheld from allowed_facts.", spath)
            for entry in secret.get("protects") or []:
                if isinstance(entry, dict):
                    _validate_proposition(report, entry, f"{spath}/protects",
                                          known_predicates)
            for guarded in secret.get("guards_topics") or []:
                if topics and guarded not in topics:
                    report.add("error", "secret.unknown_topic",
                               f"{agent_id}/{secret.get('id')} guards unknown topic {guarded}.",
                               spath)
            for subject in secret.get("about") or []:
                if subject not in agents:
                    report.add("warning", "secret.unknown_subject",
                               f"{agent_id}/{secret.get('id')} concerns unknown agent {subject}.",
                               spath)
            if "min_trust" in secret and not _in_unit_interval(secret["min_trust"]):
                report.add("error", "secret.bad_min_trust",
                           f"{agent_id}/{secret.get('id')}.min_trust must be in [0,1].", spath)


def _validate_vocabulary(report: ValidationReport, world: dict, path: str,
                         places: set, agents: set, topics: set):
    """Two things must never share an alias inside one category, or player text
    resolves to whichever happened to sort first."""
    from .content import AliasIndex

    place_aliases = {pid: (attrs.get("aliases") or []) if isinstance(attrs, dict) else []
                     for pid, attrs in (world.get("places") or {}).items()}
    for category, alias_map in (("place", place_aliases),):
        for alias, first, second in AliasIndex.build(alias_map).conflicts():
            report.add("error", f"{category}.alias_conflict",
                       f"Alias {alias!r} is claimed by both {first} and {second}.", "world.json")

    characters_dir = os.path.join(path, "characters")
    agent_aliases = {}
    if os.path.isdir(characters_dir):
        for fn in sorted(os.listdir(characters_dir)):
            if not fn.endswith(".json"):
                continue
            data = _load_json(report, path, os.path.join("characters", fn))
            if data.get("id"):
                agent_aliases[data["id"]] = (data.get("names") or {}).get("aliases") or []
    for alias, first, second in AliasIndex.build(agent_aliases).conflicts():
        report.add("error", "character.alias_conflict",
                   f"Alias {alias!r} is claimed by both {first} and {second}.", "characters")

    topics_data = (_load_json(report, path, "topics.json")
                   if os.path.exists(os.path.join(path, "topics.json")) else {})
    topic_aliases = {t["id"]: (t.get("aliases") or [])
                     for t in (topics_data.get("topics") or []) if t.get("id")}
    for alias, first, second in AliasIndex.build(topic_aliases).conflicts():
        report.add("error", "topic.alias_conflict",
                   f"Alias {alias!r} is claimed by both {first} and {second}.", "topics.json")


def _in_unit_interval(value) -> bool:
    return isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0


def _predicate_schema(report: ValidationReport, canon: dict) -> dict:
    """Engine core predicates plus the ones this pack declares in canon.json."""
    schema = dict(CORE_PREDICATES)
    for name, spec in (canon.get("predicates") or {}).items():
        cpath = f"canon.json#/predicates/{name}"
        if not isinstance(spec, dict) or not spec.get("slots"):
            report.add("error", "predicate.no_slots",
                       f"Predicate {name} must declare a non-empty 'slots' list.", cpath)
            continue
        if name in CORE_PREDICATES and spec.get("slots") != CORE_PREDICATES[name]["slots"]:
            report.add("error", "predicate.conflicts_with_core",
                       f"Predicate {name} redefines an engine core predicate with different "
                       f"slots; slot order defines the canonical proposition key.", cpath)
            continue
        functional_in = spec.get("functional_in")
        if functional_in is not None and not (
                isinstance(functional_in, int) and 0 <= functional_in < len(spec["slots"])):
            report.add("error", "predicate.bad_functional_in",
                       f"Predicate {name}.functional_in must index one of its slots.", cpath)
        schema[name] = spec
    return schema


def _validate_proposition(report: ValidationReport, prop, path: str, known_predicates=None):
    if not prop:
        return
    if "predicate" not in prop or "slots" not in prop:
        report.add("error", "proposition.bad_shape",
                   "Proposition must include predicate and slots.", path)
        return
    catalog = CORE_PREDICATES if known_predicates is None else known_predicates
    predicate = prop["predicate"]
    if predicate not in catalog:
        report.add("error", "proposition.unknown_predicate",
                   f"Predicate {predicate!r} is neither an engine core predicate nor declared "
                   f"in this pack's canon.json.", path)
        return
    slots = prop.get("slots") or {}
    required = set(catalog[predicate].get("slots") or [])
    missing = sorted(s for s in required if s not in slots)
    if missing:
        report.add("error", "proposition.missing_slots",
                   f"{predicate} is missing slots: {', '.join(missing)}", path)
