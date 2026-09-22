"""Phase 2 — symbol 판정과 재해석."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import anchor  # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus", "gc_sample.c")


def corpus():
    with open(CORPUS, encoding="utf-8") as f:
        return f.read()


class CSymbols(unittest.TestCase):
    def test_finds_kernel_style_functions(self):
        names = [s["sym"] for s in anchor.symbols(corpus(), "gc.c")]
        self.assertEqual(names, ["victim_zone", "zone_gc_thread"])

    def test_enclosing_picks_innermost(self):
        s = anchor.enclosing(anchor.symbols(corpus(), "gc.c"), [22, 31])
        self.assertEqual(s["sym"], "zone_gc_thread")

    def test_span_across_two_symbols_is_file_level(self):
        """새 파일 Write처럼 여러 symbol에 걸치면 symbol anchor를 붙이지 않는다."""
        a = anchor.make(corpus(), "gc.c", [1, 30])
        self.assertEqual(a["kind"], "file")
        self.assertIsNone(a["sym"])


class PySymbols(unittest.TestCase):
    def test_nested_names_are_qualified(self):
        src = "class A:\n    def m(self):\n        return 1\n\ndef top():\n    pass\n"
        names = [s["sym"] for s in anchor.symbols(src, "x.py")]
        self.assertIn("A.m", names)
        self.assertIn("top", names)

    def test_syntax_error_yields_nothing(self):
        self.assertEqual(anchor.symbols("def (:", "x.py"), [])


class Resolve(unittest.TestCase):
    def setUp(self):
        self.text = corpus()
        self.anchor = anchor.make(self.text, "gc.c", [22, 31])

    def test_unchanged_resolves_by_hash(self):
        self.assertEqual(anchor.resolve(self.text, "gc.c", self.anchor)[0], 1)

    def test_moved_function_still_resolves_by_hash(self):
        moved = "/* 앞에 붙인 주석 */\n\n" + self.text
        self.assertEqual(anchor.resolve(moved, "gc.c", self.anchor)[0], 1)

    def test_body_change_resolves_by_name(self):
        changed = self.text.replace("return 0;\n}", "return 1;\n}")
        self.assertEqual(anchor.resolve(changed, "gc.c", self.anchor)[0], 2)

    def test_rename_needs_deep(self):
        renamed = self.text.replace("zone_gc_thread", "zone_gc_worker")
        self.assertEqual(anchor.resolve(renamed, "gc.c", self.anchor)[0], 4)
        stage, hit = anchor.resolve(renamed, "gc.c", self.anchor, deep=True)
        self.assertEqual(stage, 3)
        self.assertEqual(hit["sym"], "zone_gc_worker")

    def test_deleted_is_lost(self):
        gone = self.text.split("int zone_gc_thread")[0]
        self.assertEqual(anchor.resolve(gone, "gc.c", self.anchor, deep=True)[0], 4)
