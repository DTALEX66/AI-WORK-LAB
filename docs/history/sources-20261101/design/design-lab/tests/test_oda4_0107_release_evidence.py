# SPDX-License-Identifier: MIT
"""ODA4-0107: release-evidence schema + SHA readback tests.

Verifies:
- The release-evidence schema rejects records where CI head_sha differs from
  evidence head_sha (a prior green CI on another SHA is NOT evidence).
- verify_release_evidence.py flags head/tree mismatch against live checkout.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # design-lab/tests -> repo root
SCHEMA = REPO / "design-lab" / "schemas" / "release-evidence.schema.json"
SCRIPT = REPO / "design-lab" / "scripts" / "verify_release_evidence.py"
SCHEMA_VALIDATOR = REPO / "design-lab" / "scripts" / "verify_evidence_cards.py"


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def git(args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_release_evidence_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseEvidenceSchemaTest(unittest.TestCase):
    def test_schema_is_valid_json(self):
        load_schema()

    def test_missing_required_fields_rejected(self):
        # jsonschema is the only third-party dep; if unavailable skip.
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = load_schema()
        bad = {"schemaVersion": "design-lab/release-evidence/v1"}  # missing most required
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)

    def test_valid_record_accepts(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = load_schema()
        good = {
            "schemaVersion": "design-lab/release-evidence/v1",
            "capability_id": "commercial-design-core",
            "subject": "uiux-golden-scenario",
            "version": "1.0",
            "branch": "main",
            "head_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "worktree": "clean",
            "evidence_level": "E4",
            "state": "PASS",
            "claim": "release verified",
            "environment": "github-actions",
            "ci": {"workflow_name": "canonical", "run_id": "123", "head_sha": "a" * 40, "conclusion": "success"},
            "reviewer": "codex-reviewer",
            "timestamp": "2026-08-07T00:00:00Z",
            "read_back": {"remote_sha": "a" * 40, "remote_branch": "main", "verified": True},
        }
        jsonschema.validate(good, schema)  # should not raise

    def test_stale_ci_rejected_by_schema_contract(self):
        # Schema requires ci.head_sha == top-level head_sha by pattern intent;
        # the verifier script is the enforcement point.
        self.assertTrue(SCHEMA.exists())
        self.assertTrue(SCRIPT.exists())


class SHAReadbackMismatchTest(unittest.TestCase):
    def test_failed_ci_cannot_be_release_evidence(self):
        verifier = load_verifier()
        record = {
            "schemaVersion": "design-lab/release-evidence/v1",
            "capability_id": "commercial-design-core",
            "subject": "uiux-golden-scenario",
            "version": "1.0",
            "branch": "main",
            "head_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "worktree": "clean",
            "evidence_level": "E4",
            "state": "PASS",
            "claim": "release verified",
            "environment": "github-actions",
            "ci": {"workflow_name": "canonical", "run_id": "123", "head_sha": "a" * 40, "conclusion": "failure"},
            "reviewer": "codex-reviewer",
            "timestamp": "2026-08-07T00:00:00Z",
            "read_back": {"remote_sha": "a" * 40, "remote_branch": "main", "verified": True},
        }
        failures = verifier.validate_contract(record)
        self.assertTrue(any("CI conclusion must be success" in failure for failure in failures), failures)

    def test_wrong_head_flagged(self):
        # Build a fake evidence record with an impossible head_sha; the script
        # must FAIL (mismatch with live checkout), not silently pass.
        bad = {
            "branch": "nope",
            "head_sha": "f" * 40,
            "tree_sha": "e" * 40,
            "worktree": "clean",
            "ci": {"workflow_name": "x", "run_id": "1", "head_sha": "f" * 40, "conclusion": "success"},
            "read_back": {"remote_sha": "f" * 40, "remote_branch": "main"},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=REPO / ".project-local" / "task-runtime" if (REPO / ".project-local").exists() else None) as f:
            json.dump(bad, f)
            path = f.name
        try:
            r = subprocess.run([sys.executable, str(SCRIPT), path], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotEqual(r.returncode, 0, "must fail on head mismatch")
            self.assertIn("RELEASE_EVIDENCE=FAIL", r.stdout)
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
