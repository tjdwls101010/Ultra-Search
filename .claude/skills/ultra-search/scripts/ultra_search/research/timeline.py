"""A run's events as the lines `log` answers with: this run's turn and its children's, each event rendered at a level."""
from __future__ import annotations

from ultra_search import runs
from ultra_search.research import evidence, render


def lines_of(run: runs.Run, *, level: str) -> list[str]:
    """Every event of the run's turn and its children's, once, as lines; the turn's own tool results numbered #N as
    `show --item` counts them.

    Bounded the way `show` and `result` bound the run: a resumed run's earlier turns, and a turn the session went on
    to afterwards, belong to other runs, and so does a task the session's next turn gave a child.
    """
    turn = evidence.turn_of(run)
    if not turn.observed:
        return []
    ordinals = {e.index: n for n, e in enumerate(turn.tool_results())} if level in ("steps", "full") else {}
    lines: list[str] = []
    for key, events in [("", turn.events), *((cid, turn.child_events[cid]) for cid in sorted(turn.children))]:
        prefix = f"[child {key}]" if key else ""
        for e in events:
            rendered = render.render(e, level=level, ordinal=None if key else ordinals.get(e.index))
            # Every line, not just the first: a child's second call or the body of its
            # answer would otherwise read as the parent's.
            for line in rendered.splitlines():
                lines.append(f"{prefix} {line}" if prefix and line else prefix or line)
    return lines
