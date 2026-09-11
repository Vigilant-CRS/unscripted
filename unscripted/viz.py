"""A claim moving through a society, as something you can watch.

Every other surface in this repository answers a question in text: who knows
what, on whose word, how sure. That is the right form for a test and the wrong
form for the thirty seconds in which somebody decides whether this is
interesting. The thing that makes this runtime worth having is a *process* --
people move, meet, tell each other things, get them slightly wrong, decline to
pass them on, and slowly forget the afternoon while keeping the conclusion -- and
a process wants a picture that moves.

So this records a real run frame by frame and writes one self-contained page that
plays it back:

    where everyone is          routines, so the cast actually meets
    what they believe          confidence in one tracked claim, as colour
    who told whom              a pulse along the edge, at the moment it happened
    who got it wrong           a ring, and what changed on the way
    who said nothing           the refusals, which are half the behaviour
    what they still remember   the occasion fading while the belief stays

Nothing here is illustrative. Every frame is the state the runtime was actually
in, and every arrow is a transmission that actually occurred, read out of the
reason traces the runtime emits anyway. The page embeds the recording as JSON, so
what is drawn can be checked against what was recorded.
"""
from __future__ import annotations

import json
import math

from .contracts import RuntimeConfig, imprint_html
from .sdk import UnscriptedRuntime


def layout(world) -> dict:
    """Deterministic positions for places: a ring, ordered by how connected they are.

    Not a force simulation. A force layout looks organic and moves every time you
    run it, which is the opposite of what this repository sells; the same world
    must produce the same picture, and a ring is legible at ten characters.
    """
    places = sorted(world.places)
    degree = {p: len((world.places[p] or {}).get("exits") or ()) for p in places}
    # Busiest place in the middle if one clearly dominates, everything else around.
    ordered = sorted(places, key=lambda p: (-degree[p], p))
    hub = ordered[0] if len(places) > 4 and degree[ordered[0]] > degree[ordered[1]] else None
    ring = [p for p in places if p != hub]

    positions = {}
    if hub:
        positions[hub] = (0.0, 0.0)
    count = max(1, len(ring))
    for index, place in enumerate(ring):
        angle = 2 * math.pi * index / count - math.pi / 2
        radius = 1.0
        positions[place] = (round(radius * math.cos(angle), 4),
                            round(radius * math.sin(angle), 4))
    return positions


def _role_of(agent) -> str:
    """What this character is, in one readable word.

    A role is authored as `{"role": "role:trader", "context": "group:crew"}`; the
    page had been printing the dict, which reached the screen as
    `[object Object]` under a character's name. Worth a named function rather
    than a nested expression: whatever the authored shape becomes, the page keeps
    asking one question.
    """
    for role in getattr(agent, "roles", None) or ():
        name = role.get("role") if isinstance(role, dict) else role
        if name:
            return str(name).split(":")[-1].replace("_", " ")
    for identity in getattr(agent, "identities", None) or ():
        name = identity.get("id") if isinstance(identity, dict) else identity
        if name:
            return str(name).split(":")[-1].replace("_", " ")
    return "resident"


def _label(world, place_id: str) -> str:
    entry = world.places.get(place_id) or {}
    return entry.get("label") or place_id.split(":")[-1].replace("_", " ").title()


def plain_claim(sdk, predicate: str) -> str:
    """What this claim is, in words a person can read.

    The predicate form is exact and unreadable. Somebody watching this page for
    the first time has thirty seconds of patience and does not have the ontology
    in their head, so the page leads with the sentence the world pack already
    wrote for the same event and keeps the formal version underneath it.
    """
    for event in sdk.world.scenario_events:
        payload = event.payload or {}
        if (payload.get("proposition") or {}).get("predicate") == predicate:
            if payload.get("summary"):
                return str(payload["summary"])
    for agent in sdk.world.agents.values():
        for memory in getattr(agent, "memory", []):
            content = getattr(memory, "content", "")
            if predicate.split("_")[0] in str(content).lower():
                return str(content)
    return predicate.replace("_", " ")


def _tracked_belief(sdk, agent_id: str, predicate: str):
    for belief in sdk.structured_agent(agent_id)["beliefs"]:
        if belief["proposition"]["predicate"] == predicate:
            return belief
    return None


#: How the runtime labels an episode by its activation: vivid above 0, faint down
#: to -1.5, lost below it. Taken from the read model rather than restated, so this
#: page cannot drift from what the inspector says.
#:
#: The phrase a relayed claim is remembered by. It comes from the diffusion layer
#: and contains no world vocabulary, which is why matching on it keeps this
#: module free of any particular pack.
RELAY_EPISODE = "passes on what they heard"


def _occasion(sdk, agent_id: str):
    """How vividly this character still recalls *being told*, as opposed to what
    they now believe.

    The two come apart, and that is the whole point of the memory layer: the
    conclusion outlives the afternoon it was formed on. A character who is still
    sure the seal failed but can no longer bring to mind who said so is the
    ordinary human case, and watching the episode fade under a belief that does
    not is the most human thing this runtime does.

    An earlier version of this looked for the *predicate* in the memory text.
    Episodes carry plain language -- "Commander Voss passes on what they heard" --
    so it matched nothing and drew every character as having forgotten
    immediately, which was a bug rendered as a finding. Worth the comment.
    """
    best = None
    for memory in sdk.structured_agent(agent_id)["memory"]:
        if RELAY_EPISODE in (memory.get("content") or ""):
            if best is None or memory["activation"] > best["activation"]:
                best = memory
    if best is None:
        return None
    return {"activation": round(best["activation"], 3), "status": best["status"]}


def record(pack: str, *, predicate: str, hours: float = 60.0,
           step_minutes: int = 30, script=(), progress=None) -> dict:
    """Run the world and keep every frame.

    `script` is a list of (step_index, player_command): the player's interventions,
    placed at known moments so the recording can be narrated. They are ordinary
    turns -- nothing about them is special-cased.
    """
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:", debug_traces=True))
    steps = int(hours * 60 / step_minutes)
    scripted = {int(index): text for index, text in script}

    try:
        places = layout(sdk.world)
        claim_text = plain_claim(sdk, predicate)
        world = {
            "places": [{"id": pid, "label": _label(sdk.world, pid),
                        "x": places[pid][0], "y": places[pid][1]}
                       for pid in sorted(places)],
            "agents": [{"id": aid,
                        "name": sdk.agent_name(aid),
                        "role": _role_of(agent)}
                       for aid, agent in sorted(sdk.world.agents.items())
                       if aid != sdk.config.player_id],
        }
        known_agents = [a["id"] for a in world["agents"]]
        frames, history = [], {aid: [] for aid in known_agents}

        sdk.submit_player_text("look")
        for step in range(steps):
            said, lies = None, []
            if step in scripted:
                turn = sdk.submit_player_text(scripted[step])
                said = {"command": scripted[step],
                        "reply": (turn.message or "").strip()[:220]}
                lies.extend(_lies_in(turn))
            outcome = sdk.advance_time(step_minutes)
            traces = outcome["last_trace"]

            tells, silence, moves = [], [], []
            for code, _magnitude, detail in (traces.get("_diffusion") or []):
                if code == "diffusion.told":
                    tells.append({"from": detail["speaker"], "to": detail["listener"],
                                  "place": detail.get("place"),
                                  "hops": detail.get("hops", 0),
                                  "distorted": bool(detail.get("distorted")),
                                  "note": detail.get("distortion_kind") or "",
                                  "proposition": detail.get("proposition", "")})
                elif code == "diffusion.stifled":
                    silence.append({"from": detail.get("speaker"),
                                    "to": detail.get("listener"), "kind": "stifled",
                                    "why": "they already knew, so he stops carrying it"})
                elif code == "diffusion.not_worth_telling":
                    silence.append({"from": detail.get("speaker"),
                                    "to": detail.get("listener"), "kind": "quiet",
                                    "why": "not worth telling them"})
            for code, _magnitude, detail in (traces.get("_routine") or []):
                if code == "routine.moved":
                    moves.append({"agent": detail["agent"], "from": detail["from"],
                                  "to": detail["to"],
                                  "activity": detail.get("activity", "")})

            tells = _dedupe(tells, ("from", "to", "proposition"))
            silence = _dedupe(silence, ("from", "to", "kind"))

            at, confidence, evidence, version, recalls, torn = {}, {}, {}, {}, {}, {}
            for aid in known_agents:
                at[aid] = sdk.world.agents[aid].location
                belief = _tracked_belief(sdk, aid, predicate)
                if belief:
                    confidence[aid] = round(belief["prob"], 3)
                    evidence[aid] = len(belief["provenance"])
                    torn[aid] = round(belief.get("conflict", 0.0), 3)
                    version[aid] = _version_key(belief["proposition"]["slots"])
                    recalls[aid] = _occasion(sdk, aid)
                    if not history[aid] or history[aid][-1]["p"] != confidence[aid]:
                        history[aid].append({
                            "t": sdk.world.world_time, "p": confidence[aid],
                            "clock": _clock(sdk.world.world_time),
                            "origins": sorted({e["origin_event"]
                                               for e in belief["provenance"]}),
                            "version": version[aid],
                            "evidence": len(belief["provenance"])})

            frames.append({
                "t": sdk.world.world_time,
                "clock": _clock(sdk.world.world_time),
                "at": at, "p": confidence, "ev": evidence, "version": version,
                "torn": torn, "recalls": recalls, "tells": tells, "silence": silence,
                "moves": moves, "said": said, "lies": lies,
            })
            if progress and step % 20 == 0:
                progress(f"{step}/{steps} steps, {len(frames)} frames")
    finally:
        sdk.close()

    # Which version is "the" version can only be decided once the run is over.
    # Deciding it from the first belief seen would make whoever happened to be
    # sorted first the arbiter of the truth, which is both wrong and unstable.
    # The canonical version is the one the most characters end up holding; every
    # other one is a variant, and the page shows who holds which.
    counts = {}
    for frame in frames:
        for key in frame["version"].values():
            counts[key] = counts.get(key, 0) + 1
    canonical = max(counts, key=lambda key: (counts[key], key)) if counts else ""
    for frame in frames:
        frame["wrong"] = sorted(aid for aid, key in frame["version"].items()
                                if key != canonical)

    return {"world": world, "predicate": predicate, "claim": claim_text,
            "chapters": chapters(frames, len(known_agents)),
            "canonical": canonical,
            "variants": sorted(k for k in counts if k != canonical),
            "frames": frames, "history": history, "step_minutes": step_minutes}


def _lies_in(turn) -> list:
    """Lies told this turn, as the runtime recorded them.

    Not inferred from the text -- the runtime knows, because a lie is a
    commitment whose proposition differs from the speaker's belief, and it says
    so in the reason trace. Reading it back out of the prose would be guessing at
    something that is already a fact in the record.
    """
    response = getattr(turn, "npc_response", None)
    if response is None:
        return []
    # The trace carries the deception across more than one entry: one names what
    # was said, another how strongly the speaker holds the opposite. Reading only
    # the first loses the number that makes it a lie rather than a mistake.
    conviction = None
    for code, _magnitude, detail in getattr(response, "reasons", ()):
        if code == "dialogue.deception" and "speaker_believes_it_with" in detail:
            conviction = detail["speaker_believes_it_with"]
    out = []
    for code, _magnitude, detail in getattr(response, "reasons", ()):
        if code != "dialogue.deception" or "spoken" not in detail:
            continue
        for utterance in detail["spoken"]:
            if utterance.get("honesty") == "lie":
                out.append({"speaker": detail.get("speaker") or response.speaker_id,
                            "asserted": utterance["proposition"].split("[")[0],
                            "believed_with": conviction,
                            "heard_by": utterance.get("heard_by", [])})
    return out


def _dedupe(rows: list, keys: tuple) -> list:
    """One entry per distinct thing that happened in this window.

    The reason trace can log the same speaker/listener pair more than once inside
    one step. Left as-is, the ticker shows it twice, and a viewer counts two
    events where the world had one.
    """
    seen, out = set(), []
    for row in rows:
        signature = tuple(row.get(key) for key in keys)
        if signature in seen:
            continue
        seen.add(signature)
        out.append(row)
    return out


#: What each moment costs a team that does not have it. Written in the terms a
#: technical director actually uses, and kept to what is structurally true of a
#: flat design rather than to claims about anybody's product.
STAKES = {
    "first": "Authored knowledge is easy. Everything after this is the part that "
             "is normally hand-maintained.",
    "channel": "A broadcast usually sets a global flag, and from then on the whole "
               "cast 'knows'. Here the intercom, the wire or the pulpit reaches only "
               "the people who were listening, at the attention each of them was "
               "authored with, and it stays ONE source no matter how many heard it.",
    "spread": "Scripted worlds need a flag for each pair of characters who might "
              "pass this on. That authoring cost grows with the square of the cast. "
              "This is the cast simply talking, on the routines you wrote.",
    "changed": "Nobody authored a wrong version. It came out of being retold, and it "
               "is still traceable to the true original -- which is what makes a "
               "false lead a puzzle instead of a bug report.",
    "lie": "A dialogue system stores the line. Here the lie is a fact about the "
           "world with the liar attached to it, so exposing him later can undo what "
           "he convinced people of.",
    "torn": "A single truth value has to pick. A character who has heard both can "
            "stay torn here, be visibly torn, and be convinced later by better "
            "evidence rather than by the most recent line.",
    "half": "",
    "all": "The state you would otherwise reach by setting one flag -- except every "
           "one of them can tell you who they heard it from, and how sure they are.",
    "forgot": "Memory that only grows is why generative NPCs quote something from "
              "forty hours of play ago. This one lets the occasion go and keeps the "
              "conclusion, which is what people do.",
}


def chapters(frames: list, cast: int) -> list:
    """The four or five moments worth jumping to, found in the recording itself.

    A five-day run is 240 frames and the interesting thirty seconds are somewhere
    in the middle. Asking a viewer to find them by dragging a slider is asking
    them to leave. These are computed rather than authored, so they are true of
    *this* recording and not of the one somebody had in mind when they wrote the
    captions.
    """
    marks, seen = [], set()

    def mark(key, frame_index, title, note):
        if key in seen:
            return
        seen.add(key)
        marks.append({"frame": frame_index, "title": title, "note": note,
                      "stakes": STAKES.get(key, ""),
                      "clock": frames[frame_index]["clock"]})

    previous = 0
    for index, frame in enumerate(frames):
        known = len(frame["p"])
        # A jump in holders with nobody having spoken is a channel: the intercom,
        # the wire, the pulpit. Worth its own mark, because it is the one route
        # that reaches many people at once and still counts as a single source --
        # which is exactly what makes it dangerous later.
        if known > previous + 1 and not frame["tells"]:
            mark("channel", index, "A channel carries it",
                 f"{known - previous} people hear it at once, from one source. "
                 f"Hearing it on the wire and then from a witness is still one "
                 f"witness.")
        previous = known
        lost = sum(1 for value in frame["recalls"].values()
                   if (value or {}).get("status") == "lost")
        if known:
            mark("first", index, "One person knows",
                 "Nobody else has heard it yet.")
        if frame["tells"]:
            mark("spread", index, "It starts moving",
                 "Two people are in the same room, and one of them mentions it.")
        if any(t["distorted"] for t in frame["tells"]):
            mark("changed", index, "It changes on the way",
                 "Somebody passes on a version that is not quite what they were told.")
        if frame.get("lies"):
            mark("lie", index, "Somebody lies about it",
                 "He asserts what he does not believe, and every listener records "
                 "him as the source.")
        if any(value > 0.3 for value in (frame.get("torn") or {}).values()):
            mark("torn", index, "Somebody has heard both",
                 "Evidence for and against at once. Being torn is a state here, "
                 "not an error.")
        if known >= max(2, cast // 2):
            mark("half", index, "Half of them hold it", "")
        if known >= cast:
            mark("all", index, "Everyone holds it", "")
        if known and lost == known:
            mark("forgot", index, "And nobody remembers who told them",
                 "The conclusion outlived the afternoon it was formed on.")
    return marks


def _version_key(slots: dict) -> str:
    """The claim as held, so two characters holding different versions differ here."""
    return ", ".join(f"{key}={slots[key]}" for key in sorted(slots) if slots[key])


def _clock(minutes: int) -> str:
    day, rest = divmod(int(minutes), 1440)
    return f"day {day} {rest // 60:02d}:{rest % 60:02d}"


# ------------------------------------------------------------------- page ----

def compact(data: dict) -> dict:
    """Index-addressed payload for the page.

    The readable recording repeats every agent id in every frame, which is fine
    for a JSON file somebody greps and wasteful inside a page that has to load in
    one go. Agents become indices; nothing else changes.
    """
    ids = [a["id"] for a in data["world"]["agents"]]
    index = {aid: position for position, aid in enumerate(ids)}
    places = [p["id"] for p in data["world"]["places"]]
    pindex = {pid: position for position, pid in enumerate(places)}

    frames = []
    for frame in data["frames"]:
        frames.append({
            "c": frame["clock"],
            "a": [pindex.get(frame["at"].get(aid), -1) for aid in ids],
            "p": [frame["p"].get(aid, -1) for aid in ids],
            "e": [frame["ev"].get(aid, 0) for aid in ids],
            "k": [(frame.get("torn") or {}).get(aid, 0) for aid in ids],
            "w": [index[aid] for aid in frame["wrong"] if aid in index],
            "m": [[index[aid], (frame["recalls"].get(aid) or {}).get("status", ""),
                   (frame["recalls"].get(aid) or {}).get("activation", 0)]
                  for aid in ids if frame["recalls"].get(aid)],
            "t": [[index[t["from"]], index[t["to"]], t["hops"],
                   1 if t["distorted"] else 0, t.get("note", "")]
                  for t in frame["tells"]
                  if t["from"] in index and t["to"] in index],
            "s": [[index[s["from"]], index[s["to"]], s["why"], s.get("kind", "quiet")]
                  for s in frame["silence"]
                  if s.get("from") in index and s.get("to") in index],
            "v": [[index[m["agent"]], pindex.get(m["from"], -1),
                   pindex.get(m["to"], -1), m.get("activity", "")]
                  for m in frame["moves"] if m["agent"] in index],
            "said": frame["said"],
            "l": [[index.get(lie["speaker"], -1), lie["asserted"],
                   [index[a] for a in lie["heard_by"] if a in index]]
                  for lie in frame.get("lies", [])],
        })
    return {
        "agents": [{"n": a["name"], "r": a["role"]} for a in data["world"]["agents"]],
        "places": [{"n": p["label"], "x": p["x"], "y": p["y"]}
                   for p in data["world"]["places"]],
        "frames": frames,
        "claim": data.get("claim") or data["predicate"],
        # What a character says, short enough to read in a bubble while it fades.
        "short": _short_claim(data.get("claim") or data["predicate"]),
        "predicate": data["predicate"],
        "chapters": data.get("chapters") or [],
        "canonical": data["canonical"],
        "variants": data["variants"],
        "history": {str(index[aid]): entries for aid, entries in data["history"].items()},
        "step": data["step_minutes"],
    }


def _short_claim(claim: str, limit: int = 34) -> str:
    """The claim as it fits above a character's head."""
    text = claim.split(":")[-1].strip().rstrip(".")
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


def render(data: dict, *, version: str, pack: str) -> str:
    payload = json.dumps(compact(data), separators=(",", ":"))
    import html as _html
    return _PAGE.replace("__DATA__", payload) \
                .replace("__VERSION__", version) \
                .replace("__IMPRINT__", imprint_html()) \
                .replace("__PACK__", pack) \
                .replace("__CLAIM__", _html.escape(data.get("claim")
                                                   or data["predicate"])) \
                .replace("__PREDICATE__", _html.escape(data["predicate"]))


_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unscripted — how a claim travels</title>
<style>
 :root{color-scheme:dark;--bg:#0b0d11;--panel:#11141a;--line:#232833;--fg:#e9e7e2;
       --dim:#868d99;--hot:#e0a458;--cool:#6fa8dc;--bad:#d0619b;--good:#7cbf6a}
 *{box-sizing:border-box}
 html,body{height:100%;margin:0}
 body{background:var(--bg);color:var(--fg);font:15px/1.55 ui-sans-serif,-apple-system,
      "Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;overflow:hidden}
 header{padding:16px 22px 14px;border-bottom:1px solid var(--line);display:flex;
        align-items:flex-start;gap:24px;flex-wrap:wrap}
 header .kicker{color:var(--dim);font-size:11px;letter-spacing:.16em;
                text-transform:uppercase;margin-bottom:4px}
 header h1{font-size:clamp(17px,2vw,23px);margin:0 0 3px;font-weight:600;
           letter-spacing:-.015em;color:var(--fg);max-width:60ch}
 header .pred{color:var(--dim);font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
 header .meta{color:var(--dim);font-size:11.5px;margin-left:auto;text-align:right;
              line-height:1.45}
 #chapters{display:flex;gap:8px;padding:10px 22px;border-bottom:1px solid var(--line);
           overflow-x:auto;background:#0e1116}
 #chapters button{white-space:nowrap;font-size:12.5px;padding:6px 12px}
 #chapters button.now{border-color:var(--hot);color:var(--hot)}
 main{flex:1;display:flex;min-height:0}
 #stage{flex:1;min-width:0;position:relative}
 #stakes{position:absolute;left:0;right:0;bottom:14px;text-align:center;
         font-size:12.5px;color:#6b7280;pointer-events:none;padding:0 12vw;
         max-width:1100px;margin:0 auto;line-height:1.5}
 #caption{position:absolute;left:0;right:0;bottom:52px;text-align:center;
          font-size:15px;color:var(--dim);pointer-events:none;padding:0 30px}
 #caption b{color:var(--fg);font-weight:500}
 #caption em{color:var(--bad);font-style:normal}
 svg{width:100%;height:100%;display:block}
 aside{width:340px;border-left:1px solid var(--line);background:var(--panel);
       overflow-y:auto;padding:18px}
 aside h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);
          margin:0 0 10px;font-weight:500}
 aside section{margin-bottom:26px}
 .who{font-size:20px;margin:0 0 2px;letter-spacing:-.01em}
 .role{color:var(--dim);font-size:13px;margin:0 0 14px}
 .row{display:flex;justify-content:space-between;gap:10px;padding:6px 0;
      border-bottom:1px solid var(--line);font-size:13px}
 .row b{font-weight:500;color:var(--dim)}
 .row span{text-align:right}
 .row .num{color:var(--dim);font-variant-numeric:tabular-nums;font-size:12px}
 .chain{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--dim);
        word-break:break-all;padding:5px 0}
 .ticker{font-size:12.5px;line-height:1.5}
 .ticker div{padding:4px 0;border-bottom:1px solid var(--line);color:var(--dim)}
 .ticker b{color:var(--fg);font-weight:500}
 .ticker .d{color:var(--bad)}
 .ticker .q{color:var(--cool)}
 .ticker .lie{color:#e05252}
 #key{display:flex;flex-wrap:wrap;gap:8px 20px;padding:9px 22px;font-size:12px;
      color:var(--dim);border-top:1px solid var(--line);background:#0e1116}
 #key i{display:inline-block;width:10px;height:10px;border-radius:50%;
        margin-right:6px;vertical-align:-1px}
 footer{border-top:1px solid var(--line);padding:12px 22px;display:flex;
         align-items:center;gap:16px;background:var(--panel)}
 button{background:#1b2029;color:var(--fg);border:1px solid var(--line);border-radius:6px;
        padding:7px 14px;font:inherit;font-size:13px;cursor:pointer}
 button:hover{background:#232a35}
 button.on{border-color:var(--hot);color:var(--hot)}
 #scrub{flex:1;accent-color:var(--hot)}
 .clock{font-family:ui-monospace,Menlo,monospace;font-size:14px;color:var(--hot);
        min-width:110px}
 .legend{display:flex;flex-wrap:wrap;gap:10px 16px;font-size:12px;color:var(--dim)}
 .legend i{display:inline-block;width:11px;height:11px;border-radius:50%;
           margin-right:6px;vertical-align:-1px}
 .spark{width:100%;height:54px;display:block}
 .hint{color:var(--dim);font-size:12.5px}
 @media (max-width:900px){aside{display:none}}
</style></head><body>
<header>
 <div class="lead">
  <div class="kicker">Watch one claim travel a society</div>
  <h1>&ldquo;__CLAIM__&rdquo;</h1>
  <code class="pred">__PREDICATE__</code>
 </div>
 <span class="meta">__PACK__ &middot; Unscripted __VERSION__<br>every frame is
 recorded state, not an illustration</span>
</header>
<nav id="chapters"></nav>
<main>
 <div id="stage"><svg id="svg" viewBox="-1.5 -1.5 3 3" preserveAspectRatio="xMidYMid meet">
   <g id="places"></g><g id="pulses"></g><g id="agents"></g>
 </svg><div id="caption"></div><div id="stakes"></div></div>
 <aside>
  <section id="detail">
   <h2>Character</h2>
   <p class="hint">Click anyone on the map to see what they believe, how many
   pieces of evidence they hold, which version they have, and whether they can
   still recall being told.</p>
  </section>
  <section>
   <h2>Who knows it</h2>
   <svg class="spark" id="spark" viewBox="0 0 300 54" preserveAspectRatio="none"></svg>
   <p class="hint" id="sparkNote"></p>
  </section>
  <section>
   <h2>What just happened</h2>
   <div class="ticker" id="ticker"></div>
  </section>
 </aside>
</main>
<div id="key">
 <span><i style="background:#232833;border:1px solid #39404e"></i>has not heard it</span>
 <span><i style="background:#c99a5e"></i>believes it</span>
 <span><i style="background:#232833;border:2px solid #6fa8dc"></i>has heard it both ways</span>
 <span><i style="background:#232833;border:2px solid #d0619b"></i>a different version</span>
 <span><i style="background:#232833;border:2px dashed #4a5160"></i>cannot recall being told</span>
 <span><i style="background:#e05252"></i>lied about it</span>
</div>
<footer>
 <button id="play">Pause</button>
 <button id="speed">1&times;</button>
 <span class="clock" id="clock"></span>
 <input type="range" id="scrub" min="0" max="0" value="0" step="0.01">
 <button id="restart">Restart</button>
</footer>
<script>
const D = __DATA__;
const svg=document.getElementById("svg"), gp=document.getElementById("places"),
      ga=document.getElementById("agents"), gu=document.getElementById("pulses"),
      scrub=document.getElementById("scrub"), clock=document.getElementById("clock"),
      ticker=document.getElementById("ticker"), detail=document.getElementById("detail"),
      NS="http://www.w3.org/2000/svg";
const N=D.agents.length, F=D.frames.length;
let pos=0, playing=true, speed=1, selected=-1, pulses=[], bubbles=[], log=[], liars={};

function el(tag,attrs,parent){const n=document.createElementNS(NS,tag);
 for(const k in attrs) n.setAttribute(k,attrs[k]); (parent||svg).appendChild(n); return n;}

// --- places: drawn once
D.places.forEach(p=>{
  el("circle",{cx:p.x,cy:p.y,r:0.30,fill:"#11141a",stroke:"#232833","stroke-width":0.006},gp);
  el("circle",{cx:p.x,cy:p.y,r:0.30,fill:"none",stroke:"#2c333f","stroke-width":0.004,
               "stroke-dasharray":"0.02 0.02"},gp);
  const t=el("text",{x:p.x,y:p.y-0.335,"text-anchor":"middle",fill:"#868d99",
                     "font-size":0.052,"letter-spacing":0.006},gp);
  t.textContent=p.n.toUpperCase();
});

// --- agents: one node each, moved every frame
const nodes=D.agents.map((a,i)=>{
  const g=el("g",{class:"agent",style:"cursor:pointer"},ga);
  const ring=el("circle",{r:0.072,fill:"none","stroke-width":0.011,stroke:"transparent"},g);
  const liar=el("circle",{r:0.014,cx:0.040,cy:-0.040,fill:"transparent"},g);
  const dot=el("circle",{r:0.055,fill:"#232833",stroke:"#39404e","stroke-width":0.005},g);
  const lab=el("text",{"text-anchor":"middle",y:0.105,fill:"#9aa1ad","font-size":0.040},g);
  lab.textContent=a.n;
  g.addEventListener("click",()=>{selected=i; drawDetail();});
  return {g,dot,ring,lab,liar};
});

// Deterministic slot inside a place, so a character does not jump when a
// neighbour arrives: the slot is their index among that place's occupants.
function seat(frame,i){
  const p=frame.a[i]; if(p<0) return [0,0];
  const here=[]; for(let j=0;j<N;j++) if(frame.a[j]===p) here.push(j);
  const k=here.indexOf(i), n=Math.max(1,here.length);
  const ang=2*Math.PI*k/n - Math.PI/2;
  const rad = n===1?0:Math.min(0.195,0.055*n);
  return [D.places[p].x+rad*Math.cos(ang), D.places[p].y+rad*Math.sin(ang)];
}

// A buyer is not Bayesian and should not have to be. 0.688 is precise and
// meaningless on sight; "fairly sure" is neither, so the page leads with the
// word and keeps the number beside it for anyone who wants it.
function sureness(p,conflict){
  if(p===undefined||p<0) return "has not heard it";
  if(conflict>0.3) return "torn — has heard it both ways";
  if(p>=0.85) return "certain";
  if(p>=0.70) return "fairly sure";
  if(p>=0.56) return "leaning towards it";
  if(p>=0.45) return "unsure";
  return "doubts it";
}

function ramp(p){                       // confidence -> colour
  if(p<0) return "#232833";
  const t=Math.max(0,Math.min(1,(p-0.42)/0.46));
  const c=[[0x4a,0x39,0x2c],[0xff,0xc3,0x76]];
  const v=k=>Math.round(c[0][k]+(c[1][k]-c[0][k])*t);
  return `rgb(${v(0)},${v(1)},${v(2)})`;
}

function draw(){
  const i=Math.min(F-1,Math.floor(pos)), j=Math.min(F-1,i+1), f=pos-i;
  const A=D.frames[i], B=D.frames[j];
  const ease=f<0.5?2*f*f:1-Math.pow(-2*f+2,2)/2;
  const wrong=new Set(A.w), mem={}; A.m.forEach(m=>mem[m[0]]=m);

  nodes.forEach((n,k)=>{
    const [ax,ay]=seat(A,k), [bx,by]=seat(B,k);
    const x=ax+(bx-ax)*ease, y=ay+(by-ay)*ease;
    n.g.setAttribute("transform",`translate(${x} ${y})`);
    const p=A.p[k];
    n.dot.setAttribute("fill",ramp(p));
    n.dot.setAttribute("stroke", p<0?"#39404e":"#00000000");
    if((A.k&&A.k[k]>0.3)){ n.ring.setAttribute("stroke","#6fa8dc");
                      n.ring.setAttribute("stroke-dasharray",""); }
    else if(wrong.has(k)){ n.ring.setAttribute("stroke","#d0619b");
                      n.ring.setAttribute("stroke-dasharray",""); }
    else if(mem[k] && mem[k][1]==="lost"){ n.ring.setAttribute("stroke","#4a5160");
                      n.ring.setAttribute("stroke-dasharray","0.018 0.018"); }
    else n.ring.setAttribute("stroke","transparent");
    n.liar.setAttribute("fill", liars[k]?"#e05252":"transparent");
    n.lab.setAttribute("fill", k===selected?"#e9e7e2":(p<0?"#5c626e":"#868d99"));
    n.dot.setAttribute("r", k===selected?0.064:0.055);
  });

  gu.innerHTML="";
  const now=performance.now();
  bubbles=bubbles.filter(b=>now-b.born<2200);
  bubbles.forEach(b=>{
    const t=(now-b.born)/2200, [x,y]=b.at;
    const w=0.020*b.text.length+0.05;
    el("rect",{x:x-w/2,y:y-0.185,width:w,height:0.075,rx:0.02,
               fill:"#1b2029",stroke:b.lie?"#e05252":"#39404e","stroke-width":0.004,
               opacity:(1-t)*0.97},gu);
    const label=el("text",{x:x,y:y-0.133,"text-anchor":"middle","font-size":0.038,
                           fill:b.lie?"#ffb0b0":"#e9e7e2",opacity:1-t},gu);
    label.textContent=b.text;
  });
  pulses=pulses.filter(p=>now-p.born<900);
  pulses.forEach(p=>{
    const t=(now-p.born)/900;
    const [x1,y1]=p.from, [x2,y2]=p.to;
    const col=p.lie?"#e05252":(p.distorted?"#d0619b":"#e0a458");
    el("line",{x1,y1,x2,y2,stroke:col,"stroke-width":0.004,opacity:(1-t)*0.55},gu);
    el("circle",{cx:x1+(x2-x1)*t,cy:y1+(y2-y1)*t,r:0.020*(1-t*0.4),fill:col,
                 opacity:1-t},gu);
  });

  clock.textContent=A.c;
  scrub.value=pos;
  caption(A);
  markChapter();
  drawSpark(i);
  if(selected>=0) drawDetail();
}

function caption(f){
  const known=f.p.filter(v=>v>=0).length, wrong=f.w.length,
        lost=f.m.filter(m=>m[1]==="lost").length,
        sure=f.p.filter(v=>v>=0.75).length;
  let text;
  if(known===0) text="Nobody has heard it yet.";
  else if(known<N) text=`<b>${known} of ${N}</b> have heard it. `+
        `The rest are going about their day.`;
  else text=`<b>All ${N}</b> hold it now.`;
  if(wrong) text+=` <em>${wrong}</em> hold a different version from the rest`+
        `${Object.keys(liars).length?" &mdash; including the one who lied about it":""}.`;
  if(lost===known && known>0)
    text+=` Not one of them can still recall being told.`;
  else if(lost) text+=` ${lost} can no longer recall being told.`;
  else if(known>0) text+=` ${sure} of them are sure of it.`;
  document.getElementById("caption").innerHTML=text;
}

function fire(idx){
  const f=D.frames[idx];
  f.t.forEach(t=>{
    pulses.push({from:seat(f,t[0]),to:seat(f,t[1]),distorted:!!t[3],born:performance.now()});
    bubbles.push({at:seat(f,t[0]),text:D.short,born:performance.now()});
    log.unshift({k:t[3]?"d":"t",
      text:`<b>${D.agents[t[0]].n}</b> tells <b>${D.agents[t[1]].n}</b>` +
           (t[3]?` &mdash; and it changes on the way${t[4]?" ("+t[4]+")":""}`
                : ` &middot; hop ${t[2]}`)});
  });
  f.s.forEach(s=>log.unshift({k:"s",
    text: s[3]==="stifled"
      ? `<b>${D.agents[s[0]].n}</b> stops passing it on &mdash; <b>${D.agents[s[1]].n}</b> already knew`
      : `<b>${D.agents[s[0]].n}</b> says nothing to <b>${D.agents[s[1]].n}</b> &mdash; ${s[2]}`}));
  if(f.said) log.unshift({k:"q",text:`you: <b>${f.said.command}</b>`});
  (f.l||[]).forEach(l=>{
    if(l[0]<0) return;
    liars[l[0]]=true;
    bubbles.push({at:seat(f,l[0]),text:D.short,lie:true,born:performance.now()});
    l[2].forEach(h=>pulses.push({from:seat(f,l[0]),to:seat(f,h),
                                 lie:true,born:performance.now()}));
    log.unshift({k:"lie",
      text:`<b>${D.agents[l[0]].n}</b> lies &mdash; asserts what he does not believe, ` +
           `to ${l[2].length} listener(s), and every one of them records him as the source`});
  });
  if(log.length>9) log.length=9;
  ticker.innerHTML=log.map(l=>`<div class="${l.k==="lie"?"lie":(l.k==="d"?"d":(l.k==="q"?"q":""))}">${l.text}</div>`).join("");
}

function drawSpark(i){
  const s=document.getElementById("spark"); s.innerHTML="";
  let d="", peak=0;
  for(let k=0;k<F;k++){
    const n=D.frames[k].p.filter(v=>v>=0).length; peak=Math.max(peak,n);
    const x=300*k/(F-1), y=54-50*n/N;
    d+=(k?"L":"M")+x.toFixed(1)+" "+y.toFixed(1);
  }
  const p=document.createElementNS(NS,"path");
  p.setAttribute("d",d); p.setAttribute("fill","none");
  p.setAttribute("stroke","#e0a458"); p.setAttribute("stroke-width","1.6");
  s.appendChild(p);
  const line=document.createElementNS(NS,"line");
  const x=300*i/(F-1);
  line.setAttribute("x1",x); line.setAttribute("x2",x);
  line.setAttribute("y1",0); line.setAttribute("y2",54);
  line.setAttribute("stroke","#6fa8dc"); line.setAttribute("stroke-width","1");
  s.appendChild(line);
  const known=D.frames[i].p.filter(v=>v>=0).length;
  const lost=D.frames[i].m.filter(m=>m[1]==="lost").length;
  document.getElementById("sparkNote").textContent =
    `${known} of ${N} hold it. ${lost === 0 ? "All of them can still recall being told."
      : lost === known ? "None of them can recall being told any more."
      : lost + " can no longer recall being told."}`;
}

function drawDetail(){
  const i=Math.min(F-1,Math.floor(pos)), f=D.frames[i], k=selected;
  if(k<0) return;
  const a=D.agents[k], p=f.p[k], hist=(D.history[String(k)]||[]);
  const learned=hist.length?hist[0]:null;
  const mem=f.m.find(m=>m[0]===k);
  const conflict=(f.k&&f.k[k])||0;
  const rows=[
    ["How sure is he?", p<0?"has not heard it"
        :`${sureness(p,conflict)} <span class="num">${p.toFixed(2)}</span>`],
    ["How often was he told?", (f.e[k]||0) + ((f.e[k]||0)===1?" time":" times")],
    ["Which version?", f.w.includes(k)?"one that differs from the rest"
                                      :"the one most of them hold"],
    ["Can he recall being told?", mem
        ? (mem[1]==="lost" ? "no &mdash; the occasion is gone, the belief is not"
                           : (mem[1]==="vivid" ? "clearly" : "only faintly"))
        : "there is no episode of it"],
    ["Since when?", learned?learned.clock:"&mdash;"],
  ];
  detail.innerHTML =
    `<h2>Character</h2><p class="who">${a.n}</p><p class="role">${a.r}</p>` +
    rows.map(r=>`<div class="row"><b>${r[0]}</b><span>${r[1]}</span></div>`).join("") +
    (learned&&learned.origins.length
      ? `<h2 style="margin-top:16px">Where it came from</h2>` +
        `<p class="hint">The one event everything he holds rests on. Hearing it ` +
        `again from anyone who also traces back to this does not make him surer.</p>` +
        learned.origins.map(o=>`<div class="chain">${o}</div>`).join("")
      : "");
}

// --- transport
let last=performance.now();
function tick(now){
  const dt=(now-last)/1000; last=now;
  if(playing){
    const before=Math.floor(pos);
    pos=Math.min(F-1,pos+dt*3.4*speed);
    for(let k=before+1;k<=Math.floor(pos);k++) fire(k);
    if(pos>=F-1){ playing=false; document.getElementById("play").textContent="Replay"; }
  }
  draw();
  requestAnimationFrame(tick);
}
scrub.max=F-1;
document.getElementById("play").onclick=e=>{
  if(pos>=F-1){ pos=0; log=[]; }
  playing=!playing; e.target.textContent=playing?"Pause":"Play";
};
document.getElementById("speed").onclick=e=>{
  speed=speed===1?2:(speed===2?4:1); e.target.textContent=speed+"×";
  e.target.className=speed===1?"":"on";
};
document.getElementById("restart").onclick=()=>{ pos=0; log=[]; pulses=[];
  playing=true; document.getElementById("play").textContent="Pause"; };
scrub.oninput=e=>{ pos=parseFloat(e.target.value); pulses=[]; bubbles=[]; };

// --- chapters: the moments worth jumping to, found in the recording itself
const chapterBar=document.getElementById("chapters");
(D.chapters||[]).forEach((c,i)=>{
  const b=document.createElement("button");
  b.textContent=c.title;
  b.title=c.note||"";
  b.onclick=()=>{ pos=c.frame; pulses=[]; bubbles=[]; log=[];
    for(let k=Math.max(0,c.frame-4);k<=c.frame;k++) fire(k);
    playing=true; document.getElementById("play").textContent="Pause"; };
  chapterBar.appendChild(b);
});
function markChapter(){
  const buttons=chapterBar.children;
  let active=-1;
  (D.chapters||[]).forEach((c,i)=>{ if(pos>=c.frame) active=i; });
  for(let i=0;i<buttons.length;i++) buttons[i].className=(i===active?"now":"");
  const band=document.getElementById("stakes");
  const chapter=(D.chapters||[])[active];
  band.textContent=(chapter&&chapter.stakes)?chapter.stakes:"";
}
// Deep link to a moment: #frame=120 opens there, &paused holds it still. The
// interesting thirty seconds of a five-day run are hard to find by scrubbing,
// and a link that lands on them is the difference between "have a look" and
// "look at this".
(function(){
  const h=new URLSearchParams(location.hash.replace(/^#/,""));
  if(h.has("frame")){
    pos=Math.max(0,Math.min(F-1,parseFloat(h.get("frame"))||0));
    for(let k=Math.max(0,Math.floor(pos)-6);k<=Math.floor(pos);k++) fire(k);
  }
  if(h.has("who")){                       // link straight to one person's state
    const wanted=h.get("who").toLowerCase();
    const found=D.agents.findIndex(a=>a.n.toLowerCase().includes(wanted));
    if(found>=0) selected=found;
  }
  if(h.has("paused")){ playing=false; document.getElementById("play").textContent="Play"; }
})();
fire(0); draw(); requestAnimationFrame(tick);
</script>
__IMPRINT__
</body></html>
"""
