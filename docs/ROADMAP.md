# Roadmap

Three documents, three jobs:

| | |
| --- | --- |
| [`CONCEPT.md`](CONCEPT.md) | what exists and has been measured |
| **this file** | what is being built, in what order, and how we know it worked |
| [`VISION_2.0.md`](VISION_2.0.md) | the three-year target picture |

The vision document is a good target and a bad plan: forty-two sections and eight
phases is a multi-year programme, and worked through in its own order it would
produce nothing demonstrable for a long time. This file takes it apart and
sequences it by a single rule:

> **Make an existing claim true before adding a new one.**

Everything the runtime already says about itself should be literally true before
anything new is built on top. That ordering is not conservatism — a system whose
central claim has a hole in it cannot be sold, and every feature added on top of
the hole has to be revisited afterwards.

---

## The finding that sets the order

The runtime says:

> The runtime decides what a character knows, believes, feels, wants and is
> permitted to say. The text layer decides only how it is phrased.

The second sentence was not true. `DialoguePlan` carried `allowed_facts` — a
*list* — and the prompt said "you may reference ONLY these facts". Which of them
reached the player was the model's choice. Because a spoken claim is a real
event that moves other characters' beliefs, the model had a channel into world
state that the architecture does not account for.

Everything in WP1–WP3 exists to close that, and WP2 exists because closing it
makes deception nearly free: once a plan commits to an *exact* proposition, a lie
is simply a commitment whose proposition differs from what the speaker believes.

---

## Work packages

Status is updated as each lands. Each has an acceptance criterion that is a test,
not an opinion.

| | Package | Status |
| --- | --- | --- |
| WP0 | Roadmap and vision documents | **done** |
| WP8 | Enforced layering + architecture map | **done** |
| WP1 | Semantic utterance commitment | **done** |
| WP2 | Deception: belief, intent and utterance separated | **done** |
| WP3 | Semantic back-parser + entity grounding | **done** |
| WP4 | Role-based perception and interpretation | **done** |
| WP5 | Knowledge topology, social graphs, attention budget | **done** |
| WP6 | Retrospective revision (truth maintenance) | **done** |
| WP7 | Memory consolidation, episode to semantic knowledge | **done** |

---

### WP1 — Semantic utterance commitment

**Problem.** The model chooses which licensed fact to state, and therefore
chooses what enters the society.

**Change.** `DialoguePlan` carries exact `semantic_moves`: act, proposition,
polarity, certainty expression, disclosure level. The realizer renders the
commitment; it selects nothing. Where variation is wanted, the *runtime* picks
among valid moves with a derived seed — same variety, full reproducibility, and
the choice lands in the event log.

**Rejected from the vision document:** *Mode B*, in which the model ranks
runtime-offered options. It reintroduces exactly the problem Mode A solves and
gives up semantic determinism to do it. Seeded selection in the runtime is
strictly better: it produces the same unpredictability from the player's side
while remaining replayable.

**Acceptance.** A test in which the provider is replaced by one that tries to
state every fact it can see, and the world state afterwards is identical to the
committed plan.

---

### WP2 — Deception

**Change.** Four states, kept apart: what I believe, what I want, what I say,
what I want you to believe afterwards. A move carries the proposition asserted,
which need not be the speaker's belief. Listeners acquire the *asserted*
proposition with the speaker as origin — so a lie is traceable to its teller
and, later, refutable.

Covers: outright lie, omission, half-truth, exaggeration, understatement.

**Acceptance.** A character who believes ¬p asserts p; the listener acquires p
with that character as origin; the speaker's own belief is unchanged; the record
shows the divergence.

---

### WP3 — Semantic back-parser and entity grounding

**Change.** Generated text is parsed *back* into propositions and compared with
the commitment. A world lexicon lists every entity a world declares; unknown
nouns are classified as decorative, generic, or a potential world invention, and
only the first passes unlicensed.

**Closes** the documented hole: "the old mill by the river" in a world with no
mill.

**Acceptance.** A provider that emits a fluent sentence asserting an uncommitted
proposition is rejected; a provider that says the same committed thing in
different words is accepted.

---

### WP4 — Role-based perception and interpretation

**Problem.** Competence affects only credibility — whether you are believed. It
does not affect perception. A technician and a tourist currently witness an event
identically.

**Change.** Perception becomes five stages: available → attended → recognised →
interpreted → encoded. Competence gates recognition; role and prior belief colour
interpretation. Characters gain structured biography, role, competence and
epistemic profiles.

**Acceptance.** The same event produces demonstrably different claims in
characters of different competence, and the difference is explainable from the
profile.

**Delivered**, with one deliberate omission. Competence, roles, values and an
epistemic profile all exist and all change behaviour. A structured `biography`
was specified in the vision and is **not** built: it would duplicate
`initial_state.json`, which already seeds who knows what and why, and a field
that exists without changing anything is worse than an absent one. Biography
returns as a real feature when it does something `initial_state` cannot —
seeding *dispositions* rather than beliefs.

---

### WP5 — Knowledge topology, social graphs, attention budget

**Rejected:** a single knowledge hierarchy. A street vendor knows more about the
local gang than a corporate director does; rank is not a knowledge ordering.

**Change.** Knowledge is classified on several axes — domain, locality, access
level, network, prerequisite knowledge. Information flows along social networks
with few bridge people rather than through an undifferentiated population. Each
character has a bounded attention budget per period.

**Acceptance.** In a large cast, knowledge stays role-local and network-local
unless a plausible public channel exists, and the bridges are identifiable.

---

### WP6 — Retrospective revision

**Change.** When a source is later exposed, dependent beliefs are recomputed
rather than only the trust being lowered. The dependency graph is built from
provenance that is already recorded; an incremental pass propagates the change
and emits a revision trace.

**Acceptance.** Exposing a fabricator measurably lowers confidence in exactly the
beliefs that rest on their claims, and leaves independently-sourced beliefs
untouched.

---

### WP7 — Memory consolidation

**Problem.** 90% of memory loss is capacity eviction. Old episodes are mostly
deleted rather than compressed, so nothing is learned from them.

**Change.** Repeated episodes consolidate into semantic judgements — "Ben is
unreliable where his own interest is involved" — which survive when the episodes
do not. The judgement keeps pointers to its strongest supporting episodes, so it
stays explainable.

**Acceptance.** After repeated instances, the judgement exists, is retrievable
when the individual episodes are not, and names its evidence.

---

### WP8 — Enforced layering

**Problem.** `unscripted/` is flat with 35+ modules and about to gain several
more.

**Decision.** The layering is *declared and enforced by test*, not by moving
files. 308 internal import lines make a physical reorganisation a large,
error-prone change in the middle of feature work, and the value of folders is
readability while the value of enforcement is that the architecture cannot erode.
Physical subpackages remain available later as a mechanical follow-up.

**Acceptance.** `docs/ARCHITECTURE.md` states the layer map, and a test fails if
a lower layer imports a higher one.

---

## Deferred to the vision, deliberately

Not rejected — sequenced after the above, because each adds per-character state,
and per-character state multiplies save size, snapshot cost and the number of
ways determinism can break.

| | Why deferred |
| --- | --- |
| Recursive theory of mind (2nd order) | first-order exists; second order multiplies state by the cast size |
| Counterfactual reasoning | needs a stable action model first |
| Learned appraisal | authored appraisal is not the bottleneck yet |
| Personality drift | needs long-run data to bound it; unbounded, every character converges |
| Common knowledge | cheap to add once knowledge topology (WP5) exists |
| Institutions and norms | large, and worth doing after roles (WP4) are real |
| Cross-media provenance | valuable and self-contained; a good first post-roadmap item |

## Rejected, with reasons

**Mode B semantic autonomy** — the model ranking runtime-offered plans. Gives up
semantic determinism for variety that seeded runtime selection provides anyway.

**A Rust or C++ core, now.** The adoption barrier is not Python; it is that
nobody has seen a compiled Unreal project. A bundled sidecar process is adequate
for PC, and a rewrite would freeze feature work for months. Revisit for console.

**A single knowledge hierarchy.** See WP5.

---

## WP9 — Contract 2.0 · **done**

Version 1 frozen and still served; version 2 additive under `/v2/`, with
`GET /capabilities` for negotiation. Both are asserted against a live service.
The features built in WP1–WP7 are now reachable from an engine instead of from
Python only.

Deliberately in the contract: what is **not** implemented. `action_bridge` and
`tts` reported `false` and were documented as gaps, so an integrator plans around
them rather than discovering them. The first of the two is now built — see WP10.

## WP10 — The action bridge · **done**

**Problem.** Everything the runtime decided was a belief or a sentence. Movement
was neither: `RoutineEngine` set `agent.location` directly, and nothing ever
asked the engine whether the character got there. A locked door, a cutscene or a
missing nav path produced two worlds — one the player watches, one the simulation
reasons about — and nothing detected the split.

**Change.** With `action_bridge=true`, relocation becomes an exchange. The
runtime issues a typed intent and moves nobody; the engine reports `SUCCEEDED`,
`FAILED`, `INTERRUPTED` or `UNREACHABLE`; only the first changes the world. An
intent nobody answers is closed as `TIMED_OUT` and counted, because a build that
silently times out every intent behaves exactly like a build with no bridge.

**Closed catalogue, one entry.** `MOVE_TO`. `WARN` and `GIVE` are in the vision
and are deliberately not declared: the runtime does not decide them yet, and an
intent type that never fires reads to an integrator as a channel they have to
handle. The catalogue grows when deliberation produces the acts, not before.

**Off by default, and off means unchanged.** A studio with no integration gets
the previous behaviour exactly.

**Acceptance.** Four assertions, all in one test: nobody moves while an intent is
open; confirming every intent lands the cast exactly where the runtime would have
put it itself; a refusal leaves the character where the player can see him; and a
save taken mid-errand still owes the same intents after a load.

## WP11 — Semantic QA · **done**

**Problem.** Golden scenarios prove that a playthrough somebody thought of still
behaves. Nobody writes a test for the leak they did not imagine, and that is the
one that ships.

**Change.** `unscripted qa` searches for the shortest sequence of player actions
that breaks a stated rule, over a closed catalogue derived from the world
itself. Iterative deepening, because the shortest path is the one a player finds
by accident. Four rule types; a finding carries the path, the source chain and
what an author would change.

**The honesty constraint is the design.** A bounded search reports its depth, its
budget, how many sequences it explored and whether the space was exhausted.
`HELD` means "no counterexample in this envelope" and must never be readable as
"impossible".

**What it found on its first run, in 0.1 seconds:** dialogue minted a fresh
origin for every spoken answer, so asking one character the same question twice
counted as two independent witnesses — the central claim, broken in the channel a
player uses most, in the reference pack, with 103 tests passing. Fixed in the
same release, with a regression guard. That is the argument for the tool better
than any description of it.

## Engine work

Deliberately not numbered among the work packages above, because it is a
different kind of work with a different skill set, and because demonstrating a
system whose central claim was not yet true would have demonstrated the wrong
thing. It becomes the priority the moment WP1–WP3 land.

- compile the plugin against a real engine and ship a packaged sample project
- MetaHuman adapter: PAD and discrete emotion onto face curves, with speech,
  emotion, attention and posture on **separate animation channels** so audio
  lip-sync and emotion do not overwrite each other
- ~~an action bridge~~ — **built** (WP10). `MOVE_TO` only; the catalogue grows
  when deliberation decides more than dialogue, flight and mobilisation. The
  plugin side (`PollIntents`, `ReportIntentResult`) is written and, like the rest
  of the C++, now compiles against Unreal 5.8.2 — but has never been run
- TTS adapter, so prosody parameters become a voice
