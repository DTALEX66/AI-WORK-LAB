# SPDX-License-Identifier: MIT
"""DLDS-F030 / DLDS-F040: shared lineage shape and the approval contract."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import (  # noqa: E402
    approval, asset_versions, creative_job, decision_ledger, lineage, lineage_view,
    requirement_ledger, store, version_guard,
)

ARTIFACT = "sha256:" + "b" * 64
READBACK = "sha256:" + "c" * 64


def brief():
    return {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-f030",
        "brief_ref": {"brief_id": "brief-f030", "sha256": "sha256:" + "a" * 64},
        "direction_ref": {"direction_id": "dir-f030", "sha256": "sha256:" + "d" * 64,
                          "gate_state": "APPROVED"},
        "rights_profile": {"profile_id": "rights-f030", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E2"}],
    }


class LineageShapeTests(unittest.TestCase):
    """DLDS-F030: five kinds, one shape, nine facts."""

    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/f030-f040-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'state.db')
        self.addCleanup(self.conn.close)
        self.job_id = creative_job.create_job(self.conn, brief(), idempotency_scope="f030",
                                              idempotency_key="job")["job_id"]
        asset_versions.register_asset_for_job(self.conn, self.job_id, "poster", "psd")
        self.root_version = asset_versions.create_version(
            self.conn, "poster", "sha256:" + "1" * 64,
            artifacts=[("root.psd", "sha256:" + "1" * 64, 128, "deliverable")])
        self.child_version = asset_versions.create_version(
            self.conn, "poster", "sha256:" + "2" * 64,
            artifacts=[("child.psd", "sha256:" + "2" * 64, 256, "deliverable")],
            parent_version_id=self.root_version["version_id"])
        with store.transaction(self.conn):
            operation_id, _ = store.record_intent(self.conn, scope="f030", key="op",
                                                  document={"op": "generate"})
        self.operation_id = operation_id
        lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self.operation_id,
                                 provider_id="comfyui", params={"steps": 20},
                                 inputs=[(self.root_version["version_id"], "reference")],
                                 outputs=[(self.child_version["version_id"], "output")])
        self.attempt_id = "att-" + "0" * 32

    def test_every_kind_exposes_the_same_nine_facts(self):
        kinds = {
            "job": self.job_id,
            "operation": self.operation_id,
            "asset": "poster",
            "version": self.child_version["version_id"],
        }
        for kind, identity in kinds.items():
            with self.subTest(kind=kind):
                node = lineage_view.node(self.conn, kind, identity)
                self.assertEqual(set(lineage_view.FIELDS) <= set(node), True,
                                 f"{kind} is missing {set(lineage_view.FIELDS) - set(node)}")
                self.assertEqual(node["kind"], kind)
                self.assertTrue(node["rollback"])
                self.assertTrue(node["state_source"])

    def test_job_state_is_derived_not_invented(self):
        node = lineage_view.node(self.conn, "job", self.job_id)
        self.assertEqual(node["state"], "NOT_DISPATCHED")
        self.assertIn("operation_state", node["state_source"])
        self.assertEqual(node["parent"], "p-f030")
        self.assertEqual([item["kind"] for item in node["inputs"]], ["brief", "direction"])
        self.assertEqual([item["deliverable_id"] for item in node["outputs"]], ["poster"])

    def test_version_node_carries_parent_inputs_outputs_and_evidence(self):
        node = lineage_view.node(self.conn, "version", self.child_version["version_id"])
        self.assertEqual(node["parent"], self.root_version["version_id"])
        self.assertEqual([item["version_id"] for item in node["inputs"]],
                         [self.root_version["version_id"]])
        self.assertEqual([item["path"] for item in node["outputs"]], ["child.psd"])
        self.assertEqual(node["evidence"]["operation_id"], self.operation_id)
        self.assertEqual(node["state"], "SERVABLE")

    def test_rejected_version_state_overrides_the_row_state(self):
        version_guard.reject_version(self.conn, self.child_version["version_id"], reason="off-brand",
                                     actor="DTALEX66", evidence_ref="review")
        node = lineage_view.node(self.conn, "version", self.child_version["version_id"])
        self.assertEqual(node["state"], "REJECTED")
        self.assertIn("rejection", node["state_source"])

    def test_asset_node_lists_versions_and_reports_absence(self):
        node = lineage_view.node(self.conn, "asset", "poster")
        self.assertEqual(len(node["outputs"]), 2)
        self.assertEqual(node["state"], "ACTIVE")
        asset_versions.register_asset_for_job(self.conn, self.job_id, "logo", "vector")
        empty = lineage_view.node(self.conn, "asset", "logo")
        self.assertEqual(empty["state"], "NO_VERSION")

    def test_attempt_node_is_reported_when_present_and_refused_when_absent(self):
        with self.assertRaisesRegex(store.CreativeError, "unknown"):
            lineage_view.node(self.conn, "attempt", self.attempt_id)
        self.conn.execute("INSERT INTO job (job_id, operation_id, schemaVersion) VALUES (?,?,?)",
                          ("job-f030", self.operation_id, "design-lab/job-spec/v2"))
        self.conn.execute("INSERT INTO attempt_state (attempt_id, job_id, attempt_no, state, started_at) "
                          "VALUES (?,?,?,?,?)", (self.attempt_id, "job-f030", 1, "RUNNING", "now"))
        self.conn.commit()
        node = lineage_view.node(self.conn, "attempt", self.attempt_id)
        self.assertEqual(node["state"], "RUNNING")
        self.assertEqual(node["parent"], "job-f030")

    def test_unknown_kind_and_unknown_identity_fail_closed(self):
        with self.assertRaisesRegex(store.CreativeError, "unknown lineage kind"):
            lineage_view.node(self.conn, "brief", "x")
        with self.assertRaisesRegex(store.CreativeError, "unknown"):
            lineage_view.node(self.conn, "job", "no-such-job")

    def test_explain_is_a_single_line(self):
        line = lineage_view.explain(self.conn, "version", self.child_version["version_id"])
        self.assertNotIn("\n", line)
        self.assertIn("version", line)


class ApprovalContractTests(unittest.TestCase):
    """DLDS-F040: approvals are gate decisions, projected, never a second ledger."""

    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/f030-f040-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'state.db')
        self.addCleanup(self.conn.close)
        self.job_id = creative_job.create_job(self.conn, brief(), idempotency_scope="f040",
                                              idempotency_key="job")["job_id"]

    def test_an_untouched_gate_reports_not_reviewed_and_still_blocks(self):
        status = approval.approval_status(self.conn, job_id=self.job_id, gate="RIGHTS")
        # Nobody has been asked, so the honest word is NOT_REVIEWED. Reading it as
        # PENDING would tell a delivery check that a review is in progress.
        self.assertEqual(status["state"], "NOT_REVIEWED")
        self.assertFalse(status["granted"])
        with self.assertRaisesRegex(store.CreativeError, "must grant it"):
            approval.require_approval(self.conn, job_id=self.job_id, gate="RIGHTS")
        self.assertIn("RIGHTS", approval.pending_approvals(self.conn, self.job_id))

    def test_asking_a_gate_is_what_makes_it_pending(self):
        """PENDING is reserved for a request that exists and awaits a human."""
        asked = approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS",
                                          actor="agent-r5", actor_kind="agent")
        self.assertEqual(asked["state"], "PENDING")
        self.assertFalse(asked["granted"])
        with self.assertRaisesRegex(store.CreativeError, "must grant it"):
            approval.require_approval(self.conn, job_id=self.job_id, gate="RIGHTS")

    def test_the_gate_inventory_names_untouched_gates_as_not_reviewed(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS",
                                  actor="agent-r5", actor_kind="agent")
        inventory = approval.gate_inventory(self.conn, self.job_id)
        self.assertEqual(inventory["gates"]["RIGHTS"], "PENDING")
        untouched = [gate for gate in approval.HUMAN_ONLY if gate != "RIGHTS"]
        self.assertTrue(untouched, "the inventory needs more than one gate to be worth reading")
        for gate in untouched:
            self.assertEqual(inventory["gates"][gate], "NOT_REVIEWED",
                             f'{gate} was never asked; it may not read as anything else')
        self.assertEqual(set(inventory["open_gates"]), set(approval.HUMAN_ONLY))
        self.assertEqual(inventory["granted"], [])

    def test_an_agent_can_ask_but_never_grant(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS",
                                  actor="agent-r5", actor_kind="agent")
        with self.assertRaisesRegex(store.CreativeError, "requires a human"):
            approval.grant(self.conn, job_id=self.job_id, gate="RIGHTS", actor="agent-r5",
                           rationale="looks fine", actor_kind="agent")
        granted = approval.grant(self.conn, job_id=self.job_id, gate="RIGHTS", actor="DTALEX66",
                                 rationale="licence terms reviewed")
        self.assertEqual(granted["state"], "APPROVED")
        self.assertTrue(granted["granted"])
        self.assertEqual(approval.require_approval(self.conn, job_id=self.job_id,
                                                   gate="RIGHTS")["actor"], "DTALEX66")

    def test_refusal_is_a_state_not_a_silence(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="RELEASE", actor="agent-r5",
                                  actor_kind="agent")
        refused = approval.refuse(self.conn, job_id=self.job_id, gate="RELEASE", actor="DTALEX66",
                                  rationale="not released")
        self.assertEqual(refused["state"], "REJECTED")
        with self.assertRaisesRegex(store.CreativeError, "must grant it"):
            approval.require_approval(self.conn, job_id=self.job_id, gate="RELEASE")

    def test_revocation_keeps_the_grant_visible_in_history(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="QUALITY", actor="agent-r5",
                                  actor_kind="agent")
        approval.grant(self.conn, job_id=self.job_id, gate="QUALITY", actor="DTALEX66",
                       rationale="looks balanced")
        revoked = approval.revoke(self.conn, job_id=self.job_id, gate="QUALITY", actor="DTALEX66",
                                  rationale="contrast issue found later")
        self.assertEqual(revoked["state"], "REVERSED")
        kinds = [event["kind"] for event in
                 decision_ledger.history(self.conn, f"DEC-quality-{self.job_id}")]
        self.assertEqual(kinds, ["PROPOSED", "DECIDED", "REVERSED"])

    def test_granting_without_a_request_is_refused(self):
        with self.assertRaisesRegex(store.CreativeError, "never requested"):
            approval.grant(self.conn, job_id=self.job_id, gate="PRODUCTION", actor="DTALEX66",
                           rationale="out of order")

    def test_only_human_gates_are_approvable(self):
        with self.assertRaisesRegex(store.CreativeError, "not a human gate"):
            approval.approval_status(self.conn, job_id=self.job_id, gate="METHOD")

    def test_the_v1_approval_table_is_a_maintained_projection(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="DIRECTION", actor="agent-r5",
                                  actor_kind="agent")
        approval.grant(self.conn, job_id=self.job_id, gate="DIRECTION", actor="DTALEX66",
                       rationale="direction approved")
        rows = approval.projection(self.conn, self.job_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action_kind"], "gate:DIRECTION")
        self.assertEqual(rows[0]["state"], "APPROVED")
        self.assertIn("projection of decision_event", rows[0]["source"])
        # re-projection must update, not duplicate
        approval.sync_projection(self.conn, job_id=self.job_id, gate="DIRECTION")
        self.assertEqual(len(approval.projection(self.conn, self.job_id)), 1)

    def test_gate_inventory_lists_what_is_still_open(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS", actor="agent-r5",
                                  actor_kind="agent")
        approval.grant(self.conn, job_id=self.job_id, gate="RIGHTS", actor="DTALEX66",
                       rationale="reviewed")
        inventory = approval.gate_inventory(self.conn, self.job_id)
        self.assertEqual(inventory["granted"], ["RIGHTS"])
        self.assertEqual(inventory["open_gates"],
                         ["DIRECTION", "QUALITY", "PRODUCTION", "RELEASE"])
        self.assertEqual(set(approval.all_gates()) >= {"DIRECTION", "QUALITY", "RIGHTS",
                                                       "PRODUCTION", "RELEASE", "METHOD"}, True)

    def test_approval_history_is_the_decision_history(self):
        approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS", actor="agent-r5",
                                  actor_kind="agent")
        events = approval.history(self.conn, job_id=self.job_id, gate="RIGHTS")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["dec_id"], f"DEC-rights-{self.job_id}")

    def test_requirement_and_decision_ledgers_still_reject_writes_after_the_projection(self):
        requirement_ledger.define_requirement(self.conn, job_id=self.job_id, req_id="REQ-approval",
                                              statement="approval recorded", acceptance="state visible",
                                              actor="DTALEX66")
        approval.request_approval(self.conn, job_id=self.job_id, gate="RIGHTS", actor="agent-r5",
                                  actor_kind="agent")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM decision_event")
        self.conn.rollback()


if __name__ == "__main__":
    unittest.main()
