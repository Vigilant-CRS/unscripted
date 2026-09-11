# Implementation Review

Status after the SDK hardening pass.

## Implemented And Tested

- Public SDK facade: player text, event ingestion, time advance, dialogue
  response, snapshots, restore, replay and inspect views.
- Deterministic terminal demo and full `unscripted showcase` sales/regression flow.
- World-pack validation and two packs using the same runtime core.
- Authored `initial_state.json` beliefs loaded with provenance.
- Automatic character generation from place, faction, role hints, appearance and
  deterministic seed.
- Bridge profiles for Unreal, Unity, Godot, custom engines and third-party NPC
  frontends, plus HTTP/JSON service endpoints.
- Provider record persistence and safe local fallback when an external provider
  fails through the SDK provider contract.
- Terminal reachability guard: physical player speech only affects reachable
  NPCs; remote integrations should use `emit_event` or `/event`.

## Review Findings Fixed

- The old `demo.py` used the internal runtime path and did not exercise the
  public SDK. It now runs the full SDK showcase.
- External text provider failures could bubble out of dialogue generation. They
  now fall back to validated local text and produce `provider.failure` traces.
- Service `/event` required host-provided event ids. It now auto-assigns an id
  when the engine payload omits one.
- `generate-characters` read only relative pack paths. It now resolves packaged
  world-pack paths before reading or writing.
- Terminal speech to remote named NPCs could produce responses without a matching
  perception event. The terminal now rejects unreachable targets.

## Theory And Product Gaps

- The theory documents describe native engine adapters and pilot samples. This
  repository currently ships the engine-neutral SDK, bridge profiles and HTTP
  ABI, not certified Unreal/Unity/Godot plugins.
- The theory calls out visual inspectors. The implemented inspector is textual
  and structured for terminal/HTTP; an engine UI remains studio-specific work.
- The theory mentions 20-30 NPC scenes. The reference pack is intentionally
  compact, while the generator can produce more NPCs. A larger authored content
  pack is still a content-production task.
- Competitor support is implemented as neutral bridge contracts and profile
  mappings. Direct certified adapters for specific external NPC products are not
  bundled.
- Performance budgets are not yet benchmarked for a target hardware profile.
  The regression suite validates behavior, not load limits.

## Verification Command

```bash
python3 tests/test_scenarios.py
python3 -m unscripted showcase
python3 -m unscripted validate worldpacks/cyberpunk-block
python3 -m unscripted validate worldpacks/noir-harbor
python3 -m unscripted golden golden/block17_smoke.json
python3 -m unscripted smoke
python3 demo.py
```
