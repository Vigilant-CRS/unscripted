"""From a premise to a world pack a studio can actually play, at scale.

`unscripted new` makes a scaffold with two people in two rooms. `unscripted generate-characters`
adds more of them. `unscripted author` says what is wrong. Between those three there was
the thing an RPG needs and nobody had built: **take a premise, produce forty
people across a dozen places who meet each other, know different things, belong
to different circles and can be asked about a dozen topics -- and then let the
gate refuse it until it is right.**

That gap is the honest reason a studio would decline this runtime. Everything
else it needs is here and tested; the content was hand-written JSON, and for a
cast of forty that is a fortnight of typing before the first question can be
asked.

WHY THE VALIDATOR IS INSIDE THE LOOP AND NOT AFTER IT. A generator that emits a
pack and hopes is a template with extra steps: it produces the same four
mistakes every time -- a place nobody can walk to, a character who meets nobody,
a topic nobody can answer, a secret guarding a topic that does not exist -- and
leaves them for an author to find one report at a time. `authoring_report`
already knows how to name all four. So this generates, reads the report, repairs
what it names, and goes round again until the report is empty or nothing
improved. What comes out is not "probably fine". It is a pack that passed the
same gate a hand-written one has to pass.

WHAT IT IS NOT. It does not write prose. Phrasings come out serviceable and
flat -- "I saw the man leave", not a line anybody would keep. That is deliberate:
the shape of a world is structural and can be generated correctly, and the words
are a writer's job. A language model belongs exactly here, at build time,
rewriting phrasings inside a structure this has already proved sound -- and the
gate still runs afterwards.

DETERMINISTIC. The same premise and the same seed produce the same pack, byte
for byte. A generator you cannot re-run is one you cannot fix a bug in.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .authoring import PackDocument, authoring_report, slug
from .determinism import derive_seed, seeded_uniform

#: Trades, and what each one plausibly knows more about than the street does.
#: Small on purpose: a generated cast should be legible, and twelve distinct
#: trades in a district is already more variety than most authored packs have.
TRADES = [
    ("innkeeper", "gossip"), ("trader", "trade"), ("physician", "medicine"),
    ("watchman", "law"), ("clerk", "records"), ("smith", "craft"),
    ("carter", "roads"), ("cook", "gossip"), ("scribe", "records"),
    ("dockhand", "trade"), ("apothecary", "medicine"), ("porter", "roads"),
]

#: Shifts, as (from, until) on the world clock. Two of them overlap on purpose:
#: a cast where nobody's hours touch is a cast where nothing travels, and that
#: is the failure the gate calls "never shares a place with anyone".
SHIFTS = [("06:00", "14:00"), ("10:00", "18:00"), ("14:00", "22:00")]

#: Used when a trade appears more than once, so the second smith is a place a
#: player can name rather than a duplicate.
_ORDINALS = ["", "the other", "the third", "the fourth", "the fifth"]

GIVEN = ["Adde", "Bly", "Corin", "Dessa", "Eno", "Fain", "Gil", "Hale", "Isa",
         "Jarek", "Kesh", "Lune", "Mor", "Nev", "Orla", "Pell", "Quen", "Rask",
         "Sable", "Tove", "Ulf", "Vane", "Wren", "Yara", "Zeph"]
FAMILY = ["Ash", "Brand", "Corr", "Dane", "Ellis", "Frey", "Garrow", "Holt",
          "Ivar", "Kell", "Marsh", "Novak", "Orwell", "Pike", "Rees", "Stroud"]


@dataclass
class Premise:
    """What somebody wants, in the few words a generator can act on."""

    name: str = "Generated World"
    seed: str = "premise"
    places: int = 8
    characters: int = 16
    topics: int = 6
    #: How many circles the cast is spread across. Information moves freely
    #: inside one and slowly between them, which is the whole point of having
    #: more than one -- and a world with a single circle behaves like a world
    #: with none.
    districts: int = 3
    #: When the scene opens. `None` means "work it out": the hour at which the
    #: most people are out on the street, so the first thing anybody sees is a
    #: place with somebody in it. Following the Quick Start used to open on an
    #: empty street at eight in the morning, because everybody was at work.
    start: str | None = None
    #: What happened, in one line. Becomes the canon fact everybody is
    #: eventually asked about, and the thing the liar lies about.
    incident: str = "somebody was robbed in the market at night"
    #: Whether one character holds a secret and a cover story for it.
    liar: bool = True
    _files: dict = field(default_factory=dict, repr=False)


# --------------------------------------------------------------- building --

def _rand(premise: Premise, *parts) -> float:
    """A repeatable number in [0, 1) for this premise and this decision.

    `derive_seed` takes fixed slots -- it was built for the runtime's
    (agent, event, time, module) shape -- so the parts are joined into the salt
    rather than spread across arguments.
    """
    return seeded_uniform(derive_seed(premise.seed, "pipeline", 0, 0, "pipeline",
                                      "|".join(str(p) for p in parts)))


def _pick(items, premise: Premise, *parts):
    return items[int(_rand(premise, *parts) * len(items)) % len(items)]


def build_world(premise: Premise) -> dict:
    """Places on a street, because a street is the only map shape that works.

    Everything opens onto a thoroughfare and the thoroughfare opens onto
    everything. It is not clever, and every alternative I tried failed the
    gate's reachability check somewhere: a grid leaves corners, a chain leaves a
    far end nobody walks to, and a random graph leaves islands.
    """
    count = max(2, premise.places)
    #: Claimed first-come, exactly as character aliases are. Twenty places drawn
    #: from a dozen trades produce two smiths, and the runtime refuses a pack
    #: where "go to the smith" points at two rooms -- rightly, because the
    #: player would be guessing which.
    taken = set()
    places = {"place:street": {
        "label": "The Street", "aliases": ["street", "road", "outside"],
        "exits": [], "noise_level": 0.5, "surveillance_level": 0.3,
        "privacy_level": 0.1, "formality": 0.3, "gossip_factor": 1.5}}
    taken.update(places["place:street"]["aliases"])
    for index in range(count - 1):
        trade, _domain = TRADES[index % len(TRADES)]
        pid = "place:%s_%d" % (slug(trade), index)
        round_number = index // len(TRADES)
        label = ("%s's" % trade.title() if round_number == 0
                 else "%s's, %s" % (trade.title(), _ORDINALS[round_number %
                                                             len(_ORDINALS)]))
        aliases = []
        for candidate in (trade, "%s %d" % (trade, index), slug(label)):
            if candidate and candidate not in taken:
                taken.add(candidate)
                aliases.append(candidate)
        places[pid] = {
            "label": label,
            "aliases": aliases,
            "exits": ["place:street"],
            "noise_level": round(0.2 + 0.4 * _rand(premise, "noise", index), 2),
            "surveillance_level": round(0.1 + 0.4 * _rand(premise, "surv", index), 2),
            "privacy_level": round(0.2 + 0.5 * _rand(premise, "priv", index), 2),
            "formality": round(0.2 + 0.5 * _rand(premise, "form", index), 2),
            "gossip_factor": round(0.6 + 0.8 * _rand(premise, "goss", index), 2),
        }
        places["place:street"]["exits"].append(pid)
    return {
        "_note": ("Generated by `unscripted generate-pack` from a premise, then "
                  "repaired until `unscripted author` had nothing left to say. Edit "
                  "freely: nothing here is special for having been generated."),
        "places": places,
        "predicates": {},          # filled by build_topics
    }


def build_topics(premise: Premise) -> tuple:
    """`(topics.json, canon.json)`. Every topic answerable, by construction.

    A topic with no proposition is a topic nobody can be asked about, and a
    proposition nobody holds is a topic nobody can answer. Both are things the
    gate refuses, so both are decided here rather than discovered later.
    """
    topics, predicates, canon_facts = [], {}, []
    for index in range(max(1, premise.topics)):
        trade, domain = TRADES[index % len(TRADES)]
        predicate = "saw_%s" % slug(trade)
        subject = "person:subject_%d" % index
        predicates[predicate] = {
            # The runtime refuses a predicate with no slots, and the authoring
            # gate did not used to ask it. Both do now.
            "slots": ["who", "where"],
            "classification": "restricted" if index % 4 == 3 else "common",
            "domain": domain,
            # Every fourth thing is trade knowledge that does not leave its
            # trade, so a generated world has walls in it and not only weather.
            **({"access": ["role:%s" % slug(trade)]} if index % 4 == 3 else {}),
        }
        proposition = {"predicate": predicate,
                       "slots": {"who": subject, "where": "place:street"},
                       "polarity": "+"}
        topics.append({
            "id": "topic_%d" % index,
            "label": "What happened at %s's" % trade.title(),
            "aliases": [trade, "%s business" % trade, "topic %d" % index],
            "query": proposition,
            "player_claim": proposition,
            "phrasings": {
                "affirm": {
                    "formal": "I saw %s there, and I would say so again." % trade,
                    "neutral": "The %s saw it. So did I." % trade,
                    "rough": "Aye. Round the %s's." % trade},
                "deny": {
                    "formal": "I could not tell you anything about that.",
                    "neutral": "Not that I know of.",
                    "rough": "No idea."},
            },
        })
        canon_facts.append({"proposition": proposition,
                            "world_time": 0,
                            "note": "generated: %s" % premise.incident})
    return ({"_note": "Generated. Every topic has aliases, a query and phrasings.",
             "topics": topics},
            {"_note": "Generated canon: what is true, whoever believes otherwise.",
             "predicates": predicates,
             "canon_facts": canon_facts})


def build_cast(premise: Premise, world: dict, topics: dict) -> dict:
    """Filename -> character. Routines that overlap, circles that do not.

    Two things the character generator does not do, and both are things the gate
    checks: a routine, so somebody is somewhere at a time and meets whoever else
    is; and a network, so a claim has a circle to stay inside.
    """
    place_ids = [p for p in world["places"] if p != "place:street"]
    characters = {}
    taken = set()
    for index in range(max(2, premise.characters)):
        trade, domain = TRADES[index % len(TRADES)]
        home = place_ids[index % len(place_ids)] if place_ids else "place:street"
        shift = SHIFTS[index % len(SHIFTS)]
        district = "district:%d" % (index % max(1, premise.districts))
        given = _pick(GIVEN, premise, "given", index)
        family = _pick(FAMILY, premise, "family", index)
        agent_id = "agent:%s_%d" % (slug(given), index)
        # NO TWO PEOPLE ANSWER TO THE SAME WORD. Forty characters drawn from
        # twenty-five given names and a dozen trades collide constantly, and the
        # runtime refuses a pack where an alias points at two people -- rightly,
        # because "ask the smith" would then be a coin toss. Aliases are claimed
        # first-come, and everybody keeps at least one nobody else can have.
        public = given if given.lower() not in taken else "%s %s" % (given, family)
        aliases = []
        for candidate in (public.lower(), given.lower(), family.lower(), trade,
                          "%s%d" % (slug(given), index)):
            if candidate and candidate not in taken:
                taken.add(candidate)
                aliases.append(candidate)
        characters["%s_%d.json" % (slug(given), index)] = {
            "id": agent_id,
            "class": "core:NPCAgent",
            "location": home,
            "goals": [{"content": "get through the day at %s" % home,
                       "priority": 0.5}],
            "names": {"public": public,
                      "objective": "%s %s" % (given, family),
                      "aliases": aliases},
            "big_five": {
                "openness": round(0.3 + 0.4 * _rand(premise, "o", index), 2),
                "conscientiousness": round(0.3 + 0.4 * _rand(premise, "c", index), 2),
                "extraversion": round(0.3 + 0.4 * _rand(premise, "e", index), 2),
                "agreeableness": round(0.3 + 0.4 * _rand(premise, "a", index), 2),
                "emotional_stability": round(0.3 + 0.4 * _rand(premise, "s", index), 2)},
            "education": {"general": round(0.3 + 0.4 * _rand(premise, "edu", index), 2),
                          domain: round(0.55 + 0.35 * _rand(premise, "dom", index), 2),
                          "gossip": round(0.3 + 0.5 * _rand(premise, "gos", index), 2)},
            "roles": [{"role": "role:%s" % slug(trade), "context": home}],
            "networks": [district],
            "identities": [{"id": slug(trade), "group": district,
                            "accessibility": 0.7}],
            "appearance": {"garment": "item:%s_coat" % slug(trade)},
            # THE ROUTINE. Home for their shift, the street either side of it.
            # The street is what makes the cast one society rather than a dozen
            # rooms: everybody passes through it, at overlapping hours.
            # Built through a dict so a time cannot appear twice. The late
            # shift ends at 22:00 and the night block began at 22:00, which the
            # gate calls "two blocks starting at 22:00" and is right to: a
            # routine with two answers for one hour has no answer for it.
            "routine": [{"from": at, "place": where, "activity": doing}
                        for at, (where, doing) in sorted({
                            shift[0]: (home, "working"),
                            shift[1]: ("place:street", "out"),
                            "23:00": (home, "asleep"),
                        }.items())],
            "relationships": {},
            "secrets": [],
            "social_status": round(0.3 + 0.4 * _rand(premise, "st", index), 2),
        }

    if premise.liar and characters and topics.get("topics"):
        # ONE LIAR, because a world where nobody has a reason to withhold is a
        # world where asking is a formality.
        first = sorted(characters)[0]
        guarded = topics["topics"][0]["id"]
        characters[first]["secrets"] = [{
            "id": "secret:generated",
            "avoid_label": "what_they_saw",
            "guards_topics": [guarded],
            "min_trust": 0.75,
            # The words that would give it away. Without these a text provider
            # phrasing the answer freely could leak the thing the secret exists
            # to protect, and nothing would catch it -- which is why the gate
            # refuses a secret that has none.
            "surface_forms": ["what they saw", "that night", "the subject"],
            "cover_phrasings": {
                "formal": "I was not there and I could not tell you.",
                "neutral": "Wasn't me you want. Ask somebody else.",
                "rough": "Nothing doing."},
        }]
    return characters


def build_initial_state(premise: Premise, cast: dict, topics: dict) -> dict:
    """Who starts out knowing what, so that every topic has an answer.

    Spread rather than shared: each topic is seeded into a couple of people, so
    asking the right person matters and asking anybody does not.
    """
    beliefs = []
    people = [c["id"] for c in (cast[k] for k in sorted(cast))]
    for index, topic in enumerate(topics.get("topics", [])):
        if not people:
            break
        for offset in range(2):
            who = people[(index * 2 + offset) % len(people)]
            beliefs.append({
                "agent": who,
                "proposition": topic["query"],
                # `origin_event` is not decoration. Two people who were told the
                # same thing by the same person are not two witnesses, and the
                # correlation discount needs a name for the origin to know
                # that -- so the runtime refuses a starting belief without one.
                "origin_event": "incident:generated",
                "summary": "What %s has to say about it." % who.split(":")[-1],
                "trust": 0.95 if offset == 0 else 0.7,
                "competence": 0.85 if offset == 0 else 0.6,
                "importance": 0.7,
            })
    return {"_note": "Generated: every topic is held by somebody, twice over.",
            "beliefs": beliefs}


def _where_at(character: dict, hour: int) -> str:
    """Where this character's routine puts them at `hour`."""
    blocks = sorted((b["from"], b["place"]) for b in character.get("routine") or [])
    if not blocks:
        return character.get("location") or "place:street"
    where = blocks[-1][1]                           # wraps from the night before
    for at, place in blocks:
        if int(at.split(":")[0]) <= hour:
            where = place
    return where


def _opening_hour(cast: dict) -> str:
    """The earliest hour with company on the street -- not the busiest.

    The busiest was the first answer and it was wrong: at the hour when the most
    people are outside, every shop is empty, and a world where the whole cast
    stands in one road is less interesting to walk into than one where two
    people are out and the rest are somewhere to be found. So: the earliest hour
    at which at least two are on the street.

    Computed from the routines rather than picked, so it stays right if the
    shifts change.
    """
    on_street = [0] * 24
    for character in cast.values():
        blocks = sorted((b["from"], b["place"]) for b in character.get("routine") or [])
        if not blocks:
            continue
        where = blocks[-1][1]                       # wraps from the night before
        cursor = 0
        for at, place in blocks:
            until = int(at.split(":")[0])
            for hour in range(cursor, until):
                if where == "place:street":
                    on_street[hour] += 1
            where, cursor = place, until
        for hour in range(cursor, 24):
            if where == "place:street":
                on_street[hour] += 1
    for hour in range(24):
        if on_street[hour] >= 2:
            return "%02d:00" % hour
    return "%02d:00" % max(range(24), key=lambda h: (on_street[h], -h))


def build(premise: Premise) -> dict:
    """The whole pack, as filename -> data, before anything is written."""
    world = build_world(premise)
    topics, canon = build_topics(premise)
    world["predicates"] = canon["predicates"]
    cast = build_cast(premise, world, topics)
    start = premise.start or _opening_hour(cast)
    hour, _, minute = start.partition(":")
    # AND EVERYBODY STANDS WHERE THEIR DAY PUTS THEM. The authored `location`
    # is where the scene finds them, and the gate refuses a pack whose routine
    # disagrees with it -- rightly: two answers to "where is this person when we
    # begin" is no answer. Set from the routine, after the hour is known.
    for character in cast.values():
        character["location"] = _where_at(character, int(hour))
    scenario = {
        "_note": "Generated scenario.",
        "intro": ("%s\n\n%s\n\nAsk the same question of different people and "
                  "compare what comes back. Somebody here has a reason not to "
                  "tell you." % (premise.name, premise.incident.capitalize())),
        "global_seed": premise.seed,
        "world_time": int(hour) * 60 + int(minute or 0),
        "player_start": "place:street",
        "focus_agents": [cast[k]["id"] for k in sorted(cast)][:8],
        "events": [],
    }
    files = {"world.json": world, "topics.json": topics, "canon.json": canon,
             "scenario.json": scenario,
             "initial_state.json": build_initial_state(premise, cast, topics)}
    for filename, character in cast.items():
        files[os.path.join("characters", filename)] = character
    return files


def write(premise: Premise, path: str) -> list:
    """Write the pack. Returns the paths written."""
    written = []
    os.makedirs(os.path.join(path, "characters"), exist_ok=True)
    for filename, data in build(premise).items():
        full = os.path.join(path, filename)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        written.append(full)
    return sorted(written)


# --------------------------------------------------------------- repairing --

def repair(path: str, *, rounds: int = 6) -> dict:
    """Read the gate's report, fix what it names, and go round again.

    Returns `{"rounds": n, "fixed": [...], "left": [...]}`. Stops when the
    report is clean or when a round changes nothing -- a repairer that cannot
    make progress and keeps trying is a hang, and a hang in a build step is
    worse than a failure.
    """
    fixed, left = [], []
    for attempt in range(max(1, rounds)):
        doc = PackDocument.load(path)
        report = authoring_report(doc)
        problems = [f for f in report.get("findings", [])
                    if f.get("level") in ("blocker", "problem")]
        if not problems:
            return {"rounds": attempt, "fixed": fixed, "left": []}
        before = len(problems)
        applied = _apply_fixes(doc, problems)
        left = [f.get("message") for f in problems]
        if not applied:
            break
        doc.save()
        fixed += applied
        if len(applied) == 0 or before == len(problems) and attempt > 0 and not applied:
            break
    doc = PackDocument.load(path)
    report = authoring_report(doc)
    left = [f.get("message") for f in report.get("findings", [])
            if f.get("level") in ("blocker", "problem")]
    return {"rounds": rounds, "fixed": fixed, "left": left}


def _apply_fixes(doc: PackDocument, problems: list) -> list:
    """One pass of repairs. Returns what it changed, in words."""
    applied = []
    places = doc.world.setdefault("places", {})
    street = "place:street" if "place:street" in places else next(iter(places), None)

    for finding in problems:
        message = finding.get("message", "")
        area = finding.get("area")

        if area == "map" and "cannot be walked to" in message:
            # Hang it off the thoroughfare, both ways: a door that opens only
            # outwards is the same defect by another name.
            for pid, attrs in places.items():
                if _label_of(attrs, pid) in message and pid != street:
                    exits = places[street].setdefault("exits", [])
                    if pid not in exits:
                        exits.append(pid)
                    back = attrs.setdefault("exits", [])
                    if street not in back:
                        back.append(street)
                    applied.append("gave %s a way in from %s" % (pid, street))

        elif area == "map" and "has no way out" in message:
            for pid, attrs in places.items():
                if _label_of(attrs, pid) in message:
                    attrs.setdefault("exits", [])
                    if street and street not in attrs["exits"] and pid != street:
                        attrs["exits"].append(street)
                        applied.append("gave %s a way out" % pid)

        elif area == "society" and "never shares a place" in message:
            # Put them on the street in the middle of the day, where everybody
            # else already passes.
            for filename, character in doc.characters.items():
                if character.get("id", "") in message:
                    routine = character.setdefault("routine", [])
                    routine.append({"from": "12:00", "place": street,
                                    "activity": "out"})
                    routine.append({"from": "14:00",
                                    "place": character.get("location") or street,
                                    "activity": "back"})
                    applied.append("gave %s an hour on the street"
                                   % character.get("id"))

        elif area == "topics" and "Nobody in this world can answer" in message:
            topic_id = message.split("'")[1] if "'" in message else None
            topic = next((t for t in doc.topics.get("topics", [])
                          if t.get("id") == topic_id), None)
            if topic and doc.characters:
                who = doc.characters[sorted(doc.characters)[0]].get("id")
                doc.initial_state.setdefault("beliefs", []).append({
                    "agent": who, "proposition": topic.get("query"),
                    "origin_event": "incident:repair",
                    "summary": "Repaired in: somebody has to be able to answer.",
                    "trust": 0.9, "competence": 0.8, "importance": 0.6})
                applied.append("gave %s something to say about %s" % (who, topic_id))

        elif area == "topics" and "no aliases" in message:
            topic_id = message.split("'")[1] if "'" in message else None
            for topic in doc.topics.get("topics", []):
                if topic.get("id") == topic_id:
                    topic["aliases"] = [topic_id.replace("_", " "), topic_id]
                    applied.append("gave %s aliases" % topic_id)

        elif area == "secrets" and "no surface forms" in message:
            for character in doc.characters.values():
                for secret in character.get("secrets") or []:
                    if isinstance(secret, dict) and not secret.get("surface_forms"):
                        secret["surface_forms"] = ["what they saw", "that night"]
                        applied.append("gave %s the words that would give it away"
                                       % secret.get("id"))

        elif area == "secrets" and "guards unknown topic" in message:
            known = [t.get("id") for t in doc.topics.get("topics", [])]
            for character in doc.characters.values():
                for secret in character.get("secrets") or []:
                    if isinstance(secret, dict):
                        guarded = [g for g in secret.get("guards_topics") or []
                                   if g in known]
                        if guarded != secret.get("guards_topics"):
                            secret["guards_topics"] = guarded or known[:1]
                            applied.append("pointed a secret at a topic that exists")
    return applied


def _label_of(attrs: dict, pid: str) -> str:
    return (attrs or {}).get("label") or pid
