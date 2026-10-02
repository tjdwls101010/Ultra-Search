"""`map` and `crawl`: a site's URLs, and a site saved page by page.

`map` is the cheap half: it discovers URLs and writes a manifest without fetching any
content, so a caller can look at what a site has before committing to downloading it.
`crawl --from` consumes that same manifest, which is what keeps a look-then-fetch from
walking the site twice.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from ultra_search import aside, fetch, outcome, saved
from ultra_search.outcome import ArgumentError, Reply
from ultra_search.site import discover


def _discovery(depth: int | None, max_urls: int | None) -> dict:
    """The discovery settings the caller gave; discover() supplies the rest."""
    given = {"depth": depth, "max_urls": max_urls}
    return {k: v for k, v in given.items() if v is not None}


def _links(frontier: list[str], same_origin_as: str) -> list[dict]:
    return discover.resolve_links(aside.read_links(frontier), same_origin_as)


def _providers(no_sitemap: bool) -> dict:
    return {
        "sitemap_provider": None if no_sitemap else aside.read_sitemaps,
        "links_provider": _links,
    }


def map_site(root: Path, url: str, *, depth: int | None, max_urls: int | None, include: list[str] | None,
             exclude: list[str] | None, no_sitemap: bool, out: str | None, list_all: bool) -> Reply:
    urls, coverage = discover.discover(
        url,
        **_discovery(depth, max_urls),
        include=include,
        exclude=exclude,
        use_sitemap=not no_sitemap,
        **_providers(no_sitemap),
    )
    manifest = {**discover.build_manifest(url, [], urls=urls), "coverage": coverage}
    path = Path(out).expanduser() if out else saved.new_map_file(root, _host(url))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # The list lives in the manifest; the reply is sized for reading whatever the site's size.
    reply = {"ok": True, "command": "map", "root": url, "count": len(urls), "coverage": _brief(coverage),
             "sample": urls[:SAMPLE], "manifest_path": str(path)}
    if list_all:
        reply["urls"] = urls
    # Nothing read -- no sitemap and not one page's links -- is no map at all, even when the
    # root itself is listed.
    saw_site = coverage["sitemap"] or coverage["pages_read"] > 0
    return Reply(reply, outcome.OK if urls and saw_site else outcome.EMPTY)


def crawl(root: Path, url: str | None, *, from_manifest: str | None, max_pages: int, depth: int | None,
          max_urls: int | None, include: list[str] | None, exclude: list[str] | None, no_sitemap: bool,
          via: str, concurrency: int, frontmatter: bool, out: str | None) -> Reply:
    if out:
        saved.refuse_used_folder(Path(out).expanduser())
    if from_manifest:
        given = [flag for flag, value in (("--max-urls", max_urls), ("--depth", depth),
                                          ("--include", include), ("--exclude", exclude),
                                          ("--no-sitemap", no_sitemap)) if value is not None and value is not False]
        if given:
            raise ArgumentError(
                f"{', '.join(given)} {'does' if len(given) == 1 else 'do'} not apply to --from: the manifest is crawled as it is",
                fix="Drop the flag, or run `map` again with it and crawl that manifest.",
            )
        source = Path(from_manifest).expanduser()
        try:
            manifest = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ArgumentError(f"could not read manifest {source}: {e}", fix="Produce one with `map --out`.") from e
        urls = discover.urls_from_manifest(manifest)
        if urls is None:
            raise ArgumentError(f"{source} is not a manifest written by `map` or `crawl`",
                                fix="Produce one with `map --out`.")
        site = manifest.get("root") or ""
        coverage = None
        if not urls:
            raise ArgumentError(f"manifest {source} lists no URLs", fix="Re-run `map` with wider filters.")
    else:
        site = url
        urls, coverage = discover.discover(
            site,
            **_discovery(depth, max_urls),
            include=include,
            exclude=exclude,
            use_sitemap=not no_sitemap,
            **_providers(no_sitemap),
        )

    urls = urls[:max_pages]
    if out:
        out_dir = Path(out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = saved.new_crawl_dir(root, _host(site))

    envelope = fetch.fetch_urls(
        urls,
        out_dir=out_dir,
        via=via,
        frontmatter=frontmatter,
        concurrency=concurrency,
        numbered=True,
    )
    items = envelope["items"]
    manifest = discover.build_manifest(site, items)
    if coverage is not None:
        manifest["coverage"] = coverage
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Counts and the first of what went wrong; every page's record is in the manifest.
    not_ok = [i for i in items if i["status"] != "ok"]
    statuses: dict[str, int] = {}
    for i in items:
        statuses[i["status"]] = statuses.get(i["status"], 0) + 1
    return Reply(
        {
            "ok": True,
            "command": "crawl",
            "root": site,
            "out_dir": str(out_dir),
            "manifest": str(manifest_path),
            "requested": len(urls),
            "saved": statuses.get("ok", 0),
            "statuses": statuses,
            "not_ok_count": len(not_ok),
            "not_ok": [{k: i[k] for k in ("url", "status", "http_status", "error", "path") if i.get(k) is not None}
                       for i in not_ok[:SAMPLE]],
            **({"coverage": _brief(coverage)} if coverage is not None else {}),
        },
        fetch.outcome_for(items),
    )


#: How many URLs a map's reply shows before pointing at its manifest.
SAMPLE = 10


def _brief(coverage: dict) -> dict:
    """Coverage sized for a reply: how many pages were missed, and the first of them."""
    missed = coverage["pages_missed"]
    return {**coverage, "pages_missed_count": len(missed), "pages_missed": missed[:SAMPLE]}


def _host(url: str) -> str:
    return urlparse(url).netloc or "site"
