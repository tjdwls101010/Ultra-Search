"""_page: fetch orchestration -- batching, escalation, retry, and where files land.

The seam is a response provider in, an envelope and files out. The provider stands in for
the browser round trip, so these tests cover the orchestration without a daemon; the real
transport is exercised in tests/live.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import _page


def provider(responses: dict, *, record: list | None = None):
    """A stand-in for the browser: URL -> the NDJSON record the snippet would have printed."""

    def fetch(urls, **kw):
        if record is not None:
            record.append(list(urls))
        out = []
        for u in urls:
            r = responses.get(u)
            if r is None:
                out.append({"url": u, "status": 404, "kind": "error", "error": "not in fixture"})
            elif callable(r):
                got = r(u)
                if got is not None:
                    out.append(got)
            else:
                out.append(dict(r, url=u))
        out.append({"kind": "batch_done", "requested": len(urls)})
        return out

    return fetch


def text_response(body: str, ct: str = "text/html", status: int = 200) -> dict:
    return {"status": status, "content_type": ct, "kind": "text", "text": body, "final_url": None}


ARTICLE = "<html><head><title>제목</title></head><body><article><p>" + ("단어 " * 300) + "</p></article></body></html>"
SHELL = "<html><head><title>shell</title></head><body><div id=root></div></body></html>"


def test_a_page_is_saved_as_markdown_and_reported(tmp_path: Path) -> None:
    out = _page.fetch_urls(
        ["https://example.org/a"],
        out_dir=tmp_path,
        fetch_provider=provider({"https://example.org/a": text_response(ARTICLE)}),
    )

    item = out["items"][0]
    assert item["status"] == "ok"
    assert item["via"] == "fetch"
    saved = Path(item["path"])
    assert saved.exists() and saved.suffix == ".md"
    assert "단어" in saved.read_text(encoding="utf-8")


def test_the_full_text_goes_to_a_file_not_into_the_reply(tmp_path: Path) -> None:
    """A fetch of ten pages would otherwise put ten pages into the caller's context as a
    side effect of asking where they are."""
    out = _page.fetch_urls(
        ["https://example.org/a"],
        out_dir=tmp_path,
        fetch_provider=provider({"https://example.org/a": text_response(ARTICLE)}),
    )

    assert "content" not in out["items"][0]
    assert out["items"][0]["words"] > 100


def test_print_includes_the_content_but_caps_it(tmp_path: Path) -> None:
    out = _page.fetch_urls(
        ["https://example.org/a"],
        out_dir=tmp_path,
        print_content=True,
        max_chars=50,
        fetch_provider=provider({"https://example.org/a": text_response(ARTICLE)}),
    )

    item = out["items"][0]
    assert len(item["content"]) <= 50
    assert item["truncated"] is True


def test_a_shell_is_escalated_to_a_browser_tab(tmp_path: Path) -> None:
    calls: list = []

    def tab(url, **kw):
        calls.append(url)
        return [{"url": url, "final_url": url, "status": 200, "kind": "text", "via": "tab", "text": ARTICLE}]

    out = _page.fetch_urls(
        ["https://x.com/a"],
        out_dir=tmp_path,
        fetch_provider=provider({"https://x.com/a": text_response(SHELL)}),
        tab_provider=tab,
    )

    assert calls == ["https://x.com/a"]
    item = out["items"][0]
    assert item["status"] == "ok"
    assert item["via"] == "tab"


def test_escalation_is_skipped_when_the_caller_forced_plain_fetch(tmp_path: Path) -> None:
    calls: list = []

    out = _page.fetch_urls(
        ["https://x.com/a"],
        out_dir=tmp_path,
        via="fetch",
        fetch_provider=provider({"https://x.com/a": text_response(SHELL)}),
        tab_provider=lambda url, **kw: calls.append(url) or [],
    )

    assert calls == []
    assert out["items"][0]["status"] == "shell"
    assert out["items"][0]["path"] is None


def test_a_page_that_is_still_a_shell_after_the_tab_says_so(tmp_path: Path) -> None:
    out = _page.fetch_urls(
        ["https://x.com/a"],
        out_dir=tmp_path,
        fetch_provider=provider({"https://x.com/a": text_response(SHELL)}),
        tab_provider=lambda url, **kw: [{"url": url, "status": 200, "kind": "text", "via": "tab", "text": SHELL}],
    )

    assert out["items"][0]["status"] == "shell_escalated"


def test_a_blocked_response_is_never_saved_as_the_page(tmp_path: Path) -> None:
    out = _page.fetch_urls(
        ["https://example.org/x"],
        out_dir=tmp_path,
        via="fetch",
        fetch_provider=provider({"https://example.org/x": text_response("nope", status=403)}),
    )

    item = out["items"][0]
    assert item["status"] == "blocked"
    assert item.get("path") is None
    assert not list(tmp_path.glob("*.md"))


# --- the batch failure mode this whole shape exists for --------------------------------


def test_one_slow_url_does_not_lose_the_rest_of_its_batch(tmp_path: Path) -> None:
    """The 120s REPL limit applies to the whole snippet. If a batch were all-or-nothing,
    a single hanging navigation would discard seven finished pages along with it."""
    urls = [f"https://example.org/p{i}" for i in range(8)]
    responses = {u: text_response(ARTICLE) for u in urls}
    responses[urls[3]] = {"status": 0, "kind": "error", "error": "timeout"}

    out = _page.fetch_urls(urls, out_dir=tmp_path, fetch_provider=provider(responses), retries=0)

    ok = [i for i in out["items"] if i["status"] == "ok"]
    assert len(ok) == 7
    assert len(list(tmp_path.glob("*.md"))) == 7
    assert [i["url"] for i in out["items"] if i["status"] == "error"] == [urls[3]]


def test_a_timed_out_url_is_retried_on_its_own(tmp_path: Path) -> None:
    """Retried alone rather than in the batch it failed in: whatever made it slow gets
    the full per-URL budget instead of a share of one it already exhausted."""
    urls = [f"https://example.org/p{i}" for i in range(4)]
    batches: list = []
    attempts = {"count": 0}

    def flaky(u):
        if u != urls[2]:
            return dict(text_response(ARTICLE), url=u)
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {"url": u, "status": 0, "kind": "error", "error": "timeout"}
        return dict(text_response(ARTICLE), url=u)

    out = _page.fetch_urls(
        urls, out_dir=tmp_path, retries=1,
        fetch_provider=provider({u: flaky for u in urls}, record=batches),
    )

    assert all(i["status"] == "ok" for i in out["items"])
    assert batches[-1] == [urls[2]], "the retry has to be the failing URL alone"


def test_urls_are_split_into_batches_of_the_requested_size(tmp_path: Path) -> None:
    urls = [f"https://example.org/p{i}" for i in range(10)]
    batches: list = []

    _page.fetch_urls(
        urls, out_dir=tmp_path, concurrency=4,
        fetch_provider=provider({u: text_response(ARTICLE) for u in urls}, record=batches),
    )

    assert [len(b) for b in batches] == [4, 4, 2]


# --- documents -------------------------------------------------------------------------


def test_a_pdf_is_converted_from_the_file_the_browser_saved(tmp_path: Path, fixtures: Path) -> None:
    pdf = fixtures / "docs" / "sample_en.pdf"

    out = _page.fetch_urls(
        ["https://example.org/paper.pdf"],
        out_dir=tmp_path,
        fetch_provider=provider({
            "https://example.org/paper.pdf": {
                "status": 200, "content_type": "application/pdf", "kind": "file",
                "saved_path": str(pdf), "ext": "pdf",
            }
        }),
    )

    item = out["items"][0]
    assert item["status"] == "ok"
    assert "Example Domain" in Path(item["path"]).read_text(encoding="utf-8")


def test_the_original_document_is_kept_beside_the_markdown(tmp_path: Path, fixtures: Path) -> None:
    """The conversion is lossy and the download cost a round trip; keeping the original
    means a better converter later does not need the network again."""
    pdf = fixtures / "docs" / "sample_en.pdf"

    out = _page.fetch_urls(
        ["https://example.org/paper.pdf"],
        out_dir=tmp_path,
        fetch_provider=provider({
            "https://example.org/paper.pdf": {
                "status": 200, "content_type": "application/pdf", "kind": "file",
                "saved_path": str(pdf), "ext": "pdf",
            }
        }),
    )

    assert Path(out["items"][0]["original_path"]).exists()


# --- output destinations ----------------------------------------------------------------


def test_a_single_url_may_be_written_to_a_named_file(tmp_path: Path) -> None:
    target = tmp_path / "answer.md"

    out = _page.fetch_urls(
        ["https://example.org/a"], out_file=target,
        fetch_provider=provider({"https://example.org/a": text_response(ARTICLE)}),
    )

    assert Path(out["items"][0]["path"]) == target
    assert target.exists()


def test_several_urls_cannot_share_one_output_file(tmp_path: Path) -> None:
    from _errors import ArgumentError

    with pytest.raises(ArgumentError):
        _page.fetch_urls(
            ["https://example.org/a", "https://example.org/b"],
            out_file=tmp_path / "one.md",
            fetch_provider=provider({}),
        )


def test_two_urls_that_slug_the_same_do_not_overwrite_each_other(tmp_path: Path) -> None:
    urls = ["https://example.org/a/b", "https://example.org/a-b"]

    out = _page.fetch_urls(
        urls, out_dir=tmp_path,
        fetch_provider=provider({u: text_response(ARTICLE) for u in urls}),
    )

    paths = {i["path"] for i in out["items"]}
    assert len(paths) == 2


# --- interpreting --out --------------------------------------------------------------
#
# Driven through the CLI rather than the private helper that implements it: what a caller
# relies on is that `--out ./notes` produces a folder, not that any particular function
# decided so.


def out_paths(tmp_path: Path, out: str, monkeypatch) -> dict:
    import ultra_search

    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    calls: list = []

    def fake_batch(urls, **kw):
        calls.append(list(urls))
        return [dict(text_response(ARTICLE), url=u) for u in urls] + [{"kind": "batch_done"}]

    import _repl

    monkeypatch.setattr(_repl, "fetch_batch", fake_batch)

    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ultra_search.main(["fetch", "https://example.org/a", "--out", out, "--runs-dir", str(tmp_path / "runs")])
    return json.loads([l for l in buf.getvalue().splitlines() if l.startswith("{")][-1])


def test_an_extensionless_out_path_is_a_directory(tmp_path: Path, monkeypatch) -> None:
    """`--out ./notes` for one URL means a folder to anyone who types it. Producing an
    extensionless file called `notes` instead is a surprise nobody checks for."""
    target = tmp_path / "notes"

    payload = out_paths(tmp_path, str(target), monkeypatch)

    assert target.is_dir()
    assert Path(payload["items"][0]["path"]).parent == target


def test_a_named_markdown_file_is_a_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "answer.md"

    payload = out_paths(tmp_path, str(target), monkeypatch)

    assert Path(payload["items"][0]["path"]) == target
    assert target.is_file()


def test_a_trailing_slash_is_a_directory_even_with_a_dot_in_the_name(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "v1.2"

    payload = out_paths(tmp_path, str(target) + "/", monkeypatch)

    assert target.is_dir()
    assert Path(payload["items"][0]["path"]).parent == target


def test_several_urls_are_refused_a_single_output_file(tmp_path: Path, monkeypatch) -> None:
    import contextlib
    import io

    import ultra_search

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = ultra_search.main([
            "fetch", "https://example.org/a", "https://example.org/b",
            "--out", str(tmp_path / "one.md"), "--runs-dir", str(tmp_path / "runs"),
        ])

    assert code == 2
    assert "file" in json.loads(buf.getvalue().splitlines()[-1])["message"]


# --- --format ---------------------------------------------------------------------------


def test_format_html_writes_the_original_html(tmp_path: Path) -> None:
    out = _page.fetch_urls(
        ["https://example.org/a"],
        out_dir=tmp_path,
        fmt="html",
        fetch_provider=provider({"https://example.org/a": text_response(ARTICLE)}),
    )

    item = out["items"][0]
    assert item["status"] == "ok"
    saved = Path(item["path"])
    assert saved.suffix == ".html"
    assert saved.read_text(encoding="utf-8") == ARTICLE


def test_format_html_is_refused_for_a_response_that_was_not_html(tmp_path: Path, fixtures: Path) -> None:
    """A .html file containing markdown is a file whose contents contradict its name --
    worse than a refusal, because nothing downstream notices."""
    pdf = fixtures / "docs" / "sample_en.pdf"

    out = _page.fetch_urls(
        ["https://example.org/paper.pdf"],
        out_dir=tmp_path,
        fmt="html",
        fetch_provider=provider({
            "https://example.org/paper.pdf": {
                "status": 200, "content_type": "application/pdf", "kind": "file",
                "saved_path": str(pdf), "ext": "pdf",
            }
        }),
    )

    item = out["items"][0]
    assert item["status"] == "unsupported"
    assert item["path"] is None
    assert not list(tmp_path.glob("*.html"))


def test_format_html_saves_a_client_rendered_page_that_has_no_article(tmp_path: Path) -> None:
    """`--format html` asked for the document, not the article. Gating the save on article
    extraction refuses exactly the pages someone reaches for raw HTML to inspect."""
    out = _page.fetch_urls(
        ["https://x.com/a"],
        out_dir=tmp_path,
        fmt="html",
        via="fetch",
        fetch_provider=provider({"https://x.com/a": text_response(SHELL)}),
    )

    item = out["items"][0]
    assert item["path"] is not None
    assert Path(item["path"]).read_text(encoding="utf-8") == SHELL


def test_format_html_still_refuses_to_save_a_bot_challenge(tmp_path: Path, fixtures: Path) -> None:
    """The one thing that stays refused in every format: a challenge saved as the page
    looks like a source that was read."""
    challenge = (fixtures / "html" / "challenge.html").read_text(encoding="utf-8")

    out = _page.fetch_urls(
        ["https://example.org/c"],
        out_dir=tmp_path,
        fmt="html",
        via="fetch",
        fetch_provider=provider({"https://example.org/c": text_response(challenge)}),
    )

    assert out["items"][0]["status"] == "challenge"
    assert out["items"][0]["path"] is None
    assert list(tmp_path.glob("*.html")) == []
