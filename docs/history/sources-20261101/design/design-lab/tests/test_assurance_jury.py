# SPDX-License-Identifier: MIT
"""DLDS-F070 / DL-P0-171 human jury structure: APPROVE/REJECT verdicts, proposals, binding.

Every guarantee the module had before the policy was frozen is re-proved here
under the frozen vocabulary, plus the two new structural refusals: a record
carrying proposal markers cannot be re-tagged into a verdict, and the retired
non-final REVISE is not part of the jury vocabulary at all.

``test_reject_needs_evidence_and_verdict_enum_is_closed`` became
:meth:`VerdictVocabularyTests.test_reject_needs_evidence` plus
:meth:`VerdictVocabularyTests.test_the_vocabulary_is_the_frozen_one`.
"""
from __future__ import annotations

import copy
import dataclasses
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
from design_lab.assurance import human_jury  # noqa: E402

SHA = "sha256:" + "c" * 64
SHA_OTHER = "sha256:" + "d" * 64
SUBJECT = "design-lab/job/job-1/deliverable/poster"


def criteria(*pairs):
    items = pairs or (("anti-slop", 4.0), ("layout", 2.0))
    weight = 1.0 / len(items)
    return tuple(
        human_jury.Criterion(criterion_id=name, weight=weight, score=score)
        for name, score in items
    )


def verdict(**overrides):
    base = {
        "jury_record_id": "jury-1",
        "subject_ref": SUBJECT,
        "artifact_sha256": SHA,
        "juror": human_jury.Juror(
            juror_id="dtalex66",
            kind="HUMAN",
            attestation="reviewed the exported poster at 100% on a calibrated display",
        ),
        "criteria": criteria(),
        "verdict": "APPROVE",
        "decided_at": "2026-09-12T10:00:00Z",
    }
    base.update(overrides)
    return human_jury.JuryVerdict(**base)


def panel(members=("dtalex66", "reviewer-2")):
    return human_jury.Juror(
        juror_id="panel-quality-1",
        kind="PANEL",
        attestation="two independent human reviewers scored the same artifact",
        members=members,
    )


def proposal():
    return human_jury.agent_may_propose(
        proposal_id="prop-1",
        subject_ref=SUBJECT,
        artifact_sha256=SHA,
        proposer="design-lab/agent/critique",
        criteria=criteria(),
        suggested_verdict="REJECT",
        rationale="the material axis looks inconsistent; a human should confirm",
        created_at="2026-09-12T09:00:00Z",
    )


class VerdictVocabularyTests(unittest.TestCase):
    """DLDS-F070: the jury's final vocabulary is APPROVE / REJECT and nothing else."""

    def test_the_vocabulary_is_the_frozen_one(self):
        self.assertEqual(("APPROVE", "REJECT"), human_jury.VERDICTS)
        self.assertEqual(("APPROVE", "REJECT"), human_jury.FINAL_OUTCOMES)
        enum = human_jury.schema()["properties"]["verdict"]["enum"]
        self.assertEqual(["APPROVE", "REJECT"], enum)
        for retired in ("ACCEPT", "REVISE", "PASS", "REJECTED"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, human_jury.VERDICTS)
                self.assertNotIn(retired, enum)
                with self.assertRaises(AssuranceError) as caught:
                    human_jury.record_verdict(verdict(verdict=retired))
                self.assertIn(retired, str(caught.exception))

    def test_revise_was_dropped_rather_than_hidden(self):
        # A non-final REVISE would need somewhere outside the final-verdict field
        # to live; DLDS-F070 keeps one vocabulary per plane instead, so a wanted
        # revision is a REJECT with evidence.
        self.assertNotIn("REVISE", human_jury.VERDICTS)
        self.assertNotIn("REVISE", human_jury.schema()["$defs"]["proposal"]
                         ["properties"]["suggested_verdict"]["enum"])
        rejected = human_jury.record_verdict(verdict(
            verdict="REJECT", evidence_refs=("reports/current/qa-summary.json",)))
        self.assertEqual("REJECT", rejected["verdict"])
        with self.assertRaises(AssuranceError):
            human_jury.record_verdict(verdict(verdict="REVISE"))

    def test_reject_needs_evidence(self):
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(verdict(verdict="REJECT"))
        self.assertIn("evidence_ref", str(caught.exception))
        approved = human_jury.record_verdict(verdict())
        self.assertEqual("APPROVE", approved["verdict"])
        self.assertEqual([], approved["evidence_refs"])


class JuryVerdictTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".project-local/task-runtime/assurance-jury-tests"
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def test_a_human_verdict_records_against_the_v2_schema(self):
        original = verdict()
        document = human_jury.record_verdict(original)
        self.assertIsInstance(document, dict)
        self.assertEqual("JURY_VERDICT", document["kind"])
        self.assertEqual("design-lab/assurance-jury-record/v2", document["schemaVersion"])
        self.assertEqual(SHA, document["artifact_sha256"])
        self.assertEqual(1.0, sum(item["weight"] for item in document["criteria"]))
        jsonschema.validate(instance=document, schema=human_jury.schema())
        path = self.tmp / "jury.json"
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        self.assertEqual(document, json.loads(path.read_text(encoding="utf-8")))
        # The frozen input is never mutated.
        self.assertEqual("APPROVE", original.verdict)

    def test_recording_never_mutates_a_document_input(self):
        source = verdict().as_dict()
        document = human_jury.record_verdict(source)
        document["verdict"] = "REJECT"
        self.assertEqual("APPROVE", source["verdict"])

    def test_weights_must_sum_to_one(self):
        uneven = verdict(criteria=(
            human_jury.Criterion(criterion_id="a", weight=0.5, score=4.0),
            human_jury.Criterion(criterion_id="b", weight=0.4, score=4.0),
        ))
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(uneven)
        self.assertIn("must sum to 1.0", str(caught.exception))
        floating = verdict(criteria=(
            human_jury.Criterion(criterion_id="a", weight=0.5, score=4.0),
            human_jury.Criterion(criterion_id="b", weight=0.5 + 1e-9, score=4.0),
        ))
        self.assertEqual("APPROVE", human_jury.record_verdict(floating)["verdict"])

    def test_duplicate_or_out_of_range_criteria_are_refused(self):
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(verdict(criteria=(
                human_jury.Criterion(criterion_id="a", weight=0.5, score=4.0),
                human_jury.Criterion(criterion_id="a", weight=0.5, score=4.0),
            )))
        self.assertIn("duplicate criterion_id", str(caught.exception))
        with self.assertRaises(AssuranceError):
            human_jury.record_verdict(verdict(criteria=(
                human_jury.Criterion(criterion_id="a", weight=1.0, score=9.0),
            )))
        with self.assertRaises(AssuranceError):
            human_jury.record_verdict(verdict(criteria=()))

    def test_extreme_scores_need_a_note(self):
        for extreme in (5.0, 0.0):
            with self.assertRaises(AssuranceError) as caught:
                human_jury.record_verdict(verdict(criteria=(
                    human_jury.Criterion(criterion_id="anti-slop", weight=1.0, score=extreme),
                )))
            self.assertIn("note", str(caught.exception))
        explained = verdict(criteria=(
            human_jury.Criterion(criterion_id="anti-slop", weight=1.0, score=5.0,
                                 note="every token is locked and no AI default pattern remains"),
        ))
        self.assertEqual("APPROVE", human_jury.record_verdict(explained)["verdict"])

    def test_an_agent_signed_verdict_is_refused_by_name(self):
        for kind in ("AGENT", "MODEL", "ASSISTANT", "SYSTEM"):
            with self.assertRaises(AssuranceError) as caught:
                human_jury.record_verdict(verdict(juror=human_jury.Juror(
                    juror_id="agent-1", kind=kind, attestation="self-assessed")))
            self.assertIn("agent-signed verdict is refused", str(caught.exception))
        # The schema forbids the actor kind independently of the module code.
        foreign = verdict().as_dict()
        foreign["juror"]["kind"] = "AGENT"
        errors = list(jsonschema.Draft202012Validator(human_jury.schema()).iter_errors(foreign))
        self.assertTrue(errors, "the schema itself must not admit an AGENT juror")

    def test_a_record_without_a_human_actor_fails_closed(self):
        document = verdict().as_dict()
        del document["juror"]
        with self.assertRaises(AssuranceError) as caught:
            human_jury.assert_not_agent_signed(document)
        self.assertIn("no human actor is established", str(caught.exception))
        with self.assertRaises(AssuranceError):
            human_jury.assert_not_agent_signed({"juror": {"juror_id": "x"}})
        with self.assertRaises(AssuranceError):
            human_jury.assert_not_agent_signed(42)

    def test_panel_kind_needs_named_members(self):
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(verdict(juror=panel(members=())))
        self.assertIn("members", str(caught.exception))
        self.assertEqual("APPROVE", human_jury.record_verdict(verdict(juror=panel()))["verdict"])

    def test_decided_at_must_be_an_rfc3339_instant(self):
        for value in ("2026-09-12", "2026-09-12T10:00:00", "12/09/2026", ""):
            with self.assertRaises(AssuranceError):
                human_jury.record_verdict(verdict(decided_at=value))
        for value in ("2026-09-12T10:00:00Z", "2026-09-12T10:00:00.500+02:00",
                      "2026-09-12T10:00:00z"):
            self.assertEqual(value, human_jury.record_verdict(verdict(decided_at=value))["decided_at"])
        # A pattern-shaped but impossible instant passes the schema (the installed
        # jsonschema has no date-time checker) and must be caught by the module.
        impossible = verdict().as_dict()
        impossible["decided_at"] = "2026-13-45T99:99:99+00:00"
        self.assertTrue(
            jsonschema.Draft202012Validator(human_jury.schema()).is_valid(impossible)
        )
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(verdict(decided_at="2026-13-45T99:99:99+00:00"))
        self.assertIn("not a parseable RFC3339", str(caught.exception))

    def test_supersedes_is_append_only(self):
        self.assertEqual("jury-0", human_jury.record_verdict(
            verdict(supersedes="jury-0"))["supersedes"])
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(verdict(supersedes="jury-1"))
        self.assertIn("may not supersede itself", str(caught.exception))

    def test_schema_closes_unknown_fields_and_the_artifact_identity(self):
        validator = jsonschema.Draft202012Validator(human_jury.schema())
        extra = verdict().as_dict()
        extra["humanReview"] = {"reviewer": "somebody"}
        self.assertTrue(list(validator.iter_errors(extra)))
        zero = verdict().as_dict()
        zero["artifact_sha256"] = "sha256:" + "0" * 64
        self.assertTrue(list(validator.iter_errors(zero)))


class JuryProposalTests(unittest.TestCase):
    """An agent may propose; every verdict-taking function must refuse a proposal."""

    def test_a_proposal_is_never_a_verdict(self):
        item = proposal()
        self.assertEqual("JURY_PROPOSAL", item.kind)
        self.assertFalse(item.is_verdict)
        schema = human_jury.schema()
        subschema = dict(schema["$defs"]["proposal"])
        subschema["$defs"] = schema["$defs"]
        jsonschema.validate(instance=item.as_dict(), schema=subschema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(instance=item.as_dict(), schema=schema)

    def test_every_verdict_function_refuses_a_proposal(self):
        item = proposal()
        for function, args, expected in (
            (human_jury.record_verdict, (item,), "JURY_PROPOSAL"),
            (human_jury.score_summary, (item,), "JURY_PROPOSAL"),
            (human_jury.validate_against_subject, (item, {"artifact_sha256": SHA}),
             "JURY_PROPOSAL"),
            (human_jury.resign_kind, (item, "JURY_VERDICT"), "JuryVerdict"),
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(AssuranceError) as caught:
                    function(*args)
                self.assertIn(expected, str(caught.exception))
        with self.assertRaises(AssuranceError) as caught:
            human_jury.assert_not_agent_signed(item)
        self.assertIn("proposal is not a signed record", str(caught.exception))
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(item.as_dict())
        self.assertIn("proposal is a recommendation, not a verdict", str(caught.exception))

    def test_a_proposal_cannot_be_relabelled_into_a_verdict(self):
        """An agent-produced document must stay unrepresentable, not merely discouraged."""
        forged = copy.deepcopy(proposal().as_dict())
        forged["kind"] = "JURY_VERDICT"
        for function, args in (
            (human_jury.record_verdict, (forged,)),
            (human_jury.score_summary, (forged,)),
            (human_jury.validate_against_subject, (forged, {"artifact_sha256": SHA})),
            (human_jury.assert_not_agent_signed, (forged,)),
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(AssuranceError) as caught:
                    function(*args)
                message = str(caught.exception)
                self.assertIn("proposal marker", message)
        # The schema refuses it independently of the module.
        errors = list(
            jsonschema.Draft202012Validator(human_jury.schema()).iter_errors(forged)
        )
        self.assertTrue(errors, "a relabelled proposal must not validate as a verdict")
        # A jury record that merely declares is_verdict false is refused too.
        marked = verdict().as_dict()
        marked["is_verdict"] = False
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(marked)
        self.assertIn("proposal marker", str(caught.exception))

    def test_the_kind_marker_is_load_bearing(self):
        reshaped = human_jury.resign_kind(verdict(), "JURY_PROPOSAL")
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(reshaped)
        self.assertIn("JURY_PROPOSAL", str(caught.exception))
        unmarked = human_jury.resign_kind(verdict(), "SOMETHING_ELSE")
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(unmarked)
        self.assertIn("requires a record of kind 'JURY_VERDICT'", str(caught.exception))

    def test_proposal_inputs_are_validated(self):
        with self.assertRaises(AssuranceError):
            human_jury.agent_may_propose(
                proposal_id="p", subject_ref=SUBJECT, artifact_sha256="sha256:" + "0" * 64,
                proposer="agent", criteria=criteria(), suggested_verdict="REJECT",
                rationale="r", created_at="2026-09-12T09:00:00Z")
        for retired in ("REVISE", "ACCEPT", "APPROVED"):
            with self.subTest(retired=retired):
                with self.assertRaises(AssuranceError) as caught:
                    human_jury.agent_may_propose(
                        proposal_id="p", subject_ref=SUBJECT, artifact_sha256=SHA,
                        proposer="agent", criteria=criteria(), suggested_verdict=retired,
                        rationale="r", created_at="2026-09-12T09:00:00Z")
                self.assertIn("suggested_verdict must be one of APPROVE, REJECT",
                              str(caught.exception))
        with self.assertRaises(AssuranceError):
            human_jury.agent_may_propose(
                proposal_id="p", subject_ref=SUBJECT, artifact_sha256=SHA,
                proposer="agent", criteria=criteria(), suggested_verdict="REJECT",
                rationale="r", created_at="yesterday")

    def test_a_tampered_proposal_cannot_become_a_verdict(self):
        document = proposal().as_dict()
        document["kind"] = "JURY_VERDICT"
        with self.assertRaises(AssuranceError) as caught:
            human_jury.record_verdict(document)
        self.assertIn("proposal marker", str(caught.exception))
        document["juror"] = dataclasses.asdict(verdict().juror)
        with self.assertRaises(AssuranceError):
            human_jury.record_verdict(document)


class JuryScoreAndBindingTests(unittest.TestCase):
    def test_score_summary_is_weighted_and_confidence_is_absent_for_one_human(self):
        summary = human_jury.score_summary(verdict())
        self.assertEqual(3.0, summary["weighted_total"])
        self.assertEqual(2, len(summary["criteria"]))
        self.assertEqual(2.0, summary["criteria"][0]["weighted"])
        self.assertIsNone(summary["confidence"])
        self.assertEqual("SINGLE_JUROR", summary["confidence_basis"])
        self.assertEqual("APPROVE", summary["verdict"])

    def test_panel_confidence_needs_more_than_one_juror(self):
        single = human_jury.score_summary(verdict(juror=panel(members=("dtalex66",))))
        self.assertIsNone(single["confidence"])
        self.assertEqual("PANEL_SINGLE_MEMBER", single["confidence_basis"])
        multi = human_jury.score_summary(verdict(juror=panel()))
        self.assertIsInstance(multi["confidence"], str)
        self.assertIn("NOT_COMPUTED", multi["confidence"])
        self.assertIn("inter-rater agreement", multi["confidence"])
        self.assertEqual(2, multi["juror_count"])

    def test_a_verdict_is_bound_to_one_exact_artifact(self):
        item = verdict()
        self.assertIsInstance(
            human_jury.validate_against_subject(item, {"artifact_sha256": SHA}), dict)
        self.assertIsInstance(human_jury.validate_against_subject(item, SHA), dict)
        with self.assertRaises(AssuranceError) as caught:
            human_jury.validate_against_subject(item, {"artifact_sha256": SHA_OTHER})
        message = str(caught.exception)
        self.assertIn("cannot be reused", message)
        self.assertIn("same design, close enough", message)
        with self.assertRaises(AssuranceError):
            human_jury.validate_against_subject(item, {"subject_ref": SUBJECT})
        with self.assertRaises(AssuranceError):
            human_jury.validate_against_subject(item, {"artifact_sha256": "sha256:" + "0" * 64})

    def test_record_is_a_plain_copy_of_the_input_shape(self):
        item = verdict()
        document = human_jury.record_verdict(item)
        self.assertEqual(
            sorted(document), sorted([
                "schemaVersion", "kind", "jury_record_id", "subject_ref", "artifact_sha256",
                "juror", "criteria", "verdict", "decided_at", "supersedes", "evidence_refs",
            ]))
        self.assertNotIn("axes", copy.deepcopy(document))


if __name__ == "__main__":
    unittest.main(verbosity=2)
