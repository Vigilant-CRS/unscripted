"""Appearance: how somebody is read before they have said anything.

Every character in every shipped pack authors an appearance -- a garment, and
sometimes a symbol worn on it -- and until now exactly one thing read it: the
character generator, to write a sentence of description. `social_status` even
promised in its own docstring to be "reputation- and appearance-mediated" and
consulted only reputation.

So this module answers one question: **what does this person's appearance do to
how they are taken?** Two effects, because they are the two that a player
notices and they are not the same thing:

    status   how seriously they are taken. A tailored suit is deferred to; a
             worn coat is talked over. This lands on perceived social status,
             which the register already reads -- so it changes how somebody
             speaks to you before they know anything about you.

    threat   how dangerous they seem. Gang colours are not low-status, they are
             something else entirely, and the difference is the whole point of
             having two numbers rather than one.

WHO READS IT, AND HOW MUCH. Not everybody judges a coat equally, so an observer
carries `epistemic.appearance_sensitivity` -- 1.0 unless a pack says otherwise,
0.0 for somebody who genuinely does not care what you are wearing. And a symbol
may `signal` a circle: somebody wearing the Reds' jacket is read as one of the
Reds, whether or not they are, which is what a symbol is for.

INERT UNTIL A PACK SAYS OTHERWISE. With no `appearance_reactions` in
`world.json` -- and no shipped pack has one yet -- every read is empty, nothing
is consumed, and a run reproduces byte-identically. That is why this is not an
optional layer with a flag: authored data that defaults to nothing needs no
switch, and a switch nobody has to set is a switch nobody has to read about.

WHAT IT DELIBERATELY DOES NOT DO. It does not change what anybody believes. Being
read as dangerous makes a character wary of you; it does not make them think you
did anything. Evidence comes from events, and a coat is not evidence.
"""
from __future__ import annotations

#: Effect of being read as dangerous on what a character would rather do. Same
#: order as the outcome values already in the action catalogue -- evading is
#: worth +0.3 safety -- and not larger: how somebody is dressed should tip a
#: close call and lose to what they have actually done.
THREAT_PULL = 0.35

#: And of being read as somebody worth taking seriously. Lower, because status
#: works through the register rather than through the decision: it changes how
#: you are spoken to more than whether you are answered at all.
STATUS_PULL = 0.15

#: Which actions a reading pushes, and which way. Pushes rather than value
#: terms: terms inside a group are averaged, so a modifier contributed as a term
#: can lower the thing it meant to raise -- which is exactly what happened, and
#: somebody dressed to look dangerous made a character LESS likely to back away.
THREAT_ACTIONS = {"evade": +1.0, "greet": -0.7, "answer_truthfully": -0.5}
STATUS_ACTIONS = {"answer_truthfully": +1.0, "greet": +0.6}


class AppearanceEngine:
    """Turns what somebody is wearing into how they are read."""

    module_id = "appearance"
    version = "1.0.0"

    # ------------------------------------------------------------- reading --

    def tokens(self, agent) -> list:
        """Every appearance token on this character: garment first, then symbols.

        Authored as `{"garment": "item:apron", "symbols": ["sym:reds"]}`, and a
        pack may add any other key it likes -- `mask`, `boots`, `scars` -- and
        the reactions table decides which of them mean anything here.
        """
        appearance = getattr(agent, "appearance", None) or {}
        found = []
        for key, value in sorted(appearance.items()):
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, (list, tuple)):
                found += [str(v) for v in value]
        return found

    def read(self, observer, agent, world) -> dict:
        """`{status, threat, signals, tokens}` -- how `observer` reads `agent`.

        Returns zeroes and empty lists when the pack authors no reactions, which
        is every pack today, which is why this changes nothing until somebody
        wants it to.
        """
        reactions = getattr(world, "appearance_reactions", None) or {}
        tokens = self.tokens(agent)
        if not reactions or not tokens:
            return {"status": 0.0, "threat": 0.0, "signals": [], "tokens": tokens}

        sensitivity = 1.0
        if observer is not None:
            epistemic = getattr(observer, "epistemic", None) or {}
            sensitivity = float(epistemic.get("appearance_sensitivity", 1.0))
        sensitivity = max(0.0, min(1.0, sensitivity))

        status = threat = 0.0
        signals = []
        for token in tokens:
            spec = reactions.get(token)
            if not spec:
                continue
            status += float(spec.get("status", 0.0))
            threat += float(spec.get("threat", 0.0))
            signal = spec.get("signals")
            if signal and signal not in signals:
                signals.append(str(signal))
        return {"status": max(-1.0, min(1.0, status)) * sensitivity,
                "threat": max(0.0, min(1.0, threat)) * sensitivity,
                "signals": signals, "tokens": tokens}

    # ----------------------------------------------------------- attraction --

    def drawn_to(self, observer, agent, world) -> float:
        """How far this observer is drawn to how this person looks, in [0, 1].

        A SEPARATE AXIS, not a flavour of liking. You can be drawn to somebody
        you do not trust and do not respect, and a runtime that folded this into
        liking could not tell an author which of the two it had modelled.

        Authored, and only authored: `epistemic.drawn_to` on a character lists
        the appearance tokens they are taken with. There is no engine here that
        decides what is attractive, because that is a fact about a person and a
        setting and not about software, and inventing one would be putting a
        number where a characterisation belongs.

        Familiarity is deliberately absent. Being drawn to a stranger across a
        room is the case worth modelling; growing fond of somebody over years is
        `liking`, which already exists and already moves.
        """
        wanted = set((getattr(observer, "epistemic", None) or {}).get("drawn_to") or ())
        if not wanted:
            return 0.0
        seen = set(self.tokens(agent))
        if not seen:
            return 0.0
        hits = wanted & seen
        if not hits:
            return 0.0
        # Two things they are taken with is more than one, and four is not four
        # times one. Saturating, because being struck by somebody does not add up.
        return min(1.0, 0.55 * len(hits) ** 0.5)

    # ------------------------------------------------------------ deciding --

    def bias_for(self, observer, action, other, world) -> float:
        """How a reading pulls what this character would rather do.

        Kept separate from the standing layer on purpose: standing is what you
        have DONE, and this is what you LOOK like, and a runtime that mixed them
        could not tell a studio which of the two it was reacting to.
        """
        if other is None or getattr(action, "target", None) != other.id:
            return 0.0
        reading = self.read(observer, other, world)
        pushed = 0.0
        for table, pull, amount in ((THREAT_ACTIONS, THREAT_PULL, reading["threat"]),
                                    (STATUS_ACTIONS, STATUS_PULL, reading["status"])):
            if abs(amount) < 1e-3:
                continue
            direction = table.get(getattr(action, "action_id", ""))
            if direction is None:
                continue
            pushed += pull * direction * amount
        return pushed
