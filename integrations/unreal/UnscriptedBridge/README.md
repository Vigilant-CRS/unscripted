# Unscripted Bridge — Unreal Engine plugin

A drop-in UE5 (5.6+/6) plugin that connects your game to the Unscripted
social-intelligence service. Unscripted decides *what* an NPC says and *why it
feels that way*; your project renders it and a voice provider speaks it.

> This is real, idiomatic plugin source. It compiles inside a UE project (it needs
> the engine's `HTTP`/`Json` modules); it is not built by the Python repo's tests.

## Install

1. Start the runtime service (from the `unscripted` repo):
   ```bash
   unscripted serve --world-pack worldpacks/cyberpunk-block --host 127.0.0.1 --port 8765
   # or with a local GPU model for free NPC text:
   unscripted serve --llm-endpoint http://localhost:11434/v1/chat/completions --llm-model unscripted-qwen4b
   ```
2. Copy this `UnscriptedBridge` folder into your project's `Plugins/` directory.
3. Regenerate project files and rebuild; enable **Unscripted Bridge** in the
   plugin browser.

## Use (Blueprint or C++)

```cpp
UUnscriptedClient* Client = NewObject<UUnscriptedClient>(this);
Client->Endpoint = TEXT("http://127.0.0.1:8765");
Client->OnAvatarTurn.AddDynamic(this, &AMyPawn::HandleAvatarTurn);
Client->SubmitTurn(TEXT("ask Vee about Milan"));
```

`OnAvatarTurn` delivers an `FUnscriptedAvatarPacket`:

| Field | Use |
|---|---|
| `Text` | validated, secret-safe line → TTS / subtitle |
| `Blendshapes` (`TMap<FString,float>`) | ARKit-52 weights → MetaHuman face |
| `DominantEmotion`, `Intensity`, `Valence`, `Arousal` | emotion preset / VFX |
| `SpeechRate`, `PitchShift` | hand to your voice provider (Convai / ACE / ElevenLabs) |
| `Posture` | locomotion / montage state (`aggressive`/`retreat`/`approach`/`neutral`) |
| `GazeAversion` | look-at offset in the Anim Blueprint |

## Driving a MetaHuman face

The `Blendshapes` map uses ARKit-52 names — the same the **Live Link Face** app
streams. Two common paths:

- **Live Link source:** push the map as a Live Link subject frame so the
  MetaHuman's existing Live Link face setup consumes it with no extra wiring.
- **Anim Blueprint curves:** in the face Anim BP, `Set Curve Value` for each key
  (`browDownLeft`, `mouthSmileLeft`, `jawOpen`, …) from the map. Interpolate toward
  the new weights each tick for smooth transitions.

Unscripted supplies the *correct, explained* emotion; engines like Convai's
NeuroSync can expand these into MetaHuman's 250+ controls if you want finer
motion.

## Keeping the world reactive

Map your Gameplay Tags / State Tree events to `EmitEvent(Type, Actor, Location)`
so factions, rumour and memory keep developing off-screen. Poll `FetchFace(AgentId)`
between turns for idle/listening expressions.

See `../../../docs/METAHUMAN_INTEGRATION.md` for the full packet schema.


## Verification

```bash
python3 tools/unreal_check.py    # compiles the plugin against a built engine
python3 tools/unreal_smoke.py    # runs it, inside Unreal, against a live service
```

Neither needs an Unreal licence: the editor runs headless without one.

**What running found that compiling could not.** The plugin compiled cleanly and
still dropped the `honesty` field the contract promises on every avatar turn —
so a game could not see whether a character had lied, which is the point of the
runtime. And the `.uplugin` declared `EngineVersion: 5.6.0`, so on 5.8 Unreal
wrote *"'UnscriptedBridge' is Incompatible — Skipping load"* and the module
never loaded at all. That pin is gone: a source plugin is built against whatever
engine it is dropped into, and declaring a version makes the plugin manager
refuse every other one.

**What is still not claimed:** nothing has been played. It compiles, loads,
answers and parses. Whether it feels right in a game is the next thing nobody
has checked.
