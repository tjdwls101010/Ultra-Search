"""Running JavaScript in the user's browser and reading back NDJSON.

The one thing worth knowing: a snippet that runs past 120 seconds is killed, and the CLI
reports that as "Could not connect to Aside", the words it uses for a connection that
failed. The daemon is fine. Taking that message at face value sends a caller to restart an
app that was never broken, so it is translated here into what actually happened -- by the
cause ASIDE_DEBUG=1 makes the CLI add, the only thing that tells the two apart.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ultra_search.aside.process import aside_bin
from ultra_search.outcome import AsideUnavailable

#: The page snippets. Real .js files rather than strings so they stay readable and editable;
#: each receives its arguments through a prepended `ARGS` constant -- the code goes over argv,
#: where interpolating values into the source would be a quoting bug waiting to happen.
SNIPPETS = Path(__file__).resolve().parent / "snippets"

#: The daemon kills a snippet here. Everything a snippet does is budgeted below this.
REPL_HARD_LIMIT = 120.0
#: The cause the CLI gives the kill under ASIDE_DEBUG=1. "fetch failed" is not one: it comes before a refused or blocked
#: connection's cause too.
_KILLED = "other side closed"


class ReplTimeout(Exception):
    """The snippet was killed at the 120s limit. ``lines`` is what reached stdout before that, which the CLI has been
    seen to drop entirely: a snippet's defence is finishing inside its own budget."""

    def __init__(self, lines: list[dict]) -> None:
        super().__init__("repl snippet exceeded the 120s limit")
        self.lines = lines


def run_code(code: str, *, timeout: float = REPL_HARD_LIMIT + 15) -> list[dict]:
    """Run code in the REPL and return the JSON objects it printed, in order."""
    try:
        proc = subprocess.run(
            [aside_bin(), "repl", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "ASIDE_DEBUG": "1"},
        )
    except subprocess.TimeoutExpired as e:
        raise ReplTimeout(parse_ndjson(_text(e.stdout))) from e
    except OSError as e:
        raise AsideUnavailable(f"could not run `aside repl`: {e}") from e

    lines = parse_ndjson(proc.stdout)
    if proc.returncode != 0:
        # stderr alone: stdout is the page's output, and a page can say anything.
        if _KILLED in (proc.stderr or ""):
            raise ReplTimeout(lines)
        raise AsideUnavailable(
            f"`aside repl` failed: {_said(proc.stderr or proc.stdout or '')}",
            fix="Check the Aside app is running, then re-run `doctor`.",
        )
    return lines


def _said(text: str) -> str:
    """What the CLI said, through the cause on its first `Details:` line; the stack it prints after that repeats both."""
    lines = text.strip().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Details:"):
            return "\n".join(lines[:i + 1])
    return text.strip()[:400]


def run_snippet(name: str, args: dict, *, timeout: float = REPL_HARD_LIMIT + 15) -> list[dict]:
    """Run one of this package's snippets with ``args`` as its `ARGS`."""
    return run_code(f"const ARGS = {json.dumps(args, ensure_ascii=False)};\n{_load_snippet(name)}", timeout=timeout)


def _load_snippet(name: str) -> str:
    path = SNIPPETS / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise AsideUnavailable(f"missing repl snippet {name}", fix=f"Reinstall the skill; expected {path}") from e


#: How long the round trip that starts a closed Aside may take: past the CLI's own waits (60 s for the app to answer,
#: 45 s more for its browser to take work), so a start that fails is reported in Aside's words, not cut off here first.
START_LIMIT = 120.0


def repl_probe(timeout: float = 60) -> tuple[bool, str]:
    """Run a snippet whose output is known and check that exact output came back.

    A round trip, not just a health endpoint: the daemon answering HTTP and the daemon
    running a snippet are different things, and only the second one matters. Any output is
    not enough either: a sandbox that refuses the snippet still prints its refusal.
    """
    worked, detail, _ = round_trip(timeout)
    return worked, detail


def round_trip(timeout: float) -> tuple[bool, str, str]:
    """`repl_probe`, with what the CLI said on stderr besides, whichever way it went."""
    code = 'console.log(JSON.stringify({ok:true}));'
    try:
        proc = subprocess.run([aside_bin(), "repl", code], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # Ours, not Aside's: kept apart from anything the CLI says, which would say why.
        raise AsideUnavailable(f"`aside repl` gave no answer in {timeout:g} s") from e
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"repl round trip failed: {e}") from e
    if proc.returncode == 0 and {"ok": True} in parse_ndjson(proc.stdout):
        return True, "round trip ok", proc.stderr or ""
    # Both streams: a sandbox refusing the snippet answers on stdout, the CLI failing to reach Aside on stderr.
    said = "\n".join(t for t in ((proc.stderr or "").strip(), (proc.stdout or "").strip()) if t)[:400] or "no output"
    return False, f"exit {proc.returncode}: {said}", proc.stderr or ""


def _text(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def parse_ndjson(stdout: str) -> list[dict]:
    out: list[dict] = []
    for line in _text(stdout).split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out
