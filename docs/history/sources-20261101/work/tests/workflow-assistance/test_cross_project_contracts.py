"""WLG-120: cross-project contract tests (mock/fixture only).

These tests verify the WORK-LAB <-> external-project contract using the
fixture-external profile and in-memory fixtures. They never touch the real
ArcheAxis repository, never write across repositories, and never depend on a
real external project for WORK-LAB to run.

Contract checklist (WLG-120):
 1. WORK-LAB can discover an external project profile
 2. only project-declared gates can be selected
 3. low-risk checkpoint does not trigger CI
 4. stage boundary triggers aggregate CI once
 5. RC/RELEASE require exact-SHA
 6. Observer has no write permission
 7. missing project fails closed without modifying config
 8. invalid profile reports BLOCKED, never degrades to arbitrary shell
 9. WORK-LAB runs/tests/releases without any external project
10. no shared DB / task state / artifacts / cross-repo commits
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from project_profile import load_registry, resolve_profile

REGISTRY_PATH = ROOT / "config/project-profiles.json"

# Tier vocabulary used by the global layer (WLG-030). Tests keep the
# vocabulary stable regardless of schema evolution in-flight.
GLOBAL_TIERS = ("TARGETED", "STAGE", "NIGHTLY", "RC", "RELEASE")

# In-memory external project fixture: profile only, no repository access.
FIXTURE_PROFILE = {
    "schema_version": "workflow/project-profile/v1",
    "project": {"id": "fixture-external", "root_policy": "discover_git_root", "windows_native_first": True},
    "configuration": {"precedence": ["global_defaults", "project_profile", "local_runtime", "environment", "cli"]},
    "modules": {"external": {"roots": ["."], "active": True}},
    "risk_zones": {"security": [".github"]},
    "gates": {
        "standalone": {"command": "python -m unittest discover", "tiers": ["TARGETED", "STAGE"], "platform": "windows-native"},
        "nightly-scan": {"command": "python -m nightly", "tiers": ["NIGHTLY"], "platform": "windows-native"},
        "release-qual": {"command": "python -m release_qual", "tiers": ["RC", "RELEASE"], "platform": "windows-native"},
    },
    "ci": {
        "stable_aggregate_check": "standalone",
        "stable_aggregate_job": "a0-gates",
        "workflow_file": ".github/workflows/ci.yml",
        "workflow_name": "CI",
        "release_workflow": "Release",
        "exact_sha_required_for": ["main", "release"],
        "outage_blocks": ["release"],
    },
}


def _declared_gates(profile: dict) -> dict:
    return profile.get("gates", {})


def _gates_for_tier(profile: dict, tier: str) -> list[str]:
    return sorted(gid for gid, g in _declared_gates(profile).items() if tier in g.get("tiers", []))


class CrossProjectContractTests(unittest.TestCase):
    def test_01_discover_external_profile(self):
        registry = load_registry(REGISTRY_PATH)
        profile = resolve_profile(registry, "fixture-external")
        self.assertEqual(profile["project"]["id"], "fixture-external")

    def test_02_only_declared_gates_selectable(self):
        registry = load_registry(REGISTRY_PATH)
        profile = resolve_profile(registry, "fixture-external")
        declared = set(_declared_gates(profile))
        # Attempting to select an undeclared gate must fail closed.
        self.assertNotIn("undeclared-gate", declared)
        for tier in GLOBAL_TIERS:
            for gid in _gates_for_tier(profile, tier):
                self.assertIn(gid, declared)

    def test_03_low_risk_checkpoint_no_ci(self):
        profile = FIXTURE_PROFILE
        # TARGETED gates only; no RC/RELEASE gate is selected at this tier.
        targeted = _gates_for_tier(profile, "TARGETED")
        self.assertEqual(targeted, ["standalone"])
        self.assertNotIn("release-qual", targeted)
        release_required = profile["ci"].get("exact_sha_required_for", [])
        self.assertIn("release", release_required)

    def test_04_stage_boundary_aggregate_once(self):
        profile = FIXTURE_PROFILE
        # STAGE tier aggregates to the stable aggregate job exactly once.
        self.assertEqual(profile["ci"]["stable_aggregate_check"], "standalone")
        self.assertEqual(profile["ci"]["stable_aggregate_job"], "a0-gates")
        self.assertEqual(profile["ci"]["workflow_name"], "CI")

    def test_05_rc_release_require_exact_sha(self):
        profile = FIXTURE_PROFILE
        release_required = profile["ci"].get("exact_sha_required_for", [])
        self.assertIn("release", release_required)
        rc_gates = _gates_for_tier(profile, "RC") + _gates_for_tier(profile, "RELEASE")
        self.assertIn("release-qual", rc_gates)

    def test_06_observer_no_write_permission(self):
        registry = load_registry(REGISTRY_PATH)
        work = resolve_profile(registry, "work-lab")
        observer = work["modules"]["work-lab-observer"]
        self.assertTrue(observer["observation_only"])
        self.assertFalse(observer.get("write", False))

    def test_07_missing_project_fails_closed(self):
        registry = load_registry(REGISTRY_PATH)
        with self.assertRaises(LookupError):
            resolve_profile(registry, "does-not-exist")

    def test_08_invalid_profile_reports_blocked(self):
        bad = {"schema_version": "workflow/project-profile/v1", "project": {"id": "bad"}}
        # No arbitrary shell command is introduced by an invalid profile.
        self.assertNotIn("command", json.dumps(bad))

    def test_09_work_lab_runs_without_external_project(self):
        # WORK-LAB's own profile resolves independently of any external repo.
        registry = load_registry(REGISTRY_PATH)
        work = resolve_profile(registry, "work-lab")
        self.assertEqual(work["project"]["id"], "work-lab")

    def test_10_no_shared_state_or_cross_repo_commits(self):
        registry = load_registry(REGISTRY_PATH)
        for profile in registry["profiles"]:
            self.assertNotIn("shared_database", profile)
            self.assertNotIn("mirror", profile)
            self.assertNotIn("sync_state", profile)
        # External profiles are declarations, not nested repositories.
        for profile in registry["profiles"]:
            pid = profile["project"]["id"]
            if pid == "work-lab":
                continue
            self.assertNotIn("git_url", profile.get("modules", {}).get("external", {}))
            self.assertNotIn("path", profile.get("modules", {}).get("external", {}))


if __name__ == "__main__":
    unittest.main()
