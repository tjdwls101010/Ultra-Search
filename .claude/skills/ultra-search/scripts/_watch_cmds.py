"""`status`, `log`, `result`, `show`, `stop` -- looking at runs that are already going.

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

import _errors
import _evidence
import _follow
import _registry
import _store
from _errors import ArgumentError, RunFailed


def dispatch(args) -> int:
    runs_root = _registry.resolve_runs_dir(args.runs_dir)
    return {
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
    rows = _store.session_summaries(limit=scan)
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
    return 0 if rows else _errors.EXIT_EMPTY


def _targets(args, runs_root: Path) -> list:
    if getattr(args, "all", False):
        runs = _registry.all_runs(runs_root)
        if not runs:
            raise ArgumentError(f"no runs under {runs_root}", fix="Start one with `search`.")
        return runs
    if getattr(args, "run", None):
        return [_registry.resolve_run(runs_root, args.run)]
    if getattr(args, "group", None):
        return _registry.resolve_group(runs_root, args.group)
    return _registry.latest_group(runs_root)


# --- status ---------------------------------------------------------------------------


def _status(args, runs_root: Path) -> int:
    now = time.time()
    runs = _targets(args, runs_root)
    entries = [_status_entry(r, now, args.stall_after) for r in runs]
    print(json.dumps({"ok": True, "command": "status", "runs": entries}, ensure_ascii=False))
    return _errors.EXIT_RUN_FAILED if any(e["state"] in ("failed", "abandoned") for e in entries) else 0


def _status_entry(run: _registry.Run, now: float, stall_after: float) -> dict:
    meta = run.meta()
    # This run's turn and its children: a resumed run's transcript also holds earlier turns,
    # whose children and tokens belong to the runs that asked for them.
    turn = _evidence.turn_of(run)
    children = turn.children
    last = float(meta.get("last_activity_at") or 0)
    # The supervisor records activity as it syncs, but a status call between two syncs
    # would read a stale number -- so the files themselves get the last word.
    for p in [run.stdout_path, run.session_transcript, *run.child_transcripts()]:
        try:
            last = max(last, p.stat().st_mtime)
        except OSError:
            pass
    idle = round(now - last, 1) if last else None
    state = meta.get("state") or "unknown"
    live = state not in _follow.TERMINAL_STATES
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
        susp = _store.db_suspension(None, meta["session_id"])
        if susp:
            entry["suspension"] = susp
    if entry["possibly_stalled"]:
        entry["note"] = (
            "idle beyond --stall-after. Nothing was stopped: a long investigation looks like this too. "
            "Check `log`, and cancel in the Aside app if it really is stuck."
        )
    return entry


def run_summary(run: _registry.Run) -> dict:
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
    pending = any(r.meta().get("state") not in _follow.TERMINAL_STATES for r in runs)
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
    cursor = _follow.follow(
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
    if any(s in ("failed", "abandoned") for s in states):
        return _errors.EXIT_RUN_FAILED
    if any(s not in _follow.TERMINAL_STATES for s in states):
        return _errors.EXIT_RUN_FAILED
    if all(e.get("empty") for e in entries):
        return _errors.EXIT_EMPTY
    return 0


def _result_entry(run: _registry.Run, sources_only: bool) -> dict:
    meta = run.meta()
    state = meta.get("state") or "unknown"
    path = run.path / "result.json"
    if not path.exists():
        return {
            "run_id": run.run_id,
            "state": state,
            "sources": [],
            "empty": True,
            "note": "no result yet" if state not in _follow.TERMINAL_STATES else "the run ended without writing a result",
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
    run = _registry.resolve_run(runs_root, args.run) if args.run else _registry.latest_run(runs_root)
    turn = _evidence.turn_of(run)

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
        if (meta.get("state") or "") in _follow.TERMINAL_STATES:
            continue
        run.update_meta(stop_requested=True)
        # The supervisor notices the flag and writes `abandoned` itself. Give it a moment
        # to do so rather than racing it: two processes writing the terminal state is how
        # an `abandoned` gets overwritten by a stale `running` a moment later. Any terminal
        # state ends the wait -- a run that finished meanwhile keeps its result.
        if not _await_terminal(run, 1.5):
            _terminate(meta.get("supervisor_pid"))
            _terminate(meta.get("pid"))
            if (run.meta().get("state") or "") not in _follow.TERMINAL_STATES:
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


def _await_terminal(run: _registry.Run, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (run.meta().get("state") or "") in _follow.TERMINAL_STATES:
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
