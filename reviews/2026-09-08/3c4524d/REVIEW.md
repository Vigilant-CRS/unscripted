# Nachprüfung von Runtime 1.20.0

**Geprüft: `3c4524d`, 8. September 2026, Branch `epistemic-correctness-pass`.**

**Der dritte Pass repariert die bisherigen direkten Sprach-Gegenbeispiele. Eine allgemeine Korrektheits- oder Produktionsfreigabe ist noch nicht begründet: Zwei weitere Fehlergruppen sind reproduzierbar, beide auch im tatsächlich kompilierten C++-Code.**

Dieses Mal wurde zusätzlich die **vollständige vorhandene Suite neu ausgeführt: alle 199 Tests bestanden**. Die unabhängigen Gegenbeispiele zeigen Eigenschaften, die diese Suite noch nicht abdeckt. Sie ersetzen den grünen Lauf nicht durch eine Vermutung, sondern ergänzen ihn um konkrete Fehlerszenarien.

## Bestätigte Reparaturen

Die vorige [Prüfung von `fd76623`](../fd76623/REVIEW.md) wurde erneut ausgeführt. Ihre Gegenbeispiele zu zwei ausgewählten Fakten, abgeschnittenem Autoreninhalt, Providerprosa bei Begrüßungen und einem vorherigen Providertext bestehen jetzt im Standardmodus. Auch ihr konkreter Retentionsablauf mit genau einer Hörung nach jeder Verdrängung bleibt unter der Grenze. Der direkte ProviderError-Fall und die Ledger-Wasserlinie funktionieren weiterhin.

Der frühere Importtest endet jetzt mit der korrekten typisierten Ablehnung eines Saves aus `block-17` in `noir-harbor`. Das alte Programm fängt diese neue Ausnahme nicht ab und endet daher mit Exitcode 1. Das ist **kein** verbliebener Produktfehler; „jede Invariante wahr“ ist lediglich keine wörtlich zutreffende Beschreibung seiner unveränderten Ausgabe. [Rohdaten](previous-check.json).

`controlled` ruft jetzt auch für Begrüßungen und Ausweichantworten keinen Textprovider auf. Die zusätzliche Inhaltsauswahl wird auf die Topic-Formulierung begrenzt; faktische Zeilen werden nicht mehr durch die Satzlängenregel abgeschnitten. Die gelieferten Packs tragen Welt-IDs. Das sind konkrete Fortschritte.

## B1 · P1 · Die globale Quellenobergrenze hält weiterhin nicht

**Fundstellen:** [belief.py](../../../unscripted/belief.py), `record_provenance`
ab Zeile 124 und `correlation_discount` ab Zeile 279;
[belief.hpp](../../../port/cpp/include/usc/belief.hpp), Zeilen 161–174
und 354–371.

Das neue `unrecognised_spent` begrenzt nur das Gewicht bestimmter **Wiederaufnahmen** in den Index. Für die behauptete globale Grenze müssten dagegen alle früheren und späteren Beiträge desselben Ursprungs zusammen berücksichtigt werden. Zwei unabhängige Randfälle zeigen die Lücke.

### B1a: Bereits verbrauchtes Wiederholungsgewicht wird ein zweites Mal gewährt

Der Test hört die informative Aussage zunächst einmal und wiederholt sie achtmal, solange der Ursprung noch erkannt wird. Damit ist das normale geometrische Wiederholungsbudget praktisch verbraucht. Anschließend verdrängen neutrale Quellen den Ursprung; seine Rückkehr erhält nochmals ρ¹ aus dem neuen Budget.

| Größe | Ergebnis in Python und C++ |
| --- | --- |
| Globale Obergrenze | 3,271598865740488 Log-Evidenz |
| Vor Verdrängung | 3,271598862468889 |
| Zusätzlicher Beitrag bei Wiederaufnahme | 0,294443897916644 |
| Danach | **3,566042760385533**, p = **0,97250959** |

Es kam keine neue informative Evidenz hinzu. Die erste Wiederholungsreihe wurde bereits bezahlt; `unrecognised_spent` berücksichtigt sie nicht. Eine zweite vollständige Reserve von ρ/(1−ρ) darf dann nicht zusätzlich gewährt werden.

### B1b: Nach Wiederaufnahme umgeht die nächste Hörung das leere Budget

Bei der Rückkehr landet der Ursprung wieder in `origin_counts`. Die **nächste** Hörung nutzt deshalb den normalen `rho ** heard`-Zweig statt der Prüfung des geteilten Budgets. Selbst eine Wiederaufnahme mit Gewicht null trägt den Ursprung wieder ein und ermöglicht anschließend einen positiven Beitrag.

Der Test variiert den bisherigen Ablauf minimal: Nach jeder Verdrängung wird die informative Aussage zweimal statt einmal gehört. Er verwendet die Standardgrenze 512 und insgesamt nur 513 feste Ursprünge. Die übrigen Berichte haben κ=0,5 und liefern exakt keine informative Log-Evidenz.

| Zyklus | Beitrag der Wiederaufnahme | Beitrag der folgenden Hörung | Gesamtüberzeugung |
| --- | --- | --- | --- |
| 1 | 0,29444 | 0,02944 | 0,963326 |
| 2 | 0 | 0,02944 | 0,964352 |
| 20 | 0 | 0,02944 | 0,978705 |
| 100 | 0 | 0,02944 | **0,997941** |

Das geteilte Budget steht nach Zyklus 2 unverändert auf 0,11111111111111112. Trotzdem wächst die Evidenz weiter. Nach 100 Zyklen beträgt sie **6,183321856249536** statt höchstens **3,271598865740488**.

Das ist diesmal keine bewusst dokumentierte schwächere Zyklusgarantie: Code und Status behaupten ausdrücklich wieder eine globale Grenze. Diese wird verletzt. Beide Rechnungen wurden gegen die echten C++-Header kompiliert und liefern dieselben beobachteten Werte. [Python-Ergebnisse](results.json), [native Ergebnisse](native-results.txt).

**Empfohlener Abschluss:** Für die erste begrenzte Produktversion ist ein nicht verdrängender Index der zugelassenen Ursprünge die einfachere konservative Lösung: Bis zur Kapazität exakt zählen; weitere unbekannte Ursprünge nicht als Evidenz aufnehmen und diese Begrenzung melden. Bekannte Ursprünge behalten ihre Zählung. Eine Alternative ist ein exaktes Archiv. Soll die jetzige Verdrängung erhalten bleiben, braucht das gesamte Beitragsmodell einen nachweisbaren Budgetvertrag; nur das Gewicht beim Einfügen in den Index zu begrenzen genügt nicht.

**Abnahme:** Die Summe der Hörungsgewichte pro Ursprung bleibt für beliebige Reihenfolgen unter 1/(1−ρ), einschließlich Wiederholungen vor Verdrängung, mehrfacher Hörungen nach Wiederaufnahme und Save/Load. Generierte Ereignisfolgen gegen ein einfaches exaktes Referenzmodell prüfen. Die bestehende Einzelfolge „verdrängen, einmal hören“ ist dafür zu eng.

## B2 · P2 · Freigegebene Wiederholung trägt noch einen Ablehnungsstatus

**Fundstellen:** [sdk.py](../../../unscripted/sdk.py), Zweig `if not reworded`
ab Zeile 1190, Audit-Schreiben ab Zeile 1268 und Rückgabe ab Zeile 1274;
[sdk.hpp](../../../port/cpp/include/usc/sdk.hpp),
`dialogue.released_anyway` um Zeile 1269.

Fünf gewöhnliche Aufrufe von `respond("agent:barkeep_12", topic="clinic")` im Standardmodus reichen. Keine Fixture-Manipulation, kein externer Provider:

| Antwort | Verhalten | Verdict | Verbreitete Aussagen |
| --- | --- | --- | --- |
| 1 | bevorzugte Vorlage | ACCEPT | 1 |
| 2 | andere vollständige Vorlage | ACCEPT | 1 |
| 3 | dritte Vorlage | ACCEPT | 1 |
| 4 | bewusst nochmals freigegeben | **REJECT_SOFT** | **1** |
| 5 | bewusst nochmals freigegeben | **REJECT_SOFT** | **1** |

Wenn keine frische Variante mehr übrig ist, wird `dialogue.released_anyway` protokolliert, der ursprüngliche `ValidationResult` aber nicht auf eine Freigabe aktualisiert. Dadurch widersprechen sich Rückgabestatus, tatsächliche Emission und Audit: `accepted_output` ist bei Antwort 4 und 5 leer, während die Behauptung in die Welt gelangt.

Ein Client, der abgewiesene Antworten nicht anzeigt, erhält dadurch eine andere Sicht als die Zuhörer in der Simulation. Ob ein konkreter Client den Text tatsächlich unterdrückt, wurde hier nicht getestet. Der SDK-/Audit-Widerspruch selbst ist direkt nachgewiesen. Der C++-Pfad reproduziert dieselben Verdicts und jeweils eine emittierte Aussage.

**Reparatur:** Die endgültige Freigabeentscheidung muss Status, Text, semantische Emission und Audit gemeinsam bestimmen. Die ursprüngliche Wiederholungsbeanstandung kann als Qualitätshinweis erhalten bleiben. Der parallele Pfad `Runtime.say()` setzt in seinem entsprechenden Zweig bereits `verdict = ACCEPT`; der SDK-Pfad muss denselben Vertrag einhalten.

**Abnahme:** Alle vollständigen Varianten nacheinander aufbrauchen und anschließend weiterfragen. Jede tatsächlich freigegebene Antwort erhält den passenden endgültigen Status und einen dazu passenden Audit-Eintrag. Beide öffentlichen Sprachpfade und die C++-Implementierung prüfen. Der bestehende Test belegt bislang nur den erfolgreichen Wechsel auf eine noch unbenutzte Variante.

## Prüfnachweis

- Der erste vollständige Versuch innerhalb der Sandbox scheiterte am Start des lokalen Testdienstes. [Protokoll](sandbox-attempt.log).
- Die genehmigte Wiederholung der **unveränderten gesamten Suite** außerhalb der Sandbox endete mit **Exitcode 0: `All tests passed. (199 tests)`**. [Vollständiges Protokoll](full-suite.log). Enthalten waren Engine-Build-/Binding-Prüfungen, Python/C++-Vergleiche, die Konformanzfixtures, Pack-/Versionsprüfungen und der Showcase. Dies ist keine zusätzliche Zertifizierung sämtlicher interaktiver Editorabläufe oder Plattformen.
- Die neuen Python-Probes reproduzieren drei Gegenbeispiele: zwei zur Quellenobergrenze und eines zum Freigabestatus. Alle liefern `invariant_holds: false`, kein `probe_error`. Exitcode 1 ist dabei beabsichtigt.
- Ein eigenständiges C++-Prüfprogramm wurde mit `g++ -std=c++17 -O0` gegen die aktuellen Header kompiliert und ausgeführt. Es bestätigt beide numerischen Budgetverletzungen sowie `REJECT_SOFT` bei gleichzeitigem `spoken=1` ab der vierten Antwort.
- Kein zweistündiger neuer Evidence-Lauf, keine unabhängigen Spielertests und kein neuer Marktvergleich. Die versiegelte Messung bleibt ein Nachweis ihres alten Codestands. Einen neuen Lauf erst auf dem anschließend reparierten Release-Kandidaten versiegeln.
- Produktcode und bestehende Tests wurden nicht verändert. Nur dieser Review-Ordner wurde hinzugefügt. Branch nicht gemerged oder gepusht; der Remote-Stand wurde nicht neu abgefragt.

## Wie weiter?

**Zuerst B1 und B2 schließen.** B2 ist eng begrenzt. B1 braucht eine konsistente Quellenregel mit einem einfachen mathematischen Nachweis, bevor erneut eine globale Garantie behauptet wird.

Danach die vollständige Suite und unabhängigen Gegenbeispiele auf dem finalen Commit prüfen, einen Release-Kandidaten markieren und die Evidenz für genau diesen Stand erneuern. Zusätzlich einen längeren Lauf mit neuen Ereignissen/Ursprüngen, Wiederholungen und Save/Load durchführen; ein langer, bereits gesättigter Ablauf ersetzt diesen Lastfall nicht.

Für die erste Produktionsfreigabe weiterhin einen konkreten Umfang wählen: eine Engine, definierte PC-Ziele, `controlled`, vereinbarte Cast-/Ereignisbudgets und eine spielbare Ermittlungssequenz. Ein fremdes Team muss Installation, Inhaltsänderung, Speichern und Wiederaufnahme ohne Eingriffe in den Runtime-Code bewältigen. Gemessene Integrationszeit, Nachvollziehbarkeit und Fehlerberichte sind die Grundlage für einen betreuten, bezahlten Pilot.

Mehrquellen-Kollaps, die Bedeutung von κ unter 0,5 und der schwächere `provider`-Modus können ausdrücklich begrenzte Produktentscheidungen bleiben. Die behauptete globale Sättigung und der Freigabevertrag müssen dagegen im angebotenen Modus stimmen. Ein Merge nach `main` ist anschließend ein Integrationsschritt, keine eigene Produktionsprüfung.

## Reproduzieren

```bash
python3 reviews/2026-09-08/3c4524d/check.py
g++ -std=c++17 -O0 -Iport/cpp/include reviews/2026-09-08/3c4524d/check.cpp -o /tmp/unscripted-3c4524d-native
/tmp/unscripted-3c4524d-native worldpacks/cyberpunk-block
```

Die Programme benötigen keine Netzverbindung. Sie verwenden temporäre Zustände; Pack-Dateien und laufende fremde Dienste werden nicht verändert.
