"""`doctor`, `setup`, `repl-api` and the contract every command shares: argv in, JSON out.

`doctor` answers one question -- would a command fail right now, and why -- so each check
is driven here by changing the one thing outside the CLI it looks at: the aside binary
(the fake), the daemon's health endpoint (a local HTTP server standing in for it), the
account roster, the installation on disk, the runs directory.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import SCRIPTS, run_cli

VERIFIED_DAEMON = {"ready": True, "version": "1.26.829.1514", "runningSessionCount": 0,
                   "semaphore": {"available": 4, "capacity": 4}}


@pytest.fixture
def daemon(monkeypatch: pytest.MonkeyPatch):
    """A stand-in for the daemon's health endpoint; returns a setter for its reply."""
    state = {"body": dict(VERIFIED_DAEMON)}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
            data = json.dumps(state["body"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("ULTRA_SEARCH_DAEMON_URL", f"http://127.0.0.1:{server.server_address[1]}/")
    yield lambda **body: state.update(body=body)
    server.shutdown()


def doctor(runs_dir: Path) -> tuple[int, dict]:
    code, payload, _ = run_cli("doctor", "--runs-dir", str(runs_dir))
    return code, payload


def check(payload: dict, name: str) -> dict:
    return next(c for c in payload["checks"] if c["check"] == name)


# --- doctor ------------------------------------------------------------------------------


def test_doctor_passes_when_everything_a_command_needs_is_there(
    runs_dir: Path, aside_home: Path, fake_aside: Path, daemon
) -> None:
    code, payload = doctor(runs_dir)

    assert code == 0, [c for c in payload["checks"] if not c["ok"]]
    assert payload["ok"] is True
    assert {c["check"] for c in payload["checks"]} == {
        "aside binary", "aside version", "aside daemon", "browser repl", "aside account",
        "node", "page conversion", "aside sessions", "runs dir",
    }
    assert all(c["ok"] and "fix" not in c for c in payload["checks"])


def test_a_closed_daemon_fails_doctor(runs_dir: Path, aside_home: Path, fake_aside: Path, monkeypatch) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setenv("ULTRA_SEARCH_DAEMON_URL", f"http://127.0.0.1:{port}/")

    code, payload = doctor(runs_dir)

    assert code == 3
    assert check(payload, "aside daemon")["ok"] is False
    assert check(payload, "aside daemon")["fix"] == "Open the Aside app."


def test_a_daemon_that_is_up_but_not_ready_fails_doctor(runs_dir: Path, aside_home: Path, fake_aside: Path, daemon) -> None:
    daemon(**{**VERIFIED_DAEMON, "ready": False})

    code, payload = doctor(runs_dir)

    assert code == 3
    assert check(payload, "aside daemon")["ok"] is False


def test_versions_other_than_the_measured_ones_are_named_not_failed(
    runs_dir: Path, aside_home: Path, fake_aside: Path, daemon, monkeypatch
) -> None:
    """A different build is the first thing to suspect when runs behave oddly, not a reason
    to refuse to run."""
    monkeypatch.setenv("FAKE_ASIDE_VERSION", "2.0.0")
    daemon(**{**VERIFIED_DAEMON, "version": "2.0.0"})

    code, payload = doctor(runs_dir)

    assert code == 0
    for name in ("aside version", "aside daemon"):
        assert check(payload, name)["ok"] is True
        assert "measured against" in check(payload, name)["fix"]


def test_doctor_fails_when_the_conversion_packages_are_missing(
    tmp_path: Path, runs_dir: Path, aside_home: Path, fake_aside: Path, daemon
) -> None:
    """Without these, `fetch` reaches the page and then fails to convert it -- a failure that
    reads as a network problem unless doctor says otherwise. Driven on an installation that
    was copied without them, which is what a fresh clone before `setup` looks like."""
    fresh = tmp_path / "fresh-install"
    shutil.copytree(SCRIPTS, fresh, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))

    p = subprocess.run([sys.executable, str(fresh / "cli.py"), "doctor", "--runs-dir", str(runs_dir)],
                       capture_output=True, text=True, timeout=120)

    payload = json.loads(p.stdout.splitlines()[-1])
    assert p.returncode == 3
    assert payload["ok"] is False
    assert check(payload, "page conversion")["ok"] is False
    assert check(payload, "page conversion")["fix"] == "Run `setup`."


def test_doctor_fails_on_an_unwritable_runs_directory(aside_home: Path, fake_aside: Path, daemon, tmp_path: Path) -> None:
    """Tried, not assumed: an unwritable runs directory lets doctor pass and then fails the
    first `search` at the moment it reserves a run, which reads as the search breaking."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    os.chmod(blocked, 0o500)
    try:
        code, payload = doctor(blocked)
    finally:
        os.chmod(blocked, 0o700)

    assert code == 3
    assert check(payload, "runs dir")["ok"] is False
    assert list(blocked.iterdir()) == []


def test_doctor_reports_a_signed_out_browser_as_a_failure(
    runs_dir: Path, aside_home: Path, fake_aside: Path, daemon, monkeypatch
) -> None:
    """A signed-out browser fetches public pages perfectly and silently loses every page this
    tool exists to reach, so an empty account roster is not a healthy environment."""
    monkeypatch.setenv("FAKE_ASIDE_ACCOUNTS", "none")

    code, payload = doctor(runs_dir)

    assert code == 3
    assert check(payload, "aside account")["ok"] is False
    assert "Sign in" in check(payload, "aside account")["fix"]


def test_doctor_without_the_aside_binary_says_how_to_get_one(runs_dir: Path, aside_home: Path, daemon, monkeypatch) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload = doctor(runs_dir)

    assert code == 3
    assert check(payload, "aside binary")["ok"] is False
    assert "ULTRA_SEARCH_ASIDE_BIN" in check(payload, "aside binary")["detail"]
    assert check(payload, "aside binary")["fix"]


# --- setup and repl-api ------------------------------------------------------------------


def test_setup_without_npm_says_what_to_install(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin-without-npm"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)

    p = subprocess.run([sys.executable, str(SCRIPTS / "cli.py"), "setup"],
                       capture_output=True, text=True, env=dict(os.environ, PATH=str(bin_dir)), timeout=60)

    payload = json.loads(p.stdout.splitlines()[-1])
    assert p.returncode == 3
    assert payload["error"] == "aside_unavailable"
    assert "Node" in payload["fix"]


def test_repl_api_is_read_from_the_installed_daemon(aside_home: Path, fake_aside: Path) -> None:
    code, payload, _ = run_cli("repl-api")

    assert code == 0
    assert payload["tools"] == [{"name": "repl", "description": "fake repl API description"}]


def test_repl_api_without_a_daemon_is_an_aside_error(aside_home: Path, monkeypatch) -> None:
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_BIN", "/nonexistent/aside")

    code, payload, _ = run_cli("repl-api")

    assert code == 3
    assert payload["error"] == "aside_unavailable"


# --- the shared contract -----------------------------------------------------------------


@pytest.mark.parametrize("argv,command", [
    (["search"], "search"),
    (["fetch"], "fetch"),
    (["status", "--run", "a", "--group", "b"], "status"),
    (["no-such-command"], None),
    (["search", "q", "--wait", "-1"], "search"),
    (["search", "q", "--wait", "nan"], "search"),
    (["search", "q", "--timeout", "inf"], "search"),
    (["log", "--heartbeat", "0"], "log"),
    (["fetch", "https://e.test/", "--concurrency", "0"], "fetch"),
    (["fetch", "https://e.test/", "--max-chars", "-5"], "fetch"),
    (["fetch", "ftp://e.test/file"], "fetch"),
    (["fetch", "e.test/page"], "fetch"),
    (["map", "https://e.test/", "--max-urls", "0"], "map"),
    (["map", "https://e.test/", "--depth", "-1"], "map"),
    (["crawl", "https://e.test/", "--max-pages", "0"], "crawl"),
    (["crawl", "file:///etc/passwd"], "crawl"),
    (["sessions", "--limit", "-2"], "sessions"),
    (["show", "--item", "-1"], "show"),
])
def test_bad_arguments_answer_in_json_with_where_to_look(argv: list[str], command: str | None) -> None:
    """Every command promises one JSON line, and a caller that mistyped a flag is the one
    most in need of it. A number outside its range or a URL that is not a web page is refused
    before any work, the same way."""
    code, payload, text = run_cli(*argv)

    assert code == 2
    assert text.strip().startswith("{") and len(text.strip().splitlines()) == 1
    assert payload["ok"] is False and payload["error"] == "bad_arguments"
    assert payload["message"]
    assert payload["fix"] == (f"cli.py {command} --help" if command else "cli.py --help")


def test_the_version_is_the_packages() -> None:
    code, _, text = run_cli("--version")

    assert code == 0
    assert text.strip() == "ultra-search 1.0.0"


def test_the_runs_dir_default_is_named_for_where_it_is(capsys) -> None:
    _, _, text = run_cli("status", "--help")

    assert "under the current working directory" in text
    assert "current project" not in text


# --- what each command's help promises -----------------------------------------------------

COMMANDS = ["search", "resume", "status", "log", "result", "show", "stop", "fetch", "map", "crawl",
            "sessions", "repl-api", "doctor", "setup"]


def help_of(command: str) -> str:
    code, _, text = run_cli(command, "--help")
    assert code == 0
    return text


@pytest.mark.parametrize("command", COMMANDS)
def test_every_help_stands_on_its_own(command: str) -> None:
    """A caller reads one command's help, at the moment it needs it. A pointer to another
    command's help is a second lookup at the worst moment."""
    assert "As for" not in help_of(command)


@pytest.mark.parametrize("command", ["search", "resume", "log"])
def test_next_is_explained_for_a_caller_nothing_will_wake(command: str) -> None:
    text = help_of(command)

    assert "run_in_background" in text and "foreground" in text and "bash_timeout_ms" in text


def test_result_help_names_every_end_state_and_what_opened_means() -> None:
    text = help_of("result")

    for state in ("completed", "completed_with_orphans", "completed_unstructured", "failed", "abandoned"):
        assert state in text
    assert "opened" in text and "not a check" in text


def test_fetch_help_names_every_item_status_and_what_conversion_loses() -> None:
    text = help_of("fetch")

    for status in ("ok", "shell", "shell_escalated", "challenge", "blocked", "needs_ocr", "unsupported", "error"):
        assert f"{status}:" in text, status
    assert "--format html" in text and "original_path" in text and "tables" in text


def test_show_says_how_sources_are_counted() -> None:
    assert "Source index from `result`, counting from 0" in help_of("show")


def test_map_help_says_what_it_does_not_do() -> None:
    assert "without extracting or saving pages" in help_of("map")


def test_crawl_help_says_which_flags_apply_to_a_manifest() -> None:
    text = help_of("crawl")

    assert "With --from" in text
    for flag in ("--max-pages", "--via", "--concurrency", "--no-frontmatter", "--out"):
        assert flag in text.split("With --from", 1)[1].split("\n", 1)[0], flag
