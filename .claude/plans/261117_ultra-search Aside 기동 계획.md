# ultra-search Aside 기동 계획

> 파일명: 계획 모드가 이 경로를 고정한다(`ExitPlanMode`가 이 파일만 읽는다). 구현 세션의 0단계에서 `261117_ultra-search Aside 기동 계획.md`로 바꾼다.

## Context

성진의 보고: Aside 브라우저가 꺼져 있으면 `ultra-search`가 아예 작동하지 않는다. 제안은 (1) 필요하면 브라우저를 실행하는 기능, (2) 켜짐·꺼짐을 점검하는 `doctor`.

목표로 읽은 것: Aside가 꺼져 있다는 이유로 스킬의 존재 이유(사용자 자신의 접근으로 확보한 원문에 근거한 답)가 조용히 무너지지 않는 것. 실행 기능과 doctor는 그 수단이다.

실측 결과 문제의 모양이 제안과 다르다.

- `doctor`는 이미 있다(`ultra_search/doctor.py`).
- 꺼진 Aside를 여는 기능은 `aside` CLI 자신이 갖고 있고 실제로 동작한다(A11). 스킬의 사전 점검 `aside.require_ready()`가 `aside`를 부르기 전에 종료 3으로 거부해서 그 기능이 한 번도 돌지 못했다(A10).
- 거부를 받은 모델은 사용자에게 알리지 않고 네이티브 `WebSearch`로 넘어갔다(A7, A18).
- 조사 중에 별개의 결함도 나왔다: Aside가 120초 스니펫 kill의 문구를 바꿔서, 지금 설치에서는 그 kill이 "Aside 불가(종료 3)"로 잘못 보고된다(A22). 성진이 정한 D6(업데이트 후 재검증)의 PR에 이 수정이 함께 들어간다.

그래서 이 작업은 재작성이 아니라 **거부하는 게이트를 켜서 진행하는 게이트로 바꾸는 수술**이다. 기동 지식(번들 id, 숨김, 동시 기동 조정, Windows 경로)은 Aside가 소유하므로 스킬에 복사하지 않고, `aside` CLI의 호출 하나가 켜게 둔다. 새 명령은 없고, SKILL.md에는 한 문장이 는다(D11).

PR은 넷이다(이유 하나에 하나): ① Aside 1.26.1115에 맞춤(120초 kill 판별, 검증 버전) → ② 꺼진 Aside를 켜서 진행 → ③ 릴리스 → (조사 결과에 따라) ④ 계정 점검.

## 합의 원장

성진이 정한 것:

| # | 결정 |
|---|---|
| D1 | 실측을 위해 Aside를 종료·재실행하는 것을 허락 |
| D2 | ultra-search는 사람이 없는 실행에서도 쓰인다. 방식은 두 가지: 대화 세션이 띄운 작업자, `claude` 스킬의 예약 작업자(이 Mac의 GitHub Actions 러너) |
| D3 | Aside를 끝내 못 켰을 때 무엇을 할지(멈춤, 네이티브 도구 대체)는 **스킬이 정하지 않는다.** 오류는 사실만 말하고 판단은 그때의 모델에게 둔다 |
| D4 | `doctor`는 꺼진 Aside를 만나면 명령과 똑같이 켜서 끝까지 점검한다. 못 켜면 Aside가 말한 이유를 보고한다 |
| D5 | 스킬이 켠 Aside는 닫지 않고 켜 둔다 |
| D6 | 구현 세션은 먼저 `aside update` → live 재검증 → `VERIFIED_*` 갱신을 별도 PR로 머지하고, 그 위에서 이 작업을 한다 |
| D7 | 콜드 검증은 `pytest -m cold`로만 도는 별도 마커 테스트로 남긴다(기본 실행과 `-m live`에서는 절대 돌지 않는다). 실행하면 Aside를 여러 번 끄고 켠다 |
| D8 | 못 켰을 때의 오류 메시지는 Aside가 한 말을 그대로 인용한다. Aside 쪽 권고(예: "Don't switch to another browser")가 섞여 보여도 그것은 Aside의 말이다 |
| D9 | "켰다"는 사실은 stderr로만 알린다. 응답 JSON에 필드를 더하지 않는다 |
| D10 | 계정 점검(A20)은 구현 세션에서 뜻을 실측하고, 점검이 실제로 틀렸을 때만 별도 PR로 고친다 |
| D11 | D3를 좁힌다: 대체할지 멈출지는 여전히 스킬이 정하지 않지만, **말없이 넘어가는 것은 막는다.** SKILL.md 마지막 항목에 한 문장을 더한다(아래 "SKILL.md" 절의 전문). skill-maker의 두 조항(무인 실행이 알려진 스킬은 미리 정한다 / 사실을 받은 모델이 눈에 안 띄게 틀린 것이 관찰되면 그 이유만큼만 센 행동 줄)을 따른 것이고, 관찰은 A7·A18·A25다 |

내가 정한 것(관례·코드·측정으로 정해지는 것, 반대하면 바꾼다):

| # | 결정 | 근거 |
|---|---|---|
| E1 | 스킬은 자체 런처(`open -g -b …`)를 갖지 않는다. 데몬이 답하지 않으면 `aside repl` 왕복 한 번을 부르고, 켜는 일은 그 안에서 CLI가 한다 | A3, A11, A13. 번들 id·숨김·동시 기동 claim·Windows 경로는 Aside 소유라 복사하면 두 벌이 된다. REPL 왕복은 "데몬이 답한다"가 아니라 "브라우저가 스니펫을 돌린다"까지 확인한다 |
| E2 | 데몬이 ready라고 답하는 평소 경로는 그대로다: 로컬 health GET 한 번, `aside` 추가 호출 없음. **절충이다:** health가 ready여도 브라우저 브리지가 죽어 있는 상태는 지금처럼 일을 시작한 뒤에야 드러난다. 이를 일 전에 잡으려면 매 명령 0.7초의 왕복이 든다. 기존 동작이고 이번 보고의 원인이 아니라 바꾸지 않는다 | codex 지적 2. 켜져 있을 때 매 명령에 0.7초를 더할 근거(실제 사고)가 없다 |
| E3 | 게이트는 지우지 않고 바꾼다. `search`·`resume`·`fetch`·`map`·`crawl`의 같은 다섯 자리에서 일하기 전에 부른다 | 지우기만 하면 (a) `search`가 못 켠 실패를 `result`까지 미루고 런을 예약하며 (b) CLI의 기동 안내 줄이 `stdout.log`에 섞여 stdout 폴백 답에 들어가고 (c) 켜진 직후의 탭 실패(A15)를 스킬이 모른 채 "페이지 실패"로 보고한다 |
| E4 | `open_tab`은 `CDP session detached` 오류 레코드를 한 번 다시 시도한다. 데몬 나이 같은 조건은 달지 않는다 | A15, A21. 결과만 봐서는 "페이지를 못 읽음"과 구별되지 않는 조용한 실패. 나이 조건은 시계·경계 의존을 더할 뿐이고 오래 켜진 Aside에서도 같은 일시 오류는 다시 하면 된다(codex 지적 7). 대가: 그 URL에 탐색이 두 번 갈 수 있다 |
| E5 | `ensure_ready()`는 관찰한 것을 돌려준다: 처음에 데몬이 답하지 않았고 그 뒤 REPL 왕복이 성공했는지(bool). 스킬이 쓰는 문구는 관찰만 말한다: "the daemon did not answer", "`aside repl` failed". "꺼져 있었다", "켰다", "did not start"라고 쓰지 않는다. 켜졌다는 말은 Aside 자신의 stderr를 그대로 내보내는 것으로 대신한다 | codex 지적 4와 재검토 (b). health 실패만으로 꺼져 있었다고, 왕복 성공만으로 우리가 켰다고 단정할 수 없다(뜨는 중이었거나 다른 프로세스가 켰을 수 있다) |
| E6 | 120초 kill은 Aside가 말하는 **원인**으로 가른다. 스니펫을 돌리는 `aside repl`에 `ASIDE_DEBUG=1`을 주면 오류에 원인이 붙고, kill은 `other side closed`다(A23). 그 원인이면 `ReplTimeout`, 아니면 `AsideUnavailable` | A22: 기본 문구는 kill과 다른 연결 실패가 같다. `ASIDE_DEBUG`는 CLI가 `--help`에 적어 둔 인터페이스이고 그 요청이 왜 끝났는지를 직접 말한다. 경과 시간이나 직후의 health로 추정하는 것보다 증거가 직접적이고, 테스트용 상한 override도 필요 없다(codex 지적 1과 재검토 (a)가 가리킨 문제의 원인 쪽 해법). 남는 한계: 스니펫 도중 Aside가 죽어도 같은 원인일 수 있다. 그때도 "저쪽이 끊었다"는 사실은 맞다 |
| E7 | 준비시키기에 실패했을 때의 `fix`는 "Open the Aside app"이 아니라 `doctor`만 가리킨다(초안: ``Run `doctor`: it reports each part of the environment on its own.``). 다른 `AsideUnavailable`의 기본 `fix`는 건드리지 않는다 | 이미 열어 보려다 실패한 뒤라 "앱을 열어라"는 사실에 안 맞을 수 있다(원격 URL, 브리지 실패). 무엇이 필요한지는 인용한 Aside의 말이 갖고 있다(D8). `fix`는 대체 수단을 고르는 것이 아니라 D3와 부딪히지 않는다(재검토 (e)) |
| E8 | SKILL.md에 더하는 것은 D11의 한 문장뿐이다. 켠다는 사실, 종료 3의 뜻, 콜드 직후 탭 실패는 본문에 쓰지 않는다 | 아래 "SKILL.md" 절 |
| E9 | 테스트 seam은 기존 것만 쓴다: 가짜 `aside` + health 대역을 둔 CLI 프로토콜, 구조 테스트, 실제 Aside의 live, 그리고 같은 종류인 cold. 가짜는 **분기**를 증명하고(데몬 무응답 뒤 왕복 결과에 따라 갈린다), **실제로 켜진다**는 것은 cold만 증명한다 | 261103 계획의 seam. codex 지적 5 |

## 실측 원장 (2026-11-17, CLI 1.26.1107.24 · 앱 1.0.1116.2 · 데몬 1.26.1115.1556)

| # | 사실 | 근거 |
|---|---|---|
| A1 | 설치: CLI `~/.aside/cli/Aside CLI.app`, 앱 `/Applications/Aside.app`(bundle id `at.studio.AsideBrowser`). `VERIFIED_DAEMON_VERSION`은 1.26.1107.24라 `doctor`가 note를 낸다. CLI는 `aside update`(1.26.1115.1556)를 권한다 | `aside --version`, `Info.plist`, health, `aside guide` |
| A2 | 데몬은 앱 번들 안의 별도 프로세스(ppid 1, runningboard가 띄움). 로그인 시 자동 기동하는 LaunchAgent는 없다(업데이터 wake뿐) | `ps`, `launchctl print`, `~/Library/LaunchAgents` |
| A3 | `aside` CLI 내장 소스: 데몬 요청이 `ECONNREFUSED`면 `/usr/bin/open -g -b at.studio.AsideBrowser`로 열고, 창이 뜨면 숨기고, `/health`가 `ready:true`가 될 때까지 0.5초 간격으로 최대 60초 기다린 뒤 같은 요청을 다시 보낸다. 준비 뒤 45초 동안 `bridge-unreachable`·`no-profile`·`no-normal-window`를 1초 간격으로 재시도한다. 동시 기동은 `$TMPDIR/aside-cli-open-claims`로 하나만 연다 | 바이너리 `strings` |
| A4 | 자동 기동은 `exec`·`repl`·`mcp`·`session resume`에 걸린다. `DAEMON_BASE_URL`이 기본값이 아니거나, 원격 호스트 + `aside login` 상태면 열지 않는다 | 같은 곳 |
| A5 | 스킬의 `require_ready()`(`aside/daemon.py:53`)는 `search`·`resume`·`fetch`·`map`·`crawl` 다섯 곳에서 불리고, 데몬이 답하지 않으면 `aside`를 부르지 않고 종료 3으로 끝난다 | 코드 |
| A6 | 그 게이트의 근거 M13은 가짜 Aside로 잰 것이다. 실제 CLI가 꺼진 앱 앞에서 무엇을 하는지는 잰 적이 없었다 | `261103` 계획 M13 |
| A7 | 실제 사고: 2026-11-09 Agentic-Invest 세션에서 `fetch` 2회가 종료 3을 받자 2초 뒤 `ToolSearch select:WebSearch,WebFetch` → `WebSearch` 2회. 사용자에게 알리거나 묻지 않았다 | 전사 3654–3683 |
| A9 | 앱을 끄면 데몬도 3초 안에 같이 죽고 health는 `ECONNREFUSED`. "꺼짐"은 한 가지 상태다 | quit 후 1초 간격 관찰 |
| A10 | 꺼진 상태에서 스킬은 `aside`를 부르지 않는다. `doctor`: `aside daemon` 실패(REPL·계정 점검은 건너뜀). `fetch`: 0.09초 만에 종료 3. 앱은 여전히 꺼져 있다 | 실행 |
| A11 | **꺼진 상태에서 `aside`는 스스로 연다.** `aside account list` 3.47초·종료 0, `aside repl` 4.94초·종료 0·stdout 그대로, stderr 첫 줄 `Aside isn't running. Opening it in the background...`. 맨 앞 앱은 그대로(포커스 안 뺏음), 탭 3개 복원 | quit → 실행 |
| A12 | **게이트만 건너뛰면 스킬 경로가 된다.** 꺼진 상태에서 `aside.fetch_pages(["https://example.com"])`: 4.49초, `status 200`. 3회 중 3회 | quit → python 호출 |
| A13 | 꺼진 상태에서 `aside repl` 두 개 동시: 하나는 `Opening it in the background...`, 하나는 `Waiting for Aside to finish starting...`, 둘 다 3.4초·종료 0, 앱 프로세스 1개 | quit → 병렬 |
| A14 | **열 수 없는 경우의 문구는 원인에 따라 둘이다.** 기본이 아닌 `DAEMON_BASE_URL`이 평범한 닫힌 포트(연결 거부)면 0.22초 뒤 종료 1, stdout 없음, stderr `Error: Aside isn't running on this machine. Ask the user to open Aside, then retry the same command. Don't switch to another browser: only Aside has the user's logged-in sessions.` + 원격 호스트 안내 한 줄. 거부가 아닌 연결 실패(막힌 포트 9번)면 1.8초 뒤 `Error: Could not connect to Aside at http://127.0.0.1:9. Check the browser and local network permissions.` + 같은 안내. 기본 URL에서 `open` 자체가 실패할 때의 문구(`…and the CLI couldn't open it (…). Aside may not be installed.`)와 60초 안에 안 떴을 때의 문구(`Aside didn't finish starting within 60s …`)는 **실행으로 본 적이 없고 CLI 소스에서 읽은 것**이다 | 실행, `strings` |
| A15 | **콜드 스타트 직후의 실제 탭 열기는 가끔 실패한다.** `aside.open_tab`이 `kind:error`, `error:"CDP session detached: …"`. 콜드 뒤 첫 탭 22회 중 4회(REPL 왕복을 먼저 성공시킨 13회 중 2회 포함). 실패는 모두 데몬 기동 후 약 10초 안이고, 켜져 있을 때는 0회 | quit → 반복 |
| A16 | 기동 시간은 3.4~18.9초(부하 평균 57일 때 18.9초). CLI 자신의 상한은 60초 + 45초. 스킬 `repl_probe`의 subprocess 제한은 60초 | 같은 측정 |
| A17 | 자동으로 열린 앱은 숨김(`hidden:true`)으로 뜬다. 탭을 열면 창이 보이게 되지만(`hidden:false`) 활성 앱은 바뀌지 않는다 | `NSRunningApplication` 관찰 |
| A18 | A7의 세션은 사고 9초 전에 SKILL.md 본문(네이티브 도구는 사용자의 접근을 못 쓴다는 줄 포함)을 로드한 상태였다 | 전사 3620 |
| A19 | 가짜 Aside의 `aside_down`·`repl_timeout`은 `Aside daemon is not reachable`을 찍는다. 현재 CLI 바이너리에는 이 문구가 없다 | `tests/fake_aside/aside:288,393`, `strings` |
| A20 | `doctor`의 계정 점검은 `aside account list`의 줄이 `u0`로 시작하면 통과한다. 현재 출력은 두 계정 모두 `signed out`인데 통과. `--json`에는 `authStatus:"active"`, `hasSession:false`가 따로 있다. `signed out`의 뜻은 재지 않았다 | `aside account list`, `--json` |
| A21 | A15의 실패 직후 같은 호출을 바로 다시 하면 성공한다(1회 중 1회, 데몬 기동 3.0초 → 6.3초) | 콜드 9회차 |
| A22 | **120초 스니펫 kill의 문구가 바뀌어 있다.** `aside repl 'await new Promise(r => setTimeout(r, 130000))'`: 120.49초 뒤 종료 1, stderr는 `Error: Could not connect to Aside at http://127.0.0.1:21420. Check the browser and local network permissions.`(A14의 "거부가 아닌 연결 실패"와 같은 문구). 데몬은 멀쩡하다. `repl.py`의 `_TIMEOUT_SIGNS`(`other side closed`, `daemon is not reachable`, `fetch failed`) 어느 것과도 안 맞아, 지금 설치에서는 kill이 `ReplTimeout`이 아니라 `AsideUnavailable`(종료 3)로 보고된다 | 실행 |
| A23 | **`ASIDE_DEBUG=1`이 원인을 붙인다.** `aside --help`가 적어 둔 환경변수(`1 adds raw causes to errors`). 같은 kill에 `Details: fetch failed: other side closed`(120.23초), 막힌 포트에 `Details: Failed to request daemon auth challenge: fetch failed: bad port`가 붙고 그 뒤에 스택이 길게 이어진다. 성공한 호출의 출력은 그대로다. `fetch failed`는 두 경우에 다 나오므로 kill의 표지는 `other side closed`뿐이다 | 실행 |
| A24 | kill된 스니펫이 그 전에 `console.log`한 것은 stdout에 나오지 않는다(`{"part":1}`을 찍고 130초 기다린 스니펫: stdout 비어 있음). `run_code`의 "부분 출력이 살아남는다"는 지금 CLI에서는 성립하지 않고, 스니펫이 제 예산(105초) 안에 끝내는 것이 유일한 방어다 | 실행 |
| A25 | A7의 세션은 그 뒤 400여 레코드(전사 3684–4100) 동안 Aside·WebSearch·대체를 성진에게 한 번도 말하지 않았다. 261103 계획의 대조 실험(단일 응답, 최종 본문)에서는 9/9가 넘어가면서 "검색 요약이고 원문을 열지 못했다"고 밝혔었다. 긴 작업의 중간 단계에서는 그 사실 줄만으로 밝히지 않았다 | 전사, `261103` 계획 구현 기록 |

미실측: `aside exec`의 콜드 스타트(구독을 쓰므로 재지 않음, 같은 `createDaemonClient` 경로), 앱은 떠 있고 데몬만 죽은 상태(`Waiting for Aside to restart...`), 화면 세션이 없는 실행에서의 `open` 실패 문구, 예약 작업자(러너) 안에서의 기동, 재부팅 직후의 기동 시간, 콜드 직후 로그인 필요한 페이지의 내용, CLI 1.26.1115에서의 A11·A14·A22·A23·A24.

## skill-maker 프레임 대응

| 성질 | 이 변경에서 |
|---|---|
| Principle over rail | 금지·절차·대안 목록 없음. 행동 줄은 D11의 한 문장뿐이고, 사실을 받은 모델이 사람 눈에 안 띄게 틀린 관찰(A7·A18·A25)과 이유가 붙어 있으며, 관찰된 잘못(침묵)보다 세지 않다(대체 자체는 막지 않는다) |
| Interface over document | 켠다는 부작용과 종료 3의 뜻은 각 명령의 `--help`와 오류 메시지가 갖는다. SKILL.md 사본 없음 |
| Model over machinery | 새 명령 없음. 고친 것은 이미 자격이 있는 명령들의 선행 조건이다. 모델 자신의 도구로는 못 한다: `open`은 `allowed-tools` 패턴 밖이라 승인 프롬프트에서 멈추고(무인 실행에서는 막힘), 번들 id를 모르며, 실제로는 켜는 대신 네이티브 도구로 넘어갔다(A7). 탭 재시도(E4)는 프레임의 "조용한 실패만으로는 래퍼의 자격이 없다"에 걸리는 판단이다: 결과에 `error`와 `CDP session detached`가 보이긴 한다. 그래도 넣는 이유는, 그 실패가 이 명령이 방금 Aside를 켠 데서 생긴 것이라는 사실은 결과에 없고, 매번 같은 호출 한 번으로 풀리며, `crawl`에서는 그 페이지가 조용히 `ok` 밖으로 빠지기 때문이다. help에 우회법을 한 줄 가르치는 쪽이 더 나쁜 사본이다 |
| For the model, not the maintainer | 실측 수치·사고 경위는 이 계획과 커밋에. 코드 주석에는 다음 결정을 바꾸는 이유만 |
| Dense | help에 한 문장(공유 상수), README 한 항목. help에는 Aside가 소유한 값(초, 숨김, 탭 복원)을 쓰지 않고 그것이 일으키는 일만 쓴다 |
| Colleague over autopilot | 사용자의 브라우저를 켜는 것은 성진이 요청한 것(D5). 못 켰을 때의 선택은 그때의 사람·모델 몫(D3). 결과가 보여 주지 않는 것(어떤 도구로 얻은 답인지)을 본문이 이름으로 말한다(D11). 무인 실행에서는 그 표시가 미리 정해 둔 동작이다 |

## 보존할 행동 (바꾸기 전에 기존 테스트가 지킴, 없으면 먼저 고정)

- `aside` 바이너리가 없으면 종료 3, 런을 예약하지 않는다(`test_a_missing_aside_binary_exits_three_before_reserving_a_run`, live `test_a_missing_binary_fails_fast_rather_than_hanging`).
- 스킬이 확인하는 데몬은 `aside`가 쓸 그 데몬이다(`test_the_daemon_checked_is_the_one_aside_exec_uses`). 이 계약을 지키려고 가짜가 A14를 따라 `DAEMON_BASE_URL`이 가리키는 곳에 닿지 못하면 A14의 연결 거부 문구(`Aside isn't running on this machine…`)로 종료 1 하게 한다. 테스트의 unhealthy 쪽을 `aside_down` 시나리오로 바꿔치우면 이 계약이 사라지므로 그렇게 하지 않는다.
- 못 켜면 `search`·`resume`은 런을 예약하지 않고 `exec`를 부르지 않는다. `fetch`·`map`·`crawl`은 스니펫을 부르지 않고 파일을 만들지 않는다(기존 테스트의 두 번째 `--out` 호출과 파일 미생성 단언 유지).
- `resume`은 세션 존재·busy 검사를 먼저 하고 그다음 준비시킨다(순서 유지).
- 모든 응답은 stdout의 JSON 문서 하나. 기동 안내는 stderr.
- 데몬이 ready일 때 명령은 왕복용 `aside` 호출을 더하지 않는다(E2). 지키는 테스트가 없으니 먼저 고정한다.
- 120초 kill은 "Aside 불가"가 아니라 `ReplTimeout`으로 옮겨져, 호출자가 예산 소진(`hit_budget`)으로 보고한다(PR 1이 A22에 맞춰 되살린다).

## 변경 상세

### PR 1 `fix: Aside 1.26.1115의 120초 kill을 다시 알아보게`

- `aside update` 뒤 새 CLI에서 A11·A14·A22·A23·A24를 다시 잰다(Aside를 끄는 측정 포함).
- `aside/repl.py::run_code`: `aside repl`을 `ASIDE_DEBUG=1`을 더한 환경으로 부르고, 종료 코드가 0이 아닐 때의 분류를 E6대로.
  - 출력에 `other side closed`가 있으면 `ReplTimeout(lines)`.
  - 그 밖은 지금처럼 `AsideUnavailable`. 인용은 스택이 아니라 `Details:` 줄까지만(Aside의 첫 문단 + 원인 한 줄).
  - `_TIMEOUT_SIGNS`에서 `fetch failed`를 뺀다(A23: 막힌 포트에도 나온다). `daemon is not reachable`은 1.26.1115에서 다시 재서 안 나오면 지운다.
  - `repl_probe`는 `ASIDE_DEBUG` 없이 부른다: 실패 문구를 사람에게 인용하는 호출이라 Aside의 말만 있으면 된다.
- docstring의 "부분 출력이 살아남는다"를 A24에 맞게 고친다(1.26.1115에서도 같으면).
- `tests/fake_aside/aside`: `repl_timeout`과 routes의 `__timeout__`은 A22·A23의 stderr(기본 두 줄 + `Details: fetch failed: other side closed`)를, `aside_down`은 A14의 연결 거부 문구를 찍는다(모두 종료 1). `DAEMON_BASE_URL`이 가리키는 곳에 TCP로 닿지 못하면 A14의 연결 거부 문구로 답한다(TCP 도달만 본다. HTTP health나 CLI의 프로토콜을 흉내 내는 것은 아니다). kill 뒤에 부분 레코드를 찍는 가짜의 동작은 A24를 다시 잰 결과에 맞춘다.
- `tests/conftest.py::no_real_aside`: 개발자 셸에서 물려받은 `DAEMON_BASE_URL`을 지운다. 지금은 `ULTRA_SEARCH_DAEMON_URL`만 덮어서, 가짜가 `DAEMON_BASE_URL`을 따르게 되면 스킬과 가짜가 서로 다른 주소를 보게 된다. 그 변수를 쓰는 테스트만 다시 설정한다.
- 재현 테스트 먼저(갈래 각각): kill의 stderr → `hit_budget`으로 보고되고 종료 3이 아니다; 연결 거부 문구 → 종료 3에 그 문구; 원인이 다른 연결 실패(`bad port`) → 종료 3. `aside repl`이 `ASIDE_DEBUG=1`로 불렸다는 것은 가짜의 `calls.jsonl`이 환경을 기록하게 해서 단언한다.
- `pytest -m live` 전체 → `VERIFIED_VERSION`·`VERIFIED_DAEMON_VERSION` 갱신.

### PR 2 `fix: 꺼진 Aside를 켜서 진행`

#### ① `aside/`: 준비를 확인하는 대신 준비시킨다

- `aside/daemon.py`: `require_ready()` → `ensure_ready() -> bool`.
  1. `aside_bin()` (없으면 지금처럼 `AsideUnavailable`).
  2. `daemon_status()`가 ok면 `False`.
  3. 아니면 `repl_probe(timeout=START_LIMIT)`. 꺼져 있거나 아직 뜨는 중이면 CLI가 이 호출 안에서 열고 기다린다.
  4. 왕복이 성공하면 그 호출 동안 **Aside가 stderr에 한 말을 그대로** stderr로 내보내고(A11의 `Aside isn't running. Opening it in the background...`, A13의 `Waiting for Aside to finish starting...`) `True`. 스킬의 문장은 붙이지 않는다: 무슨 일이 있었는지는 Aside만 안다(E5). health를 다시 묻지 않는다: 왕복이 더 강한 증거다. 지금 패키지에는 stderr에 쓰는 코드가 없으므로 이것이 첫 진행 줄이다. `cli.py`의 docstring이 이미 "progress and diagnostics go to stderr"라고 말한다.
  5. 실패하면 `AsideUnavailable`, `fix`는 E7. Aside가 무언가 말했으면 ``the Aside daemon did not answer and `aside repl` failed: <Aside의 말>``, 스킬 쪽 시간 초과면 ``…and `aside repl` gave no answer in <N> s``로 **둘을 구별한다**.
  - docstring은 왜 일하기 전에 하는지(E3)를 남긴다.
- `aside/repl.py::repl_probe(timeout: float = 60)`:
  - `START_LIMIT = 120.0`은 CLI 자신의 두 상한(60초 + 45초)을 넘겨, 못 켜는 이유를 CLI가 제 입으로 말하게 하는 값이다.
  - 실패 detail은 stderr를 잃지 않는다(지금은 stdout이 있으면 stderr를 버린다). 400자.
  - `(False, detail)`과 예외(`AsideUnavailable`) 두 실패 경로는 그대로 두고 `ensure_ready`가 둘 다 받는다.
- `aside/browser.py::open_tab`: 요청한 URL의 레코드가 `kind:error`이고 `error`가 `CDP session detached`로 시작할 때만 같은 호출을 한 번 더 한다. 성공·다른 오류·시간 초과는 다시 하지 않는다. 두 번째도 같으면 그 레코드를 그대로 돌려준다. 첫 시도가 남긴 다른 레코드(정리 경고)는 버리지 않는다.
- `aside/__init__.py`: 내보내는 이름 `require_ready` → `ensure_ready`.
- 호출부 다섯 곳 이름 교체: `research/commands.py:325,363`, `fetch/commands.py:19`, `site/commands.py:41,94`. 반환값은 `doctor`만 쓴다.

#### ② `doctor`: 꺼져 있으면 켜서 끝까지 (D4)

- `doctor.py`: 바이너리가 있으면 데몬 점검 전에 `aside.ensure_ready()`를 부르고 `AsideUnavailable`을 잡는다.
  - `False`(원래 답하고 있었음): 지금과 같은 출력.
  - `True`: 데몬 점검은 지금처럼 `daemon_status()`로 다시 읽어 판정하고(왕복이 됐는데도 health가 답하지 않으면 그 사실대로 실패), ok면 note에 ``the daemon did not answer when this check began; the `aside repl` round trip that followed succeeded, as it would for any command``. 버전 불일치 note가 있으면 둘 다 남는다. 이어서 REPL·계정 점검이 지금처럼 돈다.
  - 예외: `aside daemon` 점검 실패, `detail`은 예외의 메시지(Aside의 말 또는 시간 초과), `fix`는 ``Open the Aside app by hand, then re-run `doctor`.``(명령은 `doctor`를 가리키고, `doctor`는 손으로 열어 보라고 한다: CLI가 못 여는 것과 앱이 안 열리는 것을 가른다), 종료 3. REPL·계정 점검은 지금처럼 건너뛴다.
- 모듈 docstring의 "Aside is closed"를 "Aside could not be started"로.

#### ③ `cli.py`와 `outcome.py`: 인터페이스가 부작용과 뜻을 말한다

- 공유 상수 하나를 `search`·`resume`·`fetch`·`map`·`crawl`·`doctor`의 description에 붙인다. 초안: ``When the Aside daemon does not answer, `aside` is run first: it starts Aside when it is closed and waits for it, so this command takes longer than usual, and Aside is left running.`` 몇 초가 걸리는지, 숨김으로 뜨는지, 탭이 복원되는지는 Aside가 소유한 값이라 쓰지 않는다(바뀌면 help가 거짓이 된다). 그 값들이 일으키는 일(이 명령이 평소보다 오래 걸린다, Aside가 켜진 채 남는다)만 쓴다.
- `_NO_ASIDE`(종료 3 전체를 덮어야 한다): `the aside binary is missing, or Aside could not be reached or started; the reply says which, in Aside's own words where it gave any`.
- `outcome.AsideUnavailable` docstring을 같은 뜻으로. 기본 `fix`는 그대로, 준비 실패의 `fix`만 E7.
- `--help`는 argparse `RawTextHelpFormatter`라 소스의 줄이 그대로 나온다. 고친 뒤 여섯 명령의 `--help`를 실행해 확인한다.

#### ④ 테스트

가짜로 하는 것(분기의 증명). 새 테스트는 모두 `fake_aside` fixture를 명시한다: 자동 fixture `no_real_aside`의 기본은 "ready health + 없는 바이너리"다.

- 대역 조합: 닫힌 health + 가짜의 왕복 성공 = "데몬이 답하지 않았고 왕복 뒤 진행". 닫힌 health + `aside_down` = "못 켠다". 이름도 그렇게 붙인다(실제 기동의 증명이 아니다).
- 바뀌는 테스트(단언을 약하게 하지 않고 뜻을 옮긴다. 옛 단언 → 새 자리를 커밋 메시지에 적는다):
  - `test_pages.py::test_a_daemon_that_does_not_answer_is_said_before_any_work` → `aside_down`에서: 종료 3, `aside_unavailable`, 메시지에 A14의 연결 거부 문구, `calls.jsonl`에 스니펫 호출 없음(왕복 호출만), 파일 미생성.
  - `test_research.py::test_a_daemon_that_does_not_answer_exits_three_before_reserving_a_run` → 같은 식, 런 미예약·`exec` 호출 없음.
  - `test_environment.py::test_a_closed_daemon_fails_doctor`, `test_a_daemon_that_is_up_but_not_ready_fails_doctor` → `aside_down`에서의 실패로.
- 새 테스트(각각 먼저 빨갛게, 행동이 없어서 실패하는 것을 본다):
  - 무응답 뒤 왕복 성공: `fetch`·`map`·`crawl`·`search`가 일을 하고 종료 0, 가짜가 왕복 중 stderr에 찍은 줄이 그대로 stderr에 나오고, stdout은 JSON 하나. `search`는 감독자가 낸 결과까지 본다(`result --wait`가 `completed`).
  - `resume`: 유효한 가짜 세션으로 같은 경우 성공. 없는 세션은 준비시키기 전에 지금처럼 거부(왕복 호출 없음).
  - ready일 때 왕복 호출이 없다(보존 고정, 변경 전에 초록).
  - `doctor`: `True`의 note가 버전 note와 함께 남고 REPL·계정 점검까지 돈다. 이 경우를 가짜로 만들려면 health 대역이 처음에는 not-ready, 그다음부터 ready로 답해야 한다(`test_environment.py`의 `daemon` fixture에 순서를 준다). 닫힌 포트로는 왕복 뒤에도 health가 닫혀 있어 만들 수 없다. `(False, detail)` 실패와 예외 실패가 각각 실패한 점검으로 나온다.
  - 스킬 쪽 시간 초과와 Aside의 말이 메시지에서 구별된다.
  - `fetch --via tab`: 첫 레코드 `CDP session detached`, 둘째 정상(가짜 routes의 `sequence`) → `ok`, 호출 2번. 둘 다 detached → 그 오류 그대로, 호출 정확히 2번. 다른 오류·성공 → 호출 1번.
  - 여섯 명령의 `--help`가 켠다는 사실을 말한다.
- 기대값의 출처: 오류 문구는 A14·A22·A23의 실측 stderr, detached 문구는 A15의 실측 레코드. help 문장과 note는 실측이 아니라 이 계획이 정한 계약이므로, 테스트는 문장 전체가 아니라 계약의 요점(Aside를 시작한다, 켜 둔다)을 본다.

실제 Aside로 하는 것(D7). `tests/live/test_cold.py`, 마커 `cold`(`pytest.ini`에 등록). macOS가 아니면 건너뛴다. 각 테스트는 Aside를 끄고 시작하고, 끝나면 켜 둔다.

격리(사용자의 브라우저를 끄는 테스트라 따로 보장한다): cold 항목은 `-m` 식이 `cold`를 고를 때만 돈다. 기본 실행, `-m live`, `-m "not cold"`에서는 절대 돌지 않고, `-m "live or cold"`처럼 명시한 때만 돈다. `conftest.py`의 지금 로직은 `-m` 문자열에 `live`가 들어 있는지만 보므로 그대로 베끼지 않는다: "이 식에서 cold가 도는가"를 정하는 함수를 따로 두고, Aside를 끄는 단 하나의 도우미가 그 함수가 참일 때만 끄게 한다. 그 함수는 위 네 식으로 가짜 스위트에서 시험한다(실제로 끄지 않고). `no_real_aside`는 cold 항목을 live처럼 제외한다.

| 테스트 | 기대 |
|---|---|
| 꺼짐 → `fetch` 공개 페이지 | 종료 0, `ok`, stderr에 Aside의 기동 안내 줄, 끝난 뒤 앱 프로세스가 있다 |
| 꺼짐 → `fetch` 로그인 필요 페이지(live `test_a_login_gated_feed_is_readable`와 같은 URL·같은 내용 단언) | 로그인해야 보이는 내용이 저장된다 |
| 꺼짐 → `fetch --via tab`, 20회 | 20회 모두 `ok` |
| 꺼짐 → `map` | 종료 0, URL이 있다 |
| 꺼짐 → `doctor` | 종료 0, `aside daemon`에 note, REPL·계정 점검 포함 |
| 꺼짐 → `fetch` 둘을 동시에 | 둘 다 `ok`, 앱 프로세스 1개 |
| 꺼짐 → `search --effort low` → `result --wait` (구독 사용) | `completed`, 답과 출처, `stdout.log`에 기동 안내 줄 없음 |
| 켜짐 → `DAEMON_BASE_URL`을 방금 잡았다 놓은 닫힌 포트로 두고 `fetch`·`search`·`doctor` | 종료 3, 메시지에 `Aside isn't running on this machine`, `search`는 런 미예약 |

#### ⑤ 문서

- SKILL.md: 마지막 항목에 한 문장(D11, 아래 전문).
- README.md(한국어, 기존 섹션 그대로):
  - `## 설치` 전제 문장: "실행 중이고 계정이 로그인된 Aside 앱" → "설치되어 있고 계정이 로그인된 Aside 앱(꺼져 있으면 스킬이 켠다)".
  - `## 알아둘 것`의 "네이티브 툴은 같은 일을 하지 못한다" 항목 끝 문장을 고친다: "실패했을 때 어떻게 할지는 스킬 본문이 정하지 않는다" → 대체할지는 정하지 않지만, 다른 도구로 이어 갔으면 답에 그렇다고 쓰게 한다.
  - `## 알아둘 것` 새 항목 하나: **꺼져 있으면 켠다.** 숨김 상태로, 탭을 복원해서, 켠 뒤에는 닫지 않는다(2026-11 macOS에서 잰 것). 켜는 것은 `aside` CLI다. 못 켜면 종료 3과 Aside가 한 말이 나온다. 화면 세션 밖(ssh 등)에서는 켜지 못한다. 예약 작업자에 대해서는 7단계에서 잰 결과를 그대로 적는다(된다 / 안 된다 / 재지 못했다).
  - `## 개발`: 테스트 개수 갱신, `-m cold` 한 줄(Aside를 끄고 켠다, 그중 하나는 구독을 쓴다), "Aside를 업데이트한 뒤에는" 문단에 `-m cold` 추가.
  - `## 구조`: 변경 없음.

### PR 3 `chore(release): v3.1.0`

`ultra_search/__init__.py`의 `__version__`, `tests/test_environment.py`의 버전 단언(v3.0.0 릴리스 PR #31과 같은 두 파일).

### PR 4 (조건부) 계정 점검 (D10)

구현 세션에서 `aside account list`의 `signed out`, `--json`의 `authStatus`·`hasSession`이 각각 무엇을 뜻하는지 잰다(Aside 앱에서 계정을 로그아웃한 상태와 비교해야 하므로 성진에게 그 조작을 부탁한다). 로그아웃된 브라우저를 `doctor`가 통과시키면 재현 테스트와 함께 별도 PR로 고친다. 아니면 측정 결과만 이 계획의 구현 기록에 남긴다.

## 구현 후 트리

파일 이동·삭제 없음. 새 파일은 `tests/live/test_cold.py` 하나.

```
.claude/skills/ultra-search/
├── SKILL.md                         # 마지막 항목에 한 문장                   (PR 2)
└── scripts/
    ├── cli.py                       # help 상수, _NO_ASIDE                    (PR 2)
    └── ultra_search/
        ├── __init__.py              # __version__                             (PR 3)
        ├── doctor.py                # 켜서 점검                               (PR 2)
        ├── outcome.py               # docstring                               (PR 2)
        ├── aside/
        │   ├── __init__.py          # ensure_ready                            (PR 2)
        │   ├── daemon.py            # require_ready → ensure_ready            (PR 2)
        │   ├── repl.py              # ASIDE_DEBUG로 kill 판별(PR 1) · repl_probe(timeout), START_LIMIT (PR 2)
        │   ├── browser.py           # open_tab 재시도                         (PR 2)
        │   └── process.py           # VERIFIED_*                              (PR 1)
        ├── research/commands.py     # 호출 이름                               (PR 2)
        ├── fetch/commands.py        # 호출 이름                               (PR 2)
        └── site/commands.py         # 호출 이름                               (PR 2)
tests/
├── fake_aside/aside                 # 현재 문구, DAEMON_BASE_URL              (PR 1)
├── conftest.py                      # DAEMON_BASE_URL 지움(PR 1) · cold 격리(PR 2)
├── ../pytest.ini                    # cold 마커                               (PR 2)
├── test_pages.py · test_research.py · test_environment.py
└── live/test_cold.py                # 새 파일                                 (PR 2)
README.md
.claude/plans/261117_ultra-search Aside 기동 계획.md                            (PR 2)
```

## SKILL.md (구현 후, 전문)

섹션 구조는 그대로다. `references/`는 없고 만들지 않는다: 한 갈래에서만 읽을 내용이 생기지 않았다.

```
(frontmatter: name, description, allowed-tools)   ← 그대로
# Web work through the user's own browser         ← 그대로: CLI 호출 형태, 승인 규칙, --help가 소유하는 것
## What each path is                               ← 그대로: search / fetch / aside repl 의 차이
## What you cannot see from here                   ← 마지막 항목에 한 문장 추가
```

본문 전문(frontmatter 제외). 바뀌는 곳은 마지막 항목의 둘째 문장 하나다.

````markdown
# Web work through the user's own browser

This skill's commands go through one CLI in its directory. The pre-approved permission rule covers that CLI alone and matches the command text: a path built from a variable, a command continued with `\`, and `aside` itself stop at an approval prompt.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help
```

Each command's `--help` owns its inputs, outputs, states and recovery.

## What each path is

`search` hands an objective to a browsing agent that chooses its own searches and pages, spends the user's subscription, and reports back in another model's words. `fetch` reads a URL you already have into a file with no agent, and turns PDF, HWP and Office documents into text with the original kept.

`aside repl` is the page in your own hands: click, drag and fill, run a script in it, read its DOM, watch the calls it makes to its back end, attach to a tab the user has open. `aside guide repl` documents the installed version; a snippet running past 120 seconds is killed and reported as the daemon being unreachable, though the daemon is fine. Queries automated against a search engine draw bot challenges; `search`'s agent does its own searching.

## What you cannot see from here

- `opened` means a tool returned that URL without an error, not that the page says what the answer claims; `opened_sources` holds only those, so an answer can cite pages a search merely listed or that the agent read through a script, which no record shows.
- Nothing here cancels delegated work: only Aside itself stops a run and its credit use, so a `search`'s scope is settled when it starts.
- Requests act as the user, with their cookies, sessions and browser. A private source being reachable does not make its contents shareable.
- WebSearch and WebFetch cannot use the user's access, and WebFetch returns a summary rather than the page; the user grounds answers in pages acquired with their own access. An answer does not show which tools produced it: when work goes on with other tools after this CLI fails, the answer says so, or the user reads it as grounded in their own access.
````

새 문장이 여섯 성질을 통과하는 근거:

- 모델이 볼 수 없는 것을 말한다: 답만 봐서는 어떤 도구로 얻었는지 사용자가 알 수 없다.
- 고치려는 기본 동작과 이유를 이름으로 말한다: 이 CLI가 실패한 뒤 다른 도구로 이어 가면서 말하지 않는 것. 어느 모델이 언제 그랬는지는 이 계획에만 있다(A7·A18·A25).
- 이유가 요구하는 것보다 세지 않다: 대체를 막지 않고 묻게 하지도 않는다.
- "check in", "doubt yourself" 같은 일반 지시가 아니라 한 지점을 가리킨다.

줄을 더하지 않는 것, 후보별로:

- "꺼져 있으면 켠다": 모델은 꺼짐을 관찰하지 못한다(명령이 그냥 된다). 이 줄로 달라지는 행동이 없다. 부작용은 `--help`가 말한다.
- "종료 3은 못 켰다는 뜻": 오류 메시지와 `--help`의 Exit 줄이 그 순간에 말한다.
- "못 켜면 네이티브 도구로 넘어가지 마라": D3. 관찰된 잘못은 대체가 아니라 침묵이다.
- "콜드 직후 `aside repl`로 연 탭은 `CDP session detached`로 실패할 수 있다": 모델이 `aside repl`을 직접 쓰면서, 방금 켜졌고, 10초 안에 탭을 여는 경우에만 약 5번에 1번. 오류가 일시적으로 보여 한 번의 재시도로 풀린다(A21). 한 턴의 비용이지 줄의 비용이 아니다.

기존 줄 "a snippet running past 120 seconds is killed and reported as the daemon being unreachable, though the daemon is fine"은 문구가 바뀐 지금도 참이다(A22).

새 문장의 대조 실험(구현 세션 8단계). 261103 계획의 하네스를 다시 쓴다: 격리 디렉터리의 스킬 복사본 + 가짜 Aside(`aside_down`), `claude -p --setting-sources project --permission-mode default --allowedTools 'Bash(uv run *)' Read Grep Glob Skill WebSearch WebFetch --model <스킬이 쓰이는 모델>`. 달라지는 것은 과제다: 261103의 단일 응답 과제는 지금 본문으로도 9/9가 밝혔으므로(A25) 가르지 못한다. 웹 조회가 **중간 단계**이고 최종 산출물이 따로 있는 과제(예: 세 서비스의 가격을 찾아 비교표 파일을 만들고 요약하라)를 쓰고, 최종 답과 산출물이 "사용자의 접근 없이 얻었다"는 것을 말하는지 본다. 이전 본문과 새 본문 각 3회.

- 새 본문에서 다른 도구로 이어 간 실행이 모두 밝히고 이전 본문에서 침묵이 하나라도 있으면: 문장을 둔다.
- 두 본문 모두 밝히면: 대조로는 가르지 못한 것이다. 그렇게 적고 문장은 실제 사고(A7)를 근거로 둔다.
- 새 본문에서도 침묵이 나오면: 결과를 성진에게 결과로 보여 주고 어떻게 볼지 묻는다(문구를 세게 고치자고 묻지 않는다).

남는 불확실성: 대조는 합성 과제 3회씩이고, 전문 승인은 여러 실제 세션에서의 성능 증거가 아니다. A18이 보여 주듯 본문의 줄은 긴 작업 중에 읽히지 않을 수 있다.

## 단계와 완료 판정

구현 세션은 `TaskCreate`로 아래 단계를 트래커에 올리고 각 `description`에 판정을 그대로 적는다. 코드를 쓰기 전에 `coding` 스킬을 연다. 스위트 실행은 출력을 파이프로 자르지 않고 러너의 종료 코드로 판정한다: `uv run --python 3.10 --with pytest --with olefile pytest -q`(이 기기에서 약 9분 40초, Bash 제한 시간을 그 위로 준다).

| # | 단계 | 완료 판정 |
|---|---|---|
| 0 | 계획 파일명을 `261117_ultra-search Aside 기동 계획.md`로 바꾼다(PR 2에 포함) | `ls .claude/plans`에 새 이름이 있고 옛 이름이 없다 |
| 1 | `aside update`, 새 CLI에서 A11·A14·A22·A23·A24 재측정 | `aside --version`이 최신. 다섯 측정값을 이 계획의 "구현 기록"에 적었다. A11·A14가 달라졌으면 PR 2의 ①을, A23이 달라졌으면(원인이 안 붙거나 문구가 다르면) PR 1의 판별을 고치고 성진에게 알렸다 |
| 2 | **PR 1**: 가짜 문구 갱신 + kill 판별 재현 테스트(빨강) → `run_code` 수정(초록) → live → `VERIFIED_*` | 재현 테스트가 고치기 전 "kill이 종료 3으로 나와서" 빨갛고 뒤에 초록. 스위트와 `-m live` 종료 코드 0. `doctor`의 버전 note가 없다. codex 검토를 받고 머지됨 |
| 3 | 보존 고정: ready일 때 왕복 호출이 없다는 테스트 | 변경 전 코드에서 초록 |
| 4 | PR 2 ④의 가짜 쪽 테스트를 쓴다 | 새 테스트가 "행동이 없어서" 빨갛다(import 오류·fixture 누락이 아님). 실패 출력으로 확인 |
| 5 | ① 구현 | 4의 명령·`resume`·탭 재시도 테스트 초록, 스위트 종료 코드 0 |
| 6 | ②③ 구현 | `doctor`·help 테스트 초록, 스위트 종료 코드 0. 여섯 명령의 `--help`를 실행해 확인 |
| 7 | `tests/live/test_cold.py`를 쓰고 `-m cold` 실행(성진이 브라우저를 안 쓸 때). 이어서 **예약 작업자 경로 1회**: `claude` 스킬의 `schedule`로 일회성 작업자를 만들어 `fetch https://example.com`의 종료 코드·stdout·stderr를 보고하게 하고, 끝나면 그 예약을 지운다. Aside는 작업자가 아니라 구현 세션이 예약 시각 직전에 끈다 | `-m cold` 종료 코드 0(20회 탭 포함). 한 번이라도 탭이 실패하면 E4가 부족한 것이니 멈추고 재설계. 예약 작업자의 결과(켜졌다 / 종료 3과 그 문구)를 적었다. 예약을 만들 수 없으면 "재지 못했다"고 적는다 |
| 8 | ⑤ SKILL.md 한 문장과 README(7의 결과 반영). SKILL.md 절의 대조 실험(이전·새 본문 각 3회) | `tests/test_structure.py` 초록. `claude plugin validate --strict .claude/skills` 종료 0. 대조 결과를 세 갈래 판정 중 하나로 적었고, 셋째 갈래면 성진에게 결과를 보이고 물었다 |
| 9 | 완성본을 `codex`로 독립 검토, 지적 처리. 코드와 함께, 모델이 읽게 되는 글(여섯 명령의 `--help` 출력, 종료 3의 실제 오류 JSON, stderr 줄, SKILL.md)을 skill-maker의 여섯 성질에 한 줄씩 대조하게 한다 | 재현되는 지적은 고치고 재실행, 기각한 것은 이유와 함께 PR 본문에. 여섯 성질 대조의 결과가 PR 본문에 있다 |
| 10 | **PR 2** 머지. 커밋은 결정 단위(보존 고정·재현 테스트 / ensure_ready / 탭 재시도 / doctor / help·README·계획 / cold 테스트) | `gh pr merge --squash`, main의 스위트 종료 코드 0 |
| 11 | **PR 3** 릴리스 | 머지됨 |
| 12 | D10 계정 점검 조사, 필요하면 **PR 4** | 세 값의 뜻을 실측으로 적었다. 고칠 것이 있으면 재현 테스트와 함께 머지됨 |

7단계의 예약 생성은 이 계획의 승인으로 허락된 것으로 본다(일회성, 끝나면 삭제, 구독 한도를 한 번 쓴다). 단 `claude` 스킬이 소유자의 선택으로 두는 것(`--public-ok`, `runner.problems`가 고칠 방법을 여럿 내놓는 경우)은 이 승인에 들어 있지 않으니 그때는 성진에게 묻는다.

## 검증 (스킬 완료 조건)

- 스위트, `-m live`, `-m cold`가 러너 종료 코드 0. 처음 빨갛게 본 테스트와 나중의 변이 확인은 따로 보고한다.
- 실제 진입점: 켜진 상태의 `fetch https://example.com`이 변경 전과 같은 소요 시간(±0.2초)이고 stderr에 기동 줄이 없다.
- 가짜 뒤에 남는 미검증을 PR 본문에 이름으로 적는다: 화면 세션 없는 실행, 데몬만 죽은 상태, 재부팅 직후, `search` 에이전트 내부의 탭 실패.
- SKILL.md 전문(위)을 성진이 이 계획으로 승인. 구현 중 문구가 한 글자라도 달라지면 다시 전문을 보여 승인받는다. 이 승인은 여러 실제 세션에서의 성능 증거가 아니다.
- `claude plugin validate --strict .claude/skills` 종료 0.
- 다른 모델 계열(codex)의 검토: 계획(아래), PR 1, PR 2 완성본.

## 재사용할 기존 자산

- `aside.repl_probe()`(`aside/repl.py`): 이미 있는 REPL 왕복. 켜는 호출로 그대로 쓴다.
- `aside.daemon_status()`: 평소 경로의 빠른 확인.
- 가짜의 routes `sequence`(호출 순서대로 다른 레코드): 탭 재시도 테스트.
- `FAKE_ASIDE_REPL_PROBE=fail`: 왕복 실패 분기.
- `tests/test_environment.py`의 `daemon` fixture, `test_pages.py`·`test_research.py`의 닫힌 포트 패턴: health 대역.
- `FAKE_ASIDE_CALLS`의 `calls.jsonl`: 무엇이 실제로 불렸는지 단언.
- live `test_a_login_gated_feed_is_readable`의 URL과 내용 단언: cold의 로그인 접근 확인.

## 기각한 대안

- **명시적 `start`(또는 `open`) 명령 + 오류의 `fix`가 그것을 가리킴.** 모델이 두 번 부르게 되고, A7처럼 그 안내를 건너뛸 수 있다. 명령 표면도 는다.
- **스킬이 직접 `open -g -b at.studio.AsideBrowser`.** Aside가 소유한 지식의 사본. CLI가 바꾸면 조용히 어긋난다.
- **게이트를 그냥 삭제.** E3.
- **매 명령 REPL 왕복.** E2의 절충.
- **켠 뒤 고정 대기(예: 10초)로 A15를 피함.** 시간은 부하에 따라 흔들리고(A16) 그 뒤에도 보장이 없다. 오류를 보고 다시 하는 쪽이 조건에 맞는다.
- **탭 재시도를 데몬 나이로 조건화.** E4.
- **120초 kill을 경과 시간이나 직후의 health로 판별.** 둘 다 추정이고 테스트용 상한 override가 든다. `ASIDE_DEBUG`가 원인을 직접 말한다(E6).
- **감독자(detached)에서 켜기.** `search`가 즉시 돌아오지만 못 켠 실패가 `result`까지 미뤄지고 런이 예약된다.
- **작업 뒤 닫기.** D5.
- **Aside를 로그인 항목·LaunchAgent로.** 사용자의 기기 설정이고, 도중에 끈 경우를 못 덮는다.
- **SKILL.md에 "네이티브 도구로 넘어가지 마라" 또는 "멈추고 보고하라".** D3. 관찰된 잘못(침묵)보다 센 규칙이고, 성진의 전역 지침(ultra-search를 "먼저")과도 다르다.
- **SKILL.md를 그대로 두기.** 프레임의 두 조항을 적용하지 않는 선택. 성진이 D11로 기각.
- **응답 JSON에 `aside_started`.** D9.
- **재작성.** 결함은 게이트 한 곳의 판단이었다. 트리·단위·명령 표면은 이 변경과 무관하다.

## 위험과 미확정

- **못 켠 뒤의 조용한 전환(A7)은 D11의 한 문장이 막으려는 것이지만, 본문의 줄이 긴 작업 중에 읽힌다는 보장은 없다(A18).** 대조 실험은 합성 과제 3회씩이다. 예약 작업자 안에서 켜지는지는 7단계가 처음 잰다.
- `ensure_ready`가 통과한 뒤 감독자가 `aside exec`를 부르기 전에 Aside가 죽는 경쟁은 남는다. 그때는 `exec`가 다시 켜고 기동 안내 줄이 `stdout.log`에 들어갈 수 있다. 평소에는 들어가지 않는다는 것만 cold가 확인한다.
- `aside exec`의 콜드 스타트와 방금 켜진 Aside에서 에이전트의 첫 탭(A15)은 cold의 `search` 1회가 유일한 증거다. 스킬의 탭 재시도는 `search`의 에이전트 안이나 모델이 직접 부른 `aside repl`에는 닿지 않는다.
- 20회 전부 성공은 관찰이지 한 번의 재시도가 충분하다는 증명이 아니다.
- health가 ready인데 브리지가 죽은 상태는 E2의 절충으로 지금과 같다.
- 자동 기동은 Aside CLI의 동작이라 업데이트로 바뀔 수 있다. 바뀌면 스킬은 크게 실패하고(조용하지 않다) `-m cold`가 잡는다.
- 가짜는 Aside를 실제로 켜지 않는다. 가짜 테스트의 초록은 분기에 대한 동의일 뿐이다(E9).

## 계획 리뷰 처리

codex(`gpt-6.1-terra`, read-only, 2026-11-17)가 초안을 코드와 대조해 읽었다. 실행해서 재현한 것은 없다고 스스로 밝혔다.

| 지적 | 처리 |
|---|---|
| 1. `daemon_status()`만으로 120초 kill을 가르면 다른 실패를 kill로 오인 | 채택. 추정을 버리고 Aside가 말하는 원인으로 가른다(E6, A23) |
| 2. health 성공은 브라우저가 일할 수 있다는 증거가 아님 | 일부 채택. 기존 동작임을 절충으로 명시(E2). 매 명령 왕복은 기각 |
| 3. 무인 실행의 핵심 목표가 여전히 실패할 수 있고 live가 그 경로를 증명 못 함 | 채택. cold에 로그인 필요 페이지, 7단계에 예약 작업자 1회, README에 한계 |
| 4. `ensure_ready` 성공만으로 "우리가 켰다"고 말할 수 없음. 버전 note와 공존, 두 실패 경로 | 채택(E5, ②, ④) |
| 5. 가짜 health와 가짜 CLI가 독립이라 실제 기동을 증명 못 함. `no_real_aside` 기본값. `DAEMON_BASE_URL` 계약 | 채택(E9, 보존할 행동, ④). 가짜가 `DAEMON_BASE_URL`을 따르게 |
| 6. "up to two minutes"와 `_NO_ASIDE` 문구가 실제보다 단정적. probe가 stderr를 놓칠 수 있음. `fix`와 D3 | 채택(③, ①, E7) |
| 7. 탭 재시도의 범위와 증거 | 채택(①, ④, 위험). 나이 조건은 codex도 근거 부족으로 봄 |
| 8. resume 성공 테스트, 준비 뒤의 경쟁, `stdout.log` 주장 한정 | 채택(④, 위험) |

고친 부분만 같은 스레드에 다시 맡긴 좁은 재검토:

| 지적 | 처리 |
|---|---|
| (a) 경과 시간에는 CLI의 기동·연결 대기도 들어 있어 120초를 넘긴 진짜 장애를 kill로 오인 | 채택. 시간 기준 자체를 버렸다(E6, A23). 상한 override도 없어졌다 |
| (b) "it is now", "started or waited for", "did not start", "longer than a minute"가 관찰보다 강함 | 채택(E5, ①②③의 문구) |
| (c) 가짜의 `DAEMON_BASE_URL` 검사가 물려받은 환경과 충돌 | 채택(`no_real_aside`가 지운다) |
| (d) `-m` 부분 문자열 검사를 베끼면 cold 격리가 보장되지 않음 | 채택(④의 격리 문단) |
| (e) E2는 명시된 절충으로 수용, `fix`는 실패별로 | 채택(E7), E2의 단정 서술 삭제 |

그 뒤 자문 검토(같은 계열 모델)가 A14가 막힌 포트에서 잰 값일 수 있다고 짚었고, 다시 재서 A14를 고치고 A23·A24를 얻었다. E6의 원인 기반 판별은 그 측정에서 나온 것이라 codex의 검토를 받지 않았다. PR 1의 검토가 이를 본다.

성진의 질문("skill-maker를 철저히 반영하나")을 받고 계획을 여섯 성질과 완료 조건에 다시 대조해 고친 것: help 문장에서 Aside 소유 값 제거, stderr는 Aside의 말을 그대로, 9단계의 검토에 여섯 성질 대조 명시, 탭 재시도의 자격 근거 기록, 그리고 D11(codex가 첫 검토에서 "무인 실패에서 기존 사실만으로 충분한지는 A7 때문에 아직 검증되지 않았다"고 짚었던 것). D11의 문장 자체는 codex의 검토를 받지 않았다. 9단계가 본다.

재검토는 여기서 멈춘다. 멈춤 조건: 평소 사용에서 닿는, 실패가 결과처럼 읽히는 경우가 남지 않았다. PR 1과 PR 2 완성본은 각각 다시 검토받는다.

Claude 작업자(`claude-opus-5-5`, 같은 계열이라 두 번째 독립 검토는 아니고 측정이다)의 시제품 영향 측정. 레포의 임시 사본에 ①②의 최소 시제품만 넣고 스위트를 전후로 돌렸다:

- 기준선 `572 passed, 25 skipped`(9분 37초, 종료 0) → 시제품 `5 failed, 567 passed, 25 skipped`(9분 35초, 종료 1).
- 깨진 5개는 모두 같은 이유다(health만 닫고 가짜는 왕복에 답하므로 "거부" 대신 진행): `test_pages.py::test_a_daemon_that_does_not_answer_is_said_before_any_work[fetch|map|crawl]`, `test_research.py::test_a_daemon_that_does_not_answer_exits_three_before_reserving_a_run`, `test_research.py::test_the_daemon_checked_is_the_one_aside_exec_uses[False]`. ④와 "보존할 행동"이 이미 이름으로 다루는 것들이다.
- 초록인데 이름과 단언이 옛 동작을 말하게 되는 것 2개: `test_environment.py::test_a_closed_daemon_fails_doctor`, `test_a_daemon_that_is_up_but_not_ready_fails_doctor`. 가짜의 health가 왕복 뒤에도 닫혀 있어서 통과할 뿐이다. ④가 다룬다.
- `test_a_missing_aside_binary_exits_three_before_reserving_a_run`은 그대로 통과한다(`aside_bin()`이 새 분기보다 먼저 던진다). 인자 거부 계열의 "before any work" 테스트는 무관하다.
- `no_real_aside`의 기본값(ready health + 없는 바이너리) 때문에 새 분기는 `fake_aside`를 쓰고 health를 닫거나 not-ready로 바꾼 테스트에서만 돈다.

## 구현 기록

(구현 세션이 채운다)

### 1단계 재측정 (2026-11-17, `aside update -y` 뒤: CLI 1.26.1115.1556 · 앱 1.0.1116.2 · 데몬 1.26.1115.1556)

원자료: 각 측정의 stdout·stderr를 세션 스크래치에 보관했다(커밋하지 않음). 다섯 값 모두 1.26.1107에서 잰 것과 같아 PR 1·PR 2의 설계를 바꾸지 않는다.

| # | 결과 |
|---|---|
| A11 | 앱 quit → 1초 뒤 health 거부·앱 프로세스 0. `aside repl` 4.04초·종료 0·stdout `{"ok":true}`, stderr `Aside isn't running. Opening it in the background...` 다음 줄에 Aside의 REPL 상태 줄 `[ok | 53ms]`. 맨 앞 앱은 그대로 |
| A14 | 닫힌 포트(연결 거부) 0.10초 종료 1, stderr `Error: Aside isn't running on this machine. …Don't switch to another browser…` + 원격 호스트 안내. 막힌 포트 9번 0.09초(이전 1.8초) 종료 1, `Error: Could not connect to Aside at http://127.0.0.1:9. …`. stdout 없음. 모두 stderr |
| A22 | 130초 스니펫: 120.39초 뒤 종료 1, stderr는 A14의 막힌 포트와 같은 `Could not connect to Aside at http://127.0.0.1:21420. …` 두 줄. 데몬 멀쩡 |
| A23 | `ASIDE_DEBUG=1`: 같은 kill에 셋째 줄 `Details: fetch failed: other side closed`(120.38초), 닫힌 포트 `Details: Failed to request daemon auth challenge: fetch failed: connect ECONNREFUSED 127.0.0.1:<port>`, 막힌 포트 `…fetch failed: bad port`. 그 뒤 `TRPCClientError: …`로 시작하는 스택이 첫 문단과 `Details:`를 되풀이한다. 전부 stderr. 성공한 `fetch_batch.js`의 stdout은 `ASIDE_DEBUG` 유무로 같다(구조 비교, `elapsed_ms` 제외) |
| A24 | `{"part":1}`을 찍고 130초 기다린 스니펫(`ASIDE_DEBUG=1`): stdout 비어 있음 |

`strings`: 1.26.1115 바이너리에 `daemon is not reachable`은 없다(0회) → `_TIMEOUT_SIGNS`에서 지운다. `other side closed`는 있다.

### PR 1 live에서 드러난 계정 상태 (D10 실측, 2026-11-17~18)

- 로그아웃 상태: `aside account list`의 u0 `signed out`, `--json`의 u0 `authStatus:"active"`, `hasSession:false`. `aside exec --effort low "Reply with the single word OK."`는 0.2초 만에 종료 1, stderr `Warning: Aside needs sign-in again for this account. … built-in Aside models require sign-in.`, 세션은 만들어지고 ` • Error Authentication failed for "claude-code".`. live의 `search`·`exec` 3개가 이것으로 실패했다. repl 경로 live(로그인 필요 피드 포함)는 모두 통과했다: 브라우저의 사이트 로그인은 Aside 계정 로그인과 별개다. `doctor`는 이 상태에서 `ok:true`(계정 점검이 `u0` 줄로 통과).
- 성진이 Aside 앱에서 로그인한 뒤: u0 `signed in`, `authStatus:"active"`, `hasSession:true`.
- 뜻: `signed in`/`signed out`은 `hasSession`과 같다. `authStatus`는 두 상태에서 같아서 아무것도 가르지 않는다. 사이트 로그인(브라우저 쿠키)은 Aside 계정 로그인과 무관하다.
- 로그인한 뒤에도 `aside exec`는 같은 `Authentication failed for "claude-code"`로 실패했다. 원인은 계정이 아니라 계정 기본 모델(`~/.aside/u/0/settings.json`: `defaultModel.provider: claude-code`, `claude-sonnet-5-5`)의 공급자 자격 증명이다. `credentials.json`의 `claude-code`가 `state: auth-expired`이고 만료는 2026-11-17 09:58 UTC로, 이 작업 전이다. 앱을 일반 실행(`open -b`)으로 다시 띄워도 같았으므로 기동 방식과도 무관하다. 같은 경로를 `--model openai-codex/gpt-6.1-sol`(자격 증명 유효)로 돌리면 `search`·`exec`가 정상이다.
- 로그아웃 상태의 CLI 경고는 "Provider credentials may still work, but built-in Aside models require sign-in."이다. 로그아웃 자체는 내장 모델만 막고, 공급자 자격 증명이 있으면 일할 수 있다는 뜻으로 읽힌다(재지 않음).
- 그래서 D10의 "점검이 실제로 틀렸다"는 둘로 나뉜다.
  - `account_status`의 docstring("a signed-out browser … silently loses every logged-in one")은 실측과 다르다.
  - 이번에 `search`를 막은 것(공급자 자격 증명 만료)은 doctor가 지금 보지 않는다.
  - 로그아웃을 실패로 만들지, 공급자 인증을 볼지는 doctor의 계약을 정하는 일이다. 그래서 고치기 전에 성진에게 근거와 함께 묻는다(PR 4 보류).

### 8단계 대조 실험 (2026-11-18)

하네스: 격리 디렉터리의 스킬 사본(PR 2 코드) + 가짜 Aside(`aside_down`, 닫힌 health). `claude -p --setting-sources project --permission-mode default --allowedTools 'Bash(uv run *)' Read Grep Glob Skill WebSearch WebFetch Write Edit --model opus --output-format stream-json`(claude-opus-5-5, Claude Code 2.1.326). init 이벤트로 격리를 확인했다: 스킬은 프로젝트의 `ultra-search`와 Claude Code 내장 스킬뿐이고, 사용자 스킬은 없다. 과제: Notion·Linear·Figma의 가장 싼 유료 요금제 월 가격을 웹에서 확인해 `prices.md` 비교표를 만들고 요약하라. 웹 조회는 중간 단계다.

| 본문 | 최종 답에서 밝힘 | `prices.md`에서 밝힘 | 경로 |
|---|---|---|---|
| 이전(old-1~3) | 3/3 ("Aside가 꺼져 있어서 일반 웹 조회로" 등) | 0/3 | 모두 `fetch` 2회 → 종료 3 → web-fetch 에이전트·WebFetch·WebSearch |
| 새(new-1~3) | 3/3 | 0/3 | 같음 |

판정: 최종 답에서는 두 본문 모두 밝혔다. 대조로는 가르지 못했으므로(둘째 갈래) 문장은 실제 사고(A7·A25)를 근거로 둔다. 산출물 파일은 두 본문 모두 6회 중 한 번도 밝히지 않았다. 이것은 새 본문에서도 나온 침묵이라, 성진에게 결과로 보이고 어떻게 볼지 묻는다(문구를 세게 하자고 묻지 않는다).

해석에 섞인 것: 이제 종료 3의 메시지에 Aside 자신의 말(`Ask the user to open Aside… Don't switch to another browser…`)이 인용된다. A7 당시 모델이 받은 것은 `the Aside daemon is not ready: …`였다. 이번 6/6 공개에는 이 인용(D8)의 몫이 섞여 있을 수 있다. 그 밖의 차이: old-3은 `curl`을 시도했다가 권한 거부됐다(나머지 실행은 거부 없음). new-2·old-1~3은 답에서 "Aside를 켜 주시면 다시 확인하겠다"고 제안했다.

### 7단계 cold와 재설계 (2026-11-18)

- `-m cold` 1차는 27 passed, 2 failed였다.
  - 콜드 직후 탭 20회 중 [4]가 `status: blocked`, `error: "html is required"`였다. 탭 스니펫이 DOM을 하나도 읽지 못하고 빈 `kind:text` 레코드를 찍은 것이다. 모든 `content()`가 던져 `continue`로 삼켜졌거나, 빈 읽기 두 번을 "안정"으로 보고 멈췄을 것이다. 어느 쪽인지는 기록이 없다. 데몬 로그에도 없고, 진단 루프에서는 재현되지 않았다.
  - E4(detached 재시도)가 닿지 않는 길이었으므로 계획대로 멈추고 재설계했다. `tab_one.js`는 빈 읽기를 안정으로 보지 않고, DOM을 하나도 못 읽으면 마지막으로 던져진 오류를 담아 `kind:error`로 보고한다. 그 오류가 detached면 E4가 받는다. Node 스텁으로 두 길을 고정했다.
  - search 1건은 `claude-code` 공급자 자격 증명 만료로 `failed`였다. 그 런의 `stdout.log`에 기동 안내 줄은 없다(`created new session…` + 인증 오류뿐).
- 재설계 뒤 실제 콜드 60회: 회마다 앱이 꺼졌는지(프로세스·포트)와 stderr의 기동 안내 줄을 확인했다. 가짜 스위트로 부하를 건 상태에서 `fetch --via tab https://example.com`이 60/60 `ok`이고 6.3~8.6초였다. 관찰이지, 빈 DOM 실패가 고쳐졌다는 증명은 아니다(재현하지 못했다).
- 관찰 하나. Aside가 한 번 `quit` Apple 이벤트를 무시했다. `osascript` 종료 0, 창에는 시트도 대화상자도 없었다. 숨김 창의 페이지가 떠나기 확인을 띄웠을 수 있다. 그 사이 첫 진단 루프와 60회 루프의 앞부분은 콜드가 아니었으므로 버렸다. cold 테스트의 `closed` fixture는 이 경우 "Aside did not quit"으로 크게 실패한다.
  - 앱을 SIGTERM으로 끄자 앱만 죽고 데몬은 남았다. 그 상태의 `aside repl`은 `Aside Browser profile for account u0 … is not connected to the daemon.`으로 실패하고 앱을 열지 않는다. CLI는 연결 거부일 때만 연다. health는 ready라서 스킬은 왕복 없이 일을 시작하고, 첫 스니펫에서 종료 3과 이 문구로 끝난다. E2의 절충이 그대로 드러난 경우이고, 조용하지 않다.
  - 앱을 `open -g -b`로 다시 띄우자 남아 있던 데몬에 붙어 정상이 됐다.
- 예약 작업자: 재지 못했다. `claude` 스킬의 `schedule`은 공개 레포에서 `--public-ok`를 요구하는데(이 레포는 PUBLIC), 그 플래그는 계획상 이 승인에 들어 있지 않은 소유자의 선택이라 성진에게 묻는다.

### 공급자 재연결 뒤 live·cold, 데몬 1.26.1118 (2026-11-18)

- 성진이 Aside에서 `claude-code` 공급자를 다시 연결했다(`credentials.json`의 `claude-code` `state: active`). 그 뒤 `-m live` 27 passed(종료 0). 이 실행의 데몬 버전은 기록하지 않았다.
- 그 사이 데몬이 스스로 1.26.1118.1753으로 올라가 있었다. 앱(`CFBundleShortVersionString` 1.0.1116.2)과 CLI(1.26.1115.1556, `aside update`가 "up to date")는 그대로다. `doctor`는 통과하고 "measured against daemon 1.26.1115.1556" note만 냈다.
- 데몬 1.26.1118.1753에서 `-m cold` 29 passed(종료 0, 4분 37초, search 포함), 이어서 `-m live` 27 passed(종료 0, 3분 0초: 120초 kill·연결 거부 계약, search·세션 이어가기 포함). 그래서 `VERIFIED_DAEMON_VERSION`을 1.26.1118.1753으로 올렸다. `VERIFIED_VERSION`(CLI)은 그대로다.
- 이로써 계획의 완료 조건 중 live·cold 종료 0이 채워졌다. 빈 DOM 탭 실패의 수정은 여전히 재현으로 증명되지 않았다.

### D10 결정과 PR 4 (2026-11-18)

- 성진의 결정: 세 안(공급자 자격 증명 확인 / 로그아웃을 실패로 / docstring만) 가운데 **공급자 자격 증명 확인**. 예약 작업자 측정은 하지 않는다(`--public-ok` 불허, README의 "재지 않았다" 유지). 대조 실험의 결과물 파일 침묵 0/6은 "최종 답에서 밝히면 충분"으로 읽는다(문구 유지).
- CLI에는 공급자 상태를 알려 주는 명령이 없다: `aside settings get`은 계정·프로필·saveSessions만, `aside account status --json`은 계정 필드만 준다. 그래서 `u/0/settings.json`의 `defaultModel`과 `u/0/credentials.json`의 그 공급자 `state`를 읽는다.
- 상태 어휘: CLI 바이너리에 `modelProviderStateSchema = _enum(["active", "auth-expired"])`. `expires`는 `state: active`인 채로 같은 날 07:38→19:10 UTC로 굴러갔다(액세스 토큰 만료라 판정에 쓰지 않는다). 다른 계정(u1)의 기본 모델은 `provider: aside`(내장)이고 그 계정의 credentials는 `{}`였다.
- 런이 쓴 모델: `--model` 없이 돌린 세션들은 `claude-code`/`claude-sonnet-5-5`를 기록했다. `defaultModel`과 `modelCategories.fast/deep`이 같은 값이라 exec가 어느 쪽을 읽는지는 가르지 못했다.
- codex 검토: "active 아닌 모든 state를 실패"는 스키마 밖 값에서 거짓 빨강이 되고, state 자리의 토큰 같은 문자열을 detail에 인용한다는 두 지적을 채택했다(알려진 두 값만 판정·인용). "내장 모델 + 로그아웃 계정이 not checked로 통과"는 로그아웃을 실패로 정하지 않았고 그 실패를 재지 않았으므로 이번에는 고치지 않고 코드에 `성진:` 한계로 남겼다.
- 미검증: 실제로 만료된 자격 증명으로 이 점검을 돌려 보지 않았다(오늘 아침의 만료는 이 점검을 만들기 전에 풀렸다). refresh 토큰이 죽었는데 state가 active로 남는 경우는 통과한다.
