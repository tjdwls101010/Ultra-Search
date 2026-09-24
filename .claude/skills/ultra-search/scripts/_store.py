"""Reading Aside's own session storage.

This is someone else's private data directory, and the CLI has no supported way to ask
"which session did my command just create?". Two consequences shape everything here.

The transcript on disk is authoritative and the database is not. Ephemeral CLI sessions
have been observed writing a full ``messages.jsonl`` while adding no row to ``state.db``
at all -- so every database read returns None rather than raising, and no caller may
require one to have succeeded.

And a session is correlated by a marker we planted in the prompt, not by matching the
prompt text. Two parallel searches of the same question are otherwise indistinguishable,
and picking the wrong one reports someone else's answer as yours.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ASIDE_HOME = "~/.aside"
ACCOUNT = "u/0"


@dataclass
class SessionRef:
    session_id: str
    path: Path

    @property
    def transcript(self) -> Path:
        return self.path / "messages.jsonl"


def aside_home(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return Path(os.environ.get("ULTRA_SEARCH_ASIDE_HOME") or DEFAULT_ASIDE_HOME).expanduser()


def sessions_root(home: str | os.PathLike[str] | None = None) -> Path:
    return aside_home(home) / ACCOUNT / "sessions"


def iter_sessions(home: str | os.PathLike[str] | None = None) -> list[SessionRef]:
    """Every session directory, newest first by directory mtime."""
    root = sessions_root(home)
    try:
        entries = [d for d in root.iterdir() if d.is_dir() and "_" in d.name]
    except OSError:
        return []
    entries.sort(key=lambda d: _mtime(d), reverse=True)
    return [SessionRef(session_id=d.name.split("_", 1)[1], path=d) for d in entries]


def session_dir(home: str | os.PathLike[str] | None, session_id: str) -> Path | None:
    """The directory for a session id, whatever date prefix Aside gave it."""
    root = sessions_root(home)
    try:
        for d in root.iterdir():
            if d.is_dir() and d.name.endswith("_" + session_id):
                return d
    except OSError:
        return None
    return None


def find_session_by_marker(home: str | os.PathLike[str] | None, marker: str) -> SessionRef | None:
    """The session whose opening user message contains ``marker``.

    Only the first record is read, and only from sessions that have one: a directory
    Aside has created but not yet written to is a session in progress, not a mismatch.
    """
    for ref in iter_sessions(home):
        t = ref.transcript
        try:
            with t.open("r", encoding="utf-8", errors="replace") as f:
                first = f.readline()
        except OSError:
            continue
        if not first.strip():
            continue
        if marker in first:
            return ref
    return None


# --- copying out ------------------------------------------------------------------


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


def last_activity(
    home: str | os.PathLike[str] | None,
    session_id: str,
    child_ids: list[str] | None = None,
) -> float:
    """Newest write time across the run's own transcript and every child's.

    A parent that spawned subagents goes silent while they work. Measuring only the
    parent would call that stalled; the children's writes are the evidence that it is not.
    """
    newest = 0.0
    for sid in [session_id, *(child_ids or [])]:
        d = session_dir(home, sid)
        if not d:
            continue
        newest = max(newest, _mtime(d), _mtime(d / "messages.jsonl"))
    return newest


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


# --- the database, best-effort ------------------------------------------------------


def db_path(home: str | os.PathLike[str] | None = None) -> Path:
    return aside_home(home) / ACCOUNT / "state.db"


def _query(home, sql: str, args: tuple) -> list[dict]:
    p = db_path(home)
    if not p.exists():
        return []
    try:
        # Read-only, not immutable: the daemon writes this constantly through a WAL, and
        # immutable=1 would tell SQLite to ignore that WAL and hand back stale rows with
        # no error. Failing to open is recoverable here; being quietly wrong is not.
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()
    except sqlite3.Error:
        # A schema change, a lock, a corrupt copy -- none of these are worth failing a
        # command over, because everything this returns is supplementary detail.
        return []


def db_session_row(home: str | os.PathLike[str] | None, session_id: str) -> dict | None:
    rows = _query(home, "select * from sessions where id = ?", (session_id,))
    return rows[0] if rows else None


def db_suspension(home: str | os.PathLike[str] | None, session_id: str) -> object | None:
    row = db_session_row(home, session_id)
    if not row:
        return None
    raw = row.get("suspension")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def session_summaries(home: str | os.PathLike[str] | None = None, limit: int = 30) -> list[dict]:
    """Every Aside session on disk, newest first, with enough to pick one out.

    Sessions made in the Aside app or by a bare `aside exec` are continuable too, but a
    session id is not something anyone can recall -- so the opening prompt is what makes
    the list usable, and the marker is what says whether ultra-search started it.
    """
    import json as _json

    out: list[dict] = []
    # Filtered before limited, not after: repl calls leave behind session directories with
    # no transcript at all, and they are the newest ones, so slicing first returns a page
    # of nothing on a machine that has used the browser recently.
    for ref in iter_sessions(home):
        if len(out) >= limit:
            break
        first = ""
        try:
            with ref.transcript.open("r", encoding="utf-8", errors="replace") as f:
                first = f.readline()
        except OSError:
            continue
        if not first.strip():
            continue
        prompt = ""
        try:
            rec = _json.loads(first)
            content = rec.get("content")
            if isinstance(content, str):
                prompt = content
            else:
                prompt = " ".join(
                    str(b.get("text") or "") for b in (content or []) if isinstance(b, dict)
                )
        except ValueError:
            prompt = first[:200]
        marker = ""
        if "ultra-search:" in prompt:
            marker = prompt.split("ultra-search:", 1)[1].split(" ", 1)[0].strip(")\n")
        out.append(
            {
                "session_id": ref.session_id,
                "date": ref.path.name.split("_", 1)[0],
                "modified_at": _mtime(ref.transcript) or _mtime(ref.path),
                "prompt": " ".join(prompt.split())[:160],
                "started_by_ultra_search": bool(marker),
                "run_id": marker or None,
            }
        )
    return out
