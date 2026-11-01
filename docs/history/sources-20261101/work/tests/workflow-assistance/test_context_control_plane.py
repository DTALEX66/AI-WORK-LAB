"""Contract tests for the Context Control Plane (WL3-330 / Context Control Plane design).

Covers L1 stable prefix determinism, L2 cache truth (OBSERVED only, never 0),
L3 drift guard (missing critical fact fails closed), client adaptation surface,
and project isolation.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "receipts"))
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

from context_control_plane import ContextControlPlane, CLIENT_ADAPTATION
from context_bundle import ContextBundle, DRIFT_PRESERVE
from context_drift_guard import ContextDriftGuard


def make_preserve(**overrides) -> dict:
    p = {
        "user_goal": "g", "non_goals": "n", "allowed_paths": "p",
        "forbidden_paths": "f", "data_boundary": "b", "base_sha_tree": "sha",
        "known_failures": "k", "acceptance_commands": "a", "rollback_method": "r",
    }
    p.update(overrides)
    return p


class ContextControlPlaneTests(unittest.TestCase):
    def test_same_input_byte_identical_bundle(self) -> None:
        plane1 = ContextControlPlane("p", "r1")
        plane2 = ContextControlPlane("p", "r1")
        task = {"boundary": "b", "acceptance": "a"}
        r1 = plane1.assemble(task, {"system_boundary": "s", "evidence": "e"}, make_preserve())
        r2 = plane2.assemble(task, {"system_boundary": "s", "evidence": "e"}, make_preserve())
        self.assertEqual(r1["bundle"]["stable_digest"], r2["bundle"]["stable_digest"])

    def test_drift_missing_fails_closed(self) -> None:
        plane = ContextControlPlane("p", "r1")
        with self.assertRaises(ValueError):
            plane.assemble({"boundary": "b", "acceptance": "a"},
                           {"system_boundary": "s"}, make_preserve(user_goal=""))

    def test_assembly_order_ranked(self) -> None:
        plane = ContextControlPlane("p", "r1")
        r = plane.assemble({"boundary": "b", "acceptance": "a"},
                           {"system_boundary": "s", "evidence": "e", "transient": "t"},
                           make_preserve())
        ids = r["bundle"]["ordered_stable_block_ids"]
        self.assertEqual(ids, ["system_boundary", "evidence", "transient"])

    def test_client_adaptation_surface(self) -> None:
        plane = ContextControlPlane("p", "r1")
        r = plane.assemble({"boundary": "b", "acceptance": "a", "clients": ["dsh", "codex"]},
                           {"system_boundary": "s"}, make_preserve())
        self.assertIn("dsh", r["client_adaptation"])
        self.assertIn("codex", r["client_adaptation"])
        self.assertEqual(CLIENT_ADAPTATION["cc-switch"]["action"], "observe-only")

    def test_cache_truth_deepseek_observed_only(self) -> None:
        plane = ContextControlPlane("p", "r1")
        truth = plane.cache_truth("deepseek", {"cache_hit_tokens": 10, "cache_miss_tokens": 5})
        self.assertEqual(truth["cache_hit_rate"], 0.6667)
        self.assertEqual(truth["cache_quality"], "exact")

    def test_cache_truth_codex_unavailable_not_zero(self) -> None:
        plane = ContextControlPlane("p", "r1")
        truth = plane.cache_truth("codex", {"input_tokens": 10})
        self.assertIsNone(truth["cache_hit_rate"])
        self.assertEqual(truth["cost_note"], "subscription_not_metered")

    def test_project_isolation(self) -> None:
        a = ContextControlPlane("pa", "r1").assemble(
            {"boundary": "b", "acceptance": "a"}, {"system_boundary": "s"}, make_preserve())
        b = ContextControlPlane("pb", "r1").assemble(
            {"boundary": "b", "acceptance": "a"}, {"system_boundary": "s"}, make_preserve())
        self.assertNotEqual(a["bundle"]["stable_digest"], b["bundle"]["stable_digest"])


class ContextDriftGuardTests(unittest.TestCase):
    def test_all_preserved_passes(self) -> None:
        guard = ContextDriftGuard()
        ok, missing = guard.check({"drift_preserve": make_preserve()})
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_missing_any_fails(self) -> None:
        guard = ContextDriftGuard()
        for field in DRIFT_PRESERVE:
            p = make_preserve()
            p[field] = ""
            ok, missing = guard.check({"drift_preserve": p})
            self.assertFalse(ok, field)
            self.assertIn(field, missing)

    def test_compress_carries_drift_block(self) -> None:
        guard = ContextDriftGuard()
        bundle = {"schema_version": "workflow/context-bundle/v1", "project_id": "p",
                  "stable_digest": "abc", "drift_preserve": make_preserve()}
        comp = guard.compress(bundle, "summary")
        for k in DRIFT_PRESERVE:
            self.assertIn(k, comp["drift_preserve"])

    def test_compress_missing_drift_rejected(self) -> None:
        guard = ContextDriftGuard()
        with self.assertRaises(ValueError):
            guard.compress({"drift_preserve": {"user_goal": "x"}}, "s")

    def test_required_set_complete(self) -> None:
        self.assertEqual(set(ContextDriftGuard().required), set(DRIFT_PRESERVE))
        self.assertEqual(len(DRIFT_PRESERVE), 9)


if __name__ == "__main__":
    unittest.main()
