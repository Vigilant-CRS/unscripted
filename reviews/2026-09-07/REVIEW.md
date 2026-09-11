# Unscripted: Code-, Theorie- und Produktreview

Stand: **7. September 2026**, Commit `f8dba3936240ce5b4493d9c259bc224acb3651ac`, Runtime **1.18.0**.

**Das Projekt verfolgt einen tragfähigen Ansatz. Die zentrale Produktidee ist stärker als einige ihrer heutigen Garantien.** Eine explizite Simulation von Zeugenaussagen, Gerüchten und sozialen Konsequenzen kann Studios Arbeit abnehmen und interessante Spielmechaniken ermöglichen. Die aktuelle Implementierung hat jedoch Fehler genau in diesem Kern: Geheimnisse können durch Umschreibungen veröffentlicht werden, Aussage und simulierter Inhalt auseinanderlaufen, wiederholte Lügen neue Quellen erzeugen und Savegames die falsche Welt überschreiben.

Meine Einordnung: fortgeschrittener SDK-Prototyp mit brauchbarer Grundlage für betreute Pilotprojekte nach Behebung der kritischen Fehler. **Für eine allgemeine Produktionsfreigabe reicht der vorliegende Stand nicht. Eine Überlegenheit gegenüber dem Markt ist nicht nachgewiesen.**

## Umfang und Beweislage

Das Repository umfasst 78 Python-Dateien in `unscripted/` mit 24.613 Zeilen
sowie 63 C++-Header mit 18.837 Zeilen; Kommentare und Leerzeilen sind
mitgezählt. Dies ist ein vertieftes, risikoorientiertes Review der zentralen
Pfade, keine Behauptung, jede Zeile aller Integrationen und historischen
Theoriedokumente vollständig geprüft zu haben.

Im Schwerpunkt gelesen wurden Belief/Revision, Wahrnehmung/Interpretation, Memory, Diffusion/Routinen, Standing/ToM/Affect/Policy, Commitment/Validator/Grounding, SDK/Runtime, Snapshot/Persistence, HTTP-Service, C-ABI/JSON und Teile der Engine-Bindings. Dazu aktuelle Konzept-, Architektur-, Kalibrierungs- und Evidenzdokumente sowie relevante Abschnitte der v0.9- und CONCEPT_V2-Spezifikation. Historische Anforderungen werden nicht automatisch als bereits implementierte Features behandelt.

**Unabhängige Gegenprüfung:** 19 Python-Prüffälle, ein realer HTTP-Test mit erfundenem Token und zwei C++-JSON-Befunde. Alle Details stehen in [probes.json](probes.json), [http.json](http.json) und [cpp-json.txt](cpp-json.txt). Die 22 Befunde unten schließen eine bewusst dokumentierte, aber produktrelevante Wachstumsgrenze ein; nicht alle sind voneinander unabhängige Ursachen.

Die Python-Prüfprogramme ersetzen einen Textprovider durch fest vorgegebene Antworten. Damit prüfen sie die garantierte Vertrauensgrenze reproduzierbar. Sie messen **keine Häufigkeit**, mit der ein bestimmtes Sprachmodell solche Antworten erzeugt. Produktcode und Worldpacks wurden für dieses Review nicht geändert.

Alle 163 vorhandenen Testfunktionen wurden erfolgreich ausgeführt, verteilt auf zwei Abschnitte. Der erste Versuch scheiterte innerhalb der Sandbox am lokalen Testserver. Der Lauf mit Dienstrechten absolvierte die ersten 119 Tests einschließlich des echten Unreal-Plugin-Builds. Anschließend beanstandete der Pakettest die zunächst unter `docs/reviews/` abgelegten Review-Dateien. Das war eine durch das Review verursachte Dateiplatzierung, **kein Produktfehler**. Die Dateien wurden nach `reviews/2026-09-07/` verschoben; ab Test 120 bestanden alle 44 verbleibenden Tests. Währenddessen erschien im gemeinsamen Arbeitsverzeichnis eine weitere, nicht von diesem Review erstellte `docs/SPECIFICATION.md`. Der abschließende Pakettest beanstandet nun diese unregistrierte Datei; der aktuelle Arbeitsstand ist damit nicht vollständig grün. Ablauf und Protokolle stehen in [VALIDATION.md](VALIDATION.md).

Die bestehenden Langzeitmessungen wurden nicht erneut zwei Stunden ausgeführt. Ihre Versiegelung wurde anhand der zehn in `evidence/README.md` benannten Kernmodule kontrolliert: Alle zehn Dateiinhalte stimmen mit Commit `36bf7097` überein. Das spricht für die Nachprüfbarkeit der veröffentlichten Messung. Es erweitert nicht den Umfang ihrer Prüfkriterien.

## Priorisierte Befunde

**P1:** vor produktivem Einsatz des betroffenen Pfades beheben. **P2:** reproduzierbarer Korrektheitsfehler mit engerem Auslöser. **D:** bestätigte Designgrenze. Keine dieser Einstufungen behauptet eine bereits beobachtete Ausnutzung bei Kunden.

### F01 · P1 · Die Demo liefert das Authentifizierungstoken ohne Anmeldung aus

**Fundstelle:** [service.py](../../unscripted/service.py), `Handler.do_GET`,
Zeilen 630–647; [webdemo.py](../../unscripted/webdemo.py), `demo_html`; analog
`studio_html`.

Die HTML-Routen umgehen `_dispatch` und damit `authorize`. Gleichzeitig setzt der Server das konfigurierte Bearer-Token in die HTML-Seite ein. Mit den Standardoptionen für Debug-Endpunkte ergibt der reale Loopback-Test: `/capabilities` ohne Token → **401**, `/demo` ohne Token → **200 mit Token**, `/advance` mit dem daraus gewonnenen Token → **200**.

Das betrifft einen authentifizierten Dienst mit erreichbarer Demo. Bei deaktivierten Debug-Endpunkten ist diese Demo-Route gesperrt; ein öffentliches Netz wurde nicht getestet. Dieselbe Routinglogik wird aber auch bei einem erlaubten externen Bind verwendet.

**Reparatur:** Kein Servergeheimnis in eine unauthentifiziert gelieferte Seite einbetten. UI-Anmeldung und API-Zugriff explizit absichern, alle relevanten Routen durch dieselbe Authentifizierung führen. Der Test muss den kompletten Ablauf über HTTP prüfen, nicht nur `authorize` isoliert. Probe: `http_token_disclosure`.

### F02 · P1 · Eine einfache Umschreibung verrät das geschützte Versteck

**Fundstelle:** [validator.py](../../unscripted/validator.py), Zeilen 112–117
und 153–210; [grounding.py](../../unscripted/grounding.py), `unknown_referents`.

Okadas geschütztes Geheimnis lautet im gelieferten Pack, dass Milan im Hinterzimmer hinter der Bar versteckt ist. Der vorgegebene Providertext **„Milan hides in a room behind the bar.“** wird auf `ask Mr. Okada about milan` unverändert mit **ACCEPT** veröffentlicht. Er enthält keinen der verbotenen zusammenhängenden Ausdrücke wie `back room` oder `milan is`.

Hier fehlen keine exotischen Jailbreaks. Die Kombination aus bekannten Namen, gewöhnlichen Substantiven und anderer Satzkonstruktion reicht. Wortlisten schützen deklarierte Oberflächenformen; sie beweisen keine semantische Geheimhaltung.

**Reparatur:** Für kritische Inhalte kontrollierte, geprüfte Satzrealisierung aus typisierten Aussagen. Freie Formulierungen als zusätzlich geprüften, begrenzten Modus anbieten; dessen Schutzumfang präzise benennen. Eine weitere Synonymliste oder ein zweites LLM ist allein keine harte Garantie. Probe: `paraphrased_secret`.

### F03 · P1 · Gesprochener Satz und propagierte Aussage können Gegenteile sein

**Fundstelle:** [grounding.py](../../unscripted/grounding.py), `expresses`,
Zeilen 174–187; [sdk.py](../../unscripted/sdk.py), `_deliver`, Zeilen 1114–1139.

Auf `ask Honce about clinic` wird **„The clinic was open all night.“** akzeptiert. Der ausgelöste Kommunikationsinhalt lautet gleichzeitig **`NOT clinic_open(place=place:clinic, when=last_night)`**. Der Spieler liest „offen“, die Zuhörer lernen „geschlossen“.

`expresses` verlangt nur irgendeinen Anker aus irgendeinem Slot. Prädikat, Negation, Rollenverteilung und Zeitbezug werden nicht geprüft. Deshalb besteht auch ein inhaltlich gegenteiliger Satz die Kontrolle.

**Reparatur:** Ein verbindlicher Semantikvertrag muss dieselbe Aussage in Text und Event sichern. Für den ersten produktiven Modus bietet sich ein kontrollierter Realisierer an, bei dem jeder freigegebene Satz eine überprüfte Zuordnung zu Prädikat, Slots und Polarität hat. Probe: `contradictory_provider`.

### F04 · P1 · Wiederholte Lügen erzeugen immer neue vermeintlich unabhängige Ursprünge

**Fundstelle:** [sdk.py](../../unscripted/sdk.py), `_spoken_origin`, Zeilen
1333–1356.

Ehrliche Antworten übernehmen einen vorhandenen Ursprung. Lügen erhalten dagegen `said_<agent>_<world_time>`. Derselbe Lügner wird somit in jeder neuen Minute zu einer neuen Evidenzquelle für dieselbe Behauptung.

Der Test lässt Okada achtmal dieselbe örtliche Behauptung in vier verschiedenen korrekten Formulierungen wiederholen. Die Wiederholungssperre bleibt aktiv. Ergebnis: **acht Ursprünge**, Wahrscheinlichkeit beim Spieler von **0,513 auf 0,612**. Die geometrische Dämpfung greift nicht über diese Ursprünge hinweg.

Dass die zweite Äußerung ein neues Gesprächsereignis ist, macht sie nicht zu einer unabhängigen Beobachtung des behaupteten Sachverhalts.

**Reparatur:** Kommunikationsereignis-ID, Ursprung einer Behauptung und unabhängiger Evidenzursprung trennen. Erfundene Behauptungen benötigen einen stabilen Ursprung pro Quelle/Sachverhalt; erneute Aussagen dürfen nur durch tatsächlich neue Evidenz unabhängig werden. Probe: `repeated_lie_origins`.

### F05 · P1 · Wiederholtes Gerücht bestraft die beschuldigte Person immer wieder

**Fundstelle:** [runtime.py](../../unscripted/runtime.py), Zeilen 286–300;
[standing.py](../../unscripted/standing.py), `judge`, Zeilen 186–206.

Nach jedem aufgenommenen Bericht wird die gesamte aktuelle Überzeugung erneut in soziale Deltas übersetzt. Ein bereits gezähltes Ereignis wird dadurch wiederholt bestraft, obwohl die zusätzliche Evidenz fast null ist.

Für zwanzig Berichte über **denselben Ursprung**: Nach dem sechsten Bericht liegt die Wahrscheinlichkeit bei **0,54960677**, nach dem zwanzigsten bei **0,54960683**. Dennoch sinkt das Mögen von **−0,198 auf −0,659**. Korrekte Dämpfung im Belief-Modul verhindert den Effekt in Standing nicht.

**Reparatur:** Soziale Konsequenzen pro Beobachter und Vorfall ableiten und nur die Änderung gegenüber dem bereits verbuchten Zustand anwenden. Widerlegung muss diese Konsequenz ebenfalls neu bewerten. Einen gewünschten Wiederholungseffekt als eigenen, begrenzten Mechanismus modellieren. Probe: `standing_repeats`.

### F06 · P1 · Nach Historienkürzung kann ein entlarvter Lügner nicht mehr wirksam revidiert werden

**Fundstelle:** [belief.py](../../unscripted/belief.py), `record_provenance`,
Zeilen 62–90; [revision.py](../../unscripted/revision.py), Zeilen 85–101.

Die Belief-Summe enthält alle früheren Beiträge. Die Revision findet Beiträge jedoch nur in den letzten 64 Provenanzeinträgen. Nach 100 Wiederholungen eines Ursprungs sind die gewichtigen ersten Einträge entfernt. Die verbleibenden extrem kleinen Beiträge wurden zudem auf sechs Dezimalstellen zu null gerundet.

Der Test disqualifiziert die einzige Quelle auf Faktor 0,1: **0,96344 vorher, 0,96344 nachher, null revidierte Beliefs**. Die Garantie rückwirkender Neubewertung fällt gerade bei langlebigen Behauptungen aus.

**Reparatur:** Für die Rechnung verlustfreie kumulierte Beiträge pro Quelle/Ursprung aufbewahren; die gekürzte Erklärungshistorie davon trennen. Rundung gehört in die Anzeige. Probe: `revision_retention`.

### F07 · P2 · Quellenentwertung erzeugt fälschlich Gegenbeweise

**Fundstelle:** [revision.py](../../unscripted/revision.py), Zeilen 95–101.

Eine Entwertung positiver Evidenz wird zu `support_against` addiert, statt `support_for` zu vermindern. Der Test beginnt mit einer einzigen positiven Quelle und Konflikt 0. Nach ihrer Entwertung meldet das System **Konflikt 0,947**, obwohl keine negative Aussage hinzugekommen ist.

„Die Begründung ist schwächer“ und „es gibt einen Gegenbeweis“ sind epistemisch verschiedene Zustände. Die aktuelle Rechnung verwechselt sie.

**Reparatur:** Positive und negative Summen aus den revidierten, signierten Beiträgen neu berechnen oder korrekt subtrahieren. Ignoranz soll durch Evidenzverlust steigen können. Probe: `revision_dual_evidence`.

### F08 · P2 · Unterhalb von κ = 0,5 stimmt die Richtung der Evidenzsummen nicht

**Fundstelle:** [belief.py](../../unscripted/belief.py), Zeilen 212–220.

Bei erlaubten Werten `trust=0`, `competence=0`, `skepticism=1` ergibt sich κ = 0,25. Eine positive Aussage senkt die Wahrscheinlichkeit auf **0,25**, erhöht aber ausschließlich `support_for` um **1,0986**. Log-Odds und erklärter Evidenzzustand widersprechen einander.

**Reparatur:** Das Vorzeichen von `sign * evidence` entscheidet über die Evidenzsumme. Zusätzlich fachlich entscheiden: Ist eine unzuverlässige Quelle tatsächlich ein systematischer Gegenindikator oder lediglich wenig informativ? Probe: `negative_evidence_sign`.

### F09 · P2 · Das Gedächtnis speichert Details, die die Wahrnehmung gerade verworfen hat

**Fundstelle:** [runtime.py](../../unscripted/runtime.py), Zeilen 191–213
gegenüber 332–342.

Für Adeyemi wird im Relay-Pack eine Beobachtung korrekt zu `seal_breached(section=place:store, when=None)` vergröbert. Anschließend speichert `remembered_prop = event.proposition` die ursprüngliche vollständige Aussage. Die öffentliche Methode `retrieve_memories` liefert wieder **`when=night_cycle`**.

Damit sind interpretierte Überzeugung und abrufbare episodische Information inkonsistent. Das ist noch kein Beleg, dass dieser Pfad automatisch einen NPC-Satz veröffentlicht; wohl aber ein belegtes Informationsleck in die Gedächtnis-API und spätere Konsolidierung.

**Reparatur:** Erinnerungen aus dem observer-spezifischen Wahrnehmungsergebnis erzeugen. Die vollständige Ereigniswahrheit bleibt ausschließlich im autoritativen Ledger. Fragen und nicht erkannte Inhalte als solche typisieren. Probe: `unrecognized_memory`.

### F10 · P1 · Große Zeitsprünge erzeugen falsche Zeugen

**Fundstelle:** [runtime.py](../../unscripted/runtime.py), `_advance`, Zeilen
640–669; [routine.py](../../unscripted/routine.py), `step`.

Fällige Ereignisse werden vor dem Nachführen der Routinen verarbeitet. Ein NPC soll bei Minute 10 von P nach Q gehen. Bei Minute 20 findet ein Vorfall in P statt. `advance_time(30)` macht ihn zum Zeugen; `advance_time(10)` gefolgt von `advance_time(20)` nicht. Beide Läufe enden bei Minute 30 in Q.

Nicht jede stochastische Detailstatistik muss bei frei gewählten Zeitschritten identisch bleiben. **Die Anwesenheit zum Zeitpunkt eines autoritativen Ereignisses muss jedoch korrekt sein.**

**Reparatur:** Kritische Ereignisse und relevante Ortswechsel chronologisch integrieren. Lange Leerlaufintervalle dürfen zusammengefasst werden; ihre Endposition darf nicht die Vergangenheit ersetzen. Probe: `scheduled_witnesses`.

### F11 · P1 · Ein Savegame aus einer anderen Welt wird geladen

**Fundstelle:** [snapshot.py](../../unscripted/snapshot.py), `inspect_state`,
Zeilen 333–346; `restore`, Zeilen 138–153.

Als Weltidentitätsprüfung genügt die Überschneidung eines einzigen Agenten. Die gelieferten Welten teilen `agent:player_1`. Ein Cyberpunk-Save wird daher in `noir-harbor` mit **`usable: true`** akzeptiert. Danach steht der Spieler in **`place:main_street`**, einem Ort, der in der Zielwelt nicht existiert. Auch Zeit, Terminliste und weitere Zustände können übernommen werden.

**Reparatur:** Stabile `world_id`/`pack_id` und eine explizite Migrationslinie einführen. Weltidentität von erlaubten Inhaltsänderungen trennen; Player-ID oder Cast-Überschneidung sind kein Identitätsnachweis. Alle referenzierten Orte und Entitäten vor Anwendung prüfen. Probe: `foreign_save`.

### F12 · P1 · Ein beschädigtes Savegame verändert die Welt vor dem Fehler

**Fundstelle:** [snapshot.py](../../unscripted/snapshot.py), `inspect_state`,
`import_state`, `restore` und `_apply_agent_state`.

Ein gültiger Umschlag mit beschädigtem Belief-Payload wird als benutzbar eingestuft. Beim Import wird zunächst die Weltzeit von **4334 auf 5334** gesetzt; anschließend tritt ein **KeyError** auf. Der Zustand ist danach teilweise verändert.

**Reparatur:** Payload vollständig validieren und in einen temporären Zustand deserialisieren. Erst nach erfolgreicher Prüfung atomar übernehmen. Ein fehlgeschlagener Import muss den vorherigen Zustand erhalten und einen definierten Importfehler liefern. Probe: `corrupt_save_atomicity`.

### F13 · P1 · Laden und Weiterspielen überschreibt die vermeintlich unveränderliche Ereignishistorie

**Fundstelle:** [persistence.py](../../unscripted/persistence.py), Zeile 65;
[snapshot.py](../../unscripted/snapshot.py), Zeile 139.

Restore setzt den Eventzähler zurück. Das Ledger schreibt mit `INSERT OR REPLACE` auf `event_id`. Nach Laden eines früheren Saves überschreibt ein neuer Vorfall daher einen Vorfall des aufgegebenen Verlaufs mit derselben ID.

Im Test wird **Event 1001, „branch A“**, durch **„branch B“** ersetzt; das Ledger enthält weiterhin nur eine Zeile. Damit ist es kein Append-only-Auditverlauf. Ältere Snapshots und die zugehörigen Erklärungen können auf unterschiedliche Historien mit denselben IDs zeigen.

**Reparatur:** Verlauf/Branch und lokale Ereignisnummer als zusammengesetzte Identität führen oder global eindeutige IDs verwenden. Deterministische Simulations-IDs von unveränderlichen Audit-IDs trennen. Probe: `ledger_branch_overwrite`.

### F14 · P2 · Save/Load verliert die Bedeutung und Quellen von Judgements

**Fundstelle:** [memory.py](../../unscripted/memory.py),
`Memory.as_dict`/`from_dict`, Zeilen 80–107;
[memory.hpp](../../port/cpp/include/usc/memory.hpp),
`as_json`/`from_json`.

`about` und `evidence` werden nicht serialisiert. Ein Judgement über `(agent:speaker, helped)` mit drei Evidenzverweisen wird nach dem Roundtrip zu **`about=(), evidence=()`**. Die spätere Konsolidierung findet das vorhandene Muster nicht mehr anhand von `about`.

Ein Vergleich `export → import → export` entdeckt den Fehler nicht, wenn beide Exporte dieselben Felder weglassen. Hier wurde deshalb der tatsächliche Objektzustand verglichen.

**Reparatur:** Felder in beiden Implementierungen verlustfrei serialisieren, alte Saves gezielt migrieren und Fortsetzungsverhalten nach dem Laden testen. Probe: `judgement_roundtrip`.

### F15 · P2 · Öffentliche Negation und öffentlich behauptete Tatsache werden gleichgesetzt

**Fundstelle:** [common_knowledge.py](../../unscripted/common_knowledge.py),
`observe`, Verwendung von `proposition.core_key()`;
[sdk.py](../../unscripted/sdk.py), `_keys_out`/`_secret_is_out`.

Die Publics-Tabelle lässt Polarität weg. Ein öffentlicher Bericht **„Person ist nicht am Leben“** markiert dadurch auch den Schlüssel von **„Person ist am Leben“** als öffentlich. Bei Geheimnissen kann dadurch die Frage „ist diese geschützte Aussage bereits veröffentlicht?“ falsch beantwortet werden; auch Diffusionsunterdrückung kann falsch greifen.

**Reparatur:** Öffentliche Äußerung einschließlich Polarität und Geltungsbereich speichern. Öffentlichkeit einer Debatte von Veröffentlichung ihres Inhalts unterscheiden. Probe: `publicity_polarity`.

### F16 · P2 · Ähnliche Agenten-IDs führen zur Revision der falschen Quelle

**Fundstelle:** [revision.py](../../unscripted/revision.py), `_traces_to`,
Zeilen 61–64; entsprechend
[revision.hpp](../../port/cpp/include/usc/revision.hpp).

`source in origin` ist eine Teilstringprüfung. Eine Diskreditierung von **`agent:ann`** entwertet auch die weitergereichte Aussage aus **`said_agent:anna_100`**. Im Test fällt deren Wahrscheinlichkeit von **0,95 auf 0,676**.

**Reparatur:** Ursprungsautor und Quellenverweise strukturiert speichern und IDs exakt vergleichen. Die Ereignis-ID ist ein opakes Identifikationsmerkmal und sollte nicht als Datenbank für Agentennamen dienen. Probe: `source_id_substring`.

### F17 · P2 · OCC: Bestätigte Angst erzeugt Erleichterung

**Fundstelle:** [affect.py](../../unscripted/affect.py), Zeilen 97–100.

`prospect='confirmed', prior_fear=0.8` ergibt **relief=0.8**. Bei `disconfirmed` kommt keine Erleichterung. Das ist gegenüber OCC vertauscht: Erleichterung folgt auf das Ausbleiben eines befürchteten Ereignisses, bestätigte Befürchtung auf dessen Eintritt. Das ist ein fachlicher Zuordnungsfehler, keine Geschmacksfrage beim Tuning. [OCC, Reactions to Events II](https://www.cambridge.org/core/books/abs/cognitive-structure-of-emotions/reactions-to-events-ii/83666E338C0687B473874DBBC7748C78).

**Reparatur:** Vier Fälle explizit modellieren: Hoffnung bestätigt/enttäuscht und Befürchtung bestätigt/ausgeräumt. Dazu semantische Referenztests statt ausschließlich Bereichsprüfungen. Probe: `occ_fear_confirmation`.

### F18 · D · Der gesamte Zustand ist nicht über beliebige Laufzeit begrenzt

**Fundstelle:** [belief.py](../../unscripted/belief.py), Zeilen 64–76;
[benchmark.py](../../unscripted/benchmark.py),
`_provenance_bounded`/`_snapshot_bounded`;
[dialogue.py](../../unscripted/dialogue.py), ungekürztes `last_acts.append`.

`origin_counts` wird absichtlich vollständig behalten. **2.000 unabhängige Ursprünge ergeben 2.000 Indexeinträge**, obwohl die sichtbare Provenanzliste auf 64 begrenzt ist. Auch die Menge unterschiedlicher Beliefs ist nicht allgemein zeitunabhängig begrenzt; zeitlich qualifizierte Aussagen können neue Schlüssel erzeugen. Die derzeitigen Benchmarks prüfen Ausschnitte und eine Größenobergrenze am Messpunkt, keinen mathematischen Langzeit-Bound.

Das ist ein bewusster Tradeoff, kein überraschender Python-Fehler: Exakte Wiedererkennung beliebiger alter Ursprünge braucht entsprechende Information. Man kann nicht zugleich unbegrenzt neue Ursprünge erlauben, alle für immer exakt erkennen und konstanten Speicher versprechen.

**Produktentscheidung:** Begrenzter aktiver Zustand plus Archiv, eine definierte Vergessensfrist oder eine dokumentierte Approximation. Wachstum pro neuem Vorfall und pro NPC messen. Probe: `origin_growth`.

### F19 · P1 für Native-Import · Der C++-JSON-Parser akzeptiert kaputte Eingaben als andere Daten

**Fundstelle:** [json.hpp](../../port/cpp/include/usc/json.hpp), `parse`,
Zeilen 188–192, und Parserfunktionen ab Zeile 277.

Die kompilierte Gegenprobe ergibt unter anderem: `{"a":1` → `{"a":1}`, `{"a" 1}` → `{"a":1}`, **`[1,]` → `[1,0]`**, **`wat` → `0`**, `1e` → `1.0`. Fehlende Syntax wird nicht zuverlässig zurückgewiesen; Restzeichen werden nicht auf vollständigen Verbrauch geprüft.

Das steht an der Grenze für Packs, Konfiguration und Save-Imports über die C-ABI. Ein beschädigtes Dokument kann dadurch unbemerkt als andere Konfiguration ankommen. Python und C++ stimmen für diese Eingaben nicht überein.

**Reparatur:** Einen bewährten Parser verwenden oder vollständige JSON-Konformität mit unabhängiger Testsuite, Fehlermeldungen und Tiefen-/Größenlimits herstellen. Die Eigenschaft „keine externen Laufzeitabhängigkeiten“ rechtfertigt keine stillschweigende Datenkorrektur. Probe: [repro_json_2026_09_07.cpp](repro_json_2026_09_07.cpp).

### F20 · P2 · Gültige Unicode-Escapes werden im C++-Pfad beschädigt

**Fundstelle:** [json.hpp](../../port/cpp/include/usc/json.hpp), Zeilen
340–365.

Das gültige JSON `"\ud83d\ude00"` wird nicht zum gemeinsamen Codepoint U+1F600 zusammengesetzt. Der Parser erzeugt **`ed a0 bd ed b8 80`** statt UTF-8 **`f0 9f 98 80`**. Das betrifft Emoji und andere Zeichen außerhalb der BMP, wenn ein Serializer sie als Surrogatpaar ausgibt, darunter Pythons übliches `ensure_ascii=True`.

**Reparatur:** Surrogatpaare korrekt kombinieren, vierbyteiges UTF-8 erzeugen und unzulässige Einzel-Surrogate ausdrücklich behandeln. Sprachübergreifende Roundtrip-Tests mit realen Unicode-Zeichen ergänzen. Probe: dieselbe C++-Datei.

### F21 · P2 · Die Drohungsbewertung liest Angst in der falschen Richtung

**Fundstelle:** [social.py](../../unscripted/social.py),
`TheoryOfMindEngine.expected_reaction`, Zeilen 113–119; Bedeutung des Feldes in
[standing.py](../../unscripted/standing.py), Zeilen 208–216.

`agent.relationships[other]['fear']` ist die Angst des Handelnden vor dem Gegenüber. Die ToM-Formel behandelt sie als Angst des Gegenübers vor dem Handelnden. Das führt im Test zu **+0,32**, wenn A große Angst vor B hat und B keine vor A, aber **−0,40** im umgekehrten Fall.

**Reparatur:** Ein explizites Modell von „A glaubt, dass B A fürchtet“ verwenden. Die tatsächliche umgekehrte Beziehung ungeprüft auszulesen würde zwar die Richtung wechseln, aber Allwissenheit in ToM einführen. Probe: `tom_fear_direction`.

### F22 · P1 für Determinismusversprechen · Der Provider beeinflusst, ob Wissen überhaupt entsteht

**Fundstelle:** [sdk.py](../../unscripted/sdk.py), `_deliver`, Zeilen 1108–1139;
zusätzlich Timeout/Fallback in [edge.py](../../unscripted/edge.py).

Gleiche Welt, gleicher Spielerbefehl: Mit **„The clinic? Shutters were down all night.“** erhält der Spieler ein Belief. Mit **„Long day. I could use a drink.“** erhält er keines. Beide veröffentlichten Antworten haben **ACCEPT**. Ein nicht realisiertes Commitment wird verworfen.

Das verhindert zwar, dass eine vollständig ausweichende Antwort als Fakt propagiert wird. Es bedeutet aber auch, dass Textprovider und bei Fallbacks ihre Laufzeit die semantische Zustandsentwicklung beeinflussen. „Das Modell bestimmt nur die Formulierung“ ist in dieser starken Bedeutung derzeit falsch.

**Reparatur:** Vor der Veröffentlichung für jedes verbindliche Commitment eine gültige deterministische Formulierung bereitstellen. Modelldefekte und Timeouts wählen dann diese semantisch äquivalente Formulierung. Wird stattdessen die Semantik verworfen, muss dieses Ergebnis Teil des autoritativen Eingabe-/Entscheidungslogs sein und das Determinismusversprechen entsprechend enger ausfallen. Probe: `provider_changes_semantic_state`.

## Was an der Theorie trägt – und was nicht belegt ist

**Die Trennung von Welt, subjektiver Überzeugung und kommunizierter Aussage ist richtig.** Typisierte Propositionen und explizite Herkunft liefern eine Grundlage, die freie Dialoghistorien allein nicht liefern. Ein NPC darf überzeugt und dennoch im Unrecht sein. Das ermöglicht Ermittlungen, Rufschädigung, Täuschung und unterschiedliche soziale Perspektiven.

Die Verbindung von kurzzeitigen Emotionen, langsamerer Stimmung und Persönlichkeit ist ebenfalls eine begründete Modellierungsentscheidung. ALMA beschreibt genau eine solche mehrschichtige Architektur. Das rechtfertigt die Struktur, nicht automatisch die hier gewählten Kennzahlen oder jedes Mapping. [Gebhard, ALMA](https://www.dfki.de/en/web/research/projects-and-publications/publication/1782).

**Die Belief-Rechnung ist eine Heuristik in Bayesianischer Form.** Für ein binäres Ereignis H wäre die Bayes-Aktualisierung:

`L_neu = L_alt + log(P(E | H) / P(E | nicht H))`.

Hier wird stattdessen ein aus Vertrauen, Kompetenz und Skepsis gebildetes κ in `log(κ/(1−κ))` eingesetzt. Das ist nur unter zusätzlichen Annahmen über die Zuverlässigkeit des Evidenzkanals ein Likelihood-Verhältnis. Niedrige κ-Werte machen eine Quelle sogar zum Gegenindikator. Beobachtungsqualität dämpft im Runtime-Pfad überwiegend den Trust-Term, nicht die gesamte Evidenz.

Die aktuelle `CONCEPT.md` relativiert die Kalibrierung bereits sinnvoll. `CALIBRATION.md` kennzeichnet dagegen Teile als „grounded“, beschreibt κ vereinfacht als Produkt und schlägt vor, Autoren-Szenarien zur Kalibrierung zu verwenden. **Autoren-Erwartungen nachzutunen ist brauchbare Spielkalibrierung, aber keine empirische Bestätigung menschlicher Glaubenswahrscheinlichkeiten.**

Ein konsistenter Evidenzkern sollte erhalten:

`L = L_prior + Σ d_e`, `S_plus = Σ max(d_e, 0)`, `S_minus = Σ max(−d_e, 0)`.

Bei Entwertung werden die vorhandenen `d_e` neu gewichtet; daraus werden alle drei Größen konsistent abgeleitet. Ein gesonderter Zustand „Misstrauen wegen Entlarvung“ kann zusätzlich existieren. Er darf nicht heimlich als faktischer Gegenbeweis in dieselbe Summe eingehen.

**Ursprungsgleichheit ist nur eine Form von Quellenabhängigkeit.** Die geometrische Reihe mit ρ = 0,1 begrenzt Wiederholungen eines erkannten Ursprungs auf etwa 1,111 erste Beiträge. Unterschiedliche IDs können aber dieselbe Quelle oder koordinierte Aussagen repräsentieren. Umgekehrt kann ein einzelner Sprecher mehrere unabhängige Beobachtungen haben. Die IDs müssen diese fachliche Unterscheidung ausdrücken; eine Zeichenkette mit Sprecher und Uhrzeit genügt nicht.

**„Parakonsistent“ ist nur in einer begrenzten Bedeutung zutreffend.** Das System kann widersprechende Aussagen halten, ohne daraus beliebige Folgerungen abzuleiten. Es implementiert damit noch keine vollständige parakonsistente Inferenzlogik. Die isolierten Marginalwerte funktional ausschließender Propositionen werden nicht zu einer gemeinsamen Wahrscheinlichkeitsverteilung normalisiert. Das ist als Modell eines inkonsistenten NPCs möglich, aber keine kohärente globale Bayes-Verteilung. Die Theorie sollte diese beiden Ziele nicht vermischen.

**„Common knowledge“ ist hier eher ein Öffentlichkeitsregister.** Ein Radioempfänger weiß nicht automatisch, wer sonst eingeschaltet hat oder verstanden hat. Die tatsächlich vom Simulator bekannte Zuhörermenge einfach allen Mitgliedern als gemeinsam bekannt zuzuschreiben, verlangt zusätzliche Annahmen über den Kanal. Außerdem ist Wissen im klassischen epistemischen Sinn wahrheitsgebunden; gemeinsam geglaubte Falschmeldungen sind ein anderer Begriff. Eine idealisierte öffentliche Bekanntmachung ist modellierbar, muss aber ausdrücklich als solche definiert werden. [Halpern und Moses, Knowledge and Common Knowledge in a Distributed Environment](https://www.cs.cornell.edu/home/halpern/papers/common_knowledge.pdf).

**ACT-R-inspirierte Abrufstärke ist nicht gleich vollständiges Vergessen von Fakten.** Aktivierung durch Häufigkeit und Aktualität ist sinnvoll begründet. Hier lesen `_direct_answer` und `_tellable` jedoch direkt alle Beliefs; episodische Abrufgrenzen begrenzen nicht automatisch das sagbare Wissen. Dauerhaftes semantisches Wissen kann erwünscht sein, sollte aber vom beworbenen Vergessen unterschieden werden. [Anderson, ACT-R Learning Theory](https://act-r.psy.cmu.edu/wordpress/wp-content/uploads/2012/12/39jra_cds_2000_a.pdf).

**Die Prospect-Option ist keine vollständige Cumulative Prospect Theory.** `outcome_value` transformiert einzelne Wahrscheinlichkeiten separat und die Gruppenaggregation mittelt Beiträge. Die zitierte Theorie von 1992 verwendet kumulative, rangabhängige Entscheidungsgewichte. Auch ein dimensionsloser „stärkster unerfüllter Bedarf“ wird nicht schon dadurch zum passenden Referenzpunkt aller Ergebnisdimensionen. Für ein Spiel ist eine Prospect-inspirierte Nutzwertheuristik vertretbar. Die stärkere wissenschaftliche Bezeichnung erfordert mehr. Die Option ist standardmäßig aus. [Tversky und Kahneman 1992](https://psych.fullerton.edu/mBIRNBAUM/psych466/articles/Tversky_Kahneman_JRU_92.pdf).

**Es fehlen unabhängige Gütekriterien für die Gesamtarchitektur.** Viele etablierte Theoriebegriffe zusammen ergeben nicht automatisch ein validiertes Gesamtmodell. Benötigt werden Vergleichsgruppen, Parameter-Sensitivität und Ablationen: Welchen messbaren Beitrag liefern Provenanz, Revision, Standing und Memory tatsächlich zur Nachvollziehbarkeit und Spielqualität? Ein stabiles Simulationsprogramm kann trotzdem unplausible oder langweilige Figuren produzieren.

## Wie belastbar sind Tests, Evidenz und Portierung?

Positiv sind die verhaltensorientierten Szenarien, nachvollziehbaren Provenanztests, realen Integrationspfade, dokumentierten früheren Fehler und überprüfbaren Langzeitbelege. Die bitgenauen Python/C++-Vergleiche sind erhebliche Arbeit und schützen gegen Portierungsdrift.

Sie schützen **nicht gegen gemeinsame Spezifikationsfehler**. Die falsche Evidenzzuordnung und der Verlust von Judgement-Metadaten stehen auch in den entsprechenden C++-Modulen. Zwei Implementierungen derselben falschen Rechnung stimmen perfekt überein.

Auch ein Testorakel kann denselben blinden Fleck haben wie die geprüfte Komponente: `evidence.py` sucht Geheimnislecks über dieselben `surface_forms`, die der Validator verwendet. Der durch F02 veröffentlichte Inhalt muss deshalb nicht als Leak gezählt werden. `_belief_sanity` prüft gültige Wahrscheinlichkeitsbereiche und nichtnegative Summen; es erkennt F07/F08 nicht. Der beobachtete Langzeitbetrieb und seine Zahlen werden dadurch nicht erfunden, aber ihre Aussagekraft bleibt enger als „semantische Sicherheit“.

Die dokumentierten Millionen Turns laufen überwiegend nach Sättigung auf kleinem, festem Inhalt und mit optionalen Ebenen aus. Das eigene Evidenzdokument benennt dies bereits. Für Produktionsreife fehlen Belastungen mit dauerhaft neuen Ereignissen, wachsendem Aussagenkatalog, häufigem Save/Load, allen vorgesehenen Features, kaputten Eingaben und einem unabhängigen semantischen Prüfkorpus.

**Priorität für Tests:** Die Gegenbeispiele dieses Reviews als Spezifikationstests übernehmen; Mutationstests danach erweitern. Savegame-Tests müssen Fortsetzungen vergleichen. Revisions-Tests müssen nach Historienkürzung laufen. Texttests müssen Negationen, vertauschte Akteure, andere Zeiten, Paraphrasen und mindestens die vorgesehenen Ausgabesprachen enthalten. Native Tests brauchen neben korrekten Fixtures auch ungültige JSON-Eingaben und Unicode-Roundtrips.

Für Plattformversprechen zählen reale Zielplattformen. Ein Linux-Build und kleine Floating-Point-Abweichungen ohne diskrete Änderungen in fünf Szenarien beweisen keine universelle Plattformidentität. Für Lockstep wären zusätzliche Festlegungen zu Mathematik, Sortierung, Zustandsversionen und Log-Replay nötig. Für den ersten Einzelspieler-Release kann eine engere, getestete Plattformmatrix ausreichen.

## Marktvergleich: Wo besteht eine Chance?

Die folgenden Wettbewerbsangaben stammen aus öffentlich zugänglichen Hersteller- und Forschungsquellen, abgerufen am Reviewdatum. Es wurden keine Wettbewerber integriert oder auf demselben Spiel getestet. Fehlende öffentliche Dokumentation einer Funktion ist kein Beweis, dass ein Produkt sie nicht besitzt.

| Alternative | Öffentlich belegter Schwerpunkt | Bedeutung für Unscripted |
|---|---|---|
| Inworld | C++-Runtime für die Orchestrierung von Sprache, LLMs, Wissen/Memory und Tools; Engine-SDKs. [Hersteller](https://inworld.ai/blog/new-ai-infrastructure-scaling-games-media-characters) | „Runtime“, „Memory“ und „Engine-Integration“ sind keine Alleinstellungsmerkmale. Chance bei klarer Provenanz und deterministischen sozialen Konsequenzen. |
| Convai | Langzeitgedächtnis, Knowledge Banks, Charakterkonfiguration und Aktions-/Narrativ-APIs. [Memory](https://docs.convai.com/api-docs/convai-playground/character-creator-tool/memory), [APIs](https://docs.convai.com/api-docs/api-reference/core-api-reference/character-crafting-apis) | Kein tragfähiger Vergleich zu einem vermeintlich zustandslosen Chatbot. Natürlichsprachliche Interaktion und Autorenworkflow müssen ernst genommen werden. |
| NVIDIA ACE / PUBG Ally | Sprachverständnis, laufender Spielkontext und ausführbare Ingame-Handlungen. [Technischer Herstellerbericht](https://developer.nvidia.com/blog/how-krafton-built-pubg-ally-a-co-playable-character-powered-by-nvidia-ace/) | Ein anderer, realer Anspruch an KI-Mitspieler. Unscripted sollte zunächst soziale Weltzustände und Konsequenzen lösen. |
| Unreal StateTree / bestehende Spiel-KI | Hierarchische Zustände, Tasks, Übergänge und Engine-Integration. [Epic](https://dev.epicgames.com/documentation/unreal-engine/overview-of-state-tree-in-unreal-engine?lang=en-US) | Häufig die tatsächliche Kaufalternative: Das Studio ergänzt eigene Social-Logik. Unscripted muss Integrations- und Autorenzeit sparen. |
| ink / Autorenwerkzeuge | Bewährtes narratives Scripting, Editor, Unity-/Unreal-Integration, MIT-Lizenz. [inkle](https://www.inklestudios.com/ink/) | Für festgeschriebene Geschichten kann ein Autorenwerkzeug wirtschaftlicher sein. Anschluss an solche Werkzeuge ist attraktiv. |
| CiF / Prom Week; Generative Agents | Spielbare soziale Beziehungen sowie erfahrungsbasierte Agenten mit Memory, Reflexion und Planung. [Prom Week](https://ojs.aaai.org/index.php/AIIDE/article/view/12662), [Generative Agents](https://arxiv.org/abs/2304.03442) | Soziale KI, Erinnerungen und emergente Interaktion sind keine neue Grundidee. Die Produktchance liegt in überprüfbarer Umsetzung und einfacher Nutzbarkeit. |

**Meine Produkthypothese:** „Ein SDK für Spiele, in denen Zeugenaussagen, Gerüchte und Ruf eine nachvollziehbare Geschichte haben.“ Zielkunden sind zunächst kleinere bis mittlere Teams mit Ermittlungs-, RPG-, Stealth- oder sozialen Simulationsspielen und einem überschaubaren Cast. Dort lässt sich der Nutzen in einer konkreten Szene zeigen.

Das ist eine Empfehlung aus Code- und Marktvergleich, kein belegter Product-Market-Fit. Das Repository zeigt die Möglichkeit eines Vorteils: strukturierte Herkunft, explizite Unsicherheit, falsche Überzeugungen und kontrollierbare Konsequenzen. Es zeigt noch nicht, dass ein fremdes Studio damit schneller arbeitet oder Spieler die Ergebnisse bevorzugen.

Die eigene `FlatWorld`-Gegenüberstellung demonstriert Unterschiede zur bewusst einfachen Boolean-Repräsentation. Sie ist ausdrücklich kein implementierter Wettbewerber. Ein professionelles Studio kann Flags um Herkunftslisten, Ereignisbusse und Beziehungen ergänzen. Für einen Überlegenheitsnachweis braucht es diese realistischere Alternative und denselben Inhalts-/Implementierungsaufwand auf beiden Seiten.

## Was für eine erste Produktionsversion fehlt

Der Engpass ist gegenwärtig **Verlässlichkeit und Nutzbarkeit**, nicht die Anzahl weiterer Theoriemodule.

| Bereich | Konkretes Release-Kriterium |
|---|---|
| Semantik und Geheimnisse | F02/F03/F22 geschlossen; ein klar dokumentierter Modus mit garantiert kontrollierter Ausgabe; Modellwechsel oder Timeout verändert verbindliche Aussagen nicht. |
| Evidenz und Konsequenzen | F04–F08 sowie F16 behoben; Ursprünge bleiben unterscheidbar; Wiederholungen und Entwertung funktionieren über lange Historien und Reloads. |
| Weltzeit und Savegames | F10–F14 geschlossen; stabile Weltidentität, atomarer Import, definierte Migration, unveränderliche Audit-Verläufe und Fortsetzungstests. |
| Native Schnittstelle | F19/F20 behoben; validierte Daten an der ABI; reproduzierbare Release-Artefakte für die tatsächlich unterstützten Ziele. |
| Deployment | F01 geschlossen; Produktprofil ohne offene Verwaltungsoberflächen; dokumentierter Start, Ende, Wiederanlauf und Fehlervertrag. |
| Ressourcen | Vereinbarte Budgets für konkrete Cast-/Ereignisgrößen; P50/P95/P99, größte Zeitsprünge, Speicher-/Save-Wachstum und überlastete Textprovider messen. |
| Autorenworkflow | Eine fremde Designerin kann ohne Hilfe einen kleinen Fall anlegen, Widerspruchs-/Quellenfehler verstehen und ihre Szene in der Zielengine spielen. |
| Inhalt und Betrieb | Lokalisierbare kontrollierte Texte, reproduzierbare Pakete, Versionsmatrix, Supportprozess und ein Release-Beispiel mit echter Spielschleife. |

Eine einzelne priorisierte Engine und zunächst PC sind ein sinnvolles erstes Produktziel. Den Python-Kern als Referenz zu erhalten und den C++-Kern für Native-Builds zu härten ist plausibel. Beide Versionen müssen gegen eine gemeinsame **fachliche Spezifikation** geprüft werden, nicht nur gegeneinander. Das derzeitige Nebeneinander von HTTP- und Native-Pfaden braucht eine klare Empfehlung je Einsatzfall und eine verlässliche Supportmatrix.

Ein weiterer großer Theorieausbau, zweite Ordnung von ToM, selbstgenerierende Institutionen oder Persönlichkeitsdrift würde die Fehlerfläche vergrößern, bevor die existierenden Kernversprechen verlässlich sind. Diese Themen können nach einem brauchbaren Kundenfall wieder bewertet werden.

## Vorgehen und Vertrieb

Die folgenden Phasen geben die empfohlene Reihenfolge vor; sie sind keine Aufwandsschätzung nach vollständiger Implementierungsplanung.

**Phase 1: Kern reparieren und Angebot enger fassen.** Zuerst HTTP-Schutz, kontrollierte Realisierung, atomare Saves/Weltidentität und Evidenzbilanz. Die Regressionen aus diesem Review werden Release-Gates. In README und Demo nur das versprechen, was diese Gates tatsächlich prüfen. Die vorhandene Transparenz über Grenzen beibehalten und auf die neue Schutzgrenze ausweiten.

**Phase 2: Eine verkaufbare Szene bauen.** Ein 15–20-minütiger Fall mit etwa 6–12 relevanten Figuren: Ein glaubwürdiger falscher Bericht verbreitet sich, mehrere Aussagen lassen sich zur gleichen Quelle zurückverfolgen, der Spieler findet Gegenbeweise, entlarvt die Quelle, und eine konkrete Entscheidung eines NPCs ändert sich. Speichern und späteres Laden müssen mitten im Fall funktionieren. Dieselbe Szene mit einem einfacheren authored Ansatz vergleichen. Bestehende Demos können die Basis liefern.

**Phase 3: Drei Designpartner gewinnen.** Etwa 20–30 passende Studios identifizieren, 8–10 Problemgespräche führen und drei zeitlich begrenzte Integrationspiloten anstreben. Entscheidend ist, ob eines ihrer tatsächlichen Designprobleme gelöst wird. Ein Pilot sollte eine konkrete Szene, ein definiertes Integrationsziel und eine feste Menge Unterstützung enthalten. Preis und Laufzeit offen vereinbaren; eine Pilotgebühr kann auf die spätere Lizenz angerechnet werden. Diese Zahlen sind Vertriebsziele, keine Nachfrageprognose.

**Phase 4: Mit gemessenem Nutzen veröffentlichen.** Aus einem erfolgreichen Pilot werden Referenzszene, Installationspaket, technischer Bericht und ein knappes Fallbeispiel: benötigte Integrationszeit, eingesparte Autorenarbeit, Fehler, Performance und wahrgenommene Spielerqualität. Erst danach breiter über enginebezogene Communities, technische Vorträge, Beispielprojekte und passende Marktplätze vertreiben. Die konkreten Veröffentlichungsbedingungen des gewählten Marktplatzes sind beim Einreichen separat zu prüfen.

**Vertriebsbotschaft:** „Der Spieler kann herausfinden, wer eine Geschichte in Umlauf gebracht hat – und die Welt reagiert darauf, wenn sie widerlegt wird.“ Dazu ein kurzer Clip, ein spielbares Beispiel und eine in wenigen Minuten nachvollziehbare Integration. Ein langer Theorieüberblick ist gutes Material für die technische Prüfung; die erste Verkaufsseite muss einen Spielnutzen zeigen.

Die bereits veröffentlichten Lizenzstaffeln sind zunächst Preishypothesen. Aus dem Repository lässt sich keine Zahlungsbereitschaft ableiten. Weitere Preisoptimierung ist weniger wertvoll als die Frage, ob ein Studio nach einer eigenen Integration dafür bezahlt. Supportaufwand und Wartung beider Runtime-Pfade müssen in der Kalkulation enthalten sein. Produktpakete sollten nach Integrationsumfang und Unterstützung verständlich werden, nicht nach der Anzahl benannter psychologischer Theorien.

**Messbare Entscheidungspunkte:** Ein fremdes Team schafft die erste Integration und Inhaltsänderung selbst; mindestens ein Pilot wird bezahlt oder in einen verbindlichen Kauf überführt; ein Vergleich zeigt einen Vorteil bei Autorenzeit, Nachvollziehbarkeit oder Spielqualität. Scheitert vor allem die Inhaltserstellung, zuerst Authoring verbessern. Scheitert der spielerische Nutzen, die Produkthypothese verkleinern. Mehr Simulationsmodule lösen keine dieser beiden Ursachen automatisch.

## Reproduzieren

Im Repository-Root:

```bash
python3 reviews/2026-09-07/repro_2026_09_07.py
python3 reviews/2026-09-07/repro_2026_09_07.py --http --only http_token_disclosure
g++ -std=c++17 -Iport/cpp/include reviews/2026-09-07/repro_json_2026_09_07.cpp -o /tmp/unscripted-review-json
/tmp/unscripted-review-json
```

Die Python-Prüfungen liefern beim untersuchten Stand absichtlich Exitcode **1**: `invariant_holds: false` bedeutet einen reproduzierten Gegenbeleg. `probe_error` wäre dagegen ein Fehler im Prüffall. Der HTTP-Test öffnet nur einen kurzlebigen lokalen Port und verwendet ein erfundenes Token. Das C++-Programm protokolliert die beobachteten Parserergebnisse.

**Entscheidung:** Den deterministischen sozialen Kern weiterentwickeln und seine heutigen Garantien belastbar machen. Das Produkt sollte zunächst einen klaren narrativen Anwendungsfall außergewöhnlich gut lösen. Der vorliegende Stand bietet dafür Substanz; die gezeigten Fehler müssen vor dem Verkauf starker Sicherheits-, Revisions- und Produktionsversprechen behoben werden.
