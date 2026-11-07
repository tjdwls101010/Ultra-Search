"""Whole sites: `map` lists a site's URLs, `crawl` saves its pages -- page by page through `fetch`."""
from ultra_search.site.commands import DEFAULT_MAX_PAGES, crawl, map_site
from ultra_search.site.discover import DEFAULT_DEPTH, DEFAULT_MAX_URLS

__all__ = ["DEFAULT_DEPTH", "DEFAULT_MAX_PAGES", "DEFAULT_MAX_URLS", "crawl", "map_site"]
