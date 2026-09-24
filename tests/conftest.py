"""Shared fixtures.

Every test that touches the aside side of the world points ULTRA_SEARCH_ASIDE_HOME at a
tmpdir and ULTRA_SEARCH_ASIDE_BIN at tests/fake_aside/aside. Nothing here may read the
developer's real ~/.aside: a test that passes only on the machine that recorded the
fixtures is a test that reports the harness works everywhere when it does not.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
SCRIPTS = REPO / ".claude" / "skills" / "ultra-search" / "scripts"
FIXTURES = TESTS / "fixtures"

sys.path.insert(0, str(SCRIPTS))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: needs a running Aside app; skipped unless -m live is given")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if "live" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="live test: run with -m live and the Aside app open")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def aside_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway ~/.aside whose sessions/ starts as a copy of the recorded fixtures."""
    home = tmp_path / "aside-home"
    sessions = home / "u" / "0" / "sessions"
    sessions.mkdir(parents=True)
    for d in (FIXTURES / "sessions").iterdir():
        if d.is_dir():
            shutil.copytree(d, sessions / d.name)
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_HOME", str(home))
    return home


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runs-root"
    d.mkdir()
    return d


@pytest.fixture
def fake_aside(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The stand-in aside binary, plus a directory it records its argv into."""
    binary = TESTS / "fake_aside" / "aside"
    calls = tmp_path / "aside-calls"
    calls.mkdir()
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", str(binary))
    monkeypatch.setenv("FAKE_ASIDE_CALLS", str(calls))
    os.chmod(binary, 0o755)
    return calls


# --- the CLI seam ------------------------------------------------------------------------


def run_cli(*argv: str) -> tuple[int, dict, str]:
    """argv in; the exit code, the last JSON line on stdout, and all of stdout out."""
    import cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    text = buf.getvalue()
    last = [line for line in text.splitlines() if line.startswith("{")]
    return code, (json.loads(last[-1]) if last else {}), text


@pytest.fixture
def cli(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch: pytest.MonkeyPatch):
    """The CLI against the fake aside, with every command pointed at this test's registry."""
    monkeypatch.setenv("FAKE_ASIDE_SCENARIO", "simple")
    return lambda *a: run_cli(*a, "--runs-dir", str(runs_dir))


@pytest.fixture
def routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install the browser's answers for the page snippets (see tests/fake_aside/aside)."""

    def install(table: dict) -> None:
        path = tmp_path / "repl-routes.json"
        path.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv("FAKE_ASIDE_REPL_ROUTES", str(path))

    return install


def repl_calls(calls_dir: Path, snippet: str) -> list[dict]:
    """The ARGS of every call the CLI made to one page snippet, in order."""
    out = []
    log = calls_dir / "calls.jsonl"
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8").splitlines():
        argv = json.loads(line)["argv"]
        if len(argv) < 3 or argv[1] != "repl":
            continue
        code = argv[-1].splitlines()
        if len(code) > 1 and code[1] == f"// snippet: {snippet}":
            out.append(json.loads(code[0][len("const ARGS = "):].rstrip(";")))
    return out


def exec_calls(calls_dir: Path) -> list[list[str]]:
    """The argv of every `aside exec` the CLI started, in order."""
    log = calls_dir / "calls.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return [r["argv"] for r in rows if len(r["argv"]) > 1 and r["argv"][1] == "exec"]


@pytest.fixture
def replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Make the next `aside exec` write these transcript records after its prompt.

    Accepts records, or a recorded messages.jsonl whose bytes are replayed as they are.
    ``{"__sleep__": SEC}`` holds the run open at that point.
    """

    def install(source) -> Path:
        path = tmp_path / f"replay-{len(list(tmp_path.glob('replay-*')))}.jsonl"
        if isinstance(source, (str, Path)):
            path.write_bytes(Path(source).read_bytes())
        else:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in source), encoding="utf-8")
        monkeypatch.setenv("FAKE_ASIDE_REPLAY", str(path))
        return path

    return install


def aside_session(home: Path, session_id: str, *records: dict) -> Path:
    """A session as Aside itself would have left it on disk -- one the CLI did not start."""
    d = home / "u" / "0" / "sessions" / f"2026-09-25_{session_id}"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "messages.jsonl").open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return d


def user(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}], "timestamp": 1}


def answer(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}], "stopReason": "stop", "timestamp": 2}


def calling(*calls: tuple[str, object], text: str = "") -> dict:
    content = [{"type": "toolCall", "name": n, "arguments": a} for n, a in calls]
    if text:
        content.append({"type": "text", "text": text})
    return {"role": "assistant", "content": content, "stopReason": "toolUse", "timestamp": 2}


def tool(name: str, content: str, **details: object) -> dict:
    return {"role": "toolResult", "toolName": name, "content": content, "details": details, "timestamp": 3}
