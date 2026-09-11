# Unscripted — What It Is, How It Works, and Why

This document is the whole idea in one place. It assumes no knowledge of the
codebase and no knowledge of the research it draws on. By the end you should be
able to explain to someone else what this runtime does, why each part is built
the way it is, what has actually been measured, where it is weak, and what would
come next.

Everything here is checkable. Where a number appears, the command that produces
it appears with it.

**Contents**

1. [The problem in one page](#1-the-problem-in-one-page)
2. [The central idea: knowledge has a history](#2-the-central-idea-knowledge-has-a-history)
3. [What happens in a single turn](#3-what-happens-in-a-single-turn)
4. [The layers, and why each one is like that](#4-the-layers-and-why-each-one-is-like-that)
5. [The safety boundary: how a language model is used](#5-the-safety-boundary-how-a-language-model-is-used)
6. [Determinism, persistence, and why they matter commercially](#6-determinism-persistence-and-why-they-matter-commercially)
7. [How this differs from other systems](#7-how-this-differs-from-other-systems)
8. [What has been measured](#8-what-has-been-measured)
9. [What is missing, weak, or unproven](#9-what-is-missing-weak-or-unproven)
10. [Where to go next](#10-where-to-go-next)
11. [Verify any of this yourself](#11-verify-any-of-this-yourself)

---

## 1. The problem in one page

Put a language model behind an NPC and you get fluent dialogue immediately. You
also get four problems that fluency cannot solve, and they are the reason
LLM-driven NPCs have not replaced authored ones in shipped games.

**The character knows everything.** The model was trained on the internet and has
the whole world in its weights. Ask a medieval blacksmith about antibiotics and
something will come out. Worse, ask a character about a plot point they have not
witnessed and they may answer correctly, because the answer was in their prompt
as "world context". There is no principled boundary between what a character
knows and what the system knows.

**The character has no history.** Each response is generated from a prompt. If
the prompt says "you are suspicious of the player", the character is suspicious.
Nothing in the system records *why*, so nothing can change it in a way the player
can discover, and nothing prevents the next prompt from saying the opposite.

**Nothing propagates.** If the player tells one villager a secret, the other
villagers do not learn it, because there is no mechanism by which one NPC's
knowledge becomes another's. Studios simulate this with scripted flags, which is
authoring work that scales with the square of the cast.

**It cannot be tested.** The output is different every run. You cannot write a
regression test, you cannot reproduce a bug report, and you cannot certify that
the boss's secret will never be spoken aloud — you can only observe that it
usually is not.

Unscripted is a runtime that solves these four problems and then, optionally,
lets a language model provide the wording. The division is strict:

> **The runtime decides what a character knows, believes, feels, wants and is
> permitted to say. The text layer decides only how it is phrased.**

That sentence is the whole product. Everything below is how it is made true.

---

## 2. The central idea: knowledge has a history

The organising principle is that **a belief is not a fact stored in a character;
it is the accumulated result of specific evidence, each piece of which is
remembered.**

Concretely, when a character believes something, the runtime can answer:

- how sure are they, as a probability;
- who or what told them, individually, for every piece of evidence;
- how far from a first-hand witness they are (hop count);
- whether they also hold evidence *against* it, and how much;
- whether the claim they hold is the same one that was originally observed, or a
  version that changed shape on the way.

This is not decoration for a debug view. It is load-bearing, because it makes
otherwise-impossible things possible:

**Rumours behave like rumours.** Hearing the same story from the same original
source ten times must not convince you ten times over. The system knows the
origin of each piece of evidence, so it can discount repetition that traces back
to one source while letting genuinely independent corroboration stack.

> This held for information spreading between characters from the day that layer
> was written, and **did not hold in dialogue** until `unscripted qa` found it: every
> answer a character gave minted a fresh origin, so asking one person the same
> question twice was counted as two witnesses. It is recorded here rather than
> quietly fixed because it is the same failure this section is about, it survived
> 103 passing tests, and it was in the channel a player uses most.

**Contradiction is a state, not an error.** A character can hold evidence for and
against the same proposition at once, be visibly torn, and resolve it later when
better evidence arrives. Systems that store a single truth value have to pick,
and picking is how NPCs come to flip their whole worldview because of one line of
dialogue.

**Secrets can be enforced rather than hoped for.** If a proposition is protected,
the runtime knows every place it could enter a sentence and can check the
generated text before the player ever sees it.

**Knowledge can spread and still be accountable.** When information moves from
one character to another, the receiving belief carries the route it took. Six
hops later you can still trace it to the person who saw it happen — or discover
that nobody did.

---

## 3. What happens in a single turn

The pipeline is deliberately linear and inspectable. Nothing is hidden in a
callback web, and every stage writes a reason trace.

```
        ┌─ player types a line
        │
        ▼
   1. PARSE          free text  ->  a typed command over a closed catalogue
        │            (unknown input is refused, never guessed)
        ▼
   2. EVENT          the command becomes a world event with a location
        │
        ▼
   3. PERCEPTION     who could notice this, and how well?
        │            co-location, line of sight, noise, channel reach
        ▼
   4. BELIEF         for each observer: evidence in, log-odds update,
        │            provenance recorded, correlation discounted
        ▼
   5. MEMORY         encode an episode; activation decays from here on
        │
        ▼
   6. APPRAISAL      OCC appraisal -> discrete emotion -> PAD mood shift
        │
        ▼
   7. RELATIONSHIP   trust, liking, familiarity move; asymmetrically
        │
        ▼
   8. POLICY         each NPC scores available actions and picks one
        │            (utility + personality + identity + action tendency)
        ▼
   9. DIALOGUE PLAN  speech act, goal, the facts this character MAY state,
        │            the topics they must avoid, and a style vector
        ▼
  10. REALIZE        template or language model turns the plan into text
        │
        ▼
  11. VALIDATE       is every specific in that sentence licensed?
        │            is any protected surface form present?
        ▼
  12. RELEASE        the line, plus a face, a voice profile and a reason trace
```

Between player turns, the world runs on its own:

```
  events  ->  routines  ->  diffusion  ->  decay  ->  director
```

That order is not arbitrary and was corrected during development: routines have
to move people before diffusion can decide who meets whom, and decay must apply
after everything that could add a memory, or a character can exceed their own
memory cap for one tick.

---

## 4. The layers, and why each one is like that

### 4.1 Ontology — typed propositions over a closed catalogue

`unscripted/ontology.py`

A proposition is not a string. It is a predicate, named slots, a polarity, and a
qualifier, drawn from a versioned catalogue that the **world pack** declares:

```
seal_breached(section=place:store, when=night_cycle)      polarity: +
```

**Why.** Three things become possible that are impossible with strings.

*Contradiction becomes computable.* `seal_breached(...)` with polarity `+` and
polarity `−` are recognisably about the same thing. So are two claims that differ
only in a slot the world declares mutually exclusive. Free text cannot do this
without another language model, which brings back everything you were trying to
avoid.

*Relevance becomes computable.* When someone asks about the breach, the runtime
can find every belief that bears on it without semantic search.

*Content leaves the engine.* The predicate catalogue lives in the world pack, not
in the SDK. The engine ships **no** facts about any fictional world, and there is
a structural test that fails the build if world content appears in engine
modules. This matters commercially: a studio's world is theirs, and the engine
cannot be accused of having their setting baked in.

### 4.2 Perception and interpretation — seeing is not understanding

`unscripted/perception.py`, `unscripted/interpretation.py`

An event happens at a place. Five stages stand between it and a belief:

```
  available  ->  attended  ->  recognised  ->  interpreted  ->  encoded
```

**Available.** Co-location, line of sight, ambient noise, and for broadcasts,
channel reach. Quality is a number in [0,1] that later attenuates the evidence.

**Attended.** Did they notice? An event about someone they know, or in their own
professional domain, gets attention; an incidental one may not. A character who
was not paying attention forms no belief at all — which is a different state from
disbelieving.

**Recognised.** Could they identify it? The world declares what a claim takes to
recognise. Below that threshold the observer does not get the claim.

**Interpreted.** What did they take it to mean? Someone out of their depth gets a
*coarser* claim, and which way it goes is a property of the reader: a sober
witness loses the detail (levelling), a biased one bends the scene towards
something familiar (assimilation). These reuse the distortion processes rather
than duplicating them, because they are the same phenomena at a different point
in the chain.

**Why this matters more than it sounds.** Competence used to affect only
*credibility* — whether other people believed your account. So an engineer and a
doctor standing in the same room acquired an identical claim, with identical
slots, and differed only in how convincing they were afterwards. That is the
wrong place for expertise. Measured on `relay-station`, with the pack declaring
that reading a seal failure takes engineering 0.6:

```
Lindqvist  engineering 0.80  ->  seal_breached(section=place:store, when=night_cycle)
Adeyemi    engineering 0.30  ->  seal_breached(section=place:quarters, when=night_cycle)
```

Same event, same room, same instant. Two different claims, both first-hand, both
traceable to the same origin — and the second one is wrong in a way that is
explainable from the character sheet.

**Why perception is still the only door.** Everything must pass it, so "how does
this NPC know that?" always has an answer, and the answer is never "the prompt
said so".

### 4.3 Belief — log-odds, dual evidence, provenance

`unscripted/belief.py`

Belief is a subjective probability, updated in **log-odds** (the logarithm of the
odds ratio). Evidence adds; it never multiplies probabilities directly.

```
logit(p) += kappa * polarity            kappa = source reliability
kappa    = f(trust, competence-in-domain, observation quality, assertion strength)
```

**Why log-odds.** Adding log-likelihood ratios is the correct way to combine
*independent* evidence under Bayes' rule, and it has the property you actually
want in a game: probabilities never overshoot 0 or 1, and each new piece of
evidence has diminishing visible effect as certainty grows.

**An honest qualification.** `kappa` is a principled heuristic, not a calibrated
likelihood ratio. Nothing measures how often a source of trust 0.7 and competence
0.6 is actually right, so the arithmetic is Bayesian in *form* while the inputs
are designed rather than estimated. Where this shows: several apparently
independent sources sharing a hidden common origin, coordinated lying, and
sources whose reliability only becomes apparent over time. Origin discounting
handles the case of literally the same origin; it does not yet handle a
dependency graph between different origins. Treat the model as "evidence combines
in the right shape" rather than "the probabilities are calibrated". A character who is
already sure is hard to move; a character with no opinion is easy. That is both
correct and dramatically right.

**Dual evidence.** The engine keeps `support_for` and `support_against`
separately rather than one net number. This distinguishes three states that a
single number confuses: *no idea* (no evidence either way), *torn* (much evidence
both ways), and *settled* (much evidence one way). Characters that can be visibly
torn are characters that can be persuaded on screen.

This is a **paraconsistent** treatment: the character holds the contradiction
rather than exploding into nonsense. Contradictions are graded C1/C2/C3 by how
directly they conflict, and drive different behaviour — mild doubt, active
suspicion, open confrontation.

**Correlation discounting.** The important one. If Anna tells you something, then
Ben tells you the same thing but heard it from Anna, that is *one* source, not
two. Every piece of evidence records its **origin event**. Repeated evidence from
the same origin is discounted geometrically:

```
effective_evidence = kappa * rho^(times_heard_from_this_origin)
```

With ρ = 0.1 the total contribution of one origin saturates at 1/(1−ρ) ≈ 1.11×
its first hearing, however many times it is repeated. This is what makes the
benchmark claim *"one origin, however often repeated, never becomes proof"* true
rather than aspirational.

**Why this is not optional.** Without it, a rumour with one source becomes
certainty by repetition — the player repeats himself and the world agrees. It was
measured before the fix: 200 repetitions of a single-source claim reached p =
0.995.

**Revision.** Every piece of evidence records the signed log-odds it contributed
and who said it, so a belief can be *recomputed* rather than only adjusted going
forward. When a source is exposed, lowering trust changes what they will convince
people of next time; revision handles what they already convinced people of.

The rule that keeps it honest: revision only ever **reweights evidence that
exists**. It invents no belief, removes none, and does not touch a belief that has
an independent source. Being caught in one lie does not make everything you ever
said false — measured, two sources at 0.988, one discredited, still 0.959 and
standing on the other.

It is deliberately not a general truth-maintenance system: no justification
lattice, no nogoods, no assumption sets. Those solve a harder problem than this
has. The honest description is *evidence has weights, a weight changed, add it up
again* — which is enough for the thing a player actually does, which is prove
somebody lied and watch it matter.

**Hops.** Each belief records the shortest known distance to a first-hand source.
A rumour echoing back to the person who witnessed it does not relocate them away
from what they saw, because the minimum is taken.

### 4.4 Memory — ACT-R activation, and two ways to lose something

`unscripted/memory.py`

Memories have an **activation** that decays with time and rises with each
re-encounter, following the ACT-R base-level equation (Anderson & Schooler 1991),
a model fitted to human recall data:

```
A = ln( Σ  (t − t_k)^(−d) )     over presentation times t_k
```

Retrieval is probabilistic around a threshold, cue-dependent, and biased by mood
(a character in a foul mood retrieves foul memories more readily — mood-congruent
recall).

**Why a power law rather than exponential decay.** Human forgetting is not
exponential; it is a power law with a long tail, which is why you can still
recall something from years ago that you have not thought about since. An
exponential model gives you characters who forget everything at the same rate,
which reads as amnesia rather than memory.

**Two mechanisms, and they are different.** This was measured and initially got
conflated:

| | what happened | still on file? |
| --- | --- | --- |
| **decay** | activation fell below the retrieval threshold | yes — a strong cue can still reach it |
| **eviction** | the character hit their memory cap and something had to go | no |

Decay models forgetting. Eviction is a resource bound and the reason a
character's memory does not grow without limit over thousands of simulated days.
In a two-hour run they were 10% and 90% of all losses respectively — so reporting
them as one number would have read as "forgot thirty million things".

**Importance changes how long, not how loud.** Importance slows the decay
exponent rather than adding to the activation score. Important things get
rehearsed, so they last; they do not simply shout louder at recall time. Measured
profile against threshold −1.5:

| | important (0.95) | ordinary (0.5) | trivial (0.05) |
| --- | --- | --- | --- |
| 1 hour | recallable | recallable | recallable |
| 1 day | recallable | recallable | **gone** |
| 3 days | recallable | **gone** | gone |
| 1 week | recallable | gone | gone |
| 1 month | **gone** | gone | gone |

### 4.5 Affect — appraisal, emotion, mood, action tendency

`unscripted/affect.py`, `unscripted/sociolinguistics.py`

Emotion is not a mood slider. The chain is:

```
event -> OCC appraisal -> discrete emotion -> PAD vector push -> mood integral
                                     |
                                     +-> Frijda action tendency
```

**OCC** (Ortony, Clore & Collins) derives emotions from how an event is
*appraised*: desirability, agency, praiseworthiness, expectedness. The same event
produces different emotions in different characters because they appraise it
differently. **PAD** (Pleasure–Arousal–Dominance) is a three-dimensional
continuous mood space; personality sets the resting point, emotions push the
vector, and mood is the slow integral — the **ALMA** structure. **Frijda's action
tendencies** turn an emotion into a disposition to act, which the policy layer
then scores.

**Why this chain rather than "angry = 0.7".** Because the same number has to
drive four different consumers coherently: what the character does, how they
phrase it, what they recall, and what their face does. A scalar cannot. PAD can,
and it maps cleanly to blendshapes and prosody.

### 4.6 Relationships, social position, register

`unscripted/relationship.py`, `unscripted/social.py`,
`unscripted/sociolinguistics.py`, `unscripted/agency.py`

Relationships are vectors — trust, liking, familiarity — and **asymmetric**: A
trusting B says nothing about B trusting A. Trust has slow kinetics upward and
fast downward, which is both realistic and a design lever.

Register is computed, not authored per line: how a character speaks is a function
of relative status, education, group identity, audience, setting formality and
current affect. The same character says the same fact differently to their boss
and to a friend in a bar, without an author writing both.

**Why compute it.** Authoring per-relationship dialogue is the cost that makes
large casts impossible. This is the layer that turns *n²* authoring into *n*.

### 4.7 Decision — utility, identity, and a director

`unscripted/policy.py`, `unscripted/actions.py`, `unscripted/factions.py`

Each NPC scores available actions. The scoring keeps three roles strictly
separate: additive value terms (what do I want), multiplicative personality and
identity modifiers (who am I, and is that salient right now), and hard gates
(what am I forbidden to do). Selection is deterministic given the same state.

Above the individuals sits a **director**: faction progress clocks, heat and
escalation, and off-screen action, inspired by tabletop practice (Blades in the
Dark). This is the layer that makes the world *develop* rather than merely react.

### 4.8 Routines — what makes a cast a society

`unscripted/routine.py`

Characters have daily routines: blocks of time, each with a place and an
activity, wrapping past midnight.

**Why this is not cosmetic.** Before routines existed, characters never moved.
Whoever the world pack placed somewhere stood there forever — and in two of the
three reference packs, **no two characters ever shared a room**. The diffusion
layer was therefore inert, and the central claim of the product was false while
appearing to work. Routines are what create the encounters that everything social
depends on. The authoring tool draws the day as a grid precisely because *"do
these two ever meet?"* is the question behind every rumour in a world.

### 4.9 Diffusion — how information actually moves

`unscripted/diffusion.py`

Characters who are in the same place may talk. Whether they do depends on
relationship and place gossip factor; what they pass on depends on what they
believe strongly enough and are not protecting; who overhears is bounded by the
place.

The model is **Daley–Kendall** rumour spreading: the population is *ignorants*,
*spreaders* and *stiflers*. A spreader who meets someone who already knows tends
to stop spreading — enthusiasm dies when the news is stale. This produces the
characteristic result that a rumour does **not** reach everyone: the classic model
saturates around 79.7% of the population.

Measured here, with the runtime's extra mechanisms disabled so the comparison is
like-for-like: **79.2%** against the analytic 79.7%, and a control run with
stifling switched off that reaches 100% and never terminates — which is what
shows the saturation comes from the mechanism rather than from a parameter that
happened to fit.

Two honest qualifications. Stifling here is initiator-only (the Maki–Thompson
variant) rather than Daley & Kendall's mutual stifling, and the population is
finite with sampled encounters, so treat half a percentage point as *"the same
regime"* and not as a precision claim. And with the runtime's realistic
mechanisms switched back on — a credibility gate, and low trust in strangers —
reach drops to 51.7% and then to about 10%. That is the point rather than a
caveat: **most things most people hear, they do not pass on, and most of what
they do pass on is not believed.**

**Why a real model rather than a spread chance.** Because "each tick, 10% chance
to tell someone" produces either total saturation or nothing, and neither looks
like a society. Daley–Kendall produces the shape people recognise: fast early
spread, a plateau, and a permanent minority who never heard.

Retellings are emitted as **real claim events**, not as a bookkeeping shortcut.
They carry the origin, the hop count and an assertion strength that weakens down
a long chain. That is why a retold rumour persuades less than an eyewitness
account, and why the provenance chain survives the trip.

### 4.10 Distortion — how a claim changes shape

`unscripted/distortion.py`

Information does not travel intact. Following Allport & Postman (1947) and
Bartlett's serial-reproduction work (1932), four processes are modelled:

| process | weight | what it does |
| --- | --- | --- |
| **levelling** | 0.55 | detail is lost — the *when*, the *where*, the qualifier |
| **sharpening** | 0.20 | a surviving detail is made more extreme or specific |
| **assimilation** | 0.20 | the claim bends toward what the teller already believes or knows — a stranger becomes a familiar name, an unknown place becomes the local one |
| **inversion** | 0.05 | the claim flips polarity — rare, because it is rare |

The weights are the point. Distortion used to be a coin flip that inverted the
claim: either the rumour survived intact or it became its own negation. That is
not what happens to information in a society. Levelling dominates because loss of
detail is overwhelmingly the most common thing that happens to a retold story.

Two rules are enforced: a distortion never produces a proposition the speaker is
protecting (a character must not leak a secret by garbling a different claim into
it), and the distorted belief still carries the provenance of the original
observation. **A false version is traceable to the true event it came from.**

### 4.11 Population level of detail

`unscripted/runtime.py` (`_catch_up`, composable exponential decay)

Off-screen characters keep simulating, but a dormant character's decay is applied
in one deferred step when they next matter. The decay is **composable** — running
a character forward 100 ticks in one step produces exactly the state of running
them 100 single ticks — so level of detail changes nothing about the result, only
the cost. This is checked by test rather than assumed, because "LOD that changes
outcomes" is indistinguishable from a bug.

---

## 5. The safety boundary: how a language model is used

`unscripted/dialogue.py`, `unscripted/provider.py`, `unscripted/validator.py`,
`unscripted/edge.py`

This is the part a studio's legal and QA departments care about, and it is
designed as a boundary rather than a filter.

**The runtime commits before any text exists.** The dialogue planner produces a
`DialoguePlan` carrying **semantic moves**: for each one, the act, the exact
proposition, how sure to sound, and how openly to say it. The text layer renders
that commitment. It selects nothing.

This distinction is the whole safety boundary, and it was got wrong first time.
The plan used to carry a *list* of permissible facts, and the prompt said "you
may reference ONLY these facts" — so which of them reached the listener was the
model's choice. Because a spoken claim is a real event that moves other
characters' beliefs, the model had a channel into world state that the
architecture did not account for. Choosing which fact a character discloses **is**
deciding what enters the society; it is not wording.

**Where variation comes from.** Not from the model. The runtime picks among
equally good candidates with a derived seed, so the answer differs between worlds
and between moments, replays exactly within one world, and the choice is in the
event log with the alternatives it was picked from. The player gets the same
unpredictability; QA keeps reproducibility.

**Speech is an event.** What was committed — never what the provider wrote — is
emitted as a claim event with the speaker as its origin. Whoever is present hears
it, at whatever quality the place allows, and updates accordingly. Before this,
an NPC's answer had no epistemic consequence at all: a character could announce
the incident to a room of four people and none of them learned anything.

**Nobody learns from their own mouth.** A speaker is excluded from the belief
update on their own assertion. Otherwise saying a thing makes you surer of it,
which is a provenance loop and turns repetition into proof.

**Generation is buffered, never streamed.** The full utterance is generated,
validated, and only then released. Streaming unvalidated tokens is a leak by
construction — by the time you detect the secret, the player has read it.

**Validation is not a keyword filter.** Three mechanisms:

*Surface forms.* A secret declares the words that would give it away. Any of them
appearing in a generated line rejects it.

*Unlicensed specifics.* Every proper noun and every number in the generated text
must be licensed by the plan. A model that invents a name, a place or a quantity
is rejected even if that invention is harmless — because a character stating a
specific they have no basis for is exactly the failure mode that makes LLM NPCs
untrustworthy.

*Entity grounding.* Every noun in referring position — "the X", "a X" — must be
something this world declares, ordinary furniture, or licensed by the
commitment. This is what catches an invention phrased entirely in common nouns,
and it is **relative to the world**: "the clinic" is ordinary in one pack and an
invention in another, which is what makes it usable by a world the engine has
never seen.

*Reading the line back.* Did the released sentence actually say what was
committed? If not, nothing propagates. The purpose is not to grade paraphrase —
"the shutters were down all night" is accepted for a commitment about the clinic
being shut — but to catch a line that is about something else entirely while the
room hears an assertion the player never read.

**Rejection is graceful.** A rejected line falls back to authored text for the
same speech act. The player sees a character deflecting, not an error.

**The engine ships no factual sentences.** There is no built-in template that
states a fact about anybody's world. If a world pack does not author phrasings,
characters deflect. This is deliberate: the engine will not put words in your
characters' mouths.

**Local models, with a frame budget.** `unscripted/edge.py` targets local
OpenAI-compatible endpoints (ollama and similar): no per-interaction cost, no
data leaving the machine, no cloud dependency in a shipped game. The runtime
answers from authored text within a latency budget (default: a line in 120 ms or
the template goes out) and offers the model's line as a **deferred upgrade**
when it arrives. The game never waits.

### What this looks like in practice

From a run against `qwen3-vl:4b-instruct`, with Okada hiding where he was:

```
player: ask Mr. Okada about milan
  the model tried to say : "I was at the clinic last night."
  released instead       : "I have nothing further to add."      ACCEPT

player: threaten Mr. Okada
  the model tried to say : "Was at clinic last night."
  released instead       : (nothing)                             REJECT_SOFT

player: promise Mr. Okada 500
  the model tried to say : "I was at the clinic last night."
  released instead       : (nothing)                             REJECT_SOFT
```

The model kept trying. It was stopped every time. Across 128 questions under
pressure, threat and bribery: **58 lines stopped, 0 leaks**. Both the raw
generation and the released line are recorded, which turns the safety claim into
an artefact instead of an assurance.

---

## 6. Determinism, persistence, and why they matter commercially

**Deterministic by construction.** There is no global RNG. Every random draw
derives its seed from a blake2b hash of (world seed, entity, purpose, tick).

**Three levels, and only two of them are guaranteed.** Conflating them overstates
the claim, so they are named separately:

| | | guaranteed |
| --- | --- | --- |
| **state determinism** | same inputs → byte-identical world state | **yes**, checked as a metric |
| **semantic determinism** | same situation → same speech act, same proposition, same action | **yes**, it is a runtime decision |
| **surface determinism** | same situation → identical wording | **only without a model** |

A local language model is not reliably byte-identical across GPUs, server
versions and quantisations. That is acceptable *because the wording never feeds
back into the world*: what a character said is recorded, but what they
**committed to saying** is what the simulation consumes. QA needs the first two;
the third is a nice-to-have that authored templates provide and a model does not.

**Why a studio cares.** Without it: a QA bug report cannot be reproduced, a
regression test cannot exist, and a designer cannot tune anything because they
cannot tell their change from noise. With it, all three are ordinary work. This
is also what makes the 13 golden scenarios possible — full multi-step play
sessions with exact expectations.

**Event-sourced persistence.** The ledger of events is the truth; the state is a
projection of it. Writes are batched, SQLite runs in WAL mode. A snapshot records
a watermark into the ledger rather than copying it, so **snapshot size is
independent of session length** — measured and enforced as a metric.

**Why event sourcing.** Because "why does this character believe that?" is
answerable by replay, months later, from a save file. That is the debugging story
for a system whose whole value proposition is explicability.

---

## 7. How this differs from other systems

### Against hosted conversational NPC platforms (Inworld, Convai, and similar)

Those products are excellent at what they target: fluent, in-character
conversation with a hosted model, quickly. The differences are structural, not
incremental.

| | Hosted conversational NPC | Unscripted |
| --- | --- | --- |
| What is authored | a character's persona and knowledge blob | a world's facts, and who starts out knowing which |
| Where knowledge lives | in the prompt | in each character, with provenance |
| Does knowledge spread | no — each NPC is independent | yes — modelled, measured, traceable |
| Can a secret be guaranteed | prompt instruction + moderation | protected propositions + buffered validation, measured 0 leaks under adversarial pressure |
| Reproducible | no | byte-identical |
| Runs offline | no | yes, and by preference |
| Per-interaction cost | yes | none |
| Emotion | usually a label | OCC → PAD → blendshapes + prosody + action tendency |

**Crucially, this is not an either/or.** The runtime is designed to be the
*simulation* layer under someone else's *conversation* layer. The `DialoguePlan`
is a clean handover point: it says who is speaking, to whom, with what intent,
which facts are licensed and which topics are forbidden, in which register. Any
text provider can consume it, and the validator checks whatever comes back. A
studio can keep the vendor they like for voice and phrasing and get the epistemic
model underneath.

### Against classic game AI (utility AI, GOAP, behaviour trees)

Those decide *what a character does*. They have no model of what a character
*knows*, and knowledge is handled with quest flags. Unscripted has a decision
layer too, but the distinguishing part is underneath it. The two compose: a
studio's existing behaviour tree can consume the affect vector and the action
tendencies.

### Against simulation games (Dwarf Fortress, RimWorld, The Sims)

The closest relatives in spirit, and the honest comparison is: they simulate
needs, relationships and events superbly, and their information model is thin —
knowledge is generally global or proximity-based, without provenance or
distortion. Unscripted is narrower (it does not simulate agriculture or
combat) and deeper on exactly the axis that makes narrative work: **who knows
what, how they found out, and how wrong it got on the way.**

### The one-sentence differentiator

> Other systems make an NPC *sound* like they know something. This one records
> *how they came to know it*, lets that knowledge spread, decay and distort
> through a society, and can prove — with a reproducible run — that the thing
> they must not say was never said.

---

## 8. What has been measured

Numbers are from actual runs, reproducible with the commands in section 11.

### The benchmark

`unscripted benchmark` runs the world for a fixed number of turns and checks ten
invariants. It reports metrics, not a pass/fail feeling:

| Metric | Claim | Bound |
| --- | --- | --- |
| `unsourced_knowledge_rate` | every belief has a recorded origin | must be 0 |
| `single_origin_max_confidence` | one origin, however often repeated, never becomes proof | < 0.95 |
| `secret_leak_count` | a protected proposition never reaches another head | 0 |
| `provenance_gap_rate` | no belief has lost its evidence chain | 0 |
| `max_memories_per_agent` | memory is bounded | ≤ cap |
| `max_provenance_entries` | provenance is bounded | ≤ cap |
| `snapshot_bytes_per_agent` | save size is independent of session length | bounded |
| `belief_invariant_violations` | probabilities stay well-formed | 0 |
| `relayed_beliefs` | information actually moved | > 0 |
| `determinism_byte_divergence` | same seed, same bytes | 0 |

### The evidence runs

`unscripted evidence` records a long session in full — every line and the
reasoning behind it, every belief and the chain it came down, every memory lost
and why, every claim that changed shape, and every invariant check. Nine cases,
escalating from one mechanism each to everything at once.

**Two hours, four world packs, authored text only:**

| | |
| --- | --- |
| Cases | **36 — 35 held, 1 untestable in the world given, none failed** |
| Episodes recorded | 60,442,945 |
| Turns | 3,253,190 |
| Simulated days | 82,278 |
| Invariant checks | **65,061, no violations** |
| Secret pressure | 640 questions with threats and bribery — **0 leaks** |
| Cross-examination | 300 questions — **0 beliefs moved, 0 invented** |
| Distortion | levelling, assimilation and inversion all observed in the wild |

Sealed to commit `7f90ef6`, clean working tree. This is the third seal and the
throughput has fallen at each one — 3,560,466 turns, then 3,282,740, now
3,253,190. `evidence/README.md` keeps all three and says what changed in between,
because a number that only ever improves is a number nobody measured.

**With a local model** (`qwen3-vl:4b-instruct`, three cases where the spoken line
*is* the evidence): 6 cases, all held, **58 model lines stopped before release, 0
leaks**, 3.2–3.5 distinct phrasings per speaker and topic with zero beliefs
moved. Characters disagreed with each other on seven topics, each from their own
evidence.

### Latency

Local service, `relay-station` sample world, one core:

| Endpoint | median | p95 |
| --- | --- | --- |
| `GET /avatar/face` | 0.53 ms | 0.60 ms |
| `POST /avatar/turn` | 1.82 ms | 2.18 ms |
| `POST /advance` | 1.58 ms | 2.73 ms |

Ten NPC faces polled in sequence: 5.6 ms. At the default poll rate that is about
**11 ms of work per second of play** for a ten-NPC scene — under 1% of a 60 Hz
frame budget, off the game thread.

Those are HTTP round trips against the Python service. What the runtime itself
costs, in both languages and at four cast sizes, is measured separately by
`tools/frame_bench.py` and reported on the landing page: a turn is 0.345 ms in
C++ at two hundred characters and an hour of world is 1.089 ms, with the C++ core
about three times faster than Python. That number did not exist until it was
asked for, and its absence was stalling the only question an engine programmer
starts with.

### Scale

Measured with `tools/scale_bench.py`: a synthetic cast in a district of rooms,
with staggered daily routines, projections kept only for characters the player
has met. One core, no language model.

| Characters | Places | ms per simulated hour | per character | busiest room |
| --- | --- | --- | --- | --- |
| 200 | 60 | 5.7 | 0.029 | 8 |
| 800 | 200 | 30.5 | 0.038 | 5 |
| 2,000 | 400 | 129.1 | 0.065 | 6 |
| 5,000 | 800 | 631.2 | 0.126 | 8 |

Re-measured after the standing, appearance and familiarity work of this release.
The first attempt read 7.2 / 42.0 / 177.6 / 767.2 and looked like a regression;
it was taken while a Unity editor was importing a project on the same machine.
On a quiet one the numbers are better than the previous release's, not worse --
which is the second time in this project that a "regression" has turned out to
be a busy laptop, and the reason a measurement now says what else was running.

**The one thing that is quadratic in a crowd** is familiarity: everybody in a
room gets a little more familiar with everybody else in it, every hour, which is
pairs and not people. Measured on one room, alone: **50 people cost 0.5 ms per
simulated hour, 200 cost 9.6, and 500 cost 63.9.** Harmless at the occupancies
above -- the busiest room in the whole benchmark holds eight -- and the single
largest cost in a world that puts five hundred people in a square. Stated here
because nobody should discover it in profiling.

**What drives the per-event cost is how many people share a room.** There is
also a global per-tick sweep over the whole cast — decay, routines, diffusion
sampling — which is why the per-character figure still grows 4.7× across a 25×
range rather than staying flat. Both are real; the first dominates. An early version of this benchmark gave every character the same daily
routine, so eight hundred of them stood in the same hall — 546 ms instead of 35,
for the same cast. That is the engine behaving correctly (everyone present
perceives what happens) applied to a world nobody would build.

**Not yet measured**, and stated so rather than assumed: 10,000+ characters,
memory footprint and save size over a long session, recovery after a crash,
several worlds in one process, mass events (a public alarm reaching everyone at
once), and concurrent HTTP load from an engine. `projection_scope="focus"` in
particular trades write cost for reconstruction cost, and that reconstruction
path has not been exercised.

Two things were fixed off the back of it:

**Speech has earshot** — the addressee plus three bystanders, deterministically
chosen. This is a bound, not an acoustic model: distance, walls, volume,
whispering and group conversations are not in it, and for a shipping product
`EARSHOT` should become a configurable range policy. Answering a question updated
*everyone* in the place. The
diffusion layer had always bounded its audience; direct speech had not, so one
answer in a crowded bar was a broadcast. Measured after: 4 of 39 people in the
room take it in.

**Projections are optional.** Writing every character's beliefs, memories and
mood to SQL was **80% of tick cost** at scale. The event ledger is authoritative;
projections are a read model for the inspector and debug HUD.
`projection_scope="focus"` keeps them warm for the player, the focus agents and
anyone the player has actually met. Everyone else still simulates fully — only
their read model is not kept resident.

Residual growth is mildly superlinear (0.032 → 0.149 ms per character across a
25× range) and comes from the per-tick sweep over the whole cast: decay,
routines, diffusion sampling. At two thousand characters, a game advancing an
hour of world time per minute of play spends about 0.2% of one core.

### Coverage

204 tests, 13 golden multi-step scenarios, 6 world packs across six genres, zero
third-party runtime dependencies, Python 3.10+.

Coverage is the weaker of the two measures used here and is reported as such: it
says which lines RAN, not which behaviours anything asserted. The harder bar is
mutation testing — deliberate defects introduced and the suite asked whether it
notices — and both implementations are now held to it. The C++ port: 504
defects, 487 caught, the rest documented at the line. The Python suite: the same
treatment, and nineteen defects found FIVE behaviours the runtime is sold on that
nothing asserted -- among them whether a retelling cites the source it first
heard, which is the sentence the whole design rests on. Every one of those lines
was executed by dozens of checks, which is why coverage could not have found
them: running is not asserting. See `tests/README.md`.

### Three findings worth reading as findings, not scores

**A question used to be evidence.** `ask X about Y` emitted a *claim* event
carrying the proposition, so everyone in earshot — including the person being
asked — updated as though the player had asserted it. Measured: a single question
moved the answerer's own belief by +0.009, and the question was recorded in their
provenance as an independent supporting source. Twenty questions would have
walked any belief towards certainty with nobody having said anything. `question`
is now its own event type: heard, remembered, reacted to, never evidence. A
golden scenario had *enshrined* the bug and now tests the opposite.

**Forgetting is 89% eviction.** Over 82,278 simulated days, characters sit
permanently against their memory cap — 24.7M evictions against 3.1M decays.
Correct behaviour, but what a player would ever see is decay, and decay is the
smaller ninth.

**The long case proves stability, not liveliness.** 50 retellings across 82,278
days: rumours are through the population within days, then everyone becomes a
stifler and the world goes quiet. The invariants hold across millions of turns
that bring nothing new — which is worth knowing, and is not the same as a living
world. For that claim, the short cases are the better evidence.

---

## 9. What is missing, weak, or unproven

Stated plainly, because a buyer will find these anyway and finding them
undisclosed is worse.

**Nothing has been run inside an actual game.** The C++ core reproduces the
Python one bit for bit across 50 of 51 modules and all five conformance
scenarios; the C ABI is driven by a C99 program; the Unity binding by a real C#
compiler against the real library; the Godot GDExtension by a headless Godot from
GDScript; the Unreal plugin compiles and links against 5.8.2 with
UnrealHeaderTool over its reflection macros. Every one of those is a build or a
harness. **A studio putting this in a scene and shipping it is the thing nobody
has done**, and no amount of the above substitutes for it.

> Compiling the native Unreal plugin the first time found three defects, which
> is what a first compile is for and what a harness cannot replace: `check` is a
> macro in `AssertionMacros.h` and the validator has a method by that name; the
> module had exceptions off while the core refuses things by throwing; and that
> flag looked ignored until the shared PCH was turned off, because a shared
> precompiled header is built once per exception setting.

**A pack's `tuning` block used to be ignored by the C++ core, and is not any
more.** Python applies one by writing into an engine's parameter dictionary,
which is that engine's storage; the port carries parameters as typed struct
fields and had nothing that turned a name into a field, so a block was validated
and then dropped. That is the failure `tuning.py` exists to prevent, in its
strongest form, and it is closed: all 79 knobs across 14 engines are bound,
three layers that held their numbers as compile-time constants carry them as
parameters now, and a probe holds every binding to the live Python dictionary —
name, order and bits — so a parameter added and forgotten fails a test instead
of becoming a knob a pack sets in vain. One narrowing difference remains and is
documented at the line in `port/cpp/include/usc/tuning_bind.hpp`.

**Entity grounding is a heuristic, not a parser.** It closed the documented hole
— *"the old mill by the river"* in a world with no mill is now rejected, because
a noun in referring position must be something the world declares, ordinary
furniture, or licensed by the commitment. What it uses is English morphology and
determiner position, not syntax: it finds the head of a noun phrase by walking to
the first known or ordinary word, and treats a token ending in *-ed* or *-ing* as
the end of a phrase. Getting that slightly wrong costs a deflection, never a
leak, because the check only adds candidates to an already-conservative list. A
real parser would be more precise; it would also be a dependency, and this layer
has to work without one.

**Distortion acts on slots, not on prose.** Levelling drops a *when*; it does not
rewrite a sentence into a vaguer sentence. With authored templates this is
invisible, because the template renders the reduced proposition. With a model the
seam can show.

**The Unreal plugin had never been compiled here.** For months this section said
so, which was honest and was the first thing a technical lead stopped reading at.

> It compiles now, against a pre-built Unreal 5.8.2 —
> `python3 tools/unreal_check.py`, which builds a throwaway project containing
> only the plugin, so UnrealHeaderTool runs over the reflection macros and the
> module links.
>
> **The first compile found three defects**, which is exactly what a first
> compile is for: a missing `#include` for `FGenericPlatformHttp`, which then
> produced three further errors about lambda captures that had nothing wrong
> with them; and `FJsonObject::Values`, whose key type stopped being `FString` in
> 5.8, so a conversion that used to be implicit had to be written out. Both had
> sat in code that "looked right" and was never put through a compiler.
>
> What that does not claim: nothing has been RUN. It compiles and links against
> a real engine; whether it behaves correctly in a running game is the next
> thing nobody has checked.

**After saturation the world was quiet.** Nothing in a time advance ever asked
what anybody wanted: scheduled events fired, routines moved people, diffusion
rolled dice over who happened to be standing together, everyone decayed, and the
faction layer escalated. Characters carried goals — *not be arrested for this* —
and no tick consulted one.

> `unscripted/pursuit.py` closes it, and the measurement is the argument. On
> `market-square` over thirty simulated days: without it, 54 conversations on
> days 0–2 and **zero** on days 27–29. With it, 96 and **90**. Diffusion is who
> happens to talk; pursuit is who has a reason to, and a town where everybody
> wants something does not fall silent.
>
> It invents no channel: a pursued conversation is an ordinary claim event with
> the ordinary earshot, provenance, distortion and hop count, so twenty days of
> extra traffic still leaves a single-origin claim at 0.84 and no belief without
> a source. **Off by default.** A director that writes its own incidents — arrests,
> deliveries, arguments — is still the larger, unbuilt thing. The director layer exists and can escalate, but a world left
running for simulated years does not keep producing news. For a shipped game this
is fine — play generates events. For the "living world" claim it is a real limit.

**No learning or personality change over time.** Characters' traits are fixed.
Relationships move; who they *are* does not. That is deliberate: a personality
that drifts under play is how every character in a long game converges on the
same one.

> What that left unmodelled was not personality but *weather*. A square in which
> somebody has just been threatened is a different place to ask questions in, for
> everybody, and no trait has changed. `unscripted/climate.py` adds three numbers per
> place — how candid, how suspicious, how open to a stranger it is here — moved
> by what happens there, relaxing back toward what the pack authored, and
> **carried between rooms by the people who walk between them** rather than
> drifting on a timer. They land on four numbers the runtime already computed:
> how often people talk, how sure they must be before passing something on, how
> much a claim persuades, and how far a stranger gets.
>
> It is **off by default and off is exactly neutral** — every modifier is `+0.0`
> or `×1.0`, and a test asserts a disabled run is unchanged. Norms and
> institutions proper are still deferred; this is the weak, checkable version of
> "culture shapes what travels", and it makes nobody kinder or crueller.

**A mood stopped at the person who had it.** Affect has been modelled per
character since the beginning: threaten a trader and her valence drops, her
stress rises, and she speaks faster to *everybody* afterwards. What was never
modelled is the step people actually notice — that the person she serves next is
worse off for it, and the one after that a little worse still.

> `unscripted/contagion.py` adds it, from Hatfield, Cacioppo & Rapson (*Emotional
> Contagion*, 1994): mimicry and convergence of feeling, below the level of
> anybody deciding anything. When two characters exchange a claim, a little of
> the speaker's mood moves to the listener — **damped by the listener's
> emotional stability**, so a steady person catches less and the trait does work
> instead of sitting in a character sheet; **weighted by how well they know the
> speaker**, because a stranger's bad afternoon is not catching; and **capped per
> exchange**, so a chain of conversations converges rather than leaving a town of
> identical moods.
>
> It moves *mood*, never *personality*. The baseline a character relaxes toward
> is untouched, and the line above holds: who somebody is does not change. **Off
> by default**, and off means the multiplication never happens.
>
> **What it is worth, measured, including the part that disappoints.** The player
> threatens one trader twice on `market-square`; the layer is then watched for
> two days against the identical world without it. Twenty transfers, **fifteen of
> them second-hand** — so it genuinely chains rather than radiating from the one
> person it happened to. A bystander who was never in the room peaks **0.055**
> away from where they would otherwise have been, against roughly **0.9** for
> being threatened yourself, and is back within **0.0015** two days later.
>
> So: a sixteenth of a direct experience, and gone inside a day. That is the
> right size — Hatfield's contagion is a matter of minutes and hours, not of
> grudges — but a studio should read it plainly: **if you want a player's
> rudeness to mark a district, this is not the layer.** That is `climate`, whose
> half-life is thirty hours and which attaches to places rather than people.
> Contagion makes the next few conversations different. It does not make a town
> remember.

**The runtime knew who knew things, and not whether anybody could still deny
them.** Every belief had a holder, a source and a confidence — which is *private*
knowledge, and only the first of three things a society distinguishes. We all
know it is *mutual* knowledge. We all know we all know is *common* knowledge, and
that is the one that decides what can be **done**: a scandal everybody privately
knows is still deniable, because raising it means being the one who raised it.

> `unscripted/common_knowledge.py` adds the distinction, on Lewis (*Convention*, 1969),
> Aumann (1976) and — for the mechanism a game can use — Chwe (*Rational Ritual*,
> 2001). Common knowledge is not made by more people finding out. It is made by a
> **public moment**, because what makes a moment public is that everybody there
> watches everybody else take it in. So a broadcast establishes it and fifty
> whispers do not, and a phone call never can.
>
> Two consequences, both about what may be **said**: a secret that is common
> knowledge in a character's own community stops working as a secret, because
> refusing to discuss what everybody knows everybody knows protects nothing; and
> nobody passes on what both parties already watched a crowd find out.
>
> **What it deliberately does not do is touch the belief maths.** A public event
> is one origin, weighed once. Treating publicity as evidence would be the same
> error as treating repetition as proof, and a test asserts that establishing a
> public moves no confidence. It also does not merge its crowds: two separate
> public moments about one fact stay two crowds, because somebody who was in the
> square on Tuesday does not thereby know about the people in the bar on
> Wednesday.
>
> On `market-square`, the radio broadcasts the *false* account of the killing —
> so the thing the town cannot deny is the thing that is not true, and the one
> witness who saw otherwise is not in the crowd, because she does not listen to
> the radio.

**Every claim died with the conversation.** A thing said was heard or not heard
and then it was gone. There was nothing in the world that a character could find
later, and so nothing that was *evidence* rather than testimony.

> `unscripted/notes.py` adds the one channel that is still there afterwards. It is not a
> slower telephone; the whole difference is persistence, and everything
> interesting follows from it: a note can be **read by somebody it was not
> written for**, and it arrives with its author's name on it when the author is
> not present to be asked about it.
>
> The generator uses no knowledge a character does not have: somebody has a
> reason to tell a specific person something, cannot reach them, and leaves word
> **where they are standing**. Nobody writes to an address they do not know.
>
> Where the detail goes is the other half. On a phone the levelling happens in
> the telling, so distortion runs at the moment of the exchange. On paper it
> happens once, at the writing — and after that the words are fixed, so a note
> that says the wrong thing goes on saying exactly the wrong thing to everybody
> who reads it. That is the difference between a rumour and a document.
>
> Over a week of `market-square`: **84 written, 41 delivered, 28 read by the
> wrong person, 11 never collected.** With telephones in the world, none at all —
> the person you want is usually already in your contacts, which is the honest
> outcome and is stated rather than tuned away.

**Three engines were built and never called.** An audit of what the runtime
constructs against what anything invokes found `ReputationEngine`,
`SocialIdentityEngine` and `InterpersonalEngine` instantiated on every runtime
and reached by nothing. That is not merely waste: because nothing produced
reputation deltas, `agent.reputation` was an empty mapping in every world at
every time — and `unscripted/sociolinguistics.py` reads it to compute perceived
social status, so a documented behaviour silently reduced to a constant.
Separately, `IdentityEngine.salience` weighs four terms and one of them,
`w_threat`, was multiplied by zero everywhere because the runtime called
`salience(agent, {})`.

> Two are alive. Reputation gained a producer with `unscripted/promises.py`: breaking
> your word costs a *reliable* reputation with the person you failed and with
> everyone who heard you promise. Social identity gained the thing it was
> missing, which was never the engine — whether an event threatens *your*
> belonging depends on who you are, so it can only be decided per observer, and
> it now is. Attack a keeper in front of another keeper and her `keeper` salience
> rises from 0.832 to 0.902, halving back over a day, because alarm on behalf of
> your group is not a grudge.
>
> **The limit, stated rather than left to be discovered:** this fires on
> *witnessing*. A retold attack arrives as a `claim` carrying a proposition, and
> recovering "an attack on one of ours" from that is a different and larger piece
> of work. Somebody who was elsewhere feels nothing, and a test asserts that so
> the limit cannot quietly become an oversight.
>
> The third, `InterpersonalEngine`, is no longer constructed. Its mapping is
> right and its other half does not exist: the sociolinguistic layer would have
> to carry a stance alongside its style vector and the realizer would have to
> phrase from it. A component with no socket is better described than
> instantiated. A test now fails if any engine is built that nothing calls.

**No natural-language authoring.** The authoring tool is good — the day as a grid,
proposition pickers, live consequence reports — but a designer still thinks in
predicates and slots. That is a feature for correctness and a cost for adoption.

**Single-process, single-world.** There is no sharding, no multi-world server, no
horizontal scale story. Fine for a game client; not a service platform yet.

**Text is one language at a time.** The register system is language-agnostic in
design, but phrasings are authored per world pack in one language.

**Voice is planned, not bundled.** Rate, pitch and loudness are derived from the
speaker's affect and composed with a per-character base voice, so a frightened
character reads faster and higher and still sounds like himself. `unscripted
voice` hands that plan to `espeak-ng`, `piper` or `kokoro`; none of them ships
with the SDK, because every practical Python TTS pulls in onnxruntime or torch
and the dependency-free install is worth more than a bundled voice. Each is
reached the same way — a name on PATH. What each backend cannot honour is
reported rather than smoothed over: espeak-ng takes rate, pitch and loudness
exactly and sounds robotic; piper sounds far better and has no pitch control at
all, which costs an emotional read half its signal; kokoro is better again — 24
kHz, and the only one whose intonation sounds like somebody meaning something —
and it cannot change pitch either. There is no audio endpoint on the HTTP
service.

---

## 10. Where to go next

In the order that adds the most value per unit of work, with the reasoning.

### Near term — close the gaps that a buyer will test

**1. Entity grounding in the validator.** Extend unlicensed-specifics to common
nouns that name things the world declares (places, objects, roles). This is the
largest remaining hole in the safety claim and the one most likely to be probed
in an evaluation.

**2. Prose-level levelling.** Let the realizer receive the *distortion kind*, not
only the reduced proposition, so a levelled claim is phrased vaguely and a
sharpened one emphatically. Small change, large perceived-quality gain, and it
closes the seam that shows when a model is doing the wording.

**3. Put it in a scene.** Both Unreal plugins compile against a real engine and
both Unity paths compile against a real editor, so "integration" is no longer a
claim with an asterisk — but nothing has been RUN in a game. A single vertical
slice, one room and three characters in one engine, would replace more
speculation than any further test can.

**4. An event generator for idle worlds.** The director can escalate; it does not
yet invent. Scheduled and emergent incidents that keep a world producing news
would turn `long_life` from a stability proof into a liveliness proof.

### Medium term — the things that would make it a platform

**5. Player-visible epistemics.** The data exists to show a player *why* a
character believes something — a journal, an interrogation view, a contradiction
prompt. No game has shipped this because no engine had the data. This is the
feature that turns an architecture into a genre.

**6. Multi-world service.** Sharding, a world-per-process supervisor, and an
authenticated multi-tenant API. Needed for a hosted offering; not needed for a
single-player game.

**7. Personality drift.** Slow adaptation of traits under sustained experience.
Small model change, large narrative consequence, and needs careful bounding to
avoid every character converging.

**8. A second text path: structured generation.** Constrained decoding so a model
*cannot* produce an unlicensed specific, instead of being rejected afterwards.
Higher quality, better latency, but ties the runtime to model internals — worth
prototyping, not worth committing to yet.

### Longer term — research directions with real upside

**9. Learned appraisal.** OCC appraisal parameters are authored per character.
Learning them from play would make characters idiosyncratic in ways an author did
not have to specify.

**10. Theory of mind, deeper.** There is a ToM model layer (what A thinks B
believes). Extending it to second order — what A thinks B thinks A believes —
unlocks deception, mistrust and conspiracies as emergent rather than authored.

**11. Cross-media provenance.** Radio and channels exist. Adding documents,
overheard fragments and forged evidence would let a player *manufacture* belief,
with the system able to trace exactly what they did.

---

## 11. Verify any of this yourself

```bash
# a playable world in one command
unscripted play --world-pack worldpacks/cyberpunk-block

# the invariants, as numbers
unscripted benchmark --world-pack worldpacks/relay-station --turns 5000

# a fully recorded session; DOSSIER.md is meant to be read
unscripted evidence --hours 0.2 --world-pack worldpacks/cyberpunk-block --out evidence/

# with a local model: every line the model tried, and what was released
unscripted evidence --case secret_under_pressure --case cross_examination \
             --llm-endpoint http://localhost:11434/v1/chat/completions \
             --llm-model qwen3-vl:4b-instruct

# build a world, see the consequences while you type
unscripted new worldpacks/my-town --name "My Town" --start 09:00
unscripted studio --world-pack worldpacks/my-town
unscripted author worldpacks/my-town

# the whole suite
python3 tests/test_scenarios.py
```

Committed evidence runs are in [`../evidence/`](../evidence/).

---

## Further reading in this repository

| Document | What it covers |
| --- | --- |
| [`SPECIFICATION.md`](SPECIFICATION.md) | the reconstruction manual: every formula, ordering rule and data shape, stated so the system can be rebuilt from it |
| [`SOCIETY.md`](SOCIETY.md) | routines, diffusion, and why a question is not an assertion |
| [`CALIBRATION.md`](CALIBRATION.md) | every parameter, its basis, and whether it is grounded or authored |
| [`AUTHORING.md`](AUTHORING.md) | building a world, and the five things authors get wrong |
| [`LOCAL_MODELS.md`](LOCAL_MODELS.md) | running a model on the machine the game is on |
| [`UNREAL_INTEGRATION.md`](UNREAL_INTEGRATION.md) | the plugin, the contract, and measured cost |
| [`SDK_INTEGRATION.md`](SDK_INTEGRATION.md) | embedding the runtime in another engine |
