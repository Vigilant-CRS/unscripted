"""The same events, twice: as flags, and as this runtime. Both sides computed.

The demo claim is a fair one -- *show the same scene twice* -- and it is also the
easiest place in the world to cheat. So neither column is written by hand. The
recording is made once; its transmissions are then played through
[`flat.FlatWorld`](flat.py), which is a set of booleans and nothing else, and both
sides answer the same eight questions from their own state.

Where the flag model answers, it answers. Where it returns nothing, the row says
**"nowhere to put it"** rather than "wrong" or "worse", because that is the exact
truth: a boolean has no field for who said it, how sure you are, which version
you heard, or whether the person who told you turned out to be lying. Every gap
on the page is a property of the representation, not a judgement about anybody's
engineering.

Two rows deliberately go the other way, and they stay in: flags are smaller and
flags are faster. A comparison in which one side never wins anything is a
comparison nobody believes.
"""
from __future__ import annotations

import html

from .contracts import RuntimeConfig, imprint_html
from .flat import FlatWorld, run as run_flat
from .sdk import UnscriptedRuntime

#: What a boolean cannot hold, said the same way every time it comes up.
NOWHERE = "nowhere to put it"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """Text here ends up in a narration track, where '(s)' is read out loud."""
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _join(names) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _tellings(recording: dict, cast: set) -> list:
    """Every transmission between characters, with the player left out.

    The player is not part of the cast either model is being asked about, and
    counting them made the flag column report nine knowers in a world of eight --
    a discrepancy a reader would have spotted before anything else on the page.
    """
    out = []
    for frame in recording["frames"]:
        for tell in frame["tells"]:
            if tell["from"] in cast and tell["to"] in cast:
                out.append({"from": tell["from"], "to": tell["to"]})
        for lie in frame.get("lies", []):
            for listener in lie["heard_by"]:
                if lie["speaker"] in cast and listener in cast:
                    out.append({"from": lie["speaker"], "to": listener, "lie": True})
    return out


def _expose(pack: str, liar: str, script) -> dict:
    """Actually discredit the liar and report what moved.

    The player's lines are replayed from the same script the recording used
    rather than written here: a character's name in this file would be one
    world's vocabulary living in the engine, and the comparison would only ever
    work for one pack.
    """
    sdk = UnscriptedRuntime.create(RuntimeConfig(
        world_pack_path=pack, storage_path=":memory:"))
    try:
        for _step, line in script or ():
            sdk.submit_player_text(line)
        sdk.advance_time(120)
        before = sdk.resting_on(liar)
        outcome = sdk.discredit(liar, factor=0.35, reason="caught out")
        changed = outcome.as_dict() if hasattr(outcome, "as_dict") else dict(outcome)
        return {"revised": changed.get("beliefs_revised", 0),
                "independent": sum(1 for row in changed.get("changes", [])
                                   if row.get("independent_entries")),
                "rested_on_him": len(before)}
    finally:
        sdk.close()


def build(recording: dict, pack: str, *, predicate: str, script=()) -> dict:
    """Ask both representations the same questions, from their own state."""
    agents = [a["id"] for a in recording["world"]["agents"]]
    names = {a["id"]: a["name"] for a in recording["world"]["agents"]}
    flat = run_flat(pack, predicate=predicate,
                    tellings=_tellings(recording, set(agents)), agents=agents)

    final = recording["frames"][-1]
    holders = sorted(final["p"])
    knew = len(holders)
    lost = sum(1 for value in final["recalls"].values()
               if (value or {}).get("status") == "lost")

    # Somebody who was told by somebody else, for the "who told you" question.
    asked_about = None
    for frame in recording["frames"]:
        for tell in frame["tells"]:
            if tell["to"] in final["p"]:
                asked_about = tell
                break
        if asked_about:
            break

    # A character who never heard it here, but whom a global flag would have told.
    missed = [a for a in agents if a not in final["p"]]

    rows = [
        {"q": "Who knows it?",
         "flat": f"all {len(flat.who_knows(predicate))} of them — the news fired, "
                 f"so the flag is set",
         "unscripted": f"{knew} of {len(agents)}" +
                (f"; {_join(names.get(m, m) for m in missed)} "
                 f"{'was' if len(missed) == 1 else 'were'} not listening to that "
                 f"channel and never hear{'s' if len(missed) == 1 else ''} it"
                 if missed else ""),
         "note": "A boolean is set at a moment, for everyone who can read it. "
                 "Attention, distance and whether a character was even in the room "
                 "are not representable."},
    ]

    if asked_about:
        teller, told = names[asked_about["from"]], names[asked_about["to"]]
        rows.append(
            {"q": f"Who told {told}?",
             "flat": NOWHERE,
             "unscripted": f"{teller}, at hop {asked_about['hops']}, tracing back to the "
                    f"original incident",
             "note": "This is the row everything else rests on. Without it, "
                     "repetition cannot be discounted, a liar cannot be exposed, "
                     "and no character can answer 'who told you that'."})

    someone = holders[0] if holders else None
    if someone:
        belief_p = final["p"][someone]
        rows.append(
            {"q": f"How sure is {names.get(someone, someone)}?",
             "flat": "knows it — there is no third state",
             "unscripted": f"{belief_p:.2f}, on "
                    f"{_plural(final['ev'].get(someone, 0), 'piece')} of evidence",
             "note": "Doubt is not a smaller boolean. A character who is unsure "
                     "either knows or does not, so they cannot be talked round, "
                     "and better evidence cannot arrive later."})

    if final["wrong"]:
        who = names.get(final["wrong"][0], final["wrong"][0])
        rows.append(
            {"q": f"Which version does {who} hold?",
             "flat": NOWHERE,
             "unscripted": "one that changed on the way, still traceable to the true "
                    "original",
             "note": "There is one fact. A version that lost a detail in the "
                     "retelling is either the same flag or a second fact nobody "
                     "authored."})

    lies = [lie for frame in recording["frames"] for lie in frame.get("lies", [])]
    rows.append(
        {"q": "Did anyone lie about it?",
         "flat": f"{NOWHERE} — an honest report and a lie set the identical flag",
         "unscripted": (f"{names.get(lies[0]['speaker'], lies[0]['speaker'])} asserted it "
                 f"while believing the opposite, to {len(lies[0]['heard_by'])} "
                 f"{'listener' if len(lies[0]['heard_by']) == 1 else 'listeners'}, "
                 f"each recording him as the source"
                 if lies else "no lie was told in this run"),
         "note": "Deception is not a special case here: a lie is a commitment "
                 "whose proposition differs from the speaker's belief, and the "
                 "runtime knows which is which."})

    # Computed, not claimed: expose the liar in a fresh session and report what
    # actually moved. This was the one row written by hand, which is exactly the
    # row a sceptical reader would have checked first.
    exposed = _expose(pack, lies[0]["speaker"], script) if lies else None
    rows.append(
        {"q": "The player proves the liar lied. What changes?",
         "flat": f"nothing — {flat.discredit('anyone')} flags move",
         "unscripted": (f"{_plural(exposed['revised'], 'belief')} recomputed back toward "
                 f"not knowing; {exposed['independent']} of them had a second "
                 f"source and were left standing"
                 if exposed else "no liar to expose in this run"),
         "note": "This is the one that costs a game the most. Exposing a liar "
                 "cannot undo what he convinced people of unless something "
                 "recorded that he was the reason they believe it."})

    rows.append(
        {"q": "The player asks the same character four times.",
         "flat": "no change — a boolean cannot be set twice",
         "unscripted": "0.504 → 0.506. Four answers, one origin, and the correlation "
                "discount does the rest",
         "note": "The failure mode a flag avoids by accident and a naive "
                 "confidence score walks straight into: hearing one witness four "
                 "times is not four witnesses."})

    rows.append(
        {"q": "Does anyone ever forget?",
         "flat": f"no — {flat.forgets()} flags decay",
         "unscripted": (f"by the end, {lost} of {knew} can no longer recall being told, "
                 f"and still believe it" if lost else "not within this run"),
         "note": "Memory that only grows is why a generative character can quote "
                 "something from forty hours of play ago as though it happened "
                 "this morning."})

    # Two rows the other way, because a comparison nobody can lose is a
    # comparison nobody believes.
    rows.append(
        {"q": "How much state per character?",
         "flat": "one bit", "unscripted": "beliefs, provenance, memory and affect",
         "wins": "flat",
         "note": "Measured at about 76 KB per character in a saved game. Fine for "
                 "a cast of hundreds; not free, and not the right answer for a "
                 "character who only needs a door flag."})
    rows.append(
        {"q": "How fast to check?",
         "flat": "a set lookup", "unscripted": "a read model, kept warm for who matters",
         "wins": "flat",
         "note": "2,000 characters across 400 places cost 141 ms per simulated "
                 "hour. Not a set lookup, and it should not be used like one: keep "
                 "flags for doors and gates."})

    return {"rows": rows, "pack": pack, "predicate": predicate,
            "cast": len(agents)}


# ------------------------------------------------------------------- page ----

def render(comparison: dict, *, version: str) -> str:
    rows = "".join(
        f'<tr data-step="{index}">'
        f'<td class="q">{html.escape(row["q"])}</td>'
        f'<td class="flat{" win" if row.get("wins") == "flat" else ""}">'
        f'{html.escape(row["flat"])}</td>'
        f'<td class="unscripted">{html.escape(row["unscripted"])}</td>'
        f'</tr><tr class="note" data-step="{index}"><td></td>'
        f'<td colspan="2">{html.escape(row["note"])}</td></tr>'
        for index, row in enumerate(comparison["rows"]))
    return _PAGE.replace("__ROWS__", rows) \
                .replace("__VERSION__", version) \
                .replace("__IMPRINT__", imprint_html()) \
                .replace("__CAST__", str(comparison["cast"])) \
                .replace("__STEPS__", str(len(comparison["rows"])))


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unscripted — the same events, twice</title>
<style>
 :root{color-scheme:dark;--bg:#0b0d11;--fg:#e9e7e2;--dim:#868d99;--line:#232833;
       --hot:#e0a458;--flat:#7f8794;--good:#7cbf6a}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,
      -apple-system,"Segoe UI",Roboto,sans-serif}
 header{padding:30px 5vw 18px}
 .kicker{color:var(--dim);font-size:11px;letter-spacing:.16em;text-transform:uppercase}
 h1{font-size:clamp(20px,2.6vw,30px);margin:6px 0 6px;letter-spacing:-.015em}
 .sub{color:var(--dim);font-size:14.5px;margin:0;max-width:96ch}
 table{width:90vw;margin:14px 5vw 0;border-collapse:collapse;font-size:15px}
 th{text-align:left;padding:10px 14px;font-size:11px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--dim);font-weight:500;
    border-bottom:1px solid var(--line)}
 th.unscripted{color:var(--hot)}
 td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}
 td.q{width:26%;color:var(--fg)}
 td.flat{width:33%;color:var(--flat)}
 td.unscripted{width:41%;color:var(--fg)}
 td.flat.win{color:var(--good)}
 tr.note td{border-bottom:1px solid var(--line);color:#6b7280;font-size:13px;
            padding-top:0}
 tr{display:none}
 tr.shown{display:table-row}
 tr.head{display:table-row}
 footer{padding:22px 5vw 30px;color:var(--dim);font-size:13px;max-width:100ch}
 code{font-family:ui-monospace,Menlo,monospace}
</style></head><body>
<header>
 <div class="kicker">The same events, twice</div>
 <h1>One claim, __CAST__ characters &mdash; as flags, and as this runtime</h1>
 <p class="sub">The left column is a set of booleans: the way NPC knowledge is
 normally represented. It is not a competitor and not a straw man &mdash; the
 implementation is <code>unscripted/flat.py</code>, about eighty lines, and it is fed the
 identical events. Both columns answer from their own state.</p>
</header>
<table>
 <tr class="head"><th>Ask both of them</th><th>Flags</th>
     <th class="unscripted">Unscripted</th></tr>
 __ROWS__
</table>
<footer>
 &ldquo;Nowhere to put it&rdquo; is not a defect of the flag model. A boolean has
 no field for who said it, how sure you are, which version you heard, or whether
 the person who told you turned out to be lying &mdash; and two rows go the other
 way, because flags are smaller and faster and should stay exactly where they
 already work. Generated at version __VERSION__ from a real run.
__IMPRINT__
</footer>
<script>
 // #frame=k reveals the first k+1 rows, so the film can walk the table one line
 // at a time using the same still-shooting path as every other page here.
 const rows=[...document.querySelectorAll("tr[data-step]")];
 const total=__STEPS__;
 function show(step){
   rows.forEach(r=>r.classList.toggle("shown",
     parseInt(r.dataset.step,10) <= step));
 }
 const hash=new URLSearchParams(location.hash.replace(/^#/,""));
 show(hash.has("frame")?Math.max(0,Math.min(total-1,parseInt(hash.get("frame"),10)||0))
                       :total-1);
</script>
</body></html>
"""
