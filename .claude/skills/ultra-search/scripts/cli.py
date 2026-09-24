#!/usr/bin/env python3
"""ultra-search — search, read, map and save the web through the user's logged-in Aside browser.

Every command prints one JSON response on stdout; ``log`` prints events and its cursor before the response. Exit codes describe the command, not the quality or completeness of an investigation:

    0  success
    2  bad arguments
    3  aside unavailable (binary missing, daemon unreachable)
    4  run failed or abandoned
    5  no result data
"""
from __future__ import annotations

import argparse
from functools import partial
import json
import math
import pathlib
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ultra_search import __version__  # noqa: E402 - after the path it is found on
from ultra_search.contract import EXIT_ARGS, EXIT_OK  # noqa: E402
from ultra_search.runs.render import LEVELS  # noqa: E402

EFFORT_CHOICES = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "ultrabrowse")
SPEED_CHOICES = ("default", "fast")
FORMAT_CHOICES = ("md", "html")
VIA_CHOICES = ("auto", "fetch", "tab")
NEXT_HELP = (
    "next describes one action: command is the shell command, bash_timeout_ms is the Bash tool timeout it needs, "
    "and run_in_background says whether to run it in the background. Background is for when something will "
    "receive its completion notification; with nothing to wake -- a single-turn context -- run the same command "
    "in the foreground with that bash_timeout_ms. Execute it as returned and use that call's latest next, not a "
    "saved earlier one. A log response selects another watch with its cursor while work remains, or result "
    "collection when every target is terminal. Watch expiry does not stop the investigation."
)


class JsonArgumentParser(argparse.ArgumentParser):
    """A parser whose refusals are JSON on stdout like every other answer, not usage on stderr."""

    def error(self, message: str) -> None:  # type: ignore[override]
        print(json.dumps({"ok": False, "error": "bad_arguments", "message": message, "fix": f"{self.prog} --help"},
                         ensure_ascii=False))
        raise SystemExit(EXIT_ARGS)


def _count(minimum: int):
    """A whole number of at least `minimum`."""

    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"{value} is below the minimum of {minimum}")
        return value

    return parse


def _seconds(*, positive: bool = False):
    """A finite number of seconds: zero or more, or more than zero."""

    def parse(text: str) -> float:
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not a number of seconds") from None
        if not math.isfinite(value) or value < 0 or (positive and value == 0):
            raise argparse.ArgumentTypeError(f"{text} is not a {'positive' if positive else 'non-negative'} finite number of seconds")
        return value

    return parse


def _web_url(text: str) -> str:
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise argparse.ArgumentTypeError(f"{text!r} is not an http(s) URL")
    return text


def _add_runs_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--runs-dir",
        metavar="DIR",
        help="Registry root holding run directories and saved pages "
        "(default: .ultra-search/ under the current working directory).",
    )


def _add_target(p: argparse.ArgumentParser, *, all_flag: bool = False) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--run", metavar="ID", help="A single run id, as returned by `search`.")
    g.add_argument("--group", metavar="NAME", help="A group of runs started together by one `search`.")
    if all_flag:
        g.add_argument("--all", action="store_true", help="Every run still being watched.")
    # No --last flag: with neither --run nor --group this already targets the most recent
    # run's group, and a flag that only restates the default is one more thing to be wrong
    # about.


def _add_wait_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--wait",
        type=_seconds(),
        default=100.0,
        metavar="SEC",
        help="Seconds to stay attached before handing back a handle. Never kills the run. "
        "Default 100, which sits under the Bash tool's 120s default so the handle is never lost.",
    )
    p.add_argument("--background", action="store_true", help="Return the handle immediately instead of waiting.")


def _add_fetch_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--via",
        choices=VIA_CHOICES,
        default="auto",
        help="auto fetches first and promotes to a real browser tab when the response is a JavaScript shell "
        "or a bot challenge -- the tab runs the page's JavaScript or clears the check; fetch and tab force one "
        "path. Default auto.",
    )
    p.add_argument("--concurrency", type=_count(1), default=8, metavar="N", help="URLs fetched per browser round trip. Default 8.")
    p.add_argument("--no-frontmatter", action="store_true", help="Omit the YAML frontmatter from saved markdown.")


def _add_discovery_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--max-urls", type=_count(1), metavar="N", help="Stop discovering after this many URLs. Default 200.")
    p.add_argument("--depth", type=_count(0), metavar="N", help="Rounds of link-following from the root. Default 2.")
    p.add_argument("--include", action="append", metavar="GLOB", help="Keep only URLs matching this glob. Repeatable.")
    p.add_argument("--exclude", action="append", metavar="GLOB", help="Drop URLs matching this glob. Repeatable.")
    p.add_argument("--no-sitemap", action="store_true", help="Skip sitemap discovery and follow links only.")


def _add_exec_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--label", help="Short name for the run directory, so a later `status` is readable.")
    p.add_argument("--effort", choices=EFFORT_CHOICES, help="Aside reasoning effort. Default: the account's setting.")
    p.add_argument("--model", help="Aside model id, e.g. openai-codex/gpt-5.6-sol. Default: the account's setting.")
    p.add_argument("--speed", choices=SPEED_CHOICES, help="Aside speed setting. Default: the account's setting.")
    p.add_argument(
        "--timeout",
        type=_seconds(positive=True),
        metavar="SEC",
        help="Stop WATCHING at this point and mark the run `abandoned`. The daemon-side run keeps going "
        "and keeps spending credits -- this does not cancel anything. Default: no deadline.",
    )
    _add_runs_dir(p)


def build_parser() -> argparse.ArgumentParser:
    p = JsonArgumentParser(
        prog="cli.py",
        description="Search, read, map and save the web through the user's logged-in Aside browser.",
        epilog="Exit codes: 0 command handled (inspect run/item states) | 2 bad args | 3 aside unavailable | 4 run failed/abandoned | 5 no result data.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"ultra-search {__version__}")
    sub = p.add_subparsers(
        dest="command", metavar="COMMAND", required=True,
        parser_class=partial(JsonArgumentParser, formatter_class=argparse.RawTextHelpFormatter),
    )

    # --- search -------------------------------------------------------------
    s = sub.add_parser(
        "search",
        help="Run an autonomous web investigation (Aside's in-browser agent).",
        description="Hand a research objective to Aside's browsing agent. Several PROMPTs run in parallel "
        "as one group. Synchronous by default: if the work finishes within --wait you get the answer, "
        "sources and usage inline; if it does not, the run is left alive and you get a handle plus a "
        "`next` action for watching it. Finished entries include their state; a partial snapshot is not a complete investigation. "
        "Every prompt is sent with one more line: \"Read-only research: do not post, purchase, sign up, or change account settings.\"",
        epilog=NEXT_HELP,
    )
    s.add_argument("prompt", nargs="+", metavar="PROMPT", help="Research objective. Repeat for parallel runs.")
    _add_wait_opts(s)
    _add_exec_opts(s)

    # --- resume -------------------------------------------------------------
    r = sub.add_parser(
        "resume",
        help="Ask a follow-up in a finished run's session.",
        description="Continue an existing Aside session with a follow-up question, keeping everything it "
        "already worked out. Takes a run id from `search` or any session id from `sessions`, so a "
        "conversation started in the Aside app can be picked up here. Creates a new run id recording its "
        "lineage. Refused while the session is still working: attaching to a live one waits for the current "
        "turn and cannot steer it. The returned run's log and result describe only this new turn. "
        "The follow-up is sent with one more line, as in `search`: \"Read-only research: do not post, purchase, "
        "sign up, or change account settings.\"",
        epilog=NEXT_HELP,
    )
    r.add_argument(
        "target",
        metavar="RUN_OR_SESSION",
        help="A run id from `search`, or an Aside session id from `sessions` -- including a "
        "session started in the Aside app or by a bare `aside exec`, which this did not create.",
    )
    r.add_argument("prompt", metavar="PROMPT", help="The follow-up.")
    _add_wait_opts(r)
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
        type=_seconds(),
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
        description="Print this run's events, then a cursor and a final JSON response with runs (per-run state), "
        "cursor and next. With --follow, wait until all targets are terminal or --follow-timeout expires. "
        "Exit 0 means the log was read, not that research finished or succeeded. A resumed run excludes earlier turns and their children.",
        epilog=NEXT_HELP,
    )
    _add_target(lg)
    lg.add_argument(
        "--since",
        default="0",
        metavar="CURSOR",
        help="Resume from a previous call's `# cursor=` value. A run with no children prints a byte offset; "
        "one with children, or a group, prints a JSON object, since its streams advance independently.",
    )
    lg.add_argument(
        "--level",
        choices=LEVELS,
        default="progress",
        help="What each event becomes. progress: one line per turn -- what the run reached for (tool, count, "
        "the host or objective) and what it said; a result appears only when it errored, an answer as its "
        "first line. steps: every call with the first 200 characters of its arguments and every result's "
        "size, numbered #N for `show --item N`, for retracing why a source was chosen. full: arguments to 4000 characters and the first 2000 "
        "characters of each result. raw: the stored records unchanged. Default progress.",
    )
    lg.add_argument("--follow", action="store_true", help="Keep printing until all targets are terminal or the watching deadline expires.")
    lg.add_argument(
        "--follow-timeout",
        type=_seconds(),
        default=570.0,
        metavar="SEC",
        help="Give up following after this long and print `run.still-running`. Default 570, under the Bash "
        "tool's 600s ceiling.",
    )
    lg.add_argument(
        "--heartbeat",
        type=_seconds(positive=True),
        metavar="SEC",
        help="With --follow, emit a liveness line every SEC including the number of live children, so a long "
        "silence is distinguishable from a dead follower.",
    )
    _add_runs_dir(lg)

    # --- result -------------------------------------------------------------
    rs = sub.add_parser(
        "result",
        help="A finished run's answer and sources.",
        description="Each run's answer with <citation> tags resolved to URL footnotes, and every source the run and its "
        "children touched -- always as a runs list, one entry per run. empty means no answer and no sources, not that a claim was disproved; a textual "
        "negative finding is still an answer.\n"
        "`opened` means a page-opening tool (webfetch, repl, read_file) returned that URL: an inference that the "
        "page was read, not a check of what it said. A source only listed by a search is not opened.\n"
        "Each run ends in one state:\n"
        "completed: the process exited, its session was read, and every child finished.\n"
        "completed_with_orphans: as completed, but orphan_children were still running -- a saved snapshot; their "
        "late results are not collected.\n"
        "completed_unstructured: the session transcript, or this run's turn in it, never appeared; answer and "
        "sources come from stdout only.\n"
        "failed: aside exited non-zero.\n"
        "abandoned: watching stopped -- the daemon's work and its credit use did not.",
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
    g.add_argument("--source", metavar="N|ID", help="Source index from `result`, counting from 0, or any of its source ids.")
    g.add_argument(
        "--item",
        type=_count(0),
        metavar="N",
        help="Index into this run's tool RESULTS, in order, counting from 0 -- not into all "
        "events. `log --level steps` prints each one's N as #N.",
    )
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
        "to also get it inline. Exit 0 means at least one file was written.\n"
        "Each item's status says what the page turned out to be; only an ok item's file is the page's text:\n"
        "ok: the text was extracted and saved.\n"
        "shell: almost no text -- the page renders in the browser, or the body was empty.\n"
        "shell_escalated: still almost no text after opening it in a real tab.\n"
        "challenge: a bot check answered instead of the page.\n"
        "blocked: an HTTP error, or a challenge a real tab could not clear.\n"
        "needs_ocr: a document with no text layer; nothing was sent anywhere for OCR.\n"
        "unsupported: a response or document that could not be converted.\n"
        "error: the fetch itself failed (timeout, network).\n"
        "Markdown conversion can lose tables, figures and layout: --format html saves the document itself, and a "
        "converted document's original file is kept at original_path.",
    )
    f.add_argument("url", nargs="+", type=_web_url, metavar="URL", help="Page or document URL.")
    f.add_argument(
        "--out",
        metavar="PATH",
        help="Output file (only legal with exactly one URL) or directory. Default: .ultra-search/pages/.",
    )
    f.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="md",
        help="md saves extracted markdown; html saves the document itself -- the response body "
        "for a plain fetch, or the rendered DOM when the page was opened in a tab. html is "
        "refused for a response that was not HTML (a PDF, a markdown file) rather than "
        "silently writing markdown into a .html file. Default md.",
    )
    _add_fetch_opts(f)
    f.add_argument("--print", dest="print_content", action="store_true", help="Include the content inline in the JSON.")
    f.add_argument("--max-chars", type=_count(1), default=20000, metavar="N", help="Inline content cap for --print. Default 20000.")
    _add_runs_dir(f)

    # --- map ----------------------------------------------------------------
    m = sub.add_parser(
        "map",
        help="List a site's URLs without extracting or saving pages.",
        description="Discovers URLs from sitemaps and same-origin links, without extracting or saving pages. Cheap enough to run before deciding "
        "what is worth crawling; the manifest it writes is what `crawl --from` consumes so the site is only "
        "walked once.\n"
        "The reply is a summary whatever the site's size: count, coverage (what could not be read, and whether a "
        "budget or --max-urls cut discovery short), the first 10 URLs, and manifest_path, the file holding every URL.",
    )
    m.add_argument("url", type=_web_url, metavar="URL", help="Site or section root.")
    _add_discovery_opts(m)
    m.add_argument("--out", metavar="FILE", help="Write the manifest here instead of .ultra-search/maps/<host>-<timestamp>.json.")
    m.add_argument("--list-all", action="store_true", help="Also print every URL in the reply, not only the first 10.")
    _add_runs_dir(m)

    # --- crawl --------------------------------------------------------------
    c = sub.add_parser(
        "crawl",
        help="Map a site and save every page as markdown.",
        description="map + fetch. Writes NNN-slug.md files and a manifest.json recording url, file, title, "
        "status and via for each page. The reply counts pages by status and lists only the ones that are not ok.\n"
        "With --from, only --max-pages, --via, --concurrency, --no-frontmatter and --out apply; the manifest is "
        "crawled as it is, so discovery flags are refused.",
    )
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("url", nargs="?", type=_web_url, metavar="URL", help="Site root to crawl.")
    src.add_argument("--from", dest="from_manifest", metavar="FILE", help="A manifest.json from `map`, crawled as-is.")
    c.add_argument("--max-pages", type=_count(1), default=25, metavar="N", help="Stop after this many pages. Default 25.")
    _add_discovery_opts(c)
    _add_fetch_opts(c)
    c.add_argument("--out", metavar="DIR", help="An empty or new output directory. Default: a new "
                   ".ultra-search/crawls/<host>/<timestamp>/.")
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
    se.add_argument("--limit", type=_count(1), default=20, metavar="N", help="How many to list. Default 20.")
    se.add_argument(
        "--mine",
        action="store_true",
        help="Only sessions this tool started, identified by the marker it plants in the prompt.",
    )
    se.add_argument("--search", metavar="TEXT", help="Only sessions whose opening prompt contains TEXT.")
    _add_runs_dir(se)

    # --- repl-api / doctor / setup -----------------------------------------
    ra = sub.add_parser(
        "repl-api",
        help="Print the browser REPL's own API documentation, live.",
        description="Asks the running daemon what its repl tool accepts, and says how to call it. Use it instead of "
        "guessing at globals -- it is generated by the version actually installed.",
    )
    ra.add_argument("--all", action="store_true", help="Every tool the daemon lists, not only repl.")
    d = sub.add_parser(
        "doctor",
        help="Check the aside binary, daemon, account and conversion toolchain.",
        description="Reports everything that has to be working before a command can succeed, and exits 3 "
        "when something it can see would stop one.",
    )
    _add_runs_dir(d)
    sub.add_parser(
        "setup",
        help="Install the Node packages used for markdown and document conversion.",
        description="Runs `npm ci` in the converter directory: exactly the versions its lockfile pins. Run it again "
        "after updating this skill.",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.script_path = str(pathlib.Path(__file__).absolute())

    from ultra_search.contract import RunFailed, UltraSearchError

    if args.command in ("search", "resume", "status", "log", "result", "show", "stop", "sessions"):
        from ultra_search.runs import commands as impl
    elif args.command in ("fetch", "map", "crawl"):
        from ultra_search.pages import commands as impl
    else:
        from ultra_search import doctor as impl

    try:
        return impl.dispatch(args)
    except UltraSearchError as e:
        print(json.dumps(e.payload(), ensure_ascii=False))
        return e.exit_code
    except BrokenPipeError:
        return EXIT_OK
    except OSError as e:
        # Storage the caller pointed at -- an unwritable --out or --runs-dir, a full disk --
        # still answers in the one shape every command promises.
        err = RunFailed(
            f"could not read or write {e.filename or 'a file'}: {e.strerror or e}",
            fix="Check the path exists and is writable, or choose another with --out or --runs-dir.",
        )
        print(json.dumps(err.payload(), ensure_ascii=False))
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
