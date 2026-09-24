"""`search` and `resume` -- starting work and, when it outlasts the wait, handing back
something that can be picked up again.

Synchronous by default because most searches finish in seconds and an inline answer is
what the caller actually wanted. The interesting half is what happens when one does not:
the run is left alive, and the reply carries `next` -- the literal command that will wake
the caller when it finishes, with the Bash timeout that command needs. A handle alone
would be a handle nobody comes back for.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import _errors
import _exec
import _registry
from _errors import ArgumentError, RunFailed
from _follow import TERMINAL_STATES
from _watch_cmds import next_step, run_summary


def dispatch(args) -> int:
    runs_root = _registry.resolve_runs_dir(args.runs_dir)
    if args.command == "search":
        return _search(args, runs_root)
    return _resume(args, runs_root)


def _search(args, runs_root: Path) -> int:
    prompts = list(args.prompt)
    group = _registry.new_group_name() if len(prompts) > 1 else None
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
        run = _registry.resolve_run(runs_root, target)
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
    import _store

    home = _store.aside_home()
    if not _errors.is_safe_id(session_id) or _store.session_dir(home, session_id) is None:
        raise ArgumentError(
            f"no run and no Aside session called {session_id!r}",
            fix="List what exists with `sessions`. Aside deletes sessions within about a day.",
        )
    row = _store.db_session_row(home, session_id)
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
    import _events

    d = _store.session_dir(home, session_id)
    events, _ = _events.read_events(d / "messages.jsonl") if d else ([], 0)
    if events and not (events[-1].kind == "assistant" and events[-1].stop_reason != "toolUse"):
        raise ArgumentError(
            f"session {session_id} has a turn still in flight",
            fix="Wait for it to finish -- attaching to a live session waits for the current "
            "turn and cannot steer it.",
            state="running",
        )
    return session_id


def _start_run(runs_root: Path, prompt: str, args, *, group: str | None, **extra) -> _registry.Run:
    # Fail before reserving anything if aside is not usable: a registry full of runs that
    # never started is worse than an error.
    _exec.aside_bin()
    run = _registry.create_run(
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
    run.update_meta(marker=_registry.marker_for(run.run_id))
    # Nothing is written after the spawn: the supervisor records its own pid, so the two
    # processes never both hold a stale copy of this file at once.
    _exec.spawn_supervisor(run.path)
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


def _entry(run: _registry.Run) -> dict:
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
    if any(s in ("failed", "abandoned") for s in states):
        return _errors.EXIT_RUN_FAILED
    finished = [e for e in entries if e["state"] in TERMINAL_STATES]
    if finished and all(e.get("empty") for e in finished) and len(finished) == len(entries):
        return _errors.EXIT_EMPTY
    return 0
