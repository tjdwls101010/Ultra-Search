"""_extract: deciding what a response actually is, and turning it into markdown.

The seam is a fetched response (bytes, status, content-type) in, a verdict and markdown
out. The HTML fixtures are real captures through the user's browser, so the thresholds
here are calibrated against pages that exist rather than invented ones:

    tests/fixtures/html/article.html          4355 words  (Wikipedia)
    tests/fixtures/html/docs_page_html.html    388 words  (docs.aside.com)
    tests/fixtures/html/news_ko.html           219 words  (Korean news front page)
    tests/fixtures/html/challenge.html          24 words  (Cloudflare interstitial)
    tests/fixtures/html/js_shell.html            0 words  (x.com, renders client-side)

Reporting a blocked or empty page as a successful read is the failure that matters most
here: it removes a source from an investigation without anyone noticing it left.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import _extract


def html(fixtures: Path, name: str) -> str:
    return (fixtures / "html" / f"{name}.html").read_text(encoding="utf-8")


# --- classification ------------------------------------------------------------------


def test_an_article_extracts_to_markdown(fixtures: Path) -> None:
    out = _extract.extract_html(html(fixtures, "article"), "https://en.wikipedia.org/wiki/Web_scraping")

    assert out.status == "ok"
    assert out.words > 1000
    assert out.title == "Web scraping"
    assert "scraping" in out.markdown.lower()


def test_a_korean_page_is_not_mistaken_for_an_empty_one(fixtures: Path) -> None:
    """Counting whitespace-delimited tokens undercounts CJK badly enough that a real
    Korean page can fall under an English-calibrated threshold and be escalated for no
    reason."""
    out = _extract.extract_html(html(fixtures, "news_ko"), "https://www.yna.co.kr/")

    assert out.status == "ok"
    assert out.words >= 100


def test_a_client_rendered_page_is_recognised_as_a_shell(fixtures: Path) -> None:
    """x.com is the case that distinguishes the two. It extracts to nothing AND it is
    served through Cloudflare, whose passive bot-detection script sits in every one of
    its ordinary pages -- so a challenge check keyed on that script would call this a
    block and never escalate it. Escalating a shell works; giving up on a block does not."""
    out = _extract.extract_html(html(fixtures, "js_shell"), "https://x.com/elonmusk")

    assert out.status == "shell"
    assert out.words < _extract.SHELL_WORD_THRESHOLD


def test_a_cloudflare_fronted_article_is_not_called_blocked(fixtures: Path) -> None:
    body = html(fixtures, "article").replace(
        "</body>", '<script src="/cdn-cgi/challenge-platform/scripts/jsd/api.js"></script></body>'
    )

    assert _extract.extract_html(body, "https://en.wikipedia.org/wiki/Web_scraping").status == "ok"


def test_a_bot_challenge_is_not_reported_as_the_page(fixtures: Path) -> None:
    """A challenge page is a successful HTTP response with a body. Saving it as the
    article is how a source silently drops out of an investigation."""
    out = _extract.extract_html(html(fixtures, "challenge"), "https://example.com/")

    assert out.status == "challenge"


def test_a_challenge_is_detected_even_when_it_is_wordy(fixtures: Path) -> None:
    body = html(fixtures, "challenge").replace(
        "</body>", "<p>" + ("filler word " * 200) + "</p></body>"
    )

    assert _extract.extract_html(body, "https://example.com/").status == "challenge"


def test_an_http_error_is_reported_before_anything_is_parsed() -> None:
    verdict = _extract.classify_response(status=403, content_type="text/html", body=b"<html>nope</html>")

    assert verdict.status == "blocked"
    assert verdict.http_status == 403


def test_markdown_served_as_markdown_is_passed_through(fixtures: Path) -> None:
    """docs.aside.com serves text/markdown for its .md URLs. Running that through an
    HTML article extractor yields nothing -- measured, 0 words -- so it must not go there."""
    verdict = _extract.classify_response(
        status=200, content_type="text/markdown; charset=utf-8", body=b"# Title\n\nBody text here.\n"
    )

    assert verdict.status == "ok"
    assert verdict.kind == "markdown"
    assert verdict.markdown.startswith("# Title")


def test_plain_text_is_passed_through() -> None:
    verdict = _extract.classify_response(status=200, content_type="text/plain", body=b"just some text")

    assert verdict.status == "ok"
    assert "just some text" in verdict.markdown


# --- documents -----------------------------------------------------------------------


def test_a_pdf_becomes_structured_markdown(fixtures: Path) -> None:
    out = _extract.extract_document(fixtures / "docs" / "sample_en.pdf")

    assert out.status == "ok"
    assert "Example Domain" in out.markdown


def test_a_korean_pdf_keeps_its_text(fixtures: Path) -> None:
    out = _extract.extract_document(fixtures / "docs" / "sample_ko.pdf")

    assert out.status == "ok"
    assert any("가" <= ch <= "힯" for ch in out.markdown)


def test_a_file_that_is_not_the_document_it_claims_is_reported_not_guessed(fixtures: Path) -> None:
    out = _extract.extract_document(fixtures / "docs" / "not_really.pdf")

    assert out.status == "unsupported"
    assert "html" in (out.error or "").lower()


def test_a_scanned_pdf_asks_for_ocr_rather_than_returning_nothing(tmp_path: Path, monkeypatch) -> None:
    """anydoc exits 3 for a PDF with no text layer. Sending it for hosted OCR would ship
    the user's document to a third party, so the honest answer is that this one needs a
    step nobody has authorised."""
    monkeypatch.setattr(_extract, "_run_anydoc", lambda p: (3, "", "needs OCR"))

    out = _extract.extract_document(tmp_path / "scan.pdf")

    assert out.status == "needs_ocr"


# --- output shape ---------------------------------------------------------------------


def test_frontmatter_records_where_the_text_came_from() -> None:
    doc = _extract.Document(markdown="본문", title="제목", url="https://example.org/a", via="tab", words=2)

    text = _extract.render_markdown(doc, frontmatter=True)

    assert text.startswith("---\n")
    assert 'url: "https://example.org/a"' in text
    assert "via: tab" in text
    assert text.rstrip().endswith("본문")


def test_frontmatter_can_be_left_off() -> None:
    doc = _extract.Document(markdown="본문", title="제목", url="https://example.org/a", via="fetch", words=1)

    assert _extract.render_markdown(doc, frontmatter=False) == "본문\n"


def test_a_title_with_quotes_does_not_break_the_frontmatter() -> None:
    doc = _extract.Document(markdown="x", title='He said "hi"\nand left', url="https://e.org/", via="fetch", words=1)

    text = _extract.render_markdown(doc, frontmatter=True)
    header = text.split("---")[1]
    assert "\n" not in header.split("title:")[1].split("\n")[0].strip('" ')


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://docs.aside.com/help/developers", "docs.aside.com-help-developers"),
        ("https://example.org/", "example.org"),
        ("https://example.org/a/b/?q=1", "example.org-a-b"),
    ],
)
def test_slugs_are_readable_and_stable(url: str, expected: str) -> None:
    assert _extract.slug_for(url) == expected


def test_slugs_stay_within_a_sane_filename_length() -> None:
    long_url = "https://example.org/" + "segment/" * 60

    assert len(_extract.slug_for(long_url)) <= 120


def test_a_challenge_is_recognised_without_running_the_converter(fixtures: Path, monkeypatch) -> None:
    """The decisive markers are read off the raw body, before conversion. An interstitial
    that arrives when node is missing would otherwise come back as an extraction error --
    and an error is not escalated to a browser tab, which is the one thing that clears a
    challenge."""
    monkeypatch.setattr(
        _extract, "_run_to_markdown", lambda html, url: {"ok": False, "message": "node is not installed"}
    )

    out = _extract.extract_html(html(fixtures, "challenge"), "https://example.com/")

    assert out.status == "challenge"


def test_a_normal_page_without_the_converter_is_an_error_not_a_challenge(fixtures: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        _extract, "_run_to_markdown", lambda html, url: {"ok": False, "message": "node is not installed"}
    )

    out = _extract.extract_html(html(fixtures, "article"), "https://en.wikipedia.org/wiki/Web_scraping")

    assert out.status == "error"
    assert "node" in (out.error or "")


def test_the_original_html_is_kept_on_the_document(fixtures: Path) -> None:
    body = html(fixtures, "article")

    out = _extract.extract_html(body, "https://en.wikipedia.org/wiki/Web_scraping")

    assert out.raw == body
