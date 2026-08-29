"""_supervisor: from "spawn aside" to a result.json somebody can read.

The seam is the fake aside binary plus a throwaway ~/.aside in, a run directory out.
The supervisor is run in-process here (`supervise(run)`) rather than detached, because
the thing under test is the state machine, not the fork.

The states exist because completion is genuinely ambiguous. The process exiting is the
only hard signal -- killing it does not stop the daemon-side run, silence is not an
ending, and the session may never be correlated at all -- so each way that can go wrong
gets its own state instead of being flattened into "done".
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

import _registry
import _supervisor


def start(runs_dir: Path, prompt: str = "질문", **meta) -> _registry.Run:
    run = _registry.create_run(runs_dir, label="t", **meta)
    run.update_meta(prompt=prompt, marker=_registry.marker_for(run.run_id))
    return run


def run_to_completion(run: _registry.Run, **kw) -> dict:
    _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=kw.pop("settle", 0.5), **kw)
    return run.meta()


# --- the ordinary path --------------------------------------------------------------


def test_a_simple_search_completes_with_answer_sources_and_usage(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)

    meta = run_to_completion(run)

    assert meta["state"] == "completed"
    result = json.loads((run.path / "result.json").read_text())
    assert "Answer" in result["answer"]
    assert [s["url"] for s in result["sources"]] == ["https://example.org/a", "https://example.org/b"]
    assert result["usage"]["total_tokens"] > 0


def test_the_answer_has_its_citation_resolved(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)

    run_to_completion(run)

    result = json.loads((run.path / "result.json").read_text())
    assert "https://example.org/a" in result["answer"]


def test_the_transcript_is_copied_out_of_the_session_directory(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Aside deletes CLI sessions within about a day. A run whose evidence lives only in
    the session directory has no evidence next week."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)

    run_to_completion(run)

    assert run.session_transcript.exists()
    assert run.session_transcript.stat().st_size > 0


def test_the_session_survives_aside_deleting_it_after_the_run(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)
    run_to_completion(run)
    kept = run.session_transcript.read_bytes()

    import shutil

    shutil.rmtree(aside_home / "u" / "0" / "sessions")

    assert run.session_transcript.read_bytes() == kept
    assert json.loads((run.path / "result.json").read_text())["answer"]


# --- the ways completion goes wrong ---------------------------------------------------


def test_a_run_whose_session_is_never_found_still_produces_an_answer(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """The session store is an unofficial surface. When correlation fails -- a schema
    change, a session that is never written -- the run still finished and its stdout
    still holds the answer, so it is reported as unstructured rather than as a failure."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "no_session")
    run = start(runs_dir)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=0.5, settle=0.1)

    assert meta["state"] == "completed_unstructured"
    result = json.loads((run.path / "result.json").read_text())
    assert "visible only in stdout" in result["answer"]
    assert "https://example.org/only-in-stdout" in json.dumps(result["sources"])


def test_a_child_still_running_at_parent_exit_is_named_not_hidden(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "orphan")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "30")
    run = start(runs_dir)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=0.4)

    assert meta["state"] == "completed_with_orphans"
    assert meta["orphan_children"], "the unfinished child's id has to be reported"


def test_a_child_that_finishes_inside_the_settle_window_is_a_clean_completion(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "orphan")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "0.3")
    run = start(runs_dir)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=4.0)

    assert meta["state"] == "completed"
    assert not meta.get("orphan_children")


def test_children_transcripts_are_copied_too(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")
    run = start(runs_dir)

    meta = run_to_completion(run, settle=1.0)

    assert len(meta["children"]) == 2
    # The ids and the content, not the file count: two empty files named after the wrong
    # sessions would satisfy a count.
    for cid in meta["children"]:
        text = run.child_transcript(cid).read_text(encoding="utf-8")
        assert "child task" in text
    answer = json.loads((run.path / "result.json").read_text())["answer"]
    assert "child 1 done." in answer and "child 2 done." in answer


def test_a_failing_aside_process_is_a_failed_run(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "fail")
    run = start(runs_dir)

    meta = run_to_completion(run)

    assert meta["state"] == "failed"
    assert meta.get("exit_code") == 1


def test_a_run_that_finds_nothing_says_so_rather_than_reporting_success(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "empty")
    run = start(runs_dir)

    meta = run_to_completion(run)

    assert meta["state"] == "completed"
    assert json.loads((run.path / "result.json").read_text())["empty"] is True


# --- correlation ----------------------------------------------------------------------


def test_two_runs_of_the_same_prompt_do_not_claim_each_others_sessions(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Actually concurrent, because sequential runs cannot reproduce the bug. Two searches
    of the same question are distinguishable only by the marker; run one after the other,
    even a matcher that keyed on prompt text would pass, since by then only one candidate
    session exists at a time."""
    import threading

    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "0.8")
    a, b = start(runs_dir, "같은 질문"), start(runs_dir, "같은 질문")

    threads = [threading.Thread(target=run_to_completion, args=(r,)) for r in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    sid_a, sid_b = a.meta().get("session_id"), b.meta().get("session_id")
    assert sid_a and sid_b and sid_a != sid_b
    # And each run's copy holds its own marker, not the other's.
    assert _registry.marker_for(a.run_id) in a.session_transcript.read_text(encoding="utf-8")
    assert _registry.marker_for(b.run_id) in b.session_transcript.read_text(encoding="utf-8")


def test_the_marker_is_appended_to_the_prompt_aside_actually_receives(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir, "원래 질문")

    run_to_completion(run)

    calls = [json.loads(l) for l in (fake_aside / "calls.jsonl").read_text().splitlines()]
    prompt = calls[-1]["argv"][-1]
    assert prompt.startswith("원래 질문")
    assert _registry.marker_for(run.run_id) in prompt


def test_aside_options_reach_the_command_line(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)
    run.update_meta(effort="high", model="openai-codex/gpt-5.6-sol", speed="fast")

    run_to_completion(run)

    argv = [json.loads(l) for l in (fake_aside / "calls.jsonl").read_text().splitlines()][-1]["argv"]
    assert argv[:2] == [argv[0], "exec"]
    for pair in (("--effort", "high"), ("--model", "openai-codex/gpt-5.6-sol"), ("--speed", "fast")):
        assert pair[1] == argv[argv.index(pair[0]) + 1]


def test_resume_targets_the_earlier_run_session(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    first = start(runs_dir)
    run_to_completion(first)

    second = start(runs_dir, "후속")
    second.update_meta(resume_session_id=first.meta()["session_id"], resumed_from=first.run_id)
    run_to_completion(second)

    argv = [json.loads(l) for l in (fake_aside / "calls.jsonl").read_text().splitlines()][-1]["argv"]
    assert argv[argv.index("--session") + 1] == first.meta()["session_id"]


# --- stopping -------------------------------------------------------------------------


def test_a_stop_request_ends_the_watch_and_says_the_run_goes_on(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """`stop` detaches the watcher. It cannot cancel the daemon-side run -- killing the
    CLI was measured leaving the run going and still spending credits -- so the state is
    `abandoned` and the payload says so."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    run = start(runs_dir)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=0.2, stop_after=0.6)

    assert meta["state"] == "abandoned"
    assert meta["daemon_run_continues"] is True


def test_a_watch_deadline_abandons_rather_than_reporting_completion(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    run = start(runs_dir)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=0.2, timeout=0.6)

    assert meta["state"] == "abandoned"
    assert meta["reason"] == "watch timeout"


# --- liveness -------------------------------------------------------------------------


def test_meta_tracks_activity_while_the_run_is_going(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1.5")
    run = start(runs_dir)

    meta = run_to_completion(run)

    assert meta["last_activity_at"] > 0
    assert meta["state"] == "completed"


def test_the_watch_timeout_recorded_by_the_cli_is_honoured(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """`--timeout` is recorded by the process that starts the run, but enforced by the
    detached supervisor, which cannot be passed an argument. Reading it back from meta is
    the only link between the two -- and when that link was missing the flag did nothing
    at all, silently."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    run = start(runs_dir)
    run.update_meta(watch_timeout=0.6)

    meta = _supervisor.supervise(run, poll=0.05, discovery_deadline=5.0, settle=0.2)

    assert meta["state"] == "abandoned"
    assert meta["reason"] == "watch timeout"


def test_a_child_that_stops_with_nothing_to_say_is_finished_not_orphaned(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """A subagent that honestly found nothing stops with an empty turn. Calling that an
    orphan reports a loose end where there is an answer -- and `completed_with_orphans`
    tells the caller to go looking for work that already finished."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    run = start(runs_dir)
    run.child_transcript("quiet").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("quiet").write_text(
        json.dumps({"role": "assistant", "content": [], "stopReason": "stop"}) + "\n"
    )

    assert _supervisor._child_is_terminal(run, "quiet") is True


def test_a_child_still_mid_tool_is_not_finished(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    run = start(runs_dir)
    run.child_transcript("busy").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("busy").write_text(
        json.dumps({"role": "assistant", "content": [], "stopReason": "toolUse"}) + "\n"
    )

    assert _supervisor._child_is_terminal(run, "busy") is False


def test_concurrent_meta_updates_do_not_lose_each_others_keys(runs_dir: Path) -> None:
    """meta.json is written by the starting CLI, the detached supervisor and `stop`, each
    doing read-modify-write. Without serialisation the loser's keys vanish -- which is how
    a supervisor's `state` and `pid` got overwritten by a parent holding an older copy."""
    import threading

    run = _registry.create_run(runs_dir, label="race")
    keys = [f"k{i}" for i in range(24)]

    def write(k: str) -> None:
        run.update_meta(**{k: k})

    threads = [threading.Thread(target=write, args=(k,)) for k in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    meta = run.meta()
    assert [k for k in keys if k not in meta] == []


def test_a_resumed_run_reads_the_session_it_was_told_to_continue(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """A resumed run appends to a session that already exists, so that transcript opens
    with the original prompt and the marker never reaches the line discovery reads. Hunting
    for it anyway leaves the run `completed_unstructured` with its answer scraped out of
    stdout -- which is what happened until the id was used directly."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    first = start(runs_dir)
    run_to_completion(first)
    session_id = first.meta()["session_id"]

    second = start(runs_dir, "후속 질문")
    second.update_meta(resume_session_id=session_id, resumed_from=first.run_id)
    meta = run_to_completion(second)

    assert meta["state"] == "completed"
    assert meta["session_id"] == session_id
    result = json.loads((second.path / "result.json").read_text())
    assert result["answer"] == "이어서 답합니다."
