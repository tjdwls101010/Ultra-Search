"""A run's own copy of a transcript, kept in its run directory.

Aside deletes sessions on its own schedule, so the copy is what a run's evidence rests on
once the session is gone.
"""
from __future__ import annotations

import os
from pathlib import Path


def copy_new_lines(src: str | os.PathLike[str], dst: str | os.PathLike[str], since: int) -> int:
    """Append whole lines from ``src`` after byte ``since`` onto ``dst``; return the new cursor.

    Append-only and whole-lines-only, both deliberately. The destination outlives the
    source, so a source that shrinks or vanishes must never shorten the copy; and a line
    still being written is not yet a record, so consuming it would store a fragment that
    can never be completed.
    """
    src_p, dst_p = Path(src), Path(dst)
    try:
        size = src_p.stat().st_size
    except OSError:
        return since
    # The destination's own size is the cursor. The `since` a caller passes is a hint
    # recorded separately from the append it describes, so the two drift in both
    # directions: a lost or truncated copy leaves it too high, and a crash between the
    # append and the record that followed it leaves it too low. Trusting it either way
    # skips records or copies them twice, and duplicated records are then counted twice
    # in usage, sources and child discovery. The bytes on disk cannot drift from
    # themselves.
    since = dst_p.stat().st_size if dst_p.exists() else 0
    if size <= since:
        return since
    with src_p.open("rb") as f:
        f.seek(since)
        chunk = f.read(size - since)
    end = chunk.rfind(b"\n")
    if end == -1:
        return since
    complete = chunk[: end + 1]
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    with dst_p.open("ab") as out:
        out.write(complete)
    return since + len(complete)
