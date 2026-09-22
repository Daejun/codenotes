"""transcript JSONL을 읽어 블록을 다시 조립한다.

Phase 0 실측이 전제다.
  - 한 API message가 블록마다 한 레코드로 쪼개진다. 묶는 키는 message.id, 순서는 apiBlockIndex.
  - thinking 본문은 저장되지 않는다(빈 문자열 + signature). why 출처가 될 수 없다.
  - assistant 레코드에는 promptId가 없다. tool_result를 담은 user 레코드에는 있다.
"""
import json
import os
import re

EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")


def scan(path, offset=0):
    """offset byte부터 읽어 (레코드, 그 레코드가 끝나는 offset) 목록과 파일 끝 offset을 돌려준다."""
    out = []
    if not path or not os.path.exists(path):
        return out, offset
    size = os.path.getsize(path)
    if offset > size:
        offset = 0                 # 잘렸거나 다른 파일이다. 처음부터.
    with open(path, "rb") as f:
        f.seek(offset)
        pos = offset
        for raw in f:
            pos += len(raw)
            try:
                out.append((json.loads(raw.decode("utf-8", "replace")), pos))
            except Exception:
                continue           # 마지막 줄이 쓰이는 중일 수 있다
    return out, pos if out else offset


def index(records):
    """조립 결과. edits는 transcript에 나온 순서를 지킨다."""
    texts = {}        # message.id -> [(apiBlockIndex, text)]
    edits = []        # {tid, msg_id, idx, tool, end_off}
    results = {}      # tid -> {promptId, toolUseResult}
    prompts = {}      # promptId -> 사용자가 친 글

    for rec, end in records:
        t = rec.get("type")
        if t == "assistant":
            msg = rec.get("message") or {}
            mid = msg.get("id")
            idx = rec.get("apiBlockIndex", 0)
            for b in msg.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    texts.setdefault(mid, []).append((idx, b.get("text") or ""))
                elif b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS:
                    edits.append({"tid": b.get("id"), "msg_id": mid, "idx": idx,
                                  "tool": b.get("name"), "end_off": end})
        elif t == "user":
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                if rec.get("promptId"):
                    prompts.setdefault(rec["promptId"], content)
            elif isinstance(content, list) and rec.get("toolUseResult") is not None:
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        results[b.get("tool_use_id")] = {
                            "promptId": rec.get("promptId"),
                            "result": rec.get("toolUseResult"),
                        }
    return {"texts": texts, "edits": edits, "results": results, "prompts": prompts}


def preceding_text(ix, edit):
    """그 편집 직전의 말 — 같은 message.id에서 apiBlockIndex가 작은 text 블록."""
    blocks = ix["texts"].get(edit["msg_id"]) or []
    parts = [t for i, t in sorted(blocks) if i < edit["idx"] and t.strip()]
    return "\n".join(parts).strip()


def turn_text(ix, edit):
    """text가 없을 때의 바닥값 — 그 편집이 속한 턴의 **사용자 요청**.

    last_assistant_message는 쓰지 않는다. 턴 전체의 요약이라 그 편집과 무관하고,
    한 턴의 편집 여러 개에 같은 글이 복제된다(Phase 4 실측: 복제 28.6%).
    요청은 이유가 아니라 맥락이므로 "요청:"을 붙여 그렇게 읽히게 한다.
    """
    pid = (ix["results"].get(edit["tid"]) or {}).get("promptId")
    p = (ix["prompts"].get(pid) or "").strip()
    return ("요청: " + p if p else ""), pid


SENT = re.compile(r"(?<=[.!?。])\s+|\n+")
# "내가 이제 무엇을 한다"로 끝나는 문장. 이유가 아니라 행위 선언이다.
PROCEDURAL = re.compile(
    r"(합니다|하겠습니다|봅니다|봅시다|돌립니다|넣습니다|씁니다|고칩니다|만듭니다|"
    r"냅니다|잽니다|겁니다|둡니다|바꿉니다|옮깁니다|지웁니다|쌓입니다|"
    r"확인합니다|시작합니다|이어갑니다|정리합니다)[.!]?$")


def pick_sentences(text, hints, limit):
    """편집과 관련된 문장만 고른다.

    끝 문장을 고르는 것은 틀렸다(Phase 4 실측: 앵커율 14.3% -> 10.0%로 내려갔다).
    편집에 가장 가까운 문장이 바로 행위 선언이기 때문이다 —
    "테스트 기대값이 틀렸습니다"(이유)가 잘리고 "잘리는 예산으로 고칩니다"(행위)가 남았다.

    순서: 파일이나 symbol을 짚는 문장 > 행위 선언이 아닌 문장 > 통째로.
    """
    parts = [s.strip() for s in SENT.split(text or "") if s.strip()]
    if not parts:
        return ""
    hit = [s for s in parts if any(h and h in s for h in hints)]
    if not hit:
        hit = [s for s in parts if not PROCEDURAL.search(s)]
    return " ".join(hit or parts)[:limit]


def clean(s, limit):
    """why 한 줄로 줄인다. 상한은 불변식 7."""
    if not s:
        return ""
    s = " ".join(s.split())
    for tag in ("<command-message>", "<command-name>", "<command-args>", "<system-reminder>"):
        s = s.replace(tag, " ").replace(tag.replace("<", "</"), " ")
    s = " ".join(s.split())
    return s[:limit]


def patch_stats(result):
    """structuredPatch -> (더한 줄, 지운 줄, 바뀐 줄 범위).

    새 파일 Write는 structuredPatch가 빈 배열로 오고 type이 "create"다(실측).
    그때는 content 전체가 변경분이다.
    """
    result = result or {}
    if result.get("type") == "create" or (not result.get("structuredPatch")
                                          and not (result.get("originalFile") or "")):
        body = result.get("content") or ""
        n = len(body.splitlines())
        return n, 0, ([1, n] if n else None)
    add = dele = 0
    lo = hi = None
    for h in result.get("structuredPatch") or []:
        for ln in h.get("lines") or []:
            if ln.startswith("+"):
                add += 1
            elif ln.startswith("-"):
                dele += 1
        s = h.get("newStart")
        n = h.get("newLines") or 0
        if s is None:
            continue
        e = s + max(n - 1, 0)
        lo = s if lo is None else min(lo, s)
        hi = e if hi is None else max(hi, e)
    return add, dele, ([lo, hi] if lo is not None else None)


def rebuild(result):
    """그 편집 직후의 파일 내용. structuredPatch로 하지 않는다 — 탭이 공백으로 펴져 손실된다.

    Phase 1 실측: originalFile.replace(oldString, newString)와 Write의 content가
    디스크와 정확히 일치했고, 연쇄 적용도 일치했다.
    """
    result = result or {}
    if result.get("content") is not None and result.get("oldString") is None:
        return result["content"]                      # Write — 통째로 새 내용
    old = result.get("oldString")
    new = result.get("newString")
    base = result.get("originalFile")
    if old is None or new is None or base is None:
        return None
    return base.replace(old, new, -1 if result.get("replaceAll") else 1)
