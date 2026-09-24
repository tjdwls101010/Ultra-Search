# Graph Report - graph-wt  (2026-09-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 882 nodes · 1923 edges · 61 communities (42 shown, 19 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 146 edges (avg confidence: 0.86)
- Token cost: 46,771 input · 773 output

## Graph Freshness
- Built from commit: `7bbd8c19`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- CLI Errors and Follow
- Environment Doctor Checks
- Run Directory Tests
- CLI Environment Tests
- Response Classification and Extraction
- Subagent Transcript Following
- Fake Aside Contract Tests
- Page Fetch Tests
- Map and Crawl Tests
- Research Command Tests
- Map and Crawl Commands
- Aside Session Store
- Document Format Handling
- Fake Aside Stand-in
- Recorded Session Fixtures
- Transcript Event Parsing
- Test Fixtures and Config
- Live End-to-End Tests
- Background Run Launch Tests
- Run Supervisor
- Run Evidence Extraction
- Challenge Page Detection Tests
- CLI Parser and Errors
- Run Views and Resume
- Answer and Source Collection
- Node Package Manifest
- Sitemap Discovery Script
- Project Capabilities Overview
- Batch Fetch Script
- Transcript Log Rendering
- Follow and Log Tests
- Aside Product Documentation
- Group Follow Polling Tests
- Golden Regression Recordings
- Link Extraction Script
- Crawl Output Safety Tests
- Recorded Run Fixtures
- Harness Spec and Skill
- Run ID and Cursor Validation
- Markdown Conversion Script
- Transcript Copy Safety
- Yonhap News Pages
- Stop Race Handling
- Tab Cleanup Script
- Single Tab Script
- Full Text to File
- HTML Format Saving
- Grouped Prompt Runs
- Session Transcript File
- Prompt Marker Correlation
- REPL Sandbox Limits
- Run Terminal States
- Run
- Run
- Run
- Run
- Document
- Exception
- Run
- X JavaScript Shell
- MonkeyPatch

## God Nodes (most connected - your core abstractions)
1. `first_run()` - 44 edges
2. `page()` - 42 edges
3. `item_of()` - 40 edges
4. `search()` - 40 edges
5. `Run` - 33 edges
6. `finished_run_id()` - 24 edges
7. `ArgumentError` - 23 edges
8. `tool()` - 23 edges
9. `Event` - 21 edges
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

## Communities (61 total, 19 thin omitted)

### Community 0 - "CLI Errors and Follow"
Cohesion: 0.07
Nodes (67): ArgumentError, is_safe_id(), The failure half of the CLI contract. Every command prints one JSON line…, The caller asked for something the CLI will not do -- refused before any work., A run ended without a usable answer, or was abandoned while still going., RunFailed, _drain(), follow() (+59 more)

### Community 1 - "Environment Doctor Checks"
Cohesion: 0.06
Nodes (49): _account_status(), _check(), _daemon_status(), daemon_url(), dispatch(), _doctor(), Path, `doctor`, `setup` and `repl-api` -- the environment, and the browser's own API… (+41 more)

### Community 2 - "Run Directory Tests"
Cohesion: 0.10
Nodes (40): `--timeout` is recorded by the process that starts the run but enforced by the…, fixture, parametrize, Path, The run directory: what a run leaves on disk, and the files three processes…, `status` may read meta.json at any moment. A value that cannot be serialised…, meta.json is written by the starting CLI, the detached supervisor and `stop`,…, Processes, not threads: the lock is a file, and a threads-only test would pass… (+32 more)

### Community 3 - "CLI Environment Tests"
Cohesion: 0.11
Nodes (35): MonkeyPatch, argv in; the exit code, the last JSON line on stdout, and all of stdout out., run_cli(), check(), daemon(), doctor(), fixture, parametrize (+27 more)

### Community 4 - "Response Classification and Extraction"
Cohesion: 0.12
Nodes (35): classify_response(), count_words(), Document, extract_document(), extract_html(), _first_heading(), _has_strong_challenge_marker(), _is_document_type() (+27 more)

### Community 5 - "Subagent Transcript Following"
Cohesion: 0.09
Nodes (34): first_run(), `stop` detaches the watcher. It cannot cancel the daemon-side run -- killing…, Child ids are read out of the transcript, another product's data, and become…, Checked while the run is going as well as after: the supervisor copies every…, The parent listed a URL; its child opened it, under an id of its own. The…, Aside creates the directory before the first message lands, and repl sessions…, The recorded parent spawned three subagents; one of them was still mid-tool…, The transcript is another product's private surface. An unknown role survives… (+26 more)

### Community 6 - "Fake Aside Contract Tests"
Cohesion: 0.12
Nodes (31): CompletedProcess, live, ndjson(), Path, Keeping the stand-in aside binary honest. Every other test that involves a…, The fake tells snippets apart by this line, so a snippet without it would reach…, The fake cannot evaluate JavaScript, so the only untagged program it answers is…, If this fails and the fake's equivalent passes, the fake has drifted. (+23 more)

### Community 7 - "Page Fetch Tests"
Cohesion: 0.12
Nodes (30): The ARGS of every call the CLI made to one page snippet, in order., repl_calls(), page(), Path, The 120s REPL limit applies to the whole snippet. If a batch were all-or-…, Retried alone rather than in the batch it failed in: whatever made it slow gets…, A 404 is an answer, not a transient failure; asking again only costs a round…, `--out ./notes` for one URL means a folder to anyone who types it. Producing an… (+22 more)

### Community 8 - "Map and Crawl Tests"
Cohesion: 0.10
Nodes (23): mapped(), `fetch`, `map` and `crawl`, end to end through the CLI against the fake…, site.test/a links back to the root through a fragment., A glob says which pages to keep, not which to route through. Docs sites…, A crawl acts as the user in their own browser. A link that shares only the host…, A map that silently lost half a site reads as a small site. What was missed,…, The root alone, unread, is not a map of anything -- even though it is one URL., An href is HTML: `&amp;` in it is one `&` in the URL. Requesting it verbatim… (+15 more)

### Community 9 - "Research Command Tests"
Cohesion: 0.10
Nodes (24): log_of(), make_state_db(), `search`, `resume`, `status`, `log`, `result`, `show`, `stop` and `sessions`,…, The log of a module-scoped run; the text is the rendered lines, without the…, Actually concurrent, because sequential runs cannot reproduce the bug: two…, Watching progress must not be a way to load a fetched page into context by…, Less is the means, not the rule: a failed tool and a finished child are exactly…, The transcript is another product's private surface. A call whose arguments are… (+16 more)

### Community 10 - "Map and Crawl Commands"
Cohesion: 0.13
Nodes (24): build_manifest(), _crawl_cmd(), _default_out(), dispatch(), _map(), _providers(), Path, `map` and `crawl`. `map` is the cheap half: it discovers URLs and writes a… (+16 more)

### Community 11 - "Aside Session Store"
Cohesion: 0.17
Nodes (25): aside_home(), copy_new_lines(), db_child_rows(), db_finished_at(), db_path(), db_session_row(), db_suspension(), find_session_by_marker() (+17 more)

### Community 12 - "Document Format Handling"
Cohesion: 0.13
Nodes (27): document(), frontmatter(), item_of(), docs.aside.com serves text/markdown for its .md URLs. Running that through an…, The conversion is lossy and the download cost a round trip; keeping the…, A PDF with no text layer. Sending it for hosted OCR would ship the user's…, What fetch_batch reports for a binary response: saved to disk, path handed back., A .html file containing markdown is a file whose contents contradict its name… (+19 more)

### Community 13 - "Fake Aside Stand-in"
Cohesion: 0.14
Nodes (23): answer_for(), append(), assistant(), bump(), do_exec(), do_repl(), fetch_batch(), load_routes() (+15 more)

### Community 14 - "Recorded Session Fixtures"
Cohesion: 0.16
Nodes (25): answer(), aside_session(), calling(), A session as Aside itself would have left it on disk -- one the CLI did not…, tool(), user(), A URL appears twice: once as a search result's excerpt, once as the page a…, The count is there to say the silence is busy. A finished child is not what… (+17 more)

### Community 15 - "Transcript Event Parsing"
Cohesion: 0.15
Nodes (22): _as_text(), _assistant(), child_session_ids(), _count_lines_before(), Event, _flatten_text(), has_terminal_answer(), is_opening_tool() (+14 more)

### Community 16 - "Test Fixtures and Config"
Cohesion: 0.16
Nodes (22): Config, Item, aside_home(), cli(), fake_aside(), fixtures(), fixture, MonkeyPatch (+14 more)

### Community 17 - "Live End-to-End Tests"
Cohesion: 0.21
Nodes (18): cli(), Path, End-to-end against the real Aside app. Skipped unless run with `-m live`.…, map is the cheap look-before-you-download step, so the check that matters is…, A conversation started by a bare `aside exec` -- or in the Aside app -- is…, x.com returns a full HTML document with almost no text in it. Anything that…, The entire reason for using the user's own browser. If this fails, either the…, test_a_client_rendered_page_is_promoted_to_a_real_tab() (+10 more)

### Community 18 - "Background Run Launch Tests"
Cohesion: 0.14
Nodes (18): exec_calls(), The argv of every `aside exec` the CLI started, in order., Path, `stop` ends the watching, not the daemon's turn. Resuming the run it abandoned…, The failure this prevents: a caller starts work in the background and simply…, Aside never says which session it created. The marker is how the run finds its…, The capability this is for: a conversation started in the Aside app, or by a…, test_a_background_search_hands_back_the_command_that_will_wake_you() (+10 more)

### Community 19 - "Run Supervisor"
Cohesion: 0.20
Nodes (16): decorate_prompt(), Append the correlation marker to a prompt. Aside's CLI never reports which…, _abandon(), _activity(), _finish(), _from_stdout(), main(), Path (+8 more)

### Community 20 - "Run Evidence Extraction"
Cohesion: 0.15
Nodes (12): child_is_terminal(), _from(), What one run found: its own turn of the session, that turn's children, and…, A child's part in this turn: from the first prompt it received after the turn…, A child is done when its last turn stopped for a reason other than a tool call.…, This turn's own tool results, in order -- what `show --item N` counts., What the turn already read of a URL: the page a tool opened, else a listing's…, Turn (+4 more)

### Community 21 - "Challenge Page Detection Tests"
Cohesion: 0.13
Nodes (16): captured(), fetch_without_node(), Counting whitespace-delimited tokens undercounts CJK badly enough that a real…, x.com is the case that distinguishes the two. It extracts to nothing AND it is…, A challenge page is a successful HTTP response with a body. Saving it as the…, The one thing that stays refused in every format: a challenge saved as the page…, The CLI on a machine where `node` is not on PATH -- nothing else changed., The decisive markers are read off the raw body, before conversion. An… (+8 more)

### Community 22 - "CLI Parser and Errors"
Cohesion: 0.22
Nodes (11): ArgumentParser, EmptyResult, Exception, No result data was produced; this does not establish a negative finding., UltraSearchError, _add_exec_opts(), _add_runs_dir(), _add_target() (+3 more)

### Community 23 - "Run Views and Resume"
Cohesion: 0.13
Nodes (15): finished_run_id(), `result`, `status` and `show` describe the same run. For a resumed run that is…, Aside deletes CLI sessions within about a day. A run whose evidence lives only…, The command `next` hands back names no level, so the default is what a caller…, The transcript a resume appends to already ends in an answer. Until the new one…, test_a_resumed_run_reports_the_new_answer_not_the_previous_one(), test_a_run_that_does_not_exist_is_refused_not_guessed(), test_an_out_of_range_item_is_refused_with_the_count() (+7 more)

### Community 24 - "Answer and Source Collection"
Cohesion: 0.18
Nodes (10): collect_sources(), final_answer(), merge_sources(), The text of the last finished assistant turn, with citation tags resolved to…, Every URL the run touched, in order, deduplicated by URL. ``opened`` separates…, Several streams' sources as one list, one entry per URL, first seen first. A…, resolve_citations(), Source (+2 more)

### Community 25 - "Node Package Manifest"
Cohesion: 0.15
Nodes (12): dependencies, defuddle, @firecrawl/anydoc, linkedom, description, name, private, type (+4 more)

### Community 26 - "Sitemap Discovery Script"
Cohesion: 0.21
Nodes (8): get(), locs(), seen, start, tagValues(), TIMED_OUT, unescapeXml(), withTimeout()

### Community 27 - "Project Capabilities Overview"
Cohesion: 0.17
Nodes (12): Map and Crawl Capability, Fetch Capability, Run Observability Capability, Search Capability, Ultra-Search Project, HTML Disguised as PDF, Example Domain, Anti-Scraping Methods (+4 more)

### Community 28 - "Batch Fetch Script"
Cohesion: 0.27
Nodes (10): batchStart, extFor(), guard, looksBinary(), one(), safeName(), say(), TIMED_OUT (+2 more)

### Community 29 - "Transcript Log Rendering"
Cohesion: 0.36
Nodes (10): _assistant(), _clip(), _first_line(), _progress(), One transcript event, as the line a reader can act on. Which line an event…, ``webfetch×4[nodejs.org] read_file×2`` -- tools in first-use order, each with…, _reached_for(), render() (+2 more)

### Community 30 - "Follow and Log Tests"
Cohesion: 0.18
Nodes (11): lines_of(), Distinct from a terminal line on purpose: the caller has to be able to tell "it…, What a command printed before its JSON response, which is always the last line., A parent investigation goes silent while its subagents work; a watcher that…, test_a_follow_that_runs_out_of_time_says_the_run_is_still_going(), test_a_group_follow_exits_only_when_every_member_is_terminal(), test_an_abandoned_run_is_a_terminal_line_too(), test_child_activity_appears_in_the_parents_stream_and_its_cursor() (+3 more)

### Community 31 - "Aside Product Documentation"
Cohesion: 0.31
Nodes (9): Aside Account Management, Aside CLI, Aside Developer Tools, Aside MCP Server, Aside Browser Automation REPL, Rendered Aside CLI Documentation, Rendered Aside Developer Tools Page, Rendered Aside MCP Documentation (+1 more)

### Community 32 - "Group Follow Polling Tests"
Cohesion: 0.22
Nodes (9): poll(), Silence is labelled, never acted on: a slow run and a stuck one look identical…, The members' transcripts differ in length, so one member's position applied to…, A watch that ran out of time hands back a command that picks up where it…, Only the event lines of a log: no response, no cursor., rendered(), test_a_group_cursor_round_trips_per_member(), test_a_quiet_run_is_flagged_but_left_alone_until_a_child_writes() (+1 more)

### Community 33 - "Golden Regression Recordings"
Cohesion: 0.29
Nodes (8): Offline, live, concurrency, and golden regression validation, Steps golden fixture for a three-subagent investigation, Recorded Go 1.27 subagent investigation, Recorded Node.js 24 LTS subagent investigation, Recorded parent investigation waits for three release summaries, Recorded Python 3.14 subagent investigation, Python 3.14.0 release page — recorded fetch target, What's New in Python 3.14 — cited official document

### Community 34 - "Link Extraction Script"
Cohesion: 0.32
Nodes (7): guard, hrefsOf(), say(), start, TIMED_OUT, withTimeout(), work

### Community 35 - "Crawl Output Safety Tests"
Cohesion: 0.25
Nodes (8): parametrize, Numbered names repeat from one crawl to the next, so writing into a used folder…, The daemon kills a snippet at 120 seconds and says nothing more. What it…, test_a_crawl_never_writes_into_a_folder_that_already_has_files(), test_a_discovery_snippet_cut_off_by_the_repl_limit_is_reported(), test_a_manifest_of_the_wrong_shape_is_refused(), test_an_empty_body_is_not_a_page_that_was_read(), test_file_names_are_readable_and_stable()

### Community 36 - "Recorded Run Fixtures"
Cohesion: 0.32
Nodes (8): eventful(), fixture, A run recorded on 2026-08-29: a parent that spawned three subagents, one of…, The recorded session of a real search: one websearch, one cited answer., A run whose transcript holds every kind of event the log has to render., recorded(), simple_search(), start_isolated()

### Community 37 - "Harness Spec and Skill"
Cohesion: 0.33
Nodes (7): Authenticated Aside browser and CLI, Ultra-Search harness specification, Deferred out=NB character-versus-byte mismatch, Authenticated acquisition and evidence-reporting boundaries, Ultra-Search skill, Reuse results, read evidence, and crawl manifests, CLI-selected next action for watching or collecting results

### Community 38 - "Run ID and Cursor Validation"
Cohesion: 0.29
Nodes (7): parametrize, A run id reaches the filesystem as a directory name. One that walks out of the…, A cursor this command did not print would otherwise restart the log from the…, test_a_cursor_that_is_not_one_is_refused_rather_than_replayed(), test_a_run_id_that_names_a_path_outside_the_registry_is_refused(), test_next_commands_preserve_the_installed_path_and_run_store(), test_terminal_log_and_result_preserve_failure_and_incompleteness()

### Community 39 - "Markdown Conversion Script"
Cohesion: 0.83
Nodes (3): countWords(), main(), read()

### Community 40 - "Transcript Copy Safety"
Cohesion: 0.33
Nodes (4): A line still being written is not yet a record; consuming it would store a…, Aside cleans up sessions on its own schedule. The copy is then the only…, test_a_copy_takes_only_whole_lines_and_picks_up_a_line_once_it_is_complete(), test_a_shrinking_or_vanishing_source_never_shortens_the_copy()

### Community 41 - "Yonhap News Pages"
Cohesion: 0.67
Nodes (3): Yonhap Page Not Found, Nepal Flood Coverage, Yonhap News Portal

## Knowledge Gaps
- **43 isolated node(s):** `description`, `name`, `private`, `type`, `version` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 295 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `UltraSearchError` connect `CLI Parser and Errors` to `CLI Errors and Follow`, `Environment Doctor Checks`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `ArgumentError` connect `CLI Errors and Follow` to `Map and Crawl Commands`, `Response Classification and Extraction`, `CLI Parser and Errors`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `Run` connect `CLI Errors and Follow` to `Run Directory Tests`, `Run Supervisor`, `Run Evidence Extraction`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `description`, `name`, `private` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI Errors and Follow` be split into smaller, more focused modules?**
  _Cohesion score 0.06759259259259259 - nodes in this community are weakly interconnected._
- **Should `Environment Doctor Checks` be split into smaller, more focused modules?**
  _Cohesion score 0.06429070580013976 - nodes in this community are weakly interconnected._
- **Should `Run Directory Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.1048780487804878 - nodes in this community are weakly interconnected._