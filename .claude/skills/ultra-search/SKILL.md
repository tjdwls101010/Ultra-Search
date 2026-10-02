---
name: ultra-search
description: Search the web, read full pages and documents, and map or crawl sites through the user's logged-in Aside browser, including sources anonymous web tools cannot reach. Use instead of WebSearch/WebFetch for web research, current versions, news, docs, prices, reading a URL, PDFs or Office documents at a URL, and saving pages as markdown. Triggers include search, fetch, crawl, scrape, 검색해봐, 찾아봐, 웹에서, 최신 버전, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체, 로그인해야 보이는 페이지. Not for local files or codebase search, facts already known, browser actions unrelated to acquiring web content, or delegating non-web work to another model (codex).
allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)
---

# Web work through the user's own browser

Every command goes through one CLI in this skill's directory. Call it by its expanded absolute path, double-quoted, on one shell line: the pre-approved permission rule matches the command text, so a path built from a variable or a command continued with `\` stops at an approval prompt.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
```

Each command's `--help` owns its inputs, outputs, states and recovery. A command the CLI hands back in `next` keeps the installed path and run store; run it as returned rather than rebuilding it.

## Choose by the work still needed

**`search` when choosing sources or investigating is still the work; `fetch` when the page is already known.** `search` delegates judgment to a browsing agent and spends the user's subscription; `fetch` reads a page without that agent. A URL in the request does not rule out an investigation, and reading it does not justify one.

Reuse evidence before acquiring it again: `result` holds a finished investigation's answer and sources, `show` what it already read. Fetch again only for a fresh or separately saved copy. Map first when what it finds will decide what to crawl, and crawl from its manifest so the site is walked once; crawl directly when the scope is already settled.

`resume` when an earlier conversation's findings are context for the next question, not merely because one exists; `sessions` lists what Aside still holds, including conversations begun in the app. A saved result outlives the session, so when a session is gone, reuse its `result` and start a new `search` only if the question needs more.

When content appears only after interaction -- a click, a scroll, a form the page needs -- script the browser directly: `repl-api` gives the installed REPL's API and how to call it. Use it to act on a site already chosen, not to run web searches: queries automated against a search engine draw bot challenges, and finding sources is `search`'s job.

## Delegate an objective, not keywords

The browsing agent chooses its own searches and pages. Give it the question, the source constraints that matter and the evidence you need back; leave out a browsing sequence it may not need.

> "Have there been reports of data loss with Postgres 17 logical replication? Prefer the pgsql-bugs list and release notes. Return the affected versions and source URLs; if no relevant report is found, say what you checked rather than substituting adjacent issues."

Leave room for a negative finding when the question allows one. An explicit negative finding answers the question when what the agent checked supports it; empty output does not, and the CLI cannot judge that conclusion for you.

## Follow state, not silence

A background command ending wakes the caller; it does not mean the investigation finished, let alone succeeded. The latest response's `next` says what remains, and its help says how to run it.

Keep supervision cheaper than the work delegated: `status` to judge whether a run is alive, `log` to explain a source choice or an error -- not to replay the investigation.

## Boundaries that affect the answer

- **Watching is not cancellation.** `stop`, a watch deadline or killing the process leaves the daemon's investigation and its credit use running; only the Aside app cancels it. Bound the objective before starting work you cannot stop here.
- **Only acquired content is evidence.** A fetch item's status says whether its page was acquired; a search source's `opened` says a tool opened it, the most a finished investigation can tell you, and a URL that only appeared in results is a lead. Login walls and bot checks can answer with HTTP 200, so judge each item rather than the command's success. When a claim rests on one page, read what was acquired (`show`, or `fetch` it) before citing it as read.
- **Partial evidence is not a complete investigation.** The work is done when the question is answered from sourced evidence or the specific gaps are reported -- not when an agent was started or URLs were collected. Report unfinished children and missing sources with the findings instead of turning them into a confident absence.
- **Requests act as the user.** Their cookies, sessions and browser are in use. Fetch and crawl only what the task needs; being able to reach a private source does not make its contents shareable.

When a command fails, recover from what it reports; run `doctor` when the environment is in doubt rather than repeating a failing investigation.
