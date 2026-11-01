# SPDX-License-Identifier: MIT
"""Deterministic reconstruction contract tests."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
if str(DESIGN_LAB) not in sys.path:
    sys.path.insert(0, str(DESIGN_LAB))
    sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.contracts import (  # noqa: E402
    ContractError,
    RIR_SCHEMA_ID,
    RUN_SCHEMA_ID,
    canonical_rir_bytes,
    canonical_rir_hash,
    validate_rir,
    validate_run_contract,
)


def minimal_rir() -> dict:
    return {
        "schemaVersion": "design-lab/reconstruction-ir/v1",
        "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
        "layers": [],
    }


def raster_layer(path: str = "inputs/source.png", *, layer_id: str = "raster-1") -> dict:
    return {
        "id": layer_id,
        "type": "raster",
        "name": "Source raster",
        "opacity": 1.0,
        "bounds": {"x": 0, "y": 0, "width": 64, "height": 64},
        "inferred": False,
        "zOrder": 0,
        "visible": True,
        "locked": False,
        "blendMode": "normal",
        "raster": {
            "path": path,
            "crop": {"x": 0, "y": 0, "width": 64, "height": 64},
            "alpha": 1.0,
            "sourceMappings": [
                {
                    "sourceBounds": {"x": 0, "y": 0, "width": 64, "height": 64},
                    "targetBounds": {"x": 0, "y": 0, "width": 64, "height": 64},
                }
            ],
        },
    }


def path_layer(*, layer_id: str = "path-1") -> dict:
    return {
        "id": layer_id,
        "type": "path",
        "name": "Vector path",
        "opacity": 1.0,
        "bounds": {"x": 0, "y": 0, "width": 64, "height": 64},
        "inferred": False,
        "zOrder": 0,
        "visible": True,
        "locked": False,
        "blendMode": "normal",
        "geometry": {"pathData": "M0 0L64 64", "closed": False},
        "style": {"stroke": "#000", "strokeWidth": 1},
        "masks": [
            {
                "id": "mask-1",
                "pathData": "M0 0H64V64H0Z",
                "operation": "intersect",
                "opacity": 1.0,
            }
        ],
    }


def primitive_layer(*, layer_id: str = "primitive-1") -> dict:
    layer = path_layer(layer_id=layer_id)
    layer["type"] = "primitive"
    layer.pop("geometry")
    layer["primitive"] = {
        "kind": "rect",
        "parameters": {"x1": 0, "y1": 0, "x2": 64, "y2": 64, "rx": 0, "ry": 0},
    }
    return layer


def minimal_run_contract(run_id: str = "run-001") -> dict:
    runtime_root = f".project-local/task-runtime/reconstruction/{run_id}/"
    evidence_root = f".project-local/task-artifacts/reconstruction/{run_id}/"
    now = datetime.now(timezone.utc)
    artifact_paths = [runtime_root + "output.svg", evidence_root + "report.json"]
    return {
        "schemaVersion": "design-lab/reconstruction-run/v1",
        "runId": run_id,
        "jobId": "job-001",
        "source": {
            "sourceId": "source-001",
            "path": "inputs/source.png",
            "sha256": "a" * 64,
            "profileMetadata": {"name": "reference", "version": "1"},
            "normalizedReferenceTarget": "normalized/source.png",
        },
        "profile": "ui",
        "canvasPolicy": {
            "width": 64,
            "height": 64,
            "colorSpace": "srgb",
            "globalCoordinates": "canvas",
            "tilePolicy": {
                "enabled": False,
                "tileWidth": 64,
                "tileHeight": 64,
                "overlap": 0,
            },
        },
        "roots": {"runtime": runtime_root, "evidence": evidence_root},
        "providerPolicy": {
            "defaultProvider": "local",
            "providerAllowlist": ["local", "remote-v1"],
            "selectedProvider": "local",
            "remoteConsents": [],
        },
        "writeAuthorization": {
            "authorizationId": "auth-001",
            "jobId": "job-001",
            "runId": run_id,
            "targets": artifact_paths,
            "issuedAt": (now - timedelta(minutes=1)).isoformat(),
            "expiresAt": (now + timedelta(hours=1)).isoformat(),
            "state": "authorized",
        },
        "registries": {
            "toolRegistry": "design-lab/config/tool-registry.json",
            "modelRegistry": "design-lab/config/model-registry.json",
        },
        "lifecycle": {
            "state": "authorized",
            "history": [
                {
                    "from": "created",
                    "to": "authorized",
                    "at": (now - timedelta(minutes=1)).isoformat(),
                }
            ],
        },
        "requestedOperations": ["reconstruct", "package", "readback"],
        "cancellationPolicy": {
            "cancelable": True,
            "resume": "checkpoint",
            "checkpointPath": runtime_root + "checkpoints/",
        },
        "artifacts": [
            {"id": "vector", "kind": "vector-output", "path": artifact_paths[0]},
            {"id": "evidence", "kind": "evidence", "path": artifact_paths[1]},
        ],
    }


class ReconstructionContractTests(unittest.TestCase):
    def _make_directory_link(self, link: Path, target: Path) -> None:
        container = link.parent.parent
        container_created = not container.exists()
        parent_created = not link.parent.exists()
        link.parent.mkdir(parents=True, exist_ok=True)
        if container_created:
            self.addCleanup(container.rmdir)
        if parent_created and link.parent != container:
            self.addCleanup(link.parent.rmdir)
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.addCleanup(os.rmdir, link)
        else:
            link.symlink_to(target, target_is_directory=True)
            self.addCleanup(link.unlink)

    def test_schema_documents_are_valid_draft_2020_12(self):
        import jsonschema

        schema_dir = DESIGN_LAB / "schemas" / "reconstruction"
        for name in ("reconstruction-ir.schema.json", "reconstruction-run.schema.json"):
            schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_minimal_rir_validates(self):
        validate_rir(
            {
                "schemaVersion": "design-lab/reconstruction-ir/v1",
                "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
                "layers": [],
            }
        )

    def test_external_raster_reference_is_rejected(self):
        value = minimal_rir()
        value["layers"] = [raster_layer("https://example.test/x.png")]
        with self.assertRaises(ContractError):
            validate_rir(value)

    def test_raster_reparse_escape_outside_project_is_rejected(self):
        run_id = f"rir-reparse-{os.getpid()}"
        link = PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction" / run_id / "escape"
        self._make_directory_link(link, PROJECT_ROOT.parent)
        value = minimal_rir()
        value["layers"] = [
            raster_layer(f".project-local/task-runtime/reconstruction/{run_id}/escape/source.png")
        ]
        with self.assertRaisesRegex(ContractError, "reparse|outside"):
            validate_rir(value)

    def test_duplicate_ids_are_rejected_across_nested_groups(self):
        child = raster_layer(layer_id="duplicate")
        group = {
            "id": "group-1",
            "type": "group",
            "name": "Group",
            "opacity": 1.0,
            "bounds": {"x": 0, "y": 0, "width": 64, "height": 64},
            "inferred": False,
            "zOrder": 0,
            "visible": True,
            "locked": False,
            "blendMode": "normal",
            "children": [child],
        }
        value = minimal_rir()
        value["layers"] = [group, raster_layer(layer_id="duplicate")]
        with self.assertRaisesRegex(ContractError, "duplicate"):
            validate_rir(value)

    def test_unknown_properties_are_rejected(self):
        value = minimal_rir()
        value["unexpected"] = True
        with self.assertRaises(ContractError):
            validate_rir(value)

    def test_invalid_opacity_bounds_and_z_order_are_rejected(self):
        mutations = (
            ("opacity", -0.01),
            ("bounds", {"x": 0, "y": 0, "width": -1, "height": 64}),
            ("zOrder", -1),
        )
        for field, invalid in mutations:
            with self.subTest(field=field):
                value = minimal_rir()
                layer = raster_layer()
                layer[field] = invalid
                value["layers"] = [layer]
                with self.assertRaises(ContractError):
                    validate_rir(value)

    def test_non_finite_numbers_are_rejected_anywhere_in_rir(self):
        cases = (
            ("raster alpha", raster_layer, lambda layer: layer["raster"].__setitem__("alpha", float("nan"))),
            ("raster crop", raster_layer, lambda layer: layer["raster"]["crop"].__setitem__("x", float("nan"))),
            (
                "source mapping",
                raster_layer,
                lambda layer: layer["raster"]["sourceMappings"][0]["targetBounds"].__setitem__(
                    "width", float("nan")
                ),
            ),
            ("mask opacity", path_layer, lambda layer: layer["masks"][0].__setitem__("opacity", float("nan"))),
            ("style width", path_layer, lambda layer: layer["style"].__setitem__("strokeWidth", float("inf"))),
            (
                "primitive parameter",
                primitive_layer,
                lambda layer: layer["primitive"]["parameters"].__setitem__("rx", float("-inf")),
            ),
            (
                "confidence",
                raster_layer,
                lambda layer: layer.__setitem__("confidence", {"score": float("nan"), "method": "model"}),
            ),
        )
        for name, factory, mutate in cases:
            with self.subTest(name=name):
                value = minimal_rir()
                layer = factory()
                mutate(layer)
                value["layers"] = [layer]
                with self.assertRaisesRegex(ContractError, "finite|JSON"):
                    validate_rir(value)

    def test_parent_traversal_and_absolute_raster_paths_are_rejected(self):
        for path in (
            "../source.png",
            "inputs/../source.png",
            "/source.png",
            "C:\\source.png",
            "https:source.png",
        ):
            with self.subTest(path=path):
                value = minimal_rir()
                value["layers"] = [raster_layer(path)]
                with self.assertRaises(ContractError):
                    validate_rir(value)

    def test_canonical_hash_is_stable_across_mapping_insertion_order(self):
        first = minimal_rir()
        second = {
            "layers": [],
            "canvas": {"colorSpace": "srgb", "height": 64, "width": 64},
            "schemaVersion": RIR_SCHEMA_ID,
        }
        expected = b'{"canvas":{"colorSpace":"srgb","height":64,"width":64},"layers":[],"schemaVersion":"design-lab/reconstruction-ir/v1"}'
        self.assertEqual(canonical_rir_bytes(first), expected)
        self.assertEqual(canonical_rir_bytes(first), canonical_rir_bytes(second))
        self.assertEqual(canonical_rir_hash(first), canonical_rir_hash(second))

    def test_hashing_rejects_invalid_rir(self):
        value = minimal_rir()
        value["schemaVersion"] = "wrong"
        with self.assertRaises(ContractError):
            canonical_rir_hash(value)

    def test_minimal_run_contract_validates(self):
        self.assertEqual(RUN_SCHEMA_ID, "design-lab/reconstruction-run/v1")
        validate_run_contract(minimal_run_contract())

    def test_versioned_artifact_roles_hashes_and_producers_are_strict(self):
        value = minimal_run_contract()
        value["artifacts"][0].update(
            {
                "role": "sanitized-svg",
                "sha256": "b" * 64,
                "producer": "rir-svg-serializer-v1",
            }
        )
        value["artifacts"][1].update(
            {
                "role": "diff-evidence",
                "producer": "fidelity-metrics-v1",
            }
        )
        validate_run_contract(value)

        uppercase = copy.deepcopy(value)
        uppercase["artifacts"][0]["sha256"] = "B" * 64
        with self.assertRaisesRegex(ContractError, "sha256"):
            validate_run_contract(uppercase)

        wrong_producer = copy.deepcopy(value)
        wrong_producer["artifacts"][0]["producer"] = "resvg-v0.47.0"
        with self.assertRaisesRegex(ContractError, "producer|role"):
            validate_run_contract(wrong_producer)

        duplicate_role = copy.deepcopy(value)
        duplicate_role["artifacts"][1].update(
            {
                "kind": "vector-output",
                "role": "sanitized-svg",
                "producer": "rir-svg-serializer-v1",
            }
        )
        with self.assertRaisesRegex(ContractError, "duplicate artifact role"):
            validate_run_contract(duplicate_role)

    def test_pipeline_artifact_roles_are_typed_and_checkpoint_role_can_repeat(self):
        value = minimal_run_contract("pipeline-contract")
        runtime_root = value["roots"]["runtime"]
        additions = [
            {
                "id": "rir-input",
                "kind": "rir-input",
                "path": runtime_root + "input.rir.json",
                "role": "reconstruction-rir",
                "producer": "explicit-rir-v1",
                "sha256": "1" * 64,
            },
            {
                "id": "pipeline-journal",
                "kind": "journal",
                "path": runtime_root + "journal.json",
                "role": "pipeline-journal",
                "producer": "reconstruction-pipeline-v1",
            },
            {
                "id": "pipeline-metrics",
                "kind": "metrics",
                "path": runtime_root + "metrics.json",
                "role": "pipeline-metrics",
                "producer": "fidelity-metrics-v1",
            },
            {
                "id": "checkpoint-created",
                "kind": "checkpoint",
                "path": runtime_root + "checkpoints/0001.json",
                "role": "pipeline-checkpoint",
                "producer": "reconstruction-pipeline-v1",
            },
            {
                "id": "checkpoint-analyzed",
                "kind": "checkpoint",
                "path": runtime_root + "checkpoints/0002.json",
                "role": "pipeline-checkpoint",
                "producer": "reconstruction-pipeline-v1",
            },
        ]
        value["artifacts"].extend(additions)
        value["writeAuthorization"]["targets"].extend(
            artifact["path"] for artifact in additions
        )
        validate_run_contract(value)

        wrong = copy.deepcopy(value)
        wrong["artifacts"][2]["producer"] = "reconstruction-pipeline-v1"
        with self.assertRaisesRegex(ContractError, "producer|role"):
            validate_run_contract(wrong)

        duplicate_singleton = copy.deepcopy(value)
        duplicate_singleton["artifacts"][4]["role"] = "pipeline-journal"
        duplicate_singleton["artifacts"][4]["kind"] = "journal"
        with self.assertRaisesRegex(ContractError, "duplicate artifact role"):
            validate_run_contract(duplicate_singleton)

    def test_invalid_profile_is_rejected(self):
        value = minimal_run_contract()
        value["profile"] = "illustration"
        with self.assertRaises(ContractError):
            validate_run_contract(value)

    def test_remote_provider_requires_exact_per_file_consent(self):
        value = minimal_run_contract()
        value["providerPolicy"]["selectedProvider"] = "remote-v1"
        with self.assertRaisesRegex(ContractError, "consent"):
            validate_run_contract(value)

        value["providerPolicy"]["remoteConsents"] = [
            {
                "path": value["source"]["path"],
                "sha256": value["source"]["sha256"],
                "provider": "remote-v1",
                "consented": True,
            }
        ]
        validate_run_contract(value)

    def test_remote_consent_rejects_wrong_hash_provider_and_extra_file(self):
        valid = minimal_run_contract()
        valid["providerPolicy"]["selectedProvider"] = "remote-v1"
        matching = {
            "path": valid["source"]["path"],
            "sha256": valid["source"]["sha256"],
            "provider": "remote-v1",
            "consented": True,
        }
        cases = {
            "wrong hash": [{**matching, "sha256": "b" * 64}],
            "wrong provider": [{**matching, "provider": "remote-v2"}],
            "extra file": [matching, {**matching, "path": "inputs/other.png"}],
        }
        for name, consents in cases.items():
            with self.subTest(name=name):
                value = copy.deepcopy(valid)
                value["providerPolicy"]["remoteConsents"] = consents
                with self.assertRaisesRegex(ContractError, "consent"):
                    validate_run_contract(value)

    def test_local_provider_rejects_remote_consent_entries(self):
        value = minimal_run_contract()
        value["providerPolicy"]["remoteConsents"] = [
            {
                "path": value["source"]["path"],
                "sha256": value["source"]["sha256"],
                "provider": "remote-v1",
                "consented": True,
            }
        ]
        with self.assertRaisesRegex(ContractError, "consent"):
            validate_run_contract(value)

    def test_expired_write_authorization_is_rejected(self):
        value = minimal_run_contract()
        value["writeAuthorization"]["expiresAt"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        with self.assertRaisesRegex(ContractError, "expired"):
            validate_run_contract(value)

    def test_target_mismatched_write_authorization_is_rejected(self):
        value = minimal_run_contract()
        value["writeAuthorization"]["targets"] = [value["roots"]["runtime"] + "other.svg"]
        with self.assertRaisesRegex(ContractError, "targets"):
            validate_run_contract(value)

    def test_invalid_lifecycle_promotion_is_rejected(self):
        value = minimal_run_contract()
        value["lifecycle"] = {
            "state": "completed",
            "history": [
                {
                    "from": "created",
                    "to": "completed",
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
        with self.assertRaisesRegex(ContractError, "lifecycle"):
            validate_run_contract(value)

    def test_lifecycle_history_must_start_at_created(self):
        value = minimal_run_contract()
        value["lifecycle"] = {
            "state": "completed",
            "history": [
                {
                    "from": "running",
                    "to": "completed",
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
        with self.assertRaisesRegex(ContractError, "created"):
            validate_run_contract(value)

    def test_artifact_and_write_targets_reject_unsafe_paths(self):
        run_id = "run-001"
        runtime_root = f".project-local/task-runtime/reconstruction/{run_id}/"
        unsafe_paths = (
            "https://example.test/output.svg",
            "/absolute/output.svg",
            "C:\\absolute\\output.svg",
            runtime_root + "../escape.svg",
            "design-lab/output.svg",
        )
        for target_field in ("artifact", "authorization"):
            for unsafe in unsafe_paths:
                with self.subTest(target_field=target_field, unsafe=unsafe):
                    value = minimal_run_contract(run_id)
                    if target_field == "artifact":
                        value["artifacts"][0]["path"] = unsafe
                        value["writeAuthorization"]["targets"][0] = unsafe
                    else:
                        value["writeAuthorization"]["targets"][0] = unsafe
                    with self.assertRaises(ContractError):
                        validate_run_contract(value)

    def test_artifact_and_authorization_reparse_root_escape_is_rejected(self):
        for target_field in ("artifact", "authorization"):
            with self.subTest(target_field=target_field):
                run_id = f"run-reparse-{target_field}-{os.getpid()}"
                runtime_dir = (
                    PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction" / run_id
                )
                link = runtime_dir / "escape"
                self._make_directory_link(link, DESIGN_LAB)
                value = minimal_run_contract(run_id)
                escaped = value["roots"]["runtime"] + "escape/output.svg"
                if target_field == "artifact":
                    value["artifacts"][0]["path"] = escaped
                    value["writeAuthorization"]["targets"][0] = escaped
                    expected = r"artifacts\[0\].*outside"
                else:
                    value["writeAuthorization"]["targets"][0] = escaped
                    expected = r"writeAuthorization\.targets\[0\].*outside"
                with self.assertRaisesRegex(ContractError, expected):
                    validate_run_contract(value)

    def test_declared_runtime_root_cannot_be_a_reparse_point(self):
        run_id = f"run-root-reparse-{os.getpid()}"
        runtime_dir = PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction" / run_id
        self._make_directory_link(
            runtime_dir,
            PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction-dev",
        )
        value = minimal_run_contract(run_id)
        with self.assertRaisesRegex(ContractError, "roots.*reparse|reparse.*roots"):
            validate_run_contract(value)

    def test_unknown_operation_and_authorization_state_are_rejected(self):
        for field, invalid in (
            ("requestedOperations", ["upload"]),
            ("writeAuthorization.state", "pending"),
        ):
            with self.subTest(field=field):
                value = copy.deepcopy(minimal_run_contract())
                if field == "requestedOperations":
                    value[field] = invalid
                else:
                    value["writeAuthorization"]["state"] = invalid
                with self.assertRaises(ContractError):
                    validate_run_contract(value)


class RuntimeRootMigrationTests(unittest.TestCase):
    """PR115-F06 / DL-TP-R0-003: active reconstruction mainline must resolve
    run/evidence roots through .project-local; legacy .hermes roots are rejected."""

    def test_legacy_hermes_runtime_root_is_rejected(self):
        """A run contract declaring .hermes roots must not validate."""
        value = minimal_run_contract("run-legacy")
        value["roots"] = {
            "runtime": ".hermes/task-runtime/reconstruction/run-legacy/",
            "evidence": ".hermes/task-artifacts/reconstruction/run-legacy/",
        }
        with self.assertRaisesRegex(ContractError, "roots"):
            validate_run_contract(value)

    def test_resolver_points_at_project_local(self):
        from reconstruction import runtime_roots

        self.assertTrue(runtime_roots.RUNTIME_REL.startswith(".project-local/"))
        self.assertTrue(runtime_roots.EVIDENCE_REL.startswith(".project-local/"))
        self.assertTrue(runtime_roots.LEGACY_RUNTIME_REL.startswith(".hermes/"))

    def test_mainline_modules_have_no_active_hermes_write(self):
        """R0-003 DoD: rg finds no .hermes write in active reconstruction mainline."""

        module_files = sorted(
            (PROJECT_ROOT / "packages" / "capabilities" / "reconstruction").glob("*.py")
        )
        for path in module_files:
            if path.name == "runtime_roots.py":
                continue  # resolver intentionally names the legacy root for rejection
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                ".hermes/task-runtime", text, f"{path.name} still writes legacy runtime root"
            )
            self.assertNotIn(
                ".hermes/task-artifacts", text, f"{path.name} still writes legacy evidence root"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
