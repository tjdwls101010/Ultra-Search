"""Delegated investigations: starting them (`search`, `resume`), watching them (`status`, `log`, `stop`), and collecting what they found (`result`, `show`), plus the Aside sessions they can continue (`sessions`)."""
from ultra_search.research.commands import log, result, resume, search, sessions, show, status, stop
from ultra_search.research.render import LEVELS
from ultra_search.research.supervisor import run_detached, supervise

__all__ = [
    "LEVELS",
    "log",
    "result",
    "resume",
    "run_detached",
    "search",
    "sessions",
    "show",
    "status",
    "stop",
    "supervise",
]
