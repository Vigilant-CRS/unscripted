"""Public SDK data contracts.

The reference runtime keeps the deterministic simulation in small internal
modules. This file defines the stable, engine-facing objects a studio should
integrate against: configuration, parser results, event receipts and turn
results. They are deliberately plain dataclasses so the SDK remains dependency
free and easy to bind from other runtimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .ontology import Proposition


#: The SDK's default player agent id. Defined once so nothing else repeats the
#: literal: a game that names its player differently must keep working, and code
#: comparing against a hardcoded copy is exactly how the parser once made the
#: player addressable as an NPC.
DEFAULT_PLAYER_ID = "agent:player_1"

#: The runtime's version, defined once. It is reported to an engine as
#: `runtime_version` over HTTP, so a copy that drifts tells an integrator the
#: wrong thing about which build they are talking to. `unscripted.__version__`,
#: `RuntimeConfig.schema_version` and `pyproject.toml` all resolve here, and a
#: test fails if they ever disagree. Unrelated to `SNAPSHOT_SCHEMA_VERSION`,
#: which versions the save format and moves only when the format does.
RUNTIME_VERSION = "1.21.0"

#: WHO IS PUBLISHING THIS PAGE, as § 5 DDG requires of anyone offering a
#: publicly reachable digital service in Germany. Defined once, because it is
#: repeated on four generated pages and in three files, and an address that
#: drifts in one of them is worse than no address at all -- a test asserts every
#: copy agrees with `IMPRESSUM.md`.
#:
#: THIS IS THE VENDOR'S OWN IDENTIFICATION AND NOTHING ELSE. It goes on the
#: pages Vigilant e.K. publishes: `unscripted pages`, `tour`, `compare`, `quickstart`.
#: It is deliberately NOT emitted by `unscripted serve`: whoever makes that reachable
#: from outside their own machine is the Diensteanbieter for it and owes their
#: own notice, and a library that stamped someone else's company on a licensee's
#: service would be naming the wrong provider on a page they are liable for.
IMPRINT = {
    "company": "Vigilant e.K.",
    "owner": "Damir Dulovic",
    "street": "Königstr. 22",
    "city": "70173 Stuttgart",
    "country": "Deutschland",
    "phone": "+49 (0)711 540 464 08",
    "email": "info@vigilant-crs.de",
    "register": "HRA 726240",
    "register_court": "Amtsgericht Stuttgart",
    "vat_id": "DE 239010954",
}


def imprint_html() -> str:
    """The § 5 DDG provider identification as one HTML block, for a page footer."""
    i = IMPRINT
    return (
        '<p class="imprint"><b>Impressum</b> (Angaben gem&auml;&szlig; &sect;&nbsp;5 DDG): '
        f'{i["company"]}, Inhaber {i["owner"]}, {i["street"]}, {i["city"]}, '
        f'{i["country"]} &middot; Telefon {i["phone"]} &middot; '
        f'<a href="mailto:{i["email"]}">{i["email"]}</a> &middot; '
        f'Handelsregister {i["register"]}, {i["register_court"]} &middot; '
        f'USt-IdNr. {i["vat_id"]}. '
        'Verantwortlich nach &sect;&nbsp;18 Abs.&nbsp;2 MStV: '
        f'{i["owner"]}, Anschrift wie vor.</p>'
    )


#: Where the public finds the product. One source, for the same reason as the
#: imprint: the README, the showcase index, `pyproject.toml` and the YouTube notes
#: all name these, and a test holds every copy to this dict.
LINKS = {
    "source": "https://github.com/Vigilant-CRS/unscripted",
    "pages": "https://vigilant-crs.github.io/unscripted/",
    "video": "https://youtu.be/TfMbbJvjOk0",
}


def links_html() -> str:
    """The video and the source, as one line under the showcase index's lede.

    Plain links: following one is the reader's choice, and the page still loads
    nothing from anywhere -- which is what the Pages workflow asserts.
    """
    return (f'<p class="links"><a href="{LINKS["video"]}">&#9654; Watch the '
            f'seven-minute explanation</a> &middot; '
            f'<a href="{LINKS["source"]}">Source, licence and evidence</a></p>')


#: The mechanics a studio can decline, in one place, so that the command line,
#: the `/capabilities` response and the documentation cannot come to disagree
#: about what exists. Each is a `RuntimeConfig` field that defaults to False, and
#: for each of them off is exactly neutral -- asserted by test, not promised.
OPTIONAL_LAYERS = (
    ("action_bridge",
     "the runtime asks your engine to carry out physical acts and waits to be "
     "told what happened"),
    ("climate",
     "places have a mood -- how candid, how suspicious, how open to a stranger "
     "-- moved by what happens in them and carried between rooms by whoever "
     "walks"),
    ("pursuit",
     "characters act on their goals instead of only moving on routines and "
     "gossiping at random"),
    ("media",
     "a claim can travel by telephone as well as by conversation: fewer "
     "bystanders, more detail lost, weighed a little lower (needs pursuit)"),
    ("notes",
     "somebody who cannot reach the person they needed leaves word where they "
     "stand, and a note is still there afterwards (needs pursuit)"),
    ("promises",
     "a promise comes due and is judged on what the person it was made to came "
     "to believe, moving trust, liking and a reputation for reliability"),
    ("contagion",
     "a little of a speaker's mood moves to whoever they are talking to"),
    ("common_knowledge",
     "track not who knows a thing but who watched everyone else find out; a "
     "secret that is out in the open stops working as one"),
    ("standing",
     "how you treat one person changes how the rest of them treat you -- "
     "carried as a claim, so somebody who was only told about it judges you "
     "too, and judges you less far than somebody who watched"),
)

#: State an engine READS and nothing in the runtime ever WRITES.
#:
#: This runtime has produced the same defect six times: a field consulted by
#: three or four engines that only ever holds what a pack authored, so a studio
#: sets it once and watches it stay there for the life of the world. It cost a
#: measurement to find each time -- `reputation` before the promises layer,
#: then `fear`, `respect`, `appearance`.
#:
#: So the ones that remain are declared here, with the reason, and a test
#: asserts that this list and reality still agree: nothing may be read without
#: either a producer or a line in this table, and nothing may sit in this table
#: that has quietly acquired one.
#:
#: An entry here is a DECISION, not a to-do. Inventing a producer for
#: `dependence` -- which is about needing somebody, not about how they treated
#: you -- would be putting a number where an idea belongs.
AUTHORED_ONLY_FIELDS = {
    "dependence": "how much you need somebody. Read when deciding whether to "
                  "call on them for backup. Authored, because it is about "
                  "obligation and circumstance, not about conduct, and nothing "
                  "in the runtime models either yet.",
    "kinship": "family. A fact about a cast, not a thing play changes.",
    "loyalty": "who somebody is with when it matters. Authored per world; a "
               "faction layer could move it and none does.",
    "favor_debt": "what one character owes another. The promises layer moves "
                  "the player's debts and not theirs to each other.",
    "owes_favor": "the same debt, read from the creditor's side when deciding "
                  "who can be asked for something. Moved by nothing for the "
                  "same reason as favor_debt.",
    "reputation:status": "prestige as this observer sees it, read by "
                         "`social_status`. Conduct moves `decent` and "
                         "appearance moves how somebody is read; neither is "
                         "prestige, and nothing produces prestige.",
}

#: Which layers need another one under them to do anything at all.
LAYER_REQUIRES = {"media": "pursuit", "notes": "pursuit"}


@dataclass
class RuntimeConfig:
    runtime_id: str = "unscripted:main"
    schema_version: str = RUNTIME_VERSION
    world_pack_path: str = "worldpacks/cyberpunk-block"
    storage_path: str = ":memory:"
    debug_traces: bool = True
    strict: bool = True
    player_id: str = DEFAULT_PLAYER_ID
    #: Where the player begins. None means "ask the world pack"
    #: (scenario.json: player_start, else its first declared place) -- the default
    #: used to be a place id from the reference scene, so every other pack started
    #: the player somewhere that did not exist.
    player_start_location: str | None = None
    load_initial_state: bool = True
    population_lod: bool = False   # defer per-tick decay for dormant NPCs (large casts)
    #: Ask the engine to carry out physical acts instead of applying them here.
    #: Off means unchanged: the runtime moves the cast itself, exactly as before,
    #: and `capabilities.action_bridge` reports false. On means a character does
    #: not move until the engine reports that it moved them -- which is the only
    #: way the simulation and the visible world can be known to agree.
    action_bridge: bool = False
    #: World minutes an unanswered intent stays pending before it is TIMED_OUT.
    action_timeout_minutes: int = 60
    #: Voice backend for spoken lines: "none", "espeak-ng" or "piper". The
    #: runtime never synthesises anything itself -- it decides what a line should
    #: sound like and hands that to whatever is installed, which is why this can
    #: exist without the SDK gaining a dependency.
    voice_backend: str = "none"
    #: Model file, for backends that need one (piper).
    voice_model: str | None = None
    #: Ambient dispositions per place -- how candid, how suspicious, how open to
    #: a stranger it is here -- moved by what happens there. Off means every
    #: modifier is exactly neutral and a run reproduces byte-identically, which a
    #: test asserts rather than claims.
    climate: bool = False
    #: Let characters act on their goals during a time advance, instead of only
    #: moving on routines and gossiping at random. Off means the tick is exactly
    #: what it was: diffusion is who happens to talk, pursuit is who has a reason
    #: to, and a world without it goes quiet after saturation -- which is stable
    #: rather than alive, and the evidence run says so.
    pursuit: bool = False
    #: Let a claim travel by something other than a conversation in a room. With
    #: it off every exchange is face to face, exactly as before; with it on,
    #: somebody whose number a character has is a phone call away -- fewer
    #: bystanders, more detail lost, and weighed a little lower. Requires
    #: `pursuit` to have anybody who would place the call.
    media: bool = False
    #: Let a little of a speaker's mood move to whoever they are talking to.
    #: Hatfield, Cacioppo & Rapson (1994): mood converges below the level of
    #: anybody deciding anything. It moves mood only -- never personality, never
    #: the baseline a character relaxes toward. Off means the transfer never
    #: happens and a run reproduces byte-identically.
    contagion: bool = False
    #: Track what is not merely known but PUBLICLY known -- established in front
    #: of a crowd that watched each other find out. Lewis (1969), Aumann (1976),
    #: Chwe (2001). It changes what may be said, never what is believed: a secret
    #: that is common knowledge in a character's own community stops working as a
    #: secret, and nobody passes on what is already common knowledge between them.
    common_knowledge: bool = False
    #: Let what you did to one person change how everybody else treats you. The
    #: act is attached to the world as a claim -- `mistreated(who=..., by=...)`
    #: -- so it is perceived, believed, passed on, doubted and decayed by the
    #: machinery that already exists, and standing moves as far as the hearer
    #: believes it. Off means no such claim is ever attached, nothing is judged,
    #: and a run reproduces byte-identically.
    standing: bool = False
    #: Let a character who cannot reach somebody leave word where they stand.
    #: A note is not a slower phone call: it is still there afterwards, which is
    #: what lets it be found by the wrong person and makes it the runtime's first
    #: piece of evidence rather than testimony. Rides on `media`, because both are
    #: the same claim -- that a message can outrun the room it was spoken in.
    notes: bool = False
    #: Check whether promises were kept. The runtime has taken promises since
    #: the beginning -- parsed, emitted, remembered as commitments -- and nothing
    #: ever resolved one, so undertaking something cost nothing. With this on, a
    #: promise comes due and moves trust, liking and the promiser's reputation
    #: for reliability. Judged on what the person it was made to came to believe,
    #: because this runtime holds no ground truth about whether it happened.
    promises: bool = False
    #: Which characters get resident SQL projections of their beliefs, memories
    #: and mood. The event ledger is authoritative either way; projections exist
    #: so an inspector, a debug HUD or a save-game diagnosis can read state
    #: without replaying. Writing them for everybody is 80% of tick cost in a
    #: large cast (measured), which is a poor trade for characters nobody has met.
    #:
    #:   "all"   every character. Correct for tens of NPCs; the default.
    #:   "focus" the focus agents, the player, and anyone the player has met.
    #:   "none"  ledger only. Smallest and fastest; inspection needs a replay.
    projection_scope: str = "all"
    #: Canon parse-back for EXTERNAL text providers: "strict" rejects an utterance
    #: naming anything the plan did not license (falling back to authored text),
    #: "warn" only records it, "off" disables the check. Deterministic output is
    #: never parse-checked -- it is authored and correct by construction.
    canon_mode: str = "strict"
    #: WHO WRITES THE SENTENCE THAT CARRIES A FACT.
    #:
    #: "controlled" (the default) -- EVERY released line is the pack's own
    #: authored text, and a text provider is not called at all. The guarantee is
    #: then structural rather than checked: the player and the room cannot be
    #: told different things, because the sentence the player reads is the one
    #: the runtime wrote for exactly this claim.
    #:
    #: This used to exempt plans that asserted nothing -- greetings, evasions,
    #: deflections -- on the reasoning that a line carrying no commitment cannot
    #: contradict one. It can: a plan with no facts does not make a model's
    #: answer factually empty, and asked for a greeting a provider is free to
    #: write "He hides behind where drinks are served", an indirect description
    #: of a protected place, released with ACCEPT because the turn had been
    #: classified as carrying no fact. A guarantee that depends on the provider
    #: staying inside its brief is not a guarantee.
    #:
    #: "provider" -- a provider may write the sentence that carries a fact. The
    #: released line is still read back for the secret scan, unlicensed
    #: specifics, invented referents and polarity, and it is replaced when it
    #: does not carry the commitment. That is a real set of checks and it is NOT
    #: a guarantee: they are lexical, and three separate reviews found sentences
    #: that pass all of them and say the opposite of what propagates
    #: ("The clinic was open all night, no doubt." reads as a denial to any
    #: negation-word rule). Choose it knowingly.
    #:
    #: With the built-in deterministic realizer the two modes produce identical
    #: output, because the authored phrasing is what it emits either way.
    semantic_release: str = "controlled"
    capabilities: dict = field(default_factory=lambda: {
        "semantic_parser": "BUILTIN",
        "text_realizer": "BUILTIN",
        "dialogue_validation": "BUILTIN",
        "storage": "BUILTIN",
        "inspector": "BUILTIN",
    })
    text_realizer: dict = field(default_factory=lambda: {
        "provider": "template",
        "endpoint": None,
        "api_key": None,
        "model_id": "deterministic-template",
        "timeout": 20.0,
        #: Milliseconds a turn may wait for a model before using authored text.
        #: A warm local 4B answers in ~300 ms, which is past any frame budget, so
        #: the default is to answer now and offer the model's line as an upgrade.
        "latency_budget_ms": 120,
        #: Keep generating past the budget and expose the result via
        #: poll_line_upgrades(). Off means a slow model is simply skipped.
        "deferred": True,
        #: Page the model into VRAM at load time. A cold local model costs 7-25 s
        #: on its first call, and that lands on whoever the player talks to first.
        "warm_up": True,
        #: Check at startup whether this model can voice NPCs at all.
        "probe": True,
    })

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedCommand:
    raw_text: str
    intent: str
    confidence: float
    actor_id: str
    target_id: Optional[str] = None
    location_id: Optional[str] = None
    proposition: Optional[Proposition] = None
    amount: Optional[str] = None
    minutes: int = 0
    topic: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        data = asdict(self)
        data["proposition"] = self.proposition.as_dict() if self.proposition else None
        return data


@dataclass
class EventReceipt:
    event_id: int
    event_type: str
    world_time: int
    observed_by: list = field(default_factory=list)
    reasons: dict = field(default_factory=dict)


@dataclass
class CapabilityPlan:
    resolved: dict
    warnings: list[str] = field(default_factory=list)


@dataclass
class SnapshotId:
    value: str


@dataclass
class ReplayStep:
    command: str
    world_time: int
    message: str
    trace_hash: str


@dataclass
class ReplayResult:
    replay_id: str
    steps: list[ReplayStep]
    final_world_time: int


@dataclass
class DialogueResponse:
    speaker_id: str
    text: str
    act: str
    verdict: str
    utility: float
    reasons: list = field(default_factory=list)
    style: dict = field(default_factory=dict)


@dataclass
class TurnResult:
    world_time: int
    location_id: str
    parsed: ParsedCommand
    message: str
    observations: list = field(default_factory=list)
    receipts: list = field(default_factory=list)
    npc_response: Optional[DialogueResponse] = None
    developer_trace: str = ""
    done: bool = False

    def as_dict(self) -> dict:
        data = asdict(self)
        data["parsed"] = self.parsed.as_dict()
        return data


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str, path: str = ""):
        self.issues.append(ValidationIssue(severity, code, message, path))
        if severity == "error":
            self.ok = False
