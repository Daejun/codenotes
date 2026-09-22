"""레코드 스키마와 id 생성. 한 줄이 독립이어야 merge=union이 먹는다."""
import datetime
import hashlib
import json

VERSION = 1


def new_id(tid, rel):
    h = hashlib.sha1(("%s|%s" % (tid, rel)).encode("utf-8")).hexdigest()[:6]
    return "n_" + h


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make(tid, rel, sid, pid, op, anchor, add, dele, why, src, conf):
    rec = {"v": VERSION, "id": new_id(tid, rel), "ts": now(), "sid": (sid or "")[:8],
           "pid": (pid or "")[:8], "tid": tid, "op": op,
           "anchor": anchor, "d": {"add": add, "del": dele},
           "why": why, "src": src, "conf": conf}
    return rec


def file_anchor(lines):
    """Phase 1은 파일 레벨만. lines는 힌트이지 식별자가 아니다."""
    return {"sym": None, "kind": "file", "hash": None, "lines": lines}


def dumps(rec):
    """한 줄 JSON. store.append와 같은 모양이어야 merge=union이 일관된다."""
    return json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
