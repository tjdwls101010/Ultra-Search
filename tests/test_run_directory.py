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
from pathlib import Path

import pytest

import _registry
import _store
import _supervisor
from conftest import SCRIPTS, aside_session, answer, calling, tool, user

SESSIONS = Path(__file__).parent / "fixtures" / "sessions"


def start(runs_dir: Path, prompt: str = "질문") -> _registry.Run:
    """A run reserved the way `search` reserves one, before its supervisor starts."""
    run = _registry.create_run(runs_dir, label="t", prompt=prompt)
    run.update_meta(marker=_registry.marker_for(run.run_id))
    return run


def supervise(run: _registry.Run, **kw) -> dict:
    kw.setdefault("poll", 0.05)
    kw.setdefault("discovery_deadline", 5.0)
    kw.setdefault("settle", 0.5)
    return _supervisor.supervise(run, **kw)


def result_of(run: _registry.Run) -> dict:
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
    run = _registry.create_run(runs_dir, label="x")
    run.write_meta({"state": "running", "marker": "us-abc", "prompt": "질문"})

    written = run.update_meta(state="completed", answer_count=3)

    assert written == {"state": "completed", "marker": "us-abc", "prompt": "질문", "answer_count": 3}
    assert _registry.load_meta(run.path) == written


def test_a_meta_write_is_all_or_nothing(runs_dir: Path) -> None:
    """`status` may read meta.json at any moment. A value that cannot be serialised fails
    before the file is touched, so a reader sees the old file or the new one."""
    run = _registry.create_run(runs_dir, label="x")
    run.write_meta({"state": "running"})
    before = run.meta_path.read_bytes()

    with pytest.raises(TypeError):
        run.write_meta({"state": "done", "bad": {1, 2}})

    assert run.meta_path.read_bytes() == before
    assert [p.name for p in run.path.iterdir() if p.name.endswith(".tmp")] == []


def test_concurrent_meta_updates_do_not_lose_each_others_keys(runs_dir: Path) -> None:
    """meta.json is written by the starting CLI, the detached supervisor and `stop`, each
    doing read-modify-write. Without serialisation the loser's keys vanish."""
    run = _registry.create_run(runs_dir, label="race")
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
    run = _registry.create_run(runs_dir, label="procs")
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(SCRIPTS)!r})
        import _registry
        run = _registry.Run(run_id={run.run_id!r}, path=__import__("pathlib").Path({str(run.path)!r}))
        run.update_meta(**{{sys.argv[1]: sys.argv[1]}})
        """
    )
    procs = [subprocess.Popen([sys.executable, "-c", script, f"key{i}"]) for i in range(8)]
    for p in procs:
        assert p.wait(timeout=60) == 0

    assert [f"key{i}" for i in range(8) if f"key{i}" not in run.meta()] == []


def test_runs_reserved_in_the_same_second_get_different_ids(runs_dir: Path) -> None:
    """A group starts every member at once. Reserving the directory with O_EXCL is what makes
    the loser pick a new id instead of writing its metadata over the winner's."""
    got: list[_registry.Run] = []
    threads = [threading.Thread(target=lambda: got.append(_registry.create_run(runs_dir, label="same"))) for _ in range(8)]
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

    first = _store.copy_new_lines(src, dst, since=0)
    with src.open("a") as f:
        f.write(' 줄"}],"stopReason":"stop"}\n')
    second = _store.copy_new_lines(src, dst, since=first)

    assert first == len(whole.encode())
    assert dst.read_bytes() == src.read_bytes()
    assert second == src.stat().st_size


def test_a_copy_resumes_from_its_cursor_without_duplicating(source: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy.jsonl"

    first = _store.copy_new_lines(source, dst, since=0)
    second = _store.copy_new_lines(source, dst, since=first)

    assert second == first
    assert dst.read_bytes() == source.read_bytes()


def test_a_shrinking_or_vanishing_source_never_shortens_the_copy(source: Path, tmp_path: Path) -> None:
    """Aside cleans up sessions on its own schedule. The copy is then the only remaining
    record, so it is append-only, always."""
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(source, dst, since=0)
    kept = dst.read_bytes()

    source.write_text(json.dumps(user("짧아짐")) + "\n")
    assert _store.copy_new_lines(source, dst, since=cursor) == cursor
    source.unlink()
    assert _store.copy_new_lines(source, dst, since=cursor) == cursor

    assert dst.read_bytes() == kept


def test_a_lost_copy_is_rebuilt_rather_than_resumed_past(source: Path, tmp_path: Path) -> None:
    """The cursor describes the destination, not the source. Continuing from the old cursor
    onto an emptied copy would silently lose everything before it."""
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(source, dst, since=0)
    original = dst.read_bytes()

    dst.write_bytes(b"")

    assert _store.copy_new_lines(source, dst, since=cursor) == cursor
    assert dst.read_bytes() == original


def test_a_source_recreated_shorter_is_read_from_the_start_into_a_new_copy(source: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(source, dst, since=0)

    dst.unlink()
    source.write_text(json.dumps(user("새 세션"), ensure_ascii=False) + "\n")
    _store.copy_new_lines(source, dst, since=cursor)

    assert "새 세션" in dst.read_text(encoding="utf-8")


def test_a_copy_that_got_ahead_of_the_cursor_is_not_duplicated(source: Path, tmp_path: Path) -> None:
    """The supervisor appends and then records the new cursor as a separate step. Dying
    between the two leaves the destination ahead of what meta remembers -- and re-copying
    from the remembered position would count records twice in usage, sources and children."""
    dst = tmp_path / "copy.jsonl"
    full = _store.copy_new_lines(source, dst, since=0)
    complete = dst.read_bytes()

    after = _store.copy_new_lines(source, dst, since=full // 2)

    assert dst.read_bytes() == complete
    assert after == full


def test_stop_never_overwrites_a_run_that_finished_while_it_waited(runs_dir: Path) -> None:
    """`stop` asks the supervisor to let go and waits for it. A run that completes in that
    window has a result; recording it as abandoned would hide that result behind a state
    that says the work was cut off."""
    from conftest import run_cli

    run = _registry.create_run(runs_dir, label="race")
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
    do. Reporting it as the answer turns "let me check" into a finding."""
    records = [calling(("webfetch", {"url": "https://x.test"}), text="잠시 확인하겠습니다"), tool("webfetch", "page")]
    if ending == "stopped_empty":
        records.append({"role": "assistant", "content": [], "stopReason": "stop"})
    replay(records)
    run = start(runs_dir)

    supervise(run, settle=0.3)

    assert result_of(run)["answer"] == ""
