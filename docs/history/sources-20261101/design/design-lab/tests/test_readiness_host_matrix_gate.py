# SPDX-License-Identifier: MIT
"""GD-1: fail-closed regression tests for verify_readiness_host_matrix.py.

The gate is the fail-closed consumer of the Adobe readiness host matrix
(E1 STRUCTURAL). Every invariant must FAIL CLOSED when the matrix drifts
into a false claim. Synthetic fixtures drive the parameterised cases; a
single live smoke test asserts the committed tree itself passes.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "design-lab" / "scripts"
SCHEMA_PATH = REPO / "design-lab" / "schemas" / "readiness-host-matrix.schema.json"


def load_gate():
    path = SCRIPTS / "verify_readiness_host_matrix.py"
    spec = importlib.util.spec_from_file_location("verify_readiness_host_matrix", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_matrix() -> dict:
    return {
        "schema_version": "design-lab/readiness-host-matrix/v1",
        "task_id": "DL-P0-070",
        "inventory_ref": "reports/current/MACHINE_INVENTORY.json",
        "inventory_observed_at": "2026-09-13T14:54:08+00:00",
        "evidence_level": "E1",
        "note": "synthetic fixture",
        "entries": [
            {
                "host_id": "adobe-photoshop",
                "host_version": "26.7.0.15",
                "install_alias": "photoshop-26",
                "presence_basis": "recorded inventory PRESENT",
                "present": True,
                "apis": [
                    {
                        "api_id": "photoshop-com-automation",
                        "kind": "COM",
                        "declared": True,
                        "verified": False,
                        "evidence_level": "E1",
                        "note": "installed, not live-verified",
                    }
                ],
                "editable_delivery": True,
                "readback_method": "reopen the delivered PSD and re-read layer state",
                "known_limits": ["live readback targets exactly this host version"],
                "evidence_refs": ["reports/current/MACHINE_INVENTORY.json", "docs/LOCAL_ENVIRONMENT.md"],
                "verification": {"state": "NOT_VERIFIED", "by": "not-recorded", "at": None, "evidence_ref": None},
            }
        ],
    }


def build_repo(tmp: Path) -> Path:
    (tmp / "reports/current").mkdir(parents=True, exist_ok=True)
    (tmp / "docs").mkdir(parents=True, exist_ok=True)
    (tmp / "reports/current/MACHINE_INVENTORY.json").write_text(
        json.dumps({"schemaVersion": "x", "observed_at": "2026-09-13T14:54:08+00:00"}),
        encoding="utf-8",
    )
    (tmp / "docs/LOCAL_ENVIRONMENT.md").write_text("# env\n", encoding="utf-8")
    return tmp


class ReadinessHostMatrixTests(unittest.TestCase):
    def setUp(self):
        self.g = load_gate()
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _run(self, matrix: dict, repo: Path, use_jsonschema: bool = False) -> list[str]:
        return self.g.check_matrix(matrix, self.schema, repo, use_jsonschema=use_jsonschema)

    def test_base_fixture_passes(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            errors = self._run(base_matrix(), repo)
            self.assertEqual(errors, [], msg=errors)

    def test_base_fixture_passes_jsonschema_path(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            errors = self._run(base_matrix(), repo, use_jsonschema=True)
            self.assertEqual(errors, [], msg=errors)

    def test_evidence_level_above_structural_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["evidence_level"] = "E3"
            errors = self._run(m, repo)
            self.assertTrue(any("E3" in e and "exceeds structural" in e for e in errors), errors)

    def test_inventory_ref_missing_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["inventory_ref"] = "reports/current/DOES_NOT_EXIST.json"
            errors = self._run(m, repo)
            self.assertTrue(any("inventory_ref does not resolve" in e for e in errors), errors)

    def test_inventory_observed_at_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["inventory_observed_at"] = "2020-01-01T00:00:00+00:00"
            errors = self._run(m, repo)
            self.assertTrue(any("stale matrix" in e for e in errors), errors)

    def test_verified_above_E1_without_live_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            api = m["entries"][0]["apis"][0]
            api["verified"] = True
            api["evidence_level"] = "E3"
            errors = self._run(m, repo)
            self.assertTrue(any("without VERIFIED_LIVE state" in e for e in errors), errors)

    def test_verified_E3_with_resolving_live_evidence_passes(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            (repo / "reports/ps-live.json").parent.mkdir(parents=True, exist_ok=True)
            (repo / "reports/ps-live.json").write_text("{}", encoding="utf-8")
            m = base_matrix()
            api = m["entries"][0]["apis"][0]
            api["verified"] = True
            api["evidence_level"] = "E3"
            m["entries"][0]["verification"] = {
                "state": "VERIFIED_LIVE", "by": "operator", "at": "2026-09-20T00:00:00+00:00",
                "evidence_ref": "reports/ps-live.json",
            }
            errors = self._run(m, repo)
            self.assertEqual(errors, [], msg=errors)

    def test_verified_E3_with_null_evidence_ref_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            api = m["entries"][0]["apis"][0]
            api["verified"] = True
            api["evidence_level"] = "E3"
            m["entries"][0]["verification"] = {
                "state": "VERIFIED_LIVE", "by": "operator", "at": "2026-09-20T00:00:00+00:00",
                "evidence_ref": None,
            }
            errors = self._run(m, repo)
            self.assertTrue(any("with null evidence_ref" in e for e in errors), errors)

    def test_verified_E3_with_unresolvable_evidence_ref_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            api = m["entries"][0]["apis"][0]
            api["verified"] = True
            api["evidence_level"] = "E3"
            m["entries"][0]["verification"] = {
                "state": "VERIFIED_LIVE", "by": "operator", "at": "2026-09-20T00:00:00+00:00",
                "evidence_ref": "reports/ghost-live.json",
            }
            errors = self._run(m, repo)
            self.assertTrue(any("evidence_ref does not resolve" in e for e in errors), errors)

    def test_editable_without_readback_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["entries"][0]["readback_method"] = None
            errors = self._run(m, repo)
            self.assertTrue(any("requires a non-null readback_method" in e for e in errors), errors)

    def test_readback_without_editable_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["entries"][0]["editable_delivery"] = False
            # readback_method is still set in the base matrix
            errors = self._run(m, repo)
            self.assertTrue(any("recorded readback_method without editable_delivery" in e for e in errors), errors)

    def test_absent_host_with_editable_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            entry = m["entries"][0]
            entry["present"] = False
            entry["readback_method"] = None  # keep the readback leg quiet so only the absent+editable fires
            errors = self._run(m, repo)
            self.assertTrue(any("absent host claims editable delivery" in e for e in errors), errors)

    def test_unresolvable_evidence_ref_drift_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = build_repo(Path(d))
            m = base_matrix()
            m["entries"][0]["evidence_refs"] = ["reports/current/MISSING-DOC.md"]
            errors = self._run(m, repo)
            self.assertTrue(any("evidence_ref does not resolve" in e for e in errors), errors)

    def test_live_repo_gate_passes(self):
        """The committed tree itself must pass (smoke; main() drives both validators)."""
        rc = self.g.main(REPO)
        self.assertEqual(rc, 0, msg="live repo must pass verify_readiness_host_matrix.py")


if __name__ == "__main__":
    unittest.main()
