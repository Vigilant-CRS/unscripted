"""Fixtures a second implementation must reproduce, byte for byte.

A console port means porting the part of this runtime that runs while somebody
is playing, because a shipped title may not start a language interpreter beside
itself. That is **9,140 lines across 49 modules** -- belief, memory, perception,
diffusion, dialogue policy, and the world loop that orders them.

That figure replaces one this file carried for a while and that was wrong in the
direction that costs somebody a schedule: 2,914 lines, which counted the
foundation and the engines and quietly left out `world` and `runtime`, where two
thirds of the work is. The remaining 9,757 lines -- authoring tools, validators,
evidence runs, the service, the CLI -- stay in Python and never ship inside a
game. `port/README.md` has the measured breakdown and the order to do it in.

THE PROBLEM THIS SOLVES IS NOT THE PORT. It is knowing whether the port is
right. The obvious answer was the thirteen golden scenarios, and I said so
before checking what they assert:

    {"input": "ask Honce about clinic",
     "expect_contains": ["Honce", "shut that night"]}

They compare **text**. A C# port phrases a sentence differently and fails them
while computing perfectly, or phrases it identically and passes them while
computing something wrong. That is the wrong granularity for a port, and using
them would have produced confident nonsense in both directions.

So a fixture here is a triple:

    (world pack, seed, commands)  ->  the exported state, as JSON

State, not prose: belief log-odds, provenance chains, relationship values, mood,
place climate. A port reproduces the blob or it does not, and the diff says
which field diverged on which agent. The text layer is free to differ, because
the text layer is not what a port has to get right.

TWO THINGS THIS WILL CATCH, and they are the two that would otherwise cost
somebody a month.

Floating point. `logit += eta * log(kappa / (1 - kappa))` has to land on the
same bits in another language. It can, and it is work rather than translation.

Iteration order. Python dictionaries preserve insertion order and C#
`Dictionary` does not, so every place that walks a collection while drawing a
seeded number needs an explicit sort. That is the class of bug that shows up
once in a thousand ticks, and a byte comparison finds it on the first.

RUNNING THEM AGAINST PYTHON IS NOT POINTLESS. Regenerating and comparing catches
an accidental behaviour change in this implementation too -- it is a second
regression net that costs nothing to keep, and it is how the fixtures stay
trustworthy enough to hold a port to.
"""
from __future__ import annotations

import json
import os

#: Bumped when the fixture layout changes in a way a consumer must notice.
FIXTURE_FORMAT = "unscripted/conformance"
FIXTURE_VERSION = 1

#: The scenarios live in `conformance/scenarios.json`, not here. Deliberately
#: small and deliberately varied: each exercises a different path into the state
#: a port has to reproduce, and a set that only ever asks questions would let a
#: port ship with a broken affect model and a clean run.
#:
#: Two reasons, and the second is the one that matters. They are data, and an
#: engine module carrying the reference pack's character names failed the
#: world-neutrality check -- rightly. And a second implementation has to read
#: them: a suite whose scenario list is a Python literal is one a C# port cannot
#: consume without a Python to parse it, which defeats the point of having it.
SCENARIOS_FILE = "scenarios.json"


def scenarios(out_dir: str = None) -> list:
    """The scenario list, from the fixtures directory or the packaged default."""
    for base in ([out_dir] if out_dir else []) + [_default_dir()]:
        path = os.path.join(base, SCENARIOS_FILE)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)["scenarios"]
    raise FileNotFoundError(
        "no %s found; regenerate with `unscripted conformance --out <dir>`"
        % SCENARIOS_FILE)


def _default_dir() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "conformance")


def run_scenario(scenario: dict, *, pack_root: str = ".") -> dict:
    """Play one scenario and return the fixture it produces."""
    from .contracts import RuntimeConfig
    from .sdk import UnscriptedRuntime

    layers = {name: True for name in scenario.get("layers", ())}
    pack = scenario["world_pack"]
    if not os.path.isabs(pack):
        candidate = os.path.join(pack_root, pack)
        if os.path.exists(candidate):
            pack = candidate
    config = RuntimeConfig(world_pack_path=pack, storage_path=":memory:", **layers)
    sdk = UnscriptedRuntime.create(config)
    try:
        # The seed belongs to the world, not to the config: a fixture that did
        # not pin it would be reproducing the pack's seed and calling it proof.
        sdk.world.global_seed = scenario["seed"]
        transcript = []
        for command in scenario["commands"]:
            result = sdk.submit_player_text(command)
            transcript.append({
                "input": command,
                # The player-facing message is recorded and NOT compared. It is
                # here so a human reading a diff can see what the run was doing;
                # a port is free to phrase it differently.
                "message_for_humans": (result.message or "").strip(),
            })
        return {
            "format": FIXTURE_FORMAT,
            "format_version": FIXTURE_VERSION,
            "id": scenario["id"],
            "why": scenario["why"],
            "world_pack": scenario["world_pack"],
            "seed": scenario["seed"],
            "layers": list(scenario.get("layers", ())),
            "commands": scenario["commands"],
            "transcript": transcript,
            "expected_state": sdk.export_state(),
        }
    finally:
        sdk.close()


def write(out_dir: str, *, pack_root: str = ".") -> list:
    """Generate every fixture. Returns the paths written."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for scenario in scenarios(out_dir):
        fixture = run_scenario(scenario, pack_root=pack_root)
        path = os.path.join(out_dir, "%s.json" % scenario["id"])
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(fixture, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        written.append(path)
    _write_readme(out_dir)
    return written


#: How far two doubles may drift apart and still count as agreeing, as a
#: multiple of the gap between adjacent doubles.
#:
#: NOT A ROUND NUMBER PICKED TO MAKE THINGS PASS. `port/cpp/probe/` replaces
#: `log()` with `nextafter(log(x))` -- the smallest disagreement two correct
#: libm implementations could have -- and re-runs every scenario here. The
#: result: 160 fields move, the worst by 1.3 ULP, and **no discrete outcome
#: changes**. The error does not compound; it stays where it started. Eight
#: leaves room for a longer run than the ones measured without leaving room for
#: a real defect, which shows up as a difference thousands of times larger.
DEFAULT_ULP_TOLERANCE = 8.0

#: The gap between 1.0 and the next double.
_EPSILON = 2.220446049250313e-16


def check(out_dir: str, *, pack_root: str = ".", ulp_tolerance: float = 0.0) -> list:
    """Re-run every fixture and report what no longer matches.

    Returns a list of `(id, field-path, expected, actual)`. Empty means this
    implementation still produces what the fixtures say it should.

    `ulp_tolerance` is for holding a *port* to these fixtures, and it should be
    0 for holding this implementation to them. The distinction matters:

    Exact is the right bar here. Nothing about this runtime should change a
    belief by one bit between two runs, so a single differing bit is a
    regression and worth failing on.

    Exact is the wrong bar for a port on a foreign toolchain. `log()` is a
    library function, not an operation IEEE-754 pins down, and two correct
    implementations may return doubles one bit apart. A port that computes
    everything right would fail every fixture for a reason that is not its
    fault and cannot be fixed in its code.

    A tolerance applies to numbers only. A different agent, a different event
    count, a different provenance chain or a different string is a failure at
    any tolerance -- those are the differences that mean the port is wrong, and
    the measurement behind `DEFAULT_ULP_TOLERANCE` found none of them.
    """
    failures = []
    for scenario in scenarios(out_dir):
        path = os.path.join(out_dir, "%s.json" % scenario["id"])
        if not os.path.exists(path):
            failures.append((scenario["id"], "<file>", path, "missing"))
            continue
        with open(path, encoding="utf-8") as handle:
            stored = json.load(handle)
        fresh = run_scenario(scenario, pack_root=pack_root)
        failures += _diff(scenario["id"], stored.get("expected_state"),
                          fresh.get("expected_state"),
                          ulp_tolerance=ulp_tolerance)
    return failures


def _close_enough(expected, actual, ulp_tolerance: float) -> bool:
    """Whether two numbers agree to within the allowed number of ULPs."""
    if not ulp_tolerance:
        return False
    if isinstance(expected, bool) or isinstance(actual, bool):
        return False        # a flipped decision, not a rounding difference
    if not isinstance(expected, (int, float)) or not isinstance(actual, (int, float)):
        return False
    gap = abs(float(expected) - float(actual))
    if gap == 0.0:
        return True
    scale = max(abs(float(expected)), abs(float(actual)))
    # Near zero the relative measure is meaningless, so fall back to the
    # absolute gap between the smallest normal doubles.
    return gap <= ulp_tolerance * _EPSILON * max(scale, 1.0)


def _diff(scenario_id, expected, actual, path="state", *, ulp_tolerance=0.0) -> list:
    """Where two state blobs differ, named field by field.

    Names the path rather than dumping both blobs. A port's first run will
    differ in a dozen places and a wall of JSON tells nobody which one to fix
    first; `state.agents.agent:vee.beliefs.shot_by(...).logit` does.
    """
    if type(expected) is not type(actual):
        # int vs float is a JSON round-trip artefact, not a divergence, so it
        # goes to the numeric comparison rather than straight to a failure.
        if not _close_enough(expected, actual, ulp_tolerance):
            return [(scenario_id, path, _short(expected), _short(actual))]
        return []
    if isinstance(expected, dict):
        out = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append((scenario_id, f"{path}.{key}", "<absent>", _short(actual[key])))
            elif key not in actual:
                out.append((scenario_id, f"{path}.{key}", _short(expected[key]), "<absent>"))
            else:
                out += _diff(scenario_id, expected[key], actual[key],
                             f"{path}.{key}", ulp_tolerance=ulp_tolerance)
        return out
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [(scenario_id, f"{path}[]", f"{len(expected)} items",
                     f"{len(actual)} items")]
        out = []
        for index, (one, two) in enumerate(zip(expected, actual)):
            out += _diff(scenario_id, one, two, f"{path}[{index}]",
                         ulp_tolerance=ulp_tolerance)
        return out
    if expected != actual and not _close_enough(expected, actual, ulp_tolerance):
        return [(scenario_id, path, _short(expected), _short(actual))]
    return []


def _short(value) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False) if not isinstance(
        value, str) else value
    return text if len(text) <= 70 else text[:67] + "..."


def _write_readme(out_dir: str) -> None:
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("""# Conformance fixtures

Generated by `unscripted conformance --out .`. Each file is one scenario:

    (world pack, seed, commands)  ->  the exported state, as JSON

**A second implementation is correct when it reproduces `expected_state`.** Not
the transcript: `message_for_humans` is recorded so a person reading a diff can
see what the run was doing, and a port is free to phrase it differently. What it
is not free to do is compute a different belief, a different provenance chain, a
different mood or a different climate.

## Why these five

| | |
| --- | --- |
| `asking` | belief, provenance, and the correlation discount -- one origin heard twice must not count twice |
| `time` | routines, diffusion and decay across a day: where iteration order and seeded sampling show up |
| `violence` | affect, identity threat, place climate -- the paths a port leaves out because nothing asks them a question |
| `conduct` | standing, including what reaches somebody who was told rather than present |
| `promises` | a commitment coming due, and reputation reaching the people who heard it made |

## The two things this exists to catch

**Floating point.** `logit += eta * log(kappa / (1 - kappa))` has to land on the
same bits in another language. It can; it is work rather than translation.

**Iteration order.** Python dictionaries preserve insertion order and C#
`Dictionary` does not, so anything that walks a collection while drawing a
seeded number needs an explicit sort. That bug shows up once in a thousand
ticks, and a byte comparison finds it on the first.

## Running them against this implementation

    unscripted conformance --check --out .

Not pointless: it catches an accidental behaviour change here too, which is what
keeps the fixtures trustworthy enough to hold a port to. When a change to this
runtime is deliberate, regenerate and read the diff before committing it.
""")
