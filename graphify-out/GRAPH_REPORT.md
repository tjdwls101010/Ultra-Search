# Graph Report - Ultra-Search  (2026-09-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 718 nodes · 1473 edges · 28 communities (25 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 63 edges (avg confidence: 0.87)
- Token cost: 25,704 input · 406 output

## Graph Freshness
- Built from commit: `bcd72939`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Run Watching CLI
- Environment Doctor Command
- CLI Command Tests
- Site Map and Crawl Commands
- Shared Test Fixtures
- Supervisor Tests
- Architecture Documentation
- Page Fetch Tests
- Response Classification and Extraction
- Session Event Parsing
- Extraction Tests
- Session Store
- Session Store Tests
- Follow Watcher Tests
- Event Parsing Tests
- Fake Aside Contract Tests
- Run Supervisor State Machine
- Live End-to-End Tests
- Node Package Manifest
- Fake Aside Binary
- Browser Fetch Snippet
- Sitemap Discovery Snippet
- Link Extraction Snippet
- Markdown Conversion Script
- Yonhap News Pages
- Graphify Navigation Rules
- Tab Cleanup Snippet
- Single Tab Snippet

## God Nodes (most connected - your core abstractions)
1. `Run` - 32 edges
2. `start()` - 27 edges
3. `ArgumentError` - 22 edges
4. `cli()` - 21 edges
5. `provider()` - 21 edges
6. `run_cli()` - 17 edges
7. `run_to_completion()` - 17 edges
8. `AsideUnavailable` - 16 edges
9. `make_run()` - 16 edges
10. `Event` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Search Capability` --semantically_similar_to--> `Search Agent`  [INFERRED] [semantically similar]
  README.md → .claude/skills/ultra-search/SKILL.md
- `Graphify Query-First Navigation` --semantically_similar_to--> `Graphify Navigation Rules`  [INFERRED] [semantically similar]
  AGENTS.md → CLAUDE.md
- `Fetch Capability` --semantically_similar_to--> `Address Reader`  [INFERRED] [semantically similar]
  README.md → .claude/skills/ultra-search/SKILL.md
- `Web Crawling` --semantically_similar_to--> `Map and Crawl Capability`  [INFERRED] [semantically similar]
  tests/fixtures/html/article.html → README.md
- `HTML Disguised as PDF` --semantically_similar_to--> `Cloudflare Human Verification Challenge`  [INFERRED] [semantically similar]
  tests/fixtures/docs/not_really.pdf → tests/fixtures/html/challenge.html

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Aside Developer Tool Surface** — tests_fixtures_html_docs_page_aside_cli, tests_fixtures_html_docs_page_aside_account_management, tests_fixtures_html_docs_page_aside_mcp, tests_fixtures_html_docs_page_aside_repl [EXTRACTED 1.00]
- **Ultra-Search User-Facing Capabilities** — readme_search_capability, readme_fetch_capability, readme_crawl_capability, readme_run_observability_capability [EXTRACTED 1.00]

## Communities (28 total, 3 thin omitted)

### Community 0 - "Run Watching CLI"
Cohesion: 0.06
Nodes (65): ArgumentError, The caller asked for something the CLI will not do -- refused before any work., A run ended without a usable answer, or was abandoned while still going., RunFailed, _drain(), follow(), format_cursor(), parse_since() (+57 more)

### Community 1 - "Environment Doctor Command"
Cohesion: 0.06
Nodes (54): ArgumentParser, _account_status(), _check(), _daemon_status(), dispatch(), _doctor(), Path, `doctor`, `setup` and `repl-api` -- the environment, and the browser's own API… (+46 more)

### Community 2 - "CLI Command Tests"
Cohesion: 0.08
Nodes (49): cli(), fixture, Path, The commands, end to end through the real argparse, against the fake aside…, An honest zero is neither success nor failure: reporting it as success teaches…, Attaching to a live session was measured waiting for the current turn and then…, The parent's own files are deliberately made old and only the child's is fresh,…, The other half of the pair: when nothing anywhere has written recently, the… (+41 more)

### Community 3 - "Site Map and Crawl Commands"
Cohesion: 0.09
Nodes (35): build_manifest(), _crawl_cmd(), _default_out(), dispatch(), _map(), _number_files(), _providers(), Path (+27 more)

### Community 4 - "Shared Test Fixtures"
Cohesion: 0.08
Nodes (39): Config, Item, aside_home(), fake_aside(), fixtures(), fixture, MonkeyPatch, Path (+31 more)

### Community 5 - "Supervisor Tests"
Cohesion: 0.13
Nodes (39): Path, _supervisor: from "spawn aside" to a result.json somebody can read. The seam is…, The session store is an unofficial surface. When correlation fails -- a schema…, Actually concurrent, because sequential runs cannot reproduce the bug. Two…, `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, `--timeout` is recorded by the process that starts the run, but enforced by the…, A subagent that honestly found nothing stops with an empty turn. Calling that…, meta.json is written by the starting CLI, the detached supervisor and `stop`,… (+31 more)

### Community 6 - "Architecture Documentation"
Cohesion: 0.06
Nodes (39): Browser Fetch Pipeline, Disk as Source of Truth, Process Completion Protocol, Prompt Marker Correlation, Site Crawling Pipeline, Ultra-Search Architecture, Asynchronous Run Supervision, Content Classification Pipeline (+31 more)

### Community 7 - "Page Fetch Tests"
Cohesion: 0.14
Nodes (37): out_paths(), provider(), Path, _page: fetch orchestration -- batching, escalation, retry, and where files…, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A stand-in for the browser: URL -> the NDJSON record the snippet would have…, The conversion is lossy and the download cost a round trip; keeping the… (+29 more)

### Community 8 - "Response Classification and Extraction"
Cohesion: 0.11
Nodes (33): classify_response(), count_words(), Document, extract_document(), extract_html(), _first_heading(), _has_strong_challenge_marker(), _is_document_type() (+25 more)

### Community 9 - "Session Event Parsing"
Cohesion: 0.12
Nodes (32): _as_text(), _assistant(), child_session_ids(), _clip(), collect_sources(), _count_lines_before(), Event, final_answer() (+24 more)

### Community 10 - "Extraction Tests"
Cohesion: 0.11
Nodes (25): parametrize, html(), Path, _extract: deciding what a response actually is, and turning it into markdown.…, anydoc exits 3 for a PDF with no text layer. Sending it for hosted OCR would…, The decisive markers are read off the raw body, before conversion. An…, Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, x.com is the case that distinguishes the two. It extracts to nothing AND it is… (+17 more)

### Community 11 - "Session Store"
Cohesion: 0.17
Nodes (25): aside_home(), copy_new_lines(), db_child_rows(), db_finished_at(), db_path(), db_session_row(), db_suspension(), find_session_by_marker() (+17 more)

### Community 12 - "Session Store Tests"
Cohesion: 0.15
Nodes (25): Path, _store: finding a run's session on disk and copying it somewhere it will…, The cursor describes the destination, not the source. If the copy is truncated…, Ephemeral CLI sessions were observed writing no rows at all -- neither sessions…, The supervisor appends and then records the new cursor as a separate step.…, The reason correlation is by marker and not by prompt text. Two parallel…, Aside creates the directory before the first message lands, and repl sessions…, Aside cleans up sessions on its own schedule. When the source is truncated or… (+17 more)

### Community 13 - "Follow Watcher Tests"
Cohesion: 0.33
Nodes (24): answer(), capture(), make_run(), Path, _follow: the only watcher, and the thing that wakes a caller when a run ends.…, Distinct from a terminal line on purpose: the caller has to be able to tell "it…, A parent investigation goes silent while its subagents work. If the watcher…, Watching progress must not be a way to load a fetched page into context by… (+16 more)

### Community 14 - "Event Parsing Tests"
Cohesion: 0.18
Nodes (20): fixture, Path, _events: turning a session's messages.jsonl into things a caller can act on.…, simple(), test_a_citation_to_an_unknown_source_keeps_its_label(), test_a_completed_line_is_picked_up_on_the_next_read(), test_a_fetched_page_counts_as_opened(), test_a_half_written_line_is_left_for_the_next_read() (+12 more)

### Community 15 - "Fake Aside Contract Tests"
Cohesion: 0.18
Nodes (19): CompletedProcess, live, Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The snippets work around a specific sandbox shape. If that shape widens, the…, Measured absent from the REPL sandbox. A snippet that touches one of these…, The strongest available check: whatever the fake writes has to be readable by…, If this fails and the fake's equivalent passes, the fake has drifted. (+11 more)

### Community 16 - "Run Supervisor State Machine"
Cohesion: 0.19
Nodes (18): _abandon(), _activity(), _child_is_terminal(), _finish(), _from_stdout(), main(), Path, The state machine that turns a running `aside exec` into a result on disk.… (+10 more)

### Community 17 - "Live End-to-End Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 18 - "Node Package Manifest"
Cohesion: 0.15
Nodes (12): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+4 more)

### Community 19 - "Fake Aside Binary"
Cohesion: 0.32
Nodes (12): append(), assistant(), do_exec(), do_repl(), main(), make_session(), new_session_id(), Path (+4 more)

### Community 20 - "Browser Fetch Snippet"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 21 - "Sitemap Discovery Snippet"
Cohesion: 0.24
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 22 - "Link Extraction Snippet"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 23 - "Markdown Conversion Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 24 - "Yonhap News Pages"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **31 isolated node(s):** `description`, `name`, `private`, `type`, `version` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ArgumentError` connect `Run Watching CLI` to `Environment Doctor Command`, `Site Map and Crawl Commands`, `Shared Test Fixtures`, `Page Fetch Tests`, `Response Classification and Extraction`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `UltraSearchError` connect `Environment Doctor Command` to `Run Watching CLI`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `_doctor()` connect `Environment Doctor Command` to `CLI Command Tests`, `Shared Test Fixtures`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **What connects `description`, `name`, `private` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Run Watching CLI` be split into smaller, more focused modules?**
  _Cohesion score 0.06004543979227524 - nodes in this community are weakly interconnected._
- **Should `Environment Doctor Command` be split into smaller, more focused modules?**
  _Cohesion score 0.057859703020993344 - nodes in this community are weakly interconnected._
- **Should `CLI Command Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.08489795918367347 - nodes in this community are weakly interconnected._