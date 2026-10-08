# ultra-search 스킬 개선 계획 (수리 + 축소, v2.0.0)

## Context

`ultra-search`는 Claude의 웹 층을 네이티브 `WebSearch`/`WebFetch`에서 성진의 로그인된 Aside 브라우저로 바꾸는 전역 스킬이다(`~/.claude/skills/ultra-search` → 이 레포 `.claude/skills/ultra-search` 심볼릭 링크). 목적은 Claude의 답이 실제로 확보한 원문에 근거하게 하는 것이고, 실사용의 중심은 의원실 업무(국감 질의·보도자료·고시·처리방침 원문)다. 10/2에 v1.0.0(PR #10~#15)을 냈다.

성진은 skill-maker 프레임으로 이 스킬을 비판적으로 다시 보고 품질을 위한 개선 계획을 원했다. 계획 세션에서 실사용 전사·런 기록·Aside 세션을 실측하고 codex(gpt-6-astra high)의 적대적 리뷰를 반영한 결론: **코드 품질은 높아 재작성하지 않는다. 새 기능도 더하지 않는다. 기존 명령이 약속을 못 지키는 결함 3개를 고치고, Claude가 고를 표면을 줄인다.**

1. 감독자가 조사가 끝나기 전에 결과를 확정해 답 전체를 잃는 결함(M18)
2. 에이전트가 저장한 원본 파일(PDF·이미지)을 Claude가 열 수 없는 결함(M7, M19)
3. `fetch`가 한국 공공문서의 주 형식 HWP/HWPX를 못 읽는 결함(M11, M16)
4. 표면 축소: 명령 14→12, 대기는 `result --wait` 하나(M3, M9)
5. SKILL.md·README를 바뀐 계약에 맞추고, 위임 예시는 대조 실험으로 남길지 정한다

## 실측과 사실 (계획 세션, 2026-10-09)

| # | 사실 | 근거 |
|---|---|---|
| M1 | 기준선 `410 passed, 14 skipped`(3.10, 7분) | `uv run --python 3.10 --with pytest pytest -q -p no:cacheprovider` |
| M2 | 환경 정상. 데몬 1.26.1008.1938(검증 기준 1.26.1002.1950과 다름), CLI 1.26.810.1915(8월) | `cli.py doctor`, `aside --version` |
| M3 | `cli.py` 호출 형식이 된 9/25 이후 비개발 프로젝트의 호출 101회(9월 27·10월 74, 하위 명령 파싱 잡음 3건 포함): search 28 · fetch 24 · result 21 · log 16 · status 4 · resume 2 · sessions 1 · show·stop·map·crawl·repl-api·doctor 0. 10/2 이후 세션은 8개 | 전사 집계(정규식 `ultra-search/scripts/cli.py"?\s+(\S+)`) |
| M4 | 같은 101회 중 45회에 파이프(`--help \| head`, `result \| python3 -c`로 한 런만 추출). auto 모드에서 동작을 막지는 않는다 | 같은 집계 |
| M5 | 모델이 10/2 이후 6세션 중 4세션에서 `--runs-dir`를 스크래치패드로 주거나 `cd`해 사용자 폴더를 피했다. 피하지 않은 곳은 Obsidian 볼트 루트·`요구 자료/` 안에 `.ultra-search/`가 생겼다 | 전사, `**/.ultra-search/runs` |
| M6 | Claude는 search 답의 주장("고시 제9조의2제1항 원문", "kosmes 처리방침 제4조 22번", "KSPO PDF 83·84행")을 원문 확인 없이 전달했다. 실사용 전체에서 `show` 0회 | 10/5·10/8 Obsidian 세션 |
| M7 | Aside 에이전트가 내려받은 원본은 세션의 `artifacts/`(하위 폴더 포함, 예 `artifacts/tmp/bohun_rfp.hwpx`, 공백·괄호·한글 이름, 15MB PDF·12MB CSV)에 남고, 답은 `artifacts/KSPO_….pdf`처럼 상대 경로로만 말한다. 스킬은 이를 가져오지도 경로를 주지도 않는다 | `~/.aside/u/0/sessions/*/artifacts/`, `result.json` |
| M8 | 저장된 런의 감시 시간(완료·고아·abandoned 포함 82런) p50 341초 · p90 861초 | `meta.json` `finished_at − started_at` |
| M9 | 대기 흐름 `search`(100초) → `log --follow`(백그라운드, 진행 서사 4.4KB) → `result` 3단계. 모델은 `log` 출력을 쓰지 않고 곧바로 `result`를 부른다 | 전사 |
| M11 | HWPX는 `unsupported`, HWP 미리보기 URL은 `blocked`. 최근 Aside 세션 1,294개 중 139개(11%)에 hwp/hwpx 등장(acrc.go.kr·mss.go.kr·scourt.go.kr·mpva.go.kr 첨부) | `fetch` 실측, 세션 grep |
| M12 | Google은 REPL `fetch`·Aside `googleSearch.search` 모두 봇 챌린지, Naver 검색 HTML엔 캡차 폼. DuckDuckGo HTML은 1.5초에 한국어 질의도 정확(→ 철회한 `find`의 근거였음) | REPL 실측 |
| M13 | Aside REPL엔 내장 스킬의 사이트 API(youtube·x-twitter·google-docs·imageSearch 등)가 있다(→ 노출 철회) | `~/.aside/u/0/skills/builtin/` |
| M14 | REPL `aside.sessions.*`는 CLI가 만든 세션을 모른다("Session not found"). `~/.aside` 파일 파싱을 대체할 공식 경로는 없다 | REPL 실측 |
| M15 | 코드 품질은 높다: 실측으로 다진 경계 처리(셸 임계 80단어, 챌린지 강·약 표지, 턴 경계, 자식 완료, 원자적 쓰기)가 docstring에 이유와 함께 있고 410개 테스트에 고정 | 코드 정독 |
| M16 | HWPX는 표준 라이브러리(`zipfile`+`xml.etree`)로 추출 가능: mss.go.kr 첨부 293문단·17,509자·표 40개, `mimetype`=`application/hwp+zip`. HWP 5.0은 `olefile` + 약 50줄(FileHeader 플래그 → `BodyText/Section*` raw deflate → 레코드 태그 67 `PARA_TEXT` UTF-16LE)로 대법원 결정·헌재 결정 본문 추출. 단 스크래치 파서는 탭(9)·묶음/고정폭 빈칸(30·31)·하이픈(24)을 지워 `사건2018헌바130`처럼 붙이고, 문자를 WCHAR 단위로 `chr()`해 서로게이트 쌍을 깨며, 암호(bit 1) 플래그를 검사하지 않는다. 미리보기 `PrvText`(약 1KB)는 표를 `<…>`로 표기해 본문과 형식이 다르다 | 스크래치 `hwp/hwp5.py`, 표본 `scourt.go.kr/sjudge/1625214940201_173540.hwp`(`application/x-hwp`)·`ccourt.go.kr/…/20200123090701_cmggokmipgwnxld.hwp`(`application/x-msdownload`)·`mss.go.kr/…/a37ab8d8-….hwpx`, codex 대조 |
| M17 | 작업 디렉터리 밖 파일 Read: `--permission-mode default`는 거부, `auto`는 허용 | `claude -p --safe-mode --model haiku --tools Read` 프로브 |
| M18 | **감독자가 조사가 끝나기 전에 결과를 확정한다.** 10/3 이미지 런의 실제 전사: `subagent_wait` 11:43:58.976 → 자식 완료 system-message 11:44:15·11:45:12 → 최종 답 11:45:19.397 → `finished` 11:45:30.602. 호출자는 11:44:15에 `log --follow` 종료, 11:44:22에 `result`로 `completed_with_orphans`·답 `""`를 받았다. 관측: 확정 시각 ≤11:44:15. 추정(현재 코드에서 역산, 런 디렉터리는 지워짐): `aside exec`가 ≈11:44:05에 코드 0으로 종료하고 settle 10초 뒤 확정. 원인은 "프로세스 종료 = 턴 종료" 가정(`research/supervisor.py` docstring·`supervise()` 루프). 남아 있는 lifecycle 런 13개에서는 재현 0건(드묾, 그러나 답 전체를 잃음) | 세션 `2026-10-03_7E9w0qwRLgWWdnar`, Claude 전사 `93728070…jsonl` |
| M19 | 그 런이 찾은 사진(1752×1218 JPG)은 세션 `artifacts/`에 있었다. 답이 artifacts를 가리킨 런 77개 중 2개, 최근 세션 다수에 artifacts(PDF·CSV·JPG) | `result.json` 집계, `sessions/*/artifacts` |
| M20 | `--help` 줄 수: search 34·fetch 38·crawl 34·resume 33, 나머지 ≤28. `search --help \| head -40`은 전부 보였다 | `--help \| wc -l` |
| M21 | 릴리스 `v1.0.0` 존재, 레포 `tjdwls101010/Ultra-Search`는 PUBLIC | `git tag`, `gh repo view` |
| M22 | `fetch_batch.js`가 바이너리를 세션 디렉터리에 저장하고 확장자를 MIME으로만 고른다(HWP의 `application/x-msdownload`는 `bin`, HWPX는 `zip`); `looksBinary`는 text/XML MIME을 매직 바이트보다 먼저 본다. `fetch.classify.extract_document` → `converter.document_text`(anydoc)는 둘 다 인식 못 한다. `acquire._save`는 `record["ext"]`로 `original_path` 확장자를 정한다 | `aside/snippets/fetch_batch.js:20-44`, `fetch/classify.py:202`, `converter/node.py:59`, `fetch/acquire.py:189` |
| M23 | 가짜 Aside는 `fetch_batch` 라우트로 문서 파일을 돌려줄 수 있고(`tests/test_pages.py:41,357`, 라우트가 `ext`를 미리 줌 — JS는 실행하지 않음), 리플레이의 `{"__after_exit__": SEC}`로 프로세스 종료 뒤 부모 전사 쓰기를 재현한다(자식 전사는 쓰지 않음). 기존 `test_run_directory.py:179`가 `__after_exit__ 1.0`·`settle=5.0`으로 짧은 지연은 이미 다룬다 | `tests/fake_aside/aside:17-21,132,161` |
| M24 | `runs.create_run`은 `state="starting"`으로 만들고, 감독자 pid는 `start_exec()` 뒤에 기록된다. `Run.update_meta`의 잠금은 값을 합칠 뿐 terminal 상태를 보호하지 않는다. `evidence.turn_of()`는 marker부터 파일 끝까지를 이 턴으로 보고, `_sync`의 활동 계산은 이전 턴의 자식까지 포함한다 | `runs/registry.py:74,128`, `research/supervisor.py:94,165`, `research/evidence.py:230` |
| M25 | 제거 대상에 걸린 곳: `test_research.py`(status 31·stop 20·--follow 15·--follow-timeout 12·--since 7·possibly_stalled 5줄, `stop`이 백그라운드 정리 수단으로도 쓰임 `:1870`, 완료 응답의 `next`를 가정 `:1934`), `test_run_directory.py:377`(stop과 완료 경쟁), `test_environment.py:305`(버전 1.0.0)·`:356`(NEXT_HELP 대상), `test_contract_fake_aside.py`, `test_pages.py`, `conftest.py`, `live/test_live.py`; `research/commands.py:408`(resume 오류 복구가 `log --follow` 지시), `cli.py:197`(label 도움말이 `status` 언급)·search/result 설명의 "usage and children are in `status`"·`:348` 상태 설명; SKILL.md:39(`status`)·"Watching is not cancellation" | grep, codex |

## 합의 원장

| 구분 | 내용 | 근거 |
|---|---|---|
| 결정 | 목적 요약(원문 근거·닿음·충실도·위임·보존, Aside 불가 시 대체하지 않고 묻기)이 의도와 맞다 | 성진 |
| 결정 | 스킬은 역량을 더할 뿐 활용 목적(얼마나 확인할지 등)을 미리 정의하지 않는다. 다양한 목적에 쓰일 수 있어야 한다 | 성진 |
| 결정 | 표적 개선: 코드 전면 재작성 안 함 | 성진 |
| 결정 | 꼭 필요한 기능만. 기능이 많으면 Claude가 주요 기능을 쓰는 데 헷갈린다 | 성진 |
| 결정 | 방향 "수리 + 축소": 새 명령 없음. 인용 자동 대조·`find` 명령·Aside 사이트 API 노출 철회 | 성진 |
| 결정 | 명령 14→12: `stop`·`status` 제거, `search`/`resume --timeout` 제거, `log`는 한 번 보는 진단용(`--follow`·`--since`·`--heartbeat`·`--follow-timeout` 제거), 대기는 `result --wait SEC` 하나 | 성진 |
| 결정 | 상태 위치 현행 유지(작업 디렉터리 `./.ultra-search/`, `--runs-dir`) — skill-maker의 `data/` 규칙에서 벗어나는 유일한 지점, 이유는 README·구조 테스트에 이미 기록 | 성진(261001·오늘 재확인) |
| 결정 | `fetch`가 HWPX·HWP를 읽는다. `olefile`은 `cli.py` PEP 723 의존성 | 성진 |
| 결정 | SKILL.md는 바뀐 계약만 반영. 위임 예시는 대조 실험(예시 뺀 본문으로 위임 프롬프트 3회 수집)이 3/3 같은 모양이면 지우고 원리 한 문장만 남긴다 | 성진 |
| 결정 | 0단계에서 `aside --update`로 CLI를 올리고 그 상태를 live 검증 기준으로 삼는다 | 성진 |
| 결정 | 끝난 뒤 v2.0.0 릴리스(명령 제거는 호환 파괴) | 성진 |
| 결정 | 개선한 스킬은 skill-maker 프레임을 철저히 반영한다(아래 "skill-maker 프레임 대응") | 성진 질문 |
| 판단 | 감독자 결함(M18)은 합의된 "수리"에 포함 | M18 |
| 판단 | 파이프(M4)·`--help` 길이(M20)는 별도 작업 없음 | M4, M20 |
| 판단 | `status`·`--timeout`을 없애면 사라지는 "멈춘 런" 신호는 (a) 감독자의 무활동 상한(프로세스 생존과 무관)과 (b) `result`의 감독자 생존 확인으로 대신한다 — 없으면 `result --wait`의 `next` 연쇄가 끝나지 않는다 | codex #1·#2 |
| 이전 결정 유지 | SKILL.md·`--help`는 영어, 커밋·PR·README·릴리스 노트는 한국어. 코드 단계는 `coding` 스킬. codex 리뷰는 gpt-6-astra high(읽기 전용) | 260925·261001 계획, 메모리 |

## skill-maker 프레임 대응

| 프레임 | 이 계획에서 |
|---|---|
| 네 성질: principle over rail | SKILL.md 수정 문장은 이유와 함께(예: "Nothing here cancels delegated work" + 그래서 시작 전에 범위를 정한다). 고정 절차 추가 없음 |
| interface over document | 새 동작(`result --wait`, `artifacts`, HWP)은 `--help`·응답 JSON·상태 이름이 소유하고 SKILL.md는 언제·무엇을 조심할지만 |
| for the model, not the maintainer | 실측·기각 대안·codex 기록은 이 파일·PR 본문·커밋에, 스킬 본문엔 넣지 않음 |
| dense | 표면 축소(명령 14→12, log 플래그 4개·`--timeout` 제거), SKILL.md는 덜어내기(대조 실험으로 예시 삭제 판정) |
| 사용자 지식 끌어내기 | 이 세션에서 읽을 수 있는 것(전사·런·세션)을 먼저 읽고, 결정 9개를 AskUserQuestion으로 합의, 원장에 사실·판단·결정 구분 |
| contrast with the default | 위임 예시 대조 실험, 행동 검증 T1–T6 |
| 기존 스킬에서 시작 | 실패를 지식 부족이 아니라 실행 결함(M18·M7·M11)으로 분리, 아래 "보존할 행동"을 먼저 고정, 삭제·통합을 개선으로 셈 |
| Code the skill bundles | 트리 동일(`cli.py` 유일 진입점, 패키지 하나, 단위 종류), 새 system 단위 `hwp/`(남이 소유한 형식은 그 이름의 하위 패키지), import 한 방향, 구조 테스트 갱신, `uv run` + PEP 723(`olefile`), 각 `<command> --help`가 인자·출력·실패를 스스로 설명, stdout JSON 하나·값싼 신호 먼저, 테스트는 스킬 밖 |
| 벗어나는 지점 | `data/` 대신 `./.ultra-search/`(성진 결정, README·구조 테스트 docstring에 이유) |
| 완료 조건 | 전문 승인, `claude plugin validate --strict`, 계약 대비 코드 검증, 구조 테스트, 다른 모델 계열(codex)의 네 성질 리뷰, `/skill-doctor`로 이웃 경계, 개발 기록은 스킬 밖 |

## 보존할 행동 (바꾸기 전에 고정, 테스트가 이미 지킴)

- `fetch` 항목 상태 8종의 뜻과 "ok 아닌 항목은 저장하지 않음", 셸→탭 승격, 챌린지 판정, `--format html`, `original_path`.
- `search` 동기 대기(`--wait 100`)와 끝나면 답을 바로 주는 것, 병렬 그룹, 한글 라벨 run id와 고유 접두사 해석, 재개 런의 턴 경계, `sessions`로 앱 세션 재개.
- `next`의 뜻: 반환된 그대로 실행, 백그라운드는 완료 알림을 받을 무언가가 있을 때만, 깨워줄 것이 없으면 포그라운드.
- `show --source n`이 `result`의 `n`과 같은 출처, `show --item N`이 `log --level steps`의 `#N`.
- Aside 불가 시 종료 코드 3과 `doctor`의 해결 안내, 종료 코드 숫자 0/2/3/4/5.
- `map` → `crawl --from`, saved의 이름·덮어쓰기 보장, `./.ultra-search/.gitignore`.

## 변경 상세

### ① 턴이 끝나야 런이 끝난다 (M18)

용어:
- **이 턴** = 이 런의 marker가 든 user 레코드(앞의 `started`부터) ~ 그 뒤 첫 `finished`. 그 뒤의 `started`부터는 다른 턴이다(`evidence.turn_of`에 끝 경계를 둔다).
- **관측됨** = 이 턴의 marker가 전사에 보임. **감싸임** = 관측된 이 턴의 구간에 lifecycle 레코드가 있음(형식은 관측된 턴으로만 판정한다 — 전사 전체로 판정하면 옛 형식 세션을 재개한 런을 잘못 가른다). **끝남** = 감싸인 이 턴에 `finished`가 있음.
- **활동** = 이 런의 파일(stdout·부모 사본) + **이 턴의 자식** 전사의 마지막 쓰기 시각(`_sync`가 모은 이전 턴 자식 제외).
- **자연 종료** = `aside exec`가 스스로 끝남. 감독자가 끝낸 경우(`terminated_by_supervisor`)의 종료 코드는 판정에 쓰지 않는다.

감시 중(매 폴링, 위에서 먼저 맞는 것이 이긴다):

| # | 조건 | 결과 |
|---|---|---|
| W1 | 자연 종료, 코드 ≠ 0 | 마지막 동기화 뒤 `failed`(지금 그대로) |
| W2 | 이 턴이 끝남 | 마무리 F로 |
| W3 | 자연 종료 코드 0, 세션 미발견, `DISCOVERY_DEADLINE` 지남 | `completed_unstructured`(지금 그대로) |
| W4 | 자연 종료 코드 0, **세션은 발견됐고** 이 턴 미관측 | settle 동안 나타나길 기다리고, 끝내 안 보이면 stdout으로 `completed_unstructured`(지금 그대로 — `test_run_directory.py`의 늦은 재개 턴 두 테스트가 지킴). 세션 미발견이면 W4가 아니라 W3의 기한까지 계속 찾는다 |
| W5 | 자연 종료 코드 0, 이 턴 관측됐고 감싸이지 않음(옛 형식) | 지금의 settle 판정(`completed`/`completed_with_orphans`) |
| W6 | 무활동 ≥ `IDLE_LIMIT`(600초) — 프로세스가 살아 있든 코드 0으로 끝났든 | `abandoned`, 이유 "the turn went quiet before it finished", 그때까지의 출처·자식·답으로 `result.json` |
| W7 | 그 밖(관측·감싸임·미완료로 코드 0 종료 = M18, 또는 프로세스 생존) | 계속 감시 |

마무리 F(이 턴이 끝난 뒤, 최대 settle 10초): 동기화하며 프로세스의 자연 종료와 이 턴 자식들의 완료를 기다린다. 기다림은 "자연 종료했고 자식이 모두 끝남"이면 즉시, 아니면 settle이 지나면 끝난다. settle이 지났는데 프로세스가 살아 있으면 감독자가 끝낸다(`terminated_by_supervisor`, 그 종료 코드는 쓰지 않음). 판정은 어느 분기로 끝났든 하나의 규칙으로:
1. 자연 종료 코드 ≠ 0 → `failed`.
2. 이 턴 마지막 assistant의 stop이 `error` → `failed`(코드 0이어도 — CLI가 먼저 0으로 끝난 M18 같은 경우).
3. 끝나지 않은 이 턴의 자식이 있음 → `completed_with_orphans`.
4. 그 밖 → `completed`.

- `IDLE_LIMIT`·settle은 `supervise()` 인자로 주입 가능(시험용), 기본 600초 + `성진:` 주석(자식까지 10분 넘게 조용한 정상 조사는 끊긴다).
- 감독자 시작 순서(④에서 생존 확인과 함께 구현): `aside exec`를 띄우기 **전에** 메타 잠금 안에서 상태가 아직 `starting`인지 확인하고 자기 pid를 `supervisor_pid`로 기록한다. 이미 terminal(예: `result`가 `abandoned`로 확정)이면 아무것도 띄우지 않고 끝난다.
- 모듈 docstring의 "the only hard signal is the process exiting"을 이 표로 고친다.

### ② 에이전트가 저장한 파일을 결과에 (M7, M19)

- `aside`(system): `session_artifacts(session_id) -> list[(rel_path, Path, mtime)]` — 세션 `artifacts/` 아래를 재귀로, 일반 파일만(심볼릭 링크·특수 파일 제외), 해석한 경로가 그 폴더 안인 것만. `rewrite_artifact_refs(text, mapping) -> str` — 답의 `artifacts/<상대경로>`와 세션 절대 경로 참조를 복사본 경로로(마크다운 링크 목적지의 공백·괄호·한글 포함). 둘 다 Aside 형식 지식이라 aside에.
- 수거 대상: (a) 이 턴 시작 이후, 그리고 다음 턴이 있으면 그 `started` 이전에 수정된 파일 + (b) 이 런이 돌려주는 부모·자식 답이 명시적으로 참조하는 기존 파일(재개로 이전 자식의 늦은 결과를 수거할 때 그 파일도 열려야 한다, `test_run_directory.py:474`의 보장). (b)라도 이 턴이 끝난 뒤 다른 턴이 고쳐 쓴 파일(수정 시각이 다음 턴 `started` 이후)은 가져오지 않고 `artifacts_missing`에 "changed by a later turn"으로 남긴다.
- 복사: 감독자가 끝날 때(①의 `abandoned` 포함) 파일마다 임시 이름으로 스트리밍 복사 후 rename. 복사 전후로 크기·수정 시각·inode를 비교해 바뀌었으면 한 번 다시 복사하고, 그래도 바뀌면 `artifacts_missing`에 "changing while copied"(고아 자식이 아직 쓰는 경우). 부모 것은 `<run>/artifacts/<rel>`, 자식 것은 `<run>/artifacts/<child_id>/<rel>`(`Run.artifacts_dir`, runs가 배치 소유). 파일 하나의 실패는 `result.json`의 `artifacts_missing: [{path, error}]`와 note로 남기고 런을 실패시키지 않는다. 복사가 어떻게 끝나든 `result.json`은 쓴다. orphan·abandoned의 파일은 그 시점의 스냅숏임을 note에.
- 참조 치환은 **답을 합치기 전에 세션별 매핑으로**(부모·자식의 같은 이름 파일 구별) — `evidence.Turn.answer`가 스트림별 매핑을 받는다. 복사에 성공한 파일만 치환.
- `result.json`과 `search`·`resume`·`result` 런 항목에 `artifacts: [절대 경로, …]`(없으면 키 생략). 항목 순서: `run_id, state, empty, sources_total, sources_opened, note` → `answer` → `opened_sources` → `artifacts` → `result_path`.

### ③ fetch가 HWP·HWPX를 읽는다 (M11, M16, M22)

- 새 system 단위 `hwp/`(한컴 형식): `hwp/__init__.py`가 `extract(path) -> dict | None` 하나를 내보낸다. 내용이 HWP·HWPX가 아니면 `None`(HWP 아닌 OLE·ZIP 포함), 맞으면 `{"status": "ok"|"unsupported", "text", "error", "ext": "hwp"|"hwpx"}`. **예외를 밖으로 내지 않는다**: 인식했지만 손상된 문서(zlib·레코드 길이·ZIP/XML 오류)는 `unsupported`와 오류 문구.
  - `hwp/hwpx.py`: zip이고 `mimetype`이 `application/hwp+zip`이면 `Contents/section*.xml`을 번호 순으로. 표는 행마다 한 줄, 셀은 ` | `, 표 안 문단이 바깥 문단으로 중복되지 않게(병합 셀은 펼치지 않음 — `성진:`).
  - `hwp/hwp5.py`: OLE이고 `FileHeader`가 `HWP Document File`이면. 플래그 bit 1(암호)·bit 2(배포용)는 각각 `unsupported`("password-protected HWP"/"distribution-protected HWP"). 제어문자: 문자 제어(1 WCHAR) 0·10·13·24–31, inline(8 WCHAR) 4–9·19·20, extended(8 WCHAR) 1–3·11·12·14–18·21–23. 출력은 9 → `\t`, 10 → 줄바꿈, 13 → 문단 끝, 24 → `-`, 30·31 → 공백, 나머지 제어 제거. 일반 텍스트 구간은 UTF-16LE로 디코딩(서로게이트 쌍). 표 셀은 문단으로 나온다(`성진:`).
- `fetch/classify.py`의 `extract_document`가 `converter.document_text` 앞에서 `hwp.extract`를 묻고, `None`이면 지금처럼 anydoc. 인식되면 `Document`가 `ext`를 갖고 `acquire._save`가 `original_path` 확장자를 그것으로 정한다(스니펫의 MIME 확장자 목록은 고치지 않는다 — 판별은 내용으로).
- 알려진 한계(`성진:`): 서버가 HWP를 `text/*`·XML MIME으로 보내면 `looksBinary`가 텍스트로 보고 파일이 Python까지 오지 않는다.
- `cli.py` PEP 723 `dependencies = ["olefile>=0.47"]`. 테스트 명령 `uv run --python 3.10 --with pytest --with olefile pytest`.
- `fetch --help`의 문서 목록에 "HWP, HWPX"를 더한다.

### ④ 대기는 `result --wait` 하나, 명령 14→12 (M3, M9)

- 제거: `stop`(파서·`research.stop`·감독자 `stop_requested`), `status`(파서·`research.status`), `search`/`resume --timeout`(`watch_timeout`), `log`의 `--follow`·`--since`·`--heartbeat`·`--follow-timeout`(`follow.parse_since`·`format_cursor`·heartbeat·`run.still-running`).
- 추가 `result --wait SEC`(기본 0): 기다리는 동안 progress 레벨 진행 줄을 stderr로(그룹이면 `[run_id]` 접두사), 모두 끝나거나 SEC가 지나면 stdout에 `result` JSON. 아직 도는 런이 있으면 최상위 `next` = `result … --wait 570`(`bash_timeout_ms` 600000, `run_in_background` true).
- `next`는 항상 이 하나(`research.commands.next_step`). `NEXT_HELP`는 `search`·`resume`·`result`에 붙인다.
- 감독자 생존(`result`가 매번, 비terminal 런마다): 메타 잠금 안에서 다시 읽어 판단한다(`Run`에 조건부 갱신, runs 소유).
  - terminal이면 그대로.
  - `result.json`이 있으면(결과를 쓰고 메타를 쓰기 전에 죽은 경우) 그 파일에서 `state`와 함께 `orphan_children`·`children`·`empty`·`exit_code`를 메타로 복구한다 — `run_summary`가 고아 목록과 부분 결과 안내를 메타에서만 읽기 때문.
  - `supervisor_pid`가 기록돼 있고 그 프로세스가 없으면 `abandoned`("the supervisor is gone").
  - `starting`이고 `supervisor_pid`가 없으며 생성 뒤 60초가 지났으면 `abandoned`("the supervisor never started"). 늦게 깨어난 감독자는 ①의 시작 순서에서 terminal을 보고 아무것도 띄우지 않는다.
  - `성진: pid 재사용은 확인하지 않는다`.
- 감독자 시작 순서(① 마지막 항목: 띄우기 전 잠금 안에서 `starting` 확인·`supervisor_pid` 기록)를 이 PR에서 함께 구현한다 — 생존 확인과 짝이라 따로 들어가면 경쟁이 열린다.
- `result` 종료 코드(그룹 포함, 위에서 먼저 맞는 것): 실패·`abandoned`가 하나라도 있으면 4(아직 도는 런이 있으면 `next`도 줌) → 아직 도는 런이 있으면 0 + `next` → 모두 끝났고 모두 비었으면 5 → 0. 전에는 "아직 도는 중"이 4였다.
- `log`: `log [--run|--group] [--level]` 한 번. 이벤트 줄 stderr, stdout `{"ok","command","runs"}`. `show --item N` 번호 매김 유지.
- 같은 PR에서 고칠 호출자·문구: `research.commands`의 resume 오류 복구 문구(`log --follow` → `result --wait`), `cli.py` label 도움말·search/result 설명의 `status` 언급·상태 설명, `research/__init__.py` 공개 이름, `follow.py` docstring, SKILL.md의 `status` 문장과 "Watching is not cancellation"(최소 수정, main이 사이에 거짓 문장을 갖지 않게), README "알아둘 것"의 stop 항목.
- 테스트: 백그라운드 감독자 정리는 `stop` 대신 conftest fixture가 맡는다(테스트가 띄운 `_supervise` 프로세스 종료). 옛 status·stop·follow 단언은 PR 본문 표에 "옛 단언 → 새 위치 또는 삭제 이유"로 옮긴다. `test_run_directory.py:377`(완료 덮어쓰기 방지)은 감독자 생존 확인 경로로 이전한다. 버전 테스트는 ⑥에서 2.0.0으로.
- 사라지는 정보: `status`의 `idle_seconds`·`possibly_stalled`·`live_children`·`usage`·`suspension`(usage는 `result.json`에 남음).

### ⑤ SKILL.md·README

- SKILL.md는 아래 "SKILL.md (구현 후)"대로(④에서 최소 수정한 것 위에). 위임 예시는 대조 실험 결과로 정한다.
- README는 아래 구조대로.

## 구현 후 스킬 디렉터리 구조

```
.claude/skills/ultra-search/
├── SKILL.md
└── scripts/
    ├── cli.py                      # PEP 723(requires-python >=3.10, dependencies = ["olefile>=0.47"]). 파서·도움말·디스패치·JSON 출력·종료 코드 표, 숨은 `_supervise`. 명령 12개
    └── ultra_search/
        ├── __init__.py             # __version__ = "2.0.0"
        ├── outcome.py · ids.py · workspace.py      # helper
        ├── doctor.py               # feature: doctor · setup · repl-api
        ├── research/               # feature: search · resume · log · result · show · sessions (+ 분리 감독)
        │   ├── __init__.py         # 명령 함수 6개, supervise(), run_detached(), LEVELS   ← status·stop 제거
        │   ├── commands.py         # next_step(= result --wait), 응답 모양, 감독자 생존 확인, 종료 우선순위   ← 변경
        │   ├── supervisor.py       # 상태표(①), IDLE_LIMIT, artifacts 수거   ← 변경
        │   ├── evidence.py         # 턴 끝 경계, 이 턴 자식만, 세션별 참조 치환 후 합침   ← 변경
        │   ├── follow.py           # result --wait 진행 출력, log 한 번 보기   ← 축소
        │   ├── render.py · marker.py · states.py
        ├── fetch/                  # feature: fetch
        │   ├── classify.py         # extract_document가 hwp.extract를 먼저, Document.ext   ← 변경
        │   ├── acquire.py          # original_path 확장자를 Document.ext로   ← 변경
        │   └── __init__.py · commands.py
        ├── site/                   # feature: map · crawl (site → fetch)
        ├── aside/                  # system: Aside
        │   ├── __init__.py         # + session_artifacts, rewrite_artifact_refs   ← 변경
        │   ├── sessions.py         # + session_artifacts   ← 변경
        │   ├── transcript.py       # + rewrite_artifact_refs   ← 변경
        │   ├── process.py          # VERIFIED_* 갱신   ← 변경
        │   └── daemon.py · exec_output.py · repl.py · browser.py · snippets/
        ├── hwp/                    # system: 한컴 HWP·HWPX   ← 신규
        │   ├── __init__.py         # extract(path) -> dict | None
        │   ├── hwpx.py             # zip + XML(표준 라이브러리)
        │   └── hwp5.py             # OLE(olefile) + BodyText 레코드
        ├── converter/              # system: Node(Defuddle·anydoc)
        ├── runs/                   # store: 런 디렉터리 (+ Run.artifacts_dir, 잠금 안 조건부 갱신)   ← 변경
        └── saved.py                # store
```

```
<레포 루트>/
├── pytest.ini · README.md(← 변경)
├── tests/
│   ├── conftest.py                 # 감독자 정리 fixture   ← 변경
│   ├── fake_aside/aside            # + 자식 전사까지 쓰는 턴 중 조기 종료 리플레이, artifacts 쓰기   ← 변경
│   ├── fixtures/docs/              # + HWP 2·HWPX 1 공개 표본(전체 검토 후)   ← 변경
│   ├── test_research.py            # status·stop·follow → result --wait 이전/삭제   ← 변경
│   ├── test_run_directory.py       # S2: 상태표·IDLE_LIMIT·artifacts·생존 확인   ← 변경
│   ├── test_pages.py               # S1: fetch HWP·HWPX, 손상·보호 문서와 정상 문서 혼합   ← 변경
│   ├── test_hwp.py                 # hwp 인터페이스   ← 신규
│   ├── test_aside_formats.py       # + session_artifacts·rewrite_artifact_refs
│   ├── test_structure.py           # KINDS["hwp"]="system", fetch→hwp, 한컴 표지 격리   ← 변경
│   ├── test_environment.py         # NEXT_HELP 대상·버전·Exit 줄   ← 변경
│   ├── test_contract_fake_aside.py
│   └── live/test_live.py           # + 실제 HWP(application/x-hwp, x-msdownload)·HWPX fetch, status 의존 제거   ← 변경
├── .claude/plans/261009_ultra-search 스킬 개선 계획.md   # 이 파일(⑤에서 커밋)
└── graphify-out/                   # 머지 뒤 갱신
```

import 방향(구조 테스트): research → aside·runs·outcome·ids / fetch → aside·converter·**hwp**·saved·outcome·ids / site → fetch·aside·saved·outcome / doctor → aside·converter·runs·outcome / aside·converter·**hwp** → outcome·ids / runs·saved → outcome·ids·workspace. 형식 격리 보조 검사에 한컴 표지(`HWP Document File`, `hwp+zip`, `BodyText`, `PrvText`, `FileHeader`)를 `hwp/` 밖 `.py` 금지로, `artifacts/` 참조 형식은 `aside/` 안에만.

## CLI 계약 (구현 후)

- 명령 12개: search · resume · log · result · show · sessions · fetch · map · crawl · repl-api · doctor · setup (+ 숨은 `_supervise`).
- 흐름: `search`(기본 `--wait 100`) → 끝났으면 답 / 아니면 `next` = `uv run "<cli>" result --run <id>|--group <g> --runs-dir <root> --wait 570`(백그라운드) → 그 출력이 결과, 또는 다음 `next`.
- 런 항목(search·resume·result): `run_id, state, empty, sources_total, sources_opened, note` → `answer` → `opened_sources: [{n,url,title}]` → `artifacts: [path]` → `result_path`. 결과 없는 런은 `run_id, state, empty, note`.
- 상태 집합 그대로(completed · completed_with_orphans · completed_unstructured · failed · abandoned). `abandoned`가 생기는 길: 턴이 IDLE_LIMIT 동안 조용함, 감독자가 사라짐/시작 못 함.
- 종료 코드 표(cli.py `ENDINGS`)에서 `status`·`stop` 줄 삭제, `result`는 ④의 우선순위. 제거된 명령·플래그는 `bad_arguments`(2).

## SKILL.md (구현 후)

frontmatter 그대로(`name`, `description`, `allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)`). 영어. references 없음(모든 경로가 본문 전체를 쓴다).

```
# Web work through the user's own browser
  진입점 문단·코드 블록·"--help가 소유" — 그대로
## Choose by the work still needed
  search vs fetch — 그대로
  Reuse evidence…: `result` holds a finished investigation's answer, its sources and the files the agent saved; `show` what it already read. …   ← 저장 파일 추가(⑤)
  map/crawl, resume/sessions, repl-api 문단 — 그대로
## Delegate an objective, not keywords
  원리 문장 · Postgres 예시(대조 실험 결과로 유지/삭제) · 부정 발견 문단 — 그대로
## Follow state, not silence
  Follow the latest response's `next`: a search that outlasts its wait hands back the command that waits for its result. 백그라운드/포그라운드 문장 그대로.   ← 바뀜(④)
  `log` explains a source choice or a thin result after the fact; it is not a way to watch.   ← "status로 감독" 문장 대체(④)
## Boundaries that affect the answer
  - Nothing here cancels delegated work. Only the Aside app stops a run and its credit use; bound the objective before starting work you cannot stop here.   ← "Watching is not cancellation" 대체(④)
  - Only acquired content is evidence. … read what was acquired (`show`, a file in `artifacts`, or `fetch` it) before citing it as read.   ← artifacts 추가(⑤)
  - Partial evidence is not a complete investigation. / Requests act as the user. / Without Aside, stop rather than substitute. — 그대로
  실패 시 복구 문장 — 그대로
```

- 대조 실험(⑤): 예시만 뺀 본문을 격리 환경에 설치하고, 출처 선택이 필요한 질문(T2)으로 `claude -p`를 3회 돌려 가짜 Aside의 `calls.jsonl`에서 `search` 프롬프트를 수집(구독 소모 없음). 판정: 3회 모두 (a) 질문/목표 (b) 출처 제약·선호 (c) 돌려받을 증거(URL 등) (d) 못 찾으면 무엇을 확인했는지를 담으면 예시 삭제, 하나라도 빠지면 유지. 전역 설치본이 변형 본문을 가리지 않음을 전사의 로드된 SKILL.md로 확인.
- 전문 승인은 ⑤에서 AskUserQuestion으로 전문을 보여 받는다(침묵은 승인 아님).

## README 섹션 구조 (한국어)

```
# Ultra-Search
## 왜                (그대로)
## 네 가지 역량      (조사 위임 search/resume · 원문 확보 fetch(+HWP·HWPX) · 사이트 수집 map→crawl · 결과 수거 result(--wait)/show/log — status·stop 삭제, 에이전트 저장 파일 언급)
## 설치              (uv·Node ≥20.19·Aside, 링크·setup·doctor. olefile은 uv가 설치. aside --update 권장)
## 써보기            (result --wait, result --sources, fetch, crawl, --help 예시)
## 알아둘 것         (CLI는 조사를 멈추지 못한다(Aside 앱에서만), 침묵≠정체는 result --wait 진행 줄과 무활동 상한으로, search는 비쌈, 차단 페이지 미저장, ./.ultra-search/)
## 구조              (트리에 hwp/, 단위 종류·import 방향, ./.ultra-search/ 이유, 구조 테스트가 지키는 것)
## 개발              (uv run --python 3.10 --with pytest --with olefile pytest, -m live(실제 exec 3개는 구독), Aside 업데이트 뒤 live·VERIFIED_* 갱신, 테스트 수)
```

## 테스트 경계 (기존 합의 seam만 쓴다)

- S1(주): argv → stdout JSON + stderr + 종료 코드, 외부 대역은 가짜 Aside 하나, 반환된 `next`는 셸로 실제 실행, node 변환기·olefile은 실물.
- S2: `research.supervise()`와 runs 인터페이스(result.json·meta.json 상태기계, artifacts 복사, 조건부 갱신).
- 단위 인터페이스: `aside`(녹화·합성 전사 → 스킬 용어), `hwp.extract`(실제 공개 표본).
- 구조 테스트. live(`-m live`): fetch 계열(PR마다) + 실제 exec 3개(0단계·①·⑤, 구독 소모).
- 기대값의 출처: ①의 최종 답·상태는 M18 타임라인을 본뜬 리플레이 명세. ③의 텍스트는 같은 문서의 **다른 렌더링**(법원·헌재 사이트의 HTML/PDF 판결문 등)에서 고른 본문 중간·끝 문장과 후반 표 셀 리터럴, 순서·중복 없음; `PrvText`는 보조 증거(표 표기가 달라 포함 검사를 필수 oracle로 쓰지 않음); 현재 추출량 숫자를 golden으로 쓰지 않음. ②의 바이트는 가짜 Aside가 쓴 원본 파일.
- 대역이 가리는 것: 실제 `aside exec`가 턴 중에 종료하는 원인(M18)은 재현 못 함 — 수정은 원인과 무관하게 전사의 `finished` 기준. 가짜 Aside는 JS를 실행하지 않으므로 스니펫을 거치는 HWP 경로(`looksBinary`·확장자)는 live로만 증명된다. 실제 artifacts 배치·이름 규칙은 live search와 녹화로만.

## 단계와 완료 판정

각 단계 시작 시 `TaskCreate`에 완료 판정을 그대로 적고 끝날 때 `TaskUpdate`. 브랜치는 `main`에서, 커밋·PR 제목 `<타입>: <한국어 제목>`, PR 본문 `## 무엇을 바꿨나`/`## 왜`/`## 영향`/`## 검증`(실행한 명령과 수치). 코드 단계는 `coding` 스킬을 연다. 구조와 행동은 커밋을 나눈다(구조 먼저). 각 PR은 실제 진입점 실행 → codex(gpt-6-astra high, 읽기 전용) 리뷰(①·②·④는 공유 계약 변경이라 녹색 직후, 머지 전) → 선별 반영(기각 이유는 PR 본문) → `gh pr merge --squash` → graphify 그래프 갱신을 main에 `chore: 그래프 갱신`으로 직접 커밋. `.claude/settings.json`·`.agents`·`.codex`는 커밋하지 않는다.

0. **준비** — 계획 파일 이름이 아직 하네스 이름이면 `261009_ultra-search 스킬 개선 계획.md`로 바꾸고 하네스 경로는 그 파일로의 심볼릭 링크(커밋 안 함, ⑤에서 정리). `aside --update` → `aside --version`·`doctor` 기록 → 기준선 `uv run --python 3.10 --with pytest pytest -q` → `-m live` 전체(실제 exec 3개 구독 소모). 실패하면 형식 변화/환경으로 가르고, 형식 변화면 ① 앞에 `fix/` PR로 aside/를 고친다.
   완료 판정: 새 CLI·데몬 버전 기록, 기준선 `410 passed, 14 skipped`, live 14개 통과(또는 실패 원인과 고칠 PR 기록).
1. **① `fix/turn-completion`** — `fix: 턴이 끝나기 전에 런을 확정하지 않게`. 구조 커밋(필요하면): 턴 끝 경계·이 턴 자식만의 활동을 `evidence`로(행동 동일, 녹색). 행동 커밋, 빨강 먼저:
   - S2 `supervise()`: 리플레이(부모 `started` → 자식 둘 spawn과 **자식 전사 작성** → `subagent_wait` → `{"__after_exit__": N}`(N > 주입한 settle) → 자식 `finished`·완료 system-message → `final-started` → 최종 답 → `finished`). 수정 전 `completed_with_orphans`·답 `""`(실패 이유가 "최종 답 누락"인지 확인), 수정 후 `completed`·최종 답.
   - S1: 같은 리플레이로 `search` → `next` → 결과(간격은 기본 settle 10초를 넘는 12초).
   - 마무리 F: `finished` 뒤 프로세스가 살아 있고 마지막 답이 정상 → 감독자가 끝내고 `completed`(종료 코드 무시); 같은 상황에서 마지막 stop이 `error` → `failed`; `finished`를 쓴 뒤 코드 1로 자연 종료(가짜 `fail` 시나리오) → `failed`; 코드 0으로 먼저 종료 → 오류 답 → `finished`(자식 없음) → `failed`.
   - W3·W4 경계: 코드 0으로 일찍 끝나고 세션이 settle보다 늦게(발견 기한 안에) 나타나는 런 → stdout으로 확정하지 않고 세션에서 결과를 읽는다.
   - 기존 테스트 이관(빨강이 아니라 새 규칙에 맞춘 기대값 변경, PR 본문 대조표에): `test_run_directory.py:402` `cut_off_mid_tool`(lifecycle 형식에서 `started`만 남기고 종료) → 작은 IDLE_LIMIT을 주입해 `abandoned`·잘못된 답 미반환을 단언; `test_research.py:980` 잘린 마지막 줄 fixture → 완료된 lifecycle(`finished`) 뒤에 잘린 줄을 붙여 원래 목적(찢어진 줄 파싱)을 유지. 녹색을 지키려고 `finished` 없는 lifecycle 턴을 일찍 완료시키지 않는다.
   - W6(IDLE_LIMIT 작게 주입): 프로세스 생존 중 조용한 턴 → `abandoned` + 부분 result.json; 코드 0 종료 뒤 관측·감싸임·미완료로 조용한 턴 → 같음; 이전 턴 자식만 쓰는 재개 런 → 연장되지 않음.
   - 끝 경계: `finished` 뒤 다음 턴 `started`·답이 붙은 전사 → 이 런은 자기 턴의 답으로 끝남.
   - W4·W5·W1·W3(옛 형식, 늦은 재개 턴 → `completed_unstructured`, `failed`, 세션 미발견)과 자식 settle은 기존 테스트가 녹색으로 지킨다.
   - 0단계 live 결과로 `VERIFIED_VERSION`·`VERIFIED_DAEMON_VERSION` 갱신을 포함.
   완료 판정: 새 테스트가 수정 전 실패·수정 후 통과, 전체 녹색, live 실제 search 통과, codex 리뷰 처리.
2. **② `fix/agent-artifacts`** — `fix: 에이전트가 저장한 원본 파일을 결과에`. 빨강 먼저: 가짜 Aside가 부모·자식 세션 `artifacts/`(하위 폴더, 공백·괄호·한글 이름, 같은 이름의 부모·자식 파일, 심볼릭 링크 하나)에 파일을 쓰고 답이 상대·절대 참조로 가리킴. aside 인터페이스 테스트(`session_artifacts`가 링크·폴더 밖 경로 제외, `rewrite_artifact_refs`). S1/S2: `artifacts` 경로가 존재·바이트 동일, 부모·자식 동명 파일이 각자의 복사본을 가리킴, 재개 런은 이 턴 파일 + 답이 참조한 이전 파일만, 다음 턴이 고쳐 쓴 동명 파일 → 가져오지 않고 `artifacts_missing`, 복사 중 바뀌는 파일 → 재시도 후 `artifacts_missing`, 읽을 수 없는 파일 하나 → `artifacts_missing`과 함께 답·출처 보존.
   완료 판정: 빨강→초록, 전체 녹색, 실제 진입점(심볼릭 링크 경로, 무관한 디렉터리)에서 가짜 Aside로 `search`→`next`→`result` 후 artifacts 경로를 Read로 열 수 있음, codex 리뷰 처리.
3. **③ `feat/hwp`** — `feat: fetch가 HWP·HWPX를 읽는다`. 구조 커밋: `hwp/` 골격(`extract`가 `None`인 스텁)·구조 테스트(KINDS·import·한컴 표지). 행동 커밋(테스트 먼저): 공개 표본 3개(scourt HWP, ccourt HWP, mss.go.kr HWPX — 전체를 읽어 개인 정보 없음 확인 후 `tests/fixtures/docs/`)로 `test_hwp.py`: 다른 렌더링에서 고른 중간·끝 문장·후반 표 셀 포함, `사건 2018헌바130`처럼 탭·빈칸이 경계를 지킴, 표 행 한 줄·중복 없음; 미리보기만 반환하는 변형·첫 Section만 읽는 변형이 실패함을 확인; 암호·배포용 플래그를 바이트 패치한 사본 → 각각 `unsupported`; 잘린 사본 → `unsupported`(예외 아님); HWP 아닌 OLE·ZIP → `None`. S1: 가짜 라우트로 hwp·hwpx(라우트 `ext`를 `bin`·`zip`으로 줘서 내용 판별을 증명) → `ok`, `original_path` 확장자 `.hwp`/`.hwpx`; 정상 문서와 손상 문서를 함께 fetch해 정상 항목이 살아남음. live: 실제 HWP(`application/x-hwp`, `application/x-msdownload`)·HWPX URL fetch.
   완료 판정: 구조 커밋 후 녹색, 행동 커밋 빨강→초록, 전체 녹색(`--with olefile`), live fetch 계열 통과, PEP 723 의존성으로 `uv run cli.py fetch <hwp URL>`이 새 환경에서 동작.
4. **④ `feat/result-wait`** — `feat: 대기를 result --wait 하나로 줄임`(본문에 BREAKING: stop·status·--timeout·log --follow 제거). 테스트 먼저(S1): `slow`에서 `search --wait 0.5`의 `next`가 `result … --wait 570`·백그라운드, 그 `next`를 셸로 실행하면 stderr 진행 줄 + 완료 결과(종료 0), 짧은 `--wait`에 아직 도는 런은 `next`를 다시 주고 종료 0, 그룹의 `실패+진행 중`(4+next)·`비어 끝남+진행 중`(0+next)·`모두 비어 끝남`(5), 죽은 감독자 → `abandoned`, `starting`에서 시작 못 한 감독자 → `abandoned`, 그 뒤 늦게 깨어난 감독자 → `aside exec`를 띄우지 않음(가짜 Aside `calls.jsonl`에 exec 없음), 감독자가 결과를 쓰고 메타 전에 죽음 → 결과의 상태·`orphan_children`·부분 결과 안내까지 복구, 감독자가 끝나는 순간의 생존 확인이 완료를 덮어쓰지 않음(`test_run_directory.py:377` 이전), `--timeout` 테스트(`test_run_directory.py:195`)는 ①의 W6 테스트로 대체됨을 대조표에, 제거된 명령·플래그 → 종료 2. 옛 단언 대조표(PR 본문). `result --wait`를 일부러 망가뜨려(끝나기 전 반환) 새 테스트 실패 확인 후 되돌림. 위 "같은 PR에서 고칠 호출자·문구" 전부. `--help`의 Exit 줄·`NEXT_HELP`를 실행해 의미 단위가 한 줄인지 확인.
   완료 판정: 전체 녹색, `--help`에 명령 12개, 변형 확인, 실제 진입점에서 `search`→`next`→결과, main의 SKILL.md·README에 `status`·`stop` 지시 없음, live 통과, codex 리뷰 처리.
5. **⑤ `docs/skill-text-v2`** — `docs: 스킬 본문과 README를 v2 계약에 맞게 갱신`. SKILL.md 대조 실험 → 본문 확정, README, 이 계획 파일 커밋(하네스 심볼릭 링크 삭제), 행동 검증, 최종 리뷰, 전문 승인, live 실제 exec 3개.
   완료 판정: 아래 "검증" 전부.
6. **⑥ 릴리스** — `__version__`·버전 테스트 `2.0.0`, `git tag v2.0.0` 푸시 + `gh release create v2.0.0`(한국어 노트: 바뀐 것(결함 3개, HWP·HWPX, 명령 축소와 대기 흐름) / 없어진 것과 대신 쓸 것 / 검증한 것과 안 한 것 / 전제(uv·Node·Aside, aside --update)).
   완료 판정: `gh release view v2.0.0` 성공, 로컬·원격 main 일치, `git status`에 의도한 미추적 파일만.

## 검증 (스킬 완료 조건)

- `uv run --python 3.10 --with pytest --with olefile pytest -q` 녹색, `-m live` 전체 통과(Aside 실행 중, 새 CLI).
- 행동 검증: 격리 디렉터리에서 `claude -p --output-format json`(도구 Bash·Read·WebSearch·WebFetch, 설치된 스킬, 가짜 Aside는 `ULTRA_SEARCH_ASIDE_BIN`·`ULTRA_SEARCH_ASIDE_HOME`·`FAKE_ASIDE_SCENARIO`). T1 알려진 URL → `fetch`만 · T2 출처 선택 질문 → 목표·출처 제약·증거를 담은 `search`(대조 실험과 겸함) · T3 `slow` → `next`(`result --wait`)로 결과까지, 감시 종료를 완료로 보고하지 않음, `claude -p`에선 포그라운드 · T4 챌린지 fetch → 그 출처를 읽은 것으로 인용하지 않음 · T5 Aside 불가 → `doctor` 보고, WebSearch/WebFetch 안 씀 · T6 답이 저장 파일을 가리키는 search → 그 파일 내용을 묻자 `artifacts` 경로를 연다. `permission_denials`로 실패한 실행은 입력을 보충해 재실행.
- `claude plugin validate --strict /Users/seongjin/Coding/Ultra-Search/.claude/skills` 종료 0.
- 프로젝트에서 `claude -p "/skill-doctor"`로 트리거가 겹치는 이웃 스킬 확인(codex·coding과 경계).
- 최종 SKILL.md·`--help`를 codex(gpt-6-astra high)가 skill-maker의 네 성질로 리뷰, 선별 반영.
- 성진이 SKILL.md 전문 승인.
- 개발 기록(이 계획, 실측, 기각한 대안, codex 리뷰 처리)은 커밋·PR 본문·이 파일에 두고 스킬에는 넣지 않는다.

## 재사용할 기존 자산

- `tests/fake_aside/aside`의 리플레이 지시(`__sleep__`·`__after_exit__`·`__if_prompt__`), `fetch_batch` 문서 라우트, `FAKE_ASIDE_CALLS`, `tests/fixtures/runs/261002-lifecycle-subagent`(실제 lifecycle 녹화).
- `evidence.has_terminal_answer`·`turn_of`·`turn_start_index`·`_framed`·`child_is_terminal`, `aside.turn_finished`·`last_activity`, `supervisor._activity`·`_finish`·`_sync`, `research.commands._run_entry`·`_envelope`·`next_step`·`_await_and_report`, `follow._drain`, `runs._meta_lock`·`atomic_write_json`·`Run`, `fetch.classify.extract_document`·`count_words`·`_first_heading`, `acquire._save`, 스크래치 `hwp/hwp5.py`의 레코드 해석(제어문자·디코딩을 고쳐 옮김).

## 기각한 대안 (기록)

- 코드 전면 재작성: 결함은 구현 품질이 아니라 계약에 있고, 실측으로 다진 경계 처리(M15)를 잃는다.
- 인용 자동 대조: 얼마나 확인할지를 스킬이 정하는 셈(성진 원칙), 응답이 복잡해진다.
- `find` 명령(DuckDuckGo): 새 선택지가 search/fetch와 헷갈린다. DuckDuckGo 결과 페이지는 기존 `fetch`로도 받을 수 있다.
- Aside 사이트 API 노출: search 에이전트가 이미 안에서 쓴다. 새 표면.
- 상태를 사용자 단위로: default 권한 모드에서 Read 거부(M17), 이행 비용 대비 이득이 작다.
- `--help` 길이 목표·파이프 금지 문장: 실측상 동작 문제 없음(M4, M20).
- `aside.sessions` REPL API로 전사 읽기: CLI 세션을 모른다(M14).
- 스니펫의 MIME→확장자 목록에 HWP 추가: MIME이 제각각(`x-msdownload`)이고 가짜 Aside가 JS를 실행하지 않아 시험으로 증명되지 않는다 → Python에서 내용으로 판별한 결과로 확장자를 정한다(codex #9).
- `PrvText` 포함 검사를 필수 oracle로: 표 표기가 달라 정상 구현을 거부하고 미리보기만 반환하는 구현을 통과시킨다(codex #8).

## codex 계획 리뷰 처리 (gpt-6-astra high, 1차 13건: MAJOR 10·MINOR 3, 기각 0)

1 무활동 상한을 프로세스 생존과 무관하게, `finished`면 프로세스가 살아 있어도 확정 → ① 상태표 · 2 `starting`·생존 확인 경쟁·결과 채택 → ④ 감독자 생존 · 3 턴 끝 경계·새 marker 지연·이 턴 자식만 → ① · 4 재개 런의 참조 파일 수거 → ② 수거 대상 · 5 세션별 치환 후 합침·하위 경로·이름 → ② · 6 복사 실패가 결과를 잃지 않음·링크·특수 파일·스트리밍 → ② · 7 탭·빈칸·하이픈·UTF-16 → ③ hwp5 · 8 PrvText는 보조, 다른 렌더링 리터럴·변형 실패 → 테스트 경계·③ · 9 확장자는 Python 판별로, JS 경로는 live로 → ③·기각 대안 · 10 암호·손상은 `unsupported`, 예외 금지, 혼합 fetch → ③ · 11 빨강 시험의 간격·자식 전사 → ① · 12 호출자·문구·정리 fixture·종료 우선순위·SKILL.md 최소 수정을 ④에 → ④ · 13 M3·M4·M8·M18 정정 → 실측 표.

2차(같은 스레드): 1차 13건 중 RESOLVED 10·PARTIAL 3, 새 지적 6건(MAJOR, 기각 0). A 상태표 우선순위가 코드 0 종료 뒤 무활동 종료를 가림 → ① 표를 W1–W7로 다시 써 무활동(W6)을 "계속 감시"(W7)보다 앞에 · B 끝남 관측과 성공 판정 분리, 감독자가 끝낸 종료 코드 무시, 마무리 F에서 자연 종료·`error` stop으로 판정 → ① 마무리 F · C 형식은 관측된 이 턴으로만 판정, 미관측은 기존 규칙(W4)과 기존 테스트 유지 → ① 용어·W4 · D 늦게 깨어난 감독자 → 띄우기 전 잠금 안에서 `starting` 확인·pid 기록 → ①·④ · E 결과 채택 시 고아 목록 등 메타 복구 → ④ · F 다음 턴이 고친 파일·복사 중 변경 → ② 수거 대상·복사.

3차(같은 스레드): C–F와 이전 2·3 RESOLVED, A·B·이전 1 PARTIAL, 새 지적 3건(MAJOR 2·MINOR 1, 기각 0). W4가 세션 미발견까지 덮어 발견 기한을 우회 → W4에 "세션은 발견됐고" 조건 · 마무리 F의 조기 완료 분기가 `error` stop을 안 봄 → F를 단일 판정 규칙으로 · 기존 테스트 2개(`cut_off_mid_tool`, 잘린 마지막 줄)의 이관 → ① 단계 테스트 목록.

4차(같은 스레드, 좁은 확인): 3차 1–3·A·B·이전 1 모두 RESOLVED, 새 결함 없음. 판정 "이 계획으로 구현을 시작해도 됩니다". codex 스레드 `01a11c80-69fb-7bd2-801a-caccce9d0f2e`(런 `20261009-021220-plan-review-v2-734f` 외 3회).

## 위험과 미확정

- M18의 근본 원인(왜 `aside exec`가 턴 중에 0으로 끝나는지)은 재현 못 했다. CLI 업데이트로 사라질 수도 있다. 수정은 원인과 무관하게 전사의 `finished`를 기준으로 한다.
- IDLE_LIMIT 600초는 관측(부모 침묵 74초, 자식은 그동안 기록)에서 넉넉히 잡은 값이다. 자식까지 10분 넘게 조용한 정상 조사는 `abandoned`로 끊긴다(`성진:` 주석). 데몬 쪽 일은 계속될 수 있고 그 사실은 상태 뜻에 이미 있다.
- 공개 레포에 넣을 HWP 표본은 공개 판결문·서식이지만 전체를 읽어 개인 정보가 없음을 확인한 뒤 넣는다. 확인이 안 되면 HWPX는 테스트 안에서 합성하고 HWP는 live로만 검증한다.
- 바이너리 HWP 파서는 문단 텍스트만 뽑는다(표는 셀 문단 나열, 그림·각주 위치 미보존). 원본은 `original_path`에 남는다.
- live 실제 exec 3개는 실행마다 구독을 쓴다(0단계·①·⑤).
- 전역 설치본이 대조 실험의 변형 본문을 가릴 수 있다 — 전사로 로드된 본문을 확인한다.
