# Unscripted
## Theory Dynamics Specification & Engineering Implementation Guide v0.5

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Date:** 22 June 2026
**Status:** implementation-ready engineering spec (reference runtime)
**Builds on:** Ontology v0.4 Completion Pass, Technical Core v0.2, Theory Audit v0.5
**Target reader:** an implementing engineer or LLM coder. This document is meant to be coded down directly. Where a value is a calibration default rather than a derived constant, it is marked **(cal)** — implement it as a named parameter, do not hard-code.

---

# 0. How to use this document

This spec resolves the one thing the audits left open: **how the modules become one behaving NPC, over time, stably, deterministically, and explainably.** It contains:

- **Part A (§2)** — the affect dynamics system (the coupled continuous engine).
- **Part B (§3)** — utility aggregation and action/dialogue selection (the integration math).
- **Part C (§4)** — the propose/apply protocol for cross-cutting state (trust, reputation, salient identity).
- **§5** — the per-module update functions that hang off A–C (MVP-mandatory set).
- **§6** — the runtime tick loop (the integration order).
- **§7** — the module contract and copy-pasteable code skeletons.
- **§8** — persistence and storage, with a sizing analysis and verdict (per the explicit request to check storage).
- **§9** — the terminal MVP demo: what it proves, how world/ontology/character data is ingested, the loop, an annotated trace, and a build backlog.
- **§10–§12** — calibration, evaluation, and the decisions deliberately left open.

**Build order:** implement §7 contract → §2 → §4 → §3 → §5 modules → §6 loop → §8 persistence → §9 demo. Do not start with a game engine. Build the reference runtime in Python first.

---

# 1. Foundational conventions

**Time.** `world_time` is an integer in **world-minutes** (Technical Core v0.2 §5.1). A *tick* is one discrete event-processing step; ticks are not uniform in wall-clock or world-time — they are triggered by events (player turn, scheduled event, time-advance request).

**Numeric types** (Ontology v0.4 §1.2): `unit_interval` ∈ [0,1] for intensities/degrees; `signed_unit` ∈ [-1,1] for bipolar scores (valence, dominance, liking); `probability` ∈ [0,1] only for actual probabilities/confidences; `number` ∈ ℝ for unbounded (ACT-R activation).

**Determinism.** Every stochastic draw uses a seed derived deterministically:

```
seed = blake2b(f"{global_seed}|{agent_id}|{event_id}|{world_time}|{module_id}|{salt}")
```

No module may call a global RNG. This guarantees `ReplayScenario(seed)` reproduces every mutation (v0.2 §3.3).

**Standard module form (side-effect free).** Every theory module is a pure function:

```
new_state, proposed_effects, reason_trace = module.update(old_state, event, context, params, seed)
```

It mutates **only the state it owns**. Effects on state owned by other modules are returned as `proposed_effects` (Part C), never written directly. `reason_trace` is a list of `(code, magnitude, detail)` for explainability (v0.1 §2.5).

**State ownership (one owner per field).** Enforced; cross-cutting fields handled by §4.

| Field group | Owner module |
|---|---|
| beliefs, confidence, evidence | BeliefEngine |
| memory activation, retrieval | MemoryEngine |
| PAD mood, active emotions | AffectEngine |
| relationship vector incl. trust | RelationshipEngine |
| reputation (audience-specific) | ReputationEngine |
| salient identity | IdentityEngine |
| goals, intentions, plans | MotivationEngine |
| needs | NeedEngine |
| conversation state | DialogueEngine |

---

# 2. Part A — Affect Dynamics System (ALMA-based)

The audits noted "valence missing", "no dynamical form", "no appraisal→emotion table", "no action tendencies". This part fixes all four with one coherent engine, following the **ALMA** model (Gebhard 2005): personality sets the mood baseline, OCC appraisal produces discrete emotions, emotions push the PAD vector, mood is the slow PAD integral, and emotions bias action.

## 2.1 State

```python
@dataclass
class AffectState:
    mood: Vec3            # PAD, each component signed_unit [-1,1]; slow
    active_emotions: dict[EmotionType, float]  # type -> intensity (unit_interval); fast
    baseline: Vec3       # PAD baseline from personality (computed once, §2.2)
```

PAD axes: **P**leasure (= valence), **A**rousal, **D**ominance.

## 2.2 Personality → PAD baseline (Mehrabian mapping)

The mood baseline is a linear map of the Big Five (ALMA uses Mehrabian's coefficients). Using **emotional_stability** (= 1 − neuroticism, the sign already flipped vs. the original which uses N):

```
P0 =  0.21·E + 0.59·A + 0.19·S
A0 =  0.15·O + 0.30·A − 0.57·(1−S)
D0 =  0.25·O + 0.17·C + 0.60·E − 0.32·A
```
where O,C,E,A,S ∈ [0,1] are the Big Five (S = emotional_stability), then each axis is rescaled to [-1,1] and clamped. **(cal)** — these coefficients reproduce the documented sign structure (P rises with extraversion/agreeableness/stability; A rises with openness and instability; D rises with extraversion/openness/conscientiousness, falls with agreeableness); **verify the exact constants against Mehrabian (1996) / ALMA before freezing.** They are defaults, not derived truths.

`baseline` is computed once at agent creation; mood relaxes toward it.

## 2.3 Appraisal → discrete emotion (OCC table, MVP subset)

For each event, the AppraisalEngine (using the `affect:` appraisal predicates from v0.4) produces appraisal variables, then this table emits emotion(s). MVP emotion set (16, OCC-grounded):

| Emotion | Appraisal condition (variables from v0.4 `affect:`) | Intensity ∝ |
|---|---|---|
| joy | desirability(self) > 0 | desirability |
| distress | desirability(self) < 0 | −desirability |
| hope | prospective desirable event, unconfirmed | desirability · uncertainty |
| fear | prospective undesirable event, unconfirmed | −desirability · uncertainty |
| relief | feared event disconfirmed | prior_fear |
| disappointment | hoped event disconfirmed | prior_hope |
| pride | praiseworthy(self) action, self-agency | praiseworthiness |
| shame | blameworthy(self) action, self-agency | −praiseworthiness |
| admiration | praiseworthy(other) action | praiseworthiness |
| reproach | blameworthy(other) action | −praiseworthiness |
| gratitude | desirable + praiseworthy(other) toward self | desirability·praise |
| anger | undesirable + blameworthy(other) toward self | −desirability·−blame |
| gratification | desirable + praiseworthy(self) | desirability·praise |
| remorse | undesirable(other) + blameworthy(self) | −desirability·−blame |
| liking | appraises object, attraction > 0 | attraction |
| disliking | appraises object, attraction < 0 | −attraction |

`uncertainty = 1 − expectedness`. Multiple emotions may co-fire (emotion blending). Each new emotion is added to `active_emotions` with its intensity (capped at 1).

## 2.4 Emotion → PAD impulse

Each emotion type has a unit PAD direction (Mehrabian octant); the impulse is `intensity · k_impulse · direction` **(cal** `k_impulse` default 0.6**)**:

| Emotion | (P, A, D) direction |
|---|---|
| joy, gratification | (+1, +0.3, +0.3) |
| hope, relief | (+1, +0.2, +0.1) |
| pride | (+1, +0.4, +0.6) |
| admiration, gratitude, liking | (+1, +0.2, −0.1) |
| distress, disappointment | (−1, −0.2, −0.4) |
| shame, remorse | (−1, −0.1, −0.6) |
| fear | (−1, +0.6, −0.7) |
| anger, reproach | (−1, +0.6, +0.5) |
| disliking | (−0.6, +0.1, +0.1) |

## 2.5 Mood relaxation (discrete-time integration)

On each tick of duration `Δt` world-minutes, after collecting emotion impulses `I = Σ impulses`:

$$\mathbf{mood} \leftarrow \mathrm{clamp}_{[-1,1]^3}\!\Big(\mathbf{mood} + (\mathbf{baseline} - \mathbf{mood})\cdot\min(1, \tfrac{\Delta t}{\tau_{\text{mood}}}) + I\Big)$$

with **(cal)** `τ_mood = 240` world-minutes (mood half-returns to baseline in ~2.8 h). The `min(1, ·)` prevents overshoot on large time-skips. This is a stable exponential relaxation — it cannot oscillate or diverge because the homing term is contractive and impulses are bounded.

## 2.6 Emotion decay

Each active emotion decays independently and is dropped below ε:

$$\text{intensity} \leftarrow \text{intensity}\cdot e^{-\Delta t/\tau_{\text{emotion}}},\quad \text{drop if} < \varepsilon$$

**(cal)** `τ_emotion = 30` world-minutes, `ε = 0.05`. Emotions are short-lived; mood is the residue.

## 2.7 Action tendencies (Frijda) — the bridge to behavior

Active emotions produce an **action-tendency bias** consumed by Part B. Each emotion biases broad action classes:

| Emotion | Biased action classes (+) / suppressed (−) |
|---|---|
| fear | + flee, hide, comply, seek_safety; − approach, attack |
| anger | + attack, threaten, confront; − comply, affiliate |
| joy / gratitude | + affiliate, help, share, cooperate |
| distress / sadness | + withdraw, wait; − initiate |
| pride | + assert, display, lead |
| shame | + withdraw, conceal, repair_face |
| liking | + approach, help (target-directed) |
| disliking / reproach | + avoid, sanction (target-directed) |

The bias is `b_emotion(a) = Σ_e intensity_e · class_weight(e, class(a))`, a `signed_unit` added in §3.

## 2.8 Emotion → cognition feedback (the reverse arrows)

Affect modulates downstream modules this tick (read-only multipliers, not state writes):

- **Stress** `= arousal·max(0,−valence)` reduces ToM depth (depth-1 → depth-0 if stress > 0.7), narrows topic search, raises habit reliance.
- **Mood valence** biases memory retrieval (mood-congruent recall: add `w_moodcongruence · valence · sign(memory.emotional_valence)` to activation `A_i`).
- **High arousal** raises the selection temperature `T` in §3.6 (more impulsive choice).

## 2.9 Reason codes

`affect.emotion_fired(type, intensity, appraisal_summary)`, `affect.mood_shift(axis, delta, cause)`, `affect.tendency(action_class, bias)`.

---

# 3. Part B — Utility Aggregation & Selection

The audits' biggest blind spot: §5 of the audit said "modules contribute terms to a policy layer" but never made them commensurable. This part defines the **common unit**, the **aggregation form**, and **who contributes what**.

## 3.1 Common value unit

All contributions are expressed in **normalized value units** ∈ [-1,1] (`signed_unit`). A contribution of +1 means "maximally promotes what this NPC cares about"; −1 the opposite. Each module is responsible for normalizing its raw quantity into this band (e.g., a 300-credit debt → an obligation term, scaled by a per-pack reference amount).

## 3.2 The aggregation form

For each candidate action `a` (drawn from the closed action catalog, v0.1 §15.1):

$$U(a) = \sum_{g \in \text{TermGroups}} w_g(\text{personality}, \text{identity}) \cdot \Big[\textstyle\sum_{m \in g} v_m(a)\Big] \;+\; b_{\text{emotion}}(a)$$

then the outcome value of each term is passed through the **risk transform** (§3.5) before summation. Selection is a seeded softmax (§3.6).

**Three roles, kept distinct (this is the part the audit conflated):**

1. **Additive value terms** `v_m(a)` — needs, goals, social exchange, norms, relationship effects, ToM-expected reactions. These *are* the value.
2. **Multiplicative weights** `w_g` — personality traits and the **salient identity** scale entire term groups. They do not add value; they decide *how much each kind of value matters to this NPC right now*.
3. **Emotion** enters only as the action-tendency bias `b_emotion(a)` (§2.7) — a push, not a value source.

## 3.3 Term catalog (which module emits which `v_m`)

| Term group `g` | Terms `v_m(a)` | Emitting module |
|---|---|---|
| `need` | how much `a` reduces an active need above threshold | NeedEngine (§5.1) |
| `goal` | progress toward committed intention / next plan step | MotivationEngine (§5.4) |
| `exchange` | reciprocity/obligation: repay favor, collect debt, fairness | SocialExchange (§5.8) |
| `norm` | compliance value: −(sanction·observability·legitimacy) if `a` violates an active norm; + if `a` is normatively expected | NormEngine (§5.11) |
| `relationship` | effect of `a` on valued relationships (help ally, harm rival) | RelationshipEngine |
| `identity_value` | how `a` promotes/violates the **active** Schwartz values (gated by salient identity) | ValueEngine (§5.2) |
| `tom` | expected reaction of others (will the threat work? will they retaliate?) | TheoryOfMind (§5.13) |
| `face` | impression-management value: does `a` protect/threaten face before the current audience | ImpressionMgmt (§5.14) |

## 3.4 Personality / identity as weights

`w_g` defaults to 1 and is modulated **(cal)**:

| Weight | Raised by | Lowered by |
|---|---|---|
| `w_exchange` | agreeableness, high `owes_favor` | low agreeableness |
| `w_norm` | conscientiousness, norm internalization, low risk-tolerance | low conscientiousness |
| `w_relationship` | agreeableness, salient identity = family/friend | enmity context |
| `w_identity_value` | identity salience (the salient identity's values get full weight; others attenuated) | — |
| `w_goal` | conscientiousness (persistence) | high impulsivity |
| `w_face` | salient public role, high-surveillance/public audience | being alone (backstage) |

This is where **Self-Categorization** does its work: the salient identity (§4.5) selects *which* values are weighted at full strength. A bartender who is currently "father" weights family-protection values, not professional ones.

## 3.5 Risk transform (Prospect Theory)

Action outcomes are uncertain. Apply the Kahneman–Tversky value and weighting functions to each outcome relative to the NPC's reference point `r`:

$$v(x) = \begin{cases} (x-r)^{\alpha} & x \ge r \\ -\lambda\,(r-x)^{\beta} & x < r \end{cases}\qquad w(p) = \frac{p^{\gamma}}{\big(p^{\gamma} + (1-p)^{\gamma}\big)^{1/\gamma}}$$

with the canonical values `α = β = 0.88`, `λ = 2.25` (loss aversion), `γ = 0.61`. The reference point `r` is the NPC's current expectation (status quo, or a promised amount). Loss aversion is what makes a guard who is *defending* what he has behave differently from one *seeking* gain — and makes desperate (below-reference) NPCs risk-seeking. This is MVP-mandatory for the negotiation/threat/theft cases.

## 3.6 Selection

$$P(a) = \frac{\exp(U(a)/T)}{\sum_{a'} \exp(U(a')/T)}, \qquad a^\star \sim P(\cdot)\ \text{(seeded)}$$

Temperature `T` **(cal** base 0.3**)** rises with impulsivity (trait) and arousal (§2.8), making high-arousal/impulsive NPCs less deterministic. `argmax` is recovered as `T → 0`. The same form selects **dialogue acts** (candidates scored by the topic score of v0.2 §5.2 plus these terms).

## 3.7 Reason codes (the explainability USP)

The selector records, for the chosen and the top-3 rejected actions, every `(term_group, v_m, w_g, contribution)` and the emotion bias. This is the data behind `ExplainIntent(agent)` (v0.1 §18.6) and the demo's trace viewer. **This is the product differentiator — never optimize it away in the reference runtime.**

---

# 4. Part C — Cross-Cutting State: Propose/Apply Protocol

The audit demands "one owner per field" but its own example has Social Exchange "emit trust delta" while Relationship owns trust. Resolution: a two-phase protocol.

## 4.1 Protocol

1. **Propose phase.** Any module may emit `ProposedDelta(target_field, amount, reason, source_module)` in its `proposed_effects`.
2. **Apply phase.** The *owner* of `target_field` collects all proposals for its fields this tick and applies them with **its own kinetics** (saturation, asymmetry), producing the actual change and the reason trace. Non-owners never write.

The tick loop (§6) runs all propose phases, then all apply phases, in a fixed module order — deterministic and free of write-races.

## 4.2 Trust kinetics (owner: RelationshipEngine) — slow up, fast down

Trust must build slowly and break fast. Given net proposed delta `Δ` for a relationship's trust:

$$\text{trust} \leftarrow \mathrm{clamp}_{[0,1]}\Big(\text{trust} + \begin{cases} \eta_{\uparrow}\cdot\Delta & \Delta \ge 0 \\ \eta_{\downarrow}\cdot\Delta & \Delta < 0 \end{cases}\Big)$$

**(cal)** `η↑ = 0.10`, `η↓ = 0.40`. A single betrayal (large negative Δ from a broken commitment) costs ~4× what an equal favor earns. The other relationship dimensions (liking, respect, fear, dependence) use symmetric kinetics unless a pack overrides.

## 4.3 Reputation update kernel (owner: ReputationEngine) — audience-specific

Reputation is per-(subject, audience, dimension) (v0.4 `reputation:`). It updates from two streams:

- **Image** (direct observation): an audience member who observes subject's action updates the dimension by `η_img · appraised_sign(action, dimension)`.
- **Reputation** (reported, indirect reciprocity): a claim about the subject updates by `η_rep · credibility(source, audience) · sign`, with `η_rep < η_img` (hearsay moves less than seeing).

Aggregate audience reputation is the trust-weighted mean of members' images, decaying toward neutral over time. This is the kernel the audit listed as "generalized reciprocity" but never wrote.

## 4.4 Salient identity (owner: IdentityEngine) — Self-Categorization with the math fixed

The audit's `salience = accessibility × fit × fit × fit × threat` collapses toward 0 (product of sub-1 terms) and ignores that salience is **relative** among competing identities. Use a softmax over the agent's identities `i`:

$$\text{fit}_i = w_a\,\text{accessibility}_i + w_c\,\text{comparative\_fit}_i + w_n\,\text{normative\_fit}_i + w_t\,\text{threat}_i$$
$$\text{salience}_i = \frac{\exp(\beta\,\text{fit}_i)}{\sum_j \exp(\beta\,\text{fit}_j)}$$

where **comparative_fit** is Turner's meta-contrast ratio computed over the *others present in the current context* (mean between-category difference / mean within-category difference) — so it requires the social context (who is here, their category memberships) as input. **(cal)** `β = 4`, weights ~equal. The argmax identity (or top-mass identities) is "salient" and gates value weights in §3.4. This both avoids collapse and makes the salient identity context-dependent and competitive, as the theory requires.

## 4.5 Apply order within a tick

Owners apply in this fixed order so dependencies resolve once per tick: Belief → Memory → Affect → Identity → Relationship → Reputation → Need → Motivation → Dialogue. (Affect before Identity because stress affects salience computation; Identity before Relationship because salient identity weights relationship deltas.)

---

# 5. Per-module update functions (MVP-mandatory)

Each follows the §1 contract. Only the model-specific content is given; wrap each in the §7 skeleton.

## 5.1 NeedEngine (homeostatic)

Owns: `needs: dict[NeedType, unit_interval]`. Each need drifts up over time and is reduced by consumption events.

```
need ← clamp(need + drift_rate[type]·Δt − consumption, 0, 1)        # per tick
goal_pressure[type] = max(0, need − threshold[type]) · importance[type]
```
Emits a `need` value term to §3 for actions that reduce a pressured need. **(cal)** drift rates per type (hunger faster than need-for-recognition). **No fixed Maslow ordering** — pressures compete in §3, weighted by the agent's values.
LOD: at LOD ≤ 1, integrate needs lazily (compute on read from last-update timestamp), no per-tick update.

## 5.2 ValueEngine (Schwartz)

Owns: `value_priorities: dict[ValueType, unit_interval]` (10 Schwartz values), `conflict_matrix` (static, Schwartz circle: adjacent compatible, opposite conflicting).
Computes **active value** per §1.2 of the audit:
```
active_value[v] = baseline_priority[v] · context_relevance[v] · identity_salience_factor[v] · opportunity_or_threat[v]
```
where `identity_salience_factor` comes from §4.4 (the salient identity amplifies its associated values). Emits `identity_value` terms to §3: `+active_value[v]` for actions promoting `v`, `−active_value[v]` for actions violating `v`; conflicting values produce opposing terms, and §3's aggregation resolves the tension.

## 5.3 PersonalityEngine (static provider)

Owns: `big_five: BigFiveProfile` (the explicit schema the audit wanted). Static after creation. Read-only provider of: PAD baseline (§2.2), weight modulations (§3.4), selection temperature bias (§3.6), commitment persistence (§5.4). **Traits only shift probabilities/weights; they never force an action** (v0.1 §5.1).

## 5.4 MotivationEngine (BDI + commitment state machine)

Owns: `goals`, `intentions`, `plans`. Implements the state machine the audit specified:

```
candidate_goal → adopted_goal → committed_intention → selected_plan → executable_step
                                                          ↓
                                    success | repair | suspend | abandon
```

Reconsideration policy (the missing BDI rules):
- **Adopt** a candidate when its expected value (via §3 terms) exceeds the adoption threshold and resources are available.
- **Commit**: once committed, an intention resists reconsideration — only re-evaluated when (a) it succeeds, (b) it becomes impossible (precondition lost), (c) a much higher-value goal appears (margin `δ_reconsider` **(cal)**), or (d) the plan is blocked. This single-minded commitment is what keeps NPCs from flip-flopping every tick.
- **Plan repair** before abandon: if a step fails, try an alternative step achieving the same subgoal before dropping the intention.
- **Suspend/resume**: interrupted intentions (e.g., by a higher-priority threat) are pushed with their state and resumed when the interrupter resolves.
Emits `goal` value terms to §3.
LOD: at LOD ≤ 1, agents follow only their daily schedule (v0.1 §8), no deliberative planning.

## 5.5 AppraisalEngine

Implemented in Part A (§2.3). Owns nothing persistent beyond transient appraisal records; emits emotions to AffectEngine.

## 5.6 MemoryEngine (ACT-R + the missing pieces)

Owns: memory records, `activation`. Base spec is Technical Core v0.2 §5.1 (ACT-R base activation, logistic recall). Add the audit's missing mechanisms:
- **Source-memory confidence**: each memory stores source reliability; low-source memories are recalled with a "not sure where I heard it" flag.
- **Working-memory cap**: at retrieval, return at most `W` **(cal** W=7**)** memories above threshold, ranked by activation (cue competition: similar memories suppress each other via a `−w_interference·similarity` penalty in activation).
- **Prospective memory**: commitments with deadlines get an activation boost as `world_time → deadline` (so NPCs remember to act on time).
- **Type-specific decay**: `d` differs by memory type (episodic decays faster than semantic; emotional traces slowest) — v0.1 §9.6.
- **Reconstruction policy**: missing slots are *not* free-filled by the LLM (v0.3 §9.4); the engine returns `unknown` or applies a seeded mutation (v0.2 §3.2).
LOD: at LOD ≤ 1, only summary/commitment memories are kept; episodic detail is dropped.

## 5.7 BeliefEngine

Owns beliefs/evidence. Spec is Technical Core v0.2 §2 (logit update, correlation discount) + v0.3 dual-evidence record (support_for / support_against / ignorance / conflict). The §1.2.1 reliability decomposition applies: skepticism *attenuates* toward LR=1; only declared adversariality inverts. Emits nothing to §3 directly (beliefs are inputs to other terms).

## 5.8 SocialExchangeEngine

Owns: `exchange_balance` per relationship (reciprocity ledger), `perceived_fairness`. Reads: favors, commitments, dependence, alternatives.
- Tracks **direct reciprocity** (this dyad's give/take balance) and **generalized reciprocity** (reputation-mediated, via §4.3).
- **Comparison level** and **comparison with alternatives**: dependence-derived power = `1 − (best_alternative_value / current_relationship_value)`.
- On a fulfilled exchange: **proposes** `+trust`, `−obligation`. On a broken commitment: **proposes** large `−trust`, `+resentment`, and a reputation hit (§4.3).
Emits `exchange` value terms (repay what you owe, collect what's owed, maintain fairness) to §3.

## 5.9 SocialIdentityEngine

Owns: `identification_strength` per group, `perceived_group_status`. Computes in-group/out-group categorization of others (via shared group membership). On **identity threat** (an out-group act against the in-group), produces **group-based emotion** (proposes anger/fear impulses to AffectEngine) and raises the relevant identity's `threat` input to §4.4. Activates in-group norms and loyalties (feeds NormEngine and §3 weights).

## 5.10 SelfCategorizationEngine

Implemented in Part C (§4.4) as the IdentityEngine owner logic.

## 5.11 NormEngine

Owns nothing persistent beyond internalization levels; computes compliance pressure. The audit's missing pieces:
```
compliance_pressure(norm, action) =
    internalization[norm]                                   # I follow it because I believe it
  + observability(audience) · expected_sanction · legitimacy(authority)   # I follow it because I'd be caught
  + empirical_expectation(norm)·conformity_trait            # others do it
  + normative_expectation(norm)·approval_sensitivity        # others approve
```
Emits `norm` value terms (negative for violating, positive for conforming) to §3, scaled by `w_norm`. Observability ties to the environment (private room vs. monitored street, v0.1 §4.8) and to §4.4's audience.

## 5.12 SocialNetworkEngine (weak ties)

Owns: edge `tie_strength`, `contact_frequency`, derived `bridge_score`. Used by the **rumor/media propagation** (v0.2 §3): which NPCs talk in a background tick is sampled by tie strength (strong ties talk often), but **information novelty** routes through weak/bridge ties (a rumor crosses clusters via the bartender/driver/trader with high bridge score). Strong ties give higher credibility κ (§5.7); weak ties give reach. This is the mechanism behind v0.1's society-wide memory.
LOD: background propagation runs only on the discrete-event schedule (v0.1 §8.3), not per agent per minute.

## 5.13 TheoryOfMindEngine (depth-1)

Owns: `models[other][proposition] = (estimated_confidence, uncertainty, last_updated, source)`. The audit's missing pieces:
- **Uncertainty** and **decay**: the model of another's mind decays toward "unknown" over time.
- **Correction**: after observing the other's reaction, update the model (if they acted surprised by X, raise estimate they didn't know X).
- **False-belief support**: the model may differ from truth and from the modeler's own belief (required for deception).
Emits `tom` value terms (expected reactions: will the threat be believed? will they retaliate?) to §3, and supplies `tom:intends_listener_to_believe` to the dialogue planner for lies/bluffs.
Depth: **1 by default**; depth-2 only for LOD-4 agents; **drops to depth-0 under stress** (§2.8).

## 5.14 ImpressionManagementEngine (Goffman)

Owns: `desired_impression` per audience, `face_state`. Reads: current audience (§4.4 context), public/private role, surveillance level.
- Computes **front-stage vs back-stage**: alone → back-stage (less impression management); before peers/superiors/cameras → front-stage.
- Emits `face` value terms to §3: actions that threaten face before the current audience get negative value scaled by `w_face` (high in public, ~0 when alone). Triggers **face-repair** actions after embarrassment.
This is what makes the bartender friendly alone, hard before the gang, formal before the boss — directly operationalizing clothing/audience/role.

## 5.15 InterpersonalEngine (circumplex)

Owns: situational `(agency, communion)` stance vector (distinct from stable personality). Computed from relationship (liking→communion, dominance/respect→agency) + current emotion (anger→low communion/high agency; fear→low agency) + role. Feeds the **dialogue realization style** (warm/hostile × dominant/submissive) and **complementarity** (dominant stance invites submissive response). Output is a style vector for the realizer, not a value term.

---

# 6. The Runtime Tick Loop

The integration order. **One pass per event** (no within-tick fixpoint in the reference runtime — emotion feedback applies to the *next* event; this is a deliberate simplification for determinism and is noted in §12).

## 6.1 Event path

```python
def process_event(event, world):
    rt = ReasonTrace(event)
    # 1. Perception: who could perceive this, and how well
    observations = PerceptionEngine.filter(event, world)        # per agent, signal quality
    for agent, obs in observations:
        ctx = build_context(agent, world)        # audience, place, salient identity, mood...
        proposals = []
        # 2. Belief update from observation/claim
        s, p, r = BeliefEngine.update(agent.beliefs, obs, ctx, params, seed); proposals += p; rt += r
        # 3. Memory encoding
        s, p, r = MemoryEngine.update(agent.memory, obs, ctx, params, seed); proposals += p; rt += r
        # 4. Appraisal -> emotions -> PAD impulses
        s, p, r = AffectEngine.update(agent.affect, obs, ctx, params, seed); proposals += p; rt += r
        # 5. Social/identity reactions (propose only)
        for M in [SocialIdentityEngine, SocialExchangeEngine, NormEngine, ReputationEngine, RelationshipEngine, TheoryOfMindEngine]:
            _, p, r = M.update(M.state(agent), obs, ctx, params, seed); proposals += p; rt += r
        # 6. APPLY phase: each owner applies proposals to its fields (Part C order)
        apply_proposals(agent, proposals, rt)
        # 7. Motivation: (re)consider goals/intentions given new state
        MotivationEngine.update(agent.motivation, obs, ctx, params, seed)
    return rt   # persisted (debug) / sampled (shipping)
```

## 6.2 Dialogue path (player turn)

```python
def player_turn(text, player, npc, world):
    interp = Interpreter.parse(text, conv_context)              # speech acts + propositions + alternatives (v0.3 §10.5)
    process_event(claim_event(interp), world)                  # NPC hears it -> belief/memory/affect via 6.1
    DialogueEngine.update_conversation(npc.conv, interp)        # common ground, open questions (v0.3 §10.4)
    goal = MotivationEngine.dialogue_goal(npc)                 # what does the NPC want here
    plan = DialoguePlanner.plan(npc, goal)                     # act, topic (v0.2 §5.2), allowed_facts, avoid_topics, stance, style(§5.15)
    for _ in range(K_REGEN):                                    # validator loop (v0.2 §4)
        utt = Realizer.realize(plan, style, model_provider)     # 1 streamed LLM call, allowed_facts only
        verdict = Validator.check(utt, plan, npc)               # layers 0-4 (v0.2 §4.7)
        if verdict == ACCEPT: break
    else:
        utt = DeflectionTemplate.for(plan)                      # safe fallback
    record_conversation_effects(npc, utt)
    return utt
```

## 6.3 Periodic path (time advance: sleep, travel, wait)

```python
def advance_time(delta, world):
    for tick in scheduled_and_probable_events(delta):          # discrete-event, not per-minute (v0.1 §8.3)
        process_event(tick.event, world)
    for agent in active_agents(LOD>=1):
        NeedEngine.drift(agent, delta)
        AffectEngine.decay(agent.affect, delta)                # §2.5/2.6
        MemoryEngine.decay_and_consolidate(agent.memory, delta)
        check_commitment_deadlines(agent, delta)
    MediaPropagation.propagate(delta, world)                   # via SocialNetworkEngine weak ties
    OpinionDynamics.step(delta, world)                         # optional module, if enabled
    ReputationEngine.decay(delta, world)
```

## 6.4 Determinism & ordering

All loops iterate agents in sorted ID order; all RNG via §1 seeds; propose-then-apply prevents write races; one pass per event. The same `(global_seed, scenario, input log)` reproduces byte-identical traces — the property that makes `ReplayScenario` and golden traces possible.

---

# 7. Module contract & code skeleton

## 7.1 Base protocol

```python
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class ProposedDelta:
    target_field: str          # e.g. "relationship.npc_17.trust"
    amount: float
    reason: str                # reason code
    source_module: str

@dataclass
class ReasonEntry:
    code: str; magnitude: float; detail: dict

class TheoryModule(Protocol):
    module_id: str
    version: str
    owned_fields: list[str]    # enforced: no two modules share
    reads: list[str]
    consumes: list[str]        # event types
    def update(self, state: Any, event: Any, ctx: Any,
               params: dict, seed: bytes
               ) -> tuple[Any, list[ProposedDelta], list[ReasonEntry]]: ...
    def lod_update(self, state, event, ctx, params, seed, lod: int): ...
    def default_params(self) -> dict: ...
    def serialize(self) -> dict: ...
```

## 7.2 Worked template (NeedEngine)

```python
class NeedEngine:
    module_id = "need"; version = "0.5.0"
    owned_fields = ["needs"]
    reads = ["personality.big_five", "values.priorities", "world.time"]
    consumes = ["consume", "rest", "earn", "threat"]

    def default_params(self):
        return {"drift": {"hunger":0.0009,"sleep":0.0004,"safety":0.0,"recognition":0.0002},
                "threshold": {"hunger":0.6,"sleep":0.7,"safety":0.5,"recognition":0.5},
                "importance": {"hunger":0.9,"sleep":0.7,"safety":1.0,"recognition":0.4}}

    def update(self, needs, event, ctx, params, seed):
        reasons = []
        if event.type in ("consume","rest","earn"):
            nt = event.satisfies; reduce = event.magnitude
            needs[nt] = clamp01(needs[nt] - reduce)
            reasons.append(ReasonEntry(f"need.reduced.{nt}", -reduce, {}))
        if event.type == "threat":
            needs["safety"] = clamp01(needs["safety"] + event.severity)
            reasons.append(ReasonEntry("need.safety.raised", event.severity, {}))
        return needs, [], reasons   # NeedEngine owns needs; proposes nothing cross-cutting

    def drift(self, agent, delta, params):
        for nt, rate in params["drift"].items():
            agent.needs[nt] = clamp01(agent.needs[nt] + rate*delta)

    def value_terms(self, agent, action, params):
        # contribution to §3 utility
        terms = []
        for nt, lvl in agent.needs.items():
            pressure = max(0.0, lvl - params["threshold"][nt]) * params["importance"][nt]
            if pressure > 0 and action.reduces(nt):
                terms.append(("need", pressure))     # value in [0,1]
        return terms
```

## 7.3 Registry & wiring

A `TheoryRegistry` loads enabled modules from the World Pack, validates `owned_fields` disjointness at startup, and exposes them to the tick loop. World Packs enable/disable/parameterize modules (audit §4.3).

## 7.4 Determinism helper

```python
import hashlib
def derive_seed(global_seed, agent_id, event_id, world_time, module_id, salt=""):
    key = f"{global_seed}|{agent_id}|{event_id}|{world_time}|{module_id}|{salt}".encode()
    return hashlib.blake2b(key, digest_size=16).digest()
def seeded_uniform(seed):  # -> [0,1)
    return int.from_bytes(seed[:8], "big") / 2**64
```

---

# 8. Persistence & storage (explicit review: is it correct and sensible?)

**Short verdict: event-sourcing is the right core choice and directly powers the debugger/replay USP, but three things in the audit's storage plan are not yet correctly solved: unbounded ledger growth, persisted reason traces, and missing LOD-gating of per-agent stores.** Fixes below.

## 8.1 Architecture (correct as designed)

Append-only **event ledger** → materialized **world state** → per-agent **belief/memory/relationship projections** (audit §7.1). This gives reproducibility, rollback, savegame consistency, and `ReplayScenario`. Keep it.

## 8.2 SQLite schema (terminal MVP)

```sql
-- immutable ledger
CREATE TABLE event_ledger (
  event_id INTEGER PRIMARY KEY, world_time INTEGER NOT NULL,
  type TEXT, actor TEXT, payload JSON, seed BLOB, canonical INTEGER);
CREATE INDEX ix_ev_time ON event_ledger(world_time);

-- entities & propositions (typed, v0.4)
CREATE TABLE entity (id TEXT PRIMARY KEY, class TEXT, attrs JSON);
CREATE TABLE proposition (id TEXT PRIMARY KEY, predicate TEXT, slots JSON,
  polarity TEXT, valid_start INTEGER, valid_end INTEGER, spatial TEXT, context TEXT);

-- per-agent projections
CREATE TABLE belief (belief_id TEXT PRIMARY KEY, owner TEXT, proposition TEXT,
  expected_prob REAL, support_for REAL, support_against REAL, ignorance REAL,
  conflict REAL, logit REAL, provenance JSON, valid_start INTEGER, txn_time INTEGER);
CREATE INDEX ix_belief_owner ON belief(owner, proposition);

CREATE TABLE memory (memory_id TEXT PRIMARY KEY, owner TEXT, type TEXT, content TEXT,
  importance REAL, emotional_valence REAL, activation REAL, last_recalled INTEGER,
  source_conf REAL, retrieval_status TEXT, world_time INTEGER);
CREATE INDEX ix_mem_owner ON memory(owner, activation);

CREATE TABLE relationship (a TEXT, b TEXT, dims JSON, exchange_balance REAL,
  PRIMARY KEY (a,b));
CREATE TABLE reputation (subject TEXT, audience TEXT, dimension TEXT, degree REAL,
  PRIMARY KEY (subject,audience,dimension));
CREATE TABLE affect (agent TEXT PRIMARY KEY, pad_p REAL, pad_a REAL, pad_d REAL,
  active_emotions JSON, baseline JSON);
CREATE TABLE goal (goal_id TEXT PRIMARY KEY, owner TEXT, state TEXT, content JSON, priority REAL);
CREATE TABLE commitment (commitment_id TEXT PRIMARY KEY, debtor TEXT, creditor TEXT,
  content TEXT, deadline INTEGER, status TEXT);
CREATE TABLE conversation (conv_id TEXT PRIMARY KEY, participants JSON, state JSON);
CREATE TABLE schedule (agent TEXT, rule TEXT, activity TEXT);
CREATE TABLE media_exposure (agent TEXT, item TEXT, attention REAL, world_time INTEGER);

-- debug only (see 8.5)
CREATE TABLE reason_trace (event_id INTEGER, agent TEXT, entries JSON);

-- snapshots (see 8.4)
CREATE TABLE snapshot (world_time INTEGER PRIMARY KEY, state BLOB);
```

## 8.3 Projections vs ledger

Beliefs/memories/relationships are **materialized projections** rebuildable from the ledger. They are cached for query speed; the ledger is the source of truth. On load, restore from the latest snapshot + replay the ledger tail.

## 8.4 Growth analysis (the part to get right)

Back-of-envelope for the MVP (30 NPCs, one in-game day of active play):

- Player turns: ~hundreds. Background events (shifts, encounters, rumors, broadcasts): with discrete-event scheduling, ~10²–10³/day, **not** per-minute-per-agent (which would be 30·1440 ≈ 43k and is the wrong design).
- Event row ≈ 200–400 B → ledger ≈ a few MB/day. Fine for SQLite.
- Beliefs: 30 NPCs × ~10²–10³ propositions = 10³–10⁴ rows. Trivial.
- Memories: accumulate, but **consolidation + decay cap** them. Enforce a per-agent hard cap (e.g., 200 active episodic memories at LOD-3, fewer at lower LOD); below-cap, consolidate oldest low-importance into summaries (v0.1 §9.7) and **delete** the originals (or archive to a cold table). Without a delete/archive step, memory grows unbounded — **this is the audit's gap**.

At production scale (thousands of agents), the dominant cost is per-agent projections × N_agents. Solution = **LOD-gating (8.6)**, not a bigger database.

## 8.5 Compaction, snapshots, reason traces (fixes)

- **Snapshots**: every `S` world-minutes, persist a full state snapshot; truncate/compact ledger before the snapshot for shipping builds (keep the full ledger only in debug/replay builds). This bounds replay time and ledger size.
- **Ledger retention**: low-importance background events older than the last snapshot can be dropped in shipping builds; keep canonical/high-severity events. (Debug builds keep everything for `ReplayScenario`.)
- **Reason traces**: persisting a reason trace for *every* state change for every agent will balloon storage and is the single biggest unnecessary cost. **Fix: reason traces are debug-only**, written to a ring buffer (last `N` events) or sampled, not persisted in shipping builds. The explainability USP needs them *available on demand for the inspected agent*, not stored forever for all agents.

## 8.6 LOD-gating of stores (correctness fix)

- LOD-0/1 agents: no per-belief rows, no episodic memory — only a compact state vector (needs, schedule, a few summary memories, group memberships) advanced statistically. They get promoted to full projections only when they become interaction-relevant (player nearby). This is what makes thousands of agents storable.

## 8.7 Embeddings

Only for episodic summaries, authored lore, and fuzzy conversation-history retrieval (audit §7.3 — correct). Hard facts (location, ownership, secrets, beliefs) are **structured rows**, never embeddings. A vector index is optional and off by default in the MVP.

**Storage verdict:** the design is sound; implement (a) memory cap + delete-on-consolidate, (b) snapshots + ledger retention, (c) debug-only/sampled reason traces, (d) LOD-gated projections. With these, storage is bounded and sensible at both MVP and production scale.

---

# 9. The Terminal MVP Demo

A text-only game whose purpose is to **prove the NPC functionality end-to-end and to show how world/ontology/character data is ingested** — no graphics, no engine. This is the scientific reference and the sales demo in one.

## 9.1 What it must demonstrate

The 20 end-to-end cases (v0.3 §23.3) map onto the modules built above. The demo must visibly produce each, with a reason trace:

| Demo moment | Modules exercised |
|---|---|
| Player freely asks; NPC answers within its knowledge | Interpreter, Belief, Dialogue, Validator |
| Player lies about identity; NPC doesn't auto-believe | Belief (claim ≠ truth), credibility κ |
| NPC recognizes / culturally interprets clothing | appearance, culture, Perception |
| Noisy bar → partial hearing | Perception signal quality, environment |
| NPC remembers a promise; details fade, feeling stays | Memory (ACT-R, type-decay), commitment |
| Radio broadcasts biased report; only exposed NPCs update | media, channel, Belief, exposure |
| Rumor with shared origin discounted; independent witness counts more | provenance, correlation discount |
| NPC intentionally lies; validator permits it, marks stance; secret stays protected | deception, ToM, Validator layer-0 |
| Conversation reaches natural close | Dialogue anti-loop, topic exhaustion |
| Time jump → shift change, fatigue, mood relaxation | schedule, Need, Affect decay |
| NPC behaves differently before gang vs. alone | ImpressionMgmt, SelfCategorization salience |
| Trust drops fast on betrayal, recovers slowly | Relationship trust kinetics (§4.2) |
| Disguise → mistaken identity → later correction | identity, Perception, Belief revision |
| Save/reload reproduces all state and seeded mutations | event-sourcing, determinism |

## 9.2 Data ingestion (how the world/ontology/characters come in)

A **World Pack** is a directory of declarative files loaded at startup. This is the answer to "how does data come in":

```
worldpacks/cyberpunk-block/
├── ontology.json          # the v0.4 registry (classes, predicates, vocab schemes) — or a reference to unscripted-core
├── vocabularies.json      # ConceptScheme members for this world (Color, GangColors, Slang, ...)
├── world.json             # entities: places, items, groups, institutions, media channels
├── canon.json             # immutable propositions (canon_fact / protected_fact / reveal conditions)
├── characters/            # one file per NPC
│   └── npc_red_jacket.json
├── schedules.json         # daily routines (rrule), shift changes, opening hours
├── scenario.json          # initial world_time, global_seed, scheduled events, the opening situation
└── style.json             # world sprachstil for the realizer (register, slang, directness)
```

A character file is the full authored profile feeding the theory modules:

```json
{
  "id": "agent:npc_red_jacket",
  "class": "core:NPCAgent",
  "names": {"public": "Vee", "objective": "Valeria K."},
  "big_five": {"openness":0.6,"conscientiousness":0.4,"extraversion":0.7,"agreeableness":0.3,"emotional_stability":0.35},
  "schwartz": {"security":0.7,"self_direction":0.6,"power":0.5,"benevolence":0.4,"...":0.0},
  "needs": {"income":0.6,"safety":0.5,"recognition":0.4},
  "identities": [
    {"id":"gang_member","group":"group:reds","accessibility":0.8},
    {"id":"sister","group":"family:k","accessibility":0.9},
    {"id":"resident","group":"district:watson","accessibility":0.5}
  ],
  "roles": [{"role":"role:fixer","context":"group:reds"}],
  "appearance": {"garment":"item:red_cyberjacket","symbols":["sym:reds"]},
  "education": {"domains":{"street":0.8,"medicine":0.2}},
  "relationships": {"agent:barkeep_12":{"trust":0.4,"liking":0.2,"familiarity":0.6}},
  "secrets": ["prop:milan_location"],
  "goals": [{"content":"protect_brother_milan","priority":0.9}],
  "schedule_ref": "vee_default"
}
```

The **loader** validates every file against the JSON Schemas (§7.3), checks ontology conformance (types, cardinality, vocab membership), instantiates entities and per-agent module state, seeds the ledger with `canon.json` as canonical events at `t0`, and arms `scenario.json`'s scheduled events. **All authored data is structured and validated before any model runs** — nothing about the world lives in an LLM prompt.

## 9.3 The map & cast (v0.1 §20.2)

```
Apartment
   |
Main Street ── Bar ── Back Room
   |            
Clinic         
   |
Market ── Police Post
```

6 places, ~20–30 NPCs, 2 rival gangs, a security org, a radio channel, traders, a clinic, day/night cycle.

## 9.4 The game loop

```
=== Day 3 — 22:14 — Main Street ===
Three people stand outside the bar. A woman in a red cyberjacket leans on the wall.
> talk to the woman in the red jacket; ask if she was at the clinic yesterday
She studies you. Her right hand stays near her jacket pocket.
"Maybe. Why do you care?"
> I'm looking for my brother Milan. He supposedly works there.
Her posture loosens a little.
"Then you're either too late or someone lied to you. The clinic was shut last night."
```

The narrator describes **only observables** (v0.1 §20.5: "her hand stays near her pocket", never "she lies because she fears her gang"). Player commands: a small free-text grammar parsed by the Interpreter into actions + speech acts; the closed action catalog (v0.1 §15.1) bounds what is executable.

## 9.5 Annotated trace (what the demo shows on `inspect`)

```
> inspect last
EVENT evt_412  player asks Vee about clinic (yesterday)
  Perception: heard, quality 0.95 (close, quiet street)
  Belief: claim "looking_for_milan" stored unverified (κ_player=0.5 → no confidence change)
  Affect: appraisal(threat_to_secret) → fear 0.34 → PAD impulse (−0.34,+0.20,−0.24)
          mood now P-0.08 A+0.22 D-0.10; tendency: +conceal, +evade
  Identity: salient = "sister" (threat to brother raises its fit; softmax 0.71)
            → value weights: benevolence×1.0, security×1.0, gang-loyalty×0.4
  ToM: models player as not-yet-knowing milan_location (conf 0.8)
  Dialogue plan: act=evade+probe, goal=assess_threat, allowed={clinic_closed_last_night},
                 forbidden={milan_location} (NOT in prompt), stance=guarded
  Utility of chosen reply: evade 0.61 > truthful_answer 0.22 > threaten 0.15
  Validator: layer-0 (secret absent from prompt) ✓, leak-check ✓ → ACCEPT
```

This trace is the product. It shows *why* the NPC said what it said — knowledge, emotion, identity, ToM, and the secret never leaking.

## 9.6 Inspector views (v0.1 §19)

`inspect beliefs <npc>`, `inspect memory <npc>` (with activation + forgetting state), `inspect relationship <a> <b>`, `inspect conversation`, `inspect last` (the trace above), `replay <seed>`.

## 9.7 Build backlog (order for the coder)

1. Schemas + loader + ontology conformance (no behavior yet).
2. Event ledger + SQLite projections (§8) + determinism helper.
3. Perception → Belief → Memory (the knowledge spine).
4. AffectEngine (Part A) — visible via `inspect`.
5. Propose/apply + Relationship/Reputation/Identity (Part C).
6. NeedEngine, ValueEngine, MotivationEngine (BDI).
7. Utility aggregation + selection (Part B) with reason traces.
8. Social modules (Exchange, Identity, Norm, Network, ToM, ImpressionMgmt, Interpersonal).
9. Dialogue planner + Validator + a model provider (start with a small local model or a stub template realizer).
10. The 20 golden scenarios; wire `inspect`/`replay`.
11. Load a second pack (fantasy village) on the same runtime to prove portability.

---

# 10. Calibration & parameter management

~150 parameters across modules cannot be hand-tuned blindly (the audit's freeze criteria require ranges but no method). Approach:
- **Archetype presets**: ship 6–8 character archetypes (cautious clerk, hot-headed enforcer, weary medic…) as named parameter bundles; authors start from these.
- **High-level knobs → low-level params**: expose a handful of author-facing dials (e.g. "volatility", "loyalty", "openness to strangers") that expand deterministically to module parameters.
- **Sensitivity sweep + golden traces**: vary one parameter at a time on a fixed scenario, watch the trace; lock values that produce plausible behavior as golden defaults.
- **Behavioral judge** (§11): an automated check that a scenario still "reads" right after a parameter change.

---

# 11. Evaluation (structural + behavioral + population)

- **Structural** (unit/scenario): schema/type/contradiction/leak/repetition — pass/fail, CI-gated.
- **Adversarial**: prompt-injection and secret-probing suites measure the leak rate at the validator output for known forbidden facts.
- **Behavioral**: an LLM-as-judge scores consistency/plausibility of an NPC across a scene (the soft qualities no schema can check). Sampled, not gating, but tracked.
- **Population / emergent**: for the social-network and opinion modules, measure aggregate predictions — bounded confidence should yield N opinion clusters as a function of the confidence radius; weak ties should carry novel information across clusters faster than strong ties. These are falsifiable and validate the "society remembers" USP.
- **Determinism**: `replay(seed)` must reproduce byte-identical traces — a hard gate.

---

# 12. Decisions deliberately left open (honesty)

These do not block the reference runtime and should be decided with data, not now:

1. **Within-tick coupling.** The reference runtime uses one pass per event (emotion feeds the *next* event). If scenarios show this is too sluggish, add a bounded 2-iteration fixpoint for the affect↔appraisal loop only. Decide after measuring.
2. **Native language for the production core.** v0.1 §27 asked "Rust or C++?"; v0.5 silently chose C++20. **Reopen this.** For a small team, Rust gives memory safety and a clean C ABI (`cxx`/`cbindgen`) and is increasingly studio-accepted; the hot loop is bookkeeping, not heavy compute (the LLM call dominates latency), so native optimization is not urgent. Recommendation: **stay in the Python reference longer, profile, port only proven hot paths** — and benchmark Rust vs C++ before committing.
3. **ToM depth-2** and **opinion dynamics / structural balance** remain post-MVP and pack-gated.
4. **Embeddings provider** stays optional and off by default until fuzzy episodic recall is shown to be needed.

The theory and integration are now operational, deterministic, explainable, and testable — which is the bar from the audit's §11. The next concrete step is code: implement §7 → §2 → §4 → §3 → §5 → §6 → §8 → §9, scenario by scenario.
