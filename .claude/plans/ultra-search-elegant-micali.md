# `follow`를 감독자 뷰로 — `log --level progress`

## 목적과 요약

한 문장: 클로드가 리서치를 Aside 워커에게 맡기고 자기 일을 하다가 `follow`가 깨울 때, 워커가 **무엇에 손을 뻗었고 무엇을 말했는지**만 받고 **어떻게 요청했는지**(도구 인자·로컬 경로·바이트 크기)는 받지 않게 한다.

합의된 결과: `log --level`의 값을 `progress`(새 기본값)·`steps`(지금의 `compact`)·`full`(지금의 `normal`)·`raw`로 교체한다. `next.command`는 `--level`을 지정하지 않으므로 기본값이 바뀌면 `follow` 경로 전체가 따라온다. SKILL.md에는 이 뷰가 무엇을 보여주고 나머지가 어디 있는지 한 절만 들어간다. 나머지는 `--help`의 `choices=`와 help 문구가 가르친다(interface over document).

## 확인된 현재 상태와 근거

- **사실.** `follow`가 넘기는 것은 `_events.render(level="compact")`의 출력이다. compact는 도구 호출마다 `call name(인자 200자)`, 결과마다 `name out=NB`, 어시스턴트 텍스트 400자를 낸다. `.claude/skills/ultra-search/scripts/_events.py:357-394`, `_follow.py:70-85`.
- **사실.** `search`는 기본 100초를 인라인으로 기다린다(`_run_cmds.py:145`). 그보다 긴 런만 `next.command`(`log --run <id> --follow`, 레벨 미지정)로 넘어간다(`_run_cmds.py:168-181`). 따라서 `follow`가 쓰이는 런은 서브에이전트가 붙는 긴 런뿐이다.
- **사실(실측, 2026-09-04, `.ultra-search/runs/` 2026-08-29 기록 6개).** 문자 수 기준.

| 런 | 트랜스크립트 | compact | normal | 감독자 뷰 시뮬레이션 |
|---|---|---|---|---|
| 단순 검색 4건 평균 | 64K | 981 | 6.4K | 253 |
| 서브에이전트 3개 런 | 400K | 10,088 | 82,041 | 1,837 |

- **사실.** 서브에이전트 런 compact 10,088자의 내역: 도구 호출 인자 4,990(49%), 결과 크기 줄 1,640(16%), 워커 서술·답변 1,921(19%), 프롬프트 869, `system-message`가 raw JSON으로 떨어진 것 653.
- **사실.** Aside는 서브에이전트 완료를 `{"role":"system-message","content":"Subagent X is done (status: idle, 1/3 completed)\n<result>..."}`로 남긴다(데몬 1.26.829 기록). `parse_record`는 이 role을 모르므로 `raw[9]: {...}` 200자 JSON으로 렌더한다(`_events.py:132`, `:366`).
- **사실.** 한 이벤트에 도구 호출이 여럿이면 `_render_assistant`가 `\n`으로 잇고 `_drain`은 첫 줄에만 `[child …]` 접두사를 붙인다(`_follow.py:79-84`). 자식의 두 번째 호출부터 부모 것처럼 읽힌다.
- **사실.** 레벨 이름을 참조하는 곳: `ultra_search.py:30`(`LEVEL_CHOICES`)·`:160-165`(`--level`)·`:210`(`show --item` help), `_watch_cmds.py:213`(`show --item` 오류 fix 문구), `_follow.py:92`(기본값), `tests/test_follow.py` 13곳, `tests/test_events.py:148,162`. README와 harness-spec은 레벨 이름을 쓰지 않는다.
- **사실.** `pytest tests/` 184 통과·14 skip(live), 61초. `tests/fixtures/sessions/2026-08-29_UnknownShape0001`의 미지 role은 `telemetry`·`user-message-metadata`이므로 `system-message`를 인식해도 "미지 role은 raw로 남긴다" 테스트는 깨지지 않는다.
- **추론.** 토큰으로는 compact 10,088자가 한국어·JSON 경로 혼합이라 대략 3,500~5,000, 감독자 뷰 1,837자가 600~900이다. 토크나이저로 재지 않은 추정치다.
- **결정(성진, 2026-09-04).** `follow` 출력의 독자는 클로드뿐이다. 사람이 터미널에서 보는 용도는 설계에 넣지 않는다.
- **결정(성진, 2026-09-04).** 레벨 사다리는 **교체**한다: `progress`·`steps`·`full`·`raw`. 지금의 `full`(200KB 클립)은 `raw`와 구분이 없어 없앤다.

## 성공 기준

- 서브에이전트 3개 기록 런을 `log --run 260829-235523-subagents`(레벨 미지정)로 렌더했을 때 출력에 `call `·`out=`·`/Users/`·`"offset"`이 없고, `subagent×3[…]`·`Subagent … done`·각 자식의 `answer:` 첫 줄·`# cursor=`가 있다.
- 같은 런의 `--level steps` 출력이 이 변경 전 `--level compact` 출력과 바이트 단위로 같다(회귀 없음의 정의).
- `--level full`이 변경 전 `normal`과 같고, `raw`는 그대로다.
- `_drain`이 낸 모든 줄에 그 스트림의 접두사가 붙는다(자식 이벤트의 두 번째 줄 포함).
- `search`가 100초를 넘겨 돌려준 `next.command`를 그대로 실행하면 progress 뷰로 끝까지 따라가고 `run.<state>` 줄에서 exit한다(기존 `test_a_background_search_hands_back_the_command_that_will_wake_you`가 그대로 통과).
- `pytest tests/` 전부 통과, `validate_harness.py --path .` 결과가 지금과 같다(기존 graphify 훅 오탐 2건 외 0).
- 실패 조건: progress 뷰가 오류(`is_error`)나 서브에이전트 완료를 삼키면 실패다. "적게 보여주기"가 아니라 "다음 행동을 바꾸는 것만 보여주기"가 기준이다.

## 범위·비범위·제약

**범위.** `_events.py`(레벨 상수, `system-message` 인식, progress 렌더러), `_follow.py`(기본값, 접두사), `ultra_search.py`(`LEVEL_CHOICES`, `--level` help, `show --item` help), `_watch_cmds.py`(fix 문구), SKILL.md 한 절, `tests/test_follow.py`·`tests/test_events.py`, `.claude/harness-spec.md`(결정 10 + change history), `graphify update .`.

**비범위.** `next.command`의 형태(레벨 미지정이 곧 기본값 추종이므로 손대지 않는다). `--heartbeat`(백그라운드 Bash는 exit 시 출력을 한꺼번에 받으므로 하트비트 줄은 순수 소음이며 지금도 `next.command`에 없다). 부모·자식 스트림을 타임스탬프로 교차 정렬하는 것(팔로우 중에는 폴링이 자연히 교차시키고, 사후 렌더의 순서는 감독 결정에 영향이 없다). `validate_harness.py`가 graphify 훅 명령을 "없는 스크립트"로 잡는 오탐 2건. README(레벨 이름을 쓰지 않는다).

**제약.** 표준 라이브러리만. 모듈 400줄 이하(`_events.py`는 399줄이라 progress 렌더러를 넣으면 넘는다 — 렌더링 절 `_events.py:352-399`를 `_render.py`로 옮기는 것이 spec의 "책임 하나·400줄 이하" 원칙을 지키는 최소 이동이며, `_events.render`를 부르는 곳은 `_follow.py:76`과 테스트 두 줄뿐이다). `--help`가 인터페이스이므로 help 문구가 실제 동작과 어긋나면 안 된다(spec change history의 "help 과장 6건" 전례). 하드랩 금지.

## 핵심 결정과 근거

1. **분류 기준은 도구 이름 목록이 아니라 "감독자의 다음 행동을 바꾸는가"다.** 감독자의 다음 행동은 넷뿐이다: 계속 기다린다·`result`로 수거한다·정체를 의심해 `status`를 본다·Aside 앱에서 취소한다. 이 넷 중 하나를 바꾸는 정보만 줄이 된다. 그래서 워커의 서술(의도), 서브에이전트 생성·완료, 오류, 최종 답의 도착, 외부를 가리키는 대상(호스트·검색 목표·서브에이전트 설명)은 남고, 로컬 경로·오프셋·바이트 크기·성공한 결과의 존재는 떨어진다. 새 도구나 새 role이 와도 같은 물음으로 처리된다. 이 원칙을 `_render.py` 모듈 docstring에 적는다 — 다음 사람이 규칙을 늘리지 않고 재도출하게.
2. **호출 줄은 "무엇에 손을 뻗었나"만.** 이벤트 하나가 한 줄: `webfetch×4[nodejs.org] websearch×1[Go 1.27 release status]`. 대상은 인자 중 외부를 가리키는 하나(`url`→호스트, `objective`, `description`, `title`)이고 없으면 이름과 횟수만(`read_file×5`, `bash×1`). 키 선호 목록은 Aside 도구 스키마에 묶인 사실이므로 목록으로 두되, 목록에 없는 도구는 이름·횟수로 떨어진다는 규칙을 같이 적는다.
3. **결과는 오류일 때만 줄이 된다.** `out=NB`는 감독자의 행동을 바꾸지 않는다(그걸 보고 `show --item`으로 가는 건 `steps`의 일이다). `is_error`면 `name ERROR: 내용 120자`.
4. **최종 답은 첫 줄과 크기만.** `answer: <첫 줄 160자> …(+N)`. 본문은 `result`가 인용을 URL로 풀어 가져오므로 여기서 400자를 다시 싣는 건 같은 것을 두 번 내는 것이다. 중간 서술은 `says: <첫 줄>`로 구분한다 — 답인지 진행 보고인지가 "수거하러 갈까"를 가른다.
5. **`system-message`를 이벤트 종류로 인식한다.** kind `system`, `text=content`. progress는 `system: <첫 줄 100자>`, steps 이상은 지금처럼 raw JSON이 아니라 텍스트 클립. "모르는 레코드는 raw로 남긴다" 원칙은 그대로다 — 아는 레코드가 하나 늘었을 뿐이다.
6. **프롬프트는 첫 줄 120자.** 부모 프롬프트는 감독자가 쓴 것이고, 자식 프롬프트는 `subagent×3[설명]` 줄이 이미 이름을 댔다. 그래도 한 줄은 남긴다 — `resume`으로 외부 세션을 이어받을 때 그 세션이 무엇이었는지가 여기서만 보인다.
7. **접두사는 줄마다.** `_drain`에서 `rendered.splitlines()`마다 prefix를 붙인다. progress는 이벤트당 한 줄이라 우연히 피해가지만 steps·full은 아니고, 버그는 공유 함수 한 곳에서 고친다.
8. **이름 교체, 값은 넷 그대로.** `progress`·`steps`·`full`·`raw`. 이름이 곧 용도이고 `choices=`가 곧 문서다. 지금의 `full`(200KB)은 버린다. 버린 안: 다섯 값으로 늘리기(`compact`가 가장 압축된 뷰가 아니게 되어 이름이 거짓말을 한다), `compact`의 출력만 바꾸기(워커가 왜 그 출처를 골랐는지 되짚을 때 인자가 보이는 뷰가 사라진다).
9. **SKILL.md는 한 절.** "Collecting work you started" 절에 붙인다: `log`가 기본으로 보여주는 것은 워커가 무엇에 손을 뻗었고 무엇을 말했는지이지 어떻게 요청했는지가 아니다; 어느 페이지를 어떤 인자로 열었는지는 `--level steps`, 결과 본문은 `result`와 `show`. 왜: 감독의 목적이 컨텍스트 절약인데 추적 채널이 그 절약분을 도로 먹으면 위임할 이유가 없다. 레벨 목록·기본값·각 레벨의 정의는 쓰지 않는다 — `--help`가 낸다.

## 인터페이스·산출물

`log --level` help 문구(초안, 구현 시 실제 동작에 맞춘다):

```
--level {progress,steps,full,raw}
  What each event becomes. progress: one line per turn -- what the run reached for (tool, count,
  the host or objective) and what it said; results appear only when they errored. steps: every
  call with its arguments and every result's size, for retracing why a source was chosen. full:
  steps plus the first 2000 bytes of each result. raw: the stored records unchanged. Default progress.
```

progress 줄 문법(한 이벤트 한 줄, 접두사는 `_drain`이 붙인다):

```
prompt: <첫 줄 120자>
<tool>×<n>[<대상들, 80자>] <tool>×<n> | says: <첫 줄 160자> …(+N)
answer: <첫 줄 160자> …(+N)
<tool> ERROR: <내용 120자>
system: <첫 줄 100자>
raw: <내용 100자>
```

`show --item` help와 `_watch_cmds.py:213` fix 문구: `log --level normal` → `log --level steps`.

harness-spec 결정 10(초안): "**`log`의 기본 뷰는 감독자 것이다.** 실측(2026-09-04): 서브에이전트 런의 compact 출력 10,088자 중 감독자의 다음 행동을 바꾸는 줄은 19%였고, `follow`가 쓰이는 런은 100초를 넘긴 것뿐이라 그 케이스가 전부다. 기준은 도구 목록이 아니라 '다음 행동(기다린다·수거한다·정체 의심·앱에서 취소)을 바꾸는가'. 인자·경로·크기가 필요한 건 워커를 되짚는 개발자이고 그건 `steps`다."

## 단계·의존·완료 판정

각 단계는 앞 단계의 산출물을 쓴다. 파일을 바꾸는 단계가 3개 이상이므로 구현 세션은 `TaskCreate`로 트래커를 열고 아래 판정 기준을 description에 그대로 적는다.

1. **테스트 seam 합의와 실패 테스트(tdd 스킬로 시작).** seam은 기존과 같다: `_follow.follow(out=…)`의 출력 문자열(`tests/test_follow.py`)과 `_events.render`(`tests/test_events.py`). 추가할 테스트 — progress가 인자·경로·크기를 내지 않는다(서브에이전트 기록 런을 fixture로 복사: `.ultra-search/runs/260829-235523-subagents/session/`, 400KB이므로 부모 `messages.jsonl`과 자식 하나만), progress가 오류 결과와 `system-message`를 낸다, `steps`가 옛 compact와 같다(옛 출력을 golden으로 고정), 접두사가 모든 줄에 붙는다, 기본 레벨이 progress다(`log` CLI 경유). 판정: 새 테스트가 지금 코드에서 실패하고 기존 184개는 통과.
2. **렌더링 이동과 progress 구현.** `_events.py:352-399`를 `_render.py`로 옮기고 `_events.render`는 re-export가 아니라 호출처(`_follow.py:76`, 테스트)를 `_render.render`로 바꾼다. `parse_record`에 `system-message` 분기. progress 렌더러는 결정 1~6대로. 판정: 1단계 테스트 통과, 두 모듈 모두 400줄 이하.
3. **CLI와 기본값.** `LEVEL_CHOICES`, `--level` help·default, `show --item` help, `_watch_cmds.py:213`, `_follow.follow` 기본값. 판정: `$US log --help`의 문구가 실제 출력과 일치함을 기록 런 하나로 눈으로 확인, `test_a_background_search_hands_back_the_command_that_will_wake_you` 통과.
4. **SKILL.md 한 절.** 결정 9대로. 판정: 레벨 이름·기본값·정의가 본문에 없고, `validate_harness.py --path .`의 결과가 변경 전과 같다.
5. **spec·그래프·검증.** harness-spec에 결정 10과 change history 항목(실측 수치 포함), `graphify update .`, `pytest tests/`, `validate_harness.py`. 판정: 테스트 전부 통과, 그래프 갱신 커밋에 포함.
6. **PR.** 브랜치 `fix/follow-progress-level`, 제목 `fix: follow 기본 뷰를 감독자용 progress 레벨로 교체`. `## 검증`에 1·5단계의 실제 명령과 수치. 관례대로 codex(`gpt-5.6-sol`, high) 적대적 리뷰를 머지 전에 한 번 돌린다 — 이전 두 패스에서 P1을 각각 6건·3건 잡았다.

## 검증 시나리오

- **기록 런 재렌더.** `python3 .claude/skills/ultra-search/scripts/ultra_search.py log --run 260829-235523-subagents --runs-dir .ultra-search`의 출력이 위 문법만으로 이루어지고 1,837자 안팎이다. 같은 명령에 `--level steps`를 붙이면 변경 전 compact 출력과 `diff`가 비었다.
- **깨우기 경로.** `tests/test_commands.py`의 fake aside로 100초를 넘기는 런을 만들고 `next.command`를 실행해 progress 뷰와 `run.completed` 줄로 exit하는지 본다(기존 테스트가 이 경로를 실행으로 확인한다).
- **오류를 삼키지 않는다.** `is_error=True`인 tool result와 `system-message`를 넣은 트랜스크립트에서 progress가 둘 다 낸다.
- **접두사.** 자식 트랜스크립트에 한 이벤트 세 호출을 넣고 세 줄 모두 `[child …]`로 시작한다.
- **라이브 재측정(선택, 동의 필요).** 실제 `search` 1회로 서브에이전트가 붙는 런을 만들어 progress 출력 크기를 잰다. 비용은 Aside 구독 토큰 약 5만 개와 10~60초. 기록 런이 이미 같은 데몬 버전의 실측이므로 없어도 판정에는 지장이 없다.

## 리스크·가정·비차단 유예

- **가정.** `system-message`의 형태(`content` 문자열, 첫 줄이 "Subagent X is done (…, n/m completed)")는 데몬 1.26.829 기록 하나에서 관찰했다. 반증 시(형태가 바뀌면) `system:` 줄의 내용이 달라질 뿐 파서는 `raw`로 강등하지 않는다 — kind는 role로 정하고 content는 클립만 하므로. 바꿀 조건: `content`가 문자열이 아닌 레코드가 관찰되면 `_as_text`로 감싼다.
- **가정.** 외부를 가리키는 인자 키 선호 목록(`url`·`objective`·`description`·`title`)은 지금 기록에 나온 도구(`websearch`·`webfetch`·`subagent`·`bash`·`read_file`·`write_todos`·`subagent_wait`)로 확인했다. 목록에 없는 도구는 이름·횟수로 떨어지므로 잘못 보여주는 일은 없고 덜 보여줄 뿐이다.
- **리스크.** 인자 없는 호출 줄이 너무 조용해 정체와 구분이 안 될 수 있다는 우려는 `status`의 `possibly_stalled`가 이미 답하는 질문이고, `follow`는 exit로 알린다. progress에 하트비트를 섞지 않는 이유다.
- **비차단 유예.** 라이브 재측정은 성진이 동의하면 6단계 PR의 `## 검증`에 추가한다. 결정 시점: PR 열기 전. 영향: 수치 한 줄.
- **비차단 유예.** `validate_harness.py`가 graphify 훅 명령을 오탐하는 것은 harness-creator 스크립트 쪽 문제이고 이 레포 밖이다. 소유자: 성진. 영향 없음.
- **범위 밖 발견(지우지 않음).** `_events.render`의 `full` 200KB 클립은 이 변경으로 사라지므로 "관련 없는 데드코드"가 아니라 이 변경이 못 쓰게 만드는 코드다 — 같이 치운다.
