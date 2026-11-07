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
from conftest import answer, user, webfetch

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


# --- records as Aside writes them now -------------------------------------------------------------
#
# Shaped after records seen in real sessions (daemon 1.26.1101-1107): content as a list of text blocks, a webfetch result
# opened by its citation tag. None of these is a copy of one: the repository is public.


def jsonl(tmp_path: Path, *records: dict) -> Path:
    path = tmp_path / "messages.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def one(tmp_path: Path, record: dict) -> aside.Event:
    got = events(jsonl(tmp_path, record))
    assert len(got) == 1
    return got[0]


#: A Korean file name read as Latin-1 and written back as UTF-8: "년" becomes "ë\x85\x84", and \x85 is U+0085.
MOJIBAKE = "2026ë\x85\x84ë\x8f\x84 ê³µëª¨.pdf"


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"], ids=["NEL", "LS", "PS"])
def test_a_record_holding_a_unicode_line_separator_is_one_event(tmp_path: Path, separator: str) -> None:
    """Aside ends a record at "\\n" alone, and JSON leaves these three unescaped inside a string."""
    path = jsonl(tmp_path, user("q"),
                 webfetch("https://docs.test/a.pdf", f"\n\n공고{separator}안내서.pdf"),
                 answer("a"))

    got = events(path)

    assert [(e.kind, e.index) for e in got] == [("user", 0), ("tool_result", 1), ("assistant", 2)]
    assert [s.url for s in got[1].sources] == ["https://docs.test/a.pdf"]
    first = len(path.read_bytes().split(b"\n")[0]) + 1
    assert [(e.kind, e.index) for e in aside.read_events(path, first)[0]] == [("tool_result", 1), ("assistant", 2)]


@pytest.mark.parametrize("after_tag,opened", [
    ("\n\nThe page text.", True),
    ("\nHTTP 403 Forbidden\nAccess denied", False),
    ("\nHTTP 401 HTTP Forbidden\nPlease enable JS and disable any ad blocker", False),
    ("\nHTTP 404 Not Found", False),
    ("\nHTTP 503 Service Unavailable", False),
    ("\n\nHTTP 403 Forbidden is what this guide is about.", True),
    ("\n\nThe server answered HTTP 403 to robots.", True),
], ids=["page", "403", "401", "404", "503", "page-starting-with-a-status", "page-mentioning-a-status"])
def test_a_fetch_that_got_an_http_error_did_not_open_its_page(tmp_path: Path, after_tag: str, opened: bool) -> None:
    """Aside records an error status as a successful result whose text is the status line right after the tag; a page
    it read has a blank line there."""
    event = one(tmp_path, webfetch("https://e.test/a", after_tag))

    assert [s.opened for s in event.sources] == [opened]


@pytest.mark.parametrize("after_tag,saved_path", [
    ("\n\nDownloaded to: /s/tmp/D2603327.pdf\nMIME type: application/octet-stream\nFile size: 359165 bytes",
     "/s/tmp/D2603327.pdf"),
    (f"\n\nDownloaded to: /s/tmp/[붙임1] 'AX' {MOJIBAKE}\nMIME type: application/pdf\nFile size: 10 bytes",
     f"/s/tmp/[붙임1] 'AX' {MOJIBAKE}"),
    ("\n\nDownloaded to: /s/tmp/92379499007\nMIME type: application/octet-stream\nFile size: 12 bytes", "/s/tmp/92379499007"),
], ids=["pdf", "brackets-quote-mojibake", "no-extension"])
def test_a_fetch_that_downloaded_a_document_names_the_file_not_the_page(tmp_path: Path, after_tag: str,
                                                                       saved_path: str) -> None:
    source = one(tmp_path, webfetch("https://e.test/a.pdf", after_tag)).sources[0]

    assert (source.opened, source.holds_page, source.saved_path) == (True, False, saved_path)


@pytest.mark.parametrize("after_tag", [
    "\nHTTP 406 Not Acceptable\nDownloaded to: /s/tmp/92379499007\nMIME type: application/octet-stream\nFile size: 0 bytes",
    "\n\nDownloaded to: /s/tmp/empty.pdf\nMIME type: application/pdf\nFile size: 0 bytes",
], ids=["with-an-http-error", "empty"])
def test_a_download_that_holds_nothing_names_no_file(tmp_path: Path, after_tag: str) -> None:
    source = one(tmp_path, webfetch("https://e.test/a.pdf", after_tag)).sources[0]

    assert source.saved_path == ""


def test_a_result_too_large_to_keep_inline_names_the_file_that_holds_it(tmp_path: Path) -> None:
    pointer = ("[Output too large (91.5KB). Full output saved to: /s/tmp/webfetch-result-pZXA.txt — read it with "
               "read_file({ path, offset: 1 }), 36.0KB per read.]\n\nPreview (first 4.0KB):\n"
               '<webfetch-citation source_id="src1" />\n\nNews Summary')
    record = {**webfetch("https://e.test/a", ""), "content": [{"type": "text", "text": pointer}]}

    source = one(tmp_path, record).sources[0]

    assert (source.opened, source.holds_page, source.saved_path) == (True, True, "/s/tmp/webfetch-result-pZXA.txt")


def test_the_earlier_too_large_notice_names_its_file_too(tmp_path: Path) -> None:
    """Recorded on 2026-08-29: the path closes the bracket, with no reading hint after it."""
    pointer = ("[Output too large (193.2KB). Full output saved to: /s/tmp/webfetch-result-Bop6.txt]\n\n"
               'Preview (first 4.0KB):\n<webfetch-citation source_id="src1" />\n\nText')
    record = {**webfetch("https://e.test/a", ""), "content": [{"type": "text", "text": pointer}]}

    assert one(tmp_path, record).sources[0].saved_path == "/s/tmp/webfetch-result-Bop6.txt"


def test_a_refusal_too_large_to_keep_inline_is_still_a_refusal(tmp_path: Path) -> None:
    """A bot check's page can be large enough that Aside keeps it in a file; its preview still opens with the status."""
    pointer = ("[Output too large (52.0KB). Full output saved to: /s/tmp/webfetch-result-C1.txt — read it with "
               "read_file({ path, offset: 1 }), 36.0KB per read.]\n\nPreview (first 4.0KB):\n"
               '<webfetch-citation source_id="src1" />\nHTTP 403 Forbidden\n<html>challenge')
    record = {**webfetch("https://e.test/a", ""), "content": [{"type": "text", "text": pointer}]}

    assert [(s.opened, s.saved_path) for s in one(tmp_path, record).sources] == [(False, "")]


def test_a_result_of_text_blocks_reads_as_its_text(tmp_path: Path) -> None:
    record = {**webfetch("https://e.test/a", ""), "content": [{"type": "text", "text": "one"}, {"type": "text", "text": "two"}]}
    mixed = {**record, "content": [{"type": "text", "text": "one"}, {"type": "image", "data": "AAAA"}]}

    assert one(tmp_path, record).content == "one\ntwo"
    assert json.loads(one(tmp_path, mixed).content) == mixed["content"], "a block that is not text is kept, as JSON"


def test_a_message_that_stopped_on_an_error_carries_the_error(tmp_path: Path) -> None:
    record = {"role": "assistant", "content": [], "stopReason": "error", "timestamp": 1,
              "errorMessage": 'aside API error (402): 402 "Insufficient credits"'}

    event = one(tmp_path, record)

    assert (event.stop, event.error) == ("error", 'aside API error (402): 402 "Insufficient credits"')


@pytest.mark.parametrize("record", [
    {"role": "user-message-metadata", "attachments": [{"id": "tab:1", "type": "tab", "url": "https://e.test/"}]},
    {"role": "compaction", "summary": "earlier turns, summarised"},
], ids=["attachments", "compaction"])
def test_records_about_the_conversation_are_read_as_such(tmp_path: Path, record: dict) -> None:
    assert one(tmp_path, record).kind == "meta"


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


# --- the files the agent saved -------------------------------------------------------------------

PARENT_ID = "0lt6LxEfzahYuKsc"
SAVED = ("KSOI_20260916.pdf", "같은 죽음 다른 결론.pptx", "개인정보 영향평가 수행안내서(2025.10_12월수정).pdf", "tmp/bohun_rfp.hwpx")


@pytest.fixture
def saved(home: Path) -> Path:
    """A session's `artifacts/` as the daemon leaves it -- names with spaces, parentheses and Korean, a subfolder -- plus links a careless copy would follow out of it."""
    folder = home / f"2026-10-02_{PARENT_ID}" / "artifacts"
    (folder / "tmp").mkdir(parents=True)
    for rel in SAVED:
        (folder / rel).write_bytes(rel.encode())
    outside = home.parent / "elsewhere"
    outside.mkdir()
    (outside / "secret.txt").write_text("not the agent's")
    (folder / "linked.txt").symlink_to(outside / "secret.txt")
    (folder / "linked-folder").symlink_to(outside)
    (folder / "inside-link.pdf").symlink_to(folder / "KSOI_20260916.pdf")
    return folder


def test_the_saved_files_are_listed_at_any_depth_and_links_are_not(saved: Path) -> None:
    listed = aside.session_artifacts(PARENT_ID)

    assert [rel for rel, _, _ in listed] == sorted(SAVED)
    assert all(path == saved / rel and mtime == path.stat().st_mtime for rel, path, mtime in listed)
    assert aside.session_artifacts("ZFgNUcNIKq1MWMz4") == [], "a session that saved nothing"
    assert aside.session_artifacts("NoSuchSession01") == []


def test_every_way_an_answer_names_a_saved_file_points_at_its_copy(saved: Path) -> None:
    """The forms are the ones real answers used: a link or an image relative to the session, and the session's absolute path behind `sandbox:` with its spaces encoded."""
    copies = {rel: f"/runs/r/artifacts/{rel}" for rel in SAVED}
    text = (f"[다운로드한 원문 PDF](artifacts/KSOI_20260916.pdf) · ![받은 파일](artifacts/tmp/bohun_rfp.hwpx)\n"
            f"[PPTX 파일 받기](sandbox:{saved}/같은%20죽음%20다른%20결론.pptx)\n"
            f"{saved}/개인정보 영향평가 수행안내서(2025.10_12월수정).pdf, 그리고 원문은 artifacts/KSOI_20260916.pdf.")

    got = aside.rewrite_artifact_refs(text, PARENT_ID, copies)

    assert got == ("[다운로드한 원문 PDF](/runs/r/artifacts/KSOI_20260916.pdf) · ![받은 파일](/runs/r/artifacts/tmp/bohun_rfp.hwpx)\n"
                   "[PPTX 파일 받기](/runs/r/artifacts/같은 죽음 다른 결론.pptx)\n"
                   "/runs/r/artifacts/개인정보 영향평가 수행안내서(2025.10_12월수정).pdf, 그리고 원문은 /runs/r/artifacts/KSOI_20260916.pdf.")
    assert aside.referenced_artifacts(text, PARENT_ID, list(SAVED)) == list(SAVED)


def test_a_name_that_only_looks_like_a_saved_file_is_left_alone(saved: Path) -> None:
    """Another session's file, a longer name, a path inside a URL, and a file this session did not save are not this file."""
    text = ("/Users/x/.aside/u/0/sessions/2026-10-01_SomeOtherSession/artifacts/KSOI_20260916.pdf, "
            "artifacts/KSOI_20260916.pdf.bak, artifacts/KSOI_20260916.pdf%20backup, myartifacts/KSOI_20260916.pdf, "
            "https://x.test/?file=artifacts/KSOI_20260916.pdf, artifacts/unknown.pdf")

    assert aside.rewrite_artifact_refs(text, PARENT_ID, {"KSOI_20260916.pdf": "/copy.pdf"}) == text
    assert aside.referenced_artifacts(text, PARENT_ID, ["KSOI_20260916.pdf"]) == []


def test_another_sessions_answer_names_a_file_only_by_its_absolute_path(saved: Path) -> None:
    """A relative `artifacts/` path means the folder of the session that wrote it, so read from another session's answer only the absolute form names this session's file."""
    text = f"[부모가 받은 것](artifacts/KSOI_20260916.pdf) [자식이 받은 것]({saved}/tmp/bohun_rfp.hwpx)"
    copies = {"KSOI_20260916.pdf": "/copy/a.pdf", "tmp/bohun_rfp.hwpx": "/copy/b.hwpx"}

    assert aside.rewrite_artifact_refs(text, PARENT_ID, copies, absolute_only=True) == \
        "[부모가 받은 것](artifacts/KSOI_20260916.pdf) [자식이 받은 것](/copy/b.hwpx)"
    assert aside.referenced_artifacts(text, PARENT_ID, list(copies), absolute_only=True) == ["tmp/bohun_rfp.hwpx"]


def test_a_linked_artifacts_folder_is_not_read(home: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "secret.txt").write_text("not the agent's")
    (home / f"2026-10-02_{PARENT_ID}" / "artifacts").symlink_to(elsewhere)

    assert aside.session_artifacts(PARENT_ID) == []


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
