# SPDX-License-Identifier: MIT
"""Fail-closed evidence packaging and bundle-validation tests for C6."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_LAB = REPO_ROOT / "design-lab"
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(REPO_ROOT / "packages" / "capabilities"))

from reconstruction.pipeline import run_reconstruction  # noqa: E402
from reconstruction.state import canonical_json_bytes  # noqa: E402
from test_reconstruction_pipeline import _create_contract  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_artifact(artifact_id: str, path: str) -> dict:
    return {"id": artifact_id, "kind": "package", "path": path}


def _rewrite_manifest(bundle: Path, mutate) -> None:
    path = bundle / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_bytes(canonical_json_bytes(value))


def _rehash_manifest_artifact(bundle: Path, relative: str) -> None:
    target = bundle / relative

    def mutate(manifest: dict) -> None:
        record = next(item for item in manifest["artifacts"] if item["path"] == relative)
        record["byteSize"] = target.stat().st_size
        record["sha256"] = _sha256(target)

    _rewrite_manifest(bundle, mutate)


def _rebind_pipeline_artifact(bundle: Path, relative: str, role: str) -> None:
    _rehash_manifest_artifact(bundle, relative)
    contract = json.loads((bundle / "run.contract.json").read_text(encoding="utf-8"))
    runtime_path = next(
        item["path"] for item in contract["artifacts"] if item.get("role") == role
    )
    journal_path = bundle / "journal.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["entries"][-1]["outputHashes"][runtime_path] = _sha256(bundle / relative)
    journal_path.write_bytes(canonical_json_bytes(journal))
    _rehash_manifest_artifact(bundle, "journal.json")
    provenance_path = bundle / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["journalSha256"] = _sha256(journal_path)
    provenance_path.write_bytes(canonical_json_bytes(provenance))
    _rehash_manifest_artifact(bundle, "provenance.json")


def _execution_digest(execution: dict) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {"closureVersion": execution["closureVersion"], "files": execution["files"]}
        )
    ).hexdigest()


class ReconstructionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cleanup: list[Path] = []

    def tearDown(self) -> None:
        for path in reversed(self.cleanup):
            if path.exists() or path.is_symlink():
                shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()

    def make_completed_run(
        self, *, semantic_raster: bool = False, grouped: bool = False,
        semantic_source_origin: tuple[int, int] = (0, 0),
    ) -> tuple[Path, Path, Path, dict]:
        token = "c6-" + uuid.uuid4().hex
        contract_path, run_dir, contract = _create_contract(token)
        evidence_rel = contract["roots"]["evidence"]
        evidence_dir = REPO_ROOT.joinpath(*Path(evidence_rel.rstrip("/")).parts)

        model_registry = run_dir / "models.json"
        model_registry.write_bytes(
            canonical_json_bytes(
                {
                    "schemaVersion": "design-lab/reconstruction-models/v1",
                    "models": [],
                }
            )
        )
        model_rel = model_registry.relative_to(REPO_ROOT).as_posix()
        contract["registries"]["modelRegistry"] = model_rel
        contract["artifacts"].append(_package_artifact("model-registry", model_rel))

        semantic_bundle_names: tuple[str, ...] = ()
        if semantic_raster:
            source_x, source_y = semantic_source_origin
            raster_path = run_dir / "layers" / "texture-chip.png"
            raster_path.parent.mkdir(parents=True)
            with Image.open(REPO_ROOT / contract["source"]["path"]) as image:
                image.convert("RGBA").crop(
                    (source_x, source_y, source_x + 8, source_y + 8)
                ).save(raster_path, format="PNG")
            raster_rel = raster_path.relative_to(REPO_ROOT).as_posix()
            rir_path = run_dir / "input.rir.json"
            rir = json.loads(rir_path.read_text(encoding="utf-8"))
            bounds = {"x": source_x, "y": source_y, "width": 8, "height": 8}
            crop = {"x": 0, "y": 0, "width": 8, "height": 8}
            rir["layers"].append(
                {
                    "id": "texture-chip",
                    "type": "raster",
                    "name": "texture-chip",
                    "opacity": 1.0,
                    "bounds": bounds,
                    "inferred": False,
                    "zOrder": 4,
                    "visible": True,
                    "locked": False,
                    "blendMode": "normal",
                    "raster": {
                        "path": raster_rel,
                        "crop": crop,
                        "alpha": 1.0,
                        "sourceMappings": [
                            {"sourceBounds": bounds, "targetBounds": bounds}
                        ],
                    },
                }
            )
            rir_path.write_bytes(canonical_json_bytes(rir))
            rir_artifact = next(
                item for item in contract["artifacts"] if item.get("role") == "reconstruction-rir"
            )
            rir_artifact["sha256"] = _sha256(rir_path)
            contract["artifacts"].append(_package_artifact("semantic-raster-source", raster_rel))
            semantic_bundle_names = ("layers/texture-chip.png",)

        if grouped:
            rir_path = run_dir / "input.rir.json"
            rir = json.loads(rir_path.read_text(encoding="utf-8"))
            children = rir["layers"][:2]
            rir["layers"] = [
                {
                    "id": "top-row",
                    "type": "group",
                    "name": "top-row",
                    "opacity": 1.0,
                    "bounds": {"x": 0, "y": 0, "width": 64, "height": 32},
                    "inferred": False,
                    "zOrder": 0,
                    "visible": True,
                    "locked": False,
                    "blendMode": "normal",
                    "children": children,
                },
                *rir["layers"][2:],
            ]
            rir_path.write_bytes(canonical_json_bytes(rir))
            rir_artifact = next(
                item for item in contract["artifacts"] if item.get("role") == "reconstruction-rir"
            )
            rir_artifact["sha256"] = _sha256(rir_path)

        bundle_names = (
            "manifest.json",
            "reference.normalized.png",
            "master.svg",
            "preview.png",
            "metrics.json",
            "diff.png",
            "journal.json",
            "run.contract.json",
            "structure-report.json",
            "provenance.json",
            "registries/tool-registry.json",
            "registries/model-registry.json",
        )
        for index, name in enumerate(bundle_names + semantic_bundle_names):
            contract["artifacts"].append(
                _package_artifact(f"bundle-{index:02d}", evidence_rel + name)
            )
        contract["writeAuthorization"]["targets"] = [
            item["path"] for item in contract["artifacts"]
        ]
        contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

        self.cleanup.extend([contract_path, run_dir, evidence_dir])
        summary = run_reconstruction(contract_path)
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        return contract_path, run_dir, evidence_dir, contract

    def make_bundle(self) -> Path:
        from reconstruction.evidence import package_evidence

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        summary = package_evidence(run_dir, evidence_dir)
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        return evidence_dir

    def make_delivery_bundle(self, *, illustrator_metrics: bool = True) -> Path:
        bundle = self.make_bundle()
        manifest_path = bundle / "manifest.json"
        contract_path = bundle / "run.contract.json"
        journal_path = bundle / "journal.json"
        provenance_path = bundle / "provenance.json"
        metrics_path = bundle / "metrics.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        (bundle / "master.ai").write_bytes(b"%AI-24\nfixture-native-document\n")
        shutil.copyfile(bundle / "preview.png", bundle / "preview.illustrator.png")
        if illustrator_metrics:
            metrics["illustratorMetrics"] = {
                "profileId": "design-lab/render-profile/v1",
                "referenceSha256": _sha256(bundle / "reference.normalized.png"),
                "previewSha256": _sha256(bundle / "preview.illustrator.png"),
                "matchRatio": 1.0,
                "ssim": 1.0,
                "meanRgbaError": 0.0,
                "denseRegions": [],
                "passed": True,
            }
        metrics_path.write_bytes(canonical_json_bytes(metrics))
        reports = {
            "illustrator-readback.json": {
                "schemaVersion": "design-lab/illustrator-readback/v1",
                "passed": True,
                "masterAiSha256": _sha256(bundle / "master.ai"),
                "previewSha256": _sha256(bundle / "preview.illustrator.png"),
                "artboard": {"width": 64, "height": 64},
                "layerCount": 4,
                "objectCount": 4,
                "linksEmbedded": True,
                "saveState": "saved",
            },
            "golden-corpus.json": {
                "schemaVersion": "design-lab/reconstruction-golden-corpus/v1",
                "passed": True,
                "passedCases": [
                    "logo-icon", "ui-screen", "poster", "flat-illustration",
                    "complex-illustration", "mixed-media",
                ],
                "cleanRuns": 3,
            },
            "exact-sha-ci.json": {
                "schemaVersion": "design-lab/exact-sha-ci/v1",
                "passed": True,
                "sha256": manifest["checkedOutSourceSha256"],
            },
            "rights.json": {
                "schemaVersion": "design-lab/reconstruction-rights/v1",
                "status": "VERIFIED",
                "sourceRights": "VERIFIED",
            },
            "installed-runtime.json": {
                "schemaVersion": "design-lab/installed-runtime/v1",
                "status": "VERIFIED",
                "product": "Adobe Illustrator",
                "version": "fixture-1",
            },
        }
        for name, value in reports.items():
            (bundle / name).write_bytes(canonical_json_bytes(value))

        extra_names = (
            "master.ai", "preview.illustrator.png", "illustrator-readback.json",
            "golden-corpus.json", "exact-sha-ci.json", "rights.json", "installed-runtime.json",
        )
        evidence_root = contract["roots"]["evidence"]
        for index, name in enumerate(extra_names):
            contract["artifacts"].append(
                _package_artifact(f"release-{index:02d}", evidence_root + name)
            )
        contract["writeAuthorization"]["targets"] = [
            item["path"] for item in contract["artifacts"]
        ]
        contract_path.write_bytes(canonical_json_bytes(contract))
        old_contract_sha = journal["contractSha256"]
        new_contract_sha = hashlib.sha256(canonical_json_bytes(contract)).hexdigest()
        journal["contractSha256"] = new_contract_sha
        metrics_runtime = next(
            item["path"] for item in contract["artifacts"] if item.get("role") == "pipeline-metrics"
        )
        journal["entries"][-1]["outputHashes"][metrics_runtime] = _sha256(metrics_path)
        for entry in journal["entries"]:
            entry["inputHashes"] = {
                key: new_contract_sha if value == old_contract_sha else value
                for key, value in entry["inputHashes"].items()
            }
        journal_path.write_bytes(canonical_json_bytes(journal))
        provenance["contractSha256"] = new_contract_sha
        provenance["journalSha256"] = _sha256(journal_path)
        provenance["rightsStatus"] = {
            "status": "VERIFIED",
            "evidencePath": "rights.json",
            "evidenceSha256": _sha256(bundle / "rights.json"),
        }
        # This is a structural clean-tree fixture only; it is not live CI or host authority.
        provenance["sourceTreeState"] = "CLEAN_EXACT_HEAD"
        provenance["executionSource"]["state"] = "CLEAN_EXACT_HEAD"
        for item in provenance["executionSource"]["files"]:
            item["headBlobSha"] = item["currentBlobSha"]
            item["trackState"] = "TRACKED_HEAD_MATCH"
        execution_digest = _execution_digest(provenance["executionSource"])
        provenance["executionSource"]["digest"] = execution_digest
        provenance_path.write_bytes(canonical_json_bytes(provenance))

        existing = {item["path"]: item for item in manifest["artifacts"]}
        for name in ("run.contract.json", "journal.json", "metrics.json", "provenance.json"):
            existing[name]["byteSize"] = (bundle / name).stat().st_size
            existing[name]["sha256"] = _sha256(bundle / name)
        producers = {
            "master.ai": ("adobe-illustrator", "native-deliverable"),
            "preview.illustrator.png": ("adobe-illustrator", "host-readback"),
            "illustrator-readback.json": ("adobe-illustrator", "host-readback"),
            "golden-corpus.json": ("release-qualification", "release-evidence"),
            "exact-sha-ci.json": ("release-qualification", "release-evidence"),
            "rights.json": ("release-qualification", "release-evidence"),
            "installed-runtime.json": ("release-qualification", "release-evidence"),
        }
        for name, (producer, ownership) in producers.items():
            media = (
                "image/png" if name.endswith(".png")
                else "application/vnd.adobe.illustrator" if name.endswith(".ai")
                else "application/json"
            )
            manifest["artifacts"].append(
                {
                    "path": name,
                    "mediaType": media,
                    "byteSize": (bundle / name).stat().st_size,
                    "sha256": _sha256(bundle / name),
                    "producerPhase": producer,
                    "ownershipClass": ownership,
                }
            )
        manifest["artifacts"] = sorted(manifest["artifacts"], key=lambda item: item["path"])
        manifest["state"] = "DELIVERY_READY"
        manifest["sourceTreeState"] = "CLEAN_EXACT_HEAD"
        manifest["executionSourceDigest"] = execution_digest
        manifest["releaseEvidence"] = {
            "nativeAi": {"path": "master.ai", "sha256": _sha256(bundle / "master.ai")},
            "illustratorPreview": {"path": "preview.illustrator.png", "sha256": _sha256(bundle / "preview.illustrator.png")},
            "illustratorReadback": {"path": "illustrator-readback.json", "sha256": _sha256(bundle / "illustrator-readback.json")},
            "goldenCorpus": {"path": "golden-corpus.json", "sha256": _sha256(bundle / "golden-corpus.json")},
            "exactShaCi": {"path": "exact-sha-ci.json", "sha256": _sha256(bundle / "exact-sha-ci.json")},
            "rights": {"path": "rights.json", "sha256": _sha256(bundle / "rights.json")},
            "installedRuntime": {"path": "installed-runtime.json", "sha256": _sha256(bundle / "installed-runtime.json")},
            "authorityReceipt": None,
        }
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        return bundle

    def test_package_and_validate_require_complete_deterministic_topology(self) -> None:
        from reconstruction.evidence import validate_bundle

        bundle = self.make_bundle()
        summary = validate_bundle(bundle)
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertEqual(summary.artifact_count, 12)
        self.assertTrue(summary.passed)
        self.assertEqual(
            {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()},
            {
                "manifest.json",
                "reference.normalized.png",
                "master.svg",
                "preview.png",
                "metrics.json",
                "diff.png",
                "journal.json",
                "run.contract.json",
                "structure-report.json",
                "provenance.json",
                "registries/tool-registry.json",
                "registries/model-registry.json",
            },
        )

    def test_declared_semantic_raster_is_cropped_hash_bound_and_under_flat_budget(self) -> None:
        from reconstruction.evidence import package_evidence, validate_bundle

        _contract, run_dir, evidence_dir, _value = self.make_completed_run(semantic_raster=True)
        packaged = package_evidence(run_dir, evidence_dir)
        self.assertEqual(packaged.artifact_count, 13)
        summary = validate_bundle(evidence_dir)
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        structure = json.loads((evidence_dir / "structure-report.json").read_text(encoding="utf-8"))
        self.assertEqual(structure["semanticRasterLayers"], ["layers/texture-chip.png"])
        self.assertEqual(structure["rasterCoveredCanvasArea"], 64.0)
        self.assertEqual(structure["rasterCoveredCanvasRatio"], 0.015625)
        raster = next(item for item in structure["objects"] if item["id"] == "texture-chip")
        self.assertEqual(raster["raster"]["crop"], {"x": 0, "y": 0, "width": 8, "height": 8})
        self.assertEqual(raster["raster"]["alphaBounds"], {"x": 0, "y": 0, "width": 8, "height": 8})

    def test_semantic_raster_preserves_nonzero_source_lineage_with_local_crop_coordinates(self) -> None:
        from reconstruction.evidence import package_evidence, validate_bundle

        _contract, run_dir, evidence_dir, _value = self.make_completed_run(
            semantic_raster=True, semantic_source_origin=(8, 8)
        )
        packaged = package_evidence(run_dir, evidence_dir)
        self.assertEqual(packaged.state, "PIXEL_VERIFIED_DETERMINISTIC")
        summary = validate_bundle(evidence_dir)
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        structure = json.loads((evidence_dir / "structure-report.json").read_text(encoding="utf-8"))
        raster = next(item for item in structure["objects"] if item["id"] == "texture-chip")
        self.assertEqual(
            raster["sourceMapping"],
            [{
                "sourceBounds": {"x": 8, "y": 8, "width": 8, "height": 8},
                "targetBounds": {"x": 8, "y": 8, "width": 8, "height": 8},
            }],
        )
        self.assertEqual(raster["raster"]["crop"], {"x": 0, "y": 0, "width": 8, "height": 8})
        from reconstruction import evidence as module

        manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
        records = {item["path"]: item for item in manifest["artifacts"]}
        files = module._enumerate_files(evidence_dir)
        for case in (
            "outside-source", "wrong-source-size", "zero-target-width", "zero-target-height"
        ):
            with self.subTest(case=case):
                forged = copy.deepcopy(structure)
                forged_raster = next(item for item in forged["objects"] if item["id"] == "texture-chip")
                if case == "outside-source":
                    forged_raster["sourceMapping"][0]["sourceBounds"]["x"] = 60
                elif case == "wrong-source-size":
                    forged_raster["sourceMapping"][0]["sourceBounds"]["width"] = 7
                else:
                    dimension = case.removeprefix("zero-target-")
                    forged_raster["bounds"][dimension] = 0
                    forged_raster["sourceMapping"][0]["targetBounds"][dimension] = 0
                    forged_raster["raster"]["canvasArea"] = 0
                    forged["rasterCoveredCanvasArea"] = 0
                    forged["rasterCoveredCanvasRatio"] = 0
                with self.assertRaisesRegex(
                    module.EvidenceError, "source region|normalized canvas|local crop|positive|bounds|target"
                ):
                    module._structure_semantics(forged, records, manifest, files)

    def test_recorded_canvas_background_is_exactly_bound_to_c3_svg_projection(self) -> None:
        from reconstruction import evidence as module
        from reconstruction.svg import serialize_svg

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        module.package_evidence(run_dir, evidence_dir)
        rir = json.loads((run_dir / "input.rir.json").read_text(encoding="utf-8"))
        rir["canvas"]["background"] = {"color": "#00000000", "recorded": True}
        structure, _rasters = module._build_structure(rir, run_dir, "flat")
        manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
        structure["runId"] = manifest["runId"]
        files = module._enumerate_files(evidence_dir)
        records = {item["path"]: item for item in manifest["artifacts"]}
        raster_hashes = module._structure_semantics(structure, records, manifest, files)

        background_svg = run_dir / "background.svg"
        background_svg.write_bytes(serialize_svg(rir, REPO_ROOT))
        module._svg_semantics(background_svg, structure, raster_hashes)
        with self.assertRaisesRegex(module.EvidenceError, "background"):
            module._svg_semantics(evidence_dir / "master.svg", structure, raster_hashes)

        structure["canvas"]["background"]["extra"] = "forged"
        with self.assertRaisesRegex(module.EvidenceError, "canvas|background|shape|malformed"):
            module._structure_semantics(structure, records, manifest, files)

    def test_package_requires_exact_contract_declared_evidence_root(self) -> None:
        from reconstruction.evidence import EvidenceError, package_evidence

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        wrong = evidence_dir.parent / (evidence_dir.name + "-wrong")
        self.cleanup.append(wrong)
        with self.assertRaisesRegex(EvidenceError, "exact declared evidence root"):
            package_evidence(run_dir, wrong)
        self.assertFalse(wrong.exists())

    def test_transient_private_or_unknown_runtime_paths_are_rejected(self) -> None:
        from reconstruction.evidence import EvidenceError, package_evidence

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        private = run_dir / "session-prompt.log"
        private.write_text("private prompt", encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "undeclared|private|transient"):
            package_evidence(run_dir, evidence_dir)
        self.assertFalse(evidence_dir.exists())

    def test_missing_extra_hash_size_and_media_type_mutations_fail_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        cases = ("missing", "extra", "hash", "size", "media")
        for case in cases:
            with self.subTest(case=case):
                bundle = self.make_bundle()
                if case == "missing":
                    (bundle / "diff.png").unlink()
                elif case == "extra":
                    (bundle / "debug.log").write_text("no", encoding="utf-8")
                else:
                    def mutate(manifest: dict) -> None:
                        record = next(
                            item for item in manifest["artifacts"] if item["path"] == "diff.png"
                        )
                        if case == "hash":
                            record["sha256"] = "0" * 64
                        elif case == "size":
                            record["byteSize"] += 1
                        else:
                            record["mediaType"] = "text/plain"

                    _rewrite_manifest(bundle, mutate)
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_manifest_duplicate_keys_nonfinite_and_bounded_size_are_rejected(self) -> None:
        from reconstruction.evidence import EvidenceError, MAX_JSON_BYTES, validate_bundle

        bundle = self.make_bundle()
        manifest = bundle / "manifest.json"
        manifest.write_text('{"schemaVersion":"x","schemaVersion":"y"}', encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "duplicate|strict JSON"):
            validate_bundle(bundle)

        bundle = self.make_bundle()
        structure = bundle / "structure-report.json"
        structure.write_text('{"rasterCoveredCanvasRatio":NaN}', encoding="utf-8")
        _rehash_manifest_artifact(bundle, "structure-report.json")
        with self.assertRaisesRegex(EvidenceError, "non-finite|strict JSON"):
            validate_bundle(bundle)

        bundle = self.make_bundle()
        provenance = bundle / "provenance.json"
        with provenance.open("wb") as stream:
            stream.truncate(MAX_JSON_BYTES + 1)
        _rehash_manifest_artifact(bundle, "provenance.json")
        with self.assertRaisesRegex(EvidenceError, "byte limit|size limit"):
            validate_bundle(bundle)

    def test_provenance_rejects_prompt_session_private_and_absolute_path_material(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        for field, value in (
            ("prompt", "secret"),
            ("session", "abc"),
            ("privateRuntime", "C:/Users/ALEX/private"),
        ):
            with self.subTest(field=field):
                bundle = self.make_bundle()
                provenance_path = bundle / "provenance.json"
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                provenance[field] = value
                provenance_path.write_bytes(canonical_json_bytes(provenance))
                _rehash_manifest_artifact(bundle, "provenance.json")
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_metrics_registry_renderer_and_input_hashes_are_reverified(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        for field in ("referenceSha256", "previewSha256", "diffSha256", "registryDigest"):
            with self.subTest(field=field):
                bundle = self.make_bundle()
                metrics_path = bundle / "metrics.json"
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                metrics[field] = "0" * 64
                metrics_path.write_bytes(canonical_json_bytes(metrics))
                _rehash_manifest_artifact(bundle, "metrics.json")
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_structure_raster_coverage_inconsistency_fails_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        structure_path = bundle / "structure-report.json"
        structure = json.loads(structure_path.read_text(encoding="utf-8"))
        structure["rasterCoveredCanvasArea"] = 1
        structure["rasterCoveredCanvasRatio"] = 1 / 4096
        structure_path.write_bytes(canonical_json_bytes(structure))
        _rehash_manifest_artifact(bundle, "structure-report.json")
        with self.assertRaisesRegex(EvidenceError, "raster.*area|coverage"):
            validate_bundle(bundle)

    def test_structure_bounds_and_semantic_target_mapping_are_exact_not_containment_only(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        structure_path = bundle / "structure-report.json"
        structure = json.loads(structure_path.read_text(encoding="utf-8"))
        structure["objects"][0]["bounds"]["width"] = 64
        structure_path.write_bytes(canonical_json_bytes(structure))
        _rehash_manifest_artifact(bundle, "structure-report.json")
        with self.assertRaisesRegex(EvidenceError, "exact|bounds|projection"):
            validate_bundle(bundle)

        raster_bundle = self.make_completed_run(semantic_raster=True)
        from reconstruction.evidence import package_evidence

        _contract, run_dir, evidence_dir, _value = raster_bundle
        package_evidence(run_dir, evidence_dir)
        raster_structure_path = evidence_dir / "structure-report.json"
        raster_structure = json.loads(raster_structure_path.read_text(encoding="utf-8"))
        raster = next(item for item in raster_structure["objects"] if item["type"] == "raster")
        raster["sourceMapping"][0]["targetBounds"]["x"] = 1
        raster_structure_path.write_bytes(canonical_json_bytes(raster_structure))
        _rehash_manifest_artifact(evidence_dir, "structure-report.json")
        with self.assertRaisesRegex(EvidenceError, "target|mapping|bounds"):
            validate_bundle(evidence_dir)

        _contract, group_run, group_evidence, _value = self.make_completed_run(grouped=True)
        package_evidence(group_run, group_evidence)
        group_structure_path = group_evidence / "structure-report.json"
        group_structure = json.loads(group_structure_path.read_text(encoding="utf-8"))
        group = next(item for item in group_structure["objects"] if item["type"] == "group")
        self.assertEqual(group["bounds"], {"x": 0, "y": 0, "width": 64, "height": 32})
        group["bounds"]["width"] = 63
        group_structure_path.write_bytes(canonical_json_bytes(group_structure))
        _rehash_manifest_artifact(group_evidence, "structure-report.json")
        with self.assertRaisesRegex(EvidenceError, "group|exact|bounds"):
            validate_bundle(group_evidence)

    def test_all_control_json_rejects_extra_keys_and_private_or_profile_path_values(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        metrics_path = bundle / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["forgedExtra"] = True
        metrics_path.write_bytes(canonical_json_bytes(metrics))
        _rebind_pipeline_artifact(bundle, "metrics.json", "pipeline-metrics")
        with self.assertRaisesRegex(EvidenceError, "shape|extra|metrics"):
            validate_bundle(bundle)

        for value in ("session token=secret", r"C:\Users\ALEX\private.json", "/home/alex/private.json"):
            with self.subTest(value=value):
                bundle = self.make_bundle()
                registry_path = bundle / "registries" / "model-registry.json"
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                registry["models"] = [{"value": value}]
                registry_path.write_bytes(canonical_json_bytes(registry))
                _rehash_manifest_artifact(bundle, "registries/model-registry.json")
                provenance_path = bundle / "provenance.json"
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                provenance["registries"]["model"]["sha256"] = _sha256(registry_path)
                provenance_path.write_bytes(canonical_json_bytes(provenance))
                _rehash_manifest_artifact(bundle, "provenance.json")
                with self.assertRaisesRegex(EvidenceError, "private|absolute|profile|home"):
                    validate_bundle(bundle)

    def test_privacy_scan_uses_sensitive_key_and_absolute_path_boundaries(self) -> None:
        from reconstruction import evidence as module

        allowed = {
            "tokenizer": "local-bpe-v1",
            "sessionDuration": "15s",
            "apiKeyRotationDays": 30,
            "authenticationMode": "offline",
            "assetPath": "design-lab/assets/home/icon.png",
            "documentation": "https://example.invalid/profiles/reference",
        }
        module._scan_report_privacy(allowed)

        forbidden = (
            {"sessionId": "abc"},
            {"accessToken": "secret"},
            {"apiToken": "secret"},
            {"apiKey": "secret"},
            {"client-secret": "secret"},
            {"password": "secret"},
            {"credential": "secret"},
            {"private_key": "secret"},
            {"auth": "secret"},
            {"assetPath": r"C:\Users\ALEX\private.json"},
            {"assetPath": "/home/alex/private.json"},
            {"assetPath": "file:///home/alex/private.json"},
            {"note": "copied from /Users/alex/private.json"},
            {"note": "session token=secret"},
            {"note": "password=secret"},
            {"note": "credential = secret"},
            {"note": "private key=secret"},
            {"note": "Bearer token secret"},
        )
        for value in forbidden:
            with self.subTest(value=value):
                with self.assertRaisesRegex(module.EvidenceError, "private|absolute|profile|home"):
                    module._scan_report_privacy(value)

    def test_full_canvas_raster_overlay_is_rejected_even_when_hash_bound(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        preview_data = (bundle / "preview.png").read_bytes()
        import base64

        href = base64.b64encode(preview_data).decode("ascii")
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
            'viewBox="0 0 64 64"><image id="overlay" x="0" y="0" width="64" '
            f'height="64" href="data:image/png;base64,{href}"/></svg>'
        )
        (bundle / "master.svg").write_text(svg, encoding="utf-8")
        _rebind_pipeline_artifact(bundle, "master.svg", "sanitized-svg")
        with self.assertRaisesRegex(EvidenceError, "full-canvas raster overlay"):
            validate_bundle(bundle)

    def test_svg_color_mutation_is_rejected_by_independent_c3_c4_replay_even_when_rebound(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        svg_path = bundle / "master.svg"
        svg = svg_path.read_text(encoding="utf-8")
        self.assertIn("#142850", svg)
        svg_path.write_text(svg.replace("#142850", "#142851", 1), encoding="utf-8")
        _rebind_pipeline_artifact(bundle, "master.svg", "sanitized-svg")
        with self.assertRaisesRegex(EvidenceError, "re-render|replay|preview"):
            validate_bundle(bundle)

    def test_forged_delivery_ready_requires_all_host_release_and_rights_evidence(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()

        def mutate(manifest: dict) -> None:
            manifest["state"] = "DELIVERY_READY"

        _rewrite_manifest(bundle, mutate)
        with self.assertRaisesRegex(EvidenceError, "delivery candidate|DELIVERY_READY"):
            validate_bundle(bundle)

    def test_complete_local_delivery_is_only_unverified_candidate_and_cannot_claim_ready(self) -> None:
        from reconstruction import evidence as module
        from reconstruction.evidence import EvidenceError, validate_bundle

        def validate_fixture(bundle: Path):
            declared = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))["executionSource"]
            with mock.patch.object(module, "_execution_source_evidence", return_value=declared):
                return validate_bundle(bundle)

        incomplete = self.make_delivery_bundle(illustrator_metrics=False)
        with self.assertRaisesRegex(EvidenceError, "Illustrator metrics"):
            validate_fixture(incomplete)
        complete = self.make_delivery_bundle()
        manifest_path = complete / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["state"] = "DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        summary = validate_fixture(complete)
        self.assertEqual(summary.state, "DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL")
        self.assertFalse(summary.passed)
        self.assertEqual(summary.failure_reason, "EXTERNAL_EVIDENCE_NOT_VERIFIED")
        provenance_path = complete / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        original_current_sha = provenance["executionSource"]["files"][0]["currentSha256"]
        original_current_blob = provenance["executionSource"]["files"][0]["currentBlobSha"]
        provenance["sourceTreeState"] = "DIRTY_UNPUBLISHED"
        provenance["executionSource"]["state"] = "DIRTY_UNPUBLISHED"
        provenance["executionSource"]["files"][0]["currentSha256"] = "f" * 64
        provenance["executionSource"]["files"][0]["currentBlobSha"] = "f" * 40
        provenance["executionSource"]["files"][0]["trackState"] = "TRACKED_MODIFIED"
        dirty_digest = _execution_digest(provenance["executionSource"])
        provenance["executionSource"]["digest"] = dirty_digest
        provenance_path.write_bytes(canonical_json_bytes(provenance))
        _rehash_manifest_artifact(complete, "provenance.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sourceTreeState"] = "DIRTY_UNPUBLISHED"
        manifest["executionSourceDigest"] = dirty_digest
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(EvidenceError, "DIRTY_UNPUBLISHED"):
            validate_fixture(complete)
        provenance["sourceTreeState"] = "CLEAN_EXACT_HEAD"
        provenance["executionSource"]["state"] = "CLEAN_EXACT_HEAD"
        provenance["executionSource"]["files"][0]["currentSha256"] = original_current_sha
        provenance["executionSource"]["files"][0]["currentBlobSha"] = original_current_blob
        provenance["executionSource"]["files"][0]["trackState"] = "TRACKED_HEAD_MATCH"
        clean_digest = _execution_digest(provenance["executionSource"])
        provenance["executionSource"]["digest"] = clean_digest
        provenance_path.write_bytes(canonical_json_bytes(provenance))
        _rehash_manifest_artifact(complete, "provenance.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sourceTreeState"] = "CLEAN_EXACT_HEAD"
        manifest["executionSourceDigest"] = clean_digest
        manifest["state"] = "DELIVERY_READY"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(EvidenceError, "EXTERNAL_EVIDENCE_NOT_VERIFIED"):
            validate_fixture(complete)

    def test_structure_projection_and_provenance_mutations_fail_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        for kind in (
            "structure-opacity", "structure-type", "structure-numeric-string",
            "structure-blend", "source-hash", "inferred-regions", "provider-events",
            "registry-hash", "rights-forgery",
        ):
            with self.subTest(kind=kind):
                bundle = self.make_bundle()
                if kind.startswith("structure"):
                    path = bundle / "structure-report.json"
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if kind == "structure-opacity":
                        value["objects"][0]["opacity"] = 0.5
                    elif kind == "structure-type":
                        value["objects"][0]["type"] = "raster"
                    elif kind == "structure-numeric-string":
                        value["objects"][0]["bounds"]["x"] = "0"
                    else:
                        value["objects"][0]["blendMode"] = "unknown"
                    path.write_bytes(canonical_json_bytes(value))
                    _rehash_manifest_artifact(bundle, "structure-report.json")
                else:
                    path = bundle / "provenance.json"
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if kind == "source-hash":
                        value["source"]["originalSha256"] = "0" * 64
                    elif kind == "inferred-regions":
                        value["inferredRegions"] = ["forged"]
                    elif kind == "provider-events":
                        value["providerEvents"][0]["fallbackUsed"] = True
                    elif kind == "registry-hash":
                        value["registries"]["model"]["sha256"] = "0" * 64
                    else:
                        value["rightsStatus"] = {
                            "status": "VERIFIED", "evidencePath": "rights.json",
                            "evidenceSha256": "0" * 64,
                        }
                    path.write_bytes(canonical_json_bytes(value))
                    _rehash_manifest_artifact(bundle, "provenance.json")
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_dirty_execution_tree_is_recorded_truthfully_and_blocks_delivery_claims(self) -> None:
        from reconstruction import evidence as module

        dirty = copy.deepcopy(module._execution_source_evidence())
        dirty["files"][0]["currentSha256"] = "0" * 64
        dirty["files"][0]["currentBlobSha"] = "0" * 40
        dirty["files"][0]["trackState"] = "TRACKED_MODIFIED"
        dirty["state"] = "DIRTY_UNPUBLISHED"
        dirty["digest"] = _execution_digest(dirty)
        with mock.patch.object(module, "_execution_source_evidence", return_value=dirty):
            bundle = self.make_bundle()
            self.assertEqual(module.validate_bundle(bundle).state, "PIXEL_VERIFIED_DETERMINISTIC")
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        provenance = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sourceTreeState"], "DIRTY_UNPUBLISHED")
        self.assertEqual(provenance["sourceTreeState"], "DIRTY_UNPUBLISHED")
        self.assertEqual(manifest["executionSourceDigest"], provenance["executionSource"]["digest"])
        self.assertTrue(
            any(item["trackState"] == "TRACKED_MODIFIED" for item in provenance["executionSource"]["files"])
        )

    def test_clean_execution_source_fixture_is_structural_only_and_makes_no_ci_claim(self) -> None:
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        observed = module._execution_source_evidence()
        simulated = copy.deepcopy(observed)
        simulated["state"] = "CLEAN_EXACT_HEAD"
        for item in simulated["files"]:
            item["headBlobSha"] = item["currentBlobSha"]
            item["trackState"] = "TRACKED_HEAD_MATCH"
        simulated["digest"] = _execution_digest(simulated)
        with mock.patch.object(module, "_execution_source_evidence", return_value=simulated):
            summary = module.package_evidence(run_dir, evidence_dir)
        manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertEqual(manifest["sourceTreeState"], "CLEAN_EXACT_HEAD")
        self.assertTrue(all(value is None for value in manifest["releaseEvidence"].values()))

    def test_deterministic_replay_failure_cleans_exact_verifier_run_without_residue(self) -> None:
        from reconstruction import evidence as module

        bundle = self.make_bundle()
        runtime_parent = REPO_ROOT / ".project-local" / "task-runtime" / "reconstruction"
        evidence_parent = REPO_ROOT / ".project-local" / "task-artifacts" / "reconstruction"

        def residues(parent: Path) -> set[str]:
            return {
                path.name for path in parent.iterdir()
                if path.name.startswith("c6v-")
            } if parent.exists() else set()

        before = (residues(runtime_parent), residues(evidence_parent))
        with mock.patch.object(
            module, "render_svg", side_effect=module.RenderError("forced replay failure")
        ):
            with self.assertRaisesRegex(module.EvidenceError, "deterministic C3/C4 replay"):
                module.validate_bundle(bundle)
        self.assertEqual((residues(runtime_parent), residues(evidence_parent)), before)

    def test_execution_source_toctou_before_promotion_is_rejected(self) -> None:
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        before = module._execution_source_evidence()
        changed = copy.deepcopy(before)
        changed["files"][0]["currentSha256"] = "0" * 64
        changed["digest"] = _execution_digest(changed)
        with mock.patch.object(
            module, "_execution_source_evidence", side_effect=[before, before, changed]
        ):
            with self.assertRaisesRegex(module.EvidenceError, "execution source tree changed"):
                module.package_evidence(run_dir, evidence_dir)
        self.assertFalse(evidence_dir.exists())

    def test_execution_closure_is_dynamic_and_validator_rechecks_local_bytes(self) -> None:
        from reconstruction import evidence as module

        discovered = set(module._discover_execution_source_paths())
        expected_modules = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "packages" / "capabilities" / "reconstruction").rglob("*.py")
        }
        expected_schemas = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (DESIGN_LAB / "schemas" / "reconstruction").rglob("*.json")
        }
        self.assertTrue(expected_modules.issubset(discovered))
        self.assertTrue(expected_schemas.issubset(discovered))
        self.assertIn("design-lab/scripts/verify_reconstruction_bundle.py", discovered)
        self.assertIn("design-lab/scripts/verify_reconstruction_pipeline.py", discovered)
        self.assertIn("design-lab/scripts/verify_design_lab.py", discovered)
        self.assertIn("design-lab/config/reconstruction-tools.json", discovered)
        self.assertIn("design-lab/tests/test_reconstruction_evidence.py", discovered)

        fixture_root = (
            REPO_ROOT / ".project-local" / "task-runtime" / "reconstruction-dev"
            / ("closure-fixture-" + uuid.uuid4().hex)
        )
        self.cleanup.append(fixture_root)
        nested_module = fixture_root / "packages" / "capabilities" / "reconstruction" / "providers" / "local.py"
        nested_schema = fixture_root / "design-lab" / "schemas" / "reconstruction" / "nested" / "local.json"
        nested_module.parent.mkdir(parents=True)
        nested_schema.parent.mkdir(parents=True)
        nested_module.write_text("# nested execution fixture\n", encoding="utf-8")
        nested_schema.write_text("{}\n", encoding="utf-8")
        head_only = [
            "packages/capabilities/reconstruction/providers/head_only.py",
            "design-lab/schemas/reconstruction/nested/head_only.json",
            "design-lab/scripts/verify_design_lab.py",
            "design-lab/config/reconstruction-models.json",
        ]
        with (
            mock.patch.object(module, "PROJECT_ROOT", fixture_root),
            mock.patch.object(module, "_git_lines", return_value=head_only),
        ):
            fixture_discovered = set(module._discover_execution_source_paths())
        for expected in (
            "packages/capabilities/reconstruction/providers/local.py",
            "packages/capabilities/reconstruction/providers/head_only.py",
            "design-lab/schemas/reconstruction/nested/local.json",
            "design-lab/schemas/reconstruction/nested/head_only.json",
            "design-lab/scripts/verify_design_lab.py",
            "design-lab/config/reconstruction-models.json",
        ):
            self.assertIn(expected, fixture_discovered)
        observed = module._execution_source_evidence()
        verifier_record = next(
            item for item in observed["files"]
            if item["path"] == "design-lab/scripts/verify_reconstruction_bundle.py"
        )
        if verifier_record["headBlobSha"] is None:
            tracked = set(module._git_lines(
                ["ls-files", "--", verifier_record["path"]],
                label="test execution-source tracking",
            ))
            expected_track_state = (
                "TRACKED_NEW" if verifier_record["path"] in tracked else "UNTRACKED"
            )
        elif verifier_record["currentSha256"] is None:
            expected_track_state = "TRACKED_DELETED"
        elif verifier_record["currentBlobSha"] == verifier_record["headBlobSha"]:
            expected_track_state = "TRACKED_HEAD_MATCH"
        else:
            expected_track_state = "TRACKED_MODIFIED"
        self.assertEqual(verifier_record["trackState"], expected_track_state)
        expected_state = (
            "CLEAN_EXACT_HEAD"
            if all(item["trackState"] == "TRACKED_HEAD_MATCH" for item in observed["files"])
            else "DIRTY_UNPUBLISHED"
        )
        self.assertEqual(observed["state"], expected_state)

        bundle = self.make_bundle()
        provenance_path = bundle / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["executionSource"]["files"][0]["currentSha256"] = "0" * 64
        provenance["executionSource"]["files"][0]["currentBlobSha"] = "0" * 40
        provenance["executionSource"]["files"][0]["trackState"] = "TRACKED_MODIFIED"
        forged_digest = _execution_digest(provenance["executionSource"])
        provenance["executionSource"]["digest"] = forged_digest
        provenance_path.write_bytes(canonical_json_bytes(provenance))
        _rehash_manifest_artifact(bundle, "provenance.json")
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["executionSourceDigest"] = forged_digest
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(module.EvidenceError, "execution.source|local|closure|digest"):
            module.validate_bundle(bundle)

    def test_execution_closure_file_records_are_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        provenance_path = bundle / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["executionSource"]["files"][0]["extra"] = "forged"
        forged_digest = _execution_digest(provenance["executionSource"])
        provenance["executionSource"]["digest"] = forged_digest
        provenance_path.write_bytes(canonical_json_bytes(provenance))
        _rehash_manifest_artifact(bundle, "provenance.json")
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["executionSourceDigest"] = forged_digest
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(EvidenceError, "execution-source file record|shape"):
            validate_bundle(bundle)

    def test_prior_accepted_bundle_is_byte_preserved_when_repackaging_fails(self) -> None:
        from reconstruction.evidence import EvidenceError, package_evidence

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        package_evidence(run_dir, evidence_dir)
        before = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        (run_dir / "preview.png").write_bytes(b"tampered")
        with self.assertRaises(EvidenceError):
            package_evidence(run_dir, evidence_dir)
        after = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_source_toctou_between_snapshot_and_copy_is_rejected(self) -> None:
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        target = run_dir / "preview.png"
        original = target.read_bytes()

        def mutate_once(_path: Path) -> None:
            target.write_bytes(original + b"x")

        with mock.patch.object(module, "_after_source_snapshot", side_effect=mutate_once):
            with self.assertRaises(module.EvidenceError):
                module.package_evidence(run_dir, evidence_dir)
        self.assertFalse(evidence_dir.exists())

    def test_contract_and_journal_hash_or_state_forgery_is_rejected(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        for relative, field in (("run.contract.json", "contract"), ("journal.json", "journal")):
            with self.subTest(field=field):
                bundle = self.make_bundle()
                path = bundle / relative
                value = json.loads(path.read_text(encoding="utf-8"))
                if field == "contract":
                    value["runId"] = "forged"
                else:
                    value["entries"][-1]["newState"] = "DELIVERY_READY"
                path.write_bytes(canonical_json_bytes(value))
                _rehash_manifest_artifact(bundle, relative)
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_manifest_traversal_producer_and_ownership_mutations_fail_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        for case in ("traversal", "producer", "ownership"):
            with self.subTest(case=case):
                bundle = self.make_bundle()

                def mutate(manifest: dict) -> None:
                    record = next(
                        item for item in manifest["artifacts"] if item["path"] == "master.svg"
                    )
                    if case == "traversal":
                        record["path"] = "../master.svg"
                    elif case == "producer":
                        record["producerPhase"] = "evidence-package"
                    else:
                        record["ownershipClass"] = "bundle-report"

                _rewrite_manifest(bundle, mutate)
                with self.assertRaises(EvidenceError):
                    validate_bundle(bundle)

    def test_checkpoint_chain_mutation_fails_closed(self) -> None:
        from reconstruction.evidence import EvidenceError, validate_bundle

        bundle = self.make_bundle()
        provenance_path = bundle / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["checkpointChain"][-1]["sha256"] = "0" * 64
        provenance_path.write_bytes(canonical_json_bytes(provenance))
        _rehash_manifest_artifact(bundle, "provenance.json")
        with self.assertRaisesRegex(EvidenceError, "checkpoint"):
            validate_bundle(bundle)

    def test_atomic_promotion_failure_restores_prior_bundle_without_residue(self) -> None:
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        module.package_evidence(run_dir, evidence_dir)
        before = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        with mock.patch.object(module, "_after_promote", side_effect=OSError("forced promote readback failure")):
            with self.assertRaisesRegex(module.EvidenceError, "prior bundle restored|promotion failed"):
                module.package_evidence(run_dir, evidence_dir)
        after = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        residues = list(evidence_dir.parent.glob(f".{evidence_dir.name}.*-*"))
        self.assertEqual(residues, [])

    def test_model_registry_toctou_before_promotion_is_rejected(self) -> None:
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        model_registry = run_dir / "models.json"

        def mutate(_staging: Path) -> None:
            model_registry.write_text('{"schemaVersion":"forged","models":[]}', encoding="utf-8")

        with mock.patch.object(module, "_after_staging_validation", side_effect=mutate):
            with self.assertRaises(module.EvidenceError):
                module.package_evidence(run_dir, evidence_dir)
        self.assertFalse(evidence_dir.exists())

    def test_staging_mutation_after_seal_rejected_before_swap(self) -> None:
        """R0-004 before_swap: bytes changed after sealing must never swap."""
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()

        def mutate(_staging: Path) -> None:
            # rewrite the staged manifest after the seal was computed
            manifest = _staging / "manifest.json"
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            raw["state"] = "ANALYZED"
            manifest.write_bytes(canonical_json_bytes(raw))

        with mock.patch.object(module, "_after_staging_validation", side_effect=mutate):
            with self.assertRaisesRegex(module.EvidenceError, "seal mismatch|unsealed|changed after sealing"):
                module.package_evidence(run_dir, evidence_dir)
        self.assertFalse(evidence_dir.exists())

    def test_seal_mismatch_after_backup_restores_prior_bundle(self) -> None:
        """R0-004 after_backup: a swap-time failure restores the prior bundle."""
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        module.package_evidence(run_dir, evidence_dir)
        before = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        # force the failure right after the prior bundle was moved to backup
        with mock.patch.object(module, "_after_backup", side_effect=OSError("forced after_backup failure")):
            with self.assertRaisesRegex(module.EvidenceError, "prior bundle restored|promotion failed"):
                module.package_evidence(run_dir, evidence_dir)
        after = {
            path.relative_to(evidence_dir).as_posix(): path.read_bytes()
            for path in evidence_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        residues = list(evidence_dir.parent.glob(f".{evidence_dir.name}.*-*"))
        self.assertEqual(residues, [])

    def test_sealed_bundle_roundtrip_seal_stable(self) -> None:
        """R0-004: package_evidence promotes only sealed bundles with a stable seal."""
        from reconstruction import evidence as module

        _contract, run_dir, evidence_dir, _value = self.make_completed_run()
        module.package_evidence(run_dir, evidence_dir)
        seal = module.seal_bundle(evidence_dir)
        self.assertEqual(module.check_sealed(seal), [])
        reseal = module.seal_bundle(evidence_dir)
        self.assertEqual(seal["bundle_sha256"], reseal["bundle_sha256"])

    def test_reparse_or_symlink_bundle_member_is_rejected(self) -> None:
        from reconstruction import evidence as module

        bundle = self.make_bundle()
        target = bundle / "diff.png"
        backup = bundle.parent / (bundle.name + "-diff-backup.png")
        self.cleanup.append(backup)
        target.replace(backup)
        try:
            os.symlink(backup, target)
        except (OSError, NotImplementedError):
            backup.replace(target)
            with (
                mock.patch.object(
                    module,
                    "_is_reparse",
                    side_effect=lambda path: Path(path) == target,
                ),
                mock.patch.object(
                    module,
                    "_snapshot",
                    side_effect=AssertionError("reparse target must fail before reads"),
                ),
            ):
                with self.assertRaisesRegex(module.EvidenceError, "symlink|reparse"):
                    module.validate_bundle(bundle)
        else:
            with self.assertRaisesRegex(module.EvidenceError, "symlink|reparse"):
                module.validate_bundle(bundle)

    def test_real_fixture_verifier_and_canonical_chain_entry(self) -> None:
        verifier = DESIGN_LAB / "scripts" / "verify_reconstruction_bundle.py"
        completed = subprocess.run(
            [sys.executable, str(verifier), "--fixture"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertRegex(
            completed.stdout,
            r"RECONSTRUCTION_BUNDLE=PASS artifacts=12 state=PIXEL_VERIFIED_DETERMINISTIC",
        )
        canonical = (DESIGN_LAB / "scripts" / "verify_design_lab.py").read_text(encoding="utf-8")
        self.assertIn('"verify_reconstruction_bundle.py",', canonical)
        self.assertLess(
            canonical.index('"verify_reconstruction_pipeline.py",'),
            canonical.index('"verify_reconstruction_bundle.py",'),
        )


if __name__ == "__main__":
    unittest.main()
