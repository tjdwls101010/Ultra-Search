# ultra-search 스킬 재구성 계획 (v1.0.0 릴리즈까지)

## Context

`ultra-search`는 로그인된 Aside 브라우저로 웹을 조사(`search`)·읽기(`fetch`)·수집(`map`/`crawl`)하는 프로젝트 스킬이다(`~/.claude/skills/ultra-search` → 이 레포로 심볼릭 링크). 성진은 skill-maker의 네 프레임(principle over rail, interface over document, for the model not the maintainer, dense)이 온전히 반영됐는지 총체 점검하고, 유지보수성·이식성을 높이는 구조로 다듬은 뒤 GitHub 릴리즈까지 하길 원한다. 성공 기준은 품질이다.

계획 세션에서 코드 17개 파일 전부를 읽고, 테스트를 실측(`202 passed, 14 skipped`, 72초)하고, codex(gpt-6-astra medium) 독립 감사를 받아 발견 사항을 코드로 재확인했다. 결론: 코드 품질은 높고 실측으로 다져진 경계 사례가 많아 **완전 재작성은 하지 않는다.** 실제 문제는 파일 배치가 아니라 (1) 명령마다 다른 증거 범위, (2) 오해를 부르는 성공 신호, (3) 일부 위험한 저장 동작, (4) 하드코딩된 권한 경로다. 그래서 **테스트를 공개 경계로 먼저 옮기고 → 결함을 재현 테스트로 고치고 → 공유 계약을 통합하고 → 디렉터리를 기계적으로 옮기고 → 인터페이스를 다듬고 → 문서를 쓴다.**

## 합의 원장

| 구분 | 내용 | 근거 |
|---|---|---|
| 결정 | 이식 범위는 "성진의 여러 Mac"(git clone + 심볼릭 링크). 플러그인 배포·Windows는 범위 밖 | 성진 |
| 결정 | 행동 보존 리팩터링 + 확인된 결함 수정. 완전 재작성 아님 | 성진(감사 결과 확인 후) |
| 결정 | 진입점 `scripts/cli.py` + 패키지 `scripts/ultra_search/`, 기준은 "무엇이 바뀌면 함께 바뀌는가" | 성진 |
| 결정 | 테스트는 레포 루트 `tests/` 유지. S1 CLI 경계 중심, S3(순수 모듈 테스트)도 CLI 경계로 재작성, CLI로 결정적 관찰이 불가한 저장 성질은 S2 런 디렉터리 경계 | 성진 |
| 결정 | map/crawl 출력은 요약+핸들(cheap signal first). 재-crawl은 비어있지 않은 폴더면 거부, `--replace` 없음 | 성진 |
| 결정 | SKILL.md·`--help`는 영어 유지 | 성진 |
| 결정 | 직접 브라우저 스크립팅: 본문은 "언제"만, "방법"은 `repl-api` 출력이 소유 | 성진 |
| 결정 | 빠진 판단 4개: `opened` 의미·변환 충실도 → `--help`/필드, 위임 권한 경계 → CLI가 조사 프롬프트에 자동 첨부, 완료 기준·"확보한 것만 증거" → 본문 기존 불릿에 병합 | 성진 |
| 결정 | PR 6개(아래 순서), 매 PR 스쿼시 머지 → graphify 리빌드 main 직접 커밋 → 마지막에 `v1.0.0` GitHub 릴리즈(한국어 노트) | 성진 |
| 결정 | 구현 중 codex 리뷰: gpt-6-astra **high**, PR마다 1회 + 최종 스킬 텍스트 4프레임 리뷰 1회 | 성진 |
| 결정 | 행동 검증: 격리 `claude -p`, search는 fake Aside, fetch는 실제 브라우저(무료). 실제 search는 돌리지 않음 | 성진 |
| 결정 | 푸시 범위: `.claude/harness-spec.md` 삭제 반영 + `.claude/plans/` 커밋. `.claude/settings.json`은 커밋하지 않고 로컬에 둔다(gitignore도 추가하지 않음). 하네스용 심볼릭 링크 `users-seongjin-coding-ultra-search-clau-recursive-knuth.md`는 커밋하지 않고 구현 시작 시 삭제 | 성진 |
| 결정 | 진입점 이름은 `cli.py`(PEP 8 모듈 관행, 도구 이름은 디렉터리가 이미 말함, 테스트가 import로 호출 가능). `cli_ultra-search.py`는 하이픈 때문에 import 불가라 기각 | 성진 |
| 결정 | `result`는 단일 런도 항상 `runs` 배열. search/resume 프롬프트에 "Read-only research: do not post, purchase, sign up, or change account settings." 자동 첨부(해제 플래그 없음) | 성진 |
| 결정 | 계획 검증: codex(gpt-6-astra medium)의 계획 점검 9건을 코드·`claude --help`로 재확인 후 전부 반영 | 계획 세션 |
| 사실 | `${CLAUDE_SKILL_DIR}`는 SKILL.md 본문과 `allowed-tools` 둘 다에서 확장된다(code.claude.com/docs/en/skills.md). 심볼릭 링크 경로로 확장되는지 실제 경로로 확장되는지는 문서에 없음 → 구현 때 실측 | claude-code-guide |
| 사실 | 권한 규칙은 명령 **텍스트**와 매칭한다. 따옴표 유무가 다르면 매칭 실패 → 본문의 명령 표기와 규칙 표기를 똑같이 유지 | permissions.md |
| 사실 | 레포는 PUBLIC, 태그·릴리즈 없음, 원격 `tjdwls101010/Ultra-Search` | `gh` |
| 가정 | 다른 Mac에서도 Aside 계정 디렉터리는 `u/0`, 데몬 포트는 21420. 상수는 `aside/` 한 곳에 모으고 바꾸지 않는다 | 추론 |

## 최종 스킬 디렉터리 구조

```
.claude/skills/ultra-search/
├── SKILL.md
└── scripts/
    ├── cli.py                      # 유일한 진입점: argparse(=계약), 디스패치, JSON 오류 봉투(인자 오류 포함)
    └── ultra_search/
        ├── __init__.py             # __version__ = "1.0.0"
        ├── contract.py             # EXIT_*·TERMINAL_STATES·UltraSearchError 계열 — 정의는 여기 한 곳
        ├── doctor.py               # doctor · setup(npm ci) · repl-api
        ├── aside/                  # Aside 비공개 표면. Aside가 바뀌면 여기만 본다
        │   ├── __init__.py
        │   ├── process.py          # aside_bin, exec argv, spawn, version, VERIFIED_*, DAEMON_URL   (← _exec)
        │   ├── sessions.py         # ~/.aside·u/0·state.db·마커 탐색·copy_new_lines            (← _store)
        │   ├── transcript.py       # messages.jsonl → Event/Source 파싱                         (← _events 파싱부)
        │   └── repl.py             # 스니펫 실행기·ReplTimeout·NDJSON                           (← _repl 실행부)
        ├── runs/                   # search · resume · status · log · result · show · stop · sessions
        │   ├── __init__.py
        │   ├── commands.py         # 8개 명령 핸들러, next_step, run_summary                    (← _run_cmds + _watch_cmds)
        │   ├── registry.py         # 런 디렉터리·id 예약·meta 락·run id 검증                    (← _registry)
        │   ├── supervisor.py       # 분리 실행 상태기계                                         (← _supervisor)
        │   ├── evidence.py         # 런 범위 증거 뷰: 턴 경계·답·출처·사용량·자식 병합 — result/show/status/log 공용 (새, 중복 통합)
        │   ├── follow.py           #                                                            (← _follow)
        │   └── render.py           #                                                            (← _render)
        └── pages/                  # fetch · map · crawl
            ├── __init__.py
            ├── commands.py         # fetch/map/crawl 핸들러                                     (← _page 명령부 + _crawl_cmds)
            ├── acquire.py          # 배치·재시도·탭 승격·저장·이름 예약                         (← _page 작업부)
            ├── classify.py         # 응답 판정·마크다운화                                       (← _extract)
            ├── discover.py         # URL 선택(순수)                                             (← _crawl)
            ├── browser.py          # fetch_batch·tab_one·sitemap·links 래퍼, resolve_links      (← _repl 래퍼부)
            ├── snippets/           # fetch_batch.js · tab_one.js · sitemap.js · links.js        (cleanup_tabs.js 삭제)
            └── converter/          # package.json · package-lock.json · to_markdown.mjs · node_modules/(gitignored)
```

- 나누는 기준: `aside/`는 **어떻게 Aside와 말하는가**(프로세스·디스크 형식·REPL 전송), `runs/`·`pages/`는 **무엇을 시키는가**(명령군). 스니펫은 페이지 확보 알고리즘이므로 `pages/`, 실행기는 `aside/`.
- 분리 실행 supervisor는 `[sys.executable, "-m", "ultra_search.runs.supervisor", "--run-path", <절대경로>]`, `cwd`=런 디렉터리, 환경변수 `PYTHONPATH`=`scripts/` 절대경로로 띄운다. 파일 기반 stdout, `stdin=DEVNULL`, `start_new_session=True`는 유지.
- `cli.py`는 `Path(__file__).absolute()`(심볼릭 링크 보존)로 `next` 명령을 만들고, 모듈·자원 경로는 `resolve()`로 찾는다 — 이 구분은 기존 계약이며 유지한다.
- 옮기지 않는 것: `.ultra-search/` 사용자 데이터 레이아웃(runs/·pages/·crawls/), 저장된 `meta.json`/`result.json` 형식, 테스트·fixture(스킬 밖).

## 테스트 구조 (seam 합의 반영)

```
tests/
├── conftest.py              # scripts/ 절대경로를 sys.path에 한 번. aside_home·runs_dir·fake_aside 픽스처
├── fake_aside/aside         # + REPL 라우팅: 코드 첫 줄 `const ARGS = {...}`를 JSON으로 읽고, 스니펫 첫 줄 태그(`// snippet: fetch_batch`)로 스니펫을 식별해 URL별 녹화 응답을 돌려준다
├── fixtures/                # 기존 + repl 라우트(JSON: 스니펫 → URL → 레코드)
├── test_research.py         # S1: search·resume·status·log·result·show·stop·sessions   (← test_commands 일부, test_events, test_follow, test_store의 관찰 가능한 부분)
├── test_pages.py            # S1: fetch·map·crawl                                     (← test_page, test_extract, test_crawl)
├── test_environment.py      # S1: doctor·setup·repl-api·인자 오류 JSON·종료 코드
├── test_run_directory.py    # S2: supervise() → result.json/meta.json, 프로세스 간 flock, 복사 커서 드리프트, 반쪽 줄, run id 동시 예약, 마커 지연  (← test_supervisor, test_registry·test_store의 저장 성질)
├── test_contract_fake_aside.py  # 대역 자체의 계약(유지·REPL 라우팅 추가)
└── live/test_live.py        # 실제 Aside(-m live) — fetch 계열만 실행
```

- S1: argv → stdout JSON + 종료 코드. 대역은 외부 경계인 fake Aside 하나. 반환된 `next`는 셸로 실제 실행해 확인. node 변환기는 실물을 쓴다.
- S2: 영속화 자체가 계약인 성질만. 디스크를 읽는 것이 우회가 아니다.
- 대역이 가리는 것: 스니펫 JS 자체와 fake/실제 Aside 차이는 `-m live`(fetch 계열)로만 확인한다. **실제 search 경로는 이번에 검증하지 않은 채 남고 릴리즈 노트에 적는다.**
- 기대값은 녹화 fixture·명세에서 가져오고 현재 출력에서 베끼지 않는다.

## SKILL.md 섹션 구조 (영어, references 없음)

```
---
name: ultra-search
description: <현 트리거 문구 유지. 경계만 조정: "Not for local files or codebase search, facts already known, browser actions unrelated to acquiring web content, or delegating non-web work to another model (codex).">
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)
---
# Web work through the user's own browser
  진입점 한 문단: 확장된 절대경로·큰따옴표·한 줄(권한 패턴이 명령 텍스트와 매칭되므로), `--help`가 입력·출력·복구를 소유, 반환된 명령을 재구성하지 말 것
## Choose by the work still needed
  search(출처 선택·조사가 남음, 구독 소모) vs fetch(알려진 페이지 읽기) / 확보한 증거 재사용(result·show) / crawl 전에 map / resume은 이전 발견이 맥락일 때 /
  CLI로 못 얻는 내용(상호작용 뒤에만 나오는 것)은 `repl-api`로 설치된 API를 확인해 직접 스크립트 — 검색에는 쓰지 않는다(자동화된 검색 질의가 봇 차단을 부른다)
## Delegate an objective, not keywords
  목표·출처 제약·원하는 증거를 주고 브라우징 순서는 주지 않는다 / 예시 1개(Postgres 17) / 부정적 발견 허용 ≠ 산출물 없음
## Follow state, not silence
  감시 종료 ≠ 조사 완료, 최신 `next`를 따름, 알림 받을 주체가 없으면 포그라운드 / 감독 비용 < 위임한 일, 조용한 부모 ≠ 멈춤
## Boundaries that affect the answer
  - Watching is not cancellation (조사 범위를 시작 전에 한정)
  - Only acquired content is evidence (fetch는 item status, search는 opened; 목록에 뜬 검색 결과는 단서) ← 기존 "HTTP success" 불릿을 넓힘
  - Partial evidence is not a complete investigation + 완료 기준(출처 있는 증거로 답했거나 구체적 증거 공백을 보고했을 때; 에이전트를 띄운 것·URL을 모은 것은 완료가 아님)
  - Requests act as the user
  마지막 줄: 실패 시 복구 메시지, 환경이 불분명하면 doctor
```

- references를 두지 않는 이유: 모든 경로가 본문 전체를 필요로 하고, 한 분기에만 필요한 내용(직접 스크립팅)은 한 줄 포인터 + `repl-api` 인터페이스로 충분하다.
- 삭제·변경: "googleSearch has hit bot challenges"(발견 이력) → 이유 문장으로 대체. 도구 필드 설명(`--help`와 중복되는 것)은 본문에서 뺀다.
- 개발 기록(감사 출처, 기각한 대안, 어떤 모델이 무엇을 틀렸는지)은 PR 본문·커밋 본문과 이 계획 파일에 둔다. 스킬에는 넣지 않는다.

## 결함 목록 (PR②, 각각 재현 테스트 먼저)

| # | 결함 | seam | 기대 동작 |
|---|---|---|---|
| D1 | resume 뒤 `show`·`status`가 이전 턴 전체를 읽음(`_watch_cmds._usage`, `_show`) | S1 | `evidence.py` 한 뷰로 result·show·status·log가 같은 턴·자식 범위를 봄. 자식 전용 출처도 `show` 가능 |
| D2 | 새 마커가 안 보이면 `turn_start_index`가 0으로 떨어져 이전 답을 확정 | S2 | "턴 미관측"을 명시적으로 반환. supervisor는 이전 턴을 결과로 쓰지 않음 |
| D3 | `final_answer`가 종료되지 않은 턴(stopReason=toolUse)의 텍스트도 채택 | S2 | 종료된 assistant 턴의 텍스트만. 마지막 턴이 비었으면 답은 "" |
| D4 | 재-crawl이 `000-*.md`를 덮어씀(`_crawl_cmds.py:128`의 rename) | S1 | `--out` 폴더가 비어 있지 않으면(manifest 유무와 무관) 저장 전에 `bad_arguments`+fix(다른 `--out`). 기본 경로는 `crawls/<host>/<타임스탬프>/`. 최종 이름을 쓰기 전에 예약. 재현 테스트는 manifest 있는 폴더와 manifest 없는 비어 있지 않은 폴더 둘 다 |
| D5 | `--run`·`show --run`·`resume` 대상 run id가 경로 탈출 가능(`_registry.py:214`), 자식 id가 경로에 그대로 들어감(`_registry.py:62`). `--group`은 메타데이터 비교라 해당 없음 | S1 | run id·자식 id 형식 검증 + 레지스트리 내부 포함 검사 |
| D6 | 레지스트리 run(특히 abandoned)의 resume이 실시간 세션 검사를 건너뜀 | S1 | 어떤 경로로 고른 세션이든 같은 실시간 검사 |
| D7 | `map`이 탐색 실패를 숨김(403 전부여도 root 1개 성공) | S1 | 커버리지(놓친 페이지·예산 초과·sitemap 여부)를 응답에 포함, 0 확보면 EXIT_EMPTY |
| D8 | fetch 판정: HTML은 저장됐는데 상태 shell→종료 4 / 빈 본문인데 `ok` | S1 | 확보·추출·파일 생성을 따로 기록. 파일을 쓴 항목은 성공으로 셈, 빈 본문은 `ok` 아님 |
| D9 | 자식 출처 병합이 `opened`·id를 잃음 | S1 | URL 병합 시 `opened`는 OR, id는 모두 보존해 인용 해석 |
| D10 | 잘못된 커서·manifest 형식·storage OSError가 JSON 계약 밖으로 트레이스백 | S1 | `bad_arguments`/`run_failed` JSON |
| D11 | 동일 출처 판정이 netloc만 비교(ftp 등 통과) | S1(map) | scheme+host+port 비교, http(s)만 |
| D12 | `stop`이 대기 중 정상 완료된 런을 abandoned로 덮어씀 | S2 | 어떤 종료 상태든 도달하면 덮어쓰지 않음 |
| D13 | heartbeat의 children이 살아있는 자식이 아니라 전체 자식 수 | S1 | 비종료 자식 수 |
| D14 | doctor의 repl 왕복이 `{ok:true}`·종료 코드를 확인하지 않음, 고정 `.write-probe` 파일명 | S1 | 둘 다 확인, 임시 파일은 고유 이름 |

기각한 지적(기록용): 락 경합 후 무잠금 쓰기(종료 상태 기록 우선이라는 의도된 트레이드오프, `meta_lock_contended` 표식 유지), 챌린지 문구 휴리스틱 오탐(실측 근거 없음), Windows/fcntl(범위 밖), 동적 모델 id enum화(고정하면 낡음).

## 인터페이스 변경 (PR⑤)

- 인자 오류도 JSON 봉투: `ArgumentParser.error`를 재정의해 `{"ok":false,"error":"bad_arguments","message","fix":"<명령> --help"}` + 종료 2. 최상위 docstring의 "항상 JSON" 약속을 사실로 만든다.
- `result`는 단일 런도 항상 `runs` 배열(search·status와 같은 모양). `--help`에 상태 값(completed, completed_with_orphans, completed_unstructured, failed, abandoned)과 `opened`의 정의("페이지를 여는 도구를 거쳤다는 추정. 내용 확보·교차검증 아님")를 적는다.
- `fetch --help`: 항목 상태의 닫힌 목록(ok, shell, shell_escalated, challenge, blocked, needs_ocr, unsupported, error)과 각 뜻, 마크다운 변환이 표·그림·레이아웃을 잃을 수 있고 `--format html`/`original_path`가 원본을 보존한다는 것, auto 승격 조건(shell과 challenge 둘 다).
- `map`: 항상 manifest를 `.ultra-search/maps/<host>-<타임스탬프>.json`(또는 `--out`)에 저장. stdout은 `count`·커버리지·샘플 10개·`manifest_path`. 전체 목록은 `--list-all`. 도움말의 "without fetching"을 "without extracting or saving pages"로 정정.
- `crawl`: stdout은 상태별 개수 + ok가 아닌 항목 + `manifest`·`out_dir`. `--from`일 때 적용되는 플래그(`--max-pages`·`--via`·`--concurrency`·`--no-frontmatter`·`--out`)를 명시하고 탐색 플래그를 함께 주면 거부. manifest의 `depth`를 실제로 기록하거나 필드를 뺀다(탐색이 depth를 이미 알고 있으면 기록).
- `log --level steps`: 도구 결과마다 `#N` 서수를 출력해 `show --item N`과 맞춘다. `--source` 도움말에 0부터 셈을 명시.
- `search`/`resume`: 모든 프롬프트 끝에 마커와 함께 범위 한 줄("Read-only research: do not post, purchase, sign up, or change account settings.")을 붙이고 `--help`에 그 사실을 적는다.
- `repl-api`: repl 도구만 골라 출력하고 실행 형태(`aside repl '<code>'`, 사전 승인 없음)를 함께 준다. 전체 목록은 `--all`.
- `next`: "run_in_background는 완료 알림을 받을 주체가 있을 때의 권고, 없으면 같은 명령을 포그라운드로 bash_timeout_ms와 함께" — `NEXT_HELP`와 SKILL.md의 모순 제거.
- 반복 도움말("As for `search`")은 공유 헬퍼로 각 명령에 전문을 넣는다(`_add_discovery_opts`, `_add_fetch_opts`, `_add_wait_opts`).
- `--runs-dir` 도움말: "current project" → "current working directory".
- 숫자 인자 범위 검증(음수 limit, 0 이하 concurrency, nan/inf 거부), URL은 http(s)만.
- `doctor`: node 버전이 lockfile 요구(>=20.19)를 만족하는지 확인. `setup`은 `npm ci`, 타임아웃·OSError도 JSON.
- `--version`: `ultra-search 1.0.0`(`ultra_search.__version__`).

## PR 단계와 완료 판정

각 단계 시작 시 `TaskCreate`에 아래 완료 판정을 그대로 적고, 끝낼 때 `TaskUpdate`. 브랜치는 `main`에서 새로 판다. 커밋·PR 제목은 `<타입>: <한국어 제목>`, PR 본문은 `## 무엇을 바꿨나`/`## 왜`/`## 영향`/`## 검증`(`## 검증`에는 실행한 명령과 수치). 각 PR은 codex gpt-6-astra high 리뷰(read-only)를 받고, 리뷰 종료 조건은 "일상적 단일 세션 사용에서 도달 가능한 CONFIRMED 결함 0건"(발견 0건이 아님). 받은 지적은 선별하고 기각 이유는 PR 본문에 남긴다. 스쿼시 머지 직후 `Graphify` 스킬로 리빌드해 main에 `chore: 그래프 갱신` 직접 커밋.

0. **준비** — 하네스용 심볼릭 링크 삭제, `tdd` 스킬 호출(seam은 위에서 합의됨), 기준선 `python3 -m pytest tests/ -q` 실측 기록.
   완료 판정: 기준선 `202 passed, 14 skipped` 재현.
1. **PR① `test/public-seams`** — `test: 테스트를 공개 경계로 재작성` — fake Aside REPL 라우팅 추가, S3 테스트를 S1(`test_pages.py`·`test_research.py`·`test_environment.py`)로, 저장 성질을 S2(`test_run_directory.py`)로 옮김. `test_contract_fake_aside.py`의 대역 호환성 검증(현재 `_events`·`_store` 직접 import)도 CLI `result`·`log` 관찰로 재작성. doctor의 데몬 HTTP 확인(`_doctor.py:200`)은 외부 경계라 `ULTRA_SEARCH_DAEMON_URL` 환경변수 재정의를 추가하고 테스트가 로컬 임시 HTTP 서버(ready 응답)를 띄운다 — fake account의 빈 계정 시나리오로 로그아웃 판정(`test_commands.py:689`)과 D14를 결정적으로 재현. 스니펫 첫 줄 태그와 이 환경변수 외 제품 코드 변경 없음. 이 PR에서만 `_page._needs_retry`의 `"not in fixture"` 의존을 대역 쪽 실제 오류 계약으로 대체.
   완료 판정: 전체 녹색. 기존 테스트가 검증하던 행동 목록(파일별 test 이름 대조표를 PR 본문에)에 누락 0. `tests/`에서 `scripts/` 내부 모듈 import는 S2 파일에만 존재(`grep`으로 확인).
2. **PR② `fix/evidence-and-storage`** — `fix: 런 범위 증거와 저장 결함 수정` — D1~D14, 결함마다 red(의도한 이유로 실패 확인) → green.
   완료 판정: 결함마다 재현 테스트가 수정 전 실패·수정 후 통과, 전체 녹색.
3. **PR③ `refactor/shared-contracts`** — `refactor: 공유 계약 통합과 죽은 코드 제거` — 종료 코드·TERMINAL_STATES·원자적 JSON 쓰기·사용량 합산·활동 시각 계산을 한 곳으로. 삭제: `cleanup_tabs()`+`cleanup_tabs.js`(+`tab_one.js`의 관련 주석), `db_child_rows`, `db_finished_at`, `last_timestamp`, `SESSION_LIFETIME_NOTE`, `_RETRYABLE`, `_DOC_EXTENSIONS`, `ultra_search.py`의 `LEVEL_CHOICES`(`_render.LEVELS`를 유지하고 CLI가 import), `EmptyResult`, `fetch_batch(save_dir)`, supervisor의 테스트 전용 `stop_after`, 미사용 import.
   완료 판정: 전체 녹색, 위 삭제 심볼 `grep` 0건(유지하는 `LEVELS` 제외), 각 계약 상수의 정의 1곳.
4. **PR④ `refactor/package-layout`** — `refactor: scripts를 cli.py와 도메인 패키지로 재배치` — 위 트리대로 `git mv` 중심 이동, supervisor `-m` 실행, SKILL.md frontmatter와 본문의 진입점 경로(현재 `SKILL.md:12`)를 `${CLAUDE_SKILL_DIR}/scripts/cli.py`로 치환, README 설치 명령 갱신. 본문 재작성은 PR⑥. `ultra_search.py`는 남기지 않는다(이전 릴리즈 없음).
   완료 판정: 전체 녹색. 무관한 디렉터리에서 심볼릭 링크 경로로 `search --background` → 반환된 `next` 실행 → `result`까지 fake Aside로 통과. `git log --follow`로 주요 파일 이력 추적 가능.
5. **PR⑤ `feat/interface-contracts`** — `feat: 요약 우선 출력과 도움말 계약 정비` — "인터페이스 변경" 전체, 변경마다 S1 테스트 먼저. 수정한 모든 `--help`는 실행해 출력에서 의미 단위가 한 줄인지 확인.
   완료 판정: 전체 녹색, 각 명령 `--help`에 "As for" 0건, 인자 오류가 JSON, `map`의 stdout이 URL 수와 무관하게 요약 크기.
6. **PR⑥ `docs/skill-text-v1`** — `docs: 스킬 본문을 네 프레임에 맞게 재작성` — SKILL.md(위 구조), README(설치 경로·`cli.py`·테스트 수·삭제된 harness-spec 링크 정리·`--version`), `.claude/harness-spec.md` 삭제 반영, `.claude/plans/` 커밋(이 계획 포함, `.claude/settings.json` 제외).
   완료 판정: 아래 "스킬 완료 조건" 전부 충족 후 머지.
7. **릴리즈** — 머지·그래프 갱신 후 `git tag v1.0.0` 푸시 + `gh release create v1.0.0 --title "v1.0.0" --notes-file <한국어 노트>`(무엇을 할 수 있나 / 설치 / 이번에 바뀐 것 / 검증한 것과 검증하지 않은 것(실제 search 경로) / 전제: Aside·Node>=20.19).
   완료 판정: `gh release view v1.0.0` 성공, `git status`가 `.claude/settings.json`만 미추적으로 남음, 원격 main과 로컬 main 일치.

## 스킬 완료 조건 (skill-maker)

- 성진이 SKILL.md 전문을 승인(AskUserQuestion로 전문 제시, 침묵은 승인 아님).
- 행동 검증(S4): 격리 디렉터리에서 `claude -p --tools Bash,Read --permission-mode default --output-format json`으로(`--safe-mode`는 스킬을 끄고 `--restricted`는 Bash를 빼므로 쓰지 않는다; 비교 대상 스킬 하나만 로드되도록 격리하는 방법 — 예: 비교 동안 `~/.claude/skills/ultra-search` 링크를 비교 대상 사본으로 가리킴 — 을 먼저 실측하고 기록), **기존 SKILL.md 대 새 SKILL.md**를 같은 과제로 비교(스킬 없음은 CLI를 모르므로 대조군이 안 됨). 과제와 판정: (T1) 알려진 URL 요약 → `fetch`만 쓰고 `search`를 쓰지 않음 (T2) 출처 선택이 필요한 질문 → 목표·출처 제약·증거를 담은 `search` 프롬프트 (T3) fake `slow` 시나리오 → 감시 종료를 완료로 보고하지 않고 `next`로 `result`까지 수거 (T4) fake REPL이 challenge를 돌려주는 fetch → 그 출처를 읽은 것으로 인용하지 않음. `permission_denials`로 실패한 실행은 판정에서 빼고 입력을 보충해 재실행. 새 텍스트가 어느 과제에서도 기존보다 나쁘지 않을 것.
- 권한 실측: 기본 권한 모드에서 `${CLAUDE_SKILL_DIR}` 규칙이 심볼릭 링크 설치의 실제 호출과 매칭되는지(`permission_denials` 없음) 확인. 심볼릭 링크 경로와 실제 경로 중 어느 쪽으로 확장되는지 기록.
- `claude plugin validate --strict .claude/skills` 종료 0(심볼릭 링크를 해석한 실제 부모 디렉터리에 대해).
- 프로젝트에서 `claude -p "/skill-doctor"`로 트리거가 겹치는 이웃 스킬 확인, 겹치면 양쪽 description에 경계.
- 최종 SKILL.md를 codex gpt-6-astra high가 네 프레임으로 리뷰, 선별 반영.
- `python3 -m pytest tests/ -q` 전체 녹색, `python3 -m pytest tests/ -m live -k "not simple_search and not session_started_outside and not real_binary_writes_a_transcript"` 통과(Aside 실행 중 — 실제 `aside exec`를 부르는 세 개(search·resume·대역 계약)만 제외하고 — 선택된 테스트에서 실제 `aside exec` 호출 0건을 확인 — fetch·탭 승격·로그인 피드·PDF·crawl·map·repl-api·doctor·바이너리 부재는 실행).

## 재사용할 기존 자산

- `tests/fake_aside/aside`의 시나리오(simple·slow·subagent·orphan·fail·empty·negative·no_session·aside_down·repl_timeout)와 `FAKE_ASIDE_CALLS` argv 기록.
- `tests/fixtures/`의 녹화 세션·HTML·PDF, `tests/conftest.py`의 격리 픽스처(실제 `~/.aside`를 절대 읽지 않음).
- `_events.turn_start_index`·`child_session_ids`·`collect_sources`, `_follow.parse_since`/`format_cursor`, `_watch_cmds.next_step` 생성 경로 — `evidence.py`·`commands.py`로 옮기되 새로 쓰지 않는다.
- `_registry._meta_lock`(flock)·`_atomic_write_json`, `_store.copy_new_lines`(대상 파일 크기를 커서로 쓰는 설계).
