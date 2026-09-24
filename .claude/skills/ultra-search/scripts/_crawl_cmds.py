"""`map` and `crawl`.

`map` is the cheap half: it discovers URLs and writes a manifest without fetching any
content, so a caller can look at what a site has before committing to downloading it.
`crawl --from` consumes that same manifest, which is what keeps a look-then-fetch from
walking the site twice.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

import _crawl
import _contract
import _page
import _repl
from _contract import ArgumentError


def dispatch(args, runs_root: Path) -> int:
    return _map(args, runs_root) if args.command == "map" else _crawl_cmd(args, runs_root)


def _providers(args):
    return {
        "sitemap_provider": None if getattr(args, "no_sitemap", False) else _repl.sitemap,
        "links_provider": _repl.links,
    }


def _map(args, runs_root: Path) -> int:
    urls, coverage = _crawl.discover(
        args.url,
        depth=args.depth,
        max_urls=args.max_urls,
        include=args.include,
        exclude=args.exclude,
        use_sitemap=not args.no_sitemap,
        **_providers(args),
    )
    manifest = _crawl.build_manifest(args.url, [], urls=urls)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(out)
    print(json.dumps({"ok": True, "command": "map", **manifest, "coverage": coverage}, ensure_ascii=False))
    # Nothing read -- no sitemap and not one page's links -- is no map at all, even when the
    # root itself is listed.
    saw_site = coverage["sitemap"] or coverage["pages_read"] > 0
    return 0 if urls and saw_site else _contract.EXIT_EMPTY


def _crawl_cmd(args, runs_root: Path) -> int:
    if args.out:
        _refuse_used_folder(Path(args.out).expanduser())
    if args.from_manifest:
        source = Path(args.from_manifest).expanduser()
        try:
            manifest = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ArgumentError(f"could not read manifest {source}: {e}", fix="Produce one with `map --out`.") from e
        urls = _crawl.urls_from_manifest(manifest)
        if urls is None:
            raise ArgumentError(f"{source} is not a manifest written by `map` or `crawl`",
                                fix="Produce one with `map --out`.")
        root = manifest.get("root") or ""
        coverage = None
        if not urls:
            raise ArgumentError(f"manifest {source} lists no URLs", fix="Re-run `map` with wider filters.")
    else:
        root = args.url
        urls, coverage = _crawl.discover(
            root,
            depth=args.depth,
            max_urls=args.max_urls,
            include=args.include,
            exclude=args.exclude,
            use_sitemap=not args.no_sitemap,
            **_providers(args),
        )

    urls = urls[: args.max_pages]
    if args.out:
        out_dir = Path(args.out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = _default_out(runs_root, root)

    envelope = _page.fetch_urls(
        urls,
        out_dir=out_dir,
        via=args.via,
        frontmatter=not args.no_frontmatter,
        concurrency=args.concurrency,
        numbered=True,
    )
    items = envelope["items"]
    manifest = _crawl.build_manifest(root, items)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "ok": True,
            "command": "crawl",
            "root": root,
            "out_dir": str(out_dir),
            "manifest": str(manifest_path),
            "requested": len(urls),
            "saved": sum(1 for i in items if i["status"] == "ok"),
            "items": [{k: v for k, v in i.items() if k != "content"} for i in items],
            **({"coverage": coverage} if coverage is not None else {}),
        },
        ensure_ascii=False,
    ))
    return _page.exit_code_for(items)


def _refuse_used_folder(out: Path) -> None:
    """A crawl's numbered names repeat from one crawl to the next, so a folder that already
    holds files -- an earlier crawl's, or anyone's -- would have them replaced in place."""
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ArgumentError(
            f"--out {out} already holds files",
            fix="Pass an empty or new folder with --out; a crawl never writes over earlier pages.",
        )


def _default_out(runs_root: Path, root: str) -> Path:
    """A new folder per crawl under crawls/<host>/, reserved before anything is written."""
    host = urlparse(root).netloc or "site"
    base = Path(runs_root) / "crawls" / host
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d-%H%M%S")
    for n in range(1, 100):
        out = base / (stamp if n == 1 else f"{stamp}-{n}")
        try:
            out.mkdir()
            return out
        except FileExistsError:
            continue
    raise ArgumentError(f"could not reserve a crawl folder under {base}", fix="Pass one with --out.")
