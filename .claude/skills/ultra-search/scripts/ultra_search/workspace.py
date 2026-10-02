"""Where the skill keeps what it makes: `.ultra-search/` in the working directory.

Not the skill's own folder. The skill is loaded globally and several projects' sessions run
at once, so each project keeps its own runs -- which is what keeps a bare `status` or
`result` to that project's most recent run -- and what it saves has to be readable with
Read, which refuses files inside an installed skill folder.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_DIRNAME = ".ultra-search"


def default_root() -> Path:
    return Path.cwd() / DEFAULT_DIRNAME


def ensure(root: Path) -> None:
    """Create ``root``; when it is the default store, also a .gitignore that keeps it out of git.

    The default store lands in whatever project the caller happens to be in, and its runs and
    pages are the user's, not that project's. A place the caller chose is left as it is, and
    a .gitignore already there is the user's to keep.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        default = root.resolve() == default_root().resolve()
    except OSError:
        default = False
    ignore = root / ".gitignore"
    if default and not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
