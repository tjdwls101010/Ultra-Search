"""Watching a run, and ending the watch in a way the caller can act on.

`--follow` exits when the run reaches a terminal state, and that exit is the product.
Run as a background Bash call, a process that exits notifies the caller -- so following
turns "a run is happening somewhere" into "you will be told when it is done", which is
the difference between a background search that gets collected and one that is started
and forgotten.

Three endings are printed differently on purpose. `run.<state>` means the run finished
and there is a result to collect. `run.still-running` means only that we stopped looking.
`heartbeat` means a silence has been checked and is alive. Collapsing any two of those
would make a caller either collect nothing or wait forever.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import _events
import _registry

TERMINAL_STATES = frozenset({"completed", "completed_with_orphans", "completed_unstructured", "failed", "abandoned"})
POLL = 1.0


def parse_since(since: str | int | None, runs: list) -> dict[str, dict[str, int]]:
    """Cursors from the `# cursor=` line of a previous call.

    A single run's cursor is a plain integer so the common case stays readable; a group's
    is the JSON object printed for it, because one number cannot describe several streams
    advancing independently.
    """
    empty = {r.run_id: {} for r in runs}
    if since in (None, "", 0, "0"):
        return empty
    text = str(since)
    if text.isdigit():
        return {runs[0].run_id: {"": int(text)}} if runs else empty
    try:
        loaded = json.loads(text)
    except ValueError:
        return empty
    if not isinstance(loaded, dict):
        return empty
    out = dict(empty)
    for run_id, streams in loaded.items():
        if isinstance(streams, dict):
            out[run_id] = {k: int(v) for k, v in streams.items()}
        elif isinstance(streams, int):
            out[run_id] = {"": streams}
    return out


def format_cursor(cursors: dict[str, dict[str, int]], runs: list) -> str | int:
    if len(runs) == 1:
        return cursors.get(runs[0].run_id, {}).get("", 0)
    return json.dumps(cursors, ensure_ascii=False, separators=(",", ":"))


def _streams(run: _registry.Run) -> list[tuple[str, Path]]:
    """The parent transcript plus every child's, each with its own cursor key."""
    out = [("", run.session_transcript)]
    for p in run.child_transcripts():
        out.append((p.stem, p))
    return out


def _drain(run: _registry.Run, cursors: dict[str, int], level: str, label: bool) -> list[str]:
    lines: list[str] = []
    for key, path in _streams(run):
        events, cursor = _events.read_events(path, cursors.get(key, 0))
        cursors[key] = cursor
        for e in events:
            rendered = _events.render(e, level=level)
            if not rendered:
                continue
            prefix = ""
            if label:
                prefix = f"[{run.run_id}]"
            if key:
                prefix += f"[child {key}]"
            lines.append(f"{prefix} {rendered}" if prefix else rendered)
    return lines


def follow(
    runs: list,
    *,
    out=None,
    level: str = "compact",
    since: str | int | None = None,
    follow: bool = False,
    follow_timeout: float = 570.0,
    heartbeat: float | None = None,
    poll: float = POLL,
) -> str | int:
    stream = out if out is not None else sys.stdout
    cursors = parse_since(since, runs)
    label = len(runs) > 1
    started = time.time()
    last_beat = started

    def emit(line: str) -> None:
        print(line, file=stream, flush=True)

    while True:
        for run in runs:
            for line in _drain(run, cursors.setdefault(run.run_id, {}), level, label):
                emit(line)

        states = {r.run_id: (r.meta().get("state") or "unknown") for r in runs}
        done = [r for r in runs if states[r.run_id] in TERMINAL_STATES]

        if not follow:
            break

        if len(done) == len(runs):
            for run in runs:
                emit(f"run.{states[run.run_id]} {run.run_id}")
            if label:
                emit(f"group.completed {len(runs)} run(s)")
            break

        now = time.time()
        if now - started >= follow_timeout:
            for run in runs:
                if states[run.run_id] not in TERMINAL_STATES:
                    emit(f"run.still-running {run.run_id} watched={round(now - started, 1)}s")
            break

        if heartbeat and now - last_beat >= heartbeat:
            last_beat = now
            live = sum(len(r.meta().get("children") or []) for r in runs if states[r.run_id] not in TERMINAL_STATES)
            waiting = [r.run_id for r in runs if states[r.run_id] not in TERMINAL_STATES]
            emit(f"heartbeat elapsed={round(now - started, 1)}s running={len(waiting)} children={live}")

        time.sleep(poll)

    cursor = format_cursor(cursors, runs)
    emit(f"# cursor={cursor}")
    return cursor
