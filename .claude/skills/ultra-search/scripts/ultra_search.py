#!/usr/bin/env python3
"""ultra-search — search, read, map and save the web through the user's logged-in Aside browser.

Every command prints one JSON line on stdout (``log`` streams events first, then a
terminal line and a ``# cursor=<n>`` comment). Exit codes are the contract:

    0  success
    2  bad arguments
    3  aside unavailable (binary missing, daemon unreachable)
    4  run failed or abandoned
    5  completed but empty -- an honest zero, not an error
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

EXIT_OK = 0
EXIT_ARGS = 2
EXIT_ASIDE = 3
EXIT_RUN_FAILED = 4
EXIT_EMPTY = 5

EFFORT_CHOICES = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "ultrabrowse")
SPEED_CHOICES = ("default", "fast")
LEVEL_CHOICES = ("compact", "normal", "full", "raw")
FORMAT_CHOICES = ("md", "html")
VIA_CHOICES = ("auto", "fetch", "tab")


def _add_runs_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--runs-dir",
        metavar="DIR",
        help="Registry root holding run directories and saved pages "
        "(default: .ultra-search/ under the current project).",
    )


def _add_target(p: argparse.ArgumentParser, *, all_flag: bool = False) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--run", metavar="ID", help="A single run id, as returned by `search`.")
    g.add_argument("--group", metavar="NAME", help="A group of runs started together by one `search`.")
    if all_flag:
        g.add_argument("--all", action="store_true", help="Every run still being watched.")
    p.add_argument(
        "--last",
        action="store_true",
        help="Use the most recently started run or group. Default when neither --run nor --group is given.",
    )


def _add_exec_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--label", help="Short name for the run directory, so a later `status` is readable.")
    p.add_argument("--effort", choices=EFFORT_CHOICES, help="Aside reasoning effort. Default: the account's setting.")
    p.add_argument("--model", help="Aside model id, e.g. openai-codex/gpt-5.6-sol. Default: the account's setting.")
    p.add_argument("--speed", choices=SPEED_CHOICES, help="Aside speed setting. Default: the account's setting.")
    p.add_argument(
        "--timeout",
        type=float,
        metavar="SEC",
        help="Stop WATCHING at this point and mark the run `abandoned`. The daemon-side run keeps going "
        "and keeps spending credits -- this does not cancel anything. Default: no deadline.",
    )
    _add_runs_dir(p)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ultra_search.py",
        description="Search, read, map and save the web through the user's logged-in Aside browser.",
        epilog="Exit codes: 0 ok | 2 bad args | 3 aside unavailable | 4 run failed/abandoned | 5 completed but empty.",
    )
    p.add_argument("--version", action="version", version="ultra-search 1.0")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # --- search -------------------------------------------------------------
    s = sub.add_parser(
        "search",
        help="Run an autonomous web investigation (Aside's in-browser agent).",
        description="Hand a research objective to Aside's browsing agent. Several PROMPTs run in parallel "
        "as one group. Synchronous by default: if the work finishes within --wait you get the answer, "
        "sources and usage inline; if it does not, the run is left alive and you get a handle plus a "
        "`next` object naming the exact command that will wake you when it finishes.",
    )
    s.add_argument("prompt", nargs="+", metavar="PROMPT", help="Research objective. Repeat for parallel runs.")
    s.add_argument(
        "--wait",
        type=float,
        default=100.0,
        metavar="SEC",
        help="Seconds to stay attached before handing back a handle. Never kills the run. "
        "Default 100, which sits under the Bash tool's 120s default so the handle is never lost.",
    )
    s.add_argument(
        "--background",
        action="store_true",
        help="Return the handle immediately instead of waiting.",
    )
    _add_exec_opts(s)

    # --- resume -------------------------------------------------------------
    r = sub.add_parser(
        "resume",
        help="Ask a follow-up in a finished run's session.",
        description="Continue an existing Aside session with a follow-up question, keeping everything it "
        "already worked out. Takes a run id from `search` or any session id from `sessions`, so a "
        "conversation started in the Aside app can be picked up here. Creates a new run id recording its "
        "lineage. Refused while the session is still working: attaching to a live one waits for the current "
        "turn and cannot steer it.",
    )
    r.add_argument(
        "target",
        metavar="RUN_OR_SESSION",
        help="A run id from `search`, or an Aside session id from `sessions` -- including a "
        "session started in the Aside app or by a bare `aside exec`, which this did not create.",
    )
    r.add_argument("prompt", metavar="PROMPT", help="The follow-up.")
    r.add_argument("--wait", type=float, default=100.0, metavar="SEC", help="As for `search`.")
    r.add_argument("--background", action="store_true", help="As for `search`.")
    _add_exec_opts(r)

    # --- status -------------------------------------------------------------
    st = sub.add_parser(
        "status",
        help="Snapshot of a run: state, children, last activity.",
        description="One snapshot and exit -- there is no --follow here; `log --follow` is the only watcher. "
        "Reports last_activity_at and idle_seconds across the run's own output and every child session, so a "
        "parent that has gone quiet while its children work is visibly not stalled.",
    )
    _add_target(st)
    st.add_argument(
        "--stall-after",
        type=float,
        default=300.0,
        metavar="SEC",
        help="Idle seconds after which possibly_stalled is flagged. This only labels -- nothing is killed "
        "or transitioned. Default 300.",
    )
    _add_runs_dir(st)

    # --- log ----------------------------------------------------------------
    lg = sub.add_parser(
        "log",
        help="Stream a run's events; the only watcher.",
        description="Print a run's events from a byte cursor. With --follow this exits on the run's terminal "
        "line, which is what makes it usable as a background Bash call that wakes you when the run ends.",
    )
    _add_target(lg)
    lg.add_argument(
        "--since",
        default="0",
        metavar="CURSOR",
        help="Resume from a previous call's `# cursor=` value. A single run's cursor is a byte offset; "
        "a group's is the JSON object that call printed, since members advance independently.",
    )
    lg.add_argument(
        "--level",
        choices=LEVEL_CHOICES,
        default="compact",
        help="How much of each event to print. compact withholds tool output and reports its size instead; "
        "raw prints the stored records unchanged. Default compact.",
    )
    lg.add_argument("--follow", action="store_true", help="Keep printing until the run reaches a terminal state.")
    lg.add_argument(
        "--follow-timeout",
        type=float,
        default=570.0,
        metavar="SEC",
        help="Give up following after this long and print `run.still-running`. Default 570, under the Bash "
        "tool's 600s ceiling.",
    )
    lg.add_argument(
        "--heartbeat",
        type=float,
        metavar="SEC",
        help="With --follow, emit a liveness line every SEC including the number of live children, so a long "
        "silence is distinguishable from a dead follower.",
    )
    _add_runs_dir(lg)

    # --- result -------------------------------------------------------------
    rs = sub.add_parser(
        "result",
        help="A finished run's answer and sources.",
        description="The answer with <citation> tags resolved to URL footnotes, plus every source with "
        "`opened` telling you which were actually read rather than merely listed by a search.",
    )
    _add_target(rs)
    rs.add_argument("--sources-only", action="store_true", help="Omit the answer text.")
    _add_runs_dir(rs)

    # --- show ---------------------------------------------------------------
    sh = sub.add_parser(
        "show",
        help="Full text of one source or one tool result.",
        description="The third layer under `result`: the page text Aside already fetched, returned without "
        "fetching anything again.",
    )
    sh.add_argument("--run", metavar="ID", help="Run id. Defaults to the most recent run.")
    g = sh.add_mutually_exclusive_group(required=True)
    g.add_argument("--source", metavar="N|ID", help="Source index from `result`, or its source id.")
    g.add_argument("--item", type=int, metavar="N", help="Tool-call index from `log`.")
    _add_runs_dir(sh)

    # --- stop ---------------------------------------------------------------
    sp = sub.add_parser(
        "stop",
        help="Stop watching a run and mark it abandoned.",
        description="Detaches the supervisor and marks the run `abandoned`. THE DAEMON-SIDE RUN CONTINUES "
        "and keeps spending credits -- the CLI has no way to cancel one. Cancel in the Aside app UI.",
    )
    _add_target(sp, all_flag=True)
    _add_runs_dir(sp)

    # --- fetch --------------------------------------------------------------
    f = sub.add_parser(
        "fetch",
        help="Read one or more URLs into clean markdown files.",
        description="Fetches with the user's cookies, so logged-in and bot-blocked pages work. Documents "
        "(PDF, docx, pptx, xlsx, epub...) are converted too. Full text always goes to a file; use --print "
        "to also get it inline.",
    )
    f.add_argument("url", nargs="+", metavar="URL", help="Page or document URL.")
    f.add_argument(
        "--out",
        metavar="PATH",
        help="Output file (only legal with exactly one URL) or directory. Default: .ultra-search/pages/.",
    )
    f.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="md",
        help="md saves extracted markdown; html saves the page's original HTML exactly as "
        "fetched. html is refused for a response that was not HTML (a PDF, a markdown file) "
        "rather than silently writing markdown into a .html file. Default md.",
    )
    f.add_argument(
        "--via",
        choices=VIA_CHOICES,
        default="auto",
        help="auto fetches first and promotes to a real browser tab when the response turns out to be a "
        "JavaScript shell; fetch and tab force one path. Default auto.",
    )
    f.add_argument("--print", dest="print_content", action="store_true", help="Include the content inline in the JSON.")
    f.add_argument("--max-chars", type=int, default=20000, metavar="N", help="Inline content cap for --print. Default 20000.")
    f.add_argument("--no-frontmatter", action="store_true", help="Omit the YAML frontmatter from saved markdown.")
    f.add_argument("--concurrency", type=int, default=8, metavar="N", help="URLs fetched per browser round trip. Default 8.")
    _add_runs_dir(f)

    # --- map ----------------------------------------------------------------
    m = sub.add_parser(
        "map",
        help="List a site's URLs without fetching their content.",
        description="Discovers URLs from sitemaps and same-origin links. Cheap enough to run before deciding "
        "what is worth crawling; the manifest it writes is what `crawl --from` consumes so the site is only "
        "walked once.",
    )
    m.add_argument("url", metavar="URL", help="Site or section root.")
    m.add_argument("--max-urls", type=int, default=200, metavar="N", help="Stop after this many URLs. Default 200.")
    m.add_argument("--depth", type=int, default=2, metavar="N", help="Link-following depth from the root. Default 2.")
    m.add_argument("--include", action="append", metavar="GLOB", help="Keep only URLs matching this glob. Repeatable.")
    m.add_argument("--exclude", action="append", metavar="GLOB", help="Drop URLs matching this glob. Repeatable.")
    m.add_argument("--no-sitemap", action="store_true", help="Skip sitemap discovery and follow links only.")
    m.add_argument("--out", metavar="FILE", help="Write the manifest here instead of stdout.")
    _add_runs_dir(m)

    # --- crawl --------------------------------------------------------------
    c = sub.add_parser(
        "crawl",
        help="Map a site and save every page as markdown.",
        description="map + fetch. Writes NNN-slug.md files and a manifest.json recording url, file, title, "
        "status, depth and via for each page.",
    )
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("url", nargs="?", metavar="URL", help="Site root to crawl.")
    src.add_argument("--from", dest="from_manifest", metavar="FILE", help="A manifest.json from `map`, crawled as-is.")
    c.add_argument("--max-pages", type=int, default=25, metavar="N", help="Stop after this many pages. Default 25.")
    c.add_argument("--max-urls", type=int, default=200, metavar="N", help="Discovery cap before --max-pages applies. Default 200.")
    c.add_argument("--depth", type=int, default=2, metavar="N", help="Link-following depth. Default 2.")
    c.add_argument("--include", action="append", metavar="GLOB", help="Keep only URLs matching this glob. Repeatable.")
    c.add_argument("--exclude", action="append", metavar="GLOB", help="Drop URLs matching this glob. Repeatable.")
    c.add_argument("--no-sitemap", action="store_true", help="Skip sitemap discovery and follow links only.")
    c.add_argument("--concurrency", type=int, default=8, metavar="N", help="URLs fetched per browser round trip. Default 8.")
    c.add_argument("--via", choices=VIA_CHOICES, default="auto", help="As for `fetch`. Default auto.")
    c.add_argument("--no-frontmatter", action="store_true", help="Omit the YAML frontmatter from saved markdown.")
    c.add_argument("--out", metavar="DIR", help="Output directory. Default: .ultra-search/crawls/<host>/.")
    _add_runs_dir(c)

    # --- sessions -----------------------------------------------------------
    se = sub.add_parser(
        "sessions",
        help="List Aside sessions that exist right now, so one can be resumed.",
        description="Every conversation Aside still has on disk, newest first -- ones this tool started and "
        "ones started in the Aside app or by a bare `aside exec` alike. The opening prompt is shown because "
        "a session id is not something anyone remembers. Feed a session_id to `resume`. Aside deletes these "
        "within about a day, so a session listed here may not be listed tomorrow.",
    )
    se.add_argument("--limit", type=int, default=20, metavar="N", help="How many to list. Default 20.")
    se.add_argument(
        "--mine",
        action="store_true",
        help="Only sessions this tool started, identified by the marker it plants in the prompt.",
    )
    se.add_argument("--search", metavar="TEXT", help="Only sessions whose opening prompt contains TEXT.")
    _add_runs_dir(se)

    # --- repl-api / doctor / setup -----------------------------------------
    sub.add_parser(
        "repl-api",
        help="Print the browser REPL's own API documentation, live.",
        description="Asks the running daemon what its repl tool accepts. Use it instead of guessing at "
        "globals -- it is generated by the version actually installed.",
    )
    d = sub.add_parser(
        "doctor",
        help="Check the aside binary, daemon, account and conversion toolchain.",
        description="Reports everything that has to be working before a command can succeed, and exits 3 "
        "when something it can see would stop one.",
    )
    _add_runs_dir(d)
    sub.add_parser("setup", help="Install the Node packages used for markdown and document conversion.")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from _errors import UltraSearchError

    if args.command in ("search", "resume"):
        import _run_cmds as impl
    elif args.command in ("status", "log", "result", "show", "stop", "sessions"):
        import _watch_cmds as impl
    elif args.command in ("fetch", "map", "crawl"):
        import _page as impl
    else:
        import _doctor as impl

    try:
        return impl.dispatch(args)
    except UltraSearchError as e:
        print(json.dumps(e.payload(), ensure_ascii=False))
        return e.exit_code
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
