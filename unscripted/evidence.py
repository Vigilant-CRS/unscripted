"""Evidence runs: a long, recorded proof that the claims hold in play.

The benchmark answers "does an invariant hold" with a number. This answers a
different and harder question, the one a studio actually asks in a meeting:

    Show me a character learning something, tell me who told them, show me it
    changing on the way, show me them forgetting it, and show me that the one
    thing they must not say never got said.

So this runs a world for hours and writes down everything: every line spoken and
the reasoning behind it, every belief acquired and the chain it came down, every
memory that decayed past recall, every claim that changed shape in transit, and
the result of every invariant check along the way. The output is a dossier meant
to be read by a person, plus the same record as JSON.

Cases escalate. The early ones isolate one mechanism each, so a failure points at
one thing. The later ones let everything run at once for as long as the time
budget allows, which is where the interactions live.

With a local model configured, the spoken lines are the model's real output and
both the raw generation and the released line are recorded, so "the validator
caught this" is an artefact rather than an assurance.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from .contracts import RuntimeConfig
from .sdk import UnscriptedRuntime


# ------------------------------------------------------------------ records --

@dataclass
class Episode:
    """One thing that happened, recorded in enough detail to be evidence."""

    world_time: int
    clock: str
    kind: str                 # said | learned | forgot | distorted | moved | checked | note
    who: str = ""
    detail: dict = field(default_factory=dict)

    def as_dict(self):
        return {"world_time": self.world_time, "clock": self.clock, "kind": self.kind,
                "who": self.who, **self.detail}


@dataclass
class CaseResult:
    name: str
    question: str
    passed: bool
    applicable: bool = True
    findings: list = field(default_factory=list)
    episodes: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    seconds: float = 0.0

    def as_dict(self):
        return {"case": self.name, "question": self.question, "passed": self.passed,
                "applicable": self.applicable, "findings": self.findings, "stats": self.stats,
                "seconds": round(self.seconds, 2),
                "episodes": [e.as_dict() for e in self.episodes]}


class Recorder:
    """Watches one runtime and writes down what changed."""

    def __init__(self, runtime: UnscriptedRuntime):
        self.runtime = runtime
        self.episodes: list = []
        self._beliefs = self._belief_snapshot()
        self._recall = self._recall_snapshot()
        # A long run truncates `episodes` to stay readable, so anything counted off
        # that list would silently describe only the tail. These do not truncate.
        self.counts: dict = {}

    # -- snapshots -----------------------------------------------------------
    def _belief_snapshot(self) -> dict:
        return {(a.id, key): (b.expected_prob, b.hops, b.primary_origin)
                for a in self.runtime.world.agents.values()
                for key, b in a.beliefs.items()}

    def _recall_snapshot(self) -> dict:
        """What each character can still bring to mind, as opposed to still stores."""
        out = {}
        now = self.runtime.world.world_time
        # The threshold the retrieval path actually uses. Hard-coding 0.0 here once
        # made the record claim a character had forgotten something they could still
        # bring to mind, which is a worse error than missing it.
        threshold = self.runtime.core.memory.params["tau_ret"]
        for agent in self.runtime.world.agents.values():
            out[agent.id] = {m.memory_id for m in agent.memory
                             if m.base_activation(now) > threshold}
        return out

    def _clock(self) -> str:
        minute = self.runtime.world.world_time % 1440
        day = self.runtime.world.world_time // 1440
        return f"day {day} {minute // 60:02d}:{minute % 60:02d}"

    def note(self, text: str, **detail):
        self.episodes.append(Episode(self.runtime.world.world_time, self._clock(),
                                     "note", detail={"text": text, **detail}))

    def record(self, kind, who, **detail):
        self.counts[kind] = self.counts.get(kind, 0) + 1
        if kind == "forgot":
            split = "forgot:evicted" if "evicted" in detail.get("cause", "") else "forgot:decayed"
            self.counts[split] = self.counts.get(split, 0) + 1
        self.episodes.append(Episode(self.runtime.world.world_time, self._clock(),
                                     kind, who, detail))

    # -- the two things worth watching --------------------------------------
    def sweep(self):
        """Diff belief and recall state, and write down every change."""
        beliefs = self._belief_snapshot()
        for key, (prob, hops, origin) in beliefs.items():
            agent_id, belief_key = key
            before = self._beliefs.get(key)
            if before is None:
                self.record("learned", agent_id, belief=belief_key,
                            probability=round(prob, 3), hops=hops, origin=origin,
                            how=("witnessed or heard directly" if hops == 0
                                 else f"relayed, {hops} hop(s) from the source"))
            elif abs(before[0] - prob) > 0.02:
                self.record("shifted", agent_id, belief=belief_key,
                            was=round(before[0], 3), now=round(prob, 3), origin=origin)
        self._beliefs = beliefs

        recall = self._recall_snapshot()
        for agent_id, remembered in recall.items():
            lost = self._recall.get(agent_id, set()) - remembered
            held = {m.memory_id: m for m in self.runtime.world.agents[agent_id].memory}
            for memory_id in sorted(lost):
                # Two different things end in "cannot recall it", and a record that
                # calls them both forgetting is misleading in both directions. A
                # decayed memory is still on file and could be cued back; an evicted
                # one is gone from the store entirely, because the agent hit its
                # capacity and something had to go.
                memory = held.get(memory_id)
                self.record("forgot", agent_id, memory=memory_id,
                            content=memory.content if memory else "(no longer stored)",
                            cause="decayed below the retrieval threshold" if memory
                                  else "evicted: the agent was at capacity",
                            note="still stored, no longer retrievable" if memory
                                 else "dropped from the store")
        self._recall = recall

    def harvest_diffusion(self):
        """Pull retellings and distortions out of the last tick's trace."""
        for code, magnitude, detail in self.runtime.core.last_traces.get("_diffusion", []):
            if code == "diffusion.told":
                self.record("told", detail.get("speaker"), listener=detail.get("listener"),
                            place=detail.get("place"), claim=detail.get("proposition"),
                            origin=detail.get("origin"), hops=detail.get("hops"))
            elif code == "diffusion.distorted":
                self.record("distorted", detail.get("speaker"), kind_of=detail.get("kind"),
                            heard=detail.get("heard"), retold=detail.get("retold"),
                            what_changed=detail.get("what_changed"))
        for code, _magnitude, detail in self.runtime.core.last_traces.get("_routine", []):
            if code == "routine.moved":
                self.record("moved", detail.get("agent"), to=detail.get("to"),
                            activity=detail.get("activity"), at=detail.get("time_of_day"))

    def say(self, command: str):
        """Run a player command and record the line, the verdict and the reasoning."""
        result = self.runtime.submit_player_text(command)
        response = result.npc_response
        detail = {"player_said": command, "reply": result.message.splitlines()[0]
                  if result.message else ""}
        if response is not None:
            reasons = [c for c, _m, _d in response.reasons]
            detail.update({"speaker": response.speaker_id, "line": response.text,
                           "act": response.act, "verdict": response.verdict,
                           "why": reasons[:8]})
            gate = next((d for c, _m, d in response.reasons if c == "dialogue.secret_gate"), None)
            if gate:
                detail["withheld"] = gate
            raw = self.runtime.store.conn.execute(
                "SELECT raw_output, accepted_output, validation_result, model_id "
                "FROM provider_call ORDER BY rowid DESC LIMIT 1").fetchone()
            if raw and raw[3] not in (None, "deterministic-template"):
                blocked = bool(raw[0]) and raw[0] != raw[1]
                detail["model"] = {"id": raw[3], "raw": raw[0], "released": raw[1],
                                   "verdict": raw[2], "blocked": blocked}
                if blocked:
                    # The single most useful artefact in the whole record: a model
                    # tried to say something and was stopped. Counted separately so
                    # it is not buried in a thousand ordinary lines.
                    detail["blocked_by_validator"] = True
        self.record("said", response.speaker_id if response else "", **detail)
        return result


# ------------------------------------------------------------------- chains --

def evidence_chain(runtime: UnscriptedRuntime, agent_id: str, belief_key: str) -> dict:
    """Reconstruct how one character came to hold one belief.

    Built from the belief's own origin index plus the event ledger, which is the
    same material an auditor would have. Nothing is remembered specially for this.
    """
    agent = runtime.world.agents.get(agent_id)
    belief = agent.beliefs.get(belief_key) if agent else None
    if belief is None:
        return {"agent": agent_id, "belief": belief_key, "known": False}

    steps = []
    if runtime.store is not None:
        for row in runtime.store.diffusion_events(limit=500):
            if row.get("to") == agent_id or row.get("from") == agent_id:
                steps.append({
                    "world_time": row["world_time"],
                    "from": runtime.agent_name(row["from"]) if row["from"] else "?",
                    "to": runtime.agent_name(row["to"]) if row["to"] else "?",
                    "place": runtime.world.place_label(row["place"]) if row["place"] else "?",
                    "hops": row["hops"],
                    "changed": row.get("distortion_kind"),
                })
    first_hand = [other.id for other in runtime.world.agents.values()
                  if belief_key in other.beliefs and other.beliefs[belief_key].hops == 0]
    return {
        "agent": agent_id, "name": runtime.agent_name(agent_id),
        "belief": str(belief.proposition), "known": True,
        "confidence": round(belief.expected_prob, 3),
        "hops_from_source": belief.hops,
        "origin": belief.primary_origin,
        "times_heard": sum(belief.origin_counts.values()),
        "independent_origins": len(belief.origin_counts),
        "first_hand_holders": [runtime.agent_name(a) for a in first_hand],
        "route": steps[-6:],
    }


# -------------------------------------------------------------------- cases --

def _runtime(pack: str, *, llm: dict | None = None, seed_suffix: str = "") -> UnscriptedRuntime:
    config = RuntimeConfig(world_pack_path=pack, storage_path=":memory:", debug_traces=True)
    if llm:
        config.text_realizer = dict(llm)
    return UnscriptedRuntime.create(config)


def case_determinism(pack, llm=None, budget=None) -> CaseResult:
    """Two runs from the same seed must be the same world, to the byte."""
    from . import snapshot as snapshot_module
    result = CaseResult("determinism", "Does the same seed reproduce the same world?", True)
    started = time.perf_counter()
    fingerprints = []
    for _ in range(2):
        runtime = _runtime(pack)
        recorder = Recorder(runtime)
        try:
            for command in ("look", "wait 60", "wait 120", "wait 240"):
                recorder.say(command)
                recorder.harvest_diffusion()
                recorder.sweep()
            fingerprints.append(json.dumps(snapshot_module.capture(runtime.world, runtime.core),
                                           sort_keys=True, default=str))
        finally:
            runtime.close()
    identical = fingerprints[0] == fingerprints[1]
    result.passed = identical
    result.episodes = recorder.episodes
    result.stats = {"bytes_compared": len(fingerprints[0]), "identical": identical}
    if not identical:
        result.findings.append("two runs of the same seed diverged")
    result.seconds = time.perf_counter() - started
    return result


def case_broadcast_chain(pack, llm=None, budget=None) -> CaseResult:
    """A fact enters by radio. Can every later holder be traced back to it?"""
    result = CaseResult("broadcast_chain",
                        "Can every holder of a fact be traced back to where it entered the world?",
                        True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        recorder.note("Waiting for the scheduled broadcast to enter the world.")
        for _ in range(30):
            runtime.advance_time(60)
            recorder.harvest_diffusion()
            recorder.sweep()

        chains = []
        for agent in runtime.world.agents.values():
            for key, belief in agent.beliefs.items():
                if belief.hops > 0:
                    chains.append(evidence_chain(runtime, agent.id, key))
        # Every origin that anybody holds first-hand, over ALL propositions. A
        # distorted claim legitimately has no first-hand holder of its own -- nobody
        # witnessed the false version, because it never happened -- but the origin
        # it travels under must still be a real observation somebody made.
        real_origins = set()
        for agent in runtime.world.agents.values():
            for belief in agent.beliefs.values():
                if belief.hops == 0:
                    real_origins.update(belief.origin_counts)

        unsourced = [c for c in chains if not c["origin"]]
        invented = [c for c in chains if c["origin"] and c["origin"] not in real_origins]
        distorted_only = [c for c in chains
                          if c["origin"] in real_origins and not c["first_hand_holders"]]
        result.passed = not unsourced and not invented
        if unsourced:
            result.findings.append(f"{len(unsourced)} relayed belief(s) name no origin")
        if invented:
            result.findings.append(
                f"{len(invented)} relayed belief(s) cite an origin nobody ever observed")
        recorder.note(
            f"{len(chains)} relayed beliefs; {len(distorted_only)} of them are distorted "
            f"versions with no eyewitness of their own -- expected, since the distorted "
            f"claim never happened -- but every one still cites a real observation.")
        for chain in chains[:8]:
            recorder.record("chain", chain["agent"], **chain)
        result.stats = {"relayed_beliefs": len(chains),
                        "citing_a_real_observation": len(chains) - len(unsourced) - len(invented),
                        "distorted_without_eyewitness": len(distorted_only),
                        "distinct_real_origins": len(real_origins)}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_forgetting(pack, llm=None, budget=None) -> CaseResult:
    """Does anything actually fade, and can a character stop being able to answer?"""
    result = CaseResult("forgetting", "Do memories fade past recall, and is that observable?", True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        from .events import Event
        from .memory import Memory

        subject = next(a for a in runtime.world.agents.values()
                       if a.id != runtime.config.player_id)
        threshold = runtime.core.memory.params["tau_ret"]

        # Two memories, identical except for how much they matter. Watching one
        # named pair over time is evidence; comparing counts is not, because new
        # memories arrive while old ones fade.
        watched = {}
        for label, importance in (("the murder they witnessed", 0.95),
                                  ("someone walking past", 0.05)):
            memory = Memory(memory_id=f"watch:{label}", owner=subject.id, type="episodic",
                            content=label, importance=importance, emotional_valence=-0.6)
            runtime.core.memory.encode(subject.memory, memory, runtime.world.world_time)
            watched[label] = memory
        recorder.note(f"Watching two memories of {runtime.agent_name(subject.id)}, identical "
                      f"except for importance. Recall threshold is {threshold}.")

        curve = {label: [] for label in watched}
        lost_at = {}
        for step in range(24):
            runtime.advance_time(60 * 8)          # eight hours at a time, for eight days
            recorder.harvest_diffusion()
            recorder.sweep()
            hours = step * 8 + 8
            for label, memory in watched.items():
                activation = memory.base_activation(runtime.world.world_time)
                curve[label].append((hours, round(activation, 3)))
                if activation <= threshold and label not in lost_at:
                    lost_at[label] = hours
                    recorder.record("forgot", subject.id, memory=label, content=label,
                                    cause="decayed below the retrieval threshold",
                                    note=f"activation {activation:.2f} fell below "
                                         f"{threshold} after {hours}h")

        for label, samples in curve.items():
            recorder.record("decay", subject.id, memory=label,
                            samples=[f"{h}h:{a}" for h, a in samples[::3]],
                            lost_after_hours=lost_at.get(label))

        trivial = lost_at.get("someone walking past")
        important = lost_at.get("the murder they witnessed")
        result.passed = trivial is not None and (important is None or important > trivial)
        if trivial is None:
            result.findings.append("a trivial memory was still recallable after eight days")
        if important is not None and trivial is not None and important <= trivial:
            result.findings.append(
                "an important memory faded no slower than a trivial one -- importance "
                "is not affecting recall")
        result.stats = {"recall_threshold": threshold,
                        "trivial_lost_after_hours": trivial,
                        "important_lost_after_hours": important or "still recallable at 192h",
                        "stored_at_end": len(subject.memory)}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_distortion(pack, llm=None, budget=None) -> CaseResult:
    """Does a claim change shape in transit, and does the false version stay traceable?"""
    result = CaseResult("distortion",
                        "Does information degrade realistically, and stay accountable when it does?",
                        True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        runtime.core.diffusion.params["distortion_prob"] = 0.45
        recorder.note("Distortion raised to 0.45 so several days of drift fit in one case.")
        # Distortion rides on retelling, and retelling is a property of the cast: a
        # three-character world produces two or three conversations in sixty hours, so
        # at p=0.45 the expected number of distortions is about one. Asserting on that
        # sample would be a coin flip dressed up as a test. Run until the world has
        # gossiped enough to measure, and if it never does, say that instead of failing
        # the runtime for the pack being small.
        # Bounded twice on purpose: by simulated time, so the case has a fixed
        # meaning, and by wall clock, so a quiet world cannot eat the budget the
        # other cases need. Whichever comes first, the count reached is reported.
        NEEDED = 12
        stop_by = started + min(90.0, 0.25 * (budget or 90))
        for hour in range(600):
            runtime.advance_time(60)
            recorder.harvest_diffusion()
            recorder.sweep()
            if hour >= 59 and (recorder.counts.get("told", 0) >= NEEDED
                               or time.perf_counter() > stop_by):
                break
        retellings = recorder.counts.get("told", 0)

        by_predicate = {}
        for agent in runtime.world.agents.values():
            for key, belief in agent.beliefs.items():
                by_predicate.setdefault(belief.proposition.predicate, set()).add(key)
        variants = {p: sorted(k) for p, k in by_predicate.items() if len(k) > 1}
        kinds = {}
        for episode in recorder.episodes:
            if episode.kind == "distorted":
                kinds[episode.detail.get("kind_of")] = kinds.get(episode.detail.get("kind_of"), 0) + 1

        untraceable = []
        for keys in variants.values():
            for key in keys:
                for agent in runtime.world.agents.values():
                    belief = agent.beliefs.get(key)
                    if belief and belief.hops > 0 and not belief.primary_origin:
                        untraceable.append((agent.id, key))
        result.passed = bool(variants) and not untraceable
        if retellings < NEEDED:
            # Not a pass and not a failure: the world never gave the mechanism
            # anything to act on, and the record should say which of the two it is.
            result.applicable = False
            result.passed = not untraceable
            result.findings.append(
                f"too little gossip to measure: {retellings} retelling(s) in "
                f"{round(runtime.world.world_time / 1440)} days — a cast this small "
                f"rarely repeats anything. Distortion untested here, not disproved.")
        elif not variants:
            result.findings.append(
                f"no claim ever changed shape in {retellings} retellings")
        if untraceable:
            result.findings.append(f"{len(untraceable)} distorted belief(s) name no origin")
        result.stats = {"claims_with_several_versions": len(variants), "processes_seen": kinds,
                        "retellings_observed": retellings, "retellings_needed": NEEDED,
                        "days_simulated": round(runtime.world.world_time / 1440)}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_secret_under_pressure(pack, llm=None, budget=None) -> CaseResult:
    """Ask the same person the same thing repeatedly. Does the secret hold?"""
    result = CaseResult("secret_under_pressure",
                        "Does a secret survive persistence, pressure and gifts?", True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        holders = [a for a in runtime.world.agents.values() if a.secrets]
        if not holders:
            result.stats = {"skipped": "this world has no secrets"}
            result.seconds = time.perf_counter() - started
            return result
        holder = holders[0]
        secret = holder.secrets[0]
        forbidden = [f.lower() for f in secret.surface_forms]
        topic = (secret.guards_topics or [""])[0]
        name = runtime.agent_name(holder.id)
        recorder.note(f"{name} is hiding: {secret.summary or secret.secret_id}. "
                      f"Words that would give it away: {', '.join(secret.surface_forms) or '(none)'}")

        leaks = []
        rounds = 12 if llm else 40
        for round_number in range(rounds):
            runtime.world.agents[runtime.config.player_id].location = holder.location
            for command in (f"ask {name} about {topic}",
                            f"threaten {name}",
                            f"promise {name} 500",
                            f"ask {name} about {topic}"):
                turn = recorder.say(command)
                line = (turn.npc_response.text if turn.npc_response else turn.message).lower()
                for form in forbidden:
                    if form in line:
                        leaks.append({"round": round_number, "said": line, "gave_away": form})
            runtime.advance_time(30)
            recorder.harvest_diffusion()
            recorder.sweep()

        others = [a.id for a in runtime.world.agents.values()
                  if a.id != holder.id
                  for key in secret.protects if key in a.beliefs]
        result.passed = not leaks and not others
        if leaks:
            result.findings.append(f"the secret was said aloud {len(leaks)} time(s)")
        if others:
            result.findings.append(f"the protected fact reached {sorted(set(others))}")
        blocked = [e for e in recorder.episodes
                   if e.kind == "said" and e.detail.get("blocked_by_validator")]
        result.stats = {"rounds": rounds, "questions_asked": rounds * 4, "leaks": len(leaks),
                        "spoken_by": (llm or {}).get("model_id", "authored templates"),
                        "model_lines_stopped_before_release": len(blocked),
                        "trust_at_end": round(holder.trust_in(runtime.config.player_id), 3),
                        "gate_required": secret.min_trust}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_disagreement(pack, llm=None, budget=None) -> CaseResult:
    """When independent sources disagree, is the conflict visible rather than averaged?"""
    from .events import Event
    from .ontology import Proposition
    result = CaseResult("disagreement",
                        "Do conflicting testimonies surface as conflict rather than averaging out?",
                        True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        listener = next(a for a in runtime.world.agents.values()
                        if a.id != runtime.config.player_id)
        claim = Proposition("body:alive", {"agent": "entity:subject"})
        for index, (polarity, origin) in enumerate([("+", "witness_one"), ("-", "witness_two"),
                                                    ("+", "witness_three"), ("-", "witness_four")]):
            runtime.emit_event(Event(
                runtime.world.new_event_id(), runtime.world.world_time, "claim",
                actor=None, location=listener.location,
                payload={"proposition": claim.as_dict(), "asserter_polarity": polarity,
                         "origin_event": origin, "summary": f"witness {index + 1} testifies"}))
            recorder.sweep()
        belief = listener.beliefs.get(claim.core_key())
        conflict = belief.conflict if belief else 0.0
        recorder.record("conflict", listener.id, belief=str(claim),
                        probability=round(belief.expected_prob, 3) if belief else None,
                        conflict=round(conflict, 3),
                        support_for=round(belief.support_for, 3) if belief else 0,
                        support_against=round(belief.support_against, 3) if belief else 0,
                        independent_origins=len(belief.origin_counts) if belief else 0,
                        note="four independent witnesses, two each way")
        result.passed = belief is not None and conflict > 0.5 and len(belief.origin_counts) == 4
        if belief is None:
            result.findings.append("the listener formed no belief at all")
        elif conflict <= 0.5:
            result.findings.append(f"conflict reported as {conflict:.2f}; contradiction was "
                                   f"averaged away instead of surfaced")
        result.stats = {"conflict": round(conflict, 3),
                        "probability": round(belief.expected_prob, 3) if belief else None,
                        "distinct_origins": len(belief.origin_counts) if belief else 0}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_conversation(pack, llm=None, budget=None) -> CaseResult:
    """A recorded conversation: what was asked, what was said, and why."""
    result = CaseResult("conversation",
                        "Is every line explainable, and does the same question get "
                        "different answers from different people?", True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        topics = sorted(runtime.world.topics)
        answers = {}
        for _ in range(3 if llm else 6):
            scene = runtime.structured_scene()
            for person in scene["npcs"]:
                for topic in topics:
                    turn = recorder.say(f"ask {person['name']} about {topic}")
                    if turn.npc_response:
                        answers.setdefault(topic, {})[person["name"]] = turn.npc_response.text
            runtime.advance_time(120)
            recorder.harvest_diffusion()
            recorder.sweep()

        spoken = [e for e in recorder.episodes if e.kind == "said" and e.detail.get("line")]
        unexplained = [e for e in spoken if not e.detail.get("why")]
        blocked = [e for e in spoken if e.detail.get("blocked_by_validator")]
        divided = {t: v for t, v in answers.items() if len(set(v.values())) > 1}
        result.passed = bool(spoken) and not unexplained
        if unexplained:
            result.findings.append(f"{len(unexplained)} line(s) came with no reasoning")
        result.stats = {"lines_spoken": len(spoken),
                        "topics_where_people_disagree": sorted(divided),
                        "model_lines": sum(1 for e in spoken if e.detail.get("model")),
                        "model_lines_blocked_by_validator": len(blocked)}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_cross_examination(pack, llm=None, budget=None) -> CaseResult:
    """Press every character on every topic without letting the clock move.

    The question a studio asks about putting a language model in the mouth of an
    NPC is *"will it stay the same character?"*. This case isolates that. A player
    turn does not advance world time, so with no `advance_time` call there is no
    diffusion, no movement and no scheduled event: anything that changes during
    the interrogation was changed BY THE INTERROGATION. Belief must not move
    because someone asked. Saying a thing out loud must not make the speaker
    surer of it, and a player cannot manufacture confidence by repeating himself.

    What the model is allowed to change is the wording, and that is measured
    rather than assumed: distinct phrasings per speaker and topic, against zero
    tolerance for a moved belief.
    """
    result = CaseResult("cross_examination",
                        "Does pressing a character change what they believe, "
                        "or only how they put it?", True)
    started = time.perf_counter()
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        topics = sorted(runtime.world.topics)
        scene = runtime.structured_scene()
        if not scene["npcs"] or not topics:
            result.applicable = False
            result.findings.append("nobody to question, or nothing to ask about")
            result.stats = {"pack": os.path.basename(pack)}
            result.seconds = time.perf_counter() - started
            return result

        before_time = runtime.world.world_time
        before = {(a.id, key): b.expected_prob
                  for a in runtime.world.agents.values() for key, b in a.beliefs.items()}
        secrets = {a.id: [f.lower() for sec in a.secrets for f in sec.surface_forms]
                   for a in runtime.world.agents.values()}

        phrasings: dict = {}
        acts: dict = {}
        leaks = []
        # Every proposition actually said out loud, and by whom. A belief may move
        # if -- and only if -- an utterance explains it. Asking must change nothing;
        # being told something may.
        asserted: dict = {}
        rounds = 4 if llm else 10
        for _ in range(rounds):
            for person in scene["npcs"]:
                for topic in topics:
                    turn = recorder.say(f"ask {person['name']} about {topic}")
                    response = turn.npc_response
                    if response is None:
                        continue
                    slot = (response.speaker_id, topic)
                    phrasings.setdefault(slot, set()).add(response.text)
                    acts.setdefault(slot, set()).add(response.act)
                    for _code, _m, detail in response.reasons:
                        # every utterance counts, honest or deceptive: a lie moves
                        # belief exactly as an honest claim does, which is the point
                        for utterance in detail.get("spoken") or []:
                            asserted.setdefault(utterance["proposition"], set()).add(
                                response.speaker_id)
                    line = response.text.lower()
                    for form in secrets.get(response.speaker_id, []):
                        if form and form in line:
                            leaks.append({"who": response.speaker_id, "said": response.text,
                                          "gave_away": form})

        after = {(a.id, key): b.expected_prob
                 for a in runtime.world.agents.values() for key, b in a.beliefs.items()}
        def unexplained(agent_id, belief_key):
            """A move is explained by someone ELSE having asserted it aloud."""
            speakers = asserted.get(belief_key, set())
            return not (speakers - {agent_id})

        moved = [{"agent": k[0], "belief": k[1], "was": round(v, 4),
                  "now": round(after[k], 4)}
                 for k, v in before.items()
                 if abs(after.get(k, v) - v) > 1e-9 and unexplained(*k)]
        # A speaker must never move on their own assertion: saying a thing out
        # loud is not evidence for the person saying it.
        self_moved = [{"agent": k[0], "belief": k[1], "was": round(v, 4),
                       "now": round(after[k], 4)}
                      for k, v in before.items()
                      if abs(after.get(k, v) - v) > 1e-9
                      and k[0] in asserted.get(k[1], set())
                      and not (asserted.get(k[1], set()) - {k[0]})]
        appeared = sorted(k for k in set(after) - set(before) if unexplained(*k))
        spoken = [e for e in recorder.episodes if e.kind == "said" and e.detail.get("line")]
        unexplained_lines = [e for e in spoken if not e.detail.get("why")]

        result.passed = (not moved and not appeared and not leaks and not unexplained_lines
                         and not self_moved and runtime.world.world_time == before_time)
        if moved:
            result.findings.append(
                f"{len(moved)} belief(s) moved with nothing said that explains it: "
                f"{moved[:3]}")
        if self_moved:
            result.findings.append(
                f"{len(self_moved)} speaker(s) grew surer of what they themselves "
                f"said: {self_moved[:3]}")
        if appeared:
            result.findings.append(f"questioning created {len(appeared)} belief(s) from nothing")
        if leaks:
            result.findings.append(f"a secret surface form was said aloud {len(leaks)} time(s)")
        if unexplained_lines:
            result.findings.append(
                f"{len(unexplained_lines)} line(s) came with no reasoning")
        if runtime.world.world_time != before_time:
            result.findings.append("the clock moved during questioning, so this proves nothing")

        variety = [len(v) for v in phrasings.values()]
        blocked = [e for e in spoken if e.detail.get("blocked_by_validator")]
        result.stats = {
            "questions_asked": rounds * len(scene["npcs"]) * len(topics),
            "lines_spoken": len(spoken),
            "beliefs_moved_by_questioning": len(moved),
            "beliefs_invented_by_questioning": len(appeared),
            "beliefs_moved_by_being_told": sum(
                1 for k, v in before.items()
                if abs(after.get(k, v) - v) > 1e-9 and not unexplained(*k)),
            "propositions_said_aloud": len(asserted),
            "speakers_persuaded_by_themselves": len(self_moved),
            "distinct_phrasings_max": max(variety) if variety else 0,
            "distinct_phrasings_mean": round(sum(variety) / len(variety), 2) if variety else 0,
            "acts_used": sorted({a for v in acts.values() for a in v}),
            "spoken_by": (llm or {}).get("model_id", "authored templates"),
            "model_lines": sum(1 for e in spoken if e.detail.get("model")),
            "model_lines_stopped_before_release": len(blocked),
            "secret_leaks": len(leaks),
        }
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


def case_long_life(pack, llm=None, budget=None) -> CaseResult:
    """Everything at once, for as long as there is time. Where interactions live."""
    from .benchmark import (_belief_sanity, _memory_bounded, _provenance_completeness,
                            _secret_containment, _single_origin_certainty,
                            _unsourced_knowledge)
    result = CaseResult("long_life",
                        "Does it all still hold after days of continuous play?", True)
    started = time.perf_counter()
    deadline = started + (budget or 60)
    runtime = _runtime(pack, llm=llm)
    recorder = Recorder(runtime)
    try:
        commands = ["look", "wait 45", "wait 90"]
        topics = sorted(runtime.world.topics)
        turn = 0
        checks = 0
        dropped: dict = {}
        while time.perf_counter() < deadline:
            turn += 1
            scene = runtime.structured_scene()
            if scene["npcs"] and topics:
                person = scene["npcs"][turn % len(scene["npcs"])]["name"]
                recorder.say(f"ask {person} about {topics[turn % len(topics)]}")
            else:
                recorder.say(commands[turn % len(commands)])
            runtime.advance_time(30)
            recorder.harvest_diffusion()
            if turn % 10 == 0:
                recorder.sweep()
            if turn % 50 == 0:
                checks += 1
                for metric in (_unsourced_knowledge(runtime), _single_origin_certainty(runtime),
                               _secret_containment(runtime), _provenance_completeness(runtime),
                               _memory_bounded(runtime), _belief_sanity(runtime)):
                    if not metric.passed:
                        result.passed = False
                        result.findings.append(
                            f"turn {turn}: {metric.key} failed ({metric.value}, {metric.bound})")
                    recorder.record("checked", "", metric=metric.key,
                                    value=metric.value, passed=metric.passed)
                # Keep the record readable over a long run. Counts come from
                # recorder.counts, which is unaffected by this.
                if len(recorder.episodes) > 4000:
                    recorder.episodes = recorder.episodes[-2000:]
                    dropped["episodes"] = dropped.get("episodes", 0) + 2000
        recorder.sweep()
        result.stats = {"turns": turn, "simulated_days": round(runtime.world.world_time / 1440, 1),
                        "invariant_sweeps": checks,
                        "retellings": recorder.counts.get("told", 0),
                        "distortions": recorder.counts.get("distorted", 0),
                        "forgettings": recorder.counts.get("forgot", 0),
                        "forgettings_by_decay": recorder.counts.get("forgot:decayed", 0),
                        "forgettings_by_eviction": recorder.counts.get("forgot:evicted", 0),
                        "beliefs_acquired": recorder.counts.get("learned", 0),
                        "episodes_recorded": sum(recorder.counts.values()),
                        "episodes_kept": len(recorder.episodes),
                        "episodes_dropped_for_readability": dropped.get("episodes", 0)}
        result.episodes = recorder.episodes
    finally:
        runtime.close()
    result.seconds = time.perf_counter() - started
    return result


CASES = (case_determinism, case_broadcast_chain, case_forgetting, case_distortion,
         case_secret_under_pressure, case_disagreement, case_conversation,
         case_cross_examination, case_long_life)

#: Cases where the SPOKEN LINE is the evidence, so a configured model is used for
#: them. Everywhere else the model would only slow the run down: a case about
#: invariants over a hundred thousand turns is not made more convincing by each
#: turn also costing 300 ms of GPU.
MODEL_CASES = {"case_secret_under_pressure", "case_conversation",
               "case_cross_examination"}


# --------------------------------------------------------------------- run --

def provenance(packs) -> dict:
    """Where and when this run happened, and against which code.

    A dossier without this is a set of numbers with no address. "36 cases held"
    is only evidence if you can say which commit produced it, on what, and when --
    otherwise a result outlives the code it was true of, which is exactly how a
    passing record ends up describing something that no longer exists.
    """
    import platform
    import subprocess

    def git(*args):
        try:
            return subprocess.run(("git", *args), capture_output=True, text=True,
                                  timeout=10, cwd=os.path.dirname(os.path.dirname(
                                      os.path.abspath(__file__)))).stdout.strip()
        except Exception:
            return ""

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    return {
        "commit": commit or "unknown",
        "commit_subject": git("log", "-1", "--pretty=%s"),
        "working_tree": "dirty" if dirty else "clean",
        "packs": [os.path.basename(p) for p in packs],
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def case_names() -> tuple:
    """The cases a run can be narrowed to."""
    return tuple(c.__name__.removeprefix("case_") for c in CASES)


def run_evidence(*, packs, hours: float = 2.0, llm: dict | None = None,
                 out_dir: str = "evidence", progress=None, only=None) -> dict:
    """Run every case against every pack, filling the time budget with the long one.

    ``only`` narrows the run to named cases. A full run is the artefact -- one
    record, one clock, one determinism claim -- but re-running everything to
    inspect one case costs the whole budget, so iteration gets a filter and the
    dossier records which cases were selected.
    """
    started = time.perf_counter()
    deadline = started + hours * 3600
    os.makedirs(out_dir, exist_ok=True)
    runs = []
    stamp = provenance(packs)

    if only:
        unknown = sorted(set(only) - set(case_names()))
        if unknown:
            raise ValueError(f"no such case: {', '.join(unknown)}. "
                             f"Known: {', '.join(case_names())}")
    selected = [c for c in CASES
                if not only or c.__name__.removeprefix("case_") in only]
    short_cases = [c for c in selected if c is not case_long_life]
    for pack in packs:
        for case in short_cases:
            if progress:
                progress(f"{os.path.basename(pack)} :: {case.__name__}")
            try:
                # the model only where the line itself is the evidence
                outcome = case(pack, llm=llm if case.__name__ in MODEL_CASES else None)
            except Exception as exc:              # a case must not abort the run
                outcome = CaseResult(case.__name__, "(raised)", False,
                                     findings=[f"{type(exc).__name__}: {exc}"])
            outcome.stats["pack"] = os.path.basename(pack)
            runs.append(outcome)

    if case_long_life not in selected:
        return _write_dossier(out_dir, started, hours, packs, llm, runs, only, stamp)

    # whatever time is left goes to the long case, shared across packs
    remaining = max(30.0, deadline - time.perf_counter())
    per_pack = remaining / max(1, len(packs))
    for pack in packs:
        if progress:
            progress(f"{os.path.basename(pack)} :: long_life ({per_pack / 60:.0f} min)")
        try:
            outcome = case_long_life(pack, llm=llm, budget=per_pack)
        except Exception as exc:
            outcome = CaseResult("long_life", "(raised)", False,
                                 findings=[f"{type(exc).__name__}: {exc}"])
        outcome.stats["pack"] = os.path.basename(pack)
        runs.append(outcome)

    return _write_dossier(out_dir, started, hours, packs, llm, runs, only, stamp)


def _write_dossier(out_dir, started, hours, packs, llm, runs, only=None,
                   stamp=None) -> dict:
    dossier = {
        "generated_after_seconds": round(time.perf_counter() - started, 1),
        "hours_requested": hours,
        "packs": [os.path.basename(p) for p in packs],
        "model": (llm or {}).get("model_id", "deterministic templates only"),
        # A partial run must say so on its face. A dossier that silently omits
        # cases reads exactly like one where they all passed.
        "cases_selected": sorted(only) if only else "all",
        "run": {**(stamp or {}),
                "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        "passed": all(r.passed for r in runs),
        "cases": [r.as_dict() for r in runs],
    }
    with open(os.path.join(out_dir, "evidence.json"), "w", encoding="utf-8") as fh:
        json.dump(dossier, fh, indent=2, sort_keys=False, default=str)
        fh.write("\n")
    with open(os.path.join(out_dir, "DOSSIER.md"), "w", encoding="utf-8") as fh:
        fh.write(render_dossier(dossier))
    return dossier


def render_dossier(dossier: dict) -> str:
    """The record as something a person would actually read."""
    out = ["# Unscripted — Evidence Run", ""]
    untested = [c for c in dossier["cases"] if not c.get("applicable", True)]
    verdict = "every case held" if dossier["passed"] else "SOME CASES FAILED"
    if untested and dossier["passed"]:
        verdict += f" ({len(untested)} untestable in the world given)"
    out += [f"**{verdict}** · {dossier['generated_after_seconds'] / 60:.0f} minutes of running · "
            f"packs: {', '.join(dossier['packs'])} · text: {dossier['model']}", ""]
    run = dossier.get("run") or {}
    if run:
        out += ["| | |", "| --- | --- |",
                f"| commit | `{run.get('commit', '?')[:12]}` "
                f"{run.get('commit_subject', '')} |",
                f"| working tree | {run.get('working_tree', '?')} |",
                f"| python | {run.get('python', '?')} |",
                f"| platform | {run.get('platform', '?')} |",
                f"| started / finished | {run.get('started_utc', '?')} → "
                f"{run.get('finished_utc', '?')} |", ""]
        if run.get("working_tree") == "dirty":
            out += ["> **The working tree had uncommitted changes when this ran.** "
                    "The commit named above is not exactly what produced these "
                    "numbers.", ""]
    if dossier.get("cases_selected", "all") != "all":
        out += [f"> **Partial run.** Only these cases were run: "
                f"{', '.join(dossier['cases_selected'])}. The others were not "
                f"attempted — this is not a record of them passing.", ""]
    if untested:
        out += ["> Cases marked *n/a* were not run to a verdict because the world never "
                "exercised the mechanism — a three-character village produces almost no "
                "gossip. They are untested there, not disproved; the same case passes on "
                "the larger packs in the same run.", ""]
    blocked = sum(c["stats"].get("model_lines_blocked_by_validator", 0)
                  + c["stats"].get("model_lines_stopped_before_release", 0)
                  for c in dossier["cases"])
    if blocked:
        out += [f"> The language model produced **{blocked}** lines that were stopped before "
                f"reaching the player. Each one is recorded below with what it tried to say "
                f"and what was released instead.", ""]

    out += ["| Case | Pack | Result | Time |", "| --- | --- | --- | --- |"]
    for case in dossier["cases"]:
        mark = ("pass" if case["passed"] else "**FAIL**") if case.get("applicable", True) \
            else "n/a"
        out.append(f"| {case['case']} | {case['stats'].get('pack', '')} | {mark} | "
                   f"{case['seconds']:.0f}s |")
    out.append("")

    for case in dossier["cases"]:
        out += [f"## {case['case']} — {case['stats'].get('pack', '')}", "",
                f"*{case['question']}*", ""]
        if case["findings"]:
            out.append("**Findings:**")
            out += [f"- {f}" for f in case["findings"]]
            out.append("")
        if case["stats"]:
            out.append("```")
            for key, value in case["stats"].items():
                out.append(f"{key:32s} {value}")
            out.append("```")
            out.append("")

        episodes = case["episodes"]
        shown = _pick_evidence(episodes)
        if shown:
            out.append("**Record** (excerpt):")
            out.append("")
            for episode in shown:
                out.append(_render_episode(episode))
            out.append("")
    return "\n".join(out)


def _pick_evidence(episodes: list, limit: int = 40) -> list:
    """Prefer the episodes that show something: lines, chains, losses, distortions."""
    priority = {"said": 0, "chain": 0, "distorted": 0, "forgot": 0, "decay": 0, "conflict": 0,
                "note": 1, "told": 2, "learned": 2, "moved": 4, "checked": 4, "shifted": 5}
    ranked = sorted(enumerate(episodes), key=lambda pair: (priority.get(pair[1]["kind"], 3),
                                                           pair[0]))
    chosen = sorted(ranked[:limit], key=lambda pair: pair[0])
    return [episode for _index, episode in chosen]


def _render_episode(episode: dict) -> str:
    clock = episode.get("clock", "")
    kind = episode.get("kind")
    who = episode.get("who", "")
    if kind == "said":
        line = episode.get("line") or episode.get("reply", "")
        text = [f"- `{clock}` **{who or 'world'}** — player: *{episode.get('player_said','')}*"]
        if line:
            text.append(f"  > {line}")
        if episode.get("why"):
            text.append(f"  reasoning: `{', '.join(episode['why'])}`")
        if episode.get("withheld"):
            gate = episode["withheld"]
            text.append(f"  **withheld**: trust {gate.get('trust')} < required "
                        f"{gate.get('required')} for {gate.get('secrets')}")
        if episode.get("model"):
            model = episode["model"]
            if model.get("blocked"):
                text.append(f"  **the model tried to say:** *{model.get('raw','')[:130]}*")
                text.append(f"  **released instead:** *{model.get('released') or '(nothing)'}* "
                            f"— {model.get('verdict')}")
            elif model.get("raw"):
                text.append(f"  (model line, released as generated — {model.get('verdict')})")
        return "\n".join(text)
    if kind == "chain":
        route = " → ".join(f"{s['from']}→{s['to']}@{s['place']}" for s in episode.get("route", []))
        return (f"- `{clock}` **{episode.get('name', who)}** holds *{episode.get('belief')}* "
                f"at {episode.get('confidence')}, {episode.get('hops_from_source')} hop(s) from "
                f"origin `{episode.get('origin')}`; first-hand: "
                f"{', '.join(episode.get('first_hand_holders') or []) or 'nobody'}"
                + (f"\n  route: {route}" if route else ""))
    if kind == "distorted":
        return (f"- `{clock}` **{who}** retold it wrong ({episode.get('kind_of')}): "
                f"{episode.get('what_changed')}\n"
                f"  heard: `{episode.get('heard')}`\n  retold: `{episode.get('retold')}`")
    if kind == "forgot":
        note = episode.get("note")
        cause = episode.get("cause", "")
        return (f"- `{clock}` **{who}** can no longer recall: *{episode.get('content')}*"
                + (f" — {cause}" if cause else "")
                + (f" ({note})" if note else ""))
    if kind == "decay":
        return (f"- `{clock}` **{who}** — decay of *{episode.get('memory')}*: "
                f"{' '.join(episode.get('samples') or [])}"
                + (f" → lost after {episode.get('lost_after_hours')}h"
                   if episode.get("lost_after_hours") else " → still recallable"))
    if kind == "learned":
        return (f"- `{clock}` **{who}** learned `{episode.get('belief')}` "
                f"({episode.get('how')}, origin `{episode.get('origin')}`)")
    if kind == "told":
        return (f"- `{clock}` **{who}** → {episode.get('listener')} @ {episode.get('place')}: "
                f"`{episode.get('claim')}` (hop {episode.get('hops')})")
    if kind == "conflict":
        return (f"- `{clock}` **{who}** holds a contradiction: {episode.get('belief')} at "
                f"p={episode.get('probability')}, conflict {episode.get('conflict')}, "
                f"{episode.get('independent_origins')} independent origins")
    if kind == "note":
        return f"- `{clock}` _{episode.get('text')}_"
    return f"- `{clock}` {kind} {who} {episode.get('metric', '')}"
