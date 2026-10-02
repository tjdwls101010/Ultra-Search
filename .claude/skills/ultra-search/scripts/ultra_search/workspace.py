"""Where the skill keeps what it makes: `.ultra-search/` in the working directory.

Not the skill's own folder. The skill is loaded globally and several projects' sessions run
at once, so each project keeps its own runs -- which is what keeps a bare `status` or
`result` to that project's most recent run -- and what it saves has to be readable with
Read, which refuses files inside an installed skill folder.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_DIRNAME = ".ultra-search"
#: The store this command is using, when it is the default one; None when the caller chose one.
_in_use: Path | None = None


def default_root() -> Path:
    return Path.cwd() / DEFAULT_DIRNAME


def root_for(chosen: str | None) -> Path:
    """The store a command uses: the one the caller chose, or the default. A default store that
    already exists -- one an earlier version made -- gets its .gitignore now."""
    global _in_use
    if chosen:
        _in_use = None
        return Path(chosen).expanduser().resolve()
    _in_use = default_root()
    if _in_use.is_dir():
        ensure(_in_use)
    return _in_use


def ensure(root: Path) -> None:
    """Create ``root``; when it is the default store, also a .gitignore that keeps it out of git.

    The default store lands in whatever project the caller happens to be in, and its runs and
    pages are the user's, not that project's. A place the caller chose is left as it is, and
    a .gitignore already there is the user's to keep.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if _in_use is not None and root == _in_use and not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
