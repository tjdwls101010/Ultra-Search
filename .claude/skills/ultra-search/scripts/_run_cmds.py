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
import shlex
import sys
import time
from pathlib import Path

import _errors
import _exec
import _registry
from _errors import ArgumentError, RunFailed
from _follow import TERMINAL_STATES

SCRIPT = Path(__file__).resolve().parent / "ultra_search.py"
#: Comfortably above `log --follow`'s own 570s default, so Bash is never the thing that
#: cuts the watch short.
FOLLOW_BASH_TIMEOUT_MS = 600_000


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
    taken as a session id and verified against the sessions on disk -- that is what makes
    a conversation started in the Aside app continuable from here.
    """
    target = args.target
    resumed_from = target
    try:
        run = _registry.resolve_run(runs_root, target)
    except ArgumentError:
        session_id = _external_session(target)
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

    new_run = _start_run(
        runs_root, args.prompt, args, group=None,
        resume_session_id=session_id, resumed_from=resumed_from,
    )
    return _await_and_report([new_run], args, runs_root, None)


def _external_session(session_id: str) -> str:
    """Verify a session id that did not come from this tool's own registry."""
    import _store

    home = _store.aside_home()
    if _store.session_dir(home, session_id) is None:
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
        payload["next"] = _next_step(pending, group, args.runs_dir)
        payload["note"] = (
            "still running -- the run was left alive. Run `next.command` as a background Bash call "
            "with that timeout; it exits when the run finishes, which is what notifies you."
        )
    print(json.dumps(payload, ensure_ascii=False))
    return _exit_code(entries)


def _next_step(pending: list, group: str | None, runs_dir: str | None) -> dict:
    target = ["--group", group] if group and len(pending) > 1 else ["--run", pending[0].run_id]
    argv = [sys.executable, str(SCRIPT), "log", *target, "--follow"]
    if runs_dir:
        argv += ["--runs-dir", str(runs_dir)]
    collect = [sys.executable, str(SCRIPT), "result", *target]
    if runs_dir:
        collect += ["--runs-dir", str(runs_dir)]
    return {
        "command": " ".join(shlex.quote(a) for a in argv),
        "bash_timeout_ms": FOLLOW_BASH_TIMEOUT_MS,
        "run_in_background": True,
        "then": " ".join(shlex.quote(a) for a in collect),
    }


def _entry(run: _registry.Run) -> dict:
    meta = run.meta()
    entry = {
        "run_id": run.run_id,
        "state": meta.get("state") or "unknown",
        "label": meta.get("label"),
    }
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
            entry["note"] = result["note"]
    return entry


def _exit_code(entries: list[dict]) -> int:
    states = [e["state"] for e in entries]
    if any(s in ("failed", "abandoned") for s in states):
        return _errors.EXIT_RUN_FAILED
    finished = [e for e in entries if e["state"] in TERMINAL_STATES]
    if finished and all(e.get("empty") for e in finished) and len(finished) == len(entries):
        return _errors.EXIT_EMPTY
    return 0
