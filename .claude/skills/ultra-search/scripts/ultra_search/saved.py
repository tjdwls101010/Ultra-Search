"""Where saved pages, maps and crawls go under `<root>`, and names that do not replace each other.

A page saved twice, a map of the same site an hour later, a second crawl: each gets its own
name, because the earlier one may be what an answer already cites.
"""
from __future__ import annotations

import time
from pathlib import Path

from ultra_search.outcome import ArgumentError

PAGES_SUBDIR = "pages"
MAPS_SUBDIR = "maps"
CRAWLS_SUBDIR = "crawls"


def pages_dir(root: Path) -> Path:
    d = Path(root) / PAGES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_map_file(root: Path, host: str) -> Path:
    """A file name nobody holds yet, reserved by creating it: maps/<host>-<timestamp>.json."""
    folder = Path(root) / MAPS_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d-%H%M%S")
    for n in range(1, 100):
        path = folder / (f"{host}-{stamp}.json" if n == 1 else f"{host}-{stamp}-{n}.json")
        try:
            path.open("x").close()
            return path
        except FileExistsError:
            continue
    raise ArgumentError(f"could not reserve a file under {folder}", fix="Pass one with --out.")


def new_crawl_dir(root: Path, host: str) -> Path:
    """A new folder per crawl under crawls/<host>/, reserved before anything is written."""
    base = Path(root) / CRAWLS_SUBDIR / host
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d-%H%M%S")
    for n in range(1, 100):
        out = base / (stamp if n == 1 else f"{stamp}-{n}")
        try:
            out.mkdir()
            return out
        except FileExistsError:
            continue
    raise ArgumentError(f"could not reserve a crawl folder under {base}", fix="Pass one with --out.")


def refuse_used_folder(out: Path) -> None:
    """A crawl's numbered names repeat from one crawl to the next, so a folder that already
    holds files -- an earlier crawl's, or anyone's -- would have them replaced in place."""
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ArgumentError(
            f"--out {out} already holds files",
            fix="Pass an empty or new folder with --out; a crawl never writes over earlier pages.",
        )


def unique_path(dest: Path, stem: str, used: set[str], ext: str) -> Path:
    """``dest/<stem><ext>``, suffixed until no file and no earlier name in ``used`` holds it.

    Slugs flatten punctuation, so /a/b and /a-b arrive here identical; suffixing keeps the
    second page instead of silently replacing the first.
    """
    # 성진: 이름은 쓰기 직전에 있는 파일만 피한다(검사 후 쓰기, 원자적 예약 아님); 같은 폴더에 동시에 fetch하는 일이 생기면 O_EXCL로 예약한다.
    name = stem
    n = 2
    while name in used or (dest / f"{name}{ext}").exists():
        name = f"{stem}-{n}"
        n += 1
    used.add(name)
    return dest / f"{name}{ext}"
