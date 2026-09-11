"""Command line entry points for the Unscripted SDK."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .bridge import list_bridge_profiles
from .contracts import RuntimeConfig, imprint_html, links_html
from .generator import CharacterGenerationRequest, generate_characters, write_generated_content
from .pack import validate_world_pack
from .sdk import UnscriptedRuntime
from .service import ServiceOptions, run_service
from .showcase import run_showcase


def _apply_llm(cfg: RuntimeConfig, args) -> RuntimeConfig:
    """If --llm-endpoint is given, route text realization through a local/hosted
    OpenAI-compatible chat endpoint (e.g. ollama on GPU). Output stays buffered and
    validated; on failure the runtime falls back to the deterministic template."""
    endpoint = getattr(args, "llm_endpoint", None)
    if endpoint:
        cfg.text_realizer = {
            "provider": "http",
            "endpoint": endpoint,
            "api_key": getattr(args, "llm_key", None),
            "model_id": getattr(args, "llm_model", None) or "local-chat",
            "timeout": float(getattr(args, "llm_timeout", 30.0)),
            "latency_budget_ms": int(getattr(args, "llm_budget_ms", 120)),
            "deferred": not getattr(args, "llm_no_defer", False),
            "warm_up": not getattr(args, "llm_no_warmup", False),
            "probe": not getattr(args, "llm_no_probe", False),
        }
    return cfg


def _add_llm_args(p):
    p.add_argument("--llm-endpoint",
                   help="OpenAI-compatible chat endpoint, e.g. "
                        "http://localhost:11434/v1/chat/completions (ollama on GPU).")
    p.add_argument("--llm-model", help="Model id served at the endpoint (e.g. unscripted-qwen4b).")
    p.add_argument("--llm-key", help="Optional bearer token for hosted endpoints.")
    p.add_argument("--llm-timeout", type=float, default=30.0)
    p.add_argument("--llm-budget-ms", type=int, default=120,
                   help="Milliseconds a turn may wait for the model before using "
                        "authored text (default 120; a warm local 4B needs ~290).")
    p.add_argument("--llm-no-defer", action="store_true",
                   help="Skip a slow model entirely instead of offering its line late.")
    p.add_argument("--llm-no-warmup", action="store_true",
                   help="Do not page the model into VRAM at startup (first line costs 5-25s).")
    p.add_argument("--llm-no-probe", action="store_true",
                   help="Skip the startup capability check.")


#: What the terminal scene says before the first prompt.
#:
#: It used to be one hardcoded paragraph about a missing medic named Milan --
#: the reference pack's story -- printed over every world anybody loaded. Follow
#: the Quick Start and the first thing you read is a mystery about a clinic in a
#: world of innkeepers and traders, which is a poor first impression and, worse,
#: an untrue one.
#:
#: A pack says its own opening in `scenario.json: intro`. The fallback below
#: describes the runtime rather than a story, because that is the only thing
#: true of every world.
INTRO_FALLBACK = """A terminal scene powered by Unscripted.

Ask the same question of different people and compare the answers. Lie to
somebody, promise something, wait for the day to move, or inspect a character to
see the causal trace behind what they just said.
Type 'help' for commands, 'quit' to exit.
"""


def _intro_for(sdk) -> str:
    """The pack's own opening, or an honest general one."""
    scenario = getattr(sdk.world, "scenario_intro", None)
    if scenario:
        return str(scenario).rstrip() + "\nType 'help' for commands, 'quit' to exit.\n"
    return INTRO_FALLBACK


def _report_provider(sdk):
    """Say at startup what the configured model can and cannot do."""
    report = getattr(sdk, "provider_report", None) or {}
    warm = report.get("warm_up")
    if warm:
        if warm["ok"]:
            print(f"[model] {warm['model_id']}: cold {warm['cold_ms']:.0f} ms, "
                  f"warm {warm['warm_ms']:.0f} ms")
        else:
            print(f"[model] {warm['model_id']}: warm-up FAILED — {warm['error']}")
    probe = report.get("probe")
    if probe:
        print(f"[model] capability: {probe['verdict']} ({probe['passed']}/{probe['of']}) — "
              f"{probe['advice']}")


def play(args) -> int:
    cfg = RuntimeConfig(world_pack_path=args.world_pack, storage_path=args.storage,
                        debug_traces=True, strict=not args.no_strict,
                        load_initial_state=not args.no_initial_state)
    sdk = UnscriptedRuntime.create(_apply_llm(cfg, args))
    try:
        _report_provider(sdk)
        print(_intro_for(sdk))
        print(sdk.describe_location(sdk.world.agents[cfg.player_id].location))
        scripted = _read_script(args.script)
        while True:
            if scripted:
                line = scripted.pop(0)
                print(f"\n> {line}")
            else:
                try:
                    line = input("\n> ")
                except EOFError:
                    print()
                    break
            result = sdk.submit_player_text(line)
            if result.message:
                print(result.message)
            if args.debug and result.developer_trace:
                print("\n[developer trace]")
                print(result.developer_trace)
            if result.done:
                break
            if args.once:
                break
        return 0
    finally:
        sdk.close()


def validate(args) -> int:
    pack_path = getattr(args, "world_pack_flag", None) or args.world_pack
    if not pack_path:
        print("error: give a world pack, either as `unscripted validate PATH` or as "
              "`unscripted validate --world-pack PATH`.", file=sys.stderr)
        return 2
    report = validate_world_pack(pack_path)
    if report.ok:
        print(f"OK: {args.world_pack}")
    for issue in report.issues:
        print(f"{issue.severity.upper()} {issue.code}: {issue.message} {issue.path}")
    return 0 if report.ok else 2


def smoke(args) -> int:
    cfg = RuntimeConfig(world_pack_path=args.world_pack, storage_path=":memory:")
    sdk = UnscriptedRuntime.create(_apply_llm(cfg, args))
    try:
        commands = [
            "look",
            "ask Vee about Milan",
            "ask Honce about clinic",
            "go market",
            "attack Pavel",
            "wait 20",
            "inspect Pavel",
        ]
        for command in commands:
            result = sdk.submit_player_text(command)
            print(f"> {command}")
            print(result.message)
        return 0
    finally:
        sdk.close()


def showcase(args) -> int:
    result = run_showcase(world_pack=args.world_pack,
                          secondary_world_pack=args.secondary_world_pack,
                          tertiary_world_pack=args.tertiary_world_pack,
                          storage_path=args.storage)
    print(result["output"])
    failed = [name for name, ok in result["checks"].items() if not ok]
    if failed:
        print("FAILED CHECKS: " + ", ".join(failed))
        return 2
    return 0


def golden(args) -> int:
    from .golden import run_scenario_file
    result = run_scenario_file(args.scenario)
    if result["failures"]:
        for failure in result["failures"]:
            print("FAIL", failure)
        return 2
    print(f"OK golden {result['name']} steps={result['steps']}")
    return 0


def golden_all(args) -> int:
    from .golden import run_all
    results = run_all(args.directory)
    total_fail = 0
    for r in results:
        mark = "OK " if not r["failures"] else "FAIL"
        print(f"{mark} {r['name']} ({r['steps']} steps)")
        for f in r["failures"]:
            print("     -", f)
            total_fail += 1
    print(f"\n{len(results)} scenarios, {total_fail} failing assertions")
    return 0 if total_fail == 0 else 2


#: The pages that make up the public showcase, and the run behind each one.
#: Kept here rather than in a workflow file so the set is one thing, generated by
#: one command, and a page that stops building fails locally rather than on push.
#: The player's lines in the showcase recording. Chosen because this sequence
#: produces all of it -- a lie, a wide spread, two versions and the forgetting --
#: and stated here so the film, the comparison and the pages tell one story
#: rather than three slightly different ones.
DEFAULT_FILM_SCRIPT = ("1:ask Mr. Okada about milan", "5:ask Honce about the attack")


SHOWCASE_PAGES = (
    ("rumour.html", "Seven people think you did it",
     "A news item says the stranger is linked to the market attack. Watch it "
     "travel a city block through people who actually meet, arrive in two "
     "different versions, and end with seven of eight holding it \u2014 and not "
     "one of them able to recall who told them."),
    ("spread.html", "The same thing, on a relay station",
     "Ten people, seven rooms, five days. A different world with different "
     "routines, running the same runtime: the intercom reaches half the crew "
     "before anybody speaks, and it stays one source."),
    ("lie.html", "A lie, and who it is traceable to",
     "The same map, in a different world, following a claim a character asserts "
     "while believing the opposite. Every listener records him as the source."),
    ("compare.html", "The same events, twice",
     "One claim through eight characters, asked of a set of booleans and of this "
     "runtime. Both columns computed from the identical events; two rows go to "
     "the flags, because a comparison nobody can lose is one nobody believes."),
    ("start.html", "The first ten minutes",
     "Three commands and one HTTP call gets a character talking. Every response "
     "on the page was captured from a live service while the page was generated, "
     "including what a client mistake looks like."),
    ("tour.html", "Six scenes, with the numbers",
     "The runtime set against the language model's own recorded output, and "
     "against named structural absences. Nothing is set against an invented "
     "competitor."),
)


def film(args) -> int:
    """Record a run, compare it against flags, and write a narrated video."""
    from . import __version__
    from .compare import build as build_comparison, render as render_compare
    from .film import (CARDS, FilmError, make_story, requirements, storyboard,
                       voice_for, write_cards)
    from .viz import record, render as render_map

    if args.check:
        for name, path in sorted(requirements().items()):
            print(f"{'yes' if path else 'no ':4} {name}")
        return 0

    script = []
    for entry in args.at or DEFAULT_FILM_SCRIPT:
        step, _, text = entry.partition(":")
        if not text:
            print(f"--at wants STEP:COMMAND, got {entry!r}")
            return 1
        script.append((int(step), text))

    def progress(message):
        if not args.quiet:
            print(f"  ... {message}", flush=True)

    progress("recording the run")
    data = record(args.world_pack, predicate=args.predicate, hours=args.hours,
                  step_minutes=args.step_minutes, script=script)
    progress("asking both representations the same questions")
    comparison = build_comparison(data, args.world_pack, predicate=args.predicate,
                                  script=script)

    folder = os.path.dirname(os.path.abspath(args.out)) or "."
    pack_name = os.path.basename(args.world_pack.rstrip("/"))
    pages_written = {
        "cards": write_cards(CARDS, os.path.join(folder, ".film-cards.html")),
        "compare": os.path.join(folder, ".film-compare.html"),
        "map": os.path.join(folder, ".film-map.html"),
    }
    with open(pages_written["compare"], "w", encoding="utf-8") as fh:
        fh.write(render_compare(comparison, version=__version__))
    with open(pages_written["map"], "w", encoding="utf-8") as fh:
        fh.write(render_map(data, version=__version__, pack=pack_name))

    from .world import load_world_pack, pronunciation_hints
    hints = pronunciation_hints(load_world_pack(args.world_pack))

    beats = storyboard(data, comparison, cards_page=pages_written["cards"],
                       compare_page=pages_written["compare"],
                       map_page=pages_written["map"])
    try:
        result = make_story(beats, args.out, width=args.width, height=args.height,
                            workers=args.workers, narrator=args.narrator,
                            narrator_model=args.narrator_model,
                            narrator_voice=voice_for(args.narrator,
                                                     getattr(args, "narrator_voice", None)),
                            progress=progress)
    except FilmError as exc:
        print(f"\n{exc}")
        return 1
    finally:
        for path in pages_written.values():
            if os.path.exists(path):
                os.remove(path)

    print(f"\n{result['seconds']}s, {result['stills']} stills, "
          f"{result['beats']} spoken beats, "
          f"{result['bytes'] / 1_000_000:.1f} MB -> {result['path']}")
    if args.script_out:
        with open(args.script_out, "w", encoding="utf-8") as fh:
            json.dump(result["script"], fh, indent=2)
            fh.write("\n")
        print(f"  what it says -> {args.script_out}")
    return 0


def voice(args) -> int:
    """Say a line the way the runtime says it should sound."""
    from .contracts import RuntimeConfig
    from .sdk import UnscriptedRuntime
    from .voice import available, describe, VoiceError

    if args.list_backends:
        for name, present in sorted(available().items()):
            print(f"{'yes' if present else 'no ':4} {name}")
        print("\nespeak-ng honours rate, pitch and loudness and sounds robotic.\n"
              "piper sounds far better and cannot change pitch at all, which costs\n"
              "an emotional read half its signal. Neither is bundled: the SDK\n"
              "installs with no third-party packages and that is worth more than a\n"
              "bundled voice.")
        return 0

    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=args.world_pack, storage_path=":memory:",
        voice_backend=args.backend, voice_model=args.model))
    try:
        os.makedirs(args.out_dir, exist_ok=True)
        written, index = 0, []
        for line in args.say:
            turn = sdk.avatar_turn(line)
            packet = turn.get("avatar")
            if not packet:
                print(f"  (nothing spoken for {line!r})")
                continue
            plan = sdk.voice_plan(packet)
            print(f"  {describe(plan, args.backend)}")
            print(f"    \u201c{plan.text}\u201d")
            if args.backend == "none":
                index.append(plan.as_dict())
                continue
            path = os.path.join(args.out_dir, f"{written:02d}_{plan.agent_id.split(':')[-1]}.wav")
            try:
                outcome = sdk.speak(packet, path)
            except VoiceError as exc:
                print(f"    {exc}")
                return 1
            written += 1
            index.append({**plan.as_dict(), "path": outcome["path"],
                          "lost": list(outcome["lost"])})
        with open(os.path.join(args.out_dir, "lines.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2)
            fh.write("\n")
        print(f"\n{written} file(s) and a manifest in {args.out_dir}/")
    finally:
        sdk.close()
    return 0


def pages(args) -> int:
    """Build the whole public showcase into one directory, index included."""
    import html as _html
    from . import __version__
    from .tour import build as build_tour, narration
    from .tour import render as render_tour
    from .viz import record, render as render_viz

    os.makedirs(args.out, exist_ok=True)

    def progress(message):
        if not args.quiet:
            print(f"  ... {message}", flush=True)

    # The lead page follows the claim with stakes a stranger understands in three
    # seconds. "A seal failed in Stores" is precise and means nothing to somebody
    # who does not already care; "they think you did it" needs no explaining, and
    # it is the same runtime either way.
    progress("rumour")
    rumour = record(args.reference_pack, predicate="connected_to_attack", hours=168,
                    step_minutes=30,
                    script=[(int(entry.split(":", 1)[0]), entry.split(":", 1)[1])
                            for entry in DEFAULT_FILM_SCRIPT])
    with open(os.path.join(args.out, "rumour.html"), "w", encoding="utf-8") as fh:
        fh.write(render_viz(rumour, version=__version__,
                            pack=os.path.basename(args.reference_pack.rstrip("/"))))

    progress("spread")
    spread = record(args.relay_pack, predicate="seal_breached", hours=120,
                    step_minutes=30, script=[(4, "ask Voss about breach")])
    with open(os.path.join(args.out, "spread.html"), "w", encoding="utf-8") as fh:
        fh.write(render_viz(spread, version=__version__,
                            pack=os.path.basename(args.relay_pack.rstrip("/"))))

    progress("lie")
    lie = record(args.reference_pack, predicate="whereabouts", hours=72,
                 step_minutes=30, script=[(2, "ask Mr. Okada about milan")])
    with open(os.path.join(args.out, "lie.html"), "w", encoding="utf-8") as fh:
        fh.write(render_viz(lie, version=__version__,
                            pack=os.path.basename(args.reference_pack.rstrip("/"))))

    progress("comparison")
    from .compare import build as build_comparison, render as render_compare
    comparison = build_comparison(rumour, args.reference_pack,
                                  predicate="connected_to_attack",
                                  script=[(int(e.split(":", 1)[0]), e.split(":", 1)[1])
                                          for e in DEFAULT_FILM_SCRIPT])
    with open(os.path.join(args.out, "compare.html"), "w", encoding="utf-8") as fh:
        fh.write(render_compare(comparison, version=__version__))

    progress("quickstart")
    from .quickstart import capture, render as render_start
    with open(os.path.join(args.out, "start.html"), "w", encoding="utf-8") as fh:
        fh.write(render_start(capture(args.reference_pack), version=__version__))

    progress("tour")
    tour_data = build_tour({"relay": args.relay_pack,
                            "cyberpunk": args.reference_pack}, args.evidence)
    with open(os.path.join(args.out, "tour.html"), "w", encoding="utf-8") as fh:
        fh.write(render_tour(tour_data, version=__version__))
    with open(os.path.join(args.out, "narration.md"), "w", encoding="utf-8") as fh:
        fh.write(narration(tour_data, version=__version__))

    film_block = ""
    if args.with_film:
        from .film import CARDS, make_story, storyboard, voice_for, write_cards
        from .viz import render as render_viz2
        from .world import load_world_pack, pronunciation_hints
        progress("film")
        pages_for_film = {
            "cards": write_cards(CARDS, os.path.join(args.out, ".cards.html")),
            "compare": os.path.join(args.out, ".compare.html"),
            "map": os.path.join(args.out, ".map.html"),
        }
        with open(pages_for_film["compare"], "w", encoding="utf-8") as fh:
            fh.write(render_compare(comparison, version=__version__))
        with open(pages_for_film["map"], "w", encoding="utf-8") as fh:
            fh.write(render_viz2(rumour, version=__version__,
                                 pack=os.path.basename(args.reference_pack.rstrip("/"))))
        try:
            outcome = make_story(
                storyboard(rumour, comparison, cards_page=pages_for_film["cards"],
                           compare_page=pages_for_film["compare"],
                           map_page=pages_for_film["map"]),
                os.path.join(args.out, "film.mp4"),
                workers=args.film_workers, narrator=args.film_narrator,
                narrator_model=args.film_narrator_model,
                narrator_voice=voice_for(args.film_narrator,
                                         getattr(args, "film_narrator_voice", None)),
                hints=pronunciation_hints(load_world_pack(args.reference_pack)),
                progress=progress)
        finally:
            for path in pages_for_film.values():
                if os.path.exists(path):
                    os.remove(path)
        engine_block = ""
        if os.path.exists(os.path.join(args.out, "engine.mp4")):
            engine_block = (
                '<section class="film"><h2 class="filmhead">A murder, and who '
                'ends up believing what &mdash; inside a game engine</h2>'
                '<video controls preload="metadata" src="engine.mp4"></video>'
                '<p class="cap">A councillor is shot in the open street. City '
                'Radio says it was the east-side kids; the trader whose stall it '
                'happened in front of saw three men who did not panic. Watch the '
                'block decide which one it believes &mdash; a Godot project '
                'talking HTTP to a running <code>unscripted serve</code>, built by '
                '<code>tools/godot_demo.py</code>.</p></section>')
        film_block = (
            '<section class="film"><video controls preload="metadata" '
            'src="film.mp4"></video>'
            f'<p class="cap">{running_time(outcome["seconds"])}. The problem, what this is, '
            f'<em>the same events twice</em>, the run itself, and who it is for. '
            f'Every picture is a frame of a real run and every figure spoken is '
            f'read out of it, so the film cannot describe a moment the recording '
            f'does not contain.</p></section>') + engine_block

    cards = "".join(
        f'<a class="card" href="{name}"><h2>{_html.escape(title)}</h2>'
        f'<p>{_html.escape(blurb)}</p></a>'
        for name, title, blurb in SHOWCASE_PAGES)
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(_INDEX.replace("__CARDS__", cards)
                       .replace("__FILM__", film_block)
                       .replace("__VERSION__", __version__)
                       .replace("__IMPRINT__", imprint_html())
                       .replace("__LINKS__", links_html()))

    print(f"{len(SHOWCASE_PAGES) + 1} pages"
          f"{' and a film' if args.with_film else ''} -> {args.out}/")
    return 0


_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unscripted — see it work</title>
<style>
 :root{color-scheme:dark;--bg:#0b0d11;--fg:#e9e7e2;--dim:#868d99;--line:#232833;
       --hot:#e0a458}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,
      -apple-system,"Segoe UI",Roboto,sans-serif}
 header{padding:90px 6vw 40px;max-width:900px}
 h1{font-size:clamp(30px,5vw,54px);line-height:1.08;margin:0 0 18px;
    letter-spacing:-.02em}
 .lede{font-size:clamp(17px,2vw,21px);color:var(--dim);margin:0}
 .links{margin:22px 0 0;font-size:15.5px;color:var(--dim)}
 .links a{color:var(--hot);text-decoration:none}
 .links a:hover{text-decoration:underline}
 .grid{display:grid;gap:1px;margin:1px 0;
       grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
 .card{background:var(--bg);padding:34px 30px;text-decoration:none;color:inherit;
       display:block;transition:background .15s;box-shadow:0 0 0 1px var(--line)}
 .card:hover{background:#11141a}
 .card h2{font-size:21px;margin:0 0 10px;color:var(--hot);letter-spacing:-.01em}
 .card p{margin:0;color:var(--dim);font-size:15px}
 .film{padding:0 6vw 10px;max-width:1180px}
 .film video{width:100%;max-width:1100px;display:block;border:1px solid var(--line);
             border-radius:8px;background:#000}
 .film .cap{color:var(--dim);font-size:13.5px;margin:12px 0 0;max-width:72ch}
 .filmhead{font-size:12px;letter-spacing:.16em;text-transform:uppercase;
           color:var(--dim);font-weight:500;margin:36px 0 14px}
 .for{padding:64px 6vw 20px;max-width:1180px}
 .for h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;
         color:var(--dim);font-weight:500;margin:0 0 26px}
 .three{display:grid;gap:34px;grid-template-columns:repeat(auto-fit,minmax(270px,1fr))}
 .three h3{font-size:17px;margin:0 0 8px;letter-spacing:-.01em;line-height:1.3}
 .three p{margin:0;color:var(--dim);font-size:14.5px}
 .not{margin:40px 0 0;color:var(--dim);font-size:14.5px;max-width:70ch;
      padding-top:22px;border-top:1px solid var(--line)}
 footer{padding:44px 6vw 90px;color:var(--dim);max-width:860px;font-size:14.5px}
 code{font-family:ui-monospace,Menlo,monospace;color:var(--fg)}
</style></head><body>
<header>
 <h1>The world remembers &mdash; and every character remembers differently.</h1>
 <p class="lede">Unscripted decides what a character knows, believes, conceals
 and is allowed to say. A language model only words it. These pages are generated
 by running it rather than written by hand.</p>
 __LINKS__
</header>
__FILM__
<div class="grid">__CARDS__</div>
<section class="for">
 <h2>What it is for</h2>
 <div class="three">
  <div>
   <h3>Characters stop knowing things nobody told them</h3>
   <p>A model answers from whatever is in its prompt, so "world context" becomes
   something every character knows. Here a character knows what reached them, from
   whom, and how sure that makes them &mdash; and the text layer is given only what
   they are permitted to say.</p>
  </div>
  <div>
   <h3>Rumours stop costing a flag per pair of characters</h3>
   <p>Scripted propagation is authoring work that grows with the square of the
   cast, which is why most games have three characters who react and forty who do
   not. This spreads along the routines you already wrote, and every belief keeps
   the route it took.</p>
  </div>
  <div>
   <h3>Generative characters become testable</h3>
   <p>The same seed reproduces the same world, so a bug report is a repro. State a
   rule about your story &mdash; <em>nobody outside the crew may learn this</em>
   &mdash; and the runtime searches for the shortest sequence of player actions
   that breaks it.</p>
  </div>
  <div>
   <h3>It ships to a console</h3>
   <p>A console forbids an <em>interpreter</em>, not a language. So there is a
   second implementation in C++17 with no dependencies, held to this one bit for
   bit: 50 of 51 modules, and all five conformance scenarios played end to end by
   both, compared field by field down to every provenance chain. One C header
   underneath Unity, Unreal and Godot &mdash; no sidecar process, no IPC, nothing
   to certify.</p>
  </div>
  <div>
   <h3>The town answers to how you play</h3>
   <p>Hit somebody in the open and the street itself closes up, and the mood drifts
   into the next street. Somebody who only heard about it treats you differently.
   Break a promise and people who merely watched now call you unreliable; keep one
   and nobody remarks on it. Same seed and same conduct give the same world, exactly;
   different conduct gives a different one &mdash; because of you, not noise.</p>
  </div>
  <div>
   <h3>It runs in the engine you already use</h3>
   <p>A Godot addon with two playable demos, a Unity package and an Unreal plugin,
   each tested inside the editor against a live service &mdash; and anything else
   speaks HTTP and JSON. One bundled file beside the game, no install, no network
   calls; saves go into your own save file. A language model is optional: none,
   authored text, or any OpenAI-compatible endpoint, including a local GPU.</p>
  </div>
 </div>
 <p class="not">It is not a renderer, a quest engine, a voice or a chatbot. It sits
 behind whichever of those you already have and decides what becomes true in the
 society: who knows what, who said what, who lied, what spread, and why.</p>
</section>
<footer>
 <p>Built from source at version __VERSION__ by <code>unscripted pages</code>. Every
 figure on these pages comes from a run performed while the page was written, and
 each one prints the command that reproduces it.</p>
 <p>What is not here: no bundled voice (the runtime plans one; you supply the
 synthesiser), no faces rendered, and <strong>no shipped game</strong>. The
 native bindings are verified against real toolchains &mdash; a C# compiler for
 Unity, a headless Godot for the GDExtension, Unreal 5.8.2 for the plugin
 &mdash; but none of the three has been run inside an actual game, which is a
 different sentence. Those gaps are listed in
 <code>docs/CONCEPT.md</code>.</p>
__IMPRINT__
</footer>
</body></html>
"""


def viz(args) -> int:
    """Record a run and write the page that plays it back."""
    from . import __version__
    from .viz import record, render

    script = []
    for entry in args.at or []:
        step, _, text = entry.partition(":")
        if not text:
            print(f"--at wants STEP:COMMAND, got {entry!r}")
            return 1
        script.append((int(step), text))

    def progress(message):
        if not args.quiet:
            print(f"  ... {message}", flush=True)

    data = record(args.world_pack, predicate=args.predicate, hours=args.hours,
                  step_minutes=args.step_minutes, script=script, progress=progress)
    page = render(data, version=__version__,
                  pack=os.path.basename(args.world_pack.rstrip("/")))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(page)

    frames = data["frames"]
    tells = sum(len(f["tells"]) for f in frames)
    silences = sum(len(f["silence"]) for f in frames)
    knowers = len(frames[-1]["p"])
    print(f"{len(frames)} frames · {tells} tellings · {silences} times somebody said "
          f"nothing · {knowers} end up holding it -> {args.out}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
            fh.write("\n")
        print(f"  recording -> {args.json}")
    return 0


def tour(args) -> int:
    """Run the six scenes and write the page that shows them."""
    from . import __version__
    from .tour import build, render

    packs = {"relay": args.relay_pack, "cyberpunk": args.reference_pack}
    for label, pack in packs.items():
        if not os.path.isdir(pack):
            print(f"No world pack for {label}: {pack}")
            return 1

    def progress(name):
        if not args.quiet:
            print(f"  ... {name}", flush=True)

    result = build(packs, args.evidence, progress=progress)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(result, version=__version__))
    print(f"{len(result['scenes'])} scenes, {result['seconds']}s -> {args.out}")
    if args.script:
        from .tour import narration
        with open(args.script, "w", encoding="utf-8") as fh:
            fh.write(narration(result, version=__version__))
        print(f"narration -> {args.script}")
    return 0


def qa(args) -> int:
    """Search for the shortest player sequence that breaks a rule.

    Exit code 2 on a violation, so this can gate a build the way a test does.
    """
    import json as _json
    from .qa import load_rules, render, search

    spec, rules = load_rules(args.rules)
    pack = args.world_pack or spec.get("world_pack")
    if not pack:
        print("No world pack: pass --world-pack or set `world_pack` in the rules file.")
        return 1

    def progress(message):
        if not args.quiet:
            print(f"  ... {message}", flush=True)

    result = search(pack, rules,
                    depth=args.depth or spec.get("depth", 3),
                    budget=args.budget or spec.get("budget", 1500),
                    progress=progress)
    print(render(result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            _json.dump(result, fh, indent=2)
            fh.write("\n")
        print(f"  written: {args.json}")
    return 0 if result["held"] else 2


def benchmark(args) -> int:
    """Run the epistemic-integrity benchmark and print a publishable report."""
    from .benchmark import run_benchmark

    def progress(done, total):
        if not args.quiet:
            print(f"  ... {done:,}/{total:,} turns", flush=True)

    report = run_benchmark(world_pack=args.world_pack, turns=args.turns,
                           minutes_per_turn=args.minutes_per_turn, seed=args.seed,
                           verify_determinism=not args.no_determinism,
                           progress=progress)
    print(report.render())
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report.as_dict(), fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\n  report written to {args.json}")
    return 0 if report.passed else 2


def new_pack(args) -> int:
    """Scaffold a world pack that already works, for an author to change."""
    from .authoring import authoring_report, PackDocument, render_report, scaffold_pack
    try:
        doc = scaffold_pack(args.path, name=args.name, start=args.start,
                            overwrite=args.overwrite)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = validate_world_pack(args.path)
    print(f"Created {args.path}")
    for issue in report.issues:
        print(f"  {issue.severity.upper()} {issue.code}: {issue.message}")
    print(render_report(authoring_report(doc)))
    print(f"\nPlay it:  unscripted play --world-pack {args.path}")
    print(f"Edit it:  unscripted studio --world-pack {args.path}")
    return 0 if report.ok else 2


def author(args) -> int:
    """Report on a pack as an author, not as a schema validator."""
    from .authoring import authoring_report, PackDocument, render_report
    doc = PackDocument.load(UnscriptedRuntime._resolve_pack_path(args.world_pack))
    report = authoring_report(doc)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(render_report(report))
    return 0 if report["ready"] else 2


def studio(args) -> int:
    """Serve the authoring UI for a pack."""
    cfg = RuntimeConfig(world_pack_path=args.world_pack, storage_path=":memory:",
                        strict=False)
    options = _service_options(args)
    options.authoring_path = UnscriptedRuntime._resolve_pack_path(args.world_pack)
    print("=" * 60)
    print("  Unscripted Studio — world-pack editor")
    print(f"  Open: http://{args.host}:{args.port}/studio")
    print(f"  Editing: {options.authoring_path}")
    print("  Changes are written to disk when you press Save.")
    print("=" * 60)
    try:
        run_service(cfg, host=args.host, port=args.port, options=options)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def architecture_map(args) -> int:
    """Print the layer map, and fail if any module imports upwards."""
    from .architecture import SourceUnavailable, render, unassigned, violations
    try:
        print(render())
        return 2 if (violations() or unassigned()) else 0
    except SourceUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def tune(args) -> int:
    """Print every knob this world has, with what it is currently set to.

    An author could previously find out what a world could be tuned to only by
    reading the runtime's source, because exactly one engine of fourteen read
    anything from a pack. This is the list, and anything in it goes in a
    `"tuning"` block in world.json.
    """
    from . import tuning as tuning_module
    from .contracts import RuntimeConfig
    from .sdk import UnscriptedRuntime

    runtime = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=args.world_pack, storage_path=":memory:"))
    try:
        authored = getattr(runtime.world, "tuning", None) or {}
        rows = tuning_module.describe(runtime.core)
        total = sum(len(row["parameters"]) for row in rows)
        print(f"{total} parameters across {len(rows)} parts of the runtime.")
        print("Anything here goes in world.json under \"tuning\". A name that "
              "is not here is an error,")
        print("not a shrug -- a value silently ignored is worse than one "
              "refused.\n")
        for row in rows:
            set_here = authored.get(row["engine"]) or {}
            print(f"  {row['engine']}")
            print(f"      {row['governs']}")
            for key, value in row["parameters"].items():
                mark = "  <- set by this pack" if key in set_here else ""
                print(f"      {key:26s} {value!r}{mark}")
            print()
        if authored:
            print(f"This pack sets {sum(len(v) for v in authored.values())} of "
                  f"them.")
        else:
            print("This pack sets none of them, so every value above is the "
                  "runtime default.")
    finally:
        runtime.close()
    return 0


def bundle(args) -> int:
    """Pack the runtime into one file that any Python 3.10+ can run.

    THIS IS HALF OF THE SHIPPING ANSWER, and it is worth being exact about which
    half. It does not remove the need for a Python interpreter on the machine.
    What it removes is everything else: no pip, no virtualenv, no site-packages,
    no install step, no import path to get wrong. One file you copy next to your
    game, about a megabyte, and

        python3 unscripted.pyz serve --world-pack ... --port 0 --announce ...

    behaves exactly as an installed `unscripted` does -- the service, every endpoint,
    every optional layer. This is only possible because the SDK has no
    third-party dependencies, which is the promise paying for itself.

    For the other half -- shipping to a player who has no Python at all --
    `--standalone` puts a redistributable interpreter beside it and writes a
    launcher, so what you copy into your game is a folder that runs on a machine
    with nothing installed.
    """
    import shutil
    import tempfile
    import zipapp
    from .architecture import _package_dir

    out = args.out
    staging = tempfile.mkdtemp(prefix="unscripted-bundle-")
    try:
        package = os.path.join(staging, "unscripted")
        shutil.copytree(_package_dir(), package,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        with open(os.path.join(staging, "__main__.py"), "w",
                  encoding="utf-8") as handle:
            handle.write("import sys\nfrom unscripted.cli import main\n"
                         "raise SystemExit(main(sys.argv[1:]))\n")
        zipapp.create_archive(staging, target=out,
                              interpreter=args.interpreter, compressed=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    if getattr(args, "standalone", False):
        return _standalone(args, out)

    size = os.path.getsize(out)
    print(f"{out}  {size / 1024:.0f} kB")
    print(f"  python3 {os.path.basename(out)} serve --world-pack <your pack>")
    print("  World packs are NOT bundled: they are your content, they change "
          "without a rebuild,")
    print("  and --world-pack takes a path outside the archive.")
    return 0


#: Where a redistributable CPython comes from. Not a dependency of the SDK --
#: nothing here imports it, and the download happens once, at build time, on a
#: developer's machine. The runtime still has no third-party dependencies.
PYTHON_DIST_INDEX = ("https://api.github.com/repos/astral-sh/"
                     "python-build-standalone/releases/latest")


def _standalone(args, pyz: str) -> int:
    """Interpreter, runtime and a launcher in one folder that needs nothing.

    THE HALF THAT WAS MISSING. `unscripted bundle` removed pip, virtualenvs, install
    steps and import paths, and left one requirement standing: a Python on the
    player's machine. For a studio shipping a game that is not a small caveat,
    it is the caveat -- you cannot ask a player to install a language runtime,
    and the docs said as much and called it somebody else's packaging exercise.

    So: a redistributable CPython goes next to the archive and a two-line
    launcher points at it. What a studio copies into their game is a folder.
    Nothing is installed, nothing is on PATH, and the system Python -- if there
    even is one -- is not consulted.

    Deliberately NOT a build toolchain. No PyInstaller, no Nuitka, no compiler:
    the interpreter is downloaded already built, the runtime is already one
    file, and assembling them is copying. A packaging step that can fail in
    interesting ways is a packaging step that fails on somebody else's machine.
    """
    import json as _json
    import shutil
    import tarfile
    import urllib.request

    folder = os.path.splitext(pyz)[0] + "-standalone"
    runtime_dir = os.path.join(folder, "runtime")
    os.makedirs(folder, exist_ok=True)

    archive = getattr(args, "python_dist", None)
    if not archive:
        print("  ... asking for the current redistributable CPython")
        with urllib.request.urlopen(PYTHON_DIST_INDEX, timeout=60) as response:
            release = _json.load(response)
        wanted = getattr(args, "python_target", "x86_64-unknown-linux-gnu")
        # `install_only_stripped` over `install_only`: the difference is debug
        # symbols, which are 209 MB of libpython and 98 MB of interpreter that a
        # shipped game never reads. 34 MB against 111, and 71 MB unpacked
        # against 337.
        def _asset(kind):
            return next((a for a in release.get("assets", [])
                         if wanted in a["name"] and kind in a["name"]
                         and a["name"].startswith("cpython-3.12")), None)

        asset = _asset("install_only_stripped") or _asset("install_only")
        if asset is None:
            print(f"error: no cpython-3.12 build for {wanted} in "
                  f"{release.get('tag_name')}. Pass --python-dist with a "
                  f"tarball you already have.", file=sys.stderr)
            return 2
        archive = os.path.join(folder, asset["name"])
        if not os.path.exists(archive):
            print(f"  ... {asset['name']}  {asset['size'] / 1e6:.0f} MB")
            urllib.request.urlretrieve(asset["browser_download_url"], archive)

    if os.path.isdir(runtime_dir):
        shutil.rmtree(runtime_dir)
    os.makedirs(runtime_dir, exist_ok=True)
    with tarfile.open(archive) as tar:
        # The distribution unpacks into a `python/` directory; lift its contents
        # so the launcher path does not depend on that name.
        tar.extractall(runtime_dir, filter="data")
    inner = os.path.join(runtime_dir, "python")
    if os.path.isdir(inner):
        for entry in os.listdir(inner):
            shutil.move(os.path.join(inner, entry),
                        os.path.join(runtime_dir, entry))
        os.rmdir(inner)

    shutil.copy2(pyz, os.path.join(folder, "unscripted.pyz"))

    # THE REFERENCE PACKS COME ALONG. Not because a studio ships them -- they
    # will bring their own -- but because a folder that cannot run its own
    # examples is a folder somebody cannot check before trusting.
    from .architecture import _package_dir
    source_packs = os.path.join(os.path.dirname(_package_dir()), "worldpacks")
    if os.path.isdir(source_packs):
        target_packs = os.path.join(folder, "worldpacks")
        if os.path.isdir(target_packs):
            shutil.rmtree(target_packs)
        shutil.copytree(source_packs, target_packs,
                        ignore=shutil.ignore_patterns("__pycache__"))
    launcher = os.path.join(folder, "unscripted")
    with open(launcher, "w", encoding="utf-8") as handle:
        handle.write(
            '#!/bin/sh\n'
            '# Unscripted, self-contained. Nothing is installed and\n'
            '# the system Python is not consulted.\n'
            '#\n'
            '# Shell built-ins only -- no dirname, no readlink. A launcher that\n'
            '# shells out is a launcher that fails on a stripped image, and\n'
            '# stripped images are exactly where a shipped game runs.\n'
            'here=${0%/*}\n'
            '[ "$here" = "$0" ] && here=.\n'
            'exec "$here/runtime/bin/python3" "$here/unscripted.pyz" "$@"\n')
    os.chmod(launcher, 0o755)
    with open(os.path.join(folder, "unscripted.bat"), "w",
              encoding="utf-8") as handle:
        handle.write('@echo off\r\n'
                     'set HERE=%~dp0\r\n'
                     '"%HERE%runtime\\python.exe" "%HERE%unscripted.pyz" %*\r\n')

    # WHAT A GAME DOES NOT SHIP. The distribution carries CPython's own test
    # suite, static libraries for building extensions, and headers -- around
    # two thirds of it, none of which a running service opens. Removed here
    # rather than left for a studio to discover in their build size.
    # `share/` stays: it holds terminfo and the like, the saving is a few
    # megabytes, and removing things whose absence only shows up in an obscure
    # code path is how a bundle breaks on somebody else's machine.
    for junk in (os.path.join(runtime_dir, "lib", "python3.12", "test"),
                 os.path.join(runtime_dir, "lib", "python3.12", "idlelib"),
                 os.path.join(runtime_dir, "lib", "python3.12", "tkinter"),
                 os.path.join(runtime_dir, "include")):
        shutil.rmtree(junk, ignore_errors=True)
    for root, _dirs, names in os.walk(runtime_dir):
        for name in names:
            if name.endswith((".a", ".pyc", ".whl")):
                os.remove(os.path.join(root, name))
    # And the tarball it came out of, which is not part of what you ship.
    if not getattr(args, "python_dist", None) and os.path.exists(archive):
        os.remove(archive)

    # Counted by inode, because the distribution hard-links `python3` to
    # `python3.12` and the naive sum reported a folder twice the size of the one
    # on disk -- which is the number a studio would have budgeted against.
    seen, total = set(), 0
    for root, _dirs, names in os.walk(folder):
        for name in names:
            stat = os.stat(os.path.join(root, name))
            if stat.st_ino in seen:
                continue
            seen.add(stat.st_ino)
            total += stat.st_size
    print(f"{folder}  {total / 1e6:.0f} MB")
    print(f"  {launcher} serve --world-pack <your pack>")
    print("  Copy that folder into your game. It runs on a machine with no "
          "Python at all.")
    return 0


def evidence(args) -> int:
    """Run a long, fully recorded evidence session and write a dossier."""
    from .evidence import run_evidence
    packs = [UnscriptedRuntime._resolve_pack_path(p) for p in
             (args.world_pack or ["worldpacks/cyberpunk-block"])]
    llm = None
    if getattr(args, "llm_endpoint", None):
        llm = {"provider": "http", "endpoint": args.llm_endpoint,
               "model_id": args.llm_model or "local-chat",
               "api_key": args.llm_key, "timeout": float(args.llm_timeout),
               "latency_budget_ms": int(args.llm_budget_ms),
               "deferred": False, "warm_up": True, "probe": True}
    started = time.time()

    def progress(label):
        elapsed = (time.time() - started) / 60.0
        print(f"[{elapsed:6.1f} min] {label}", flush=True)

    try:
        dossier = run_evidence(packs=packs, hours=args.hours, llm=llm,
                               out_dir=args.out, progress=progress,
                               only=args.case or None)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    failed = [c for c in dossier["cases"] if not c["passed"]]
    print()
    print(f"{len(dossier['cases'])} cases · "
          f"{'all held' if not failed else str(len(failed)) + ' FAILED'} · "
          f"{dossier['generated_after_seconds'] / 60:.0f} minutes")
    for case in failed:
        print(f"  FAIL {case['case']} ({case['stats'].get('pack','')}): "
              f"{'; '.join(case['findings'])}")
    print(f"\nDossier: {os.path.join(args.out, 'DOSSIER.md')}")
    return 0 if not failed else 2


def bridges(args) -> int:
    print(json.dumps(list_bridge_profiles(), indent=2, sort_keys=True))
    return 0


def avatar(args) -> int:
    """Emit a MetaHuman/Unreal avatar packet (ARKit blendshapes + prosody + gaze)."""
    cfg = RuntimeConfig(world_pack_path=args.world_pack, storage_path=":memory:")
    sdk = UnscriptedRuntime.create(_apply_llm(cfg, args))
    try:
        if args.agent:
            print(json.dumps(sdk.face_packet(args.agent), indent=2, sort_keys=True))
            return 0
        for command in args.text or ["ask Vee about Milan"]:
            packet = sdk.avatar_turn(command)
            print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    finally:
        sdk.close()


def generate_characters_cmd(args) -> int:
    pack_path = UnscriptedRuntime._resolve_pack_path(args.world_pack)
    with open(os.path.join(pack_path, "world.json"), "r", encoding="utf-8") as f:
        world_data = json.load(f)
    request = CharacterGenerationRequest(
        count=args.count,
        location_id=args.location,
        faction_id=args.faction,
        appearances=args.appearance or [],
        role_hints=args.role or [],
        seed=args.seed,
        id_prefix=args.id_prefix,
        player_id=args.player_id,
    )
    content = generate_characters(world_data, request)
    if args.write:
        written = write_generated_content(pack_path, content)
        print(json.dumps({"written": written}, indent=2, sort_keys=True))
    else:
        print(json.dumps(content.as_dict(), indent=2, sort_keys=True))
    return 0


def _service_options(args) -> ServiceOptions:
    token = getattr(args, "auth_token", None) or os.environ.get("UNSCRIPTED_AUTH_TOKEN")
    return ServiceOptions(
        auth_token=token,
        expose_debug_endpoints=not getattr(args, "no_debug_endpoints", False),
        allow_origin=getattr(args, "allow_origin", None),
        allow_insecure_bind=getattr(args, "allow_insecure_bind", False),
        max_body_bytes=getattr(args, "max_body_bytes", 1 << 20),
    )


def serve(args) -> int:
    if getattr(args, "explain_layers", False):
        return _explain_layers()
    cfg = RuntimeConfig(world_pack_path=args.world_pack, storage_path=args.storage,
                        debug_traces=True, strict=not args.no_strict)
    try:
        run_service(_apply_layers(_apply_llm(cfg, args), args),
                    host=args.host, port=args.port,
                    options=_service_options(args),
                    announce_path=getattr(args, "announce", None),
                    parent_pid=getattr(args, "parent_pid", None))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def rewrite_phrasings(args) -> int:
    """The place a language model belongs: build time, behind the gate."""
    from .authoring import PackDocument, authoring_report
    from .phrasing import rewrite_pack
    from .provider import HttpModelProvider

    pack = UnscriptedRuntime._resolve_pack_path(args.world_pack)
    provider = HttpModelProvider(endpoint=args.llm_endpoint,
                                 api_key=args.llm_key,
                                 model_id=args.llm_model,
                                 timeout=args.llm_timeout)

    def report(topic, stance, register, text, why):
        if args.verbose:
            mark = "kept " if why else "wrote"
            print(f"  {mark} {topic}/{stance}/{register}: {why or text}")

    summary = rewrite_pack(pack, provider, model_id=args.llm_model,
                           voice=args.voice, on_line=report)
    print(f"  {summary['rewritten']} lines rewritten, {summary['kept']} kept as "
          f"they were")
    for why, count in summary["reasons"].items():
        print(f"    {count} x {why}")

    # THE GATE STILL RUNS. A model that wrote something the pack cannot carry
    # should be caught here rather than in a playthrough.
    findings = [f for f in authoring_report(PackDocument.load(pack))["findings"]
                if f.get("level") in ("blocker", "problem")]
    if findings:
        print(f"\n  {len(findings)} problem(s) afterwards:")
        for finding in findings[:8]:
            print(f"    - {finding['message']}")
        return 1
    print("\n  `unscripted author` has nothing to say. The lines are committed JSON; "
          "nothing infers at play time.")
    return 0


def conformance(args) -> int:
    """The fixtures that make a port checkable instead of a matter of faith."""
    from . import conformance as fixtures

    if args.check:
        tolerance = fixtures.DEFAULT_ULP_TOLERANCE if args.port else 0.0
        failures = fixtures.check(args.out, ulp_tolerance=tolerance)
        if not failures:
            how = (" to within %g ULP" % tolerance) if tolerance else " exactly"
            print(f"  {len(fixtures.scenarios(args.out))} scenarios still produce the "
                  f"state the fixtures say they should,{how}.")
            return 0
        print(f"  {len(failures)} difference(s):")
        for scenario, where, expected, actual in failures[:40]:
            print(f"    [{scenario}] {where}")
            print(f"        expected {expected}")
            print(f"        actual   {actual}")
        if len(failures) > 40:
            print(f"    ... and {len(failures) - 40} more")
        if not args.port:
            print("\n  If the change was deliberate, regenerate with "
                  "`unscripted conformance --out " + args.out + "` and read the diff.")
            print("  If you are checking a port on a different toolchain, "
                  "`--port` allows the last bit of a double to differ; see "
                  "`port/README.md` for what that is measured against.")
        return 1

    written = fixtures.write(args.out)
    total = sum(os.path.getsize(p) for p in written)
    print(f"  {len(written)} fixtures, {total / 1024:.0f} kB, in {args.out}")
    for path in written:
        print(f"    {os.path.basename(path)}")
    print("\n  A second implementation is correct when it reproduces "
          "`expected_state` in each of these.")
    return 0


def generate_pack(args) -> int:
    """Premise in, playable pack out -- or an honest refusal.

    The repair loop is the point. A generator that emits and hopes leaves the
    same four faults for an author to find one report at a time; this reads the
    report itself and goes round again, and what it prints at the end is what
    the gate says rather than what the generator believes.
    """
    from .pipeline import Premise, repair, write

    if os.path.exists(args.path) and os.listdir(args.path) and not args.overwrite:
        print(f"error: {args.path} is not empty. Use --overwrite if you mean it.",
              file=sys.stderr)
        return 2

    premise = Premise(name=args.name, seed=args.seed, places=args.places,
                      characters=args.characters, topics=args.topics,
                      districts=args.districts, start=args.start,
                      incident=args.incident, liar=not args.no_liar)
    written = write(premise, args.path)
    print(f"  {len(written)} files written")

    outcome = repair(args.path)
    for line in outcome["fixed"]:
        print(f"  repaired: {line}")
    if outcome["left"]:
        print("")
        print(f"  {len(outcome['left'])} thing(s) the repairer could not fix:")
        for line in outcome["left"][:10]:
            print(f"    - {line}")
        print("")
        print("  Run `unscripted author` for the full report and fix these by hand.")
        return 1

    print("")
    print(f"  READY. `unscripted author {args.path}` has nothing to say and the "
          f"runtime will load it.")
    print(f"  Play it:  unscripted play --world-pack {args.path}")
    return 0


def _add_layer_args(p):
    """The mechanics a studio can decline, on the command line.

    They existed as `RuntimeConfig` fields and could only be reached from Python,
    which meant the documented entry point -- `unscripted serve` -- could not switch on
    a single one of them. An integrator evaluating the runtime should not have to
    write a Python file to find out what it does.
    """
    from .contracts import OPTIONAL_LAYERS
    names = ", ".join(name for name, _ in OPTIONAL_LAYERS)
    p.add_argument(
        "--layers", default="",
        help=("Comma-separated optional layers to switch on, 'all', or 'none' to "
              "ignore what the world pack asks for. Each is off by default and "
              "off is exactly neutral. A pack may switch some on itself through "
              "world.json's \"layers\". Available: "
              + names + ". Use --explain-layers to see what each one does."))
    p.add_argument("--explain-layers", action="store_true",
                   help="Print what each optional layer does, and exit.")


def _pack_layers(world_pack_path) -> list:
    """The layers a world pack says it needs, from `world.json: {"layers": [...]}`.

    A pack that ships a radio station and a list of who listens to it depends on
    the media layer, and until now it had no way to say so: the data sat there,
    every broadcast reached nobody, and nothing anywhere said why. The pack
    author knows which mechanics the world is built on; this is where they say it.

    `--layers none` overrides this, so the "off is exactly neutral" comparison
    stays available on a pack that asks for something.
    """
    if not world_pack_path:
        return []
    try:
        with open(os.path.join(str(world_pack_path), "world.json"), encoding="utf-8") as fh:
            declared = json.load(fh).get("layers") or []
    except (OSError, ValueError):
        return []          # the loader reports a broken pack far better than this
    return [str(name).strip() for name in declared if str(name).strip()]


def _apply_layers(cfg, args):
    """Turn on what was asked for, and refuse what cannot work.

    A misspelled layer is an error rather than a shrug: silently running without
    the mechanic somebody asked for is the failure that costs an afternoon.
    """
    from .contracts import LAYER_REQUIRES, OPTIONAL_LAYERS
    known = {name for name, _ in OPTIONAL_LAYERS}
    asked = [part.strip() for part in (getattr(args, "layers", "") or "").split(",")
             if part.strip()]
    if asked == ["none"]:
        return cfg
    if asked == ["all"]:
        asked = sorted(known)
    for name in _pack_layers(getattr(cfg, "world_pack_path", None)):
        if name not in asked:
            asked.append(name)
    unknown = [name for name in asked if name not in known]
    if unknown:
        raise ValueError(
            "unknown layer(s): " + ", ".join(unknown) + ". Available: "
            + ", ".join(sorted(known)))
    for name in asked:
        setattr(cfg, name, True)
    for name in asked:
        needs = LAYER_REQUIRES.get(name)
        if needs and not getattr(cfg, needs, False):
            raise ValueError(
                f"--layers {name} needs {needs} as well: without it nothing "
                f"would ever place a call or write a note. Add it, or drop "
                f"{name}.")
    return cfg


def _explain_layers() -> int:
    from .contracts import LAYER_REQUIRES, OPTIONAL_LAYERS
    print("Optional layers. Every one is off by default, and off is exactly")
    print("neutral -- a run with the flag off reproduces byte-identically.\n")
    for name, what in OPTIONAL_LAYERS:
        needs = LAYER_REQUIRES.get(name)
        print(f"  {name}")
        for line in _wrap(what, 68):
            print(f"      {line}")
        if needs:
            print(f"      needs: {needs}")
        print()
    print("  unscripted serve --world-pack worldpacks/market-square --layers pursuit,notes")
    return 0


def _wrap(text: str, width: int) -> list:
    words, lines, row = text.split(), [], ""
    for word in words:
        if row and len(row) + 1 + len(word) > width:
            lines.append(row)
            row = word
        else:
            row = f"{row} {word}".strip()
    if row:
        lines.append(row)
    return lines


def _add_embedding_args(p):
    """What a game needs to launch this as a child process instead of by hand.

    Both of the shipped engine clients assume the service is already running --
    the Godot one says so in its error message -- which is fine for a demo and
    is the whole integration for a shipping game. These three flags together
    turn "the developer remembers to start a server" into "the game launches a
    child process and is told where it is".
    """
    p.add_argument("--announce", metavar="FILE",
                   help="Write {url, port, token, pid} here once listening, "
                        "atomically. Use with --port 0 so the OS picks a free "
                        "port and the launcher reads it back rather than "
                        "hard-coding one.")
    p.add_argument("--parent-pid", type=int, metavar="PID",
                   help="Exit when this process does. Without it, a game that "
                        "crashes leaves a service holding a port and a save.")


def _add_service_args(p):
    p.add_argument("--auth-token",
                   help="Require this bearer token on every request "
                        "(or set UNSCRIPTED_AUTH_TOKEN).")
    p.add_argument("--no-debug-endpoints", action="store_true",
                   help="Disable /state/*, /inspect/*, /avatar/face and the demo UI. "
                        "Use for builds that ship to players: those endpoints expose "
                        "every NPC's private beliefs and reason traces.")
    p.add_argument("--allow-origin", help="Send CORS headers for this origin.")
    p.add_argument("--allow-insecure-bind", action="store_true",
                   help="Permit binding to a non-loopback address without a token.")
    p.add_argument("--max-body-bytes", type=int, default=1 << 20,
                   help="Reject request bodies larger than this (default 1 MiB).")


def demo(args) -> int:
    """Start the service and open the browser demo UI."""
    url = f"http://{args.host}:{args.port}/"
    print("=" * 60)
    print("  Unscripted — live demo UI")
    print(f"  Open: {url}")
    if getattr(args, "llm_endpoint", None):
        print(f"  NPC text via LLM: {args.llm_model or 'local-chat'} @ {args.llm_endpoint}")
    else:
        print("  NPC text: deterministic templates (add --llm-endpoint for a model)")
    print("=" * 60)
    return serve(args)


def _read_script(path: str | None) -> list[str]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]


def running_time(seconds: float) -> str:
    """A film's length as its player shows it: whole minutes, whole seconds.

    The caption used to format the minutes with `:.0f`, which rounds, so a
    2:41 film was captioned 3:41 on the page that shows its player right above.
    """
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unscripted", description="Unscripted SDK tools")
    parser.set_defaults(func=play)
    parser.add_argument("--world-pack", default="worldpacks/cyberpunk-block",
                        help="Path to a Unscripted world pack.")
    parser.add_argument("--storage", default=":memory:",
                        help="SQLite storage path for the session.")
    parser.add_argument("--debug", action="store_true", help="Print developer traces after each turn.")
    parser.add_argument("--script", help="Run commands from a text file.")
    parser.add_argument("--once", action="store_true", help="Process one command and exit.")
    parser.add_argument("--no-strict", action="store_true", help="Start even if validation reports errors.")
    parser.add_argument("--no-initial-state", action="store_true",
                        help="Disable authored initial_state.json beliefs.")

    sub = parser.add_subparsers(dest="command")
    p_play = sub.add_parser("play", help="Run the interactive terminal reference scene.")
    p_play.set_defaults(func=play)
    p_play.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_play.add_argument("--storage", default=":memory:")
    p_play.add_argument("--debug", action="store_true")
    p_play.add_argument("--script")
    p_play.add_argument("--once", action="store_true")
    p_play.add_argument("--no-strict", action="store_true")
    p_play.add_argument("--no-initial-state", action="store_true")
    _add_llm_args(p_play)

    p_validate = sub.add_parser("validate", help="Validate a world pack.")
    p_validate.set_defaults(func=validate)
    # THREE CONVENTIONS FOR ONE ARGUMENT is one too many. Fourteen subcommands
    # take `--world-pack` after the verb, this one took a positional, and three
    # more accepted it only BEFORE the verb -- so a developer's first three
    # commands each wanted a different syntax and two of them failed with an
    # argparse usage dump. Both spellings work here now, and the flag is added
    # to the three that lacked it.
    p_validate.add_argument("world_pack", nargs="?", default=None,
                            help="The pack to validate. --world-pack also works.")
    p_validate.add_argument("--world-pack", dest="world_pack_flag",
                            help="Same thing, spelled the way every other "
                                 "subcommand spells it.")

    p_smoke = sub.add_parser("smoke", help="Run a deterministic reference smoke scenario.")
    p_smoke.set_defaults(func=smoke)
    p_smoke.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    _add_llm_args(p_smoke)

    p_showcase = sub.add_parser("showcase", help="Run the full SDK sales/regression showcase.")
    p_showcase.set_defaults(func=showcase)
    p_showcase.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_showcase.add_argument("--secondary-world-pack", default="worldpacks/noir-harbor")
    p_showcase.add_argument("--tertiary-world-pack", default="worldpacks/dorf-thornfeld")
    p_showcase.add_argument("--storage", default=":memory:")

    p_golden = sub.add_parser("golden", help="Run a golden scenario JSON file.")
    p_golden.set_defaults(func=golden)
    p_golden.add_argument("scenario")
    p_golden.add_argument("--world-pack", default="worldpacks/cyberpunk-block")

    p_golden_all = sub.add_parser("golden-all", help="Run every golden scenario in a directory.")
    p_golden_all.set_defaults(func=golden_all)
    p_golden_all.add_argument("--directory", default="golden")

    p_film = sub.add_parser(
        "film", help="Record a run and write a narrated video of it.")
    p_film.set_defaults(func=film)
    p_film.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_film.add_argument("--predicate", default="connected_to_attack")
    p_film.add_argument("--hours", type=float, default=168.0)
    p_film.add_argument("--step-minutes", type=int, default=30)
    p_film.add_argument("--at", action="append", metavar="STEP:COMMAND")
    p_film.add_argument("--out", default="unscripted.mp4")
    p_film.add_argument("--width", type=int, default=1920)
    p_film.add_argument("--height", type=int, default=1080)
    p_film.add_argument("--workers", type=int, default=4)
    p_film.add_argument("--script-out", help="Write what the narration says, with "
                                             "the length of each line.")
    # espeak-ng stays the default because it is the only one likely to be
    # already installed, and a film that will not render is worse than a film
    # that sounds robotic. kokoro is what the shipped video uses.
    p_film.add_argument("--narrator", default="espeak-ng",
                        choices=("espeak-ng", "piper", "kokoro"),
                        help="Voice for the narration. kokoro sounds best and "
                             "piper is close; both need a --narrator-model.")
    p_film.add_argument("--narrator-model",
                        help="Voice model for piper or kokoro (.onnx).")
    p_film.add_argument("--narrator-voice", default=None,
                        help="Voice for the narrator's backend. Default: the "
                             "backend's own, and af_heart for kokoro.")
    p_film.add_argument("--check", action="store_true",
                        help="Report which of chrome, ffmpeg and espeak-ng are present.")
    p_film.add_argument("--quiet", action="store_true")

    p_voice = sub.add_parser(
        "voice", help="Render spoken lines with the prosody the runtime derived.")
    p_voice.set_defaults(func=voice)
    p_voice.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_voice.add_argument("--say", action="append", default=[],
                         help="A player line. Repeatable.")
    p_voice.add_argument("--backend", default="espeak-ng", choices=("espeak-ng", "piper", "none"),
                         help="'none' prints the plans without rendering anything.")
    p_voice.add_argument("--model", help="Voice model file, for piper.")
    p_voice.add_argument("--out-dir", default="voices")
    p_voice.add_argument("--list-backends", action="store_true",
                         help="What this machine can actually run.")

    p_pages = sub.add_parser(
        "pages", help="Build the whole public showcase into one directory.")
    p_pages.set_defaults(func=pages)
    p_pages.add_argument("--out", default="demo-pages")
    p_pages.add_argument("--relay-pack", default="worldpacks/relay-station")
    p_pages.add_argument("--reference-pack", default="worldpacks/cyberpunk-block")
    p_pages.add_argument("--evidence", default="evidence/evidence-llm.json")
    p_pages.add_argument("--with-film", action="store_true",
                         help="Also render the narrated video and put it on the "
                              "index. Needs chrome, ffmpeg and espeak-ng.")
    p_pages.add_argument("--film-narrator", default="espeak-ng",
                         choices=("espeak-ng", "piper", "kokoro"))
    p_pages.add_argument("--film-narrator-model")
    p_pages.add_argument("--film-narrator-voice", default=None,
                         help="As `film --narrator-voice`.")
    p_pages.add_argument("--film-workers", type=int, default=4)
    p_pages.add_argument("--quiet", action="store_true")

    p_viz = sub.add_parser(
        "viz", help="Record a run and write an animated page of it: who learns what, "
                    "from whom, who gets it wrong, who forgets.")
    p_viz.set_defaults(func=viz)
    p_viz.add_argument("--world-pack", default="worldpacks/relay-station")
    p_viz.add_argument("--predicate", default="seal_breached",
                       help="The claim to follow through the society.")
    p_viz.add_argument("--hours", type=float, default=120.0)
    p_viz.add_argument("--step-minutes", type=int, default=30)
    p_viz.add_argument("--at", action="append", metavar="STEP:COMMAND",
                       help="A player action at a given step, e.g. 4:'ask Voss about "
                            "breach'. Repeatable. These are ordinary turns.")
    p_viz.add_argument("--out", default="spread.html")
    p_viz.add_argument("--json", help="Also write the raw recording, so the page can "
                                      "be checked against what was recorded.")
    p_viz.add_argument("--quiet", action="store_true")

    p_tour = sub.add_parser(
        "tour", help="Write a self-contained page of six scenes, with real numbers.")
    p_tour.set_defaults(func=tour)
    p_tour.add_argument("--out", default="tour.html")
    p_tour.add_argument("--relay-pack", default="worldpacks/relay-station")
    p_tour.add_argument("--reference-pack", default="worldpacks/cyberpunk-block")
    p_tour.add_argument("--evidence", default="evidence/evidence-llm.json",
                        help="A recorded model run. Its scene is left empty if absent, "
                             "rather than illustrated with something invented.")
    p_tour.add_argument("--script", help="Also write the voiceover, with the same "
                                         "figures as the page.")
    p_tour.add_argument("--quiet", action="store_true")

    p_qa = sub.add_parser(
        "qa", help="Search for the shortest player sequence that breaks a rule.")
    p_qa.set_defaults(func=qa)
    p_qa.add_argument("rules", help="A rules JSON file (see qa/).")
    p_qa.add_argument("--world-pack", default=None,
                      help="Overrides `world_pack` in the rules file.")
    p_qa.add_argument("--depth", type=int, default=None,
                      help="Longest player sequence to try (default 3).")
    p_qa.add_argument("--budget", type=int, default=None,
                      help="Maximum sequences to simulate before giving up.")
    p_qa.add_argument("--json", help="Also write the result as JSON.")
    p_qa.add_argument("--quiet", action="store_true")

    p_benchmark = sub.add_parser(
        "benchmark",
        help="Measure epistemic integrity over a long run (publishable report).")
    p_benchmark.set_defaults(func=benchmark)
    p_benchmark.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_benchmark.add_argument("--turns", type=int, default=2000)
    p_benchmark.add_argument("--minutes-per-turn", type=int, default=20)
    p_benchmark.add_argument("--seed", default="benchmark")
    p_benchmark.add_argument("--json", help="Also write the report as JSON.")
    p_benchmark.add_argument("--no-determinism", action="store_true",
                             help="Skip the replay check (halves the runtime).")
    p_benchmark.add_argument("--quiet", action="store_true")

    p_new = sub.add_parser("new", help="Create a world pack that already works.")
    p_new.set_defaults(func=new_pack)
    p_new.add_argument("path", help="Directory to create the pack in.")
    p_new.add_argument("--name", default="New World")
    p_new.add_argument("--start", default="08:00", help="Time of day the scene opens (HH:MM).")
    p_new.add_argument("--overwrite", action="store_true")

    p_gen = sub.add_parser(
        "generate-pack",
        help="Build a whole world pack from a premise, and repair it until both "
             "gates accept it.")
    p_gen.set_defaults(func=generate_pack)
    p_gen.add_argument("path", help="Directory to write the pack into.")
    p_gen.add_argument("--name", default="Generated World")
    p_gen.add_argument("--seed", default="premise",
                       help="Same premise and same seed produce the same pack.")
    p_gen.add_argument("--places", type=int, default=8)
    p_gen.add_argument("--characters", type=int, default=16)
    p_gen.add_argument("--topics", type=int, default=6)
    p_gen.add_argument("--districts", type=int, default=3,
                       help="How many circles the cast is spread across. One is "
                            "a world where everything reaches everybody.")
    p_gen.add_argument("--start", default=None,
                       help="HH:MM. Left out, the busiest hour on the street is "
                            "worked out from the routines, so the scene does "
                            "not open on an empty road.")
    p_gen.add_argument("--incident",
                       default="somebody was robbed in the market at night")
    p_gen.add_argument("--no-liar", action="store_true",
                       help="Leave out the one character with something to hide.")
    p_gen.add_argument("--overwrite", action="store_true")

    p_conf = sub.add_parser(
        "conformance",
        help="Write, or check, the fixtures a second implementation must "
             "reproduce byte for byte.")
    p_conf.set_defaults(func=conformance)
    p_conf.add_argument("--out", default="conformance",
                        help="Directory for the fixtures.")
    p_conf.add_argument("--check", action="store_true",
                        help="Re-run them and report what no longer matches, "
                             "instead of writing them.")
    p_conf.add_argument("--port", action="store_true",
                        help="Judge a port rather than this implementation: "
                             "numbers may differ in the last bit, because "
                             "another toolchain's log() may. Nothing else may "
                             "differ. Meaningless without --check.")

    p_phr = sub.add_parser(
        "rewrite-phrasings",
        help="Rewrite a pack's lines with a model, at build time, behind three "
             "checks. The result is committed JSON; nothing infers at play time.")
    p_phr.set_defaults(func=rewrite_phrasings)
    p_phr.add_argument("world_pack")
    p_phr.add_argument("--llm-endpoint", required=True,
                       help="Anything OpenAI-shaped, including a local model.")
    p_phr.add_argument("--llm-model", default="local-chat")
    p_phr.add_argument("--llm-key")
    p_phr.add_argument("--llm-timeout", type=float, default=60.0)
    p_phr.add_argument("--voice", default="",
                       help="How the world should sound. Defaults to the pack's "
                            "own `scenario.json: intro`.")
    p_phr.add_argument("--verbose", action="store_true")

    p_author = sub.add_parser(
        "author", help="Report on a pack the way an author needs: map, day, meetings, gaps.")
    p_author.set_defaults(func=author)
    p_author.add_argument("world_pack")
    p_author.add_argument("--json", action="store_true")

    p_studio = sub.add_parser("studio", help="Serve the world-pack editor.")
    p_studio.set_defaults(func=studio)
    p_studio.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_studio.add_argument("--host", default="127.0.0.1")
    p_studio.add_argument("--port", type=int, default=8766)
    p_studio.add_argument("--storage", default=":memory:")
    p_studio.add_argument("--no-strict", action="store_true")
    _add_service_args(p_studio)

    p_evidence = sub.add_parser(
        "evidence",
        help="Run a long recorded session and write an evidence dossier.")
    p_evidence.set_defaults(func=evidence)
    p_evidence.add_argument("--world-pack", action="append",
                            help="Repeatable. Defaults to the reference pack.")
    p_evidence.add_argument("--hours", type=float, default=2.0)
    p_evidence.add_argument("--out", default="evidence")
    p_evidence.add_argument(
        "--case", action="append", metavar="NAME",
        help="Run only this case (repeatable). For iterating; a full run is the "
             "artefact. The dossier states that it was partial.")
    _add_llm_args(p_evidence)

    p_arch = sub.add_parser(
        "architecture", help="Print the module layer map and check it holds.")
    p_arch.set_defaults(func=architecture_map)

    p_bridges = sub.add_parser("bridges", help="List engine and third-party bridge profiles.")
    p_bridges.set_defaults(func=bridges)

    p_avatar = sub.add_parser("avatar",
                              help="Emit a MetaHuman/Unreal avatar packet for a turn or agent.")
    p_avatar.set_defaults(func=avatar)
    p_avatar.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_avatar.add_argument("--text", action="append",
                          help="Player command(s) to run; prints an avatar packet per turn.")
    p_avatar.add_argument("--agent",
                          help="Instead of a turn, dump the live face packet for this agent id.")
    _add_llm_args(p_avatar)

    p_generate = sub.add_parser("generate-characters",
                                help="Generate production character JSON from world context.")
    p_generate.set_defaults(func=generate_characters_cmd)
    p_generate.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_generate.add_argument("--count", type=int, default=1)
    p_generate.add_argument("--location", required=True)
    p_generate.add_argument("--faction")
    p_generate.add_argument("--appearance", action="append")
    p_generate.add_argument("--role", action="append")
    p_generate.add_argument("--seed", default="generated")
    p_generate.add_argument("--id-prefix", default="agent:gen")
    p_generate.add_argument("--player-id", default=RuntimeConfig.player_id,
                            help="Player id the generated characters relate to.")
    p_generate.add_argument("--write", action="store_true",
                            help="Write generated characters and initial state into the pack.")

    p_tune = sub.add_parser(
        "tune", help="List every parameter a world pack may set, and its value.")
    p_tune.set_defaults(func=tune)
    p_tune.add_argument("--world-pack", default="worldpacks/market-square")

    p_bundle = sub.add_parser(
        "bundle", help="Pack the runtime into one file any Python 3.10+ can run.")
    p_bundle.set_defaults(func=bundle)
    p_bundle.add_argument("--out", default="unscripted.pyz",
                          help="Where to write the bundle (default unscripted.pyz).")
    p_bundle.add_argument("--interpreter", default="/usr/bin/env python3",
                          help="Shebang for the archive; ignored on Windows, "
                               "where you run it as `python unscripted.pyz`.")
    p_bundle.add_argument(
        "--standalone", action="store_true",
        help=("Also put a redistributable CPython and a launcher beside it, so "
              "the result runs on a machine with no Python at all."))
    p_bundle.add_argument(
        "--python-dist",
        help="A python-build-standalone tarball you already have, instead of "
             "downloading one.")
    p_bundle.add_argument(
        "--python-target", default="x86_64-unknown-linux-gnu",
        help="Which build to fetch, e.g. x86_64-pc-windows-msvc.")

    p_serve = sub.add_parser("serve", help="Run the HTTP/JSON integration service.")
    p_serve.set_defaults(func=serve)
    p_serve.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_serve.add_argument("--storage", default=":memory:")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765,
                         help="0 lets the OS pick a free one; pair with "
                              "--announce to find out which.")
    p_serve.add_argument("--no-strict", action="store_true")
    _add_layer_args(p_serve)
    _add_embedding_args(p_serve)
    _add_service_args(p_serve)
    _add_llm_args(p_serve)

    p_demo = sub.add_parser("demo", help="Serve the browser demo UI (the sales demo).")
    p_demo.set_defaults(func=demo)
    p_demo.add_argument("--world-pack", default="worldpacks/cyberpunk-block")
    p_demo.add_argument("--storage", default=":memory:")
    p_demo.add_argument("--host", default="127.0.0.1")
    p_demo.add_argument("--port", type=int, default=8765)
    p_demo.add_argument("--no-strict", action="store_true")
    _add_layer_args(p_demo)
    _add_embedding_args(p_demo)
    _add_service_args(p_demo)
    _add_llm_args(p_demo)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
