# Running a Local Model

Unscripted needs no language model. Everything — belief, memory, secrets,
diffusion, faction reaction — runs deterministically without one, at zero cost
per interaction. A model is an *optional text layer* that makes lines less
repetitive, and the runtime keeps it on a short leash.

If you use one, use a local one. No per-interaction cost, no network dependency,
no vendor who can deprecate your NPCs.

---

## The numbers that shape the design

Measured against ollama on one desktop GPU:

| Model | cold | warm |
| --- | --- | --- |
| `qwen3-vl:4b-instruct` | 7,493 ms | **290 ms** |
| `qwen3-vl-abliterated:4b-q4_K_M` | 6,796 ms | **281 ms** |
| `qwen3-vl-abliterated:8b-q4_K_M` | 25,234 ms | **361 ms** |

Two different problems live in there:

**Cold start.** The first request pays for loading weights into VRAM. Without
intervention that 7–25 s lands on whichever NPC the player talks to first.

**Warm latency.** ~300 ms is past any frame budget but fine for a dialogue turn —
*provided nothing blocks on it*.

---

## How the runtime handles both

```python
from unscripted import UnscriptedRuntime, RuntimeConfig

runtime = UnscriptedRuntime.create(RuntimeConfig(
    text_realizer={
        "provider": "http",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "model_id": "qwen3-vl:4b-instruct",
        "latency_budget_ms": 120,   # answer within this or use authored text
        "deferred": True,           # keep generating; offer the line later
        "warm_up": True,            # page the model in at load time
        "probe": True,              # check at startup that it can do the job
        "timeout": 20.0,            # hard ceiling on a background request
    }))
```

### 1. Warm-up removes the cold start from gameplay

At load time the runtime issues two throwaway generations and measures them:

```python
runtime.provider_report["warm_up"]
# {'model_id': 'qwen3-vl:4b-instruct', 'cold_ms': 5294.5, 'warm_ms': 293.2, 'ok': True}
```

A 5-second load becomes a loading screen instead of a broken first conversation.

### 2. The latency budget: answer now, upgrade later

A turn waits at most `latency_budget_ms`. If the model beats it, its line is used
directly. If not, the turn answers from **authored text immediately** and the
model keeps generating in the background.

```text
budget 120 ms →  turn took 122 ms   "Far as I know, the place was shut that night."
                 upgrade at 372 ms  "Shift's over, thanks for coming."

budget 600 ms →  turn took 316 ms   "Shift's over, thanks for coming."   (direct)
```

Collect late lines whenever it suits your frame loop:

```python
for upgrade in runtime.poll_line_upgrades():
    subtitle.replace(upgrade["speaker_id"], upgrade["text"])
```

`poll_line_upgrades()` returns only lines that **passed the same validator** —
canon parse-back, secret surface forms, repetition — as any other generated text.
A rejected late line is never offered, and the rejection appears in the speaker's
reason trace as `provider.late_line_rejected`.

Set the budget from your measured warm latency:

| Budget | Effect |
| --- | --- |
| below warm latency (e.g. 120 ms) | every line is authored first, model arrives as an upgrade |
| above warm latency (e.g. 600 ms) | model lines are used directly; turns take that long |
| `deferred: false` | a slow model is simply skipped, no upgrades |

### 3. The probe says at startup whether the model is worth using

```python
runtime.provider_report["probe"]
# {'verdict': 'usable', 'passed': 3, 'of': 3, 'typical_ms': 293.8,
#  'advice': 'model produces clean in-character lines. Typical latency 294 ms
#             exceeds the 120 ms budget, so lines will arrive as deferred upgrades'}
```

Three verdicts:

- **`usable`** — clean, short, in-character, no prompt scaffolding echoed back.
- **`degraded`** — some checks fail; many lines will fall back to authored text.
- **`unusable`** — nothing usable comes out. Typically a small *thinking* model
  whose reasoning gets cleaned away, leaving nothing. Safe, but pointless: you
  are paying for a GPU to produce the same authored lines you would get for free.

Without the probe you discover this one fallback line at a time, which tells
nobody anything.

---

## Choosing a model

- **Prefer a non-thinking instruct model.** A 4B instruct produces clean lines; a
  small "thinking" model spends its output on reasoning that is then stripped.
- **4B is enough** for NPC one-liners and costs half the VRAM of an 8B, at similar
  latency. The 8B was not measurably better at this task in probing.
- **Quantised (q4_K_M) is fine.** No measurable quality difference for lines this
  short.
- **Keep the model resident.** ollama unloads after an idle timeout; the next line
  then pays the cold cost again. Set `OLLAMA_KEEP_ALIVE` generously for a session.

```bash
ollama pull qwen3-vl:4b-instruct
OLLAMA_KEEP_ALIVE=2h ollama serve
unscripted play --llm-endpoint http://localhost:11434/v1/chat/completions \
         --llm-model qwen3-vl:4b-instruct
```

---

## What the model is never allowed to do

This is the part that makes a local model safe to ship:

- It never sees a secret. The dialogue planner passes an avoid-*label*; protected
  propositions are removed from `allowed_facts` before the prompt is built.
- It cannot introduce a fact. Every proper noun and number in its output must be
  licensed by the plan, or the line is rejected and authored text is used
  (`docs/` → canon layer in the README).
- It cannot make a turn hang. The budget is enforced by the runtime, not by the
  model's cooperation.
- It cannot break a save. Model text is never part of simulation state; a snapshot
  restores identically whether a model was involved or not.
- Its raw output is recorded in the `provider_call` table, accepted or not, for
  audit.

If the model, the endpoint or the whole GPU disappears mid-session, every NPC
keeps talking. The lines get less varied. Nothing else changes.

---

## Known limits

- **No streaming.** Deliberate: a partially generated line cannot be validated,
  and validating after the player has read it is not validation.
- **No batching.** Each line is one request. A scene with many simultaneous
  speakers will queue; `max_pending` (default 8) refuses the overflow rather than
  letting lines get staler.
- **The budget is wall-clock, not a cancellation.** A late request runs to
  completion in the background even if its result is discarded. It costs GPU, not
  frame time.
- **The probe is three cases.** It catches "this model cannot do the job at all",
  not "this model is subtly worse than that one".
