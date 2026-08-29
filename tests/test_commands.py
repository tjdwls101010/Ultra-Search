"""The commands, end to end through the real argparse, against the fake aside binary.

The seam is argv in, one JSON line and an exit code out -- exactly what a caller sees.
These are the tests that would catch a change to the CLI contract itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import ultra_search


def run_cli(*argv: str) -> tuple[int, dict, str]:
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = ultra_search.main(list(argv))
    text = buf.getvalue()
    last = [l for l in text.splitlines() if l.startswith("{")]
    return code, (json.loads(last[-1]) if last else {}), text


@pytest.fixture
def cli(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch):
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    return lambda *a: run_cli(*a, "--runs-dir", str(runs_dir))


# --- search -------------------------------------------------------------------------


def test_a_search_that_finishes_in_time_returns_its_answer_inline(cli) -> None:
    code, payload, _ = cli("search", "질문", "--wait", "30")

    assert code == 0
    assert payload["ok"] is True
    run = payload["runs"][0]
    assert run["state"] == "completed"
    assert "Answer" in run["answer"]
    assert run["sources"][0]["url"] == "https://example.org/a"


def test_a_finished_search_does_not_hand_back_a_next_step(cli) -> None:
    _, payload, _ = cli("search", "질문", "--wait", "30")

    assert "next" not in payload


def test_several_prompts_run_as_one_group(cli) -> None:
    code, payload, _ = cli("search", "A", "B", "C", "--wait", "30")

    assert code == 0
    assert payload["group"]
    assert len(payload["runs"]) == 3
    assert len({r["run_id"] for r in payload["runs"]}) == 3


def test_a_background_search_hands_back_the_command_that_will_wake_you(cli) -> None:
    """The failure this prevents: a caller starts work in the background and simply
    stops, because nothing told it how to find out the work had finished. The command is
    spelled out rather than described, and carries the Bash timeout it needs."""
    code, payload, _ = cli("search", "질문", "--background")

    assert code == 0
    assert payload["runs"][0]["state"] in ("starting", "running")
    nxt = payload["next"]
    assert "--follow" in nxt["command"]
    assert nxt["run_in_background"] is True
    assert nxt["bash_timeout_ms"] >= 600_000


def test_a_search_that_outlasts_the_wait_keeps_running_and_hands_back_a_handle(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")

    code, payload, _ = run_cli("search", "느린 질문", "--wait", "1", "--runs-dir", str(runs_dir))

    assert code == 0
    assert payload["runs"][0]["state"] in ("starting", "running")
    assert "next" in payload


def test_the_handed_back_run_can_be_collected_once_it_finishes(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1")
    _, payload, _ = run_cli("search", "느린 질문", "--wait", "0.3", "--runs-dir", str(runs_dir))
    run_id = payload["runs"][0]["run_id"]

    import io, contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ultra_search.main(["log", "--run", run_id, "--follow", "--follow-timeout", "30", "--runs-dir", str(runs_dir)])
    assert "run.completed" in buf.getvalue()

    code, result, _ = run_cli("result", "--run", run_id, "--runs-dir", str(runs_dir))
    assert code == 0
    assert result["answer"] == "느린 답."
    assert result["sources"]


def test_a_failed_run_exits_four(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "fail")

    code, payload, _ = run_cli("search", "질문", "--wait", "30", "--runs-dir", str(runs_dir))

    assert code == 4
    assert payload["runs"][0]["state"] == "failed"


def test_a_run_that_found_nothing_exits_five(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    """An honest zero is neither success nor failure: reporting it as success teaches a
    caller to trust an empty answer, and as failure teaches it to retry for the same
    nothing."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "empty")

    code, payload, _ = run_cli("search", "질문", "--wait", "30", "--runs-dir", str(runs_dir))

    assert code == 5
    assert payload["runs"][0]["empty"] is True


def test_a_missing_aside_binary_exits_three_instead_of_hanging(
    runs_dir: Path, aside_home: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload, _ = run_cli("search", "질문", "--wait", "5", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["error"] == "aside_unavailable"
    assert payload["fix"]


# --- resume -------------------------------------------------------------------------


def test_resume_continues_a_finished_run(cli) -> None:
    _, first, _ = cli("search", "질문", "--wait", "30")
    run_id = first["runs"][0]["run_id"]

    code, payload, _ = cli("resume", run_id, "후속 질문", "--wait", "30")

    assert code == 0
    assert payload["runs"][0]["resumed_from"] == run_id


def test_resume_is_refused_while_the_run_is_still_going(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Attaching to a live session was measured waiting for the current turn and then
    printing its result -- it cannot interrupt or redirect. Refusing is honest; letting
    it through would look like steering and silently not be."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")
    _, payload, _ = run_cli("search", "질문", "--wait", "0.3", "--runs-dir", str(runs_dir))
    run_id = payload["runs"][0]["run_id"]

    code, err, _ = run_cli("resume", run_id, "후속", "--runs-dir", str(runs_dir))

    assert code == 2
    assert "running" in err["message"]


# --- status -------------------------------------------------------------------------


def test_status_reports_activity_rather_than_guessing_at_health(cli) -> None:
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]

    code, status, _ = cli("status", "--run", run_id)

    assert code == 0
    assert status["runs"][0]["state"] == "completed"
    assert "idle_seconds" in status["runs"][0]
    assert status["runs"][0]["possibly_stalled"] is False


def test_status_flags_a_long_silence_without_acting_on_it(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    import _registry

    run = _registry.create_run(runs_dir, label="quiet")
    run.update_meta(state="running", last_activity_at=1.0, children=[])

    code, status, _ = run_cli("status", "--run", run.run_id, "--stall-after", "1", "--runs-dir", str(runs_dir))

    assert status["runs"][0]["possibly_stalled"] is True
    # Flagged only: the state is untouched and nothing was killed, because a slow run and
    # a stuck one look identical from here and only one of them should be abandoned.
    assert run.meta()["state"] == "running"


def test_a_silent_parent_with_busy_children_is_not_called_stalled(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    import time as _t

    import _registry

    run = _registry.create_run(runs_dir, label="subs")
    run.update_meta(state="running", children=["kid"], last_activity_at=1.0)
    run.child_transcript("kid").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid").write_text('{"role":"assistant","content":[],"timestamp":1}\n')

    code, status, _ = run_cli("status", "--run", run.run_id, "--stall-after", "60", "--runs-dir", str(runs_dir))

    assert status["runs"][0]["possibly_stalled"] is False
    assert status["runs"][0]["children"] == 1


# --- result and show ------------------------------------------------------------------


def test_sources_only_omits_the_answer(cli) -> None:
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]

    _, result, _ = cli("result", "--run", run_id, "--sources-only")

    assert "answer" not in result
    assert result["sources"]


def test_show_returns_a_sources_text_without_fetching_it_again(cli) -> None:
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]

    code, shown, _ = cli("show", "--run", run_id, "--item", "0")

    assert code == 0
    assert shown["tool"] == "websearch"
    assert shown["content"]


def test_an_out_of_range_item_is_refused_with_the_count(cli) -> None:
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]

    code, err, _ = cli("show", "--run", run_id, "--item", "9")

    assert code == 2
    assert "1 tool result" in err["message"]


def test_result_of_the_whole_group(cli) -> None:
    _, payload, _ = cli("search", "A", "B", "--wait", "30")

    code, result, _ = cli("result", "--group", payload["group"])

    assert code == 0
    assert len(result["runs"]) == 2


# --- stop -----------------------------------------------------------------------------


def test_stop_says_plainly_that_the_run_itself_continues(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")
    _, payload, _ = run_cli("search", "질문", "--wait", "0.3", "--runs-dir", str(runs_dir))
    run_id = payload["runs"][0]["run_id"]

    code, stopped, _ = run_cli("stop", "--run", run_id, "--runs-dir", str(runs_dir))

    assert code == 0
    assert stopped["daemon_run_continues"] is True
    assert "aside" in stopped["note"].lower()
