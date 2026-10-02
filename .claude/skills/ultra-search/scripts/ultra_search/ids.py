"""Ids that become one segment of a path, and the labels run ids are made from."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

#: Run, session and child ids each become one path segment. Starting with a letter or digit
#: and staying in this set rules out "." and ".." and any separator, so an id read from the
#: command line or from a transcript cannot name a path outside the directory it is joined to.
#: Letters are any script's: a run id carries its label, and a Korean prompt's label is Korean.
_SAFE_ID = re.compile(r"[^\W_][\w.-]{0,199}")
_LABEL_UNSAFE = re.compile(r"[^\w.-]+")


def normal(text: str) -> str:
    """One spelling for text that can be typed two ways: a Mac can hand over 한 decomposed."""
    return unicodedata.normalize("NFC", text)


def is_safe_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.fullmatch(normal(value)))


def label_for(text: str | None) -> str:
    """A label that can end a run id: only the basename, and only letters, digits and `._-`,
    since a label reaches here from the command line and would otherwise be able to name a
    directory outside the registry."""
    if not text:
        return "run"
    clean = _LABEL_UNSAFE.sub("-", Path(normal(str(text))).name).strip("-._")
    return clean[:40].rstrip("-._") or "run"
