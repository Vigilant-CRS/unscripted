# SDK Integration Guide

This guide describes the supported integration boundary for a game studio.

## Ownership Boundary

The game keeps authority over rendering, animation, physics, navigation,
inventory, quest completion, combat execution, UI and savegame containers.

Unscripted owns the social intelligence state:

- perception and observations;
- beliefs and provenance;
- memories and decay;
- affect and social relationships;
- dialogue plans and validated text;
- ally mobilization, faction heat and scheduled social consequences;
- reason traces and replay metadata.

## Minimal Integration Loop

```python
from unscripted import UnscriptedRuntime, RuntimeConfig, Event

unscripted = UnscriptedRuntime.create(RuntimeConfig(
    world_pack_path="worldpacks/cyberpunk-block",
    storage_path="unscripted.sqlite",
))

# Player free text, terminal/web prototype path.
turn = unscripted.submit_player_text("ask Honce about clinic")
show_text(turn.message)
show_debug(turn.developer_trace)

# Engine event path.
receipt = unscripted.emit_event(Event(
    event_id=unscripted.world.new_event_id(),
    world_time=unscripted.world.world_time,
    type="attack",
    actor="agent:player_1",
    location="place:market",
    payload={"summary": "player attacked Pavel", "severity": 0.8},
))

# Time and off-screen consequences.
unscripted.advance_time(20)

# QA and save/load support.
snapshot = unscripted.create_snapshot("before_branch")
replay = unscripted.replay_commands(["look", "ask Honce about clinic"])
unscripted.restore_snapshot(snapshot)

unscripted.close()
```

## HTTP Service Mode

Engines and third-party NPC frontends can use the SDK without embedding Python
internals by running:

```bash
unscripted serve --world-pack worldpacks/cyberpunk-block --host 127.0.0.1 --port 8765
```

Core endpoints:

- `GET /health`
- `GET /bridges`
- `POST /turn` with `{"text": "ask Honce about clinic"}`
- `POST /event` with neutral `WorldEvent` JSON
- `POST /advance` with `{"minutes": 20}`
- `POST /snapshot`
- `POST /restore`
- `POST /generate/characters`

Bridge profiles are available through:

```bash
unscripted bridges
```

The included profiles cover Unreal, Unity, Godot, custom engines and external
NPC/dialogue frontends. They define the integration contract; native plugins can
be thin mappings from engine events to the neutral JSON ABI.

## Engine Adapter Responsibilities

An Unreal, Unity or custom adapter should:

- map engine actor ids to Unscripted `agent:*` ids;
- emit authoritative events when gameplay happens;
- call `advance_time` from game time;
- ask `respond` or `submit_player_text` only when text output is needed;
- execute or reject proposed actions in the engine;
- persist the SQLite file or copy Unscripted projections into the game save;
- expose `inspect_agent` and `inspect_world` to internal developer tooling.
- run golden scenarios in CI for deterministic behavior checks.

## Provider Replacement

Default realization is deterministic. To connect a local or hosted chat endpoint:

```python
from unscripted import UnscriptedRuntime, RuntimeConfig

unscripted = UnscriptedRuntime.create(RuntimeConfig(
    text_realizer={
        "provider": "http",
        "endpoint": "http://localhost:8000/v1/chat/completions",
        "model_id": "studio-local-model",
        "timeout": 20.0
    }
))
```

Provider output is never streamed directly to the player. The runtime stores the
provider record, validates the full text, then releases the accepted output or a
safe fallback. Provider failures that raise the SDK provider error contract are
captured as `provider.failure` reason traces and fall back to the deterministic
local realizer.

## Production Requirements Before Pilot

- Replace or approve the reference parser for the target input style.
- Add a second world pack and run the same tests against both packs.
- Wire engine save/load to the SQLite store or a studio storage provider.
- Add game-specific protected facts and validator surface forms.
- Add performance budgets for active NPC count and background events.
- Decide whether text realization is deterministic, local model, cloud endpoint
  or studio-owned provider.
- Add at least one studio-authored golden scenario before pilot review.
- Choose embedded SDK mode or HTTP service mode for the engine integration.
- Build native Unreal/Unity/Godot packaging only after choosing the target
  pilot engine; this repository currently ships the neutral SDK and bridge ABI.
