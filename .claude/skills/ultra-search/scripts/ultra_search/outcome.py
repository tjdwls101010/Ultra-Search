"""How a command ends: its reply, which kind of ending it was, and errors that carry a recovery step.

Every command answers with one JSON document whether it worked or not, so a caller parses one
shape rather than branching on stderr. Each error carries the recovery step in the payload:
the message is read at the moment it matters, which is the only moment anyone reads
documentation. Which exit code an ending is belongs to `cli.py`, which owns the command line.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The command did its work; the payload's states say how that work went.
OK = "ok"
#: Refused before any work: the arguments ask for something the CLI will not do.
BAD_ARGUMENTS = "bad_arguments"
#: The aside binary is missing, or its daemon will not answer.
ASIDE_UNAVAILABLE = "aside_unavailable"
#: A run failed or was abandoned, nothing was saved, or a file could not be read or written.
FAILED = "failed"
#: Nothing came back: no answer and no sources, no session, nothing a map could read.
EMPTY = "empty"


@dataclass
class Reply:
    payload: dict
    outcome: str = OK


class UltraSearchError(Exception):
    outcome = BAD_ARGUMENTS
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

    outcome = BAD_ARGUMENTS
    kind = "bad_arguments"


class RunNotFound(ArgumentError):
    """No run has this id, or begins with it."""


class AmbiguousRun(ArgumentError):
    """Several runs begin with this prefix; the error names them."""


class AsideUnavailable(UltraSearchError):
    """The aside binary is missing, or its daemon will not answer.

    Never a hang: a command that cannot reach the daemon says so and exits, because a
    caller waiting on a dead daemon is indistinguishable from one waiting on slow work.
    """

    outcome = ASIDE_UNAVAILABLE
    kind = "aside_unavailable"

    def __init__(self, message: str, fix: str = "Open the Aside app, then re-run `doctor`.", **extra: object) -> None:
        super().__init__(message, fix, **extra)


class RunFailed(UltraSearchError):
    """A run ended without a usable answer, or was abandoned while still going."""

    outcome = FAILED
    kind = "run_failed"
