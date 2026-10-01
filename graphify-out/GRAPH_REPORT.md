# Graph Report - wt-main  (2026-10-02)

## Corpus Check
- 42 files · ~92,028 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: .jsonl 9, (none) 2, .csv 1)

## Summary
- 989 nodes · 2190 edges · 49 communities (45 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 42 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `33a02d15`
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
- finished_run_id
- captured
- tool
- sitemap.js
- Ultra-Search Project
- package.json
- fetch_batch.js
- Aside Developer Tools
- Recorded parent investigation waits for three release summaries
- links.js
- eventful
- Ultra-Search skill
- evidence.py
- discover.py
- Yonhap News Portal
- tab_one.js
- test_the_full_text_goes_to_a_file_not_into_the_reply
- test_a_file_that_was_written_counts_as_success
- browser.py
- turn_of
- Source
- ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)
- Context
- transcript.py
- Event
- acquire.py
- `follow`를 감독자 뷰로 — `log --level progress`
- X JavaScript-Disabled Shell

## God Nodes (most connected - your core abstractions)
1. `page()` - 45 edges
2. `first_run()` - 45 edges
3. `item_of()` - 41 edges
4. `search()` - 41 edges
5. `Run` - 35 edges
6. `tool()` - 26 edges
7. `finished_run_id()` - 26 edges
8. `run_cli()` - 25 edges
9. `ArgumentError` - 23 edges
10. `answer()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `_doctor()` --indirect_call--> `runs_dir()`  [INFERRED]
  .claude/skills/ultra-search/scripts/ultra_search/doctor.py → tests/conftest.py
- `result_of()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/ultra_search/runs/registry.py
- `resumed()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/ultra_search/runs/registry.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (49 total, 4 thin omitted)

### Community 0 - "test_run_directory.py"
Cohesion: 0.08
Nodes (49): fixture, parametrize, Path, The run directory: what a run leaves on disk, and the files three processes…, `--timeout` is recorded by the process that starts the run but enforced by the…, `status` may read meta.json at any moment. A value that cannot be serialised…, meta.json is written by the starting CLI, the detached supervisor and `stop`,…, Processes, not threads: the lock is a file, and a threads-only test would pass… (+41 more)

### Community 1 - "doctor.py"
Cohesion: 0.05
Nodes (64): ArgumentParser, _add_discovery_opts(), _add_exec_opts(), _add_fetch_opts(), _add_runs_dir(), _add_target(), _add_wait_opts(), build_parser() (+56 more)

### Community 2 - "runs/commands.py"
Cohesion: 0.10
Nodes (48): is_safe_id(), _await_and_report(), _await_terminal(), dispatch(), _entry(), _exit_code(), _log(), next_step() (+40 more)

### Community 3 - "test_environment.py"
Cohesion: 0.07
Nodes (53): argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), cli_with_path(), daemon(), doctor(), help_of(), fixture (+45 more)

### Community 4 - "supervisor.py"
Cohesion: 0.18
Nodes (15): decorate_prompt(), Append the research scope and the correlation marker to a prompt. Aside's CLI…, _abandon(), _activity(), main(), Path, PathLike, The state machine that turns a running `aside exec` into a result on disk.… (+7 more)

### Community 5 - "pages/commands.py"
Cohesion: 0.17
Nodes (24): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., _brief(), _crawl_cmd(), _default_out(), _destinations(), _discovery(), dispatch() (+16 more)

### Community 6 - "first_run"
Cohesion: 0.08
Nodes (38): first_run(), `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Checked while the run is going as well as after: the supervisor copies every…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Aside creates the directory before the first message lands, and repl sessions…, `--timeout` is recorded by the process that starts the run but enforced by the… (+30 more)

### Community 7 - "test_contract_fake_aside.py"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 8 - "page"
Cohesion: 0.12
Nodes (31): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round… (+23 more)

### Community 9 - "item_of"
Cohesion: 0.10
Nodes (31): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+23 more)

### Community 10 - "classify.py"
Cohesion: 0.20
Nodes (20): _escalate(), Re-fetch through a real browser tab. Worth trying for both a client-rendered…, classify_response(), count_words(), Document, extract_document(), extract_html(), _first_heading() (+12 more)

### Community 11 - "follow.py"
Cohesion: 0.18
Nodes (14): _drain(), follow(), format_cursor(), _live_children(), _number(), _offset(), parse_since(), Path (+6 more)

### Community 12 - "aside"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 13 - "test_research.py"
Cohesion: 0.09
Nodes (31): lines_of(), log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, What a command printed before its JSON response, which is always the last line., The members' transcripts differ in length, so one member's position applied to…, A parent investigation goes silent while its subagents work; a watcher that…, Only the event lines of a log: no response, no cursor. (+23 more)

### Community 14 - "ultra-search 스킬 구현 계획"
Cohesion: 0.10
Nodes (20): aside CLI (1.26.810.1915, 데몬 1.26.827.1029, `~/.local/bin/aside`), codex 스킬의 구조적 선례 (`~/.claude/skills/codex`), Context (목적과 요약), crawl4ai (v1 제외의 근거), exec (`scratchpad/exec_probe.py`, `subagent_probe.py`, `--effort` 비교, kill 실험), PDF·오피스 문서 변환 — anydoc (`.tmp/anydoc`, `scratchpad/anydoc-test/`), repl (`aside repl "…"` 실측 다수), ultra-search 스킬 구현 계획 (+12 more)

### Community 15 - "test_pages.py"
Cohesion: 0.12
Nodes (21): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, A site that refuses most of its pages would otherwise answer with a list the…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., test_a_cycle_does_not_revisit() (+13 more)

### Community 16 - "conftest.py"
Cohesion: 0.14
Nodes (25): Config, FixtureRequest, Item, aside_home(), cli(), fake_aside(), fixtures(), no_real_aside() (+17 more)

### Community 17 - "Path"
Cohesion: 0.11
Nodes (24): exec_calls(), The argv of every `aside exec` the CLI started, in order., make_state_db(), poll(), Path, `stop` ends the watching, not the daemon's turn. Resuming the run it abandoned…, The browsing agent acts as the user, in their logged-in browser. What research…, The failure this prevents: a caller starts work in the background and simply… (+16 more)

### Community 18 - "test_live.py"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 19 - "listed"
Cohesion: 0.11
Nodes (19): listed(), parametrize, Every URL a map found: its manifest holds the full list, not its reply., A crawl acts as the user in their own browser. A link that shares only the host…, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim…, With --from nothing is discovered, so a discovery flag would silently do… (+11 more)

### Community 20 - "sessions.py"
Cohesion: 0.17
Nodes (25): aside_home(), copy_new_lines(), db_path(), db_session_row(), db_suspension(), find_session_by_marker(), iter_sessions(), last_activity() (+17 more)

### Community 21 - "finished_run_id"
Cohesion: 0.09
Nodes (24): finished_run_id(), parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, `result`, `status` and `show` describe the same run. For a resumed run that is…, One shape whether one run or a group was asked for -- the shape `search` and…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller… (+16 more)

### Community 22 - "captured"
Cohesion: 0.14
Nodes (15): captured(), fetch_without_node(), x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An…, test_a_bot_challenge_is_not_reported_as_the_page() (+7 more)

### Community 23 - "tool"
Cohesion: 0.13
Nodes (32): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), user(), Silence is labelled, never acted on: a slow run and a stuck one look identical…, A URL appears twice: once as a search result's excerpt, once as the page a… (+24 more)

### Community 24 - "sitemap.js"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 25 - "Ultra-Search Project"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 26 - "package.json"
Cohesion: 0.13
Nodes (15): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+7 more)

### Community 27 - "fetch_batch.js"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 28 - "Aside Developer Tools"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 29 - "Recorded parent investigation waits for three release summaries"
Cohesion: 0.33
Nodes (7): Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 30 - "links.js"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 31 - "eventful"
Cohesion: 0.32
Nodes (8): eventful(), fixture, A run recorded on 2026-08-29: a parent that spawned three subagents, one of…, The recorded session of a real search: one websearch, one cited answer., A run whose transcript holds every kind of event the log has to render., recorded(), simple_search(), start_isolated()

### Community 32 - "Ultra-Search skill"
Cohesion: 0.50
Nodes (4): Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 33 - "evidence.py"
Cohesion: 0.12
Nodes (12): How ultra-search talks to Aside: its process, its session storage, its…, child_is_terminal(), _from(), has_terminal_answer(), is_opening_tool(), What one run found: its own turn of the session, that turn's children, and…, Whether an assistant turn has finished here, as opposed to stopping to call a…, Whether this tool's result means the agent read the page rather than just… (+4 more)

### Community 34 - "discover.py"
Cohesion: 0.17
Nodes (14): build_manifest(), _dedupe(), discover(), matches(), normalise(), origin(), Choosing which URLs a crawl will visit. Pure: URLs and two discovery providers…, The record of what a crawl or map found. `map` writes one with urls and no… (+6 more)

### Community 35 - "Yonhap News Portal"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

### Community 39 - "browser.py"
Cohesion: 0.21
Nodes (13): build_code(), _decode_attribute(), fetch_batch(), links(), load_snippet(), The page snippets: fetching, opening a tab, reading sitemaps and links, in the…, Fetch a batch; non-text responses are written to the browser session directory.…, Same-origin links from a set of pages. The snippet returns raw href strings;… (+5 more)

### Community 40 - "turn_of"
Cohesion: 0.16
Nodes (12): child_session_ids(), Index of the user message that began this run's turn, or None if it is not…, Child sessions spawned by this run, in spawn order. Read from the parent's own…, This turn's own tool results, in order -- what `show --item N` counts., total_usage(), Turn, turn_of(), turn_start_index() (+4 more)

### Community 41 - "Source"
Cohesion: 0.21
Nodes (10): collect_sources(), final_answer(), merge_sources(), Several streams' sources as one list, one entry per URL, first seen first. A…, Every URL the turn and its children touched, one entry per URL., The turn's answer, each child's appended under its id. Citations resolve…, The text of the last finished assistant turn, with citation tags resolved to…, Every URL the run touched, in order, deduplicated by URL. ``opened`` separates… (+2 more)

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
Cohesion: 0.39
Nodes (11): Event, _assistant(), _clip(), _first_line(), _progress(), One transcript event, as the line a reader can act on. Which line an event…, ``webfetch×4[nodejs.org] read_file×2`` -- tools in first-use order, each with…, _reached_for() (+3 more)

### Community 46 - "acquire.py"
Cohesion: 0.27
Nodes (10): _chunks(), fetch_urls(), _needs_retry(), Path, Getting pages, and putting them where they can be read. Two shapes carry most…, _save(), _to_document(), _unique_path() (+2 more)

### Community 47 - "`follow`를 감독자 뷰로 — `log --level progress`"
Cohesion: 0.18
Nodes (10): `follow`를 감독자 뷰로 — `log --level progress`, 검증 시나리오, 단계·의존·완료 판정, 리스크·가정·비차단 유예, 목적과 요약, 범위·비범위·제약, 성공 기준, 인터페이스·산출물 (+2 more)

## Knowledge Gaps
- **85 isolated node(s):** `name`, `version`, `private`, `type`, `description` (+80 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 359 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_cli()` connect `test_environment.py` to `test_run_directory.py`, `test_contract_fake_aside.py`, `test_research.py`, `conftest.py`, `Path`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `Run` connect `runs/commands.py` to `turn_of`, `test_run_directory.py`, `follow.py`, `supervisor.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `_doctor()` connect `doctor.py` to `conftest.py`, `runs/commands.py`, `sessions.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _85 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_run_directory.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08078431372549019 - nodes in this community are weakly interconnected._
- **Should `doctor.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05403508771929825 - nodes in this community are weakly interconnected._
- **Should `runs/commands.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09526592635885447 - nodes in this community are weakly interconnected._