"""Tests for task governance (WL-170/180/190): task protocol, completion
authority, permission gate.

Repo convention (mirrors test_session_federation.py): modules under
services/ are loaded by spec — no package __init__ — so each file is loaded
via importlib and pre-registered in sys.modules under a stable name so shared
enums stay singletons across the three governance modules.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "services" / "task-governance"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, GOV / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TaskProtocolTests(unittest.TestCase):
    def test_mode_classification(self):
        tp = _load("task_protocol.py", "tg_tp")
        self.assertEqual(tp.classify(), tp.TaskMode.NATIVE)
        self.assertEqual(tp.classify(cross_agent=True), tp.TaskMode.PORTABLE)
        self.assertEqual(
            tp.classify(cross_session=True, cross_machine=True), tp.TaskMode.PORTABLE
        )
        # risk dominates: any high-risk topic forces AUDITED even when no
        # cross-boundary flag is set
        self.assertEqual(
            tp.classify(topic_hints=["release"]), tp.TaskMode.AUDITED
        )

    def test_high_risk_topics_are_case_insensitive(self):
        tp = _load("task_protocol.py", "tg_tp")
        self.assertEqual(tp.audit_risk(["Delete", "  SECURITY ", "nope"]),
                         ["delete", "security"])
        self.assertEqual(tp.audit_risk(["bananas"]), [])

    def test_artifacts_contract(self):
        tp = _load("task_protocol.py", "tg_tp")
        self.assertEqual(tp.required_artifacts(tp.TaskMode.NATIVE), ())
        self.assertEqual(
            tp.required_artifacts(tp.TaskMode.PORTABLE),
            tp.PORTABLE_ARTIFACTS,
        )
        # audited inherits the portable triple
        self.assertEqual(
            tp.required_artifacts(tp.TaskMode.AUDITED), tp.PORTABLE_ARTIFACTS
        )
        self.assertEqual(
            tp.required_extras(tp.TaskMode.AUDITED), tp.AUDITED_EXTRAS
        )
        self.assertEqual(tp.required_extras(tp.TaskMode.NATIVE), ())

    def test_validate_completion_flags_missing(self):
        tp = _load("task_protocol.py", "tg_tp")
        ok = tp.validate_completion(
            tp.TaskMode.AUDITED,
            artifacts_present=["contract.json", "events.jsonl", "capsule.md"],
            extras_present=["independent_evaluator", "typed_receipt", "owner_epoch",
                            "rollback", "human_approval"],
        )
        self.assertTrue(ok["ok"])
        # drop one extra -> not ok, exactly that one missing
        partial = tp.validate_completion(
            tp.TaskMode.AUDITED,
            artifacts_present=["contract.json", "events.jsonl", "capsule.md"],
            extras_present=["typed_receipt"],
        )
        self.assertFalse(partial["ok"])
        self.assertIn("independent_evaluator", partial["missing_extras"])
        self.assertNotIn("typed_receipt", partial["missing_extras"])


class CompletionAuthorityTests(unittest.TestCase):
    def _chain(self, ca, auth, task_id="t"):
        auth.submit(task_id, ca.EvidenceClaim("output", "worker", "did it", ca.EvidenceLevel.SELF, "build.log"))
        auth.submit(task_id, ca.EvidenceClaim("verification", "worker", "reran", ca.EvidenceLevel.REPRODUCIBLE, "tests.log"))
        auth.submit(task_id, ca.EvidenceClaim("independent_check", "reviewer", "audited", ca.EvidenceLevel.INDEPENDENT, "audit.txt"))

    def test_full_chain_passes(self):
        ca = _load("completion_authority.py", "tg_ca")
        auth = ca.CompletionAuthority()
        self._chain(ca, auth)
        rec = auth.evaluate("t", mode="native", approver="manager")
        self.assertEqual(rec.status, ca.AcceptanceStatus.PASSED)
        self.assertEqual(rec.missing, [])
        # receipt hash is stable and re-verifiable
        self.assertTrue(ca.CompletionAuthority.verify_receipt_sha(rec))
        payload = json.dumps(rec.to_dict(), sort_keys=True, default=str)
        self.assertIn(rec.receipt_sha256[0:12], json.dumps(rec.to_dict()))

    def test_bare_done_is_not_passed(self):
        # ch 16: "Worker says DONE -> PASS" is forbidden — no links, no PASS.
        ca = _load("completion_authority.py", "tg_ca")
        auth = ca.CompletionAuthority()
        rec = auth.evaluate("bare", mode="native", approver="manager")
        self.assertEqual(rec.status, ca.AcceptanceStatus.PENDING)
        self.assertIn("link:output", rec.missing)
        self.assertIn("link:verification", rec.missing)
        self.assertIn("link:independent_check", rec.missing)

    def test_self_check_alone_never_suffices(self):
        # three links, but the independent check is only SELF level -> defect
        ca = _load("completion_authority.py", "tg_ca")
        auth = ca.CompletionAuthority()
        auth.submit("s", ca.EvidenceClaim("output", "w", "o", ca.EvidenceLevel.SELF))
        auth.submit("s", ca.EvidenceClaim("verification", "w", "v", ca.EvidenceLevel.SELF))
        auth.submit("s", ca.EvidenceClaim("independent_check", "w", "i", ca.EvidenceLevel.SELF))
        rec = auth.evaluate("s", mode="native", approver="m")
        self.assertEqual(rec.status, ca.AcceptanceStatus.PENDING)
        self.assertIn("link:independent_check!level", rec.missing)

    def test_audited_missing_extras_is_pending(self):
        ca = _load("completion_authority.py", "tg_ca")
        auth = ca.CompletionAuthority()
        self._chain(ca, auth)
        # portable triple present but audited extras absent
        rec = auth.evaluate(
            "t", mode="audited",
            artifacts_present=["contract.json", "events.jsonl", "capsule.md"],
            extras_present=["typed_receipt"],
            approver="m",
        )
        self.assertEqual(rec.status, ca.AcceptanceStatus.PENDING)
        self.assertIn("extra:human_approval", rec.missing)
        self.assertNotIn("extra:typed_receipt", rec.missing)

    def test_rejection_reasons_force_rejected(self):
        ca = _load("completion_authority.py", "tg_ca")
        auth = ca.CompletionAuthority()
        self._chain(ca, auth)
        rec = auth.evaluate("t", mode="native", approver="m",
                            reject_reasons=["acceptance check X failed"])
        self.assertEqual(rec.status, ca.AcceptanceStatus.REJECTED)
        self.assertIn("acceptance check X failed", rec.missing)


class PermissionGateTests(unittest.TestCase):
    def test_out_of_scope_denied(self):
        pg = _load("permission_gate.py", "tg_pg")
        gate = pg.PermissionGate()
        # full default scope: filesystem is auto at LOW
        d = gate.evaluate("filesystem", target="docs/plan.md")
        self.assertEqual(d.status, pg.DecisionStatus.ALLOWED)
        self.assertEqual(d.risk, pg.RiskTier.LOW)
        # restrict scope to filesystem-only -> shell is out of scope => denied
        ro = pg.PermissionGate(gate.readonly())
        self.assertEqual(ro.evaluate("shell").status, pg.DecisionStatus.DENIED)

    def test_sensitive_targets_escalate_to_human(self):
        pg = _load("permission_gate.py", "tg_pg")
        gate = pg.PermissionGate()
        d = gate.evaluate("filesystem", target=".env")
        self.assertEqual(d.status, pg.DecisionStatus.NEEDS_HUMAN)
        self.assertTrue(d.gate_required)
        self.assertEqual(d.risk, pg.RiskTier.CRITICAL)

    def test_destructive_critical_needs_human(self):
        pg = _load("permission_gate.py", "tg_pg")
        gate = pg.PermissionGate()
        d = gate.evaluate("destructive", scope="delete production db")
        self.assertEqual(d.status, pg.DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(d.risk, pg.RiskTier.CRITICAL)

    def test_forbidden_host_denied(self):
        pg = _load("permission_gate.py", "tg_pg")
        gate = pg.gate_for_policy({
            "scope": ["network"], "human_gate_from": "MEDIUM",
            "forbidden_hosts": ["internal.corp"],
        })
        self.assertEqual(gate.evaluate("network").status, pg.DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(gate.evaluate("network", scope="internal.corp").status,
                         pg.DecisionStatus.DENIED)
        # a kind outside the narrowed scope is denied, not human-gated
        self.assertEqual(gate.evaluate("credential").status, pg.DecisionStatus.DENIED)

    def test_risk_tier_resolvable_by_name_and_value(self):
        pg = _load("permission_gate.py", "tg_pg")
        by_name = pg.gate_for_policy({"human_gate_from": "CRITICAL"})
        self.assertEqual(by_name.policy.human_gate_from, pg.RiskTier.CRITICAL)
        by_value = pg.gate_for_policy({"human_gate_from": 2})
        self.assertEqual(by_value.policy.human_gate_from, pg.RiskTier.MEDIUM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
