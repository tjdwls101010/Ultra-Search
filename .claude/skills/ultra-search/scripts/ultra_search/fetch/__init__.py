"""Reading known pages through the user's browser into files: `fetch`, and the page acquisition `crawl` is built from."""
from ultra_search.fetch.acquire import fetch_urls
from ultra_search.fetch.commands import exit_code_for, fetch

__all__ = ["exit_code_for", "fetch", "fetch_urls"]
