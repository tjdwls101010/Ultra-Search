"""The CLI's contract: exit codes, run states, errors, and what an id may be.

Every command prints one JSON line whether it worked or not, so a caller parses one
shape rather than branching on stderr. Each error carries the recovery step in the
payload: the message is read at the moment it matters, which is the only moment
anyone reads documentation.
"""
from __future__ import annotations

import re

EXIT_OK = 0
EXIT_ARGS = 2
EXIT_ASIDE = 3
EXIT_RUN_FAILED = 4
EXIT_EMPTY = 5

#: Every state a run can end in. Anything else is still going.
TERMINAL_STATES = frozenset({"completed", "completed_with_orphans", "completed_unstructured", "failed", "abandoned"})
#: Ends that exit EXIT_RUN_FAILED. `abandoned` is one: the watching stopped, not the work.
FAILED_STATES = frozenset({"failed", "abandoned"})


#: Run, session and child ids each become one path segment. Starting with a letter or digit
#: and staying in this set rules out "." and ".." and any separator, so an id read from the
#: command line or from a transcript cannot name a path outside the directory it is joined to.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


def is_safe_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))


class UltraSearchError(Exception):
    exit_code = EXIT_ARGS
    kind = "error"

    def __init__(self, message: str, fix: str = "", **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.fix = fix
        self.extra = extra

    def payload(self) -> dict:
        out = {"ok": False, "error": self.kind, "message": self.message}
        if self.fix:
            out["fix"] = self.fix
        out.update(self.extra)
        return out


class ArgumentError(UltraSearchError):
    """The caller asked for something the CLI will not do -- refused before any work."""

    exit_code = EXIT_ARGS
    kind = "bad_arguments"


class AsideUnavailable(UltraSearchError):
    """The aside binary is missing, or its daemon will not answer.

    Never a hang: a command that cannot reach the daemon says so and exits, because a
    caller waiting on a dead daemon is indistinguishable from one waiting on slow work.
    """

    exit_code = EXIT_ASIDE
    kind = "aside_unavailable"

    def __init__(self, message: str, fix: str = "Open the Aside app, then re-run `doctor`.", **extra: object) -> None:
        super().__init__(message, fix, **extra)


class RunFailed(UltraSearchError):
    """A run ended without a usable answer, or was abandoned while still going."""

    exit_code = EXIT_RUN_FAILED
    kind = "run_failed"

