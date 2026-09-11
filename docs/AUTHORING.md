# Building a World

You should not need to know how the runtime stores anything in order to write a
world for it. This page is the whole workflow.

```bash
unscripted new worldpacks/my-town --name "My Town" --start 09:00   # a world that already works
unscripted studio --world-pack worldpacks/my-town                  # edit it, see consequences live
unscripted author worldpacks/my-town                               # what is still missing
unscripted play  --world-pack worldpacks/my-town                   # play it
```

---

## 1. Start from something that works

`unscripted new` does not create an empty directory. It writes a small,
complete, **playable** world:

- two places that connect, so you can walk;
- two characters whose routines put them in the same room, so information can move;
- one topic one of them can answer, so asking does something;
- one secret the other actually withholds, with the words that would give it away.

Rename things and you have your world. Starting from an empty directory means a
week of reading documentation — and every pack written that way in this project
shipped a defect that only a test found.

The scaffold also guarantees the thing first-time authors get wrong: the opening
scene and the routines **agree** about where everyone is at the scenario's start
time.

---

## 2. Edit it in Studio

`unscripted studio` serves an editor at `http://127.0.0.1:8766/studio`. Three
things it does that a text editor cannot:

### The day is a picture

A routine is drawn as a 24-hour grid, one row per character, coloured by place.
Where two characters overlap is outlined. *"Do these two ever meet?"* is the
question behind every rumour in your world, and it used to be unanswerable
without running the game.

### Consequences appear while you type

Every edit re-runs the authoring report against the **unsaved** document. "Nobody
can answer this topic", "this secret is decorative", "nobody ever meets" show up
as you work, not after a playtest. Nothing is written until you press Save.

### Facts are pickers, not strings

Choose a fact from a list, fill in its fields. The canonical key the runtime uses
internally is never shown, because it is never typed. Typing
`pred(a=1,b=2)[None,None,None]` by hand is how you silently disable a secret.

### What you can edit without touching JSON

| Section | What it gives you |
| --- | --- |
| **Places** | name, the words players type, which places connect (checkboxes, not lists), and how loud / watched / private / formal / gossipy a place is, as sliders |
| **Characters** | names and aliases, the day as editable blocks, relationships (trust, liking, familiarity) toward everyone including the player, and secrets |
| **Topics** | the words players might type, what asking actually asks, and the phrasings characters answer with, per stance and register |
| **Who knows what** | who starts out knowing what, from which source, and how much they trust it |

Everything else stays available as raw JSON. This is an editor for the parts that
need one, not a wrapper that hides the format from people who know it.

Trust is the field worth understanding: it decides how much a claim from that
person moves a belief. Liking and familiarity decide whether the two chat at all.
A character who trusts nobody hears everything and believes none of it.

---

## 3. Ask what is missing

```bash
unscripted author worldpacks/my-town
```

```text
  MAP
     The Square -> place:tavern
     The Tavern -> place:square
    !Cellar (no exits)

  WHO MEETS WHOM (hours per day)
     agent:mara + agent:tomas: 7.0h in place:square, place:tavern

  ANSWERABLE TOPICS: delivery

  9 THING(S) TO LOOK AT
   [BLOCKER] Tomas starts at The Square but their routine puts them at Cellar at 09:30.
              -> The pack disagrees with itself about where the scene opens.
   [problem] Secret 'secret:the_cart' has no surface forms.
              -> A text provider phrasing it freely would not be caught. List the
                 words that would give it away.
```

This is deliberately more opinionated than `unscripted validate`. A pack can be
perfectly valid and still be a world where nobody meets, nothing can be asked
and every secret is decorative. Validation checks the schema; this checks
whether you have made a world.

Three levels:

| | Meaning |
| --- | --- |
| **blocker** | the pack contradicts itself or cannot function. Fix before playing |
| **problem** | it will run, but something you probably wanted will not happen |
| **hint** | a choice worth being deliberate about |

Every finding carries a fix. `--json` gives the same thing machine-readable.

---

## 4. The five things authors get wrong

Ordered by how often, based on the three packs shipped with the runtime — all of
which had at least one of these.

**1. The opening scene disagrees with the routines.** A character declares
`location` *and* a `routine`, and they name different places at the scenario's
start time. Now a **blocker**, not a mystery.

**2. Nobody ever meets.** Every character is alone in their own place all day, so
nothing can spread. Two of three reference packs had this, and it made the whole
diffusion layer inert.

**3. A topic nobody can answer.** You wrote the question but seeded the belief in
nobody. Characters deflect and it reads like a bug.

**4. A topic with no phrasings.** The engine ships **no** factual sentences — it
will not put words in your characters' mouths about your world. Without
`phrasings.affirm` / `phrasings.deny` they deflect instead of answering.

**5. A secret with no surface forms.** It filters facts out of prompts, but if a
language model phrases the secret in its own words nothing catches it. List the
words that would give it away.

---

## 5. What a pack contains

```text
world.json          places (label, aliases, exits, formality, gossip_factor),
                    entities, channels, factions, identity_values, slang_lexicon,
                    dialogue_templates, command_aliases, diffusion settings
scenario.json       seed, start time, player_start, focus_agents, scheduled events
canon.json          predicates this world declares, and its canon facts
topics.json         what can be asked, what it answers, authored phrasings
initial_state.json  who starts out knowing what, and from which source
characters/*.json   people: personality, relationships, routine, secrets
```

Details of routines and rumour spread: [`SOCIETY.md`](SOCIETY.md).
Parameter grounding: [`CALIBRATION.md`](CALIBRATION.md).

---

## 6. Studio is a local tool

It is the only part of the runtime that **writes files**, so it is treated
accordingly:

- disabled unless you start it with `unscripted studio`;
- confined to the one pack directory you named;
- character filenames from the browser are rejected unless they are a plain
  `*.json` name — no separators, no traversal, no dotfiles;
- refused on any non-loopback address, whatever the authentication settings;
- preview never touches disk.

Do not put it on a shared machine and do not expose the port.
