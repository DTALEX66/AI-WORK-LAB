# SPDX-License-Identifier: MIT
"""DL-P0-070: host matrix contract, inventory cross-check, and gap accounting.

Everything asserted here is E1 STRUCTURAL, except the cross-check against the
recorded machine inventory (reports/current/MACHINE_INVENTORY.json), which is a
machine fact already recorded in this repository. No host is launched or queried.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class HostMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from design_lab.readiness import host_matrix

        cls.host_matrix = host_matrix
        cls.matrix = host_matrix.load_matrix()
        cls.inventory = json.loads(
            (ROOT / "reports/current/MACHINE_INVENTORY.json").read_text(encoding="utf-8"))
        cls.by_name = {row["name"]: row for row in cls.inventory["software"]}

    def entry(self, host_id, host_version):
        for entry in self.matrix["entries"]:
            if entry["host_id"] == host_id and entry["host_version"] == host_version:
                return entry
        self.fail(f"missing matrix entry {host_id}@{host_version}")

    def mutated(self):
        """A deep copy of the loaded matrix, safe to break in place."""
        return copy.deepcopy(self.matrix)

    def assert_invalid(self, document, fragment):
        with self.assertRaises(self.host_matrix.ReadinessError) as caught:
            self.host_matrix.validate_matrix(document)
        self.assertIn(fragment, str(caught.exception))

    # -- repository document -------------------------------------------
    def test_repository_matrix_loads_and_matches_schema(self):
        self.assertEqual(self.matrix["task_id"], "DL-P0-070")
        self.assertEqual(self.matrix["schema_version"], "design-lab/readiness-host-matrix/v1")
        for entry in self.matrix["entries"]:
            self.assertIn(entry["verification"]["state"], self.host_matrix.VERIFICATION_STATES)
            for api in entry["apis"]:
                self.assertIn(api["kind"], self.host_matrix.API_KINDS)

    def test_presence_matches_the_recorded_inventory(self):
        """The only facts here that are not E1 are these recorded inventory rows."""
        for entry in self.matrix["entries"]:
            recorded = self.by_name[entry["inventory_name"]]
            expected = recorded["presence"] == "PRESENT"
            self.assertEqual(entry["present"], expected,
                             f"{entry['inventory_name']} presence disagrees with the recorded inventory")
            if expected and recorded.get("version"):
                self.assertEqual(entry["host_version"], recorded["version"])
        self.assertEqual(self.matrix["inventory_observed_at"], self.inventory["observed_at"])
        self.assertEqual(self.matrix["inventory_ref"], "reports/current/MACHINE_INVENTORY.json")

    def test_every_verified_flag_is_false_and_every_state_is_not_verified(self):
        for entry in self.matrix["entries"]:
            for api in entry["apis"]:
                self.assertFalse(api["verified"], f"{entry['host_id']}: {api['api_id']} claims verification")
            self.assertEqual(entry["verification"]["state"], "NOT_VERIFIED")
            self.assertIsNone(entry["verification"]["evidence_ref"])
            self.assertIsNone(entry["verification"]["at"])

    def test_no_entry_stores_an_absolute_path_alias(self):
        for entry in self.matrix["entries"]:
            alias = entry["install_alias"]
            for forbidden in ("/", "\\", ":", "C:", "D:"):
                self.assertNotIn(forbidden, alias)

    def test_summary_reports_no_live_evidence(self):
        summary = self.host_matrix.summary(self.matrix)
        self.assertEqual(summary["live_host_evidence"], "NONE_RECORDED")
        self.assertEqual(summary["apis_verified"], 0)
        self.assertEqual(summary["hosts_live_verified"], 0)
        self.assertEqual(summary["hosts_total"], len(self.matrix["entries"]))

    # -- rules ----------------------------------------------------------
    def test_verified_api_without_live_state_is_rejected(self):
        document = self.mutated()
        entry = document["entries"][0]
        entry["apis"][0]["verified"] = True
        entry["apis"][0]["evidence_level"] = "E3"
        self.assert_invalid(document, "require verification.state == VERIFIED_LIVE")

    def test_live_state_without_evidence_ref_is_rejected(self):
        document = self.mutated()
        entry = document["entries"][0]
        entry["verification"].update(state="VERIFIED_LIVE", by="synthetic-reviewer", at="2026-01-01")
        self.assert_invalid(document, "VERIFIED_LIVE requires a non-empty verification.evidence_ref")

    def test_absent_host_may_not_declare_a_verified_api(self):
        document = self.mutated()
        entry = next(item for item in document["entries"] if not item["present"])
        for api in entry["apis"]:
            api["verified"] = True
            api["evidence_level"] = "E3"
        entry["verification"].update(state="VERIFIED_LIVE", by="synthetic-reviewer",
                                      at="2026-01-01", evidence_ref="synthetic/evidence.json")
        self.assert_invalid(document, "may not declare a verified API")

    def test_editable_delivery_requires_a_delivery_api_and_readback(self):
        document = self.mutated()
        entry = document["entries"][0]
        entry["apis"] = [{"api_id": "photoshop-cli-batch", "kind": "CLI", "declared": True,
                          "verified": False, "evidence_level": "E1",
                          "note": "synthetic non-delivery surface"}]
        self.assert_invalid(document, "editable_delivery requires a declared")

        document = self.mutated()
        entry = document["entries"][0]
        entry["apis"] = [dict(api, declared=False) for api in entry["apis"]]
        self.assert_invalid(document, "editable_delivery requires a declared")

        document = self.mutated()
        document["entries"][0]["readback_method"] = None
        self.assert_invalid(document, "editable_delivery requires a readback_method")

    def test_presence_basis_is_required_by_schema(self):
        document = self.mutated()
        del document["entries"][0]["presence_basis"]
        self.assert_invalid(document, "schema violation")

    def test_duplicate_host_version_is_rejected(self):
        document = self.mutated()
        document["entries"].append(copy.deepcopy(document["entries"][0]))
        self.assert_invalid(document, "duplicate host entry")

    def test_entry_without_evidence_refs_is_rejected(self):
        document = self.mutated()
        document["entries"][0]["evidence_refs"] = []
        self.assert_invalid(document, "schema violation")

    # -- gap accounting --------------------------------------------------
    def test_capability_gap_lists_declared_but_unverified_apis(self):
        gaps = self.host_matrix.capability_gap(self.matrix)
        self.assertEqual(len(gaps), len(self.matrix["entries"]))
        by_host = {(gap["host_id"], gap["host_version"]): gap for gap in gaps}
        photoshop = by_host[("adobe-photoshop", "26.7.0.15")]
        self.assertTrue(photoshop["unverified_apis"])
        self.assertTrue(all(api["api_id"] for api in photoshop["unverified_apis"]))
        self.assertIn("editable delivery via", photoshop["unproven"])
        self.assertIn("PSD", photoshop["unproven"])
        premiere = by_host[("adobe-premiere-pro", "2025")]
        self.assertEqual(premiere["unproven"], "no editable delivery claimed for this host")
        self.assertIn("NOT_VERIFIED", premiere["evidence_gap"])

    def test_load_matrix_refuses_a_missing_file(self):
        with self.assertRaises(self.host_matrix.ReadinessError) as caught:
            self.host_matrix.load_matrix(ROOT / "design-lab/readiness/nonexistent-matrix.json")
        self.assertIn("unreadable", str(caught.exception))

    def test_load_document_refuses_malformed_and_duplicate_key_json(self):
        import tempfile

        parent = ROOT / ".project-local/task-runtime/readiness-host-matrix-tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as name:
            broken = Path(name) / "broken.json"
            broken.write_text('{"schema_version": "x",}', encoding="utf-8")
            with self.assertRaises(self.host_matrix.ReadinessError) as caught:
                self.host_matrix.load_document(broken)
            self.assertIn("invalid JSON", str(caught.exception))
            duplicate = Path(name) / "duplicate.json"
            duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaises(self.host_matrix.ReadinessError) as caught:
                self.host_matrix.load_document(duplicate)
            self.assertIn("duplicate JSON key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
