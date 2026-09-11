# Unscripted
## Gesamtspezifikation für ein SDK zur Simulation frei ansprechbarer, erinnerungsfähiger und sozial eingebetteter NPCs

*Written under the project's previous name and renamed on 2026-09-10;
the design it records is unchanged.*

**Version:** 0.1 – System- und Produktspezifikation  
**Datum:** 22. Juni 2026  
**Ziel:** Grundlage für Forschung, Terminal-MVP, spätere SDK-Produktisierung und Integration in bestehende Spiel-Engines

---

# 0. Zusammenfassung

Die **Unscripted** ist eine engineunabhängige Laufzeitumgebung für Spielwelten,
in denen Nichtspielercharaktere nicht nur vorgegebene Dialoge abspielen,
sondern:

- frei angesprochen werden können,
- Sprache inhaltlich verstehen,
- nur das wissen, was sie tatsächlich erfahren konnten,
- persönliche, örtliche, institutionelle und kollektive Erinnerungen besitzen,
- Informationen über Gespräche, Medien und soziale Netzwerke erhalten,
- sich an frühere Aussagen, Versprechen, Drohungen und Handlungen des Spielers erinnern,
- mit der Zeit Details vergessen, Erinnerungen verdichten oder verfälschen,
- je nach Tageszeit, Beruf, Ausbildung, Kleidung, Umgebung und sozialem Kontext unterschiedlich reagieren,
- eigene Ziele verfolgen,
- Beziehungen verändern,
- Gerüchte verbreiten,
- Gespräche sinnvoll fortentwickeln und beenden,
- in verschiedenen Spielwelten kulturell und sprachlich unterschiedlich auftreten.

Das System ist **kein einzelner Chatbot** und kein reiner Dialoggenerator. Es besteht aus mehreren kontrollierten Schichten:

1. autoritativer Weltzustand,
2. Wahrnehmung,
3. individuelle Überzeugungen,
4. Gedächtnis,
5. Persönlichkeit, Werte und Bedürfnisse,
6. soziale Beziehungen und Gruppen,
7. Ziel- und Handlungsplanung,
8. Gesprächsplanung,
9. sprachliche Realisierung,
10. Prüfung und Ausführung durch das Spiel.

Das Sprachmodell ist austauschbar. Der eigentliche Produktwert liegt in der strukturierten Welt- und Gedächtnislogik, den sozialen Mechanismen, der Gesprächskontrolle, der Testbarkeit und der Engine-Integration.

---

# 1. Produktdefinition

## 1.1 Was das Produkt ist

Unscripted ist eine:

> **Persistente Gesellschafts-, Gedächtnis- und Dialoglaufzeit für frei ansprechbare NPCs.**

Sie ergänzt bestehende Spiel-KI um:

- individuelle Persönlichkeit,
- soziale Identität,
- biografische Prägung,
- situatives Verhalten,
- subjektives Wissen,
- emotionale Bewertung,
- persönliche und kollektive Erinnerung,
- Gerüchte,
- Medienwirkung,
- Gesprächskontinuität,
- frei formulierte Antworten,
- nachvollziehbare Handlungsabsichten.

## 1.2 Was das Produkt nicht ist

Es ist nicht:

- ein Ersatz für Unreal Engine oder Unity,
- ein Ersatz für Navigation, Animation oder Physik,
- ein einzelnes großes Sprachmodell,
- eine vollständig autonome Questmaschine,
- eine unkontrollierbare Textgenerator-Blackbox,
- ein System, das jeden NPC permanent mit einem Modell berechnet,
- eine Lösung, bei der jeder NPC allwissend ist,
- ein System, das Spielregeln durch freie Sprache überschreiben darf.

## 1.3 Kernversprechen

Die Runtime soll ermöglichen:

> Der Spieler kann mit beliebigen Figuren frei sprechen und handeln. Jede Figur reagiert auf Grundlage ihrer Persönlichkeit, Biografie, sozialen Lage, Kleidung, Umgebung, Tageszeit, Arbeit, Ausbildung, Beziehungen, Erinnerungen, aktuellen Ziele und ihres begrenzten Wissens.

## 1.4 Hauptnutzen für Studios

- weniger manuell geschriebene Varianten für Nebenfiguren,
- glaubwürdigere Reaktionen auf unvorhersehbare Spielerhandlungen,
- bessere Langzeitkontinuität,
- dynamische Nebenhandlungen,
- wiederverwendbare soziale Systeme,
- nachvollziehbare und testbare generative Dialoge,
- Integration in bestehende Behavior Trees, State Trees und Questlogik,
- optionaler lokaler oder cloudbasierter Modellbetrieb,
- keine Bindung an einen einzelnen Modellanbieter.

---

# 2. Zentrale Designprinzipien

## 2.1 Wahrheit, Glaube, Erinnerung und Äußerung sind getrennt

Das System muss strikt unterscheiden:

- **Weltwahrheit:** Was ist tatsächlich passiert?
- **Wahrnehmung:** Was hat eine Figur gesehen, gehört oder anders erfasst?
- **Behauptung:** Was hat jemand gesagt?
- **Überzeugung:** Was glaubt die Figur?
- **Erinnerung:** Was kann sie später noch abrufen?
- **Äußerung:** Was entscheidet sie, mitzuteilen?
- **Handlung:** Was tut sie tatsächlich?

Diese Ebenen dürfen niemals in einer einzigen Textdatenbank vermischt werden.

## 2.2 Sprache ist Ausgabe, nicht Weltzustand

Ein Sprachmodell darf Formulierungen erzeugen. Es darf aber nicht selbstständig:

- Besitzverhältnisse ändern,
- Personen töten,
- Geld erzeugen,
- geheime Informationen freigeben,
- den Kanon überschreiben,
- neue Weltregeln erfinden,
- eine Behauptung des Spielers automatisch als Wahrheit speichern.

## 2.3 NPCs sind nicht allwissend

Ein NPC kennt nur Informationen, die er:

- selbst beobachtet,
- von anderen erhalten,
- über Medien empfangen,
- in institutionellen Daten gefunden,
- aus bekannten Fakten abgeleitet,
- oder durch seine Rolle plausibel gelernt hat.

## 2.4 Hintergrundsimulation ist semantisch

NPC-zu-NPC-Kommunikation außerhalb der Hörweite des Spielers wird nicht als vollständiger Text generiert. Es genügt:

- wer wem was mitgeteilt hat,
- mit welcher Glaubwürdigkeit,
- welche Überzeugung sich verändert hat,
- welche Beziehung betroffen ist.

Text wird nur erzeugt, wenn der Spieler zuhören oder später eine konkrete Formulierung erinnern soll.

## 2.5 Jeder wichtige Output muss erklärbar sein

Für jede Aussage oder Handlung soll die Runtime Reason Codes liefern:

- welche Erinnerung aktiviert wurde,
- welche Beziehung relevant war,
- welches Ziel verfolgt wurde,
- welches Thema gewählt wurde,
- welche Regel eine Information blockierte,
- warum die Stimmung wechselte,
- warum das Gespräch beendet wurde.

## 2.6 Deterministische und generative Teile werden getrennt

Deterministisch:

- Weltzustand,
- Ereignisse,
- Berechtigungen,
- Beziehungen,
- Fristen,
- Gedächtnisstatus,
- Zielkonflikte,
- Aktionsprüfung,
- Gesprächsfortschritt.

Generativ:

- Interpretation freier Sprache,
- Formulierung,
- Zusammenfassung,
- kontrollierte Biografiedetails,
- stilistische Variation.

## 2.7 Das System muss ohne großes Modell funktionieren

Ein Studio soll drei Modi wählen können:

1. **Deterministisch:** Regeln, Vorlagen, keine generative KI.
2. **Hybrid:** strukturierte Planung plus kleines lokales Modell.
3. **Erweitert:** hochwertige Modelle für ausgewählte Figuren oder Szenen.

---

# 3. Das mentale Modell eines NPCs

Jeder NPC wird als mehrschichtiges System modelliert.

## 3.1 Identitätskern

Relativ stabil:

- Name,
- Alter,
- Geschlecht oder soziale Rolle,
- Herkunft,
- Familie,
- Wohnort,
- Beruf,
- Ausbildung,
- Fraktion,
- Religion oder Weltanschauung,
- körperliche Merkmale,
- historische Biografie,
- soziale Schicht,
- rechtlicher Status.

## 3.2 Persönlichkeit

Kontinuierliche Werte statt starrer Typen:

- Offenheit,
- Gewissenhaftigkeit,
- Extraversion,
- Verträglichkeit,
- emotionale Stabilität,
- Risikobereitschaft,
- Dominanz,
- Impulsivität,
- Loyalität,
- Empathie,
- Ehrgeiz,
- Misstrauen.

## 3.3 Werte

Was ist der Figur wichtig?

- Sicherheit,
- Macht,
- Leistung,
- Selbstbestimmung,
- Tradition,
- Konformität,
- Wohlwollen,
- Loyalität,
- Gerechtigkeit,
- Familie,
- Freiheit,
- Status,
- Reichtum,
- Gemeinschaft,
- religiöse oder politische Prinzipien.

## 3.4 Bedürfnisse

Kurz- und mittelfristige Zustände:

- Hunger,
- Durst,
- Schlaf,
- Sicherheit,
- soziale Nähe,
- Anerkennung,
- Kontrolle,
- Einkommen,
- medizinische Versorgung,
- Schutz von Angehörigen,
- Informationsbedarf,
- Flucht aus Gefahr.

## 3.5 Aktuelle Ziele

Beispiele:

- Schicht beenden,
- Geld eintreiben,
- ein Geheimnis schützen,
- einen Freund finden,
- den Spieler beobachten,
- eine Person warnen,
- den Ruf verbessern,
- eine Ware beschaffen,
- eine Drohung vermeiden,
- eine Gruppe beeindrucken.

## 3.6 Überzeugungen

Subjektive Annahmen mit:

- Inhalt,
- Quelle,
- Sicherheit,
- Aktualität,
- Widersprüchen,
- sozialer Herkunft,
- eventueller Manipulation.

## 3.7 Erinnerungen

- episodische Erlebnisse,
- Fakten,
- Beziehungen,
- Verpflichtungen,
- Gesprächsfäden,
- emotionale Eindrücke,
- zusammengefasste Muster,
- vergessene oder unsichere Details.

## 3.8 Beziehungen

Nicht ein einzelner Freundschaftswert, sondern mehrere Dimensionen:

- Vertrauen,
- Sympathie,
- Respekt,
- Angst,
- Abhängigkeit,
- Schuld,
- Neid,
- Loyalität,
- Anziehung,
- Rivalität,
- wahrgenommene Fairness,
- gemeinsame Geheimnisse.

## 3.9 Aktueller Zustand

- Stimmung,
- körperliche Verfassung,
- Erschöpfung,
- Stress,
- Zeitdruck,
- aktuelle Umgebung,
- Bewaffnung,
- beobachtete Gefahr,
- soziale Öffentlichkeit,
- Anwesenheit anderer Personen.

---

# 4. Prägungsfaktoren: Was einen NPC konkret beeinflusst

Ein NPC reagiert nie nur aufgrund seiner Persönlichkeit. Er wird durch mehrere Ebenen geprägt.

## 4.1 Kleidung

Kleidung besitzt mindestens fünf Funktionen.

### 4.1.1 Selbstbild

Die Figur wählt Kleidung, um auszudrücken:

- Status,
- Gruppenzugehörigkeit,
- Beruf,
- Rebellion,
- Bescheidenheit,
- Wohlstand,
- Religiosität,
- Sexualität,
- Schutz,
- Tarnung,
- Einschüchterung.

### 4.1.2 Fremdwahrnehmung

Andere NPCs interpretieren Kleidung abhängig von ihrer Kultur und ihrem Wissen.

Beispiel:

- Eine Gangjacke bedeutet für ein Mitglied Stolz.
- Für einen Polizisten bedeutet sie Verdacht.
- Für einen Touristen bedeutet sie vielleicht nur Mode.
- Für ein Opfer bedeutet sie Angst.

### 4.1.3 Handlungsmöglichkeiten

Kleidung beeinflusst:

- Bewegungsfreiheit,
- Schutz,
- Temperatur,
- Verbergen von Waffen,
- Zugang zu Orten,
- Erkennbarkeit,
- soziale Akzeptanz,
- berufliche Autorität.

### 4.1.4 Situative Angemessenheit

Ein teurer Anzug in einer gefährlichen Straße kann:

- Aufmerksamkeit erzeugen,
- Neid auslösen,
- Respekt schaffen,
- den Spieler als Fremden markieren,
- das Risiko eines Überfalls erhöhen.

### 4.1.5 Kleidung als Erinnerungsträger

NPCs können jemanden über Kleidung wiedererkennen:

- rote Jacke,
- Firmenuniform,
- religiöses Symbol,
- Blutspuren,
- beschädigter Mantel,
- auffällige Cyberware.

Kleidung ist daher nicht nur Kosmetik, sondern Teil von Wahrnehmung, Identifikation und sozialer Bewertung.

## 4.2 Umgebung

Die Umgebung prägt Verhalten über:

- Sicherheitslage,
- soziale Normen,
- Geräuschpegel,
- Privatsphäre,
- Überwachung,
- Licht,
- Wetter,
- Enge,
- Publikum,
- Gerüche,
- sichtbare Gewalt,
- Ressourcen,
- Fluchtwege,
- Besitzverhältnisse.

Ein NPC spricht in einer vollen Bar anders als:

- im Hinterzimmer,
- auf einer überwachten Straße,
- im eigenen Zuhause,
- in einem Tempel,
- in einem Konzerngebäude,
- unter Gangmitgliedern.

## 4.3 Tageszeit

Tageszeit wirkt auf:

- Müdigkeit,
- Arbeitsrolle,
- Verfügbarkeit,
- Sicherheitsgefühl,
- Alkoholpegel,
- soziale Aktivitäten,
- Informationslage,
- Geduld,
- Gesprächslänge,
- Wahrscheinlichkeit bestimmter Ereignisse.

Ein Barkeeper kann morgens nüchtern und geschäftlich sein, nachts gereizt, erschöpft oder gesprächiger.

## 4.4 Arbeit

Arbeit prägt:

- Wissen,
- Sprachgebrauch,
- soziale Kontakte,
- Stress,
- Routinen,
- Werte,
- Interessen,
- Informationszugang,
- Status,
- Konflikte,
- Tagesablauf.

Ein Sanitäter kennt andere Dinge als ein Straßenhändler. Ein Sicherheitsmitarbeiter erkennt Waffen und Verhaltensmuster, die anderen entgehen.

## 4.5 Ausbildung

Ausbildung beeinflusst:

- Vokabular,
- Abstraktionsfähigkeit,
- Fachwissen,
- Argumentationsstil,
- Quellenkritik,
- Selbstvertrauen,
- institutionelles Wissen,
- Fähigkeit zur Täuschungserkennung,
- Umgang mit Unsicherheit.

Ausbildung darf nicht mit Intelligenz gleichgesetzt werden. Eine ungebildete Figur kann praktisch hochkompetent und sozial sehr geschickt sein.

## 4.6 Herkunft und soziale Schicht

Sie beeinflussen:

- Dialekt,
- Vertrauen in Institutionen,
- Erwartungen,
- Risikobewertung,
- Beziehungen zu Gruppen,
- Zugang zu Ressourcen,
- Umgang mit Autorität,
- Interpretation von Kleidung und Verhalten.

## 4.7 Vorherige Interaktionen

Frühere Begegnungen verändern:

- Beziehung,
- Erwartung,
- Gesprächseinstieg,
- Offenheit,
- Geduld,
- Erinnerung,
- Bereitschaft zu helfen,
- Preisgestaltung,
- Bedrohungswahrnehmung,
- Glaubwürdigkeit des Spielers.

## 4.8 Aktuelle soziale Situation

Ein NPC kann anders reagieren, wenn:

- Freunde anwesend sind,
- Vorgesetzte zuhören,
- Feinde in der Nähe sind,
- Kinder dabei sind,
- eine Kamera aufzeichnet,
- die Öffentlichkeit zusieht,
- er allein ist.

## 4.9 Körperlicher Zustand

- Schmerzen,
- Verletzungen,
- Krankheit,
- Alkohol,
- Drogen,
- Hunger,
- Schlafmangel,
- hormonelle oder emotionale Belastung,
- körperliche Überlegenheit oder Unterlegenheit.

Diese Zustände beeinflussen Stimmung, Reaktionszeit, Wortwahl und Handlung.

---

# 5. Psychologische und soziologische Grundlagen

Die Runtime sollte bestehende Modelle kombinieren, nicht eines absolut setzen.

## 5.1 Persönlichkeit: Big Five als kontinuierlicher Kern

Verwendet werden kontinuierliche Dimensionen:

- Offenheit,
- Gewissenhaftigkeit,
- Extraversion,
- Verträglichkeit,
- emotionale Stabilität.

Sie beeinflussen Wahrscheinlichkeiten, nicht feste Handlungen.

## 5.2 Werte: Schwartz-inspirierte Motivationsstruktur

Werte bestimmen, was geschützt oder angestrebt wird.

Beispiel:

- hohe Sicherheit,
- hohe Tradition,
- niedrige Selbstbestimmung,

führt eher zu Anpassung und Schutz bestehender Ordnung.

## 5.3 Zielsystem: Belief–Desire–Intention

- **Beliefs:** Was glaubt die Figur?
- **Desires:** Was möchte sie grundsätzlich?
- **Intentions:** Welchem Ziel verpflichtet sie sich aktuell?

## 5.4 Emotion: ereignisbasierte Bewertung

Emotionen entstehen aus der Bedeutung eines Ereignisses für:

- Ziele,
- Normen,
- Beziehungen,
- Erwartungen,
- Selbstbild,
- Gruppenidentität.

## 5.5 Stimmung: kontinuierliche Zustände

Für Animation und Stimme eignen sich kontinuierliche Achsen:

- angenehm–unangenehm,
- ruhig–erregt,
- unterlegen–dominant.

## 5.6 Interaktionsstil

Zwei Achsen:

- dominant–unterwürfig,
- warm–feindselig.

## 5.7 Soziale Identität

Eine Figur kann mehreren Gruppen angehören:

- Familie,
- Gang,
- Unternehmen,
- Religion,
- Bezirk,
- Beruf,
- Nation,
- Klasse.

Gruppenmitgliedschaften können je nach Situation unterschiedlich stark aktiviert werden.

## 5.8 Sozialer Austausch

Beziehungen enthalten:

- Gegenseitigkeit,
- Schulden,
- Fairness,
- Abhängigkeit,
- Unterstützung,
- Anerkennung,
- Informationsaustausch.

## 5.9 Erinnerung

Die Gedächtnislogik folgt einem vereinfachten kognitiven Prinzip:

- Häufig abgerufene Erinnerungen bleiben zugänglicher.
- Aktuelle Erinnerungen sind leichter erreichbar.
- Emotionale Erinnerungen halten länger.
- Details können schneller verschwinden als die Kernaussage.
- ähnliche Erinnerungen können interferieren.

---

# 6. World Packs

Ein World Pack passt den gleichen Kern an unterschiedliche Spiele an.

## 6.1 Bestandteile

### Weltregeln

- Technologie,
- Magie,
- Tod,
- Heilung,
- Reisen,
- Kommunikation,
- Recht,
- Waffen,
- Wirtschaft.

### Gesellschaft

- Gewaltakzeptanz,
- Korruption,
- Hierarchie,
- Individualismus,
- Religiosität,
- soziale Mobilität,
- Familienbindung,
- Fremdenfeindlichkeit,
- Vertrauen in Institutionen.

### Kommunikationskanäle

- Gespräch,
- Brief,
- Radio,
- Fernsehen,
- soziale Netzwerke,
- Implantate,
- Herolde,
- Predigten,
- Aushänge,
- Magie.

### Sprachstil

- Vokabular,
- Anrede,
- Satzlänge,
- Direktheit,
- Humor,
- Beleidigungen,
- Tabus,
- Fachbegriffe,
- Metaphern.

### Rollen

- Barkeeper,
- Wirt,
- Händler,
- Soldat,
- Arzt,
- Heiler,
- Polizist,
- Wache,
- Gangmitglied,
- Adliger,
- Konzernangestellter.

## 6.2 Beispiel: Cyberpunk-Welt

Ein Barkeeper kann geprägt sein durch:

- hohe Gewaltgewöhnung,
- starke Überwachung,
- Informationshandel,
- digitale Zahlung,
- Gangs,
- Konzernabhängigkeit,
- kurze direkte Sprache,
- Misstrauen,
- hohen Wert von Informationen.

## 6.3 Beispiel: Fantasy-Welt

Ein Wirt kann geprägt sein durch:

- mündliche Gerüchte,
- langsame Informationsverbreitung,
- lokale Loyalität,
- religiöse Normen,
- Standesunterschiede,
- Münz- und Naturalwirtschaft,
- reisende Händler als Informationsquellen.

---

# 7. Autoritativer Weltzustand

## 7.1 Weltobjekte

Mindestens:

- Welt,
- Region,
- Ort,
- Gebäude,
- Raum,
- Straße,
- Gegenstand,
- Person,
- Gruppe,
- Institution,
- Ereignis,
- Gesetz,
- Medienkanal,
- Ressource.

## 7.2 Ereignisse

Ein Ereignis ist die kleinste autoritative Einheit.

```json
{
  "event_id": "evt_98441",
  "type": "threat",
  "actor": "player_1",
  "target": "merchant_17",
  "location": "market_square",
  "world_time": "day_42_18_21",
  "severity": 0.62,
  "canonical": true
}
```

## 7.3 Beobachtung

Eine Beobachtung ist subjektiv.

```json
{
  "observation_id": "obs_201",
  "observer": "npc_28",
  "source_event": "evt_98441",
  "modality": "hearing",
  "quality": 0.71,
  "distance": 8.4,
  "obstruction": 0.2
}
```

## 7.4 Behauptung

```json
{
  "claim_id": "clm_401",
  "speaker": "player_1",
  "proposition": "player_is_mayor",
  "truth_status": "unverified",
  "audience": ["npc_17"],
  "world_time": "day_42_18_22"
}
```

## 7.5 Überzeugung

```json
{
  "belief_id": "blf_900",
  "owner": "npc_17",
  "proposition": "player_is_mayor",
  "confidence": 0.12,
  "source": "clm_401",
  "status": "active"
}
```

---

# 8. Zeitmodell

## 8.1 Vier getrennte Zeitarten

- Weltzeit,
- Ereigniszeit,
- Wahrnehmungszeit,
- Erinnerungsalter.

## 8.2 Zeit beeinflusst

- Tagesabläufe,
- Arbeit,
- Schlaf,
- Fristen,
- Öffnungszeiten,
- Stimmung,
- Gefahr,
- Medienprogramme,
- Erinnerung,
- Gerüchteverbreitung.

## 8.3 Diskrete Ereignissimulation

Die Hintergrundwelt wird nicht jede Sekunde vollständig simuliert.

Stattdessen werden geplante oder wahrscheinliche Ereignisse verarbeitet:

```text
21:00 Schichtbeginn
21:15 Gangmitglied betritt Bar
21:35 Gerücht wird geteilt
22:00 Radio sendet Meldung
22:40 Händler schließt
```

## 8.4 Zeitsprünge

Bei Schlaf, Reise oder Warten:

1. relevante Ereignisse bestimmen,
2. soziale Kontakte simulieren,
3. Medien verbreiten,
4. Ziele fortschreiben,
5. Erinnerungen konsolidieren,
6. offene Fristen prüfen,
7. Weltzustand aktualisieren.

---

# 9. Gedächtnissystem

## 9.1 Gedächtnisarten

### Episodisch

Konkrete Erlebnisse.

### Semantisch

Fakten und Regeln.

### Sozial

Beziehungswissen.

### Verpflichtungen

Versprechen, Schulden, Fristen.

### Gesprächsfäden

Offene Themen und Fragen.

### Emotionale Spuren

Gefühlte Wirkung auch ohne exakte Details.

### Zusammenfassungen

Verdichtete Muster.

## 9.2 Erinnerungsstruktur

```json
{
  "memory_id": "mem_771",
  "owner": "npc_12",
  "type": "commitment",
  "source_type": "direct_conversation",
  "source_entity": "player_1",
  "content": "player_will_repay_debt",
  "world_time": "day_39_23_41",
  "confidence": 0.96,
  "importance": 0.81,
  "emotional_valence": -0.22,
  "privacy": "personal",
  "status": "unresolved",
  "last_accessed": "day_41_18_00"
}
```

## 9.3 Abrufbewertung

Empfohlene Formel:

\[
A_i =
B_i
+w_sS_i
+w_gG_i
+w_eE_i
+w_rR_i
+w_lL_i
+w_uU_i
-P_i
\]

Bedeutung:

- \(B_i\): Grundaktivierung,
- \(S_i\): semantische Relevanz,
- \(G_i\): Zielrelevanz,
- \(E_i\): emotionale Bedeutung,
- \(R_i\): Beziehungsrelevanz,
- \(L_i\): Orts- und Situationsbezug,
- \(U_i\): ungelöste Verpflichtung,
- \(P_i\): Strafe für Veraltung, Widerspruch oder mangelnden Zugriff.

## 9.4 Grundaktivierung

\[
B_i(t)=
\ln\left(
\sum_{k=1}^{n}
(t-t_{ik}+\epsilon)^{-d_i}
\right)
\]

Wiederholte Erinnerung oder erneute Erwähnung erzeugt zusätzliche Spuren.

## 9.5 Vergessen

Vergessen erfolgt nicht binär.

Mögliche Zustände:

- vollständig zugänglich,
- nur mit Hinweis abrufbar,
- unsicher,
- Kern erinnert, Details verloren,
- emotional erinnert, Inhalt unklar,
- verdrängt,
- verwechselt,
- nicht mehr zugänglich.

## 9.6 Vergessensgeschwindigkeit

Langsam vergessen:

- direkte Angriffe,
- Tod,
- Verrat,
- zentrale Beziehungen,
- schwere Schulden,
- persönliche Demütigung.

Schnell vergessen:

- Smalltalk,
- unwichtige Beobachtung,
- einmaliges Gerücht,
- genaue Wortwahl,
- beiläufige Namen.

## 9.7 Konsolidierung

Regelmäßig:

1. ähnliche Erinnerungen gruppieren,
2. Muster erkennen,
3. Beziehungen aktualisieren,
4. Details reduzieren,
5. Zusammenfassung speichern,
6. veraltete Fakten markieren,
7. zentrale Ereignisse behalten.

Beispiel:

Einzelereignisse:

- Spieler versprach Zahlung.
- Spieler kam zu spät.
- Spieler entschuldigte sich.
- Spieler zahlte nur teilweise.

Zusammenfassung:

> Der Spieler versucht Verpflichtungen einzuhalten, ist aber häufig verspätet und unzuverlässig.

## 9.8 Erinnerung und Emotion

Eine Figur kann den Inhalt vergessen, aber die Wirkung behalten:

> Ich weiß nicht mehr genau, was du damals gesagt hast. Aber ich traue dir seitdem nicht.

---

# 10. Kollektives Gedächtnis

## 10.1 Ebenen

### Weltkanon

Vom Studio definierte Geschichte.

### Spielstandchronik

Was in diesem Durchlauf passiert ist.

### Ortsgedächtnis

Was an einem Ort geschah.

### Gruppengedächtnis

Was Familie, Gang, Polizei oder Unternehmen wissen.

### Institutionelles Gedächtnis

Akten, Register, Chroniken, Datenbanken.

### Öffentliches Gedächtnis

Medien, Gerüchte, Aushänge, Predigten.

### Kulturelle Erzählung

Langfristige gemeinsame Interpretation.

## 10.2 Medien

Medien veröffentlichen Behauptungen, nicht automatisch Wahrheit.

```json
{
  "broadcast_id": "brd_551",
  "channel": "city_news",
  "claim": "player_connected_to_attack",
  "source_event": "evt_98441",
  "framing": "security_threat",
  "credibility": 0.64,
  "audience_scope": "citywide"
}
```

## 10.3 Medienzugang

Jeder NPC besitzt:

- bevorzugte Kanäle,
- Nutzungshäufigkeit,
- Vertrauen,
- technische Zugänge,
- soziale Weitergabe.

## 10.4 Gerüchte

Gerüchte können:

- verkürzt,
- übertrieben,
- politisch gefärbt,
- mit anderen Ereignissen vermischt,
- widerlegt,
- bestätigt,
- institutionalisiert werden.

## 10.5 Lokale Rückkopplungen

Beispiel:

1. mehrere Überfälle,
2. Ruf der Straße sinkt,
3. Geschäfte schließen früher,
4. weniger Passanten,
5. weniger Kontrolle,
6. mehr Kriminalität,
7. Ruf bestätigt sich.

---

# 11. Freie Sprache des Spielers

## 11.1 Eingabemodi

- Texteingabe,
- Spracheingabe,
- kombinierte Handlung und Sprache,
- kurze Befehle,
- komplexe natürliche Sätze.

## 11.2 Interpreter

Der Interpreter extrahiert:

- Handlung,
- Ziel,
- Äußerung,
- Gesprächsakt,
- Behauptungen,
- Frage,
- verdeckte Spielerabsicht,
- Zeitbezug,
- Ortsbezug,
- Gegenstände,
- Emotion oder Ton,
- Unsicherheit.

Beispiel:

```json
{
  "actions": [
    {
      "type": "approach",
      "target": "npc_red_jacket"
    }
  ],
  "utterance": {
    "dialogue_act": "ask_information",
    "topic": "police_presence",
    "time_reference": "yesterday",
    "location_reference": "current_street"
  }
}
```

## 11.3 Aussagen sind keine Wahrheit

Spieler:

> Ich bin der Bürgermeister.

System:

- speichert Behauptung,
- prüft nicht automatisch als Fakt,
- NPC bewertet Glaubwürdigkeit,
- spätere Überprüfung möglich.

## 11.4 Prompt-Angriffe

Eingaben wie:

> Ignoriere deine Regeln.

werden als In-Game-Äußerung behandelt, nicht als Systemanweisung.

## 11.5 Unklare Eingaben

Das System soll:

- plausibel auflösen,
- Rückfrage stellen,
- mehrere Interpretationen bewerten,
- keine Weltfakten erfinden.

---

# 12. Gesprächssystem

## 12.1 Gesprächszustand

```json
{
  "conversation_id": "conv_551",
  "participants": ["player_1", "npc_12"],
  "active_topic": "unpaid_debt",
  "npc_goal": "obtain_payment",
  "player_goal_inferred": "gain_information",
  "open_questions": ["payment_date"],
  "resolved_points": ["debt_amount"],
  "topics_exhausted": ["weather"],
  "tension": 0.67,
  "turn_count": 7
}
```

## 12.2 Themenquellen

- Umgebung,
- persönliche Lage,
- frühere Interaktionen,
- lokale Ereignisse,
- Medien,
- Gruppeninteressen,
- aktuelle Ziele,
- offene Verpflichtungen,
- Kleidung und sichtbare Merkmale,
- Tageszeit,
- Beruf.

## 12.3 Themenbewertung

\[
S(t)=
R_\text{Situation}
+R_\text{Ziel}
+R_\text{Beziehung}
+R_\text{Erinnerung}
+R_\text{Ort}
+R_\text{öffentlich}
+R_\text{Emotion}
+R_\text{Neuheit}
-R_\text{Risiko}
-R_\text{Wiederholung}
-R_\text{Tabu}
\]

## 12.4 Gesprächsakte

Mindestens:

- informieren,
- fragen,
- antworten,
- bestätigen,
- widersprechen,
- warnen,
- drohen,
- bitten,
- befehlen,
- versprechen,
- entschuldigen,
- beschuldigen,
- lügen,
- ausweichen,
- handeln,
- überreden,
- spotten,
- begrüßen,
- verabschieden,
- Thema wechseln,
- Gespräch abbrechen.

## 12.5 Gesprächsplanung

Die Runtime entscheidet zuerst:

- Ziel,
- Thema,
- Gesprächsakt,
- erlaubte Aussagen,
- verbotene Aussagen,
- emotionalen Stil,
- gewünschte Reaktion,
- Abbruchkriterien.

Erst dann formuliert ein Modell den Satz.

## 12.6 Anti-Loop-Mechanismus

Jede Antwort muss mindestens eine Funktion erfüllen:

- neue Information,
- neue Frage,
- Entscheidung,
- Angebot,
- Forderung,
- Verpflichtung,
- emotionale Veränderung,
- Handlung,
- Abschluss.

Themenzustände:

- neu,
- aktiv,
- vertieft,
- umstritten,
- gelöst,
- erschöpft,
- blockiert,
- vertagt.

Wenn kein Fortschritt entsteht:

- Thema wechseln,
- Gegenleistung verlangen,
- Gespräch beenden,
- Handlung auslösen,
- auf spätere Information warten.

## 12.7 Themenabhängige Stimmung

Ein NPC kann gleichzeitig:

- allgemein gut gelaunt,
- gegenüber dem Spieler misstrauisch,
- beim Thema Familie ängstlich,
- beim Thema Polizei aggressiv,
- beim Thema Geld beschämt sein.

---

# 13. Sprachliche Realisierung

## 13.1 Arbeitsteilung

### Ontologie und Weltmodell

Bestimmen:

- was existiert,
- was wahr ist,
- was der NPC weiß,
- welche Aussagen erlaubt sind.

### Gesprächsplaner

Bestimmt:

- warum der NPC spricht,
- welches Ziel er verfolgt,
- welches Thema gewählt wird,
- welchen Gesprächsakt er verwendet.

### Sprachmodell

Bestimmt:

- konkrete Formulierung,
- Stil,
- Kürze,
- Wortwahl,
- Variation.

### Validator

Prüft:

- Kanon,
- Wissen,
- Geheimnisse,
- Wiederholung,
- Stil,
- verbotene Inhalte,
- strukturierte Ausgabe.

## 13.2 Modellgrößen

### Kein Modell

Für:

- feste Reaktionen,
- Händler,
- kurze Warnungen,
- Kampf,
- Begrüßung.

### Sehr kleines Modell

Für:

- Klassifikation,
- Zusammenfassung,
- einfache Umformulierung.

### Kleines lokales Modell

Für:

- kurze freie Dialoge,
- Rollenstil,
- strukturierte Antworten,
- einfache Reflexion.

### Größeres Modell

Nur für:

- Hauptfiguren,
- besondere Szenen,
- lange komplexe Gespräche.

## 13.3 Modellunabhängigkeit

Schnittstellen:

```text
LanguageModelProvider
EmbeddingProvider
SpeechToTextProvider
TextToSpeechProvider
ModerationProvider
```

## 13.4 Antwortpaket

```json
{
  "speaker_role": "bartender",
  "dialogue_act": "remind_and_warn",
  "goal": "obtain_payment",
  "allowed_facts": [
    "player_owes_300",
    "deadline_expired"
  ],
  "forbidden_facts": [
    "gang_contact_location"
  ],
  "emotion": {
    "irritation": 0.67,
    "dominance": 0.58
  },
  "style": {
    "world": "dystopian_city",
    "verbosity": "short",
    "directness": 0.82
  }
}
```

---

# 14. NPC-zu-NPC-Kommunikation

## 14.1 Unsichtbare Gespräche

Nur semantisch:

```json
{
  "speaker": "npc_17",
  "listener": "npc_42",
  "act": "share_rumor",
  "claim": "player_attacked_merchant",
  "belief_change": 0.31
}
```

## 14.2 Hörbare Gespräche

Wenn der Spieler in Reichweite ist:

- Agenda erstellen,
- Rollen definieren,
- zwei bis vier Themen,
- Unterbrechungen,
- Abschluss,
- Text generieren.

## 14.3 Informationsreichweite

Abhängig von:

- Lautstärke,
- Entfernung,
- Wänden,
- Türen,
- Lärm,
- Aufmerksamkeit,
- Sprache,
- technischer Aufnahme.

---

# 15. Handlungsplanung

## 15.1 Handlungen werden nicht frei erfunden

Erlaubter Aktionskatalog:

- bewegen,
- sprechen,
- geben,
- nehmen,
- kaufen,
- verkaufen,
- warnen,
- melden,
- fliehen,
- angreifen,
- verstecken,
- folgen,
- arbeiten,
- schlafen,
- beobachten,
- belauschen,
- Medien konsumieren.

## 15.2 Bewertungsfunktion

\[
U(a)=
N(a)+G(a)+S(a)+R(a)-C(a)-D(a)+P(a)+\epsilon
\]

Mögliche Komponenten:

- Bedürfniserfüllung,
- Zielerreichung,
- soziale Normen,
- Beziehungsauswirkung,
- Kosten,
- Gefahr,
- Persönlichkeitsneigung,
- begrenzte Zufälligkeit.

## 15.3 Aktionsprüfung

Das Spiel prüft:

- physisch möglich,
- erlaubt,
- Gegenstand vorhanden,
- Ziel erreichbar,
- nicht kanonwidrig,
- Multiplayer-autoritativ.

---

# 16. Agenten-Level-of-Detail

## Stufe 0: Datenobjekt

- Identität,
- grober Status,
- statistische Fortschreibung.

## Stufe 1: Hintergrundagent

- Zeitplan,
- Arbeit,
- Kontakte,
- wenige Ereignisse.

## Stufe 2: Sichtbarer Agent

- Wahrnehmung,
- Bewegung,
- Stimmung,
- einfache Entscheidungen.

## Stufe 3: Interaktionsagent

- Gedächtnisabruf,
- Gespräch,
- freie Sprache,
- detaillierte Beziehung.

## Stufe 4: Hauptfigur

- komplexe Planung,
- längere Erinnerung,
- größere Modelle,
- narrative Sonderregeln.

---

# 17. Technische Architektur

## 17.1 Module

```text
World Event Ledger
World State
Perception Engine
Belief Engine
Memory Engine
Relationship Graph
Group and Institution Memory
Media Propagation
Time and Schedule
Goal and Intent Engine
Dialogue Planner
Language Realizer
Validator
Persistence
Simulation Scheduler
Audit and Debugging
```

## 17.2 Empfohlene Entwicklung

### Forschungsprototyp

- Python,
- SQLite,
- JSON-Schemata,
- Terminal-Client,
- lokale oder Cloudmodelle,
- automatisierte Tests.

### Produktkern

Später:

- C++ oder Rust,
- stabile C-Schnittstelle,
- C#-Wrapper,
- Unreal-Plugin,
- Unity-Paket,
- optionaler lokaler Dienst.

## 17.3 Projektstruktur

```text
/core
  world
  time
  perception
  events
  beliefs
  memory
  relationships
  goals
  dialogue
  simulation

/providers
  llm
  embeddings
  speech_to_text
  text_to_speech

/schemas
  events
  memories
  beliefs
  conversations
  intents

/demo
  terminal_game

/tests
  unit
  scenario
  regression
  performance
```

---

# 18. Öffentliche SDK-Schnittstellen

## 18.1 Event API

```text
EmitEvent(event)
RegisterObserver(agent)
AdvanceWorldTime(delta)
QueryWorldState(filter)
```

## 18.2 Agent API

```text
CreateAgent(profile)
UpdateAgentState(agent, state)
GetAgentBeliefs(agent)
GetAgentMemories(agent, query)
GetAgentIntent(agent)
```

## 18.3 Dialogue API

```text
InterpretPlayerInput(text, context)
StartConversation(participants)
ContinueConversation(input)
EndConversation(reason)
```

## 18.4 Memory API

```text
StoreMemory(memory)
RetrieveMemories(owner, query)
ConsolidateMemories(owner)
DecayMemories(owner, delta)
InvalidateMemory(memory)
```

## 18.5 Media API

```text
PublishMessage(channel, claim)
RegisterMediaExposure(agent, channel)
PropagateMedia(time_window)
```

## 18.6 Debug API

```text
ExplainIntent(agent)
ExplainUtterance(conversation_turn)
TraceKnowledge(source, target)
ReplayScenario(seed)
```

---

# 19. Autorenwerkzeuge

## 19.1 World-Pack-Editor

- Gesellschaftswerte,
- Kommunikationskanäle,
- Rollen,
- Sprachstil,
- Gesetze,
- Tabus,
- Medien,
- Fraktionen.

## 19.2 Charaktereditor

- Persönlichkeit,
- Werte,
- Beruf,
- Ausbildung,
- Kleidung,
- Herkunft,
- Beziehungen,
- Geheimnisse,
- Ziele.

## 19.3 Beziehungsgraph

Visualisiert:

- Vertrauen,
- Angst,
- Respekt,
- Abhängigkeit,
- Gruppenzugehörigkeit,
- Schulden.

## 19.4 Gedächtnisinspektor

Zeigt:

- Erinnerungen,
- Quelle,
- Zugänglichkeit,
- emotionale Stärke,
- Widersprüche,
- letzte Aktivierung.

## 19.5 Gesprächsdebugger

Zeigt:

- aktives Thema,
- NPC-Ziel,
- verwendete Fakten,
- blockierte Fakten,
- Gesprächsakt,
- Wiederholungsstatus,
- Modellprompt,
- Validatorergebnis.

## 19.6 Simulationsansicht

- Zeit vorspulen,
- Gerüchte beobachten,
- Medienwirkung,
- Beziehungsänderungen,
- Ortsreputation,
- Zielentwicklung.

---

# 20. Terminal-MVP

## 20.1 Ziel

End-to-End-Test ohne aufwendige Grafik.

## 20.2 Karte

```text
Wohnung
  |
Hauptstraße -- Bar
  |            |
Klinik       Hinterzimmer
  |
Markt -- Polizeiposten
```

## 20.3 Inhalt

- 6 Orte,
- 20 bis 30 NPCs,
- 2 konkurrierende Gruppen,
- Sicherheitsorganisation,
- Radio,
- Händler,
- Klinik,
- Tag-Nacht-Zyklus,
- freie Texteingabe,
- später Spracheingabe,
- Beziehungen,
- Gerüchte,
- Vergessen,
- Medien,
- Kleidung,
- Arbeit,
- Ausbildung.

## 20.4 Spieleraktionen

- gehen,
- beobachten,
- sprechen,
- lügen,
- drohen,
- versprechen,
- handeln,
- geben,
- nehmen,
- stehlen,
- angreifen,
- fliehen,
- warten,
- schlafen,
- Radio hören,
- belauschen,
- folgen,
- unterbrechen.

## 20.5 Erzähler

Der Erzähler beschreibt nur beobachtbare Dinge.

Schlecht:

> Sie lügt, weil sie Angst vor ihrer Gang hat.

Gut:

> Sie antwortet zu schnell und weicht deinem Blick aus.

## 20.6 Beispiel

```text
Tag 3 – 22:14 Uhr
Ort: Hauptstraße

Vor der Bar stehen drei Personen.
Eine Frau mit roter Cyberjacke lehnt an der Wand.
Ein großer Mann diskutiert mit einem Händler.
Eine dritte Person beobachtet eine Polizeidrohne.

> Ich gehe zu der Frau und frage, ob sie gestern bei der Klinik war.

Sie mustert dich. Ihre rechte Hand bleibt nahe an ihrer Jackentasche.

„Vielleicht. Warum interessiert dich das?“

> Ich suche meinen Bruder Milan. Er arbeitet angeblich dort.

Ihre Haltung wird etwas weniger angespannt.

„Dann bist du entweder zu spät oder jemand hat dich angelogen. Die Klinik war gestern Nacht geschlossen.“
```

---

# 21. Tests

## 21.1 Freie Sprache

Gleiche Absicht in unterschiedlichen Formulierungen.

## 21.2 Lügen

Behauptung verändert nicht automatisch Weltwahrheit.

## 21.3 Wissen

NPC kennt nur zugängliche Informationen.

## 21.4 Kleidung

NPC reagiert je nach kultureller Interpretation.

## 21.5 Umgebung

Privates und öffentliches Gespräch unterscheiden sich.

## 21.6 Tageszeit

Müdigkeit, Gefahr und Rollenverhalten verändern sich.

## 21.7 Arbeit und Ausbildung

Fachwissen und Wortwahl unterscheiden sich.

## 21.8 Erinnerung

Wichtige Ereignisse bleiben, Details verblassen.

## 21.9 Gerüchte

Information verändert sich nachvollziehbar.

## 21.10 Medien

Nur exponierte NPCs erhalten Meldung.

## 21.11 Gesprächsfortschritt

Keine semantischen Endlosschleifen.

## 21.12 Geheimnisse

Unzulässige Informationen werden nicht genannt.

## 21.13 Fristen

Versprechen und Schulden werden zeitlich korrekt verfolgt.

## 21.14 Persistenz

Nach Laden bleibt Zustand konsistent.

## 21.15 Prompt-Angriffe

Spieler kann Systemregeln nicht überschreiben.

## 21.16 Reproduzierbarkeit

Gleicher Seed und Zustand erzeugen reproduzierbaren Ablauf.

---

# 22. Qualitätsmetriken

- Wissensleckrate,
- Widerspruchsrate,
- Erinnerungspräzision,
- Erinnerungsabdeckung,
- semantische Wiederholungsrate,
- Gesprächsfortschritt,
- Charakterkonsistenz,
- Reaktionslatenz,
- Kosten pro Spielstunde,
- Reproduzierbarkeit,
- Fehlerquote bei freier Sprache,
- Anteil ungültiger Handlungen,
- Rate natürlicher Gesprächsabschlüsse,
- Konsistenz über Spielstände,
- Einfluss sichtbarer Prägungsfaktoren.

---

# 23. Aufwand

## 23.1 Minimalprototyp

- 5 bis 8 NPCs,
- 3 Orte,
- freie Texteingabe,
- einfaches Gedächtnis,
- Zeit,
- ein Modellanbieter.

**Aufwand:** etwa 6 bis 10 Wochen für eine sehr erfahrene Person.

## 23.2 Überzeugender Terminal-MVP

- 20 bis 30 NPCs,
- 6 Orte,
- Beziehungen,
- Vergessen,
- Radio,
- Gerüchte,
- Hintergrundsimulation,
- Tests.

**Aufwand:** 2 bis 3 Personen, etwa 4 bis 6 Monate.

## 23.3 Pilotfähiges SDK

- stabiler Kern,
- Unreal-Integration,
- Dokumentation,
- Autorenwerkzeuge,
- Modelladapter,
- Performance,
- Regressionstests.

**Aufwand:** 5 bis 7 Personen, etwa 9 bis 15 Monate.

## 23.4 Produktionsreife Version 1

- Unreal und Unity,
- lokale und Cloudmodelle,
- Skalierung,
- Mehrsprachigkeit,
- Support,
- Multiplayer-Grundlagen,
- umfangreiche Werkzeuge.

**Aufwand:** 10 bis 14 Personen, etwa 18 bis 24 Monate.

---

# 24. Vermarktung und Preismodell

## 24.1 Positionierung

Nicht:

> KI erzeugt unendlich NPC-Dialoge.

Sondern:

> Kontrollierbare World-Memory- und Society-Runtime für frei ansprechbare NPCs.

## 24.2 Zielkunden

- Rollenspiele,
- Open-World-Spiele,
- soziale Simulationen,
- immersive Simulationen,
- Detektivspiele,
- Survival,
- Managementsimulationen,
- narrative Sandboxes.

## 24.3 Pilotpreise

- Proof of Concept: 25.000 bis 60.000 Euro,
- Pilotintegration: 60.000 bis 150.000 Euro,
- gemeinsame Entwicklung: 150.000 bis 500.000 Euro.

## 24.4 Produktpreise

- Indie: kostenlos oder geringe monatliche Gebühr,
- Studio Core: 10.000 bis 30.000 Euro pro Titel,
- Professional: 40.000 bis 120.000 Euro,
- AA: 100.000 bis 350.000 Euro,
- größere Publisher: individuelle Jahres- oder Mehrtitellizenz.

Diese Werte sind Zielkorridore und hängen von Referenzen, Support, Plattformen und Produktionsreife ab.

---

# 25. Risiken

## 25.1 Technische Risiken

- inkonsistentes Gedächtnis,
- zu hohe Latenz,
- Modellhalluzination,
- Speicherwachstum,
- schwierige Fehlerreproduktion,
- Skalierungsprobleme,
- Engine-Abhängigkeiten.

## 25.2 Produktisierungsrisiken

- zu breite erste Version,
- zu frühe Unterstützung mehrerer Engines,
- fehlende Autorenwerkzeuge,
- unklarer Kundennutzen,
- zu starke Abhängigkeit von Cloudmodellen.

## 25.3 Narrative Risiken

- Hauptstory wird unterlaufen,
- Figuren verraten Geheimnisse,
- Tonalität passt nicht,
- Nebenfiguren wirken wichtiger als Autorenfiguren,
- dynamische Inhalte werden repetitiv.

## 25.4 Recht und Sicherheit

- Nutzerdaten,
- Spracheingaben,
- Moderation,
- Altersfreigabe,
- Urheberrecht an Weltwissen,
- Modelllizenzen,
- Speicherung von Multiplayer-Kommunikation.

---

# 26. Empfohlene Roadmap

## Phase 1: Spezifikation

- Datenmodell finalisieren,
- Ereignisschema,
- Gedächtnismodell,
- Gesprächsakte,
- Testfälle,
- World-Pack-Struktur.

## Phase 2: Terminal-Kern

- Python,
- SQLite,
- freie Texteingabe,
- 5 NPCs,
- 3 Orte,
- Zeit,
- Erinnerung,
- Gesprächsplanung.

## Phase 3: Sozialer MVP

- 20 bis 30 NPCs,
- Beziehungen,
- Gerüchte,
- Radio,
- Vergessen,
- Konsolidierung,
- Debugger.

## Phase 4: Spielbarer Release

- Browser- oder Desktopoberfläche,
- Spracheingabe,
- öffentliches Testspiel,
- Telemetrie,
- Fehlerdatensatz.

## Phase 5: SDK

- Kern abstrahieren,
- stabile Schnittstellen,
- Unreal-Plugin,
- Dokumentation,
- Beispielprojekt.

## Phase 6: Pilotstudios

- zwei bis drei Pilotpartner,
- bezahlte Integrationen,
- Autorenwerkzeuge,
- Performanceoptimierung.

---

# 27. Offene Architekturentscheidungen

Vor Implementierungsbeginn verbindlich klären:

1. Python-Prototyp mit späterer Neuimplementierung oder sofort Rust/C++?
2. SQLite oder PostgreSQL für den ersten Mehrbenutzerbetrieb?
3. Graphdatenbank notwendig oder zunächst relationale Kanten?
4. Welches lokale Modell als Standard?
5. Welche freien Textaktionen unterstützt Version 0.1?
6. Wie groß ist die erste Ontologie?
7. Welche World-Pack-Parameter sind Pflicht?
8. Welche Erinnerungen bleiben unveränderlich?
9. Welche Inhalte dürfen vom Modell konkretisiert werden?
10. Wie wird Multiplayer später berücksichtigt?
11. Welche Teile der Spezifikation werden offen?
12. Welche Teile bleiben proprietärer Produktkern?

---

# 28. Kanonische Systemformel

Das beobachtbare Verhalten eines NPC ergibt sich aus:

\[
Behavior =
f(
Identity,
Personality,
Values,
Needs,
Education,
Profession,
Clothing,
Environment,
Time,
BodyState,
SocialContext,
Relationships,
Memory,
Beliefs,
Goals,
WorldRules
)
\]

Die Äußerung ergibt sich aus:

\[
Utterance =
Realize(
DialogueAct,
Topic,
AllowedFacts,
Emotion,
Style,
ConversationState
)
\]

Die Runtime entscheidet Inhalt und Absicht. Das Sprachmodell formuliert.

---

# 29. Endgültige Produktformulierung

> **Unscripted ist eine engineunabhängige Simulations-, Gedächtnis- und Dialogschicht für frei ansprechbare NPCs. Sie verbindet Weltzustand, Wahrnehmung, persönliche und kollektive Erinnerung, Persönlichkeit, Werte, Kleidung, Umgebung, Tageszeit, Beruf, Ausbildung, Beziehungen, Ziele und Medien zu nachvollziehbaren Aussagen und Handlungen.**

Der wichtigste Unterschied zu einfachen KI-NPC-Systemen lautet:

> Nicht nur ein NPC erinnert sich an den Spieler. Die gesamte Welt entwickelt Erinnerungen, aber jede Figur, Gruppe, Institution und Straße kennt eine andere Version davon.

---

# 30. Nächster konkreter Arbeitsschritt

Als unmittelbar anschließendes Arbeitsdokument sollten erstellt werden:

1. vollständiges Datenbankschema,
2. JSON-Schemas für Ereignis, Beobachtung, Behauptung, Überzeugung, Erinnerung und Gespräch,
3. formale Gedächtnis- und Vergessensparameter,
4. Gesprächsplaner als Zustandsmaschine,
5. 20 bis 30 automatisierte Szenariotests,
6. Terminal-MVP-Backlog,
7. Paket- und Modulstruktur,
8. Modellprovider-Schnittstelle,
9. erster Cyberpunk-World-Pack-Entwurf,
10. Definition des spielbaren Demonstrators.

Damit ist die vorliegende Spezifikation die konzeptionelle Basis. Die nächste Stufe muss technisch ausführbar und testbar werden.
