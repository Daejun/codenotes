# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**계획, 진행 상태, 실측치는 `PLAN.md`에 있다. 이 파일에는 Phase를 적지 않는다.**
여기 적힌 것은 언제 읽어도 유효한 계약 — 명령, 구조, 스키마, 불변식이다.

## 이 저장소가 만드는 것

codenotes — 코드가 바뀔 때 **왜 바뀌었는지**를 소스 파일 바깥의 sidecar 메타 파일에 기록하는
Claude Code hook 묶음과 CLI. 기록은 나중에 (1) review에서 근거로 읽고, (2) 같은 곳을 다시 고칠 때
편집 직전에 context로 되돌려 넣는 데 쓴다. 주석과 달리 소스 파일에는 한 글자도 쓰지 않는다.

**용량은 소스가 아니라 저장소에서 나간다.** 이 저장소 실측으로 note 1건이 398 byte,
sidecar 합계가 소스+문서의 **9.47%**다. note는 편집마다 늘고 소스는 그만큼 안 는다.
소스 파일이 안 커지는 것이 이 방식의 값어치이지, 저장소가 안 커진다는 뜻이 아니다.
오래 쓰면 `codenotes gc`가 필수다 — 레코드는 남기고 `why`만 비워 이력을 지키면서 줄인다.

## 명령

의존성 0(python3 stdlib 전용)이 요구사항이다. 이 머신에는 pytest, ruff, mypy, tree-sitter, ctags가 없고
앞으로도 쓰지 않는다. hook은 사용자의 모든 편집마다 돌기 때문에 import 비용과 설치 실패가 곧 장애다.

```bash
# 테스트 전체
python3 -m unittest discover -s tests -t . -v

# 테스트 파일 하나
python3 -m unittest tests.test_anchor -v

# 테스트 케이스 하나
python3 -m unittest tests.test_anchor.AnchorResolve.test_moved_function -v

# hook을 fixture로 직접 돌리기 (stdin이 곧 hook 입력)
python3 hooks/pre_edit_recall.py < tests/fixtures/hook_input/pre_edit.json | jq .
python3 hooks/turn_capture.py    < tests/fixtures/hook_input/stop.json; echo "exit=$?"

# CLI
python3 -m codenotes show fs/gc.c
python3 -m codenotes search "deadlock"
python3 -m codenotes review --since origin/main   # 지금 diff에 걸린 note만
python3 -m codenotes doctor          # stale 비율, orphan sidecar, 따라가야 할 rename
python3 -m codenotes mv <old> <new>  # sidecar를 rename 따라 옮긴다
python3 -m codenotes gc --keep 3     # anchor당 3건 초과분의 why를 비운다 (레코드는 남는다)

# anchor 생존율 재측정 (시험용 clone을 replay)
python3 tools/anchor_probe.py
```

이 저장소는 **자기 자신에게 codenotes를 건다**(self-hosting). `.claude/settings.json`이
`hooks/*.py`를 절대 경로로 가리키고, hook 스크립트는 `Path(__file__).resolve().parent.parent`를
`sys.path`에 넣어 `codenotes` 패키지를 찾는다.

## capture는 hook, 해석은 skill

**capture를 skill로 만들지 않는다.** skill은 모델이 invoke해야 동작하고, frontmatter `hooks`로 건
hook은 그 세션 한정이다. 편집 하나를 놓치면 그 note는 복구할 수 없다. 강제 실행은 harness만 보장한다.

skill이 맡는 몫은 강제가 필요 없고 모델 판단이 필요한 쪽이다 — diff에 걸린 note를 읽어 review를
쓰는 일. 이 경계를 흐리지 않는다.

## 편집 전에 이유를 한 줄 쓴다

이 저장소에서 파일을 고칠 때는 **그 편집 직전에 왜 고치는지를 한 줄 쓴다.** 무엇을 할지가 아니라
무엇이 잘못됐는지를 쓴다. "예산 계산을 고칩니다"가 아니라 "예산 200자에 163자가 다 들어가는데
잘린다고 단정했다"이다.

강제가 아니라 관행인데, 이 관행이 곧 제품의 입력이다. `thinking`은 transcript에 저장되지 않으므로
capture가 볼 수 있는 이유는 **그 편집 직전의 text 블록**뿐이다(`docs/findings-hook-io.md`).
한 줄을 쓰면 그것이 note가 되고, 안 쓰면 note는 `src:"turn"`으로 떨어져 recall에서 빠진다.

Phase 4 실측 — 이 규칙 없이 자동 추출만 했을 때 note 12건 중 인과 표지가 있는 것은 4건(33.3%)이었다.

## 구조

hook은 **둘**이다. 읽는 쪽(PreToolUse)과 쓰는 쪽(Stop). 편집마다 쓰지 않고 턴 끝에 몰아 쓴다.

```
사용자 편집 요청
   |
   +-- PreToolUse(Edit|Write)   hooks/pre_edit_recall.py
   |      그 파일의 기존 note를 골라 additionalContext로 주입   <-- "참조" 경로
   |
   +-- (Edit 실행)  ... 한 턴에 여러 번
   |
   +-- Stop                     hooks/turn_capture.py        <-- "기록" 경로
          transcript를 watermark부터 읽어 Edit/Write tool_use를 모으고,
          toolUseResult로 그 편집 시점의 내용을 복원해 anchor를 계산,
          why를 붙여 sidecar에 append. rename 추적과 index 갱신도 여기서.
```

**capture가 PostToolUse가 아니라 Stop인 이유** — 셋 다 실측이다(`docs/findings-hook-io.md`).

1. PostToolUse 시점에 그 `tool_use_id` 레코드가 transcript에 아직 없다(2/2 사례에서 3줄 뒤).
2. `thinking` 본문은 transcript에 저장되지 않는다. 빈 문자열에 signature만 남는다.
   편집 직후에 읽을 "이유"라는 것이 애초에 없다.
3. `toolUseResult`가 편집 전후를 통째로 들고 있어 Stop에서 그 턴의 편집을 복원할 수 있다.

**복원은 `oldString`/`newString`으로 한다. `structuredPatch`로 하지 않는다.**
`structuredPatch`는 탭을 공백으로 펴서 담기 때문에 내용이 손실된다 — 원본 `\tunsigned int zone;`이
패치에는 `'   unsigned int zone;'`로 들어온다. 줄 수와 줄 범위 산정에만 쓴다.

| tool | 편집 후 내용 | 비고 |
| --- | --- | --- |
| Edit | `originalFile.replace(oldString, newString)` (`replaceAll`이면 전부) | 디스크와 정확히 일치 확인 |
| Write | `content` | 새 파일이면 `type == "create"`, `originalFile`은 None |

transcript에서 한 API message는 **블록마다 한 레코드**로 쪼개진다. 묶는 키는 `message.id`,
순서는 `apiBlockIndex`. "그 편집 직전의 말"은 같은 `message.id`에서 `apiBlockIndex`가 작은
text 블록이다. assistant 레코드에는 `promptId`가 없으므로 턴을 prompt_id로 자르지 않는다 —
watermark와 `tid` dedup으로 처리한다.

모듈 경계 — hook 스크립트는 stdin 파싱과 종료 코드만 책임지고 로직은 전부 패키지에 둔다.

| 파일 | 책임 |
| --- | --- |
| `codenotes/anchor.py` | enclosing symbol 판정, 정규화 해시, 읽을 때 재해석 |
| `codenotes/store.py` | sidecar 경로 매핑, append, 원자적 rewrite |
| `codenotes/record.py` | 레코드 스키마, id 생성, supersede 판정 |
| `codenotes/extract.py` | transcript JSONL 파싱(블록 재조립), why 추출, confidence 산정 |
| `codenotes/render.py` | additionalContext 문자열 생성과 예산 |
| `codenotes/ask.py` | 이유가 빈 편집을 되묻고 답을 `sup`으로 잇는다 (opt-in) |
| `codenotes/review.py` | review, 검색, rename 추적, gc |

## 저장 배치

```
.codenotes/
  config.json             # budget_chars, why_max, ask_missing, shared
  state.json              # gitignore. watermark와 본 tid — sidecar에서 재생성된다
  hook.log                # gitignore
  src/gc.c.jsonl          # sidecar: 소스 트리를 미러링, 원본 확장자 유지 + .jsonl
  fs/core/segment.c.jsonl  # shared가 아니면 이것들도 gitignore
```

**색인을 두지 않는다.** FTS5는 드문 질의에서 확실히 빠르지만(note 20만 건에 34ms -> 0.31ms),
현실 규모인 1만 건에서 전수 스캔이 1.8ms다. CLI 한 번에 1.8ms면 색인을 동기화하고 재생성하고
stale을 걱정할 값어치가 없다. note가 5만 건을 넘어 스캔이 10ms를 넘으면 다시 본다.

**기본값은 gitignore다.** note의 why는 모델이 편집 직전에 쓴 말에서 나오므로,
그 말에 비공개 프로젝트 이름이나 내부 경로가 섞이면 그대로 sidecar에 적히고 커밋된다.
이 저장소도 그래서 로컬 전용으로 둔다 — 실제로 한 번 섞였고 저장소를 갈아엎어야 했다.

공유가 필요하면 `codenotes init --shared`다. 그때는 `.gitattributes`에
`.codenotes/**/*.jsonl merge=union`이 붙는다. 그래서 레코드는 **줄 단위로 독립**이어야 하고
순서에 의미를 두면 안 된다. 켜기 전에 무엇이 적히는지 먼저 본다:

```bash
git ls-files -z | xargs -0 grep -ril '<밖에 나가면 안 되는 말>'
```

레코드 한 줄:

```json
{"v":1,"id":"n_7f3a91","ts":"2026-09-15T02:53:57Z","sid":"00000000","pid":"bd27dfb3",
 "tid":"toolu_01ABC","op":"edit",
 "anchor":{"sym":"zone_gc_thread","kind":"fn","hash":"a91c3f","lines":[412,431]},
 "d":{"add":12,"del":3},
 "why":"zone reset 중 victim 재선택이 같은 zone을 잡아 GC가 진전하지 못함",
 "src":"text","conf":0.7,"sup":["n_5b21"]}
```

`sup`은 이 레코드가 대체하는 이전 레코드 id. 읽을 때는 최신만 보이되 이력은 지우지 않는다.

## anchor 해석 순서

줄 번호는 **힌트일 뿐** 식별자가 아니다. note를 찾을 때 이 순서로 시도한다.

1. `hash`와 같은 정규화 블록이 파일 안에 있으면 그 위치 — 코드가 이동해도 따라간다
2. 실패하면 `sym` 이름으로 enclosing symbol 재탐색 — 위치는 맞고 내용이 바뀐 경우, `stale: content`
3. 실패하면 **파일 전체**의 symbol 중 본문 유사도가 가장 높은 것(`difflib.SequenceMatcher` 0.6 이상)
   — 개명된 함수를 찾는 단계다. `lines` 주변만 뒤지지 않는다
4. 전부 실패하면 `stale: lost`, 파일 레벨 note로 강등

3단계가 줄 창이 아니라 파일 전수인 이유는 실측 때문이다. 139개 커밋 쌍, 함수 anchor
11,040건에서 1단계 94.3% / 2단계 5.1% / 유실 0.6%였다. note가 붙는 곳은 방금 고친 함수,
곧 2단계 구간이고 이름으로 다 잡힌다. 남는 문제는 "줄이 밀렸다"가 아니라 "이름이 바뀌었다"다.
근거는 `docs/findings-anchor.md`, 재측정은 `tools/anchor_probe.py`.

symbol 판정은 언어별로 싸게 한다: `.py`는 stdlib `ast`, C 계열(C/C++/Rust/Go/Java/JS/TS)은 역방향
brace scan 휴리스틱, 나머지는 파일 레벨. tree-sitter나 ctags를 끌어들이지 않는다.

## 불변식

깨지면 프로젝트의 전제가 무너지는 것들이다.

1. **hook은 절대 편집을 막지 않는다.** 어떤 예외도 잡아서 exit 0. 진단은 `.codenotes/hook.log`로만 흘린다.
   note 시스템 고장이 사용자 작업 중단이 되면 안 된다.
2. **소스 파일에 쓰지 않는다.** 코드 파일을 여는 쓰기 경로 자체를 두지 않는다.
3. **예산**: PreToolUse 300ms(편집마다 돈다), Stop 2,000ms(턴당 1회).
   hook 1회의 바닥값은 python3 기동 + json 파싱 + 300줄 transcript 스캔에 3.1ms로 측정됐다.
4. **hook 경로에서는 append만.** rewrite(rebind, gc, rename)는 CLI와 Stop에서 temp + rename으로.
5. **`tid`로 중복을 막는다.** 같은 tool_use_id는 두 번 기록하지 않는다.
6. **진실은 sidecar JSONL 하나뿐이다.** 색인을 두지 않고, `state.json`은 watermark 캐시라
   지워도 sidecar에서 복구된다(`store.rebuild_seen`). 다른 곳에 사본을 만들지 않는다.
7. **why는 짧다.** 240자 상한. 넘으면 자른다. 용량이 곧 이 방식의 존재 이유다.
8. **why의 출처를 `src`로 구분하고, 이유가 아닌 것은 recall에 넣지 않는다.**

   | `src` | 무엇 | conf | recall |
   | --- | --- | --- | --- |
   | `text` | 그 편집 직전의 말에서 고른 문장 | 0.7 | 넣는다 |
   | `asked` | 되물어 받은 이유 | 0.8 | 넣는다 |
   | `turn` | 그 턴의 사용자 요청. 이유가 아니라 맥락 | 0.2 | 뺀다 (review에만) |
   | `gc` | why를 비운 옛 레코드. 이력만 남았다 | - | 뺀다 |

   `thinking`은 출처가 될 수 없다 — transcript에 저장되지 않는다.
   `last_assistant_message`도 쓰지 않는다 — 턴 요약이라 편집과 무관하고 복제된다(Phase 4 실측).

9. **capture는 작업 파일을 읽지 않는다.** anchor는 `toolUseResult`로 복원한 "그 편집 시점의 내용"에
   건다. Stop은 턴 끝에 도니 디스크는 이미 더 고쳐져 있을 수 있다. 한 턴에 같은 파일을 세 번 고치면
   note도 세 개고, 각각 제 시점의 내용에 걸려야 한다.

## 시험 재료

| 용도 | 재료 | 위치 |
| --- | --- | --- |
| unit/golden test | 손으로 얼린 커널 스타일 C 표본 | `tests/corpus/` (커밋) |
| anchor 생존율 실측 | 실제 C 저장소 clone의 커밋을 replay | `.testrepos/` (gitignore) |
| end-to-end dogfood | 이 저장소 자신(Python) + clone한 C 저장소 | 해당 트리 |

`.testrepos/`에는 실측용 C 저장소를 `git clone`으로 떠 둔다(hardlink라 싸다). 이 디렉터리는
gitignore이고 **여기에는 codenotes를 걸지 않는다** — 시험 대상이지 작업 트리가 아니다.
남의 작업 트리에 직접 걸면 `.codenotes/`가 그쪽 브랜치에 섞인다.

## 이 저장소에서 하지 않는 것

- 다른 프로젝트의 `.claude/settings.json`을 내 판단으로 고치지 않는다. 설치는 `codenotes init`이 하고
  사용자가 실행한다.
- 에디터나 사람이 직접 고친 변경은 이유를 알 수 없으므로 잡지 않는다. 범위 밖이다.
- hook 동작을 바꾸면 `tests/fixtures/hook_input/`의 fixture를 함께 갱신한다. fixture는 손으로 쓰지 말고
  실제 hook 입력을 덤프해 받아 적는다.
- **`.testrepos/`에 codenotes를 걸지 않는다.** 여기는 시험 대상이지 작업 트리가 아니다.
  중첩 git 저장소, 생성 파일(`*.mod.c`), 빌드 산출물은 capture에서 제외한다.
