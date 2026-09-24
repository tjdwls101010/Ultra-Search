"""What one run found: its own turn of the session, that turn's children, and their sum.

A resumed run appends to a transcript that already holds every earlier turn, so "the
transcript" and "this run" are different things. Every command that reports what a run
found -- the result the supervisor writes, `status`, `show`, `log` -- reads it through this
one view, so they cannot disagree about which turn and which children are the run's.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import _events
import _registry


@dataclass
class Turn:
    #: Whether this run's prompt has appeared in its transcript. Until it has, everything
    #: there belongs to earlier turns, and none of it is this run's evidence.
    observed: bool
    #: Line index of this run's prompt in the transcript.
    start_line: int = 0
    events: list[_events.Event] = field(default_factory=list)
    #: Children spawned in this turn, in spawn order.
    children: list[str] = field(default_factory=list)
    child_events: dict[str, list[_events.Event]] = field(default_factory=dict)

    def sources(self) -> list[_events.Source]:
        """Every URL the turn and its children touched, one entry per URL."""
        return _events.merge_sources(
            [_events.collect_sources(self.events)]
            + [_events.collect_sources(self.child_events[cid]) for cid in self.children]
        )

    def answer(self, sources: list[_events.Source] | None = None) -> str:
        """The turn's answer, each child's appended under its id.

        Citations resolve against every source of the turn: a parent routinely cites what
        its child read, by the child's id.
        """
        sources = self.sources() if sources is None else sources
        answer = _events.final_answer(self.events, sources)
        for cid in self.children:
            ctext = _events.final_answer(self.child_events[cid], sources)
            if ctext:
                answer = f"{answer}\n\n--- child {cid} ---\n{ctext}" if answer else ctext
        return answer

    def usage(self) -> dict:
        total = _events.total_usage(self.events)
        for cid in self.children:
            for k, v in _events.total_usage(self.child_events[cid]).items():
                total[k] = round(total.get(k, 0) + v, 6) if k == "cost" else total.get(k, 0) + v
        return total

    def tool_results(self) -> list[_events.Event]:
        """This turn's own tool results, in order -- what `show --item N` counts."""
        return [e for e in self.events if e.kind == "tool_result"]

    def source_text(self, url: str) -> str:
        """What the turn already read of a URL: the page a tool opened, else a listing's excerpt.

        A URL usually appears twice -- once as a search result, once as the page a later
        fetch actually read -- and the read page is the one worth returning, whichever
        stream and whichever order it came in.
        """
        fallback = ""
        for events in [self.events, *(self.child_events[cid] for cid in self.children)]:
            for e in events:
                if e.kind != "tool_result":
                    continue
                if not any(isinstance(s, dict) and s.get("url") == url for s in (e.details or {}).get("sources") or []):
                    continue
                if _events.is_opening_tool(e.tool_name) and e.content:
                    return e.content
                fallback = fallback or e.content
        return fallback


def turn_of(run: _registry.Run) -> Turn:
    meta = run.meta()
    marker = meta.get("marker") or _registry.marker_for(run.run_id)
    events, _ = _events.read_events(run.session_transcript)
    start = _events.turn_start_index(events, marker)
    if start is None:
        return Turn(observed=False)
    mine = events[start:]
    children = _events.child_session_ids(mine)
    return Turn(
        observed=True,
        start_line=mine[0].index,
        events=mine,
        children=children,
        child_events={cid: _from(_events.read_events(run.child_transcript(cid))[0], mine[0].timestamp)
                      for cid in children},
    )


def _from(events: list[_events.Event], since: int) -> list[_events.Event]:
    """A child's part in this turn: from the first prompt it received after the turn began.

    A resumed parent can hand an earlier child a new task, and the child's transcript then
    holds the earlier run's work too. Without timestamps to go by, all of it is this turn's.
    """
    if since:
        for i, e in enumerate(events):
            if e.kind == "user" and e.timestamp >= since:
                return events[i:]
    return events


def child_is_terminal(events: list[_events.Event]) -> bool:
    """A child is done when its last turn stopped for a reason other than a tool call.

    The LAST event, not the last assistant one: a user turn after a finished answer means a
    new turn has begun. And the stop reason alone decides it -- requiring text as well would
    call a child that honestly found nothing, and said so by stopping, an orphan.
    """
    if not events:
        return False
    last = events[-1]
    if last.kind != "assistant":
        return False
    if last.stop_reason:
        return last.stop_reason != "toolUse"
    # No stop reason recorded at all: fall back to whether it produced anything.
    return bool(last.text.strip())
