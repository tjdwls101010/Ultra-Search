"""The page snippets, called in the user's browser: fetching, opening a tab, reading sitemaps and links.

Each returns the snippet's records as it printed them, in order. A snippet the daemon killed
at its 120-second limit still returns what it printed before that, closed by the record that
says its budget ran out, so a caller sees a partial answer as partial.
"""
from __future__ import annotations

import re

from ultra_search.aside import repl

#: The daemon kills a snippet at 120 seconds. Everything a snippet does is budgeted below that.
#: Room to print what already succeeded before the kill lands.
DEFAULT_BUDGET_MS = 105_000
DEFAULT_PER_URL_MS = 20_000
TAB_WAIT_MS = 45_000


def fetch_pages(urls: list[str], *, per_url_ms: int = DEFAULT_PER_URL_MS,
                budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    """Fetch a batch; non-text responses are written to the browser session directory.

    Where downloads land is not the caller's choice: the sandbox refuses writes outside the
    project and session roots. The caller gets the path back and copies the file itself.
    """
    args = {"urls": list(urls), "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms}
    try:
        return repl.run_snippet("fetch_batch.js", args)
    except repl.ReplTimeout as e:
        return e.lines


def open_tab(url: str, *, wait_ms: int = TAB_WAIT_MS, settle_ms: int = 700) -> list[dict]:
    try:
        return repl.run_snippet("tab_one.js", {"url": url, "waitMs": wait_ms, "settleMs": settle_ms})
    except repl.ReplTimeout as e:
        return e.lines


def read_sitemaps(roots: list[str], *, per_url_ms: int = DEFAULT_PER_URL_MS,
                  budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    try:
        return repl.run_snippet("sitemap.js", {"roots": roots, "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms})
    except repl.ReplTimeout as e:
        # What it printed is kept; that the list stops short is said, as the budget would.
        return e.lines + [{"kind": "sitemap_done", "hit_budget": True}]


def read_links(pages: list[str], *, per_url_ms: int = DEFAULT_PER_URL_MS,
               budget_ms: int = DEFAULT_BUDGET_MS) -> list[dict]:
    """The href attributes of a set of pages, decoded into the URLs they spell, unresolved.

    The browser sandbox has no URL constructor, so joining an href to its page and deciding
    which site it is on happen in the caller, where that can be tested.
    """
    args = {"pages": pages, "perUrlTimeoutMs": per_url_ms, "budgetMs": budget_ms}
    try:
        records = repl.run_snippet("links.js", args)
    except repl.ReplTimeout as e:
        records = e.lines + [{"kind": "links_done", "hit_budget": True}]
    for rec in records:
        if rec.get("kind") == "hrefs":
            # An href is an HTML attribute: `&amp;` in it is one `&` of the URL.
            rec["hrefs"] = [_decode_attribute(h) for h in rec.get("hrefs") or []]
    return records


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
