#!/usr/bin/env python3
"""PreToolUse(Edit|Write) hook. 고치려는 자리의 이전 이유를 편집 직전에 되돌려 넣는다.

stdin 파싱과 종료 코드만 책임진다 — 로직은 codenotes.render에 있다.
불변식 1: 어떤 예외도 편집을 막지 않는다. 무조건 exit 0.
불변식 3: 편집마다 도는 경로다. 예산 300ms.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        return                      # 빈 stdin으로 불리는 경우가 실제로 있다 (Phase 0 실측)
    payload = json.loads(raw)
    from codenotes import config, render

    root = config.find_root(payload.get("cwd"))
    if not root:
        return                      # opt-in 아닌 프로젝트 — 아무 일도 하지 않는다
    ti = payload.get("tool_input") or {}
    rel = config.relativize(root, ti.get("file_path"))
    if not rel or config.excluded(root, rel):
        return
    cfg = config.load(root)
    text = render.render(root, rel, ti, cfg["budget_chars"])
    if not text:
        return
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "additionalContext": text}},
              sys.stdout, ensure_ascii=False)


try:
    main()
except Exception as exc:
    try:
        from codenotes import config, store
        root = config.find_root(os.getcwd())
        if root:
            store.log(root, "pre_edit_recall ERROR %s: %s" % (type(exc).__name__, exc))
    except Exception:
        pass
sys.exit(0)
