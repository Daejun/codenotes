#!/usr/bin/env python3
"""Stop hook. stdin 파싱과 종료 코드만 책임진다 — 로직은 codenotes 패키지에 있다.

종료 코드는 둘뿐이다.
  0  평소. 어떤 예외도 여기로 떨어진다 (불변식 1: note 시스템 고장이 작업 중단이 되면 안 된다)
  2  이유가 빈 편집이 있어 한 번 되묻는다. `ask_missing`이 켜져 있을 때만, 턴당 한 번만.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run():
    """돌려주는 값이 곧 종료 코드다."""
    raw = sys.stdin.read()
    if not raw.strip():
        return 0                    # 빈 stdin으로 불리는 경우가 실제로 있다 (Phase 0 실측)
    payload = json.loads(raw)
    from codenotes import ask, capture, config, store

    root = config.find_root(payload.get("cwd"))
    if not root:
        return 0                    # opt-in 아닌 프로젝트
    t0 = time.time()
    cfg = config.load(root)
    asked_turn = bool(payload.get("stop_hook_active"))

    # 되물어 받은 답이 먼저다. capture가 그 text를 새 note로 또 집기 전에 잇는다.
    joined = ask.apply(root, payload.get("last_assistant_message"), cfg) if asked_turn else 0

    stat = capture.run(payload)
    if stat.get("wrote") or joined:
        store.log(root, "%s capture %s joined=%d %.0fms" % (
            time.strftime("%Y-%m-%dT%H:%M:%S"), json.dumps(stat, ensure_ascii=False),
            joined, (time.time() - t0) * 1000))

    weak = stat.get("weak") or []
    if cfg.get("ask_missing") and weak and not asked_turn:
        sys.stderr.write(ask.prompt(weak))
        return 2
    return 0


try:
    code = run()
except Exception as exc:
    code = 0
    try:
        from codenotes import config, store
        root = config.find_root(os.getcwd())
        if root:
            store.log(root, "%s ERROR %s: %s" % (
                time.strftime("%Y-%m-%dT%H:%M:%S"), type(exc).__name__, exc))
    except Exception:
        pass
sys.exit(code)
