# MetaHuman & Unreal Engine Integration

Unscripted is the **social-intelligence layer**, not a renderer. This adapter
makes it plug-and-play with **MetaHuman** (Unreal Engine 5.6+ / 6): the runtime
decides *what* a character says and *why it feels that way*; MetaHuman renders
the face and a voice provider speaks the line.

```
player input ─▶ Unscripted ─▶ avatar packet ─┬─▶ MetaHuman face (ARKit-52 via Live Link)
                (belief, memory,         text+emotion+   ├─▶ TTS / Convai / NVIDIA ACE (prosody hints)
                 affect, validator)      blendshapes     └─▶ Anim Blueprint (gaze + posture)
```

We do **not** compete with MetaHuman, Convai, NVIDIA ACE or ElevenLabs — they
sit *beside* the runtime. Unscripted owns causal world-memory, validated
dialogue and explainable affect; they render and voice it.

## The avatar packet

`POST /avatar/turn` (or `runtime.avatar_turn(text)`) returns a normal turn result
plus an `avatar` block whenever an NPC speaks:

```jsonc
{
  "message": "Vee: \"...\"",
  "avatar": {
    "speaker_id": "agent:npc_red_jacket",
    "text": "...",              // validated, secret-safe line to voice
    "act": "evade",
    "verdict": "ACCEPT",        // only ACCEPT lines ever reach the player
    "emotion": {
      "dominant": "distress",
      "intensity": 0.68,
      "valence": -0.4, "arousal": 0.3, "dominance": 0.19,
      "active": { "distress": 0.68, "fear": 0.47, "anger": 0.33 }
    },
    "blendshapes": {            // ARKit-52 weights in [0,1] — stream via Live Link
      "browInnerUp": 0.84, "mouthFrownLeft": 0.47, "mouthFrownRight": 0.47,
      "eyeWideLeft": 0.38, "browDownLeft": 0.44, "...": 0.0
    },
    "gaze": { "target": "agent:player_1", "aversion": 0.19, "make_contact": true },
    "prosody": { "speech_rate": 1.01, "pitch_shift": -0.10, "loudness": 0.51 },
    "posture": "retreat"        // aggressive | retreat | approach | neutral
  }
}
```

Between turns, poll a character's live face with
`GET /avatar/face?agent_id=agent:npc_red_jacket` (or `runtime.face_packet(id)`) —
useful for idle expression, reactions to off-screen events, or listening faces
while another NPC speaks.

## Field reference

| Field | Maps to in Unreal | Notes |
|---|---|---|
| `text` | TTS input / subtitle | Already validated; never leaks a protected fact. |
| `blendshapes` | MetaHuman face via **Live Link** | ARKit-52 names, `[0,1]`. Absent key = `0.0`. |
| `emotion.dominant` / `intensity` | optional emotion preset selector | Coarse label if you prefer presets over raw blendshapes. |
| `gaze.aversion` / `make_contact` | look-at target / aim offset in Anim BP | Rises with shame, fear and low dominance. |
| `prosody.*` | TTS / Convai / ACE voice params | `speech_rate` ≈ 1.0, `pitch_shift` and `loudness` are hints. |
| `posture` | locomotion / montage state | From Frijda action tendencies. |

The blendshape set is deterministic: identical affect in → identical weights
out, so avatar output is reproducible and replayable like everything else in the
runtime. The mapping lives in
[`unscripted/metahuman.py`](../unscripted/metahuman.py).

## Unreal side (sketch)

A thin C++/Blueprint plugin only has to do JSON plumbing:

1. On a dialogue trigger, `POST /avatar/turn { "text": "<player line>" }`.
2. Feed `avatar.text` to your TTS / Convai / ACE node.
3. Each tick during the line, apply `avatar.blendshapes` to the MetaHuman face
   through a **Live Link Source** (the same channel Live Link Face uses).
4. Drive look-at from `avatar.gaze`, locomotion from `avatar.posture`, and pass
   `avatar.prosody` to the voice provider.
5. Map your Gameplay Tags / State Tree events to `POST /event` so the world keeps
   reacting off-screen.

Bridge profiles `metahuman` and `unreal_metahuman` (`GET /bridges`) document the
inbound events and outbound results for a native plugin.

## Why ARKit-52

ARKit-52 is the Live Link Face standard MetaHuman consumes natively, so no
per-character expression authoring is needed. With MetaHuman's RigLogic/DNA now
open source (MIT, MetaHuman Devkit), the same packet can also drive MetaHumans
**outside** Unreal. Voice/face engines such as Convai's NeuroSync expand these
into MetaHuman's 250+ controls — our job is to supply the *correct, explained*
emotion, not to re-render the face.

## Try it

```bash
unscripted avatar --text "ask Vee about Milan"            # one turn, full packet
unscripted avatar --agent agent:npc_red_jacket            # live face packet, no turn
unscripted serve --world-pack worldpacks/cyberpunk-block  # then POST /avatar/turn
```
