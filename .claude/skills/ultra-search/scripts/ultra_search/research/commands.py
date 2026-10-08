"""`search` and `resume` -- starting work and, when it outlasts the wait, handing back
something that can be picked up again.

Synchronous by default because most searches finish in seconds and an inline answer is
what the caller actually wanted. The interesting half is what happens when one does not:
the run is left alive, and the reply carries `next` -- the literal command that will wake
the caller when it finishes, with the Bash timeout that command needs. A handle alone
would be a handle nobody comes back for.

`result`, `log`, `show`, `sessions` -- looking at runs that are already going.

These are split by the question each answers. What did it conclude, waiting for it if asked (`result`, the one wait, which also settles a run whose supervisor is gone -- nothing else would ever end it). Why did it choose a source, or come back thin (`log`, read once, after the fact). What exactly did it read (`show`).
"""
from __future__ import annotations

import json
import os
import shlex
import time
from pathlib import Path

from ultra_search import aside, outcome, runs
from ultra_search.ids import is_safe_id, normal
from ultra_search.outcome import ArgumentError, AsideUnavailable, Reply, RunFailed, RunNotFound
from ultra_search.research import evidence, follow, supervisor
from ultra_search.research.marker import marker_for, run_id_in
from ultra_search.research.states import FAILED_STATES, TERMINAL_STATES


def sessions(*, limit: int, mine: bool, search: str | None) -> Reply:
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
    return Reply(
        {
            "ok": True,
            "command": "sessions",
            "sessions": rows,
            "note": "resume any of these by session_id. Aside removes old sessions on its own schedule.",
        },
        outcome.OK if rows else outcome.EMPTY,
    )


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


def _targets(root: Path, run: str | None, group: str | None) -> list:
    if run:
        return [runs.resolve_run(root, run)]
    if group:
        return runs.resolve_group(root, group)
    return runs.latest_group(root)


def run_summary(run: runs.Run) -> dict:
    meta = run.meta()
    entry = {"run_id": run.run_id, "state": meta.get("state") or "unknown"}
    notes = []
    if meta.get("orphan_children"):
        entry["orphan_children"] = meta["orphan_children"]
        notes.append("Partial snapshot: these children were still running; late results are not collected automatically.")
    if entry["state"] == "abandoned":
        entry["daemon_run_continues"] = True
        why = f" ({meta['reason']})" if meta.get("reason") else ""
        notes.append(f"Only watching stopped{why}. Aside keeps working and spending credits; cancel in the Aside app UI.")
    if notes:
        entry["note"] = " ".join(notes)
    return entry


# --- log ------------------------------------------------------------------------------


def log(root: Path, *, run: str | None, group: str | None, level: str) -> Reply:
    targets = _targets(root, run, group)
    follow.print_log(targets, level=level)
    return Reply({"ok": True, "command": "log", "runs": [run_summary(r) for r in targets]})


# --- result ---------------------------------------------------------------------------


#: How long the wait `next` hands back lasts: under the Bash tool's 600-second ceiling, with room to answer.
WAIT = 570
#: How long a reserved run may go without its supervisor claiming it before it is taken for one that never will.
STARTUP_GRACE = 60.0


def next_step(targets: list, group: str | None, root: Path, cli: str) -> dict:
    """The one action that waits for these runs and returns their result."""
    target = ["--group", group] if group else ["--run", targets[0].run_id]
    argv = ["result", *target, "--runs-dir", str(root), "--wait", str(WAIT)]
    quoted_script = cli.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return {"command": f'uv run "{quoted_script}" {shlex.join(argv)}', "bash_timeout_ms": 600_000, "run_in_background": True}


def result(root: Path, *, run: str | None, group: str | None, sources: bool, wait: float, cli: str) -> Reply:
    targets = _targets(root, run, group)
    group = None if run else (group or targets[0].meta().get("group"))
    for r in targets:
        _settle_unwatched(r)
    if wait:
        follow.wait(targets, seconds=wait, check=_settle_unwatched)
    entries = [_run_entry(r, sources=sources) for r in targets]
    return Reply(_envelope("result", targets, entries, group, root, cli), _outcome(entries))


def _settle_unwatched(run: runs.Run) -> None:
    """End a run nothing is watching any more, since nothing else ever will: decided under the meta lock, so a supervisor that settles it at the same moment wins.

    A result on disk is the run's even when its supervisor died before recording it -- with what it says of children still running. A supervisor that is gone abandons the run; so does one that never claimed it within the grace period.
    """
    saved_path = run.path / "result.json"

    def decide(meta: dict) -> dict | None:
        if (meta.get("state") or "") in TERMINAL_STATES:
            return None
        saved = _saved_result(run) if saved_path.exists() else None
        if saved and saved.get("state") in TERMINAL_STATES:
            return {k: saved[k] for k in ("state", "children", "orphan_children", "empty", "exit_code") if k in saved}
        pid = meta.get("supervisor_pid")
        if isinstance(pid, int) and not _alive(pid):
            return _abandoned("the supervisor is gone")
        if meta.get("state") == "starting" and not pid and time.time() - float(meta.get("created_at") or 0) > STARTUP_GRACE:
            return _abandoned("the supervisor never started")
        return None

    run.update_meta_if(decide)


def _abandoned(reason: str) -> dict:
    return {"state": "abandoned", "reason": reason, "daemon_run_continues": True, "finished_at": time.time()}


def _alive(pid: int) -> bool:
    # 성진: pid 재사용은 확인하지 않는다(감독자가 죽고 같은 pid를 다른 프로세스가 받으면 살아 있는 것으로 본다); 오판이 보이면 감독자 시작 시각을 함께 기록해 대조한다.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _envelope(command: str, targets: list, entries: list[dict], group: str | None, root: Path, cli: str) -> dict:
    """What a search, resume or result reply opens with: the group, and while any run is still
    going, the one action that watches it."""
    payload = {"ok": True, "command": command}
    if group:
        payload["group"] = group
    if any(e["state"] not in TERMINAL_STATES for e in entries):
        payload["note"] = ("Still running. Execute next, then follow its response; a wait that ends does not mean "
                           "the investigation finished.")
        payload["next"] = next_step(targets, group, root, cli)
    payload["runs"] = entries
    return payload


def _saved_result(run: runs.Run) -> dict | None:
    path = run.path / "result.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RunFailed(f"run {run.run_id} has an unreadable result.json: {e}") from e


def _run_entry(run: runs.Run, *, sources: bool = False) -> dict:
    """One run as search, resume and result report it: the summary that decides what to do
    next, then the answer and the sources it opened -- or, with ``sources``, every source --
    then the copies of the files its agent saved, then where the whole result is saved.

    Sources are numbered by their place in the saved result, the numbering `show --source`
    uses, so an opened source keeps its number among all of them.
    """
    summary = run_summary(run)
    saved = _saved_result(run)
    entry = {"run_id": run.run_id, "state": summary["state"]}
    notes = [summary.get("note")]
    if saved is None:
        entry["empty"] = True
        notes.append("no result yet" if summary["state"] not in TERMINAL_STATES else "the run ended without writing a result")
    else:
        listed = saved.get("sources") or []
        entry["empty"] = bool(saved.get("empty"))
        entry["sources_total"] = len(listed)
        entry["sources_opened"] = sum(1 for s in listed if s.get("opened"))
        notes.append(saved.get("note"))
    entry.update({k: v for k, v in summary.items() if k not in ("run_id", "state", "note")})
    if any(notes):
        entry["note"] = " ".join(filter(None, notes))
    if saved is None:
        return entry
    numbered = list(enumerate(saved.get("sources") or []))
    if sources:
        entry["sources"] = [{"n": n, "url": s.get("url"), "title": s.get("title") or "", "opened": bool(s.get("opened"))}
                            for n, s in numbered]
    else:
        entry["answer"] = saved.get("answer", "")
        entry["opened_sources"] = [{"n": n, "url": s.get("url"), "title": s.get("title") or ""}
                                   for n, s in numbered if s.get("opened")]
    if saved.get("artifacts"):
        entry["artifacts"] = saved["artifacts"]
    entry["result_path"] = str(run.path / "result.json")
    return entry


# --- show -----------------------------------------------------------------------------


def show(root: Path, *, run: str | None, source: str | None, item: int | None) -> Reply:
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
        return Reply(payload)

    # A finished run's sources are the saved ones, numbered as `result` numbers them. Before the
    # result is written -- still running, or abandoned -- they come from its transcript copy.
    saved = _saved_result(target)
    listed = ([{"url": s.get("url"), "title": s.get("title") or "", "id": s.get("id") or "", "ids": s.get("ids") or [],
                "opened": bool(s.get("opened"))} for s in saved.get("sources") or []] if saved is not None else
              [{"url": s.url, "title": s.title, "id": s.id, "ids": s.ids, "opened": s.opened} for s in turn.sources()])
    hit = None
    if str(source).isdigit():
        i = int(source)
        if 0 <= i < len(listed):
            hit = listed[i]
    else:
        hit = next((s for s in listed if source in s["ids"] or s["url"] == source), None)
    if hit is None:
        raise ArgumentError(
            f"run {target.run_id} has no source {source!r}",
            fix="List them with `result --sources`.",
            source_count=len(listed),
        )
    # The text Aside already fetched, not a fresh request: re-fetching would cost a round
    # trip and could return something different from what the answer was based on.
    payload = {"ok": True, "command": "show", "run_id": target.run_id, "source": hit,
               "content": turn.source_text(hit["url"]) if turn.observed else ""}
    if not turn.observed:
        payload["note"] = ("no page text: this run's session transcript was never read, so all it has is what "
                           "`aside exec` printed on stdout")
    return Reply(payload)


# --- search and resume ----------------------------------------------------------------


def search(root: Path, prompts: list[str], *, wait: float, background: bool, label: str | None,
           effort: str | None, model: str | None, speed: str | None, cli: str) -> Reply:
    group = runs.new_group_name() if len(prompts) > 1 else None
    _require_aside()
    started = [_start_run(root, p, cli, label=label, effort=effort, model=model, speed=speed, group=group)
               for p in prompts]
    return _await_and_report(started, "search", root, group, wait=0.0 if background else wait, cli=cli)


def resume(root: Path, target: str, prompt: str, *, wait: float, background: bool, label: str | None,
           cli: str) -> Reply:
    """Continue an existing Aside session, whether or not this tool created it.

    A run id is looked up first because it carries state we can check. Anything else is
    taken as a session id -- that is what makes a conversation started in the Aside app
    continuable from here. Either way the session itself is checked last: a run this tool
    abandoned stopped being watched, not working.
    """
    try:
        run = runs.resolve_run(root, target)
    except RunNotFound:
        session_id = _resumable_session(target)
        resumed_from = session_id
    else:
        resumed_from = run.run_id
        meta = run.meta()
        state = meta.get("state") or "unknown"
        if state not in TERMINAL_STATES:
            raise ArgumentError(
                f"run {run.run_id} is still {state}; resume only continues a session that has stopped working",
                fix=f"Wait for it with `result --run {run.run_id} --wait {WAIT}`, or start a separate `search`.",
                state=state,
            )
        session_id = meta.get("session_id")
        if not session_id:
            raise ArgumentError(
                f"run {run.run_id} has no session to continue",
                fix="Its session was never correlated; start a fresh `search` instead.",
                state=state,
            )
        _resumable_session(session_id)

    _require_aside()
    new_run = _start_run(
        root, prompt, cli, label=label, effort=None, model=None, speed=None, group=None,
        resume_session_id=session_id, resumed_from=resumed_from,
    )
    return _await_and_report([new_run], "resume", root, None, wait=0.0 if background else wait, cli=cli)


def _resumable_session(session_id: str) -> str:
    """Verify a session exists on disk and has no turn in flight."""
    if not is_safe_id(session_id) or aside.session_transcript(session_id) is None:
        raise ArgumentError(
            f"no run and no Aside session called {session_id!r}",
            fix="List what exists with `sessions`; Aside removes old sessions on its own schedule.",
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


def _require_aside() -> None:
    """Fail before reserving anything if Aside cannot take the work: a registry full of runs
    that never started is worse than an error, and with the app closed `aside exec` fails in a
    way that would be recorded as a failed investigation, its error text as the answer."""
    aside.aside_bin()
    daemon = aside.daemon_status()
    if not daemon["ok"]:
        raise AsideUnavailable(f"the Aside daemon is not ready: {daemon['detail']}")


def _start_run(root: Path, prompt: str, cli: str, *, label: str | None, effort: str | None, model: str | None,
               speed: str | None, group: str | None, **extra) -> runs.Run:
    run = runs.create_run(
        root,
        label=label or _slug(prompt),
        group=group,
        prompt=prompt,
        effort=effort,
        model=model,
        speed=speed,
        **extra,
    )
    run.update_meta(marker=marker_for(run.run_id))
    # Nothing is written after the spawn: the supervisor records its own pid, so the two
    # processes never both hold a stale copy of this file at once.
    supervisor.spawn(cli, run.path)
    return run


def _slug(prompt: str) -> str:
    words = "".join(ch if ch.isalnum() or ch in "-_ " else " " for ch in normal(prompt)).split()
    return "-".join(words[:4])[:40] or "run"


def _await_and_report(started: list, command: str, root: Path, group: str | None, *, wait: float, cli: str) -> Reply:
    deadline = time.time() + wait
    while time.time() < deadline:
        if all((r.meta().get("state") or "") in TERMINAL_STATES for r in started):
            break
        time.sleep(0.1)

    entries = [_run_entry(r) for r in started]
    return Reply(_envelope(command, started, entries, group, root, cli), _outcome(entries))


def _outcome(entries: list[dict]) -> str:
    states = [e["state"] for e in entries]
    if any(s in FAILED_STATES for s in states):
        return outcome.FAILED
    finished = [e for e in entries if e["state"] in TERMINAL_STATES]
    if finished and all(e.get("empty") for e in finished) and len(finished) == len(entries):
        return outcome.EMPTY
    return outcome.OK
