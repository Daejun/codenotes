# codenotes 개발 계획

판정의 주인은 이 파일이다. Phase가 끝나면 아래 "현재 상태"와 실측치를 고치고,
계약(명령, 구조, 스키마, 불변식)이 바뀌면 `CLAUDE.md`를 고친다. `CLAUDE.md`에는 Phase를 적지 않는다.

## 현재 상태 (2026-09-22)

**Phase 0-6 전부 완료.** loop를 일곱 바퀴 돌렸다. 코드 1,387줄, 테스트 42건.

| Phase | 결과 | log |
| --- | --- | --- |
| 0 hook 입력 실측 | 계획의 전제 둘이 무너짐 (thinking 없음, flush 전) | `logs/phase-0.md` |
| 1 capture | hook 3개 -> 2개, capture를 Stop으로 | `logs/phase-1.md` |
| 2 anchor | 50 커밋 뒤에도 96.4% 생존 | `logs/phase-2.md` |
| 3 recall | 편집 대상 symbol을 편집 전에 짚음, 14ms | `logs/phase-3.md` |
| 4 이유 품질 | 사람 판정 14% -> 55% | `logs/phase-4.md` |
| 5 review·검색 | 색인을 실측으로 뺌 | `logs/phase-5.md` |
| 6 설치·이식 | 다른 저장소에서 확인, plugin install은 미검증 | `logs/phase-6.md` |

남은 것은 `logs/phase-6.md`의 "검증하지 못한 것" 둘이다 — plugin install 경로와 장기 dogfood.

이미 있는 것:

| 경로 | 무엇 |
| --- | --- |
| `CLAUDE.md` | 구현 계약 |
| `PLAN.md` | 이 파일 |
| `tools/anchor_probe.py` | anchor 생존율 replay 하네스 |
| `docs/findings-anchor.md` | 실측 결과 |
| `.testrepos/` | 실측용 C 저장소 clone (gitignore) |
| `.gitignore` | `.testrepos/`, `index.sqlite`, `hook.log`, `__pycache__/` |
| `tools/phase0_dump.py` | Phase 0 계측 hook (Phase 1 시작 시 제거) |
| `.claude/settings.json` | Phase 0 계측 hook 등록 (Phase 1에서 `turn_capture.py`로 교체) |
| `docs/findings-hook-io.md` | Phase 0 실측 |
| `logs/phase-0.md` | Phase 0 log |
| `tests/corpus/gc_sample.c` | brace scan 시험용 C 표본 |

아직 없는 것: `codenotes/`, `hooks/`, `tests/test_*.py`.

## 작업 loop

Phase를 하나 끝낼 때마다 다음 Phase를 고쳐 쓴다. 계획은 착수 시점에 이미 낡아 있다는 전제다.

```
N = 0 에서 시작
  1. Phase N 수행. 하면서 logs/phase-N.md 를 쓴다 (한 일, 예상과 달랐던 것, 버린 것)
  2. 그 log를 근거로 Phase N+1 을 고친다 (PLAN.md 직접 수정)
  3. 고친 Phase N+1 을 아래 체크로 검토하고 보강한다
  4. N = N+1, 1로
```

step 1의 log는 결과 보고가 아니라 **다음 Phase를 고치기 위한 재료**다. 그래서 세 가지만 쓴다.
한 일, 예상과 달랐던 것(이게 제일 중요하다), 계획에서 빼기로 한 것과 그 이유.
측정 결과 자체는 `docs/findings-*.md`로 따로 나간다 — log는 짧게 유지한다.

step 3의 검토 항목. 하나라도 "아니오"면 그 Phase는 아직 착수하지 않는다.

1. 성공 기준이 **측정 가능한가.** "동작한다"가 아니라 숫자나 열어 볼 산출물인가
2. 전제가 Phase N의 log와 **모순되지 않는가**
3. 실패하면 **무엇을 버릴지** 정해져 있는가 (기능을 줄일 것인가, 접근을 바꿀 것인가)
4. 예산(지연, 용량, 코드량)이 적혀 있는가
5. 이 Phase가 없으면 다음 Phase가 막히는가 — 아니면 뒤로 미룬다

## 결정된 것

| 항목 | 결정 |
| --- | --- |
| 저장 형태 | 코드 파일마다 sidecar. `.codenotes/<소스 경로>.jsonl` (소스 트리 미러링) |
| git | **기본은 전부 gitignore.** `codenotes init --shared`로 켜면 JSONL을 커밋하고 `merge=union`을 건다 |
| why 출처 | PostToolUse에서 transcript 자동 추출 + Stop에서 보강 |
| 설치 | 프로젝트별 `.claude/settings.json`. 배포는 plugin(`claude plugin install --scope project`), `.codenotes/` 준비는 `codenotes init` |
| 구현 | python3 stdlib 전용, 의존성 0 |

## Phase 0 — 사실 확인 (완료, 2026-09-22)

결과: `docs/findings-hook-io.md`, log: `logs/phase-0.md`.
Phase 1 설계가 이 결과로 바뀌었다 — thinking은 transcript에 저장되지 않고,
PostToolUse 시점에는 해당 레코드가 아직 flush되지 않는다.

측정할 것:
1. **PostToolUse 시점에 transcript가 flush돼 있는가.** `tool_use_id`가 든 assistant 메시지를
   `transcript_path`에서 그 순간 읽을 수 있는지. 못 읽으면 why 1차 기록을 Stop으로 전부 옮겨야 한다.
2. 같은 메시지 안에 `thinking` 블록이 실제로 들어오는지, 아니면 `text`만 오는지.
3. `Edit`과 `Write`의 `tool_input` 차이, `file_path`가 최상위로 오는지.
4. 병렬 편집 시 `PostToolUse`가 편집마다 오는지, `PostToolBatch`가 더 나은 포착 지점인지.
5. hook 왕복 지연의 바닥값 (python3 기동 + json 파싱만 했을 때).

방법: 20줄짜리 덤프 hook(받은 stdin 전체 + transcript 마지막 50줄을 파일로 저장)을
codewriter의 `.claude/settings.json`에만 등록하고, 이 저장소에서 편집 5회.

산출물: `docs/findings-hook-io.md` 한 장 + `tests/fixtures/hook_input/*.json` (실제 입력 그대로).

## Phase 1 — 최소 왕복 (완료 일부, 2026-09-22)

결과: `logs/phase-1.md`. 성공 기준 1·2·4 통과, 3(출처 분포)·5(note 10건)는 표본 부족으로 미달 —
live hook이 켜졌으니 쌓이는 대로 낸다. 아래는 착수 시점의 계획 원문이다.

Phase 0이 설계를 바꿨다. capture는 PostToolUse가 아니라 **Stop**에서 한다.
근거는 셋이다 — PostToolUse 시점에 레코드가 flush 전이고(3줄 뒤), thinking은 어차피 빈 문자열이며,
`toolUseResult`가 `originalFile`과 `structuredPatch`를 그대로 들고 있어 그 턴의 편집을
Stop에서 patch까지 복원할 수 있다.

anchor는 파일 레벨만. symbol 판정 없음. 목표는 배관이 끝까지 이어지는 것.

- `codenotes/{config,record,store,extract}.py`, `hooks/turn_capture.py`
- **gate 0 — Stop payload를 먼저 확인한다.** Stop 시점에 그 턴의 tool_use/tool_result가
  flush돼 있다는 것은 아직 측정하지 않았다. 3줄 lag에서 추론했을 뿐이다.
  실제 Stop payload를 받아 확인하고, 아니면 이 Phase 전체를 다시 짠다.
- Stop capture 절차:
  1. `transcript_path`를 **watermark(마지막 처리 줄 offset, `.codenotes/`에 저장)부터** 읽는다.
     `prompt_id`로 턴을 자르지 않는다 — assistant 레코드에는 `promptId`가 없다(108건 전수 확인).
     전체를 훑고 `tid`로 거르면 인터럽트로 Stop이 빠진 턴도 다음 Stop이 자동으로 줍는다.
  2. Edit/Write `tool_use` 블록을 모은다 (블록은 `message.id` + `apiBlockIndex`로 묶인다)
  3. 짝이 되는 `toolUseResult`에서 `filePath`, `originalFile`, `structuredPatch`를 꺼낸다
  4. why를 붙인다 — 같은 `message.id`의 낮은 `apiBlockIndex` text 블록(`src:"text"`),
     없으면 턴 단위(`last_assistant_message` + 그 턴의 user prompt, `src:"turn"`)
  5. `tid`로 중복을 거르고 sidecar에 append
- `python3 -m codenotes show <file>`
- 예외 삼킴 + `hook.log`

성공 기준 (전부 수치나 열어 볼 산출물):

1. **놓친 편집 0건.** transcript의 Edit/Write `tool_use` 중 **제외 규칙을 통과한 것**의 개수와
   sidecar 레코드 개수가 같다. 분모에 `.testrepos/`, 생성 파일, 스크래치패드가 섞이면 기준이 무의미하다.
   세는 것까지 `codenotes doctor --audit <transcript>`로 만든다 — 눈으로 세지 않는다.
2. **`tid` 중복 0건.** 같은 턴에서 Stop이 두 번 떠도 레코드가 늘지 않는다.
3. **why 출처 분포를 낸다** — `src`가 `text` / `turn` 각각 몇 %인가. 이 숫자가 Phase 4를
   앞으로 당길지 말지를 정한다. Phase 0의 30%가 실제 note에서도 재현되는지 확인하는 자리다.
4. Stop hook 지연 중앙값 (예산 2,000ms — 턴당 1회라 PostToolUse보다 여유가 크다).
5. `show`로 열어 why 문자열 10건을 직접 읽는다. 열어 보지 않은 것은 "됐다"가 아니다.

실패 시 버릴 것: Stop 단독 capture가 편집을 놓치면(성공 기준 1 실패) PostToolUse에
`why` 없는 pending 레코드를 쓰고 Stop이 채우는 2단계로 되돌린다. 그때는 hook이 3개가 된다.

예산: 코어 300줄 이하. 넘으면 Phase 1 범위를 잘못 잡은 것이다.

여기서부터 codenotes를 자기 자신에게 켜 두고 개발한다 — 이후 Phase의 이유 기록이 곧 dogfood 데이터다.

## Phase 2 — anchor (완료, 2026-09-22)

결과: `docs/findings-anchor.md`, log: `logs/phase-2.md`. 성공 기준 4개 전부 통과.
50 커밋을 건너도 note의 96.4%가 제자리를 찾는다. 아래는 착수 시점의 계획 원문이다.

### 계획 원문

baseline은 이미 쟀다(`docs/findings-anchor.md`): 139개 커밋 쌍, 11,040건에서
1단계 94.3% / 2단계 5.1% / 유실 0.6%.

- **anchor를 걸 대상은 디스크가 아니라 복원한 "편집 후 내용"이다.** Phase 1 실측:
  `structuredPatch`는 탭을 공백으로 펴서 담아 내용 복원에 못 쓴다(줄 수·범위만 유효).
  `originalFile.replace(oldString, newString)`(Edit)과 `content`(Write)는 디스크와 정확히 일치했고
  연쇄 적용도 일치했다. 이 경로로 편집마다 그 시점 내용을 세워 anchor를 건다 —
  한 턴에 같은 파일을 여러 번 고쳐도 각 편집이 제 위치에 걸린다.
- `codenotes/anchor.py`: `.py`는 `ast`, C 계열은 brace scan, 나머지는 파일 레벨
- 정규화 해시(공백 접기), 4단계 해석 순서 — **3단계는 줄 창이 아니라 파일 전수 유사도**(개명 탐지)
- 매크로 생성 심볼, TRACE_EVENT 헤더, 생성 파일은 파일 레벨로 강등하거나 제외
- `codenotes doctor` (stale 비율 보고), `codenotes rebind <file>` (사람이 승인)

성공 기준:
1. `tools/anchor_probe.py`를 `codenotes/anchor.py`로 갈아끼워 다시 재서 유실률 0.6% 이하를 유지한다
2. 1스텝이 아니라 **N스텝 누적**으로 확장해 10/50/100 커밋 뒤의 유실률을 처음으로 낸다
3. 3단계(개명 탐지)가 1스텝 유실 69건 중 몇 건을 건지는지 수치로 낸다 — 못 건지면 3단계를 뺀다
4. **복원한 내용이 디스크와 일치하는지 매 편집마다 자체 검사한다.** 턴의 마지막 편집에 한해
   복원 결과와 디스크를 비교해 불일치 건수를 센다. 0이 아니면 anchor 전체를 믿을 수 없다

실패 시 버릴 것: 복원 경로가 어긋나면(성공 기준 4 실패) symbol anchor를 포기하고 파일 레벨로 남긴다.
줄 번호 힌트만 쓰는 Phase 1 상태가 곧 fallback이다.

예산: `anchor.py` 200줄 이하. 언어별 판정이 그보다 길어지면 tree-sitter 없이 할 일이 아니다.

## Phase 3 — 참조 경로 (완료, 2026-09-22)

결과: log `logs/phase-3.md`. 성공 기준 4개 전부 통과. 아래는 착수 시점의 계획 원문이다.

### 계획 원문

Phase 2가 recall의 키를 바꿨다. **파일 단위가 아니라 편집 대상 symbol 단위로 좁힌다.**
PreToolUse는 `tool_input.old_string`을 준다(Phase 0 fixture 확인). Edit은 정확 일치를 요구하므로
현재 파일에서 그 위치를 찾으면 어느 symbol을 고치려는지 편집 **전에** 알 수 있다.

- gate 0 — **통과 완료.** `symbols()` + 본문 해시가 <가장 큰 파일>(4,230줄)에서 1.4ms.
  PreToolUse 예산 300ms에 두 자릿수 여유다.
- `hooks/pre_edit_recall.py` + `codenotes/render.py`
- 절차:
  1. root 없으면 즉시 exit 0 (opt-in)
  2. `tool_input.file_path`의 sidecar를 읽는다. 없으면 exit 0
  3. `old_string`이 있으면 현재 파일에서 위치를 찾아 감싸는 symbol을 구한다.
     Write거나 `replace_all`이면 파일 단위로 남긴다
  4. 각 note의 anchor를 `resolve(deep=False)`로 현재 파일에 다시 건다
  5. 고르기: 같은 symbol 우선 > 최신 > conf 높은 순. superseded 제외, conf 0.3 미만 제외
  6. `hookSpecificOutput.additionalContext`로 내보낸다. `budget_chars` 상한

성공 기준:

1. **같은 symbol을 두 번째 고칠 때 첫 note가 주입된다.** 실제로 일으켜 주입된 문자열을 열어 본다.
2. **관련 없는 파일을 고칠 때 아무것도 주입하지 않는다.** 출력이 비고 exit 0.
3. **stale을 stale이라고 말한다.** `resolve`가 2단계(본문 변경)나 4단계(유실)로 떨어진 note는
   그 사실을 붙여 내보낸다. 옛 줄 번호를 사실처럼 말하면 모델을 오도한다 — 이게 가장 위험하다.
4. PreToolUse 지연 중앙값 (예산 300ms), 주입 문자 수 (예산 `budget_chars` 1,200).

실패 시 버릴 것: symbol 단위 좁히기가 어긋나면(1·2 실패) 파일 단위 recall로 되돌린다.
예산: `render.py` + hook 합쳐 150줄.

### dogfood 표본 문제

이 세션은 bypass 모드 지침대로 대부분의 파일을 **Bash heredoc으로** 쓴다. hook이 보는 것은
`Edit`/`Write` tool 호출뿐이라 note가 거의 안 쌓인다 — Phase 1 성공 기준 3(출처 분포)과
5(note 10건 읽기)가 미달인 진짜 이유가 이것이다.

그래서 **이 저장소의 파일은 `Edit`/`Write` tool로 고친다.** Bash는 조회와 실행에만 쓴다.
Phase 3이 끝날 때 다시 센다.

## Phase 4 — 이유 품질 (완료, 2026-09-22)

결과: log `logs/phase-4.md`. 사람 판정 쓸 만한 비율 14% -> 55%. 제품 정의는 지켰다.
되묻기(`ask_missing`)는 구현했고 기본값은 꺼 둔다 — 관행만으로 55%가 나온다.

### 계획 원문

배관은 다 됐다. 남은 문제는 하나다 — **잡힌 why가 이유가 아니라 진행 서술이다.**
Phase 1에서 잡은 실물이 이렇다.

> hook이 세션 재시작 없이 바로 먹었습니다. 이제 `Edit`의 입력 모양을 받기 위해 한 번 고칩니다.

Phase 0 실측: tool_use를 낸 message 40개 중 text를 동반한 것이 12개(30%).
`thinking`은 transcript에 없다. 자동 추출의 천장이 여기다.

### 먼저 잴 것 (Phase 1의 성공 기준 3·5를 여기서 갚는다)

1. `src` 분포 — `text` / `turn` 각각 몇 %. `codenotes stats`
2. **자동 판정 두 가지.** 사람이 읽기 전에 기계로 거른다.
   - why에 그 편집에 나온 **코드 식별자**가 하나라도 들어있는가
   - why가 **진행 서술**로 끝나는가 ("~하겠습니다", "~합니다", "확인", "봅니다")
3. 한 message에 편집이 여러 개일 때 **같은 text가 N개 note에 복제되는가**. 복제면 중복 제거 필요
4. 그 위에 note 30건을 직접 읽고 "이 자리를 다시 고칠 때 도움이 되는가"를 센다

### 손댈 곳 (위 수치를 보고 고른다)

- (a) text 블록 전체가 아니라 **그 편집과 관련된 문장만** 고른다 — 파일명·symbol명이 언급된 문장 우선
- (b) 한 message의 여러 편집이 같은 why를 공유하면 supersede가 아니라 **공유 표시**로 접는다
- (c) **Stop이 exit 2로 한 번 되묻는다.** 이유가 빈 편집이 있으면 턴을 이어 모델에게 한 줄씩 받는다.
      비용은 턴당 모델 왕복 1회. `stop_hook_active`로 무한 반복을 막는다(Phase 0에서 이 필드 확인)
- (d) CLAUDE.md 규칙으로 "편집 전 한 줄 이유"를 유도한다. 강제가 아니라 관행이고,
      그 text 블록은 실제로 저장되므로 (a)와 맞물린다

성공 기준:

1. 자동 판정 두 가지의 **착수 전후 수치**를 낸다. 식별자 포함률은 오르고 진행 서술률은 내려야 한다
2. note 30건 사람 판정에서 "도움이 된다"가 착수 전보다 늘어난다
3. (c)를 켰을 때와 껐을 때의 **턴당 추가 비용**을 실측한다 — 왕복 1회가 얼마인지 모르면 기본값을 못 정한다

실패 시 버릴 것: (a)(b)(d)로 품질이 안 나오고 (c)의 비용이 감당 안 되면,
note를 **"왜"가 아니라 "무엇을 바꿨나"** 중심으로 재정의한다. patch 요약은 자동으로 정확하게 나온다.
그때는 CLAUDE.md의 "이 저장소가 만드는 것"부터 고쳐야 한다 — 제품의 정의가 바뀌는 것이다.

예산: (c)는 opt-in. 기본값은 수치를 보고 정한다.

## Phase 5 — review와 검색 (완료, 2026-09-22)

결과: log `logs/phase-5.md`. 성공 기준 통과, 단 색인은 실측 결과 빼기로 했다
(현실 규모 1만 건에서 전수 스캔 1.8ms). 아래는 착수 시점의 계획 원문이다.

### 계획 원문

Phase 4가 재료를 정했다. **review에 내보낼 것은 `text`/`asked` note다.**
`turn`은 conf 0.2로 recall에서 빠지지만 review에서는 "어느 요청에서 나온 변경인가"를
말해 주므로 따로 묶어 보여준다 — 이유인 척하지 않게 구분한다.

- `codenotes review [--since <rev>] [--staged]`: 현재 diff에 걸린 note만 뽑는다.
  anchor를 `resolve`로 다시 걸어 **stale은 stale이라고 표시한다**(Phase 3과 같은 규칙)
- `git diff -M --name-status`로 rename 추적 -> sidecar 이동. Stop에서 자동, CLI로 수동
- `codenotes/index.py` FTS5 + `codenotes search`, `codenotes index --rebuild`
- `codenotes gc`: 같은 anchor의 note가 N개를 넘으면 오래된 것부터 접는다.
  **superseded는 지우지 않는다** — `sup` 사슬이 이력이다(불변식 6의 "진실은 sidecar 하나")

성공 기준:

1. `review --since <rev>`가 그 구간에서 바뀐 파일의 note만 낸다. 안 바뀐 파일은 0건
2. **rename 추적**: 파일을 `git mv`하면 sidecar가 따라간다. 옮긴 뒤 `show`가 note를 그대로 읽는다
3. `search`가 FTS5로 돈다. `index --rebuild` 후 건수가 sidecar 총 note 수와 같다
4. `index.sqlite`를 지워도 `--rebuild`로 완전히 복구된다 (불변식 6)
5. `gc` 후에도 `sup` 사슬을 따라 이력을 읽을 수 있다

실패 시 버릴 것: FTS5 색인이 sidecar 스캔보다 빠르지 않으면(note가 수천 건 규모라면
그냥 스캔이 빠를 수 있다) `index.py`를 통째로 뺀다. 먼저 재 보고 정한다.

예산: `index.py` 100줄, review/rename 합쳐 150줄.

## Phase 6 — plugin으로 포장하고 이식 (완료, 2026-09-22)

결과: log `logs/phase-6.md`. 다른 저장소에서 도는 것과 opt-in 격리를 확인했다.
`claude plugin validate` 통과, `install`은 검증하지 못했다.

### 계획 원문

hook 3개는 plugin의 `hooks/hooks.json`으로 옮긴다. `${CLAUDE_PLUGIN_ROOT}`를 쓰면 설치처마다
경로를 고쳐 쓸 필요가 없다. skill은 capture를 대신할 수 없고(세션 한정, invoke 의존)
해석 쪽만 맡는다 — `skills/codenotes-review/`.

- `.claude-plugin/plugin.json`: `userConfig`로 `budget_chars`, `why_max`, `ask_missing` 노출
  (hook 프로세스에는 `CLAUDE_PLUGIN_OPTION_*` 환경 변수로 들어온다 -> `config.json`의 절반을 대체)
- `hooks/hooks.json`, `bin/codenotes`, `skills/codenotes-review/`
- `codenotes init`: `.codenotes/`, `config.json`, `.gitattributes`(`merge=union`), `.gitignore`

성공 기준:

1. **`codenotes init`한 다른 저장소에서 편집하면 note가 잡힌다.** `.testrepos/<clone>`에 걸어
   실제로 고쳐 보고 `show`로 연다. 이 저장소 밖에서 도는 것을 처음 확인하는 자리다
2. **opt-in이 아닌 저장소는 아무 영향이 없다.** `.codenotes/`가 없는 곳에서 hook이 exit 0,
   출력 0 byte, 지연은 python 기동분뿐
3. **실측**: sidecar 총 용량, note 1건당 byte, 편집당 추가 지연
4. plugin 포장은 만들되, `claude plugin install`을 이 세션에서 검증할 수 없으면
   **검증하지 못했다고 적는다.** 돌려 보지 않은 것을 "된다"고 쓰지 않는다

실패 시 버릴 것: plugin 경로가 확인되지 않으면 `codenotes init`이 `.claude/settings.json`에
절대 경로를 직접 쓰는 방식만 남긴다. 그것은 Phase 0부터 실제로 돌고 있는 경로다.

예산: `init` 60줄, plugin 뼈대는 코드가 아니라 설정 파일.

## 위험과 대응

| 위험 | 대응 |
| --- | --- |
| transcript에 이유가 없다(도구만 연속 호출) | conf 0은 저장하지 않고 Stop 보강에 맡긴다 |
| 대규모 refactor 후 anchor 대량 유실 | `doctor`가 비율로 보고, `rebind`는 자동 실행하지 않는다 |
| 같은 함수 반복 수정으로 sidecar 비대 | supersede + `gc`, why 240자 상한 |
| sidecar merge 충돌 | append-only + `merge=union`, 레코드는 줄 단위로 독립 |
| hook 지연이 편집 흐름을 느리게 함 | Phase별로 실측 기록, 예산 초과 시 기능을 줄인다 |
| **자동 출처로는 이유가 안 나온다** (thinking 없음, tool_use message의 70%가 text 없음) | 턴 단위 why를 바닥값으로 깔고, Stop이 exit 2로 한 번 되묻는 경로를 Phase 4에서 검토. Phase 1의 출처 분포 수치로 Phase 4를 앞당길지 정한다 |
| Stop이 안 뜨면(사용자 인터럽트) 그 턴의 편집이 통째로 빠진다 | 다음 SessionStart/UserPromptSubmit이 미처리 턴을 줍는다. Phase 1에서 구멍 크기를 먼저 잰다 |
| bypass 모드에서 Bash heredoc으로 파일을 쓰면 hook이 못 본다 | 이 저장소 작업은 `Edit`/`Write` tool로 한다. 일반 사용자에게는 해당 없음 — 에이전트가 도구로 편집하는 것이 정상 경로다 |
| 사람이 에디터로 고친 변경은 못 잡는다 | 범위 밖으로 명시. 구멍이 있다는 사실을 문서에 남긴다 |
| plugin으로 싸면 hook 수정 왕복이 느려진다(`/reload-plugins`) | Phase 0-5는 `.claude/settings.json` 직접 등록으로 개발, 포장은 Phase 6 |

## 남은 질문 (구현하면서 정한다)

- 제외 규칙의 경계: `.gitignore`된 파일, 바이너리, 거대 파일. 확실한 것은 이미 나왔다 —
  중첩 git 저장소(`.testrepos/`), 생성 파일(`<mod>.mod.c`), 빌드 산출물(`*.o`)
- sidecar 경로에서 원본 확장자를 유지할 때 `foo.c.jsonl`과 `foo.h.jsonl` 충돌은 없지만,
  확장자 없는 파일과 디렉터리 이름이 겹치는 경우의 처리
- `Write`로 파일을 통째로 새로 쓸 때 anchor를 파일 레벨로 둘지 symbol별로 쪼갤지
