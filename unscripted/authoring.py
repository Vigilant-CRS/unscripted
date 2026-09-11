"""Authoring: building a world without knowing how the runtime stores it.

A world pack is JSON, and until now writing one meant knowing things a narrative
designer has no business knowing: that a protected proposition is identified by a
canonical core key, that slot order determines that key, that a routine block runs
until the next one starts, that a topic without phrasings makes characters
deflect. Three packs were written by hand for this project and every one of them
shipped a defect that only showed up in a test.

The runtime is well past the point where the limiting factor is the runtime.

This module is the SDK half of the answer: pure functions over a pack, with no
UI in them. It does three things.

**Scaffold.** :func:`scaffold_pack` writes a small, complete, *playable* world --
two places that connect, two characters who meet, one topic they can answer, one
secret that is actually enforceable. Starting from something that works and
changing it beats starting from an empty directory.

**Document.** :class:`PackDocument` loads every file of a pack as one object and
writes it back, so an editor edits a world rather than seven JSON files.

**Report.** :func:`authoring_report` answers the questions an author actually has
-- can you walk from here to there, do these two ever meet, can anybody answer
this question, would this secret actually be protected -- and says what to do
about each answer. It is deliberately more opinionated than validation: a pack
can be valid and still be a world where nothing happens.

Nothing here mutates a running world, and nothing here needs the runtime to be
started, so an editor can work on a pack that does not load yet.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .contracts import DEFAULT_PLAYER_ID
from .ontology import CORE_PREDICATES, PREDICATE_CATALOG
from .routine import MINUTES_PER_DAY, Routine, parse_clock

PACK_FILES = ("world.json", "scenario.json", "canon.json", "topics.json",
              "initial_state.json")


# ------------------------------------------------------------------ helpers --

def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_") or "unnamed"


def proposition_template(predicate: str, slots: dict, polarity: str = "+") -> dict:
    """Build a proposition the way an author thinks of it: a name and its fields.

    Authors never write core keys. They pick a predicate and fill its slots; the
    loader canonicalises. Handing someone ``pred(a=1,b=2)[None,None,None]`` to type
    is an invitation to typo a security control into silence.
    """
    known = PREDICATE_CATALOG.get(predicate)
    if known:
        missing = [s for s in known["slots"] if s not in slots]
        if missing:
            raise ValueError(f"{predicate} needs slots {known['slots']}; missing {missing}")
    return {"predicate": predicate, "slots": dict(slots), "polarity": polarity}


def predicate_menu(pack_predicates: dict | None = None) -> list:
    """Every predicate an author can choose from, with its fields, for a dropdown."""
    menu = []
    for name, spec in sorted({**CORE_PREDICATES, **(pack_predicates or {})}.items()):
        menu.append({"predicate": name, "slots": list(spec.get("slots") or []),
                     "source": "engine" if name in CORE_PREDICATES else "this pack"})
    return menu


# ----------------------------------------------------------------- document --

@dataclass
class PackDocument:
    """A whole world pack as one editable object."""

    path: str
    world: dict = field(default_factory=dict)
    scenario: dict = field(default_factory=dict)
    canon: dict = field(default_factory=dict)
    topics: dict = field(default_factory=dict)
    initial_state: dict = field(default_factory=dict)
    characters: dict = field(default_factory=dict)      # filename -> character dict

    @staticmethod
    def load(path: str) -> "PackDocument":
        def read(name, default):
            fp = os.path.join(path, name)
            if not os.path.exists(fp):
                return default
            with open(fp, "r", encoding="utf-8") as fh:
                return json.load(fh)

        doc = PackDocument(
            path=path,
            world=read("world.json", {}),
            scenario=read("scenario.json", {}),
            canon=read("canon.json", {}),
            topics=read("topics.json", {"topics": []}),
            initial_state=read("initial_state.json", {"beliefs": []}),
        )
        chardir = os.path.join(path, "characters")
        if os.path.isdir(chardir):
            for fn in sorted(os.listdir(chardir)):
                if fn.endswith(".json"):
                    doc.characters[fn] = read(os.path.join("characters", fn), {})
        return doc

    def save(self) -> list:
        """Write the whole pack back. Returns the files touched."""
        os.makedirs(os.path.join(self.path, "characters"), exist_ok=True)
        written = []
        for name, data in (("world.json", self.world), ("scenario.json", self.scenario),
                           ("canon.json", self.canon), ("topics.json", self.topics),
                           ("initial_state.json", self.initial_state)):
            written.append(_write_json(os.path.join(self.path, name), data))
        for filename, character in self.characters.items():
            written.append(_write_json(
                os.path.join(self.path, "characters", os.path.basename(filename)), character))
        return written

    # -- convenience an editor uses ------------------------------------------
    def place_ids(self) -> list:
        return sorted(self.world.get("places") or {})

    def character_ids(self) -> list:
        return sorted(c.get("id", "") for c in self.characters.values() if c.get("id"))

    def topic_ids(self) -> list:
        return [t.get("id") for t in (self.topics.get("topics") or []) if t.get("id")]

    def as_dict(self) -> dict:
        return {"path": self.path, "world": self.world, "scenario": self.scenario,
                "canon": self.canon, "topics": self.topics,
                "initial_state": self.initial_state, "characters": self.characters}


def _write_json(path: str, data) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    return path


# ----------------------------------------------------------------- scaffold --

def scaffold_pack(path: str, *, name: str = "New World", start: str = "08:00",
                  language: str = "en", overwrite: bool = False) -> PackDocument:
    """Write a small pack that already works, for an author to change.

    Everything the runtime needs in order to be interesting is present and wired:
    two connected places, two characters whose routines make them meet, a topic one
    of them can answer, and a secret the other actually withholds. An author who
    renames things has a working world; an author starting from an empty directory
    has a week of reading documentation.
    """
    if os.path.exists(path) and os.listdir(path) and not overwrite:
        raise FileExistsError(f"{path} is not empty; pass overwrite=True to write anyway")
    os.makedirs(os.path.join(path, "characters"), exist_ok=True)

    start_minute = parse_clock(start)
    doc = PackDocument(path=path)
    doc.world = {
        "places": {
            "place:square": {
                "label": "The Square", "aliases": ["square", "market"],
                "exits": ["place:tavern"],
                "noise_level": 0.5, "surveillance_level": 0.3, "privacy_level": 0.2,
                "formality": 0.35, "gossip_factor": 1.6,
            },
            "place:tavern": {
                "label": "The Tavern", "aliases": ["tavern", "inn", "bar"],
                "exits": ["place:square"],
                "noise_level": 0.6, "surveillance_level": 0.1, "privacy_level": 0.5,
                "formality": 0.25, "gossip_factor": 1.3,
            },
        },
        "identity_values": {"trader": ["achievement", "security"],
                            "keeper": ["benevolence", "tradition"]},
        "channels": {}, "entities": {}, "media_exposure": [], "factions": [],
        "diffusion": {"encounters_per_hour": 0.4, "distortion_prob": 0.06},
    }
    doc.scenario = {
        # A WORLD SAYS WHAT IT IS, from the first minute of a new pack.
        #
        # Without this a save can only be matched to a world by inference, and
        # `inspect_state` correctly reports `world_unverified` rather than `ok`.
        # Every shipped pack declares one; a pack an author has just created is
        # the one that most needs to, because it is about to be renamed, copied
        # and forked into three variants before anybody thinks about save
        # compatibility. Change it freely while nothing has been saved; after
        # that, changing it makes existing saves foreign.
        "world_id": slug(name),
        "global_seed": f"{slug(name)}-001",
        "world_time": start_minute,
        "player_start": "place:square",
        "focus_agents": ["agent:mara"],
        "events": [],
    }
    doc.canon = {
        "predicates": {
            "delivery_arrived": {"slots": ["goods", "when"], "functional_in": 1},
        },
        "canon_facts": [
            {"predicate": "delivery_arrived",
             "slots": {"goods": "goods:grain", "when": "yesterday"}, "polarity": "-"},
        ],
    }
    doc.topics = {"topics": [{
        "id": "delivery",
        "label": "The delivery that never came",
        "aliases": ["delivery", "grain", "cart", "shipment"],
        "query": proposition_template("delivery_arrived",
                                      {"goods": "goods:grain", "when": "yesterday"}, "-"),
        "player_claim": proposition_template("delivery_arrived",
                                             {"goods": "goods:grain", "when": "yesterday"}, "-"),
        "phrasings": {
            "affirm": {"formal": "No, nothing arrived yesterday.",
                       "neutral": "Nothing came yesterday.",
                       "vernacular": "Nothing came. Not a sack."},
            "deny": {"formal": "It arrived exactly as arranged.",
                     "neutral": "It came, same as always.",
                     "vernacular": "Came fine."},
        },
    }]}
    doc.characters = {
        "mara.json": {
            "id": "agent:mara", "class": "core:NPCAgent",
            "names": {"public": "Mara", "objective": "Mara Vance",
                      "aliases": ["mara", "vance", "trader"]},
            "big_five": {"openness": 0.55, "conscientiousness": 0.6, "extraversion": 0.6,
                         "agreeableness": 0.5, "emotional_stability": 0.55},
            "schwartz": {"achievement": 0.6, "security": 0.5},
            "needs": {"income": 0.6, "safety": 0.3},
            "identities": [{"id": "trader", "group": "district:square", "accessibility": 0.8}],
            "roles": [{"role": "role:trader", "context": "district:square"}],
            "education": {"domains": {"general": 0.5, "trade": 0.8, "gossip": 0.7}},
            "relationships": {DEFAULT_PLAYER_ID: {"trust": 0.3, "liking": 0.0, "familiarity": 0.0},
                              "agent:tomas": {"trust": 0.5, "liking": 0.3, "familiarity": 0.7}},
            "secrets": [],
            "goals": [{"content": "keep_the_stall", "priority": 0.8}],
            "social_status": 0.45, "resources": 0.4,
            "location": "place:square",
            "routine": [
                {"from": "06:00", "place": "place:square", "activity": "running the stall"},
                {"from": "19:00", "place": "place:tavern", "activity": "a drink after close"},
                {"from": "23:00", "place": "place:square", "activity": "sleeping by the stall"},
            ],
        },
        "tomas.json": {
            "id": "agent:tomas", "class": "core:NPCAgent",
            "names": {"public": "Tomas", "objective": "Tomas Reed",
                      "aliases": ["tomas", "reed", "keeper", "innkeeper"]},
            "big_five": {"openness": 0.4, "conscientiousness": 0.7, "extraversion": 0.5,
                         "agreeableness": 0.45, "emotional_stability": 0.6},
            "schwartz": {"benevolence": 0.6, "tradition": 0.6},
            "needs": {"income": 0.5, "recognition": 0.4},
            "identities": [{"id": "keeper", "group": "district:square", "accessibility": 0.85}],
            "roles": [{"role": "role:bartender", "context": "place:tavern"}],
            "education": {"domains": {"general": 0.45, "gossip": 0.8}},
            "relationships": {DEFAULT_PLAYER_ID: {"trust": 0.3, "liking": 0.0, "familiarity": 0.0},
                              "agent:mara": {"trust": 0.5, "liking": 0.3, "familiarity": 0.7}},
            "secrets": [{
                "id": "secret:the_cart",
                "avoid_label": "the_missing_cart",
                "guards_topics": ["delivery"],
                "summary": "Tomas took the grain himself and sold it on.",
                "surface_forms": ["i took it", "sold it on", "behind the tavern"],
                "protects": [proposition_template(
                    "delivery_arrived", {"goods": "goods:grain", "when": "yesterday"}, "-")],
                "about": ["agent:tomas"],
                "min_trust": 0.55,
            }],
            "goals": [{"content": "keep_the_tavern_quiet", "priority": 0.75}],
            "social_status": 0.5, "resources": 0.45,
            "location": "place:tavern",
            "routine": [
                {"from": "09:00", "place": "place:square", "activity": "buying supplies"},
                {"from": "12:00", "place": "place:tavern", "activity": "behind the bar"},
            ],
        },
    }
    doc.initial_state = {"beliefs": [{
        "agent": "agent:mara",
        "proposition": proposition_template(
            "delivery_arrived", {"goods": "goods:grain", "when": "yesterday"}, "-"),
        "summary": "Mara waited all day and no cart came.",
        "origin_event": "seed_mara_waited",
        "trust": 0.95, "competence": 0.9, "importance": 0.8,
    }]}
    # A pack whose opening scene disagrees with its own routines is the first trap
    # every author falls into, so the scaffold cannot ship with one.
    for character in doc.characters.values():
        block = Routine.from_list(character.get("routine")).block_at(start_minute)
        if block:
            character["location"] = block[1]
    doc.save()
    return doc


# ------------------------------------------------------------------- report --

@dataclass
class Finding:
    """Something an author should know, and what to do about it."""

    level: str          # "blocker" | "problem" | "hint"
    area: str
    message: str
    fix: str = ""

    def as_dict(self):
        return {"level": self.level, "area": self.area, "message": self.message, "fix": self.fix}


def authoring_report(doc: PackDocument, *, samples: int = 48) -> dict:
    """The questions an author has, answered — with what to do about each.

    Deliberately more opinionated than validation. A pack can be perfectly valid
    and still be a world where nobody meets, nothing can be asked, and every
    secret is decorative.
    """
    findings: list = []
    places = doc.world.get("places") or {}

    # AND WHAT THE RUNTIME ITSELF SAYS, which this never asked.
    #
    # There are two gates in this project and they check different things: this
    # one asks whether a world is worth playing -- can anybody be asked
    # anything, does anybody meet anybody -- and `unscripted validate` asks whether it
    # will load at all. A generated pack passed here and was refused there over
    # predicates with no slots and forty colliding aliases, so this said READY
    # TO PLAY about something the runtime would not open. A gate that clears
    # what the next gate rejects is worse than no gate: it is a gate somebody
    # trusts.
    try:
        from .pack import validate_world_pack
        loadable = validate_world_pack(doc.path)
        for issue in loadable.issues:
            if issue.severity != "error":
                continue
            findings.append(Finding(
                "blocker", "loadable", issue.message,
                "The runtime refuses to load this. `unscripted validate` reports the "
                "same thing, and nothing here can be played until it stops."))
    except Exception as exc:                       # pragma: no cover - defensive
        findings.append(Finding(
            "problem", "loadable", f"Could not ask the runtime to check this: {exc}",
            "Run `unscripted validate` on the pack directly."))

    # AN EMPTY PACK IS NOT A READY ONE. Every check below asks whether the
    # things in a pack are wired correctly, and each of them is vacuously
    # satisfied by there being nothing there -- so a directory with five empty
    # files was reported READY TO PLAY. Found by pointing a generator at this
    # gate and watching it approve the generator's own failure to write
    # anything.
    for what, present in (("place", len(places)),
                          ("character", len(doc.characters or {})),
                          ("topic", len((doc.topics or {}).get("topics") or []))):
        if not present:
            findings.append(Finding(
                "blocker", "pack", f"This pack has no {what}s at all.",
                f"Every check here asks whether the {what}s are wired up. With "
                f"none, they all pass and the pack is still unplayable."))
    characters = [c for c in doc.characters.values() if c.get("id")]
    topics = doc.topics.get("topics") or []
    start_minute = int(doc.scenario.get("world_time", 0)) % MINUTES_PER_DAY

    # -- the map --------------------------------------------------------------
    exits = {pid: list((attrs or {}).get("exits") or []) for pid, attrs in places.items()}
    reachable = _reachable_from(doc.scenario.get("player_start") or next(iter(places), None), exits)
    for pid in sorted(places):
        if pid not in reachable:
            findings.append(Finding(
                "problem", "map", f"{_label(places, pid)} cannot be walked to from the start.",
                "Add it to another place's exits, or accept that only events put people there."))
        if not exits.get(pid):
            findings.append(Finding(
                "problem", "map", f"{_label(places, pid)} has no way out.",
                "Give it an 'exits' list, or players who enter are stuck."))

    # -- the day --------------------------------------------------------------
    schedules = {}
    for character in characters:
        blocks = character.get("routine")
        if not blocks:
            findings.append(Finding(
                "hint", "routine", f"{_name(character)} never moves.",
                "Fine for a shopkeeper. Add a 'routine' if they should have a day."))
            continue
        try:
            schedules[character["id"]] = Routine.from_list(blocks)
        except (KeyError, ValueError) as exc:
            findings.append(Finding("blocker", "routine",
                                    f"{_name(character)} has an unreadable routine: {exc}",
                                    "Times are HH:MM; every block needs 'from' and 'place'."))

    day_grid = {}
    step = max(1, MINUTES_PER_DAY // samples)
    for agent_id, routine in schedules.items():
        day_grid[agent_id] = [
            {"minute": minute,
             "clock": f"{minute // 60:02d}:{minute % 60:02d}",
             "place": (routine.block_at(minute) or (0, None, ""))[1],
             "activity": (routine.block_at(minute) or (0, None, ""))[2]}
            for minute in range(0, MINUTES_PER_DAY, step)]

    # -- who meets whom -------------------------------------------------------
    meetings = {}
    for minute in range(0, MINUTES_PER_DAY, step):
        occupancy = {}
        for agent_id, routine in schedules.items():
            block = routine.block_at(minute)
            if block:
                occupancy.setdefault(block[1], []).append(agent_id)
        for place, present in occupancy.items():
            for i, one in enumerate(sorted(present)):
                for other in sorted(present)[i + 1:]:
                    entry = meetings.setdefault((one, other), {"hours": 0, "places": set()})
                    entry["hours"] += step / 60.0
                    entry["places"].add(place)
    meeting_rows = [{"a": a, "b": b, "hours_per_day": round(v["hours"], 1),
                     "places": sorted(v["places"])}
                    for (a, b), v in sorted(meetings.items())]

    lonely = [aid for aid in schedules
              if not any(aid in (row["a"], row["b"]) for row in meeting_rows)]
    for agent_id in lonely:
        findings.append(Finding(
            "problem", "society", f"{agent_id} never shares a place with anyone.",
            "Nothing can be told to them and they can tell nobody. Overlap a routine block."))
    if schedules and not meeting_rows:
        findings.append(Finding(
            "blocker", "society", "No two characters are ever in the same place.",
            "Rumour cannot spread at all. Give two characters an overlapping block."))

    # -- can anything be asked? ----------------------------------------------
    answerable = _answerable_topics(doc)
    for topic in topics:
        tid = topic.get("id")
        if not topic.get("aliases"):
            findings.append(Finding("problem", "topics", f"Topic '{tid}' has no aliases.",
                                    "Players type words, not ids. Add the words they would use."))
        if topic.get("query") and not topic.get("phrasings"):
            findings.append(Finding(
                "problem", "topics", f"Topic '{tid}' can be asked but has no phrasings.",
                "Characters will deflect instead of answering. Add phrasings.affirm/deny."))
        if topic.get("query") and tid not in answerable:
            findings.append(Finding(
                "problem", "topics", f"Nobody in this world can answer '{tid}'.",
                "Seed a belief in initial_state.json for at least one character."))

    # -- are the secrets real? ------------------------------------------------
    for character in characters:
        for secret in character.get("secrets") or []:
            if isinstance(secret, str):
                findings.append(Finding(
                    "problem", "secrets", f"{_name(character)} has a bare-string secret.",
                    "It has no surface forms and no trust gate, so it changes nothing."))
                continue
            sid = secret.get("id", "?")
            if not secret.get("surface_forms"):
                findings.append(Finding(
                    "problem", "secrets", f"Secret '{sid}' has no surface forms.",
                    "A text provider phrasing it freely would not be caught. List the "
                    "words that would give it away."))
            if not secret.get("guards_topics"):
                findings.append(Finding(
                    "hint", "secrets", f"Secret '{sid}' guards no topic.",
                    "Without guards_topics it filters facts but changes no behaviour."))
            for guarded in secret.get("guards_topics") or []:
                if guarded not in doc.topic_ids():
                    findings.append(Finding(
                        "blocker", "secrets", f"Secret '{sid}' guards unknown topic '{guarded}'.",
                        f"Known topics: {', '.join(doc.topic_ids()) or '(none)'}"))

    # -- the opening scene ----------------------------------------------------
    for character in characters:
        routine = schedules.get(character.get("id"))
        authored = character.get("location")
        if routine and authored:
            block = routine.block_at(start_minute)
            if block and block[1] != authored:
                findings.append(Finding(
                    "blocker", "scene",
                    f"{_name(character)} starts at {_label(places, authored)} but their "
                    f"routine puts them at {_label(places, block[1])} at "
                    f"{start_minute // 60:02d}:{start_minute % 60:02d}.",
                    "The pack disagrees with itself about where the scene opens."))

    order = {"blocker": 0, "problem": 1, "hint": 2}
    findings.sort(key=lambda f: (order[f.level], f.area, f.message))
    return {
        "pack": doc.path,
        "start_clock": f"{start_minute // 60:02d}:{start_minute % 60:02d}",
        "counts": {"places": len(places), "characters": len(characters),
                   "topics": len(topics), "secrets": sum(len(c.get("secrets") or [])
                                                         for c in characters)},
        "map": [{"place": pid, "label": _label(places, pid), "exits": exits.get(pid, []),
                 "reachable": pid in reachable,
                 "gossip_factor": (places[pid] or {}).get("gossip_factor", 1.0)}
                for pid in sorted(places)],
        "day": day_grid,
        "meetings": meeting_rows,
        "answerable_topics": sorted(answerable),
        "findings": [f.as_dict() for f in findings],
        "ready": not any(f.level == "blocker" for f in findings),
    }


def _answerable_topics(doc: PackDocument) -> set:
    """Topics at least one character holds a matching belief about."""
    seeded = set()
    for belief in doc.initial_state.get("beliefs") or []:
        proposition = belief.get("proposition") or {}
        if proposition.get("predicate"):
            seeded.add((proposition["predicate"],
                        tuple(sorted((proposition.get("slots") or {}).items()))))
    answerable = set()
    for topic in doc.topics.get("topics") or []:
        query = topic.get("query")
        if not query:
            continue
        key = (query.get("predicate"), tuple(sorted((query.get("slots") or {}).items())))
        if key in seeded:
            answerable.add(topic.get("id"))
        elif any(predicate == query.get("predicate") for predicate, _slots in seeded):
            answerable.add(topic.get("id"))   # same predicate, different slots: close enough
    return answerable


def _reachable_from(start, exits: dict) -> set:
    if not start:
        return set()
    seen, queue = {start}, [start]
    while queue:
        current = queue.pop()
        for target in exits.get(current, []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _label(places: dict, place_id) -> str:
    return ((places.get(place_id) or {}).get("label") or place_id) if place_id else "?"


def _name(character: dict) -> str:
    return (character.get("names") or {}).get("public") or character.get("id", "?")


def render_report(report: dict) -> str:
    """The report as text, for the CLI."""
    counts = report["counts"]
    out = [
        "=" * 78,
        f"  {report['pack']}",
        "=" * 78,
        f"  {counts['places']} places · {counts['characters']} characters · "
        f"{counts['topics']} topics · {counts['secrets']} secrets · opens {report['start_clock']}",
        "",
        "  MAP",
    ]
    for entry in report["map"]:
        arrow = " -> " + ", ".join(entry["exits"]) if entry["exits"] else " (no exits)"
        mark = "  " if entry["reachable"] else " !"
        out.append(f"   {mark}{entry['label']}{arrow}")

    out.append("")
    out.append("  WHO MEETS WHOM (hours per day)")
    if report["meetings"]:
        for row in report["meetings"]:
            out.append(f"     {row['a']} + {row['b']}: {row['hours_per_day']}h "
                       f"in {', '.join(row['places'])}")
    else:
        out.append("     nobody ever meets — no rumour can spread")

    out.append("")
    out.append(f"  ANSWERABLE TOPICS: {', '.join(report['answerable_topics']) or 'none'}")

    findings = report["findings"]
    out.append("")
    if not findings:
        out.append("  Nothing to fix.")
    else:
        marks = {"blocker": "BLOCKER", "problem": "problem", "hint": "hint   "}
        out.append(f"  {len(findings)} THING(S) TO LOOK AT")
        for finding in findings:
            out.append(f"   [{marks[finding['level']]}] {finding['message']}")
            if finding["fix"]:
                out.append(f"              -> {finding['fix']}")
    out.append("")
    out.append("=" * 78)
    out.append(f"  {'READY TO PLAY' if report['ready'] else 'NOT PLAYABLE YET'}")
    out.append("=" * 78)
    return "\n".join(out)
