"""_events: turning a session's messages.jsonl into things a caller can act on.

The seam is the file's bytes in, typed events out -- no aside process, no daemon. Every
test here reads a fixture recorded from a real session, so a schema change upstream
fails these rather than silently changing what `result` reports.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import _events


@pytest.fixture
def simple(fixtures: Path) -> Path:
    return fixtures / "sessions" / "2026-08-29_SimpleSearch00001" / "messages.jsonl"


@pytest.fixture
def unknown(fixtures: Path) -> Path:
    return fixtures / "sessions" / "2026-08-29_UnknownShape0001" / "messages.jsonl"


def test_reads_a_recorded_search_as_ordered_events(simple: Path) -> None:
    events, cursor = _events.read_events(simple)

    assert [e.kind for e in events] == ["user", "assistant", "tool_result", "assistant"]
    assert cursor == simple.stat().st_size


def test_tool_call_arguments_survive_parsing(simple: Path) -> None:
    events, _ = _events.read_events(simple)

    calls = [c for e in events for c in e.tool_calls]
    assert [c.name for c in calls] == ["websearch"]
    assert "search_queries" in calls[0].arguments


def test_final_answer_is_the_last_assistant_text(simple: Path) -> None:
    events, _ = _events.read_events(simple)

    answer = _events.final_answer(events)
    assert "3.14.7" in answer


def test_citation_tags_become_readable_references(simple: Path) -> None:
    events, _ = _events.read_events(simple)

    answer = _events.final_answer(events)
    assert "<citation" not in answer
    # The recorded run cited source aQzmmOfnlbkdc2ZD_mUd1, which is http://python.org/.
    # Asserting the resolved URL and not just the label is the point: a lookup that finds
    # nothing also strips the tag, and would pass a laxer assertion.
    assert "http://python.org/" in answer
    assert "Python.org의 최신 안정 버전" in answer


def test_a_citation_to_an_unknown_source_keeps_its_label(simple: Path) -> None:
    events, _ = _events.read_events(simple)
    text = 'See <citation refs="nosuchref">the release notes</citation> for detail.'

    resolved = _events.resolve_citations(text, _events.collect_sources(events))
    assert resolved == "See the release notes for detail."


def test_sources_distinguish_seen_from_actually_read(simple: Path) -> None:
    events, _ = _events.read_events(simple)

    sources = _events.collect_sources(events)
    assert sources, "a search that cited a URL must report at least one source"
    assert all(s.url for s in sources)
    # This run only ran websearch -- it listed results, it never opened one.
    assert all(s.opened is False for s in sources)


def test_a_fetched_page_counts_as_opened(fixtures: Path) -> None:
    child = fixtures / "sessions" / "2026-08-23_xtXKs5dqLhtZ9sCN" / "messages.jsonl"
    events, _ = _events.read_events(child)

    sources = _events.collect_sources(events)
    assert [s.opened for s in sources] == [True]


def test_usage_totals_across_every_assistant_turn(simple: Path) -> None:
    events, _ = _events.read_events(simple)

    usage = _events.total_usage(events)
    assert usage["total_tokens"] == 10813 + 18580
    assert usage["cost"] > 0


def test_subagent_children_are_discoverable_from_the_parent(fixtures: Path) -> None:
    parent = fixtures / "sessions" / "2026-08-23_SubagentParent01" / "messages.jsonl"
    events, _ = _events.read_events(parent)

    assert _events.child_session_ids(events) == [
        "WvAjHmOMXm36S58Y",
        "jYjSOAaKKm79uXXI",
        "xtXKs5dqLhtZ9sCN",
    ]


def test_an_unrecognised_record_is_kept_as_raw_not_dropped(unknown: Path) -> None:
    events, _ = _events.read_events(unknown)

    kinds = [e.kind for e in events]
    assert "raw" in kinds, "an unknown role must survive as raw -- dropping it hides work that happened"
    assert kinds.count("raw") == 1


def test_an_unrecognised_content_block_does_not_lose_its_siblings(unknown: Path) -> None:
    events, _ = _events.read_events(unknown)

    assert _events.final_answer(events) == "끝."


def test_a_half_written_line_is_left_for_the_next_read(unknown: Path) -> None:
    events, cursor = _events.read_events(unknown)

    assert cursor < unknown.stat().st_size, "the torn last line must not be consumed"
    assert all(e.kind != "torn" for e in events)
    # Re-reading from the cursor yields nothing until the writer completes the line.
    again, cursor2 = _events.read_events(unknown, since=cursor)
    assert again == []
    assert cursor2 == cursor


def test_a_completed_line_is_picked_up_on_the_next_read(unknown: Path, tmp_path: Path) -> None:
    growing = tmp_path / "messages.jsonl"
    growing.write_bytes(unknown.read_bytes())
    _, cursor = _events.read_events(growing)

    with growing.open("a") as f:
        f.write('"}],"stopReason":"stop","timestamp":1787483300000}\n')
    events, cursor2 = _events.read_events(growing, since=cursor)

    assert [e.kind for e in events] == ["assistant"]
    assert cursor2 == growing.stat().st_size


def test_compact_level_reports_tool_output_size_instead_of_its_bytes(simple: Path) -> None:
    events, _ = _events.read_events(simple)
    result = next(e for e in events if e.kind == "tool_result")

    line = _events.render(result, level="compact")
    assert "websearch" in line
    assert str(len(result.content)) in line or "B" in line
    assert result.content[:200] not in line


def test_raw_level_prints_the_stored_record_unchanged(simple: Path) -> None:
    events, _ = _events.read_events(simple)
    result = next(e for e in events if e.kind == "tool_result")

    assert '"toolName"' in _events.render(result, level="raw")
