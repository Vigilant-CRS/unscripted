# Status of the 8 September 2026 recheck

The recheck read commit `56d77bf` and reproduced six remaining defects. All six
are closed; its report is left unedited beside this note.

| Finding | Closed by |
| --- | --- |
| R1 negation words do not establish polarity | `semantic_release="controlled"` (the default): a plan that asserts something never reaches a text provider, so there is no wording that can disagree with it. The negation rule remains, and is now what it always was -- a check on the weaker `"provider"` contract |
| R2 a provider failure changed what the world knew | one decision, `Runtime.write_the_line`, shared by both speech paths. A failure costs the wording; the authored phrasing carries the commitment. `carried()` asks the realizer that actually wrote the line |
| R3 a secret can still be described | narrowed, not closed, and now bounded: in controlled release a provider never writes the factual line, so the residue is what a provider may say in a line that asserts nothing. Stated as a limit rather than a guarantee |
| R4 an evicted origin returned at full weight | a belief that has forgotten anything treats every unrecognised source as one it has heard before. The direction is deliberate: it can only lower the weight of evidence |
| R5 a snapshot's history grew a future | snapshots record a ledger watermark a reload cannot rewind, and `Store.ledger_up_to` -- whose contract could not be met -- is gone in favour of `ledger_as_of` |
| R6 a shared place name was enough | `scenario.json: world_id` is believed when both sides carry it; without it a save needs a character who is not the player, or more than one place |

Two of the recheck's own probes now raise instead of reporting: one calls
`ledger_up_to`, which no longer exists, and one does not catch the typed
`StateImportError` the import now refuses with. Both are the fix.

## Still open

- **Lexical protection is not semantic protection.** In `provider` release a
  model may describe a protected place without naming it. Controlled release is
  the answer to that, and it costs the model's wording for factual lines.
- **Multi-source collapse.** A belief held on several independent sources is
  retold carrying its primary origin; the rest of the structure does not travel.
  An evidence DAG would close it, and that is a feature.
- **`kappa` below 0.5** still means "reliable liar" rather than "I doubt them",
  and no pack says which it intends.
- **A re-admitted origin costs a bounded amount of extra weight** -- at most
  `rho/(1-rho)` of a hearing per eviction cycle, and an adversary must push a
  further `origin_limit` sources through the belief to buy each one. Exact
  recognition of unboundedly many origins needs unbounded memory; this is the
  stated trade.
