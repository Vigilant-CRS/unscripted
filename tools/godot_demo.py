"""Record the Godot demo: service, engine, narration, one MP4.

Not part of the package. Like `scale_bench.py`, this is a tool for producing
something the repository claims, kept so whoever doubts the claim can reproduce
it rather than take it.

    python3 tools/godot_demo.py --out demo-pages/engine.mp4

What it does, in order: starts `unscripted serve` on a free port, runs the Godot project
through Movie Maker mode (a fixed timestep, so the recording is deterministic and
does not depend on how fast this machine happens to be), speaks one line per beat
with the same voice adapter the film uses, lays each line at the exact second its
beat begins, and transcodes to H.264 with the narration mastered to the level
online video is mixed at.

The timings come from the demo's own constants rather than from watching it, so
the narration cannot drift out of sync with a scene it is describing.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PROJECT = os.path.join(ROOT, "integrations", "godot", "UnscriptedDemo")
PACK = os.path.join(ROOT, "worldpacks", "market-square")

#: Breath after each line, and the shortest a beat may be however short its line.
GAP_SECONDS = 0.7
MIN_BEAT_SECONDS = 2.6

#: The narration, laid at offsets computed from the demo's own constants.
#:
#: It opens on the problem, in the words a studio uses about it, and only then
#: shows the system -- and it names what is on the screen while it is on the
#: screen, because a viewer who cannot tell what a dot means learns nothing from
#: watching it change colour.
#: Spoken over the opening cards, one line each, and over the closing ones. The
#: closing cards are the specification: a studio's third question is what it
#: would actually be installing, and a video that never answers it sends them to
#: a README they will not open.
INTRO_LINES = [
    "Unscripted. A runtime from Vigilant.",

    "What if you could build a game world where characters lie to the player, "
    "and where the runtime knows it was a lie?",

    "Where information takes time to travel, arrives at different people in "
    "different shapes, and never reaches everyone?",

    "Where a district has a mood, and a player who behaves badly in it makes it "
    "harder to get an answer there?",

    "Most attempts at this make the characters smarter. More dialogue, more "
    "scripted branches, or a language model behind each one so they speak well.",

    "All of those are written in advance. They are the same for every player, "
    "and they still hand every character the same knowledge at the same moment.",

    "The problem was never how the characters talk. It is that the world they "
    "live in does not know anything, and does not change.",

    "That needs a system that organises itself, and this is what one looks like.",
]

OUTRO_LINES = [
    "None of what you just watched was written for this video. It is what the "
    "same seven characters do with one killing and one radio station.",

    "The same machinery does the rest of it. Be unpleasant to a trader and her "
    "mood drops by almost a full point, and she is measurably sharper with "
    "everyone she speaks to next, not only with you.",

    "A little of that mood moves to whoever she talks to, and three quarters of "
    "those transfers are second hand. One rude moment reaches people who never "
    "met you.",

    "Memories fade unless they are brought up again. Being threatened stays "
    "reachable for about a week; something trivial is gone in three days. A "
    "character can be useful on Tuesday and no help at all by Friday.",

    "Opinions change. Catch a source lying and every belief resting on it is "
    "recomputed across the whole block, not just the one you challenged.",

    "Hurt somebody in front of people who share their trade, and that belonging "
    "becomes the thing they are for the next day. Break a promise and it costs "
    "you a reputation with everyone who heard you make it.",

    "For a developer, this is the point: none of that is branched, scripted or "
    "hard coded. Side missions have a reason to exist because somebody knows "
    "something somebody else needs, and every player ends up somewhere "
    "different because of what they did.",

    "What you would be installing is a local service. HTTP and JSON on "
    "localhost, no network calls, and no third-party packages. It ships as a "
    "single file.",

    "It runs with no language model at all, on authored text, or with a local "
    "one on any OpenAI-compatible endpoint. The runtime decides what may be "
    "said; the model only chooses the words.",

    "About seventy-six kilobytes per character in a save. Two thousand "
    "characters across four hundred places, a hundred and forty-one "
    "milliseconds per simulated hour. Every layer can be switched off, and off "
    "changes nothing.",

    "Unscripted. Built by Vigilant, in Stuttgart.",
]

RUNNING_LINES = [
    "A quest flag flips and everybody knows at once. Put a language model behind "
    "them and they become articulate, but they still know whatever is in the "
    "prompt, all of them, at the same moment. Nothing is ever found out.",

    "Unscripted, built by Vigilant, is the layer underneath. It comes from "
    "game theory and information theory, and it treats what a character knows as "
    "something that arrives: late, unevenly, and not to everyone.",

    "So here is a murder. A councillor has been shot in the open street, in "
    "daylight, in front of the market stalls.",

    "City Radio has the story first: it was the east-side kids. Six people on "
    "this block hear it and believe it, because that is what a broadcast does.",

    "But Yara had a stall two metres away. She saw three men who did not run and "
    "did not panic. She knows it was contract work, and she is not listening to "
    "the radio, because she was standing in it.",

    "Two answers now exist in one block. Amber travelled by broadcast, green by "
    "one person telling another, and every line that lights stays as the route "
    "it took -- so the runtime can always say who told whom, and on whose word "
    "anybody believes anything.",

    "Places do as much work here as people. This square is authored to pass "
    "things on nearly twice as readily as the alley, so where a character spends "
    "the day decides what reaches them -- which is why moving somebody is a way "
    "of changing what they can possibly know.",

    "Nobody wrote this split. It fell out of who was listening and who talks to "
    "whom -- which is the difference between a system that organises itself and "
    "a branch somebody has to author. A detective story becomes possible with no "
    "quest logic at all: the truth exists, in one person, and has to be found.",
]

QUESTION_LINES = [
    # 1. the man on the bench -- the loud version, and where it came from
    "You ask the man on the bench. In a flag world he knows, because everybody "
    "knows, and there is nothing else to ask him.",
    "Here he holds the radio's version, and the panel says where he got it and "
    "how often he has heard it. Ask him again and he does not become surer: it "
    "is still one broadcast.",

    # 2. the witness -- the reason to look for people
    "You ask the trader whose stall it happened in front of. Same flag. Same "
    "answer as everybody else.",
    "She has the other answer, first hand, at point eight three. This is the "
    "moment a flag world cannot give you: one person in the block knows, and "
    "finding her is the game.",

    # 3. walking
    "You walk to the precinct.",
    "The block keeps talking while you walk, and none of it is waiting for you. "
    "Come back an hour later and the room has moved on without you.",

    # 4. the officer -- ignorance you can play against
    "You ask the officer holding the case. Flags: yes, he knows.",
    "He has the radio's version, from the radio, and he has never met the woman "
    "who watched it happen. He is not hiding anything. He genuinely does not "
    "know, and that is a thing a player can now do something about.",

    # 5. the aide -- and the point of all of it
    "You ask the councillor's own aide. The flag says what it has said five "
    "times already.",
    "She holds the truth and offers you the radio's story. The runtime recorded "
    "that as a lie, with her name on it. Believe her and you are wrong for the "
    "next three hours of play, and being wrong is finally available.",

    # 6. back to the square
    "You go back to the square.",
    "The witness is still there, and so is every claim she has made. What she "
    "said is kept with her name on it, so it can be quoted back at her later, or "
    "used to catch her out.",

    # 7. leaning on her
    "You lean on her. A flag has nothing to record about how you asked.",
    "Her trust in you drops to zero. Not her view of the case, her view of you.",

    # 8. the same question, a different world
    "You ask the same question again. In a flag world this is the same question "
    "with the same answer, because there is only one of each.",
    "She gives you less. The same woman, the same fact, a shorter sentence, "
    "because of something you did. Every player ends up in a slightly different "
    "world, and this is how: not by branching a script, but by being treated "
    "differently by people who remember.",
]


def _srt_time(seconds: float) -> str:
    """SubRip wants hours:minutes:seconds,milliseconds, and is fussy about it."""
    whole = int(seconds)
    return (f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d},"
            f"{int(round((seconds - whole) * 1000)):03d}")


def _wrap_caption(text: str, width: int = 42) -> str:
    """Two-ish lines. A caption wider than the screen is worse than none."""
    words, lines, row = text.split(), [], ""
    for word in words:
        if row and len(row) + 1 + len(word) > width:
            lines.append(row)
            row = word
        else:
            row = f"{row} {word}".strip()
    if row:
        lines.append(row)
    return "\n".join(lines)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def constants() -> dict:
    """Read the timings out of the demo instead of restating them here."""
    source = open(os.path.join(PROJECT, "Main.gd"), encoding="utf-8").read()

    def number(name: str) -> float:
        match = re.search(rf"const {name} := ([0-9.]+)", source)
        if not match:
            raise SystemExit(f"{name} is no longer declared in Main.gd")
        return float(match.group(1))

    return {"side": number("SIDE_SECONDS"), "hours": number("HOURS"),
            "hour_seconds": number("HOUR_SECONDS")}


def questions_in_demo() -> int:
    """How many questions the demo asks, read from the demo."""
    source = open(os.path.join(PROJECT, "Main.gd"), encoding="utf-8").read()
    block = source[source.index("const QUESTIONS := ["):source.index("var unscripted")]
    return block.count('{"text"')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="engine.mp4")
    parser.add_argument("--godot", default=os.path.expanduser(
        "~/.local/opt/godot/Godot_v4.3-stable_linux.x86_64"))
    # Kokoro by default: 24 kHz against piper's 22.05, and the only one of the
    # three whose intonation sounds like somebody meaning what they say. A
    # studio watching this judges the voice before it judges the argument.
    parser.add_argument("--narrator", default="kokoro",
                        choices=("kokoro", "piper", "espeak-ng"))
    parser.add_argument("--narrator-model", default=None)
    parser.add_argument("--subtitles", default=None, metavar="FILE",
                        help="Write an SRT of the narration, timed from the "
                             "same measurements the cut uses.")
    parser.add_argument("--chapters", default=None, metavar="FILE",
                        help="Write YouTube chapter marks, derived from the "
                             "same measured line offsets the cut uses.")
    parser.add_argument("--narrator-voice", default="af_heart",
                        help="kokoro voice name; af_heart is the best-graded one")
    args = parser.parse_args()
    if args.narrator_model is None:
        args.narrator_model = os.path.expanduser(
            "~/.local/opt/kokoro/kokoro-v1.0.onnx" if args.narrator == "kokoro"
            else "~/.local/opt/piper/en_US-lessac-high.onnx")

    for name, path in (("godot", args.godot), ("ffmpeg", shutil.which("ffmpeg"))):
        if not path or not (os.path.exists(path) or shutil.which(str(path))):
            raise SystemExit(f"{name} not found: {path}")

    work = os.path.join(os.path.dirname(os.path.abspath(args.out)) or ".",
                        ".engine-work")
    os.makedirs(work, exist_ok=True)

    print("  ... speaking the narration")
    import wave
    from unscripted.voice import VoicePlan, synthesize
    from unscripted.world import load_world_pack, pronunciation_hints
    hints = pronunciation_hints(load_world_pack(PACK))

    timing = constants()
    expected = 2 * questions_in_demo()
    if len(QUESTION_LINES) != expected:
        raise SystemExit(
            f"the demo asks {questions_in_demo()} questions and so needs "
            f"{expected} spoken lines; QUESTION_LINES has {len(QUESTION_LINES)}.")

    def say(index: int, text: str) -> float:
        wav = os.path.join(work, f"say{index:02d}.wav")
        synthesize(VoicePlan("narrator", text, rate=0.94, pitch=-0.05,
                             loudness=0.62, voice_name=args.narrator_voice),
                   wav, backend=args.narrator, model=args.narrator_model,
                   hints=hints)
        with wave.open(wav) as handle:
            return handle.getnframes() / handle.getframerate()

    # THE PICTURE IS CUT TO THE VOICE, not the other way round. Laying lines at
    # constant offsets over a scene with constant beats means any line longer
    # than the beat talks over the next one, and six of sixteen did -- by as much
    # as three and a half seconds. So: speak first, measure, then tell the engine
    # how long to hold each beat.
    lines, at = [], 0.0
    intro = []
    for index, text in enumerate(INTRO_LINES):
        seconds = say(1000 + index, text)
        lines.append({"wav": os.path.join(work, f"say{1000 + index:02d}.wav"),
                      "at": at, "text": text, "seconds": seconds})
        intro.append(seconds + GAP_SECONDS)
        at += seconds + GAP_SECONDS

    intro_span = at
    for index, text in enumerate(RUNNING_LINES):
        seconds = say(index, text)
        lines.append({"wav": os.path.join(work, f"say{index:02d}.wav"),
                      "at": at, "text": text, "seconds": seconds})
        at += seconds + GAP_SECONDS
    running_span = at - intro_span + 1.0
    sides = []
    for offset, text in enumerate(QUESTION_LINES):
        index = len(RUNNING_LINES) + offset
        seconds = say(index, text)
        lines.append({"wav": os.path.join(work, f"say{index:02d}.wav"),
                      "at": intro_span + running_span + sum(sides), "text": text,
                      "seconds": seconds})
        sides.append(max(MIN_BEAT_SECONDS, seconds + GAP_SECONDS))

    outro, at = [], intro_span + running_span + sum(sides)
    for index, text in enumerate(OUTRO_LINES):
        seconds = say(2000 + index, text)
        lines.append({"wav": os.path.join(work, f"say{2000 + index:02d}.wav"),
                      "at": at, "text": text, "seconds": seconds})
        outro.append(seconds + GAP_SECONDS)
        at += seconds + GAP_SECONDS

    # CHAPTERS, FROM THE SAME NUMBERS THE CUT USES. YouTube reads these out of a
    # description and they are most of what makes a seven-minute video findable
    # in pieces. Deriving them from the measured line offsets rather than typing
    # them means they cannot drift out of step with the film.
    if args.chapters:
        marks = [(0.0, "The problem"),
                 (lines[len(INTRO_LINES)]["at"], "A killing, and two accounts"),
                 (lines[len(INTRO_LINES) + len(RUNNING_LINES)]["at"],
                  "Asking eight questions, twice"),
                 (lines[len(INTRO_LINES) + len(RUNNING_LINES)
                        + len(QUESTION_LINES)]["at"],
                  "What this means for a developer")]
        with open(args.chapters, "w", encoding="utf-8") as handle:
            for at, title in marks:
                # YouTube requires the first chapter at 0:00 and mm:ss form.
                handle.write(f"{int(at) // 60}:{int(at) % 60:02d} {title}\n")
        print(f"  ... chapters written to {args.chapters}")

    # SUBTITLES, FROM THE SAME MEASUREMENTS. Search reads them, and a viewer with
    # the sound off reads them, and the text and the timings both already exist
    # here -- so not emitting them was leaving the cheapest thing on the table.
    if args.subtitles:
        with open(args.subtitles, "w", encoding="utf-8") as handle:
            for index, line in enumerate(lines, start=1):
                start, end = line["at"], line["at"] + line["seconds"]
                handle.write(f"{index}\n{_srt_time(start)} --> "
                             f"{_srt_time(end)}\n{_wrap_caption(line['text'])}\n\n")
        print(f"  ... subtitles written to {args.subtitles}")

    overlaps = sum(1 for a, b in zip(lines, lines[1:])
                   if a["at"] + a["seconds"] > b["at"] + 0.05)
    if overlaps:
        raise SystemExit(f"{overlaps} lines still overlap; the pacing is wrong")

    # Chosen here rather than at the top: synthesising the narration takes about
    # two minutes, and a port reserved before that wait can be taken during it.
    port = free_port()
    print(f"  ... serving the runtime on {port}")
    # Kept rather than discarded: a service that fails to start says why, and
    # throwing that away turns a one-line cause into twenty minutes of guessing.
    service_log = open(os.path.join(work, "service.log"), "w", encoding="utf-8")
    service = subprocess.Popen(
        [sys.executable, "-m", "unscripted", "serve", "--world-pack", PACK,
         "--auth-token", "dev", "--port", str(port)],
        cwd=ROOT, stdout=service_log, stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 25
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.4)
        else:
            service_log.flush()
            said = open(os.path.join(work, "service.log"), encoding="utf-8").read()
            raise SystemExit("the service never came up on port %d.\n%s"
                             % (port, said.strip()[-800:] or "(it printed nothing)"))

        raw = os.path.join(work, "godot.avi")
        print("  ... running the engine (a window appears; it closes itself)")
        subprocess.run(
            [args.godot, "--path", PROJECT, "--rendering-driver", "opengl3",
             "--write-movie", raw, "--fixed-fps", "30", "--resolution", "1920x1080",
             "--", f"--url=http://127.0.0.1:{port}", "--token=dev",
             f"--running={running_span:.3f}",
             "--sides=" + ",".join(f"{side:.3f}" for side in sides),
             "--intro=" + ",".join(f"{card:.3f}" for card in intro),
             "--outro=" + ",".join(f"{card:.3f}" for card in outro)],
            check=True, capture_output=True, timeout=900)
    finally:
        service.terminate()
        service.wait(timeout=10)

    if not os.path.exists(raw):
        raise SystemExit("the engine produced no recording")

    # THE LOADING PHASE IS IN THE RECORDING. Movie Maker writes every frame the
    # engine draws, and the demo fetches its whole session before it plays any of
    # it, so the file opens on "Running hour 6 of 16..." for as long as the HTTP
    # took. The playback length is known exactly -- it was handed to the engine --
    # so whatever the file has beyond it is the wait, and it comes off the front.
    played = (sum(intro) + running_span + sum(sides) + sum(outro) + 0.5)
    recorded = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", raw],
        capture_output=True, text=True, timeout=60).stdout.strip())
    waited = max(0.0, recorded - played)
    print(f"  ... trimming {waited:.1f}s of loading from the front")

    print("  ... assembling")
    # THE WINDOW IS NOT THE PROJECT. `--resolution 1920x1080` is asked for and
    # the window manager clamps it to whatever fits the screen with decorations
    # on, so a machine with a 1050-pixel-tall desktop records 1920x1004 and the
    # file is not 1080p. Padding to the demo's own background colour costs
    # nothing, distorts nothing, and produces a file with the shape it claims.
    inputs, filters, labels = ["-i", raw], [
        "[0:v]pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b0d11,"
        "setsar=1[v]"], []
    for index, line in enumerate(lines):
        inputs += ["-i", line["wav"]]
        filters.append(f"[{index + 1}:a]adelay={int(line['at'] * 1000)}|"
                       f"{int(line['at'] * 1000)}[a{index}]")
        labels.append(f"[a{index}]")
    # One mix, then one loudness pass over the result: normalising each line
    # separately would pull the quiet ones up to meet the loud ones.
    filters.append(f"{''.join(labels)}amix=inputs={len(lines)}:normalize=0"
                   f"[mixed]")
    filters.append("[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]")

    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{waited:.3f}", *inputs,
         "-filter_complex", ";".join(filters),
         "-map", "[v]", "-map", "[out]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18",
         # loudnorm resamples to 192 kHz internally, and left alone ffmpeg
         # picked 96 kHz for the AAC track -- outside what a lot of players and
         # every video platform expect. 48 kHz is what video is mixed at.
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", args.out],
        check=True, capture_output=True, timeout=1800)

    size = os.path.getsize(args.out)
    duration = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", args.out],
        capture_output=True, text=True, timeout=60).stdout.strip()
    shutil.rmtree(work, ignore_errors=True)
    print(f"\n{float(duration):.0f}s, {size / 1_000_000:.1f} MB -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
