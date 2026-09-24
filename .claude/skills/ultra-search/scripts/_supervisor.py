"""The state machine that turns a running `aside exec` into a result on disk.

Deciding a run is over is the whole problem. Three things that look like endings are not:
silence, because a parent goes quiet for minutes while its subagents work; a killed CLI,
because the daemon-side run carries on regardless; and a missing session, because the
transcript is a private surface that may simply not be there. So the only hard signal is
the process exiting with its stdout drained, and each remaining ambiguity gets its own
state rather than being rounded to "done":

    completed               process exited, session read, children all terminal
    completed_with_orphans  as above, but a child was still writing -- ids reported
    completed_unstructured  process exited, session never correlated; answer from stdout
    failed                  non-zero exit
    abandoned               we stopped watching. THE RUN CONTINUES.

Run detached, this writes meta.json continuously so `status` and `log` can read progress
from a process that has no channel back to them.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _events
import _evidence
import _exec
import _registry
import _store

POLL = 2.0
#: How long to keep looking for the session before giving up and using stdout alone.
DISCOVERY_DEADLINE = 30.0
#: After the parent exits, how long a child gets to reach a terminal state.
SETTLE = 10.0

_URL_IN_STDOUT = re.compile(r'https?://[^\s"\'<>)\]]+')


def supervise(
    run: _registry.Run,
    *,
    poll: float = POLL,
    discovery_deadline: float = DISCOVERY_DEADLINE,
    settle: float = SETTLE,
    timeout: float | None = None,
) -> dict:
    meta = run.meta()
    prompt = meta.get("prompt") or ""
    marker = meta.get("marker") or _registry.marker_for(run.run_id)
    if timeout is None and meta.get("watch_timeout") is not None:
        # `--timeout` is recorded by the CLI that started the run; the supervisor is a
        # separate process with no way to be passed it, so it is read back from disk here.
        timeout = float(meta["watch_timeout"])

    argv = _exec.exec_argv(
        _registry.decorate_prompt(prompt, marker),
        session=meta.get("resume_session_id"),
        effort=meta.get("effort"),
        model=meta.get("model"),
        speed=meta.get("speed"),
    )
    # A resumed run appends to a session that already exists, so its transcript opens with
    # the original prompt and the marker never appears in the first line that discovery
    # reads. The id is already known here -- use it rather than hunting for it.
    session_id: str | None = meta.get("session_id") or meta.get("resume_session_id")

    proc = _exec.spawn_exec(argv, run.stdout_path)
    started = time.time()
    opening = {"state": "running", "pid": proc.pid, "supervisor_pid": os.getpid(),
               "started_at": started, "argv": argv}
    if session_id:
        opening["session_id"] = session_id
    run.update_meta(**opening)

    home = _store.aside_home()
    cursor = int(meta.get("session_cursor") or 0)
    child_cursors: dict[str, int] = dict(meta.get("child_cursors") or {})
    children: list[str] = list(meta.get("children") or [])
    exit_code: int | None = None

    while True:
        now = time.time()
        if _stop_requested(run):
            return _abandon(run, "stop requested", proc)
        if timeout is not None and now - started >= timeout:
            return _abandon(run, "watch timeout", proc)

        if session_id is None and now - started <= discovery_deadline:
            found = _store.find_session_by_marker(home, marker)
            if found:
                session_id = found.session_id
                run.update_meta(session_id=session_id)

        if session_id:
            cursor, children, child_cursors = _sync(run, home, session_id, cursor, children, child_cursors)

        exit_code = proc.poll()
        if exit_code is not None:
            break
        time.sleep(poll)

    # The process is gone, but its last writes may not have landed yet. Drain, then
    # give children a bounded window: a child that finishes here is a clean completion,
    # one that does not is reported by id rather than quietly ignored.
    deadline = time.time() + settle
    orphans: list[str] = []
    while True:
        if session_id is None and time.time() - started <= discovery_deadline:
            found = _store.find_session_by_marker(home, marker)
            if found:
                session_id = found.session_id
                run.update_meta(session_id=session_id)
        if session_id:
            cursor, children, child_cursors = _sync(run, home, session_id, cursor, children, child_cursors)
            turn = _evidence.turn_of(run)
            orphans = [c for c in turn.children if not _evidence.child_is_terminal(turn.child_events[c])]
            # Both conditions, not just the children. The process exiting does not mean the
            # last message has been flushed, and on a resumed session the message that is
            # already there is the previous turn's answer -- which is why an unobserved turn
            # is waited for rather than read as this one.
            if turn.observed and _events.has_terminal_answer(turn.events) and not orphans:
                break
        if time.time() >= deadline:
            break
        time.sleep(min(poll, 0.2))

    return _finish(run, session_id, exit_code, orphans)


def _sync(run, home, session_id, cursor, children, child_cursors):
    src = _store.session_dir(home, session_id)
    if src:
        cursor = _store.copy_new_lines(src / "messages.jsonl", run.session_transcript, cursor)
    events, _ = _events.read_events(run.session_transcript)
    for cid in _events.child_session_ids(events):
        if cid not in children:
            children.append(cid)
    for cid in children:
        cd = _store.session_dir(home, cid)
        if cd:
            child_cursors[cid] = _store.copy_new_lines(
                cd / "messages.jsonl", run.child_transcript(cid), child_cursors.get(cid, 0)
            )
    run.update_meta(
        session_cursor=cursor,
        children=children,
        child_cursors=child_cursors,
        last_activity_at=_activity(run, home, session_id, children),
    )
    return cursor, children, child_cursors


def _activity(run, home, session_id, children) -> float:
    """Newest write anywhere this run touches: its own files, and Aside's session directories."""
    aside = _store.last_activity(home, session_id, children) if session_id else 0.0
    return max(aside, run.last_write())


def _stop_requested(run: _registry.Run) -> bool:
    return bool(run.meta().get("stop_requested"))


def _abandon(run: _registry.Run, reason: str, proc) -> dict:
    try:
        proc.terminate()
    except OSError:
        pass
    return run.update_meta(
        state="abandoned",
        reason=reason,
        # Said in the payload, not only in documentation, because this is the one thing
        # a caller is most likely to assume wrongly and never be corrected on.
        daemon_run_continues=True,
        note="the daemon-side run keeps going and keeps spending credits; cancel it in the Aside app",
        finished_at=time.time(),
    )


def _finish(run, session_id, exit_code, orphans) -> dict:
    stdout = _read_text(run.stdout_path)
    # This turn only. A resumed session's earlier turns are context, not results, and
    # counting them again would attribute the previous answer, its sources and its tokens
    # to this run -- and strictly this turn's children, for the same reason.
    turn = _evidence.turn_of(run) if session_id else _evidence.Turn(observed=False)
    children: list[str] = turn.children

    if turn.observed:
        sources = turn.sources()
        answer = turn.answer(sources)
        usage = turn.usage()
        structured = True
    else:
        answer, sources, usage, structured = _from_stdout(stdout)

    if exit_code not in (0, None):
        state = "failed"
    elif not structured:
        state = "completed_unstructured"
    elif orphans:
        state = "completed_with_orphans"
    else:
        state = "completed"

    result = {
        "run_id": run.run_id,
        "state": state,
        "answer": answer,
        "sources": [
            {"url": s.url, "title": s.title, "id": s.id, "ids": s.ids, "opened": s.opened, "published": s.published}
            for s in sources
        ],
        "usage": usage,
        "children": children,
        "orphan_children": orphans,
        "empty": not answer.strip() and not sources,
        "exit_code": exit_code,
    }
    if not structured:
        result["note"] = (
            "this run's turn never appeared in the session transcript; answer and sources come from stdout only"
            if session_id else
            "the session transcript was never found; answer and sources come from stdout only"
        )
    _registry.atomic_write_json(run.path / "result.json", result)
    return run.update_meta(
        state=state,
        exit_code=exit_code,
        orphan_children=orphans,
        children=children,
        empty=result["empty"],
        finished_at=time.time(),
    )


def _from_stdout(stdout: str):
    """Everything recoverable when the session was never correlated.

    The last non-tool block of stdout is the agent's final message, and the URLs it
    printed along the way are the only source list available. Both are worse than the
    transcript -- which is why this path is labelled -- but they are not nothing.
    """
    lines = [l.rstrip() for l in stdout.splitlines()]
    answer_lines: list[str] = []
    for line in reversed(lines):
        if not line.strip():
            if answer_lines:
                break
            continue
        if line.startswith(("Thinking:", " > ")) or re.match(r"^\w+\(", line):
            break
        answer_lines.append(line)
    answer = "\n".join(reversed(answer_lines)).strip()
    urls: list[str] = []
    for u in _URL_IN_STDOUT.findall(stdout):
        u = u.rstrip('.,")')
        if u not in urls:
            urls.append(u)
    sources = [_events.Source(url=u, opened=False) for u in urls]
    return answer, sources, _events.total_usage([]), False


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Internal: watch one ultra-search run to completion.")
    p.add_argument("--run-path", required=True, help="The run directory to supervise.")
    args = p.parse_args(argv)
    path = Path(args.run_path)
    run = _registry.Run(run_id=path.name, path=path)
    try:
        meta = supervise(run)
    except Exception as e:  # noqa: BLE001 - a detached process must record why it died
        run.update_meta(state="failed", reason=f"{type(e).__name__}: {e}", finished_at=time.time())
        raise
    return 0 if meta.get("state", "").startswith("completed") else 1


if __name__ == "__main__":
    sys.exit(main())
