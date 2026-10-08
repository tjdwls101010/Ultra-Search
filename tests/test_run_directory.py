"""The run directory: what a run leaves on disk, and the files three processes share.

This is the one test file that reaches below the CLI, and only for properties where the
persisted bytes are themselves the contract and no command can observe them
deterministically: the supervisor's end states under timings a caller cannot choose (the
settle window, the discovery deadline), meta.json under concurrent writers, run ids
reserved in the same second, and the append-only copy of a transcript whose source
shrinks, vanishes or is still being written.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from ultra_search import research, runs
from conftest import SCRIPTS, aside_session, answer, calling, subagent_turn, tool, turn, user

SESSIONS = Path(__file__).parent / "fixtures" / "sessions"


def start(runs_dir: Path, prompt: str = "질문") -> runs.Run:
    """A run reserved the way `search` reserves one, before its supervisor starts."""
    return runs.create_run(runs_dir, label="t", prompt=prompt)


def supervise(run: runs.Run, **kw) -> dict:
    kw.setdefault("poll", 0.05)
    kw.setdefault("discovery_deadline", 5.0)
    kw.setdefault("settle", 0.5)
    return research.supervise(run, **kw)


def result_of(run: runs.Run) -> dict:
    return json.loads((run.path / "result.json").read_text(encoding="utf-8"))


# --- the supervisor's end states ---------------------------------------------------------


def test_a_run_whose_session_is_never_found_still_produces_an_answer(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """The session store is an unofficial surface. When correlation fails the run still
    finished and its stdout still holds the answer, so it is reported as unstructured
    rather than as a failure -- and not as a structured answer either."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "no_session")
    run = start(runs_dir)

    meta = supervise(run, discovery_deadline=0.5, settle=0.1)

    assert meta["state"] == "completed_unstructured"
    result = result_of(run)
    assert result["answer"] == "The answer, visible only in stdout."
    assert [s["url"] for s in result["sources"]] == ["https://example.org/only-in-stdout"]
    assert "stdout only" in result["note"]


RECORDED_STDOUT = Path(__file__).parent / "fixtures" / "runs" / "261002-lifecycle-subagent" / "stdout.log"


def test_without_a_session_the_answer_is_the_whole_final_message_from_stdout(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Recorded from the real binary: tool calls in colour, their output dimmed, and the
    final message after the last dimmed block. Without its line the answer is whatever came
    after the last blank line -- here the tail of a subagent's report -- with colour codes."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "no_session")
    monkeypatch.setenv("FAKE_ASIDE_STDOUT", str(RECORDED_STDOUT))
    run = start(runs_dir)

    supervise(run, discovery_deadline=0.5, settle=0.1)

    result = result_of(run)
    assert result["answer"] == ("The latest stable Python 3 release is **Python 3.14.8**, according to "
                                "[python.org](https://www.python.org/downloads/).")
    assert "https://www.python.org/downloads/" in [s["url"] for s in result["sources"]]
    assert not any("\x1b" in s["url"] for s in result["sources"])


def test_a_final_message_with_paragraphs_is_not_cut_at_its_last_blank_line(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch, tmp_path: Path
) -> None:
    """A real run's report -- headings, a table, a list of what it could not confirm -- came
    back as its last paragraph alone, 386 of 10,080 characters."""
    final = "## 결론\n\n첫 문단.\n\n| 날짜 | 출처 |\n|---|---|\n| 9/7 | https://e.test/a |\n\n### 확인하지 못한 항목\n\n- 하나"
    stdout = tmp_path / "stdout.log"
    stdout.write_text(
        "조사하겠습니다.\x1b[0m\n\n\x1b[32mwebfetch\x1b[0m(url: \x1b[32m'https://e.test/a'\x1b[39m)\n\n"
        "\x1b[2m > page text\n\nwith a blank line\x1b[0m\n" + final + "\x1b[0m\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "no_session")
    monkeypatch.setenv("FAKE_ASIDE_STDOUT", str(stdout))
    run = start(runs_dir)

    supervise(run, discovery_deadline=0.5, settle=0.1)

    assert result_of(run)["answer"] == final


def test_a_child_still_running_at_parent_exit_is_named_not_hidden(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "orphan")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "30")
    run = start(runs_dir)

    meta = supervise(run, settle=0.4)

    assert meta["state"] == "completed_with_orphans"
    assert len(meta["orphan_children"]) == 1
    assert result_of(run)["orphan_children"] == meta["orphan_children"]
    assert meta["orphan_children"][0] in result_of(run)["children"]


def test_a_child_that_finishes_inside_the_settle_window_is_a_clean_completion(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "orphan")
    monkeypatch.setenv("FAKE_ASIDE_ORPHAN_DELAY", "0.3")
    run = start(runs_dir)

    meta = supervise(run, settle=4.0)

    assert meta["state"] == "completed"
    assert not meta.get("orphan_children")
    assert "child 2 finished late." in result_of(run)["answer"]


def test_a_child_is_finished_only_when_its_last_turn_stopped(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """Mid-tool means still working, and a user turn after a finished answer means a new turn
    has begun -- looking only at the last assistant message would stop copying that child
    mid-investigation. A child that stopped with nothing to say is finished, not orphaned."""
    aside_session(aside_home, "MidToolChild0001", user("a"), calling(("webfetch", {"url": "https://x.test"})))
    aside_session(aside_home, "NewTurnChild0001", user("b"), answer("done"), user("추가 조사해"))
    aside_session(aside_home, "QuietChild000001", user("c"), {"role": "assistant", "content": [], "stopReason": "stop"})
    replay([tool("subagent", "spawned", taskId=sid) for sid in ("MidToolChild0001", "NewTurnChild0001", "QuietChild000001")]
           + [answer("부모 답")])
    run = start(runs_dir)

    meta = supervise(run, settle=0.3)

    assert meta["state"] == "completed_with_orphans"
    assert meta["orphan_children"] == ["MidToolChild0001", "NewTurnChild0001"]


@pytest.mark.parametrize("between", [[], [{"role": "system-message", "content": "Relevant skill docs are available."}]],
                         ids=["adjacent", "system-message-between"])
def test_a_child_that_reported_mid_turn_is_still_running(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay, between: list
) -> None:
    """Recorded from a real child: it messages its parent and stops with `stop` well before
    its turn's `final-started` and final answer. Its turn is only over at `finished` -- read
    from the prompt it got in this run, which is where its transcript is cut, and real turns
    can carry a system message between `started` and that prompt."""
    now = int(time.time() * 1000) + 60_000
    aside_session(aside_home, "ReportingChild01",
                  {**turn("started"), "timestamp": now}, *between, {**user("조사해"), "timestamp": now},
                  {**calling(("webfetch", {"url": "https://x.test"})), "timestamp": now},
                  {**tool("webfetch", "page"), "timestamp": now}, {**answer("중간 보고"), "timestamp": now})
    replay([tool("subagent", "spawned", taskId="ReportingChild01"), answer("부모 답")])
    run = start(runs_dir)

    meta = supervise(run, settle=0.3)

    assert meta["state"] == "completed_with_orphans"
    assert meta["orphan_children"] == ["ReportingChild01"]


def test_the_parents_turn_is_waited_for_until_it_has_finished(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """The process can exit before the daemon's last writes land. A message that stopped
    earlier in the turn is not its end; `finished` is."""
    replay([turn("started"), user("recorded prompt"), calling(("webfetch", {"url": "https://x.test"})),
            tool("webfetch", "page"), answer("중간 보고"), {"__after_exit__": 1.0},
            turn("final-started"), answer("최종 답"), turn("finished")])
    run = start(runs_dir)

    meta = supervise(run, settle=5.0)

    assert meta["state"] == "completed"
    assert result_of(run)["answer"] == "최종 답"


# --- when a turn is over ------------------------------------------------------------------


def test_a_turn_is_over_when_it_finishes_not_when_its_process_exits(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """`aside exec` was seen exiting 0 while both subagents were still working; their results, the final answer and `finished` came after. Taking the exit for the end reported an empty answer with two orphans."""
    replay(subagent_turn(gap=1.5))
    run = start(runs_dir)

    meta = supervise(run, settle=0.5)

    assert meta["state"] == "completed"
    assert meta["orphan_children"] == []
    assert result_of(run)["answer"].startswith("최종 답")
    assert "child 2 found it" in result_of(run)["answer"]


ERROR_STOP = {"role": "assistant", "content": [{"type": "text", "text": "도구 오류로 중단합니다"}], "stopReason": "error",
              "timestamp": 2}


@pytest.mark.parametrize("last,state", [(answer("최종 답"), "completed"), (ERROR_STOP, "failed")], ids=["answer", "error"])
def test_a_finished_turn_whose_process_lingers_is_judged_by_the_turn(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay, last: dict, state: str
) -> None:
    """The turn is over at `finished` even while the process is still up. The supervisor ends the process after the settle window, and the code that ending produces says nothing about the turn: its last message does."""
    replay([calling(("webfetch", {"url": "https://x.test"})), tool("webfetch", "page"), turn("final-started"), last,
            turn("finished"), {"__sleep__": 30}])
    run = start(runs_dir)
    began = time.time()

    meta = supervise(run, settle=0.5)

    assert time.time() - began < 15, "a turn that finished is not waited on for its process"
    assert meta["state"] == state
    assert meta["terminated_by_supervisor"] is True
    assert result_of(run)["exit_code"] is None


def test_a_turn_that_finished_and_then_exited_non_zero_failed(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "fail")
    run = start(runs_dir)

    meta = supervise(run, settle=0.5)

    assert meta["state"] == "failed"
    assert meta["exit_code"] == 1


def test_an_error_that_ends_a_turn_after_its_process_exited_0_is_a_failure(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """The process can exit 0 before the turn's last message, and that message can be an error."""
    replay([calling(("webfetch", {"url": "https://x.test"})), tool("webfetch", "page"), {"__after_exit__": 1.0},
            turn("final-started"), ERROR_STOP, turn("finished")])
    run = start(runs_dir)

    meta = supervise(run, settle=0.5)

    assert meta["state"] == "failed"
    assert meta["exit_code"] == 0


def test_a_session_that_appears_after_the_process_exits_is_read_not_replaced_by_stdout(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Exiting 0 before the session is on disk is not a reason to settle for stdout while the discovery deadline still runs: the transcript, once it lands, is the better record."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "late_session")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "1.5")
    run = start(runs_dir)

    meta = supervise(run, settle=0.5, discovery_deadline=5.0)

    assert meta["state"] == "completed"
    assert result_of(run)["answer"] == "Answer Example A (https://example.org/a)"
    assert "note" not in result_of(run)


@pytest.mark.parametrize("process", ["alive", "exited"])
def test_a_turn_quiet_past_the_idle_limit_is_abandoned_with_what_it_had(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch, replay, process: str
) -> None:
    """Without the process exit as an ending, silence needs a bound -- whether the process is still up or exited 0 mid-turn. What the turn gathered by then is kept, and the state says watching stopped, not the work."""
    if process == "alive":
        monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
        monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    else:
        replay([calling(("webfetch", {"url": "https://x.test"})),
                tool("webfetch", "page", sources=[{"id": "w1", "url": "https://x.test/"}])])
    run = start(runs_dir)

    meta = supervise(run, idle_limit=1.0, settle=0.3)

    assert meta["state"] == "abandoned"
    assert meta["reason"] == "the turn went quiet before it finished"
    assert meta["daemon_run_continues"] is True
    result = result_of(run)
    assert result["state"] == "abandoned"
    assert result["answer"] == ""
    if process == "exited":
        assert [s["url"] for s in result["sources"]] == ["https://x.test/"]


def test_an_earlier_turns_child_still_writing_does_not_keep_this_turn_alive(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """A resumed session's earlier children can go on writing; that says nothing about whether this turn is alive."""
    aside_session(aside_home, "ParentOfBusyKid1", user("old-prompt"), tool("subagent", "spawned", taskId="BusyEarlierKid01"),
                  answer("partial"))
    kid = aside_session(aside_home, "BusyEarlierKid01", user("task"), calling(("webfetch", {"url": "https://x.test"})))
    replay([calling(("webfetch", {"url": "https://y.test"}))])
    run = start(runs_dir, "후속")
    run.update_meta(resume_session_id="ParentOfBusyKid1")
    done = threading.Event()

    def keep_writing() -> None:
        until = time.time() + 8
        while not done.wait(0.2) and time.time() < until:
            with (kid / "messages.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(tool("webfetch", "more")) + "\n")

    writer = threading.Thread(target=keep_writing)
    writer.start()
    began = time.time()
    try:
        meta = supervise(run, idle_limit=1.0, settle=0.3)
    finally:
        done.set()
        writer.join()

    assert meta["state"] == "abandoned"
    assert time.time() - began < 6


def test_a_turn_ends_at_its_own_finished_record(runs_dir: Path, aside_home: Path, fake_aside: Path, replay) -> None:
    """A session continued after this run appends the next turn to the same transcript. This run's answer is still the one its own turn gave."""
    replay([calling(("webfetch", {"url": "https://x.test"})), tool("webfetch", "page"), turn("final-started"),
            answer("내 턴의 답"), turn("finished"), turn("started"), user("다음 질문"), turn("final-started"),
            answer("다음 턴의 답"), turn("finished")])
    run = start(runs_dir)

    meta = supervise(run, settle=0.3)

    assert meta["state"] == "completed"
    assert result_of(run)["answer"] == "내 턴의 답"


def test_the_watch_deadline_recorded_by_the_cli_is_what_abandons_the_run(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """`--timeout` is recorded by the process that starts the run but enforced by the detached
    supervisor, which cannot be passed an argument -- meta.json is the only link. The reason
    it records is what tells a later reader this was a deadline and not a `stop`."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "slow")
    monkeypatch.setenv("FAKE_ASIDE_DELAY", "20")
    run = start(runs_dir)
    run.update_meta(watch_timeout=0.6)

    meta = supervise(run, settle=0.2)

    assert meta["state"] == "abandoned"
    assert meta["reason"] == "watch timeout"
    assert meta["daemon_run_continues"] is True


# --- meta.json ---------------------------------------------------------------------------


def test_metadata_round_trips_and_updates_merge(runs_dir: Path) -> None:
    run = runs.create_run(runs_dir, label="x")
    run.write_meta({"state": "running", "marker": "us-abc", "prompt": "질문"})

    written = run.update_meta(state="completed", answer_count=3)

    assert written == {"state": "completed", "marker": "us-abc", "prompt": "질문", "answer_count": 3}
    assert runs.load_meta(run.path) == written


def test_a_meta_write_is_all_or_nothing(runs_dir: Path) -> None:
    """`status` may read meta.json at any moment. A value that cannot be serialised fails
    before the file is touched, so a reader sees the old file or the new one."""
    run = runs.create_run(runs_dir, label="x")
    run.write_meta({"state": "running"})
    before = run.meta_path.read_bytes()

    with pytest.raises(TypeError):
        run.write_meta({"state": "done", "bad": {1, 2}})

    assert run.meta_path.read_bytes() == before
    assert [p.name for p in run.path.iterdir() if p.name.endswith(".tmp")] == []


def test_concurrent_meta_updates_do_not_lose_each_others_keys(runs_dir: Path) -> None:
    """meta.json is written by the starting CLI, the detached supervisor and `stop`, each
    doing read-modify-write. Without serialisation the loser's keys vanish."""
    run = runs.create_run(runs_dir, label="race")
    keys = [f"k{i}" for i in range(24)]

    threads = [threading.Thread(target=run.update_meta, kwargs={k: k}) for k in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert [k for k in keys if k not in run.meta()] == []


def test_updates_from_many_processes_all_survive(runs_dir: Path) -> None:
    """Processes, not threads: the lock is a file, and a threads-only test would pass on an
    in-process lock that does nothing across the process boundary this actually has."""
    run = runs.create_run(runs_dir, label="procs")
    script = textwrap.dedent(
        f"""
        import sys
        from ultra_search import runs
        run = runs.Run(run_id={run.run_id!r}, path=__import__("pathlib").Path({str(run.path)!r}))
        run.update_meta(**{{sys.argv[1]: sys.argv[1]}})
        """
    )
    # Run from the scripts directory, which is how the package is found: nothing edits sys.path.
    procs = [subprocess.Popen([sys.executable, "-c", script, f"key{i}"], cwd=SCRIPTS) for i in range(8)]
    for p in procs:
        assert p.wait(timeout=60) == 0

    assert [f"key{i}" for i in range(8) if f"key{i}" not in run.meta()] == []


def test_runs_reserved_in_the_same_second_get_different_ids(runs_dir: Path) -> None:
    """A group starts every member at once. Reserving the directory with O_EXCL is what makes
    the loser pick a new id instead of writing its metadata over the winner's."""
    got: list[runs.Run] = []
    threads = [threading.Thread(target=lambda: got.append(runs.create_run(runs_dir, label="same"))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len({r.run_id for r in got}) == 8
    assert all(r.meta()["run_id"] == r.run_id for r in got)


# --- the copy of a transcript ------------------------------------------------------------


@pytest.fixture
def source(aside_home: Path) -> Path:
    return aside_home / "u" / "0" / "sessions" / "2026-08-29_SimpleSearch00001" / "messages.jsonl"


def test_a_copy_takes_only_whole_lines_and_picks_up_a_line_once_it_is_complete(tmp_path: Path) -> None:
    """A line still being written is not yet a record; consuming it would store a fragment
    that can never be completed."""
    src, dst = tmp_path / "src.jsonl", tmp_path / "dst.jsonl"
    whole = json.dumps(user("q")) + "\n"
    src.write_text(whole + '{"role":"assistant","content":[{"type":"text","text":"잘린')

    first = runs.copy_new_lines(src, dst, since=0)
    with src.open("a") as f:
        f.write(' 줄"}],"stopReason":"stop"}\n')
    second = runs.copy_new_lines(src, dst, since=first)

    assert first == len(whole.encode())
    assert dst.read_bytes() == src.read_bytes()
    assert second == src.stat().st_size


def test_a_copy_resumes_from_its_cursor_without_duplicating(source: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy.jsonl"

    first = runs.copy_new_lines(source, dst, since=0)
    second = runs.copy_new_lines(source, dst, since=first)

    assert second == first
    assert dst.read_bytes() == source.read_bytes()


def test_a_shrinking_or_vanishing_source_never_shortens_the_copy(source: Path, tmp_path: Path) -> None:
    """Aside cleans up sessions on its own schedule. The copy is then the only remaining
    record, so it is append-only, always."""
    dst = tmp_path / "copy.jsonl"
    cursor = runs.copy_new_lines(source, dst, since=0)
    kept = dst.read_bytes()

    source.write_text(json.dumps(user("짧아짐")) + "\n")
    assert runs.copy_new_lines(source, dst, since=cursor) == cursor
    source.unlink()
    assert runs.copy_new_lines(source, dst, since=cursor) == cursor

    assert dst.read_bytes() == kept


def test_a_lost_copy_is_rebuilt_rather_than_resumed_past(source: Path, tmp_path: Path) -> None:
    """The cursor describes the destination, not the source. Continuing from the old cursor
    onto an emptied copy would silently lose everything before it."""
    dst = tmp_path / "copy.jsonl"
    cursor = runs.copy_new_lines(source, dst, since=0)
    original = dst.read_bytes()

    dst.write_bytes(b"")

    assert runs.copy_new_lines(source, dst, since=cursor) == cursor
    assert dst.read_bytes() == original


def test_a_source_recreated_shorter_is_read_from_the_start_into_a_new_copy(source: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy.jsonl"
    cursor = runs.copy_new_lines(source, dst, since=0)

    dst.unlink()
    source.write_text(json.dumps(user("새 세션"), ensure_ascii=False) + "\n")
    runs.copy_new_lines(source, dst, since=cursor)

    assert "새 세션" in dst.read_text(encoding="utf-8")


def test_a_copy_that_got_ahead_of_the_cursor_is_not_duplicated(source: Path, tmp_path: Path) -> None:
    """The supervisor appends and then records the new cursor as a separate step. Dying
    between the two leaves the destination ahead of what meta remembers -- and re-copying
    from the remembered position would count records twice in usage, sources and children."""
    dst = tmp_path / "copy.jsonl"
    full = runs.copy_new_lines(source, dst, since=0)
    complete = dst.read_bytes()

    after = runs.copy_new_lines(source, dst, since=full // 2)

    assert dst.read_bytes() == complete
    assert after == full


def test_stop_never_overwrites_a_run_that_finished_while_it_waited(runs_dir: Path) -> None:
    """`stop` asks the supervisor to let go and waits for it. A run that completes in that
    window has a result; recording it as abandoned would hide that result behind a state
    that says the work was cut off."""
    from conftest import run_cli

    run = runs.create_run(runs_dir, label="race")
    run.update_meta(state="running")

    def supervisor_finishes_first() -> None:
        while not run.meta().get("stop_requested"):
            pass
        run.update_meta(state="completed", finished_at=1.0)

    t = threading.Thread(target=supervisor_finishes_first)
    t.start()
    code, payload, _ = run_cli("stop", "--run", run.run_id, "--runs-dir", str(runs_dir))
    t.join()

    assert code == 0
    assert run.meta()["state"] == "completed"
    assert payload["stopped_watching"] == []


@pytest.mark.parametrize("ending", ["stopped_empty", "cut_off_mid_tool"])
def test_only_a_finished_turn_supplies_the_answer(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay, ending: str
) -> None:
    """Text in a turn that stopped to call a tool is the worker narrating what it is about to
    do. Reporting it as the answer turns "let me check" into a finding. A turn cut off mid-tool never finishes, so it ends at the idle limit, abandoned."""
    records = [calling(("webfetch", {"url": "https://x.test"}), text="잠시 확인하겠습니다"), tool("webfetch", "page")]
    if ending == "stopped_empty":
        records.append({"role": "assistant", "content": [], "stopReason": "stop"})
    replay(records)
    run = start(runs_dir)

    meta = supervise(run, settle=0.3, idle_limit=1.0)

    assert result_of(run)["answer"] == ""
    assert meta["state"] == ("completed" if ending == "stopped_empty" else "abandoned")


def resumed(runs_dir: Path, aside_home: Path) -> runs.Run:
    """A run continuing the recorded search session, whose last turn already has an answer."""
    run = start(runs_dir, "후속 질문")
    run.update_meta(resume_session_id="SimpleSearch00001", resumed_from="SimpleSearch00001")
    return run


def test_a_turn_that_has_not_appeared_yet_is_waited_for_not_replaced_by_the_last_one(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    """Until this run's prompt appears, everything in a resumed transcript belongs to earlier
    turns -- including an answer. The process can exit before the turn lands."""
    monkeypatch.setenv("FAKE_ASIDE_RESUME_LATE", "1")
    monkeypatch.setenv("FAKE_ASIDE_RESUME_DELAY", "1.0")
    run = resumed(runs_dir, aside_home)

    meta = supervise(run, settle=4.0)

    assert meta["state"] == "completed"
    assert result_of(run)["answer"] == "이어서 답합니다."


def test_a_turn_that_never_appears_is_not_reported_from_the_turn_before(
    runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_ASIDE_RESUME_LATE", "1")
    monkeypatch.setenv("FAKE_ASIDE_RESUME_DELAY", "30")
    run = resumed(runs_dir, aside_home)

    meta = supervise(run, settle=0.3)

    result = result_of(run)
    assert "3.14.7" not in result["answer"], "the previous turn's answer is not this run's"
    assert result["sources"] == [] or all("python.org" not in s["url"] for s in result["sources"])
    assert meta["state"] == "completed_unstructured"
    assert result["answer"] == "이어서 답합니다.", "stdout is the only record of this turn"
    assert "never appeared" in result["note"]


def test_a_reused_childs_earlier_answer_is_not_its_answer_now(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """A child given a second task keeps its transcript. Until the new task finishes, the
    answer in it is to the old one."""
    aside_session(aside_home, "ReusedChild00001", user("이전 과제"), answer("이전 답"),
                  user("추가 조사"), calling(("webfetch", {"url": "https://x.test"})))
    replay([tool("subagent", "spawned", taskId="ReusedChild00001"), answer("부모 답")])
    run = start(runs_dir)

    meta = supervise(run, settle=0.3)

    assert meta["orphan_children"] == ["ReusedChild00001"]
    assert "이전 답" not in result_of(run)["answer"]



def test_resuming_to_collect_an_earlier_childs_late_result_counts_it(
    runs_dir: Path, aside_home: Path, fake_aside: Path, replay
) -> None:
    """An earlier run ended with a child still working. Resuming to wait for it collects its
    result: the child finished, and what it found is this run's answer."""
    aside_session(aside_home, "ParentWithKid001", user("old-prompt"),
                  tool("subagent", "spawned", taskId="LateKid000000001"), answer("partial"))
    aside_session(aside_home, "LateKid000000001", {**user("task"), "timestamp": 1_000},
                  {**tool("webfetch", "page", sources=[{"id": "l1", "url": "https://late.test/"}]), "timestamp": 2_000},
                  {**answer("late child answer"), "timestamp": 3_000})
    replay([tool("subagent_wait", "done", results=[{"taskId": "LateKid000000001"}]), answer("collected")])
    run = start(runs_dir, "wait for it")
    run.update_meta(resume_session_id="ParentWithKid001")

    meta = supervise(run, settle=0.3)

    assert meta["state"] == "completed"
    assert "late child answer" in result_of(run)["answer"]
    assert [s["url"] for s in result_of(run)["sources"]] == ["https://late.test/"]
