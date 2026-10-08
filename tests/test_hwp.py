"""Hancom's formats read through the hwp unit's one interface, `extract`.

The fixtures are real public documents: a Supreme Court decision (scourt.go.kr, served as application/x-hwp), a Constitutional Court decision (ccourt.go.kr, served as application/x-msdownload), a draft decree from a legislative notice in four sections (mpva.go.kr) and an MSS application form (mss.go.kr, HWPX). The court decisions name their parties only as ○○; the names of people in the summary metadata of the first and the draft, which nothing here reads, are blanked.

The expected text is not read off this code's output. Each passage comes from another rendering of the same document -- casenote.kr's pages of the two decisions, the PDF that mss.go.kr posts beside the HWPX, and for the draft pyhwp's hwp5txt, a reader of the format written by other people -- and is one that rendering and the original share word for word.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

import olefile
import pytest

from ultra_search import hwp

DOCS = Path(__file__).parent / "fixtures" / "docs"
SCOURT = DOCS / "scourt_2020seu596.hwp"
CCOURT = DOCS / "ccourt_2018heonba130.hwp"
FORM = DOCS / "mss_evidence_form.hwpx"
DRAFT = DOCS / "mpva_decree_draft_2021.hwp"

#: (document, its extension, a passage from its middle, its last passage) -- each from another rendering.
PASSAGES = [
    (SCOURT, "hwp", "사건본인은 2018. 11.경 혈관성 치매(Vascular dementia) 등 진단을 받고",
     "재항고는 이유 없으므로 이를 기각하고 재항고비용은 패소자가 부담하도록 하여, 대법관의 일치된 의견으로 주문과 같이 결정한다."),
    (CCOURT, "hwp", "2013. 7.부터 2016. 9.까지 서울가정법원에서 다툼 없는 사건 중 60.1%, 다툼 있는 사건 중 38.5%에서 감정을 생략한 것으로 나타났다.",
     "침해의 최소성 및 법익균형성에 위반하여 자기결정권을 침해하는 것으로서 헌법에 위반된다."),
    (FORM, "hwpx", "창업진흥원은 사업 수행과 관련한 재무건전성의 확인을 위하여",
     "창업 및 유지 동의 등 책임 동의를 거부할 권리가 있습니다."),
    (DRAFT, "hwp", "제102조의2제1항 각 호 외의 부분 중 “제102조”를 “보훈심사위원회와 제102조”로 한다.",
     "이 영은 공포한 날부터 시행한다."),
]


@pytest.mark.parametrize("path,ext,middle,last", PASSAGES, ids=["scourt", "ccourt", "form", "draft"])
def test_a_document_reads_whole_in_order_and_once(path: Path, ext: str, middle: str, last: str) -> None:
    """A reader that stopped at a preview or at its first section would miss the later passage; one that read a table's paragraphs twice would repeat it."""
    got = hwp.extract(path)

    assert got["status"] == "ok" and got["ext"] == ext and got["error"] is None
    text = got["text"]
    assert text.count(middle) == 1 and text.count(last) == 1
    assert text.index(middle) < text.index(last)


def test_tabs_and_fixed_spaces_keep_words_apart() -> None:
    """The decision's header lays its labels out with tabs: dropped, the label runs into the case number."""
    assert re.search(r"건\s+2018헌바130\s+민법 제9조 제1항 등 위헌소원", hwp.extract(CCOURT)["text"])


def test_every_section_is_read_in_order() -> None:
    """The draft's body is in four sections. hwp5txt shows the third ending on the enforcement clause and the fourth opening with the comparison table's title."""
    assert "이 영은 공포한 날부터 시행한다.\n\n신ㆍ구조문대비표\n\n" in hwp.extract(DRAFT)["text"]


def test_a_table_row_is_one_line_its_cells_apart() -> None:
    """From the form's last pages: the PDF beside it shows these two cells side by side."""
    text = hwp.extract(FORM)["text"]

    assert text.count("신청서 제출 관련 책임 동의 | □ 동의 □ 비동의") == 1


def patched_header(tmp_path: Path, flags: int | None = None, signature: bytes | None = None) -> Path:
    """A copy of the decision with its FileHeader's lock flags or signature changed in place."""
    copy = tmp_path / "patched.hwp"
    shutil.copy(SCOURT, copy)
    with olefile.OleFileIO(str(copy), write_mode=True) as ole:
        header = bytearray(ole.openstream("FileHeader").read())
        if flags is not None:
            header[36:40] = (int.from_bytes(header[36:40], "little") | flags).to_bytes(4, "little")
        if signature is not None:
            header[: len(signature)] = signature
        ole.write_stream("FileHeader", bytes(header))
    return copy


@pytest.mark.parametrize("flag,why", [(2, "password-protected HWP"), (4, "distribution-protected HWP")])
def test_a_locked_document_says_so(tmp_path: Path, flag: int, why: str) -> None:
    assert hwp.extract(patched_header(tmp_path, flags=flag)) == {"status": "unsupported", "text": "", "error": why, "ext": "hwp"}


@pytest.mark.parametrize("source,ext", [(SCOURT, "hwp"), (CCOURT, "hwp"), (FORM, "hwpx")])
def test_a_cut_short_document_never_passes_for_a_whole_one(tmp_path: Path, source: Path, ext: str) -> None:
    """A download cut short is unsupported -- or, cut where only parts other than the body were, reads whole. What it must never do is read as ok with less than the whole text, or raise; too short to show what it is, it is left to the other converters."""
    data = source.read_bytes()
    whole = hwp.extract(source)["text"]
    cut = tmp_path / f"cut.{ext}"
    for n in range(1, 20):
        cut.write_bytes(data[: len(data) * n // 20])
        got = hwp.extract(cut)
        if got is not None:
            assert got["ext"] == ext
            assert (got["status"], got["text"]) == ("ok", whole) or (got["status"] == "unsupported" and got["error"]), n
    cut.write_bytes(data[: len(data) // 2])

    assert hwp.extract(cut)["status"] == "unsupported"


def test_a_container_that_is_not_hancoms_is_left_to_others(tmp_path: Path) -> None:
    """An OLE file whose FileHeader is not HWP's -- even with the signature's bytes somewhere else in it -- and a zip whose first entry does not say HWPX -- even with the words further in -- are some other document."""
    other_ole = patched_header(tmp_path, signature=b"Not a Hangul Word Processor")
    with olefile.OleFileIO(str(other_ole)) as ole:
        preview = (ole.direntries[ole._find(["PrvImage"])].isectStart + 1) * ole.sectorsize
    data = bytearray(other_ole.read_bytes())
    data[preview:preview + len(HWP_SIGNATURE)] = HWP_SIGNATURE
    other_ole.write_bytes(bytes(data))
    other_zip = tmp_path / "other.zip"
    with zipfile.ZipFile(other_zip, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("note.txt", "application/hwp+zip")
        z.writestr("Contents/section0.xml", SECTION.format(body=PARAGRAPH.format(text="본문")))

    assert hwp.extract(other_ole) is None
    assert hwp.extract(other_zip) is None
    assert hwp.extract(DOCS / "sample_en.pdf") is None


HWP_SIGNATURE = b"HWP Document File"
SECTION = '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">{body}</hs:sec>'
PARAGRAPH = '<hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>'


def rezipped(tmp_path: Path, *, drop: str = "", add: dict[str, str] | None = None) -> Path:
    """The form, repacked the way Hancom packs one -- `mimetype` first and stored -- less an entry or with more."""
    out = tmp_path / "repacked.hwpx"
    with zipfile.ZipFile(FORM) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename != drop:
                dst.writestr(info, src.read(info), compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
        for name, text in (add or {}).items():
            dst.writestr(name, text)
    return out


def test_a_section_the_manifest_lists_but_the_file_lacks_is_damage(tmp_path: Path) -> None:
    """Without the check, the rest reads cleanly and the document passes for whole."""
    got = hwp.extract(rezipped(tmp_path, drop="Contents/section5.xml"))

    assert got["status"] == "unsupported" and "Contents/section5.xml" in got["error"]


def test_a_flood_of_elements_is_refused_not_held(tmp_path: Path) -> None:
    """A few kilobytes of zip can carry millions of empty elements in one paragraph."""
    flood = PARAGRAPH.format(text="<hp:tab/>" * 400_000)
    got = hwp.extract(rezipped(tmp_path, drop="Contents/section5.xml", add={"Contents/section5.xml": SECTION.format(body=flood)}))

    assert got["status"] == "unsupported" and "elements" in got["error"]
