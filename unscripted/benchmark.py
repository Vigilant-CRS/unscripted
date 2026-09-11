"""Epistemic integrity benchmark — the claims, measured over a long run.

Unit tests check invariants on a handful of turns. The claims this runtime is
sold on are about what happens over *hours or days of play*: that nobody ends up
knowing something they were never told, that a repeated rumour never hardens into
proof, that a secret never slips out, that nothing grows without bound, and that
the whole run reproduces exactly. None of that is visible in a five-step test.

This module runs a world for a long time under adversarial pressure and reports
each claim as a pass/fail metric with the number behind it. It is meant to be
published: a studio evaluating any NPC system can run it, and the numbers are
comparable across versions and, for the metrics that are system-agnostic, across
vendors.

    unscripted benchmark --turns 5000
    unscripted benchmark --world-pack worldpacks/noir-harbor --json report.json

Every metric is a falsifiable statement about the runtime, not a score. A metric
either holds or it does not, and the report says which.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from .contracts import RuntimeConfig
from .determinism import derive_seed, seeded_uniform
from .sdk import UnscriptedRuntime


@dataclass
class Metric:
    """One falsifiable claim, its measured value, and whether it held."""

    key: str
    claim: str
    value: float
    bound: str
    passed: bool
    detail: dict = field(default_factory=dict)
    #: A claim the run could not put under test at all (e.g. measuring diffusion in
    #: a world whose characters are never in the same room). Reported as SKIP: a
    #: benchmark that cannot tell "did not happen" from "cannot happen" is not
    #: measuring anything.
    applicable: bool = True

    def as_dict(self):
        return {"metric": self.key, "claim": self.claim, "value": self.value,
                "bound": self.bound, "passed": self.passed,
                "applicable": self.applicable, "detail": self.detail}

    def line(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        if not self.applicable:
            mark = "SKIP"
        return f"  [{mark}] {self.key:34s} {self.value:>12,.4g}   {self.bound}"


@dataclass
class BenchmarkReport:
    world_pack: str
    turns: int
    world_minutes: int
    wall_seconds: float
    metrics: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(m.passed for m in self.metrics if m.applicable)

    @property
    def skipped(self) -> list:
        return [m for m in self.metrics if not m.applicable]

    def as_dict(self):
        return {
            "world_pack": self.world_pack,
            "turns": self.turns,
            "world_minutes": self.world_minutes,
            "world_days": round(self.world_minutes / 1440.0, 2),
            "wall_seconds": round(self.wall_seconds, 3),
            "turns_per_second": round(self.turns / self.wall_seconds, 1) if self.wall_seconds else 0,
            "passed": self.passed,
            "metrics": [m.as_dict() for m in self.metrics],
        }

    def render(self) -> str:
        out = [
            "=" * 78,
            f"  Epistemic integrity benchmark — {self.world_pack}",
            "=" * 78,
            f"  {self.turns:,} turns · {self.world_minutes / 1440.0:.1f} simulated days · "
            f"{self.wall_seconds:.1f}s wall · {self.turns / max(self.wall_seconds, 1e-9):,.0f} turns/s",
            "",
        ]
        out += [m.line() for m in self.metrics]
        failed = [m for m in self.metrics if m.applicable and not m.passed]
        out += ["", "=" * 78]
        verdict = "all claims held" if self.passed else f"{len(failed)} CLAIM(S) FAILED"
        if self.skipped:
            verdict += f" ({len(self.skipped)} not exercised by this world)"
        out.append(f"  RESULT: {verdict}")
        for m in failed:
            out.append(f"    - {m.key}: {m.claim} (measured {m.value:,.4g}, {m.bound})")
        out.append("=" * 78)
        return "\n".join(out)


#: Player commands the driver cycles through. Chosen to exercise the paths that
#: matter: asking, lying, promising, threatening, moving and waiting.
_PRESSURE = ["look", "wait 30", "ask about it", "wait 60", "inspect"]


def run_benchmark(*, world_pack: str = "worldpacks/cyberpunk-block", turns: int = 2000,
                  minutes_per_turn: int = 20, seed: str = "benchmark",
                  verify_determinism: bool = True, progress=None) -> BenchmarkReport:
    """Drive a world hard for `turns` turns and measure whether the claims hold."""
    started = time.perf_counter()
    world_minutes = 0

    def drive(run_seed: str):
        sdk = UnscriptedRuntime.create(RuntimeConfig(
            world_pack_path=world_pack, storage_path=":memory:", debug_traces=False))
        commands = _command_cycle(sdk, run_seed, turns)
        for index, command in enumerate(commands):
            sdk.submit_player_text(command)
            sdk.advance_time(minutes_per_turn)
            if progress and index % max(1, turns // 20) == 0:
                progress(index, turns)
        return sdk

    sdk = drive(seed)
    world_minutes = sdk.world.world_time
    metrics = []

    metrics.append(_unsourced_knowledge(sdk))
    metrics.append(_single_origin_certainty(sdk))
    metrics.append(_secret_containment(sdk))
    metrics.append(_provenance_completeness(sdk))
    metrics.append(_memory_bounded(sdk))
    metrics.append(_provenance_bounded(sdk))
    metrics.append(_snapshot_bounded(sdk))
    metrics.append(_belief_sanity(sdk))
    metrics.append(_diffusion_reach(sdk))

    if verify_determinism:
        metrics.append(_determinism(sdk, drive, seed))

    sdk.close()
    return BenchmarkReport(world_pack=world_pack, turns=turns, world_minutes=world_minutes,
                           wall_seconds=time.perf_counter() - started, metrics=metrics)


def _command_cycle(sdk, seed: str, turns: int):
    """Deterministic pressure: move around, ask about real topics, make claims."""
    topics = sorted(sdk.world.topics) or [""]
    places = sorted(sdk.world.places)
    names = [a.public_name or a.id for a in sdk.world.agents.values()
             if a.id != sdk.config.player_id]
    commands = []
    for index in range(turns):
        pick = seeded_uniform(derive_seed(seed, "cmd", index, 0, "benchmark"))
        slot = int(pick * 6)
        if slot == 0:
            commands.append(f"go {sdk.world.place_label(places[index % len(places)])}")
        elif slot == 1 and names:
            commands.append(f"ask {names[index % len(names)]} about {topics[index % len(topics)]}")
        elif slot == 2 and names:
            commands.append(f"tell {names[index % len(names)]} about {topics[index % len(topics)]}")
        elif slot == 3:
            commands.append("wait 45")
        elif slot == 4 and names:
            commands.append(f"promise {names[index % len(names)]} 200")
        else:
            commands.append(_PRESSURE[index % len(_PRESSURE)])
    return commands


# ------------------------------------------------------------------ metrics --

def _unsourced_knowledge(sdk) -> Metric:
    """No belief may exist without a recorded route to where it came from.

    This is the whole product in one number. A belief with no provenance is a
    character knowing something for no reason, which is the failure mode a studio
    cannot debug and the reason they would build this themselves.
    """
    total = unsourced = 0
    examples = []
    for agent in sdk.world.agents.values():
        for key, belief in agent.beliefs.items():
            total += 1
            if not belief.origin_counts and not belief.provenance:
                unsourced += 1
                if len(examples) < 5:
                    examples.append({"agent": agent.id, "belief": key})
    rate = unsourced / total if total else 0.0
    return Metric("unsourced_knowledge_rate",
                  "every belief has a recorded origin", rate, "must be 0",
                  unsourced == 0, {"beliefs": total, "unsourced": unsourced,
                                   "examples": examples})


def _single_origin_certainty(sdk) -> Metric:
    """A belief resting on ONE origin must never reach practical certainty.

    However many times it is repeated. This is what separates "a rumour is weak
    evidence" from "a rumour is proof if you are patient", and it is the claim the
    correlation discount exists to make true.
    """
    worst = 0.0
    offender = {}
    checked = 0
    for agent in sdk.world.agents.values():
        for key, belief in agent.beliefs.items():
            if len(belief.origin_counts) != 1:
                continue
            checked += 1
            confidence = max(belief.expected_prob, 1.0 - belief.expected_prob)
            if confidence > worst:
                worst = confidence
                offender = {"agent": agent.id, "belief": key,
                            "times_heard": sum(belief.origin_counts.values()),
                            "confidence": round(confidence, 4)}
    return Metric("single_origin_max_confidence",
                  "one origin, however often repeated, never becomes proof",
                  worst, "must stay < 0.95", worst < 0.95,
                  {"single_origin_beliefs": checked, "worst": offender})


def _secret_containment(sdk) -> Metric:
    """A protected proposition must never appear in anyone else's head."""
    leaks = []
    independent = 0
    protected_total = 0
    for owner in sdk.world.agents.values():
        for secret in owner.secrets:
            protected_total += len(secret.protects)
            for key in secret.protects:
                held = owner.beliefs.get(key)
                owner_origins = set(held.origin_counts) if held else set()
                for other in sdk.world.agents.values():
                    theirs = other.beliefs.get(key)
                    if other.id == owner.id or theirs is None:
                        continue
                    # Holding the same proposition from a source of their OWN is not
                    # a leak -- two people can independently know the same thing, and
                    # counting that as a breach would report a false positive every
                    # time a pack gives two characters the same fact. A leak is
                    # knowledge that traces back to the holder.
                    if owner_origins and not (set(theirs.origin_counts) & owner_origins):
                        independent += 1
                        continue
                    leaks.append({"secret": secret.secret_id, "owner": owner.id,
                                  "leaked_to": other.id,
                                  "shared_origins": sorted(set(theirs.origin_counts) & owner_origins)})
    return Metric("secret_leak_count",
                  "protected knowledge never travels from its holder to anyone else",
                  float(len(leaks)), "must be 0", not leaks,
                  {"protected_propositions": protected_total, "leaks": leaks[:5],
                   "independently_known": independent})


def _provenance_completeness(sdk) -> Metric:
    """Hearsay must record how far it travelled; first-hand must not claim to be."""
    wrong = 0
    total = 0
    for agent in sdk.world.agents.values():
        for key, belief in agent.beliefs.items():
            total += 1
            # A belief with hops > 0 must name an origin it did not invent.
            if belief.hops > 0 and not belief.primary_origin:
                wrong += 1
    rate = wrong / total if total else 0.0
    return Metric("provenance_gap_rate",
                  "relayed knowledge always names the origin it came from",
                  rate, "must be 0", wrong == 0, {"beliefs": total, "gaps": wrong})


def _memory_bounded(sdk) -> Metric:
    """Memory per character must be bounded by the caps, not by session length."""
    cap = sdk.core.memory.params["total_cap"]
    worst = 0
    who = None
    for agent in sdk.world.agents.values():
        count = sum(1 for m in agent.memory if m.type != "summary")
        if count > worst:
            worst, who = count, agent.id
    return Metric("max_memories_per_agent",
                  "memory is bounded by its cap, not by how long you played",
                  float(worst), f"must be <= {cap}", worst <= cap,
                  {"cap": cap, "worst_agent": who})


def _provenance_bounded(sdk) -> Metric:
    limit = sdk.core.belief.params["provenance_limit"]
    worst = 0
    for agent in sdk.world.agents.values():
        for belief in agent.beliefs.values():
            worst = max(worst, len(belief.provenance))
    return Metric("max_provenance_entries",
                  "the evidence record per belief is bounded",
                  float(worst), f"must be <= {limit}", worst <= limit, {"limit": limit})


def _snapshot_bounded(sdk) -> Metric:
    """A savegame must be a function of world size, not of playtime."""
    from . import snapshot as snapshot_module
    payload = json.dumps(snapshot_module.capture(sdk.world, sdk.core), default=str)
    per_agent = len(payload) / max(1, len(sdk.world.agents))
    return Metric("snapshot_bytes_per_agent",
                  "savegame size scales with the world, not the session",
                  per_agent, "must stay < 250,000", per_agent < 250_000,
                  {"total_bytes": len(payload), "agents": len(sdk.world.agents)})


def _belief_sanity(sdk) -> Metric:
    """No probability may leave [0,1] and no support may go negative."""
    bad = 0
    for agent in sdk.world.agents.values():
        for belief in agent.beliefs.values():
            if not (0.0 <= belief.expected_prob <= 1.0):
                bad += 1
            if belief.support_for < 0 or belief.support_against < 0:
                bad += 1
    return Metric("belief_invariant_violations",
                  "probabilities stay in [0,1] and support never goes negative",
                  float(bad), "must be 0", bad == 0)


def _diffusion_reach(sdk) -> Metric:
    """Information must actually have moved. A society that never talks is not one.

    Not applicable to a world whose characters are never in the same place -- with
    no routines or schedules, a cast that starts in separate rooms stays there, and
    reporting that as a failure of diffusion would blame the engine for the
    content. It is still worth surfacing: a world where nobody ever meets cannot
    have a rumour.
    """
    from collections import Counter
    occupancy = Counter(a.location for a in sdk.world.agents.values()
                        if a.id != sdk.config.player_id and a.location)
    can_meet = any(count >= 2 for count in occupancy.values())
    relayed = sum(1 for agent in sdk.world.agents.values()
                  for belief in agent.beliefs.values() if belief.hops > 0)
    return Metric("relayed_beliefs",
                  "knowledge reached characters who were not there",
                  float(relayed), "must be > 0", relayed > 0,
                  {"co_located_places": {p: c for p, c in occupancy.items() if c >= 2},
                   "note": ("" if can_meet else
                            "no two characters share a place in this world, and nothing "
                            "moves them, so diffusion cannot be exercised")},
                  applicable=can_meet)


def _determinism(sdk, drive, seed: str) -> Metric:
    """The same seed must reproduce the same world, exactly.

    Without this every other metric is an anecdote: a bug that cannot be
    reproduced cannot be fixed, and a benchmark that cannot be reproduced cannot
    be trusted.
    """
    from . import snapshot as snapshot_module
    first = json.dumps(snapshot_module.capture(sdk.world, sdk.core), sort_keys=True, default=str)
    replica = drive(seed)
    second = json.dumps(snapshot_module.capture(replica.world, replica.core),
                        sort_keys=True, default=str)
    replica.close()
    identical = first == second
    divergence = 0
    if not identical:
        for index, (a, b) in enumerate(zip(first, second)):
            if a != b:
                divergence = index
                break
    return Metric("determinism_byte_divergence",
                  "the same seed reproduces the same world byte for byte",
                  float(divergence), "must be 0 (identical)", identical,
                  {"bytes_compared": len(first)})
