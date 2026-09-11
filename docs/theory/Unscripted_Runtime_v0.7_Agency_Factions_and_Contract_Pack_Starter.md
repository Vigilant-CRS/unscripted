# Unscripted
## v0.7 Design Note — Agency, Mobilization & the Faction/Director Layer

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*
### (+ Implementation Contract Pack starter: ownership matrix, phase graph, schemas)

**Date:** 22 June 2026 **Builds on:** v0.6 reference runtime + Theory Dynamics &
Engineering Spec v0.6. **Status:** implemented and tested in
`unscripted-reference-v0.7` (16/16 tests green; `python demo.py`).

This note (a) records what we adopted from tabletop RPG design and why, (b) specifies the new primitives with the equations actually used in the reference code, and (c) starts the **Implementation Contract Pack** the readiness review asked for — the module ownership matrix, the runtime phase graph, and the new JSON schemas — extracted from the working code rather than guessed.

---

# 1. What we took from tabletop, and why

The deliberative layer (v0.6) let an NPC decide and speak, but every action was **solo**. Tabletop systems solve exactly the missing piece — social power as a move. We adopted, deliberately, only the primitives that generalize across genres; genre-specific mechanics (initiative order, dice math, classes/levels) stay in the World Pack.

| Source idea | System | What we built | Why core (not pack) |
|---|---|---|---|
| Resources/budget as a behavioral driver | most RPGs | `resources` state → affordability + **Prospect reference point** | A universal driver; reuses the Prospect transform we already had. |
| Calling in allies / contacts / retainers | Blades, PbtA Bonds | **ally-response model** + mobilization action with latency + social-capital cost | A general social primitive (kin, gang, guild, police). |
| Reactive moves / triggers | behavior-tree AI, PbtA moves | **ReactiveRule** layer (condition → priority action, preempts deliberation) | Small, generic, was architecturally absent. |
| Influence / leverage | FATE, Blades | **leverage** model (dependence + secrets + resources + status) | The basis for coercion/recruitment; thin derived model. |
| Partial success | PbtA, FATE | **graded resolution** (full / partial / consequence / miss) | Narrative texture; trivial to implement. |
| Faction clocks / fronts | Blades, Dungeon World | **ProgressClock** + **Director** (off-screen goal progress) | This *is* the "society develops" USP. |
| Heat / wanted | Blades | **heat** accumulator → faction mobilization at threshold | Emergent enforcement pressure; ties mobilization + reputation. |

Explicitly **not** adopted into core: initiative/turn economy, dice-specific resolution, class/level/XP ladders, fixed stat blocks. These are pack/genre choices.

---

# 2. The new primitives (equations as implemented)

## 2.1 Resources → risk (Prospect reference point)

`resources ∈ [0,1]` is liquid wealth. It (a) gates affordability (a real pack: can't bribe/hire without funds) and (b) sets the **risk reference point** `ref = resources`. With the Prospect flag on, an `ActionOutcome(delta, p, ref)` contributes `v(delta − ref)·w(p)`. **Below** the reference (desperation) the value curve is risk-seeking; **above** it (established wealth) it is loss-averse. So the broke NPC and the wealthy NPC value the *same* gamble differently — emergent, not hand-coded. Reference: `agency.risk_reference_point`, `policy.outcome_value`.

## 2.2 Reactive rules (trigger → priority action)

A `ReactiveRule(condition, action_id, priority, reason)` fires on a context predicate and **preempts deliberation**: the matching candidate gets a `+priority` utility floor and selection temperature drops to near-deterministic. The shipped rules:

- `summon_kin_when_hurt`: `injured ∧ threatened` → `mobilize_allies` (priority 2.0);
- `flee_when_outmatched`: `threatened ∧ threat_severity > 0.7 ∧ ¬has_backup` → `flee` (priority 1.5).

This is how "only when injured, summon the sons" stays authorable instead of being a fragile utility accident. Reference: `agency.default_reactive_rules`, `runtime.decide`.

## 2.3 Ally-response model (mobilization)

Calling for help is an action whose payoff is the summed response of reachable allies. For each ally `b` of caller `a`:

```
P(b responds) = σ( 2.0·loyalty + 2.5·kinship·(0.5+0.5·urgency)
                 + 1.5·favor_debt + 1.2·authority(a→b) − 1.0·cost_b − 1.0 )
authority(a→b) = clamp( 0.6·clamp(status_a − status_b + 0.5) + rank )
latency(b)     = 2 if co-located else 15   (world-minutes; scheduled as ally_arrives events)
```

Reachability is **status-gated**: kin / loyal / same-group allies are always reachable; **institutional** allies (police, corp security) require `status_a ≥ 0.6`. Mobilizing depletes the reciprocity ledger (social-capital cost) — over-asking burns the relationship. The expected backup is scaled by **reach** `= 0.7 + 0.6·status`, so high standing summons heavier muscle. Reference: `agency.ally_response`, `agency.mobilization_candidate`, `runtime.mobilize`.

## 2.4 Leverage (asymmetric power)

```
leverage(a over b) = clamp( 0.4·dependence_b_on_a + 0.3·a_holds_secret_on_b
                          + 0.2·clamp(resources_a − resources_b + 0.3) + 0.1·clamp(status_a − status_b) )
```

Leverage is what lets `a` move `b` against `b`'s own preference (coercion, recruitment). It is asymmetric by construction. Reference: `agency.leverage`.

## 2.5 Graded resolution

```
r = U(0,1) seeded;  p = success_prob
r < 0.6p          → full          (clean success)
0.6p ≤ r < p      → partial        (success at a cost)
p ≤ r < p+0.4(1−p)→ consequence    (failure with a complication)
else              → miss
```

Reference: `agency.resolve`.

## 2.6 Faction / Director layer

A `Faction(influence, resources, heat, territory, goals, clocks)` is a collective agent. Each tick the `Director`:

- decays `heat` by `0.02·(Δt/60)`;
- advances each goal `ProgressClock` with probability `0.15·(0.5+influence)·(0.5+resources)` (off-screen progress);
- on `heat ≥ 0.6`, schedules a `faction_mobilize` event with `latency = 20·(1.5 − influence)` (more influence → faster response), then discharges `0.4` heat.

Crimes/threats/attacks raise the **controlling faction's** heat by `0.25·|severity|·(0.5 + surveillance_level)`. This is the ally-response mechanic at faction scale and the engine of emergent enforcement. Reference: `factions.Director.step`, `runtime.process_event`.

---

# 3. Social standing — woven through (the explicit requirement)

| Mechanism | How standing enters | Reference |
|---|---|---|
| Mobilization reach | institutional allies require `status ≥ 0.6`; reach scales `0.7 + 0.6·status` | `agency.potential_allies`, `mobilization_candidate` |
| Authority over others | `0.6·clamp(status_gap+0.5) + rank` | `agency.authority` |
| Leverage | `+0.1·clamp(status_a − status_b)` term | `agency.leverage` |
| Faction response speed | faction `influence` (collective standing) → lower mobilization latency, faster clocks | `factions.Director.step` |
| Register / speech | status raises default formality; perceived status is reputation-mediated | `sociolinguistics` (v0.6) |

Standing is **prestige/position**, not "worth" — consistent with the v0.6 anti-classism framing of the sociolinguistic module.

---

# 4. Implementation Contract Pack — starter

The readiness review's recommended binding artifact. This is a **starter** extracted from the working v0.7 code (not yet the full frozen pack — the remaining ~20 schemas and the 20 golden fixtures are the next consolidation pass). What is below is authoritative for the modules it covers.

## 4.1 Module ownership matrix

One owner per mutable state (the review's hard requirement). Feature providers own no mutable state.

| State | Owner module | Kind | File |
|---|---|---|---|
| beliefs (per agent) | `belief` | state-owner | `belief.py` |
| memory (per agent) | `memory` | state-owner | `memory.py` |
| affect (mood + emotions) | `affect` | state-owner | `affect.py` |
| relationship vector (trust/liking/…) | `relationship` | state-owner | `relationship.py` |
| reputation (audience view) | `reputation` | state-owner | `relationship.py` |
| identity salience | `identity` | state-owner | `relationship.py` |
| resources / social_status | (agent attribute; authored) | data | `agent.py` |
| faction heat / clocks / resources | `director` | state-owner | `factions.py` |
| conversation state | `dialogue_planner` | state-owner | `dialogue.py` |
| value activation | `value` | feature-provider | `social.py` |
| exchange/fairness/dependence | `social_exchange` | feature-provider | `social.py` |
| norm pressure | `norm` | feature-provider | `social.py` |
| network/tie/bridge | `social_network` | feature-provider | `social.py` |
| theory-of-mind | `tom` | feature-provider | `social.py` |
| impression/face | `impression` | feature-provider | `social.py` |
| interpersonal stance | `interpersonal` | feature-provider | `social.py` |
| style vector | `sociolinguistics` | feature-provider | `sociolinguistics.py` |
| candidate scoring/selection | `policy` | function | `policy.py` |
| reactive rules / ally response / leverage / resolution | `agency` | functions | `agency.py` |
| event ledger + projections | `store` | persistence | `persistence.py` |

## 4.2 Runtime phase graph

**Event path** (`runtime.process_event`):
```
append_event
  → [macro] faction_mobilize? narrate & return
  → [heat]  threat/attack/crime → director.add_heat(controlling_faction)
  → perception.filter → for each observer:
        belief.update        (state-owner)
        memory.encode        (state-owner)
        affect.update        (state-owner)
        persist projections + reason trace
```

**Decision path** (`runtime.decide`):
```
context + identity.salience + value.active_values
  → assemble candidates (catalog) [+ mobilization candidate]
  → reactive rules fire? inject priority action, lower temperature
  → if use_prospect: set outcome reference_point = resources
  → policy.score (bounded groups + emotion bias) → policy.select (seeded softmax)
```

**Speech path** (`runtime.say`): `decide → sociolinguistics.compute_style → dialogue.plan → realize → validate (buffered) → fallback on REJECT_HARD`.

**Periodic path** (`runtime.advance_time`):
```
fire due scheduled events (incl. ally_arrives, faction_mobilize)
  → affect.decay + memory.decay_and_consolidate per agent
  → director.step (heat decay, clock advance, threshold mobilization scheduling)
```

## 4.3 New/changed JSON schemas (v0.7)

**Character file additions:**
```json
{
  "social_status": 0.0,            // [0,1] prestige baseline
  "resources": 0.0,                // [0,1] liquid wealth -> affordability + risk reference
  "dialect": "string|null",
  "relationships": {
    "<other_id>": { "trust": 0.0, "liking": 0.0, "familiarity": 0.0,
                    "kinship": 0.0, "loyalty": 0.0, "favor_debt": 0.0, "dependence": 0.0 }
  }
}
```

**world.json `factions` block:**
```json
{ "factions": [
  { "id": "faction:badges", "influence": 0.8, "resources": 0.7,
    "territory": ["place:..."], "goals": ["suppress_gang"] }
] }
```

**ActionOutcome** (frozen): `{ dimension, delta, probability, reference_point, source }`.
**AllyResponse:** `{ ally_id, probability, latency, will_come }`.
**ProgressClock:** `{ name, size, filled }`.
**ReactiveRule:** `{ rule_id, condition, action_id, priority, reason }` (condition is code-side, not data, in the MVP).

## 4.4 Invariants (carried into tickets)

- side-effect-free theory functions; owners apply staged state;
- determinism: every stochastic draw seeded from `(global_seed, agent, event, time, module[, salt])`;
- one owner per mutable state; feature providers propose typed deltas only;
- trust applies positive/negative totals separately (η↑=0.10, η↓=0.40);
- generation buffered, never streamed before validation;
- social standing gates institutional mobilization reach (`status ≥ 0.6`).

---

# 5. What remains

Full **Implementation Contract Pack** (the ~20 remaining frozen schemas: Entity, Event, EventRole, Observation, Claim, Evidence, Goal, Intention, Plan, Conversation, ConversationTurn, DialoguePlan, ValidationResult, WorldPackManifest, Snapshot, ReasonTrace, …) + the **20 golden scenario fixtures** with expected structured outcomes. These are now an *extraction* task from the v0.7 code, not a design task.

Still genuinely not built (from the v0.6 sync table, unchanged): full BDI plan repair/resource-locking; LOD promotion/demotion; full `EmotionInstance`; real LLM provider; group emotional contagion and multi-agent coalition beyond pairwise mobilization.
