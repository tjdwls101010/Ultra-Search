"""Where the skill keeps what it makes: `.ultra-search/` in the working directory.

Not the skill's own folder. The skill is loaded globally and several projects' sessions run
at once, so each project keeps its own runs -- which is what keeps a bare `result` or
`log` to that project's most recent run -- and what it saves has to be readable with
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
    """The store a command uses: the one the caller chose, or the default. Choosing writes nothing."""
    global _in_use
    if chosen:
        _in_use = None
        return Path(chosen).expanduser().resolve()
    _in_use = default_root()
    return _in_use


def ensure(root: Path) -> None:
    """Create ``root`` for a write; when it is the default store, also a .gitignore that keeps it
    out of git.

    The default store lands in whatever project the caller happens to be in, and its runs and
    pages are the user's, not that project's. A place the caller chose is left as it is, and
    a .gitignore already there is the user's to keep. The .gitignore never fails the write it
    comes with: a store that cannot take one is still the user's store.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    mark_written(root)


def mark_written(root: Path) -> None:
    """Called where something is written into an existing store, so a default store an earlier
    version made gets its .gitignore at its next write."""
    if _in_use is None or Path(root) != _in_use:
        return
    ignore = Path(root) / ".gitignore"
    try:
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
    except OSError:
        pass
