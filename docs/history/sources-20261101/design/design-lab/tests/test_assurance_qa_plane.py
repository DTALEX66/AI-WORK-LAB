# SPDX-License-Identifier: MIT
"""DLDS-F070 QA policy: plane inventory, per-plane outcome vocabulary and the aggregate gate.

Every guarantee this module had before the policy was frozen is re-proved here
under the frozen vocabulary (PASS / WARN / REVIEW_REQUIRED / HARD_BLOCK for the
automated planes, APPROVE / REJECT for the human jury), plus the new refusals:
an automated plane may not produce a final REJECT, may not reach an outcome its
plane does not allow, and a human finding without a signed verdict is refused.

Tests that changed name with the vocabulary, and what they still prove:

* ``test_pass_and_fail_need_a_nonzero_artifact_digest`` ->
  :meth:`QaFindingTests.test_every_outcome_needs_a_nonzero_artifact_digest`
  (now every admitted outcome, not only PASS/FAIL);
* ``test_human_verdict_must_settle_a_result`` ->
  :meth:`QaFindingTests.test_a_human_decision_needs_its_signed_verdict`;
* ``test_a_human_pass_without_a_verdict_is_not_a_verdict`` ->
  :meth:`QaFindingTests.test_a_human_decision_needs_its_signed_verdict` and
  :meth:`QaAggregateTests.test_automated_findings_alone_never_reach_pass` (an
  unsigned human outcome is now refused outright, and PASS still needs a
  verdict);
* ``test_blocker_outranks_a_human_accept`` ->
  :meth:`QaAggregateTests.test_blocker_outranks_a_human_approve`;
* ``test_a_blocker_that_did_not_run_still_blocks`` (the INCONCLUSIVE/NOT_RUN
  outcomes no longer exist) ->
  :meth:`QaAggregateTests.test_a_hard_block_outranks_a_later_human_approve`.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jsonschema  # noqa: E402

from design_lab.assurance import AssuranceError  # noqa: E402
from design_lab.assurance import qa_plane  # noqa: E402

SHA = "sha256:" + "a" * 64
SHA_OTHER = "sha256:" + "b" * 64
SUBJECT = "design-lab/job/job-1/deliverable/poster"


def finding(**overrides):
    base = {
        "finding_id": "f-1",
        "layer_id": "qa-deterministic",
        "check_id": "check_anti_slop",
        "subject_ref": SUBJECT,
        "outcome": "PASS",
        "severity": "MAJOR",
        "evidence": {"artifact_sha256": SHA},
    }
    base.update(overrides)
    return qa_plane.QaFinding(**base)


def model_finding(**overrides):
    base = {
        "finding_id": "m-1",
        "layer_id": "qa-model-assisted",
        "check_id": "provider:aesthetic/laion",
        "subject_ref": SUBJECT,
        "outcome": "PASS",
        "severity": "MINOR",
        "evidence": {"artifact_sha256": SHA, "evidence_level": "E2"},
        "recommendation": "score 4.1 of 5; worth a human look at the material axis",
    }
    base.update(overrides)
    return qa_plane.QaFinding(**base)


def human_finding(**overrides):
    base = {
        "finding_id": "h-1",
        "layer_id": "qa-human",
        "check_id": "professional-jury/DL-QLT-002",
        "subject_ref": SUBJECT,
        "outcome": "APPROVE",
        "severity": "MAJOR",
        "evidence": {"artifact_sha256": SHA, "evidence_level": "E4"},
        "verdict": "APPROVE",
    }
    base.update(overrides)
    return qa_plane.QaFinding(**base)


def layer_document(findings):
    return {
        "schemaVersion": "design-lab/assurance-qa-layer/v1",
        "planes": [layer.as_dict() for layer in qa_plane.QA_PLANES],
        "findings": [item.as_dict() for item in findings],
    }


class FrozenPolicyTests(unittest.TestCase):
    """The module vocabulary must be exactly the frozen DLDS-F070 policy."""

    def test_policy_rows_are_the_frozen_four(self):
        table = qa_plane.check_policy()
        self.assertEqual(
            ["DETERMINISTIC_QA", "RIGHTS_SECURITY", "MODEL_ASSISTED_QA", "HUMAN_JURY"],
            [row["policy_row"] for row in table["rows"]],
        )
        by_row = {row["policy_row"]: row for row in table["rows"]}
        self.assertEqual(["PASS", "WARN", "HARD_BLOCK"],
                         by_row["DETERMINISTIC_QA"]["allowed_outcomes"])
        self.assertEqual(["HARD_BLOCK"], by_row["RIGHTS_SECURITY"]["allowed_outcomes"])
        self.assertEqual(["PASS", "WARN", "REVIEW_REQUIRED"],
                         by_row["MODEL_ASSISTED_QA"]["allowed_outcomes"])
        self.assertEqual(["APPROVE", "REJECT"], by_row["HUMAN_JURY"]["allowed_outcomes"])
        self.assertTrue(by_row["DETERMINISTIC_QA"]["may_block"])
        self.assertTrue(by_row["RIGHTS_SECURITY"]["may_block"])
        self.assertFalse(by_row["MODEL_ASSISTED_QA"]["may_block"])
        self.assertFalse(by_row["MODEL_ASSISTED_QA"]["may_be_final"])
        self.assertTrue(by_row["HUMAN_JURY"]["may_be_final"])
        # The rights/security row is a check family inside the deterministic plane.
        self.assertEqual("qa-deterministic", by_row["RIGHTS_SECURITY"]["plane_id"])

    def test_the_vocabulary_is_exactly_the_policy(self):
        self.assertEqual(
            ("PASS", "WARN", "REVIEW_REQUIRED", "HARD_BLOCK",
             "APPROVE", "REJECT"),
            qa_plane.OUTCOMES,
        )
        self.assertEqual(("PASS", "WARN", "REVIEW_REQUIRED", "HARD_BLOCK"),
                         qa_plane.AUTOMATED_OUTCOMES)
        self.assertEqual(("APPROVE", "REJECT"), qa_plane.HUMAN_OUTCOMES)
        self.assertEqual(("APPROVE", "REJECT"), qa_plane.FINAL_OUTCOMES)
        self.assertEqual(
            {"DETERMINISTIC": ("PASS", "WARN", "HARD_BLOCK"),
             "MODEL_ASSISTED": ("PASS", "WARN", "REVIEW_REQUIRED"),
             "HUMAN": ("APPROVE", "REJECT")},
            qa_plane.OUTCOMES_BY_KIND,
        )
        # The retired vocabulary is gone, not merely deprecated.
        for retired in ("FAIL", "INCONCLUSIVE", "NOT_RUN", "ACCEPT", "REVISE"):
            self.assertNotIn(retired, qa_plane.OUTCOMES, retired)

    def test_policy_outcomes_resolve_per_plane(self):
        self.assertEqual(("PASS", "WARN", "HARD_BLOCK"),
                         qa_plane.policy_outcomes("DETERMINISTIC"))
        self.assertEqual(("PASS", "WARN", "REVIEW_REQUIRED"),
                         qa_plane.policy_outcomes("MODEL_ASSISTED"))
        self.assertEqual(("APPROVE", "REJECT"), qa_plane.policy_outcomes("HUMAN"))
        with self.assertRaises(AssuranceError):
            qa_plane.policy_outcomes("SEMI_AUTOMATIC")

    def test_a_policy_that_lets_automation_be_final_is_refused(self):
        escape = qa_plane.POLICY_ROWS[:3] + (
            {**qa_plane.POLICY_ROWS[3], "may_be_final": False},
        )
        original = qa_plane.POLICY_ROWS
        qa_plane.POLICY_ROWS = escape
        try:
            with self.assertRaises(AssuranceError) as caught:
                qa_plane.check_policy()
            self.assertIn("may_be_final", str(caught.exception))
        finally:
            qa_plane.POLICY_ROWS = original

        automation_rejects = (
            {**qa_plane.POLICY_ROWS[2], "allowed_outcomes": ("PASS", "REJECT")},
        ) + qa_plane.POLICY_ROWS[3:]
        qa_plane.POLICY_ROWS = automation_rejects
        try:
            with self.assertRaises(AssuranceError) as caught:
                qa_plane.check_policy()
            self.assertIn("final rejection belongs to the HUMAN jury", str(caught.exception))
        finally:
            qa_plane.POLICY_ROWS = original


class QaPlaneInventoryTests(unittest.TestCase):
    def test_planes_cover_the_existing_quality_pipeline_exactly(self):
        declared = qa_plane.pipeline_layer_ids()
        self.assertEqual(
            ("deterministic", "visual-model", "expert-agent", "human-feedback"), declared
        )
        self.assertEqual(tuple(sorted(declared)), qa_plane.check_plane_inventory())

    def test_each_pipeline_layer_is_mapped_onto_exactly_one_plane(self):
        mapped = {}
        for layer in qa_plane.QA_PLANES:
            for name in layer.pipeline_layers:
                self.assertNotIn(name, mapped)
                mapped[name] = layer.layer_id
        self.assertEqual(mapped["deterministic"], "qa-deterministic")
        self.assertEqual(mapped["visual-model"], "qa-model-assisted")
        self.assertEqual(mapped["expert-agent"], "qa-model-assisted")
        self.assertEqual(mapped["human-feedback"], "qa-human")

    def test_plane_kinds_and_evidence_ceilings(self):
        ceilings = {layer.kind: layer.evidence_ceiling for layer in qa_plane.QA_PLANES}
        self.assertEqual(("E1", "E2"), ceilings["DETERMINISTIC"])
        self.assertEqual(("E2", "E3"), ceilings["MODEL_ASSISTED"])
        self.assertEqual(("E4",), ceilings["HUMAN"])
        self.assertFalse(qa_plane.plane_for("qa-model-assisted").can_block)
        self.assertTrue(qa_plane.plane_for("qa-deterministic").can_block)
        self.assertTrue(qa_plane.plane_for("qa-human").can_block)
        # The ceiling is the policy's blocking authority, stated per plane.
        deterministic = qa_plane.plane_for("qa-deterministic")
        model_assisted = qa_plane.plane_for("qa-model-assisted")
        human = qa_plane.plane_for("qa-human")
        self.assertIn("HARD_BLOCK", qa_plane.policy_outcomes(deterministic.kind))
        self.assertNotIn("HARD_BLOCK", qa_plane.policy_outcomes(model_assisted.kind))
        self.assertFalse(model_assisted.can_block)
        self.assertTrue(qa_plane.check_policy()["rows"][3]["may_block"])
        self.assertNotIn("APPROVE", qa_plane.policy_outcomes(deterministic.kind))
        self.assertNotIn("APPROVE", qa_plane.policy_outcomes(model_assisted.kind))
        self.assertEqual(("APPROVE", "REJECT"), qa_plane.policy_outcomes(human.kind))

    def test_unclaimed_pipeline_layer_is_refused(self):
        without_human = tuple(
            layer for layer in qa_plane.QA_PLANES if layer.layer_id != "qa-human"
        )
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.check_plane_inventory(planes=without_human)
        self.assertIn("human-feedback", str(caught.exception))

    def test_double_claim_is_refused(self):
        split = qa_plane.QA_PLANES + (
            qa_plane.QaLayer(
                layer_id="qa-extra",
                kind="MODEL_ASSISTED",
                evidence_ceiling=("E2", "E3"),
                owner="x",
                description="y",
                can_block=False,
                pipeline_layers=("visual-model",),
            ),
        )
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.check_plane_inventory(planes=split)
        self.assertIn("claimed by both", str(caught.exception))

    def test_unknown_pipeline_layer_is_refused(self):
        broken = tuple(
            qa_plane.QaLayer(**{**layer.__dict__, "pipeline_layers": ("no-such-layer",)})
            if layer.layer_id == "qa-human" else layer
            for layer in qa_plane.QA_PLANES
        )
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.check_plane_inventory(planes=broken)
        self.assertIn("unknown pipeline layer", str(caught.exception))

    def test_model_plane_may_not_block(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_layer(qa_plane.QaLayer(
                layer_id="qa-model-assisted",
                kind="MODEL_ASSISTED",
                evidence_ceiling=("E2", "E3"),
                owner="x",
                description="y",
                can_block=True,
                pipeline_layers=("visual-model",),
            ))
        self.assertIn("may not block", str(caught.exception))

    def test_plane_document_matches_the_schema(self):
        document = qa_plane.qa_layer_document()
        jsonschema.validate(instance=document, schema=qa_plane.qa_schema())
        self.assertEqual(3, len(document["planes"]))

        # The ceiling is a schema-level guarantee too, not only a module rule.
        validator = jsonschema.Draft202012Validator(qa_plane.qa_schema())
        escalated = json.loads(json.dumps(document))
        escalated["planes"][1]["can_block"] = True
        self.assertTrue(list(validator.iter_errors(escalated)))
        escalated_ceiling = json.loads(json.dumps(document))
        escalated_ceiling["planes"][1]["evidence_ceiling"] = ["E2", "E3", "E4"]
        self.assertTrue(list(validator.iter_errors(escalated_ceiling)))


class QaOutcomeVocabularyTests(unittest.TestCase):
    """Each plane may produce its own outcomes and no others."""

    def test_a_deterministic_finding_may_not_be_final(self):
        for outcome in ("REJECT", "REJECTED", "APPROVE"):
            with self.subTest(outcome=outcome):
                with self.assertRaises(AssuranceError) as caught:
                    qa_plane.validate_finding(finding(outcome=outcome))
                message = str(caught.exception)
                self.assertIn("frozen QA policy", message)
                self.assertIn("HUMAN jury", message)
        # PASS, WARN and HARD_BLOCK are the deterministic outcomes.
        for outcome in ("PASS", "WARN", "HARD_BLOCK"):
            self.assertIsNotNone(qa_plane.validate_finding(finding(outcome=outcome)))
        # REVIEW_REQUIRED is the model plane's escalation, not a deterministic one.
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(finding(outcome="REVIEW_REQUIRED"))
        self.assertIn("may not produce", str(caught.exception))
        self.assertIn("PASS/WARN/HARD_BLOCK", str(caught.exception))

    def test_a_model_assisted_finding_escalates_instead_of_rejecting(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(model_finding(outcome="REJECT"))
        message = str(caught.exception)
        self.assertIn("REJECT", message)
        self.assertIn("HUMAN jury", message)
        self.assertIn("REVIEW_REQUIRED", message)
        with self.assertRaises(AssuranceError) as rejected_spelling:
            qa_plane.validate_finding(model_finding(outcome="REJECTED"))
        self.assertIn("frozen QA policy", str(rejected_spelling.exception))
        # The escalation is representable, and it is not a rejection.
        escalated = qa_plane.validate_finding(model_finding(outcome="REVIEW_REQUIRED"))
        self.assertEqual("REVIEW_REQUIRED", escalated.outcome)
        self.assertNotIn(escalated.outcome, qa_plane.FINAL_OUTCOMES)
        for outcome in ("HARD_BLOCK", "APPROVE"):
            with self.subTest(outcome=outcome):
                with self.assertRaises(AssuranceError):
                    qa_plane.validate_finding(model_finding(outcome=outcome))

    def test_no_automated_plane_reaches_the_human_vocabulary(self):
        for outcome in qa_plane.HUMAN_OUTCOMES:
            with self.subTest(outcome=outcome):
                with self.assertRaises(AssuranceError):
                    qa_plane.validate_finding(finding(outcome=outcome))
                with self.assertRaises(AssuranceError):
                    qa_plane.validate_finding(model_finding(outcome=outcome))

    def test_the_rights_and_security_row_blocks_on_the_deterministic_plane(self):
        rights = finding(
            finding_id="r-1", check_id="rights/font-license-preflight",
            outcome="HARD_BLOCK", severity="BLOCKER",
        )
        self.assertEqual("HARD_BLOCK", qa_plane.validate_finding(rights).outcome)
        rights_row = next(
            row for row in qa_plane.POLICY_ROWS if row["policy_row"] == "RIGHTS_SECURITY"
        )
        self.assertEqual(("HARD_BLOCK",), rights_row["allowed_outcomes"])
        self.assertTrue(rights_row["may_block"])
        self.assertFalse(rights_row["may_be_final"])
        self.assertEqual("qa-deterministic", rights_row["plane_id"])
        # The row is a check family, not a fourth plane: it shares the
        # deterministic plane's allowed set and cannot push a decision to a human.
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(check_id="security/secret-scan",
                                              outcome="REVIEW_REQUIRED"))

    def test_the_schema_carries_the_closed_vocabulary(self):
        validator = jsonschema.Draft202012Validator(qa_plane.qa_schema())
        enum = qa_plane.qa_schema()["$defs"]["finding"]["properties"]["outcome"]["enum"]
        self.assertEqual(list(qa_plane.OUTCOMES), enum)
        for retired in ("FAIL", "INCONCLUSIVE", "NOT_RUN", "REJECTED"):
            with self.subTest(retired=retired):
                document = layer_document([finding(outcome=retired)])
                self.assertTrue(list(validator.iter_errors(document)), retired)

    def test_a_human_approval_is_never_a_blocker(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(human_finding(severity="BLOCKER"))
        self.assertIn("never a blocker", str(caught.exception))
        rejected = human_finding(outcome="REJECT", verdict="REJECT", severity="BLOCKER")
        self.assertEqual("REJECT", qa_plane.validate_finding(rejected).verdict)


class QaFindingTests(unittest.TestCase):
    def test_every_outcome_needs_a_nonzero_artifact_digest(self):
        candidate = finding()
        self.assertIs(candidate, qa_plane.validate_finding(candidate))
        for outcome in qa_plane.OUTCOMES:
            if outcome in qa_plane.HUMAN_OUTCOMES:
                item = human_finding(outcome=outcome, verdict=outcome, evidence={})
            elif outcome == "REVIEW_REQUIRED":
                item = model_finding(outcome=outcome, evidence={})
            else:
                item = finding(outcome=outcome, evidence={})
            with self.subTest(outcome=outcome):
                with self.assertRaises(AssuranceError) as caught:
                    qa_plane.validate_finding(item)
                self.assertIn("without an artifact_sha256", str(caught.exception))
        with self.assertRaises(AssuranceError) as zero:
            qa_plane.validate_finding(finding(evidence={"artifact_sha256": "sha256:" + "0" * 64}))
        self.assertIn("nonzero", str(zero.exception))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(outcome="WARN", evidence={"artifact_sha256": "nope"}))

    def test_an_unbound_result_is_not_evidence(self):
        document = finding(evidence={}).as_dict()
        validator = jsonschema.Draft202012Validator(qa_plane.qa_schema())
        errors = list(validator.iter_errors(layer_document([]) | {"findings": [document]}))
        self.assertTrue(errors, "a finding without artifact_sha256 must fail the schema too")
    def test_deterministic_plane_states_an_outcome_only(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(finding(recommendation="looks fine, ship it"))
        self.assertIn("deterministic", str(caught.exception))
        with self.assertRaises(AssuranceError) as verdict:
            qa_plane.validate_finding(finding(outcome="PASS", verdict="APPROVE"))
        self.assertIn("only permitted in a HUMAN plane", str(verdict.exception))

    def test_model_assisted_plane_may_only_recommend(self):
        self.assertIsNotNone(qa_plane.validate_finding(model_finding()))
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(model_finding(recommendation=None))
        self.assertIn("may only recommend", str(caught.exception))
        with self.assertRaises(AssuranceError) as verdict:
            qa_plane.validate_finding(model_finding(verdict="APPROVE"))
        self.assertIn("HUMAN plane", str(verdict.exception))

    def test_model_assisted_plane_cannot_claim_human_evidence(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(model_finding(
                evidence={"artifact_sha256": SHA, "evidence_level": "E4"}))
        self.assertIn("above its ceiling", str(caught.exception))

    def test_blocker_requires_a_plane_that_can_block(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(model_finding(severity="BLOCKER"))
        self.assertIn("may not block", str(caught.exception))
        with self.assertRaises(AssuranceError) as outcome:
            qa_plane.validate_finding(model_finding(outcome="HARD_BLOCK"))
        self.assertIn("may not block", str(outcome.exception))
        blocking = finding(outcome="HARD_BLOCK", severity="BLOCKER")
        self.assertIsNotNone(qa_plane.validate_finding(blocking))

    def test_a_human_decision_needs_its_signed_verdict(self):
        self.assertIsNotNone(qa_plane.validate_finding(human_finding()))
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(human_finding(verdict=None))
        self.assertIn("without a verdict", str(caught.exception))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(human_finding(verdict="ACCEPT"))
        with self.assertRaises(AssuranceError) as disagreement:
            qa_plane.validate_finding(human_finding(outcome="APPROVE", verdict="REJECT"))
        self.assertIn("must state the same one", str(disagreement.exception))
        rejected = qa_plane.validate_finding(human_finding(outcome="REJECT", verdict="REJECT"))
        self.assertEqual("REJECT", rejected.verdict)

    def test_the_schema_pins_verdict_to_outcome(self):
        validator = jsonschema.Draft202012Validator(qa_plane.qa_schema())
        document = layer_document([human_finding(outcome="APPROVE", verdict="REJECT")])
        self.assertTrue(list(validator.iter_errors(document)))
        clean = layer_document([human_finding()])
        self.assertEqual([], list(validator.iter_errors(clean)))

    def test_unknown_plane_and_identifiers_are_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.validate_finding(finding(layer_id="qa-made-up"))
        self.assertIn("unknown QA layer", str(caught.exception))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(finding_id="  "))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(outcome="MAYBE"))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(severity="CRITICAL"))
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding({"finding_id": "f"})
        with self.assertRaises(AssuranceError):
            qa_plane.validate_finding(finding(evidence="sha256:abc"))


class QaAggregateTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".project-local/task-runtime/assurance-qa-plane-tests"
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def test_automated_findings_alone_never_reach_pass(self):
        summary = qa_plane.aggregate([finding(), model_finding()])
        self.assertEqual("NEEDS_HUMAN_VERDICT", summary["gate"])
        self.assertEqual([], summary["blocking"])
        self.assertEqual(["qa-human"], summary["missing_human_verdicts"])
        reason = qa_plane.explain_aggregate(summary)
        self.assertIn("NEEDS_HUMAN_VERDICT", reason)
        self.assertIn("no automated plane may supply one", reason)

    def test_an_escalation_is_not_a_verdict(self):
        summary = qa_plane.aggregate([model_finding(outcome="REVIEW_REQUIRED")])
        self.assertEqual("NEEDS_HUMAN_VERDICT", summary["gate"])
        self.assertEqual(1, summary["planes"]["MODEL_ASSISTED"]["outcomes"]["REVIEW_REQUIRED"])
        self.assertIsNone(summary["planes"]["MODEL_ASSISTED"]["human_verdict"])

    def test_empty_findings_fail_closed(self):
        summary = qa_plane.aggregate([])
        self.assertEqual("NEEDS_HUMAN_VERDICT", summary["gate"])

    def test_human_verdict_completes_the_gate(self):
        summary = qa_plane.aggregate([finding(), model_finding(), human_finding()])
        self.assertEqual("PASS", summary["gate"])
        self.assertEqual({"qa-human": "APPROVE"}, summary["human_verdicts"])
        self.assertIn("gate PASS", qa_plane.explain_aggregate(summary))

    def test_a_human_rejection_is_final_and_blocks(self):
        rejected = human_finding(finding_id="h-reject", outcome="REJECT", verdict="REJECT")
        summary = qa_plane.aggregate([finding(), model_finding(), rejected])
        self.assertEqual("BLOCKED", summary["gate"])
        self.assertEqual(["h-reject"], summary["blocking"])
        self.assertEqual("REJECT", summary["planes"]["HUMAN"]["human_verdict"])
        reason = qa_plane.explain_aggregate(summary)
        self.assertIn("gate BLOCKED", reason)
        self.assertIn("not waivable here", reason)

    def test_an_unsigned_human_finding_is_refused_not_counted(self):
        with self.assertRaises(AssuranceError):
            qa_plane.aggregate([finding(), human_finding(verdict=None)])

    def test_blocker_outranks_a_human_approve(self):
        blocked = finding(finding_id="f-blocker", outcome="HARD_BLOCK", severity="BLOCKER")
        summary = qa_plane.aggregate([blocked, model_finding(), human_finding()])
        self.assertEqual("BLOCKED", summary["gate"])
        self.assertEqual(["f-blocker"], summary["blocking"])
        self.assertEqual("HUMAN", summary["layers"]["qa-human"]["kind"])
        self.assertEqual("APPROVE", summary["planes"]["HUMAN"]["human_verdict"])
        reason = qa_plane.explain_aggregate(summary)
        self.assertIn("gate BLOCKED", reason)
        self.assertIn("f-blocker", reason)
        self.assertIn("not waivable here", reason)

    def test_a_hard_block_outranks_a_later_human_approve(self):
        hard = finding(finding_id="f-hard", outcome="HARD_BLOCK", severity="MAJOR")
        summary = qa_plane.aggregate([hard, human_finding()])
        self.assertEqual("BLOCKED", summary["gate"])

    def test_per_plane_counts(self):
        summary = qa_plane.aggregate([
            finding(finding_id="f-1"),
            finding(finding_id="f-2", outcome="WARN"),
            model_finding(),
            human_finding(),
        ])
        self.assertEqual(2, summary["planes"]["DETERMINISTIC"]["finding_count"])
        self.assertEqual(1, summary["planes"]["DETERMINISTIC"]["outcomes"]["PASS"])
        self.assertEqual(1, summary["planes"]["DETERMINISTIC"]["outcomes"]["WARN"])
        self.assertEqual(1, summary["planes"]["MODEL_ASSISTED"]["finding_count"])
        self.assertEqual(1, summary["planes"]["HUMAN"]["finding_count"])
        self.assertEqual(4, summary["finding_count"])

    def test_summary_is_json_serializable_and_schema_valid(self):
        summary = qa_plane.aggregate([finding(), model_finding(), human_finding()])
        path = self.tmp / "summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(summary, reloaded)
        document = {
            "schemaVersion": "design-lab/assurance-qa-layer/v1",
            "planes": [layer.as_dict() for layer in qa_plane.QA_PLANES],
            "summary": reloaded,
        }
        jsonschema.validate(instance=document, schema=qa_plane.qa_schema())
        self.assertIn("not an acceptance record", reloaded["explanation"])

    def test_duplicate_findings_and_bad_input_are_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            qa_plane.aggregate([finding(), finding()])
        self.assertIn("duplicate finding_id", str(caught.exception))
        with self.assertRaises(AssuranceError):
            qa_plane.aggregate("f-1")
        with self.assertRaises(AssuranceError):
            qa_plane.aggregate([{"finding_id": "f"}])

    def test_explain_refuses_a_foreign_summary(self):
        with self.assertRaises(AssuranceError):
            qa_plane.explain_aggregate({"gate": "DONE"})
        with self.assertRaises(AssuranceError):
            qa_plane.explain_aggregate("gate PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
