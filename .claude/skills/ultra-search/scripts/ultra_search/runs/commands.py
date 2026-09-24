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

from ultra_search import contract
from ultra_search.aside import process, sessions, transcript
from ultra_search.contract import FAILED_STATES, TERMINAL_STATES, ArgumentError, RunFailed
from ultra_search.runs import evidence, follow, registry, supervisor


def dispatch(args) -> int:
    runs_root = registry.resolve_runs_dir(args.runs_dir)
    return {
        "search": _search,
        "resume": _resume,
        "status": _status,
        "log": _log,
        "result": _result,
        "show": _show,
        "stop": _stop,
        "sessions": _sessions,
    }[args.command](args, runs_root)


def _sessions(args, runs_root: Path) -> int:
    # A filter searches everything and then takes the first N matches. Reading a page first
    # and filtering it afterwards reports "no match" for a session that is simply further
    # down the list, which is indistinguishable from its not existing.
    scan = 10_000 if (args.mine or args.search) else args.limit
    rows = sessions.session_summaries(limit=scan)
    if args.mine:
        rows = [r for r in rows if r["started_by_ultra_search"]]
    if args.search:
        needle = args.search.lower()
        rows = [r for r in rows if needle in (r["prompt"] or "").lower()]
    rows = rows[: args.limit]
    print(json.dumps(
        {
            "ok": True,
            "command": "sessions",
            "sessions": rows,
            "note": "resume any of these by session_id. Aside deletes sessions within about a day.",
        },
        ensure_ascii=False,
    ))
    return 0 if rows else contract.EXIT_EMPTY


def _targets(args, runs_root: Path) -> list:
    if getattr(args, "all", False):
        runs = registry.all_runs(runs_root)
        if not runs:
            raise ArgumentError(f"no runs under {runs_root}", fix="Start one with `search`.")
        return runs
    if getattr(args, "run", None):
        return [registry.resolve_run(runs_root, args.run)]
    if getattr(args, "group", None):
        return registry.resolve_group(runs_root, args.group)
    return registry.latest_group(runs_root)


# --- status ---------------------------------------------------------------------------


def _status(args, runs_root: Path) -> int:
    now = time.time()
    runs = _targets(args, runs_root)
    entries = [_status_entry(r, now, args.stall_after) for r in runs]
    print(json.dumps({"ok": True, "command": "status", "runs": entries}, ensure_ascii=False))
    return contract.EXIT_RUN_FAILED if any(e["state"] in contract.FAILED_STATES for e in entries) else 0


def _status_entry(run: registry.Run, now: float, stall_after: float) -> dict:
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
    live = state not in contract.TERMINAL_STATES
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
        susp = sessions.db_suspension(None, meta["session_id"])
        if susp:
            entry["suspension"] = susp
    if entry["possibly_stalled"]:
        entry["note"] = (
            "idle beyond --stall-after. Nothing was stopped: a long investigation looks like this too. "
            "Check `log`, and cancel in the Aside app if it really is stuck."
        )
    return entry


def run_summary(run: registry.Run) -> dict:
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


def next_step(runs: list, group: str | None, runs_root: Path, script: str, *, since=None) -> dict:
    pending = any(r.meta().get("state") not in contract.TERMINAL_STATES for r in runs)
    target = ["--group", group] if group else ["--run", runs[0].run_id]
    argv = ["log" if pending else "result", *target, "--runs-dir", str(runs_root)]
    if pending:
        argv += ["--follow"]
        if since is not None:
            argv += ["--since", str(since)]
    quoted_script = script.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return {
        "command": f'python3 "{quoted_script}" {shlex.join(argv)}',
        "bash_timeout_ms": 600_000 if pending else 120_000,
        "run_in_background": pending,
    }


def _log(args, runs_root: Path) -> int:
    runs = _targets(args, runs_root)
    cursor = follow.follow(
        runs,
        level=args.level,
        since=args.since,
        follow=args.follow,
        follow_timeout=args.follow_timeout,
        heartbeat=args.heartbeat,
    )
    group = None if args.run else (args.group or runs[0].meta().get("group"))
    print(json.dumps({
        "ok": True,
        "command": "log",
        "runs": [run_summary(r) for r in runs],
        "cursor": cursor,
        "next": next_step(runs, group, runs_root, args.script_path, since=cursor),
    }, ensure_ascii=False))
    return 0


# --- result ---------------------------------------------------------------------------


def _result(args, runs_root: Path) -> int:
    runs = _targets(args, runs_root)
    entries = [_result_entry(r, args.sources_only) for r in runs]
    if len(entries) == 1:
        payload = {"ok": True, "command": "result", **entries[0]}
    else:
        payload = {"ok": True, "command": "result", "runs": entries}
    print(json.dumps(payload, ensure_ascii=False))

    states = [e["state"] for e in entries]
    if any(s in contract.FAILED_STATES for s in states):
        return contract.EXIT_RUN_FAILED
    if any(s not in contract.TERMINAL_STATES for s in states):
        return contract.EXIT_RUN_FAILED
    if all(e.get("empty") for e in entries):
        return contract.EXIT_EMPTY
    return 0


def _result_entry(run: registry.Run, sources_only: bool) -> dict:
    meta = run.meta()
    state = meta.get("state") or "unknown"
    path = run.path / "result.json"
    if not path.exists():
        return {
            "run_id": run.run_id,
            "state": state,
            "sources": [],
            "empty": True,
            "note": "no result yet" if state not in contract.TERMINAL_STATES else "the run ended without writing a result",
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


def _show(args, runs_root: Path) -> int:
    run = registry.resolve_run(runs_root, args.run) if args.run else registry.latest_run(runs_root)
    turn = evidence.turn_of(run)

    if args.item is not None:
        results = turn.tool_results()
        if not 0 <= args.item < len(results):
            raise ArgumentError(
                f"run {run.run_id} has {len(results)} tool result(s); no item {args.item}",
                fix="Index them with `log --level steps`.",
            )
        e = results[args.item]
        payload = {"ok": True, "command": "show", "run_id": run.run_id, "item": args.item,
                   "tool": e.tool_name, "content": e.content, "details": e.details}
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    sources = turn.sources()
    hit = None
    if str(args.source).isdigit():
        i = int(args.source)
        if 0 <= i < len(sources):
            hit = sources[i]
    else:
        hit = next((s for s in sources if args.source in s.ids or s.url == args.source), None)
    if hit is None:
        raise ArgumentError(
            f"run {run.run_id} has no source {args.source!r}",
            fix="List them with `result --sources-only`.",
            source_count=len(sources),
        )
    # The text Aside already fetched, not a fresh request: re-fetching would cost a round
    # trip and could return something different from what the answer was based on.
    payload = {"ok": True, "command": "show", "run_id": run.run_id,
               "source": {"url": hit.url, "title": hit.title, "id": hit.id, "ids": hit.ids, "opened": hit.opened},
               "content": turn.source_text(hit.url)}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


# --- stop -----------------------------------------------------------------------------


def _stop(args, runs_root: Path) -> int:
    runs = _targets(args, runs_root)
    stopped = []
    for run in runs:
        meta = run.meta()
        if (meta.get("state") or "") in contract.TERMINAL_STATES:
            continue
        run.update_meta(stop_requested=True)
        # The supervisor notices the flag and writes `abandoned` itself. Give it a moment
        # to do so rather than racing it: two processes writing the terminal state is how
        # an `abandoned` gets overwritten by a stale `running` a moment later. Any terminal
        # state ends the wait -- a run that finished meanwhile keeps its result.
        if not _await_terminal(run, 1.5):
            _terminate(meta.get("supervisor_pid"))
            _terminate(meta.get("pid"))
            if (run.meta().get("state") or "") not in contract.TERMINAL_STATES:
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


def _await_terminal(run: registry.Run, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (run.meta().get("state") or "") in contract.TERMINAL_STATES:
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


def _search(args, runs_root: Path) -> int:
    prompts = list(args.prompt)
    group = registry.new_group_name() if len(prompts) > 1 else None
    runs = [_start_run(runs_root, p, args, group=group) for p in prompts]
    return _await_and_report(runs, args, runs_root, group)


def _resume(args, runs_root: Path) -> int:
    """Continue an existing Aside session, whether or not this tool created it.

    A run id is looked up first because it carries state we can check. Anything else is
    taken as a session id -- that is what makes a conversation started in the Aside app
    continuable from here. Either way the session itself is checked last: a run this tool
    abandoned stopped being watched, not working.
    """
    target = args.target
    resumed_from = target
    try:
        run = registry.resolve_run(runs_root, target)
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
        runs_root, args.prompt, args, group=None,
        resume_session_id=session_id, resumed_from=resumed_from,
    )
    return _await_and_report([new_run], args, runs_root, None)


def _resumable_session(session_id: str) -> str:
    """Verify a session exists on disk and has no turn in flight."""
    home = sessions.aside_home()
    if not contract.is_safe_id(session_id) or sessions.session_dir(home, session_id) is None:
        raise ArgumentError(
            f"no run and no Aside session called {session_id!r}",
            fix="List what exists with `sessions`. Aside deletes sessions within about a day.",
        )
    row = sessions.db_session_row(home, session_id)
    if row and str(row.get("status") or "") == "running":
        raise ArgumentError(
            f"session {session_id} is still working",
            fix="Wait for it to finish, or ask in the Aside app.",
            state="running",
        )

    # The database is not enough on its own: an ephemeral CLI session has no row there at
    # all, so a busy one would pass the check above by simply not existing in it. The
    # transcript is the surface that always exists -- a turn that has not reached a
    # terminal assistant message is a turn still in flight.
    d = sessions.session_dir(home, session_id)
    events, _ = transcript.read_events(d / "messages.jsonl") if d else ([], 0)
    if events and not (events[-1].kind == "assistant" and events[-1].stop_reason != "toolUse"):
        raise ArgumentError(
            f"session {session_id} has a turn still in flight",
            fix="Wait for it to finish -- attaching to a live session waits for the current "
            "turn and cannot steer it.",
            state="running",
        )
    return session_id


def _start_run(runs_root: Path, prompt: str, args, *, group: str | None, **extra) -> registry.Run:
    # Fail before reserving anything if aside is not usable: a registry full of runs that
    # never started is worse than an error.
    process.aside_bin()
    run = registry.create_run(
        runs_root,
        label=getattr(args, "label", None) or _slug(prompt),
        group=group,
        prompt=prompt,
        effort=getattr(args, "effort", None),
        model=getattr(args, "model", None),
        speed=getattr(args, "speed", None),
        watch_timeout=getattr(args, "timeout", None),
        **extra,
    )
    run.update_meta(marker=registry.marker_for(run.run_id))
    # Nothing is written after the spawn: the supervisor records its own pid, so the two
    # processes never both hold a stale copy of this file at once.
    supervisor.spawn(run.path)
    return run


def _slug(prompt: str) -> str:
    words = "".join(ch if ch.isalnum() or ch in "-_ " else " " for ch in prompt).split()
    return "-".join(words[:4])[:40] or "run"


def _await_and_report(runs: list, args, runs_root: Path, group: str | None) -> int:
    wait = 0.0 if getattr(args, "background", False) else float(getattr(args, "wait", 100.0))
    deadline = time.time() + wait
    while time.time() < deadline:
        if all((r.meta().get("state") or "") in TERMINAL_STATES for r in runs):
            break
        time.sleep(0.1)

    entries = [_entry(r) for r in runs]
    payload = {"ok": True, "command": args.command, "runs": entries}
    if group:
        payload["group"] = group

    pending = [r for r, e in zip(runs, entries) if e["state"] not in TERMINAL_STATES]
    if pending:
        payload["next"] = next_step(runs, group, runs_root, args.script_path)
        payload["note"] = "Still running. Execute next, then follow its response; a watcher exiting does not mean the investigation finished."
    print(json.dumps(payload, ensure_ascii=False))
    return _exit_code(entries)


def _entry(run: registry.Run) -> dict:
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
        return contract.EXIT_RUN_FAILED
    finished = [e for e in entries if e["state"] in TERMINAL_STATES]
    if finished and all(e.get("empty") for e in finished) and len(finished) == len(entries):
        return contract.EXIT_EMPTY
    return 0
