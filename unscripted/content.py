"""Authored world content: topics, secrets and the alias index.

Everything in this module is *content*, not engine. It exists because the
reference scene's vocabulary -- which places connect to which, what "the medic"
refers to, which words would give a secret away -- used to live in Python
constants inside the SDK. That made the runtime look engine-independent while
in practice only one world pack was playable: a second pack loaded, validated
and then could not be navigated or talked to.

The rule this module enforces: **the engine knows the shape of content, never a
particular world's content.** A pack declares its own topology, vocabulary and
secrets; the SDK reads them. Adding a world means writing JSON, not editing
Python, and a pack can be authored in any language because its aliases travel
with it.

Templates may reference the configured player through the ``$player`` token, so
a pack does not hardcode an agent id it cannot know.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PLAYER_TOKEN = "$player"
ADDRESSEE_TOKEN = "$addressee"


def substitute(value, bindings: dict):
    """Recursively replace ``$token`` strings anywhere in authored JSON."""
    if isinstance(value, str):
        return bindings.get(value, value)
    if isinstance(value, dict):
        return {k: substitute(v, bindings) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [substitute(v, bindings) for v in value]
    return value


def resolve_template(template: dict | None, player_id: str, addressee_id: str | None = None):
    """Substitute ``$player`` / ``$addressee`` in an authored template."""
    if not template:
        return None
    bindings = {PLAYER_TOKEN: player_id}
    if addressee_id:
        bindings[ADDRESSEE_TOKEN] = addressee_id
    return substitute(template, bindings)


@dataclass(frozen=True)
class Topic:
    """A subject the player can raise, and what the world does about it.

    ``query`` is the proposition a belief must be relevant to for the NPC to
    consider it an answer. ``player_claim`` is what asking *asserts* -- raising a
    subject is itself information the NPC now holds about the player. ``reactions``
    are authored events the world fires when this topic comes up (asking a gang
    fixer about her hidden brother is a threat to her, and that is a fact about
    this world, not about dialogue systems in general).
    """

    topic_id: str
    label: str = ""
    aliases: tuple = ()
    query: dict | None = None
    player_claim: dict | None = None       # what ASKING about it asserts
    player_assertion: dict | None = None   # what TELLING/claiming it asserts
    reactions: tuple = ()
    #: How a character phrases an answer about this topic, per stance and register:
    #: {"affirm": {"formal": ..., "neutral": ..., "vernacular": ...}, "deny": {...}}.
    #: Without these the engine will not assert anything about this world.
    phrasings: dict = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> "Topic":
        topic_id = data["id"]
        return Topic(
            topic_id=topic_id,
            label=data.get("label") or topic_id,
            aliases=tuple(data.get("aliases") or ()),
            query=data.get("query"),
            player_claim=data.get("player_claim"),
            player_assertion=data.get("player_assertion"),
            reactions=tuple(data.get("reactions") or ()),
            phrasings=dict(data.get("phrasings") or {}),
        )

    def resolved_query(self, player_id: str) -> dict | None:
        return resolve_template(self.query, player_id)

    def resolved_player_claim(self, player_id: str) -> dict | None:
        return resolve_template(self.player_claim, player_id)

    def resolved_player_assertion(self, player_id: str) -> dict | None:
        return resolve_template(self.player_assertion, player_id)

    def phrasing_for(self, affirmed: bool) -> dict:
        """Register variants for affirming or denying this topic's query."""
        return dict(self.phrasings.get("affirm" if affirmed else "deny") or {})

    def resolved_reactions(self, player_id: str, addressee_id: str | None = None) -> list:
        return [resolve_template(r, player_id, addressee_id) for r in self.reactions]


def _protected_ids(entries) -> list:
    """World ids named in the slots of protected propositions, in a stable order."""
    found = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for value in (entry.get("slots") or {}).values():
            token = str(value)
            if ":" in token and token not in found:
                found.append(token)
    return found


def _protected_key(entry):
    """A ``protects`` entry may be a proposition template or an already-canonical key.

    Authors write ``{"predicate": ..., "slots": {...}}`` and the loader canonicalises
    it; making a human type ``pred(a=1,b=2)[None,None,None]`` by hand would be an
    invitation to typo a security control into silence.
    """
    if isinstance(entry, dict):
        from .ontology import Proposition
        return Proposition.from_dict(entry).core_key()
    return entry


@dataclass(frozen=True)
class Secret:
    """Something a character will not say, and the words that would give it away.

    Two labels, deliberately distinct:

    - ``avoid_label`` is the coarse tag handed to the dialogue planner and the
      validator. It names the *shape* of the forbidden area, never its content
      (spec §4.2 Layer 0), so the secret cannot leak by sitting in a prompt.
    - ``guards_topics`` are the conversation topics the holder refuses to discuss
      while trust is below ``min_trust``. This is what turns a secret into
      behaviour rather than a filter.

    ``summary`` exists for authors and the inspector; it is never placed in a
    prompt and never sent to a text provider.

    ``surface_forms`` are the strings the validator scans released text for --
    the last line of defence when an external model writes the line. They belong
    to the pack because they are this world's vocabulary: "back room" is a leak
    in Block 17 and meaningless anywhere else.
    """

    secret_id: str
    avoid_label: str = "protected_topic"
    guards_topics: tuple = ()
    summary: str = ""
    surface_forms: tuple = ()
    protects: tuple = ()          # proposition core_keys / rendered strings covered
    #: Every world id named in a slot of a protected proposition. `protects`
    #: keeps canonical KEYS, which is the right identity for filtering beliefs
    #: and the wrong one for reading a sentence back: a released line that names
    #: the place a secret is about has given it away whatever wording it used.
    #: Empty for a secret declared as a bare string, which has no structure to
    #: read.
    protected_ids: tuple = ()
    about: tuple = ()             # agent ids this secret concerns (drives leverage)
    min_trust: float = 0.45       # below this the holder will not discuss the topic
    #: What the holder says INSTEAD, when they would rather lie than deflect. A
    #: proposition template, so the lie is authored world content like everything
    #: else -- the engine will not invent a cover story any more than it invents a
    #: fact. Without one, a cornered character deflects, which is the honest
    #: default: silence is refusal, and refusal is information.
    cover_story: dict | None = None
    #: How the cover story sounds, per register. A lie needs authored words like
    #: any other assertion -- without them the character has committed to saying
    #: something the text layer cannot express, and nothing is asserted at all.
    cover_phrasings: dict = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict | str, *, owner: str = "") -> "Secret":
        if isinstance(data, str):
            # A bare string names a protected proposition and nothing else. Accepted
            # so a pack can start small, but pack validation warns about it: without
            # surface forms there is no protection against an external model
            # phrasing the secret in its own words.
            return Secret(secret_id=data, protects=(data,))
        return Secret(
            secret_id=data["id"],
            avoid_label=data.get("avoid_label") or "protected_topic",
            guards_topics=tuple(data.get("guards_topics") or ()),
            summary=data.get("summary", ""),
            surface_forms=tuple(data.get("surface_forms") or ()),
            protects=tuple(_protected_key(entry) for entry in (data.get("protects") or ())),
            protected_ids=tuple(_protected_ids(data.get("protects") or ())),
            about=tuple(data.get("about") or ()),
            min_trust=float(data.get("min_trust", 0.45)),
            cover_story=data.get("cover_story"),
            cover_phrasings=dict(data.get("cover_phrasings") or {}),
        )

    def covers(self, proposition_key: str, rendered: str = "") -> bool:
        return proposition_key in self.protects or (bool(rendered) and rendered in self.protects)


@dataclass
class AliasIndex:
    """Longest-match lookup from free text to a world id.

    Longest-first matching matters: "police post" must win over "police", or
    `go police post` resolves to an officer instead of a place.
    """

    entries: list = field(default_factory=list)   # (alias, target_id), longest alias first

    @staticmethod
    def build(alias_map: dict) -> "AliasIndex":
        entries = [(alias.lower(), target)
                   for target, aliases in alias_map.items()
                   for alias in aliases if alias]
        entries.sort(key=lambda pair: (-len(pair[0]), pair[0]))
        return AliasIndex(entries)

    def match(self, text: str, *, exclude=()) -> str | None:
        for alias, target in self.entries:
            if target in exclude:
                continue
            if alias in text:
                return target
        return None

    def conflicts(self) -> list:
        """Aliases claimed by more than one target -- an authoring error."""
        seen, clashes = {}, []
        for alias, target in self.entries:
            if alias in seen and seen[alias] != target:
                clashes.append((alias, seen[alias], target))
            seen.setdefault(alias, target)
        return clashes


def secrets_from(data, *, owner: str = "") -> list:
    return [Secret.from_dict(entry, owner=owner) for entry in (data or [])]


def protected_keys(secrets) -> set:
    keys = set()
    for secret in secrets:
        keys.update(secret.protects)
    return keys


def protected_ids_by_label(secrets) -> dict:
    """avoid-label -> the world ids its secrets are about."""
    table = {}
    for secret in secrets:
        if secret.protected_ids:
            table.setdefault(secret.avoid_label, set()).update(secret.protected_ids)
    return table


def secrets_guarding(secrets, topic_id: str) -> list:
    """Secrets whose holder refuses to discuss this conversation topic."""
    return [s for s in secrets if topic_id in s.guards_topics]


def avoid_labels(secrets) -> list:
    """Coarse labels the dialogue planner may expose. Never contains secret content."""
    seen, out = set(), []
    for secret in secrets:
        if secret.avoid_label not in seen:
            seen.add(secret.avoid_label)
            out.append(secret.avoid_label)
    return out


def surface_forms_by_label(secrets) -> dict:
    """Validator input: avoid-label -> the strings that would give the secret away."""
    forms = {}
    for secret in secrets:
        forms.setdefault(secret.avoid_label, []).extend(secret.surface_forms)
    return forms
