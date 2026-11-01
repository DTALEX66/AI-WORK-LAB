"""Contract tests for stable prefix / context bundle (WL3-330 / MR-10).

Covers taskpack §20.4: byte-identical prefix, timestamp pollution, project
switch isolation, rules-revision invalidation, missing acceptance fails
closed, path escape rejection.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from context_bundle import ContextBundle, build_from_directory

PRESERVE = {
    "user_goal": "goal", "non_goals": "non", "allowed_paths": "p",
    "forbidden_paths": "f", "data_boundary": "b", "base_sha_tree": "sha",
    "known_failures": "k", "acceptance_commands": "a", "rollback_method": "r",
}


class ContextBundleTests(unittest.TestCase):
    def test_same_input_byte_identical_digest(self) -> None:
        a = ContextBundle("p1", "r1").build({"f": "hello"}, "b", "a", preserve=PRESERVE)
        b = ContextBundle("p1", "r1").build({"f": "hello"}, "b", "a", preserve=PRESERVE)
        self.assertEqual(a["stable_prefix"], b["stable_prefix"])
        self.assertEqual(a["stable_digest"], b["stable_digest"])

    def test_timestamp_not_polluting_stable_prefix(self) -> None:
        b1 = ContextBundle("p1", "r1").build(
            {"f": "text 2026-08-16T00:00:00Z tmp/abc"}, "b", "a", preserve=PRESERVE)
        b2 = ContextBundle("p1", "r1").build(
            {"f": "text 2026-08-17T01:02:03Z tmp/xyz"}, "b", "a", preserve=PRESERVE)
        self.assertEqual(b1["stable_digest"], b2["stable_digest"])

    def test_project_switch_changes_digest(self) -> None:
        a = ContextBundle("p1", "r1").build({"f": "x"}, "b", "a", preserve=PRESERVE)
        b = ContextBundle("p2", "r1").build({"f": "x"}, "b", "a", preserve=PRESERVE)
        self.assertNotEqual(a["stable_digest"], b["stable_digest"])
        self.assertTrue(ContextBundle.project_mismatch(a, "p2"))

    def test_rules_revision_change_invalidates(self) -> None:
        a = ContextBundle("p1", "rev-1").build({"f": "x"}, "b", "a", preserve=PRESERVE)
        self.assertTrue(ContextBundle.revision_changed(a, "rev-2"))

    def test_missing_acceptance_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            ContextBundle("p1", "r1").build({"f": "x"}, "boundary", "  ", preserve=PRESERVE)

    def test_missing_boundary_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            ContextBundle("p1", "r1").build({"f": "x"}, "", "acceptance", preserve=PRESERVE)

    def test_validate_requires_all_fields(self) -> None:
        ok, msg = ContextBundle.validate({"schema_version": "x"})
        self.assertFalse(ok)
        self.assertIn("missing", msg)

    def test_build_from_directory_reads_selected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("alpha", encoding="utf-8")
            (root / "b.txt").write_text("beta", encoding="utf-8")
            bundle = build_from_directory(ContextBundle("p", "r"), root,
                                          ["a.txt", "b.txt"], "b", "a", preserve=PRESERVE)
            self.assertEqual(bundle["stable_prefix"].count("["), 2)

    def test_path_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                build_from_directory(ContextBundle("p", "r"), root,
                                     ["../outside.txt"], "b", "a", preserve=PRESERVE)

    def test_json_field_order_preserved(self) -> None:
        # JSON key order is preserved as-is (no re-sorting) => deterministic per input
        b1 = ContextBundle("p", "r").build({"f": '{"a":1,"b":2}'}, "b", "a", preserve=PRESERVE)
        b2 = ContextBundle("p", "r").build({"f": '{"a":1,"b":2}'}, "b", "a", preserve=PRESERVE)
        self.assertEqual(b1["stable_digest"], b2["stable_digest"])


if __name__ == "__main__":
    unittest.main()
