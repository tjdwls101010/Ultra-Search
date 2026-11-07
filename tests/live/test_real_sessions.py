"""This machine's own recent Aside sessions, read the way the skill reads them. Skipped unless run with `-m live`.

Every other test reads transcripts shaped after real ones, and stays green when Aside changes the real shape: 454
tests passed while records were being split apart and pages lost. These read what the installed Aside actually
wrote and hold the invariants that broke. Nothing from those sessions enters the repository; a failure names what
it found. Run after every Aside update.
"""
from __future__ import annotations

import os

import pytest

from ultra_search import aside

pytestmark = pytest.mark.live

#: How many of the newest sessions to read.
RECENT = 60
#: Tool names the skill has seen and reads: a new one is not an error, but it is a format change to look at.
KNOWN_TOOLS = {"websearch", "webfetch", "repl", "bash", "read_file", "subagent", "subagent_wait", "write_todos",
               "get_time", "memory_search", "history_search", "closeTab"}


@pytest.fixture(scope="module")
def recent() -> list:
    root = aside.sessions_root()
    found = [d / "messages.jsonl" for d in root.iterdir() if (d / "messages.jsonl").is_file()]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not found:
        pytest.skip(f"no Aside session under {root}")
    return [(p, aside.read_events(p)[0]) for p in found[:RECENT]]


def test_every_record_is_one_event(recent) -> None:
    """Aside ends a record at "\\n" alone; reading it any other way splits a record and loses what it held."""
    split = []
    for path, events in recent:
        data = path.read_bytes()
        records = sum(1 for line in data[: data.rfind(b"\n") + 1].split(b"\n") if line.strip())
        if records != len(events):
            split.append(f"{path.parent.name}: {records} records, {len(events)} events")
    assert split == []


def test_every_record_is_one_this_skill_reads(recent) -> None:
    unread = [f"{path.parent.name}#{e.index}: {e.content[:120]}" for path, events in recent for e in events if e.kind == "raw"]
    assert unread == []


def test_every_tool_called_is_one_this_skill_has_seen(recent) -> None:
    new = {c.name for _, events in recent for e in events for c in e.tool_calls} - KNOWN_TOOLS
    assert new == set(), "a tool this skill has not seen -- check how its results name pages and files"


def test_every_saved_file_a_result_names_is_there(recent) -> None:
    """`Downloaded to:` and `Full output saved to:` are read as a path; one that does not exist means the notice
    changed shape and is being read wrong."""
    gone = [f"{path.parent.name}: {s.saved_path}" for path, events in recent for e in events for s in e.sources
            if s.saved_path and not os.path.exists(s.saved_path)]
    assert gone == []
