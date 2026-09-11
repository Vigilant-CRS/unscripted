# Prüfnachweis zum Review vom 7. September 2026

Untersuchter Commit: `f8dba3936240ce5b4493d9c259bc224acb3651ac`, Runtime 1.18.0. Umgebung: Linux x86_64, Python 3.14.4, g++ 15.2.0. Produktcode, Tests und Worldpacks wurden nicht geändert. Die Review-Artefakte liegen außerhalb des Paketverzeichnisses `docs/`.

## Vorhandene Testsuite

**Alle 163 vorhandenen Testfunktionen wurden erfolgreich ausgeführt, verteilt auf zwei Abschnitte. Dies war kein unterbrechungsfreier grüner Gesamtlauf.**

1. Der erste Versuch innerhalb der Sandbox scheiterte beim Start des lokalen Testdienstes. Danach wurde dieselbe Suite mit den erforderlichen Dienstrechten gestartet.
2. `python3 -u tests/test_scenarios.py`: Die ersten **119 Tests bestanden**. Der folgende Pakettest beanstandete die zunächst unter `docs/reviews/` abgelegten Review-Programme und deren Bytecode. Diese durch das Review verursachte Dateiplatzierung wurde korrigiert, indem die Artefakte nach `reviews/2026-09-07/` verschoben wurden. Der Lauf endete mit Exitcode 1. [Vollständiges Protokoll dieses Laufs](suite-first-119.log).
3. Anschließend wurden die **44 verbleibenden Testfunktionen ab Nummer 120** in unveränderter Reihenfolge ausgeführt. Der Fortsetzungshelfer liest die Funktionsliste direkt aus der Suite; keine Testfunktion wurde ersetzt. Alle 44 bestanden, Exitcode 0. Darunter bestand der Pakettest mit allen damals vorhandenen 145 Datendateien. [Protokoll](suite-last-44.log), [portabler Fortsetzungshelfer](resume_suite.py).

Ausgeführt wurden unter anderem der echte Unreal-Plugin-Build, Unity-Assembly-Kompilierung, Python/C++-Vergleiche, C-ABI-, Unreal-Native-, Unity- und Godot-Binding-Prüfungen sowie der vollständige Showcase-Test. Das ist keine Behauptung, sämtliche interaktiven Editor-Spielabläufe oder andere Betriebssysteme und Konsolen getestet zu haben.

### Nachträgliche Änderung im gemeinsamen Arbeitsverzeichnis

Während des Reviews erschien zusätzlich die unversionierte Datei `docs/SPECIFICATION.md`. Sie wurde nicht von diesem Review erstellt oder verändert und war nicht Teil des ursprünglich untersuchten Commits. Eine abschließende isolierte Wiederholung von `test_packaging_manifest_covers_every_data_file` meldet nun:

```text
AssertionError: data files not packaged: ['docs/SPECIFICATION.md']
```

[Protokoll des abschließenden Pakettests](packaging-final.log). Damit ist der **aktuelle gemeinsame Arbeitsstand nicht vollständig grün**, obwohl alle ursprünglichen 163 Testfunktionen in den oben dokumentierten Abschnitten bestanden. Für die neue Dokumentdatei müssen Ablage und Paketmanifest abgestimmt werden. Sie wurde nicht stillschweigend in das Review des ursprünglichen Codes einbezogen.

## Unabhängige Gegenbeispiele

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Python, ohne Netzwerk und ohne echtes LLM | 19 von 19 Prüfungen liefern `invariant_holds: false`; keine `probe_error` | [Programm](repro_2026_09_07.py), [JSON](probes.json) |
| Echter lokaler HTTP-Dienst | Ohne Token `/capabilities`: 401; `/demo`: 200 mit konfiguriertem synthetischem Token; damit `/advance`: 200 | [JSON](http.json) |
| Tatsächlich kompilierter C++-JSON-Parser | Sechs ungültige Eingaben werden akzeptiert; gültiges Surrogatpaar wird in ungültiges UTF-8 umgewandelt | [Programm](repro_json_2026_09_07.cpp), [Ausgabe](cpp-json.txt) |

Die Python-Prüfprogramme verwenden absichtlich Exitcode **1**, wenn ein Gegenbeispiel reproduziert wird. Das ist von einem kaputten Prüffall zu unterscheiden. Sie dokumentieren den untersuchten fehlerhaften Stand; nach Reparaturen sind die erwarteten Invarianten als reguläre Regressionstests zu übernehmen.

Die Textprovider-Prüfungen speisen fest vorgegebene Antworten ein. Sie widerlegen die behauptete Vertrauensgrenze anhand konkreter Eingaben, messen aber keine reale Fehlerrate eines Sprachmodells. Der HTTP-Test verwendet ausschließlich `review-synthetic-token-not-a-real-credential`, bindet lokal und beendet den eigenen Dienst wieder. Es wurden keine realen Geheimnisse abgegriffen und keine fremden Dienste untersucht.

## Grenzen

- Die vorhandene zweistündige Langzeitmessung wurde nicht wiederholt. Die Inhalte der zehn in `evidence/README.md` benannten versiegelten Kernmodule stimmen mit dem angegebenen Commit `36bf7097` überein.
- Keine neuen Langzeitlasttests mit unbegrenzt neuen Inhalten, keine zusätzlichen Plattformzertifizierungen und keine vollständige empirische Validierung des psychologischen Gesamtmodells.
- Der Marktvergleich stützt sich auf die im [Bericht](REVIEW.md) verlinkten Primärquellen. Kein konkurrierendes SDK wurde implementiert oder im direkten Leistungsvergleich vermessen.
- Keine Änderungen am Produktcode, kein Commit, kein Release und keine Kontaktaufnahme mit potenziellen Kunden.
