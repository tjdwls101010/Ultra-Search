# Graph Report - graph-wt  (2026-09-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 746 nodes · 1635 edges · 39 communities (31 shown, 8 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 39 edges (avg confidence: 0.88)
- Token cost: 44,238 input · 511 output

## Graph Freshness
- Built from commit: `a16ed2b9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Page Fetch Tests
- Transcript Event Parsing
- Doctor and Setup Commands
- Run Command Execution
- Run Registry Storage
- Research Command Tests
- Environment Check Tests
- Fake Aside Contract Tests
- Run Directory Tests
- Aside Session Store
- Fake Aside Binary
- Search Outcome Tests
- Test Fixtures Setup
- Session Transcript Tests
- Map and Crawl Commands
- Document Extraction
- Live End-to-End Tests
- Page Fetch Commands
- Aside Exec Invocation Tests
- Node Package Manifest
- Project Capabilities Overview
- Batch Fetch Script
- Sitemap Discovery Script
- Aside Product Documentation
- Golden Regression Fixtures
- Link Extraction Script
- Recorded Session Fixtures
- Harness Specification
- Markdown Conversion Script
- Group Log Cursor
- Yonhap News Pages
- Tab Cleanup Script
- Single Tab Script
- Session Transcript File
- Prompt Marker Boundary
- REPL Sandbox Constraints
- Run Terminal States
- Exception Base
- X JavaScript Shell

## God Nodes (most connected - your core abstractions)
1. `item_of()` - 37 edges
2. `page()` - 37 edges
3. `first_run()` - 37 edges
4. `search()` - 36 edges
5. `finished_run_id()` - 19 edges
6. `Event` - 18 edges
7. `ArgumentError` - 18 edges
8. `run_cli()` - 18 edges
9. `repl_calls()` - 16 edges
10. `Run` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `_doctor()` --indirect_call--> `runs_dir()`  [INFERRED]
  .claude/skills/ultra-search/scripts/_doctor.py → tests/conftest.py
- `Example Domain` --conceptually_related_to--> `Cloudflare Human Verification Challenge`  [INFERRED]
  tests/fixtures/docs/sample_en.pdf → tests/fixtures/html/challenge.html
- `Offline, live, concurrency, and golden regression validation` --conceptually_related_to--> `Steps golden fixture for a three-subagent investigation`  [INFERRED]
  .claude/harness-spec.md → tests/fixtures/runs/260829-235523-subagents/steps.golden.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (39 total, 8 thin omitted)

### Community 0 - "Page Fetch Tests"
Cohesion: 0.08
Nodes (75): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), captured(), document(), fetch_without_node(), frontmatter(), item_of(), mapped() (+67 more)

### Community 1 - "Transcript Event Parsing"
Cohesion: 0.06
Nodes (65): _as_text(), _assistant(), child_session_ids(), collect_sources(), _count_lines_before(), Event, final_answer(), _flatten_text() (+57 more)

### Community 2 - "Doctor and Setup Commands"
Cohesion: 0.05
Nodes (58): ArgumentParser, _account_status(), _check(), _daemon_status(), daemon_url(), dispatch(), _doctor(), Path (+50 more)

### Community 3 - "Run Command Execution"
Cohesion: 0.12
Nodes (36): A run ended without a usable answer, or was abandoned while still going., RunFailed, is_opening_tool(), Whether this tool's result means the agent read the page rather than just…, _await_and_report(), dispatch(), _entry(), _exit_code() (+28 more)

### Community 4 - "Run Registry Storage"
Cohesion: 0.13
Nodes (25): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., all_runs(), _atomic_write_json(), create_run(), decorate_prompt(), default_runs_dir(), latest_group() (+17 more)

### Community 5 - "Research Command Tests"
Cohesion: 0.10
Nodes (32): finished_run_id(), lines_of(), log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, What a command printed before its JSON response, which is always the last line., A parent investigation goes silent while its subagents work; a watcher that…, test_a_follow_that_runs_out_of_time_says_the_run_is_still_going() (+24 more)

### Community 6 - "Environment Check Tests"
Cohesion: 0.12
Nodes (31): argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), daemon(), doctor(), fixture, MonkeyPatch, parametrize (+23 more)

### Community 7 - "Fake Aside Contract Tests"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 8 - "Run Directory Tests"
Cohesion: 0.13
Nodes (30): Run, fixture, Path, The run directory: what a run leaves on disk, and the files three processes…, `status` may read meta.json at any moment. A value that cannot be serialised…, A group starts every member at once. Reserving the directory with O_EXCL is…, A line still being written is not yet a record; consuming it would store a…, Aside cleans up sessions on its own schedule. The copy is then the only… (+22 more)

### Community 9 - "Aside Session Store"
Cohesion: 0.17
Nodes (25): aside_home(), copy_new_lines(), db_child_rows(), db_finished_at(), db_path(), db_session_row(), db_suspension(), find_session_by_marker() (+17 more)

### Community 10 - "Fake Aside Binary"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 11 - "Search Outcome Tests"
Cohesion: 0.12
Nodes (25): first_run(), Run ids are timestamps and a group starts every member inside the same second,…, The recorded parent spawned three subagents; one of them was still mid-tool…, The transcript is another product's private surface. An unknown role survives…, search(), test_a_child_still_running_when_the_parent_exits_is_named(), test_a_failed_run_exits_four(), test_a_finished_search_does_not_hand_back_a_next_step() (+17 more)

### Community 12 - "Test Fixtures Setup"
Cohesion: 0.16
Nodes (22): Config, Item, aside_home(), cli(), fake_aside(), fixtures(), fixture, MonkeyPatch (+14 more)

### Community 13 - "Session Transcript Tests"
Cohesion: 0.20
Nodes (22): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), user(), poll(), Silence is labelled, never acted on: a slow run and a stuck one look identical… (+14 more)

### Community 14 - "Map and Crawl Commands"
Cohesion: 0.16
Nodes (18): build_manifest(), _crawl_cmd(), _default_out(), dispatch(), _map(), _number_files(), _providers(), Path (+10 more)

### Community 15 - "Document Extraction"
Cohesion: 0.20
Nodes (18): classify_response(), count_words(), Document, extract_document(), extract_html(), _first_heading(), _has_strong_challenge_marker(), _is_document_type() (+10 more)

### Community 16 - "Live End-to-End Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 17 - "Page Fetch Commands"
Cohesion: 0.23
Nodes (16): _chunks(), _destinations(), dispatch(), _escalate(), exit_code_for(), _fetch_cmd(), fetch_urls(), _needs_retry() (+8 more)

### Community 18 - "Aside Exec Invocation Tests"
Cohesion: 0.15
Nodes (17): exec_calls(), The argv of every `aside exec` the CLI started, in order., make_state_db(), parametrize, Path, Aside never says which session it created. The marker is how the run finds its…, test_a_database_without_the_expected_tables_is_ignored(), test_a_label_names_the_run_and_cannot_escape_the_registry() (+9 more)

### Community 19 - "Node Package Manifest"
Cohesion: 0.15
Nodes (12): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+4 more)

### Community 20 - "Project Capabilities Overview"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 21 - "Batch Fetch Script"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 22 - "Sitemap Discovery Script"
Cohesion: 0.24
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 23 - "Aside Product Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 24 - "Golden Regression Fixtures"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 25 - "Link Extraction Script"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 26 - "Recorded Session Fixtures"
Cohesion: 0.32
Nodes (8): eventful(), fixture, A run recorded on 2026-08-29: a parent that spawned three subagents, one of…, The recorded session of a real search: one websearch, one cited answer., A run whose transcript holds every kind of event the log has to render., recorded(), simple_search(), start_isolated()

### Community 27 - "Harness Specification"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 28 - "Markdown Conversion Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 29 - "Group Log Cursor"
Cohesion: 0.50
Nodes (4): The members' transcripts differ in length, so one member's position applied to…, Only the event lines of a log: no response, no cursor., rendered(), test_a_group_cursor_round_trips_per_member()

### Community 30 - "Yonhap News Pages"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **43 isolated node(s):** `description`, `name`, `private`, `type`, `version` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 204 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `tool()` connect `Session Transcript Tests` to `Research Command Tests`, `Fake Aside Contract Tests`, `Run Directory Tests`, `Test Fixtures Setup`, `Recorded Session Fixtures`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `UltraSearchError` connect `Doctor and Setup Commands` to `Run Command Execution`, `Run Registry Storage`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `ArgumentError` connect `Run Registry Storage` to `Page Fetch Commands`, `Doctor and Setup Commands`, `Run Command Execution`, `Map and Crawl Commands`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **What connects `description`, `name`, `private` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Page Fetch Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.08140350877192983 - nodes in this community are weakly interconnected._
- **Should `Transcript Event Parsing` be split into smaller, more focused modules?**
  _Cohesion score 0.06116700201207243 - nodes in this community are weakly interconnected._
- **Should `Doctor and Setup Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.052917232021709636 - nodes in this community are weakly interconnected._