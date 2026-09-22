"""Phase 5 — review, 검색, rename, gc."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import record, review, store  # noqa: E402

SRC = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"


def git(root, *a):
    return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".codenotes"))
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        self.write("a.py", SRC)
        self.write("b.py", SRC)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def note(self, rel, sym, why, src="text", tid=None):
        rec = record.make(tid or ("toolu_%s_%s" % (rel, sym)), rel, "s", "p", "edit",
                          {"sym": sym, "kind": "fn", "hash": "zz", "lines": [1, 2]},
                          1, 0, why, src, 0.7 if src == "text" else 0.2)
        store.append(self.root, rel, rec)
        return rec


class ReviewScope(Base):
    def test_only_changed_files(self):
        self.note("a.py", "f", "f가 0을 돌려줘야 했다")
        self.note("b.py", "g", "b 쪽 이유")
        self.assertEqual(review.changed_files(self.root), [])
        self.write("a.py", SRC.replace("return 1", "return 0"))
        self.assertEqual(review.changed_files(self.root), ["a.py"])

    def test_weak_is_separable(self):
        self.note("a.py", "f", "진짜 이유")
        self.note("a.py", "g", "요청: 뭐 좀 해줘", src="turn", tid="toolu_x")
        recs = review.live(self.root, "a.py")
        weak = [r for r in recs if r["src"] in review.WEAK]
        self.assertEqual(len(weak), 1)
        self.assertEqual(len(recs) - len(weak), 1)


class Search(Base):
    def test_finds_by_why_and_symbol(self):
        self.note("a.py", "f", "경계에서 터진다")
        self.note("b.py", "g", "무관한 이유")
        self.assertEqual([rel for rel, _ in review.search(self.root, "경계")], ["a.py"])
        self.assertEqual([rel for rel, _ in review.search(self.root, "g")], ["b.py"])

    def test_superseded_is_hidden(self):
        old = self.note("a.py", "f", "옛 이유")
        new = dict(old)
        new["id"] = "n_new"
        new["why"] = "새 이유"
        new["sup"] = [old["id"]]
        store.append(self.root, "a.py", new)
        self.assertEqual(len(review.search(self.root, "이유")), 1)


class Rename(Base):
    def test_git_mv_is_detected_and_followed(self):
        self.note("a.py", "f", "따라와야 한다")
        git(self.root, "mv", "a.py", "c.py")
        self.assertEqual(review.renames(self.root), [("a.py", "c.py")])
        self.assertTrue(review.move_sidecar(self.root, "a.py", "c.py"))
        self.assertEqual(len(store.read(self.root, "c.py")), 1)
        self.assertEqual(store.read(self.root, "a.py"), [])

    def test_merges_into_existing_sidecar(self):
        self.note("a.py", "f", "옛 파일 쪽")
        self.note("b.py", "g", "새 파일 쪽")
        review.move_sidecar(self.root, "a.py", "b.py")
        self.assertEqual(len(store.read(self.root, "b.py")), 2)

    def test_orphan_is_reported(self):
        self.note("a.py", "f", "이유")
        os.remove(os.path.join(self.root, "a.py"))
        self.assertEqual(review.orphans(self.root), ["a.py"])


class Gc(Base):
    def test_keeps_records_and_chain(self):
        for i in range(5):
            r = self.note("a.py", "f", "이유 %d" % i, tid="toolu_%d" % i)
            r["ts"] = "2026-09-%02dT00:00:00Z" % (i + 1)
        # ts를 다시 쓰려면 파일을 다시 만들어야 한다 — 위 append는 원래 ts를 썼다
        freed, total = review.gc(self.root, keep=2)
        recs = store.read(self.root, "a.py")
        self.assertEqual(len(recs), 5)                       # 하나도 지우지 않는다
        self.assertEqual(sum(1 for r in recs if r["src"] == "gc"), 3)
        self.assertGreater(freed, 0)
        self.assertEqual(total, 5)

    def test_gc_is_idempotent(self):
        for i in range(4):
            self.note("a.py", "f", "이유 %d" % i, tid="toolu_%d" % i)
        review.gc(self.root, keep=1)
        freed2, _ = review.gc(self.root, keep=1)
        self.assertEqual(freed2, 0)
