"""Tests for the curator fold-back policy.

The safety rule under test is the whole point of the tool: automation may only ADD.
A curator edit that removes, trims or rewrites repository content must be reported
for a human, because that is precisely the destructive case the managed-asset guard
exists to catch. Each rule gets its own case, including the conservative one where a
single rewrite blocks the entire target even though other files were pure additions.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "integrations/executors/hermes" / "curator_foldback.py"


def load():
    spec = importlib.util.spec_from_file_location("curator_foldback_under_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = b"line one\nline two\nline three\n"


class ClassificationTests(unittest.TestCase):
    """Per-file classification, as a pure function."""

    def setUp(self) -> None:
        self.m = load()

    def test_identical_bytes_are_unchanged(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, BASE), self.m.UNCHANGED)

    def test_line_ending_difference_is_recognised_and_not_a_rewrite(self) -> None:
        crlf = BASE.replace(b"\n", b"\r\n")
        self.assertEqual(self.m.classify_file(BASE, crlf), self.m.LINE_ENDINGS)

    def test_added_file(self) -> None:
        self.assertEqual(self.m.classify_file(None, BASE), self.m.ADDED)

    def test_appended_lines_are_extended(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, BASE + b"line four\n"), self.m.EXTENDED)

    def test_inserted_lines_are_extended(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, b"line one\nnew\nline two\nline three\n"), self.m.EXTENDED)

    def test_removed_file_is_blocked(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, None), self.m.REMOVED)

    def test_deleted_lines_are_trimmed_and_blocked(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, b"line one\nline three\n"), self.m.TRIMMED)

    def test_changed_line_is_a_rewrite_and_blocked(self) -> None:
        self.assertEqual(self.m.classify_file(BASE, b"line one\nCHANGED\nline three\n"), self.m.REWRITTEN)


class TreeVerdictTests(unittest.TestCase):
    """Target-level verdicts."""

    def setUp(self) -> None:
        self.m = load()

    def test_identical_tree_is_identical(self) -> None:
        repo = {"SKILL.md": BASE}
        self.assertEqual(self.m.classify_tree(repo, dict(repo))["verdict"], self.m.IDENTICAL)

    def test_pure_addition_is_foldable(self) -> None:
        repo = {"SKILL.md": BASE}
        live = {"SKILL.md": BASE + b"line four\n"}
        result = self.m.classify_tree(repo, live)
        self.assertEqual(result["verdict"], self.m.FOLDABLE)
        self.assertEqual(result["auto_fold"], ["SKILL.md"])
        self.assertEqual(result["blocking"], [])

    def test_new_file_only_is_foldable(self) -> None:
        repo = {"SKILL.md": BASE}
        live = {"SKILL.md": BASE, "references/new.md": b"brand new\n"}
        result = self.m.classify_tree(repo, live)
        self.assertEqual(result["verdict"], self.m.FOLDABLE)
        self.assertEqual(result["auto_fold"], ["references/new.md"])

    def test_removal_blocks_the_whole_target(self) -> None:
        repo = {"SKILL.md": BASE, "references/gone.md": b"x\n"}
        live = {"SKILL.md": BASE}
        result = self.m.classify_tree(repo, live)
        self.assertEqual(result["verdict"], self.m.NEEDS_REVIEW)
        self.assertEqual(result["blocking"], ["references/gone.md"])

    def test_one_rewrite_blocks_even_when_other_files_were_added(self) -> None:
        repo = {"SKILL.md": BASE, "references/old.md": b"keep\n"}
        live = {"SKILL.md": BASE + b"added\n", "references/old.md": b"REPLACED\n"}
        result = self.m.classify_tree(repo, live)
        self.assertEqual(result["verdict"], self.m.NEEDS_REVIEW)
        self.assertEqual(result["files"]["SKILL.md"], self.m.EXTENDED)
        self.assertEqual(result["files"]["references/old.md"], self.m.REWRITTEN)


class FoldApplicationTests(unittest.TestCase):
    """Folding writes additions, normalises LF, and never deletes."""

    def setUp(self) -> None:
        self.m = load()

    def _trees(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        repo, live = root / "repo", root / "live"
        (repo / "references").mkdir(parents=True)
        (live / "references").mkdir(parents=True)
        return tmp, repo, live

    def test_fold_writes_additions_and_keeps_lf_for_policy_extensions(self) -> None:
        tmp, repo, live = self._trees()
        with tmp:
            (repo / "SKILL.md").write_bytes(b"a\nb\n")
            (live / "SKILL.md").write_bytes(b"a\r\nb\r\nc\r\n")  # extension + CRLF
            (live / "references" / "new.md").write_bytes(b"new\r\n")
            written = self.m.fold_target(live, repo)
            self.assertEqual(sorted(written), ["SKILL.md", "references/new.md"])
            self.assertEqual((repo / "SKILL.md").read_bytes(), b"a\nb\nc\n")
            self.assertEqual((repo / "references" / "new.md").read_bytes(), b"new\n")
            self.assertNotIn(b"\r\n", (repo / "SKILL.md").read_bytes())

    def test_fold_never_deletes_a_repository_file_missing_from_live(self) -> None:
        tmp, repo, live = self._trees()
        with tmp:
            (repo / "SKILL.md").write_bytes(b"a\n")
            (repo / "references" / "keep.md").write_bytes(b"must survive\n")
            (live / "SKILL.md").write_bytes(b"a\n")
            self.m.fold_target(live, repo)
            self.assertTrue((repo / "references" / "keep.md").is_file())
            self.assertEqual((repo / "references" / "keep.md").read_bytes(), b"must survive\n")

    def test_fold_is_idempotent(self) -> None:
        tmp, repo, live = self._trees()
        with tmp:
            (repo / "SKILL.md").write_bytes(b"a\n")
            (live / "SKILL.md").write_bytes(b"a\nb\n")
            self.assertEqual(self.m.fold_target(live, repo), ["SKILL.md"])
            self.assertEqual(self.m.fold_target(live, repo), [])

    def test_after_folding_the_trees_compare_identical(self) -> None:
        tmp, repo, live = self._trees()
        with tmp:
            (repo / "SKILL.md").write_bytes(b"a\nb\n")
            (live / "SKILL.md").write_bytes(b"a\r\nb\r\nadded\r\n")
            self.m.fold_target(live, repo)
            result = self.m.classify_tree(self.m.read_tree(repo), self.m.read_tree(live))
            # live is CRLF, repo is now LF: content equal, so only line endings remain
            self.assertEqual(result["verdict"], self.m.FOLDABLE)
            self.assertEqual(set(result["files"].values()), {self.m.LINE_ENDINGS})


if __name__ == "__main__":
    unittest.main()
