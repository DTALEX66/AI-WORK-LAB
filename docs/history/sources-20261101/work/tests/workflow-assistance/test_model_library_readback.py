"""Gate: no model's size may be the size of the whole shared blob store.

The readback itself cannot run in CI - a required job that can only skip on a runner without the weight
root would fail the aggregate gate, which is why it is deliberately local. What CI can check is the
receipt it publishes: the tracked artifact must show that each model names its own bytes, and the helper
that enforces this must be shown to refuse the old shape.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "docs/audits/MODEL_LIBRARY_READBACK_2026-10-07.json"
SCRIPT = ROOT / "scripts/audit/model_library_readback.py"

spec = importlib.util.spec_from_file_location("model_library_readback", SCRIPT)
readback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readback)  # type: ignore[attr-defined]


class StoreTotalGuard(unittest.TestCase):
    def test_a_row_naming_its_own_blob_is_clean(self) -> None:
        rows = [{"id": "m1", "store_dir": "ollama/blobs", "store_dir_bytes": 1000,
                 "bytes_observed": 400}]
        self.assertEqual([], readback.store_total_masquerading_as_model(rows))

    def test_a_row_whose_size_equals_the_store_is_refused(self) -> None:
        rows = [{"id": "m1", "store_dir": "ollama/blobs", "store_dir_bytes": 1000,
                 "bytes_observed": 1000}]
        problems = readback.store_total_masquerading_as_model(rows)
        self.assertEqual(1, len(problems))
        self.assertIn("store's size, not the model's", problems[0])

    def test_a_row_without_a_store_directory_is_not_guessed_at(self) -> None:
        self.assertEqual([], readback.store_total_masquerading_as_model(
            [{"id": "m1", "bytes_observed": 1000}]))


class PublishedReceiptShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RECEIPT.is_file():
            raise unittest.SkipTest("the model-library receipt is not in the tree")
        cls.doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        cls.models = cls.doc["models"]

    def test_the_receipt_reports_no_failures(self) -> None:
        self.assertEqual([], self.doc["failures"])

    def test_no_model_carries_the_store_total_and_every_sized_row_names_its_basis(self) -> None:
        self.assertEqual([], readback.store_total_masquerading_as_model(self.models))
        for row in self.models:
            if row.get("bytes_observed"):
                self.assertIn(row.get("bytesBasis"), {"file", "directory", "blob"}, row["id"])

    def test_blob_sized_models_are_distinct_numbers(self) -> None:
        # Two models sharing one blob is legitimate dedup and is reported as such; what must not happen
        # is two models silently publishing the same figure that is really the store total.
        seen: dict[int, list[str]] = {}
        for row in self.models:
            if row.get("bytesBasis") == "blob" and row.get("bytes_observed"):
                seen.setdefault(row["bytes_observed"], []).append(row["id"])
        for size, ids in seen.items():
            if len(ids) > 1:
                self.assertIn(str(size), json.dumps(self.doc.get("modelsSharingOneBlob") or {}),
                              f"{ids} share {size} B but the receipt does not say so")


if __name__ == "__main__":
    unittest.main(verbosity=2)
