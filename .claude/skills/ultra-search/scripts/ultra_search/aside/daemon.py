"""The daemon as the app runs it: its health endpoint, the signed-in account, and its MCP tool list."""
from __future__ import annotations

import json
import os
import re
import subprocess

from ultra_search.aside.process import aside_bin
from ultra_search.outcome import AsideUnavailable

DAEMON_URL = "http://127.0.0.1:21420/"


def daemon_url() -> str:
    """The health endpoint of the daemon `aside exec` will use.

    The aside CLI takes DAEMON_BASE_URL when it is set, else the stable daemon's port (the
    installed build fixes its own variant, whatever the environment says); checking any other
    daemon would refuse work the real one can do, or pass work it cannot.
    ULTRA_SEARCH_DAEMON_URL overrides both, for tests.
    """
    if os.environ.get("ULTRA_SEARCH_DAEMON_URL"):
        return os.environ["ULTRA_SEARCH_DAEMON_URL"]
    if os.environ.get("DAEMON_BASE_URL"):
        return os.environ["DAEMON_BASE_URL"].rstrip("/") + "/"
    return DAEMON_URL


def daemon_status() -> dict:
    """{ok, version, detail}: whether the daemon answers and says it is ready."""
    import urllib.error
    import urllib.request

    url = daemon_url()
    # Straight to the daemon: it is on this machine, and a proxy from the environment would
    # answer for it -- or refuse to.
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with direct.open(url, timeout=5) as r:
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


def account_status() -> dict:
    """{ok, detail}: whether an account is signed in. A signed-out browser fetches public pages
    fine and silently loses every logged-in one, which is the capability this tool exists for."""
    try:
        proc = subprocess.run([aside_bin(), "account", "list"], capture_output=True, text=True, timeout=30)
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


def mcp_tools() -> list[dict]:
    """Every tool the running daemon lists over MCP, as it describes them."""
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
            [aside_bin(), "mcp"],
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
    return tools
