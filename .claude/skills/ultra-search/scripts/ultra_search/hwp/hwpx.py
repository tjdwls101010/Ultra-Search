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
_OPF = "{http://www.idpf.org/2007/opf/}"
_AS_TEXT = {f"{_HP}tab": "\t", f"{_HP}lineBreak": "\n", f"{_HP}fwSpace": " ", f"{_HP}nbSpace": " ", f"{_HP}hyphen": "-"}
#: Past this much uncompressed body the file is refused: it came from the web, and a zip entry can expand without bound.
_MAX_BODY = 256 << 20
#: Past this many elements in one paragraph or table the file is refused. The XML is read a block at a time and each is let go once read; this bounds what one block can hold -- a table of tens of thousands of cells is under it, a crafted flood of elements is not.
_MAX_NODES = 300_000


def text_of(path: str | os.PathLike[str]) -> str | None:
    """The body's paragraphs and table rows, a blank line between paragraphs; None when the file is not HWPX. Raises once it is one: ValueError for a missing or oversized body, whatever zipfile or the XML parser raise for damage."""
    data = Path(path).read_bytes()
    if not _first_entry_is_mimetype(data):
        return None
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        present = {info.filename: info for info in z.infolist()}
        names = _listed_sections(z) if "Contents/content.hpf" in present else []
        missing = [n for n in names if n not in present]
        if missing:
            raise ValueError(f"the HWPX file lacks {', '.join(missing)}, which its manifest lists")
        names = names or [n for n in present if _SECTION.fullmatch(n)]
        sections = sorted((int(_SECTION.fullmatch(n).group(1)), present[n]) for n in names)
        if not sections:
            raise ValueError("the HWPX file has no body")
        if sum(info.file_size for _, info in sections) > _MAX_BODY:
            raise ValueError(f"the HWPX body is larger than {_MAX_BODY >> 20} MB")
        blocks: list[str] = []
        for _, info in sections:
            with z.open(info) as stream:
                blocks += _section(stream)
    return "\n\n".join(blocks)


def _first_entry_is_mimetype(data: bytes) -> bool:
    """Whether the zip's first entry is `mimetype`, stored uncompressed, reading exactly application/hwp+zip -- read from its local header, so a copy cut short is still known for what it is."""
    if not data.startswith(b"PK\x03\x04") or len(data) < 30:
        return False
    method = int.from_bytes(data[8:10], "little")
    size = int.from_bytes(data[18:22], "little")
    name_len, extra_len = int.from_bytes(data[26:28], "little"), int.from_bytes(data[28:30], "little")
    start = 30 + name_len + extra_len
    return method == 0 and data[30:30 + name_len] == b"mimetype" and data[start:start + size] == MIMETYPE


def _listed_sections(z: zipfile.ZipFile) -> list[str]:
    """The body sections the package manifest lists: a section missing from the zip would otherwise go unread without a sign."""
    manifest = ElementTree.fromstring(z.read("Contents/content.hpf"))
    return [href for item in manifest.iter(f"{_OPF}item") if _SECTION.fullmatch(href := item.get("href") or "")]


def _section(stream) -> list[str]:
    """A section's paragraphs, read one top-level block at a time and let go once read."""
    blocks: list[str] = []
    depth = nodes = 0
    root = None
    for event, elem in ElementTree.iterparse(stream, events=("start", "end")):
        if event == "start":
            depth += 1
            nodes += 1
            root = root if root is not None else elem
            if nodes > _MAX_NODES:
                raise ValueError(f"an HWPX paragraph has more than {_MAX_NODES:,} elements")
            continue
        depth -= 1
        if depth == 1:
            if elem.tag == f"{_HP}p":
                blocks += _paragraph(elem)
            root.clear()
            nodes = 0
    return blocks


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
