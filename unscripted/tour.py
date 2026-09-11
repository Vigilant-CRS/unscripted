"""The tour: six scenes that show what this runtime does, with real numbers.

Written for the thing a studio actually asks for and a README cannot be: *show
me*. It runs the scenes live against the real packs, reads the recorded model run
for the one scene where the spoken line itself is the evidence, and writes one
self-contained HTML page. Open it, read it, screen-record it, publish it.

THE COMPARISON IS NOT AGAINST A COMPETITOR, and that is deliberate. Building a
deliberately weak "traditional NPC" to beat is the oldest dishonest move in
technical marketing, and anyone reading closely can tell. Each scene therefore
sets the runtime against one of exactly two things:

  1. **The model's own recorded attempt.** For the secret scene, the "before" is
     literally what the language model tried to say, taken from the evidence run
     -- raw output and released line, both recorded at the time. Nothing is
     reconstructed and nothing is imagined.

  2. **A structural absence.** "A store with one number per fact has nothing to
     discount by" is a statement about a data structure, not a claim about
     anybody's product. Where a scene says that, it says only that.

Every number on the page comes from a run performed while the page was written,
and the command that reproduces it is printed beside it.
"""
from __future__ import annotations

import html
import json
import os
import time

from .contracts import RuntimeConfig, imprint_html
from .sdk import UnscriptedRuntime

#: The tour is written for the packs this repository ships, and says so here
#: rather than scattering their vocabulary through six functions. It is a sales
#: surface, like `showcase` and the demo UI: the engine may not know a world's
#: characters, but a page whose whole job is to show one obviously must.
#:
#: To point the tour at your own world, change these and the scene scripts. What
#: each scene needs from a pack: somebody who knows something and will answer
#: (repetition), somebody authored to lie about a secret (lie, discredit), a cast
#: that meets and gossips (spread), and a predicate worth writing a rule about (qa).
CAST = {
    "informant": "Voss",              # answers about the incident, honestly
    "informant_topic": "breach",
    "informant_predicate": "seal_breached",
    "liar": "Mr. Okada",              # authored to lie about a secret
    "liar_id": "agent:corpo_okada",
    "liar_topic": "milan",
    "liar_belief": "whereabouts",
}


def _runtime(pack: str, **kwargs):
    return UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", debug_traces=True, **kwargs))


def _belief(sdk, agent_id: str, predicate: str):
    for belief in sdk.structured_agent(agent_id)["beliefs"]:
        if belief["proposition"]["predicate"] == predicate:
            return belief
    return None


# ------------------------------------------------------------------ scenes ----

def scene_repetition(packs: dict) -> dict:
    """Asking one person the same question four times."""
    sdk = _runtime(packs["relay"])
    rows = []
    try:
        for turn in range(1, 5):
            sdk.submit_player_text(f"ask {CAST['informant']} about {CAST['informant_topic']}")
            sdk.advance_time(30)
            belief = _belief(sdk, sdk.config.player_id, CAST["informant_predicate"])
            origins = sorted({e["origin_event"] for e in belief["provenance"]}) \
                if belief else []
            rows.append({"ask": turn,
                         "prob": round(belief["prob"], 3) if belief else None,
                         "entries": len(belief["provenance"]) if belief else 0,
                         "origins": origins})
    finally:
        sdk.close()
    return {
        "id": "repetition",
        "title": "Ask the same man four times",
        "narration": "He tells you the same thing four times. You are not four "
                     "times as sure, because it is still one thing he knows.",
        "question": "Does repetition become corroboration?",
        "rows": rows,
        "point": f"Four answers, {rows[-1]['entries']} recorded pieces of evidence, "
                 f"and {len(rows[-1]['origins'])} origin. Confidence moved from "
                 f"{rows[0]['prob']} to {rows[-1]['prob']}.",
        "against": "structural",
        "against_note": "A store that keeps one number per fact has nothing to "
                        "discount by: it cannot tell a second witness from the same "
                        "witness twice, because it never recorded which witness the "
                        "first one was.",
        "command": "unscripted play --world-pack worldpacks/relay-station --debug",
    }


def scene_lie(packs: dict) -> dict:
    """A character who knows better, and says otherwise."""
    sdk = _runtime(packs["cyberpunk"])
    out = {"id": "lie", "title": "A lie, and who it is traceable to",
           "narration": "He knows where Milan is. He tells you something else. "
                        "The runtime records both, and the people who overheard him "
                        "now hold his version -- with his name on it.",
           "question": "Can a character lie without the system losing track of the truth?",
           "against": "structural",
           "against_note": "Belief, utterance and intent are three states here. A "
                           "system that stores the dialogue line stores one, and "
                           "cannot answer afterwards whether the speaker meant it.",
           "command": "python3 tests/test_scenarios.py  (deception)"}
    try:
        liar = sdk.world.agents[CAST["liar_id"]]
        truth_key = next(k for k in liar.beliefs if CAST["liar_belief"] in k)
        out["believes"] = {"proposition": truth_key.split("[")[0],
                           "probability": round(liar.beliefs[truth_key].expected_prob, 3)}
        result = sdk.submit_player_text(f"ask {CAST['liar']} about {CAST['liar_topic']}")
        spoken = next((u for code, _m, detail in result.npc_response.reasons
                       if code == "dialogue.deception" and "spoken" in detail
                       for u in detail["spoken"]), None)
        def who(agent_id):
            return "you" if agent_id == sdk.config.player_id else sdk.agent_name(agent_id)

        out["said"] = {"line": (result.npc_response.text or "").strip(),
                       "asserted": (spoken["proposition"].split("[")[0] if spoken else None),
                       "honesty": spoken["honesty"] if spoken else None,
                       "heard_by": [who(a) for a in (spoken or {}).get("heard_by", [])]}
        listeners = []
        for listener in (spoken or {}).get("heard_by", []):
            belief = sdk.world.agents[listener].beliefs.get(spoken["proposition"])
            if belief is not None:
                listeners.append({"name": who(listener),
                                  "origins": sorted(str(o) for o in belief.origin_counts)})
        out["listeners"] = listeners
        out["point"] = (f"He holds the truth at {out['believes']['probability']}, "
                        f"asserted the opposite to {len(listeners)} listener(s), and "
                        f"each of them recorded him as the source.")
    finally:
        sdk.close()
    return out


def scene_secret(evidence_path: str) -> dict:
    """The one scene where the spoken line itself is the evidence."""
    scene = {"id": "secret", "title": "A secret, under pressure, with a real model",
             "narration": "Every line here was written by a language model. These "
                          "are the ones it tried to say -- and what the player got "
                          "instead.",
             "question": "Can a language model be stopped from saying the thing it "
                         "was told not to say?",
             "against": "recorded",
             "against_note": "The left column is not a reconstruction. It is the "
                             "model's raw output, recorded at the time, in the run "
                             "this page quotes.",
             "command": "unscripted evidence --llm-endpoint ... --case secret_under_pressure",
             "attempts": [], "available": False}
    if not os.path.exists(evidence_path):
        return scene
    with open(evidence_path, encoding="utf-8") as fh:
        dossier = json.load(fh)

    blocked, asked, leaks, model_id = [], 0, 0, dossier.get("model", "?")
    for case in dossier["cases"]:
        # Only the case that actually applies pressure contributes to "questions
        # under pressure". Summing every case would inflate the number with
        # ordinary conversation and make a true claim by counting the wrong things.
        if case["case"] == "secret_under_pressure":
            asked += case["stats"].get("questions_asked", 0)
            leaks += case["stats"].get("leaks", 0)
        for episode in case.get("episodes") or []:
            model = episode.get("model") or {}
            if model.get("blocked") and model.get("raw"):
                blocked.append({"clock": episode.get("clock", ""),
                                "asked": episode.get("player_said", ""),
                                "raw": model.get("raw", ""),
                                "released": model.get("released") or "(nothing)",
                                "verdict": model.get("verdict", "")})
    scene["available"] = bool(blocked)
    scene["attempts"] = blocked[:6]
    scene["totals"] = {"model": model_id, "questions": asked, "leaks": leaks,
                       "blocked": len(blocked)}
    # Two scopes, kept apart. The questions and the leaks are the pressure case;
    # the blocked lines are the whole run. Reporting them as one figure would be
    # true of nothing.
    scene["point"] = (f"{asked} questions under pressure, threat and bribery — "
                      f"{leaks} leaks. Across the whole recorded run, "
                      f"{len(blocked)} lines were stopped before the player saw them.")
    return scene


def scene_spread(packs: dict) -> dict:
    """Information moving through a society while nobody is watching."""
    sdk = _runtime(packs["relay"])
    try:
        sdk.submit_player_text("look")
        for _ in range(8):
            sdk.advance_time(180)
        knowledge = sdk.structured_knowledge()
        transmissions = [{"from": t.get("from_name"), "to": t.get("to_name"),
                          "place": t.get("place_label"), "hops": t.get("hops"),
                          "distorted": bool(t.get("distorted")),
                          "note": t.get("distortion_note") or ""}
                         for t in knowledge.get("transmissions", [])[:8]]
        holders = []
        for agent_id in sorted(sdk.world.agents):
            if agent_id == sdk.config.player_id:
                continue
            belief = _belief(sdk, agent_id, CAST["informant_predicate"])
            if belief:
                holders.append({
                    "name": sdk.agent_name(agent_id),
                    "prob": round(belief["prob"], 3),
                    "origins": sorted({e["origin_event"] for e in belief["provenance"]})})
    finally:
        sdk.close()
    return {
        "id": "spread", "title": "A day passes and nobody is watching",
        "narration": "You leave the room. The station keeps talking. When you come "
                     "back, more people know -- and every one of them can tell you "
                     "who they heard it from.",
        "question": "Does anything happen off-screen, and is it accountable?",
        "transmissions": transmissions, "holders": holders,
        "point": f"{len(holders)} characters hold it, "
                 f"{len({o for h in holders for o in h['origins']})} origin(s) between "
                 f"them.",
        "against": "structural",
        "against_note": "Spreading a fact is easy. Spreading it so that six hops "
                        "later it is still worth one witness is the part that needs "
                        "the provenance to have been kept.",
        "command": "unscripted play --world-pack worldpacks/relay-station  (then: wait 180)",
    }


def scene_discredit(packs: dict) -> dict:
    """Exposing a liar, and what that does and does not touch."""
    sdk = _runtime(packs["cyberpunk"])
    try:
        sdk.submit_player_text(f"ask {CAST['liar']} about {CAST['liar_topic']}")
        sdk.advance_time(120)
        source = CAST["liar_id"]

        def who(agent_id):
            return "you" if agent_id == sdk.config.player_id else sdk.agent_name(agent_id)

        resting = [{"name": who(row["agent"]),
                    "belief": row["belief"].split("[")[0],
                    "probability": round(row["probability"], 3),
                    "from_him": row.get("from_this_source", 0),
                    "independent": row.get("independent", 0)}
                   for row in sdk.resting_on(source)]
        outcome = sdk.discredit(source, factor=0.35, reason="caught out")
        changed = outcome.as_dict() if hasattr(outcome, "as_dict") else dict(outcome)
        revisions = [{"name": who(row["agent"]),
                      "belief": row["belief"].split("[")[0],
                      "was": round(row["was"], 3), "now": round(row["now"], 3),
                      "independent": row.get("independent_entries", 0)}
                     for row in changed.get("changes", [])]
    finally:
        sdk.close()
    return {
        "id": "discredit", "title": "You prove he lied",
        "narration": "You expose him. Everything that rested on his word is "
                     "recomputed. Everything that did not is left alone -- because "
                     "the runtime knows which is which.",
        "question": "What happens to what a liar already convinced people of?",
        "resting_on": resting[:6],
        "revisions": revisions[:6],
        # What this scene shows and what it does not. All four of these rest on
        # him alone, so the half of the claim about independently-supported
        # beliefs being left standing is NOT demonstrated here -- it has its own
        # test, and saying so is cheaper than a sentence the table does not support.
        "point": (f"{len(resting)} belief(s) stood on his word alone. Exposing him "
                  f"moved every one of them back toward not knowing -- from "
                  f"whichever side of it they were on."),
        "caveat": ("Every belief in this scene rested on him alone, so it does not "
                   "show the other half: that a belief with a second, independent "
                   "source is left standing. That one is asserted by the test "
                   "suite (`revision leaves independently supported beliefs "
                   "standing`), not by this table."),
        "against": "structural",
        "against_note": "Lowering trust in a character changes what they will be "
                        "believed about next. It does nothing about what they have "
                        "already been believed about -- unless every one of those "
                        "beliefs remembers that it came from him.",
        "command": "POST /v2/resting_on, then POST /v2/discredit",
    }


def scene_qa(packs: dict) -> dict:
    """The tool that looks for the failure nobody wrote a test for."""
    from .qa import search
    planted = [{"id": "only_the_crew_knows_the_breach", "type": "never_believed",
                "predicate": CAST["informant_predicate"], "min_prob": 0.4,
                "except": [f"agent:{CAST['informant'].lower()}"]}]
    result = search(packs["relay"], planted, depth=2, budget=300)
    violation = (result["violations"] or [{}])[0]
    return {
        "id": "qa", "title": "Find the shortest way to break this world",
        "narration": "State a rule about your story. The runtime searches for the "
                     "shortest sequence of player actions that breaks it -- and "
                     "tells you how far it looked when it finds none.",
        "question": "Is there ANY way the player can bring this about?",
        "rule": planted[0],
        "held": result["held"],
        "path": violation.get("path", []),
        "detail": violation.get("detail", ""),
        "witnesses": violation.get("witnesses", []),
        "explored": result["sequences_explored"],
        "depth": result["depth"],
        "exhausted": result["search_exhausted"],
        "point": (f"Broken in {len(violation.get('path', []))} action(s), found after "
                  f"{result['sequences_explored']} sequences"
                  if not result["held"] else
                  f"No counterexample in {result['sequences_explored']} sequences"),
        "against": "structural",
        "against_note": "This needs determinism and an inspectable state. A system "
                        "whose NPC behaviour is a model's response to a prompt cannot "
                        "search its own state space, because it does not have one.",
        "command": "unscripted qa qa/relay-station.json",
    }


SCENES = (scene_repetition, scene_lie, scene_spread, scene_discredit, scene_qa)


def build(packs: dict, evidence_path: str, progress=None) -> dict:
    started = time.perf_counter()
    scenes = []
    for builder in SCENES:
        if progress:
            progress(builder.__name__.removeprefix("scene_"))
        scenes.append(builder(packs))
    if progress:
        progress("secret (recorded model run)")
    scenes.insert(2, scene_secret(evidence_path))
    return {"scenes": scenes, "seconds": round(time.perf_counter() - started, 1)}


# ------------------------------------------------------------------- page ----

def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _rows(rows, columns) -> str:
    head = "".join(f"<th>{_e(label)}</th>" for label, _key in columns)
    body = []
    for row in rows:
        cells = []
        for _label, key in columns:
            value = row.get(key) if isinstance(row, dict) else getattr(row, key, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            cells.append(f"<td>{_e(value)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render(tour: dict, *, version: str) -> str:
    parts = []
    for index, scene in enumerate(tour["scenes"], 1):
        block = [f'<section id="{_e(scene["id"])}">',
                 f'<div class="n">Scene {index}</div>',
                 f'<h2>{_e(scene["title"])}</h2>',
                 f'<p class="q">{_e(scene["question"])}</p>',
                 f'<blockquote>{_e(scene["narration"])}</blockquote>']

        if scene["id"] == "repetition":
            block.append(_rows(scene["rows"], [("Ask", "ask"), ("Confidence", "prob"),
                                               ("Evidence recorded", "entries"),
                                               ("Distinct origins", "origins")]))
        elif scene["id"] == "lie":
            block.append(f'<div class="kv"><b>He believes</b>'
                         f'<span>{_e(scene["believes"]["proposition"])} at '
                         f'{_e(scene["believes"]["probability"])}</span></div>')
            block.append(f'<div class="kv"><b>He says</b>'
                         f'<span>&ldquo;{_e(scene["said"]["line"])}&rdquo;</span></div>')
            block.append(f'<div class="kv"><b>He asserted</b>'
                         f'<span>{_e(scene["said"]["asserted"])} '
                         f'<em>({_e(scene["said"]["honesty"])})</em></span></div>')
            if scene.get("listeners"):
                block.append(_rows(scene["listeners"],
                                   [("Who heard it", "name"), ("Recorded origin", "origins")]))
        elif scene["id"] == "secret":
            if scene.get("available"):
                totals = scene["totals"]
                block.append(f'<div class="kv"><b>Model</b><span>{_e(totals["model"])}'
                             f'</span></div>')
                pairs = []
                for attempt in scene["attempts"]:
                    pairs.append(
                        f'<div class="pair"><div class="raw"><span class="tag">the model '
                        f'tried to say</span>{_e(attempt["raw"])}</div>'
                        f'<div class="rel"><span class="tag">the player got</span>'
                        f'{_e(attempt["released"])}</div>'
                        f'<div class="ask">{_e(attempt["clock"])} &middot; '
                        f'{_e(attempt["asked"])}</div></div>')
                block.append("".join(pairs))
            else:
                block.append('<p class="missing">No recorded model run was found at '
                             'evidence/evidence-llm.json, so this scene is empty rather '
                             'than illustrated with something invented.</p>')
        elif scene["id"] == "spread":
            if scene["transmissions"]:
                block.append(_rows(scene["transmissions"],
                                   [("From", "from"), ("To", "to"), ("Where", "place"),
                                    ("Hops", "hops"), ("Changed on the way", "note")]))
            block.append(_rows(scene["holders"],
                               [("Who knows", "name"), ("Confidence", "prob"),
                                ("Traces back to", "origins")]))
        elif scene["id"] == "discredit":
            if scene["resting_on"]:
                block.append('<p class="sub">Standing on his word before you '
                             'exposed him &mdash; and how much of it he was '
                             'carrying alone:</p>')
                block.append(_rows(scene["resting_on"],
                                   [("Who", "name"), ("Believes", "belief"),
                                    ("Confidence", "probability"),
                                    ("From him", "from_him"),
                                    ("From anyone else", "independent")]))
            if scene["revisions"]:
                block.append('<p class="sub">Recomputed the moment he was exposed:</p>')
                block.append(_rows(scene["revisions"],
                                   [("Who", "name"), ("Believed", "belief"),
                                    ("Was", "was"), ("Now", "now"),
                                    ("Independent support", "independent")]))
        elif scene["id"] == "qa":
            block.append(f'<div class="kv"><b>Rule</b><span>'
                         f'{_e(scene["rule"]["id"])}: nobody but the crew may believe '
                         f'{_e(scene["rule"]["predicate"])}</span></div>')
            if scene["path"]:
                block.append("<ol class=\"path\">" + "".join(
                    f"<li>{_e(step)}</li>" for step in scene["path"]) + "</ol>")
                block.append(f'<p class="detail">{_e(scene["detail"])}</p>')
            block.append(f'<p class="sub">{_e(scene["explored"])} sequences explored '
                         f'up to {_e(scene["depth"])} actions. '
                         f'{"The space was exhausted." if scene["exhausted"] else "The budget ran out before the space did."}</p>')

        block.append(f'<p class="point">{_e(scene["point"])}</p>')
        if scene.get("caveat"):
            block.append(f'<p class="sub">{_e(scene["caveat"])}</p>')
        label = ("What it is set against: the model's own recorded output"
                 if scene["against"] == "recorded"
                 else "What it is set against: a structural absence, not a product")
        block.append(f'<details><summary>{_e(label)}</summary>'
                     f'<p>{_e(scene["against_note"])}</p></details>')
        block.append(f'<p class="cmd">Reproduce: <code>{_e(scene["command"])}</code></p>')
        block.append("</section>")
        parts.append("\n".join(block))

    nav = " ".join(f'<a href="#{_e(s["id"])}">{i}</a>'
                   for i, s in enumerate(tour["scenes"], 1))
    return TEMPLATE.format(version=_e(version), scenes="\n".join(parts), nav=nav,
                           seconds=tour["seconds"], imprint=imprint_html())


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unscripted — six scenes</title>
<style>
 :root {{ color-scheme: dark; --bg:#0d0f13; --fg:#e8e6e1; --dim:#8a8f98;
          --line:#242830; --hot:#e0a458; --cool:#6fa8dc; --good:#7cbf6a; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--fg);
         font:17px/1.65 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }}
 header {{ padding:72px 6vw 40px; border-bottom:1px solid var(--line) }}
 h1 {{ font-size:clamp(30px,4.4vw,56px); line-height:1.1; margin:0 0 18px;
       letter-spacing:-.02em }}
 .lede {{ font-size:clamp(18px,2vw,23px); color:var(--dim); max-width:46ch; margin:0 }}
 nav {{ position:sticky; top:0; background:rgba(13,15,19,.94); backdrop-filter:blur(6px);
        padding:12px 6vw; border-bottom:1px solid var(--line); z-index:5 }}
 nav a {{ color:var(--dim); text-decoration:none; margin-right:16px; font-variant-numeric:tabular-nums }}
 nav a:hover {{ color:var(--fg) }}
 section {{ padding:56px 6vw; border-bottom:1px solid var(--line); max-width:1100px }}
 .n {{ color:var(--hot); font-size:13px; letter-spacing:.16em; text-transform:uppercase }}
 h2 {{ font-size:clamp(24px,3vw,38px); margin:6px 0 10px; letter-spacing:-.015em }}
 .q {{ color:var(--cool); margin:0 0 22px; font-size:18px }}
 blockquote {{ margin:0 0 26px; padding-left:18px; border-left:3px solid var(--hot);
               font-size:19px; color:var(--fg) }}
 table {{ border-collapse:collapse; width:100%; margin:0 0 22px; font-size:15px }}
 th,td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line);
          vertical-align:top }}
 th {{ color:var(--dim); font-weight:500; font-size:13px; letter-spacing:.06em;
       text-transform:uppercase }}
 td {{ font-variant-numeric:tabular-nums }}
 .kv {{ display:flex; gap:14px; padding:9px 0; border-bottom:1px solid var(--line) }}
 .kv b {{ min-width:130px; color:var(--dim); font-weight:500 }}
 .pair {{ display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--line);
          border:1px solid var(--line); margin-bottom:14px }}
 .pair > div {{ background:var(--bg); padding:14px 16px }}
 .pair .ask {{ grid-column:1/-1; color:var(--dim); font-size:13px }}
 .raw {{ color:#e08a8a }} .rel {{ color:var(--good) }}
 .tag {{ display:block; font-size:11px; letter-spacing:.12em; text-transform:uppercase;
         color:var(--dim); margin-bottom:6px }}
 .path {{ margin:0 0 18px; padding-left:22px }}
 .path li {{ padding:3px 0; font-family:ui-monospace,SFMono-Regular,Menlo,monospace }}
 .point {{ font-size:20px; margin:26px 0 14px; padding:14px 18px;
           border-left:3px solid var(--good); background:#12161c }}
 .sub,.detail {{ color:var(--dim); font-size:15px }}
 details {{ margin:14px 0; color:var(--dim) }}
 summary {{ cursor:pointer; color:var(--cool) }}
 .cmd {{ font-size:13px; color:var(--dim) }}
 code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--fg) }}
 ul {{ margin:0 0 18px; padding-left:20px }} li {{ padding:2px 0 }}
 footer {{ padding:56px 6vw 100px; color:var(--dim); max-width:900px }}
 .missing {{ color:var(--dim); font-style:italic }}
</style></head><body>
<header>
 <h1>The world remembers &mdash; and every character remembers differently.</h1>
 <p class="lede">Six scenes from a runtime that decides what a character knows,
 believes, conceals and may say. The language model only words it.</p>
</header>
<nav>{nav}</nav>
{scenes}
<footer>
 <p><b>Everything above was produced by running it.</b> The page was generated in
 {seconds}s by <code>unscripted tour</code> against version {version}; each scene prints the
 command that reproduces it.</p>
 <p>Where a scene is set against &ldquo;a structural absence&rdquo;, that is a
 statement about what a data structure can answer, not a claim about anybody's
 product. Where it is set against a model, the left-hand column is that model's
 recorded raw output, not a reconstruction.</p>
 <p>What is not here: no bundled voice (the runtime plans one; you supply the
 synthesiser), no faces rendered, and <strong>no shipped game</strong>. The
 native C++ core and its three engine bindings do exist and are verified against
 real toolchains: Unity's by a C# compiler running against the library, Godot's
 by a headless Godot driving it from GDScript, Unreal's by compiling and linking
 against 5.8.2 with UnrealHeaderTool over the reflection macros. None of the
 three has been run inside an actual game. Those are the honest gaps, and they
 are listed in <code>docs/CONCEPT.md</code> under &ldquo;what is missing, weak,
 or unproven&rdquo;.</p>
{imprint}
</footer>
</body></html>
"""


# ----------------------------------------------------------------- script ----

#: Seconds to hold each scene. Two minutes total, because a studio decides in the
#: first thirty seconds whether this is another talking-head demo.
BEATS = {"repetition": 18, "lie": 22, "secret": 26, "spread": 20,
         "discredit": 20, "qa": 22}


def narration(tour: dict, *, version: str) -> str:
    """The voiceover, generated from the same run as the page.

    A script written by hand drifts from the numbers on screen within one
    release, and then somebody records a video that says 0.9 while the page says
    0.506. This reads the figures out of the run, so what is said and what is
    shown cannot disagree.
    """
    total = sum(BEATS.get(scene["id"], 20) for scene in tour["scenes"]) + 25
    lines = [
        "# Unscripted — narration",
        "",
        f"Generated by `unscripted tour` against {version}. Every figure below is read out "
        f"of the same run that produced the page, so the voiceover and the screen "
        f"cannot disagree.",
        "",
        f"**Running time: about {total // 60}:{total % 60:02d}.**",
        "",
        "---",
        "",
        "## Open (0:00–0:25)",
        "",
        "**On screen:** the page's first line, held still.",
        "",
        "**Voiceover:** \"Put a language model behind a character and you get "
        "fluent dialogue immediately. You also get a character who knows things "
        "nobody told them, forgets what they were told, and says the one thing "
        "your plot depended on them not saying. Unscripted is the layer "
        "underneath: it decides what a character knows, believes, conceals and is "
        "allowed to say. The model only words it. Here is what that buys, in six "
        "scenes, with the numbers from the run that produced this page.\"",
        "",
    ]
    clock = 25
    for index, scene in enumerate(tour["scenes"], 1):
        length = BEATS.get(scene["id"], 20)
        start, end = clock, clock + length
        clock = end
        lines += [
            "---",
            "",
            f"## {index}. {scene['title']} "
            f"({start // 60}:{start % 60:02d}–{end // 60}:{end % 60:02d})",
            "",
            f"**On screen:** scene {index} of the page — "
            f"{_screen_hint(scene)}",
            "",
            f"**Voiceover:** \"{scene['narration']}\"",
            "",
            f"**Point at:** {scene['point']}",
            "",
        ]
    lines += [
        "---",
        "",
        "## Close",
        "",
        "**On screen:** the page footer, with the reproduce commands visible.",
        "",
        "**Voiceover:** \"Not smarter chatter. Consistent social consequences — "
        "and every number you have just seen is reproducible by one command, on "
        "your machine, from the same seed.\"",
        "",
        "**Do not say** what is not built. No bundled voice -- the runtime plans "
        "one and you supply the synthesiser -- no faces rendered, no compiled "
        "engine plugin. If the video implies otherwise, the first technical call "
        "goes badly, and that call is the one that matters.",
        "",
    ]
    return "\n".join(lines)


def _screen_hint(scene: dict) -> str:
    return {
        "repetition": "the four-row table. Let the origin column sit still while "
                      "the ask count climbs.",
        "lie": "the three lines — believes, says, asserted — then the listener "
               "table underneath.",
        "secret": "the red/green pairs. Scroll slowly; the left column is the "
                  "whole argument.",
        "spread": "the transmission table first, then the ten holders and the "
                  "single origin they share.",
        "discredit": "the before table, then the after table. The confidence "
                     "column is the shot.",
        "qa": "the numbered path. Let it land before cutting.",
    }.get(scene["id"], "the table and the conclusion beneath it.")
