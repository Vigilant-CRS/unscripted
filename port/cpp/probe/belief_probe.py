"""Runs the same cases through the Python belief engine, and compares.

The C++ side prints its belief store with every double as a raw bit pattern.
This runs `belief_cases.json` through `unscripted.belief` -- the real module, not a
re-implementation -- serialises it the same way, and diffs the two.

Naming the differing field matters more than counting them. A port's first run
disagrees in a dozen places, and a wall of JSON says nothing about which one to
fix; `one_origin_repeated.beliefs.was_at(...).logit` says exactly where to look
and, usually, why.

    python3 port/cpp/probe/belief_probe.py
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(PORT_ROOT))
CASES = os.path.join(HERE, "belief_cases.json")

sys.path.insert(0, REPO_ROOT)

from unscripted.belief import BeliefEngine                     # noqa: E402
from unscripted.ontology import Proposition                    # noqa: E402


def to_bits(value):
    """Every float in a blob rewritten as its raw 64 bits.

    Floats only. An int stays an int, because `1` and `1.0` are a real
    difference here: one of them means a port produced an integer where the
    reference produced a float, and that shows up in the exported state.
    """
    if isinstance(value, float):
        return "b:%016x" % struct.unpack("<Q", struct.pack("<d", value))[0]
    if isinstance(value, (list, tuple)):
        # TUPLES TOO. A reason detail carries `[(action, probability), ...]` as
        # tuples, and a tuple that fell through here kept its floats as decimal
        # numbers while the C++ side had already turned its arrays into bit
        # patterns -- so the two could never match and the mismatch read as a
        # value difference rather than as a type one.
        return [to_bits(item) for item in value]
    if isinstance(value, dict):
        return {key: to_bits(item) for key, item in value.items()}
    return value


def python_side(document: dict) -> dict:
    engine = BeliefEngine()
    report = {}
    for scenario in document["cases"]:
        beliefs, traces = {}, []
        for update in scenario["updates"]:
            repeat = update.get("repeat", 1)
            for step in range(repeat):
                claim = Proposition(update["predicate"], dict(update["slots"]),
                                    "-" if update.get("store_negated") else "+")
                origin = update.get("origin")
                if origin == "vary":
                    origin = step
                claim_id = update["claim_id"]
                if repeat > 1:
                    claim_id = "%s:%d" % (claim_id, step)
                _belief, reasons = engine.update(
                    beliefs, claim, asserter_polarity=update["polarity"],
                    trust=update["trust"], competence=update["competence"],
                    skepticism=update["skepticism"], claim_id=claim_id,
                    origin_event=origin, world_time=update["world_time"],
                    speaker=update.get("speaker"))
                if step + 1 == repeat:
                    traces.append([{"code": code, "amount": amount, "detail": detail}
                                   for code, amount, detail in reasons])
        report[scenario["id"]] = to_bits({
            "beliefs": {key: belief.as_dict() for key, belief in beliefs.items()},
            "reasons": traces,
        })
    return report


def cpp_side() -> dict:
    compiler = os.environ.get("CXX", "g++")
    with tempfile.TemporaryDirectory() as work:
        binary = os.path.join(work, "belief_probe")
        subprocess.run(
            [compiler, "-O2", "-std=c++17", "-I", os.path.join(PORT_ROOT, "include"),
             os.path.join(HERE, "belief_probe.cpp"), "-o", binary],
            check=True)
        out = subprocess.run([binary, CASES], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def differences(expected, actual, path="") -> list:
    """Field paths where two blobs disagree, deepest name first."""
    if type(expected) is not type(actual):
        return [(path, _short(expected), _short(actual))]
    if isinstance(expected, dict):
        out = []
        for key in list(expected) + [k for k in actual if k not in expected]:
            where = f"{path}.{key}" if path else key
            if key not in expected:
                out.append((where, "<absent>", _short(actual[key])))
            elif key not in actual:
                out.append((where, _short(expected[key]), "<absent>"))
            else:
                out += differences(expected[key], actual[key], where)
        # Order is part of the answer, not a detail: `primary_origin` is the
        # first key of `origin_counts`, and `core_key` walks slots in order.
        if list(expected) != list(actual) and set(expected) == set(actual):
            out.append((path or "<root>", "key order " + ", ".join(list(expected)[:4]),
                        "key order " + ", ".join(list(actual)[:4])))
        return out
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [(path + "[]", "%d items" % len(expected), "%d items" % len(actual))]
        out = []
        for index, (one, two) in enumerate(zip(expected, actual)):
            out += differences(one, two, f"{path}[{index}]")
        return out
    if expected != actual:
        return [(path, _short(expected), _short(actual))]
    return []


def _short(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=False)
    return text if len(text) <= 72 else text[:69] + "..."


def main() -> int:
    with open(CASES, encoding="utf-8") as handle:
        document = json.load(handle)

    expected = python_side(document)
    try:
        actual = cpp_side()
    except FileNotFoundError:
        print("no C++ compiler; nothing measured")
        return 0
    except subprocess.CalledProcessError as exc:
        print("the probe would not build or run: %s" % exc)
        return 1

    total = clean = 0
    for scenario in document["cases"]:
        name = scenario["id"]
        total += 1
        rows = differences(expected.get(name), actual.get(name))
        if not rows:
            clean += 1
            print("  ok    %s" % name)
            continue
        print("  DIFF  %s   %d field(s)" % (name, len(rows)))
        for where, exp, act in rows[:6]:
            print("          %s" % where)
            print("            python %s" % exp)
            print("            c++    %s" % act)
        if len(rows) > 6:
            print("          ... and %d more" % (len(rows) - 6))

    print("\n%d of %d cases reproduce the Python belief engine exactly." % (clean, total))
    if clean != total:
        return 1
    print("Beliefs, provenance, origin counts, contradictions and reason traces "
          "all agree,\nincluding the order of every map.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
