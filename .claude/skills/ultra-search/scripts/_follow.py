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
import _evidence
import _registry
import _render
from _errors import ArgumentError

TERMINAL_STATES = frozenset({"completed", "completed_with_orphans", "completed_unstructured", "failed", "abandoned"})
POLL = 1.0


def parse_since(since: str | int | None, runs: list) -> dict[str, dict[str, int]]:
    """Cursors from the `# cursor=` line of a previous call.

    A single run's cursor is a plain integer so the common case stays readable; a group's
    is the JSON object printed for it, because one number cannot describe several streams
    advancing independently. Anything else is refused: read as "from the start", it would
    replay the whole run to a caller who believes it is new.
    """
    empty = {r.run_id: {} for r in runs}
    if since in (None, "", 0, "0"):
        return empty
    text = str(since)
    if text.isascii() and text.isdigit():
        return {runs[0].run_id: {"": int(text)}} if runs else empty
    bad = ArgumentError(
        f"--since {text!r} is not a cursor this command printed",
        fix="Pass the `cursor` value from the previous `log` response, or omit --since to read from the start.",
    )
    try:
        loaded = json.loads(text)
    except ValueError:
        raise bad from None
    if not isinstance(loaded, dict):
        raise bad
    out = dict(empty)
    for run_id, streams in loaded.items():
        if _offset(streams):
            out[run_id] = {"": streams}
        elif isinstance(streams, dict) and all(_offset(v) for v in streams.values()):
            out[run_id] = dict(streams)
        else:
            raise bad
    return out


def _offset(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def format_cursor(cursors: dict[str, dict[str, int]], runs: list) -> str | int:
    # A plain integer only while there is one stream to describe. Once a child exists an
    # integer can only carry the parent's offset, and the next read replays the child.
    if len(runs) == 1 and set(cursors.get(runs[0].run_id, {})) <= {""}:
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
    streams = _streams(run)
    start_line = 0
    meta = run.meta()
    if meta.get("resume_session_id"):
        # 성진: resume은 턴 경계를 위해 부모 로그를 매번 읽는다; 긴 세션 감시가 병목이면 시작 바이트를 보존한다.
        turn = _evidence.turn_of(run)
        if not turn.observed:
            return lines
        start_line = turn.start_line
        children = set(turn.children)
        streams = [(key, path) for key, path in streams if not key or key in children]
    for key, path in streams:
        events, cursor = _events.read_events(path, cursors.get(key, 0))
        cursors[key] = cursor
        if not key:
            events = [event for event in events if event.index >= start_line]
        prefix = f"[{run.run_id}]" if label else ""
        if key:
            prefix += f"[child {key}]"
        for e in events:
            rendered = _render.render(e, level=level)
            # Every line, not just the first: a child's second call or the body of its
            # answer would otherwise read as the parent's.
            for line in rendered.splitlines():
                lines.append(f"{prefix} {line}" if prefix and line else prefix or line)
    return lines


def _live_children(run: _registry.Run) -> int:
    """Children of this run's turn that have not finished -- the ones keeping a quiet parent busy."""
    turn = _evidence.turn_of(run)
    return sum(1 for cid in turn.children if not _evidence.child_is_terminal(turn.child_events[cid]))


def follow(
    runs: list,
    *,
    out=None,
    level: str = "progress",
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
                emit(f"group.finished {len(runs)} run(s)")
            break

        now = time.time()
        if now - started >= follow_timeout:
            for run in runs:
                if states[run.run_id] not in TERMINAL_STATES:
                    emit(f"run.still-running {run.run_id} watched={round(now - started, 1)}s")
            break

        if heartbeat and now - last_beat >= heartbeat:
            last_beat = now
            live = sum(_live_children(r) for r in runs if states[r.run_id] not in TERMINAL_STATES)
            waiting = [r.run_id for r in runs if states[r.run_id] not in TERMINAL_STATES]
            emit(f"heartbeat elapsed={round(now - started, 1)}s running={len(waiting)} children={live}")

        time.sleep(poll)

    cursor = format_cursor(cursors, runs)
    emit(f"# cursor={cursor}")
    return cursor
