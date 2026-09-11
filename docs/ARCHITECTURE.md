# Architecture

Where things live and what may depend on what. For *why* each mechanism works
the way it does, see [`CONCEPT.md`](CONCEPT.md).

```bash
unscripted architecture      # prints the live map and checks it
```

---

## Six layers

A module may import from its own layer or any layer below it, **never above**.
This is enforced by `tests/test_scenarios.py :: test_layering_is_declared_and_holds`,
which reads the real import graph rather than trusting this page.

```
 5  surfaces    cli · service · studio · webdemo · authoring · benchmark · golden
                evidence · showcase
                     ▲  nothing depends on these
 4  runtime     runtime · pack · sdk · state_view · inspect
                     ▲  the loop, the world pack, the read models
 3  world       agent · perception · diffusion · routine · parser · validator
                world · snapshot · persistence · generator
                     ▲  many characters and a place
 2  adapters    provider · edge · metahuman · bridge · capabilities
                     ▲  translation to things that are not this runtime
 1  engines     belief · memory · affect · relationship · social · sociolinguistics
                agency · policy · content · distortion · dialogue · factions
                     ▲  one character's mind, one mechanism per module
 0  foundation  types · statekey · determinism · events · ontology · contracts
                actions · architecture
                     vocabulary with no behaviour
```

49 modules, 6 layers, 0 upward imports.

### What each layer is for

**0 — foundation.** Value types, the proposition catalogue, event shapes, seed
derivation. No behaviour, no state, no decisions. Everything else is written in
this vocabulary, which is why contradiction and relevance are computable at all.

**1 — engines.** One character's mind, one mechanism per module. Each takes
state and inputs and returns new state plus a reason trace. **None of them knows
there is a world, a player, or a text layer** — `belief.py` cannot reach a world
pack, and that is what makes each one testable in isolation and replaceable
without touching anything else.

**2 — adapters.** Translation to and from things that are not this runtime: text
providers, local model endpoints, faces, engine bridges. They convert; they never
decide.

*Why below the world rather than above it.* An adapter is an interface the
runtime uses, not a consumer of it. Placing them here makes the important
property structural instead of intentional: **the world cannot come to depend on
which provider is installed.** Delete every adapter and the simulation still
runs — which is exactly the guarantee that a game must keep working when a model
endpoint is gone.

**3 — world.** Many characters and a place: who could perceive what, who met
whom, who moved where, what a player typed, what may be said aloud, and how all
of it is stored and restored.

**4 — runtime.** The loop that puts the above in order, the world pack that feeds
it, and the read models built on top.

**5 — surfaces.** Ways a human or a machine reaches the runtime. Nothing depends
on these, so any of them can be removed or replaced without consequence — which
is what makes the demo genuinely separable from the SDK rather than merely
described as separable.

---

## Why not folders

`unscripted/core/`, `unscripted/social/`, `unscripted/text/` would express the
same thing in the filesystem, and at some point they probably should.

They are not used yet for a specific reason: there are about three hundred
internal import lines, and rewriting them in the middle of feature work is a
large, error-prone change whose payoff is readability. The payoff of
*enforcement* is that the architecture cannot quietly erode, and that costs one
file. `unscripted/architecture.py` holds the map; moving the files later is a
mechanical follow-up that this map would drive.

The map is the single source of truth. A new module that is not placed in a layer
fails the test rather than being silently tolerated — placing it is a decision
someone has to make on purpose.

---

## Rules that hold across layers

**Every stage writes a reason trace.** `(code, magnitude, detail)`. This is why
`unscripted evidence` can reconstruct why a line was said months later, and why
`inspect` can answer "why does this character believe that".

**No global RNG.** Every draw derives its seed from
`blake2b(world_seed, entity, purpose, tick)`. A module that reached for
`random.random()` would break replay, so it does not exist.

**The engine ships no world content.** Predicates, facts and phrasings live in
world packs. `test_engine_contains_no_world_content` fails the build if fictional
content appears in an engine module.

**Bounded state.** Memory, provenance and summaries all have caps. Anything
per-character that can grow needs a bound and a metric, because the runtime is
expected to survive thousands of simulated days.
