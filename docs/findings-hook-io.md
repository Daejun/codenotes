# Phase 0 — hook 입력 실측

측정일 2026-09-22. Claude Code 2.1.272, 이 저장소에서 `Write` 1회 + `Edit` 1회.
계측 hook은 받은 stdin 전체를 파일로 떨구는 20줄짜리였고 Phase 0이 끝나며 지웠다.
그때 받은 실제 입력은 `tests/fixtures/hook_input/`에 남겼다 — 그것이 지금 테스트의 재료다.

## 판정

**PostToolUse에서 why를 뽑을 수 없다.** 두 가지가 겹친다.

1. PostToolUse 시점에 그 `tool_use_id` 레코드가 transcript에 **아직 없다.**
   | tool | hook이 본 줄수 | 레코드가 실제로 쓰인 줄 |
   | --- | --- | --- |
   | Write `toolu_01V1byES4skb…` | 285 | 288 |
   | Edit `toolu_01SQ8Gqc3b8G…` | 302 | 305 |
   두 번 다 3줄 뒤. hook이 돌 때 그 턴의 블록들은 아직 flush 전이다.

2. flush된 뒤에도 **`thinking` 본문이 없다.** 블록은 남지만 `thinking`은 빈 문자열이고
   `signature`만 2,532~4,916 byte로 붙는다. 추론 내용은 transcript에 저장되지 않는다.

남는 why 후보는 `text` 블록뿐인데 이것도 부족하다. 이 세션 최근 구간에서
**tool_use를 포함한 assistant message 40개 중 text 블록을 동반한 것은 12개(30%)**다.
나머지 70%는 연속 도구 호출이라 글자가 한 자도 없다. 동반한 12개도 내용이 이유가 아니다 —
이번 Edit에 붙은 text 전문은 다음 한 줄이었다.

> hook이 세션 재시작 없이 바로 먹었습니다. 이제 `Edit`의 입력 모양을 받기 위해 한 번 고칩니다.

## transcript 구조

한 API message가 **블록마다 한 레코드**로 쪼개져 들어간다. 묶는 키는 `message.id`,
순서는 `apiBlockIndex`, 사슬은 `parentUuid`.

```
msg_011CfJTqvNXTaTgqSaX4WJYm
  apiBlockIndex 0  thinking   (thinking="" , signature 4520B)
  apiBlockIndex 1  text       ("...")
  apiBlockIndex 2  tool_use   (id=toolu_012NCqYvTxXcxYGzRxe29XEy)
```

즉 "같은 메시지의 앞선 블록"은 `message.id`가 같고 `apiBlockIndex`가 작은 레코드들이다.
모호함이 없는 깨끗한 키다.

## 실제 payload

`PostToolUse` 최상위 키:
`cwd duration_ms effort hook_event_name permission_mode prompt_id scratchpad_dir
session_id tool_input tool_name tool_response tool_use_id transcript_path`

- **`file_path`는 최상위에 오지 않는다.** 공식 문서 표와 다르다. `tool_input.file_path`를 써야 한다.
- 문서에 없는 것이 온다: `scratchpad_dir`, `effort`, `permission_mode`, `duration_ms`.
- `PostToolBatch`의 배열 키는 `tool_calls`다(문서는 `tools`). matcher를 안 주면 Bash 호출에도 붙는다.

`tool_input` / `tool_response` 키:

| tool | tool_input | tool_response |
| --- | --- | --- |
| Write | `content`, `file_path` | `content`, `filePath`, `originalFile`, `structuredPatch`, `type`, `userModified` |
| Edit | `file_path`, `old_string`, `new_string`, `replace_all` | `filePath`, `oldString`, `newString`, `originalFile`, `replaceAll`, `structuredPatch`, `userModified` |

`structuredPatch`는 hunk 배열이고 `{oldStart, oldLines, newStart, newLines, lines[]}`를 준다.
`originalFile`은 **편집 전 파일 전체**다(이번 Edit: 648 byte, 편집 후 실제 파일 791 byte).
diff를 직접 계산할 필요가 없다.

같은 내용이 transcript의 `toolUseResult`에도 그대로 남는다. 즉 **Stop 시점에 그 턴의 모든 편집을
patch까지 복원할 수 있다.**

## 그 밖에

- `.claude/settings.json`에 hook을 추가하면 **세션 재시작 없이 즉시 적용된다.**
- hook 1회 비용: python3 기동 + json 파싱 + 302줄 transcript 역방향 스캔에 **3.1~3.2ms**.
  예산(PostToolUse 500ms)에 비해 두 자릿수 여유가 있다.
- `tests/corpus/gc_sample.c`를 만들자 clangd가 진단 10건을 띄웠다. 시험용 표본 파일은
  compile database에서 빼야 한다.
- 전역 `~/.claude/settings.json`의 `PostToolUse(Write|Edit|MultiEdit)` checkpatch hook이 같이 뜨지만
  커널 트리가 아니면 즉시 exit 0이라 간섭하지 않는다.

## 덧 — 빈 stdin

계측 중 hook이 **stdin이 완전히 빈 채로** 한 번 호출됐다. 이벤트 이름조차 없었다.
hook은 이 경우에도 exit 0으로 살아남아야 한다.
`json.loads("")`는 예외를 던지므로 파싱을 반드시 감싼다.
