"""The state machine that turns a running agent turn into a result on disk.

Deciding a run is over is the whole problem. Four things that look like endings are not: silence, because a parent goes quiet for minutes while its subagents work; a killed CLI, because the daemon-side run carries on regardless; a missing session, because the transcript is a private surface that may simply not be there; and the process exiting, because `aside exec` has been seen returning 0 mid-turn, with its subagents' results and its final answer still to come. Where the daemon frames turns, the signal is this turn's `finished` record, and each remaining ambiguity gets its own state rather than being rounded to "done":

    completed               this turn finished and every child of it did
    completed_with_orphans  as above, but a child was still writing -- ids reported
    completed_unstructured  the session, or this turn in it, never appeared; answer from stdout
    failed                  a non-zero exit, or a turn that ended on an error
    abandoned               watching stopped. THE RUN CONTINUES.

Each poll, the first of these that holds decides:

    W1  the process exited non-zero                               failed
    W2  this turn has finished                                    wind down, below
    W3  exited 0, no session found by the discovery deadline      completed_unstructured
    W4  exited 0, session found, this turn not in it yet          wait the settle window for it, else completed_unstructured
    W5  exited 0, this turn seen without lifecycle records        the earlier format: settle, then judge as below
    W6  nothing written for the idle limit, alive or exited 0     abandoned, with what it had by then
    W7  anything else -- still running, or exited 0 mid-turn      keep watching

Winding down gives the process and this turn's children the settle window to end, ends a process still running after it, and then judges once, as the earlier format's settle does: a non-zero exit of its own or a last message that stopped on an error is failed, a child still running is completed_with_orphans, anything else completed. The exit code of a process the supervisor ended says nothing about the turn and is not read.

Run detached, this writes meta.json continuously so `result` and `log` can read progress from a process that has no channel back to them. It is started as `cli.py _supervise <run>`: the one entry point, found by the path the caller used to reach it. It claims the run before it starts any work, and `result` settles a run whose supervisor never claimed it or is gone: a supervisor that wakes after that finds the run settled and starts nothing.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ultra_search import aside, runs
from ultra_search.research import evidence
from ultra_search.research.marker import decorate_prompt, marker_for

POLL = 2.0
#: How long to keep looking for the session before giving up and using stdout alone.
DISCOVERY_DEADLINE = 30.0
#: After the turn ends, how long the process and the turn's children get to end too.
SETTLE = 10.0
#: How long a turn may go without a write anywhere it reaches before watching gives up on it.
# 성진: 무활동 상한은 관측(부모 침묵 74초, 자식은 그동안 기록)에서 넉넉히 잡은 값이다; 자식까지 10분 넘게 조용한 정상 조사는 abandoned로 끊기니, 그런 조사가 실제로 보이면 상한을 올리거나 데몬의 진행 신호를 함께 본다.
IDLE_LIMIT = 600.0


def spawn(cli: str, run_path: str | os.PathLike[str]) -> int:
    """Start the detached supervisor for a run and return its pid.

    setsid, and output to a file rather than a pipe: an inherited pipe would keep the
    supervisor's lifetime tied to a reader that is about to go away, which is the exact
    coupling this is here to break.
    """
    run = Path(run_path).absolute()
    log = run / "supervisor.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("ab")
    proc = subprocess.Popen(
        [sys.executable, cli, "_supervise", str(run)],
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        cwd=str(run),
    )
    return proc.pid


def run_detached(run_path: str | os.PathLike[str]) -> None:
    """The supervisor process's whole life: watch the run, and record why if watching dies."""
    path = Path(run_path)
    run = runs.Run(run_id=path.name, path=path)
    try:
        supervise(run)
    except Exception as e:  # noqa: BLE001 - a detached process must record why it died
        run.update_meta(state="failed", reason=f"{type(e).__name__}: {e}", finished_at=time.time())
        raise


class _Watch:
    """What the supervisor carries from one poll to the next: the session once found, how far each transcript has been copied, and when anything this turn reaches was last written."""

    def __init__(self, run: runs.Run, meta: dict, started: float, discovery_deadline: float) -> None:
        self.run = run
        self.marker = meta.get("marker") or marker_for(run.run_id)
        # A resumed run appends to a session that already exists, so its transcript opens with
        # the original prompt and the marker never appears in the first line that discovery
        # reads. The id is already known here -- use it rather than hunting for it.
        self.session_id: str | None = meta.get("session_id") or meta.get("resume_session_id")
        self.cursor = int(meta.get("session_cursor") or 0)
        self.child_cursors: dict[str, int] = dict(meta.get("child_cursors") or {})
        self.children: list[str] = list(meta.get("children") or [])
        self.started = started
        self.discovery_deadline = discovery_deadline
        self.activity = started

    def sync(self) -> evidence.Turn:
        """Copy what is new, and return this run's turn as it stands."""
        if self.session_id is None and time.time() - self.started <= self.discovery_deadline:
            self.session_id = aside.find_session_by_marker(self.marker)
            if self.session_id:
                self.run.update_meta(session_id=self.session_id)
        if self.session_id is None:
            self.activity = max(self.activity, self.run.last_write([]))
            return evidence.Turn(observed=False)
        src = aside.session_transcript(self.session_id)
        if src:
            self.cursor = runs.copy_new_lines(src, self.run.session_transcript, self.cursor)
        events, _ = aside.read_events(self.run.session_transcript)
        for cid in evidence.child_session_ids(events):
            if cid not in self.children:
                self.children.append(cid)
        for cid in self.children:
            child = aside.session_transcript(cid)
            if child:
                self.child_cursors[cid] = runs.copy_new_lines(child, self.run.child_transcript(cid),
                                                              self.child_cursors.get(cid, 0))
        turn = evidence.turn_of(self.run)
        # This turn's children only: a resumed session's earlier children can still be writing,
        # and that is no sign this turn is alive.
        self.activity = max(self.activity, aside.last_activity(self.session_id, turn.children),
                            self.run.last_write(turn.children))
        self.run.update_meta(session_cursor=self.cursor, children=self.children, child_cursors=self.child_cursors,
                             last_activity_at=self.activity)
        return turn


def supervise(
    run: runs.Run,
    *,
    poll: float = POLL,
    discovery_deadline: float = DISCOVERY_DEADLINE,
    settle: float = SETTLE,
    idle_limit: float = IDLE_LIMIT,
) -> dict:
    # Claimed under the lock before anything starts: a run `result` has already settled -- its supervisor taken
    # for one that never started -- must not have its work started now, after the caller was told otherwise.
    meta = run.update_meta_if(lambda m: {"supervisor_pid": os.getpid()} if m.get("state") == "starting"
                              and not m.get("supervisor_pid") else None)
    if meta.get("supervisor_pid") != os.getpid():
        return meta
    prompt = meta.get("prompt") or ""

    proc = aside.start_exec(
        decorate_prompt(prompt, meta.get("marker") or marker_for(run.run_id)),
        stdout_path=run.stdout_path,
        session=meta.get("resume_session_id"),
        effort=meta.get("effort"),
        model=meta.get("model"),
        speed=meta.get("speed"),
    )
    started = time.time()
    watch = _Watch(run, meta, started, discovery_deadline)
    opening = {"state": "running", "pid": proc.pid, "supervisor_pid": os.getpid(),
               "started_at": started, "argv": list(proc.args)}
    if watch.session_id:
        opening["session_id"] = watch.session_id
    run.update_meta(**opening)

    exit_code: int | None = None
    exited_at = 0.0
    while True:
        # The exit is read before the transcript, never after: whatever the process wrote before exiting is then
        # on disk when this poll copies it, so an ending is never judged on a snapshot older than the exit.
        if exit_code is None:
            exit_code = proc.poll()
            exited_at = time.time()
        turn = watch.sync()
        now = time.time()

        if exit_code not in (None, 0):                                            # W1
            return _finish(run, watch.session_id, turn, "failed", exit_code, turn.unfinished_children())
        if turn.finished:                                                         # W2
            return _wind_down(run, watch, proc, exit_code, poll=poll, settle=settle)
        if exit_code == 0:
            if watch.session_id is None:
                if now - started > discovery_deadline:                            # W3
                    return _finish(run, None, turn, "completed_unstructured", exit_code, [])
            elif not turn.observed:                                               # W4
                # On a resumed session the message already there is the previous turn's answer, so a turn not
                # seen yet is waited for, never read as this one.
                if now - exited_at >= settle:
                    return _finish(run, watch.session_id, turn, "completed_unstructured", exit_code, [])
                time.sleep(min(poll, 0.2))
                continue
            elif not turn.framed:                                                 # W5
                # The process exiting does not mean its last message has landed: wait for an answer as well as
                # for the children, within the settle window.
                orphans = turn.unfinished_children()
                if (evidence.has_terminal_answer(turn.events) and not orphans) or now - exited_at >= settle:
                    state = "failed" if turn.ended_on_error() else "completed_with_orphans" if orphans else "completed"
                    return _finish(run, watch.session_id, turn, state, exit_code, orphans)
                time.sleep(min(poll, 0.2))
                continue
        if now - watch.activity >= idle_limit:                                    # W6
            return _abandon_quiet(run, watch, turn, proc, exit_code, idle_limit)
        time.sleep(poll)                                                          # W7


def _wind_down(run: runs.Run, watch: _Watch, proc, exit_code: int | None, *, poll: float, settle: float) -> dict:
    """This turn has finished: give the process and the turn's children the settle window, then judge once."""
    deadline = time.time() + settle
    while True:
        if exit_code is None:
            exit_code = proc.poll()
        turn = watch.sync()
        orphans = turn.unfinished_children()
        if (exit_code is not None and not orphans) or time.time() >= deadline:
            break
        time.sleep(min(poll, 0.2))
    if exit_code is None:
        # It may have exited while the last sync ran: an exit of its own is judged by its code, on what it wrote.
        exit_code = proc.poll()
        if exit_code is not None:
            turn = watch.sync()
            orphans = turn.unfinished_children()
    ended_by_us = exit_code is None
    if ended_by_us:
        _terminate(proc)
    if exit_code not in (None, 0) or turn.ended_on_error():
        state = "failed"
    elif orphans:
        state = "completed_with_orphans"
    else:
        state = "completed"
    extra = {"terminated_by_supervisor": True} if ended_by_us else {}
    return _finish(run, watch.session_id, turn, state, exit_code, orphans, **extra)


def _terminate(proc) -> None:
    try:
        proc.terminate()
    except OSError:
        pass


def _abandon_quiet(run: runs.Run, watch: _Watch, turn: evidence.Turn, proc, exit_code: int | None,
                   idle_limit: float) -> dict:
    """Nothing this turn reaches has been written for the idle limit: keep what it had, and stop watching."""
    _terminate(proc)
    return _finish(
        run, watch.session_id, turn, "abandoned", exit_code, turn.unfinished_children(),
        result_note=f"nothing was written for {idle_limit:g}s before the turn finished; this is what it had by then",
        reason="the turn went quiet before it finished",
        # Said in the payload, not only in documentation, because this is the one thing
        # a caller is most likely to assume wrongly and never be corrected on.
        daemon_run_continues=True,
    )


def _finish(run: runs.Run, session_id: str | None, turn: evidence.Turn, state: str, exit_code: int | None,
            orphans: list[str], *, result_note: str | None = None, **meta: object) -> dict:
    """Write result.json from this turn -- or, where it was never seen, from stdout -- and then the ending to meta.json."""
    # This turn only. A resumed session's earlier turns are context, not results, and
    # counting them again would attribute the previous answer, its sources and its tokens
    # to this run -- and strictly this turn's children, for the same reason.
    kept: dict[str | None, dict[str, Path]] = {}
    missing: list[dict] = []
    if turn.observed:
        sources = turn.sources()
        if session_id:
            kept, missing = _keep_artifacts(run, session_id, turn, sources)
        answer = turn.answer(sources, rewrite=lambda cid, text: _point_at_copies(text, cid, session_id, kept))
        usage = turn.usage()
    else:
        answer, sources, usage = _from_stdout(_read_text(run.stdout_path))
        result_note = result_note or (
            "this run's turn never appeared in the session transcript; answer and sources come from stdout only"
            if session_id else
            "the session transcript was never found; answer and sources come from stdout only"
        )
    result = {
        "run_id": run.run_id,
        "state": state,
        "answer": answer,
        "sources": [
            {"url": s.url, "title": s.title, "id": s.id, "ids": s.ids, "opened": s.opened, "published": s.published}
            for s in sources
        ],
        "usage": usage,
        "children": turn.children,
        "orphan_children": orphans,
        "empty": not answer.strip() and not sources,
        "exit_code": exit_code,
    }
    notes = [result_note]
    copied = [str(path) for cid in [None, *turn.children] for path in kept.get(cid, {}).values()]
    if copied:
        result["artifacts"] = copied
        if state in ("completed_with_orphans", "abandoned"):
            notes.append("the saved files are copies as they were when watching ended")
    if missing:
        result["artifacts_missing"] = missing
        notes.append(f"{len(missing)} saved file{'' if len(missing) == 1 else 's'} could not be copied; "
                     "artifacts_missing in this result says why")
    if any(notes):
        result["note"] = " ".join(filter(None, notes))
    runs.atomic_write_json(run.path / "result.json", result)
    return run.update_meta(
        state=state,
        exit_code=exit_code,
        orphan_children=orphans,
        children=turn.children,
        empty=result["empty"],
        finished_at=time.time(),
        **meta,
    )


def _keep_artifacts(run: runs.Run, session_id: str, turn: evidence.Turn,
                    sources: list[evidence.Source]) -> tuple[dict[str | None, dict[str, Path]], list[dict]]:
    """Copy into the run the files this turn's sessions saved -- each session's under its own id, since a parent's folder can be named like a child -- and say which could not be copied.

    A session keeps every turn's saved files together. This turn's are the ones changed since its part in the turn began and before its session's next turn did; an older one is kept only when an answer names it, as a run collecting an earlier child's late result names what that child saved, and where the transcript gives no start only a named file is. A file a later turn changed is no longer the one this turn's answer meant, so it is reported rather than copied. The copies are taken now, so a child still at work, or an abandoned turn, leaves them as they were at this moment.
    """
    kept: dict[str | None, dict[str, Path]] = {}
    missing: list[dict] = []
    texts = dict(turn.stream_answers(sources))
    streams = [None, *turn.children]
    try:
        for cid in streams:
            sid = cid or session_id
            saved = aside.session_artifacts(sid)
            rels = [rel for rel, _, _ in saved]
            # A relative path means the folder of the session that wrote it; another session's answer names this
            # one's files only by absolute path.
            named = set(aside.referenced_artifacts(texts.get(cid, ""), sid, rels))
            for other in streams:
                if other != cid:
                    named |= set(aside.referenced_artifacts(texts.get(other, ""), sid, rels, absolute_only=True))
            began, next_began = turn.window(cid)

            def later(mtime: float) -> bool:
                # Aside stamps a record to the millisecond, so a file in the next turn's first millisecond could be
                # either turn's; it is not claimed for this one.
                return next_began is not None and mtime >= next_began

            for rel, path, mtime in saved:
                if later(mtime):
                    if rel in named:
                        missing.append({"path": str(path), "error": "changed after a later turn began"})
                    continue
                if rel not in named and (began is None or mtime < began):
                    continue
                dst = run.artifacts_dir / sid / rel
                try:
                    copied = runs.copy_snapshot(path, dst)
                except OSError as e:
                    missing.append({"path": str(path), "error": str(e)})
                    continue
                if later(copied.st_mtime):  # rewritten between the listing and the copy
                    dst.unlink(missing_ok=True)
                    if rel in named:
                        missing.append({"path": str(path), "error": "changed after a later turn began"})
                    continue
                kept.setdefault(cid, {})[rel] = dst
    except Exception as e:  # noqa: BLE001 - the result is written whatever happens to its copies
        missing.append({"path": str(run.artifacts_dir), "error": f"{type(e).__name__}: {e}"})
    return kept, missing


def _point_at_copies(text: str, cid: str | None, session_id: str | None,
                     kept: dict[str | None, dict[str, Path]]) -> str:
    """One stream's text naming the copies: its own session's files by any path, another session's by absolute path only."""
    if not session_id:
        return text
    text = aside.rewrite_artifact_refs(text, cid or session_id, kept.get(cid, {}))
    for other, copies in kept.items():
        if other != cid:
            text = aside.rewrite_artifact_refs(text, other or session_id, copies, absolute_only=True)
    return text


def _from_stdout(stdout: str):
    """Everything recoverable when the session was never correlated.

    The agent's final message, and the URLs printed along the way as the only source list
    available -- none of them known to have been opened. Both are worse than the
    transcript, which is why this path is labelled, but they are not nothing.
    """
    answer, urls = aside.parse_exec_output(stdout)
    sources = [evidence.Source(url=u, opened=False) for u in urls]
    return answer, sources, evidence.total_usage([])


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
