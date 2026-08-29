"""`map` and `crawl`.

`map` is the cheap half: it discovers URLs and writes a manifest without fetching any
content, so a caller can look at what a site has before committing to downloading it.
`crawl --from` consumes that same manifest, which is what keeps a look-then-fetch from
walking the site twice.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import _crawl
import _errors
import _page
import _registry
import _repl
from _errors import ArgumentError


def dispatch(args, runs_root: Path) -> int:
    return _map(args, runs_root) if args.command == "map" else _crawl_cmd(args, runs_root)


def _providers(args):
    return {
        "sitemap_provider": None if getattr(args, "no_sitemap", False) else _repl.sitemap,
        "links_provider": _repl.links,
    }


def _map(args, runs_root: Path) -> int:
    urls = _crawl.discover(
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
    print(json.dumps({"ok": True, "command": "map", **manifest}, ensure_ascii=False))
    return 0 if urls else _errors.EXIT_EMPTY


def _crawl_cmd(args, runs_root: Path) -> int:
    if args.from_manifest:
        source = Path(args.from_manifest).expanduser()
        try:
            manifest = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ArgumentError(f"could not read manifest {source}: {e}", fix="Produce one with `map --out`.") from e
        root = manifest.get("root") or ""
        urls = _crawl.urls_from_manifest(manifest)
        if not urls:
            raise ArgumentError(f"manifest {source} lists no URLs", fix="Re-run `map` with wider filters.")
    else:
        root = args.url
        urls = _crawl.discover(
            root,
            depth=args.depth,
            max_urls=args.max_urls,
            include=args.include,
            exclude=args.exclude,
            use_sitemap=not args.no_sitemap,
            **_providers(args),
        )

    urls = urls[: args.max_pages]
    out_dir = Path(args.out).expanduser() if args.out else _default_out(runs_root, root)
    out_dir.mkdir(parents=True, exist_ok=True)

    envelope = _page.fetch_urls(
        urls,
        out_dir=out_dir,
        via=args.via,
        frontmatter=not args.no_frontmatter,
        concurrency=args.concurrency,
    )
    items = envelope["items"]
    _number_files(items, out_dir)
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
        },
        ensure_ascii=False,
    ))
    return _page.exit_code_for(items)


def _default_out(runs_root: Path, root: str) -> Path:
    host = urlparse(root).netloc or "site"
    return Path(runs_root) / "crawls" / host


def _number_files(items: list[dict], out_dir: Path) -> None:
    """Prefix saved files with their crawl order.

    A directory listing then reads in the order the site presents its pages, which is
    usually the order they are meant to be read in.
    """
    for i, item in enumerate(items):
        if not item.get("path"):
            continue
        current = Path(item["path"])
        if current.parent != out_dir:
            continue
        target = out_dir / f"{i:03d}-{current.name}"
        try:
            current.rename(target)
            item["path"] = str(target)
        except OSError:
            pass
