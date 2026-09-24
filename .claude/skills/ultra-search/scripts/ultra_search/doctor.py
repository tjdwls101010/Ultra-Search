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
from pathlib import Path

from ultra_search import contract
from ultra_search.aside import process, repl, sessions
from ultra_search.contract import AsideUnavailable
from ultra_search.pages.classify import CONVERTER
from ultra_search.runs import registry


def dispatch(args) -> int:
    if args.command == "setup":
        return _setup()
    if args.command == "repl-api":
        return _repl_api(args)
    return _doctor(args)


# --- doctor ------------------------------------------------------------------------------


def _doctor(args) -> int:
    checks: list[dict] = []
    ok = True

    binary = None
    try:
        binary = process.aside_bin()
        checks.append(_check("aside binary", True, binary))
    except AsideUnavailable as e:
        ok = False
        checks.append(_check("aside binary", False, e.message, e.fix))

    if binary:
        try:
            version = process.version()
            same = version.startswith(process.VERIFIED_VERSION)
            checks.append(
                _check(
                    "aside version",
                    True,
                    version,
                    None
                    if same
                    else f"this skill's behaviour was measured against {process.VERIFIED_VERSION}; "
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
    elif daemon.get("version") and not str(daemon["version"]).startswith(process.VERIFIED_DAEMON_VERSION):
        daemon_fix = (
            f"measured against daemon {process.VERIFIED_DAEMON_VERSION}; the daemon decides what a run "
            "records, so a difference here is the first thing to suspect if results look thin"
        )
    checks.append(_check("aside daemon", daemon["ok"], daemon["detail"], daemon_fix))
    ok = ok and daemon["ok"]

    if binary and daemon["ok"]:
        # A round trip, not just a health endpoint: the daemon answering HTTP and the
        # daemon running a snippet are different things, and only the second one matters.
        try:
            probed, detail = _repl_probe()
            checks.append(_check("browser repl", probed, detail,
                                 None if probed else "Open the Aside app, then retry."))
            ok = ok and probed
        except (AsideUnavailable, repl.ReplTimeout) as e:
            ok = False
            checks.append(_check("browser repl", False, str(e), "Open the Aside app, then retry."))

    if binary and daemon["ok"]:
        account = _account_status()
        checks.append(_check("aside account", account["ok"], account["detail"],
                             None if account["ok"] else "Sign in to Aside, then re-run `doctor`."))
        ok = ok and account["ok"]

    node_ok, node_detail = _node_status()
    checks.append(_check("node", node_ok, node_detail,
                         None if node_ok else f"Install Node {_version_text(_node_minimum())} or newer; the converter packages require it."))
    ok = ok and node_ok

    modules = CONVERTER / "node_modules"
    have_modules = (modules / "defuddle").exists() and (modules / ".bin" / "anydoc").exists()
    checks.append(_check("page conversion", have_modules,
                         str(modules) if have_modules else "not installed",
                         None if have_modules else "Run `setup`."))
    # Without these, `fetch` reaches the page and then fails to convert it -- a failure
    # that reads as a network problem unless doctor says otherwise.
    ok = ok and have_modules

    home = sessions.sessions_root()
    checks.append(_check("aside sessions", home.is_dir(), str(home),
                         None if home.is_dir() else "Aside has not been run for this account yet."))
    ok = ok and home.is_dir()

    runs_root = registry.resolve_runs_dir(getattr(args, "runs_dir", None))
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
    return 0 if ok else contract.EXIT_ASIDE


def _check(name: str, ok: bool, detail: str, fix: str | None = None) -> dict:
    out = {"check": name, "ok": ok, "detail": detail}
    if fix:
        out["fix"] = fix
    return out


def _repl_probe() -> tuple[bool, str]:
    """Run a snippet whose output is known and check that exact output came back.

    Any output is not enough: a sandbox that refuses the snippet still prints its refusal.
    """
    code = 'console.log(JSON.stringify({ok:true}));'
    try:
        proc = subprocess.run([process.aside_bin(), "repl", code], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise AsideUnavailable(f"repl round trip failed: {e}") from e
    if proc.returncode == 0 and {"ok": True} in repl.parse_ndjson(proc.stdout):
        return True, "round trip ok"
    said = (proc.stdout or proc.stderr or "").strip()[:200] or "no output"
    return False, f"exit {proc.returncode}: {said}"


def _writable(path: Path) -> tuple[bool, str]:
    import tempfile

    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        # A fresh name each time: a fixed one can collide with something already there and
        # report a writable directory as unwritable.
        fd, probe = tempfile.mkstemp(prefix=".write-probe-", dir=path)
        os.close(fd)
        os.unlink(probe)
        return True, str(path)
    except OSError as e:
        return False, f"{path} is not writable ({e})"


def _account_status() -> dict:
    """Whether an account is signed in. A signed-out browser fetches public pages fine and
    silently loses every logged-in one, which is the capability this tool exists for."""
    try:
        proc = subprocess.run([process.aside_bin(), "account", "list"], capture_output=True, text=True, timeout=30)
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

    url = process.daemon_url()
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


def _node_minimum() -> tuple[int, ...]:
    """The newest Node any locked converter package requires, read from the lockfile itself.

    `setup` installs exactly what the lockfile pins, so this is the requirement that holds --
    and it moves with the lockfile rather than going stale in a constant.
    """
    try:
        lock = json.loads((CONVERTER / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (20,)
    floors = [(20,)]
    for pkg in (lock.get("packages") or {}).values():
        m = re.search(r">=\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", str((pkg.get("engines") or {}).get("node") or ""))
        if m:
            floors.append(tuple(int(g) for g in m.groups() if g is not None))
    return max(floors)


def _version_text(version: tuple[int, ...]) -> str:
    return ".".join(str(v) for v in version)


def _node_status() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "not on PATH"
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"could not run `node --version`: {e}"
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", out)
    if not m:
        return False, f"{node} reported an unreadable version {out!r}"
    version = tuple(int(g) for g in m.groups())
    minimum = _node_minimum()
    return version >= minimum, f"{node} v{_version_text(version)} (needs {_version_text(minimum)}+)"


def _setup() -> int:
    if not shutil.which("npm"):
        raise AsideUnavailable("npm is not on PATH",
                               fix=f"Install Node {_version_text(_node_minimum())} or newer, which ships npm.")
    # `ci`, not `install`: exactly the versions the lockfile pins, which are the ones measured.
    try:
        proc = subprocess.run(["npm", "ci"], cwd=str(CONVERTER), capture_output=True, text=True, timeout=900)
        ok, detail = proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr) or ""
    except (OSError, subprocess.SubprocessError) as e:
        ok, detail = False, f"could not run `npm ci`: {e}"
    print(json.dumps(
        {"ok": ok, "command": "setup", "dir": str(CONVERTER), "detail": detail.strip()[-1500:]},
        ensure_ascii=False,
    ))
    return 0 if ok else contract.EXIT_ASIDE


# --- repl-api -----------------------------------------------------------------------------


def _repl_api(args) -> int:
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
            [process.aside_bin(), "mcp"],
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
    if getattr(args, "all", False):
        print(json.dumps({"ok": True, "command": "repl-api", "tools": tools}, ensure_ascii=False))
        return 0
    repl_tool = next((t for t in tools if isinstance(t, dict) and t.get("name") == "repl"), None)
    if repl_tool is None:
        raise AsideUnavailable("the daemon lists no repl tool", fix="Run `repl-api --all` to see what it does list.",
                               tools=[t.get("name") for t in tools if isinstance(t, dict)])
    print(json.dumps({
        "ok": True,
        "command": "repl-api",
        "tool": repl_tool,
        "run": "Run code with `aside repl '<code>'`. This skill's permission rule covers only its own CLI, "
               "so expect an approval prompt for it.",
    }, ensure_ascii=False))
    return 0
