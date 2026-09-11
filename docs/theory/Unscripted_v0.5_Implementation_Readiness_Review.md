# Unscripted v0.5
## Implementation-Readiness Review for LLM-Assisted Coding

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Reviewed document:** `Unscripted_Theory_Dynamics_and_Engineering_v0.5.md`
**Date:** 22 June 2026 **Review objective:** Determine whether the specification
can be implemented reliably by an LLM coding agent and define the corrections
required before coding begins.

---

# 0. Executive verdict

## Overall assessment

The document is a strong architecture and research specification. It is suitable for:

- generating the repository skeleton;
- implementing isolated modules behind tests;
- building a narrow vertical slice;
- producing work packages and engineering tickets;
- guiding an iterative coding agent with human review.

It is **not yet suitable for a one-shot instruction such as “implement the entire system”**.

### Readiness scores

| Area | Score | Verdict |
|---|---:|---|
| Product and architecture clarity | 8.5/10 | Strong |
| Theory coverage | 8/10 | Strong, some mappings unresolved |
| Module decomposition | 7/10 | Good, but ownership and execution inconsistencies remain |
| Mathematical executability | 6/10 | Several formulas need correction or explicit normalization |
| Data-contract completeness | 4.5/10 | Major missing schemas and types |
| Runtime-loop correctness | 5/10 | Pseudocode contains integration bugs |
| Persistence design | 6/10 | Direction is good, schema is not production-safe |
| Testability | 7/10 | Strong intent, acceptance fixtures still missing |
| One-shot LLM implementation readiness | 3/10 | Not recommended |
| Iterative LLM-agent readiness after P0 fixes | 8/10 | Recommended |

## Precise answer

> The project is ready to enter engineering, but only after a short **contract-freeze phase**. An LLM coder may already build the scaffolding and individual tested modules. It should not yet implement the complete runtime end-to-end because ambiguities would be converted into architectural debt and inconsistent behavior.

---

# 1. What is already sufficiently specified

The following can be implemented now with little ambiguity:

1. Repository layout.
2. Deterministic seed derivation.
3. Base module protocol as a starting point.
4. Event-ledger concept.
5. Basic need drift.
6. Big-Five profile storage.
7. Basic PAD state container.
8. Relationship-vector storage.
9. World-Pack directory layout.
10. Initial terminal commands and inspector concept.
11. Reason-code structure.
12. Basic SQLite bootstrap.
13. Golden-trace testing infrastructure.
14. Provider interfaces as empty protocols.
15. A template-only dialogue realizer.

These are appropriate first tasks for an LLM coding agent.

---

# 2. P0 blockers before full implementation

P0 means that coding the dependent system before resolving the point is likely to create incorrect architecture rather than merely incomplete functionality.

## P0.1 No single canonical specification bundle

The v0.5 document depends repeatedly on v0.1, v0.2, v0.3 and v0.4. An implementing agent cannot infer which definition wins if terms differ.

### Risk

- stale field names;
- incompatible schemas;
- duplicate concepts;
- references to sections not in the coding context;
- silent implementation of superseded behavior.

### Required correction

Create a frozen implementation bundle:

```text
specs/
├── CORE_REQUIREMENTS.md
├── ontology-v0.4.json
├── vocabularies/
├── schemas/
├── theory-modules/
├── runtime-order.md
├── provider-contracts.md
├── persistence.md
└── decisions.md
```

Add a precedence rule:

```text
JSON Schema and registry
> explicit v0.5 module contract
> v0.4 ontology
> v0.2 technical formulas
> earlier conceptual documents
```

No coding ticket should cite an obsolete section without copying the binding requirement into the ticket.

---

## P0.2 Missing executable schemas

The document says that the loader validates JSON Schemas, but those schemas are not included.

### Missing authoritative types

At minimum:

- Entity;
- Event;
- EventRole;
- Proposition;
- LogicalExpression;
- Observation;
- Claim;
- Evidence;
- Belief;
- Memory;
- Relationship;
- Reputation;
- AffectState;
- EmotionInstance;
- Goal;
- Intention;
- Plan;
- ActionDefinition;
- ActionCandidate;
- ActionOutcome;
- Conversation;
- ConversationTurn;
- DialoguePlan;
- ValidationResult;
- WorldPackManifest;
- Snapshot;
- ReasonTrace.

### Required correction

Generate and freeze JSON Schemas before behavioral code. Then generate Python models from the schemas or maintain one source that emits both.

The LLM coder must not invent fields ad hoc.

---

## P0.3 The runtime loop does not apply returned state

The module contract returns:

```python
new_state, proposed_effects, reason_trace
```

The event-loop pseudocode assigns the returned state to `s` but does not assign it back to the agent.

```python
s, p, r = BeliefEngine.update(...)
```

`agent.beliefs = s` is absent. The same occurs for Memory and Affect.

### Additional loop omissions

The event path does not call:

- NeedEngine, although `threat` is defined to raise safety need;
- ImpressionManagementEngine;
- InterpersonalEngine;
- ValueEngine where contextual activation may change;
- SelfCategorization explicitly;
- AppraisalEngine as a separate producer.

### Required correction

Define two distinct module categories:

1. **State update modules** that return owned state.
2. **Feature providers** that compute transient terms without owning mutable state.

The orchestrator must use a registry-driven phase graph rather than a manually maintained list.

Correct pattern:

```python
result = module.update(
    state=state_store.read(module.owned_state_key, agent_id),
    event=event,
    context=context_snapshot,
    params=parameter_store.for_module(module.id),
    seed=seed_for(module.id),
)
state_store.stage(module.owned_state_key, agent_id, result.new_state)
proposal_bus.extend(result.proposals)
trace.extend(result.reasons)
```

All staged state is committed atomically after the phase.

---

## P0.4 “Pure functions” conflict with mutable examples

The document requires side-effect-free modules, but the NeedEngine example mutates the input dictionary:

```python
needs[nt] = ...
```

Its `drift()` method also mutates `agent.needs` directly.

### Risk

- replay divergence;
- hidden state changes;
- tests affected by object aliasing;
- difficult rollback;
- accidental cross-agent mutation.

### Required correction

Use immutable or copy-on-write state in the reference runtime:

```python
new_needs = dict(needs)
new_needs[need_type] = ...
return ModuleResult(new_state=new_needs, ...)
```

Periodic updates must use the same module contract as event updates.

---

## P0.5 Deterministic replay is incompatible with external LLM calls

The document requires byte-identical replay but also performs generative model calls. The same model, prompt and seed do not guarantee byte-identical output across:

- provider updates;
- hardware;
- serving stacks;
- quantization;
- sampling implementation;
- model version changes.

### Required correction

Define two replay modes:

#### Semantic replay

Re-executes deterministic simulation but reuses the recorded accepted utterance.

#### Model replay

Attempts regeneration for diagnostics but is not a hard byte-identity guarantee.

Persist for every generated turn:

```json
{
  "provider": "local",
  "model_id": "model-x",
  "model_hash": "...",
  "runtime_version": "...",
  "prompt_hash": "...",
  "generation_params": {},
  "raw_output": "...",
  "accepted_output": "...",
  "validator_version": "...",
  "validation_result": {}
}
```

The hard determinism gate should apply to structured state and semantic traces, not to fresh external-model inference.

---

## P0.6 Streaming before validation can leak secrets

The document proposes a streamed LLM call followed by validation. If tokens are shown to the player before validation completes, a forbidden fact can already be exposed.

### Required correction

Choose one mode:

1. **Buffered generation:** generate internally, validate, then display.
2. **Chunk-gated streaming:** buffer clauses or sentences, validate each before release.
3. **Deterministic high-secrecy templates:** no free streaming for protected interactions.

For the MVP, use buffered generation. The target latency is less important than proving non-leakage.

---

## P0.7 Affect state cannot be keyed only by emotion type

The current state is:

```python
active_emotions: dict[EmotionType, float]
```

This cannot represent:

- anger at the player;
- anger at the police;
- fear of the gang;
- gratitude toward a doctor;

at the same time.

### Required correction

Use emotion instances:

```python
@dataclass(frozen=True)
class EmotionInstance:
    id: str
    type: EmotionType
    target_id: str | None
    elicitor_event_id: str
    onset_time: int
    intensity: float
    appraisal_id: str
    decay_tau: float
```

Aggregated emotion by type remains a derived view.

---

## P0.8 The appraisal table does not match the ontology inputs

The table uses:

- desirability;
- praiseworthiness;
- attraction;
- prospective status;
- confirmation/disconfirmation;
- prior fear and hope.

The earlier ontology mainly specifies:

- goal congruence;
- agency;
- blameworthiness;
- expectedness;
- controllability.

### Required correction

Freeze an `AppraisalRecord` schema containing every required dimension and define how each is computed.

Do not allow the LLM to infer appraisal values freely.

---

## P0.9 Mood integration formula and description disagree

The document calls the formula exponential relaxation:

```text
mood += (baseline - mood) * min(1, Δt / τ)
```

This is Euler interpolation, not exact exponential relaxation. The stated half-return time only matches the exact exponential form.

### Correct formula

```text
alpha = 1 - exp(-Δt / τ)
mood = mood + alpha * (baseline - mood) + impulse
```

Then the half-life is:

```text
t_half = τ * ln(2)
```

Also define whether an emotion impulse is applied:

- only when the emotion is created or reinforced; or
- continuously as a force over time.

Applying the full impulse every periodic tick would rapidly saturate PAD.

---

## P0.10 Utility aggregation is not mathematically closed

Each term is said to lie in `[-1,1]`, but the sum of multiple terms in a group may exceed this interval. The emotion sum can also exceed the signed-unit range.

The document also says each term is passed through Prospect Theory, but utility terms are not necessarily uncertain monetary or scalar outcomes.

### Required correction

Introduce an explicit outcome model:

```python
@dataclass(frozen=True)
class ActionOutcome:
    dimension: ValueDimension
    delta: float
    probability: float
    reference_point: float
    source: str
```

Prospect transformation applies to outcomes, not directly to arbitrary module terms.

Then define:

```text
group_value = bounded_aggregate(outcome_values)
utility = Σ group_weight × group_value + bounded_emotion_bias
```

Recommended MVP:

- postpone full Prospect Theory;
- use expected normalized outcomes first;
- add the transform behind a feature flag after golden scenarios pass.

This also resolves the conflict with the earlier scope in which Prospect Theory was post-MVP.

---

## P0.11 Belief representation remains dual and underspecified

The document references both:

- log-odds update;
- support-for/support-against/ignorance/conflict.

It does not define the exact conversion and update rules between them.

### Risk

Two implementations can produce different beliefs from the same evidence.

### Required correction

Select one authoritative evidence representation.

Recommended:

- store atomic evidence contributions;
- derive subjective-opinion fields;
- derive expected probability and logit as cached views.

Alternatively, use a single log-odds implementation for MVP and defer explicit conflict/ignorance metrics. Do not maintain independent mutable versions of both.

---

## P0.12 Event sourcing and ledger truncation conflict

The ledger is called immutable and the source of truth, but the shipping design proposes deletion of older events after snapshots.

After deletion:

- projections can no longer be rebuilt from genesis;
- full causal explanation may be lost;
- byte-identical historical replay is impossible.

### Required correction

Define retention tiers:

1. canonical ledger retained permanently;
2. compacted background ledger summarized into signed aggregate events;
3. optional full debug archive;
4. snapshot plus tail as the operational savegame.

A snapshot must contain:

- schema version;
- ontology version;
- World-Pack hash;
- module versions;
- state checksum;
- last event ID;
- branch ID.

The phrase “ledger is the source of truth” should become:

> The current save state is defined by a verified snapshot plus its ordered event tail; canonical history remains append-only.

---

# 3. P1 issues that should be resolved before the second coding phase

## P1.1 State-ownership table is incomplete

Missing or ambiguous ownership includes:

- personality;
- value priorities;
- exchange balance;
- fairness;
- group identification;
- internalized norms;
- Theory-of-Mind models;
- face state;
- interpersonal stance;
- social-network edges;
- schedules.

Provide a complete ownership matrix.

---

## P1.2 ProposedDelta uses untyped string paths

```python
target_field: str
```

This allows invalid paths and runtime typos.

Use:

```python
StateKey(module="relationship", entity_id="npc_17", field="trust", subject_id="npc_42")
```

or typed proposal variants:

```python
TrustDelta
ReputationDelta
EmotionProposal
IdentityThreatProposal
```

The owner must validate source, range and target.

---

## P1.3 Simultaneous positive and negative trust proposals

The current design nets all proposals before applying either the slow-positive or fast-negative coefficient.

Example:

```text
+0.8 kindness and -0.7 betrayal → net +0.1
```

This loses the fact that betrayal should be strongly penalized.

Apply positive and negative totals separately:

```text
trust += η_up * sum_positive + η_down * sum_negative
```

then clamp.

---

## P1.4 Identity salience lacks an absolute “none strongly salient” state

Softmax forces all identities to sum to one even when the context weakly activates every identity.

Add:

- a neutral/self baseline category; or
- an absolute activation gate before softmax.

Also define:

- no-other-person case;
- overlapping identities;
- identities not known to observers;
- tie handling;
- temporal inertia to prevent rapid identity switching.

---

## P1.5 Social-exchange dependence formula is unsafe

```text
1 - best_alternative / current_relationship_value
```

can divide by zero, become negative or exceed the intended range.

Use a bounded ratio, for example:

```text
dependence = current_value / (current_value + best_alternative + epsilon)
```

and model power asymmetry from the difference between A’s and B’s dependence.

---

## P1.6 Candidate-action generation is missing

The utility engine can score candidates, but the system does not define who creates them.

Required:

- action catalog schema;
- preconditions;
- target binding;
- affordance query;
- candidate cap;
- fallback actions;
- dialogue-act candidate generation;
- deterministic candidate order.

Without this, an LLM coder will invent a planner architecture.

---

## P1.7 BDI plans are not specified enough to implement

Missing:

- plan representation;
- subgoal representation;
- variable binding;
- action effects;
- resource locking;
- failure codes;
- plan-library selection;
- repair algorithm;
- cycle detection.

For MVP, restrict plans to authored finite action graphs.

---

## P1.8 Parser contract is missing

The interpreter needs an exact result schema:

```text
interpretations[]
confidence
actions[]
speech_acts[]
propositions[]
references[]
temporal_expressions[]
unresolved_ambiguities[]
quoted_content[]
player_private_intent[]
```

Define the policy for low-confidence parses:

- ask a clarification;
- choose a safe interpretation;
- reject impossible action;
- separate spoken content from hidden intent.

---

## P1.9 Dialogue plan and validator contracts are missing

Freeze:

- allowed propositions;
- allowed derived propositions;
- avoid-topic patterns;
- secrecy labels;
- speech act;
- stance;
- uncertainty requirement;
- lie authorization;
- maximum length;
- progress requirement;
- fallback template ID.

Define a structured validation result with hard and soft failures.

---

## P1.10 SQLite schema is only illustrative

Before coding persistence, add:

- foreign keys;
- schema versions;
- branch/world IDs;
- composite uniqueness constraints;
- normalized evidence edges;
- normalized event roles;
- transaction boundaries;
- idempotency keys;
- migration framework;
- checks for numeric ranges;
- current-state and history separation;
- snapshot checksum.

Do not use the current SQL as final migration code.

---

## P1.11 LOD promotion and demotion are not specified

When a statistical NPC becomes interactive:

- how are episodic memories materialized?
- what knowledge is inferred from summary state?
- which facts are guaranteed?
- how is continuity preserved?

When demoted:

- what gets summarized?
- what is discarded?
- which commitments and secrets must remain?

This needs an explicit promotion/demotion protocol.

---

## P1.12 Model-provider failure behavior is missing

Define:

- timeout;
- retry;
- cancellation;
- provider unavailable;
- malformed JSON;
- context too long;
- unsupported language;
- content-policy rejection;
- deterministic fallback;
- circuit breaker;
- telemetry fields.

---

# 4. What an LLM coder may implement immediately

## Safe first work package

The following can start before all P1 issues are solved:

### Milestone 0 — Repository and quality gates

- Python package;
- type checking;
- linting;
- test runner;
- migration framework;
- logging;
- CI;
- deterministic seed helper.

### Milestone 1 — Canonical schemas

Only after the schema package is supplied:

- models;
- serialization;
- validation;
- IDs;
- World-Pack manifest;
- loader error reporting.

### Milestone 2 — Event ledger and replay without LLM

- append event;
- snapshot;
- restore;
- semantic replay;
- checksum;
- branch ID;
- golden trace.

### Milestone 3 — Three-module vertical slice

Implement only:

1. Perception;
2. Belief;
3. Memory.

Scenario:

- player makes a claim;
- one NPC hears it;
- another cannot hear it;
- first NPC stores a belief and memory;
- save/load reproduces state.

### Milestone 4 — Controlled dialogue without generative model

- authored dialogue plans;
- template realizer;
- common ground;
- topic state;
- anti-loop;
- safe fallback.

Only after this works should a small language model be added as an interchangeable renderer.

---

# 5. Recommended coding strategy

## Do not issue one giant prompt

Use one isolated ticket per contract or behavior.

Each ticket should contain:

- purpose;
- files allowed to change;
- authoritative schema;
- inputs;
- outputs;
- invariants;
- edge cases;
- tests;
- acceptance command;
- prohibited design changes.

## Example ticket

```text
Implement MemoryActivationService.

Inputs:
- MemoryRecord[]
- RetrievalQuery
- WorldTime
- MemoryParams

Outputs:
- ranked RecallCandidate[]

Invariants:
- input records are not mutated;
- result is deterministic for identical input;
- maximum W results;
- unresolved commitments receive deadline boost;
- inaccessible memories are excluded;
- activation is finite.

Tests:
- recent > old with otherwise equal fields;
- repeated > single exposure;
- emotional trace survives longer;
- cue lifts a below-threshold memory;
- identical seed and input produce identical output.
```

## Mandatory agent rules

The coding agent must:

- never invent new persistent fields;
- never change schemas without an architecture decision record;
- never call an LLM from a theory module;
- never mutate input state;
- always add tests;
- preserve deterministic ordering;
- produce a migration for persistent changes;
- record reason codes for state transitions.

---

# 6. Revised build sequence

## Phase A — Contract freeze

1. consolidate authoritative requirements;
2. freeze schemas;
3. freeze event/action/dialogue contracts;
4. freeze module ownership;
5. correct the affect and utility mathematics;
6. decide the authoritative belief representation;
7. define semantic replay.

## Phase B — Knowledge spine

1. World-Pack loader;
2. event ledger;
3. perception;
4. beliefs;
5. memories;
6. save/load;
7. inspector.

## Phase C — One NPC interaction

1. conversation state;
2. dialogue plan;
3. template realization;
4. validator;
5. anti-loop;
6. one controlled free-text parser.

## Phase D — Psychological dynamics

1. needs;
2. appraisal;
3. emotion instances;
4. PAD mood;
5. relationships;
6. trust proposals.

## Phase E — Social behavior

1. identity salience;
2. social exchange;
3. norms;
4. impression management;
5. Theory of Mind;
6. rumor network;
7. reputation.

## Phase F — Generative realization

1. provider interface;
2. buffered generation;
3. parse-back;
4. secret validation;
5. semantic replay records;
6. fallback behavior.

## Phase G — Scale and portability

1. LOD;
2. background simulation;
3. second World Pack;
4. performance benchmarks;
5. native-runtime evaluation.

---

# 7. Definition of Ready for full LLM-agent implementation

The complete reference runtime is ready to be assigned when all boxes are checked:

- [ ] one canonical spec bundle exists;
- [ ] all core JSON Schemas exist;
- [ ] no unresolved field ownership remains;
- [ ] runtime phase graph is frozen;
- [ ] state updates are transactionally applied;
- [ ] EmotionInstance replaces type-only emotion storage;
- [ ] appraisal schema matches emotion rules;
- [ ] exact mood integration is corrected;
- [ ] utility normalization is defined;
- [ ] Prospect Theory is deferred or given explicit outcomes;
- [ ] one authoritative belief-evidence model is selected;
- [ ] action candidate generation is specified;
- [ ] parser output schema is frozen;
- [ ] dialogue and validator schemas are frozen;
- [ ] semantic replay behavior for LLM output is frozen;
- [ ] snapshot and retention semantics are frozen;
- [ ] provider failure behavior is specified;
- [ ] 20 golden scenarios have expected structured outcomes;
- [ ] first five tickets contain explicit acceptance tests.

---

# 8. Final recommendation

## Is it ready?

### Yes, for:

- repository scaffolding;
- contract implementation;
- isolated module coding;
- a narrow knowledge-spine vertical slice;
- iterative agentic development with tests.

### No, for:

- complete one-shot implementation;
- parallel implementation of all theory modules;
- production persistence;
- secret-safe streamed generation;
- claiming deterministic replay across fresh LLM inference;
- immediate Unreal integration.

## Recommended next artifact

Create:

> **Unscripted Implementation Contract Pack v0.6**

It should contain only machine-binding artifacts and concise engineering decisions:

1. schemas;
2. module ownership map;
3. phase graph;
4. event and action catalogs;
5. parser result schema;
6. dialogue plan schema;
7. validation schema;
8. belief-evidence decision;
9. snapshot and replay contract;
10. first 20 scenario fixtures.

Once v0.6 exists, an LLM coding agent can implement the reference runtime in controlled milestones with substantially less architectural improvisation.
