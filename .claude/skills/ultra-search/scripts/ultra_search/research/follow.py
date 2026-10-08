"""A run's events as lines: read once, after the fact (`log`), or as they come while `result --wait` waits.

A wait prints only what happens while it waits -- a run's history is `log`'s -- so a caller that chains waits never reads a line twice, and the wait's exit, run as a background Bash call, is what tells the caller the work has ended.

Every line here is progress, so it goes to stderr as it happens, each flushed: stdout is
kept for the one JSON reply the command ends with.
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable

from ultra_search import aside, runs
from ultra_search.research import evidence, render
from ultra_search.research.states import TERMINAL_STATES

POLL = 1.0


def print_log(targets: list, *, level: str) -> None:
    """Every event of these runs' turns, once."""
    numbering: dict[str, int] = {}
    for run in targets:
        for line in _drain(run, {}, level, len(targets) > 1, numbering):
            _emit(line)


def wait(targets: list, *, seconds: float, check: Callable[[runs.Run], None], level: str = "progress") -> None:
    """Wait until every run has ended or ``seconds`` have passed, printing what they do meanwhile. ``check`` sees each run on every poll: the chance to settle one that nothing is watching any more."""
    label = len(targets) > 1
    cursors: dict[str, dict[str, int]] = {r.run_id: {} for r in targets}
    numbering: dict[str, int] = {}
    for run in targets:
        _drain(run, cursors[run.run_id], level, label, numbering)
    deadline = time.time() + seconds
    while True:
        for run in targets:
            check(run)
            for line in _drain(run, cursors[run.run_id], level, label, numbering):
                _emit(line)
        if all((r.meta().get("state") or "") in TERMINAL_STATES for r in targets) or time.time() >= deadline:
            return
        time.sleep(min(POLL, max(0.0, deadline - time.time())))


def _emit(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def _drain(run: runs.Run, cursors: dict[str, int], level: str, label: bool, numbering: dict[str, int]) -> list[str]:
    lines: list[str] = []
    # This run's turn and its children only, bounded the way `show` and `result` bound them: a resumed run's earlier
    # turns, and a turn the session went on to afterwards, belong to other runs. The parent's records are read before
    # the bounds are taken, so the bounds always come from a transcript at least as new as the records they cut.
    # 성진: 턴 경계를 위해 부모 로그를 매번 처음부터 읽는다; 긴 세션 감시가 병목이면 시작·끝 위치를 보존한다.
    parent, parent_cursor = aside.read_events(run.session_transcript, cursors.get("", 0))
    turn = evidence.turn_of(run)
    if not turn.observed:
        return lines
    cursors[""] = parent_cursor
    streams = [("", run.session_transcript, parent, turn.start_line, turn.end_line)]
    for cid in sorted(turn.children):
        path = run.child_transcript(cid)
        events, cursors[cid] = aside.read_events(path, cursors.get(cid, 0))
        streams.append((cid, path, events, turn.child_events[cid][0].index if turn.child_events[cid] else 0, None))
    for key, path, events, start, end in streams:
        events = [event for event in events if event.index >= start and (end is None or event.index < end)]
        ordinals = _number(run, path, events, start, numbering) if not key and level in ("steps", "full") else {}
        prefix = f"[{run.run_id}]" if label else ""
        if key:
            prefix += f"[child {key}]"
        for e in events:
            rendered = render.render(e, level=level, ordinal=ordinals.get(e.index))
            # Every line, not just the first: a child's second call or the body of its
            # answer would otherwise read as the parent's.
            for line in rendered.splitlines():
                lines.append(f"{prefix} {line}" if prefix and line else prefix or line)
    return lines


def _number(run: runs.Run, path, events: list, start_line: int, numbering: dict[str, int]) -> dict[int, int]:
    """Line index -> N for this turn's own tool results, the numbering `show --item N` uses.

    Counted over the whole turn, not the chunk being printed, so a read from a cursor carries
    on where the last one stopped. The results before the first chunk are counted once per
    `log` call; after that the count is carried.
    """
    if not events:
        return {}
    n = numbering.get(run.run_id)
    if n is None:
        first = events[0].index
        earlier, _ = aside.read_events(path) if first > start_line else ([], 0)
        n = sum(1 for e in earlier if e.kind == "tool_result" and start_line <= e.index < first)
    ordinals = {}
    for e in events:
        if e.kind == "tool_result":
            ordinals[e.index] = n
            n += 1
    numbering[run.run_id] = n
    return ordinals
