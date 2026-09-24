"""Running JavaScript in the user's browser and reading back NDJSON.

The one thing worth knowing: a snippet that runs past 120 seconds is killed, and the
daemon reports that as "fetch failed: other side closed / Aside daemon is not reachable".
The daemon is fine. Taking that message at face value sends a caller to restart an app
that was never broken, so it is translated here into what actually happened.
"""
from __future__ import annotations

import json
import subprocess

from ultra_search.aside.process import aside_bin
from ultra_search.contract import AsideUnavailable

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
