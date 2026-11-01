# SPDX-License-Identifier: MIT
"""DL-P0-021 Operation lineage: single producer, acyclic impact, provenance."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import asset_versions, creative_job, lineage, store  # noqa: E402


def brief(**overrides):
    document = {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-lineage",
        "brief_ref": {"brief_id": "brief-lin", "sha256": "sha256:" + "a" * 64},
        "rights_profile": {"profile_id": "rights-1", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E2"}],
    }
    document.update(overrides)
    return document


class LineageTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-lineage-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'creative.db')
        self.addCleanup(self.conn.close)
        created = creative_job.create_job(self.conn, brief(), idempotency_scope="s", idempotency_key="job")
        self.job_id = created["job_id"]
        asset_versions.register_asset_for_job(self.conn, self.job_id, "poster", "psd")
        self.v1 = self._version("1")
        self.op_generate = self._operation("op-generate")
        self.op_composite = self._operation("op-composite")

    def _version(self, digit):
        result = asset_versions.create_version(
            self.conn, "poster", "sha256:" + digit * 64,
            artifacts=[(f"v{digit}.psd", "sha256:" + digit * 64, 128, "deliverable")])
        return result["version_id"]

    def _operation(self, name):
        """Register an operation intent; lineage never invents an operation id."""
        with store.transaction(self.conn):
            operation_id, _ = store.record_intent(self.conn, scope="lineage-tests", key=name,
                                                  document={"operation": name})
        return operation_id

    def _chain(self):
        self.v2 = self._version("2")
        lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self.op_generate,
                                 provider_id="comfyui", model_id="sdxl", params={"steps": 30},
                                 inputs=[(self.v1, "reference")], outputs=[(self.v2, "output")])
        self.v3 = self._version("3")
        lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self.op_composite,
                                 provider_id="photoshop", params={"layer": "bg"},
                                 inputs=[(self.v2, "base")], outputs=[(self.v3, "composite")])

    def test_records_inputs_outputs_and_params_digest(self):
        self._chain()
        recorded = lineage.lineage(self.conn, self.op_generate)
        self.assertEqual(recorded["provider_id"], "comfyui")
        self.assertEqual(recorded["params_sha256"], lineage.params_digest({"steps": 30}))
        self.assertEqual(recorded["inputs"], [{"version_id": self.v1, "role": "reference"}])
        self.assertEqual(recorded["outputs"], [{"version_id": self.v2, "role": "output"}])

    def test_replay_of_identical_operation_is_idempotent(self):
        self._chain()
        again = lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self.op_composite,
                                         provider_id="photoshop", params={"layer": "bg"},
                                         inputs=[(self.v2, "base")], outputs=[(self.v3, "composite")])
        self.assertFalse(again["created"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM operation_lineage").fetchone()[0], 2)

    def test_changed_replay_of_an_operation_is_refused(self):
        self._chain()
        with self.assertRaisesRegex(store.CreativeError, "immutable"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self.op_composite,
                                     provider_id="illustrator", params={"layer": "bg"},
                                     inputs=[(self.v2, "base")], outputs=[(self.v3, "composite")])

    def test_a_version_has_exactly_one_producer(self):
        self._chain()
        with self.assertRaisesRegex(store.CreativeError, "producing operation"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self._operation("duplicate"),
                                     provider_id="comfyui", inputs=[], outputs=[(self.v3, "output")])

    def test_unknown_operation_is_refused_before_writing(self):
        with self.assertRaisesRegex(store.CreativeError, "register the operation intent"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id="op-not-registered",
                                     provider_id="comfyui", inputs=[], outputs=[(self.v1, "output")])

    def test_unknown_version_is_refused_before_writing(self):
        with self.assertRaisesRegex(store.CreativeError, "unknown asset version"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self._operation("bad-version"),
                                     provider_id="comfyui", inputs=[("v-missing", "input")],
                                     outputs=[(self.v1, "output")])

    def test_operation_without_output_is_refused(self):
        with self.assertRaisesRegex(store.CreativeError, "at least one output"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self._operation("no-output"),
                                     provider_id="comfyui", inputs=[(self.v1, "input")], outputs=[])

    def test_ancestors_descendants_and_impact_set(self):
        self._chain()
        self.assertEqual(lineage.ancestors(self.conn, self.v3), sorted([self.v1, self.v2]))
        self.assertEqual(lineage.descendants(self.conn, self.v1), sorted([self.v2, self.v3]))
        self.assertEqual(lineage.impacted_outputs(self.conn, [self.v2]), [self.v3])
        self.assertEqual(lineage.impacted_outputs(self.conn, [self.v3]), [])

    def test_explain_version_reports_an_unrecorded_root(self):
        self._chain()
        explanation = lineage.explain_version(self.conn, self.v3)
        origins = {node["version_id"]: node["origin"] for node in explanation["chain"]}
        self.assertEqual(origins[self.v3], "RECORDED")
        self.assertEqual(origins[self.v2], "RECORDED")
        self.assertEqual(origins[self.v1], "ROOT_OR_UNRECORDED")
        self.assertFalse(explanation["complete"])

    def test_producer_of_unknown_version_fails_closed(self):
        with self.assertRaisesRegex(store.CreativeError, "no recorded producer"):
            lineage.producer_of(self.conn, self.v1)

    def test_acyclic_check_and_job_graph(self):
        self._chain()
        self.assertEqual(lineage.verify_acyclic(self.conn), 3)
        graph = lineage.job_graph(self.conn, self.job_id)
        self.assertTrue(graph["acyclic"])
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(sorted((edge["from_version"], edge["to_version"]) for edge in graph["edges"]),
                         sorted([(self.v1, self.v2), (self.v2, self.v3)]))

    def test_duplicate_link_in_one_operation_is_refused(self):
        with self.assertRaisesRegex(store.CreativeError, "duplicate input link"):
            lineage.record_operation(self.conn, job_id=self.job_id, operation_id=self._operation("dup-link"),
                                     provider_id="comfyui",
                                     inputs=[(self.v1, "input"), (self.v1, "input")],
                                     outputs=[(self.v1, "output")])


if __name__ == "__main__":
    unittest.main()
