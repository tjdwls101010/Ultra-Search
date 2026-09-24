"""`doctor`, `setup` and `repl-api` -- the environment, and the browser's own API docs.

`doctor` answers one question: would a command fail right now, and why. It exits 3 when
something it can see would stop one, so a caller can tell "Aside is closed" from "the
search found nothing" without reading prose.

`repl-api` prints the REPL's documentation from the running daemon rather than a copy
kept here. A copy would be a second thing that can be wrong, and it is the version
installed on this machine that decides what the snippets may use.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _errors
import _exec
import _registry
import _repl
import _store
from _errors import AsideUnavailable

PAGE_DIR = Path(__file__).resolve().parent / "page"
DAEMON_URL = "http://127.0.0.1:21420/"


def daemon_url() -> str:
    """The daemon's health endpoint; ULTRA_SEARCH_DAEMON_URL points doctor at another one."""
    return os.environ.get("ULTRA_SEARCH_DAEMON_URL") or DAEMON_URL


def dispatch(args) -> int:
    if args.command == "setup":
        return _setup()
    if args.command == "repl-api":
        return _repl_api()
    return _doctor(args)


# --- doctor ------------------------------------------------------------------------------


def _doctor(args) -> int:
    checks: list[dict] = []
    ok = True

    binary = None
    try:
        binary = _exec.aside_bin()
        checks.append(_check("aside binary", True, binary))
    except AsideUnavailable as e:
        ok = False
        checks.append(_check("aside binary", False, e.message, e.fix))

    if binary:
        try:
            version = _exec.version()
            same = version.startswith(_exec.VERIFIED_VERSION)
            checks.append(
                _check(
                    "aside version",
                    True,
                    version,
                    None
                    if same
                    else f"this skill's behaviour was measured against {_exec.VERIFIED_VERSION}; "
                    "if runs behave oddly, that difference is the first thing to suspect",
                )
            )
        except AsideUnavailable as e:
            ok = False
            checks.append(_check("aside version", False, e.message, e.fix))

    daemon = _daemon_status()
    daemon_fix = None
    if not daemon["ok"]:
        daemon_fix = "Open the Aside app."
    elif daemon.get("version") and not str(daemon["version"]).startswith(_exec.VERIFIED_DAEMON_VERSION):
        daemon_fix = (
            f"measured against daemon {_exec.VERIFIED_DAEMON_VERSION}; the daemon decides what a run "
            "records, so a difference here is the first thing to suspect if results look thin"
        )
    checks.append(_check("aside daemon", daemon["ok"], daemon["detail"], daemon_fix))
    ok = ok and daemon["ok"]

    if binary and daemon["ok"]:
        # A round trip, not just a health endpoint: the daemon answering HTTP and the
        # daemon running a snippet are different things, and only the second one matters.
        try:
            lines = _repl_probe()
            checks.append(_check("browser repl", bool(lines), "round trip ok" if lines else "no output"))
            ok = ok and bool(lines)
        except (AsideUnavailable, _repl.ReplTimeout) as e:
            ok = False
            checks.append(_check("browser repl", False, str(e), "Open the Aside app, then retry."))

    if binary and daemon["ok"]:
        account = _account_status()
        checks.append(_check("aside account", account["ok"], account["detail"],
                             None if account["ok"] else "Sign in to Aside, then re-run `doctor`."))
        ok = ok and account["ok"]

    node = shutil.which("node")
    checks.append(_check("node", bool(node), node or "not on PATH", None if node else "Install Node 20 or newer."))
    ok = ok and bool(node)

    modules = PAGE_DIR / "node_modules"
    have_modules = (modules / "defuddle").exists() and (modules / ".bin" / "anydoc").exists()
    checks.append(_check("page conversion", have_modules,
                         str(modules) if have_modules else "not installed",
                         None if have_modules else "Run `setup`."))
    # Without these, `fetch` reaches the page and then fails to convert it -- a failure
    # that reads as a network problem unless doctor says otherwise.
    ok = ok and have_modules

    sessions = _store.sessions_root()
    checks.append(_check("aside sessions", sessions.is_dir(), str(sessions),
                         None if sessions.is_dir() else "Aside has not been run for this account yet."))
    ok = ok and sessions.is_dir()

    runs_root = _registry.resolve_runs_dir(getattr(args, "runs_dir", None))
    # Tried, not assumed. An unwritable runs directory lets doctor pass and then fails the
    # first `search` at the moment it reserves a run -- which reads as the search breaking.
    writable, detail = _writable(runs_root)
    checks.append(_check("runs dir", writable, detail,
                         None if writable else "Choose a writable --runs-dir."))
    ok = ok and writable

    payload = {
        "ok": ok,
        "command": "doctor",
        "checks": checks,
        "notes": [
            # Two things a caller will otherwise learn the expensive way.
            "aside deletes CLI sessions within about a day; a run's own copy under the runs dir outlives that",
            "`stop` ends the watching, not the run -- the daemon keeps working and keeps spending credits",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else _errors.EXIT_ASIDE


def _check(name: str, ok: bool, detail: str, fix: str | None = None) -> dict:
    out = {"check": name, "ok": ok, "detail": detail}
    if fix:
        out["fix"] = fix
    return out


def _repl_probe() -> list[dict]:
    code = 'console.log(JSON.stringify({ok:true}));'
    try:
        proc = subprocess.run([_exec.aside_bin(), "repl", code], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"repl round trip failed: {e}") from e
    return [json.loads(l) for l in proc.stdout.splitlines() if l.strip().startswith("{")]


def _writable(path: Path) -> tuple[bool, str]:
    probe = Path(path) / ".write-probe"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True, str(path)
    except OSError as e:
        return False, f"{path} is not writable ({e})"


def _account_status() -> dict:
    """Whether an account is signed in. A signed-out browser fetches public pages fine and
    silently loses every logged-in one, which is the capability this tool exists for."""
    try:
        proc = subprocess.run([_exec.aside_bin(), "account", "list"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "detail": f"could not run `aside account list`: {e}"}
    out = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        return {"ok": False, "detail": out[:200] or f"exit {proc.returncode}"}
    # Exit 0 with an empty roster is a signed-out browser, not a healthy one -- and a
    # signed-out browser fetches public pages perfectly while silently losing every page
    # this tool exists to reach. So the answer has to come from the content, not the
    # command having run.
    flat = " ".join(out.split())
    try:
        parsed = json.loads(out)
        accounts = parsed.get("accounts") if isinstance(parsed, dict) else parsed
        if isinstance(accounts, list):
            return {"ok": bool(accounts), "detail": flat[:200] or "no accounts"}
    except ValueError:
        pass
    signed_in = "signed in" in flat.lower() or bool(re.search(r"^\s*\*?\s*u\d", out, re.M))
    return {"ok": signed_in, "detail": flat[:200] or "no accounts listed"}


def _daemon_status() -> dict:
    import urllib.error
    import urllib.request

    url = daemon_url()
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
        sem = body.get("semaphore") or {}
        return {
            "ok": bool(body.get("ready")),
            "version": body.get("version"),
            "detail": f"v{body.get('version')} ready={body.get('ready')} "
            f"running={body.get('runningSessionCount')} slots={sem.get('available')}/{sem.get('capacity')}",
        }
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        return {"ok": False, "version": None, "detail": f"no answer from {url} ({e})"}


# --- setup --------------------------------------------------------------------------------


def _setup() -> int:
    if not shutil.which("npm"):
        raise AsideUnavailable("npm is not on PATH", fix="Install Node 20 or newer, which ships npm.")
    proc = subprocess.run(["npm", "install"], cwd=str(PAGE_DIR), capture_output=True, text=True, timeout=900)
    ok = proc.returncode == 0
    print(json.dumps(
        {
            "ok": ok,
            "command": "setup",
            "dir": str(PAGE_DIR),
            "detail": (proc.stdout or "").strip()[-1500:] if ok else (proc.stderr or "").strip()[-1500:],
        },
        ensure_ascii=False,
    ))
    return 0 if ok else _errors.EXIT_ASIDE


# --- repl-api -----------------------------------------------------------------------------


def _repl_api() -> int:
    """Ask the daemon over MCP what its repl tool accepts."""
    request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
    })
    init = json.dumps({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ultra-search", "version": "1.0"}},
    })
    notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    try:
        proc = subprocess.run(
            [_exec.aside_bin(), "mcp"],
            input=f"{init}\n{notify}\n{request}\n",
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"could not run `aside mcp`: {e}") from e

    tools = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        found = ((msg.get("result") or {}).get("tools")) or []
        if found:
            tools = found
    if not tools:
        raise AsideUnavailable(
            "the daemon returned no tool list",
            fix="Check the Aside app is running, then re-run `doctor`.",
            stderr=(proc.stderr or "").strip()[-400:],
        )
    print(json.dumps({"ok": True, "command": "repl-api", "tools": tools}, ensure_ascii=False))
    return 0
