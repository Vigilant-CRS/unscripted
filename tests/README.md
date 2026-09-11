# The suite

```
python3 tests/test_scenarios.py
```

One file, 202 checks, no test framework and no third-party dependency — the same
constraint the runtime itself is under, for the same reason: a suite that needs
something installed is a suite that stops being run.

It takes **320 seconds** here — measured, not estimated, and on a USB-mounted
filesystem where the suite is I/O bound rather than CPU bound. Nothing is mocked. Every check drives the real
runtime over a real world pack, because the failures worth catching here are
about what a character comes to believe, and a mock cannot be wrong about that.

## What the checks are, and what each family proves

| Family | Roughly | What a failure means |
| --- | --- | --- |
| **Determinism** | `test_determinism`, seeded selection, replay | The same seed stopped producing the same world. Every other guarantee rests on this one. |
| **Belief** | correlation discount, contradiction, saturation, revision | A claim heard twice from one source started counting as two, or exposing a liar stopped unwinding what he convinced people of. |
| **Perception and interpretation** | earshot, occupancy, competence, epistemic profile | Somebody learned something nobody told them, or four witnesses stopped disagreeing. |
| **Memory** | decay by importance, consolidation, judgements, **recall bounds** | A character forgot a murder before the player left the room, or recalled everything they ever heard at once. |
| **Diffusion** | circles, tie strength, distortion, **hop limits** | A rumour crossed a boundary it should not have, or circulated forever. |
| **Safety** | validator layers, secret gates, grounding, unsayable commitments | A secret leaked, or a character asserted something the world does not contain. That is the claim this runtime is sold on. |
| **Release** | what the player reads against what the room learns | The two came apart: a claim propagated behind a sentence that never worded it, style cut the claim out of a line that still counted, or an earlier sentence decided whether a later fact entered the society. Four external reviews found this class four separate ways, and the checks here are the property, not the wordings. |
| **The optional layers** | climate, pursuit, promises, notes, contagion, common knowledge, standing | Off stopped being byte-identical, which is the promise that makes them safe to ship. |
| **Save and load** | snapshot round trips, state envelopes, patched casts | A save stopped restoring the world it was taken from, or a load lost something quietly. |
| **Scale and cost** | population LOD, trace bounds, tick latency | The tick got slower or the traces grew without bound. |
| **The service** | HTTP contract, auth, the engine bridges' contracts | An endpoint changed shape under a shipped client. |
| **The C++ port** | three probes, bit for bit | The port stopped agreeing with Python. |
| **The C ABI and the bindings** | C99, C#, GDScript, Unreal native | An engine can no longer call the runtime. |

## The parts that need a toolchain

These **skip rather than fail** when what they need is absent, because the suite
has to pass on a machine that only has Python — and a check that cannot run is
not a regression in the runtime.

| Check | Needs | Point it somewhere else with |
| --- | --- | --- |
| The three port probes | a C++ compiler, and Python 3.12+ | `CXX` |
| The C ABI | a C compiler as well | `CC` |
| The Unreal binding's native half | a C++ compiler | `CXX` |
| The Unity binding | a .NET SDK (Unity ships one) | `UNSCRIPTED_DOTNET` |
| The Godot binding | a Godot 4 binary | `UNSCRIPTED_GODOT` |

Two things are deliberately NOT in the suite because they cost minutes rather
than seconds, and they are run by hand before a release:

```
python3 tools/unreal_check.py --plugin native   # compiles the plugin against a real engine
python3 tools/unity_check.py                    # compiles the C# package against a real editor
python3 tools/coverage_check.py                 # line coverage, no dependency
```

## Why the port probes are switched off when Python is mutated

The port probes compare the C++ build against Python. If Python is deliberately
broken to find out whether the suite notices — which is how five of the checks in
here came to exist — those probes fail for a reason that says nothing about the
test being measured. `CXX=/nonexistent` is the documented way to silence them.

## And why the harness must delete `__pycache__` between mutations

This cost a false result, so it is written down rather than remembered.

Python validates a `.pyc` against **(source mtime in whole seconds, source size)**.
A mutation that replaces text with text of the SAME LENGTH — `"eta_up": 0.10`
becoming `"eta_up": 0.40` is one character — and is restored within the same
clock second leaves both of those unchanged. The source on disk is correct,
`git status` is clean, and Python goes on executing the mutant out of the cache.

What that does to a mutation run is worse than a wrong answer for one mutation.
The poisoned module stays poisoned for every run AFTER it, so the next mutations
fail for a reason that has nothing to do with them and are recorded as *caught*.
Two results in the second batch had to be discarded and re-run for exactly this.

So: purge the caches before each run and again after the restore.

```bash
find unscripted -name __pycache__ -type d -exec rm -rf {} +
```

The tell, if it happens anyway: a test unrelated to the mutation fails, and it
still fails after the file is restored and `git diff` shows nothing.

## The standard the suite is held to

Not coverage. Coverage measures which lines ran; it cannot tell a line that ran
from a line whose behaviour anything asserted. The C++ port is held to a harder
bar — 504 deliberate defects introduced, 487 caught, each of the rest documented
at the line — and **the Python suite is now measured the same way.**

Nineteen deliberate defects have been introduced so far — across belief, memory,
affect, policy, the validator, grounding, perception, relationships, diffusion,
attention and the tick loop — and they found **five holes**. Every one is a
behaviour this runtime is sold on:

| What was broken | And the suite | Now pinned by |
| --- | --- | --- |
| `working_cap` raised tenfold — a character recalls everything they ever heard | stayed green | `test_recall_is_bounded_by_working_memory` |
| `max_hops` **deleted** — a rumour circulates forever | stayed green | `test_a_claim_stops_being_passed_on_after_enough_retellings` |
| `primary_origin` returns the LATEST source instead of the first | stayed green | `test_a_retelling_carries_the_first_origin_not_the_latest` |
| The "you learn nothing by hearing yourself" guard removed | stayed green | `test_nobody_is_convinced_by_the_sound_of_their_own_voice` |
| The validator's repetition window shrunk from three lines to one | stayed green | `test_a_character_does_not_repeat_a_line_they_just_said` |

The third is the one that should worry a reader most. *A rumour relayed through
five mouths is worth one witness rather than five* is the sentence this runtime
exists for, and it works only because the origin travels with the CLAIM and never
with the mouth it came out of. Citing the latest source instead would mean an
echo keeps arriving from a "new" origin, so the correlation discount never bites
and repetition quietly becomes proof — and nothing in the 158 checks that came before would have said
so.

None of the five was a bug in the runtime. All five were the same failure the
port's mutation testing kept turning up on the other side: **a case that cannot
distinguish the right answer from the wrong one passes both.** Each new test pins
the BOUNDARY rather than the neighbourhood — `>=` against `>` is one retelling,
and one retelling is a different world.

Two of the five also show why coverage would not have found them. Every one of
those lines RAN, in dozens of checks. Running is not asserting.

The fourth needed a case that did not exist anywhere: on a direct event the
perception layer already declines to report the actor as an observer, so the
guard is unreachable. The one path that reaches it is a BROADCAST, where a
speaker may be listening to the channel they are speaking on.

The fifth is the one that was nearly missed twice. It first reported *caught* —
falsely, off a poisoned bytecode cache — and only showed itself when the run was
repeated with the caches purged. The repetition guard could be shrunk from three
released lines to one and all 162 checks stayed green, because nothing anywhere
asked how far back it looks. The new test pins it at BOTH edges: the third line
back must be refused and the fourth must be allowed, so a window of 1, 2 or 4
all fail it.

## Adding one

Name it for the behaviour, not for the function: `test_a_claim_stops_being_
passed_on_after_enough_retellings`, not `test_max_hops`. Put the reasoning in
the docstring — what would be wrong in the world if this failed, and why the
case is built the way it is. Print one line on success saying what held.

Then append it to the `suite` list at the bottom of the file. There is a check
that fails if a `test_` function is defined and never run, which exists because
that happened.
