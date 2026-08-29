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
    assert len(run.child_transcripts()) == 2


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
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    a, b = start(runs_dir, "같은 질문"), start(runs_dir, "같은 질문")

    run_to_completion(a)
    run_to_completion(b)

    assert a.meta()["session_id"] != b.meta()["session_id"]


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
