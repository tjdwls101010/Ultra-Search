"""End-to-end against the real Aside app. Skipped unless run with `-m live`.

    python3 -m pytest tests/ -m live

These cost real tokens on the user's subscription and need the Aside app open and logged
in, which is why they are opt-in. They exist because every other test in this repo mocks
the one thing that is hardest to get right -- the browser -- and a suite that never
touches it would pass while the whole tool was broken.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

SCRIPT = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "ultra-search" / "scripts" / "cli.py"


def cli(*args: str, timeout: float = 300) -> tuple[int, dict]:
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=timeout)
    lines = [l for l in p.stdout.splitlines() if l.startswith("{")]
    return p.returncode, (json.loads(lines[-1]) if lines else {})


def test_doctor_reports_a_working_environment() -> None:
    code, payload = cli("doctor")

    assert code == 0, [c for c in payload.get("checks", []) if not c["ok"]]
    assert all(c["ok"] for c in payload["checks"])


def test_a_simple_search_answers_with_sources(tmp_path: Path) -> None:
    """`completed`, a session id and token usage are the correlation working: when the run's
    own session is not found, the run still ends, as `completed_unstructured`, with an answer
    cut from stdout and no usage. The page it was asked to open is a source it opened, whichever
    tool the agent chose to open it with."""
    code, payload = cli(
        "search",
        "현재 Python 3의 최신 안정 버전은 무엇인가? python.org 다운로드 페이지를 직접 열어 확인하고 한 줄로 답해라.",
        "--effort", "low",
        "--wait", "120",
        "--runs-dir", str(tmp_path),
    )

    assert code == 0
    run = payload["runs"][0]
    _, mine = cli("sessions", "--mine", "--limit", "50", "--runs-dir", str(tmp_path))
    assert run["state"] == "completed", run.get("note")
    assert run["run_id"] in [s["run_id"] for s in mine["sessions"]], "the run found its own session by its marker"
    assert run["answer"].strip()
    assert run["opened_sources"], run
    assert json.loads(Path(run["result_path"]).read_text(encoding="utf-8"))["usage"]["total_tokens"] > 0


@pytest.mark.parametrize("url,ext,passage", [
    ("https://www.scourt.go.kr/sjudge/1625214940201_173540.hwp", ".hwp", "대법관의 일치된 의견으로 주문과 같이 결정한다."),
    ("https://ccourt.go.kr/common/board/Download.do?bcIdx=941807&cbIdx=1106&streFileNm=20200123090701_cmggokmipgwnxld.hwp",
     ".hwp", "법익균형성에 위반하여 자기결정권을 침해하는 것으로서 헌법에 위반된다."),
    ("https://www.mss.go.kr/common/board/Download.do?bcIdx=1069575&cbIdx=310&streFileNm=a37ab8d8-8013-4d42-8ab6-a4b24766ba10.hwpx",
     ".hwpx", "신청서 제출 관련 책임 동의 | □ 동의 □ 비동의"),
], ids=["hwp-x-hwp", "hwp-x-msdownload", "hwpx"])
def test_a_hancom_document_is_fetched_by_the_browser_and_read(tmp_path: Path, url: str, ext: str, passage: str) -> None:
    """The fake browser runs no JavaScript, so only this shows the snippet passing an HWP served as application/x-hwp or application/x-msdownload, and an HWPX as octet-stream, through to the reader as a file."""
    code, payload = cli("fetch", url, "--out", str(tmp_path / "out") + "/", "--runs-dir", str(tmp_path))

    item = payload["items"][0]
    assert code == 0 and item["status"] == "ok", item
    assert passage in Path(item["path"]).read_text(encoding="utf-8")
    assert Path(item["original_path"]).suffix == ext


def test_a_public_page_is_fetched_and_saved(tmp_path: Path) -> None:
    code, payload = cli("fetch", "https://en.wikipedia.org/wiki/Web_scraping", "--out", str(tmp_path / "pages"))

    assert code == 0
    item = payload["items"][0]
    assert item["status"] == "ok"
    assert item["words"] > 1000
    assert "scraping" in Path(item["path"]).read_text(encoding="utf-8").lower()


def test_a_client_rendered_page_is_promoted_to_a_real_tab(tmp_path: Path) -> None:
    """x.com returns a full HTML document with almost no text in it. Anything that reports
    this as a successful read is reporting an empty page as a source."""
    code, payload = cli("fetch", "https://x.com/elonmusk", "--out", str(tmp_path / "pages"))

    item = payload["items"][0]
    assert item["status"] == "ok"
    assert item["via"] == "tab"
    assert item["words"] > 50


def test_a_login_gated_feed_is_readable(tmp_path: Path) -> None:
    """The entire reason for using the user's own browser. If this fails, either the
    session expired or the escalation path broke."""
    code, payload = cli("fetch", "https://www.youtube.com/feed/subscriptions", "--out", str(tmp_path / "pages"))

    item = payload["items"][0]
    assert item["status"] == "ok", item.get("error")
    assert item["words"] > 100


def test_a_pdf_becomes_markdown_and_the_original_is_kept(tmp_path: Path) -> None:
    code, payload = cli("fetch", "https://arxiv.org/pdf/1706.03762", "--out", str(tmp_path / "pages"))

    item = payload["items"][0]
    assert item["status"] == "ok"
    assert Path(item["path"]).suffix == ".md"
    assert Path(item["original_path"]).exists()


def test_a_documentation_site_crawls(tmp_path: Path) -> None:
    code, payload = cli("crawl", "https://docs.aside.com", "--out", str(tmp_path / "docs"), "--max-pages", "25")

    assert code == 0
    assert payload["saved"] >= 10
    manifest = json.loads((tmp_path / "docs" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == payload["saved"]


def test_map_finds_urls_without_downloading_them(tmp_path: Path) -> None:
    """map is the cheap look-before-you-download step, so the check that matters is that
    it wrote a manifest and no pages -- pointed at a directory it actually uses."""
    manifest = tmp_path / "map.json"

    code, payload = cli("map", "https://docs.aside.com", "--max-urls", "50", "--out", str(manifest))

    assert code == 0
    assert payload["count"] >= 10
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["urls"]) == payload["count"]
    assert list(tmp_path.rglob("*.md")) == []


def test_a_session_started_outside_this_tool_can_be_continued(tmp_path: Path) -> None:
    """A conversation started by a bare `aside exec` -- or in the Aside app -- is picked up
    here and continued with what it already worked out, rather than investigated again."""
    import subprocess as sp

    sp.run(
        ["aside", "exec", "--effort", "low", "내 이름은 성진이야. 기억해 두고 알겠다고만 답해."],
        capture_output=True, text=True, timeout=180,
    )

    code, listing = cli("sessions", "--limit", "10", "--runs-dir", str(tmp_path))
    assert code == 0
    external = next(s for s in listing["sessions"] if "성진" in s["prompt"])
    assert external["started_by_ultra_search"] is False

    code, payload = cli(
        "resume", external["session_id"], "내 이름이 뭐라고 했지? 이름만 답해.",
        "--wait", "120", "--runs-dir", str(tmp_path),
    )

    assert code == 0
    run = payload["runs"][0]
    assert run["state"] == "completed"
    # The point of resuming rather than starting fresh: it still has the earlier turn.
    assert "성진" in run["answer"]


def test_repl_api_reports_the_installed_browser_api() -> None:
    code, payload = cli("repl-api")

    assert code == 0
    assert payload["tool"]["name"] == "repl"


def test_a_missing_binary_fails_fast_rather_than_hanging(tmp_path: Path, monkeypatch) -> None:
    import os

    env = dict(os.environ, ULTRA_SEARCH_ASIDE_BIN="/nonexistent/aside")
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "search", "질문", "--wait", "5", "--runs-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, timeout=60,
    )

    assert p.returncode == 3
    assert json.loads(p.stdout.splitlines()[-1])["error"] == "aside_unavailable"
