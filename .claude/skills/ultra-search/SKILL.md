---
name: ultra-search
description: Search the web, read full pages and documents, and map or crawl sites through the user's logged-in Aside browser, including sources anonymous web tools cannot reach. Use instead of WebSearch/WebFetch for web research, current versions, news, docs, prices, reading a URL, PDFs or Office documents, and saving pages as markdown. Triggers include search, fetch, crawl, scrape, 검색해봐, 찾아봐, 웹에서, 최신 버전, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체, 로그인해야 보이는 페이지. Not for local files or codebase search, facts already known, general browser interaction, or delegating non-web work to another model (codex).
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)
---

# Web work through the user's own browser

The CLI is in this skill's directory. Use the expanded absolute path, double-quoted, on one shell line: variable-based paths and line continuations do not match this skill's pre-approved permission pattern, so an unattended call can stop at an approval prompt.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
```

Command-specific `--help` describes inputs, outputs and recovery. Returned commands preserve the entrypoint and run store; use them rather than rebuilding paths.

## Choose by the work still needed

**Use `search` for source discovery and investigation; use `fetch` to read a known page.** Search delegates judgment to a reasoning agent and consumes the user's subscription; fetching does not invoke that agent. A supplied URL does not rule out an investigation, but merely reading it does not justify one.

Reuse evidence before acquiring it again. `result` gives a finished investigation's answer and sources; `show` exposes what it already read. Fetch again when you need a fresh or separately saved copy. Likewise, `map` lets you judge a site's scope before paying to crawl its pages; the resulting manifest can be passed to `crawl` instead of rediscovering it.

Resume a conversation when its findings are useful context for the next question, not merely because one exists. `sessions` discovers resumable conversations, including ones begun in the Aside app. Saved results survive session cleanup, but a saved result is not a promise that the browser session still exists.

## Delegate an objective, not keywords

The browsing agent chooses its own searches and pages. Give it the question, relevant source constraints and desired evidence, without prescribing a browsing sequence it may not need.

> "Have there been reports of data loss with Postgres 17 logical replication? Prefer the pgsql-bugs list and release notes. Return the affected versions and source URLs; if no relevant report is found, say what you checked rather than substituting adjacent issues."

Allow a negative finding when the question permits one. An agent returning no answer is different from an agent explaining that it found no evidence; the CLI cannot judge that conclusion for you.

## Follow state, not silence

A background command ending wakes the caller; it does not prove the investigation succeeded or even finished. Follow the latest response's `next` action: the CLI selects continued watching or result collection from the current state. A watch is useful only if something will receive its completion notification. In a one-turn environment with no later wake-up, keep it in the foreground with the returned timeout instead.

Keep supervision cheaper than the work delegated. The default log is for deciding whether to wait, inspect or intervene; request detailed logs when the source choice or an error needs explaining, not to replay the whole investigation. A quiet parent can have busy children, so use `status` to inspect activity rather than interpreting silence as failure.

## Boundaries that affect the answer

- **Watching is not cancellation.** `stop`, a watching deadline or killing the local process does not cancel the daemon's investigation or its credit use. Cancellation is in the Aside app UI. Bound the research objective before starting work you cannot cancel here.
- **Partial evidence is not a complete investigation.** Report missing or unfinished sources alongside the findings; do not turn a partial result into a confident absence claim. The CLI identifies unfinished children and whether their late results will be collected.
- **HTTP success is not readable evidence.** Login walls and bot challenges can return 200. Judge source acquisition from each item's status, not the outer command's success, and do not cite an unacquired page as if it were read.
- **Requests act as the user.** Their real cookies, sessions and browser are in use. Limit a crawl to the pages the task needs; being able to access a private source does not authorize sharing its contents elsewhere.

When a command fails, use its recovery message; reach for `doctor` when the environment is unclear rather than repeating a failing investigation. For custom browser extraction, consult `repl-api` from the installed browser rather than assuming a Node environment. Its `googleSearch` has hit bot challenges; use the browsing agent for search rather than trusting that shortcut.
