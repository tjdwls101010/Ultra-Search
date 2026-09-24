"""What one run found: its own turn of the session, that turn's children, and their sum.

A resumed run appends to a transcript that already holds every earlier turn, so "the
transcript" and "this run" are different things. Every command that reports what a run
found -- the result the supervisor writes, `status`, `show`, `log` -- reads it through this
one view, so they cannot disagree about which turn and which children are the run's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ultra_search.aside import transcript
from ultra_search.contract import is_safe_id
from ultra_search.runs import registry


#: Tools whose result means the agent actually read a page, rather than merely being
#: shown it in a result list. The distinction is what `opened` reports.
_OPENING_TOOLS = frozenset({"webfetch", "repl", "read_file"})

def is_opening_tool(name: str) -> bool:
    """Whether this tool's result means the agent read the page rather than just listing it."""
    return name in _OPENING_TOOLS


_CITATION_RE = re.compile(r'<citation\s+refs="([^"]*)"\s*>(.*?)</citation>', re.DOTALL)


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


def final_answer(events: list[transcript.Event], sources: list[Source] | None = None) -> str:
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
        if e.kind == "assistant" and e.stop_reason and e.stop_reason != "toolUse":
            text = e.text
    if not text.strip():
        return ""
    return resolve_citations(text, sources if sources is not None else collect_sources(events))


def resolve_citations(text: str, sources: list[Source]) -> str:
    by_id = {i: s for s in sources for i in s.ids}

    def sub(m: re.Match[str]) -> str:
        refs = [r.strip() for r in m.group(1).split(",") if r.strip()]
        label = m.group(2).strip()
        urls = []
        for ref in refs:
            hit = by_id.get(ref) or next((s for i, s in by_id.items() if ref.startswith(i)), None)
            if hit and hit.url and hit.url not in urls:
                urls.append(hit.url)
        if not urls:
            return label
        return f"{label} ({', '.join(urls)})" if label else f"({', '.join(urls)})"

    return _CITATION_RE.sub(sub, text)


def collect_sources(events: list[transcript.Event]) -> list[Source]:
    """Every URL the run touched, in order, deduplicated by URL.

    ``opened`` separates a URL the agent was shown in a result list from one it actually
    read. Treating the two alike is how a report ends up citing a search snippet as
    though someone had checked the page.
    """
    out: list[Source] = []
    seen: dict[str, Source] = {}
    for e in events:
        if e.kind != "tool_result":
            continue
        opened = e.tool_name in _OPENING_TOOLS
        for raw in (e.details or {}).get("sources") or []:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            sid = str(raw.get("id") or "")
            s = Source(
                url=url,
                title=str(raw.get("title") or ""),
                id=sid,
                excerpt=str(raw.get("excerpt") or ""),
                published=str(raw.get("publishDate") or raw.get("published") or ""),
                opened=opened,
                ids=[sid] if sid else [],
            )
            existing = seen.get(url)
            if existing:
                existing.absorb(s)
                continue
            seen[url] = s
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


def turn_start_index(events: list[transcript.Event], marker: str) -> int | None:
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


def has_terminal_answer(events: list[transcript.Event]) -> bool:
    """Whether an assistant turn has finished here, as opposed to stopping to call a tool.

    An empty answer still counts: a run that honestly found nothing has finished.
    """
    for e in events:
        if e.kind == "assistant" and e.stop_reason and e.stop_reason != "toolUse":
            return True
    return False


def child_session_ids(events: list[transcript.Event]) -> list[str]:
    """Child sessions spawned by this run, in spawn order.

    Read from the parent's own transcript rather than the database, because an ephemeral
    CLI session and its children may never appear there at all. An id that could not be a
    session id is skipped: it becomes a file name in the run directory.
    """
    out: list[str] = []
    for e in events:
        if e.kind != "tool_result" or not e.tool_name.startswith("subagent"):
            continue
        det = e.details or {}
        for key in ("taskId", "task_id", "sessionId", "session_id"):
            val = det.get(key)
            if is_safe_id(val) and val not in out:
                out.append(val)
        for r in det.get("results") or []:
            if isinstance(r, dict):
                val = r.get("taskId") or r.get("task_id")
                if is_safe_id(val) and val not in out:
                    out.append(val)
    return out


def total_usage(events: list[transcript.Event]) -> dict:
    keys = ("input", "output", "cacheRead", "cacheWrite", "reasoning", "totalTokens")
    acc = dict.fromkeys(keys, 0)
    cost = 0.0
    for e in events:
        u = e.usage or {}
        for k in keys:
            try:
                acc[k] += int(u.get(k) or 0)
            except (TypeError, ValueError):
                pass
        c = u.get("cost")
        if isinstance(c, dict):
            try:
                cost += float(c.get("total") or 0)
            except (TypeError, ValueError):
                pass
        elif isinstance(c, (int, float)):
            cost += float(c)
    return {
        "input": acc["input"],
        "output": acc["output"],
        "cache_read": acc["cacheRead"],
        "cache_write": acc["cacheWrite"],
        "reasoning": acc["reasoning"],
        "total_tokens": acc["totalTokens"],
        "cost": round(cost, 6),
    }


# --- one run's view --------------------------------------------------------------


@dataclass
class Turn:
    #: Whether this run's prompt has appeared in its transcript. Until it has, everything
    #: there belongs to earlier turns, and none of it is this run's evidence.
    observed: bool
    #: Line index of this run's prompt in the transcript.
    start_line: int = 0
    events: list[transcript.Event] = field(default_factory=list)
    #: Children spawned in this turn, in spawn order.
    children: list[str] = field(default_factory=list)
    child_events: dict[str, list[transcript.Event]] = field(default_factory=dict)

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

    def tool_results(self) -> list[transcript.Event]:
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
                if is_opening_tool(e.tool_name) and e.content:
                    return e.content
                fallback = fallback or e.content
        return fallback


def turn_of(run: registry.Run) -> Turn:
    meta = run.meta()
    marker = meta.get("marker") or registry.marker_for(run.run_id)
    events, _ = transcript.read_events(run.session_transcript)
    start = turn_start_index(events, marker)
    if start is None:
        return Turn(observed=False)
    mine = events[start:]
    children = child_session_ids(mine)
    return Turn(
        observed=True,
        start_line=mine[0].index,
        events=mine,
        children=children,
        child_events={cid: _from(transcript.read_events(run.child_transcript(cid))[0], mine[0].timestamp)
                      for cid in children},
    )


def _from(events: list[transcript.Event], since: int) -> list[transcript.Event]:
    """A child's part in this turn: from the first prompt it received after the turn began.

    A resumed parent can hand an earlier child a new task, and the child's transcript then
    holds the earlier run's work too. With no prompt that recent, the whole transcript is
    this turn's -- which is right for a turn that only collects a child's late result.
    """
    # 성진: 재사용 자식의 새 프롬프트가 아직 안 보인 짧은 창에서는 이전 과제가 이 런 몫으로 보인다; 자식이 받은 과제를 부모 전사에서 식별할 수 있게 되면 그걸로 가른다.
    if since:
        for i, e in enumerate(events):
            if e.kind == "user" and e.timestamp >= since:
                return events[i:]
    return events


def child_is_terminal(events: list[transcript.Event]) -> bool:
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
