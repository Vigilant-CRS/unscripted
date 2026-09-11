# Porting the runtime to a console

**Status: 50 of 51 modules are ported and held to Python on every test run, all
five conformance scenarios play end to end in C++, and all three engine bindings
are verified against a real engine. The whole `engines` layer is
complete** — all fifteen of them — **and so is every
optional layer**: climate, pursuit, promises, notes, medium, contagion, common
knowledge, flat-world, tuning, grounding and interpretation -- `tuning` included
all the way through to the engines, which it was not until [the note
below](#the-knob-that-did-not-turn-and-now-does) was written and then acted on. One character
entire: belief, memory, mood, relationships, identity, standing, how they are
read, how they sound, what they decide, what they commit to saying, and what
they made of what they saw. And the society around them: who is where, who can
hear, who tells whom what, what the story becomes on the way, and what the
factions do while nobody is watching.

**All five conformance scenarios now play end to end in C++**, against the
shipped packs, and the exported state agrees with Python field for field.

One module left, and it is not going anywhere: the pack VALIDATOR. See the note
at the end of this list. This page says what was measured, what it means, and what the
work actually is — so nobody plans a quarter against a guess.

---

## Why a port at all — and why not four of them

A shipped console title may not start a Python interpreter beside itself. Not a
licensing problem, a certification one: Sony, Microsoft and Nintendo all forbid
loading and running code that was not in the submitted, signed binary. The same
rule closes off the sidecar on iOS. On PC the sidecar is fine and is what the
Godot, Unity and Unreal integrations do today.

The instinct is that "port to every console" means a port per platform, or a
port per language — C# for Unity, C++ for Unreal, GDScript for Godot, and
something for each console. It does not. **A console forbids an interpreter, not
a language.** All five current consoles compile C++, and all three engines can
call a C function.

So the plan is one core and thin bindings:

```
                      usc-core  (C++17, no dependencies)
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   C ABI header         C ABI header         C ABI header
        │                    │                    │
   Unreal module        Unity P/Invoke       Godot GDExtension
   (links natively)     (IL2CPP → native)    (loads the .so/.dll)
```

Three bindings, each a few hundred lines of marshalling, over one implementation
that is written once and verified once. Not four ports drifting apart, each with
its own bugs and its own idea of what a belief is.

The work is therefore **sequential, not parallel**: the core first, the bindings
after. Nothing about the bindings can be validated before there is something to
bind.

---

## The question everything rested on

A port is worthless if it computes something subtly different. This runtime is
deterministic on a seed, which is stronger than it sounds: `derive_seed` decides
who overhears what, `seeded_choice` decides which of four things somebody does,
and a belief crossing a threshold decides whether a character will say a thing
out loud. **A difference in the last bit of a double is not a rounding error
here. It is potentially a different world.**

So before writing anything else: does C++ compute the same bits as Python?

    python3 port/cpp/probe/port_probe.py

It builds `bit_probe.cpp`, runs it, computes the same 31 values in Python, and
compares the raw 64 bits of every double — because `0.35` printed to fifteen
places hides exactly the difference that matters.

### Measured, on this machine (g++ 15.2, glibc)

| | |
| --- | --- |
| blake2b seeds, four cases incl. UTF-8 and empty strings | identical |
| `int.from_bytes(seed[:8], "big") / 2**64` | identical |
| `eta * log(kappa / (1 - kappa))`, 21 combinations | identical |
| 200 accumulated evidence steps, then a sigmoid | identical |
| **total** | **31 of 31 bit-identical** |

Two of those three are identical *by construction* and will stay so anywhere:
blake2b is integer arithmetic, and dividing by 2⁶⁴ is one rounding of an integer
that fits in a double. Neither can drift.

`log()` is the exception, and it is the whole risk. It is a library function, not
an operation IEEE-754 pins down. Two correct implementations may return doubles
one bit apart, and a console's libm is not glibc.

### So the second measurement: what does one bit actually do?

`log` was replaced with `nextafter(log(x))` — the smallest disagreement two
correct implementations could have — and all five conformance scenarios re-run
against the committed fixtures:

| | |
| --- | --- |
| fields that moved | 160 |
| largest relative error, after a full scenario | **1.3 ULP** |
| discrete outcomes that changed | **0** |

**The error does not compound.** After a whole scenario it is still sitting
roughly where it started, and no seeded choice, no threshold and no provenance
chain moved. That is the finding that makes a port viable, and it was not
obvious beforehand — a feedback loop through a sigmoid could easily have
amplified it.

It is also five scenarios of a few dozen turns, not a forty-hour playthrough.
The claim is what was measured and not more than that.

### The third measurement: the compiler is a variable too

The same source, the same machine, the same libm — six flag sets, and since this
release **two GCC major versions**: the whole suite, all four probes, the C ABI
and all three engine bindings pass under **15.2 and under 13.x** alike.

```bash
CXX=g++-13 CC=gcc-13 python3 tests/test_scenarios.py    # 163 tests, green
```

Two major versions is a different optimiser and different code generation, so it
retires "it has only ever been built by one compiler". It does **not** touch the
question that actually matters for a console, and saying so is the point of this
page: both link the same glibc, so this is still one libm. A console's is not
glibc, and `log()` is a library function rather than an IEEE-754 operation. That
remains untested and untestable here.

The six flag sets:

| Flags | Result |
| --- | --- |
| `-O0`, `-O2`, `-O3` | identical to each other |
| `-march=native` | identical — vectorisation alone does not move a bit |
| `-Ofast`, `-O2 -ffast-math` | **one value differs, by 1 ULP** |

The value that moves is the only accumulated one: 200 additions in a loop.
`-ffast-math` licenses the compiler to reassociate a sum, and `(a+b)+c` is not
`a+(b+c)` in floating point.

One ULP over 200 steps is inside the tolerance, so a port built this way still
passes. But this is the one error in the whole measurement that **grows with run
length** rather than staying put, and 200 steps is not a playthrough. The right
call is not to rely on the tolerance absorbing it: build the core without
`-ffast-math`. That is why `port/cpp/CMakeLists.txt` sets no such flag and says
why, and why a project-wide toolchain file that turns it on is worth catching —
the probe will show it as a single differing line.

### What this changed in the tooling

The fixtures compare eighteen significant digits. Held to that, a *correct* port
on a console toolchain fails every single scenario, for a reason that is not its
fault and cannot be fixed in its code. So:

    usc conformance --check          # this implementation: exact, no tolerance
    usc conformance --check --port   # a port: numbers may differ in the last bit

`--port` allows 8 ULP — measured room over the 1.3 that was observed, and four
orders of magnitude below a real defect. Nothing else is tolerated: a different
agent, a different event count, a different provenance chain or a different
string fails at any tolerance, because those are the differences that mean the
port is wrong.

Both ends are pinned by `test_a_port_may_differ_in_the_last_bit_and_nowhere_else`,
which substitutes a 1-ULP `log` and requires it to pass, then substitutes a `log`
wrong by one part in ten thousand and requires it to fail. It catches 301 fields.

---

## What has to be ported, measured

| Layer | Lines | Modules | |
| --- | ---: | ---: | --- |
| `foundation` | 659 | 8 | value types, seeds, event shapes, contracts |
| `engines` | 2,253 | 15 | belief, memory, affect, policy, standing, … |
| `world` | 4,038 | 23 | perception, diffusion, routines, topology, climate |
| `runtime` | 2,673 | 5 | the loop, the pack, the read models |
| **to port** | **9,140** | **49** | minus 483 lines of `generator`/`validator`, which are build-time |
| **…of which done** | **9,140** | **49** | all of it. The row read **3,780 / 28** for months after the port had finished, which is the drift this table exists to prevent: a status line and a status table in one file disagreeing, with the reader believing whichever they read first |
| stays Python | 9,757 | 25 | CLI, service, authoring, evidence, benchmarks, demos |

Roughly half the codebase never ships inside a game.

---

## The order, and why

Each step is verifiable before the next begins. That is the point of the order:
a port that can only be judged at the end is a port nobody can schedule.

1. **`determinism`** — **done.** Everything stochastic derives from it.
2. **`types`, `ontology`, `statekey`** — **done.** The two-branch sigmoid,
   propositions with the contradiction logic, and typed deltas. `core_key()` is
   the identity a belief is filed under, so it matters far more than its size
   suggests.
3. **`belief`** — **done.** Log-odds accumulation, the correlation discount, the
   provenance chain.
4. **`memory`, `affect`, `relationship`** — **done.** One mind, no world: mood
   and emotion, trust kinetics, reputation, identity salience, ACT-R recall and
   the judgements drawn out of forgotten episodes.
5. **`actions`, `policy`** — **done.** Utility aggregation and the seeded
   choice. The term/bias distinction is preserved exactly: a term is averaged
   into its group, a bias is added, and merging the two reintroduces a bug where
   looking dangerous made a character *less* likely to back away.
6. **`contracts`, `events`, `social`, `content`** — **done.** The vocabulary, the
   feature providers, and a pack's own words. `contracts` is mostly constants, so
   the probe compares them word for word: a layer description worded differently
   in C++ is a lie in a `/capabilities` response.
7. **`agent`, `world`, `routine`, `topology`, `perception`, `distortion`,
   `diffusion`** — **done.** The society. Where the seeded draws start happening
   inside loops over collections, which is what the fixtures were built to catch:
   seven of them in `diffusion` alone.
8. **`agency`, `sociolinguistics`, `dialogue`, `standing`, `appearance`,
   `commitment`, `factions`** — **done.** The `engines` layer is complete: all
   fifteen. How somebody is read before they speak, how they sound to the person
   in front of them, what the town thinks of them, who comes when they call, and
   what the runtime commits them to saying before any words exist.
9. **`climate`, `pursuit`, `promises`, `notes`, `medium`, `contagion`,
   `common_knowledge`, `flat`, `tuning`** — **done.** The optional layers, one
   at a time, each already covered by a fixture that switches it on.
10. **`grounding`, `interpretation`, `revision`** — **done.** What a released
    sentence asserts about a world that may not contain it, what a witness
    actually made of what they saw, and what a liar has already convinced you
    of, and `parser` -- reading a player's sentence. `snapshot` is done too:
    capture, restore, and the one blob a game puts in its OWN save file.
11. **`runtime`, `sdk`, the pack loader** — **done.** The tick loop, the turn
    loop and the reader that turns a directory of JSON into a world. All five
    conformance scenarios are played by both implementations and compared.
13. **`state_view`, `metahuman`, `capabilities`** — **done.** The machine-readable
    face of the explainability, and the bridge to a face that moves.
12. **The C ABI** — **done.** `port/cpp/abi/usc.h`, one header, no C++ across
    the boundary, nothing that throws, every structured answer as JSON. Proved by
    a program in C99 compiled by a C compiler, which is the only proof that
    matters: a header that works from C++ and not from C is not a C ABI, and the
    mistake does not surface until somebody's plugin will not link. It builds as
    a static library or a shared one, and `cmake -S port/cpp -B build` is the
    whole build.
14. **The three bindings** — **done, and all three are verified against a real
    engine.** `port/bindings/` has the table and the reasons. Unity's P/Invoke
    layer is compiled by a C# compiler and run against the library; Godot's
    GDExtension is loaded by a headless Godot and driven from GDScript; Unreal's
    plugin compiles and links against Unreal 5.8.2 with UnrealHeaderTool over
    its reflection macros, and its engine-free half is driven against the
    library in the suite. None of the three has been RUN IN A GAME, which is a
    different sentence and is the one still outstanding.

`persistence` is SQLite, and it is NOT going to be ported. A console's save
system belongs to the host: the snapshot layer hands out one opaque blob with an
envelope a loader can read without parsing the payload, and the game writes it
wherever it writes everything else. Porting a database into a dependency-free
simulation core to re-implement a save file the host already has would be the
wrong answer to a question nobody asked. The same reasoning applies to the HTTP
client in `provider` and, for a different reason, to `pack`: a pack is
LOADED by the port -- `pack_loader.hpp`, and every shipped pack is read by both
implementations and compared field by field -- but it is VALIDATED on a
developer's machine at build time, in Python, against the same files. A shipped
game loads its pack every time it starts and never validates one.

`architecture` and `generator` are build-time tools and are not on this list:
nothing in a shipped game calls them. `validator` was listed here too and that
was WRONG -- the runtime builds one per world and every provider line goes
through it, so it is as shippable as the belief engine and is now ported.
`tuning` was listed here as well and is ported anyway, because a pack that ships
a tuning block needs the same numbers read the same way on both sides.

#### The knob that did not turn, and now does

**And here is the hole that was in it, and how it was closed**, because a silent
knob is the one failure `tuning.py` exists to prevent and this port had it in its
strongest form.

`tuning::check` rejects exactly what Python rejects and `tuning::apply` computes
exactly what Python computes -- into a `ParameterTable`, a map of names to
numbers. Python gets away with that because `engine.params` IS the engine's
storage: writing the map changes the engine. C++ has no reflection, so each
engine holds its parameters as typed members, and for months nothing filled that
table from the engines or wrote it back. A tuning block was validated, computed,
and dropped. An author would have set a knob, believed it, and got nothing.

Closing it was not seventy setters, which is what this page said before somebody
looked. Three layers -- `notes`, `promises` and `common_knowledge` -- held their
numbers as `inline constexpr` constants, and a constant cannot be written at run
time. They carry a `Params` struct now, like the other eleven, with the constants
kept as its defaults so each value is still stated exactly once.

**All 79 knobs across 14 engines are bound**, in `knob.hpp` and each engine's own
`knobs()` table, and `tuning_bind.hpp` carries the values in and out. The
binding sits beside the `Params` it describes rather than in one central file,
because an explicit list of names is a copy and a copy drifts -- and drifting
here is invisible, which is the whole problem. So a fourth probe holds every one
of them to the live Python dictionary:

```
python3 port/cpp/probe/tuning_probe.py
  tuning: 79 knobs across 14 engines reach the C++ engines and agree with
  Python, over 8 blocks
```

Name for name, ORDER for order, and bit for bit, plus what a block CHANGES and
the reason rows it leaves in the trace. It was checked against a deliberately
forgotten knob and a deliberately reordered one, and it fails on both, naming
what went wrong.

**One difference remains, and it is deliberate.** Python stores whatever JSON
handed it, so `provenance_limit: 7.0` leaves a float in the dictionary; this port
narrows to the member's type and stores `7`. Wherever the value is compared or
added those are the same number -- which is every count but two.
`notes.max_per_place` and `promises.max_open_per_agent` are used by Python as
SLICE bounds, where a fractional float raises `TypeError` mid-tick while this
port truncates and carries on. Reproducing a crash is not worth porting.
`tuning.check` arguably ought to refuse a fractional count on both sides, and
that would be a change to the reference rather than to the port -- so it is
written down here instead of done quietly.

---

## Four traps found while porting, every one of which would have shipped

None is exotic. All four are the obvious C++ for the Python, and all four are
wrong.

**`round()` is not `nearbyint(x * 1000) / 1000`.** The runtime rounds `kappa`,
`eta` and `delta` before storing them, and those land in the exported state. The
obvious implementation disagrees with Python on 3 of 4,006 random values —
always a tie. `round(0.0005, 3)` is `0.001`, because that double sits a hair
*above* one half and correct decimal rounding can see it; multiplying by 1000
first destroys exactly the information the decision needed, then rounds an exact
0.5 to even and returns zero. Formatting to a fixed number of decimals and
parsing back keeps it: **zero disagreements over 40,010 values.**

**The sigmoid must keep its two branches.** `1/(1+exp(-x))` looks equivalent and
is, until the log-odds pass about −710, where `exp(710)` overflows to infinity
and the whole thing collapses to a flat 0 — while the two-branch form still
returns `5.07e-314`. That is where a character has finally made up their mind,
which is the worst possible place to lose the answer.

**`sum()` is not a loop of additions.** This one cost the most to find, because
every plausible suspect was ruled out first. The ported identity engine
disagreed with Python by one bit from the second round onward, and the obvious
culprit was FMA contraction — so `-O0`, `-O2`, `-O3`, `-march=native` and
`-ffp-contract=off` were all measured, and all gave the same wrong answer. The
actual cause: **CPython 3.12 gave `sum()` a fast path for floats that uses
Neumaier compensated summation.** A naive loop over a softmax gives
`0.99999999999999989` where Python gives exactly `1.0`, and dividing by one or
the other is the difference. The core calls `sum()` over floats in nineteen
places, so a port that adds in a loop is wrong in all of them. `pysum.hpp`
compensates; measured against Python over 3,005 groups including adversarial
ones (`[1e16, 1.0, -1e16]`): zero disagreements.

**`sum()` of nothing is an integer.** `sum(d.amount for d in ds if d.amount >= 0)`
with no positive deltas returns `0`, not `0.0`, and `round(0, 3)` is still `0`.
That reaches the exported state as `0` rather than `0.0` — a type difference, not
a value one, and invisible to any comparison that casts before comparing.

Two of these are also lessons about the probe rather than the port. The
`extremes` case originally used 400 repetitions, which is *past* the window where
the two sigmoids differ: by then both return 0, and the case passed a
deliberately broken sigmoid. And `retrieval_ties_are_stable` originally had six
memories, which passed a deliberately unstable sort — libstdc++ falls back to
insertion sort below sixteen elements, and insertion sort is stable. Forty
memories catch it; six prove nothing. **Exercising an extreme is not the same as
exercising the extreme that matters.**

## The Python side has a version dependency, and it is worth knowing about

`sum()` compensates from CPython 3.12. The SDK supports 3.10, where it does not,
so the committed conformance fixtures — generated on 3.14 — do not reproduce
bit-exactly on an older interpreter.

Measured rather than feared, by substituting a naive `sum` across every core
module and re-running all five fixtures:

| | |
| --- | --- |
| fields that move | 12 |
| worst error | **0.9 ULP** |
| discrete outcomes that change | **0** |
| failures under `--port` tolerance | **0** |

So nothing behaves differently on Python 3.10 — but somebody who runs
`usc conformance --check` there will see twelve exact failures, and deserves to
find this paragraph rather than hunt for a bug that is not one.

## No probe is trusted — every module is mutation-tested

A cross-check that passes on the first run is suspicious, and all of these did.
So **504 deliberate defects** have been introduced into the C++ and the probes
re-run. **487 are caught.** Per module, and how many escaped on the first attempt
because the CASE was too weak rather than because the port was right:

| Module | Mutations | Escaped first, then the case was strengthened |
| --- | ---: | --- |
| `belief` | 7 | — |
| `affect`, `relationship`, `memory` | 11 | unstable retrieve, unstable consolidate, bipolar `fear` |
| `policy` | 7 | the temperature floor, unstable candidate sort |
| save/load round-trips | 6 | — |
| `contracts` | 7 | — |
| `topology`, `agent` | 8 | the fallback transmissibility |
| `perception`, `world` | 9 | the stale occupancy cache |
| `routine` | 8 | tied blocks, a zero delta, an unsorted `whereabouts` |
| `social` | 8 | the front-stage threshold |
| `distortion` | 10 | a zero beside a number, an odd quantity, a capped list |
| `content` | 11 | an alias tie, a sorted label list |
| `diffusion` | 10 | a tied topic ranking |
| `standing`, `appearance` | 17 | a negative threat, an unasked target check |
| `sociolinguistics` | 10 | two politeness thresholds, a slang band, an empty regard |
| `factions`, `commitment` | 12 | a finished clock, a fractional latency, a rounded sort key |
| `dialogue`, `agency` | 19 | an assertion threshold, an identity label reused across groups |
| `medium`, `contagion` | 11 | the per-exchange mood cap |
| `climate` | 11 | two cases that could not have failed |
| `common_knowledge` | 11 | a threshold of three that three witnesses meet |
| `promises` | 10 | four, all of them a fixture that never reached the branch |
| `notes` | 11 | nine — the first version of the case tested almost nothing |
| `pursuit` | 11 | six, including a pursued call delivered as a room conversation |
| `revision` | 9 | — |
| `flat`, `tuning` | 12 | a tuning block nobody applied, two unreached tables |
| `grounding` | 12 | two things claiming one name |
| `interpretation` | 20 | six boundaries nobody stood on |
| `parser`, the world vocabulary | 28 | seven, including two NPCs in one room |
| `validator` | 24 | a name in the middle of a sentence, a letter nobody licensed |
| `actionbridge`, `OrderedMap::erase` | 14 | a pending order that was already sorted |
| `provider` | 26 | four scaffolding markers that cannot fire |
| `runtime`, `Reason` | 34 | eleven layers the scenario never switched on |
| `snapshot`, `sha256`, `Json::copy` | 22 | eight things a save can be wrong about |
| `inspect`, the float `repr` | 17 | a tie shorter than sixteen, a notation nobody reached |
| the pack loader | 17 | six packs that filled in every default |
| `sdk`, the turn loop | 19 | ten branches five fixtures never reach |
| `state_view`, `metahuman`, `capabilities` | 25 | four numeric bands a scene never lands on |
| **total** | **504** | **127** |

The pattern in that last column is worth stating outright, because it repeated
one hundred and twenty-seven times across thirty-two modules: **a case that cannot distinguish the right
answer from the wrong one passes both.** Six identical memories do not perturb
`std::sort`, because libstdc++ falls back to insertion sort below sixteen
elements and insertion sort is stable. A threshold nobody lands on cannot tell
`>` from `>=`. A list of two cannot show that it is capped at three. And one
diffusion scenario passed while emitting *zero events* — a single encounter,
refused immediately at the restricted-claim gate.

Each was strengthened until it failed. That is a warning about the conformance
fixtures too: they are chosen the same way and can have the same blind spots.

### The seventeen that are not caught, and why that is the honest answer

| Defect | Why no case catches it |
| --- | --- |
| trimming provenance by 1 rather than by the overflow | `record_provenance` appends once per call, so the overflow is never more than one. The two are the same code. |
| `_applied` never stamped in `routine` | Unobservable without the action bridge: a move always succeeds, and the next check reaches the same conclusion. It becomes load-bearing when the bridge lands. |
| `draw <= running` versus `draw <` in `distortion` | They differ only when the draw lands exactly on a cumulative boundary, and the draw is a 64-bit integer over 2^64. Inventing a case for it would be inventing a seed. |
| skipping an empty `appearance_reactions` entry | Reading `{}` yields zero status, zero threat and no signal — the same as skipping it. It differs only on a reaction authored as something that is not an object, where Python raises. |
| `commit()` leaving the avoid list alone when the commitment's is empty | `plan()` passes the same list into both branches, so it can never produce the case. Kept because `commit()` is public and a caller with a commitment from elsewhere would see it at once. |
| compensated summation of ally probabilities | Fifteen values all in [0,1] are of similar magnitude, which is where Neumaier and a plain loop agree. The guarantee is demonstrated where it does bite: the identity softmax, where a naive loop gives 0.99999999999999989 for a distribution Python normalises by exactly 1.0. |
| the self-contagion guard in `contagion` | A character's mood differs from their own by zero on every axis, so refusing to catch a mood from yourself changes nothing a mutation can see. It stays because it says what the module means. |
| reading an `origin_event` of 0 as `"0"` in `revision` | The two differ only for a source id that is a substring of `"0"` or `"False"`. Unobservable for any realistic id, and inventing one would be inventing a fixture. |
| longest-match-first in `grounding` | Every constituent word longer than three characters is indexed on its own, so a shorter match inside a longer one is itself a known term and the walk skips the same tokens either way. The two orders can only diverge on a multi-word name whose second word is three characters or fewer — and such a word can never begin a flagged phrase, because a flagged phrase must follow a determiner. |
| lower-casing a place alias, and an agent alias, before indexing it | `AliasIndex.build` lowers every alias again and lowering is idempotent. Kept because Python has it, and a port that dropped it would be relying on a caller it does not own. |
| the order of `public_name` and `objective_name` in an agent's fallback aliases | The index sorts by length and then alphabetically, so which of the two is appended first cannot reach any output. |
| the finding KIND in the validator's de-duplication key | A number token is all digits and a word token is not, so the two can never collide, and among words the kind is decided purely by whether the term table knows the lowered token. Kept because Python keys on the pair, and because the day a fourth kind arrives the key is already right. |
| halving `max_length` when a topic is re-asked | It reaches an external provider's prompt and nothing else, so it changes what a language model is asked for and cannot change a template. Kept because the day a provider is attached it is the difference between a character repeating themselves at length and one getting to the point. |
| a missing pack file reading as an empty OBJECT rather than as null | Every caller reads it through `find`, which answers the same either way. Written as Python writes it, and said here so the next reader does not have to work out that null would also have done. |
| the `standing.enabled()` test in the runtime's judgement block | `judge` refuses on its own when the layer is off, and applying an empty delta list is a no-op. Kept because it is in the Python, and because reading the guard is how a reader learns the block is optional. |
| the `not_recognised` fallthrough in `interpretation` | Unreachable. `distort` tries all four processes in turn with inversion last, and inversion cannot fail: negating a claim always changes its polarity. The only other refusal is a protected key, and interpretation passes none — what an observer secretly holds has no bearing on what they managed to make out. The branch stays because `distort` is free to grow a way to fail. |

Each is documented at the line rather than quietly dropped from the table.

## What is in this directory

    port/
      README.md                     this page
      cpp/
        include/usc/blake2b.hpp     BLAKE2b, RFC 7693, vendored — a console
                                    build should not need OpenSSL
        include/usc/ordered_map.hpp insertion-ordered map. The least interesting
                                    file here and the most important: Python
                                    dicts keep order, and this runtime relies on
                                    it in three places that decide behaviour
        include/usc/json.hpp        a JSON value, and Python's str() for one —
                                    `None`, not `null` — because slot values go
                                    into the key a belief is filed under
        include/usc/pyround.hpp     Python's round(), which is not the obvious
                                    thing
        include/usc/pysum.hpp       Python's sum(), which since 3.12 is Neumaier
                                    compensated summation and not a loop
        include/usc/types.hpp       clamps, the two-branch sigmoid, the logit
        include/usc/determinism.hpp derive_seed, seeded_uniform, seeded_choice
        include/usc/ontology.hpp    propositions, the catalogue, C1/C2/C3
        include/usc/belief.hpp      log-odds, dual evidence, the correlation
                                    discount
        include/usc/actions.hpp     the closed action catalogue and outcomes
        include/usc/policy.hpp      utility aggregation, and the seeded choice
        include/usc/statekey.hpp    typed cross-cutting deltas
        include/usc/affect.hpp      ALMA: PAD mood, OCC appraisal, Frijda
                                    action tendencies
        include/usc/relationship.hpp trust kinetics, reputation, identity
                                    salience
        include/usc/memory.hpp      ACT-R activation, retrieval, consolidation,
                                    and the judgements drawn from what fades
        probe/bit_probe.cpp         prints every primitive as raw bits
        probe/port_probe.py         computes the same in Python and compares
        probe/belief_cases.json     nine belief scenarios, executed by BOTH
                                    sides so two scripts cannot drift apart
        probe/belief_probe.cpp      runs them through the ported engine
        probe/belief_probe.py       runs them through `unscripted.belief` and diffs
        probe/engine_cases.json     twenty-four more, across the other five
        probe/engine_probe.cpp      the ported engines
        probe/engine_probe.py       the real modules, and the diff
        CMakeLists.txt

Building it needs nothing but a C++17 compiler:

    cmake -S port/cpp -B build && cmake --build build && ctest --test-dir build

or `python3 port/cpp/probe/port_probe.py` and `.../belief_probe.py`, which build
and compare in one step. Both also run inside the Python suite as
`test_the_cpp_port_reproduces_python_exactly`, skipped where there is no
compiler — so the port cannot drift while this implementation changes, which is
how a second implementation normally dies.


---

## Run the probe on your target before trusting a port on it

Everything above about `log()` was measured on glibc. A console SDK ships its own
libm, and the honest position is that this has not been tested there and cannot
be from here. The probe is 80 lines and needs no engine, no console SDK licence
and no world pack — it is deliberately small enough to run inside a devkit
toolchain on day one of the port, which is when the answer is still cheap.

If it comes back with differences larger than a few ULP, the fix is known and
unpleasant: replace `log` with an implementation shipped in the port itself, so
both sides compute the identical polynomial. That is a day of work and it is
better to discover the need for it early.
