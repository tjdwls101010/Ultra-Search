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
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ToolCall:
    name: str
    arguments: dict
    raw: dict = field(repr=False, default_factory=dict)


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
    if role == "system-message":
        # Aside reports a subagent finishing this way. It is the one record a supervisor
        # most wants to see, so it gets a kind of its own rather than the raw fallback.
        return Event(kind="system", index=index, raw=obj, text=_as_text(obj.get("content")), timestamp=ts)
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
