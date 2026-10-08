"""Hancom's word-processor formats, which someone else owns: HWP 5.0, an OLE compound file of compressed binary records, and HWPX, a zip of XML. Korean public bodies publish much of what they say in these, and the document converter reads neither. When Hancom changes a format, this is where the fix goes."""
from __future__ import annotations

import os

from ultra_search.hwp import hwp5, hwpx

__all__ = ["extract"]


def extract(path: str | os.PathLike[str]) -> dict | None:
    """The text of an HWP or HWPX file, or None when the file is neither -- told by its content, never its name or MIME type, which servers give as anything from application/x-hwp to application/x-msdownload.

    A recognised file answers {"status", "text", "error", "ext"}: "ok" with its paragraphs, or "unsupported" with why -- a password or distribution lock, or damage. This never raises: a damaged document is one item's status, not a failed fetch.
    """
    for unit in (hwp5, hwpx):
        try:
            text = unit.text_of(path)
        except ValueError as e:
            return {"status": "unsupported", "text": "", "error": str(e), "ext": unit.EXT}
        except Exception as e:  # noqa: BLE001 - past recognition, any failure is damage the format's reader did not foresee
            return {"status": "unsupported", "text": "", "ext": unit.EXT,
                    "error": f"the {unit.EXT.upper()} file could not be read: {type(e).__name__}: {e}"}
        if text is not None:
            return {"status": "ok", "text": text, "error": None, "ext": unit.EXT}
    return None
