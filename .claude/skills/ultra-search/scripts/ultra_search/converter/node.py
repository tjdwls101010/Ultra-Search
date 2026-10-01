"""Running the Node side: the converter script, the anydoc binary, node itself and npm.

This folder is the npm package `setup` installs: its lockfile pins the converter packages,
and `node_modules/` lands beside it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from ultra_search.outcome import AsideUnavailable

HERE = Path(__file__).resolve().parent
TO_MARKDOWN = HERE / "to_markdown.mjs"
MODULES = HERE / "node_modules"
ANYDOC = MODULES / ".bin" / "anydoc"
#: anydoc's exit status for a PDF with no text layer.
NO_TEXT_LAYER = 3


def to_markdown(html: str, url: str) -> dict:
    """{ok, markdown, title, author, published, site, words} for a page, or {ok: False, error}."""
    payload = json.dumps({"html": html, "url": url}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            ["node", str(TO_MARKDOWN)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "node is not installed; run `setup`"}
    except subprocess.SubprocessError as e:
        return {"ok": False, "error": f"markdown conversion failed: {e}"}
    for line in (proc.stdout or "").splitlines():
        if line.startswith("{"):
            try:
                result = json.loads(line)
            except ValueError:
                continue
            if not result.get("ok"):
                return {"ok": False, "error": str(result.get("message") or "extraction failed")}
            return {
                "ok": True,
                "markdown": result.get("markdown") or "",
                "title": result.get("title") or "",
                "author": result.get("author") or "",
                "published": result.get("published") or "",
                "site": result.get("site") or "",
                "words": int(result.get("words") or 0),
            }
    return {"ok": False, "error": (proc.stderr or "no output from to_markdown.mjs").strip()[:400]}


def document_text(path: str | Path) -> dict:
    """{status, text, error} for a saved document: ok, needs_ocr (no text layer), or unsupported."""
    code, out, err = _run_anydoc(Path(path))
    if code == 0:
        return {"status": "ok", "text": out or "", "error": ""}
    if code == NO_TEXT_LAYER:
        # No text layer. Hosted OCR exists but ships the document to a third party, which
        # nobody has agreed to -- so this is reported, not silently escalated.
        return {"status": "needs_ocr", "text": "", "error": (err or "").strip()[:300] or "the PDF has no text layer"}
    return {"status": "unsupported", "text": "", "error": (err or out or "").strip()[:300] or f"anydoc exit {code}"}


def _run_anydoc(path: Path) -> tuple[int, str, str]:
    if not ANYDOC.exists():
        return 1, "", "document conversion is not installed; run `setup`"
    try:
        proc = subprocess.run([str(ANYDOC), str(path)], capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return 1, "", "document conversion is not installed; run `setup`"
    except subprocess.SubprocessError as e:
        return 1, "", f"document conversion failed: {e}"
    return proc.returncode, proc.stdout, proc.stderr


def node_minimum() -> str:
    """The newest Node any locked converter package requires, read from the lockfile itself.

    `setup` installs exactly what the lockfile pins, so this is the requirement that holds --
    and it moves with the lockfile rather than going stale in a constant.
    """
    return _version_text(_minimum())


def _minimum() -> tuple[int, ...]:
    try:
        lock = json.loads((HERE / "package-lock.json").read_text(encoding="utf-8"))
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


def check() -> dict:
    """{node_ok, node_detail, packages_ok, packages_detail, node_minimum}: whether conversion can run here."""
    node_ok, node_detail = _node_status()
    have = (MODULES / "defuddle").exists() and ANYDOC.exists()
    return {
        "node_ok": node_ok,
        "node_detail": node_detail,
        "node_minimum": node_minimum(),
        "packages_ok": have,
        "packages_detail": str(MODULES) if have else "not installed",
    }


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
    minimum = _minimum()
    return version >= minimum, f"{node} v{_version_text(version)} (needs {_version_text(minimum)}+)"


def install() -> dict:
    """{ok, dir, detail}: `npm ci` here -- exactly the versions the lockfile pins, which are the ones measured."""
    if not shutil.which("npm"):
        raise AsideUnavailable("npm is not on PATH",
                               fix=f"Install Node {node_minimum()} or newer, which ships npm.")
    try:
        proc = subprocess.run(["npm", "ci"], cwd=str(HERE), capture_output=True, text=True, timeout=900)
        ok, detail = proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr) or ""
    except (OSError, subprocess.SubprocessError) as e:
        ok, detail = False, f"could not run `npm ci`: {e}"
    return {"ok": ok, "dir": str(HERE), "detail": detail.strip()[-1500:]}
