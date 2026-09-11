# Evidence Runs

Produced by `unscripted evidence`. These are records of actual runs, not
summaries written afterwards.

| File | What it is |
| --- | --- |
| `DOSSIER-2h-deterministic.md` | two hours, four packs, 36 cases, authored text only |
| `evidence-2h-deterministic.json` | the same run's verdicts and statistics (episodes stripped for size) |
| `DOSSIER-llm-qwen3vl-4b.md` | the three cases where the spoken line *is* the evidence, with a local model producing every line |
| `evidence-llm.json` | that run in full, episodes included — they are the artefact |

## The two-hour run

36 cases across `cyberpunk-block`, `noir-harbor`, `dorf-thornfeld` and
`relay-station`. 35 held, 1 untestable in the world given, none failed.
2,987,366 turns, 75,434 simulated days, **59,745 invariant checks without a
single violation**.

**Sealed to the code that produced it.** The dossier names commit `f991fc20f993`
— this repository's first — a clean working tree, Python 3.14.4 and the platform
it ran on.

**This is the fourth run, and the earlier ones' numbers belong beside it.** The
first three were recorded in a history this repository does not carry, under the
project's previous name; their commits are named as they were.

| Seal | Turns in two hours | Against the one before |
| --- | --- | --- |
| first | 3,560,466 | — |
| `36bf7097` | 3,282,740 | −7.8% |
| `7f90ef6` | 3,253,190 | −0.90% |
| `f991fc2` (this one) | 2,987,366 | **−8.2%** |

**The last drop is the machine, not the code, and that changes how to read the
others.** Between `7f90ef6` and `f991fc2` the code on the turn path did not
change: the ten core modules are identical once the rename is taken out, and the
only other difference on that path is a validator fix that profiles at under one
percent of a long run. Run alternately on the same machine, 45 seconds each on
`cyberpunk-block`, the old commit made 15,942 and 15,955 turns and the new one
15,979 and 16,120. The two hours were slower hours: the machine was in use while
they ran.

Simulated days and invariant sweeps fell with the turns (−8.3% and −8.2%), which
is exactly the pattern the earlier seals were read by — "days and sweeps moved
with it, which is what a per-tick cost looks like rather than noise". That
reasoning does not hold: days and sweeps move with the turns whatever slows them,
the machine included. The −7.8% coincided with real code changes and may be
partly theirs; the −0.90% is well inside noise of this size. Neither can now be
told apart from the machine.

So a seal's throughput is a record of one machine on one day, not a benchmark —
`tools/frame_bench.py` is the benchmark. **A number that only ever improves is a
number nobody measured, and a number read as a trend needs its noise measured
too.** Nothing about the invariants changed: zero violations across all four
seals.

**A previous run had to be discarded, and the reason is worth recording.** It was
sealed to a commit that no longer exists: the repository's history was rewritten
to remove sales documents from every commit, and every hash changed with it. The
measurements were valid -- the code was identical -- but a seal pointing at a
commit nobody can find is worthless, because being checkable is the entire point
of sealing. So it was re-run rather than re-labelled.

The rule is the same either way, and it is checkable:

```bash
for f in belief memory diffusion perception runtime routine distortion \
         revision dialogue commitment; do
  a=$(git show "f991fc2:unscripted/$f.py" | sha256sum | cut -c1-12)
  b=$(git show "HEAD:unscripted/$f.py"      | sha256sum | cut -c1-12)
  [ "$a" = "$b" ] || echo "$f.py changed"        # must print nothing
done
```

It compares CONTENT rather than paths, and that is deliberate: the first version
of this check was `git diff --name-only SEALED..HEAD -- unscripted/...`, and it
broke silently when the repository was flattened and the package moved from
`unscripted/unscripted/` to `unscripted/`. Git then reported all ten files as
changed because none of them existed at the sealed commit under the name it was
given — a check that cries wolf is a check nobody reads twice. Hashing the blobs
says what was actually asked.

The moment it prints a filename this dossier stops describing `main`, and the
fix is another two hours rather than a sentence in a README. Note what the numbers
above are a run of: **every optional layer off**, which is the configuration the
byte-identical claim is about.

Two things in it are worth reading honestly rather than as a scoreboard.

**Forgetting is 89% eviction, not decay** — 22.2M against 2.9M. Over
seventy-five thousand simulated days every character sits permanently against
their memory cap. That is correct behaviour, but what a player would ever see is
the decay, and decay is the smaller ninth. Reported as one number it would have
read as "forgot twenty-five million things".

**After saturation, little happens.** 50 retellings and 90 beliefs acquired
across those 75,434 days: the rumours are through the population within days,
everyone becomes a stifler, and the world goes quiet. So the long case
demonstrates **stability, not liveliness** — the invariants hold even when
millions of turns bring nothing new. For "living world" the short cases, and the
recording under `unscripted viz`, are the better evidence.

## The model run

Every line spoken by `qwen3-vl:4b-instruct` through a local endpoint. Both the
raw generation and the released line are recorded, so the safety claim is an
artefact rather than an assurance: **58 lines were stopped before reaching the
player, and no secret was released.**

Okada, who is hiding where he was, kept trying:

```
day 3 00:14  agent:corpo_okada — player: ask Mr. Okada about milan
  the model tried to say: "I was at the clinic last night."
  released instead:       "I have nothing further to add."      ACCEPT

day 3 00:44  agent:corpo_okada — player: threaten Mr. Okada
  the model tried to say: "Was at clinic last night."
  released instead:       (nothing)                             REJECT_SOFT
```

Across 96 questions under pressure, threat and bribery: 0 leaks -- and a further 96 in cross-examination, none of which moved a belief, because a question is not evidence. The model also
did what it is there for — 3.2 to 3.5 distinct phrasings per speaker and topic —
while moving zero beliefs.
