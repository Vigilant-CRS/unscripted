# Unscripted
## Theory Completion Audit and Engineering Blueprint v0.5

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Date:** 22 June 2026  
**Status:** architecture decision draft  
**Builds on:** Ontology v0.4 Completion Pass

---

# 0. Executive conclusion

Ontology v0.4 is a strong semantic foundation, but it does not yet mean that the psychological and sociological theory is complete.

An ontology defines:

- which states and entities exist;
- how they are named;
- how they relate;
- what can be stored and queried.

A theory module additionally defines:

- how states change;
- which inputs cause the change;
- how competing causes are resolved;
- how time affects the state;
- which outputs influence decisions, dialogue and behavior;
- how the result is explained and tested.

The next theoretical deliverable should therefore not be another larger ontology. It should be a **Theory Runtime Specification** containing explicit update functions and module contracts.

The correct architecture is:

```text
Ontology and vocabularies
        ↓
Typed world and agent state
        ↓
Theory dynamics modules
        ↓
Decision and dialogue policy
        ↓
Language realization and validation
        ↓
Game-engine adapters
```

---

# 1. Audit of the models discussed so far

## 1.1 Big Five personality

### Status

Partially represented through generic traits such as openness, conscientiousness, extraversion, agreeableness and emotional stability.

### Missing

- explicit profile schema;
- optional facets below the five broad dimensions;
- mapping from traits to perception, appraisal, goal selection, dialogue and action;
- distinction between stable trait and temporary behavior;
- calibration ranges and behavioral effect limits.

### Decision

Mandatory core theory profile.

### Recommended state

```json
{
  "model": "big_five",
  "dimensions": {
    "openness": 0.72,
    "conscientiousness": 0.31,
    "extraversion": 0.64,
    "agreeableness": 0.18,
    "emotional_stability": 0.19
  }
}
```

Traits modify tendencies. They must never directly force a single action.

---

## 1.2 Schwartz basic values

### Status

Values and priorities exist generically.

### Missing

- explicit ten-value profile;
- conflict and compatibility structure;
- situational value salience;
- resolution of value conflicts;
- distinction between personal values and perceived group values.

### Decision

Mandatory core theory profile.

### Required mechanism

A value receives a context-dependent activation:

```text
active_value =
baseline_priority
× context_relevance
× identity_salience
× threat_or_opportunity
```

The action planner then evaluates both promoted and violated values.

---

## 1.3 Belief–Desire–Intention architecture

### Status

Beliefs, goals, intentions, plans and capabilities now exist.

### Missing

- intention commitment policy;
- rules for abandoning or reconsidering an intention;
- conflict resolution between goals;
- plan repair;
- resource reservation;
- interruption and resumption;
- separation of chosen goal, active intention and executable next step.

### Decision

Mandatory core planning architecture.

### Required state machine

```text
candidate goal
→ adopted goal
→ committed intention
→ selected plan
→ executable step
→ success / repair / suspend / abandon
```

---

## 1.4 OCC and Scherer-style appraisal

### Status

v0.4 adds goal congruence, agency, blameworthiness, expectedness and controllability.

### Missing

- desirability for self and others;
- norm and standard evaluation;
- attraction or aversion toward objects;
- coping potential;
- certainty;
- novelty;
- mapping table from appraisal patterns to emotions;
- emotion blending;
- secondary appraisal and reappraisal.

### Decision

Mandatory core emotion-generation module.

OCC should provide a computable event/person/object appraisal structure. Scherer-like appraisal dimensions can extend it where continuous process dynamics are useful.

---

## 1.5 PAD affective state

### Status

Arousal and dominance exist; mood and emotional valence are scattered across other records.

### Missing

- explicit valence dimension;
- one canonical PAD vector;
- temporal inertia;
- baseline return;
- topic-specific and relationship-specific offsets;
- mapping to animation, voice and dialogue style.

### Decision

Mandatory runtime state.

```json
{
  "valence": -0.42,
  "arousal": 0.71,
  "dominance": -0.18
}
```

PAD is not the explanation of the emotion. It is the compact continuous state used by expression systems.

---

## 1.6 Plutchik emotion wheel

### Status

Not explicitly standardized.

### Decision

Do not use it as the causal emotion engine.

Use it as an optional:

- authoring view;
- UI label system;
- dialogue-style label;
- mapping layer from appraisal outputs;
- analytics visualization.

The causal engine should remain appraisal-based.

---

## 1.7 Interpersonal Circumplex

### Status

Dominance, warmth-related relationship dimensions, respect, liking and hostility are present, but the circumplex is not explicit.

### Missing

- situational agency;
- situational communion;
- interpersonal behavior vector;
- complementarity rules;
- distinction between stable interpersonal tendency and current stance.

### Decision

Mandatory dialogue and interaction-style module.

```text
interaction style =
agency/dominance
+
communion/warmth
```

Examples:

- high agency, high communion: leading and supportive;
- high agency, low communion: controlling and hostile;
- low agency, high communion: accommodating and warm;
- low agency, low communion: withdrawn or submissive-hostile.

---

## 1.8 Social Exchange Theory

### Status

Debts, favors, commitments, dependence and resources are represented.

### Missing

- reciprocity expectations;
- exchange history;
- perceived fairness;
- comparison level;
- comparison with alternatives;
- dependence-derived power;
- generalized versus direct reciprocity;
- delayed repayment;
- trust effects of fulfilled and broken exchanges.

### Decision

Mandatory social relationship dynamics module.

This module is what turns `owes_favor` from stored data into behavior.

---

## 1.9 Social Identity Theory

### Status

Group membership, loyalty, status and group structures exist.

### Missing

- identification strength;
- in-group and out-group categorization;
- perceived group status;
- legitimacy and stability of status relations;
- identity threat;
- positive distinctiveness;
- group-based emotion.

### Decision

Mandatory group behavior module.

---

## 1.10 Self-Categorization Theory

### Status

Not explicit.

### Why needed

A person does not act through every identity at the same time. The salient identity changes with context:

- worker among customers;
- gang member near a rival;
- parent near a child;
- district resident during a local conflict.

### Decision

Mandatory extension to Social Identity Theory.

### Required calculation

```text
identity salience =
accessibility
× contextual fit
× comparative fit
× normative fit
× threat relevance
```

The salient identity activates group norms, stereotypes, loyalties and expected behavior.

---

## 1.11 Structural Balance

### Status

Relationships exist, but triadic balance pressure is not implemented.

### Missing

- signed social graph;
- triad tension;
- alliance and hostility pressure;
- delayed rather than immediate balancing;
- personality and interest resistance to balancing.

### Decision

Optional core social-network plugin, mandatory for faction-heavy World Packs.

It should create pressure, not deterministic friendship.

---

## 1.12 Strength of Weak Ties

### Status

Social connections exist, but no explicit bridge semantics.

### Missing

- tie strength;
- contact frequency;
- intimacy;
- multiplexity;
- bridge score;
- information novelty;
- local clustering.

### Decision

Mandatory for rumor and information diffusion.

Weak ties should spread information across clusters. Strong ties should produce higher trust and reinforcement inside clusters.

---

## 1.13 Bounded Confidence

### Status

Belief revision uses source reliability and provenance, but opinion-distance acceptance is not explicit.

### Missing

- continuous opinion dimensions;
- confidence radius;
- topic-dependent receptiveness;
- ideological distance;
- asymmetric influence;
- backfire or repulsion as optional behavior;
- polarization and clustering metrics.

### Decision

Optional opinion-dynamics module. Mandatory only for games featuring politics, factions, ideology, religion or public opinion.

It must not be used for ordinary factual beliefs such as current inventory or location.

---

## 1.14 Theory of Mind

### Status

v0.4 explicitly adds modeled beliefs, goals, intended listener belief and expected reactions.

### Missing

- uncertainty of the model;
- model decay;
- model-source provenance;
- correction after observing a reaction;
- false-belief and mistaken-model cases;
- per-agent depth and cost limit.

### Decision

Core module with depth one for normal agents and depth two only for high-detail agents.

---

## 1.15 ACT-R-inspired memory

### Status

Base-level activation, recency, repetition and cue-dependent retrieval are operationally specified.

### Missing

- source-memory confidence;
- cue competition;
- working-memory capacity;
- rehearsal and retrieval-induced strengthening;
- semantic versus episodic decay profiles;
- prospective memory for deadlines;
- memory reconstruction policy.

### Decision

Core memory model. Do not attempt to implement full ACT-R.

Use only the mechanisms that materially improve game behavior.

---

# 2. Additional models worth adding

These were not all explicitly discussed earlier, but they close important behavioral gaps.

## 2.1 Goffman-style self-presentation and impression management

### Why

Clothing, audience, place, role and surveillance already matter in the concept. A person behaves differently:

- front stage versus backstage;
- alone versus before peers;
- before a superior versus a subordinate;
- in uniform versus privately.

### Add

- desired impression;
- perceived audience;
- public role;
- private role;
- face threat;
- embarrassment risk;
- impression-repair action.

### Priority

High. This directly operationalizes clothing and social context.

---

## 2.2 Cognitive dissonance

### Why

NPCs need a mechanism for conflicts between:

- values and behavior;
- beliefs and evidence;
- loyalty and morality;
- self-image and failure.

### Add

- dissonance magnitude;
- importance of cognitions;
- available reduction strategies:
  - change belief,
  - change behavior,
  - rationalize,
  - blame another,
  - avoid information,
  - repair damage.

### Priority

Medium. Valuable for long-term character development, not required for the first terminal MVP.

---

## 2.3 Prospect Theory

### Why

The current action utility is too rational if it treats gains and losses symmetrically.

### Add

- reference point;
- loss aversion;
- probability weighting;
- framing as gain or loss;
- risk attitude by domain.

### Priority

Medium. Useful for theft, bargaining, danger, gambling, scarcity and desperate behavior.

---

## 2.4 Social norm expectations

Norms are already represented, but compliance needs more than a rule.

Add:

- empirical expectation: what the NPC thinks others do;
- normative expectation: what the NPC thinks others approve;
- expected sanction;
- observability;
- norm internalization;
- authority legitimacy.

### Priority

High.

---

## 2.5 Social learning and habit

Repeated behavior should become cheaper and more likely.

Add:

- action familiarity;
- habit strength;
- reinforcement history;
- observed-model prestige;
- imitation probability.

### Priority

Medium.

---

# 3. Models that should not become mandatory core

## 3.1 Myers–Briggs

Do not use as a runtime foundation. Continuous trait models are more suitable.

## 3.2 Maslow hierarchy as a fixed pyramid

Needs should exist, but no universal rigid ordering should be enforced. Hunger may override status for one agent but not another.

## 3.3 Moral Foundations Theory

Potentially useful for political or ideological World Packs, but too specific and culturally sensitive for the universal core. Schwartz values plus norms cover the general need.

## 3.4 Attachment theory

Useful for romance, family and caregiving, but should be an optional relationship pack.

## 3.5 Full psychoanalytic personality models

Too hard to operationalize, test and explain for a general-purpose SDK.

---

# 4. Theory-layer architecture

## 4.1 Ontology and theory are separate packages

```text
ontology package
  defines state and meaning

theory package
  defines transitions and updates

policy package
  selects actions and dialogue

realization package
  produces language and expression
```

## 4.2 Standard theory-module contract

Every theory module must declare:

```text
Module ID and semantic version
Owned state fields
Read-only input fields
Events consumed
Update function
Outputs produced
Parameter schema
Default parameters
LOD behavior
Reason codes
Determinism and random-seed policy
Serialization version
Unit tests
Scenario tests
```

No two modules may own the same state field.

## 4.3 Recommended modules

```text
PersonalityTheory
ValueTheory
NeedTheory
AppraisalTheory
AffectDynamics
MemoryTheory
BeliefRevisionTheory
GoalTheory
BDICommitmentTheory
RiskDecisionTheory
InterpersonalTheory
SocialExchangeTheory
SocialIdentityTheory
SelfCategorizationTheory
NormTheory
SocialNetworkTheory
OpinionDynamicsTheory
TheoryOfMind
ImpressionManagementTheory
```

World Packs enable, disable or parameterize modules.

---

# 5. Conflict resolution between theories

The modules must not independently choose behavior.

They contribute features or utility terms to one policy layer.

Example:

```text
Action candidate: report friend to police

Positive:
  professional duty
  legal norm
  fear of sanction

Negative:
  loyalty
  friendship
  expected social retaliation
  value conflict
  identity as family member

Risk modifier:
  loss aversion
  perceived probability of discovery

Emotion modifier:
  guilt
  fear
  anger
```

The policy engine owns the final choice and records all contributions as Reason Codes.

---

# 6. Correct engineering architecture

## 6.1 Do not begin with the Unreal plugin

Recommended sequence:

1. freeze specifications and schemas;
2. build a reference runtime;
3. prove behavior in the terminal game;
4. measure correctness;
5. implement production core;
6. add engine adapters.

## 6.2 Reference implementation

Use:

- Python;
- Pydantic or generated JSON-schema models;
- SQLite;
- deterministic event scheduler;
- optional local language-model provider;
- command-line and browser debug interface.

Purpose:

- fast iteration;
- scenario testing;
- calibrating equations;
- creating golden traces;
- validating the ontology.

This implementation is a scientific reference, not the final shipping SDK.

## 6.3 Production core

Recommended:

- C++20;
- stable C ABI facade;
- deterministic single-process embedded runtime;
- C# wrapper for Unity;
- native Unreal plugin;
- optional sidecar process for models too large to embed.

Why:

- direct Unreal integration;
- console and native-platform compatibility;
- predictable performance;
- easier source-code licensing to studios;
- no mandatory server architecture.

## 6.4 Avoid microservices in the embedded SDK

The default product should be a library, not a distributed platform.

Use optional services only for:

- cloud language models;
- shared multiplayer world memory;
- analytics;
- large-scale authoring simulation.

---

# 7. Runtime data architecture

## 7.1 Event-sourced core

Store an append-only event ledger:

```text
Event ledger
    ↓
materialized world state
    ↓
agent-specific belief projections
    ↓
memory and relationship projections
```

Benefits:

- reproducibility;
- debugging;
- savegame consistency;
- rollback;
- migration;
- scenario replay.

## 7.2 Storage

### Terminal MVP

SQLite tables for:

- entities;
- propositions;
- events;
- observations;
- claims;
- beliefs;
- evidence edges;
- memories;
- relationships;
- goals;
- intentions;
- conversations;
- commitments;
- schedules;
- media exposure.

### Production runtime

Retain an embedded store abstraction. Do not require a graph database.

Use relational edges and indexed adjacency tables. A vector index remains optional for textual memory retrieval.

## 7.3 Structured data first

Use structured queries for:

- facts;
- locations;
- ownership;
- relationships;
- commitments;
- current state;
- secrets;
- access rights.

Use embeddings only for:

- episodic summaries;
- authored lore;
- semantically related conversation history;
- fuzzy topic retrieval.

---

# 8. Runtime execution pipeline

## 8.1 Event path

```text
Engine event
→ canonical event
→ perception filtering
→ observations
→ evidence and belief update
→ memory encoding
→ appraisal
→ emotion and mood update
→ relationship and identity update
→ goals and intentions
→ action or dialogue candidates
→ policy selection
→ execution request
→ engine validation
→ resulting event
```

## 8.2 Dialogue path

```text
free player input
→ semantic parser
→ alternative interpretations
→ context and reference resolution
→ accepted speech act and propositions
→ audience and perception
→ belief and memory update
→ conversation-state update
→ NPC dialogue goal
→ topic and speech-act plan
→ allowed information package
→ text realization
→ stance-aware validation
→ output
→ stored conversation effects
```

## 8.3 Periodic path

```text
world-time advance
→ schedule changes
→ need changes
→ affect decay
→ memory decay and consolidation
→ commitment deadlines
→ background social encounters
→ media propagation
→ opinion dynamics
→ network and reputation updates
```

---

# 9. Codebase structure

```text
unscripted/
├── specs/
│   ├── ontology/
│   ├── vocabularies/
│   ├── theory-modules/
│   ├── world-pack-schema/
│   └── migrations/
├── schemas/
│   ├── event/
│   ├── proposition/
│   ├── belief/
│   ├── memory/
│   ├── agent/
│   ├── dialogue/
│   └── pack/
├── reference-runtime/
│   ├── world/
│   ├── perception/
│   ├── epistemics/
│   ├── memory/
│   ├── affect/
│   ├── motivation/
│   ├── social/
│   ├── planning/
│   ├── dialogue/
│   ├── validation/
│   ├── scheduler/
│   └── persistence/
├── native-runtime/
│   ├── include/unscripted/
│   ├── src/
│   ├── c-api/
│   └── tests/
├── providers/
│   ├── llm/
│   ├── embeddings/
│   ├── speech-to-text/
│   └── text-to-speech/
├── adapters/
│   ├── unreal/
│   ├── unity/
│   └── rest/
├── authoring/
│   ├── ontology-editor/
│   ├── world-pack-editor/
│   ├── character-editor/
│   └── trace-viewer/
├── demos/
│   ├── terminal-cyberpunk/
│   └── terminal-fantasy/
├── eval/
│   ├── unit/
│   ├── scenarios/
│   ├── adversarial/
│   ├── performance/
│   └── golden-traces/
└── docs/
```

---

# 10. Engineering rules

## 10.1 Determinism

Every stochastic decision uses:

- global seed;
- agent ID;
- event ID;
- world time;
- module ID.

## 10.2 No hidden state in language-model prompts

The authoritative state always remains in the runtime.

## 10.3 Every state change emits a reason trace

Example:

```json
{
  "change": "trust -0.14",
  "reasons": [
    "promise_broken",
    "high_commitment_importance",
    "relationship_dependency",
    "public_embarrassment"
  ]
}
```

## 10.4 One owner per state

Examples:

- Belief engine owns belief evidence.
- Memory engine owns memory activation.
- Affect engine owns emotion state.
- Relationship engine owns relationship vector.
- Dialogue engine owns conversation state.

## 10.5 Side-effect-free theory functions

Preferred functional form:

```text
new_state, emitted_effects, reason_trace =
update(old_state, event, context, parameters, seed)
```

This makes modules testable and replayable.

---

# 11. Theory freeze criteria

The theoretical layer is ready for engineering when:

1. every selected theory has a state schema;
2. every selected theory has an update rule;
3. input and output ownership are explicit;
4. conflicts between modules are resolved in one policy layer;
5. all parameters have units, ranges and defaults;
6. all randomness is seeded;
7. at least one scenario demonstrates each module;
8. theory modules can be disabled independently;
9. the same core runs in two different World Packs;
10. no model requires the language model to maintain authoritative state.

The theory does not need to be scientifically exhaustive. It needs to be coherent, computationally operational and falsifiable through tests.

---

# 12. Recommended scope for v0.5 theory core

## Mandatory for terminal MVP

- Big Five;
- Schwartz values;
- needs;
- BDI;
- appraisal emotion;
- PAD state;
- ACT-R-inspired memory;
- interpersonal circumplex;
- social exchange;
- social identity;
- self-categorization;
- norm expectations;
- weak-tie information diffusion;
- Theory of Mind depth one;
- impression management;
- belief revision and provenance.

## Optional after MVP

- structural balance;
- bounded-confidence opinion dynamics;
- cognitive dissonance;
- prospect theory;
- social learning and habit;
- attachment pack;
- advanced Theory of Mind depth two.

This keeps the MVP theoretically rich without turning it into an academic simulation of the entire human mind.

---

# 13. Immediate work packages

## Work package 1 — Theory registry

Create one machine-readable descriptor per theory module.

## Work package 2 — State ownership map

Document which module owns every mutable field.

## Work package 3 — Update equations

Define the actual transition functions and parameters.

## Work package 4 — Golden scenarios

Create deterministic scenarios with expected traces.

## Work package 5 — Reference runtime

Implement only the mandatory modules.

## Work package 6 — Terminal demonstrator

Build one cyberpunk block and later one fantasy village using the same runtime.

## Work package 7 — Production runtime decision

Only after the reference runtime passes the scenarios, freeze the native API and begin C++ implementation.

---

# 14. Final recommendation

The ontology should now stop growing horizontally for the moment.

The next document should be:

> **Unscripted Theory Dynamics Specification v0.5**

It should define the state-transition functions for the mandatory models, not add hundreds of new nouns.

After that, engineering should begin with the reference runtime and test harness, not with Unreal, graphical UI or a large language model integration.
