"""Phase 4 — 되물어 받은 이유를 기존 note에 잇는다."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import ask, record, store  # noqa: E402

CFG = {"why_max": 240}


class Parse(unittest.TestCase):
    def test_reads_the_exact_format(self):
        msg = ("앞말\n"
               "codenotes: codenotes/anchor.py — enclosing이 새 파일을 첫 함수에 걸었다\n"
               "codenotes: tests/x.py: 예산 계산이 틀렸다\n"
               "뒷말")
        self.assertEqual(ask.parse(msg), [
            ("codenotes/anchor.py", "enclosing이 새 파일을 첫 함수에 걸었다"),
            ("tests/x.py", "예산 계산이 틀렸다"),
        ])

    def test_ignores_prose(self):
        self.assertEqual(ask.parse("그냥 설명입니다. codenotes 이야기도 했습니다."), [])

    def test_empty_message(self):
        self.assertEqual(ask.parse(None), [])


class Apply(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".codenotes"))
        self.rel = "src/a.py"
        self.weak = record.make("toolu_1", self.rel, "s", "p", "edit",
                                {"sym": "f", "kind": "fn", "hash": "aa", "lines": [1, 3]},
                                2, 1, "요청: 뭐 좀 고쳐줘", "turn", 0.2)
        store.append(self.root, self.rel, self.weak)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_joins_and_supersedes(self):
        n = ask.apply(self.root, "codenotes: src/a.py — 경계 조건에서 f가 None을 돌려줬다", CFG)
        self.assertEqual(n, 1)
        recs = store.read(self.root, self.rel)
        self.assertEqual(len(recs), 2)                 # 덮어쓰지 않고 쌓는다
        new = recs[-1]
        self.assertEqual(new["src"], "asked")
        self.assertEqual(new["conf"], 0.8)
        self.assertEqual(new["sup"], [self.weak["id"]])
        self.assertEqual(new["anchor"], self.weak["anchor"])   # 위치는 그대로

    def test_does_not_touch_text_sourced_notes(self):
        store.append(self.root, "src/b.py",
                     record.make("toolu_2", "src/b.py", "s", "p", "edit",
                                 {"kind": "file", "lines": None}, 1, 0,
                                 "이미 좋은 이유", "text", 0.7))
        self.assertEqual(ask.apply(self.root, "codenotes: src/b.py — 다른 이유", CFG), 0)
        self.assertEqual(len(store.read(self.root, "src/b.py")), 1)

    def test_already_answered_note_is_not_rejoined(self):
        ask.apply(self.root, "codenotes: src/a.py — 첫 답", CFG)
        self.assertEqual(ask.apply(self.root, "codenotes: src/a.py — 둘째 답", CFG), 0)
