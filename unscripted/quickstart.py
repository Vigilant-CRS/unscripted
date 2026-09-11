"""What the first ten minutes actually look like, captured from a live service.

A studio's third question, after what it is and whether it works, is how long
until they can see it in their own project. That question is usually answered
with a code sample somebody typed into a README, which drifts, and which the
reader has no way to check.

So this starts the service, makes the calls, and embeds what came back. Every
response on the page is a real response; if a field is renamed the page changes
with it, and the contract test fails on the same day.

The honest part is the timing. Installing and getting a spoken line back is a few
minutes. Wiring the runtime into a game so that it is worth having is an
afternoon at least, because the interesting work is deciding which of your
existing events become world events -- and the page says so rather than implying
that ten minutes buys a finished integration.
"""
from __future__ import annotations

import json
import threading

from .contracts import RuntimeConfig, imprint_html
from .service import ServiceOptions, create_server

#: Trimmed on purpose: an avatar packet carries 52 ARKit blendshapes, and a page
#: that prints all of them teaches nothing that the first three do not.
BLENDSHAPE_SAMPLE = 3

def steps(pack: str, line: str) -> tuple:
    """The three commands, written for the pack the page was generated against.

    The character and topic are looked up from the running world rather than
    written here. Naming them in the engine would be a world's vocabulary living
    in the SDK, which is the one thing a structural test greps for -- and the page
    then only ever worked for one pack.
    """
    return (
        ("Install it", "pip install -e unscripted",
         "Python 3.10 or newer. No third-party packages: the install pulls "
         "nothing, which is why it works behind a studio firewall and in a locked "
         "build environment."),
        ("Start the service", f"unscripted serve --world-pack {pack} --auth-token dev",
         "Binding off loopback without a token is refused rather than warned "
         "about. For a shipping build, add --no-debug-endpoints: /state/* exposes "
         "every character's private beliefs, which is what makes the debug HUD "
         "useful and what a game client must not have."),
        ("Say something to a character",
         'curl -s localhost:8080/v2/avatar/turn -H "Authorization: Bearer dev" '
         f'-d \'{{"text": "{line}"}}\'',
         "One call. The response below is the real one, captured while this page "
         "was generated."),
    )


def _call(port: int, method: str, path: str, body=None):
    import http.client
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    connection.request(method, path,
                       body=json.dumps(body) if body is not None else None,
                       headers={"Content-Type": "application/json",
                                "Authorization": "Bearer dev"})
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, json.loads(payload or b"{}")


def _trim(value):
    """Shorten what is long without hiding that it was shortened."""
    if isinstance(value, dict):
        if len(value) > 8 and all(isinstance(v, (int, float)) for v in value.values()):
            kept = dict(list(value.items())[:BLENDSHAPE_SAMPLE])
            kept[f"... {len(value) - BLENDSHAPE_SAMPLE} more"] = "..."
            return kept
        return {key: _trim(item) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > 4:
            return [_trim(item) for item in value[:3]] + [f"... {len(value) - 3} more"]
        return [_trim(item) for item in value]
    return value


def capture(pack: str) -> dict:
    """Run the first calls against a real service and keep what came back."""
    server = create_server(
        RuntimeConfig(world_pack_path=pack, storage_path=":memory:",
                      action_bridge=True),
        host="127.0.0.1", port=0, options=ServiceOptions(auth_token="dev"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        calls = []

        # Who is standing here, and what can be asked about? Looked up rather
        # than written down, so this page works for any pack and the engine keeps
        # containing no world's vocabulary.
        _, scene = _call(port, "GET", "/state/scene")
        who = next((person["name"] for person in scene.get("npcs") or []), None)
        # Topics are not on the wire, and adding them would grow a version-1
        # response -- which a test forbids, because a strict parser in a shipped
        # game breaks on a new field just as surely as on a renamed one. Read from
        # the pack instead.
        from .world import load_world_pack
        subject = next(iter(sorted(getattr(load_world_pack(pack), "topics", {}) or {})),
                       None)
        line = (f"ask {who} about {subject}" if who and subject
                else (f"ask {who} about it" if who else "look"))

        status, capabilities = _call(port, "GET", "/capabilities")
        calls.append({
            "title": "Ask what this build can do, before anything else",
            "request": "GET /capabilities",
            "status": status, "body": _trim(capabilities),
            "note": "A capability that is false means the feature is absent, not "
                    "that it produced nothing this turn. Refuse to start if the "
                    "runtime does not list a contract version you understand."})

        status, turn = _call(port, "POST", "/v2/avatar/turn", {"text": line})
        calls.append({
            "title": "Say something to a character",
            "request": f'POST /v2/avatar/turn  {{"text": "{line}"}}',
            "status": status, "body": _trim(turn),
            "note": "`text` is the line. `honesty` is the runtime's own record of "
                    "whether it matched what the speaker believes — never infer "
                    "that from the prose. `asserted` is what the line committed "
                    "the character to, and who was close enough to hear it. The "
                    "face and prosody blocks drive an avatar and a voice."})

        status, knowledge = _call(port, "GET", "/v2/state/knowledge")
        calls.append({
            "title": "Ask who knows what, and on whose word",
            "request": "GET /v2/state/knowledge",
            "status": status, "body": _trim(knowledge),
            "note": "The debug HUD lives here: stories grouped by incident, who "
                    "is a bridge between circles, which claims are contested. Turn "
                    "it off for a shipping client."})

        status, pending = _call(port, "GET", "/v2/actions/pending")
        calls.append({
            "title": "Ask what the runtime wants your engine to do",
            "request": "GET /v2/actions/pending",
            "status": status, "body": _trim(pending),
            "note": "Empty here because no world time has passed yet. When a "
                    "routine moves somebody, an intent appears and the character "
                    "does NOT move until you report the result — that is how the "
                    "simulation and the screen are kept from disagreeing."})

        status, refused = _call(port, "POST", "/advance", {"minutes": -30})
        calls.append({
            "title": "And what a mistake looks like",
            "request": 'POST /advance  {"minutes": -30}',
            "status": status, "body": _trim(refused),
            "note": "World time is monotonic; rewinding it would corrupt every "
                    "memory activation. Client mistakes come back as typed 4xx "
                    "with a code you can branch on, never as a 500 or a silently "
                    "broken world."})
        return {"calls": calls, "pack": pack, "line": line}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ------------------------------------------------------------------- page ----

def render(captured: dict, *, version: str) -> str:
    import html as _html

    step_html = "".join(
        f'<li><h3>{_html.escape(title)}</h3>'
        f'<pre class="sh">{_html.escape(command)}</pre>'
        f'<p>{_html.escape(note)}</p></li>'
        for title, command, note in steps(captured["pack"], captured["line"]))

    calls = "".join(
        f'<section><h2>{_html.escape(call["title"])}</h2>'
        f'<div class="req"><code>{_html.escape(call["request"])}</code>'
        f'<span class="status s{call["status"] // 100}">{call["status"]}</span></div>'
        f'<pre class="json">{_html.escape(json.dumps(call["body"], indent=2))}</pre>'
        f'<p class="note">{call["note"]}</p></section>'
        for call in captured["calls"])

    return _PAGE.replace("__STEPS__", step_html).replace("__CALLS__", calls) \
                .replace("__VERSION__", version) \
                .replace("__IMPRINT__", imprint_html()) \
                .replace("__PACK__", _html.escape(captured["pack"].split("/")[-1]))


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unscripted — the first ten minutes</title>
<style>
 :root{color-scheme:dark;--bg:#0b0d11;--fg:#e9e7e2;--dim:#868d99;--line:#232833;
       --hot:#e0a458;--good:#7cbf6a;--bad:#d0619b}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:15.5px/1.65 ui-sans-serif,
      -apple-system,"Segoe UI",Roboto,sans-serif}
 header{padding:80px 6vw 34px;max-width:820px}
 h1{font-size:clamp(28px,4.4vw,46px);line-height:1.1;margin:0 0 16px;
    letter-spacing:-.02em}
 .lede{font-size:clamp(16px,1.8vw,19px);color:var(--dim);margin:0}
 ol{max-width:900px;margin:0;padding:0 6vw 20px;list-style:none;counter-reset:s}
 ol li{counter-increment:s;padding:22px 0 22px 46px;position:relative;
       border-bottom:1px solid var(--line)}
 ol li::before{content:counter(s);position:absolute;left:0;top:22px;width:28px;
               height:28px;border:1px solid var(--line);border-radius:50%;
               text-align:center;line-height:27px;font-size:13px;color:var(--hot)}
 h3{font-size:17px;margin:0 0 10px;letter-spacing:-.01em}
 ol li p{margin:10px 0 0;color:var(--dim);font-size:14.5px}
 pre{margin:0;padding:13px 16px;background:#11141a;border:1px solid var(--line);
     border-radius:7px;overflow-x:auto;font:13px/1.6 ui-monospace,Menlo,monospace}
 pre.sh{color:var(--hot)}
 pre.json{color:#c8ccd4;max-height:340px;overflow-y:auto}
 section{padding:34px 6vw;border-top:1px solid var(--line);max-width:1000px}
 section h2{font-size:20px;margin:0 0 14px;letter-spacing:-.01em}
 .req{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}
 .req code{font:13px ui-monospace,Menlo,monospace;color:var(--dim)}
 .status{font:12px ui-monospace,Menlo,monospace;padding:2px 8px;border-radius:4px;
         border:1px solid var(--line)}
 .s2{color:var(--good)} .s4{color:var(--bad)}
 .note{color:var(--dim);font-size:14.5px;max-width:72ch;margin:14px 0 0}
 footer{padding:44px 6vw 100px;color:var(--dim);max-width:820px;font-size:14.5px}
 footer b{color:var(--fg);font-weight:500}
 code{font-family:ui-monospace,Menlo,monospace}
</style></head><body>
<header>
 <h1>The first ten minutes</h1>
 <p class="lede">Three commands and one HTTP call gets a character talking. Every
 response below was captured from a live service while this page was generated,
 against <code>__PACK__</code>.</p>
</header>
<ol>__STEPS__</ol>
__CALLS__
<footer>
 <p><b>What ten minutes actually buys:</b> a character who answers, with the
 runtime's own record of whether the answer was honest, what it committed them to,
 and who overheard. That is enough to see whether this is worth your time.</p>
 <p><b>What it does not buy:</b> an integration. The real work is deciding which
 of your existing gameplay events become world events &mdash; a door forced, a
 body found, a payment made &mdash; because that is what gives characters
 something to know. Budget an afternoon for a first pass and expect to argue
 about which events matter, not about the API.</p>
 <p>Generated by <code>unscripted pages</code> at version __VERSION__. If a field here is
 ever renamed, this page changes with it and the contract test fails the same
 day.</p>
__IMPRINT__
</footer>
</body></html>
"""
