---
name: ultra-search
description: Search the web, read pages in full, map and crawl sites, and save clean markdown — through the user's own logged-in Aside browser, so paywalled, login-gated and bot-blocked pages work where WebSearch and WebFetch do not. Use instead of WebSearch/WebFetch whenever the answer is on the web: current versions, releases, news, docs, prices, anything past the knowledge cutoff; reading a specific URL in full rather than a search snippet; PDFs and Office documents; a whole site or doc set at once. Triggers include web search, look it up, fetch this page, read this URL, crawl, scrape, save as markdown, 검색해봐, 찾아봐, 웹에서, 최신 버전, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체, 로그인해야 보이는 페이지. Not for searching local files or this codebase (Grep/Glob), facts already known, or handing work to another model (the codex skill).
allowed-tools: Bash(python3 "/Users/seongjin/.claude/skills/ultra-search/scripts/ultra_search.py" *)
---

# Web work through the user's own browser

One CLI. Your context carries a line reading **`Base directory for this skill: <dir>`** — the tool is `<dir>/scripts/ultra_search.py`. Below, `$US` stands for `python3 "<base directory>/scripts/ultra_search.py"`; write it out in full, on one line, double-quoted. A path built from a shell variable and a command broken across lines with `\` both fail to match the pre-approved permission pattern, and a refused call in a background run is the whole run.

`$US --help` lists the commands; `$US <command> --help` is the full option surface — every flag, its default, and what it refuses. None of that is repeated here, because a second copy is a second thing that can go stale. What is here is what `--help` cannot tell you: which command to reach for, and what has actually bitten.

## The one distinction that decides everything

**`search` hands an objective to an agent that browses and judges. Everything else reads an address you already have.**

That is the whole routing rule, and the reason is cost. A `search` runs a reasoning model through a browser — measured at 10–60 seconds and ~50,000 tokens, billed to the user's own subscription. A `fetch` of a URL you can already name costs well under a second and no tokens at all. So `search` when the question is *which sources answer this*, and `fetch` the moment you know *which page*. Searching for a URL you could have named is the one expensive mistake this tool makes easy.

Everything downstream follows: `map` before `crawl` when you are not sure a site is worth downloading; `crawl --from` the manifest `map` wrote, so the site is walked once; `result` rather than more `log` once a run has finished.

## Writing a search prompt

`search` is not a query box. It is an agent that will run its own searches, open pages and decide what is worth reporting — so give it an objective, the sources you trust, and the shape of answer you want, and it will do better than a keyword string.

> `$US search "vLLM's current recommended way to serve a quantized Llama model. Prefer the official docs and GitHub issues over blog posts. Answer with the command and the doc URL it came from."`

> `$US search "Has anyone reported data loss with Postgres 17 logical replication? Look at the pgsql-bugs list and the release notes. If nobody has, say so plainly rather than reaching for adjacent issues."`

Note the second one. An agent asked an open question will find *something* — telling it that "nothing" is an acceptable answer is what keeps it from manufacturing one. The tool reports a genuinely empty result as its own outcome rather than as success or failure, and that only works if the prompt permitted it.

Several prompts in one call run in parallel as a group.

## Collecting work you started

`search` waits by default and hands you the answer inline, which is what usually happens. When a run outlasts the wait it is left alive and the reply carries a `next` object: the exact command to run, the Bash timeout to give it, and that it goes in the background. Run it as written. It exits when the run finishes, and a background Bash call that exits is what notifies you — that exit *is* the wake-up.

What that follow prints is a supervisor's view: what the run reached for and what it said, one line per turn, not how it asked. Delegating only saves context if watching stays small -- measured on a run that spawned three subagents, the view with every call's arguments was five times the size, and none of those arguments changed what to do next. Retracing why a source was chosen is `log --level steps`; the answer and the pages behind it are `result` and `show`.

Then collect with `next.then`. Starting a background run and never coming back for it is the failure this field exists to prevent; if you have nothing to do meanwhile, say you are waiting and hand the turn back armed, rather than filling the time.

If this is your only turn — nothing will wake you — run the follow in the *foreground* as the turn's last call, and raise that Bash call's own timeout to match the one `next` gives you.

## What has actually bitten

**`stop` does not stop anything.** It ends the watching. The daemon-side run carries on and keeps spending the user's credits, and there is no CLI that can cancel it — only the Aside app's own UI. Killing the process does not help either; that was measured, and the run continued and spawned more work afterwards. The only real cost control is asking for something bounded in the first place.

**Silence is not a stall.** A run that spawns subagents goes quiet for minutes while they work — the parent has nothing to say until they report. `status` distinguishes these by looking at every child too, and flags a long silence without acting on it, because a slow investigation and a stuck one look identical from outside. Treat the flag as something to check, not a verdict.

**A blocked page is a successful HTTP response.** Bot challenges, login walls and client-rendered shells all return 200 with a body. `fetch` classifies them and refuses to save one as the page, so an item that is not `ok` means that source is genuinely not in hand — do not cite it, and do not assume the file exists. Pages that render client-side are automatically retried in a real browser tab, which is usually enough.

**The browser is the user's real browser.** Their cookies, their sessions, their tabs — that is the point, and it is why a subscription feed or a paywalled article works at all. It also means a `crawl` is hitting sites as them. Keep page counts to what the task needs.

**A conversation already underway is usually cheaper than a new one.** `resume` continues any session Aside still has — one this tool started, or one the user began in the Aside app or with a bare `aside exec` — keeping everything it already worked out instead of paying to rediscover it. `sessions` is how you find one, because it lists the opening prompt and nobody recognises a session id. It is refused on a session still working: attaching to a live one cannot steer it, only wait for the current turn and print the result.

**Sessions are cleaned up within about a day.** Each run's transcript, answer and sources are copied into the runs directory as it goes, so results survive; the Aside-side session does not — which is also why a session worth continuing is worth continuing today.

**`repl-api` prints the browser REPL's own documentation**, live from the installed version. Reach for it before hand-writing browser automation. Its sandbox is narrower than Node: no `URL`, no `AbortController`, and `fs` is promise-based and refuses writes outside the project and session directories. Its built-in `googleSearch` hits a bot challenge and cannot be trusted — that is what `search` is for.

**When something is wrong, `doctor` first.** It reports the binary, the daemon, the account and the conversion toolchain in one line and exits non-zero when something it can see would stop a command. `setup` installs the Node packages that convert HTML and documents; without them, conversion is the thing that fails, not the fetch.
