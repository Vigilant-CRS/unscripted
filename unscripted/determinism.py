"""Deterministic seeding (spec v0.5 §1, §7.4).

No module may call a global RNG. Every stochastic draw derives its seed from
(global_seed, agent_id, event_id, world_time, module_id, salt) so that
ReplayScenario(seed) reproduces byte-identical traces.
"""
from __future__ import annotations
import hashlib


def derive_seed(global_seed, agent_id, event_id, world_time, module_id, salt: str = "") -> bytes:
    key = f"{global_seed}|{agent_id}|{event_id}|{world_time}|{module_id}|{salt}".encode()
    return hashlib.blake2b(key, digest_size=16).digest()


def seeded_uniform(seed: bytes) -> float:
    """Map a seed to a uniform float in [0, 1)."""
    return int.from_bytes(seed[:8], "big") / 2 ** 64


def seeded_choice(seed: bytes, weights):
    """Weighted choice over indices given a seed. weights need not be normalized."""
    total = float(sum(weights))
    if total <= 0:
        return 0
    r = seeded_uniform(seed) * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return i
    return len(weights) - 1
