# Unscripted
## Ontology v0.4 — Completion Pass

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Status:** implementation-ready extension, not frozen standard **Date:** 22
June 2026 **Relation:** audits and extends `Unscripted_Ontology_v0_3.md` (which
itself extends Technical Core v0.2). **Additive only** — no v0.3 term is
removed; v0.4 corrects type/namespace issues, reconciles two redundancies, and
adds the modules the v0.3 architecture promised but did not deliver.
**Regenerates:** `unscripted_core_ontology_v0.4.json` (the machine-readable
registry must be rebuilt from the corrected catalog).

---

# 0. Verdict — is v0.3 finished?

No, and the right target is not "finished as a closed list." v0.3 itself argues correctly (§0, §2.2, §21) that completeness comes from the **extension contract**, not from enumerating every concept. "Complete for all cases" is provably open-ended for an SDK meant to serve cyberpunk, fantasy, historical, sci-fi and social-sim worlds at once. The achievable and correct objective is:

> **A maximally complete stable core, plus a clean extension surface, such that what any single game must add is small and local.**

v0.4 closes the distance to that target by fixing three classes of problem found in v0.3:

- **(A) Internal inconsistencies** — modules promised by the architecture but absent from the catalog; module name ≠ namespace.
- **(B) Type-system flaws** — `literal:probability` abused as a generic `[0,1]` degree; `core:Concept` used as an untyped catch-all (the "stringly-typed" smell at the ontology level).
- **(C) Coverage gaps** — units/currency, agent kinds beyond person/collective, item properties, capability/affordance, appraisal-derived emotion, action preconditions/effects, day-phase/calendar/age time, non-audiovisual perception, communication channels, plans, theory-of-mind for deception, and formal provenance.

---

# 1. Structural corrections (apply before adding anything)

## 1.1 Namespace = module (fix the three violations)

v0.3 §1.10 and §20 mandate one namespace per module, but the catalog breaks this. Corrections:

| v0.3 module | v0.3 predicate prefix | v0.4 decision |
|---|---|---|
| `causality` | `event:` | **Rename to `causality:`** (e.g. `causality:causes`). Causal predicates are not event-structural roles. |
| `discourse` | `dialogue:` | **Merge into `dialogue`** in the inventory (one namespace), or split conversation-level predicates into `discourse:`. Recommended: keep one `dialogue` namespace; drop the separate "discourse" inventory row. |
| `identity` | `core:` | **Keep `core:`** for the truly universal identity predicates (`instance_of`, `has_name`, `has_role`…) but list them under the `core` namespace in the inventory, not under a phantom `identity` module. |

Rule going forward: the inventory's "module" column and the predicate's namespace prefix must be identical. The conformance suite (§20.3) must add a test that enforces this.

## 1.2 Type-system overhaul (the most important fix)

### 1.2.1 Stop overloading `literal:probability`

A probability and an intensity are different types. Introduce:

| Type | Meaning | Range | Replaces (examples) |
|---|---|---|---|
| `literal:probability` | subjective probability of a proposition holding | [0,1] | keep only for `epistemic:confidence`, `expected_probability`, `perception:recognized_identity.confidence`, `success_probability` |
| `literal:unit_interval` | normalized intensity / degree / rating | [0,1] | `pain_level`, `fatigue_level`, `danger_level`, `skill_level`, `domain_competence`, `crowd_density`, `surveillance_level`, `importance`, `attention`, `volume`, all "degree" slots that are not probabilities |
| `literal:signed_unit` | bipolar score | [-1,1] | `social:likes`, `psych:dominance_state`, `reputation:*.degree` |
| `literal:count` | non-negative integer | ℤ≥0 | turn counts, stock counts |
| `literal:number` | unconstrained real | ℝ | `memory:activation` (ACT-R activation is unbounded) |

This is not cosmetic: contradiction detection on functional/quantitative slots and the retrieval/utility formulas (Technical Core v0.2 §5) depend on knowing whether a number is a probability (combine in log-odds) or an intensity (combine/clamp linearly).

### 1.2.2 Replace `core:Concept` catch-all with controlled vocabularies

`core:Concept` is the new opaque string. Introduce **ConceptScheme** (a controlled vocabulary) as a first-class registry object, and retype every `core:Concept` slot to a specific scheme. A scheme is a small, versioned, pack-extensible enumeration with stable IDs.

Mandatory core schemes (each `vocab:<Scheme>`):

`Color, GarmentStyle, Condition, Status, LegalStatus, SocialStatus, Stance, Tone, Manner, Framing, EditorialBias, EmotionType, MoodType, NeedType, ValueType, TraitType, RelationType (family/romantic), TopicState, ClosureReason, DialogueActType, RetrievalStatus, MemoryType, WeatherState, Register, SymbolMeaning, ChannelType, Modality, DamageType, WoundType, DiseaseType, RankType, SpoilerLevel, ContradictionStatus.`

Slots typed `core:Concept` in v0.3 are repointed to the matching scheme (e.g. `dialogue:has_stance.stance : vocab:Stance`, `appearance:garment_color.color : vocab:Color`). Schemes are pack-extensible (a World Pack may add `Color:neon_chrome`) but the scheme *identity* is frozen in core. This preserves computability (closed per version) while allowing growth (Layer D additions).

### 1.2.3 Reconcile the Belief object vs. the `epistemic:believes` predicate

v0.3 has both a reified **Belief record** (§8.2, with `expected_probability`, `support_for/against`, `provenance`) and an **`epistemic:believes(agent, proposition)`** predicate (§22). These overlap. Resolution:

- The **Belief record is authoritative** — it carries evidence, dual support, provenance, valid/transaction time.
- `epistemic:believes/knows/suspects/doubts/denies` are **derived, queryable views** over the record, defined by thresholds on the opinion tuple, e.g.
  - `knows` ⇔ `expected_probability ≥ θ_know ∧ conflict ≤ θ_lowconf ∧ provenance grounded in observation/authority`;
  - `believes` ⇔ `expected_probability ≥ θ_believe`;
  - `suspects` ⇔ `θ_suspect ≤ expected_probability < θ_believe`;
  - `doubts` ⇔ `expected_probability ≤ 1 − θ_suspect`;
  - `denies` ⇔ a speech-act/stance, **not** an epistemic state (move `denies` out of `epistemic` into `dialogue`).
- These views are never *stored*; they are computed from the record so they can never drift out of sync.

### 1.2.4 Define the Quantity/Unit ontology behind `QuantityValue`

`QuantityValue` (number + unit) is referenced throughout v0.3 (`owes_amount`, `price_of`, `income_level`, `distance`, `duration`) but never defined. See the new **`units`** module (§3.1) for `Unit`, `Currency`, `MeasurementSystem`, conversion and comparison predicates. Without this, two prices in different currencies cannot be compared and `can_afford` is undefinable across packs.

---

# 2. Missing upper-ontology branches

## 2.1 Agent kinds beyond person/collective

v0.3 §4 has `Agent → PersonAgent | CollectiveAgent` only. Extend:

```text
Agent
├── PersonAgent (PlayerAgent | NPCAgent)
├── CollectiveAgent (Group | Institution | Organization)
├── CreatureAgent          ; non-person sentient/animal actors
│   ├── AnimalAgent
│   └── MonsterAgent        ; fantasy/sci-fi hostiles with goals
└── ArtificialAgent         ; AIs, drones, robots, automated systems
    ├── AutonomousSystem    ; drone, turret, vehicle AI
    └── SoftwareAgent       ; netrunner ICE, assistant, bot
```

Rationale: cyberpunk has AIs and drones as perceivers/actors (surveillance!); fantasy has creatures with goals. They need belief/perception/goal slots without being persons (e.g. no `culture:`, but yes `perception:`, `psych:has_goal`). Pack-level subclasses (specific monsters) live in Layer D.

## 2.2 Physical-object properties and missing object classes

v0.3 `Item → {Garment, Weapon, Tool}` has no generic attributes and omits common classes. Extend the hierarchy:

```text
PhysicalObject
├── Body, BodyPart
├── Item
│   ├── Garment, Weapon, Tool
│   ├── Vehicle              ; NEW
│   ├── Consumable           ; NEW (food, drug, medicine, ammo)
│   ├── Container            ; NEW (bag, case, safe — holds Items)
│   ├── Document             ; promoted from InformationEntity carrier
│   └── CurrencyToken        ; NEW (physical money / chips)
└── Substance                ; NEW (liquid, gas, material — non-discrete)
```

Generic item attributes are added in the new **`object`** module (§3.2): mass, volume, monetary value, legality, condition, quality, stackability, owner-mark, container-capacity.

## 2.3 Capability / affordance as first-class

The action planner (Technical Core v0.2 §5.3, `U(a)`) needs to know *what an agent can do and how well*. v0.3 scatters this across `body:mobility`, `education:skill`, `appearance:protects_against` with no unifying queryable layer. Add the **`capability`** module (§3.3) linking agent + action-type + required skill/tool/role + success probability + cost.

---

# 3. New and extended module catalogs

Same format as v0.3 §22: **Predicate | Named slots | Semantics / notes**. Column headers standardized to English. All types use §1.2 corrections. Cardinality/temporal scope follow v0.3 §1.4 (scoped by predicate + key + context + valid-time).

## 3.1 `units` (NEW)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `units:has_unit` | quantity: `core:QuantityValue`, unit: `core:Unit` | binds a numeric magnitude to a unit |
| `units:magnitude` | quantity: `core:QuantityValue`, value: `literal:number` | the scalar part |
| `units:unit_of_system` | unit: `core:Unit`, system: `core:MeasurementSystem` | e.g. metric, imperial, in-world |
| `units:is_currency` | unit: `core:Unit`, currency: `core:Currency` | marks a monetary unit |
| `units:exchange_rate` | from: `core:Currency`, to: `core:Currency`, rate: `literal:number`, valid_time | time-scoped FX; enables cross-pack price comparison |
| `units:convertible_to` | from: `core:Unit`, to: `core:Unit`, factor: `literal:number` | dimensional conversion |
| `units:quantity_gt` | left: `core:QuantityValue`, right: `core:QuantityValue` | comparison after normalization; transitive |
| `units:quantity_eq` | left: `core:QuantityValue`, right: `core:QuantityValue` | symmetric |
| `units:dimension_of` | unit: `core:Unit`, dimension: `vocab:Dimension` | mass/length/time/currency/etc. — guards illegal comparisons |

## 3.2 `object` (NEW — generic physical-object properties)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `object:mass` | object: `core:PhysicalObject`, quantity: `core:QuantityValue` | — |
| `object:volume` | object: `core:PhysicalObject`, quantity: `core:QuantityValue` | — |
| `object:monetary_value` | object: `core:Thing`, amount: `core:QuantityValue`, audience: `core:CollectiveAgent` | worth is audience-relative, like reputation |
| `object:legality` | object: `core:Thing`, status: `vocab:LegalStatus`, jurisdiction: `core:CollectiveAgent` | a weapon legal in one zone, illegal in another |
| `object:condition` | object: `core:PhysicalObject`, condition: `vocab:Condition` | pristine…broken |
| `object:quality` | object: `core:PhysicalObject`, degree: `literal:unit_interval` | craftsmanship/grade |
| `object:stackable` | object: `core:Item`, max_stack: `literal:count` | for consumables/ammo |
| `object:owner_mark` | object: `core:Thing`, mark: `core:Concept`, owner: `core:Agent` | engraving/brand — recognition cue, theft evidence |
| `object:contains_item` | container: `core:Container`, item: `core:Item` | item-in-container (distinct from `space:contains` for places) |
| `object:capacity` | container: `core:Container`, quantity: `core:QuantityValue` | — |
| `object:is_vehicle` | object: `core:Vehicle`, vehicle_class: `vocab:VehicleClass` | — |
| `object:consumable_effect` | object: `core:Consumable`, effect: `core:State`, magnitude: `literal:unit_interval` | food→satiety, drug→intoxication |

## 3.3 `capability` (NEW — the planner's affordance layer)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `capability:can_perform` | agent: `core:Agent`, action_type: `core:ActionType`, context: `core:Thing` | derived/queryable; gated by preconditions below |
| `capability:requires_skill` | action_type: `core:ActionType`, skill: `core:Skill`, min_level: `literal:unit_interval` | — |
| `capability:requires_tool` | action_type: `core:ActionType`, tool_class: `core:Concept` | e.g. lockpick for `picklock` |
| `capability:requires_role` | action_type: `core:ActionType`, role: `core:Role`, context: `core:Thing` | authority to arrest, prescribe |
| `capability:requires_access` | action_type: `core:ActionType`, place: `core:Place` | physical/permission access |
| `capability:has_precondition` | action_type: `core:ActionType`, condition: `core:LogicalExpression` | STRIPS-style precondition |
| `capability:has_effect` | action_type: `core:ActionType`, effect: `core:Proposition`, polarity: `vocab:Polarity` | add/delete effect |
| `capability:action_cost` | action_type: `core:ActionType`, cost_kind: `vocab:CostKind`, amount: `core:QuantityValue` | time/energy/money/risk |
| `capability:success_probability` | agent: `core:Agent`, action_type: `core:ActionType`, target: `core:Thing`, probability: `literal:probability` | derived from skill vs difficulty |

## 3.4 `combat` (NEW — declared in v0.3 Layer C, never cataloged)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `combat:weapon_damage` | weapon: `core:Weapon`, damage_type: `vocab:DamageType`, magnitude: `literal:unit_interval` | — |
| `combat:weapon_range` | weapon: `core:Weapon`, range: `core:QuantityValue` | melee/ranged distinction follows from value |
| `combat:weapon_concealable` | weapon: `core:Weapon`, degree: `literal:unit_interval` | feeds `appearance:conceals_item` and search risk |
| `combat:armor_rating` | garment: `core:Garment`, damage_type: `vocab:DamageType`, mitigation: `literal:unit_interval` | generalizes v0.3 `appearance:protects_against` |
| `combat:attacks` | attacker: `core:Agent`, target: `core:Agent`, weapon: `core:Weapon` | the act; pairs with `event:AttackAction` |
| `combat:inflicts_wound` | source_event: `core:Event`, target: `core:Agent`, wound_type: `vocab:WoundType`, severity: `literal:unit_interval` | links combat to `body`/`health` |
| `combat:defends_with` | agent: `core:Agent`, means: `core:Thing` | block/dodge/cover |
| `combat:threat_assessment` | observer: `core:Agent`, target: `core:Agent`, perceived_threat: `literal:unit_interval` | drives flee/fight/comply decisions |
| `combat:combat_state` | agent: `core:Agent`, state: `vocab:CombatState` | calm/alert/fighting/fleeing/incapacitated |
| `combat:is_armed` | agent: `core:Agent`, weapon: `core:Weapon` | derived from `appearance:equipped_with` + weapon class |

## 3.5 `organization` (NEW — promised in v0.3 §7.3, absent from catalog)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `organization:has_unit` | org: `core:Organization`, subunit: `core:Organization` | org chart; transitive containment |
| `organization:has_rank` | agent: `core:Agent`, org: `core:Organization`, rank: `vocab:RankType` | — |
| `organization:reports_to` | subordinate: `core:Agent`, superior: `core:Agent`, org: `core:Organization` | chain of command (distinct from generic `social:supervises`) |
| `organization:has_policy` | org: `core:CollectiveAgent`, policy: `core:Norm` | org-level norms |
| `organization:controls_territory` | org: `core:CollectiveAgent`, place: `core:Place` | gang/corp turf — fixes v0.3 §7.3 "territory" with no predicate |
| `organization:has_jurisdiction` | org: `core:CollectiveAgent`, domain: `core:Concept`, place: `core:Place` | police/court scope |
| `organization:org_resource` | org: `core:CollectiveAgent`, resource: `core:Resource`, quantity: `core:QuantityValue` | treasury, materiel |
| `organization:employment_terms` | agent: `core:Agent`, org: `core:Organization`, commitment: `core:Commitment` | wage/duties as a commitment |
| `organization:maintains_record` | org: `core:CollectiveAgent`, record: `core:Record` | institutional memory access path (v0.3 §7.3: no auto-inheritance of member knowledge) |
| `organization:represented_by` | org: `core:CollectiveAgent`, agent: `core:Agent`, context: `core:Thing` | who may speak for the org |

## 3.6 `transport` (NEW — declared in v0.3 Layer C, never cataloged)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `transport:operates` | agent: `core:Agent`, vehicle: `core:Vehicle` | currently driving/piloting |
| `transport:can_operate` | agent: `core:Agent`, vehicle_class: `vocab:VehicleClass` | license/skill gate |
| `transport:vehicle_at` | vehicle: `core:Vehicle`, place: `core:Place` | uses `space:exactly_at` semantics |
| `transport:route_between` | route: `core:Route`, origin: `core:Place`, destination: `core:Place` | named path object |
| `transport:travel_time` | route: `core:Route`, mode: `vocab:TransportMode`, duration: `core:QuantityValue` | — |
| `transport:transit_access` | agent: `core:Agent`, line: `core:Thing` | public-transit/checkpoint permission |
| `transport:vehicle_capacity` | vehicle: `core:Vehicle`, passengers: `literal:count`, cargo: `core:QuantityValue` | — |

## 3.7 `health` (EXTENDS `body` — v0.3 listed health separately but only `body` exists)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `health:has_disease` | agent: `core:Agent`, disease: `vocab:DiseaseType`, severity: `literal:unit_interval` | — |
| `health:has_symptom` | agent: `core:Agent`, symptom: `core:Concept`, degree: `literal:unit_interval` | observable → feeds perception/diagnosis |
| `health:contagious` | agent: `core:Agent`, disease: `vocab:DiseaseType`, transmissibility: `literal:probability` | epidemic dynamics on the social graph |
| `health:receives_treatment` | patient: `core:Agent`, treatment: `core:Concept`, provider: `core:Agent` | — |
| `health:takes_medication` | agent: `core:Agent`, medication: `core:Consumable`, dose: `core:QuantityValue` | — |
| `health:recovery_progress` | agent: `core:Agent`, condition: `core:Concept`, progress: `literal:unit_interval` | heals over world-time |
| `health:addiction` | agent: `core:Agent`, substance: `core:Substance`, severity: `literal:unit_interval` | drives needs/goals |
| `health:medical_record` | record: `core:Record`, patient: `core:Agent`, institution: `core:Institution` | institutional, access-gated knowledge |

## 3.8 `affect` (EXTENDS `psychology` — appraisal-derived emotion; v0.1 §5.4 wanted this)

Emotions must be *generated and explainable*, not just stored. These predicates link an event/proposition to an emotion via appraisal dimensions (OCC/Scherer-style), so the runtime can answer "*why* does the NPC feel this?" (the v0.1 §2.5 explainability promise).

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `affect:appraises` | agent: `core:Agent`, stimulus: `core:Thing`, appraisal: `core:Appraisal` | reifies one appraisal instance |
| `affect:goal_congruence` | appraisal: `core:Appraisal`, degree: `literal:signed_unit` | helps/harms the agent's goals |
| `affect:agency` | appraisal: `core:Appraisal`, agent_cause: `core:Agent` | self/other/circumstance → anger vs guilt vs sadness |
| `affect:blameworthiness` | appraisal: `core:Appraisal`, degree: `literal:signed_unit` | against standards/norms |
| `affect:expectedness` | appraisal: `core:Appraisal`, degree: `literal:unit_interval` | surprise component |
| `affect:controllability` | appraisal: `core:Appraisal`, degree: `literal:unit_interval` | coping potential → fear vs anger |
| `affect:produces_emotion` | appraisal: `core:Appraisal`, emotion: `vocab:EmotionType`, intensity: `literal:unit_interval` | the appraisal→emotion mapping |
| `affect:emotion_decay_rate` | emotion_instance: `core:Thing`, rate: `literal:number` | mood returns to baseline over time |

v0.3 `psych:emotion_toward` and `psych:mood_state` remain as the *current-state* views; `affect:*` explains how they got there.

## 3.9 `time` (EXTENDS — day-phase, calendar, age; v0.1 made Tageszeit central)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `time:day_phase` | instant: `core:TimeInstant`, phase: `vocab:DayPhase` | dawn/morning/noon/evening/night — NPCs reason in phases, not minutes |
| `time:calendar_date` | instant: `core:TimeInstant`, year: `literal:count`, month: `literal:count`, day: `literal:count` | maps world-minutes → date |
| `time:season` | interval: `core:TimeInterval`, season: `vocab:Season` | — |
| `time:weekday` | instant: `core:TimeInstant`, weekday: `vocab:Weekday` | "market day", "patrol changes Fridays" |
| `time:age_of` | agent: `core:Agent`, age: `core:QuantityValue` | derived from birth `LifeEvent` + current time |
| `time:is_open` | place_or_service: `core:Thing`, interval: `core:TimeInterval` | opening hours (v0.1 §8.2) |

## 3.10 `perception` (EXTENDS — non-audiovisual & sensor modalities)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `perception:smell_access` | observer: `core:Agent`, source: `core:Thing`, degree: `literal:unit_interval` | v0.1 explicitly listed Gerüche |
| `perception:touch_contact` | observer: `core:Agent`, target: `core:Thing` | frisking, grabbing |
| `perception:reads_text` | observer: `core:Agent`, document: `core:Document`, comprehension: `literal:unit_interval` | gated by `education:literate_in` |
| `perception:sensor_detects` | sensor: `core:ArtificialAgent`, target: `core:Thing`, modality: `vocab:Modality` | camera/drone/microphone — surveillance (v0.1 §13) |
| `perception:perceptual_range` | observer: `core:Agent`, modality: `vocab:Modality`, range: `core:QuantityValue` | per-modality reach; cyberware can extend |
| `perception:occluded_by` | observer: `core:Agent`, target: `core:Thing`, obstacle: `core:Thing` | wall/smoke/crowd reduces signal_quality |

## 3.11 `channel` (NEW — communication infrastructure, distinct from `media` items)

`media` describes *items/messages*; `channel` describes the *infrastructure* that carries them. v0.1 listed radio, TV, social nets, implants, heralds, sermons, notices, magic — none had typed properties.

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `channel:channel_type` | channel: `core:Channel`, type: `vocab:ChannelType` | radio/print/net/implant/herald/sermon/magic |
| `channel:directionality` | channel: `core:Channel`, mode: `vocab:Directionality` | one_to_one / one_to_many / broadcast |
| `channel:reach` | channel: `core:Channel`, scope: `core:Thing` | room/street/district/citywide/global |
| `channel:latency` | channel: `core:Channel`, duration: `core:QuantityValue` | gossip is slow, broadcast is instant |
| `channel:persistence` | channel: `core:Channel`, mode: `vocab:Persistence` | ephemeral / recorded / archived |
| `channel:requires_access` | channel: `core:Channel`, requirement: `core:Concept` | device/literacy/membership |
| `channel:encrypted` | channel: `core:Channel`, degree: `literal:unit_interval` | eavesdropping difficulty |
| `channel:authenticated` | channel: `core:Channel`, degree: `literal:unit_interval` | impersonation difficulty — ties to `deception` |
| `channel:carries` | channel: `core:Channel`, item: `core:MediaItem` | binds infrastructure to content |

## 3.12 `plan` (EXTENDS goals/intentions — decomposition the planner needs)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `plan:has_plan` | agent: `core:Agent`, plan: `core:Plan`, goal: `core:Goal` | a plan serves a goal |
| `plan:subgoal_of` | child: `core:Goal`, parent: `core:Goal` | goal decomposition; cycle-safe |
| `plan:has_step` | plan: `core:Plan`, step: `core:Action`, order: `literal:count` | ordered actions |
| `plan:step_precondition` | step: `core:Action`, condition: `core:LogicalExpression` | per-step gating (uses `capability:has_precondition`) |
| `plan:plan_status` | plan: `core:Plan`, status: `vocab:PlanStatus` | active/suspended/abandoned/completed/failed |
| `plan:blocked_by` | plan: `core:Plan`, obstacle: `core:Thing` | explains stalled NPC behavior |

## 3.13 `tom` (NEW — theory of mind; required for working deception)

v0.3 `deception:intends_to_deceive` needs nested belief to function: a lie requires the speaker to model the listener's mind. v0.4 makes this explicit and bounded (depth ≤ 2 in the core; deeper is pack-opt-in for performance).

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `tom:models_belief` | agent: `core:Agent`, about: `core:Agent`, proposition: `core:Proposition`, estimated_confidence: `literal:probability` | A's estimate of B's belief |
| `tom:models_goal` | agent: `core:Agent`, about: `core:Agent`, goal: `core:Goal` | A's estimate of B's goal (drives negotiation) |
| `tom:intends_listener_to_believe` | speaker: `core:Agent`, listener: `core:Agent`, proposition: `core:Proposition` | the communicative intent behind assertion/lie |
| `tom:expects_reaction` | agent: `core:Agent`, about: `core:Agent`, action_type: `core:ActionType`, probability: `literal:probability` | anticipates response → bluff/threat planning |

Bound: core enforces **max nesting depth 2** (A models B's belief about a proposition). Recursive "A thinks B thinks A thinks…" is a pack-level, LOD-gated option (Technical Core v0.2 §16 — only Stufe 4 agents).

## 3.14 `provenance` (FORMALIZES v0.3 §8.4 — was prose, not predicates)

| Predicate | Named slots | Semantics / notes |
|---|---|---|
| `provenance:derived_via` | derived: `core:InformationEntity`, source: `core:InformationEntity`, transform: `vocab:Transform` | typed transformation (mutation operator from Technical Core v0.2 §3.2) |
| `provenance:shares_origin` | left: `core:InformationEntity`, right: `core:InformationEntity`, origin: `core:Event` | the basis for correlation discounting (η in v0.2 §2.5) |
| `provenance:retracted_by` | claim: `core:Claim`, retraction_event: `core:Event` | refutation tracking |
| `provenance:chain_length` | info: `core:InformationEntity`, hops: `literal:count` | how far a rumor traveled from source |
| `provenance:original_observer` | info: `core:InformationEntity`, observer: `core:Agent` | the root of the evidence graph |

---

# 4. Updated module inventory

Corrected namespaces (§1.1) and the new/extended modules. Counts are the **added** predicates in v0.4 plus the corrected v0.3 set.

| Module (= namespace) | Status | Predicate count |
|---|---|---:|
| `core` (incl. identity) | corrected namespace | 13 |
| `appearance` | unchanged | 13 |
| `body` | unchanged | 13 |
| `causality` | renamed from `event:` | 7 |
| `culture` | unchanged | 8 |
| `deception` | unchanged | 7 |
| `dialogue` (incl. discourse) | merged | 26 |
| `economy` | unchanged | 12 |
| `education` | unchanged | 7 |
| `environment` | unchanged | 11 |
| `epistemic` | `denies` moved to `dialogue` | 14 |
| `event` | unchanged | 11 |
| `media` | unchanged | 10 |
| `memory` | unchanged | 13 |
| `multiplayer` | unchanged | 4 |
| `narrative` | unchanged | 8 |
| `norm` | unchanged | 12 |
| `perception` | **+6** | 15 |
| `psychology` | unchanged | 14 |
| `reputation` | unchanged | 6 |
| `security` | unchanged | 5 |
| `social` | unchanged | 17 |
| `space` | unchanged | 16 |
| `time` | **+6** | 18 |
| `work` | unchanged | 6 |
| `units` | **NEW** | 9 |
| `object` | **NEW** | 12 |
| `capability` | **NEW** | 9 |
| `combat` | **NEW** | 10 |
| `organization` | **NEW** | 10 |
| `transport` | **NEW** | 7 |
| `health` | **NEW** | 8 |
| `affect` | **NEW** | 8 |
| `channel` | **NEW** | 9 |
| `plan` | **NEW** | 6 |
| `tom` | **NEW** | 4 |
| `provenance` | **NEW** | 5 |

**New total: ≈ 412 predicates across 38 modules** (v0.3 had 275 across 25, minus the namespace mergers). Plus the **ConceptScheme registry** (≈ 33 mandatory schemes, §1.2.2) and the extended class hierarchy (§2.1–2.2).

---

# 5. Revised MVP-minimum and freeze criteria

## 5.1 What of v0.4 is MVP-mandatory vs. pack-level

The v0.3 §23 MVP subset stays, with these v0.4 additions promoted to **MVP-mandatory** because the 20 end-to-end cases (v0.3 §23.3) silently depend on them:

- `units` — case 6/10/11 (debt, prices) are undefinable without it;
- `object` (value, legality, condition) — clothing-recognition and theft cases;
- `affect` (appraisal) — the "emotional trace remains" case (7) needs emotion *generation*;
- `time` day-phase — case 16 (time jump → shift/fatigue);
- `provenance` — cases 10/11 (shared-origin discount vs. independent witness) are *the* differentiator and need explicit predicates;
- `tom` (depth ≤ 1) — cases 12/13 (intentional lie) need `intends_listener_to_believe`.

**Pack-level (not MVP):** `combat`, `transport`, `organization` (beyond `social:supervises`), `health` (beyond `body`), `channel` (beyond a single radio), `plan` (beyond flat goals). These can be stubbed for the terminal MVP and filled per World Pack.

## 5.2 Updated freeze criterion (replaces v0.3 §24.3)

v1.0 freezes only when, in addition to v0.3's criteria:

1. the type checker enforces `literal:probability` vs `literal:unit_interval` vs `literal:signed_unit` distinctly;
2. **no slot is typed `core:Concept`** — every former `Concept` slot points to a named `vocab:` scheme;
3. module name = namespace, enforced by a conformance test;
4. every declared Layer-C module has either a predicate catalog or an explicit "deferred to pack" marker (no phantom modules);
5. the two demonstrator World Packs exercise at least one Creature/Artificial agent and at least two currencies (proves §2.1 and §3.1 portability);
6. deception works end-to-end through `tom` nested belief (proves §3.13).

---

# 6. What this still does not settle (honest residual)

Even at v0.4, three things are deliberately *not* "complete," and pretending otherwise would be wrong:

1. **The ConceptScheme contents.** Naming 33 schemes is not the same as populating them. Each scheme's member terms are a curation task per World Pack (the real ontology-authoring cost, Technical Core v0.2 §1.10). The core freezes scheme *identities*, not their full membership.
2. **Quantitative calibration.** All `θ` thresholds (the `epistemic:*` view cutoffs in §1.2.3, retrieval/utility weights) are starting points; they require tuning against the eval harness, which does not yet exist.
3. **Genre-specific physics.** Magic systems, hacking/netrunning rules, vehicle physics, and creature abilities are correctly Layer-D and should *not* be forced into the core. The extension contract (v0.3 §20) is what makes their absence acceptable rather than a gap.

This is the correct stopping point for the *core*: broad enough that a new genre adds a pack, not a fork — which is exactly the v0.3 §0 objective, now actually met.

---

# 7. Immediate next deliverables

1. **Regenerate the machine-readable registry** `unscripted_core_ontology_v0.4.json` from this corrected catalog (with `vocab:` schemes, typed literals, cardinality, properties, examples, tests per v0.3 §20.1).
2. **Generate JSON Schemas** for the corrected proposition/belief/event/plan records (the §24.2 item-1 dependency).
3. **Author the 33 ConceptScheme stubs** with their initial cyberpunk-pack membership.
4. Only then proceed to the **terminal MVP** (Technical Core v0.2 §7 / v0.3 §25 step 10), which now has a stable, type-clean ontology to build on.
