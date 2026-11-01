from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/impact_planner.py"
LIVE_PROFILE = ROOT / ".project/governance/work-lab.project-profile.yaml"


def load_module():
    spec = importlib.util.spec_from_file_location("impact_planner", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROFILE = {
    "schema": "work-lab-project-profile/v1",
    "project": {"id": "work-lab", "root_policy": "discover_git_root", "windows_native_first": True},
    "modules": {
        "workflow": {"roots": ["packages/client-neutral-core"]},
        "observer": {"roots": ["apps/observer"], "depends_on": ["workflow"]},
    },
    "risk_zones": {"critical": [".github/workflows/**", ".project/governance/**"]},
    "gates": {
        "workflow": {"command": "python workflow.py", "tiers": ["module"], "platform": "any"},
        "observer": {"command": "python observer.py", "tiers": ["module"], "platform": "any"},
        "integration": {"command": "python integration.py", "tiers": ["full"], "platform": "any"},
    },
    "ci": {"stable_aggregate_check": "aggregate", "exact_sha_required_for": ["critical"], "outage_blocks": ["release"]},
}


class ImpactPlannerTests(unittest.TestCase):
    def test_canonical_project_profile_loads_with_contract_schema_version(self) -> None:
        module = load_module()
        profile = module.load_profile(Path(__file__).resolve().parents[2] / ".project/governance" / "work-lab.project-profile.yaml")
        self.assertEqual(profile["schema_version"], "workflow/project-profile/v1")
        self.assertEqual(profile["ci"]["workflow_name"], "work-lab-gate")
        self.assertEqual(profile["ci"]["stable_aggregate_job"], "aggregate")
        self.assertEqual(
            profile["gates"]["token-monitor"]["paths"],
            ["apps/token-monitor/**"],
        )

    def test_token_monitor_path_selects_its_dedicated_gate(self) -> None:
        module = load_module()
        profile = module.load_profile(Path(__file__).resolve().parents[2] / ".project/governance" / "work-lab.project-profile.yaml")
        plan = module.build_plan(
            profile,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["apps/token-monitor/src-tauri/src/lib.rs"],
        )
        self.assertIn("token-monitor", plan["required_gates"])

    def test_critical_ci_path_selects_supply_chain_security_gate(self) -> None:
        module = load_module()
        profile = module.load_profile(Path(__file__).resolve().parents[2] / ".project/governance" / "work-lab.project-profile.yaml")
        plan = module.build_plan(
            profile,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=[".github/workflows/work-lab-gate.yml"],
        )
        self.assertEqual(
            plan["required_gates"],
            ["integration", "observer", "supply-chain-security", "token-monitor", "workflow"],
        )

    def test_workflow_change_expands_to_transitive_dependents(self) -> None:
        module = load_module()
        plan = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["packages/client-neutral-core/scripts/task_ledger.py"],
        )
        self.assertEqual(plan["required_gates"], ["observer", "workflow"])
        self.assertEqual(plan["risk"], "medium")
        self.assertEqual(plan["delivery_effect"], "none")
        self.assertEqual(len(plan["plan_digest"]["value"]), 64)

    def test_external_design_path_fails_closed_to_all_active_gates(self) -> None:
        module = load_module()
        plan = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["external/handoff-pointer.txt"],
        )
        self.assertEqual(plan["required_gates"], ["integration", "observer", "workflow"])

    def test_governance_change_is_critical_and_requires_integration(self) -> None:
        module = load_module()
        plan = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=[".project/governance/contracts/contract-catalog.json"],
            delivery_effect="push",
            platform_scope=["linux", "windows"],
        )
        self.assertEqual(plan["risk"], "critical")
        self.assertIn("integration", plan["required_gates"])
        self.assertEqual(plan["platform_scope"], ["linux", "windows"])

    def test_unknown_path_fails_closed_to_all_configured_gates(self) -> None:
        module = load_module()
        plan = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["unclassified/new-boundary.txt"],
        )
        self.assertEqual(plan["risk"], "critical")
        self.assertEqual(plan["required_gates"], ["integration", "observer", "workflow"])

    def test_plan_digest_ignores_timestamp_and_display_id(self) -> None:
        module = load_module()
        first = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["external/handoff-pointer.txt"],
            plan_id="local",
            generated_at="2026-08-07T00:00:00Z",
        )
        second = module.build_plan(
            PROFILE,
            repository="DTALEX66/WORK-LAB",
            commit="commit",
            tree="tree",
            changed_paths=["external/handoff-pointer.txt"],
            plan_id="cloud",
            generated_at="2026-08-07T01:00:00Z",
        )
        self.assertEqual(first["plan_digest"], second["plan_digest"])


class UnselectedChangeTests(unittest.TestCase):
    """P2-04 (2026-10-08): a change the mapping does not cover must never yield an empty plan.

    Proven before the fix: a path inside a declared module root whose module had no same-named gate made
    `required_gates` empty with risk "medium" — a plan that reads like a cheap PASS. A gate-id set the CI
    aggregate does not know about is the same class of failure from the other side.
    """

    def profile(self):
        import copy
        return copy.deepcopy(PROFILE)

    def test_a_module_without_a_same_named_gate_is_refused_at_load(self) -> None:
        import tempfile
        module = load_module()
        broken = self.profile()
        broken["modules"]["control-plane"] = {"roots": ["services/control"]}
        with tempfile.TemporaryDirectory(dir=ROOT / ".project-local" / "runs") as raw:
            path = Path(raw) / "profile.yaml"
            import yaml
            path.write_text(yaml.safe_dump(broken, sort_keys=False), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                module.load_profile(path)
            self.assertIn("no same-named gate", str(caught.exception))

    def test_an_unselected_change_escalates_to_every_gate(self) -> None:
        module = load_module()
        orphaned = self.profile()
        # bypass load_profile's check on purpose: this is the shape that used to pass silently
        orphaned["modules"]["orphan"] = {"roots": ["services/orphan"]}
        plan = module.build_plan(orphaned, repository="r", commit="c", tree="t",
                                 changed_paths=["services/orphan/x.py"])
        self.assertEqual(plan["risk"], "critical")
        self.assertEqual(sorted(plan["required_gates"]), sorted(orphaned["gates"]))

    def test_a_path_outside_every_root_still_escalates(self) -> None:
        module = load_module()
        plan = module.build_plan(self.profile(), repository="r", commit="c", tree="t",
                                 changed_paths=["elsewhere/x.py"])
        self.assertEqual(plan["risk"], "critical")

    def test_no_change_requires_nothing(self) -> None:
        """Negative control: the escalation must be triggered by a change, not by an empty input."""
        module = load_module()
        plan = module.build_plan(self.profile(), repository="r", commit="c", tree="t", changed_paths=[])
        self.assertEqual(plan["required_gates"], [])
        self.assertEqual(plan["risk"], "low")

    def test_the_canonical_profile_keeps_the_ci_gate_set_exactly(self) -> None:
        """scripts/ci/aggregate_gate.py compares the plan against its own PLAN_GATES.

        A profile gate that the aggregate does not know rejects every plan, and a gate it knows but the
        profile lacks makes skipped_gates incomplete — so the two sets are asserted equal here rather than
        discovered in CI.
        """
        module = load_module()
        profile = module.load_profile(LIVE_PROFILE)
        aggregate = (ROOT / "scripts/ci/aggregate_gate.py").read_text(encoding="utf-8")
        declared = aggregate.split("PLAN_GATES = {", 1)[1].split("}", 1)[0]
        plan_gates = {token.strip().strip('"\'') for token in declared.split(",") if token.strip()}
        self.assertEqual(set(profile["gates"]), plan_gates)

    def test_the_supporting_surfaces_select_the_workflow_job_instead_of_everything(self) -> None:
        """The precision P2-04 actually buys, with the transitive dependent named, not hidden.

        `observer` appears in every workflow-facing expectation because the profile declares
        observer depends_on workflow — a workflow-side change must re-run the read-only projection's own
        job. That is the planner working, not over-selecting. What used to be forced and no longer is:
        token-monitor and supply-chain-security.
        """
        module = load_module()
        profile = module.load_profile(LIVE_PROFILE)
        all_gates = set(profile["gates"])
        for changed, expected in (
            ("services/control/control_service.py", {"workflow", "observer"}),
            ("services/orchestration/sidecar.py", {"workflow", "observer"}),
            ("integrations/executors/codex/codex_adapter.py", {"workflow", "observer"}),
            ("packages/contracts/README.md", {"workflow", "integration", "observer"}),
        ):
            with self.subTest(changed=changed):
                plan = module.build_plan(profile, repository="r", commit="c", tree="t",
                                          changed_paths=[changed])
                self.assertEqual(set(plan["required_gates"]), expected,
                                 f"{changed} selected {plan['required_gates']} (risk {plan['risk']})")
                self.assertNotIn("token-monitor", plan["required_gates"])
                self.assertNotIn("supply-chain-security", plan["required_gates"])
                self.assertLess(len(plan["required_gates"]), len(all_gates))

    def test_a_schema_change_stays_in_the_critical_zone(self) -> None:
        """Precision must not loosen the declared critical surfaces."""
        module = load_module()
        profile = module.load_profile(LIVE_PROFILE)
        plan = module.build_plan(profile, repository="r", commit="c", tree="t",
                                  changed_paths=["packages/contracts/schemas/workflow/"
                                                 "control-operation.schema.json"])
        self.assertEqual(plan["risk"], "critical")
        self.assertEqual(set(plan["required_gates"]), set(profile["gates"]))

    def test_an_unnamed_surface_still_requires_the_whole_set(self) -> None:
        module = load_module()
        profile = module.load_profile(LIVE_PROFILE)
        plan = module.build_plan(profile, repository="r", commit="c", tree="t",
                                 changed_paths=["apps/control-surface/index.html"])
        self.assertEqual(plan["risk"], "critical",
                         "a surface nobody named must fail safe to every gate")


if __name__ == "__main__":
    unittest.main()


class UnclassifiedPathReportingTests(unittest.TestCase):
    """W07 (2026-10-15): an escalation to every gate must name its cause.

    Measured before this: `build_plan` collected the unmapped paths and then escalated risk to critical and
    required every gate WITHOUT writing the paths into the plan -- so a reader saw "run everything" with
    nothing to act on, and the cheapest fix (declare the path under a module root) was not discoverable from
    the artifact. Fail-closed behaviour is unchanged; what changed is that the reason is now readable.
    """

    def _plan(self, *paths: str) -> dict:
        module = load_module()
        profile = module.load_profile(LIVE_PROFILE)
        return module.build_plan(profile=profile, repository="DTALEX66/WORK-LAB",
                                 commit="a" * 40, tree="b" * 40, changed_paths=list(paths))

    def test_an_unmapped_path_is_named_with_reason_and_required_classification(self) -> None:
        plan = self._plan("some/unmapped/surface.txt")
        entries = {entry["path"]: entry for entry in plan["unclassified_paths"]}
        self.assertIn("some/unmapped/surface.txt", entries)
        self.assertIn("no module root", entries["some/unmapped/surface.txt"]["reason"])
        self.assertTrue(entries["some/unmapped/surface.txt"]["needs"].strip(),
                        "an unclassified path must say what classification it requires")
        self.assertEqual("critical", plan["risk"], "an unmapped path still escalates: fail-closed is unchanged")
        self.assertEqual(sorted(plan["required_gates"]),
                         plan["required_gates"], "required gates stay a sorted list")

    def test_a_mapped_path_is_not_reported_as_unclassified(self) -> None:
        plan = self._plan("services/orchestration/sidecar.py", "apps/observer/frontend/src/lib/api.ts")
        self.assertEqual([], plan["unclassified_paths"],
                         "a path a module root or gate pattern selects is classified, not unknown")

    def test_the_plan_still_validates_against_its_own_schema(self) -> None:
        """build_plan validates internally; this pins that the new key is in the schema, not merely emitted."""
        plan = self._plan("some/unmapped/surface.txt")
        self.assertIn("unclassified_paths", plan)
        self.assertTrue(plan["plan_digest"]["value"], "the digest must cover the new field")
