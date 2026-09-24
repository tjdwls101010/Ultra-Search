"""Starting `aside exec`, and starting the supervisor that watches it.

Both spawns are detached on purpose, for the same reason: the process that starts the
work is a Bash tool call that will be cut off at a timeout the work does not respect.
A supervisor that died with its caller would leave the run going with nobody recording
it -- and the run does keep going, because killing the CLI was measured leaving the
daemon-side work running and still spending credits.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from _contract import AsideUnavailable

DEFAULT_BIN = "aside"
#: The versions this skill's behaviour was measured against. `doctor` compares both,
#: because they move independently and it is the daemon that decides what a run records:
#: between two daemon builds, ephemeral CLI sessions stopped writing state.db rows
#: entirely while still writing full transcripts to disk.
VERIFIED_VERSION = "1.26.810.1915"
VERIFIED_DAEMON_VERSION = "1.26.829.1514"


def aside_bin() -> str:
    explicit = os.environ.get("ULTRA_SEARCH_ASIDE_BIN")
    if explicit:
        if not Path(explicit).exists():
            raise AsideUnavailable(
                f"ULTRA_SEARCH_ASIDE_BIN points at {explicit}, which does not exist",
                fix="Unset it to use the aside on PATH.",
            )
        return explicit
    found = shutil.which(DEFAULT_BIN)
    if not found:
        raise AsideUnavailable(
            "no `aside` on PATH",
            fix="Install the Aside CLI, or set ULTRA_SEARCH_ASIDE_BIN to its path.",
        )
    return found


def exec_argv(prompt: str, *, session: str | None = None, effort: str | None = None,
              model: str | None = None, speed: str | None = None) -> list[str]:
    argv = [aside_bin(), "exec"]
    if session:
        argv += ["--session", session]
    if effort:
        argv += ["--effort", effort]
    if model:
        argv += ["--model", model]
    if speed:
        argv += ["--speed", speed]
    # The prompt goes last and unquoted-as-one-argument: passing it on stdin mixes the
    # daemon's interactive banner into the stream.
    argv.append(prompt)
    return argv


def spawn_exec(argv: list[str], stdout_path: str | os.PathLike[str]) -> subprocess.Popen:
    """Run `aside exec`, streaming its stdout to a file the supervisor tails."""
    out = Path(stdout_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    handle = out.open("ab")
    return subprocess.Popen(
        argv,
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def spawn_supervisor(run_path: str | os.PathLike[str]) -> int:
    """Start the detached supervisor for a run and return its pid.

    setsid, and output to a file rather than a pipe: an inherited pipe would keep the
    supervisor's lifetime tied to a reader that is about to go away, which is the exact
    coupling this is here to break.
    """
    run = Path(run_path)
    log = run / "supervisor.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("ab")
    script = Path(__file__).resolve().parent / "_supervisor.py"
    proc = subprocess.Popen(
        [sys.executable, str(script), "--run-path", str(run)],
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        cwd=str(run),
    )
    return proc.pid


def version() -> str:
    try:
        p = subprocess.run([aside_bin(), "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"could not run `aside --version`: {e}") from e
    return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else ""
