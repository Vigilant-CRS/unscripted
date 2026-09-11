# Integrating with Unreal

The question this page answers is *"how many weeks of my team?"*, and it answers
it with measurements rather than adjectives.

**Division of labour.** The runtime decides what a character knows, says and feels
and why. Your project renders it. Nothing in the plugin simulates anything, and
nothing in the runtime touches a frame.

---

## What you get

| | |
| --- | --- |
| `worldpacks/relay-station` | a 10-NPC sample world: seven rooms, overlapping shifts, three askable topics, one real secret |
| `integrations/unreal/UnscriptedBridge` | the plugin: one subsystem, one component, one transport |
| `contract.json` | the exact JSON the plugin parses — checked against a live service by the runtime's own tests |

---

## The shape of the integration

Three objects, and you only ever touch two of them.

**`UUnscriptedSubsystem`** — one per world. Owns the connection, the current
scene and world time. This is your Blueprint surface:

```
Connect(BaseUrl, AuthToken)     -> OnSceneChanged
SubmitPlayerLine(Text)          -> OnNpcSpoke(FUnscriptedAvatarPacket)
AdvanceWorldTime(Minutes)
SendGameplayEvent(Type, Actor, Location, Summary)
RefreshKnowledge()              -> GetRecentRetellings()   (debug HUD)
```

**`UUnscriptedNpcComponent`** — drop on a character, set `AgentId` to the id in
the world pack. It polls that character's face and calls `OnFaceUpdated`, which
you implement in Blueprint to drive your rig. Faces are *polled*, not pushed,
because a face is a continuous property of mood rather than an event: an NPC
sulking in a corner should be visibly angrier when the player walks back in.

**`UUnscriptedClient`** — the transport. You should not need to touch it.

---

## Measured cost

Local service, `relay-station`, 30 calls per endpoint, one core:

| Endpoint | median | p95 |
| --- | --- | --- |
| `GET /health` | 0.54 ms | 0.92 ms |
| `GET /state/scene` | 0.51 ms | 0.64 ms |
| `GET /avatar/face` | 0.53 ms | 0.60 ms |
| `POST /avatar/turn` | 1.82 ms | 2.18 ms |
| `POST /advance` | 1.58 ms | 2.73 ms |
| `GET /state/knowledge` | 1.11 ms | 1.42 ms |

Ten faces polled in sequence: **5.6 ms**. At the default half-second poll interval
that is 20 requests per second and about **11 ms of work per second of play** for
a ten-NPC scene — under 1% of a 60 Hz frame budget, spread across frames, and all
of it off the game thread because every call is async.

The one call that is not free is `POST /avatar/turn` at ~1.8 ms, and it happens
once per player line. If you add a language model, that number is replaced by the
model's latency, which is why the runtime answers from authored text inside a
frame budget and offers the model's line as a later upgrade — see
[`LOCAL_MODELS.md`](LOCAL_MODELS.md).

---

## Getting to a speaking NPC

```bash
# 1. Serve the sample world
unscripted serve --world-pack worldpacks/relay-station --auth-token dev-token

# 2. Copy the plugin into your project
cp -r integrations/unreal/UnscriptedBridge  MyProject/Plugins/

# 3. Regenerate project files and build
```

In the level Blueprint:

1. `Get Unscripted Subsystem` → `Connect("http://127.0.0.1:8765", "dev-token")`
2. Bind `OnNpcSpoke` → set your subtitle widget from `Packet.Text`
3. Add `UnscriptedNpcComponent` to each of the ten characters, set `AgentId`
   (`agent:voss`, `agent:okonkwo`, `agent:rask`, `agent:lindqvist`, `agent:mbeki`,
   `agent:tan`, `agent:ferro`, `agent:nakamura`, `agent:adeyemi`, `agent:hollis`)
4. Implement `OnFaceUpdated` → drive your MetaHuman from `Face.Blendshapes`

The weights are the ARKit-52 names Live Link Face uses, so a MetaHuman needs no
per-character authoring. **Only non-zero weights are sent** — a calm face is an
empty map, not fifty-two zeroes. Treat a missing key as `0.0`.

---

## The sample world

`relay-station` is built to show the thing that is hard to show: a society where
information moves.

Seven rooms, ten crew on overlapping shifts, a seal that failed in Stores during
the night cycle. After two simulated days, with nobody scripting anything:

```
seal_breached(section=place:store, when=night_cycle)   10 know  (5 saw, 5 heard)
logged_out(agent=agent:lindqvist, when=night_cycle)     9 know  (1 saw, 8 heard)
supply_short(item=item:sealant)                         7 know  (2 saw, 5 heard)
seal_breached(section=place:store, when=None)           6 know  (0 saw, 6 heard)
skipped_check(agent=agent:lindqvist, check=check:seal)  1 knows (1 saw, 0 heard)
```

Read that bottom-up and you have a detective scene nobody wrote:

- **the deed** is known to exactly one person, behind a trust gate of 0.6;
- **the clue** — that Lindqvist was signed out — has spread to nine, eight of them
  by hearsay, from a single observation by Hollis;
- **the motive** — the station being out of sealant — is known to seven;
- and the fourth line is a **levelled** version of the incident: six people have
  lost the "when" entirely. They know a seal blew. They no longer know when.

`RefreshKnowledge()` gives you all of that, including who told whom and what
changed on the way, which makes a genuinely useful in-editor debug HUD.

---

## Two contracts, and how to pick one

```
GET /capabilities        ->  ask this first, before anything else
```

```json
{
  "runtime_version": "1.16.0",
  "contract_versions": ["1.0.0", "2.0.0"],
  "default_contract": "1.0.0",
  "capabilities": {
    "semantic_moves": true, "deception": true, "retrospective_revision": true,
    "knowledge_topology": true, "story_grouping": true, "judgements": true,
    "action_bridge": true, "tts": false
  }
}
```

**Version and capability answer different questions.** The version says which JSON
shape is spoken. A capability says whether this particular build supports the
feature at all — a `false` means the feature is absent, not that nothing happened
this turn. `action_bridge` is the one that is *configuration*: it reports whether
this build was started with `action_bridge=true`, because "no intents pending"
and "this build never issues any" look identical on the wire. A client asks for a version it understands and refuses to
start if the runtime does not list it.

**Version 1 is frozen and still served.** A shipped game keeps working: no field
under the old paths changes name, type or meaning, and the v1 responses do not
even grow new fields, because a strict parser would break on that too. Both
contracts are asserted against a live service by the test suite.

### What version 2 adds

| | |
| --- | --- |
| `POST /v2/avatar/turn` | the line **plus** `honesty` and `asserted`: what the runtime committed the character to saying, and who was close enough to hear it |
| `GET /v2/state/knowledge` | `stories`, `knowledge_classes`, `circles`, `bridges`, `contested`, `judgements` |
| `POST /v2/discredit` | the player proves somebody lied; dependent beliefs are recomputed |
| `GET /v2/resting_on` | what currently stands on one person's word, changing nothing |
| `GET /v2/actions/pending` | what the runtime is asking **your engine** to carry out |
| `POST /v2/actions/{id}/result` | what your engine actually did about it |

`honesty` is the one to build a mechanic on. It is the runtime's own record of
whether the line matched what the speaker believes, and **it must never be
inferred from the text** — that is the whole reason the runtime owns it.

`stories` is the one to build UI on. A radio headline and an eyewitness account
of the same incident are one story at two levels of detail, and reach and detail
are independent: a claim can be widely known and thin, narrowly known and
precise, or widely known and wrong, all at once.

### The action bridge: the runtime asks, the engine answers

Until now the runtime moved characters itself. `RoutineEngine` set
`agent.location` at 12:00 because the schedule said the mess hall, and no part of
the system ever asked whether your engine had walked anyone anywhere. If a door
was locked, a cutscene was running, or there was simply no nav path, the player
kept watching a character stand still while every belief, perception and rumour
in the simulation was computed for a character who had left. Nothing detected it,
because nothing was ever asked.

Start the runtime with `action_bridge=true` and relocation becomes an exchange:

```
GET  /v2/actions/pending                -> [{intent_id, actor, type, params, reason,
                                             issued_at, expires_at}, ...]
POST /v2/actions/{intent_id}/result     <- {"status": "SUCCEEDED"}
```

```
runtime            engine
  |  MOVE_TO(mess)   |    the character has NOT moved. He is at params.from
  | ---------------> |    and stays there until you answer
  |                  |    you walk him, or you fail to
  |   SUCCEEDED      |
  | <--------------- |    only now does his location change, only now does
  |                  |    everyone in the room perceive an arrival
```

Four answers, and no fifth: `SUCCEEDED`, `FAILED`, `INTERRUPTED`, `UNREACHABLE`.
Only the first changes the world. Anything else records that the act did not
happen and leaves the character exactly where the player last saw him — which is
the point of the whole exchange: the two worlds agree, *including* when they
agree that nothing moved. A status outside the four is a 400 rather than a guess;
a second result for one intent is a 404.

**Answer every intent.** One left open past `expires_at` (world time, in minutes)
is closed by the runtime as `TIMED_OUT` and treated as a failure, so a project
that polls but never reports ends up with a world in which nobody ever arrives
anywhere. The `bridge` block on `/v2/actions/pending` carries the counts —
`timed_out` climbing is how you find that out in ten seconds instead of a week.

In the plugin: `UUnscriptedSubsystem::PollIntents()` after every turn and every
time advance, handle `OnActionIntent`, then `ReportIntentResult(IntentId,
Status, Detail)`. Each intent is broadcast once, so polling every tick during a
thirty-second walk does not restart that walk thirty times a second.

The catalogue is closed and currently has **one** entry, `MOVE_TO`. `WARN` and
`GIVE` appear in the roadmap and are deliberately not declared: the runtime does
not decide them yet, and an intent type that never fires reads as a channel you
have to handle.

### What is still specified and not served

`capabilities` reports `tts: false`. Prosody parameters — rate, pitch, loudness —
are emitted on every spoken line; no speech synthesis is integrated. It is
written into `contract.v2.json` so the gap is part of the agreement rather than a
surprise.

## How the two sides stay in sync

The engine side cannot be compiled in this runtime's CI, so a renamed field would
otherwise break the plugin silently and be discovered by a studio, in Unreal, at
integration time.

`contract.json` states exactly what the C++ parses. The runtime's test suite spins
up a real service and asserts every endpoint still produces those fields with
those types, including that no blendshape key appears which the plugin cannot map.
Change either side and the test fails until they agree again.

That is the mechanism. It is not a substitute for compiling: **the plugin sources
have not been built against an engine in this repository.** Treat the first build
as a normal porting task — expect include and API-version fixes for your engine
version — and treat the contract as the guarantee that the *protocol* is right.

### First build: what was checked here, and what only you can check

Checked in this repository, by test:

- every endpoint the plugin parses still produces those fields, with those types,
  against a live service;
- every `called_by` in both contracts names a method that is declared in a header
  **and** defined in a `.cpp` — twelve of them. This found one that did not exist.

Checked by reading, not by building — the two findings are already applied:

- `Json` moved from a private to a public module dependency. `UnscriptedClient.h`
  puts `TSharedPtr<FJsonObject>` in a delegate that is part of the public API, so
  a game module binding a handler to `GetJson` needs the type rather than the
  forward declaration. Private compiles *here* and fails in the project that
  consumes it, which is the worst place to find out.
- the `.uplugin` `VersionName` said `0.1.0` while the module implements contract
  2.0 including the action bridge. It now says `0.2.0` and the description names
  the contract version it speaks.

What only a real build tells you, in the order it will tell you:

1. `EngineVersion` is pinned to `5.6.0` in the `.uplugin`. On another 5.x the
   editor asks whether to rebuild; that is normal, not a compatibility statement.
2. Include fixes. `CoreMinimal.h` covers `TSet` and `FString::Printf`, but UE
   moves headers between minor versions more often than it moves APIs.
3. `TSet::Intersect` and the delegate macros are stable API surface and should
   need nothing.
4. `PollIntents` broadcasts `OnActionIntent` once per intent. Bind it, walk the
   character, and call `ReportIntentResult` — a project that polls and never
   reports produces a world in which nobody ever arrives anywhere, and the
   `bridge.timed_out` counter is how you will see that in ten seconds.

---

## Things worth knowing before you start

- **`avatar` is optional.** A turn that moved the player, looked around, or was
  rejected by the parser produces no spoken line. Check for the block.
- **World time is monotonic.** `AdvanceWorldTime(-1)` is refused by the plugin and
  by the server. To rewind, restore a snapshot.
- **Authentication is required off loopback.** The server refuses to bind to a
  non-loopback address without a token, and refuses to serve the authoring UI off
  loopback at all.
- **Disable the inspection endpoints for a shipping build** with
  `--no-debug-endpoints`. `/state/*` exposes every character's private beliefs;
  that is what makes the debug HUD useful and what a game client must not have.
- **The runtime keeps simulating off-screen characters.** The component stops
  polling faces for actors that are not rendered, which saves requests, not
  simulation — they still meet, talk and change their minds while you are away.
