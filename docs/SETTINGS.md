# Settings

Every knob, what it does, and — the part most references leave out — **what to
set it to for a shipping build, and what breaks if you get it wrong.**

Two objects. `RuntimeConfig` is the simulation; `ServiceOptions` is the HTTP
surface in front of it. Everything has a default that works, so a first run needs
none of this.

---

## The four you must decide

Everything else has a defensible default. These four do not, and getting each
wrong has cost somebody an afternoon.

| Setting | Default | What to actually set |
| --- | --- | --- |
| `storage_path` | `":memory:"` | **A real path, or nothing persists.** The default is right for tests and wrong for a game. See *Saving* below — and note that even with a real path, the save your game ships is `GET /v2/state/export`, not this. |
| `world_pack_path` | `worldpacks/cyberpunk-block` | Your pack. The default is a demo world about a cyberpunk city block. |
| `auth_token` | `None` | Any string, always. Without it, anything on the machine can talk to your runtime. Generate one per launch; see `UnscriptedHost.gd`. |
| `expose_debug_endpoints` | `True` | **`False` in anything a player runs.** True exposes `/state/*`, `/inspect/*` and `/avatar/face` — every character's private beliefs and reason traces. Fine in the editor, a spoiler machine in a shipped build. |

```bash
# development
unscripted serve --world-pack worldpacks/my-town --auth-token dev

# what a game launches
unscripted serve --world-pack worldpacks/my-town \
          --storage save/world.db --auth-token "$GENERATED" \
          --no-debug-endpoints --port 0 --announce "$RUNDIR/unscripted.json" \
          --parent-pid $$ --layers pursuit,promises
```

---

## `RuntimeConfig` — the simulation

### Identity and content

| Field | Default | Notes |
| --- | --- | --- |
| `runtime_id` | `"unscripted:main"` | Labels this instance in traces and `/health`. Only matters if you run more than one. |
| `schema_version` | current | Reported, never set by you. |
| `world_pack_path` | a demo pack | The directory. Three files is a valid pack — see *How small a world can be*. |
| `player_id` | `"agent:player_1"` | Which agent is the player. Must exist in the pack, or be created by it. |
| `player_start_location` | `None` | Overrides the pack's `player_start`. |
| `load_initial_state` | `True` | Whether authored beliefs from `initial_state.json` are seeded. `False` gives you a cast that knows nothing — useful for testing diffusion, wrong for a scenario. |
| `canon_mode` | `"strict"` | `strict` rejects a generated line that contradicts `canon.json`. Leave it. |

### Storage and performance

| Field | Default | Notes |
| --- | --- | --- |
| `storage_path` | `":memory:"` | A file path, or `":memory:"`. See the warning above. |
| `debug_traces` | `True` | Keeps the per-event reason traces. They are the explainability story and they cost memory; `False` in a shipping build unless you surface them. |
| `strict` | `True` | Refuse to load a pack with validation errors. Keep it `True`: a pack that loads with errors fails later and further away. |
| `population_lod` | `False` | Defer decay for characters nobody is interacting with, caught up exactly on access. Turn on above ~200 characters; it is the difference between 141 ms and comfortably under at 2,000. |
| `projection_scope` | `"all"` | Which characters get resident SQL projections. `"all"` costs four fifths of the tick at scale; use `"none"` and call `project_for(...)` on the handful a debug HUD is watching. |

### The optional layers

All off. All neutral when off — a test asserts a disabled run reproduces
byte-identically. `unscripted serve --explain-layers` prints this list at the
terminal.

| Field | Needs | What it adds |
| --- | --- | --- |
| `action_bridge` | — | The runtime asks your engine to carry out physical acts and waits to be told what happened. **You must answer every intent, or characters never arrive anywhere.** |
| `climate` | — | Places have a mood, moved by what happens in them and carried between rooms by whoever walks. |
| `pursuit` | — | Characters act on their goals instead of only gossiping at random. Without it a world goes quiet once a rumour saturates. |
| `media` | `pursuit` | A claim can travel by telephone: fewer bystanders, more detail lost, weighed lower. |
| `notes` | `pursuit` | Somebody who cannot reach the person they needed leaves word where they stand. |
| `contagion` | — | A little of a speaker's mood moves to the listener. |
| `common_knowledge` | — | Tracks who watched everyone else find out. A secret that is out in the open stops working as one. |
| `standing` | — | What you did to one person changes how the others treat you, carried as a claim so hearsay reaches people who were not there — and moves them less. |
| `promises` | — | A promise comes due and costs or earns something. **Settle them from your engine** — see `POST /v2/promises/{id}/settle`. |

`action_timeout_minutes` (default 60) is how long the bridge waits for your
engine before giving up on an intent. Too short and characters abandon errands
mid-stride; too long and a dropped answer freezes somebody for an hour of world
time.

### Voice

| Field | Default | Notes |
| --- | --- | --- |
| `voice_backend` | `"none"` | `espeak-ng`, `piper` or `kokoro`. None ships with the SDK; each is a name on PATH. |
| `voice_model` | `None` | The `.onnx` for piper and kokoro. |

### Text generation

`text_realizer` and `capabilities` are dictionaries; see *Connecting other
people's systems* for what goes in them.

---

## `ServiceOptions` — the HTTP surface

| Field | Default | Notes |
| --- | --- | --- |
| `auth_token` | `None` | Set it. Also readable from `UNSCRIPTED_AUTH_TOKEN`. |
| `expose_debug_endpoints` | `True` | `False` in a shipping build. |
| `allow_insecure_bind` | `False` | Guards binding to a non-loopback address without a token. If you are reaching for this, ask why the runtime is on a network at all — it is a single-process, single-world local service, not a server. |
| `allow_origin` | `None` | CORS, for a browser client. |
| `max_body_bytes` | 1 MiB | Rejected on the header, before anything is read. |
| `max_text_chars` | 4000 | One player utterance. |
| `max_advance_minutes` | 525600 | One year per call. A guard against a client that meant hours and sent minutes. |
| `max_generated_characters` | 64 | Per authoring request. |
| `authoring_path` | `None` | Where the authoring UI may write. Leave unset outside the editor. |

---

## Saving — the one that surprises people

There are **two** things called saving and they are not the same.

`POST /snapshot` and `/restore` keep state inside the runtime's own store and
hand you an id. Good for a debug rewind. **Not** what your game should ship: a
player's save is copied between machines and synced to a cloud, and an id
pointing into a second database drifts away from the file it belongs to the
first time that happens.

`GET /v2/state/export` gives you one JSON blob — about 11 kB gzipped for eight
characters — to write into **your own save file**, alongside everything else you
persist.

```
GET  /v2/state/export      -> {"format": "unscripted-state", ...}
POST /v2/state/inspect     -> {"usable": true, "code": "world_changed", ...}
POST /v2/state/import      -> load it
```

Call `inspect` on your load screen before offering *continue*. When you patch
your game and the cast changes, old saves still load — `code` becomes
`world_changed` and the response names exactly who was `restored`, `dropped` and
`unsaved`. A patch is not a corruption, and refusing the save would cost a player
their game to protect them from a difference the runtime can simply name.

---

## Tuning — how *this* world works

The settings above are the build. This is the world, and it belongs in the world
pack, because a mediaeval village and a surveillance state are not the same
simulation with different names in it.

**79 parameters across 14 parts of the runtime** are authorable from one block:

```json
// world.json
"tuning": {
  "diffusion": { "distortion_prob": 0.30, "encounters_per_hour": 0.9 },
  "memory":    { "tau_ret": -1.2, "episodic_cap": 400 },
  "contagion": { "transfer": 0.20 },
  "promises":  { "horizon_minutes": 720 }
}
```

```bash
unscripted tune --world-pack worldpacks/my-town   # every knob, its value, what it governs
```

Three things worth knowing before you use it:

- **An unknown name is an error, never a shrug.** `unscripted validate` refuses a
  misspelled parameter and names the close ones. A value silently ignored is the
  worst outcome this feature could have: the world behaves as though nothing was
  set and the author believes otherwise.
- **It is recorded.** Every override appears in the trace as `tuning.applied`
  with the default beside it, so a scene behaving oddly never requires diffing a
  JSON file against the runtime's source.
- **Tuning changes how much, never what is possible.** These are rates and
  thresholds. No value makes a character know something nobody told them or say
  something the validator would stop, so a pack cannot tune its way out of the
  guarantees — a test asserts that under deliberately extreme settings.

Measured on `market-square` over a simulated week: `distortion_prob` at 0.6
takes retellings that lose a detail from 31 to 128; `episodic_cap` at 20 takes a
character from 119 remembered things to 61.

---

## How small a world can be

The shipped packs have hundred-line characters. That is richness, not
requirement. This loads and plays:

```
my-pack/world.json          {"places": {"place:inn": {"label": "The Inn"}}}
my-pack/scenario.json       {"id": "scenario:min", "title": "Min"}
my-pack/characters/anna.json {"id": "agent:anna", "names": {"public": "Anna"}}
```

`unscripted validate my-pack` then tells you, as warnings, everything that would
make it better — traits, relationships, goals, a location, exits, topics —
without refusing to run. Start there and add what a scene actually needs.

`unscripted new my-pack` scaffolds a validated, playable two-character world
with a map report and a "who meets whom" table, which is a better starting point
than a blank directory.
