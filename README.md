# Ultra-Search

클로드가 웹에서 무언가를 알아내야 할 때 네이티브 `WebSearch`/`WebFetch` 대신 집어드는 `ultra-search` 스킬의 소스 저장소다. 엔진은 로그인된 Aside 브라우저(`aside` CLI)다.

## 왜

네이티브 툴은 Brave 인덱스 안에서만 찾고, 로그인·봇차단 뒤에 닿지 못하며, 결과가 질의에 맞춘 발췌라 원문이 필요할 때 부족하고, 크롤링도 로컬 저장도 못 한다. `ultra-search`는 **내 실제 브라우저**를 쓴다. 쿠키와 세션이 그대로 있으니 구독 피드도 유료 기사도 열리고, 원문 전체를 마크다운 파일로 떨어뜨리며, 사이트 하나를 통째로 받아올 수 있다.

## 네 가지 역량

- **`search`** — 목적을 주면 브라우저 안의 에이전트가 스스로 조사한다. 여러 개를 병렬로 돌리고, 오래 걸리면 백그라운드로 넘겨 끝날 때 깨워준다.
- **`fetch`** — URL을 원문 마크다운으로. PDF·docx·pptx·xlsx·epub도 변환한다. 자바스크립트로 그리는 페이지는 실제 탭으로 자동 승격.
- **`map` / `crawl`** — 사이트의 URL 목록만 먼저 보고, 받을 만하면 통째로 받는다.
- **`status` / `log` / `result`** — 돌고 있는 조사를 들여다보고, 끝나면 답과 출처를 수거한다.
- **`sessions` / `resume`** — Aside가 아직 가지고 있는 대화를 목록으로 보고, 이어서 묻는다. 앱에서 시작한 대화도 포함된다.

## 설치

```bash
git clone <this repo> ~/Coding/Ultra-Search
ln -s ~/Coding/Ultra-Search/.claude/skills/ultra-search ~/.claude/skills/ultra-search
python3 ~/.claude/skills/ultra-search/scripts/cli.py setup    # Node 변환 의존성
python3 ~/.claude/skills/ultra-search/scripts/cli.py doctor   # 환경 점검
```

전제: Aside 앱이 실행 중이고 계정이 로그인되어 있을 것, `aside` CLI가 PATH에 있을 것, Node 20 이상. Python은 표준 라이브러리만 쓰므로 별도 설치가 없다.

`doctor`가 초록이면 준비된 것이다. 무엇이 왜 막혔는지는 `doctor`가 한 줄로 말한다.

## 써보기

```bash
US='python3 ~/.claude/skills/ultra-search/scripts/cli.py'

$US search "현재 Python 3의 최신 안정 버전은? 공식 출처를 들어 한 줄로"
$US fetch https://arxiv.org/pdf/1706.03762 --out ./papers
$US crawl https://docs.aside.com --out ./docs
$US --help          # 커맨드 전체
$US fetch --help    # 플래그·기본값·거부 규칙
```

사용법의 진실은 `--help`에 있다. 이 README에 플래그 표를 두지 않는 것은 두 벌이 되는 순간 한 벌이 틀리기 때문이다.

## 알아둘 것

- **`stop`은 런을 멈추지 못한다.** 감시만 끊는다. 데몬 쪽 조사는 계속되고 크레딧도 계속 나간다. 진짜 중단은 Aside 앱 UI에서만 된다.
- **침묵은 정체가 아니다.** 서브에이전트를 띄운 조사는 자식들이 일하는 동안 부모가 몇 분씩 조용하다. `status`가 자식까지 보고 판단 재료만 주며, 죽이지는 않는다.
- **`search`는 비싸다.** 한 번에 수만 토큰이 ChatGPT 구독으로 나간다. URL을 이미 아는데 `search`를 쓰는 것이 이 도구로 저지르기 쉬운 유일하게 비싼 실수다. 주소를 알면 `fetch`.
- **차단된 페이지는 저장되지 않는다.** 봇 챌린지·로그인 벽도 HTTP 200에 본문이 있다. 그걸 본문으로 저장하면 출처가 조용히 빠진다. `ok`가 아닌 항목은 그 출처를 확보하지 못한 것이다.

## 개발

```bash
python3 -m pytest tests/          # 170개, aside 없이 통과
python3 -m pytest tests/ -m live  # 실제 Aside 필요
```

테스트는 `tests/fake_aside/aside`(가짜 바이너리)와 `tests/fixtures/`(실제 세션·페이지·PDF에서 녹화)를 쓴다. 임계값은 지어낸 값이 아니라 실측에서 나왔다 — 셸 판정 80단어는 x.com 0단어, 연합뉴스 219단어, 위키백과 4355단어 사이에서 잡은 것이다.

구조와 설계 근거는 [.claude/harness-spec.md](.claude/harness-spec.md)에, 만든 과정은 [.claude/plans/](.claude/plans/)에 있다.
