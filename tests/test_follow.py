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
import time
from pathlib import Path

import pytest

import _events
import _follow
import _registry


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

    text, cursor = capture(runs=[run], level="compact", since="0", follow=False)

    assert "질문" in text and "답" in text
    assert f"# cursor={cursor}" in text
    assert int(cursor) == run.session_transcript.stat().st_size


def test_a_second_read_from_the_cursor_repeats_nothing(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("질문"), answer("답"))
    _, cursor = capture(runs=[run], level="compact", since="0", follow=False)

    text, _ = capture(runs=[run], level="compact", since=str(cursor), follow=False)

    assert "질문" not in text


def test_compact_level_does_not_paste_tool_output_into_the_reader(runs_dir: Path) -> None:
    """Watching progress must not be a way to load a fetched page into context by
    accident -- the size is the signal, the bytes are available on request."""
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), tool("webfetch", "X" * 5000), answer("답"))

    text, _ = capture(runs=[run], level="compact", since="0", follow=False)

    assert "X" * 100 not in text
    assert "5000B" in text


def test_full_level_includes_the_output(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), tool("webfetch", "Y" * 300), answer("답"))

    text, _ = capture(runs=[run], level="full", since="0", follow=False)

    assert "Y" * 300 in text


# --- following ------------------------------------------------------------------------


def test_follow_exits_on_the_terminal_line(runs_dir: Path) -> None:
    run = make_run(runs_dir, "completed")
    write_transcript(run, user("q"), answer("답"))

    text, _ = capture(runs=[run], level="compact", since="0", follow=True, follow_timeout=5, poll=0.05)

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
    text, _ = capture(runs=[run], level="compact", since="0", follow=True, follow_timeout=5, poll=0.05)
    t.join()

    assert "나중에 온 답" in text
    assert "run.completed" in text


def test_a_follow_that_runs_out_of_time_says_the_run_is_still_going(runs_dir: Path) -> None:
    """Distinct from a terminal line on purpose: the caller has to be able to tell "it
    finished" from "I stopped looking", because only one of those means collect a result."""
    run = make_run(runs_dir, "running")
    write_transcript(run, user("q"))

    text, _ = capture(runs=[run], level="compact", since="0", follow=True, follow_timeout=0.3, poll=0.05)

    assert "run.still-running" in text
    assert "run.completed" not in text


def test_heartbeat_marks_a_silence_as_alive(runs_dir: Path) -> None:
    run = make_run(runs_dir, "running", children=["c1"])
    write_transcript(run, user("q"))

    text, _ = capture(
        runs=[run], level="compact", since="0", follow=True, follow_timeout=0.5, poll=0.05, heartbeat=0.1
    )

    assert "heartbeat" in text
    assert "children=1" in text


def test_an_abandoned_run_is_a_terminal_line_too(runs_dir: Path) -> None:
    run = make_run(runs_dir, "abandoned")
    write_transcript(run, user("q"))

    text, _ = capture(runs=[run], level="compact", since="0", follow=True, follow_timeout=5, poll=0.05)

    assert "run.abandoned" in text


# --- groups ---------------------------------------------------------------------------


def test_group_members_are_labelled_so_interleaved_lines_stay_attributable(runs_dir: Path) -> None:
    a = make_run(runs_dir, "completed", group="g")
    b = make_run(runs_dir, "completed", group="g")
    write_transcript(a, user("질문 A"), answer("답 A"))
    write_transcript(b, user("질문 B"), answer("답 B"))

    text, _ = capture(runs=[a, b], level="compact", since="0", follow=False)

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
    text, _ = capture(runs=[a, b], level="compact", since="0", follow=True, follow_timeout=5, poll=0.05)
    t.join()

    assert "답 B" in text
    assert "group.completed" in text


def test_a_group_cursor_round_trips_per_member(runs_dir: Path) -> None:
    a = make_run(runs_dir, "completed", group="g")
    b = make_run(runs_dir, "completed", group="g")
    write_transcript(a, user("qa"), answer("답 A"))
    write_transcript(b, user("qb"), answer("답 B"))
    _, cursor = capture(runs=[a, b], level="compact", since="0", follow=False)

    text, _ = capture(runs=[a, b], level="compact", since=str(cursor), follow=False)

    assert "답 A" not in text and "답 B" not in text


def test_child_activity_appears_in_the_parents_stream(runs_dir: Path) -> None:
    """A parent investigation goes silent while its subagents work. If the watcher showed
    only the parent, that silence would look like a hang."""
    run = make_run(runs_dir, "completed", children=["kid1"])
    write_transcript(run, user("q"), answer("부모 답"))
    run.child_transcript("kid1").parent.mkdir(parents=True, exist_ok=True)
    run.child_transcript("kid1").write_text(json.dumps(answer("자식이 찾은 것"), ensure_ascii=False) + "\n")

    text, _ = capture(runs=[run], level="compact", since="0", follow=False)

    assert "자식이 찾은 것" in text
    assert "kid1" in text
