"""Does C++ compute the same bits as Python? Measure it before porting anything.

A port of this runtime is a multi-month job, and the whole of it rests on one
assumption that nobody checks until it is too late: that the same formula in
another language produces the same number. Not approximately -- exactly. A
seeded simulation that agrees to fifteen decimal places diverges anyway, because
the sixteenth decides one `if` a thousand ticks in and the two worlds are then
different worlds.

So this is the first thing built, and it is a measurement rather than a test of
anything I wrote: it builds `bit_probe.cpp`, runs it, computes the same values
here, and compares the raw 64 bits of every double.

WHAT IT CAN AND CANNOT ESTABLISH, said plainly.

It proves agreement *on this machine, with this compiler and this libm*. blake2b
and `int / 2**64` are exact and portable by construction -- integer arithmetic
and a division by a power of two. `log()` is not: it is a library function, not
an IEEE-754-mandated operation, and two correct implementations may differ in
the last bit. Both sides here call the same glibc, so agreement here does not
prove agreement on a console.

That is the finding, not a caveat on it. Run this on the target toolchain before
trusting a port on it.

    python3 port/cpp/probe/port_probe.py
"""
from __future__ import annotations

import hashlib
import math
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def bits(value: float) -> str:
    """The double's raw 64 bits, which is the only comparison worth making."""
    return "%016x" % struct.unpack("<Q", struct.pack("<d", value))[0]


def derive_seed(global_seed, agent_id, event_id, world_time, module_id, salt=""):
    key = f"{global_seed}|{agent_id}|{event_id}|{world_time}|{module_id}|{salt}"
    return hashlib.blake2b(key.encode("utf-8"), digest_size=16).digest()


def seeded_uniform(seed: bytes) -> float:
    return int.from_bytes(seed[:8], "big") / 2 ** 64


#: The same cases as `bit_probe.cpp`, in the same order. Kept as a literal in
#: both rather than shared through a file: a mismatch caused by a parser is a
#: mismatch this probe would report as a numerical one.
CASES = [
    ("lamb-street-2107", "agent:halloran", 17, 1267, "diffusion", ""),
    ("seedA", "npc", 0, 0, "belief", "topic"),
    ("", "", 0, 0, "", ""),
    ("unicode-äö", "agent:ü", 9, 4242, "climate", "x|y"),
]
KAPPAS = [0.2, 0.35, 0.5, 0.571, 0.698, 0.803, 0.95]

#: Values where `round(x, n)` is a tie and the obvious C++ implementation is
#: wrong. Not decoration: `nearbyint(x * 1000) / 1000` disagrees with Python on
#: 3 of 4,006 random values, and all three are ties like these.
TIES = [0.0005, 0.0015, 0.1235, 0.1245, 0.5555, 0.8885,
        -0.1235, -0.5555, 0.9995, 0.0000005, 2.675, 1.005]
ETAS = [1.0, 0.85, 0.4225]


def python_side() -> list:
    """Every value the C++ probe prints, computed here, in that order."""
    lines = []
    for case in CASES:
        seed = derive_seed(*case)
        lines.append("seed\t" + seed.hex())
        lines.append("uniform\t" + bits(seeded_uniform(seed)))
    for kappa in KAPPAS:
        for eta in ETAS:
            lines.append("evidence\t" + bits(eta * math.log(kappa / (1.0 - kappa))))
    for digits in (3, 6):
        for value in TIES:
            lines.append("round%d\t" % digits + bits(round(value, digits)))
    logit = 0.0
    for i in range(200):
        logit += math.pow(0.85, i % 12) * math.log(0.698 / (1.0 - 0.698))
    lines.append("accumulated\t" + bits(logit))
    lines.append("sigmoid\t" + bits(1.0 / (1.0 + math.exp(-logit))))
    return lines


def cpp_side() -> list:
    """Build the probe and run it. Returns the same shape as `python_side`."""
    compiler = os.environ.get("CXX", "g++")
    with tempfile.TemporaryDirectory() as work:
        binary = os.path.join(work, "bit_probe")
        subprocess.run(
            [compiler, "-O2", "-std=c++17", "-I", os.path.join(ROOT, "include"),
             os.path.join(HERE, "bit_probe.cpp"), "-o", binary],
            check=True)
        out = subprocess.run([binary], check=True, capture_output=True, text=True)
    lines = []
    for line in out.stdout.strip().splitlines():
        parts = line.split("\t")
        # The C++ side prints a readable decimal after the bits. Dropped here:
        # it is for a human reading the raw output, not for the comparison.
        lines.append("\t".join(parts[:2]))
    return lines


def main() -> int:
    expected = python_side()
    try:
        actual = cpp_side()
    except FileNotFoundError:
        print("no C++ compiler; nothing measured")
        return 0
    except subprocess.CalledProcessError as exc:
        print("the probe would not build or run: %s" % exc)
        return 1

    if len(expected) != len(actual):
        print("the two sides printed different numbers of values: "
              "%d here, %d there" % (len(expected), len(actual)))
        return 1

    bad = [(i, e, a) for i, (e, a) in enumerate(zip(expected, actual)) if e != a]
    width = max(len(line.split("\t")[0]) for line in expected)
    for index, exp, act in bad:
        label = exp.split("\t")[0]
        print("%-*s  differs at value %d" % (width, label, index))
        print("    python %s" % exp.split("\t")[1])
        print("    c++    %s" % act.split("\t")[1])

    print("\n%d of %d values are bit-identical." % (len(expected) - len(bad),
                                                    len(expected)))
    if bad:
        print("A port cannot be held to the conformance fixtures on this "
              "toolchain until these agree.")
        return 1
    print("blake2b, the uniform draw and the belief arithmetic agree exactly "
          "on this machine.\nThis says nothing about another compiler's libm; "
          "run it there before trusting it there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
