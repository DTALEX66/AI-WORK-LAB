#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic tests for the context capsule / session receipt (Prompt F,
DL-CLOUD-2026-09-25): capsule completeness, non-authoritative marking, the
STALE branch, and the receipt's reference-not-reclaim contract.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load(name: str):
    path = ROOT / "design-lab" / "scripts" / "context_capsule.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


cap = load("context_capsule_under_test_f")


class CapsuleCompletenessTest(unittest.TestCase):
    def setUp(self):
        self.capsule = cap.build_capsule(ROOT)

    def test_all_fields_present_with_value_or_absent(self):
        for field in cap.CAPSULE_FIELDS:
            self.assertIn(field, self.capsule, f"capsule missing {field}")
            value = self.capsule[field]
            self.assertIsInstance(value, (str, dict))
            if isinstance(value, dict):
                self.assertIn("absent", value, f"{field} absent-marker without reason")

    def test_non_authoritative_marker(self):
        self.assertIs(self.capsule["non_authoritative"], True)
        self.assertEqual(self.capsule["schema_version"], "design-lab/context-capsule/v1")

    def test_no_field_is_guessed(self):
        # every value that is not a real string is an explicit absent-with-reason
        for field, value in self.capsule.items():
            if isinstance(value, dict):
                self.assertEqual(set(value), {"absent"}, f"{field} dict carries more than a reason")

    def test_authority_id_came_from_machine_ledger(self):
        authority_index = ROOT / ".project" / "governance" / "authority-index.json"
        if authority_index.exists():
            expected = json.loads(authority_index.read_text(encoding="utf-8")).get("authorityId")
            if expected:
                self.assertEqual(self.capsule["authority_id"], expected)


class StaleBranchTest(unittest.TestCase):
    def test_advanced_main_reports_stale(self):
        capsule = cap.build_capsule(ROOT)
        # simulate main advancing one commit past the capsule's observed SHA
        old_main = capsule["live_main_sha"] if isinstance(capsule["live_main_sha"], str) else ""
        capsule["live_main_sha"] = "0" * 40  # a divergent observed main
        stale = cap.capsule_is_stale(capsule, ROOT)
        # the capsule no longer matches live main -> STALE is reported
        self.assertTrue(any("live_main" in s for s in stale), f"expected live_main stale, got {stale}")

    def test_fresh_capsule_is_not_stale(self):
        capsule = cap.build_capsule(ROOT)
        stale = cap.capsule_is_stale(capsule, ROOT)
        self.assertEqual(stale, [], f"fresh capsule reported stale: {stale}")

    def test_missing_field_is_stale(self):
        capsule = cap.build_capsule(ROOT)
        capsule.pop("task_ledger_sha256")
        stale = cap.capsule_is_stale(capsule, ROOT)
        self.assertTrue(any("task_ledger_sha256" in s for s in stale))


class ReceiptReferenceTest(unittest.TestCase):
    def test_receipt_references_capsule_by_hash(self):
        capsule = cap.build_capsule(ROOT)
        receipt = cap.build_receipt(
            capsule=capsule, task_id="t1", files_changed=["a.py"], commands=["pytest"],
            tests=["ok"], evidence_ids=["E1"], host_receipts=[], blockers=[],
            rollback="git revert X", next_atomic_task="none")
        self.assertIn("input_capsule_sha256", receipt)
        self.assertIs(receipt["non_authoritative"], True)
        self.assertEqual(receipt["task_id"], "t1")
        # the hash is deterministic for the same capsule content
        again = cap.build_receipt(
            capsule=capsule, task_id="t1", files_changed=["a.py"], commands=["pytest"],
            tests=["ok"], evidence_ids=["E1"], host_receipts=[], blockers=[],
            rollback="git revert X", next_atomic_task="none")
        self.assertEqual(receipt["input_capsule_sha256"], again["input_capsule_sha256"])


if __name__ == "__main__":
    unittest.main()
