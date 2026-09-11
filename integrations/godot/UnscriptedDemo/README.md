# Unscripted — Godot demo

The same events, twice, inside a game engine.

The web pages make this argument with a table and a map. A studio's next
question is whether it survives contact with an engine, and a table cannot
answer that. This is a real Godot 4.3 project talking HTTP to a running
`unscripted serve`.

## Run it

```bash
# 1. the runtime
unscripted serve --world-pack worldpacks/market-square --auth-token dev

# 2. the demo
godot --path integrations/godot/UnscriptedDemo
```

It takes `--url=` and `--token=` after a `--`:

```bash
godot --path integrations/godot/UnscriptedDemo -- --url=http://10.0.0.4:8080 --token=hunter2
```

## What it shows

A councillor is shot in the open street. City Radio has the story first and says
it was the east-side kids. It was not: Yara had a stall two metres away and saw
three men who did not run and did not panic, and she is not listening to the
radio, because she was standing in it.

Sixteen simulated hours run before anything is asked. People walk their routines,
claims pass between them as pulses that leave the route behind as a thread, and
the block splits: **eight believe the radio, five believe the witness.** Nobody
authored that. Then the same questions are asked of two representations:

| | Flags | Unscripted |
| --- | --- | --- |
| Who knows it? | everyone: the channel fired | only the people who were listening |
| Who told them? | nowhere to put it | the origin, and how many hops away |
| How sure? | there is no third state | a probability, with the evidence behind it |
| Was it a lie? | nowhere to put it | the runtime's own record of the speaker's belief |

`Flags.gd` is fifteen lines and it is **not a straw man**: a set of booleans is
how most shipped games hold what characters know, and it is fast, saveable and
understood by everyone on the team. What it cannot hold is the entire finding.
The same model, with the reasoning written out, is `unscripted/flat.py`.

## How it is built

- **Two phases.** Everything is fetched first and played back second. A demo that
  renders while it waits on HTTP shows a different thing on a slow machine, and
  the slow machine is the one it will be shown on. It also makes a recording
  deterministic.
- **No assets.** Rooms, characters and panels are `_draw()` calls. That is not
  thrift: a schematic that is clearly designed reads as engineering, and there
  are no third-party licences to track.
- **No fallback.** With no service running it says so and stops. A demo that
  quietly invents an answer when the runtime is absent will one day be shown with
  the runtime absent, and nobody will notice until the questions start.

## Recording it

`tools/godot_demo.py` starts the service, runs the demo through Godot's Movie
Maker mode at a fixed timestep, lays the narration over it and writes an MP4.

## What this is not

A plugin. It is a demo of the HTTP contract, written in one file plus a client,
so that reading it end to end takes ten minutes. The engine-side integration
this repository ships as a plugin is the Unreal one under
`integrations/unreal/`, and that has never been compiled here — which is stated
wherever it is mentioned.
