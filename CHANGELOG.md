# Changelog

All notable changes to Unscripted.

## [Unreleased]

### Changed

- **The project is now called Unscripted.** `Living Worlds` and `Living Worlds
  Runtime` are retired as names for it, together with the `lwr` module, the `lwr`
  command and the `LivingWorlds*` types in the engine plugins. The reason is
  trademark exposure rather than taste: a name that has to be defended costs more
  than it earns, and this one sits close to marks already in use.

  The product is **Unscripted**, the category is **Persistent World & Social
  Memory Runtime**, and **Vigilant e.K.** is the publisher rather than half the
  product name. `Vigilant` is itself well occupied in the software classes, so it
  stays where a company name belongs: beside the product, not inside it.

  What moved: the Python package `lwr` → `unscripted`; the console scripts `lwr`
  and `lwr-play` → `unscripted` and `unscripted-play`; the distribution
  `living-worlds-runtime` → `unscripted`, which also moves the installed data
  from `share/living-worlds-runtime/` to `share/unscripted/`; the Unity package
  `com.vigilant.livingworlds` → `com.vigilant.unscripted`; the Unreal plugin
  `LivingWorldsBridge` → `UnscriptedBridge`; the Godot addon `living_worlds` →
  `unscripted`; and the bundle `lwr.pyz` → `unscripted.pyz`.

  **The environment variables move too**, and they are part of the public
  surface: `LWR_AUTH_TOKEN` → `UNSCRIPTED_AUTH_TOKEN`, `LWR_URL` →
  `UNSCRIPTED_URL`, `LWR_TOKEN` → `UNSCRIPTED_TOKEN`, and the tooling's
  `LWR_GODOT`, `LWR_DOTNET` and `LWR_PORT_ROOT` likewise. A deployment that sets
  the old names loses its token. On a non-loopback bind that fails loudly —
  `service.py` refuses to start without either a token or `--allow-insecure-bind`
  — but on loopback it comes up unauthenticated and says nothing. Worth grepping
  a CI config for.

  **The C++ port keeps a short prefix of its own.** `lwr_`, `LWR_`, `Lwr` and the
  `lwr/` include tree become `usc_`, `USC_`, `Usc` and `usc/`. A C ABI spelled
  `unscripted_get_state` would be unusable; SQLite ships as SQLite with a
  `sqlite3_` ABI for the same reason. **This breaks anyone linking the port**,
  which is the one part of this change that is not cosmetic.

  The licence goes to **1.3** — the terms are unchanged, but § 3(a) now requires
  a different attribution string, and two files both calling themselves 1.2 with
  different obligations would be worse than a version number.

  Commits published before this one keep the old name in their blobs, and so do
  clones of them. That is the same decision as the address change below, for the
  same reason: rewriting the history across two remotes would break every
  existing clone to achieve a scrub that forks and caches defeat anyway.

  **Existing save files still load.** The state envelope's `format` marker is
  now `unscripted-state`, and `lwr-state` is accepted on read and rewritten under
  the new marker — in Python and in the C++ port, which are checked against each
  other. Refusing an old save would have been a rename that ate people's games.

  **Two runtime values carried the old name and had to move with it**, which
  makes this more than a rename for one case. The default `global_seed` is now
  `unscripted-seed-0` (was `lwr-seed-0`) and `runtime_id` is `unscripted:main`
  (was `lwr:main`). The seed feeds `derive_seed`, so **a world pack that does
  not declare its own `global_seed` will simulate differently after this
  change.** All six shipped packs declare one, so no shipped result and no
  sealed figure moves; a third-party pack that relied on the default must pin
  `"global_seed": "lwr-seed-0"` to keep its old runs reproducible. Leaving the
  literals alone was the alternative and it was worse: the retired name would
  have gone on appearing in every save file and every world fingerprint.

  **The sealed evidence run is unaffected.** Its digests derive from world, agent
  and event data and never from the package name, so every figure quoted here
  still describes commit `7f90ef6` — recorded, as the dossiers now say, under the
  previous name.

- **The sealed evidence run is redone and sealed to `7f90ef6`.** The previous one
  described `36bf7097`, and `belief.py`, `memory.py`, `runtime.py` and
  `revision.py` had all changed since — `belief.py` three times over five external
  reviews, ending with an origin index that never evicts. A seal describing code
  that no longer exists is worth nothing.

  Two hours, four packs, 36 cases: 35 held, 1 untestable in the world given, none
  failed. **3,253,190 turns, 82,278 simulated days, 65,061 invariant checks, 0
  violations**, every optional layer off.

  **It is slower than the run it replaces, and every quoted figure moved down.**
  3,560,466 turns, then 3,282,740 (−7.8%), now 3,253,190 (−0.90%); simulated days
  and invariant sweeps fell with it, which is a per-tick cost rather than noise.
  The non-evicting origin index is the likely source: it does strictly more
  bookkeeping per hearing than the version that threw entries away. Recorded in
  three places rather than quietly replaced, because a number that only ever
  improves is a number nobody measured.

Requoted everywhere it appears: `README.md`, `docs/SPECIFICATION.md`,
`docs/CONCEPT.md`, `evidence/README.md` and `unscripted/pursuit.py`, which
quotes the dossier in its own docstring. `docs/CONCEPT.md` had been carrying
figures from a run older than either seal (3,791,879 turns / 95,926 days) and
now agrees with the others.

### Added

- **`IMPRESSUM.md`** and a § 5 DDG provider identification in the footer of every
  page Vigilant e.K. publishes itself (`unscripted pages`, `tour`, `compare`,
  `quickstart`, `viz`). One source of truth in `contracts.IMPRINT`, with a test
  that the address cannot drift between the five pages and four files it appears
  in, that every field § 5 DDG names is present, and that no imprint links the EU
  ODR platform, which closed on 20 July 2025.

  `unscripted serve` deliberately emits **no** imprint. Whoever makes it publicly
  reachable is the Diensteanbieter for that instance and owes their own notice; a
  library that stamped its vendor onto a licensee's page would name the wrong
  provider. `docs/INTEGRATION.md` says so where somebody deploying it will read it.
- **`docs/COMMERCIAL.md`** — the licence model and the price list assessed against
  what comparable middleware actually charges, what a buyer's legal review will
  object to, and what this will realistically earn, which is less than the price
  table suggests.

- **The cost argument, next to the price table.** Every price is paid once, for a
  product's lifetime, at any player count -- against a hosted AI-NPC service whose
  bill scales with success and never ends. Six figures a year at a million players
  versus one licence fee is the comparison a studio's finance department makes,
  and it was in `docs/COMMERCIAL.md` as a recommendation instead of in the README
  where a buyer reads it. With it: no player text leaves the machine unless a
  provider is attached, so there is no processor agreement to negotiate; and
  nothing here is an AI system under the EU AI Act, so those obligations attach to
  whatever model a studio adds and not to this.

### Changed

- The contact address is now **info@vigilant-crs.de** and the company web address
  **vigilant-crs.de**, replacing the previous ones throughout: `IMPRESSUM.md`,
  `LICENSE`, `README.md`, `pyproject.toml`, `contracts.IMPRINT`, the Unity
  package manifest and the Godot demo's end card.

  Commits published before this one keep the previous address in their blobs,
  and so do any clones of them. That is deliberate: it is a business contact
  address that was published on purpose, not a credential, and rewriting 184
  commits across two remotes would break every existing clone to achieve a scrub
  that forks and caches would defeat anyway. Keep the old address forwarding for
  a while instead — a licence file in someone's checkout is exactly the kind of
  copy that outlives a domain.
- The README and the showcase index link the seven-minute video and the public
  repository, and the README links the showcase. The addresses live in one place,
  `contracts.LINKS`, beside the imprint, and the imprint test holds every copy —
  README, `pyproject.toml`, `docs/YOUTUBE.md` and the generated index — to it. The
  Pages workflow's self-containment check refused any `href` to another site,
  which would have refused a link; it now refuses what a page could actually load
  — `src`, stylesheets, `@import`, `fetch`, `XMLHttpRequest`, `WebSocket` — which
  is what it was written to protect.

### Fixed

- **`unscripted new` produced a pack with no `world_id`.** Every shipped pack declares
  one; a pack an author had just scaffolded did not, so the first world a new
  customer built started on the pre-`world_id` compatibility path and its own
  saves came back `world_unverified` instead of `ok`. The onboarding path is the
  one that most needs an identity, because a new pack gets renamed, copied and
  forked long before anybody thinks about save compatibility.
- `LICENSE` § 3 was lettered a, b, c, f, d, e. The items keep their reading order;
  the letters now run a to f.
- **The liar in Lamb Street had stopped lying.** Asked at the door, Reyes answered
  *"I've got nothing for you."* instead of her authored cover story, and the
  avatar packet still said `honesty: lie` — a tell on a sentence that asserted
  nothing, in the one scene built around a lie. Found by re-recording the demo,
  not by the suite.

  The validator refuses a line that names what a secret is about unless the plan
  licensed it, and the authored phrasing for the answer is part of that licence.
  But the licence compared ids, and a phrasing names things in the world's own
  words: "Nobody came past this door" never matched `place:club_door`, so every
  cover story about its own subject refused itself. Since 1.18.0, when that check
  arrived, her lie never reached the world; since 1.20.0, when a refused line
  stopped being re-released under another act name, she stopped saying it too.

  What the phrasing names is now read with the same lexicon as the line, in
  Python and in the C++ port. The licence belongs to the phrasing, not to the
  sentence: the same words under a plan that did not author them are still
  refused. And `honesty` is taken only from what was said, so a deflection that
  replaced a cover story is no longer labelled a lie. The noir test had asserted
  the label and nothing else, which is how this passed for three releases; it now
  asserts the sentence and that it was spoken, a new test covers both directions,
  and the engine probe plays the scene in both implementations — with the C++ fix
  removed it fails in 11 fields.
- **The Pages workflow could not build the film, and had not since 1.17.0.**
  `unscripted pages --with-film` and `unscripted film` defaulted the narrator to
  espeak-ng and its voice to `af_heart` — a kokoro voice. espeak-ng was asked for
  a voice it does not have, on every machine, and the workflow runs exactly the
  default command, so it stopped at the first line of narration. Each default was
  reasonable on its own; nothing tested them together. The voice now defaults to
  the backend's own, `af_heart` only for kokoro, resolved in one place for both
  commands, and a test parses the real defaults and renders a line with them.
  Found by building the pages the way CI does before the first push.
- The film's caption on the showcase index gave its length a minute too long
  whenever the seconds ran past thirty: the minutes were rounded rather than
  floored, so a 2:41 film was captioned 3:41 directly under a player saying 2:41.
- The showcase index left two empty cells of its card grid painted grey whenever
  the window was wide enough for four columns. The dividing lines are now drawn
  by each card, so an empty cell is page background at any width.

## [1.21.0] - 2026-09-08

A fifth review read `3c4524d`, re-ran the whole suite green, and still found two
counterexamples -- both reproduced against the compiled C++ headers as well as
Python. Both are closed, and the first one is closed differently in kind from the
three attempts before it.

### Changed

- **The origin index no longer evicts.** At capacity a *new* origin is refused:
  worth exactly zero, counted in `Belief.origins_refused`. An origin already in
  the index always counts up. `origins_forgotten` and `unrecognised_spent` are
  gone with the designs that needed them.

  Three earlier versions bounded the index by evicting and correcting for it, and
  every one leaked, because **an index that forgets cannot recognise a repeat**:
  evicting outright let a source return at full weight (2.94 twice against a 3.27
  ceiling); charging a re-admission `rho` bounded one return and not the series
  (0.950 -> 0.99985 over twenty cycles); and charging all re-admissions from one
  shared `rho/(1-rho)` allowance leaked twice more -- it did not count the repeats
  already paid while the origin was still recognised, and a re-admitted origin was
  back *in* the index, so its next hearing took the `rho ** heard` branch and
  skipped the allowance entirely (6.18 log-odds after a hundred cycles).

  Not evicting makes `max_origin_contribution()` a theorem rather than a policy:
  the n-th hearing is worth `rho^(n-1)` for every n, so the total is a geometric
  series under `1/(1-rho)` for any ordering, across save and load. The cost is
  stated rather than hidden -- at capacity a genuinely new source is over-doubted,
  and `origins_refused` says how often that happened.
- **A line the runtime chose to release is reported as released.** The
  safety/quality split left the verdict behind: from the fourth identical question
  onward `_deliver` released the line and told the room while returning
  `REJECT_SOFT` with an empty `accepted_output` in the audit, so a client that
  hides rejected answers would show the player nothing the room had just heard.
  The release decision is now made once and recorded once -- verdict, text,
  emission and audit together. `Runtime.say` already did this; the SDK path is now
  the same contract.

### Notes

- Belief serialisation replaces two fields with one (`origins_refused`); an older
  save reads back as 0, which is what a belief that has refused nothing carries.
- The saturation claim is now checked as a *property*: twelve random orderings
  over 575 origins, with a save and a load mid-run, compared against an eight-line
  reference model. Every earlier version of this check asked one hand-written
  sequence, which is how three bounds shipped narrowed.

## [1.20.0] - 2026-09-08

A fourth review read `fd76623` and found five ways the guarantees still came
apart -- three of them on the runtime's own side, with no provider involved at
all. The pattern across all four reviews is the same and worth naming: each
earlier fix narrowed a failure class without closing it, because each was a new
*check*. These change what has to be true.

### Changed

- **`semantic_release="controlled"` now writes EVERY line, and does not call a
  text provider at all.** It used to exempt plans that assert nothing --
  greetings, evasions, deflections -- on the reasoning that a line carrying no
  commitment cannot contradict one. It can: a plan with no facts does not make a
  model's answer factually empty. Asked for a greeting, a provider wrote *"He
  hides behind where drinks are served"* -- an indirect description of a
  protected place -- and it was released with `ACCEPT` because the turn had been
  classified as carrying no fact. A guarantee that depends on the provider
  staying inside its brief is not a guarantee. `"provider"` is unchanged.
- **Nothing is committed that the answer cannot say.** Selection picks up to two
  propositions; a pack authors one phrasing per *topic*, and it words one thing.
  A character who knew both "the clinic was shut last night" and "the clinic is
  open today" said the first and taught the room both. Factual moves with no
  authored wording are now dropped from the commitment and reported as
  `commitment.unsayable_dropped`.
- **Style chooses between wordings; it never removes a claim.** The
  mean-sentence-length pressure cut *"Listen carefully. Place was shut that
  night."* to `"Listen carefully."` for an agitated speaker while the claim still
  propagated. Shortening is skipped for any line carrying a fact, and
  `TemplateRealizer.variants()` gives the anti-repeat retry a choice between
  *complete* realizations of the same commitment.
- **A rejection is two different answers.** `validator.SAFETY_CODES` and
  `is_unsafe()` separate them. An unsafe line voids its commitment and deflects
  -- and now also clears `plan.phrasing`, without which the "deflection" released
  the same sentence again under a different act name. A repetition is a *quality*
  objection: the runtime tries another complete wording (`dialogue.reworded`) or
  says it again (`dialogue.released_anyway`). Conflating the two let arbitrary
  earlier prose decide whether a later, fully controlled fact entered the society
  at all.
- **The source ceiling is global again.** Treating an unrecognised source as a
  first repeat bounded what *one* re-admission is worth, not what a sequence of
  them is worth: cycling `origin_limit` uninformative sources through a belief
  evicts the informative one again, and its next repetition starts a fresh
  geometric series. Twenty cycles took a belief from 0.950 to 0.99985 on no new
  evidence at all, at 8.83 log-odds against a 3.27 ceiling. `Belief` now carries
  `unrecognised_spent`: everything it cannot recognise draws on ONE allowance of
  `rho/(1-rho)` of a hearing. Twenty cycles now end at p=0.9623 and 3.23888
  log-odds with the last cycle worth exactly 0. The cost, stated rather than
  hidden: past `origin_limit` a genuinely new source is over-doubted.
- **A world says what it is.** All six shipped packs declare `world_id` in
  `scenario.json`. The pre-`world_id` compatibility path needs a character who is
  not the player: raising its bar from one shared place name to two only moved
  the coincidence, and `place:spawn` plus `place:street` jumped a noir clock from
  1200 to 4334. An inferred match now reports `world_unverified` rather than
  `ok`, so a loader can refuse it.

### Fixed

- `TemplateRealizer.expressed_commitment` asked *was there a template* rather
  than *did these words carry the commitment*. A factual plan realised from a
  stance template -- because the pack authored no phrasing for it -- reported the
  commitment as expressed.

### Notes

- Snapshot schema stays at 11: `unrecognised_spent` reads back as 0.0 from an
  older save, which is what a belief that has forgotten nothing carries anyway.
- Conformance fixtures regenerated for the new belief field and the declared
  world ids; no other field moved.

## [1.19.0] - 2026-09-08

Three independent reviews read this runtime and between them found thirty
defects that a green suite had not. This release closes them. Nothing here is a
feature: it is the difference between the guarantees being described and being
kept.

### Changed

- **`semantic_release` decides who writes a sentence that carries a fact, and
  defaults to `"controlled"`.** The runtime's own authored phrasing is released
  for anything that asserts something; a text provider writes only lines that
  assert nothing. The guarantee becomes structural instead of checked -- the
  player and the room cannot be told different things, because the sentence the
  player reads is the one written for exactly this claim. Set it to `"provider"`
  to let a model write factual lines, knowing that the checks are lexical: three
  reviews found sentences that pass all of them and say the opposite of what
  propagates. With the built-in realizer the two modes are identical.
- **A forgotten source is never fresh again.** Bounding the per-belief source
  index (added the day before) let an evicted origin return at full weight: one
  claim contributed 2.94, was evicted, and its bare repetition contributed 2.94
  again -- against a documented ceiling of 3.27 -- taking a belief from 0.95 to
  0.997 on nothing but repetition. A belief that has forgotten anything now
  treats every unrecognised source as one it has heard before, which can only
  lower the weight of evidence and never raise it.
- **A provider failure costs the wording, not the content.** A thrown provider
  released the authored line and voided the commitment, so the model's failure
  mode decided what the society knew.
- **Snapshots carry a ledger watermark that a reload cannot rewind**, and
  `Store.ledger_up_to` is gone. It filtered on the event id, which `restore`
  rewinds, so the history "as of snapshot A" answered A, and later A and B. Use
  `Store.ledger_as_of(watermark)`.
- **World identity is declared, not inferred.** `scenario.json: world_id` is
  believed when both sides carry it. Without it a save is refused unless it
  shares a character who is not the player, or more than one place -- one shared
  id is always a coincidence somewhere, and both `agent:player_1` and a room
  called `place:spawn` proved it.
- **Snapshot schema 11.** Older saves still load; every new field has a
  documented fallback.

### Fixed

- Evidence pools follow what the evidence did to the log-odds, not how it was
  asserted; `revision` recomputes from a cumulative ledger that is not trimmed
  with the inspector's record, and each pool loses what it was given rather than
  gaining a contradiction out of nothing.
- One liar telling one lie is one source; one incident restated is one
  judgement, and a second act is still a second incident.
- Memory stores what the observer understood, keeps `about` and `evidence`
  across a reload, and retrieval is a seeded draw rather than a threshold
  wearing a probability's clothes.
- The tick walks its window in order, so who witnessed an event no longer
  depends on how large a step the caller took.
- One speech path: `Runtime.say()` puts what was said into the world.
- Theory of mind no longer reads the actor's own fear as the other person's
  fear of them; OCC's prospect pair is the right way round; publics carry
  polarity; an origin must name a whole id.
- Imports are atomic, the ledger appends, and `/demo` and `/studio` no longer
  hand out the bearer token they embed.
- The native JSON parser refuses malformed documents instead of inventing
  plausible ones, and a surrogate pair becomes one character.

### Known limits

Named in `reviews/2026-09-08/STATUS.md` rather than left to be discovered:
lexical secret protection is not semantic protection, `kappa` below 0.5 means
"reliable liar" and no pack says whether it means to, and an origin re-admitted
after eviction costs a bounded amount of extra weight.


## [1.18.0] - 2026-08-31

### Added
- **The world fits in the game's own save file.** `GET /v2/state/export`,
  `POST /v2/state/inspect`, `POST /v2/state/import`, and `export_state()` /
  `inspect_state()` / `import_state()` on the SDK. One JSON blob, ~11 kB gzipped
  for eight characters. A save written before the studio patched the cast still
  loads, naming who was restored, dropped and left at their authored state --
  because a patch is not a corruption.
- **A game can launch the runtime itself.** `--port 0`, `--announce FILE`
  (written atomically once *listening*), `--parent-pid` (exit when the game
  does, including when it crashes), SIGTERM handled so a clean stop is clean.
  Plus `integrations/godot/addons/unscripted/UnscriptedHost.gd`.
- **Promises (`promises`, off by default).** The runtime had taken promises
  since the beginning and never resolved one, so breaking your word was free --
  and better than free, since making a promise granted +0.35 trust on the spot.
  Now a promise comes due and moves trust, liking and a reputation for
  reliability. `POST /v2/promises/{id}/settle` is the authoritative path; left
  alone the runtime judges on whether the promisee came to believe it.
- **`agent.reputation` is populated for the first time.** It was empty in every
  world at every time, and `unscripted/sociolinguistics.py` reads it. The missing piece
  was never `ReputationEngine` -- it was the thing that resolves a promise.

- **`unscripted bundle`** — the whole runtime as one ~340 kB file any Python 3.10+
  runs. No pip, no virtualenv, no install step. Only possible because the SDK
  has no third-party dependencies. It does **not** remove the interpreter: for a
  player with no Python, pair it with an embedded one, which has not been done
  here.
- **Social identity is wired.** `IdentityEngine.salience` weighs four terms and
  one of them, `w_threat`, was multiplied by zero in every world since it was
  written. Attack a keeper in front of another keeper and her `keeper` salience
  rises 0.832 → 0.902, halving back over a day. Fires on *witnessing*; a retold
  attack does not, and a test pins that limit.
- **`InterpersonalEngine` is no longer constructed**, with the reason written on
  the class. A test now fails if the runtime builds any engine nothing calls.

### Fixed
- **A tick reported only its last event.** `process_event` replaced
  `last_traces` rather than accumulating, so a week of world time reported
  `climate.moved: 0` and `common_knowledge.established: 0` from layers that
  demonstrably worked. `routine.perform_move` also discarded what
  `climate.carried` returned, so the mood really did travel between rooms and no
  trace ever showed it.
- The world-pack validator crashed with a traceback on a JSON array where a
  mapping belongs, which is the commonest first mistake.
- `--world-pack` had three different conventions across the subcommands.
- A misspelled body field (`{"txt": ...}`) returned 200 and ran an empty turn.

## [1.17.0] - 2026-08-28

### Added
- **Emotional contagion (`contagion`, off by default).** A little of a speaker's
  mood moves to whoever they are talking to, damped by the listener's emotional
  stability and weighted by how well they know the speaker. Hatfield, Cacioppo &
  Rapson (1994). It moves mood only, never personality, and is capped per
  exchange so a chain of conversations converges instead of running away.
- **Common knowledge (`common_knowledge`, off by default).** The runtime tracked
  who holds a belief; it now also tracks who watched everybody else find out.
  Lewis (1969), Aumann (1976) and Chwe (*Rational Ritual*, 2001): common
  knowledge is made by a public moment, not by a headcount, so a broadcast or a
  claim made in the open in front of a crowd establishes it and a phone call
  never can. Two consequences, both about what may be **said** rather than what
  is believed: a secret that is out in the open stops working as a secret, and
  nobody passes on what both parties already watched a crowd find out. Publicity
  is explicitly not evidence — a test asserts that establishing a public moves no
  confidence.
- **Notes (`notes`, off by default).** A character who cannot reach the person
  they needed leaves word where they stand. Unlike every other channel a note is
  still there afterwards, so it can be found by somebody it was not written for.
  What it says is fixed when it is written, not when it is read. Over a week of
  `market-square`: 84 written, 41 delivered, 28 read by the wrong person, 11
  never collected — and with telephones in the world, none, because the person
  you want is usually in your contacts.
- **`GET /v2/state/public`.** What is out in the open, and what is lying unread
  in a room. Deliberately not a debug endpoint: nothing it returns is private.
- **`--layers` on `unscripted serve` and `unscripted demo`.** Seven optional mechanics had
  accumulated as `RuntimeConfig` fields reachable only from Python, while the
  entry point the documentation gives an integrator is `unscripted serve` — so none of
  them could be switched on from the documented entry point. `--layers
  pursuit,notes` turns them on, `--explain-layers` says what each one does, a
  misspelling is an error rather than a shrug, and an unmet dependency (`notes`
  without `pursuit`) is refused with the reason. One declaration in
  `contracts.OPTIONAL_LAYERS` feeds the command line, `/capabilities` and the
  documentation, and a test asserts all three agree.
- **`/capabilities` now reports every optional layer**, not only the action
  bridge. Off and "this build does not have it" looked identical from outside.
- **Kokoro as a voice backend.** 24 kHz and by a distance the best intonation of
  the three. Reached the same way as `espeak-ng` and `piper` -- a name on PATH --
  so the SDK still installs with no third-party packages.

## [1.16.0]

### Added — `unscripted/medium.py`: how something was said is part of what was said

A person-to-person claim was one undifferentiated act: A told B. But the same two
people telling each other the same thing face to face and over a phone are
different events. Daft & Lengel's media richness theory (1986) is the usual
framing — leaner media carry less per exchange — and here it reduces to three
numbers that land on machinery that already existed rather than a parallel one:

| | lands on |
| --- | --- |
| `fidelity` | the levelling Allport & Postman measured, already in `unscripted/distortion.py` |
| `audience` | the earshot that decides who overhears |
| `trust_factor` | the assertion strength a listener weighs |

Measured over five simulated days on `market-square`: **a claim passed in person
loses a detail 11% of the time; the same claim by phone loses one 21% of the
time.** Nobody overhears a call, which is why a call is where a secret goes.

**Who can reach whom** is the other half. A room is who is standing in it; a
phone is who has your number. A character may declare `contacts`, and where a
pack has not said, familiarity above a threshold stands in — stated as the
default it is rather than presented as a finding. Somebody you do not know
cannot be rung, which is what stops a world with phones from having no geography
left.

The phone is a **fallback, not a preference**: a character goes to whoever is
standing there unless somebody they trust noticeably more is elsewhere. A first
draft ranked every contact in the world against the room and turned five days
into ninety-eight calls and thirty-four conversations, which is not a market
square.

### Added — `docs/INTEGRATION.md`

What you install, what it costs, what it needs from you, and what it will not do:
the API, running with a local model or with none at all, the measured costs, the
four optional layers with what each one costs you, and the honest list of what it
does not do. Including the sentence that matters most — **the integration is not
the API, it is deciding which of your gameplay events become world events.**

### Changed

- `store.diffusion_events()` carries the medium, so a debug HUD can tell a
  conversation from a phone call and explain why one of them lost a detail.
- Tests: 116 → 117.

## [1.15.0]

### Added — `unscripted/pursuit.py`: somebody wants something, so somebody does something

The evidence run has said this since it was first written, and it was the most
damning line in the repository:

> After saturation, little happens. The rumours are through the population within
> days, everyone becomes a stifler, and **the world goes quiet.**

The cause was in the tick. Scheduled events fire, routines move people, diffusion
rolls dice over who happens to be standing together, everyone decays, factions
escalate — and **nothing ever asked what anybody wanted.** Characters have carried
goals like *not be arrested for this* since the first world pack, and no time
advance ever consulted one.

**Diffusion is who happens to talk. Pursuit is who has a reason to.**

Measured on `market-square`, thirty simulated days:

| | days 0–2 | days 27–29 |
| --- | --- | --- |
| without pursuit | 54 conversations | **0** |
| with pursuit | 96 | **90** |

- A character acts on their strongest goal at most every few hours, picks the
  belief that bears on it, and says it to the person present they trust most.
  Not the nearest, not a random draw.
- A goal says what it is about with `"about": [...]`. Without it the words of the
  goal are used — and *"not be arrested for this"* shares nothing with
  `killed_by(who=person:councillor, by=group:eastside)`, which is how the first
  run of this layer produced a town full of motivated people and no
  conversations at all.
- **It invents no channel.** A pursued conversation is an ordinary claim event
  with the ordinary earshot, provenance, distortion and hop count, so twenty days
  of extra traffic still leaves every belief sourced and a single-origin claim at
  0.84. A layer that manufactures talk could quietly walk a rumour to certainty;
  a test asserts this one does not.
- **Off by default.** A studio that wants a quiet world gets one.

### Changed

- `DiffusionEngine.tell_about()` — the public half of the telling path, so a
  purposeful speaker supplies the topic and everything after it is the same code
  the random path runs. A purposeful conversation must not become a second kind
  of conversation.
- Snapshot schema 6 → 7.
- `docs/CONCEPT.md` records the finding and its answer, and names what is still
  missing: a director that writes its own incidents.
- Tests: 115 → 116.

## [1.14.0]

### Added — `unscripted/climate.py`: weather, not personality

The runtime has always said that traits are fixed — relationships move, who
somebody is does not — and that stays true, because a personality that drifts
under play converges every character on the same one. What it left unmodelled was
not personality but **weather**: a square in which somebody has just been
threatened is a different place to ask questions in, for everybody, and nobody's
character has changed.

Three numbers per place: `candour` (how readily what is known here gets passed
on), `suspicion` (how much a claim is discounted for coming from outside), and
`openness` (how readily a stranger is spoken to at all). They land on four
numbers the runtime already computed — **how often people talk, which is the
speed of the thing; how sure they must be before passing something on; how much
a claim persuades; and how far a stranger gets.** Nothing new was invented to
receive them.

- **It spreads by traffic, not by the clock.** Somebody walking out of a room
  takes its mood with them, capped so a shift change cannot import a district. An
  earlier draft drifted each place toward its neighbours on a timer: the same
  picture, the wrong model — two rooms joined by a door nobody uses would have
  converged anyway.
- **It relaxes**, halfway back to the authored baseline every thirty world hours,
  so one bad afternoon does not mark a world permanently.
- **A pack may author it** with `"climate": {...}` on a place; otherwise it is
  derived from `gossip_factor`, `surveillance_level` and `privacy_level`, so
  existing worlds get a sensible one without being touched.
- `sdk.climate_report()` says where it is tense and how far that is from normal.

**Off by default, and off is exactly neutral.** Every modifier is `+0.0` or
`×1.0`; a test asserts that, that an enabled run actually differs, that the square
closes and recovers, that the mood travels with the traffic — and that no trait
moved.

Measured on `market-square`: threatening and attacking the trader takes the
square's openness from 0.605 to 0.305. After twenty-four hours and seven walks
the bar, the alley, the precinct and the radio station have all moved from their
baselines, none of them further than the square.

### Changed

- Snapshot schema 5 → 6: the weather is state, and a load that dropped it would
  quietly undo what a player did to a room.
- Tests: 114 → 115.

## [1.13.0]

**The demo stopped explaining the system and started telling a story.**

Read cold, the film described a mechanism. A viewer with two minutes needs to be
told what goes wrong today, what this makes possible, and *why anybody would want
it* — and the example has to carry that rather than illustrate it afterwards.

### Added — `worldpacks/market-square`

A councillor is shot in the open street in front of the market stalls. City Radio
has the story first: **it was the east-side kids.** It was not. Yara had a stall
two metres away and saw three men who did not run and did not panic — and she is
not listening to the radio, because she was standing in it.

Measured after twelve simulated hours: **eight people hold the radio's version,
five hold the witness's**, the strongest of them Yara at 0.83, and the killing is
a *contested* claim. Nobody authored that split. It falls out of who was listening
to the channel and who walks past whose stall.

- Seven characters, one radio channel, per-person attention from 0.9 down to
  Yara's 0.05.
- The councillor's aide holds the truth and offers the radio's version as a cover
  story — a lie the runtime records with her name on it.
- A test fails if the pack ever stops producing two answers, or if the witness
  stops being the surest person in the world about what she saw.

### Changed — the engine demo shows two answers, in two colours

Amber is what the radio said; green is what the witness saw. A viewer works out
which is which in about four seconds and never needs it explained again. A
character holding both at once gets a mark of its own, because that is the state
a single truth value cannot represent.

The demo now ends by **leaning on the witness**: threatening her costs 0.30 of
her trust, and asked the same question again she gives a shorter answer — the
same woman, the same fact, one clause fewer, because of something the player did.
Every player ends up in a slightly different world, and that is the mechanism.

### Fixed — three real defects

- **The narration talked over itself.** Lines were laid at constant offsets over
  a scene with constant beats, so any line longer than a beat overlapped the next
  one: six of sixteen did, by as much as 3.4 seconds. The picture is now cut to
  the voice — the recorder speaks first, measures, and tells the engine how long
  to hold each beat.
- **The flag column showed the runtime's sentence.** A boolean has one line per
  fact and gives it to everybody in the same words, however they asked; printing
  the generated line there quietly credited flags with something they did not do.
  It now says what it actually has: *the one line this fact has, to anyone,
  always.*
- **The recorder reserved a port two minutes before using it**, and lost the race
  to whatever took it during synthesis. It also discarded the service's output,
  turning a one-line cause into twenty minutes of guessing.

### Changed

- Piper's synthesis timeout: 30s → 180s. A high-quality voice runs at about
  0.05× real time, which was fine until the lines got long enough to be worth
  listening to.
- Tests: 113 → 114.

## [1.12.0]

**The demo stopped showing states and started showing the process.**

The engine demo drew one snapshot per beat, held for four seconds. It was
accurate and it was dead: what is worth seeing here is not a state but a claim
*leaving a mouth, crossing a room and arriving*, and snapshots sample exactly
that away.

### Changed — the engine demo moves

- **Sixteen simulated hours run before any question is asked.** People walk their
  routines between rooms, interpolated, and the block talks without anybody
  scripting the conversations.
- **A claim in flight is a pulse** that travels the line between two characters
  and lands with a flash on the listener. A retelling that changed on the way is
  a different colour.
- **What lands stays as a thread.** The threads accumulate into the provenance
  web the runtime has been keeping all along — and **switching to FLAGS makes
  every one of them vanish.** Not a flourish: a boolean has nowhere to keep them,
  and that is the clearest single frame in the whole argument.
- **A gauge around each character** shows how sure they are, because "believes
  it" and "is sure of it" are different states and a fill alone cannot separate
  them at a glance.
- A live panel of *who told whom*, filling as it happens.

### Added — names are pronounced the way the world says they are

Piper read "Okada" as OH-kay-da and "Honce" as HONSS-ee. On a page that does not
matter; spoken over a video for a studio it is the first thing anybody notices.

A character may now declare `"voice": {"say_as": "..."}` in the world pack,
because how a name is said is a fact about the world and not about this runtime.
The respelling is applied to the text handed to the synthesiser and **nowhere
else** — the world, the transcript and every log keep the spelling.

### Changed

- Best available voice throughout: piper `en_US-lessac-high`.
- The Godot flag model gained `which_version`, which the panel had been asking
  about while the model had no method for it. A test now fails if any of the
  three "nowhere to put it" answers ever starts answering — a comparison whose
  weaker side quietly improves is not the comparison being claimed.

## [1.11.0]

### Added — the same events, twice, inside a game engine

A studio's next question after the tables is whether any of it survives contact
with an engine. `integrations/godot/UnscriptedDemo` is a Godot 4.3 project
talking HTTP to a running `unscripted serve`: the district, the cast, who knows
what and on whose word, all drawn from `/v2/state/knowledge` and
`/v2/avatar/turn`.

Same district, same question, two answers. Ask the officer about the attack and
the flag model says **yes** — the channel fired, the boolean is set. The runtime
says **no, never heard it**: he was not listening to that channel, and there is
nowhere in a boolean to record that he was not.

- **`Flags.gd`, fifteen lines**, the GDScript twin of `unscripted/flat.py`. Not a straw
  man: a set of booleans is how most shipped games hold what characters know.
- **Two phases.** Everything is fetched first and played back second, so the
  demo does not render while it waits on HTTP — the slow machine is the one it
  will be shown on — and a recording of it is deterministic.
- **No assets.** Rooms, characters and panels are `_draw()` calls: no licences to
  track, and a schematic that is clearly designed reads as engineering.
- **No fallback.** With no service running it says so and stops.
- `tools/godot_demo.py` starts the service, records through Godot's Movie Maker
  mode at a fixed timestep, lays the narration at computed offsets and writes a
  79-second MP4, mastered to −16 LUFS.

### Fixed — a parser defect the demo found on its first run

`ask Honce about the market attack` was parsed as an **assault**. `move`, `wait`
and `inspect` had always matched on the start of the line; every other intent
matched anywhere in it, and in a world whose topic is called `market_attack` that
made the topic unaskable by anyone, ever — every question about it mobilised the
room's allies.

An imperative puts its verb first, so a leading verb now decides. The
contains-anywhere pass stays as the fallback, because that is what catches "I
want to threaten him".

### Fixed

- A film beat whose window contained no rendered still asked for a picture that
  was never taken. It now holds the nearest one — which is what sampling frames
  always implied.
- The Godot client's `advance()` emitted `knowledge` on its own while the caller
  also asked for it, so the demo consumed two beats per answer and silently
  played back five of its eight steps.
- Two narration lines were missing against the demo's seventeen half-beats:
  twelve seconds of video playing in silence, which reads as a broken product
  rather than a broken edit. A test now checks the two files agree.

### Changed

- Best available voice: piper `en_US-lessac-high`, with a breath between beats
  and one loudness pass over the finished track rather than per line.
- Tests: 111 → 113.

## [1.10.0]

**The demo stopped being a demonstration and became an argument.**

Read cold, the previous film failed four of the five questions a viewer with
forty seconds actually has. It never said what goes wrong today, what this
replaces, how it works, or who it is for. It was a beautiful showing of a
mechanism *to somebody who already knew why the mechanism mattered* — which is
everybody except the person deciding.

### Added — `unscripted/flat.py`: flags, implemented honestly

A set of booleans, about eighty lines, in the repository next to the thing it is
compared against. **Not a competitor and not a straw man**: it is the
representation most shipped games use for what characters know, and it is not
stupid — it is fast, it saves and loads, and every designer understands it.

### Added — `compare.html`: the same events, twice, both columns computed

The recording is made once; its transmissions are played through the flag model;
both sides answer the same ten questions from their own state. Nothing is written
by hand — including the row about exposing a liar, which had been the one
sentence a sceptical reader would have checked first and is now an actual
`discredit()` on an actual session.

Where a boolean holds nothing, the row says **"nowhere to put it"** rather than
"worse" — a property of the representation, not a judgement about anybody's
engineering. And **two rows go to the flags**: one bit per character against
76 KB, a set lookup against a read model. A comparison nobody can lose is a
comparison nobody believes, and a test fails if those rows disappear.

### Changed — the film is five acts, not one

The problem, in the words a studio uses about it · what this is, in one sentence
· **the same events twice** · the run itself · why it can be trusted and who it
is for. Two and a half minutes, and the middle act is the one the whole thing
exists for.

- **Title cards**, addressed by `#frame=k` like every other page here, so the
  still-shooting path does not need to know the difference between a sentence and
  a simulation.
- **A better narrator.** piper is wired through the same voice adapter; it sounds
  far better than espeak-ng and cannot change pitch, which a narrator does not
  need. `--narrator piper --narrator-model voice.onnx`.
- One player script (`DEFAULT_FILM_SCRIPT`) now drives the film, the comparison
  and the showcase pages, so they tell one story rather than three slightly
  different ones.

### Fixed

- The flag column counted the player, reporting nine knowers in a world of eight.
- `2 piece(s) of evidence` and `4 belief(s)` — fine on a page, clumsy when a
  synthesiser reads them aloud, which this text now is.
- Only the first character who never heard the claim was named; it lists them.
- Title cards fell back to a serif: `font:` shorthand without a size is invalid
  CSS. A nuisance on a page, the entire frame on a title card.

### Changed

- Tests: 110 → 111.

## [1.9.0]

### Added — `unscripted film`

A page animates, and a page is a thing somebody has to be persuaded to open. A
video is a thing they watch because it was in front of them, and it is the form a
studio forwards to three colleagues.

```
unscripted film --at "3:ask Honce about the attack" --out unscripted.mp4
```

Forty-five seconds, 1600×900, H.264 and AAC, from one command.

- **No screen is recorded.** There is no display on the machines this runs on.
  The page already deep-links a moment — `#frame=120&paused` — so each frame is
  fetched as a still and the stills are assembled afterwards. Frames are rendered
  in parallel because the page is a pure function of its hash fragment, which is
  the same property that makes the recording reproducible.
- **The picture is cut to the voice, not to a frame rate.** A beat that speaks
  for eight seconds spreads its frames over eight seconds; one that speaks for
  two nearly holds still. That is what a person does with a scrubber, and it is
  the difference between a video and a slideshow with a voiceover on top.
- **The narration is generated from the chapters the runtime found in its own
  run**, so a video cannot describe a moment the recording does not contain, and
  re-running it after the world changes produces a video about the new world.
- `unscripted pages --with-film` puts it on the index; the deploy fails if it did not
  build.

Stated plainly on the page: the voice is a speech synthesiser, the cuts are hard,
and there is no music. It is an honest forty-five seconds, reproducible from one
command.

### Fixed

- Chapter text said "the station" and "the intercom" — one pack's furniture,
  wrong in a harbour, a village or a city block, and *read aloud* by the film,
  where a wrong noun is louder still. The default role fell back to "crew" for
  the same reason.

### Changed

- Tests: 109 → 110.

## [1.8.0]

### Changed — the evidence is sealed to the code that produced it

The two-hour dossier in `evidence/` predated the sealing feature and could not
name its commit. Replaced by a run that does: `696e6d9f8135`, clean tree, Python
3.14.4, two hours, 36 cases across four packs, **all held** — 3.25 million turns,
82,525 simulated days, 65,083 invariant checks without a violation.

Replaced rather than kept alongside. Two dossiers of which only one is
attributable invites somebody to quote the other.

Its headline figures were recomputed rather than carried over: forgetting is 91%
eviction against 9% decay (24.5M / 2.5M), and 78 retellings and 92 beliefs
acquired across those 82,525 days — the long case demonstrates **stability, not
liveliness**, and the README says so.

## [1.7.0]

### Added — a voice, planned by the runtime and rendered by whatever you have

Prosody has been emitted on every spoken line since the MetaHuman adapter was
written — rate, pitch and loudness derived from the speaker's affect — and
nothing consumed it. `capabilities.tts` reported false while the interesting half
of the problem was already solved and sitting unused.

```
unscripted voice --say "threaten Mr. Okada" --backend espeak-ng
```

- **The runtime plans; a backend renders.** The emotional movement composes with
  a per-character base voice, so a frightened character reads faster and higher
  and still sounds like himself. Voices are derived from the character id rather
  than drawn at random: a voice that changes between sessions is a continuity bug
  a player notices before any belief state. A world pack can author one instead.
- **Nothing is bundled, and that is the point.** Every practical Python TTS pulls
  in onnxruntime or torch; the dependency-free install is worth more than a
  bundled voice, and a studio with its own pipeline wants the plan and none of
  the rendering.
- **What a backend cannot do is stated.** `espeak-ng` honours rate, pitch and
  loudness and sounds robotic; `piper` sounds far better and has no pitch control
  at all, which costs an emotional read half its signal. `describe()` and the CLI
  say which, per line.
- `capabilities.tts` is configuration *and* installation — a build that names a
  backend it cannot run would have an integrator wiring up audio that never
  arrives.

### Changed — the map is for people who have not read the ontology

The recording page was accurate and hard to read. It now leads with the claim in
plain language (*"Station net: a seal failed in Stores during the night cycle"*)
and keeps the predicate underneath, and **chapter buttons, computed from the
recording itself**, jump to the moments worth seeing: one person knows, the
intercom says it, it starts moving, it changes on the way, everyone holds it, and
nobody remembers who told them. A five-day run is 240 frames and asking a viewer
to find the interesting thirty seconds with a slider is asking them to leave.

- **Contradiction is drawn.** A character holding evidence both ways is not the
  same as one who has not heard, and the map now separates them.
- **Speech bubbles** at the moment of telling, so you see *what* is said.
- The legend sits under the map, where the eye already is.

### Fixed

- **A label that contradicted itself two lines apart.** `diffusion.stifled` was
  rendered as "says nothing to X — they already knew". It is the opposite: they
  *did* tell, the listener already knew, and the teller stops carrying it — the
  stifler that makes a rumour die out. The ticker showed the same pair telling
  and staying silent in the same breath.
- The reason trace can log one speaker/listener pair more than once inside a
  window; the ticker showed it twice, so a viewer counted two events where the
  world had one.

## [1.6.0]

### Added — `unscripted viz`

Everything else here answers a question in text. What makes this runtime worth
having is a *process* — people move, meet, tell each other things, get them
slightly wrong, decline to pass them on, and forget the afternoon while keeping
the conclusion — and a process wants a picture that moves.

```
unscripted viz --at "4:ask Voss about breach" --out spread.html
```

One self-contained page that plays back a real run, frame by frame:

- **where everyone is** — routines, so you watch the cast actually meet;
- **what they believe** — confidence in one tracked claim, as colour;
- **who told whom** — a pulse along the edge at the moment it happened, with the
  hop count;
- **who got a different version** — and what changed on the way;
- **who said nothing** — the refusals, which are half the behaviour: *"Tan says
  nothing to Rask — they already knew"*;
- **who lied** — read out of the runtime's reason trace, never inferred from the
  sentence, with a mark that stays on the liar;
- **what they can still recall** — the episode fading under a belief that does
  not. On the reference run, by day four all ten still hold it at 0.66 and **not
  one of them can recall being told.**

A caption under the map names the moment in a sentence, so the page narrates
itself for a screen recording. `#frame=120&paused` deep-links a moment, because
the interesting thirty seconds of a five-day run are hard to find by scrubbing.

**It is a recording, and a test holds it to that**: the same seed produces a
byte-identical recording, the page carries the recording it draws so the two can
be compared, and it fetches nothing.

### Changed

- The map says "holds a different version **from the rest**" rather than implying
  a wrong one. In the deception recording the majority version *is* the lie, and
  the one character holding something else is the only one telling the truth — a
  label that called him wrong would have been backwards in exactly the scene the
  page exists to show.
- Tests: 106 → 107.

## [1.5.0]

### Added — `unscripted tour`

Six scenes, run live, written to one self-contained HTML page and a voiceover
script generated from the same run. For the thing a studio asks for that a README
cannot be: *show me*.

```
unscripted tour --out tour.html --script narration.md
```

**No invented opponent.** Building a deliberately weak "traditional NPC" to beat
is the oldest dishonest move in technical marketing and anyone reading closely
can tell, so each scene is set against one of exactly two things, and says which:

- **the model's own recorded attempt** — for the secret scene, the "before" is
  literally what the language model tried to say, raw output and released line,
  both recorded at the time in the evidence run. If no recorded model run is
  present, that scene is **empty** rather than illustrated with something
  reconstructed, and a test asserts it.
- **a structural absence** — "a store that keeps one number per fact has nothing
  to discount by" is a statement about a data structure, not a claim about
  anybody's product.

Every scene prints the command that reproduces it, and every scene states a
conclusion the data on it actually supports: the discredit scene now carries a
caveat saying which half of its claim its own table does *not* show.

The narration is generated rather than written, because a hand-written script
drifts from the figures on screen within one release — and then somebody records
a video saying 0.9 while the page says 0.506. A test asserts every figure on the
page appears in the script, and that the script names what is not built.

### Fixed

- **The evidence README overstated a count.** "Across 128 questions under
  pressure, threat and bribery: 0 leaks" — the run recorded 96 under pressure
  (48 per pack) and a further 96 in cross-examination. 128 came from neither.
  Corrected, with both figures and what each measures.

### Changed

- Tests: 105 → 106.

## [1.4.0]

A tool that looks for the failure nobody wrote a test for, and the failure it
found on its first run.

### Added — `unscripted qa`

A golden scenario proves that a playthrough *somebody thought of* still behaves.
That is the wrong shape for what studios actually ship: nobody writes a test for
the leak they did not imagine. `unscripted qa` asks the opposite question — *is
there ANY way the player can bring this about?* — and answers it by searching.

```
unscripted qa qa/relay-station.json
```

- Iterative deepening over a **closed catalogue of player actions derived from
  the world itself** — every candidate names a character, place or topic the pack
  declares, so the search cannot invent an affordance the game does not have.
  Deepening rather than depth-first, because a designer needs the *shortest*
  path: the shortest is the one a player finds by accident.
- Four rule types, each a question an author asks anyway: `never_believed`,
  `max_independent_sources`, `provenance_complete`, `never_spoken`.
- A finding carries the path, who ended up believing what, **the source chain
  that got it there**, and what an author would change. A finding without a
  source chain is an opinion.
- **`HELD` is not a proof, and says so.** Every verdict carries the depth, the
  budget, how many sequences were explored and whether the space was exhausted.
  A bounded search that let "nothing found" read as "impossible" would be worse
  than no search at all.
- Exit code 2 on a violation, so it gates a build the way a test does.

This is possible here for a reason a prompt-driven NPC system cannot copy: the
runtime is deterministic and its state is inspectable, so a rule is checked
against the *world* rather than against a string, and the same seed replays from
the start as often as the search needs.

### Fixed — asking one person twice was two witnesses

**The tool found this on its first run, in the reference pack, in 0.1 seconds.**

The origin travels with the claim, not with the mouth it came out of — a rumour
relayed through five people is one witness. The diffusion layer had followed that
rule since it was written. **Dialogue had not.** Every spoken answer minted
`said_<speaker>_<time>` as its origin, so asking one character the same question
twice produced two independent origins and the runtime counted its own repetition
as corroboration. The channel a player uses most was the one breaking the central
claim, and nothing caught it: the benchmark measures *relayed* beliefs, not the
player's.

A spoken claim now inherits the origin of the speaker's own belief. **A lie does
not** — a lie has no evidential ancestor, the claim genuinely begins with the
speaker, and `said_<speaker>_<time>` is the literal truth about where it came
from. Traceability is unaffected either way: provenance records the speaker
separately, which is what `discredit` matches on.

Measured on the same four questions that exposed it: one origin instead of three,
and the player's confidence moves from 0.504 to 0.506 instead of 0.504 to 0.569.

### Fixed — one incident had two origins in the reference pack

`relay-station` seeded Voss with an incident report and broadcast the same
breach over the station net under a *different* `origin_event`. One incident,
two authored ids, so hearing both counted as independent corroboration of
itself. Both now carry `incident:store_seal_night`. An authoring defect rather
than an engine one — and exactly the class of defect `unscripted qa` exists to
surface.

### Changed

- Tests: 103 → 105, including a regression guard for the dialogue-origin defect
  and a test that the search finds a planted break in the minimum number of
  actions.

## [1.3.0]

The runtime stops assuming that what it decided is what the player saw.

### Added — the action bridge

Everything the runtime decided was a belief or a sentence. Movement was neither:
`RoutineEngine` set `agent.location` at 12:00 because the schedule said the mess
hall, and nothing ever asked the engine whether anyone had walked there. A locked
door, a cutscene or a missing nav path left two worlds running — one the player
watches, one the simulation reasons about — and nothing detected the split,
because nothing was ever asked.

- **`GET /v2/actions/pending`** — typed intents the runtime is asking the engine
  to carry out, with `params`, the `reason` in plain language, and `expires_at`.
  The character has **not** moved; he is at `params.from` until the engine
  answers.
- **`POST /v2/actions/{intent_id}/result`** — `SUCCEEDED`, `FAILED`,
  `INTERRUPTED` or `UNREACHABLE`. Only the first changes the world; the rest
  record that the act did not happen and leave the character where the player
  last saw him. A status outside the four is a 400 rather than a guess, and a
  second result for one intent is a 404.
- **`TIMED_OUT`** — the runtime's own fifth result, for an intent nobody answers
  within its window. Treated as a failure and *counted*, because a build that
  silently times out every intent behaves exactly like a build with no bridge
  attached, and looks like one too until you read `bridge.timed_out`.
- **Closed catalogue, one entry: `MOVE_TO`.** `WARN` and `GIVE` are in the
  roadmap and are deliberately not declared. The runtime does not decide them
  yet, and an intent type that never fires reads to an integrator as a channel
  they have to handle.
- **Off by default, and off means unchanged.** With `action_bridge=false` the
  runtime moves the cast itself exactly as before and issues nothing. Asserted,
  not asserted-to: confirming every intent lands the cast in *identical*
  locations to a run with the bridge switched off.
- `UUnscriptedSubsystem::PollIntents` and `::ReportIntentResult` on the Unreal
  side, with `OnActionIntent` broadcast once per intent — polling every tick
  during a thirty-second walk must not restart that walk thirty times a second.
  Like the rest of the C++, it has not been compiled here.
- `capabilities.action_bridge` is now *configuration* rather than a constant. It
  reports whether this build was started with the bridge on, because "no intents
  pending" and "this build never issues any" look identical on the wire.

### Fixed

- **The contract named a method that never existed.** `contract.json` said
  `GET /avatar/face` is called by `UUnscriptedNpcComponent::TickFace`; the
  class has `TickComponent`. The field tests asserted the contract's *shapes* and
  nobody checked its prose, so an integration point a studio could look up was a
  paragraph. A test now asserts every `called_by` names a method that is both
  declared in a header and defined in a `.cpp` — twelve call sites.

### Changed

- **Snapshot schema 4 → 5.** A save now carries the intents the engine still owes
  an answer for; without them a load silently drops a character's errand. Saves
  written by 1.2.0 and earlier are reported as a version mismatch on restore
  rather than being read as if the field had always been absent.
- Tests: 101 → 103.

## [1.2.0]

Two bodies of work. A hardening pass against the v1.1.0 implementation review,
and then the roadmap that pass made possible: the text layer stopped being able
to decide what enters the society. Every entry under the review-pass headings
fixes a defect the 30-test suite passed over, because it only ever exercised the
reference world pack.

The release rule was one line — **make an existing claim true before adding a new
one.** The runtime said "the text layer decides only how it is phrased" while
`DialoguePlan` handed the model a *list* of facts and let it pick. WP1–WP3 close
that; everything after builds on the closed version.

### Added — semantics before text (WP1–WP3)

- **Semantic utterance commitment.** A plan carries exact `semantic_moves` — act,
  proposition, polarity, certainty, disclosure level. The realizer renders the
  commitment and selects nothing. Where variation is wanted the *runtime* picks
  among valid moves with a derived seed, so variety survives without giving up
  replay.
- **Deception.** Belief, intent, utterance and intended effect are four separate
  states. A speaker who believes ¬p can assert p; the listener acquires p with
  that speaker as origin, the speaker's own belief is untouched, and the record
  shows the divergence. Covers the lie, the omission, the half-truth, the
  exaggeration and the understatement.
- **Semantic back-parser and entity grounding.** Generated text is parsed back
  into propositions and compared with the commitment. A world lexicon declares
  every entity, so "the old mill by the river" in a world with no mill is
  refused. Documented limit: this is English morphology and determiner position,
  not syntax — getting it wrong costs a deflection, never a leak.

### Added — the society (WP4–WP7)

- **Role-based perception.** Five stages: available → attended → recognised →
  interpreted → encoded. Competence gates recognition, role and prior belief
  colour interpretation, so a technician and a tourist no longer witness an event
  identically.
- **Knowledge topology.** Knowledge is classified by domain, locality, access
  level and network rather than by rank; information flows along social networks
  through identifiable bridge people, and each character has a bounded attention
  budget. A street vendor knows more about the local gang than a director does.
- **Retrospective revision.** Exposing a fabricator recomputes the beliefs that
  rest on their word and leaves independently-sourced ones alone, with a revision
  trace. `GET /v2/resting_on` answers the question a player weighs before
  exposing someone, and changes nothing by asking.
- **Memory consolidation.** What repeats is taken out of the episodes before the
  cap deletes them: three separate occasions of the same predicate about the same
  person become a judgement that decays more slowly than any episode it came
  from. Measured — 430 occasions become one judgement still retrievable when
  every episode behind it is gone. It keeps pointers to its five strongest
  episodes, because a conclusion that cannot name its evidence is a prejudice.
- **Stories.** Reach and detail are different states. A headline known by eleven
  people and a full account known by two are one incident, grouped as such, and
  hearing both does not count as two independent sources.

### Added — reachable from an engine (WP9)

- **Contract 2.0, additive.** Version 1 is frozen and still served: no field
  under the old paths changes name, type or meaning, and v1 responses do not even
  grow new fields — a strict parser would break on that too, and a test asserts
  it. New paths live under `/v2/`: `POST /v2/avatar/turn` (the line plus whether
  it was honest and what it asserted to whom), `GET /v2/state/knowledge`,
  `POST /v2/discredit`, `GET /v2/resting_on`.
- **`GET /capabilities`.** Version and capability are different questions. The
  version says which JSON shape is spoken; a capability says whether this build
  can do the thing at all. `action_bridge` and `tts` report `false` and are
  documented as gaps in the contract itself, so an integrator plans around them
  rather than discovering them.
- Both contracts are asserted against a live service by the test suite.

### Added — evidence and scale

- **`unscripted evidence`** runs a long recorded session and writes a dossier: cases,
  verdicts, statistics and the transcript that produced them. Every dossier names
  the commit, the working-tree state, the Python version, the platform and the
  start and finish times — a result that cannot name its commit outlives the code
  it was true of. A run against uncommitted changes says so on its face.
- **`unscripted benchmark`** measures ten claims over a long run — unsourced knowledge,
  single-origin confidence ceiling, secret leaks, provenance gaps, memory and
  snapshot bounds, belief invariants, relaying, and byte-identical replay.
- **`tools/scale_bench.py`** reproduces the scale table: 200 characters over 60
  places cost 6.3 ms per simulated hour, 800 over 200 cost 35 ms, 2,000 over 400
  cost 141 ms, 5,000 over 800 cost 744 ms.
- **`unscripted new`, `unscripted author`, `unscripted studio`** — a world pack that already works, a
  report on what a pack is still missing, and an editor that shows the day as a
  grid with live consequences.
- Two further world packs (`dorf-thornfeld`, `relay-station`) and a documentation
  set: `CONCEPT.md`, `ROADMAP.md`, `VISION_2.0.md`, `ARCHITECTURE.md`,
  `CALIBRATION.md`.

### Fixed — performance

- **Speech had no earshot.** Answering a question updated every person in the
  place, so one answer in a crowded bar was a broadcast to everyone standing in
  it. Bounded to three, and stated as what it is: a bound, not an acoustic model.
  Distance, walls, volume and whispering are not in it.
- **Projections were 80% of tick cost.** Every character's beliefs, memories and
  mood were written to SQL on every event. The event ledger is authoritative;
  projections are a read model. `projection_scope="focus"` keeps them warm for
  the player, the focus agents and anyone the player has met. Everyone else still
  simulates fully — only their read model stops being resident.
- **Recognition was applied to claims that arrived in words.** A layman hearing a
  radio report that a seal failed in Stores relocated it to the med bay. You can
  disbelieve a report; you do not mishear "Stores" as "the med bay". Recognition
  now applies only to what a character perceived directly.

### Changed

- The module layering is declared in `docs/ARCHITECTURE.md` and **enforced by
  test**: a lower layer that imports a higher one fails the suite. Files were not
  moved — 308 internal import lines make a physical reorganisation a large,
  error-prone change in the middle of feature work.
- Tests: 42 → 100.

### Fixed — save/load

- Snapshots lost **relationships, reputation, identity salience, theory-of-mind
  models and all faction state** (heat, progress clocks). A restore rewound
  location and beliefs while keeping the post-rollback social state, so a load
  did not undo what a player had done.
- Snapshots embedded the whole event ledger, provider-call log and reason traces,
  making each save O(session length) and the snapshot table O(saves × length).
  They now record an event-id watermark; `Store.ledger_up_to()` reconstructs the
  ledger as of a snapshot with one range query.
- `AffectState` and `Faction` rounded values in the persistence path, making every
  round-trip lossy. `Memory` did not round-trip `last_recalled`/`world_time`.
- Restore now reports schema, seed and roster mismatches instead of swallowing
  them, and never invents agents the loaded pack does not define.

### Fixed — content/engine separation

- Place topology, place and character aliases, topic definitions, secret surface
  forms, answer phrasings, the slang lexicon, identity→value maps, scene focus
  agents and two world-specific predicates all lived in the SDK. A second world
  pack loaded and validated but could not be navigated or talked to.
- Secret protection was keyed to one literal topic string, so every secret in
  every other pack was unprotected. Secrets are now structured pack content with
  an avoid label, guarded topics, a trust threshold, protected propositions and
  surface forms.
- The secret trust gate was evaluated *after* the fact filter, which hid it in
  exactly the case it exists for. It now runs first, and its reason survives the
  fall-through to deliberation instead of being overwritten.
- The default `inform` template asserted a fact about the reference scene's
  clinic, so characters in other worlds stated things they did not believe.
- The parser excluded the player by a hardcoded id, so a game naming its player
  differently could address the player as an NPC.

### Fixed — LLM safety

- Validator layer 3b (canon) was a comment. Provider output is now parse-checked:
  every proper noun and number must be licensed by the plan. Documented limit:
  inventions worded purely in common nouns are not caught.

### Fixed — service

- Every request field is validated; client mistakes return typed 4xx instead of
  500. `POST /advance {"minutes": -500}` used to rewind world time and silently
  corrupt every memory activation.
- Request bodies are capped from the `Content-Length` header before being read.
- Optional bearer auth (constant-time compare); inspection endpoints and the demo
  UI can be disabled for a shipping build; binding off-loopback unauthenticated
  is refused unless explicitly overridden.

### Added — packaging, validation and tests

- `unscripted/snapshot.py`, `unscripted/content.py`; predicate registry in `unscripted/ontology.py`.
- Pack validation for topology reachability, topic shape, alias collisions,
  secret completeness, predicate declarations and focus agents.
- `LICENSE`, GitHub Actions CI (Python 3.10–3.13, Linux/macOS/Windows, plus a
  clean-environment wheel install), and a complete packaging manifest — 15 of 38
  data files, including both packs' `topics.json`, had been unpackaged.
- Tests: 30 → 42, including a structural guard that greps the engine for 32
  world-content patterns, pack-independence tests, a full snapshot round-trip
  comparison, real-socket service tests, and an end-to-end hallucinating-provider
  test.

## [1.1.0]

Initial reference SDK: belief/memory/affect spine, dialogue stack, agency and
faction layer, MetaHuman adapter, HTTP service, web demo, two world packs.
