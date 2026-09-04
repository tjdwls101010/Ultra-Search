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
| `_events.py` | `messages.jsonl` → 이벤트·출처·인용·usage |
| `_render.py` | 이벤트 → 한 줄. 독자가 누구냐가 레벨을 정한다: `progress`는 위임한 감독자, `steps`·`full`은 워커를 되짚는 개발자 |
| `_store.py` | aside 홈 읽기: 마커로 세션 발견, 커서 기반 복사, DB(선택적) |
| `_registry.py` | 런 디렉터리·id 예약(O_EXCL)·atomic meta·그룹·마커 |
| `_exec.py` | `aside exec` spawn과 슈퍼바이저 detach |
| `_supervisor.py` | 상태 기계: 세션 확정 → 동기화 → 종료 판정 → `result.json` |
| `_follow.py` | 유일한 watcher. 터미널 라인에서 exit하는 것이 제품이다. |
| `_run_cmds.py` | `search`·`resume` — 시작과 `next` 핸들 |
| `_watch_cmds.py` | `status`·`log`·`result`·`show`·`stop`·`sessions` |
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
8. **`resume`은 임의의 aside 세션을 받는다.** 앱 UI나 맨 `aside exec`으로 시작한 대화도 이어받을 수 있어야 한다(성진 요청). 세션 id는 아무도 기억하지 못하므로 `sessions`가 첫 프롬프트와 함께 목록을 낸다 — 발견 표면이 없으면 그 역량은 없는 것과 같다.
9. **tab 승격 시 innerText도 받는다.** 기사 추출기는 기사가 아닌 페이지(구독 피드·받은편지함·대시보드 — 로그인 fetch의 존재 이유)에서 아무것도 못 찾는다.
10. **`log`의 기본 뷰는 감독자 것이다.** 실측(2026-09-04, 서브에이전트 3개 런): 옛 기본값 compact 출력 10,088자 중 감독자의 다음 행동을 바꾸는 줄은 19%였고 도구 인자가 49%였다. `follow`는 100초를 넘긴 런에만 쓰이므로 그 케이스가 전부다. 분류 기준은 도구 이름 목록이 아니라 "다음 행동(기다린다·수거한다·정체 의심·앱에서 취소)을 바꾸는가" — 모르는 도구는 이름·횟수로 떨어지고 오류와 서브에이전트 완료는 항상 남는다. 인자·경로·크기가 필요한 건 워커를 되짚는 개발자이고 그건 `steps`다.

## aside repl 샌드박스 제약 (실측)

없는 것: `URL`, `URLSearchParams`, `AbortController`, `Response`, `Headers`, `Blob`, `require`, `process`, `structuredClone`.
있는 것: `fetch`, `Buffer`, `fs`(프로미스 기반, `*Sync` 없음, 프로젝트·세션 루트 밖 쓰기 거부), `path`, `pwd`, `setTimeout`, `TextDecoder/Encoder`, `atob/btoa`, `openTab`/`closeTab`/`snapshot`/`page`, `aside`/`youtube`/`googleSearch`.

## 검증

`pytest tests/` — 184개, aside 없이 통과. 라이브 테스트는 `-m live`(14개, 실제 Aside 필요).

테스트가 **이름과 다른 것을 검증하지 않도록** 특히 신경 쓴 지점: 목적지 축소는 목적지를 줄여서 재현하고(소스가 아니라), 동일 프롬프트 병렬은 실제로 스레드로 동시에 돌리며, `next.command`는 문자열 검색이 아니라 실행해서 확인하고, "자식이 바쁜 부모"는 부모 파일의 mtime을 과거로 밀어 자식만이 판정 근거가 되게 한다.

## Change history

### 2026-08-29 — 최초 생성
계획서 `.claude/plans/260829_ultra-search 스킬 구현 계획.md`대로 스킬 전체를 생성했다. 계획 대비 변경 셋:

- **결정 2·3·6의 메커니즘을 뒤집었다.** 계획은 `state.db`를 1차 correlation 표면으로 삼았으나, 실측 결과 ephemeral CLI 세션이 DB에 행을 남기지 않는다. 디스크 우선·DB 보조로 바꿨다. 계획 결정 2의 강등 경로와 리스크 A가 이 경우를 이미 흡수하도록 설계되어 있었으므로 의도는 그대로다.
- **모듈 둘을 추가했다** (`_run_cmds`, `_watch_cmds`, `_crawl_cmds`). 엔트리포인트를 200줄 이하로 유지하면서 각 모듈을 400줄 이하로 두려면 커맨드 계층이 필요했다.
- **챌린지 판정을 강·약 토큰으로 분리**했다(계획 결정 12는 토큰 목록 하나만 상정). x.com 실측에서 false positive가 나왔다.

검증 시나리오 1·2·3·4·5·7 통과. 6(Aside 종료 상태)은 앱을 끄지 않고 확인 가능한 범위만 검증했다.

### 2026-08-30 — codex 적대적 리뷰 반영과 세션 이어받기

`gpt-5.6` 리뷰가 P1 6건을 짚었고 전부 고쳤다. 공통점은 **오류 없이 조용히 실패하던 것들**이라, 각각 회귀 테스트를 함께 넣었다.

- `sitemap.js`가 샌드박스에 없는 `AbortController`를 써서 sitemap 발견이 통째로 실패하고 링크 BFS로 조용히 강등됐다(docs.aside.com 실측 0개 → 18개). 스니펫 전체를 금지 전역 목록으로 검사하는 테스트를 추가했다.
- `--timeout`이 meta에만 기록되고 감독기가 읽지 않아 아무 효과가 없었다.
- `copy_new_lines`가 커서를 소스 기준으로만 봐서, 복사본이 잘리거나 지워지면 그 사이를 영영 건너뛰었다. 커서는 목적지를 기술한다는 것을 코드와 테스트 양쪽에 명시했다.
- `show --source`가 같은 URL의 첫 tool result를 집어 검색 스니펫을 원문 대신 돌려줄 수 있었다.
- `--format`이 네 형식을 약속하고 하나만 구현하고 있었다. 구현된 둘(`md`·`html`)로 줄이고, HTML이 아닌 응답에 `--format html`은 거부한다.
- `doctor`가 node·변환 모듈·세션 디렉터리 실패를 보고도 exit 0을 냈고, help가 약속한 계정 검사가 없었다. 둘 다 고쳤다.
- `meta.json`의 read-modify-write에 잠금이 없어 세 프로세스가 서로의 키를 덮어썼다. O_EXCL 잠금을 넣고, 감독기가 자기 pid를 직접 쓰게 해 경합 자체를 하나 없앴다.
- 빈 텍스트로 정상 종료한 자식을 orphan으로 오판하던 것도 고쳤다.

**세션 이어받기(성진 요청).** `resume`이 이제 ultra-search가 만든 런뿐 아니라 임의의 aside 세션 id를 받는다. 앱 UI나 맨 `aside exec`으로 시작한 대화를 그대로 이어간다. 발견 표면으로 `sessions` 커맨드를 추가했다(첫 프롬프트·ultra-search가 만든 것인지 표시·`--mine`·`--search`).

테스트 143 → 170개, 라이브 13 → 14개.

### 2026-08-30 — gpt-5.6-sol 리뷰 반영

두 번째 리뷰(`gpt-5.6-sol`, high)가 P1 3건·P2 6건과 `--help` 불일치 6건을 짚었다. 전부 반영했다.

- **resume이 이전 턴의 답을 이번 결과로 확정할 수 있었다.** 프로세스가 끝나도 새 답이 아직 안 왔으면 트랜스크립트의 마지막 assistant는 *직전* 턴의 답이다. 마커가 든 user 이벤트를 턴 경계로 삼아 그 뒤만 이번 런의 것으로 본다(새 런은 경계가 0이라 같은 코드가 그대로 맞는다). 이전 턴의 자식·usage·출처가 딸려오던 것도 같이 해결된다.
- **meta 잠금이 상호배제가 아니었다.** O_EXCL 센티넬은 타임아웃 뒤 잠금 없이 진행했고 stale 제거에 소유권 개념이 없었다. `fcntl.flock`으로 바꿨다 — 프로세스가 죽으면 커널이 놓으므로 stale 판정 자체가 필요 없다.
- **커서는 목적지 크기다.** `dst < cursor`(복사본 유실)만 보정하고 `dst > cursor`(append 뒤 기록 전 crash)를 놓쳐 레코드를 중복 복사할 수 있었다. 규칙을 "목적지 크기가 곧 커서"로 단순화했다.
- 자식 종료 판정이 마지막 assistant만 보고 그 뒤의 새 user 턴을 무시했다. 마지막 *이벤트*를 본다.
- 외부 세션 resume이 DB 행 없는 실행 중 세션을 통과시켰다 — DB가 없는 게 정상인 ephemeral 세션에서 항상 그렇다. 트랜스크립트의 턴 경계로 판정한다.
- `--format html`이 마크다운 변환기 성공에 묶여 있었고 `--print`는 마크다운을 돌려줬다. 원문 저장에 변환기는 필요 없고, `--print`는 파일과 같은 바이트를 낸다.
- `sessions --search/--mine`이 앞 페이지만 훑어 "없음"과 "더 뒤에 있음"을 구분 못 했다.
- sitemap이 `robots.txt`의 `Sitemap:` 지시를 못 읽고 XML 엔티티를 디코드하지 않았다.
- `doctor`가 빈 계정 목록을 로그인으로 보고, runs dir 쓰기 가능 여부를 확인하지 않았다.
- `--help` 과장 6건을 실제 동작에 맞췄다(`--format html`은 tab 경로에서 렌더링된 DOM, `map --out`은 stdout에도 출력, `show --item`은 tool result 순번, `result`는 각주가 아니라 인라인 괄호 URL, `doctor`가 볼 수 없는 것 명시). 아무 효과 없던 `--last` 플래그는 없앴다.

테스트 170 → 184개. 각 수정마다 "고치기 전에는 실패하는가"를 확인했다 — 예: 프로세스 8개 동시 갱신 테스트는 잠금을 빼면 8개 중 6개가 유실된다.

### 2026-09-04 — `follow`를 감독자 뷰로

성진 관찰: `follow`가 넘기는 것이 워커의 `bash()` 인자까지 전부라 위임의 컨텍스트 절약분을 도로 먹는다. 기록 런 6개로 실측해 결정 10을 세우고 `--level`을 `progress`(새 기본)·`steps`(옛 compact)·`full`(옛 normal)·`raw`로 교체했다. 옛 `full`(200KB 클립)은 `raw`와 구분이 없어 없앴다. `next.command`는 레벨을 지정하지 않으므로 손대지 않았다.

- 렌더링을 `_events.py`에서 `_render.py`로 분리했다(400줄 원칙). 분류 원칙은 그 모듈 docstring에 있다.
- Aside가 서브에이전트 완료를 남기는 `system-message` 레코드를 이벤트 종류 `system`으로 인식한다. 전에는 raw JSON 200자로 떨어져 가장 감독자스러운 정보가 가장 안 읽혔다.
- 한 이벤트가 여러 줄로 렌더될 때 `[child …]` 접두사가 첫 줄에만 붙던 것을 `_drain`에서 고쳤다.
- SKILL.md에는 이 뷰가 무엇이고 나머지가 어디 있는지 한 절만 넣었다. 레벨 정의는 `--help`가 낸다.

서브에이전트 런 재렌더: compact 10,088자 → progress 2,822자. 테스트 184 → 189개(기록 런 fixture와 옛 compact 출력을 golden으로 고정).
