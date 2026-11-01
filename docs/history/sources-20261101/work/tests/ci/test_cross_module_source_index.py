"""NX-100: cross-module source index honest-state tests.

RED-GREEN coverage (uses synthetic indexes to exercise the verifier's
honesty rules without mutating the real 33-entry index):
- Open Design-owned sources must NOT claim WORK-LAB implementation.
- A local-verified claim requires real existing target paths.
- Removing an implementation target causes verification to fail (auto-downgrade).
- A local-verified claim on a truly existing WORK-LAB path passes.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from verify_cross_module_source_index import verify  # noqa: E402


def _base_index() -> dict:
    return {
        "schemaVersion": "work-lab/cross-module-source-index/v1",
        "scope": ["workflow-assistance", "work-lab-observer"],
        "generated_at": "test",
        "adopt_now_total": 0,
        "adopt_now_complete_in_worklab": 0,
        "adopt_now_partial_in_worklab": 0,
        "adopt_now_no_worklab_targets": 0,
        "entries": [],
    }


def _write_tmp(data: dict) -> Path:
    # Windows-safe: close the fd before returning so the file is not locked.
    fd, name = __import__("tempfile").mkstemp(suffix=".json", prefix="cross-index-")
    os.close(fd)
    Path(name).write_text(json.dumps(data), encoding="utf-8")
    return Path(name)


class CrossModuleSourceIndexTest(unittest.TestCase):
    def test_open_design_source_must_not_claim_worklab_implementation(self) -> None:
        data = _base_index()
        data["entries"] = [{
            "id": "od-x", "ownerModule": "OPEN-DESIGN-Assistance",
            "decisionStatus": "external-optional",
            "implementationStatus": "local-verified",  # dishonest
            "targetPaths": ["knowledge/foo"], "tests": [],
        }]
        tmp = _write_tmp(data)
        try:
            with self.assertRaises(ValueError) as ctx:
                verify(index_path=tmp)
            self.assertIn("must not claim", str(ctx.exception))
        finally:
            tmp.unlink()

    def test_local_verified_requires_existing_target(self) -> None:
        data = _base_index()
        data["entries"] = [{
            "id": "wl-x", "ownerModule": "workflow-assistance",
            "decisionStatus": "derive",
            "implementationStatus": "local-verified",
            "targetPaths": ["does/not/exist/anywhere"], "tests": [],
        }]
        tmp = _write_tmp(data)
        try:
            with self.assertRaises(ValueError) as ctx:
                verify(index_path=tmp)
            self.assertIn("does not exist", str(ctx.exception))
        finally:
            tmp.unlink()

    def test_removing_target_auto_downgrades(self) -> None:
        """Removing an implementation target makes the honest claim fail."""
        data = _base_index()
        existing = ROOT / ".project/governance" / "contracts" / "contract-catalog.json"
        data["entries"] = [{
            "id": "wl-x", "ownerModule": "workflow-assistance",
            "decisionStatus": "derive",
            "implementationStatus": "local-verified",
            "targetPaths": [".project/governance/contracts/contract-catalog.json"], "tests": [],
        }]
        tmp = _write_tmp(data)
        backup = existing.with_suffix(".json.bak")
        try:
            # target exists -> passes
            self.assertIsNotNone(verify(index_path=tmp))
            # remove the target to simulate deletion
            existing.rename(backup)
            try:
                with self.assertRaises(ValueError) as ctx:
                    verify(index_path=tmp)
                self.assertIn("does not exist", str(ctx.exception))
            finally:
                backup.rename(existing)
        finally:
            tmp.unlink()

    def test_local_verified_on_existing_worklab_path_passes(self) -> None:
        data = _base_index()
        data["entries"] = [{
            "id": "wl-x", "ownerModule": "workflow-assistance",
            "decisionStatus": "derive",
            "implementationStatus": "local-verified",
            "targetPaths": [".project/governance/contracts/contract-catalog.json"], "tests": [],
        }]
        tmp = _write_tmp(data)
        try:
            result = verify(index_path=tmp)
            self.assertEqual(result["entries"], 1)
        finally:
            tmp.unlink()


if __name__ == "__main__":
    unittest.main()
