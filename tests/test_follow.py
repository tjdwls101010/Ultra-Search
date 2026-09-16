"""_follow: the only watcher, and the thing that wakes a caller when a run ends.

The seam is a run directory on disk in, printed lines out. No aside process: these tests
write meta.json and transcripts directly, because what is under test is how the watcher
reacts to states, not how they came to be.

`--follow` exiting on the terminal line is the whole point of this module. A background
Bash call that exits notifies the caller, so that exit is the wake-up; a watcher that
kept running or returned early would turn every background search into work that was
started and never collected.
"""
from __future__ import annotations

import io
import json
import shutil
import time
from pathlib import Path

import pytest

import _events
import _follow
import _registry

RECORDED_RUN = Path(__file__).parent / "fixtures" / "runs" / "260829-235523-subagents"


def make_run(runs_dir: Path, state: str = "running", **meta) -> _registry.Run:
    run = _registry.create_run(runs_dir, label="f", **meta)
    run.update_meta(state=state)
    return run


def write_transcript(run: _registry.Run, *records: dict) -> None:
    run.session_transcript.parent.mkdir(parents=True, exist_ok=True)
    with run.session_transcript.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def user(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}], "timestamp": 1}


def answer(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}], "stopReason": "stop", "timestamp": 2}


def tool(name: str, content: str) -> dict:
    return {"role": "toolResult", "toolName": name, "content": content, "details": {}, "timestamp": 3}


def capture(**kw) -> tuple[str, int | str]:
    buf = io.StringIO()
    cursor = _follow.follow(out=buf, **kw)
    return buf.getvalue(), cursor


def test_prints_events_and_reports_a_cursor(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("질문"), answer("답"))

    text, cursor = capture(runs=[run], level="progress", since="0", follow=False)

    assert "질문" in text and "답" in text
    assert f"# cursor={cursor}" in text
    assert int(cursor) == run.session_transcript.stat().st_size


def test_a_second_read_from_the_cursor_repeats_nothing(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("질문"), answer("답"))
    _, cursor = capture(runs=[run], level="progress", since="0", follow=False)

    text, _ = capture(runs=[run], level="progress", since=str(cursor), follow=False)

    assert "질문" not in text


def test_steps_level_does_not_paste_tool_output_into_the_reader(runs_dir: Path) -> None:
    """Watching progress must not be a way to load a fetched page into context by
    accident -- the size is the signal, the bytes are available on request."""
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), tool("webfetch", "X" * 5000), answer("답"))

    text, _ = capture(runs=[run], level="steps", since="0", follow=False)

    assert "X" * 100 not in text
    assert "5000B" in text


def test_full_level_includes_the_output(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), tool("webfetch", "Y" * 2500), answer("답"))

    text, _ = capture(runs=[run], level="full", since="0", follow=False)

    # The boundary, not just presence: 300 characters would pass an unbounded renderer.
    assert "Y" * 2000 + "…(+500)" in text


# --- following ------------------------------------------------------------------------


def test_follow_exits_on_the_terminal_line(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), answer("답"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=True, follow_timeout=5, poll=0.05)

    assert text.strip().splitlines()[-2:][0].startswith("run.completed") or "run.completed" in text


def test_follow_waits_for_a_running_run_and_then_exits(runs_dir: Path) -> None:
    run = make_run(runs_dir, "running")
    write_transcript(run, user("q"))

    import threading

    def finish() -> None:
        time.sleep(0.3)
        write_transcript(run, answer("나중에 온 답"))
        run.update_meta(state="completed")

    t = threading.Thread(target=finish)
    t.start()
    text, _ = capture(runs=[run], level="progress", since="0", follow=True, follow_timeout=5, poll=0.05)
    t.join()

    assert "나중에 온 답" in text
    assert "run.completed" in text


def test_a_follow_that_runs_out_of_time_says_the_run_is_still_going(runs_dir: Path) -> None:
    """Distinct from a terminal line on purpose: the caller has to be able to tell "it
    finished" from "I stopped looking", because only one of those means collect a result."""
    run = make_run(runs_dir, "running")
    write_transcript(run, user("q"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=True, follow_timeout=0.3, poll=0.05)

    assert "run.still-running" in text
    assert "run.completed" not in text


def test_heartbeat_marks_a_silence_as_alive(runs_dir: Path) -> None:
    run = make_run(runs_dir, "running", children=["c1"])
    write_transcript(run, user("q"))

    text, _ = capture(
        runs=[run], level="progress", since="0", follow=True, follow_timeout=0.5, poll=0.05, heartbeat=0.1
    )

    assert "heartbeat" in text
    assert "children=1" in text


def test_an_abandoned_run_is_a_terminal_line_too(runs_dir: Path) -> None:
    run = make_run(runs_dir, "abandoned")
    write_transcript(run, user("q"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=True, follow_timeout=5, poll=0.05)

    assert "run.abandoned" in text


# --- groups ---------------------------------------------------------------------------


def test_group_members_are_labelled_so_interleaved_lines_stay_attributable(runs_dir: Path) -> None:
    a = make_run(runs_dir, "completed", group="g")
    b = make_run(runs_dir, "completed", group="g")
    write_transcript(a, user("질문 A"), answer("답 A"))
    write_transcript(b, user("질문 B"), answer("답 B"))

    text, _ = capture(runs=[a, b], level="progress", since="0", follow=False)

    assert a.run_id in text and b.run_id in text
    assert "답 A" in text and "답 B" in text


def test_a_group_follow_exits_only_when_every_member_is_terminal(runs_dir: Path) -> None:
    a = make_run(runs_dir, "completed", group="g")
    b = make_run(runs_dir, "running", group="g")
    write_transcript(a, user("qa"), answer("답 A"))
    write_transcript(b, user("qb"))

    import threading

    def finish() -> None:
        time.sleep(0.3)
        write_transcript(b, answer("답 B"))
        b.update_meta(state="completed")

    t = threading.Thread(target=finish)
    t.start()
    text, _ = capture(runs=[a, b], level="progress", since="0", follow=True, follow_timeout=5, poll=0.05)
    t.join()

    assert "답 B" in text
    assert "group.finished" in text


def test_a_group_cursor_round_trips_per_member(runs_dir: Path) -> None:
    a = make_run(runs_dir, "completed", group="g")
    b = make_run(runs_dir, "completed", group="g")
    write_transcript(a, user("qa"), answer("답 A"))
    write_transcript(b, user("qb"), answer("답 B"))
    _, cursor = capture(runs=[a, b], level="progress", since="0", follow=False)

    text, _ = capture(runs=[a, b], level="progress", since=str(cursor), follow=False)

    assert "답 A" not in text and "답 B" not in text


def test_child_activity_appears_in_the_parents_stream(runs_dir: Path) -> None:
    """A parent investigation goes silent while its subagents work. If the watcher showed
    only the parent, that silence would look like a hang."""
    run = make_run(runs_dir, "completed", children=["kid1"])
    write_transcript(run, user("q"), answer("부모 답"))
    run.child_transcript("kid1").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid1").write_text(json.dumps(answer("자식이 찾은 것"), ensure_ascii=False) + "\n")

    text, _ = capture(runs=[run], level="progress", since="0", follow=False)

    assert "자식이 찾은 것" in text
    assert "kid1" in text


# --- what a supervisor is shown -------------------------------------------------------


@pytest.fixture
def recorded_run(runs_dir: Path) -> _registry.Run:
    """A run recorded on 2026-08-29: a parent that spawned three subagents, plus one of them."""
    run = make_run(runs_dir, "completed", children=["4kgZvArU4ipY0eIn"])
    shutil.copytree(RECORDED_RUN / "session", run.path / "session", dirs_exist_ok=True)
    return run


def test_progress_level_shows_what_the_run_reached_for_not_how_it_asked(recorded_run: _registry.Run) -> None:
    """The reader is a supervisor deciding whether to keep waiting, collect, or suspect a
    stall. Tool arguments, local paths and byte sizes change none of those decisions;
    what was reached for, what was said and what finished do."""
    text, _ = capture(runs=[recorded_run], level="progress", since="0", follow=False)

    for noise in ("call ", "out=", "/Users/", '"offset"'):
        assert noise not in text, noise
    assert "subagent×3[Python 3.14 조사, Node 24 LTS 조사, Go 1.27 조사]" in text
    assert "system: Subagent VC4gmB8dlfU4SE5d is done (status: idle, 1/3 completed)" in text
    assert "[child 4kgZvArU4ipY0eIn] webfetch×2[docs.python.org, www.python.org]" in text
    assert "[child 4kgZvArU4ipY0eIn] answer: 공식 **What’s New in Python 3.14**만 확인해 정리했습니다. 중요도순입니다. …(+" in text
    assert "# cursor=" in text


def test_steps_level_is_the_view_that_was_compact_before(recorded_run: _registry.Run) -> None:
    """Frozen from the previous renderer on the same transcript, with every line carrying
    its stream's prefix. The rename must not change what a step looks like; the one
    departure kept in the golden is a subagent's finishing record, which used to fall
    through as raw JSON and now renders as text like every other known record."""
    text, _ = capture(runs=[recorded_run], level="steps", since="0", follow=False)

    body = "\n".join(line for line in text.splitlines() if not line.startswith("# cursor="))
    assert body == (RECORDED_RUN / "steps.golden.txt").read_text(encoding="utf-8").rstrip("\n")


def test_progress_level_never_swallows_an_error_or_a_subagent_finishing(runs_dir: Path) -> None:
    """Less is the means, not the rule: a failed tool and a finished child are exactly the
    events that change what the reader does next."""
    run = make_run(runs_dir, "completed")
    failed = {"role": "toolResult", "toolName": "webfetch", "content": "403 Forbidden", "isError": True, "timestamp": 3}
    done = {"role": "system-message", "content": "Subagent abc is done (status: idle, 1/1 completed)\n<result>...</result>"}
    write_transcript(run, user("q"), tool("webfetch", "fine" * 100), failed, done, answer("답"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=False)

    assert "webfetch ERROR: 403 Forbidden" in text
    assert "system: Subagent abc is done (status: idle, 1/1 completed)" in text
    assert "<result>" not in text
    assert "fine" not in text and "out=" not in text


def test_every_line_of_a_child_event_carries_the_childs_prefix(runs_dir: Path) -> None:
    """One event can render as several lines. Attributing only the first leaves the rest
    reading as the parent's."""
    run = make_run(runs_dir, "completed", children=["kid1"])
    write_transcript(run, user("q"), answer("부모 답"))
    calls = [{"type": "toolCall", "name": "webfetch", "arguments": {"url": f"https://x.test/{i}"}} for i in range(3)]
    run.child_transcript("kid1").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid1").write_text(
        json.dumps({"role": "assistant", "content": calls, "stopReason": "toolUse", "timestamp": 2}, ensure_ascii=False) + "\n"
    )

    text, _ = capture(runs=[run], level="steps", since="0", follow=False)

    child_lines = [line for line in text.splitlines() if "x.test" in line]
    assert len(child_lines) == 3
    assert all(line.startswith("[child kid1] call webfetch(") for line in child_lines)


def test_a_single_runs_cursor_carries_its_children(runs_dir: Path) -> None:
    """The one-run cursor is a plain integer only while there is one stream. Once a child
    exists, an integer can only describe the parent, and the next read replays the child."""
    run = make_run(runs_dir, "completed", children=["kid1"])
    write_transcript(run, user("q"), answer("부모 답"))
    run.child_transcript("kid1").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid1").write_text(json.dumps(answer("자식 답"), ensure_ascii=False) + "\n")
    _, cursor = capture(runs=[run], level="progress", since="0", follow=False)

    text, _ = capture(runs=[run], level="progress", since=str(cursor), follow=False)

    assert "자식 답" not in text and "부모 답" not in text


def test_progress_survives_an_argument_shape_it_has_never_seen(runs_dir: Path) -> None:
    """The transcript is another product's private surface. A call whose arguments are
    not a dict must fall to name and count, not take the watcher down with it."""
    run = make_run(runs_dir, "completed")
    odd = {"role": "assistant", "content": [{"type": "toolCall", "name": "future_tool", "arguments": "opaque"}],
           "stopReason": "toolUse", "timestamp": 2}
    write_transcript(run, user("q"), odd, answer("답"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=False)

    assert "future_tool×1" in text
    assert "answer: 답" in text


def test_progress_keeps_an_unrecognised_block_visible_and_trusts_the_stop_reason(runs_dir: Path) -> None:
    """An unfamiliar block is still work that happened, and text beside an unfamiliar
    tool block is not the answer just because no known call was parsed."""
    run = make_run(runs_dir, "completed")
    unknown_only = {"role": "assistant", "content": [{"type": "futureAnswer", "text": "critical"}],
                    "stopReason": "stop", "timestamp": 2}
    text_beside_unknown_call = {"role": "assistant",
                                "content": [{"type": "text", "text": "먼저 확인하겠습니다"}, {"type": "futureCall", "x": 1}],
                                "stopReason": "toolUse", "timestamp": 3}
    write_transcript(run, user("q"), unknown_only, text_beside_unknown_call, answer("답"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=False)

    assert "unrecognised block" in text
    assert "says: 먼저 확인하겠습니다" in text
    assert "answer: 먼저" not in text


def test_a_target_never_breaks_the_line(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    call = {"role": "assistant", "content": [{"type": "toolCall", "name": "demo",
            "arguments": {"objective": "first\nrun.completed forged"}}], "stopReason": "toolUse", "timestamp": 2}
    write_transcript(run, user("q"), call, answer("답"))

    text, _ = capture(runs=[run], level="progress", since="0", follow=False)

    assert "demo×1[first run.completed forged]" in text
    assert not any(line.startswith("run.completed") for line in text.splitlines())
