# Graph Report - graph-wt  (2026-09-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 872 nodes · 1909 edges · 49 communities (32 shown, 17 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 144 edges (avg confidence: 0.86)
- Token cost: 45,189 input · 608 output

## Graph Freshness
- Built from commit: `b4af13f8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Run Log Following
- CLI Contract and Doctor
- Transcript Event Parsing
- Run Directory Tests
- Map and Crawl Commands
- Aside Session Store
- Search Run Lifecycle
- CLI Environment Tests
- Research Command Tests
- Fake Aside Contract Tests
- Session Transcript Fixtures
- Page Snippet Call Tests
- Recorded Run Fixtures
- Site Map Crawl Tests
- Document Format Handling
- Fake Aside Binary
- Test Fixtures Setup
- Run ID and Cursor Validation
- Live Aside End-to-End
- Crawl URL Selection
- Bot Challenge Detection
- Node Package Dependencies
- Sitemap Discovery Script
- Project Capabilities Overview
- Batch Page Fetch Script
- Aside Product Documentation
- Golden Regression Fixtures
- Link Extraction Script
- Crawl Output Safety Tests
- Harness Spec and Skill
- Markdown Conversion Script
- Yonhap News Samples
- Tab Opening Script
- Full Text to File
- HTML Format Saving
- Session Transcript File
- Prompt Marker Correlation
- REPL Sandbox Limits
- Run Terminal States
- Run
- PathLike
- Run
- Run
- Run
- Document
- Exception
- Run
- X JavaScript Shell Page
- MonkeyPatch

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 44 edges
2. `page()` - 42 edges
3. `item_of()` - 40 edges
4. `search()` - 40 edges
5. `Run` - 34 edges
6. `finished_run_id()` - 24 edges
7. `tool()` - 23 edges
8. `ArgumentError` - 22 edges
9. `Event` - 20 edges
10. `answer()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `_doctor()` --indirect_call--> `runs_dir()`  [INFERRED]
  .claude/skills/ultra-search/scripts/_doctor.py → tests/conftest.py
- `result_of()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/_registry.py
- `resumed()` --references--> `Run`  [EXTRACTED]
  tests/test_run_directory.py → .claude/skills/ultra-search/scripts/_registry.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (49 total, 17 thin omitted)

### Community 0 - "Run Log Following"
Cohesion: 0.07
Nodes (66): ArgumentError, is_safe_id(), _drain(), follow(), format_cursor(), _live_children(), _offset(), parse_since() (+58 more)

### Community 1 - "CLI Contract and Doctor"
Cohesion: 0.06
Nodes (57): ArgumentParser, AsideUnavailable, Exception, The CLI's contract: exit codes, run states, errors, and what an id may be.…, RunFailed, UltraSearchError, _account_status(), _check() (+49 more)

### Community 2 - "Transcript Event Parsing"
Cohesion: 0.06
Nodes (53): _as_text(), _assistant(), child_session_ids(), collect_sources(), _count_lines_before(), Event, final_answer(), _flatten_text() (+45 more)

### Community 3 - "Run Directory Tests"
Cohesion: 0.08
Nodes (49): `--timeout` is recorded by the process that starts the run but enforced by the…, fixture, parametrize, Path, The run directory: what a run leaves on disk, and the files three processes…, Mid-tool means still working, and a user turn after a finished answer means a…, `status` may read meta.json at any moment. A value that cannot be serialised…, meta.json is written by the starting CLI, the detached supervisor and `stop`,… (+41 more)

### Community 4 - "Map and Crawl Commands"
Cohesion: 0.09
Nodes (45): _crawl_cmd(), _default_out(), dispatch(), _map(), _providers(), Path, `map` and `crawl`. `map` is the cheap half: it discovers URLs and writes a…, A crawl's numbered names repeat from one crawl to the next, so a folder that… (+37 more)

### Community 5 - "Aside Session Store"
Cohesion: 0.11
Nodes (36): decorate_prompt(), Append the correlation marker to a prompt. Aside's CLI never reports which…, aside_home(), copy_new_lines(), db_path(), db_session_row(), db_suspension(), find_session_by_marker() (+28 more)

### Community 6 - "Search Run Lifecycle"
Cohesion: 0.07
Nodes (39): first_run(), `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Checked while the run is going as well as after: the supervisor copies every…, Run ids are timestamps and a group starts every member inside the same second,…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Aside creates the directory before the first message lands, and repl sessions…, The recorded parent spawned three subagents; one of them was still mid-tool… (+31 more)

### Community 7 - "CLI Environment Tests"
Cohesion: 0.11
Nodes (35): MonkeyPatch, argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), daemon(), doctor(), fixture, parametrize (+27 more)

### Community 8 - "Research Command Tests"
Cohesion: 0.09
Nodes (31): lines_of(), log_of(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, What a command printed before its JSON response, which is always the last line., The members' transcripts differ in length, so one member's position applied to…, A parent investigation goes silent while its subagents work; a watcher that…, Only the event lines of a log: no response, no cursor. (+23 more)

### Community 9 - "Fake Aside Contract Tests"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 10 - "Session Transcript Fixtures"
Cohesion: 0.14
Nodes (30): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), user(), Silence is labelled, never acted on: a slow run and a stuck one look identical…, A URL appears twice: once as a search result's excerpt, once as the page a… (+22 more)

### Community 11 - "Page Snippet Call Tests"
Cohesion: 0.12
Nodes (30): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round…, `--out ./notes` for one URL means a folder to anyone who types it. Producing an… (+22 more)

### Community 12 - "Recorded Run Fixtures"
Cohesion: 0.10
Nodes (28): exec_calls(), The argv of every `aside exec` the CLI started, in order., eventful(), make_state_db(), poll(), fixture, Path, A run recorded on 2026-08-29: a parent that spawned three subagents, one of… (+20 more)

### Community 13 - "Site Map Crawl Tests"
Cohesion: 0.10
Nodes (23): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A crawl acts as the user in their own browser. A link that shares only the host…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim… (+15 more)

### Community 14 - "Document Format Handling"
Cohesion: 0.13
Nodes (27): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+19 more)

### Community 15 - "Fake Aside Binary"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 16 - "Test Fixtures Setup"
Cohesion: 0.16
Nodes (22): Config, Item, aside_home(), cli(), fake_aside(), fixtures(), fixture, MonkeyPatch (+14 more)

### Community 17 - "Run ID and Cursor Validation"
Cohesion: 0.10
Nodes (22): finished_run_id(), parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, `result`, `status` and `show` describe the same run. For a resumed run that is…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller…, The transcript a resume appends to already ends in an answer. Until the new one… (+14 more)

### Community 18 - "Live Aside End-to-End"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 19 - "Crawl URL Selection"
Cohesion: 0.17
Nodes (14): build_manifest(), _dedupe(), discover(), matches(), normalise(), origin(), Choosing which URLs a crawl will visit. Pure: URLs and two discovery providers…, The record of what a crawl or map found. `map` writes one with urls and no… (+6 more)

### Community 20 - "Bot Challenge Detection"
Cohesion: 0.13
Nodes (16): captured(), fetch_without_node(), Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An… (+8 more)

### Community 21 - "Node Package Dependencies"
Cohesion: 0.15
Nodes (12): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+4 more)

### Community 22 - "Sitemap Discovery Script"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 23 - "Project Capabilities Overview"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 24 - "Batch Page Fetch Script"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 25 - "Aside Product Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 26 - "Golden Regression Fixtures"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 27 - "Link Extraction Script"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 28 - "Crawl Output Safety Tests"
Cohesion: 0.25
Nodes (8): parametrize, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, test_a_crawl_never_writes_into_a_folder_that_already_has_files(), test_a_discovery_snippet_cut_off_by_the_repl_limit_is_reported(), test_a_manifest_of_the_wrong_shape_is_refused(), test_an_empty_body_is_not_a_page_that_was_read(), test_file_names_are_readable_and_stable()

### Community 29 - "Harness Spec and Skill"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 30 - "Markdown Conversion Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 31 - "Yonhap News Samples"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **42 isolated node(s):** `description`, `name`, `private`, `type`, `version` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 290 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Run` connect `Run Log Following` to `Transcript Event Parsing`, `Run Directory Tests`, `Aside Session Store`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `ArgumentError` connect `Run Log Following` to `CLI Contract and Doctor`, `Map and Crawl Commands`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `_doctor()` connect `CLI Contract and Doctor` to `Run Log Following`, `Test Fixtures Setup`, `Aside Session Store`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `description`, `name`, `private` to the rest of the system?**
  _42 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Run Log Following` be split into smaller, more focused modules?**
  _Cohesion score 0.0670886075949367 - nodes in this community are weakly interconnected._
- **Should `CLI Contract and Doctor` be split into smaller, more focused modules?**
  _Cohesion score 0.0574400723654455 - nodes in this community are weakly interconnected._
- **Should `Transcript Event Parsing` be split into smaller, more focused modules?**
  _Cohesion score 0.05837173579109063 - nodes in this community are weakly interconnected._