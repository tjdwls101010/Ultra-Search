# Graph Report - Ultra-Search  (2026-09-16)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 762 nodes · 1606 edges · 37 communities (29 shown, 8 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 61 edges (avg confidence: 0.87)
- Token cost: 36,207 input · 369 output

## Community Hubs (Navigation)
- Session Event Parsing
- Environment Setup and Diagnostics
- CLI Command Integration Tests
- Run Progress Watcher Tests
- Site Mapping and Crawling
- Background Run Supervisor Tests
- Run Commands and Reporting
- Page Fetch Orchestration Tests
- Run Registry and Metadata
- Document Classification and Extraction
- Document Extraction Tests
- Session Storage and Discovery
- Run Registry Concurrency Tests
- Session Storage Recovery Tests
- Session Event Parsing Tests
- Browser Simulator Contract Tests
- Live Browser Integration Tests
- Shared Test Fixtures
- Aside CLI Simulator
- Document Processing Dependencies
- Web Acquisition Capabilities
- Batch Page Fetching
- Sitemap URL Discovery
- Aside Platform Documentation
- Recorded Investigation Regression Fixtures
- Page Link Discovery
- Search Harness Operating Contracts
- Markdown Conversion
- Yonhap News Examples
- Browser Tab Cleanup
- Rendered Page Fetching
- Authoritative Session Transcript
- Run and Turn Correlation
- Browser Sandbox Restrictions
- Incomplete Run Outcome States
- Exception Handling
- X JavaScript Requirement

## God Nodes (most connected - your core abstractions)
1. `start()` - 27 edges
2. `cli()` - 23 edges
3. `make_run()` - 23 edges
4. `write_transcript()` - 23 edges
5. `ArgumentError` - 22 edges
6. `capture()` - 22 edges
7. `provider()` - 21 edges
8. `run_cli()` - 20 edges
9. `user()` - 20 edges
10. `Event` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html
- `test_several_urls_cannot_share_one_output_file()` --uses--> `ArgumentError`  [INFERRED]
  tests/test_page.py → .claude/skills/ultra-search/scripts/_errors.py
- `test_asking_for_a_run_that_does_not_exist_is_refused_not_guessed()` --uses--> `ArgumentError`  [INFERRED]
  tests/test_registry.py → .claude/skills/ultra-search/scripts/_errors.py
- `test_the_latest_run_of_an_empty_registry_is_refused()` --uses--> `ArgumentError`  [INFERRED]
  tests/test_registry.py → .claude/skills/ultra-search/scripts/_errors.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three parallel official-source investigations joined before synthesis** — tests_fixtures_runs_260829_235523_subagents_steps_golden_parent_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_python_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_node_investigation, tests_fixtures_runs_260829_235523_subagents_steps_golden_go_investigation [EXTRACTED 1.00]
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (37 total, 8 thin omitted)

### Community 0 - "Session Event Parsing"
Cohesion: 0.06
Nodes (65): _as_text(), _assistant(), child_session_ids(), collect_sources(), _count_lines_before(), Event, final_answer(), _flatten_text() (+57 more)

### Community 1 - "Environment Setup and Diagnostics"
Cohesion: 0.06
Nodes (55): ArgumentParser, _account_status(), _check(), _daemon_status(), dispatch(), _doctor(), Path, `doctor`, `setup` and `repl-api` -- the environment, and the browser's own API… (+47 more)

### Community 2 - "CLI Command Integration Tests"
Cohesion: 0.08
Nodes (56): parametrize, cli(), fixture, Path, The commands, end to end through the real argparse, against the fake aside…, The command `next` hands back names no level, so the default is what a caller…, Attaching to a live session was measured waiting for the current turn and then…, The parent's own files are deliberately made old and only the child's is fresh,… (+48 more)

### Community 3 - "Run Progress Watcher Tests"
Cohesion: 0.17
Nodes (45): answer(), capture(), make_run(), fixture, Path, Run, _follow: the only watcher, and the thing that wakes a caller when a run ends.…, Distinct from a terminal line on purpose: the caller has to be able to tell "it… (+37 more)

### Community 4 - "Site Mapping and Crawling"
Cohesion: 0.09
Nodes (35): build_manifest(), _crawl_cmd(), _default_out(), dispatch(), _map(), _number_files(), _providers(), Path (+27 more)

### Community 5 - "Background Run Supervisor Tests"
Cohesion: 0.13
Nodes (39): Path, _supervisor: from "spawn aside" to a result.json somebody can read. The seam is…, The session store is an unofficial surface. When correlation fails -- a schema…, Actually concurrent, because sequential runs cannot reproduce the bug. Two…, `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, `--timeout` is recorded by the process that starts the run, but enforced by the…, A subagent that honestly found nothing stops with an empty turn. Calling that…, meta.json is written by the starting CLI, the detached supervisor and `stop`,… (+31 more)

### Community 6 - "Run Commands and Reporting"
Cohesion: 0.12
Nodes (36): A run ended without a usable answer, or was abandoned while still going., RunFailed, is_opening_tool(), Whether this tool's result means the agent read the page rather than just…, _await_and_report(), dispatch(), _entry(), _exit_code() (+28 more)

### Community 7 - "Page Fetch Orchestration Tests"
Cohesion: 0.14
Nodes (37): out_paths(), provider(), Path, _page: fetch orchestration -- batching, escalation, retry, and where files…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A stand-in for the browser: URL -> the NDJSON record the snippet would have…, The conversion is lossy and the download cost a round trip; keeping the… (+29 more)

### Community 8 - "Run Registry and Metadata"
Cohesion: 0.13
Nodes (25): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., all_runs(), _atomic_write_json(), create_run(), decorate_prompt(), default_runs_dir(), latest_group() (+17 more)

### Community 9 - "Document Classification and Extraction"
Cohesion: 0.11
Nodes (33): classify_response(), count_words(), Document, extract_document(), extract_html(), _first_heading(), _has_strong_challenge_marker(), _is_document_type() (+25 more)

### Community 10 - "Document Extraction Tests"
Cohesion: 0.11
Nodes (24): html(), Path, _extract: deciding what a response actually is, and turning it into markdown.…, anydoc exits 3 for a PDF with no text layer. Sending it for hosted OCR would…, The decisive markers are read off the raw body, before conversion. An…, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the… (+16 more)

### Community 11 - "Session Storage and Discovery"
Cohesion: 0.17
Nodes (25): aside_home(), copy_new_lines(), db_child_rows(), db_finished_at(), db_path(), db_session_row(), db_suspension(), find_session_by_marker() (+17 more)

### Community 12 - "Run Registry Concurrency Tests"
Cohesion: 0.13
Nodes (25): MonkeyPatch, Path, _registry: run directories, run ids, and metadata that survives a crash. The…, The supervisor is a separate process started later; it learns its group from…, The lock gives up after its timeout rather than refusing to record a run's…, Processes, not threads: the lock is a file, and a threads-only test would pass…, Run ids are timestamps, and a group starts every member at once. Reserving the…, The supervisor rewrites meta.json while `status` may be reading it. A half-… (+17 more)

### Community 13 - "Session Storage Recovery Tests"
Cohesion: 0.15
Nodes (25): Path, _store: finding a run's session on disk and copying it somewhere it will…, The cursor describes the destination, not the source. If the copy is truncated…, Ephemeral CLI sessions were observed writing no rows at all -- neither sessions…, The supervisor appends and then records the new cursor as a separate step.…, The reason correlation is by marker and not by prompt text. Two parallel…, Aside creates the directory before the first message lands, and repl sessions…, Aside cleans up sessions on its own schedule. When the source is truncated or… (+17 more)

### Community 14 - "Session Event Parsing Tests"
Cohesion: 0.18
Nodes (20): fixture, Path, _events: turning a session's messages.jsonl into things a caller can act on.…, simple(), test_a_citation_to_an_unknown_source_keeps_its_label(), test_a_completed_line_is_picked_up_on_the_next_read(), test_a_fetched_page_counts_as_opened(), test_a_half_written_line_is_left_for_the_next_read() (+12 more)

### Community 15 - "Browser Simulator Contract Tests"
Cohesion: 0.18
Nodes (19): CompletedProcess, live, Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The snippets work around a specific sandbox shape. If that shape widens, the…, Measured absent from the REPL sandbox. A snippet that touches one of these…, The strongest available check: whatever the fake writes has to be readable by…, If this fails and the fake's equivalent passes, the fake has drifted. (+11 more)

### Community 16 - "Live Browser Integration Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 17 - "Shared Test Fixtures"
Cohesion: 0.21
Nodes (14): Config, Item, aside_home(), fake_aside(), fixtures(), fixture, MonkeyPatch, Path (+6 more)

### Community 18 - "Aside CLI Simulator"
Cohesion: 0.29
Nodes (13): append(), assistant(), do_exec(), do_repl(), main(), make_session(), new_session_id(), Path (+5 more)

### Community 19 - "Document Processing Dependencies"
Cohesion: 0.15
Nodes (12): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+4 more)

### Community 20 - "Web Acquisition Capabilities"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 21 - "Batch Page Fetching"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 22 - "Sitemap URL Discovery"
Cohesion: 0.24
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 23 - "Aside Platform Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 24 - "Recorded Investigation Regression Fixtures"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 25 - "Page Link Discovery"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 26 - "Search Harness Operating Contracts"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 27 - "Markdown Conversion"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 28 - "Yonhap News Examples"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **43 isolated node(s):** `description`, `name`, `private`, `type`, `version` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 223 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ArgumentError` connect `Run Registry and Metadata` to `Environment Setup and Diagnostics`, `Site Mapping and Crawling`, `Run Commands and Reporting`, `Page Fetch Orchestration Tests`, `Document Classification and Extraction`, `Run Registry Concurrency Tests`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `UltraSearchError` connect `Environment Setup and Diagnostics` to `Run Registry and Metadata`, `Run Commands and Reporting`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `_doctor()` connect `Environment Setup and Diagnostics` to `Shared Test Fixtures`, `CLI Command Integration Tests`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **What connects `description`, `name`, `private` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Session Event Parsing` be split into smaller, more focused modules?**
  _Cohesion score 0.06116700201207243 - nodes in this community are weakly interconnected._
- **Should `Environment Setup and Diagnostics` be split into smaller, more focused modules?**
  _Cohesion score 0.05704365079365079 - nodes in this community are weakly interconnected._
- **Should `CLI Command Integration Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.07644110275689223 - nodes in this community are weakly interconnected._