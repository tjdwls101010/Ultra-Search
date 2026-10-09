# Ultra-Search

클로드가 웹에서 무언가를 알아내야 할 때 네이티브 `WebSearch`/`WebFetch` 대신 집어드는 `ultra-search` 스킬의 소스 저장소다. 엔진은 로그인된 Aside 브라우저(`aside` CLI)다.

## 왜

네이티브 툴은 Brave 인덱스 안에서만 찾고, 로그인·봇차단 뒤에 닿지 못하며, 결과가 질의에 맞춘 발췌라 원문이 필요할 때 부족하고, 크롤링도 로컬 저장도 못 한다. `ultra-search`는 **내 실제 브라우저**를 쓴다. 쿠키와 세션이 그대로 있으니 구독 피드도 유료 기사도 열리고, 원문 전체를 마크다운 파일로 떨어뜨리며, 사이트 하나를 통째로 받아올 수 있다. 목적은 클로드의 답이 실제로 확보한 원문에 근거하게 하는 것이다.

## 네 가지 역량

- **조사 위임 `search` / `resume`** — 목적을 주면 브라우저 안의 에이전트가 스스로 조사한다. 여러 개를 병렬로 돌리고, 오래 걸리면 기다리는 명령(`next`)을 돌려줘 끝날 때 깨워준다. 끝난 조사나 Aside 앱에서 시작한 대화(`sessions`)에 이어서 물을 수 있다.
- **원문 확보 `fetch`** — URL을 원문 마크다운으로. PDF·HWP·HWPX·docx·pptx·xlsx·epub도 변환하고, 원본 파일도 남긴다. 한글 문서는 서버가 붙인 MIME이 아니라 내용으로 알아본다. 자바스크립트로 그리는 페이지와 봇 확인은 실제 탭으로 자동 승격.
- **사이트 수집 `map` → `crawl`** — 사이트의 URL 목록만 먼저 보고, 받을 만하면 통째로 받는다.
- **결과 수거 `result` / `show` / `log`** — 끝날 때까지 기다려(`result --wait`) 답과 열어 본 출처, 에이전트가 내려받은 파일의 사본을 수거한다. 이미 읽은 본문은 다시 가져오지 않고 꺼내며(`show`), 출처를 왜 골랐는지는 나중에 되짚는다(`log`).

## 설치

전제: [uv](https://docs.astral.sh/uv/)(스킬을 실행할 Python과 의존성 `olefile`도 uv가 고른다), Node 20.19 이상(변환 패키지 lockfile의 요구치이며 `doctor`가 확인한다), 실행 중이고 계정이 로그인된 Aside 앱과 PATH의 `aside` CLI.

```bash
git clone <this repo> ~/Coding/Ultra-Search
ln -s ~/Coding/Ultra-Search/.claude/skills/ultra-search ~/.claude/skills/ultra-search
uv run ~/.claude/skills/ultra-search/scripts/cli.py setup    # Node 변환 의존성
aside --update                                               # 검증한 Aside CLI로
uv run ~/.claude/skills/ultra-search/scripts/cli.py doctor   # 환경 점검
```

`doctor`가 모두 통과하면 준비된 것이다. 무엇이 왜 막혔는지는 실패한 점검마다 고치는 법과 함께 나온다. 설치된 Aside가 스킬을 검증한 버전과 다르면 `doctor`가 알린다.

`git pull`로 올린 뒤에는 `setup`을 다시 실행한다. Node 의존성은 git이 추적하지 않아서, 변환기 위치나 버전이 바뀌면 새 자리에 다시 설치해야 한다.

## 써보기

```bash
US='uv run ~/.claude/skills/ultra-search/scripts/cli.py'

$US search "현재 Python 3의 최신 안정 버전은? python.org를 근거로 한 줄로"
$US result --wait 570       # 방금 조사가 끝날 때까지 기다려 답·출처·저장 파일을
$US result --sources        # 방금 조사의 전체 출처
$US fetch https://www.scourt.go.kr/sjudge/1625214940201_173540.hwp --out ./docs/
$US crawl https://docs.aside.com --out ./site
$US --help                  # 명령 전체
$US result --help           # 플래그·기본값·출력·상태·종료 코드
```

사용법의 진실은 `--help`에 있다. 이 README에 플래그 표를 두지 않는 것은 두 벌이 되는 순간 한 벌이 틀리기 때문이다.

## 알아둘 것

- **CLI는 조사를 멈추지 못한다.** 진짜 중단은 Aside 쪽에서만 된다. 기다리기를 그만둬도 데몬 쪽 조사와 크레딧은 계속된다.
- **침묵은 정체가 아니다.** 서브에이전트를 띄운 조사는 자식들이 일하는 동안 부모가 몇 분씩 조용하다. `result --wait`는 그동안의 진행을 보여 주며 기다리고, 감독자는 이 턴의 자식까지 포함해 10분 동안 아무 기록이 없을 때만 감시를 그만두고(`abandoned`) 그때까지의 결과를 남긴다.
- **`search`는 비싸다.** 한 번에 수만 토큰이 구독으로 나간다. 주소를 이미 알면 `fetch`.
- **차단된 페이지는 저장되지 않는다.** 봇 챌린지·로그인 벽도 HTTP 200에 본문이 있다. 그걸 본문으로 저장하면 출처가 조용히 빠진다. `ok`가 아닌 항목은 그 출처를 확보하지 못한 것이다.
- **산출물은 작업 디렉터리의 `./.ultra-search/`에 쌓인다.** 런·에이전트 저장 파일의 사본·저장한 페이지·맵·크롤이 여기 들어가고, 스킬이 처음 쓸 때 `*` 한 줄짜리 `.gitignore`를 만들어 그 프로젝트의 git에 섞이지 않게 한다. `--runs-dir`·`--out`으로 고른 곳은 건드리지 않는다.
- **Aside를 쓸 수 없으면 대신 네이티브 툴을 쓰지 않는다.** 스킬은 `doctor`가 말한 원인과 해결을 알리고, 네이티브 툴로 대체할지 묻는다.

## 구조

```
.claude/skills/ultra-search/
├── SKILL.md
└── scripts/
    ├── cli.py              # 유일한 진입점: 파서·도움말·디스패치·종료 코드 표, PEP 723 헤더
    └── ultra_search/
        ├── research/  fetch/  site/  doctor.py      # 기능
        ├── aside/  converter/  hwp/                 # 남이 소유한 시스템
        ├── runs/  saved.py                          # 저장소
        └── outcome.py  ids.py  workspace.py         # 도우미
```

- **기능**은 스킬이 존재하는 이유 하나씩(조사 위임, 원문 확보, 사이트 수집, 환경 점검)이고, **시스템**은 남이 소유해 예고 없이 바뀌는 것(Aside의 CLI·데몬·전사·stdout·REPL·세션의 저장 파일, Node 변환기, 한컴 HWP·HWPX 형식), **저장소**는 디스크 상태(런 디렉터리와 그 사본, 저장한 페이지·맵·크롤의 이름), **도우미**는 모두가 쓰는 것이다.
- import는 기능 → 시스템·저장소 → 도우미 한 방향이다. 기능 간 엣지는 `site → fetch`(크롤은 페이지 단위 fetch로 만든다) 하나뿐이다. 단위 밖에서는 `__init__.py`가 내보낸 이름만 쓴다.
- Aside가 형식을 바꾸면 `aside/`만, 한컴이 형식을 바꾸면 `hwp/`만 고친다. 전사 레코드는 `aside/`에서 스킬 용어(`Event`: 정지 이유, 출처와 열었는지, 자식 id, 사용량)로 바뀌어 나간다.
- 상태는 skill-maker 규칙의 `data/`가 아니라 작업 디렉터리의 `./.ultra-search/`에 둔다. 전역으로 로드되는 스킬이라 여러 프로젝트의 세션이 동시에 돌고, 프로젝트별 레지스트리가 대상 없는 `result`·`log`의 "가장 최근"을 그 프로젝트로 한정한다. 산출물은 Read로 읽혀야 하는데 심볼릭 링크로 설치된 스킬 폴더 안 파일은 Read가 거부한다.
- `tests/test_structure.py`가 이 트리를 지킨다: 최상위 두 이름, 단위 종류 표, import 방향, 인터페이스 밖 접근 금지, `sys.path`·`PYTHONPATH` 변경 금지, 진입점 하나, Aside·변환기·한컴 이름이 제 단위 밖에 없음, SKILL.md의 호출 형태와 `cli.py`의 PEP 723 헤더.

## 개발

```bash
uv run --python 3.10 --with pytest --with olefile pytest -q          # 454개, 실제 aside 없이 통과
uv run --python 3.10 --with pytest --with olefile pytest -q -m live  # 18개, 실제 Aside 앱 필요
```

- 테스트는 `tests/fake_aside/aside`(가짜 바이너리)와 `tests/fixtures/`(실제 세션·stdout·페이지·PDF·공개 HWP·HWPX에서 녹화)를 쓴다. 임계값은 실측에서 나왔다 — 셸 판정 80단어는 x.com 0단어, 연합뉴스 219단어, 위키백과 4355단어 사이에서 잡았다. HWP·HWPX 기대 문장은 같은 문서의 다른 렌더링(법원 판결문 페이지, 같은 공고의 PDF, pyhwp)에서 골랐다.
- `-m live` 가운데 실제 `aside exec`를 부르는 3개(`test_a_simple_search_answers_with_sources`, `test_a_session_started_outside_this_tool_can_be_continued`, `test_the_real_binary_writes_a_transcript_the_cli_can_find`)는 실행할 때마다 구독을 쓴다. 나머지 live는 fetch(HWP·HWPX 포함)·map·crawl·doctor 계열이다.
- **Aside를 업데이트한 뒤에는** live 전체를 다시 돌리고, 통과하면 `aside/process.py`의 `VERIFIED_VERSION`·`VERIFIED_DAEMON_VERSION`을 그 버전으로 올린다. 가짜 Aside와 녹화 fixture는 실제 형식이 바뀐 것을 모르기 때문에, 2026-09 중순 전사 형식 변경은 live를 돌리지 않는 동안 2주 넘게 녹색 테스트 뒤에 숨어 있었고, 2026-10 CLI 업데이트의 `exec --session` 제거는 live가 잡았다.
- 설계 근거는 각 모듈의 docstring에, 만든 과정과 결정은 [.claude/plans/](.claude/plans/)에 있다.
