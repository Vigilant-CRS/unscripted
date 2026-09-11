"""Dialogue planner (spec v0.5 §6.2, §3.7; review P1.9).

Turns a chosen dialogue action into a DialoguePlan: speech act, topic, allowed
facts (only what the NPC believes above threshold and may disclose), forbidden
facts (secrets -- their CONTENT is never put in the plan, only avoid-topics),
stance, and the style vector. Anti-loop ensures each turn does something new.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from . import commitment, content


@dataclass
class ConversationState:
    conv_id: str
    participants: list
    active_topic: str = None
    common_ground: set = field(default_factory=set)     # proposition core_keys both know
    open_questions: list = field(default_factory=list)
    resolved: set = field(default_factory=set)
    turn_count: int = 0
    last_acts: list = field(default_factory=list)
    discussed_topics: dict = field(default_factory=dict)  # topic -> times asked (continuity)
    last_world_time: int = 0                              # for resume across save/load
    recent_lines: list = field(default_factory=list)      # last utterances (anti-repeat)

    def note_topic(self, topic: str, world_time: int) -> int:
        """Record that a topic was discussed; return how many times now (>=1)."""
        self.discussed_topics[topic] = self.discussed_topics.get(topic, 0) + 1
        self.last_world_time = world_time
        return self.discussed_topics[topic]

    def as_dict(self) -> dict:
        return {"conv_id": self.conv_id, "participants": list(self.participants),
                "active_topic": self.active_topic, "turn_count": self.turn_count,
                "last_acts": list(self.last_acts), "discussed_topics": dict(self.discussed_topics),
                "last_world_time": self.last_world_time, "recent_lines": list(self.recent_lines)}

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationState":
        c = cls(d["conv_id"], list(d.get("participants", [])),
                active_topic=d.get("active_topic"), turn_count=d.get("turn_count", 0),
                last_acts=list(d.get("last_acts", [])))
        c.discussed_topics = dict(d.get("discussed_topics", {}))
        c.last_world_time = d.get("last_world_time", 0)
        c.recent_lines = list(d.get("recent_lines", []))
        return c


@dataclass
class DialoguePlan:
    speaker: str
    addressee: str
    dialogue_act: str
    goal: str
    #: What the runtime has COMMITTED this character to saying. The text layer
    #: renders these and selects nothing. Empty means "assert no fact".
    moves: tuple = ()
    #: Rendered form of the committed propositions. Kept as a plain list because
    #: the validator licenses specifics against it and persistence stores it; it
    #: is always exactly the commitment, never a menu to choose from.
    allowed_facts: list = field(default_factory=list)
    avoid_topics: list = field(default_factory=list)     # topic labels to steer away from (NOT the secret content)
    stance: str = "asserted"
    style: dict = field(default_factory=dict)
    fallback_template_id: str = "deflect"
    max_length: int = 30
    #: Authored register variants for THIS answer (topics.json). When empty the
    #: realizer falls back to a stance template and asserts nothing factual.
    phrasing: dict = field(default_factory=dict)
    #: Stable id for this generation, so a line that misses the frame budget can be
    #: matched back to the turn it belongs to when it arrives late.
    request_id: str = ""

    def commit(self, commitment) -> "DialoguePlan":
        """Adopt a commitment: the moves become the plan's only factual content."""
        self.moves = tuple(commitment.moves)
        self.allowed_facts = list(commitment.rendered_facts())
        if commitment.forbidden:
            self.avoid_topics = list(commitment.forbidden)
        return self

    @property
    def committed_propositions(self) -> list:
        return [m.proposition for m in self.moves if m.proposition is not None]


class DialoguePlanner:
    module_id = "dialogue_planner"
    version = "0.6.0"

    C_ASSERT = 0.6   # min belief confidence to state as fact

    #: Acts that state something about the world. Everything else -- evading,
    #: deflecting, greeting, threatening -- commits to no fact, and a plan that
    #: commits to no fact hands the text layer nothing to choose from.
    ASSERTING_ACTS = ("inform", "answer", "confide", "warn")

    def plan(self, agent, conv: ConversationState, chosen_action, *, addressee, style, goal,
             world_seed: str = "", world_time: int = 0):
        act = chosen_action.action.dialogue_act or "inform"
        avoid = content.avoid_labels(agent.secrets)
        stance = "deceptive" if act == "evade" else "asserted"
        plan = DialoguePlan(speaker=agent.id, addressee=addressee, dialogue_act=act, goal=goal,
                            avoid_topics=avoid, stance=stance,
                            style=style.as_dict() if hasattr(style, "as_dict") else dict(style))

        # The runtime decides what is said. This used to build a list of every
        # belief above threshold and hand it over, which left the choice of what
        # a character actually discloses to whatever rendered the text.
        if act in self.ASSERTING_ACTS:
            protected = content.protected_keys(agent.secrets)
            candidates = []
            for belief in agent.beliefs.values():
                if belief.expected_prob < self.C_ASSERT:
                    continue
                if (belief.proposition.core_key() in protected
                        or str(belief.proposition) in protected):
                    continue
                candidates.append(commitment.Candidate(
                    proposition=belief.proposition, confidence=belief.expected_prob,
                    relevance=1.0, affirmed=True))
            plan.commit(commitment.select(
                candidates, act="assert", limit=1,
                seed_parts=(world_seed, agent.id, conv.turn_count, world_time, "deliberate"),
                forbidden=avoid))
        else:
            plan.commit(commitment.Commitment(moves=(), forbidden=tuple(avoid)))

        conv.turn_count += 1
        conv.last_acts.append(act)
        return plan

    def anti_loop_ok(self, conv: ConversationState, act):
        """Each turn must do something new (spec v0.1 §12.6)."""
        if len(conv.last_acts) >= 3 and len(set(conv.last_acts[-3:])) == 1 and act == conv.last_acts[-1]:
            return False
        return True
