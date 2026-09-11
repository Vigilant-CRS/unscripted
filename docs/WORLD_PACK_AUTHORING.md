# World Pack Authoring

World packs are declarative content. They should not contain model prompts as
state. The runtime turns authored facts, events, characters and relationships
into structured beliefs, memories and social consequences.

## Required Layout

```text
my-pack/
  world.json
  scenario.json
  canon.json
  initial_state.json
  characters/
    character_a.json
    character_b.json
```

Validate before loading:

```bash
unscripted validate my-pack
```

Generate NPCs from environment and appearance:

```bash
unscripted generate-characters \
  --world-pack my-pack \
  --location place:market \
  --appearance worn_jacket \
  --count 4 \
  --write
```

The generator derives personality, values, needs, role, identity, education,
status, resources and starting knowledge from:

- place noise/surveillance/privacy;
- faction territory;
- appearance token;
- optional role hints;
- deterministic seed.

## world.json

Defines places, channels, media exposure, entities and factions.

Required for each place:

- `noise_level`
- `surveillance_level`
- `privacy_level`

Faction entries should include:

- `id`
- `influence`
- `resources`
- `territory`
- `goals`

## scenario.json

Defines seed, start time and scheduled events.

Events are structured:

```json
{
  "world_time": 4360,
  "type": "broadcast",
  "actor": "channel:city_news",
  "location": null,
  "payload": {
    "channel": "channel:city_news",
    "credibility": 0.64,
    "proposition": {
      "predicate": "connected_to_attack",
      "slots": {"agent": "agent:player_1"},
      "polarity": "+"
    },
    "summary": "City News links the stranger to the market attack",
    "origin_event": "evt_market_attack"
  }
}
```

## Character Profiles

Core fields:

- `id`
- `names.public`
- `big_five`
- `schwartz`
- `needs`
- `identities`
- `roles`
- `relationships`
- `secrets`
- `goals`
- `social_status`
- `resources`
- `location`

Secrets should be labels such as `prop:milan_location`, not full secret prose.
The validator maps labels to safe avoid-topics and surface-form guards.

## initial_state.json

Initial state contains authored subjective beliefs and memories. Use it for
starting knowledge that an NPC already has before play begins.

```json
{
  "beliefs": [
    {
      "agent": "agent:barkeep_12",
      "proposition": {
        "predicate": "clinic_open",
        "slots": {"place": "place:clinic", "when": "last_night"},
        "polarity": "-"
      },
      "summary": "Honce heard two regulars say the clinic was closed.",
      "origin_event": "seed_bar_clinic",
      "trust": 0.82,
      "competence": 0.85,
      "importance": 0.70
    }
  ]
}
```

This is subjective evidence. It does not overwrite canonical truth.

## Authoring Rules

- Do not make NPCs all-knowing through prompt text.
- Use scheduled events, starting beliefs or scenario interactions to distribute
  information.
- Keep protected facts out of generated prompt context.
- Prefer precise proposition predicates to raw strings.
- Assign repeated rumors the same `origin_event`.
- Give independent witnesses separate `origin_event` values.
- Put language style in character data, not in ad hoc prompt hacks.
- Add a golden scenario under `golden/` for every pack intended for pilots.
- Review generated profiles as authored content before shipping.
