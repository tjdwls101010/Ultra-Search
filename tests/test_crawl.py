"""_crawl: choosing which URLs a crawl will visit.

Pure frontier logic -- URLs and a discovery provider in, an ordered manifest out. No
network and no browser, so depth, globs and caps are testable exactly rather than
approximately.
"""
from __future__ import annotations

import pytest

import _crawl


SITE = {
    "https://site.test/": ["https://site.test/a", "https://site.test/b", "https://other.test/x"],
    "https://site.test/a": ["https://site.test/a/1", "https://site.test/a/2", "https://site.test/"],
    "https://site.test/b": ["https://site.test/b/1"],
    "https://site.test/a/1": ["https://site.test/a/1/deep"],
    "https://site.test/a/2": [],
    "https://site.test/b/1": [],
    "https://site.test/a/1/deep": [],
}


def links_provider(pages, same_origin_as, **kw):
    out = []
    for p in pages:
        for u in SITE.get(p, []):
            out.append({"kind": "url", "url": u, "from": p})
    return out


def no_sitemap(roots, **kw):
    return [{"kind": "sitemap_miss", "url": r, "status": 404} for r in roots]


def test_depth_one_visits_only_the_root_and_its_links() -> None:
    urls = _crawl.discover("https://site.test/", depth=1, sitemap_provider=no_sitemap, links_provider=links_provider)

    assert set(urls) == {"https://site.test/", "https://site.test/a", "https://site.test/b"}


def test_depth_two_reaches_one_level_further() -> None:
    urls = _crawl.discover("https://site.test/", depth=2, sitemap_provider=no_sitemap, links_provider=links_provider)

    assert "https://site.test/a/1" in urls
    assert "https://site.test/a/1/deep" not in urls


def test_offsite_links_are_not_followed() -> None:
    urls = _crawl.discover("https://site.test/", depth=3, sitemap_provider=no_sitemap, links_provider=links_provider)

    assert not any("other.test" in u for u in urls)


def test_a_cycle_does_not_revisit() -> None:
    """site.test/a links back to the root."""
    urls = _crawl.discover("https://site.test/", depth=3, sitemap_provider=no_sitemap, links_provider=links_provider)

    assert len(urls) == len(set(urls))


def test_the_cap_is_respected() -> None:
    urls = _crawl.discover(
        "https://site.test/", depth=3, max_urls=3, sitemap_provider=no_sitemap, links_provider=links_provider
    )

    assert len(urls) == 3
    assert urls[0] == "https://site.test/"


def test_include_globs_keep_only_matches() -> None:
    urls = _crawl.discover(
        "https://site.test/", depth=3, include=["*/a/*"],
        sitemap_provider=no_sitemap, links_provider=links_provider,
    )

    assert set(urls) == {"https://site.test/a/1", "https://site.test/a/2", "https://site.test/a/1/deep"}


def test_exclude_globs_drop_matches() -> None:
    urls = _crawl.discover(
        "https://site.test/", depth=2, exclude=["*/b*"],
        sitemap_provider=no_sitemap, links_provider=links_provider,
    )

    assert not any("/b" in u for u in urls)


def test_a_filtered_out_page_is_still_walked_through() -> None:
    """A glob says which pages to keep, not which to route through. Docs sites routinely
    hang every article off an index that the glob itself would exclude."""
    urls = _crawl.discover(
        "https://site.test/", depth=3, include=["*/a/1/*"],
        sitemap_provider=no_sitemap, links_provider=links_provider,
    )

    assert urls == ["https://site.test/a/1/deep"]


def test_a_sitemap_short_circuits_link_following() -> None:
    def sitemap(roots, **kw):
        return [
            {"kind": "url", "url": "https://site.test/from-sitemap-1"},
            {"kind": "url", "url": "https://site.test/from-sitemap-2"},
            {"kind": "sitemap_done", "count": 2},
        ]

    urls = _crawl.discover("https://site.test/", depth=2, sitemap_provider=sitemap, links_provider=links_provider)

    assert "https://site.test/from-sitemap-1" in urls
    assert "https://site.test/a/1" not in urls, "a sitemap is the site's own list; walking anyway doubles the cost"


def test_sitemap_urls_are_still_filtered() -> None:
    def sitemap(roots, **kw):
        return [
            {"kind": "url", "url": "https://site.test/docs/x"},
            {"kind": "url", "url": "https://site.test/blog/y"},
        ]

    urls = _crawl.discover(
        "https://site.test/", depth=2, include=["*/docs/*"],
        sitemap_provider=sitemap, links_provider=links_provider,
    )

    assert urls == ["https://site.test/docs/x"]


def test_sitemap_candidates_cover_the_usual_locations() -> None:
    seen: list = []

    def sitemap(roots, **kw):
        seen.extend(roots)
        return []

    _crawl.discover("https://site.test/docs/guide", depth=1, sitemap_provider=sitemap, links_provider=links_provider)

    assert "https://site.test/sitemap.xml" in seen
    assert "https://site.test/robots.txt" in seen


def test_a_manifest_round_trips() -> None:
    manifest = _crawl.build_manifest(
        "https://site.test/",
        [{"url": "https://site.test/a", "path": "/tmp/a.md", "status": "ok", "title": "A", "via": "fetch", "words": 10}],
    )

    assert manifest["root"] == "https://site.test/"
    assert manifest["pages"][0]["url"] == "https://site.test/a"
    assert _crawl.urls_from_manifest(manifest) == ["https://site.test/a"]


def test_a_manifest_from_map_has_urls_but_no_files() -> None:
    manifest = _crawl.build_manifest("https://site.test/", [], urls=["https://site.test/a", "https://site.test/b"])

    assert _crawl.urls_from_manifest(manifest) == ["https://site.test/a", "https://site.test/b"]
