# Evidence Runs

Produced by `unscripted evidence`. These are records of actual runs, not
summaries written afterwards.

> *Recorded at commit `7f90ef6`, under the project's previous name. The
> digests derive from world, agent and event data and never from the package
> name, so the rename to Unscripted leaves every figure below unchanged.*

| File | What it is |
| --- | --- |
| `DOSSIER-2h-deterministic.md` | two hours, four packs, 36 cases, authored text only |
| `evidence-2h-deterministic.json` | the same run's verdicts and statistics (episodes stripped for size) |
| `DOSSIER-llm-qwen3vl-4b.md` | the three cases where the spoken line *is* the evidence, with a local model producing every line |
| `evidence-llm.json` | that run in full, episodes included — they are the artefact |

## The two-hour run

36 cases across `cyberpunk-block`, `noir-harbor`, `dorf-thornfeld` and
`relay-station`. 35 held, 1 untestable in the world given, none failed. 3.25
million turns, 82,278 simulated days, **65,061 invariant checks without a single
violation**.

**Sealed to the code that produced it.** The dossier names commit `7f90ef6111a1`,
a clean working tree, Python 3.14.4 and the platform it ran on.

**This is the third run, and the earlier ones' numbers belong beside it**, because
the interesting thing about this series is that the number keeps going down:

| Seal | Turns in two hours | Against the one before |
| --- | --- | --- |
| first | 3,560,466 | — |
| `36bf7097` | 3,282,740 | −7.8% |
| `7f90ef6` (this one) | 3,253,190 | **−0.90%** |

Simulated days and invariant sweeps moved with it — −1.16% and −0.90% — which is
what a per-tick cost looks like rather than noise. Between the last two seals
`belief.py` was rebuilt three times over five external reviews, ending with an
origin index that never evicts, and `memory.py`, `runtime.py` and `revision.py`
all changed. The non-evicting index is the likely cost: it does strictly more
bookkeeping per hearing than the version that threw entries away.

Nine tenths of one percent is small, and it is recorded anyway. **A number that
only ever improves is a number nobody measured.** Nothing about the invariants
changed: zero violations across all three seals.

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
  a=$(git show "7f90ef6:unscripted/$f.py" | sha256sum | cut -c1-12)
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

**Forgetting is 89% eviction, not decay** — 24.7M against 3.1M. Over eighty-two
thousand simulated days every character sits permanently against their memory
cap. That is correct behaviour, but what a player would ever see is the decay,
and decay is the smaller ninth. Reported as one number it would have read as
"forgot twenty-eight million things".

**After saturation, little happens.** 50 retellings and 90 beliefs acquired
across those 82,278 days: the rumours are through the population within days,
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
