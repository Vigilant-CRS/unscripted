# Integrating Unscripted

What you install, what it costs, what it needs from you, and what it will not do.

---

**Two companion documents, and between them they answer most of what follows.**
[`SETTINGS.md`](SETTINGS.md) is every knob, what to set it to for a shipping
build, and what breaks if you get it wrong. [`CONNECTING.md`](CONNECTING.md) is
how a language model, a speech engine, an animation system, your navmesh and
your quest system each attach — and what has no adapter at all.

---

## What it is

A **local service**. One Python process, HTTP and JSON on localhost, no network
calls and no third-party packages. Your game talks to it the way it would talk to
any other subsystem, and it holds one thing your game does not: **what every
character knows, on whose word, how sure they are, and what they are permitted to
say about it.**

It is not a renderer, a quest engine, a dialogue tree or a chatbot. It sits
behind whichever of those you already have.

```bash
pip install -e unscripted          # Python 3.10+, no dependencies
unscripted serve --world-pack worldpacks/market-square --auth-token dev
```

Or with no install at all — the dependency-free promise collecting on itself:

```bash
unscripted bundle --out unscripted.pyz              # one file, ~340 kB
python3 unscripted.pyz serve --world-pack worldpacks/market-square --auth-token dev
```

---

## With a language model, or without

Both are supported and the difference is smaller than it sounds, because **the
model never decides anything.**

| | |
| --- | --- |
| **Without** | Authored phrasings per world pack. Fully deterministic, no GPU, no latency beyond the runtime's own. This is what the test suite and the evidence runs use. |
| **With** | Any OpenAI-compatible chat endpoint, local or hosted. The runtime hands the model an exact semantic commitment; the model returns wording; the wording is parsed back and compared to the commitment before the player sees it. |

The division does not move: **the runtime decides what a character knows,
believes, conceals and is allowed to say. The model chooses words.** A line that
asserts something the runtime did not commit to is rejected and the authored
phrasing is used instead — measured in `evidence/`: 96 questions under pressure,
threat and bribery, 58 model lines stopped before reaching the player, 0 leaks.

```bash
unscripted serve --world-pack worldpacks/market-square \
          --llm-endpoint http://localhost:11434/v1/chat/completions \
          --llm-model qwen3-vl:4b-instruct
```

Latency is handled rather than waited on. The deterministic line is produced
immediately; if the model returns something better inside the frame budget it is
offered as an upgrade, and if it does not, nothing is late. A warm local 4B model
answers in about 290 ms; the budget defaults to 120.

---

## The API

Ask `GET /capabilities` first and refuse to start if the runtime does not list a
contract version you understand. Version 1 is frozen; version 2 is additive under
`/v2/`.

| | |
| --- | --- |
| `POST /v2/avatar/turn` | a player line in, a character's line out — plus `honesty`, what it `asserted`, who heard it, face blendshapes, prosody |
| `POST /event` | **the one you will use most.** A gameplay event becomes a world event: a door forced, a body found, a payment made |
| `POST /advance` | move world time; the society goes about its day |
| `GET /v2/state/knowledge` | who knows what, on whose word — a debug HUD, off in a shipping build |
| `GET /v2/state/public` | what is out in the open, and what is lying unread in a room. **Not** debug-only: a shipping build may read it, because none of it is private |
| `GET /v2/state/character?id=` | one character as a shipped game may draw them: name, place, mood, ARKit face, and their regard for the player — trust, liking, familiarity, what they make of your conduct, and one warmth number to colour a portrait by. **Not** debug-only. Carries nothing about what they know: `/state/agent` has the beliefs, the secrets and the reason trace, and stays off in a shipping build |
| `GET /v2/state/export` | **the save path.** The whole mutable world as one JSON blob — about 11 kB gzipped for eight characters — to write into your own save file |
| `POST /v2/state/inspect` | what loading a blob *would* do, without doing it. What a load screen asks before offering "continue" |
| `POST /v2/state/import` | load it |
| `GET /v2/promises` | what characters have undertaken and not yet made good |
| `POST /v2/promises/{id}/settle` | your engine says what became of one |
| `GET /v2/actions/pending` | what the runtime is asking your engine to carry out |
| `POST /v2/actions/{id}/result` | what your engine actually did about it |
| `POST /v2/discredit` | the player proves somebody lied; dependent beliefs are recomputed |

A full worked example, with real responses captured from a live service, is the
`start.html` page built by `unscripted pages`.

---

## What it costs

Measured, and reproducible with `tools/scale_bench.py` and `unscripted
benchmark`.

| | |
| --- | --- |
| Save size | ~76 KB per character |
| 200 characters over 60 places | 6.3 ms per simulated hour |
| 800 over 200 | 35 ms |
| 2,000 over 400 | 141 ms |
| 5,000 over 800 | 744 ms |
| A dialogue turn | well under a millisecond without a model |

At two thousand characters, a game advancing an hour of world time per minute of
play spends about 0.2% of one core. Cost is driven by how many people share a
room rather than by how many exist — plus a smaller per-tick sweep over the whole
cast.

---

## The work is not the API

Installing takes minutes. The integration is an afternoon, and it is not spent on
HTTP. It is spent deciding **which of your existing gameplay events become world
events.**

A door forced, a body found, a payment made, a quest step completed, an NPC
killed — each is a candidate. Send the ones characters could plausibly perceive
or hear about, and let the runtime decide who actually did. Sending too few gives
you a society that knows nothing; sending everything gives you one where the
distinction between witnessed and heard stops meaning anything.

Expect to argue about which events matter. That argument is the integration.

---

## The optional layers, and why they are optional

Everything below is **off by default**, and off is exactly neutral — a run with
the flag off reproduces byte-identically. A studio that does not want a mechanic
does not pay for it.

```bash
unscripted serve --world-pack worldpacks/market-square --layers pursuit,notes,climate
unscripted serve --explain-layers      # what each one does, and what it needs
```

`GET /capabilities` reports which of them this build is running, so a HUD written
against a mechanic can tell "off" apart from "not in this build".

| Flag | What it adds | What it costs |
| --- | --- | --- |
| `action_bridge` | The runtime asks your engine to carry out physical acts and waits to be told what happened, so the simulation and the screen cannot disagree | You must answer every intent, or characters never arrive anywhere |
| `climate` | Places have a mood — how candid, how suspicious, how open to a stranger — moved by what happens there and carried between rooms by whoever walks | A player can close a district by behaving badly in it |
| `pursuit` | Characters act on their goals instead of only moving on routines and gossiping at random. Without it a world goes quiet after saturation | More events, more traffic, more save churn |
| `media` | A claim can travel by phone as well as by conversation: fewer bystanders, more detail lost, weighed a little lower | Needs `pursuit`; a world with phones has less geography |
| `promises` | A promise comes due and costs or earns something. The runtime has taken promises since the beginning — parsed, emitted, remembered — and nothing ever resolved one, so undertaking something was free | Your engine should settle them (`POST /v2/promises/{id}/settle`); left alone, the runtime judges on whether the promisee came to believe it, which models somebody *noticing* rather than a transaction completing |
| `notes` | Somebody who cannot reach the person they needed leaves word where they stand. A note is still there afterwards, so it can be found by the wrong person — the runtime's first piece of evidence rather than testimony | Needs `pursuit`. Notes are objects in a save; a world with telephones barely produces any, because the person you want is usually in your contacts |
| `contagion` | A little of a speaker's mood moves to whoever they are talking to, damped by the listener's emotional stability | Moods correlate across a cast, which is the point and also means a bad afternoon is visible three conversations away |
| `common_knowledge` | Tracks not who knows a thing but who watched everyone else find out. A secret that is out in the open stops working as a secret, and nobody passes on what both already know is public | Changes what may be **said**, never what is believed. A player who makes something public strips a character of the ability to stonewall — deliberately, and irreversibly |
| `standing` | How you treated one person changes how the rest of them treat you. The act is put into the world as a claim — `mistreated(who=…, by=…)` — so it is perceived, believed, retold and doubted by the machinery that already exists, and somebody's opinion of you moves as far as they believe it | Not a reputation counter. Somebody who was only *told* judges you too, and judges you less far than somebody who watched, because certainty is what scales it. A character can also lie about what you did, and the lie lands exactly as far as it is believed |

---

## Turning a society into a city

The layers above are separable on purpose, and they answer different
questions. A studio that wants all of it turns on all of it; the useful thing is
knowing which one buys which behaviour.

| The question | The layer |
| --- | --- |
| Who has a reason to speak at all? | `pursuit` — without it a world goes quiet once a rumour has saturated |
| Can a message outrun the room? | `media` (phone) and `notes` (paper) |
| Is this place still willing to talk to a stranger? | `climate` |
| Does anybody carry somebody else's afternoon with them? | `contagion` |
| Does breaking your word cost anything? | `promises` |
| Can this still be denied? | `common_knowledge` |
| Does the town hold what I did against me? | `standing` |
| Do my threats work on this person? | `standing` — it is the only thing that has ever produced `fear` |
| Can this stay inside the trade that keeps it? | built in, not a layer: `world.json: predicates` declares a claim `restricted` and to which circles |

The last one is the one worth reading twice. Everything else in the runtime
answers *who knows what*. Common knowledge answers *what can still be gotten away
with*, which is the question a scene is usually actually about.

---

## What it will not do

- **It does not render anything.** There is a Unity package, an Unreal plugin
  and a Godot demo project; the protocol between them and the service is
  asserted against a live service by the test suite. The Unity C# and the Unreal
  C++ both compile here (`tools/unity_check.py`, `tools/unreal_check.py`).
  **Neither has been run inside a game** — treat first integration as a normal
  porting task.
- **It does not synthesise speech.** It plans one: rate, pitch and loudness from
  the speaker's affect, composed with a per-character base voice. `unscripted voice`
  hands that to `espeak-ng`, `piper` or `kokoro`; none of them ships with the
  SDK, and each is reached the same way — a name on PATH.
- **It does not invent incidents.** A world with nothing happening in it stays
  quiet unless your game sends events or `pursuit` is on. That is deliberate:
  a runtime that authored fiction would be doing the exact thing this one exists
  to stop a language model from doing.
- **It is single-process and single-world.** No sharding, no multi-world server.
  Fine for a game client; not a service platform.
- **One language at a time.** The register system is language-agnostic; phrasings
  are authored per pack in one language.

---

## If you put `unscripted serve` on the public internet

Then **you** are the Diensteanbieter for that service, not Vigilant e.K., and in
Germany § 5 DDG wants your provider identification on it: name, address, contact,
register entry and VAT id, easily recognisable and directly reachable. The same
goes for a hosted build shown to press or playtesters.

The runtime deliberately does **not** emit anybody's imprint on `/demo` or
`/studio`. A library that stamped its vendor's company onto a page you are liable
for would be naming the wrong provider. Add your own to whatever wraps it.

Two other things that follow from operating it rather than shipping it: the state
inspection endpoints (`/state/*`, `/inspect/*`) expose what every character
believes and are for development, so turn them off in anything public; and a
public instance processing player text is your data processing, under your privacy
notice.

Vigilant e.K.'s own imprint, for the pages and demos it publishes itself, is in
[`IMPRESSUM.md`](../IMPRESSUM.md).

## Verifying any of it

```bash
python3 tests/test_scenarios.py              # the whole suite
python3 -m unscripted golden-all                    # multi-step playthroughs with assertions
python3 -m unscripted benchmark --turns 1500        # ten claims measured over a long run
python3 -m unscripted qa qa/relay-station.json      # the shortest player sequence that breaks a stated rule
python3 -m unscripted evidence --hours 2            # a dossier sealed to the commit that produced it
```

Every number on every page in this repository is produced by one of those, and
each page prints the command that reproduces it.
