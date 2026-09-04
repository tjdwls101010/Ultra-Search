"""One transcript event, as the line a reader can act on.

Which line an event becomes is decided by who is reading. ``progress`` is read by the
caller who delegated the run and is choosing between four things: keep waiting, collect
with ``result``, suspect a stall and check ``status``, or cancel in the Aside app. Only
what can change that choice becomes a line -- what the run reached for (a tool, how many
times, the host or objective it pointed at), what it said, what finished, what errored.
How it asked (arguments, local paths, offsets) and how large a successful result was
change none of those, so they are not printed. A tool this module has never seen falls
to its name and count under the same rule; nothing is dropped for being unfamiliar.

``steps`` is for retracing why a source was chosen: every call with its arguments, every
result with its size but not its bytes. ``full`` adds each result's first 2000 bytes.
``raw`` is the stored record unchanged.
"""
from __future__ import annotations

import json
import re

from _events import Event

LEVELS = ("progress", "steps", "full", "raw")

#: Arguments that name something outside the session -- the thing a call reached for.
#: A local path or an offset says how the worker asked, not what it went after, so it is
#: not here; a tool with none of these is reported by name and count alone.
_TARGET_KEYS = ("url", "objective", "description", "title")
_HOST_RE = re.compile(r"^https?://([^/]+)")


def render(event: Event, level: str = "progress") -> str:
    if level == "raw":
        return json.dumps(event.raw, ensure_ascii=False)
    if level == "progress":
        return _progress(event)
    if event.kind == "user":
        return f"user: {_clip(event.text, 200 if level == 'steps' else 2000)}"
    if event.kind == "assistant":
        return _assistant(event, level)
    if event.kind == "tool_result":
        return _tool_result(event, level)
    if event.kind == "system":
        return f"system: {_clip(event.text, 200 if level == 'steps' else 2000)}"
    return f"raw[{event.index}]: {_clip(event.content, 200)}"


# --- progress ---------------------------------------------------------------------------


def _progress(event: Event) -> str:
    if event.kind == "user":
        return f"prompt: {_first_line(event.text, 120)}"
    if event.kind == "assistant":
        parts = []
        if event.tool_calls:
            parts.append(_reached_for(event))
        if event.text.strip():
            # A turn that ends without calling anything is the answer; text beside a call
            # is the worker saying what it is about to do. The reader collects the first
            # and waits through the second.
            label = "says" if event.tool_calls else "answer"
            parts.append(f"{label}: {_first_line(event.text, 160)}")
        return " | ".join(parts)
    if event.kind == "tool_result":
        return f"{event.tool_name} ERROR: {_first_line(event.content, 120)}" if event.is_error else ""
    if event.kind == "system":
        return f"system: {_first_line(event.text, 100)}"
    return f"raw: {_first_line(event.content, 100)}"


def _reached_for(event: Event) -> str:
    """``webfetch×4[nodejs.org] read_file×2`` -- tools in first-use order, each with the
    distinct targets it pointed at."""
    by_tool: dict[str, list[str]] = {}
    for c in event.tool_calls:
        targets = by_tool.setdefault(c.name, [])
        target = _target(c.arguments)
        if target and target not in targets:
            targets.append(target)
    out = []
    for name, targets in by_tool.items():
        n = sum(1 for c in event.tool_calls if c.name == name)
        out.append(f"{name}×{n}" + (f"[{_clip(', '.join(targets), 80)}]" if targets else ""))
    return " ".join(out)


def _target(arguments: dict) -> str:
    for key in _TARGET_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            m = _HOST_RE.match(value.strip())
            return m.group(1) if m else value.strip()
    return ""


# --- steps and full ---------------------------------------------------------------------


def _assistant(event: Event, level: str) -> str:
    parts = []
    for c in event.tool_calls:
        args = json.dumps(c.arguments, ensure_ascii=False)
        parts.append(f"call {c.name}({_clip(args, 200 if level == 'steps' else 4000)})")
    if event.text:
        parts.append(_clip(event.text, 400 if level == "steps" else 100000))
    if event.unknown_blocks:
        parts.append(f"[{len(event.unknown_blocks)} unrecognised block(s)]")
    return "\n".join(parts) if parts else f"assistant[{event.stop_reason}]"


def _tool_result(event: Event, level: str) -> str:
    n = len(event.content)
    head = f"{event.tool_name} {'ERROR ' if event.is_error else ''}out={n}B"
    srcs = (event.details or {}).get("sources") or []
    if srcs:
        head += f" sources={len(srcs)}"
    if level == "steps":
        # The size, not the bytes: a tool that printed a whole page would otherwise put
        # that page into the reader's context as a byproduct of watching progress.
        return head
    return f"{head}\n{_clip(event.content, 2000)}"


def _clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"…(+{len(s) - n})"


def _first_line(s: str, n: int) -> str:
    s = (s or "").strip()
    first = s.splitlines()[0] if s else ""
    head = first[:n]
    rest = len(s) - len(head)
    return head + (f" …(+{rest})" if rest else "")
