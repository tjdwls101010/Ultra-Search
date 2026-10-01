"""Whole sites: `map` lists a site's URLs, `crawl` saves its pages -- page by page through `fetch`."""
from ultra_search.site.commands import crawl, map_site

__all__ = ["crawl", "map_site"]
