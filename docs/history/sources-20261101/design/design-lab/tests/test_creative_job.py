# SPDX-License-Identifier: MIT
"""DL-P0-020 CreativeJob: identity, deliverables, rights gate, idempotency."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import creative_job, store  # noqa: E402


def job(**overrides):
    document = {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-creative",
        "brief_ref": {"brief_id": "brief-1", "sha256": "sha256:" + "a" * 64},
        "rights_profile": {"profile_id": "rights-1", "gate_state": "CHECKED"},
        "deliverables": [
            {"deliverable_id": "poster", "asset_kind": "psd", "host_target": "photoshop-2025", "editable": True},
            {"deliverable_id": "export-png", "asset_kind": "raster", "host_target": "photoshop-2025", "editable": False},
        ],
        "host_targets": [
            {"host_id": "photoshop-2025", "host_version": "26.7.0.15", "adapter_id": "adobe-photoshop",
             "mode": "process-isolated", "editable_source": True, "evidence_level": "E0"},
        ],
    }
    document.update(overrides)
    return document


class CreativeJobTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-job-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'creative.db')
        self.addCleanup(self.conn.close)

    def test_create_and_reload_round_trip(self):
        result = creative_job.create_job(self.conn, job(), idempotency_scope="s", idempotency_key="k1")
        self.assertTrue(result["created"])
        stored = creative_job.load_job(self.conn, result["job_id"])
        self.assertEqual(stored["brief_ref"]["brief_id"], "brief-1")
        self.assertEqual(stored["spec_sha256"], result["spec_sha256"])
        self.assertEqual([d["deliverable_id"] for d in creative_job.deliverables(self.conn, result["job_id"])],
                         ["export-png", "poster"])
        self.assertEqual(creative_job.job_for_operation(self.conn, result["operation_id"]), result["job_id"])

    def test_same_key_same_content_is_idempotent(self):
        first = creative_job.create_job(self.conn, job(), idempotency_scope="s", idempotency_key="k1")
        second = creative_job.create_job(self.conn, job(), idempotency_scope="s", idempotency_key="k1")
        self.assertFalse(second["created"])
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM creative_job").fetchone()[0], 1)

    def test_same_key_different_content_fails_closed(self):
        creative_job.create_job(self.conn, job(), idempotency_scope="s", idempotency_key="k1")
        with self.assertRaises(store.CreativeError):
            creative_job.create_job(self.conn, job(constraints={"note": "changed"}),
                                    idempotency_scope="s", idempotency_key="k1")

    def test_blocked_rights_profile_cannot_start(self):
        document = job(rights_profile={"profile_id": "rights-blocked", "gate_state": "BLOCKED"})
        with self.assertRaisesRegex(store.CreativeError, "rights profile is BLOCKED"):
            creative_job.validate_job(document)

    def test_rejected_direction_cannot_start(self):
        document = job(direction_ref={"direction_id": "dir-1", "sha256": "sha256:" + "b" * 64,
                                      "gate_state": "REJECTED"})
        with self.assertRaisesRegex(store.CreativeError, "direction gate REJECTED"):
            creative_job.validate_job(document)

    def test_undeclared_host_target_is_refused(self):
        document = job(deliverables=[{"deliverable_id": "x", "asset_kind": "psd",
                                      "host_target": "illustrator-2025", "editable": False}])
        with self.assertRaisesRegex(store.CreativeError, "undeclared host target"):
            creative_job.validate_job(document)

    def test_editable_deliverable_requires_editable_source_host(self):
        document = job(host_targets=[{"host_id": "photoshop-2025", "mode": "none",
                                      "editable_source": False, "evidence_level": "E0"}])
        with self.assertRaisesRegex(store.CreativeError, "editable deliverable requires an editable source host"):
            creative_job.validate_job(document)

    def test_duplicate_deliverable_id_is_refused(self):
        document = job(deliverables=[
            {"deliverable_id": "same", "asset_kind": "psd", "host_target": "photoshop-2025", "editable": False},
            {"deliverable_id": "same", "asset_kind": "raster", "host_target": "photoshop-2025", "editable": False},
        ])
        with self.assertRaisesRegex(store.CreativeError, "duplicate deliverable_id"):
            creative_job.validate_job(document)

    def test_schema_violation_reports_a_path(self):
        document = job(deliverables=[{"deliverable_id": "x", "asset_kind": "nope",
                                      "host_target": "photoshop-2025", "editable": False}])
        with self.assertRaisesRegex(store.CreativeError, "schema violation"):
            creative_job.validate_job(document)

    def test_validation_does_not_mutate_the_caller_document(self):
        document = job()
        snapshot = copy.deepcopy(document)
        creative_job.validate_job(document)
        self.assertEqual(document, snapshot)

    def test_readiness_separates_structural_from_host_verified(self):
        structural = creative_job.delivery_readiness(job())
        self.assertEqual(structural["job"], "NOT_HOST_VERIFIED")
        verified = creative_job.delivery_readiness(job(host_targets=[
            {"host_id": "photoshop-2025", "mode": "process-isolated", "editable_source": True,
             "evidence_level": "E2"}]))
        self.assertEqual(verified["job"], "DELIVERY_CANDIDATE")
        self.assertEqual(verified["host_verified_targets"], ["photoshop-2025"])

    def test_stored_spec_hash_is_verified_on_load(self):
        result = creative_job.create_job(self.conn, job(), idempotency_scope="s", idempotency_key="k1")
        self.conn.execute("UPDATE creative_job SET spec_json=? WHERE job_id=?",
                          ('{"schemaVersion":"design-lab/creative-job/v1"}', result["job_id"]))
        self.conn.commit()
        with self.assertRaisesRegex(store.CreativeError, "does not match its recorded hash"):
            creative_job.load_job(self.conn, result["job_id"])


if __name__ == "__main__":
    unittest.main()
