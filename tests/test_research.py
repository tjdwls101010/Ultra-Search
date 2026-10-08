"""`search`, `resume`, `log`, `result`, `show` and `sessions`, end to end.

The seam is argv in, stdout and an exit code out -- exactly what a caller sees. The one
external boundary, the aside binary, is the fake in tests/fake_aside, which writes session
transcripts into a throwaway ~/.aside the way the real one does; everything between the
CLI and that boundary is the real code, including the detached supervisor.

What a run concluded is only ever read back through the commands. A test that opened a
run directory to check its answer would pass while `result` reported something else.
"""
from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import pytest

import cli
from ultra_search import research, runs
from conftest import (
    FIXTURES,
    SCRIPTS,
    aside_session,
    answer,
    calling,
    exec_calls,
    run_cli,
    run_cli_streams,
    subagent_turn,
    tool,
    turn,
    user,
)

SESSIONS = FIXTURES / "sessions"
RECORDED_RUN = FIXTURES / "runs" / "260829-235523-subagents"
#: A run recorded on 2026-10-02 against daemon 1.26.1001.14: every turn framed by lifecycle
#: records, and one subagent given a second task after its first came back empty.
LIFECYCLE_RUN = FIXTURES / "runs" / "261002-lifecycle-subagent"
LIFECYCLE_CHILD = "ZFgNUcNIKq1MWMz4"


def first_run(payload: dict) -> dict:
    return payload["runs"][0]


def search(cli, *prompts: str, wait: str = "30", extra: tuple = ()) -> tuple[int, dict, str]:
    return cli("search", *prompts, "--wait", wait, *extra)


def finished_run_id(cli, *extra: str) -> str:
    code, payload, _ = search(cli, "질문", extra=extra)
    assert first_run(payload)["state"] in ("completed", "completed_with_orphans"), payload
    return first_run(payload)["run_id"]


def lines_of(text: str) -> list[str]:
    """What a command printed before its JSON response, which is always the last line."""
    lines = text.splitlines()
    return lines[:-1] if lines and lines[-1].startswith("{") else lines


def rendered(text: str) -> str:
    """Only the event lines of a log, without its response."""
    return "\n".join(lines_of(text))


def every_source(cli, run_id: str) -> list[dict]:
    """All the sources of a run, as `result --sources` lists them."""
    return first_run(cli("result", "--run", run_id, "--sources")[1])["sources"]


def session_of(cli, run_id: str) -> str | None:
    """The Aside session a run this tool started correlated with, as `sessions --mine` lists it."""
    listed = cli("sessions", "--mine", "--limit", "100")[1].get("sessions", [])
    return next((row["session_id"] for row in listed if row["run_id"] == run_id), None)


def kill_supervisors(*targets: runs.Run) -> None:
    """End a run's detached supervisor the way a crash would. Started from this process by the in-process CLI, it is this
    process's child and is reaped here -- as the system reaps it once the CLI that started it has exited."""
    for run in targets:
        pid = poll(lambda: run.meta().get("supervisor_pid"), timeout=10)
        os.kill(pid, signal.SIGKILL)
        with contextlib.suppress(ChildProcessError):
            os.waitpid(pid, 0)


def saved(entry: dict) -> dict:
    """The whole result a reply points at."""
    return json.loads(Path(entry["result_path"]).read_text(encoding="utf-8"))


def follow_next(payload: dict, limit: int = 5) -> dict:
    """Run each reply's `next` as the shell would, until a reply hands back none: the reply a caller ends with."""
    for _ in range(limit):
        if "next" not in payload:
            return payload
        done = subprocess.run(payload["next"]["command"], shell=True, capture_output=True, text=True,
                              timeout=payload["next"]["bash_timeout_ms"] / 1000)
        payload = json.loads(done.stdout.splitlines()[-1])
    raise AssertionError(f"still handing back next after {limit} steps: {payload}")


def poll(check, timeout: float = 10.0, every: float = 0.2):
    deadline = time.time() + timeout
    while True:
        got = check()
        if got or time.time() >= deadline:
            return got
        time.sleep(every)


# --- runs started outside a test's own fixtures ------------------------------------------
#
# A few transcripts are expensive to produce (a recorded run whose unfinished children cost
# the full settle window) and are read by several tests. Those are started once per module
# in their own throwaway ~/.aside, through a subprocess, exactly as a caller would.


def start_isolated(base: Path, records, *, daemon: str, children: dict | None = None, prompt: str = "질문",
                   label: str = "run", wait: str = "60", fmt: str = "lifecycle") -> tuple[Path, dict]:
    home = base / "aside-home"
    (home / "u" / "0" / "sessions").mkdir(parents=True)
    for sid, source in (children or {}).items():
        d = home / "u" / "0" / "sessions" / f"2026-09-25_{sid}"
        d.mkdir()
        if isinstance(source, Path):
            shutil.copy(source, d / "messages.jsonl")
        else:
            (d / "messages.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in source))
    replay = base / "replay.jsonl"
    if isinstance(records, Path):
        shutil.copy(records, replay)
    else:
        replay.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    runs = base / "runs-root"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FAKE_ASIDE_", "ULTRA_SEARCH_"))}
    env.update(
        ULTRA_SEARCH_ASIDE_HOME=str(home),
        ULTRA_SEARCH_ASIDE_BIN=str(Path(__file__).parent / "fake_aside" / "aside"),
        FAKE_ASIDE_SCENARIO="simple",
        FAKE_ASIDE_REPLAY=str(replay),
        FAKE_ASIDE_FORMAT=fmt,
        ULTRA_SEARCH_DAEMON_URL=daemon,
    )
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "cli.py"), "search", prompt, "--label", label,
         "--wait", wait, "--runs-dir", str(runs)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    return runs, json.loads(p.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def recorded(tmp_path_factory, ready_daemon: str) -> tuple[Path, str]:
    """A run recorded on 2026-08-29, before lifecycle records: a parent that spawned three
    subagents, one of them kept."""
    parent = RECORDED_RUN / "session" / "messages.jsonl"
    opening = json.loads(parent.read_text(encoding="utf-8").splitlines()[0])
    prompt = opening["content"][0]["text"].split("\n\n(ultra-search:")[0]
    kid = "4kgZvArU4ipY0eIn"
    runs, payload = start_isolated(
        tmp_path_factory.mktemp("recorded"), parent,
        children={kid: RECORDED_RUN / "session" / "children" / f"{kid}.jsonl"},
        prompt=prompt, label="subagents", fmt="legacy", daemon=ready_daemon,
    )
    return runs, first_run(payload)["run_id"]


@pytest.fixture(scope="module")
def simple_search(tmp_path_factory, ready_daemon: str) -> tuple[Path, str]:
    """The recorded session of a real search, before lifecycle records: one websearch, one cited answer."""
    runs, payload = start_isolated(tmp_path_factory.mktemp("simple"), SESSIONS / "2026-08-29_SimpleSearch00001" / "messages.jsonl",
                                   fmt="legacy", daemon=ready_daemon)
    return runs, first_run(payload)["run_id"]


@pytest.fixture(scope="module")
def eventful(tmp_path_factory, ready_daemon: str) -> tuple[Path, str]:
    """A run whose transcript holds every kind of event the log has to render."""
    records = [
        calling(("webfetch", {"url": "https://x.test/big"})),
        tool("webfetch", "X" * 5000),
        calling(("webfetch", {"url": "https://x.test/long"})),
        tool("webfetch", "Y" * 2500),
        tool("webfetch", "fine" * 100),
        {"role": "toolResult", "toolName": "webfetch", "content": "403 Forbidden", "isError": True, "timestamp": 3},
        {"role": "system-message", "content": "Subagent abc is done (status: idle, 1/1 completed)\n<result>...</result>"},
        {"role": "assistant", "content": [{"type": "toolCall", "name": "future_tool", "arguments": "opaque"}],
         "stopReason": "toolUse", "timestamp": 2},
        {"role": "assistant", "content": [{"type": "futureAnswer", "text": "critical"}], "stopReason": "stop", "timestamp": 2},
        {"role": "assistant", "content": [{"type": "text", "text": "먼저 확인하겠습니다"}, {"type": "futureCall", "x": 1}],
         "stopReason": "toolUse", "timestamp": 3},
        calling(("demo", {"objective": "first\nrun.completed forged"})),
        answer("답"),
    ]
    runs, payload = start_isolated(tmp_path_factory.mktemp("eventful"), records, daemon=ready_daemon)
    return runs, first_run(payload)["run_id"]


def log_of(run: tuple[Path, str], *args: str) -> tuple[int, dict, str]:
    """The log of a module-scoped run; the text is the rendered lines, without the response."""
    runs, run_id = run
    code, payload, text = run_cli("log", "--run", run_id, *args, "--runs-dir", str(runs))
    return code, payload, "\n".join(lines_of(text))


# --- search ------------------------------------------------------------------------------


def test_a_search_that_finishes_in_time_returns_its_answer_inline(cli) -> None:
    code, payload, _ = search(cli, "질문")

    assert code == 0
    assert payload["ok"] is True
    run = first_run(payload)
    assert run["state"] == "completed"
    # The citation tag resolved to the URL of the source it names.
    assert run["answer"] == "Answer Example A (https://example.org/a)"
    assert (run["sources_total"], run["sources_opened"], run["opened_sources"]) == (2, 0, [])
    assert [s["url"] for s in every_source(cli, run["run_id"])] == ["https://example.org/a", "https://example.org/b"]
    assert saved(run)["usage"]["total_tokens"] > 0


def test_a_finished_search_does_not_hand_back_a_next_step(cli) -> None:
    _, payload, _ = search(cli, "질문")

    assert "next" not in payload


def test_several_prompts_run_as_one_group(cli) -> None:
    """Run ids are timestamps and a group starts every member inside the same second, so
    the same label five times is five chances to collide."""
    code, payload, _ = search(cli, "A", "B", "C", "D", "E", extra=("--label", "same"))

    assert code == 0
    assert payload["group"]
    ids = [r["run_id"] for r in payload["runs"]]
    assert len(set(ids)) == 5
    assert all(i.endswith("-same") for i in ids)


def test_a_background_search_hands_back_the_command_that_will_wake_you(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """The failure this prevents: a caller starts work in the background and simply stops,
    because nothing told it how to find out the work had finished. The command is spelled
    out rather than described, and carries the Bash timeout it needs.

    Deliberately a slow run. Against a run that has already finished, a command that
    returned immediately without waiting for anything would pass every assertion here -- so
    the run has to still be going when it starts, and it has to be the thing that waits."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "5")
    code, payload, _ = run_cli("search", "질문", "--background", "--runs-dir", str(runs_dir))

    assert code == 0
    assert first_run(payload)["state"] in ("starting", "running")
    nxt = payload["next"]
    assert set(nxt) == {"command", "bash_timeout_ms", "run_in_background"}, "one action, nothing to do afterwards"
    assert nxt["run_in_background"] is True
    assert nxt["bash_timeout_ms"] >= 600_000

    # Run it, rather than checking what it contains: a command that names the wrong run, or
    # that cannot execute at all, passes every string check and still leaves the caller with
    # no way to find out the work finished.
    started = time.time()
    done = subprocess.run(shlex.split(nxt["command"]), capture_output=True, text=True, timeout=180)
    waited = time.time() - started

    assert done.returncode == 0
    assert waited > 1.0, "it has to wait for the run, not return on a run already over"
    assert "answer: 느린 답." in done.stderr, "what the run does while it is waited on is shown as it happens"
    finished = json.loads(done.stdout)
    assert finished["command"] == "result"
    assert "next" not in finished, "a finished run hands back nothing more to do"
    assert first_run(finished)["state"] == "completed"
    assert first_run(finished)["answer"] == "느린 답."


def test_a_search_that_outlasts_the_wait_keeps_running_and_hands_back_a_handle(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")

    code, payload, _ = search(cli, "느린 질문", wait="1")

    assert code == 0
    assert first_run(payload)["state"] in ("starting", "running")
    assert " result --run " in payload["next"]["command"] and payload["next"]["command"].endswith(" --wait 570")


def test_the_handed_back_run_can_be_collected_once_it_finishes(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1")
    _, payload, _ = search(cli, "느린 질문", wait="0.3")
    run_id = first_run(payload)["run_id"]

    code, result, _ = cli("result", "--run", run_id, "--wait", "30")

    result = result["runs"][0]
    assert code == 0
    assert result["answer"] == "느린 답."
    assert result["sources_total"] > 0


def test_a_wait_that_runs_out_hands_back_the_wait_again(cli, monkeypatch) -> None:
    """Running out of time to wait is not an ending: the run is reported as it stands, with the same wait to continue."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    _, payload, _ = search(cli, "느린 질문", wait="0.3")

    began = time.time()
    code, waited, _ = cli("result", "--run", first_run(payload)["run_id"], "--wait", "1")

    assert code == 0
    assert 1.0 <= time.time() - began < 10
    assert first_run(waited)["state"] in ("starting", "running")
    assert waited["next"] == payload["next"]


SLOW = [{"__if_prompt__": "느린", **calling(("webfetch", {"url": "https://x.test"}))},
        {"__if_prompt__": "느린", "__sleep__": 20}, {"__if_prompt__": "느린", **answer("늦은 답")}]


@pytest.mark.parametrize("ended,code", [
    ([{"__if_prompt__": "실패", **{"role": "assistant", "content": [{"type": "text", "text": "오류"}], "stopReason": "error", "timestamp": 2}}], 4),
    ([{"__if_prompt__": "빈", **answer("")}], 0),
], ids=["failed-and-running", "empty-and-running"])
def test_a_group_still_going_is_handed_back_whatever_its_ended_members_say(cli, replay, ended, code) -> None:
    """A failure is reported as soon as it is known, with the wait for the rest; an empty result is not the group's verdict while a member is still going."""
    replay(ended + SLOW)
    _, started, _ = cli("search", "실패 빈 질문", "느린 질문", "--wait", "3")

    got, waited, _ = cli("result", "--group", started["group"], "--wait", "0.5")

    assert got == code
    assert waited["next"]["command"].endswith(" --wait 570") and f"--group {started['group']}" in waited["next"]["command"]
    assert {first_run(waited)["state"], waited["runs"][1]["state"]} & {"starting", "running"}


def test_a_group_whose_members_all_ended_empty_exits_five(cli, replay) -> None:
    replay([answer("")])
    _, started, _ = cli("search", "하나", "둘", "--wait", "30")

    code, collected, _ = cli("result", "--group", started["group"])

    assert code == 5
    assert "next" not in collected


def dead_pid() -> int:
    """The pid of a process that has exited and been reaped."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    return gone.pid


def test_a_run_whose_supervisor_is_gone_is_abandoned_not_waited_on_forever(cli, runs_dir: Path) -> None:
    """Nothing else would ever end it: a wait would hand back the same wait without end."""
    run = runs.create_run(runs_dir, label="orphaned", prompt="질문")
    run.update_meta(state="running", supervisor_pid=dead_pid())

    code, payload, _ = cli("result", "--run", run.run_id)

    assert code == 4
    assert first_run(payload)["state"] == "abandoned"
    assert "next" not in payload
    assert "the supervisor is gone" in first_run(payload)["note"]


def test_a_run_whose_supervisor_never_started_is_abandoned_and_a_late_one_starts_nothing(
    cli, runs_dir: Path, fake_aside: Path
) -> None:
    """A run reserved more than a minute ago without a supervisor is not coming. If its supervisor wakes after all, it finds the run settled and does not start the work a caller has already been told was abandoned."""
    fresh = runs.create_run(runs_dir, label="fresh", prompt="질문")
    stale = runs.create_run(runs_dir, label="stale", prompt="질문")
    stale.update_meta(created_at=time.time() - 120)

    _, young, _ = cli("result", "--run", fresh.run_id)
    code, old, _ = cli("result", "--run", stale.run_id)
    research.supervise(stale, poll=0.05)

    assert first_run(young)["state"] == "starting" and "next" in young
    assert code == 4 and first_run(old)["state"] == "abandoned"
    assert "the supervisor never started" in first_run(old)["note"]
    assert exec_calls(fake_aside) == [], "the supervisor that woke late started no work"


def test_a_result_written_by_a_supervisor_that_died_before_recording_it_is_kept(cli, runs_dir: Path) -> None:
    """The supervisor writes result.json and then meta.json. Dying between the two leaves a result the run's state must come from -- with what it says about children still running."""
    run = runs.create_run(runs_dir, label="half", prompt="질문")
    run.update_meta(state="running", supervisor_pid=dead_pid())
    runs.atomic_write_json(run.path / "result.json", {
        "run_id": run.run_id, "state": "completed_with_orphans", "answer": "부분 답", "sources": [], "usage": {},
        "children": ["StillGoingKid001"], "orphan_children": ["StillGoingKid001"], "empty": False, "exit_code": 0})

    code, payload, _ = cli("result", "--run", run.run_id)

    entry = first_run(payload)
    assert code == 0
    assert entry["state"] == "completed_with_orphans"
    assert entry["orphan_children"] == ["StillGoingKid001"]
    assert "Partial snapshot" in entry["note"]
    assert entry["answer"] == "부분 답"


def test_a_finished_run_is_never_rewritten_as_abandoned(cli, runs_dir: Path) -> None:
    """Its supervisor is gone because it finished; the check that catches a dead one must not overwrite the result."""
    run = runs.create_run(runs_dir, label="done", prompt="질문")
    run.update_meta(state="completed", supervisor_pid=dead_pid())

    code, payload, _ = cli("result", "--run", run.run_id)

    assert first_run(payload)["state"] == "completed"
    assert code in (0, 5)


@pytest.mark.parametrize("argv", [
    ["status"], ["stop", "--run", "x"], ["search", "q", "--timeout", "1"], ["resume", "x", "q", "--timeout", "1"],
    ["log", "--follow"], ["log", "--since", "0"], ["log", "--heartbeat", "1"], ["log", "--follow-timeout", "1"],
], ids=lambda a: " ".join(a[:2]))
def test_what_was_removed_is_refused(cli, argv: list[str], fake_aside: Path) -> None:
    code, payload, _ = cli(*argv)

    assert code == 2
    assert payload["error"] == "bad_arguments"
    assert "invalid choice" in payload["message"] or "unrecognized arguments" in payload["message"]
    assert exec_calls(fake_aside) == []


def test_log_reads_once_and_answers_without_a_cursor(cli, runs_dir: Path) -> None:
    run_id = finished_run_id(cli)

    code, out, err = run_cli_streams("log", "--run", run_id, "--runs-dir", str(runs_dir))

    assert code == 0
    assert "prompt: 질문" in err
    assert set(json.loads(out)) == {"ok", "command", "runs"}


def test_a_search_whose_process_exits_mid_turn_hands_back_the_final_answer(cli, replay) -> None:
    """`aside exec` exited 0 while its subagents were working, and the final answer came 15 seconds later -- past the supervisor's own settle window and its poll after it. Following `next` to the end still has to give the caller that answer, not an empty snapshot with orphans."""
    replay(subagent_turn(gap=15))

    _, payload, _ = search(cli, "질문", wait="0.5")
    final = follow_next(payload)

    run = first_run(final)
    assert final["command"] == "result"
    assert run["state"] == "completed"
    assert run["answer"].startswith("최종 답")


def test_the_files_the_agent_saved_come_back_as_copies_its_answer_points_at(cli, replay, aside_home: Path) -> None:
    """The agent keeps what it downloads in its session's `artifacts/`, and its answer names those files relative to that session -- a path the caller cannot open. Each comes back as a copy under the run, the answer pointing at it; a parent and a child that saved the same name keep their own; a link is not followed out of the folder."""
    kid = "SavingChild00001"
    replay([
        {"__artifact__": "KSPO 보고서 (최종).pdf", "text": "parent pdf"},
        {"__artifact__": "tmp/표.csv", "text": "a,b"},
        {"__artifact__": "report.txt", "text": "parent report"},
        {"__artifact__": f"{kid}/report.txt", "text": "parent's folder named like the child"},
        {"__artifact__": "linked.txt", "link": str(aside_home)},
        calling(("subagent", {"action": "spawn", "description": "c1"})),
        {"__session__": kid, **turn("started")}, {"__session__": kid, **user("child task")},
        {"__session__": kid, "__artifact__": "report.txt", "text": "child report"},
        {"__session__": kid, **turn("final-started")},
        {"__session__": kid, **answer("자식 보고서: [보고서](artifacts/report.txt)")},
        {"__session__": kid, **turn("finished")},
        tool("subagent", "spawned", taskId=kid),
        turn("final-started"),
        answer("[원문](artifacts/KSPO 보고서 (최종).pdf) · [표](sandbox:__SESSION_DIR__/artifacts/tmp/%ED%91%9C.csv) · "
               "[보고서](artifacts/report.txt) · [자식 것](__SESSION_DIR:SavingChild00001__/artifacts/report.txt)"),
        turn("finished"),
    ])

    _, payload, _ = search(cli, "질문")

    run = first_run(payload)
    parent = next(d.name.split("_", 1)[1] for d in (aside_home / "u" / "0" / "sessions").iterdir()
                  if (d / "artifacts" / "tmp" / "표.csv").exists())
    mine, theirs = Path(run["result_path"]).parent / "artifacts" / parent, Path(run["result_path"]).parent / "artifacts" / kid
    expected = {mine / "KSPO 보고서 (최종).pdf": "parent pdf", mine / "tmp" / "표.csv": "a,b",
                mine / "report.txt": "parent report", mine / kid / "report.txt": "parent's folder named like the child",
                theirs / "report.txt": "child report"}
    assert sorted(run["artifacts"]) == sorted(str(p) for p in expected)
    assert {Path(p): Path(p).read_text(encoding="utf-8") for p in run["artifacts"]} == expected
    assert list(run)[-3:] == ["opened_sources", "artifacts", "result_path"]
    assert run["answer"] == (f"[원문]({mine / 'KSPO 보고서 (최종).pdf'}) · [표]({mine / 'tmp' / '표.csv'}) · "
                             f"[보고서]({mine / 'report.txt'}) · [자식 것]({theirs / 'report.txt'})\n\n--- child {kid} ---\n"
                             f"자식 보고서: [보고서]({theirs / 'report.txt'})")


def test_a_failed_run_exits_four(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "fail")

    code, payload, _ = search(cli, "질문")
    _, result, _ = cli("result", "--run", first_run(payload)["run_id"])
    result = result["runs"][0]

    assert code == 4
    assert first_run(payload)["state"] == "failed"
    assert saved(result)["exit_code"] == 1, "aside's own exit status is kept for diagnosis"


def test_a_run_without_answer_or_sources_exits_five(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "empty")

    code, payload, _ = search(cli, "질문")

    assert code == 5
    assert first_run(payload)["state"] == "completed"
    assert first_run(payload)["empty"] is True


def test_a_negative_finding_is_an_answer_not_empty_output(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "negative")

    code, payload, _ = search(cli, "관련 사례가 있는가?")

    assert code == 0
    assert first_run(payload)["answer"] == "관련 사례를 찾지 못했습니다."
    assert first_run(payload)["sources_total"] == 0
    assert first_run(payload)["empty"] is False


def test_a_daemon_that_does_not_answer_exits_three_before_reserving_a_run(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """With the Aside app closed, `aside exec` exits with an error that used to be reported as a
    failed run whose answer was the error text."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setenv("ULTRA_SEARCH_DAEMON_URL", f"http://127.0.0.1:{port}/")

    code, payload, _ = run_cli("search", "질문", "--wait", "5", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["error"] == "aside_unavailable" and "doctor" in payload["fix"]
    assert run_cli("result", "--runs-dir", str(runs_dir))[0] == 2, "no run was reserved"
    assert exec_calls(fake_aside) == []


def test_a_missing_aside_binary_exits_three_before_reserving_a_run(runs_dir: Path, aside_home: Path, monkeypatch) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload, _ = run_cli("search", "질문", "--wait", "5", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["error"] == "aside_unavailable"
    assert payload["fix"]
    code, _, _ = run_cli("result", "--runs-dir", str(runs_dir))
    assert code == 2, "a registry full of runs that never started is worse than the error"


@pytest.mark.parametrize("runs_arg", [None, "relative runs"])
def test_next_commands_preserve_the_installed_path_and_run_store(
    tmp_path: Path, aside_home: Path, fake_aside: Path, monkeypatch, runs_arg
) -> None:
    installed = tmp_path / r'installed "quote" $(touch injected) `touch leaked` \\ path'
    installed.symlink_to(Path(cli.__file__).parent, target_is_directory=True)
    script = installed / "cli.py"
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

    nxt = payload["next"]
    args = shlex.split(nxt["command"])
    # The form the skill's permission rule pre-approves: uv runs the script with the Python
    # its header asks for, whatever `python3` is on PATH.
    assert args[:2] == ["uv", "run"] and args[3] == "result"
    assert args[2].startswith(str(installed.parent / "installed "))
    assert nxt["command"].startswith('uv run "')
    root = Path(args[args.index("--runs-dir") + 1])
    assert root == started_in / (runs_arg or ".ultra-search")
    called = subprocess.run(nxt["command"], shell=True, cwd=collected_in, capture_output=True, text=True, timeout=60)
    assert called.returncode == 0, called.stderr + called.stdout
    payload = json.loads(called.stdout.splitlines()[-1])
    assert "next" not in payload
    assert payload["runs"][0]["answer"] == "느린 답."
    assert (started_in / (runs_arg or ".ultra-search") / "runs").is_dir()
    assert not (collected_in / "injected").exists()
    assert not (collected_in / "leaked").exists()


def test_aside_receives_the_prompt_with_this_runs_marker(cli, fake_aside: Path) -> None:
    """Aside never says which session it created. The marker is how the run finds its own,
    so it has to reach the prompt aside actually receives, and be this run's alone."""
    _, payload, _ = search(cli, "원래 질문", "원래 질문")

    prompts = [argv[-1] for argv in exec_calls(fake_aside)]
    for run in payload["runs"]:
        mine = [p for p in prompts if f"ultra-search:{run['run_id']} " in p]
        assert len(mine) == 1
        assert mine[0].startswith("원래 질문\n\n")


def test_aside_options_reach_the_command_line(cli, fake_aside: Path) -> None:
    search(cli, "질문", extra=("--effort", "high", "--model", "openai-codex/gpt-5.6-sol", "--speed", "fast"))

    argv = exec_calls(fake_aside)[-1]
    for flag, value in (("--effort", "high"), ("--model", "openai-codex/gpt-5.6-sol"), ("--speed", "fast")):
        assert argv[argv.index(flag) + 1] == value


@pytest.mark.parametrize("option", [("--effort", "high"), ("--model", "openai-codex/gpt-5.6-sol"), ("--speed", "fast")])
def test_resume_refuses_options_a_continued_session_cannot_take(cli, fake_aside: Path, option: tuple) -> None:
    """Aside continues a session with the settings it already has: `aside session resume` takes no effort, model or
    speed. Accepting one here and dropping it would report a setting that never reached the run."""
    run_id = finished_run_id(cli)
    started = len(exec_calls(fake_aside))

    code, payload, _ = cli("resume", run_id, "후속 질문", *option)

    assert code == 2
    assert payload["error"] == "bad_arguments"
    assert len(exec_calls(fake_aside)) == started


def test_a_label_names_the_run_and_cannot_escape_the_registry(cli, runs_dir: Path) -> None:
    _, named, _ = search(cli, "질문", extra=("--label", "python-version"))
    _, hostile, _ = search(cli, "질문", extra=("--label", "../../etc/passwd"))

    assert first_run(named)["run_id"].endswith("-python-version")
    run_id = first_run(hostile)["run_id"]
    assert "/" not in run_id and ".." not in run_id
    assert (runs_dir / "runs" / run_id).is_dir()
    code, collected, _ = cli("result", "--run", run_id)
    assert code == 0 and first_run(collected)["state"] == "completed"


def test_two_runs_of_the_same_prompt_keep_their_own_sessions(cli, monkeypatch) -> None:
    """Actually concurrent, because sequential runs cannot reproduce the bug: two searches of
    the same question are distinguishable only by the marker, and run one after the other
    even a matcher keyed on prompt text would pass."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "0.8")
    _, payload, _ = search(cli, "같은 질문", "같은 질문")
    a, b = (r["run_id"] for r in payload["runs"])

    assert None not in {session_of(cli, a), session_of(cli, b)} and session_of(cli, a) != session_of(cli, b)
    # Each run's transcript opens with its own marker and never holds the other's.
    _, _, text_a = cli("log", "--run", a, "--level", "raw")
    _, _, text_b = cli("log", "--run", b, "--level", "raw")
    assert f"ultra-search:{a}" in text_a and f"ultra-search:{b}" not in text_a
    assert f"ultra-search:{b}" in text_b and f"ultra-search:{a}" not in text_b


def test_the_transcript_outlives_asides_own_copy(cli, aside_home: Path) -> None:
    """Aside removes old sessions on its own schedule. A run whose evidence lived only in the
    session directory would have none once Aside removes it."""
    run_id = finished_run_id(cli)

    shutil.rmtree(aside_home / "u" / "0" / "sessions")

    _, result, _ = cli("result", "--run", run_id)
    result = result["runs"][0]
    code, shown, _ = cli("show", "--run", run_id, "--item", "0")
    _, _, logged = cli("log", "--run", run_id)
    assert result["answer"].startswith("Answer")
    assert code == 0 and shown["tool"] == "websearch"
    assert "answer: Answer" in logged


def test_session_discovery_skips_a_directory_with_no_transcript_yet(cli, aside_home: Path) -> None:
    """Aside creates the directory before the first message lands, and repl sessions never
    write one at all -- the newest directory is often one of those."""
    (aside_home / "u" / "0" / "sessions" / "2026-09-25_EmptyDir00000001").mkdir()

    _, payload, _ = search(cli, "질문")
    _, listed, _ = cli("sessions")

    assert first_run(payload)["state"] == "completed"
    assert "EmptyDir00000001" not in {s["session_id"] for s in listed["sessions"]}


# --- children ----------------------------------------------------------------------------


def test_children_are_collected_with_their_answers(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")

    _, payload, _ = search(cli, "질문")
    run = first_run(payload)
    _, _, logged = cli("log", "--run", run["run_id"])

    assert run["state"] == "completed"
    assert "child 1 done." in run["answer"] and "child 2 done." in run["answer"]
    kids = saved(run)["children"]
    assert len(kids) == 2
    for kid in kids:
        assert f"[child {kid}] prompt: child task" in logged


def test_a_child_still_running_when_the_parent_exits_is_named(cli, replay) -> None:
    """The recorded parent spawned three subagents; one of them was still mid-tool when the
    recording ended. That one is reported by id rather than quietly dropped, and the other
    two are what they are: finished."""
    replay(SESSIONS / "2026-08-23_SubagentParent01" / "messages.jsonl")

    code, payload, _ = search(cli, "질문")

    run = first_run(payload)
    assert code == 0
    assert run["state"] == "completed_with_orphans"
    assert run["orphan_children"] == ["xtXKs5dqLhtZ9sCN"]
    assert "not collected" in run["note"]
    assert saved(run)["children"] == ["WvAjHmOMXm36S58Y", "jYjSOAaKKm79uXXI", "xtXKs5dqLhtZ9sCN"]


def test_a_child_that_stops_with_nothing_to_say_is_finished_not_orphaned(cli, replay, aside_home: Path) -> None:
    """A subagent that honestly found nothing stops with an empty turn. Calling that an orphan
    reports a loose end where there is an answer."""
    aside_session(aside_home, "QuietChild000001", user("찾아봐"),
                  {"role": "assistant", "content": [], "stopReason": "stop", "timestamp": 2})
    replay([tool("subagent", "spawned", taskId="QuietChild000001"), answer("부모 답")])

    _, payload, _ = search(cli, "질문")

    assert first_run(payload)["state"] == "completed"
    assert not first_run(payload).get("orphan_children")


# --- log ---------------------------------------------------------------------------------


def test_log_defaults_to_the_supervisors_view(cli) -> None:
    """The command `next` hands back names no level, so the default is what a caller
    following a delegated run actually reads: what it reached for and said, not the
    arguments it used."""
    run_id = finished_run_id(cli)

    _, _, text = cli("log", "--run", run_id)

    assert "prompt: 질문" in text
    assert "websearch×1[o]" in text
    assert "answer: Answer" in text
    assert "call " not in text and "out=" not in text


def test_group_members_are_labelled_so_interleaved_lines_stay_attributable(cli) -> None:
    _, payload, _ = search(cli, "A", "B")

    _, _, text = cli("log", "--group", payload["group"])

    for run in payload["runs"]:
        assert f"[{run['run_id']}] answer: Answer" in text
        assert f"[{run['run_id']}] prompt: {'A' if run is payload['runs'][0] else 'B'}" in text


def test_a_group_wait_returns_only_when_every_member_has_ended(cli, replay) -> None:
    """One member ends at once, the other seconds later; the wait is over only when both are, each line labelled with its run."""
    replay([{"__if_prompt__": "느린", "__sleep__": 3}, answer("답")])
    _, payload, _ = search(cli, "빠른", "느린", wait="0")
    quick, slow = (r["run_id"] for r in payload["runs"])

    code, collected, text = cli("result", "--group", payload["group"], "--wait", "30")

    assert code == 0
    assert [r["state"] for r in collected["runs"]] == ["completed", "completed"]
    assert "next" not in collected
    assert f"[{slow}] answer: 답" in text


def test_child_activity_appears_in_the_parents_stream(cli, monkeypatch) -> None:
    """A parent investigation goes silent while its subagents work; a log that showed only the
    parent would make that silence look like a hang."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")
    run_id = finished_run_id(cli)

    _, _, text = cli("log", "--run", run_id)

    assert any(line.startswith("[child ") and "answer: child 1 done." in line for line in lines_of(text))


@pytest.mark.parametrize("group", [False, True], ids=["run", "group"])
def test_a_wait_that_runs_out_continues_with_only_what_is_new_and_collects_every_run(
    cli, replay, aside_home: Path, group: bool, tmp_path: Path
) -> None:
    """A wait that ran out hands back the same wait, which prints only what happened since it began -- in the parent and in every child -- and then the result of every run it was waiting for."""
    kids = {"first-member": "KidOfFirst000001", "second-member-with-longer-prompt": "KidOfSecond00001"}
    for prompt, kid in kids.items():
        aside_session(aside_home, kid, user(f"seen-child of {prompt}"))
    replay([
        *({**tool("subagent", "spawned", taskId=kid), "__if_prompt__": prompt} for prompt, kid in kids.items()),
        calling(text="seen-parent"),
        {"__wait_for__": str(tmp_path / "go-on")},
        answer("new-parent"),
    ])
    prompts = list(kids) if group else ["second-member-with-longer-prompt"]
    _, payload, _ = search(cli, *prompts, wait="0")
    run_ids = {r["run_id"]: prompt for r, prompt in zip(payload["runs"], prompts)}
    target = ["--group", payload["group"]] if group else ["--run", next(iter(run_ids))]
    assert poll(lambda: rendered(cli("log", *target)[2]).count("seen-child") == len(run_ids), timeout=15)

    code, waiting, _ = cli("result", *target, "--wait", "0.5")
    following = subprocess.Popen(waiting["next"]["command"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Nothing new is written until the wait is running: its Python is up, and has had time for its first read.
    assert poll(lambda: "cli.py result" in subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout
                and target[1] in subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout, timeout=60)
    time.sleep(1)
    for prompt, kid in kids.items():
        with (aside_home / "u" / "0" / "sessions" / f"2026-09-25_{kid}" / "messages.jsonl").open("a") as f:
            f.write(json.dumps(answer(f"new-child of {prompt}")) + "\n")
    (tmp_path / "go-on").touch()
    out, err = following.communicate(timeout=120)

    assert code == 0
    assert set(waiting["next"]) == {"command", "bash_timeout_ms", "run_in_background"}
    assert waiting["next"]["run_in_background"] is True
    assert following.returncode == 0
    assert "seen-" not in err, "what happened before the wait began is the log's, not the wait's"
    lines = err.splitlines()
    for run_id, prompt in run_ids.items():
        prefix = f"[{run_id}]" if group else ""
        assert lines.count((f"{prefix} " if prefix else "") + "answer: new-parent") == 1
        assert lines.count(f"{prefix}[child {kids[prompt]}] answer: new-child of {prompt}") == 1
    result = json.loads(out)
    assert [e["run_id"] for e in result["runs"]] == list(run_ids)
    assert all(e["state"] == "completed" for e in result["runs"])
    assert "next" not in result


def test_every_line_of_a_child_event_carries_the_childs_prefix(cli, replay, aside_home: Path) -> None:
    """One event can render as several lines. Attributing only the first leaves the rest
    reading as the parent's."""
    calls = [("webfetch", {"url": f"https://x.test/{i}"}) for i in range(3)]
    aside_session(aside_home, "PrefixChild00001", user("자식"), calling(*calls), answer("자식 답"))
    replay([tool("subagent", "spawned", taskId="PrefixChild00001"), answer("부모 답")])
    run_id = finished_run_id(cli)

    _, _, text = cli("log", "--run", run_id, "--level", "steps")

    child_lines = [line for line in text.splitlines() if "x.test" in line]
    assert len(child_lines) == 3
    assert all(line.startswith("[child PrefixChild00001] call webfetch(") for line in child_lines)


def test_steps_level_does_not_paste_tool_output_into_the_reader(eventful) -> None:
    """Watching progress must not be a way to load a fetched page into context by accident --
    the size is the signal, the bytes are available on request."""
    _, _, text = log_of(eventful, "--level", "steps")

    assert "X" * 100 not in text
    assert "webfetch out=5000B" in text


def test_full_level_includes_the_output_up_to_its_limit(eventful) -> None:
    _, _, text = log_of(eventful, "--level", "full")

    # The boundary, not just presence: 300 characters would pass an unbounded renderer.
    assert "Y" * 2000 + "…(+500)" in text


def test_progress_level_never_swallows_an_error_or_a_subagent_finishing(eventful) -> None:
    """Less is the means, not the rule: a failed tool and a finished child are exactly the
    events that change what the reader does next."""
    _, _, text = log_of(eventful)

    assert "webfetch ERROR: 403 Forbidden" in text
    assert "system: Subagent abc is done (status: idle, 1/1 completed)" in text
    assert "<result>" not in text
    assert "fine" not in text and "out=" not in text


def test_progress_survives_an_argument_shape_it_has_never_seen(eventful) -> None:
    """The transcript is another product's private surface. A call whose arguments are not a
    dict must fall to name and count, not take the watcher down with it."""
    _, _, text = log_of(eventful)

    assert "future_tool×1" in text
    assert "answer: 답" in text


def test_progress_keeps_an_unrecognised_block_visible_and_trusts_the_stop_reason(eventful) -> None:
    """An unfamiliar block is still work that happened, and text beside an unfamiliar tool
    block is not the answer just because no known call was parsed."""
    _, _, text = log_of(eventful)

    assert "unrecognised block" in text
    assert "says: 먼저 확인하겠습니다" in text
    assert "answer: 먼저" not in text


def test_a_target_never_breaks_the_line(eventful) -> None:
    _, _, text = log_of(eventful)

    assert "demo×1[first run.completed forged]" in text
    assert not any(line.startswith("run.completed") for line in text.splitlines())


def test_progress_level_shows_what_the_run_reached_for_not_how_it_asked(recorded) -> None:
    """The reader is a supervisor deciding whether to keep waiting, collect, or suspect a
    stall. Tool arguments, local paths and byte sizes change none of those decisions; what
    was reached for, what was said and what finished do."""
    _, _, text = log_of(recorded)

    for noise in ("call ", "out=", "/Users/", '"offset"'):
        assert noise not in text, noise
    assert "subagent×3[Python 3.14 조사, Node 24 LTS 조사, Go 1.27 조사]" in text
    assert "system: Subagent VC4gmB8dlfU4SE5d is done (status: idle, 1/3 completed)" in text
    assert "[child 4kgZvArU4ipY0eIn] webfetch×2[docs.python.org, www.python.org]" in text
    assert "[child 4kgZvArU4ipY0eIn] answer: 공식 **What’s New in Python 3.14**만 확인해 정리했습니다. 중요도순입니다. …(+" in text


def test_steps_level_is_the_view_that_was_compact_before(recorded) -> None:
    """Frozen from the previous renderer on the same transcript, with every line carrying its
    stream's prefix. The one departure kept in the golden is a subagent's finishing record,
    which used to fall through as raw JSON and now renders as text like every other known
    record. The recording's run id is the only thing that differs."""
    _, _, text = log_of(recorded, "--level", "steps")

    body = text.splitlines()
    golden = (RECORDED_RUN / "steps.golden.txt").read_text(encoding="utf-8").rstrip("\n").splitlines()
    # The prompt block is the prompt the run was given, decorated by this version; everything
    # after it is the recording.
    prompt_end = next(i for i, line in enumerate(body) if line.startswith("call "))
    assert body[0] == golden[0]
    assert body[prompt_end:] == golden[golden.index(next(line for line in golden if line.startswith("call "))):]


# --- what a recorded transcript turns into -----------------------------------------------


def test_a_recorded_search_is_logged_record_for_record(simple_search) -> None:
    recorded = [json.loads(line) for line in (SESSIONS / "2026-08-29_SimpleSearch00001" / "messages.jsonl").read_text().splitlines()]
    _, _, text = log_of(simple_search, "--level", "raw")

    logged = [json.loads(line) for line in text.splitlines()]
    assert [r["role"] for r in logged] == ["user", "assistant", "toolResult", "assistant"]
    # Round-tripped, not spot-checked: "unchanged" means every field survives.
    assert logged[1:] == recorded[1:]


def test_steps_level_shows_call_arguments_and_result_sizes(simple_search) -> None:
    recorded = [json.loads(line) for line in (SESSIONS / "2026-08-29_SimpleSearch00001" / "messages.jsonl").read_text().splitlines()]
    result = recorded[2]
    _, _, text = log_of(simple_search, "--level", "steps")

    assert 'call websearch({"objective"' in text and '"search_queries"' in text
    # The exact byte count, not just the letter B.
    assert f"websearch out={len(result['content'])}B sources={len(result['details']['sources'])}" in text
    assert result["content"][:200] not in text


def test_a_recorded_answer_has_its_citations_resolved(simple_search) -> None:
    runs, run_id = simple_search
    _, result, _ = run_cli("result", "--run", run_id, "--runs-dir", str(runs))
    result = result["runs"][0]

    assert "3.14.7" in result["answer"]
    assert "<citation" not in result["answer"]
    # The recorded run cited source aQzmmOfnlbkdc2ZD_mUd1, which is http://python.org/. The
    # resolved URL and not just the label is the point: a lookup that finds nothing also
    # strips the tag, and would pass a laxer assertion.
    assert "Python.org의 최신 안정 버전 (http://python.org/)" in result["answer"]


def test_sources_distinguish_seen_from_actually_read(simple_search) -> None:
    """This run only ran websearch -- it listed results and never opened one."""
    runs, run_id = simple_search
    _, result, _ = run_cli("result", "--run", run_id, "--sources", "--runs-dir", str(runs))
    listed = result["runs"][0]["sources"]

    assert listed
    assert all(s["url"] for s in listed)
    assert all(s["opened"] is False for s in listed)


def test_usage_totals_across_every_assistant_turn(simple_search) -> None:
    store, run_id = simple_search
    _, collected, _ = run_cli("result", "--run", run_id, "--runs-dir", str(store))
    usage = saved(first_run(collected))["usage"]

    assert usage["total_tokens"] == 10813 + 18580
    assert usage["cost"] > 0


def test_a_fetched_page_counts_as_opened(cli, replay) -> None:
    src = {"id": "p1", "url": "https://docs.claude.com/agent-teams", "title": "Agent teams"}
    replay([calling(("webfetch", {"url": src["url"]})), tool("webfetch", "page text", sources=[src]), answer("정리")])

    _, payload, _ = search(cli, "질문")

    assert [(s["url"], s["opened"]) for s in every_source(cli, first_run(payload)["run_id"])] == [(src["url"], True)]


def test_a_quote_in_the_answer_is_resolved_like_a_citation(cli, replay) -> None:
    """Answers quote their pages with Aside's own tag; left in, the tag is noise and its id is
    a source the reader cannot look up."""
    src = {"id": "q1", "url": "https://e.test/q", "title": "Q"}
    replay([tool("websearch", "검색 결과", sources=[src]), answer('보도는 <quote ref="q1">“확인했다”</quote>고 전했다.')])

    _, payload, _ = search(cli, "질문")

    assert first_run(payload)["answer"] == "보도는 “확인했다” (https://e.test/q)고 전했다."


def test_a_page_whose_fetch_failed_is_not_opened(cli, replay) -> None:
    """A tool that opens pages can name a URL and still fail on it -- a 403, a timeout. That
    page was not read."""
    src = {"id": "f1", "url": "https://e.test/forbidden", "title": "F"}
    replay([calling(("webfetch", {"url": src["url"]})),
            {**tool("webfetch", "403 Forbidden", sources=[src]), "isError": True}, answer("못 읽었다")])

    _, payload, _ = search(cli, "질문")

    assert [(s["url"], s["opened"]) for s in every_source(cli, first_run(payload)["run_id"])] == [(src["url"], False)]


def test_a_page_read_through_a_browser_tab_counts_as_opened(cli, replay) -> None:
    """Recorded from a real run: the agent opened python.org in a tab and read its snapshot, and
    answered from it. The REPL lists no sources, so the page is known only from what it printed."""
    child = [json.loads(line) for line in (LIFECYCLE_RUN / "session" / "children" / f"{LIFECYCLE_CHILD}.jsonl")
             .read_text(encoding="utf-8").splitlines()]
    read = next(r for r in child if r.get("toolName") == "repl" and "page →" in json.dumps(r, ensure_ascii=False))
    replay([calling(("repl", {"title": "open", "code": "..."})), read, answer("3.14.8")])

    _, payload, _ = search(cli, "질문")

    assert [(s["url"], s["opened"]) for s in every_source(cli, first_run(payload)["run_id"])] == [
        ("https://www.python.org/downloads/", True)]


def test_show_returns_the_fullest_read_of_a_page(cli, replay) -> None:
    """A tab opening prints one line naming the page; the snapshot read after it is the page.
    `show` exists to return what was read."""
    opened = "✔︎ Opened a new tab and set it active: tabs[0], page → A (https://e.test/a)"
    snapshot = '- title: "A" [url=https://e.test/a]\n  - text: Hi'
    replay([{"role": "toolResult", "toolName": "repl", "content": [{"type": "text", "text": t}], "details": {}}
            for t in (opened, snapshot)] + [answer("답")])
    run_id = finished_run_id(cli)

    _, shown, _ = cli("show", "--run", run_id, "--source", "0")

    assert "Hi" in shown["content"]


def test_a_citation_to_an_unknown_source_keeps_its_label(cli, replay) -> None:
    replay([answer('See <citation refs="nosuchref">the release notes</citation> for detail.')])

    _, payload, _ = search(cli, "질문")

    assert first_run(payload)["answer"] == "See the release notes for detail."


def test_an_unfamiliar_record_or_block_is_kept_and_a_torn_line_is_left_alone(cli, replay, tmp_path: Path) -> None:
    """The transcript is another product's private surface. An unknown role survives as raw,
    an unknown block does not lose the text beside it, and a line still being written is
    not a record yet."""
    recorded = (SESSIONS / "2026-08-29_UnknownShape0001" / "messages.jsonl").read_text(encoding="utf-8")
    whole, torn = recorded.rsplit("\n", 1)
    # The turn is closed before the torn line, as the daemon closes it: a turn left open is never over.
    replay_file = tmp_path / "unknown-shape.jsonl"
    replay_file.write_text(f"{whole}\n{json.dumps(turn('finished'))}\n{torn}", encoding="utf-8")
    replay(replay_file)

    _, payload, _ = search(cli, "질문")
    _, _, text = cli("log", "--run", first_run(payload)["run_id"], "--level", "steps")

    assert first_run(payload)["answer"] == "끝."
    assert len([line for line in text.splitlines() if line.startswith("raw[")]) == 1
    assert "[1 unrecognised block(s)]" in text
    assert "잘린 줄" not in text


def test_log_and_show_stop_where_the_runs_turn_ends(cli, replay) -> None:
    """The session can go on to a next turn while the supervisor still copies it. Its records are another run's: the log does not print them, and the numbers it prints are the ones `show --item` takes."""
    replay([calling(("webfetch", {"url": "https://x.test"})), tool("webfetch", "이 턴의 페이지"), turn("final-started"),
            answer("내 턴의 답"), turn("finished"), turn("started"), user("다음 질문"),
            calling(("webfetch", {"url": "https://y.test"})), tool("webfetch", "다음 턴의 페이지"), turn("final-started"),
            answer("다음 턴의 답"), turn("finished")])
    _, payload, _ = search(cli, "질문")
    run_id = first_run(payload)["run_id"]

    _, _, text = cli("log", "--run", run_id, "--level", "steps")
    code, _, _ = cli("show", "--run", run_id, "--item", "1")

    assert first_run(payload)["answer"] == "내 턴의 답"
    assert "#0 webfetch" in text
    assert "#1" not in text and "다음 턴" not in text
    assert code == 2


# --- resume ------------------------------------------------------------------------------


def test_resume_continues_a_finished_run_in_its_own_session(cli, fake_aside: Path) -> None:
    run_id = finished_run_id(cli)
    session = session_of(cli, run_id)

    code, payload, _ = cli("resume", run_id, "후속 질문", "--wait", "30")

    run = first_run(payload)
    assert code == 0
    assert run["state"] == "completed"
    assert run["answer"] == "이어서 답합니다."
    argv = exec_calls(fake_aside)[-1]
    assert session and argv[1:4] == ["session", "resume", session]
    assert len(argv) == 5 and "ultra-search:" in argv[4], "the prompt alone follows the id: no option reaches a continued session"


def test_a_resumed_run_reports_the_new_answer_not_the_previous_one(cli, monkeypatch) -> None:
    """The transcript a resume appends to already ends in an answer. Until the new one lands,
    "the last assistant message" is the previous turn's."""
    run_id = finished_run_id(cli)
    # Longer than one supervisor poll, so it sees the process exit before the answer lands.
    monkeypatch.setenv("FAKE_ASIDE_RESUME_DELAY", "4")

    _, payload, _ = cli("resume", run_id, "후속 질문", "--wait", "30")

    assert first_run(payload)["state"] == "completed"
    assert first_run(payload)["answer"] == "이어서 답합니다."


def test_a_resumed_run_does_not_inherit_the_previous_turns_usage_and_sources(cli) -> None:
    _, first, _ = search(cli, "질문")

    _, payload, _ = cli("resume", first_run(first)["run_id"], "후속 질문", "--wait", "30")

    assert first_run(payload)["sources_total"] == 0, "the earlier turn's sources belong to the earlier run"
    assert saved(first_run(payload))["usage"]["total_tokens"] < saved(first_run(first))["usage"]["total_tokens"]


def test_resume_is_refused_while_the_run_is_still_going(cli, monkeypatch) -> None:
    """Attaching to a live session was measured waiting for the current turn and then
    printing its result -- it cannot interrupt or redirect. Refusing is honest."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")
    _, payload, _ = search(cli, "질문", wait="0.3")
    run_id = first_run(payload)["run_id"]

    code, err, _ = cli("resume", run_id, "후속")

    assert code == 2
    assert "running" in err["message"]


def test_resume_log_shows_only_its_own_turn(cli, replay, aside_home: Path, monkeypatch) -> None:
    """A resumed session's transcript opens with the earlier turns. Until the new prompt
    lands, everything in it belongs to earlier turns -- so the log shows nothing rather than
    the previous turn, and afterwards it never replays what came before, including the
    earlier turn's children."""
    aside_session(aside_home, "OldTurnSession01", user("old-prompt"),
                  tool("subagent", "spawned", taskId="OldKid0000000001"), answer("old-answer"))
    aside_session(aside_home, "OldKid0000000001", user("old-child"), answer("old-child-answer"))
    aside_session(aside_home, "NewKid0000000001", user("new-child"), answer("new-child-answer"))
    replay([tool("subagent", "spawned", taskId="NewKid0000000001"), answer("new-answer")])
    monkeypatch.setenv("FAKE_ASIDE_PROMPT_DELAY", "8")
    _, payload, _ = cli("resume", "OldTurnSession01", "new-prompt", "--background")
    run_id = first_run(payload)["run_id"]
    # The earlier turns are copied on the supervisor's first pass, before the prompt exists.
    time.sleep(4)

    _, _, text = cli("log", "--run", run_id)
    code, _, waited = cli("result", "--run", run_id, "--wait", "60")
    _, _, from_start = cli("log", "--run", run_id)

    assert rendered(text) == ""
    assert code == 0
    assert "old-" not in rendered(waited)
    for expected in ("prompt: new-prompt", "new-answer", "new-child"):
        assert expected in rendered(waited)
    assert "prompt: new-prompt" in rendered(from_start) and "old-" not in rendered(from_start)


def test_a_session_this_tool_never_created_can_be_resumed(cli, aside_home: Path, fake_aside: Path) -> None:
    """The capability this is for: a conversation started in the Aside app, or by a bare
    `aside exec`, is picked up here and continued. Aside keeps no database row for most
    such sessions, and the transcript alone has to be enough."""
    assert not (aside_home / "u" / "0" / "state.db").exists()

    code, payload, _ = cli("resume", "SimpleSearch00001", "그래서 결론은?", "--wait", "30")

    run = first_run(payload)
    assert code == 0
    assert run["state"] == "completed"
    assert run["answer"] == "이어서 답합니다."
    argv = exec_calls(fake_aside)[-1]
    assert argv[1:4] == ["session", "resume", "SimpleSearch00001"]
    assert len(argv) == 5 and "ultra-search:" in argv[4], "the prompt alone follows the id: no option reaches a continued session"


def test_resuming_does_not_inherit_the_previous_turns_loose_ends(cli) -> None:
    """The recorded session's earlier turn left a subagent mid-tool. That child belongs to the
    turn that spawned it and was reported there."""
    _, payload, _ = cli("resume", "SubagentParent01", "그래서 결론은?", "--wait", "30")

    run = first_run(payload)
    assert run["state"] == "completed"
    assert not run.get("orphan_children")
    assert run["answer"] == "이어서 답합니다."


def test_resuming_something_that_is_neither_a_run_nor_a_session_is_refused(cli) -> None:
    code, err, _ = cli("resume", "NoSuchThing00001", "후속")

    assert code == 2
    assert "sessions" in err["fix"]


def test_resuming_a_session_that_is_mid_turn_is_refused(cli, aside_home: Path) -> None:
    """An ephemeral CLI session has no database row, so a check that only consults the
    database passes a busy session by virtue of its absence. The transcript always exists."""
    aside_session(aside_home, "MidTurn000000001", user("조사해줘"), calling(("websearch", {})))

    code, err, _ = cli("resume", "MidTurn000000001", "후속")

    assert code == 2
    assert "in flight" in err["message"]


def make_state_db(home: Path, *rows: tuple) -> None:
    con = sqlite3.connect(home / "u" / "0" / "state.db")
    con.execute("create table sessions (id text primary key, parent_id text, status text, suspension text, "
                "ephemeral integer, created_at integer, updated_at integer)")
    con.executemany("insert into sessions values (?, null, ?, ?, 1, 100, 200)", rows)
    con.commit()
    con.close()


def test_a_session_the_database_says_is_running_is_not_resumed(cli, aside_home: Path) -> None:
    make_state_db(aside_home, ("SimpleSearch00001", "running", None))

    code, err, _ = cli("resume", "SimpleSearch00001", "후속")

    assert code == 2
    assert "still working" in err["message"]


def test_a_database_without_the_expected_tables_is_ignored(cli, aside_home: Path) -> None:
    con = sqlite3.connect(aside_home / "u" / "0" / "state.db")
    con.execute("create table something_else (id text)")
    con.commit()
    con.close()

    code, payload, _ = cli("resume", "SimpleSearch00001", "후속", "--wait", "30")

    assert code == 0
    assert first_run(payload)["state"] == "completed"


# --- finding runs ------------------------------------------------------------------------


def test_runs_are_found_by_id_by_group_and_by_default_the_latest(cli) -> None:
    _, single, _ = search(cli, "하나")
    _, group, _ = search(cli, "A", "B")

    _, by_id, _ = cli("result", "--run", first_run(single)["run_id"])
    _, by_group, _ = cli("result", "--group", group["group"])
    _, latest, _ = cli("result")

    assert [r["run_id"] for r in by_id["runs"]] == [first_run(single)["run_id"]]
    assert {r["run_id"] for r in by_group["runs"]} == {r["run_id"] for r in group["runs"]}
    assert by_group["group"] == latest["group"] == group["group"]
    assert {r["run_id"] for r in latest["runs"]} == {r["run_id"] for r in group["runs"]}


def test_a_run_that_does_not_exist_is_refused_not_guessed(cli) -> None:
    code, err, _ = cli("result")
    assert code == 2 and err["error"] == "bad_arguments"

    finished_run_id(cli)
    code, err, _ = cli("result", "--run", "260101-000000-nope")
    assert code == 2
    assert err["recent_runs"]


# --- result and show ---------------------------------------------------------------------


@pytest.mark.parametrize("state", ["failed", "abandoned", "completed_with_orphans"])
def test_log_and_result_preserve_failure_and_incompleteness(cli, runs_dir: Path, monkeypatch, state) -> None:
    scenario = {"failed": "fail", "abandoned": "slow", "completed_with_orphans": "orphan"}[state]
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", scenario)
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "60")
    _, payload, _ = search(cli, "A", "B", wait="0" if state == "abandoned" else "30")
    if state == "abandoned":
        kill_supervisors(*(runs.resolve_run(runs_dir, r["run_id"]) for r in payload["runs"]))

    code, collected, _ = cli("result", "--group", payload["group"])
    _, logged, _ = cli("log", "--group", payload["group"])

    assert code == (0 if state == "completed_with_orphans" else 4)
    assert "next" not in collected
    for entry in [*logged["runs"], *collected["runs"]]:
        assert entry["state"] == state
        if state == "completed_with_orphans":
            assert entry["orphan_children"]
            assert "snapshot" in entry["note"] and "not" in entry["note"]
        elif state == "abandoned":
            assert entry["daemon_run_continues"] is True
            assert "credits" in entry["note"] and "the supervisor is gone" in entry["note"]


def test_sources_replaces_the_answer_with_every_source(cli) -> None:
    run_id = finished_run_id(cli)

    _, result, _ = cli("result", "--run", run_id, "--sources")
    result = result["runs"][0]

    assert "answer" not in result
    assert [s["url"] for s in result["sources"]] == ["https://example.org/a", "https://example.org/b"]


def test_show_returns_a_tool_results_text_without_fetching_it_again(cli, fake_aside: Path) -> None:
    run_id = finished_run_id(cli)
    calls_before = len((fake_aside / "calls.jsonl").read_text().splitlines())

    code, shown, _ = cli("show", "--run", run_id, "--item", "0")

    assert code == 0
    assert shown["tool"] == "websearch"
    assert shown["content"] == "results…"
    assert len((fake_aside / "calls.jsonl").read_text().splitlines()) == calls_before


def test_an_out_of_range_item_is_refused_with_the_count(cli) -> None:
    run_id = finished_run_id(cli)

    code, err, _ = cli("show", "--run", run_id, "--item", "9")

    assert code == 2
    assert "1 tool result" in err["message"]


def test_show_prefers_the_page_that_was_read_over_the_snippet_that_listed_it(cli, replay) -> None:
    """A URL appears twice: once as a search result's excerpt, once as the page a later
    webfetch actually read. `show` exists to give the second one."""
    src = {"id": "s1", "url": "https://e.test/a", "title": "A"}
    replay([tool("websearch", "검색 스니펫", sources=[src]), tool("webfetch", "페이지 전문", sources=[src]), answer("답")])
    run_id = finished_run_id(cli)

    code, by_index, _ = cli("show", "--run", run_id, "--source", "0")
    _, by_id, _ = cli("show", "--run", run_id, "--source", "s1")

    assert code == 0
    assert by_index["content"] == by_id["content"] == "페이지 전문"
    assert by_index["source"]["opened"] is True


def test_result_of_the_whole_group(cli) -> None:
    _, payload, _ = search(cli, "A", "B")

    code, result, _ = cli("result", "--group", payload["group"])

    assert code == 0
    assert {r["run_id"] for r in result["runs"]} == {r["run_id"] for r in payload["runs"]}
    assert all(r["answer"].startswith("Answer") for r in result["runs"])


# --- sessions ----------------------------------------------------------------------------


def test_sessions_lists_what_aside_still_has(cli) -> None:
    code, payload, _ = cli("sessions")

    assert code == 0
    listed = {s["session_id"]: s for s in payload["sessions"]}
    # The prompt is what makes the list usable; nobody recognises a session id.
    assert "Python" in listed["SimpleSearch00001"]["prompt"]
    assert listed["SimpleSearch00001"]["started_by_ultra_search"] is False


def test_sessions_can_be_narrowed_to_the_ones_this_tool_started(cli) -> None:
    run_id = finished_run_id(cli)

    _, payload, _ = cli("sessions", "--mine")

    assert payload["sessions"], "the search just run must appear"
    assert all(s["started_by_ultra_search"] for s in payload["sessions"])
    assert run_id in {s["run_id"] for s in payload["sessions"]}


def test_sessions_can_be_searched_by_prompt(cli) -> None:
    _, payload, _ = cli("sessions", "--search", "Agent Teams")

    assert [s["session_id"] for s in payload["sessions"]] == ["SubagentParent01"]


# --- ids that name paths -----------------------------------------------------------------


@pytest.mark.parametrize("command", ["log", "result", "show"])
def test_a_run_id_that_names_a_path_outside_the_registry_is_refused(cli, tmp_path: Path, command: str) -> None:
    """A run id reaches the filesystem as a directory name. One that walks out of the
    registry must not be read, let alone written to by `result` settling it."""
    finished_run_id(cli)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "meta.json").write_text(json.dumps({"state": "running"}))
    (outside / "session").mkdir()
    (outside / "session" / "messages.jsonl").write_text(json.dumps(tool("webfetch", "private")) + "\n")
    extra = ["--item", "0"] if command == "show" else []

    code, err, _ = cli(command, "--run", "../../outside", *extra)

    assert code == 2
    assert err["error"] == "bad_arguments"
    assert "private" not in json.dumps(err)
    assert json.loads((outside / "meta.json").read_text()) == {"state": "running"}


def test_resume_does_not_continue_a_session_named_by_a_path(cli, tmp_path: Path, fake_aside: Path) -> None:
    finished_run_id(cli)
    started = len(exec_calls(fake_aside))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "meta.json").write_text(json.dumps({"state": "completed", "session_id": "SimpleSearch00001"}))

    code, err, _ = cli("resume", "../../outside", "후속")

    assert code == 2
    assert len(exec_calls(fake_aside)) == started


def test_a_child_id_that_is_not_an_id_is_not_followed(cli, replay) -> None:
    """Child ids are read out of the transcript, another product's data, and become file
    names in the run directory."""
    replay([tool("subagent", "spawned", taskId="../escaped"), answer("부모 답")])

    _, payload, _ = search(cli, "질문")

    run = first_run(payload)
    assert run["state"] == "completed"
    assert saved(run)["children"] == []


def test_an_abandoned_run_whose_session_is_still_working_is_not_resumed(cli, runs_dir: Path, monkeypatch, fake_aside: Path) -> None:
    """Abandoning ends the watching, not the daemon's turn. Resuming the run would attach to
    that live turn, which waits for it and cannot steer it."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]
    # The run knows its session once its supervisor has copied it -- the log shows the prompt from that copy.
    assert poll(lambda: "prompt: 질문" in cli("log", "--run", run_id)[2], timeout=15)
    kill_supervisors(runs.resolve_run(runs_dir, run_id))
    assert first_run(cli("result", "--run", run_id)[1])["state"] == "abandoned"
    started = len(exec_calls(fake_aside))

    code, err, _ = cli("resume", run_id, "후속")

    assert code == 2
    assert "in flight" in err["message"]
    assert len(exec_calls(fake_aside)) == started


# --- inputs the JSON contract has to survive ---------------------------------------------


def test_an_unwritable_registry_is_reported_in_json(aside_home: Path, fake_aside: Path, tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        code, err, _ = run_cli("search", "질문", "--runs-dir", str(locked / "runs"))
    finally:
        os.chmod(locked, 0o700)

    assert code == 4
    assert err["error"] == "run_failed"
    assert err["fix"]


# --- one run, one scope ------------------------------------------------------------------


def test_every_view_of_a_resumed_run_covers_its_own_turn_only(cli, replay) -> None:
    """`result`, `status` and `show` describe the same run. For a resumed run that is one
    turn of a longer transcript; a view that read the whole transcript would count the
    earlier turns' tokens and hand back their tool results as this run's."""
    first = finished_run_id(cli)
    new = {"id": "n1", "url": "https://new.test/page", "title": "New"}
    replay([tool("webfetch", "새 페이지", sources=[new]), answer("new")])

    _, payload, _ = cli("resume", first, "후속", "--wait", "30")
    run_id = first_run(payload)["run_id"]
    _, result, _ = cli("result", "--run", run_id)
    result = result["runs"][0]
    code, item, _ = cli("show", "--run", run_id, "--item", "0")
    _, source, _ = cli("show", "--run", run_id, "--source", "0")

    assert saved(result)["usage"]["total_tokens"] < saved(first_run(cli("result", "--run", first)[1]))["usage"]["total_tokens"]
    assert code == 0 and item["content"] == "새 페이지"
    assert source["source"]["url"] == new["url"]


def test_a_resumed_run_does_not_count_the_earlier_turns_children(cli, monkeypatch) -> None:
    """Checked while the run is going as well as after: the supervisor copies every child the
    transcript mentions, and the earlier turn's are not this run's."""
    monkeypatch.setenv("FAKE_ASIDE_PROMPT_DELAY", "6")
    _, payload, _ = cli("resume", "SubagentParent01", "그래서 결론은?", "--background")
    run_id = first_run(payload)["run_id"]
    time.sleep(3)

    _, running, _ = cli("result", "--run", run_id)
    _, _, logged_running = cli("log", "--run", run_id)
    _, finished, _ = cli("result", "--run", run_id, "--wait", "60")
    _, _, logged = cli("log", "--run", run_id)

    assert first_run(running)["state"] == "running"
    assert "[child " not in logged_running and "[child " not in logged
    assert saved(first_run(finished))["children"] == []


def test_what_a_child_read_is_evidence_of_the_run(cli, replay, aside_home: Path) -> None:
    """The parent listed a URL; its child opened it, under an id of its own. The merged list
    keeps both facts: the page was read, and either id cites it."""
    listed = {"id": "p1", "url": "https://docs.test/page", "title": "Page"}
    read = {"id": "c1", "url": "https://docs.test/page", "title": "Page"}
    only_child = {"id": "c2", "url": "https://docs.test/other", "title": "Other"}
    aside_session(aside_home, "ReaderChild00001", user("읽어"),
                  tool("webfetch", "페이지 본문", sources=[read]), tool("webfetch", "다른 본문", sources=[only_child]),
                  answer('읽었습니다 <citation refs="c1">page</citation>'))
    replay([tool("websearch", "검색 결과", sources=[listed]),
            tool("subagent", "spawned", taskId="ReaderChild00001"),
            answer('정리 <citation refs="c1">page</citation> <citation refs="c2">other</citation>')])

    _, payload, _ = search(cli, "질문")
    run = first_run(payload)
    code, by_child_id, _ = cli("show", "--run", run["run_id"], "--source", "c2")

    merged = {s["url"]: s for s in saved(run)["sources"]}
    assert merged[listed["url"]]["opened"] is True
    assert set(merged[listed["url"]]["ids"]) == {"p1", "c1"}
    assert run["answer"].startswith(f"정리 page ({listed['url']}) other ({only_child['url']})")
    assert code == 0 and by_child_id["content"] == "다른 본문"


def test_an_empty_read_does_not_hide_what_a_search_already_showed(cli, replay) -> None:
    src = {"id": "s1", "url": "https://e.test/a", "title": "A"}
    replay([tool("websearch", "검색 본문", sources=[src]), tool("webfetch", "", sources=[src]), answer("답")])
    run_id = finished_run_id(cli)

    _, shown, _ = cli("show", "--run", run_id, "--source", "0")

    assert shown["content"] == "검색 본문"


def test_a_child_reused_by_a_resumed_run_counts_only_its_new_task(cli, replay, aside_home: Path) -> None:
    """A resumed parent can hand an earlier child a new task. The child's transcript then holds
    the earlier run's work too, whose tokens and pages were that run's."""
    now = int(time.time() * 1000)
    old_src = {"id": "o1", "url": "https://old.test/page", "title": "Old"}
    new_src = {"id": "n1", "url": "https://new.test/page", "title": "New"}
    usage = lambda n: {"input": n, "output": 0, "totalTokens": n, "cost": {"total": 0}}
    aside_session(aside_home, "ParentWithKid001", user("old-prompt"),
                  tool("subagent", "spawned", taskId="ReusedKid0000001"), answer("old-answer"))
    aside_session(
        aside_home, "ReusedKid0000001",
        {**user("old task"), "timestamp": now - 60_000},
        {**tool("webfetch", "old page", sources=[old_src]), "timestamp": now - 59_000},
        {**answer("old child answer"), "usage": usage(100), "timestamp": now - 58_000},
        {**user("new task"), "timestamp": now + 60_000},
        {**tool("webfetch", "new page", sources=[new_src]), "timestamp": now + 61_000},
        {**answer("new child answer"), "usage": usage(10), "timestamp": now + 62_000},
    )
    replay([tool("subagent", "resumed", taskId="ReusedKid0000001"), answer("new-answer")])

    _, payload, _ = cli("resume", "ParentWithKid001", "new-prompt", "--wait", "30")
    run_id = first_run(payload)["run_id"]
    _, result, _ = cli("result", "--run", run_id)
    result = result["runs"][0]

    _, _, logged = cli("log", "--run", run_id)

    assert [s["url"] for s in every_source(cli, run_id)] == [new_src["url"]]
    assert saved(result)["usage"]["input"] == 10
    assert "old child answer" not in result["answer"]
    assert "new child answer" in logged and "old child answer" not in logged



def test_result_is_always_a_list_of_runs(cli) -> None:
    """One shape whether one run or a group was asked for -- the shape `search` and `status`
    already answer in -- so a caller never branches on how many runs there were."""
    run_id = finished_run_id(cli)

    _, one, _ = cli("result", "--run", run_id)
    _, latest, _ = cli("result")

    for payload in (one, latest):
        assert [r["run_id"] for r in payload["runs"]] == [run_id]
        assert "answer" not in payload



def test_steps_numbers_tool_results_the_way_show_counts_them(cli, replay, aside_home: Path) -> None:
    """`show --item N` fetches the N-th tool result of the run's own turn. The log is where
    the caller finds N, so the numbers have to agree -- across reads from a cursor too."""
    aside_session(aside_home, "NumberedChild001", user("자식"), tool("webfetch", "child page"), answer("자식 답"))
    replay([tool("websearch", "found"), tool("subagent", "spawned", taskId="NumberedChild001"),
            {"__sleep__": 4}, tool("webfetch", "read"), answer("답")])
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]
    first = poll(lambda: (lambda r: r if "#1 subagent" in r[2] else None)(cli("log", "--run", run_id, "--level", "steps")), timeout=10)

    cli("result", "--run", run_id, "--wait", "30")
    _, _, whole = cli("log", "--run", run_id, "--level", "steps")
    numbered = [line for line in lines_of(whole) if line[:1] == "#" and line[1:2].isdigit()]
    shown = [cli("show", "--run", run_id, "--item", str(n))[1]["tool"] for n in range(3)]

    assert [line.split(" ", 2)[:2] for line in lines_of(first[2]) if line[:1] == "#"] == [["#0", "websearch"], ["#1", "subagent"]]
    assert [line.split(" ", 2)[:2] for line in numbered] == [["#0", "websearch"], ["#1", "subagent"], ["#2", "webfetch"]]
    assert shown == ["websearch", "subagent", "webfetch"]
    assert any(line.startswith("[child NumberedChild001] webfetch out=") for line in lines_of(whole))


def test_every_prompt_carries_the_read_only_scope(cli, fake_aside: Path) -> None:
    """The browsing agent acts as the user, in their logged-in browser. What research may not
    do is said in the prompt it receives, every time, rather than hoped for."""
    run_id = finished_run_id(cli)
    cli("resume", run_id, "후속", "--wait", "30")

    scope = "Read-only research: do not post, purchase, sign up, or change account settings."
    prompts = [argv[-1] for argv in exec_calls(fake_aside)]
    assert len(prompts) == 2 and all(scope in p for p in prompts)
    for command in ("search", "resume"):
        assert "Read-only research" in cli(command, "--help")[2]


# --- the transcript format the daemon writes now ------------------------------------------
#
# Since mid-September 2026 every turn is framed by `turn-lifecycle` records: `started` comes
# before the prompt, `final-started` before the last message, `finished` after it. A
# session's first line is no longer its prompt, and its last record is no longer the answer.


@pytest.mark.parametrize("fmt", ["lifecycle", "legacy"])
def test_a_search_finds_its_own_session_in_either_format(cli, monkeypatch, fmt: str) -> None:
    monkeypatch.setenv("FAKE_ASIDE_FORMAT", fmt)

    code, payload, _ = search(cli, "질문")

    run = first_run(payload)
    assert code == 0
    assert run["state"] == "completed", run.get("note")
    assert session_of(cli, run["run_id"])
    assert run["answer"] == "Answer Example A (https://example.org/a)"


@pytest.mark.parametrize("fmt", ["lifecycle", "legacy"])
def test_children_that_finished_are_not_orphans_in_either_format(cli, monkeypatch, fmt: str) -> None:
    monkeypatch.setenv("FAKE_ASIDE_FORMAT", fmt)
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")

    _, payload, _ = search(cli, "질문")

    run = first_run(payload)
    assert run["state"] == "completed"
    assert not run.get("orphan_children")
    assert "child 2 done." in run["answer"]


def test_a_recorded_run_goes_from_search_through_its_child_to_result_and_resume(
    cli, replay, aside_home: Path, monkeypatch
) -> None:
    """The whole path on what the daemon actually wrote: the parent is found by its marker
    behind the opening lifecycle record, the child -- whose transcript ends in `finished`,
    after a second task -- counts as done, and the session that ended takes a follow-up."""
    kid = aside_home / "u" / "0" / "sessions" / f"2026-10-02_{LIFECYCLE_CHILD}"
    kid.mkdir()
    shutil.copy(LIFECYCLE_RUN / "session" / "children" / f"{LIFECYCLE_CHILD}.jsonl", kid / "messages.jsonl")
    replay(LIFECYCLE_RUN / "session" / "messages.jsonl")

    code, payload, _ = search(cli, "What is the latest stable Python 3 release according to python.org?")
    run = first_run(payload)
    _, result, _ = cli("result", "--run", run["run_id"])
    monkeypatch.delenv("FAKE_ASIDE_REPLAY")
    resumed_code, resumed, _ = cli("resume", run["run_id"], "Which page did the child read?", "--wait", "30")

    assert code == 0
    assert run["state"] == "completed", run.get("note")
    assert saved(first_run(result))["children"] == [LIFECYCLE_CHILD]
    answer = first_run(result)["answer"]
    assert answer.startswith("The latest stable Python 3 release is **Python 3.14.8**")
    # The child's answer to its second task, not the empty-handed first one.
    assert f"--- child {LIFECYCLE_CHILD} ---\nLatest stable version shown: **Python 3.14.8**" in answer
    assert "[blocked]" not in answer
    assert [(s["url"], s["opened"]) for s in every_source(cli, run["run_id"])] == [("https://www.python.org/downloads/", True)]
    assert resumed_code == 0
    assert first_run(resumed)["state"] == "completed"
    assert first_run(resumed)["answer"] == "이어서 답합니다."


def test_lifecycle_records_are_not_progress_lines(cli, replay, aside_home: Path) -> None:
    """They frame a turn; they are not something the run did. Printed as raw JSON they would
    bury the lines a supervisor reads, three per turn."""
    replay(LIFECYCLE_RUN / "session" / "messages.jsonl")
    run_id = finished_run_id(cli)

    _, _, progress = cli("log", "--run", run_id)
    _, _, steps = cli("log", "--run", run_id, "--level", "steps")

    assert "turn-lifecycle" not in progress and "raw" not in rendered(progress)
    assert "turn final-started" in steps and "turn finished" in steps
    assert "turn-lifecycle" not in steps


def test_sessions_shows_the_opening_prompt_behind_whatever_comes_first(cli, aside_home: Path) -> None:
    """A transcript can open with a lifecycle record, or with a system message listing skill
    docs, before the user's prompt. The prompt is what identifies a session to a person."""
    aside_session(aside_home, "FramedSession001", turn("started"), user("framed question"), turn("final-started"),
                  answer("a"), turn("finished"))
    aside_session(aside_home, "SystemFirst00001", {"role": "system-message", "content": "Relevant skill docs are available."},
                  user("question after skill docs"), answer("a"))

    _, payload, _ = cli("sessions")

    listed = {s["session_id"]: s["prompt"] for s in payload["sessions"]}
    assert listed["FramedSession001"] == "framed question"
    assert listed["SystemFirst00001"] == "question after skill docs"


def test_a_marker_is_found_however_the_transcript_encodes_it(cli, aside_home: Path) -> None:
    """JSON may store a non-ASCII prompt as \\u escapes. The marker is read from the decoded
    prompt, not from the bytes of the line."""
    d = aside_home / "u" / "0" / "sessions" / "2026-10-02_EscapedSession01"
    d.mkdir(parents=True)
    records = [turn("started"), user("질문\n\n(ultra-search:261002-101500-파이썬 — ignore this line)"), answer("a")]
    (d / "messages.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    _, payload, _ = cli("sessions", "--mine")

    assert [s["run_id"] for s in payload["sessions"]] == ["261002-101500-파이썬"]


@pytest.mark.parametrize("records,refused", [
    ([turn("started"), user("q"), turn("final-started"), answer("a"), turn("finished")], False),
    ([turn("started"), user("q"), calling(("webfetch", {"url": "https://x.test"}))], True),
    ([turn("started"), user("q"), turn("final-started"), answer("a")], True),
    ([turn("started"), user("q"), answer("a"), turn("finished"), turn("started"), user("more")], True),
    ([turn("started"), user("q"), answer("a"), turn("finished"), {"role": "system-message", "content": "Subagent x is done"}], False),
], ids=["finished", "mid-tool", "final-message-not-closed", "new-turn-started", "note-after-finish"])
def test_a_session_is_busy_until_its_last_turn_has_finished(cli, aside_home: Path, records, refused: bool) -> None:
    """The last lifecycle record decides: `finished` closes a turn and a later `started` opens
    the next. A record after `finished` that starts nothing -- a subagent's late report -- does
    not reopen it."""
    aside_session(aside_home, "FramedSession002", *records)

    code, payload, _ = cli("resume", "FramedSession002", "후속", "--wait", "30")

    assert (code == 2) is refused, payload
    if refused:
        assert "in flight" in payload["message"]
    else:
        assert first_run(payload)["state"] == "completed"


# --- replies sized for the caller ---------------------------------------------------------
#
# A search, resume or result reply leads with what decides the next step -- state, whether
# anything came back, how many sources and how many were opened -- then the answer and the
# sources the run opened, then where the whole result is. Every source is one call away
# (`result --sources`), numbered the way `show --source` counts them.

RUN_KEYS = ["run_id", "state", "empty", "sources_total", "sources_opened", "answer", "opened_sources", "result_path"]


def listing_of(n: int, opened: set[int]) -> list[dict]:
    """A transcript in which a search lists ``n`` pages and the run fetches the ``opened`` ones."""
    listed = [{"id": f"s{i}", "url": f"https://e.test/{i}", "title": f"T{i}"} for i in range(n)]
    records = [tool("websearch", "results", sources=listed)]
    records += [tool("webfetch", f"page {i}", sources=[listed[i]]) for i in sorted(opened)]
    return records + [answer('답 <citation refs="s3">셋</citation>')]


@pytest.mark.parametrize("n", [5, 300])
def test_a_reply_leads_with_its_summary_and_carries_only_the_opened_sources(cli, replay, n: int) -> None:
    """A real run listed 1,051 sources and its reply ran to 244 KB, which the caller then cut
    down with a script of its own. The size of what the run listed is not the reply's size."""
    replay(listing_of(n, {1, 3}))

    code, payload, text = search(cli, "질문")

    run = first_run(payload)
    assert code == 0
    assert list(run) == RUN_KEYS
    assert (run["sources_total"], run["sources_opened"]) == (n, 2)
    assert run["opened_sources"] == [{"n": 1, "url": "https://e.test/1", "title": "T1"},
                                     {"n": 3, "url": "https://e.test/3", "title": "T3"}]
    assert len(text) < 1500
    assert json.loads(Path(run["result_path"]).read_text(encoding="utf-8"))["answer"] == run["answer"]


def test_every_source_is_one_call_away_numbered_as_show_counts_them(cli, replay) -> None:
    replay(listing_of(6, {1, 3}))
    run_id = finished_run_id(cli)

    code, payload, _ = cli("result", "--run", run_id, "--sources")

    run = first_run(payload)
    assert code == 0
    assert "answer" not in run and "opened_sources" not in run
    assert [(s["n"], s["url"], s["opened"]) for s in run["sources"]] == [
        (i, f"https://e.test/{i}", i in (1, 3)) for i in range(6)]
    for s in run["sources"]:
        _, shown, _ = cli("show", "--run", run_id, "--source", str(s["n"]))
        assert shown["source"]["url"] == s["url"]
    assert cli("show", "--run", run_id, "--source", "3")[1]["content"] == "page 3"


def test_a_run_still_going_or_abandoned_shows_what_it_has_read_so_far(cli, replay, runs_dir: Path) -> None:
    """Before the result is written -- still running, or abandoned when its supervisor died --
    the sources come from the run's own copy of its transcript."""
    replay([tool("webfetch", "읽은 본문", sources=[{"id": "a", "url": "https://e.test/a", "title": "A"}]),
            {"__sleep__": 30}])
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]

    running = poll(lambda: (lambda r: r if r[0] == 0 else None)(cli("show", "--run", run_id, "--source", "0")), timeout=15)
    kill_supervisors(runs.resolve_run(runs_dir, run_id))
    assert first_run(cli("result", "--run", run_id)[1])["state"] == "abandoned"
    code, stopped, _ = cli("show", "--run", run_id, "--source", "0")

    assert running and running[1]["content"] == "읽은 본문"
    assert code == 0 and stopped["content"] == "읽은 본문"


def test_a_run_answered_from_stdout_says_it_has_no_page_text(runs_dir: Path, aside_home: Path, fake_aside: Path,
                                                             monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "no_session")
    from ultra_search import research, runs

    run = runs.create_run(runs_dir, label="t", prompt="질문")
    research.supervise(run, poll=0.05, discovery_deadline=0.5, settle=0.1)

    code, shown, _ = run_cli("show", "--run", run.run_id, "--source", "0", "--runs-dir", str(runs_dir))

    assert code == 0
    assert shown["source"]["url"] == "https://example.org/only-in-stdout"
    assert shown["content"] == "" and "stdout" in shown["note"]


def test_result_of_a_run_still_going_hands_back_the_watch(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]

    code, result, _ = cli("result", "--run", run_id)

    assert code == 0, "still going is not a failure"
    assert result["next"]["run_in_background"] is True
    assert result["next"]["command"].endswith(" --wait 570")
    assert first_run(result)["note"] == "no result yet"


# --- run ids a caller can type --------------------------------------------------------------
#
# A run id is `<yymmdd-HHMMSS>[-xxxx]-<label>`. Callers rebuilt ids from memory and got them
# wrong, and a Korean prompt's label used to keep only its ASCII -- `2022--4`, `3`, `run`.


def test_a_label_keeps_the_prompts_own_words(cli) -> None:
    """Typed on a Mac a name can arrive decomposed; it is stored composed, the way it will be
    typed back."""
    decomposed = unicodedata.normalize("NFD", "파이썬 최신 안정 버전은 무엇인가")

    _, payload, _ = search(cli, decomposed)

    run_id = first_run(payload)["run_id"]
    assert run_id.endswith("-파이썬-최신-안정-버전은")
    assert run_id == unicodedata.normalize("NFC", run_id)


def test_a_run_is_found_by_any_prefix_only_it_has(cli) -> None:
    first = finished_run_id(cli)
    _, payload, _ = search(cli, "다른 질문", extra=("--label", "other"))
    second = first_run(payload)["run_id"]
    shared = next(i for i in range(len(first)) if first[i] != second[i])

    code, collected, _ = cli("result", "--run", second[: shared + 1])
    _, shown, _ = cli("show", "--run", second[: shared + 1], "--item", "0")
    ambiguous_code, ambiguous, _ = cli("result", "--run", first[:shared])

    assert code == 0 and first_run(collected)["run_id"] == second
    assert shown["run_id"] == second
    assert ambiguous_code == 2 and ambiguous["error"] == "bad_arguments"
    assert set(ambiguous["candidates"]) == {first, second}


def test_a_whole_id_wins_over_a_longer_one_it_begins(cli) -> None:
    _, short, _ = search(cli, "질문", extra=("--label", "x"))
    run_id = first_run(short)["run_id"]
    search(cli, "질문", extra=("--label", "x-more"))

    code, collected, _ = cli("result", "--run", run_id)

    assert code == 0 and first_run(collected)["run_id"] == run_id


def test_a_korean_run_goes_from_search_through_its_watch_to_result_and_a_resume_by_prefix(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1")
    _, payload, _ = cli("search", unicodedata.normalize("NFD", "한국어 질문입니다"), "--background")
    run_id = first_run(payload)["run_id"]

    collected = subprocess.run(payload["next"]["command"], shell=True, capture_output=True, text=True, timeout=120)
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    code, resumed, _ = cli("resume", run_id[: len(run_id) - 2], "후속", "--wait", "30")

    assert run_id.endswith("-한국어-질문입니다")
    assert json.loads(collected.stdout)["runs"][0]["answer"] == "느린 답."
    assert code == 0 and first_run(resumed)["state"] == "completed"


def test_resuming_a_prefix_several_runs_share_names_them_instead(cli, fake_aside: Path) -> None:
    finished_run_id(cli)
    finished_run_id(cli)
    started = len(exec_calls(fake_aside))

    code, err, _ = cli("resume", "2", "후속")

    assert code == 2 and len(err["candidates"]) == 2
    assert len(exec_calls(fake_aside)) == started


def test_runs_in_the_default_store_are_kept_out_of_git(aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")

    code, payload, _ = run_cli("search", "질문", "--wait", "30")

    assert code == 0
    assert (Path.cwd() / ".ultra-search" / ".gitignore").read_text() == "*\n"


def test_a_store_chosen_with_runs_dir_is_left_as_it_is_even_where_the_default_would_be(
    aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")

    run_cli("search", "질문", "--wait", "30", "--runs-dir", "./.ultra-search")

    assert (Path.cwd() / ".ultra-search" / "runs").is_dir()
    assert not (Path.cwd() / ".ultra-search" / ".gitignore").exists()


def test_a_default_store_from_before_gets_its_gitignore_when_next_written(aside_home: Path, fake_aside: Path) -> None:
    """A store made by an earlier version has no .gitignore. Reading it writes nothing; the next
    write into it -- here `result` settling a run whose supervisor is gone -- adds one."""
    run_dir = Path.cwd() / ".ultra-search" / "runs" / "260901-000000-old"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"run_id": run_dir.name, "state": "running"}))

    run_cli("log")
    run_cli("result")
    run_cli("doctor")
    unread = (Path.cwd() / ".ultra-search" / ".gitignore").exists()
    meta = json.loads((run_dir / "meta.json").read_text())
    (run_dir / "meta.json").write_text(json.dumps({**meta, "supervisor_pid": dead_pid()}))
    run_cli("result")

    assert unread is False
    assert (Path.cwd() / ".ultra-search" / ".gitignore").read_text() == "*\n"


def test_a_store_that_cannot_take_a_gitignore_is_still_read(aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    _, payload, _ = run_cli("search", "질문", "--wait", "30")
    store = Path.cwd() / ".ultra-search"
    (store / ".gitignore").unlink()
    store.chmod(0o500)
    try:
        code, result, _ = run_cli("result", "--run", first_run(payload)["run_id"])
    finally:
        store.chmod(0o700)

    assert code == 0 and first_run(result)["answer"]


@pytest.mark.parametrize("healthy", [True, False])
def test_the_daemon_checked_is_the_one_aside_exec_uses(runs_dir: Path, aside_home: Path, fake_aside: Path,
                                                       ready_daemon: str, monkeypatch, healthy: bool) -> None:
    """The aside CLI talks to DAEMON_BASE_URL when it is set; checking another daemon would refuse
    work the real one can do, or pass work it cannot."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed = f"http://127.0.0.1:{sock.getsockname()[1]}"
    monkeypatch.delenv("ULTRA_SEARCH_DAEMON_URL")
    monkeypatch.setenv("DAEMON_BASE_URL", ready_daemon.rstrip("/") if healthy else closed)
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")

    code, _, _ = run_cli("search", "질문", "--wait", "30", "--runs-dir", str(runs_dir))

    assert code == (0 if healthy else 3)


def test_a_proxy_in_the_environment_does_not_stand_between_the_cli_and_its_daemon(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        proxy = f"http://127.0.0.1:{sock.getsockname()[1]}"
    for name in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.setenv(name, proxy)
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")

    code, _, _ = run_cli("search", "질문", "--wait", "30", "--runs-dir", str(runs_dir))

    assert code == 0
