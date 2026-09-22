# Phase 6 log

## 한 일

`codenotes/init.py` — 저장소를 opt-in시킨다. `.codenotes/`, `config.json`, `.gitignore`,
`.gitattributes`, `.claude/settings.json`(기존 hook을 지우지 않고 병합).
`bin/codenotes` 실행기. plugin 포장 — `.claude-plugin/plugin.json`, `hooks/hooks.json`,
`skills/codenotes-review/SKILL.md`. `userConfig`가 `CLAUDE_PLUGIN_OPTION_*`로 hook에 들어오게 연결.

성공 기준:

| 기준 | 결과 |
| --- | --- |
| 1 다른 저장소에서 도는가 | 통과. `.testrepos/<clone>`에 `init` -> 편집 -> capture -> `show`까지 |
| 2 opt-in 아닌 곳은 무영향 | 통과. `<사내 저장소>`에서 exit 0, 출력 0 byte, 16~19ms, 디렉터리 안 생김 |
| 3 실측 | 아래 |
| 4 plugin 설치 검증 | **부분.** `claude plugin validate .` 통과. `install`은 검증하지 못했다 |

## 실측

| | |
| --- | --- |
| note | 22건, sidecar 11개 |
| note 1건당 | 398 byte |
| sidecar 합계 대 소스+문서 | 10,101 byte / 106,685자 = **9.47%** |
| PreToolUse (편집마다) | 중앙값 **14ms** (예산 300ms) |
| Stop (턴당 1회) | 중앙값 **20ms** (예산 2,000ms) |
| 코드 | 1,387줄, 테스트 42건 |

`src` 분포: `text` 59.1% / `turn` 31.8% / `asked` 9.1%.

## 예상과 달랐던 것

1. **저장소 root가 곧 plugin root다.** plugin이 `codenotes` 패키지를 들고 가야 하는데
   `${CLAUDE_PLUGIN_ROOT}`가 plugin 디렉터리를 가리키므로, 저장소에 `.claude-plugin/`과
   `hooks/hooks.json`을 얹으면 그대로 plugin이 된다. 따로 포장 디렉터리를 만들 이유가 없었다.
2. **CLI가 다른 저장소에서 죽었다.** `python3 -m codenotes`는 cwd에 패키지가 있어야 한다.
   `bin/codenotes`가 `realpath(__file__)`로 체크아웃을 찾아 `sys.path`에 넣는다. 9줄.
3. **`claude plugin validate`가 있다.** manifest와 구성 요소를 검사해 준다. 경고 하나가 남는데
   맞는 경고다 — "plugin root의 CLAUDE.md는 컨텍스트로 안 실린다. skill을 써라."
   우리 CLAUDE.md는 이 저장소의 개발 계약이지 plugin이 싣는 컨텍스트가 아니고,
   plugin이 싣는 것은 `skills/codenotes-review/SKILL.md`다. 의도대로다.
4. **sidecar가 소스의 9.47%다.** 작지 않다. note는 편집마다 늘고 소스는 그만큼 안 는다.
   오래 쓰면 `gc`가 필수다. "주석과 달리 용량 문제가 없다"는 처음 전제는 **소스 파일이
   안 커진다**는 뜻이지 저장소가 안 커진다는 뜻이 아니었다. 문서를 그렇게 고쳐야 한다.

## 검증하지 못한 것

- `claude plugin install codenotes --scope project`. marketplace 없이 로컬 디렉터리를
  설치하는 경로를 이 세션에서 찾지 못했다(`plugin details`는 설치된 것만 본다).
  **돌려 보지 않았으므로 된다고 쓰지 않는다.** 실제로 돌고 있는 것은 Phase 0부터 쓰던
  `.claude/settings.json` 직접 기록 방식이고, `codenotes init`이 그것을 쓴다.
- 다른 저장소에서의 장기 dogfood. 시험용 clone에서 편집 1건을 흉내내 왕복만 확인했다.

## 버린 것

- 별도 plugin 포장 디렉터리. 1번.
