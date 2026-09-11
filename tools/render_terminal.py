"""Render real command output as the terminal screenshot the README shows.

WHY THIS EXISTS. `docs/images/tests.png` said 145 tests while the suite ran 154.
Nobody wrote a wrong number: the image was made by hand once, the suite grew,
and a picture cannot be checked by a test. That is the same failure this project
keeps having in prose, and the fix is the same one -- generate it from the thing
it describes, so it cannot drift without the command drifting too.

So this RUNS the command and renders what actually came back. There is no way to
put a number in the image that the command did not produce.

    python3 tools/render_terminal.py docs/images/tests.png \\
        --title "unscripted -- the regression suite" \\
        -- python3 tests/test_scenarios.py

Long output is elided in the middle, keeping the head and the tail, with a line
saying how much was dropped -- the same shape the existing image had, because a
screenshot of four hundred passing lines tells a reader less than eight of them
and an honest count.

Needs a headless Chrome, which is the same dependency `unscripted film` already has,
and nothing else.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

#: Roughly the palette of the terminal the original screenshot was taken in.
#: Not a theme system -- one look, so every image in the documentation matches.
STYLE = """
  :root { color-scheme: dark; }
  body { margin: 0; background: #11151c; font-family: "DejaVu Sans Mono",
         "Liberation Mono", Menlo, Consolas, monospace; }
  .frame { width: 1198px; }
  .bar { height: 34px; background: #1b2029; display: flex; align-items: center;
         padding: 0 14px; gap: 8px; }
  .dot { width: 11px; height: 11px; border-radius: 50%; }
  .title { color: #7c8797; font-size: 12.5px; margin-left: 8px; }
  pre { margin: 0; padding: 22px 22px 26px; color: #c8d0da; font-size: 14px;
        line-height: 1.72; white-space: pre; }
  .cmd  { color: #dfe6ef; }
  .ok   { color: #56d364; }
  .fail { color: #f0654f; }
  .dim  { color: #6b7684; }
  .done { color: #56d364; }
"""


def elide(lines: list, head: int, tail: int) -> list:
    """Keep the first `head` and last `tail` lines, saying what went."""
    if len(lines) <= head + tail:
        return lines
    dropped = len(lines) - head - tail
    return (lines[:head]
            + ["", "  ... %d more lines" % dropped, ""]
            + lines[-tail:])


def classify(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("ok "):
        return "ok"
    if stripped.startswith(("FAIL", "ERROR", "Traceback")):
        return "fail"
    if stripped.startswith("..."):
        return "dim"
    if stripped.startswith("All tests passed"):
        return "done"
    return ""


def truncate(line: str, width: int) -> str:
    """Cut an over-long line with an ellipsis, as the original image did."""
    return line if len(line) <= width else line[:width - 2].rstrip() + " …"


def build_html(command: list, output: str, title: str, head: int, tail: int,
               width: int) -> str:
    lines = [truncate(line, width) for line in output.splitlines() if line.strip()]
    body = ['<span class="cmd">$ %s</span>' % html.escape(" ".join(command)), ""]
    for line in elide(lines, head, tail):
        kind = classify(line)
        text = html.escape(line)
        body.append('<span class="%s">%s</span>' % (kind, text) if kind else text)
    return """<!doctype html><meta charset="utf-8"><style>%s</style>
<div class="frame">
  <div class="bar">
    <span class="dot" style="background:#ff5f57"></span>
    <span class="dot" style="background:#febc2e"></span>
    <span class="dot" style="background:#28c840"></span>
    <span class="title">%s</span>
  </div>
  <pre>%s</pre>
</div>""" % (STYLE, html.escape(title), "\n".join(body))


def browser() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no headless Chrome found; it is the same one `unscripted film` needs")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a command and render its real output as a PNG.")
    parser.add_argument("out", help="PNG to write")
    parser.add_argument("--title", default="unscripted")
    parser.add_argument("--head", type=int, default=8,
                        help="lines kept from the start (default 8)")
    parser.add_argument("--tail", type=int, default=1,
                        help="lines kept from the end (default 1)")
    parser.add_argument("--width", type=int, default=96,
                        help="characters before a line is elided (default 96)")
    parser.add_argument("--timeout", type=int, default=3600)
    # The command is split off by hand rather than with `argparse.REMAINDER`,
    # which swallows this script's own options the moment one follows the
    # positional argument -- so `--title` was being passed to the shell.
    argv = sys.argv[1:]
    command = []
    if "--" in argv:
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    args = parser.parse_args(argv)
    if not command:
        parser.error("give the command after --")

    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=args.timeout)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        # Render it anyway -- a screenshot of a failing suite is a true
        # screenshot -- but say so, loudly, because it is almost never wanted.
        print("WARNING: the command exited %d. Rendering the failure."
              % result.returncode, file=sys.stderr)

    page = build_html(command, output, args.title, args.head, args.tail, args.width)
    with tempfile.TemporaryDirectory() as work:
        source = os.path.join(work, "page.html")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write(page)
        subprocess.run([browser(), "--headless", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--screenshot=" + os.path.abspath(args.out),
                        "--window-size=1198,%d" % height_for(page),
                        "--default-background-color=00000000",
                        "file://" + source],
                       check=True, capture_output=True,
                       env={**os.environ, "HOME": work})
    print("%s  <- %s" % (args.out, " ".join(command)))
    return 0 if result.returncode == 0 else 1


def height_for(page: str) -> int:
    """Tall enough for the rendered lines, with no empty band underneath."""
    rows = page.count("\n", page.index("<pre>"), page.index("</pre>")) + 1
    return 34 + 48 + int(rows * 24.1)


if __name__ == "__main__":
    sys.exit(main())
