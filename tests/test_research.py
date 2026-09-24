"""`search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`, end to end.

The seam is argv in, stdout and an exit code out -- exactly what a caller sees. The one
external boundary, the aside binary, is the fake in tests/fake_aside, which writes session
transcripts into a throwaway ~/.aside the way the real one does; everything between the
CLI and that boundary is the real code, including the detached supervisor.

What a run concluded is only ever read back through the commands. A test that opened a
run directory to check its answer would pass while `result` reported something else.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import ultra_search
from conftest import (
    FIXTURES,
    SCRIPTS,
    aside_session,
    answer,
    calling,
    exec_calls,
    run_cli,
    tool,
    user,
)

SESSIONS = FIXTURES / "sessions"
RECORDED_RUN = FIXTURES / "runs" / "260829-235523-subagents"


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
    """Only the event lines of a log: no response, no cursor."""
    return "\n".join(line for line in lines_of(text) if not line.startswith("# cursor="))


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


def start_isolated(base: Path, records, *, children: dict | None = None, prompt: str = "질문",
                   label: str = "run", wait: str = "60") -> tuple[Path, dict]:
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
    )
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "ultra_search.py"), "search", prompt, "--label", label,
         "--wait", wait, "--runs-dir", str(runs)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    return runs, json.loads(p.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def recorded(tmp_path_factory) -> tuple[Path, str]:
    """A run recorded on 2026-08-29: a parent that spawned three subagents, one of them kept."""
    parent = RECORDED_RUN / "session" / "messages.jsonl"
    opening = json.loads(parent.read_text(encoding="utf-8").splitlines()[0])
    prompt = opening["content"][0]["text"].split("\n\n(ultra-search:")[0]
    kid = "4kgZvArU4ipY0eIn"
    runs, payload = start_isolated(
        tmp_path_factory.mktemp("recorded"), parent,
        children={kid: RECORDED_RUN / "session" / "children" / f"{kid}.jsonl"},
        prompt=prompt, label="subagents",
    )
    return runs, first_run(payload)["run_id"]


@pytest.fixture(scope="module")
def simple_search(tmp_path_factory) -> tuple[Path, str]:
    """The recorded session of a real search: one websearch, one cited answer."""
    runs, payload = start_isolated(tmp_path_factory.mktemp("simple"), SESSIONS / "2026-08-29_SimpleSearch00001" / "messages.jsonl")
    return runs, first_run(payload)["run_id"]


@pytest.fixture(scope="module")
def eventful(tmp_path_factory) -> tuple[Path, str]:
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
    runs, payload = start_isolated(tmp_path_factory.mktemp("eventful"), records)
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
    assert [s["url"] for s in run["sources"]] == ["https://example.org/a", "https://example.org/b"]
    assert run["usage"]["total_tokens"] > 0


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

    Deliberately a slow run. Against a run that has already finished, a follower that
    returned immediately without waiting for anything would pass every assertion here -- so
    the run has to still be going when the follower starts, and the follower has to be the
    thing that waits."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "5")
    code, payload, _ = run_cli("search", "질문", "--background", "--runs-dir", str(runs_dir))

    assert code == 0
    assert first_run(payload)["state"] in ("starting", "running")
    nxt = payload["next"]
    assert set(nxt) == {"command", "bash_timeout_ms", "run_in_background"}, "one action, nothing to do afterwards"
    assert nxt["run_in_background"] is True
    assert nxt["bash_timeout_ms"] >= 600_000

    # Run it, rather than checking it contains "--follow": a command that names the wrong
    # run, or that cannot execute at all, passes every string check and still leaves the
    # caller with no way to find out the work finished.
    started = time.time()
    done = subprocess.run(shlex.split(nxt["command"]), capture_output=True, text=True, timeout=180)
    waited = time.time() - started

    assert done.returncode == 0
    assert f"run.completed {first_run(payload)['run_id']}" in done.stdout
    assert waited > 1.0, "the follower has to wait for the run, not return on a run already over"
    finished = json.loads(done.stdout.splitlines()[-1])
    assert finished["command"] == "log"
    assert first_run(finished)["state"] == "completed"
    assert finished["next"]["run_in_background"] is False
    collected = subprocess.run(finished["next"]["command"], shell=True, capture_output=True, text=True, timeout=120)
    assert collected.returncode == 0
    assert json.loads(collected.stdout.splitlines()[-1])["answer"] == "느린 답."


def test_a_search_that_outlasts_the_wait_keeps_running_and_hands_back_a_handle(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")

    code, payload, _ = search(cli, "느린 질문", wait="1")

    assert code == 0
    assert first_run(payload)["state"] in ("starting", "running")
    assert "next" in payload
    cli("stop", "--run", first_run(payload)["run_id"])


def test_the_handed_back_run_can_be_collected_once_it_finishes(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1")
    _, payload, _ = search(cli, "느린 질문", wait="0.3")
    run_id = first_run(payload)["run_id"]

    _, _, text = cli("log", "--run", run_id, "--follow", "--follow-timeout", "30")
    assert f"run.completed {run_id}" in text

    code, result, _ = cli("result", "--run", run_id)
    assert code == 0
    assert result["answer"] == "느린 답."
    assert result["sources"]


def test_a_failed_run_exits_four(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "fail")

    code, payload, _ = search(cli, "질문")
    _, result, _ = cli("result", "--run", first_run(payload)["run_id"])

    assert code == 4
    assert first_run(payload)["state"] == "failed"
    assert result["exit_code"] == 1, "aside's own exit status is kept for diagnosis"


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
    assert first_run(payload)["sources"] == []
    assert first_run(payload)["empty"] is False


def test_a_missing_aside_binary_exits_three_before_reserving_a_run(runs_dir: Path, aside_home: Path, monkeypatch) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload, _ = run_cli("search", "질문", "--wait", "5", "--runs-dir", str(runs_dir))

    assert code == 3
    assert payload["error"] == "aside_unavailable"
    assert payload["fix"]
    code, _, _ = run_cli("status", "--runs-dir", str(runs_dir))
    assert code == 2, "a registry full of runs that never started is worse than the error"


@pytest.mark.parametrize("runs_arg", [None, "relative runs"])
def test_next_commands_preserve_the_installed_path_and_run_store(
    tmp_path: Path, aside_home: Path, fake_aside: Path, monkeypatch, runs_arg
) -> None:
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


def test_a_label_names_the_run_and_cannot_escape_the_registry(cli, runs_dir: Path) -> None:
    _, named, _ = search(cli, "질문", extra=("--label", "python-version"))
    _, hostile, _ = search(cli, "질문", extra=("--label", "../../etc/passwd"))

    assert first_run(named)["run_id"].endswith("-python-version")
    run_id = first_run(hostile)["run_id"]
    assert "/" not in run_id and ".." not in run_id
    assert (runs_dir / "runs" / run_id).is_dir()
    code, status, _ = cli("status", "--run", run_id)
    assert code == 0 and first_run(status)["state"] == "completed"


def test_two_runs_of_the_same_prompt_keep_their_own_sessions(cli, monkeypatch) -> None:
    """Actually concurrent, because sequential runs cannot reproduce the bug: two searches of
    the same question are distinguishable only by the marker, and run one after the other
    even a matcher keyed on prompt text would pass."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "0.8")
    _, payload, _ = search(cli, "같은 질문", "같은 질문")
    a, b = (r["run_id"] for r in payload["runs"])

    _, status, _ = cli("status", "--group", payload["group"])
    assert len({r["session_id"] for r in status["runs"]}) == 2
    # Each run's transcript opens with its own marker and never holds the other's.
    _, _, text_a = cli("log", "--run", a, "--level", "raw")
    _, _, text_b = cli("log", "--run", b, "--level", "raw")
    assert f"ultra-search:{a}" in text_a and f"ultra-search:{b}" not in text_a
    assert f"ultra-search:{b}" in text_b and f"ultra-search:{a}" not in text_b


def test_the_transcript_outlives_asides_own_copy(cli, aside_home: Path) -> None:
    """Aside deletes CLI sessions within about a day. A run whose evidence lives only in the
    session directory has no evidence next week."""
    run_id = finished_run_id(cli)

    shutil.rmtree(aside_home / "u" / "0" / "sessions")

    _, result, _ = cli("result", "--run", run_id)
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


def test_a_watch_deadline_abandons_rather_than_reporting_completion(cli, monkeypatch) -> None:
    """`--timeout` is recorded by the process that starts the run but enforced by the
    detached supervisor, which cannot be passed an argument."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")

    code, payload, _ = search(cli, "질문", extra=("--timeout", "1"))

    assert code == 4
    assert first_run(payload)["state"] == "abandoned"
    assert first_run(payload)["daemon_run_continues"] is True


# --- children ----------------------------------------------------------------------------


def test_children_are_collected_with_their_answers(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")

    _, payload, _ = search(cli, "질문")
    run = first_run(payload)
    _, status, _ = cli("status", "--run", run["run_id"])
    _, _, logged = cli("log", "--run", run["run_id"])

    assert run["state"] == "completed"
    assert "child 1 done." in run["answer"] and "child 2 done." in run["answer"]
    kids = first_run(status)["child_ids"]
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
    _, result, _ = cli("result", "--run", run["run_id"])
    assert result["children"] == ["WvAjHmOMXm36S58Y", "jYjSOAaKKm79uXXI", "xtXKs5dqLhtZ9sCN"]


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


def test_log_prints_events_and_a_cursor_that_repeats_nothing(cli) -> None:
    run_id = finished_run_id(cli)

    _, first, text = cli("log", "--run", run_id)
    _, second, again = cli("log", "--run", run_id, "--since", str(first["cursor"]))

    assert f"# cursor={first['cursor']}" in text
    assert "prompt: 질문" in text
    assert lines_of(again) == [f"# cursor={first['cursor']}"]
    assert second["cursor"] == first["cursor"]


def test_follow_exits_on_the_terminal_line(cli) -> None:
    run_id = finished_run_id(cli)

    code, payload, text = cli("log", "--run", run_id, "--follow", "--follow-timeout", "5")

    assert code == 0
    assert f"run.completed {run_id}" in lines_of(text)
    assert payload["next"]["command"].split()[2] == "result"


def test_a_follow_that_runs_out_of_time_says_the_run_is_still_going(cli, monkeypatch) -> None:
    """Distinct from a terminal line on purpose: the caller has to be able to tell "it
    finished" from "I stopped looking", because only one of those means collect a result."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]

    _, followed, text = cli("log", "--run", run_id, "--follow", "--follow-timeout", "0.5")

    assert any(line.startswith(f"run.still-running {run_id}") for line in lines_of(text))
    assert "run.completed" not in text
    assert followed["next"]["run_in_background"] is True
    cli("stop", "--run", run_id)


def test_heartbeat_marks_a_silence_as_alive(cli, replay, aside_home: Path) -> None:
    aside_session(aside_home, "LiveChild0000001", user("자식 조사"), calling(("webfetch", {"url": "https://x.test"})))
    replay([tool("subagent", "spawned", taskId="LiveChild0000001"), {"__sleep__": 30}])
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]

    _, _, text = cli("log", "--run", run_id, "--follow", "--follow-timeout", "5", "--heartbeat", "0.5")

    beats = [line for line in lines_of(text) if line.startswith("heartbeat ")]
    assert beats
    assert "running=1 children=1" in beats[-1]
    cli("stop", "--run", run_id)


def test_an_abandoned_run_is_a_terminal_line_too(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]
    cli("stop", "--run", run_id)

    _, _, text = cli("log", "--run", run_id, "--follow", "--follow-timeout", "5")

    assert f"run.abandoned {run_id}" in lines_of(text)


def test_group_members_are_labelled_so_interleaved_lines_stay_attributable(cli) -> None:
    _, payload, _ = search(cli, "A", "B")

    _, _, text = cli("log", "--group", payload["group"])

    for run in payload["runs"]:
        assert f"[{run['run_id']}] answer: Answer" in text
        assert f"[{run['run_id']}] prompt: {'A' if run is payload['runs'][0] else 'B'}" in text


def test_a_group_follow_exits_only_when_every_member_is_terminal(cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "3")
    _, payload, _ = search(cli, "A", "B", wait="0")
    first, second = (r["run_id"] for r in payload["runs"])
    cli("stop", "--run", first)

    _, _, text = cli("log", "--group", payload["group"], "--follow", "--follow-timeout", "30")

    lines = lines_of(text)
    assert f"run.abandoned {first}" in lines
    assert f"run.completed {second}" in lines
    assert "group.finished 2 run(s)" in lines
    assert f"[{second}] answer: 느린 답." in text


def test_a_group_cursor_round_trips_per_member(cli) -> None:
    """The members' transcripts differ in length, so one member's position applied to the
    other lands mid-record and shows up as output."""
    _, payload, _ = search(cli, "A", "a much longer prompt for the second member")
    _, first, _ = cli("log", "--group", payload["group"])

    _, _, again = cli("log", "--group", payload["group"], "--since", first["cursor"])

    assert rendered(again) == ""


def test_child_activity_appears_in_the_parents_stream_and_its_cursor(cli, monkeypatch) -> None:
    """A parent investigation goes silent while its subagents work; a watcher that showed
    only the parent would make that silence look like a hang. And once a child exists, a
    single run's cursor has to carry the child's position too, or the next read replays it."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "subagent")
    run_id = finished_run_id(cli)

    _, first, text = cli("log", "--run", run_id)
    _, _, again = cli("log", "--run", run_id, "--since", str(first["cursor"]))

    assert any(line.startswith("[child ") and "answer: child 1 done." in line for line in lines_of(text))
    assert "child 1 done." not in again and "부모 답" not in again


@pytest.mark.parametrize("group", [False, True], ids=["run", "group"])
def test_a_timed_out_follow_continues_from_each_stream_and_collects_every_run(
    cli, replay, aside_home: Path, group: bool
) -> None:
    """A watch that ran out of time hands back a command that picks up where it stopped --
    in the parent and in every child, each advancing on its own -- and then hands back the
    collection of every run it was watching, including one that had already ended."""
    kids = {"first-member": "KidOfFirst000001", "second-member-with-longer-prompt": "KidOfSecond00001"}
    for prompt, kid in kids.items():
        aside_session(aside_home, kid, user(f"seen-child of {prompt}"))
    replay([
        *({**tool("subagent", "spawned", taskId=kid), "__if_prompt__": prompt} for prompt, kid in kids.items()),
        calling(text="seen-parent"),
        {"__sleep__": 10},
        answer("new-parent"),
    ])
    prompts = list(kids) if group else ["second-member-with-longer-prompt"]
    _, payload, _ = search(cli, *prompts, wait="0")
    runs = {r["run_id"]: prompt for r, prompt in zip(payload["runs"], prompts)}
    target = ["--group", payload["group"]] if group else ["--run", next(iter(runs))]
    assert poll(lambda: rendered(cli("log", *target)[2]).count("seen-child") == len(runs), timeout=15)
    if group:
        ended = next(iter(runs))
        cli("stop", "--run", ended)

    code, waiting, text = cli("log", *target, "--follow", "--follow-timeout", "0")
    for prompt, kid in kids.items():
        with (aside_home / "u" / "0" / "sessions" / f"2026-09-25_{kid}" / "messages.jsonl").open("a") as f:
            f.write(json.dumps(answer(f"new-child of {prompt}")) + "\n")
    followed = subprocess.run(waiting["next"]["command"], shell=True, capture_output=True, text=True, timeout=60)

    assert code == 0
    assert "says: seen-parent" in text
    assert "run.still-running" in text
    assert set(waiting["next"]) == {"command", "bash_timeout_ms", "run_in_background"}
    assert waiting["next"]["run_in_background"] is True
    assert followed.returncode == 0
    assert "seen-" not in rendered(followed.stdout)
    for run_id, prompt in runs.items():
        prefix = f"[{run_id}]" if group else ""
        lines = lines_of(followed.stdout)
        if group and run_id == ended:
            assert not any(line.startswith(prefix) and "new-" in line for line in lines)
            continue
        assert (f"{prefix} " if prefix else "") + "answer: new-parent" in lines
        assert f"{prefix}[child {kids[prompt]}] answer: new-child of {prompt}" in lines
    finished = json.loads(followed.stdout.splitlines()[-1])
    collected = subprocess.run(finished["next"]["command"], shell=True, capture_output=True, text=True, timeout=20)
    result = json.loads(collected.stdout)
    entries = result["runs"] if group else [result]
    assert [e["run_id"] for e in entries] == list(runs)
    states = {e["run_id"]: e["state"] for e in entries}
    assert collected.returncode == (4 if group else 0)
    for run_id in runs:
        assert states[run_id] == ("abandoned" if group and run_id == ended else "completed")


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
    assert "# cursor=" in text


def test_steps_level_is_the_view_that_was_compact_before(recorded) -> None:
    """Frozen from the previous renderer on the same transcript, with every line carrying its
    stream's prefix. The one departure kept in the golden is a subagent's finishing record,
    which used to fall through as raw JSON and now renders as text like every other known
    record. The recording's run id is the only thing that differs."""
    _, run_id = recorded
    _, _, text = log_of(recorded, "--level", "steps")

    body = "\n".join(line for line in text.splitlines() if not line.startswith("# cursor="))
    golden = (RECORDED_RUN / "steps.golden.txt").read_text(encoding="utf-8").rstrip("\n")
    assert body == golden.replace("260829-235523-subagents", run_id)


# --- what a recorded transcript turns into -----------------------------------------------


def test_a_recorded_search_is_logged_record_for_record(simple_search) -> None:
    recorded = [json.loads(line) for line in (SESSIONS / "2026-08-29_SimpleSearch00001" / "messages.jsonl").read_text().splitlines()]
    _, _, text = log_of(simple_search, "--level", "raw")

    logged = [json.loads(line) for line in lines_of(text) if not line.startswith("# cursor=")]
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

    assert "3.14.7" in result["answer"]
    assert "<citation" not in result["answer"]
    # The recorded run cited source aQzmmOfnlbkdc2ZD_mUd1, which is http://python.org/. The
    # resolved URL and not just the label is the point: a lookup that finds nothing also
    # strips the tag, and would pass a laxer assertion.
    assert "Python.org의 최신 안정 버전 (http://python.org/)" in result["answer"]


def test_sources_distinguish_seen_from_actually_read(simple_search) -> None:
    """This run only ran websearch -- it listed results and never opened one."""
    runs, run_id = simple_search
    _, result, _ = run_cli("result", "--run", run_id, "--runs-dir", str(runs))

    assert result["sources"]
    assert all(s["url"] for s in result["sources"])
    assert all(s["opened"] is False for s in result["sources"])


def test_usage_totals_across_every_assistant_turn(simple_search) -> None:
    runs, run_id = simple_search
    _, result, _ = run_cli("result", "--run", run_id, "--runs-dir", str(runs))

    assert result["usage"]["total_tokens"] == 10813 + 18580
    assert result["usage"]["cost"] > 0


def test_a_fetched_page_counts_as_opened(cli, replay) -> None:
    src = {"id": "p1", "url": "https://docs.claude.com/agent-teams", "title": "Agent teams"}
    replay([calling(("webfetch", {"url": src["url"]})), tool("webfetch", "page text", sources=[src]), answer("정리")])

    _, payload, _ = search(cli, "질문")

    assert [(s["url"], s["opened"]) for s in first_run(payload)["sources"]] == [(src["url"], True)]


def test_a_citation_to_an_unknown_source_keeps_its_label(cli, replay) -> None:
    replay([answer('See <citation refs="nosuchref">the release notes</citation> for detail.')])

    _, payload, _ = search(cli, "질문")

    assert first_run(payload)["answer"] == "See the release notes for detail."


def test_an_unfamiliar_record_or_block_is_kept_and_a_torn_line_is_left_alone(cli, replay) -> None:
    """The transcript is another product's private surface. An unknown role survives as raw,
    an unknown block does not lose the text beside it, and a line still being written is
    not a record yet."""
    replay(SESSIONS / "2026-08-29_UnknownShape0001" / "messages.jsonl")

    _, payload, _ = search(cli, "질문")
    _, _, text = cli("log", "--run", first_run(payload)["run_id"], "--level", "steps")

    assert first_run(payload)["answer"] == "끝."
    assert len([line for line in text.splitlines() if line.startswith("raw[")]) == 1
    assert "[1 unrecognised block(s)]" in text
    assert "잘린 줄" not in text


# --- resume ------------------------------------------------------------------------------


def test_resume_continues_a_finished_run_in_its_own_session(cli, fake_aside: Path) -> None:
    run_id = finished_run_id(cli)
    _, first, _ = cli("status", "--run", run_id)

    code, payload, _ = cli("resume", run_id, "후속 질문", "--wait", "30")

    run = first_run(payload)
    assert code == 0
    assert run["resumed_from"] == run_id
    assert run["state"] == "completed"
    assert run["session_id"] == first_run(first)["session_id"]
    assert run["answer"] == "이어서 답합니다."
    argv = exec_calls(fake_aside)[-1]
    assert argv[argv.index("--session") + 1] == first_run(first)["session_id"]


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

    assert first_run(payload)["sources"] == [], "the earlier turn's sources belong to the earlier run"
    assert first_run(payload)["usage"]["total_tokens"] < first_run(first)["usage"]["total_tokens"]


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
    cli("stop", "--run", run_id)


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

    _, waiting, text = cli("log", "--run", run_id)
    _, finished, followed = cli("log", "--run", run_id, "--since", str(waiting["cursor"]),
                                "--follow", "--follow-timeout", "60")
    _, _, repeated = cli("log", "--run", run_id, "--since", str(finished["cursor"]))
    _, _, from_start = cli("log", "--run", run_id)

    assert rendered(text) == ""
    assert "old-" not in rendered(followed)
    for expected in ("prompt: new-prompt", "new-answer", "new-child"):
        assert expected in rendered(followed)
    assert rendered(repeated) == ""
    assert "prompt: new-prompt" in rendered(from_start) and "old-" not in rendered(from_start)


def test_a_session_this_tool_never_created_can_be_resumed(cli, aside_home: Path, fake_aside: Path) -> None:
    """The capability this is for: a conversation started in the Aside app, or by a bare
    `aside exec`, is picked up here and continued. Aside keeps no database row for most
    such sessions, and the transcript alone has to be enough."""
    assert not (aside_home / "u" / "0" / "state.db").exists()

    code, payload, _ = cli("resume", "SimpleSearch00001", "그래서 결론은?", "--wait", "30")

    run = first_run(payload)
    assert code == 0
    assert run["resumed_from"] == "SimpleSearch00001"
    assert run["state"] == "completed"
    assert run["answer"] == "이어서 답합니다."
    argv = exec_calls(fake_aside)[-1]
    assert argv[argv.index("--session") + 1] == "SimpleSearch00001"


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


# --- status ------------------------------------------------------------------------------


def test_status_reports_activity_rather_than_guessing_at_health(cli) -> None:
    run_id = finished_run_id(cli)

    code, status, _ = cli("status", "--run", run_id)

    run = first_run(status)
    assert code == 0
    assert run["state"] == "completed"
    assert run["last_activity_at"] > 0
    assert 0 <= run["idle_seconds"] < 60
    assert run["possibly_stalled"] is False


def test_database_details_are_reported_when_they_exist(cli, aside_home: Path) -> None:
    run_id = finished_run_id(cli)
    _, status, _ = cli("status", "--run", run_id)
    make_state_db(aside_home, (first_run(status)["session_id"], "idle", '{"kind":"approval"}'))

    _, status, _ = cli("status", "--run", run_id)

    assert first_run(status)["suspension"] == {"kind": "approval"}


def test_a_quiet_run_is_flagged_but_left_alone_until_a_child_writes(cli, replay, aside_home: Path) -> None:
    """Silence is labelled, never acted on: a slow run and a stuck one look identical from
    here. And a parent goes quiet for minutes while its subagents work, so a child's writes
    count as the run's activity -- the parent's own files stay old throughout."""
    child = aside_session(aside_home, "BusyChild0000001", user("자식"), calling(("webfetch", {"url": "https://x.test"})))
    replay([tool("subagent", "spawned", taskId="BusyChild0000001"), {"__sleep__": 40}])
    _, payload, _ = search(cli, "질문", wait="0")
    run_id = first_run(payload)["run_id"]

    quiet = poll(lambda: (lambda s: s if first_run(s)["possibly_stalled"] else None)(
        cli("status", "--run", run_id, "--stall-after", "3")[1]), timeout=20)
    assert quiet, "nothing has written for longer than --stall-after"
    with (child / "messages.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(tool("webfetch", "새 결과")) + "\n")
    busy = poll(lambda: (lambda s: s if not first_run(s)["possibly_stalled"] else None)(
        cli("status", "--run", run_id, "--stall-after", "3")[1]), timeout=8)

    assert first_run(quiet)["possibly_stalled"] is True
    assert first_run(quiet)["state"] == "running", "flagged only: nothing is stopped"
    assert "Nothing was stopped" in first_run(quiet)["note"]
    assert busy, "a child's write has to count as the run's activity"
    assert first_run(busy)["children"] == 1
    assert first_run(busy)["idle_seconds"] < 3
    cli("stop", "--run", run_id)


def test_runs_are_found_by_id_by_group_and_by_default_the_latest(cli) -> None:
    _, single, _ = search(cli, "하나")
    _, group, _ = search(cli, "A", "B")

    _, by_id, _ = cli("status", "--run", first_run(single)["run_id"])
    _, by_group, _ = cli("status", "--group", group["group"])
    _, latest, _ = cli("status")

    assert [r["run_id"] for r in by_id["runs"]] == [first_run(single)["run_id"]]
    assert {r["run_id"] for r in by_group["runs"]} == {r["run_id"] for r in group["runs"]}
    assert all(r["group"] == group["group"] for r in by_group["runs"])
    assert {r["run_id"] for r in latest["runs"]} == {r["run_id"] for r in group["runs"]}


def test_a_run_that_does_not_exist_is_refused_not_guessed(cli) -> None:
    code, err, _ = cli("status")
    assert code == 2 and err["error"] == "bad_arguments"

    finished_run_id(cli)
    code, err, _ = cli("status", "--run", "260101-000000-nope")
    assert code == 2
    assert err["recent_runs"]


# --- result and show ---------------------------------------------------------------------


@pytest.mark.parametrize("state", ["failed", "abandoned", "completed_with_orphans"])
def test_terminal_log_and_result_preserve_failure_and_incompleteness(cli, monkeypatch, state) -> None:
    scenario = {"failed": "fail", "abandoned": "slow", "completed_with_orphans": "orphan"}[state]
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", scenario)
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "60")
    _, payload, _ = search(cli, "A", "B", wait="0" if state == "abandoned" else "30")
    if state == "abandoned":
        cli("stop", "--group", payload["group"])

    code, logged, text = cli("log", "--group", payload["group"], "--follow")

    assert code == 0
    assert "group.completed" not in text
    assert {r["state"] for r in logged["runs"]} == {state}
    assert logged["next"]["run_in_background"] is False
    collected = subprocess.run(logged["next"]["command"], shell=True, capture_output=True, text=True, timeout=10)
    result = json.loads(collected.stdout)
    assert collected.returncode == (0 if state == "completed_with_orphans" else 4)
    for entry in [*logged["runs"], *result["runs"]]:
        assert entry["state"] == state
        if state == "completed_with_orphans":
            assert entry["orphan_children"]
            assert "snapshot" in entry["note"] and "not" in entry["note"]
        elif state == "abandoned":
            assert entry["daemon_run_continues"] is True
            assert "credits" in entry["note"]


def test_sources_only_omits_the_answer(cli) -> None:
    run_id = finished_run_id(cli)

    _, result, _ = cli("result", "--run", run_id, "--sources-only")

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


# --- stop --------------------------------------------------------------------------------


def test_stop_says_plainly_that_the_run_itself_continues(cli, monkeypatch) -> None:
    """`stop` detaches the watcher. It cannot cancel the daemon-side run -- killing the CLI
    was measured leaving the run going and still spending credits."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "10")
    _, payload, _ = search(cli, "질문", wait="0.3")
    run_id = first_run(payload)["run_id"]

    code, stopped, _ = cli("stop", "--run", run_id)

    assert code == 0
    assert stopped["stopped_watching"] == [run_id]
    assert stopped["daemon_run_continues"] is True
    assert "aside" in stopped["note"].lower()
    for command in ("status", "log", "result"):
        _, payload, _ = cli(command, "--run", run_id)
        entry = payload["runs"][0] if command != "result" else payload
        assert entry["state"] == "abandoned"
        assert entry["daemon_run_continues"] is True
        assert "credits" in entry["note"]


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


@pytest.mark.parametrize("command", ["status", "log", "result", "show", "stop"])
def test_a_run_id_that_names_a_path_outside_the_registry_is_refused(cli, tmp_path: Path, command: str) -> None:
    """A run id reaches the filesystem as a directory name. One that walks out of the
    registry must not be read, let alone written to by `stop`."""
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
    _, result, _ = cli("result", "--run", run["run_id"])
    assert result["children"] == []
