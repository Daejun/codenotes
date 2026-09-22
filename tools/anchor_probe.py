"""history replay — codenotes/anchor.py가 실제 커밋 사이에서 note를 얼마나 지키는가.

1스텝(부모->자식)과 N스텝 누적을 잰다. docs/findings-anchor.md가 결과다.
"""
import argparse
import collections
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import anchor  # noqa: E402



REPO = os.environ.get("CODENOTES_PROBE_REPO", "")


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout


_cache = {}


def snapshot(sha, path):
    """(commit, file) -> symbol 목록. simhash가 비싸서 캐시한다."""
    key = (sha, path)
    if key not in _cache:
        text = git("show", "%s:%s" % (sha, path))
        syms = anchor.symbols(text, path)
        for s in syms:
            s["_h"] = anchor.body_hash(s["body"])
            s["_s"] = anchor.simhash(s["body"])
        _cache[key] = syms
        if len(_cache) > 400:
            _cache.pop(next(iter(_cache)))
    return _cache[key]


def resolve_in(syms, a, sim_max):
    """anchor.resolve와 같은 순서. 캐시된 symbol 위에서 돈다."""
    for s in syms:
        if s["_h"] == a["hash"]:
            return 1, s
    for s in syms:
        if s["sym"] == a["sym"]:
            return 2, s
    best, dist = None, 65
    for s in syms:
        d = anchor.hamming(a["sig"], s["_s"])
        if d < dist:
            best, dist = s, d
    if best and dist <= sim_max:
        return 3, best
    return 4, None


def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=150, help="볼 커밋 수")
    ap.add_argument("--steps", default="1", help="쉼표로 구분한 N스텝 (예: 1,10,50)")
    ap.add_argument("--sim-max", type=int, default=anchor.SIM_MAX)
    ap.add_argument("--repo", default=REPO, help="replay할 git 저장소 (또는 CODENOTES_PROBE_REPO)")
    args = ap.parse_args()
    REPO = args.repo
    if not REPO:
        raise SystemExit("--repo 나 CODENOTES_PROBE_REPO 로 replay할 저장소를 준다")

    shas = git("log", "--format=%H", "-%d" % (args.n + max(int(x) for x in args.steps.split(",")))).split()
    for step in [int(x) for x in args.steps.split(",")]:
        stat = collections.Counter()
        dists = []
        pairs = 0
        for idx in range(min(args.n, len(shas) - step)):
            child = shas[idx]
            parent = shas[idx + step]
            changed = [l for l in git("diff", "--name-only", parent, child).split("\n")
                       if l.endswith((".c", ".h"))]
            if not changed:
                continue
            pairs += 1
            for f in changed:
                old = snapshot(parent, f)
                new = snapshot(child, f)
                if not old:
                    continue
                for s in old:
                    a = {"sym": s["sym"], "hash": s["_h"], "sig": s["_s"]}
                    st, hit = resolve_in(new, a, args.sim_max)
                    stat[st] += 1
                    if st == 4:
                        # 유실 건의 최소 해밍 거리 — SIM_MAX 보정용
                        d = min([anchor.hamming(a["sig"], t["_s"]) for t in new] or [64])
                        dists.append(d)
        tot = sum(stat.values()) or 1
        label = {1: "1 해시", 2: "2 이름", 3: "3 개명", 4: "4 유실"}
        print("step=%-3d 커밋쌍 %3d개, anchor %5d건" % (step, pairs, tot))
        for k in sorted(stat):
            print("   %-8s %6d  %5.1f%%" % (label[k], stat[k], 100.0 * stat[k] / tot))
        if dists:
            dists.sort()
            print("   유실 건의 최소 해밍 거리: 중앙값 %d, 하위 10%% %d (SIM_MAX=%d)"
                  % (dists[len(dists) // 2], dists[len(dists) // 10], args.sim_max))


if __name__ == "__main__":
    main()
