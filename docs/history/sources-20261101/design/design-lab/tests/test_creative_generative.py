# SPDX-License-Identifier: MIT
"""Wave D (DL-P0-080/081/090/091): generative contracts, planning and guards."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative.generative import (  # noqa: E402
    GenerativeError, model_assets, partial_execution, remote_provider, workflow_provider,
)
from design_lab.runtime.paths import resolve_paths  # noqa: E402

DIGEST = "sha256:" + "a" * 64


def workflow():
    """A small but structurally real ComfyUI UI graph: load, encode, sample, decode, save."""
    return {
        "version": 0.4,
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "pos": [0, 0], "inputs": [],
             "outputs": [{"name": "MODEL"}, {"name": "CLIP"}, {"name": "VAE"}],
             "widgets_values": ["sd_xl_base.safetensors"]},
            {"id": 2, "type": "CLIPTextEncode", "pos": [10, 0],
             "inputs": [{"name": "clip", "link": 1},
                        {"name": "text", "widget": {"name": "text"}}],
             "outputs": [{"name": "CONDITIONING"}], "widgets_values": ["a poster"]},
            {"id": 3, "type": "KSampler", "pos": [20, 0],
             "inputs": [{"name": "model", "link": 2}, {"name": "positive", "link": 3},
                        {"name": "seed", "widget": {"name": "seed"}},
                        {"name": "steps", "widget": {"name": "steps"}}],
             "outputs": [{"name": "LATENT"}], "widgets_values": [42, 30]},
            {"id": 4, "type": "VAEDecode", "pos": [30, 0],
             "inputs": [{"name": "samples", "link": 4}, {"name": "vae", "link": 5}],
             "outputs": [{"name": "IMAGE"}], "widgets_values": []},
            {"id": 5, "type": "SaveImage", "pos": [40, 0],
             "inputs": [{"name": "images", "link": 6}], "outputs": [], "widgets_values": ["out"]},
        ],
        "links": [
            [1, 1, 1, 2, 0, "CLIP"],
            [2, 1, 0, 3, 0, "MODEL"],
            [3, 2, 0, 3, 1, "CONDITIONING"],
            [4, 3, 0, 4, 0, "LATENT"],
            [5, 1, 2, 4, 1, "VAE"],
            [6, 4, 0, 5, 0, "IMAGE"],
        ],
    }


class WorkflowProviderTests(unittest.TestCase):
    def test_valid_graph_summary(self):
        summary = workflow_provider.validate_ui_workflow(workflow())
        self.assertEqual(summary["node_count"], 5)
        self.assertEqual(summary["link_count"], 6)
        self.assertEqual(summary["version"], 0.4)
        self.assertIn("KSampler", summary["class_types"])

    def test_unsupported_version_is_refused(self):
        document = workflow()
        document["version"] = 1.0
        with self.assertRaisesRegex(GenerativeError, "unsupported ComfyUI workflow version"):
            workflow_provider.validate_ui_workflow(document)

    def test_structural_violations_are_named(self):
        duplicate = workflow()
        duplicate["nodes"][1]["id"] = 1
        with self.assertRaisesRegex(GenerativeError, "duplicate node id 1"):
            workflow_provider.validate_ui_workflow(duplicate)

        dangling = workflow()
        dangling["links"][0][3] = 99
        with self.assertRaisesRegex(GenerativeError, "unknown target node 99"):
            workflow_provider.validate_ui_workflow(dangling)

        slot = workflow()
        slot["links"][0][4] = 5
        with self.assertRaisesRegex(GenerativeError, "target slot 5 is out of range"):
            workflow_provider.validate_ui_workflow(slot)

        mismatch = workflow()
        mismatch["nodes"][1]["inputs"][0]["link"] = 4
        with self.assertRaisesRegex(GenerativeError, "does not target node 2 input 0"):
            workflow_provider.validate_ui_workflow(mismatch)

        unknown_link = workflow()
        unknown_link["nodes"][1]["inputs"][0]["link"] = 99
        with self.assertRaisesRegex(GenerativeError, "unknown link 99"):
            workflow_provider.validate_ui_workflow(unknown_link)

    def test_fingerprint_ignores_canvas_position_and_array_order(self):
        document = workflow()
        shuffled = copy.deepcopy(document)
        shuffled["nodes"].reverse()
        shuffled["links"].reverse()
        for node in shuffled["nodes"]:
            node["pos"] = [999, 999]
        self.assertEqual(workflow_provider.graph_fingerprint(document),
                         workflow_provider.graph_fingerprint(shuffled))

    def test_fingerprint_changes_with_parameters(self):
        document = workflow()
        changed = workflow_provider.bind_input(document, 3, "steps", 60)
        self.assertNotEqual(workflow_provider.graph_fingerprint(document),
                            workflow_provider.graph_fingerprint(changed))
        self.assertEqual(document["nodes"][2]["widgets_values"], [42, 30])

    def test_binding_rejects_an_unknown_widget(self):
        with self.assertRaisesRegex(GenerativeError, "no widget input named 'cfg'"):
            workflow_provider.bind_input(workflow(), 3, "cfg", 7)

    def test_changed_nodes_reports_parameter_and_wiring_changes(self):
        document = workflow()
        reparam = workflow_provider.bind_input(document, 3, "steps", 60)
        self.assertEqual(workflow_provider.changed_nodes(document, reparam), [3])
        rewired = copy.deepcopy(document)
        rewired["links"][2][1] = 1
        self.assertEqual(workflow_provider.changed_nodes(document, rewired), [3])

    def test_api_graph_validation(self):
        graph = {"3": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": 42}},
                 "4": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        self.assertEqual(workflow_provider.validate_api_workflow(graph)["node_count"], 2)
        with self.assertRaisesRegex(GenerativeError, "references unknown node 9"):
            workflow_provider.validate_api_workflow(
                {"3": {"class_type": "KSampler", "inputs": {"model": ["9", 0]}}})

    def test_provider_is_structural_and_never_dispatches(self):
        provider = workflow_provider.ComfyWorkflowProvider()
        probe = provider.probe({})
        self.assertEqual(probe["status"], "STRUCTURAL")
        self.assertEqual(probe["evidence_level"], "E1")
        self.assertFalse(probe["capabilities"][0]["supported"])
        prepared = provider.prepare({"workflow": workflow()})
        self.assertTrue(prepared["prepared"])
        self.assertFalse(prepared["dispatched"])
        with self.assertRaisesRegex(GenerativeError, "NOT_EXECUTED_STRUCTURAL_ONLY"):
            provider.execute({"workflow": workflow()})
        self.assertEqual(provider.observe({})["observed"], False)
        self.assertEqual(provider.readback({})["readback"], "NOT_EXECUTED")
        self.assertEqual(provider.rollback({})["rollback"], "PLAN_ONLY")

    def test_declarations_validate_against_repository_contracts(self):
        declaration = workflow_provider.provider_declaration()
        self.assertEqual(declaration["status"], "structural")
        self.assertTrue(all(not item["supported"] for item in declaration["capabilities"]))
        entry = workflow_provider.registry_entry()
        self.assertEqual(entry["license"], "unverified")
        self.assertEqual(entry["evidence_level"], "E1")


class PartialExecutionTests(unittest.TestCase):
    def test_plan_reruns_changed_and_downstream_only(self):
        result = partial_execution.plan(workflow(), [2])
        self.assertEqual(result["changed"], [2])
        self.assertEqual(result["rerun"], [2, 3, 4, 5])
        self.assertEqual(result["reuse"], [1])
        self.assertEqual(result["invalidated_terminals"], [5])
        self.assertTrue(result["delivery_blocked"])
        partial_execution.assert_plan_sound(result, workflow())

    def test_unchanged_branch_is_reused(self):
        result = partial_execution.plan(workflow(), [4], terminal=[5])
        self.assertEqual(result["rerun"], [4, 5])
        self.assertEqual(result["reuse"], [1, 2, 3])

    def test_reusing_a_downstream_node_is_refused(self):
        with self.assertRaisesRegex(GenerativeError, "cannot reuse nodes that changed or are downstream"):
            partial_execution.plan(workflow(), [2], cached=[4])

    def test_unknown_change_and_unknown_terminal_are_refused(self):
        with self.assertRaisesRegex(GenerativeError, "not in the workflow"):
            partial_execution.plan(workflow(), [99])
        with self.assertRaisesRegex(GenerativeError, "terminal nodes are not in the workflow"):
            partial_execution.plan(workflow(), [2], terminal=[99])

    def test_empty_change_set_is_refused(self):
        with self.assertRaisesRegex(GenerativeError, "at least one changed node"):
            partial_execution.plan(workflow(), [])

    def test_cycle_is_detected(self):
        document = workflow()
        document["links"].append([7, 4, 0, 3, 0, "LATENT"])
        document["nodes"][2]["inputs"][0]["link"] = 7
        with self.assertRaisesRegex(GenerativeError, "cycle detected"):
            partial_execution.verify_acyclic(document)

    def test_unsound_plan_is_refused(self):
        plan = {"changed": [2], "rerun": [2, 3], "reuse": [4, 5]}
        with self.assertRaisesRegex(GenerativeError, "unsound plan"):
            partial_execution.assert_plan_sound(plan, workflow())

    def test_lineage_impact_maps_onto_nodes(self):
        result = partial_execution.plan_from_lineage(
            workflow(), {1: "v-root", 3: "v-latent", 5: "v-image"}, ["v-latent"])
        self.assertEqual(result["changed_nodes_from_lineage"], [3])
        self.assertEqual(result["rerun"], [3, 4, 5])
        with self.assertRaisesRegex(GenerativeError, "not produced by any workflow node"):
            partial_execution.plan_from_lineage(workflow(), {1: "v-root"}, ["v-unknown"])


class RemoteProviderTests(unittest.TestCase):
    def _request(self):
        return remote_provider.build_request(
            model_ref="black-forest-labs/flux-schnell", version_ref="3f7f6f0e0d4b8c7a",
            inputs=[{"role": "init", "sha256": DIGEST, "source": "asset_version",
                     "asset_version_id": "v-1"}], params={"steps": 4})

    def test_request_pins_a_version_and_carries_no_credentials(self):
        request = self._request()
        self.assertEqual(request["version_ref"], "3f7f6f0e0d4b8c7a")
        self.assertTrue(request["request_sha256"].startswith("sha256:"))
        with self.assertRaisesRegex(GenerativeError, "exact model version"):
            remote_provider.build_request(model_ref="m", version_ref="latest", inputs=[{"role": "init"}])
        with self.assertRaisesRegex(GenerativeError, "credentials never enter a request record"):
            remote_provider.build_request(model_ref="m", version_ref="v1", inputs=[{"role": "init"}],
                                          params={"api_key": "x"})
        with self.assertRaisesRegex(GenerativeError, "at least one input"):
            remote_provider.build_request(model_ref="m", version_ref="v1", inputs=[])

    def test_response_status_is_closed(self):
        with self.assertRaisesRegex(GenerativeError, "unknown provider status"):
            remote_provider.parse_response({"status": "probably_fine"})
        normalized = remote_provider.parse_response({"id": "p1", "status": "succeeded",
                                                     "output": ["https://example.invalid/out.png"],
                                                     "metrics": {"predict_time": 1.5}})
        self.assertEqual(normalized["prediction_id"], "p1")
        self.assertTrue(normalized["outputs"][0]["ref_sha256"].startswith("sha256:"))

    def test_remote_success_without_local_readback_is_not_qualified(self):
        request = self._request()
        response = remote_provider.parse_response({"id": "p1", "status": "succeeded",
                                                   "output": ["https://example.invalid/out.png"]})
        receipt = remote_provider.to_receipt(request, response)
        self.assertEqual(receipt["axes"]["host_live"], "NOT_VERIFIED")
        self.assertEqual(receipt["axes"]["unit"], "PARTIAL")
        with self.assertRaisesRegex(GenerativeError, "lacks local_artifact_sha256"):
            remote_provider.assert_local_evidence(receipt)
        self.assertIn("artifact_available", remote_provider.unsupported_claims(receipt))

    def test_receipt_qualifies_only_with_local_artifact_and_readback(self):
        request = self._request()
        response = remote_provider.parse_response({"id": "p1", "status": "succeeded",
                                                   "output": ["https://example.invalid/out.png"]})
        receipt = remote_provider.to_receipt(request, response, local_artifact_sha256=DIGEST,
                                             readback_sha256="sha256:" + "b" * 64,
                                             rights_state="CLEARED", territory_limits=["EU", "UK"])
        remote_provider.assert_local_evidence(receipt)
        self.assertEqual(receipt["axes"]["host_live"], "PASS")
        self.assertNotIn("commercial_use", remote_provider.unsupported_claims(receipt))
        self.assertIn("reproducible_offline", remote_provider.unsupported_claims(receipt))

    def test_credentials_boundary_and_structural_execute(self):
        boundary = remote_provider.credentials_boundary()
        self.assertEqual(boundary["in_repo_credentials"], "FORBIDDEN")
        self.assertEqual(boundary["env_lookup"], "NOT_PERFORMED")
        provider = remote_provider.ReplicateProvider()
        self.assertEqual(provider.probe({})["status"], "STRUCTURAL")
        with self.assertRaisesRegex(GenerativeError, "NOT_EXECUTED_STRUCTURAL_ONLY"):
            provider.execute({})


class ModelAssetTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/generative-model-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def _entry(self, **overrides):
        kwargs = dict(
            model_id="sdxl-base-1.0", family="image-generation",
            source={"kind": "huggingface", "ref": "stabilityai/stable-diffusion-xl-base-1.0",
                    "license_id": "openrail++"},
            root_alias="model-library",
            files=[{"path": "ComfyUI/models/checkpoints/sd_xl_base.safetensors", "sha256": DIGEST,
                    "bytes": 6938049088}],
            state="QUALIFIED", machine_state="LOAD_VERIFIED",
            rights={"license_id": "openrail++", "territory_limits": [], "commercial_use": "PERMITTED"},
            hardware={"vram_gib_required": 8.0, "verdict": "FITS"}, default_enabled=True,
            notes="declared for structural tests")
        kwargs.update(overrides)
        return model_assets.model_entry(**kwargs)

    def test_qualified_entry_resolves_and_is_enabled(self):
        registry = {"schemaVersion": "design-lab/generative-model-registry/v1", "models": [self._entry()]}
        resolved = model_assets.resolve(registry, "sdxl-base-1.0")
        self.assertEqual(resolved["model_id"], "sdxl-base-1.0")
        self.assertTrue(model_assets.default_enabled(resolved))
        self.assertEqual(model_assets.validate_registry(registry)["enabled"], ["sdxl-base-1.0"])

    def test_unqualified_models_are_disabled_and_refused(self):
        with self.assertRaisesRegex(GenerativeError, "default_enabled requires a QUALIFIED model"):
            self._entry(state="HASH_VERIFIED")
        blocked = self._entry(model_id="minimax-h3-video", state="BLOCKED", default_enabled=False,
                              rights={"license_id": "unverified", "territory_limits": ["EU", "UK", "KR", "US"],
                                      "commercial_use": "UNKNOWN"})
        registry = {"schemaVersion": "design-lab/generative-model-registry/v1",
                    "models": [blocked, self._entry()]}
        self.assertFalse(model_assets.default_enabled(blocked))
        with self.assertRaisesRegex(GenerativeError, "BLOCKED_BY_LICENSE"):
            model_assets.resolve(registry, "minimax-h3-video")
        report = model_assets.registry_report(registry)
        self.assertIn("minimax-h3-video", report["refused"])
        self.assertEqual(report["enabled"], ["sdxl-base-1.0"])

    def test_qualification_requires_rights_and_machine_evidence(self):
        with self.assertRaisesRegex(GenerativeError, "commercial-use position"):
            self._entry(rights={"license_id": "openrail++", "territory_limits": [],
                                "commercial_use": "UNKNOWN"})
        with self.assertRaisesRegex(GenerativeError, "LOAD_VERIFIED"):
            self._entry(machine_state="WEIGHTS_COMPLETE")
        with self.assertRaisesRegex(GenerativeError, "requires a named licence"):
            self._entry(rights={"license_id": "unverified", "territory_limits": [],
                                "commercial_use": "PERMITTED"})

    def test_unknown_model_never_falls_back(self):
        registry = {"schemaVersion": "design-lab/generative-model-registry/v1", "models": [self._entry()]}
        with self.assertRaisesRegex(GenerativeError, "unknown model"):
            model_assets.resolve(registry, "some-other-model")

    def test_paths_are_alias_relative_and_cannot_escape(self):
        entry = self._entry()
        resolved = model_assets.declared_path(entry, entry["files"][0])
        alias_root = Path(resolve_paths().shared_inputs["model-library"]).resolve()
        self.assertTrue(resolved.is_relative_to(alias_root))
        self.assertEqual(resolved.name, "sd_xl_base.safetensors")
        for bad in ("../../secrets.txt", "C:/Windows/system32/config", "/etc/passwd"):
            with self.subTest(path=bad):
                with self.assertRaises(GenerativeError):
                    model_assets.declared_path(entry, {"path": bad})
        with self.assertRaisesRegex(GenerativeError, "unknown path alias"):
            model_assets.declared_path(self._entry(root_alias="not-declared"), {"path": "a.bin"})

    def test_missing_files_fail_closed_when_presence_is_required(self):
        registry = {"schemaVersion": "design-lab/generative-model-registry/v1", "models": [
            self._entry(files=[{"path": "ComfyUI/models/checkpoints/absent.safetensors",
                                "sha256": DIGEST, "bytes": 1}])]}
        self.assertEqual(model_assets.resolve(registry, "sdxl-base-1.0")["state"], "QUALIFIED")
        with self.assertRaisesRegex(GenerativeError, "FILES_MISSING"):
            model_assets.resolve(registry, "sdxl-base-1.0", require_present=True)
        present = model_assets.present_files(registry["models"][0])
        self.assertFalse(present[0]["present"])

    def test_hash_file_is_read_only_and_refuses_empty(self):
        target = self.tmp / "weights.bin"
        target.write_bytes(b"model")
        self.assertTrue(model_assets.hash_file(target).startswith("sha256:"))
        empty = self.tmp / "empty.bin"
        empty.write_bytes(b"")
        with self.assertRaisesRegex(GenerativeError, "empty file"):
            model_assets.hash_file(empty)

    def test_real_model_radar_projects_and_blocked_licences_stay_refused(self):
        """DL-P0-091 resolves over the DL-P1-100 registry; no second registry."""
        radar_path = ROOT / "design-lab/readiness/model-radar.json"
        radar = json.loads(radar_path.read_text(encoding="utf-8"))
        registry = model_assets.registry_from_radar(radar)
        self.assertEqual(len(registry["models"]), len(radar["entries"]))
        report = model_assets.registry_report(registry)
        self.assertEqual(report["enabled"], [])
        for model_id in ("minimax-h3-diffusion", "minimax-h3-text-encoder",
                         "minimax-h3-video-vae", "minimax-h3-audio-vae"):
            with self.subTest(model=model_id), self.assertRaisesRegex(GenerativeError, "BLOCKED_BY_LICENSE"):
                model_assets.resolve(registry, model_id)

    def test_radar_paths_and_vocabulary_are_mapped_not_guessed(self):
        entry = model_assets.from_radar_entry({
            "model_id": "radar-sample", "family": "upscaling", "radar_state": "WATCH",
            "machine_state": "ABSENT", "local_path": "model-library:ComfyUI/x.bin",
            "weights_sha256": [], "source": {"kind": "local", "ref": "model-library:x", "license_id": "MIT"},
            "rights": {"license_id": "MIT", "territory_limits": [], "commercial_use": "UNKNOWN"},
            "hardware_fit": {"vram_gib_required": 4.0, "verdict": "FITS"}})
        self.assertEqual(entry["family"], "upscale")
        self.assertEqual(entry["root_alias"], "model-library")
        self.assertEqual(entry["files"][0]["path"], "ComfyUI/x.bin")
        self.assertFalse(entry["default_enabled"])
        repo_local = model_assets.from_radar_entry({
            "model_id": "repo-local-sample", "family": "ocr", "radar_state": "EVALUATING",
            "machine_state": "METADATA_ONLY", "local_path": ".project-local/task-artifacts/x",
            "weights_sha256": [], "source": {"kind": "local", "ref": "x", "license_id": "MIT"},
            "rights": {"license_id": "MIT", "territory_limits": [], "commercial_use": "RESTRICTED"},
            "hardware_fit": {"vram_gib_required": 1.0, "verdict": "FITS"}})
        self.assertEqual(repo_local["root_alias"], "project-local")
        with self.assertRaisesRegex(GenerativeError, "no counterpart in the model-asset contract"):
            model_assets.from_radar_entry({
                "model_id": "drift", "family": "not-a-family", "radar_state": "WATCH",
                "machine_state": "ABSENT", "local_path": "model-library:x",
                "weights_sha256": [], "source": {"kind": "local", "ref": "x", "license_id": "MIT"},
                "rights": {"license_id": "MIT", "territory_limits": [], "commercial_use": "UNKNOWN"},
                "hardware_fit": {"vram_gib_required": None, "verdict": "UNKNOWN"}})


if __name__ == "__main__":
    unittest.main()
