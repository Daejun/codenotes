"""이유가 비어 있을 때 Stop이 한 번 되묻고, 답을 기존 note에 잇는다.

자동 추출의 천장이 낮아서 필요한 경로다 — `thinking`은 저장되지 않고, 편집 직전에
글자가 없는 턴이 많다. 비용은 턴당 모델 왕복 1회라 기본값은 꺼 둔다(`ask_missing`).

덮어쓰지 않는다. hook 경로는 append만 한다(불변식 4). 답으로 받은 이유는 새 레코드로
쌓고 `sup`으로 앞 레코드를 대체 표시한다. 이력은 지우지 않는다.
"""
import re

from . import record, store

WEAK_SRC = "turn"          # 이유가 비어 요청문으로 때운 레코드
MARK = "codenotes:"
# "codenotes: <경로> — <이유>" 한 줄. 구분자는 em dash, 콜론, 하이픈 아무거나 받는다.
LINE = re.compile(r"^\s*" + MARK + r"\s*(\S+?)\s*[—:\-]\s*(.+?)\s*$")


def prompt(weak):
    """되물을 말. 형식을 정확히 알려 주지 않으면 파싱할 수 없다.

    파일 하나당 한 번만 묻는다. 답은 경로로 찾아 붙이므로 같은 파일을 두 번 물어도
    답을 하나밖에 못 받는다 — 그 파일의 가장 최근 turn 레코드에 붙는다.
    """
    seen, uniq = set(), []
    for w in weak:
        if w["rel"] in seen:
            continue
        seen.add(w["rel"])
        uniq.append(w)
    items = "\n".join("  - %s%s" % (w["rel"], (" (%s)" % w["sym"]) if w.get("sym") else "")
                      for w in uniq)
    return (
        "codenotes: 아래 편집의 이유가 기록되지 않았습니다. 왜 고쳤는지를 한 줄씩 적어 주세요.\n"
        "%s\n"
        "형식은 정확히 이렇게, 한 줄에 하나씩입니다.\n"
        "  codenotes: <파일 경로> — <무엇이 잘못됐는지>\n"
        "무엇을 했는지가 아니라 무엇이 잘못됐는지를 씁니다. 이 줄 외의 답은 평소대로 쓰면 됩니다."
        % items)


def parse(message):
    """모델의 답에서 (경로, 이유)를 뽑는다."""
    out = []
    for ln in (message or "").split("\n"):
        m = LINE.match(ln)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def apply(root, message, cfg):
    """받은 이유를 그 파일의 가장 최근 turn 레코드에 잇는다. 이은 건수를 돌려준다."""
    pairs = parse(message)
    if not pairs:
        return 0
    done = 0
    for rel, why in pairs:
        recs = store.read(root, rel)
        # 이유가 빈 것은 turn 뿐이다. asked는 이미 답을 받은 것이고 text는 애초에 이유가 있다.
        weak = [r for r in recs if r.get("src") == WEAK_SRC]
        sup = {s for r in recs for s in (r.get("sup") or [])}
        weak = [r for r in weak if r["id"] not in sup]
        if not weak:
            continue
        target = weak[-1]
        new = dict(target)
        new["id"] = record.new_id(target["tid"] + ":asked", rel)
        new["ts"] = record.now()
        new["why"] = why[:cfg["why_max"]]
        new["src"] = "asked"
        new["conf"] = 0.8
        new["sup"] = [target["id"]]
        store.append(root, rel, new)
        done += 1
    return done
