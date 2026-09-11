"""Line coverage of the runtime, with no third-party dependency.

The README claims a coverage figure. It was measured once with `coverage.py`,
which is not installed here and is not a dependency this project wants -- so the
number sat in the documentation unverifiable, which is the same as unverified.

`sys.monitoring` (CPython 3.12+) gives line events cheaply enough to run the
whole suite under it. So the figure can be re-measured by anybody, on a clean
machine, with nothing installed:

    python3 tools/coverage_check.py

WHAT IS COUNTED, said plainly, because a coverage number without its definition
is decoration.

The denominator is every line CPython considers executable in the module, taken
from the code object's own line table rather than by parsing -- so a docstring, a
comment and a blank line are not counted as missed, and neither is a `def` line
that is reached at import.

Modules are split into the three groups the README talks about:

  simulation core   the layers a shipped game runs: foundation, engines, world,
                    runtime
  optional layers   the nine that are off by default
  tooling           CLI, service, authoring, evidence, demos -- reported, but
                    NOT what the headline figure is about, because a studio does
                    not ship them

A line being executed is not a line being tested. This measures reach, not
assertion, and saying so is the difference between a number and a claim.
"""
from __future__ import annotations

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from unscripted import architecture                                        # noqa: E402
from unscripted.contracts import OPTIONAL_LAYERS                           # noqa: E402

SHIPPED = ("foundation", "engines", "world", "runtime")


def group_of(module: str) -> str:
    if module in OPTIONAL_LAYERS:
        return "optional layers"
    for name, _why, members in architecture.LAYERS:
        if module in members:
            return "simulation core" if name in SHIPPED else "tooling"
    return "tooling"


def executable_lines(path: str) -> set:
    """Every line CPython will emit a line event for, from the code objects."""
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    code = compile(source, path, "exec")
    found = set()
    pending = [code]
    while pending:
        current = pending.pop()
        for _start, _end, line in current.co_lines():
            if line:
                found.add(line)
        for constant in current.co_consts:
            if hasattr(constant, "co_lines"):
                pending.append(constant)
    return found


def main() -> int:
    if not hasattr(sys, "monitoring"):
        print("needs CPython 3.12 or newer for sys.monitoring")
        return 1

    modules = {}
    for name in architecture.modules():
        path = os.path.join(ROOT, "unscripted", name + ".py")
        if os.path.exists(path):
            modules[os.path.realpath(path)] = name

    hit = {path: set() for path in modules}

    monitoring = sys.monitoring
    tool = monitoring.DEBUGGER_ID
    monitoring.use_tool_id(tool, "unscripted-coverage")

    def on_line(code, line_number):
        seen = hit.get(os.path.realpath(code.co_filename))
        if seen is not None:
            seen.add(line_number)
        return None

    monitoring.register_callback(tool, monitoring.events.LINE, on_line)
    monitoring.set_events(tool, monitoring.events.LINE)
    try:
        # `runpy`, because the suite has no `main()`: its list of tests lives
        # under `if __name__ == "__main__"`, and importing it would run nothing.
        runpy.run_path(os.path.join(ROOT, "tests", "test_scenarios.py"),
                       run_name="__main__")
    finally:
        monitoring.set_events(tool, 0)
        monitoring.free_tool_id(tool)

    totals = {}
    for path, name in sorted(modules.items(), key=lambda kv: kv[1]):
        possible = executable_lines(path)
        covered = hit[path] & possible
        group = group_of(name)
        reached, total = totals.get(group, (0, 0))
        totals[group] = (reached + len(covered), total + len(possible))

    print()
    for group in ("simulation core", "optional layers", "tooling"):
        if group not in totals:
            continue
        reached, total = totals[group]
        percent = 100.0 * reached / total if total else 0.0
        print("  %-16s %5d / %5d lines   %.0f%%" % (group, reached, total, percent))
    print("\n  Reach, not assertion: a line executed is not a line tested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
