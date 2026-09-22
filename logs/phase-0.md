# Phase 0 log

## 한 일

`tools/phase0_dump.py`를 `.claude/settings.json`에 PreToolUse/PostToolUse/PostToolBatch/Stop으로
걸고, `Write` 1회 + `Edit` 1회를 실제로 일으켜 입력을 받았다. 측정치는 `docs/findings-hook-io.md`.

`git init`, `logs/`, `tests/corpus/gc_sample.c`(brace scan 시험용 C 표본)를 만들었다.

## 예상과 달랐던 것

1. **`thinking` 본문이 transcript에 저장되지 않는다.** 빈 문자열에 signature만 붙는다.
   계획의 1차 why 출처가 통째로 없어졌다. 이것 하나로 Phase 1 설계가 바뀐다.
2. **PostToolUse 시점에 그 tool_use 레코드가 아직 flush되지 않았다.** 두 사례 모두 3줄 뒤에 쓰였다.
   thinking이 살아 있었더라도 PostToolUse에서는 못 읽었다는 뜻이다.
3. **tool_use를 낸 message 40개 중 text 블록을 동반한 것이 12개(30%)뿐이다.**
   연속 도구 호출 구간에는 글자가 한 자도 없다. 남은 유일한 자동 출처마저 70%가 빈다.
4. **`tool_response.structuredPatch`와 `originalFile`이 공짜로 온다.** diff를 계산할 이유가 없다.
   같은 것이 transcript의 `toolUseResult`에도 남아서, Stop 하나로 그 턴의 편집을 전부 복원할 수 있다.
5. `file_path`가 최상위에 오지 않는다(공식 문서와 다름). `PostToolBatch`의 키는 `tool_calls`다.
6. `.claude/settings.json` 변경이 세션 중간에 즉시 먹는다. 재시작이 필요 없다.
7. hook 1회가 3.1ms다. 예산 걱정은 접어도 된다.

## 버린 것

- **"PostToolUse에서 thinking을 잘라 why 1차 기록"** — 근거가 사라졌다. 2번, 1번.
- **hook 3개 구성(Pre/Post/Stop)** — capture를 PostToolUse에 둘 이유가 없어졌다.
  4번 때문에 Stop 하나가 그 턴의 편집을 patch까지 복원한다. capture는 Stop으로 합친다.
- **`conf` 0 레코드를 버린다는 불변식** — 70%가 빈다는 3번 앞에서 이 규칙은 note의 70%를 버린다.
  turn 단위 why(사용자 prompt + `last_assistant_message`)를 바닥값으로 깔고 `src`로 구분한다.
- **직접 diff 계산** — 4번.

## 다음 Phase에 남기는 질문

- 자동 출처로는 이유가 안 나온다. 모델에게 **시키는** 경로가 필요하다.
  Stop은 exit 2로 턴을 이어붙일 수 있다 — 이유가 빈 편집이 있으면 한 번만 되묻는 방식.
  비용이 턴마다 모델 왕복 1회다. 기본값으로 둘지 opt-in으로 둘지 Phase 1에서 재본다.
- Stop이 안 뜨는 경우(사용자 인터럽트)의 미처리 편집을 누가 줍는가.

## step 3 검토가 잡은 것 (Phase 1 보강)

1. **미검증 전제.** "Stop 시점에는 flush돼 있다"를 3줄 lag에서 추론만 했다. Phase 0에서 Stop
   덤프를 못 받았다 — hook을 턴 중간에 걸어서 Stop이 아직 안 떴다. Phase 1의 gate 0으로 올렸다.
2. **성공 기준의 분모가 틀렸다.** "transcript의 Edit/Write 개수"가 아니라 "제외 규칙을 통과한
   Edit/Write 개수"다. `.testrepos/`나 스크래치패드 편집이 분모에 섞이면 기준이 무의미해진다.
3. **`prompt_id`로 턴을 자를 수 없다.** assistant 레코드에 `promptId`가 없다(108건 전수 false).
   `user` 레코드에만 있다(59건 전수 true). watermark + `tid` dedup으로 바꿨다 —
   인터럽트로 Stop이 빠진 턴을 다음 Stop이 자동으로 줍는 이점이 따라온다.
   위험 표의 "Stop이 안 뜨면 그 턴이 빠진다"가 이것으로 절반 해결된다.
