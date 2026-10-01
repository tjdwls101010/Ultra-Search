"""Ids that become one segment of a path, and the labels run ids are made from."""
from __future__ import annotations

import re
from pathlib import Path

#: Run, session and child ids each become one path segment. Starting with a letter or digit
#: and staying in this set rules out "." and ".." and any separator, so an id read from the
#: command line or from a transcript cannot name a path outside the directory it is joined to.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_LABEL_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def is_safe_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))


def label_for(text: str | None) -> str:
    """A label that can end a run id: only the basename, and only safe characters, since a
    label reaches here from the command line and would otherwise be able to name a directory
    outside the registry."""
    if not text:
        return "run"
    clean = _LABEL_SAFE.sub("-", Path(str(text)).name).strip("-.")
    return clean[:40] or "run"
