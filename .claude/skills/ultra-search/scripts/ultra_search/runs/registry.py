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
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from ultra_search import workspace
from ultra_search.ids import is_safe_id, label_for, normal
from ultra_search.outcome import AmbiguousRun, ArgumentError, RunNotFound

RUNS_SUBDIR = "runs"


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
        if not is_safe_id(child_id):
            raise ValueError(f"not a session id: {child_id!r}")
        return self.path / "session" / "children" / f"{child_id}.jsonl"

    @property
    def artifacts_dir(self) -> Path:
        """Where copies of the files the agent saved go: the run's own at the top, each child's under its id."""
        return self.path / "artifacts"

    def child_transcripts(self) -> list[Path]:
        d = self.path / "session" / "children"
        try:
            return sorted(p for p in d.iterdir() if p.suffix == ".jsonl")
        except OSError:
            return []

    def last_write(self, children: list[str] | None = None) -> float:
        """Newest write among the files the run itself keeps: stdout, the session copy, and the copies of ``children`` -- every child's when None.

        A parent that spawned subagents goes silent while they work, so the children's
        copies count -- measuring only the parent would call that silence a stall.
        """
        copies = self.child_transcripts() if children is None else [self.child_transcript(c) for c in children]
        newest = 0.0
        for p in [self.stdout_path, self.session_transcript, *copies]:
            try:
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                pass
        return newest

    def write_meta(self, meta: dict) -> None:
        atomic_write_json(self.meta_path, meta)

    def update_meta(self, **changes: object) -> dict:
        """Merge changes into meta.json, serialised against other processes.

        Three processes write this file: the CLI that started the run, the detached
        supervisor, and whatever later calls `stop`. Each does read-modify-write, so
        without a lock two concurrent updates lose one side's keys entirely -- the
        supervisor's `state` and `pid` being overwritten by a parent that had already read
        the older copy. The lock makes the pair atomic; the atomic rename below only ever
        made the write itself atomic.
        """
        workspace.mark_written(self.path.parent.parent)
        last: Exception | None = None
        for attempt in range(5):
            try:
                with _meta_lock(self.path):
                    meta = load_meta(self.path)
                    meta.update(changes)
                    atomic_write_json(self.meta_path, meta)
                    return meta
            except (TimeoutError, OSError) as e:
                last = e
                time.sleep(0.05 * (attempt + 1))
        # Out of retries. Recording the run's state matters more than the lock did, so
        # this proceeds -- but says so, because a lost update here is otherwise invisible.
        meta = load_meta(self.path)
        meta.update(changes)
        meta["meta_lock_contended"] = str(last)
        atomic_write_json(self.meta_path, meta)
        return meta

    def meta(self) -> dict:
        return load_meta(self.path)


def create_run(
    runs_root: str | os.PathLike[str],
    label: str | None = None,
    group: str | None = None,
    **meta: object,
) -> Run:
    workspace.ensure(Path(runs_root))
    root = Path(runs_root) / RUNS_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d-%H%M%S")
    safe = label_for(label)
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
def _meta_lock(run_path: Path, timeout: float = 10.0):
    """A real cross-process lock, held by the kernel.

    flock and not an O_EXCL sentinel file, because the holder this has to survive is a
    supervisor that was killed: the kernel drops a flock when the process dies, while a
    sentinel outlives it and needs a staleness heuristic that can either block everyone
    behind a dead run or unlink a live holder's lock. Neither is acceptable for the file
    that records whether a run finished.

    A caller that cannot acquire it within the timeout raises rather than proceeding
    unlocked -- an unsynchronised read-modify-write silently drops the other writer's
    keys, and `update_meta` retries, which is a better answer than a lost update.
    """
    import fcntl

    lock_path = Path(run_path) / "meta.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    deadline = time.time() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError(f"could not lock {lock_path} within {timeout}s")
                time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def atomic_write_json(path: Path, obj: dict) -> None:
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
    """The run with this id, or the one run whose id begins with it.

    A prefix is how ids get typed back -- the time, without the label. A whole id always
    wins over longer ones it begins; a prefix several runs share is refused with their ids,
    because guessing reports someone else's run.
    """
    key = normal(run_id)
    if not is_safe_id(key):
        raise ArgumentError(
            f"{run_id!r} is not a run id",
            fix="Run ids look like 260925-021530-label; `status` with no target shows the latest.",
        )
    path = Path(runs_root) / RUNS_SUBDIR / key
    if path.is_dir():
        return Run(run_id=key, path=path)
    every = all_runs(runs_root)
    matches = [r for r in every if r.run_id.startswith(key)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise AmbiguousRun(
            f"{len(matches)} runs begin with {key!r}",
            fix="Name one of them in full, or by a longer prefix.",
            candidates=[r.run_id for r in matches][-10:],
        )
    known = [r.run_id for r in every][-5:]
    raise RunNotFound(
        f"no run {key!r} under {Path(runs_root) / RUNS_SUBDIR}",
        fix="Run `status` with no target for the most recent one, or name one of these." if known
        else "No runs have been started here yet.",
        recent_runs=known,
    )


def resolve_group(runs_root: str | os.PathLike[str], group: str) -> list[Run]:
    members = [r for r in all_runs(runs_root) if load_meta(r.path).get("group") == group]
    if not members:
        raise ArgumentError(f"no group {group!r} under {Path(runs_root) / RUNS_SUBDIR}", fix="Run `status` with no target for the most recent one.")
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

