"""MetaHuman / Unreal avatar adapter.

Unscripted owns *why* a character feels and says something; MetaHuman owns how
the face looks. This module is the deterministic bridge between the two. It maps
an :class:`~unscripted.affect.AffectState` (PAD mood + active OCC emotions) onto:

- **ARKit-52 blendshape weights** -- the Live Link Face standard MetaHuman
  consumes natively, so an Unreal plugin can stream the values straight onto a
  MetaHuman face with no per-character authoring.
- a compact **face summary** (dominant emotion, intensity, valence/arousal/dominance);
- **gaze** aversion (shame / low dominance / fear pull the eyes away);
- **prosody hints** (speech rate, pitch, loudness) for a downstream TTS / voice
  provider such as Convai, NVIDIA ACE or ElevenLabs;
- **posture** derived from Frijda action tendencies.

Everything here is pure and deterministic: identical affect in -> identical
packet out, so avatar output stays reproducible and replayable like the rest of
the runtime. No rendering, no network, no third-party dependency.
"""
from __future__ import annotations

from .affect import AffectState
from .types import clamp01

# ARKit-52 facial display templates per OCC emotion *family*, at full intensity.
# Weights are symmetric (left/right expanded below) and stay in [0, 1]. Names are
# the canonical ARKit / Live Link Face blendshape identifiers MetaHuman maps to.
# Each family is a recognisable display: smile, sadness, fear, anger, disgust.
_SMILE = {
    "mouthSmile": 0.85, "cheekSquint": 0.45, "eyeSquint": 0.30,
    "browInnerUp": 0.10, "mouthDimple": 0.30,
}
_SADNESS = {
    "mouthFrown": 0.70, "browInnerUp": 0.65, "eyeSquint": 0.20,
    "mouthShrugLower": 0.25, "mouthStretch": 0.15,
}
_FEAR = {
    "eyeWide": 0.80, "browInnerUp": 0.85, "browOuterUp": 0.55,
    "jawOpen": 0.30, "mouthStretch": 0.45,
}
_ANGER = {
    "browDown": 0.85, "noseSneer": 0.45, "eyeSquint": 0.40,
    "mouthPress": 0.55, "jawForward": 0.30,
}
_DISGUST = {
    "noseSneer": 0.80, "mouthFrown": 0.35, "browDown": 0.30,
    "mouthShrugUpper": 0.40,
}

# OCC emotion (base type, before any "@target" suffix) -> display template.
EMOTION_DISPLAY: dict[str, dict] = {
    # positive valence -> smile family
    "joy": _SMILE, "gratification": _SMILE, "hope": _SMILE, "relief": _SMILE,
    "admiration": _SMILE, "gratitude": _SMILE, "liking": _SMILE, "pride": _SMILE,
    # loss / negative valence, low arousal -> sadness family
    "distress": _SADNESS, "disappointment": _SADNESS,
    "shame": _SADNESS, "remorse": _SADNESS,
    # high-arousal threat -> fear family
    "fear": _FEAR,
    # high-arousal antagonism -> anger family
    "anger": _ANGER, "reproach": _ANGER,
    # aversion -> disgust family
    "disliking": _DISGUST,
}

# Canonical ARKit-52 expression keys this adapter can emit. The Unreal side can
# rely on this stable set; absent keys are simply 0.0.
ARKIT_KEYS = (
    "browInnerUp", "browDownLeft", "browDownRight", "browOuterUpLeft", "browOuterUpRight",
    "eyeWideLeft", "eyeWideRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeLookDownLeft", "eyeLookDownRight",
    "cheekSquintLeft", "cheekSquintRight", "noseSneerLeft", "noseSneerRight",
    "jawOpen", "jawForward",
    "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthPressLeft", "mouthPressRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthShrugUpper", "mouthShrugLower",
)

# Blendshape stems that exist as symmetric left/right pairs in ARKit.
_SYMMETRIC = {
    "browDown", "browOuterUp", "eyeWide", "eyeSquint", "eyeLookDown",
    "cheekSquint", "noseSneer", "mouthSmile", "mouthFrown", "mouthPress",
    "mouthStretch", "mouthDimple",
}


def _base(emotion_key: str) -> str:
    """Strip the target suffix: 'anger@player' -> 'anger'."""
    return emotion_key.split("@", 1)[0]


def _accumulate(weights: dict, stem: str, value: float) -> None:
    """Add a stem weight, expanding symmetric stems into left/right ARKit keys."""
    if stem in _SYMMETRIC:
        weights[stem + "Left"] = weights.get(stem + "Left", 0.0) + value
        weights[stem + "Right"] = weights.get(stem + "Right", 0.0) + value
    else:
        weights[stem] = weights.get(stem, 0.0) + value


def affect_to_blendshapes(affect: AffectState, *, precision: int = 4) -> dict:
    """Map an AffectState onto ARKit-52 blendshape weights in [0, 1].

    Active discrete emotions drive the bulk of the expression; the slow PAD mood
    supplies a resting expression that fills the remaining "expressive budget" so
    a neutral, calm character is not a frozen mask but a faint mood tint.
    """
    weights: dict[str, float] = {}

    total_emotion = 0.0
    for emotion_key, intensity in affect.active_emotions.items():
        intensity = clamp01(intensity)
        total_emotion += intensity
        template = EMOTION_DISPLAY.get(_base(emotion_key))
        if not template:
            continue
        for stem, w in template.items():
            _accumulate(weights, stem, w * intensity)

    # Resting mood tint, scaled down as discrete emotion fills the budget.
    headroom = clamp01(1.0 - total_emotion)
    p, a, d = affect.mood.p, affect.mood.a, affect.mood.d
    if p > 0:
        _accumulate(weights, "mouthSmile", 0.30 * p * headroom)
        _accumulate(weights, "cheekSquint", 0.15 * p * headroom)
    elif p < 0:
        _accumulate(weights, "mouthFrown", 0.30 * -p * headroom)
        _accumulate(weights, "browInnerUp", 0.25 * -p * headroom)
    if a > 0:  # alertness widens the eyes a touch
        _accumulate(weights, "eyeWide", 0.20 * a * headroom)
    if d < 0:  # low dominance -> submissive inner brow + lowered gaze
        _accumulate(weights, "browInnerUp", 0.20 * -d * headroom)
        _accumulate(weights, "eyeLookDown", 0.25 * -d * headroom)

    return {k: round(clamp01(v), precision) for k, v in sorted(weights.items()) if v > 0}


def dominant_emotion(affect: AffectState) -> tuple[str, float]:
    """Strongest active emotion (base type) and its intensity, else ('neutral', mood)."""
    best_type, best_intensity = "neutral", 0.0
    for emotion_key, intensity in affect.active_emotions.items():
        if intensity > best_intensity:
            best_type, best_intensity = _base(emotion_key), intensity
    if best_type == "neutral":
        # fall back to the sign of mood valence for a coarse resting label
        p = affect.mood.p
        if p > 0.15:
            return "content", round(min(1.0, p), 3)
        if p < -0.15:
            return "downcast", round(min(1.0, -p), 3)
    return best_type, round(best_intensity, 3)


def _gaze_aversion(affect: AffectState) -> float:
    """How strongly the character avoids eye contact, in [0, 1]."""
    shame = max((i for k, i in affect.active_emotions.items()
                 if _base(k) in ("shame", "remorse")), default=0.0)
    fear = max((i for k, i in affect.active_emotions.items()
                if _base(k) == "fear"), default=0.0)
    submissive = max(0.0, -affect.mood.d)
    return round(clamp01(0.9 * shame + 0.4 * fear + 0.35 * submissive), 4)


def _prosody(affect: AffectState) -> dict:
    """TTS prosody hints for a downstream voice provider (Convai / ACE / ElevenLabs)."""
    p, a = affect.mood.p, affect.mood.a
    return {
        # arousal speeds and lifts the voice; valence adds a gentler lift
        "speech_rate": round(1.0 + 0.30 * a, 3),
        "pitch_shift": round(0.18 * a + 0.10 * p, 3),
        "loudness": round(clamp01(0.5 + 0.35 * a), 3),
    }


# Frijda action-tendency classes (from AffectEngine.action_tendencies) -> posture.
_POSTURE_RULES = (
    ("aggressive", ("attack", "threaten", "confront", "sanction", "assert", "display")),
    ("retreat", ("flee", "hide", "withdraw", "conceal", "evade", "avoid", "seek_safety")),
    ("approach", ("affiliate", "approach", "help", "share", "cooperate", "lead")),
)


def _posture(action_tendencies: dict | None) -> str:
    """Pick a coarse body posture from the strongest action-tendency class."""
    if not action_tendencies:
        return "neutral"
    best_label, best_score = "neutral", 0.0
    for label, classes in _POSTURE_RULES:
        score = sum(max(0.0, action_tendencies.get(c, 0.0)) for c in classes)
        if score > best_score:
            best_label, best_score = label, score
    return best_label if best_score > 0.15 else "neutral"


def affect_to_face(affect: AffectState, *, action_tendencies: dict | None = None,
                   gaze_target: str | None = None) -> dict:
    """Full MetaHuman-ready face state for one character at the current instant."""
    dom_type, dom_intensity = dominant_emotion(affect)
    aversion = _gaze_aversion(affect)
    return {
        "emotion": {
            "dominant": dom_type,
            "intensity": dom_intensity,
            "valence": round(affect.mood.p, 4),
            "arousal": round(affect.mood.a, 4),
            "dominance": round(affect.mood.d, 4),
            "active": {_base(k): round(v, 3) for k, v in affect.active_emotions.items()},
        },
        "blendshapes": affect_to_blendshapes(affect),
        "gaze": {
            "target": gaze_target,
            "aversion": aversion,
            "make_contact": aversion < 0.35,
        },
        "prosody": _prosody(affect),
        "posture": _posture(action_tendencies),
    }


def build_avatar_packet(response, affect: AffectState, *,
                        action_tendencies: dict | None = None,
                        gaze_target: str | None = None) -> dict:
    """Combine a DialogueResponse with its speaker's face state.

    This is the single JSON object an Unreal/MetaHuman plugin needs per turn:
    *what* to say (validated text + act + verdict), *how it feels* (emotion +
    blendshapes + gaze + posture) and *how to voice it* (prosody hints).
    """
    face = affect_to_face(affect, action_tendencies=action_tendencies,
                          gaze_target=gaze_target or getattr(response, "addressee", None))
    # What the line COMMITTED to, and what it did to the world. An engine that
    # only receives text can render a talking face; with this it can show a
    # journal entry, mark a claim as heard by a bystander, or put a tell on a
    # character who just lied. All of it was reachable from Python only.
    spoken, honesty = [], "honest"
    for code, _magnitude, detail in (response.reasons or ()):
        for utterance in (detail.get("spoken") or ()) if isinstance(detail, dict) else ():
            spoken.append({"proposition": utterance.get("proposition"),
                           "text": utterance.get("rendered"),
                           "certainty": utterance.get("certainty"),
                           "honesty": utterance.get("honesty"),
                           "heard_by": list(utterance.get("heard_by") or ())})
            if utterance.get("honesty") not in (None, "honest"):
                honesty = utterance["honesty"]
    # A lie is what was SAID. This used to read the planned deception as well,
    # so a cover story the validator replaced with a deflection still came back
    # labelled a lie: a tell on a sentence that asserted nothing.

    return {
        "speaker_id": response.speaker_id,
        "text": response.text,
        "act": response.act,
        "verdict": response.verdict,
        "utility": response.utility,
        "style": response.style,
        "reasons": response.reasons,
        #: Whether this line was true to the speaker's own beliefs. A game may
        #: use it for a tell, for a detective mechanic, or not at all -- but it
        #: must not be inferred from the text, which is exactly the point.
        "honesty": honesty,
        #: The propositions this line actually asserted, and who overheard it.
        "asserted": spoken,
        **face,
    }
