"""Choosing which URLs a crawl will visit.

Pure: URLs and two discovery providers in, an ordered list out. Keeping the network on
the other side of a provider is what makes depth, globs and caps testable exactly.

A sitemap, when there is one, replaces link-following rather than adding to it -- it is
the site's own list of its pages, so walking the links as well pays twice for the same
answer. Filters still apply to it, because "what the site has" and "what the caller asked
for" are different questions.
"""
from __future__ import annotations

import fnmatch
from urllib.parse import urldefrag, urlparse, urlunparse

DEFAULT_DEPTH = 2
DEFAULT_MAX_URLS = 200


def normalise(url: str) -> str:
    """Drop the fragment and a trailing empty query so one page is not crawled twice."""
    clean, _ = urldefrag(url)
    parsed = urlparse(clean)
    path = parsed.path or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))


def origin(url: str) -> tuple[str, str, int] | None:
    """Scheme, host and port of a web URL; None for anything that is not http(s).

    The host name alone is not a site: http: and https: of one host, or two ports, can be
    different servers, and a crawl acting as the user should not wander onto either.
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
    except ValueError:
        return None
    return p.scheme, p.hostname.lower(), port


def sitemap_candidates(root: str) -> list[str]:
    p = urlparse(root)
    base = f"{p.scheme}://{p.netloc}"
    return [f"{base}/sitemap.xml", f"{base}/sitemap_index.xml", f"{base}/robots.txt"]


def matches(url: str, include: list[str] | None, exclude: list[str] | None) -> bool:
    if exclude and any(fnmatch.fnmatch(url, pat) for pat in exclude):
        return False
    if include:
        return any(fnmatch.fnmatch(url, pat) for pat in include)
    return True


def discover(
    root: str,
    *,
    depth: int = DEFAULT_DEPTH,
    max_urls: int = DEFAULT_MAX_URLS,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    use_sitemap: bool = True,
    sitemap_provider=None,
    links_provider=None,
) -> tuple[list[str], dict]:
    """The URLs to visit, and how much of the site was actually seen to choose them.

    The coverage is half the answer: a map that could not read half the site's pages looks
    exactly like a small site unless it says so.
    """
    root = normalise(root)
    site = origin(root)
    coverage = {"sitemap": False, "pages_read": 0, "pages_missed": [],
                "budget_exhausted": False, "max_urls_reached": False}

    def done(urls: list[str]) -> tuple[list[str], dict]:
        coverage["max_urls_reached"] = len(urls) > max_urls or coverage["max_urls_reached"]
        return urls[:max_urls], coverage

    if use_sitemap and sitemap_provider:
        found = [
            normalise(r["url"])
            for r in sitemap_provider(sitemap_candidates(root))
            if r.get("kind") == "url" and r.get("url")
        ]
        same_site = [u for u in found if origin(u) == site]
        if same_site:
            coverage["sitemap"] = True
            return done([u for u in _dedupe(same_site) if matches(u, include, exclude)])

    if not links_provider:
        return done([root] if matches(root, include, exclude) else [])

    # Breadth-first, and the frontier is walked whether or not a page passes the filters:
    # a glob selects what to keep, and docs sites routinely reach every article through an
    # index page the glob itself excludes.
    seen = {root}
    frontier = [root]
    kept: list[str] = []
    if matches(root, include, exclude):
        kept.append(root)

    # `depth` counts rounds of link-following, so depth=1 is the root plus what it links to.
    for _ in range(max(0, depth)):
        if not frontier or len(kept) >= max_urls:
            break
        found = links_provider(frontier, same_origin_as=root)
        frontier = []
        for record in found:
            kind = record.get("kind")
            if kind == "page_read":
                coverage["pages_read"] += 1
            elif kind == "link_miss":
                coverage["pages_missed"].append(
                    {k: record[k] for k in ("url", "status", "error") if record.get(k) is not None})
            elif kind == "links_done" and record.get("hit_budget"):
                coverage["budget_exhausted"] = True
            if kind != "url" or not record.get("url"):
                continue
            u = normalise(record["url"])
            if u in seen or origin(u) != site:
                continue
            seen.add(u)
            frontier.append(u)
            if matches(u, include, exclude):
                kept.append(u)
                if len(kept) >= max_urls:
                    coverage["max_urls_reached"] = True
                    break
    return done(kept)


def _dedupe(seq: list[str]) -> list[str]:
    out: list[str] = []
    for s in seq:
        if s not in out:
            out.append(s)
    return out


def build_manifest(root: str, pages: list[dict], urls: list[str] | None = None) -> dict:
    """The record of what a crawl or map found.

    `map` writes one with urls and no files; `crawl --from` reads either, which is what
    lets a caller look before deciding to fetch without paying for discovery twice.
    """
    manifest = {"root": root, "pages": []}
    for i, p in enumerate(pages):
        manifest["pages"].append(
            {
                "n": i,
                "url": p.get("url"),
                "final_url": p.get("final_url") or p.get("url"),
                "file": p.get("path"),
                "title": p.get("title") or "",
                "status": p.get("status"),
                "via": p.get("via"),
                "words": p.get("words", 0),
                "depth": p.get("depth"),
            }
        )
    if urls is not None:
        manifest["urls"] = list(urls)
    manifest["count"] = len(manifest["pages"]) or len(manifest.get("urls") or [])
    return manifest


def urls_from_manifest(manifest: object) -> list[str] | None:
    """The URLs a manifest lists, or None when it is not shaped like one `map` or `crawl` wrote."""
    if not isinstance(manifest, dict):
        return None
    pages, urls = manifest.get("pages"), manifest.get("urls")
    if pages:
        if not isinstance(pages, list) or not all(
            isinstance(p, dict) and isinstance(p.get("url") or "", str) for p in pages
        ):
            return None
        return [p["url"] for p in pages if p.get("url")]
    if urls is None:
        return []
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        return None
    return list(urls)
