# Unscripted
## Theory Dynamics & Engineering Specification v0.6

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Date:** 22 June 2026 **Supersedes:**
`Unscripted_Theory_Dynamics_and_Engineering_v0.5.md` **Incorporates:** the v0.5
Implementation-Readiness Review (P0/P1 corrections) and the v0.6 reference
runtime (`unscripted-reference-v0.6`). **Adds:** Part D — Sociolinguistic
Register & Social Status.

> This document does **not** re-paste the parts of v0.5 that remain valid (§4 lists what carries forward unchanged). It contains, in full, only what **changed** (the review corrections, §1), what is **new** (the sociolinguistic module, §2), and the **spec↔code sync map** (§3).

---

# 0. Status and precedence

The reference runtime is now the **executable truth**; this prose spec is subordinate to it. Binding order (matching the readiness review's precedence rule):

```
JSON Schemas + reference code  >  this v0.6 spec  >  v0.4 ontology  >  v0.2 formulas  >  earlier conceptual docs
```

An implementing agent treats a disagreement between this prose and the reference code as a **code-wins** situation, and files a correction to the spec. The recommended *binding* artifact for full LLM-agent implementation remains the **Implementation Contract Pack** (frozen JSON Schemas + ownership matrix + phase graph + scenario fixtures) — see §5.

All constants below are the calibration defaults actually used in the v0.6 reference runtime, so spec and code agree numerically.

---

# 1. Corrections carried from the readiness review

Each item replaces the corresponding v0.5 definition.

## 1.1 Mood integration — exact exponential relaxation (was P0.9)

v0.5 used `mood += (baseline − mood)·min(1, Δt/τ)`, which is Euler interpolation and does **not** match the stated half-life. Corrected:

$$\alpha = 1 - e^{-\Delta t/\tau_{\text{mood}}}, \qquad \mathbf{mood} \leftarrow \mathrm{clamp}_{[-1,1]^3}\big(\mathbf{mood} + \alpha(\mathbf{baseline}-\mathbf{mood}) + \mathbf{I}\big)$$

with `τ_mood = 240` world-minutes ⇒ half-life `t½ = τ·ln2 ≈ 166 min`. The
emotion impulse `I` is applied **only when an emotion is created or
reinforced**, never as a per-tick force (otherwise PAD saturates). Reference:
`unscripted/affect.py: AffectEngine.update`.

## 1.2 Emotions are target-aware (was P0.7)

v0.5 keyed active emotions by type only, so "anger at the player" and "anger at
the police" could not coexist. Corrected: emotions are keyed by `(type,
target)`; the by-type intensity is a derived view. The realization/relationship
layers read **target-directed** emotion (e.g. anger@player lowers liking toward
the player and raises directness toward them only). Reference:
`unscripted/affect.py` (`emotions_toward`).

> Note: this is the lightweight form. The review's full `EmotionInstance` (id, onset, appraisal_id, decay_tau) remains the production target; the reference runtime implements the `(type,target)` subset, which is sufficient for the social layer.

## 1.3 Utility aggregation is mathematically closed (was P0.10)

Terms in a group are **bounded-aggregated** (mean, clamped), so a group value stays in `[-1,1]` regardless of term count:

$$\text{group\_value}_g = \mathrm{clamp}_{[-1,1]}\!\Big(\tfrac{1}{|g|}\textstyle\sum_{m\in g} v_m\Big), \qquad U(a) = \sum_g w_g\cdot\text{group\_value}_g + \mathrm{clamp}_{[-1,1]}\big(b_{\text{emotion}}(a)\big)$$

**Prospect Theory is OFF by default** (feature flag `use_prospect`) and, when
on, transforms **outcomes**, not arbitrary terms: an `ActionOutcome(dimension,
delta, probability, reference_point)` contributes `v(delta−ref)·w(probability)`
with `α=β=0.88, λ=2.25, γ=0.61`. With the flag off (MVP), an outcome contributes
`delta·probability` (expected normalized value). Selection is seeded softmax
with `T = max(0.05, 0.3·(1 + 0.4·impulsivity + 0.3·max(0,arousal)))`. Reference:
`unscripted/policy.py`, `unscripted/actions.py`.

## 1.4 One authoritative belief representation (was P0.11)

Atomic evidence is the source of truth; the dual-evidence fields are **derived views**, never independently mutated:

- stored: `logit` (sum of `sign·η·ln(κ/(1−κ))` contributions) and accumulated `support_for`/`support_against` magnitudes;
- derived: `expected_prob = σ(logit)`, `ignorance = 1/(1+support_for+support_against)`, `conflict = 2·min(sf,sa)/(sf+sa)`.

`κ = clamp(0.55 + 0.25·trust + 0.20·competence − 0.30·skepticism, 0.20, 0.95)`;
skepticism **attenuates** toward `κ=0.5` (no inversion) — only declared
adversariality may push `κ<0.5`. Reference: `unscripted/belief.py`.

## 1.5 Propose/apply uses typed keys; trust applies +/− separately (was P1.2, P1.3)

Cross-cutting deltas are typed `ProposedDelta(StateKey(module, field, entity_id, subject_id, dimension), amount, reason, source)` — no string paths. The owner sums positive and negative proposals **separately** before applying asymmetric kinetics:

$$\text{trust} \leftarrow \mathrm{clamp}_{[0,1]}\big(\text{trust} + \eta_{\uparrow}\!\sum\nolimits_{+}\!\Delta + \eta_{\downarrow}\!\sum\nolimits_{-}\!\Delta\big),\quad \eta_{\uparrow}=0.10,\ \eta_{\downarrow}=0.40$$

so a `+0.8` kindness and a `−0.7` betrayal in the same tick do **not** cancel to
a mild net positive; the betrayal is penalized at the fast-down rate. Other
relationship dimensions use a symmetric `η_other=0.20`. Reference:
`unscripted/statekey.py`, `unscripted/relationship.py:
RelationshipEngine.apply`.

## 1.6 Identity salience has a neutral baseline + inertia (was P1.4)

A neutral `_neutral` category (fit `0.4`) enters the softmax so that "no
identity strongly salient" is representable; temporal inertia (`0.5`) blends
with the previous salience to prevent per-tick identity flicker. `salienceᵢ ∝
exp(β·fitᵢ)`, `β=4`. `comparative_fit` is the meta-contrast ratio over the
present others and must be supplied by the context. Reference:
`unscripted/relationship.py: IdentityEngine.salience`.

## 1.7 Generation is buffered, never streamed unvalidated (was P0.6)

The realizer produces the **full** utterance; the validator runs **before** any
display. Layered: Layer 0 (forbidden-fact content never enters the prompt — only
avoid-topic labels), Layer 3 (deterministic secret-surface-form scan, canon,
repetition), Layer 4 (safe template fallback on `REJECT_HARD`). No clause is
shown to the player before validation. Reference: `unscripted/validator.py`,
`unscripted/runtime.py: Runtime.say`.

## 1.8 Two replay modes (was P0.5)

Byte-identical replay is guaranteed only for the **deterministic state + semantic traces**, not for fresh external-model inference. Define:

- **Semantic replay** — re-runs the deterministic simulation and **reuses the recorded accepted utterance**. This is the hard determinism gate.
- **Model replay** — regenerates text for diagnostics; not a byte-identity guarantee.

For every generated turn persist: provider, model_id/hash, runtime_version,
prompt_hash, generation_params, raw_output, accepted_output, validator_version,
validation_result. Reference: `unscripted/provider.py:
StubLLMProvider.last_prompt_constraints` (the semantic-replay record stub).

## 1.9 Persistence: retention tiers, snapshot + tail (was P0.12)

"The ledger is the source of truth" becomes: **the current save state = a
verified snapshot + its ordered event tail; canonical history remains
append-only.** Retention tiers: (1) canonical ledger permanent; (2) background
events compacted into signed aggregate events; (3) optional full debug archive;
(4) snapshot+tail as the operational savegame. A snapshot carries
schema/ontology/pack versions, module versions, a state checksum, last event id,
branch id. Reference: `unscripted/persistence.py` (ledger + projections +
reload; snapshot/retention is the documented extension).

## 1.10 Runtime loop: staged apply, feature-providers vs state-owners (was P0.3, P0.4)

Two module categories: **state-update modules** (return owned state, applied
transactionally after the phase) and **feature providers** (compute transient
terms/proposals, own no mutable state). The event path stages owned state and a
proposal bus, then applies owners in the fixed Part-C order
(Belief→Memory→Affect→Identity→Relationship→Reputation→Need→Motivation→Dialogue).
Theory functions are side-effect-free (`new_state, proposals, reasons =
update(...)`); the reference runtime copies state rather than mutating inputs.
Reference: `unscripted/runtime.py`.

## 1.11 Candidate generation + outcome model (was P1.6)

The policy engine **scores** candidates; a candidate generator **produces** them
from a closed catalog with explicit `ActionOutcome`s (never invented). MVP ships
a deterministic catalog (`default_candidates`); a pack supplies the full catalog
+ an affordance query (the `capability` module of Ontology v0.4 §3.3).
Reference: `unscripted/actions.py`.

## 1.12 Bounded dependence (was P1.5)

`dependence = current_value / (current_value + best_alternative + ε)` — never
divides by zero, stays in `[0,1]`; power asymmetry is the difference between the
two parties' dependence. Reference: `unscripted/social.py:
SocialExchangeEngine.dependence`.

---

# 2. NEW — Part D: Sociolinguistic Register & Social Status

This module was absent from v0.5. It governs **how** an NPC speaks as a function of social position, education, group, audience, setting and affect, and feeds the realization layer. It is the answer to "do we model slang / register / social ranking and their effect on what and how things are said."

## 2.0 Framing (non-negotiable)

This is **not** a "good speech vs bad speech" ladder, and a higher-status speaker is **not** modeled as speaking "better." The module models **register and prestige variation** — formality, sentence length, lexical breadth, slang/argot, politeness — plus **code-switching** and **accommodation**. A low-status or vernacular speaker is fully competent in their own variety. Education must not be equated with intelligence (Ontology v0.1 §4.5). Baking a class-quality hierarchy into the core would be both linguistically wrong and an ethics defect.

## 2.1 Social status

A continuous prestige score `status ∈ [0,1]` per agent (authored baseline `social_status`), plus a **perceived** status that is audience-relative:

$$\text{perceived\_status}(s \mid o) = 0.6\cdot\text{base}(s) + 0.4\cdot\mathrm{clamp}_{[0,1]}\!\big(0.5 + 0.5\cdot\text{rep}_o(s,\text{status})\big)$$

i.e. the observer's reputation-of-subject (and, in a fuller model, clothing
signals) shift perceived status away from the baseline. Reference:
`unscripted/sociolinguistics.py: SociolinguisticEngine.social_status`.

## 2.2 The style vector

The realizer consumes a `StyleVector`: `formality`, `lexical_sophistication`, `mean_sentence_length`, `slang_level`, `directness`, `hedging`, `dialect`, `jargon_domain`, `slang_lexicon`, `politeness_strategy`.

## 2.3 Mapping equations (defaults used in the reference runtime)

Let `edu` = **general** education (vocabulary/register breadth, default 0.35 — *not* street competence), `setting` = setting formality of the place, `role_formal` ∈ {0.4, 0.7}, `status` = §2.1, `stress = clamp(arousal·max(0,−valence))`, `membership` ∈ {0,1} (member of a group with an in-group vernacular).

$$\text{ingroup\_pull} = \text{membership}\cdot(1-\text{setting})$$
$$\text{formality} = \mathrm{clamp}_{[0,1]}\big(0.4\,edu + 0.3\,setting + 0.2\,status + 0.2\,role\_formal - 0.4\,stress - 0.5\,\text{ingroup\_pull}\big)$$
$$\text{lexical} = \mathrm{clamp}\big(0.4\,edu + 0.6\,edu\cdot formality\big)$$
$$\text{sentence\_len} = 8 + 12\cdot lexical\cdot formality - 6\cdot stress \quad (\ge 4)$$
$$\text{slang} = \mathrm{clamp}\big(\text{membership}\cdot(1-formality)\big)$$
$$\text{directness} = \mathrm{clamp}\big(0.5 + 0.3(1-\text{agreeableness}) - 0.3\,formality + 0.4\,\text{anger@interlocutor}\big)$$
$$\text{hedging} = \mathrm{clamp}\big((1-directness)(0.4 + 0.4\,formality)\big)$$

The `ingroup_pull` term is **code-switching**: a gang member's vernacular default is suppressed in formal settings (`(1−setting)` shrinks the pull in a police post). Politeness strategy (Brown & Levinson) is read off `(formality, directness)`: high-formality+indirect → negative politeness; low-formality+direct → bald; indirect → off-record; else positive.

## 2.4 Communication Accommodation (Giles) and Audience Design (Bell)

The speaker shifts toward a liked interlocutor's register and diverges from a disliked one:

$$\text{formality} \mathrel{+}= \lambda_{\text{acc}}\cdot(\text{target\_formality}-\text{formality})\cdot\mathrm{sign}(\text{liking}),\quad \lambda_{\text{acc}}=0.4,\ \text{target\_formality}=0.5+0.5\cdot\text{status}(\text{interlocutor})$$

so an NPC formalizes toward a higher-status interlocutor (audience design) and
converges toward those it likes. Reference: `unscripted/sociolinguistics.py:
compute_style`.

## 2.5 Realizer contract

The `StyleVector` conditions the realizer. The deterministic **template
realizer** selects a register band (vernacular/neutral/formal) by `formality`,
applies slang substitution when `slang_level > 0.3` using the pack's slang
lexicon, and trims to the first clause when `mean_sentence_length < 7`. An **LLM
realizer** receives the style vector as prompt constraints (register, max
sentence length, slang lexicon id, directness, politeness strategy); its output
is **buffered and validated** (§1.7). Reference: `unscripted/provider.py`.

Worked contrast (same intent "evade a probing stranger", from the reference demo):

- street fixer (status 0.35, gang vernacular): *"Maybe. Why do you care?"* — formality 0.11, slang 0.89, short, bald.
- corporate exec (status 0.90, formal role): *"I am afraid that is not something I am able to discuss."* — formality 0.71, no slang, hedged, negative politeness.

## 2.6 Ownership, MVP scope, LOD

Owner: `SociolinguisticEngine` (computes a transient style vector each turn; owns no persistent mutable state beyond the authored `social_status`/`dialect`). MVP-mandatory (it directly realizes clothing/role/audience effects on speech). The slang lexicons and dialect markers are **World-Pack content** (a `vocab:` scheme per Ontology v0.4 §1.2.2), not core. LOD: at LOD ≤ 1 the style vector is not computed (no free dialogue).

---

# 3. Spec ↔ code sync map (v0.6 reference runtime)

| Spec part | Status | Reference file(s) |
|---|---|---|
| Determinism, seeds | implemented | `determinism.py` |
| Typed propositions, contradiction C1/C2/C3, relevance | implemented | `ontology.py` |
| Perception (co-location + noise → quality) | implemented | `perception.py` |
| Belief: logit + dual-evidence + correlation discount + κ | implemented (§1.4) | `belief.py` |
| Memory: ACT-R activation, type decay, retrieval, consolidation | implemented | `memory.py` |
| Affect (Part A): PAD baseline, OCC table, impulse, **exact** relaxation, target-aware, tendencies | implemented (§1.1, §1.2) | `affect.py` |
| Part C: propose/apply, trust kinetics (+/− separated), reputation, identity salience (+neutral/inertia) | implemented (§1.5, §1.6) | `relationship.py`, `statekey.py` |
| Social §5.8–5.15 (Value, Exchange, Identity, Norm, Network, ToM, Impression, Interpersonal) | implemented (feature providers) | `social.py` |
| **Part D: Sociolinguistics + social status** | implemented (§2) | `sociolinguistics.py` |
| Part B: utility aggregation (bounded), Prospect (flagged), seeded softmax, reason codes | implemented (§1.3) | `policy.py`, `actions.py` |
| Dialogue planner + conversation state + anti-loop | implemented | `dialogue.py` |
| Validator: buffered, layered, fallback | implemented (§1.7) | `validator.py` |
| Model provider: protocol + register-aware template realizer + LLM stub | implemented (§1.8 record stub) | `provider.py` |
| Persistence: event ledger + projections + save/reload | implemented; snapshot/retention documented (§1.9) | `persistence.py` |
| Tick loop: event/decide/say/time-advance | implemented | `runtime.py` |
| Inspector views | implemented | `inspect.py` |
| BDI plan repair, resource locking, plan library | **not built** (flat catalog only) | — |
| LOD promotion/demotion protocol | **not built** | — |
| EmotionInstance (full), within-tick fixpoint | **not built** (subset only) | — |
| Real LLM provider, semantic-replay persistence table | **not built** (interface + stub only) | — |

Tests covering the corrections live in `tests/test_scenarios.py` (determinism, claim≠truth, correlation discount, contradiction, affect, register contrast, asymmetric trust, bounded utility, secret-leak rejection).

---

# 4. Carried forward from v0.5 unchanged

The following v0.5 sections remain valid and are **not** restated here: the overall architecture and layer model (§0), the build-order and milestones (§9.7), the calibration approach (§10), the evaluation taxonomy incl. population-level metrics (§11), and the open decisions on native language and within-tick coupling (§12). Where v0.5 numeric formulas conflict with §1 above, **§1 wins**.

---

# 5. Recommended next artifact (unchanged from the review)

The binding deliverable for a full LLM-agent implementation is the **Implementation Contract Pack v0.6**: frozen JSON Schemas (Entity, Event, Proposition, Belief, Memory, AffectState, ActionDefinition/Outcome, DialoguePlan, ValidationResult, WorldPackManifest, Snapshot, ReasonTrace…), the complete module **ownership matrix**, the runtime **phase graph**, the action/dialogue **catalogs**, the parser result schema, and the **20 golden scenario fixtures** with expected structured outcomes. The v0.6 reference runtime is the executable reference from which these contracts can now be **extracted** rather than guessed — which is the cleanest path before scaling the social layer or porting to a native core.
