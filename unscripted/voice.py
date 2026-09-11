"""Prosody into a voice, without the runtime learning to synthesise anything.

The runtime has emitted prosody on every spoken line since the MetaHuman adapter
was written -- speech rate, pitch shift and loudness, derived from the speaker's
affect, so a frightened character reads faster and higher and a dominant one
slower and lower. Nothing consumed it. `capabilities.tts` reported false and
`CONCEPT.md` listed "no voice" among the gaps, while the interesting half of the
problem -- *what should this line sound like, and why* -- was already solved and
sitting unused.

This module is the other half, and it is deliberately thin. It does not
synthesise; it decides what the synthesis should do and hands that to whatever is
installed. Three reasons the split is here rather than a dependency:

**The SDK stays dependency-free.** Every practical Python TTS pulls in
onnxruntime or torch. The runtime promises an install with no third-party
packages and that promise is worth more than a bundled voice.

**Backends are replaceable and none of them is right for everyone.** A studio
with an ElevenLabs contract, a studio shipping offline, and a developer who wants
a voice in the next ten seconds need three different answers to the same request.

**The mapping is the part worth owning.** Which prosody a frightened lie gets is
a claim about the runtime; turning numbers into a waveform is not.

So: the runtime produces a `VoicePlan`, and a backend turns it into audio. What
each backend can and cannot honour is stated rather than smoothed over --
`espeak-ng` takes rate, pitch and volume exactly, and `piper` has no pitch
control at all, which costs an emotional read half its signal. A build says which
it has; it does not pretend.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass, field

#: Backends this module knows how to drive.
#:
#: `espeak-ng` is robotic and honours every parameter. `piper` sounds far better
#: and cannot change pitch. `kokoro` is better again -- 24 kHz, and the only one
#: of the three whose intonation sounds like somebody meaning something -- and it
#: cannot change pitch either. That trade is the whole choice, and it belongs to
#: the person shipping the game rather than to this file.
#:
#: None of them is bundled. Every practical Python TTS pulls in onnxruntime or
#: torch, and the install promise is worth more than a bundled voice, so each is
#: reached the same way: a name on PATH.
BACKENDS = ("espeak-ng", "piper", "kokoro", "none")

#: espeak-ng's own defaults, which the mapping is expressed relative to.
ESPEAK_BASE_WPM = 175
ESPEAK_BASE_PITCH = 50
ESPEAK_BASE_AMPLITUDE = 100


class VoiceError(RuntimeError):
    """Synthesis was asked for and could not be done."""


@dataclass
class VoicePlan:
    """What a line should sound like, before any particular synthesiser sees it."""
    agent_id: str
    text: str
    #: Multiplier on ordinary speaking rate. 1.0 is neutral.
    rate: float = 1.0
    #: Semitone-ish shift, roughly [-0.5, +0.5]. Positive is higher.
    pitch: float = 0.0
    #: [0, 1].
    loudness: float = 0.5
    #: The character's own voice, before this line's emotion moved it.
    base_pitch: float = 0.0
    base_rate: float = 1.0
    voice_name: str = ""
    #: Carried for the record, never for the synthesis: two lines that sound the
    #: same for different reasons are a thing a debug HUD should be able to show.
    emotion: str = ""
    honesty: str = ""

    def as_dict(self) -> dict:
        return {"agent_id": self.agent_id, "text": self.text,
                "rate": round(self.rate, 3), "pitch": round(self.pitch, 3),
                "loudness": round(self.loudness, 3), "voice": self.voice_name,
                "emotion": self.emotion, "honesty": self.honesty}


def respell(text: str, hints: dict) -> str:
    """Rewrite names a synthesiser says wrongly, for the synthesiser only.

    Piper reads "Okada" as OH-kay-da and "Honce" as HONSS-ee. On a page that does
    not matter; spoken over a video for a studio it is the first thing anybody
    notices, and it makes the whole thing sound like it was assembled carelessly.

    The rewrite is applied to the text handed to the synthesiser and NOWHERE
    else: the world keeps its spelling, the transcript keeps its spelling, and a
    respelling never reaches a page or a log. Hints are authored per character in
    the world pack (`"voice": {"say_as": "..."}`), because how a name is said is
    a fact about the world and not about this runtime.
    """
    if not hints:
        return text
    # Longest first, so "Mr. Okada" wins over "Okada" when both are declared.
    for spelling in sorted(hints, key=len, reverse=True):
        said = hints[spelling]
        if spelling and said and spelling in text:
            text = text.replace(spelling, said)
    return text


@dataclass
class VoiceProfile:
    """A character's standing voice: what they sound like when nothing is wrong.

    Authored in the world pack when it matters, derived from the character id
    when it does not. Derived rather than random because ten characters who all
    sound identical is worse than any particular assignment, and because the same
    character must sound the same in every session -- a voice that changes between
    runs is a continuity bug the player will notice before any belief state.
    """
    pitch: float = 0.0
    rate: float = 1.0
    voice_name: str = ""
    #: How the character's name should be pronounced, if the pack says.
    say_as: str = ""

    @classmethod
    def for_agent(cls, agent_id: str, authored: dict | None = None) -> "VoiceProfile":
        authored = authored or {}
        digest = hashlib.sha256(agent_id.encode("utf-8")).digest()
        # Spread across a range a listener can tell apart without anybody sounding
        # like a cartoon: +-0.22 of pitch and +-8% of rate.
        pitch = (digest[0] / 255.0 - 0.5) * 0.44
        rate = 1.0 + (digest[1] / 255.0 - 0.5) * 0.16
        return cls(pitch=float(authored.get("pitch", round(pitch, 3))),
                   rate=float(authored.get("rate", round(rate, 3))),
                   voice_name=str(authored.get("voice", "")),
                   say_as=str(authored.get("say_as", "")))


def plan_from_avatar(packet: dict, *, profile: VoiceProfile | None = None) -> VoicePlan:
    """Turn an avatar turn into a voice plan.

    The prosody in the packet is the *emotional* movement; the profile is who the
    character is. They compose: a frightened baritone is still a baritone.
    """
    prosody = packet.get("prosody") or {}
    emotion = (packet.get("emotion") or {}).get("dominant", "")
    profile = profile or VoiceProfile.for_agent(packet.get("speaker_id", "agent:?"))
    return VoicePlan(
        agent_id=packet.get("speaker_id", "agent:?"),
        text=(packet.get("text") or "").strip(),
        rate=float(prosody.get("speech_rate", 1.0)) * profile.rate,
        pitch=float(prosody.get("pitch_shift", 0.0)) + profile.pitch,
        loudness=float(prosody.get("loudness", 0.5)),
        base_pitch=profile.pitch, base_rate=profile.rate,
        voice_name=profile.voice_name,
        emotion=emotion, honesty=packet.get("honesty", ""))


# ---------------------------------------------------------------- backends ----

def available() -> dict:
    """Which backends this machine can actually run, right now."""
    return {"espeak-ng": bool(shutil.which("espeak-ng") or shutil.which("espeak")),
            "piper": bool(shutil.which("piper") or shutil.which("piper-tts")),
            "kokoro": bool(shutil.which("kokoro-say")),
            "none": True}


#: What each backend is able to honour. Stated so a report can say what was lost
#: rather than producing a flat read and calling it the character's voice.
HONOURS = {
    "espeak-ng": ("rate", "pitch", "loudness"),
    "piper": ("rate",),
    "kokoro": ("rate", "voice"),
    "none": (),
}


def command(backend: str, plan: VoicePlan, out_path: str, *,
            model: str | None = None) -> list:
    """The argv that renders this plan to a WAV file.

    Separated from running it so the mapping can be tested on a machine with no
    synthesiser installed at all -- which is most machines, including the one this
    was written on.
    """
    if backend not in BACKENDS:
        raise VoiceError(f"unknown backend {backend!r}. Known: {', '.join(BACKENDS)}")
    if backend == "none":
        raise VoiceError("backend 'none' renders nothing by design")

    if backend == "espeak-ng":
        binary = shutil.which("espeak-ng") or shutil.which("espeak") or "espeak-ng"
        speed = int(round(ESPEAK_BASE_WPM * plan.rate))
        # espeak takes pitch 0-99 and amplitude 0-200; both are clamped rather
        # than scaled, so an extreme affect state cannot silence a character or
        # push them out of the range and wrap around.
        pitch = int(round(ESPEAK_BASE_PITCH + 50.0 * plan.pitch))
        amplitude = int(round(2 * ESPEAK_BASE_AMPLITUDE * plan.loudness))
        argv = [binary,
                "-s", str(max(80, min(450, speed))),
                "-p", str(max(0, min(99, pitch))),
                "-a", str(max(0, min(200, amplitude))),
                "-w", out_path]
        if plan.voice_name:
            argv[1:1] = ["-v", plan.voice_name]
        return argv + [plan.text]

    if backend == "kokoro":
        binary = shutil.which("kokoro-say") or "kokoro-say"
        if not model:
            raise VoiceError("kokoro needs a voice model: pass --model "
                             "path/to/kokoro-v1.0.onnx")
        # The voice bank sits beside the model in every distribution of it, so
        # asking for both would be asking twice for one thing.
        voices = os.path.join(os.path.dirname(os.path.abspath(model)),
                              "voices-v1.0.bin")
        argv = [binary, "--model", model, "--voices", voices,
                "--out", out_path,
                # Kokoro takes a speed multiplier directly, which is our rate.
                "--speed", f"{max(0.5, min(2.0, plan.rate)):.3f}"]
        if plan.voice_name:
            argv += ["--voice", plan.voice_name]
        return argv

    binary = shutil.which("piper") or shutil.which("piper-tts") or "piper"
    if not model:
        raise VoiceError("piper needs a voice model: pass --model path/to/voice.onnx")
    # piper's length_scale is time per unit, so it is the inverse of rate. Pitch
    # is not exposed at all: the emotional lift is simply lost, and the report
    # says so rather than leaving somebody to wonder why fear sounds calm.
    return [binary, "--model", model, "--output_file", out_path,
            "--length_scale", f"{1.0 / max(0.35, plan.rate):.3f}"]


#: A high-quality piper voice runs at roughly 0.05x real time, so a long
#: narration line costs seconds rather than milliseconds. Thirty was enough until
#: the lines got long enough to be worth listening to.
SYNTHESIS_TIMEOUT = 180.0


def synthesize(plan: VoicePlan, out_path: str, *, backend: str = "espeak-ng",
               model: str | None = None, timeout: float = SYNTHESIS_TIMEOUT,
               hints: dict | None = None) -> dict:
    """Render one line. Returns what was rendered and what the backend dropped.

    `hints` respell names for the synthesiser only; the plan keeps its own text,
    so what is reported and logged is what was actually meant to be said.
    """
    if backend == "none":
        return {"path": None, "rendered": False, "backend": backend,
                "lost": ("rate", "pitch", "loudness"), "plan": plan.as_dict()}
    if not plan.text:
        return {"path": None, "rendered": False, "backend": backend,
                "lost": (), "plan": plan.as_dict(),
                "note": "nothing was said this turn"}

    spoken = plan
    if hints:
        spoken = VoicePlan(**{**plan.__dict__, "text": respell(plan.text, hints)})
    argv = command(backend, spoken, out_path, model=model)
    if not shutil.which(argv[0]):
        raise VoiceError(
            f"{argv[0]} is not installed. `espeak-ng` is one apt/brew package and "
            f"honours rate, pitch and loudness; `piper` sounds better and cannot "
            f"change pitch. Or run with --backend none to see the plans without "
            f"rendering them.")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    try:
        completed = subprocess.run(
            argv, capture_output=True, timeout=timeout,
            input=(spoken.text.encode("utf-8")
                   if backend in ("piper", "kokoro") else None))
    except subprocess.TimeoutExpired as exc:
        raise VoiceError(f"{argv[0]} did not finish in {timeout}s") from exc
    if completed.returncode != 0:
        raise VoiceError(f"{argv[0]} failed: "
                         f"{completed.stderr.decode('utf-8', 'replace')[:300]}")
    return {"path": out_path, "rendered": True, "backend": backend,
            "lost": tuple(p for p in ("rate", "pitch", "loudness")
                          if p not in HONOURS[backend]),
            "plan": plan.as_dict()}


def describe(plan: VoicePlan, backend: str) -> str:
    """One line a person can read: what this should sound like, and what survives."""
    lost = [p for p in ("rate", "pitch", "loudness") if p not in HONOURS.get(backend, ())]
    faster = "faster" if plan.rate > 1.03 else ("slower" if plan.rate < 0.97 else "even")
    higher = "higher" if plan.pitch > 0.03 else ("lower" if plan.pitch < -0.03 else "level")
    line = (f"{plan.agent_id}: {faster}, {higher}, "
            f"{'loud' if plan.loudness > 0.65 else 'quiet' if plan.loudness < 0.4 else 'ordinary'}"
            f"{' (' + plan.emotion + ')' if plan.emotion else ''}")
    if lost:
        line += f" — {backend} cannot honour {', '.join(lost)}"
    return line
