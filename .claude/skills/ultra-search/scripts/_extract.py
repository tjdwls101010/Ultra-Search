"""Deciding what a fetched response really is, and turning it into markdown.

The order matters and is not arbitrary. Each check answers a question the next one cannot:
an HTTP error is not a page; a document is not HTML and would extract to nothing; a bot
challenge is a successful response whose body is not the article; and a client-rendered
shell parses cleanly to almost no text. Only what survives all four is the page.

Everything here exists to avoid one failure: reporting a blocked, empty or wrong-format
response as a successful read. That removes a source from an investigation without
anyone noticing it left, which is worse than an error, because an error gets retried.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PAGE_DIR = Path(__file__).resolve().parent / "page"
TO_MARKDOWN = PAGE_DIR / "to_markdown.mjs"
ANYDOC = PAGE_DIR / "node_modules" / ".bin" / "anydoc"

#: Below this many words a page is treated as a shell worth re-fetching in a real tab.
#: Calibrated on real captures: x.com 0 and threads 9 fall under, while docs.aside.com
#: (388), a Korean news front page (219) and a Wikipedia article (4355) sit well above.
SHELL_WORD_THRESHOLD = 80

#: Text and paths that only an interstitial serves. Any one of these is decisive.
_CHALLENGE_STRONG = (
    "just a moment",
    "verifying you are human",
    "checking your browser before accessing",
    "enable javascript and cookies to continue",
    "/orchestrate/chl_page",
    "__cf_chl_",
)

#: Present on every page a Cloudflare-fronted site serves, interstitial or not -- x.com
#: loads challenge-platform/scripts/jsd/api.js for passive bot detection on ordinary
#: article pages. Treating either of these as proof would mark a large fraction of the
#: web as blocked, so they only corroborate.
_CHALLENGE_WEAK = (
    "cdn-cgi/challenge-platform",
    "ray id",
)

_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
_SLUG_STRIP = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class Document:
    markdown: str = ""
    title: str = ""
    url: str = ""
    final_url: str = ""
    via: str = "fetch"
    words: int = 0
    status: str = "ok"
    kind: str = "html"
    error: str | None = None
    http_status: int | None = None
    author: str = ""
    published: str = ""
    site: str = ""
    #: The response body exactly as fetched, kept so `--format html` can write the
    #: original rather than a re-rendering of it.
    raw: str = ""


def count_words(text: str) -> int:
    """Words, counting CJK by character.

    A Korean or Japanese paragraph can be a single whitespace-delimited token, so a
    token count would put a full page under the shell threshold and send it for a
    pointless browser round trip.
    """
    stripped = (text or "").strip()
    if not stripped:
        return 0
    cjk = len(_CJK.findall(stripped))
    latin = len(_CJK.sub(" ", stripped).split())
    return latin + cjk


# --- classification -------------------------------------------------------------------


def classify_response(*, status: int, content_type: str, body: bytes, url: str = "",
                      saved_path: str | Path | None = None) -> Document:
    ct = (content_type or "").lower()

    if status and not 200 <= status < 300:
        return Document(url=url, status="blocked", http_status=status, kind="http_error",
                        error=f"HTTP {status}")

    if saved_path:
        doc = extract_document(saved_path)
        doc.url = url
        doc.http_status = status
        return doc

    if _is_document_type(ct, body):
        return Document(url=url, status="unsupported", http_status=status, kind="document",
                        error="a document response arrived without being saved to a file")

    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)

    if ("markdown" in ct or ct.startswith("text/")) and "html" not in ct and "xml" not in ct and not count_words(text):
        # Nothing to read is not a page that was read. Called a shell, it is also worth the
        # real tab a JavaScript shell gets.
        return Document(url=url, status="shell", kind="text", http_status=status,
                        error="the response body is empty")

    if "markdown" in ct:
        # Served as markdown already. An HTML article extractor finds no article in it and
        # returns nothing -- measured 0 words on docs.aside.com's .md URLs.
        return Document(markdown=text, url=url, status="ok", kind="markdown",
                        words=count_words(text), title=_first_heading(text), http_status=status)

    if ct.startswith("text/plain") or (ct.startswith("text/") and "html" not in ct and "xml" not in ct):
        return Document(markdown=text, url=url, status="ok", kind="text",
                        words=count_words(text), http_status=status)

    doc = extract_html(text, url)
    doc.http_status = status
    return doc


def _is_document_type(content_type: str, body: bytes) -> bool:
    ct = content_type or ""
    if any(k in ct for k in ("pdf", "officedocument", "msword", "ms-excel", "ms-powerpoint", "epub", "opendocument")):
        return True
    if isinstance(body, bytes) and len(body) >= 4:
        if body[:4] == b"%PDF" or body[:2] == b"PK" or body[:4] == b"\xd0\xcf\x11\xe0":
            return True
    return False


def looks_like_challenge(html: str, extracted_words: int) -> bool:
    """Whether this response is an interstitial rather than the page.

    Split into decisive and corroborating markers because the obvious signal is not one.
    Being served through Cloudflare is not being blocked by it -- x.com's ordinary pages
    carry the challenge-platform script -- so those markers only count alongside each
    other and an empty extraction. A challenge that has grown wordy is still a challenge,
    which is why word count qualifies the weak path and not the strong one.
    """
    if _has_strong_challenge_marker(html):
        return True
    low = html.lower()
    weak = sum(1 for sign in _CHALLENGE_WEAK if sign in low)
    return weak >= 2 and extracted_words < SHELL_WORD_THRESHOLD


def _has_strong_challenge_marker(html: str) -> bool:
    low = (html or "").lower()
    return any(sign in low for sign in _CHALLENGE_STRONG)


def extract_html(html: str, url: str = "", *, via: str = "fetch") -> Document:
    # The decisive challenge markers are read off the raw body, before conversion. An
    # interstitial that the converter cannot handle -- or that arrives when node is not
    # installed at all -- would otherwise be reported as an extraction error, and an error
    # is not escalated to a browser tab, which is the one thing that clears a challenge.
    if _has_strong_challenge_marker(html):
        return Document(url=url, via=via, raw=html, status="challenge", kind="html",
                        error="the response is a bot challenge, not the page")

    result = _run_to_markdown(html, url)
    if not result.get("ok"):
        return Document(url=url, via=via, raw=html, status="error", kind="html",
                        error=str(result.get("message") or "extraction failed"))

    markdown = result.get("markdown") or ""
    words = int(result.get("words") or 0)

    if looks_like_challenge(html, words):
        return Document(url=url, via=via, raw=html, status="challenge", kind="html", words=words,
                        title=result.get("title") or "", markdown=markdown,
                        error="the response is a bot challenge, not the page")

    doc = Document(
        markdown=markdown,
        title=result.get("title") or "",
        url=url,
        via=via,
        words=words,
        kind="html",
        author=result.get("author") or "",
        published=result.get("published") or "",
        site=result.get("site") or "",
    )
    doc.raw = html
    doc.status = "ok" if words >= SHELL_WORD_THRESHOLD else "shell"
    if doc.status == "shell":
        doc.error = f"only {words} words extracted; the page probably renders client-side"
    return doc


def _run_to_markdown(html: str, url: str) -> dict:
    payload = json.dumps({"html": html, "url": url}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            ["node", str(TO_MARKDOWN)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"ok": False, "message": "node is not installed; run `setup`"}
    except subprocess.SubprocessError as e:
        return {"ok": False, "message": f"markdown conversion failed: {e}"}
    for line in (proc.stdout or "").splitlines():
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {"ok": False, "message": (proc.stderr or "no output from to_markdown.mjs").strip()[:400]}


# --- documents -------------------------------------------------------------------------


def extract_document(path: str | Path) -> Document:
    p = Path(path)
    code, out, err = _run_anydoc(p)
    if code == 0:
        text = out or ""
        if not count_words(text):
            return Document(kind="document", status="unsupported", error="the document converted to no text")
        return Document(markdown=text, title=_first_heading(text), kind="document",
                        words=count_words(text), status="ok")
    if code == 3:
        # No text layer. Hosted OCR exists but ships the document to a third party, which
        # nobody has agreed to -- so this is reported, not silently escalated.
        return Document(kind="document", status="needs_ocr", error=(err or "").strip()[:300] or "the PDF has no text layer")
    return Document(kind="document", status="unsupported", error=(err or out or "").strip()[:300] or f"anydoc exit {code}")


def _run_anydoc(path: Path) -> tuple[int, str, str]:
    if not ANYDOC.exists():
        return 1, "", "document conversion is not installed; run `setup`"
    try:
        proc = subprocess.run([str(ANYDOC), str(path)], capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return 1, "", "document conversion is not installed; run `setup`"
    except subprocess.SubprocessError as e:
        return 1, "", f"document conversion failed: {e}"
    return proc.returncode, proc.stdout, proc.stderr


def _first_heading(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s.startswith("**") and s.endswith("**") and len(s) > 4:
            return s.strip("*").strip()
    return ""


# --- output ----------------------------------------------------------------------------


def render_markdown(doc: Document, *, frontmatter: bool = True) -> str:
    body = (doc.markdown or "").rstrip() + "\n"
    if not frontmatter:
        return body
    fields = [
        ("title", doc.title),
        ("url", doc.final_url or doc.url),
        ("source_url", doc.url if doc.final_url and doc.final_url != doc.url else ""),
        ("author", doc.author),
        ("published", doc.published),
        ("site", doc.site),
    ]
    lines = ["---"]
    for key, value in fields:
        if value:
            lines.append(f'{key}: "{_yaml_scalar(value)}"')
    # Unquoted because they are machine-generated and closed: `via` is one of two words
    # and `words` is an integer, so quoting them would only add noise.
    lines.append(f"via: {doc.via}")
    lines.append(f"words: {doc.words}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


def _yaml_scalar(value: str) -> str:
    """Flatten to one line and escape the quote, so a title can never end the block early."""
    flat = " ".join(str(value).split())
    return flat.replace("\\", "\\\\").replace('"', '\\"')


def slug_for(url: str, *, max_len: int = 120) -> str:
    parsed = urlparse(url)
    parts = [parsed.netloc] + [p for p in parsed.path.split("/") if p]
    raw = "-".join(parts) or "page"
    normalised = unicodedata.normalize("NFKD", raw)
    cleaned = _SLUG_STRIP.sub("-", normalised).strip("-.")
    cleaned = re.sub(r"-{2,}", "-", cleaned) or "page"
    if len(cleaned) <= max_len:
        return cleaned
    # Keep the head, which identifies the page, and mark the truncation so two long URLs
    # sharing a prefix do not collide silently.
    import hashlib

    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[: max_len - 9].rstrip('-')}-{digest}"
