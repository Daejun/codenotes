"""sidecar 경로 매핑과 append. 진실은 여기 JSONL 하나뿐이다."""
import json
import os

from . import config, record


def sidecar(root, rel):
    """src/gc.c -> <root>/.codenotes/src/gc.c.jsonl"""
    return os.path.join(root, config.DIRNAME, rel + ".jsonl")


def append(root, rel, rec):
    p = sidecar(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    line = record.dumps(rec) + "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)          # 한 줄 한 번에. 줄 단위로 독립이라 merge=union이 먹는다.
    return len(line)


def read(root, rel):
    p = sidecar(root, rel)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue          # 깨진 줄 하나가 파일 전체를 못 쓰게 만들지 않는다
    return out


def all_sidecars(root):
    """(rel, path) 목록. .codenotes/ 아래 *.jsonl 전부."""
    base = os.path.join(root, config.DIRNAME)
    for dirpath, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, base)[:-len(".jsonl")]
            yield rel, full


# ---- state: watermark와 본 tid. 파생물이라 지워도 sidecar에서 복구된다. ----

def state_path(root):
    return os.path.join(root, config.DIRNAME, "state.json")


def load_state(root):
    try:
        with open(state_path(root), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(root, st):
    p = state_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, p)           # 원자적 교체


def rebuild_seen(root):
    """state.json을 잃었을 때 sidecar에서 tid 집합을 되살린다."""
    seen = []
    for rel, _ in all_sidecars(root):
        for rec in read(root, rel):
            if rec.get("tid"):
                seen.append(rec["tid"])
    return seen


def log(root, msg):
    try:
        with open(os.path.join(root, config.DIRNAME, "hook.log"), "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass
