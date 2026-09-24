"""Keeping the stand-in aside binary honest.

Every other test that involves a subprocess runs against `tests/fake_aside/aside`. That is
only worth anything while the fake behaves like the real one, and a fake drifts silently --
it keeps passing the tests written for it while the thing it stands in for has moved.

The first half pins what the fake must do, reading its output through the CLI that reads
the real one. The second half is marked `live` and asks the real binary the same questions,
so a divergence shows up as a failing test rather than as a production surprise.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS, run_cli, tool

FAKE = Path(__file__).resolve().parent / "fake_aside" / "aside"
SNIPPETS = SCRIPTS / "page" / "snippets"


def run_fake(args: list[str], home: Path, calls: Path, scenario: str = "simple", **env: str) -> subprocess.CompletedProcess:
    full = dict(os.environ, ULTRA_SEARCH_ASIDE_HOME=str(home), FAKE_ASIDE_CALLS=str(calls), FAKE_ASIDE_SCENARIO=scenario, **env)
    return subprocess.run([str(FAKE), *args], capture_output=True, text=True, env=full, timeout=60)


def snippet(name: str, args: dict) -> str:
    """The code the CLI sends for a snippet: its ARGS line, then the snippet file."""
    return f"const ARGS = {json.dumps(args)};\n" + (SNIPPETS / f"{name}.js").read_text(encoding="utf-8")


def ndjson(p: subprocess.CompletedProcess) -> list[dict]:
    return [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]


# --- what the fake promises about sessions -----------------------------------------------


def test_the_fake_writes_a_session_transcript_where_the_real_one_does(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "질문 (ultra-search:test-1 — ignore this line)"], home, calls)

    sessions = list((home / "u" / "0" / "sessions").iterdir())
    assert len(sessions) == 1
    assert (sessions[0] / "messages.jsonl").exists()
    assert "_" in sessions[0].name, "the directory name must carry <date>_<session id>"


def test_the_fakes_transcript_reads_like_a_real_one(cli) -> None:
    """The strongest available check: whatever the fake writes has to be read by the same
    code that reads production transcripts, into an answer, sources and usage."""
    _, payload, _ = cli("search", "질문", "--wait", "30")
    run_id = payload["runs"][0]["run_id"]
    _, _, text = cli("log", "--run", run_id, "--level", "raw")

    roles = [json.loads(line)["role"] for line in text.splitlines()[:-1] if line.startswith("{")]
    assert roles == ["user", "assistant", "toolResult", "assistant"]
    run = payload["runs"][0]
    assert run["answer"] and run["sources"] and run["usage"]["total_tokens"] > 0


def test_the_fake_records_the_argv_it_was_given(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "--effort", "high", "질문"], home, calls)

    recorded = [json.loads(line) for line in (calls / "calls.jsonl").read_text().splitlines()]
    assert recorded[0]["argv"][1] == "exec"
    assert "--effort" in recorded[0]["argv"]


def test_the_fake_puts_the_marker_in_the_first_user_record(tmp_path: Path, monkeypatch) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    run_fake(["exec", "질문\n\n(ultra-search:test-3 — ignore this line)"], home, calls)
    monkeypatch.setenv("ULTRA_SEARCH_ASIDE_HOME", str(home))

    _, payload, _ = run_cli("sessions", "--mine", "--runs-dir", str(tmp_path / "runs"))

    assert [s["run_id"] for s in payload["sessions"]] == ["test-3"]


def test_the_fake_can_fail_the_way_a_real_failure_looks(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"

    assert run_fake(["exec", "질문"], home, calls, scenario="fail").returncode == 1


def test_a_replay_follows_the_prompt_and_keeps_a_torn_tail_torn(tmp_path: Path) -> None:
    home, calls = tmp_path / "home", tmp_path / "calls"
    replay = tmp_path / "replay.jsonl"
    replay.write_text(
        json.dumps({"role": "user", "content": "recorded prompt"}) + "\n"
        + json.dumps({"__sleep__": 0.1}) + "\n"
        + json.dumps(tool("websearch", "r")) + "\n"
        + '{"role":"assistant","content":"half'
    )

    run_fake(["exec", "새 질문"], home, calls, FAKE_ASIDE_REPLAY=str(replay))

    (session,) = (home / "u" / "0" / "sessions").iterdir()
    written = (session / "messages.jsonl").read_text()
    assert "recorded prompt" not in written, "the recording's own prompt is replaced by this run's"
    assert json.loads(written.splitlines()[0])["content"][0]["text"] == "새 질문"
    assert json.loads(written.splitlines()[1])["toolName"] == "websearch"
    assert written.endswith('"content":"half')


def test_a_signed_out_fake_has_an_empty_roster(tmp_path: Path) -> None:
    p = run_fake(["account", "list"], tmp_path / "home", tmp_path / "calls", FAKE_ASIDE_ACCOUNTS="none")

    assert p.returncode == 0
    assert json.loads(p.stdout) == {"accounts": []}


# --- what the fake promises about the browser --------------------------------------------


def test_every_snippet_names_itself_on_its_first_line() -> None:
    """The fake tells snippets apart by this line, so a snippet without it would reach the
    fake as unrecognised code and every page test would be answering the wrong question."""
    for js in SNIPPETS.glob("*.js"):
        assert js.read_text(encoding="utf-8").splitlines()[0] == f"// snippet: {js.stem}", js.name


def test_the_fake_repl_prints_ndjson_for_code_that_is_not_a_snippet(tmp_path: Path) -> None:
    p = run_fake(["repl", "console.log(1)"], tmp_path / "home", tmp_path / "calls")

    assert ndjson(p)[0]["ok"] is True


def test_fetch_batch_answers_each_url_and_a_missing_one_as_a_404(tmp_path: Path) -> None:
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"fetch_batch": {"https://e.test/a": {"status": 200, "content_type": "text/html",
                                                                       "kind": "text", "text": "<p>a</p>"}}}))

    p = run_fake(["repl", snippet("fetch_batch", {"urls": ["https://e.test/a", "https://e.test/missing"],
                                                  "perUrlTimeoutMs": 1, "budgetMs": 1})],
                 tmp_path / "home", tmp_path / "calls", FAKE_ASIDE_REPL_ROUTES=str(routes))

    a, missing, done = ndjson(p)
    assert (a["url"], a["status"], a["text"]) == ("https://e.test/a", 200, "<p>a</p>")
    assert (missing["url"], missing["status"], missing["kind"]) == ("https://e.test/missing", 404, "text")
    assert done == {"kind": "batch_done", "requested": 2, "elapsed_ms": 1, "hit_budget": False}


def test_a_sequence_route_answers_in_call_order_and_repeats_its_last(tmp_path: Path) -> None:
    routes = tmp_path / "routes.json"
    steps = [{"status": 0, "kind": "error", "error": "timeout"}, {"status": 200, "kind": "text", "text": "ok"}]
    routes.write_text(json.dumps({"fetch_batch": {"https://e.test/a": {"sequence": steps}}}))
    code = snippet("fetch_batch", {"urls": ["https://e.test/a"], "perUrlTimeoutMs": 1, "budgetMs": 1})

    got = [ndjson(run_fake(["repl", code], tmp_path / "home", tmp_path / "calls", FAKE_ASIDE_REPL_ROUTES=str(routes)))[0]
           for _ in range(3)]

    assert [g.get("error") or g["text"] for g in got] == ["timeout", "ok", "ok"]


def test_tab_sitemap_and_links_answer_like_their_snippets(tmp_path: Path) -> None:
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({
        "tab_one": {"https://e.test/t": {"status": 200, "kind": "text", "text": "<p>t</p>", "visible_text": "t"}},
        "sitemap": {"https://e.test/sitemap.xml": ["https://e.test/1"]},
        "links": {"https://e.test/": ["/x"]},
    }))
    env = {"FAKE_ASIDE_REPL_ROUTES": str(routes)}

    def call(name: str, args: dict) -> list[dict]:
        return ndjson(run_fake(["repl", snippet(name, args)], tmp_path / "home", tmp_path / "calls", **env))

    assert call("tab_one", {"url": "https://e.test/t", "waitMs": 1, "settleMs": 1})[0]["via"] == "tab"
    assert call("tab_one", {"url": "https://e.test/gone", "waitMs": 1, "settleMs": 1})[0]["kind"] == "error"
    assert [r["kind"] for r in call("sitemap", {"roots": ["https://e.test/sitemap.xml", "https://e.test/robots.txt"],
                                                "perUrlTimeoutMs": 1, "budgetMs": 1})] == ["url", "sitemap_miss", "sitemap_done"]
    assert [r["kind"] for r in call("links", {"pages": ["https://e.test/", "https://e.test/none"],
                                              "perUrlTimeoutMs": 1, "budgetMs": 1})] == ["hrefs", "link_miss", "links_done"]


# --- the same questions, asked of the real binary ----------------------------------------


@pytest.mark.live
def test_the_real_binary_writes_a_transcript_the_cli_can_find(tmp_path: Path) -> None:
    """If this fails and the fake's equivalent passes, the fake has drifted."""
    marker = "ultra-search:contract-live"
    prompt = f"Reply with the single word OK.\n\n({marker} — ignore this line)"
    subprocess.run(["aside", "exec", prompt], capture_output=True, text=True, timeout=180)

    p = subprocess.run([sys.executable, str(SCRIPTS / "ultra_search.py"), "sessions", "--mine", "--search", marker,
                        "--runs-dir", str(tmp_path)], capture_output=True, text=True, timeout=60)

    found = json.loads(p.stdout)["sessions"]
    assert [s["run_id"] for s in found] == ["contract-live"], "the real transcript must be findable by its prompt marker"


@pytest.mark.live
def test_the_real_repl_still_lacks_the_globals_the_snippets_avoid() -> None:
    """The snippets work around a specific sandbox shape. If that shape widens, the
    workarounds become unnecessary complexity -- and if it narrows further, they break."""
    code = (
        'const r={}; for (const n of ["URL","AbortController","fetch","Buffer","fs","path","pwd"]) '
        '{ try { r[n]=typeof eval(n); } catch(e) { r[n]="undefined"; } } console.log(JSON.stringify(r));'
    )
    p = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=120)
    got = json.loads(next(line for line in p.stdout.splitlines() if line.startswith("{")))

    assert got["URL"] == "undefined"
    assert got["AbortController"] == "undefined"
    assert got["fetch"] == "function"
    assert got["fs"] == "object"


@pytest.mark.live
def test_the_real_repl_fs_is_promise_based_without_sync_variants() -> None:
    code = 'console.log(JSON.stringify({keys:Object.keys(fs)}));'
    p = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=120)
    keys = json.loads(next(line for line in p.stdout.splitlines() if line.startswith("{")))["keys"]

    assert "writeFile" in keys
    assert not any(k.endswith("Sync") for k in keys)


# --- the snippets must only use globals the sandbox actually has --------------------------


def test_no_snippet_reaches_for_a_global_the_sandbox_lacks() -> None:
    """Measured absent from the REPL sandbox. A snippet that touches one of these throws
    before its own try block, so the rejection is swallowed by Promise.allSettled and the
    snippet reports an empty result instead of an error -- which is how sitemap discovery
    silently degraded to link-following for a while without any test noticing."""
    forbidden = ("AbortController", "new URL(", "URLSearchParams", "structuredClone", "require(", "writeFileSync")

    offenders = []
    for js in SNIPPETS.glob("*.js"):
        code = "\n".join(
            line for line in js.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("//")
        )
        offenders += [f"{js.name}: {tok}" for tok in forbidden if tok in code]

    assert offenders == []
