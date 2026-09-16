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


def test_a_background_search_hands_back_the_command_that_will_wake_you(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """The failure this prevents: a caller starts work in the background and simply
    stops, because nothing told it how to find out the work had finished. The command is
    spelled out rather than described, and carries the Bash timeout it needs.

    Deliberately a slow run. Against a run that has already finished, a follower that
    returned immediately without waiting for anything would pass every assertion here --
    so the run has to still be going when the follower starts, and the follower has to be
    the thing that waits."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "2")
    code, payload, _ = run_cli("search", "질문", "--background", "--runs-dir", str(runs_dir))

    assert code == 0
    assert payload["runs"][0]["state"] in ("starting", "running")
    nxt = payload["next"]
    assert nxt["run_in_background"] is True
    assert nxt["bash_timeout_ms"] >= 600_000

    # Run it, rather than checking it contains "--follow": a command that names the wrong
    # run, or that cannot execute at all, passes every string check and still leaves the
    # caller with no way to find out the work finished.
    import shlex
    import subprocess
    import time as _t

    started = _t.time()
    done = subprocess.run(shlex.split(nxt["command"]), capture_output=True, text=True, timeout=180)
    waited = _t.time() - started

    assert done.returncode == 0
    assert f"run.completed {payload['runs'][0]['run_id']}" in done.stdout
    assert waited > 1.0, "the follower has to wait for the run, not return on a run already over"

    assert "then" not in nxt
    finished = json.loads(done.stdout.splitlines()[-1])
    assert finished["command"] == "log"
    assert finished["runs"][0]["state"] == "completed"
    assert finished["next"]["run_in_background"] is False
    collected = subprocess.run(finished["next"]["command"], shell=True, capture_output=True, text=True, timeout=120)
    assert collected.returncode == 0
    assert json.loads(collected.stdout.splitlines()[-1])["answer"] == "느린 답."


def test_log_defaults_to_the_supervisors_view(cli) -> None:
    """The command `next` hands back names no level, so the default is what a caller
    following a delegated run actually reads: what it reached for and said, not the
    arguments it used."""
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]

    _, _, text = cli("log", "--run", run_id)

    assert "prompt: 질문" in text
    assert "answer: " in text
    assert "call " not in text and "out=" not in text


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


def test_a_run_without_answer_or_sources_exits_five(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "empty")

    code, payload, _ = run_cli("search", "질문", "--wait", "30", "--runs-dir", str(runs_dir))

    assert code == 5
    assert payload["runs"][0]["empty"] is True


def test_a_negative_finding_is_an_answer_not_empty_output(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "negative")

    code, payload, _ = cli("search", "관련 사례가 있는가?", "--wait", "30")

    assert code == 0
    assert payload["runs"][0]["answer"] == "관련 사례를 찾지 못했습니다."
    assert payload["runs"][0]["sources"] == []
    assert payload["runs"][0]["empty"] is False


def test_a_missing_aside_binary_exits_three_instead_of_hanging(
    runs_dir: Path, aside_home: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload, _ = run_cli("search", "질문", "--wait", "5", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["error"] == "aside_unavailable"
    assert payload["fix"]


@pytest.mark.parametrize("runs_arg", [None, "relative runs"])
def test_next_commands_preserve_the_installed_path_and_run_store(
    tmp_path: Path, aside_home: Path, fake_aside: Path, monkeypatch, runs_arg
) -> None:
    import shlex
    import subprocess

    installed = tmp_path / r'installed "quote" $(touch injected) `touch leaked` \\ path'
    installed.symlink_to(Path(ultra_search.__file__).parent, target_is_directory=True)
    script = installed / "ultra_search.py"
    started_in = tmp_path / "start"
    collected_in = tmp_path / "elsewhere"
    started_in.mkdir()
    collected_in.mkdir()
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "0.5")
    argv = [sys.executable, str(script), "search", "path-test", "--background"]
    if runs_arg:
        argv += ["--runs-dir", runs_arg]
    started = subprocess.run(argv, cwd=started_in, capture_output=True, text=True, timeout=10)
    assert started.returncode == 0
    payload = json.loads(started.stdout)

    for command in ("log", "result"):
        nxt = payload["next"]
        args = shlex.split(nxt["command"])
        assert args[0] == "python3" and args[2] == command
        assert args[1].startswith(str(installed.parent / "installed "))
        assert nxt["command"].startswith('python3 "')
        root = Path(args[args.index("--runs-dir") + 1])
        assert root == started_in / (runs_arg or ".ultra-search")
        called = subprocess.run(nxt["command"], shell=True, cwd=collected_in, capture_output=True, text=True, timeout=15)
        assert called.returncode == 0, called.stderr + called.stdout
        payload = json.loads(called.stdout.splitlines()[-1])
    assert payload["answer"] == "느린 답."
    assert not (collected_in / "injected").exists()
    assert not (collected_in / "leaked").exists()


@pytest.mark.parametrize("group", [None, "mixed-group"])
def test_timed_out_follow_continues_from_each_stream_and_collects_all_runs(runs_dir: Path, group) -> None:
    import subprocess
    import _registry

    runs = [_registry.create_run(runs_dir, label=name, group=group) for name in (["a", "b"] if group else ["a"])]
    for run in runs:
        run.update_meta(state="running")
        run.session_transcript.parent.mkdir(parents=True, exist_ok=True)
        run.session_transcript.write_text(json.dumps({"role": "user", "content": f"seen-{run.run_id}"}) + "\n")
        run.child_transcript("kid").parent.mkdir(parents=True, exist_ok=True)
        run.child_transcript("kid").write_text(json.dumps({"role": "user", "content": f"seen-child-{run.run_id}"}) + "\n")
    if group:
        runs[0].update_meta(state="completed")
    target = ["--group", group] if group else ["--run", runs[0].run_id]

    code, waiting, text = run_cli("log", *target, "--follow", "--follow-timeout", "0", "--runs-dir", str(runs_dir))

    assert code == 0
    assert "run.still-running" in text
    assert waiting["next"]["run_in_background"] is True
    assert "then" not in waiting["next"]
    for run in runs:
        with run.child_transcript("kid").open("a") as f:
            f.write(json.dumps({"role": "assistant", "content": f"new-child-{run.run_id}", "stopReason": "stop"}) + "\n")
        (run.path / "result.json").write_text(json.dumps({"run_id": run.run_id, "answer": run.run_id, "sources": [], "empty": False}))
        run.update_meta(state="completed")

    followed = subprocess.run(waiting["next"]["command"], shell=True, capture_output=True, text=True, timeout=10)

    assert followed.returncode == 0
    assert "seen-" not in followed.stdout
    for run in runs:
        assert f"new-child-{run.run_id}" in followed.stdout
    finished = json.loads(followed.stdout.splitlines()[-1])
    collected = subprocess.run(finished["next"]["command"], shell=True, capture_output=True, text=True, timeout=10)
    result = json.loads(collected.stdout)
    assert collected.returncode == 0
    entries = result["runs"] if group else [result]
    assert {entry["answer"] for entry in entries} == {run.run_id for run in runs}


# --- resume -------------------------------------------------------------------------


def test_resume_log_waits_for_its_turn_and_never_replays_old_children(runs_dir: Path) -> None:
    import _registry

    run = _registry.create_run(runs_dir, label="resumed", resume_session_id="existing-session")
    marker = _registry.marker_for(run.run_id)
    run.update_meta(state="running", marker=marker)
    run.session_transcript.parent.mkdir(parents=True, exist_ok=True)
    old = [
        {"role": "user", "content": "old-prompt"},
        {"role": "toolResult", "toolName": "subagent", "details": {"taskId": "old-kid"}},
        {"role": "assistant", "content": "old-answer", "stopReason": "stop"},
    ]
    run.session_transcript.write_text("".join(json.dumps(r) + "\n" for r in old))
    run.child_transcript("old-kid").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("old-kid").write_text(json.dumps({"role": "user", "content": "old-child"}) + "\n")
    target = ["--run", run.run_id, "--runs-dir", str(runs_dir)]

    _, waiting, text = run_cli("log", *target)

    assert "old-" not in text
    current = [
        {"role": "user", "content": f"new-prompt {marker}"},
        {"role": "toolResult", "toolName": "subagent", "details": {"taskId": "new-kid"}},
        {"role": "assistant", "content": "new-answer", "stopReason": "stop"},
    ]
    with run.session_transcript.open("a") as f:
        f.write("".join(json.dumps(r) + "\n" for r in current))
    run.child_transcript("new-kid").write_text(json.dumps({"role": "user", "content": "new-child"}) + "\n")
    run.update_meta(state="completed")

    _, finished, text = run_cli("log", *target, "--since", str(waiting["cursor"]))

    assert "old-" not in text
    for expected in ("new-prompt", "new-answer", "new-child"):
        assert expected in text
    _, _, repeated = run_cli("log", *target, "--since", str(finished["cursor"]))
    assert "new-prompt" not in repeated and "new-child" not in repeated
    _, _, from_start = run_cli("log", *target)
    assert "new-prompt" in from_start and "old-" not in from_start


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
    """The parent's own files are deliberately made old and only the child's is fresh, so
    the child's activity is the only thing that can produce the verdict. Leaving the
    parent's files newly written would pass whether children were consulted or not."""
    import os
    import time as _t

    import _registry

    run = _registry.create_run(runs_dir, label="subs")
    run.update_meta(state="running", children=["kid"], last_activity_at=1.0)
    run.stdout_path.write_text("old output\n")
    run.session_transcript.parent.mkdir(parents=True, exist_ok=True)
    run.session_transcript.write_text('{"role":"user","content":[{"type":"text","text":"q"}]}\n')
    stale = _t.time() - 3600
    for p in (run.stdout_path, run.session_transcript, run.meta_path):
        os.utime(p, (stale, stale))

    run.child_transcript("kid").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid").write_text('{"role":"assistant","content":[],"timestamp":1}\n')

    code, status, _ = run_cli("status", "--run", run.run_id, "--stall-after", "60", "--runs-dir", str(runs_dir))

    assert status["runs"][0]["possibly_stalled"] is False
    assert status["runs"][0]["children"] == 1
    assert status["runs"][0]["idle_seconds"] < 60


def test_a_parent_whose_children_have_also_gone_quiet_is_flagged(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """The other half of the pair: when nothing anywhere has written recently, the flag has
    to appear -- otherwise the previous test passes for a `status` that never flags at all."""
    import os
    import time as _t

    import _registry

    run = _registry.create_run(runs_dir, label="quiet-subs")
    run.update_meta(state="running", children=["kid"], last_activity_at=1.0)
    run.child_transcript("kid").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid").write_text('{"role":"assistant","content":[],"timestamp":1}\n')
    stale = _t.time() - 3600
    for p in (run.meta_path, run.child_transcript("kid")):
        os.utime(p, (stale, stale))

    code, status, _ = run_cli("status", "--run", run.run_id, "--stall-after", "60", "--runs-dir", str(runs_dir))

    assert status["runs"][0]["possibly_stalled"] is True


# --- result and show ------------------------------------------------------------------


@pytest.mark.parametrize("state", ["failed", "abandoned", "completed_with_orphans"])
def test_terminal_log_and_result_preserve_failure_and_incompleteness(runs_dir: Path, state) -> None:
    import subprocess
    import _registry

    run = _registry.create_run(runs_dir, label="partial", group="g")
    run.update_meta(state=state, orphan_children=["late-child"] if state == "completed_with_orphans" else [])
    (run.path / "result.json").write_text(json.dumps({"run_id": run.run_id, "answer": "partial answer", "empty": False}))

    code, logged, text = run_cli("log", "--group", "g", "--follow", "--runs-dir", str(runs_dir))

    assert code == 0
    assert "group.completed" not in text
    assert logged["runs"][0]["state"] == state
    assert logged["next"]["run_in_background"] is False
    collected = subprocess.run(logged["next"]["command"], shell=True, capture_output=True, text=True, timeout=10)
    result = json.loads(collected.stdout)
    assert collected.returncode == (0 if state == "completed_with_orphans" else 4)
    assert result["state"] == state
    for entry in (logged["runs"][0], result):
        if state == "completed_with_orphans":
            assert entry["orphan_children"] == ["late-child"]
            assert "snapshot" in entry["note"] and "not" in entry["note"]
        elif state == "abandoned":
            assert entry["daemon_run_continues"] is True
            assert "credits" in entry["note"]


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
    for command in ("status", "log", "result"):
        _, payload, _ = run_cli(command, "--run", run_id, "--runs-dir", str(runs_dir))
        entry = payload["runs"][0] if command != "result" else payload
        assert entry["daemon_run_continues"] is True
        assert "credits" in entry["note"]


# --- continuing a session this tool did not create --------------------------------------


def test_sessions_lists_what_aside_still_has(cli, aside_home: Path) -> None:
    code, payload, _ = cli("sessions")

    assert code == 0
    ids = {s["session_id"] for s in payload["sessions"]}
    assert "SimpleSearch00001" in ids
    listed = next(s for s in payload["sessions"] if s["session_id"] == "SimpleSearch00001")
    # The prompt is what makes the list usable; nobody recognises a session id.
    assert "Python" in listed["prompt"]


def test_sessions_can_be_narrowed_to_the_ones_this_tool_started(cli, aside_home: Path) -> None:
    _, started, _ = cli("search", "질문", "--wait", "30")
    run_id = started["runs"][0]["run_id"]

    _, payload, _ = cli("sessions", "--mine")

    assert payload["sessions"], "the search just run must appear"
    assert all(s["started_by_ultra_search"] for s in payload["sessions"])
    assert run_id in {s["run_id"] for s in payload["sessions"]}


def test_sessions_can_be_searched_by_prompt(cli, aside_home: Path) -> None:
    _, payload, _ = cli("sessions", "--search", "Agent Teams")

    assert [s["session_id"] for s in payload["sessions"]] == ["SubagentParent01"]


def test_a_session_this_tool_never_created_can_be_resumed(cli, aside_home: Path) -> None:
    """The capability this is for: a conversation started in the Aside app, or by a bare
    `aside exec`, is picked up here and continued -- keeping everything it already worked
    out instead of starting the investigation again."""
    code, payload, _ = cli("resume", "SimpleSearch00001", "그래서 결론은?", "--wait", "30")

    assert code == 0
    run = payload["runs"][0]
    assert run["resumed_from"] == "SimpleSearch00001"
    assert run["state"] == "completed"
    assert run["answer"] == "이어서 답합니다."


def test_resuming_an_external_session_passes_it_to_aside_as_the_session(
    cli, aside_home: Path, fake_aside: Path
) -> None:
    cli("resume", "SimpleSearch00001", "후속", "--wait", "30")

    calls = [json.loads(l) for l in (fake_aside / "calls.jsonl").read_text().splitlines()]
    argv = calls[-1]["argv"]
    assert argv[argv.index("--session") + 1] == "SimpleSearch00001"


def test_resuming_does_not_inherit_the_previous_turns_loose_ends(cli, aside_home: Path) -> None:
    """The recorded session's earlier turn left a subagent mid-tool. That child belongs to
    the turn that spawned it and was reported there; carrying it forward would attach an
    unresolved loose end to every later question asked in the same conversation."""
    code, payload, _ = cli("resume", "SubagentParent01", "그래서 결론은?", "--wait", "30")

    run = payload["runs"][0]
    assert run["state"] == "completed"
    assert not run.get("orphan_children")
    assert run["answer"] == "이어서 답합니다."


def test_resuming_something_that_is_neither_a_run_nor_a_session_is_refused(cli) -> None:
    code, err, _ = cli("resume", "NoSuchThing00001", "후속")

    assert code == 2
    assert "sessions" in err["fix"]


def test_show_prefers_the_page_that_was_read_over_the_snippet_that_listed_it(
    runs_dir: Path, aside_home: Path, fake_aside: Path
) -> None:
    """A URL appears twice: once as a search result's excerpt, once as the page a later
    webfetch actually read. `show` exists to give the second one, and taking whichever
    came first in the transcript gives the first."""
    import _registry

    run = _registry.create_run(runs_dir, label="show")
    run.update_meta(state="completed")
    run.session_transcript.parent.mkdir(parents=True, exist_ok=True)
    src = {"sources": [{"id": "s1", "url": "https://e.test/a", "title": "A"}]}
    with run.session_transcript.open("w", encoding="utf-8") as f:
        for rec in (
            {"role": "user", "content": [{"type": "text", "text": "q"}]},
            {"role": "toolResult", "toolName": "websearch", "content": "검색 스니펫", "details": src},
            {"role": "toolResult", "toolName": "webfetch", "content": "페이지 전문", "details": src},
        ):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    code, shown, _ = run_cli("show", "--run", run.run_id, "--source", "0", "--runs-dir", str(runs_dir))

    assert code == 0
    assert shown["content"] == "페이지 전문"
    assert shown["source"]["opened"] is True


def test_resuming_a_session_that_is_mid_turn_is_refused(cli, aside_home: Path) -> None:
    """An ephemeral CLI session has no database row, so a check that only consults the
    database passes a busy session by virtue of its absence. The transcript always exists,
    and a turn that has not reached a terminal assistant message is still in flight."""
    d = aside_home / "u" / "0" / "sessions" / "2026-08-30_MidTurn000000001"
    d.mkdir()
    with (d / "messages.jsonl").open("w", encoding="utf-8") as f:
        for rec in (
            {"role": "user", "content": [{"type": "text", "text": "조사해줘"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "name": "websearch", "arguments": {}}],
             "stopReason": "toolUse"},
        ):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    code, err, _ = cli("resume", "MidTurn000000001", "후속")

    assert code == 2
    assert "in flight" in err["message"]


# --- doctor's negative paths ------------------------------------------------------------


def test_doctor_fails_when_the_conversion_packages_are_missing(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch, tmp_path: Path
) -> None:
    """Without these, `fetch` reaches the page and then fails to convert it -- a failure
    that reads as a network problem unless doctor says otherwise."""
    import _doctor

    monkeypatch.setattr(_doctor, "PAGE_DIR", tmp_path / "no-modules")

    code, payload, _ = run_cli("doctor", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["ok"] is False
    conversion = next(c for c in payload["checks"] if c["check"] == "page conversion")
    assert conversion["ok"] is False
    assert conversion["fix"]


def test_doctor_fails_on_an_unwritable_runs_directory(
    aside_home: Path, fake_aside: Path, tmp_path: Path
) -> None:
    """Tried, not assumed: an unwritable runs directory lets doctor pass and then fails the
    first `search` at the moment it reserves a run, which reads as the search breaking."""
    import os

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    os.chmod(blocked, 0o500)
    try:
        code, payload, _ = run_cli("doctor", "--runs-dir", str(blocked))
    finally:
        os.chmod(blocked, 0o700)

    assert code == 3
    runs = next(c for c in payload["checks"] if c["check"] == "runs dir")
    assert runs["ok"] is False


def test_doctor_reports_a_signed_out_browser_as_a_failure(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """A signed-out browser fetches public pages perfectly and silently loses every page
    this tool exists to reach, so an empty account roster is not a healthy environment."""
    import _doctor

    monkeypatch.setattr(_doctor, "_account_status", lambda: {"ok": False, "detail": "no accounts"})

    code, payload, _ = run_cli("doctor", "--runs-dir", str(runs_dir))

    assert code == 3
    assert next(c for c in payload["checks"] if c["check"] == "aside account")["ok"] is False
