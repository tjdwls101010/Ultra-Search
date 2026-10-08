"""Delegated investigations: starting them (`search`, `resume`), waiting for and collecting what they found (`result`, `show`), retracing how (`log`), plus the Aside sessions they can continue (`sessions`)."""
from ultra_search.research.commands import log, result, resume, search, sessions, show
from ultra_search.research.render import LEVELS
from ultra_search.research.supervisor import IDLE_LIMIT, run_detached, supervise

__all__ = [
    "IDLE_LIMIT",
    "LEVELS",
    "log",
    "result",
    "resume",
    "run_detached",
    "search",
    "sessions",
    "show",
    "supervise",
]
