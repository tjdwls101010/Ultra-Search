"""_store: finding a run's session on disk and copying it somewhere it will survive.

The seam is a fake ~/.aside (ULTRA_SEARCH_ASIDE_HOME) in, paths and copied bytes out.

Two things drive the design and so most of these tests. Aside deletes CLI sessions
within a day or so, which is why anything we want to keep is copied out while the run is
still going; and it writes the transcript line by line, which is why the copy is
cursor-based and never trusts a trailing partial line.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import _store


def sessions_of(home: Path) -> Path:
    return home / "u" / "0" / "sessions"


def test_finds_the_session_whose_prompt_carries_the_marker(aside_home: Path) -> None:
    found = _store.find_session_by_marker(aside_home, "us-fixture-simple")

    assert found is not None
    assert found.session_id == "SimpleSearch00001"
    assert found.path.name == "2026-08-29_SimpleSearch00001"


def test_a_marker_nobody_wrote_is_simply_not_found(aside_home: Path) -> None:
    assert _store.find_session_by_marker(aside_home, "us-never-issued") is None


def test_two_runs_of_the_same_prompt_resolve_to_different_sessions(aside_home: Path) -> None:
    """The reason correlation is by marker and not by prompt text.

    Two parallel searches of the same question produce two sessions whose user messages
    are otherwise identical; matching on the prompt would pick whichever came first for
    both, and the second run would report the first one's answer.
    """
    prompt = "같은 질문"
    for sid, marker in (("DupeAAAAAAAAAAAA1", "us-dupe-a"), ("DupeBBBBBBBBBBBB2", "us-dupe-b")):
        d = sessions_of(aside_home) / f"2026-08-29_{sid}"
        d.mkdir()
        rec = {"role": "user", "content": [{"type": "text", "text": f"{prompt}\n\n(ultra-search run {marker} — ignore this line)"}]}
        (d / "messages.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n")

    a = _store.find_session_by_marker(aside_home, "us-dupe-a")
    b = _store.find_session_by_marker(aside_home, "us-dupe-b")
    assert a is not None and b is not None
    assert a.session_id == "DupeAAAAAAAAAAAA1"
    assert b.session_id == "DupeBBBBBBBBBBBB2"


def test_a_session_directory_with_no_transcript_yet_is_skipped(aside_home: Path) -> None:
    """Aside creates the directory before the first message lands, and repl sessions
    never write one at all."""
    (sessions_of(aside_home) / "2026-08-29_EmptyDir00000001").mkdir()

    assert _store.find_session_by_marker(aside_home, "us-fixture-simple").session_id == "SimpleSearch00001"


def test_locates_a_session_by_id_regardless_of_its_date_prefix(aside_home: Path) -> None:
    p = _store.session_dir(aside_home, "WvAjHmOMXm36S58Y")

    assert p is not None and p.name == "2026-08-23_WvAjHmOMXm36S58Y"


def test_copy_appends_only_whole_lines(aside_home: Path, tmp_path: Path) -> None:
    src = sessions_of(aside_home) / "2026-08-29_UnknownShape0001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"

    cursor = _store.copy_new_lines(src, dst, since=0)

    assert cursor < src.stat().st_size
    assert dst.read_bytes().endswith(b"\n")
    assert dst.stat().st_size == cursor


def test_copy_resumes_from_the_cursor_without_duplicating(aside_home: Path, tmp_path: Path) -> None:
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"

    first = _store.copy_new_lines(src, dst, since=0)
    second = _store.copy_new_lines(src, dst, since=first)

    assert second == first
    assert dst.read_bytes() == src.read_bytes()


def test_a_shrinking_source_never_shortens_the_copy(aside_home: Path, tmp_path: Path) -> None:
    """Aside cleans up sessions on its own schedule. When the source is truncated or
    deleted underneath a live run, the copy we already made is the only remaining record
    of it -- so the copy is append-only, always."""
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(src, dst, since=0)
    kept = dst.read_bytes()

    src.write_text('{"role":"user","content":[{"type":"text","text":"짧아짐"}]}\n')
    after = _store.copy_new_lines(src, dst, since=cursor)

    assert dst.read_bytes() == kept
    assert after == cursor


def test_a_lost_copy_is_rebuilt_rather_than_resumed_past(aside_home: Path, tmp_path: Path) -> None:
    """The cursor describes the destination, not the source. If the copy is truncated or
    deleted while the source is intact, continuing from the old cursor would append the
    tail onto nothing and silently lose everything before it."""
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(src, dst, since=0)
    original = dst.read_bytes()

    dst.write_bytes(b"")
    after = _store.copy_new_lines(src, dst, since=cursor)

    assert dst.read_bytes() == original
    assert after == cursor


def test_a_source_recreated_shorter_at_the_same_path_is_read_from_the_start(
    aside_home: Path, tmp_path: Path
) -> None:
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(src, dst, since=0)

    dst.unlink()
    src.write_text('{"role":"user","content":[{"type":"text","text":"새 세션"}]}\n')
    _store.copy_new_lines(src, dst, since=cursor)

    assert "새 세션" in dst.read_text(encoding="utf-8")


def test_copy_survives_the_source_disappearing(aside_home: Path, tmp_path: Path) -> None:
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"
    cursor = _store.copy_new_lines(src, dst, since=0)
    kept = dst.read_bytes()

    src.unlink()

    assert _store.copy_new_lines(src, dst, since=cursor) == cursor
    assert dst.read_bytes() == kept


def test_last_activity_is_the_newest_write_across_parent_and_children(aside_home: Path) -> None:
    parent = _store.session_dir(aside_home, "SubagentParent01")
    child = _store.session_dir(aside_home, "jYjSOAaKKm79uXXI")
    (child / "messages.jsonl").touch()

    newest = _store.last_activity(aside_home, "SubagentParent01", ["jYjSOAaKKm79uXXI"])

    assert newest >= (parent / "messages.jsonl").stat().st_mtime
    assert newest == pytest.approx((child / "messages.jsonl").stat().st_mtime, abs=1)


# --- the database, which for CLI runs is usually simply not there ------------------


def test_a_missing_database_is_not_an_error(aside_home: Path) -> None:
    """Ephemeral CLI sessions were observed writing no rows at all -- neither sessions
    nor session_runs. The transcript on disk is the source of truth; the database only
    ever adds detail."""
    assert not (aside_home / "u" / "0" / "state.db").exists()

    assert _store.db_session_row(aside_home, "SimpleSearch00001") is None
    assert _store.db_finished_at(aside_home, "SimpleSearch00001") is None


def test_database_details_are_reported_when_they_do_exist(aside_home: Path) -> None:
    db = aside_home / "u" / "0" / "state.db"
    con = sqlite3.connect(db)
    con.execute(
        "create table sessions (id text primary key, parent_id text, status text, "
        "suspension text, ephemeral integer, created_at integer, updated_at integer)"
    )
    con.execute(
        "insert into sessions values ('SimpleSearch00001', null, 'running', "
        "'{\"kind\":\"approval\"}', 1, 100, 200)"
    )
    con.commit()
    con.close()

    row = _store.db_session_row(aside_home, "SimpleSearch00001")
    assert row["status"] == "running"
    assert row["suspension"] == '{"kind":"approval"}'


def test_a_database_missing_the_expected_tables_degrades_quietly(aside_home: Path) -> None:
    db = aside_home / "u" / "0" / "state.db"
    con = sqlite3.connect(db)
    con.execute("create table something_else (id text)")
    con.commit()
    con.close()

    assert _store.db_session_row(aside_home, "SimpleSearch00001") is None


def test_a_copy_that_got_ahead_of_the_cursor_is_not_duplicated(aside_home: Path, tmp_path: Path) -> None:
    """The supervisor appends and then records the new cursor as a separate step. Dying
    between the two leaves the destination ahead of what meta remembers -- and re-copying
    from the remembered position duplicates records, which are then counted twice in
    usage, sources and child discovery."""
    src = sessions_of(aside_home) / "2026-08-29_SimpleSearch00001" / "messages.jsonl"
    dst = tmp_path / "copy.jsonl"
    full = _store.copy_new_lines(src, dst, since=0)
    complete = dst.read_bytes()

    # meta still holds a cursor from before the last append.
    stale_cursor = full // 2
    after = _store.copy_new_lines(src, dst, since=stale_cursor)

    assert dst.read_bytes() == complete
    assert after == full
