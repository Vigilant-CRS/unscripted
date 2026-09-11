"""Reading a released sentence back, and checking it against what was committed.

The validator catches proper nouns and numbers a speaker was not licensed to use.
That leaves a documented hole: *"the old mill by the river"* in a world with no
mill contains no proper noun and no number, so it passed. A character asserting
the existence of a thing that does not exist is exactly the failure mode that
makes a language model untrustworthy in an NPC's mouth, and it is invisible to a
capitalisation rule.

Two checks live here, and they are different questions:

**Did the sentence say what it was supposed to?** A commitment that the words did
not carry must not propagate, or the room hears an assertion the player never
read. Answered by looking for the commitment's anchors -- the words a listener
would have to see for the claim to have been made.

**Did the sentence say anything else?** Every referential noun phrase is checked
against the world's own vocabulary. Unknown ones are classified rather than
uniformly rejected, because "the door" is furniture and "the old mill" is a claim
about what exists.

No language model is involved. This is deliberate: a grounding check that needs a
model to work cannot be the thing that makes the model safe.
"""

from __future__ import annotations

import re

#: Words that introduce a referring noun phrase. An unknown noun after one of
#: these asserts that the thing exists; the same noun elsewhere usually does not.
_DETERMINERS = ("the", "a", "an", "that", "this", "those", "these", "his", "her",
                "their", "my", "your", "our", "its")

#: Ordinary furniture of a sentence: nouns that describe rather than assert. A
#: world extends this through `world.json: decorative_vocabulary` -- what counts
#: as scenery is a property of the setting, not of the engine.
GENERIC_NOUNS = frozenset("""
door doors wall walls floor ceiling roof window windows street streets road roads
corner corners room rooms place places thing things man woman men women people
person guy guys kid kids friend friends family night day morning evening
afternoon week weeks month months year years hour hours minute minutes time times
money cash price cost work job business trouble problem problems question
questions answer answers word words name names story stories news rumour rumor
truth lie lies matter matters point points reason reasons way ways side sides
hand hands eye eyes face head foot feet body voice light dark air water food
drink smoke rain cold heat noise sound silence
""".split())

#: Words that end a noun phrase. The head noun is the last word before one of
#: these, which is why "the old mill" is a claim about a mill and not about "old".
_PHRASE_END = frozenset("""
by in on at to of for with from into onto over under near behind beside about
was were is are be been being had has have did does do will would can could
should might must went came saw said told burned closed opened stood sat ran
and or but so then than that which who whom whose when where while because if
""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_TOKEN = re.compile(r"[a-z][a-z'\-]*")


def _looks_verbal(token: str) -> bool:
    """Rough end-of-phrase test for a past participle or gerund.

    English morphology, not a parser. It exists so "a courier dropped" is read as
    a courier and a verb rather than as a thing called a "dropped". Getting this
    slightly wrong costs a deflection, never a leak, because the check only ever
    adds candidates to an already-conservative list.
    """
    return len(token) > 4 and token.endswith(("ed", "ing"))


class WorldLexicon:
    """Every phrase this world answers to, and what it refers to.

    Built once per world and cached, because it is consulted on every released
    line.
    """

    def __init__(self, terms: dict, decorative: frozenset):
        self.terms = terms
        self.decorative = decorative

    @classmethod
    def build(cls, world) -> "WorldLexicon":
        terms: dict = {}

        def add(name, target, kind):
            if not name:
                return
            key = str(name).strip().lower()
            if not key:
                return
            terms.setdefault(key, (kind, target))
            # Index the words of a multi-word name too. "The Harbour Front" is a
            # place, so "harbour" is this world's vocabulary and a character
            # saying it has invented nothing. Without this, every world's own
            # nouns read as inventions the moment they appear on their own.
            parts = [p for p in re.split(r"[\s:_\-]+", key) if len(p) > 3]
            if len(parts) > 1 or key != parts[:1]:
                for part in parts:
                    if part not in _DETERMINERS:
                        terms.setdefault(part, (kind, target))

        for place_id, attrs in (getattr(world, "places", None) or {}).items():
            attrs = attrs or {}
            add(attrs.get("label"), place_id, "place")
            for alias in attrs.get("aliases") or ():
                add(alias, place_id, "place")
        for agent in (getattr(world, "agents", None) or {}).values():
            add(agent.public_name, agent.id, "agent")
            add(agent.objective_name, agent.id, "agent")
            for alias in agent.aliases or ():
                add(alias, agent.id, "agent")
        for entity_id, entity in (getattr(world, "entities", None) or {}).items():
            entity = entity or {}
            add(entity.get("name"), entity_id, "entity")
            for alias in entity.get("aliases") or ():
                add(alias, entity_id, "entity")
            # bare ids read like "item:sealant"; the tail is what people say
            if ":" in str(entity_id):
                add(str(entity_id).split(":", 1)[1].replace("_", " "), entity_id, "entity")
        for topic in (getattr(world, "topics", None) or {}).values():
            for alias in topic.aliases or ():
                add(alias, topic.topic_id, "topic")

        # The predicate catalogue is this world's declared subject matter: if a pack
        # declares `seal_breached`, then "seal" is a thing in that world.
        for predicate in (getattr(world, "predicates", None) or {}):
            for part in re.split(r"[\s:_\-]+", str(predicate).lower()):
                if len(part) > 3:
                    terms.setdefault(part, ("predicate", predicate))

        extra = set(getattr(world, "decorative_vocabulary", None) or ())
        return cls(terms, frozenset(GENERIC_NOUNS | {str(w).lower() for w in extra}))

    def lookup(self, phrase: str):
        return self.terms.get(phrase.strip().lower())

    def longest_match_at(self, tokens: list, index: int, span: int = 4):
        """The longest known phrase starting at `index`, or None."""
        for length in range(min(span, len(tokens) - index), 0, -1):
            phrase = " ".join(tokens[index:index + length])
            hit = self.terms.get(phrase)
            if hit:
                return phrase, hit, length
        return None


def anchors_for(proposition, world) -> list:
    """The words a listener would have to hear for this claim to have been made.

    Slot values give the concrete ones -- a place, a person, an item -- resolved
    through the world's own aliases. That is the honest floor: without naming any
    of the things a proposition is about, a sentence has not asserted it.
    """
    if proposition is None:
        return []
    lexicon = _lexicon(world)
    reverse: dict = {}
    for phrase, (_kind, target) in lexicon.terms.items():
        reverse.setdefault(target, []).append(phrase)

    anchors = []
    for value in (proposition.slots or {}).values():
        value = str(value)
        anchors += reverse.get(value, [])
        tail = value.split(":", 1)[1] if ":" in value else value
        anchors.append(tail.replace("_", " "))
    return sorted({a.lower() for a in anchors if a})


#: Words that make a sentence a denial. Crude on purpose, and it can only ever
#: cost a deflection: this decides whether a released line AGREES with the
#: polarity of what was committed, and a false reading sends the turn to authored
#: text rather than letting an assertion through.
_NEGATIONS = frozenset("""
not no never none nothing nobody nowhere neither nor without
isn't wasn't aren't weren't don't doesn't didn't won't wouldn't shouldn't
can't cannot couldn't hasn't haven't hadn't ain't
denied denies deny refused refuses
""".split())


def _denies(text: str) -> bool:
    return any(token in _NEGATIONS for token in _TOKEN.findall(text.lower()))


def referenced_ids(text: str, world) -> set:
    """Every world id this sentence names, by any word the world answers to.

    Longest-match, so "the back room" resolves once to the place rather than
    twice to two of its words.
    """
    lexicon = _lexicon(world)
    tokens = _TOKEN.findall(text.lower())
    found, index = set(), 0
    while index < len(tokens):
        hit = lexicon.longest_match_at(tokens, index)
        if hit:
            _phrase, (_kind, target), length = hit
            found.add(target)
            index += length
            continue
        index += 1
    return found


def expresses(text: str, proposition, world) -> bool:
    """Would a listener take this sentence to have made that claim?

    Deliberately generous: one anchor is enough. The purpose is to catch a
    sentence that says nothing about the subject at all -- a deflection released
    while the room heard an assertion -- not to grade paraphrase quality. Being
    strict here would reject good writing; being absent lets the simulation and
    the script describe different conversations.
    """
    anchors = anchors_for(proposition, world)
    if not anchors:
        return True                      # nothing to look for; do not block on it
    lowered = f" {text.lower()} "
    if not any(f" {anchor} " in lowered or anchor in lowered for anchor in anchors):
        return False
    # AND IT HAS TO SAY IT THE RIGHT WAY ROUND. Naming the subject is not the
    # same as making the claim: "The clinic was open all night" names the clinic,
    # and the commitment behind it was that the clinic was NOT open. Both halves
    # passed, the player read one thing and the room was told the other, and the
    # simulation and the script were describing different conversations.
    #
    # Generosity is right about paraphrase and wrong about negation, which is the
    # one distinction a listener never misses.
    #
    # WHAT THIS COSTS, STATED RATHER THAN DISCOVERED. English negates lexically
    # as well as grammatically: "the shutters were down" denies that a place was
    # open without using one of these words. So a NEGATED commitment phrased that
    # way reads as disagreement here and the line is replaced by the pack's own
    # deny phrasing -- correct output, and the model's wording lost. A positive
    # commitment is unaffected, which is the common case.
    #
    # The alternative is a heuristic that guesses at lexical negation, and it was
    # tried: comparing the released line against the topic's authored affirm and
    # deny variants scores "The clinic? Shutters were down all night." as
    # AFFIRMATIVE, because the deny variant says "the place" and the affirm one
    # says "the clinic". A wrong answer with more machinery behind it is worse
    # than a conservative one, because it fails in the direction that releases a
    # contradiction rather than the direction that replaces a sentence.
    return (getattr(proposition, "polarity", "+") == "-") == _denies(text)


def unknown_referents(text: str, world, *, licensed: str = "") -> list:
    """Noun phrases that assert the existence of something the world lacks.

    Each is classified rather than uniformly rejected:

    - **decorative** -- ordinary furniture ("the door"). Passes.
    - **licensed** -- named in the commitment or the authored phrasing. Passes.
    - **invented** -- an unknown noun in referring position. This is the "old mill
      by the river" case: it does not exist, and the character just implied it
      does.
    """
    lexicon = _lexicon(world)
    tokens = [t for t in _TOKEN.findall(text.lower())]
    licence = re.sub(r"[:_\-()=,.]+", " ", licensed or "").lower()
    found, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        match = lexicon.longest_match_at(tokens, index)
        if match:
            index += match[2]            # a known thing, however many words long
            continue
        if index > 0 and tokens[index - 1] in _DETERMINERS:
            # Walk to the head of the noun phrase. "the old mill" asserts a mill,
            # not an "old"; flagging the adjective would be both wrong and noisy.
            end = index
            while (end + 1 < len(tokens)
                   # stop AT the head: an ordinary or known noun ends the phrase,
                   # so "the city months ago" is about a city and not about "ago"
                   and tokens[end] not in lexicon.decorative
                   and not lexicon.lookup(tokens[end])
                   and tokens[end + 1] not in _PHRASE_END
                   and tokens[end + 1] not in _DETERMINERS
                   and not _looks_verbal(tokens[end + 1])
                   and not lexicon.longest_match_at(tokens, end + 1)):
                end += 1
            head = tokens[end]
            phrase = " ".join(tokens[index - 1:end + 1])
            if (head not in lexicon.decorative
                    and head not in licence
                    and not lexicon.lookup(head)
                    and len(head) > 2):
                found.append({"kind": "invented_referent", "token": head,
                              "phrase": phrase})
            index = end + 1
            continue
        index += 1

    seen, unique = set(), []
    for entry in found:
        if entry["token"] not in seen:
            seen.add(entry["token"])
            unique.append(entry)
    return unique


def _lexicon(world) -> WorldLexicon:
    """Cached per world. Rebuilt if the world's contents changed underneath us."""
    cached = getattr(world, "_grounding_lexicon", None)
    size = (len(getattr(world, "places", None) or {}),
            len(getattr(world, "agents", None) or {}),
            len(getattr(world, "entities", None) or {}))
    if cached is not None and getattr(world, "_grounding_lexicon_size", None) == size:
        return cached
    lexicon = WorldLexicon.build(world)
    try:
        world._grounding_lexicon = lexicon
        world._grounding_lexicon_size = size
    except Exception:                     # a world that refuses attributes still works
        pass
    return lexicon
