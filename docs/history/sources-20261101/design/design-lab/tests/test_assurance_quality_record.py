# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-B3 / G-3: sealed per-artifact QualityRecord guarantees.

Proves the record layer of the frozen QA policy: the ``quality.{deterministic,
automated_judge, human_jury}`` triple is three physically separated fields that
cannot overwrite one another, an automated judge can never fill the human field
or reach the gate, no model score reaches ``final_gate``, a finding placed in
the wrong plane field is refused, and ``PASS`` is structurally unreachable
without a signed human verdict.

The tests reuse the frozen modules (``qa_plane``, ``human_jury``) rather than
re-deriving their policy, so they stay closed under the same vocabulary
DLDS-F070 froze.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jsonschema  # noqa: E402

from design_lab.assurance import AssuranceError  # noqa: E402
from design_lab.assurance import human_jury  # noqa: E402
from design_lab.assurance import qa_plane  # noqa: E402
from design_lab.assurance import quality_record  # noqa: E402

SHA = "sha256:" + "a" * 64
SHA_OTHER = "sha256:" + "b" * 64
SUBJECT = "design-lab/job/job-1/deliverable/poster"


def det_finding(**overrides):
    base = {
        "finding_id": "f-det-1",
        "layer_id": "qa-deterministic",
        "check_id": "check_anti_slop",
        "subject_ref": SUBJECT,
        "outcome": "PASS",
        "severity": "INFO",
        "evidence": {"artifact_sha256": SHA},
    }
    base.update(overrides)
    return base


def judge_finding(**overrides):
    base = {
        "finding_id": "f-judge-1",
        "layer_id": "qa-model-assisted",
        "check_id": "provider:aesthetic/laion",
        "subject_ref": SUBJECT,
        "outcome": "REVIEW_REQUIRED",
        "severity": "MINOR",
        "evidence": {"artifact_sha256": SHA},
        "recommendation": "composition reads as default; escalate to the human jury",
    }
    base.update(overrides)
    return base


def verdict_doc(**overrides):
    base = {
        "schemaVersion": "design-lab/assurance-jury-record/v2",
        "kind": "JURY_VERDICT",
        "jury_record_id": "j-1",
        "subject_ref": SUBJECT,
        "artifact_sha256": SHA,
        "juror": {
            "juror_id": "dtalex66",
            "kind": "HUMAN",
            "attestation": "reviewed the exported poster at 100% on a calibrated display",
        },
        "criteria": [
            {"criterion_id": "anti-slop", "weight": 1.0, "score": 4.0, "note": None},
        ],
        "verdict": "APPROVE",
        "decided_at": "2026-09-23T10:00:00Z",
        "supersedes": None,
        "evidence_refs": [],
    }
    base.update(overrides)
    return base


class RecordConstructionTests(unittest.TestCase):
    def test_needs_human_verdict_when_no_human_field(self):
        record = quality_record.record_quality_record(
            quality_record_id="qr-1", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()], automated_judge=[judge_finding()])
        self.assertIsNone(record["human_jury"])
        self.assertEqual("NEEDS_HUMAN_VERDICT", record["final_gate"])

    def test_human_approve_reaches_pass(self):
        record = quality_record.record_quality_record(
            quality_record_id="qr-2", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()], automated_judge=[judge_finding()],
            human_verdict=verdict_doc())
        self.assertEqual("PASS", record["final_gate"])
        self.assertEqual("APPROVE", record["human_jury"]["verdict"])

    def test_human_reject_is_blocking(self):
        record = quality_record.record_quality_record(
            quality_record_id="qr-3", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()],
            human_verdict=verdict_doc(verdict="REJECT",
                                     evidence_refs=["reports/current/qa-summary.json"]))
        self.assertEqual("BLOCKED", record["final_gate"])

    def test_deterministic_hard_block_outranks_human_approve(self):
        record = quality_record.record_quality_record(
            quality_record_id="qr-4", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding(outcome="HARD_BLOCK", severity="BLOCKER",
                                       finding_id="f-block")],
            human_verdict=verdict_doc())
        self.assertEqual("BLOCKED", record["final_gate"])

    def test_record_is_plain_and_schema_valid(self):
        record = quality_record.record_quality_record(
            quality_record_id="qr-5", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()],
            human_verdict=verdict_doc())
        self.assertIsInstance(record, dict)
        jsonschema.validate(instance=record, schema=quality_record.schema())
        # the input verdict document is not mutated by recording
        self.assertEqual("APPROVE", verdict_doc()["verdict"])


class NonOverwriteGuaranteeTests(unittest.TestCase):
    """The three plane fields cannot overwrite each other."""

    def test_automated_judge_never_blocks_or_gates(self):
        # only an advisory model finding and no human verdict yet: the gate must
        # still need the human, not be decided by the model's REVIEW_REQUIRED.
        record = quality_record.record_quality_record(
            quality_record_id="g-1", subject_ref=SUBJECT, artifact_sha256=SHA,
            automated_judge=[judge_finding()])
        self.assertEqual("NEEDS_HUMAN_VERDICT", record["final_gate"])

    def test_a_model_finding_misplaced_in_the_deterministic_field_is_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="g-2", subject_ref=SUBJECT, artifact_sha256=SHA,
                deterministic=[judge_finding()])
        self.assertIn("placed in", str(caught.exception))

    def test_a_human_finding_misplaced_in_the_judge_field_is_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="g-3", subject_ref=SUBJECT, artifact_sha256=SHA,
                automated_judge=[{"finding_id": "h1", "layer_id": "qa-human",
                                    "check_id": "human-jury", "subject_ref": SUBJECT,
                                    "outcome": "APPROVE", "severity": "INFO",
                                    "evidence": {"artifact_sha256": SHA},
                                    "verdict": "APPROVE"}])
        self.assertIn("placed in", str(caught.exception))

    def test_a_finding_bound_to_a_different_artifact_is_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="g-4", subject_ref=SUBJECT, artifact_sha256=SHA,
                deterministic=[det_finding(evidence={"artifact_sha256": SHA_OTHER})])
        self.assertIn("bound to", str(caught.exception))

    def test_a_human_verdict_on_a_different_artifact_is_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="g-5", subject_ref=SUBJECT, artifact_sha256=SHA,
                deterministic=[det_finding()],
                human_verdict=verdict_doc(artifact_sha256=SHA_OTHER))
        self.assertIn("bound to", str(caught.exception))


class NoModelScoreReachesGateTests(unittest.TestCase):
    def test_an_agent_signed_human_field_is_refused(self):
        agent = verdict_doc(juror={"juror_id": "auto", "kind": "MODEL",
                                    "attestation": "model self-score"})
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="m-1", subject_ref=SUBJECT, artifact_sha256=SHA,
                deterministic=[det_finding()], human_verdict=agent)
        self.assertIn("agent-signed", str(caught.exception))

    def test_a_proposal_retagged_as_a_verdict_is_refused(self):
        proposal = human_jury.agent_may_propose(
            proposal_id="p-1", subject_ref=SUBJECT, artifact_sha256=SHA,
            proposer="design-lab/agent/critique",
            criteria=(human_jury.Criterion(criterion_id="a", weight=1.0, score=4.0),),
            suggested_verdict="APPROVE", rationale="r",
            created_at="2026-09-23T10:00:00Z").as_dict()
        proposal["kind"] = "JURY_VERDICT"
        with self.assertRaises(AssuranceError) as caught:
            quality_record.record_quality_record(
                quality_record_id="m-2", subject_ref=SUBJECT, artifact_sha256=SHA,
                deterministic=[det_finding()], human_verdict=proposal)
        self.assertIn("proposal marker", str(caught.exception))

    def test_an_automated_judge_cannot_supply_the_gate(self):
        good = quality_record.record_quality_record(
            quality_record_id="m-3", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()])
        self.assertEqual("NEEDS_HUMAN_VERDICT", good["final_gate"])
        forged = copy.deepcopy(good)
        forged["final_gate"] = "PASS"
        with self.assertRaises(AssuranceError) as caught:
            quality_record.validate_quality_record(forged)
        self.assertIn("derive", str(caught.exception))


class SummaryViewTests(unittest.TestCase):
    def test_summary_excludes_the_judge_from_blocking(self):
        record = quality_record.record_quality_record(
            quality_record_id="s-1", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()], automated_judge=[judge_finding()],
            human_verdict=verdict_doc())
        view = quality_record.as_gate_summary(record)
        self.assertFalse(view["automated_judge"]["final"])
        # Stronger than an empty list: the advisory judge block has no
        # 'blocking' key at all, so a model score cannot even be represented as
        # blocking, let alone as an empty-but-present one.
        self.assertNotIn("blocking", view["automated_judge"])
        self.assertEqual("PASS", view["final_gate"])
        self.assertEqual("APPROVE", view["human_jury"]["verdict"])

    def test_a_rejected_record_marks_the_human_field_blocking(self):
        record = quality_record.record_quality_record(
            quality_record_id="s-2", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()],
            human_verdict=verdict_doc(verdict="REJECT",
                                      evidence_refs=["reports/current/qa-summary.json"]))
        view = quality_record.as_gate_summary(record)
        self.assertEqual("BLOCKED", view["final_gate"])
        self.assertTrue(view["human_jury"]["blocking"])


class RoundTripTests(unittest.TestCase):
    def test_a_valid_record_re_validates_cleanly(self):
        record = quality_record.record_quality_record(
            quality_record_id="rt-1", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()], automated_judge=[judge_finding()],
            human_verdict=verdict_doc())
        self.assertEqual(record, quality_record.validate_quality_record(
            json.loads(json.dumps(record))))

    def test_a_stale_record_with_a_retagged_human_field_fails_closed(self):
        record = quality_record.record_quality_record(
            quality_record_id="rt-2", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[det_finding()], human_verdict=verdict_doc())
        tampered = json.loads(json.dumps(record))
        tampered["human_jury"]["juror"]["kind"] = "MODEL"
        with self.assertRaises(AssuranceError):
            quality_record.validate_quality_record(tampered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
