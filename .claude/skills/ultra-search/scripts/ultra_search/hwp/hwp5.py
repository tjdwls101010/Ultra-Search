"""HWP 5.0: an OLE compound file whose `FileHeader` names the format and its locks, and whose `BodyText/Section<N>` streams hold the body as records -- raw-deflated unless the header says otherwise.

Each paragraph's characters are one `PARA_TEXT` record of UTF-16LE code units, in which a code unit below 32 is a control: some take one unit, the rest eight, and a tab, a line break, a hyphen and the two kinds of fixed-width space are text a reader needs -- dropping them runs words together, `사건2018헌바130`.
"""
from __future__ import annotations

import io
import os
import zlib
from pathlib import Path

import olefile

EXT = "hwp"
SIGNATURE = b"HWP Document File"
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PARA_TEXT = 67
#: Controls eight code units wide: the inline ones (a tab among them) and the extended ones (a table, a footnote, a field). Every other control below 32 is one unit wide.
_EIGHT = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23})
#: What a control means as text; any other is dropped.
_AS_TEXT = {9: "\t", 10: "\n", 24: "-", 30: " ", 31: " "}
#: Past this much decompressed body the file is refused: it came from the web, and a deflate stream can expand without bound.
_MAX_BODY = 256 << 20


def text_of(path: str | os.PathLike[str]) -> str | None:
    """The body's paragraphs, a blank line between each; None when the file is not HWP 5.0. Raises once it is one: ValueError for a lock or a damaged body, whatever olefile or zlib raise for a damaged container."""
    data = Path(path).read_bytes()
    if not data.startswith(_OLE):
        return None
    try:
        # A truncated container is an error here, not a defect to read past: olefile would hand back short streams.
        ole = olefile.OleFileIO(io.BytesIO(data), raise_defects=olefile.DEFECT_INCORRECT)
    except Exception:
        if _signed(data):
            raise
        return None
    with ole:
        header = ole.openstream("FileHeader").read() if ole.exists("FileHeader") else b""
        if not header.startswith(SIGNATURE):
            return None
        flags = int.from_bytes(header[36:40], "little")
        if flags & 2:
            raise ValueError("password-protected HWP")
        if flags & 4:
            raise ValueError("distribution-protected HWP")
        sections = sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
                          key=lambda e: int(e[1][len("Section"):]))
        if not sections:
            raise ValueError("the HWP file has no body")
        paragraphs: list[str] = []
        left = _MAX_BODY
        for entry in sections:
            raw = ole.openstream(entry).read()
            body = _inflate(raw, left) if flags & 1 else raw
            left -= len(body)
            if left < 0:
                raise ValueError(f"the HWP body is larger than {_MAX_BODY >> 20} MB")
            paragraphs += [p for p in (_paragraph(r) for r in _records(body, _PARA_TEXT)) if p.strip()]
    return "\n\n".join(paragraphs)


def _signed(data: bytes) -> bool:
    """Whether bytes olefile cannot open still hold the HWP signature where a small stream's data starts: a copy too damaged to read is still known for what it is."""
    return any(data.startswith(SIGNATURE, i) for i in range(0, len(data), 64))


def _inflate(raw: bytes, limit: int) -> bytes:
    d = zlib.decompressobj(-15)
    body = d.decompress(raw, max(limit, 0) + 1)
    if d.unconsumed_tail or len(body) > limit:
        raise ValueError(f"the HWP body is larger than {_MAX_BODY >> 20} MB")
    if not d.eof:
        # A deflate stream cut short inflates to its first part without complaint.
        raise ValueError("the HWP body is cut short")
    return body


def _records(body: bytes, tag: int):
    """Each record's data with this tag. A record's header packs tag, nesting level and size into four bytes, the size spilling into four more when it is 0xFFF."""
    i = 0
    while i + 4 <= len(body):
        head = int.from_bytes(body[i:i + 4], "little")
        i += 4
        size = head >> 20
        if size == 0xFFF:
            size = int.from_bytes(body[i:i + 4], "little")
            i += 4
        if i + size > len(body):
            raise ValueError("the HWP body ends inside a record")
        if head & 0x3FF == tag:
            yield body[i:i + size]
        i += size
    if i != len(body):
        raise ValueError("the HWP body ends inside a record")


def _paragraph(units: bytes) -> str:
    """A paragraph's text: plain stretches decoded whole, so a character outside the BMP keeps both halves, and each control replaced by the text it stands for."""
    if len(units) % 2:
        raise ValueError("an HWP paragraph ends inside a character")
    out: list[str] = []
    start = i = 0
    end = len(units)
    while i < end:
        code = units[i] | units[i + 1] << 8
        if code >= 32:
            i += 2
            continue
        out.append(units[start:i].decode("utf-16-le", "replace"))
        out.append(_AS_TEXT.get(code, ""))
        i += 16 if code in _EIGHT else 2
        if i > end:
            raise ValueError("an HWP paragraph ends inside a control")
        start = i
    out.append(units[start:end].decode("utf-16-le", "replace"))
    return "".join(out).rstrip()
