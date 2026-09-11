# Lamb Street

A murder happened behind a hotel at 21:07. Six people on one street saw part of
it. One of them is lying. You can ask any of them anything.

There is a switch at the top of the screen:

    NPC MODE    SCRIPTED    UNSCRIPTED

Everything else is identical — same scene, same camera, same six characters,
same questions, same order. Only where the answers come from changes.

## The point of it

`scripted_dialogue.gd` is the conventional side, and it is written to be **good**:
per-character lines, variations so nobody repeats themselves, a cover story for
the liar, a fallback for questions nobody wrote. It is the shape Dialogic, Yarn
Spinner and Ink all produce, because it is the shape the problem has when
dialogue is authored by hand.

The demo asks the same questions twice: on the night of, and at nine the next
morning, after the police give a statement to City Radio.

* **21:07 — Byrne, about the bulletin.** The table says *"Radio's been on about
  it all morning."* Twelve hours before the radio says anything. The line is not
  badly written; it was written before anyone knew when it would be asked, and a
  table has no other kind of time to be written at. The runtime has Byrne say he
  has nothing, because he has nothing.
* **09:00 — Byrne, Halloran and Okonkwo, in three different rooms.** The table
  repeats its three lines. The runtime has all three independently give the
  *radio's* version — which is wrong, and is wrong because it came from the one
  source all three listen to. Nobody authored that agreement.
* **09:00 — Reyes, at the door.** Both sides say the same sentence. Only one of
  them knows it is a lie: `honesty: lie   confidence: certain   heard by: 1`.

## Running it

The scene starts the runtime itself, from a single bundled file. Build it first
(it is not committed — `unscripted bundle` regenerates it, and a checked-in copy
would drift):

    cd ../..
    python3 -m unscripted bundle --out demos/lamb-street/unscripted.pyz
    /path/to/godot --path demos/lamb-street

Keys: `T` switch mode, `SPACE` ask, `1`–`5` choose the question, arrows walk,
`R` reset.

## Recording the comparison

`--tour` walks both modes through the same three acts unattended, so the
comparison is not a matter of who was at the keyboard:

    godot --path . --tour --write-movie recording/lamb-street.avi \
          --fixed-fps 30 --resolution 1920x1080 --quit-after 9000
    ffmpeg -i recording/lamb-street.avi -c:v libx264 -crf 21 -pix_fmt yuv420p \
           -r 30 recording/lamb-street.mp4

It prints one line per beat, which is what CI reads.

## The addon

`addons/unscripted/` is a copy of `integrations/godot/addons/unscripted/`,
because Godot can only load an addon from under `res://`. A test asserts the two
are byte-identical, so the demo can never quietly test a fork of the client.
