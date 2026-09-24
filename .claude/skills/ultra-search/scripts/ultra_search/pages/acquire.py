"""Getting pages, and putting them where they can be read.

Two shapes carry most of the value here.

Batches are per-URL isolated. The REPL is killed at 120 seconds regardless of how the
work inside it is going, so a batch that succeeded or failed as a unit would lose seven
finished pages to one hanging navigation. Each URL reports as it lands, and a URL that
failed is retried alone rather than back inside a batch it already exhausted.

And the full text always goes to a file. A fetch of ten pages that returned their
contents would put ten pages into the caller's context as a side effect of being told
where they are; `--print` makes that a decision instead of a default.
"""
from __future__ import annotations

from pathlib import Path

from ultra_search.contract import ArgumentError
from ultra_search.pages import browser, classify

DEFAULT_CONCURRENCY = 8
DEFAULT_RETRIES = 1


def fetch_urls(
    urls: list[str],
    *,
    out_dir: Path | None = None,
    out_file: Path | None = None,
    via: str = "auto",
    fmt: str = "md",
    frontmatter: bool = True,
    print_content: bool = False,
    max_chars: int = 20000,
    concurrency: int = DEFAULT_CONCURRENCY,
    retries: int = DEFAULT_RETRIES,
    numbered: bool = False,
) -> dict:
    if out_file and len(urls) > 1:
        raise ArgumentError(
            f"--out names a single file but {len(urls)} URLs were given",
            fix="Pass a directory instead, or fetch one URL at a time.",
        )
    dest = out_file.parent if out_file else (out_dir or Path.cwd())
    dest.mkdir(parents=True, exist_ok=True)

    raw: dict[str, dict] = {}
    if via != "tab":
        for batch in _chunks(urls, max(1, concurrency)):
            for record in browser.fetch_batch(batch):
                if record.get("kind") == "batch_done" or not record.get("url"):
                    continue
                raw[record["url"]] = record
        for _ in range(max(0, retries)):
            missing = [u for u in urls if _needs_retry(raw.get(u))]
            if not missing:
                break
            for u in missing:
                # Alone, not re-batched: it gets the whole per-URL budget rather than a
                # share of the one it already used up.
                for record in browser.fetch_batch([u]):
                    if record.get("url"):
                        raw[record["url"]] = record

    items = []
    used_names: set[str] = set()
    for i, url in enumerate(urls):
        # Numbered names read in crawl order in a directory listing, which is usually the
        # order a site means its pages to be read. The final name is chosen here, once.
        stem = f"{i:03d}-{classify.slug_for(url)}" if numbered else classify.slug_for(url)
        record = raw.get(url)
        doc = _to_document(url, record) if record else classify.Document(
            url=url, status="error", error="no response"
        )
        if via == "tab" or (via == "auto" and doc.status in ("shell", "challenge")):
            doc = _escalate(url, doc)
        items.append(_save(doc, url, dest, out_file, frontmatter, fmt, print_content, max_chars, used_names, record, stem))
    return {"ok": True, "command": "fetch", "items": items}


def _needs_retry(record: dict | None) -> bool:
    return record is None or record.get("kind") == "error"


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _to_document(url: str, record: dict) -> classify.Document:
    if record.get("kind") == "error":
        return classify.Document(url=url, status="error", error=str(record.get("error") or "fetch failed"))
    body = (record.get("text") or "").encode("utf-8") if record.get("kind") == "text" else b""
    doc = classify.classify_response(
        status=int(record.get("status") or 0),
        content_type=record.get("content_type") or "",
        body=body,
        url=url,
        saved_path=record.get("saved_path"),
    )
    doc.final_url = record.get("final_url") or url
    doc.via = record.get("via") or "fetch"
    return doc


def _escalate(url: str, doc: classify.Document) -> classify.Document:
    """Re-fetch through a real browser tab.

    Worth trying for both a client-rendered shell and a bot challenge: the tab runs the
    JavaScript in one case and clears the interstitial in the other. If what comes back
    is still thin, the original verdict stands and is reported as escalated-and-still-empty
    rather than as a page.
    """
    records = [r for r in (browser.tab_one(url) or []) if r.get("kind") == "text"]
    if not records:
        doc.status = "shell_escalated" if doc.status == "shell" else "blocked"
        return doc
    record = records[0]
    promoted = classify.extract_html(record.get("text") or "", url, via="tab")
    promoted.final_url = record.get("final_url") or url
    if promoted.status == "ok":
        return promoted

    # An article extractor finding no article does not mean the tab found nothing. A
    # subscription feed, an inbox, a dashboard -- the pages a logged-in fetch exists for --
    # have real rendered text and no article, so that text is the answer for them.
    if promoted.status == "shell":
        visible = (record.get("visible_text") or "").strip()
        if classify.count_words(visible) >= classify.SHELL_WORD_THRESHOLD:
            return classify.Document(
                markdown=visible,
                title=promoted.title or doc.title,
                url=url,
                final_url=promoted.final_url,
                via="tab",
                words=classify.count_words(visible),
                kind="rendered_text",
                status="ok",
            )

    promoted.status = "shell_escalated" if promoted.status == "shell" else "blocked"
    promoted.error = promoted.error or doc.error
    return promoted


def _save(doc, url, dest, out_file, frontmatter, fmt, print_content, max_chars, used_names, record, stem) -> dict:
    item = {
        "url": url,
        "final_url": doc.final_url or url,
        "status": doc.status,
        "via": doc.via,
        "title": doc.title,
        "words": doc.words,
        "path": None,
    }
    if doc.http_status:
        item["http_status"] = doc.http_status
    if doc.error:
        item["error"] = doc.error

    # What counts as "usable" depends on what was asked for. `--format md` needs an
    # article, so a page that extracted to nothing has nothing to write. `--format html`
    # asked for the document itself, and a client-rendered page still has one -- gating
    # that on article extraction would refuse to save exactly the pages someone reaches
    # for raw HTML to inspect.
    #
    # A challenge or a blocked response is refused either way: saving one looks like a
    # source that was read, which is the failure this whole module is arranged around.
    if doc.status in ("challenge", "blocked"):
        return item
    if fmt == "html":
        # Saving the document needs no article extractor, so a converter that is missing or
        # that failed does not stand between the caller and the bytes already in hand.
        if not (doc.raw or "").strip():
            item["status"] = "unsupported"
            item["error"] = f"--format html needs an HTML response; this one was {doc.kind}"
            return item
    elif doc.status != "ok" or not (doc.markdown or "").strip():
        return item

    path = out_file or _unique_path(dest, stem, used_names, fmt)
    text = doc.raw if fmt == "html" else classify.render_markdown(doc, frontmatter=frontmatter)
    body_for_print = text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    item["path"] = str(path)

    if record and record.get("saved_path"):
        original = Path(record["saved_path"])
        if original.exists():
            kept = path.with_suffix("." + (record.get("ext") or original.suffix.lstrip(".") or "bin"))
            try:
                kept.write_bytes(original.read_bytes())
                item["original_path"] = str(kept)
            except OSError:
                pass

    if print_content:
        # The same bytes that went to the file. Returning markdown alongside an .html file
        # would make --print disagree with the artifact it is describing.
        item["content"] = body_for_print[:max_chars]
        item["truncated"] = len(body_for_print) > max_chars
    return item


def _unique_path(dest: Path, slug: str, used: set[str], fmt: str) -> Path:
    ext = {"md": ".md", "html": ".html"}.get(fmt, ".md")
    name = slug
    n = 2
    # Slugs flatten punctuation, so /a/b and /a-b arrive here identical. Suffixing keeps
    # the second page instead of silently replacing the first.
    while name in used or (dest / f"{name}{ext}").exists():
        name = f"{slug}-{n}"
        n += 1
    used.add(name)
    return dest / f"{name}{ext}"
