"""`search` and `resume` -- starting work and, when it outlasts the wait, handing back
something that can be picked up again.

Synchronous by default because most searches finish in seconds and an inline answer is
what the caller actually wanted. The interesting half is what happens when one does not:
the run is left alive, and the reply carries `next` -- the literal command that will wake
the caller when it finishes, with the Bash timeout that command needs. A handle alone
would be a handle nobody comes back for.

`status`, `log`, `result`, `show`, `stop`, `sessions` -- looking at runs that are already going.

These are split by the question each answers, because reaching for the wrong one is how a
caller ends up polling something that was never going to change. Is it alive and how far
along (`status`, one snapshot, no watching). What is it doing, incrementally (`log`, the
only watcher). What did it conclude (`result`). A finished run needs `result`, not more
`log`.

`status` reports and never acts. A slow investigation and a stuck one are indistinguishable
from here -- silence is not evidence, since a parent goes quiet for minutes while its
children work -- so it labels the silence and leaves the judgement to the caller.
"""
from __future__ import annotations

import json
import shlex
import time
from pathlib import Path

from ultra_search import aside, outcome, runs
from ultra_search.ids import is_safe_id
from ultra_search.outcome import ArgumentError, RunFailed
from ultra_search.research import evidence, follow, supervisor
from ultra_search.research.marker import marker_for, run_id_in
from ultra_search.research.states import FAILED_STATES, TERMINAL_STATES


def sessions(*, limit: int, mine: bool, search: str | None) -> int:
    # A filter searches everything and then takes the first N matches. Reading a page first
    # and filtering it afterwards reports "no match" for a session that is simply further
    # down the list, which is indistinguishable from its not existing.
    scan = 10_000 if (mine or search) else limit
    rows = [_session_row(s) for s in aside.session_summaries(limit=scan)]
    if mine:
        rows = [r for r in rows if r["started_by_ultra_search"]]
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in (r["prompt"] or "").lower()]
    rows = rows[:limit]
    print(json.dumps(
        {
            "ok": True,
            "command": "sessions",
            "sessions": rows,
            "note": "resume any of these by session_id. Aside deletes sessions within about a day.",
        },
        ensure_ascii=False,
    ))
    return 0 if rows else outcome.EXIT_EMPTY


def _session_row(summary: dict) -> dict:
    """A session as `sessions` lists it. The marker is read before the prompt is shortened for
    display: it sits at the end."""
    run_id = run_id_in(summary["opening_prompt"])
    return {
        "session_id": summary["session_id"],
        "date": summary["date"],
        "modified_at": summary["modified_at"],
        "prompt": " ".join(summary["opening_prompt"].split())[:160],
        "started_by_ultra_search": bool(run_id),
        "run_id": run_id,
    }


def _targets(root: Path, run: str | None, group: str | None, every: bool = False) -> list:
    if every:
        found = runs.all_runs(root)
        if not found:
            raise ArgumentError(f"no runs under {root}", fix="Start one with `search`.")
        return found
    if run:
        return [runs.resolve_run(root, run)]
    if group:
        return runs.resolve_group(root, group)
    return runs.latest_group(root)


# --- status ---------------------------------------------------------------------------


def status(root: Path, *, run: str | None, group: str | None, stall_after: float) -> int:
    now = time.time()
    targets = _targets(root, run, group)
    entries = [_status_entry(r, now, stall_after) for r in targets]
    print(json.dumps({"ok": True, "command": "status", "runs": entries}, ensure_ascii=False))
    return outcome.EXIT_RUN_FAILED if any(e["state"] in FAILED_STATES for e in entries) else 0


def _status_entry(run: runs.Run, now: float, stall_after: float) -> dict:
    meta = run.meta()
    # This run's turn and its children: a resumed run's transcript also holds earlier turns,
    # whose children and tokens belong to the runs that asked for them.
    turn = evidence.turn_of(run)
    children = turn.children
    # The supervisor records activity as it syncs, but a status call between two syncs
    # would read a stale number -- so the files themselves get the last word.
    last = max(float(meta.get("last_activity_at") or 0), run.last_write())
    idle = round(now - last, 1) if last else None
    state = meta.get("state") or "unknown"
    live = state not in TERMINAL_STATES
    entry = {
        **run_summary(run),
        "label": meta.get("label"),
        "session_id": meta.get("session_id"),
        "children": len(children),
        "child_ids": children,
        "last_activity_at": last or None,
        "idle_seconds": idle,
        "possibly_stalled": bool(live and idle is not None and idle > stall_after),
        "usage": turn.usage(),
    }
    if meta.get("group"):
        entry["group"] = meta["group"]
    if meta.get("session_id"):
        # Aside documents a run pausing for an approval or MFA prompt. It has never been
        # observed here, so it is surfaced rather than interpreted.
        susp = aside.suspension(meta["session_id"])
        if susp:
            entry["suspension"] = susp
    if entry["possibly_stalled"]:
        entry["note"] = (
            "idle beyond --stall-after. Nothing was stopped: a long investigation looks like this too. "
            "Check `log`, and cancel in the Aside app if it really is stuck."
        )
    return entry


def run_summary(run: runs.Run) -> dict:
    meta = run.meta()
    entry = {"run_id": run.run_id, "state": meta.get("state") or "unknown"}
    notes = []
    if meta.get("orphan_children"):
        entry["orphan_children"] = meta["orphan_children"]
        notes.append("Partial snapshot: these children were still running; late results are not collected automatically.")
    if entry["state"] == "abandoned":
        entry["daemon_run_continues"] = True
        notes.append("Only watching stopped. Aside keeps working and spending credits; cancel in the Aside app UI.")
    if notes:
        entry["note"] = " ".join(notes)
    return entry


# --- log ------------------------------------------------------------------------------


def next_step(targets: list, group: str | None, root: Path, cli: str, *, since=None) -> dict:
    pending = any(r.meta().get("state") not in TERMINAL_STATES for r in targets)
    target = ["--group", group] if group else ["--run", targets[0].run_id]
    argv = ["log" if pending else "result", *target, "--runs-dir", str(root)]
    if pending:
        argv += ["--follow"]
        if since is not None:
            argv += ["--since", str(since)]
    quoted_script = cli.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return {
        "command": f'python3 "{quoted_script}" {shlex.join(argv)}',
        "bash_timeout_ms": 600_000 if pending else 120_000,
        "run_in_background": pending,
    }


def log(root: Path, *, run: str | None, group: str | None, since: str, level: str, follow_: bool,
        follow_timeout: float, heartbeat: float | None, cli: str) -> int:
    targets = _targets(root, run, group)
    cursor = follow.follow(
        targets,
        level=level,
        since=since,
        follow=follow_,
        follow_timeout=follow_timeout,
        heartbeat=heartbeat,
    )
    group = None if run else (group or targets[0].meta().get("group"))
    print(json.dumps({
        "ok": True,
        "command": "log",
        "runs": [run_summary(r) for r in targets],
        "cursor": cursor,
        "next": next_step(targets, group, root, cli, since=cursor),
    }, ensure_ascii=False))
    return 0


# --- result ---------------------------------------------------------------------------


def result(root: Path, *, run: str | None, group: str | None, sources_only: bool) -> int:
    targets = _targets(root, run, group)
    entries = [_result_entry(r, sources_only) for r in targets]
    print(json.dumps({"ok": True, "command": "result", "runs": entries}, ensure_ascii=False))

    states = [e["state"] for e in entries]
    if any(s in FAILED_STATES for s in states):
        return outcome.EXIT_RUN_FAILED
    if any(s not in TERMINAL_STATES for s in states):
        return outcome.EXIT_RUN_FAILED
    if all(e.get("empty") for e in entries):
        return outcome.EXIT_EMPTY
    return 0


def _result_entry(run: runs.Run, sources_only: bool) -> dict:
    meta = run.meta()
    state = meta.get("state") or "unknown"
    path = run.path / "result.json"
    if not path.exists():
        return {
            "run_id": run.run_id,
            "state": state,
            "sources": [],
            "empty": True,
            "note": "no result yet" if state not in TERMINAL_STATES else "the run ended without writing a result",
            **run_summary(run),
        }
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RunFailed(f"run {run.run_id} has an unreadable result.json: {e}") from e
    result.update(run_summary(run))
    if sources_only:
        result.pop("answer", None)
    return result


# --- show -----------------------------------------------------------------------------


def show(root: Path, *, run: str | None, source: str | None, item: int | None) -> int:
    target = runs.resolve_run(root, run) if run else runs.latest_run(root)
    turn = evidence.turn_of(target)

    if item is not None:
        results = turn.tool_results()
        if not 0 <= item < len(results):
            raise ArgumentError(
                f"run {target.run_id} has {len(results)} tool result(s); no item {item}",
                fix="Index them with `log --level steps`.",
            )
        e = results[item]
        payload = {"ok": True, "command": "show", "run_id": target.run_id, "item": item,
                   "tool": e.tool_name, "content": e.content, "details": e.details}
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    sources = turn.sources()
    hit = None
    if str(source).isdigit():
        i = int(source)
        if 0 <= i < len(sources):
            hit = sources[i]
    else:
        hit = next((s for s in sources if source in s.ids or s.url == source), None)
    if hit is None:
        raise ArgumentError(
            f"run {target.run_id} has no source {source!r}",
            fix="List them with `result --sources-only`.",
            source_count=len(sources),
        )
    # The text Aside already fetched, not a fresh request: re-fetching would cost a round
    # trip and could return something different from what the answer was based on.
    payload = {"ok": True, "command": "show", "run_id": target.run_id,
               "source": {"url": hit.url, "title": hit.title, "id": hit.id, "ids": hit.ids, "opened": hit.opened},
               "content": turn.source_text(hit.url)}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


# --- stop -----------------------------------------------------------------------------


def stop(root: Path, *, run: str | None, group: str | None, every: bool) -> int:
    targets = _targets(root, run, group, every)
    stopped = []
    for run in targets:
        meta = run.meta()
        if (meta.get("state") or "") in TERMINAL_STATES:
            continue
        run.update_meta(stop_requested=True)
        # The supervisor notices the flag and writes `abandoned` itself. Give it a moment
        # to do so rather than racing it: two processes writing the terminal state is how
        # an `abandoned` gets overwritten by a stale `running` a moment later. Any terminal
        # state ends the wait -- a run that finished meanwhile keeps its result.
        if not _await_terminal(run, 1.5):
            _terminate(meta.get("supervisor_pid"))
            _terminate(meta.get("pid"))
            if (run.meta().get("state") or "") not in TERMINAL_STATES:
                run.update_meta(state="abandoned", reason="stop requested",
                                daemon_run_continues=True, finished_at=time.time())
        if run.meta().get("state") == "abandoned":
            stopped.append(run.run_id)
    payload = {
        "ok": True,
        "command": "stop",
        "stopped_watching": stopped,
        "daemon_run_continues": True,
        # The single most likely wrong assumption about this command, said where it is
        # read rather than only in the help text.
        "note": "This stopped the watching, not the run. Aside keeps working and keeps spending "
        "credits; cancel it in the Aside app UI.",
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _await_terminal(run: runs.Run, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (run.meta().get("state") or "") in TERMINAL_STATES:
            return True
        time.sleep(0.05)
    return False


def _terminate(pid: object) -> None:
    import os
    import signal

    if not isinstance(pid, int):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


# --- search and resume ----------------------------------------------------------------


def search(root: Path, prompts: list[str], *, wait: float, background: bool, label: str | None,
           effort: str | None, model: str | None, speed: str | None, timeout: float | None, cli: str) -> int:
    group = runs.new_group_name() if len(prompts) > 1 else None
    started = [_start_run(root, p, cli, label=label, effort=effort, model=model, speed=speed, timeout=timeout,
                          group=group) for p in prompts]
    return _await_and_report(started, "search", root, group, wait=0.0 if background else wait, cli=cli)


def resume(root: Path, target: str, prompt: str, *, wait: float, background: bool, label: str | None,
           effort: str | None, model: str | None, speed: str | None, timeout: float | None, cli: str) -> int:
    """Continue an existing Aside session, whether or not this tool created it.

    A run id is looked up first because it carries state we can check. Anything else is
    taken as a session id -- that is what makes a conversation started in the Aside app
    continuable from here. Either way the session itself is checked last: a run this tool
    abandoned stopped being watched, not working.
    """
    resumed_from = target
    try:
        run = runs.resolve_run(root, target)
    except ArgumentError:
        session_id = _resumable_session(target)
    else:
        meta = run.meta()
        state = meta.get("state") or "unknown"
        if state not in TERMINAL_STATES:
            raise ArgumentError(
                f"run {target} is still {state}; resume only continues a session that has stopped working",
                fix=f"Wait for it with `log --run {target} --follow`, or start a separate `search`.",
                state=state,
            )
        session_id = meta.get("session_id")
        if not session_id:
            raise ArgumentError(
                f"run {target} has no session to continue",
                fix="Its session was never correlated; start a fresh `search` instead.",
                state=state,
            )
        _resumable_session(session_id)

    new_run = _start_run(
        root, prompt, cli, label=label, effort=effort, model=model, speed=speed, timeout=timeout, group=None,
        resume_session_id=session_id, resumed_from=resumed_from,
    )
    return _await_and_report([new_run], "resume", root, None, wait=0.0 if background else wait, cli=cli)


def _resumable_session(session_id: str) -> str:
    """Verify a session exists on disk and has no turn in flight."""
    if not is_safe_id(session_id) or aside.session_transcript(session_id) is None:
        raise ArgumentError(
            f"no run and no Aside session called {session_id!r}",
            fix="List what exists with `sessions`. Aside deletes sessions within about a day.",
        )
    busy = aside.session_busy(session_id)
    if busy == "database":
        raise ArgumentError(
            f"session {session_id} is still working",
            fix="Wait for it to finish, or ask in the Aside app.",
            state="running",
        )
    if busy:
        raise ArgumentError(
            f"session {session_id} has a turn still in flight",
            fix="Wait for it to finish -- attaching to a live session waits for the current "
            "turn and cannot steer it.",
            state="running",
        )
    return session_id


def _start_run(root: Path, prompt: str, cli: str, *, label: str | None, effort: str | None, model: str | None,
               speed: str | None, timeout: float | None, group: str | None, **extra) -> runs.Run:
    # Fail before reserving anything if aside is not usable: a registry full of runs that
    # never started is worse than an error.
    aside.aside_bin()
    run = runs.create_run(
        root,
        label=label or _slug(prompt),
        group=group,
        prompt=prompt,
        effort=effort,
        model=model,
        speed=speed,
        watch_timeout=timeout,
        **extra,
    )
    run.update_meta(marker=marker_for(run.run_id))
    # Nothing is written after the spawn: the supervisor records its own pid, so the two
    # processes never both hold a stale copy of this file at once.
    supervisor.spawn(cli, run.path)
    return run


def _slug(prompt: str) -> str:
    words = "".join(ch if ch.isalnum() or ch in "-_ " else " " for ch in prompt).split()
    return "-".join(words[:4])[:40] or "run"


def _await_and_report(started: list, command: str, root: Path, group: str | None, *, wait: float, cli: str) -> int:
    deadline = time.time() + wait
    while time.time() < deadline:
        if all((r.meta().get("state") or "") in TERMINAL_STATES for r in started):
            break
        time.sleep(0.1)

    entries = [_entry(r) for r in started]
    payload = {"ok": True, "command": command, "runs": entries}
    if group:
        payload["group"] = group

    pending = [r for r, e in zip(started, entries) if e["state"] not in TERMINAL_STATES]
    if pending:
        payload["next"] = next_step(started, group, root, cli)
        payload["note"] = "Still running. Execute next, then follow its response; a watcher exiting does not mean the investigation finished."
    print(json.dumps(payload, ensure_ascii=False))
    return _exit_code(entries)


def _entry(run: runs.Run) -> dict:
    meta = run.meta()
    entry = {**run_summary(run), "label": meta.get("label")}
    for key in ("resumed_from", "session_id", "orphan_children"):
        if meta.get(key):
            entry[key] = meta[key]
    result_path = run.path / "result.json"
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return entry
        entry.update(
            {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "usage": result.get("usage", {}),
                "empty": result.get("empty", False),
            }
        )
        if result.get("note"):
            entry["note"] = " ".join(filter(None, (entry.get("note"), result["note"])))
    return entry


def _exit_code(entries: list[dict]) -> int:
    states = [e["state"] for e in entries]
    if any(s in FAILED_STATES for s in states):
        return outcome.EXIT_RUN_FAILED
    finished = [e for e in entries if e["state"] in TERMINAL_STATES]
    if finished and all(e.get("empty") for e in finished) and len(finished) == len(entries):
        return outcome.EXIT_EMPTY
    return 0
