# Unscripted — Technical Core Specification

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

## v0.2 — Operational Foundation: Proposition Ontology, Belief Revision, and Output Validation

**Version:** 0.2 — Technical Core (extends, does not replace, v0.1 System & Product Specification)
**Date:** 22 June 2026
**Scope:** This document closes the load-bearing implementation gaps in v0.1. It makes the deterministic layer executable and testable by specifying (1) how propositions are represented, (2) how beliefs are updated and revised, (3) how rumors propagate and mutate, (4) how free-text output is constrained and validated, and (5) how the v0.1 formulas become real, calibrated functions.

> **Relationship to v0.1.** No feature of v0.1 is removed or changed. v0.1 answers *what* the runtime does. v0.2 answers *how* the three subsystems that everything else depends on actually work, in a form that can be implemented, unit-tested, and measured in CI. Sections, schemas, and APIs here are additive refinements of v0.1 §7, §9, §12, §13, and §14.

---

## 0. Why these three subsystems first

The entire deterministic layer of v0.1 rests on three primitives that v0.1 left as placeholders:

1. **Proposition representation** (v0.1 §7.4–7.5 used opaque strings like `"player_is_mayor"`). Without a typed representation, contradiction detection (a v0.1 §22 quality metric), semantic relevance (the `S_i` term in v0.1 §9.3 retrieval and the topic score in §12.3), and secret/forbidden-fact matching in the validator are all **impossible to compute deterministically**. Everything downstream inherits this.
2. **Belief update and revision** (v0.1 §7.5 had `confidence` and `source` but no update rule; v0.1 §14.1 used a literal magic number `belief_change: 0.31`). Without a principled rule, rumor dynamics, media credibility, and contradiction resolution cannot be specified or tested.
3. **Output validation** (v0.1 §13.1 listed what the validator *checks* but not *how*). This is the single hardest engineering problem and the crux of the product promise ("NPCs only know what they could know; they never leak secrets").

Gaps 4 (decorative math) and 5 (rumor magic numbers) dissolve once 1–3 are in place, so they are folded in here.

---

# 1. Knowledge Representation: The Proposition Ontology

*(Resolves Gap 1. Refines v0.1 §7.)*

## 1.1 Design goal

Replace opaque proposition strings with **typed predicate–argument terms over a closed, versioned ontology**, supporting four operations the runtime needs and free strings cannot provide:

- **Equality / canonicalization** — two beliefs about the same fact must be syntactically identical.
- **Contradiction detection** — a decidable relation `⊥` over propositions.
- **Relevance scoring** — a bounded function `rel(φ, τ) ∈ [0,1]` of a proposition `φ` to a topic pattern `τ` (this is the missing definition behind `S_i` and the topic score).
- **Secret matching** — deciding whether an utterance conveys a forbidden proposition.

## 1.2 Entities and types

Let `ℰ` be the set of world entities, each with a stable ID and a type from a closed type lattice `T`:

```
agent | place | item | group | institution | event | time_point
| time_interval | role | trait_value | quantity | proposition_ref
```

`τ: ℰ → T` is the typing function. Entities are *references*, never free text. `proposition_ref` allows higher-order propositions (e.g. *"npc_12 knows that φ"*).

## 1.3 Predicate catalog

A **predicate** `p ∈ 𝒫` is declared in the World Pack with:

- a **signature** `σ(p) = (T₁, …, T_{n_p})` fixing arity and argument types;
- a **functional flag** `F(p) ∈ {true, false}` — if true, the last argument (the *value slot*) is functionally determined by the preceding arguments (the *key slots*). Example: `located_at(agent, place)` is functional in `place` — an agent is in at most one place at a given time;
- a position in a **predicate taxonomy** (a DAG) used for graded relevance, e.g. `assaulted ⊑ harmed ⊑ acted_negatively_toward`;
- **gradability**: optional, for predicates carrying a degree (e.g. `threatened` with `severity ∈ [0,1]`).

The catalog is **closed and versioned per World Pack**. New predicates require a pack version bump; this is what makes contradiction and relevance decidable (see §1.10 on ontology size).

## 1.4 Propositions

A **ground proposition** is

$$
\varphi = \langle\, p \,;\; e_1, \dots, e_{n_p} \,;\; q \,;\; m \,\rangle
$$

where `p ∈ 𝒫`, each `eᵢ ∈ ℰ` with `τ(eᵢ) = Tᵢ`, `q` is an optional **qualifier** (temporal interval and/or spatial scope), and `m ∈ {+, −}` is **polarity** (`−` = negation).

The **core** strips polarity:

$$
\mathrm{core}(\varphi) = \langle\, p \,;\; e_1, \dots, e_{n_p} \,;\; q \,\rangle .
$$

## 1.5 Canonical form

Two propositions denoting the same fact must be identical bytes. Canonicalization applies:

1. **Argument normalization** — entity IDs in their declared signature order; symmetric predicates (e.g. `sibling_of`) sort their arguments by ID.
2. **Qualifier defaulting** — absent temporal qualifier ⇒ `q.time = always`; absent spatial ⇒ `q.place = ⊤` (unrestricted).
3. **Degree binning** (for gradable predicates) — continuous `severity` is *stored raw* but a *coarse bin* (`{minor, moderate, severe}`) is used for equality of the symbolic core, so `severity 0.61` and `0.63` count as the same fact with differing intensity, not as two facts.

`canon(φ)` is a pure function; equality of beliefs is equality of `canon`.

## 1.6 Contradiction relation

`φ ⊥ ψ` (φ contradicts ψ) holds iff the qualifier scopes overlap (`overlap(q_φ, q_ψ)`) **and** one of:

- **(C1) Direct negation:** `core(φ) = core(ψ)` and `m(φ) ≠ m(ψ)`.
- **(C2) Functional conflict:** `F(p) = true`, same predicate, same key slots, *different* value slots, both polarities `+`. (E.g. `located_at(a, bar)` vs `located_at(a, clinic)` at overlapping times.)
- **(C3) Declared mutual exclusion:** `⟨core(φ), core(ψ)⟩ ∈ MutEx`, where the pack declares exclusive sets (e.g. `{alive(x), dead(x)}`).

`overlap(q, q')` is true if the temporal intervals intersect *and* the spatial scopes are not disjoint. This is why "in the bar yesterday" and "in the clinic today" do **not** contradict.

`⊥` is decidable in `O(1)` per candidate pair given canonical form and the pack's `MutEx` table — cheap enough to run on every belief insertion.

## 1.7 Topic patterns and the relevance function

A **topic** `τ` is a *partially bound* proposition: a pattern in which some argument or qualifier positions are **variables** (wildcards). Example: `police_presence(street = current_street, time = ?)`.

Relevance of a ground proposition `φ` to topic `τ`:

$$
\mathrm{rel}(\varphi, \tau) \;=\; \mathrm{predsim}(p_\varphi, p_\tau)\;\cdot\;\mathrm{argmatch}(\varphi, \tau)\;\cdot\;\mathrm{qualmatch}(\varphi, \tau)\;\in[0,1].
$$

with the three factors defined as:

- **Predicate similarity** via taxonomy distance `d_pred` (shortest path in the predicate DAG, `0` if identical):
$$
\mathrm{predsim} = e^{-\lambda\, d_{\text{pred}}(p_\varphi, p_\tau)}, \quad \lambda > 0 .
$$
- **Argument agreement** averaged over signature positions:
$$
\mathrm{argmatch} = \frac{1}{n_p}\sum_{i=1}^{n_p}
\begin{cases}
1 & \text{both bound and equal}\\
0 & \text{both bound and unequal}\\
\beta & \text{position is a wildcard in } \tau
\end{cases}
\qquad \beta \in [0,1] \text{ (default } 0.5).
$$
- **Qualifier match** `qualmatch ∈ {0,1}`: `1` if `τ` leaves the qualifier free or the scopes overlap, else `0`.

This single function is the previously-undefined `S_i` term in retrieval (§5.1 below) and the `R_Erinnerung` / `R_Ort` terms in the topic score (§5.2). It is bounded, pure, and unit-testable.

## 1.8 Proposition JSON schema

```json
{
  "$id": "proposition.schema.json",
  "type": "object",
  "required": ["predicate", "args", "polarity"],
  "properties": {
    "predicate": { "type": "string", "description": "ID from World Pack predicate catalog" },
    "args": {
      "type": "array",
      "items": { "type": "string", "description": "entity ID, typed per predicate signature" }
    },
    "degree": { "type": "number", "minimum": 0, "maximum": 1,
                "description": "raw value for gradable predicates; binned for core equality" },
    "qualifier": {
      "type": "object",
      "properties": {
        "time": {
          "type": "object",
          "properties": {
            "start": { "type": "integer", "description": "world-minutes (see §5.1)" },
            "end":   { "type": "integer" }
          }
        },
        "place": { "type": "string", "description": "place/region entity ID, or '*' for unrestricted" }
      }
    },
    "polarity": { "type": "string", "enum": ["+", "-"] }
  }
}
```

The v0.1 belief object (§7.5) changes only in that `proposition` now references this object instead of a string; **all other v0.1 fields are kept**.

## 1.9 Worked example

v0.1's `"player_is_mayor"` becomes:

```json
{ "predicate": "holds_role", "args": ["player_1", "mayor", "city_nightcity"], "polarity": "+" }
```

- A later claim *"the player is not the mayor"* is the same core with `polarity: "-"` → fires **(C1)**.
- A claim *"the player is the chief of police"*, if `holds_role` is declared functional in the role slot per institution and `mayor`/`chief_of_police` are in a `MutEx` set, fires **(C3)**.
- A topic *"who holds office in the city?"* is `holds_role(?, ?, city_nightcity)` → `rel ≈ predsim(1)·argmatch(0.5·2 + 1 wildcard-handling)·qualmatch(1)` > 0, so the mayor belief surfaces in retrieval.

## 1.10 Ontology size (the hidden critical path — v0.1 §27.6)

The closed catalog is the most underestimated cost in v0.1's effort estimates. A defensible first cyberpunk pack needs on the order of **80–150 predicates**, **8–12 relationship dimensions** (already in v0.1 §3.8), **~25 dialogue acts** (v0.1 §12.4), and a `MutEx` table. Recommended bootstrap method:

1. Hand-author the ~30 highest-frequency predicates (movement, possession, harm, social bonds, roles, location).
2. LLM-assisted extraction of candidate predicates from a target corpus of authored dialogue/quests, with human curation into the closed catalog.
3. Freeze per pack version; treat additions as schema migrations.

This is a 2–4 week task on its own and should be a named milestone, not absorbed into the "6–10 week prototype" of v0.1 §23.1.

---

# 2. The Belief Engine: Confidence and Revision

*(Resolves Gap 2 and dissolves most of the truth-maintenance problem. Refines v0.1 §7.5.)*

## 2.1 Belief record

$$
\beta = \langle\, \varphi,\; c,\; \mathrm{prov},\; t_{\text{acq}},\; t_{\text{upd}} \,\rangle
$$

- `φ` — canonical proposition (§1).
- `c ∈ (0,1)` — **subjective probability** that `φ` holds (this is the semantics of v0.1's `confidence`).
- `prov` — **provenance set**: the claim/observation IDs that contributed, with their origin-event IDs (needed for correlation discounting, §2.5).
- `t_acq`, `t_upd` — acquisition and last-update world-times.

## 2.2 Semantics

`c` is a probability, so the natural arithmetic is in **log-odds** (logit):

$$
\ell(c) = \ln\!\frac{c}{1-c}, \qquad c = \sigma(\ell) = \frac{1}{1+e^{-\ell}} .
$$

`ℓ = 0 ⇔ c = 0.5` (maximal uncertainty). Logit space turns Bayesian evidence combination into addition and keeps `c` bounded in `(0,1)` automatically.

## 2.3 Source credibility

When agent `a` receives a claim about `φ` from source `s`, define the **per-claim reliability**

$$
\kappa(s, a, \varphi) = \mathrm{clamp}\Big(\kappa_0 + \alpha\,\mathrm{trust}(a\!\to\! s) + \gamma\,\mathrm{competence}(s, \mathrm{dom}(\varphi)) - \delta\,\mathrm{Misstrauen}(a),\;\; \kappa_{\min},\; \kappa_{\max}\Big)
$$

interpreted as `κ = P(s asserts φ | φ holds) = P(s asserts ¬φ | φ does not hold)` (symmetric reliability).

- `trust(a→s)` is a relationship dimension already in v0.1 §3.8.
- `competence(s, dom(φ))` is domain expertise (a medic on medical facts, a fixer on street facts) — drawn from the agent's profession/education (v0.1 §4.4–4.5).
- `Misstrauen(a)` is the skepticism trait (v0.1 §3.2) and *reduces* reliability uniformly.
- Bounds: `κ_max < 1` (never certain), `κ_min` may be **below 0.5** for a known liar — see §2.4 for the elegant consequence.

## 2.4 Update rule (binary propositions)

The Bayesian log-odds update for a single claim is exactly:

$$
\boxed{\;\ell(c_{\text{post}}) = \ell(c_{\text{prior}}) + s_\varphi \cdot \ln\!\frac{\kappa}{1-\kappa}\;}
$$

where `s_φ = +1` if `s` asserts `φ`, `s_φ = −1` if `s` asserts `¬φ`.

Properties (all desirable, all emergent):

- `κ = 0.5` ⇒ update term `= 0` ⇒ an untrusted source moves nothing.
- `κ > 0.5` ⇒ asserting `φ` raises `c`; asserting `¬φ` lowers it.
- `κ < 0.5` (known liar) ⇒ the sign flips: **if the liar says φ, the listener believes φ *less***. This is the correct, realistic behavior and falls out of the math for free.
- Independent claims **accumulate additively** in logit space.
- The whole "belief revision" problem for binary facts reduces to this single line; **(C1) direct-negation contradictions need no separate machinery** because `φ` and `¬φ` are the same `core` and a `¬φ` claim is just negative evidence on `c(φ)`.

The **prior** for a never-before-held proposition is `c = π(φ)`, a World-Pack plausibility prior (default `0.5 ⇒ ℓ = 0`).

## 2.5 Correlation discounting (independence is a lie)

Naive accumulation overcounts a rumor that ten gang members all heard from the *same* origin. Using `prov`, before applying a claim, compute the **novel evidence fraction**:

$$
\eta = 1 - \max_{\beta' \in B_a}\ \mathrm{originOverlap}(\mathrm{prov}_{\text{claim}}, \mathrm{prov}_{\beta'}) \in [0,1],
$$

and scale the update term by `η`. A claim tracing entirely to an already-counted origin event contributes `η ≈ 0`. This is what makes "ten people repeating one rumor" *not* certainty, and it is testable against v0.1 §22's contradiction/leak metrics.

## 2.6 Functional and mutually-exclusive variables

For a functional predicate `f` (e.g. `located_at(a, ?)`) or a `MutEx` set, the listener does not hold independent binary beliefs but a **categorical distribution** over the value domain `V = {v₁, …, v_k}` with weights `w_v > 0`, `c(value = v) = w_v / Σ_u w_u`.

A claim "`f(key) = v` from `s`" applies a multiplicative-weights update:

$$
w_v \leftarrow w_v \cdot \exp\!\Big(\eta\,\ln\tfrac{\kappa}{1-\kappa}\Big), \qquad \text{then renormalize.}
$$

Competing evidence on the same variable is handled automatically by renormalization; **(C2) and (C3) contradictions need no hard retraction** — they are resolved as probability mass shifting between alternatives.

## 2.7 Derived beliefs and lightweight TMS

Hard non-monotonic truth maintenance is needed *only* for **inferred** beliefs (those produced by rules, not by observation/claim). Each derived belief stores a **justification set** = the antecedent belief IDs and the rule used. Maintenance:

- A derived belief's confidence is `c_derived = rule_strength · ∏(antecedent confidences)` (or a rule-specific function).
- On any antecedent update, mark dependents **stale**; re-evaluate lazily at next retrieval.
- If an antecedent drops below `c_min`, the dependent is recomputed, not deleted (it may have other justifications).

This is a minimal justification-based TMS (JTMS-style), scoped to the small set of derived beliefs, avoiding a full assumption-based TMS.

## 2.8 The v0.1 "magic number" derived

v0.1 §14.1's `belief_change: 0.31` is no longer authored. It is computed:

$$
\Delta c = \sigma\!\Big(\ell(c_{\text{prior}}) + s_\varphi\,\eta\,\ln\tfrac{\kappa}{1-\kappa}\Big) - c_{\text{prior}} .
$$

For `c_prior = 0.20`, `κ = 0.75`, `η = 1`, `s_φ = +1`: `ℓ_prior = −1.386`, term `= +1.099`, `ℓ_post = −0.287`, `c_post = 0.429`, **`Δc = 0.229`** — a derived, explainable number with a Reason Code (`source=npc_17, trust=0.6, competence=0.7 → κ=0.75`), satisfying v0.1 §2.5 explainability.

---

# 3. Rumor and Information Diffusion

*(Resolves Gap 5. Refines v0.1 §10.4 and §14.1. Now nearly free because propositions are structured.)*

## 3.1 Propagation as claim events

An NPC-to-NPC share (v0.1 §14.1) is just a **claim event** in which the speaker's signal is its *own current confidence* and the listener applies §2.4. No new mechanism, no magic number. The `belief_change` field becomes a *computed output*, not an input.

## 3.2 Mutation operators

Because propositions are structured terms, distortion is well-defined as operators on `φ` (this directly implements v0.1 §9.1 "interference" and §10.4 "verkürzt/übertrieben/vermischt"):

| Operator | Effect on `φ` | Triggered by |
|---|---|---|
| **Generalization** | drop a qualifier, or replace an entity with its type/group (`player_1` → "someone in a red jacket") | low importance, age |
| **Intensification** | raise a gradable predicate's degree (`severity 0.6` → `0.9`), or move up the predicate taxonomy (`threatened` → `assaulted`) | high emotional arousal |
| **Misattribution** | swap an argument with a *confusable* entity (interference between similar memories) | similarity to a co-active memory |
| **Truncation** | drop a conjunct from a compound proposition | low importance |

## 3.3 Determinism and reproducibility

Each mutation fires with a probability function, e.g.

$$
P(\text{mutate}) = \rho_0\,(1 - \text{importance})\,(1 - e^{-\mu\,\text{age}})\,(1 + a_{\text{intens}}\cdot\text{arousal}),
$$

sampled from a **seeded PRNG keyed by `(memory_id, agent_id, world_time, global_seed)`**. This reconciles v0.1's apparent conflict between §22 *reproducibility* (same seed → same run) and §9.5 *distortion/confabulation*: distortion is stochastic but **deterministic given the seed**. `ReplayScenario(seed)` (v0.1 §18.6) reproduces every mutation exactly.

## 3.4 Example trace

```
t0  evt: player_1 threatened merchant_17, severity 0.6        [canonical]
t1  npc_28 observes (quality 0.71) → belief c=0.78
t2  npc_28 → npc_42 share; κ=0.70, η=1 → npc_42 c=0.62
    mutation (intensification, seeded) severity 0.6 → 0.85
t3  npc_42 → npc_55; κ=0.55 → c=0.54
    mutation (generalization) player_1 → "stranger_in_red_jacket"
t4  city_news broadcast refutes: claim ¬threatened, credibility 0.64
    → all exposed NPCs apply negative evidence; npc_42 c: 0.62 → 0.41
```

Every step is explainable and replayable. The refutation in `t4` propagates a downgrade with no special "retraction" code — it is negative evidence (§2.4).

---

# 4. Output Validation and Controllable Generation

*(Resolves Gap 3 — the hardest problem and the core product promise. Refines v0.1 §13.1. Touches Gap 6 latency.)*

## 4.1 Threat model: what "leak" means formally

Given a planned turn with `allowed_facts ⊆` the NPC's belief base and `forbidden_facts` (secrets the NPC may *know* but must not *convey*), a generated utterance `u` **leaks** iff:

$$
\exists\, f \in \text{forbidden\_facts}:\ \ u \models f \quad(\text{entailment, possibly partial/probabilistic}),
$$

and is **out-of-knowledge** iff it asserts as fact some `φ` with `c_a(φ) < c_{\text{assert}}` (the NPC states something it does not sufficiently believe — a hallucination).

Leak rate and hallucination rate are exactly v0.1 §22's *Wissensleckrate* and a slice of *Widerspruchsrate*; §6 ties them to the eval harness.

## 4.2 Layer 0 — Context minimization (prevent, don't detect)

**The single most effective control, and the one v0.1 missed.** You cannot leak what the model never sees. Therefore:

- The realization prompt contains **only `allowed_facts`** as conveyable content. `forbidden_facts` are **absent from the prompt entirely**.
- For secrets the player may *probe*, the NPC needs to deflect convincingly without knowing the content. So the planner supplies a **`avoid_topics`** list (the *topic patterns*, not the fact content) plus a **deflection dialogue act** (e.g. `evade`, `lie`, v0.1 §12.4). The model is told *what subject to steer away from*, never the secret itself.

This caps the structural leak probability near zero for the high-secrecy path; the remaining layers catch residue and the inferential case (where allowed facts *combine* to imply a secret).

## 4.3 Layer 1 — Structured utterance plan (high-control mode)

In high-control mode (Stufe 3–4 NPCs, v0.1 §16), the model first emits a **structured plan** — which allowed propositions to convey, ordered, with the speech act — and only then a realization constrained to that plan. The plan is trivially checkable against `allowed_facts`. Low-control modes skip to Layer 2.

## 4.4 Layer 2 — Entailment check (NLI)

A small, fast natural-language-inference model checks, for the generated utterance `u`:

- **Leak:** for each `f ∈ forbidden_facts`, `entail_score(u, f)`. If `max > θ_leak` → reject.
- **Containment:** the set of propositions `u` conveys should satisfy `conveyed(u) ⊆ allowed_facts ∪ smalltalk`. Implemented either by semantic-parsing `u` back into propositions (§1) and set-checking, or by NLI against each allowed fact.

Probabilistic, hence never relied on alone — it is the second line behind Layer 0.

## 4.5 Layer 3 — Deterministic guards (cheap, high precision)

- **Secret-token / alias scan:** named secrets (`gang_contact_location = warehouse_7`) and their declared aliases are string/regex-scanned in `u`. Cheap, near-perfect recall for *named* secrets.
- **Canon guard:** every proposition `u` asserts as fact must be a belief with `c_a ≥ c_assert`. Blocks hallucinated facts.
- **Repetition guard:** semantic similarity of `u` to recent turns > `θ_rep` → reject (implements v0.1 §12.6 anti-loop and §22 *semantische Wiederholungsrate*).

## 4.6 Layer 4 — Regeneration and template fallback

On any rejection: regenerate with tightened constraints up to `k` attempts (default `k = 2`); if still failing, fall back to a **deterministic template deflection** for the planned act. This *guarantees a safe output always exists* and bounds worst-case latency.

## 4.7 Validation decision

```
validate(u, plan):
    if Layer3.secret_tokens(u, plan.forbidden) hit:        return REJECT_HARD
    if Layer3.canon(u, agent) violated:                    return REJECT_HARD
    if Layer3.repetition(u, history) > θ_rep:              return REJECT_SOFT
    if control_level >= HIGH:
        if Layer2.leak(u, plan.forbidden) > θ_leak:        return REJECT_HARD
        if not Layer2.contained(u, plan.allowed):          return REJECT_SOFT
    return ACCEPT
```

`REJECT_HARD` → regenerate or fall back (Layer 4). `REJECT_SOFT` → regenerate once, else accept with a logged warning (style issues are not safety issues).

## 4.8 Latency budget (Gap 6)

The validator must not add a second blocking LLM round-trip on the common path:

| Step | Cost | Path |
|---|---|---|
| Interpret player input | small **classifier** model, not a large LLM | always |
| Plan (goal/topic/act/facts) | deterministic | always |
| Realize utterance | 1 LLM call, **streamed** | always |
| Layer 0 + Layer 3 guards | no LLM, sub-ms | always |
| Layer 2 NLI | small model, runs **in parallel** with stream; only enforced for high-secrecy NPCs | conditional |
| Layer 4 regen | only on reject | rare |

**Target:** ≤ 1 large-LLM call per player turn on the common path; NLI off the critical path for most NPCs. This is what keeps interactive latency under ~1–2 s and the per-hour cost (Gap 9) bounded — only Stufe 3–4 NPCs incur the large model, per v0.1 §16 LOD.

---

# 5. Recasting the v0.1 formulas as operational functions

*(Resolves Gap 4. The v0.1 formulas in §9.3, §12.3, §15.2 are kept but given units, normalization, and parameters.)*

## 5.1 Canonical time and memory retrieval

**Canonical time.** v0.1's `"day_42_18_21"` is mapped to an integer **world-minute** `t = ((day−1)·24 + hour)·60 + minute`. All decay and recency math uses `t`.

**Base activation** (v0.1 §9.4, ACT-R base-level learning, unchanged):

$$
B_i(t) = \ln\!\left(\sum_{k=1}^{n} (t - t_{ik} + \varepsilon)^{-d}\right), \qquad d = 0.5,\ \varepsilon = 1.
$$

**Full activation** (v0.1 §9.3) with every term now defined and on the same activation scale (natural-log units of odds-like quantities):

$$
A_i = B_i
+ w_s \ln(1 + S_i)
+ w_g \ln(1 + G_i)
+ w_e\, E_i
+ w_r\, R_i
+ w_l\, L_i
+ w_u\, U_i
- P_i
$$

- `S_i = max_{φ∈mem_i, τ∈active_topics} rel(φ, τ)` ∈ [0,1] — **defined in §1.7**.
- `G_i ∈ [0,1]` — relevance to active goals (same `rel` against goal-derived topic patterns).
- `E_i = |emotional_valence|` ∈ [0,1] (v0.1 memory field).
- `R_i ∈ [0,1]` — normalized relationship relevance of the memory's subject.
- `L_i ∈ {0, 1}` — location/situation match (current place ∈ memory qualifier scope).
- `U_i ∈ {0, 1}` — unresolved-commitment flag (v0.1 memory `status`).
- `P_i ≥ 0` — penalty for staleness/contradiction/no-access.

**Retrieval is probabilistic, not a hard cutoff** (ACT-R logistic, fixing the "what threshold?" problem):

$$
p_{\text{recall}}(i) = \frac{1}{1 + e^{-(A_i - \tau_{\text{ret}})/s}}, \qquad s = 0.4 .
$$

Memories below `τ_ret` are recalled only "with a hint" (v0.1 §9.5 graded forgetting): expose them only if `S_i` (cue strength) lifts `A_i` past threshold. This makes v0.1's eight forgetting states (§9.5) a function of `A_i` regions rather than authored flags.

## 5.2 Topic score

v0.1 §12.3 `S(t)` keeps its structure but each term is now a bounded, defined quantity, combined with explicit weights and a softmax over candidate topics for selection:

$$
\mathrm{Score}(\tau) = \theta_{\text{sit}} R_{\text{sit}} + \theta_g R_g + \theta_{\text{rel}} R_{\text{rel}} + \theta_m R_{\text{mem}} + \theta_l R_{\text{loc}} + \theta_e R_{\text{emo}} + \theta_n R_{\text{nov}} - \theta_r R_{\text{risk}} - \theta_w R_{\text{rep}} - \theta_t R_{\text{taboo}}
$$

where `R_mem` reuses `rel` (§1.7), `R_rep` reuses the repetition guard (§4.5), `R_taboo`/`R_risk` are pack-defined, and topic choice is `softmax(Score / T_topic)` for controlled variety (temperature `T_topic`).

## 5.3 Action utility

v0.1 §15.2 `U(a)` likewise gets explicit, bounded, normalized components and weights:

$$
U(a) = \theta_N N(a) + \theta_G G(a) + \theta_S S(a) + \theta_R R(a) - \theta_C C(a) - \theta_D D(a) + \theta_P P(a) + \epsilon,\qquad \epsilon \sim \mathcal{N}(0, \sigma_\epsilon^2)
$$

with each `(·) ∈ [0,1]` after normalization, `θ ≥ 0`, and the Gaussian noise `ε` (seeded) giving v0.1 §15.2's "limited randomness." Action choice = `argmax_a U(a)` over the *closed* action catalog (v0.1 §15.1), never free invention.

## 5.4 Parameter table (defaults; all per-pack tunable)

| Symbol | Meaning | Default | Range |
|---|---|---|---|
| `d` | memory decay | 0.5 | [0.3, 0.8] |
| `τ_ret`, `s` | retrieval threshold, noise | 0.0, 0.4 | — |
| `w_s, w_g, w_e, w_r, w_l, w_u` | activation weights | 1.0 each | [0, 3] |
| `κ₀, α, γ, δ` | credibility coeffs | 0.55, 0.25, 0.20, 0.30 | — |
| `κ_min, κ_max` | reliability bounds | 0.2, 0.95 | — |
| `θ_leak, θ_rep` | validator thresholds | 0.5, 0.85 | — |
| `c_assert` | min confidence to state as fact | 0.6 | [0.5, 0.8] |
| `ρ₀, μ, a_intens` | mutation params | 0.1, 0.01, 1.5 | — |
| `k` | regen attempts | 2 | {1,2,3} |

These are **starting points to be calibrated against the eval harness** (§6), not claimed-optimal values.

---

# 6. Updated module data flow

The v0.1 module list (§17.1) is unchanged; v0.2 fixes the *contracts* between them:

```
World Event Ledger ─ emits canonical events (typed propositions, §1)
        │
   Perception Engine ─ events → observations (subjective, quality-weighted)
        │
   Belief Engine ─ observations/claims → logit/categorical update (§2), contradiction check (§1.6)
        │                                   provenance → correlation discount (§2.5)
   Memory Engine ─ beliefs/episodes → activation A_i (§5.1), consolidation, seeded mutation (§3)
        │
   Goal & Intent Engine ─ U(a) (§5.3) over closed action catalog
        │
   Dialogue Planner ─ topic Score (§5.2), act, allowed_facts, avoid_topics (§4.2)
        │
   Language Realizer ─ 1 streamed LLM call, allowed_facts only (§4.2)
        │
   Validator ─ Layers 0–4 (§4); REJECT → regen/fallback
        │
   Persistence + Audit ─ Reason Codes for every step (v0.1 §2.5), ReplayScenario(seed) (§3.3)
```

Every arrow now carries a typed, testable payload. The eval harness (next deliverable) instruments this flow: adversarial probes at the Dialogue input measure leak rate at the Validator output; seeded replays measure reproducibility; contradiction counts come from the Belief Engine's `⊥` checks.

---

# 7. What this unblocks, and the next deliverables

This document makes v0.1's deterministic layer **implementable and measurable**. With the foundation fixed, the remaining tracks proceed on stable contracts:

1. **MVP code (v0.1 Phase 2 / §20)** — Python + SQLite skeleton implementing §1 proposition store, §2 belief engine, §5.1 retrieval, §4 validator stub, and the terminal loop. Builds directly on the schemas here.
2. **Remaining §30 items** — full DB schema, the dialogue planner as an explicit state machine, 20–30 scenario tests, the model-provider interface, the first Cyberpunk World Pack, and the playable-demonstrator definition.
3. **Eval harness (Gap 7)** — adversarial probe suite + automated judge computing v0.1 §22 metrics in CI; the bridge from "we have metrics" to "we measure them."
4. **Competitive positioning & cost model (Gaps 9, and strategy)** — explicit positioning vs. existing voice/NPC-AI offerings, a per-player-hour cost derivation tied to the §4.8 latency/LOD model, and the narrowed wedge (provable knowledge-control + explainability) for the pilot pitch.

---

## Appendix A — Consolidated additions to the v0.1 schemas

```jsonc
// Belief (extends v0.1 §7.5)
{
  "belief_id": "blf_900",
  "owner": "npc_17",
  "proposition": { /* §1.8 proposition object, replaces the string */ },
  "confidence": 0.43,            // c ∈ (0,1), subjective probability
  "logit": -0.287,               // cached ℓ(c) for additive updates
  "provenance": [                // §2.5 correlation discounting
    { "claim_id": "clm_401", "origin_event": "evt_98441", "kappa": 0.75 }
  ],
  "justification": null,         // §2.7; set only for derived beliefs
  "status": "active",
  "t_acq": 60981,                // world-minutes (§5.1)
  "t_upd": 61102
}

// Dialogue plan handed to the realizer (extends v0.1 §13.4)
{
  "speaker_role": "bartender",
  "dialogue_act": "remind_and_warn",
  "goal": "obtain_payment",
  "allowed_facts": [ /* proposition objects, §1.8 */ ],
  "avoid_topics":  [ /* topic patterns, §1.7 — content NOT included */ ],
  "control_level": "high",       // selects validator layers, §4
  "emotion": { "irritation": 0.67, "dominance": 0.58 },
  "style": { "world": "dystopian_city", "verbosity": "short", "directness": 0.82 }
}
```
