"""`doctor` and `setup` -- the environment.

`doctor` answers one question: would a command fail right now, and why. It exits 3 when
something it can see would stop one, so a caller can tell "Aside is closed" from "the
search found nothing" without reading prose.
"""
from __future__ import annotations

import os
from pathlib import Path

from ultra_search import aside, converter, outcome
from ultra_search.outcome import AsideUnavailable, Reply


# --- doctor ------------------------------------------------------------------------------


def doctor(root: Path) -> Reply:
    checks: list[dict] = []
    ok = True

    binary = None
    try:
        binary = aside.aside_bin()
        checks.append(_check("aside binary", True, binary))
    except AsideUnavailable as e:
        ok = False
        checks.append(_check("aside binary", False, e.message, e.fix))

    if binary:
        try:
            version = aside.version()
            same = version.startswith(aside.VERIFIED_VERSION)
            checks.append(
                _check(
                    "aside version",
                    True,
                    version,
                    note=None
                    if same
                    else f"this skill's behaviour was measured against {aside.VERIFIED_VERSION}; "
                    "if runs behave oddly, that difference is the first thing to suspect",
                )
            )
        except AsideUnavailable as e:
            ok = False
            checks.append(_check("aside version", False, e.message, e.fix))

    daemon = aside.daemon_status()
    daemon_note = None
    if daemon["ok"] and daemon.get("version") and not str(daemon["version"]).startswith(aside.VERIFIED_DAEMON_VERSION):
        daemon_note = (
            f"measured against daemon {aside.VERIFIED_DAEMON_VERSION}; the daemon decides what a run "
            "records, so a difference here is the first thing to suspect if results look thin"
        )
    checks.append(_check("aside daemon", daemon["ok"], daemon["detail"], None if daemon["ok"] else "Open the Aside app.",
                         note=daemon_note))
    ok = ok and daemon["ok"]

    if binary and daemon["ok"]:
        try:
            probed, detail = aside.repl_probe()
            checks.append(_check("browser repl", probed, detail,
                                 None if probed else "Open the Aside app, then retry."))
            ok = ok and probed
        except (AsideUnavailable, aside.ReplTimeout) as e:
            ok = False
            checks.append(_check("browser repl", False, str(e), "Open the Aside app, then retry."))

    if binary and daemon["ok"]:
        account = aside.account_status()
        checks.append(_check("aside account", account["ok"], account["detail"],
                             None if account["ok"] else "Sign in to Aside, then re-run `doctor`."))
        ok = ok and account["ok"]

    conversion = converter.check()
    checks.append(_check("node", conversion["node_ok"], conversion["node_detail"],
                         None if conversion["node_ok"] else
                         f"Install Node {conversion['node_minimum']} or newer; the converter packages require it."))
    ok = ok and conversion["node_ok"]
    checks.append(_check("page conversion", conversion["packages_ok"], conversion["packages_detail"],
                         None if conversion["packages_ok"] else "Run `setup`."))
    # Without these, `fetch` reaches the page and then fails to convert it -- a failure
    # that reads as a network problem unless doctor says otherwise.
    ok = ok and conversion["packages_ok"]

    home = aside.sessions_root()
    checks.append(_check("aside sessions", home.is_dir(), str(home),
                         None if home.is_dir() else "Aside has not been run for this account yet."))
    ok = ok and home.is_dir()

    # Tried, not assumed. An unwritable runs directory lets doctor pass and then fails the
    # first `search` at the moment it reserves a run -- which reads as the search breaking.
    writable, detail = _writable(root)
    checks.append(_check("runs dir", writable, detail,
                         None if writable else "Choose a writable --runs-dir."))
    ok = ok and writable

    payload = {
        "ok": ok,
        "command": "doctor",
        "checks": checks,
        "notes": [
            # Two things a caller will otherwise learn the expensive way.
            "aside removes old sessions on its own schedule; a run's own copy under the runs dir outlives that",
            "nothing here cancels a run; its work and its credit use stop only from Aside itself",
        ],
    }
    return Reply(payload, outcome.OK if ok else outcome.ASIDE_UNAVAILABLE)


def _check(name: str, ok: bool, detail: str, fix: str | None = None, *, note: str | None = None) -> dict:
    """A check: a fix only for what is broken; a note for what is fine but worth knowing."""
    out = {"check": name, "ok": ok, "detail": detail}
    if fix:
        out["fix"] = fix
    if note:
        out["note"] = note
    return out


def _writable(path: Path) -> tuple[bool, str]:
    """Whether the runs dir can be written, tried in it -- or, before it exists, in the nearest
    directory it would be made in, so checking leaves nothing behind."""
    import tempfile

    try:
        here = Path(path)
        while not here.exists() and here != here.parent:
            here = here.parent
        # A fresh name each time: a fixed one can collide with something already there and
        # report a writable directory as unwritable.
        fd, probe = tempfile.mkstemp(prefix=".write-probe-", dir=here)
        os.close(fd)
        os.unlink(probe)
        return True, str(path)
    except OSError as e:
        return False, f"{path} is not writable ({e})"


# --- setup --------------------------------------------------------------------------------


def setup() -> Reply:
    installed = converter.install()
    return Reply({"ok": installed["ok"], "command": "setup", **{k: installed[k] for k in ("dir", "detail")}},
                 outcome.OK if installed["ok"] else outcome.ASIDE_UNAVAILABLE)

