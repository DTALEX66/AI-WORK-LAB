# SPDX-License-Identifier: MIT
"""DL-P0-030 / DL-P0-031: requirement ledger and design decision ledger."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import creative_job, decision_ledger, requirement_ledger, store  # noqa: E402

ARTIFACT = "sha256:" + "b" * 64
READBACK = "sha256:" + "c" * 64


def brief():
    return {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-ledger",
        "brief_ref": {"brief_id": "brief-ledger", "sha256": "sha256:" + "a" * 64},
        "rights_profile": {"profile_id": "rights-1", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E2"}],
    }


class LedgerTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-ledger-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'creative.db')
        self.addCleanup(self.conn.close)
        created = creative_job.create_job(self.conn, brief(), idempotency_scope="s", idempotency_key="job")
        self.job_id = created["job_id"]

    def _requirement(self, req_id="REQ-bleed", priority="MUST"):
        return requirement_ledger.define_requirement(
            self.conn, job_id=self.job_id, req_id=req_id, statement="no ink bleed at trim",
            acceptance="measured bleed <= 1mm on the exported PDF", actor="DTALEX66", priority=priority)

    def test_definition_starts_open_and_is_unique(self):
        created = self._requirement()
        self.assertEqual(created["status"], "OPEN")
        with self.assertRaisesRegex(store.CreativeError, "already defined"):
            self._requirement()

    def test_requirement_id_must_be_namespaced(self):
        with self.assertRaisesRegex(store.CreativeError, "REQ-"):
            requirement_ledger.define_requirement(self.conn, job_id=self.job_id, req_id="bleed",
                                                  statement="x", acceptance="y", actor="a")

    def test_verification_requires_artifact_and_readback(self):
        self._requirement()
        with self.assertRaisesRegex(store.CreativeError, "evidence is incomplete"):
            requirement_ledger.verify(self.conn, req_id="REQ-bleed", evidence_ref="print-proof",
                                      artifact_sha256=ARTIFACT, readback_sha256=None, actor="DTALEX66")
        met = requirement_ledger.verify(self.conn, req_id="REQ-bleed", evidence_ref="print-proof",
                                        artifact_sha256=ARTIFACT, readback_sha256=READBACK, actor="DTALEX66")
        self.assertEqual(met["status"], "MET")
        self.assertEqual(requirement_ledger.coverage(self.conn, self.job_id)["gate"], "SATISFIED")

    def test_unmet_must_requirement_blocks_delivery(self):
        self._requirement()
        report = requirement_ledger.coverage(self.conn, self.job_id)
        self.assertEqual(report["unmet_must"], ["REQ-bleed"])
        self.assertEqual(report["gate"], "OPEN")
        with self.assertRaisesRegex(store.CreativeError, "block delivery"):
            requirement_ledger.gate(self.conn, self.job_id)

    def test_a_waiver_clears_the_gate_but_stays_visible(self):
        self._requirement()
        requirement_ledger.waive(self.conn, req_id="REQ-bleed", actor="DTALEX66",
                                 reason="printer confirmed the stock tolerance")
        report = requirement_ledger.gate(self.conn, self.job_id)
        self.assertEqual(report["waived"], ["REQ-bleed"])
        self.assertEqual(report["unmet_must"], [])
        with self.assertRaisesRegex(store.CreativeError, "reason"):
            requirement_ledger.waive(self.conn, req_id="REQ-bleed", actor="DTALEX66", reason=" ")

    def test_waived_requirement_cannot_be_verified_without_reopening(self):
        self._requirement()
        requirement_ledger.waive(self.conn, req_id="REQ-bleed", actor="DTALEX66", reason="accepted as is")
        with self.assertRaisesRegex(store.CreativeError, "cannot move"):
            requirement_ledger.verify(self.conn, req_id="REQ-bleed", evidence_ref="proof",
                                      artifact_sha256=ARTIFACT, readback_sha256=READBACK, actor="DTALEX66")
        reopened = requirement_ledger.reopen(self.conn, req_id="REQ-bleed", actor="DTALEX66",
                                             reason="printer changed stock")
        self.assertEqual(reopened["status"], "OPEN")

    def test_failed_requirement_blocks_delivery_even_when_optional(self):
        self._requirement("REQ-optional", priority="SHOULD")
        requirement_ledger.fail(self.conn, req_id="REQ-optional", evidence_ref="inspected",
                                actor="DTALEX66", note="edge sharpening visible")
        report = requirement_ledger.coverage(self.conn, self.job_id)
        self.assertEqual(report["failed"], ["REQ-optional"])
        with self.assertRaisesRegex(store.CreativeError, "failed/contradicted"):
            requirement_ledger.gate(self.conn, self.job_id)

    def test_history_is_append_only(self):
        self._requirement()
        requirement_ledger.verify(self.conn, req_id="REQ-bleed", evidence_ref="proof",
                                  artifact_sha256=ARTIFACT, readback_sha256=READBACK, actor="DTALEX66")
        kinds = [event["kind"] for event in requirement_ledger.history(self.conn, "REQ-bleed")]
        self.assertEqual(kinds, ["DEFINED", "VERIFIED"])
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM requirement_event WHERE req_id='REQ-bleed'")
        self.conn.rollback()

    def test_decision_records_options_choice_and_rationale(self):
        options = [{"option_id": "A", "summary": "tighten the grid", "tradeoffs": "less air"},
                   {"option_id": "B", "summary": "keep the grid"}]
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-grid", options=options,
                                actor="agent-r5", requirement_refs=[])
        decided = decision_ledger.decide(self.conn, dec_id="DEC-grid", chosen="B",
                                         rationale="brand grid is locked by the direction gate",
                                         actor="DTALEX66", actor_kind="human")
        self.assertEqual(decided["state"], "DECIDED")
        self.assertEqual(decided["chosen"], "B")
        self.assertEqual(len(decided["options"]), 2)

    def test_chosen_option_must_exist(self):
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-grid",
                                options=[{"option_id": "A", "summary": "tighten"}], actor="agent-r5")
        with self.assertRaisesRegex(store.CreativeError, "not one of the recorded options"):
            decision_ledger.decide(self.conn, dec_id="DEC-grid", chosen="Z", rationale="because",
                                   actor="DTALEX66", actor_kind="human")

    def test_agent_cannot_sign_a_human_gate(self):
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-rights",
                                options=[{"option_id": "APPROVE", "summary": "approve the model licence"},
                                         {"option_id": "BLOCK", "summary": "block until clarified"}],
                                actor="agent-r5", gate="RIGHTS")
        with self.assertRaisesRegex(store.CreativeError, "requires a human decision"):
            decision_ledger.decide(self.conn, dec_id="DEC-rights", chosen="APPROVE",
                                   rationale="looks fine", actor="agent-r5", actor_kind="agent")
        with self.assertRaisesRegex(store.CreativeError, "gate is unsigned"):
            decision_ledger.assert_gate(self.conn, self.job_id, "RIGHTS")
        decision_ledger.decide(self.conn, dec_id="DEC-rights", chosen="APPROVE",
                               rationale="licence and territory are verified", actor="DTALEX66",
                               actor_kind="human")
        self.assertEqual(decision_ledger.assert_gate(self.conn, self.job_id, "RIGHTS")["chosen"],
                         "APPROVE")

    def test_blocking_choice_does_not_satisfy_a_human_gate(self):
        decision_ledger.propose(
            self.conn, job_id=self.job_id, dec_id="DEC-rights-block",
            options=[{"option_id": "APPROVE", "summary": "approve"},
                     {"option_id": "BLOCK", "summary": "block"}],
            actor="agent-r5", gate="RIGHTS")
        decision_ledger.decide(
            self.conn, dec_id="DEC-rights-block", chosen="BLOCK",
            rationale="territory terms are unresolved", actor="DTALEX66", actor_kind="human")
        with self.assertRaisesRegex(store.CreativeError, "does not approve"):
            decision_ledger.assert_gate(self.conn, self.job_id, "RIGHTS")
        self.assertIn("RIGHTS", decision_ledger.open_gates(self.conn, self.job_id))

    def test_open_gates_lists_unsigned_human_gates(self):
        self.assertEqual(decision_ledger.open_gates(self.conn, self.job_id),
                         ["DIRECTION", "QUALITY", "RIGHTS", "PRODUCTION", "RELEASE"])

    def test_reversal_keeps_the_original_decision_visible(self):
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-type",
                                options=[{"option_id": "A", "summary": "condensed"}], actor="agent-r5")
        decision_ledger.decide(self.conn, dec_id="DEC-type", chosen="A", rationale="fits the format",
                               actor="DTALEX66", actor_kind="human")
        reversed_decision = decision_ledger.reverse(self.conn, dec_id="DEC-type",
                                                    rationale="legibility failed at 60mm", actor="DTALEX66")
        self.assertEqual(reversed_decision["state"], "REVERSED")
        self.assertEqual([event["kind"] for event in decision_ledger.history(self.conn, "DEC-type")],
                         ["PROPOSED", "DECIDED", "REVERSED"])

    def test_supersede_marks_the_previous_decision(self):
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-old",
                                options=[{"option_id": "A", "summary": "v1"}], actor="agent-r5")
        decision_ledger.decide(self.conn, dec_id="DEC-old", chosen="A", rationale="first pass",
                               actor="DTALEX66", actor_kind="human")
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-new",
                                options=[{"option_id": "B", "summary": "v2"}], actor="agent-r5",
                                supersedes="DEC-old")
        self.assertEqual(decision_ledger.decision(self.conn, "DEC-old")["state"], "SUPERSEDED")
        self.assertEqual(decision_ledger.decision(self.conn, "DEC-new")["state"], "PROPOSED")

    def test_supersede_cannot_cross_job_boundaries(self):
        other = creative_job.create_job(
            self.conn, brief(), idempotency_scope="s", idempotency_key="other-job")
        decision_ledger.propose(
            self.conn, job_id=self.job_id, dec_id="DEC-old",
            options=[{"option_id": "A", "summary": "v1"}], actor="agent-r5")
        with self.assertRaisesRegex(store.CreativeError, "same job"):
            decision_ledger.propose(
                self.conn, job_id=other["job_id"], dec_id="DEC-new",
                options=[{"option_id": "B", "summary": "v2"}], actor="agent-r5",
                supersedes="DEC-old")
        self.assertEqual(decision_ledger.decision(self.conn, "DEC-old")["state"], "PROPOSED")

    def test_agent_cannot_supersede_a_human_gate_decision(self):
        decision_ledger.propose(
            self.conn, job_id=self.job_id, dec_id="DEC-rights-old",
            options=[{"option_id": "APPROVE", "summary": "approve"}],
            actor="agent-r5", gate="RIGHTS")
        decision_ledger.decide(
            self.conn, dec_id="DEC-rights-old", chosen="APPROVE", rationale="licensed",
            actor="DTALEX66", actor_kind="human")
        with self.assertRaisesRegex(store.CreativeError, "human supersession"):
            decision_ledger.propose(
                self.conn, job_id=self.job_id, dec_id="DEC-rights-new",
                options=[{"option_id": "BLOCK", "summary": "block"}],
                actor="agent-r5", actor_kind="agent", gate="RIGHTS",
                supersedes="DEC-rights-old")
        self.assertEqual(decision_ledger.decision(self.conn, "DEC-rights-old")["state"], "DECIDED")

    def test_supersede_has_one_live_successor(self):
        decision_ledger.propose(
            self.conn, job_id=self.job_id, dec_id="DEC-old",
            options=[{"option_id": "A", "summary": "v1"}], actor="agent-r5")
        decision_ledger.propose(
            self.conn, job_id=self.job_id, dec_id="DEC-new-a",
            options=[{"option_id": "B", "summary": "v2"}], actor="agent-r5",
            supersedes="DEC-old")
        with self.assertRaisesRegex(store.CreativeError, "not active"):
            decision_ledger.propose(
                self.conn, job_id=self.job_id, dec_id="DEC-new-b",
                options=[{"option_id": "C", "summary": "v3"}], actor="agent-r5",
                supersedes="DEC-old")
        with self.assertRaisesRegex(store.CreativeError, "unknown decision"):
            decision_ledger.decision(self.conn, "DEC-new-b")

    def test_decision_can_reference_a_requirement(self):
        self._requirement()
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-bleed",
                                options=[{"option_id": "A", "summary": "increase the safe margin"}],
                                actor="agent-r5", requirement_refs=["REQ-bleed"])
        linked = decision_ledger.decisions_for_requirement(self.conn, "REQ-bleed")
        self.assertEqual([item["dec_id"] for item in linked], ["DEC-bleed"])
        with self.assertRaisesRegex(store.CreativeError, "REQ-"):
            decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-bad",
                                    options=[{"option_id": "A", "summary": "x"}], actor="agent-r5",
                                    requirement_refs=["bleed"])

    def test_decision_events_are_append_only(self):
        decision_ledger.propose(self.conn, job_id=self.job_id, dec_id="DEC-grid",
                                options=[{"option_id": "A", "summary": "x"}], actor="agent-r5")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE decision_event SET rationale='rewritten'")
        self.conn.rollback()


    def test_ledger_projects_into_the_delivery_receipt_contract(self):
        """The join between DL-P0-030 and DL-P0-161 is explicit, not guessed."""
        from design_lab.interop import delivery_receipt
        self._requirement("REQ-met")
        requirement_ledger.verify(self.conn, req_id="REQ-met", evidence_ref="proof",
                                  artifact_sha256=ARTIFACT, readback_sha256=READBACK, actor="DTALEX66")
        self._requirement("REQ-open", priority="SHOULD")
        self._requirement("REQ-dropped", priority="SHOULD")
        requirement_ledger.waive(self.conn, req_id="REQ-dropped", actor="DTALEX66",
                                 reason="printer confirmed tolerance")
        projected = requirement_ledger.delivery_requirements(self.conn, self.job_id)
        self.assertEqual(projected, [{"req_id": "REQ-dropped", "status": "SKIPPED_OPTIONAL"},
                                     {"req_id": "REQ-met", "status": "PASS"},
                                     {"req_id": "REQ-open", "status": "NOT_RUN"}])
        receipt = delivery_receipt.build_receipt({
            "job_id": self.job_id,
            "rollback": {"backup_ref": "backup-1", "procedure": "restore the previous active version"},
            "deliverables": [{"deliverable_id": "poster", "artifact_sha256": ARTIFACT, "byte_size": 10,
                              "editable": True, "provenance_sha256": "sha256:" + "d" * 64,
                              "requirements": projected}]})
        self.assertEqual(receipt["axes"]["delivery"], "PARTIAL")
        self.assertEqual([entry["status"] for entry in receipt["deliverables"][0]["requirements"]],
                         ["SKIPPED_OPTIONAL", "PASS", "NOT_RUN"])

    def test_receipt_projection_covers_every_ledger_status(self):
        self.assertEqual(set(requirement_ledger.RECEIPT_STATUS), set(requirement_ledger.STATUSES))


if __name__ == "__main__":
    unittest.main()
