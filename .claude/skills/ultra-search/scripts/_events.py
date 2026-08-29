"""The session transcript, as events a caller can act on.

Aside writes one JSON object per line to a session's ``messages.jsonl`` while the run is
still going, so this module reads by byte cursor and stops at the last newline: a line
being written is half a line, and parsing it would either crash or invent a record.

Nothing here drops a record it does not recognise. This file is a private surface of
another product -- when it changes, an unfamiliar shape arriving as ``raw`` degrades a
report, while a dropped one silently shortens it and nobody finds out.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Tools whose result means the agent actually read a page, rather than merely being
#: shown it in a result list. The distinction is what `opened` reports.
_OPENING_TOOLS = frozenset({"webfetch", "repl", "read_file"})

_CITATION_RE = re.compile(r'<citation\s+refs="([^"]*)"\s*>(.*?)</citation>', re.DOTALL)


@dataclass
class ToolCall:
    name: str
    arguments: dict
    raw: dict = field(repr=False, default_factory=dict)


@dataclass
class Source:
    url: str
    title: str = ""
    id: str = ""
    excerpt: str = ""
    published: str = ""
    opened: bool = False


@dataclass
class Event:
    kind: str
    index: int
    raw: dict = field(repr=False, default_factory=dict)
    text: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str = ""
    content: str = ""
    details: dict = field(default_factory=dict)
    is_error: bool = False
    usage: dict = field(default_factory=dict)
    stop_reason: str = ""
    timestamp: int = 0
    unknown_blocks: list[dict] = field(default_factory=list)


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
        return Event(
            kind="tool_result",
            index=index,
            raw=obj,
            tool_name=str(obj.get("toolName") or ""),
            content=_as_text(obj.get("content")),
            details=obj.get("details") or {},
            is_error=bool(obj.get("isError")),
            timestamp=ts,
        )
    return Event(kind="raw", index=index, raw=obj, content=json.dumps(obj, ensure_ascii=False), timestamp=ts)


def _assistant(obj: dict, index: int, ts: int) -> Event:
    texts: list[str] = []
    thinking: list[str] = []
    calls: list[ToolCall] = []
    unknown: list[dict] = []
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
            thinking.append(str(block.get("text") or block.get("thinking") or ""))
        elif kind == "toolCall":
            calls.append(ToolCall(name=str(block.get("name") or ""), arguments=block.get("arguments") or {}, raw=block))
        else:
            # An unfamiliar block type keeps its siblings: the text next to it is still
            # the answer, and losing the whole turn over one new block would hide it.
            unknown.append(block)
    return Event(
        kind="assistant",
        index=index,
        raw=obj,
        text="\n".join(t for t in texts if t),
        thinking="\n".join(t for t in thinking if t),
        tool_calls=calls,
        usage=obj.get("usage") or {},
        stop_reason=str(obj.get("stopReason") or ""),
        timestamp=ts,
        unknown_blocks=unknown,
    )


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


# --- derived views ---------------------------------------------------------------


def final_answer(events: list[Event], sources: list[Source] | None = None) -> str:
    """The last assistant text, with citation tags resolved to their URLs.

    A run that ends mid-tool has no final text; the caller gets "" and decides whether
    that is an honest zero or an interrupted run -- this module will not guess.
    """
    text = ""
    for e in events:
        if e.kind == "assistant" and e.text.strip():
            text = e.text
    if not text:
        return ""
    return resolve_citations(text, sources if sources is not None else collect_sources(events))


def resolve_citations(text: str, sources: list[Source]) -> str:
    by_id = {s.id: s for s in sources if s.id}

    def sub(m: re.Match[str]) -> str:
        refs = [r.strip() for r in m.group(1).split(",") if r.strip()]
        label = m.group(2).strip()
        urls = []
        for ref in refs:
            hit = by_id.get(ref) or next((s for s in sources if s.id and ref.startswith(s.id)), None)
            if hit and hit.url and hit.url not in urls:
                urls.append(hit.url)
        if not urls:
            return label
        return f"{label} ({', '.join(urls)})" if label else f"({', '.join(urls)})"

    return _CITATION_RE.sub(sub, text)


def collect_sources(events: list[Event]) -> list[Source]:
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
            existing = seen.get(url)
            if existing:
                existing.opened = existing.opened or opened
                continue
            s = Source(
                url=url,
                title=str(raw.get("title") or ""),
                id=str(raw.get("id") or ""),
                excerpt=str(raw.get("excerpt") or ""),
                published=str(raw.get("publishDate") or raw.get("published") or ""),
                opened=opened,
            )
            seen[url] = s
            out.append(s)
    return out


def child_session_ids(events: list[Event]) -> list[str]:
    """Child sessions spawned by this run, in spawn order.

    Read from the parent's own transcript rather than the database, because an ephemeral
    CLI session and its children may never appear there at all.
    """
    out: list[str] = []
    for e in events:
        if e.kind != "tool_result" or not e.tool_name.startswith("subagent"):
            continue
        det = e.details or {}
        for key in ("taskId", "task_id", "sessionId", "session_id"):
            val = det.get(key)
            if isinstance(val, str) and val and val not in out:
                out.append(val)
        for r in det.get("results") or []:
            if isinstance(r, dict):
                val = r.get("taskId") or r.get("task_id")
                if isinstance(val, str) and val and val not in out:
                    out.append(val)
    return out


def total_usage(events: list[Event]) -> dict:
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


def last_timestamp(events: list[Event]) -> int:
    return max((e.timestamp for e in events if e.timestamp), default=0)


# --- rendering -------------------------------------------------------------------

_LEVELS = ("compact", "normal", "full", "raw")


def render(event: Event, level: str = "compact") -> str:
    if level == "raw":
        return json.dumps(event.raw, ensure_ascii=False)
    if event.kind == "user":
        return f"user: {_clip(event.text, 200 if level == 'compact' else 2000)}"
    if event.kind == "assistant":
        return _render_assistant(event, level)
    if event.kind == "tool_result":
        return _render_tool_result(event, level)
    return f"raw[{event.index}]: {_clip(event.content, 200)}"


def _render_assistant(event: Event, level: str) -> str:
    parts = []
    if event.thinking and level in ("full",):
        parts.append(f"thinking: {_clip(event.thinking, 4000)}")
    for c in event.tool_calls:
        args = json.dumps(c.arguments, ensure_ascii=False)
        parts.append(f"call {c.name}({_clip(args, 200 if level == 'compact' else 4000)})")
    if event.text:
        parts.append(_clip(event.text, 400 if level == "compact" else 100000))
    if event.unknown_blocks:
        parts.append(f"[{len(event.unknown_blocks)} unrecognised block(s)]")
    return "\n".join(parts) if parts else f"assistant[{event.stop_reason}]"


def _render_tool_result(event: Event, level: str) -> str:
    n = len(event.content)
    head = f"{event.tool_name} {'ERROR ' if event.is_error else ''}out={n}B"
    srcs = (event.details or {}).get("sources") or []
    if srcs:
        head += f" sources={len(srcs)}"
    if level == "compact":
        # The size, not the bytes: a tool that printed a whole page would otherwise put
        # that page into the reader's context as a byproduct of watching progress.
        return head
    limit = 2000 if level == "normal" else 200000
    return f"{head}\n{_clip(event.content, limit)}"


def _clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"…(+{len(s) - n})"
