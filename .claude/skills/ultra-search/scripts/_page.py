"""`fetch`, `map` and `crawl` -- getting pages, and putting them where they can be read.

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

import json
from pathlib import Path

import _errors
import _extract
import _registry
import _repl
from _errors import ArgumentError

DEFAULT_CONCURRENCY = 8
DEFAULT_RETRIES = 1

#: Statuses worth a second, isolated attempt. A 403 or a scanned PDF will not change.
_RETRYABLE = frozenset({"error"})


def dispatch(args) -> int:
    runs_root = _registry.resolve_runs_dir(args.runs_dir)
    if args.command == "fetch":
        return _fetch_cmd(args, runs_root)
    import _crawl_cmds

    return _crawl_cmds.dispatch(args, runs_root)


def _fetch_cmd(args, runs_root: Path) -> int:
    out_file, out_dir = _destinations(args.url, args.out, runs_root)
    envelope = fetch_urls(
        args.url,
        out_dir=out_dir,
        out_file=out_file,
        via=args.via,
        fmt=args.format,
        frontmatter=not args.no_frontmatter,
        print_content=args.print_content,
        max_chars=args.max_chars,
        concurrency=args.concurrency,
    )
    print(json.dumps(envelope, ensure_ascii=False))
    return exit_code_for(envelope["items"])


def _destinations(urls: list[str], out: str | None, runs_root: Path) -> tuple[Path | None, Path]:
    """Split --out into a file destination or a directory one.

    A path is a file only when it looks like one -- an existing file, or a name with an
    extension. Anything else is a directory, because `--out ./notes` for one URL means a
    folder to everyone who types it, and silently producing an extensionless file named
    `notes` is the kind of surprise nobody checks for.
    """
    if not out:
        return None, _registry.pages_dir(runs_root)
    p = Path(out).expanduser()
    looks_like_file = p.is_file() or (bool(p.suffix) and not p.is_dir() and not out.endswith("/"))
    if looks_like_file:
        if len(urls) > 1:
            raise ArgumentError(
                f"--out {out!r} names a file but {len(urls)} URLs were given",
                fix="Pass a directory for several URLs, or fetch them one at a time.",
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, p.parent
    p.mkdir(parents=True, exist_ok=True)
    return None, p


def exit_code_for(items: list[dict]) -> int:
    if not items:
        return _errors.EXIT_EMPTY
    if all(i["status"] == "ok" for i in items):
        return 0
    if any(i["status"] == "ok" for i in items):
        return 0
    return _errors.EXIT_RUN_FAILED


# --- the work ---------------------------------------------------------------------------


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
    fetch_provider=None,
    tab_provider=None,
) -> dict:
    if out_file and len(urls) > 1:
        raise ArgumentError(
            f"--out names a single file but {len(urls)} URLs were given",
            fix="Pass a directory instead, or fetch one URL at a time.",
        )
    fetch_provider = fetch_provider or _repl.fetch_batch
    tab_provider = tab_provider or _repl.tab_one
    dest = out_file.parent if out_file else (out_dir or Path.cwd())
    dest.mkdir(parents=True, exist_ok=True)

    raw: dict[str, dict] = {}
    if via != "tab":
        for batch in _chunks(urls, max(1, concurrency)):
            for record in fetch_provider(batch, save_dir=dest):
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
                for record in fetch_provider([u], save_dir=dest):
                    if record.get("url"):
                        raw[record["url"]] = record

    items = []
    used_names: set[str] = set()
    for url in urls:
        record = raw.get(url)
        doc = _to_document(url, record) if record else _extract.Document(
            url=url, status="error", error="no response"
        )
        if via == "tab" or (via == "auto" and doc.status in ("shell", "challenge")):
            doc = _escalate(url, doc, tab_provider)
        items.append(_save(doc, url, dest, out_file, frontmatter, fmt, print_content, max_chars, used_names, record))
    return {"ok": True, "command": "fetch", "items": items}


def _needs_retry(record: dict | None) -> bool:
    return record is None or record.get("kind") == "error"


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _to_document(url: str, record: dict) -> _extract.Document:
    if record.get("kind") == "error":
        return _extract.Document(url=url, status="error", error=str(record.get("error") or "fetch failed"))
    body = (record.get("text") or "").encode("utf-8") if record.get("kind") == "text" else b""
    doc = _extract.classify_response(
        status=int(record.get("status") or 0),
        content_type=record.get("content_type") or "",
        body=body,
        url=url,
        saved_path=record.get("saved_path"),
    )
    doc.final_url = record.get("final_url") or url
    doc.via = record.get("via") or "fetch"
    return doc


def _escalate(url: str, doc: _extract.Document, tab_provider) -> _extract.Document:
    """Re-fetch through a real browser tab.

    Worth trying for both a client-rendered shell and a bot challenge: the tab runs the
    JavaScript in one case and clears the interstitial in the other. If what comes back
    is still thin, the original verdict stands and is reported as escalated-and-still-empty
    rather than as a page.
    """
    records = [r for r in (tab_provider(url) or []) if r.get("kind") == "text"]
    if not records:
        doc.status = "shell_escalated" if doc.status == "shell" else "blocked"
        return doc
    record = records[0]
    promoted = _extract.extract_html(record.get("text") or "", url, via="tab")
    promoted.final_url = record.get("final_url") or url
    if promoted.status == "ok":
        return promoted

    # An article extractor finding no article does not mean the tab found nothing. A
    # subscription feed, an inbox, a dashboard -- the pages a logged-in fetch exists for --
    # have real rendered text and no article, so that text is the answer for them.
    if promoted.status == "shell":
        visible = (record.get("visible_text") or "").strip()
        if _extract.count_words(visible) >= _extract.SHELL_WORD_THRESHOLD:
            return _extract.Document(
                markdown=visible,
                title=promoted.title or doc.title,
                url=url,
                final_url=promoted.final_url,
                via="tab",
                words=_extract.count_words(visible),
                kind="rendered_text",
                status="ok",
            )

    promoted.status = "shell_escalated" if promoted.status == "shell" else "blocked"
    promoted.error = promoted.error or doc.error
    return promoted


def _save(doc, url, dest, out_file, frontmatter, fmt, print_content, max_chars, used_names, record) -> dict:
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

    path = out_file or _unique_path(dest, _extract.slug_for(url), used_names, fmt)
    text = doc.raw if fmt == "html" else _extract.render_markdown(doc, frontmatter=frontmatter)
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
