# SPDX-License-Identifier: MIT
"""DL-P1-100: model radar contract, licence/hardware fail-closed rules, resolver.

E1 STRUCTURAL throughout, plus the reuse of recorded machine facts (the local H3
component set, the Whisper cache, and the 8151 MiB VRAM figure). Nothing here
downloads, hashes, loads, or runs a model.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class ModelRadarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from design_lab.readiness import model_radar

        cls.model_radar = model_radar
        cls.registry = model_radar.load_registry()
        cls.inventory = json.loads(
            (ROOT / "reports/current/MACHINE_INVENTORY.json").read_text(encoding="utf-8"))
        cls.assets = json.loads(
            (ROOT / "design-lab/config/external-assets-index.json").read_text(encoding="utf-8"))

    def entry(self, model_id):
        for entry in self.registry["entries"]:
            if entry["model_id"] == model_id:
                return entry
        self.fail(f"missing radar entry {model_id}")

    def mutated(self):
        return copy.deepcopy(self.registry)

    def assert_invalid(self, document, fragment):
        with self.assertRaises(self.model_radar.ReadinessError) as caught:
            self.model_radar.validate_registry(document)
        self.assertIn(fragment, str(caught.exception))

    def assert_refused(self, model_id, code):
        with self.assertRaises(self.model_radar.ReadinessError) as caught:
            self.model_radar.resolve(self.registry, model_id)
        self.assertIn(code, str(caught.exception))
        return str(caught.exception)

    # -- repository registry ---------------------------------------------
    def test_registry_loads_and_covers_the_required_families(self):
        self.assertEqual(self.registry["task_id"], "DL-P1-100")
        families = {entry["family"] for entry in self.registry["entries"]}
        for required in ("image-generation", "video-generation", "upscaling", "segmentation",
                         "ocr", "asr", "tts", "3d"):
            self.assertIn(required, families)

    def test_machine_states_reuse_the_model_manifest_vocabulary(self):
        from design_lab.analysis.model_manifest import STAGES

        self.assertEqual(self.model_radar.MACHINE_STATES, STAGES)
        for entry in self.registry["entries"]:
            self.assertIn(entry["machine_state"], STAGES)

    def test_vram_ceiling_is_the_recorded_inventory_figure(self):
        self.assertEqual(self.registry["hardware"]["available_vram_mib"], 8151)
        self.assertIn("8151", self.inventory["host"]["gpu_note"])
        self.assertIn("5060", self.registry["hardware"]["gpu"])

    def test_local_h3_entries_are_license_blocked_and_use_the_existing_asset_index(self):
        index_ids = {asset["id"] for asset in self.assets["assets"]}
        inventory_paths = {model["path"].replace("\\", "/") for model in self.inventory["models"]}
        blocked = [entry for entry in self.registry["entries"]
                   if entry["radar_state"] == "BLOCKED_BY_LICENSE"]
        self.assertEqual(len(blocked), 4)
        for entry in blocked:
            self.assertTrue(entry["model_id"].startswith("minimax-h3-"))
            self.assertFalse(entry["default_enabled"])
            self.assertEqual(entry["rights"]["commercial_use"], "UNKNOWN")
            self.assertIn("owner", entry["blocking_reason"])
            self.assertTrue(set(entry["asset_index_ids"]) <= index_ids)
            suffix = entry["local_path"].split("ComfyUI/", 1)[1]
            self.assertTrue(any(path.endswith(suffix) for path in inventory_paths),
                            f"{entry['model_id']} is not one of the recorded local model files")
        self.assertEqual(self.registry["external_assets_ref"],
                         "design-lab/config/external-assets-index.json")

    def test_whisper_cache_is_registered_without_claiming_a_qualified_stage(self):
        entry = self.entry("whisper-large-v3-turbo")
        self.assertEqual(entry["family"], "asr")
        self.assertFalse(entry["default_enabled"])
        self.assertEqual(entry["machine_state"], "METADATA_ONLY")
        self.assertEqual(entry["weights_sha256"], [])
        self.assertIn("whisper/faster-whisper-large-v3-turbo", entry["local_path"])

    def test_every_entry_has_a_local_reference_or_is_explicitly_absent(self):
        for entry in self.registry["entries"]:
            if entry["machine_state"] == "ABSENT":
                self.assertIsNone(entry["local_path"])
            else:
                self.assertTrue(entry["local_path"])

    # -- rules ------------------------------------------------------------
    def test_default_enabled_outside_qualified_local_is_rejected(self):
        document = self.mutated()
        document["entries"][0]["default_enabled"] = True
        self.assert_invalid(document, "default_enabled requires radar_state")

    def test_qualified_local_requires_load_verified_and_a_nonzero_hash(self):
        document = self.mutated()
        candidate = next(entry for entry in document["entries"]
                         if entry["family"] == "segmentation" and entry["machine_state"] == "ABSENT")
        candidate.update(radar_state="QUALIFIED_LOCAL", machine_state="WEIGHTS_COMPLETE",
                         default_enabled=True, qualified_by="synthetic-reviewer", local_path="synthetic/model")
        self.assert_invalid(document, "requires machine_state >= LOAD_VERIFIED")

        document = self.mutated()
        candidate = next(entry for entry in document["entries"]
                         if entry["family"] == "segmentation" and entry["machine_state"] == "ABSENT")
        candidate.update(radar_state="QUALIFIED_LOCAL", machine_state="LOAD_VERIFIED",
                         default_enabled=True, qualified_by="synthetic-reviewer", local_path="synthetic/model")
        self.assert_invalid(document, "requires a nonzero recorded weight hash")

        document = self.mutated()
        candidate = next(entry for entry in document["entries"]
                         if entry["family"] == "segmentation" and entry["machine_state"] == "ABSENT")
        candidate.update(radar_state="QUALIFIED_LOCAL", machine_state="LOAD_VERIFIED",
                         default_enabled=True, qualified_by="synthetic-reviewer",
                         local_path="synthetic/model", weights_sha256=["0" * 64])
        self.assert_invalid(document, "zero weight hash is not evidence")

        document = self.mutated()
        candidate = next(entry for entry in document["entries"]
                         if entry["family"] == "segmentation" and entry["machine_state"] == "ABSENT")
        candidate.update(radar_state="QUALIFIED_LOCAL", machine_state="LOAD_VERIFIED",
                         default_enabled=True, qualified_by="synthetic-reviewer",
                         local_path="synthetic/model", weights_sha256=["a" * 64])
        self.model_radar.validate_registry(document)  # well-formed qualification is accepted

    def test_inference_verified_requires_an_evidence_reference(self):
        document = self.mutated()
        entry = next(item for item in document["entries"] if item["machine_state"] == "ABSENT")
        entry["machine_state"] = "INFERENCE_VERIFIED"
        entry["local_path"] = "synthetic/model"
        entry["evidence_ref"] = None
        self.assert_invalid(document, "INFERENCE_VERIFIED requires a non-empty evidence_ref")

    def test_blocked_entry_may_not_claim_fits_or_permitted_use(self):
        document = self.mutated()
        entry = next(item for item in document["entries"] if item["radar_state"] == "BLOCKED_BY_LICENSE")
        entry["hardware_fit"] = {"vram_gib_required": 4, "verdict": "FITS"}
        self.assert_invalid(document, "may not carry a FITS hardware verdict")

        document = self.mutated()
        entry = next(item for item in document["entries"] if item["radar_state"] == "BLOCKED_BY_LICENSE")
        entry["rights"]["commercial_use"] = "PERMITTED"
        self.assert_invalid(document, "conflicts with commercial_use PERMITTED")

    def test_hardware_verdict_must_agree_with_the_declared_ceiling(self):
        document = self.mutated()
        entry = next(item for item in document["entries"] if item["hardware_fit"]["verdict"] == "FITS")
        entry["hardware_fit"] = {"vram_gib_required": 32, "verdict": "FITS"}
        self.assert_invalid(document, "FITS contradicts the declared ceiling")

        document = self.mutated()
        entry = next(item for item in document["entries"] if item["hardware_fit"]["verdict"] == "EXCEEDS")
        entry["hardware_fit"] = {"vram_gib_required": 1, "verdict": "EXCEEDS"}
        self.assert_invalid(document, "EXCEEDS contradicts the declared ceiling")

    def test_duplicate_model_id_is_rejected(self):
        document = self.mutated()
        document["entries"].append(copy.deepcopy(document["entries"][0]))
        self.assert_invalid(document, "duplicate model_id")

    # -- resolver ---------------------------------------------------------
    def test_resolver_refuses_each_reason_distinctly(self):
        self.assertIn(self.model_radar.REFUSAL_UNKNOWN, self.assert_refused("no-such-model", "UNKNOWN_MODEL"))
        self.assertIn(self.model_radar.REFUSAL_LICENSE,
                      self.assert_refused("minimax-h3-diffusion", "BLOCKED_BY_LICENSE"))
        self.assertIn(self.model_radar.REFUSAL_UNQUALIFIED,
                      self.assert_refused("sam2", "UNQUALIFIED_RADAR_STATE"))

        document = self.mutated()
        entry = next(item for item in document["entries"] if item["model_id"] == "sam2")
        entry.update(radar_state="QUALIFIED_LOCAL", machine_state="LOAD_VERIFIED", default_enabled=True,
                     qualified_by="synthetic-reviewer", local_path="synthetic/model",
                     weights_sha256=["a" * 64],
                     hardware_fit={"vram_gib_required": 64, "verdict": "EXCEEDS"})
        self.model_radar.validate_registry(document)
        with self.assertRaises(self.model_radar.ReadinessError) as caught:
            self.model_radar.resolve(document, "sam2")
        self.assertIn(self.model_radar.REFUSAL_HARDWARE, str(caught.exception))

        entry["hardware_fit"] = {"vram_gib_required": None, "verdict": "UNKNOWN"}
        with self.assertRaises(self.model_radar.ReadinessError) as caught:
            self.model_radar.resolve(document, "sam2")
        self.assertIn(self.model_radar.REFUSAL_HARDWARE, str(caught.exception))

    def test_resolver_returns_a_detached_copy_for_a_well_formed_entry(self):
        document = self.mutated()
        entry = next(item for item in document["entries"] if item["model_id"] == "sam2")
        entry.update(radar_state="QUALIFIED_LOCAL", machine_state="LOAD_VERIFIED", default_enabled=True,
                     qualified_by="synthetic-reviewer", local_path="synthetic/model",
                     weights_sha256=["a" * 64],
                     hardware_fit={"vram_gib_required": 4, "verdict": "FITS"})
        self.model_radar.validate_registry(document)
        resolved = self.model_radar.resolve(document, "sam2")
        resolved["hardware_fit"]["verdict"] = "MUTATED"
        self.assertEqual(entry["hardware_fit"]["verdict"], "FITS")

    def test_report_refuses_every_registered_model_and_flags_licence_pending(self):
        report = self.model_radar.radar_report(self.registry)
        self.assertEqual(report["entries_total"], len(self.registry["entries"]))
        self.assertEqual(report["default_enabled"], [])
        self.assertEqual(report["licence_adjudication_pending"],
                         [entry["model_id"] for entry in self.registry["entries"]
                          if entry["radar_state"] == "BLOCKED_BY_LICENSE"])
        refused = {row["model_id"] for row in report["refused_by_resolver"]}
        self.assertEqual(refused, {entry["model_id"] for entry in self.registry["entries"]})
        self.assertEqual(sum(report["by_radar_state"].values()), report["entries_total"])
        self.assertEqual(report["inference_executed"], "NONE")

    def test_load_registry_refuses_a_missing_file(self):
        with self.assertRaises(self.model_radar.ReadinessError) as caught:
            self.model_radar.load_registry(ROOT / "design-lab/readiness/nonexistent-radar.json")
        self.assertIn("unreadable", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
