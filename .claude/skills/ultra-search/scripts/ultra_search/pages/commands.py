"""`fetch`, `map` and `crawl`.

`fetch` saves each page to a file and reports where, never its text unless asked: a fetch of
ten pages that returned them would put ten pages into the caller's context as a side
effect of being told where they are.

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

from ultra_search import contract
from ultra_search.contract import ArgumentError
from ultra_search.pages import acquire, browser, discover
from ultra_search.runs import registry


def dispatch(args) -> int:
    runs_root = registry.resolve_runs_dir(args.runs_dir)
    if args.command == "fetch":
        return _fetch_cmd(args, runs_root)
    return _map(args, runs_root) if args.command == "map" else _crawl_cmd(args, runs_root)


def _fetch_cmd(args, runs_root: Path) -> int:
    out_file, out_dir = _destinations(args.url, args.out, runs_root)
    envelope = acquire.fetch_urls(
        args.url,
        out_dir=out_dir,
        out_file=out_file,
        via=args.via,
        fmt=args.format,
        frontmatter=not args.no_frontmatter,
        print_content=args.print_content,
        max_chars=args.max_chars,
        concurrency=args.concurrency,
    )
    print(json.dumps(envelope, ensure_ascii=False))
    return exit_code_for(envelope["items"])


def _destinations(urls: list[str], out: str | None, runs_root: Path) -> tuple[Path | None, Path]:
    """Split --out into a file destination or a directory one.

    A path is a file only when it looks like one -- an existing file, or a name with an
    extension. Anything else is a directory, because `--out ./notes` for one URL means a
    folder to everyone who types it, and silently producing an extensionless file named
    `notes` is the kind of surprise nobody checks for.
    """
    if not out:
        return None, registry.pages_dir(runs_root)
    p = Path(out).expanduser()
    looks_like_file = p.is_file() or (bool(p.suffix) and not p.is_dir() and not out.endswith("/"))
    if looks_like_file:
        if len(urls) > 1:
            raise ArgumentError(
                f"--out {out!r} names a file but {len(urls)} URLs were given",
                fix="Pass a directory for several URLs, or fetch them one at a time.",
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, p.parent
    p.mkdir(parents=True, exist_ok=True)
    return None, p


def exit_code_for(items: list[dict]) -> int:
    """0 when anything was saved. The status still says what each page turned out to be:
    `--format html` writes a client-rendered document that has no article in it."""
    if not items:
        return contract.EXIT_EMPTY
    if any(i["status"] == "ok" or i.get("path") for i in items):
        return 0
    return contract.EXIT_RUN_FAILED


def _discovery(args) -> dict:
    """The discovery settings the caller gave; discover() supplies the rest."""
    given = {"depth": args.depth, "max_urls": args.max_urls}
    return {k: v for k, v in given.items() if v is not None}


def _providers(args):
    return {
        "sitemap_provider": None if getattr(args, "no_sitemap", False) else browser.sitemap,
        "links_provider": browser.links,
    }


def _map(args, runs_root: Path) -> int:
    urls, coverage = discover.discover(
        args.url,
        **_discovery(args),
        include=args.include,
        exclude=args.exclude,
        use_sitemap=not args.no_sitemap,
        **_providers(args),
    )
    manifest = discover.build_manifest(args.url, [], urls=urls)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(out)
    print(json.dumps({"ok": True, "command": "map", **manifest, "coverage": coverage}, ensure_ascii=False))
    # Nothing read -- no sitemap and not one page's links -- is no map at all, even when the
    # root itself is listed.
    saw_site = coverage["sitemap"] or coverage["pages_read"] > 0
    return 0 if urls and saw_site else contract.EXIT_EMPTY


def _crawl_cmd(args, runs_root: Path) -> int:
    if args.out:
        _refuse_used_folder(Path(args.out).expanduser())
    if args.from_manifest:
        given = [flag for flag, value in (("--max-urls", args.max_urls), ("--depth", args.depth),
                                          ("--include", args.include), ("--exclude", args.exclude),
                                          ("--no-sitemap", args.no_sitemap)) if value not in (None, False)]
        if given:
            raise ArgumentError(
                f"{', '.join(given)} {'does' if len(given) == 1 else 'do'} not apply to --from: the manifest is crawled as it is",
                fix="Drop the flag, or run `map` again with it and crawl that manifest.",
            )
        source = Path(args.from_manifest).expanduser()
        try:
            manifest = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ArgumentError(f"could not read manifest {source}: {e}", fix="Produce one with `map --out`.") from e
        urls = discover.urls_from_manifest(manifest)
        if urls is None:
            raise ArgumentError(f"{source} is not a manifest written by `map` or `crawl`",
                                fix="Produce one with `map --out`.")
        root = manifest.get("root") or ""
        coverage = None
        if not urls:
            raise ArgumentError(f"manifest {source} lists no URLs", fix="Re-run `map` with wider filters.")
    else:
        root = args.url
        urls, coverage = discover.discover(
            root,
            **_discovery(args),
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

    envelope = acquire.fetch_urls(
        urls,
        out_dir=out_dir,
        via=args.via,
        frontmatter=not args.no_frontmatter,
        concurrency=args.concurrency,
        numbered=True,
    )
    items = envelope["items"]
    manifest = discover.build_manifest(root, items)
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
    return exit_code_for(items)


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
