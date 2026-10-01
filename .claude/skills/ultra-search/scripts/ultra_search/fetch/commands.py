"""`fetch`: each page saved to a file and reported by where it went, never its text unless asked.

A fetch of ten pages that returned them would put ten pages into the caller's context as a
side effect of being told where they are.
"""
from __future__ import annotations

import json
from pathlib import Path

from ultra_search import outcome, saved
from ultra_search.fetch import acquire
from ultra_search.outcome import ArgumentError


def fetch(root: Path, urls: list[str], *, out: str | None, fmt: str, via: str, concurrency: int,
          frontmatter: bool, print_content: bool, max_chars: int) -> int:
    out_file, out_dir = _destinations(urls, out, root)
    envelope = acquire.fetch_urls(
        urls,
        out_dir=out_dir,
        out_file=out_file,
        via=via,
        fmt=fmt,
        frontmatter=frontmatter,
        print_content=print_content,
        max_chars=max_chars,
        concurrency=concurrency,
    )
    print(json.dumps(envelope, ensure_ascii=False))
    return exit_code_for(envelope["items"])


def _destinations(urls: list[str], out: str | None, root: Path) -> tuple[Path | None, Path]:
    """Split --out into a file destination or a directory one.

    A path is a file only when it looks like one -- an existing file, or a name with an
    extension. Anything else is a directory, because `--out ./notes` for one URL means a
    folder to everyone who types it, and silently producing an extensionless file named
    `notes` is the kind of surprise nobody checks for.
    """
    if not out:
        return None, saved.pages_dir(root)
    p = Path(out).expanduser()
    looks_like_file = p.is_file() or (bool(p.suffix) and not p.is_dir() and not out.endswith("/"))
    if looks_like_file:
        if len(urls) > 1:
            raise ArgumentError(
                f"--out {out!r} names a file but {len(urls)} URLs were given",
                fix="Pass a directory for several URLs, or fetch them one at a time.",
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, p.parent
    p.mkdir(parents=True, exist_ok=True)
    return None, p


def exit_code_for(items: list[dict]) -> int:
    """0 when anything was saved. The status still says what each page turned out to be:
    `--format html` writes a client-rendered document that has no article in it."""
    if not items:
        return outcome.EXIT_EMPTY
    if any(i["status"] == "ok" or i.get("path") for i in items):
        return 0
    return outcome.EXIT_RUN_FAILED
