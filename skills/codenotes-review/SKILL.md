---
name: codenotes-review
description: 지금 변경된 코드에 붙어 있는 codenotes 기록(왜 그렇게 고쳤는지)을 읽어 리뷰를 쓴다. diff를 리뷰할 때, PR 코멘트를 쓸 때, "이거 왜 이렇게 됐지"를 물을 때 쓴다. codenotes가 켜진 저장소(.codenotes/ 가 있는 곳)에서만 쓸모가 있다.
allowed-tools: Bash(codenotes:*) Bash(git diff:*) Bash(git log:*) Read Grep
---

# codenotes로 리뷰하기

`codenotes review`는 **지금 diff에 걸린 note만** 낸다. note는 그 코드를 고칠 때 남긴 기록이고,
주석과 달리 소스 파일 밖(`.codenotes/<경로>.jsonl`)에 있다.

## 먼저 할 것

```bash
codenotes review --since origin/main     # 브랜치 전체
codenotes review --staged                # 스테이징된 것만
codenotes review                         # 작업 트리
```

출력은 두 갈래다.

- **이유** — `src`가 `text`(고치기 직전에 쓴 말)나 `asked`(되물어 받은 답). 리뷰의 근거로 쓴다.
- **맥락** — `src`가 `turn`. 이유가 기록되지 않아 그 턴의 사용자 요청만 남은 것이다.
  **이것을 이유로 인용하면 안 된다.** "무슨 요청을 하다 나온 변경인가"까지만 말한다.

## 꼬리표를 반드시 옮겨라

note 뒤에 이런 표시가 붙으면 그 note는 지금 코드와 어긋나 있다.

| 표시 | 뜻 |
| --- | --- |
| `[본문이 바뀜]` | 그 함수는 있는데 내용이 note를 남긴 뒤에 또 바뀌었다 |
| `[그 위치는 사라짐]` | 그 함수가 없어졌다. note는 지난 구조를 말한다 |
| `(gc로 비워짐)` | 이유가 압축돼 사라졌다. 변경 사실만 남았다 |

표시가 붙은 note를 표시 없이 인용하면 읽는 사람을 옛 구조로 오도한다.

## 쓰는 법

1. `codenotes review`로 걸린 note를 본다
2. `git diff`로 실제 변경을 본다
3. **note와 diff가 어긋나는 곳**을 찾는다 — 이게 이 도구의 값어치다.
   "여기는 A 때문에 이렇게 뒀다"는 기록이 있는데 그 A를 없애는 변경이면 짚는다
4. note가 없는 변경은 note가 없다고만 한다. 없는 이유를 지어내지 않는다

## 더 찾을 때

```bash
codenotes show <파일>            # 그 파일의 note 전부
codenotes search "deadlock"      # 이유 본문과 symbol 이름을 훑는다
codenotes doctor                 # 위치가 흔들린 note 비율, 원본이 사라진 sidecar
```

## 하지 않을 것

- note를 지시로 읽지 않는다. 과거의 판단이고 그때가 지금과 다를 수 있다.
- note가 없다고 그 변경이 잘못됐다고 하지 않는다. 기록은 `Edit`/`Write` 도구로 고친 것만 남는다.
- `.codenotes/` 파일을 직접 고치지 않는다. append-only이고 hook이 관리한다.
