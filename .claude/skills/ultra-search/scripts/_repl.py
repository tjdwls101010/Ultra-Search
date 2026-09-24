"""Running a JavaScript snippet in the user's browser and reading back NDJSON.

Snippets live as real .js files rather than strings so they stay readable and editable,
and receive their arguments through a prepended `ARGS` constant -- the code goes over
argv, where interpolating values into the source would be a quoting bug waiting to happen.

The one thing worth knowing: a snippet that runs past 120 seconds is killed, and the
daemon reports that as "fetch failed: other side closed / Aside daemon is not reachable".
The daemon is fine. Taking that message at face value sends a caller to restart an app
that was never broken, so it is translated here into what actually happened.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from _errors import AsideUnavailable
from _exec import aside_bin

SNIPPETS = Path(__file__).resolve().parent / "page" / "snippets"

#: The daemon kills a snippet here. Everything a snippet does is budgeted below this.
REPL_HARD_LIMIT = 120.0
#: Room to print what already succeeded before the kill lands.
DEFAULT_BUDGET_MS = 105_000
DEFAULT_PER_URL_MS = 20_000
TAB_WAIT_MS = 45_000

_TIMEOUT_SIGNS = ("other side closed", "daemon is not reachable", "fetch failed")


class ReplTimeout(Exception):
    """The snippet was killed at the 120s limit. Partial output is still usable."""

    def __init__(self, lines: list[dict]) -> None:
        super().__init__("repl snippet exceeded the 120s limit")
        self.lines = lines


def load_snippet(name: str) -> str:
    path = SNIPPETS / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise AsideUnavailable(f"missing repl snippet {name}", fix=f"Reinstall the skill; expected {path}") from e


def build_code(name: str, args: dict) -> str:
    return f"const ARGS = {json.dumps(args, ensure_ascii=False)};\n{load_snippet(name)}"


def run_snippet(name: str, args: dict, *, timeout: float = REPL_HARD_LIMIT + 15) -> list[dict]:
    """Run a snippet and return the JSON objects it printed, in order.

    Partial output survives a timeout on purpose: the snippets print each result as it
    lands precisely so that a batch cut short still yields the URLs that finished.
    """
    code = build_code(name, args)
    try:
        proc = subprocess.run(
            [aside_bin(), "repl", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ReplTimeout(_parse_ndjson(_text(e.stdout))) from e
    except OSError as e:
        raise AsideUnavailable(f"could not run `aside repl`: {e}") from e

    lines = _parse_ndjson(proc.stdout)
    if proc.returncode != 0:
        blob = f"{proc.stdout}\n{proc.stderr}".lower()
        if any(sign in blob for sign in _TIMEOUT_SIGNS):
            # The message names the daemon, but the daemon is running: this is the 120s
            # snippet kill wearing a misleading label.
            raise ReplTimeout(lines)
        raise AsideUnavailable(
            f"`aside repl` failed: {(proc.stderr or proc.stdout or '').strip()[:400]}",
            fix="Check the Aside app is running, then re-run `doctor`.",
        )
    return lines


def _text(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def _parse_ndjson(stdout: str) -> list[dict]:
    out: list[dict] = []
    for line in _text(stdout).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def fetch_batch(urls: list[str], *, save_dir: str | os.PathLike[str] | None = None,
                per_url_ms: int = DEFAULT_PER_URL_MS, budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    """Fetch a batch; non-text responses are written to the browser session directory.

    `save_dir` is accepted and ignored: the sandbox refuses writes outside the project and
    session roots, so where downloads land is not the caller's choice. The caller gets the
    path back and copies the file wherever it wants.
    """
    args = {"urls": list(urls), "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms}
    try:
        return run_snippet("fetch_batch.js", args)
    except ReplTimeout as e:
        return e.lines


def tab_one(url: str, *, wait_ms: int = TAB_WAIT_MS, settle_ms: int = 700) -> list[dict]:
    try:
        return run_snippet("tab_one.js", {"url": url, "waitMs": wait_ms, "settleMs": settle_ms})
    except ReplTimeout as e:
        return e.lines


def sitemap(roots: list[str], *, per_url_ms: int = DEFAULT_PER_URL_MS,
            budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    try:
        return run_snippet("sitemap.js", {"roots": roots, "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms})
    except ReplTimeout as e:
        # What it printed is kept; that the list stops short is said, as the budget would.
        return e.lines + [{"kind": "sitemap_done", "hit_budget": True}]


def links(pages: list[str], same_origin_as: str, *, per_url_ms: int = DEFAULT_PER_URL_MS,
          budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    """Same-origin links from a set of pages.

    The snippet returns raw href strings; joining and origin-filtering happen here,
    because the browser sandbox has no URL constructor and hand-rolling one there would
    put the trickiest part of crawling somewhere it cannot be tested.
    """
    args = {"pages": pages, "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms}
    try:
        records = run_snippet("links.js", args)
    except ReplTimeout as e:
        records = e.lines + [{"kind": "links_done", "hit_budget": True}]
    return resolve_links(records, same_origin_as)


_REFERENCE = re.compile(r"&(?:#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[A-Za-z][A-Za-z0-9]*;?)")


def _decode_attribute(value: str) -> str:
    """Character references in an attribute value, decoded the way a browser does.

    Numeric references always decode, and so does a known name closed by its semicolon. A
    name without one decodes as its longest known prefix -- unless "=" or an ASCII letter or
    digit follows that prefix, when it is literal text: `?a=1&copy=2` keeps its `&copy`,
    `&notebook` its `&not`.
    """
    import html
    from html.entities import html5

    def sub(m: re.Match[str]) -> str:
        ref = m.group(0)
        if ref.startswith("&#") or (ref.endswith(";") and ref[1:] in html5):
            return html.unescape(ref)
        name = next((ref[1:k] for k in range(len(ref), 1, -1) if ref[1:k] in html5), None)
        if name is None:
            return ref
        after = (ref[len(name) + 1:] or value[m.end():m.end() + 1])[:1]
        if after == "=" or (after.isascii() and after.isalnum()):
            return ref
        return html5[name] + ref[len(name) + 1:]

    return _REFERENCE.sub(sub, value)


def resolve_links(records: list[dict], same_origin_as: str) -> list[dict]:
    from urllib.parse import urljoin, urldefrag

    from _crawl import origin as origin_of

    origin = origin_of(same_origin_as)
    out: list[dict] = []
    seen: set[str] = set()
    for rec in records:
        if rec.get("kind") != "hrefs":
            if rec.get("kind") in ("link_miss", "links_done"):
                out.append(rec)
            continue
        base = rec.get("final_url") or rec.get("url") or same_origin_as
        # A page with no usable links was still read; saying so is what separates it from
        # a page that could not be fetched at all.
        out.append({"kind": "page_read", "url": rec.get("url")})
        for href in rec.get("hrefs") or []:
            # An href is an HTML attribute: `&amp;` in it is one `&` of the URL.
            href = _decode_attribute(href)
            if href.lower().startswith(("javascript:", "mailto:", "tel:", "data:")):
                continue
            try:
                absolute, _ = urldefrag(urljoin(base, href))
            except ValueError:
                # One malformed href (an unclosed IPv6 bracket) is one link lost, not the page.
                continue
            if origin_of(absolute) != origin or absolute in seen:
                continue
            seen.add(absolute)
            out.append({"kind": "url", "url": absolute, "from": rec.get("url")})
    return out


def cleanup_tabs(urls: list[str]) -> list[dict]:
    try:
        return run_snippet("cleanup_tabs.js", {"urls": list(urls)}, timeout=60)
    except (ReplTimeout, AsideUnavailable):
        # Best-effort sweep of tabs an earlier timeout may have left open. Failing here
        # must never fail the fetch whose content is already in hand.
        return []
