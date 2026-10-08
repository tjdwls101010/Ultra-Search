"""Hancom's word-processor formats, which someone else owns: HWP 5.0, an OLE compound file of compressed binary records, and HWPX, a zip of XML. Korean public bodies publish much of what they say in these, and the document converter reads neither. When Hancom changes a format, this is where the fix goes."""
from __future__ import annotations

import os

__all__ = ["extract"]


def extract(path: str | os.PathLike[str]) -> dict | None:
    return None
