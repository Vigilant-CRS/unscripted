"""World container + World-Pack loader (spec v0.5 §9.2).

A World Pack is a directory of declarative JSON files. The loader validates and
instantiates entities, places, channels, agents, topics, secrets and the
scenario. Nothing about the world lives in an LLM prompt -- and, since the
content split, nothing about a *particular* world lives in the SDK either: a
pack brings its own topology, vocabulary, secrets and predicates.

Pack layout:

    world.json          places (attributes, label, exits, aliases), entities,
                        channels, factions, media exposure
    scenario.json       seed, start time, scheduled events, focus agents
    canon.json          pack-declared predicates and canon facts
    topics.json         what the player can ask about, and how the world reacts
    initial_state.json  authored starting beliefs
    characters/*.json   agents, including their aliases and structured secrets
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
from .agent import Agent
from .content import AliasIndex, Secret, Topic, secrets_from
from .events import Event
from .ontology import register_predicates
from .routine import Routine


@dataclass
class World:
    global_seed: str = "unscripted-seed-0"
    world_time: int = 0
    places: dict = field(default_factory=dict)            # id -> attrs (noise_level, label, exits, ...)
    entities: dict = field(default_factory=dict)
    channels: dict = field(default_factory=dict)
    agents: dict = field(default_factory=dict)            # id -> Agent
    media_exposure: dict = field(default_factory=dict)    # (agent_id, channel) -> {attention}
    scenario_events: list = field(default_factory=list)   # scheduled Events
    factions: list = field(default_factory=list)          # raw faction dicts (built into Faction by runtime)
    initial_beliefs: list = field(default_factory=list)   # authored belief seeds from initial_state.json
    topics: dict = field(default_factory=dict)            # topic_id -> Topic
    identity_values: dict = field(default_factory=dict)   # identity id -> value names it amplifies
    focus_agents: tuple = ()                              # authored fallback order for unaddressed speech
    player_start: str = ""                                # authored starting place for the player
    #: What this world IS, as opposed to what it currently contains. Authored in
    #: `scenario.json: world_id`. A save carries it, and a loader refuses one
    #: whose id is not this world's -- which is the only answer that does not
    #: depend on two packs happening to share a name. Empty means the pack has
    #: not said, and the loader falls back to comparing the cast and the map.
    world_id: str = ""
    canon_facts: list = field(default_factory=list)
    #: predicate -> which competence bears on it (whose word counts about this)
    predicate_domains: dict = field(default_factory=dict)
    #: predicate -> {"domain": str, "level": float}: what it takes to RECOGNISE
    #: an event of this kind. Below it, an observer sees something coarser.
    predicate_competence: dict = field(default_factory=dict)
    #: The raw predicate declarations, for the knowledge-topology layer: what
    #: class a claim is, who may circulate it, where, and how readily.
    predicates: dict = field(default_factory=dict)

    def occupants(self, place_id: str) -> list:
        """Everyone at a place. Cached, and invalidated by any move.

        Perception used to scan the whole cast for every event. With hundreds of
        characters that is quadratic -- more people produce more events AND make
        each event more expensive to route -- and it was the dominant cost in a
        large world once persistence was taken out of the way.
        """
        from . import agent as agent_module
        epoch = agent_module.LOCATION_EPOCH
        if getattr(self, "_occupancy_epoch", None) != epoch:
            index: dict = {}
            for a in self.agents.values():
                index.setdefault(a.location, []).append(a)
            for bucket in index.values():
                bucket.sort(key=lambda a: a.id)      # deterministic order
            self._occupancy = index
            self._occupancy_epoch = epoch
        return self._occupancy.get(place_id, ())
    command_aliases: dict = field(default_factory=dict)    # intent -> words, extends the engine lexicon
    #: predicate -> {dimension, sign, weight} for the `standing` layer. What
    #: counts as decency is a fact about a setting, so a pack may add predicates
    #: or retune the two that ship. Read even when the layer is off, because
    #: loading a pack must not depend on which mechanics are switched on.
    standing_conduct: dict = field(default_factory=dict)
    #: `scenario.json: intro` -- the pack's own opening paragraph.
    scenario_intro: str = ""
    #: appearance token -> {status, threat, signals}. What a garment or a symbol
    #: does to how its wearer is read. Empty in every shipped pack, which is why
    #: adding this changed nothing: authored data that defaults to nothing needs
    #: no switch.
    appearance_reactions: dict = field(default_factory=dict)
    dialogue_templates: dict = field(default_factory=dict) # act -> register -> line
    slang_lexicon: dict = field(default_factory=dict)      # plain word -> in-group word
    diffusion_params: dict = field(default_factory=dict)   # how gossip moves in this world
    #: Authored overrides for every engine's parameters. `how this world works`
    #: is content: a mediaeval village and a surveillance state are not the same
    #: simulation with different names in it. See unscripted/tuning.py.
    tuning: dict = field(default_factory=dict)
    routine_params: dict = field(default_factory=dict)     # how daily schedules behave
    pack_path: str = ""
    _next_event_id: int = 1000
    _alias_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def new_event_id(self):
        self._next_event_id += 1
        return self._next_event_id

    def invalidate_indexes(self):
        """Drop cached alias indexes. Call after adding places, agents or topics."""
        self._alias_cache.clear()

    def _index(self, key, build):
        # Alias indexes are rebuilt only when the roster changes (the SDK adds the
        # player agent at startup, the generator can add characters at runtime),
        # so parsing does not pay to re-sort the vocabulary on every turn.
        stamp = (len(self.agents), len(self.places), len(self.topics))
        cached = self._alias_cache.get(key)
        if cached is None or cached[0] != stamp:
            cached = (stamp, build())
            self._alias_cache[key] = cached
        return cached[1]

    # ---- authored topology ----
    def place_label(self, place_id: str) -> str:
        """Display name for a place; falls back to the id so an unlabelled pack still runs."""
        return (self.places.get(place_id) or {}).get("label") or place_id

    def exits_from(self, place_id: str) -> list:
        return list((self.places.get(place_id) or {}).get("exits") or [])

    def place_formality(self, place_id: str, default: float = 0.4) -> float:
        """Setting formality (police post vs back room). Authored per place."""
        value = (self.places.get(place_id) or {}).get("formality")
        return default if value is None else float(value)

    # ---- authored vocabulary ----
    def place_alias_index(self) -> AliasIndex:
        return self._index("places", lambda: AliasIndex.build(
            {pid: _place_aliases(pid, attrs) for pid, attrs in self.places.items()}))

    def agent_alias_index(self) -> AliasIndex:
        return self._index("agents", lambda: AliasIndex.build(
            {agent.id: _agent_aliases(agent) for agent in self.agents.values()}))

    def topic_alias_index(self) -> AliasIndex:
        return self._index("topics", lambda: AliasIndex.build(
            {t.topic_id: (t.aliases or (t.topic_id,)) for t in self.topics.values()}))

    # ---- authored secrets ----
    def all_secrets(self) -> list:
        return [secret for agent in self.agents.values() for secret in agent.secrets]


def _place_aliases(place_id: str, attrs: dict) -> tuple:
    authored = tuple(attrs.get("aliases") or ())
    if authored:
        return authored
    # A pack that authored no aliases still gets a usable one from its label or id,
    # so `go <place>` works before the vocabulary is filled in.
    label = attrs.get("label")
    return (label.lower(),) if label else (place_id.split(":", 1)[-1].replace("_", " "),)


def _agent_aliases(agent: Agent) -> tuple:
    authored = tuple(a.lower() for a in (agent.aliases or ()))
    fallback = tuple(n.lower() for n in (agent.public_name, agent.objective_name) if n)
    return authored or fallback or (agent.id.split(":", 1)[-1].replace("_", " "),)


def load_world_pack(path: str) -> World:
    def _read(name):
        fp = os.path.join(path, name)
        if not os.path.exists(fp):
            return {}
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)

    world_data = _read("world.json")
    scenario = _read("scenario.json")
    canon = _read("canon.json")
    topics_data = _read("topics.json")
    initial_state = _read("initial_state.json")

    w = World(global_seed=scenario.get("global_seed", "unscripted-seed-0"),
              world_time=scenario.get("world_time", 0),
              pack_path=path)
    w.places = world_data.get("places", {})
    w.entities = world_data.get("entities", {})
    w.channels = world_data.get("channels", {})
    w.identity_values = {k: tuple(v) for k, v in (world_data.get("identity_values") or {}).items()}
    w.command_aliases = {k: list(v) for k, v in (world_data.get("command_aliases") or {}).items()}
    w.standing_conduct = {k: dict(v) for k, v in (world_data.get("standing_conduct") or {}).items()}
    # `_note` keys are how every section of a pack carries its own explanation,
    # and they are strings rather than tables. Skipped here rather than special
    # cased at every read.
    w.appearance_reactions = {k: dict(v) for k, v in
                              (world_data.get("appearance_reactions") or {}).items()
                              if not k.startswith("_") and isinstance(v, dict)}
    w.dialogue_templates = world_data.get("dialogue_templates") or {}
    w.slang_lexicon = world_data.get("slang_lexicon") or {}
    w.diffusion_params = world_data.get("diffusion") or {}
    w.tuning = world_data.get("tuning") or {}
    w.routine_params = world_data.get("routine") or {}

    # Pack-declared predicates must be registered before any proposition from this
    # pack is parsed: slot order defines a proposition's canonical key.
    register_predicates(canon.get("predicates"), source=f"world pack {os.path.basename(path)}")
    # Which competence applies to a claim, and what it takes to recognise one.
    # Both are world content: "you need an engineer to see that this was
    # deliberate" is a fact about a setting, not about an engine.
    for name, spec in (canon.get("predicates") or {}).items():
        if (spec or {}).get("domain"):
            w.predicate_domains[name] = spec["domain"]
        if (spec or {}).get("requires_competence"):
            w.predicate_competence[name] = dict(spec["requires_competence"])
        w.predicates[name] = dict(spec or {})
    w.canon_facts = canon.get("canon_facts", [])

    for entry in (topics_data.get("topics") or []):
        topic = Topic.from_dict(entry)
        w.topics[topic.topic_id] = topic

    # characters
    chardir = os.path.join(path, "characters")
    if os.path.isdir(chardir):
        for fn in sorted(os.listdir(chardir)):
            if not fn.endswith(".json"):
                continue
            cd = _read(os.path.join("characters", fn))
            names = cd.get("names", {})
            agent = Agent(
                id=cd["id"], big_five=cd.get("big_five", {}), schwartz=cd.get("schwartz", {}),
                needs=cd.get("needs", {}), identities=cd.get("identities", []),
                roles=cd.get("roles", []), appearance=cd.get("appearance", {}),
                education=cd.get("education", {}).get("domains", cd.get("education", {})),
                relationships=cd.get("relationships", {}),
                secrets=secrets_from(cd.get("secrets"), owner=cd["id"]),
                goals=cd.get("goals", []), location=cd.get("location"),
                public_name=names.get("public"),
                objective_name=names.get("objective"),
                aliases=tuple(names.get("aliases") or ()),
                routine=Routine.from_list(cd.get("routine")),
                social_status=cd.get("social_status", 0.4),
                resources=cd.get("resources", 0.4),
                dialect=cd.get("dialect"),
                values=cd.get("values", {}),
                epistemic=cd.get("epistemic", {}),
                networks=tuple(cd.get("networks") or ()),
                voice=cd.get("voice", {}),
                contacts=tuple(cd.get("contacts") or ()))
            w.agents[agent.id] = agent

    # media exposure
    for me in world_data.get("media_exposure", []):
        w.media_exposure[(me["agent"], me["channel"])] = {"attention": me.get("attention", 0.5)}

    # factions (raw dicts; the runtime builds Faction objects + clocks)
    w.factions = world_data.get("factions", [])

    # scenario scheduled events
    for ev in scenario.get("events", []):
        w.scenario_events.append(Event(
            event_id=w.new_event_id(), world_time=ev.get("world_time", w.world_time),
            type=ev["type"], actor=ev.get("actor"), location=ev.get("location"),
            payload=ev.get("payload", {}), canonical=ev.get("canonical", True)))

    #: What a pack says before its first prompt. Optional; `unscripted play` falls back
    #: to describing the runtime rather than inventing a story.
    w.scenario_intro = scenario.get("intro") or ""
    w.focus_agents = tuple(scenario.get("focus_agents") or ())
    w.player_start = scenario.get("player_start") or (next(iter(w.places), "") if w.places else "")
    w.world_id = str(scenario.get("world_id") or "")
    w.initial_beliefs = initial_state.get("beliefs", [])

    return w


def pronunciation_hints(world) -> dict:
    """How this world's names are meant to be said, for a synthesiser only.

    A name is a fact about the world, and so is how it is pronounced, which is
    why the hint is authored beside the name rather than kept in a list inside
    the runtime. Only characters whose spelling misleads a synthesiser declare
    one: a hint for every character would be noise, and a wrong hint is worse
    than none at all.

    The result maps what is written to what should be said. Nothing else in the
    system sees it -- the world, the transcript and every log keep the spelling.
    """
    hints = {}
    for agent in world.agents.values():
        said = (getattr(agent, "voice", None) or {}).get("say_as", "")
        if not said:
            continue
        written = agent.public_name or agent.id
        hints[written] = said
        # A character called "Mr. Okada" is also referred to as "Okada"; the
        # respelling matches longest-first, so both entries are safe and the
        # short one catches the cases the long one misses.
        surname = written.split()[-1] if " " in written else ""
        if surname and surname not in hints:
            hints[surname] = said.split()[-1]
    return hints
