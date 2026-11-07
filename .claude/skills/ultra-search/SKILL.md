---
name: ultra-search
description: Search the web, read full pages and documents, map or crawl sites, and work a page directly (click, script, inspect its DOM or back-end calls) through the user's logged-in Aside browser, including sources anonymous web tools cannot reach. Use instead of WebSearch/WebFetch for web research, current versions, news, docs, prices, reading a URL, PDFs, HWP or Office documents at a URL, and saving pages as markdown. Triggers include search, fetch, crawl, scrape, 검색해봐, 찾아봐, 웹에서, 최신 버전, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체, 로그인해야 보이는 페이지. Not for local files or codebase search, or facts already known.
allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)
---

# Web work through the user's own browser

This skill's commands go through one CLI in its directory. The pre-approved permission rule covers that CLI alone and matches the command text: a path built from a variable, a command continued with `\`, and `aside` itself stop at an approval prompt.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
```

Each command's `--help` owns its inputs, outputs, states and recovery.

## What each path is

`search` hands an objective to a browsing agent that chooses its own searches and pages, spends the user's subscription, and reports back in another model's words. `fetch` reads a URL you already have into a file with no agent, and turns PDF, HWP and Office documents into text with the original kept.

`aside repl` is the page in your own hands: click, drag and fill, run a script in it, read its DOM, watch the calls it makes to its back end, attach to a tab the user has open. `aside guide repl` documents the installed version; a snippet running past 120 seconds is killed and reported as the daemon being unreachable, though the daemon is fine. Queries automated against a search engine draw bot challenges; `search`'s agent does its own searching.

## What you cannot see from here

- `opened` means a tool returned that URL without an error, not that the page says what the answer claims; `opened_sources` holds only those, so an answer can cite pages a search merely listed or that the agent read through a script, which no record shows.
- Nothing here cancels delegated work: only Aside itself stops a run and its credit use, so a `search`'s scope is settled when it starts.
- Requests act as the user, with their cookies, sessions and browser. A private source being reachable does not make its contents shareable.
- WebSearch and WebFetch cannot use the user's access, and WebFetch returns a summary rather than the page; the user grounds answers in pages acquired with their own access.
