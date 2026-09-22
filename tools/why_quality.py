"""why가 이유인지 행위 선언인지 기계로 센다.

사람 판정은 재현이 안 되므로 자동 지표를 먼저 본다. 다만 주의할 것이 하나 있다.
**진행 서술 패턴은 extract.pick_sentences가 필터로 쓴다.** 그래서 그 비율은 구조적으로
낮아지고, 성공 지표가 될 수 없다(지표를 겨냥해 고치는 꼴이 된다). 참고로만 찍는다.

독립 지표는 둘이다.
  - 앵커: why가 그 편집의 symbol이나 파일 이름을 짚는가
  - 인과 표지: why에 원인·문제를 가리키는 말이 있는가 (필터와 무관한 어휘다)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import config, extract, store  # noqa: E402

# 원인이나 문제를 가리키는 말. "무엇을 하겠다"가 아니라 "무엇이 잘못됐다"는 쪽.
CAUSAL = re.compile(
    r"(때문|않|못 |못하|틀렸|틀린|필요|이유|실패|버그|어긋|모순|빠졌|없다|없었|없으|"
    r"아니라|라서|탓|깨졌|막히|잘못|오도|위험|손실)")


def anchored(rec, rel):
    why = rec.get("why") or ""
    sym = (rec.get("anchor") or {}).get("sym")
    base = os.path.basename(rel)
    return any(t and t in why for t in (sym, base, os.path.splitext(base)[0]))


def main():
    root = config.find_root(os.getcwd())
    rows = [(rel, rec) for rel, _ in sorted(store.all_sidecars(root))
            for rec in store.read(root, rel)]
    if not rows:
        print("note 없음")
        return
    n = len(rows)
    by_src, anc, causal, proc = {}, 0, 0, 0
    text_whys = {}
    for rel, rec in rows:
        src = rec.get("src")
        by_src[src] = by_src.get(src, 0) + 1
        why = rec.get("why") or ""
        anc += anchored(rec, rel)
        causal += bool(CAUSAL.search(why))
        proc += bool(extract.PROCEDURAL.search(why.strip()))
        if src == "text":
            text_whys.setdefault(why[:80], []).append(rel)
    # 복제는 text 출처만 센다. turn은 한 요청에서 나온 편집들이 같은 맥락을 공유하는 게 맞다.
    dup = sum(len(v) for v in text_whys.values() if len(v) > 1)
    nt = by_src.get("text", 0)

    print("note %d건" % n)
    for k, v in sorted(by_src.items(), key=lambda kv: -kv[1]):
        print("  src=%-5s %3d건  %5.1f%%" % (k, v, 100.0 * v / n))
    print("  [지표] 앵커       %3d/%d  %5.1f%%   높을수록 좋다" % (anc, n, 100.0 * anc / n))
    print("  [지표] 인과 표지  %3d/%d  %5.1f%%   높을수록 좋다" % (causal, n, 100.0 * causal / n))
    print("  [지표] text 복제  %3d/%d  %5.1f%%   0이어야 한다" % (dup, nt, 100.0 * dup / nt if nt else 0))
    print("  [참고] 행위 선술 %3d/%d  %5.1f%%   필터로 쓰므로 독립 지표 아님"
          % (proc, n, 100.0 * proc / n))
    print("  why 평균 %.0f자" % (sum(len(r.get("why") or "") for _, r in rows) / n))


if __name__ == "__main__":
    main()
