# ultra-search 스킬 레이아웃 이행 재설계 계획

## Context

`ultra-search`는 Claude의 웹 층을 네이티브 `WebSearch`/`WebFetch`에서 성진의 로그인된 Aside 브라우저로 바꾸는 스킬이다(`~/.claude/skills/ultra-search` → 이 레포 `.claude/skills/ultra-search`로 심볼릭 링크, 전역 로드). 역량은 조사 위임(`search`/`resume`), 원문 확보(`fetch`), 사이트 수집(`map`→`crawl`), 긴 조사 감독(`status`/`log`/`result`/`show`/`stop`)이고, 목적은 Claude의 답이 실제로 확보한 원문에 근거하게 하는 것이다.

2026-09-25 재구성(PR #5~#9)으로 `scripts/cli.py` + `scripts/ultra_search/` 패키지가 됐다. PR⑥ 커밋(`31f1b35`, 브랜치 `docs/skill-text-v1`)은 로컬에만 있고 v1.0.0 릴리즈는 없다. 그 뒤 skill-maker가 "Code the skill bundles" 규칙(같은 트리, `uv run` + PEP 723, cli.py가 명령 표면 전체 소유, feature/system/store/helper 단위, 단방향 import, 구조 테스트, `data/`)을 갖췄다. 성진은 이 규칙을 스킬 전체에 반영하고 그 밖의 개선도 원한다. 성공 기준은 품질이다.

계획 세션에서 코드 전부를 읽고, 테스트·권한·`uv`를 실측하고, 다른 프로젝트 세션 전사(실제 호출 521회)와 실제 `result.json` 64개를 분석하고, codex(gpt-6-astra high)의 적대적 계획 리뷰(19건, CONFIRMED 15)를 반영했다. 결론: **완전 재작성은 하지 않는다**(실측으로 다진 경계 처리가 294개 테스트에 고정돼 있다). 순서는 (1) 실사용에서 찾은 치명적 결함 F1·F2(9월 중순부터 search 결과 대부분이 잘림)를 먼저 고치고, (2) 새 트리로 파일·함수를 옮기고, (3) 남이 소유한 형식이 단위 경계를 스킬 용어로만 넘게 하고, (4) CLI 계약을 새 규칙과 실사용 증거에 맞추고, (5) SKILL.md·README를 맞춘 뒤 v1.0.0을 낸다.

## 실측과 사실 (계획 세션, 2026-10-01)

| 구분 | 내용 | 근거 |
|---|---|---|
| 사실 | 기준선 `294 passed, 14 skipped`(3.12.8), 3.10에서도 `294 passed, 14 skipped` | `python3 -m pytest tests/ -q`, `uv run --no-project --python 3.10 --with pytest python -m pytest tests/ -q` |
| 사실 | `${CLAUDE_SKILL_DIR}`는 심볼릭 링크 경로로 확장되고, `allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)`가 `claude -p --permission-mode default`에서 거부 없이 매칭된다. 이때 `sys.path[0]`은 링크를 해석한 실제 `scripts/`, `__file__`은 링크 경로다 | 스크래치 프로브 `us-probe` |
| 사실 | 스킬 폴더 안 파일을 Read하면 거부된다(심볼릭 링크 설치는 작업 디렉터리 밖). `allowed-tools`에 `Read(${CLAUDE_SKILL_DIR}/data/**)`를 넣어도 거부된다 | 프로브 `us-withread`/`us-noread` |
| 사실 | 백그라운드 Bash 출력 파일은 stdout과 stderr를 순서대로 함께 담는다 | 프로브 |
| 사실 | `uv run`(0.8.0)은 캐시된 무의존 스크립트를 ~30ms에 띄우고 stderr에 아무것도 쓰지 않는다. 인터프리터는 uv가 고르고(이번엔 3.13.5), `sys.executable`은 uv 캐시 환경의 python | 프로브 |
| 사실 | `allowed-tools` 사전 승인은 스킬이 호출된 턴에만 유효. 성진의 전역 권한 모드는 `auto` | skills.md, `~/.claude/settings.json` |
| 사실 | `repl-api`가 주는 Aside repl 도구 설명은 120초 제한·Playwright API·`fetch`·`fs`를 설명하지만, 120초 강제 종료가 "fetch failed: other side closed / daemon is not reachable"로 보고된다는 것은 없다 | `repl-api` 실행 |
| 사실 | 현재 데몬 1.26.1001.14(검증 기준 1.26.829.1514), 슬롯 200/200 | `doctor` |
| 사실 | 실제 `aside exec`를 부르는 live 테스트 3개(`test_a_simple_search_answers_with_sources`, `test_a_session_started_outside_this_tool_can_be_continued`, `test_the_real_binary_writes_a_transcript_the_cli_can_find`)는 있었지만 이전 계획이 비용 때문에 실행에서 뺐다. 마지막 것이 F1을 정확히 잡는 테스트다 | `tests/live/test_live.py:37,115`, `tests/test_contract_fake_aside.py:189`, 260925 계획 |

## 실사용 증거 (다른 프로젝트 세션 전사 521회 호출, 실제 `result.json` 64개)

| # | 발견 | 근거 |
|---|---|---|
| F1 | **세션 상관이 2026-09-13경부터 깨져 있다.** Aside가 `messages.jsonl` 첫 줄에 `{"role":"turn-lifecycle","event":"started","turnId":…}`를 쓰기 시작했고, `aside/sessions.py`의 `find_session_by_marker`는 첫 줄만 읽어 마커를 못 찾는다. 결과 64개 중 31개가 `completed_unstructured`(09-17 이후 사실상 전부). 이때 `runs/supervisor.py`의 `_from_stdout`은 마지막 빈 줄 뒤 문단만 답으로 잡아(실례: 실제 최종 답 10,080자 → 386자) ANSI 코드(`\x1b[0m`)가 섞이고, 출처는 stdout의 URL 165개가 전부 `opened=false`다. `show`·자식·`resume`도 막힌다(실례: 잘린 답을 다시 받으려던 `resume`이 "has no session to continue"로 실패). `sessions`의 프롬프트 표시·`--mine`도 같은 원인으로 깨진다. 가짜 Aside·녹화 fixture가 변경 이전 형식이고 실제 `aside exec` live 테스트가 실행되지 않아 테스트는 녹색이었다 | `~/.aside/u/0/sessions/*/messages.jsonl` 첫 줄 역할 집계, `/Users/seongjin/Coding/Agentic SNS/.ultra-search/runs/261001-200459-kimjiyong` |
| F2 | **완료 판정도 깨진다.** 새 형식에서는 부모·자식 전사의 마지막 레코드가 `turn-lifecycle` `finished`다. "마지막 이벤트가 assistant인가"로 판정하는 `runs/evidence.py:331` `child_is_terminal`(→ 감독자 orphan 판정, `follow`의 live children)과 `runs/commands.py:404` `_resumable_session`(→ resume 거부)이 끝난 세션을 진행 중으로 본다. 상관만 고치면 자식 있는 런은 `completed_with_orphans`, resume은 "turn still in flight"로 거부된다. 레코드는 `started`·`final-started`·`finished`와 `turnId`를 갖는다. 자식 완료는 `system-message`("Subagent … is done (status: idle, …)") | 실제 부모·자식 전사에 현재 함수 적용(읽기 전용) 재현, codex |
| F2' | 세션만 찾고 완료 판정만 고치면 나머지 파서는 새 형식에서도 맞다: 같은 전사에서 자식 2개, 출처 32개(열어 봄 13), 답 9,602자 | 같은 재현 |
| F3 | 응답이 너무 크다: 실제 `result.json` p50 20KB·p90 69KB·최대 244KB, 출처 수 p50 95·최대 1,051(대부분 F1 대체 경로의 stdout URL). 모델은 `result`·`status`·`log`·`resume` 응답을 `python3 -c`로 95회 걸러 `run_id`·`state`·`answer`만 뽑았다(`head`/`tail` 파이프 139회 별도) | 전사 집계 |
| F4 | 모델이 run id를 기억으로 재구성해 틀린다(`'260921-...'`, `'260915-202416-123'` 등 `bad_arguments` 11회). 한국어 프롬프트의 라벨은 ASCII만 남아 `2022--4`·`3`·`run`처럼 의미가 없다 | 전사 오류 응답의 `recent_runs` |
| F5 | 병렬 `search`를 한 번에 3~7개 띄우는 일이 흔하다. `--effort low`를 단순 조회에 스스로 쓴 사례가 있다 | 전사 |
| F6 | 답에 Aside의 `<quote source="id">…</quote>` 태그가 해석되지 않은 채 남는다(`<citation>`만 해석) | 실제 답 9건 |
| F7 | 위임 프롬프트 품질은 이미 높다(질문 + 출처 선호 + 돌려받을 증거 + "없으면 없다고" — 현행 Postgres 예시의 모양) | 전사 프롬프트 |
| F8 | `opened`는 도구 이름만 보고 정해진다: `webfetch`가 `isError=True`·본문 `403 Forbidden`을 돌려줘도 `opened=True` | `runs/evidence.py:99`, codex 재현 |

## 새 규칙과의 격차 (현재 코드 기준)

1. `cli.py:23`이 `sys.path`를 고친다. `tests/conftest.py:25`, `tests/test_run_directory.py:182`(자식 프로세스용 문자열 코드)도.
2. 호출이 `python3 "…/cli.py"`이고 PEP 723 헤더가 없다. `next.command`(`runs/commands.py:164`), SKILL.md frontmatter·본문, README가 이 형태를 쓴다.
3. 진입점이 둘이다: 감독자가 `python -m ultra_search.runs.supervisor` + `PYTHONPATH`로 뜬다(`runs/supervisor.py:56`).
4. 종료 코드와 JSON 출력을 각 기능의 `commands.py`가 정한다.
5. `log`가 이벤트 줄과 `# cursor=`를 stdout에 JSON과 섞어 낸다.
6. 명령별 `--help`가 자기 종료 코드를 말하지 않는다(최상위 epilog에만 있다).
7. 단위 인터페이스가 비어 있다(모든 `__init__.py`가 docstring뿐). `cli.py`→`runs.render.LEVELS`, 테스트→`runs.registry`·`runs.supervisor`·`aside.sessions`처럼 모듈 안까지 들어간다. 테스트가 스니펫 파일을 경로로 읽는다(`tests/test_contract_fake_aside.py:24`).
8. import 방향 위반: `doctor.py`→`pages.classify.CONVERTER`(기능→기능), `pages/commands.py`→`runs.registry`(기능→다른 기능 안의 저장소).
9. 남이 소유한 형식이 기능 코드로 샌다: Aside 전사 필드(`details.sources`·`publishDate`·`taskId`·`stopReason=="toolUse"`·`cacheRead`, 도구 이름 `webfetch/repl/read_file`, `<citation refs>`)가 `runs/evidence.py`·`runs/render.py`에, Aside stdout 모양(ANSI 블록)이 `runs/supervisor.py:265`에, 데몬 HTTP·`aside account list`·MCP `tools/list` 파싱이 `doctor.py`에, 우리 마커 형식이 `aside/sessions.py`에, Aside REPL API(`openTab`·`closeTab`·`pwd`·`fs`)를 쓰는 스니펫과 href 디코딩이 `pages/`에, Node 변환기(Defuddle·anydoc 종료 코드 3)가 `pages/classify.py`에 있다.
10. 상태가 작업 디렉터리의 `.ultra-search/`에 쌓인다(새 규칙은 `data/`) → 성진 결정으로 유지, 이유 기록.
11. 구조 테스트가 없다.

## 합의 원장

| 구분 | 내용 | 근거 |
|---|---|---|
| 결정 | 계획 파일명 `261001_ultra-search 스킬 레이아웃 이행 재설계 계획.md`(하네스 경로 2개는 이 파일을 가리키는 심볼릭 링크, 커밋하지 않고 0단계에서 삭제) | 성진 |
| 결정 | 방향: 완전 재작성이 아니라 행동 보존 구조 이행 + 근거 있는 표적 개선. 격차 11개를 모두 다룬다 | 성진 |
| 결정 | 미완 PR⑥(`31f1b35`)은 0단계에서 푸시·PR·머지. 새 작업은 main에서. v1.0.0은 이번 작업이 끝난 뒤 새 구조로 | 성진 |
| 결정 | 상태 위치: 런·페이지·맵·크롤 모두 작업 디렉터리 `./.ultra-search/` 유지, `--runs-dir` 유지. 이유: 전역 로드 스킬이라 여러 프로젝트 세션이 동시에 돌고, 프로젝트별 레지스트리가 대상 없는 `status`·`result`·`show`의 "가장 최근"을 그 프로젝트로 한정한다. 산출물은 Read로 읽혀야 하는데 스킬 폴더 파일은 Read가 거부된다(실측). skill-maker `data/` 규칙에서 벗어난 사실과 이유를 README·구조 테스트에 기록 | 성진 |
| 결정 | 스킬이 기본 위치 `./.ultra-search/`를 만들거나 쓸 때 그 안에 `.gitignore`(`*`)가 없으면 만든다. `--runs-dir`·`--out`으로 고른 곳에는 쓰지 않는다 | 성진 |
| 결정 | `log`: 이벤트 줄은 줄마다 플러시해 stderr로, `# cursor=` 줄 삭제(커서는 JSON `cursor`), stdout은 JSON 하나 | 성진 |
| 결정 | 기능은 `Reply(payload, outcome)`만 돌려주고 cli.py가 JSON 출력과 outcome→종료 코드 변환을 소유. 명령별 `--help`의 Exit 줄도 같은 표에서 생성. 숫자와 의미(0/2/3/4/5)는 유지 | 성진 |
| 결정 | 감독자는 cli.py의 숨은 내부 경로로 `[sys.executable, <cli.py>, "_supervise", <run>]` 기동. `-m`·`PYTHONPATH` 제거 | 성진 |
| 결정 | 단위: research·fetch·site·doctor(feature), aside·converter(system), runs·saved(store), outcome·ids·workspace(helper). site→fetch만 이름 붙은 기능 간 엣지. saved는 모듈 `saved.py` | 성진 |
| 결정 | 남의 형식 가두기: 전부. Aside 전사·stdout·데몬·계정·MCP·REPL API(스니펫 4개 포함)는 aside/, Node 변환은 converter/. 기능은 배치·재시도·승격·판정·저장·탐색 범위 같은 판단만 갖는다 | 성진(+codex 지적으로 스니펫 이동 합의) |
| 결정 | 단계: 0 준비 → ① fix(세션 상관·완료 판정) → ② 트리 이행(파일·함수 재배치) → ③ 형식 경계(스킬 용어 인터페이스) → ④ CLI 계약 → ⑤ 스킬 본문 → ⑥ 릴리즈. 구조 변경은 기존 테스트 녹색 유지로, 행동 변경은 빨강→초록으로 판정 | 성진(+F1·F2로 ① 추가, codex 지적으로 ②·③ 경계 조정) |
| 결정 | 테스트 경계: S1(CLI + 가짜 Aside) 유지, S2(영속화)는 runs 인터페이스와 `research.supervise()` 경유, 구조 테스트 신설, aside 인터페이스에 녹화된 실제 전사·stdout을 넣는 변환 테스트 추가 | 성진 |
| 결정 | 실제 `aside exec` live 테스트 3개(실제 search는 `--effort low`로 바꾸고 상관 성공을 확인하도록 강화, 외부 세션 resume, 실제 바이너리 계약)를 ①·⑤ 끝과 Aside 업데이트 뒤에 돌린다(구독 소모). fetch 계열 live는 PR마다 | 성진 |
| 결정 | search·resume·result 응답은 요약 → 답 → 열어 본 출처 → 핸들(아래 CLI 계약). 전체 출처는 `result --sources`. usage·자식 id 목록은 status에만 | 성진 |
| 결정 | run id: `--run`·`resume`·`show --run`이 고유 접두사를 받고, 여럿이면 후보를 담아 `bad_arguments`. 라벨은 한글 등 유니코드 글자를 살리되 경로 문자는 막고 NFC 정규화 | 성진 |
| 결정 | SKILL.md 본문 전면 재검토 결과: 호출 형태 변경, "Without Aside" 경계 추가, "Only acquired content" 불릿을 판단만 남게 다듬음. 위임 예시는 현행 유지(F7). 병렬 분할·`--effort`는 쓰지 않는다(모델 판단) | 성진 |
| 결정 | Aside를 쓸 수 없으면 공개 사실 질문이라도 네이티브 도구로 대체하지 않는다: `doctor`가 말한 원인과 해결을 알리고 대체 여부를 묻는다. 물을 사람이 없는 실행(서브에이전트, `claude -p` 배치)에서는 그 보고가 결과다 | 성진 |
| 결정 | "Aside 업데이트 뒤 live 재실행과 `VERIFIED_*` 갱신"은 README 개발 절에 둔다. doctor는 "검증 기준과 다른 버전이 결과가 얇을 때 먼저 의심할 점"만 말한다(모델이 할 수 없는 유지보수자 일) | 성진 |
| 결정 | SKILL.md·`--help`는 영어, 커밋·PR·README는 한국어 | 이전 계획 |
| 결정 | codex 리뷰는 gpt-6-astra high(읽기 전용): 이 계획(완료, 아래 반영), PR마다 1회, 최종 스킬 텍스트 1회. 리뷰 종료 조건은 "일상 사용에서 도달 가능한 CONFIRMED 결함 0건" | 이전 계획 + 메모리 |
| 가정 | 다른 Mac에서도 Aside 계정 디렉터리는 `u/0`, 데몬 포트는 21420(상수는 aside/ 한 곳) | 이전 계획 |

## 구현 후 스킬 디렉터리 구조

```
.claude/skills/ultra-search/
├── SKILL.md
└── scripts/
    ├── cli.py                      # PEP 723 헤더. 유일한 진입점: 파서·도움말·디스패치·JSON 출력·종료 코드 표, --runs-dir 해석, 숨은 `_supervise`
    └── ultra_search/
        ├── __init__.py             # __version__ = "1.0.0"
        ├── outcome.py              # helper: Reply(payload, outcome), UltraSearchError·ArgumentError·RunNotFound·AmbiguousRun·AsideUnavailable·RunFailed(④부터 종류만, 종료 코드 숫자는 cli.py)
        ├── ids.py                  # helper: 경로 한 마디가 될 id 검증(유니코드 글자·숫자·`._-`, 경로 문자·`..` 차단, NFC), 라벨 만들기
        ├── workspace.py            # helper: 기본 위치 ./.ultra-search 결정, 디렉터리 생성과 .gitignore('*')
        ├── doctor.py               # feature: doctor · setup · repl-api — aside·converter·runs 인터페이스만 호출, repl-api 응답에 120초 강제 종료 안내
        ├── research/               # feature: search · resume · status · log · result · show · stop · sessions (+ 분리 감독)
        │   ├── __init__.py         # 인터페이스: 명령 함수 8개(→Reply), supervise(), run_detached(), LEVELS
        │   ├── commands.py         # 명령 핸들러, next_step, run_summary, 응답 모양, TERMINAL_STATES·FAILED_STATES
        │   ├── marker.py           # 상관 마커 형식, 프롬프트 장식(SCOPE), 여는 프롬프트에서 마커 읽기
        │   ├── supervisor.py       # 상태기계(__main__ 없음), spawn(cli_path)
        │   ├── evidence.py         # 런 범위 증거 뷰: 턴 경계·답·출처 병합(id 별칭)·사용량 합산 — 스킬 용어만
        │   ├── follow.py           # 감시·커서, 이벤트는 stderr
        │   └── render.py           # 이벤트 → 줄
        ├── fetch/                  # feature: fetch
        │   ├── __init__.py         # 인터페이스: fetch()(→Reply), fetch_urls()(site가 씀)
        │   ├── commands.py         # --out 해석, 응답 모양
        │   ├── acquire.py          # 묶음·재시도·탭 승격·저장
        │   └── classify.py         # 응답 판정(HTTP·문서·챌린지·셸), Document, 프런트매터, slug, 단어 수
        ├── site/                   # feature: map · crawl  (site → fetch: 이름 붙은 기능 간 엣지)
        │   ├── __init__.py         # 인터페이스: map_site(), crawl()(→Reply)
        │   ├── commands.py         # map·crawl 핸들러, 요약 응답
        │   └── discover.py         # URL 선택(순수): 정규화·동일 출처·글롭·깊이, href→절대 URL, manifest 형식
        ├── aside/                  # system: Aside CLI·데몬·~/.aside·전사·stdout·REPL·MCP. Aside가 바뀌면 여기만 고친다
        │   ├── __init__.py         # 인터페이스(아래)
        │   ├── process.py          # 바이너리, exec 기동(cwd 지정), --version, EFFORTS·SPEEDS·VERIFIED_*
        │   ├── daemon.py           # 헬스 HTTP, `aside account list`, MCP tools/list
        │   ├── sessions.py         # ~/.aside 배치, state.db, 여는 user 레코드 읽기, 마커로 세션 찾기, 세션 요약, 바쁜 세션 판정
        │   ├── transcript.py       # messages.jsonl → 스킬 용어 Event, 턴 끝 판정, <citation>·<quote> 해석
        │   ├── exec_output.py      # `aside exec` stdout → 최종 답·URL(ANSI 경계 판별 후 제거)
        │   ├── repl.py             # 코드·스니펫 실행(ARGS 주입), ReplTimeout, 왕복 확인
        │   ├── browser.py          # fetch_pages·open_tab·read_sitemaps·read_links: 스니펫 호출과 응답 해석(바이너리 판별 결과, href 엔티티 디코딩)
        │   └── snippets/           # fetch_batch.js · tab_one.js · sitemap.js · links.js
        ├── converter/              # system: Node 변환(Defuddle·anydoc). 이 폴더가 npm 패키지
        │   ├── __init__.py         # 인터페이스: to_markdown(html, url), document_text(path), check(), install()
        │   ├── node.py             # node 실행, lockfile에서 Node 최소 버전, npm ci, anydoc 종료 코드 해석
        │   ├── to_markdown.mjs · package.json · package-lock.json
        │   └── node_modules/       # setup이 설치(gitignored)
        ├── runs/                   # store: <root>/runs 런 디렉터리
        │   ├── __init__.py         # 인터페이스(아래)
        │   ├── registry.py         # id 예약(O_EXCL), 접두사 해석, meta flock, 원자적 쓰기, 그룹
        │   └── copies.py           # 전사 사본: 통째 줄만 덧붙이고 사본 크기를 커서로
        └── saved.py                # store: <root>/pages·maps·crawls 위치와 이름 고르기(현행 보장 그대로)
```

```
<레포 루트>/
├── pytest.ini                      # pythonpath = .claude/skills/ultra-search/scripts, testpaths = tests, markers = live
├── README.md
├── tests/                          # 스킬 밖. 단위 인터페이스와 CLI만 사용
│   ├── conftest.py                 # sys.path 수정·마커 등록 삭제, run_cli가 stdout·stderr를 모두 잡음
│   ├── fake_aside/aside            # 새 형식(started → user → … → finished) 시나리오 + 옛 형식 시나리오
│   ├── fixtures/                   # + 현재 데몬에서 새로 녹화한 부모·자식 전사와 stdout(공개 출처 질문, 검토·축약)
│   ├── test_research.py · test_pages.py · test_environment.py           # S1
│   ├── test_run_directory.py       # S2: runs 인터페이스, research.supervise()
│   ├── test_aside_formats.py       # 녹화 전사·stdout → aside 인터페이스 → 스킬 용어
│   ├── test_structure.py           # 구조 테스트(아래)
│   ├── test_contract_fake_aside.py # 가짜와 실제 Aside의 형식 계약(실제 쪽은 live)
│   └── live/test_live.py
└── graphify-out/                   # 유지보수자 산출물(머지 뒤 갱신)
```

### 함수 이동표 (단위 경계를 넘는 것만)

| 지금 | 새 소유자 · 공개 이름 | 호출자 |
|---|---|---|
| `contract.py` 오류 계열, `EXIT_*` | ②: 그대로 `outcome.py`로(숫자와 오류의 `exit_code` 포함, 기능은 지금처럼 정수를 돌려줌). ④: `Reply`·outcome 도입과 함께 숫자를 `cli.py` 표로 옮기고 오류에서 `exit_code`를 뺌, `RunNotFound`·`AmbiguousRun` 추가 | 전부 / cli |
| `contract.TERMINAL_STATES`·`FAILED_STATES` | `research.commands` | research 안 |
| `contract.is_safe_id`, `registry._sanitize_label` | `ids.is_safe_id`, `ids.label_for(text)` | runs, aside, research |
| `registry.default_runs_dir`·`resolve_runs_dir` | `workspace.default_root()`·`workspace.ensure(root)`; cli.py가 `--runs-dir`를 Path로 해석해 기능에 `root`로 넘김 | cli, runs, saved |
| `registry.create_run`·`resolve_run`·`resolve_group`·`latest_run`·`latest_group`·`all_runs`·`new_group_name`·`Run`·`load_meta`·`atomic_write_json` | `runs`(같은 이름, `resolve_run`의 접두사 해석은 ④) | research |
| `doctor._writable` | doctor에 그대로(cli가 넘긴 `root`에 임시 파일을 써 보는 실제 쓰기 확인) | doctor |
| `registry.pages_dir`, `pages/commands._new_file`·`_default_out`·`_refuse_used_folder`, `acquire._unique_path` | `saved.pages_dir(root)`·`saved.new_map_file(root, host)`·`saved.new_crawl_dir(root, host)`·`saved.refuse_used_folder(path)`·`saved.unique_path(dest, stem, used, ext)` | fetch, site |
| `registry.marker_for`·`decorate_prompt`·`SCOPE`, `sessions.session_summaries`의 마커 파싱 | `research.marker` | research 안 |
| `sessions.copy_new_lines` | `runs.copy_new_lines(src, dst, since)` — research가 `aside.session_transcript(id)`와 조합(aside→runs 의존 없음) | research.supervisor |
| `research._resumable_session`의 DB·전사 판정 | `aside.session_busy(session_id) -> bool` | research.resume |
| `evidence.collect_sources`의 형식부, `child_session_ids`, `total_usage`의 키 정규화, `_OPENING_TOOLS`, `resolve_citations` | `aside.transcript`: `Event.sources`·`Event.child_ids`·`Event.usage`, `aside.resolve_answer_tags(text, id_to_url)` | research.evidence |
| `render._TARGET_KEYS` | `aside`: `ToolCall.target` | research.render |
| `supervisor._from_stdout` | `aside.parse_exec_output(text) -> (answer, urls)`; 대체 경로를 쓸지·상태 이름은 research | research.supervisor |
| `doctor._daemon_status`·`_account_status`·`_repl_probe`·`_repl_api`의 MCP 부분, `process.VERIFIED_*` | `aside.daemon_status()`·`account_status()`·`repl_probe()`·`mcp_tools()`(전체 목록, `repl-api --all`이 씀), 상수 `aside.VERIFIED_*` | doctor |
| `cli.EFFORT_CHOICES`·`SPEED_CHOICES` | `aside.EFFORTS`·`aside.SPEEDS` | cli |
| `pages/browser.py` 전체, `pages/snippets/*` | `aside.fetch_pages(urls, per_url_ms, budget_ms)`·`open_tab(url, wait_ms)`·`read_sitemaps(roots, …)`·`read_links(pages, …)`(href는 엔티티 디코딩까지, 절대 URL·동일 출처는 site) | fetch, site |
| `classify._run_to_markdown`·`_run_anydoc`·`CONVERTER`·`TO_MARKDOWN`·`ANYDOC`, `doctor._node_*`·`_setup` | `converter.to_markdown(html, url)`(정규화된 dict: ok·markdown·title·author·published·site·words·error), `converter.document_text(path)`(status ok·needs_ocr·unsupported, text, error — anydoc 종료 코드 해석까지), `check()`, `install()` | fetch, doctor |
| `classify.extract_document` | 나눈다: 종료 코드 해석은 `converter.document_text`, `Document` 조립·단어 수·`_first_heading`은 `fetch.classify`에 남김(converter→fetch 의존 없음) | fetch |
| `runs.render.LEVELS` | `research.LEVELS` | cli |

### 단위 인터페이스와 import 방향

| 단위 | 종류 | import 해도 되는 것 |
|---|---|---|
| `cli.py` | 진입점 | 모든 단위의 인터페이스 |
| research | feature | aside, runs, outcome, ids |
| fetch | feature | aside, converter, saved, outcome, ids |
| site | feature | **fetch**(이름 붙은 엣지), aside, saved, outcome |
| doctor | feature | aside, converter, runs, outcome |
| aside · converter | system | outcome, ids |
| runs · saved | store | outcome, ids, workspace |
| outcome · ids · workspace | helper | (패키지 내부 없음) |

aside 인터페이스: `aside_bin()`, `start_exec(prompt, *, session, effort, model, speed, stdout_path, cwd)`, `version()`, `daemon_status()`, `account_status()`, `mcp_tools()`, `repl_probe()`, `run_code()`, `ReplTimeout`, `REPL_HARD_LIMIT`, `fetch_pages()`, `open_tab()`, `read_sitemaps()`, `read_links()`, `aside_home()`, `sessions_root()`, `session_transcript(session_id)`, `find_session_by_marker(marker)`, `session_summaries(limit)`(잘리지 않은 `opening_prompt` 포함), `session_busy(session_id)`, `suspension(session_id)`, `last_activity(session_id, child_ids)`, `read_events(path, since)`, `turn_finished(events)`, `parse_exec_output(text)`, `resolve_answer_tags(text, id_to_url)`, `Event`, `ToolCall`, `SourceRef`, `EFFORTS`, `SPEEDS`, `VERIFIED_VERSION`, `VERIFIED_DAEMON_VERSION`.

`Event`(스킬 용어): `kind`(user·assistant·tool_result·system·lifecycle·raw), `index`, `timestamp`, `text`, `tool_calls[ToolCall(name, arguments, target)]`, `tool_name`, `content`, `is_error`, `stop`("tool"·"end"·""=기록 없음), `lifecycle`(started·final-started·finished·"" ), `sources[SourceRef(url, title, id, excerpt, published, opened)]`(`opened`는 페이지를 여는 도구이면서 오류가 아닐 때만 — ③ 행동 커밋), `child_ids`, `usage`(input·output·cache_read·cache_write·reasoning·total_tokens·cost), `unknown_blocks`(개수와 원본, 렌더러가 "[N unrecognised block(s)]"로 표시), `details`(불투명 원본, `show --item`이 그대로 돌려줄 때만), `raw`(log `--level raw`만). 출처 별칭(`ids`)은 evidence가 URL 단위로 병합하며 만든다. 판정 로직(`final_answer`는 `stop=="end"`만, 자식 완료는 아래 F2 규칙)은 그대로 옮긴다.

runs 인터페이스: `Run`, `create_run`, `resolve_run(root, id_or_prefix)`(정확 일치 우선 → 유일한 접두사 → 없으면 `RunNotFound`, 여럿이면 후보를 담은 `AmbiguousRun`), `resolve_group`, `latest_run`, `latest_group`, `all_runs`, `new_group_name`, `load_meta`, `atomic_write_json`, `copy_new_lines`.

### 구조 테스트 (`tests/test_structure.py`)

검사기 자체를 검증하는 실패 예제(일부러 어긴 짧은 소스 문자열)를 함께 둔다.

1. `scripts/` 최상위는 `cli.py`와 `ultra_search/`뿐(`__pycache__` 제외). `ultra_search`는 `sys.stdlib_module_names`에 없다.
2. 패키지 최상위의 모든 모듈·하위 패키지가 위 표의 종류 하나로 분류돼 있다(새 단위는 표에 넣어야 통과).
3. import 방향이 위 표를 따른다. AST로 `import`·`from … import`·상대 import를 모두 해석하고, `from ultra_search.X import name`에서 `name`이 하위 모듈이면 그 모듈을 import한 것으로 본다. 기능 간 엣지는 `site→fetch`만.
4. 단위 밖(다른 단위, `cli.py`, `tests/` 포함)은 단위의 공개 이름(`__init__`이 내보낸 것, 단일 모듈 단위는 그 모듈)만 쓴다. 테스트는 패키지 안 파일을 경로로 읽지 않는다.
5. 스킬과 테스트 어디에도 `sys.path` 변경(`insert`·`append`·`extend`·대입, 자식 프로세스에 넘기는 코드 문자열 포함)과 `PYTHONPATH` 설정이 없다. 자식 프로세스 테스트는 `cwd=scripts/`로 import한다.
6. 진입점은 `cli.py` 하나: 패키지 안에 `if __name__ == "__main__"`이 없다. (④부터) `cli.py`는 PEP 723 블록(`requires-python`, `dependencies`)으로 시작한다.
7. (③부터) 형식 격리 — 주 검사: 기능·저장소 코드가 `Event.raw`·`Event.details`를 읽지 않는다(허용: `research.render`의 raw 레벨, `research`의 `show --item` 응답). 보조 검사: Aside 날 이름(`stopReason`, `toolUse`, `taskId`, `task_id`, `cacheRead`, `cacheWrite`, `publishDate`, `toolResult`, `turn-lifecycle`, `system-message`, `<citation`, `<quote`, `runningSessionCount`, `semaphore`, `webfetch`, `websearch`, `read_file`, `openTab`, `closeTab`, `\x1b[`)가 `scripts/` 안 `aside/` 밖 `.py`(cli.py 도움말 포함)에, Node 변환기 이름(`node_modules`, `anydoc`, `to_markdown.mjs`, `npm`)이 `converter/` 밖 `.py`에 나오지 않는다. `tests/`·fixture는 범위 밖.
8. (④부터) SKILL.md의 `allowed-tools`와 본문 코드 블록이 같은 호출 형태 `uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py"`를 쓴다.
9. 모듈 docstring에 기록: 상태는 skill-maker의 `data/`가 아니라 작업 디렉터리 `./.ultra-search/`에 둔다(이유는 합의 원장). 스킬 폴더에 `data/`가 생기면 실패.

## F1·F2 수정 규칙 (① 단계)

- 여는 user 레코드: 전사를 위에서부터 JSON으로 해석해 첫 `role=="user"` 레코드를 찾는다(상한: 앞 20줄). 마커는 원시 줄이 아니라 해석한 user 텍스트에서 찾는다(유니코드가 `\uXXXX`로 저장돼도 맞도록). `find_session_by_marker`와 `session_summaries`(잘리지 않은 프롬프트에서 마커를 읽은 뒤 표시용으로 자름)가 같은 함수를 쓴다.
- 턴 끝: 전사에 `turn-lifecycle` 레코드가 있으면 마지막 lifecycle 레코드가 `finished`일 때 끝났고, `finished` 뒤 새 `started`가 오면 다시 진행 중이다. lifecycle 레코드가 없는 옛 형식은 지금 규칙(마지막 이벤트가 `stop!="tool"`인 assistant, 기록 없으면 텍스트 유무)을 쓴다. 자식 완료(`child_is_terminal`)와 바쁜 세션(`_resumable_session`) 둘 다 이 규칙.
- stdout 대체 경로: ANSI 경계(도구 출력 블록의 `\x1b[2m`…`\x1b[0m`)로 마지막 도구 블록 뒤를 최종 메시지 전체로 잡은 뒤 ANSI를 지운다. 녹화한 실제 stdout으로 검증한다.
- `turn-lifecycle`은 progress 로그에 `raw:` 줄로 찍지 않는다(steps 이상에선 한 줄 `turn <event>`).

## CLI 계약 (구현 후)

- 호출: `uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" <command> …`. `cli.py` 맨 위:
  ```
  # /// script
  # requires-python = ">=3.10"
  # dependencies = []
  # ///
  ```
- 명령 14개는 그대로(search, resume, status, log, result, show, stop, fetch, map, crawl, sessions, repl-api, doctor, setup) + 숨은 `_supervise`(argparse 전에 가로챔, `--help`에 없음). `result --sources-only`는 `result --sources`(전체 출처, 답 생략)로 바뀌고, 이를 안내하던 오류 `fix`도 바꾼다.
- 종료 코드(숫자·의미 유지, 표는 cli.py 한 곳): 0 처리됨(각 상태를 볼 것) · 2 인자 오류 · 3 Aside 사용 불가 · 4 런 실패/포기, 또는 저장한 것 없음 · 5 결과 데이터 없음. 각 `<command> --help` 끝에 그 명령이 낼 수 있는 코드와 뜻을 같은 표에서 만든 Exit 줄로 단다.
- stdout은 JSON 하나, 값싼 신호 먼저. stderr는 진행·진단(`log` 이벤트, `run.<state>`·`run.still-running`·`heartbeat` 줄).
- 봉투는 유지: `{"ok", "command", ["group"], ["note"], ["next"], "runs": [...]}` — `next`는 지금처럼 그룹 전체에 대한 최상위 행동 하나. `result`도 진행 중인 런이 있으면 최상위 `next`(watch)를 준다.
- search·resume·result 런 항목 순서: `run_id`, `state`, `empty`, `sources_total`, `sources_opened`, `note`(있을 때) → `answer` → `opened_sources: [{n, url, title}]` → `result_path`. `n`은 저장된 `result.json`의 전체 출처 목록에서 먼저 매긴 번호이고(거른 뒤 다시 매기지 않음), `show --source n`도 `result.json`이 있으면 같은 저장 목록에서, 없으면(진행 중, `stop`·감시 timeout으로 `abandoned`) 지금처럼 그 런의 전사에서 계산한 목록에서 출처를 찾은 뒤 전사에서 본문을 읽는다. 전사가 없는 런(`completed_unstructured`)은 `show`가 "본문 없음, stdout만 있음"을 말한다. `result --sources`는 `answer` 대신 `sources: [{n, url, title, opened}]`.
- 예시(단일, 완료):
  ```
  {"ok":true,"command":"result","runs":[{"run_id":"261002-101500-파이썬-최신","state":"completed","empty":false,"sources_total":12,"sources_opened":3,"answer":"…","opened_sources":[{"n":1,"url":"https://www.python.org/downloads/","title":"Download Python"}],"result_path":".ultra-search/runs/261002-101500-파이썬-최신/result.json"}]}
  ```
  그룹·진행 중: `{"ok":true,"command":"search","group":"g261002-…","note":"Still running…","next":{…},"runs":[{"run_id":…,"state":"running","empty":true}, {…완료 항목…}]}`. 결과 파일 없음: 항목에 `"note":"no result yet"`.
- status 항목: `run_id`, `state`, `idle_seconds`, `possibly_stalled`, `live_children`, `note` → `label`, `group`, `session_id`, `child_ids`, `usage`, `suspension`.
- fetch: `ok`, `command`, `statuses`(상태별 개수) → `items`(항목 키 순서 `status`, `url`, `path`, `words`, `title`, …).
- run id: `<yymmdd-HHMMSS>[-xxxx]-<라벨>`, 라벨은 유니코드 글자 유지(NFC). 정확 일치 → 유일 접두사 → `RunNotFound`/`AmbiguousRun`. `resume`은 `RunNotFound`일 때만 Aside 세션 id로 해석한다(모호하면 후보를 그대로 보고).
- `opened`의 `--help` 정의: 페이지를 여는 도구가 오류 없이 그 URL을 돌려줬다는 추정(내용 확인 아님).
- `repl-api`의 실행 안내에 추가: 120초에 강제 종료된 스니펫은 "fetch failed: other side closed / daemon is not reachable"로 보고되지만 데몬은 멀쩡하다, 결과는 생기는 대로 출력해 두라.
- saved의 보장은 현행 그대로: 자동 이름은 쓰는 순간 있는 파일을 피하고(검사 후 쓰기, 원자적 예약 아님 — `성진:` 주석), map·crawl 기본 위치는 O_EXCL로 예약, `fetch --out FILE`·`map --out FILE`은 요청대로 덮어쓰고, `crawl --out`은 비어 있지 않은 폴더를 거부한다.

## SKILL.md (구현 후)

frontmatter: `name: ultra-search`, `description`(현행 유지), `allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)`. 영어. references 없음.

섹션 구조:

```
# Web work through the user's own browser
  진입점 문단(확장된 절대경로·큰따옴표·한 줄 — 권한 규칙이 명령 텍스트와 매칭)
  코드 블록: uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
  --help가 입력·출력·상태·복구를 소유, next는 반환된 그대로 실행
## Choose by the work still needed
  search vs fetch / 재사용(result·show) / map 먼저 vs crawl 바로 / resume·sessions / 상호작용 뒤 내용은 repl-api로 직접 스크립트(검색엔진 자동 질의 금지)
## Delegate an objective, not keywords
  목표·출처 제약·원하는 증거 / Postgres 예시(현행) / 부정 발견 허용 ≠ 빈 출력
## Follow state, not silence
  감시 종료 ≠ 조사 완료, 최신 next / 감독 비용 < 위임한 일
## Boundaries that affect the answer
  - Watching is not cancellation.
  - Only acquired content is evidence.          ← 다듬음
  - Partial evidence is not a complete investigation.
  - Requests act as the user.
  - Without Aside, stop rather than substitute.  ← 새
  마지막 줄: 실패 시 복구 메시지, 환경이 의심되면 doctor
```

바뀌는 곳 초안(나머지는 `31f1b35` 그대로):

> ```bash
> uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
> ```

> - **Only acquired content is evidence.** A fetch item's status says whether its page was acquired; a search source counts as read only if the run opened it, and one that only appeared in results is a lead. Login walls and bot checks can answer with HTTP 200, so judge each item rather than the command's success. When a claim rests on one page, read what was acquired (`show`, or `fetch` it) before citing it as read.
> - **Without Aside, stop rather than substitute.** The user routes web work through their own browser so answers rest on pages acquired with their access; WebSearch and WebFetch cannot use it. When a command reports Aside unavailable, run `doctor`, tell the user what it found and how to fix it, and ask before using them, even for a fact that looks public; where no one can be asked, that report is the result.

- references를 두지 않는 이유: 모든 경로가 본문 전체를 필요로 하고, 한 분기에만 필요한 직접 스크립팅은 `repl-api` 인터페이스(도구 설명 + 실행 안내)가 소유한다.
- 본문에 넣지 않기로 한 것(기록): 병렬 분할 기준, `--effort` 선택(성진 결정: 모델 판단), 응답을 파이프로 거르지 말라는 지시(응답 모양을 고쳐 원인을 없앤다), 위임 예시 교체(F7로 현행 유지).
- 전문 승인은 ⑤단계에서 AskUserQuestion으로 전문을 보여 받는다.

## README 섹션 구조 (한국어)

```
# Ultra-Search
## 왜
## 네 가지 역량
## 설치          (uv·Node ≥20.19·Aside 전제, git clone + 심볼릭 링크, `uv run … setup`, `uv run … doctor`, git pull 뒤 setup 재실행)
## 써보기        (uv run 예시, --help·--version)
## 알아둘 것     (stop은 런을 못 멈춤, 침묵≠정체, search는 비쌈, 차단된 페이지는 저장 안 됨, ./.ultra-search/와 자동 .gitignore)
## 구조          (트리 요약, 단위 종류와 import 방향, data/ 대신 ./.ultra-search/인 이유, 구조 테스트가 지키는 것)
## 개발          (`uv run --python 3.10 --with pytest pytest`, `-m live`(실제 exec 3개는 구독 소모), Aside 업데이트 뒤 live 재실행과 VERIFIED_* 갱신, 테스트 수)
```

## 테스트 경계

- S1(주): argv → stdout JSON + stderr + 종료 코드. 외부 경계 대역은 가짜 Aside 하나. 반환된 `next`는 셸로 실제 실행. node 변환기는 실물.
- S2: 영속화가 약속인 성질만 — runs 인터페이스(meta flock, 원자적 쓰기, id 예약·접두사 해석, 전사 사본 커서)와 `research.supervise()`(result.json·meta.json 상태기계). 디스크를 읽는 것이 우회가 아니다.
- aside 인터페이스: 녹화한 실제 전사·stdout → `read_events`·`turn_finished`·`find_session_by_marker`·`session_summaries`·`parse_exec_output` → 스킬 용어. Aside 형식이 바뀌면 여기가 먼저 깨진다.
- 구조 테스트: 위 9개 항목(6 일부·8은 ④, 7은 ③부터).
- live(`-m live`, Aside 실행 중): fetch 계열(PR마다) + 실제 exec 3개(①·⑤ 끝, Aside 업데이트 뒤).
- 대역이 가리는 것: 스니펫 JS와 가짜/실제 Aside 차이는 live로만 본다. 기대값은 녹화·명세에서 가져오고 현재 출력에서 베끼지 않는다.

## 단계와 완료 판정

각 단계 시작 시 `TaskCreate`에 완료 판정을 그대로 적고 끝날 때 `TaskUpdate`. 브랜치는 `main`에서 판다. 커밋·PR 제목 `<타입>: <한국어 제목>`, PR 본문 `## 무엇을 바꿨나`/`## 왜`/`## 영향`/`## 검증`(실행한 명령과 수치). 코드 단계는 `coding` 스킬을 연다. 구조와 행동은 커밋을 나눈다(구조 먼저). 각 PR은 실제 진입점 실행 후 codex(gpt-6-astra high, 읽기 전용) 리뷰 → 선별 반영(기각 이유는 PR 본문) → `gh pr merge --squash` → `Graphify` 리빌드를 main에 `chore: 그래프 갱신`으로 직접 커밋.

0. **준비** — `docs/skill-text-v1` 푸시 → PR → 스쿼시 머지 → 그래프 갱신. 하네스 심볼릭 링크 2개(`.claude/plans/users-seongjin-coding-ultra-search-clau-shiny-iverson.md`, `…-glowing-cook.md`) 삭제. 기준선 실측.
   완료 판정: main에 `31f1b35` 내용 반영, `uv run --python 3.10 --with pytest pytest tests/ -q`가 `294 passed, 14 skipped`.
1. **① `fix/session-correlation`** — `fix: 새 전사 형식에서 세션 상관과 완료 판정 복구`. 먼저 현재 데몬에서 공개 출처만 쓰는 질문(`--effort low`, 예: "python.org 기준 Python 최신 안정 버전")으로 자식이 있는 런을 하나 녹화하고(부모·자식 전사, stdout), 전체를 검토해 개인 정보·로그인 페이지 내용이 없음을 확인한 뒤 lifecycle 순서·ANSI 경계·참조 관계를 보존한 채 축약해 fixture로 넣는다. 가짜 Aside에 새 형식 시나리오(실제 파일을 `started → user → … → finished` 순서로 씀)를 추가한다. 빨강 확인: 새 형식에서 상관 실패, `sessions --mine` 실패, 자식 완료 오판, 완료된 세션의 resume 거부, stdout 대체 답 잘림. 수정은 위 "F1·F2 수정 규칙". live: 실제 search 테스트를 `--effort low` + 상관 성공 확인(`completed`, `session_id`, 열어 본 출처 ≥1)으로 강화하고 실제 exec 3개를 실행. `VERIFIED_DAEMON_VERSION`을 통과한 버전으로 갱신.
   완료 판정: 위 다섯 빨강이 수정 전 실패·수정 후 통과, 새 형식의 부모 → 자식 완료 → `result`(`completed`) → `resume` 왕복 통과, 전체 녹색, live 실제 exec 3개 통과.
2. **② `refactor/skill-layout`** — `refactor: 스킬 코드를 새 트리로 재배치`. 위 트리와 함수 이동표대로 `git mv` 중심 이동(스니펫·browser 래퍼는 `aside/`로, href 엔티티 디코딩은 aside·절대 URL과 동일 출처 판정은 `site/discover.py`, 데몬·계정·MCP 파싱은 `aside/daemon.py`, Node 변환은 `converter/`, 예약 함수는 `saved.py`, 사본 복사는 `runs/copies.py`), 단위 인터페이스, cli.py가 `--runs-dir`를 해석해 `root`로 넘김, 감독자 `_supervise`, `sys.path` 수정 제거와 `pytest.ini`, 테스트를 인터페이스 경유로(옛 단언 → 새 위치 대조표를 PR 본문에), 구조 테스트 1~5·6(진입점 부분)·9. 동작 변경 없음.
   완료 판정: 전체 녹색, 구조 테스트 통과, import 방향을 하나 일부러 어겨 구조 테스트가 실패하는 것을 확인 후 되돌림, 무관한 디렉터리에서 심볼릭 링크 경로로 `search --background`(가짜 Aside) → 반환 `next` 실행 → `result`까지 통과, live fetch 계열 통과.
3. **③ `refactor/foreign-formats`** — `refactor: Aside 형식을 스킬 용어 인터페이스 뒤로`. 구조 커밋: 스킬 용어 `Event`(위 필드), evidence·render·follow·supervisor가 그것만 쓰게, `parse_exec_output`·`turn_finished`·`resolve_answer_tags`를 aside로, `test_aside_formats.py`, 구조 테스트 7. 행동 커밋(테스트 먼저): `<quote source>` 해석(F6), 오류인 도구 결과는 `opened`가 아님(F8).
   완료 판정: 구조 커밋 후 전체 녹색(`show --item`의 `details`, 미지 블록 표시 테스트 포함), 구조 테스트 7 통과, 행동 커밋 두 변경 각각 빨강→초록.
4. **④ `feat/cli-contract`** — `feat: uv 실행과 요약 우선 응답 계약`. 변경마다 S1 테스트 먼저: `uv run` + PEP 723 + `next`·SKILL.md frontmatter·본문 코드 블록·README 명령 동시 변경(구조 테스트 6 전체·8 활성화), Reply/outcome과 cli.py 종료 코드 표, 명령별 Exit 줄, `log` 이벤트→stderr, 응답 모양과 `result --sources`·`show` 번호 일치, run id 접두사·유니코드 라벨, `.ultra-search/.gitignore`, `repl-api` 안내, `opened` 도움말. live의 usage 검증은 status로 옮긴다. 수정한 `--help`는 실행해 의미 단위가 한 줄인지 확인.
   완료 판정: 전체 녹색. 모든 명령 `--help`에 Exit 줄. `log`의 stdout이 `json.loads` 한 번으로 읽힘. 출처 95개 이상인 실제 `result.json` 사본으로 만든 `result` 응답이 출처 수와 무관하게 답 + 열어 본 출처 크기. 한글 라벨(NFD 입력 포함)로 `search` → `next` → `result` → 접두사로 `resume` 왕복 통과, 모호한 접두사의 `resume`이 후보를 보고. `show --source`가 진행 중 런과 `stop` 뒤 런에서도 확보한 본문을 돌려주고, 완료 런에서는 `result --sources`의 `n`과 같은 출처를 가리킴. 심볼릭 링크 설치 경로의 `uv run` 호출이 `claude -p --permission-mode default`에서 `permission_denials` 없음.
5. **⑤ `docs/skill-text`** — `docs: 스킬 본문과 README를 새 계약에 맞게 갱신`. SKILL.md 초안 반영, README(위 구조), 이 계획 파일 커밋(`.claude/settings.json`·`.agents`·`.codex` 제외), 행동 검증, 최종 리뷰, 전문 승인, live 실제 exec 3개.
   완료 판정: 아래 "스킬 완료 조건" 전부.
6. **⑥ 릴리즈** — `git tag v1.0.0` 푸시 + `gh release create v1.0.0`(한국어 노트: 할 수 있는 것 / 설치(uv 포함) / 이번에 바뀐 것(F1·F2 수정 포함) / 검증한 것과 안 한 것 / 전제).
   완료 판정: `gh release view v1.0.0` 성공, 로컬·원격 main 일치, `git status`에 의도한 미추적 파일만.

## 스킬 완료 조건 (skill-maker)

- 성진이 SKILL.md 전문을 승인(침묵은 승인 아님).
- 행동 검증: 격리 디렉터리에서 `claude -p --permission-mode default --output-format json`, 도구 `Bash,Read,WebSearch,WebFetch`, 설치된 스킬(심볼릭 링크) 사용, 가짜 Aside는 환경변수(`ULTRA_SEARCH_ASIDE_BIN`·`ULTRA_SEARCH_ASIDE_HOME`·`FAKE_ASIDE_SCENARIO`)로. 과제와 판정 — T1 알려진 URL 요약 → `fetch`만 · T2 출처 선택이 필요한 질문 → 목표·출처 제약·증거를 담은 `search`(위임 프롬프트 품질이 현행 수준) · T3 가짜 `slow` → 감시 종료를 완료로 보고하지 않고 `next`로 `result`까지 · T4 챌린지를 돌려주는 fetch → 그 출처를 읽은 것으로 인용하지 않음 · T5 Aside 사용 불가(`ULTRA_SEARCH_ASIDE_BIN`이 없는 경로) → `doctor` 결과를 보고하고 WebSearch/WebFetch를 쓰지 않음. 부수 관찰: 응답을 `python3`로 거르는 횟수. `permission_denials`로 실패한 실행은 입력을 보충해 재실행.
- `claude plugin validate --strict /Users/seongjin/Coding/Ultra-Search/.claude/skills` 종료 0.
- 프로젝트에서 `claude -p "/skill-doctor"`로 트리거가 겹치는 이웃 스킬 확인.
- 최종 SKILL.md·`--help`를 codex(gpt-6-astra high)가 네 프레임으로 리뷰, 선별 반영.
- `uv run --python 3.10 --with pytest pytest tests/ -q` 녹색, `-m live` 전체 통과(Aside 실행 중).
- 개발 기록(이 계획, 실사용 증거, 기각한 대안)은 커밋·PR 본문과 이 파일에 두고 스킬에는 넣지 않는다.

## 재사용할 기존 자산

- `tests/fake_aside/aside`의 시나리오(simple·slow·subagent·orphan·fail·empty·negative·no_session·aside_down·repl_timeout), `FAKE_ASIDE_CALLS`, REPL 라우팅. `tests/conftest.py`의 격리 픽스처(실제 `~/.aside`를 읽지 않음).
- `evidence.turn_start_index`·`merge_sources`·`Turn`, `follow.parse_since`/`format_cursor`, `commands.next_step`, `registry._meta_lock`·`atomic_write_json`·`create_run`, `sessions.copy_new_lines`(사본 크기를 커서로), `classify`의 판정 순서와 임계값, `discover.discover` — 옮기되 새로 쓰지 않는다.

## 위험과 미확정

- 녹화 fixture(공개 레포): 공개 출처만 쓰는 질문으로 새로 녹화하고, 부모·자식·stdout 전체를 검토한 뒤 축약한다.
- stdout 대체 경로의 최종 메시지 경계는 Aside 출력 모양(`\x1b[2m`…`\x1b[0m`)에 기대는 휴리스틱이다. 상관이 정상이면 거의 쓰이지 않으며 한계는 `성진:` 주석으로 남긴다.
- live 실제 exec 3개는 실행할 때마다 구독을 쓴다.
- 두 전사 형식(lifecycle 있음/없음)을 함께 지원하는 근거는 옛 fixture뿐이다(Aside는 세션을 하루 안에 지운다). 옛 형식 지원은 fixture가 새 형식으로 다 바뀌면 걷어낼 수 있다(`성진:` 주석).
- codex 계획 재검토(같은 스레드) CONFIRMED 4건 반영: ②·④ 사이 종료 코드 중간 상태 → 함수 이동표 첫 줄, `extract_document` 분할 → 이동표, doctor 쓰기 확인은 doctor에 유지 → 이동표, `show --source`의 진행 중·중단 런 조회 보존 → 응답 계약과 ④ 판정.
- codex 계획 리뷰 19건 중 기각 없음. 반영 위치: 1·15 → ①과 "F1·F2 수정 규칙", 2 → 구조 테스트 6·8을 ④에서 활성화, 3 → `Event` 필드, 4 → F8·③ 행동 커밋, 5·6 → `aside/exec_output.py`·`aside/browser.py`(성진 합의), 7 → 함수 이동표, 8 → 여는 user 레코드 규칙, 9·10 → run id 계약·④ 판정, 11·12 → 응답 계약, 13·14 → 구조 테스트 3·4·5·7, 16 → live 사실·결정, 17 → saved 보장, 18 → fixture 검토, 19 → SKILL.md 초안(예시 유지, 이유 재서술).

## 구현 기록 (2026-10-02)

PR #10(0단계) · #11(①) · #12(②) · #13(③) · #14(④) · ⑤ docs PR로 진행했다. 각 PR 본문에 실행한 명령·수치와 codex 리뷰 처리가 있다.

### 구현 중 결정과 계획과 달라진 점

| 구분 | 내용 | 근거 |
|---|---|---|
| 성진 결정 | REPL로 연 페이지도 opened 출처로 센다(③ 행동 커밋). 탭 열기 줄 `…Opened a new tab…, page → 제목 (URL)`과 스냅숏 머리 `- title: "제목" [url=URL]`를 출력 순서대로, 실패한 호출 안의 것도 | live search가 repl로만 python.org를 읽어 출처 0. 실제 repl 결과 3,077개 중 탭 표시 389·스냅숏 883 |
| 실측으로 정정 | F6의 태그는 `<quote source=…>`가 아니라 `<quote>`·`<quote ref="id">`·`<quote refs="id">`(최종 답에서 71·22·2회) | 실제 전사 |
| 실측으로 정정 | "Aside가 세션을 하루 안에 지운다"는 문구를 "제 일정대로"로. 9월 13일 이후 세션 디렉터리가 모두 남아 있다 | `~/.aside/u/0/sessions` 날짜별 집계 |
| 실측으로 추가 | lifecycle 형식의 자식은 `final-started` 전에 `stop`으로 멈춘 메시지(부모에게 보내는 중간 보고)를 쓴다. 이번 턴의 프롬프트에서 자른 전사도 그 턴의 `started`까지 포함해 판정한다 | codex 리뷰가 실제 자식 전사로 재현 |
| 실측으로 추가 | search·resume은 런을 예약하기 전에 aside CLI가 쓰는 데몬(`DAEMON_BASE_URL` 또는 21420, 프록시 없이)을 확인해 앱이 닫혀 있으면 3. 전에는 오류 문구가 실패한 조사의 답이 되고 4 | codex 리뷰, aside CLI 내장 소스 |
| 계획과 다름 | 런 종료 상태 집합은 `research/commands.py`가 아니라 `research/states.py`(follow가 commands를 import하면 순환) | — |
| 계획과 다름 | 결과 없는 런 항목은 `run_id, state, empty, note`만(계획 예시 그대로), 도움말에 명시. 상태 항목에 `resumed_from` 추가 | codex 지적 기각 |
| 추가 | `doctor`는 아무것도 쓰지 않는다(없는 runs 디렉터리는 가장 가까운 기존 상위에서 쓰기 시험). `.gitignore`는 기본 저장소에 쓸 때만, 실패해도 명령을 막지 않음 | `claude -p` 권한 실측 중 빈 `.ultra-search/`가 남음, codex 리뷰 |
| 성진 승인(⑤ 전문 승인) | SKILL.md "Follow state, not silence"에 깨워줄 것이 없는 실행(`claude -p`, 서브에이전트, 예약 작업)은 `next`를 포그라운드로 돌려 결과까지 수거한다는 한 문장 | 행동 검증 T3가 두 번 모두 백그라운드로 돌리고 결과 없이 끝남, 문장 추가 뒤 통과 |
| 버전 | `VERIFIED_DAEMON_VERSION` 1.26.829.1514 → 1.26.1001.14(①) → 1.26.1002.1950(⑤, live 14개 통과). CLI 바이너리는 1.26.810.1915 그대로 | live |
