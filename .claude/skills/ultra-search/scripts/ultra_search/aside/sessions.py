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
import re
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from ultra_search.aside.transcript import read_events, turn_finished

DEFAULT_ASIDE_HOME = "~/.aside"
ACCOUNT = "u/0"
#: How far into a transcript the opening prompt is looked for. Records come before it -- a
#: turn's lifecycle record, attachment metadata, a system message listing skill docs -- but
#: only a few, and a session with none of its prompt this far in is not one to match.
OPENING_SCAN_LINES = 20


@dataclass
class SessionRef:
    session_id: str
    path: Path

    @property
    def transcript(self) -> Path:
        return self.path / "messages.jsonl"


def aside_home() -> Path:
    """~/.aside, or ULTRA_SEARCH_ASIDE_HOME."""
    return Path(os.environ.get("ULTRA_SEARCH_ASIDE_HOME") or DEFAULT_ASIDE_HOME).expanduser()


def sessions_root() -> Path:
    return aside_home() / ACCOUNT / "sessions"


def _sessions() -> list[SessionRef]:
    """Every session directory, newest first by directory mtime."""
    root = sessions_root()
    try:
        entries = [d for d in root.iterdir() if d.is_dir() and "_" in d.name]
    except OSError:
        return []
    entries.sort(key=lambda d: _mtime(d), reverse=True)
    return [SessionRef(session_id=d.name.split("_", 1)[1], path=d) for d in entries]


def _session_dir(session_id: str) -> Path | None:
    """The directory for a session id, whatever date prefix Aside gave it."""
    root = sessions_root()
    try:
        for d in root.iterdir():
            if d.is_dir() and d.name.endswith("_" + session_id):
                return d
    except OSError:
        return None
    return None


def session_transcript(session_id: str) -> Path | None:
    """Where a session's transcript is written, or None when Aside has no such session.

    The file itself may not exist yet: Aside creates the directory before the first record.
    """
    d = _session_dir(session_id)
    return d / "messages.jsonl" if d else None


def _opening_prompt(transcript: str | os.PathLike[str]) -> str | None:
    """The text of the first user record, or None when there is none yet.

    Decoded rather than searched as bytes: JSON may store the prompt's non-ASCII characters
    as escapes, and a marker carrying a non-ASCII label would then never match the line.
    """
    try:
        with Path(transcript).open("r", encoding="utf-8", errors="replace") as f:
            for _ in range(OPENING_SCAN_LINES):
                line = f.readline()
                if not line:
                    return None
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("role") == "user":
                    return _text_of(rec.get("content"))
    except OSError:
        return None
    return None


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    return " ".join(str(b.get("text") or "") for b in (content or []) if isinstance(b, dict))


def find_session_by_marker(marker: str) -> str | None:
    """The id of the session whose opening prompt contains ``marker``.

    A session whose prompt has not been written yet is a session in progress, not a
    mismatch, and is passed over until it has one.
    """
    for ref in _sessions():
        prompt = _opening_prompt(ref.transcript)
        if prompt and marker in prompt:
            return ref.session_id
    return None


def session_busy(session_id: str) -> str | None:
    """Why a session cannot take a new turn now: "database" when Aside's database says it is
    running, "transcript" when its last turn has not ended; None when it can.

    The database is not enough on its own: an ephemeral CLI session has no row there at all,
    so a busy one would pass that check by simply not existing in it. The transcript is the
    surface that always exists.
    """
    row = _db_session_row(session_id)
    if row and str(row.get("status") or "") == "running":
        return "database"
    transcript = session_transcript(session_id)
    events, _ = read_events(transcript) if transcript else ([], 0)
    if events and not turn_finished(events):
        return "transcript"
    return None


def last_activity(session_id: str, child_ids: list[str] | None = None) -> float:
    """Newest write time across the run's own transcript and every child's.

    A parent that spawned subagents goes silent while they work. Measuring only the
    parent would call that stalled; the children's writes are the evidence that it is not.
    """
    newest = 0.0
    for sid in [session_id, *(child_ids or [])]:
        d = _session_dir(sid)
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


def _db_path() -> Path:
    return aside_home() / ACCOUNT / "state.db"


def _query(sql: str, args: tuple) -> list[dict]:
    p = _db_path()
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


def _db_session_row(session_id: str) -> dict | None:
    rows = _query("select * from sessions where id = ?", (session_id,))
    return rows[0] if rows else None


def suspension(session_id: str) -> object | None:
    """What Aside's database says the session is paused on, if anything -- surfaced, not interpreted."""
    row = _db_session_row(session_id)
    if not row:
        return None
    raw = row.get("suspension")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def session_summaries(limit: int = 30) -> list[dict]:
    """Sessions on disk that have a prompt, newest first: session_id, date, modified_at and
    the whole opening_prompt.

    Sessions made in the Aside app or by a bare `aside exec` are continuable too, but a
    session id is not something anyone can recall -- so the opening prompt is what makes
    the list usable.
    """
    out: list[dict] = []
    # Filtered before limited, not after: repl calls leave behind session directories with
    # no transcript at all, and they are the newest ones, so slicing first returns a page
    # of nothing on a machine that has used the browser recently.
    for ref in _sessions():
        if len(out) >= limit:
            break
        prompt = _opening_prompt(ref.transcript)
        if prompt is None:
            continue
        out.append(
            {
                "session_id": ref.session_id,
                "date": ref.path.name.split("_", 1)[0],
                "modified_at": _mtime(ref.transcript) or _mtime(ref.path),
                "opening_prompt": prompt,
            }
        )
    return out


# --- the files the agent saved ------------------------------------------------------------


def session_artifacts(session_id: str) -> list[tuple[str, Path, float]]:
    """The files the agent saved in a session's `artifacts/` folder, at any depth, by path: (path within that folder, path, modification time).

    Regular files inside the folder only: a link can name any file on this machine, and what is listed here is copied out of Aside's directory.
    """
    d = _session_dir(session_id)
    if d is None:
        return []
    folder = d / "artifacts"
    try:
        base = folder.resolve(strict=True)
    except OSError:
        return []
    out = []
    for parent, _, names in os.walk(folder):  # a linked folder is listed, never entered
        for name in names:
            path = Path(parent) / name
            try:
                st = path.lstat()
                inside = path.resolve(strict=True).is_relative_to(base)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and inside:
                out.append((path.relative_to(folder).as_posix(), path, st.st_mtime))
    return sorted(out)


def _ref(session_id: str, rel: str) -> re.Pattern[str]:
    """Every way an answer names the saved file ``rel``: relative to its session, as the agent links its files (`artifacts/<rel>`), or by the session's absolute path, bare or behind `sandbox:` or `file://`; each with the name as saved, its spaces as `%20`, or all of it percent-encoded.

    A name continued by more of a name -- `.bak`, a letter, a slash -- is a different file, and a path whose folder is not this session's is another session's file.
    """
    names = "|".join(re.escape(n) for n in sorted({rel, rel.replace(" ", "%20"), quote(rel)}, key=len, reverse=True))
    forms = [rf"(?<![A-Za-z0-9_/.%-])(?:\./)?artifacts/(?:{names})"]
    d = _session_dir(session_id)
    if d is not None:
        folder = str(d / "artifacts")
        roots = "|".join(re.escape(r) for r in sorted({folder, folder.replace(" ", "%20"), quote(folder)}, key=len, reverse=True))
        forms.insert(0, rf"(?:sandbox:|file://)?(?:{roots})/(?:{names})")
    return re.compile(rf"(?:{'|'.join(forms)})(?![A-Za-z0-9_/\\-]|\.\w)")


def referenced_artifacts(text: str, session_id: str, rels: list[str]) -> list[str]:
    """Which of the session's saved files ``text`` names, in the order given."""
    return [rel for rel in rels if _ref(session_id, rel).search(text)]


def rewrite_artifact_refs(text: str, session_id: str, copies: dict[str, str | os.PathLike[str]]) -> str:
    """``text`` with each saved file it names -- ``copies`` maps a path within the session's `artifacts/` to where a copy of the file now is -- naming that copy instead, as a plain path a reader can open."""
    for rel in sorted(copies, key=len, reverse=True):
        target = str(copies[rel])
        text = _ref(session_id, rel).sub(lambda _: target, text)
    return text
