# Harness spec — Ultra-Search

이 저장소의 하네스가 무엇으로 이루어져 있고 왜 그렇게 되어 있는지에 대한 단일 출처. `audit_harness.py`가 이 파일과 디스크를 비교한다.

## 목적

클로드가 웹에서 무언가를 알아내야 할 때 네이티브 `WebSearch`/`WebFetch` 대신 집어드는 도구를 제공한다. 엔진은 성진의 로그인된 Aside 브라우저(`aside` CLI)다. 네이티브 툴이 못 하는 네 가지 — 로그인·봇차단 뒤의 페이지, 원문 전체, 사이트 단위 수집, 로컬 마크다운 저장 — 이 존재 이유다.

## 컴포넌트

| 계층 | 경로 | 왜 이 계층인가 |
|---|---|---|
| skill | `.claude/skills/ultra-search/` | 웹 조사라는 특정 작업이 생겼을 때만 필요한 절차·gotcha. `description`이 유일한 트리거 표면이다. |
| skill scripts | `.claude/skills/ultra-search/scripts/` | 사용법은 `--help`·`choices=`·출력 JSON이 가르치고 SKILL.md는 "언제·왜·무엇을 조심"만 쓴다(interface over document). |
| — | CLAUDE.md / rules / hooks / agents / workflows | **없음.** 강제 계층은 범위 밖(성진 결정). 트리거는 `description`이 전담한다. |

`.claude/settings.json`, `.codex/hooks.json`, `CLAUDE.md`, `AGENTS.md`는 graphify가 설치한 것으로 이 스킬과 무관하다.

### 스킬 내부 모듈

책임 하나·400줄 이하 원칙. 엔트리포인트는 argparse와 디스패치만.

| 모듈 | 책임 |
|---|---|
| `ultra_search.py` | argparse 배선·디스패치·종료 코드. 이 파일이 CLI 인터페이스 그 자체다. |
| `_errors.py` | 실패도 JSON 한 줄이라는 규약, 종료 코드와 복구 문구 |
| `_events.py` | `messages.jsonl` → 이벤트·출처·인용·usage·렌더링 |
| `_store.py` | aside 홈 읽기: 마커로 세션 발견, 커서 기반 복사, DB(선택적) |
| `_registry.py` | 런 디렉터리·id 예약(O_EXCL)·atomic meta·그룹·마커 |
| `_exec.py` | `aside exec` spawn과 슈퍼바이저 detach |
| `_supervisor.py` | 상태 기계: 세션 확정 → 동기화 → 종료 판정 → `result.json` |
| `_follow.py` | 유일한 watcher. 터미널 라인에서 exit하는 것이 제품이다. |
| `_run_cmds.py` | `search`·`resume` — 시작과 `next` 핸들 |
| `_watch_cmds.py` | `status`·`log`·`result`·`show`·`stop` |
| `_repl.py` | repl 스니펫 전송·NDJSON 회수·120초 오해 메시지 번역 |
| `_extract.py` | 응답 판정 순서, defuddle/anydoc 분기, frontmatter, 슬러그 |
| `_page.py` | `fetch` 오케스트레이션: 배치·재시도·승격·파일 쓰기 |
| `_crawl.py` | 순수 frontier 로직(sitemap·BFS·glob·상한) |
| `_crawl_cmds.py` | `map`·`crawl` |
| `_doctor.py` | `doctor`·`setup`·`repl-api` |
| `page/` | Node 변환: `to_markdown.mjs`(defuddle+linkedom), `snippets/*.js`, `package.json` |

## 설계 결정 중 재도출이 안 되는 것

1. **디스크가 진실, DB는 보조.** ephemeral CLI 세션은 `state.db`에 행을 전혀 남기지 않는다(2026-08-29 실측, 데몬 1.26.829). `messages.jsonl`은 온전히 남는다. 그래서 모든 DB 읽기는 부재를 정상으로 취급하고 None을 돌려준다.
2. **세션 correlation은 프롬프트 마커로.** CLI는 자기가 만든 세션 id를 알려주지 않고, 프롬프트 텍스트 일치로는 같은 질문의 병렬 실행 둘을 구분할 수 없다.
3. **종료 판정은 프로세스 종료 ∧ stdout drain.** 침묵은 근거가 아니고(서브에이전트), 프로세스를 죽여도 데몬 런은 계속되며, 세션은 아예 없을 수도 있다. 남는 모호함마다 별도 상태를 준다: `completed_with_orphans`, `completed_unstructured`, `abandoned`.
4. **`stop`은 감시만 끊는다.** 데몬 런을 멈출 CLI 수단이 없다(실측: SIGTERM/SIGINT 후에도 런 계속, 자식 세션 추가 생성). 출력과 help 양쪽에 명시한다.
5. **배치는 URL별 격리.** repl은 120초에 무조건 죽는다. 한 URL의 지연이 배치 전체를 날리지 않도록 URL별 타임아웃·전체 예산·즉시 출력·단건 재시도를 둔다.
6. **봇 챌린지 판정은 강·약 토큰 분리.** x.com은 평상시에도 Cloudflare JSD 스크립트를 싣는다 — `cdn-cgi/challenge-platform` 하나로 판정하면 CF 경유 사이트 상당수가 "차단됨"이 된다.
7. **셸 임계 80단어, CJK는 글자 수로.** 실측 보정: x.com 0, threads 9 ↔ docs 388, 연합뉴스 219, 위키백과 4355. 공백 토큰만 세면 한국어 페이지가 임계 밑으로 떨어진다.
8. **tab 승격 시 innerText도 받는다.** 기사 추출기는 기사가 아닌 페이지(구독 피드·받은편지함·대시보드 — 로그인 fetch의 존재 이유)에서 아무것도 못 찾는다.

## aside repl 샌드박스 제약 (실측)

없는 것: `URL`, `URLSearchParams`, `AbortController`, `Response`, `Headers`, `Blob`, `require`, `process`, `structuredClone`.
있는 것: `fetch`, `Buffer`, `fs`(프로미스 기반, `*Sync` 없음, 프로젝트·세션 루트 밖 쓰기 거부), `path`, `pwd`, `setTimeout`, `TextDecoder/Encoder`, `atob/btoa`, `openTab`/`closeTab`/`snapshot`/`page`, `aside`/`youtube`/`googleSearch`.

## 검증

`pytest tests/` — 143개, aside 없이 통과. 라이브 테스트는 `-m live`.

## Change history

### 2026-08-29 — 최초 생성
계획서 `.claude/plans/260829_ultra-search 스킬 구현 계획.md`대로 스킬 전체를 생성했다. 계획 대비 변경 셋:

- **결정 2·3·6의 메커니즘을 뒤집었다.** 계획은 `state.db`를 1차 correlation 표면으로 삼았으나, 실측 결과 ephemeral CLI 세션이 DB에 행을 남기지 않는다. 디스크 우선·DB 보조로 바꿨다. 계획 결정 2의 강등 경로와 리스크 A가 이 경우를 이미 흡수하도록 설계되어 있었으므로 의도는 그대로다.
- **모듈 둘을 추가했다** (`_run_cmds`, `_watch_cmds`, `_crawl_cmds`). 엔트리포인트를 200줄 이하로 유지하면서 각 모듈을 400줄 이하로 두려면 커맨드 계층이 필요했다.
- **챌린지 판정을 강·약 토큰으로 분리**했다(계획 결정 12는 토큰 목록 하나만 상정). x.com 실측에서 false positive가 나왔다.

검증 시나리오 1·2·3·4·5·7 통과. 6(Aside 종료 상태)은 앱을 끄지 않고 확인 가능한 범위만 검증했다.
