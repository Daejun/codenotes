"""Phase 3 — 편집 직전에 무엇을 주입하는가."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import anchor, record, render, store  # noqa: E402

SRC = '''static int helper(int a)
{
\treturn a + 1;
}

int worker(void *data)
{
\tint x = helper(1);
\treturn x;
}
'''


class Recall(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".codenotes"))
        self.rel = "gc.c"
        with open(os.path.join(self.root, self.rel), "w", encoding="utf-8") as f:
            f.write(SRC)
        self.note("worker", [6, 10], "worker가 helper 실패를 무시하고 있었다")
        self.note("helper", [1, 4], "a+1이 아니라 a+2여야 했다")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def note(self, sym, span, why, text=None):
        a = anchor.make(text or SRC, self.rel, span)
        self.assertEqual(a["sym"], sym)
        store.append(self.root, self.rel,
                     record.make("toolu_" + sym, self.rel, "s", "p", "edit",
                                 a, 1, 0, why, "text", 0.7))

    def edit_input(self, old):
        return {"file_path": os.path.join(self.root, self.rel),
                "old_string": old, "new_string": old + " ", "replace_all": False}

    def test_target_symbol_comes_first(self):
        out = render.render(self.root, self.rel, self.edit_input("\tint x = helper(1);"), 1200)
        self.assertIn("이번 편집 대상은 worker", out)
        self.assertLess(out.index("worker가 helper"), out.index("a+1이 아니라"))

    def test_no_notes_means_empty(self):
        with open(os.path.join(self.root, "other.c"), "w", encoding="utf-8") as f:
            f.write(SRC)
        self.assertEqual(render.render(self.root, "other.c", {}, 1200), "")

    def test_body_change_is_marked_stale(self):
        p = os.path.join(self.root, self.rel)
        with open(p, "w", encoding="utf-8") as f:
            f.write(SRC.replace("return x;", "return x + 1;"))
        out = render.render(self.root, self.rel, self.edit_input("\tint x = helper(1);"), 1200)
        self.assertIn("[본문이 바뀜]", out)

    def test_deleted_symbol_is_marked_lost(self):
        p = os.path.join(self.root, self.rel)
        with open(p, "w", encoding="utf-8") as f:
            f.write(SRC.split("int worker")[0])
        out = render.render(self.root, self.rel, {}, 1200)
        self.assertIn("[그 위치는 사라짐]", out)

    def test_budget_is_respected(self):
        full = render.render(self.root, self.rel, {}, 1200)
        self.assertIn("a+1이 아니라", full)
        tight = render.render(self.root, self.rel, {}, len(full) - 20)
        self.assertLessEqual(len(tight), len(full) - 20)
        self.assertNotIn("a+1이 아니라", tight)      # 예산에 못 들어간 것은 잘린다

    def test_low_confidence_is_dropped(self):
        store.append(self.root, self.rel,
                     record.make("toolu_low", self.rel, "s", "p", "edit",
                                 anchor.make(SRC, self.rel, [6, 10]), 1, 0,
                                 "믿을 수 없는 이유", "turn", 0.1))
        self.assertNotIn("믿을 수 없는", render.render(self.root, self.rel, {}, 1200))

    def test_replace_all_does_not_narrow(self):
        ti = self.edit_input("\treturn x;")
        ti["replace_all"] = True
        self.assertNotIn("이번 편집 대상은", render.render(self.root, self.rel, ti, 1200))
