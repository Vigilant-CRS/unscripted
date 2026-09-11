"""Numeric types and helpers (spec v0.5 §1).

unit_interval [0,1] for intensities; signed_unit [-1,1] for bipolar values
(valence, dominance, liking); probability [0,1] for confidences.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def clamp01(x: float) -> float:
    return clamp(x, 0.0, 1.0)


def clamp_signed(x: float) -> float:
    return clamp(x, -1.0, 1.0)


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logit(p: float, eps: float = 1e-6) -> float:
    p = clamp(p, eps, 1.0 - eps)
    return math.log(p / (1.0 - p))


@dataclass
class Vec3:
    """PAD vector (Pleasure/valence, Arousal, Dominance), each in [-1, 1]."""
    p: float = 0.0
    a: float = 0.0
    d: float = 0.0

    def add(self, o: "Vec3") -> "Vec3":
        return Vec3(self.p + o.p, self.a + o.a, self.d + o.d)

    def scale(self, k: float) -> "Vec3":
        return Vec3(self.p * k, self.a * k, self.d * k)

    def clamped(self) -> "Vec3":
        return Vec3(clamp_signed(self.p), clamp_signed(self.a), clamp_signed(self.d))

    def as_dict(self):
        # full precision for persistence (reproduction must be exact; display rounds separately)
        return {"valence": self.p, "arousal": self.a, "dominance": self.d}

    @staticmethod
    def from_dict(d):
        return Vec3(d.get("valence", 0.0), d.get("arousal", 0.0), d.get("dominance", 0.0))
