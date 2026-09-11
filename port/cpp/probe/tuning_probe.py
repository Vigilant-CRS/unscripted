"""Does a pack's `tuning` block do the same thing in C++ as in Python?

WHY THIS PROBE EXISTS, AND WHAT IT IS GUARDING. Python applies a tuning block by
writing into `engine.params`, which IS the engine's storage. C++ has no
reflection, so its engines carry parameters as typed members and something has to
say that the name `kappa0` means that member of that struct. That something is an
explicit list of names in each engine's `knobs()` table -- and an explicit list is
a copy, and a copy drifts.

The failure it drifts into is the worst one this part of the runtime has. A
parameter added to an engine and forgotten in its table does not crash and does
not warn: the pack sets it, the author believes it, and nothing happens. That is
the exact failure `tuning.py` was written to prevent, and this port had it in its
strongest form for months -- the block was validated and then reached no engine
at all.

So this compares the two, and it compares more than the values:

  - every ENGINE, in order
  - every PARAMETER of every engine, in order -- insertion order is load-bearing
    in this runtime and a reordered dictionary exports a different state
  - every VALUE, as raw bits for floats rather than as text
  - what a tuning block CHANGES, and the reason rows it produces, which are what
    a trace shows somebody debugging a scene

    python3 port/cpp/probe/tuning_probe.py

Needs a C++ compiler. `CXX` picks one; without it, g++.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_ROOT = os.path.dirname(HERE)                      # .../port/cpp
REPO_ROOT = os.path.dirname(os.path.dirname(PORT_ROOT))
INCLUDE = os.path.join(PORT_ROOT, "include")

sys.path.insert(0, REPO_ROOT)

from unscripted.runtime import Runtime          # noqa: E402
from unscripted.tuning import TUNABLE           # noqa: E402
from unscripted.world import World              # noqa: E402
from unscripted import tuning as tuning_module  # noqa: E402


def build(binary: str) -> None:
    """Compile the probe, or say why it could not be compiled."""
    compiler = os.environ.get("CXX") or "g++"
    command = [compiler, "-std=c++17", "-O1", "-I", INCLUDE,
               os.path.join(HERE, "tuning_probe.cpp"), "-o", binary]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("the tuning probe does not compile:\n" + done.stderr)


def run(binary: str, block: dict | None) -> dict:
    argv = [binary] if block is None else [binary, json.dumps(block)]
    done = subprocess.run(argv, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("the tuning probe crashed:\n" + done.stdout + done.stderr)
    return json.loads(done.stdout)


def python_side(block: dict | None) -> tuple:
    """The same thing in Python: the parameter table, and the reasons."""
    world = World()
    core = Runtime(world)
    reasons = tuning_module.apply(core, block) if block else []
    table = {}
    for name in TUNABLE:
        params = getattr(getattr(core, name), "params")
        table[name] = dict(params)
    return table, [list(one) for one in reasons]


def bits(value) -> str:
    """A float compared as bits, not as text -- 0.1 and 0.1 must be the SAME 0.1."""
    if isinstance(value, bool):
        return "bool:%s" % value
    if isinstance(value, float):
        return "f64:%s" % struct.pack("<d", value).hex()
    if isinstance(value, int):
        return "int:%d" % value
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "{%s}" % ",".join("%s=%s" % (k, bits(v)) for k, v in value.items())
    return "str:%s" % value


def compare_tables(cpp: dict, py: dict, what: str) -> None:
    if list(cpp) != list(py):
        raise SystemExit(
            "%s: the ENGINES differ, or their order does.\n  C++:    %s\n  Python: %s"
            % (what, list(cpp), list(py)))
    for engine in py:
        got, want = cpp[engine], py[engine]
        if list(got) != list(want):
            missing = [k for k in want if k not in got]
            extra = [k for k in got if k not in want]
            detail = ""
            if missing:
                detail += ("\n  NOT BOUND IN C++: %s -- a pack setting one of "
                           "these would be validated and then ignored, which is "
                           "the failure this probe exists to catch. Add it to "
                           "%s's knobs() table." % (missing, engine))
            if extra:
                detail += "\n  bound in C++ but not a Python parameter: %s" % extra
            raise SystemExit(
                "%s: %s has different parameters, or a different order.%s"
                "\n  C++:    %s\n  Python: %s"
                % (what, engine, detail, list(got), list(want)))
        for key in want:
            if bits(got[key]) != bits(want[key]):
                raise SystemExit(
                    "%s: %s.%s differs.\n  C++:    %r (%s)\n  Python: %r (%s)"
                    % (what, engine, key, got[key], bits(got[key]),
                       want[key], bits(want[key])))


def compare_reasons(cpp: list, py: list, what: str) -> None:
    if len(cpp) != len(py):
        raise SystemExit("%s: %d reason(s) in C++, %d in Python\n  C++:    %s\n"
                         "  Python: %s" % (what, len(cpp), len(py), cpp, py))
    for got, want in zip(cpp, py):
        if got[0] != want[0] or bits(got[1]) != bits(want[1]):
            raise SystemExit("%s: reason head differs\n  C++:    %s\n  Python: %s"
                             % (what, got, want))
        if list(got[2]) != list(want[2]):
            raise SystemExit("%s: reason detail keys differ or are reordered\n"
                             "  C++:    %s\n  Python: %s" % (what, got[2], want[2]))
        for key in want[2]:
            if bits(got[2][key]) != bits(want[2][key]):
                raise SystemExit("%s: reason detail %s differs\n  C++:    %r\n"
                                 "  Python: %r" % (what, key, got[2][key], want[2][key]))


#: One block per kind of knob, plus one that touches every engine at once. The
#: point is coverage of the BINDING, not of the arithmetic -- `tuning.hpp` is
#: already held to Python by the engine probe.
CASES = [
    ("the defaults, untouched", None),
    ("a float", {"belief": {"kappa0": 0.9}}),
    ("a count", {"memory": {"working_cap": 3}}),
    ("a boolean", {"policy": {"use_prospect": True},
                   "diffusion": {"include_player": True}}),
    ("a table of weights",
     {"diffusion": {"distortion_weights": {"levelling": 0.5, "sharpening": 0.5}}}),
    ("the three engines whose numbers used to be compile-time constants",
     {"notes": {"max_per_place": 3, "lifetime_minutes": 60, "intercept_base": 0.5},
      "promises": {"horizon_minutes": 60, "kept_margin": 0.5,
                   "max_open_per_agent": 2},
      "common_knowledge": {"min_witnesses": 5, "public_privacy": 0.9,
                           "min_quality": 0.9}}),
    ("every engine at once",
     {"belief": {"alpha": 0.3}, "memory": {"noise_s": 0.5}, "affect": {"epsilon": 0.1},
      "diffusion": {"min_tie": 0.2}, "pursuit": {"min_confidence": 0.7},
      "contagion": {"transfer": 0.2}, "notes": {"intercept_base": 0.03},
      "promises": {"kept_margin": 0.01}, "common_knowledge": {"min_quality": 0.6},
      "policy": {"temperature": 0.5}, "relationship": {"eta_up": 0.2},
      "reputation": {"decay": 0.002}, "identity": {"beta": 5.0},
      "socioling": {"w_edu": 0.5}}),
    ("a value equal to the default, which must produce NO reason row",
     {"belief": {"kappa0": 0.55}}),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as work:
        binary = os.path.join(work, "tuning_probe")
        build(binary)
        knobs = 0
        for what, block in CASES:
            got = run(binary, block)
            want_table, want_reasons = python_side(block)
            compare_tables(got["parameters"], want_table, what)
            compare_reasons(got["reasons"], want_reasons, what)
            if block is None:
                knobs = sum(len(v) for v in want_table.values())
    print("  tuning: %d knobs across %d engines reach the C++ engines and agree "
          "with Python, over %d blocks" % (knobs, len(TUNABLE), len(CASES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
