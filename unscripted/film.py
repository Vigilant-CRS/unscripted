"""A video of a run, with narration, assembled from the recording itself.

The page animates and the page is the truth, but a page is a thing somebody has
to be persuaded to open. A video is a thing they watch because it was in front of
them, and it is the form a studio forwards to three colleagues.

There is no display on the machines this runs on, so nothing here records a
screen. The page already deep-links to a moment -- `#frame=120&paused` -- so each
frame is fetched as a still, and the stills are assembled at a pace the narration
sets rather than at a fixed frame rate. The result is that the picture slows down
where the voice has something to say and moves where it does not, which is what a
person would do with a scrubber and cannot be done with a constant rate.

**The narration is generated from the recording, not written beside it.** Every
sentence is the chapter that the runtime found in its own run, so a video cannot
describe a moment the recording does not contain, and re-running it after the
world changes produces a video about the new world rather than a stale one about
the old.

What this is not: broadcast production. The voice is a speech synthesiser, the
cuts are hard, and there is no music. It is an honest sixty seconds that can be
put in front of somebody, and it is reproducible from one command.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import wave

#: Frames are stills; this floors how long one may be shown, so a chapter with
#: many frames and a short line does not ask ffmpeg for a 2 ms picture.
MIN_FRAME_SECONDS = 1.0 / 24
#: How long a title card holds if nothing is being said over it.
CARD_SECONDS = 2.5


class FilmError(RuntimeError):
    """Something needed for a film is missing, and guessing would waste an hour."""


def requirements() -> dict:
    return {"chrome": shutil.which("google-chrome") or shutil.which("chromium")
                       or shutil.which("chromium-browser"),
            "ffmpeg": shutil.which("ffmpeg"),
            "espeak-ng": shutil.which("espeak-ng") or shutil.which("espeak")}


def check(narrator: str = "espeak-ng") -> None:
    needed = dict(requirements())
    if narrator == "piper":
        needed.pop("espeak-ng", None)
        needed["piper"] = shutil.which("piper") or shutil.which("piper-tts")
    elif narrator == "kokoro":
        needed.pop("espeak-ng", None)
        needed["kokoro-say"] = shutil.which("kokoro-say")
    missing = [name for name, path in needed.items() if not path]
    if missing:
        raise FilmError(
            "a film needs " + ", ".join(missing) + ". Chrome renders the frames "
            "(there is no display to record), ffmpeg assembles them, espeak-ng "
            "speaks the narration.")


CARDS_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>.</title><style>
 html,body{height:100%;margin:0;background:#0b0d11;color:#e9e7e2;
   font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",
   Arial,sans-serif;display:flex;align-items:center;justify-content:center}
 main{max-width:66vw;padding:0 4vw;text-align:center}
 .kicker{color:#e0a458;font-size:1.0vw;letter-spacing:.24em;text-transform:uppercase;
   margin-bottom:1.8vw;font-weight:500}
 p{font-size:2.9vw;line-height:1.28;margin:0;letter-spacing:-.02em;font-weight:600}
 p em{color:#e0a458;font-style:normal}
 .small p{font-size:1.9vw;color:#a8aeb8}
</style></head><body><main id="m"></main><script>
 const CARDS=__CARDS__;
 const h=new URLSearchParams(location.hash.replace(/^#/,""));
 const i=Math.max(0,Math.min(CARDS.length-1,parseInt(h.get("frame"),10)||0));
 const c=CARDS[i];
 document.getElementById("m").outerHTML =
   `<main class="${c.small?"small":""}">` +
   (c.kicker?`<div class="kicker">${c.kicker}</div>`:"") +
   `<p>${c.text}</p></main>`;
</script></body></html>
"""


def write_cards(cards: list, path: str) -> str:
    """One page holding every card; `#frame=k` shows the k-th.

    The same addressing as every other page here, so the still-shooting path does
    not need to know the difference between a sentence and a simulation.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(CARDS_PAGE.replace("__CARDS__", json.dumps(cards)))
    return path


# ------------------------------------------------------------------ frames ----

def shoot_many(shots: list, out_dir: str, *, width: int = 1920, height: int = 1080,
               workers: int = 4, progress=None) -> dict:
    """Stills for (page, frame) pairs across any number of pages."""
    browser = requirements()["chrome"]
    os.makedirs(out_dir, exist_ok=True)
    done = {}

    def one(shot):
        page, frame = shot
        key = f"{abs(hash(page)) % 10**8}_{frame:05d}"
        path = os.path.join(out_dir, f"s{key}.png")
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--virtual-time-budget=1400",
             f"--window-size={width},{height}", f"--screenshot={path}",
             f"file://{os.path.abspath(page)}#frame={frame}&paused"],
            capture_output=True, timeout=120)
        return shot, path

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for count, (shot, path) in enumerate(pool.map(one, shots), 1):
            if not os.path.exists(path):
                raise FilmError(f"the browser produced no still for {shot}")
            done[shot] = path
            if progress and count % 25 == 0:
                progress(f"{count}/{len(shots)} stills")
    return done


def shoot(page: str, frames: list, out_dir: str, *, width: int = 1920,
          height: int = 1080, workers: int = 4, progress=None) -> dict:
    """One still per frame, straight out of the page a viewer would open.

    Parallel because each still costs a browser start-up and they are entirely
    independent -- the page is a pure function of its hash fragment, which is the
    same property that makes the recording reproducible.
    """
    browser = requirements()["chrome"]
    os.makedirs(out_dir, exist_ok=True)
    page_url = "file://" + os.path.abspath(page)
    done = {}

    def one(index: int) -> tuple:
        path = os.path.join(out_dir, f"f{index:05d}.png")
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--virtual-time-budget=1200",
             f"--window-size={width},{height}", f"--screenshot={path}",
             f"{page_url}#frame={index}&paused"],
            capture_output=True, timeout=120)
        return index, path

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for count, (index, path) in enumerate(pool.map(one, frames), 1):
            if not os.path.exists(path):
                raise FilmError(f"the browser produced no still for frame {index}")
            done[index] = path
            if progress and count % 25 == 0:
                progress(f"{count}/{len(frames)} stills")
    return done


# --------------------------------------------------------------- narration ----

def script(recording: dict) -> list:
    """What is said, derived from the chapters the runtime found in its own run.

    Two sentences at most per beat. A synthesiser reading a paragraph is how a
    demo video gets closed.
    """
    cast = len(recording["world"]["agents"])
    final = recording["frames"][-1]
    knew = len(final["p"])
    lost = sum(1 for value in final["recalls"].values()
               if (value or {}).get("status") == "lost")
    wrong = len(final["wrong"])

    beats = [{"frame": 0, "text":
              f"One claim, and {cast} people who have not heard it yet. "
              f"Watch who ends up believing it, and on whose word."}]
    for chapter in recording.get("chapters") or []:
        text = chapter["title"] + "."
        if chapter.get("note"):
            text += " " + chapter["note"]
        beats.append({"frame": chapter["frame"], "text": text})

    closing = f"{knew} of {cast} hold it."
    if wrong:
        closing += f" {wrong} of them hold a version that changed on the way."
    if lost == knew and knew:
        closing += " Not one of them can recall who told them."
    closing += (" Every frame you have just seen is recorded state, reproducible "
                "from the same seed.")
    beats.append({"frame": len(recording["frames"]) - 1, "text": closing})
    return beats


#: Silence appended to every spoken beat. Sentences butted straight against each
#: other sound hurried and slightly panicked, which is the opposite of the tone
#: this material needs; the pause is also where a viewer looks back at the
#: picture. It counts toward the beat's length, so the frame holds through it.
BEAT_PAUSE_SECONDS = 0.55

#: Where the finished track sits. -16 LUFS is the level online video is mastered
#: to, so this plays at the same loudness as everything else in a browser tab
#: instead of making somebody reach for the volume.
TARGET_LUFS = -16.0


def _add_tail(path: str, seconds: float) -> None:
    """Append silence to a WAV in place, using nothing but the standard library."""
    with wave.open(path) as handle:
        params = handle.getparams()
        frames = handle.readframes(handle.getnframes())
    padding = b"\x00" * int(params.framerate * seconds) * params.sampwidth * params.nchannels
    with wave.open(path, "wb") as handle:
        handle.setparams(params)
        handle.writeframes(frames + padding)


#: A voice name belongs to one synthesiser. Only kokoro needs one named: espeak-ng
#: and piper have a default of their own, and asking espeak-ng for kokoro's
#: default is asking for a voice it does not have -- which is what both film
#: commands did by default, so the Pages build failed at its first line.
DEFAULT_NARRATOR_VOICES = {"kokoro": "af_heart"}


def voice_for(backend: str, requested: str | None) -> str:
    """The voice to ask this backend for: the one requested, else its own default."""
    return requested or DEFAULT_NARRATOR_VOICES.get(backend, "")


def speak(beats: list, out_dir: str, *, voice_rate: float = 0.92,
          backend: str = "espeak-ng", model: str | None = None,
          pause: float = BEAT_PAUSE_SECONDS, hints: dict | None = None,
          voice_name: str = "") -> list:
    """Render each beat and measure it, because the picture is cut to the voice.

    The narrator does not have to use the backend the characters use. A studio
    watching this judges the voice before it judges the argument, and kokoro or
    piper is worth the download for that one job even though neither can change
    pitch -- which the narrator does not need, being a narrator.
    """
    from .voice import VoicePlan, synthesize
    os.makedirs(out_dir, exist_ok=True)
    spoken = []
    for index, beat in enumerate(beats):
        path = os.path.join(out_dir, f"say{index:03d}.wav")
        # The narrator is a narrator, not a character: a flat, slightly slow read,
        # deliberately without the affect prosody that drives the cast.
        synthesize(VoicePlan(agent_id="narrator", text=beat["text"],
                             rate=voice_rate, pitch=-0.05, loudness=0.62,
                             voice_name=voice_name),
                   path, backend=backend, model=model, hints=hints)
        if pause > 0:
            _add_tail(path, pause)
        with wave.open(path) as handle:
            seconds = handle.getnframes() / handle.getframerate()
        spoken.append({**beat, "wav": path, "seconds": round(seconds, 3)})
    return spoken


# ---------------------------------------------------------------- assembly ----

def timeline(total_frames: int, spoken: list, stills: dict) -> list:
    """How long each still is held: the voice sets the pace, the frames follow.

    A beat that speaks for eight seconds over forty frames shows them at five a
    second; a beat that speaks for two seconds over four frames nearly holds
    still. That is the difference between a video and a slideshow with a
    voiceover on top.
    """
    plan = []
    for index, beat in enumerate(spoken):
        start = beat["frame"]
        end = spoken[index + 1]["frame"] if index + 1 < len(spoken) else total_frames
        covered = [f for f in sorted(stills) if start <= f < end]
        if not covered:
            # A beat whose window contains no rendered still -- which happens
            # whenever frames are sampled and a chapter lands between two of them
            # -- holds the nearest one. Falling back to the raw frame index asked
            # for a picture that was never taken.
            covered = [min(stills, key=lambda frame: abs(frame - start))]
        each = max(MIN_FRAME_SECONDS, beat["seconds"] / len(covered))
        for frame in covered:
            plan.append((stills[frame], round(each, 4)))
        # A beat whose frames are all floored would end before its line does;
        # hold the last picture for whatever the voice still needs.
        spent = each * len(covered)
        if beat["seconds"] > spent:
            plan.append((stills[covered[-1]], round(beat["seconds"] - spent, 4)))
    return plan


def assemble(plan: list, spoken: list, out_path: str, *, fps: int = 24) -> dict:
    """Stills plus narration into one file somebody can send to a colleague."""
    folder = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(folder, exist_ok=True)
    work = os.path.join(folder, ".film-work")
    os.makedirs(work, exist_ok=True)

    concat = os.path.join(work, "frames.txt")
    with open(concat, "w", encoding="utf-8") as fh:
        for path, seconds in plan:
            fh.write(f"file '{os.path.abspath(path)}'\nduration {seconds}\n")
        # The concat demuxer ignores the final duration unless the last file is
        # repeated; without this the closing shot is a single frame long.
        fh.write(f"file '{os.path.abspath(plan[-1][0])}'\n")

    audio_list = os.path.join(work, "audio.txt")
    with open(audio_list, "w", encoding="utf-8") as fh:
        for beat in spoken:
            fh.write(f"file '{os.path.abspath(beat['wav'])}'\n")

    raw = os.path.join(work, "raw.wav")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_list,
          "-c", "copy", raw])

    # One loudness pass over the whole narration rather than per beat: normalising
    # each sentence separately would pump the quiet ones up to meet the loud ones
    # and flatten the reading.
    narration = os.path.join(work, "narration.wav")
    # 48 kHz, not the synthesiser's own rate: that is what video is mixed at,
    # and leaving ffmpeg to choose after loudnorm's internal 192 kHz resample
    # produced files no platform expects.
    _run(["ffmpeg", "-y", "-i", raw,
          "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11",
          "-ar", "48000", narration])

    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
          "-i", narration,
          "-vf", f"fps={fps},format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
          "-c:v", "libx264", "-preset", "slow", "-crf", "18",
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
          "-movflags", "+faststart",
          "-shortest", out_path])

    duration = float(_run(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration", "-of",
                           "default=nw=1:nk=1", out_path]).strip())
    shutil.rmtree(work, ignore_errors=True)
    return {"path": out_path, "seconds": round(duration, 1),
            "stills": len(plan), "beats": len(spoken),
            "bytes": os.path.getsize(out_path)}


def _run(argv: list) -> str:
    completed = subprocess.run(argv, capture_output=True, timeout=900)
    if completed.returncode != 0:
        raise FilmError(f"{argv[0]} failed: "
                        f"{completed.stderr.decode('utf-8', 'replace')[-400:]}")
    return completed.stdout.decode("utf-8", "replace")


def make(recording: dict, page: str, out_path: str, *, every: int = 1,
         width: int = 1920, height: int = 1080, workers: int = 4,
         narrator: str = "espeak-ng", narrator_model: str | None = None,
         narrator_voice: str = "",
         progress=None) -> dict:
    """Record -> stills -> narration -> one file. The whole thing."""
    check(narrator)
    folder = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".",
                          ".film-stills")
    total = len(recording["frames"])
    wanted = sorted(set(list(range(0, total, max(1, every))) + [total - 1]))
    if progress:
        progress(f"{len(wanted)} stills to render")
    stills = shoot(page, wanted, folder, width=width, height=height,
                   workers=workers, progress=progress)

    if progress:
        progress("narration")
    spoken = speak(script(recording), os.path.join(folder, "voice"),
                   backend=narrator, model=narrator_model,
                   voice_name=narrator_voice)
    plan = timeline(total, spoken, stills)

    if progress:
        progress("assembling")
    result = assemble(plan, spoken, out_path)
    result["script"] = [{"text": beat["text"], "seconds": beat["seconds"]}
                        for beat in spoken]
    shutil.rmtree(folder, ignore_errors=True)
    return result


# -------------------------------------------------------------- storyboard ----

def storyboard(recording: dict, comparison: dict, *, cards_page: str,
               compare_page: str, map_page: str) -> list:
    """The film in five acts, because a demonstration is not an argument.

    The map on its own shows a mechanism working to somebody who already knows
    why the mechanism matters. Watched cold, it never says what goes wrong today,
    what this replaces, how it works, or who it is for -- four of the five things
    a viewer with forty seconds needs. So the run is act four, and it is
    surrounded.

    Act three is the comparison, and it is the one the whole film exists for:
    the same events, twice, both columns computed.
    """
    cast = len(recording["world"]["agents"])
    final = recording["frames"][-1]
    knew, lost = len(final["p"]), sum(
        1 for v in final["recalls"].values() if (v or {}).get("status") == "lost")
    rows = len(comparison["rows"])
    chapters = recording.get("chapters") or []

    beats = [
        # 1. the problem, in the words a studio uses about it
        {"page": cards_page, "frames": [0], "text":
         "Put a language model behind a character and it answers immediately. It "
         "will also tell the player something nobody ever told it."},
        {"page": cards_page, "frames": [1], "text":
         "Ask it to keep a secret and it usually does. Usually is not a thing you "
         "can ship."},
        {"page": cards_page, "frames": [2], "text":
         "And none of it can be tested, because the output is different every "
         "run."},
        # 2. what this is, in one sentence
        {"page": cards_page, "frames": [3], "text":
         "Unscripted decides what a character knows, believes, conceals and is "
         "allowed to say. The model only chooses the words."},
        # 3. the same events, twice
        {"page": cards_page, "frames": [4], "text":
         f"Here is one claim moving through {cast} characters. First as most games "
         f"hold it: one flag per fact. Then with this runtime, from the identical "
         f"events."},
    ]
    for index, row in enumerate(comparison["rows"][:6]):
        beats.append({"page": compare_page, "frames": [index],
                      "text": f"{row['q']} {_spoken(row)}"})

    # 4. the run itself
    beats.append({"page": map_page, "frames": [0], "text":
                  "That is a table. This is the same claim, moving."})
    for chapter in chapters:
        text = chapter["title"] + "."
        if chapter.get("note"):
            text += " " + chapter["note"]
        beats.append({"page": map_page, "frames": [chapter["frame"]], "text": text})

    closing = f"{knew} of {cast} end up holding it."
    if lost == knew and knew:
        closing += " Not one of them can recall who told them."
    beats.append({"page": map_page,
                  "frames": [len(recording["frames"]) - 1], "text": closing})

    # 5. why it can be trusted, and who it is for
    beats += [
        {"page": cards_page, "frames": [5], "text":
         "Same seed, same world, every time. So a bug report is a repro, and you "
         "can state a rule about your story and have the runtime search for the "
         "shortest way a player breaks it."},
        {"page": cards_page, "frames": [6], "text":
         "It is not a renderer, a voice or a chatbot. It sits behind whichever of "
         "those you already have, and decides what becomes true in the society."},
    ]
    return beats


CARDS = [
    {"kicker": "the problem", "text":
     "A character who <em>knows things nobody told them</em>"},
    {"kicker": "the problem", "text":
     "A secret that leaks <em>when the wording happens to go that way</em>"},
    {"kicker": "the problem", "text":
     "And a world you <em>cannot write a test for</em>"},
    {"kicker": "unscripted", "text":
     "The runtime decides what is <em>known, believed, concealed and sayable</em>."
     "<br>The model only chooses the words."},
    {"kicker": "the same events, twice", "text":
     "As <em>flags</em> &mdash; and as this runtime"},
    {"kicker": "why you can trust it", "text":
     "Same seed, same world.<br><em>204 tests. 2.99 million turns, sealed.</em>"},
    {"kicker": "what it is for", "text":
     "Studios shipping <em>systemic games</em><br>"
     "<span style='font-size:.6em'>vigilant-crs.de</span>",
     "small": False},
]


def _spoken(row: dict) -> str:
    """A comparison row, read aloud without the punctuation of a table.

    The dash carries an aside that a table can afford and a sentence cannot, so
    it goes. The semicolon does not: on the first row it introduces WHO did not
    hear it, which is the most interesting half of the answer.
    """
    flat = row["flat"].split("—")[0].strip().rstrip(".")
    unscripted = row["unscripted"].split("—")[0].strip().rstrip(".")
    if row.get("wins") == "flat":
        return f"Flags: {flat}. Unscripted: {unscripted}. Keep flags where they work."
    if row["flat"].startswith("nowhere"):
        return f"Flags have nowhere to put it. Unscripted: {unscripted}."
    return f"Flags: {flat}. Unscripted: {unscripted}."


def make_story(beats: list, out_path: str, *, width: int = 1920, height: int = 1080,
               workers: int = 4, narrator: str = "espeak-ng",
               narrator_voice: str = "",
               narrator_model: str | None = None, hints: dict | None = None,
               progress=None) -> dict:
    """Shoot every beat's stills, speak every beat, and cut one to the other."""
    check(narrator)
    folder = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".",
                          ".film-stills")
    shots = sorted({(beat["page"], frame) for beat in beats for frame in beat["frames"]})
    if progress:
        progress(f"{len(shots)} stills across {len({s[0] for s in shots})} pages")
    stills = shoot_many(shots, folder, width=width, height=height,
                        workers=workers, progress=progress)

    if progress:
        progress("narration")
    spoken = speak(beats, os.path.join(folder, "voice"),
                   backend=narrator, model=narrator_model, hints=hints,
                   voice_name=narrator_voice)

    plan = []
    for beat in spoken:
        frames = beat["frames"] or [0]
        each = max(MIN_FRAME_SECONDS, beat["seconds"] / len(frames))
        for frame in frames:
            plan.append((stills[(beat["page"], frame)], round(each, 4)))
        spent = each * len(frames)
        if beat["seconds"] > spent:
            plan.append((stills[(beat["page"], frames[-1])],
                         round(beat["seconds"] - spent, 4)))

    if progress:
        progress("assembling")
    result = assemble(plan, spoken, out_path)
    result["script"] = [{"text": b["text"], "seconds": b["seconds"]} for b in spoken]
    shutil.rmtree(folder, ignore_errors=True)
    return result
