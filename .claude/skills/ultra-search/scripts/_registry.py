"""Run directories, ids, and metadata that outlives the process that wrote it.

A run's directory is the only thing three processes agree on: the CLI that started it,
the detached supervisor that watches it, and whatever later command asks how it went.
None of them can pass arguments to the others, so everything shared lives on disk.

Ids embed the start time so a directory listing reads chronologically, and are reserved
with O_EXCL because a group starts every member inside the same second -- the mkdir
either wins the name or the caller takes another.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from _errors import ArgumentError

RUNS_SUBDIR = "runs"
PAGES_SUBDIR = "pages"
DEFAULT_DIRNAME = ".ultra-search"

_LABEL_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def default_runs_dir() -> Path:
    return Path.cwd() / DEFAULT_DIRNAME


def resolve_runs_dir(explicit: str | os.PathLike[str] | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else default_runs_dir()


def pages_dir(runs_root: str | os.PathLike[str]) -> Path:
    d = Path(runs_root) / PAGES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Run:
    run_id: str
    path: Path

    @property
    def meta_path(self) -> Path:
        return self.path / "meta.json"

    @property
    def stdout_path(self) -> Path:
        return self.path / "stdout.log"

    @property
    def session_transcript(self) -> Path:
        return self.path / "session" / "messages.jsonl"

    def child_transcript(self, child_id: str) -> Path:
        return self.path / "session" / "children" / f"{child_id}.jsonl"

    def child_transcripts(self) -> list[Path]:
        d = self.path / "session" / "children"
        try:
            return sorted(p for p in d.iterdir() if p.suffix == ".jsonl")
        except OSError:
            return []

    def write_meta(self, meta: dict) -> None:
        _atomic_write_json(self.meta_path, meta)

    def update_meta(self, **changes: object) -> dict:
        """Merge changes into meta.json, serialised against other processes.

        Three processes write this file: the CLI that started the run, the detached
        supervisor, and whatever later calls `stop`. Each does read-modify-write, so
        without a lock two concurrent updates lose one side's keys entirely -- the
        supervisor's `state` and `pid` being overwritten by a parent that had already read
        the older copy. The lock makes the pair atomic; the atomic rename below only ever
        made the write itself atomic.
        """
        for attempt in range(5):
            with _meta_lock(self.path):
                meta = load_meta(self.path)
                meta.update(changes)
                _atomic_write_json(self.meta_path, meta)
            # Verify rather than assume. The lock gives up after its timeout rather than
            # refusing to record a run's state at all, so the last write may have raced;
            # reading our own keys back is what makes that fallback self-correcting
            # instead of a silent loss.
            written = load_meta(self.path)
            if all(written.get(k) == v for k, v in changes.items()):
                return written
            time.sleep(0.02 * (attempt + 1))
        return load_meta(self.path)

    def meta(self) -> dict:
        return load_meta(self.path)


def _sanitize_label(label: str | None) -> str:
    if not label:
        return "run"
    # Only the basename, and only safe characters: a label reaches here from the command
    # line and would otherwise be able to name a directory outside the registry.
    clean = _LABEL_SAFE.sub("-", Path(str(label)).name).strip("-.")
    return clean[:40] or "run"


def create_run(
    runs_root: str | os.PathLike[str],
    label: str | None = None,
    group: str | None = None,
    **meta: object,
) -> Run:
    root = Path(runs_root) / RUNS_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d-%H%M%S")
    safe = _sanitize_label(label)
    for attempt in range(100):
        suffix = "" if attempt == 0 else f"-{secrets.token_hex(2)}"
        run_id = f"{stamp}{suffix}-{safe}"
        path = root / run_id
        try:
            path.mkdir()
        except FileExistsError:
            continue
        run = Run(run_id=run_id, path=path)
        base = {"run_id": run_id, "label": safe, "created_at": time.time(), "state": "starting"}
        if group:
            base["group"] = group
        base.update(meta)
        run.write_meta(base)
        return run
    raise ArgumentError(f"could not reserve a run directory under {root}", fix="Check the directory is writable.")


@contextlib.contextmanager
def _meta_lock(run_path: Path, timeout: float = 5.0, stale_after: float = 30.0):
    """A cross-process lock via O_EXCL.

    Staleness is checked on every attempt rather than only after the timeout, because the
    holder this needs to survive is a supervisor that was killed -- its lock is never
    coming back, and waiting the full window for something already dead delays every
    writer behind it.

    If the wait runs out anyway the update proceeds unlocked. Losing a race is a
    degradation; refusing to record a run's state at all is a run nobody can find.
    """
    lock = Path(run_path) / "meta.lock"
    deadline = time.time() + timeout
    fd = None
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_after:
                    lock.unlink()
                    continue
            except OSError:
                # Cleared by its owner between the open and the stat -- retry immediately.
                continue
            if time.time() >= deadline:
                break
            time.sleep(0.02)
        except OSError:
            break  # an unwritable run directory is the caller's problem, not this lock's
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def _atomic_write_json(path: Path, obj: dict) -> None:
    """Serialise first, then rename.

    `status` may read this file at any moment. Serialising before touching the
    destination means an unserialisable value fails without having damaged what was
    already there, and the rename means a reader sees the old file or the new one.
    """
    payload = json.dumps(obj, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def load_meta(run_path: str | os.PathLike[str]) -> dict:
    p = Path(run_path) / "meta.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def all_runs(runs_root: str | os.PathLike[str]) -> list[Run]:
    root = Path(runs_root) / RUNS_SUBDIR
    try:
        dirs = [d for d in root.iterdir() if d.is_dir()]
    except OSError:
        return []
    dirs.sort(key=lambda d: (load_meta(d).get("created_at") or 0, d.name))
    return [Run(run_id=d.name, path=d) for d in dirs]


def resolve_run(runs_root: str | os.PathLike[str], run_id: str) -> Run:
    path = Path(runs_root) / RUNS_SUBDIR / run_id
    if not path.is_dir():
        known = [r.run_id for r in all_runs(runs_root)][-5:]
        raise ArgumentError(
            f"no run {run_id!r} under {Path(runs_root) / RUNS_SUBDIR}",
            fix="Use `status --last`, or one of these run ids." if known else "No runs have been started here yet.",
            recent_runs=known,
        )
    return Run(run_id=run_id, path=path)


def resolve_group(runs_root: str | os.PathLike[str], group: str) -> list[Run]:
    members = [r for r in all_runs(runs_root) if load_meta(r.path).get("group") == group]
    if not members:
        raise ArgumentError(f"no group {group!r} under {Path(runs_root) / RUNS_SUBDIR}", fix="Use `status --last`.")
    return members


def latest_run(runs_root: str | os.PathLike[str]) -> Run:
    runs = all_runs(runs_root)
    if not runs:
        raise ArgumentError(f"no runs under {Path(runs_root) / RUNS_SUBDIR}", fix="Start one with `search`.")
    return runs[-1]


def latest_group(runs_root: str | os.PathLike[str]) -> list[Run]:
    """Every member of the newest run's group, or just that run if it has none."""
    newest = latest_run(runs_root)
    group = load_meta(newest.path).get("group")
    return resolve_group(runs_root, group) if group else [newest]


def new_group_name() -> str:
    return time.strftime("g%y%m%d-%H%M%S-") + secrets.token_hex(2)


# --- correlation ------------------------------------------------------------------


def marker_for(run_id: str) -> str:
    return f"ultra-search:{run_id}"


def decorate_prompt(prompt: str, marker: str) -> str:
    """Append the correlation marker to a prompt.

    Aside's CLI never reports which session it created, and matching on the prompt text
    cannot tell two parallel runs of the same question apart. The marker goes last and
    says what it is, so the agent reads it as bookkeeping rather than as part of the
    task; a run was measured answering the question correctly with it attached.
    """
    return f"{prompt}\n\n({marker} — ignore this line)"
