# Unscripted
## Ontology, Semantics and Technical Core v0.3

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Status:** implementation-ready draft, not frozen standard  
**Date:** 22 June 2026  
**Relation:** reviews and extends `Unscripted_Technical_Core_v0.2.md`  
**Companion artifact:** `unscripted_core_ontology_v0.3.json`

---

# 0. Executive verdict

The v0.2 draft is a strong and unusually concrete technical foundation. It correctly identifies typed propositions, belief revision, rumor provenance, reproducibility and output validation as load-bearing components. It is, however, **not yet perfect or complete**.

The main reason is not lack of detail. The current model is still too narrow in several places for a general-purpose SDK:

1. it treats almost every semantic object as an entity reference;
2. it represents propositions as fixed positional argument lists;
3. it lacks a complete distinction between proposition, attitude and speech act;
4. it treats uncertainty and conflicting evidence too similarly;
5. its spatial and temporal constraints are too simple;
6. it does not yet cover identity, disguise, clothing, work, education, norms, dialogue common ground, causality, narrative control and multiplayer privacy as first-class ontology modules;
7. it assumes a closed catalog without specifying a safe extension and migration mechanism.

The correct objective is therefore not a single finite list that can never change. The correct objective is:

> **A stable, versioned upper ontology plus mandatory runtime modules and world-specific extension packs.**

This is how the system can become broad enough for many genres without becoming an unmaintainable universal database.

---

# 1. Audit of v0.2

## 1.1 What is already strong

The following elements should be preserved:

- canonical typed propositions instead of opaque strings;
- explicit provenance;
- temporal and spatial qualifiers;
- contradiction detection;
- belief confidence;
- correlation discounting;
- seeded rumor mutation;
- context minimization before generation;
- structured dialogue plans;
- deterministic fallback;
- measured leak, repetition and contradiction rates;
- explicit latency budgets;
- operational rather than decorative formulas.

## 1.2 Critical correction: distrust is not the same as adversarial reliability

The v0.2 source-reliability formula allows general distrust to push reliability below `0.5`. In log-odds updating, a source below `0.5` is interpreted as **systematically inversely reliable**: what the source says becomes evidence for the opposite.

That is correct only for a known adversarial liar. It is not correct for ordinary skepticism.

The model must distinguish:

- **low trust:** attenuate evidence toward neutral likelihood ratio `1`;
- **unknown competence:** attenuate evidence;
- **known liar/adversary:** explicitly invert evidence;
- **motivated source:** apply topic-specific bias;
- **honest but mistaken source:** high honesty, low competence.

Recommended decomposition:

```text
evidence_strength =
channel_quality
× attention
× source_honesty
× source_competence
× listener_trust
× access_plausibility
× novelty
```

Only a separate `adversariality` parameter may invert the sign.

## 1.3 Critical correction: ignorance and balanced conflict are different

A probability of `0.5` can mean:

- no information at all, or
- strong evidence for and strong evidence against.

Those states have different narrative consequences. A cautious NPC with no evidence says:

> “I have no idea.”

An NPC with conflicting testimony says:

> “Half the street says one thing, the police say another.”

The final belief record therefore needs at least:

- expected probability,
- positive support,
- negative support,
- ignorance,
- conflict,
- provenance graph.

A practical implementation can retain log-odds for decisions but must also store dual evidence or a subjective-opinion tuple.

## 1.4 Critical correction: roles and locations are not simply functional

An agent can simultaneously be:

- inside a room,
- inside a building,
- in a district,
- in a city.

Therefore `located_at` is not globally functional. Use:

- `space:exactly_at` for the smallest authoritative place;
- `space:located_within` for inherited containment.

Likewise, a person can simultaneously be:

- bartender,
- parent,
- gang informant,
- tenant,
- citizen.

`has_role` is contextual and multi-valued, not globally functional.

Cardinality constraints must be scoped by:

- predicate,
- key slots,
- context,
- valid time,
- spatial granularity.

## 1.5 Critical correction: proposition, attitude and utterance must be separate

The same proposition can be:

- asserted,
- denied,
- questioned,
- quoted,
- hypothesized,
- joked about,
- used sarcastically,
- intentionally lied about.

A truth-conditional proposition must therefore not carry the full communicative status.

Required layers:

1. **Proposition:** what would be true or false.
2. **Epistemic attitude:** what an agent believes, doubts or suspects.
3. **Speech act:** what an agent does socially by speaking.
4. **Stance:** asserted, hypothetical, ironic, quoted, uncertain and so on.
5. **Surface realization:** the actual sentence.

Without these layers, the validator will falsely classify questions, lies, jokes and quotations as hallucinations.

## 1.6 Critical correction: open-world semantics

Absence of a proposition is not evidence of its negation.

Default:

- unknown ≠ false;
- not observed ≠ did not happen;
- not remembered ≠ never known;
- not authorized ≠ false.

Some domains may use local closed-world rules, for example:

- current inventory,
- current occupants of a locked room,
- active quest flags,
- authoritative account balance.

Closed-world domains must be explicitly declared.

## 1.7 Critical correction: contradiction is constraint-based

Direct negation is only one contradiction type.

The engine also needs:

- cardinality conflicts;
- disjoint classes;
- incompatible states;
- impossible temporal overlap;
- impossible spatial overlap;
- narrative constraints;
- world-physics constraints;
- incompatible quantities;
- superseded states.

Paraconsistent storage is preferable: contradictory evidence may coexist without allowing arbitrary conclusions.

## 1.8 Critical correction: output validation must allow controlled false speech

An NPC may intentionally:

- lie,
- bluff,
- threaten with a consequence it cannot deliver,
- repeat a rumor,
- quote someone else,
- speculate,
- speak metaphorically.

Therefore the validator must not require every uttered proposition to be personally believed above `c_assert`.

Instead it checks the **speech policy**:

- asserted as fact → sufficiently believed, unless deception is authorized;
- reported speech → source must be represented;
- speculation → uncertainty marker required;
- lie → false-belief relation and deception intention required;
- joke/irony → stance must be explicit in the plan;
- threat → capability and commitment may be separately represented.

## 1.9 Important improvement: named semantic slots

Fixed positional argument arrays are compact but brittle. They make migration, debugging and cross-predicate mapping difficult.

Recommended representation:

```json
{
  "predicate": "economy:owes_amount",
  "slots": {
    "debtor": "agent:player_1",
    "creditor": "agent:barkeep_12",
    "amount": "quantity:300_credits"
  },
  "valid_time": { "start": 60981, "end": null },
  "polarity": "positive"
}
```

Named slots improve:

- schema validation,
- readability,
- predicate evolution,
- semantic parsing,
- explanation,
- model prompting.

## 1.10 Important improvement: versioned namespaces

The ontology needs:

- namespace per module;
- semantic version;
- immutable IDs;
- deprecation markers;
- aliases;
- migration scripts;
- compatibility declarations;
- pack dependencies;
- conformance tests.

Example:

```text
unscripted-core 0.3
unscripted-dialogue 0.3
unscripted-cyberpunk-pack 0.1 requires unscripted-core >= 0.3 < 0.4
```

---

# 2. Ontology architecture

## 2.1 Four layers

### Layer A — Upper ontology

Stable, genre-independent concepts:

- agent,
- object,
- place,
- event,
- state,
- proposition,
- time,
- information,
- role,
- norm.

### Layer B — Runtime ontology

Mandatory concepts needed by the engine:

- observation,
- belief,
- memory,
- goal,
- intention,
- relationship,
- conversation,
- dialogue act,
- commitment,
- media message,
- reputation.

### Layer C — Gameplay-domain modules

Optional reusable modules:

- combat,
- economy,
- work,
- education,
- clothing,
- health,
- law,
- organizations,
- media,
- weather,
- romance,
- transport.

### Layer D — World Pack

Game-specific additions:

- Night-City-like districts;
- specific gangs and corporations;
- fantasy magic schools;
- monsters;
- proprietary currencies;
- unique laws;
- authored lore;
- style rules;
- plot constraints.

## 2.2 What belongs in the standard

The standard should freeze:

- representation format;
- base classes;
- mandatory predicates;
- event-role model;
- evidence and provenance format;
- temporal and spatial qualification;
- dialogue-act framework;
- privacy and disclosure labels;
- versioning;
- conformance tests.

It should not freeze every possible profession, weapon, monster, spell or cultural norm.

---

# 3. Canonical representation

## 3.1 Distinguish entities, concepts and literals

The v0.2 type lattice places `quantity`, `trait_value` and similar values next to entities. The revised model separates:

- **Entity IDs:** persistent world objects;
- **Concept IDs:** classes, roles, topics and categories;
- **Literal values:** strings, booleans, numbers;
- **Quantity values:** number plus unit;
- **References:** proposition, event, memory and document IDs.

## 3.2 Atomic proposition

```json
{
  "id": "prop:991",
  "predicate": "appearance:wears",
  "slots": {
    "agent": "agent:npc_12",
    "garment": "item:red_jacket"
  },
  "polarity": "positive",
  "valid_time": { "start": 62000, "end": null },
  "spatial_scope": "place:hamilton_street",
  "context": "world:main",
  "schema_version": "0.3.0"
}
```

## 3.3 Logical expression

Required for:

- conjunction,
- disjunction,
- implication,
- conditional,
- quantification,
- reveal conditions,
- norms,
- plans.

```json
{
  "operator": "and",
  "operands": ["prop:991", "prop:992"]
}
```

MVP support may be limited to:

- `and`,
- `or`,
- `not`,
- `if`,
- `exists`.

## 3.4 Valid time and transaction time

Every mutable record should distinguish:

- **valid time:** when it was true in the world;
- **transaction time:** when the runtime learned or stored it.

This is necessary for:

- delayed reports,
- retroactive corrections,
- savegame migration,
- investigations,
- “What did the police know at that time?”

## 3.5 Context

A proposition may belong to:

- canonical world,
- current savegame,
- simulation branch,
- dream,
- hallucination,
- hypothetical plan,
- quoted story,
- game-within-game.

Context IDs prevent fictional or hypothetical content from contaminating world truth.

---

# 4. Class hierarchy

The machine-readable companion contains the full starter hierarchy. The top level is:

```text
Thing
├── Continuant
│   ├── Agent
│   │   ├── PersonAgent
│   │   │   ├── PlayerAgent
│   │   │   └── NPCAgent
│   │   └── CollectiveAgent
│   │       ├── Group
│   │       ├── Institution
│   │       └── Organization
│   ├── PhysicalObject
│   │   ├── Body
│   │   ├── BodyPart
│   │   └── Item
│   │       ├── Garment
│   │       ├── Weapon
│   │       └── Tool
│   ├── Place
│   ├── Resource
│   └── DigitalObject
├── Occurrent
│   ├── Event
│   │   ├── Action
│   │   ├── CommunicationEvent
│   │   ├── PerceptionEvent
│   │   ├── EconomicEvent
│   │   ├── InstitutionalEvent
│   │   └── LifeEvent
│   ├── State
│   └── Process
├── AbstractEntity
│   ├── Role
│   ├── Skill
│   ├── Goal
│   ├── Intention
│   ├── Norm
│   ├── Relationship
│   ├── Topic
│   └── TimeEntity
└── InformationEntity
    ├── Proposition
    ├── Claim
    ├── Belief
    ├── Observation
    ├── Memory
    ├── Message
    ├── MediaItem
    ├── Conversation
    └── Record
```

---

# 5. Event ontology

## 5.1 Event frames rather than endless binary predicates

Actions are represented as event entities with typed roles:

- actor,
- patient,
- recipient,
- instrument,
- object,
- origin,
- destination,
- place,
- time,
- manner,
- severity,
- result.

Example:

```json
{
  "event_id": "event:threat_77",
  "event_type": "event:ThreatAction",
  "roles": {
    "actor": "agent:player_1",
    "patient": "agent:merchant_17",
    "instrument": "item:pistol_4"
  },
  "place": "place:market",
  "valid_time": { "start": 61002, "end": 61003 },
  "severity": 0.62
}
```

## 5.2 Core event classes

The standard starter catalog includes:

- movement, entering, leaving and travel;
- transfer, giving, taking and theft;
- use, equip, hide, damage and repair;
- attack, threat, help, rescue and killing;
- arrest, hiring, firing, promotion and sanction;
- buying, selling, payment and bribery;
- birth, death, injury, recovery and relationship changes;
- assertion, question, answer, request, command, promise, warning, apology, accusation, confession, denial, lie, joke, greeting and farewell;
- broadcast.

World Packs add domain-specific subclasses.

---

# 6. Agent ontology

## 6.1 Identity

Required distinctions:

- objective identity,
- public identity,
- alias,
- digital identity,
- disguise,
- perceived identity,
- mistaken identity,
- role identity.

## 6.2 Body and condition

First-class states:

- alive,
- conscious,
- injured,
- pain,
- fatigue,
- hunger,
- thirst,
- intoxication,
- mobility,
- visible features.

## 6.3 Clothing and appearance

Clothing must influence both capability and social interpretation.

Represent:

- garment worn;
- color, style and condition;
- symbols displayed;
- items concealed;
- protection afforded;
- role and group signaled;
- perceived status;
- recognition cues.

The meaning of clothing is culturally scoped. A jacket does not objectively mean “gang member”; a culture, institution or observer interprets it that way.

## 6.4 Work, education and expertise

Represent separately:

- profession,
- employer,
- job title,
- active shift,
- assigned task,
- income;
- credential,
- training,
- skill,
- skill level,
- domain competence,
- experience,
- literacy and language ability.

This feeds:

- source credibility;
- vocabulary;
- perception;
- available actions;
- schedules;
- social status;
- goals.

## 6.5 Personality, values and needs

Personality values are continuous. Values and needs remain separate.

Required:

- trait profile;
- value priorities;
- current needs;
- current goals;
- goal priority;
- intentions;
- preferences;
- aversions;
- emotion toward target;
- mood;
- stress;
- arousal;
- dominance;
- self-control.

---

# 7. Social ontology

## 7.1 Relationship vector

Do not collapse relationships into friendship.

Mandatory dimensions:

- familiarity,
- trust,
- liking,
- respect,
- fear,
- dependence,
- loyalty,
- rivalry,
- alliance,
- enmity,
- favor debt,
- shared secrets.

## 7.2 Family, hierarchy and institutions

Represent:

- family relation;
- friend and romantic relation;
- supervision;
- authority;
- membership;
- representation;
- jurisdiction;
- affiliation.

## 7.3 Collective agents

Groups and institutions can have:

- goals;
- policies;
- memory;
- records;
- reputation;
- media channels;
- norms;
- resources;
- territory;
- internal roles.

A collective must not simply inherit every member’s knowledge. Group knowledge requires a communication or record path.

---

# 8. Knowledge, belief and evidence

## 8.1 Five separate objects

```text
Event       What happened?
Observation What was perceived?
Claim       What was communicated?
Belief      What is currently accepted?
Memory      What can later be retrieved?
```

## 8.2 Recommended belief record

```json
{
  "belief_id": "belief:44",
  "owner": "agent:npc_12",
  "proposition": "prop:991",
  "expected_probability": 0.63,
  "support_for": 1.8,
  "support_against": 0.9,
  "ignorance": 0.21,
  "conflict": 0.34,
  "provenance": ["obs:12", "claim:55"],
  "valid_time": { "start": 61000, "end": null },
  "transaction_time": 61004
}
```

## 8.3 Reliability decomposition

Reliability should be a function of:

- perception/channel quality;
- attention;
- honesty;
- competence in the relevant domain;
- access plausibility;
- listener trust;
- known bias;
- adversariality;
- evidence independence.

Skepticism reduces update magnitude. Only adversariality inverts evidence.

## 8.4 Evidence graph

Every belief update must retain:

- origin event;
- observation chain;
- speakers;
- media items;
- transformations;
- shared origins;
- contradictions;
- retractions.

Correlation discounting operates on this graph rather than on a flat maximum-overlap heuristic.

## 8.5 Derived beliefs

Inference rules must be:

- typed;
- versioned;
- explainable;
- cycle-safe;
- scoped to contexts;
- recalculated when premises change.

Rule confidence must be rule-specific. A universal product of antecedent probabilities is not sufficient.

---

# 9. Memory ontology

## 9.1 Memory types

- episodic;
- semantic;
- social;
- procedural;
- commitment;
- conversation thread;
- emotional trace;
- summary;
- place memory;
- group memory;
- media memory.

## 9.2 Memory transformations

- consolidation;
- summarization;
- detail loss;
- generalization;
- misattribution;
- source confusion;
- emotional amplification;
- reinterpretation;
- correction;
- suppression;
- retrieval-induced strengthening.

## 9.3 Forgetting state

A memory should expose:

- activation;
- retrieval probability;
- cue dependence;
- known missing slots;
- uncertainty;
- last access;
- consolidation target;
- distortion source.

## 9.4 No automatic confabulation

If a detail is missing, the NPC should preferably:

- admit uncertainty,
- produce a range,
- ask for a cue,
- confuse only according to an explicit seeded mutation.

The language model must not fill missing memory slots freely.

---

# 10. Dialogue and discourse ontology

## 10.1 Dialogue acts

The core list contains 36 acts, including:

- inform,
- ask,
- answer,
- confirm,
- deny,
- correct,
- clarify,
- request,
- command,
- offer,
- accept,
- reject,
- promise,
- threaten,
- warn,
- advise,
- apologize,
- forgive,
- accuse,
- confess,
- evade,
- lie,
- joke,
- mock,
- praise,
- greet,
- farewell,
- topic change,
- interruption,
- closure,
- uncertainty,
- quotation,
- hypothesis,
- negotiation.

## 10.2 Stance

Required stance values:

- asserted,
- denied,
- questioned,
- requested,
- hypothetical,
- conditional,
- counterfactual,
- quoted,
- reported speech,
- uncertain,
- sarcastic,
- ironic,
- metaphorical,
- joking,
- deceptive,
- presupposed,
- implied.

## 10.3 Conversation state

Represent:

- participants;
- turns;
- active topic;
- common ground;
- open questions;
- resolved issues;
- topic state;
- per-participant goals;
- interruptions;
- closure reason.

## 10.4 Common ground

A fact may be:

- privately known to one participant;
- mutually known;
- believed to be mutually known;
- disputed;
- intentionally concealed.

This prevents NPCs from repeating information both participants already established.

## 10.5 Reference resolution

Free text requires:

- pronouns;
- aliases;
- deictic references such as “here”, “yesterday” and “that guy”;
- quoted speech;
- ellipsis;
- corrections;
- ambiguous targets;
- multi-action sentences.

The interpreter must emit confidence and alternatives rather than force a single parse.

---

# 11. Deception ontology

A lie is not merely a false utterance.

Required conditions:

1. speaker presents proposition as true;
2. speaker believes or strongly suspects it is false;
3. speaker intends the listener to accept it;
4. the utterance has a deceptive stance.

Also represent:

- bluff;
- omission;
- evasive answer;
- impersonation;
- disguise;
- alias;
- detection of deception;
- accidental misinformation.

This distinction is essential for relationship updates and later confrontation.

---

# 12. Norms, law and commitments

## 12.1 Deontic states

Represent:

- obligation;
- permission;
- prohibition;
- authority;
- jurisdiction;
- applicability;
- violation;
- sanction.

## 12.2 Commitments

Promises, contracts and debts need:

- debtor;
- creditor;
- content;
- deadline;
- conditions;
- status;
- fulfillment event;
- breach event;
- excuse;
- social and legal consequences.

## 12.3 Norm conflicts

A figure may face:

- legal duty versus family loyalty;
- group order versus personal morality;
- professional secrecy versus immediate danger.

The action planner must compare active norms and values rather than assume one absolute rule.

---

# 13. Environment and context

Environment is a first-class influence on perception and behavior:

- weather;
- lighting;
- noise;
- temperature;
- crowd density;
- surveillance;
- danger;
- privacy;
- visibility;
- contamination;
- local norm salience.

The same utterance in a private room and on a monitored street has different risk, audience and phrasing.

---

# 14. Media and collective memory

## 14.1 Media item

Represent:

- publisher;
- channel;
- claims;
- framing;
- audience;
- credibility by observer;
- editorial bias;
- publication time;
- exposure;
- attention.

## 14.2 Collective memory

Separate:

- canonical history;
- savegame chronicle;
- place memory;
- organization records;
- public narrative;
- cultural narrative;
- rumor network.

## 14.3 No automatic broadcast knowledge

A character receives information only if:

- exposed;
- attentive enough;
- able to understand the language;
- able to access the channel;
- not blocked by technical or social constraints.

---

# 15. Reputation ontology

Reputation is audience-specific.

Represent dimensions such as:

- dangerous;
- reliable;
- generous;
- corrupt;
- competent;
- loyal;
- violent;
- truthful.

A player may be respected by a gang, feared by shopkeepers and unknown to another district.

Public narrative labels are not objective facts.

---

# 16. Narrative and authorial control

A studio needs hard guarantees.

Represent:

- canon facts;
- protected facts;
- reveal conditions;
- plot gates;
- quest states;
- authorial priority;
- spoiler level;
- dynamic hooks.

A generative NPC may improvise around a plot but must not:

- reveal protected information early;
- kill protected characters;
- resolve a gated quest without the condition;
- contradict immutable lore.

---

# 17. Security, privacy and multiplayer

## 17.1 Information classification

Every sensitive information object may define:

- classification level;
- allowed agents;
- allowed groups;
- need-to-know rule;
- declassification condition.

## 17.2 Multiplayer

Distinguish:

- human player;
- avatar;
- account identity;
- party;
- voice channel;
- private message;
- public speech;
- consent scope;
- persistent memory scope.

An NPC must not attribute one player’s statement to another merely because they share an avatar type or party.

---

# 18. Contradiction and consistency model

## 18.1 Constraint families

- direct polarity conflict;
- class disjointness;
- cardinality conflict;
- temporal incompatibility;
- spatial disjointness;
- quantity bounds;
- world-physics constraint;
- narrative constraint;
- authority constraint;
- state-machine constraint.

## 18.2 Paraconsistency

Contradictory evidence is stored and surfaced. It does not collapse the knowledge base.

Possible statuses:

- supported;
- refuted;
- both supported and refuted;
- unknown;
- superseded;
- context-dependent.

## 18.3 State transitions

Mutable states should use explicit transitions:

```text
employed → fired
alive → dead
door_locked → door_unlocked
commitment_open → fulfilled
```

The previous state remains historical but not currently active.

---

# 19. Disclosure and validation policy

## 19.1 Planner output

The planner should produce:

- speech act;
- stance;
- intended content;
- permitted disclosure;
- prohibited disclosure;
- allowed uncertainty;
- deception policy;
- style;
- desired conversational effect.

## 19.2 Taint analysis

Facts derived from secrets must inherit a secrecy label unless a declassification rule exists.

This prevents allowed facts from being combined to infer a protected secret.

## 19.3 Validation order

1. structured plan validation;
2. disclosure policy;
3. realization;
4. parse-back to speech act and propositions;
5. stance-aware containment;
6. contradiction and canon check;
7. repetition and progress check;
8. deterministic fallback.

## 19.4 Safe fallback

Fallbacks must exist per dialogue act and World Pack, not as generic error messages.

---

# 20. Ontology lifecycle

## 20.1 Registry rules

Every class and predicate needs:

- immutable ID;
- label;
- description;
- namespace;
- version introduced;
- deprecation version;
- replacement ID;
- slot schema;
- constraints;
- examples;
- test cases.

## 20.2 Migration

A pack update may:

- add predicate;
- add optional slot;
- deprecate term;
- split term;
- merge terms;
- change cardinality only with migration.

## 20.3 Conformance suite

A compliant pack must pass:

- schema validation;
- type validation;
- inverse consistency;
- disjointness tests;
- cardinality tests;
- temporal tests;
- disclosure tests;
- deterministic replay;
- free-text parse tests;
- multilingual label separation.

---

# 21. Module inventory

The companion JSON currently defines **129 classes** and **275 predicates** across the following modules:

| Module | Predicate count |
|---|---:|
| `appearance` | 13 |
| `body` | 13 |
| `causality` | 7 |
| `culture` | 8 |
| `deception` | 7 |
| `dialogue` | 16 |
| `discourse` | 10 |
| `economy` | 12 |
| `education` | 7 |
| `environment` | 11 |
| `epistemic` | 15 |
| `event` | 11 |
| `identity` | 13 |
| `media` | 10 |
| `memory` | 13 |
| `multiplayer` | 4 |
| `narrative` | 8 |
| `norm` | 12 |
| `perception` | 9 |
| `psychology` | 14 |
| `reputation` | 6 |
| `security` | 5 |
| `social` | 17 |
| `space` | 16 |
| `time` | 12 |
| `work` | 6 |

This is a starter core, not a claim that every future game-specific concept is already present. Completeness is achieved through the extension contract and conformance rules.

---

# 22. Predicate catalog

### appearance

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `appearance:wears` | agent: `core:Agent`, garment: `core:Garment` | — |
| `appearance:equipped_with` | agent: `core:Agent`, item: `core:Item` | — |
| `appearance:carries` | agent: `core:Agent`, item: `core:Item` | — |
| `appearance:garment_style` | garment: `core:Garment`, style: `core:Concept` | — |
| `appearance:garment_color` | garment: `core:Garment`, color: `core:Concept` | — |
| `appearance:garment_condition` | garment: `core:Garment`, condition: `core:Concept` | — |
| `appearance:displays_symbol` | entity: `core:Thing`, symbol: `core:Concept` | — |
| `appearance:conceals_item` | garment: `core:Garment`, item: `core:Item` | — |
| `appearance:protects_against` | garment: `core:Garment`, hazard: `core:Concept`, degree: `literal:probability` | — |
| `appearance:signals_role` | appearance_item: `core:Thing`, role: `core:Role`, culture: `core:CollectiveAgent` | — |
| `appearance:signals_group` | appearance_item: `core:Thing`, group: `core:Group`, culture: `core:CollectiveAgent` | — |
| `appearance:perceived_status` | observer: `core:Agent`, target: `core:Agent`, status: `core:Concept` | — |
| `appearance:recognition_cue` | observer: `core:Agent`, target: `core:Agent`, cue: `core:Thing` | — |

### body

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `body:has_body` | agent: `core:Agent`, body: `core:Body` | — |
| `body:has_part` | body: `core:Body`, part: `core:BodyPart` | — |
| `body:alive` | agent: `core:Agent` | — |
| `body:conscious` | agent: `core:Agent` | — |
| `body:injured` | agent: `core:Agent`, severity: `literal:probability` | — |
| `body:has_condition` | agent: `core:Agent`, condition: `core:Concept` | — |
| `body:pain_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:fatigue_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:hunger_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:thirst_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:intoxication_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:mobility_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `body:visible_feature` | agent: `core:Agent`, feature: `core:Concept` | — |

### causality

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `event:causes` | cause: `core:Thing`, effect: `core:Thing` | — |
| `event:enables` | condition: `core:Thing`, effect: `core:Thing` | — |
| `event:prevents` | condition: `core:Thing`, effect: `core:Thing` | — |
| `event:motivates` | cause: `core:Thing`, agent: `core:Agent`, action: `core:Action` | — |
| `event:explains` | explanation: `core:Thing`, explanandum: `core:Thing` | — |
| `event:expected_outcome` | action: `core:Action`, state: `core:State`, probability: `literal:probability` | — |
| `event:counterfactual_result` | condition: `core:Proposition`, result: `core:Proposition` | — |

### culture

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `culture:belongs_to` | agent: `core:Agent`, culture: `core:CollectiveAgent` | — |
| `culture:has_norm` | culture: `core:CollectiveAgent`, norm: `core:Norm` | — |
| `culture:has_taboo` | culture: `core:CollectiveAgent`, topic: `core:Topic` | — |
| `culture:uses_dialect` | agent: `core:Agent`, language: `core:Language`, dialect: `core:Concept` | — |
| `culture:preferred_register` | agent: `core:Agent`, context: `core:Thing`, register: `core:Concept` | — |
| `culture:interprets_symbol_as` | culture: `core:CollectiveAgent`, symbol: `core:Concept`, meaning: `core:Concept` | — |
| `culture:status_marker` | culture: `core:CollectiveAgent`, marker: `core:Thing`, status: `core:Concept` | — |
| `culture:etiquette_rule` | culture: `core:CollectiveAgent`, norm: `core:Norm` | — |

### deception

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `deception:intends_to_deceive` | agent: `core:Agent`, target: `core:Agent`, content: `core:Proposition` | — |
| `deception:presents_as_true` | agent: `core:Agent`, content: `core:Proposition` | — |
| `deception:believes_false` | agent: `core:Agent`, content: `core:Proposition` | — |
| `deception:uses_disguise` | agent: `core:Agent`, disguise: `core:Thing` | — |
| `deception:impersonates` | agent: `core:Agent`, identity: `core:Thing` | — |
| `deception:conceals_identity` | agent: `core:Agent`, identity: `core:Thing` | — |
| `deception:detects_deception` | observer: `core:Agent`, deceiver: `core:Agent`, content: `core:Proposition`, confidence: `literal:probability` | — |

### dialogue

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `dialogue:has_speaker` | utterance: `core:CommunicationEvent`, speaker: `core:Agent` | — |
| `dialogue:has_addressee` | utterance: `core:CommunicationEvent`, addressee: `core:Agent` | — |
| `dialogue:has_audience` | utterance: `core:CommunicationEvent`, audience: `core:Agent` | — |
| `dialogue:uses_language` | utterance: `core:CommunicationEvent`, language: `core:Language` | — |
| `dialogue:has_act` | utterance: `core:CommunicationEvent`, act: `core:DialogueAct` | — |
| `dialogue:has_topic` | utterance: `core:CommunicationEvent`, topic: `core:Topic` | — |
| `dialogue:has_content` | utterance: `core:CommunicationEvent`, content: `core:InformationEntity` | — |
| `dialogue:has_stance` | utterance: `core:CommunicationEvent`, stance: `core:Concept` | asserted, questioned, hypothetical, ironic, quoted, denied, uncertain usw. |
| `dialogue:answers` | answer: `core:CommunicationEvent`, question: `core:CommunicationEvent` | — |
| `dialogue:presupposes` | utterance: `core:CommunicationEvent`, content: `core:Proposition` | — |
| `dialogue:implies` | utterance: `core:CommunicationEvent`, content: `core:Proposition` | — |
| `dialogue:quotes` | utterance: `core:CommunicationEvent`, quoted_event: `core:CommunicationEvent` | — |
| `dialogue:has_tone` | utterance: `core:CommunicationEvent`, tone: `core:Concept` | — |
| `dialogue:has_volume` | utterance: `core:CommunicationEvent`, degree: `literal:probability` | — |
| `dialogue:privacy_scope` | utterance: `core:CommunicationEvent`, scope: `core:Concept` | — |
| `dialogue:overheard_by` | utterance: `core:CommunicationEvent`, agent: `core:Agent` | — |

### discourse

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `dialogue:conversation_participant` | conversation: `core:Conversation`, agent: `core:Agent` | — |
| `dialogue:contains_turn` | conversation: `core:Conversation`, turn: `core:ConversationTurn` | — |
| `dialogue:active_topic` | conversation: `core:Conversation`, topic: `core:Topic` | — |
| `dialogue:common_ground_contains` | conversation: `core:Conversation`, proposition: `core:Proposition` | — |
| `dialogue:open_question` | conversation: `core:Conversation`, content: `core:InformationEntity` | — |
| `dialogue:resolved_issue` | conversation: `core:Conversation`, content: `core:InformationEntity` | — |
| `dialogue:topic_state` | conversation: `core:Conversation`, topic: `core:Topic`, state: `core:Concept` | — |
| `dialogue:conversation_goal` | conversation: `core:Conversation`, agent: `core:Agent`, goal: `core:Goal` | — |
| `dialogue:interrupts` | turn: `core:ConversationTurn`, interrupted_turn: `core:ConversationTurn` | — |
| `dialogue:closes` | turn: `core:ConversationTurn`, conversation: `core:Conversation` | — |

### economy

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `economy:owns` | owner: `core:Agent`, object: `core:Thing` | — |
| `economy:possesses` | holder: `core:Agent`, object: `core:Thing` | — |
| `economy:has_custody_of` | holder: `core:Agent`, object: `core:Thing` | — |
| `economy:borrowed_from` | borrower: `core:Agent`, object: `core:Thing`, lender: `core:Agent` | — |
| `economy:stolen_from` | object: `core:Thing`, victim: `core:Agent` | — |
| `economy:owes_amount` | debtor: `core:Agent`, creditor: `core:Agent`, amount: `core:QuantityValue` | — |
| `economy:price_of` | seller: `core:Agent`, object: `core:Thing`, amount: `core:QuantityValue` | — |
| `economy:can_afford` | agent: `core:Agent`, amount: `core:QuantityValue` | — |
| `economy:resource_stock` | holder: `core:Thing`, resource: `core:Resource`, quantity: `core:QuantityValue` | — |
| `economy:scarcity_level` | resource: `core:Resource`, region: `core:Region`, degree: `literal:probability` | — |
| `economy:market_demand` | resource: `core:Resource`, region: `core:Region`, degree: `literal:probability` | — |
| `economy:offers_service` | agent: `core:Agent`, service: `core:Concept` | — |

### education

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `education:has_credential` | agent: `core:Agent`, credential: `core:EducationCredential` | — |
| `education:trained_in` | agent: `core:Agent`, domain: `core:KnowledgeDomain` | — |
| `education:has_skill` | agent: `core:Agent`, skill: `core:Skill` | — |
| `education:skill_level` | agent: `core:Agent`, skill: `core:Skill`, degree: `literal:probability` | — |
| `education:domain_competence` | agent: `core:Agent`, domain: `core:KnowledgeDomain`, degree: `literal:probability` | — |
| `education:experience_duration` | agent: `core:Agent`, domain: `core:KnowledgeDomain`, duration: `core:QuantityValue` | — |
| `education:literate_in` | agent: `core:Agent`, language: `core:Language`, degree: `literal:probability` | — |

### environment

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `environment:weather_state` | region: `core:Region`, state: `core:Concept` | — |
| `environment:lighting_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:noise_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:temperature` | place: `core:Place`, quantity: `core:QuantityValue` | — |
| `environment:crowd_density` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:surveillance_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:danger_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:privacy_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:visibility_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:contamination_level` | place: `core:Place`, degree: `literal:probability` | — |
| `environment:local_norm_salience` | place: `core:Place`, norm: `core:Norm`, degree: `literal:probability` | — |

### epistemic

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `epistemic:believes` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:knows` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:suspects` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:doubts` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:denies` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:unaware_of` | agent: `core:Agent`, proposition: `core:Proposition` | — |
| `epistemic:evidence_for` | evidence: `core:Thing`, proposition: `core:Proposition` | — |
| `epistemic:evidence_against` | evidence: `core:Thing`, proposition: `core:Proposition` | — |
| `epistemic:source_of` | information: `core:InformationEntity`, source: `core:Thing` | — |
| `epistemic:derived_from` | conclusion: `core:InformationEntity`, premise: `core:InformationEntity` | — |
| `epistemic:contradicts` | left: `core:Proposition`, right: `core:Proposition` | Eigenschaften: symmetric. |
| `epistemic:supersedes` | new_information: `core:InformationEntity`, old_information: `core:InformationEntity` | — |
| `epistemic:confidence` | attitude: `core:InformationEntity`, degree: `literal:probability` | — |
| `epistemic:conflict_level` | belief: `core:Belief`, degree: `literal:probability` | — |
| `epistemic:ignorance_level` | belief: `core:Belief`, degree: `literal:probability` | — |

### event

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `event:has_actor` | event: `core:Event`, actor: `core:Agent` | — |
| `event:has_patient` | event: `core:Event`, patient: `core:Thing` | — |
| `event:has_recipient` | event: `core:Event`, recipient: `core:Agent` | — |
| `event:has_instrument` | event: `core:Event`, instrument: `core:Thing` | — |
| `event:has_object` | event: `core:Event`, object: `core:Thing` | — |
| `event:has_origin` | event: `core:Event`, origin: `core:Place` | — |
| `event:has_destination` | event: `core:Event`, destination: `core:Place` | — |
| `event:has_location` | event: `core:Event`, place: `core:Place` | — |
| `event:has_result` | event: `core:Event`, result: `core:State` | — |
| `event:has_manner` | event: `core:Event`, manner: `core:Concept` | — |
| `event:has_severity` | event: `core:Event`, degree: `literal:probability` | — |

### identity

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `core:instance_of` | entity: `core:Thing`, class: `core:Concept` | Ordnet eine Instanz einer Klasse zu; nicht mit natürlicher Sprachbezeichnung verwechseln. |
| `core:has_name` | entity: `core:Thing`, name: `literal:string` | — |
| `core:has_alias` | entity: `core:Thing`, alias: `literal:string` | — |
| `core:same_identity_as` | left: `core:Thing`, right: `core:Thing` | Strenge Identitätsbehauptung; nur durch autoritative Regeln setzen. Eigenschaften: symmetric. |
| `core:recognized_as` | observer: `core:Agent`, perceived_entity: `core:Thing`, identity: `core:Thing` | Subjektive Identifizierung, nicht objektive Identität. |
| `core:uses_identity` | agent: `core:Agent`, identity_profile: `core:DigitalObject` | — |
| `core:has_role` | agent: `core:Agent`, role: `core:Role`, context: `core:Thing` | Nicht global funktional; ein Agent kann mehrere Rollen in verschiedenen Kontexten besitzen. |
| `core:member_of` | agent: `core:Agent`, group: `core:Group` | — |
| `core:has_member` | group: `core:Group`, agent: `core:Agent` | — |
| `core:affiliated_with` | agent: `core:Agent`, organization: `core:Organization` | — |
| `core:represents` | agent: `core:Agent`, collective: `core:CollectiveAgent` | — |
| `core:legal_status` | agent: `core:Agent`, status: `core:Concept` | — |
| `core:social_status` | agent: `core:Agent`, status: `core:Concept`, community: `core:CollectiveAgent` | — |

### media

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `media:published_by` | item: `core:MediaItem`, publisher: `core:CollectiveAgent` | — |
| `media:distributed_via` | item: `core:MediaItem`, channel: `core:Thing` | — |
| `media:contains_claim` | item: `core:MediaItem`, claim: `core:Claim` | — |
| `media:has_framing` | item: `core:MediaItem`, frame: `core:Concept` | — |
| `media:source_credibility` | source: `core:Thing`, audience: `core:Agent`, degree: `literal:probability` | — |
| `media:audience_scope` | item: `core:MediaItem`, scope: `core:Thing` | — |
| `media:exposed_to` | agent: `core:Agent`, item: `core:MediaItem` | — |
| `media:consumed` | agent: `core:Agent`, item: `core:MediaItem`, attention: `literal:probability` | — |
| `media:shared_with` | item: `core:MediaItem`, sender: `core:Agent`, recipient: `core:Agent` | — |
| `media:editorial_bias` | source: `core:Thing`, bias: `core:Concept` | — |

### memory

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `memory:owned_by` | memory: `core:Memory`, agent: `core:Agent` | — |
| `memory:about` | memory: `core:Memory`, subject: `core:Thing` | — |
| `memory:encodes` | memory: `core:Memory`, content: `core:InformationEntity` | — |
| `memory:memory_type` | memory: `core:Memory`, type: `core:Concept` | — |
| `memory:importance` | memory: `core:Memory`, degree: `literal:probability` | — |
| `memory:activation` | memory: `core:Memory`, value: `literal:number` | — |
| `memory:last_recalled_at` | memory: `core:Memory`, instant: `core:TimeInstant` | — |
| `memory:retrieved_by_cue` | memory: `core:Memory`, cue: `core:Thing` | — |
| `memory:consolidated_into` | source: `core:Memory`, summary: `core:Memory` | — |
| `memory:distorted_from` | memory: `core:Memory`, source: `core:Memory` | — |
| `memory:forgotten_detail` | memory: `core:Memory`, slot: `literal:string` | — |
| `memory:emotionally_tagged` | memory: `core:Memory`, emotion: `core:Emotion`, degree: `literal:probability` | — |
| `memory:retrieval_status` | memory: `core:Memory`, status: `core:Concept` | — |

### multiplayer

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `multiplayer:controls_avatar` | player: `core:PlayerAgent`, avatar: `core:Agent` | — |
| `multiplayer:member_of_party` | player: `core:PlayerAgent`, group: `core:Group` | — |
| `multiplayer:voice_channel_member` | player: `core:PlayerAgent`, channel: `core:Thing` | — |
| `multiplayer:permitted_visibility` | observer: `core:Agent`, target: `core:Thing`, scope: `core:Concept` | — |

### narrative

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `narrative:canon_fact` | proposition: `core:Proposition` | — |
| `narrative:protected_fact` | proposition: `core:Proposition`, policy: `core:Concept` | — |
| `narrative:reveal_condition` | proposition: `core:Proposition`, condition: `core:LogicalExpression` | — |
| `narrative:plot_gate` | gate: `core:Concept`, condition: `core:LogicalExpression` | — |
| `narrative:quest_state` | quest: `core:Concept`, state: `core:Concept` | — |
| `narrative:authorial_priority` | content: `core:InformationEntity`, priority: `literal:probability` | — |
| `narrative:spoiler_level` | content: `core:InformationEntity`, level: `core:Concept` | — |
| `narrative:dynamic_hook` | event: `core:Event`, hook: `core:Concept` | — |

### norm

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `norm:obligated_to` | agent: `core:Agent`, action: `core:Action`, norm: `core:Norm` | — |
| `norm:permitted_to` | agent: `core:Agent`, action: `core:Action`, norm: `core:Norm` | — |
| `norm:forbidden_to` | agent: `core:Agent`, action: `core:Action`, norm: `core:Norm` | — |
| `norm:has_authority_over` | authority: `core:Agent`, subject: `core:Agent`, domain: `core:Concept` | — |
| `norm:applies_in` | norm: `core:Norm`, context: `core:Thing` | — |
| `norm:violated_by` | norm: `core:Norm`, event: `core:Event` | — |
| `norm:has_sanction` | norm: `core:Norm`, sanction: `core:Concept` | — |
| `norm:commitment_by` | commitment: `core:Commitment`, debtor: `core:Agent` | — |
| `norm:commitment_to` | commitment: `core:Commitment`, creditor: `core:Agent` | — |
| `norm:commitment_content` | commitment: `core:Commitment`, content: `core:Proposition` | — |
| `norm:commitment_status` | commitment: `core:Commitment`, status: `core:Concept` | — |
| `norm:contract_contains` | document: `core:Document`, commitment: `core:Commitment` | — |

### perception

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `perception:observed` | observer: `core:Agent`, event: `core:Event` | — |
| `perception:perceived_entity` | observer: `core:Agent`, entity: `core:Thing`, modality: `core:Concept` | — |
| `perception:signal_quality` | observation: `core:Observation`, degree: `literal:probability` | — |
| `perception:attention_level` | observer: `core:Agent`, target: `core:Thing`, degree: `literal:probability` | — |
| `perception:line_of_sight` | observer: `core:Agent`, target: `core:Thing` | — |
| `perception:hearing_access` | observer: `core:Agent`, source: `core:Thing`, degree: `literal:probability` | — |
| `perception:recognized_identity` | observer: `core:Agent`, target: `core:Thing`, identity: `core:Thing`, confidence: `literal:probability` | — |
| `perception:noticed_feature` | observer: `core:Agent`, target: `core:Thing`, feature: `core:Concept` | — |
| `perception:inferred_from` | conclusion: `core:Proposition`, observation: `core:Observation` | — |

### psychology

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `psych:has_trait` | agent: `core:Agent`, trait: `core:Trait`, degree: `literal:probability` | — |
| `psych:holds_value` | agent: `core:Agent`, value: `core:Value`, priority: `literal:probability` | — |
| `psych:has_need` | agent: `core:Agent`, need: `core:Need`, level: `literal:probability` | — |
| `psych:has_goal` | agent: `core:Agent`, goal: `core:Goal` | — |
| `psych:goal_priority` | agent: `core:Agent`, goal: `core:Goal`, priority: `literal:probability` | — |
| `psych:committed_to` | agent: `core:Agent`, intention: `core:Intention` | — |
| `psych:prefers` | agent: `core:Agent`, object: `core:Thing`, degree: `literal:probability` | — |
| `psych:averse_to` | agent: `core:Agent`, object: `core:Thing`, degree: `literal:probability` | — |
| `psych:emotion_toward` | agent: `core:Agent`, emotion: `core:Emotion`, target: `core:Thing`, degree: `literal:probability` | — |
| `psych:mood_state` | agent: `core:Agent`, mood: `core:Mood`, degree: `literal:probability` | — |
| `psych:stress_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `psych:arousal_level` | agent: `core:Agent`, degree: `literal:probability` | — |
| `psych:dominance_state` | agent: `core:Agent`, degree: `literal:number_minus1_plus1` | — |
| `psych:self_control` | agent: `core:Agent`, degree: `literal:probability` | — |

### reputation

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `reputation:holds_reputation` | subject: `core:Thing`, audience: `core:CollectiveAgent`, dimension: `core:Concept`, degree: `literal:number_minus1_plus1` | — |
| `reputation:local_reputation` | subject: `core:Thing`, place: `core:Place`, dimension: `core:Concept`, degree: `literal:number_minus1_plus1` | — |
| `reputation:narrative_label` | subject: `core:Thing`, label: `core:Concept`, community: `core:CollectiveAgent` | — |
| `reputation:rumor_about` | rumor: `core:Claim`, subject: `core:Thing` | — |
| `reputation:fame_level` | subject: `core:Thing`, audience: `core:CollectiveAgent`, degree: `literal:probability` | — |
| `reputation:credibility_reputation` | subject: `core:Agent`, audience: `core:CollectiveAgent`, degree: `literal:probability` | — |

### security

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `security:classification` | information: `core:InformationEntity`, level: `core:Concept` | — |
| `security:allowed_recipient` | information: `core:InformationEntity`, agent: `core:Agent` | — |
| `security:allowed_group` | information: `core:InformationEntity`, group: `core:Group` | — |
| `security:need_to_know` | agent: `core:Agent`, information: `core:InformationEntity` | — |
| `security:consent_scope` | agent: `core:Agent`, data: `core:InformationEntity`, scope: `core:Concept` | — |

### social

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `social:knows` | agent: `core:Agent`, other: `core:Agent` | — |
| `social:trusts` | agent: `core:Agent`, other: `core:Agent`, degree: `literal:probability` | — |
| `social:likes` | agent: `core:Agent`, other: `core:Agent`, degree: `literal:number_minus1_plus1` | — |
| `social:respects` | agent: `core:Agent`, other: `core:Agent`, degree: `literal:probability` | — |
| `social:fears` | agent: `core:Agent`, other: `core:Agent`, degree: `literal:probability` | — |
| `social:depends_on` | agent: `core:Agent`, other: `core:Agent`, degree: `literal:probability` | — |
| `social:loyal_to` | agent: `core:Agent`, target: `core:Agent`, degree: `literal:probability` | — |
| `social:rival_of` | left: `core:Agent`, right: `core:Agent` | Eigenschaften: symmetric. |
| `social:allied_with` | left: `core:Agent`, right: `core:Agent` | Eigenschaften: symmetric. |
| `social:enemy_of` | left: `core:Agent`, right: `core:Agent` | Eigenschaften: symmetric. |
| `social:family_relation` | left: `core:Agent`, right: `core:Agent`, relation_type: `core:Concept` | — |
| `social:friend_of` | left: `core:Agent`, right: `core:Agent` | Eigenschaften: symmetric. |
| `social:romantic_relation` | left: `core:Agent`, right: `core:Agent`, relation_type: `core:Concept` | — |
| `social:supervises` | supervisor: `core:Agent`, subordinate: `core:Agent`, context: `core:Organization` | — |
| `social:owes_favor` | debtor: `core:Agent`, creditor: `core:Agent`, degree: `literal:probability` | — |
| `social:shares_secret_with` | agent: `core:Agent`, other: `core:Agent`, proposition: `core:Proposition` | — |
| `social:relationship_summary` | agent: `core:Agent`, other: `core:Agent`, summary: `literal:string` | — |

### space

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `space:exactly_at` | entity: `core:Thing`, place: `core:Place` | Kleinster autoritativ bekannter Aufenthaltsort. Cardinality: `{'value': 'at_most_one_per_time'}`. |
| `space:located_within` | entity: `core:Thing`, place: `core:Place` | Kann gleichzeitig für Raum, Gebäude, Bezirk und Stadt wahr sein. |
| `space:contains` | container: `core:Place`, entity: `core:Thing` | — |
| `space:part_of_place` | child: `core:Place`, parent: `core:Place` | Eigenschaften: transitive. |
| `space:spatially_disjoint` | left: `core:Place`, right: `core:Place` | Eigenschaften: symmetric. |
| `space:adjacent_to` | left: `core:Place`, right: `core:Place` | Eigenschaften: symmetric. |
| `space:connected_to` | left: `core:Place`, right: `core:Place` | Eigenschaften: symmetric. |
| `space:reachable_from` | destination: `core:Place`, origin: `core:Place`, agent: `core:Agent` | — |
| `space:distance_between` | left: `core:Thing`, right: `core:Thing`, distance: `core:QuantityValue` | — |
| `space:visible_from` | target: `core:Thing`, observer_place: `core:Place` | — |
| `space:audible_from` | source: `core:Thing`, listener_place: `core:Place` | — |
| `space:has_access_to` | agent: `core:Agent`, place: `core:Place` | — |
| `space:controls_access_to` | agent: `core:Agent`, place: `core:Place` | — |
| `space:home_at` | agent: `core:Agent`, place: `core:Place` | — |
| `space:works_at` | agent: `core:Agent`, place: `core:Place` | — |
| `space:owns_place` | owner: `core:Agent`, place: `core:Place` | — |

### time

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `time:starts_at` | entity: `core:Occurrent`, instant: `core:TimeInstant` | — |
| `time:ends_at` | entity: `core:Occurrent`, instant: `core:TimeInstant` | — |
| `time:occurs_during` | entity: `core:Occurrent`, interval: `core:TimeInterval` | — |
| `time:before` | left: `core:Occurrent`, right: `core:Occurrent` | Eigenschaften: transitive. |
| `time:after` | left: `core:Occurrent`, right: `core:Occurrent` | — |
| `time:overlaps` | left: `core:TimeInterval`, right: `core:TimeInterval` | Eigenschaften: symmetric. |
| `time:during` | inner: `core:TimeInterval`, outer: `core:TimeInterval` | — |
| `time:has_duration` | entity: `core:Occurrent`, duration: `core:QuantityValue` | — |
| `time:has_deadline` | commitment: `core:Commitment`, instant: `core:TimeInstant` | — |
| `time:scheduled_for` | entity: `core:Occurrent`, schedule: `core:Schedule` | — |
| `time:recurs_by` | entity: `core:Occurrent`, rule: `literal:rrule` | — |
| `time:active_during` | state: `core:State`, interval: `core:TimeInterval` | — |

### work

| Prädikat | Benannte Slots | Semantik / Hinweise |
|---|---|---|
| `work:has_profession` | agent: `core:Agent`, profession: `core:Profession` | — |
| `work:employed_by` | agent: `core:Agent`, organization: `core:Organization` | — |
| `work:job_title` | agent: `core:Agent`, role: `core:Role` | — |
| `work:on_shift` | agent: `core:Agent` | — |
| `work:assigned_task` | agent: `core:Agent`, goal: `core:Goal` | — |
| `work:income_level` | agent: `core:Agent`, quantity: `core:QuantityValue` | — |


---

# 23. Minimum ontology for the terminal MVP

The terminal MVP should not implement all modules at full depth. Mandatory subset:

## 23.1 Required classes

- Agent;
- Place;
- Item;
- Event;
- Action;
- Proposition;
- Observation;
- Claim;
- Belief;
- Memory;
- Goal;
- Relationship;
- Conversation;
- Commitment;
- MediaItem.

## 23.2 Required modules

- identity;
- space;
- time;
- event;
- appearance;
- work;
- education;
- psychology;
- social;
- perception;
- epistemic;
- memory;
- dialogue;
- deception;
- norm;
- environment;
- media;
- reputation;
- narrative;
- security.

## 23.3 Required end-to-end cases

1. player freely asks a question;
2. player lies about identity;
3. NPC recognizes clothing;
4. NPC interprets clothing differently because of culture;
5. noisy environment causes partial hearing;
6. NPC remembers a promise;
7. exact wording fades but emotional trace remains;
8. radio broadcasts a biased report;
9. NPC hears it and updates belief;
10. rumor shares the same provenance and is discounted;
11. a second independent witness changes confidence more strongly;
12. NPC intentionally lies;
13. validator permits the lie but marks deceptive stance;
14. secret remains protected;
15. topic becomes exhausted and conversation ends;
16. time jump updates work shift and fatigue;
17. NPC expertise affects source credibility;
18. disguise causes mistaken identity;
19. later evidence corrects the identity;
20. save/reload reproduces all state and seeded mutations.

---

# 24. Is it now finished?

## 24.1 Conceptual completeness

With this v0.3 architecture, the ontology is broad enough to serve as a serious foundation for:

- cyberpunk;
- fantasy;
- historical;
- modern;
- science-fiction;
- social simulation;
- detective;
- survival;
- role-playing and open-world games.

## 24.2 What is still not finished

A specification is not a proven product. Before calling the core “finished”, the following must exist:

1. executable JSON Schemas;
2. ontology registry loader;
3. type and constraint checker;
4. belief evidence implementation;
5. temporal and spatial reasoner;
6. parser from free text to event/speech-act frames;
7. dialogue planner state machine;
8. validator with stance-aware checks;
9. savegame persistence and migration;
10. scenario test suite;
11. two World Packs demonstrating portability;
12. measured latency, leak rate and contradiction rate.

## 24.3 Freeze criterion

Version 1.0 should be frozen only when:

- two very different worlds use the same core without schema forks;
- at least 30 end-to-end scenarios pass;
- all ontology terms have examples and tests;
- no critical information leak occurs in the adversarial suite;
- deterministic replay is stable;
- pack migration works;
- an external developer can integrate the terminal API from documentation alone.

---

# 25. Recommended next implementation sequence

1. freeze the v0.3 representation format;
2. generate JSON Schemas from the registry;
3. implement class, predicate and slot validation;
4. implement valid-time and transaction-time storage;
5. implement evidence graph and belief updates;
6. implement memory retrieval and consolidation;
7. implement free-text interpreter with alternative parses;
8. implement speech-act and stance-aware dialogue planning;
9. implement disclosure labels and taint propagation;
10. implement the terminal sandbox;
11. add 30 scenario tests;
12. only then begin Unreal integration.

---

# 26. Final assessment

The v0.2 draft was not merely a rough idea. It already contained a credible technical core. Its strongest contribution is the shift from prompt-based NPCs to typed, auditable and replayable semantics.

It was nevertheless incomplete as a universal SDK specification. The most important additions in v0.3 are:

- named semantic slots;
- context separation;
- valid and transaction time;
- open-world and paraconsistent reasoning;
- dual evidence for ignorance versus conflict;
- explicit speech stance;
- controlled lying and quotation;
- contextual roles and hierarchical locations;
- clothing, work and education as first-class modules;
- norms and commitments;
- narrative gates;
- information-flow labels;
- multiplayer identity and privacy;
- versioned ontology extensions.

The system should now be described as:

> **A versioned semantic runtime for world state, perception, belief, memory, social relations, dialogue and controlled language generation—not as a chatbot SDK.**
