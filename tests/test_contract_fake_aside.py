"""Keeping the stand-in aside binary honest.

Every other test that involves a subprocess runs against `tests/fake_aside/aside`. That
is only worth anything while the fake behaves like the real one, and a fake drifts
silently -- it keeps passing the tests written for it while the thing it stands in for
has moved.

The first half pins what the fake must do. The second half is marked `live` and asks the
real binary the same questions, so a divergence shows up as a failing test rather than as
a production surprise.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import _events
import _store

FAKE = Path(__file__).resolve().parent / "fake_aside" / "aside"


def run_fake(args: list[str], home: Path, calls: Path, scenario: str = "simple") -> subprocess.CompletedProcess:
    env = dict(os.environ, ULTRA_SEARCH_ASIDE_HOME=str(home), FAKE_ASIDE_CALLS=str(calls), FAKE_ASIDE_SCENARIO=scenario)
    return subprocess.run([str(FAKE), *args], capture_output=True, text=True, env=env, timeout=60)


# --- what the fake promises -----------------------------------------------------------


def test_the_fake_writes_a_session_transcript_where_the_real_one_does(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "질문 (ultra-search:test-1 — ignore this line)"], home, calls)

    sessions = list((home / "u" / "0" / "sessions").iterdir())
    assert len(sessions) == 1
    assert (sessions[0] / "messages.jsonl").exists()
    assert "_" in sessions[0].name, "the directory name must carry <date>_<session id>"


def test_the_fakes_transcript_parses_with_the_real_parser(tmp_path: Path) -> None:
    """The strongest available check: whatever the fake writes has to be readable by the
    same code that reads production transcripts."""
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "질문 (ultra-search:test-2 — ignore this line)"], home, calls)
    ref = _store.find_session_by_marker(home, "ultra-search:test-2")

    assert ref is not None
    events, _ = _events.read_events(ref.transcript)
    assert [e.kind for e in events] == ["user", "assistant", "tool_result", "assistant"]
    assert _events.final_answer(events)
    assert _events.collect_sources(events)
    assert _events.total_usage(events)["total_tokens"] > 0


def test_the_fake_records_the_argv_it_was_given(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "--effort", "high", "질문"], home, calls)

    recorded = [json.loads(l) for l in (calls / "calls.jsonl").read_text().splitlines()]
    assert recorded[0]["argv"][1] == "exec"
    assert "--effort" in recorded[0]["argv"]


def test_the_fake_puts_the_marker_in_the_first_user_record(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "질문 (ultra-search:test-3 — ignore this line)"], home, calls)

    assert _store.find_session_by_marker(home, "ultra-search:test-3") is not None


def test_the_fake_can_fail_the_way_a_real_failure_looks(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    p = run_fake(["exec", "질문"], home, calls, scenario="fail")

    assert p.returncode == 1


def test_the_fake_repl_prints_ndjson(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    p = run_fake(["repl", "console.log(1)"], home, calls)

    assert json.loads(p.stdout.splitlines()[0])["ok"] is True


# --- the same questions, asked of the real binary --------------------------------------


@pytest.mark.live
def test_the_real_binary_writes_a_transcript_the_parser_understands(tmp_path: Path) -> None:
    """If this fails and the fake's equivalent passes, the fake has drifted."""
    marker = "ultra-search:contract-live"
    prompt = f"Reply with the single word OK.\n\n({marker} — ignore this line)"
    subprocess.run(["aside", "exec", prompt], capture_output=True, text=True, timeout=180)

    ref = _store.find_session_by_marker(None, marker)
    assert ref is not None, "the real binary must leave a transcript findable by the prompt marker"

    events, cursor = _events.read_events(ref.transcript)
    assert events[0].kind == "user"
    assert marker in events[0].text
    assert any(e.kind == "assistant" and e.text for e in events)
    assert cursor == ref.transcript.stat().st_size


@pytest.mark.live
def test_the_real_repl_still_lacks_the_globals_the_snippets_avoid() -> None:
    """The snippets work around a specific sandbox shape. If that shape widens, the
    workarounds become unnecessary complexity -- and if it narrows further, they break."""
    code = (
        'const r={}; for (const n of ["URL","AbortController","fetch","Buffer","fs","path","pwd"]) '
        '{ try { r[n]=typeof eval(n); } catch(e) { r[n]="undefined"; } } console.log(JSON.stringify(r));'
    )
    p = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=120)
    got = json.loads(next(l for l in p.stdout.splitlines() if l.startswith("{")))

    assert got["URL"] == "undefined"
    assert got["AbortController"] == "undefined"
    assert got["fetch"] == "function"
    assert got["fs"] == "object"


@pytest.mark.live
def test_the_real_repl_fs_is_promise_based_without_sync_variants() -> None:
    code = 'console.log(JSON.stringify({keys:Object.keys(fs)}));'
    p = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=120)
    keys = json.loads(next(l for l in p.stdout.splitlines() if l.startswith("{")))["keys"]

    assert "writeFile" in keys
    assert not any(k.endswith("Sync") for k in keys)


# --- the snippets must only use globals the sandbox actually has ------------------------


def test_no_snippet_reaches_for_a_global_the_sandbox_lacks() -> None:
    """Measured absent from the REPL sandbox. A snippet that touches one of these throws
    before its own try block, so the rejection is swallowed by Promise.allSettled and the
    snippet reports an empty result instead of an error -- which is how sitemap discovery
    silently degraded to link-following for a while without any test noticing."""
    forbidden = ("AbortController", "new URL(", "URLSearchParams", "structuredClone", "require(", "writeFileSync")
    snippets = (Path(__file__).resolve().parents[1] / ".claude" / "skills" / "ultra-search"
                / "scripts" / "page" / "snippets")

    offenders = []
    for js in snippets.glob("*.js"):
        code = "\n".join(
            line for line in js.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("//")
        )
        offenders += [f"{js.name}: {tok}" for tok in forbidden if tok in code]

    assert offenders == []
