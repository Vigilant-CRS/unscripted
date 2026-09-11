# Every value that moves, what moves it, and what reads it

`CALIBRATION.md` is about whether the constants are grounded. This page is about
the wiring: **which numbers change during play, what changes them, and what acts
on them afterwards.**

It exists because the same defect kept turning up in this runtime and each time
it took a measurement to find: a value that several engines *read* and nothing
ever *wrote*. `reputation` was like that until the promises layer arrived.
`fear`, `respect` and `dependence` were like that until conduct started producing
them. `appearance` was authored on every character in every pack and read by
nothing but the character generator. A table you can scan is the cheapest defence
against the next one.

**Read the third column first.** A row marked *authored only* is a value you can
set and then watch stay exactly where you put it — and every one of them is now
declared in `contracts.AUTHORED_ONLY_FIELDS` with the reason it has no producer,
because `test_nothing_is_read_that_nothing_writes` refuses to let a field be read
by an engine and written by nothing without somebody saying so out loud.

---

## Per character, per other person

| Value | Range | Moved by | Read by |
| --- | --- | --- | --- |
| `trust` | 0…1 | a promise kept (+0.8) or broken (−0.7); conduct believed; being threatened or helped | how far their testimony moves your belief; `warmth`; what they will say to you |
| `liking` | −1…1 | promises; conduct believed | `warmth`; the register they speak to you in (converge or diverge) |
| `familiarity` | 0…1 | perceiving somebody, saturating: `+0.02` of the remaining distance each time, so roughly thirty-five encounters to pass halfway | how far a mood carries between them (`contagion`); `warmth`; how personally their treatment of a third party is taken |
| `fear` | 0…1 | **cruelty believed** (`standing`) | whether a threat against them is expected to work or to backfire; how carefully they speak to you |
| `respect` | 0…1 | **kindness believed** (`standing`) | deference in the register; `influence` |
| `dependence` | 0…1 | **authored only**, declared in `contracts.AUTHORED_ONLY_FIELDS` with the reason | whether they will call on somebody for backup; `influence` |
| `attraction` | 0…1 | `epistemic.drawn_to` matching the other's appearance tokens | `warmth` |
| `kinship`, `loyalty`, `favor_debt`, `owes_favor` | 0…1 | **authored only**, each declared with its reason | mobilisation, who can be asked for a favour |
| `reputation.status` | −1…1 | **authored only** | perceived prestige, in the register |
| `reputation.decent` | −1…1 | conduct believed, first-hand or by hearsay, scaled by how far it is believed | `warmth`; perceived status |
| `reputation.reliable` | −1…1 | a **broken** promise, among the promisee and everybody who heard it made. A kept one records nothing: a kept promise is expected, a broken one is news | authoring and inspection; not currently read by a decision |

### Computed from those, never stored

| Summary | What it is |
| --- | --- |
| `warmth` −1…1 | one number to colour a portrait by: `0.30·liking + 0.20·trust + 0.50·decent + 0.25·attraction` |
| `influence` 0…1 | how much sway somebody has over you: `0.35·respect + 0.30·dependence + 0.25·fear + 0.10·reach`. **Not liking** — somebody you are fond of and neither respect nor need has no particular pull |
| perceived status 0…1 | their baseline prestige, what you think of their conduct, and **what they are wearing** |
| a reading | `{status, threat, signals}` from appearance — see below |

Both `warmth` and `influence` come back from `GET /v2/state/character?id=`, which
a shipping build may call.

---

## Per character, about themselves

| Value | Range | Moved by | Read by |
| --- | --- | --- | --- |
| beliefs | log-odds + provenance | claims, broadcasts, and acts they watched | what they will say, what they pass on, what can be revised out from under them |
| memory | strength, decays | everything they perceive | recall, and what they can be asked about |
| mood (PAD) | −1…1 each | appraisal of what happens; a little of a speaker's mood (`contagion`) | their face, their register, what they feel like doing |
| `identity_salience` | 0…1 | which belonging the moment makes matter | how they weigh safety against loyalty |
| `identity_threat` | 0…1 | somebody who shares a belonging being attacked. Halves in a day: alarm, not a grudge | identity salience |
| attention budget | per day | hearing new claims | whether they take in the next one at all |

**Personality never moves.** `big_five`, `schwartz` values, `education` and
authored `values` are fixed for the life of a world, deliberately: a runtime
where traits drift under play is how every character in a long game converges on
the same person.

---

## Per place

| Value | Range | Moved by | Read by |
| --- | --- | --- | --- |
| `candour` | 0…1 | what happens here; drifts toward neighbours | how readily what is known here gets passed on |
| `suspicion` | 0…1 | violence, crime | how far a claim is discounted for coming from outside |
| `openness` | 0…1 | the same | how readily a stranger is spoken to at all |

All three relax back toward what the pack authored. Requires the `climate` layer.

---

## What a developer authors, and where

Everything below is content: it is read at load and never changes during play.
This is the whole calibration surface, in one list.

### On a character (`characters/*.json`)

| Key | What it decides |
| --- | --- |
| `big_five`, `schwartz`, `needs`, `values` | who they are: how agreeable, how security-minded, whether they would lie to you |
| `education: {domain: 0…1}` | what they are competent *on*. A doctor on medicine and a bartender on gossip are not equally credible, and this is the number that says so |
| `epistemic.curiosity`, `.confirmation_bias` | how much they notice, and which way a scene they cannot read gets bent |
| **`epistemic.source_trust`** | **whom they believe.** A multiplier per kind of source, looked up most specific first: a channel id (`channel:city_radio`), then its type (`radio`, `intercom`, `press`), then the speaker's role (`role:officer`), then `witnessed` / `broadcast` / `told`. Absent means 1.0 |
| **`epistemic.appearance_sensitivity`** | how much they judge by a coat at all. 0.0 for somebody who genuinely does not care |
| **`epistemic.drawn_to`** | which appearance tokens they are taken with. Authored, never decided by an engine: what somebody finds striking is a characterisation |
| `appearance` | `{"garment": "item:apron", "symbols": ["sym:reds"]}` — and any other key you like |
| `networks`, `roles`, `identities` | **which groups they belong to.** A district, a shift, a trade, a family. This is what decides what reaches them |
| `routine` | where they are, hour by hour — and therefore who they ever meet |
| `secrets` | what they will not say, what they will say instead, and what it would take |
| `relationships` | the starting values of every row in the first table |

### On the world (`world.json`)

| Key | What it decides |
| --- | --- |
| `places` | the map, and per place `noise`, `surveillance`, `privacy`, `formality`, `gossip_factor` |
| `predicates` | **what kind of thing each claim is**: `common`, `public`, `trade`, `restricted` — and for a restricted one, `access: ["role:engineer"]`. A restricted claim does not leave its circle. Not slowly: at all |
| `channels`, `media_exposure` | who hears what, and how attentively |
| **`appearance_reactions`** | **what a garment means here.** Per token: `status` (how seriously the wearer is taken), `threat` (how dangerous they look), `signals` (which circle a symbol claims) |
| **`standing_conduct`** | what counts as decency in this setting. Per predicate: which reputation dimension it moves, which way, and how far |
| `identity_values` | what a belonging amplifies |
| `command_aliases` | the words your players will actually type |
| `layers` | which optional mechanics this pack is built on |
| `tuning` | 79 parameters across 14 engines — see `SETTINGS.md` |

### Or let a premise write the first draft

    unscripted generate-pack worldpacks/mine --places 20 --characters 60 --topics 12

Produces every file above, wired so both gates accept it: trades and shifts so
people meet, districts so a claim has a circle to stay inside, routines, one
liar. Deterministic on the seed. It writes structure, not prose — the phrasings
are flat on purpose, and that is the place for a language model at build time.

### What each one costs you if you leave it out

Nothing. Every key above is optional and every one defaults to neutral: no
`appearance_reactions` and a coat means nothing; no `source_trust` and everybody
weighs a source the same way; no `drawn_to` and nobody is taken with anybody.
That is why adding all three left every shipped pack byte-identical — and it is
why they are authored data rather than layers with switches. A switch nobody has
to set is a switch nobody has to read about.

---

## The 9 optional layers

Everything above is on. These are off until asked for, each one byte-identical
when off, asserted by test rather than promised:

`action_bridge` · `climate` · `pursuit` · `media` · `notes` · `promises` ·
`contagion` · `common_knowledge` · `standing`

Switch them on with `unscripted serve --layers pursuit,standing`, or let a pack
name its own in `world.json: layers`. `--layers none` ignores what the pack asks
for, so "off is exactly neutral" stays checkable on a pack that asks for
something.

---

## Where each of these is proved

| Claim | Test |
| --- | --- |
| conduct produces fear and respect, and they reach what reads them | `test_fear_and_respect_stop_being_decorative` |
| what you did reaches people who were not there, and moves them less | `test_what_you_did_to_one_of_them_reaches_the_rest_of_them` |
| a coat changes how you are taken; gang colours are read as something else | `test_what_you_turn_up_wearing_changes_how_you_are_taken` |
| whom you believe is a fact about you | `test_who_you_believe_is_a_fact_about_you` |
| a restricted claim does not leave its circle | `test_a_thing_the_engineers_say_stays_among_the_engineers` |
| every optional layer is neutral when off | `test_every_optional_layer_is_off_by_default_and_reachable` |
| **nothing is read that nothing writes** — the guard for this whole page | `test_nothing_is_read_that_nothing_writes` |
