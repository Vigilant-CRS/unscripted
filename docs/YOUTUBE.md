# YouTube — Titel und Beschreibung

Veröffentlicht: **https://youtu.be/TfMbbJvjOk0**

Alles hier ist belegt. Keine Zahl steht drin, die nicht im Repository gemessen
wurde, und keine Fähigkeit, die nicht implementiert ist. Das ist kein Purismus,
sondern Verkaufsstrategie: die Leute, die das kaufen sollen, sind technische
Leads, und die prüfen genau eine Behauptung nach, bevor sie den Rest glauben.

---

## Titel

```
Unscripted: NPCs That Find Things Out — Rumour, Lies & Memory
```

Produktname vorn, dann der Unterschied in fünf Wörtern. Mobil wird nach etwa
vierzig Zeichen abgeschnitten; bis dahin steht die ganze Aussage schon da, der
Rest ist für die Suche. **„unscripted" ist in diesem Markt bereits ein
Suchbegriff** — Inworld wirbt mit „unscripted dialogue", andere mit „unscripted
conversations" —, der Produktname liegt also auf einem Begriff, nach dem ohnehin
gesucht wird. Gefunden wird er dadurch leichter, exklusiv besetzen lässt er sich
nicht; das ist hier auch nicht das Ziel.

## Titel — Alternativen

```
Unscripted: A Game World That Remembers What You Did
NPC AI Without Hardcoding: Information That Travels, Decays and Lies
Why Every NPC Knows Everything — and a Runtime That Fixes It
```

Die erste stellt das Spielerverhalten nach vorn. Die zweite ist die
suchstärkste, wenn Studios nach „NPC AI" und „hardcoding" suchen. Die dritte ist
die klickstärkste, nennt aber den Produktnamen nicht.

---

## Beschreibung

Rund 3.600 von 5.000 Zeichen. Der erste Satz steht vollständig vor „mehr".

```
Unscripted is a persistent world & social memory runtime for games: NPCs know only what they saw or were told, pass it on, lie about it — and the town changes with how you play.

In this video: a councillor is shot in the open street. The radio blames a youth gang; the trader whose stall it happened in front of saw something else. Nobody scripted the split — it falls out of who was listening and who talks to whom. Then the same eight questions are asked twice: of a world with quest flags, and of this one.

WHAT CHARACTERS KNOW
• Only what they observed or were told — on whose word, and how sure they are.
• Information travels through who meets whom. Two witnesses hold the truth at 0.83; within an hour all seven characters hold the radio's version.
• Rumours change as they travel (levelling and sharpening, after Allport & Postman).
• Characters lie, misread what they see, or believe false reports — and a lie is recorded as a lie, with the liar's name on it.
• Memories fade: a threat stays retrievable for about a week, something trivial for three days.

WHAT YOUR PLAYING DOES TO THE WORLD
• Hit somebody in the open and the street closes up: openness to a stranger 0.56 → 0.40, suspicion 0.56 → 0.77 — and the mood drifts into the next street.
• Be vile to a trader where one man sees it. Six hours later a woman in another room, who never met you, has gone from "Evening." to "I've got nothing for you." Somebody told her.
• Break a promise and four people call you unreliable, three of whom only watched. Keep it and nobody remarks on it.
• Threats and kindness change what people do, not just what they think: fear makes your next threat land; respect makes them defer.
• Same seed, same conduct: the same world, exactly. Different conduct: a different world — because of you, not noise.

NOT BETTER DIALOGUE — A WORLD THAT KNOWS THINGS
The runtime decides what happened, who knows what and what each character may say. A language model is optional: it only words it, and a validator refuses a line the character does not hold.

FOR DEVELOPERS
• Godot 4.6 addon with two playable demos. Unity 6 LTS package and Unreal 5.8 plugin, each tested inside the editor against a live service. Anything else speaks HTTP/JSON.
• Two ways in: a local service beside the game — one bundled file, no install, no network calls — or a C++17 core with a C ABI and thin bindings for Unreal, Unity and Godot, for platforms that forbid an interpreter. 50 of 51 modules match the reference bit for bit, checked on every test run.
• A player's turn costs 0.08–1.5 ms in C++ for 11 to 1,001 characters; an hour of a 200-person town, about 1 ms.
• Deterministic, so a bug report is a repro. Saves go into your own save file. No model, authored text, or any OpenAI-compatible endpoint — including a local GPU.
• 204 tests, no dependencies. A sealed two-hour evidence run: 2,987,366 turns, 75,434 simulated days, 59,745 invariant checks, 0 violations.
• Verified in three engines and two demos — not yet in a shipped game.

Grounded in published research: Daley & Kendall (1964), Allport & Postman (1947), Anderson & Schooler (1991), Hatfield, Cacioppo & Rapson (1994), Chwe (2001).

Characters remember. Relationships evolve. Communities react. Worlds change.

Source, licence and evidence: https://github.com/Vigilant-CRS/unscripted
Showcase: https://vigilant-crs.github.io/unscripted/
Vigilant e.K., Stuttgart — https://vigilant-crs.de

CHAPTERS
0:00 The problem
0:54 A killing, and two accounts
2:46 Asking eight questions, twice
4:57 What this means for a developer

#gamedev #npc #gameai #indiedev #godot #unrealengine #unity #gamedesign
```

Wo jede Zahl herkommt: Züge, Tage und Prüfungen aus `evidence/`; die Straße,
das gebrochene Versprechen und die Frau in der Bar aus
`test_the_world_answers_to_what_the_player_does` und der Demo *The Square*;
die Kosten pro Zug aus `tools/frame_bench.py`; der Port aus `port/cpp/probe/`.
Alle stehen im README mit dem Befehl, der sie reproduziert.

---

## Was ich bewusst NICHT hineingeschrieben habe

**„Local mood can shift toward fear, hostility, optimism or instability."** Ein
Ort hat im Runtime genau drei Werte — *openness*, *suspicion*, *candour*. Angst
gibt es als Emotion einzelner Figuren, „optimism" und „instability" gibt es gar
nicht. Der Satz wurde durch das ersetzt, was tatsächlich passiert, mit der Zahl,
die es belegt.

**„Character Runtime" und „Unscripted Worlds".** Das Produkt heißt überall
*Unscripted*, die Kategorie *Persistent World & Social Memory Runtime*.
„Character Runtime" stellt es neben Inworld, Convai und NVIDIA ACE, die auf der
Ebene einzelner Figuren arbeiten; der Unterschied liegt eine Ebene höher, bei
dem, was Information in einer ganzen Gesellschaft von Figuren anrichtet.

**„KI-NPCs" als Schlagwort.** Es würde Aufrufe bringen und die falschen. Wer nach
KI-NPCs sucht, sucht ein Sprachmodell — und bekäme hier das Gegenteil erklärt.
Der Titel würde die Leute anziehen, die nach zwei Minuten abspringen, und das
verschlechtert die Empfehlung des Videos für alle anderen.

**Vergleiche mit namentlich genannten Spielen.** *Radiant AI*, *Nemesis-System*
und ähnliche bringen Suchvolumen und laden zu einer Diskussion darüber ein, ob
der Vergleich fair ist. Diese Diskussion gewinnt man nicht in Kommentaren.

**Zahlen ohne Herkunft.** Jede Zahl oben stammt aus einem Test oder einem
Beweislauf im Repository. Wenn ein technischer Lead eine nachprüft und sie
stimmt, glaubt er den Rest; stimmt eine nicht, glaubt er nichts mehr.

---

## Was YouTube noch braucht, das kein Text ist

**Ein Vorschaubild.** Der stärkste Kandidat ist der geteilte Bildschirm mit den
zwei Farben — bernstein für die Radioversion, grün für die Zeugin — mit vier
Wörtern darüber, etwa *„who told whom?"*. Das Bild funktioniert ohne Ton und ohne
Kontext, und das ist die einzige Anforderung an ein Vorschaubild.

**Ein kurzer Schnitt.** Sieben Minuten sind richtig für ein Studio und zu lang
für eine Zeitleiste. Neunzig Sekunden nur mit dem Mordfall und dem Vorher-Nachher
sind der Zubringer; das lange Video ist das Ziel.

**Untertitel.** `tools/godot_demo.py --subtitles` schreibt sie aus denselben
gemessenen Offsets, die auch den Schnitt bestimmen — Text und Bild können also
nicht auseinanderlaufen. Selbst hochladen statt YouTube automatisch erkennen
lassen: die automatische Erkennung verliest die Eigennamen aus den World Packs.
