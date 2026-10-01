# Graph Report - wt-main  (2026-10-02)

## Corpus Check
- 56 files · ~97,994 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: .jsonl 11, (none) 2, .ini 1)

## Summary
- 1133 nodes · 2460 edges · 51 communities (46 shown, 5 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `44ed8171`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_run_directory.py
- doctor.py
- runs/commands.py
- test_environment.py
- supervisor.py
- pages/commands.py
- first_run
- test_contract_fake_aside.py
- page
- item_of
- classify.py
- follow.py
- aside
- test_research.py
- ultra-search 스킬 구현 계획
- test_pages.py
- conftest.py
- Path
- test_live.py
- listed
- sessions.py
- parametrize
- captured
- tool
- sitemap.js
- Ultra-Search Project
- package.json
- fetch_batch.js
- Aside Developer Tools
- Recorded parent investigation waits for three release summaries
- links.js
- cli.py
- Ultra-Search skill
- turn_finished
- discover.py
- Yonhap News Portal
- tab_one.js
- test_the_full_text_goes_to_a_file_not_into_the_reply
- test_a_file_that_was_written_counts_as_success
- browser.py
- rendered
- evidence.py
- ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)
- Context
- transcript.py
- Event
- contract.py
- `follow`를 감독자 뷰로 — `log --level progress`
- _framed
- is_opening_tool
- X JavaScript-Disabled Shell

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 49 edges
2. `page()` - 45 edges
3. `search()` - 44 edges
4. `item_of()` - 41 edges
5. `Run` - 35 edges
6. `tool()` - 29 edges
7. `run_cli()` - 27 edges
8. `finished_run_id()` - 27 edges
9. `ArgumentError` - 26 edges
10. `answer()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `_root()` --indirect_call--> `runs_dir()`  [INFERRED]
  .claude/skills/ultra-search/scripts/cli.py → tests/conftest.py
- `result_of()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/ultra_search/runs/registry.py
- `resumed()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/ultra_search/runs/registry.py

## Import Cycles
- 3-file cycle: `.claude/skills/ultra-search/scripts/ultra_search/research/__init__.py -> .claude/skills/ultra-search/scripts/ultra_search/research/commands.py -> .claude/skills/ultra-search/scripts/ultra_search/research/follow.py -> .claude/skills/ultra-search/scripts/ultra_search/research/__init__.py`
- 3-file cycle: `.claude/skills/ultra-search/scripts/ultra_search/research/__init__.py -> .claude/skills/ultra-search/scripts/ultra_search/research/commands.py -> .claude/skills/ultra-search/scripts/ultra_search/research/supervisor.py -> .claude/skills/ultra-search/scripts/ultra_search/research/__init__.py`

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (51 total, 5 thin omitted)

### Community 0 - "test_run_directory.py"
Cohesion: 0.08
Nodes (55): fixture, parametrize, Path, The run directory: what a run leaves on disk, and the files three processes…, Mid-tool means still working, and a user turn after a finished answer means a…, The process can exit before the daemon's last writes land. A message that…, `--timeout` is recorded by the process that starts the run but enforced by the…, `status` may read meta.json at any moment. A value that cannot be serialised… (+47 more)

### Community 1 - "doctor.py"
Cohesion: 0.17
Nodes (19): account_status(), mcp_tools(), The daemon as the app runs it: its health endpoint, the signed-in account, and…, {ok, detail}: whether an account is signed in. A signed-out browser fetches…, Every tool the running daemon lists over MCP, as it describes them., aside_bin(), The aside binary: finding it, starting `aside exec`, and where its daemon…, version() (+11 more)

### Community 2 - "runs/commands.py"
Cohesion: 0.05
Nodes (75): is_safe_id(), label_for(), Ids that become one segment of a path, and the labels run ids are made from., A label that can end a run id: only the basename, and only safe characters,…, ArgumentError, The caller asked for something the CLI will not do -- refused before any work., A run ended without a usable answer, or was abandoned while still going., RunFailed (+67 more)

### Community 3 - "test_environment.py"
Cohesion: 0.07
Nodes (56): argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), cli_with_path(), daemon(), doctor(), help_of(), fixture (+48 more)

### Community 4 - "supervisor.py"
Cohesion: 0.16
Nodes (15): _decode_attribute(), fetch_pages(), open_tab(), The page snippets, called in the user's browser: fetching, opening a tab,…, Fetch a batch; non-text responses are written to the browser session directory.…, The href attributes of a set of pages, decoded into the URLs they spell,…, Character references in an attribute value, decoded the way a browser does.…, read_links() (+7 more)

### Community 5 - "pages/commands.py"
Cohesion: 0.08
Nodes (39): new_crawl_dir(), new_map_file(), pages_dir(), Path, Where saved pages, maps and crawls go under `<root>`, and names that do not…, A file name nobody holds yet, reserved by creating it:…, A new folder per crawl under crawls/<host>/, reserved before anything is…, A crawl's numbered names repeat from one crawl to the next, so a folder that… (+31 more)

### Community 6 - "first_run"
Cohesion: 0.07
Nodes (42): first_run(), parametrize, `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Checked while the run is going as well as after: the supervisor copies every…, The whole path on what the daemon actually wrote: the parent is found by its…, The last lifecycle record decides: `finished` closes a turn and a later…, Aside creates the directory before the first message lands, and repl sessions… (+34 more)

### Community 7 - "test_contract_fake_aside.py"
Cohesion: 0.10
Nodes (41): CompletedProcess, live, lifecycle_frame(), ndjson(), fixture, Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The recording is daemon 1.26.1001.14's. A turn opens with `started` before its… (+33 more)

### Community 8 - "page"
Cohesion: 0.12
Nodes (31): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round… (+23 more)

### Community 9 - "item_of"
Cohesion: 0.10
Nodes (31): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+23 more)

### Community 10 - "classify.py"
Cohesion: 0.09
Nodes (33): AST, direction_violations(), exported(), imports(), is_package(), main_guard(), module_is_package(), module_name() (+25 more)

### Community 11 - "follow.py"
Cohesion: 0.11
Nodes (34): _chunks(), _escalate(), fetch_urls(), _needs_retry(), Path, Getting pages, and putting them where they can be read. Two shapes carry most…, Re-fetch through a real browser tab. Worth trying for both a client-rendered…, _save() (+26 more)

### Community 12 - "aside"
Cohesion: 0.14
Nodes (28): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), finish() (+20 more)

### Community 13 - "test_research.py"
Cohesion: 0.08
Nodes (33): lines_of(), log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Distinct from a terminal line on purpose: the caller has to be able to tell "it…, What a command printed before its JSON response, which is always the last line. (+25 more)

### Community 14 - "ultra-search 스킬 구현 계획"
Cohesion: 0.10
Nodes (20): aside CLI (1.26.810.1915, 데몬 1.26.827.1029, `~/.local/bin/aside`), codex 스킬의 구조적 선례 (`~/.claude/skills/codex`), Context (목적과 요약), crawl4ai (v1 제외의 근거), exec (`scratchpad/exec_probe.py`, `subagent_probe.py`, `--effort` 비교, kill 실험), PDF·오피스 문서 변환 — anydoc (`.tmp/anydoc`, `scratchpad/anydoc-test/`), repl (`aside repl "…"` 실측 다수), ultra-search 스킬 구현 계획 (+12 more)

### Community 15 - "test_pages.py"
Cohesion: 0.12
Nodes (21): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, A site that refuses most of its pages would otherwise answer with a list the…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., test_a_cycle_does_not_revisit() (+13 more)

### Community 16 - "conftest.py"
Cohesion: 0.18
Nodes (19): FixtureRequest, aside_home(), cli(), fake_aside(), fixtures(), no_real_aside(), fixture, MonkeyPatch (+11 more)

### Community 17 - "Path"
Cohesion: 0.10
Nodes (29): exec_calls(), The argv of every `aside exec` the CLI started, in order., make_state_db(), fixture, Path, A run recorded on 2026-08-29, before lifecycle records: a parent that spawned…, `stop` ends the watching, not the daemon's turn. Resuming the run it abandoned…, The recorded session of a real search, before lifecycle records: one websearch,… (+21 more)

### Community 18 - "test_live.py"
Cohesion: 0.19
Nodes (19): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, `completed`, a session id and token usage are the correlation working: when the…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the… (+11 more)

### Community 19 - "listed"
Cohesion: 0.11
Nodes (19): listed(), parametrize, Every URL a map found: its manifest holds the full list, not its reply., A crawl acts as the user in their own browser. A link that shares only the host…, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim…, With --from nothing is discovered, so a discovery flag would silently do… (+11 more)

### Community 20 - "sessions.py"
Cohesion: 0.11
Nodes (32): aside_home(), _db_path(), _db_session_row(), find_session_by_marker(), last_activity(), _mtime(), _opening_prompt(), Path (+24 more)

### Community 21 - "parametrize"
Cohesion: 0.10
Nodes (21): finished_run_id(), A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, `result`, `status` and `show` describe the same run. For a resumed run that is…, One shape whether one run or a group was asked for -- the shape `search` and…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller…, The transcript a resume appends to already ends in an answer. Until the new one… (+13 more)

### Community 22 - "captured"
Cohesion: 0.14
Nodes (15): captured(), fetch_without_node(), x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An…, test_a_bot_challenge_is_not_reported_as_the_page() (+7 more)

### Community 23 - "tool"
Cohesion: 0.10
Nodes (43): answer(), aside_session(), calling(), Shared fixtures. Every test that touches the aside side of the world points…, A session as Aside itself would have left it on disk -- one the CLI did not…, A `turn-lifecycle` record: the daemon frames every turn with started, final-…, tool(), turn() (+35 more)

### Community 24 - "sitemap.js"
Cohesion: 0.18
Nodes (17): Conversion to markdown, which Node packages someone else owns do: Defuddle for…, check(), document_text(), install(), _minimum(), node_minimum(), _node_status(), Path (+9 more)

### Community 25 - "Ultra-Search Project"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 26 - "package.json"
Cohesion: 0.13
Nodes (15): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+7 more)

### Community 27 - "fetch_batch.js"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 28 - "Aside Developer Tools"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 29 - "Recorded parent investigation waits for three release summaries"
Cohesion: 0.33
Nodes (7): Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 30 - "links.js"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 31 - "cli.py"
Cohesion: 0.11
Nodes (30): ArgumentParser, _add_discovery_opts(), _add_exec_opts(), _add_fetch_opts(), _add_runs_dir(), _add_target(), _add_wait_opts(), build_parser() (+22 more)

### Community 32 - "Ultra-Search skill"
Cohesion: 0.50
Nodes (4): Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 33 - "turn_finished"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 34 - "discover.py"
Cohesion: 0.36
Nodes (7): _check(), doctor(), Path, `doctor`, `setup` and `repl-api` -- the environment, and the browser's own API…, What the daemon's repl tool accepts, asked of the daemon over MCP., repl_api(), _writable()

### Community 35 - "Yonhap News Portal"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

### Community 39 - "browser.py"
Cohesion: 0.50
Nodes (4): daemon_status(), daemon_url(), The daemon's health endpoint; ULTRA_SEARCH_DAEMON_URL points doctor at another…, {ok, version, detail}: whether the daemon answers and says it is ready.

### Community 40 - "rendered"
Cohesion: 0.33
Nodes (6): They frame a turn; they are not something the run did. Printed as raw JSON they…, The members' transcripts differ in length, so one member's position applied to…, Only the event lines of a log: no response, no cursor., rendered(), test_a_group_cursor_round_trips_per_member(), test_lifecycle_records_are_not_progress_lines()

### Community 41 - "evidence.py"
Cohesion: 0.50
Nodes (4): PathLike, Start `aside exec` detached, streaming its stdout to a file the supervisor…, start_exec(), Popen

### Community 42 - "ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)"
Cohesion: 0.17
Nodes (11): Context, PR 단계와 완료 판정, SKILL.md 섹션 구조 (영어, references 없음), ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지), 결함 목록 (PR②, 각각 재현 테스트 먼저), 스킬 완료 조건 (skill-maker), 인터페이스 변경 (PR⑤), 재사용할 기존 자산 (+3 more)

### Community 43 - "Context"
Cohesion: 0.17
Nodes (11): 1. 다음 행동을 현재 상태에서 결정한다, 2. 호출 경로와 권한 계약을 맞춘다, 3. 본문과 도움말을 실제 보장에 맞춘다, Context, 검증 seam과 순서, 검토 결과와 남은 한계, 권장 실행 계약, 네 프레임을 완료 기준으로 적용 (+3 more)

### Community 44 - "transcript.py"
Cohesion: 0.29
Nodes (11): _as_text(), _assistant(), _count_lines_before(), _flatten_text(), parse_lines(), parse_record(), Path, The session transcript, as events a caller can act on. Aside writes one JSON… (+3 more)

### Community 45 - "Event"
Cohesion: 0.05
Nodes (65): Event, ultra-search: web work through the user's logged-in Aside browser., child_is_terminal(), child_session_ids(), collect_sources(), final_answer(), _framed(), _from() (+57 more)

### Community 46 - "contract.py"
Cohesion: 0.67
Nodes (3): Exception, The snippet was killed at the 120s limit. Partial output is still usable., ReplTimeout

### Community 47 - "`follow`를 감독자 뷰로 — `log --level progress`"
Cohesion: 0.18
Nodes (10): `follow`를 감독자 뷰로 — `log --level progress`, 검증 시나리오, 단계·의존·완료 판정, 리스크·가정·비차단 유예, 목적과 요약, 범위·비범위·제약, 성공 기준, 인터페이스·산출물 (+2 more)

### Community 48 - "_framed"
Cohesion: 0.67
Nodes (3): Config, Item, pytest_collection_modifyitems()

## Knowledge Gaps
- **85 isolated node(s):** `TIMED_OUT`, `batchStart`, `work`, `guard`, `TIMED_OUT` (+80 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 427 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_cli()` connect `test_environment.py` to `test_run_directory.py`, `test_contract_fake_aside.py`, `test_research.py`, `conftest.py`, `Path`, `tool`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `Run` connect `runs/commands.py` to `test_run_directory.py`, `Event`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `ArgumentError` connect `runs/commands.py` to `doctor.py`, `tab_one.js`, `pages/commands.py`, `follow.py`, `cli.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **What connects `TIMED_OUT`, `batchStart`, `work` to the rest of the system?**
  _85 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_run_directory.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07581453634085213 - nodes in this community are weakly interconnected._
- **Should `runs/commands.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05212716222533895 - nodes in this community are weakly interconnected._
- **Should `test_environment.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07130333138515488 - nodes in this community are weakly interconnected._