"""What Aside actually wrote, read through the aside unit into this skill's terms.

The fixtures are recordings: a parent and its subagent from daemon 1.26.1001.14 (every turn
framed by lifecycle records, the subagent given a second task), its stdout, and sessions
from before the lifecycle records existed. When Aside changes how it writes any of these,
these tests break first -- and the fix belongs in `aside/`, which is the only place that
reads them. The expected values are read off the recordings, not off this code's output.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ultra_search import aside

FIXTURES = Path(__file__).parent / "fixtures"
RECORDED = FIXTURES / "runs" / "261002-lifecycle-subagent"
PARENT = RECORDED / "session" / "messages.jsonl"
CHILD = RECORDED / "session" / "children" / "ZFgNUcNIKq1MWMz4.jsonl"
LEGACY = FIXTURES / "sessions"


def events(path: Path) -> list[aside.Event]:
    return aside.read_events(path)[0]


def prefix(path: Path, n: int, tmp_path: Path) -> list[aside.Event]:
    """The first ``n`` records, as a reader polling the transcript mid-run would see them."""
    cut = tmp_path / f"prefix-{n}.jsonl"
    cut.write_text("".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:n]), encoding="utf-8")
    return events(cut)


# --- records ----------------------------------------------------------------------------------


def test_a_recorded_turn_reads_as_its_kinds_with_its_frame() -> None:
    got = [(e.kind, e.lifecycle or e.stop or e.tool_name) for e in events(PARENT)]

    assert got == [
        ("lifecycle", "started"), ("user", ""),
        ("assistant", "tool"), ("tool_result", "subagent"), ("assistant", "tool"), ("tool_result", "subagent_wait"),
        ("system", ""), ("assistant", "tool"), ("tool_result", "subagent"), ("assistant", "tool"),
        ("tool_result", "subagent_wait"), ("system", ""),
        ("lifecycle", "final-started"), ("assistant", "end"), ("lifecycle", "finished"),
    ]


def test_a_subagent_is_named_by_the_results_that_started_and_awaited_it() -> None:
    named = [e.child_ids for e in events(PARENT) if e.kind == "tool_result"]

    assert named == [["ZFgNUcNIKq1MWMz4"]] * 4


def test_usage_comes_out_in_this_skills_keys_and_as_numbers() -> None:
    first = next(e for e in events(PARENT) if e.kind == "assistant")

    assert first.usage == {"input": 10462, "output": 79, "cache_read": 0, "cache_write": 0, "reasoning": 0,
                           "total_tokens": 10541, "cost": pytest.approx(0.021714)}
    assert sum(e.usage.get("total_tokens", 0) for e in events(PARENT)) == 10541 + 10843 + 11350 + 11645 + 12082


def test_a_page_a_fetch_returned_is_a_source_it_opened() -> None:
    sources = [s for e in events(CHILD) if e.tool_name == "webfetch" for s in e.sources]

    assert [(s.url, s.id, s.opened) for s in sources] == [
        ("https://www.python.org/downloads/", "RRY-TcWzgg1MznOsnlqMd", True),
        ("https://www.python.org/downloads/", "cPvWvEirM0bvXVllioGJx", True),
    ]


def test_a_page_opened_in_a_browser_tab_is_a_source_it_opened() -> None:
    """The REPL lists no sources, but says which page a tab opened and which page a snapshot
    read. The recorded child read python.org this way after its fetches came back empty."""
    read = [(s.url, s.title, s.opened) for e in events(CHILD) if e.tool_name == "repl" for s in e.sources]

    assert read == [("https://www.python.org/downloads/", "Download Python | Python.org", True)]


def repl_result(text: str, *, error: bool = False) -> str:
    return json.dumps({"role": "toolResult", "toolName": "repl", "content": [{"type": "text", "text": text}],
                       "details": {"elapsedMs": 1}, "isError": error})


def sources_of(line: str) -> list[tuple[str, str]]:
    return [(s.url, s.title) for s in aside.read_events(_write(line))[0][0].sources]


def _write(line: str) -> Path:
    import tempfile
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write(line + "\n")
    f.close()
    return Path(f.name)


def test_browser_pages_come_in_the_order_they_were_printed() -> None:
    printed = ('- title: "A" [url=https://e.test/a]\n  - link "x"\n'
               "✔︎ Opened a new tab and set it active: tabs[1], page → B (https://e.test/b)")

    assert sources_of(repl_result(printed)) == [("https://e.test/a", "A"), ("https://e.test/b", "B")]


def test_a_url_with_parentheses_is_kept_whole() -> None:
    printed = "✔︎ Opened a new tab and set it active: tabs[0], page → Function (https://en.wikipedia.org/wiki/Function_(mathematics))"

    assert sources_of(repl_result(printed)) == [("https://en.wikipedia.org/wiki/Function_(mathematics)", "Function")]


def test_a_page_opened_before_the_call_failed_is_still_opened() -> None:
    printed = "✔︎ Opened a new tab and set it active: tabs[0], page → A (https://e.test/a)\nTypeError: x is not a function"

    assert sources_of(repl_result(printed, error=True)) == [("https://e.test/a", "A")]


def test_page_text_that_mentions_a_page_is_not_an_opened_page() -> None:
    printed = '- title: "A" [url=https://e.test/a]\n  The docs say page → Other (https://e.test/other)'

    assert sources_of(repl_result(printed)) == [("https://e.test/a", "A")]


def test_an_assistant_message_that_stopped_on_an_error_says_so() -> None:
    event = aside.read_events(_write(json.dumps({"role": "assistant", "content": [], "stopReason": "error"})))[0][0]

    assert event.stop == "error" and event.stopped


def test_a_search_listing_is_a_source_not_opened() -> None:
    listed = [s for e in events(LEGACY / "2026-08-29_SimpleSearch00001" / "messages.jsonl") for s in e.sources]

    assert listed and not any(s.opened for s in listed)


def test_what_a_call_reached_for_is_one_line() -> None:
    calls = [c for e in events(PARENT) for c in e.tool_calls]

    assert [(c.name, c.target) for c in calls] == [
        ("subagent", "Check latest Python release"), ("subagent_wait", ""), ("subagent", ""), ("subagent_wait", ""),
    ]


def test_an_unfamiliar_record_or_block_is_kept() -> None:
    got = events(LEGACY / "2026-08-29_UnknownShape0001" / "messages.jsonl")

    assert any(e.kind == "raw" for e in got)
    assert any(e.unknown_blocks for e in got if e.kind == "assistant")


# --- when a turn is over --------------------------------------------------------------------------


@pytest.mark.parametrize("records,finished", [
    (8, False),   # the first task's answer is written, its `finished` is not
    (9, True),    # the first task closed
    (10, False),  # the second task has started
    (17, False),  # the second task's answer, before its `finished`
    (18, True),
])
def test_a_turn_is_over_at_finished_and_reopens_at_started(tmp_path: Path, records: int, finished: bool) -> None:
    assert aside.turn_finished(prefix(CHILD, records, tmp_path)) is finished


def test_without_lifecycle_records_the_last_message_decides() -> None:
    simple = events(LEGACY / "2026-08-29_SimpleSearch00001" / "messages.jsonl")

    assert aside.turn_finished(simple) is True
    assert aside.turn_finished(simple[:-1]) is False


# --- finding a session ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "home" / "u" / "0" / "sessions"
    for name, source in (("2026-10-02_0lt6LxEfzahYuKsc", PARENT), ("2026-10-02_ZFgNUcNIKq1MWMz4", CHILD)):
        (root / name).mkdir(parents=True)
        shutil.copy(source, root / name / "messages.jsonl")
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_HOME", str(tmp_path / "home"))
    return root


def test_a_session_is_found_by_the_marker_behind_its_opening_record(home: Path) -> None:
    assert aside.find_session_by_marker("ultra-search:261002-090000-python-latest") == "0lt6LxEfzahYuKsc"
    assert aside.find_session_by_marker("ultra-search:no-such-run") is None


def test_a_session_summary_carries_the_whole_opening_prompt(home: Path) -> None:
    summaries = {s["session_id"]: s for s in aside.session_summaries(limit=10)}

    opening = json.loads(PARENT.read_text(encoding="utf-8").splitlines()[1])["content"][0]["text"]
    assert summaries["0lt6LxEfzahYuKsc"]["opening_prompt"] == opening
    assert summaries["ZFgNUcNIKq1MWMz4"]["opening_prompt"].startswith("Read-only: read https://www.python.org/downloads/")


def test_a_session_that_finished_its_last_turn_is_not_busy(home: Path) -> None:
    assert aside.session_busy("0lt6LxEfzahYuKsc") is None


# --- what `aside exec` printed -------------------------------------------------------------------


def test_the_final_message_is_everything_after_the_last_tool_output() -> None:
    answer, urls = aside.parse_exec_output((RECORDED / "stdout.log").read_text(encoding="utf-8"))

    assert answer == ("The latest stable Python 3 release is **Python 3.14.8**, according to "
                      "[python.org](https://www.python.org/downloads/).")
    assert "https://www.python.org/downloads/" in urls
    assert not any("\x1b" in u for u in urls)


def test_with_no_tool_call_everything_printed_is_the_message() -> None:
    assert aside.parse_exec_output("첫 줄.\n\n둘째 문단.\x1b[0m\n") == ("첫 줄.\n\n둘째 문단.", [])


# --- the answer's tags ---------------------------------------------------------------------------


@pytest.mark.parametrize("tag", ['<quote ref="s1">', '<quote refs="s1">', '<quote source="s1">'])
def test_a_quote_becomes_its_text_and_the_url_its_id_names(tag: str) -> None:
    text = f"그는 {tag}“그렇다”</quote>고 했다. <quote>출처 없는 인용</quote>."

    assert aside.resolve_answer_tags(text, {"s1": "https://e.test/1"}) == "그는 “그렇다” (https://e.test/1)고 했다. 출처 없는 인용."


def test_a_quote_inside_a_citation_cites_once() -> None:
    text = '<citation refs="s1"><quote ref="s1">words</quote></citation> and <citation refs="s1"><quote ref="s2">more</quote></citation>'

    resolved = aside.resolve_answer_tags(text, {"s1": "https://e.test/1", "s2": "https://e.test/2"})

    assert resolved == "words (https://e.test/1) and more (https://e.test/2) (https://e.test/1)"


def test_a_citation_becomes_the_urls_its_ids_name() -> None:
    text = 'A <citation refs="s1,s2">claim</citation>, B <citation refs="nope">other</citation>.'

    resolved = aside.resolve_answer_tags(text, {"s1": "https://e.test/1", "s2": "https://e.test/2"})

    assert resolved == "A claim (https://e.test/1, https://e.test/2), B other."
