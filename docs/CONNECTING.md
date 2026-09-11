# Connecting other people's systems

This runtime is deliberately small. It decides **what a character knows,
believes, conceals and is permitted to say** — and nothing else. Everything that
makes that visible or audible is somebody else's software, and this is how each
of them attaches.

The rule that governs all of it, and the reason any of this is safe:

> **The runtime decides the commitment. Other systems choose the form.**

A language model picks words for a claim the runtime already made. A speech
engine gives that line a voice. An animation system gives it a face. None of
them decides *what is true*, *who knows it*, or *what may be said* — so none of
them can leak a secret, invent a fact, or contradict the world, whatever it
produces.

---

## Two ways in, and which one you want

There are two integrations, and they are not competitors — they are for
different platforms.

| | **The sidecar** (`integrations/`) | **The native core** (`port/`) |
| --- | --- | --- |
| What it is | The runtime as a child process; the game talks HTTP to it | The runtime compiled into the game, behind a C ABI |
| Language | Python | C++17, no dependencies |
| Ships to PC | Yes | Yes |
| Ships to a console | **No** — a console forbids shipping an interpreter | Yes |
| Text provider | Any OpenAI-compatible endpoint, out of the box | The host makes the call; the runtime does not open sockets |
| Save | The service hands you a blob | The library hands you the same blob |
| Maturity | Shipped and verified against real editors | 50 of 51 modules, bit-for-bit against Python — `tuning` included, so a pack that tunes a world behaves the same on both; all three bindings driven against a real toolchain, none of them yet inside a running game |

If you are on PC and want to be running today, take the sidecar. If you are
shipping to a console, or you want the simulation inside your own process with
no IPC, take the native core. **The world packs, the fixtures and the behaviour
are identical** — that is the whole point of holding the port to the same
conformance scenarios.

---

## A language model, for wording

Any **OpenAI-compatible chat endpoint**: Ollama, llama.cpp, LM Studio, vLLM,
or a hosted API. No SDK, no dependency — the adapter is `urllib`.

```python
RuntimeConfig(
    world_pack_path="worldpacks/my-town",
    text_realizer={
        "provider": "http",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "model_id": "qwen3-vl:4b-instruct",
        "api_key": None,            # a Bearer header when set
        "latency_budget_ms": 120,   # see "Latency is handled, not waited on"
        "timeout": 20.0,
        "deferred": True,
        "warm_up": True,            # first call is slow; pay it at load
        "probe": True,              # find out at startup if it cannot do the job
    })
```

```bash
unscripted serve --world-pack worldpacks/my-town \
          --llm-endpoint http://localhost:11434/v1/chat/completions \
          --llm-model qwen3-vl:4b-instruct
```

**What the model is given and what it is not.** It receives the semantic
commitment — this character asserts this, at this certainty, honestly or not —
plus register, mood and the topics it must avoid. It never receives protected
propositions: a secret cannot reach its context at all, so it cannot leak one
even if it tries. What comes back is parsed and compared to the commitment; a
line that asserts something the runtime did not commit to is rejected and the
authored phrasing is used instead. Measured in `evidence/`: 96 questions under
pressure, threat and bribery, 58 model lines stopped, 0 leaks.

**Latency is handled, not waited on.** The deterministic line is produced
immediately. If the model returns something better inside `latency_budget_ms` it
is offered as an upgrade; if not, nothing is late. A warm local 4B answers in
about 290 ms against a 120 ms budget, which means most turns ship the authored
line and the model improves the ones it can. That is the intended behaviour, not
a degraded mode.

**`probe` is worth leaving on.** It asks the configured model, at load, whether
it can actually voice an NPC — and reports in `provider_report` rather than
letting you discover it one fallback line at a time.

**No model at all** is a first-class configuration, not a fallback: authored
phrasings per world pack, fully deterministic, no GPU. It is what the test suite
and every evidence run use.

---

## A speech engine, for voice

The runtime produces a **voice plan** — speech rate, pitch shift and loudness
derived from the speaker's affect, composed with a per-character base voice — so
a frightened character reads faster and higher and still sounds like himself.

```python
from unscripted.voice import synthesize
packet = runtime.avatar_turn("ask Yara about the shooting")
plan = runtime.voice_plan(packet["avatar"])      # a plan, no synthesiser involved
synthesize(plan, "line.wav", backend="kokoro",
           model="~/.local/opt/kokoro/kokoro-v1.0.onnx")
```

`voice_plan` takes the avatar packet — the same dict `/v2/avatar/turn` returns —
because the prosody comes from what the runtime decided about the line, not from
the text. A studio with its own voice pipeline wants the plan and none of the
rendering, and `runtime.speak(...)` is there when you want both.

Three backends ship as adapters, none as a dependency — each is a name on PATH,
because every practical Python TTS pulls in onnxruntime or torch and the
dependency-free install is worth more than a bundled voice.

| Backend | Quality | Honours |
| --- | --- | --- |
| `espeak-ng` | robotic | rate, pitch, loudness |
| `piper` | good | rate |
| `kokoro` | best, 24 kHz | rate, voice selection |

**What each backend cannot do is reported, not smoothed over.** `describe(plan,
backend)` says so in a sentence: piper and kokoro have no pitch control at all,
which costs an emotional read half its signal.

**A commercial engine** (ElevenLabs, Azure, a studio's own) attaches at the same
seam: take the `VoicePlan`, map its three numbers onto that vendor's parameters,
and call their API. `unscripted/voice.py` is 300 lines and the mapping is the
whole of it — the part worth owning is *which prosody a frightened lie gets*,
and that stays here.

There is no audio endpoint on the HTTP service. Speech synthesis belongs on the
machine that plays the audio.

---

## An animation system, for faces

`POST /v2/avatar/turn` returns face blendshapes and prosody alongside the line,
and says whether the character was honest and what they asserted to whom.
`integrations/unreal/` carries MetaHuman-shaped output; `docs/METAHUMAN_INTEGRATION.md`
covers the mapping.

The Unreal C++ **compiles against a pre-built Unreal 5.8.2** and **runs**:
`tools/unreal_check.py` compiles it (UnrealHeaderTool over the reflection macros,
and it links), and `tools/unreal_smoke.py` runs three automation tests inside a
headless editor against a live service — no Unreal licence needed for either.

Worth knowing why both exist. Compiling found a missing include and a map key
type that changed in 5.8. Running found what compiling structurally cannot: the
plugin dropped the `honesty` field the contract promises, and an `EngineVersion`
pin in the `.uplugin` made Unreal skip loading the module entirely on 5.8 — a
plugin that builds, installs, and is silently not there.

---

## Your navmesh, behaviour trees and animation state machines

This is what `action_bridge` is for, and it is the one integration where the
runtime asks *you* for something.

```
GET  /v2/actions/pending              what the runtime wants carried out
POST /v2/actions/{id}/result          what your engine actually did
```

The runtime says *this character intends to go there*. Your engine paths, plays
the walk cycle, opens the door — and answers `SUCCEEDED`, `FAILED`,
`INTERRUPTED` or `UNREACHABLE`. Until it answers, the character is committed;
after `action_timeout_minutes` the runtime gives up on its own.

**You must answer every intent.** A bridge that is enabled and never answered is
a cast that never arrives anywhere. If you are not going to answer, leave the
layer off — off is exactly neutral.

The same shape applies to promises: `POST /v2/promises/{id}/settle` is your
engine telling the runtime that the player really did hand over the money.
Anywhere the runtime cannot know something physical, it asks rather than guesses.

---

## Your quest system, dialogue tree and save game

These are not adapters. They are the actual integration work, and it is an
afternoon that is not spent on HTTP.

**Your existing dialogue tree keeps running.** This does not replace it. Ask
`/v2/state/knowledge` (in the editor) or track it yourself: a node that requires
a character to know something can now ask whether they do, on whose word, and
how sure they are — instead of a global flag that everybody shares.

**Your quest system keeps its own state.** Send the quest steps that characters
could plausibly perceive or hear about as world events; leave the bookkeeping
where it is. Deciding *which* of your existing gameplay events become world
events is the integration — send too few and the society knows nothing, send
everything and the distinction between witnessed and heard stops meaning
anything. Expect to argue about it. That argument is the work.

**Your save file holds the world.** `GET /v2/state/export`, into your own save,
alongside everything else you persist. See `docs/SETTINGS.md` § *Saving*.

---

## What has no adapter, and what to do instead

| You want | The honest answer |
| --- | --- |
| **Unity** | Shipped and **verified**: `integrations/unity/com.vigilant.unscripted/`, the same two components as the Godot addon in C#. It compiles against 6000.0.82f1 with warnings as errors (`tools/unity_check.py`, no licence needed) and three behavioural tests pass inside the editor against a live service (`tools/unity_smoke.py`, which does need one) — on the LTS editor 6000.0.82f1 and on 6000.6.0f1, the newest there is. The latter needs `libxml2.so.2` beside it on Ubuntu 26.04, which ships `libxml2.so.16`; that is a fact about the machine and not about the package. Not yet used in an actual game. |
| **To ship without Python on the player's machine** | **Solved.** `unscripted bundle --standalone` writes a ~94 MB folder holding a redistributable CPython, the runtime as one 380 kB archive, the reference world packs and a launcher. Nothing is installed, nothing goes on PATH, and the system Python — if there is one — is not consulted. Verified by running `unscripted smoke` out of it from an unrelated working directory. Without `--standalone` you get the 380 kB archive alone, which still needs a Python 3.10+ on the box. The interpreter is downloaded already built: no compiler, no PyInstaller, no build toolchain, because a packaging step that can fail in interesting ways fails on somebody else's machine. |
| **To ship to a console** | **Two routes now exist, and which one a studio wants depends on the platform.** On PC the sidecar above is fine: a child process, an HTTP client, `integrations/`. On a console it is forbidden, so there is a second route — one C++17 core with a C ABI, bound natively into all three engines, because **a console forbids an interpreter, not a language.** Measured: 9,623 lines across 51 modules, of which 50 are done — every engine, every optional layer, the parser, the validator, the tick loop, the turn loop and the pack reader, held to this implementation on every test run. All five conformance scenarios are played end to end by the C++ build against the shipped packs and the exported state agrees field for field. The C ABI is proved by a program in C99 compiled by a C compiler; the Unity P/Invoke layer by a real C# compiler against the real library; the Godot GDExtension by a headless Godot driving it from GDScript. Unreal's plugin is split so the half that touches the runtime is tested and the half that has never been compiled is one page of FString conversions — said plainly, because Unreal is not installed on the machine this was written on. See `port/README.md` and `port/bindings/README.md`. |
| **A multiplayer or server deployment** | Single-process, single-world. No sharding. Fine for a game client, not a service platform. |
| **More than one language at once** | The register system is language-agnostic; phrasings are authored per pack in one language. |
| **Analytics or telemetry** | Nothing phones home and nothing will. Reason traces are on every response — take what you want from them. |

---

## Shipping it

```bash
unscripted bundle --out unscripted.pyz          # one file, ~340 kB
python3 unscripted.pyz serve --world-pack my-town --port 0 --announce run/unscripted.json
```

The bundle behaves exactly as an installed `unscripted` does — every endpoint,
every optional layer. **World packs are deliberately left outside it:** they are
your content, they change without a rebuild, and `--world-pack` takes a path.

One command cannot work from a bundle and says so rather than half-answering:
`unscripted architecture` reads the package's own `.py` files to check the layer
map, and inside an archive they are not on disk. It is a development-time
assertion about this repository, not something a shipped game runs.

---

## The check to run before you start

```bash
GET /capabilities
```

It reports the contract versions this build understands and which optional
layers are actually running. **Refuse to start if it does not list a contract
version you know**, and read the layer flags before writing a HUD against a
mechanic — "off" and "not in this build" look identical from outside otherwise,
which is exactly the kind of thing that eats an afternoon.
