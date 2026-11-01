from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALL_GATES = ["workflow", "observer", "token-monitor", "supply-chain-security", "integration"]


def load_gate():
    path = ROOT / "scripts" / "ci" / "aggregate_gate.py"
    spec = importlib.util.spec_from_file_location("aggregate_gate", path)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load aggregate gate")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_plan(
    gate,
    *,
    required_gates=None,
    changed_paths=("README.md",),
    risk="medium",
    repository="DTALEX66/WORK-LAB",
    commit="c" * 40,
    tree="t" * 40,
    generated_at="2026-08-15T00:00:00Z",
    skipped_gates=None,
):
    if required_gates is None:
        required_gates = sorted(gate.PLAN_GATES)
    if skipped_gates is None:
        skipped_gates = [
            {"gate_id": g, "reason": "no changed path or transitive dependency selected this gate"}
            for g in sorted(gate.PLAN_GATES - set(required_gates))
        ]
    plan = {
        "schema_version": "workflow/gate-plan/v1",
        "plan_id": "work-lab-gate",
        "source_identity": {
            "repository": repository,
            "commit": {"algorithm": "repository-default", "object_type": "commit", "oid": commit},
            "tree": {"algorithm": "repository-default", "object_type": "tree", "oid": tree},
        },
        "changed_paths": list(changed_paths),
        "required_gates": list(required_gates),
        "skipped_gates": skipped_gates,
        "risk": risk,
        "delivery_effect": "none",
        "platform_scope": ["discovered"],
        "generated_at": generated_at,
    }
    plan["plan_digest"] = {"algorithm": "sha256", "value": gate._plan_digest(plan)}
    return plan


def make_payload(
    gate,
    plan,
    *,
    jobs,
    expected_repository="DTALEX66/WORK-LAB",
    expected_commit=None,
    expected_tree=None,
    expected_digest=None,
):
    return json.dumps(
        {
            "gate_plan": plan,
            "expected_plan_digest": expected_digest or plan["plan_digest"]["value"],
            "expected_head_sha": expected_commit or plan["source_identity"]["commit"]["oid"],
            "expected_head_tree": expected_tree or plan["source_identity"]["tree"]["oid"],
            "expected_repository": expected_repository,
            "jobs": jobs,
        }
    )


def all_jobs(required_gates, status="success", skipped="skipped"):
    jobs = {}
    for name in ALL_GATES:
        jobs[name] = status if name in required_gates else skipped
    return jobs


class AggregateGateTests(unittest.TestCase):
    def test_all_gates_success_with_plan_pass(self):
        gate = load_gate()
        plan = make_plan(gate)
        payload = make_payload(gate, plan, jobs=all_jobs(plan["required_gates"]))
        self.assertEqual(gate.main(payload), 0)

    def test_missing_plan_fails_closed(self):
        gate = load_gate()
        payload = json.dumps({"jobs": all_jobs(ALL_GATES)})
        self.assertEqual(gate.main(payload), 1)

    def test_retired_open_design_job_does_not_satisfy_gate(self):
        gate = load_gate()
        plan = make_plan(gate)
        payload = make_payload(
            gate,
            plan,
            jobs={"workflow": "success", "open-design": "success", "integration": "success"},
        )
        self.assertEqual(gate.main(payload), 1)

    def test_selected_token_monitor_failure_fails(self):
        gate = load_gate()
        plan = make_plan(gate, required_gates=["token-monitor"])
        payload = make_payload(gate, plan, jobs={"token-monitor": "skipped"})
        self.assertEqual(gate.main(payload), 1)
        payload = make_payload(gate, plan, jobs=all_jobs(["token-monitor"]))
        self.assertEqual(gate.main(payload), 0)

    def test_critical_under_selection_fails_closed(self):
        """A6: critical changed paths (.github/**, .project/governance/**, ...) must
        require ALL gates; an under-selecting plan fails even with green jobs."""
        gate = load_gate()
        plan = make_plan(
            gate,
            required_gates=["supply-chain-security"],
            changed_paths=[".github/workflows/work-lab-gate.yml"],
            risk="critical",
        )
        payload = make_payload(gate, plan, jobs=all_jobs(["supply-chain-security"]))
        self.assertEqual(gate.main(payload), 1)

    def test_critical_full_gates_pass(self):
        gate = load_gate()
        plan = make_plan(
            gate,
            changed_paths=[".github/workflows/work-lab-gate.yml"],
            risk="critical",
        )
        payload = make_payload(gate, plan, jobs=all_jobs(plan["required_gates"]))
        self.assertEqual(gate.main(payload), 0)

    def test_digest_and_identity_verified(self):
        gate = load_gate()
        plan = make_plan(gate, required_gates=["workflow"])
        payload = make_payload(gate, plan, jobs=all_jobs(["workflow"]))
        self.assertEqual(gate.main(payload), 0)
        # repository mismatch (A2)
        payload = make_payload(gate, plan, jobs=all_jobs(["workflow"]), expected_repository="WRONG/REPO")
        self.assertEqual(gate.main(payload), 1)
        # head tree mismatch (A3)
        payload = make_payload(gate, plan, jobs=all_jobs(["workflow"]), expected_tree="wrong-tree")
        self.assertEqual(gate.main(payload), 1)
        # head commit mismatch (existing contract)
        payload = make_payload(gate, plan, jobs=all_jobs(["workflow"]), expected_commit="wrong-commit")
        self.assertEqual(gate.main(payload), 1)

    def test_plan_digest_mismatch_fails_closed(self):
        gate = load_gate()
        plan = make_plan(gate)
        payload = make_payload(gate, plan, jobs=all_jobs(plan["required_gates"]), expected_digest="deadbeef")
        self.assertEqual(gate.main(payload), 1)

    def test_skipped_gates_must_cover_all_non_required(self):
        """A4: skipped_gates must exactly cover PLAN_GATES - required."""
        gate = load_gate()
        plan = make_plan(
            gate,
            required_gates=["workflow"],
            skipped_gates=[{"gate_id": "observer", "reason": "not selected"}],
        )
        payload = make_payload(gate, plan, jobs=all_jobs(["workflow"]))
        self.assertEqual(gate.main(payload), 1)

    def test_non_selected_gate_must_be_explicitly_skipped(self):
        """A8: a non-selected gate that ran (or is absent) instead of 'skipped'
        fails closed."""
        gate = load_gate()
        plan = make_plan(gate, required_gates=["workflow"])
        jobs = {name: "success" if name == "workflow" else "success" for name in ALL_GATES}
        payload = make_payload(gate, plan, jobs=jobs)
        self.assertEqual(gate.main(payload), 1)

    def test_missing_commit_identity_fails_closed(self):
        gate = load_gate()
        plan = make_plan(gate)
        plan["source_identity"]["commit"] = {"algorithm": "repository-default", "object_type": "commit"}
        plan["plan_digest"] = {"algorithm": "sha256", "value": gate._plan_digest(plan)}
        payload = make_payload(
            gate,
            plan,
            jobs=all_jobs(plan["required_gates"]),
            expected_commit="c" * 40,
            expected_tree="t" * 40,
        )
        self.assertEqual(gate.main(payload), 1)

    def test_nonempty_change_set_cannot_select_zero_gates(self):
        gate = load_gate()
        plan = make_plan(gate, required_gates=[], changed_paths=["README.md"], risk="low")
        payload = make_payload(gate, plan, jobs={})
        self.assertEqual(gate.main(payload), 1)

    def test_non_sha256_plan_digest_algorithm_fails_closed(self):
        gate = load_gate()
        plan = make_plan(gate)
        plan["plan_digest"] = {"algorithm": "md5", "value": gate._plan_digest(plan)}
        payload = make_payload(gate, plan, jobs=all_jobs(plan["required_gates"]))
        self.assertEqual(gate.main(payload), 1)

    def test_invalid_risk_value_fails_closed(self):
        gate = load_gate()
        plan = make_plan(gate, risk="catastrophic")
        plan["plan_digest"] = {"algorithm": "sha256", "value": gate._plan_digest(plan)}
        payload = make_payload(gate, plan, jobs=all_jobs(plan["required_gates"]))
        self.assertEqual(gate.main(payload), 1)


if __name__ == "__main__":
    unittest.main()
