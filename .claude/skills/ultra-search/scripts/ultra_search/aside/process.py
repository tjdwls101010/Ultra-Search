"""The aside binary: finding it, starting `aside exec`, and where its daemon answers.

`aside exec` is spawned detached, for the reason the supervisor is: the process that starts
the work is a Bash tool call that will be cut off at a timeout the work does not respect,
and killing the CLI was measured leaving the daemon-side work running and still spending
credits.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ultra_search.outcome import AsideUnavailable

DEFAULT_BIN = "aside"
#: What `aside exec` accepts for --effort and --speed.
EFFORTS = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "ultrabrowse")
SPEEDS = ("default", "fast")
#: The versions this skill's behaviour was measured against. `doctor` compares both,
#: because they move independently and it is the daemon that decides what a run records:
#: between two daemon builds, ephemeral CLI sessions stopped writing state.db rows
#: entirely while still writing full transcripts to disk.
VERIFIED_VERSION = "1.26.810.1915"
VERIFIED_DAEMON_VERSION = "1.26.1001.14"


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


def start_exec(prompt: str, *, stdout_path: str | os.PathLike[str], session: str | None = None,
               effort: str | None = None, model: str | None = None, speed: str | None = None,
               cwd: str | os.PathLike[str] | None = None) -> subprocess.Popen:
    """Start `aside exec` detached, streaming its stdout to a file the supervisor tails.

    The returned process's `args` is the argv it was started with.
    """
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
        cwd=cwd,
    )


def version() -> str:
    try:
        p = subprocess.run([aside_bin(), "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"could not run `aside --version`: {e}") from e
    return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else ""
