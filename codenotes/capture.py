"""Stop에서 그 턴의 편집을 sidecar에 적는다.

capture가 PostToolUse가 아니라 Stop인 이유는 docs/findings-hook-io.md에 있다.
요약하면 PostToolUse 시점에는 transcript에 그 레코드가 아직 없고, thinking 본문은
애초에 저장되지 않으며, toolUseResult가 originalFile과 structuredPatch를 들고 있다.
"""
import os

from . import anchor, config, extract, record, review, store

# turn은 "무슨 요청을 하다 생긴 변경인가"라는 맥락이다. 이유가 아니므로 recall에는 넣지 않는다
# (render.MIN_CONF = 0.3 미만이면 주입에서 빠진다). 기록으로는 남긴다 — review에서 쓸모가 있다.
SRC_CONF = {"text": 0.7, "turn": 0.2}


def run(payload):
    """돌려주는 값은 통계다. 예외는 부르는 쪽(hook)이 삼킨다."""
    root = config.find_root(payload.get("cwd"))
    if not root:
        return {"skip": "no-root"}
    cfg = config.load(root)
    tp = payload.get("transcript_path")

    st = store.load_state(root)
    off = st.get("offset", 0) if st.get("transcript") == tp else 0
    seen = set(st.get("seen") or [])
    if not seen and off == 0:
        seen = set(store.rebuild_seen(root))   # state를 잃었으면 sidecar에서 되살린다

    # rename을 먼저 따라간다. 옮기기 전에 append하면 sidecar가 두 군데로 갈라진다.
    moved = 0
    for old, new in review.renames(root):
        moved += review.move_sidecar(root, old, new)

    records, end_off = extract.scan(tp, off)
    ix = extract.index(records)

    stat = {"edits": len(ix["edits"]), "wrote": 0, "dup": 0, "moved": moved,
            "excluded": 0, "pending": 0, "src": {}, "weak": []}
    safe_off = end_off

    for e in ix["edits"]:
        tid = e["tid"]
        if not tid:
            continue
        if tid in seen:
            stat["dup"] += 1
            continue
        got = ix["results"].get(tid)
        if not got:
            # 결과가 아직 flush되지 않았다. watermark를 여기서 멈춰 다음 Stop이 다시 본다.
            stat["pending"] += 1
            safe_off = min(safe_off, e["end_off"] - 1)
            continue
        res = got["result"] or {}
        rel = config.relativize(root, res.get("filePath"))
        why_src = config.excluded(root, rel)
        if why_src:
            seen.add(tid)          # 제외는 확정이다. 다시 볼 이유가 없다.
            stat["excluded"] += 1
            continue

        add, dele, span = extract.patch_stats(res)
        after = extract.rebuild(res)          # 디스크가 아니라 그 편집 시점의 내용 (불변식 9)
        anc = anchor.make(after, rel, span) if after else record.file_anchor(span)
        if anc.get("kind") != "file":
            stat["sym"] = stat.get("sym", 0) + 1

        # anchor를 먼저 구해야 어떤 symbol을 짚는 문장인지 고를 수 있다.
        base = os.path.basename(rel)
        hints = [anc.get("sym"), base, os.path.splitext(base)[0]]
        text = extract.pick_sentences(extract.preceding_text(ix, e), hints, cfg["why_max"])
        if text:
            why, src = text, "text"
        else:
            why, _pid = extract.turn_text(ix, e)
            src = "turn"
        why = extract.clean(why, cfg["why_max"])
        if not why:
            stat["pending"] += 1   # 이유가 하나도 없으면 적지 않는다 (불변식 8)
            continue
        rec = record.make(tid, rel, payload.get("session_id"), got.get("promptId"),
                          "create" if res.get("type") == "create" else e["tool"].lower(),
                          anc, add, dele, why, src, SRC_CONF[src])
        store.append(root, rel, rec)
        seen.add(tid)
        stat["wrote"] += 1
        stat["src"][src] = stat["src"].get(src, 0) + 1
        if src != "text":
            # 이유가 없어 요청문으로 때운 것. 되묻기(ask)가 켜져 있으면 이 목록을 쓴다.
            stat["weak"].append({"rel": rel, "id": rec["id"], "sym": anc.get("sym")})

    cap = cfg["seen_cap"]
    store.save_state(root, {"transcript": tp, "offset": max(safe_off, 0),
                            "seen": list(seen)[-cap:]})
    return stat
