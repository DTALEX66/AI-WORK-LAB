"""W09 (2026-10-17): a recorded client capability may not outrun its evidence.

The live registry passes today, and that is the least interesting half. The point of this module is the
falsifications: each one plants a promotion the project's own wording forbids ("不把有安装或有manifest记为集成
已完成") and requires the checker to report it BY CLIENT ID, because a silent promotion is invisible precisely
where it matters -- a reader planning against capabilities that were never verified.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_adapter_support_levels.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_adapter_support_levels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def entry(client_id: str, **overrides):
    base = {
        "id": client_id,
        "support_level": "manifest-only",
        "operations": ["detect", "capabilities", "observe"],
        "detection": {"mode": "static", "evidence_state": "UNVERIFIED"},
        "provenance": {"source_kind": "external-manifest", "version": "UNVERIFIED"},
        "policy_projection": {"supported": False, "apply_supported": False,
                              "readback_supported": False, "rollback_supported": False},
    }
    base.update(overrides)
    return base


class SupportLevelTests(unittest.TestCase):
    def test_the_live_registry_passes(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertEqual(0, proc.returncode, out)
        self.assertIn("ADAPTER_SUPPORT_LEVELS_PASS", out)

    def test_a_manifest_only_client_claiming_write_is_reported(self) -> None:
        module = load_module()
        registry = {"entries": [entry("workbuddy", operations=["detect", "apply"])]}
        problems = module.audit(registry, set())
        self.assertTrue(any("workbuddy" in p and "manifest-only" in p for p in problems), problems)

    def test_static_detection_may_not_claim_apply(self) -> None:
        module = load_module()
        registry = {"entries": [entry("cursor", support_level="deep",
                                      detection={"mode": "static", "evidence_state": "UNVERIFIED"},
                                      policy_projection={"apply_supported": True})]}
        problems = module.audit(registry, set())
        self.assertTrue(any("cursor" in p and "static" in p for p in problems), problems)

    def test_apply_without_a_reviewed_adapter_directory_is_reported(self) -> None:
        module = load_module()
        registry = {"entries": [entry("newclient", support_level="deep",
                                      provenance={"source_kind": "repository", "version": "1.2.3"},
                                      operations=["detect", "apply"],
                                      detection={"mode": "isolated", "evidence_state": "UNVERIFIED"},
                                      policy_projection={"apply_supported": True})]}
        problems = module.audit(registry, {"integrations/executors/hermes/x.py"})
        self.assertTrue(any("newclient" in p and "adapter directory" in p for p in problems), problems)

    def test_an_unverified_version_may_not_be_promoted(self) -> None:
        module = load_module()
        registry = {"entries": [entry("qoder", support_level="deep")]}
        problems = module.audit(registry, set())
        self.assertTrue(any("qoder" in p and "UNVERIFIED" in p for p in problems), problems)

    def test_a_missing_evidence_state_is_reported(self) -> None:
        module = load_module()
        registry = {"entries": [entry("ghost", detection={"mode": "static"})]}
        problems = module.audit(registry, set())
        self.assertTrue(any("ghost" in p and "evidence_state" in p for p in problems), problems)

    def test_an_empty_registry_is_a_failure_not_a_pass(self) -> None:
        """A checker that sees nothing must not report a clean pass."""
        module = load_module()
        self.assertTrue(module.audit({"entries": []}, set()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
