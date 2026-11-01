"""NF-10 / NF-11 / NF-12 convergence-audit contract tests.

Read-only, deterministic; consumes only git-tracked repository facts (so it
never reaches into user global state like ``~/.agents/skills``, and it never
claims a measured savings percentage it did not measure).  Loaded by file path
per the NF-02 convention (no `from services`).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOD = os.path.join(ROOT, "services", "policy", "convergence_audit.py")
CO = os.path.join(ROOT, "config", "config-ownership.json")
AR = os.path.join(ROOT, "config", "adapter-registry.json")

# git-tracked dependency manifests (NF-11 registered toolchains).
# P0-06 tail (ff08787): observer frontend is an npm project — pnpm residue
# (pnpm-lock.yaml / pnpm-workspace.yaml) was deleted; package-lock.json is
# the authoritative npm lockfile and the one CI installs from (npm ci).
MANIFESTS = [
    "apps/observer/frontend/package.json",
    "apps/observer/frontend/package-lock.json",
    "apps/observer/src-tauri/Cargo.toml",
    "apps/observer/src-tauri/Cargo.lock",
    "apps/token-monitor/package.json",
    "apps/token-monitor/src-tauri/Cargo.toml",
    "integrations/protocols/acp/requirements.txt",
    "packages/client-neutral-core/requirements.txt",
]


def _load():
    spec = importlib.util.spec_from_file_location("nf112_audit", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["nf112_audit"] = m
    spec.loader.exec_module(m)
    return m


class ConvergenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.co = json.load(open(CO, encoding="utf-8"))
        cls.ar = json.load(open(AR, encoding="utf-8"))

    # --- NF-10: skill lifecycle ----------------------------------------
    def test_nf10_repository_served_by_trigger_only(self):
        out = self.m.skill_load_surface(ROOT)
        # The repository ships exactly one on-demand skill.
        self.assertEqual(out["repository_skill_count"], 1)
        skill = out["skills"][0]
        self.assertEqual(skill["name"], "work-lab-workflow")
        self.assertTrue(skill["trigger"])  # has a trigger description
        self.assertTrue(skill["select_to_read_body"])
        self.assertIn("NOT read", out["global_backups_scope"])  # out of scope, not touched

    def test_nf10_user_native_fields_protected(self):
        out = self.m.protected_user_native_fields(self.co)
        # provider/model/reasoning/hook/MCP/plugin fields are all present and
        # NOT in a managed write set (i.e. clean).
        self.assertTrue(out["clean"], out["managed_reset_violations"])
        self.assertFalse(out["managed_reset_violations"])
        # The protected set is non-trivial and every entry is OBSERVE/FORBIDDEN.
        self.assertGreater(len(out["protected_fields"]), 5)
        for path, mode in out["mode_by_field"].items():
            self.assertIn(mode, ("OBSERVE", "FORBIDDEN"), f"{path}={mode} must not be MANAGE")

    # --- NF-11: dependency / runnable convergence ---------------------
    def test_nf11_manifests_present_and_apps_clean(self):
        out = self.m.dependency_convergence(ROOT, MANIFESTS)
        self.assertEqual(out["manifests_missing"], [])
        self.assertEqual(out["unexpected_apps"], [])
        self.assertEqual(out["forbidden_services"], [])
        self.assertTrue(out["clean"])
        # observer + token-monitor are the expected app surfaces.
        self.assertIn("observer", out["apps"])
        self.assertIn("token-monitor", out["apps"])

    # --- NF-12: model / version diff -----------------------------------
    def test_nf12_no_observed_version_is_unknown_never_passed(self):
        out = self.m.model_version_diff(self.ar)
        for e in out["entries"]:
            self.assertIsNone(e["observed_version"])
            self.assertEqual(e["status"], "UNKNOWN")
            self.assertEqual(e["model_behavior"], "UNVERIFIED")
        self.assertEqual(len(out["entries"]), len(self.ar.get("entries", [])))

    def test_nf12_same_version_is_no_change(self):
        # target "unknown" + observed "unknown" -> NO_CHANGE
        out = self.m.model_version_diff(self.ar, observed_versions={"hermes": "unknown"})
        hermes = next(e for e in out["entries"] if e["client"] == "hermes")
        self.assertEqual(hermes["status"], "NO_CHANGE")
        self.assertEqual(hermes["model_behavior"], "UNVERIFIED")  # still not "passed"

    # --- receipt determinism + no global read / no paid calls ----------
    def test_receipt_is_deterministic_and_sandboxed(self):
        a = self.m.build_convergence_receipt(ROOT, self.co, self.ar, MANIFESTS)
        b = self.m.build_convergence_receipt(ROOT, self.co, self.ar, MANIFESTS)
        self.assertEqual(a, b)
        self.assertFalse(a["global_state_read"])
        self.assertEqual(a["paid_calls"], 0)
        self.assertEqual(a["nf10_protected"]["clean"], True)
        self.assertEqual(a["nf11_dependency"]["clean"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
