# Status of the 7 September 2026 review

**This directory is a record of a review, not a list of open defects.** The
report beside it describes the runtime as it stood at commit `f8dba39`. The
report's own text is left unedited so the two can be compared.

**This note first said "every finding has since been closed", and that was too
strong.** A recheck the next day showed that two of them -- the paraphrased
secret and the contradicting line -- had been *narrowed* rather than closed, and
that the fix for a memory bound had opened a worse hole than the one it filled.
What closed them is in `reviews/2026-09-08/`. The table below is what each
finding became; where a row says a defence is lexical, it is lexical.

The fixes, the regression tests and the C++ port changes are in the commit that
adds this file. What each finding became:

| Finding | Closed by |
| --- | --- |
| F01 demo page hands out the auth token | `/demo` and `/studio` run through `authorize`; a token may arrive in the query string, which is how a launcher's announced link reaches a browser |
| F02 paraphrase names the hiding place | narrowed by validator layer 3a′ (a released line may not name an entity a protected claim is about), then closed for the default path by `semantic_release="controlled"`: a provider never writes a line that carries a fact. A description that names nothing -- "behind where drinks are served" -- still passes the lexical layer, which is why the mode exists |
| F03 released line contradicts the claim | narrowed by a polarity check, then closed for the default path the same way. The check is a negation-word rule and "The clinic was open all night, **no** doubt." defeats it |
| F04 repeated lies mint new origins | a lie's origin names the speaker **and the claim**, so one liar telling one lie is one source |
| F05 repeated report re-punishes | `standing.judge` applies the change since it last judged that incident; conduct claims carry `valid_start`, so a second act is still a second incident |
| F06 revision cannot reach trimmed provenance | the arithmetic moved to `Belief.contributions`, kept per (speaker, origin) and not trimmed with the display record |
| F07 revision invents conflict | each support pool loses what it was given; weakening evidence raises ignorance |
| F08 support pool follows the assertion | it follows the contribution's sign |
| F09 memory keeps what perception discarded | memory stores the interpreted proposition |
| F10 step size changes who witnessed what | the window is walked in chronological order |
| F11 foreign save loads | the map has to be the same map |
| F12 corrupt import half-applies | the import is atomic |
| F13 ledger overwrites a branch | the ledger row has its own id |
| F14 judgement loses `about`/`evidence` | both are serialised |
| F15 publicity ignores polarity | publics are filed under the signed key |
| F16 substring source matching | an origin must name a whole id |
| F17 confirmed fear produced relief | the OCC prospect pair is the right way round |
| F18 unbounded source index | bounded at `origin_limit`, first origin never evicted -- **and this bound opened R4**: an evicted origin returned at full weight until a belief that has forgotten anything began treating every unrecognised source as a returning one |
| F19/F20 native JSON accepts garbage | strict parsing, and surrogate pairs become one character |
| F21 theory of mind reads fear inverted | an explicit model, written from what the actor has been seen to do |
| F22 provider decides whether knowledge exists | the wording is replaced, never the content |

Two of the probe cases in `repro_2026_09_07.py` still report
`invariant_holds: false` and one raises. That is the probes' success criteria,
not the behaviour: they were written to expect a *refusal*, and the runtime now
recovers instead — it replaces the wording, or refuses the import with a typed
error. `tests/test_scenarios.py` asserts the invariant those cases were reaching
for.

## What the review raised and is still open

- **Multi-source collapse.** A belief held on three independent sources is
  retold carrying its primary origin, so the rest of the evidence structure does
  not travel. Closing it properly means an evidence DAG rather than a single
  origin token, which is a feature and not a fix.
- **`kappa` below 0.5.** The bookkeeping is correct now, but a source that
  credible-in-reverse is still treated as evidence *for* the opposite. Bayes
  permits it; it means "this person is a reliable liar" rather than "I doubt
  them", and no pack states which it means.
- **Polarity is read lexically.** English negates lexically too, so a negated
  commitment phrased without a negation word loses the model's wording to the
  pack's. `unscripted/grounding.py` records why the cleverer rule was rejected.
