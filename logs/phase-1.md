# Phase 1 log

## 한 일

gate 0 통과 — Stop 시점 transcript 414줄, 같은 턴의 Write(288줄)와 Edit(305줄)이 모두 flush돼 있었다.

`codenotes/{config,store,extract,record,capture}.py` + `hooks/turn_capture.py` + CLI(`show`,
`stats`, `doctor --audit`)를 썼다. 계측 hook `tools/phase0_dump.py`를 지우고 `.claude/settings.json`을
Stop 하나로 교체했다. 테스트 10건.

성공 기준:

| 기준 | 결과 |
| --- | --- |
| 1 놓친 편집 0건 | 통과. `doctor --audit` 기준 편집 2건 = sidecar 2건, 놓침 0 |
| 2 `tid` 중복 0건 | 통과. 같은 Stop payload를 3회 돌려도 레코드 2건 그대로 |
| 3 why 출처 분포 | **미달.** 표본이 2건뿐이고 둘 다 `text`. Phase 0의 30%가 재현되는지 확인 못 함 |
| 4 Stop 지연 | 통과. watermark 0(최악, 1.3MB/509레코드) 전수 스캔 중앙값 4ms. 예산 2,000ms |
| 5 note 10건 읽기 | **미달.** 2건뿐 |

3번과 5번은 live hook이 켜졌으니 세션이 이어지면서 쌓인다. 그때 낸다.

## 예상과 달랐던 것

1. **`structuredPatch`는 내용 복원에 쓸 수 없다.** 탭이 공백으로 펴져 들어온다 —
   원본이 `\tunsigned int zone;`인데 패치 줄은 `'   unsigned int zone;'`이다.
   줄 수와 줄 범위만 유효하다. 이걸로 파일을 되살리면 693자짜리가 709자가 된다.
2. **`oldString`/`newString`은 정확하다.** `originalFile.replace(oldString, newString)`이
   디스크와 정확히 일치했고, Write의 `content`에서 시작해 Edit을 연쇄 적용해도 일치했다.
   Phase 2의 anchor는 이 경로로 편집 후 내용을 복원한다. 디스크를 읽지 않는다.
3. **새 파일 Write는 `structuredPatch`가 빈 배열이고 `type`이 `"create"`, `originalFile`이 None이다.**
   변경량을 `content` 줄 수로 보정했다.
4. **why 품질 문제가 실물로 보인다.** 잡힌 note 두 건이 이렇다.
   > hook이 세션 재시작 없이 바로 먹었습니다. 이제 `Edit`의 입력 모양을 받기 위해 한 번 고칩니다.
   편집한 이유가 아니라 진행 서술이다. 배관은 됐고 내용이 문제다.
5. 레코드 1건당 443 byte. why 240자 상한이 대부분을 차지한다.
6. 코어가 396줄로 예산 300줄을 넘었다. 줄인다면 `store.py`의 state 처리다.

## 버린 것

- **PostToolUse pending 2단계 회귀안.** 성공 기준 1이 통과해서 발동하지 않았다. 필요해지면 되살린다.
- **`structuredPatch`로 내용 복원.** 1번 때문에 근거가 없다.

## step 3 검토가 잡은 것 (Phase 2 보강)

1. **Phase 2의 전제를 미리 깼다.** "`structuredPatch`로 편집 후 내용을 복원한다"는 Phase 1 착수 시점의
   계획이었는데, 실제로 돌려 보니 탭이 공백으로 펴져 복원이 어긋났다(693자 -> 709자).
   `oldString`/`newString` 경로로 바꾸고 실측으로 확인했다. 검토가 아니라 착수 전 측정이 잡았다.
2. **성공 기준을 하나 더 달았다** — 복원 결과와 디스크의 불일치 건수. 0이 아니면 symbol anchor를
   통째로 믿을 수 없으므로, 이건 Phase 2의 다른 어떤 수치보다 먼저 봐야 한다.
3. **실패 시 버릴 것과 예산이 없었다.** symbol anchor 포기 시 파일 레벨(=Phase 1 상태)이 fallback,
   `anchor.py` 200줄 상한을 박았다.
