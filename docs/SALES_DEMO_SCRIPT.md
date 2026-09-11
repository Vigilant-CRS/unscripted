# Sales Demo Script

Use this flow for a short terminal demonstration.

Start:

```bash
unscripted showcase
```

Interactive terminal:

```bash
unscripted play --debug
```

Automated smoke proof:

```bash
unscripted golden golden/block17_smoke.json
```

## 1. Same Topic, Different Knowledge

```text
ask Vee about Milan
ask Honce about clinic
inspect Vee
inspect Honce
```

Point to make: Vee evades because Milan is protected and trust is low. Honce can
state the clinic was shut because he has non-protected evidence.

## 2. Player Claim Is Not Truth

```text
go market
go police post
tell Kane I am police
inspect Kane
```

Point to make: the claim becomes a belief with provenance and uncertainty. It
does not rewrite canonical world truth. Terminal speech is physical; remote
engine integrations should send explicit events through the SDK.

## 3. Media Propagation

```text
listen radio
inspect Vee
inspect Honce
```

Point to make: only agents with media exposure receive the broadcast claim.

## 4. Off-Screen Social Consequence

```text
go market
attack Pavel
wait 20
inspect Pavel
```

Point to make: Pavel's reactive rule mobilizes allies, arrivals are scheduled by
latency, and the inspector shows memories and reason traces.

## 5. Protected Fact Guard

Run the scripted proof:

```bash
unscripted showcase
```

Point to make: the validator rejects an utterance that names the protected Milan
location, and the secret content never enters the generation context.

## 6. Automatic NPC Fabrication

```bash
unscripted generate-characters --world-pack worldpacks/cyberpunk-block --location place:police_post --appearance uniform --count 2
```

Point to make: environment, role and visible appearance produce structured
personality, values, education, status, goals and starting knowledge without
manual character writing.
