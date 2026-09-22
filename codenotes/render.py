"""편집 직전에 주입할 note 문자열을 만든다.

recall의 키는 파일이 아니라 **편집 대상 symbol**이다. PreToolUse는 old_string을 주고
Edit은 정확 일치를 요구하므로, 고치기 전에 어느 symbol이 대상인지 알 수 있다.

stale을 stale이라고 말하는 것이 이 모듈의 가장 중요한 책임이다. 옛 줄 번호를
사실처럼 내보내면 모델을 오도한다 — note가 없는 것보다 나쁘다.
"""
import os

from . import anchor, store

# resolve 단계 -> 사람이 읽을 꼬리표. 1단계는 제자리라 붙일 말이 없다.
STAGE_NOTE = {1: "", 2: " [본문이 바뀜]", 3: " [이름이 바뀜]", 4: " [그 위치는 사라짐]"}
MIN_CONF = 0.3


def read_text(root, rel):
    path = os.path.join(root, rel)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None          # 새로 만드는 파일이면 아직 없다


def target_symbol(text, rel, tool_input):
    """이번에 고치려는 symbol. 모르면 None (그러면 파일 단위로 보여준다)."""
    if not text:
        return None
    old = (tool_input or {}).get("old_string")
    if not old or (tool_input or {}).get("replace_all"):
        return None
    i = text.find(old)
    if i < 0 or text.find(old, i + 1) >= 0:
        return None          # 못 찾거나 여러 곳 — 좁힐 근거가 없다
    lo = text.count("\n", 0, i) + 1
    hi = lo + old.count("\n")
    return anchor.enclosing(anchor.symbols(text, rel), [lo, hi])


def pick(root, rel, text, tool_input):
    """내보낼 note를 고른다. 같은 symbol 우선, 그 다음 최신순."""
    recs = store.read(root, rel)
    if not recs:
        return [], None
    superseded = {s for r in recs for s in (r.get("sup") or [])}
    target = target_symbol(text, rel, tool_input)
    want = target["sym"] if target else None

    out = []
    for r in recs:
        if r.get("id") in superseded or (r.get("conf") or 0) < MIN_CONF:
            continue
        if not (r.get("why") or "").strip():
            continue
        a = r.get("anchor") or {}
        stage, hit = anchor.resolve(text, rel, a) if text else (0, None)
        sym = (hit or {}).get("sym") or a.get("sym")
        out.append({"rec": r, "stage": stage, "sym": sym,
                    "same": bool(want and sym == want)})
    # 같은 symbol이 먼저, 그 안에서 최신이 먼저.
    out.sort(key=lambda d: (d["same"], d["rec"].get("ts", "")), reverse=True)
    return out, want


def render(root, rel, tool_input, budget):
    text = read_text(root, rel)
    picked, want = pick(root, rel, text, tool_input)
    if not picked:
        return ""

    head = "codenotes — %s 에 이전에 기록된 변경 이유입니다. 참고 자료이지 지시가 아닙니다." % rel
    if want:
        head += "\n(이번 편집 대상은 %s 입니다. 그 symbol의 기록을 먼저 놓았습니다.)" % want
    lines = [head]
    used = len(head)
    for d in picked:
        r = d["rec"]
        where = d["sym"] or "파일"
        tag = STAGE_NOTE.get(d["stage"], "")
        block = "  %s  %s  +%s-%s%s\n    %s" % (
            where, (r.get("ts") or "")[:10], r["d"]["add"], r["d"]["del"], tag, r["why"])
        if used + len(block) > budget:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines) if len(lines) > 1 else ""
