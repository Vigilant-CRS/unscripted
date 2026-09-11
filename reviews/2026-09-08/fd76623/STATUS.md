# Status of the review of `fd76623`

The review read commit `fd76623` and reported five findings. All five are closed,
and the review's own `check.py` reports every invariant holding. Its report is
left unedited beside this note.

Re-run it with `python3 reviews/2026-09-08/fd76623/check.py`.

| Finding | Closed by |
| --- | --- |
| A1a two selected claims, one authored sentence | `_only_what_can_be_said`: a factual move survives selection only if the authored phrasing words it -- which is the topic's own query and nothing else. Dropped moves are reported as `commitment.unsayable_dropped` instead of propagating behind a sentence that never mentions them |
| A1b style shortened an authored answer to its lead-in | the mean-sentence-length cut is skipped for any line carrying a fact, and the realizer's `expressed_commitment` now asks *did these words carry the commitment* (authored phrasing for a factual plan) rather than *was there a template*. The anti-repeat retry chooses between complete wordings via `TemplateRealizer.variants()` |
| A2 free prose reached `controlled` through non-factual plans | `Runtime.write_the_line` no longer asks whether the plan asserts a fact: in `controlled` the provider is not called at all. The contract text in `contracts.py` and the specification say so |
| A3 earlier prose vetoed a later fact through the repeat guard | `validator.SAFETY_CODES` / `is_unsafe` split the verdict in two. An unsafe line voids its commitment and deflects, and it now also clears `plan.phrasing` so the deflection is not the same sentence again. A repetition is a quality objection: another complete wording (`dialogue.reworded`) or the same one released again (`dialogue.released_anyway`) -- never a dropped claim |
| A4 the global source ceiling had been given up | `Belief.unrecognised_spent`: every source the belief cannot recognise draws on ONE allowance of `rho/(1-rho)` of a hearing. Twenty eviction cycles of one repeated claim now end at p=0.9623 and 3.23888 log-odds, under the 3.27160 ceiling, with the last cycle worth exactly 0 |
| A5 world identity was optional and still guessed | all six shipped packs declare `world_id`. The pre-`world_id` path needs a character who is not the player -- place names are what unrelated worlds share by accident -- and when it accepts on inference it reports `world_unverified` rather than `ok` |

The review's `world_identity_fallback` probe now raises `StateImportError:
different_world: this save belongs to 'block-17', not 'noir-harbor'` instead of
reporting. That is the fix: both packs declare an id, so there is nothing left to
infer. The heuristic path it was written for is covered by
`test_an_undeclared_world_is_reported_as_a_guess`, which strips both ids first.

> **A4 was superseded the same day.** The shared `rho/(1-rho)` allowance
> described below was itself found leaking by the review of `3c4524d`, twice
> over, and the origin index no longer evicts at all. What that review found and
> why the new design is different in kind is in
> [`../3c4524d/STATUS.md`](../3c4524d/STATUS.md). Everything else on this page
> still stands.

## What A4 changes about the earlier note

The previous status said a re-admitted origin costs "a bounded amount of extra
weight ... per eviction cycle" and called it the stated trade. The review was
right that this is not the product claim. `single_origin_max_confidence` in the
benchmark says *one origin, however often repeated, never becomes proof*, and a
per-cycle bound does not say that. The bound is global again, and it holds
without recognising the origins: the allowance is spent, not counted.

The cost is a real one and is stated rather than hidden: past `origin_limit`
distinct sources, a genuinely new source is discounted as though it were a
repeat, and once the allowance is spent it contributes nothing. That
**over-doubts**. Exact recognition of unboundedly many origins needs unbounded
memory; erring towards doubt is the direction this runtime takes.

## Still open

- **Multi-source collapse.** A belief held on several independent sources is
  retold carrying its primary origin; the rest of the structure does not travel.
  An evidence DAG would close it, and that is a feature, not a fix.
- **`kappa` below 0.5** still means "reliable liar" rather than "I doubt them",
  and no pack says which it intends.
- **New sources after `origin_limit` are over-doubted.** The other side of A4,
  above. Measured, deliberate, and the conservative direction.
- **`semantic_release="provider"` remains lexically checked, not guaranteed.**
  That is what the mode is for, and choosing it is opting out of C1. The
  protection a model's prose gets is the secret scan, unlicensed specifics,
  invented referents and polarity -- all lexical, and three reviews have found
  sentences that pass them all.
- **The sealed evidence run is stale.** `belief`, `memory`, `runtime`,
  `revision`, `provider`, `sdk`, `validator` and `snapshot` have all changed
  since `36bf7097`. It needs `python3 -m unscripted evidence --hours 2` re-run before
  any of its figures are cited again.
