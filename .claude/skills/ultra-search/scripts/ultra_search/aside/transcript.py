"""The session transcript, as events in this skill's terms.

Aside writes one JSON object per line to a session's ``messages.jsonl`` while the run is
still going, so this module reads by byte cursor and stops at the last newline: a line
being written is half a line, and parsing it would either crash or invent a record.

Everything that depends on how Aside spells a record -- its roles, its stop reasons, where a
tool result keeps its sources and a subagent's id, its usage keys, its tool names -- is read
here and handed on as an `Event`. Nothing here drops a record it does not recognise: this
file is a private surface of another product, and when it changes an unfamiliar shape
arriving as ``raw`` degrades a report, while a dropped one silently shortens it and nobody
finds out.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Tools whose result means the agent read a page, rather than being shown it in a list.
_OPENING_TOOLS = frozenset({"webfetch", "repl", "read_file"})
#: The browser REPL lists no sources; it prints the pages it touched, each on a line of its
#: own: opening a tab says "...Opened a new tab ..., page → <title> (<url>)", and a snapshot of
#: a page starts `- title: "<title>" [url=<url>]`. Anchored to those lines, so page text that
#: happens to mention a page is not taken for one.
_PAGE_PRINTED = re.compile(
    r'^\S*\s*Opened a new tab\b.*?, page → (?P<tab_title>.*?) \((?P<tab_url>https?://.+)\)[ \t]*$'
    r'|^- title: "(?P<snap_title>.*)" \[url=(?P<snap_url>https?://[^\]\s]+)\]',
    re.M,
)
#: Arguments that name something outside the session -- the thing a call reached for. A local
#: path or an offset says how the worker asked, not what it went after.
_TARGET_KEYS = ("url", "objective", "description", "title")
_HOST_RE = re.compile(r"^https?://([^/]+)")
_USAGE_KEYS = {"input": "input", "output": "output", "cacheRead": "cache_read", "cacheWrite": "cache_write",
               "reasoning": "reasoning", "totalTokens": "total_tokens"}


@dataclass
class ToolCall:
    name: str
    #: The call's arguments as the worker wrote them.
    arguments: object
    #: What the call reached for, on one line: a URL's host, an objective, a description; "" when none.
    target: str = ""


@dataclass
class SourceRef:
    """A page a tool result named: listed by a search, or opened by a tool that reads pages."""

    url: str
    title: str = ""
    id: str = ""
    excerpt: str = ""
    published: str = ""
    #: Whether a page-opening tool returned it -- an inference that it was read, not a check of what it said.
    opened: bool = False


@dataclass
class Event:
    """One transcript record: user, assistant, tool_result, system, lifecycle, or raw (anything unfamiliar)."""

    kind: str
    index: int
    timestamp: int = 0
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str = ""
    content: str = ""
    is_error: bool = False
    #: Why an assistant message stopped: "tool" to call one, "error", "end" for anything else, "" when not recorded.
    stop: str = ""
    #: For a `lifecycle` event, which boundary of a turn it marks: started, final-started, finished.
    lifecycle: str = ""
    sources: list[SourceRef] = field(default_factory=list)
    #: Sessions a tool result says were spawned or continued as subagents, as Aside named them.
    child_ids: list[str] = field(default_factory=list)
    #: input, output, cache_read, cache_write, reasoning, total_tokens and cost, as numbers; {} when not recorded.
    usage: dict = field(default_factory=dict)
    unknown_blocks: list = field(default_factory=list)
    #: A tool result's own structured detail, unread here: handed out whole on request.
    details: dict = field(default_factory=dict)
    #: The record as stored, for a reader who asked for it unchanged.
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def stopped(self) -> bool:
        """An assistant message that ended its turn's work rather than pausing to call a tool."""
        return self.stop in ("end", "error")


def read_events(path: str | Path, since: int = 0) -> tuple[list[Event], int]:
    """Events appended after byte ``since``, and the cursor to resume from.

    The cursor only ever advances past a trailing newline, so a caller polling a live
    session never sees a torn record and never re-reads a whole one.
    """
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return [], since
    if size <= since:
        # A shrunk file means the source was rotated or cleaned up underneath us. Report
        # no progress rather than re-reading from a position that now means something else.
        return [], min(since, size)
    with p.open("rb") as f:
        f.seek(since)
        chunk = f.read(size - since)
    end = chunk.rfind(b"\n")
    if end == -1:
        return [], since
    complete = chunk[: end + 1]
    events = parse_lines(complete.decode("utf-8", "replace"), start_index=_count_lines_before(p, since))
    return events, since + len(complete)


def _count_lines_before(path: Path, offset: int) -> int:
    if offset <= 0:
        return 0
    with path.open("rb") as f:
        return f.read(offset).count(b"\n")


def parse_lines(text: str, start_index: int = 0) -> list[Event]:
    out: list[Event] = []
    for i, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        out.append(parse_record(line, start_index + i))
    return out


def parse_record(line: str, index: int = 0) -> Event:
    try:
        obj = json.loads(line)
    except ValueError:
        return Event(kind="raw", index=index, raw={"unparsed": line}, content=line)
    if not isinstance(obj, dict):
        return Event(kind="raw", index=index, raw={"unparsed": line}, content=line)

    role = obj.get("role")
    ts = int(obj.get("timestamp") or 0)
    if role == "user":
        return Event(kind="user", index=index, raw=obj, text=_flatten_text(obj.get("content")), timestamp=ts)
    if role == "assistant":
        return _assistant(obj, index, ts)
    if role == "toolResult":
        return _tool_result(obj, index, ts)
    if role == "turn-lifecycle":
        return Event(kind="lifecycle", index=index, raw=obj, lifecycle=str(obj.get("event") or ""), timestamp=ts)
    if role == "system-message":
        # Aside reports a subagent finishing this way. It is the one record a supervisor
        # most wants to see, so it gets a kind of its own rather than the raw fallback.
        return Event(kind="system", index=index, raw=obj, text=_as_text(obj.get("content")), timestamp=ts)
    return Event(kind="raw", index=index, raw=obj, content=json.dumps(obj, ensure_ascii=False), timestamp=ts)


def turn_finished(events: list[Event]) -> bool:
    """Whether the last turn in these events has ended, rather than stopped mid-work.

    Since mid-September 2026 the daemon frames every turn with lifecycle records, and the last
    one decides: `finished` closes the turn, and a `started` after it opens the next. The
    final message comes after `final-started`, and other records -- a subagent's report --
    can follow it, so the last message alone says nothing in this format.

    A transcript with no lifecycle records is the earlier format, where the last event
    decides: an assistant turn that stopped for a reason other than a tool call. With no stop
    reason recorded, a turn that said something has ended -- requiring text when a reason
    is recorded would call a child that honestly found nothing, and stopped, unfinished.
    """
    # 성진: 형식 두 가지를 함께 읽는다; 옛 형식의 근거는 260829 fixture뿐이니 그것들이 새 형식 녹화로 바뀌면 lifecycle 분기만 남긴다.
    marks = [e.lifecycle for e in events if e.kind == "lifecycle"]
    if marks:
        return marks[-1] == "finished"
    if not events:
        return False
    last = events[-1]
    if last.kind != "assistant":
        return False
    if last.stop:
        return last.stopped
    return bool(last.text.strip())


def _assistant(obj: dict, index: int, ts: int) -> Event:
    texts: list[str] = []
    calls: list[ToolCall] = []
    unknown: list = []
    blocks = obj.get("content")
    if isinstance(blocks, str):
        texts.append(blocks)
        blocks = []
    for block in blocks or []:
        if not isinstance(block, dict):
            unknown.append({"value": block})
            continue
        kind = block.get("type")
        if kind == "text":
            texts.append(str(block.get("text") or ""))
        elif kind == "thinking":
            continue
        elif kind == "toolCall":
            arguments = block.get("arguments") or {}
            calls.append(ToolCall(name=str(block.get("name") or ""), arguments=arguments, target=_target(arguments)))
        else:
            # An unfamiliar block type keeps its siblings: the text next to it is still
            # the answer, and losing the whole turn over one new block would hide it.
            unknown.append(block)
    reason = str(obj.get("stopReason") or "")
    return Event(
        kind="assistant",
        index=index,
        raw=obj,
        text="\n".join(t for t in texts if t),
        tool_calls=calls,
        usage=_usage(obj.get("usage")),
        stop={"": "", "toolUse": "tool", "error": "error"}.get(reason, "end"),
        timestamp=ts,
        unknown_blocks=unknown,
    )


def _tool_result(obj: dict, index: int, ts: int) -> Event:
    name = str(obj.get("toolName") or "")
    details = obj.get("details") or {}
    if not isinstance(details, dict):
        details = {}
    is_error = bool(obj.get("isError"))
    # A tool that opens pages can still fail on the one it was given -- a 403, a timeout.
    opened = name in _OPENING_TOOLS and not is_error
    content = _as_text(obj.get("content"))
    sources = []
    for raw in details.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        sources.append(SourceRef(
            url=url,
            title=str(raw.get("title") or ""),
            id=str(raw.get("id") or ""),
            excerpt=str(raw.get("excerpt") or ""),
            published=str(raw.get("publishDate") or raw.get("published") or ""),
            opened=opened,
        ))
    if name == "repl":
        # Each printed page is evidence on its own: a call that opened a tab and then failed on
        # its next statement still opened that page.
        listed = {s.url for s in sources}
        for m in _PAGE_PRINTED.finditer(_flatten_text(obj.get("content"))):
            url = m.group("tab_url") or m.group("snap_url")
            if url not in listed:
                listed.add(url)
                sources.append(SourceRef(url=url, title=(m.group("tab_title") or m.group("snap_title") or "").strip(),
                                         opened=True))
    return Event(
        kind="tool_result",
        index=index,
        raw=obj,
        tool_name=name,
        content=content,
        details=details,
        is_error=is_error,
        sources=sources,
        child_ids=_child_ids(name, details),
        timestamp=ts,
    )


def _child_ids(tool: str, details: dict) -> list[str]:
    """Sessions a subagent tool started or continued, in the order its result names them."""
    if not tool.startswith("subagent"):
        return []
    out: list[str] = []
    for key in ("taskId", "task_id", "sessionId", "session_id"):
        val = details.get(key)
        if isinstance(val, str) and val and val not in out:
            out.append(val)
    for r in details.get("results") or []:
        if isinstance(r, dict):
            val = r.get("taskId") or r.get("task_id")
            if isinstance(val, str) and val and val not in out:
                out.append(val)
    return out


def _usage(raw: object) -> dict:
    if not isinstance(raw, dict) or not raw:
        return {}
    out = {}
    for theirs, ours in _USAGE_KEYS.items():
        try:
            out[ours] = int(raw.get(theirs) or 0)
        except (TypeError, ValueError):
            out[ours] = 0
    cost = raw.get("cost")
    try:
        out["cost"] = float(cost.get("total") or 0) if isinstance(cost, dict) else float(cost or 0)
    except (TypeError, ValueError):
        out["cost"] = 0.0
    return out


def _target(arguments: object) -> str:
    if not isinstance(arguments, dict):
        return ""
    for key in _TARGET_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            # One physical line: a target carrying a newline would end a log line early, and
            # could forge a terminal line such as `run.completed`.
            flat = " ".join(value.split())
            m = _HOST_RE.match(flat)
            return m.group(1) if m else flat
    return ""


def _flatten_text(content: object) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts)


def _as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


_CITATION_RE = re.compile(r'<citation\s+refs="([^"]*)"\s*>(.*?)</citation>', re.DOTALL)
#: Answers quote their pages as `<quote>`, `<quote ref="id">` or `<quote refs="id,id">`.
_QUOTE_RE = re.compile(r'<quote(?:\s+(?:refs?|source)="([^"]*)")?\s*>(.*?)</quote>', re.DOTALL)


def resolve_answer_tags(text: str, id_to_url: dict[str, str]) -> str:
    """An answer with Aside's quote and citation tags replaced by the text they wrap and the
    URLs they cite, as `text (url, ...)`.

    A tag whose ids name no known source keeps its text: the claim stays, without a URL to
    vouch for it. An id may arrive longer than the one a source was listed under, so a
    listed id that the cited one starts with matches too. A citation can wrap a quote; a URL
    the citation gives is not repeated for the quote inside it.
    """

    def urls_of(ids: str | None) -> list[str]:
        urls: list[str] = []
        for ref in (r.strip() for r in (ids or "").split(",")):
            if not ref:
                continue
            url = id_to_url.get(ref) or next((u for i, u in id_to_url.items() if ref.startswith(i)), None)
            if url and url not in urls:
                urls.append(url)
        return urls

    def tagged(label: str, urls: list[str]) -> str:
        if not urls:
            return label
        return f"{label} ({', '.join(urls)})" if label else f"({', '.join(urls)})"

    def quote(m: re.Match[str], given: list[str] = ()) -> str:
        return tagged(m.group(2).strip(), [u for u in urls_of(m.group(1)) if u not in given])

    def citation(m: re.Match[str]) -> str:
        urls = urls_of(m.group(1))
        return tagged(_QUOTE_RE.sub(lambda q: quote(q, urls), m.group(2)).strip(), urls)

    return _QUOTE_RE.sub(quote, _CITATION_RE.sub(citation, text))
