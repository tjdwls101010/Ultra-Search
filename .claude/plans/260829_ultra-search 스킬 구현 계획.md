# ultra-search 스킬 구현 계획

## Context (목적과 요약)

**한 문장:** 클로드가 웹에서 무언가를 알아내야 할 때 네이티브 `WebSearch`/`WebFetch` 대신 자연스럽게 집어드는, 성진의 로그인된 Aside 브라우저(`aside` CLI)를 엔진으로 삼는 `ultra-search` 스킬을 만든다.

**왜:** 네이티브 툴은 Brave 인덱스에 갇혀 검색 범위가 좁고, 로그인·봇차단 뒤의 정보에 닿지 못하며, 결과가 query 맞춤 발췌라 원문이 필요할 때 부족하고, 크롤링과 로컬 저장이 불가능하다. `aside`는 성진의 실제 브라우저(쿠키·세션 포함)를 쓰고, `exec`으로 브라우저 안의 LLM 에이전트가 자율 조사를 수행하며, `repl`로 Playwright 수준의 결정적 조작이 가능하다.

**합의된 결과물:** `.claude/skills/ultra-search/`(이 레포가 소스, `~/.claude/skills/ultra-search`로 심링크)에 SKILL.md + Python CLI(`scripts/ultra_search.py` + 작은 모듈들) + Node 변환 헬퍼 + pytest 테스트. 네 역량 — (1) 병렬·백그라운드 검색과 진행 추적·이어하기, (2) 원문 fetch, (3) 사이트 map/crawl, (4) 깔끔한 마크다운 저장 — 를 하나의 CLI 표면으로 제공한다. 성진의 결정: 네이티브 툴 deny 같은 강제 계층은 넣지 않고 스킬 완성도에 집중, crawl4ai는 v1 제외, `aside mcp` 등록 안 함, 스크립트는 작은 모듈로.

**설계 원칙(harness-creator):** principle over rail — 규칙 나열 대신 재도출 가능한 원리와 gotcha만. interface over document — 사용법은 `--help`·`choices=`·출력 JSON이 가르치고 SKILL.md는 "언제·왜·무엇을 조심"만 쓴다. for user not developer — 커맨드는 클로드의 목적(검색·읽기·매핑·저장) 단위, aside 내부 개념 노출 최소. dense information — 모델이 이미 아는 것은 쓰지 않는다.

## 확정된 현재 상태와 근거 (2026-08-29 실측)

표기: **[관측]** 이 세션에서 직접 측정한 사실(근거 위치 괄호), **[추론]** 관측에서 끌어낸 결론, **[목표]** 아직 실행하지 않은 검증 대상.

### aside CLI (1.26.810.1915, 데몬 1.26.827.1029, `~/.local/bin/aside`)
- [관측] 커맨드: `exec [prompt]`, `repl [code]`, `mcp`(stdio, `repl` 툴 하나), `account list|status|use`. 공통 옵션 `--session <id>`, `--account`, `-m/--model`, `-p/--provider`, `-s/--speed default|fast`, `--effort off|minimal|low|medium|high|xhigh|max|ultrabrowse`. (`aside --help`)
- [관측] 계정 `u0` 구글 로그인 상태. 기본 모델 `openai-codex/gpt-5.6-sol`, thinking high, fast (`~/.aside/u/0/settings.json`). ChatGPT 구독으로 과금. 단순 검색 1건 ≈ 18K 토큰(`messages.jsonl` usage).
- [관측] 공식 문서 `https://docs.aside.com/help/developers.md`(Mintlify, `llms.txt` 제공). exec 출력 형식·타임아웃·중단 방법은 문서화되어 있지 않다.
- [관측] 데몬 `127.0.0.1:21420/`(무인증 GET)이 `semaphore {available:20, capacity:20}`을 보고. [추론] 동시 세션 상한 20 — 문서 근거 없음, 관측값.

### exec (`scratchpad/exec_probe.py`, `subagent_probe.py`, `--effort` 비교, kill 실험)
- [관측] PTY 없이 정상 종료(9.5초, exit 0, stdout 28KB). `조사.py`가 전제한 "PTY 필수"는 현재 버전에 해당 없음.
- [관측] 두 exec 동시 실행 정상, 각자 세션.
- [관측] stdout: `Thinking: …` → `websearch(objective: …, search_queries: […], mode: 'basic')` → ` > {json 결과}` → 마지막 줄이 최종 답(`<citation refs="…">` 태그). JSON 출력 모드 없음.
- [관측] 세션 기록이 구조화되어 디스크에 남는다: `~/.aside/u/0/sessions/<YYYY-MM-DD>_<sessionId>/messages.jsonl` — `role: user|assistant|toolResult`. assistant는 `content[]`에 `thinking`·`toolCall{name, arguments}`·`text`, `usage{input,output,cacheRead,reasoning,totalTokens,cost}`, `stopReason`. toolResult는 `toolName`(websearch·webfetch·repl·read_file·bash·write_todos·subagent·subagent_wait·get_time·memory_search·browsing_history_search·write_file 관측), `content`, `details`. `websearch.details.sources[]`={id,url,title,publishDate,excerpt}; `webfetch.content`=페이지 전문 + `details.sources`; `subagent.details.taskId`; `subagent_wait.details.results[]`.
- [관측] `~/.aside/u/0/state.db`(SQLite): `sessions(id, parent_id, title, trigger, status, model, cwd, ephemeral, suspension, created_at, updated_at…)` — CLI 세션은 `trigger={"type":"user","source":"cli"}`, `ephemeral=1`, 실행 중 `status='running'` → 종료 시 `'idle'`. 서브에이전트는 `trigger.type='subagent'`인 별도 세션으로 `parent_id`가 부모. `session_runs(session_id, user_message, final_assistant_message, token_usage, started_at, last_message_timestamp, finished_at, aborted_at, abort_reason)` — `finished_at`이 완료 신호. `suspension`은 이력 전체에서 한 번도 채워진 적 없음.
- [관측] `exec --session <id> "후속"`(종료된 세션): 3.5초, `Thinking:` 한 줄 + 답만 출력.
- [관측] `exec --session <id> "STOP"`(실행 중인 세션): 진행 중인 런이 끝날 때까지 24초 붙어 있다가 **그 런의 결과를 출력**하고 exit 0. 중단되지 않는다.
- [관측] **프로세스를 죽여도 데몬 쪽 런은 계속된다.** SIGTERM(프로세스 그룹)·SIGINT 모두 CLI만 종료(rc −15/−2)하고 세션은 `running` 유지, 죽인 뒤에 자식 세션 2개가 새로 생성돼 조사를 계속함. [추론] CLI에는 런 중단 수단이 없다. 중단은 Aside 앱 UI뿐.
- [관측] 서브에이전트: 부모에게 "둘을 기다려라"고 지시한 한 사례에서 자식 2개가 8초에 생성, 20·28초에 `idle`+`finished_at`, 부모 프로세스는 30.5초 exit 0. 부모 stdout은 그 사이 18초 침묵. `subagent` toolResult의 `task_id` = 자식 세션 id. [추론] 명시적 대기가 있는 경우 프로세스 종료가 곧 부모 완료. 부모가 자식을 기다리지 않고 끝내는 경우는 미검증.
- [관측] `--effort minimal --speed fast`(10.9초, 29K 토큰), `--effort low`(7.5초, 29K)는 기본 high(9.5초, 18K)보다 나을 게 없다. [추론] effort를 낮추라는 권장은 쓰지 않는다.
- [관측] **CLI 세션은 다음 날에는 이미 없다.** 8/28 `조사.py`가 만든 세션들이 DB와 디스크 양쪽에서 사라졌고, DB에 남은 CLI 세션은 오늘 것뿐. 정확한 보존 기간은 미상.
- [관측] 세션 id는 stdout에서 websearch 결과 JSON의 `"session_id"`로만 우연히 노출된다.

### repl (`aside repl "…"` 실측 다수)
- [관측] 호출마다 새 세션, 상태 미지속(변수·`page` 리셋, `page`는 null로 시작). 코드는 argv로 전달(stdin은 대화형 배너가 섞임).
- [관측] 120초 하드 제한. 125초 sleep → 120초에 "fetch failed: other side closed / Aside daemon is not reachable" exit 1. 데몬은 살아 있는데도 이 메시지가 나온다.
- [관측] `console.log`만 출력 채널. 264KB JSON 한 줄도 온전히 나온다.
- [관측] `fetch(url)`은 로그인 쿠키를 실어 보낸다(YouTube 응답 `"LOGGED_IN":true`, 1.1초). 8개 병렬 fetch 0.66초. `openTab` 1.8초, `page.content()` 원문 HTML, `page.evaluate`, `snapshot(page)`→`{tree(접근성 트리 8KB), refs, diff}`, `page.pdf`, `closeTab`.
- [관측] fetch vs openTab(5개 사이트): mk.co.kr·yna.co.kr·reddit은 `fetch`만으로 본문(텍스트 5~27K자, 차단 없음). x.com은 `fetch` HTML 290KB에 텍스트 451자 ↔ `openTab` innerText 2,777자; threads.com 9자 ↔ 554자. [추론] 승격 판정은 HTML 크기·상태코드(둘 다 200)가 아니라 추출된 본문 양으로.
- [관측] 전역: Playwright `page`/`tabs`, `listBrowserTabs`, `attachBrowserTab`, `openTab`, `closeTab`, `snapshot`, `annotatedScreenshot`, `display`, `fs`, `path`, `Buffer`, `sleep`, `pwd`. `require`/`import` 차단, `util` 없음.
- [관측] 내장 클라이언트: `youtube.search/getMetadata/getTranscript/getComments`(검색 0.8초), `googleSearch.search`(봇 챌린지로 실패 — 신뢰 불가), `aside.sessions.get/list/messages/childSessions/update/archive`(abort 없음; `list`는 ephemeral 미포함), `aside.pdf.extractText({filePath})/renderPages`(파일 경로 입력), 기타 twitter·linkedin·gmail·googleDocs·googleSheets·notion·slack·cua·captcha.
- [관측] `aside mcp` `tools/list`의 repl description은 4,489자로 repl API 전체(환경·함수·규칙·예시)를 담는다(`mcp_probe2.py`, 2회 재현). codex 리뷰의 "한 줄뿐" 지적은 재현되지 않음.

### 마크다운 변환 (`scratchpad/defuddle-test/`)
- [관측] obsidian-clipper의 변환 엔진은 npm `defuddle`(0.19.3, Turndown 내장). clipper 자체 코드는 템플릿 엔진·하이라이트 UI라 불필요.
- [관측] Node 22.14에서 `Defuddle(html, url, {markdown:true})`(defuddle/node) → `{content, title, author, published, site, domain, wordCount, language, description, metaTags, schemaOrgData}`. docs 페이지 285ms, 품질 양호. README: `parseAsync()`는 본문이 없을 때 제3자 API(FxTwitter 등)로 fallback하며 `useAsync:false`로 끌 수 있다. `defuddle` 자체 CLI는 stdin 입력 시 `--url`을 못 받는다.
- [관측] 의존성 `defuddle` + `linkedom`. Node 22.14, npm 10.9, uv 0.8, Python 3.12 설치됨.

### PDF·오피스 문서 변환 — anydoc (`.tmp/anydoc`, `scratchpad/anydoc-test/`)
- [관측] Firecrawl의 Rust 라이브러리, npm `@firecrawl/anydoc` 0.2.4(prebuilt 바이너리 6.8MB, `npm install` 1.9초, Node ≥20), Python `firecrawl-anydoc`도 있음. 입력: PDF·doc/docx·ppt/pptx·xls/xlsx·odt/ods/odp·rtf·epub·csv, 형식은 바이트 시그니처로 감지. CLI `anydoc <file|-> [-o out] [--format] [--ocr reject|hosted]`, 종료 코드 0/1(변환 불가)/2(인자)/3(OCR 필요). stdin 입력 가능. 텍스트 레이어 없는 스캔 PDF는 로컬 OCR 없이 exit 3.
- [관측] arXiv 논문 PDF 2.2MB → 0.48초, 40KB GFM 마크다운, 제목 39개·표 34줄 구조 유지. 브라우저에서 찍은 한국어 페이지 PDF(6쪽) → 한글 3,598자 정상, 제목·본문 구조 유지. HTML을 PDF로 속이면 "not a PDF: file appears to be HTML" exit 1.
- [관측] 비교 대상 `aside.pdf.extractText({filePath})`: 1.07초, `{pageCount, pages[{page,text}]}` — 줄바꿈뿐인 평문, 구조 없음. [추론] PDF 경로는 anydoc이 우월하고 오피스 문서까지 덤으로 얻는다.
- [관측] repl `fetch`로 PDF를 받아 `pwd`(세션 디렉터리)에 저장하는 데 185ms — Python이 그 경로를 읽어 anydoc에 넘기면 된다.

### crawl4ai (v1 제외의 근거)
- [관측] 0.9.0 설치됨. Aside 브라우저의 CDP(`127.0.0.1:45103`)는 Authorization 필요 → 붙일 수 없음. `AsyncUrlSeeder` sitemap 발견 17 URL 5초.
- [추론] 로그인 세션 활용이라는 존재 이유와 충돌하고, sitemap은 repl `fetch`로 읽으면 되므로 제외.

### 참고 자산의 교훈 (`.tmp/조사.py`, `.tmp/ultra-fetch`)
- `조사.py`: 출력 침묵을 정체로 오판해 살아 있는 조사를 죽인 사례 → 침묵은 판정 근거가 아니다. 툴 이름 열거가 새 툴에 깨진 사례 → 열거하지 않는다. 같은 초 두 실행의 로그 충돌 → `O_EXCL` 예약. SIGKILL로 정리했으나 데몬 세션은 계속됐을 것(위 관측과 일치).
- `ultra-fetch`: 차단 페이지가 "성공"으로 보이는 문제, JS 셸 감지, PDF 오인, 파서에서 문서를 생성하는 `catalog`. 판정 규칙만 가져온다.

### codex 스킬의 구조적 선례 (`~/.claude/skills/codex`)
- 단일 브리지 CLI, JSON 한 줄 출력, `start`→핸들, `log --follow`가 터미널 라인에서 exit하여 백그라운드 Bash 알림으로 클로드를 깨우는 arming 관용구, `status/log/result` 역할 분리, `--since` 커서, `--level`, `show`, group, `resume`, `stop`, `doctor`. 성진이 관찰한 실패: 클로드가 실행만 해두고 멈춤. 유지보수 관찰: `codex_bridge.py` 86KB·`_batch.py` 82KB 단일 파일이 무겁다.

## 핵심 결정과 근거

1. **exec 위에 검색, repl 위에 fetch/crawl/save.** exec 결과는 에이전트의 요약이고 호출당 수십 초·수만 토큰. repl `fetch`는 쿠키 포함 0.1~1초에 원문 HTML. "모두 exec"은 비용·비결정성, "모두 repl"은 자율 조사를 클로드가 직접 짜야 해서 기각.
2. **진행 추적은 stdout 파싱이 아니라 세션 저장소(`messages.jsonl` + `state.db`) 읽기 — 단, 비공식 표면이므로 강등 경로를 갖춘다.** 세션 발견에 실패하거나 스키마가 바뀌어도 런은 프로세스 종료와 `stdout.log`만으로 `completed_unstructured`(답=stdout 마지막 비툴 블록, 출처=stdout의 `url:` 인자 목록) 결과를 낸다. 파서는 알 수 없는 형태를 raw로 강등하고 절대 조용히 빈 결과를 내지 않는다. `doctor`가 aside 버전이 실측 버전(1.26.810)과 다르면 경고.
3. **세션 correlation은 프롬프트 안의 마커로.** `created_at ≥ 시작시각` + `user_message` 일치만으로는 같은 프롬프트의 병렬 실행이나 두 클로드 세션을 구분 못 한다(codex 지적). 각 exec 프롬프트 끝에 `\n\n(ultra-search run <run_id> — ignore this line)`을 붙여 `session_runs.user_message`와 1:1 대응. 발견에는 30초 데드라인, 실패 시 결정 2의 강등.
4. **`search`의 기본은 동기, `--wait`(기본 100초)를 넘으면 런은 살려 둔 채 핸들 반환. 슈퍼바이저는 호출 CLI에서 분리(detach)되어 CLI가 Bash 타임아웃으로 끊겨도 런과 동기화는 계속된다.** 성진이 codex에서 본 "실행만 하고 멈춤"은 백그라운드 경로에서만 생긴다. 단순 검색은 10초 안팎이라 대부분 인라인으로 끝나고, 긴 조사는 길이를 예측하지 않아도 자동으로 백그라운드 경로로 넘어간다. 100초는 Bash 기본 120초 아래라 타임아웃을 안 올려도 핸들을 잃지 않는다. 핸들 JSON은 `next: {command, bash_timeout_ms, run_in_background}`로 arm 명령과 권장 Bash 타임아웃까지 구조화해 돌려준다.
5. **런을 죽이는 기본 마감은 없다. `stop`은 감시를 끊는 것이지 런을 멈추는 게 아니다.** 조사 길이는 10초~수십 분(성진 지적, `조사.py`도 "병렬 조사는 10분 넘는 게 정상"), 생존 신호가 따로 있고, 무엇보다 프로세스를 죽여도 데몬 쪽 런은 계속되어 크레딧이 그대로 나간다(관측). `--timeout`은 옵션으로만 두며 의미는 "이 시점에 감시를 끊고 `abandoned`로 표시"임을 help에 명시. 진짜 중단은 Aside 앱 UI — SKILL.md gotcha. 따라서 프롬프트를 작고 경계가 분명하게 쓰는 것이 유일한 비용 통제다.
6. **종료 판정 = 프로세스 종료 ∧ stdout drain(필수) + DB `finished_at`(보조) + 자식 세션 전부 terminal(확인).** 프로세스 종료 후 자식이 `running`이면 settle window(10초) 뒤 `completed_with_orphans`로 명시하고 자식 id를 남긴다. 침묵 기반 자동 종료는 없다.
7. **비파괴 정체 관측.** `status`는 stdout·부모/자식 JSONL·DB 중 가장 최근 변화 시각을 `last_activity_at`, 경과를 `idle_seconds`로 노출하고, `--stall-after`(기본 300초) 초과 시 `possibly_stalled: true`를 *표시만* 한다(상태 전이·kill 없음). `suspension`도 그대로 노출. 판단은 클로드가 한다.
8. **결과 보관은 단조롭게.** 세션 파일은 완전한 줄까지만 커서 기반으로 append 복사하고 목적지를 절대 축소하지 않는다(aside 정리로 원본이 짧아지거나 사라져도 복사본은 남는다). `meta.json`·`result.json`은 temp 파일 후 atomic replace. 세션이 다음 날 사라지므로 완료 즉시 최종 동기화.
9. **레지스트리는 `<project>/.ultra-search/`(기본), `--runs-dir`로 변경.** codex `.codex-runs` 관례와 동일. 저장 페이지 기본 목적지 `.ultra-search/pages/`, `--out`으로 어디든. `.gitignore`에 `.ultra-search/`.
10. **HTML 마크다운은 defuddle Node API**(`scripts/page/to_markdown.mjs`, linkedom으로 Document 생성, `useAsync:false`), 문서 파일은 anydoc CLI(결정 13). 둘 다 `scripts/page/package.json` 한 곳에서 관리하고 `doctor`가 `node_modules`·`anydoc` 바이너리 부재를 보고, `setup`이 `npm install`.
11. **fetch는 URL별로 격리된 repl 실행.** 120초 제한은 URL 개수로 나눠서는 보장되지 않는다(한 URL의 navigation이 120초를 먹으면 청크 전체가 죽고 성공분도 잃는다 — codex 지적). 스니펫 안에서 URL별 타임아웃(fetch 20초, tab 45초)과 전체 예산 105초를 두고 `Promise.allSettled`로 돌리며 **URL별 결과를 NDJSON 한 줄씩 즉시 출력**한다. Python은 실패 URL만 더 작은 묶음 또는 단건으로 재시도한다. 빠른 fetch 배치와 느린 tab 승격은 별도 repl 호출.
12. **추출·판정 순서:** HTTP 상태·content-type·명백한 챌린지 토큰(`cf-ray`·`just a moment`·`challenge-platform`이 짧은 본문과 공존) → PDF면 결정 13 → linkedom Document → Defuddle(`useAsync:false`) → `wordCount` < 임계(초기값 80 단어; x.com 451자·threads 9자 미만, mk·yna·reddit 통과)면 셸로 판정하고 `--via auto`에서 tab 승격(URL별 별도 repl, 최종 URL 검증, bounded wait, `finally closeTab`; 타임아웃으로 탭을 못 닫은 경우 다음 호출에서 `listBrowserTabs`로 찾아 닫기). frontmatter `via: fetch|tab`.
13. **PDF·오피스 문서는 anydoc으로 마크다운화.** defuddle은 DOM 입력만 받으므로 HTML이 아닌 응답(content-type 또는 바이트 시그니처가 PDF·docx·pptx·xlsx·epub 등)은 repl이 `pwd` 아래에 바이너리로 저장하고(`save_binary.js`), Python이 `node_modules/.bin/anydoc <file>`을 실행해 GFM 마크다운을 얻는다. `aside.pdf.extractText`는 평문만 주므로 기각(관측). exec 경로와 무관(aside 에이전트는 PDF를 스스로 읽는다). anydoc exit 3(스캔 PDF)은 해당 URL만 `status: needs_ocr`로 정직하게 보고 — OCR(Firecrawl 호스팅)은 비범위(성진 결정). exit 1은 `status: unsupported`.
14. **fetch/map/crawl 출력도 JSON 한 줄 규약을 따른다.** `fetch`는 `items[{url, final_url, status, via, path, title, words, truncated}]` envelope. 전문은 항상 파일(artifact)에 쓰고, `--print`가 있을 때만 `content`(기본 상한 20K자, `truncated` 표기)를 인라인 포함. `--out FILE`은 URL 하나일 때만 허용, 여럿이면 디렉터리만(help에 거부 규칙).
15. **커맨드 표면 정리.** `status`는 스냅샷만(`--follow` 없음), `log --follow`가 유일한 watcher(그룹은 멤버 인터리브 + 그룹 터미널 라인). `result --json` 제거(전부 JSON). `map --out manifest.json`을 `crawl --from manifest.json`이 소비해 두 번 탐색하지 않는다. `repl-api` 유지(관측 재현).
16. **강제 계층 없음.** deny·CLAUDE.md 변경은 범위 밖(성진 결정). 트리거는 `description`이 전담.
17. **SKILL.md는 영어**(codex·harness-creator와 동일), description 트리거에 한국어 표현 포함.
18. **모듈은 책임 하나·400줄 이하, 엔트리포인트는 argparse와 디스패치만(≤200줄).** 테스트가 모듈 경계를 따르고, Edit 정확 매칭·PR 리뷰 가독성이 파일 크기에 반비례하기 때문. 초과하면 분할 seam을 먼저 찾는다.

## 최종 디렉터리 구조

```
Ultra-Search/                                  # 이 레포 = 스킬의 소스이자 테스트 장소
├── .claude/
│   ├── skills/
│   │   └── ultra-search/                      # ~/.claude/skills/ultra-search → 여기로 심링크 (codex·harness-creator와 같은 방식)
│   │       ├── SKILL.md                       # 트리거(description), exec vs repl 원리, arming 관용구, gotcha. references/ 없음(분기 없는 단일 절차)
│   │       └── scripts/
│   │           ├── ultra_search.py            # argparse 배선·디스패치·종료 코드 (≤200줄)
│   │           ├── _exec.py                   # exec 전송: 프로세스 spawn(setsid, detach)·stdout 캡처·마커 삽입
│   │           ├── _repl.py                   # repl 전송: 스니펫 로드·인자 주입·호출·NDJSON 회수·120초 오류 해석
│   │           ├── _store.py                  # aside 홈 읽기: DB 조회(세션 발견·자식·finished)·세션 디렉터리·커서 복사
│   │           ├── _events.py                 # messages.jsonl 이벤트 모델, level 필터, 출처·인용·usage, 렌더링
│   │           ├── _registry.py               # 런 디렉터리·id 예약(O_EXCL)·meta.json atomic·그룹 조회
│   │           ├── _supervisor.py             # 상태 기계: 세션 확정→동기화 루프→종료 판정(orphans 포함)→result.json
│   │           ├── _follow.py                 # log --follow, 커서, heartbeat, 자식 인터리브, 터미널 라인
│   │           ├── _extract.py                # 상태/챌린지 판정, HTML→defuddle / 문서→anydoc 분기, 셸 판정(wordCount), frontmatter, 슬러그
│   │           ├── _crawl.py                  # sitemap 파서, 링크 frontier(BFS, glob, depth, 상한), manifest — 순수 로직(response-provider 주입)
│   │           ├── _page.py                   # fetch/map/crawl 오케스트레이션: 배치·재시도·승격·파일 쓰기
│   │           ├── _doctor.py                 # 환경 점검·setup(npm install)·repl-api(mcp tools/list)
│   │           └── page/
│   │               ├── package.json           # defuddle, linkedom, @firecrawl/anydoc
│   │               ├── to_markdown.mjs        # stdin {html,url} → stdout {markdown, meta} (linkedom Document, useAsync:false)
│   │               └── snippets/              # repl에 보낼 JS 템플릿 (URL별 타임아웃·예산·allSettled·NDJSON)
│   │                   ├── fetch_batch.js     # 쿠키 fetch N개 병렬; HTML은 본문 인라인, 비HTML은 pwd에 저장 후 경로 보고
│   │                   ├── tab_one.js         # openTab + page.content() 승격, finally closeTab
│   │                   ├── sitemap.js         # sitemap.xml / index 수집
│   │                   ├── links.js           # 같은 origin 링크 수집
│   │                   └── cleanup_tabs.js    # 남은 승격 탭 닫기
│   ├── harness-spec.md                        # harness-creator 스펙(컴포넌트 목록·Change history)
│   └── plans/
│       └── websearch-smooth-gem.md            # 이 계획서
├── tests/
│   ├── conftest.py                            # ULTRA_SEARCH_ASIDE_BIN·ULTRA_SEARCH_ASIDE_HOME → tmpdir 주입, 임시 runs-dir
│   ├── fake_aside/
│   │   └── aside                              # 가짜 실행 파일: exec은 시나리오별 녹화 stdout 재생 + ASIDE_HOME 아래 가짜 세션 디렉터리·DB 생성, repl은 스니펫 이름별 NDJSON 응답, argv 기록
│   ├── fixtures/
│   │   ├── sessions/                          # 익명화한 실제 messages.jsonl(단순 검색·서브에이전트·resume) + state.db 축소본 + suspension 비null 케이스
│   │   ├── html/                              # docs 페이지, JS 셸(x.com형), 차단 페이지
│   │   ├── docs/                              # 작은 텍스트 PDF(영문·한글), docx 1개, HTML을 PDF로 속인 파일
│   │   └── golden/                            # 기대 마크다운·manifest.json
│   ├── test_events.py  test_store.py  test_registry.py  test_supervisor.py  test_follow.py
│   ├── test_extract.py  test_crawl.py  test_page.py  test_contract_fake_aside.py
│   └── live/                                  # -m live, 실제 aside 필요, 기본 skip
│       └── test_live_search.py  test_live_fetch.py  test_live_crawl.py
├── .ultra-search/                             # 런타임 산출물(런 디렉터리·저장 페이지), .gitignore 대상
├── .gitignore                                 # .tmp/, .ultra-search/, .claude/histories, node_modules/
├── README.md                                  # 설치(심링크·setup), 사용 개요, 개발(테스트) — 한국어
└── .tmp/                                      # 참고 자산 — 커밋 안 함
```

런타임에 생기는 것: `<project>/.ultra-search/runs/<yymmdd-hhmmss>-<label>/{meta.json, stdout.log, session/messages.jsonl, session/children/<id>.jsonl, result.json}`, `<project>/.ultra-search/pages/<slug>.md`(문서 파일은 원본 바이너리도 `<slug>.<ext>`로 옆에 보관), `crawl --out DIR/{NNN-slug.md…, manifest.json}`, `scripts/page/node_modules/`(setup 후, defuddle·linkedom·anydoc 바이너리).

## 인터페이스 (CLI 표면 — 구현 시 `--help`가 이 표를 대체한다)

`python3 "<skill dir>/scripts/ultra_search.py" <command>`. 모든 커맨드는 JSON 한 줄을 출력한다(`log`는 이벤트 스트림 후 터미널 라인 + `# cursor=<n>`). stdlib만, Python 3.10+. 환경변수 `ULTRA_SEARCH_ASIDE_BIN`, `ULTRA_SEARCH_ASIDE_HOME`(기본 `~/.aside`)은 테스트 주입용.

| 커맨드 | 역할 | 주요 인자 |
|---|---|---|
| `search PROMPT [PROMPT…]` | exec 실행. 여러 PROMPT는 병렬(그룹). 기본 동기: `--wait` 안에 끝나면 각 런의 답·출처·usage, 못 끝나면 런은 살려 둔 채 핸들 + `next{command, bash_timeout_ms, run_in_background}` | `--background`(즉시 핸들), `--wait SEC`(기본 100, 런을 죽이지 않음), `--label`, `--effort <aside choices>`, `--model`, `--speed`, `--timeout SEC`(기본 없음; 의미는 감시 중단+`abandoned`, 런은 계속됨), `--runs-dir` |
| `resume RUN "후속"` | `exec --session`으로 종료된 세션 이어가기(새 런 id, lineage). 실행 중인 런에는 거부(붙어서 기다릴 뿐 중단·조향 안 됨 — 관측) | `search`와 동일 옵션 |
| `status` | 스냅샷: state, 세션 id, 자식 수/상태, `last_activity_at`, `idle_seconds`, `possibly_stalled`, `suspension`, usage 누계 | `--run`/`--group`, `--stall-after SEC`(기본 300) |
| `log` | 이벤트를 바이트 커서부터 필터해 출력; 유일한 watcher | `--run`/`--group`(멤버 인터리브), `--since`, `--level compact|normal|full|raw`, `--follow`, `--follow-timeout SEC`(기본 570 — Bash 600s 아래; 만료 시 `run.still-running`), `--heartbeat SEC`(살아 있는 자식 수 포함) |
| `result` | 세 층 중 위 둘: `answer`(최종 답 전문, `<citation>` 태그를 URL 각주로 치환, 자식 결과 포함)와 `sources[]`(url·title·`opened: true|false` — 검색 결과로 *본* 것과 webfetch/repl로 *실제 읽은* 것을 구분; `조사.py` 교훈), usage·state(`completed|completed_with_orphans|completed_unstructured|failed|abandoned`) | `--run`/`--group`, `--sources-only`(답 생략) |
| `show` | 세 번째 층: 출처 하나의 전문(aside가 webfetch로 이미 받아둔 텍스트 — 다시 fetch 안 함) 또는 툴 호출 하나의 결과 | `--run`, `--source N|ID` \| `--item N` |
| `stop` | 감시 중단 + `abandoned` 표시 + 프로세스 종료. **데몬 쪽 런은 계속됨** — help와 출력에 명시 | `--run`/`--group`/`--all` |
| `fetch URL [URL…]` | 페이지 또는 문서(PDF·docx·pptx·xlsx·epub…) → 파일(마크다운 기본). JSON envelope `items[]`(항목 `status`: ok·shell_escalated·blocked·needs_ocr·unsupported·error) | `--out FILE(단일 URL만)|DIR`, `--format md|html|text|snapshot`(문서 파일은 md만), `--via auto|fetch|tab`, `--print`(content 인라인, `--max-chars` 기본 20000), `--no-frontmatter` |
| `map URL` | 콘텐츠 없이 URL 목록(+제목 옵션) → manifest | `--max-urls`, `--depth`, `--include/--exclude GLOB`, `--no-sitemap`, `--out manifest.json` |
| `crawl URL \| --from manifest.json` | map + fetch → `NNN-slug.md` + `manifest.json` | map 옵션 + `--max-pages`(기본 25), `--concurrency`(기본 8), `--out DIR` |
| `repl-api` | `aside mcp` `tools/list`의 repl description을 실시간 출력 | — |
| `doctor` | aside 바이너리·버전(실측 버전과 다르면 경고)·데몬 응답(repl 왕복)·계정·node·node_modules·runs-dir·기본 모델 | — |
| `setup` | `npm install` | — |

종료 코드: 0 성공 / 2 인자 오류 / 3 aside 불가 / 4 런 실패·abandoned / 5 완료했으나 빈 결과("정직한 0").

## 도메인 인터페이스·산출물·데이터 흐름

- **search:** CLI가 런 디렉터리를 예약하고 슈퍼바이저를 detach(setsid, 별도 프로세스)로 띄운 뒤, 동기 모드면 `meta.state`를 `--wait`까지 폴링. 슈퍼바이저: 마커 붙인 프롬프트로 `aside exec` spawn → stdout을 `stdout.log`에 스트리밍 → DB에서 마커로 세션 확정(30초 데드라인) → 2초마다 부모·자식 JSONL을 커서 복사 → 프로세스 종료·stdout drain → 자식 terminal 확인(settle 10초) → 최종 복사 → `result.json` atomic → `meta.state`.
- **follow:** `log --follow`는 런 디렉터리 복사본을 tail하고 `meta.state`가 터미널이면 `run.<state>` 라인 후 exit. 백그라운드 Bash로 띄우면 종료 시 클로드가 깨어난다.
- **fetch:** Python이 URL 묶음(기본 8)을 `fetch_batch.js`에 JSON 인자로 주입 → repl이 URL별 타임아웃·전체 예산 안에서 allSettled → URL별 NDJSON(url, final_url, status, content_type, html|saved_path|error; 비HTML 응답은 `pwd`에 저장하고 경로만) → Python이 결정 12 순서로 판정: HTML은 defuddle, 저장된 문서 파일은 anydoc(결정 13) → 저장 → 실패·셸 URL은 `tab_one.js`로 단건 승격 → envelope 출력.
- **crawl:** `_crawl`이 sitemap(있으면)과 링크 BFS로 frontier를 만들되 fetch 응답은 response-provider(실제: `_page`의 repl 배치, 테스트: fixture)에서 받는다 → 페이지 저장 → `manifest.json`(url, file, title, status, depth, via).
- **트리거 표면:** `description`에 네이티브 툴 이름(WebSearch, WebFetch, web search, fetch a page, crawl, save as markdown)과 한국어 의도(검색해봐, 찾아봐, 웹에서, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체) 열거. near-miss: 로컬 파일·코드베이스 검색, 이미 아는 사실, codex 위임.

## 범위·비범위·제약

- 범위: 위 CLI 전부, SKILL.md, 테스트, 심링크 설치, README(한국어), harness-spec.md, .gitignore.
- 비범위: 네이티브 툴 deny/CLAUDE.md 강제, crawl4ai, `aside mcp` 등록, clipper 코드 이식, 스캔 PDF OCR(anydoc `--ocr hosted`·Firecrawl 키 — 성진 결정), 이미지·스크린샷, 데몬 쪽 런 중단(CLI에 수단 없음).
- 제약: stdlib Python(어떤 프로젝트에서도 설치 없이), Node는 변환에만, repl 120초·상태 미지속, 동시 세션 20(관측), 세션 다음 날 소멸, Bash 툴 기본 120초·최대 600초.
- 권한: 스킬 `allowed-tools`에 `Bash(python3 "<abs skill path>/scripts/ultra_search.py" *)`와 `Bash(aside repl *)`. codex 스킬의 함정(변수 경로·줄바꿈 continuation은 패턴 불일치)을 SKILL.md에 옮긴다.

## 성공 기준

- "X 최신 버전이 뭐야?"에 `search` 한 번으로 답과 출처 URL(동기, 60초 내).
- 3건 `--background` → `next`대로 arm → 종료 알림 → `result --group` 3건 completed. 실행만 하고 멈추는 경로가 동기 기본 + `next` 필드로 막혀 있다.
- 서브에이전트 조사에서 부모 침묵 중에도 `status`가 자식 N개 running과 `last_activity_at`을 보이고, 종료는 프로세스 종료로만 판정된다.
- 로그인 페이지(YouTube 구독 피드)를 `fetch`로 마크다운 저장.
- `crawl https://docs.aside.com` → 17개 `.md` + manifest(2분 내) — [목표].
- Aside 꺼짐 → `doctor`/각 커맨드 exit 3 + 복구 한 줄, 무한 대기 없음.
- 실패 조건: 빈 결과를 성공으로 보고, 침묵을 종료로 오판, 세션 소멸로 결과 유실, repl 120초를 데몬 장애로 보고, 한 URL의 지연으로 같은 배치의 성공분 유실, `stop`이 런을 멈췄다고 보고.

## 순서·의존성·단계별 완료 판정

각 단계는 `tdd` 스킬을 열어 seam을 합의한 뒤 테스트 → 구현. 코드 검증은 `codex` 스킬(gpt-5.6-sol high, `--sandbox read-only`)에 위임.

0. **골격** — 디렉터리 구조대로 빈 모듈·argparse(모든 인자 `help=`, 닫힌 값 `choices=`)·`page/package.json`·`tests/conftest.py`·`.gitignore`·`harness-spec.md`. 완료: `validate_harness.py --path .` 에러 0, 모든 서브커맨드 `--help`가 인자 전부 설명.
1. **`_store` + `_events`** — DB 조회·커서 복사·JSONL 파싱·필터·출처·인용·usage·렌더링. seam: fixture 파일 → 순수 함수, `ULTRA_SEARCH_ASIDE_HOME`=tmpdir. 완료: fixture 테스트 통과, 알 수 없는 형태에서 raw 강등, 부분 줄 미복사·목적지 비축소 테스트 통과.
2. **`_registry` + `_exec` + `_supervisor`** — id 예약, atomic meta, detach spawn, 마커 correlation, 상태 기계, orphans, `completed_unstructured`, `stop`(abandoned), `resume`(실행 중 거부). seam: `tests/fake_aside/aside` + `ASIDE_HOME` tmpdir; 필수 fixture — 동일 프롬프트 2건 병렬, DB 부재, 자식이 부모보다 오래 삶, stdout에 session_id 없음. 완료: 가짜 aside로 전 시나리오 통과, contract test가 argv·마커를 검증; 라이브: 실제 exec 2건 병렬 + 서브에이전트 프롬프트 종료 오판 없음.
3. **`_follow` + 동기 `search`** — `--wait` 초과 시 핸들+`next`, `log --follow` 터미널 라인·`--follow-timeout`·heartbeat·그룹 인터리브, `status`의 `last_activity_at`/`possibly_stalled`/`suspension`. 완료: 부모 침묵 60초+자식 활동 fixture에서 `possibly_stalled: false`, 활동 0 fixture에서 `true`, `--wait` 초과 후 런이 완료되어 `result` 수거 테스트 통과.
4. **`_extract` + `to_markdown.mjs` + `_repl` + `fetch`** — 판정 순서, 셸 임계, 문서 파일→anydoc 분기(exit 3→`needs_ocr`), frontmatter, envelope, URL별 격리·재시도·승격, `setup`/`doctor`. seam: HTML·문서 fixture → 골든 md; fake repl은 스니펫 이름별 NDJSON(중간 출력 후 타임아웃 fixture 포함). 완료: 골든 통과(PDF 영문·한글 포함), 배치 중 1건 타임아웃 시 나머지 7건 저장 테스트 통과; 라이브: docs 페이지·로그인 페이지·x.com(승격)·arXiv PDF fetch.
5. **`_crawl` + `map`/`crawl`** — sitemap(index 포함), BFS, glob, 상한, `--from`. seam: response-provider 주입(순수), 로컬 HTTP 서버는 contract test에만. 완료: fixture 사이트에서 depth/max/glob 정확; 라이브: docs.aside.com 17페이지 [목표].
6. **`repl-api`·`doctor` 마무리·SKILL.md** — `references/skills.md` 기준 description(트리거·near-miss 앞에), 본문은 exec vs repl 원리, arming 두 경로(백그라운드 follow / 마지막 턴이면 Bash 600초 + foreground follow), gotcha(120초와 오해 메시지, 세션 소멸, 서브에이전트 침묵, `stop`은 런을 못 멈춤, 봇 챌린지·googleSearch 불가). 완료: `validate_harness.py` 에러 0, description 1,536자 이내, 새 세션에서 "웹에서 찾아봐"가 트리거(수동), 그리고 아래 네 원칙 판정을 codex 리뷰가 항목별로 통과 처리.

   **네 원칙의 판정 기준(SKILL.md에 적용):**
   - *principle over rail* — "상황→커맨드" 표나 시나리오 열거가 없다. 규칙은 원리 하나(exec=판단이 필요한 조사, repl=결정적 읽기)와 실측 gotcha만이고, 각 gotcha는 "왜"가 붙어 있어 클로드가 열거되지 않은 경우를 스스로 재도출할 수 있다. 검색 프롬프트 지침도 "exec은 검색 API가 아니라 에이전트다 — 목적·선호 출처·답의 모양을 주면 된다" 한 원리 + 예시 둘.
   - *interface over document* — SKILL.md에 등장하는 커맨드·플래그는 전부 `--help`에 존재하고, 플래그의 의미·기본값은 SKILL.md에 없다(`--help`만이 진실). arming 관용구·`stop`의 한계·repl API는 각각 `next` 필드·`stop` 출력·`repl-api`라는 인터페이스가 나른다.
   - *for user not developer* — 커맨드는 클로드의 목적(검색·읽기·매핑·저장·상태) 단위. 세션 id·JSONL·DB·마커·모듈 이름 같은 구현 사정은 gotcha 설명에 불가피한 것(세션 소멸, 120초) 외에는 SKILL.md에 나오지 않는다.
   - *dense information* — 문장마다 "지우면 클로드가 틀리게 행동하는가?"를 물어 아니면 지운다. 모델이 이미 아는 것(Playwright, 백그라운드 Bash 알림의 원리, 마크다운)은 쓰지 않는다. 분량은 codex SKILL.md(17KB)보다 짧게.
7. **설치·검증·마무리** — 심링크, README, harness-spec Change history, codex 최종 리뷰, e2e(`run_e2e.py`, 성진 동의 후). 완료: 아래 시나리오 통과, `feat/ultra-search` → PR → squash 머지.

## 검증 시나리오

1. 단순 검색(동기): `search "현재 Python 3 안정 버전과 출처"` → 60초 내 답 + 출처 ≥1 + usage.
2. 병렬 백그라운드 3건: `search --background A B C` → `next` 명령을 백그라운드 Bash로 arm → 알림 → `result --group` 3건 completed.
3. 서브에이전트: 자식 2개 강제 프롬프트에서 `status`가 자식 running 2와 `possibly_stalled: false`, 최종 `run.completed`.
4. 로그인 페이지: `fetch https://www.youtube.com/feed/subscriptions --out ./x.md` → 구독 채널명 존재.
5. 크롤: `crawl https://docs.aside.com --out ./docs` → 17 파일 + manifest, frontmatter — [목표].
6. 장애: Aside 종료 상태에서 `doctor` exit 3, `search` 즉시 exit 3; 배치 중 1 URL을 60초 지연시키는 fixture에서 나머지 저장 + 지연 URL만 재시도 기록.
7. `stop`: 실행 중 런에 `stop` → 출력에 "daemon-side run continues" 명시, state `abandoned`, 이후 세션이 스스로 끝나면 `status`가 그 사실을 반영(복사본 갱신은 중단).

## 리스크·가정·비차단 유보

- **리스크 A:** 세션 저장소 스키마 변경. 완화: 결정 2의 강등 경로, fixture 테스트, `doctor` 버전 경고, `stdout.log` 보존.
- **리스크 B:** 봇 차단·Cloudflare가 `fetch`를 막음. 완화: 결정 12의 승격.
- **리스크 C:** exec 비용. 완화: `result`에 usage, SKILL.md에 "URL 읽기는 fetch, 검색·판단만 exec", `stop`이 비용을 못 멈춘다는 gotcha.
- **리스크 D:** 승인·MFA 대기로 런이 멈춤(문서상 존재, 이력 0건). 완화: `possibly_stalled`·`suspension` 표시, 판단은 클로드, 해제는 Aside UI.
- **가정 E(비차단, 2단계 라이브에서 확인):** 마커 줄이 에이전트의 답에 영향을 주지 않는다. 영향 시 마커를 더 짧게/끝으로.
- **가정 F(비차단, 2단계 라이브에서 확인):** 부모가 자식을 기다리지 않고 종료하는 경우가 있으면 `completed_with_orphans`가 이를 드러낸다(설계가 이미 흡수).
- **유보 1(비차단, 6단계):** `youtube.getTranscript`를 `fetch`의 YouTube 분기로 노출할지.
- **유보 2(비차단, 7단계):** 컴팩션 후에도 스킬을 잊지 않도록 전역 CLAUDE.md 한 줄 — 제안만, 이번엔 넣지 않음.
- **유보 3(비차단, v1.1):** 데몬 쪽 런 중단 수단 탐색(데몬 HTTP API는 인증 필요).
- **유보 4(비차단, v1.1):** 스캔 PDF OCR — anydoc `--ocr hosted`는 키 없이도 동작한다고 문서화되어 있으나 외부 전송이므로 성진 결정으로 제외. 필요해지면 `--ocr` 플래그 passthrough 한 줄.
