# Unscripted
## Master Reference, Modular Architecture and Implementation Contract v0.9

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Datum:** 22. Juni 2026  
**Status:** verbindlicher Architektur- und Implementierungsentwurf für die Python-Referenzruntime  
**Zielgruppe:** LLM-Coder, Softwarearchitekten, Game-AI-Entwickler und technische Integrationspartner  
**Produktform:** einbettbare Source-Code-Runtime für NPC-Intelligenz  
**Primärer Einsatz:** Spiele mit persistenten, sozial eingebetteten und frei interagierenden NPCs  
**Nicht Teil des Produktkerns:** Rendering, Animation, Navigation, Speech-to-Text, Text-to-Speech, Lippenbewegung, Avatare und Hosting

---

# 0. Verbindlichkeit und Zweck

Dieses Dokument konsolidiert die bisherige Unscripted-Arbeit zu einer einheitlichen, implementierbaren Referenz.

Es ersetzt keine vollständige Ontologie-Registry oder einzelne JSON-Schemas, legt aber verbindlich fest:

- was das Produkt ist;
- welche Komponenten autoritativ sind;
- welche Module eingebaut, extern ersetzt oder abgeschaltet werden können;
- wie lokale und externe Sprachmodelle angebunden werden;
- wie bestehende NPC-Plattformen als Provider oder Bridge integriert werden;
- wie Welt-, Charakter- und Spieldaten importiert werden;
- welche Runtime-Schnittstellen ein Studio erhält;
- wie die Module zusammenarbeiten;
- welche Datenstrukturen und Invarianten ein Coding-Agent einhalten muss;
- welche Ausbaustufen und Tests zur Fertigstellung notwendig sind.

## 0.1 Normative Begriffe

- **MUST / MUSS:** verbindliche Anforderung.
- **SHOULD / SOLLTE:** Standardentscheidung; Abweichung braucht eine dokumentierte Begründung.
- **MAY / KANN:** optionale Funktion.
- **AUTHORITATIVE:** alleinige Quelle eines Zustandsbereichs.
- **BUILTIN:** Unscripted implementiert und besitzt den Zustand.
- **EXTERNAL:** ein Adapter delegiert die Funktion an ein externes System.
- **DISABLED:** die Funktion ist abgeschaltet und liefert einen definierten neutralen Fallback.

## 0.2 Priorität bei widersprüchlichen Dokumenten

Für die Implementierung gilt:

```text
Ausführbare JSON-Schemas und Registry
> dieses Master-Dokument v0.9
> v0.7 Contract-Pack-Starter und Referenzcode
> Ontologie v0.4
> Technical Core v0.2
> ältere Konzeptdokumente
```

Ein Coding-Agent darf bei Widersprüchen nicht raten. Er muss die höhere Quelle verwenden und die Abweichung als Architecture Decision Record dokumentieren.

---

# 1. Endgültige Produktdefinition

> **Unscripted ist eine einbettbare Source-Code-SDK für die Intelligenz sozialer NPCs. Sie bestimmt, was Figuren wahrnehmen, wissen, glauben, erinnern, wollen, sagen und tun sowie wie ihre Interaktionen andere Figuren, Gruppen, Institutionen und die Welt verändern.**

Das Studio behält die Autorität über:

- Rendering;
- Animation;
- Navigation;
- Kampfphysik;
- Inventar;
- Quest-Ausführung;
- UI;
- Audio;
- tatsächliche Aktionsausführung;
- Netzwerk- und Multiplayer-Infrastruktur.

Unscripted besitzt die Intelligenz- und Sozialschicht:

```text
Weltzustand
→ Wahrnehmung
→ subjektives Wissen
→ Erinnerung
→ Persönlichkeit und Motivation
→ soziale Bewertung
→ Dialog- oder Handlungsentscheidung
→ soziale und institutionelle Folgewirkung
```

## 1.1 Kern-USP

Der Kern ist nicht „ein NPC kann sprechen“.

Der Kern ist:

> **Causal Social Memory und Epistemic Social Simulation.**

Unscripted trennt:

- objektive Weltwahrheit;
- individuelle Wahrnehmung;
- kommunizierte Behauptung;
- subjektive Überzeugung;
- Erinnerung;
- Offenlegungsentscheidung;
- tatsächliche Aussage;
- soziale Verbreitung;
- institutionelle und fraktionelle Konsequenz.

## 1.2 Marktbehauptung mit korrekter Einschränkung

Es darf nicht behauptet werden, Unscripted sei absolut das einzige System mit
irgendeiner Form von World Memory oder NPC Memory.

Öffentlich dokumentierte Wettbewerber besitzen bereits unter anderem:

- Charakterwissen;
- Langzeitgedächtnis;
- Beziehungen;
- Ziele;
- emotionale Zustände;
- Narrative Graphs;
- ausführbare Aktionen;
- Observability.

Die öffentlich erkennbare Differenzierung von Unscripted ist die **kombinierte,
engineunabhängige und reproduzierbare Verarbeitung** von:

- objektiver Wahrheit versus subjektivem Glauben;
- Evidenz und Provenienz;
- widersprüchlichen Aussagen;
- korrelierten Gerüchtequellen;
- Vergessen und Erinnerungsverzerrung;
- Beziehungen und Verpflichtungen;
- Orts-, Gruppen- und Institutionsgedächtnis;
- Informationsverbreitung;
- Fraktionsreaktionen;
- geschützten Fakten;
- kausalen Reason Traces.

Die zulässige Aussage lautet:

> Nach öffentlich dokumentiertem Funktionsumfang ist derzeit kein verglichenes Produkt sichtbar, das diese vollständige Kombination als einen eigenständigen, providerunabhängigen Social-Intelligence-Kern anbietet.

Dies ist eine Marktbeobachtung, kein Beweis absoluter Einzigartigkeit und kein Patenturteil.

---

# 2. Produktmodi

Unscripted MUSS vier Betriebsarten unterstützen.

## 2.1 Standalone Intelligence Mode

Unscripted liefert das vollständige NPC-Intelligence-System:

- Wahrnehmung;
- Beliefs;
- Gedächtnis;
- Persönlichkeit;
- Werte;
- Bedürfnisse;
- Beziehungen;
- Ziele;
- Dialogplanung;
- Aktionsentscheidung;
- Informationsverbreitung;
- Fraktionen;
- Textformulierung über Template oder Modellprovider;
- Validierung.

Das Studio benötigt keine konkurrierende NPC-Plattform.

Mögliche Sprachprovider:

- Template Provider;
- lokales Sprachmodell;
- OpenAI-kompatible lokale Runtime;
- Internet-API;
- NVIDIA-basierter Provider;
- kundeneigener Provider.

## 2.2 Headless Intelligence Mode

Unscripted liefert nur strukturierte Intelligenz:

- `NpcDecision`;
- `DialoguePlan`;
- `ActionProposal`;
- `KnowledgeQuery`;
- `SocialEffects`;
- `ReasonTrace`.

Das Studio formuliert Text, führt Aktionen aus und rendert alles selbst.

Dies ist der wichtigste Modus für größere Studios und Source-Code-Kunden.

## 2.3 Bridge Mode

Unscripted besitzt World Memory, Beliefs, Beziehungen und soziale Folgen. Ein
Fremdsystem übernimmt ausgewählte Teile:

- freie Formulierung;
- bestehende Charakterdialoge;
- Voice;
- Narrative Graphs;
- allgemeine Agentenausführung.

Beispiele:

- Inworld als Dialogue/LLM/TTS-Graph;
- Convai als Dialog- und Voice-Frontend;
- Charisma als authorierter Story-Graph;
- NVIDIA Game Agent SDK als lokale Modell- und Tool-Infrastruktur;
- FAtiMA als optionales Appraisal-Modul;
- internes Studio-System als Policy- oder Realizer-Provider.

## 2.4 Partial Module Mode

Ein Studio kann einzelne Unscripted-Module verwenden:

- nur Belief + Provenance;
- nur Memory;
- nur Social Relationships;
- nur Rumor/Faction Layer;
- nur Inspector und Replay;
- nur Validator;
- nur World Memory als Dienst oder Library.

---

# 3. Zentrale Modularitätsregel

Jede Capability besitzt exakt einen Modus:

```text
BUILTIN
EXTERNAL
DISABLED
```

## 3.1 Beispielkonfiguration

```json
{
  "capabilities": {
    "perception":          { "mode": "BUILTIN" },
    "beliefs":             { "mode": "BUILTIN" },
    "memory.personal":     { "mode": "BUILTIN" },
    "affect":              { "mode": "BUILTIN" },
    "relationships":       { "mode": "BUILTIN" },
    "motivation":          { "mode": "BUILTIN" },
    "dialogue.planning":   { "mode": "BUILTIN" },
    "dialogue.realization": {
      "mode": "EXTERNAL",
      "provider": "openai_compatible:local_model"
    },
    "dialogue.validation": { "mode": "BUILTIN" },
    "society.propagation": { "mode": "BUILTIN" },
    "society.factions":    { "mode": "BUILTIN" },
    "audio.tts": {
      "mode": "EXTERNAL",
      "provider": "studio_tts"
    }
  }
}
```

## 3.2 Verbot von Doppelautorität

Kein Zustandsbereich darf zwei aktive Owner besitzen.

Unzulässig:

```text
Unscripted Memory schreibt Erinnerungen
UND
Convai Memory schreibt dieselben Erinnerungen
UND
beide werden ungeprüft zusammengeführt.
```

Zulässig:

### Variante A

- Unscripted Memory = AUTHORITATIVE.
- Fremdplattform-Memory = deaktiviert.

### Variante B

- Fremdplattform-Memory = AUTHORITATIVE.
- Unscripted Memory = EXTERNAL Adapter.
- Der Adapter muss den Unscripted-Memory-Vertrag erfüllen.

### Variante C

- Unscripted Memory = AUTHORITATIVE.
- Fremdplattform-Memory = `SHADOW`.
- Shadow-Daten dürfen nur als Diagnosedaten dienen oder über explizite `ExternalMemoryImportEvent`s übernommen werden.

## 3.3 Capability Registry

Die Runtime MUSS beim Start:

1. alle Capability-Bindings laden;
2. Dependencies auflösen;
3. genau einen Owner pro mutablem State prüfen;
4. inkompatible Kombinationen ablehnen;
5. neutrale Fallbacks für DISABLED-Module registrieren;
6. die endgültige Phase Graph erzeugen;
7. den resolved Runtime Plan in den Logs und im Inspector anzeigen.

---

# 4. Capability-Katalog

## 4.1 Kern-Capabilities

| Capability ID | Aufgabe | Standard |
|---|---|---|
| `world.state` | autoritativer strukturierter Weltzustand | BUILTIN |
| `world.events` | Event Ledger und Zeit | BUILTIN |
| `perception` | Erreichbarkeit, Qualität und Modalität einer Wahrnehmung | BUILTIN |
| `beliefs` | subjektive Überzeugungen, Evidenz, Konflikt | BUILTIN |
| `memory.personal` | episodisches, semantisches und soziales Gedächtnis | BUILTIN |
| `memory.collective` | Ort, Institution, Gruppe, öffentliches Narrativ | BUILTIN |
| `identity` | Rollen, aktive Identität, Status | BUILTIN |
| `personality` | Big Five und stabile Dispositionen | BUILTIN |
| `values` | Schwartz-Werte und situative Aktivierung | BUILTIN |
| `needs` | homeostatische und soziale Bedürfnisse | BUILTIN |
| `affect` | Appraisal, EmotionInstance und PAD | BUILTIN |
| `relationships` | Vertrauen, Sympathie, Angst, Loyalität, Schuld | BUILTIN |
| `motivation` | Ziele, Intentionen und begrenzte Pläne | BUILTIN |
| `decision.policy` | Kandidatenbewertung und Auswahl | BUILTIN |
| `dialogue.state` | Gesprächszustand und Common Ground | BUILTIN |
| `dialogue.planning` | Speech Act, Thema, Fakten und Stil | BUILTIN |
| `dialogue.realization` | Formulierung des Plans als Text | BUILTIN Template oder EXTERNAL |
| `dialogue.validation` | Wissens-, Geheimnis-, Kanon- und Loop-Prüfung | BUILTIN |
| `society.propagation` | Gerüchte, Medien und Informationsnetz | BUILTIN |
| `society.reputation` | zielgruppen- und ortsspezifischer Ruf | BUILTIN |
| `society.factions` | Heat, Clocks und Offscreen-Reaktion | BUILTIN |
| `explainability` | Reason Traces, Inspector und Replay | BUILTIN |
| `persistence` | Snapshot, Event Tail und Migration | BUILTIN |

## 4.2 Nicht-kernige optionale Capabilities

| Capability ID | Standard |
|---|---|
| `language.semantic_parser` | BUILTIN Rule/Template oder EXTERNAL LLM |
| `embedding.retrieval` | DISABLED |
| `audio.stt` | DISABLED oder EXTERNAL |
| `audio.tts` | DISABLED oder EXTERNAL |
| `animation.expression` | DISABLED oder EXTERNAL |
| `moderation` | EXTERNAL oder BUILTIN Regeln |
| `engine.navigation` | EXTERNAL |
| `engine.combat` | EXTERNAL |
| `engine.inventory` | EXTERNAL |
| `engine.quest` | EXTERNAL |

Unscripted darf optionale Daten für Animation oder TTS ausgeben, implementiert
diese Systeme aber nicht.

---

# 5. Dependencies und Degradationsregeln

## 5.1 Harte Dependencies

```text
beliefs              requires world.events
memory.personal      requires world.events
dialogue.planning    requires dialogue.state
society.propagation  requires world.events
explainability       requires world.events
```

## 5.2 Weiche Dependencies

```text
dialogue.planning may use beliefs, memory, affect, relationships, motivation
decision.policy may use needs, values, affect, relationships, motivation
society.factions may use reputation, propagation and world events
```

## 5.3 Definierte Fallbacks

### Beliefs DISABLED

Der NPC erhält nur:

- kanonisches Pack-Wissen;
- aktuelle explizite Context Facts.

Er besitzt keine falschen oder unsicheren Überzeugungen.

### Memory DISABLED

Der NPC verwendet nur:

- aktuelle Conversation State;
- aktuelle Beliefs.

Keine langfristige persönliche Erinnerung.

### Affect DISABLED

Neutraler Zustand:

```json
{ "valence": 0, "arousal": 0, "dominance": 0 }
```

Keine Emotion Bias.

### Relationships DISABLED

Alle Beziehungen werden neutral gelesen:

```json
{
  "trust": 0.5,
  "liking": 0,
  "respect": 0.5,
  "fear": 0,
  "loyalty": 0
}
```

### Motivation DISABLED

Das Spiel oder Fremdsystem muss ein `ExternalGoalContext` liefern. Sonst verwendet die Runtime einen neutralen Reaktionsmodus.

### Dialogue Realization DISABLED

Die Runtime gibt ausschließlich `DialoguePlan` aus.

### Dialogue Validation DISABLED

Nur in einem expliziten `unsafe_development_mode`.

Im Produktmodus SOLLTE Validation nicht deaktivierbar sein, wenn ein generativer Realizer verwendet wird.

### Society/Factions DISABLED

Keine Offscreen-Verbreitung oder Makroreaktion. Individuelle NPCs funktionieren weiterhin.

---

# 6. Autoritative Zustandsbereiche

| State Domain | Standard-Owner |
|---|---|
| Canonical world facts | Game Engine / WorldStateAdapter |
| Events and observation history | Unscripted Event Ledger |
| NPC beliefs and evidence | BeliefEngine |
| Personal memory | MemoryEngine |
| Collective memory | CollectiveMemoryEngine |
| Affect and emotion instances | AffectEngine |
| Relationships | RelationshipEngine |
| Reputation | ReputationEngine |
| Identity salience | IdentityEngine |
| Goals and intentions | MotivationEngine oder External Motivation Adapter |
| Conversation state | DialogueStateEngine |
| Dialogue plan | DialoguePlanner |
| Generated wording | TextRealizerProvider |
| Validation outcome | Validator |
| Physical action success | Game Engine |
| Animation and audio | Game Engine or external provider |
| Faction state | FactionDirector |

Die Game Engine bleibt autoritativ für physische Realität.

Beispiel:

Unscripted schlägt vor:

```text
npc_12 attacks player
```

Die Engine meldet zurück:

```text
attack failed because door was locked
```

Erst dieses Resultat wird als kanonisches Event gespeichert.

---

# 7. Öffentliche Runtime-API

Die öffentliche API MUSS klein, typisiert und engineunabhängig sein.

## 7.1 Lifecycle

```python
runtime = UnscriptedRuntime.create(RuntimeConfig)
runtime.load_world_pack(path_or_stream)
runtime.start()
runtime.stop()
```

## 7.2 Welt und Zeit

```python
runtime.emit_event(WorldEvent) -> EventReceipt
runtime.advance_time(TimeAdvance) -> AdvanceResult
runtime.query_world(WorldQuery) -> WorldQueryResult
runtime.create_snapshot() -> SnapshotId
runtime.restore_snapshot(SnapshotId)
```

## 7.3 NPC-Wissen

```python
runtime.query_belief(agent_id, proposition) -> BeliefView
runtime.query_awareness(agent_id, topic) -> AwarenessResult
runtime.retrieve_memories(agent_id, MemoryQuery) -> list[MemoryView]
runtime.explain_knowledge(agent_id, proposition) -> ProvenanceTrace
```

## 7.4 NPC-Entscheidung

```python
runtime.decide(DecisionRequest) -> NpcDecision
runtime.report_action_result(ActionResult) -> EventReceipt
```

## 7.5 Dialog

```python
runtime.interpret_input(InputEnvelope) -> InterpretationResult
runtime.begin_conversation(ConversationStart) -> ConversationId
runtime.respond(DialogueRequest) -> DialogueResponse
runtime.end_conversation(ConversationEnd)
```

## 7.6 Soziale Folgen

```python
runtime.publish_claim(ClaimEvent) -> EventReceipt
runtime.publish_media(MediaPublication) -> EventReceipt
runtime.query_reputation(ReputationQuery) -> ReputationView
runtime.query_faction(FactionQuery) -> FactionView
```

## 7.7 Debugging

```python
runtime.explain_decision(decision_id) -> DecisionTrace
runtime.explain_utterance(turn_id) -> DialogueTrace
runtime.replay(ReplayRequest) -> ReplayResult
runtime.validate_world_pack(path) -> ValidationReport
```

---

# 8. Zentrale Datenverträge

## 8.1 RuntimeConfig

```json
{
  "runtime_id": "unscripted:main",
  "schema_version": "0.9.0",
  "global_seed": "project-seed",
  "strict_mode": true,
  "capabilities": {},
  "providers": {},
  "storage": {
    "type": "sqlite",
    "path": "./save/unscripted.db",
    "reason_trace_mode": "ring_buffer"
  }
}
```

## 8.2 WorldPackManifest

```json
{
  "pack_id": "studio:night_district",
  "pack_version": "1.0.0",
  "requires_core": ">=0.9.0 <1.0.0",
  "default_language": "en",
  "files": {
    "world": "world.json",
    "canon": "canon.json",
    "characters": "characters/",
    "factions": "factions.json",
    "schedules": "schedules.json",
    "actions": "actions.json",
    "archetypes": "archetypes.json",
    "style": "style.json"
  },
  "extensions": [
    "studio:magic-system@1"
  ]
}
```

## 8.3 Minimal CharacterProfile

```json
{
  "id": "npc:guard_17",
  "archetype": "security_guard",
  "name": "Rao",
  "roles": ["guard"],
  "factions": ["city_security"],
  "location": "place:security_post"
}
```

Der Archetyp ergänzt Standardwerte.

## 8.4 Vollständiges CharacterProfile

```json
{
  "id": "npc:vee",
  "names": {
    "public": "Vee",
    "objective": "Valeria K."
  },
  "roles": [
    { "role": "fixer", "context": "group:reds" },
    { "role": "sister", "context": "family:k" }
  ],
  "profession": "street_fixer",
  "education": {
    "street": 0.85,
    "medicine": 0.20,
    "corporate_law": 0.10
  },
  "big_five": {
    "openness": 0.60,
    "conscientiousness": 0.40,
    "extraversion": 0.70,
    "agreeableness": 0.30,
    "emotional_stability": 0.35
  },
  "values": {
    "security": 0.70,
    "self_direction": 0.60,
    "power": 0.50,
    "benevolence": 0.75
  },
  "needs": {
    "safety": 0.45,
    "income": 0.60,
    "recognition": 0.40
  },
  "identities": [
    {
      "id": "identity:gang_member",
      "group": "group:reds",
      "accessibility": 0.80
    },
    {
      "id": "identity:sister",
      "group": "family:k",
      "accessibility": 0.90
    }
  ],
  "appearance": {
    "garments": ["item:red_cyberjacket"],
    "symbols": ["symbol:reds"]
  },
  "relationships": {
    "npc:milan": {
      "kinship": 1.0,
      "trust": 0.95,
      "loyalty": 0.95
    }
  },
  "goals": [
    {
      "id": "goal:protect_milan",
      "priority": 0.90
    }
  ],
  "protected_information": [
    {
      "proposition": "prop:milan_location",
      "policy": "family_only"
    }
  ],
  "schedule_ref": "schedule:vee_default"
}
```

## 8.5 WorldEvent

```json
{
  "event_id": "event:1001",
  "event_type": "event:ThreatAction",
  "world_time": 61002,
  "actor": "player:1",
  "roles": {
    "patient": "npc:merchant_17",
    "instrument": "item:pistol_4"
  },
  "place": "place:market",
  "severity": 0.62,
  "canonical": true,
  "payload": {}
}
```

## 8.6 ClaimEvent

```json
{
  "speaker": "player:1",
  "audience": ["npc:vee"],
  "proposition": {
    "predicate": "core:has_role",
    "slots": {
      "agent": "player:1",
      "role": "role:police_officer",
      "context": "org:city_security"
    },
    "polarity": "positive"
  },
  "stance": "asserted",
  "world_time": 61003
}
```

Eine ClaimEvent ändert nicht automatisch den World State.

## 8.7 NpcDecision

```json
{
  "decision_id": "decision:773",
  "npc_id": "npc:vee",
  "decision_type": "dialogue",
  "goal": "goal:protect_milan",
  "selected_action": "dialogue:evade_and_probe",
  "suggested_game_action": "action:watch_player_reaction",
  "dialogue_plan_id": "plan:884",
  "social_effect_proposals": [],
  "confidence": 0.78,
  "reason_trace_id": "trace:991"
}
```

## 8.8 DialoguePlan

```json
{
  "plan_id": "plan:884",
  "speaker": "npc:vee",
  "addressee": "player:1",
  "dialogue_act": "evade",
  "secondary_act": "probe",
  "topic": "topic:clinic_shutdown",
  "goal": "goal:protect_milan",
  "stance": "guarded",
  "allowed_propositions": [
    "prop:clinic_closed_last_night"
  ],
  "avoid_topic_patterns": [
    "topic:milan_current_location"
  ],
  "required_uncertainty": [],
  "deception_authorization": {
    "allowed": true,
    "scope": "protect_family"
  },
  "style": {
    "warmth": -0.20,
    "dominance": 0.30,
    "formality": 0.20,
    "directness": 0.75,
    "verbosity": "short"
  },
  "max_tokens": 70,
  "fallback_template_id": "deflect_family_secret"
}
```

Das eigentliche Geheimnis SOLLTE dem generativen Provider nicht übergeben werden.

## 8.9 DialogueResponse

```json
{
  "turn_id": "turn:910",
  "plan_id": "plan:884",
  "text": "Maybe. Why do you care?",
  "semantic_content": [],
  "suggested_animation_tags": [
    "guarded",
    "watchful"
  ],
  "validation": {
    "accepted": true,
    "hard_failures": [],
    "soft_warnings": []
  },
  "provider_record_id": "provider_call:331"
}
```

## 8.10 ActionResult

```json
{
  "decision_id": "decision:773",
  "action_id": "action:watch_player_reaction",
  "status": "succeeded",
  "canonical_effects": [],
  "world_time": 61004
}
```

---

# 9. Provider-System

## 9.1 Grundprinzip

Provider sind austauschbare Implementierungen. Sie dürfen keine autoritativen Unscripted-Zustände direkt verändern.

Jeder Provider erhält nur den minimal notwendigen Input und gibt typisierte Ergebnisse zurück.

## 9.2 SemanticParserProvider

```python
class SemanticParserProvider(Protocol):
    provider_id: str
    version: str

    def parse(
        self,
        envelope: InputEnvelope,
        context: ParserContext
    ) -> InterpretationResult:
        ...
```

Implementierungen:

- `RuleBasedParserProvider`;
- `TemplateCommandParserProvider`;
- `LocalLlmParserProvider`;
- `OpenAICompatibleParserProvider`;
- `StudioParserProvider`;
- `CompetitorParserBridge`.

## 9.3 TextRealizerProvider

```python
class TextRealizerProvider(Protocol):
    provider_id: str
    version: str

    def realize(
        self,
        plan: DialoguePlan,
        context: RealizerContext
    ) -> ProviderTextResult:
        ...
```

Implementierungen:

- `TemplateRealizer`;
- `LocalLlmRealizer`;
- `OpenAICompatibleRealizer`;
- `NvidiaGameAgentRealizer`;
- `InworldRealizerBridge`;
- `ConvaiRealizerBridge`;
- `CharismaRealizerBridge`;
- `StudioRealizer`.

## 9.4 EmbeddingProvider

Optional und standardmäßig deaktiviert.

Verwendung nur für:

- semantische Ähnlichkeit von episodischen Zusammenfassungen;
- Lore Retrieval;
- Fuzzy Topic Matching.

Nicht verwenden für:

- Besitz;
- aktuelle Position;
- Geheimnisse;
- Verpflichtungen;
- harte Weltfakten.

## 9.5 TTSProvider

TTS ist nicht Teil der NPC-Intelligenz. Es existiert nur als optionaler Ausgangsadapter:

```python
class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_profile: dict,
        expression_tags: list[str]
    ) -> AudioReference:
        ...
```

Unscripted besitzt keine Stimme und hostet kein TTS.

## 9.6 GameActionExecutor

Das Spiel führt Aktionen aus:

```python
class GameActionExecutor(Protocol):
    def can_execute(self, proposal: ActionProposal) -> CapabilityCheck:
        ...

    def execute(self, proposal: ActionProposal) -> ActionExecutionReceipt:
        ...
```

Die Runtime darf auch nur einen Vorschlag zurückgeben. Die Engine kann später `ActionResult` melden.

## 9.7 StorageProvider

```python
class StorageProvider(Protocol):
    def append_event(self, event: WorldEvent) -> None: ...
    def load_projection(self, key: str): ...
    def save_projection(self, key: str, state) -> None: ...
    def create_snapshot(self, state) -> SnapshotId: ...
```

Default:

- SQLite für Referenzruntime.
- Studio kann eigene Savegame- oder Datenbankschicht implementieren.

---

# 10. Fremdsystem-Bridge

## 10.1 Gemeinsamer Bridge-Vertrag

```python
class ExternalNpcPlatformBridge(Protocol):
    bridge_id: str

    def capabilities(self) -> set[str]:
        ...

    def send_context(
        self,
        agent_id: str,
        context: ExternalNpcContext
    ) -> None:
        ...

    def request_realization(
        self,
        plan: DialoguePlan
    ) -> ProviderTextResult:
        ...

    def import_external_event(
        self,
        event: ExternalPlatformEvent
    ) -> list[WorldEvent]:
        ...
```

## 10.2 Bridge-Mapping

Jede Bridge muss dokumentieren:

- welche Capabilities sie implementiert;
- welche Zustände sie besitzt;
- welche Zustände nur gespiegelt werden;
- welche Daten sie an die Fremdplattform sendet;
- welche Fremddaten zurückkommen;
- welche Funktionen deaktiviert werden müssen;
- welche Lizenz- oder Cloudabhängigkeit besteht.

## 10.3 Inworld Bridge

Technisch sinnvoll:

```text
Inworld input/STT
→ Unscripted Custom Node
→ DialoguePlan
→ Inworld LLM Node
→ Unscripted Validation Node
→ optional Inworld TTS
```

Unscripted sollte Inworld nutzen als:

- Text Realizer;
- Modellrouter;
- optional Audio-Frontend.

Unscripted bleibt Owner von:

- Weltwahrheit;
- Beliefs;
- Memory;
- Beziehungen;
- Faction State;
- Disclosure Policy.

Inworld bietet öffentlich dokumentierte Custom Nodes und Graphen. Daher ist eine Bridge technisch plausibel.

## 10.4 Convai Bridge

Sinnvolle Nutzung:

- Convai erhält Dynamic Environment Info;
- Convai formuliert eine Antwort;
- Convai kann Voice und Embodied Actions liefern;
- Unscripted validiert und speichert die sozialen Folgen.

Empfehlung:

- Convai Long-Term Memory deaktivieren, wenn Unscripted Memory authoritative ist;
- keine vollständigen Geheimnisse in Dynamic Context übertragen;
- externe Actions als Vorschläge behandeln;
- jedes Ergebnis über `ExternalPlatformEvent` zurückmelden.

## 10.5 NVIDIA Game Agent Bridge

NVIDIA eignet sich als offene Grundlage für Standalone Mode:

```text
Unscripted
→ NVIDIA Game Agent SDK
→ lokales Modell / Chat / RAG
```

Unscripted bleibt oberhalb der Inferenzschicht.

Der NVIDIA Game Agent SDK ist öffentlich unter Apache 2.0 dokumentiert. Er darf nicht mit dem Unscripted-Semantikmodell verwechselt werden: Er liefert Infrastruktur, nicht unseren World-Memory-Kern.

## 10.6 Charisma Bridge

Charisma kann:

- authored Story Graph;
- flexible Eingaben;
- Story Playthrough;
- Ausgabe und optionale Audioantworten

übernehmen.

Unscripted kann:

- World Memory;
- Beliefs;
- soziale Folgen;
- Fraktionen;
- Inspector

ergänzen.

Story Gates müssen zwischen Charisma und Unscripted eindeutig gemappt werden.
Einer der beiden Systeme bleibt Owner des Quest-/Narrativzustands.

## 10.7 FAtiMA Adapter

FAtiMA ist als optionaler `EXTERNAL affect` oder `EXTERNAL social_appraisal` Provider denkbar.

Nicht empfohlen:

- Unscripted vollständig auf FAtiMA aufzubauen;
- zwei parallele Appraisal-Systeme gleichzeitig zu betreiben.

## 10.8 Kundeneigene Systeme

Die wichtigste Bridge ist nicht zwingend ein Konkurrent, sondern das bestehende Studio-System:

```text
Behavior Tree
Quest System
Dialogue System
Internal LLM
Internal SaveGame
```

Unscripted muss daher nicht nur markenspezifische Adapter, sondern einen
stabilen generischen ABI/API-Vertrag anbieten.

---

# 11. Vollständige Runtime-Schichten

## 11.1 Layer 1 — World Contract

Enthält:

- Entity Registry;
- Place Graph;
- Time;
- Canonical Facts;
- Institutions;
- Factions;
- Items und Ressourcen;
- World Rules;
- Protected Facts;
- Action Catalog.

## 11.2 Layer 2 — Perception

Entscheidet:

- wer ein Ereignis wahrnehmen konnte;
- über welche Modalität;
- mit welcher Qualität;
- welche Identität erkannt wurde;
- welche Kleidung und Symbole sichtbar waren;
- ob Türen, Lärm, Entfernung oder Verkleidung störten.

## 11.3 Layer 3 — Epistemics

Verarbeitet:

- Observation;
- Claim;
- Evidence;
- Belief;
- Widerspruch;
- Unwissen;
- Quelle;
- Korrelation;
- Aktualisierung;
- Supersession.

## 11.4 Layer 4 — Memory

Verarbeitet:

- episodische Erinnerung;
- semantisches Wissen;
- soziale Erinnerung;
- Verpflichtungen;
- Gesprächsfäden;
- emotionalen Rest;
- Konsolidierung;
- Vergessen;
- Cue Retrieval.

## 11.5 Layer 5 — Character Cognition

Enthält:

- Identität;
- Big Five;
- Werte;
- Bedürfnisse;
- Rollen;
- Beruf;
- Ausbildung;
- Kleidung;
- Status;
- Ziele;
- aktuelle Emotion;
- Theory of Mind.

## 11.6 Layer 6 — Social Dynamics

Enthält:

- Beziehungen;
- Schulden und Versprechen;
- Reputation;
- Gruppenidentität;
- Normen;
- soziale Netzwerke;
- Informationsverbreitung;
- Mobilisierung;
- Fraktionen.

## 11.7 Layer 7 — Deliberation

Erzeugt:

- ausführbare Kandidaten;
- Utility Contributions;
- Dialogue Acts;
- Action Proposals;
- Entscheidungen;
- Reason Traces.

## 11.8 Layer 8 — Realization

Optional:

- strukturierte Ausgabe;
- Template;
- lokales Modell;
- Cloudmodell;
- Fremdplattform.

## 11.9 Layer 9 — Validation

Prüft:

- Wissenszugang;
- Geheimnisse;
- Kanon;
- Stance;
- kontrollierte Lüge;
- Wiederholung;
- Länge;
- erlaubte Handlung;
- Schema.

---

# 12. Runtime-Pipelines

## 12.1 Ereignisverarbeitung

```text
Game Engine emits WorldEvent
→ Event Ledger
→ Perception
→ Observation per observer
→ Belief update
→ Memory encoding
→ Appraisal and affect
→ Relationship and identity proposals
→ Apply by state owners
→ Reputation and faction consequences
→ Persist projections
→ Reason Trace
```

## 12.2 Spielerinput

```text
Text or structured player input
→ Semantic Parser Provider
→ alternative interpretations
→ reference resolution
→ action and speech-act validation
→ canonical Claim/Action Event
→ normal event processing
```

## 12.3 NPC-Dialog

```text
Conversation state
→ active NPC goal
→ topic candidates
→ dialogue-act candidates
→ allowed proposition retrieval
→ disclosure policy
→ DialoguePlan
→ TextRealizerProvider or semantic-only output
→ buffered validation
→ accepted DialogueResponse
→ conversation effects
```

## 12.4 NPC-Handlung

```text
Context
→ action candidates from Action Catalog and affordances
→ precondition check
→ utility and reactive rules
→ selection
→ ActionProposal
→ Game Engine executes or rejects
→ ActionResult becomes canonical event
```

## 12.5 Informationsverbreitung

```text
Belief or Claim
→ share decision
→ recipient selection from social network/channel
→ latency
→ mutation if configured
→ provenance chain
→ recipient belief update
```

## 12.6 Zeitfortschritt

```text
Advance time
→ due scheduled events
→ shifts and schedules
→ needs
→ affect decay
→ memory decay and consolidation
→ deadlines
→ media broadcasts
→ rumor propagation
→ faction clocks
→ off-screen reactions
```

---

# 13. Theorie-Module und ihre Rolle

Die Theorie dient der Dynamik, nicht dem Marketing.

## 13.1 Big Five

Beeinflusst:

- Initiativwahrscheinlichkeit;
- Persistenz;
- Konfliktstil;
- Offenheit für Neues;
- emotionale Reaktivität.

Keine Eigenschaft erzwingt eine Handlung.

## 13.2 Schwartz-Werte

Aktiviert kontextabhängig:

- Sicherheit;
- Macht;
- Leistung;
- Selbstbestimmung;
- Tradition;
- Konformität;
- Wohlwollen;
- Universalismus;
- Stimulation;
- Hedonismus.

## 13.3 BDI

Trennt:

- Beliefs;
- Desires/Goals;
- Intentions;
- Plans.

Im MVP sind Pläne authored und begrenzt.

## 13.4 Appraisal + PAD

Appraisal erklärt, warum Emotion entsteht. PAD liefert einen kompakten Ausdruckszustand.

Emotionen müssen target-aware sein.

## 13.5 ACT-R-inspiriertes Memory

Verwendet:

- Recency;
- Frequency;
- Cue Relevance;
- Emotional Salience;
- Relationship Relevance;
- prospective Deadline Boost;
- type-specific decay.

Kein vollständiges ACT-R-System erforderlich.

## 13.6 Social Exchange

Verarbeitet:

- Reciprocity;
- Fairness;
- Favors;
- Dependence;
- Promise fulfillment;
- Betrayal.

## 13.7 Social Identity und Self-Categorization

Bestimmt, welche Identität in einer Situation salient ist und welche Werte oder Gruppennormen dadurch stärker wirken.

## 13.8 Theory of Mind

Der NPC modelliert in begrenzter Tiefe:

- was ein anderer weiß;
- was er will;
- wie er wahrscheinlich reagieren wird.

Depth 1 Standard; Depth 2 nur für High-LOD-Agenten.

## 13.9 Weak Ties und Propagation

Starke Beziehungen liefern:

- Vertrauen;
- häufigen Kontakt;
- Verstärkung.

Schwache Bridge-Ties liefern:

- neue Information zwischen Gruppen;
- Reichweite.

## 13.10 Goffman/Impression Management

Publikum, Kleidung, Rolle und Überwachung beeinflussen Selbstdarstellung und Offenlegung.

---

# 14. Plug-and-Play-Weltintegration

## 14.1 Drei Integrationsstufen

### Stufe A — Minimal

Studio liefert:

- NPC ID;
- Archetyp;
- Rolle;
- Fraktion;
- Ort.

Unscripted generiert Defaults.

### Stufe B — Standard

Studio liefert zusätzlich:

- Persönlichkeit;
- Werte;
- Beziehungen;
- Ziele;
- Wissen;
- Zeitplan.

### Stufe C — Voll

Studio modelliert:

- Protected Facts;
- individuelle Beliefs;
- institutionelle Zugriffe;
- Verpflichtungen;
- Narrative Gates;
- spezielle Regeln.

## 14.2 Importer

Der Importer SOLLTE Mappings unterstützen für:

- Unreal Data Tables;
- Gameplay Tags;
- Data Assets;
- Quest Data;
- CSV;
- JSON;
- YAML;
- kundeneigene REST- oder C++-Datenmodelle.

## 14.3 Mapping-Datei

```json
{
  "source": "unreal_gameplay_tags",
  "mappings": {
    "Faction.Security": "group:city_security",
    "Role.Guard": "role:guard",
    "State.Injured": "body:injured",
    "Quest.Milan.LocationKnown": "prop:milan_location_known"
  }
}
```

## 14.4 Event Bridge

Ein Studio muss nur relevante Ereignisse melden:

```text
OnActorEnteredArea
OnDialogueLineHeard
OnItemTransferred
OnDamageApplied
OnQuestStateChanged
OnMediaBroadcast
OnRoleChanged
OnActionResult
```

Unscripted darf keine per-frame Weltkopie verlangen.

## 14.5 Archetypen

Archetypen reduzieren Autorenaufwand:

```text
honest_guard
corrupt_guard
weary_medic
street_vendor
gang_fixer
corporate_manager
local_elder
opportunistic_informant
```

Archetypen sind Defaults, keine starren Klassen.

---

# 15. Modulkonfiguration

## 15.1 Beispiel: Vollständiges Unscripted

```json
{
  "profile": "standalone_full",
  "capabilities": {
    "perception": "BUILTIN",
    "beliefs": "BUILTIN",
    "memory.personal": "BUILTIN",
    "memory.collective": "BUILTIN",
    "affect": "BUILTIN",
    "relationships": "BUILTIN",
    "motivation": "BUILTIN",
    "decision.policy": "BUILTIN",
    "dialogue.state": "BUILTIN",
    "dialogue.planning": "BUILTIN",
    "dialogue.realization": {
      "mode": "EXTERNAL",
      "provider": "openai_compatible:ollama"
    },
    "dialogue.validation": "BUILTIN",
    "society.propagation": "BUILTIN",
    "society.factions": "BUILTIN"
  }
}
```

## 15.2 Beispiel: Unscripted + Convai

```json
{
  "profile": "bridge_convai",
  "capabilities": {
    "beliefs": "BUILTIN",
    "memory.personal": "BUILTIN",
    "relationships": "BUILTIN",
    "motivation": "BUILTIN",
    "dialogue.planning": "BUILTIN",
    "dialogue.realization": {
      "mode": "EXTERNAL",
      "provider": "convai"
    },
    "dialogue.validation": "BUILTIN",
    "society.propagation": "BUILTIN",
    "society.factions": "BUILTIN",
    "audio.tts": {
      "mode": "EXTERNAL",
      "provider": "convai"
    }
  },
  "external_policies": {
    "convai_long_term_memory": "DISABLE",
    "convai_narrative_state": "SHADOW"
  }
}
```

## 15.3 Beispiel: Headless für internes Studio-System

```json
{
  "profile": "headless_social_intelligence",
  "capabilities": {
    "perception": "BUILTIN",
    "beliefs": "BUILTIN",
    "memory.personal": "BUILTIN",
    "memory.collective": "BUILTIN",
    "relationships": "BUILTIN",
    "motivation": "EXTERNAL",
    "decision.policy": "BUILTIN",
    "dialogue.state": "BUILTIN",
    "dialogue.planning": "BUILTIN",
    "dialogue.realization": "DISABLED",
    "dialogue.validation": "DISABLED",
    "society.propagation": "BUILTIN",
    "society.factions": "BUILTIN"
  }
}
```

## 15.4 Beispiel: Nur World Memory und Informationsverteilung

```json
{
  "profile": "causal_memory_only",
  "capabilities": {
    "perception": "BUILTIN",
    "beliefs": "BUILTIN",
    "memory.personal": "BUILTIN",
    "memory.collective": "BUILTIN",
    "relationships": "BUILTIN",
    "society.propagation": "BUILTIN",
    "society.reputation": "BUILTIN",
    "society.factions": "DISABLED",
    "dialogue.planning": "DISABLED",
    "dialogue.realization": "DISABLED"
  }
}
```

---

# 16. Fehler- und Ausfallverhalten

## 16.1 External Provider Timeout

- genau ein konfigurierbarer Retry;
- danach Template Fallback oder semantic-only result;
- kein Verlust des Conversation State;
- Provider Failure Event im Reason Trace.

## 16.2 Ungültige Provider-Ausgabe

- JSON parse failure → reject;
- unbekannte Proposition → reject;
- verbotene Handlung → reject;
- Secret Token → hard reject;
- maximal zwei Regenerationen;
- danach deterministischer Fallback.

## 16.3 Provider nicht verfügbar

Die Runtime MUSS weiter funktionieren:

- ohne LLM: Template oder semantic-only;
- ohne TTS: Textausgabe;
- ohne Embeddings: strukturierte Retrieval-Logik;
- ohne Fremdplattform: Builtin Provider.

## 16.4 Capability Adapter inkompatibel

Runtime startet nicht im Strict Mode.

Fehlermeldung muss nennen:

- fehlende Capability;
- erwartete Version;
- tatsächliche Version;
- konfliktierender State Owner;
- vorgeschlagene Behebung.

---

# 17. Determinismus und Replay

## 17.1 Strukturierter Determinismus

Deterministisch reproduzierbar:

- Events;
- Perception;
- Belief Update;
- Memory;
- Relationship Changes;
- Faction State;
- Candidate Scores;
- selected semantic action;
- DialoguePlan;
- Validation result.

## 17.2 Modelltext

Frische LLM-Inferenz ist nicht garantiert byteidentisch.

Daher speichert `ProviderCallRecord`:

```json
{
  "provider_id": "openai_compatible:ollama",
  "model_id": "model-name",
  "model_hash": "sha256:...",
  "prompt_hash": "sha256:...",
  "generation_params": {},
  "raw_output": "...",
  "accepted_output": "...",
  "validator_version": "0.9.0"
}
```

Semantic Replay verwendet die gespeicherte akzeptierte Antwort.

## 17.3 Seed

Jeder Zufallszug:

```text
hash(global_seed, agent_id, event_id, world_time, module_id, salt)
```

Globale Random-Generatoren sind verboten.

---

# 18. Explainability und Inspector

Der Inspector ist Teil des Produkts, nicht nur Debugging.

## 18.1 Views

```text
inspect world event
inspect npc beliefs
inspect npc memory
inspect npc relationships
inspect npc identity
inspect npc goals
inspect conversation
inspect rumor path
inspect faction
inspect last decision
inspect provider call
replay scenario
```

## 18.2 Decision Trace

Muss enthalten:

- Kandidaten;
- Hard Preconditions;
- Utility Contributions;
- Emotion Bias;
- Reactive Rules;
- Selection Probability;
- höchste Utility;
- tatsächlich ausgewählte Handlung;
- Seed.

## 18.3 Knowledge Trace

Muss enthalten:

- Proposition;
- Expected Probability;
- Support For;
- Support Against;
- Conflict;
- Ignorance;
- Evidenzpfad;
- ursprüngliche Beobachter;
- gemeinsame Herkunft;
- Zeit;
- Memory References.

## 18.4 Dialogue Trace

Muss enthalten:

- Gesprächsziel;
- Topic;
- Speech Act;
- Allowed Facts;
- Avoid Topics;
- Disclosure Rules;
- Realizer Provider;
- Validation;
- Fallback.

---

# 19. Persistenz

## 19.1 Modell

```text
verified snapshot
+ ordered event tail
= current save state
```

## 19.2 Permanent

Dauerhaft speichern:

- kanonische Ereignisse;
- aktuelle Projections;
- offene Verpflichtungen;
- geschützte Informationen;
- Faction State;
- Snapshot Metadata.

## 19.3 Kompaktierbar

- unwichtige Hintergrundereignisse;
- alte episodische Details;
- Debug Reason Traces;
- Provider Raw Outputs nach Retention Policy.

## 19.4 Snapshot Metadata

```json
{
  "schema_version": "0.9.0",
  "ontology_version": "0.4.x",
  "world_pack_hash": "...",
  "runtime_version": "0.9.0",
  "module_versions": {},
  "last_event_id": "event:9001",
  "branch_id": "main",
  "state_checksum": "sha256:..."
}
```

---

# 20. Referenz-Codearchitektur

```text
unscripted/
├── specs/
│   ├── master/
│   ├── ontology/
│   ├── schemas/
│   ├── capabilities/
│   ├── providers/
│   ├── bridges/
│   └── decisions/
├── unscripted/
│   ├── core/
│   │   ├── registry.py
│   │   ├── config.py
│   │   ├── runtime.py
│   │   ├── phases.py
│   │   └── result.py
│   ├── world/
│   │   ├── entities.py
│   │   ├── events.py
│   │   ├── time.py
│   │   └── loader.py
│   ├── perception/
│   ├── epistemics/
│   ├── memory/
│   ├── cognition/
│   ├── social/
│   ├── motivation/
│   ├── decision/
│   ├── dialogue/
│   ├── society/
│   ├── validation/
│   ├── explain/
│   ├── persistence/
│   └── providers/
│       ├── templates/
│       ├── openai_compatible/
│       ├── nvidia/
│       └── bridges/
│           ├── inworld/
│           ├── convai/
│           ├── charisma/
│           └── studio/
├── worldpacks/
├── examples/
│   ├── cyberpunk-block/
│   └── fantasy-village/
├── tests/
│   ├── unit/
│   ├── contracts/
│   ├── golden/
│   ├── adversarial/
│   └── integration/
└── tools/
    ├── inspector/
    ├── pack_validator/
    └── schema_codegen/
```

---

# 21. Implementierungsregeln für einen LLM-Coder

Der Coding-Agent MUSS:

1. niemals neue persistente Felder ohne Schemaänderung erzeugen;
2. niemals zwei Owner für einen Zustand registrieren;
3. keine Theorie-Module direkt ein LLM aufrufen lassen;
4. keine Eingabestates mutieren;
5. alle Updates als neues State-Objekt zurückgeben;
6. alle Zufallsoperationen deterministisch seeden;
7. jeden neuen persistenten Typ serialisierbar machen;
8. jede neue Capability mit einem Disabled Fallback ausstatten;
9. jede EXTERNAL Capability gegen einen Contract-Test prüfen;
10. jedem State Change Reason Codes geben;
11. jedes Ticket mit Tests abschließen;
12. keine Engine-, Audio- oder Renderinglogik in den Core einbauen;
13. keine vollständigen Secrets an generative Provider senden;
14. Provider-Ausgaben puffern und vor Ausgabe validieren;
15. bei unklarer Spezifikation ein ADR erzeugen statt still zu improvisieren.

---

# 22. Implementierungsreihenfolge

## Phase 0 — Contract Freeze

- Capability Registry;
- RuntimeConfig Schema;
- WorldPackManifest;
- CharacterProfile;
- WorldEvent;
- Claim;
- Belief;
- Memory;
- DialoguePlan;
- NpcDecision;
- ActionResult;
- Provider Contracts;
- Ownership Matrix.

## Phase 1 — Modulare Runtime

- Capability Binding;
- BUILTIN/EXTERNAL/DISABLED;
- dependency resolver;
- neutral fallbacks;
- strict startup validation.

## Phase 2 — Knowledge Spine

```text
WorldEvent
→ Perception
→ Observation
→ Evidence
→ Belief
→ Memory
→ Persistence
→ ExplainKnowledge
```

## Phase 3 — Social Core

- Relationships;
- Commitments;
- Reputation;
- Group Identity;
- Propagation;
- Collective Memory.

## Phase 4 — Intelligence

- Values;
- Needs;
- Affect;
- Goals;
- Action Candidate Generation;
- Policy;
- NpcDecision.

## Phase 5 — Dialogue

- Conversation State;
- Parser Contract;
- DialoguePlan;
- TemplateRealizer;
- Validator;
- semantic-only mode;
- Provider Record.

## Phase 6 — Providers

- OpenAI-compatible local/cloud;
- NVIDIA adapter;
- generic studio provider;
- Convai Bridge;
- Inworld Bridge;
- Charisma Bridge.

## Phase 7 — Society

- Media;
- Rumor;
- Faction Director;
- Mobilization;
- Heat and Clocks.

## Phase 8 — Inspector and Golden Tests

- Knowledge Trace;
- Decision Trace;
- Rumor Trace;
- Provider Trace;
- Replay;
- 30–50 Golden Scenarios.

## Phase 9 — Engine Packaging

- C ABI or native library boundary;
- Unreal adapter;
- source distribution;
- documentation;
- sample integration.

---

# 23. Pflichtszenarien

## 23.1 Plugin Architecture

1. All Builtin.
2. Realizer External.
3. Memory External.
4. Memory Disabled.
5. Dialogue Disabled.
6. Invalid double owner rejected.
7. Provider timeout falls back.
8. Missing dependency rejected.

## 23.2 Knowledge

9. Claim does not change truth.
10. Direct witness differs from hearsay.
11. Five repeated reports with one source are correlated.
12. Independent witness changes probability.
13. Conflict differs from ignorance.
14. New fact supersedes old temporal state.

## 23.3 Memory

15. Recent beats old.
16. Repetition strengthens.
17. Detail fades before gist.
18. Emotional trace remains.
19. Deadline boosts prospective recall.
20. Missing slots are not hallucinated.

## 23.4 Social

21. Trust rises slowly and falls quickly.
22. Promise fulfillment changes relationship.
23. Broken commitment changes reputation.
24. Weak tie carries rumor across groups.
25. Media affects only exposed agents.
26. Faction reacts after causal threshold.

## 23.5 Dialogue

27. NPC only states allowed belief.
28. NPC can express uncertainty.
29. Authorized lie is permitted.
30. Secret is not leaked.
31. Same semantic plan works with Template and external LLM.
32. External provider output is rejected and replaced by fallback.
33. Topic exhaustion ends conversation.
34. Semantic replay is stable.

## 23.6 Portability

35. Cyberpunk pack.
36. Fantasy pack.
37. Same core and contracts.
38. Different vocabulary and culture.
39. No core fork.

---

# 24. Definition of Done für v1

Unscripted ist als Source-Code-SDK bereit, wenn:

- alle Capabilities BUILTIN/EXTERNAL/DISABLED unterstützen;
- Capability Conflicts automatisch erkannt werden;
- Standalone und Headless Mode laufen;
- mindestens zwei externe Textprovider funktionieren;
- mindestens eine Konkurrenz-Bridge als Proof funktioniert;
- zwei World Packs denselben Kern verwenden;
- 30–50 Golden Scenarios bestehen;
- Protected-Fact-Leakage in definierter Suite null ist;
- Knowledge Provenance vollständig inspizierbar ist;
- strukturierter Replay deterministisch ist;
- World Pack Import dokumentiert ist;
- ein externer Entwickler ohne Core-Änderung einen Provider schreibt;
- ein Studio die Runtime ausschließlich über Event-, Query- und Result-API integrieren kann.

---

# 25. Source-Code-Produktisierung

Das auszuliefernde Paket enthält:

- vollständigen Core-Source;
- Schemata;
- Capability Registry;
- Builtin Modules;
- Provider Interfaces;
- mindestens einen lokalen und einen API-Modelladapter;
- Bridge Examples;
- World-Pack Loader;
- Inspector;
- Tests;
- zwei Reference Packs;
- Integrationshandbuch;
- Lizenztext;
- Update- und Migration Policy.

Der Kunde darf:

- eigene Provider schreiben;
- Module austauschen;
- World Packs erweitern;
- Engine Adapter erstellen;
- Quellcode projektintern anpassen.

Der Kunde darf nicht:

- Unscripted als konkurrierende Middleware weiterverkaufen;
- proprietäre Teile ohne Lizenz weitergeben;
- Produktmarken oder Copyright entfernen.

---

# 26. Endgültige Architekturformel

```text
Unscripted Core
    owns:
        truth/belief separation
        evidence provenance
        memory
        social state
        information propagation
        faction consequences
        dialogue/action intent
        validation
        explainability

Providers
    may supply:
        semantic parsing
        text realization
        embeddings
        TTS/STT
        external behavior
        engine execution

Game Engine
    owns:
        physical world
        action execution
        rendering
        animation
        UI
        audio
```

## 26.1 Endgültige Produktthese

> **Unscripted ist kein Monolith und kein Cloudservice. Es ist ein modularer, einbettbarer NPC-Intelligence-Kern mit vollständigem Source Code. Studios können das gesamte System verwenden oder einzelne Bereiche durch eigene Systeme, lokale Modelle, APIs oder bestehende NPC-Plattformen ersetzen. Unscripted bleibt dort einzigartig wertvoll, wo Wissen, Erinnerung, Beziehungen und gesellschaftliche Konsequenzen über Zeit korrekt, kontrollierbar und nachvollziehbar verarbeitet werden müssen.**
