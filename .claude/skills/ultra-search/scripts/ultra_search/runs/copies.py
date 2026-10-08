"""A run's own copies of what Aside keeps -- its transcripts, and the files its agent saved -- kept in its run directory.

Aside deletes sessions on its own schedule, so the copy is what a run's evidence rests on
once the session is gone.
"""
from __future__ import annotations

import os
import stat
import tempfile
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


def copy_snapshot(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> os.stat_result:
    """Copy a file another process may still be writing, so that the copy is one moment of it or nothing, and return the status of the version copied.

    Opened without following a link and without waiting on a pipe, read only as far as it was long when opened, written under a temporary name and renamed into place. A source whose size, times or identity moved while it was read is read once more, and if it moves again this raises OSError("changing while copied"): a torn copy would pass for the file.
    """
    src_p, dst_p = Path(src), Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        with os.fdopen(os.open(src_p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as fin:
            before = os.fstat(fin.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise OSError(f"{src_p} is not a regular file")
            fd, tmp = tempfile.mkstemp(prefix=f".{dst_p.name}.", suffix=".part", dir=dst_p.parent)
            try:
                with os.fdopen(fd, "wb") as fout:
                    left = before.st_size
                    while left and (chunk := fin.read(min(left, 1 << 20))):
                        fout.write(chunk)
                        left -= len(chunk)
                after = os.stat(src_p, follow_symlinks=False)
                if not left and all(getattr(before, k) == getattr(after, k)
                                    for k in ("st_size", "st_mtime_ns", "st_ctime_ns", "st_ino")):
                    os.replace(tmp, dst_p)
                    return before
            finally:
                Path(tmp).unlink(missing_ok=True)
    raise OSError("changing while copied")
