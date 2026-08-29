"""Shared fixtures.

Every test that touches the aside side of the world points ULTRA_SEARCH_ASIDE_HOME at a
tmpdir and ULTRA_SEARCH_ASIDE_BIN at tests/fake_aside/aside. Nothing here may read the
developer's real ~/.aside: a test that passes only on the machine that recorded the
fixtures is a test that reports the harness works everywhere when it does not.
"""
from __future__ import annotations

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
