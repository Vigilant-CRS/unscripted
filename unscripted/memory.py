"""MemoryEngine (Technical Core v0.2 §5.1; Ontology v0.3 §9; spec v0.5 §5.6).

ACT-R base-level activation with recency/repetition decay, cue-based retrieval,
type-specific decay, working-memory cap, and mood-congruent recall bias.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math
from .determinism import derive_seed, seeded_uniform
from .types import sigmoid
from .ontology import Proposition, relevance


# type-specific decay rates d (Ontology v0.1 §9.6: episodic fades faster than semantic)
DECAY_BY_TYPE = {
    # A conclusion drawn from many occasions outlasts any one of them. This is the
    # point of forming it: the episodes are what fade, the pattern is what stays.
    "judgement": 0.28,"episodic": 0.55, "semantic": 0.40, "commitment": 0.30,
                 "emotional": 0.25, "summary": 0.35, "social": 0.40}


@dataclass
class Memory:
    memory_id: str
    owner: str
    type: str
    content: str
    proposition: Optional[Proposition] = None
    importance: float = 0.5
    emotional_valence: float = 0.0
    presentations: list = field(default_factory=list)   # world_times of encode/recall
    last_recalled: int = None
    source_conf: float = 1.0
    world_time: int = None
    #: For a summary: how many original episodes it stands for. Merging summaries
    #: sums these, so "a lot happened that week" keeps an honest count no matter
    #: how many times memory has been compressed.
    episodes: int = 1
    #: For a judgement: who it is about, and the episodes it was drawn from. A
    #: conclusion that cannot name its evidence is a prejudice, so the pointers
    #: are kept even when the episodes themselves are gone.
    about: tuple = ()
    evidence: tuple = ()

    def base_activation(self, t: int, eps: float = 1.0, *,
                        time_scale: float = 60.0, importance_slows_decay: float = 0.6) -> float:
        """ACT-R base-level activation, in HOURS, with important things fading slower.

        Two corrections over the textbook form, both found by watching a long run
        rather than by reading the formula:

        **Time scale.** World time is in minutes, and feeding minutes straight into
        a power law put a once-seen memory below the retrieval threshold after
        thirty of them. A character forgot a murder before the player left the
        room. Activation is now measured in hours, which is the unit a scene
        actually works in ("last night", "this morning").

        **Importance.** It had no effect on recall whatsoever -- a witnessed murder
        at importance 0.95 decayed identically to a passer-by at 0.05, because
        importance was only ever used to decide consolidation order. Important
        things get rehearsed, so importance now slows the decay exponent rather
        than adding a one-off bonus: it changes how long something lasts, not how
        loudly it scores once.
        """
        decay = DECAY_BY_TYPE.get(self.type, 0.5)
        decay *= max(0.05, 1.0 - importance_slows_decay * max(0.0, min(1.0, self.importance)))
        total = 0.0
        for tk in self.presentations:
            dt = max(eps, (t - tk) / max(1e-9, time_scale) + eps)
            total += dt ** (-decay)
        if total <= 0:
            return -10.0
        return math.log(total)

    def as_dict(self, t=None):
        # Lossless: every field that influences future activation must round-trip,
        # or a restored save drifts from the session it was taken from.
        d = {"memory_id": self.memory_id, "owner": self.owner, "type": self.type,
             "content": self.content,
             "importance": self.importance, "emotional_valence": self.emotional_valence,
             "source_conf": self.source_conf, "presentations": list(self.presentations),
             "last_recalled": self.last_recalled, "world_time": self.world_time,
             "episodes": self.episodes,
             # A judgement without these is a prejudice: `about` is who it
             # concerns and `evidence` names the occasions it was drawn from.
             # They were absent from the record entirely, so save/load turned
             # every conclusion a character had reached into an unattributed
             # sentence -- and consolidation, which finds an existing judgement
             # BY `about`, stopped finding it and started making duplicates.
             "about": list(self.about), "evidence": list(self.evidence),
             "proposition": self.proposition.as_dict() if self.proposition else None}
        if t is not None:
            d["activation"] = self.base_activation(t)
        return d

    @staticmethod
    def from_dict(d: dict, owner: str | None = None) -> "Memory":
        prop = Proposition.from_dict(d["proposition"]) if d.get("proposition") else None
        return Memory(memory_id=d["memory_id"], owner=owner or d.get("owner", ""),
                      type=d["type"], content=d["content"], proposition=prop,
                      importance=d["importance"], emotional_valence=d["emotional_valence"],
                      presentations=list(d.get("presentations", [])),
                      last_recalled=d.get("last_recalled"),
                      source_conf=d.get("source_conf", 1.0),
                      world_time=d.get("world_time"),
                      episodes=d.get("episodes", 1),
                      about=tuple(d.get("about") or ()),
                      evidence=tuple(d.get("evidence") or ()))


class MemoryEngine:
    module_id = "memory"
    version = "0.5.0"

    def __init__(self, params=None):
        self.params = {# Retrieval threshold. Was 0.0, which with the corrected time
                       # scale means "anything older than an hour is gone". -1.5
                       # gives trivia a few hours and an important memory weeks.
                       "tau_ret": -1.5, "noise_s": 0.4, "working_cap": 7,
                       "w_topic": 1.0, "w_goal": 0.6, "w_emotion": 0.5,
                       "w_mood_congruence": 0.3, "episodic_cap": 200,
                       "interference": 0.3,
                       # Every recall used to append a timestamp forever: 301 entries
                       # per memory after 300 retrievals, with base_activation() and
                       # every save walking the whole list. Old presentations
                       # contribute dt**-d, which is negligible next to recent ones,
                       # so a rolling window is a bounded and faithful approximation.
                       "presentation_window": 32,
                       # Non-episodic memory was uncapped entirely.
                       "total_cap": 600,
                       # Summaries are memories too. Excluding them from
                       # consolidation to avoid compounding loss created an
                       # unbounded path instead: one summary per tick, forever.
                       # 1,905 stored memories against a cap of 600 after 173
                       # simulated days, 1,595 of them summaries. Merging them is
                       # also what actually happens to people -- the details of
                       # what you forgot become "a lot happened that month".
                       "summary_cap": 40}
        if params:
            self.params.update(params)

    def encode(self, memories: list, mem: Memory, world_time: int):
        self._note_presentation(mem, world_time)
        mem.world_time = world_time
        memories.append(mem)
        return [("memory.encoded", mem.importance, {"content": mem.content, "type": mem.type})]

    def reinforce(self, mem: Memory, world_time: int):
        self._note_presentation(mem, world_time)
        mem.last_recalled = world_time

    def _note_presentation(self, mem: Memory, world_time: int):
        mem.presentations.append(world_time)
        window = self.params["presentation_window"]
        if window and len(mem.presentations) > window:
            del mem.presentations[:-window]   # keep the most recent, which dominate

    def retrieve(self, memories: list, t: int, *, topics=None, mood_valence: float = 0.0,
                 seed_parts=None):
        """Return memories above retrieval threshold, ranked, capped to working memory.

        RETRIEVAL IS A DRAW, NOT A THRESHOLD, and for a long time it only looked
        like one. The probability was computed as
        `sigmoid((a - tau_ret) / noise_s)` and then tested with `prob >= 0.5` --
        and because the sigmoid is monotonic and `sigmoid(0) = 0.5`, that
        comparison is exactly `a >= tau_ret` for ANY positive `noise_s`. The noise
        parameter moved the number that was reported and never the decision it
        was reported for, so the documented ACT-R retrieval probability was a
        deterministic cut-off wearing a probability's clothes.

        It draws now, from the runtime's own seed algebra rather than any global
        source, so a save still replays exactly while a character genuinely
        sometimes fails to come up with something they nearly remember.
        `seed_parts` is `(global_seed, agent_id, occasion)`; without it -- an
        engine used directly, with no world around it -- the old threshold
        behaviour is kept, because inventing a seed here would make an isolated
        engine irreproducible.
        """
        p = self.params
        scored = []
        for m in memories:
            a = m.base_activation(t)
            # spreading activation from cue topics
            if topics:
                best = max((relevance(m.proposition, tp) for tp in topics if m.proposition), default=0.0)
                a += p["w_topic"] * math.log(1 + best)
            # emotional importance
            a += p["w_emotion"] * abs(m.emotional_valence)
            # mood-congruent recall (spec §2.8)
            a += p["w_mood_congruence"] * mood_valence * (1 if m.emotional_valence >= 0 else -1)
            scored.append((a, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        # cue competition / interference: penalize similar lower-ranked memories
        out = []
        for a, m in scored:
            prob = sigmoid((a - p["tau_ret"]) / p["noise_s"])
            if seed_parts is None:
                came_up = prob >= 0.5
            else:
                draw = seeded_uniform(derive_seed(
                    *(list(seed_parts) + [t, self.module_id, m.memory_id])[:6]))
                came_up = draw < prob
            if came_up or (topics and a > p["tau_ret"] - 1.0):  # retrievable, or cue-dependent
                if m.last_recalled != t:
                    self.reinforce(m, t)  # retrieval-induced strengthening
                out.append((round(a, 3), round(prob, 3), m))
            if len(out) >= p["working_cap"]:
                break
        return out

    def decay_and_consolidate(self, memories: list, t: int):
        """Enforce memory caps by consolidating the least important, least active
        memories into a summary (spec §8.4).

        Two caps: the episodic one, and a total cap across all types. Only episodic
        memory was bounded before, so semantic, commitment, social and summary
        memories grew for the lifetime of a session.
        """
        reasons = []
        reasons += self._consolidate(memories, t, [m for m in memories if m.type == "episodic"],
                                     self.params["episodic_cap"], "episodic")
        total_cap = self.params.get("total_cap")
        if total_cap:
            reasons += self._consolidate(memories, t,
                                         [m for m in memories if m.type != "summary"],
                                         total_cap, "total")
        summary_cap = self.params.get("summary_cap")
        if summary_cap:
            reasons += self._consolidate(memories, t,
                                         [m for m in memories if m.type == "summary"],
                                         summary_cap, "summary")
        return reasons

    def _consolidate(self, memories: list, t: int, pool: list, cap: int, scope: str):
        if cap is None or len(pool) <= cap:
            return []
        pool.sort(key=lambda m: (m.importance, m.base_activation(t)))
        to_drop = pool[: len(pool) - cap]
        if not to_drop:
            return []

        # Before the detail goes, take what it was evidence FOR. Ninety per cent of
        # memory loss in a long run is capacity eviction, and evicting episodes
        # without drawing anything from them means a character can live through the
        # same thing fifty times and conclude nothing.
        reasons = self._form_judgements(memories, to_drop, t)
        episodes = sum(m.episodes for m in to_drop)
        summary = Memory(memory_id=f"sum_{scope}_{t}_{len(memories)}", owner=to_drop[0].owner,
                         type="summary",
                         content=f"(a blur of {episodes} minor moments)",
                         importance=0.3, world_time=t, presentations=[t],
                         episodes=episodes)
        memories.append(summary)
        for m in to_drop:
            memories.remove(m)
        return reasons + [("memory.consolidated", float(len(to_drop)),
                           {"summary": summary.memory_id, "scope": scope,
                            "episodes": episodes,
                            "dropped_ids": [m.memory_id for m in to_drop]})]

    #: How many occasions it takes before a pattern is worth concluding anything
    #: from. Two is coincidence.
    JUDGEMENT_THRESHOLD = 3

    def _form_judgements(self, memories: list, expiring: list, t: int) -> list:
        """Draw what repeats out of what is about to be forgotten.

        The pattern this looks for is deliberately narrow: the same predicate,
        about the same person, on several separate occasions. That is the shape a
        character actually generalises from -- "he keeps doing this" -- and it is
        the one that can be stated without inventing anything.

        The judgement keeps pointers to the episodes it came from. A conclusion
        that cannot name its evidence is a prejudice, and the inspector has to be
        able to answer "why does she think that about him" after the individual
        occasions are gone.
        """
        groups: dict = {}
        for memory in expiring:
            proposition = memory.proposition
            if proposition is None:
                continue
            for value in (proposition.slots or {}).values():
                subject = str(value)
                if not subject.startswith("agent:") or subject == memory.owner:
                    continue
                groups.setdefault((subject, proposition.predicate), []).append(memory)

        reasons = []
        for (subject, predicate), occasions in sorted(groups.items()):
            if len(occasions) < self.JUDGEMENT_THRESHOLD:
                continue
            existing = next((m for m in memories if m.type == "judgement"
                             and m.about == (subject, predicate)), None)
            valence = sum(m.emotional_valence for m in occasions) / len(occasions)
            strongest = sorted(occasions, key=lambda m: -m.importance)[:5]
            if existing is not None:
                # A pattern that keeps recurring gets firmer, not duplicated.
                existing.episodes += len(occasions)
                existing.importance = min(0.95, existing.importance + 0.05)
                existing.emotional_valence = (existing.emotional_valence + valence) / 2.0
                existing.evidence = tuple(list(existing.evidence)[-4:]
                                          + [m.memory_id for m in strongest[:2]])
                self._note_presentation(existing, t)
                reasons.append(("memory.judgement_reinforced", float(existing.episodes),
                                {"about": subject, "pattern": predicate,
                                 "occasions": existing.episodes,
                                 "content": existing.content}))
                continue
            content = (f"{subject} keeps being involved in {predicate}"
                       f" ({len(occasions)} times)")
            judgement = Memory(
                memory_id=f"judge_{predicate}_{subject.split(':')[-1]}_{t}",
                owner=occasions[0].owner, type="judgement", content=content,
                importance=min(0.9, 0.5 + 0.08 * len(occasions)),
                emotional_valence=valence, world_time=t, presentations=[t],
                episodes=len(occasions), about=(subject, predicate),
                evidence=tuple(m.memory_id for m in strongest))
            memories.append(judgement)
            reasons.append(("memory.judgement_formed", float(len(occasions)),
                            {"about": subject, "pattern": predicate,
                             "occasions": len(occasions), "content": content,
                             "from_episodes": list(judgement.evidence),
                             "note": "the episodes fade; the pattern does not"}))
        return reasons
