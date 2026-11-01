"""NF-05-SYNC: client capabilities registered BY ROLE, reusing native probes.

Proves the acceptance rows for AT-18/19/20:
  * missing Hermes, the other usable executors still work (and vice versa) —
    executor selection is by capability, not a fixed dependency;
  * the SAME adapter is configured by two projects without per-project
    branching in the code (dispatch keys on adapter_id);
  * every used client has a per-capability coverage row; a missing interface
    is reported PARTIAL / UNSUPPORTED, never "full-feature done".

Plus the role constraints: a planning/reviewing software (GitHub / CC Switch)
is registered under its real role and is not usable as a code executor
without a probed execute capability.

Pure and deterministic: no network, no process launch, no paid call.
"""
from __future__ import annotations

import os
import sys
import unittest

_PKG = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..",
    "packages", "client-neutral-core", "scripts"))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import capability_roles as cr  # noqa: E402


def build_registry() -> cr.CapabilityRoleRegistry:
    reg = cr.CapabilityRoleRegistry()
    # Hermes: full executor (probe confirmed execute + resume + status + cancel)
    reg.register_software(
        "hermes", adapter_id="hermes-native",
        roles=["executor", "observer"],
        probed_capabilities={"execute", "status", "cancel", "resume", "observe"},
    )
    # Codex: executor too, but no cancel/resume in this version
    reg.register_software(
        "codex", adapter_id="codex-native",
        roles=["executor"],
        probed_capabilities={"execute", "status"},
    )
    # GitHub: planner / reviewer / storage — NOT an executor
    reg.register_software(
        "github", adapter_id="github-native",
        roles=["planner", "reviewer", "storage"],
        probed_capabilities={"publish", "review", "store", "read"},
        prerequisites={"execute": "needs a real code-execution adapter; planning-only"},
    )
    # CC Switch: config routing only, manifest-level
    reg.register_software(
        "cc-switch", adapter_id="ccswitch-native",
        roles=["observer"],
        probed_capabilities={"read", "observe"},
    )
    # two projects share the hermes adapter
    reg.register_project_binding("work-lab", "executor", "hermes-native")
    reg.register_project_binding("aether-radar", "executor", "hermes-native")
    return reg


class TestExecutorDecoupling(unittest.TestCase):
    def test_missing_hermes_leaves_other_executors(self):
        reg = build_registry()
        all_exec = reg.executor_candidates()
        self.assertIn("hermes", all_exec)
        self.assertIn("codex", all_exec)
        remaining = reg.executor_candidates(exclude=["hermes"])
        self.assertNotIn("hermes", remaining)
        self.assertIn("codex", remaining)  # codex still works

    def test_missing_codex_leaves_hermes(self):
        reg = build_registry()
        remaining = reg.executor_candidates(exclude=["codex"])
        self.assertIn("hermes", remaining)
        self.assertNotIn("codex", remaining)


class TestRoleConstraints(unittest.TestCase):
    def test_github_is_not_a_code_executor(self):
        reg = build_registry()
        # github has no 'execute' probe -> not a candidate executor
        self.assertNotIn("github", reg.executor_candidates())
        # but it is a planner/reviewer (publish + review probed)
        self.assertTrue(reg.can_plan_publish("github"))
        self.assertIn("github", reg.roles_with_capability("publish"))

    def test_cc_switch_is_not_disguised_as_executor(self):
        reg = build_registry()
        self.assertNotIn("cc-switch", reg.executor_candidates())

    def test_executor_role_without_execute_is_flagged(self):
        reg = cr.CapabilityRoleRegistry()
        # a software claims the executor role but its probe has no execute
        reg.register_software(
            "fake-exec", adapter_id="fe",
            roles=["executor"], probed_capabilities={"read"})
        flags = reg.role_constraint_report()
        self.assertIn("fake-exec", flags.get("executor_without_execute", []))


class TestAdapterReuse(unittest.TestCase):
    def test_two_projects_share_one_adapter_with_no_branching(self):
        reg = build_registry()
        reuse = reg.adapter_reused_by("hermes-native")
        self.assertEqual(reuse["owner"], "hermes")
        self.assertEqual(reuse["projects"], ["aether-radar", "work-lab"])
        # dispatch key is the adapter_id, identical for both projects
        self.assertEqual(reg._projects["work-lab"]["executor"], "hermes-native")
        self.assertEqual(reg._projects["aether-radar"]["executor"], "hermes-native")

    def test_project_cannot_bind_unregistered_adapter(self):
        reg = build_registry()
        with self.assertRaises(KeyError):
            reg.register_project_binding("newproj", "executor", "unregistered-adapter")


class TestCapabilityIsDynamicNotFixedEnum(unittest.TestCase):
    def test_capability_set_is_probe_driven(self):
        reg = cr.CapabilityRoleRegistry()
        reg.register_software(
            "custom-x", adapter_id="cx",
            roles=["executor"],
            probed_capabilities={"execute", "status", "trace", "diff_preview"},
        )
        # probe-confirmed, including non-standard 'trace'/'diff_preview'
        self.assertTrue(reg.has_capability("custom-x", "trace"))
        # an un-probed capability is simply absent, not invented
        self.assertFalse(reg.has_capability("custom-x", "cancel"))

    def test_unknown_role_rejected(self):
        reg = cr.CapabilityRoleRegistry()
        with self.assertRaises(ValueError):
            reg.register_software("x", adapter_id="xa", roles=["wizard"],
                                  probed_capabilities={"read"})


class TestCoverageMatrix(unittest.TestCase):
    def test_every_used_client_has_a_coverage_row(self):
        reg = build_registry()
        rows = reg.coverage_matrix(
            ["hermes", "codex", "github", "cc-switch"],
            ["read", "publish", "execute", "status", "cancel", "resume", "observe"])
        by_name = {r["software"]: r for r in rows}
        self.assertEqual(set(by_name), {"hermes", "codex", "github", "cc-switch"})
        # hermes: full within these caps? has execute+status+cancel+resume+observe (no read/publish)
        self.assertEqual(by_name["hermes"]["status"], "PARTIAL")
        self.assertIn("execute", by_name["hermes"]["supported"])
        # cc-switch has no execute/publish -> its status reflects the gap
        self.assertEqual(by_name["cc-switch"]["missing"],
                         [c for c in ["read","publish","execute","status","cancel","resume","observe"]
                          if c not in by_name["cc-switch"]["supported"]])

    def test_missing_interface_reported_partial_not_full(self):
        reg = build_registry()
        res = reg.missing_capability_prerequisite("github", "execute")
        self.assertEqual(res["state"], "GAP")
        # the prerequisite is a non-empty explanation of what would close the gap
        self.assertTrue(res["prerequisite"])
        # a probed capability is supported, not a gap
        ok = reg.missing_capability_prerequisite("github", "publish")
        self.assertEqual(ok["state"], "SUPPORTED")

    def test_unsupported_when_no_capability_probed(self):
        reg = cr.CapabilityRoleRegistry()
        reg.register_software(
            "manifest-only-y", adapter_id="my",
            roles=["observer"], probed_capabilities=set())
        rows = reg.coverage_matrix(["manifest-only-y"],
                                   ["execute", "status", "observe"])
        self.assertEqual(rows[0]["status"], "UNSUPPORTED")
        self.assertEqual(rows[0]["supported"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
