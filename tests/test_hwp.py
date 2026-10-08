"""Hancom's formats read through the hwp unit's one interface, `extract`.

The fixtures are real public documents: a Supreme Court decision (scourt.go.kr, served as application/x-hwp), a Constitutional Court decision (ccourt.go.kr, served as application/x-msdownload) and an MSS application form (mss.go.kr, HWPX). The court decisions name their parties only as ○○; the account name in the first one's summary metadata, which nothing here reads, is blanked.

The expected text is not read off this code's output. Each passage comes from another rendering of the same document -- casenote.kr's pages of the two decisions and the PDF that mss.go.kr posts beside the HWPX -- and is one that rendering and the original share word for word.
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

#: (document, its extension, a passage from its middle, its last passage) -- each from another rendering.
PASSAGES = [
    (SCOURT, "hwp", "사건본인은 2018. 11.경 혈관성 치매(Vascular dementia) 등 진단을 받고",
     "재항고는 이유 없으므로 이를 기각하고 재항고비용은 패소자가 부담하도록 하여, 대법관의 일치된 의견으로 주문과 같이 결정한다."),
    (CCOURT, "hwp", "2013. 7.부터 2016. 9.까지 서울가정법원에서 다툼 없는 사건 중 60.1%, 다툼 있는 사건 중 38.5%에서 감정을 생략한 것으로 나타났다.",
     "침해의 최소성 및 법익균형성에 위반하여 자기결정권을 침해하는 것으로서 헌법에 위반된다."),
    (FORM, "hwpx", "창업진흥원은 사업 수행과 관련한 재무건전성의 확인을 위하여",
     "창업 및 유지 동의 등 책임 동의를 거부할 권리가 있습니다."),
]


@pytest.mark.parametrize("path,ext,middle,last", PASSAGES, ids=["scourt", "ccourt", "form"])
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
    """An OLE file without the HWP signature, and a zip that is not HWPX, are some other document."""
    other_zip = tmp_path / "other.zip"
    with zipfile.ZipFile(other_zip, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("content.xml", "<x/>")

    assert hwp.extract(patched_header(tmp_path, signature=b"Not a Hangul Word Processor")) is None
    assert hwp.extract(other_zip) is None
    assert hwp.extract(DOCS / "sample_en.pdf") is None
