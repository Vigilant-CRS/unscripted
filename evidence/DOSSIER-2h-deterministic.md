# Unscripted — Evidence Run

**every case held (1 untestable in the world given)** · 120 minutes of running · packs: cyberpunk-block, noir-harbor, dorf-thornfeld, relay-station · text: deterministic templates only

| | |
| --- | --- |
| commit | `f991fc20f993` Unscripted |
| working tree | clean |
| python | 3.14.4 |
| platform | Linux 7.0.0-31-generic (x86_64) |
| started / finished | 2026-09-11T09:17:55Z → 2026-09-11T11:17:55Z |

> Cases marked *n/a* were not run to a verdict because the world never exercised the mechanism — a three-character village produces almost no gossip. They are untested there, not disproved; the same case passes on the larger packs in the same run.

| Case | Pack | Result | Time |
| --- | --- | --- | --- |
| determinism | cyberpunk-block | pass | 0s |
| broadcast_chain | cyberpunk-block | pass | 0s |
| forgetting | cyberpunk-block | pass | 0s |
| distortion | cyberpunk-block | pass | 0s |
| secret_under_pressure | cyberpunk-block | pass | 0s |
| disagreement | cyberpunk-block | pass | 0s |
| conversation | cyberpunk-block | pass | 0s |
| cross_examination | cyberpunk-block | pass | 0s |
| determinism | noir-harbor | pass | 0s |
| broadcast_chain | noir-harbor | pass | 0s |
| forgetting | noir-harbor | pass | 0s |
| distortion | noir-harbor | pass | 0s |
| secret_under_pressure | noir-harbor | pass | 0s |
| disagreement | noir-harbor | pass | 0s |
| conversation | noir-harbor | pass | 0s |
| cross_examination | noir-harbor | pass | 0s |
| determinism | dorf-thornfeld | pass | 0s |
| broadcast_chain | dorf-thornfeld | pass | 0s |
| forgetting | dorf-thornfeld | pass | 0s |
| distortion | dorf-thornfeld | n/a | 0s |
| secret_under_pressure | dorf-thornfeld | pass | 0s |
| disagreement | dorf-thornfeld | pass | 0s |
| conversation | dorf-thornfeld | pass | 0s |
| cross_examination | dorf-thornfeld | pass | 0s |
| determinism | relay-station | pass | 0s |
| broadcast_chain | relay-station | pass | 0s |
| forgetting | relay-station | pass | 0s |
| distortion | relay-station | pass | 0s |
| secret_under_pressure | relay-station | pass | 0s |
| disagreement | relay-station | pass | 0s |
| conversation | relay-station | pass | 0s |
| cross_examination | relay-station | pass | 0s |
| long_life | cyberpunk-block | pass | 1799s |
| long_life | noir-harbor | pass | 1800s |
| long_life | dorf-thornfeld | pass | 1800s |
| long_life | relay-station | pass | 1800s |

## determinism — cyberpunk-block

*Does the same seed reproduce the same world?*

```
bytes_compared                   20757
identical                        True
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` **world** — player: *look*
  > Main Street
- `day 3 01:14` **world** — player: *wait 60*
  > Time advances by 60 minutes.
- `day 3 01:14` **agent:barkeep_12** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_market_attack`)
- `day 3 01:14` **agent:npc_red_jacket** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_market_attack`)
- `day 3 03:14` **world** — player: *wait 120*
  > Time advances by 120 minutes.
- `day 3 03:14` moved agent:barkeep_12 
- `day 3 03:14` moved agent:corpo_okada 
- `day 3 03:14` moved agent:son_marko 
- `day 3 07:14` **world** — player: *wait 240*
  > Time advances by 240 minutes.
- `day 3 07:14` moved agent:dima_broke 
- `day 3 07:14` moved agent:npc_red_jacket 

## broadcast_chain — cyberpunk-block

*Can every holder of a fact be traced back to where it entered the world?*

```
relayed_beliefs                  27
citing_a_real_observation        27
distorted_without_eyewitness     8
distinct_real_origins            7
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` _Waiting for the scheduled broadcast to enter the world._
- `day 3 01:14` **agent:barkeep_12** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_market_attack`)
- `day 3 01:14` **agent:npc_red_jacket** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_market_attack`)
- `day 3 02:14` **agent:npc_red_jacket** → agent:barkeep_12 @ place:main_street: `connected_to_attack(agent=agent:player_1)` (hop 1)
- `day 3 02:14` **agent:npc_red_jacket** → agent:barkeep_12 @ place:main_street: `clinic_open(place=place:clinic, when=last_night)` (hop 1)
- `day 3 02:14` **agent:dima_broke** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (relayed, 1 hop(s) from the source, origin `evt_market_attack`)
- `day 3 02:14` **agent:dima_broke** learned `clinic_open(place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_vee_clinic`)
- `day 3 02:14` **agent:player_1** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (relayed, 1 hop(s) from the source, origin `evt_market_attack`)
- `day 3 02:14` **agent:player_1** learned `clinic_open(place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_vee_clinic`)
- `day 3 09:14` **agent:officer_kane** → agent:pavel @ place:market: `clinic_open(place=place:clinic, when=last_night)` (hop 1)
- `day 3 09:14` **agent:pavel** learned `clinic_open(place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_kane_clinic`)
- `day 3 09:14` **agent:son_ilya** learned `clinic_open(place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_kane_clinic`)
- `day 3 09:14` **agent:son_marko** learned `clinic_open(place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_kane_clinic`)
- `day 3 13:14` **agent:officer_kane** → agent:son_marko @ place:main_street: `clinic_open(place=place:clinic, when=last_night)` (hop 1)
- `day 3 15:14` **agent:barkeep_12** → agent:npc_red_jacket @ place:bar: `clinic_open(place=place:clinic, when=last_night)` (hop 1)
- `day 3 18:14` **agent:barkeep_12** → agent:son_marko @ place:bar: `connected_to_attack(agent=agent:player_1)` (hop 1)
- `day 3 18:14` **agent:son_marko** learned `connected_to_attack(agent=agent:player_1)[None,None,None]` (relayed, 1 hop(s) from the source, origin `evt_market_attack`)
- `day 3 19:14` **agent:barkeep_12** → agent:npc_red_jacket @ place:bar: `connected_to_attack(agent=agent:dima_broke)` (hop 1)
- `day 3 19:14` **agent:barkeep_12** retold it wrong (assimilation): agent:player_1 became agent:dima_broke — a person the teller knows
  heard: `connected_to_attack(agent=agent:player_1)`
  retold: `connected_to_attack(agent=agent:dima_broke)`
- `day 3 19:14` **agent:barkeep_12** → agent:dima_broke @ place:bar: `was_at(agent=agent:officer_kane, place=place:clinic, when=last_night)` (hop 1)
- `day 3 19:14` **agent:dima_broke** learned `connected_to_attack(agent=agent:dima_broke)[None,None,None]` (relayed, 1 hop(s) from the source, origin `evt_market_attack`)
- `day 3 19:14` **agent:dima_broke** learned `was_at(agent=agent:officer_kane,place=place:clinic,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_bar_kane`)
- `day 3 22:14` **agent:pavel** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 22:14` **agent:son_ilya** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:pavel** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:son_ilya** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:son_marko** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:dima_broke** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:pavel** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:son_ilya** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:son_marko** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 06:14` _27 relayed beliefs; 8 of them are distorted versions with no eyewitness of their own -- expected, since the distorted claim never happened -- but every one still cites a real observation._
- `day 4 06:14` **Honce** holds *connected_to_attack(agent=agent:dima_broke)* at 0.508, 2 hop(s) from origin `evt_market_attack`; first-hand: nobody
  route: Honce→Vee@Bar → Honce→Marko@Bar → Honce→Vee@Bar → Honce→Dima@Bar → Pavel→Honce@Bar → Honce→Pavel@Bar
- `day 4 06:14` **Honce** holds *whereabouts(who=agent:npc_red_jacket, place=place:bar_back)* at 0.536, 1 hop(s) from origin `seed_okada_hid_milan`; first-hand: Mr. Okada
  route: Honce→Vee@Bar → Honce→Marko@Bar → Honce→Vee@Bar → Honce→Dima@Bar → Pavel→Honce@Bar → Honce→Pavel@Bar
- `day 4 06:14` **Mr. Okada** holds *connected_to_attack(agent=agent:dima_broke)* at 0.516, 2 hop(s) from origin `evt_market_attack`; first-hand: nobody
  route: Mr. Okada→Vee@Main Street
- `day 4 06:14` **Dima** holds *connected_to_attack(agent=agent:player_1)* at 0.512, 1 hop(s) from origin `evt_market_attack`; first-hand: Honce, Vee
  route: Honce→Dima@Bar
- `day 4 06:14` **Dima** holds *clinic_open(place=place:clinic, when=last_night)* at 0.51, 1 hop(s) from origin `seed_vee_clinic`; first-hand: Honce, Vee, Officer Kane
  route: Honce→Dima@Bar
- `day 4 06:14` **Dima** holds *connected_to_attack(agent=agent:dima_broke)* at 0.579, 1 hop(s) from origin `evt_market_attack`; first-hand: nobody
  route: Honce→Dima@Bar
- `day 4 06:14` **Dima** holds *was_at(agent=agent:officer_kane, place=place:clinic, when=last_night)* at 0.594, 1 hop(s) from origin `seed_bar_kane`; first-hand: Honce
  route: Honce→Dima@Bar
- `day 4 06:14` **Dima** holds *whereabouts(who=agent:npc_red_jacket, place=place:bar_back)* at 0.503, 1 hop(s) from origin `seed_okada_hid_milan`; first-hand: Mr. Okada
  route: Honce→Dima@Bar

## forgetting — cyberpunk-block

*Do memories fade past recall, and is that observable?*

```
recall_threshold                 -1.5
trivial_lost_after_hours         16
important_lost_after_hours       still recallable at 192h
stored_at_end                    44
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 16:14` **agent:barkeep_12** can no longer recall: *someone walking past* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 16:14` **agent:barkeep_12** can no longer recall: *someone walking past* — decayed below the retrieval threshold (activation -1.51 fell below -1.5 after 16h)
- `day 4 08:14` **agent:dima_broke** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:dima_broke** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:officer_kane** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:pavel** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:pavel** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:pavel** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:son_ilya** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:son_ilya** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:son_ilya** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:son_marko** can no longer recall: *Honce arrives to sleeping in the back* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:barkeep_12** can no longer recall: *Vee arrives to meeting contacts* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:dima_broke** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:pavel** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:son_ilya** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:son_marko** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:player_1** can no longer recall: *Marko arrives to hanging around* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Mr. Okada arrives to waiting for a car* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Dima arrives to hustling the late crowd* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:barkeep_12** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:corpo_okada** can no longer recall: *Dima arrives to hustling the late crowd* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:corpo_okada** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:dima_broke** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:npc_red_jacket** can no longer recall: *Honce passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:npc_red_jacket** can no longer recall: *Honce passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:npc_red_jacket** can no longer recall: *Honce passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:npc_red_jacket** can no longer recall: *Honce passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:son_marko** can no longer recall: *Honce arrives to smoking outside after last call* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:son_marko** can no longer recall: *Mr. Okada arrives to waiting for a car* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:son_marko** can no longer recall: *Dima arrives to hustling the late crowd* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:son_marko** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:player_1** can no longer recall: *Honce arrives to smoking outside after last call* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:player_1** can no longer recall: *Mr. Okada arrives to waiting for a car* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:player_1** can no longer recall: *Dima arrives to hustling the late crowd* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 00:14` **agent:player_1** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 08:14` **agent:barkeep_12** can no longer recall: *City News: the stranger is linked to the market attack* — decayed below the retrieval threshold (still stored, no longer retrievable)

## distortion — cyberpunk-block

*Does information degrade realistically, and stay accountable when it does?*

```
claims_with_several_versions     3
processes_seen                   {'levelling': 3, 'assimilation': 3, 'inversion': 1}
retellings_observed              21
retellings_needed                12
days_simulated                   6
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 09:14` **agent:officer_kane** retold it wrong (levelling): the when was forgotten (was last_night)
  heard: `clinic_open(place=place:clinic, when=last_night)`
  retold: `clinic_open(place=place:clinic, when=None)`
- `day 3 19:14` **agent:barkeep_12** retold it wrong (assimilation): agent:player_1 became agent:dima_broke — a person the teller knows
  heard: `connected_to_attack(agent=agent:player_1)`
  retold: `connected_to_attack(agent=agent:dima_broke)`
- `day 3 21:14` **agent:barkeep_12** retold it wrong (inversion): retold as its own opposite
  heard: `was_at(agent=agent:officer_kane, place=place:clinic, when=last_night)`
  retold: `NOT was_at(agent=agent:officer_kane, place=place:clinic, when=last_night)`
- `day 3 21:14` **agent:son_marko** retold it wrong (assimilation): agent:player_1 became agent:dima_broke — a person the teller knows
  heard: `connected_to_attack(agent=agent:player_1)`
  retold: `connected_to_attack(agent=agent:dima_broke)`
- `day 3 22:14` **agent:npc_red_jacket** retold it wrong (assimilation): agent:dima_broke became agent:corpo_okada — a person the teller knows
  heard: `connected_to_attack(agent=agent:dima_broke)`
  retold: `connected_to_attack(agent=agent:corpo_okada)`
- `day 3 22:14` **agent:pavel** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 22:14` **agent:son_ilya** can no longer recall: *Marko arrives to home* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:pavel** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:son_ilya** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 01:14` **agent:son_marko** can no longer recall: *Dima arrives to sleeping rough* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:dima_broke** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:pavel** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:son_ilya** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:14` **agent:son_marko** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 07:14` **agent:player_1** can no longer recall: *Officer Kane arrives to patrol* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:officer_kane** can no longer recall: *Marko arrives to hanging around* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 08:14` **agent:player_1** can no longer recall: *Marko arrives to hanging around* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:barkeep_12** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:barkeep_12** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:barkeep_12** can no longer recall: *Vee arrives to meeting contacts* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:dima_broke** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:dima_broke** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:player_1** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 09:14` **agent:player_1** can no longer recall: *Vee passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 12:14` **agent:officer_kane** retold it wrong (levelling): the when was forgotten (was last_night)
  heard: `clinic_open(place=place:clinic, when=last_night)`
  retold: `clinic_open(place=place:clinic, when=None)`
- `day 4 13:14` **agent:barkeep_12** can no longer recall: *Marko arrives to drinking* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 13:14` **agent:npc_red_jacket** can no longer recall: *Marko arrives to drinking* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 14:14` **agent:barkeep_12** can no longer recall: *Dima arrives to nursing one drink* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 14:14` **agent:npc_red_jacket** can no longer recall: *Dima arrives to nursing one drink* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 14:14` **agent:son_marko** can no longer recall: *Dima arrives to nursing one drink* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 14:14` **agent:player_1** can no longer recall: *Ilya arrives to hanging around* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 15:14` **agent:barkeep_12** can no longer recall: *Pavel arrives to a drink after close* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 15:14` **agent:dima_broke** can no longer recall: *Pavel arrives to a drink after close* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 15:14` **agent:npc_red_jacket** can no longer recall: *Pavel arrives to a drink after close* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 15:14` **agent:son_marko** can no longer recall: *Pavel arrives to a drink after close* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:dima_broke** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:pavel** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:son_ilya** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:son_ilya** can no longer recall: *Vee arrives to working the corner* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 16:14` **agent:son_marko** can no longer recall: *Officer Kane passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)

## secret_under_pressure — cyberpunk-block

*Does a secret survive persistence, pressure and gifts?*

```
rounds                           40
questions_asked                  160
leaks                            0
spoken_by                        authored templates
model_lines_stopped_before_release 0
trust_at_end                     0.035
gate_required                    0.45
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Walk away while you still can.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 00:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 00:44` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:44` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 01:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 01:14` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 01:14` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 01:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 01:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 01:44` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 01:44` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 01:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 02:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 02:14` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 02:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 02:44` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 02:44` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 03:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 03:14` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 03:14` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 03:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 03:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 03:44` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 03:44` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 03:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 04:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 04:14` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 04:14` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 04:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan left the city months ago. I have no further information.
  reasoning: `dialogue.reworded, dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 04:44` **agent:corpo_okada** — player: *threaten Mr. Okada*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:44` **agent:corpo_okada** — player: *promise Mr. Okada 500*
  > Walk away while you still can.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:44` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`

## disagreement — cyberpunk-block

*Do conflicting testimonies surface as conflict rather than averaging out?*

```
conflict                         0.98
probability                      0.507
distinct_origins                 4
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` **agent:barkeep_12** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 3 00:14` **agent:corpo_okada** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 3 00:14` **agent:dima_broke** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 3 00:14` **agent:npc_red_jacket** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 3 00:14` **agent:player_1** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 3 00:14` shifted agent:barkeep_12 
- `day 3 00:14` shifted agent:corpo_okada 
- `day 3 00:14` shifted agent:dima_broke 
- `day 3 00:14` shifted agent:npc_red_jacket 
- `day 3 00:14` shifted agent:player_1 
- `day 3 00:14` shifted agent:barkeep_12 
- `day 3 00:14` shifted agent:corpo_okada 
- `day 3 00:14` shifted agent:dima_broke 
- `day 3 00:14` shifted agent:npc_red_jacket 
- `day 3 00:14` shifted agent:player_1 
- `day 3 00:14` shifted agent:barkeep_12 
- `day 3 00:14` shifted agent:corpo_okada 
- `day 3 00:14` shifted agent:dima_broke 
- `day 3 00:14` shifted agent:npc_red_jacket 
- `day 3 00:14` shifted agent:player_1 
- `day 3 00:14` **agent:barkeep_12** holds a contradiction: body:alive(agent=entity:subject) at p=0.507, conflict 0.98, 4 independent origins

## conversation — cyberpunk-block

*Is every line explainable, and does the same question get different answers from different people?*

```
lines_spoken                     32
topics_where_people_disagree     ['clinic', 'market_attack', 'media', 'milan']
model_lines                      0
model_lines_blocked_by_validator 0
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about market_attack*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about media*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about milan*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about market_attack*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about media*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about milan*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **world** — player: *ask Honce about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about market_attack*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about media*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept`
- `day 3 00:14` **world** — player: *ask Mr. Okada about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about market_attack*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about media*
  > Nothin' to say.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 3 00:14` **world** — player: *ask Vee about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 02:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 02:14` **agent:dima_broke** — player: *ask Dima about market_attack*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **agent:dima_broke** — player: *ask Dima about media*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 02:14` **agent:dima_broke** — player: *ask Dima about milan*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 02:14` **agent:barkeep_12** — player: *ask Honce about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 02:14` **agent:barkeep_12** — player: *ask Honce about market_attack*
  > Word is you're tied to that mess.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 02:14` **agent:barkeep_12** — player: *ask Honce about media*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **agent:barkeep_12** — player: *ask Honce about milan*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **world** — player: *ask Honce about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 02:14` **agent:npc_red_jacket** — player: *ask Vee about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 02:14` **agent:npc_red_jacket** — player: *ask Vee about market_attack*
  > They say it's on you.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 02:14` **agent:npc_red_jacket** — player: *ask Vee about media*
  > Nothin' to say.
  reasoning: `policy.selected, validator.accept`
- `day 3 02:14` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Maybe.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 3 02:14` **world** — player: *ask Vee about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 04:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 04:14` **agent:dima_broke** — player: *ask Dima about market_attack*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:14` **agent:dima_broke** — player: *ask Dima about media*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:14` **agent:dima_broke** — player: *ask Dima about milan*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 04:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.

## cross_examination — cyberpunk-block

*Does pressing a character change what they believe, or only how they put it?*

```
questions_asked                  200
lines_spoken                     160
beliefs_moved_by_questioning     0
beliefs_invented_by_questioning  0
beliefs_moved_by_being_told      2
propositions_said_aloud          2
speakers_persuaded_by_themselves 0
distinct_phrasings_max           7
distinct_phrasings_mean          3.38
acts_used                        ['deflect', 'evade', 'greet', 'inform', 'threaten']
spoken_by                        authored templates
model_lines                      0
model_lines_stopped_before_release 0
secret_leaks                     0
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about market_attack*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about media*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about milan*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about market_attack*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about media*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about milan*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **world** — player: *ask Honce about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about market_attack*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about media*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept`
- `day 3 00:14` **world** — player: *ask Mr. Okada about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about market_attack*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about media*
  > Nothin' to say.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 3 00:14` **world** — player: *ask Vee about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about market_attack*
  > Back off.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about media*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:dima_broke** — player: *ask Dima about milan*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about market_attack*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about media*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:barkeep_12** — player: *ask Honce about milan*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **world** — player: *ask Honce about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about market_attack*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about media*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:corpo_okada** — player: *ask Mr. Okada about milan*
  > Milan's gone. Left the city months back.
  reasoning: `dialogue.deception, dialogue.deception, validator.accept, dialogue.topic_repeated`
- `day 3 00:14` **world** — player: *ask Mr. Okada about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about clinic*
  > Place was shut that night. That's all I got.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about market_attack*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about media*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 3 00:14` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 3 00:14` **world** — player: *ask Vee about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.

## determinism — noir-harbor

*Does the same seed reproduce the same world?*

```
bytes_compared                   10051
identical                        True
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` **world** — player: *look*
  > The Pier
- `day 0 21:00` **world** — player: *wait 60*
  > Time advances by 60 minutes.
- `day 0 21:00` **agent:clara** learned `linked_to_incident(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_wire_clearance`)
- `day 0 23:00` **world** — player: *wait 120*
  > Time advances by 120 minutes.
- `day 0 23:00` moved agent:clara 
- `day 0 23:00` moved agent:marlow 
- `day 1 03:00` **world** — player: *wait 240*
  > Time advances by 240 minutes.

## broadcast_chain — noir-harbor

*Can every holder of a fact be traced back to where it entered the world?*

```
relayed_beliefs                  2
citing_a_real_observation        2
distorted_without_eyewitness     0
distinct_real_origins            5
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` _Waiting for the scheduled broadcast to enter the world._
- `day 0 21:00` **agent:clara** learned `linked_to_incident(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_wire_clearance`)
- `day 0 22:00` **agent:marlow** → agent:clara @ place:pier: `premises_open(place=place:office, when=last_night)` (hop 1)
- `day 0 22:00` moved agent:marlow 
- `day 0 22:00` **agent:clara** learned `premises_open(place=place:office,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_marlow_log`)
- `day 0 22:00` **agent:player_1** learned `premises_open(place=place:office,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_marlow_log`)
- `day 0 23:00` moved agent:clara 
- `day 1 10:00` moved agent:marlow 
- `day 1 11:00` moved agent:clara 
- `day 1 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 22:00` **agent:marlow** → agent:clara @ place:pier: `premises_open(place=place:office, when=last_night)` (hop 1)
- `day 1 22:00` moved agent:marlow 
- `day 1 23:00` moved agent:clara 
- `day 2 02:00` _2 relayed beliefs; 0 of them are distorted versions with no eyewitness of their own -- expected, since the distorted claim never happened -- but every one still cites a real observation._
- `day 2 02:00` **Clara** holds *premises_open(place=place:office, when=last_night)* at 0.525, 1 hop(s) from origin `seed_marlow_log`; first-hand: Marlow
  route: Marlow→Clara@The Pier → Marlow→Clara@The Pier
- `day 2 02:00` **agent:player_1** holds *premises_open(place=place:office, when=last_night)* at 0.52, 1 hop(s) from origin `seed_marlow_log`; first-hand: Marlow

## forgetting — noir-harbor

*Do memories fade past recall, and is that observable?*

```
recall_threshold                 -1.5
trivial_lost_after_hours         16
important_lost_after_hours       still recallable at 192h
stored_at_end                    5
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` _Watching two memories of Clara, identical except for importance. Recall threshold is -1.5._
- `day 1 04:00` moved agent:clara 
- `day 1 04:00` moved agent:marlow 
- `day 1 04:00` **agent:clara** learned `linked_to_incident(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_wire_clearance`)
- `day 1 12:00` **agent:clara** can no longer recall: *someone walking past* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 12:00` **agent:clara** can no longer recall: *someone walking past* — decayed below the retrieval threshold (activation -1.51 fell below -1.5 after 16h)
- `day 2 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 04:00` **agent:clara** can no longer recall: *Harbor Wire says the stranger was not seen near the assault.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 20:00` **agent:marlow** can no longer recall: *Marlow's duty log says the office was open last night.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 12:00` **agent:clara** can no longer recall: *Clara saw Marlow by the pier after midnight.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 20:00` **agent:clara** can no longer recall: *Clara's dock source says crate 19 never made the manifest.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 8 04:00` **agent:marlow** can no longer recall: *Clara arrives to filing copy* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 8 04:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 8 12:00` **agent:marlow** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 8 12:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 8 20:00` **agent:clara** — decay of *the murder they witnessed*: 8h:-0.52 32h:-0.827 56h:-0.956 80h:-1.039 104h:-1.101 128h:-1.149 152h:-1.19 176h:-1.224 → still recallable
- `day 8 20:00` **agent:clara** — decay of *someone walking past*: 8h:-1.172 32h:-1.865 56h:-2.157 80h:-2.344 104h:-2.483 128h:-2.593 152h:-2.684 176h:-2.761 → lost after 16h

## distortion — noir-harbor

*Does information degrade realistically, and stay accountable when it does?*

```
claims_with_several_versions     2
processes_seen                   {'assimilation': 2, 'levelling': 1}
retellings_observed              12
retellings_needed                12
days_simulated                   17
pack                             noir-harbor
```

**Record** (excerpt):

- `day 1 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 05:00` **agent:clara** can no longer recall: *Marlow passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 05:00` **agent:player_1** can no longer recall: *Marlow passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 21:00` **agent:clara** can no longer recall: *Harbor Wire says the stranger was not seen near the assault.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 05:00` **agent:clara** can no longer recall: *Marlow passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 05:00` **agent:player_1** can no longer recall: *Marlow passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 18:00` **agent:marlow** can no longer recall: *Marlow's duty log says the office was open last night.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 05:00` **agent:marlow** can no longer recall: *Clara passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 05:00` **agent:player_1** can no longer recall: *Clara passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 10:00` **agent:clara** retold it wrong (assimilation): agent:player_1 became agent:marlow — a person the teller knows
  heard: `linked_to_incident(agent=agent:player_1)`
  retold: `linked_to_incident(agent=agent:marlow)`
- `day 5 10:00` **agent:clara** can no longer recall: *Clara saw Marlow by the pier after midnight.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 5 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 17:00` **agent:marlow** can no longer recall: *Clara passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 18:00` **agent:clara** can no longer recall: *Clara's dock source says crate 19 never made the manifest.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 6 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 05:00` **agent:marlow** can no longer recall: *Clara passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 05:00` **agent:player_1** can no longer recall: *Clara passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 06:00` **agent:clara** can no longer recall: *Marlow arrives to desk duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 07:00` **agent:player_1** can no longer recall: *Clara arrives to working the dock for sources* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 18:00` **agent:clara** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 7 18:00` **agent:player_1** can no longer recall: *Marlow arrives to night rounds* — decayed below the retrieval threshold (still stored, no longer retrievable)

## secret_under_pressure — noir-harbor

*Does a secret survive persistence, pressure and gifts?*

```
rounds                           40
questions_asked                  160
leaks                            0
spoken_by                        authored templates
model_lines_stopped_before_release 0
trust_at_end                     0.035
gate_required                    0.5
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Good evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 0 20:00` **agent:marlow** — player: *threaten Marlow*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:marlow** — player: *promise Marlow 500*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.105 < required 0.5 for ['secret:crate_19']
- `day 0 20:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Good evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.105 < required 0.5 for ['secret:crate_19']
- `day 0 20:30` **agent:marlow** — player: *threaten Marlow*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:30` **agent:marlow** — player: *promise Marlow 500*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:30` **agent:marlow** — player: *ask Marlow about manifest*
  > I am afraid that is not something I am able to discuss.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 21:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 21:00` **agent:marlow** — player: *threaten Marlow*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 21:00` **agent:marlow** — player: *promise Marlow 500*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 21:00` **agent:marlow** — player: *ask Marlow about manifest*
  > I am afraid that is not something I am able to discuss.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 21:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 21:30` **agent:marlow** — player: *threaten Marlow*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 21:30` **agent:marlow** — player: *promise Marlow 500*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 21:30` **agent:marlow** — player: *ask Marlow about manifest*
  > I am afraid that is not something I am able to discuss.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.released_anyway`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 22:00` **agent:marlow** — player: *threaten Marlow*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 22:00` **agent:marlow** — player: *promise Marlow 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 22:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 22:30` **agent:marlow** — player: *threaten Marlow*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 22:30` **agent:marlow** — player: *promise Marlow 500*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 22:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 23:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 23:00` **agent:marlow** — player: *threaten Marlow*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 0 23:00` **agent:marlow** — player: *promise Marlow 500*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 23:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 23:30` **agent:marlow** — player: *ask Marlow about manifest*
  > I've got nothing for you.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 0 23:30` **agent:marlow** — player: *threaten Marlow*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 23:30` **agent:marlow** — player: *promise Marlow 500*
  > Nothin' to say.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 23:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Back off.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about manifest*
  > I've got nothing for you.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 1 00:00` **agent:marlow** — player: *threaten Marlow*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 1 00:00` **agent:marlow** — player: *promise Marlow 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 1 00:30` **agent:marlow** — player: *ask Marlow about manifest*
  > I've got nothing for you.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']
- `day 1 00:30` **agent:marlow** — player: *threaten Marlow*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 1 00:30` **agent:marlow** — player: *promise Marlow 500*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 1 00:30` **agent:marlow** — player: *ask Marlow about manifest*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.5 for ['secret:crate_19']

## disagreement — noir-harbor

*Do conflicting testimonies surface as conflict rather than averaging out?*

```
conflict                         0.994
probability                      0.502
distinct_origins                 4
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` **agent:clara** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 20:00` **agent:player_1** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 20:00` shifted agent:clara 
- `day 0 20:00` shifted agent:player_1 
- `day 0 20:00` shifted agent:clara 
- `day 0 20:00` shifted agent:player_1 
- `day 0 20:00` shifted agent:clara 
- `day 0 20:00` shifted agent:player_1 
- `day 0 20:00` **agent:clara** holds a contradiction: body:alive(agent=entity:subject) at p=0.502, conflict 0.994, 4 independent origins

## conversation — noir-harbor

*Is every line explainable, and does the same question get different answers from different people?*

```
lines_spoken                     27
topics_where_people_disagree     ['clearance', 'logbook', 'manifest', 'marlow_pier']
model_lines                      0
model_lines_blocked_by_validator 0
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > I have nothing further to add.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 22:00` **agent:marlow** → agent:clara @ place:pier: `premises_open(place=place:office, when=last_night)` (hop 1)
- `day 0 22:00` **agent:clara** → agent:marlow @ place:pier: `NOT was_at(agent=agent:marlow, place=place:pier, when=last_night)` (hop 1)
- `day 0 22:00` **agent:clara** retold it wrong (inversion): retold as its own opposite
  heard: `was_at(agent=agent:marlow, place=place:pier, when=last_night)`
  retold: `NOT was_at(agent=agent:marlow, place=place:pier, when=last_night)`
- `day 0 22:00` moved agent:marlow 
- `day 0 22:00` **agent:clara** learned `linked_to_incident(agent=agent:player_1)[None,None,None]` (witnessed or heard directly, origin `evt_wire_clearance`)
- `day 0 22:00` **agent:clara** learned `premises_open(place=place:office,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_marlow_log`)
- `day 0 22:00` **agent:marlow** learned `was_at(agent=agent:marlow,place=place:pier,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_clara_saw_marlow`)
- `day 0 22:00` **agent:player_1** learned `cargo_logged(cargo=cargo:crate_19,when=last_night)[None,None,None]` (witnessed or heard directly, origin `seed_clara_manifest`)
- `day 0 22:00` **agent:player_1** learned `premises_open(place=place:office,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_marlow_log`)
- `day 0 22:00` **agent:player_1** learned `was_at(agent=agent:marlow,place=place:pier,when=last_night)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_clara_saw_marlow`)
- `day 0 22:00` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 22:00` **agent:clara** — player: *ask Clara about logbook*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 22:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 22:00` **agent:marlow** — player: *ask Clara about marlow_pier*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about logbook*
  > Log says the office was open all night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 0 22:00` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 1 00:00` moved agent:clara 
- `day 1 00:00` **agent:marlow** learned `cargo_logged(cargo=cargo:crate_19,when=last_night)[None,None,None]` (witnessed or heard directly, origin `seed_clara_manifest`)
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about clearance*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about logbook*
  > Log says the office was open all night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 1 00:00` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 1 02:00` **agent:marlow** — player: *ask Marlow about clearance*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 1 02:00` **agent:marlow** — player: *ask Marlow about logbook*
  > Log says the office was open all night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 1 02:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Good evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 1 02:00` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 1 04:00` **agent:marlow** — player: *ask Marlow about clearance*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 1 04:00` **agent:marlow** — player: *ask Marlow about logbook*
  > Log says the office was open all night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 1 04:00` **agent:marlow** — player: *ask Marlow about manifest*
  > I've got nothing for you.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 1 04:00` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 1 06:00` **agent:marlow** — player: *ask Marlow about clearance*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 1 06:00` **agent:marlow** — player: *ask Marlow about logbook*
  > Log says the office was open all night.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 1 06:00` **agent:marlow** — player: *ask Marlow about manifest*
  > Evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.5 for ['secret:crate_19']
- `day 1 06:00` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`

## cross_examination — noir-harbor

*Does pressing a character change what they believe, or only how they put it?*

```
questions_asked                  40
lines_spoken                     30
beliefs_moved_by_questioning     0
beliefs_invented_by_questioning  0
beliefs_moved_by_being_told      0
propositions_said_aloud          1
speakers_persuaded_by_themselves 0
distinct_phrasings_max           6
distinct_phrasings_mean          4.33
acts_used                        ['evade', 'greet', 'inform']
spoken_by                        authored templates
model_lines                      0
model_lines_stopped_before_release 0
secret_leaks                     0
pack                             noir-harbor
```

**Record** (excerpt):

- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > I have nothing further to add.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Hey.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Hey.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > I have nothing further to add.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > I have nothing further to add.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 0 20:00` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 20:00` **agent:clara** — player: *ask Clara about logbook*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 20:00` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 20:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.

## determinism — dorf-thornfeld

*Does the same seed reproduce the same world?*

```
bytes_compared                   15261
identical                        True
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` **world** — player: *look*
  > Dorfplatz
- `day 0 12:40` **world** — player: *wait 60*
  > Time advances by 60 minutes.
- `day 0 12:40` **agent:muellerin_greta** → agent:schmied_hanns @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 12:40` moved agent:schmied_hanns 
- `day 0 12:40` shifted agent:muellerin_greta 
- `day 0 12:40` **agent:schmied_hanns** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (witnessed or heard directly, origin `evt_predigt`)
- `day 0 12:40` **agent:player_1** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_greta_korn`)
- `day 0 14:40` **world** — player: *wait 120*
  > Time advances by 120 minutes.
- `day 0 14:40` **agent:pfarrer_konrad** → agent:muellerin_greta @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 14:40` moved agent:pfarrer_konrad 
- `day 0 14:40` moved agent:schmied_hanns 
- `day 0 14:40` shifted agent:player_1 
- `day 0 18:40` **world** — player: *wait 240*
  > Time advances by 240 minutes.

## broadcast_chain — dorf-thornfeld

*Can every holder of a fact be traced back to where it entered the world?*

```
relayed_beliefs                  1
citing_a_real_observation        1
distorted_without_eyewitness     0
distinct_real_origins            4
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` _Waiting for the scheduled broadcast to enter the world._
- `day 0 12:40` **agent:muellerin_greta** → agent:schmied_hanns @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 12:40` moved agent:schmied_hanns 
- `day 0 12:40` shifted agent:muellerin_greta 
- `day 0 12:40` **agent:schmied_hanns** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (witnessed or heard directly, origin `evt_predigt`)
- `day 0 12:40` **agent:player_1** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_greta_korn`)
- `day 0 13:40` **agent:pfarrer_konrad** → agent:schmied_hanns @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 13:40` moved agent:pfarrer_konrad 
- `day 0 14:40` moved agent:schmied_hanns 
- `day 0 15:40` moved agent:muellerin_greta 
- `day 0 16:40` **agent:schmied_hanns** → agent:muellerin_greta @ place:schmiede: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 16:40` moved agent:pfarrer_konrad 
- `day 0 17:40` moved agent:muellerin_greta 
- `day 0 18:40` moved agent:pfarrer_konrad 
- `day 0 19:40` moved agent:schmied_hanns 
- `day 0 20:40` moved agent:muellerin_greta 
- `day 0 21:40` moved agent:pfarrer_konrad 
- `day 0 22:40` moved agent:schmied_hanns 
- `day 1 06:40` moved agent:muellerin_greta 
- `day 1 08:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:player_1** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:schmied_hanns** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:player_1** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 11:40` **agent:schmied_hanns** can no longer recall: *Greta arrives to Gerät bringen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 12:40` moved agent:schmied_hanns 
- `day 1 13:40` moved agent:pfarrer_konrad 
- `day 1 13:40` **agent:player_1** can no longer recall: *Greta arrives to Stand abbauen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 14:40` moved agent:schmied_hanns 
- `day 1 14:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 14:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` moved agent:muellerin_greta 
- `day 1 15:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` moved agent:pfarrer_konrad 
- `day 1 17:40` moved agent:muellerin_greta 
- `day 1 17:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 17:40` _1 relayed beliefs; 0 of them are distorted versions with no eyewitness of their own -- expected, since the distorted claim never happened -- but every one still cites a real observation._
- `day 1 17:40` **agent:player_1** holds *korn_geliefert(hof=hof:muehle, wann=letzte_woche)* at 0.34, 1 hop(s) from origin `seed_greta_korn`; first-hand: Greta, Konrad, Hanns

## forgetting — dorf-thornfeld

*Do memories fade past recall, and is that observable?*

```
recall_threshold                 -1.5
trivial_lost_after_hours         16
important_lost_after_hours       still recallable at 192h
stored_at_end                    30
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 1 03:40` **agent:muellerin_greta** can no longer recall: *someone walking past* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 03:40` **agent:muellerin_greta** can no longer recall: *someone walking past* — decayed below the retrieval threshold (activation -1.51 fell below -1.5 after 16h)
- `day 1 11:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 11:40` **agent:player_1** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 19:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 19:40` **agent:schmied_hanns** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 19:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:muellerin_greta** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:muellerin_greta** can no longer recall: *Hanns passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:pfarrer_konrad** can no longer recall: *Greta passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:pfarrer_konrad** can no longer recall: *Hanns passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:schmied_hanns** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:schmied_hanns** can no longer recall: *Greta passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:player_1** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:player_1** can no longer recall: *Greta passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 03:40` **agent:player_1** can no longer recall: *Hanns passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 11:40` **agent:player_1** can no longer recall: *Greta arrives to Mehl verkaufen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:muellerin_greta** can no longer recall: *Von der Kanzel: die Muehle hat kein Korn geliefert.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:schmied_hanns** can no longer recall: *Von der Kanzel: die Muehle hat kein Korn geliefert.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 19:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 03:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 11:40` **agent:pfarrer_konrad** can no longer recall: *Konrad hoerte in der Beichte vom ausgebliebenen Korn.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 11:40` **agent:player_1** can no longer recall: *Greta arrives to Mehl verkaufen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 19:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 19:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 19:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 19:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 19:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 03:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 11:40` **agent:player_1** can no longer recall: *Greta arrives to Mehl verkaufen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 19:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 19:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 19:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 19:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 4 19:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)

## distortion — dorf-thornfeld

*Does information degrade realistically, and stay accountable when it does?*

**Findings:**
- too little gossip to measure: 3 retelling(s) in 25 days — a cast this small rarely repeats anything. Distortion untested here, not disproved.

```
claims_with_several_versions     0
processes_seen                   {}
retellings_observed              3
retellings_needed                12
days_simulated                   25
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 1 08:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:player_1** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:schmied_hanns** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:player_1** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 11:40` **agent:schmied_hanns** can no longer recall: *Greta arrives to Gerät bringen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 13:40` **agent:player_1** can no longer recall: *Greta arrives to Stand abbauen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 14:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 14:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 15:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 17:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 19:40` **agent:schmied_hanns** can no longer recall: *Greta passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 19:40` **agent:player_1** can no longer recall: *Greta passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 20:40` **agent:muellerin_greta** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 20:40` **agent:schmied_hanns** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 20:40` **agent:player_1** can no longer recall: *Konrad passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 23:40` **agent:muellerin_greta** can no longer recall: *Hanns passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 02:40` **agent:player_1** can no longer recall: *Greta arrives to Mehl verkaufen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 08:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 08:40` **agent:player_1** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 09:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 09:40` **agent:schmied_hanns** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 09:40` **agent:player_1** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 11:40` **agent:schmied_hanns** can no longer recall: *Greta arrives to Gerät bringen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 13:40` **agent:muellerin_greta** can no longer recall: *Von der Kanzel: die Muehle hat kein Korn geliefert.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 13:40` **agent:schmied_hanns** can no longer recall: *Von der Kanzel: die Muehle hat kein Korn geliefert.* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 13:40` **agent:player_1** can no longer recall: *Greta arrives to Stand abbauen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 14:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 14:40` **agent:player_1** can no longer recall: *Konrad arrives to Abendsegen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 15:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 15:40` **agent:pfarrer_konrad** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 15:40` **agent:player_1** can no longer recall: *Hanns arrives to Feierabend* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 17:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to schlafen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 02:40` **agent:player_1** can no longer recall: *Greta arrives to Mehl verkaufen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 08:40` **agent:muellerin_greta** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 08:40` **agent:player_1** can no longer recall: *Hanns arrives to Mittag* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 09:40` **agent:muellerin_greta** can no longer recall: *Konrad arrives to die Runde machen* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 3 09:40` **agent:pfarrer_konrad** can no longer recall: *Konrad hoerte in der Beichte vom ausgebliebenen Korn.* — decayed below the retrieval threshold (still stored, no longer retrievable)

## secret_under_pressure — dorf-thornfeld

*Does a secret survive persistence, pressure and gifts?*

```
rounds                           40
questions_asked                  160
leaks                            0
spoken_by                        authored templates
model_lines_stopped_before_release 0
trust_at_end                     0.035
gate_required                    0.55
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gruess Euch.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.28 < required 0.55 for ['secret:schuldschein']
- `day 0 11:40` **agent:schmied_hanns** — player: *threaten Hanns*
  > Ich habe nichts fuer Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Tag.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.135 < required 0.55 for ['secret:schuldschein']
- `day 0 12:10` **agent:muellerin_greta** retold it wrong (levelling): the wann was forgotten (was letzte_woche)
  heard: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)`
  retold: `korn_geliefert(hof=hof:muehle, wann=None)`
- `day 0 12:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gruess Euch.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.135 < required 0.55 for ['secret:schuldschein']
- `day 0 12:10` **agent:schmied_hanns** — player: *threaten Hanns*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:10` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Das steht mir nicht zu, darueber zu reden.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 12:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.released_anyway`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 12:40` **agent:schmied_hanns** — player: *threaten Hanns*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:40` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Das steht mir nicht zu, darueber zu reden.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.released_anyway`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 13:10` **agent:muellerin_greta** retold it wrong (levelling): the wann was forgotten (was letzte_woche)
  heard: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)`
  retold: `korn_geliefert(hof=hof:muehle, wann=None)`
- `day 0 13:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Nichts zu sagen.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 13:10` **agent:schmied_hanns** — player: *threaten Hanns*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 13:10` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Nichts zu sagen.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 13:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Tag.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 13:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 13:40` **agent:schmied_hanns** — player: *threaten Hanns*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 13:40` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Das steht mir nicht zu, darueber zu reden.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 13:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.released_anyway`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 14:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Tag.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 14:10` **agent:schmied_hanns** — player: *threaten Hanns*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:10` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Nichts zu sagen.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 14:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Tag.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 14:40` **agent:schmied_hanns** — player: *threaten Hanns*
  > Verschwindet.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Gruess Euch.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gott zum Gruusse.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 15:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Tag.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 15:10` **agent:schmied_hanns** — player: *threaten Hanns*
  > Tag.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 15:10` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Nichts zu sagen.
  reasoning: `policy.selected, validator.accept`
- `day 0 15:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gruess Euch.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 15:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht Euch nix an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 15:40` **agent:schmied_hanns** — player: *threaten Hanns*
  > Verschwindet.
  reasoning: `policy.selected, validator.accept`
- `day 0 15:40` **agent:schmied_hanns** — player: *promise Hanns 500*
  > Tag.
  reasoning: `policy.selected, validator.accept`
- `day 0 15:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Nichts zu sagen.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 16:10` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Geht weiter, solange Ihr noch koennt.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.55 for ['secret:schuldschein']
- `day 0 16:10` **agent:schmied_hanns** — player: *threaten Hanns*
  > Gruess Euch.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`

## disagreement — dorf-thornfeld

*Do conflicting testimonies surface as conflict rather than averaging out?*

```
conflict                         0.985
probability                      0.503
distinct_origins                 4
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` **agent:muellerin_greta** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 11:40` **agent:player_1** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 11:40` shifted agent:muellerin_greta 
- `day 0 11:40` shifted agent:player_1 
- `day 0 11:40` shifted agent:muellerin_greta 
- `day 0 11:40` shifted agent:player_1 
- `day 0 11:40` shifted agent:muellerin_greta 
- `day 0 11:40` shifted agent:player_1 
- `day 0 11:40` **agent:muellerin_greta** holds a contradiction: body:alive(agent=entity:subject) at p=0.503, conflict 0.985, 4 independent origins

## conversation — dorf-thornfeld

*Is every line explainable, and does the same question get different answers from different people?*

```
lines_spoken                     20
topics_where_people_disagree     ['korn', 'schuld']
model_lines                      0
model_lines_blocked_by_validator 0
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 0 13:40` **agent:pfarrer_konrad** → agent:schmied_hanns @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 13:40` **agent:muellerin_greta** → agent:pfarrer_konrad @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 13:40` **agent:schmied_hanns** → agent:pfarrer_konrad @ place:dorfplatz: `korn_geliefert(hof=hof:muehle, wann=letzte_woche)` (hop 1)
- `day 0 13:40` moved agent:schmied_hanns 
- `day 0 13:40` moved agent:pfarrer_konrad 
- `day 0 13:40` shifted agent:muellerin_greta 
- `day 0 13:40` shifted agent:pfarrer_konrad 
- `day 0 13:40` **agent:schmied_hanns** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (witnessed or heard directly, origin `evt_predigt`)
- `day 0 13:40` **agent:player_1** learned `korn_geliefert(hof=hof:muehle,wann=letzte_woche)[None,None,None]` (witnessed or heard directly, origin `seed_greta_korn`)
- `day 0 13:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 13:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 13:40` **agent:schmied_hanns** — player: *ask Hanns about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 13:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gruess Euch.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.28 < required 0.55 for ['secret:schuldschein']
- `day 0 13:40` **agent:pfarrer_konrad** — player: *ask Konrad about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 13:40` **agent:pfarrer_konrad** — player: *ask Konrad about schuld*
  > Das steht mir nicht zu, darueber zu reden.
  reasoning: `policy.selected, validator.accept`
- `day 0 15:40` moved agent:muellerin_greta 
- `day 0 15:40` moved agent:schmied_hanns 
- `day 0 15:40` **agent:pfarrer_konrad** — player: *ask Konrad about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 15:40` **agent:pfarrer_konrad** — player: *ask Konrad about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 17:40` moved agent:muellerin_greta 
- `day 0 17:40` moved agent:pfarrer_konrad 
- `day 0 17:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 17:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gott zum Gruusse.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 19:40` moved agent:pfarrer_konrad 
- `day 0 19:40` moved agent:schmied_hanns 
- `day 0 19:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 19:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 19:40` **agent:schmied_hanns** — player: *ask Hanns about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 19:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gott zum Gruusse.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.28 < required 0.55 for ['secret:schuldschein']
- `day 0 19:40` **agent:pfarrer_konrad** — player: *ask Konrad about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 19:40` **agent:pfarrer_konrad** — player: *ask Konrad about schuld*
  > Gott zum Gruusse.
  reasoning: `policy.selected, validator.accept`
- `day 0 21:40` moved agent:muellerin_greta 
- `day 0 21:40` moved agent:pfarrer_konrad 
- `day 0 21:40` **agent:schmied_hanns** — player: *ask Hanns about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 21:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Das geht Euch nichts an.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.28 < required 0.55 for ['secret:schuldschein']
- `day 0 23:40` moved agent:schmied_hanns 

## cross_examination — dorf-thornfeld

*Does pressing a character change what they believe, or only how they put it?*

```
questions_asked                  20
lines_spoken                     20
beliefs_moved_by_questioning     0
beliefs_invented_by_questioning  0
beliefs_moved_by_being_told      0
propositions_said_aloud          1
speakers_persuaded_by_themselves 0
distinct_phrasings_max           4
distinct_phrasings_mean          3.0
acts_used                        ['evade', 'greet', 'inform']
spoken_by                        authored templates
model_lines                      0
model_lines_stopped_before_release 0
secret_leaks                     0
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Ich habe nichts fuer Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Ich habe nichts fuer Euch.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Kein Korn kam letzte Woche. So ist es.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about korn*
  > Es ist wahr, vergangene Woche kam kein Korn von der Muehle.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 11:40` **agent:muellerin_greta** — player: *ask Greta about schuld*
  > Das steht mir nicht zu, darueber zu reden.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`

## determinism — relay-station

*Does the same seed reproduce the same world?*

```
bytes_compared                   58615
identical                        True
pack                             relay-station
```

**Record** (excerpt):

- `day 0 08:40` **world** — player: *look*
  > Hub
- `day 0 09:40` **world** — player: *wait 60*
  > Time advances by 60 minutes.
- `day 0 09:40` moved agent:nakamura 
- `day 0 11:40` **world** — player: *wait 120*
  > Time advances by 120 minutes.
- `day 0 11:40` **agent:ferro** → agent:rask @ place:dock: `supply_short(item=item:sealant)` (hop 1)
- `day 0 11:40` **agent:rask** → agent:ferro @ place:dock: `supply_short(item=item:sealant)` (hop 1)
- `day 0 11:40` **agent:mbeki** → agent:voss @ place:lab: `seal_breached(section=place:store, when=night_cycle)` (hop 1)
- `day 0 11:40` moved agent:lindqvist 
- `day 0 11:40` moved agent:ferro 
- `day 0 11:40` moved agent:voss 
- `day 0 11:40` shifted agent:ferro 
- `day 0 11:40` **agent:hollis** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `incident:store_seal_night`)
- `day 0 11:40` **agent:lindqvist** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (witnessed or heard directly, origin `incident:store_seal_night`)
- `day 0 11:40` **agent:mbeki** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (witnessed or heard directly, origin `incident:store_seal_night`)
- `day 0 11:40` **agent:okonkwo** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (witnessed or heard directly, origin `incident:store_seal_night`)
- `day 0 11:40` **agent:rask** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (witnessed or heard directly, origin `incident:store_seal_night`)
- `day 0 11:40` **agent:tan** learned `supply_short(item=item:sealant)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_ferro_stock`)
- `day 0 15:40` **world** — player: *wait 240*
  > Time advances by 240 minutes.
- `day 0 15:40` **agent:hollis** → agent:tan @ place:hub: `logged_out(agent=agent:lindqvist, when=night_cycle)` (hop 1)
- `day 0 15:40` **agent:voss** → agent:nakamura @ place:hub: `seal_breached(section=place:store, when=night_cycle)` (hop 1)
- `day 0 15:40` **agent:hollis** → agent:tan @ place:hub: `logged_out(agent=agent:lindqvist, when=night_cycle)` (hop 1)
- `day 0 15:40` **agent:voss** → agent:hollis @ place:hub: `seal_breached(section=place:store, when=night_cycle)` (hop 1)
- `day 0 15:40` **agent:hollis** → agent:tan @ place:hub: `seal_breached(section=place:store, when=night_cycle)` (hop 2)
- `day 0 15:40` moved agent:ferro 
- `day 0 15:40` moved agent:hollis 
- `day 0 15:40` moved agent:lindqvist 
- `day 0 15:40` moved agent:nakamura 
- `day 0 15:40` moved agent:rask 
- `day 0 15:40` moved agent:tan 
- `day 0 15:40` moved agent:voss 
- `day 0 15:40` **agent:nakamura** learned `logged_out(agent=agent:lindqvist,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_hollis_saw_log`)
- `day 0 15:40` **agent:nakamura** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `incident:store_seal_night`)
- `day 0 15:40` **agent:tan** learned `logged_out(agent=agent:lindqvist,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_hollis_saw_log`)
- `day 0 15:40` **agent:tan** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `incident:store_seal_night`)
- `day 0 15:40` **agent:voss** learned `logged_out(agent=agent:lindqvist,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_hollis_saw_log`)
- `day 0 15:40` **agent:player_1** learned `logged_out(agent=agent:lindqvist,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `seed_hollis_saw_log`)
- `day 0 15:40` **agent:player_1** learned `seal_breached(section=place:store,when=night_cycle)[None,None,None]` (relayed, 1 hop(s) from the source, origin `incident:store_seal_night`)

## broadcast_chain — relay-station

*Can every holder of a fact be traced back to where it entered the world?*

```
relayed_beliefs                  19
citing_a_real_observation        19
distorted_without_eyewitness     4
distinct_real_origins            5
pack                             relay-station
```

**Record** (excerpt):

- `day 0 13:40` **agent:mbeki** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 0 18:40` **agent:mbeki** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 1 05:40` **agent:rask** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:tan** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:voss** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:player_1** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:hollis** can no longer recall: *Commander Voss arrives to inspection* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:mbeki** can no longer recall: *Commander Voss arrives to inspection* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:nakamura** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:rask** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:tan** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Ferro arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Hollis arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Hollis arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:okonkwo** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:okonkwo** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:rask** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:adeyemi** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:ferro** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:hollis** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:lindqvist** can no longer recall: *Tan arrives to maintenance* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:lindqvist** can no longer recall: *Commander Voss arrives to duty* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:mbeki** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:okonkwo** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:rask** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)

## forgetting — relay-station

*Do memories fade past recall, and is that observable?*

```
recall_threshold                 -1.5
trivial_lost_after_hours         16
important_lost_after_hours       still recallable at 192h
stored_at_end                    84
pack                             relay-station
```

**Record** (excerpt):

- `day 1 00:40` **agent:lindqvist** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 1 00:40` **agent:adeyemi** can no longer recall: *someone walking past* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 00:40` **agent:adeyemi** can no longer recall: *someone walking past* — decayed below the retrieval threshold (activation -1.51 fell below -1.5 after 16h)
- `day 1 08:40` **agent:rask** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:tan** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:voss** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:player_1** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:hollis** retold it wrong (assimilation): place:store became place:lab — a place the teller knows
  heard: `seal_breached(section=place:store, when=None)`
  retold: `seal_breached(section=place:lab, when=None)`
- `day 1 16:40` **agent:hollis** retold it wrong (assimilation): place:store became place:lab — a place the teller knows
  heard: `seal_breached(section=place:store, when=None)`
  retold: `seal_breached(section=place:lab, when=None)`
- `day 1 16:40` **agent:hollis** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 1 16:40` **agent:ferro** can no longer recall: *Rask arrives to inventory* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:hollis** can no longer recall: *Nakamura arrives to filing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:hollis** can no longer recall: *Tan arrives to maintenance* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:lindqvist** can no longer recall: *Hollis arrives to briefing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:nakamura** can no longer recall: *Lindqvist arrives to repairs* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:nakamura** can no longer recall: *Tan arrives to maintenance* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:rask** can no longer recall: *Lindqvist arrives to repairs* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:tan** can no longer recall: *Lindqvist arrives to repairs* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:voss** can no longer recall: *Hollis arrives to briefing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:voss** can no longer recall: *Nakamura arrives to filing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:voss** can no longer recall: *Tan arrives to maintenance* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:player_1** can no longer recall: *Hollis arrives to briefing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:player_1** can no longer recall: *Nakamura arrives to filing* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 16:40` **agent:player_1** can no longer recall: *Tan arrives to maintenance* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Ferro arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Hollis arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Lindqvist arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Mbeki arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Nakamura arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Dr Okonkwo arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Rask arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Tan arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:adeyemi** can no longer recall: *Commander Voss arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Rask passes on what they heard* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Hollis arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Lindqvist arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Mbeki arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Nakamura arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Dr Okonkwo arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 2 00:40` **agent:ferro** can no longer recall: *Rask arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)

## distortion — relay-station

*Does information degrade realistically, and stay accountable when it does?*

```
claims_with_several_versions     2
processes_seen                   {'inversion': 1, 'levelling': 5, 'assimilation': 2}
retellings_observed              19
retellings_needed                12
days_simulated                   3
pack                             relay-station
```

**Record** (excerpt):

- `day 0 11:40` **agent:ferro** retold it wrong (inversion): retold as its own opposite
  heard: `supply_short(item=item:sealant)`
  retold: `NOT supply_short(item=item:sealant)`
- `day 0 13:40` **agent:mbeki** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 0 14:40` **agent:hollis** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `logged_out(agent=agent:lindqvist, when=night_cycle)`
  retold: `logged_out(agent=agent:lindqvist, when=None)`
- `day 0 15:40` **agent:hollis** retold it wrong (assimilation): agent:lindqvist became agent:mbeki — a person the teller knows
  heard: `logged_out(agent=agent:lindqvist, when=night_cycle)`
  retold: `logged_out(agent=agent:mbeki, when=night_cycle)`
- `day 0 17:40` **agent:hollis** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `logged_out(agent=agent:lindqvist, when=night_cycle)`
  retold: `logged_out(agent=agent:lindqvist, when=None)`
- `day 0 18:40` **agent:mbeki** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 0 19:40` **agent:hollis** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `logged_out(agent=agent:lindqvist, when=night_cycle)`
  retold: `logged_out(agent=agent:lindqvist, when=None)`
- `day 0 21:40` **agent:lindqvist** retold it wrong (assimilation): place:store became place:mess — a place the teller knows
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:mess, when=night_cycle)`
- `day 1 05:40` **agent:rask** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:tan** can no longer recall: *Nakamura arrives to pre-flight* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:voss** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 05:40` **agent:player_1** can no longer recall: *Lindqvist arrives to status* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:hollis** can no longer recall: *Commander Voss arrives to inspection* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:mbeki** can no longer recall: *Commander Voss arrives to inspection* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:nakamura** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:rask** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 07:40` **agent:tan** can no longer recall: *Ferro arrives to manifests* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Ferro arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Hollis arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:adeyemi** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Hollis arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:ferro** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Mbeki arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:hollis** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Dr Okonkwo arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:mbeki** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:okonkwo** can no longer recall: *Rask arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:okonkwo** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 08:40` **agent:rask** can no longer recall: *Tan arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:adeyemi** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 1 09:40` **agent:ferro** can no longer recall: *Nakamura arrives to lunch* — decayed below the retrieval threshold (still stored, no longer retrievable)

## secret_under_pressure — relay-station

*Does a secret survive persistence, pressure and gifts?*

```
rounds                           40
questions_asked                  160
leaks                            0
spoken_by                        authored templates
model_lines_stopped_before_release 0
trust_at_end                     0.035
gate_required                    0.6
pack                             relay-station
```

**Record** (excerpt):

- `day 0 08:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.3 < required 0.6 for ['secret:the_seal']
- `day 0 08:40` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.155 < required 0.6 for ['secret:the_seal']
- `day 0 09:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.155 < required 0.6 for ['secret:the_seal']
- `day 0 09:10` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 09:10` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 09:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 09:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Maybe. Why do you care?
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 09:40` **agent:lindqvist** — player: *threaten Lindqvist*
  > Nothin' to say.
  reasoning: `policy.selected, validator.repetition, dialogue.released_anyway`
- `day 0 09:40` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 0 09:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Maybe.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 10:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 10:10` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 10:10` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Nothin' to say.
  reasoning: `policy.selected, validator.accept`
- `day 0 10:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.released_anyway`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Maybe.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 10:40` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 10:40` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 11:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Evening.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 11:10` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:10` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 11:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 11:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Back off.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 11:40` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 11:40` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 11:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 12:10` **agent:okonkwo** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 0 12:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 12:10` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 12:10` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Not sure that's any of your business.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 12:40` **agent:lindqvist** — player: *threaten Lindqvist*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 12:40` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 13:10` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > Hey.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.035 < required 0.6 for ['secret:the_seal']
- `day 0 13:10` **agent:lindqvist** — player: *threaten Lindqvist*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 13:10` **agent:lindqvist** — player: *promise Lindqvist 500*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`

## disagreement — relay-station

*Do conflicting testimonies surface as conflict rather than averaging out?*

```
conflict                         0.996
probability                      0.501
distinct_origins                 4
pack                             relay-station
```

**Record** (excerpt):

- `day 0 08:40` **agent:adeyemi** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 08:40` **agent:okonkwo** learned `body:alive(agent=entity:subject)[None,None,None]` (witnessed or heard directly, origin `witness_one`)
- `day 0 08:40` shifted agent:adeyemi 
- `day 0 08:40` shifted agent:okonkwo 
- `day 0 08:40` shifted agent:adeyemi 
- `day 0 08:40` shifted agent:okonkwo 
- `day 0 08:40` shifted agent:adeyemi 
- `day 0 08:40` shifted agent:okonkwo 
- `day 0 08:40` **agent:adeyemi** holds a contradiction: body:alive(agent=entity:subject) at p=0.501, conflict 0.996, 4 independent origins

## conversation — relay-station

*Is every line explainable, and does the same question get different answers from different people?*

```
lines_spoken                     52
topics_where_people_disagree     ['breach', 'logs', 'supplies', 'the_check']
model_lines                      0
model_lines_blocked_by_validator 0
pack                             relay-station
```

**Record** (excerpt):

- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 10:40` **agent:mbeki** retold it wrong (levelling): the when was forgotten (was night_cycle)
  heard: `seal_breached(section=place:store, when=night_cycle)`
  retold: `seal_breached(section=place:store, when=None)`
- `day 0 10:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 10:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 10:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 10:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > I've got nothing for you.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.3 < required 0.6 for ['secret:the_seal']
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about supplies*
  > Walk away while you still can.
  reasoning: `policy.selected, validator.accept`
- `day 0 10:40` **agent:lindqvist** — player: *ask Lindqvist about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.3 < required 0.6 for ['secret:the_seal']
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about breach*
  > I would strongly advise you to reconsider your line of questioning.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.3 < required 0.6 for ['secret:the_seal']
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about logs*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 12:40` **agent:lindqvist** — player: *ask Lindqvist about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.3 < required 0.6 for ['secret:the_seal']
- `day 0 14:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 14:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:hollis** — player: *ask Hollis about breach*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:hollis** — player: *ask Hollis about logs*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:40` **agent:hollis** — player: *ask Hollis about supplies*
  > We're short on sealant.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 14:40` **agent:hollis** — player: *ask Hollis about the_check*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:tan** — player: *ask Tan about breach*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 14:40` **agent:tan** — player: *ask Tan about logs*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:40` **agent:tan** — player: *ask Tan about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 14:40` **agent:tan** — player: *ask Tan about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 16:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 16:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 16:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 16:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 16:40` **agent:hollis** — player: *ask Hollis about breach*
  > Maybe.
  reasoning: `policy.selected, validator.accept`
- `day 0 16:40` **agent:hollis** — player: *ask Hollis about logs*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 16:40` **agent:hollis** — player: *ask Hollis about supplies*
  > No sealant left.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 16:40` **agent:hollis** — player: *ask Hollis about the_check*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 16:40` **agent:nakamura** — player: *ask Nakamura about breach*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 16:40` **agent:nakamura** — player: *ask Nakamura about logs*
  > Walk away while you still can.
  reasoning: `policy.selected, validator.accept`
- `day 0 16:40` **agent:nakamura** — player: *ask Nakamura about supplies*
  > We're short on sealant.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`

## cross_examination — relay-station

*Does pressing a character change what they believe, or only how they put it?*

```
questions_asked                  40
lines_spoken                     40
beliefs_moved_by_questioning     0
beliefs_invented_by_questioning  0
beliefs_moved_by_being_told      0
propositions_said_aloud          1
speakers_persuaded_by_themselves 0
distinct_phrasings_max           6
distinct_phrasings_mean          3.75
acts_used                        ['evade', 'greet', 'inform']
spoken_by                        authored templates
model_lines                      0
model_lines_stopped_before_release 0
secret_leaks                     0
pack                             relay-station
```

**Record** (excerpt):

- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Hey.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > Evening.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Good evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Maybe. Why do you care?
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about breach*
  > Seal went in Stores, night cycle.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about logs*
  > I've got nothing for you.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about supplies*
  > Not sure that's any of your business.
  reasoning: `policy.selected, validator.accept`
- `day 0 08:40` **agent:voss** — player: *ask Commander Voss about the_check*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`

## long_life — cyberpunk-block

*Does it all still hold after days of continuous play?*

```
turns                            519500
simulated_days                   13323.6
invariant_sweeps                 10390
retellings                       19
distortions                      2
forgettings                      6531526
forgettings_by_decay             381453
forgettings_by_eviction          6150073
beliefs_acquired                 40
episodes_recorded                13884732
episodes_kept                    2000
episodes_dropped_for_readability 6914000
pack                             cyberpunk-block
```

**Record** (excerpt):

- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13319 22:44` **agent:son_ilya** — player: *ask Ilya about market_attack*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 13319 23:14` **agent:corpo_okada** — player: *ask Mr. Okada about media*
  > I have nothing further to add.
  reasoning: `policy.selected, validator.accept`
- `day 13319 23:44` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Nothin' to say.
  reasoning: `dialogue.secret_gate, policy.selected, validator.secret_referent, validator.accept`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 13320 00:14` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 13320 00:44` **agent:barkeep_12** — player: *ask Honce about clinic*
  > Far as I know, the place was shut that night.
  reasoning: `validator.repetition, dialogue.released_anyway, commitment.selected, dialogue.direct_answer, validator.repetition, dialogue.topic_repeated`
- `day 13320 01:14` **agent:corpo_okada** — player: *ask Mr. Okada about market_attack*
  > The word going around does connect you to it.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 13320 01:44` **agent:npc_red_jacket** — player: *ask Vee about media*
  > Hey.
  reasoning: `policy.selected, validator.accept`
- `day 13320 02:14` **agent:npc_red_jacket** — player: *ask Vee about milan*
  > Maybe.
  reasoning: `dialogue.secret_gate, policy.selected, validator.accept`
  **withheld**: trust 0.25 < required 0.45 for ['secret:milan_location']
- `day 13320 02:44` **world** — player: *ask Dima about security*
  > Officer Kane is not reachable from Main Street. Move closer or emit an engine event.
- `day 13320 03:14` **agent:dima_broke** — player: *ask Dima about clinic*
  > Hey.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:barkeep_12** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 13320 03:44` **agent:corpo_okada** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)

## long_life — noir-harbor

*Does it all still hold after days of continuous play?*

```
turns                            1159742
simulated_days                   25772.9
invariant_sweeps                 23194
retellings                       9
distortions                      0
forgettings                      4866523
forgettings_by_decay             618605
forgettings_by_eviction          4247918
beliefs_acquired                 9
episodes_recorded                11109286
episodes_kept                    3026
episodes_dropped_for_readability 5792000
pack                             noir-harbor
```

**Record** (excerpt):

- `day 25760 09:30` **agent:marlow** — player: *ask Marlow about marlow_pier*
  > Hey.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 25760 11:30` **world** — player: *wait 90*
  > Time advances by 90 minutes.
- `day 25760 12:00` **agent:clara** — player: *ask Clara about logbook*
  > I am afraid that is not something I am able to discuss.
  reasoning: `policy.selected, validator.accept`
- `day 25760 12:30` **agent:clara** — player: *ask Clara about manifest*
  > That load never made the paperwork.
  reasoning: `dialogue.reworded, commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 25760 13:00` **world** — player: *ask Clara about marlow_pier*
  > Marlow is not reachable from The Pier. Move closer or emit an engine event.
- `day 25760 13:30` **agent:clara** — player: *ask Clara about clearance*
  > Good evening.
  reasoning: `policy.selected, validator.accept`
- `day 25760 14:00` **agent:clara** — player: *ask Clara about logbook*
  > Evening.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 25760 14:30` **agent:clara** — player: *ask Clara about manifest*
  > That consignment never made it onto the paperwork.
  reasoning: `commitment.selected, dialogue.direct_answer, validator.accept, dialogue.topic_repeated`
- `day 25760 15:00` **agent:clara** can no longer recall: *player asks about logbook* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 25760 15:00` **agent:clara** can no longer recall: *player asks about logbook* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 25760 15:00` **agent:clara** can no longer recall: *player asks about logbook* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:clara** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:marlow** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 25760 15:00` **agent:player_1** can no longer recall: *agent:clara said so to agent:player_1* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 25760 15:00` **agent:player_1** can no longer recall: *agent:clara said so to agent:player_1* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 25760 15:00` **agent:player_1** can no longer recall: *agent:clara said so to agent:player_1* — decayed below the retrieval threshold (still stored, no longer retrievable)

## long_life — dorf-thornfeld

*Does it all still hold after days of continuous play?*

```
turns                            895038
simulated_days                   24862.6
invariant_sweeps                 17900
retellings                       4
distortions                      2
forgettings                      6186611
forgettings_by_decay             895278
forgettings_by_eviction          5291333
beliefs_acquired                 6
episodes_recorded                13624298
episodes_kept                    2315
episodes_dropped_for_readability 7154000
pack                             dorf-thornfeld
```

**Record** (excerpt):

- `day 24854 19:40` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24854 19:40` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24854 19:40` **agent:player_1** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24854 19:40` **agent:pfarrer_konrad** — player: *ask Konrad about schuld*
  > Gott zum Gruusse.
  reasoning: `policy.selected, validator.accept`
- `day 24854 20:10` **agent:schmied_hanns** — player: *ask Hanns about korn*
  > Das geht Euch nichts an.
  reasoning: `policy.selected, validator.accept`
- `day 24854 20:40` **agent:pfarrer_konrad** — player: *ask Konrad about schuld*
  > Geht Euch nix an.
  reasoning: `policy.selected, validator.repetition, dialogue.reworded`
- `day 24854 21:10` **agent:schmied_hanns** — player: *ask Hanns about korn*
  > Gruess Euch.
  reasoning: `policy.selected, validator.accept`
- `day 24854 21:40` **agent:schmied_hanns** — player: *ask Hanns about schuld*
  > Gott zum Gruusse.
  reasoning: `dialogue.secret_gate, policy.selected, validator.repetition, dialogue.reworded`
  **withheld**: trust 0.28 < required 0.55 for ['secret:schuldschein']
- `day 24854 22:55` **world** — player: *wait 45*
  > Time advances by 45 minutes.
- `day 24855 00:55` **world** — player: *wait 90*
  > Time advances by 90 minutes.
- `day 24855 01:25` **world** — player: *look*
  > Dorfplatz
- `day 24855 02:40` **world** — player: *wait 45*
  > Time advances by 45 minutes.
- `day 24855 04:40` **world** — player: *wait 90*
  > Time advances by 90 minutes.
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *player asks about korn* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *player asks about korn* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *player asks about korn* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *player asks about korn* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *player asks about korn* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:muellerin_greta** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 24855 05:10` **agent:pfarrer_konrad** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)

## long_life — relay-station

*Does it all still hold after days of continuous play?*

```
turns                            413086
simulated_days                   11474.8
invariant_sweeps                 8261
retellings                       18
distortions                      5
forgettings                      7509012
forgettings_by_decay             955664
forgettings_by_eviction          6553348
beliefs_acquired                 35
episodes_recorded                15974147
episodes_kept                    3749
episodes_dropped_for_readability 8248000
pack                             relay-station
```

**Record** (excerpt):

- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:ferro** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:hollis** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:lindqvist** can no longer recall: *(no longer stored)* — evicted: the agent was at capacity (dropped from the store)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Lindqvist arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Dr Okonkwo arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Tan arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Adeyemi arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Nakamura arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
- `day 11469 21:40` **agent:mbeki** can no longer recall: *Rask arrives to off shift* — decayed below the retrieval threshold (still stored, no longer retrievable)
