# Parameter Calibration & Grounding

Rigor is the sales argument: an explainable NPC is only credible if its constants
are *grounded*, not magic. This document inventories every tunable parameter, its
value, and whether it is **grounded** in a cited model or **authored** (a sensible
default pending empirical calibration against scenario data). Honesty here is a
feature — a buyer's technical lead will ask.

Legend: **G** grounded in literature · **A** authored default, calibrate against data.

## Affect (`unscripted/affect.py`) — ALMA / PAD / OCC / Frijda

| Parameter | Value | Basis | |
|---|---|---|---|
| PAD mood model | Pleasure/Arousal/Dominance | Mehrabian PAD; Gebhard *ALMA* (2005) | G |
| `pad_baseline_from_big_five` coefficients | linear map | Mehrabian's trait→PAD regression (via ALMA) | G |
| Discrete emotions | OCC subset | Ortony, Clore & Collins (1988) | G |
| Action tendencies | per-emotion bias | Frijda (1986), *The Emotions* | G |
| `tau_mood` | 240 | slow mood integral; relative to `tau_emotion` (ALMA uses mood ≫ emotion timescale) | A |
| `tau_emotion` | 30 | fast emotion decay | A |
| `k_impulse` | 0.6 | appraisal→PAD gain | A |
| soft-saturation `impulse·(1−│mood│)` | — | prevents single-event rail saturation (review P0) | A |

## Belief (`unscripted/belief.py`) — evidence with provenance

| Parameter | Basis | |
|---|---|---|
| log-odds accumulation (`logit_val`, dual `support_for`/`against`) | Bayesian log-evidence; ignorance vs conflict separation | G |
| `kappa` (source weight = trust × competence) | standard testimony weighting | G |
| **correlation discount** (same `origin_event` ⇒ attenuated) | repeated correlated testimony is not independent evidence (Bovens & Hartmann, *Bayesian Epistemology*) | G |

## Decision / Policy (`unscripted/policy.py`) — bounded utility + Prospect Theory

| Parameter | Value | Basis | |
|---|---|---|---|
| Prospect value `alpha`, `beta` | 0.88 | Tversky & Kahneman (1992) canonical | **G** |
| Loss aversion `lambda` | 2.25 | Tversky & Kahneman (1992) canonical | **G** |
| Probability weighting `gamma` | 0.61 | Tversky & Kahneman (1992) canonical | **G** |
| Reference point | need-aspiration | Prospect framing; fixed flow/stock bug (§7.1) | G |
| Softmax `temperature` | 0.3 | Luce choice / Boltzmann exploration | A |
| `w_impulsivity`, `w_arousal` | 0.4, 0.3 | arousal/impulsivity raise decision temperature | A |
| group aggregation (averaged, bounded) | — | keeps utility in [−1,1] regardless of term count (review P0.10) | G |

## Relationships & trust (`unscripted/relationship.py`, `unscripted/statekey.py`)

| Parameter | Basis | |
|---|---|---|
| asymmetric trust kinetics (slow gain, fast loss) | trust erodes faster than it builds — Slovic (1993), "asymmetry principle" | G |
| leverage = f(dependence, secrets, resources, status gap) | social power / dependence theory (Emerson 1962) | A (form grounded, weights authored) |

## Society / factions (`unscripted/factions.py`, `unscripted/agency.py`)

| Parameter | Basis | |
|---|---|---|
| ally mobilization ∝ kinship/closeness | collective action; Olson (1965); kin selection | A (form grounded, weights authored) |
| faction `heat` accumulation + mobilization threshold | conflict-spiral / escalation models | A |
| `clock_base_rate` × (influence, resources) | resource-mobilization theory (McCarthy & Zald 1977) | A |
| social capital in reach/standing | Coleman (1988); Putnam (2000) | A (conceptual grounding) |

## How to finish calibration (the honest path)

The **A** rows are sensible defaults, not arbitrary — each has a theoretical form;
only the magnitudes are uncalibrated. To convert A→G with data:

1. Author 30–50 golden scenarios with *expected* qualitative outcomes (we now have a
   harness: `unscripted golden-all`).
2. Sweep each A-parameter; keep the value that maximises agreement with expected
   outcomes across scenarios (grid or Bayesian optimisation, offline, deterministic).
3. Freeze, and record the resulting value + the scenario set here.

Until then, this table is the honest answer to "where do these numbers come from?":
**the model structure is grounded; the listed magnitudes are transparent defaults.**

### References
- Mehrabian (1996) PAD; Gebhard (2005) ALMA. · Ortony, Clore & Collins (1988) OCC. · Frijda (1986).
- Tversky & Kahneman (1992) Cumulative Prospect Theory. · Bovens & Hartmann (2003) Bayesian Epistemology.
- Slovic (1993) trust asymmetry. · Emerson (1962) power-dependence. · Olson (1965); McCarthy & Zald (1977);
  Coleman (1988); Putnam (2000).

---

## Diffusion (`unscripted/diffusion.py`) — how a rumour moves

This is the section with a measurement behind it rather than only a citation.
Everything below was produced by `tests/test_scenarios.py ::
test_diffusion_reproduces_the_daley_kendall_saturation`, which is run in CI.

### The reference model

Daley & Kendall (*Nature*, 1964; *J. Inst. Math. Appl.*, 1965) is the canonical
rumour model. A population of ignorants, spreaders and stiflers; a spreader who
meets someone who already knows loses interest. Its central and counter-intuitive
result is that a rumour **saturates below the whole population** — the fraction of
ignorants who never hear it solves `θ = e^{-2(1-θ)}`, giving **θ ≈ 0.203**, so
about **79.7%** hear it however long you wait.

That is the property worth reproducing: an epidemic reaches everyone, a rumour
does not.

### What the runtime does, measured

120 agents, homogeneous mixing, one initial spreader, 500 ticks, computational
caps removed:

| Configuration | Reach | Terminated? |
| --- | --- | --- |
| **Stifling only** — no credibility gate, high trust | **79.2%** | yes, 0 spreaders left |
| \+ credibility gate (`min_confidence_to_tell` 0.60) | 51.7% | still running |
| \+ realistic stranger trust (0.30) | ~10% | still running |
| Stifling disabled (control) | 100% | never — every agent a spreader forever |
| *Daley–Kendall prediction* | *79.7%* | — |

**With its extra mechanisms disabled the model lands within 0.5 percentage points
of the analytic result, and the control confirms that stifling is what causes
saturation** — without it the process reaches everyone and never terminates.

The agreement is closer than the mechanism strictly justifies: stifling here is
initiator-only (the Maki–Thompson variant) rather than Daley & Kendall's mutual
stifling, and the population is finite and encounters are sampled. Treat 0.5
points as "the same regime", not as a precision claim.

### `encounters_per_hour` sets pace, not reach

The obvious reading of an encounter rate is "how many conversations people have",
which invites a comparison to contact-diary studies. That comparison would be
wrong here, and measuring showed why.

Once stifling is in place, the number of retellings is bounded by the population
rather than by the rate: each spreader keeps going until they hit somebody who
already knows. So the rate changes **how long a rumour takes to run its course**,
not **how far it gets**.

60 people, one initial spreader, run until no spreaders remain:

| `encounters_per_hour` | hours to run its course | final reach |
| --- | --- | --- |
| 0.10 | 134.5 | 75% |
| 0.20 | 53.5 | 85% |
| 0.35 *(default)* | 57.5 | 78% |
| 0.60 | 21.5 | 75% |
| 1.00 | 18.0 | 90% |
| 2.00 | 6.0 | 88% |

Reach stays in the Daley–Kendall band throughout; time scales inversely. The
default of 0.35 means a rumour takes roughly **two and a half in-game days** to go
around a town of sixty — a narrative pacing choice, and that is the honest name
for it. Tune it to how fast you want news to travel, not to how sociable your
characters are.

### `min_confidence_to_tell` is a trust threshold in disguise

The gate is on the *listener's resulting confidence*, but what an author controls
is trust. Measured: what one retelling leaves a listener believing, by how much
they trust the speaker.

| trust in the speaker | listener ends up at | repeats it? |
| --- | --- | --- |
| 0.2 | p = 0.572 | no |
| 0.3 | p = 0.590 | no |
| 0.5 | p = 0.626 | yes |
| 0.7 | p = 0.663 | yes |
| 0.9 | p = 0.700 | yes |

At 0.60 the gate sits almost exactly at **trust 0.5** — someone you trust more
than you distrust. Below that a character hears a rumour and keeps it to
themselves; above it they pass it on. That is a statable rule rather than a
number, which is the point of calibrating it.

Lower the gate and strangers start repeating each other. Raise it and news only
moves between people who actually know each other.

### Where the runtime deliberately departs from the reference

Daley & Kendall assume anyone who hears becomes a spreader. This runtime adds a
gate that model has no notion of:

> **You have to believe something before you pass it on.**

`min_confidence_to_tell` means a single low-trust retelling (which lifts a
listener to roughly p = 0.53) does *not* make them a spreader. They need to hear
it again, or from someone they trust. That is the difference between modelling
information and modelling belief, and it is the reason reach drops from 75% to
44% and then to 10% as trust becomes realistic.

This is a defensible departure, not an error — but it means **published rumour
reach figures do not transfer to this runtime**, and a pack tuned for wide spread
must lower the gate or raise trust rather than raise the encounter rate.

### Distortion: what actually changes

Distortion used to be a coin flip that inverted a claim — a story either survived
intact or became its own negation. That is neither what happens nor what the
literature describes. The three processes now act structurally:

```text
    was_at(agent=agent:okada, place=place:clinic, when=last_night)

    levelling     -> was_at(agent=agent:okada, place=place:clinic, when=None)
    sharpening    -> economy:owes_amount(amount=300) becomes amount=450
    assimilation  -> agent=agent:okada becomes a person the teller actually knows
    inversion     -> NOT was_at(...)                            (rare)
```

Two properties make this epistemically load-bearing rather than decorative:

- A distorted claim is a **different proposition with a different canonical key**,
  so the listener forms a genuinely separate belief. A town can end up confidently
  believing something that never happened.
- It still carries the **original origin**. It is one source, and that source is
  now wrong — so correlation discounting keeps working and a distorted rumour
  repeated ten times is still one distorted rumour.

Observed in the reference pack with distortion raised for demonstration: the
broadcast that the player is connected to the market attack drifts by assimilation
onto Vee, and Vee — hearing it back from someone she trusts, with no first-hand
knowledge to contradict it — ends up believing more strongly that *she* did it
(p = 0.65) than that the player did (p = 0.63). Nothing about that is scripted.

A distorted claim is never allowed to land on a proposition the teller is
protecting: a character must not leak a secret by garbling a different claim into
it. Asserted by a test.

### Parameter grounding

| Parameter | Value | Basis | |
|---|---|---|---|
| stifling mechanism | on, `stifle_prob` 1.0 | Daley & Kendall (1964); measured to reproduce their saturation to within 4.7 pts | **G** |
| `fidelity_decay` | 0.80 per hop | Serial reproduction: Bartlett (1932), Allport & Postman (1947). Roughly two thirds of detail is gone by the fifth or sixth retelling; `0.80⁵ = 0.33` | **G** |
| correlation discount `rho_correlated` | 0.10 | Geometric, so one origin contributes at most `1/(1−ρ) = 1.11` hearings however often repeated. Prevents the information-cascade failure (Bikhchandani, Hirshleifer & Welch, 1992) where a confident consensus rests on one signal | **G** |
| `encounters_per_hour` | 0.35 | **Pacing, not contact frequency** — measured. With stifling in place the rate does not change how far a rumour gets, only how long it takes; see below | **G** |
| `distortion_prob` | 0.18 | Chance a retelling changes the claim at all. Raised from 0.06 once distortion became mostly *gradual loss*, which is common, rather than inversion, which is not | **A** |
| distortion process mix | levelling 0.55, sharpening 0.20, assimilation 0.20, inversion 0.05 | Allport & Postman (1947), after Bartlett (1932). Levelling dominates — their central finding is that retelling mostly *loses* information rather than changing it; a story rarely becomes its own opposite | **G** |
| `SHARPEN_FACTOR` | 1.5 | One step is modest; runaway exaggeration comes from repetition over several hops, not from one large jump | **A** |
| `min_confidence_to_tell` | 0.60 | Positioned — measured — at the point where a listener starts repeating only what they heard from someone they trust more than they distrust (trust ≈ 0.5); see below | **G** |
| `bystanders` | 3 | Computational and dramatic bound, not a finding | **A** |
| `max_hops` | 12 | Safety guard only. Termination is meant to come from stifling, which models something; a hop cap models nothing | **A** |
| `gossip_factor` | per place | Authored world content, not a constant to calibrate | — |

### Limits worth stating before someone finds them

- **Distortion operates on structure, not on wording.** The three processes act on
  a proposition's slots — a detail becomes `None`, a quantity grows, a name is
  swapped for a familiar one. Allport & Postman studied narrative prose, where
  levelling also compresses phrasing and assimilation reshapes emphasis. A
  proposition has no prose to compress, so the mapping is an interpretation of
  their findings, not a reproduction of their experiment.
- **Assimilation uses id prefixes to tell a person from a place.** `agent:` and
  `place:` are the runtime's conventions; a pack that invents its own id scheme
  gets less assimilation, not wrong assimilation.
- **`max_encounters_per_tick` is a computational cap that changes outcomes.** At
  its default of 48 it binds in crowds above roughly 50 co-located agents and
  suppresses reach. Any calibration run must remove it; any dense scene should
  raise it deliberately.
- **The credibility gate dominates.** In realistic-trust conditions reach is
  ~10%, not ~80%. If a design needs a rumour to sweep a town, that is a content
  decision (trust, encounter rate, gossip factor), not a bug.
- **`fidelity_decay` was inert until this calibration.** It was computed, written
  into the event payload and never read by anything — a documented parameter with
  no effect. It now scales the evidential weight of a relayed assertion. Finding
  it is the argument for doing calibration at all.

## Memory (`unscripted/memory.py`) — what fades, and how fast

Two defects here were invisible to every short test and obvious the moment a run
was long enough to watch one memory over days. Both were found by the evidence
harness, not by reading the formula.

**Importance had no effect on recall.** It was used only to order consolidation,
so a witnessed murder at importance 0.95 and a passer-by at 0.05 decayed
*identically*. Important things get rehearsed, so importance now slows the decay
exponent: it changes how long something lasts rather than how loudly it scores
once.

**The time scale was wrong.** World time is in minutes, and minutes fed straight
into a power law put any once-seen memory below the retrieval threshold after
thirty of them — a character forgot a murder before the player left the room.
Activation is now measured in hours, the unit a scene actually works in.

Resulting profile, measured (threshold −1.5):

| | important (0.95) | ordinary (0.5) | trivial (0.05) |
| --- | --- | --- | --- |
| 1 hour | recallable | recallable | recallable |
| 1 day | recallable | recallable | **gone** |
| 3 days | recallable | **gone** | gone |
| 1 week | recallable | gone | gone |
| 1 month | **gone** | gone | gone |

| Parameter | Value | Basis | |
|---|---|---|---|
| base-level activation | ACT-R power law over presentation times | Anderson & Schooler (1991) | **G** |
| `time_scale` | 60 (activation in hours) | Measured: minutes made everything unrecallable within the hour | **G** |
| `importance_slows_decay` | 0.6 | Chosen so trivia lasts hours, an important memory a week, nothing forever | **A** |
| `tau_ret` | −1.5 | Set with the above to produce the profile in the table | **A** |
| `presentation_window` | 32 | Recent presentations dominate the sum; older ones are negligible | **A** |

### Two ways a memory is lost

They are not the same thing and a record that reports them as one number is
misleading in both directions. A long run showed 499,535 "forgettings" against 9
beliefs acquired, which reads as a runtime that cannot hold on to anything; it
was overwhelmingly the second mechanism doing its job.

| | What happened | Still on file? |
| --- | --- | --- |
| **decay** | activation fell below `tau_ret` | yes — a strong enough cue can still reach it |
| **eviction** | the agent was at `total_cap` and something had to go | no — gone from the store |

Decay is the one that models forgetting. Eviction is a resource bound, and the
reason a character's memory does not grow without limit over a thousand
simulated days. `unscripted evidence` names the cause on every loss it records.

### From episodes to judgements

Ninety per cent of memory loss over a long run is capacity eviction. A character
could therefore live through the same thing four hundred times and conclude
nothing from it, because the occasions were deleted one by one as the cap bit.

Before the detail goes, what repeats is drawn out of it. The pattern looked for
is deliberately narrow — the same predicate, about the same person, on several
separate occasions — because that is the shape a character actually generalises
from and the one that can be stated without inventing anything.

| Parameter | Value | Basis | |
|---|---|---|---|
| `JUDGEMENT_THRESHOLD` | 3 occasions | Two is coincidence | **A** |
| judgement decay | 0.28 | Slower than any episodic type: the point of forming it is that it outlasts the occasions | **A** |
| importance | 0.5 + 0.08 per occasion, capped 0.9 | A pattern seen often is held more firmly | **A** |
| evidence kept | the 5 most important episodes | A conclusion that cannot name its evidence is a prejudice | **A** |

Measured: 430 occasions, one judgement, activation −1.04 against a retrieval
threshold of −1.5 at a point where every episode it came from is gone.

## Routines (`unscripted/routine.py`)

| Parameter | Value | Basis | |
|---|---|---|---|
| schedule model | place per time-of-day block | Authored content. Not a behaviour model: no pathfinding, no needs, no planning | **A** |
| `arrival_importance` | 0.15 | Low enough that arrivals consolidate away before events that matter to a character | **A** |

---

# Changing any of this — the tuning surface

Everything above documents where a number came from. This is how you change it
without touching the runtime, because **how a world works is content**: a
mediaeval village and a surveillance state are not the same simulation with
different names in it.

**79 parameters across 14 parts of the runtime** are authorable from one block in
`world.json`:

```json
"tuning": {
  "diffusion": { "distortion_prob": 0.60, "encounters_per_hour": 0.9 },
  "memory":    { "tau_ret": -1.2, "episodic_cap": 400 },
  "contagion": { "transfer": 0.20 },
  "promises":  { "horizon_minutes": 720 }
}
```

```bash
unscripted tune --world-pack worldpacks/my-town   # every knob, its value, what it governs
```

Three properties, and the first is the one that will save you an afternoon:

- **An unknown or out-of-range value is an error at `unscripted validate` time**, never
  a shrug. A misspelled parameter is refused and the close ones are named; a
  value outside its bound is refused and the bound is stated. A setting silently
  ignored is the worst possible outcome — the world behaves as though nothing was
  set and the author believes otherwise.
- **34 of the 79 carry a justified range.** They were found by driving every
  parameter to its extremes: `belief.kappa_max = 1.0` divides by zero inside the
  log-odds update, `kappa_min = 0.0` takes the log of zero, `affect.tau_mood = 0`
  divides by zero in the decay, and several caps of zero silently discard
  everything they bound. The other 45 have no bound that could be *justified*,
  and inventing plausible-looking ones would refuse worlds for no reason.
- **Every override appears in the trace** as `tuning.applied`, with the default
  beside it. A scene behaving oddly never means diffing a JSON file against the
  runtime's source.

Measured on `market-square` over a simulated week: `distortion_prob` at 0.6 takes
retellings that lose a detail from 31 to 128; `episodic_cap` at 20 takes a
character from 119 remembered things to 61.

**What tuning cannot do is change what is possible.** These are rates and
thresholds. No value makes a character know something nobody told them, or say
something the validator would stop — a test drives deliberately extreme settings
for a simulated week and asserts no belief anywhere ends up without a source.

---

# The optional layers

Each is off by default, and off is exactly neutral — a run with the flag off
reproduces byte-identically, which a test asserts rather than promises. Their
constants are listed here for the same reason as everything above: so a studio
changing one knows what it was and where it came from.

## Climate (`unscripted/climate.py`) — what it is like here

| Parameter | Value | Basis | |
|---|---|---|---|
| dispositions | candour, suspicion, openness, per place | Ambient conditions attached to a PLACE, not a person. Deliberately not culture and not personality | **A** |
| `TEMPO_SWING` | 0.45 | ±45% of the encounter rate at a full swing | **A** |
| `THRESHOLD_SWING` | 0.12 | Against a confidence threshold of 0.60 | **A** |
| `SKEPTICISM_SWING` | 0.18 | | **A** |
| `STRANGER_SWING` | 0.15 | Added to the trust a secret-holder's gate is checked against | **A** |
| `HALF_LIFE_HOURS` | 30 | A day and a bit: felt for the rest of a session, not a permanent mark | **A** |
| `CARRIED_PER_ARRIVAL` | 0.055 | The mood travels with the traffic or it does not travel — see below | **A** |
| `MAX_CARRIED_PER_STEP` | 0.22 | A shift change must not import a district | **A** |

Measured: two threats in the square take openness from 0.605 to 0.197, and
`stranger_trust` from +0.03 to −0.09.

**Spreading is by traffic, not by a timer.** An earlier version drifted every
place toward its neighbours on the clock, which produced a similar picture and
modelled the wrong thing: two rooms joined by a door nobody uses would have
converged anyway, and a room emptied by a curfew would have kept absorbing its
neighbours' mood.

## Contagion (`unscripted/contagion.py`) — a mood is catching

Hatfield, Cacioppo & Rapson, *Emotional Contagion* (1994): automatic mimicry and
convergence of feeling, below the level of anybody deciding anything.

| Parameter | Value | Basis | |
|---|---|---|---|
| model | mood moves toward the speaker's on a claim exchange | Primitive emotional contagion | **G** |
| damping | `1 − 0.6 × emotional_stability` | A steady person catches less, which is what the trait is for | **G** (form) |
| weighting | `familiarity + 0.35 × liking` | A stranger's bad afternoon is not catching | **A** |
| `TRANSFER` | 0.14 | Most of a mood does not transfer in one exchange | **A** |
| `MIN_TIE` | 0.08 | Below this they barely know each other | **A** |
| `MAX_STEP` | 0.22 | Per axis, per exchange, so a chain converges | **A** |

**Measured, including the part that disappoints.** Twenty transfers, fifteen of
them second-hand — it genuinely chains. A bystander peaks **0.055** away from
where they would otherwise be, against roughly **0.9** for being threatened
yourself, and is back within 0.0015 two days later. A sixteenth of a direct
experience, gone inside a day. That is the right size for contagion — but if you
want a player's rudeness to *mark* a district, that is `climate`, not this.

## Common knowledge (`unscripted/common_knowledge.py`)

Lewis (*Convention*, 1969) and Aumann (1976) for the definition; Chwe (*Rational
Ritual*, 2001) for the mechanism a game can use.

| Parameter | Value | Basis | |
|---|---|---|---|
| what establishes it | a public moment, not a headcount | Chwe: what makes a moment public is that everybody there watches everybody else take it in | **G** |
| `MIN_WITNESSES` | 3 | Two people talking is mutual knowledge, which is what a conversation already is | **G** (form) |
| `PUBLIC_PRIVACY` | 0.35 | Read from `privacy_level`, which packs already declare | **A** |
| `MIN_QUALITY` | 0.5 | Half-catching something is not what a public event means | **A** |

**It touches no belief.** A public event is one origin, weighed once; treating
publicity as evidence would be the same error as treating repetition as proof. A
test asserts that establishing a public moves no confidence.

## Promises (`unscripted/promises.py`)

| Parameter | Value | Basis | |
|---|---|---|---|
| what a kept and broken promise are worth | trust +0.8/−0.7, liking +0.4/−0.5, reputation "reliable" −0.4 | `SocialExchangeEngine`, which has always known this and had no caller | **A** |
| `DEFAULT_HORIZON_MINUTES` | 2880 | Long enough to act on in a session, short enough that the consequence lands while the player remembers | **A** |
| `KEPT_MARGIN` | 0.002 | See below | **A** |
| `MAX_OPEN_PER_AGENT` | 24 | A bound on save size, not a claim about human nature | **A** |

**How a promise is judged, and why the margin is so small.** Not against the
truth — this runtime holds no ground truth about whether somebody paid. A
promise is kept when *the person it was made to comes to believe it was*, which
is the right answer for a social simulation and not a compromise: reputation has
always been about what people think happened.

The margin is tiny because how far one piece of evidence moves a belief is not a
constant. Measured on `market-square`, the same payment claim moved the promisee
by 0.037 when she was paying attention and 0.0003 when she was not, so any larger
number would silently have meant "and she happened to be listening".

**A studio should not rely on that.** `POST /v2/promises/{id}/settle` is the
authoritative path: when your game knows the player handed over the money, say
so. The belief-based judgement is the fallback for promises nobody settles, and
it models somebody *noticing* rather than a transaction completing.

## Media and notes (`unscripted/medium.py`, `unscripted/notes.py`)

Daft & Lengel, *Media Richness Theory* (1986): media differ in how much they
carry per exchange, and leaner media lose more of what was meant.

| Medium | fidelity | audience | trust factor | |
|---|---|---|---|---|
| in person | 1.00 | the room hears it | 1.00 | **G** (form) |
| phone | 0.72 | nobody overhears | 0.88 | **A** |
| note | 0.88 | nobody overhears | 0.78 | **A** |

Measured: in person loses a detail in 11% of retellings, by telephone 21%.

| Parameter | Value | Basis | |
|---|---|---|---|
| `CONTACT_FAMILIARITY` | 0.45 | Who has whose number, when a pack has not said. A default, not a finding | **A** |
| `notes.INTERCEPT_BASE` | 0.02/hour | Capped at one interception per note. At the first value tried, more notes were intercepted than delivered over a week, which made being read by a stranger the normal fate of a letter | **A** |
| `notes.LIFETIME_MINUTES` | 7200 | Five days: long enough to cross a routine, short enough that a world does not silt up | **A** |

**Where a note loses its detail is different from where a call does.** On a phone
the levelling happens in the telling, so distortion runs at the exchange. On
paper it happens once, at the *writing* — after which the words are fixed, and a
note that says the wrong thing goes on saying exactly the wrong thing to
everybody who reads it. That is the difference between a rumour and a document.

Over a week of `market-square`: 84 notes written, 41 delivered, 28 read by the
wrong person, 11 never collected. **With telephones in the world, none at all** —
the person you want is usually already in your contacts. That is the honest
outcome and it is stated rather than tuned away.

## Pursuit (`unscripted/pursuit.py`)

| Parameter | Value | Basis | |
|---|---|---|---|
| `BASE_INTERVAL_MINUTES` | 180 | Deliberately slow: a cast acting on goals every twenty minutes is frantic, not alive | **A** |
| `min_confidence` | 0.55 | Pursuit is for what you believe, not what you suspect | **A** |
| `worth_a_call` | 0.12 | How much *more* somebody elsewhere must be trusted before the phone beats the room. An absolute floor was the wrong shape — the default trust between strangers is 0.3, so any floor above it turned a market square into a call centre | **A** |
| `worth_writing` | 0.20 | Larger than `worth_a_call`: ringing somebody is easy, writing to them is a decision | **A** |

Measured on `market-square` over thirty simulated days: without pursuit, 54
conversations on days 0–2 and **zero** on days 27–29. With it, 96 and **90**.
