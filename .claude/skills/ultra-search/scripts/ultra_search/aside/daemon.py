"""The daemon as the app runs it: its health endpoint and the signed-in account."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from ultra_search.aside.process import aside_bin
from ultra_search.aside.repl import START_LIMIT, round_trip
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


#: After Aside could not be started there is nothing more to open: what it said is in the message, and doctor checks
#: each part of the environment apart.
START_FIX = "Run `doctor`: it reports each part of the environment on its own."


def ensure_ready(*, timeout: float = START_LIMIT) -> bool:
    """Make Aside able to take work, before any: True when the daemon did not answer ready and the `aside repl` round
    trip that followed worked -- not that Aside was closed or that this started it, since it may have been starting
    already, or something else may have opened it.

    A daemon answering ready costs one local request and nothing more. Otherwise the round trip: the CLI opens a closed
    Aside itself and waits for it, and a snippet coming back proves the browser takes work, which a health answer does
    not. What the CLI said meanwhile goes to stderr as it said it.

    Before the work rather than inside it: work started on an Aside that cannot take it fails in shapes that read as
    findings -- a fetch's `no response`, a map of an empty site -- and a `search` would reserve a run, leave the
    failure to `result`, and get the CLI's start-up line in its stdout.
    """
    aside_bin()
    if daemon_status()["ok"]:
        return False
    try:
        worked, detail, said = round_trip(timeout)
    except AsideUnavailable as e:
        raise AsideUnavailable(f"the Aside daemon did not report ready and {e.message}", fix=START_FIX) from e
    if not worked:
        raise AsideUnavailable(f"the Aside daemon did not report ready and `aside repl` failed: {detail}",
                               fix=START_FIX)
    if said:
        sys.stderr.write(said if said.endswith("\n") else said + "\n")
    return True


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

