#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-B3 / G-3: structural gate for the sealed QualityRecord.

Proves, on every run, that the record layer of the frozen QA policy holds:
the ``quality.{deterministic, automated_judge, human_jury}`` triple is three
physically separated fields that cannot overwrite one another; an automated
judge can never fill the human field or reach the gate; no model score reaches
``final_gate``; and ``PASS`` is structurally unreachable without a signed human
verdict. This is the record counterpart of the frozen policy already owned by
``design-lab/src/design_lab/assurance/{qa_plane,human_jury}.py``; it composes
them rather than re-deriving them, so it stays closed under the same frozen
vocabulary.

Fail-closed and stdlib-plus-jsonschema (jsonschema is the sole schema-validation
dependency of this repository, see requirements.txt). Exit 0 = every
guarantee held; exit 1 = one was broken.

Usage:
    python design-lab/scripts/verify_quality_record.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from design_lab.assurance import AssuranceError, human_jury, qa_plane, quality_record  # noqa: E402

SHA = "sha256:" + "a" * 64
SHA_OTHER = "sha256:" + "b" * 64
SUBJECT = "design-lab/job/job-1/deliverable/poster"


def _det(**ov):
    base = {"finding_id": "f-det-1", "layer_id": "qa-deterministic",
            "check_id": "check_anti_slop", "subject_ref": SUBJECT, "outcome": "PASS",
            "severity": "INFO", "evidence": {"artifact_sha256": SHA}}
    base.update(ov)
    return base


def _judge(**ov):
    base = {"finding_id": "f-judge-1", "layer_id": "qa-model-assisted",
            "check_id": "provider:aesthetic/laion", "subject_ref": SUBJECT,
            "outcome": "REVIEW_REQUIRED", "severity": "MINOR",
            "evidence": {"artifact_sha256": SHA},
            "recommendation": "composition reads as default; escalate to the human jury"}
    base.update(ov)
    return base


def _verdict(**ov):
    base = {"schemaVersion": "design-lab/assurance-jury-record/v2", "kind": "JURY_VERDICT",
            "jury_record_id": "j-1", "subject_ref": SUBJECT, "artifact_sha256": SHA,
            "juror": {"juror_id": "dtalex66", "kind": "HUMAN",
                       "attestation": "reviewed the exported poster at 100% on a calibrated display"},
            "criteria": [{"criterion_id": "anti-slop", "weight": 1.0, "score": 4.0, "note": None}],
            "verdict": "APPROVE", "decided_at": "2026-09-23T10:00:00Z",
            "supersedes": None, "evidence_refs": []}
    base.update(ov)
    return base


def main() -> int:
    errors: list[str] = []

    # 0. the schema itself is a valid, closed, three-field document
    schema = quality_record.schema()
    required = set(schema.get("required", ()))
    for field in ("deterministic", "automated_judge", "human_jury", "final_gate", "artifact_sha256"):
        if field not in required:
            errors.append(f"schema does not require the {field!r} field")
    if schema.get("additionalProperties") is not False:
        errors.append("the record schema must be closed (additionalProperties false)")

    # 1. happy paths: the three reachable gate states
    r_needs = quality_record.record_quality_record(
        quality_record_id="g3-1", subject_ref=SUBJECT, artifact_sha256=SHA,
        deterministic=[_det()], automated_judge=[_judge()])
    if r_needs["final_gate"] != "NEEDS_HUMAN_VERDICT":
        errors.append(f"no-human record must be NEEDS_HUMAN_VERDICT, got {r_needs['final_gate']!r}")

    r_pass = quality_record.record_quality_record(
        quality_record_id="g3-2", subject_ref=SUBJECT, artifact_sha256=SHA,
        deterministic=[_det()], automated_judge=[_judge()], human_verdict=_verdict())
    if r_pass["final_gate"] != "PASS":
        errors.append(f"signed-APPROVE record must be PASS, got {r_pass['final_gate']!r}")

    r_rej = quality_record.record_quality_record(
        quality_record_id="g3-3", subject_ref=SUBJECT, artifact_sha256=SHA,
        deterministic=[_det()],
        human_verdict=_verdict(verdict="REJECT",
                               evidence_refs=["reports/current/qa-summary.json"]))
    if r_rej["final_gate"] != "BLOCKED":
        errors.append(f"signed-REJECT record must be BLOCKED, got {r_rej['final_gate']!r}")

    # a deterministic HARD_BLOCK outranks a human APPROVE
    r_block = quality_record.record_quality_record(
        quality_record_id="g3-4", subject_ref=SUBJECT, artifact_sha256=SHA,
        deterministic=[_det(outcome="HARD_BLOCK", severity="BLOCKER", finding_id="f-block")],
        human_verdict=_verdict())
    if r_block["final_gate"] != "BLOCKED":
        errors.append(f"a deterministic HARD_BLOCK must outrank APPROVE, got {r_block['final_gate']!r}")

    # round-trip: a valid record re-validates through the frozen policy
    for record in (r_needs, r_pass, r_rej, r_block):
        try:
            quality_record.validate_quality_record(json.loads(json.dumps(record)))
        except AssuranceError as exc:
            errors.append(f"valid record {record['quality_record_id']} re-validation failed: {exc}")

    # 2. the guarantees that keep an automated judge out of the gate
    adversarial = {
        "an agent-signed human field": lambda: quality_record.record_quality_record(
            quality_record_id="g3-x", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[_det()],
            human_verdict=_verdict(juror={"juror_id": "auto", "kind": "MODEL",
                                            "attestation": "model self-score"})),
        "a proposal re-tagged as a verdict": lambda: quality_record.record_quality_record(
            quality_record_id="g3-x", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[_det()],
            human_verdict=(lambda p: dict(p, kind="JURY_VERDICT"))(
                human_jury.agent_may_propose(
                    proposal_id="p-1", subject_ref=SUBJECT, artifact_sha256=SHA,
                    proposer="design-lab/agent/critique",
                    criteria=(human_jury.Criterion(criterion_id="a", weight=1.0, score=4.0),),
                    suggested_verdict="APPROVE", rationale="r",
                    created_at="2026-09-23T10:00:00Z").as_dict())),
        "a model finding misplaced in the deterministic field": lambda: quality_record.record_quality_record(
            quality_record_id="g3-x", subject_ref=SUBJECT, artifact_sha256=SHA,
            deterministic=[_judge()]),
        "an automated judge supplying the gate": lambda: quality_record.validate_quality_record(
            (lambda rec: dict(rec, final_gate="PASS"))(
                quality_record.record_quality_record(
                    quality_record_id="g3-x", subject_ref=SUBJECT, artifact_sha256=SHA,
                    deterministic=[_det()]))),
    }
    for label, fire in adversarial.items():
        try:
            fire()
            errors.append(f"guarantee held {label!r} but the record was accepted")
        except AssuranceError:
            pass  # the correct outcome: the record was refused

    if errors:
        for e in errors:
            print(f"  {e}")
        print(f"VERIFY_QUALITY_RECORD=FAIL findings={len(errors)}")
        return 1
    print("VERIFY_QUALITY_RECORD=OK (schema closed, three gates reachable, "
          "automated judge excluded from the gate, adversarial records refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
