# Graph Report - graph-wt  (2026-09-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 810 nodes · 1905 edges · 48 communities (31 shown, 17 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.88)
- Token cost: 45,113 input · 642 output

## Graph Freshness
- Built from commit: `dbd678fd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Aside Transcript Parsing
- Page Acquisition and Saving
- Run Command Dispatch
- Run Directory Tests
- CLI Parser and Process
- Search Run Behavior Tests
- Environment Doctor Tests
- Research Log Tests
- Fake Aside Contract Tests
- Recorded Session Fixtures
- Page Snippet Call Tests
- Exec Polling Fixtures
- Map and Crawl Tests
- Document Conversion Tests
- Fake Aside Binary
- Pytest Configuration Fixtures
- Run Lookup and Resume Tests
- Aside Session Store
- Live End-to-End Tests
- Bot Challenge Detection
- Sitemap Discovery Snippet
- Project Capabilities and Scraping
- Converter Package Dependencies
- Batch Fetch Snippet
- Aside Product Documentation
- Golden Regression Fixtures
- Link Extraction Snippet
- Crawl Output Safeguards
- Harness Spec and Skill
- Markdown Converter Script
- Yonhap News Pages
- Tab Opening Snippet
- Full Text to File
- HTML Format Saving
- Session Transcript File
- Prompt Marker Boundary
- REPL Sandbox Limits
- Run Completion States
- Run Type
- PathLike Type
- Run Type
- Run Type
- Run Type
- Document Type
- Exception Type
- MonkeyPatch Fixture
- Run Type
- X JavaScript Shell

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 44 edges
2. `page()` - 42 edges
3. `item_of()` - 40 edges
4. `search()` - 40 edges
5. `Run` - 34 edges
6. `tool()` - 25 edges
7. `finished_run_id()` - 24 edges
8. `ArgumentError` - 22 edges
9. `run_cli()` - 21 edges
10. `Event` - 20 edges

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

## Communities (48 total, 17 thin omitted)

### Community 0 - "Aside Transcript Parsing"
Cohesion: 0.07
Nodes (56): How ultra-search talks to Aside: its process, its session storage, its…, _as_text(), _assistant(), _count_lines_before(), Event, _flatten_text(), parse_lines(), parse_record() (+48 more)

### Community 1 - "Page Acquisition and Saving"
Cohesion: 0.07
Nodes (57): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., ultra-search: web work through the user's logged-in Aside browser., _chunks(), _escalate(), fetch_urls(), _needs_retry(), Path (+49 more)

### Community 2 - "Run Command Dispatch"
Cohesion: 0.12
Nodes (40): is_safe_id(), _await_and_report(), _await_terminal(), dispatch(), _entry(), _exit_code(), _log(), next_step() (+32 more)

### Community 3 - "Run Directory Tests"
Cohesion: 0.08
Nodes (49): `--timeout` is recorded by the process that starts the run but enforced by the…, fixture, parametrize, Path, The run directory: what a run leaves on disk, and the files three processes…, `status` may read meta.json at any moment. A value that cannot be serialised…, meta.json is written by the starting CLI, the detached supervisor and `stop`,…, Processes, not threads: the lock is a file, and a threads-only test would pass… (+41 more)

### Community 4 - "CLI Parser and Process"
Cohesion: 0.09
Nodes (37): ArgumentParser, _add_exec_opts(), _add_runs_dir(), _add_target(), build_parser(), main(), aside_bin(), daemon_url() (+29 more)

### Community 5 - "Search Run Behavior Tests"
Cohesion: 0.07
Nodes (39): first_run(), `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Checked while the run is going as well as after: the supervisor copies every…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Aside creates the directory before the first message lands, and repl sessions…, The recorded parent spawned three subagents; one of them was still mid-tool… (+31 more)

### Community 6 - "Environment Doctor Tests"
Cohesion: 0.11
Nodes (35): argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), daemon(), doctor(), fixture, MonkeyPatch, parametrize (+27 more)

### Community 7 - "Research Log Tests"
Cohesion: 0.09
Nodes (31): lines_of(), log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, What a command printed before its JSON response, which is always the last line., The members' transcripts differ in length, so one member's position applied to…, A parent investigation goes silent while its subagents work; a watcher that…, Only the event lines of a log: no response, no cursor. (+23 more)

### Community 8 - "Fake Aside Contract Tests"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 9 - "Recorded Session Fixtures"
Cohesion: 0.14
Nodes (30): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), user(), Silence is labelled, never acted on: a slow run and a stuck one look identical…, A URL appears twice: once as a search result's excerpt, once as the page a… (+22 more)

### Community 10 - "Page Snippet Call Tests"
Cohesion: 0.12
Nodes (30): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round…, `--out ./notes` for one URL means a folder to anyone who types it. Producing an… (+22 more)

### Community 11 - "Exec Polling Fixtures"
Cohesion: 0.10
Nodes (28): exec_calls(), The argv of every `aside exec` the CLI started, in order., eventful(), make_state_db(), poll(), fixture, Path, A run recorded on 2026-08-29: a parent that spawned three subagents, one of… (+20 more)

### Community 12 - "Map and Crawl Tests"
Cohesion: 0.10
Nodes (23): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A crawl acts as the user in their own browser. A link that shares only the host…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim… (+15 more)

### Community 13 - "Document Conversion Tests"
Cohesion: 0.13
Nodes (27): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+19 more)

### Community 14 - "Fake Aside Binary"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 15 - "Pytest Configuration Fixtures"
Cohesion: 0.16
Nodes (22): Config, Item, aside_home(), cli(), fake_aside(), fixtures(), fixture, MonkeyPatch (+14 more)

### Community 16 - "Run Lookup and Resume Tests"
Cohesion: 0.10
Nodes (22): finished_run_id(), parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, `result`, `status` and `show` describe the same run. For a resumed run that is…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller…, The transcript a resume appends to already ends in an answer. Until the new one… (+14 more)

### Community 17 - "Aside Session Store"
Cohesion: 0.30
Nodes (17): aside_home(), copy_new_lines(), db_path(), db_session_row(), db_suspension(), find_session_by_marker(), iter_sessions(), last_activity() (+9 more)

### Community 18 - "Live End-to-End Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 19 - "Bot Challenge Detection"
Cohesion: 0.13
Nodes (16): captured(), fetch_without_node(), Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An… (+8 more)

### Community 20 - "Sitemap Discovery Snippet"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 21 - "Project Capabilities and Scraping"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 22 - "Converter Package Dependencies"
Cohesion: 0.18
Nodes (10): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+2 more)

### Community 23 - "Batch Fetch Snippet"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 24 - "Aside Product Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 25 - "Golden Regression Fixtures"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 26 - "Link Extraction Snippet"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 27 - "Crawl Output Safeguards"
Cohesion: 0.25
Nodes (8): parametrize, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, test_a_crawl_never_writes_into_a_folder_that_already_has_files(), test_a_discovery_snippet_cut_off_by_the_repl_limit_is_reported(), test_a_manifest_of_the_wrong_shape_is_refused(), test_an_empty_body_is_not_a_page_that_was_read(), test_file_names_are_readable_and_stable()

### Community 28 - "Harness Spec and Skill"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 29 - "Markdown Converter Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 30 - "Yonhap News Pages"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **43 isolated node(s):** `seen`, `start`, `TIMED_OUT`, `defuddle`, `@firecrawl/anydoc` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 229 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_cli()` connect `Environment Doctor Tests` to `Run Directory Tests`, `Research Log Tests`, `Fake Aside Contract Tests`, `Exec Polling Fixtures`, `Pytest Configuration Fixtures`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `Run` connect `Run Command Dispatch` to `Aside Transcript Parsing`, `Run Directory Tests`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `tool()` connect `Recorded Session Fixtures` to `Run Directory Tests`, `Search Run Behavior Tests`, `Research Log Tests`, `Fake Aside Contract Tests`, `Exec Polling Fixtures`, `Pytest Configuration Fixtures`, `Run Lookup and Resume Tests`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **What connects `seen`, `start`, `TIMED_OUT` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Aside Transcript Parsing` be split into smaller, more focused modules?**
  _Cohesion score 0.06599597585513078 - nodes in this community are weakly interconnected._
- **Should `Page Acquisition and Saving` be split into smaller, more focused modules?**
  _Cohesion score 0.068997668997669 - nodes in this community are weakly interconnected._
- **Should `Run Command Dispatch` be split into smaller, more focused modules?**
  _Cohesion score 0.12156862745098039 - nodes in this community are weakly interconnected._