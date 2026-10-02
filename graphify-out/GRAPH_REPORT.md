# Graph Report - wt-main  (2026-10-02)

## Corpus Check
- 58 files · ~110,387 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: .jsonl 11, (none) 2, .ini 1)

## Summary
- 1295 nodes · 2836 edges · 64 communities (59 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `839ae51c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_run_directory.py
- AsideUnavailable
- research/commands.py
- run_cli
- aside/__init__.py
- Run
- first_run
- test_contract_fake_aside.py
- page
- item_of
- test_structure.py
- classify.py
- aside
- test_research.py
- ultra-search 스킬 구현 계획
- test_pages.py
- Path
- Path
- test_live.py
- parametrize
- sessions.py
- finished_run_id
- captured
- tool
- node.py
- Ultra-Search Project
- package.json
- sitemap.js
- Aside Developer Tools
- Recorded parent investigation waits for three release summaries
- fetch_batch.js
- cli.py
- Ultra-Search skill
- links.js
- ultra-search 스킬 레이아웃 이행 재설계 계획
- Yonhap News Portal
- UltraSearchError
- Event
- test_a_file_that_was_written_counts_as_success
- rendered
- lines_of
- saved
- ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)
- Context
- transcript.py
- evidence.py
- repl.py
- `follow`를 감독자 뷰로 — `log --level progress`
- conftest.py
- tab_one.js
- test_aside_formats.py
- supervisor.py
- ArgumentError
- site/commands.py
- X JavaScript-Disabled Shell
- workspace.py
- parametrize
- Source
- eventful
- test_stop_never_overwrites_a_run_that_finished_while_it_waited
- Turn
- resolve_answer_tags
- test_a_child_that_reported_mid_turn_is_still_running

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 64 edges
2. `search()` - 54 edges
3. `page()` - 49 edges
4. `run_cli()` - 41 edges
5. `item_of()` - 41 edges
6. `Run` - 35 edges
7. `tool()` - 33 edges
8. `finished_run_id()` - 33 edges
9. `answer()` - 30 edges
10. `Event` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `_root()` --indirect_call--> `runs_dir()`  [INFERRED]
  .claude/skills/ultra-search/scripts/cli.py → tests/conftest.py
- `events()` --references--> `Event`  [EXTRACTED]
  tests/test_aside_formats.py → .claude/skills/ultra-search/scripts/ultra_search/aside/transcript.py
- `prefix()` --references--> `Event`  [EXTRACTED]
  tests/test_aside_formats.py → .claude/skills/ultra-search/scripts/ultra_search/aside/transcript.py

## Import Cycles
- 3-file cycle: `.claude/skills/ultra-search/scripts/ultra_search/research/__init__.py -> .claude/skills/ultra-search/scripts/ultra_search/research/commands.py -> .claude/skills/ultra-search/scripts/ultra_search/research/supervisor.py -> .claude/skills/ultra-search/scripts/ultra_search/research/__init__.py`
- 3-file cycle: `.claude/skills/ultra-search/scripts/ultra_search/research/__init__.py -> .claude/skills/ultra-search/scripts/ultra_search/research/commands.py -> .claude/skills/ultra-search/scripts/ultra_search/research/follow.py -> .claude/skills/ultra-search/scripts/ultra_search/research/__init__.py`

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (64 total, 4 thin omitted)

### Community 0 - "test_run_directory.py"
Cohesion: 0.10
Nodes (42): fixture, Path, The run directory: what a run leaves on disk, and the files three processes…, `--timeout` is recorded by the process that starts the run but enforced by the…, `status` may read meta.json at any moment. A value that cannot be serialised…, meta.json is written by the starting CLI, the detached supervisor and `stop`,…, Processes, not threads: the lock is a file, and a threads-only test would pass…, A group starts every member at once. Reserving the directory with O_EXCL is… (+34 more)

### Community 1 - "AsideUnavailable"
Cohesion: 0.15
Nodes (18): account_status(), daemon_status(), daemon_url(), mcp_tools(), The daemon as the app runs it: its health endpoint, the signed-in account, and…, The health endpoint of the daemon `aside exec` will use. The aside CLI takes…, {ok, version, detail}: whether the daemon answers and says it is ready., {ok, detail}: whether an account is signed in. A signed-out browser fetches… (+10 more)

### Community 2 - "research/commands.py"
Cohesion: 0.13
Nodes (36): Reply, _await_and_report(), _await_terminal(), _envelope(), log(), next_step(), _outcome(), Path (+28 more)

### Community 3 - "run_cli"
Cohesion: 0.07
Nodes (60): argv in; the exit code, the JSON document on stdout, and everything printed --…, run_cli(), check(), cli_with_path(), daemon(), doctor(), help_of(), fixture (+52 more)

### Community 4 - "aside/__init__.py"
Cohesion: 0.16
Nodes (15): _decode_attribute(), fetch_pages(), open_tab(), The page snippets, called in the user's browser: fetching, opening a tab,…, Fetch a batch; non-text responses are written to the browser session directory.…, The href attributes of a set of pages, decoded into the URLs they spell,…, Character references in an attribute value, decoded the way a browser does.…, read_links() (+7 more)

### Community 5 - "Run"
Cohesion: 0.11
Nodes (31): is_safe_id(), label_for(), normal(), Ids that become one segment of a path, and the labels run ids are made from., One spelling for text that can be typed two ways: a Mac can hand over 한…, A label that can end a run id: only the basename, and only letters, digits and…, copy_new_lines(), PathLike (+23 more)

### Community 6 - "first_run"
Cohesion: 0.09
Nodes (40): first_run(), Attaching to a live session was measured waiting for the current turn and then…, The capability this is for: a conversation started in the Aside app, or by a…, `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, The whole path on what the daemon actually wrote: the parent is found by its…, Typed on a Mac a name can arrive decomposed; it is stored composed, the way it…, Aside creates the directory before the first message lands, and repl sessions… (+32 more)

### Community 7 - "test_contract_fake_aside.py"
Cohesion: 0.10
Nodes (41): CompletedProcess, live, lifecycle_frame(), ndjson(), fixture, Path, Keeping the stand-in aside binary honest. Every other test that involves a…, Where the lifecycle records sit among the others: what a turn's boundaries look… (+33 more)

### Community 8 - "page"
Cohesion: 0.10
Nodes (36): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, `.ultra-search/` lands in whatever project the caller is in. Its pages and runs…, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets… (+28 more)

### Community 9 - "item_of"
Cohesion: 0.09
Nodes (34): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+26 more)

### Community 10 - "test_structure.py"
Cohesion: 0.07
Nodes (46): AST, direction_violations(), exported(), foreign_names(), imports(), is_package(), main_guard(), module_is_package() (+38 more)

### Community 11 - "classify.py"
Cohesion: 0.11
Nodes (34): _chunks(), _escalate(), fetch_urls(), _needs_retry(), Path, Getting pages, and putting them where they can be read. Two shapes carry most…, Re-fetch through a real browser tab. Worth trying for both a client-rendered…, _save() (+26 more)

### Community 12 - "aside"
Cohesion: 0.14
Nodes (28): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), finish() (+20 more)

### Community 13 - "test_research.py"
Cohesion: 0.09
Nodes (27): log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The recorded session's earlier turn left a subagent mid-tool. That child…, Checked while the run is going as well as after: the supervisor copies every…, The log of a module-scoped run; the text is the rendered lines, without the…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Watching progress must not be a way to load a fetched page into context by… (+19 more)

### Community 14 - "ultra-search 스킬 구현 계획"
Cohesion: 0.10
Nodes (20): aside CLI (1.26.810.1915, 데몬 1.26.827.1029, `~/.local/bin/aside`), codex 스킬의 구조적 선례 (`~/.claude/skills/codex`), Context (목적과 요약), crawl4ai (v1 제외의 근거), exec (`scratchpad/exec_probe.py`, `subagent_probe.py`, `--effort` 비교, kill 실험), PDF·오피스 문서 변환 — anydoc (`.tmp/anydoc`, `scratchpad/anydoc-test/`), repl (`aside repl "…"` 실측 다수), ultra-search 스킬 구현 계획 (+12 more)

### Community 15 - "test_pages.py"
Cohesion: 0.09
Nodes (28): listed(), mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, A site that refuses most of its pages would otherwise answer with a list the…, Every URL a map found: its manifest holds the full list, not its reply., site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A crawl acts as the user in their own browser. A link that shares only the host… (+20 more)

### Community 16 - "Path"
Cohesion: 0.14
Nodes (21): FixtureRequest, aside_home(), cli(), fake_aside(), fixtures(), no_real_aside(), fixture, MonkeyPatch (+13 more)

### Community 17 - "Path"
Cohesion: 0.09
Nodes (30): exec_calls(), The argv of every `aside exec` the CLI started, in order., make_state_db(), Path, `stop` ends the watching, not the daemon's turn. Resuming the run it abandoned…, The browsing agent acts as the user, in their logged-in browser. What research…, A store made by an earlier version has no .gitignore. Reading it writes…, The failure this prevents: a caller starts work in the background and simply… (+22 more)

### Community 18 - "test_live.py"
Cohesion: 0.19
Nodes (19): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, `completed`, a session id and token usage are the correlation working: when the…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the… (+11 more)

### Community 19 - "parametrize"
Cohesion: 0.17
Nodes (12): parametrize, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, With --from nothing is discovered, so a discovery flag would silently do…, The full list is a file the caller can open when it wants it. Printing it would…, test_a_crawl_never_writes_into_a_folder_that_already_has_files(), test_a_discovery_snippet_cut_off_by_the_repl_limit_is_reported(), test_a_manifest_is_crawled_as_it_is_so_discovery_flags_are_refused() (+4 more)

### Community 20 - "sessions.py"
Cohesion: 0.12
Nodes (30): aside_home(), _db_path(), _db_session_row(), find_session_by_marker(), last_activity(), _mtime(), _opening_prompt(), Path (+22 more)

### Community 21 - "finished_run_id"
Cohesion: 0.08
Nodes (25): argv in; the exit code, stdout and stderr out, kept apart., run_cli_streams(), finished_run_id(), The transcript a resume appends to already ends in an answer. Until the new one…, A URL appears twice: once as a search result's excerpt, once as the page a…, One shape whether one run or a group was asked for -- the shape `search` and…, Aside removes old sessions on its own schedule. A run whose evidence lived only…, The command `next` hands back names no level, so the default is what a caller… (+17 more)

### Community 22 - "captured"
Cohesion: 0.14
Nodes (15): captured(), fetch_without_node(), x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An…, test_a_bot_challenge_is_not_reported_as_the_page() (+7 more)

### Community 23 - "tool"
Cohesion: 0.09
Nodes (40): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), every_source(), poll(), A resumed session's transcript opens with the earlier turns. Until the new… (+32 more)

### Community 24 - "node.py"
Cohesion: 0.18
Nodes (17): Conversion to markdown, which Node packages someone else owns do: Defuddle for…, check(), document_text(), install(), _minimum(), node_minimum(), _node_status(), Path (+9 more)

### Community 25 - "Ultra-Search Project"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 26 - "package.json"
Cohesion: 0.13
Nodes (15): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+7 more)

### Community 27 - "sitemap.js"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 28 - "Aside Developer Tools"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 29 - "Recorded parent investigation waits for three release summaries"
Cohesion: 0.33
Nodes (7): Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 30 - "fetch_batch.js"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 31 - "cli.py"
Cohesion: 0.10
Nodes (36): ArgumentParser, _add_discovery_opts(), _add_exec_opts(), _add_fetch_opts(), _add_runs_dir(), _add_target(), _add_wait_opts(), build_parser() (+28 more)

### Community 32 - "Ultra-Search skill"
Cohesion: 0.50
Nodes (4): Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 33 - "links.js"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 34 - "ultra-search 스킬 레이아웃 이행 재설계 계획"
Cohesion: 0.09
Nodes (21): CLI 계약 (구현 후), Context, F1·F2 수정 규칙 (① 단계), README 섹션 구조 (한국어), SKILL.md (구현 후), ultra-search 스킬 레이아웃 이행 재설계 계획, 구조 테스트 (`tests/test_structure.py`), 구현 기록 (2026-10-02) (+13 more)

### Community 35 - "Yonhap News Portal"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

### Community 36 - "UltraSearchError"
Cohesion: 0.40
Nodes (4): Exception, A run ended without a usable answer, or was abandoned while still going., RunFailed, UltraSearchError

### Community 37 - "Event"
Cohesion: 0.24
Nodes (14): Event, Whether the last turn in these events has ended, rather than stopped mid-work.…, One transcript record: user, assistant, tool_result, system, lifecycle, or raw…, An assistant message that ended its turn's work rather than pausing to call a…, turn_finished(), _assistant(), _clip(), _first_line() (+6 more)

### Community 39 - "rendered"
Cohesion: 0.33
Nodes (6): They frame a turn; they are not something the run did. Printed as raw JSON they…, The members' transcripts differ in length, so one member's position applied to…, Only the event lines of a log, without its response., rendered(), test_a_group_cursor_round_trips_per_member(), test_lifecycle_records_are_not_progress_lines()

### Community 40 - "lines_of"
Cohesion: 0.15
Nodes (13): lines_of(), Distinct from a terminal line on purpose: the caller has to be able to tell "it…, What a command printed before its JSON response, which is always the last line., A group watched until its deadline: the members that ended say so, the one…, A parent investigation goes silent while its subagents work; a watcher that…, test_a_follow_that_runs_out_of_time_says_the_run_is_still_going(), test_a_group_follow_exits_only_when_every_member_is_terminal(), test_a_watch_that_runs_out_says_how_every_member_stands() (+5 more)

### Community 41 - "saved"
Cohesion: 0.40
Nodes (5): `result`, `status` and `show` describe the same run. For a resumed run that is…, The whole result a reply points at., saved(), test_a_failed_run_exits_four(), test_every_view_of_a_resumed_run_covers_its_own_turn_only()

### Community 42 - "ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)"
Cohesion: 0.17
Nodes (11): Context, PR 단계와 완료 판정, SKILL.md 섹션 구조 (영어, references 없음), ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지), 결함 목록 (PR②, 각각 재현 테스트 먼저), 스킬 완료 조건 (skill-maker), 인터페이스 변경 (PR⑤), 재사용할 기존 자산 (+3 more)

### Community 43 - "Context"
Cohesion: 0.17
Nodes (11): 1. 다음 행동을 현재 상태에서 결정한다, 2. 호출 경로와 권한 계약을 맞춘다, 3. 본문과 도움말을 실제 보장에 맞춘다, Context, 검증 seam과 순서, 검토 결과와 남은 한계, 권장 실행 계약, 네 프레임을 완료 기준으로 적용 (+3 more)

### Community 44 - "transcript.py"
Cohesion: 0.19
Nodes (18): _as_text(), _assistant(), _child_ids(), _count_lines_before(), _flatten_text(), parse_lines(), parse_record(), Path (+10 more)

### Community 45 - "evidence.py"
Cohesion: 0.16
Nodes (16): child_is_terminal(), child_session_ids(), _framed(), _from(), has_terminal_answer(), What one run found: its own turn of the session, that turn's children, and…, Index of the user message that began this run's turn, or None if it is not…, Whether the turn has given its answer, as opposed to stopping to call a tool.… (+8 more)

### Community 46 - "repl.py"
Cohesion: 0.23
Nodes (11): _load_snippet(), parse_ndjson(), Exception, Running JavaScript in the user's browser and reading back NDJSON. The one thing…, The snippet was killed at the 120s limit. Partial output is still usable., Run code in the REPL and return the JSON objects it printed, in order. Partial…, Run a snippet whose output is known and check that exact output came back. A…, repl_probe() (+3 more)

### Community 47 - "`follow`를 감독자 뷰로 — `log --level progress`"
Cohesion: 0.18
Nodes (10): `follow`를 감독자 뷰로 — `log --level progress`, 검증 시나리오, 단계·의존·완료 판정, 리스크·가정·비차단 유예, 목적과 요약, 범위·비범위·제약, 성공 기준, 인터페이스·산출물 (+2 more)

### Community 48 - "conftest.py"
Cohesion: 0.13
Nodes (17): Config, Item, pytest_collection_modifyitems(), Shared fixtures. Every test that touches the aside side of the world points…, A `turn-lifecycle` record: the daemon frames every turn with started, final-…, turn(), user(), A transcript can open with a lifecycle record, or with a system message listing… (+9 more)

### Community 50 - "test_aside_formats.py"
Cohesion: 0.10
Nodes (31): events(), home(), prefix(), fixture, parametrize, Path, What Aside actually wrote, read through the aside unit into this skill's terms.…, The first ``n`` records, as a reader polling the transcript mid-run would see… (+23 more)

### Community 52 - "supervisor.py"
Cohesion: 0.16
Nodes (19): decorate_prompt(), Append the research scope and the correlation marker to a prompt. The marker…, _abandon(), _activity(), _finish(), _from_stdout(), Path, PathLike (+11 more)

### Community 53 - "ArgumentError"
Cohesion: 0.08
Nodes (34): ultra-search: web work through the user's logged-in Aside browser., AmbiguousRun, ArgumentError, How a command ends: its reply, which kind of ending it was, and errors that…, The caller asked for something the CLI will not do -- refused before any work., No run has this id, or begins with it., Several runs begin with this prefix; the error names them., RunNotFound (+26 more)

### Community 54 - "site/commands.py"
Cohesion: 0.11
Nodes (28): _brief(), crawl(), _discovery(), _host(), _links(), map_site(), _providers(), Path (+20 more)

### Community 57 - "workspace.py"
Cohesion: 0.31
Nodes (9): default_root(), ensure(), mark_written(), Path, Where the skill keeps what it makes: `.ultra-search/` in the working directory.…, The store a command uses: the one the caller chose, or the default. Choosing…, Create ``root`` for a write; when it is the default store, also a .gitignore…, Called where something is written into an existing store, so a default store an… (+1 more)

### Community 58 - "parametrize"
Cohesion: 0.12
Nodes (17): listing_of(), parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, The last lifecycle record decides: `finished` closes a turn and a later…, A transcript in which a search lists ``n`` pages and the run fetches the…, A real run listed 1,051 sources and its reply ran to 244 KB, which the caller…, The aside CLI talks to DAEMON_BASE_URL when it is set; checking another daemon… (+9 more)

### Community 59 - "Source"
Cohesion: 0.24
Nodes (9): collect_sources(), final_answer(), merge_sources(), Every URL the turn and its children touched, one entry per URL., The turn's answer, each child's appended under its id. Citations resolve…, The text of the last finished assistant turn, with citation tags resolved to…, Every URL the run touched, in order, deduplicated by URL. ``opened`` separates…, Several streams' sources as one list, one entry per URL, first seen first. A… (+1 more)

### Community 60 - "eventful"
Cohesion: 0.32
Nodes (8): eventful(), fixture, A run recorded on 2026-08-29, before lifecycle records: a parent that spawned…, The recorded session of a real search, before lifecycle records: one websearch,…, A run whose transcript holds every kind of event the log has to render., recorded(), simple_search(), start_isolated()

### Community 64 - "Turn"
Cohesion: 0.29
Nodes (4): This turn's own tool results, in order -- what `show --item N` counts., What the turn already read of a URL: the fullest result that holds the page,…, total_usage(), Turn

### Community 65 - "resolve_answer_tags"
Cohesion: 0.67
Nodes (6): An answer with Aside's quote and citation tags replaced by the text they wrap…, resolve_answer_tags(), citation(), quote(), tagged(), urls_of()

### Community 66 - "test_a_child_that_reported_mid_turn_is_still_running"
Cohesion: 0.40
Nodes (5): parametrize, Recorded from a real child: it messages its parent and stops with `stop` well…, Text in a turn that stopped to call a tool is the worker narrating what it is…, test_a_child_that_reported_mid_turn_is_still_running(), test_only_a_finished_turn_supplies_the_answer()

## Knowledge Gaps
- **103 isolated node(s):** `TIMED_OUT`, `batchStart`, `work`, `guard`, `TIMED_OUT` (+98 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 494 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_cli()` connect `run_cli` to `test_run_directory.py`, `test_contract_fake_aside.py`, `page`, `test_research.py`, `test_pages.py`, `conftest.py`, `Path`, `Path`, `finished_run_id`, `parametrize`, `test_stop_never_overwrites_a_run_that_finished_while_it_waited`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `Run` connect `Run` to `test_run_directory.py`, `research/commands.py`, `evidence.py`, `supervisor.py`, `ArgumentError`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `ArgumentError` connect `ArgumentError` to `research/commands.py`, `UltraSearchError`, `Run`, `classify.py`, `site/commands.py`, `cli.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `TIMED_OUT`, `batchStart`, `work` to the rest of the system?**
  _103 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_run_directory.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10299003322259136 - nodes in this community are weakly interconnected._
- **Should `research/commands.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1337126600284495 - nodes in this community are weakly interconnected._
- **Should `run_cli` be split into smaller, more focused modules?**
  _Cohesion score 0.0670762928827445 - nodes in this community are weakly interconnected._