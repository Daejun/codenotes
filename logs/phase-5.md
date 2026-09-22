# Phase 5 log

## 한 일

`codenotes/review.py`(120줄) — review, 검색, rename 추적, gc.
CLI를 `show / review / search / stats / mv / gc / doctor`로 다시 짰다.
rename 추적을 Stop에 연결했다. 테스트 42건.

성공 기준:

| 기준 | 결과 |
| --- | --- |
| 1 review가 바뀐 파일의 note만 | 통과. 변경 0개일 때 0건, `gc_sample.c`만 고치니 그 파일 2건 |
| 2 rename 추적 | 통과. `git mv` 후 `doctor`가 잡고 `mv`로 따라가니 `show`가 그대로 읽는다 |
| 3 search | 통과. 색인 없이 전수 스캔 |
| 4 index 재생성 | **해당 없음 — 색인을 뺐다** (아래) |
| 5 gc가 `sup` 사슬을 지킴 | 통과. 22건에서 451자 회수, 레코드는 하나도 안 지워짐 |

## 예상과 달랐던 것

1. **FTS5 색인을 넣지 않기로 했다.** 계획의 실패 조항("스캔보다 빠르지 않으면 뺀다")을
   재 보니 애매했다 — 드문 질의에서는 확실히 빠르다.

   | note | 전수 스캔 | FTS5 | 색인 비용 |
   | --- | --- | --- | --- |
   | 10,000 | 1.8ms | 0.13ms | 36ms / 1.8MB |
   | 50,000 | 8.5ms | 0.14ms | 121ms / 9.8MB |
   | 200,000 | 34.1ms | 0.31ms | 476ms / 37.1MB |

   200배 빠르지만 **현실 규모에서 스캔이 1.8ms다.** CLI 한 번에 1.8ms면 색인을 동기화하고
   재생성하고 stale을 걱정할 값어치가 없다. `index.py`를 통째로 빼고 불변식 6을
   "진실은 sidecar 하나"로 더 단단하게 고쳤다. note 5만 건을 넘으면 다시 본다.
2. **gc는 레코드를 지우면 안 된다.** 부피의 대부분이 `why`(240자 상한)이므로
   `why`만 비우면 `sup` 사슬과 "무엇이 언제 바뀌었나"를 지키면서 줄어든다. 22건에서 451자.
3. **rename 순서가 중요하다.** 옮기기 전에 append하면 sidecar가 두 군데로 갈라진다.
   Stop에서 rename을 **먼저** 따라가고 그 다음 capture한다.
4. **`git mv`만 잡힌다.** `git status --porcelain -M`은 staged rename만 보고한다.
   평범한 `mv`는 못 잡고 `doctor`가 orphan sidecar로만 보고한다. 한계로 남긴다.
5. **CLAUDE.md가 코드와 어긋나 있었다.** `post_edit_capture.py`(Phase 1에서 사라진 이름),
   `show --symbol`(없는 옵션), `pre_edit_c.json`(없는 fixture)이 명령 예시에 남아 있었다.
   계약 문서는 Phase가 바뀔 때마다 같이 안 고치면 조용히 거짓말이 된다.

## 버린 것

- **`codenotes/index.py`.** 1번. 계획에 있던 모듈 하나를 통째로 안 만들었다.
- **`codenotes index --rebuild` 명령**과 `.codenotes/index.sqlite` 경로.

## step 3 검토가 잡은 것 (Phase 6 보강)

1. **"1주 dogfood"는 이 세션에서 검증할 수 없다.** 성공 기준에서 빼고, 대신 `.testrepos/<clone>`에
   실제로 걸어 이 저장소 밖에서 도는 것을 확인하는 것으로 바꿨다.
2. **plugin 설치를 검증할 수 없으면 그렇게 적는다.** `claude plugin install`을 이 세션에서
   돌릴 수 없으므로 "돌려 보지 않은 것을 된다고 쓰지 않는다"를 성공 기준 4로 올렸다.
3. **실패 시 버릴 것이 이미 검증된 경로다.** plugin이 안 되면 `.claude/settings.json` 직접
   기록만 남기면 된다 — Phase 0부터 실제로 돌고 있는 방식이다. 위험이 낮다.
