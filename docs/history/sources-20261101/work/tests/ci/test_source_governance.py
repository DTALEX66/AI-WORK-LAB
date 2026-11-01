"""NX-110: source governance (license/NOTICE/size) test suite.

RED-GREEN coverage:
- Implemented entry with licenseVerified=false fails.
- Implemented entry with non-permissive license fails.
- Forbidden tracked artifact (node_modules / .pyc / binary / vendor) fails.
- NOTICE.md missing fails.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from verify_source_governance import verify, FORBIDDEN_TRACKED  # noqa: E402


def _base_index() -> dict:
    return {
        "schemaVersion": "work-lab/cross-module-source-index/v1",
        "scope": ["workflow-assistance", "work-lab-observer"],
        "adopt_now_total": 0, "adopt_now_complete_in_worklab": 0,
        "adopt_now_partial_in_worklab": 0, "adopt_now_no_worklab_targets": 0,
        "entries": [],
    }


def _write_tmp(data: dict) -> Path:
    fd, name = tempfile.mkstemp(suffix=".json", prefix="gov-")
    os.close(fd)
    Path(name).write_text(json.dumps(data), encoding="utf-8")
    return Path(name)


class SourceGovernanceTest(unittest.TestCase):
    def _patch_index(self, entries: list) -> Path:
        data = _base_index()
        data["entries"] = entries
        return _write_tmp(data)

    def _entry(self, **kw) -> dict:
        base = {
            "id": "wl-x", "ownerModule": "workflow-assistance",
            "decisionStatus": "derive", "implementationStatus": "local-verified",
            "license": "MIT", "licenseVerified": True, "targetPaths": [], "tests": [],
        }
        base.update(kw)
        return base

    def test_real_repo_passes(self) -> None:
        result = verify()
        self.assertEqual(result["forbidden"], 0)
        self.assertTrue(result["notice_ok"])

    def test_implemented_without_license_verified_fails(self) -> None:
        tmp = self._patch_index([self._entry(licenseVerified=False)])
        try:
            with mock.patch("verify_source_governance.INDEX", tmp):
                with self.assertRaises(ValueError) as ctx:
                    verify()
            self.assertIn("licenseVerified=true", str(ctx.exception))
        finally:
            tmp.unlink()

    def test_implemented_with_non_permissive_license_fails(self) -> None:
        tmp = self._patch_index([self._entry(license="Proprietary", licenseVerified=True)])
        try:
            with mock.patch("verify_source_governance.INDEX", tmp):
                with self.assertRaises(ValueError) as ctx:
                    verify()
            self.assertIn("not permissive", str(ctx.exception))
        finally:
            tmp.unlink()

    def test_forbidden_tracked_artifact_matches(self) -> None:
        for path in ["node_modules/x/y.js", "a/__pycache__/b.pyc",
                     "bin/app.exe", "vendor/upstream/main.c", "build/out.js"]:
            self.assertTrue(FORBIDDEN_TRACKED.search(path), "should flag: " + path)

    def test_clean_path_not_flagged(self) -> None:
        for path in ["packages/client-neutral-core/src/x.py",
                     ".project/governance/contracts/c.json",
                     "scripts/ci/verify.py", "tests/ci/t.py"]:
            self.assertFalse(FORBIDDEN_TRACKED.search(path), "should NOT flag: " + path)

    def test_notice_missing_fails(self) -> None:
        tmp = self._patch_index([])
        notice = ROOT / "NOTICE.md"
        backup = notice.with_suffix(".md.bak")
        try:
            with mock.patch("verify_source_governance.INDEX", tmp):
                notice.rename(backup)
                try:
                    with self.assertRaises(ValueError) as ctx:
                        verify()
                    self.assertIn("NOTICE", str(ctx.exception))
                finally:
                    backup.rename(notice)
        finally:
            tmp.unlink()


if __name__ == "__main__":
    unittest.main()
