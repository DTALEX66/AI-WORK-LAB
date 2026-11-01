"""CL-05 gate: an external result is a claim, and only WORK-LAB's own re-read can answer it.

CL-04 gave the pack a durable lifecycle; nothing yet let a result from outside come back in. What this file
pins is the part an "import results" feature usually gets wrong:

1. **The document must bind to this handoff.** Wrong pack, wrong project, wrong target version, a result
   produced before the handoff existed, a missing field, and a second submission of the same result id are
   each refused by name and write nothing.
2. **An import is a pending claim.** The external receipt is filled (it is the only writer), the document
   lands as `self`/`none` evidence, the record stays APPROVED, and no outcome is written.
3. **The verdict comes from the store.** The tests below run the real composition root
   (`issue_projection.load_issues`) against a real `CanonicalStore`: a BLOCKED task keeps the repair
   UNRESOLVED, and clearing it makes every source answer so the same pack can resolve.
4. **Four counterexamples never become solved.** Missing evidence, a stale result, a result that arrives
   after the record closed, and a failing repair all end without a SUCCEEDED row -- including the case where
   the store looks fixed but the imported result claimed FAILED (a failure is not rewritten into a success).
5. **UNVERIFIABLE closes nothing.** An absent projection or a truncated read stays pending; "we did not
   read it" is never recorded as "it is fixed".

The four-level evidence scale is the authority's own; a line-shaped guard parses
`completion_authority.EvidenceLevel` instead of importing it (that module drags in the task-protocol loader,
and a guard that crashes is a guard that gets skipped).
"""
from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import issue_projection  # noqa: E402
import project_temp  # noqa: E402
import repair_pack_projection as projection  # noqa: E402
import repair_state  # noqa: E402
import repair_verification as rv  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402

GENERATED_AT = "2026-10-23T00:00:00Z"
_ABSENT = object()
FP_ONE = "1" * 16
FP_TWO = "2" * 16
REGISTRY = {"entries": [
    {"id": "codex", "display_name": "Codex", "support_level": "deep",
     "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"]},
]}


def summary(sources: dict[str, str], *, truncated: bool = False,
            scan_truncated: dict | None = None) -> dict:
    """The real shape `issue_projection` emits: each source is named by `source`, not `name`."""
    return {"sources": [{"source": name, "state": state} for name, state in sorted(sources.items())],
            "truncated": truncated, "scanTruncated": scan_truncated or {}}


def pack(refs: list[str], fingerprints: list[str]) -> dict:
    return {"packId": "rp-work-lab-codex-x", "target": {"projectId": "work-lab"},
            "binds": {"issueFingerprints": fingerprints, "evidenceRefs": refs,
                      "issueCount": len(fingerprints)}}


def issue_row(fingerprint: str = FP_ONE, project: str = "work-lab") -> dict:
    return {
        "schemaVersion": "workflow/issue/v1", "fingerprint": fingerprint, "class": "SOURCE_STALE",
        "projectId": project, "subject": "subject", "origin": "telemetry_events",
        "evidenceRef": f"telemetry_events:{fingerprint}", "priority": "P2",
        "priorityRule": "rule", "safeToReread": True, "firstSeenAt": GENERATED_AT,
        "lastSeenAt": GENERATED_AT, "occurrences": 1, "magnitude": {}, "detail": "d",
        "status": "OPEN", "softwareId": None, "softwareVersion": None,
        "softwareVersionSource": "unattributable",
    }


class OutcomeTests(unittest.TestCase):
    def test_a_condition_still_producing_is_unresolved_even_when_the_receipt_says_it_is_fixed(self) -> None:
        verdict = rv.verify_repair_record(
            pack=pack([f"telemetry_events:{FP_ONE}"], [FP_ONE]),
            issues_now=[{"fingerprint": FP_ONE}], summary_now=summary({"telemetry_events": "read"}),
            absent_reason=None, verified_at=GENERATED_AT,
            receipt={"claimedOutcome": "SUCCEEDED", "producer": "codex"})
        self.assertEqual("UNRESOLVED", verdict["outcome"])
        self.assertEqual([FP_ONE], verdict["fingerprintsPresent"])
        self.assertEqual("independent", verdict["evidenceLevel"],
                         "the re-read is independent whether it agrees with the fixer or not")
        self.assertIs(True, verdict["receiptRecorded"])
        self.assertIs(False, verdict["receiptAcceptedAsVerification"])
        self.assertEqual([], rv.validate_repair_verification(verdict))

    def test_every_fingerprint_gone_with_all_sources_answered_is_resolved(self) -> None:
        verdict = rv.verify_repair_record(
            pack=pack([f"telemetry_events:{FP_ONE}", f"tasks:{FP_TWO}"], [FP_ONE, FP_TWO]),
            issues_now=[], summary_now=summary({"telemetry_events": "read", "tasks": "read"}),
            absent_reason=None, verified_at=GENERATED_AT)
        self.assertEqual("RESOLVED", verdict["outcome"])
        self.assertEqual([FP_ONE, FP_TWO], verdict["fingerprintsAbsent"])
        self.assertEqual(["tasks", "telemetry_events"], verdict["sourcesUnderTest"],
                         "the source names come from the evidence refs, so they can be checked for answering")
        self.assertEqual([], rv.validate_repair_verification(verdict))

    def test_a_source_that_did_not_answer_cannot_be_read_as_a_fix(self) -> None:
        verdict = rv.verify_repair_record(
            pack=pack([f"telemetry_events:{FP_ONE}"], [FP_ONE]),
            issues_now=[], summary_now=summary({"telemetry_events": "absent"}),
            absent_reason="telemetry", verified_at=GENERATED_AT)
        self.assertEqual("UNVERIFIABLE", verdict["outcome"])
        self.assertEqual("none", verdict["evidenceLevel"])
        self.assertEqual(["telemetry_events"], verdict["sourcesUnanswered"])
        self.assertIn("did not answer", verdict["reason"])
        self.assertEqual([], rv.validate_repair_verification(verdict))

    def test_a_truncated_read_cannot_turn_a_missing_fingerprint_into_a_fix(self) -> None:
        verdict = rv.verify_repair_record(
            pack=pack([f"telemetry_events:{FP_ONE}"], [FP_ONE]),
            issues_now=[], summary_now=summary({"telemetry_events": "read"}, truncated=True),
            absent_reason=None, verified_at=GENERATED_AT)
        self.assertEqual("UNVERIFIABLE", verdict["outcome"])
        self.assertIn("truncated", verdict["reason"])

    def test_an_absent_projection_is_unverifiable_and_names_what_was_absent(self) -> None:
        verdict = rv.verify_repair_record(pack=pack([f"tasks:{FP_ONE}"], [FP_ONE]), issues_now=None,
                                          summary_now=None, absent_reason="canonical-store-unreadable",
                                          verified_at=GENERATED_AT)
        self.assertEqual("UNVERIFIABLE", verdict["outcome"])
        self.assertIn("canonical-store-unreadable", verdict["reason"])
        self.assertEqual(1, verdict["boundFingerprintCount"],
                         "the bound count is a fact about the pack, not about this round's read")

    def test_a_pack_that_bound_nothing_cannot_be_verified(self) -> None:
        verdict = rv.verify_repair_record(pack=pack([], []), issues_now=[], summary_now=summary({}),
                                          absent_reason=None, verified_at=GENERATED_AT)
        self.assertEqual("UNVERIFIABLE", verdict["outcome"])
        self.assertIn("no fingerprint", verdict["reason"])

    def test_a_telemetry_evidence_ref_checks_the_telemetry_events_source(self) -> None:
        """Live packs carry `telemetry:<event>` refs while the projection names the source
        `telemetry_events`; reading the ref prefix literally would mark every real pack unanswered."""
        verdict = rv.verify_repair_record(
            pack=pack(["telemetry:task-ledger-6b0ea894031d6adcd30387f86e6ad12a"], [FP_ONE]),
            issues_now=[], summary_now=summary({"telemetry_events": "absent"}),
            absent_reason=None, verified_at=GENERATED_AT)
        self.assertEqual(["telemetry_events"], verdict["sourcesUnderTest"])
        self.assertEqual(["telemetry_events"], verdict["sourcesUnanswered"])
        self.assertEqual("UNVERIFIABLE", verdict["outcome"])


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verdict = rv.verify_repair_record(
            pack=pack([f"telemetry_events:{FP_ONE}"], [FP_ONE]), issues_now=[],
            summary_now=summary({"telemetry_events": "read"}), absent_reason=None,
            verified_at=GENERATED_AT)

    def test_resolved_may_not_carry_a_present_fingerprint(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["fingerprintsPresent"] = [FP_ONE]
        forged["fingerprintsAbsent"] = []
        self.assertTrue(any("still present" in p for p in rv.validate_repair_verification(forged)),
                        "a RESOLVED that admits the fault is still being produced must be rejected")

    def test_resolved_may_not_carry_an_unanswered_source(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["sourcesUnanswered"] = ["telemetry_events"]
        self.assertTrue(any("not reading the fault" in p for p in rv.validate_repair_verification(forged)))

    def test_unverifiable_may_not_borrow_independent_strength(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["outcome"] = "UNVERIFIABLE"
        forged["reason"] = "x"
        self.assertTrue(any("independent" in p for p in rv.validate_repair_verification(forged)))

    def test_unresolved_must_name_what_is_still_there(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["outcome"] = "UNRESOLVED"
        self.assertTrue(any("still there" in p for p in rv.validate_repair_verification(forged)))

    def test_a_receipt_may_not_accept_itself(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["receiptAcceptedAsVerification"] = True
        self.assertTrue(any("own verification" in p for p in rv.validate_repair_verification(forged)))

    def test_denominators_must_add_up(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["fingerprintsAbsent"] = [FP_ONE, FP_TWO]
        self.assertTrue(any("present + absent" in p for p in rv.validate_repair_verification(forged)))

    def test_a_verdict_may_not_smuggle_content(self) -> None:
        forged = copy.deepcopy(self.verdict)
        forged["payload"] = "the log lines"
        self.assertTrue(any("carry 'payload'" in p for p in rv.validate_repair_verification(forged)))


class SharedVocabularyTests(unittest.TestCase):
    def test_evidence_levels_are_the_authoritys_own_values_not_a_paraphrase(self) -> None:
        text = (ROOT / "services/task-governance/completion_authority.py").read_text(encoding="utf-8")
        block = text.split("class EvidenceLevel", 1)[1].split("class ", 1)[0]
        theirs = sorted(re.findall(r'=\s*"([a-z]+)"', block))
        self.assertEqual(theirs, sorted(rv.EVIDENCE_LEVELS),
                         "this slice may not mint a fifth evidence scale; align it with "
                         "services/task-governance/completion_authority.py or move the verdict there")

    def test_the_lifecycle_and_the_verdict_share_one_evidence_scale(self) -> None:
        self.assertEqual(list(repair_state.EVIDENCE_LEVELS), list(rv.EVIDENCE_LEVELS))


class LifecycleCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("repair-verification-")
        self.runtime = Path(self.fixture)
        self.project = self.runtime / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        gate = self.project / projection.OWN_GATE_RELATIVE_PATH
        gate.parent.mkdir(parents=True, exist_ok=True)
        gate.write_text("# gate fixture\n", encoding="utf-8")
        self.store = CanonicalStore(self.runtime / "canonical.sqlite")
        self.pack = self.make_pack([issue_row()])

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def make_pack(self, issues: list[dict]) -> dict:
        projects = [{"project_id": "work-lab", "root_path": self.project.as_posix(),
                     "display_name": "work-lab", "status": "REGISTERED"}]
        out = projection.project_repair_packs(issues=issues, projects=projects, registry=REGISTRY,
                                              adapters=["codex"], generated_at=GENERATED_AT)
        self.assertTrue(out["packs"], out["summary"])
        return out["packs"][0]

    def approved(self) -> dict:
        recorded = repair_state.record_pack(self.store, self.pack)
        return repair_state.approve_pack(
            self.store, self.pack["packId"], authorization_ref="grant-1",
            grants={"grant-1": f"work-unit:{self.pack['packId']}"},
            expected_version=recorded["version"], approved_at="2026-10-23T00:30:00Z")

    def declared(self, *, target_version: str | None = "1.4.0") -> dict:
        approved = self.approved()
        return repair_state.declare_handoff(
            self.store, self.pack["packId"], claim="userDeclaredHandoff",
            declared_at="2026-10-23T01:00:00Z", channel="manual-file",
            claimed_recipient="codex", target_version=target_version,
            expected_version=approved["version"])

    def result(self, **overrides) -> dict:
        document = {
            "schemaVersion": rv.EXTERNAL_RESULT_SCHEMA_VERSION,
            "resultId": "res-1",
            "packId": self.pack["packId"],
            "projectId": "work-lab",
            "targetVersion": "1.4.0",
            "producedAt": "2026-10-23T02:00:00Z",
            "producer": "codex",
            "claimedOutcome": "SUCCEEDED",
            "evidenceRefs": ["codex-run:abc"],
            "detail": "patched the writer",
        }
        document.update(overrides)
        return document

    def imported(self, **overrides) -> dict:
        declared = self.declared()
        return repair_state.import_external_result(
            self.store, self.pack["packId"], self.result(**overrides),
            accepted_at="2026-10-23T03:00:00Z", expected_version=declared["version"])

    def verdict(self, *, issues_now=_ABSENT, summary_now=_ABSENT, absent_reason=None,
                verified_at: str = "2026-10-23T04:00:00Z") -> dict:
        return rv.verify_repair_record(
            pack=self.pack,
            issues_now=[] if issues_now is _ABSENT else issues_now,
            summary_now=(summary({"telemetry_events": "read"}) if summary_now is _ABSENT
                         else summary_now),
            absent_reason=absent_reason, verified_at=verified_at)


class BindingTests(LifecycleCase):
    def test_a_result_must_name_the_handoff_it_answers(self) -> None:
        approved = self.approved()
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_HANDOFF_MISSING"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], self.result(),
                expected_version=approved["version"])

    def test_a_handoff_without_a_target_version_cannot_bind_a_result(self) -> None:
        declared = self.declared(target_version=None)
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_HANDOFF_UNBOUND"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], self.result(),
                expected_version=declared["version"])

    def test_wrong_pack_wrong_project_and_wrong_version_are_each_named(self) -> None:
        declared = self.declared()
        cases = (("packId", "rp-work-lab-codex-other", "EXTERNAL_RESULT_WRONG_PACK"),
                 ("projectId", "another-project", "EXTERNAL_RESULT_WRONG_PROJECT"),
                 ("targetVersion", "9.9.9", "EXTERNAL_RESULT_WRONG_VERSION"))
        for field, value, code in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, code):
                    repair_state.import_external_result(
                        self.store, self.pack["packId"], self.result(**{field: value}),
                        expected_version=declared["version"])
        self.assertIsNone(repair_state.read_record(self.store, self.pack["packId"])["payload"]["outcome"])

    def test_a_result_produced_before_the_handoff_is_stale(self) -> None:
        declared = self.declared()
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_STALE"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], self.result(producedAt="2026-10-23T00:30:00Z"),
                expected_version=declared["version"])

    def test_a_missing_field_is_named_not_defaulted(self) -> None:
        declared = self.declared()
        document = self.result()
        document.pop("resultId")
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_INCOMPLETE resultId"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], document, expected_version=declared["version"])

    def test_the_same_result_cannot_be_submitted_twice(self) -> None:
        imported = self.imported()
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_DUPLICATE"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], self.result(), expected_version=imported["version"])

    def test_an_import_is_a_pending_claim_and_does_not_change_the_status(self) -> None:
        imported = self.imported()
        self.assertEqual("APPROVED", imported["status"])
        payload = imported["payload"]
        self.assertIsNone(payload["outcome"])
        receipt = payload["handoffRecord"]["externalReceipt"]
        self.assertEqual({"received": True, "receivedAt": "2026-10-23T03:00:00Z",
                          "externalId": "res-1", "source": "codex"}, receipt)
        self.assertEqual("res-1", payload["pendingVerification"]["resultId"])
        self.assertEqual("self", payload["externalResults"][0]["evidenceLevel"],
                         "a document's own references make it a self-report, never independent evidence")

    def test_a_result_without_evidence_is_still_only_a_claim(self) -> None:
        imported = self.imported(evidenceRefs=[])
        self.assertEqual("APPROVED", imported["status"])
        self.assertEqual("none", imported["payload"]["externalResults"][0]["evidenceLevel"])

    def test_a_late_result_cannot_reopen_a_closed_record(self) -> None:
        declared = self.declared()
        closed = repair_state.record_outcome(
            self.store, self.pack["packId"], outcome="FAILED", evidence_level="self",
            evidence_refs=["user-note:gave-up"], expected_version=declared["version"],
            recorded_at="2026-10-23T02:30:00Z")
        with self.assertRaisesRegex(ValueError, "EXTERNAL_RESULT_RECORD_CLOSED"):
            repair_state.import_external_result(
                self.store, self.pack["packId"], self.result(), expected_version=closed["version"])


class RecordVerificationTests(LifecycleCase):
    def test_a_verified_success_closes_at_independent_strength(self) -> None:
        imported = self.imported()
        row = repair_state.record_verification(self.store, self.pack["packId"], self.verdict(),
                                               expected_version=imported["version"])
        self.assertEqual("SUCCEEDED", row["status"])
        payload = row["payload"]
        self.assertEqual("independent", payload["outcome"]["evidenceLevel"])
        self.assertEqual([f"action_plan:{self.pack['packId']}#verification:v1"],
                         payload["outcome"]["evidenceRefs"])
        self.assertIsNone(payload["pendingVerification"])
        self.assertEqual("RESOLVED", payload["externalResults"][0]["verification"]["outcome"])
        self.assertEqual("VERIFICATION_RECORDED", payload["history"][-1]["event"])

    def test_a_fault_still_being_produced_closes_as_failed_never_solved(self) -> None:
        imported = self.imported()
        row = repair_state.record_verification(
            self.store, self.pack["packId"],
            self.verdict(issues_now=[{"fingerprint": FP_ONE}]),
            expected_version=imported["version"])
        self.assertEqual("FAILED", row["status"])
        self.assertEqual([FP_ONE], row["payload"]["verifications"][-1]["fingerprintsPresent"])

    def test_a_failed_claim_is_not_rewritten_into_a_success(self) -> None:
        imported = self.imported(claimedOutcome="FAILED")
        row = repair_state.record_verification(self.store, self.pack["packId"], self.verdict(),
                                               expected_version=imported["version"])
        self.assertEqual("FAILED", row["status"],
                         "the store says the fault is gone, but the imported result says the repair failed; "
                         "a failure is not promoted to success by absence alone")

    def test_an_unverifiable_verdict_closes_nothing_and_stays_pending(self) -> None:
        imported = self.imported()
        row = repair_state.record_verification(
            self.store, self.pack["packId"], self.verdict(issues_now=None, summary_now=None,
                                                          absent_reason=None),
            expected_version=imported["version"])
        self.assertEqual("APPROVED", row["status"])
        self.assertIsNone(row["payload"]["outcome"])
        self.assertEqual("res-1", row["payload"]["pendingVerification"]["resultId"])
        self.assertEqual("UNVERIFIABLE", row["payload"]["verifications"][-1]["outcome"])

    def test_a_verdict_for_another_pack_is_refused(self) -> None:
        imported = self.imported()
        forged = copy.deepcopy(self.verdict())
        forged["packId"] = "rp-work-lab-codex-other"
        with self.assertRaisesRegex(ValueError, "REPAIR_VERIFICATION_WRONG_PACK"):
            repair_state.record_verification(self.store, self.pack["packId"], forged,
                                             expected_version=imported["version"])

    def test_no_imported_result_means_there_is_no_claim_to_answer(self) -> None:
        approved = self.approved()
        with self.assertRaisesRegex(ValueError, "REPAIR_VERIFICATION_NOT_PENDING"):
            repair_state.record_verification(self.store, self.pack["packId"], self.verdict(),
                                             expected_version=approved["version"])

    def test_replaying_the_same_verdict_after_close_is_a_no_op(self) -> None:
        imported = self.imported()
        closed = repair_state.record_verification(self.store, self.pack["packId"], self.verdict(),
                                                  expected_version=imported["version"])
        replay = repair_state.record_verification(self.store, self.pack["packId"], self.verdict(),
                                                  expected_version=closed["version"])
        self.assertFalse(replay["changed"])
        self.assertEqual(closed["version"], replay["version"])


class StoreReReadTests(LifecycleCase):
    """The verdict path itself, reading a real store through `issue_projection.load_issues`."""

    def start(self) -> dict:
        self.store.upsert_task({"task_id": "WL-CL05-1", "project_id": "work-lab", "status": "BLOCKED",
                                "created_at": GENERATED_AT, "updated_at": GENERATED_AT})
        issues, summary_now, absent = issue_projection.load_issues(self.store)
        self.assertIsNone(absent)
        self.assertTrue(issues)
        self.pack = self.make_pack(issues)
        return self.imported()

    def test_a_blocked_task_keeps_the_repair_unresolved(self) -> None:
        imported = self.start()
        row = repair_state.verify_record(self.store, self.pack["packId"],
                                         verified_at="2026-10-23T04:00:00Z",
                                         expected_version=imported["version"])
        self.assertEqual("FAILED", row["status"])
        verdict = row["payload"]["verifications"][-1]
        self.assertEqual("UNRESOLVED", verdict["outcome"])
        self.assertIn("tasks", verdict["sourcesUnderTest"])
        self.assertEqual([], verdict["sourcesUnanswered"])

    def test_clearing_the_task_leaves_the_sources_answering_and_resolves(self) -> None:
        imported = self.start()
        self.store.upsert_task({"task_id": "WL-CL05-1", "project_id": "work-lab", "status": "RUNNING",
                                "created_at": GENERATED_AT, "updated_at": "2026-10-23T03:30:00Z"})
        row = repair_state.verify_record(self.store, self.pack["packId"],
                                         verified_at="2026-10-23T04:00:00Z",
                                         expected_version=imported["version"])
        self.assertEqual("SUCCEEDED", row["status"])
        verdict = row["payload"]["verifications"][-1]
        self.assertEqual("RESOLVED", verdict["outcome"])
        self.assertEqual("independent", verdict["evidenceLevel"])
        self.assertEqual([], verdict["sourcesUnanswered"])


if __name__ == "__main__":
    unittest.main()
