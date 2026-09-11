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
Unscripted: A Game World That Remembers, Talks and Changes
NPC AI Without Hardcoding: Information That Travels, Decays and Lies
Why Every NPC Knows Everything — and a Runtime That Fixes It
```

Die erste ist die Formulierung aus der Beschreibung. Die zweite ist die
suchstärkste, wenn Studios nach „NPC AI" und „hardcoding" suchen. Die dritte ist
die klickstärkste, nennt aber den Produktnamen nicht.

---

## Beschreibung

```
Unscripted is a persistent world & social memory runtime for games, by Vigilant.

Most game worlds have one shared brain: a quest flag flips and every NPC knows
at once. Unscripted gives each character only what they could realistically have
seen or been told — and gives you a world that remembers what happened, talks
about it and changes because of it.

In this video: a councillor is shot in the open street. The radio says it was a
youth gang; the trader whose stall it happened in front of saw something else
entirely. Nobody scripted the split — it falls out of who was listening and who
talks to whom. Then the same eight questions are asked twice: once of a world
with quest flags, once of this one.

WHAT IT DOES

• NPCs know only what they observed or were told — and on whose word, and how sure they are.
• Information travels through who meets whom. Two witnesses hold the truth at
  0.83 confidence; within an hour all seven characters hold the radio's version,
  and the truth never catches up, because the lie had a transmitter.
• Rumours change as they travel: levelling and sharpening, after Allport & Postman.
• Characters lie, misread what they see, or believe false reports — and the
  runtime records a lie as a lie, with the liar's name on it.
• Memories persist, fade and can be contradicted. Being threatened stays
  retrievable for about a week; something trivial is gone in three days.
• Catch a source lying and every belief resting on it is recomputed across the block.
• Trust, relationships and reputation move with what you do. A broken promise
  costs you with everyone who heard you make it.
• Groups react together: hurt one of a trade in front of the others and that
  belonging becomes who they are.
• Places have a climate. After violence in the square, openness drops from
  0.605 to 0.197 — and a stranger asking questions gets measurably less.
• Moods spread from character to character; three quarters of those transfers
  are second-hand.
• What you did keeps mattering long after the event itself.

NOT BETTER DIALOGUE — A WORLD THAT KNOWS THINGS

Unscripted separates simulation from language. The runtime decides what
happened, who knows what, what each character believes and what they may say.
A language model is optional: it only chooses the words, and it is never the
source of truth for your game world.

FOR DEVELOPERS

A local service: HTTP and JSON on localhost, no network calls, no third-party
packages, one file. Runs with no language model at all, on authored text, or
with a local model on any OpenAI-compatible endpoint. Deterministic: same seed,
same world. About 76 KB per character in a save; 2,000 characters across 400
places at 141 ms per simulated hour. Every optional layer switches off, and off
changes nothing. Godot demos, Unity and Unreal plugins, and a dependency-free
C++17 port for consoles.

Grounded in published research: Daley & Kendall (1964), Allport & Postman (1947),
Anderson & Schooler (1991), Hatfield, Cacioppo & Rapson (1994), Chwe (2001).

Characters remember. Relationships evolve. Communities react. Worlds change.

Source, licence and evidence runs: https://github.com/Vigilant-CRS/unscripted
Live pages: https://vigilant-crs.github.io/unscripted/
Vigilant e.K., Stuttgart — https://vigilant-crs.de

CHAPTERS
0:00 The problem
0:54 A killing, and two accounts
2:46 Asking eight questions, twice
4:57 What this means for a developer

#gamedev #npc #gameai #indiedev #godot #unrealengine #unity #gamedesign
```

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
