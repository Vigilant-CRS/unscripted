# Prüfung des zweiten Korrektheits-Passes

**Stand: 8. September 2026, Commit `fd76623`, Runtime 1.19.0, Snapshot-Schema 11.**

**Nein: „alles korrekt“ und „alle sechs geschlossen“ sind weiterhin zu starke Aussagen.** Mehrere konkrete Reparaturen funktionieren. Es bleiben aber Fehler im Standardmodus, und bei Quellenretention und Weltidentität gelten schwächere Bedingungen als die Zusammenfassungen nahelegen.

Diese Nachprüfung verändert keinen Produktcode. Sie prüft die neuen Freigabe-, Herkunfts- und Save-Verträge mit weiteren Gegenbeispielen. Die Ergebnisse sind in [results.json](results.json) festgehalten und mit [check.py](check.py) reproduzierbar. Sechs Gegenbeispiele gehören zu fünf Befundgruppen; zusätzlich bestätigen zwei unabhängige Prüfungen tatsächlich repariertes Verhalten.

## Was ich bestätigen kann

- `controlled` ist der Standard. Bei einem **bereits als faktisch geplanten** Dialog wird der Provider tatsächlich umgangen. Die früheren direkten Klinik-Gegenbeispiele ändern diese Antwort nicht mehr.
- Der ursprüngliche **ProviderError-Fall** ist behoben. Auch im ausdrücklich gewählten `provider`-Modus erzeugen passende Modellantwort und Providerfehler mit kontrolliertem Ersatz dieselbe behauptete Klinik-Aussage. Die neue unabhängige Probe führt den Provider wirklich aus; sie prüft nicht nur, dass `controlled` ihn überspringt.
- Die **Ledger-Wasserlinie** funktioniert für den geprüften Audit-Fall: Ein späterer Spielzweig erweitert die Abfrage eines früheren, gespeicherten Wasserstands nicht mehr; beide SQL-Ereignisse bleiben vorhanden. Das ist ein echter Abschluss des vorherigen konkreten R5-Gegenbeispiels. Globale Audit-Historie ist weiterhin von Replay eines einzelnen Spielverlaufs zu unterscheiden.
- Der **eine gemeinsame Ortsname** aus dem vorigen Gegenbeispiel reicht nicht mehr. Zwei explizit verschiedene `world_id` werden ebenfalls abgewiesen.
- Ein verdrängter Ursprung erhält jetzt **0,1 statt 1,0** des ersten Gewichts. Der einmalige Verdrängungstest ist somit repariert. Die langfristige Bedeutung steht unter A4.
- Version und Paketmanifest sind konsistent. Die Arbeitskopie war vor der Prüfung sauber, auf Branch `epistemic-correctness-pass`.

## A1 · P1 · Der kontrollierte Realisierer trägt nicht zuverlässig alle freigegebenen Aussagen

**Fundstellen:** [sdk.py](../../../unscripted/sdk.py), `_direct_answer` ab Zeile
968, Auswahl mit `limit=2` um Zeile 1063, `_answer_phrasing` ab Zeile 1326;
[provider.py](../../../unscripted/provider.py), Zeilen 108–133.

### Zwei Inhalte, ein Satz

Ein NPC besitzt die ursprüngliche Überzeugung „Klinik letzte Nacht geschlossen“ und zusätzlich die legitime Überzeugung „Klinik heute offen“. Im **Standardmodus ohne externen Provider** ergibt `respond(..., topic="clinic")`:

```text
Veröffentlicht: Far as I know, the place was shut that night.
Verbreitet:     NOT clinic_open(place=place:clinic, when=last_night)
               clinic_open(place=place:clinic, when=today)
Verdict:        ACCEPT
```

Der heutige Öffnungszustand kommt im Satz nicht vor, wird aber von den Zuhörern gelernt. Die Fixture ergänzt nur einen plausiblen Belief in der temporären Welt. Keine Pack-Datei und kein Engine-Code wurde verändert.

`_direct_answer` wählt bis zu zwei Inhalte. `_answer_phrasing` liefert dagegen eine Formulierung zur Topic-Abfrage. Der Realisierer setzt `expressed_commitment=True`, sobald eine Vorlage vorhanden ist; diese Flagge bestätigt nicht, dass der endgültige Text jeden ausgewählten Move ausdrückt.

### Auch ein einzelner Inhalt kann nachträglich abgeschnitten werden

In einer zweiten Fixture beginnt die korrekte Autorenformulierung mit einem Vorsatz:

```text
Listen carefully. Place was shut that night. That's all I got.
```

Bei stark negativem, erregtem Mood ergibt der vorhandene Stilpfad eine Satzlänge von 4. Der Realisierer kürzt auf **„Listen carefully.“**, behält jedoch sein zuvor gesetztes `expressed_commitment=True`. Ergebnis: `ACCEPT`, und die Klinikbehauptung wird trotzdem verbreitet. Diese Probe variiert erlaubten Autoreninhalt und Affect-Zustand nur im Speicher.

**Folgerung:** „Autorentext statt Modelltext“ reicht als Konstruktionsgarantie nicht. Die endgültige Realisierung muss an **die tatsächlich ausgewählten Moves** gebunden sein und darf ihren Inhalt durch Stilbearbeitung nicht verlieren.

**Abnahme:** Für jeden freigegebenen Move eine dafür autorisierte Realisierung besitzen; alle tatsächlich veröffentlichten Moves zusammen ausdrücken. Varianten und Kürzung dürfen nur zwischen vollständigen, semantisch passenden Realisierungen wählen. Tests mit mehreren Inhalten, Zeitbezügen und kurzen Stilvorgaben ergänzen. Die bloße Existenz einer Topic-Vorlage ist kein geeignetes Orakel.

## A2 · P1 für den behaupteten Schutzumfang · Freie Aussagen erreichen auch `controlled`

**Fundstellen:** [runtime.py](../../../unscripted/runtime.py), `write_the_line`
ab Zeile 1080; [contracts.py](../../../unscripted/contracts.py), Beschreibung
von `semantic_release` ab etwa Zeile 200.

Die Standardkonfiguration lässt den Provider für geplante Begrüßungen, Ausweichantworten und andere Pläne ohne Fakten weiterhin schreiben. Bei Okada beobachtet die unabhängige Probe:

```text
Modus:          controlled
Geplanter Akt:  greet
allowed_facts:  []
avoid_topics:   [brother_whereabouts]
Providertext:  He hides behind where drinks are served.
Veröffentlicht unverändert mit ACCEPT; keine semantischen Moves.
```

Ein **Plan ohne Fakten** macht eine externe Antwort nicht faktisch leer. Der Provider kann weiterhin Behauptungen hinzufügen und indirekte Ortsangaben zu einem Geheimnis veröffentlichen. Der Satz allein benennt Milan nicht; er ist aber gerade die indirekte Ortsbeschreibung, deren lexikalische Erkennung schon zuvor fehlte. Die Probe misst keine Fehlerrate eines echten Modells.

Die neue Statusdatei beschreibt bei R3 selbst „narrowed, not closed“ und erwähnt diesen Rest. Die Schlussbehauptung „alle sechs geschlossen“ sowie die Erklärung, kontrollierter Modus beantworte das Geheimnisproblem, sind damit zu pauschal. Diese Grenze betrifft **nicht ausschließlich** den ausdrücklich gewählten `provider`-Modus.

**Abnahme:** Entweder alle sichtbar freigegebenen Zeilen des garantierten Modus kontrolliert realisieren, einschließlich Begrüßungen und Ausweichantworten, oder den Vertrag ausdrücklich auf die intern geplanten Faktensätze beschränken. Für das Produktversprechen „Spieler und Welt erhalten dieselben Aussagen“ reicht diese Einschränkung allein noch nicht; siehe A3.

## A3 · P1 · Frühere Providerprosa verändert spätere Fakten über die Wiederholungssperre

**Fundstellen:** [sdk.py](../../../unscripted/sdk.py), `_deliver`, Zeilen
1108–1161; [validator.py](../../../unscripted/validator.py),
Wiederholungssperre; gemeinsamer Konversationsverlauf in
[runtime.py](../../../unscripted/runtime.py), `say`.

Gleicher Default-Modus, gleicher Seed, dieselben beiden öffentlichen SDK-Aufrufe:

```python
runtime.respond("agent:barkeep_12")
runtime.respond("agent:barkeep_12", topic="clinic")
```

Lediglich die Providerantwort beim ersten, nichtfaktisch geplanten Turn unterscheidet sich:

| Erste Providerantwort | Zweite veröffentlichte Antwort | Zweites Ergebnis |
| --- | --- | --- |
| `Evening.` | `Far as I know, the place was shut that night.` | `ACCEPT`, Klinik-Belief entsteht |
| `Far as I know, the place was shut that night.` | Derselbe Klinik-Satz | `REJECT_SOFT`, kein Klinik-Belief |

Der Provider wird in beiden Abläufen genau einmal aufgerufen. Die spätere Faktensprache ist vollständig kontrolliert. Trotzdem sperrt eine frühere Providerformulierung den verbindlichen Inhalt über `recent_lines` und `fallback_used`. Der SDK-Aufruf liefert im zweiten Fall den abgewiesenen Text weiterhin im Antwortobjekt; ob ein Client ihn anzeigt, hängt von dessen Umgang mit dem Verdict ab.

**Abnahme:** Variation und Anti-Repetition dürfen nicht durch beliebige frühere Providerprosa entscheiden, ob ein späteres verbindliches Commitment stattfindet. Den kompletten Freigabepfad vereinheitlichen, nicht nur die Auswahl des schreibenden Realisierers. Mehrturn-Tests müssen semantische Fortsetzungen vergleichen, statt jeweils eine frische Welt pro Providerantwort zu verwenden.

## A4 · Designentscheidung mit Korrektheitsfolge · Die globale Quellenobergrenze ist aufgegeben

**Fundstellen:** [belief.py](../../../unscripted/belief.py),
`correlation_discount` ab Zeile 257 und `max_origin_contribution` ab Zeile 306;
[Status](../STATUS.md), „Still open“; stärkere Behauptung weiterhin in
[README.md](../../../README.md), Zeile 1421.

Die Implementierung hält keinen Digest zur Wiedererkennung aller früheren Ursprünge. Sobald jemals etwas vergessen wurde, behandelt sie jeden unbekannten Ursprung wie eine erste Wiederholung. Nach jeder Verdrängung beginnt für denselben Ursprung damit wieder eine neue Reihe bei ρ¹.

Der Test benutzt **insgesamt nur 513 Ursprünge**, davon einen informativen, einen neutralen angehefteten und 511 neutrale Füller. Die Füller haben κ=0,5 und tragen exakt keine Log-Evidenz bei. Dieselben Füller und dieselbe informative Aussage werden wiederholt; es braucht keine unbegrenzt neuen Quellen.

| Verdrängungszyklen | Überzeugung |
| --- | --- |
| Vorher | 0,950000 |
| 1 | 0,962272 |
| 2 | 0,971621 |
| 10 | 0,997238 |
| 20 | 0,999854 |

Pro Zyklus kommen korrekt 0,29444 hinzu. Über beliebig viele Zyklen ist diese Summe **unbeschränkt**. Die frühere Quellenobergrenze von 3,27160 Log-Evidenz wird überschritten; nach 20 Zyklen sind es 8,83332.

**Das widerlegt nicht die jetzt dokumentierte Obergrenze pro Zyklus.** Diese schwächere Grenze hält in der Probe. Es zeigt, dass „eine wiederholte Aussage wird niemals Beweis“ durch diese Reparatur nicht wiederhergestellt wurde. Die Richtung ist gegenüber der unmittelbaren Vorgängerversion vorsichtiger, gegenüber genauer Quellenzählung übergewichtet sie jedoch Wiederholungen und untergewichtet neue Quellen.

**Abnahme:** Den Produktvertrag entscheiden und überall gleich formulieren. Für die ursprüngliche globale Sättigung müssen Zählung bzw. Evidenzbudgets erhalten bleiben, beispielsweise in einem Archiv. Alternativ ab der Grenze konservativ keine weitere Evidenz ohne nachgewiesene Unabhängigkeit aufnehmen. Wenn die heutige Approximation bewusst bleibt, ihre langfristige Aufhärtung und die fehlende allgemeine Garantie offen benennen und im Zielspiel bewerten. Ein weiterer Test mit nur einem Verdrängungszyklus löst diese Frage nicht.

## A5 · P2 · Weltidentität ist optional; der Fallback errät sie weiterhin

**Fundstellen:** [snapshot.py](../../../unscripted/snapshot.py), Zeilen 386–409;
[world.py](../../../unscripted/world.py), Einlesen von `scenario.json:
world_id`.

Explizite, verschiedene `world_id` funktionieren. Die ausgelieferten Scenario-Dateien enthalten jedoch noch keine solche ID. Ohne IDs akzeptiert der Fallback jetzt einen gemeinsamen Nicht-Spieler **oder zwei gemeinsame Orte**.

Zwei fremde Demo-Welten, jeweils nur im Speicher um `place:spawn` und `place:street` ergänzt, akzeptieren daher wieder denselben fremden Save. Der Noir-Zeitpunkt springt von **1200 auf 4334**. Beide IDs sind leer. Das ist ein synthetischer Test legitimer Namensüberschneidung, kein beobachteter Import zwischen unveränderten ausgelieferten Packs.

Die Schwelle wurde von einem auf zwei Ortsnamen verschoben. Zwei generische Namen sind ebenso wenig eine Identität wie einer.

**Abnahme:** Neue produktive Packs erhalten verpflichtende stabile IDs, und neue Saves ohne passende Identität werden nicht heuristisch zugeordnet. Für alte Saves ausdrücklich erlaubte Migrationen bzw. Herkunftsnachweise definieren. Der normale Produktionspfad und ein Kompatibilitätspfad für Altstände brauchen getrennte Regeln.

## Verifikation und verbleibender Umfang

- **37 vorhandene Testfunktionen erneut ausgeführt:** alle 30 Review-Regressionsfunktionen beider Pässe, Showcase und sechs einschlägige weitere Tests. 36 bestanden im Sandbox-Lauf; ausschließlich der lokale HTTP-Test scheiterte dort am gesperrten Port. Die genehmigte Wiederholung außerhalb der Sandbox bestand mit `ok service: the demo page is behind the same token it embeds`. Damit bestanden alle 37 ausgewählten Funktionen in den dokumentierten Abschnitten. [Protokoll](targeted-tests.log), [exakte Auswahl](selected-tests.json).
- Der vorhandene **Python/C++-Vergleich** einschließlich Engine-Szenarien und Konformanzfixtures bestand. Die unabhängigen neuen Gegenbeispiele wurden auf Python ausgeführt; ich behaupte keine zusätzliche vollständige Nachprüfung jedes C++-Pfades.
- **193 Funktionen sind registriert.** Ein vollständiger neuer Lauf aller 193 wurde in dieser Nachprüfung nicht ausgeführt. Die vollständige grüne Suite ist eine vom Projekt berichtete Messung; die heutige Nachprüfung bestätigt die 37 ausgewählten Funktionen.
- Die alten R1–R4-Einzelprobes bestehen unter dem neuen Standard. Die beiden weiteren alten Probes benötigen die neue Snapshot-API bzw. Fehlerbehandlung. Ihre API-Ausnahmen wurden nicht als Produktfehler gezählt. [Rohdaten](previous-probes.json).
- **Versiegelte Langzeitmessung:** Gegenüber `36bf7097` unterscheiden sich vier der zehn im Evidenzdokument benannten Python-Module: `belief`, `memory`, `runtime`, `revision`. `dialogue` und `commitment` sind entgegen der zitierten Zusammenfassung unverändert. Ein neuer zweistündiger Lauf fand hier nicht statt. Er sollte den anschließend reparierten, festgelegten Release-Stand messen.
- `main` enthält die zwei Reparatur-Commits lokal noch nicht. Merge und Veröffentlichung wurden nicht ausgeführt. Der Remote-Stand wurde nicht neu abgefragt; daraus folgt keine Aussage über zwischenzeitliche externe Pushes.
- Keine Pack-Dateien, bestehende Tests oder Produktdateien wurden geändert. Nur diese Nachprüfungsartefakte wurden hinzugefügt.

## Konkreter nächster Schritt

**Zuerst die tatsächliche Semantik der gesamten sichtbaren Ausgabe absichern:** Realisierung je ausgewähltem Move, inhaltserhaltende Stilvarianten, kontrollierte Ausgaben auch für nichtfaktische Pläne und ein Freigabeergebnis, dessen semantische Moves nicht durch eine frühere Providerzeile entfallen. Die vier Sprach-Gegenbeispiele hier bilden dafür konkrete Abnahmekriterien.

Danach die Quellenregel und die verpflichtende Weltidentität abschließen. Erst auf diesem Stand die vollständige Suite, die Zielengine und aktualisierte Langzeitmessungen als Release-Nachweis zusammenführen. Der Einsatz als betreuter Pilot bleibt ein sinnvoller nächster Produktmeilenstein; ein grüner Zähler und ein Merge allein sind keine Produktionsfreigabe.

```bash
python3 reviews/2026-09-08/fd76623/check.py
```

Beim geprüften Commit: sechs `invariant_holds: false`, zwei `true`, keine `probe_error`, Exitcode 1. Die Retentionsprobe prüft ausdrücklich die ursprüngliche globale Garantie; ihr Ergebnis ist von einer Verletzung der inzwischen schwächeren Zyklusgarantie zu unterscheiden.
