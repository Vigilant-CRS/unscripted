"""Deterministic semantic parser for the terminal reference client.

This is not a chatbot. It maps free player text into a closed command catalog
that the SDK can validate, execute and replay. Studios can replace this module
with a local or cloud parser provider while keeping the same ParsedCommand
contract.

Two vocabularies meet here, and keeping them apart is the point:

- The **command lexicon** (go / ask / threaten / wait ...) belongs to the engine:
  the intent catalog is closed, and the engine ships a default English+German
  lexicon for it. A pack may extend or replace the words via
  ``world.json: command_aliases`` without inventing new intents.
- The **world vocabulary** (place names, character names, what "the medic" means)
  belongs to the pack. It used to live in tables in this file, which meant only
  the reference scene was addressable: a second pack loaded and then could not
  be navigated or talked to. Now it is read from the world.
"""
from __future__ import annotations

import re

from .contracts import ParsedCommand
from .ontology import Proposition


#: Engine-level command words. Packs extend or replace these per intent through
#: ``world.json: {"command_aliases": {"move": [...], ...}}``.
DEFAULT_COMMAND_LEXICON = {
    "quit": ["quit", "exit", "q", "ende", "stop"],
    "help": ["help", "hilfe", "?", "commands"],
    "observe": ["look", "observe", "l", "schau", "umsehen", "umschauen", "sieh dich um"],
    "move": ["go ", "move ", "walk ", "enter ", "gehe ", "geh ", "zu ", "nach "],
    "wait": ["wait", "sleep", "warte", "schlaf"],
    "inspect": ["inspect", "debug", "trace", "untersuche", "zeige"],
    "listen_radio": ["radio", "news", "nachrichten"],
    "attack": ["attack", "hit", "punch", "angreif", "schlag"],
    "threaten": ["threaten", "droh", "intimidat", "warn"],
    "promise": ["promise", "versprech", "pay", "zahl", "give you", "gebe dir"],
    "claim": ["lie", "lueg", "lüg", "claim", "behaupt", "tell"],
    "ask": ["ask", "frage", "frag", "rede", "talk", "speak", "sprich"],
    "accuse": ["accuse", "beschuldig", "confront", "konfront"],
    #: The only thing a player could do TO somebody was hostile or
    #: transactional: threaten, attack, accuse, promise. A runtime about what a
    #: town comes to think of you needs a way to be decent in front of it.
    #:
    #: Called `assist` and not `help`: `help` is already the intent for the
    #: system command, and a second key of the same name in this literal simply
    #: replaced it -- so "help byrne" printed the command list and nobody could
    #: be kind to anybody. Every entry keeps its trailing space so that a bare
    #: "help" is still the command list.
    "assist": ["help ", "assist ", "hilf ", "defend ", "stand up for ", "steh "],
    #: What you turn up wearing. Needed to play the thing at all: appearance was
    #: authored on every character and fixed for the player, so the one person
    #: whose clothes a player could reasonably choose was the one who could not.
    "wear": ["wear ", "put on ", "change into ", "zieh ", "trage "],
}

HELP_TEXT = (
    "Commands: look, go <place>, ask <npc> about <topic>, tell <npc> <claim>, "
    "promise <npc> 300, threaten <npc>, attack <npc>, wait 30, inspect <npc>, quit."
)


def normalize(text: str) -> str:
    low = text.strip().lower()
    low = low.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"\s+", " ", low)


def _contains_any(text: str, words) -> bool:
    return any(w in text for w in words)


class RuleBasedParserProvider:
    module_id = "rule_based_parser"
    version = "2.0.0"

    def __init__(self, command_lexicon: dict | None = None):
        self._lexicon_override = command_lexicon

    # ---- vocabulary, resolved against the loaded world ----
    def _lexicon(self, world) -> dict:
        lexicon = dict(DEFAULT_COMMAND_LEXICON)
        for intent, words in (self._lexicon_override or {}).items():
            lexicon[intent] = list(words)
        for intent, words in (getattr(world, "command_aliases", None) or {}).items():
            lexicon[intent] = list(words)
        return {intent: [normalize(w) if w.strip() == w else w.lower()
                         for w in words]
                for intent, words in lexicon.items()}

    def parse(self, text: str, *, player_id: str, player_location: str, world) -> ParsedCommand:
        raw = text.strip()
        low = normalize(raw)
        lex = self._lexicon(world)

        if not low:
            return ParsedCommand(raw, "noop", 1.0, player_id, reasons=[("parser.empty", 1.0, {})])
        if low in lex["quit"]:
            return ParsedCommand(raw, "quit", 1.0, player_id, reasons=[("parser.system", 1.0, {})])
        if low in lex["help"]:
            return ParsedCommand(raw, "help", 1.0, player_id, metadata={"help": HELP_TEXT},
                                 reasons=[("parser.system", 1.0, {})])
        if low in lex["observe"]:
            return ParsedCommand(raw, "observe", 1.0, player_id,
                                 reasons=[("parser.observe", 1.0, {})])

        if low.startswith(tuple(lex["move"])):
            place = world.place_alias_index().match(low)
            if place:
                return ParsedCommand(raw, "move", 0.95, player_id, location_id=place,
                                     reasons=[("parser.move.place_alias", 0.95, {"place": place})])
            return ParsedCommand(raw, "unknown", 0.2, player_id,
                                 reasons=[("parser.move.no_place", 0.2, {})])

        if low.startswith(tuple(lex["wait"])) or "minute" in low:
            minutes = self._extract_minutes(low) or (
                8 * 60 if _contains_any(low, ("sleep", "schlaf")) else 30)
            return ParsedCommand(raw, "wait", 0.9, player_id, minutes=minutes,
                                 reasons=[("parser.time", 0.9, {"minutes": minutes})])

        if low.startswith(tuple(lex["inspect"])):
            target = self._resolve_agent(low, world, player_location, player_id)
            return ParsedCommand(raw, "inspect", 0.9, player_id, target_id=target,
                                 reasons=[("parser.inspect", 0.9, {"target": target})])

        # A LEADING VERB WINS -- see the long note below, and note that this
        # check has to come BEFORE the radio. It did not, and `listen_radio`
        # matched "radio" or "news" anywhere in the line, so "ask Byrne about the
        # news" switched the radio on instead of asking the newsagent, and "ask
        # him about the radio version" could not be said at all. Same bug as the
        # one below, one line earlier, found by asking a newsstand about the news.
        leading = None
        for intent in ("attack", "threaten", "promise", "claim", "accuse", "assist",
                       "wear", "ask"):
            if low.startswith(tuple(w for w in lex.get(intent, ()) if w.strip())):
                leading = intent
                break

        if leading is None and _contains_any(low, lex["listen_radio"]):
            return ParsedCommand(raw, "listen_radio", 0.85, player_id,
                                 reasons=[("parser.media", 0.85, {})])

        target = self._resolve_agent(low, world, player_location, player_id)
        topic = world.topic_alias_index().match(low)

        # `move`, `wait` and `inspect` above have always
        # matched on the start of the line; the intents below matched anywhere in
        # it, and the inconsistency was a bug with teeth: in a world whose topic
        # is called `market_attack`, "ask Honce about the market attack" contains
        # the word "attack" and was parsed as an assault. Every character in the
        # room mobilised their allies, and the topic could not be asked about at
        # all -- by anyone, ever, in that world.
        #
        # An imperative puts its verb first, so when the line starts with one, it
        # decides. The contains-anywhere pass stays as the fallback, because that
        # is what catches "I want to threaten him".
        def means(intent: str) -> bool:
            if leading is not None:
                return leading == intent
            return _contains_any(low, lex[intent])

        if means("attack"):
            return ParsedCommand(raw, "attack", 0.85, player_id, target_id=target,
                                 reasons=[("parser.attack", 0.85, {"target": target})])

        if means("wear"):
            token = self._match_appearance(low, world)
            return ParsedCommand(raw, "wear", 0.9 if token else 0.3, player_id,
                                 metadata={"garment": token},
                                 reasons=[("parser.wear", 0.9 if token else 0.3,
                                           {"garment": token})])

        if means("assist"):
            return ParsedCommand(raw, "assist", 0.85, player_id, target_id=target,
                                 reasons=[("parser.assist", 0.85, {"target": target})])

        if means("threaten"):
            return ParsedCommand(raw, "threaten", 0.85, player_id, target_id=target,
                                 topic=topic, reasons=[("parser.threat", 0.85, {"target": target})])

        if means("promise"):
            amount = self._extract_amount(low) or "300"
            prop = Proposition("economy:owes_amount",
                               {"debtor": player_id, "creditor": target or "", "amount": amount})
            return ParsedCommand(raw, "promise", 0.9, player_id, target_id=target,
                                 proposition=prop, amount=amount,
                                 reasons=[("parser.promise", 0.9, {"target": target, "amount": amount})])

        if means("claim"):
            prop = self._topic_proposition(world, topic, player_id, "assertion")
            return ParsedCommand(raw, "claim", 0.78, player_id, target_id=target,
                                 proposition=prop, topic=topic,
                                 reasons=[("parser.claim", 0.78, {"target": target, "topic": topic})])

        if means("ask"):
            prop = self._topic_proposition(world, topic, player_id, "claim")
            return ParsedCommand(raw, "ask", 0.86, player_id, target_id=target,
                                 proposition=prop, topic=topic,
                                 reasons=[("parser.ask", 0.86, {"target": target, "topic": topic})])

        if means("accuse"):
            return ParsedCommand(raw, "accuse", 0.78, player_id, target_id=target, topic=topic,
                                 reasons=[("parser.accuse", 0.78, {"target": target})])

        # Fallback: route as ordinary speech to a nearby target if one was named.
        if target:
            return ParsedCommand(raw, "say", 0.55, player_id, target_id=target, topic=topic,
                                 reasons=[("parser.fallback_say", 0.55, {"target": target})])
        return ParsedCommand(raw, "unknown", 0.2, player_id,
                             reasons=[("parser.unknown", 0.2, {})])

    # ---- resolution ----
    def _resolve_agent(self, text: str, world, player_location: str,
                       player_id: str) -> str | None:
        """Named agent first, else the only NPC present.

        The player is excluded by their configured id -- this used to compare
        against the literal string "agent:player_1", so any game that named its
        player differently could address the player as if they were an NPC.
        """
        named = world.agent_alias_index().match(text, exclude=(player_id,))
        if named:
            return named
        nearby = [a.id for a in world.agents.values()
                  if a.id != player_id and a.location == player_location]
        return nearby[0] if len(nearby) == 1 else None

    @staticmethod
    def _topic_proposition(world, topic_id, player_id, kind: str):
        topic = world.topics.get(topic_id) if topic_id else None
        if topic is None:
            return None
        data = (topic.resolved_player_assertion(player_id) if kind == "assertion"
                else topic.resolved_player_claim(player_id))
        return Proposition.from_dict(data) if data else None

    def _match_appearance(self, low, world):
        """Which authored garment the player meant, by its last word.

        Deliberately dumb: `item:red_cyberjacket` answers to "cyberjacket" and
        to its full id, and nothing else. A pack that wants "the red one" adds
        the alias to its reactions table rather than teaching this parser about
        adjectives.
        """
        for token in sorted(getattr(world, "appearance_reactions", None) or ()):
            if token.startswith("_"):
                continue
            tail = token.split(":")[-1].replace("_", " ")
            if token in low or tail in low or tail.split()[-1] in low.split():
                return token
        return None

    @staticmethod
    def _extract_minutes(text: str) -> int | None:
        match = re.search(r"(\d+)\s*(m|min|minute|minutes|minuten|h|hour|hours|stunden)?", text)
        if not match:
            return None
        value = int(match.group(1))
        unit = match.group(2) or "m"
        return value * 60 if unit.startswith(("h", "hour", "stund")) else value

    @staticmethod
    def _extract_amount(text: str) -> str | None:
        match = re.search(r"(\d+)", text)
        return match.group(1) if match else None
