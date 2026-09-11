"""Semantic QA: find the shortest sequence of player actions that breaks a world.

A golden scenario proves that a playthrough *somebody thought of* still behaves.
That is the wrong shape for the failure studios actually ship: nobody writes a
test for the leak they did not imagine. The question a narrative designer has is
the opposite one --

    "Is there ANY way the player can make Clara know this before quest 4?"

-- and it is answerable here for a reason no prompt-driven NPC system can copy.
The runtime is deterministic and its state is inspectable, so a rule can be
checked against the *world* rather than against a string, and the same seed can
be replayed from the start as many times as the search needs.

WHAT THIS IS NOT. It is a bounded search, not a proof. It explores a closed
catalogue of player actions to a stated depth within a stated budget, and it
reports both numbers next to every verdict. `HELD` here means "no counterexample
within this envelope", never "impossible" -- and a report that let those two read
the same would be worse than no report.

Rules are deliberately few and each one is a question an author asks anyway:

    never_believed          may this get out at all, and to whom?
    max_independent_sources can repetition turn one witness into three?
    provenance_complete     can anyone come to know something from nowhere?
    never_spoken            can this phrase reach the player's screen?
"""
from __future__ import annotations

import json
import os
import time

from .contracts import RuntimeConfig
from .sdk import UnscriptedRuntime

RULE_TYPES = ("never_believed", "max_independent_sources", "provenance_complete",
              "never_spoken")

#: What the search may try, in the order it tries it. Cheap and common first, so
#: the shortest path found is also the most ordinary one -- a leak reachable by
#: asking twice is a very different report from one that needs a threat, a bribe
#: and a radio broadcast.
DEFAULT_BUDGET = 1500
DEFAULT_DEPTH = 3


# ------------------------------------------------------------------ rules ----

class Violation:
    """One rule broken, with everything needed to act on it."""

    def __init__(self, rule: dict, path: list, detail: str, witnesses: list):
        self.rule = rule
        self.path = list(path)
        self.detail = detail
        self.witnesses = witnesses

    def as_dict(self) -> dict:
        return {"rule": self.rule.get("id", self.rule.get("type")),
                "type": self.rule["type"], "path": self.path,
                "detail": self.detail, "witnesses": self.witnesses,
                "fix": fix_hint(self.rule)}


def fix_hint(rule: dict) -> str:
    """What an author would actually change. Stated as options, not as an order."""
    return {
        "never_believed":
            "Either the disclosure gate is too weak (raise the trust threshold or "
            "add the proposition to the holder's protected set in secrets.json), or "
            "the route is legitimate and the rule is wrong -- check the source chain "
            "below before changing anything.",
        "max_independent_sources":
            "Independent corroboration is being counted where there is one origin. "
            "Check that the relaying channel preserves `origin_event` rather than "
            "minting a new one; a broadcast that re-originates a claim is the usual "
            "cause.",
        "provenance_complete":
            "A belief arrived without a source. That is an engine defect rather than "
            "an authoring one -- every path into a belief is supposed to carry the "
            "claim it came from.",
        "never_spoken":
            "The phrase reached the player. Add it to the secret's surface forms so "
            "the validator scans for it, or remove it from the authored phrasings "
            "that can render it.",
    }.get(rule["type"], "")


def check(sdk, rules: list, path: list, said: list) -> list:
    """Every rule, against the world as it stands. Returns violations."""
    found = []
    for rule in rules:
        kind = rule["type"]
        if kind == "never_believed":
            found.extend(_never_believed(sdk, rule, path))
        elif kind == "max_independent_sources":
            found.extend(_max_independent_sources(sdk, rule, path))
        elif kind == "provenance_complete":
            found.extend(_provenance_complete(sdk, rule, path))
        elif kind == "never_spoken":
            found.extend(_never_spoken(rule, path, said))
    return found


def _matches(belief: dict, rule: dict) -> bool:
    proposition = belief.get("proposition") or {}
    if proposition.get("predicate") != rule["predicate"]:
        return False
    for slot, value in (rule.get("slots") or {}).items():
        if (proposition.get("slots") or {}).get(slot) != value:
            return False
    return True


def _never_believed(sdk, rule, path) -> list:
    """Who may not come to believe this, and how sure is too sure.

    The player is checked like anyone else. "Can the player find this out before
    quest 4" is the canonical version of this question, and excluding them would
    answer a different one; a world where only the player may know is written as
    `"except": ["agent:player_1"]`.
    """
    allowed = set(rule.get("except") or ())
    floor = float(rule.get("min_prob", 0.5))
    out = []
    for agent_id in sorted(sdk.world.agents):
        if agent_id in allowed:
            continue
        for belief in sdk.structured_agent(agent_id)["beliefs"]:
            if _matches(belief, rule) and belief["prob"] >= floor:
                out.append(Violation(
                    rule, path,
                    f"{sdk.agent_name(agent_id)} believes {belief['text']} at "
                    f"p={belief['prob']:.2f} (rule allows < {floor:.2f})",
                    _chain(sdk, agent_id, belief)))
    return out


def _max_independent_sources(sdk, rule, path) -> list:
    limit = int(rule.get("max", 1))
    only = rule.get("agent")
    out = []
    for agent_id in sorted(sdk.world.agents):
        if only and agent_id != only:
            continue
        for belief in sdk.structured_agent(agent_id)["beliefs"]:
            if not _matches(belief, rule):
                continue
            origins = {entry.get("origin_event") for entry in belief["provenance"]}
            origins.discard(None)
            if len(origins) > limit:
                out.append(Violation(
                    rule, path,
                    f"{sdk.agent_name(agent_id)} holds {belief['text']} on "
                    f"{len(origins)} independent origins (limit {limit}): "
                    f"{', '.join(sorted(origins))}",
                    _chain(sdk, agent_id, belief)))
    return out


def _provenance_complete(sdk, rule, path) -> list:
    out = []
    for agent_id in sorted(sdk.world.agents):
        if agent_id == sdk.config.player_id:
            continue
        for belief in sdk.structured_agent(agent_id)["beliefs"]:
            if not belief["provenance"]:
                out.append(Violation(
                    rule, path,
                    f"{sdk.agent_name(agent_id)} believes {belief['text']} with no "
                    f"recorded source at all",
                    [{"agent": agent_id, "belief": belief["text"], "provenance": []}]))
    return out


def _never_spoken(rule, path, said) -> list:
    needle = rule["text"]
    for line in said:
        if needle.lower() in line.lower():
            return [Violation(rule, path,
                              f"the phrase {needle!r} reached the player: {line[:160]!r}",
                              [])]
    return []


def _chain(sdk, agent_id, belief) -> list:
    """Who this rests on, so a report says *how* it got there and not only that it did."""
    return [{"agent": agent_id, "name": sdk.agent_name(agent_id),
             "belief": belief["text"], "prob": round(belief["prob"], 3),
             "provenance": [{"claim": entry.get("claim_id"),
                             "origin": entry.get("origin_event"),
                             "weight": entry.get("kappa")}
                            for entry in belief["provenance"]]}]


# ----------------------------------------------------------------- search ----

def action_catalogue(sdk) -> list:
    """The player actions the search may try, derived from the world itself.

    Closed by construction: every entry names a character, place or topic the
    pack declares. The search cannot invent an affordance the game does not have,
    which is the same guarantee the parser gives a player.
    """
    world = sdk.world
    player = world.agents[sdk.config.player_id]
    here = player.location

    present = sorted(a for a in world.agents
                     if a != sdk.config.player_id and world.agents[a].location == here)
    names = {aid: (world.agents[aid].public_name or aid) for aid in present}
    topics = sorted(getattr(world, "topics", {}) or {})

    actions = []
    for aid in present:
        for topic in topics:
            actions.append(f"ask {names[aid]} about {topic}")
    for aid in present:
        actions.append(f"threaten {names[aid]}")
    actions.append("radio")
    actions.append("wait 120")
    for exit_id in sorted((world.places.get(here) or {}).get("exits") or ()):
        actions.append(f"go {exit_id}")
    return actions


def _fresh(pack: str, seed_config: dict | None = None):
    config = RuntimeConfig(world_pack_path=pack, storage_path=":memory:",
                           debug_traces=False, **(seed_config or {}))
    return UnscriptedRuntime.create(config)


def search(pack: str, rules: list, *, depth: int = DEFAULT_DEPTH,
           budget: int = DEFAULT_BUDGET, progress=None) -> dict:
    """Iterative deepening for the shortest breaking sequence.

    Depth-first would find *a* path; a designer needs the *shortest*, because the
    shortest is the one a player finds by accident. Deepening costs re-running
    prefixes and buys minimality, and re-running is 0.06 ms a turn.
    """
    started = time.perf_counter()
    explored = 0
    exhausted = True

    # Depth 0: the world as authored. A rule already broken before the player
    # does anything is not a search result, it is a content bug -- and reporting
    # it as "found after 0 actions" is how it reads correctly.
    sdk = _fresh(pack)
    try:
        violations = check(sdk, rules, [], [])
    finally:
        sdk.close()
    if violations:
        return _result(pack, rules, violations, explored, depth, budget, started, True)

    for limit in range(1, depth + 1):
        frontier = [[]]
        for _ in range(limit):
            next_frontier = []
            for prefix in frontier:
                if explored >= budget:
                    exhausted = False
                    break
                sdk = _fresh(pack)
                try:
                    said = [sdk.submit_player_text(step).message or "" for step in prefix]
                    for action in action_catalogue(sdk):
                        if explored >= budget:
                            exhausted = False
                            break
                        explored += 1
                        if progress and explored % 250 == 0:
                            progress(f"{explored} sequences, depth {limit}")
                        probe = _fresh(pack)
                        try:
                            lines = list(said)
                            for step in prefix:
                                probe.submit_player_text(step)
                            lines.append(probe.submit_player_text(action).message or "")
                            path = prefix + [action]
                            violations = check(probe, rules, path, lines)
                        finally:
                            probe.close()
                        if violations:
                            return _result(pack, rules, violations, explored, depth,
                                           budget, started, True)
                        next_frontier.append(path)
                finally:
                    sdk.close()
            frontier = next_frontier
            if not frontier:
                break
    return _result(pack, rules, [], explored, depth, budget, started, exhausted)


def _result(pack, rules, violations, explored, depth, budget, started, exhausted) -> dict:
    return {
        "world_pack": os.path.basename(pack),
        "rules": [r.get("id", r["type"]) for r in rules],
        "held": not violations,
        "violations": [v.as_dict() for v in violations],
        "sequences_explored": explored,
        "depth": depth,
        "budget": budget,
        # The difference between "nothing found" and "nothing exists" is the whole
        # honesty of this tool, so it is a field rather than a footnote.
        "search_exhausted": exhausted,
        "seconds": round(time.perf_counter() - started, 1),
    }


# ----------------------------------------------------------------- report ----

def render(result: dict) -> str:
    out = ["=" * 78,
           f"  Semantic QA — {result['world_pack']}",
           "=" * 78, ""]
    if result["held"]:
        out.append(f"  HELD — no counterexample in {result['sequences_explored']:,} "
                   f"sequences up to {result['depth']} actions "
                   f"({result['seconds']}s)")
        if not result["search_exhausted"]:
            out += ["", "  The budget ran out before the space did. This is not a "
                        "proof that no", "  path exists; it is a proof that none was "
                        "found in this envelope."]
        else:
            out += ["", f"  Every sequence up to {result['depth']} actions was tried. "
                        f"Longer ones were not."]
        out += ["", "=" * 78]
        return "\n".join(out)

    for violation in result["violations"]:
        out += [f"  BROKEN — {violation['rule']}", ""]
        steps = violation["path"]
        if not steps:
            out += ["  The world is already in this state before the player acts.", ""]
        else:
            out += [f"  Shortest path found ({len(steps)} action"
                    f"{'s' if len(steps) != 1 else ''}):", ""]
            out += [f"    {i}. {step}" for i, step in enumerate(steps, 1)]
            out.append("")
        out += [f"  {violation['detail']}", ""]
        for witness in violation["witnesses"]:
            out.append(f"  {witness['name']} — {witness['belief']} "
                       f"(p={witness['prob']})")
            for entry in witness["provenance"] or [{"claim": "(none)", "origin": None,
                                                    "weight": None}]:
                out.append(f"      via {entry['claim']}"
                           f"{' from ' + str(entry['origin']) if entry['origin'] else ''}")
            out.append("")
        out += ["  Fix:", f"    {violation['fix']}", ""]
    out += [f"  {result['sequences_explored']:,} sequences explored in "
            f"{result['seconds']}s", "=" * 78]
    return "\n".join(out)


def load_rules(path: str) -> tuple:
    """Read a rules file, and refuse one that cannot mean what it says."""
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    rules = spec.get("rules") or []
    if not rules:
        raise ValueError(f"{path} declares no rules")
    for rule in rules:
        kind = rule.get("type")
        if kind not in RULE_TYPES:
            raise ValueError(f"unknown rule type {kind!r} in {path}. "
                             f"Known: {', '.join(RULE_TYPES)}")
        if kind in ("never_believed", "max_independent_sources") and not rule.get("predicate"):
            raise ValueError(f"rule {rule.get('id', kind)!r} needs a `predicate`")
        if kind == "never_spoken" and not rule.get("text"):
            raise ValueError(f"rule {rule.get('id', kind)!r} needs a `text` to look for")
    return spec, rules
