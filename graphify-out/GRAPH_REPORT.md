# Graph Report - graph-wt  (2026-09-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 910 nodes · 2076 edges · 56 communities (36 shown, 20 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 44 edges (avg confidence: 0.86)
- Token cost: 45,934 input · 711 output

## Graph Freshness
- Built from commit: `d5d2d963`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Aside Test Fixtures
- Aside Process and REPL
- Run Commands Dispatch
- CLI Environment Tests
- Aside Transcript Parsing
- Page Commands Dispatch
- Search Run Tests
- Fake Aside Contract Tests
- Page Fetch Tests
- Document Conversion Tests
- Page Acquisition and Classification
- Run Follow Streaming
- Fake Aside Implementation
- Research Command Tests
- CLI Argument Parser
- Map and Crawl Tests
- CLI Test Fixtures
- Background Search Tests
- Live Aside Tests
- Crawl Manifest Tests
- Aside Session Store
- Run Result Views
- Bot Challenge Detection
- Log Follow Tests
- Sitemap Discovery Snippet
- Project Capabilities Overview
- Converter Package Manifest
- Batch Fetch Snippet
- Aside Product Documentation
- Recorded Investigation Fixtures
- Link Extraction Snippet
- Recorded Run Fixtures
- Harness Spec and Skill
- Run ID Safety Tests
- Markdown Converter Script
- Yonhap News Pages
- Tab Open Snippet
- Fetch Output to File
- HTML Format Saving
- Resumed Child Counting
- Resume Loose Ends
- Session Transcript File
- Prompt Marker Boundary
- REPL Sandbox Limits
- Run Terminal States
- Run Type
- PathLike Type
- Run Type
- Run Type
- PathLike Type
- Run Type
- Document Type
- Exception Type
- MonkeyPatch Type
- Run Type
- X JavaScript Shell

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 45 edges
2. `page()` - 45 edges
3. `search()` - 41 edges
4. `item_of()` - 41 edges
5. `Run` - 35 edges
6. `tool()` - 26 edges
7. `finished_run_id()` - 26 edges
8. `run_cli()` - 25 edges
9. `answer()` - 21 edges
10. `user()` - 20 edges

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

## Communities (56 total, 20 thin omitted)

### Community 0 - "Aside Test Fixtures"
Cohesion: 0.05
Nodes (84): Config, Item, answer(), aside_session(), calling(), pytest_collection_modifyitems(), pytest_configure(), Shared fixtures. Every test that touches the aside side of the world points… (+76 more)

### Community 1 - "Aside Process and REPL"
Cohesion: 0.06
Nodes (51): aside_bin(), daemon_url(), exec_argv(), PathLike, The aside binary: finding it, starting `aside exec`, and where its daemon…, spawn_exec(), version(), parse_ndjson() (+43 more)

### Community 2 - "Run Commands Dispatch"
Cohesion: 0.09
Nodes (50): is_safe_id(), _await_and_report(), _await_terminal(), dispatch(), _entry(), _exit_code(), _log(), next_step() (+42 more)

### Community 3 - "CLI Environment Tests"
Cohesion: 0.07
Nodes (53): argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), cli_with_path(), daemon(), doctor(), help_of(), fixture (+45 more)

### Community 4 - "Aside Transcript Parsing"
Cohesion: 0.08
Nodes (43): How ultra-search talks to Aside: its process, its session storage, its…, _as_text(), _assistant(), _count_lines_before(), Event, _flatten_text(), parse_lines(), parse_record() (+35 more)

### Community 5 - "Page Commands Dispatch"
Cohesion: 0.10
Nodes (36): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., _brief(), _crawl_cmd(), _default_out(), _destinations(), _discovery(), dispatch() (+28 more)

### Community 6 - "Search Run Tests"
Cohesion: 0.09
Nodes (33): first_run(), `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Aside creates the directory before the first message lands, and repl sessions…, `--timeout` is recorded by the process that starts the run but enforced by the…, The recorded parent spawned three subagents; one of them was still mid-tool… (+25 more)

### Community 7 - "Fake Aside Contract Tests"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 8 - "Page Fetch Tests"
Cohesion: 0.12
Nodes (31): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round… (+23 more)

### Community 9 - "Document Conversion Tests"
Cohesion: 0.10
Nodes (31): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+23 more)

### Community 10 - "Page Acquisition and Classification"
Cohesion: 0.16
Nodes (25): _chunks(), _escalate(), fetch_urls(), _needs_retry(), Path, Getting pages, and putting them where they can be read. Two shapes carry most…, _save(), _to_document() (+17 more)

### Community 11 - "Run Follow Streaming"
Cohesion: 0.14
Nodes (23): _drain(), follow(), format_cursor(), _number(), _offset(), parse_since(), Path, Watching a run, and ending the watch in a way the caller can act on. `--follow`… (+15 more)

### Community 12 - "Fake Aside Implementation"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 13 - "Research Command Tests"
Cohesion: 0.11
Nodes (22): log_of(), make_state_db(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, Watching progress must not be a way to load a fetched page into context by…, Less is the means, not the rule: a failed tool and a finished child are exactly…, The transcript is another product's private surface. A call whose arguments are…, An unfamiliar block is still work that happened, and text beside an unfamiliar… (+14 more)

### Community 14 - "CLI Argument Parser"
Cohesion: 0.16
Nodes (21): ArgumentParser, _add_discovery_opts(), _add_exec_opts(), _add_fetch_opts(), _add_runs_dir(), _add_target(), _add_wait_opts(), build_parser() (+13 more)

### Community 15 - "Map and Crawl Tests"
Cohesion: 0.12
Nodes (21): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, A site that refuses most of its pages would otherwise answer with a list the…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., test_a_cycle_does_not_revisit() (+13 more)

### Community 16 - "CLI Test Fixtures"
Cohesion: 0.17
Nodes (20): FixtureRequest, aside_home(), cli(), fake_aside(), fixtures(), no_real_aside(), fixture, MonkeyPatch (+12 more)

### Community 17 - "Background Search Tests"
Cohesion: 0.13
Nodes (20): exec_calls(), The argv of every `aside exec` the CLI started, in order., Path, `stop` ends the watching, not the daemon's turn. Resuming the run it abandoned…, The browsing agent acts as the user, in their logged-in browser. What research…, The failure this prevents: a caller starts work in the background and simply…, Aside never says which session it created. The marker is how the run finds its…, The capability this is for: a conversation started in the Aside app, or by a… (+12 more)

### Community 18 - "Live Aside Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 19 - "Crawl Manifest Tests"
Cohesion: 0.11
Nodes (19): listed(), parametrize, Every URL a map found: its manifest holds the full list, not its reply., A crawl acts as the user in their own browser. A link that shares only the host…, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim…, With --from nothing is discovered, so a discovery flag would silently do… (+11 more)

### Community 20 - "Aside Session Store"
Cohesion: 0.31
Nodes (16): aside_home(), copy_new_lines(), db_path(), db_session_row(), db_suspension(), find_session_by_marker(), iter_sessions(), last_activity() (+8 more)

### Community 21 - "Run Result Views"
Cohesion: 0.12
Nodes (17): finished_run_id(), `result`, `status` and `show` describe the same run. For a resumed run that is…, One shape whether one run or a group was asked for -- the shape `search` and…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller…, The transcript a resume appends to already ends in an answer. Until the new one…, test_a_resumed_run_reports_the_new_answer_not_the_previous_one(), test_a_run_that_does_not_exist_is_refused_not_guessed() (+9 more)

### Community 22 - "Bot Challenge Detection"
Cohesion: 0.14
Nodes (15): captured(), fetch_without_node(), x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An…, test_a_bot_challenge_is_not_reported_as_the_page() (+7 more)

### Community 23 - "Log Follow Tests"
Cohesion: 0.13
Nodes (15): lines_of(), Distinct from a terminal line on purpose: the caller has to be able to tell "it…, What a command printed before its JSON response, which is always the last line., The members' transcripts differ in length, so one member's position applied to…, A parent investigation goes silent while its subagents work; a watcher that…, Only the event lines of a log: no response, no cursor., rendered(), test_a_follow_that_runs_out_of_time_says_the_run_is_still_going() (+7 more)

### Community 24 - "Sitemap Discovery Snippet"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 25 - "Project Capabilities Overview"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 26 - "Converter Package Manifest"
Cohesion: 0.18
Nodes (10): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+2 more)

### Community 27 - "Batch Fetch Snippet"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 28 - "Aside Product Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 29 - "Recorded Investigation Fixtures"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 30 - "Link Extraction Snippet"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 31 - "Recorded Run Fixtures"
Cohesion: 0.32
Nodes (8): eventful(), fixture, A run recorded on 2026-08-29: a parent that spawned three subagents, one of…, The recorded session of a real search: one websearch, one cited answer., A run whose transcript holds every kind of event the log has to render., recorded(), simple_search(), start_isolated()

### Community 32 - "Harness Spec and Skill"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 33 - "Run ID Safety Tests"
Cohesion: 0.29
Nodes (7): parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, test_a_cursor_that_is_not_one_is_refused_rather_than_replayed(), test_a_run_id_that_names_a_path_outside_the_registry_is_refused(), test_next_commands_preserve_the_installed_path_and_run_store(), test_terminal_log_and_result_preserve_failure_and_incompleteness()

### Community 34 - "Markdown Converter Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 35 - "Yonhap News Pages"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **43 isolated node(s):** `seen`, `start`, `TIMED_OUT`, `defuddle`, `@firecrawl/anydoc` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 284 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_cli()` connect `CLI Environment Tests` to `Aside Test Fixtures`, `Fake Aside Contract Tests`, `Research Command Tests`, `CLI Test Fixtures`, `Background Search Tests`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `Run` connect `Run Commands Dispatch` to `Aside Test Fixtures`, `Run Follow Streaming`, `Aside Transcript Parsing`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `_doctor()` connect `Aside Process and REPL` to `CLI Test Fixtures`, `Run Commands Dispatch`, `Aside Session Store`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **What connects `seen`, `start`, `TIMED_OUT` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Aside Test Fixtures` be split into smaller, more focused modules?**
  _Cohesion score 0.05399625768511093 - nodes in this community are weakly interconnected._
- **Should `Aside Process and REPL` be split into smaller, more focused modules?**
  _Cohesion score 0.06393442622950819 - nodes in this community are weakly interconnected._
- **Should `Run Commands Dispatch` be split into smaller, more focused modules?**
  _Cohesion score 0.0907103825136612 - nodes in this community are weakly interconnected._