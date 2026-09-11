"""The layer map, and the check that keeps it true.

`unscripted/` is a flat package of forty-odd modules. That is not a problem in itself --
Python's module namespace is flat within a package and the import graph here is
acyclic -- but a structure that exists only in the author's head erodes. One
import from a low-level engine up into the runtime, added because it was
convenient, and the layering is gone with nothing failing.

So the layering is declared here and enforced by test. The rule is the usual one:

    a module may import from its own layer or any layer below it, never above.

Physical subpackages (`unscripted/core/`, `unscripted/social/`, ...) would express the same
thing in the filesystem. They are deliberately not used yet: there are three
hundred internal import lines, and reorganising them in the middle of feature
work is a large, error-prone change whose payoff is readability. Enforcement is
the part with teeth, and it costs one file. Moving the files later stays a
mechanical follow-up, and this map is what would drive it.
"""

from __future__ import annotations

import ast
import os

#: Bottom to top. A module may depend on its own layer and everything before it.
LAYERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("foundation",
     "Vocabulary with no behaviour: value types, the proposition catalogue, event "
     "shapes, seed derivation. Everything else is written in these terms.",
     ("types", "statekey", "determinism", "events", "ontology", "contracts", "actions",
      "architecture")),

    ("engines",
     "One character's mind, one mechanism per module. Each takes state and inputs "
     "and returns new state plus a reason trace. None of them knows there is a "
     "world, a player, or a text layer.",
     ("belief", "memory", "affect", "relationship", "social", "sociolinguistics",
      "agency", "policy", "content", "distortion", "dialogue", "factions",
      "commitment", "standing", "appearance")),

    ("adapters",
     "Translation to and from things that are not this runtime: text providers, "
     "local model endpoints, faces, engine bridges. They convert; they never "
     "decide. Below the world on purpose, so the world cannot come to depend on "
     "which provider is installed.",
     ("provider", "edge", "metahuman", "bridge", "actionbridge", "voice",
      "capabilities")),

    ("world",
     "Many characters and a place: who perceived what, who met whom, who moved, "
     "what a player typed, what may be said aloud, and how all of it is stored.",
     ("agent", "perception", "diffusion", "routine", "parser", "validator", "world",
      "snapshot", "persistence", "generator", "grounding", "interpretation", "topology", "revision",
      "flat", "climate", "pursuit", "medium", "contagion",
      "common_knowledge", "notes", "promises", "tuning")),

    ("runtime",
     "The loop that puts the above in order, the world pack that feeds it, and "
     "the read models built on top.",
     ("runtime", "pack", "sdk", "state_view", "inspect")),

    ("surfaces",
     "Ways a human or a machine reaches the runtime: command line, HTTP service, "
     "authoring tools, benchmarks, evidence runs, demos. Nothing depends on these.",
     ("cli", "service", "studio", "webdemo", "authoring", "pipeline", "conformance", "phrasing",
      "benchmark", "golden",
      "evidence", "qa", "tour", "viz", "quickstart", "film", "compare", "showcase")),
)

#: Modules that are entry points rather than layers.
EXEMPT = ("__init__", "__main__")


def layer_of(module: str) -> int | None:
    """Index of the layer `module` belongs to, or None if it is unassigned."""
    for index, (_name, _why, members) in enumerate(LAYERS):
        if module in members:
            return index
    return None


def _package_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


class SourceUnavailable(RuntimeError):
    """The package's own source is not on disk to be read.

    True inside a zipapp bundle, which is how the runtime ships as one file. The
    layer check is a development-time assertion about this repository, so the
    honest behaviour there is to say so rather than to half-answer.
    """


def modules() -> list[str]:
    """Every module in the package, entry points excluded."""
    try:
        names = os.listdir(_package_dir())
    except (NotADirectoryError, FileNotFoundError) as exc:
        raise SourceUnavailable(
            "the layer map is read from this package's own .py files, and they "
            "are inside a bundle rather than on disk. Run `unscripted architecture` "
            "from a source checkout.") from exc
    return sorted(f[:-3] for f in names
                  if f.endswith(".py") and f[:-3] not in EXEMPT)


def internal_imports(module: str) -> set[str]:
    """The sibling modules `module` imports, by `from .x import y`."""
    path = os.path.join(_package_dir(), f"{module}.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            found.add(node.module.split(".")[0])
    return found


def unassigned() -> list[str]:
    """Modules the map has forgotten. A new module must be placed deliberately."""
    return [m for m in modules() if layer_of(m) is None]


def stale() -> list[str]:
    """Names in the map that no longer exist."""
    present = set(modules())
    return sorted(m for _n, _w, members in LAYERS for m in members if m not in present)


def violations() -> list[tuple[str, str]]:
    """Imports that point upwards. Empty is the only acceptable result."""
    out = []
    for module in modules():
        here = layer_of(module)
        if here is None:
            continue
        for dependency in sorted(internal_imports(module)):
            there = layer_of(dependency)
            if there is not None and there > here:
                out.append((module, dependency))
    return out


def render() -> str:
    """The map as text, for `unscripted architecture` and for documentation."""
    lines = []
    for index, (name, why, members) in enumerate(LAYERS):
        lines.append(f"{index}. {name}")
        lines.append(f"   {why}")
        lines.append("   " + "  ".join(sorted(members)))
        lines.append("")
    problems = violations()
    lines.append(f"{len(modules())} modules, {len(LAYERS)} layers, "
                 f"{len(problems)} upward import(s)")
    for module, dependency in problems:
        lines.append(f"  ! {module} -> {dependency}")
    return "\n".join(lines)
