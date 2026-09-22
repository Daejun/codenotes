"""codenotes CLI."""
import argparse
import os
import sys

from . import config, extract, init, review, store


def root_or_die():
    root = config.find_root(os.getcwd())
    if not root:
        print("이 프로젝트에는 .codenotes/가 없습니다. codenotes init 먼저.", file=sys.stderr)
        raise SystemExit(1)
    return root


def line(rel, rec, stage, sym, show_file=False):
    tag = {1: "", 2: " [본문이 바뀜]", 3: " [이름이 바뀜]", 4: " [그 위치는 사라짐]"}.get(stage, "")
    where = "%s  " % rel if show_file else ""
    return ("  %s%s  %s  +%s-%s  [%s %.1f]%s\n      %s"
            % (where, sym or "파일", (rec.get("ts") or "")[:10],
               rec["d"]["add"], rec["d"]["del"], rec["src"], rec["conf"], tag,
               rec.get("why") or "(gc로 비워짐)"))


def cmd_show(args):
    root = root_or_die()
    rel = config.relativize(root, os.path.abspath(args.file))
    if not rel:
        print("root 밖입니다", file=sys.stderr)
        return 1
    recs = review.live(root, rel)
    if not recs:
        print("note 없음: %s" % rel)
        return 0
    print("%s — note %d건" % (rel, len(recs)))
    for rec, stage, sym in review.annotate(root, rel, recs):
        print(line(rel, rec, stage, sym))
    return 0


def cmd_review(args):
    """지금 diff에 걸린 note만. 이유(text/asked)와 맥락(turn)을 갈라 놓는다."""
    root = root_or_die()
    files = review.changed_files(root, args.since, args.staged)
    reasons, contexts, n = [], [], 0
    for rel in files:
        recs = review.live(root, rel)
        if not recs:
            continue
        for rec, stage, sym in review.annotate(root, rel, recs):
            n += 1
            (contexts if rec.get("src") in review.WEAK else reasons).append(
                line(rel, rec, stage, sym, show_file=True))
    scope = args.since or ("staged" if args.staged else "working tree")
    print("변경된 파일 %d개, note %d건 (%s)" % (len(files), n, scope))
    if reasons:
        print("\n이유:")
        print("\n".join(reasons))
    if contexts:
        print("\n맥락 (이유가 기록되지 않아 요청문으로 남은 것):")
        print("\n".join(contexts))
    return 0


def cmd_search(args):
    root = root_or_die()
    hits = review.search(root, args.query)
    print("%d건" % len(hits))
    for rel, rec in hits:
        print(line(rel, rec, 0, (rec.get("anchor") or {}).get("sym"), show_file=True))
    return 0


def cmd_stats(args):
    root = root_or_die()
    n = files = size = 0
    src = {}
    for rel, full in store.all_sidecars(root):
        files += 1
        size += os.path.getsize(full)
        for r in store.read(root, rel):
            n += 1
            src[r.get("src")] = src.get(r.get("src"), 0) + 1
    print("sidecar %d개, note %d건, 총 %d byte (건당 %.0f byte)"
          % (files, n, size, size / n if n else 0))
    for k, v in sorted(src.items(), key=lambda kv: -kv[1]):
        print("  src=%-6s %3d건  %5.1f%%" % (k, v, 100.0 * v / n if n else 0))
    return 0


def cmd_mv(args):
    root = root_or_die()
    a = config.relativize(root, os.path.abspath(args.old))
    b = config.relativize(root, os.path.abspath(args.new))
    ok = review.move_sidecar(root, a, b)
    print("%s -> %s  %s" % (a, b, "옮김" if ok else "sidecar 없음"))
    return 0 if ok else 1


def cmd_gc(args):
    root = root_or_die()
    freed, total = review.gc(root, args.keep)
    print("note %d건 중 anchor당 %d건 초과분의 why를 비웠다. %d자 회수." % (total, args.keep, freed))
    return 0


def cmd_doctor(args):
    root = root_or_die()
    if args.transcript:
        return audit(root, args.transcript)
    orph = review.orphans(root)
    ren = review.renames(root)
    stale = 0
    total = 0
    for rel, _ in sorted(store.all_sidecars(root)):
        if rel in orph:
            continue
        for _rec, stage, _sym in review.annotate(root, rel, review.live(root, rel)):
            total += 1
            stale += stage in (2, 4)
    print("note %d건 중 위치가 흔들린 것 %d건 (%.1f%%)"
          % (total, stale, 100.0 * stale / total if total else 0))
    print("원본이 사라진 sidecar %d개%s" % (len(orph), (": " + ", ".join(orph[:5])) if orph else ""))
    if ren:
        print("git이 아는 rename %d건 — `codenotes mv`로 따라가게 할 수 있다:" % len(ren))
        for a, b in ren:
            print("  %s -> %s" % (a, b))
    return 0


def audit(root, transcript):
    """성공 기준 검사: 제외를 통과한 편집 수 = sidecar 레코드 수, 그리고 복원이 디스크와 맞는가."""
    recs, _ = extract.scan(transcript, 0)
    ix = extract.index(recs)
    kept, excl, pend, last = [], 0, 0, {}
    for e in ix["edits"]:
        got = ix["results"].get(e["tid"])
        if not got:
            pend += 1
            continue
        rel = config.relativize(root, (got["result"] or {}).get("filePath"))
        if config.excluded(root, rel):
            excl += 1
        else:
            kept.append(e["tid"])
            last[rel] = got["result"]
    have = {r.get("tid") for rel, _ in store.all_sidecars(root) for r in store.read(root, rel)}
    missing = [t for t in kept if t not in have]
    bad = []
    for rel, res in sorted(last.items()):
        built = extract.rebuild(res)
        path = os.path.join(root, rel)
        if built is None or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            if f.read() != built:
                bad.append(rel)
    print("transcript 편집 %d건 = 제외 %d + 결과미도착 %d + 대상 %d"
          % (len(ix["edits"]), excl, pend, len(kept)))
    print("sidecar 기록 %d건 / 대상 %d건" % (len(set(kept) & have), len(kept)))
    print("놓친 편집: %d건" % len(missing))
    print("복원 검사: 파일 %d개 중 디스크와 불일치 %d건%s"
          % (len(last), len(bad), (" " + ", ".join(bad[:3])) if bad else ""))
    return 1 if (missing or bad) else 0


def cmd_init(args):
    root = os.path.abspath(args.path)
    made = init.run(root, write_settings=not args.no_settings)
    print("%s 를 codenotes에 넣었다: %s" % (root, ", ".join(made)))
    print("해제하려면 .codenotes/ 를 지운다 — hook은 그 디렉터리가 없으면 즉시 빠진다.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codenotes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("path", nargs="?", default=".")
    s.add_argument("--no-settings", action="store_true",
                   help=".claude/settings.json은 건드리지 않는다")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("show"); s.add_argument("file"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("review")
    s.add_argument("--since"); s.add_argument("--staged", action="store_true")
    s.set_defaults(fn=cmd_review)
    s = sub.add_parser("search"); s.add_argument("query"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("stats"); s.set_defaults(fn=cmd_stats)
    s = sub.add_parser("mv"); s.add_argument("old"); s.add_argument("new"); s.set_defaults(fn=cmd_mv)
    s = sub.add_parser("gc"); s.add_argument("--keep", type=int, default=3); s.set_defaults(fn=cmd_gc)
    s = sub.add_parser("doctor"); s.add_argument("--audit", dest="transcript")
    s.set_defaults(fn=cmd_doctor)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
