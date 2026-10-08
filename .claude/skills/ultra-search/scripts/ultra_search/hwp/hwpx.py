"""HWPX: a zip that opens with an uncompressed `mimetype` entry reading application/hwp+zip, and holds the body as `Contents/section<N>.xml`.

A paragraph's text is its runs' `t` elements, with a tab, a line break and fixed-width spaces as child elements. A table sits inside a run of the paragraph that anchors it, its cells holding paragraphs of their own -- so the table is read as rows, one line each, cells between ` | `, and its paragraphs are not read again as the anchor's.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

EXT = "hwpx"
MIMETYPE = b"application/hwp+zip"
_HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
_SECTION = re.compile(r"Contents/section(\d+)\.xml")
_AS_TEXT = {f"{_HP}tab": "\t", f"{_HP}lineBreak": "\n", f"{_HP}fwSpace": " ", f"{_HP}nbSpace": " ", f"{_HP}hyphen": "-"}
#: Past this much uncompressed body the file is refused: it came from the web, and a zip entry can expand without bound.
_MAX_BODY = 256 << 20


def text_of(path: str | os.PathLike[str]) -> str | None:
    """The body's paragraphs and table rows, a blank line between paragraphs; None when the file is not HWPX. Raises once it is one: ValueError for a missing or oversized body, whatever zipfile or the XML parser raise for damage."""
    data = Path(path).read_bytes()
    if not (data.startswith(b"PK\x03\x04") and data[30:38] == b"mimetype" and MIMETYPE in data[38:200]):
        return None
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        sections = sorted((int(m.group(1)), info) for info in z.infolist() if (m := _SECTION.fullmatch(info.filename)))
        if not sections:
            raise ValueError("the HWPX file has no body")
        if sum(info.file_size for _, info in sections) > _MAX_BODY:
            raise ValueError(f"the HWPX body is larger than {_MAX_BODY >> 20} MB")
        blocks: list[str] = []
        for _, info in sections:
            root = ElementTree.fromstring(z.read(info))
            for p in root.findall(f"{_HP}p"):
                blocks += _paragraph(p)
    return "\n\n".join(blocks)


def _paragraph(p: ElementTree.Element) -> list[str]:
    """The paragraph's text, then each table it anchors."""
    text: list[str] = []
    tables: list[str] = []
    for run in p.findall(f"{_HP}run"):
        for child in run:
            if child.tag == f"{_HP}t":
                text.append(_text(child))
            elif child.tag == f"{_HP}tbl":
                rows = _rows(child)
                if rows:
                    tables.append("\n".join(rows))
    line = "".join(text).strip()
    # 성진: 글상자·각주·머리말처럼 표가 아닌 개체 안의 문단은 읽지 않는다; 그런 문서에서 본문이 빠진다는 보고가 오면 개체별 subList를 따라간다.
    return ([line] if line else []) + tables


def _text(t: ElementTree.Element) -> str:
    parts = [t.text or ""]
    for child in t:
        parts += [_AS_TEXT.get(child.tag, ""), child.tail or ""]
    return "".join(parts)


def _rows(tbl: ElementTree.Element) -> list[str]:
    """One line per row, its cells between ` | `; a cell's own paragraphs, a table inside it included, run together on that line."""
    # 성진: 병합 셀은 펼치지 않는다(합친 칸은 그 행에 한 번만 나온다); 열 위치가 필요한 표가 보이면 cellAddr·cellSpan으로 격자를 채운다.
    rows = []
    for tr in tbl.findall(f"{_HP}tr"):
        cells = []
        for tc in tr.findall(f"{_HP}tc"):
            lines = [line for sub in tc.findall(f"{_HP}subList") for p in sub.findall(f"{_HP}p") for line in _paragraph(p)]
            cells.append(" ".join(" ".join(line.split()) for line in lines))
        if any(cells):
            rows.append(" | ".join(cells))
    return rows
