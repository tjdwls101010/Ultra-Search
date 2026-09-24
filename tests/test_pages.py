"""`fetch`, `map` and `crawl`, end to end through the CLI against the fake browser.

The seam is argv in, one JSON line, files on disk and an exit code out. The browser is the
one external boundary and is replaced by the fake aside's snippet routes (see
tests/fake_aside/aside); the markdown converter is the real one. The HTML fixtures are real
captures, so the thresholds are checked against pages that exist:

    tests/fixtures/html/article.html          4355 words  (Wikipedia)
    tests/fixtures/html/docs_page_html.html    388 words  (docs.aside.com)
    tests/fixtures/html/news_ko.html           219 words  (Korean news front page)
    tests/fixtures/html/challenge.html          24 words  (Cloudflare interstitial)
    tests/fixtures/html/js_shell.html            0 words  (x.com, renders client-side)

Reporting a blocked or empty page as a successful read is the failure that matters most
here: it removes a source from an investigation without anyone noticing it left.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES, SCRIPTS, repl_calls

ARTICLE = "<html><head><title>제목</title></head><body><article><p>" + ("단어 " * 300) + "</p></article></body></html>"
SHELL = "<html><head><title>shell</title></head><body><div id=root></div></body></html>"


def page(body: str, ct: str = "text/html", status: int = 200) -> dict:
    return {"status": status, "content_type": ct, "kind": "text", "text": body}


def captured(name: str) -> str:
    return (FIXTURES / "html" / f"{name}.html").read_text(encoding="utf-8")


def document(name: str, ct: str = "application/pdf") -> dict:
    """What fetch_batch reports for a binary response: saved to disk, path handed back."""
    path = FIXTURES / "docs" / name
    return {"status": 200, "content_type": ct, "kind": "file", "saved_path": str(path), "ext": path.suffix.lstrip(".")}


def item_of(payload: dict) -> dict:
    return payload["items"][0]


def saved(item: dict) -> str:
    return Path(item["path"]).read_text(encoding="utf-8")


def frontmatter(text: str) -> list[str]:
    assert text.startswith("---\n")
    return text.split("---\n")[1].splitlines()


# --- reading a page ----------------------------------------------------------------------


def test_a_page_is_saved_as_markdown_and_reported(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    code, payload, _ = cli("fetch", "https://example.org/a", "--out", str(tmp_path / "out"))

    assert code == 0
    item = item_of(payload)
    assert item["status"] == "ok"
    assert item["via"] == "fetch"
    assert Path(item["path"]).suffix == ".md"
    assert "단어" in saved(item)


def test_saved_pages_default_to_the_registry_beside_the_runs(cli, routes, runs_dir: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    _, payload, _ = cli("fetch", "https://example.org/a")

    assert Path(item_of(payload)["path"]).parent == runs_dir / "pages"


def test_the_full_text_goes_to_a_file_not_into_the_reply(cli, routes) -> None:
    """A fetch of ten pages would otherwise put ten pages into the caller's context as a
    side effect of asking where they are."""
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    _, payload, _ = cli("fetch", "https://example.org/a")

    assert "content" not in item_of(payload)
    assert item_of(payload)["words"] > 100


def test_print_includes_the_content_but_caps_it(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    _, payload, _ = cli("fetch", "https://example.org/a", "--print", "--max-chars", "50")

    item = item_of(payload)
    assert len(item["content"]) == 50
    assert item["truncated"] is True
    assert saved(item).startswith(item["content"]), "--print shows the same bytes the file holds"


def test_an_article_extracts_to_markdown(cli, routes) -> None:
    url = "https://en.wikipedia.org/wiki/Web_scraping"
    routes({"fetch_batch": {url: page(captured("article"))}})

    _, payload, _ = cli("fetch", url)

    item = item_of(payload)
    assert item["status"] == "ok"
    assert item["words"] > 1000
    assert item["title"] == "Web scraping"
    assert "scraping" in saved(item).lower()


def test_a_korean_page_is_not_mistaken_for_an_empty_one(cli, routes, fake_aside: Path) -> None:
    """Counting whitespace-delimited tokens undercounts CJK badly enough that a real Korean
    page can fall under an English-calibrated threshold and be escalated for no reason."""
    routes({"fetch_batch": {"https://www.yna.co.kr/": page(captured("news_ko"))}})

    _, payload, _ = cli("fetch", "https://www.yna.co.kr/")

    assert item_of(payload)["status"] == "ok"
    assert item_of(payload)["words"] >= 100
    assert repl_calls(fake_aside, "tab_one") == []


# --- what a response really is -----------------------------------------------------------


def test_a_blocked_response_is_never_saved_as_the_page(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/x": page("<html><body>nope</body></html>", status=403)}})
    out = tmp_path / "out"

    code, payload, _ = cli("fetch", "https://example.org/x", "--via", "fetch", "--out", str(out))

    item = item_of(payload)
    assert code == 4
    assert item["status"] == "blocked"
    assert item["http_status"] == 403
    assert item["path"] is None
    assert list(out.glob("*")) == []


def test_a_client_rendered_page_is_recognised_as_a_shell(cli, routes) -> None:
    """x.com is the case that distinguishes the two. It extracts to nothing AND it is served
    through Cloudflare, whose passive bot-detection script sits in every one of its ordinary
    pages -- so a challenge check keyed on that script would call this a block and never
    escalate it. Escalating a shell works; giving up on a block does not."""
    routes({"fetch_batch": {"https://x.com/elonmusk": page(captured("js_shell"))}})

    _, payload, _ = cli("fetch", "https://x.com/elonmusk", "--via", "fetch")

    assert item_of(payload)["status"] == "shell"
    assert item_of(payload)["words"] < 80
    assert item_of(payload)["path"] is None


def test_a_cloudflare_fronted_article_is_not_called_blocked(cli, routes) -> None:
    body = captured("article").replace(
        "</body>", '<script src="/cdn-cgi/challenge-platform/scripts/jsd/api.js"></script></body>'
    )
    routes({"fetch_batch": {"https://en.wikipedia.org/wiki/Web_scraping": page(body)}})

    _, payload, _ = cli("fetch", "https://en.wikipedia.org/wiki/Web_scraping", "--via", "fetch")

    assert item_of(payload)["status"] == "ok"


def test_a_bot_challenge_is_not_reported_as_the_page(cli, routes) -> None:
    """A challenge page is a successful HTTP response with a body. Saving it as the article
    is how a source silently drops out of an investigation."""
    routes({"fetch_batch": {"https://example.com/": page(captured("challenge"))}})

    code, payload, _ = cli("fetch", "https://example.com/", "--via", "fetch")

    assert code == 4
    assert item_of(payload)["status"] == "challenge"
    assert item_of(payload)["path"] is None


def test_a_challenge_is_detected_even_when_it_is_wordy(cli, routes) -> None:
    body = captured("challenge").replace("</body>", "<p>" + ("filler word " * 200) + "</p></body>")
    routes({"fetch_batch": {"https://example.com/": page(body)}})

    _, payload, _ = cli("fetch", "https://example.com/", "--via", "fetch")

    assert item_of(payload)["status"] == "challenge"


def test_markdown_served_as_markdown_is_passed_through(cli, routes) -> None:
    """docs.aside.com serves text/markdown for its .md URLs. Running that through an HTML
    article extractor yields nothing -- measured, 0 words -- so it must not go there."""
    url = "https://docs.aside.com/help/developers.md"
    routes({"fetch_batch": {url: page("# Title\n\nBody text here.\n", ct="text/markdown; charset=utf-8")}})

    _, payload, _ = cli("fetch", url)

    item = item_of(payload)
    assert item["status"] == "ok"
    assert item["title"] == "Title"
    assert saved(item).split("---\n", 2)[2].lstrip().startswith("# Title\n\nBody text here.")


def test_plain_text_is_passed_through(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/notes.txt": page("just some text", ct="text/plain")}})

    _, payload, _ = cli("fetch", "https://example.org/notes.txt")

    assert item_of(payload)["status"] == "ok"
    assert "just some text" in saved(item_of(payload))


# --- escalating to a real tab ------------------------------------------------------------


def test_a_shell_is_escalated_to_a_browser_tab(cli, routes, fake_aside: Path) -> None:
    routes({
        "fetch_batch": {"https://x.com/a": page(SHELL)},
        "tab_one": {"https://x.com/a": page(ARTICLE)},
    })

    _, payload, _ = cli("fetch", "https://x.com/a")

    assert [c["url"] for c in repl_calls(fake_aside, "tab_one")] == ["https://x.com/a"]
    item = item_of(payload)
    assert item["status"] == "ok"
    assert item["via"] == "tab"


def test_frontmatter_records_where_the_text_came_from(cli, routes) -> None:
    routes({
        "fetch_batch": {"https://x.com/a": page(SHELL)},
        "tab_one": {"https://x.com/a": page(ARTICLE)},
    })

    _, payload, _ = cli("fetch", "https://x.com/a")

    text = saved(item_of(payload))
    header = frontmatter(text)
    assert 'url: "https://x.com/a"' in header
    assert "via: tab" in header
    assert text.rstrip().endswith("단어")


def test_escalation_is_skipped_when_the_caller_forced_plain_fetch(cli, routes, fake_aside: Path) -> None:
    routes({"fetch_batch": {"https://x.com/a": page(SHELL)}, "tab_one": {"https://x.com/a": page(ARTICLE)}})

    _, payload, _ = cli("fetch", "https://x.com/a", "--via", "fetch")

    assert repl_calls(fake_aside, "tab_one") == []
    assert item_of(payload)["status"] == "shell"
    assert item_of(payload)["path"] is None


def test_a_page_that_is_still_a_shell_after_the_tab_says_so(cli, routes) -> None:
    routes({"fetch_batch": {"https://x.com/a": page(SHELL)}, "tab_one": {"https://x.com/a": page(SHELL)}})

    _, payload, _ = cli("fetch", "https://x.com/a")

    assert item_of(payload)["status"] == "shell_escalated"


# --- the batch failure mode this whole shape exists for ----------------------------------


def test_one_slow_url_does_not_lose_the_rest_of_its_batch(cli, routes, tmp_path: Path) -> None:
    """The 120s REPL limit applies to the whole snippet. If a batch were all-or-nothing, a
    single hanging navigation would discard seven finished pages along with it."""
    urls = [f"https://example.org/p{i}" for i in range(8)]
    table = {u: page(ARTICLE) for u in urls}
    table[urls[3]] = {"status": 0, "kind": "error", "error": "timeout"}
    routes({"fetch_batch": table})
    out = tmp_path / "out"

    code, payload, _ = cli("fetch", *urls, "--out", str(out))

    assert code == 0
    assert [i["url"] for i in payload["items"] if i["status"] == "ok"] == urls[:3] + urls[4:]
    assert len(list(out.glob("*.md"))) == 7
    assert [i["url"] for i in payload["items"] if i["status"] == "error"] == [urls[3]]


def test_a_timed_out_url_is_retried_on_its_own(cli, routes, fake_aside: Path) -> None:
    """Retried alone rather than in the batch it failed in: whatever made it slow gets the
    full per-URL budget instead of a share of one it already exhausted."""
    urls = [f"https://example.org/p{i}" for i in range(4)]
    table = {u: page(ARTICLE) for u in urls}
    table[urls[2]] = {"sequence": [{"status": 0, "kind": "error", "error": "timeout"}, page(ARTICLE)]}
    routes({"fetch_batch": table})

    _, payload, _ = cli("fetch", *urls)

    assert all(i["status"] == "ok" for i in payload["items"])
    assert [c["urls"] for c in repl_calls(fake_aside, "fetch_batch")] == [urls, [urls[2]]]


def test_an_http_error_is_not_retried(cli, routes, fake_aside: Path) -> None:
    """A 404 is an answer, not a transient failure; asking again only costs a round trip."""
    routes({"fetch_batch": {}})

    _, payload, _ = cli("fetch", "https://example.org/missing", "--via", "fetch")

    assert item_of(payload)["status"] == "blocked"
    assert item_of(payload)["http_status"] == 404
    assert len(repl_calls(fake_aside, "fetch_batch")) == 1


def test_urls_are_split_into_batches_of_the_requested_size(cli, routes, fake_aside: Path) -> None:
    urls = [f"https://example.org/p{i}" for i in range(10)]
    routes({"fetch_batch": {u: page(ARTICLE) for u in urls}})

    cli("fetch", *urls, "--concurrency", "4")

    assert [len(c["urls"]) for c in repl_calls(fake_aside, "fetch_batch")] == [4, 4, 2]


# --- documents ---------------------------------------------------------------------------


def test_a_pdf_is_converted_from_the_file_the_browser_saved(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/paper.pdf": document("sample_en.pdf")}})

    _, payload, _ = cli("fetch", "https://example.org/paper.pdf")

    assert item_of(payload)["status"] == "ok"
    assert "Example Domain" in saved(item_of(payload))


def test_the_original_document_is_kept_beside_the_markdown(cli, routes) -> None:
    """The conversion is lossy and the download cost a round trip; keeping the original
    means a better converter later does not need the network again."""
    routes({"fetch_batch": {"https://example.org/paper.pdf": document("sample_en.pdf")}})

    _, payload, _ = cli("fetch", "https://example.org/paper.pdf")

    original = Path(item_of(payload)["original_path"])
    assert original.read_bytes() == (FIXTURES / "docs" / "sample_en.pdf").read_bytes()
    assert original.parent == Path(item_of(payload)["path"]).parent


def test_a_korean_pdf_keeps_its_text(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/ko.pdf": document("sample_ko.pdf")}})

    _, payload, _ = cli("fetch", "https://example.org/ko.pdf")

    assert item_of(payload)["status"] == "ok"
    assert any("가" <= ch <= "힯" for ch in saved(item_of(payload)))


def test_a_file_that_is_not_the_document_it_claims_is_reported_not_guessed(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/fake.pdf": document("not_really.pdf")}})

    _, payload, _ = cli("fetch", "https://example.org/fake.pdf")

    assert item_of(payload)["status"] == "unsupported"
    assert "html" in item_of(payload)["error"].lower()


def test_a_scanned_pdf_asks_for_ocr_rather_than_returning_nothing(cli, routes) -> None:
    """A PDF with no text layer. Sending it for hosted OCR would ship the user's document to
    a third party, so the honest answer is that it needs a step nobody has authorised."""
    routes({"fetch_batch": {"https://example.org/scan.pdf": document("scanned.pdf")}})

    code, payload, _ = cli("fetch", "https://example.org/scan.pdf")

    assert code == 4
    assert item_of(payload)["status"] == "needs_ocr"
    assert item_of(payload)["path"] is None


# --- output destinations and names -------------------------------------------------------


def test_a_named_markdown_file_is_a_file(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})
    target = tmp_path / "answer.md"

    _, payload, _ = cli("fetch", "https://example.org/a", "--out", str(target))

    assert Path(item_of(payload)["path"]) == target
    assert target.is_file()


def test_an_extensionless_out_path_is_a_directory(cli, routes, tmp_path: Path) -> None:
    """`--out ./notes` for one URL means a folder to anyone who types it. Producing an
    extensionless file called `notes` instead is a surprise nobody checks for."""
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})
    target = tmp_path / "notes"

    _, payload, _ = cli("fetch", "https://example.org/a", "--out", str(target))

    assert target.is_dir()
    assert Path(item_of(payload)["path"]).parent == target


def test_a_trailing_slash_is_a_directory_even_with_a_dot_in_the_name(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})
    target = tmp_path / "v1.2"

    _, payload, _ = cli("fetch", "https://example.org/a", "--out", str(target) + "/")

    assert target.is_dir()
    assert Path(item_of(payload)["path"]).parent == target


def test_several_urls_are_refused_a_single_output_file(cli, routes, fake_aside: Path, tmp_path: Path) -> None:
    routes({"fetch_batch": {}})

    code, payload, _ = cli("fetch", "https://example.org/a", "https://example.org/b", "--out", str(tmp_path / "one.md"))

    assert code == 2
    assert payload["error"] == "bad_arguments"
    assert "file" in payload["message"]
    assert repl_calls(fake_aside, "fetch_batch") == [], "refused before any work"


def test_two_urls_that_slug_the_same_do_not_overwrite_each_other(cli, routes) -> None:
    urls = ["https://example.org/a/b", "https://example.org/a-b"]
    routes({"fetch_batch": {u: page(ARTICLE) for u in urls}})

    _, payload, _ = cli("fetch", *urls)

    paths = [Path(i["path"]) for i in payload["items"]]
    assert len(set(paths)) == 2
    assert all(p.exists() for p in paths)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://docs.aside.com/help/developers", "docs.aside.com-help-developers.md"),
        ("https://example.org/", "example.org.md"),
        ("https://example.org/a/b/?q=1", "example.org-a-b.md"),
    ],
)
def test_file_names_are_readable_and_stable(cli, routes, url: str, expected: str) -> None:
    routes({"fetch_batch": {url: page(ARTICLE)}})

    _, payload, _ = cli("fetch", url)

    assert Path(item_of(payload)["path"]).name == expected


def test_file_names_stay_within_a_sane_length(cli, routes) -> None:
    url = "https://example.org/" + "segment/" * 60
    routes({"fetch_batch": {url: page(ARTICLE)}})

    _, payload, _ = cli("fetch", url)

    assert len(Path(item_of(payload)["path"]).stem) <= 120


# --- frontmatter -------------------------------------------------------------------------


def test_frontmatter_can_be_left_off_without_touching_the_body(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    _, with_header, _ = cli("fetch", "https://example.org/a", "--out", str(tmp_path / "with"))
    _, bare, _ = cli("fetch", "https://example.org/a", "--no-frontmatter", "--out", str(tmp_path / "bare"))

    headed = saved(item_of(with_header))
    body = headed.split("---\n", 2)[2].lstrip("\n")
    assert saved(item_of(bare)) == body
    assert body.startswith("단어")


def test_a_title_with_quotes_does_not_break_the_frontmatter(cli, routes) -> None:
    body = ARTICLE.replace("<title>제목</title>", '<title>He said "hi"\nand left</title>')
    routes({"fetch_batch": {"https://example.org/q": page(body)}})

    _, payload, _ = cli("fetch", "https://example.org/q")

    header = frontmatter(saved(item_of(payload)))
    title = [line for line in header if line.startswith("title:")]
    assert len(title) == 1
    assert '\\"hi\\"' in title[0]
    assert all(line.split(":", 1)[0].isidentifier() for line in header), header


# --- --format html -----------------------------------------------------------------------


def test_format_html_writes_the_original_html(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})

    _, payload, _ = cli("fetch", "https://example.org/a", "--format", "html")

    item = item_of(payload)
    assert item["status"] == "ok"
    assert Path(item["path"]).suffix == ".html"
    assert saved(item) == ARTICLE


def test_format_html_is_refused_for_a_response_that_was_not_html(cli, routes, tmp_path: Path) -> None:
    """A .html file containing markdown is a file whose contents contradict its name --
    worse than a refusal, because nothing downstream notices."""
    routes({"fetch_batch": {"https://example.org/paper.pdf": document("sample_en.pdf")}})
    out = tmp_path / "out"

    _, payload, _ = cli("fetch", "https://example.org/paper.pdf", "--format", "html", "--out", str(out))

    assert item_of(payload)["status"] == "unsupported"
    assert item_of(payload)["path"] is None
    assert list(out.glob("*.html")) == []


def test_format_html_saves_a_client_rendered_page_that_has_no_article(cli, routes) -> None:
    """`--format html` asked for the document, not the article. Gating the save on article
    extraction refuses exactly the pages someone reaches for raw HTML to inspect."""
    routes({"fetch_batch": {"https://x.com/a": page(SHELL)}})

    _, payload, _ = cli("fetch", "https://x.com/a", "--format", "html", "--via", "fetch")

    assert item_of(payload)["path"] is not None
    assert saved(item_of(payload)) == SHELL


def test_format_html_still_refuses_to_save_a_bot_challenge(cli, routes, tmp_path: Path) -> None:
    """The one thing that stays refused in every format: a challenge saved as the page looks
    like a source that was read."""
    routes({"fetch_batch": {"https://example.org/c": page(captured("challenge"))}})
    out = tmp_path / "out"

    _, payload, _ = cli("fetch", "https://example.org/c", "--format", "html", "--via", "fetch", "--out", str(out))

    assert item_of(payload)["status"] == "challenge"
    assert item_of(payload)["path"] is None
    assert list(out.glob("*.html")) == []


# --- without the converter ---------------------------------------------------------------


def fetch_without_node(tmp_path: Path, routes_file: Path, runs_dir: Path, url: str) -> dict:
    """The CLI on a machine where `node` is not on PATH -- nothing else changed."""
    bin_dir = tmp_path / "bin-without-node"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    env = dict(os.environ, PATH=str(bin_dir), FAKE_ASIDE_REPL_ROUTES=str(routes_file))
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "cli.py"), "fetch", url, "--via", "fetch", "--runs-dir", str(runs_dir)],
        capture_output=True, text=True, env=env, timeout=60,
    )
    return json.loads(p.stdout.splitlines()[-1])


def test_a_challenge_is_recognised_without_running_the_converter(
    cli, routes, tmp_path: Path, runs_dir: Path
) -> None:
    """The decisive markers are read off the raw body, before conversion. An interstitial that
    arrives when node is missing would otherwise come back as an extraction error -- and an
    error is not escalated to a browser tab, which is the one thing that clears a challenge."""
    routes({"fetch_batch": {"https://example.com/": page(captured("challenge"))}})

    payload = fetch_without_node(tmp_path, Path(os.environ["FAKE_ASIDE_REPL_ROUTES"]), runs_dir, "https://example.com/")

    assert item_of(payload)["status"] == "challenge"


def test_a_normal_page_without_the_converter_is_an_error_not_a_challenge(
    cli, routes, tmp_path: Path, runs_dir: Path
) -> None:
    url = "https://en.wikipedia.org/wiki/Web_scraping"
    routes({"fetch_batch": {url: page(captured("article"))}})

    payload = fetch_without_node(tmp_path, Path(os.environ["FAKE_ASIDE_REPL_ROUTES"]), runs_dir, url)

    assert item_of(payload)["status"] == "error"
    assert "node" in item_of(payload)["error"]


# --- map: choosing which URLs a crawl will visit -----------------------------------------

SITE = {
    "https://site.test/": ["/a", "https://site.test/b", "https://other.test/x", "mailto:x@site.test"],
    "https://site.test/a": ["/a/1", "a/2", "https://site.test/#top"],
    "https://site.test/b": ["https://site.test/b/1"],
    "https://site.test/a/1": ["https://site.test/a/1/deep"],
    "https://site.test/a/2": [],
    "https://site.test/b/1": [],
    "https://site.test/a/1/deep": [],
}


def mapped(cli, *args: str) -> list[str]:
    code, payload, _ = cli("map", "https://site.test/", *args)
    assert code == 0, payload
    return payload["urls"]


def test_depth_one_visits_only_the_root_and_its_links(cli, routes) -> None:
    routes({"links": SITE})

    assert set(mapped(cli, "--depth", "1")) == {"https://site.test/", "https://site.test/a", "https://site.test/b"}


def test_depth_two_reaches_one_level_further(cli, routes) -> None:
    routes({"links": SITE})

    urls = mapped(cli, "--depth", "2")

    assert "https://site.test/a/1" in urls
    assert "https://site.test/a/2" in urls, "a relative href resolves against the page it is on"
    assert "https://site.test/a/1/deep" not in urls


def test_offsite_links_are_not_followed(cli, routes) -> None:
    routes({"links": SITE})

    assert not any("other.test" in u or u.startswith("mailto:") for u in mapped(cli, "--depth", "3"))


def test_a_cycle_does_not_revisit(cli, routes) -> None:
    """site.test/a links back to the root through a fragment."""
    routes({"links": SITE})

    urls = mapped(cli, "--depth", "3")

    assert len(urls) == len(set(urls)) == 7


def test_the_cap_is_respected(cli, routes) -> None:
    routes({"links": SITE})

    urls = mapped(cli, "--depth", "3", "--max-urls", "3")

    assert len(urls) == 3
    assert urls[0] == "https://site.test/"


def test_include_globs_keep_only_matches(cli, routes) -> None:
    routes({"links": SITE})

    urls = mapped(cli, "--depth", "3", "--include", "*/a/*")

    assert set(urls) == {"https://site.test/a/1", "https://site.test/a/2", "https://site.test/a/1/deep"}


def test_exclude_globs_drop_matches(cli, routes) -> None:
    routes({"links": SITE})

    assert not any("/b" in u for u in mapped(cli, "--depth", "2", "--exclude", "*/b*"))


def test_a_filtered_out_page_is_still_walked_through(cli, routes) -> None:
    """A glob says which pages to keep, not which to route through. Docs sites routinely hang
    every article off an index that the glob itself would exclude."""
    routes({"links": SITE})

    assert mapped(cli, "--depth", "3", "--include", "*/a/1/*") == ["https://site.test/a/1/deep"]


def test_a_sitemap_short_circuits_link_following(cli, routes, fake_aside: Path) -> None:
    routes({
        "sitemap": {"https://site.test/sitemap.xml": ["https://site.test/from-sitemap-1", "https://site.test/from-sitemap-2"]},
        "links": SITE,
    })

    urls = mapped(cli, "--depth", "2")

    assert urls == ["https://site.test/from-sitemap-1", "https://site.test/from-sitemap-2"]
    assert repl_calls(fake_aside, "links") == [], "a sitemap is the site's own list; walking anyway doubles the cost"


def test_sitemap_urls_are_still_filtered(cli, routes) -> None:
    routes({"sitemap": {"https://site.test/sitemap.xml": ["https://site.test/docs/x", "https://site.test/blog/y"]}})

    assert mapped(cli, "--include", "*/docs/*") == ["https://site.test/docs/x"]


def test_sitemap_candidates_cover_the_usual_locations(cli, routes, fake_aside: Path) -> None:
    routes({"links": SITE})

    cli("map", "https://site.test/docs/guide", "--depth", "1")

    (asked,) = repl_calls(fake_aside, "sitemap")
    assert "https://site.test/sitemap.xml" in asked["roots"]
    assert "https://site.test/robots.txt" in asked["roots"]


def test_no_sitemap_follows_links_only(cli, routes, fake_aside: Path) -> None:
    routes({"sitemap": {"https://site.test/sitemap.xml": ["https://site.test/from-sitemap"]}, "links": SITE})

    urls = mapped(cli, "--depth", "1", "--no-sitemap")

    assert repl_calls(fake_aside, "sitemap") == []
    assert "https://site.test/from-sitemap" not in urls


# --- crawl ------------------------------------------------------------------------------


def test_a_map_manifest_is_crawled_without_discovering_again(cli, routes, fake_aside: Path, tmp_path: Path) -> None:
    """`map` looks, `crawl --from` fetches what it saw -- the site is walked once."""
    routes({"links": SITE, "fetch_batch": {u: page(ARTICLE) for u in SITE}})
    manifest = tmp_path / "map.json"
    cli("map", "https://site.test/", "--depth", "1", "--out", str(manifest))
    walked = len(repl_calls(fake_aside, "links"))

    code, payload, _ = cli("crawl", "--from", str(manifest), "--out", str(tmp_path / "site"))

    assert code == 0
    assert json.loads(manifest.read_text())["urls"] == ["https://site.test/", "https://site.test/a", "https://site.test/b"]
    assert len(repl_calls(fake_aside, "links")) == walked
    assert [i["url"] for i in payload["items"]] == ["https://site.test/", "https://site.test/a", "https://site.test/b"]
    assert payload["saved"] == 3


def test_a_crawl_writes_numbered_pages_and_a_manifest_that_crawls_again(cli, routes, tmp_path: Path) -> None:
    routes({"links": SITE, "fetch_batch": {u: page(ARTICLE) for u in SITE}})
    out = tmp_path / "site"

    _, payload, _ = cli("crawl", "https://site.test/", "--depth", "1", "--out", str(out))

    manifest = json.loads(Path(payload["manifest"]).read_text())
    assert manifest["root"] == "https://site.test/"
    assert [p["url"] for p in manifest["pages"]] == [i["url"] for i in payload["items"]]
    assert sorted(p.name[:4] for p in out.glob("*.md")) == ["000-", "001-", "002-"]
    code, again, _ = cli("crawl", "--from", payload["manifest"], "--out", str(tmp_path / "again"))
    assert code == 0
    assert [i["url"] for i in again["items"]] == [p["url"] for p in manifest["pages"]]


def test_max_pages_caps_what_a_crawl_fetches(cli, routes, fake_aside: Path) -> None:
    routes({"links": SITE, "fetch_batch": {u: page(ARTICLE) for u in SITE}})

    _, payload, _ = cli("crawl", "https://site.test/", "--depth", "3", "--max-pages", "2")

    assert payload["requested"] == 2
    assert sum(len(c["urls"]) for c in repl_calls(fake_aside, "fetch_batch")) == 2


@pytest.mark.parametrize("manifest", [[], {"pages": ["https://site.test/a"]}, {"urls": "https://site.test/a"},
                                      {"root": 123, "urls": ["https://site.test/a"]}])
def test_a_manifest_of_the_wrong_shape_is_refused(cli, routes, tmp_path: Path, manifest) -> None:
    routes({})
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    code, err, _ = cli("crawl", "--from", str(path))

    assert code == 2
    assert err["error"] == "bad_arguments"
    assert "map" in err["fix"]


def test_an_unwritable_destination_is_reported_in_json(cli, routes, tmp_path: Path) -> None:
    routes({"fetch_batch": {"https://example.org/a": page(ARTICLE)}})
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        code, err, _ = cli("fetch", "https://example.org/a", "--out", str(locked / "sub"))
    finally:
        os.chmod(locked, 0o700)

    assert code == 4
    assert err["ok"] is False and err["error"] == "run_failed"
    assert str(locked / "sub") in err["message"]
    assert err["fix"]


def test_same_site_means_same_scheme_host_and_port_over_http(cli, routes) -> None:
    """A crawl acts as the user in their own browser. A link that shares only the host name
    -- another scheme, another port -- is a different site, and ftp: is not a web page."""
    routes({
        "sitemap": {"https://site.test/sitemap.xml": ["ftp://site.test/listed", "https://site.test/listed"]},
        "links": {"https://site.test/": ["ftp://site.test/file", "http://site.test/insecure",
                                         "https://site.test:8443/other-port", "https://site.test:0/port-zero", "/same"]},
    })

    code, from_sitemap, _ = cli("map", "https://site.test/")
    _, from_links, _ = cli("map", "https://site.test/", "--no-sitemap", "--depth", "1")

    assert from_sitemap["urls"] == ["https://site.test/listed"]
    assert from_links["urls"] == ["https://site.test/", "https://site.test/same"]


@pytest.mark.parametrize("left_behind", ["manifest", "other"])
def test_a_crawl_never_writes_into_a_folder_that_already_has_files(cli, routes, tmp_path: Path, left_behind: str) -> None:
    """Numbered names repeat from one crawl to the next, so writing into a used folder
    replaces pages from the earlier crawl -- or a file that was never a crawl's -- in place."""
    routes({"links": SITE, "fetch_batch": {u: page(ARTICLE) for u in SITE}})
    out = tmp_path / "site"
    if left_behind == "manifest":
        cli("crawl", "https://site.test/", "--depth", "1", "--out", str(out))
    else:
        out.mkdir()
        (out / "000-notes.md").write_text("mine")
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    code, err, _ = cli("crawl", "https://site.test/", "--depth", "1", "--out", str(out))

    assert code == 2
    assert err["error"] == "bad_arguments"
    assert "--out" in err["fix"]
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_crawls_without_out_each_get_their_own_folder(cli, routes, runs_dir: Path) -> None:
    routes({"links": SITE, "fetch_batch": {u: page(ARTICLE) for u in SITE}})

    _, first, _ = cli("crawl", "https://site.test/", "--depth", "1")
    kept = {p: p.read_bytes() for p in Path(first["out_dir"]).iterdir()}
    _, second, _ = cli("crawl", "https://site.test/", "--depth", "0")

    assert Path(first["out_dir"]).parent == Path(second["out_dir"]).parent == runs_dir / "crawls" / "site.test"
    assert first["out_dir"] != second["out_dir"]
    assert {p: p.read_bytes() for p in Path(first["out_dir"]).iterdir()} == kept
    assert sorted(p.name[:4] for p in Path(second["out_dir"]).glob("*.md")) == ["000-"]


def test_map_reports_what_it_could_not_read(cli, routes) -> None:
    """A map that silently lost half a site reads as a small site. What was missed, and why
    discovery stopped, is part of the answer."""
    routes({"links": {"https://site.test/": ["/a", "/b"], "https://site.test/a": ["/a/1"]}})

    code, payload, _ = cli("map", "https://site.test/", "--depth", "2")

    assert code == 0
    coverage = payload["coverage"]
    assert coverage["sitemap"] is False
    assert coverage["pages_read"] == 2
    assert [m["url"] for m in coverage["pages_missed"]] == ["https://site.test/b"]
    assert coverage["budget_exhausted"] is False
    assert coverage["max_urls_reached"] is False


def test_map_that_read_nothing_exits_empty(cli, routes) -> None:
    """The root alone, unread, is not a map of anything -- even though it is one URL."""
    routes({"links": {}})

    code, payload, _ = cli("map", "https://site.test/")

    assert code == 5
    assert payload["coverage"]["pages_read"] == 0
    assert [m["url"] for m in payload["coverage"]["pages_missed"]] == ["https://site.test/"]


def test_map_says_when_a_budget_or_the_cap_cut_discovery_short(cli, routes) -> None:
    routes({"links": {**SITE, "__hit_budget__": True}})

    _, cut, _ = cli("map", "https://site.test/", "--depth", "1")
    _, capped, _ = cli("map", "https://site.test/", "--depth", "3", "--max-urls", "3")

    assert cut["coverage"]["budget_exhausted"] is True
    assert capped["coverage"]["max_urls_reached"] is True


def test_map_from_a_sitemap_says_so(cli, routes) -> None:
    routes({"sitemap": {"https://site.test/sitemap.xml": ["https://site.test/x"]}})

    code, payload, _ = cli("map", "https://site.test/")

    assert code == 0
    assert payload["coverage"]["sitemap"] is True


def test_a_file_that_was_written_counts_as_success(cli, routes) -> None:
    """`--format html` saves the document even when no article was extracted from it. The
    item keeps saying what the page is, but a command that wrote what was asked for has not
    failed."""
    routes({"fetch_batch": {"https://x.com/a": page(SHELL)}})

    code, payload, _ = cli("fetch", "https://x.com/a", "--format", "html", "--via", "fetch")

    assert item_of(payload)["status"] == "shell"
    assert item_of(payload)["path"] is not None
    assert code == 0


@pytest.mark.parametrize("ct", ["text/markdown", "text/plain"])
def test_an_empty_body_is_not_a_page_that_was_read(cli, routes, ct: str) -> None:
    routes({"fetch_batch": {"https://example.org/empty": page("  \n", ct=ct)}})

    code, payload, _ = cli("fetch", "https://example.org/empty", "--via", "fetch")

    assert item_of(payload)["status"] != "ok"
    assert "empty" in item_of(payload)["error"]
    assert item_of(payload)["path"] is None
    assert code == 4


def test_a_miss_after_the_cap_is_reached_is_still_reported(cli, routes) -> None:
    routes({"links": {"https://site.test/": ["/a", "/b"], "https://site.test/a": ["/c"]}})

    _, payload, _ = cli("map", "https://site.test/", "--depth", "2", "--max-urls", "4")

    assert payload["coverage"]["max_urls_reached"] is True
    assert [m["url"] for m in payload["coverage"]["pages_missed"]] == ["https://site.test/b"]


@pytest.mark.parametrize("snippet", ["links", "sitemap"])
def test_a_discovery_snippet_cut_off_by_the_repl_limit_is_reported(cli, routes, snippet: str) -> None:
    """The daemon kills a snippet at 120 seconds and says nothing more. What it printed
    before that is kept; that the list is incomplete has to be said too."""
    table = {
        "links": {"links": {"https://site.test/": ["/a"], "__timeout__": True}},
        "sitemap": {"sitemap": {"https://site.test/sitemap.xml": ["https://site.test/x"], "__timeout__": True}},
    }[snippet]
    routes(table)

    code, payload, _ = cli("map", "https://site.test/", "--depth", "1")

    assert code == 0
    assert payload["urls"]
    assert payload["coverage"]["budget_exhausted"] is True


def test_one_malformed_link_does_not_lose_the_rest_of_the_page(cli, routes) -> None:
    routes({"links": {"https://site.test/": ["http://[broken", "/ok"]}})

    code, payload, _ = cli("map", "https://site.test/", "--depth", "1")

    assert code == 0
    assert payload["urls"] == ["https://site.test/", "https://site.test/ok"]


def test_a_document_that_converts_to_nothing_is_not_a_page_that_was_read(cli, routes) -> None:
    routes({"fetch_batch": {"https://example.org/data.csv": document("empty.csv", ct="text/csv")}})

    code, payload, _ = cli("fetch", "https://example.org/data.csv")

    assert item_of(payload)["status"] != "ok"
    assert item_of(payload)["path"] is None
    assert code == 4


def test_an_escaped_ampersand_in_a_link_is_the_url_the_page_meant(cli, routes) -> None:
    """An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim asks the
    site for a parameter called `amp;lang`."""
    routes({"links": {"https://site.test/": ["/article?id=1&amp;lang=ko", "/q?id=1&copy=2&notebook=3",
                                             "/n?id=1&#38lang=en", "/c/&copy", "/q?x=1&notebook;=2", "/d/&copy한글"]}})

    _, payload, _ = cli("map", "https://site.test/", "--depth", "1")

    # Decoded as a browser decodes an attribute: numeric and closed references always, a bare
    # name only when neither "=" nor a letter or digit follows it.
    assert payload["urls"] == ["https://site.test/", "https://site.test/article?id=1&lang=ko",
                               "https://site.test/q?id=1&copy=2&notebook=3",
                               "https://site.test/n?id=1&lang=en", "https://site.test/c/©",
                               "https://site.test/q?x=1&notebook;=2", "https://site.test/d/©한글"]
