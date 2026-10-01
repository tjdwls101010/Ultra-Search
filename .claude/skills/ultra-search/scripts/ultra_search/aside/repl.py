"""Running JavaScript in the user's browser and reading back NDJSON.

The one thing worth knowing: a snippet that runs past 120 seconds is killed, and the
daemon reports that as "fetch failed: other side closed / Aside daemon is not reachable".
The daemon is fine. Taking that message at face value sends a caller to restart an app
that was never broken, so it is translated here into what actually happened.
"""
from __future__ import annotations

import json
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
_TIMEOUT_SIGNS = ("other side closed", "daemon is not reachable", "fetch failed")


class ReplTimeout(Exception):
    """The snippet was killed at the 120s limit. Partial output is still usable."""

    def __init__(self, lines: list[dict]) -> None:
        super().__init__("repl snippet exceeded the 120s limit")
        self.lines = lines


def run_code(code: str, *, timeout: float = REPL_HARD_LIMIT + 15) -> list[dict]:
    """Run code in the REPL and return the JSON objects it printed, in order.

    Partial output survives a timeout on purpose: the snippets print each result as it
    lands precisely so that a batch cut short still yields the URLs that finished.
    """
    try:
        proc = subprocess.run(
            [aside_bin(), "repl", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ReplTimeout(parse_ndjson(_text(e.stdout))) from e
    except OSError as e:
        raise AsideUnavailable(f"could not run `aside repl`: {e}") from e

    lines = parse_ndjson(proc.stdout)
    if proc.returncode != 0:
        blob = f"{proc.stdout}\n{proc.stderr}".lower()
        if any(sign in blob for sign in _TIMEOUT_SIGNS):
            # The message names the daemon, but the daemon is running: this is the 120s
            # snippet kill wearing a misleading label.
            raise ReplTimeout(lines)
        raise AsideUnavailable(
            f"`aside repl` failed: {(proc.stderr or proc.stdout or '').strip()[:400]}",
            fix="Check the Aside app is running, then re-run `doctor`.",
        )
    return lines


def run_snippet(name: str, args: dict, *, timeout: float = REPL_HARD_LIMIT + 15) -> list[dict]:
    """Run one of this package's snippets with ``args`` as its `ARGS`."""
    return run_code(f"const ARGS = {json.dumps(args, ensure_ascii=False)};\n{_load_snippet(name)}", timeout=timeout)


def _load_snippet(name: str) -> str:
    path = SNIPPETS / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise AsideUnavailable(f"missing repl snippet {name}", fix=f"Reinstall the skill; expected {path}") from e


def repl_probe() -> tuple[bool, str]:
    """Run a snippet whose output is known and check that exact output came back.

    A round trip, not just a health endpoint: the daemon answering HTTP and the daemon
    running a snippet are different things, and only the second one matters. Any output is
    not enough either: a sandbox that refuses the snippet still prints its refusal.
    """
    code = 'console.log(JSON.stringify({ok:true}));'
    try:
        proc = subprocess.run([aside_bin(), "repl", code], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"repl round trip failed: {e}") from e
    if proc.returncode == 0 and {"ok": True} in parse_ndjson(proc.stdout):
        return True, "round trip ok"
    said = (proc.stdout or proc.stderr or "").strip()[:200] or "no output"
    return False, f"exit {proc.returncode}: {said}"


def _text(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def parse_ndjson(stdout: str) -> list[dict]:
    out: list[dict] = []
    for line in _text(stdout).splitlines():
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
