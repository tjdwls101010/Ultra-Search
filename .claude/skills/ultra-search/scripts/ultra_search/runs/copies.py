"""A run's own copies of what Aside keeps -- its transcripts, and the files its agent saved -- kept in its run directory.

Aside deletes sessions on its own schedule, so the copy is what a run's evidence rests on
once the session is gone.
"""
from __future__ import annotations

import os
import shutil
import stat
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


def copy_snapshot(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    """Copy a file another process may still be writing, so that the copy is one moment of it or nothing.

    Read through a descriptor that refuses a link, written under a temporary name and renamed into place. A source whose size, modification time or identity moved while it was read is read once more, and if it moves again this raises OSError("changing while copied"): a torn copy would pass for the file.
    """
    src_p, dst_p = Path(src), Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_p.with_name(f".{dst_p.name}.{os.getpid()}.part")
    try:
        for _ in range(2):
            with os.fdopen(os.open(src_p, os.O_RDONLY | os.O_NOFOLLOW), "rb") as fin:
                before = os.fstat(fin.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise OSError(f"{src_p} is not a regular file")
                with tmp.open("wb") as fout:
                    shutil.copyfileobj(fin, fout, 1 << 20)
            after = os.stat(src_p, follow_symlinks=False)
            if (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino):
                os.replace(tmp, dst_p)
                return
        raise OSError("changing while copied")
    finally:
        tmp.unlink(missing_ok=True)
