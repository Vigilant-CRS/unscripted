# Authoring a Society

How to make a world where people go about their day, meet, talk, and pass things
on — with every step of it traceable.

Two layers do this work, and both are **authored in the world pack**, not
configured in code:

| Layer | File | What it decides |
| --- | --- | --- |
| **Routines** | `characters/*.json → routine` | who is where, at what time of day |
| **Diffusion** | `world.json → diffusion`, `places.*.gossip_factor` | who tells whom what, and how it distorts |

Routines come first: information cannot travel between people who never share a
room. Before routines existed, two of the three reference packs had no two
characters in the same place at any point, and nothing could ever spread.

---

## 1. Routines — the day

A routine is a list of blocks. Each block starts at a time of day and runs until
the next one begins, wrapping past midnight.

```json
{
  "id": "agent:schmied_hanns",
  "location": "place:schmiede",
  "routine": [
    {"from": "05:00", "place": "place:schmiede",  "activity": "an der Esse"},
    {"from": "12:00", "place": "place:dorfplatz", "activity": "Mittag"},
    {"from": "14:00", "place": "place:schmiede",  "activity": "an der Esse"},
    {"from": "19:00", "place": "place:dorfplatz", "activity": "Feierabend"},
    {"from": "22:00", "place": "place:schmiede",  "activity": "schlafen"}
  ]
}
```

- `from` is `HH:MM`, or minutes past midnight as an integer.
- `place` must exist in `world.json`.
- `activity` is optional, appears in arrival text and in the reason trace, and is
  purely descriptive — the engine never branches on it.
- A character with no `routine` stays where `location` puts them, forever. That is
  a legitimate choice for a shopkeeper who never leaves the counter.

**A block wraps.** With blocks at 05:00 and 22:00, a character asked about at
02:00 is in the 22:00 block. You never write the overnight block twice.

### The rule that will bite you once

> If a character declares both a `location` and a `routine`, they must agree at
> the scenario's start time.

`location` is where the scene opens. The routine is the rest of the day. If they
disagree, the pack contradicts itself and the session begins somewhere you did
not write. `unscripted validate` treats this as an **error**:

```text
ERROR routine.contradicts_start_location: agent:clara starts at place:office but the
routine puts them at place:pier at 20:00; the pack disagrees with itself about where
the scene opens.
```

Check your scenario's start time before writing routines:

```bash
python3 -c "import json; t=json.load(open('worldpacks/mypack/scenario.json'))['world_time']%1440; print(f'{t//60:02d}:{t%60:02d}')"
```

Block 17 opens at **00:14** — which is why its cast is out on Main Street after
last call, not asleep. The routines say so explicitly.

### Checking that your cast actually meets

```python
from unscripted import UnscriptedRuntime, RuntimeConfig
rt = UnscriptedRuntime.create(RuntimeConfig(world_pack_path="worldpacks/mypack"))
for place, who in rt.core.routine.meeting_opportunities(rt.world).items():
    print(rt.world.place_label(place), "->", who)
```

`unscripted validate` warns when nobody ever meets:

```text
WARNING routine.no_meetings: No two scheduled characters ever share a place over a
full day, so nothing can be told to anyone and rumour cannot spread.
```

### What movement produces

Every transition emits a real `move` event, so an arrival is perceived,
remembered and recorded. "Who was in the bar at 21:00" is a ledger query, not a
guess. Arrivals carry low importance (0.15), so they consolidate away before
anything that matters to a character.

Turn them off for a pack that does not want the noise:

```json
{ "routine": { "emit_events": false, "arrival_importance": 0.15 } }
```

A long time skip is safe: `advance_time(60*24*7)` puts everyone where they belong
at the end of the week and emits at most one movement per character. Intermediate
blocks are skipped, not replayed.

---

## 2. Diffusion — the rumour

Once people meet, they talk. A retelling is emitted as an ordinary `claim` event
by the speaker at their location, so it flows through the same
perception → belief → memory → affect path as everything else.

```json
{
  "diffusion": {
    "encounters_per_hour": 0.35,
    "min_confidence_to_tell": 0.60,
    "fidelity_decay": 0.85,
    "distortion_prob": 0.06,
    "max_hops": 4,
    "bystanders": 3,
    "include_player": false
  },
  "places": {
    "place:dorfplatz": { "gossip_factor": 1.9 },
    "place:kapelle":   { "gossip_factor": 0.5 }
  }
}
```

| Key | Meaning |
| --- | --- |
| `encounters_per_hour` | conversations per person per hour, before place and tie modifiers |
| `gossip_factor` | per place. A market square spreads; a chapel does not. `0` disables gossip there entirely |
| `min_confidence_to_tell` | nobody passes on what they are unsure of |
| `fidelity_decay` | how much conviction a retelling loses per hop |
| `distortion_prob` | chance a retelling changes the claim (see distortion below) |
| `distortion_weights` | relative frequency of levelling / sharpening / assimilation / inversion |
| `max_hops` | how far a claim travels before people stop bothering |
| `bystanders` | how many others overhear one exchange. This is how a player picks up rumours in a bar |
| `include_player` | whether NPCs gossip *to* the player unprompted |

### The property that matters

**A retelling carries the origin it came from, not the person who relayed it.**

```text
Honce (witnessed it, origin seed_bar_clinic, hops 0)
  └─ tells Okada    (origin seed_bar_clinic, hops 1)
       └─ tells Dima (origin seed_bar_clinic, hops 2)
```

Dima has now heard it from Okada, but the belief still records
`seed_bar_clinic`. If Dima later hears the same thing from a third person who
also traces to Honce, correlation discounting sees the duplication and the claim
barely moves. Five mouths relaying one witness is one witness.

Hearing it from someone with a *genuinely different* origin is independent
evidence and moves the needle properly. That distinction is the product.

### hops

`belief.hops` is the **shortest** known social distance to a first-hand source.
Witnessing something, or hearing it on a broadcast channel, is 0. A rumour that
echoes back to its own witness does not move them away from what they saw.

Use it for UI: `hops == 0` is testimony, `hops >= 3` is "people are saying".

### How a claim changes on the way

A retelling may be levelled (a detail is forgotten), sharpened (a quantity grows),
assimilated (a name drifts to someone the teller knows) or, rarely, inverted.

```text
heard : connected_to_attack(agent=agent:player_1)
retold: connected_to_attack(agent=agent:npc_red_jacket)
     -> agent:player_1 became agent:npc_red_jacket — a person the teller knows
```

The distorted claim becomes a **separate belief** with its own key, so the world
can hold both the true and the false version at once and you can see who holds
which. It still carries the true origin, so it stays one source that is now wrong.

The demo's "who told whom" feed says what changed, not just that something did.

### Secrets never travel

A proposition protected by a secret is never selected for gossip — the same
filter the dialogue planner uses. There is a benchmark metric for it
(`secret_leak_count`) that traces provenance, so two characters independently
knowing the same thing is correctly *not* reported as a leak.

---

## 3. Verifying it works

```bash
unscripted validate worldpacks/mypack        # topology, routines, meetings, secrets
unscripted benchmark --world-pack worldpacks/mypack --turns 3000
```

The benchmark's `relayed_beliefs` metric answers "did anything actually spread".
If your world cannot exercise it — nobody ever meets — it reports `SKIP`, not
`PASS`. A benchmark that cannot tell "did not happen" from "cannot happen"
measures nothing.

Watch a rumour move:

```python
from unscripted import UnscriptedRuntime, RuntimeConfig
rt = UnscriptedRuntime.create(RuntimeConfig(world_pack_path="worldpacks/mypack"))
for _ in range(24):
    rt.advance_time(60)
for agent in rt.world.agents.values():
    for belief in agent.beliefs.values():
        if belief.hops > 0:
            print(f"{agent.id} heard {belief.proposition} "
                  f"(origin {belief.primary_origin}, {belief.hops} hops away)")
```

Or use the structured map, which is what the demo UI renders:

```python
k = rt.structured_knowledge()
for fact in k["facts"][:3]:
    print(fact["text"], f"reach {fact['reach']}",
          f"({fact['first_hand']} saw, {fact['hearsay']} heard)",
          f"origins {fact['origins']}")
for row in k["transmissions"][-5:]:
    print(f"{row['from_name']} -> {row['to_name']} @ {row['place_label']}")
```

`GET /state/knowledge` returns the same thing over HTTP. Note `origins`: more
than one means genuinely **independent** sources, which is the difference between
a well-founded belief and a well-repeated one.

Read who told whom, from the ledger:

```sql
SELECT world_time, actor, location, payload
FROM event_ledger
WHERE payload LIKE '%diffusion%'
ORDER BY event_id;
```

---

## 4. Tuning notes

These defaults were set by hand and are **not yet calibrated against the
literature** on rumour propagation. They are honest starting points, not results.
If you are tuning for a specific feel:

- **Nothing spreads.** Check `meeting_opportunities` first — it is almost always
  the routines, not the diffusion parameters. Then check
  `min_confidence_to_tell`: characters will not pass on a 0.55 belief.
- **Everything spreads instantly.** Lower `encounters_per_hour`, or lower
  `gossip_factor` on your busiest place. Remember the encounter rate is *per
  person*, so a crowded square is already multiplied by its occupancy.
- **Rumours feel too accurate.** Raise `distortion_prob`, or shift
  `distortion_weights` toward `sharpening` and `assimilation` — those produce
  wrong stories, while `levelling` produces vague ones.
- **A false belief will not die.** That is intended: correcting a belief needs
  countervailing evidence with its own origin, not time. Author a broadcast or a
  credible witness.

---

## 5. Known limits

Stated plainly so you do not discover them in playtesting:

- **Routines are schedules, not plans.** No pathfinding, no needs-driven
  behaviour, no reacting to a locked door. A character teleports between blocks.
- **Distortion acts on slots, not on prose.** A detail is dropped, a number grows,
  a name is swapped. There is no wording to garble.
- **No sub-place proximity.** Everyone in a place is equally "present"; the
  `bystanders` cap approximates who is close enough to overhear.
- **Parameters are uncalibrated.** See above.
- **Routines do not vary by day.** No weekends, no market days. A pack that needs
  them can drive movement through scheduled scenario events instead.

## A question is not an assertion

Asking about something must not make anyone believe it. This is easy to get
wrong, and this project got it wrong: `ask X about Y` emitted a **claim** event
carrying the proposition, so everyone in earshot -- including the person being
asked -- updated as though the player had stated it as fact. Measured, a single
question moved the answer's own belief by about +0.009, and asking twenty times
walked it towards certainty with nobody having said anything at all.

`question` is now its own event type. It is heard, encoded and remembered -- a
character knows they were asked and can react to being asked, and interrogating
someone repeatedly is still socially visible -- but it never reaches the belief
system. The `cross_examination` evidence case exists to keep it that way: it
presses every character on every topic **without advancing the clock**, so there
is no diffusion and no movement to explain anything away, and requires that not
one belief has shifted by the end.

The distinction it draws is worth stating plainly, because it is the difference
between a simulation and a mood:

| | moves belief | is remembered |
| --- | --- | --- |
| someone asserts something (`claim`) | yes, discounted by trust and provenance | yes |
| someone asks about something (`question`) | **never** | yes |


## Lying

A character who is cornered has two options, and which they take is a
characterisation decision rather than an engine one.

**Refuse.** The default. Below the trust a secret demands, the holder will not
discuss the topic — and refusal is itself information, which is why silence is a
respectable answer and not a failure mode.

**Lie.** If the world has authored a *cover story* for the secret and the
character's `truthfulness` is below the secret's stake, they assert the cover
story instead. Four states stay apart:

| | |
| --- | --- |
| what they **believe** | unchanged, and recorded on the move as `believed_probability` |
| what they **want** | to protect the secret |
| what they **say** | the cover story, as a real claim, with them as its origin |
| what they intend you to **believe** | the cover story |

Measured on `cyberpunk-block`: Okada holds "Milan is in the back room" at 0.868,
asserts "Milan left the city months ago", and four listeners acquire the lie with
Okada named as the source. His own belief does not move — nobody is persuaded by
their own mouth.

Because the cover story contradicts the truth (the `whereabouts` predicate is
declared functional in its `who` slot), anyone who later hears both holds a
genuine contradiction, and the liar is findable.

**The engine invents neither the lie nor its words.** No cover story means no
lie. No `cover_phrasings` means the character has committed to saying something
the text layer cannot express — and then **nothing is asserted at all**. That
rule exists because the alternative was observed: the player read "I have nothing
further to add" while the room heard Okada announce where Milan was. The
simulation and the sentence must be describing the same conversation.

## Why not everyone ends up knowing everything

Diffusion answers *how* information moves. In a city-sized cast, *where it stops*
matters more — left to co-location and trust alone, a claim eventually reaches
anyone who ever shares a room with anyone, and a long-running world has plenty of
time.

Three brakes, all of them world content.

**Knowledge is not a hierarchy.** A street vendor knows more about the local gang
than a corporate director does, so rank is not a knowledge ordering and a single
pyramid would be the wrong shape. A predicate is classified on independent axes:

| | |
| --- | --- |
| `classification` | public · common · local · trade · restricted · secret — sets how readily it travels |
| `access` | the circles whose members will pass it on. Empty means anyone |
| `locality` | places where it circulates at all |
| `domain` | whose competence bears on it — shop talk reaches the trade and bores everyone else |

Access restricts **circulation, never perception**. Seeing something you have no
clearance for is exactly how interesting trouble starts.

**People talk inside their circles.** Family, shift, union, crew, clique. A claim
moves more readily between people who share one, and crosses between them only
through the few who belong to both. `topology.bridges(world)` names those people,
because "who could this have reached" is a question a designer asks constantly.

**Attention is finite.** A bounded number of *new* claims per day are properly
encoded — being reminded of something you already hold is free. Past that a
character hears and forgets. The budget scales with curiosity, resets each world
day, and survives save/load, because a reload that hands everyone a fresh day
would absorb information the same session refused.

Measured on `relay-station`, four simulated days, eleven characters:

```
skipped_check   [restricted]   1 holder    engineers only
seal_breached   [trade     ]  11 holders   everyone saw it happen
logged_out      [common    ]   9 holders
supply_short    [public    ]   7 holders
```

The restricted maintenance finding never left the trade. That is the mechanism
working: to get it out of the engineering circle, someone has to carry it — and
the obvious someone is the player.

## Reach and detail are different things

A robbery happens at a kiosk. The radio says *"an armed robbery in the lower
city"* and reaches everyone. A neighbour saw two men on a red motorcycle. The
kiosk owner knows they were looking for one particular chip. A mechanic
recognises the bike.

These are not four facts. They are one incident with four versions in
circulation, and they differ on two axes that have nothing to do with each other:

| | wide | narrow |
| --- | --- | --- |
| **thin** | a radio headline | someone half-overheard something |
| **detailed** | a scandal everybody has read the file on | an eyewitness account |

The runtime has always known these belong together — every claim carries the
origin event it came from, which is why hearing the headline and then meeting the
witness does not count as two independent sources. What it did not do was *say*
so, and a debug HUD saw unrelated facts where there is one story.
`structured_knowledge()["stories"]` now groups them. Measured on
`relay-station`:

```
incident_42
   reach 11 · detail 1   seal_breached(section=place:store)
   reach  2 · detail 2   seal_breached(section=place:store, when=night_cycle)
   reach  1 · detail 2   seal_breached(section=place:mess,  when=night_cycle)
```

The headline reached the whole station and dropped the shift. Two people who were
there hold the full account. One of them, who lacks the trade to read the scene,
holds a version with the wrong section — widely known, precisely known, and
wrongly known are three different states, and all three exist here at once.

### A stated claim is not misheard

Finding this exposed a real error. Recognition — *could this character identify
what they perceived?* — was being applied to claims that arrived **in words**. So
a layman hearing a radio report that a seal failed in Stores would relocate it to
the med bay.

That is wrong. You can disbelieve a report; you do not mishear "Stores" as "the
med bay". When a claim arrives stated, the speaker has already done the
identifying, and competence bears on whether you *believe* them — which the
belief engine handles. Recognition now applies only to what a character
**perceived directly**, which is where it belongs and where it produces the good
result: the witness who could not read the scene is the one holding the wrong
section.
