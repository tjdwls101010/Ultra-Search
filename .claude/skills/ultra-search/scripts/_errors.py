"""The failure half of the CLI contract.

Every command prints one JSON line whether it worked or not, so a caller parses one
shape rather than branching on stderr. Each error carries the recovery step in the
payload: the message is read at the moment it matters, which is the only moment
anyone reads documentation.
"""
from __future__ import annotations

EXIT_ARGS = 2
EXIT_ASIDE = 3
EXIT_RUN_FAILED = 4
EXIT_EMPTY = 5


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


class EmptyResult(UltraSearchError):
    """No result data was produced; this does not establish a negative finding."""

    exit_code = EXIT_EMPTY
    kind = "empty_result"
