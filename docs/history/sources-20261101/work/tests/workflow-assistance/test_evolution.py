"""Tests for the evolution plane (WL-330/340/350/360): the Penguin
provider, the ch 29 independent gate, the M1..M5 mutation policy, and
the Exo sandbox boundary.

Repo convention: load each service file by spec, pre-register in
sys.modules under a stable name.  No external evolution engine is
installed — the Penguin provider runs without a handle (the honest
UNAVAILABLE negative control) and the gate/policy/sandbox are the
locally-owned control plane WORK-LAB verifies end to end.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVO = ROOT / "services" / "evolution"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, EVO / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class PenguinProviderTests(unittest.TestCase):
    """WL-330: the 8-capability interface, honest without a live engine."""

    def _provider(self):
        p = _load("provider.py", "evo_p")
        return p, p.PenguinProvider()   # bare -> no live handle

    def test_bare_provider_is_unavailable(self):
        p, prov = self._provider()
        self.assertFalse(prov.available())
        self.assertTrue(prov.health()["external_engine"])
        # a benchmark with no live engine is UNAVAILABLE, not a number
        c = prov.create_candidate("base-1", kind="prompt")
        self.assertEqual(prov.benchmark(c)["status"], "UNAVAILABLE")

    def test_create_mutate_trace_snapshot_rollback(self):
        p, prov = self._provider()
        c = prov.create_candidate("base", kind="skill")
        m = prov.mutate_skill(c, "tighten guardrails")
        self.assertEqual(m.base_id, c.candidate_id)
        self.assertEqual(m.payload["delta"], "tighten guardrails")
        snap = prov.snapshot()["snapshot_id"]
        # mutate after the snapshot, then roll back to it
        prov.mutate_prompt(m, "after-snapshot change")
        self.assertTrue(prov.rollback(snap))
        ev = [e for e in prov.trace().events if e.get("op") == "rollback"]
        self.assertTrue(ev and ev[0].get("to") == snap)

    def test_rollback_missing_snapshot_is_false(self):
        p, prov = self._provider()
        self.assertFalse(prov.rollback("nope"))


class IndependentEvalTests(unittest.TestCase):
    """WL-340: ch 29's two structural invariants."""

    def _gate(self):
        iv = _load("independent_eval.py", "evo_iv")
        return iv, iv.EvolutionGate()

    def _candidate(self, producer="penguin"):
        p = _load("provider.py", "evo_p")
        prov = p.PenguinProvider()
        return prov.create_candidate("base", kind="prompt")

    def _full_evidence(self, iv):
        ev = {a: {"score": 0.9, "status": "ok", "note": "evidenced"}
              for a in iv.Axis.ORDER}
        return ev

    def test_self_evaluation_is_forbidden(self):
        iv, gate = self._gate()
        cand = self._candidate(producer="penguin")
        # an evaluator named exactly the producer trips the ch 29 guard
        self_evaluator = iv.Evaluator("penguin", evidence=self._full_evidence(iv))
        with self.assertRaises(iv.SelfEvaluationError):
            gate.evaluate(cand, evaluator=self_evaluator)

    def test_pass_receipt_when_all_axes_scored(self):
        iv, gate = self._gate()
        cand = self._candidate()
        evaluator = iv.Evaluator("independent-lab", evidence=self._full_evidence(iv))
        receipt = gate.evaluate(cand, evaluator=evaluator)
        self.assertEqual(receipt.overall, "PASS")
        self.assertEqual(receipt.producer, "penguin")
        int(receipt.receipt_sha256(), 16)

    def test_pending_when_an_axis_is_unavailable(self):
        iv, gate = self._gate()
        cand = self._candidate()
        ev = self._full_evidence(iv)
        ev[iv.Axis.HOLDOUT] = {"score": 0.0, "status": "unavailable"}
        evaluator = iv.Evaluator("independent-lab", evidence=ev)
        receipt = gate.evaluate(cand, evaluator=evaluator)
        self.assertEqual(receipt.overall, "PENDING")

    def test_only_worklab_authority_may_promote(self):
        iv, gate = self._gate()
        cand = self._candidate()
        receipt = gate.evaluate(cand, evaluator=iv.Evaluator(
            "independent-lab", evidence=self._full_evidence(iv)))
        # the WORK-LAB authority promotes a fully-passing receipt
        self.assertEqual(gate.promote(cand, receipt, by="work-lab-evolution-gate",
                                      allow_worklab=True), "PASS")
        # a non-WORK-LAB authority (even the evaluator) is structurally refused
        with self.assertRaises(iv.PromotionAuthorityError):
            gate.promote(cand, receipt, by="independent-lab")
        with self.assertRaises(iv.PromotionAuthorityError):
            gate.promote(cand, receipt, by="work-lab-evolution-gate")  # no allow flag


class MutationPolicyTests(unittest.TestCase):
    """WL-350: the fixed M1..M5 mapping, M5 self-accept refused."""

    def _gate(self):
        mp = _load("mutation_policy.py", "evo_mp")
        return mp, mp.MutationGate()

    def test_fixed_policy_mapping(self):
        mp, gate = self._gate()
        expected = {"M1": "auto_experiment", "M2": "auto_experiment",
                    "M3": "sandbox", "M4": "security_eval_approval",
                    "M5": "independent_approval"}
        for lv, disp in expected.items():
            self.assertEqual(mp.Disposition.POLICY[lv], disp)

    def test_m1_m2_auto_allowed(self):
        mp, gate = self._gate()
        for lv in ("M1", "M2"):
            d = gate.decide(lv)
            self.assertTrue(d.allowed, lv)
            int(d.receipt_sha256(), 16)

    def test_m3_needs_sandbox(self):
        mp, gate = self._gate()
        self.assertFalse(gate.decide("M3").allowed)
        self.assertTrue(gate.decide("M3", in_sandbox=True).allowed)

    def test_m4_needs_security_eval_approval(self):
        mp, gate = self._gate()
        self.assertFalse(gate.decide("M4").allowed)
        d = gate.decide("M4", security_passed=True, eval_passed=True,
                        approval={"granted": True})
        self.assertTrue(d.allowed)

    def test_m5_forbids_self_accept(self):
        mp, gate = self._gate()
        # the modifying agent accepting its own governance change is refused
        self.assertFalse(gate.decide("M5", accepted_by="agent").allowed)
        # only the independent authority may accept M5
        d = gate.decide("M5", accepted_by="work-lab-governance")
        self.assertTrue(d.allowed)


class ExoSandboxTests(unittest.TestCase):
    """WL-360: writes confined to the sandbox; history survives rollback."""

    def _sandbox(self):
        ex = _load("exo_sandbox.py", "evo_ex")
        return ex, ex.ExoSandbox()

    def test_write_inside_sandbox_ok(self):
        ex, sb = self._sandbox()
        sb.write("prompt", "v1", "new prompt text")
        self.assertEqual(sb.read("prompt", "v1"), "new prompt text")
        self.assertEqual(len(sb.history()), 1)

    def test_write_cannot_escape_sandbox(self):
        ex, sb = self._sandbox()
        with self.assertRaises(ex.SandboxEscapeError):
            sb.write("prompt", "../../etc/passwd", "x")
        with self.assertRaises(ex.SandboxEscapeError):
            sb.write("not_a_surface", "k", "v")

    def test_rollback_preserves_canonical_history(self):
        ex, sb = self._sandbox()
        sb.write("memory", "fact", "one")
        sb.snapshot()                      # snap-1
        sb.write("memory", "fact", "two")  # after the snapshot
        self.assertTrue(sb.rollback("snap-1"))
        self.assertEqual(sb.read("memory", "fact"), "one")   # state restored
        self.assertTrue(sb.assert_history_survives_rollback())
        # the canonical history still records every write (key "fact") AND
        # the rollback — rollback must not un-record the earlier writes.
        self.assertTrue(any(e.action == "rollback" for e in sb.history()))
        self.assertTrue(any(e.action == "write" and e.detail == "fact"
                            for e in sb.history()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
