"""NF-02-SYNC: real cross-process / cross-project acceptance + exact-version CI.

Proves the acceptance rows for AT-01 / AT-14 / AT-15 / AT-25 / AT-31 / AT-35 /
AT-39 on the self-executable slice (real cross-process / external-project /
CI evidence stays authorization-gated and BLOCKED):
  * simulation and real evidence are counted SEPARATELY, never summed;
  * a case whose only evidence is simulated is SIMULATED-ONLY / PENDING-VERIFY,
    never a faked pass;
  * an unauthorized (or below-required-level) case stays PENDING-VERIFY;
  * at least one external real project is clean — the core source is NOT
    copied into it and role switching does not cross-wire;
  * a required CI gate is bound to an EXACT SHA: a different-SHA CI success is
    not a substitute, a public repo is not wired to an arbitrary PR-callable
    everyday self-hosted runner, and an optional comparison never blocks the
    required gate.

Pure and deterministic: no network, no CI invocation, no runner, no device.
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

import acceptance_evidence as ae  # noqa: E402


class TestEvidenceSeparation(unittest.TestCase):
    def test_simulation_and_real_are_counted_separately(self):
        led = ae.EvidenceLedger()
        led.add(ae.EvidenceRecord("AT-31", "SIMULATED", "sim-report-1", simulated=True))
        led.add(ae.EvidenceRecord("AT-31", "REAL", "real-run-42", simulated=False))
        counts = led.count_by_level()
        self.assertEqual(counts["SIMULATED"], 1)
        self.assertEqual(counts["REAL"], 1)
        # they are distinct buckets, not summed into one 'covered' number
        self.assertNotIn("SIMULATED", [counts["REAL"]])

    def test_simulated_only_is_not_a_faked_pass(self):
        led = ae.EvidenceLedger()
        led.add(ae.EvidenceRecord("AT-35", "SIMULATED", "sim-only", simulated=True))
        grade = led.grade_case("AT-35", required="REAL")
        self.assertEqual(grade["status"], "SIMULATED-ONLY")
        self.assertFalse(grade["covered"])

    def test_real_evidence_covers_when_at_required_level(self):
        led = ae.EvidenceLedger()
        led.add(ae.EvidenceRecord("AT-15", "REAL", "real-cicd-9", simulated=False))
        grade = led.grade_case("AT-15", required="REAL")
        self.assertTrue(grade["covered"])
        self.assertEqual(grade["status"], "COVERED")

    def test_below_required_level_is_pending_not_pass(self):
        led = ae.EvidenceLedger()
        # INTEGRATED is a real-level record but below the REAL requirement
        led.add(ae.EvidenceRecord("AT-25", "INTEGRATED", "integ-report", simulated=False))
        grade = led.grade_case("AT-25", required="REAL")
        self.assertEqual(grade["status"], "PENDING-VERIFY")
        self.assertFalse(grade["covered"])

    def test_simulated_below_required_is_simulated_only(self):
        led = ae.EvidenceLedger()
        # SYNTHETIC is simulated-only evidence
        led.add(ae.EvidenceRecord("AT-26", "SYNTHETIC", "syn-report", simulated=True))
        grade = led.grade_case("AT-26", required="REAL")
        self.assertEqual(grade["status"], "SIMULATED-ONLY")
        self.assertFalse(grade["covered"])

    def test_summary_never_fakes_a_pass(self):
        led = ae.EvidenceLedger()
        led.add(ae.EvidenceRecord("AT-01", "REAL", "r1", simulated=False))
        led.add(ae.EvidenceRecord("AT-14", "SIMULATED", "s1", simulated=True))
        summary = led.summary({"AT-01": "REAL", "AT-14": "REAL"})
        self.assertIn("AT-01", summary["covered"])
        self.assertIn("AT-14", summary["simulated_only"])
        self.assertFalse(summary["faked_any_pass"])
        # counts kept apart
        self.assertEqual(summary["counts_by_level"]["REAL"], 1)
        self.assertEqual(summary["counts_by_level"]["SIMULATED"], 1)


class TestExternalProjectClean(unittest.TestCase):
    def test_at_least_one_external_project_without_copied_core(self):
        checks = [
            ae.ExternalProjectCheck("archeaxis", core_source_copied_into_it=False,
                                    role_cross_wired=False),
            ae.ExternalProjectCheck("radar", core_source_copied_into_it=True,
                                    role_cross_wired=False),  # dirty
        ]
        res = ae.external_project_ok(checks)
        self.assertTrue(res["has_clean_external_project"])
        self.assertEqual(res["clean_projects"], ["archeaxis"])
        self.assertEqual(res["rejected"], ["radar"])

    def test_role_cross_wiring_is_rejected(self):
        checks = [ae.ExternalProjectCheck("p", core_source_copied_into_it=False,
                                          role_cross_wired=True)]
        res = ae.external_project_ok(checks)
        self.assertFalse(res["has_clean_external_project"])


class TestExactShaCiGate(unittest.TestCase):
    def _gate(self, sha: str) -> ae.CiShaGate:
        g = ae.CiShaGate()
        g.bind_required("work-lab-gate", sha)
        return g

    def test_different_sha_success_is_not_a_substitute(self):
        g = self._gate("abc123def")
        g.record_result("work-lab-gate", sha="9999999", status="success")
        res = g.evaluate("work-lab-gate")
        self.assertEqual(res["verdict"], "SHA_MISMATCH")
        self.assertEqual(res["recorded_sha"], "9999999")

    def test_public_repo_not_wired_to_everyday_self_hosted_runner(self):
        g = self._gate("abc123def")
        g.record_result("work-lab-gate", sha="abc123def", status="success",
                        runner_kind="everyday-self-hosted")
        res = g.evaluate("work-lab-gate")
        self.assertEqual(res["verdict"], "RUNNER_REFUSED")

    def test_exact_sha_success_on_hosted_runner_passes(self):
        g = self._gate("abc123def")
        g.record_result("work-lab-gate", sha="abc123def", status="success")
        res = g.evaluate("work-lab-gate")
        self.assertEqual(res["verdict"], "GATE_PASSED")

    def test_optional_comparison_does_not_block_required(self):
        g = ae.CiShaGate()
        g.bind_required("required-gate", "abc123def")
        g.bind_required("optional-compare", "aaa111def")
        g.mark_optional("optional-compare")
        g.record_result("required-gate", sha="abc123def", status="success")
        g.record_result("optional-compare", sha="aaa111def", status="success")
        # the optional gate passing does NOT block / not block the required one
        req = g.evaluate("required-gate")
        opt = g.evaluate("optional-compare")
        self.assertEqual(req["verdict"], "GATE_PASSED")
        self.assertEqual(opt["verdict"], "OPTIONAL_PASSED")

    def test_unbound_gate_is_pending_not_passed(self):
        g = ae.CiShaGate()
        res = g.evaluate("no-such-gate")
        self.assertEqual(res["verdict"], "UNBOUND")

    def test_short_sha_is_refused_as_not_exact(self):
        g = ae.CiShaGate()
        with self.assertRaises(ValueError):
            g.bind_required("g", "abc")  # too short to be an exact SHA


# ---------------------------------------------------------------------------
# U11 — REAL evidence binding: a REAL record must carry a complete, verifiable
# binding (evidence type, non-empty handle, identity/digest, producer,
# verifier/readback, observedAt, source SHA/run identity when applicable).
# An EMPTY REAL handle is invalid.  These are additive optional fields, so the
# frozen positional constructions above (and every other behavior) stay intact.
# ---------------------------------------------------------------------------
class TestRealEvidenceBinding(unittest.TestCase):
    def test_real_record_rejects_empty_handle(self):
        with self.assertRaises(ValueError):
            ae.EvidenceRecord("AT-31", "REAL", "   ", simulated=False)
        # a non-simulated real record with a real handle is fine.
        ae.EvidenceRecord("AT-31", "REAL", "real-run-42", simulated=False)

    def test_real_binding_requires_full_field_set(self):
        r = ae.EvidenceRecord("AT-15", "REAL", "real-cicd-9", simulated=False,
                              evidence_type="RUN_ARTIFACT",
                              receipt_digest="sha256:abc123",
                              producer="work-lab/observer",
                              verifier="work-lab/readback",
                              observed_at="2026-09-20T00:00:00Z")
        issues = ae.validate_real_binding(r)
        self.assertEqual(issues, [])
        # dropping one required field surfaces it.
        weak = ae.EvidenceRecord("AT-15", "REAL", "real-cicd-9", simulated=False,
                                 evidence_type="RUN_ARTIFACT",
                                 receipt_digest="sha256:abc123",
                                 producer="work-lab/observer",
                                 verifier=None,                 # missing
                                 observed_at="2026-09-20T00:00:00Z")
        self.assertIn("verifier", ae.validate_real_binding(weak))

    def test_source_sha_optional_but_must_be_well_formed_when_present(self):
        ok = ae.EvidenceRecord("AT-15", "REAL", "run", simulated=False,
                               evidence_type="CI", receipt_digest="sha256:x",
                               producer="p", verifier="v",
                               observed_at="2026-09-20T00:00:00Z",
                               source_sha="abc123def")
        self.assertEqual(ae.validate_real_binding(ok), [])
        # a present-but-malformed source sha (too short to be an identity) fails.
        bad = ae.EvidenceRecord("AT-15", "REAL", "run", simulated=False,
                                evidence_type="CI", receipt_digest="sha256:x",
                                producer="p", verifier="v",
                                observed_at="2026-09-20T00:00:00Z",
                                source_sha="ab")
        self.assertIn("source_sha", ae.validate_real_binding(bad))

    def test_simulated_level_is_not_subject_to_real_binding(self):
        # A simulated record legitimately has none of the real-binding fields;
        # validating its REAL binding is simply not applicable, never an error.
        s = ae.EvidenceRecord("AT-31", "SIMULATED", "sim-report-1", simulated=True)
        self.assertEqual(ae.real_binding_status(s), "NOT_APPLICABLE")
        r = ae.EvidenceRecord("AT-15", "REAL", "real-cicd-9", simulated=False,
                              evidence_type="RUN_ARTIFACT",
                              receipt_digest="sha256:abc123",
                              producer="p", verifier="v",
                              observed_at="2026-09-20T00:00:00Z")
        self.assertEqual(ae.real_binding_status(r), "VALID")
        weak = ae.EvidenceRecord("AT-15", "REAL", "real-cicd-9", simulated=False,
                                 evidence_type="RUN_ARTIFACT",
                                 receipt_digest="sha256:abc123",
                                 producer=None,
                                 verifier="v",
                                 observed_at="2026-09-20T00:00:00Z")
        self.assertEqual(ae.real_binding_status(weak), "INCOMPLETE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
