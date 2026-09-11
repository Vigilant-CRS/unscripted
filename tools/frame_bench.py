"""What does this cost inside a game's frame? Measured, in both languages.

THE QUESTION THIS ANSWERS, AND WHY IT NEEDED ITS OWN TOOL. `scale_bench.py`
reports milliseconds per SIMULATED HOUR, which is the right unit for asking
whether a town of five thousand is affordable and the wrong one for the first
question an engine programmer asks: *what does this cost in my frame, with two
hundred NPCs?* Those are different questions and the second one had no answer
anywhere, which is a buying question rather than a support question.

It also measures the C++ core, which had never been benchmarked at all -- the
console path was verified for CORRECTNESS, bit for bit against Python, and never
once for cost.

WHAT IS MEASURED, AND WHAT EACH NUMBER IS FOR.

  A TURN -- somebody answers the player. This is the only number on a player's
  critical path: they have asked, and they are waiting. Compared against the
  ~100 ms at which a response stops feeling immediate, not against a frame,
  because nothing forces it to complete inside one.

  AN HOUR OF WORLD -- the whole cast moves, meets, talks, forgets and passes
  things on. This is BACKGROUND work. A game does not call it every frame; it
  calls it when world time advances, which for most designs is a handful of
  times a minute at most. The frame column exists to answer the question as
  asked, and the table says plainly what a game would actually do with it.

FAIRNESS. Both sides load the SAME generated pack from disk, with the same seed,
and run the same sequence. The pack is written into a temporary directory and
grown from `relay-station` by duplicating its cast into a district of rooms with
staggered shifts, so a large world is a plausible one rather than five hundred
people standing in a corridor. Nothing is warmed differently: each side does one
untimed hour first, then the timed ones.

WHAT IT CANNOT TELL YOU. One machine, one compiler, one libm, one CPU. A console
is a different machine with a different memory system, and the C++ column here is
evidence that the port is in the same order of magnitude as Python, not a
prediction of what it costs on a devkit. Run it there; that is what it is for.

    python3 tools/frame_bench.py
    python3 tools/frame_bench.py --sizes 50,200 --hours 4

Needs a C++ compiler for the C++ column. `CXX` picks one; without one, the
Python column is measured alone and the table says so.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INCLUDE = os.path.join(ROOT, "port", "cpp", "include")
BENCH_CPP = os.path.join(ROOT, "port", "cpp", "bench", "frame_bench.cpp")
TEMPLATE = os.path.join(ROOT, "worldpacks", "relay-station")

sys.path.insert(0, ROOT)

#: A 60 Hz frame, in milliseconds. The number the question is asked against.
FRAME_60 = 1000.0 / 60.0
#: The point at which a reply stops feeling like an answer and starts feeling
#: like a wait. Not a frame: a turn is allowed to take longer than one.
IMMEDIATE_MS = 100.0


# ---------------------------------------------------------------- the pack

def grow_pack(target: str, characters: int, places: int) -> None:
    """Write a pack with this many characters, in a district of this many rooms.

    Grown from `relay-station` rather than invented, so every character is a
    complete one -- traits, values, needs, education, a routine and a social
    network. A synthetic cast with empty fields would measure a runtime doing
    nothing, which is the easiest way to publish a fast number that means
    nothing.
    """
    shutil.copytree(TEMPLATE, target)
    world_path = os.path.join(target, "world.json")
    world = json.load(open(world_path, encoding="utf-8"))

    base_place = list(world["places"].values())[0]
    rooms = []
    for i in range(places):
        key = "place:room_%d" % i
        room = dict(base_place, label="Room %d" % i, exits=[],
                    aliases=["room%d" % i])
        world["places"][key] = room
        rooms.append(key)
    json.dump(world, open(world_path, "w", encoding="utf-8"))

    folder = os.path.join(target, "characters")
    seeds = []
    for name in sorted(os.listdir(folder)):
        seeds.append(json.load(open(os.path.join(folder, name), encoding="utf-8")))

    # The seed cast keeps its own places and routines: it is the part of the
    # world the scenario refers to, and moving it would break the pack.
    for i in range(characters - len(seeds)):
        source = seeds[i % len(seeds)]
        one = copy.deepcopy(source)
        one["id"] = "agent:extra_%d" % i
        one["names"] = dict(one.get("names") or {})
        one["names"]["public"] = "Extra %d" % i
        one["names"]["aliases"] = ["extra%d" % i]
        one["relationships"] = {}
        one["secrets"] = []
        home = rooms[i % len(rooms)]
        work = rooms[(i * 7 + 3) % len(rooms)]
        shift = (i % 6) * 4
        one["location"] = home
        one["routine"] = [
            {"from": "%02d:00" % shift, "place": work, "activity": "work"},
            {"from": "%02d:00" % ((shift + 8) % 24), "place": home,
             "activity": "rest"},
        ]
        one["networks"] = ["shift:%d" % (i % 3)]
        json.dump(one, open(os.path.join(folder, "extra_%d.json" % i), "w",
                            encoding="utf-8"))


# ---------------------------------------------------------------- python side

def measure_python(pack: str, hours: int, turns: int) -> dict:
    """Python doing exactly what the C++ core does, and nothing it does not.

    NO STORE. `UnscriptedRuntime.create()` opens SQLite and writes a projection
    per character per tick; the C++ core has no store at all, by design -- a
    console's save system is the host's, and the snapshot layer hands it one
    blob. Timing one side's database writes against the other side's absence of
    them would not be a comparison, so this builds the runtime directly with
    `store=None`, which is the configuration a shipped game runs in.
    """
    from unscripted.agent import Agent
    from unscripted.contracts import RuntimeConfig
    from unscripted.sdk import UnscriptedRuntime
    from unscripted.world import load_world_pack

    config = RuntimeConfig(world_pack_path=pack)
    world = load_world_pack(pack)
    # The rest of what `create()` does, minus the store and the pack validation:
    # put the player in the world and stand the cast where their DAY says they
    # should be. Both matter to the measurement -- a cast still standing where
    # the character files listed them is not the cast the routines produce.
    start = config.player_start_location or world.player_start
    if config.player_id not in world.agents:
        world.agents[config.player_id] = Agent(
            id=config.player_id, location=start,
            big_five={"agreeableness": 0.5, "emotional_stability": 0.5})
    else:
        world.agents[config.player_id].location = start
    runtime = UnscriptedRuntime(config, world, store=None)
    runtime.core.routine.seed(world)
    if config.load_initial_state:
        runtime.load_initial_state()

    runtime.advance_time(60)                      # warm, untimed

    start = time.perf_counter()
    for _ in range(hours):
        runtime.advance_time(60)
    hour_ms = (time.perf_counter() - start) / hours * 1000.0

    speaker, listener = _two_agents(runtime.world)
    runtime.core.say(speaker, listener)           # warm, untimed
    start = time.perf_counter()
    for _ in range(turns):
        runtime.core.say(speaker, listener)
    turn_ms = (time.perf_counter() - start) / turns * 1000.0

    cast = len(runtime.world.agents)
    busiest = max(len(runtime.world.occupants(p)) for p in runtime.world.places)
    runtime.close()
    return {"hour_ms": hour_ms, "turn_ms": turn_ms, "cast": cast,
            "busiest": busiest}


def _two_agents(world) -> tuple:
    ids = list(world.agents)
    return ids[0], ids[1]


# ---------------------------------------------------------------- c++ side

def build_cpp(binary: str) -> str | None:
    """Compile the C++ bench, or explain why the column will be missing."""
    compiler = os.environ.get("CXX") or "g++"
    if shutil.which(compiler) is None:
        return "no C++ compiler (%s); set CXX" % compiler
    command = [compiler, "-std=c++17", "-O2", "-I", INCLUDE, BENCH_CPP,
               "-o", binary]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        return "the C++ bench does not compile:\n" + done.stderr[-1500:]
    return None


def measure_cpp(binary: str, pack: str, hours: int, turns: int) -> dict:
    done = subprocess.run([binary, pack, str(hours), str(turns)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("the C++ bench failed on %s:\n%s%s"
                         % (pack, done.stdout, done.stderr))
    return json.loads(done.stdout)


# ---------------------------------------------------------------- the table

def frame_share(ms: float) -> str:
    return "%.1f%%" % (100.0 * ms / FRAME_60)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="10,50,200,1000",
                        help="cast sizes, comma separated")
    parser.add_argument("--hours", type=int, default=6,
                        help="timed simulated hours per size")
    parser.add_argument("--turns", type=int, default=40,
                        help="timed dialogue turns per size")
    parser.add_argument("--json", default=None, help="also write the raw numbers")
    args = parser.parse_args()

    sizes = [int(one) for one in args.sizes.split(",") if one.strip()]

    with tempfile.TemporaryDirectory() as work:
        binary = os.path.join(work, "frame_bench")
        cpp_problem = build_cpp(binary)

        rows = []
        for cast in sizes:
            pack = os.path.join(work, "pack_%d" % cast)
            grow_pack(pack, cast, max(4, cast // 4))
            row = {"asked_for": cast}
            row["python"] = measure_python(pack, args.hours, args.turns)
            row["cpp"] = None if cpp_problem else measure_cpp(
                binary, pack, args.hours, args.turns)
            rows.append(row)

    print()
    print("A TURN -- what a player waits for after asking a question")
    print("%8s %14s %14s %12s" % ("cast", "Python", "C++", "of 100 ms"))
    for row in rows:
        cpp = row["cpp"]
        best = cpp["turn_ms"] if cpp else row["python"]["turn_ms"]
        print("%8d %12.3f ms %12s %12s" % (
            row["python"]["cast"], row["python"]["turn_ms"],
            ("%.3f ms" % cpp["turn_ms"]) if cpp else "--",
            "%.1f%%" % (100.0 * best / IMMEDIATE_MS)))

    print()
    print("AN HOUR OF WORLD -- the whole cast moves, meets, talks and forgets")
    print("%8s %8s %14s %14s %16s" % ("cast", "busiest", "Python", "C++",
                                      "C++ of a frame"))
    for row in rows:
        cpp = row["cpp"]
        print("%8d %8d %12.3f ms %12s %16s" % (
            row["python"]["cast"], row["python"]["busiest"],
            row["python"]["hour_ms"],
            ("%.3f ms" % cpp["hour_ms"]) if cpp else "--",
            frame_share(cpp["hour_ms"]) if cpp else "--"))

    print()
    print("A 60 Hz frame is %.2f ms. The hour column is not per-frame work: a"
          % FRAME_60)
    print("game advances world time on its own schedule, and one call covers a")
    print("whole simulated hour of everybody's day.")
    if cpp_problem:
        print()
        print("No C++ column: %s" % cpp_problem)

    if args.json:
        json.dump({"frame_60_ms": FRAME_60, "immediate_ms": IMMEDIATE_MS,
                   "hours": args.hours, "turns": args.turns, "rows": rows},
                  open(args.json, "w", encoding="utf-8"), indent=1)
        print("\nRaw numbers: %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
