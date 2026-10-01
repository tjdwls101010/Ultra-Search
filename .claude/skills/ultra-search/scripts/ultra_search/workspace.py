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
