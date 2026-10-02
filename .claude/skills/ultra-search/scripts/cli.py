# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""ultra-search — search, read, map and save the web through the user's logged-in Aside browser.

The whole command line lives here: the parser, every command's help, dispatch to the units that do the work, and the one table that turns how a command ended into its exit code. Every command prints one JSON document on stdout; progress and diagnostics go to stderr.
"""
from __future__ import annotations

import argparse
from functools import partial
import json
import math
import os
import pathlib
import sys
from urllib.parse import urlparse

from ultra_search import __version__, aside, doctor, fetch, outcome, research, site, workspace

FORMAT_CHOICES = ("md", "html")
VIA_CHOICES = ("auto", "fetch", "tab")
#: Which exit code each way a command can end is. Exit codes describe the command, not the
#: quality or completeness of an investigation; the payload's states say that.
EXIT = {outcome.OK: 0, outcome.BAD_ARGUMENTS: 2, outcome.ASIDE_UNAVAILABLE: 3, outcome.FAILED: 4, outcome.EMPTY: 5}

_REFUSED = "the arguments were refused before any work; the reply says what to change"
_NO_ASIDE = "the aside binary is missing or its daemon does not answer; the reply says how to fix it"
_UNWRITABLE = "a file under the runs dir or --out could not be read or written"
#: What each ending means for each command -- the Exit lines of its --help.
ENDINGS = {
    "search": {outcome.OK: "every run was started and reported; read each run's state",
               outcome.BAD_ARGUMENTS: _REFUSED, outcome.ASIDE_UNAVAILABLE: _NO_ASIDE,
               outcome.FAILED: f"a run failed or was abandoned, or {_UNWRITABLE}",
               outcome.EMPTY: "every run finished with no answer and no sources"},
    "status": {outcome.OK: "the runs were reported; read each run's state", outcome.BAD_ARGUMENTS: _REFUSED,
               outcome.FAILED: f"a run failed or was abandoned, or {_UNWRITABLE}"},
    "log": {outcome.OK: "the log was read -- not that the research finished or succeeded",
            outcome.BAD_ARGUMENTS: _REFUSED, outcome.FAILED: _UNWRITABLE},
    "result": {outcome.OK: "every run has a result; read each run's state", outcome.BAD_ARGUMENTS: _REFUSED,
               outcome.FAILED: f"a run failed, was abandoned or is still running, or {_UNWRITABLE}",
               outcome.EMPTY: "every run ended with no answer and no sources"},
    "show": {outcome.OK: "the text was returned", outcome.BAD_ARGUMENTS: _REFUSED, outcome.FAILED: _UNWRITABLE},
    "stop": {outcome.OK: "watching stopped where it was going; the daemon's runs continue",
             outcome.BAD_ARGUMENTS: _REFUSED, outcome.FAILED: _UNWRITABLE},
    "sessions": {outcome.OK: "sessions were listed", outcome.BAD_ARGUMENTS: _REFUSED,
                 outcome.EMPTY: "no session matched"},
    "fetch": {outcome.OK: "at least one file was written; read each item's status", outcome.BAD_ARGUMENTS: _REFUSED,
              outcome.ASIDE_UNAVAILABLE: _NO_ASIDE, outcome.FAILED: f"nothing was saved, or {_UNWRITABLE}"},
    "map": {outcome.OK: "URLs were found and the manifest written", outcome.BAD_ARGUMENTS: _REFUSED,
            outcome.ASIDE_UNAVAILABLE: _NO_ASIDE, outcome.FAILED: _UNWRITABLE,
            outcome.EMPTY: "no sitemap and no page could be read"},
    "crawl": {outcome.OK: "at least one page was saved; the manifest has every page's status",
              outcome.BAD_ARGUMENTS: _REFUSED, outcome.ASIDE_UNAVAILABLE: _NO_ASIDE,
              outcome.FAILED: f"nothing was saved, or {_UNWRITABLE}"},
    "doctor": {outcome.OK: "nothing it can see would stop a command", outcome.BAD_ARGUMENTS: _REFUSED,
               outcome.ASIDE_UNAVAILABLE: "a check failed; each failed check has its fix"},
    "setup": {outcome.OK: "the packages were installed", outcome.BAD_ARGUMENTS: _REFUSED,
              outcome.ASIDE_UNAVAILABLE: "Node is missing or the install failed; the reply says which"},
    "repl-api": {outcome.OK: "the daemon's tool description was returned", outcome.BAD_ARGUMENTS: _REFUSED,
                 outcome.ASIDE_UNAVAILABLE: _NO_ASIDE},
}
ENDINGS["resume"] = ENDINGS["search"]


def _exit_lines(command: str) -> str:
    return "Exit codes:\n" + "\n".join(f"{EXIT[o]}  {meaning}" for o, meaning in
                                       sorted(ENDINGS[command].items(), key=lambda kv: EXIT[kv[0]]))


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
        raise SystemExit(EXIT[outcome.BAD_ARGUMENTS])


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


def _user_path(text: str) -> str:
    """A path as typed, with `~` expanded here so a home that does not exist is refused now.

    Expanded as a string: a trailing slash is part of what was asked (`--out notes/` is a
    folder), and a Path would drop it.
    """
    expanded = os.path.expanduser(text)
    if expanded.startswith("~"):
        raise argparse.ArgumentTypeError(f"{text!r} names a home directory that does not exist")
    return expanded


def _add_runs_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--runs-dir",
        type=_user_path,
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
    p.add_argument("--effort", choices=aside.EFFORTS, help="Aside reasoning effort. Default: the account's setting.")
    p.add_argument("--model", help="Aside model id, e.g. openai-codex/gpt-5.6-sol. Default: the account's setting.")
    p.add_argument("--speed", choices=aside.SPEEDS, help="Aside speed setting. Default: the account's setting.")
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
        epilog="Exit codes describe the command, not the investigation: 0 handled (read the states in the reply) | "
        "2 bad arguments | 3 Aside unavailable | 4 a run failed or was abandoned, nothing was saved, or a file could not "
        "be written | 5 no result data. Each command's --help lists its own.",
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
        choices=research.LEVELS,
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
        description="Each run's answer with its citation tags resolved to URL footnotes, and every source the run and its "
        "children touched -- always as a runs list, one entry per run. Results are saved in the runs directory and "
        "outlive Aside's session. empty means no answer and no sources, not that a claim was disproved; a textual "
        "negative finding is still an answer.\n"
        "`opened` means a tool that opens pages returned that URL: an inference that the "
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
        type=_user_path,
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
        "The reply is a summary whatever the site's size: count, coverage (how many pages could not be read with the "
        "first 10 of them, and whether a budget or --max-urls cut discovery short), the first 10 URLs, and "
        "manifest_path, the file holding every URL and the full coverage.",
    )
    m.add_argument("url", type=_web_url, metavar="URL", help="Site or section root.")
    _add_discovery_opts(m)
    m.add_argument("--out", type=_user_path, metavar="FILE", help="Write the manifest here instead of .ultra-search/maps/<host>-<timestamp>.json.")
    m.add_argument("--list-all", action="store_true", help="Also print every URL in the reply, not only the first 10.")
    _add_runs_dir(m)

    # --- crawl --------------------------------------------------------------
    c = sub.add_parser(
        "crawl",
        help="Map a site and save every page as markdown.",
        description="map + fetch. Writes NNN-slug.md files and a manifest.json recording url, file, title, "
        "status and via for each page. The reply counts pages by status and lists the first 10 that are not ok; the "
        "manifest has every page.\n"
        "With --from, only --max-pages, --via, --concurrency, --no-frontmatter and --out apply; the manifest is "
        "crawled as it is, so discovery flags are refused.",
    )
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("url", nargs="?", type=_web_url, metavar="URL", help="Site root to crawl.")
    src.add_argument("--from", dest="from_manifest", type=_user_path, metavar="FILE", help="A manifest.json from `map`, crawled as-is.")
    c.add_argument("--max-pages", type=_count(1), default=25, metavar="N", help="Stop after this many pages. Default 25.")
    _add_discovery_opts(c)
    _add_fetch_opts(c)
    c.add_argument("--out", type=_user_path, metavar="DIR", help="An empty or new output directory. Default: a new "
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
        description="Installs the Node packages page and document conversion use, exactly the versions their lockfile pins. Run it again "
        "after updating this skill.",
    )

    for name, command in sub.choices.items():
        command.epilog = f"{command.epilog}\n\n{_exit_lines(name)}" if command.epilog else _exit_lines(name)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_supervise"]:
        # Internal: the detached supervisor a `search` or `resume` starts, through the same
        # entry point the caller used. Not a command, so not in --help.
        research.run_detached(argv[1])
        return 0
    args = build_parser().parse_args(argv)
    # The path as the caller reached it, not resolved: a `next` command built from it keeps
    # the installed location, symlink included.
    cli = str(pathlib.Path(__file__).absolute())
    try:
        reply = _dispatch(args, _root(args), cli)
        print(json.dumps(reply.payload, ensure_ascii=False))
        return EXIT[reply.outcome]
    except outcome.UltraSearchError as e:
        print(json.dumps(e.payload(), ensure_ascii=False))
        return EXIT[e.outcome]
    except BrokenPipeError:
        return EXIT[outcome.OK]
    except OSError as e:
        # Storage the caller pointed at -- an unwritable --out or --runs-dir, a full disk --
        # still answers in the one shape every command promises.
        err = outcome.RunFailed(
            f"could not read or write {e.filename or 'a file'}: {e.strerror or e}",
            fix="Check the path exists and is writable, or choose another with --out or --runs-dir.",
        )
        print(json.dumps(err.payload(), ensure_ascii=False))
        return EXIT[err.outcome]


def _root(args: argparse.Namespace) -> pathlib.Path:
    """Where runs and saved pages go: --runs-dir, or .ultra-search/ in the working directory."""
    if not getattr(args, "runs_dir", None):
        return workspace.default_root()
    try:
        return pathlib.Path(args.runs_dir).expanduser().resolve()
    except RuntimeError as e:  # a symlink loop, on the Pythons that raise rather than OSError
        raise outcome.ArgumentError(f"--runs-dir {args.runs_dir!r} cannot be resolved: {e}",
                                    fix="Pass a directory that is not a symlink loop.") from e


def _dispatch(args: argparse.Namespace, root: pathlib.Path, cli: str) -> outcome.Reply:
    c = args.command
    if c in ("search", "resume"):
        common = dict(wait=args.wait, background=args.background, label=args.label, effort=args.effort,
                      model=args.model, speed=args.speed, timeout=args.timeout, cli=cli)
        if c == "search":
            return research.search(root, list(args.prompt), **common)
        return research.resume(root, args.target, args.prompt, **common)
    if c == "status":
        return research.status(root, run=args.run, group=args.group, stall_after=args.stall_after)
    if c == "log":
        return research.log(root, run=args.run, group=args.group, since=args.since, level=args.level,
                            follow_=args.follow, follow_timeout=args.follow_timeout, heartbeat=args.heartbeat, cli=cli)
    if c == "result":
        return research.result(root, run=args.run, group=args.group, sources_only=args.sources_only)
    if c == "show":
        return research.show(root, run=args.run, source=args.source, item=args.item)
    if c == "stop":
        return research.stop(root, run=args.run, group=args.group, every=args.all)
    if c == "sessions":
        return research.sessions(limit=args.limit, mine=args.mine, search=args.search)
    if c == "fetch":
        return fetch.fetch(root, args.url, out=args.out, fmt=args.format, via=args.via, concurrency=args.concurrency,
                           frontmatter=not args.no_frontmatter, print_content=args.print_content,
                           max_chars=args.max_chars)
    if c == "map":
        return site.map_site(root, args.url, depth=args.depth, max_urls=args.max_urls, include=args.include,
                             exclude=args.exclude, no_sitemap=args.no_sitemap, out=args.out, list_all=args.list_all)
    if c == "crawl":
        return site.crawl(root, args.url, from_manifest=args.from_manifest, max_pages=args.max_pages,
                          depth=args.depth, max_urls=args.max_urls, include=args.include, exclude=args.exclude,
                          no_sitemap=args.no_sitemap, via=args.via, concurrency=args.concurrency,
                          frontmatter=not args.no_frontmatter, out=args.out)
    if c == "doctor":
        return doctor.doctor(root)
    if c == "setup":
        return doctor.setup()
    return doctor.repl_api(every=args.all)


if __name__ == "__main__":
    sys.exit(main())
