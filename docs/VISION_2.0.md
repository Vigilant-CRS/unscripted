# Unscripted 2.0 — Technical Architecture and Implementation Specification

**Status:** Proposed architecture extension  
**Document type:** Normative technical concept  
**Audience:** Runtime engineers, engine-integration engineers, AI engineers, narrative designers, QA, technical producers  
**Relationship to `CONCEPT.md`:** This document extends the existing measured runtime. It does not replace the evidence, benchmarks, or limitations recorded there.

---

> ### How to read this document
>
> This is the **three-year target picture**, not a work plan. It describes where
> Unscripted should end up; it does not describe what exists today and it does
> not describe what to build next.
>
> - **What exists and has been measured** → [`CONCEPT.md`](CONCEPT.md)
> - **What is being built, in what order, with acceptance criteria** → [`ROADMAP.md`](ROADMAP.md)
> - **Where we want to be** → this document
>
> Sections here are adopted, deferred or rejected individually, and the roadmap
> records which and why. Nothing in this file should be read as a claim about the
> current runtime.

---

## 0. Executive definition

Unscripted is a deterministic epistemic and social simulation runtime in which
every character maintains a subjective, historically grounded model of the
world.

The runtime must be able to answer, for every consequential belief, communication, relationship change, and action:

- what happened in the objective world;
- what the character could perceive;
- what they attended to and recognised;
- how they interpreted it;
- which evidence changed their belief;
- which source or chain of sources produced that evidence;
- whether they believe a source was honest, mistaken, coerced, deceptive, or manipulated;
- how their role, biography, competence, identity, mood, interests, norms, and current goals coloured the interpretation;
- what they chose to communicate and what they intentionally withheld;
- what they wanted the listener to believe afterwards;
- what downstream beliefs and actions depend on this evidence;
- how those downstream states change if a source is later discredited or vindicated.

The central invariant is:

> **Player communication may change the world deeply. Unvalidated model output may not.**

A different player history should produce a different world line. The language model is not the owner of that world line. The deterministic semantic runtime is.

---

## 1. Product goals

### 1.1 Primary goals

The system shall support worlds in which:

1. Different players create different causal histories through speech and action.
2. Different NPCs know different things for explainable reasons.
3. The same event can be perceived and interpreted differently by different NPCs.
4. Knowledge remains local, role-specific, network-bound, incomplete, and often wrong.
5. NPCs can lie, omit, mislead, bluff, test, threaten, persuade, and strategically disclose.
6. NPCs can believe that another NPC is lying without knowing the underlying truth.
7. Trust is contextual rather than a single scalar.
8. Later discoveries can trigger bounded retrospective belief revision through provenance.
9. The world remains playable without any external language-model provider.
10. The semantic simulation remains deterministic and replayable over the lifetime of a shipped game.
11. Small local models and larger local or API models can be exchanged without changing world semantics.
12. Unreal, MetaHuman, Unity, Godot, and custom clients can consume the same semantic contract.
13. Designers can author roles, biographies, institutions, norms, information channels, and world facts without writing engine code.
14. The runtime can scale from a small cast to a large city through simulation levels of detail.
15. Every major system has explicit acceptance tests and reason traces.

### 1.2 Non-goals for the first production release

The first release does not need to provide:

- unrestricted autonomous language-model agents;
- unlimited recursive Theory of Mind;
- physically complete city simulation;
- fully learned personalities;
- arbitrary natural-language world mutation;
- semantic guarantees over unconstrained model output;
- identical surface text across every model and hardware configuration;
- a hosted multi-tenant service as a prerequisite for local games.

---

## 2. Normative language

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST**: required for architectural correctness.
- **SHOULD**: required unless a documented design reason justifies an exception.
- **MAY**: optional extension.

---

## 3. Core invariants

### I-01 — Objective facts and communicated claims are separate

A player or NPC assertion creates a communication event. It does not directly create an objective world fact.

### I-02 — Every consequential belief has provenance

Every belief update MUST reference one or more evidence records. Every evidence record MUST reference an origin event or an explicitly authored prior.

### I-03 — No global omniscient NPC context

A text provider MUST NOT receive the complete world state. It receives only a capability-scoped semantic plan.

### I-04 — Roles affect access, attention, interpretation, credibility, and behaviour

A role is not cosmetic metadata. It MUST be capable of changing:

- which channels an NPC can access;
- which events they attend to;
- which patterns they recognise;
- which sources they trust in a domain;
- which secrets they are permitted or required to protect;
- which actions they can perform;
- which social expectations apply;
- which consequences follow from violating those expectations.

### I-05 — Trust is directional, contextual, and dynamic

`trust(A, B)` as one scalar is insufficient. Trust MUST support domain, role, context, and inferred-intent dimensions.

### I-06 — Deception is represented explicitly

The runtime MUST distinguish:

- a false belief;
- an honest mistake;
- a deliberate lie;
- a technically true but misleading statement;
- omission;
- coerced speech;
- impersonation;
- forged evidence;
- uncertainty;
- misremembering.

### I-07 — Retrospective revision follows dependency edges

If a source is later discredited, only beliefs that depend on relevant evidence from that source are reconsidered. Unrelated beliefs MUST remain unchanged.

### I-08 — Revision does not rewrite history

Historical evidence records are immutable. New evidence changes current interpretation and confidence, not the fact that a statement was made or believed earlier.

### I-09 — Language models cannot commit unvalidated semantic state

A language model MAY propose a semantic move. Only the deterministic runtime may validate and commit it.

### I-10 — The game remains playable without a model

Every production world pack MUST provide a no-model fallback path for all critical speech acts and interactions.

### I-11 — World state is semantically deterministic

Given the same runtime version, world pack version, initial seed, and ordered semantic inputs, the same semantic world state MUST result.

### I-12 — Surface text is non-authoritative

Generated wording MUST NOT be parsed back into authoritative world state unless it is treated as an untrusted player-facing surface and validated through the same semantic input boundary.

### I-13 — Knowledge saturation is not the default

Information dissemination MUST be constrained by channels, networks, attention, relevance, secrecy, trust, capacity, time, role, location, and incentives.

### I-14 — Expensive cognition is sparse

Recursive Theory of Mind, counterfactual planning, and deep revision MUST be allocated only to socially or narratively salient relationships and claims.

### I-15 — Every committed transition emits a reason trace

The trace MUST be sufficient to reconstruct why the transition occurred without consulting a language model.

---

## 4. System architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                            WORLD PACK                              │
│ Ontology · roles · biographies · institutions · norms · places    │
│ factions · channels · routines · events · templates · localisation │
└─────────────────────────────────┬──────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────┐
│                    DETERMINISTIC SEMANTIC CORE                     │
│                                                                    │
│ Event ledger                Objective world projection             │
│ Perception                  Attention and recognition              │
│ Interpretation              Belief and evidence graph              │
│ Source models               Trust and deception models             │
│ Memory                      Consolidation and forgetting            │
│ Affect                      Relationships and social identity       │
│ Norms and institutions      Theory of Mind                          │
│ Policy                      Director and event generation           │
│ Dialogue planning           Action planning                         │
└───────────────┬───────────────────────────────┬────────────────────┘
                │                               │
┌───────────────▼────────────────┐  ┌───────────▼────────────────────┐
│ LANGUAGE PROVIDER ABSTRACTION │  │ ENGINE ACTION ABSTRACTION      │
│ Templates                    │  │ Typed intents                   │
│ Small local model            │  │ Execution requests             │
│ Large local model            │  │ Result and interruption events │
│ Remote API                   │  │ Navigation/animation adapters  │
└───────────────┬────────────────┘  └───────────┬────────────────────┘
                │                               │
┌───────────────▼───────────────────────────────▼────────────────────┐
│                         ENGINE ADAPTERS                            │
│ Unreal · MetaHuman · Unity · Godot · Web · custom simulation       │
└────────────────────────────────────────────────────────────────────┘
```

### 4.1 Architectural boundary

The semantic core owns:

- facts;
- beliefs;
- evidence;
- memory;
- relationships;
- role state;
- goals;
- norms;
- semantic actions;
- semantic speech acts;
- causal history;
- savegame compatibility.

Language providers own only:

- parsing proposals;
- surface realisation;
- optional summarisation proposals;
- optional authoring assistance;
- optional bounded candidate ranking.

Game engines own:

- rendering;
- animation;
- navigation;
- physics;
- input;
- audio playback;
- presentation timing;
- physical action execution.

---

## 5. World truth, observations, claims, and beliefs

### 5.1 Objective fact

An objective fact belongs to the authoritative world projection.

```yaml
fact:
  fact_id: fact-01928
  proposition:
    predicate: ordered_attack
    slots:
      actor: entity:kane
      target: place:warehouse_7
    polarity: positive
  valid_from_tick: 8821
  valid_to_tick: null
  caused_by_event: event-7712
```

Objective facts are not automatically visible to any NPC.

### 5.2 Communication event

```yaml
communication_event:
  event_id: event-9001
  speaker: entity:player
  listeners:
    - entity:anna
    - entity:ben
  speech_act: assert
  asserted_propositions:
    - predicate: ordered_attack
      slots:
        actor: entity:kane
        target: place:warehouse_7
      polarity: positive
  assertion_strength: 0.88
  declared_confidence: high
  channel: face_to_face
  location: place:bar_12
  tick: 90015
```

This event proves only that the player asserted the claim.

### 5.3 Observation

An observation is an agent-specific sensory record derived from an event.

```yaml
observation:
  observation_id: obs-001
  observer: entity:anna
  source_event: event-9001
  sensory_quality: 0.94
  attended_fraction: 0.83
  recognised_features:
    - speaker_identity
    - asserted_actor
    - asserted_target
  missed_features:
    - ironic_tone
```

### 5.4 Interpretation

An interpretation maps an observation into one or more subjective propositions.

```yaml
interpretation:
  interpretation_id: int-001
  observer: entity:anna
  source_observation: obs-001
  hypotheses:
    - proposition: player_asserted_kane_ordered_attack
      probability: 0.98
    - proposition: kane_ordered_attack
      probability: 0.63
    - proposition: player_is_testing_anna
      probability: 0.19
  selected_for_encoding:
    - player_asserted_kane_ordered_attack
    - kane_ordered_attack
```

### 5.5 Evidence

```yaml
evidence:
  evidence_id: evd-001
  holder: entity:anna
  proposition: kane_ordered_attack
  polarity: support
  origin_event: event-9001
  immediate_source: entity:player
  channel: face_to_face
  source_role_context: outsider_informant
  perceived_assertion_strength: 0.82
  observation_quality: 0.94
  interpretation_confidence: 0.63
  independence_cluster: origin:event-9001
  active_weight: 0.47
  created_tick: 90015
```

### 5.6 Belief state

```yaml
belief_state:
  holder: entity:anna
  proposition: kane_ordered_attack
  prior_log_odds: -0.4
  support_evidence:
    - evd-001
    - evd-088
  opposing_evidence:
    - evd-043
  posterior_probability: 0.61
  contradiction_grade: C2
  last_recomputed_tick: 90015
  epistemic_status: contested
```

---

## 6. NPC composition

An NPC is not defined by one persona prompt. It is assembled from explicit, independently versioned profiles.

```text
NPC
├── Identity Profile
├── Biography Graph
├── Active Role Stack
├── Competence Profile
├── Epistemic Profile
├── Motivational Profile
├── Social Identity Profile
├── Norm and Institution Membership
├── Relationship Graph
├── Source Models
├── Belief Graph
├── Memory Store
├── Theory-of-Mind Cache
├── Affect State
└── Routine and Current Situation
```

### 6.1 Identity profile

```yaml
identity_profile:
  character_id: entity:mara
  age_band: adult
  origin_groups:
    - district:lower_city
    - culture:dock_community
  languages:
    city_standard: fluent
    dock_slang: native
    corporate_register: basic
  education:
    formal_level: vocational
    institutions:
      - lower_city_technical_college
  social_class_history:
    childhood: working_class
    current: precarious_middle
```

Identity influences initial priors and social interpretation but MUST NOT hard-code deterministic stereotypes. Every identity-derived prior MUST be overrideable by biography and individual traits.

### 6.2 Biography graph

Biography is a graph of events, consequences, acquired competencies, and durable interpretations.

```yaml
biography_event:
  biography_event_id: bio-mara-017
  character: entity:mara
  event_type: dismissed_after_accident
  period:
    start_year: 2041
    end_year: 2041
  involved_entities:
    - faction:helix_security
  experienced_role: security_technician
  subjective_attribution:
    predicate: management_acted_unfairly
    confidence: 0.84
  effects:
    competence_delta:
      security_systems: 0.14
    source_prior_delta:
      corporate_executives:
        honesty: -0.18
    goal_added:
      - regain_professional_status
    emotional_association:
      corporate_authority:
        valence: -0.6
        arousal: 0.4
```

Biography creates initial state through normal events and evidence where practical. It SHOULD NOT bypass provenance by directly setting unexplained beliefs.

### 6.3 Competence profile

Competence is domain-specific.

```yaml
competence_profile:
  security_systems:
    theoretical: 0.78
    practical: 0.91
    current_familiarity: 0.72
  medicine:
    theoretical: 0.09
    practical: 0.03
  gang_politics:
    theoretical: 0.41
    practical: 0.67
```

Competence affects:

- feature recognition;
- event interpretation;
- ability to detect inconsistencies;
- source credibility in the eyes of others;
- memory consolidation;
- action availability;
- confidence calibration.

### 6.4 Epistemic profile

```yaml
epistemic_profile:
  curiosity: 0.63
  skepticism: 0.71
  conformity: 0.28
  authority_bias: 0.19
  confirmation_bias: 0.66
  ambiguity_tolerance: 0.42
  novelty_preference: 0.51
  gossip_tendency: 0.36
  secrecy_discipline: 0.82
  evidence_thresholds:
    act_on_claim: 0.72
    repeat_as_fact: 0.81
    investigate: 0.44
```

### 6.5 Motivational profile

```yaml
motivational_profile:
  goals:
    - goal_id: protect_family
      priority: 0.92
      horizon: long
    - goal_id: regain_professional_status
      priority: 0.64
      horizon: medium
  values:
    loyalty: 0.81
    truthfulness: 0.54
    self_preservation: 0.92
    procedural_fairness: 0.76
  aversions:
    public_humiliation: 0.71
    physical_harm: 0.88
```

### 6.6 Social identity profile

A character may hold several identities. Their salience changes by situation.

```yaml
social_identity:
  identities:
    - identity_id: former_security_worker
      baseline_salience: 0.48
    - identity_id: dock_community_member
      baseline_salience: 0.71
    - identity_id: parent
      baseline_salience: 0.86
```

Role and identity salience affect interpretation and action multiplicatively, but hard rules remain explicit gates.

---

## 7. Dynamic role system

### 7.1 Why roles must be dynamic

A character is not one role. The same person may be:

- a bartender in public;
- a former security engineer when inspecting equipment;
- a gang informant during covert contact;
- a parent when their child is threatened;
- a union member during a labour dispute;
- a witness during an investigation.

The active role stack changes which knowledge, obligations, competencies, and communication policies are salient.

### 7.2 Role definition

```yaml
role_definition:
  role_id: gang_informant
  visibility: secret
  domains:
    - gang_politics
    - illicit_trade
  access_grants:
    channels:
      - encrypted_gang_chat
    places:
      - backroom_network
    proposition_scopes:
      - gang_internal
  obligations:
    - protect_handler_identity
    - report_rival_activity
  prohibitions:
    - disclose_safehouse_location_to_outsider
  action_capabilities:
    - arrange_secret_meeting
    - sell_information
    - plant_rumour
  source_expectations:
    gang_lieutenant:
      competence: 0.74
      honesty: 0.49
  sanctions:
    disclosure_violation:
      - retaliation
      - role_loss
```

### 7.3 Role instance

```yaml
role_instance:
  role_instance_id: role-mara-informant
  character: entity:mara
  role_id: gang_informant
  valid_from_tick: 40000
  valid_to_tick: null
  status: active
  public_visibility:
    player: unknown
    entity:handler: known
    faction:gang_alpha: suspected
  competence_modifier: 0.12
  obligation_strength: 0.79
  current_risk: 0.63
```

### 7.4 Role salience

```text
role_salience(role, situation) =
    baseline_salience
  + location_match
  + audience_match
  + goal_relevance
  + threat_relevance
  + institutional_activation
  + recent_role_use
  - role_conflict_cost
```

The result is normalized over candidate roles. Multiple roles MAY remain active.

### 7.5 Role conflict

Role conflict is explicit.

Example:

- `security_employee` requires reporting sabotage.
- `sibling_of_suspect` motivates concealment.
- `union_member` discourages cooperation with corporate management.

```yaml
role_conflict:
  character: entity:mara
  situation: event:sabotage_discovered
  active_roles:
    - security_employee
    - sibling
    - union_member
  conflict_axes:
    institutional_duty_vs_family_loyalty: 0.88
    truthfulness_vs_self_preservation: 0.54
```

Conflict affects emotion, hesitation, speech strategy, and action selection.

### 7.6 Role-based knowledge is not role omniscience

A role grants:

- access opportunities;
- expected competencies;
- channel membership;
- possible priors.

It does not automatically grant all facts in a domain.

A police officer may have access to a case system but may not have opened a specific file. A corporate executive may know a project exists but not its implementation details.

---

## 8. Knowledge topology

A single social hierarchy is insufficient. Knowledge is distributed across several overlapping structures.

### 8.1 Knowledge dimensions

Every proposition type MAY declare:

```yaml
knowledge_metadata:
  domains:
    - corporate_security
    - military_technology
  geographic_scope:
    - district:central
  organisational_scope:
    - faction:helix
  access_level: restricted
  expertise_requirement: 0.68
  public_visibility: hidden
  social_relevance: high
  transmissibility: low
  emotional_charge: medium
  freshness_half_life_ticks: 30000
  prerequisites:
    - proposition: project_orpheus_exists
```

### 8.2 Knowledge classes

The runtime SHOULD support:

- public knowledge;
- local knowledge;
- occupational knowledge;
- faction knowledge;
- hierarchical knowledge;
- network knowledge;
- experiential knowledge;
- inferred knowledge;
- rumour knowledge;
- classified knowledge;
- obsolete knowledge;
- false knowledge;
- common knowledge;
- contested knowledge;
- taboo knowledge;
- procedural knowledge.

### 8.3 Access graph

```text
Character
  ├── Role instances
  ├── Institutions
  ├── Locations
  ├── Relationships
  ├── Devices and credentials
  └── Channels
          ↓
    Access opportunities
          ↓
    Observations and records
          ↓
    Subjective knowledge
```

### 8.4 Prerequisite graph

Some claims cannot be meaningfully interpreted without earlier knowledge.

```yaml
proposition_schema:
  predicate: reactor_cascade_imminent
  comprehension_requirements:
    any_of:
      - competence:
          reactor_engineering: 0.75
      - known_proposition:
          reactor_warning_code_meaning: true
```

A character who lacks the prerequisites may encode a lower-level interpretation such as `warning_light_is_flashing`.

---

## 9. Selective perception and interpretation

The existing sensory gate is extended into a five-stage pipeline.

```text
World event
   ↓
1. Sensory availability
   ↓
2. Attention allocation
   ↓
3. Feature recognition
   ↓
4. Interpretation hypotheses
   ↓
5. Memory encoding and belief evidence
```

### 9.1 Sensory availability

Inputs include:

- location;
- line of sight;
- distance;
- noise;
- occlusion;
- channel membership;
- device quality;
- impairment;
- interruption.

### 9.2 Attention allocation

```text
attention_score =
    sensory_strength
  × current_focus_capacity
  × role_relevance
  × goal_relevance
  × emotional_salience
  × novelty
  × threat_value
  × social_relevance
```

Attention is budgeted. Observing one detail can reduce the probability of observing another.

### 9.3 Feature recognition

```text
recognition_probability =
    observation_quality
  × domain_competence
  × familiarity
  × expectedness_modifier
  × stress_modifier
```

### 9.4 Interpretation hypotheses

Interpretation MUST support multiple hypotheses rather than one forced reading.

```yaml
interpretation_hypotheses:
  observer: entity:mara
  source_observation: obs-733
  candidates:
    - proposition: armed_person_is_police
      probability: 0.38
      reasons:
        - uniform_similarity
        - authority_bias
    - proposition: armed_person_is_gang_member
      probability: 0.49
      reasons:
        - district_context
        - prior_gang_activity
        - weapon_carry_style
    - proposition: armed_person_is_private_security
      probability: 0.13
```

### 9.5 Interpretive colouring

Interpretation is affected by:

- role;
- active identity;
- biography;
- competence;
- prior beliefs;
- current mood;
- current goals;
- norms;
- stereotypes;
- relationship to involved actors;
- perceived incentives of the source.

Biases MUST be represented as explainable modifiers. They SHOULD NOT silently alter objective facts.

### 9.6 Misinterpretation as first-class state

A misinterpretation is not an engine error. It is a valid subjective state with provenance.

---

## 10. Dynamic source models: who believes whom, about what, and why

### 10.1 Source models replace global trust

Each NPC maintains a contextual model of relevant sources.

```yaml
source_model:
  evaluator: entity:anna
  source: entity:ben
  global_familiarity: 0.74
  dimensions:
    honesty:
      baseline: 0.58
      confidence: 0.61
    competence:
      corporate_security: 0.82
      medicine: 0.11
      gang_politics: 0.44
    benevolence_toward_evaluator: 0.37
    coercion_susceptibility: 0.42
    exaggeration_tendency: 0.66
    secrecy_discipline: 0.72
    ideological_bias:
      anti_corporate: 0.73
  context_overrides:
    under_public_pressure:
      honesty_delta: -0.11
    speaking_about_family:
      honesty_delta: -0.28
```

### 10.2 Role-conditioned source models

Anna may trust Ben as a mechanic but distrust him as a political commentator.

```yaml
role_conditioned_credibility:
  evaluator: entity:anna
  source: entity:ben
  source_role: mechanic
  claim_domain: engine_failure
  credibility: 0.89
```

The source's claimed role and the evaluator's belief about that role may differ.

### 10.3 Source-role recognition

When a source speaks, the listener infers the currently relevant source role.

```yaml
inferred_source_role:
  evaluator: entity:anna
  source: entity:ben
  candidates:
    - role: mechanic
      probability: 0.67
    - role: union_representative
      probability: 0.22
    - role: friend
      probability: 0.11
```

Credibility is weighted over these hypotheses.

### 10.4 Claim-specific credibility

```text
source_reliability(evaluator, source, claim, context) =
    honesty_expectation
  × domain_competence
  × access_plausibility
  × benevolence_or_alignment
  × channel_integrity
  × coercion_modifier
  × incentive_modifier
  × consistency_modifier
  × role_legitimacy
```

### 10.5 Access plausibility

A credible person may still be an implausible source for a specific fact.

Example: A bartender claiming exact classified launch codes should receive low access plausibility unless their biography, role, or evidence explains access.

### 10.6 Dynamic updates to source models

Source models change through events such as:

- verified true prediction;
- verified false statement;
- discovered lie;
- honest admission of uncertainty;
- corrected mistake;
- evidence of coercion;
- proven forgery;
- repeated exaggeration;
- successful confidential behaviour;
- betrayal;
- competence demonstration;
- role change;
- ideological realignment.

### 10.7 Calibration rather than binary liar labels

An NPC SHOULD NOT become a universal liar after one false statement. Updates are scoped by:

- domain;
- context;
- motive;
- role;
- statement type;
- certainty claimed;
- whether the falsehood was intentional.

---

## 11. Deception model

### 11.1 Four-state separation

The runtime MUST distinguish:

```text
actual world state
speaker belief state
speaker communicative content
speaker intended listener belief
```

### 11.2 Communication intention

```yaml
communication_intention:
  speaker: entity:ben
  listener: entity:anna
  current_belief:
    proposition: kane_ordered_attack
    probability: 0.84
  chosen_content:
    proposition: kane_did_not_order_attack
  truth_relation: contrary_to_speaker_belief
  strategy: direct_lie
  intended_listener_state:
    proposition: kane_ordered_attack
    target_probability: 0.25
  motive:
    - protect_employer
    - avoid_retaliation
```

### 11.3 Deception taxonomy

```yaml
deception_type:
  values:
    - direct_lie
    - omission
    - selective_truth
    - misleading_implication
    - equivocation
    - exaggeration
    - understatement
    - false_uncertainty
    - false_confidence
    - bluff
    - feigned_ignorance
    - impersonation
    - forged_evidence
    - coerced_falsehood
    - rehearsed_cover_story
```

### 11.4 Honest error

```yaml
honest_error:
  speaker_belief_probability: 0.79
  objective_truth_relation: false
  deception_intent: none
```

This should reduce perceived competence when disproven, but not necessarily honesty.

### 11.5 Lying policy

A character considers lying only if it passes hard gates and utility scoring.

```text
lie_utility =
    expected_goal_gain
  - moral_cost
  - relationship_cost
  - detection_risk
  - sanction_risk
  - cognitive_cost
  - future_consistency_cost
```

### 11.6 Lie consistency obligations

A committed lie creates a cover-story obligation.

```yaml
cover_story:
  owner: entity:ben
  proposition: ben_was_at_home
  first_asserted_tick: 90000
  audience_models:
    entity:anna: told
    entity:police_1: not_told
  supporting_fabrications:
    - fake_message_timestamp
  contradiction_risk: 0.42
```

Future dialogue planning checks prior lies. The character may:

- repeat the lie;
- elaborate it;
- avoid the subject;
- confess;
- contradict themselves under stress;
- shift blame.

### 11.7 Belief that another person is lying

Listeners maintain a deception hypothesis independent of the factual claim.

```yaml
deception_belief:
  evaluator: entity:anna
  source: entity:ben
  communication_event: event-9102
  hypotheses:
    - type: honest_statement
      probability: 0.31
    - type: honest_mistake
      probability: 0.18
    - type: deliberate_lie
      probability: 0.43
    - type: coerced_statement
      probability: 0.08
```

A listener can believe:

- the statement is false but honestly made;
- the statement is true but strategically misleading;
- the speaker is lying without knowing the truth;
- the speaker believes they are truthful while being manipulated.

### 11.8 Lie detection signals

Detection may use:

- contradiction with existing evidence;
- implausible access;
- inconsistent retellings;
- motive to deceive;
- behavioural cues if the world pack enables them;
- known source history;
- external evidence;
- failed prediction;
- relationship context;
- role conflict;
- coercion indicators.

Behavioural cues MUST NOT be treated as reliable universal lie detectors. They are weak evidence with world-specific calibration.

---

## 12. Retrospective and downstream belief revision

### 12.1 Requirement

When Anna later learns that Ben fabricated evidence, the runtime should not merely lower Anna's current trust in Ben. It should identify beliefs that depend on Ben's relevant statements and recompute them.

### 12.2 Evidence dependency graph

```text
Origin event
   ↓
Observation
   ↓
Interpretation
   ↓
Evidence record
   ↓
Belief state
   ↓
Derived inference
   ↓
Action or communication
   ↓
Other agents' evidence
```

Every edge is typed and immutable.

### 12.3 Revision trigger

```yaml
revision_trigger:
  event: forged_document_exposed
  affected_source: entity:ben
  affected_domain: warehouse_attack
  affected_period:
    from_tick: 85000
    to_tick: 92000
  reliability_revision:
    honesty_delta: -0.42
    competence_delta: 0.00
  scope:
    statement_types:
      - direct_assertion
      - document_authorship
```

### 12.4 Incremental truth-maintenance algorithm

```python
queue = find_evidence_affected_by(trigger)
visited = set()

while queue:
    evidence_id = queue.pop()
    if evidence_id in visited:
        continue
    visited.add(evidence_id)

    old_weight = evidence[evidence_id].active_weight
    new_weight = recompute_evidence_weight(evidence_id)

    if materially_changed(old_weight, new_weight):
        evidence[evidence_id].active_weight = new_weight
        belief_id = evidence[evidence_id].target_belief
        old_belief = belief[belief_id]
        recompute_belief(belief_id)
        emit_revision_trace(old_belief, belief[belief_id], trigger)

        for dependent in dependency_graph.outgoing(belief_id):
            queue.push(dependent)
```

### 12.5 Bounded revision

To remain performant and narratively plausible:

- revision is scoped by claim domain and source relation;
- low-salience dormant branches may be lazily recomputed;
- old conclusions may remain psychologically sticky even after evidence weakens;
- memory retrieval determines whether an NPC consciously notices the revision;
- beliefs can become uncertain without instantly reversing;
- previous actions remain historical facts.

### 12.6 Psychological response to revision

Discovering deception may cause:

- trust loss;
- humiliation;
- anger;
- denial;
- motivated reasoning;
- reinterpretation of earlier events;
- faction realignment;
- investigation;
- retaliation;
- confession;
- increased skepticism in a domain.

These are policy outcomes, not automatic fixed consequences.

### 12.7 Vindication

The same mechanism supports later confirmation of a previously distrusted source.

---

## 13. Belief update model

### 13.1 Evidence weight

The current log-odds architecture remains useful, but `kappa` is explicitly treated as a calibrated game-model likelihood contribution rather than an automatically exact statistical likelihood ratio.

```text
kappa =
    base_evidence_strength
  × source_reliability
  × observation_quality
  × interpretation_confidence
  × channel_integrity
  × independence_discount
  × relevance_match
  × cognitive_state_modifier
```

### 13.2 Dual evidence

Support and opposition remain separate to distinguish:

- ignorance;
- settled belief;
- active contradiction;
- unstable uncertainty.

### 13.3 Dependence and correlation

Evidence records belong to an `independence_cluster`.

```yaml
evidence_independence:
  cluster_id: origin:event-1234
  lineage:
    - entity:clara
    - entity:ben
    - entity:anna
```

Repeated evidence from the same cluster is discounted. A later discovery that two apparently independent sources coordinated can merge their clusters and trigger revision.

### 13.4 Source collusion

```yaml
collusion_event:
  participants:
    - entity:ben
    - entity:clara
  affected_claims:
    - kane_ordered_attack
  result:
    merge_independence_clusters: true
```

### 13.5 Belief inertia

Beliefs MAY have persistence based on:

- identity centrality;
- emotional investment;
- public commitment;
- social-group alignment;
- number of dependent beliefs;
- cognitive flexibility.

Belief inertia slows revision but does not fabricate evidence.

---

## 14. Information ecology and anti-saturation

### 14.1 Principle

A city is not a complete graph. Information flows through overlapping networks and channels under capacity constraints.

### 14.2 Social networks

The runtime supports edges for:

- family;
- friendship;
- workplace;
- hierarchy;
- faction;
- neighbourhood;
- ideological group;
- criminal network;
- professional network;
- digital contacts;
- media audience;
- institutional reporting lines.

### 14.3 Channel model

```yaml
information_channel:
  channel_id: corp_security_intranet
  type: digital_broadcast
  membership_rule:
    role_any_of:
      - corporate_security
      - executive
  reach_model: membership
  latency_ticks: 3
  reliability: 0.93
  authentication: signed
  surveillance_risk: 0.08
  distortion_profile:
    levelling: 0.03
    sharpening: 0.01
    assimilation: 0.01
    inversion: 0.00
```

### 14.4 Attention budget

```yaml
attention_budget:
  character: entity:mara
  per_tick: 10.0
  per_day_deep_processing: 18.0
  current_load: 7.4
```

Events consume attention according to complexity and relevance.

### 14.5 Sharing decision

```text
sharing_score =
    listener_relevance
  + emotional_urgency
  + expected_goal_gain
  + social_reward
  + norm_pressure
  - secrecy_cost
  - retaliation_risk
  - uncertainty_cost
  - boredom
  - listener_overload
```

### 14.6 Information appetite

A character tracks topic interests and role duties.

```yaml
information_appetite:
  gang_politics: 0.84
  celebrity_news: 0.03
  corporate_security: 0.58
```

### 14.7 Transmission state

Daley–Kendall-style spreader/stifler state remains useful but becomes claim-and-network specific.

```yaml
rumour_state:
  holder: entity:mara
  claim: kane_ordered_attack
  network: dockworkers_union
  state: spreader
  novelty_estimate: 0.61
```

A character can be a stifler in one network but a spreader in another.

### 14.8 Saturation prevention mechanisms

Information saturation is prevented through:

1. network boundaries;
2. channel access;
3. role relevance;
4. limited attention;
5. limited memory;
6. low trust across some edges;
7. secrecy and sanctions;
8. declining novelty;
9. listener-specific usefulness;
10. distortion and loss;
11. geographic separation;
12. temporal expiry;
13. competing information;
14. active suppression;
15. disinformation;
16. institutional compartmentalisation.

### 14.9 Knowledge expiry

```yaml
knowledge_freshness:
  proposition: checkpoint_is_closed
  observed_tick: 90000
  expected_validity_ticks: 1200
  status_at_tick_92000: stale
```

Stale beliefs are not automatically false. They become less action-worthy.

### 14.10 Common knowledge

A broadcast can create common knowledge only when participants believe the audience and authenticity conditions were satisfied.

```yaml
common_knowledge_event:
  proposition: mayor_is_dead
  audience_scope: district_population
  publication_event: official_broadcast_17
  audience_visibility: public
  authentication_confidence: 0.96
```

---

## 15. Memory and consolidation

### 15.1 Memory classes

- episodic memory;
- semantic memory;
- procedural memory;
- source reputation memory;
- social scripts;
- cover-story memory;
- Theory-of-Mind memory;
- public-commitment memory.

### 15.2 Episodic memory

The existing ACT-R-style activation remains the retrieval basis.

### 15.3 Consolidation

Repeated or structurally related episodes can produce derived semantic beliefs.

```yaml
consolidation_result:
  owner: entity:anna
  derived_proposition:
    predicate: person_is_unreliable_under_pressure
    slots:
      person: entity:ben
  supporting_episodes:
    - mem-111
    - mem-234
    - mem-311
  derivation_rule: repeated_false_claims_under_pressure
  confidence: 0.73
```

### 15.4 Provenance retention

Consolidated beliefs retain pointers to representative evidence and aggregate statistics. They MUST NOT become unsourced summaries.

### 15.5 Memory compression

Low-level episodes MAY be compressed after consolidation if:

- required narrative hooks are retained;
- source provenance remains reconstructable;
- active cover stories are not lost;
- unresolved contradictions are preserved;
- legal or quest-critical records are protected.

### 15.6 Reconsolidation

Retrieving a memory under new context MAY create a revised interpretation while retaining the original episode.

```text
Original episode → current retrieval context → revised interpretation
```

---

## 16. Player communication pipeline

### 16.1 Input stages

```text
Player utterance
   ↓
Language identification
   ↓
Literal semantic candidates
   ↓
Pragmatic-act candidates
   ↓
Entity grounding
   ↓
Ambiguity assessment
   ↓
Deterministic semantic commit or clarification/abstention
```

### 16.2 Player input schema

```yaml
player_communication:
  raw_text: "Interesting that Kane left before the alarms started."
  literal_candidates:
    - predicate: kane_left_before_alarms
      confidence: 0.88
  pragmatic_candidates:
    - act: imply_suspicion
      confidence: 0.66
    - act: neutral_observation
      confidence: 0.24
    - act: test_listener
      confidence: 0.10
  grounded_entities:
    kane: entity:kane
  unresolved:
    - whether_player_claims_causation
```

### 16.3 Ambiguity policy

The parser MUST NOT silently convert low-confidence ambiguity into a strong factual assertion.

Possible policies:

- ask the player for clarification;
- commit only the unambiguous literal content;
- encode several listener-specific hypotheses;
- refuse unsupported entity grounding;
- treat the utterance as social pressure without factual commitment.

### 16.4 Listener-specific pragmatic interpretation

The parser generates common candidates. Each listener weights them according to context, relationship, role, and bias.

### 16.5 Player lies

The runtime normally does not know whether the player is lying unless the player character's belief state is modelled or objective evidence establishes contradiction.

Where the player character has a belief model:

```text
player belief vs player assertion → possible deliberate deception
```

Where it does not, the runtime records only the assertion and later evidence.

---

## 17. Semantic dialogue planning

### 17.1 Semantic commitment

The planner MUST produce exact semantic commitments, not merely a list of facts that may be mentioned.

```yaml
dialogue_plan:
  plan_id: dlg-001
  speaker: entity:anna
  listeners:
    - entity:player
  primary_speech_act: warn
  communicative_goal:
    - cause_player_to_leave
  semantic_moves:
    - move_id: move-1
      act: assert
      proposition: corporate_security_searching_for_player
      polarity: positive
      certainty_expression: probable
      disclosure_level: direct
    - move_id: move-2
      act: advise
      action: leave_location
  forbidden_semantics:
    - anna_is_informant
    - handler_identity
  permitted_entities:
    - entity:player
    - faction:corporate_security
    - place:current_location
  style:
    register: intimate
    urgency: high
    dominance: low
    warmth: medium
  maximum_sentences: 2
```

### 17.2 Three semantic autonomy modes

#### Mode A — Exact commitment

The runtime fixes every semantic move. The model realises wording only.

#### Mode B — Bounded choice

The runtime offers a closed set of valid semantic plans. A provider MAY rank them. The selected option is validated and recorded.

#### Mode C — Proposal mode

A provider proposes a typed plan. The runtime validates it as untrusted input. Rejection falls back to Mode A or B.

Production default: Mode A for critical dialogue, Mode B for low-risk variation.

### 17.3 Pragmatic metadata

```yaml
pragmatics:
  literal_content: player_was_at_warehouse
  indirect_act: accuse
  presuppositions:
    - player_had_access_to_warehouse
  intended_implicature:
    - player_may_be_responsible
  deniability: 0.61
```

### 17.4 Dialogue as world event

Only the semantic plan committed by the runtime becomes the communication event. Surface wording is attached as presentation evidence, not parsed as authoritative content.

---

## 18. Language-provider abstraction

### 18.1 Provider classes

1. `TemplateProvider`
2. `SmallLocalModelProvider`
3. `LargeLocalModelProvider`
4. `RemoteAPIProvider`
5. `RecordedSurfaceProvider` for deterministic replay

### 18.2 Capability manifest

```yaml
provider_manifest:
  provider_id: local-qwen-small
  provider_version: 3
  offline: true
  supports:
    structured_output: true
    grammar_constraints: true
    json_schema: true
    deterministic_seed: partial
    tool_calls: false
    multilingual:
      - en
      - de
  limits:
    context_tokens: 8192
    maximum_output_tokens: 256
  packaging:
    model_hash: sha256:...
    tokenizer_hash: sha256:...
    runtime_hash: sha256:...
```

### 18.3 Required provider interface

```python
class LanguageProvider(Protocol):
    def parse_player_input(
        self,
        request: ParseRequest,
        constraints: ParseConstraints,
    ) -> ParseProposal: ...

    def realize_dialogue(
        self,
        plan: DialoguePlan,
        constraints: RealizationConstraints,
    ) -> RealizationProposal: ...

    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> ProviderCapabilities: ...
```

### 18.4 Small-model design

Small local models SHOULD receive:

- minimal context;
- exact schema;
- short enumerations;
- no complete belief graph;
- no complete world lore;
- deterministic temperature and decoding configuration where available.

Tasks suited to small models:

- wording;
- intent classification over a closed catalogue;
- entity candidate extraction;
- style transfer within constraints;
- short summaries that are subsequently validated.

### 18.5 Large-model design

Larger local or API models MAY improve:

- nuanced pragmatics;
- multilingual quality;
- ambiguous input analysis;
- natural authoring;
- richer style variation;
- low-risk candidate ranking.

They MUST NOT become required for semantic correctness.

### 18.6 Provider-independent semantics

Changing providers MUST NOT change:

- available facts;
- beliefs;
- actions;
- relationship updates;
- quest state;
- world chronology;
- role membership;
- objective facts.

### 18.7 Fallback chain

```text
Requested provider healthy and compatible?
   yes → use provider
   no
Packaged local provider healthy?
   yes → use local provider
   no
Matching authored template available?
   yes → use template
   no
Safe neutral speech-act fallback
```

### 18.8 Deferred upgrade

The engine may release a template line within the frame budget and replace it with a model-generated surface only if replacement does not create presentation inconsistency. Spoken audio generally requires choosing one surface before playback.

---

## 19. Validation and semantic grounding

### 19.1 Validation stages

```text
Surface output
   ↓
Schema validation
   ↓
Entity extraction
   ↓
Proposition back-parsing
   ↓
Pragmatic-risk checks
   ↓
Secret and protected-surface checks
   ↓
Semantic entailment comparison
   ↓
Accept, repair, regenerate, or fallback
```

### 19.2 Entity grounding

Every world-referential noun phrase is assigned one of:

- known entity;
- known entity class;
- permitted generic description;
- decorative non-world content;
- ungrounded potential invention.

Ungrounded potential inventions are rejected in production-critical dialogue.

### 19.3 Semantic comparison

The validator compares `realized_semantics` to `DialoguePlan.semantic_moves`.

```yaml
validation_result:
  licensed_moves_realized:
    - move-1
    - move-2
  omitted_required_moves: []
  extra_moves: []
  ungrounded_entities: []
  protected_semantics_detected: []
  verdict: accept
```

### 19.4 Implicature and presupposition risk

Critical secrets MAY declare semantic neighbourhoods and inference rules.

```yaml
protected_semantic_region:
  secret: anna_is_informant
  prohibited_entailments:
    - anna_reports_to_handler
    - anna_has_secret_contact
  high_risk_implicatures:
    - anna_knows_internal_gang_schedule_without_public_access
```

No finite validator can guarantee all human inference. Product claims MUST state the tested protection boundary precisely.

### 19.5 Structured generation

Where a provider supports constrained decoding, the runtime SHOULD restrict generation to:

- permitted entity names;
- permitted quantities;
- selected speech-act templates;
- bounded lexical classes.

---

## 20. Determinism and lifetime support

### 20.1 Three determinism levels

#### State determinism

Identical semantic inputs produce identical world state.

#### Semantic determinism

Identical state produces identical committed semantic action and speech plans.

#### Surface determinism

Identical state produces identical rendered text and audio.

State and semantic determinism are mandatory. Surface determinism is optional unless using templates or recorded surfaces.

### 20.2 Semantic input log

The event ledger records normalized semantic player input, not only raw text.

```yaml
semantic_input_record:
  raw_text_hash: sha256:...
  parser_provider: local-qwen-small
  parser_version: 3
  committed_semantics:
    speech_act: assert
    propositions:
      - kane_left_before_alarms
  ambiguity_policy: committed_literal_only
```

### 20.3 Frozen runtime bundle

A shipped game includes:

```text
/runtime-bundle
  /semantic-core
  /world-pack
  /schemas
  /templates
  /localisation
  /provider-adapters
  /optional-local-model
  /tokenizer
  /model-runtime
  /validation-rules
  /migration-manifests
  bundle-manifest.json
```

Every component is hash-addressed.

### 20.4 Long-term no-maintenance guarantee

A game remains playable when:

- the remote API is unavailable;
- the API contract has changed;
- the vendor no longer exists;
- the user is offline;
- the original development team no longer supports the title.

This guarantee depends on the packaged template path and, optionally, packaged local model runtime.

### 20.5 Replay

For exact replay, the runtime MAY store released text, selected voice, audio identifier, and animation timing. The semantic state remains reconstructable without them.

### 20.6 Version migrations

Every persisted event declares schema versions. Migrations are deterministic pure functions.

```yaml
migration_manifest:
  from_schema: belief-evidence-v2
  to_schema: belief-evidence-v3
  migration_id: add_independence_cluster
  deterministic: true
```

---

## 21. Engine integration contract

### 21.1 Generic runtime API

```http
POST /v2/worlds/{world_id}/turn
POST /v2/worlds/{world_id}/advance
GET  /v2/worlds/{world_id}/agents/{agent_id}/presentation
GET  /v2/worlds/{world_id}/agents/{agent_id}/reason-trace
POST /v2/worlds/{world_id}/actions/{action_id}/result
POST /v2/worlds/{world_id}/save
POST /v2/worlds/{world_id}/load
```

### 21.2 Turn request

```json
{
  "request_id": "req-91",
  "tick": 90015,
  "speaker": "entity:player",
  "raw_text": "Kane ordered the attack.",
  "channel": "face_to_face",
  "location": "place:bar_12",
  "visible_context": {
    "look_target": "entity:anna",
    "distance_m": 1.8
  }
}
```

### 21.3 Turn response

```json
{
  "committed_player_event": "event-9001",
  "npc_responses": [
    {
      "speaker": "entity:anna",
      "dialogue_plan_id": "dlg-001",
      "surface_text": "Where did you hear that?",
      "speech_act": "challenge_source",
      "face_state": {
        "valence": -0.22,
        "arousal": 0.49,
        "dominance": 0.08
      },
      "gaze_target": "entity:player",
      "reason_trace_id": "trace-883"
    }
  ],
  "action_requests": []
}
```

### 21.4 Typed action request

```yaml
action_request:
  action_id: action-991
  actor: entity:anna
  type: move_to
  target: place:back_exit
  urgency: 0.72
  interruptibility: high
  semantic_reason:
    - avoid_corporate_security
```

### 21.5 Action result

```yaml
action_result:
  action_id: action-991
  status: failed
  reason: target_unreachable
  engine_tick: 90101
```

The result becomes a world event and may change beliefs, mood, and policy.

---

## 22. Unreal and MetaHuman implementation

### 22.1 Unreal modules

```text
UnscriptedRuntime
UnscriptedEditor
UnscriptedMetaHuman
UnscriptedTests
```

### 22.2 `UUnscriptedSubsystem`

Responsibilities:

- service lifecycle;
- world connection;
- batching;
- tick synchronization;
- request correlation;
- save/load;
- provider health;
- fallback handling;
- version compatibility.

### 22.3 `UUnscriptedAgentComponent`

Properties:

- `CharacterId`;
- current semantic action;
- current dialogue plan;
- affect vector;
- gaze target;
- voice profile;
- role summary;
- reason-trace handle.

Blueprint events:

- `OnDialogueReady`;
- `OnSemanticActionRequested`;
- `OnAffectChanged`;
- `OnRelationshipChanged`;
- `OnRoleChanged`;
- `OnBeliefRevisionVisible`;
- `OnProviderFallback`.

### 22.4 MetaHuman adapter

Animation channels remain separated:

```text
Speech audio      → lips, jaw, tongue
Discrete emotion → expression pose
PAD mood          → slow upper-face and posture bias
Attention         → eye gaze
Conversation act  → head movement and gesture
Action tendency   → body animation request
```

The adapter MUST define blending priorities so lip synchronisation does not erase emotion and emotion does not corrupt phoneme articulation.

### 22.5 StateTree and behaviour-tree bridge

Unscripted emits semantic intent. Unreal executes physical behaviour. Unreal
reports results.

### 22.6 Plugin acceptance target

A developer can:

1. install the plugin;
2. add `UUnscriptedAgentComponent` to a MetaHuman;
3. assign a world-pack character ID;
4. connect a local runtime or bundled service;
5. converse and receive semantic actions without custom C++.

---

## 23. Scaling and simulation levels of detail

### 23.1 Population tiers

#### Tier A — Active agents

Full perception, memory retrieval, dialogue, Theory of Mind, action policy, and presentation.

#### Tier B — Nearby agents

Full social and belief simulation, reduced presentation and planning frequency.

#### Tier C — Off-screen individual agents

Deferred composable updates, event summaries, sparse interaction sampling.

#### Tier D — Population cohorts

Aggregated statistics for low-salience populations.

### 23.2 Cohort representation

```yaml
population_cohort:
  cohort_id: district7_factory_workers
  estimated_count: 8200
  role_distribution:
    factory_worker: 0.71
    supervisor: 0.08
    unemployed: 0.12
    other: 0.09
  belief_distribution:
    mayor_is_corrupt:
      mean: 0.62
      variance: 0.08
  network_links:
    union_channel: 0.73
    public_media: 0.91
```

### 23.3 Materialisation

When a cohort member becomes important, the runtime materialises an individual with:

- a deterministic identity seed;
- cohort-consistent biography;
- plausible role memberships;
- sampled but reproducible beliefs;
- provenance summaries generated from aggregate events.

### 23.4 No outcome-changing LOD

Promotion and demotion between tiers MUST preserve semantic equivalence within declared approximation bounds.

---

## 24. Institutions and norms

### 24.1 Institution model

```yaml
institution:
  institution_id: city_police
  roles:
    - patrol_officer
    - detective
    - commander
  reporting_lines:
    patrol_officer: detective
    detective: commander
  information_channels:
    - police_dispatch
    - case_database
  norms:
    - report_use_of_force
    - protect_confidential_informants
  sanctions:
    falsify_report:
      - suspension
      - prosecution
```

### 24.2 Norm state

```yaml
norm_state:
  character: entity:anna
  norm: protect_confidential_informants
  awareness: 0.91
  internalisation: 0.64
  expected_external_sanction: 0.77
  perceived_peer_support: 0.51
```

### 24.3 Norm emergence

Later versions MAY infer local norms from repeated sanction and imitation events. Production release SHOULD begin with authored norm schemas and dynamic adherence.

---

## 25. Theory of Mind

### 25.1 Sparse allocation

A character creates Theory-of-Mind entries only for salient people and claims.

Salience sources:

- strong relationship;
- active conflict;
- authority;
- dependency;
- repeated interaction;
- current strategic relevance;
- deception risk.

### 25.2 First-order model

```yaml
tom_entry:
  modeller: entity:anna
  target: entity:ben
  target_belief_estimate:
    proposition: kane_ordered_attack
    probability: 0.78
  confidence: 0.61
  evidence:
    - ben_defended_kane
    - ben_saw_document
```

### 25.3 Second-order model

```yaml
second_order_tom:
  modeller: entity:anna
  target: entity:ben
  proposition:
    type: target_believes_modeller_knows
    embedded_claim: secret_door_location
  probability: 0.54
```

### 25.4 Bounded depth

Default maximum explicit depth: 2. Higher-order beliefs are approximated as strategic summaries.

### 25.5 ToM errors

Theory of Mind is subjective and can be wrong. It must retain provenance and confidence.

---

## 26. Counterfactual reasoning

### 26.1 Purpose

Important communication and action choices can simulate a small number of possible outcomes.

### 26.2 Bounded rollout

```yaml
counterfactual_request:
  actor: entity:anna
  candidate_action: tell_secret_to_ben
  horizon_steps: 3
  outcome_dimensions:
    - goal_gain
    - disclosure_risk
    - relationship_change
    - faction_consequence
```

### 26.3 Deterministic sampling

Candidate rollouts use purpose-scoped deterministic seeds.

### 26.4 No complete world clone

Counterfactuals operate on sparse local projections and declared consequence models.

---

## 27. Personality development

### 27.1 Slow bounded drift

Traits change only under repeated, high-salience evidence.

```text
trait_delta =
    learning_rate
  × cumulative_experience_signal
  × identity_compatibility
  × plasticity
  × decay_over_time
```

### 27.2 Core versus adaptive traits

```yaml
personality_trait:
  trait: general_trust
  core_baseline: 0.44
  adaptive_offset: -0.12
  lower_bound: 0.20
  upper_bound: 0.68
```

### 27.3 Anti-convergence

Individual bounds, learning rates, and identity constraints prevent all characters converging under shared events.

---

## 28. Learned appraisal

Initial appraisal parameters are authored. Later versions MAY update them from repeated reactions and choices.

Learning MUST remain:

- bounded;
- reversible;
- explainable;
- versioned;
- independent of language-model hidden state.

---

## 29. Cross-media provenance

### 29.1 Evidence media

- speech;
- document;
- image;
- video;
- audio recording;
- sensor reading;
- database record;
- physical object;
- anonymous message;
- forged artifact.

### 29.2 Artifact provenance

```yaml
evidence_artifact:
  artifact_id: doc-991
  type: document
  declared_author: entity:ben
  actual_author: entity:clara
  creation_tick: 88001
  modifications:
    - modifier: entity:ben
      tick: 88110
      operation: altered_timestamp
  authenticity_state:
    objective: forged
    entity:anna: believed_authentic
    entity:investigator: suspected_forgery
```

### 29.3 Authentication expertise

Different NPCs may reach different authenticity judgments based on competence and tools.

---

## 30. Event generation and living-world continuity

### 30.1 Event sources

- authored schedules;
- routines;
- resource pressure;
- relationship conflict;
- role obligation;
- faction progress;
- institutional procedure;
- unresolved contradiction;
- lie maintenance;
- norm violation;
- environmental state;
- player consequences;
- bounded stochastic incidents.

### 30.2 Causal event templates

```yaml
event_template:
  template_id: informant_misses_report
  preconditions:
    - role_active: gang_informant
    - obligation_due: report_rival_activity
    - threat_level_above: 0.6
  outcomes:
    - handler_suspicion_increases
    - possible_role_review
  selection_weight:
    base: 0.2
    modifiers:
      recent_player_threat: 0.5
```

### 30.3 Director constraints

The director MAY choose among causally valid events. It MUST NOT introduce facts that violate world constraints simply to improve drama.

---

## 31. Player model and narrative direction

### 31.1 Player epistemic model

The system tracks what information was exposed to the player, not what the real human certainly understood.

```yaml
player_exposure_model:
  proposition: kane_ordered_attack
  exposures:
    - source: entity:anna
      tick: 90015
      certainty_expression: probable
  estimated_comprehension: 0.72
  confidence: 0.44
```

### 31.2 Director use

The director may prefer valid events that:

- surface unresolved consequences;
- reintroduce neglected relationships;
- expose meaningful contradictions;
- avoid redundant information;
- preserve causal integrity;
- maintain tension.

### 31.3 No mind-reading claim

The player model is an estimate based on exposure and behaviour, never a claim about actual human cognition.

---

## 32. Authoring model

### 32.1 World-pack assets

```text
worldpack/
  ontology/
  entities/
  roles/
  biographies/
  institutions/
  norms/
  factions/
  places/
  channels/
  routines/
  event_templates/
  dialogue_templates/
  localisation/
  tests/
  migrations/
```

### 32.2 Natural-language authoring assistant

A designer may write:

> Mara used to maintain corporate security systems. She distrusts executives after being blamed for an accident, but she still respects technically competent officers.

The assistant proposes structured assets. The designer reviews a diff before commit.

### 32.3 Authoring consequence report

The editor should answer:

- Who can initially know this fact?
- Which roles can access it?
- Which channels can spread it?
- Which characters can understand it?
- Which secrets conflict with it?
- Can this role ever meet that role?
- Does any authored fact lack provenance?
- Does any required speech act lack fallback text?

---

## 33. Observability and reason traces

### 33.1 Standard trace

```yaml
reason_trace:
  trace_id: trace-883
  transition: belief_update
  character: entity:anna
  proposition: kane_ordered_attack
  before: 0.31
  after: 0.61
  evidence_added:
    - evd-001
  modifiers:
    player_honesty_expectation: 0.72
    player_access_plausibility: 0.58
    observation_quality: 0.94
    confirmation_bias: 1.07
    independence_discount: 1.00
  contradiction_grade: C2
```

### 33.2 Revision trace

```yaml
revision_trace:
  trigger: ben_forgery_discovered
  affected_belief: kane_ordered_attack
  before: 0.74
  after: 0.46
  evidence_reweighted:
    evd-ben-document:
      before: 0.61
      after: 0.08
  downstream_effects:
    - suspicion_of_kane_reduced
    - trust_in_ben_reduced
    - investigate_clara_action_enabled
```

### 33.3 Designer debugger views

- belief graph;
- source graph;
- independence clusters;
- role stack;
- access graph;
- information diffusion map;
- lie and cover-story ledger;
- Theory-of-Mind matrix;
- memory consolidation view;
- revision cascade preview;
- deterministic replay comparison.

---

## 34. Testing strategy

### 34.1 Unit tests

Each pure transition function receives deterministic fixtures.

### 34.2 Golden scenarios

Golden scenarios compare semantic state, not model wording.

### 34.3 Provider conformance tests

Every provider must pass:

- schema compliance;
- no unlicensed entities;
- required move coverage;
- protected semantic tests;
- latency and fallback tests;
- multilingual grounding tests where claimed.

### 34.4 Engine contract tests

Recorded engine requests and responses assert field compatibility.

### 34.5 Property tests

Required properties include:

- no unsourced consequential beliefs;
- no probability outside `[0,1]`;
- no revision outside declared dependency scope;
- same seed and semantic input produce identical semantic state;
- role access does not imply unobserved knowledge;
- repeated same-origin evidence saturates below proof threshold;
- source discrediting lowers only relevant evidence;
- honest error affects competence more than honesty under default calibration;
- deliberate lie affects honesty more than competence under default calibration;
- removing a role revokes future access but does not erase past knowledge;
- forgetting an episode does not delete objective history;
- common knowledge requires audience visibility assumptions;
- language-provider failure never blocks critical progression.

### 34.6 Adversarial scenarios

1. Player repeats one claim 1,000 times.
2. Ten NPCs repeat one originating lie through different routes.
3. Two sources appear independent and are later exposed as coordinated.
4. Trusted expert speaks outside their competence.
5. Known liar presents verifiable evidence.
6. NPC tells a technically true but misleading statement.
7. NPC changes role and loses information access.
8. NPC is coerced into a false confession.
9. Forged document is authenticated by a novice and rejected by an expert.
10. A source is vindicated years later.
11. Remote model disappears permanently.
12. Savegame loads after schema migration.
13. Thousands of NPCs remain informationally compartmentalised.
14. A public broadcast creates common knowledge; a private leak does not.
15. A player uses ambiguous sarcasm in a high-stakes accusation.

---

## 35. Acceptance scenarios

### A-01 — Role-coloured perception

A technician, civilian, and gang member observe the same damaged control panel.

Expected:

- all may observe physical damage;
- only technician recognises deliberate bypass with high confidence;
- gang member may infer sabotage from contextual priors;
- civilian stores an uncertain generic malfunction;
- all interpretations retain the same origin event.

### A-02 — Contextual trust

Anna trusts Ben about engines but not politics.

Expected:

- engine claim receives high source reliability;
- political claim receives lower reliability;
- no global trust scalar can explain both outcomes alone.

### A-03 — Discovered lie and retrospective revision

Ben supplies a forged document. Anna acts on it. The forgery is later exposed.

Expected:

- the document remains historically received;
- its evidence weight falls;
- dependent beliefs are recomputed;
- unrelated beliefs from Ben remain stable unless scope justifies revision;
- Anna may feel anger or humiliation;
- the historical action remains committed;
- new actions may become available.

### A-04 — Honest mistake

A competent but tired medic gives a wrong estimate and later corrects it.

Expected:

- honesty need not fall materially;
- situational competence estimate may fall;
- correction may recover trust;
- prior listeners do not all receive the correction automatically.

### A-05 — Strategic omission

An informant gives true information while omitting handler identity.

Expected:

- no direct false proposition is asserted;
- the listener may infer concealment;
- secrecy obligation is maintained;
- validator prevents accidental handler disclosure.

### A-06 — Knowledge compartmentalisation

A cyberpunk city contains 10,000 agents across institutions and districts.

Expected:

- classified project knowledge remains concentrated in plausible access networks;
- public rumours spread wider but lose detail;
- unrelated agents do not converge to identical knowledge;
- no global saturation occurs absent a public broadcast or systemic leak.

### A-07 — Provider independence

The same semantic scenario is run with templates, a small local model, and a remote model.

Expected:

- wording differs;
- semantic plans, actions, beliefs, and save-state hashes are identical.

### A-08 — Unsupported legacy game

All network access is disabled years after release.

Expected:

- game starts;
- dialogue remains functional through packaged fallback;
- critical progression is possible;
- old saves load through bundled migrations;
- no vendor account is required.

---

## 36. Performance budgets

Initial targets must be measured on representative hardware.

### 36.1 Semantic core

Suggested provisional targets:

- active-agent non-language turn: p95 under 5 ms off the game thread;
- 100 nearby agents update: p95 under 15 ms per simulation batch;
- lazy retrospective revision: bounded work per frame with background continuation;
- engine presentation polling: batched;
- no blocking model call on game thread.

These are design targets, not measured claims.

### 36.2 Revision budget

Large revision cascades are processed through:

- priority queue by narrative salience;
- transaction checkpoints;
- lazy dormant-branch recomputation;
- deterministic work slicing;
- visible-state consistency barriers.

---

## 37. Security, privacy, and content ownership

### 37.1 Local-first operation

No world data needs to leave the machine in the default configuration.

### 37.2 Remote provider capability scope

Remote requests receive only the minimum semantic plan and style context required for realisation.

### 37.3 Studio content separation

World ontology and content remain in world packs. The engine ships no embedded studio lore.

### 37.4 Audit logs

Production builds MAY reduce raw model logging for privacy, while retaining semantic decision traces and hashes.

---

## 38. Migration from current runtime

### 38.1 Preserve existing components

The following concepts remain foundational:

- typed propositions;
- perception gate;
- log-odds belief update;
- dual evidence;
- provenance and origin-event correlation discounting;
- ACT-R-style memory activation;
- OCC/PAD/Frijda affect chain;
- asymmetric relationships;
- routines;
- rumour diffusion;
- distortion;
- deterministic purpose-scoped random draws;
- event-sourced persistence;
- dialogue plan and buffered validation;
- local model fallback.

### 38.2 New modules

Suggested modules:

```text
unscripted/attention.py
unscripted/interpretation.py
unscripted/roles.py                 # extend existing role/identity support
unscripted/biography.py
unscripted/competence.py
unscripted/source_model.py
unscripted/deception.py
unscripted/revision.py
unscripted/dependency_graph.py
unscripted/consolidation.py
unscripted/institutions.py
unscripted/norms.py
unscripted/theory_of_mind.py
unscripted/counterfactual.py
unscripted/common_knowledge.py
unscripted/channels.py
unscripted/provider_capabilities.py
unscripted/semantic_validator.py
unscripted/migrations.py
```

### 38.3 Schema upgrade order

1. Add evidence dependency identifiers.
2. Add contextual source models.
3. Add role instances and access opportunities.
4. Split perception into observation and interpretation.
5. Add semantic dialogue commitments.
6. Add deception intentions and cover stories.
7. Add retrospective revision.
8. Add memory consolidation.
9. Add sparse Theory of Mind.
10. Add institutions, norms, and common knowledge.

---

## 39. Implementation roadmap

### Phase 0 — Semantic integrity foundation

Deliver:

- objective fact versus communicated claim separation;
- exact semantic dialogue commitments;
- semantic back-parser;
- entity grounding;
- provider-independent committed plans;
- three determinism levels;
- versioned event schemas.

Exit criteria:

- no unvalidated model output can commit a consequential proposition or action;
- templates and model providers produce identical semantic state.

### Phase 1 — Dynamic roles and source models

Deliver:

- role definitions and instances;
- role salience and conflict;
- competence profiles;
- contextual trust/source models;
- access plausibility;
- source-role inference;
- role-conditioned credibility.

Exit criteria:

- one source can be trusted in one domain and distrusted in another;
- role access creates opportunities rather than automatic knowledge;
- active-role changes alter attention, interpretation, and policy.

### Phase 2 — Deception and retrospective revision

Deliver:

- deception taxonomy;
- communication intention;
- listener deception hypotheses;
- cover-story ledger;
- evidence dependency graph;
- incremental truth maintenance;
- source vindication and discrediting.

Exit criteria:

- a discovered lie revises relevant downstream beliefs and relationships without rewriting history;
- honest mistakes and deliberate lies have different effects.

### Phase 3 — Information ecology and anti-saturation

Deliver:

- multi-network social graph;
- channel model;
- attention budget;
- information appetite;
- claim/network-specific rumour states;
- freshness and staleness;
- common knowledge;
- institutional compartmentalisation.

Exit criteria:

- large populations retain heterogeneous role-specific knowledge over long runs;
- public broadcasts and private rumours produce measurably different distributions.

### Phase 4 — Memory consolidation and long-term character change

Deliver:

- episodic-to-semantic consolidation;
- source reputation learning;
- reconsolidation;
- bounded personality drift;
- public commitment and identity-central beliefs.

Exit criteria:

- long-running agents preserve meaningful patterns without retaining every episode;
- personality changes are slow, bounded, and traceable.

### Phase 5 — Provider abstraction and lifetime support

Deliver:

- provider manifests;
- template provider;
- small local provider;
- large local/API provider;
- fallback chain;
- frozen runtime bundle;
- exact replay surfaces;
- migration packaging.

Exit criteria:

- all external services can be disabled permanently without breaking game completion.

### Phase 6 — Unreal and MetaHuman production integration

Deliver:

- compiled Unreal plugin;
- runtime subsystem;
- agent component;
- action bridge;
- StateTree/behaviour-tree adapters;
- MetaHuman face, gaze, voice, and posture adapter;
- shipping-build test project;
- automated engine-version matrix.

Exit criteria:

- plugin installation to working MetaHuman conversation requires no custom C++.

### Phase 7 — Advanced social intelligence

Deliver:

- sparse second-order Theory of Mind;
- counterfactual communication planning;
- social norms and institutions;
- strategic misleading communication;
- cross-media evidence and forgery;
- learned appraisal prototype.

Exit criteria:

- NPCs can strategically deceive, suspect deception, enforce norms, and reason about others' beliefs in bounded scenarios.

### Phase 8 — Large worlds and narrative direction

Deliver:

- cohort simulation;
- deterministic materialisation;
- idle event generation;
- player exposure model;
- causally constrained narrative director;
- multi-world supervisor if commercially required.

Exit criteria:

- a large world remains active, heterogeneous, and causally coherent over long sessions.

---

## 40. Recommended first vertical slice

### Scenario: The missing evidence package

Cast:

- 10 high-fidelity NPCs;
- 30 nearby simulated agents;
- one corporate institution;
- one gang;
- one police unit;
- one media channel;
- one union network.

Required roles:

- eyewitness;
- honest but unreliable witness;
- technically competent investigator;
- strategic liar;
- coerced source;
- journalist;
- executive;
- gang informant;
- ordinary worker;
- player-facing ally.

Required mechanics:

- one objective event;
- four different perceptions;
- one forged document;
- one coordinated false narrative;
- one role conflict;
- one private leak;
- one public broadcast;
- one discovered lie;
- one retrospective belief cascade;
- one NPC who resists revision because of identity investment;
- one exact semantic fallback path without a model.

Demonstration output:

```text
Why does Anna believe Kane ordered the attack?

1. The player asserted it in the bar.
2. Anna trusted the player moderately but considered access uncertain.
3. Ben supplied a document that appeared authentic.
4. Ben and Clara were initially treated as independent sources.
5. The document was later exposed as forged.
6. Ben and Clara were shown to have coordinated.
7. Their evidence clusters were merged and reweighted.
8. Anna's confidence fell from 0.81 to 0.47.
9. Anna now believes Ben probably lied, but remains uncertain about Kane.
10. Her trust in Ben fell only for political and corporate claims, not mechanical expertise.
```

This vertical slice demonstrates the unique product category more clearly than a generic talking-NPC town.

---

## 41. Commercial product boundary

Unscripted should be sold as:

> **A deterministic epistemic and social simulation layer for games and interactive training.**

Not as:

- a chatbot SDK;
- a voice provider;
- a universal autonomous agent;
- a replacement for all behaviour trees;
- a general-purpose city simulator.

It composes with:

- hosted dialogue platforms;
- local language models;
- TTS systems;
- MetaHuman;
- conventional behaviour trees;
- StateTree;
- authored quest systems;
- simulation and training platforms.

---

## 42. Final architecture statement

A Unscripted character does not simply have a personality and a prompt.

They have:

- a role-dependent position in an information topology;
- a biography that shapes expectations and values;
- domain-specific competence;
- selective attention;
- subjective interpretations;
- beliefs backed by evidence;
- contextual models of who is credible;
- hypotheses about who is lying and why;
- strategic communication goals;
- obligations to roles, institutions, and relationships;
- memories that decay, consolidate, and can be reinterpreted;
- bounded models of what other people believe;
- a causal record that supports retrospective revision;
- a semantic decision process independent of any text model.

The player's communication is therefore not decorative dialogue. It is a source of events, evidence, relationships, suspicion, misinformation, coordination, and institutional change.

Different players create different worlds because they create different semantic histories. Those worlds remain testable, explainable, replayable, and playable even when no external model provider remains available.

---

## Appendix A — Minimal core data types

```python
@dataclass(frozen=True)
class Proposition:
    predicate: str
    slots: Mapping[str, EntityRef | Literal]
    polarity: Polarity
    qualifier: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    holder: EntityRef
    proposition: Proposition
    support_direction: SupportDirection
    origin_event_id: str
    immediate_source: EntityRef | None
    observation_id: str | None
    interpretation_id: str | None
    independence_cluster_id: str
    source_context: SourceContext
    base_strength: float
    active_weight: float
    created_tick: int


@dataclass
class SourceModel:
    evaluator: EntityRef
    source: EntityRef
    honesty: DistributionEstimate
    competence_by_domain: Mapping[str, DistributionEstimate]
    benevolence: DistributionEstimate
    coercion_susceptibility: DistributionEstimate
    exaggeration_tendency: DistributionEstimate
    context_overrides: Mapping[str, SourceContextOverride]


@dataclass(frozen=True)
class RoleInstance:
    role_instance_id: str
    character: EntityRef
    role_id: str
    valid_from_tick: int
    valid_to_tick: int | None
    visibility_by_observer: Mapping[EntityRef, EpistemicVisibility]
    current_risk: float


@dataclass(frozen=True)
class CommunicationIntention:
    speaker: EntityRef
    listeners: tuple[EntityRef, ...]
    actual_belief: BeliefReference
    selected_semantic_moves: tuple[SemanticMove, ...]
    intended_listener_updates: tuple[IntendedBeliefChange, ...]
    deception_type: DeceptionType | None
    motives: tuple[str, ...]


@dataclass(frozen=True)
class DialoguePlan:
    plan_id: str
    speaker: EntityRef
    listeners: tuple[EntityRef, ...]
    speech_act: str
    communicative_goals: tuple[str, ...]
    semantic_moves: tuple[SemanticMove, ...]
    forbidden_semantics: tuple[PropositionPattern, ...]
    permitted_entities: tuple[EntityRef, ...]
    style: StyleVector
    maximum_sentences: int


@dataclass(frozen=True)
class RevisionTrigger:
    trigger_event_id: str
    source_scope: EntityRef | None
    domain_scope: tuple[str, ...]
    event_type_scope: tuple[str, ...]
    time_scope: TickRange | None
    reliability_delta: ReliabilityDelta
```

---

## Appendix B — Deterministic seed derivation

```python
def deterministic_seed(
    *,
    world_seed: bytes,
    entity_id: str,
    purpose: str,
    tick: int,
    semantic_input_hash: str = "",
) -> int:
    payload = "|".join(
        [entity_id, purpose, str(tick), semantic_input_hash]
    ).encode("utf-8")
    digest = blake2b(payload, key=world_seed, digest_size=16).digest()
    return int.from_bytes(digest, "big")
```

Randomness MUST be purpose-scoped. Adding a new random draw in one subsystem must not perturb unrelated subsystems.

---

## Appendix C — Source reliability calculation sketch

```python
def compute_source_reliability(
    evaluator: AgentState,
    source: EntityRef,
    claim: Proposition,
    context: CommunicationContext,
) -> ReliabilityTrace:
    model = evaluator.source_models.get_or_prior(source)
    domain = ontology.domain_of(claim)

    honesty = model.honesty.for_context(context)
    competence = model.competence_by_domain.get(domain, PRIOR_COMPETENCE)
    access = access_plausibility(evaluator, source, claim, context)
    incentive = incentive_to_deceive(evaluator, source, claim, context)
    coercion = perceived_coercion(evaluator, source, context)
    consistency = statement_consistency(evaluator, source, claim)
    role = inferred_role_legitimacy(evaluator, source, claim, context)

    score = combine_calibrated(
        honesty=honesty.mean,
        competence=competence.mean,
        access=access,
        incentive_penalty=incentive,
        coercion_modifier=coercion,
        consistency=consistency,
        role_legitimacy=role,
    )

    return ReliabilityTrace(score=score, factors={...})
```

---

## Appendix D — Revision transaction semantics

A revision cascade runs as a deterministic transaction:

1. Freeze the input trigger.
2. Resolve the affected evidence set.
3. Sort work items by stable key.
4. Recompute evidence weights.
5. Recompute beliefs.
6. Recompute derived inferences.
7. Queue resulting affect, relationship, and policy events.
8. Commit a revision watermark.
9. Emit reason traces.
10. Release visible consequences only after the consistency barrier.

If work is sliced across frames, intermediate partial state is not exposed to gameplay consumers.

---

## Appendix E — Definition of done for Unscripted 2.0 core

The core is not complete until all of the following are demonstrated in a reproducible scenario:

- two characters observe the same event and form different justified interpretations;
- a character trusts one source in one domain and distrusts them in another;
- a character deliberately lies for a role-based goal;
- the listener suspects the lie for explainable reasons;
- the lie spreads through a limited network without saturating the population;
- later evidence exposes the lie;
- dependent beliefs are revised and unrelated beliefs remain stable;
- relationships and policies change from the revision;
- the exact historical sequence remains replayable;
- templates, a small local model, and a remote model produce the same semantic outcome;
- all remote services can be removed and the scenario remains fully playable;
- the Unreal/MetaHuman client renders the same semantic scenario without owning the world logic.
