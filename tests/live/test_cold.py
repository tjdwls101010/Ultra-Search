"""A closed Aside, started by the commands themselves. Runs only when `-m` names `cold`:

    python3 -m pytest tests/ -m cold

Each test quits the user's Aside app first and leaves it running at the end, so run these when nobody is using the
browser. One of them spends the user's subscription on a short search. The fakes prove which way the skill branches
when the daemon does not answer; only these prove that the real CLI then opens Aside and the work goes through.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from conftest import cold_runs

pytestmark = [pytest.mark.cold, pytest.mark.skipif(sys.platform != "darwin", reason="quits the app the macOS way")]

SCRIPT = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "ultra-search" / "scripts" / "cli.py"
APP_ID = "at.studio.AsideBrowser"
HEALTH = "http://127.0.0.1:21420/"
#: What the CLI says when it opens a closed Aside (A11), and when it finds one still starting (A13).
OPENING = ("Aside isn't running. Opening it in the background...", "Waiting for Aside to finish starting...")


def cli(*args: str, timeout: float = 300, env: dict | None = None) -> tuple[int, dict, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=timeout, env=env)
    lines = [line for line in p.stdout.split("\n") if line.startswith("{")]
    return p.returncode, (json.loads(lines[-1]) if lines else {}), p.stderr


def app_processes() -> int:
    found = subprocess.run(["pgrep", "-f", r"Aside\.app/Contents/MacOS/Aside$"], capture_output=True, text=True)
    return len(found.stdout.split())


def health_answers() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 21420), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def closed(request: pytest.FixtureRequest) -> None:
    """The one place a test quits Aside, and only under an `-m` that names the cold tests."""
    assert cold_runs(request.config.getoption("-m") or ""), "only -m cold may quit the user's browser"
    subprocess.run(["osascript", "-e", f'quit app id "{APP_ID}"'], capture_output=True, timeout=60)
    until = time.time() + 30
    while (health_answers() or app_processes()) and time.time() < until:
        time.sleep(0.5)
    assert not health_answers() and app_processes() == 0, "Aside did not quit"


def test_a_closed_aside_is_started_and_a_page_fetched(closed, tmp_path: Path) -> None:
    code, payload, err = cli("fetch", "https://example.com", "--out", str(tmp_path / "pages"))

    assert code == 0, payload
    assert payload["items"][0]["status"] == "ok"
    assert any(line in err for line in OPENING), err
    assert app_processes() == 1


def test_a_closed_aside_is_started_with_the_users_logins(closed, tmp_path: Path) -> None:
    """As test_live's login-gated feed: the Aside that comes up is the user's, signed in to its sites."""
    code, payload, _ = cli("fetch", "https://www.youtube.com/feed/subscriptions", "--out", str(tmp_path / "pages"))

    item = payload["items"][0]
    assert item["status"] == "ok", item.get("error")
    assert item["words"] > 100


@pytest.mark.parametrize("attempt", range(20))
def test_a_tab_opened_right_after_the_start_is_read(closed, tmp_path: Path, attempt: int) -> None:
    """A tab opened in the first seconds after a start failed 4 times in 22 with `CDP session detached`."""
    code, payload, _ = cli("fetch", "https://example.com", "--via", "tab", "--out", str(tmp_path / "pages"))

    assert payload["items"][0]["status"] == "ok", payload["items"][0].get("error")


def test_a_closed_aside_is_started_and_a_site_mapped(closed, tmp_path: Path) -> None:
    code, payload, _ = cli("map", "https://docs.aside.com", "--max-urls", "20", "--out", str(tmp_path / "map.json"))

    assert code == 0, payload
    assert payload["count"] > 0


def test_doctor_starts_a_closed_aside_and_checks_everything(closed) -> None:
    code, payload, _ = cli("doctor")

    assert code == 0, [c for c in payload["checks"] if not c["ok"]]
    daemon = next(c for c in payload["checks"] if c["check"] == "aside daemon")
    assert "round trip" in daemon.get("note", "")
    assert {"browser repl", "aside account"} <= {c["check"] for c in payload["checks"]}


def test_two_commands_against_a_closed_aside_start_one_app(closed, tmp_path: Path) -> None:
    results: list[tuple[int, dict, str]] = []
    runs = [threading.Thread(target=lambda i=i: results.append(
        cli("fetch", "https://example.com", "--out", str(tmp_path / f"pages-{i}")))) for i in range(2)]
    for t in runs:
        t.start()
    for t in runs:
        t.join()

    assert [r[1]["items"][0]["status"] for r in results] == ["ok", "ok"]
    assert app_processes() == 1


def test_a_search_against_a_closed_aside_is_answered(closed, tmp_path: Path) -> None:
    """Spends the subscription. The start-up happens before the run is reserved, so the run's own stdout -- which an
    answer can be cut from -- never carries the CLI's start-up line."""
    code, started, err = cli("search", "What is the title of https://example.com ? Open it and answer in one line.",
                             "--effort", "low", "--runs-dir", str(tmp_path))
    assert code == 0, started
    run_id = started["runs"][0]["run_id"]
    code, payload, _ = cli("result", run_id, "--wait", "300", "--runs-dir", str(tmp_path), timeout=360)

    run = payload["runs"][0]
    assert run["state"] == "completed", run
    assert run["answer"] and run["opened_sources"]
    assert not any(line in (tmp_path / "runs" / run_id / "stdout.log").read_text(encoding="utf-8") for line in OPENING)


@pytest.mark.parametrize("argv", [["fetch", "https://example.com"], ["search", "x"], ["doctor"]],
                         ids=["fetch", "search", "doctor"])
def test_an_aside_the_cli_will_not_open_is_reported_in_its_words(tmp_path: Path, argv: list[str]) -> None:
    """A DAEMON_BASE_URL other than the default is one the CLI does not open; Aside's own app stays as it is."""
    import os

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed_url = f"http://127.0.0.1:{s.getsockname()[1]}"
    env = {**os.environ, "DAEMON_BASE_URL": closed_url}

    code, payload, _ = cli(*argv, "--runs-dir", str(tmp_path), env=env)

    assert code == 3
    said = payload["message"] if "message" in payload else next(c["detail"] for c in payload["checks"]
                                                                  if c["check"] == "aside daemon")
    assert "Aside isn't running on this machine" in said
    if argv[0] == "search":
        assert not (tmp_path / "runs").exists() or not any((tmp_path / "runs").iterdir())
