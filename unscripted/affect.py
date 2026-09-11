"""AffectEngine -- Part A of the dynamics spec (v0.5 §2).

ALMA-based: personality sets the PAD mood baseline, OCC appraisal produces
discrete emotions, emotions push the PAD vector, mood is the slow PAD integral,
emotions decay fast, and active emotions produce Frijda action tendencies.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from .types import Vec3, clamp_signed, clamp01


# emotion -> PAD impulse direction (Mehrabian octants), spec v0.5 §2.4
EMOTION_PAD = {
    "joy": Vec3(1.0, 0.3, 0.3), "gratification": Vec3(1.0, 0.3, 0.3),
    "hope": Vec3(1.0, 0.2, 0.1), "relief": Vec3(1.0, 0.2, 0.1),
    "pride": Vec3(1.0, 0.4, 0.6),
    "admiration": Vec3(1.0, 0.2, -0.1), "gratitude": Vec3(1.0, 0.2, -0.1), "liking": Vec3(1.0, 0.2, -0.1),
    "distress": Vec3(-1.0, -0.2, -0.4), "disappointment": Vec3(-1.0, -0.2, -0.4),
    "shame": Vec3(-1.0, -0.1, -0.6), "remorse": Vec3(-1.0, -0.1, -0.6),
    "fear": Vec3(-1.0, 0.6, -0.7),
    "anger": Vec3(-1.0, 0.6, 0.5), "reproach": Vec3(-1.0, 0.6, 0.5),
    "disliking": Vec3(-0.6, 0.1, 0.1),
}

# emotion -> action-class bias (Frijda), spec v0.5 §2.7
ACTION_TENDENCIES = {
    "fear":   {"flee": 1.0, "hide": 0.8, "comply": 0.6, "seek_safety": 0.8, "approach": -0.7, "attack": -0.8, "evade": 0.6},
    "anger":  {"attack": 1.0, "threaten": 0.9, "confront": 0.8, "comply": -0.6, "affiliate": -0.7},
    "joy":    {"affiliate": 0.9, "help": 0.7, "share": 0.7, "cooperate": 0.8},
    "gratitude": {"help": 0.9, "affiliate": 0.7, "cooperate": 0.6},
    "distress": {"withdraw": 0.8, "wait": 0.5, "initiate": -0.6},
    "pride":  {"assert": 0.8, "display": 0.7, "lead": 0.6},
    "shame":  {"withdraw": 0.8, "conceal": 0.9, "repair_face": 0.7, "evade": 0.5},
    "liking": {"approach": 0.8, "help": 0.6},
    "disliking": {"avoid": 0.7, "sanction": 0.6},
    "reproach": {"sanction": 0.7, "avoid": 0.5},
}


@dataclass
class AffectState:
    mood: Vec3 = field(default_factory=Vec3)
    baseline: Vec3 = field(default_factory=Vec3)
    active_emotions: dict = field(default_factory=dict)   # type -> intensity

    def as_dict(self):
        # Full precision: this is the persistence shape, and rounding here would make
        # a save/load round-trip lossy. Display code rounds separately.
        return {"mood": self.mood.as_dict(), "baseline": self.baseline.as_dict(),
                "active_emotions": dict(self.active_emotions)}

    @staticmethod
    def from_dict(d: dict) -> "AffectState":
        return AffectState(mood=Vec3.from_dict(d["mood"]),
                           baseline=Vec3.from_dict(d["baseline"]),
                           active_emotions=dict(d.get("active_emotions", {})))


def pad_baseline_from_big_five(b: dict) -> Vec3:
    """Mehrabian/ALMA linear map (spec v0.5 §2.2). Traits in [0,1] -> converted to [-1,1].
    Coefficients are calibration defaults; verify against ALMA before freezing."""
    O = 2 * b.get("openness", 0.5) - 1
    C = 2 * b.get("conscientiousness", 0.5) - 1
    E = 2 * b.get("extraversion", 0.5) - 1
    A = 2 * b.get("agreeableness", 0.5) - 1
    S = 2 * b.get("emotional_stability", 0.5) - 1
    # THE SIGN CONVENTION, WRITTEN DOWN BECAUSE IT IS NOT OBVIOUS AND WAS
    # DESCRIBED WRONG. The commonly cited ALMA/Mehrabian arousal equation is
    # `0.15*O + 0.30*A - 0.57*N`. The input here is EMOTIONAL STABILITY, which is
    # `-N`, so `-0.57*(-S)` is `+0.57*S` -- and the arithmetic below is faithful
    # to that source. The comment used to read "instability raises arousal",
    # which is the opposite of what both the source and this line say.
    #
    # Secondary sources disagree about this sign, so it is not treated as
    # grounded: `docs/CALIBRATION.md` marks the mapping literature-derived and the
    # coefficients authored, and `test_the_pad_baseline_states_its_sign_convention`
    # pins the direction so it cannot drift silently in either direction.
    P = 0.21 * E + 0.59 * A + 0.19 * S
    Ar = 0.15 * O + 0.30 * A - 0.57 * (-S)     # == +0.57*S; S = -N, see above
    D = 0.25 * O + 0.17 * C + 0.60 * E - 0.32 * A
    return Vec3(clamp_signed(P), clamp_signed(Ar), clamp_signed(D))


class AffectEngine:
    module_id = "affect"
    version = "0.5.0"

    def __init__(self, params=None):
        self.params = {"k_impulse": 0.6, "tau_mood": 240.0, "tau_emotion": 30.0, "epsilon": 0.05}
        if params:
            self.params.update(params)

    # ---- appraisal -> emotions (OCC table subset, spec v0.5 §2.3) ----
    def appraise(self, appraisal: dict):
        """appraisal dict may carry: desirability [-1,1], agency 'self'/'other'/'none',
        praiseworthiness [-1,1], expectedness [0,1], prospect 'confirmed'/'disconfirmed'/None,
        attraction [-1,1], prior_fear, prior_hope. Returns list of (emotion, intensity)."""
        out = []
        des = appraisal.get("desirability")
        agency = appraisal.get("agency", "none")
        praise = appraisal.get("praiseworthiness")
        expect = appraisal.get("expectedness", 0.5)
        uncertainty = 1.0 - expect
        prospect = appraisal.get("prospect")
        attr = appraisal.get("attraction")

        # THE PROSPECT PAIR, IN THE DIRECTION OCC ACTUALLY STATES IT. Relief is
        # what follows a feared event NOT happening; a feared event that does
        # happen is fears-confirmed, which is a distress-family emotion. This was
        # the wrong way round -- `confirmed` produced relief -- so a character
        # whose worst expectation came true cheered up.
        #
        # The four cases use the existing emotion vocabulary rather than adding
        # `fears_confirmed` and `satisfaction` as names of their own: those two
        # sit in the distress and joy families, everything downstream (PAD
        # impulse, action tendencies, blendshapes) is keyed on that vocabulary,
        # and a name nothing can render is worse than the family it belongs to.
        if prospect == "disconfirmed" and appraisal.get("prior_fear"):
            out.append(("relief", appraisal["prior_fear"]))
        if prospect == "confirmed" and appraisal.get("prior_fear"):
            out.append(("distress", appraisal["prior_fear"]))       # fears-confirmed
        if prospect == "disconfirmed" and appraisal.get("prior_hope"):
            out.append(("disappointment", appraisal["prior_hope"]))
        if prospect == "confirmed" and appraisal.get("prior_hope"):
            out.append(("joy", appraisal["prior_hope"]))             # satisfaction

        if des is not None:
            if prospect is None and uncertainty > 0.3 and des > 0:
                out.append(("hope", des * uncertainty))
            if prospect is None and uncertainty > 0.3 and des < 0:
                out.append(("fear", -des * uncertainty))
            # well-being
            if des > 0:
                out.append(("joy", des))
            elif des < 0:
                out.append(("distress", -des))

        if praise is not None and agency == "self":
            out.append(("pride" if praise > 0 else "shame", abs(praise)))
        if praise is not None and agency == "other":
            out.append(("admiration" if praise > 0 else "reproach", abs(praise)))

        # compound (gratitude/anger/gratification/remorse)
        if des is not None and praise is not None and agency == "other":
            if des > 0 and praise > 0:
                out.append(("gratitude", min(1.0, des * praise + 0.2)))
            if des < 0 and praise < 0:
                out.append(("anger", min(1.0, (-des) * (-praise) + 0.2)))

        if attr is not None:
            out.append(("liking" if attr > 0 else "disliking", abs(attr)))

        # merge duplicates, cap intensity
        merged = {}
        for emo, inten in out:
            merged[emo] = clamp01(max(merged.get(emo, 0.0), inten))
        return list(merged.items())

    def update(self, state: AffectState, appraisal: dict, dt: float):
        """Appraise -> impulses, decay existing emotions, relax mood. Returns (impulse_emotions, reasons)."""
        reasons = []
        target = appraisal.get("target") if appraisal else None
        new_emotions = self.appraise(appraisal) if appraisal else []
        impulse = Vec3()
        for emo, inten in new_emotions:
            # target-aware emotion key (review P0.7): "anger@player" != "anger@police"
            key = emo if target is None else f"{emo}@{target}"
            state.active_emotions[key] = clamp01(max(state.active_emotions.get(key, 0.0), inten))
            direction = EMOTION_PAD.get(emo, Vec3())
            impulse = impulse.add(direction.scale(inten * self.params["k_impulse"]))
            reasons.append(("affect.emotion_fired", round(inten, 3), {"emotion": emo, "target": target}))

        # decay existing emotions
        decayed = {}
        for emo, inten in state.active_emotions.items():
            v = inten * math.exp(-dt / self.params["tau_emotion"])
            if v >= self.params["epsilon"]:
                decayed[emo] = v
        state.active_emotions = decayed

        # mood relaxation toward baseline + impulses
        # exact exponential relaxation (review P0.9): alpha = 1 - exp(-dt/tau), t_half = tau*ln2
        homing = (1.0 - math.exp(-dt / self.params["tau_mood"])) if dt > 0 else 0.0
        toward = state.baseline.add(state.mood.scale(-1)).scale(homing)
        relaxed = state.mood.add(toward)
        # soft saturation (review P0): impulse pushes less the closer mood is to the rail,
        # so a single strong event can no longer slam valence/arousal/dominance to +/-1.
        # impulse_component *= (1 - |mood_component|); mood approaches the rail asymptotically.
        soft = Vec3(
            impulse.p * (1.0 - abs(relaxed.p)),
            impulse.a * (1.0 - abs(relaxed.a)),
            impulse.d * (1.0 - abs(relaxed.d)),
        )
        state.mood = relaxed.add(soft).clamped()
        if impulse.p or impulse.a or impulse.d:
            reasons.append(("affect.mood_shift", round(impulse.p, 3),
                            {"pad": state.mood.as_dict()}))
        return new_emotions, reasons

    def decay(self, state: AffectState, dt: float):
        """Periodic affect decay when no event (spec §6.3)."""
        return self.update(state, {}, dt)

    def action_tendencies(self, state: AffectState) -> dict:
        """Aggregate action-class bias from active emotions (spec §2.7)."""
        bias = {}
        for emo, inten in state.active_emotions.items():
            base = emo.split("@")[0]
            for cls, w in ACTION_TENDENCIES.get(base, {}).items():
                bias[cls] = bias.get(cls, 0.0) + inten * w
        return {k: round(clamp_signed(v), 3) for k, v in bias.items()}

    @staticmethod
    def emotions_toward(state: AffectState, target: str) -> dict:
        """Emotions directed at a specific target -> {base_type: intensity} (review P0.7)."""
        out = {}
        suffix = "@" + target
        for k, v in state.active_emotions.items():
            if k.endswith(suffix):
                out[k.split("@")[0]] = v
        return out

    def stress(self, state: AffectState) -> float:
        """stress = arousal * max(0, -valence)  (spec §2.8)."""
        return clamp01(state.mood.a * max(0.0, -state.mood.p))
