# Nachprüfung und Weg zur Produktionsversion

**8. September 2026, geprüfter Commit `56d77bf`, Runtime 1.18.0.**

**Viele konkrete Fehler wurden repariert. „Alle Befunde geschlossen“ und „produktionsreif“ sind jedoch noch nicht belastbar.** Sechs Gegenbeispiele zeigen verbleibende Lücken in zentralen Produktversprechen. Das ist kein vollständiges neues Review aller Module; es ist eine unabhängige Nachprüfung des Reparatur-Commits mit Schwerpunkt auf den früheren Fehlerklassen.

## Was tatsächlich weiter ist

Der Arbeitsbaum war zu Beginn sauber. Der vom Nutzer zitierte Arbeitsbericht endet vor dem aktuellen Stand: Die Suite umfasst inzwischen **188 Testfunktionen**, darunter 25 neue Review-Tests. Der Commit enthält Änderungen in Python und C++.

- **N1:** Der SDK-Abruf verwendet jetzt einen reproduzierbaren Zufallszug. `noise_s` beeinflusst damit die Auswahl. Beim direkten Aufruf des Memory-Moduls ohne `seed_parts` bleibt absichtlich die alte Schwellenentscheidung erhalten.
- **N2:** SDK und `Runtime.say()` teilen den Emissionspfad `Runtime.speak_aloud`. Die Providerfehlerbehandlung bleibt allerdings problematisch, siehe R2.
- **N3:** Die Vorzeichenkonvention des PAD-Mappings wurde kommentiert und durch einen Test festgehalten. Das ist keine neue empirische Validierung des Persönlichkeitsmodells.
- Die unauthentifizierte Token-Auslieferung ist im realen HTTP-Test geschlossen.
- Die ursprünglichen Gegenbeispiele zu wiederholten Lügen, wiederholter Standing-Bestrafung, Historienkürzung bei einer Quelle, Evidenzvorzeichen, interpretiertem Gedächtnis, Zeugen bei Zeitsprüngen, beschädigtem Import, Judgement-Serialisierung, Öffentlichkeitspolarität und bestätigter Angst sind korrigiert.
- Das ursprüngliche falsche ToM-Lesen wurde durch ein eigenes Modell ersetzt. Der ursprüngliche fremde Save ohne gemeinsame Orte wird abgewiesen. Der native JSON-Parser besteht die neuen Regressionen.
- Das Paketmanifest enthält jetzt auch die neue Spezifikation; der damalige Paketfehler besteht nicht mehr.

Diese Aussagen beziehen sich auf die nachgeprüften Fälle. Sie sind keine pauschale Bestätigung aller Kombinationen und Langzeitbedingungen. Insbesondere begrenzen neue Herkunftslimits die Revision; eine vollständige Rücknahme sozialer Konsequenzen nach jeder Form der Widerlegung wurde hier nicht zusätzlich nachgewiesen.

## Noch reproduzierbare Befunde

Die Programme verwenden feste Providerantworten, keine echten Modellaufrufe. Sie zeigen mögliche Vertragsverletzungen und keine statistische Fehlerrate eines Modells. [Prüfprogramm](recheck.py), [vollständige Ergebnisse](results.json).

### R1 — P1 — Negationswörter sichern keine Aussagegleichheit

**Bezug:** F03. [grounding.py](../../unscripted/grounding.py), `_denies` ab
Zeile 186 und `expresses` ab Zeile 210.

Alle drei Antworten erreichen den Spieler unverändert mit `ACCEPT`:

```text
The clinic was open all night, no doubt.
The clinic was not closed last night.
Nobody doubts the clinic was open all night.
```

Bei jeder wird gleichzeitig `NOT clinic_open(place=place:clinic, when=last_night)` verbreitet. Die Wörter `no`, `not` und `nobody` negieren hier entweder eine andere Aussage oder das Gegenteil des gemeinten Prädikats. Ihre bloße Anwesenheit sagt nichts über die Polarität der Klinikbehauptung aus.

Die neuen Tests vergleichen selbst wieder Negationswörter. Deshalb kann ihre erfolgreiche Ausführung diese Fehlerklasse nicht ausschließen. Der Kommentar, eine falsche Lesart koste lediglich die Providerformulierung, trifft nicht zu: Die falsche Formulierung wird veröffentlicht.

**Abnahme:** Der freigegebene Text muss Prädikat, Argumente, Zeitbezug und Polarität des verbindlichen Inhalts tragen. Für einen garantierten ersten Produktionsmodus kontrollierte, geprüfte Satzmuster verwenden. Freie Providertexte nur mit einem ausdrücklich schwächeren Vertrag anbieten. Kein weiteres Wortlisten-Patch als Abschluss dieses Befundes werten.

### R2 — P1 — Providerfehler verändern weiter den semantischen Weltzustand

**Bezug:** F22 und N2. [sdk.py](../../unscripted/sdk.py), Zeilen 1103–1162;
vergleichbare Verzweigung in [runtime.py](../../unscripted/runtime.py), `say`.

Gleiche Welt und gleiche Frage:

| Provider | Veröffentlichte Antwort | Gesprochene Events / Spielerwissen |
| --- | --- | --- |
| Liefert passenden Text | `The clinic was not open last night.` | Negative Klinikbehauptung entsteht |
| Wirft `ProviderError` | `Far as I know, the place was shut that night.` | Keine Behauptung, kein Spieler-Belief |

Beide Antworten werden akzeptiert und drücken dieselbe relevante Aussage aus. Trotzdem unterdrückt `fallback_used` im Fehlerfall die Kommunikation. Außerdem fragt `_carried` hier den ursprünglichen Provider statt des tatsächlich verwendeten Fallback-Realisierers ab. Die Korrektur der ausweichenden, aber erfolgreich gelieferten Antwort deckt diesen Pfad nicht ab.

**Abnahme:** Ein gemeinsames Freigabeergebnis trägt Text und verbindliche semantische Moves. Provider-Erfolg, Timeout, abgewiesene Ausgabe und deterministischer Ersatz führen bei realisierbarem Commitment zu derselben semantischen Fortsetzung. Für deterministisch unformulierbare Inhalte muss der Fehler vor der Veröffentlichung eindeutig behandelt werden. Diese Eigenschaften über beide öffentlichen Sprachpfade prüfen.

### R3 — P1 für Geheimhaltungsversprechen — Eine Ortsumschreibung passiert weiter

**Bezug:** F02. [validator.py](../../unscripted/validator.py), Layer 3a′ ab etwa
Zeile 145.

Mit dem expliziten Wort `room` erkennt die neue Prüfung das geschützte Objekt. Ohne dieses Wort wird folgende Antwort auf die Frage nach Milan unverändert veröffentlicht:

```text
Milan went outside the city. Now he hides behind where drinks are served.
```

Die zweite Aussage gibt weiterhin einen Orts-Hinweis auf das geschützte Versteck hinter dem Ausschank. Gleichzeitig wird nur die Behauptung über den Aufenthalt außerhalb der Stadt verbreitet. Die neue Prüfung erweitert also den lexikalischen Schutz, stellt aber keine semantische Geheimhaltung her. Das benennt der Kommentar selbst bereits richtig; die pauschale Schließung im Review-Status geht weiter als dieser Schutzumfang.

**Abnahme:** Im garantierten Modus nur freigegebene Aussagen und geprüfte Realisierungen veröffentlichen. Bei freiem Text auch indirekte Ortsbeschreibungen, Pronomen und zusätzliche Sätze prüfen; deren Restrisiko ausdrücklich von einer harten Garantie unterscheiden. Bereits die ursprünglichen Gegenbeispiele zeigen, dass der Provider bekannte Geheimnisse umschreiben kann.

### R4 — P1 für unbegrenzte Korrelationsgarantie — Verdrängte Ursprünge zählen wieder voll

**Bezug:** F18 in Wechselwirkung mit F04/F06.
[belief.py](../../unscripted/belief.py), `_remember` ab Zeile 97,
`record_provenance` und `correlation_discount` ab Zeile 255.

Der neue Index bleibt bei 512 Ursprüngen begrenzt. Wird ein anderer als der erste Ursprung verdrängt, ist seine frühere Zählung weg. Eine spätere Wiederholung erhält wieder Gewicht 1.

Der Gegenbeweis verwendet die Standardgrenze und neutrale Zwischenberichte: Die erste relevante Aussage trägt **2,94444** Log-Evidenz bei. Nach Verdrängung trägt ihre bloße Wiederholung erneut **2,94444** bei. Ihre Gesamtevidenz **5,88888** überschreitet die ausgewiesene Obergrenze **3,27160**. Die Überzeugung steigt allein durch die Wiederholung von **0,95 auf 0,99724**.

**Abnahme:** Eine verbindliche Retentionsregel wählen. Bei genauer, langfristiger Herkunftserkennung braucht es ein erhaltenes Register bzw. Archiv. Bei begrenzter Erinnerung dürfen vergessene Quellen nicht automatisch als nachweislich neue unabhängige Evidenz gelten. Ein endliches Register, unbegrenzt viele Ursprünge und unbegrenzt genaue Wiedererkennung sind nicht gleichzeitig zu haben. Die Grenze muss im Produktvertrag stehen; bloß den Speicherindex zu begrenzen schließt die ursprüngliche Designfrage nicht.

### R5 — P2 — Die Historie eines alten Snapshots enthält später eine andere Zukunft

**Bezug:** F13. [persistence.py](../../unscripted/persistence.py),
`ledger_up_to` ab Zeile 262; [snapshot.py](../../unscripted/snapshot.py),
`event_id_watermark` in `capture`.

Die eigenen SQL-Zeilen-IDs verhindern jetzt das Überschreiben: Das ist repariert. Die Snapshot-Abfrage filtert aber weiter nach der zurücksetzbaren `event_id`.

Ein gespeicherter Stand A liefert zuerst nur Ereignis A. Nach Laden eines früheren Standes und Erzeugen von Ereignis B mit derselben Simulations-ID liefert **dieselbe Abfrage für denselben alten Snapshot A nun A und B**. Die Weltzustandskopie wurde in diesem Test nicht beschädigt; falsch ist die zugesagte Historie „as of a snapshot“.

**Abnahme:** Für einen unveränderlichen Audit-Ausschnitt eine nicht zurücksetzbare Ledger-Wasserlinie speichern. Für die Rekonstruktion eines bestimmten Spielverlaufs zusätzlich Zweigidentität und Abstammung festlegen. Globales Audit und Replay eines Spielverlaufs haben unterschiedliche Abfragebedingungen.

### R6 — P1 für Save-Kompatibilität — Ein gemeinsamer Ortsname ersetzt keine Weltidentität

**Bezug:** F11. [snapshot.py](../../unscripted/snapshot.py), `inspect_state`,
Zeilen 371–387.

Die neue Prüfung verlangt lediglich mindestens einen gemeinsamen Ort. Im Gegenbeispiel bekommen die zwei unabhängigen, nur im Speicher angepassten Demo-Welten denselben generischen Eintrag `place:spawn`. Der Cyberpunk-Save wird daraufhin als `world_changed` in Noir akzeptiert; dessen Uhr springt von **1200 auf 4457**. Gemeinsam ist außerdem der Standard-Spieler. Die Worldpack-Dateien bleiben unverändert.

**Abnahme:** Eine stabile Welt-/Produktidentität getrennt von Inhaltsrevision und Layout-Fingerprint speichern. Neue Inhalte derselben Welt können über erklärte Migrationen kompatibel bleiben; eine andere Welt wird unabhängig von zufällig gemeinsamen IDs abgewiesen.

## Was die Testzahlen bedeuten

Heute wurden **32 ausgewählte Testfunktionen** erneut ausgeführt: alle 25 neuen Review-Tests, der Showcase und sechs relevante bestehende Prüfungen einschließlich vollständigem Python/C++-Vergleich. **31 bestanden innerhalb der Sandbox.** Der HTTP-Test scheiterte dort ausschließlich am gesperrten lokalen Port und bestand bei der genehmigten Wiederholung außerhalb der Sandbox:

```text
ok  service: the demo page is behind the same token it embeds
```

Somit bestanden alle 32 ausgewählten Funktionen, aber nicht in einem einzigen ununterbrochenen Lauf. [Laufprotokoll](targeted-tests.log). Die komplette aktuelle Suite mit 188 Funktionen wurde in dieser Nachprüfung **nicht** neu ausgeführt. Der im README genannte Gesamtlauf ist eine vorhandene Projektangabe und kein von dieser Nachprüfung neu erzeugter Nachweis.

Die 19 alten Python-Probes wurden ebenfalls erneut ausgeführt: [Rohdaten](original-probes-rerun.json). Manche ihrer Erfolgskriterien passen nicht mehr zum reparierten Verhalten: Eine sicher ersetzte Antwort darf `ACCEPT` heißen, ein fremder Save darf mit einem typisierten Fehler scheitern, und ein neues ToM-Modell darf ohne eigene Beobachtung neutral bleiben. Diese Roh-Flags wurden nicht pauschal als weiterbestehende Fehler gezählt. Die sechs oben aufgeführten Befunde haben eigene Gegenbeispiele für die aktuelle Implementierung.

Keine neue zweistündige Lastmessung, keine komplette Zielplattformmatrix, keine neuen interaktiven Engine-Spieltests, keine Wettbewerbsintegration oder Kundenvalidierung. Produktcode, bestehende Tests und der historische Review-Status wurden nicht geändert.

## Empfohlener Weg zur Produktionsversion

Die nächste Etappe ist eine **begrenzte, belastbare Pilotversion**. Weitere psychologische Ebenen oder zusätzliche Engine-Integrationen erhöhen derzeit vor allem die zu prüfende Fläche.

| Reihenfolge | Arbeit | Nachweis, bevor es weitergeht |
| --- | --- | --- |
| 1. Vertrag und Korrektheit | R1–R3 durch kontrollierte Realisierung und gemeinsamen Freigabe-/Fehlerpfad schließen; R4–R6 durch erklärte Herkunftsretention, stabile Weltidentität und richtige Historienabfragen schließen. | Neue Gegenbeispiele sind grün. Zusätzliche Tests prüfen die Eigenschaften unabhängig von der implementierten Wortliste. Die vollständige Suite und Portvergleiche bestehen auf dem Reparatur-Commit. |
| 2. Enger Release-Kandidat | Eine Zielengine und eine konkrete PC-Plattform auswählen. Unterstützten Cast, Ereignisvolumen, Inhalte, Sprachmodus, Save-Migration und Verhalten bei Überlast festlegen. | Sauber installiertes Release-Artefakt läuft in einem kleinen echten Spiel einschließlich Start, Interaktion, Speichern, Prozessneustart und Laden. |
| 3. Belastung und Nachvollziehbarkeit | Dauerhaft neue Vorfälle/Ursprünge, mehrere Spielverläufe, Save/Load-Schleifen, kaputte Eingaben und alle tatsächlich angebotenen Features testen. | P50/P95/P99, Spitzenzeiten, Speicher-, Ledger- und Save-Wachstum bleiben im vereinbarten Budget. Ein Fehler lässt sich aus Version, Seed und autoritativen Eingaben reproduzieren. |
| 4. Fremdes Team integriert | Ein 15–20-minütiger Ermittlungsfall mit etwa 6–12 relevanten Figuren: Gerücht, Quellenprüfung, Entlarvung und sichtbare Konsequenz. | Ein fremdes Team integriert und ändert die Szene; Integrationszeit, Autorenprobleme und Spieler-Nachvollziehbarkeit werden dokumentiert. |
| 5. Bezahlter Pilot, dann breitere Freigabe | Wenige passende Studios mit diesem konkreten Spielnutzen ansprechen. Pilotumfang, Unterstützung und Lizenz schriftlich begrenzen. | Mindestens eine erfolgreiche Kundenintegration und belastbare Zahlungsbereitschaft. Erst daraus Supportmatrix, öffentliche Pakete und breiteren Vertrieb ableiten. |

Die Zahlen für Szene und Cast sind Planungsannahmen, keine gemessenen Kapazitätsgrenzen. Für erste Frame-Budgets die bereits vorhandenen Werkzeuge `tools/frame_bench.py` und `tools/scale_bench.py` verwenden und um dauerhaft wachsende Inhalte ergänzen. Keine pauschale Millisekunden- oder Speichergrenze ohne Zielhardware und vereinbarte Spielanforderungen versprechen.

Ein vollständiger Evidenzgraph über mehrere unabhängige Quellen, empirische Kalibrierung von `kappa`, umfassendes Common Knowledge oder weitere ToM-Tiefe müssen eine erste klar begrenzte Spielversion nicht blockieren. Die vereinfachte Bedeutung muss jedoch im Angebot stimmen. Dagegen können gegensätzlicher Text und Weltzustand, falsche Save-Zuordnung oder unverlässliche Revision genau den narrativen Kern beschädigen, der verkauft werden soll.

**Nächster konkreter Arbeitsauftrag:** zuerst den gemeinsamen Sprach-Freigabepfad samt kontrolliertem Realisierer abschließen, danach Herkunftsretention und Save-/Ledger-Verträge härten. Anschließend einen Release-Kandidaten gegen die oben definierten Gates prüfen. Eine weitere bloße Erhöhung der Testanzahl ist kein eigenes Abnahmekriterium.

## Reproduzieren

```bash
python3 reviews/2026-09-08/recheck.py
```

Beim untersuchten Commit liefert das Programm sechs `invariant_holds: false` und Exitcode 1, ohne `probe_error`. Es verwendet nur temporäre Welten und In-Memory-Speicher. Nach Reparaturen sollen die Invarianten bestehen; das Programm ist kein absichtlich auf den Fehler festgelegtes Golden File.
