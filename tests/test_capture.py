"""Phase 1 — 실제 hook 입력 fixture로 capture 왕복을 검사한다."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codenotes import capture, config, extract, record, store  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hook_input")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


class Exclusion(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".codenotes"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def rel(self, p):
        return config.relativize(self.root, os.path.join(self.root, p))

    def test_source_file_passes(self):
        self.assertIsNone(config.excluded(self.root, self.rel("src/gc.c")))

    def test_generated_and_artifacts_blocked(self):
        self.assertEqual(config.excluded(self.root, self.rel("a/<mod>.mod.c")), "generated")
        self.assertEqual(config.excluded(self.root, self.rel("a/gc.o")), "skip-suffix")

    def test_outside_root_blocked(self):
        self.assertEqual(config.excluded(self.root, config.relativize(self.root, "/tmp/x.c")),
                         "outside-root")

    def test_nested_repo_blocked(self):
        os.makedirs(os.path.join(self.root, "vendor", "dep", ".git"))
        self.assertEqual(config.excluded(self.root, self.rel("vendor/dep/x.c")), "nested-repo")


class PatchStats(unittest.TestCase):
    def test_new_file_write_counts_whole_content(self):
        """새 파일 Write는 structuredPatch가 비어 온다 (Phase 0 실측)."""
        res = {"type": "create", "structuredPatch": [], "originalFile": "",
               "content": "a\nb\nc\n"}
        self.assertEqual(extract.patch_stats(res), (3, 0, [1, 3]))

    def test_edit_counts_hunk_lines(self):
        res = fixture("post_edit.json")["tool_response"]
        add, dele, span = extract.patch_stats(res)
        self.assertEqual((add, dele), (3, 1))
        self.assertEqual(span, [22, 31])


class Dedup(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".codenotes"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_same_tid_yields_same_id(self):
        a = record.make("toolu_x", "src/a.c", "s", "p", "edit",
                        record.file_anchor([1, 2]), 1, 0, "왜", "text", 0.7)
        b = record.make("toolu_x", "src/a.c", "s", "p", "edit",
                        record.file_anchor([1, 2]), 1, 0, "왜", "text", 0.7)
        self.assertEqual(a["id"], b["id"])

    def test_rebuild_seen_recovers_tids(self):
        rec = record.make("toolu_y", "src/a.c", "s", "p", "edit",
                          record.file_anchor(None), 1, 0, "왜", "turn", 0.3)
        store.append(self.root, "src/a.c", rec)
        self.assertEqual(store.rebuild_seen(self.root), ["toolu_y"])


class WhyBudget(unittest.TestCase):
    def test_clean_strips_and_truncates(self):
        s = extract.clean("  여러   줄\n에 걸친   말  " + "가" * 500, 240)
        self.assertEqual(len(s), 240)
        self.assertNotIn("\n", s)

    def test_empty_why_is_empty(self):
        self.assertEqual(extract.clean("", 240), "")


if __name__ == "__main__":
    unittest.main()
