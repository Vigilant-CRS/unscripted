"""What to do when a source turns out to have been lying.

Lowering trust in a liar changes what they will manage to convince you of *next
time*. It does nothing about what they already convinced you of, and that is the
part that matters: the whole point of exposing someone is that the things they
told you stop counting.

So a belief has to be recomputable. Every piece of evidence records the signed
log-odds it contributed and who said it, and revision replays that record with
the discredited entries reweighted. The change then propagates: anyone who
believed it because *you* told them is holding evidence that traces back to the
same origin, and their belief is recomputed too.

This is a small incremental truth-maintenance system. It is deliberately not a
general one -- no justification lattice, no nogoods, no assumption sets. Those
solve a harder problem than this has, and the honest description of what happens
here is: evidence has weights, a weight changed, add it up again.

The one rule that keeps it sane: **revision only ever reweights evidence that
exists.** It never invents a belief, never removes one, and never touches a
belief that has an independent source for what it holds. Being caught in one lie
does not make everything you ever said false.
"""

from __future__ import annotations

from . import belief as belief_module

#: Compensated summation, so a port that adds in a loop and this one agree. See
#: `port/README.md`: CPython gives `sum()` a fast path over floats and a naive
#: loop disagrees in the last bit, which is a discrete difference once it decides
#: a comparison.
_sum = sum

#: How far a single exposure can discount what a source already contributed. Not
#: to zero: people who lie about one thing were sometimes telling the truth about
#: another, and a model that erases everything they said would make exposing them
#: strictly better than never having heard them.
FLOOR = 0.1


class Revision:
    """One recomputation pass and what it changed."""

    def __init__(self, source: str, factor: float, reason: str):
        self.source = source
        self.factor = factor
        self.reason = reason
        self.changes: list = []
        self.reasons: list = []

    @property
    def touched(self) -> int:
        return len(self.changes)

    def as_dict(self) -> dict:
        return {"source": self.source, "factor": round(self.factor, 3),
                "reason": self.reason, "beliefs_revised": self.touched,
                "changes": self.changes}


#: Characters that may sit either side of an id inside an origin token. Origins
#: are built by joining parts with these, so a match bounded by one of them is a
#: whole id rather than a coincidence.
_BOUNDARY = frozenset(("", "_", ":", "/", "|", ".", "-", " "))


def _names(origin: str, source: str) -> bool:
    """Does this origin token name `source` as a WHOLE id?

    `source in origin` was a plain substring test, and substrings of ids are
    other ids: discrediting `agent:ann` also unwound everything relayed from
    `said_agent:anna_100`, taking a bystander's belief from 0.95 to 0.676. The
    match now has to end where an id ends.
    """
    if not source or not origin:
        return False
    at = origin.find(source)
    while at >= 0:
        before = origin[at - 1] if at else ""
        end = at + len(source)
        after = origin[end] if end < len(origin) else ""
        if before in _BOUNDARY and after in _BOUNDARY:
            return True
        at = origin.find(source, at + 1)
    return False


def _key_traces_to(speaker: str, origin: str, source: str) -> bool:
    """Did evidence filed under this (speaker, origin) come from `source`?

    Directly: they said it to this listener. Down a chain: the claim carries the
    origin it started from, which survives retelling -- so a rumour three hops
    from the liar still names them.
    """
    return speaker == source or _names(origin, source)


def _traces_to(entry: dict, source: str) -> bool:
    """The same question, asked of one provenance record."""
    speaker = entry.get("speaker")
    origin = entry.get("origin_event")
    return _key_traces_to("" if speaker is None else str(speaker),
                          "" if origin is None else str(origin), source)


def discredit(world, source: str, *, factor: float = 0.25, reason: str = "exposed",
              predicate: str | None = None) -> Revision:
    """Reweight everything `source` convinced anyone of, and recompute.

    `factor` scales their past contributions: 0.25 means "a quarter of the weight
    it originally had". `predicate` narrows the revision to one kind of claim,
    because being caught lying about where someone is says little about your
    account of the weather.
    """
    factor = max(FLOOR, min(1.0, factor))
    revision = Revision(source, factor, reason)

    for agent in (getattr(world, "agents", None) or {}).values():
        if agent.id == source:
            continue                      # a liar's own beliefs are not evidence from them
        for key, belief in agent.beliefs.items():
            if predicate and belief.proposition.predicate != predicate:
                continue
            # THE ARITHMETIC COMES FROM `contributions`, NOT FROM THE
            # PROVENANCE LIST. That list is trimmed to its newest entries for
            # the inspector, so summing it silently under-corrected -- and once
            # a claim had been heard more than the retention limit, exposing the
            # only source who ever supplied it did nothing whatsoever.
            # `source_key`, not `key`: the enclosing loop is already bound to the
            # belief's key, and shadowing it here put the contribution key into
            # the change record -- so a caller looking up its own belief in the
            # result found nothing.
            matched = [source_key for source_key in belief.contributions
                       if source_key != belief_module.FORGOTTEN
                       and _key_traces_to(
                           *source_key.split(belief_module._CONTRIB_SEP, 1), source)]
            if not matched:
                continue

            before = belief.expected_prob
            positive = _sum(belief.contributions[one][0] for one in matched)
            negative = _sum(belief.contributions[one][1] for one in matched)
            adjustment = (positive + negative) * (factor - 1.0)
            if abs(adjustment) < 1e-9:
                continue
            belief.logit_val += adjustment
            # EACH POOL LOSES WHAT IT WAS GIVEN. Adding a negative adjustment to
            # `support_against` reported the weakening of positive evidence as
            # the arrival of a contradiction: one uncontested source, discredited,
            # produced conflict 0.947 out of nothing. Weakening evidence raises
            # ignorance; only a counter-claim raises conflict.
            belief.support_for = max(0.0, belief.support_for
                                     + positive * (factor - 1.0))
            belief.support_against = max(0.0, belief.support_against
                                         + (-negative) * (factor - 1.0))
            for one in matched:
                bucket = belief.contributions[one]
                bucket[0] *= factor
                bucket[1] *= factor
            affected = [e for e in belief.provenance if _traces_to(e, source)]
            independent = [e for e in belief.provenance if e not in affected]
            for entry in affected:
                entry["delta"] = round(float(entry.get("delta") or 0.0) * factor, 6)
                entry["revised"] = reason
            still_supported = any(
                one != belief_module.FORGOTTEN and one not in matched
                and any(belief.contributions[one])
                for one in belief.contributions)

            after = belief.expected_prob
            revision.changes.append({
                "agent": agent.id, "belief": key,
                "was": round(before, 4), "now": round(after, 4),
                "entries_reweighted": len(affected),
                "sources_reweighted": len(matched),
                "independent_entries": len(independent),
                "still_supported": still_supported})
            revision.reasons.append((
                "revision.recomputed", round(after - before, 4),
                {"agent": agent.id, "belief": key, "source": source,
                 "reason": reason, "factor": round(factor, 3),
                 "independent_support": len(independent)}))

    return revision


def would_change(world, source: str) -> list:
    """Which beliefs rest on this source, without changing anything.

    The question a player asks before deciding whether exposing someone is worth
    it, and the question a designer asks about whether a lie was load-bearing.
    """
    resting = []
    for agent in (getattr(world, "agents", None) or {}).values():
        if agent.id == source:
            continue
        for key, belief in agent.beliefs.items():
            matched = [one for one in belief.contributions
                       if one != belief_module.FORGOTTEN
                       and _key_traces_to(
                           *one.split(belief_module._CONTRIB_SEP, 1), source)]
            if matched:
                affected = [e for e in belief.provenance if _traces_to(e, source)]
                resting.append({
                    "agent": agent.id, "belief": key,
                    "probability": round(belief.expected_prob, 4),
                    "from_this_source": len(affected),
                    "sources_from_this_source": len(matched),
                    "independent": len(belief.provenance) - len(affected)})
    return resting
