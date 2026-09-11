# Status of the review of `3c4524d`

The review re-ran the whole suite green and still produced two counterexamples,
both reproduced against the compiled C++ headers. Both are closed. Its report and
its programs are left unedited beside this note.

| Finding | Closed by |
| --- | --- |
| B1a a re-admission was granted a second full allowance on top of repeats already paid | — |
| B1b a re-admitted origin was back in the index, so its next hearing took the `rho ** heard` branch and skipped the allowance entirely | **the origin index no longer evicts.** At capacity a new origin is refused (worth exactly zero, counted in `Belief.origins_refused`); an origin already in the index always counts up. `origins_forgotten` and `unrecognised_spent` are gone with the design that needed them |
| B2 a deliberately released repetition still carried `REJECT_SOFT` and an empty `accepted_output` | the release decision is made once and recorded once: `_deliver` sets the verdict when it releases, so verdict, text, emission and audit agree. `Runtime.say` already did this |

Both of the review's programs, adapted only where they read a field that no
longer exists (`unrecognised_spent` → `origins_refused`, one word in each), now
report the bound holding, and Python and C++ agree to the last digit. The adapted
copies and their output are archived here:

```bash
python3 reviews/2026-09-08/3c4524d/check-after.py       # -> check-after-results.json
g++ -std=c++17 -O0 -Iport/cpp/include \
    reviews/2026-09-08/3c4524d/check-after.cpp -o /tmp/unscripted-after
/tmp/unscripted-after worldpacks/cyberpunk-block                # -> check-after-native.txt
```


```
prior_repeats=8 cycles=1   after_reentry=0  logit=3.2715988654133281  ceiling=3.2715988657404882
prior_repeats=0 cycles=100 after_reentry=1  logit=3.2715988657404882  ceiling=3.2715988657404882
turn=1..5  verdict=ACCEPT  spoken=1
```

## Why this fix is different in kind

Three earlier versions bounded the origin index by evicting and then correcting
for it, and each was found leaking by the next review:

| Design | What it bounded | How it leaked |
| --- | --- | --- |
| evict, no correction | nothing | 2.94 twice from one source against a 3.27 ceiling |
| a re-admission is worth `rho¹` | one return | 0.950 → 0.99985 over twenty cycles |
| all re-admissions share `rho/(1-rho)` | the re-admissions | B1a and B1b: 6.18 log-odds after a hundred cycles |

Every one was a correction applied at **one step** of a sequence whose length an
adversary chooses. An index that forgets cannot recognise a repeat, and paying at
the door does not change that. Not evicting makes the bound a consequence of the
arithmetic: the n-th hearing is worth `rho^(n-1)` for every n, so the total is a
geometric series under `1/(1-rho)` for any ordering, across save and load.

The review's acceptance criterion is met as stated: the check is now a property
over generated orderings against an eight-line reference model, with a save and a
load mid-run, not a hand-written sequence.
`test_no_ordering_of_events_lifts_the_source_ceiling`.

## The price, named

At capacity a **genuinely new** source is refused and contributes nothing. A
belief that has met 512 distinct sources over-doubts the 513th. That is the
conservative direction and it is the trade this runtime takes; `origins_refused`
makes it visible per belief rather than silent. Exact recognition of unboundedly
many origins needs unbounded memory, and the review's own recommendation was this
design.

## Still open

- **Over-doubt past `origin_limit`**, above. Deliberate, measured, reported.
- **Multi-source collapse.** A belief held on several independent sources is
  retold carrying its primary origin; the rest of the structure does not travel.
  An evidence DAG would close it, and that is a feature.
- **`kappa` below 0.5** still means "reliable liar" rather than "I doubt them",
  and no pack says which it intends.
- **`semantic_release="provider"`** remains lexically checked, not guaranteed.
  Choosing it is opting out of C1.
- **The sealed evidence run is stale.** `belief` has now changed again. It needs
  `python3 -m unscripted evidence --hours 2` re-run before any of its figures are cited,
  and the review is right that it should be sealed on the release candidate
  rather than mid-pass.
- **No release-candidate tag, no merge to `main`, no push.**
- **No independent playtest, no new market comparison, no long run with a
  continuously growing event and origin population.** The review asks for the
  last of these specifically, and it is the load case the benchmark's 2,000-turn
  run does not cover.
