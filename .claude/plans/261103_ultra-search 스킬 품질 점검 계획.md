# ultra-search 스킬 품질 점검 계획 (v3.0.0)

## Context

`ultra-search`는 Claude의 웹 층을 네이티브 `WebSearch`/`WebFetch`에서 성진의 로그인된 Aside 브라우저로 바꾸는 전역 스킬이다(`~/.claude/skills/ultra-search` → 이 레포 심볼릭 링크). 목적은 Claude의 답이 실제로 확보한 원문에 근거하게 하는 것이다. 성진은 skill-maker 프레임 반영 여부를 포함해 품질을 다시 점검하고, 필요하면 재작성까지 고려한 구현 계획을 원했다.

계획 세션의 결론: **재작성하지 않는다.** 코드 구조와 트리는 프레임에 부합한다(M1, M28). 문제는 두 가지다.

1. **결과가 사실을 말하지 않는 결함.** 454개 테스트가 녹색인 채, 실제 데이터에서 파서가 레코드를 잃고(M7), HTTP 403을 "열었다"고 하고(M20), 실패 원인을 숨기고(M21), 에이전트가 읽은 문서를 놓치고(M9), EUC-KR을 깨진 채 `ok`로 저장한다(M11). 스킬이 존재하는 이유인 "정직함"을 직접 해친다.
2. **본문이 프레임보다 많이 정한다.** skill-maker가 10/15·10/23 개정된 뒤의 기준으로 보면 본문에 방법을 정하는 줄이 많고, 대조 실험상 행동을 바꾸지 못하는 구간도 있다(M25). 스킬은 기능을 포괄적으로 담고 목적에 중립이어야 한다.

그래서 **인터페이스는 결과가 사실을 말하게 고치고, 본문은 모델이 볼 수 없는 사실과 명령의 비교만 남긴다.** 판단은 모델과 사용자의 몫이다.

## 합의 원장

| 구분 | 내용 | 근거 |
|---|---|---|
| 결정 | **이 작업의 목표.** skill-maker 프레임을 철저히 반영한다: 밀도 높은 원칙 중심으로 문서와 인터페이스를 쓰고, 문서보다 인터페이스를 우선하며, 자동화가 아니라 사용자와 소통하는 동료로 작동한다. 기능은 포괄적으로 담되 특정 상황과 방법론을 상정하지 않는다. 구현 중 판단이 갈리면 이 문장으로 정한다 | 성진 |
| 결정 | 목적: 원문 근거(닿음·충실도·정직함·위임·비용과 행위 의식). 활용 목적은 미리 정하지 않는다. 쓰는 사람은 사실상 성진, 레포는 공개 | 성진 |
| 결정 | 품질의 중심은 정직한 결과. 역량(map·crawl·resume·sessions·show·log)은 사용량 0이어도 유지 | 성진 |
| 결정 | **새 기준.** 인터페이스: 결과가 사실을 말하게 고친다, 판단은 모델이 한다. 본문: 모델이 볼 수 없는 사실과 명령의 비교만. "언제, 얼마나, 어떤 순서로"는 쓰지 않는다. 새 금지·사전 확인·절차 줄을 넣지 않는다 | 성진 |
| 결정 | 실패 시 대안을 일일이 정의하지 않는다(레일) | 성진 |
| 결정 | "Aside가 없으면 대체하지 말고 묻는다"는 행동 줄은 빼고, 그 뒤의 사실을 한 줄로 둔다: WebSearch·WebFetch는 사용자의 접근을 쓰지 못하고 WebFetch는 원문이 아니라 요약을 돌려준다, 성진은 자기 접근으로 얻은 원문을 근거로 삼는다. 실패했을 때 어떻게 할지는 모델이 정한다(skill-maker v0.6.0, M36) | 성진 11/7 |
| 결정 | 대량 수집·병렬 search 사전 확인 줄을 넣지 않는다 | 성진 |
| 결정 | REPL은 이미 포함된 역량이고 제한 줄을 넣지 않는다. 쓰임은 사이트에 직접 들어가 DOM·백엔드 API를 보고 클릭·드래그·스크립트를 적용하는 것이다. 본문 문장을 그렇게 넓힌다. Aside 사이트 스킬(`aside skills`)은 언급하지 않는다 | 성진 |
| 결정 | 스킬은 다른 스킬과 독립적이다. description에 다른 스킬을 언급하지 않는다(10/19 SNS 제외 문구, `(codex)` 제거). description 문안은 아래 그대로 | 성진 |
| 결정 | `search`·`resume`은 항상 즉시 반환, `--wait`·`--background` 제거. 대기는 `result --wait` 하나 | 성진 |
| 결정 | `result --wait`의 진행 줄 제거, 출력은 JSON 하나 | 성진 |
| 결정 | `search`·`resume` 프롬프트 접미사를 "Unless the objective asks for it, do not post, purchase, sign up, or change account settings."로 바꾼다. 조사 중 제멋대로 하는 행동은 막고 사용자의 요청은 막지 않는다 | 성진 |
| 이전 결정 유지 | 상태는 작업 디렉터리 `./.ultra-search/`(skill-maker `data/`에서의 유일한 이탈, 이유는 README·구조 테스트에 있음). SKILL.md·`--help`는 영어, 커밋·PR·README·릴리스 노트는 한국어. references 없음 | 260925·261001·261009 |
| 내 판단 | `crawl --from`은 매니페스트 전체(`--help`의 "crawled as it is"를 참으로 만든다), URL 직접은 25 유지 + 잘린 수 보고. 성진이 이 질문에는 답하지 않아 내가 정했고, 계획 승인 때 뒤집을 수 있다 | M14 |
| 내 판단 | run id는 위치 인자 하나로(`--run` 제거). 모델의 첫 추측이 위치 인자이고(M26), `resume RUN_OR_SESSION`과 같은 모양이다 | M26 |
| 결정 | 모두 끝낸 뒤 GitHub 릴리스까지 한다. 구현 세션은 ⑦의 `gh release create`로 끝난다 | 성진 |
| 내 판단 | 파괴적 변경이 있으므로 v3.0.0(v2.0.0 전례) | 261009 |
| 내 판단 | `next.run_in_background`는 유지한다. 감사는 상수라며 제거를 권했지만, 대화 세션(가장 흔한 맥락)에서 포그라운드로 최대 9.5분 막히는 위험이 더 크다. 필드는 기본 권장, 턴과 함께 끝나는 맥락의 예외는 응답 `note`가 말한다 | 계획 리뷰 #16 |
| 내 판단 | fork_self 부모 선택은 이번에 고치지 않는다. 10월 이후 런에서 0건이고 부모를 가를 관측 기준이 불확실해 합성 시험이 규칙을 베끼게 된다. `성진:` 주석으로 남긴다. 마커 경계만 고친다 | M24, 계획 리뷰 #9 |
| 결정 | `repl-api`를 없앤다(명령 12→11). 데몬의 설명을 넘기기만 하는 명령이고 Aside가 직접 `aside guide repl`을 준다(Model over machinery, M37). REPL 역량은 그대로다 | 성진 11/7 |
| 결정 | `cited_not_opened` 필드를 만들지 않는다. 결과의 `opened_sources`를 보면 드러나는 일이라 본문의 사실 한 줄로 충분하다(Model over machinery, M25 T7·T7b 8/8) | 성진 11/7 |
| 결정 | skill-maker v0.6.0(11/6)을 기준으로 삼는다: 여섯 성질, 처방 줄은 사실만 줘도 틀리는 것이 관찰된 경우에만, 명령은 Model over machinery를 통과해야 한다 | 성진 11/7 |

## 실측 원장 (2026-11-03, v2.0.0 기준)

| # | 사실 | 근거 |
|---|---|---|
| M1 | 기준선 `454 passed, 18 skipped`(405초). 아래 결함을 하나도 못 잡는다. `claude plugin validate --strict` 통과. 세션 디렉터리 12,400개 앞에서도 `find_session_by_marker` 0.18초라 비용 문제 없음 | 실행 |
| M2 | `doctor` 전부 ok, 그러나 데몬 1.26.1101.2244 ≠ 검증 기준 1.26.1008.1938(CLI는 1008). ok인 점검에 `fix`가 붙어 항상 뜬다 | 실행 |
| M3 | v2 이후 Claude 전사 20세션 107회: search 35·fetch 35·result 34(`--help` 포함, search·fetch 각 약 13회), resume·sessions·log·show·map·crawl·`--sources` 0회. 실제 작업 세션의 네이티브 웹 도구 0회. 22세션 중 20세션이 `Skill`로 로드 | 전사 집계 |
| M4 | 파이프 45회, 복합 명령 56회, `cd` 27회, `--runs-dir` 34회+(대부분 스크래치패드). 권한 모드 auto라 막히지 않는다 | 전사 |
| M5 | 런 71개 소요 시간 ≤100초 14%(대부분 초기 시험), p50 364초, p90 752초. 실제 search 22회 중 기본 대기 안에 끝난 것 최대 1회, 11회는 모델이 `--background` 선택 | `meta.json`, 전사 |
| M6 | 백그라운드 `result --wait` 출력 파일에 stderr 진행 줄과 stdout JSON이 섞여 `json.load`가 9회(6세션) 실패 | 전사 |
| M7 | **파서가 레코드를 잃는다.** `str.splitlines()`가 U+0085·U+2028·U+2029에서 JSON 줄을 자른다. 런 `261103-143546`: 레코드 43 → 이벤트 67(raw 27), 답이 인용한 PDF(thevc.kr)의 webfetch가 사라져 `opened:false`, `show --item` 번호도 밀림. 스킬 세션 104개 중 11개(10.6%), 레코드 18개, 소실 source 121개. 한글 파일명 모지바케가 U+0085를 만든다 | 재현, Sonnet 전수 |
| M8 | 같은 문자를 담은 페이지는 `fetch`에서 `no response`, 변환기에서 `no output`이 된다(REPL이 그대로 출력함을 확인). 공개 페이지 표본 44개 중 해당 0개라 드물다 | `aside repl`, 표본 |
| M9 | **에이전트가 받은 문서를 못 챙긴다.** 10/16 이후 세션 `tmp/` 파일 902개 vs `artifacts/` 1개. webfetch는 문서를 `tmp/<이름>`에 받고 `Downloaded to:`만 돌려준다(908회 중 34회, PDF 166개). `artifacts`가 찬 런 0개. 10/9 측정 땐 `artifacts/tmp/`였으니 Aside 배치가 바뀐 것으로 보인다(추론) | 세션 폴더 |
| M10 | **`show`가 약속과 다르다.** 내용이 `[{"type":"text",…}]` JSON 문자열, PDF는 `Downloaded to:` 안내뿐, 안 열린 출처는 그 검색 결과 전체(같은 14,801자) | 실제 런에 실행 |
| M11 | **EUC-KR을 깨진 채 `ok`로 저장.** ppomppu 글 `ok`, 제목 `��ü �Խ���`, 6,943자 중 U+FFFD 3,451자. `fetch_batch.js`가 UTF-8로만 디코딩. 샌드박스 `TextDecoder("euc-kr")`도 틀린 값. 탭 경로는 정상. 실사용 저장 페이지 76개 중 0개 | `fetch` 실측 |
| M12 | **JSON 응답을 못 읽는다.** `api.github.com` → `error`, `httpbin.org/json` → `shell_escalated`. XML은 `shell`. 10/31 실사용에서 API URL 2개 error | 실측, 전사 |
| M13 | **Aside가 꺼져도 `fetch`·`map`이 그렇게 말하지 않는다.** `fetch` 종료 4 `no response`, `map` 종료 5 `budget_exhausted`. `search`만 종료 3 | 가짜 Aside |
| M14 | `crawl`이 `--max-pages`(기본 25)로 잘라도 응답에 표시 없음. `--from`도 25에서 잘려 `--help`의 "crawled as it is"가 거짓 | 합성 60개 → `requested:25` |
| M15 | `fetch --out` 상대 경로는 응답 `path`도 상대(`"index.html"`) | 전사, 코드 |
| M16 | `sessions --runs-dir`는 효과 없음. `log`만 결과를 stderr로. `--model` 예시·기본값이 문장에 박힘. `search --help`에 구독 비용 없음. 종료 3의 뜻이 층마다 다름. `next.run_in_background`는 상수인데 산문이 고쳐 읽게 함 | 프레임 감사 |
| M20 | **HTTP 오류가 `opened`.** webfetch 908건 중 126건(13.9%, 46세션)이 `isError:false`에 본문 `HTTP 403 …`(403 71·401 28·404 17 등) | 전수 재확인, `transcript.py:237` |
| M21 | **실패 원인을 숨긴다.** `stopReason:error` 8세션(`402 Insufficient credits` 6, `Codex usage limit` 2). `errorMessage`를 읽는 코드가 없어 응답은 `failed`·`empty`뿐 | 전수 재확인 |
| M22 | **답의 인용 URL과 `opened`가 어긋난다.** 최근 런, 답 URL opened/목록만/기록 없음: onplat 2/8/7, platform 3/3/3, fsc 0/5/2·0/2/5, 261103 1/8/1. 기록 없는 것에 "직접 확인했다"는 회의록 PDF 5건 포함(REPL `fetch`로 읽어 파서가 못 본다) | `result.json` 대조 |
| M23 | `map`·`crawl`이 apex→www 리다이렉트에서 사이트를 1페이지로 본다, 응답은 `ok` | Sonnet 합성 재현, 코드 |
| M24 | `find_session_by_marker`가 fork_self 자식에 붙은 런 8개(9월), 같은 초 그룹에서 슬러그가 접두사면 마커 충돌(합성). 현재 런엔 아직 없음 | Sonnet |
| M25 | **대조 실험**(Opus 5.5, 가짜 Aside, 현재 본문 vs 진입점만 남긴 본문, 28회). 네이티브 웹 도구 사용: 최소 12/14, 현재 0/14. 위임 프롬프트(목표·출처 제약·증거·부정 발견 허용)는 두 본문이 같은 모양. `opened` 안 된 인용 검증(30일/60일 함정)은 두 본문 모두 4/4 통과하고 원문을 따름, 받은 한계도 스스로 밝힘. `next` 포그라운드는 현재 본문 2/2 | `claude -p` 28회 |
| M26 | 모델이 run id를 위치 인자로 추측: 실험 11/28, 실사용 1회 | 실험, 전사 |
| M27 | default 모드에서 변수 경로·`cd` 복합은 실제로 거부(실험 denial 7건). SKILL.md 진입점 문단의 설명은 사실이다 | `permission_denials` |
| M28 | 프레임 감사(Sonnet, 코드만 제공): 트리·`cli.py`·import 방향·stdout·테스트 위치 모두 부합, 재작성 불필요. **다른 모델 계열 리뷰가 아니다**(Codex 한도, 11/4 17:09 재개) | 워커 `…-frame-audit-b36e`, `…-reality-check-8326` |
| M29 | `aside repl` 직접 호출 23회(v2 이후), 실사용 주제는 탭 부착·응답 감시·스크립트. `repl-api`는 설명 6,141자에 `openTab`·`attachBrowserTab` 등을 담는다 | 전사, 실행 |
| M30 | 큰 webfetch 결과는 본문 대신 `[Output too large (69.8KB). Full output saved to: <세션>/tmp/webfetch-result-….txt — …]` 한 줄이다. 최근 238세션 webfetch 781건 중 48건(6.1%, 인용 태그 없음, 파일은 모두 존재). websearch도 189건이나 `details.sources[].excerpt`가 남는다 | 전수 재확인 |
| M31 | 파서가 모르는 역할: `user-message-metadata` 8건(첨부 메타데이터), `compaction`(런 사본에만). 지금은 `raw`가 된다 | 전수 재확인 |
| M32 | `Downloaded to:` 38건 중 HTTP 오류 동반 2건, `File size: 0 bytes` 3건. 일반은 태그 뒤 빈 줄, 오류는 `\nHTTP 406 …\nDownloaded to: …`. 경로에 `'`·`[ ]`·U+0085, 확장자 없음이 있다 | 전수 재확인 |
| M33 | HTTP 규칙 `^<webfetch-citation[^>]*/>\nHTTP [3-5]\d\d\b`: 781건 중 113건 일치, 미일치인데 첫 300자에 `HTTP [3-5]\d\d`가 든 것 0건. 정상 페이지는 태그 뒤 빈 줄이다 | Sonnet, 재확인 |
| M34 | U+FFFD 비율은 전체 길이로 재면 마크업 많은 EUC-KR 페이지를 놓친다(합성 13만 자: 전체의 0.45%). 비ASCII 대비로는 85.7%, 산문 100% | 합성 측정 |
| M36 | skill-maker v0.6.0 실측의 fallback 사례: 사실만 준 조건(WebFetch는 요약을 돌려주고 사용자 접근을 쓰지 못한다, 사용자는 자기 접근으로 얻은 원문을 근거로 삼는다)에서 조용한 WebFetch 대체 0/3. M25의 12/14는 이 사실도 없는 조건이었다. 단일 응답 시험이다 | `Skill Maker/.tmp/measure-v0.6/fs/out__fallback__fact__*.json` |
| M37 | `aside guide repl`(Aside 1.26.1008)은 전역 함수·`snapshot`·탭 부착·120초 제한·사이트 스킬 안내를 담는다. `repl-api`는 데몬 MCP의 `repl` 설명을 넘길 뿐이고, 더하는 것은 "120초 초과가 데몬 연결 불가 문구로 보고된다"는 한 문장뿐이다. `aside repl --help`도 기본 사용법을 준다 | 실행 |
| M35 | 실제 전사의 `content`는 항상 텍스트 블록 list인데 `conftest.tool()`과 가짜 `tool_result()`는 문자열을 쓴다. 454개 녹색이 M10을 가린 이유다 | 코드 대조 |

문제없음으로 확인한 것(Sonnet·직접): 현재 데몬의 레코드 형식과 stopReason, 도구 이름과 `_child_ids`, 최근 런 상태기계, 세션 디렉터리 비용, `next` 경로, fetch 상태 판정(EUC-KR 외), search 트리거(M3).

## skill-maker 프레임 대응 (v0.6.0, 여섯 성질)

| 프레임 | 지금 | 이 계획 |
|---|---|---|
| Principle over rail | 방법을 정하는 줄이 많다(Reuse, Map first, resume when, read before citing, work is done when, stop rather than substitute) | 전부 삭제. 모델이 볼 수 없는 사실과 성진이 정한 것(원문을 근거로 삼는다)만 남긴다. 행동 줄은 하나도 없다: 진입점 문단도 "규칙이 명령 문자열을 대조하므로 변수 경로·이어쓰기는 승인 창에 걸린다"는 사실로 쓴다 |
| Interface over document | `next` 규칙·취소 불가·부분 결과·`opened`가 본문과 `--help` 두 벌 | `next`의 사실은 응답 `note`로, 나머지는 `--help`로. 본문은 명령 사이의 차이와 호출 전에 알아야 할 것(취소 불가, search의 구독 비용, 사용자 계정으로 나감)만 |
| Model over machinery (신규) | 12개 명령 | 아래 "명령 자격 대조" 표. `repl-api` 제거, `cited_not_opened` 미도입. 이번 수정은 대부분 이미 자격 있는 명령이 남의 형식을 조용히 잘못 읽던 것을 고치는 일이다 |
| For the model | 부합 | 실측·기각 대안은 이 파일·PR 본문에 |
| Dense | 약 700단어, 행동을 안 바꾸는 구간 있음(M25) | 약 200단어 목표 |
| Colleague over autopilot | 비어 있음 | 도메인이 가진 것만 적는다: 오판 지점과 확인할 증거(`ok`·`opened`·`opened_sources`의 뜻), 되돌리기 비싼 것(취소 불가, 사용자 계정). 사람 몫을 정하는 줄을 없앤다. 일반적인 "확인하라"·"보고하라" 줄은 쓰지 않는다(프레임이 금하고, 인계 때 한계를 밝히는 것은 M25에서 모델이 이미 했다) |
| 특정 상황·방법론 상정 없음 | `Choose`·`Delegate`·`Follow` 구간, `search`의 고정 접미사 | 본문은 사실과 비교로, 응답의 맥락 문구는 사실로 쓴다(행동을 지시하지 않는다). 접미사는 "요청이 없으면"으로 |
| Code the skill bundles | 부합 | 트리 유지. 벗어나는 지점은 `./.ultra-search/` 하나 그대로 |
| When the skill is done | 아래 "검증"이 항목별로 대응 | 전문 승인, 성진의 이의와 모델이 못 잡는 실수마다 자리 또는 뺀 이유, 행동 줄마다 Principle over rail 시험, 명령마다 Model over machinery 시험, `plugin validate --strict`, 계약 대비 검증, 다른 모델 계열이 여섯 성질로 리뷰, 개발 기록은 스킬 밖 |

### 명령 자격 대조 (Model over machinery)

| 명령 | 자격 | 판정 |
|---|---|---|
| `search`·`resume`·`sessions` | Aside 에이전트와 세션 저장소에 닿는 길(모델 도구에 없는 도달) | 유지 |
| `result`·`log`·`show` | 남이 소유한 전사 형식을 턴 경계·자식·인용 태그까지 읽는 일. 모델이 JSONL을 직접 읽으면 조용히 틀린다(M7·M10·M20이 그 증거) | 유지, 결과가 사실을 말하게 고침 |
| `fetch`·`map`·`crawl` | 로그인된 브라우저로의 도달, 모델 도구가 못 읽는 HWP·PDF·Office 변환, 크롤이 페이지마다 같은 일을 반복 | 유지. JSON·XML은 변환 없이 원문 저장(변환이 자격이 없는 경우) |
| `doctor`·`setup` | 매번 같은 점검과 설치 | 유지 |
| `repl-api` | 데몬 설명을 넘기기만 함, `aside guide repl`이 대신함 | **제거** |
| `cited_not_opened`(계획했던 필드) | 결과에 이미 드러나는 일을 다시 계산 | **만들지 않음** |
| `search`의 접미사 | 원격 에이전트에게 성진이 정한 사실을 전한다 | 유지(문장은 ⑤) |

### 대조 실험이 드러낸 차이의 처리 (프레임 완료 조건)

| 차이 (최소 본문 vs 현재 본문) | 처리 | 이유 |
|---|---|---|
| 실패·부실 결과에 네이티브 도구 사용 12/14 vs 0/14 | 행동 줄 대신 사실 한 줄 | 사실만 준 조건 0/3(M36). ⑥에서 새 본문으로 다시 잰다 |
| 차단 페이지에 `search`를 추가로 돌림(최소만) | 넣지 않음 | 모델 판단 몫. `search`가 구독을 쓴다는 비교는 본문과 `--help`에 있다 |
| 저비용 `--effort`를 스스로 고름(최소만) | 넣지 않음 | 모델 판단 몫 |
| run id 위치 인자 추측 11/28(양쪽) | 인터페이스 | ⑤ |
| 위임 프롬프트 모양, 인용 검증 | 차이 없음 | 본문에서 삭제 |
| `next` 포그라운드 실행(현재 2/2, 최소는 그 단계에 못 감) | 응답 `note`의 사실 | T3으로 판정. 사실만으로 부족하면 그때 처방을 이유와 함께 |

## 보존할 행동 (바꾸기 전에 기존 테스트가 지킴)

`fetch` 상태 8종과 "ok 아닌 항목은 저장 안 함", 셸→탭 승격, 챌린지 판정, `--format html`, `original_path`. 병렬 그룹, 한글 라벨 run id와 고유 접두사, 재개 런의 턴 경계, `sessions`로 앱 세션 재개. W1–W7 상태표와 마무리 판정, `abandoned`, 감독자 생존 확인. `show --source n`이 `result`의 `n`과 같은 출처, `show --item N`이 `log --level steps`의 `#N`. 종료 코드 0/2/3/4/5. `map` → `crawl --from`, 저장 이름 보장, `./.ultra-search/.gitignore`. HWP·HWPX 추출.

## 변경 상세

### ① 전사가 사실을 말하게 (M7, M10, M20, M21, M22, M24)

- `aside/transcript.py:133`, `aside/repl.py:106`, `converter/node.py:39`, `aside/daemon.py:101`의 레코드 분리를 `split("\n")`으로. `_count_lines_before`와 같은 기준이 되어 `index`도 맞는다. 표시용 `render._first_line`, `classify._first_heading`, `process.version`은 그대로.
- 가짜와 시험 도구도 같이: `tests/fake_aside/aside:174`(replay), `tests/conftest.py:150`(`run_cli`). 안 고치면 시험 자체가 그 문자를 못 지나간다.
- `_as_text`: 블록이 전부 텍스트면 `_flatten_text`와 같은 규칙(구분자 `\n`)으로 평문, 그 외 블록이 섞이면 지금처럼 JSON. `steps.golden.txt`의 크기 값이 바뀌는 것은 의도한 변경으로 PR 본문에 적는다.
- `_tool_result`(webfetch 한정): 본문이 `^<webfetch-citation[^>]*/>\nHTTP [3-5]\d\d\b`면 `opened=False`(M33). `Downloaded to: <줄 끝까지>`면 `holds_page=False`와 `SourceRef.saved_path`, 단 HTTP 오류 동반이나 `File size: 0`이면 기록하지 않는다(M32). `Full output saved to: <경로>`면 본문은 그 파일에 있으니 `saved_path`에 텍스트로 표시, `holds_page` 참(M30). `saved_path`는 ②가 쓴다.
- `errorMessage`(`role:assistant`, `stopReason:error`의 최상위 키)를 `Event.error`로. `Turn.error_message()`는 이 턴의 부모 스트림만 본다(`ended_on_error`와 같은 범위). `_finish`가 `failed`면 `note`와 `reason`에 넣어 `result` 응답까지 나온다.
- 역할 `user-message-metadata`, `compaction`은 `kind="meta"`로 읽고 `render`는 표시하지 않는다(M31). 남은 `raw`가 있으면 `note`에 "N records in this run's transcript could not be read". 형식 변화가 조용히 지나가지 않게 한다.
- `cited_not_opened` 필드는 만들지 않는다(성진 11/7). 열린 기록이 없는 인용은 `opened_sources`와 답을 보면 드러나므로 본문의 사실 한 줄이 맡는다.
- `source_text`: 안 열린 출처는 `excerpt`가 있으면 그것, 없으면(HTTP 오류로 닫힌 webfetch 등) 그 결과 본문을 준다. 검색 결과 전체를 주지 않는다.
- 마커 대조: `marker.py`가 `f"{marker} —"` 토큰을 만들고 호출자가 그것을 넘긴다(`turn_start_index`, `find_session_by_marker`, `aside`는 이 문자열의 구조를 모른다). `성진:` 주석 둘: REPL로 읽은 페이지는 `opened`로 잡지 못한다, 그래서 본문이 그 사실을 말한다 / fork_self 자식과 부모를 가르지 않는다, 잘못 붙은 런이 다시 보이면 기준을 정한다.
- `aside/__init__.py`의 `__all__`에 새 이름을 올린다. `research`·`cli.py`의 문구에는 구조 테스트의 `ASIDE_NAMES`(`webfetch`, `artifacts/`, `toolResult` 등)를 쓰지 않는다.
- 이 PR이 `show --help`와 `ENTRY_HELP`의 `opened` 설명을 같이 고친다.

### ② 에이전트가 받은 문서를 챙긴다 (M9, M10)

- `aside.session_saved_files(session_id, events)`: 스트림의 `saved_path`를 그 스트림의 세션 폴더 안 일반 파일만 걸러 돌려준다(`resolve` 후 `is_relative_to`, 자식은 자식 세션 폴더 기준). `parse_record`는 세션 폴더를 모르므로 거르는 일은 여기서 한다. 새 형식 지식은 `aside/` 안에만.
- `_keep_artifacts`: 기존 `artifacts/` 처리는 그대로 두고, 이 턴 스트림의 저장 파일을 `run.artifacts_dir/<sid>/downloads/<이름>`으로 같은 `copy_snapshot`으로 복사한다(기존 `rel`과 섞이면 덮어쓰고 답의 링크를 잘못 고친다). 같은 이름이 한 턴에 두 번 오면 나중 것을 `-2`로. 수정 시각이 다음 턴 시작 이후면 복사하지 않고 `artifacts_missing`. 실패도 `artifacts_missing`. `tmp/` 전체를 긁지 않는다(`websearch-result-*.txt`, `guide.txt` 같은 작업 파일이 대부분).
- `Source.file` → `result.json`의 source와 `opened_sources[].file`. `artifacts`에는 받은 문서만 넣고 잘린 출력의 텍스트 파일은 넣지 않는다.
- `show --source N`: 잘린 출력이면 그 파일의 본문을 `content`로(태그 제거), 받은 문서면 안내 대신 `note`와 `file`. 런이 끝나기 전에는 세션 경로를 읽는다.
- 이 PR이 `ENTRY_HELP`의 `file`을 같이 고친다.

### ③ fetch가 사실을 말하게 (M8, M11, M12, M13, M15)

- `aside.require_ready()`: `research/commands._require_aside`를 `aside` 단위로 옮겨 `search`·`resume`·`fetch`·`map`·`crawl`이 일하기 전에 부른다. Aside 불가면 종료 3과 `fix`.
- JSON·XML: `classify_response`가 `json`, `+json`, `xml`, `+xml`(xhtml 제외, 본문에 `<html` 없음)을 `kind="data"`, `ext`로 분류하고 `status ok`. `_save`는 `.json`/`.xml`로 원문 그대로, frontmatter 없음. `--format html`은 기존처럼 거부.
- 디코딩 실패: 원본 본문에서 U+FFFD가 20자 이상이고 **비ASCII 문자의 과반**이면(M34) `Document(status="shell", raw="", error="the response is not UTF-8")`. `auto`는 탭으로 승격하고(브라우저가 charset을 푼다), `--via fetch`는 `shell`로 저장 안 함. `--format html --via fetch`도 같은 상태와 오류로 보고한다(`_save`의 `needs an HTML response` 경로로 빠지지 않게). 오판 비용은 탭 한 번이고 탭 결과에는 이 검사를 하지 않는다. 상태는 8종 그대로, `shell` 설명에 한 구절 추가. `성진:` 주석에 임계값과 근거, JS에서 디코딩하지 않는 이유(`TextDecoder` 실측 오류)를 적는다.
- `_destinations`, `map --out`, `crawl --out` 경로를 `.absolute()`로.
- 이 PR이 `fetch --help`의 `shell`·`ok`·응답 모양과 문서 목록을 같이 고친다. `ok`는 "text was saved; not proof it is the text you wanted"(JSON·XML·평문은 추출이 아니다).
- 시험 주의: 자동 fixture `no_real_aside`는 바이너리를 없는 경로로 둔다. `fake_aside` 없이 `fetch`를 부르던 시험이 있으면 `require_ready`에 먼저 막히니 확인한다. `aside_down` 시나리오와 죽은 데몬은 별개라 `ULTRA_SEARCH_DAEMON_URL`을 닫힌 포트로 돌린다.

### ④ 사이트 수집이 사실을 말하게 (M14, M23)

- `--max-pages` 기본 None: `URL`이면 `site.DEFAULT_MAX_PAGES`(25), `--from`이면 전체. 응답에 `discovered`, `not_crawled`(수), 잘렸으면 `note`("stopped at --max-pages; raise it, or map and crawl --from"). 매니페스트의 `not_crawled`는 URL 목록. `discovered`는 `--max-urls`로 이미 잘린 수일 수 있고 그것은 `coverage.max_urls_reached`가 말한다.
- `discover.origin()`이 `www.` 접두사를 같은 사이트로 본다(스킴·포트 구분은 유지). `coverage.dropped_other_origin`(링크·사이트맵에서 다른 출처라 버린 수)로 다른 리다이렉트도 드러낸다. `성진:` 주석: apex와 www가 섞인 사이트는 같은 페이지를 두 번 받을 수 있다, 보이면 URL 정규화.
- 이 PR이 `crawl --help`·`map --help`의 `--max-pages`·`--from` 문구를 같이 고친다.

### ⑤ 표면 정리 (파괴적, M5, M6, M16, M26)

- `search`·`resume`: `--wait`·`--background` 제거, `_await_and_report` 제거, 시작 즉시 항목과 `next`. `commands.py` docstring의 "most searches finish in seconds"를 고친다.
- `result [RUN]`, `log [RUN]`, `show [RUN]`: 위치 인자로, `--run` 제거. `--group`과 상호 배타(3.10·3.14 argparse 동작 확인됨). `next`와 `resume` 오류의 `fix`(`commands.py:316`)도 위치 인자로. 테스트 `--run` 80곳은 기계적 치환.
- `result --wait`: 진행 줄 없음. `follow.py`의 커서·`_emit`을 지우고 `timeline.py`로 줄인다(`log`가 읽는 줄 만들기). 대기 루프는 `commands.py`.
- `log`: stdout JSON 하나 `{ok, command, runs:[{run_id, state, …, lines:[…]}]}`. stderr 없음. `--level` 4종과 `#N` 번호 유지. `--help`에 `full`·`raw`는 크다고 적는다. 시험은 `test_research.py:212`의 `log_of` 도우미만 바꾼다.
- `next = {command, bash_timeout_ms, run_in_background}` 그대로. 응답 `note`는 사실만 말한다: 백그라운드 호출의 완료는 그때 살아서 받을 무언가에게만 닿는다(턴과 함께 끝나는 `claude -p`·서브에이전트·예약 작업에서는 아무도 받지 않는다). 무엇을 할지는 쓰지 않는다. `NEXT_HELP`는 두 문장으로(필드 뜻과 `note`). `test_environment.py:360`의 대상 문구를 함께 고친다.
- `research/marker.py`의 `SCOPE`를 합의 원장의 문장으로. `search --help`·`resume --help`가 인용하는 문장과 이를 단언하는 시험을 같이 고친다.
- `cli.py` 문구: `search --help`에 구독 사용, 종료 3을 "an external dependency is unavailable"로, `--model` 예시 제거, 기본값은 `%(default)s`. `sessions --runs-dir` 제거.
- `doctor`: 버전 차이는 `fix`가 아니라 `note`.
- `repl-api` 제거(성진 11/7): `cli.py`의 파서·`ENDINGS`, `doctor.repl_api`·`_HOW_TO_RUN`, `aside.mcp_tools`(다른 호출자 없음, `__all__`에서도), `tests/test_environment.py:200-226`의 세 시험과 `:318`·`:341`의 명령 목록, `tests/live/test_live.py:166`, 가짜 Aside의 `mcp` 응답(다른 시험이 쓰지 않으면). 옛 명령은 종료 2. `_HOW_TO_RUN`의 사실(120초 초과가 연결 불가로 보고된다)은 본문으로 옮긴다.
- **SKILL.md 최소 수정(같은 PR):** `Follow state` 구간을 사실로 고친다(`search`가 즉시 반환, `result` 위치 인자, 응답 `note`를 따른다). 스킬이 전역 심볼릭 링크라 머지 순간 모든 세션이 이 본문을 읽기 때문이다. 전체 교체는 ⑥.
- `tests/test_structure.py` docstring의 낡은 `status` 언급 정리(지나가는 경로).

## 구현 후 트리

```
.claude/skills/ultra-search/
├── SKILL.md                         # 본문 재작성
└── scripts/
    ├── cli.py                       # 표면 정리, 위치 인자, 문구
    └── ultra_search/
        ├── __init__.py              # __version__ = "3.0.0"
        ├── research/
        │   ├── commands.py          # 즉시 반환, 대기 루프
        │   ├── supervisor.py        # 다운로드 복사, 실패 원인 note
        │   ├── evidence.py          # source_text, 마커 경계
        │   ├── timeline.py          # follow.py에서 줄임
        │   ├── marker.py            # 마커 토큰
        │   └── render.py · states.py · __init__.py
        ├── aside/
        │   ├── transcript.py        # split("\n"), HTTP 오류, 다운로드, errorMessage, _as_text
        │   ├── repl.py · daemon.py  # split("\n"), require_ready
        │   ├── sessions.py          # session_saved_files
        │   └── process.py           # VERIFIED_* 갱신, require_ready는 daemon.py 쪽
        ├── fetch/classify.py · acquire.py · commands.py   # data, 디코딩, 절대 경로
        ├── site/commands.py · discover.py                 # discovered, www, dropped_other_origin
        ├── doctor.py                # doctor · setup (repl-api 제거)
        ├── converter/node.py
        └── hwp/ · runs/ · saved.py · outcome.py · ids.py · workspace.py   # 그대로
tests/
├── conftest.py · fake_aside/aside   # split("\n"), 재생 지시
├── test_aside_formats.py            # 분리 문자, HTTP 오류, 다운로드, errorMessage
├── test_research.py · test_run_directory.py · test_pages.py · test_environment.py · test_contract_fake_aside.py · test_structure.py
└── live/test_live.py · live/test_real_sessions.py   # 신규: 실제 전사 불변식
```

import 방향과 단위 종류는 그대로라 구조 테스트의 표는 바뀌지 않는다.

## SKILL.md (구현 후, 전문 초안)

frontmatter: `name`, 아래 description, `allowed-tools` 그대로. 영어. references 없음(모든 경로가 본문 전체를 쓴다).

description:

> Search the web, read full pages and documents, map or crawl sites, and work a page directly (click, script, inspect its DOM or back-end calls) through the user's logged-in Aside browser, including sources anonymous web tools cannot reach. Use instead of WebSearch/WebFetch for web research, current versions, news, docs, prices, reading a URL, PDFs, HWP or Office documents at a URL, and saving pages as markdown. Triggers include search, fetch, crawl, scrape, 검색해봐, 찾아봐, 웹에서, 최신 버전, 원문 읽어와, 크롤링, 마크다운으로 저장, 사이트 전체, 로그인해야 보이는 페이지. Not for local files or codebase search, or facts already known.

본문:

```
# Web work through the user's own browser
  진입점 문단을 사실로: "The pre-approved permission rule matches the command text: a path built from a variable or a command continued with `\` stops at an approval prompt." · 코드 블록 · "--help가 소유" — 그대로

## What each path is
  `search` hands an objective to a browsing agent that chooses its own searches and pages, spends the user's subscription, and reports back in another model's words. `fetch` reads a URL you already have into a file with no agent, and turns PDF, HWP and Office documents into text with the original kept.
  `aside repl` is the page in your own hands: click, drag and fill, run a script in it, read its DOM, watch the calls it makes to its back end, attach to a tab the user has open. `aside guide repl` documents the installed version; a snippet running past 120 seconds is killed and reported as the daemon being unreachable, though it is fine. Queries automated against a search engine draw bot challenges, so finding sources across the web works better through `search`.

## What you cannot see from here
  - `ok` means text was saved, not that it is the text you wanted: a long enough login notice passes. `opened` means a tool returned that URL without an error, not that the page says what the answer claims; `opened_sources` holds only those, so an answer can cite pages a search merely listed or that the agent read through a script, which no record shows.
  - Nothing here cancels delegated work: only Aside itself stops a run and its credit use, so a `search`'s scope is settled when it starts.
  - Requests act as the user, with their cookies, sessions and browser. A private source being reachable does not make its contents shareable.
  - WebSearch and WebFetch cannot use the user's access, and WebFetch returns a summary rather than the page; the user grounds answers in pages acquired with their own access.
```

삭제: `Choose by the work still needed`의 재사용·map·resume 문단, `Delegate an objective` 전체, `Follow state` 전체(응답 `note`로), `Only acquired content`의 "read before citing", `Partial evidence`, `Without Aside`의 행동 지시(사실은 마지막 항목으로 남김), 마지막 복구 문장. 문구는 초안이고 ⑥에서 대조 실험과 리뷰를 거쳐 전문 승인을 받는다.

## README 섹션 구조 (한국어)

```
# Ultra-Search
## 왜                (그대로)
## 네 가지 역량      (조사 위임: 즉시 반환과 next · 원문 확보: JSON·XML, 인코딩 처리 · 사이트 수집: 잘림 보고 · 결과 수거: result --wait, 에이전트가 받은 문서 · REPL 직접 조작은 `aside guide repl`)
## 설치              (그대로)
## 써보기            (위치 인자로 갱신, search 뒤 result --wait)
## 알아둘 것         (CLI는 조사를 못 멈춘다 · 침묵≠정체는 무활동 상한으로 · search는 비쌈 · 차단 페이지 미저장 · ok와 opened의 뜻 · ./.ultra-search/. "Aside 없으면 대체 안 함"은 네이티브 도구가 못 하는 것의 사실로 바꿈)
## 구조              (트리, 단위 종류·import, ./.ultra-search/ 이유, 구조 테스트)
## 개발              (테스트 명령과 개수, live, Aside 업데이트 뒤 real_sessions·live·VERIFIED_* 절차, 전사 불변식)
```

## 테스트 경계 (기존 seam만 쓴다)

- S1(주): argv → stdout JSON + 종료 코드, 외부 대역은 가짜 Aside, 반환된 `next`는 셸로 실제 실행, node 변환기·olefile은 실물.
- S2: `research.supervise()`와 runs 인터페이스.
- 단위 인터페이스: `aside`(레코드 → 스킬 용어), `hwp.extract`. 구조 테스트.
- live(`-m live`): 실제 Aside.
- 기대값의 출처: 실제 세션에서 관측한 레코드의 모양을 그대로 본뜬 합성 레코드(공개 레포이므로 실제 전사를 넣지 않는다). 예: 제목에 `ë\x85\x84`가 든 webfetch, `<webfetch-citation source_id="x" />\nHTTP 403 Forbidden` 본문, `HTTP 406`과 `Downloaded to:`가 함께 온 본문, `File size: 0 bytes`, `Full output saved to:` 한 줄, `errorMessage: aside API error (402)`, `user-message-metadata`. 답의 인용 판정은 시험이 손으로 쓴 답과 출처 목록. EUC-KR은 파이썬 `encode("euc-kr")` 바이트를 `decode("utf-8","replace")`한 본문으로, 마크업이 많아 전체 대비 0.1%·0.33%인 두 경우를 포함한다. 현재 출력을 복사한 값을 기대값으로 쓰지 않는다.
- **레코드는 실제 모양으로 쓴다**(M35): `content`는 텍스트 블록 list, webfetch는 인용 태그 접두. 기존 `conftest.tool()`과 가짜 `tool_result()`는 문자열을 만들어 수정 전에도 시험이 통과할 수 있으니, 실제 모양을 만드는 도우미를 새로 두고 ①②의 시험은 그것을 쓴다. 기존 시험을 바꾸지는 않는다.
- 가짜 Aside 확장: 세션 `tmp/` 아래에 바이너리 파일을 쓰는 재생 지시(`{"__tmp__": 이름, "bytes_b64": …}`), `__SESSION_DIR__`로 `Downloaded to:` 경로 구성. `test_contract_fake_aside.py`에 그 계약을 더한다. 재생의 `splitlines`도 고친다. 결정적 시험을 위해 접두사 충돌은 `aside_session` 도우미로 두 세션을 직접 만들고 `os.utime`으로 시각을 고정한다. CLI stdout을 `splitlines()`로 읽는 기존 시험(`test_research.py:111,162,600`)은 분리 문자가 지나가는 새 시험에서 쓰지 않는다.
- 대역이 가리는 것: 가짜는 JS를 실행하지 않으므로 `fetch_batch.js` 경로와 실제 인코딩 승격은 live로만 증명된다. 실제 `Downloaded to:`·`Full output saved to:`·`HTTP nnn` 형식 변화는 `test_real_sessions`와 live search로만 잡힌다. 대화 세션에서 모델이 `next`를 어떻게 실행하는지는 어떤 시험도 재지 않는다.
- 새 live 불변식 `tests/live/test_real_sessions.py`: 이 기기의 최근 실제 세션 전사에서 `\n` 레코드 수 == 이벤트 수, `raw` 0, 도구 이름이 시험 안의 `KNOWN_TOOLS`(websearch, webfetch, repl, bash, read_file, subagent, subagent_wait, write_todos, get_time, memory_search, history_search, closeTab) 밖이면 목록을 실패 메시지에, `saved_path`가 가리키는 파일이 있음. `aside` 공개 인터페이스만 쓰고 데이터는 레포에 넣지 않는다. 이것이 M1의 원인(녹색 테스트 뒤의 형식 변화)을 줄인다.

## 단계와 완료 판정

각 단계 시작 시 `TaskCreate`에 완료 판정을 그대로 적고 끝날 때 `TaskUpdate`. 브랜치는 `main`에서, 제목은 `<타입>: <한국어 제목>`, PR 본문 `## 무엇을 바꿨나`/`## 왜`/`## 영향`/`## 검증`(실행한 명령과 수치). 코드 단계는 `coding` 스킬을 연다. 구조와 행동은 커밋을 나눈다. 버그는 재현 테스트 먼저. `gh pr merge --squash`. `git add`는 파일을 지정한다: `.claude/settings.json`·`.agents`·`.codex`와 `.claude/plans/users-seongjin-…-rippling-koala.md`(하네스 경로의 심볼릭 링크)는 커밋하지 않는다. 각 PR은 자기가 바꾼 응답의 `--help`를 같이 고쳐, main의 `--help`와 SKILL.md가 어느 머지 시점에도 거짓을 말하지 않게 한다.

독립 리뷰: **Codex 한도가 11/4 17:09에 풀린다.** 풀린 뒤에는 `codex` 스킬(gpt-6.1-terra, high, read-only)로 공유 계약 변경(①·⑤) 녹색 직후와 머지 전, 그리고 최종 전체를 리뷰한다. 구현 시작 때 이 계획도 먼저 Codex에 넘긴다. 풀리기 전이면 `claude` 스킬 Sonnet으로 대신하고 다른 모델 계열의 시각이 없다고 보고에 적는다.

0. **준비** — 합의 원장의 "이 작업의 목표"를 프로젝트 메모리에 `feedback`으로 기록한다(계획 모드에서는 쓸 수 없었다). 작업 트리 SKILL.md의 커밋 안 된 description 변경을 버린다(`git checkout -- .claude/skills/ultra-search/SKILL.md`, 성진 결정: 다른 스킬 언급 없음, 최종 문안은 ⑥). `aside --update`, `aside --version`·`doctor` 기록, 기준선, `-m live` 전체(실제 exec 3개 구독 소모). 실패하면 형식 변화인지 가르고 형식 변화면 ① 앞에서 고친다. Codex 한도가 풀렸으면 이 계획을 먼저 Codex에 넘긴다.
   완료 판정: 새 CLI·데몬 버전 기록, 기준선 `454 passed, 18 skipped`, live 18개 결과 기록, `git status`에 SKILL.md 변경 없음.
1. **① `fix/transcript-truth`** — `fix: 전사가 사실을 말하게`. 빨강 먼저(aside 인터페이스와 S1, 실제 모양 레코드): U+0085·U+2028·U+2029 레코드가 이벤트 1개로 읽힘(수정 전 raw), 같은 문자가 든 REPL 레코드·변환기 출력이 통과, `HTTP 403` webfetch가 `opened:false`, 태그 뒤 빈 줄의 정상 webfetch는 `opened:true`, 본문 어딘가에 `HTTP 403`이 든 정상 페이지도 `opened:true`, `errorMessage`가 `failed` 응답의 `note`에 나옴, `user-message-metadata`가 `raw`도 note도 만들지 않음, 알 수 없는 역할은 note, `show --source`가 평문이고 안 열린 출처는 그 `excerpt`, excerpt 없는 HTTP 오류는 그 사유, `show --item N`이 `log --level steps`의 `#N`과 일치(분리 문자 레코드가 앞에 있을 때), 같은 초 그룹의 접두사 슬러그가 각자 세션에 붙음. `VERIFIED_*`는 0단계 결과로 갱신.
   완료 판정: 새 테스트가 수정 전 실패·수정 후 통과, 전체 녹색, `runs/261103-143546`의 전사 사본에 수정 코드를 돌려 레코드 43 → 이벤트 43, thevc PDF `opened:true`, 리뷰 처리.
2. **② `fix/agent-downloads`** — `fix: 에이전트가 받은 문서를 결과에`. 빨강 먼저(S1·S2): 가짜 Aside가 세션 `tmp/`에 문서를 쓰고 webfetch가 `Downloaded to:`를 돌려줌 → `artifacts`·`opened_sources[].file`에 복사본, 바이트 동일, 모지바케 이름도 동작, 세션 밖 경로·링크·0바이트·HTTP 오류 동반은 복사 안 함, 부모·자식 동명 파일과 `artifacts/`의 같은 이름이 섞이지 않음, 다음 턴이 고쳐 쓴 파일은 `artifacts_missing`, 복사 실패도 `artifacts_missing`, `show --source`가 문서엔 `file`, 잘린 출력엔 그 파일의 본문.
   완료 판정: 빨강→초록, 전체 녹색, 실제 진입점(심볼릭 링크 경로, 무관한 디렉터리)에서 가짜 Aside로 받은 경로를 Read로 열 수 있음.
3. **③ `fix/fetch-truth`** — `fix: fetch가 사실을 말하게`. 빨강 먼저(S1): `fetch`·`map`·`crawl`이 죽은 데몬에서 종료 3과 `fix`, JSON·XML이 `ok`로 원문 그대로 `.json`·`.xml`, 페이지 HTML 분류는 그대로, EUC-KR 바이트 본문(전체 대비 0.1%인 경우 포함)이 `ok`가 아니고 `auto`면 탭 결과로 저장, `--via fetch`·`--format html --via fetch`면 `shell`로 저장 안 함, 정상 페이지에 U+FFFD 몇 자는 `ok`, 상대 `--out`의 `path`가 절대 경로. live: JSON API, ppomppu 글에 U+FFFD 없음.
   완료 판정: 빨강→초록, 전체 녹색, live fetch 계열 통과.
4. **④ `fix/site-truth`** — `fix: 사이트 수집이 잘림을 말하게`. 빨강 먼저(S1): 사이트맵 60개 기본 `crawl` → `discovered:60, not_crawled:35`와 `note`, 매니페스트에 잘린 URL, `--from` 매니페스트 60개 → 60개 저장, `--from --max-pages 10` → 10개와 `not_crawled:50`, apex 루트의 www 링크·사이트맵을 받아들임, 다른 도메인 리다이렉트는 `dropped_other_origin`에 수.
   완료 판정: 빨강→초록, 전체 녹색, live `crawl`·`map` 통과, `--help` 문구 일치.
5. **⑤ `feat/one-wait`** — `feat: 조사는 즉시 반환, 대기는 result 하나로`(본문에 BREAKING). 구조 커밋: `follow.py` → `timeline.py`(녹색 유지). 행동 커밋, 테스트 먼저(S1): `search`가 대기 없이 `next`를 줌(`slow`에서 1초 안에 반환), 그 `next`를 셸로 실행하면 stdout·stderr를 합쳐도 `json.loads` 성공(M6 재현), `note`에 맥락 규칙, `result RUN`·`log RUN`·`show RUN` 동작, `--run`·`--wait`(search)·`--background` 종료 2, `log`가 stdout JSON이고 `--level steps`에 `#N`, `sessions --runs-dir` 종료 2. `tests/test_research.py:57`의 `search` 도우미를 "`search`로 시작하고, 실패하거나 `next`가 없으면 그 코드와 응답을, 아니면 `result <run_id|--group> --wait`의 코드와 응답을 돌려준다"로 바꿔 동기 흐름 테스트를 옮긴다. 시작 시점 동작(종료 3 등)을 보는 시험은 `cli("search", …)`를 직접 쓴다. 옛 단언 → 새 위치 대조표를 PR 본문에. `result --wait`를 일부러 끝나기 전 반환하도록 망가뜨려 옮긴 테스트 실패 확인 후 되돌림.
   완료 판정: 전체 녹색, 변형 확인, `--help` 최상위에 명령 11개, 실제 진입점에서 `search`→`next`→결과, `--help` 전 명령을 실행해 응답·문구 일치와 의미 단위 한 줄 확인, SKILL.md에 거짓 문장 없음, 리뷰 처리.
6. **⑥ `docs/skill-text-v3`** — `docs: 스킬 본문을 목적 중립으로 재작성`. SKILL.md·README·`.claude/plans/261103_ultra-search 스킬 품질 점검 계획.md`를 커밋하고 하네스 경로의 심볼릭 링크는 지운다. 대조 실험 재실행(아래). 리뷰 반영. 전문을 AskUserQuestion으로 보여 승인(침묵은 승인 아님).
   완료 판정: 아래 "검증" 전부.
7. **⑦ GitHub 릴리스 (성진 요청, 이 작업의 마지막 단계)** — ⑥까지 머지되고 "검증"이 모두 끝난 뒤. `chore(release): v3.0.0` PR(`__version__`·버전 테스트) 머지 → main을 받아 `git tag v3.0.0`·푸시 → `gh release create v3.0.0 --title …`. 형식은 `gh release view v2.0.0`을 따른다. 한국어 노트: 바로잡은 것 / 없어진 것과 대신 쓸 것(`search --wait`·`--background`, `--run`, `sessions --runs-dir`, `repl-api` → `aside guide repl`) / 바뀐 동작(즉시 반환, `result --wait` 출력, `crawl --from`, 접미사, 본문에서 빠진 대체 금지) / 검증한 것과 안 한 것 / 전제(uv·Node·Aside, `setup` 재실행, `aside --update`).
   완료 판정: `gh release view v3.0.0` 성공(최신 릴리스, main 머지 커밋의 태그), `cli.py --version`이 `ultra-search 3.0.0`, 로컬·원격 main 일치, `git status`에 의도한 미추적 파일만.

## 검증 (스킬 완료 조건)

- `uv run --python 3.10 --with pytest --with olefile pytest -q` 녹색, `-m live` 전체 통과(새 `test_real_sessions` 포함).
- 대조 실험: 격리 디렉터리의 스킬 복사본 + 가짜 Aside, `claude -p --setting-sources project --permission-mode default --allowedTools 'Bash(uv run *)' Read Grep Glob Skill WebSearch WebFetch --model opus`(`bypassPermissions`는 자동 모드 분류기가 막았다). 새 본문으로 각 3회:
  - T1 알려진 URL → `fetch`. T2 출처 선택 질문 → 목표를 담은 `search`. T4 챌린지 → 읽은 것으로 인용하지 않음.
  - T3 `slow`, `claude -p` → `next`를 포그라운드로 실행해 결과를 받음. **이것이 3/3이 아니면 본문에 맥락 규칙 한 문장을 되살린다**(응답 `note`만으로 부족하다는 뜻).
  - T7 30일/60일 함정 → 인용 전 원문 대조(M25 수준 유지).
  - T5·T5b Aside 불가, T2 부실 결과 → 조용한 네이티브 대체가 없는지(M36 수준). 넘어가더라도 요약임을 밝히거나 먼저 물으면 통과. 결과는 성진에게 결과로 보여 주고 어떻게 볼지 묻는다(행동 처방을 정하자고 묻지 않는다).
  - T9 REPL이 필요한 과제(예: 페이지의 백엔드 호출 확인) → `aside guide repl`을 찾아 읽는지.
  - `permission_denials`로 실패한 실행은 입력을 보충해 재실행. 기록은 PR 본문에.
- `claude plugin validate --strict /Users/seongjin/Coding/Ultra-Search/.claude/skills` 종료 0.
- `claude -p "/skill-doctor"`로 이웃 트리거 확인(결과만 기록, description에 다른 스킬 이름을 넣지 않는다).
- 최종 SKILL.md·`--help`를 `codex`(gpt-6.1-terra, high)가 skill-maker v0.6.0 여섯 성질로 리뷰, 선별 반영.
- 행동 줄마다 Principle over rail, 명령마다 Model over machinery 시험을 통과한다(위 대조 표를 구현 뒤 다시 확인).
- 성진이 SKILL.md 전문 승인. 승인은 실사용 성능의 증거가 아니라고 보고에 적는다.
- 개발 기록은 커밋·PR 본문·이 파일에.

## 재사용할 기존 자산

`tests/fake_aside/aside`의 리플레이 지시(`__sleep__`·`__after_exit__`·`__session__`·`__artifact__`·`__SESSION_DIR__`), `fetch_batch` 라우트, `FAKE_ASIDE_CALLS`, conftest `ready_daemon`·`cli`·`routes`. `runs.copy_snapshot`·`atomic_write_json`·`Run.artifacts_dir`, `supervisor._keep_artifacts`·`_finish`, `evidence.collect_sources`·`Turn.sources`·`final_answer`, `aside.exec_output._URL`, `fetch.classify.classify_response`·`_escalate`, `saved.unique_path`, `discover.resolve_links`·`origin`, `cli.ENDINGS`·`_exit_lines`.

## 기각한 대안

- 전면 재작성: 구조는 프레임에 부합하고(M28) 실측으로 다진 경계 처리를 잃는다. 결함은 지점이 분명하다.
- 사전 확인 줄, REPL 쓰기 금지, 인계 필수 항목, 저장 위치 안내, 항상 run id 넘기기: 사용자·모델 몫을 정하는 레일(성진 결정, 프레임 감사의 제안 중 기각).
- 페이지 실패 시 대안 정의, 대체 금지 확대: 같은 이유.
- `show`·`log` 제거 또는 병합, 출처별 파일로 대체: 역량 유지 결정, `show`는 내용만 고쳐도 약속을 지킨다.
- REPL 코드 파싱으로 `opened` 추정: 틀린 `opened`를 만든다. 본문의 사실이 모르는 것을 모른다고 말한다.
- `cited_not_opened` 필드, `repl-api` 유지: Model over machinery(성진 11/7).
- `tmp/` 전체 복사: 작업 파일이 대부분이다. `Downloaded to:`가 정확하다.
- JS에서 charset 디코딩: 샌드박스 `TextDecoder`가 틀린 값을 내고 가짜로 시험할 수 없다. 탭 승격이면 된다.
- Aside 사이트 스킬 안내: 성진 판단으로 넣지 않음.
- 상태를 `data/`로: 뒤집을 새 근거 없음.
- `--help`에 잘림 대비 재배치: `next` 규칙이 응답 `note`로 가면서 문제가 사라진다.
- `next.run_in_background` 제거: 위 내 판단 참조.
- fork_self 부모 선택: 위 내 판단 참조.

## 계획 리뷰 처리 (Sonnet read-only, 다른 모델 계열 아님)

워커 `20261103-194721-plan-review-5e55`, MAJOR 9·MINOR 14, BLOCKER 0. 채택 전 핵심 수치는 직접 재확인했다(M30–M34).

- 채택: #1 잘린 webfetch 포인터 → ①② · #2 알려진 역할 → ① · #3 실제 모양 레코드와 가짜 확장 → 테스트 경계 · #4 다운로드 오복사·이름 충돌·이후 변경 → ①② · #5 U+FFFD 분모 → ③ · #6 `aside.urls_in`과 비교 규칙 → ① · #7 PR마다 `--help`, ⑤에 SKILL.md 최소 수정, 파일 지정 add → 단계 · #8 HTTP 오류의 사유 → ① · #9 마커 토큰 위치 → ① · #11 `--help` 문구와 unstructured 생략 → ① · #12 앵커 규칙 → ① · #13·#14 → ① · #15 시험 주의 → 테스트 경계 · #17 → ⑤ · #18 → ③ · #19 → ④ · #20·#23 → 본문 초안 · #21 → ① · 모호한 지시 9건 → 각 항목에 확정.
- 부분 채택: #9의 "부모 기준 먼저 정하기"는 범위에서 뺐다(근거 부족, `성진:` 주석). #16은 필드 제거 대신 유지로 풀었다.
- 기각: #10 "`repl-api`가 API를 주지 않는다". 직접 실행 결과 설명 6,141자에 API 표가 있다(M29). 워커 샌드박스의 출력으로 보인다.

## 위험과 미확정

- 대조 실험은 합성 과제, 표본이 작고(과제당 1~3회) Opus 5.5 기준이다. 다른 모델이나 실제 대화에서 다를 수 있다. 전문 승인도 실사용 성능의 증거가 아니다.
- 본문에서 방법을 지우면 모델 기본값에 맡기는 범위가 넓어진다. M25가 지지하는 것은 위임 프롬프트와 인용 검증까지이고, map/crawl·resume 선택은 사용 사례가 없어 재지 못했다.
- `next`의 맥락 규칙을 응답으로 옮기는 것은 T3으로 판정한다. 대화 세션의 동작은 재지 않는다.
- `Downloaded to:`, `Full output saved to:`, `HTTP nnn` 본문은 Aside의 비공개 표면이다. 바뀌면 `test_real_sessions`와 `note`로 드러나도록 했지만 완전하지 않다. `tmp/` 이동 시점은 추론이다.
- 대체 사실 한 줄의 충분성은 단일 응답 시험 3회(M36)뿐이다. 긴 대화에서 사실이 멀리 있을 때도 같은지는 모른다. 성진의 글로벌 CLAUDE.md에도 같은 이유가 있어 실사용에서는 두 곳이 겹친다.
- `aside guide repl`은 Aside가 바꿀 수 있는 문서다. 내용이 바뀌어도 우리 쪽에서는 알 수 없다(대신 사본이 낡을 일도 없다).
- U+FFFD 임계값(20자·비ASCII 과반)은 실제 사례 1개와 합성으로 잡았다. 오판 비용은 탭 한 번이다.
- www 규칙은 흔한 경우만 덮는다. 다른 도메인으로의 리다이렉트는 수만 보고한다.
- 이 계획을 검토한 것은 같은 모델 계열(Sonnet)이다. Codex 리뷰는 11/4 17:09 이후로 미룬다.

## 구현 기록 (2026-11-07)

검증은 성진의 지시로 `codex`가 아니라 `claude` 워커(Opus 5.5, read-only)로 했다. 다른 모델 계열의 리뷰는 없다.

| 단계 | PR | 계획과 다른 점 |
|---|---|---|
| 0b | #24 | 계획에 없던 단계. `aside --update`(1.26.1008 → 1.26.1107.24) 뒤 live 5개가 실패했다. 일회성 `aside repl`이 세션 폴더를 지워 문서 fetch가 전부 실패했고, 샌드박스 fetch가 YouTube를 거부했다. 문서는 base64로 받고, `auto`는 던져진 fetch 실패를 호스트당 한 번 탭으로 승격한다 |
| ① | #25 | 리뷰로 8월의 "Full output saved to: …]" 모양과 큰 거부 페이지도 읽게 했다 |
| ② | #26 | 복사 위치를 `artifacts/<세션>/downloads/`가 아니라 `downloads/<세션>/`로 했다. 에이전트의 `artifacts/downloads/`와 섞이지 않게 하려는 것이다 |
| ③ | #27 | 리뷰 3회. "선언된 UTF-8이면 개수를 보지 않는다" 규칙이 M11을 되살려 판정을 다시 설계했다. 지금 규칙: UTF-8 아닌 선언 + U+FFFD 하나, 또는 개수. 데이터는 선언만 본다. 본문 첫머리 정규식의 역추적 폭발을 고쳤다 |
| ④ | #28 | 리뷰로 두 이름의 중복 페이지, `--include`의 이름, crawl 매니페스트의 `not_crawled` 재크롤을 더했다 |
| ⑤ | #29 | 축약 옵션을 껐다. 옛 `--run`이 `--runs-dir`로 읽혔다. `test_real_sessions` live를 더했다. 리뷰가 워크트리의 `node_modules` 심볼릭 링크가 커밋에 들어간 것을 잡았다. 머지 전에 빼고 `.gitignore`를 고쳤다 |
| ⑥ | 이 PR | 본문 전문 승인(성진 11/7). 리뷰 반영: `ok` 줄은 `--help`와 중복이라 빼고, 사전 승인이 CLI만 덮는다는 사실을 넣었다. 리뷰 워커는 `skill-maker`를 불러올 수 없어(사용자만 호출 가능) 이 파일의 여섯 성질 표로 판단했다 |

대조 실험(Opus 5.5, `claude -p --setting-sources project --permission-mode default`, 가짜 Aside, 최종 본문, 각 3회):

| 과제 | 결과 |
|---|---|
| T1 알려진 URL | 3/3 `fetch` |
| T2 출처 선택 질문 | 3/3 목표를 담은 `search` |
| T3 느린 조사 | 3/3 `next`(`result --wait`)를 포그라운드(timeout 600000)로 실행해 같은 턴에 결과를 받았다. 본문에 맥락 규칙을 되살리지 않는다. 처음 설계(Python 버전)는 모델이 `fetch`를 골라 재지 못해 클라우드 비교 과제로 다시 쟀다 |
| T4 챌린지 | 3/3 읽은 것으로 인용하지 않음 |
| T7 30/60일 함정 | 3/3 열린 기록이 없는 인용을 알아채고 원문을 받아 60일 |
| T9 백엔드 호출 | 3/3 `aside guide repl`을 찾음. 이 하네스의 사전 승인이 `uv run`뿐이라 실행은 막혔다 |
| T5·T5b·T2poor 대체 | 9/9 WebSearch로 넘어가며 "검색 요약이고 원문을 열지 못했다"를 밝힘. 먼저 묻지는 않았다. 성진: "충분하다" |

가짜 환경의 영향: `.test` 도메인과 똑같은 답을 본 모델이 결과를 불신해 추가 검증을 했다. 한 번은 WebFetch 결과를 "원문을 직접 열어 확인"했다고 썼다.

남은 위험:
- uv가 스크립트 환경을 새로 만들 때 stderr에 쓰는 "Installed N packages" 한 줄이 백그라운드 출력 파일에서 JSON 앞에 올 수 있다(CLI 밖).
- 큰 문서의 base64가 Aside stdout 상한에 걸리는지 재지 않았다.
- 대조 실험은 합성 과제이고 과제당 3회다. 승인은 실사용 성능의 증거가 아니다.
