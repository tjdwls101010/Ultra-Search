"""What one run found: its own turn of the session, that turn's children, and their sum.

A resumed run appends to a transcript that already holds every earlier turn, so "the
transcript" and "this run" are different things. Every command that reports what a run
found -- the result the supervisor writes, `status`, `show`, `log` -- reads it through this
one view, so they cannot disagree about which turn and which children are the run's.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ultra_search import aside, runs
from ultra_search.ids import is_safe_id
from ultra_search.research.marker import marker_for


@dataclass
class Source:
    url: str
    title: str = ""
    id: str = ""
    excerpt: str = ""
    published: str = ""
    opened: bool = False
    #: Every id a citation may use for this URL. Two tools, or a parent and its child, can
    #: list one page under different ids, and a citation to either has to resolve.
    ids: list[str] = field(default_factory=list)

    def absorb(self, other: "Source") -> None:
        self.opened = self.opened or other.opened
        for i in other.ids:
            if i not in self.ids:
                self.ids.append(i)


def final_answer(events: list[aside.Event], sources: list[Source] | None = None) -> str:
    """The text of the last finished assistant turn, with citation tags resolved to URLs.

    Only a turn that stopped for a reason other than calling a tool is an answer; text beside
    a tool call is the worker narrating what it is about to do. A run that ends mid-tool, or
    whose last finished turn said nothing, has no answer: the caller gets "" and decides
    whether that is an honest zero or an interrupted run -- this module will not guess.
    """
    # Only the latest turn: a child given a second task keeps its transcript, and until the
    # new task finishes the answer in it is to the old one.
    last_prompt = max((i for i, e in enumerate(events) if e.kind == "user"), default=0)
    text = ""
    for e in events[last_prompt:]:
        if e.kind == "assistant" and e.stopped:
            text = e.text
    if not text.strip():
        return ""
    sources = sources if sources is not None else collect_sources(events)
    return aside.resolve_answer_tags(text, {i: s.url for s in sources for i in s.ids if s.url})


def collect_sources(events: list[aside.Event]) -> list[Source]:
    """Every URL the run touched, in order, deduplicated by URL.

    ``opened`` separates a URL the agent was shown in a result list from one it actually
    read. Treating the two alike is how a report ends up citing a search snippet as
    though someone had checked the page.
    """
    out: list[Source] = []
    seen: dict[str, Source] = {}
    for e in events:
        for ref in e.sources:
            s = Source(url=ref.url, title=ref.title, id=ref.id, excerpt=ref.excerpt, published=ref.published,
                       opened=ref.opened, ids=[ref.id] if ref.id else [])
            existing = seen.get(ref.url)
            if existing:
                existing.absorb(s)
                continue
            seen[ref.url] = s
            out.append(s)
    return out


def merge_sources(lists: list[list[Source]]) -> list[Source]:
    """Several streams' sources as one list, one entry per URL, first seen first.

    A URL one stream only listed and another opened was read, and keeps every id either
    stream cited it by.
    """
    out: list[Source] = []
    seen: dict[str, Source] = {}
    for sources in lists:
        for s in sources:
            if s.url in seen:
                seen[s.url].absorb(s)
                continue
            merged = Source(url=s.url, title=s.title, id=s.id, excerpt=s.excerpt, published=s.published,
                            opened=s.opened, ids=list(s.ids))
            seen[s.url] = merged
            out.append(merged)
    return out


def turn_start_index(events: list[aside.Event], marker: str) -> int | None:
    """Index of the user message that began this run's turn, or None if it is not there yet.

    A resumed run appends to a transcript that already holds earlier turns, so "the last
    assistant message" is the previous answer until the new one lands. The marker planted
    in the prompt is what separates the two; without this boundary a resume reports the
    answer to the question before it, and folds that turn's children and token usage into
    the new result.

    A fresh run's marker is in the first record, so the boundary is 0 and the whole
    transcript is this turn -- the same code path, not a special case. No marker means the
    turn has not landed, which is not the same as the whole transcript being this turn.
    """
    for i in range(len(events) - 1, -1, -1):
        e = events[i]
        if e.kind == "user" and marker and marker in e.text:
            return i
    return None


def has_terminal_answer(events: list[aside.Event]) -> bool:
    """Whether the turn has given its answer, as opposed to stopping to call a tool.

    Where the daemon frames turns, only `finished` says so: a message that stopped earlier
    in the turn -- a report to the parent, a pause -- is followed by more work and the final
    answer. In the earlier format, any message that stopped for another reason than a tool
    call is the answer. An empty answer still counts: a run that honestly found nothing has
    finished.
    """
    if any(e.kind == "lifecycle" for e in events):
        return aside.turn_finished(events)
    return any(e.kind == "assistant" and e.stopped for e in events)


def child_session_ids(events: list[aside.Event]) -> list[str]:
    """Child sessions spawned by this run, in spawn order.

    Read from the parent's own transcript rather than the database, because an ephemeral
    CLI session and its children may never appear there at all. An id that could not be a
    session id is skipped: it becomes a file name in the run directory.
    """
    out: list[str] = []
    for e in events:
        for cid in e.child_ids:
            if is_safe_id(cid) and cid not in out:
                out.append(cid)
    return out


_USAGE = ("input", "output", "cache_read", "cache_write", "reasoning", "total_tokens")


def total_usage(events: list[aside.Event]) -> dict:
    acc = dict.fromkeys(_USAGE, 0)
    cost = 0.0
    for e in events:
        for k in _USAGE:
            acc[k] += e.usage.get(k, 0)
        cost += e.usage.get("cost", 0.0)
    return {**acc, "cost": round(cost, 6)}


# --- one run's view --------------------------------------------------------------


@dataclass
class Turn:
    #: Whether this run's prompt has appeared in its transcript. Until it has, everything
    #: there belongs to earlier turns, and none of it is this run's evidence.
    observed: bool
    #: Line index of this run's prompt in the transcript.
    start_line: int = 0
    events: list[aside.Event] = field(default_factory=list)
    #: Children spawned in this turn, in spawn order.
    children: list[str] = field(default_factory=list)
    child_events: dict[str, list[aside.Event]] = field(default_factory=dict)

    @property
    def framed(self) -> bool:
        """Whether the daemon framed this turn with lifecycle records: the format in which only `finished` ends it."""
        return any(e.kind == "lifecycle" for e in self.events)

    @property
    def finished(self) -> bool:
        return self.framed and aside.turn_finished(self.events)

    def unfinished_children(self) -> list[str]:
        """This turn's children still working, in spawn order."""
        return [cid for cid in self.children if not child_is_terminal(self.child_events[cid])]

    def ended_on_error(self) -> bool:
        """Whether the turn's last message stopped on an error. A turn can end that way and its process still exit 0."""
        said = [e for e in self.events if e.kind == "assistant"]
        return bool(said) and said[-1].stop == "error"

    def sources(self) -> list[Source]:
        """Every URL the turn and its children touched, one entry per URL."""
        return merge_sources(
            [collect_sources(self.events)]
            + [collect_sources(self.child_events[cid]) for cid in self.children]
        )

    def answer(self, sources: list[Source] | None = None) -> str:
        """The turn's answer, each child's appended under its id.

        Citations resolve against every source of the turn: a parent routinely cites what
        its child read, by the child's id.
        """
        sources = self.sources() if sources is None else sources
        answer = final_answer(self.events, sources)
        for cid in self.children:
            ctext = final_answer(self.child_events[cid], sources)
            if ctext:
                answer = f"{answer}\n\n--- child {cid} ---\n{ctext}" if answer else ctext
        return answer

    def usage(self) -> dict:
        total = total_usage(self.events)
        for cid in self.children:
            for k, v in total_usage(self.child_events[cid]).items():
                total[k] = round(total.get(k, 0) + v, 6) if k == "cost" else total.get(k, 0) + v
        return total

    def tool_results(self) -> list[aside.Event]:
        """This turn's own tool results, in order -- what `show --item N` counts."""
        return [e for e in self.events if e.kind == "tool_result"]

    def source_text(self, url: str) -> str:
        """What the turn already read of a URL: the fullest result that holds the page, else a
        notice that a tab opened on it, else a listing's excerpt.

        A URL usually appears more than once -- as a search result, as a tab being opened, as
        the page then read -- and the read page is the one worth returning, whichever stream
        and whichever order it came in.
        """
        read, opened, listed = "", "", ""
        for events in [self.events, *(self.child_events[cid] for cid in self.children)]:
            for e in events:
                named = [s for s in e.sources if s.url == url]
                if not named:
                    continue
                if any(s.opened and s.holds_page for s in named):
                    read = max(read, e.content, key=len)
                elif any(s.opened for s in named):
                    opened = opened or e.content
                listed = listed or e.content
        return read or opened or listed


def turn_of(run: runs.Run) -> Turn:
    meta = run.meta()
    marker = meta.get("marker") or marker_for(run.run_id)
    events, _ = aside.read_events(run.session_transcript)
    start = turn_start_index(events, marker)
    if start is None:
        return Turn(observed=False)
    opened_at = events[start].timestamp
    mine = events[_framed(events, start):_turn_end(events, start)]
    children = child_session_ids(mine)
    return Turn(
        observed=True,
        start_line=mine[0].index,
        events=mine,
        children=children,
        child_events={cid: _from(aside.read_events(run.child_transcript(cid))[0], opened_at)
                      for cid in children},
    )


def _framed(events: list[aside.Event], prompt: int) -> int:
    """Where the turn that opens with the prompt at ``prompt`` begins: at its `started`
    record, if it has one. A turn cut at its prompt has lost the record that says it began,
    and without it a message that stopped mid-turn reads as the turn's end. Records can sit
    between the two -- a system message, attachment metadata -- but no conversation does."""
    i = prompt - 1
    while i >= 0 and events[i].kind not in ("user", "assistant", "tool_result"):
        if events[i].kind == "lifecycle" and events[i].lifecycle == "started":
            return i
        i -= 1
    return prompt


def _turn_end(events: list[aside.Event], prompt: int) -> int:
    """Where the turn that opens with the prompt at ``prompt`` ends: just past its `finished` record, or where a next turn's `started` begins. A session continued after this run appends that next turn to the same transcript, and without an end this run would take its answer, sources and children for its own."""
    for i in range(prompt + 1, len(events)):
        if events[i].kind == "lifecycle" and events[i].lifecycle in ("finished", "started"):
            return i + 1 if events[i].lifecycle == "finished" else i
    return len(events)


def _from(events: list[aside.Event], since: int) -> list[aside.Event]:
    """A child's part in this turn: from the first prompt it received after the turn began.

    A resumed parent can hand an earlier child a new task, and the child's transcript then
    holds the earlier run's work too. With no prompt that recent, the whole transcript is
    this turn's -- which is right for a turn that only collects a child's late result.
    """
    # 성진: 재사용 자식의 새 프롬프트가 아직 안 보인 짧은 창에서는 이전 과제가 이 런 몫으로 보인다; 자식이 받은 과제를 부모 전사에서 식별할 수 있게 되면 그걸로 가른다.
    if since:
        for i, e in enumerate(events):
            if e.kind == "user" and e.timestamp >= since:
                return events[_framed(events, i):]
    return events


def child_is_terminal(events: list[aside.Event]) -> bool:
    """A child is done when its last turn has ended -- a new task given to it after an
    answer is a turn still going."""
    return aside.turn_finished(events)
