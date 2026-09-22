"""review와 검색, rename 추적, gc.

색인은 두지 않는다. FTS5는 드문 질의에서 확실히 빠르지만(note 20만 건에 34ms -> 0.31ms),
현실 규모인 1만 건에서 전수 스캔이 1.8ms다. CLI 한 번에 1.8ms면 색인을 동기화하고
재생성하고 stale을 걱정할 값어치가 없다. note가 5만 건을 넘어 스캔이 10ms를 넘으면 다시 본다.
"""
import os
import subprocess

from . import anchor, record, store

WEAK = ("turn",)            # 이유가 아니라 맥락. review에서 따로 묶는다.


def git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def changed_files(root, since=None, staged=False):
    if staged:
        out = git(root, "diff", "--cached", "--name-only")
    elif since:
        out = git(root, "diff", "--name-only", "%s...HEAD" % since)
    else:
        out = git(root, "diff", "--name-only") + git(root, "diff", "--cached", "--name-only")
    return sorted({l for l in out.split("\n") if l.strip()})


def live(root, rel):
    """superseded를 걷어낸 note."""
    recs = store.read(root, rel)
    sup = {s for r in recs for s in (r.get("sup") or [])}
    return [r for r in recs if r["id"] not in sup]


def current_text(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def annotate(root, rel, recs):
    """각 note의 anchor를 지금 파일에 다시 걸어 (stage, symbol)을 붙인다."""
    text = current_text(root, rel)
    out = []
    for r in recs:
        stage, hit = anchor.resolve(text, rel, r.get("anchor") or {}) if text else (0, None)
        out.append((r, stage, (hit or {}).get("sym") or (r.get("anchor") or {}).get("sym")))
    return out


def search(root, query):
    """sidecar 전수 스캔. 색인 없음 — 위 docstring의 실측 근거를 보라."""
    q = query.lower()
    hits = []
    for rel, _ in sorted(store.all_sidecars(root)):
        for r in live(root, rel):
            hay = "%s %s" % (r.get("why") or "", (r.get("anchor") or {}).get("sym") or "")
            if q in hay.lower():
                hits.append((rel, r))
    return hits


# ---- rename ----

def renames(root):
    """git이 아는 rename. `git mv`로 옮긴 것(staged)만 잡힌다 — 평범한 mv는 못 잡는다."""
    out = []
    for ln in git(root, "status", "--porcelain", "-M").split("\n"):
        if ln[:2].strip().startswith("R") and " -> " in ln:
            old, new = ln[3:].split(" -> ", 1)
            out.append((old.strip().strip('"'), new.strip().strip('"')))
    return out


def move_sidecar(root, old, new):
    src = store.sidecar(root, old)
    if not os.path.exists(src):
        return False
    dst = store.sidecar(root, new)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):                       # 합친다 — 목적지 note를 덮지 않는다
        with open(src, encoding="utf-8") as f:
            body = f.read()
        with open(dst, "a", encoding="utf-8") as f:
            f.write(body)
        os.remove(src)
    else:
        os.replace(src, dst)
    return True


def orphans(root):
    """원본 파일이 사라진 sidecar. rename을 놓쳤거나 파일이 지워진 것이다."""
    return [rel for rel, _ in sorted(store.all_sidecars(root))
            if not os.path.exists(os.path.join(root, rel))]


# ---- gc ----

def gc(root, keep):
    """같은 anchor의 note가 keep을 넘으면 오래된 것의 why만 비운다.

    레코드를 지우지 않는다. `sup` 사슬과 "무엇이 언제 바뀌었나"는 남고 부피의 대부분인
    why만 사라진다. 진실은 sidecar 하나라는 불변식을 지키면서 줄이는 유일한 방법이다.
    """
    freed = total = 0
    for rel, path in sorted(store.all_sidecars(root)):
        recs = store.read(root, rel)
        by = {}
        for r in recs:
            by.setdefault((r.get("anchor") or {}).get("sym"), []).append(r)
        changed = False
        for _sym, group in by.items():
            group.sort(key=lambda r: r.get("ts") or "")
            for r in group[:-keep] if len(group) > keep else []:
                if r.get("why"):
                    freed += len(r["why"])
                    r["why"] = ""
                    r["src"] = "gc"
                    changed = True
        total += len(recs)
        if changed:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(record.dumps(r) + "\n")
            os.replace(tmp, path)          # CLI 경로라 rewrite해도 된다 (불변식 4)
    return freed, total
