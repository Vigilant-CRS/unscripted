"""One place to change how a world behaves, without changing the runtime.

Seventy-nine numbers decide how this simulation feels: how readily people talk,
how fast a detail is lost in a retelling, how long a memory stays reachable, how
much of somebody's mood rubs off, how long a promise has. Exactly one engine --
diffusion -- ever read any of them from a world pack. Every other constant lived
in Python, so a studio that wanted a gossipier town, longer memories or rarer
distortion had to edit the SDK.

That is the wrong seam. A world pack is content, and *how this world works* is
content too: a mediaeval village and a surveillance state are not the same
simulation with different names in it. So every engine's parameters are
authorable from one block:

    // world.json
    "tuning": {
      "diffusion": { "distortion_prob": 0.30 },
      "memory":    { "tau_ret": -1.2 },
      "contagion": { "transfer": 0.20 },
      "promises":  { "horizon_minutes": 720 }
    }

THREE RULES, AND THE FIRST IS THE ONE THAT MATTERS.

**An unknown key is an error, never a shrug.** A tuning value silently ignored
because it was misspelled is the worst failure this file could have: the world
behaves as though nothing was set, the author believes it was, and the gap
between them is invisible. Every name is checked against what the engine
actually has, and a near miss is named back.

**Types are checked.** A string where a number belongs would either crash deep
inside a tick or, worse, compare as something unexpected.

**Nothing here changes what is POSSIBLE, only how much.** These are rates and
thresholds. No amount of tuning makes a character know something they were never
told, or say something the validator would stop -- so a pack cannot tune its way
out of the guarantees the runtime exists to make.
"""
from __future__ import annotations

#: Which runtime attributes may be tuned, and what each governs. The values are
#: for `unscripted tune`, which prints this so an author does not have to read source
#: to find out what a knob does.
TUNABLE = {
    "belief": "how much a source's word is worth, and how fast a repeated "
              "rumour stops counting",
    "memory": "how long things stay reachable, how much is kept, how much "
              "interferes",
    "affect": "how hard an event hits a mood and how fast it relaxes",
    "diffusion": "how often people meet and talk, how far a claim travels, and "
                 "how often a detail is lost",
    "pursuit": "how often somebody acts on a goal, and whom they reach for",
    "contagion": "how much of a speaker's mood moves to the listener",
    "notes": "how long a note lies unread, and how likely the wrong person "
             "finds it",
    "promises": "how long a promise has, and what counts as keeping it",
    "common_knowledge": "how big a crowd has to be, and how public a place",
    "policy": "how decisively characters choose between options",
    "relationship": "how fast trust is gained and lost",
    "reputation": "how fast a reputation moves and fades",
    "identity": "what decides which identity somebody leads with",
    "socioling": "how strongly register follows education, role and mood",
}


#: Bounds for the parameters where a value outside them either crashes the
#: runtime or means nothing. `(low, high, low_open, high_open)` -- an open bound
#: excludes the endpoint.
#:
#: These are not style. Measured by driving every parameter to its extremes:
#: `belief.kappa_max = 1.0` divides by zero inside the log-odds update,
#: `kappa_min = 0.0` takes the log of zero, and `affect.tau_mood = 0` divides by
#: zero in the decay. All three are values a pack could legally set, and all
#: three crashed mid-tick with a traceback from three files away.
#:
#: Only parameters with a bound that can be JUSTIFIED are listed. Inventing a
#: plausible-looking range for the rest would refuse worlds for no reason, and
#: the whole point of this surface is that a studio can build a world that does
#: not resemble the reference packs.
RANGES = {
    # A source's credibility is a probability, and the log-odds update takes
    # log(k / (1 - k)): neither endpoint exists.
    ("belief", "kappa_min"): (0.0, 1.0, True, True),
    ("belief", "kappa_max"): (0.0, 1.0, True, True),
    ("belief", "rho_correlated"): (0.0, 1.0, False, True),
    ("belief", "provenance_limit"): (1, None, False, False),
    # Time constants divide.
    ("affect", "tau_mood"): (0.0, None, True, False),
    ("affect", "tau_emotion"): (0.0, None, True, False),
    # Caps of zero silently discard everything they cap, which looks exactly
    # like a layer being broken.
    ("memory", "episodic_cap"): (1, None, False, False),
    ("memory", "total_cap"): (1, None, False, False),
    ("memory", "working_cap"): (1, None, False, False),
    ("memory", "presentation_window"): (1, None, False, False),
    ("notes", "max_per_place"): (1, None, False, False),
    ("notes", "lifetime_minutes"): (0, None, True, False),
    ("promises", "max_open_per_agent"): (1, None, False, False),
    ("promises", "horizon_minutes"): (0, None, True, False),
    ("pursuit", "interval_minutes"): (0.0, None, True, False),
    ("diffusion", "max_hops"): (1, None, False, False),
    ("diffusion", "bystanders"): (0, None, False, False),
    ("diffusion", "fidelity_decay"): (0.0, 1.0, True, False),
    ("diffusion", "distortion_prob"): (0.0, 1.0, False, False),
    ("diffusion", "stifle_prob"): (0.0, 1.0, False, False),
    ("diffusion", "min_confidence_to_tell"): (0.0, 1.0, False, False),
    ("diffusion", "encounters_per_hour"): (0.0, None, False, False),
    ("contagion", "transfer"): (0.0, 1.0, False, False),
    ("contagion", "max_step"): (0.0, 1.0, True, False),
    ("contagion", "min_tie"): (0.0, None, False, False),
    # Two people who both know a thing are a conversation, not a crowd. Three is
    # the smallest honest number and the module says why; two is the hard floor
    # below which the word stops meaning anything.
    ("common_knowledge", "min_witnesses"): (2, None, False, False),
    ("common_knowledge", "public_privacy"): (0.0, 1.0, False, False),
    ("common_knowledge", "min_quality"): (0.0, 1.0, False, False),
    ("promises", "kept_margin"): (0.0, 1.0, False, False),
    ("pursuit", "min_confidence"): (0.0, 1.0, False, False),
    ("pursuit", "max_per_tick"): (0, None, False, False),
    ("policy", "temperature"): (0.0, None, True, False),
    ("relationship", "eta_up"): (0.0, None, False, False),
    ("relationship", "eta_down"): (0.0, None, False, False),
}


def _range_text(low, high, low_open, high_open) -> str:
    left = ("greater than" if low_open else "at least") + f" {low}"
    if high is None:
        return left
    right = ("less than" if high_open else "at most") + f" {high}"
    return f"{left} and {right}"


class TuningError(ValueError):
    """A tuning block that cannot be applied, naming what is wrong with it."""


def _near(name: str, known) -> str:
    """A 'did you mean' for the commonest kind of mistake, which is a typo."""
    name = name.lower().replace("-", "_")
    close = [k for k in known
             if k.lower().startswith(name[:4]) or name.startswith(k.lower()[:4])]
    return f" Did you mean {', '.join(sorted(close)[:3])}?" if close else ""


def check(tuning: dict, core) -> list:
    """Validate a tuning block against a live runtime. Returns warnings.

    Raises :class:`TuningError` on anything that would not take effect, which is
    the whole point: silence here is indistinguishable from success.
    """
    if not isinstance(tuning, dict):
        raise TuningError(f"'tuning' must be an object, not a "
                          f"{type(tuning).__name__}")
    warnings = []
    for engine_name, values in tuning.items():
        if engine_name not in TUNABLE:
            raise TuningError(
                f"'tuning.{engine_name}' is not a tunable part of the runtime."
                + _near(engine_name, TUNABLE)
                + f" Tunable: {', '.join(sorted(TUNABLE))}.")
        engine = getattr(core, engine_name, None)
        params = getattr(engine, "params", None)
        if not isinstance(params, dict):
            warnings.append(f"tuning.{engine_name}: this build has no "
                            f"parameters for it; ignored")
            continue
        if not isinstance(values, dict):
            raise TuningError(f"'tuning.{engine_name}' must be an object, not a "
                              f"{type(values).__name__}")
        for key, value in values.items():
            if key not in params:
                raise TuningError(
                    f"'tuning.{engine_name}.{key}' is not a parameter of "
                    f"{engine_name}." + _near(key, params)
                    + f" It has: {', '.join(sorted(params))}.")
            current = params[key]
            if isinstance(current, bool) and not isinstance(value, bool):
                raise TuningError(f"'tuning.{engine_name}.{key}' must be true "
                                  f"or false")
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TuningError(
                        f"'tuning.{engine_name}.{key}' must be a number, not a "
                        f"{type(value).__name__}")
                bound = RANGES.get((engine_name, key))
                if bound is not None:
                    low, high, low_open, high_open = bound
                    too_low = value <= low if low_open else value < low
                    too_high = (high is not None
                                and (value >= high if high_open else value > high))
                    if too_low or too_high:
                        raise TuningError(
                            f"'tuning.{engine_name}.{key}' is {value}; it must "
                            f"be {_range_text(low, high, low_open, high_open)}. "
                            f"Outside that it either crashes the runtime or "
                            f"means nothing.")
    return warnings


def apply(core, tuning: dict) -> list:
    """Apply a validated tuning block. Returns one reason entry per change.

    Applied after every engine is constructed, so a pack overrides the default
    rather than racing it, and the trace records what the world asked for --
    a scene behaving oddly should not require diffing a JSON file against the
    source of the runtime.
    """
    if not tuning:
        return []
    check(tuning, core)
    reasons = []
    for engine_name, values in sorted(tuning.items()):
        engine = getattr(core, engine_name, None)
        params = getattr(engine, "params", None)
        if not isinstance(params, dict):
            continue
        for key, value in sorted(values.items()):
            was = params[key]
            params[key] = value
            if was != value:
                reasons.append(("tuning.applied", 1.0, {
                    "engine": engine_name, "parameter": key,
                    "default": was, "authored": value}))
    return reasons


def describe(core) -> list:
    """Every knob, its current value and what its engine governs.

    What `unscripted tune` prints. An author should be able to find out what they can
    change without reading the runtime's source, which until now was the only
    way.
    """
    rows = []
    for engine_name, what in sorted(TUNABLE.items()):
        engine = getattr(core, engine_name, None)
        params = getattr(engine, "params", None)
        if not isinstance(params, dict):
            continue
        rows.append({"engine": engine_name, "governs": what,
                     "parameters": {k: params[k] for k in sorted(params)}})
    return rows
