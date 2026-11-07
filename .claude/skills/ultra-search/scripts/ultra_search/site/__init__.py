"""Whole sites: `map` lists a site's URLs, `crawl` saves its pages -- page by page through `fetch`."""
from ultra_search.site.commands import DEFAULT_MAX_PAGES, crawl, map_site

__all__ = ["DEFAULT_MAX_PAGES", "crawl", "map_site"]
