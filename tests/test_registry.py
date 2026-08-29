"""_registry: run directories, run ids, and metadata that survives a crash.

The seam is a tmpdir runs root in, directories and JSON files out. No aside, no
subprocess.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import _registry
from _errors import ArgumentError


def test_a_run_gets_its_own_directory_named_for_when_and_what(runs_dir: Path) -> None:
    run = _registry.create_run(runs_dir, label="python-version")

    assert run.path.parent == runs_dir / "runs"
    assert run.path.is_dir()
    assert run.run_id.endswith("-python-version")


def test_two_runs_started_in_the_same_second_do_not_collide(runs_dir: Path) -> None:
    """Run ids are timestamps, and a group starts every member at once. Reserving the
    directory with O_EXCL is what makes the second one pick a new id instead of writing
    its metadata over the first one's."""
    runs = [_registry.create_run(runs_dir, label="same") for _ in range(5)]

    ids = [r.run_id for r in runs]
    assert len(set(ids)) == 5


def test_a_label_cannot_escape_the_runs_directory(runs_dir: Path) -> None:
    run = _registry.create_run(runs_dir, label="../../etc/passwd")

    assert runs_dir / "runs" in run.path.parents


def test_metadata_round_trips(runs_dir: Path) -> None:
    run = _registry.create_run(runs_dir, label="x")
    run.write_meta({"state": "running", "marker": "us-abc", "prompt": "질문"})

    assert _registry.load_meta(run.path)["marker"] == "us-abc"


def test_a_meta_write_is_all_or_nothing(runs_dir: Path) -> None:
    """The supervisor rewrites meta.json while `status` may be reading it. A half-written
    file would make a live run look corrupt, so the write lands by rename."""
    run = _registry.create_run(runs_dir, label="x")
    run.write_meta({"state": "running"})
    before = (run.path / "meta.json").read_text()

    try:
        run.write_meta({"state": "done", "bad": {1, 2}})  # a set is not JSON
    except TypeError:
        pass

    assert (run.path / "meta.json").read_text() == before


def test_update_meta_merges_rather_than_replacing(runs_dir: Path) -> None:
    run = _registry.create_run(runs_dir, label="x")
    run.write_meta({"state": "running", "marker": "us-abc"})

    run.update_meta(state="completed")

    meta = _registry.load_meta(run.path)
    assert meta == {"state": "completed", "marker": "us-abc"}


def test_runs_are_findable_by_id_and_by_group(runs_dir: Path) -> None:
    a = _registry.create_run(runs_dir, label="a", group="g1")
    b = _registry.create_run(runs_dir, label="b", group="g1")
    c = _registry.create_run(runs_dir, label="c", group="g2")

    assert _registry.resolve_run(runs_dir, a.run_id).path == a.path
    assert {r.run_id for r in _registry.resolve_group(runs_dir, "g1")} == {a.run_id, b.run_id}
    assert [r.run_id for r in _registry.resolve_group(runs_dir, "g2")] == [c.run_id]


def test_the_latest_run_is_the_most_recently_created(runs_dir: Path) -> None:
    _registry.create_run(runs_dir, label="old")
    newest = _registry.create_run(runs_dir, label="new")

    assert _registry.latest_run(runs_dir).run_id == newest.run_id


def test_asking_for_a_run_that_does_not_exist_is_refused_not_guessed(runs_dir: Path) -> None:
    _registry.create_run(runs_dir, label="a")

    with pytest.raises(ArgumentError):
        _registry.resolve_run(runs_dir, "260101-000000-nope")


def test_the_latest_run_of_an_empty_registry_is_refused(runs_dir: Path) -> None:
    with pytest.raises(ArgumentError):
        _registry.latest_run(runs_dir)


def test_the_runs_directory_defaults_under_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert _registry.default_runs_dir() == tmp_path / ".ultra-search"


def test_an_explicit_runs_directory_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert _registry.resolve_runs_dir(str(tmp_path / "elsewhere")) == tmp_path / "elsewhere"


def test_a_marker_is_unique_per_run_and_appears_in_the_prompt(runs_dir: Path) -> None:
    run = _registry.create_run(runs_dir, label="x")

    marker = _registry.marker_for(run.run_id)
    decorated = _registry.decorate_prompt("원래 질문", marker)
    assert decorated.startswith("원래 질문")
    assert marker in decorated
    assert marker != _registry.marker_for("260101-000000-y")


def test_group_membership_is_recorded_where_a_later_process_can_read_it(runs_dir: Path) -> None:
    """The supervisor is a separate process started later; it learns its group from
    disk, not from an argument that would be lost if the caller died."""
    run = _registry.create_run(runs_dir, label="a", group="g1")

    assert _registry.load_meta(run.path)["group"] == "g1"


def test_saved_pages_live_beside_the_runs(runs_dir: Path) -> None:
    assert _registry.pages_dir(runs_dir) == runs_dir / "pages"
    assert _registry.pages_dir(runs_dir).is_dir()
