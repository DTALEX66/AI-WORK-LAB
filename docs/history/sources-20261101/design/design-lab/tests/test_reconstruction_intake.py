# SPDX-License-Identifier: MIT
"""Deterministic reconstruction image-intake tests."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest
import uuid
import zlib
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageCms

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
FIXTURE = DESIGN_LAB / "tests" / "fixtures" / "reconstruction" / "flat-64.png"
if str(DESIGN_LAB) not in sys.path:
    sys.path.insert(0, str(DESIGN_LAB))
# DL-DIR-MIG-R1: reconstruction package moved to packages/capabilities/reconstruction
_PKG_ROOT = PROJECT_ROOT / "packages" / "capabilities"
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import reconstruction.intake as intake_module  # noqa: E402
from reconstruction.intake import (  # noqa: E402
    IntakeError,
    ReconstructionProfile,
    classify_reconstruction_profile,
    normalize_reference,
    partition_analysis_tiles,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_with_dimensions(width: int, height: int) -> bytes:
    """Build a tiny PNG container with a literal IHDR for invalid-dimension tests."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")


def _resolved_requirement_specs(path: Path, seen: set[Path] | None = None) -> set[str]:
    """Resolve pip -r includes so the test exercises the root install manifest."""

    resolved = path.resolve(strict=True)
    visited = set() if seen is None else seen
    if resolved in visited:
        return set()
    visited.add(resolved)
    specs: set[str] = set()
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r ") or line.startswith("--requirement "):
            include = line.split(maxsplit=1)[1]
            specs.update(_resolved_requirement_specs(resolved.parent / include, visited))
        else:
            specs.add(line)
    return specs


def _make_directory_reparse(target: Path, link: Path) -> None:
    """Create a directory symlink, with an unprivileged Windows junction fallback."""

    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError) as symlink_error:
        if os.name != "nt":
            raise symlink_error
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OSError(f"cannot create Windows junction (exit {completed.returncode})")


def _remove_directory_reparse(link: Path) -> None:
    """Remove only the link itself on POSIX and Windows, never its target."""

    if link.is_symlink():
        link.unlink()
    else:
        # Windows directory junctions are reparse directories, not symlinks.
        link.rmdir()


def _intake_run_contract(
    source: Path,
    run_id: str,
    *,
    width: int = 64,
    height: int = 64,
    profile: str = "flat",
) -> dict:
    runtime = f".project-local/task-runtime/reconstruction/{run_id}/"
    normalized = runtime + "reference.normalized.png"
    source_rel = source.resolve().relative_to(PROJECT_ROOT).as_posix()
    now = datetime.now(timezone.utc)
    return {
        "schemaVersion": "design-lab/reconstruction-run/v1",
        "runId": run_id,
        "jobId": "job-intake",
        "source": {
            "sourceId": "source-intake",
            "path": source_rel,
            "sha256": sha256(source),
            "profileMetadata": {"name": "reference", "version": "1"},
            "normalizedReferenceTarget": normalized,
        },
        "profile": profile,
        "canvasPolicy": {
            "width": width,
            "height": height,
            "colorSpace": "srgb",
            "globalCoordinates": "source-pixel",
            "tilePolicy": {
                "enabled": width > 4096 or height > 4096,
                "tileWidth": 4096,
                "tileHeight": 4096,
                "overlap": 0,
            },
        },
        "roots": {
            "runtime": runtime,
            "evidence": f".project-local/task-artifacts/reconstruction/{run_id}/",
        },
        "providerPolicy": {
            "defaultProvider": "local",
            "providerAllowlist": ["local"],
            "selectedProvider": "local",
            "remoteConsents": [],
        },
        "writeAuthorization": {
            "authorizationId": "auth-intake",
            "jobId": "job-intake",
            "runId": run_id,
            "targets": [normalized],
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
        "requestedOperations": ["analyze"],
        "cancellationPolicy": {
            "cancelable": True,
            "resume": "checkpoint",
            "checkpointPath": runtime + "checkpoint.json",
        },
        "artifacts": [
            {"id": "normalized", "kind": "normalized-source", "path": normalized}
        ],
    }


class ReconstructionIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        root = PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction-tests"
        self.token = uuid.uuid4().hex
        self.scratch = root / self.token
        self.scratch.mkdir(parents=True)
        self.canonical_runtime_root = (
            PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction"
        )
        self.run_dirs: list[Path] = []

    def tearDown(self) -> None:
        for run_dir in reversed(self.run_dirs):
            if run_dir.exists() and not run_dir.is_symlink():
                shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(self.scratch, ignore_errors=True)

    def run_dir(self, label: str) -> Path:
        path = self.canonical_runtime_root / f"test-{self.token}-{label}"
        self.run_dirs.append(path)
        return path

    def contract_for(
        self,
        source: Path,
        label: str,
        *,
        width: int = 64,
        height: int = 64,
        profile: str = "flat",
    ) -> tuple[dict, Path]:
        run_dir = self.run_dir(label)
        return (
            _intake_run_contract(
                source,
                run_dir.name,
                width=width,
                height=height,
                profile=profile,
            ),
            run_dir,
        )

    def normalize(
        self,
        source: Path,
        label: str,
        *,
        width: int = 64,
        height: int = 64,
        profile: str = "flat",
        max_axis: int = 4096,
    ):
        contract, run_dir = self.contract_for(
            source,
            label,
            width=width,
            height=height,
            profile=profile,
        )
        return normalize_reference(
            source,
            run_dir,
            max_axis=max_axis,
            run_contract=contract,
        )

    def _save(self, name: str, mode: str, format_name: str, *, icc: bytes | None = None) -> Path:
        path = self.scratch / name
        color = (12, 34, 56, 78) if mode == "RGBA" else (12, 34, 56)
        image = Image.new(mode, (7, 5), color)
        kwargs = {"lossless": True} if format_name == "WEBP" else {}
        if icc is not None:
            kwargs["icc_profile"] = icc
        image.save(path, format=format_name, **kwargs)
        return path

    def test_tracked_fixture_matches_literal_first_party_recipe_and_sidecar(self) -> None:
        with Image.open(FIXTURE) as image:
            self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGBA", (64, 64)))
            pixels = image.load()
            for y in range(64):
                for x in range(64):
                    # Hand-authored four-quadrant recipe used to generate this fixture.
                    expected = (
                        (20, 40, 80, 255)
                        if x < 32 and y < 32
                        else (230, 70, 50, 255)
                        if x >= 32 and y < 32
                        else (40, 190, 110, 192)
                        if x < 32
                        else (245, 210, 60, 64)
                    )
                    self.assertEqual(pixels[x, y], expected)

        sidecar = json.loads(Path(str(FIXTURE) + ".license").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["schemaVersion"], "design-lab/asset-sidecar/v1")
        self.assertEqual(sidecar["file"], "design-lab/tests/fixtures/reconstruction/flat-64.png")
        self.assertEqual(sidecar["sha256"], "sha256:" + sha256(FIXTURE))
        self.assertEqual(sidecar["license"], "MIT")
        self.assertIn("DTALEX66", sidecar["author"])

    def test_png_jpeg_and_webp_rgb_rgba_inputs_are_normalized_without_source_mutation(self) -> None:
        sources = [
            (FIXTURE, "PNG", "RGBA"),
            (self._save("photo.jpg", "RGB", "JPEG"), "JPEG", "RGB"),
            (self._save("surface.webp", "RGB", "WEBP"), "WEBP", "RGB"),
        ]
        for index, (source, expected_format, expected_mode) in enumerate(sources):
            with self.subTest(expected_format):
                expected_size = (64, 64) if source == FIXTURE else (7, 5)
                contract, run_dir = self.contract_for(
                    source,
                    f"format-{index}",
                    width=expected_size[0],
                    height=expected_size[1],
                )
                before = source.read_bytes()
                result = normalize_reference(source, run_dir, run_contract=contract)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(result.source_sha256, hashlib.sha256(before).hexdigest())
                self.assertEqual(result.source_identity.sha256, result.source_sha256)
                self.assertEqual(result.source_identity.resolved_path, source.resolve())
                self.assertEqual(result.source_identity.size_bytes, len(before))
                self.assertEqual(result.source_format, expected_format)
                self.assertEqual(result.original_mode, expected_mode)
                self.assertEqual(result.mode, "RGBA")
                self.assertEqual((result.width, result.height), expected_size)
                self.assertEqual(result.color_profile.origin, "assumed-srgb")
                self.assertIsNone(result.color_profile.icc_sha256)
                self.assertTrue(result.normalized_path.is_relative_to(run_dir))
                self.assertEqual(result.normalized_sha256, sha256(result.normalized_path))
                with Image.open(result.normalized_path) as normalized:
                    self.assertEqual((normalized.format, normalized.mode, normalized.size), (
                        "PNG", "RGBA", (result.width, result.height)
                    ))

                with self.assertRaises(FrozenInstanceError):
                    result.source_identity.size_bytes = 0  # type: ignore[misc]

    def test_alpha_and_embedded_profile_are_preserved_and_recorded(self) -> None:
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        source = self._save("profiled.png", "RGBA", "PNG", icc=profile.tobytes())
        result = self.normalize(source, "profiled", width=7, height=5)
        self.assertEqual(result.color_profile.origin, "embedded")
        self.assertEqual(
            result.color_profile.icc_sha256,
            hashlib.sha256(profile.tobytes()).hexdigest(),
        )
        self.assertIn("sRGB", result.color_profile.name)
        with Image.open(result.normalized_path) as normalized:
            self.assertEqual(normalized.getpixel((0, 0))[3], 78)
            self.assertIn("icc_profile", normalized.info)

    def test_invalid_embedded_profile_fails_before_output(self) -> None:
        source = self._save("bad-profile.png", "RGB", "PNG", icc=b"not-an-icc-profile")
        contract, run_dir = self.contract_for(source, "bad-profile", width=7, height=5)
        with self.assertRaises(IntakeError):
            normalize_reference(source, run_dir, run_contract=contract)
        self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_corrupt_zero_dimension_mode_and_format_inputs_fail_closed(self) -> None:
        invalid_sources: list[Path] = []
        corrupt = self.scratch / "corrupt.png"
        corrupt.write_bytes(b"not a PNG")
        invalid_sources.append(corrupt)
        zero = self.scratch / "zero.png"
        zero.write_bytes(_png_with_dimensions(0, 1))
        invalid_sources.append(zero)
        grayscale = self.scratch / "grayscale.png"
        Image.new("L", (2, 2), 128).save(grayscale, format="PNG")
        invalid_sources.append(grayscale)
        bitmap = self.scratch / "bitmap.bmp"
        Image.new("RGB", (2, 2), (1, 2, 3)).save(bitmap, format="BMP")
        invalid_sources.append(bitmap)

        for index, source in enumerate(invalid_sources):
            contract, run_dir = self.contract_for(source, f"invalid-{index}", width=2, height=2)
            with self.subTest(source.name), self.assertRaises(IntakeError):
                normalize_reference(source, run_dir, run_contract=contract)
            self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_normalization_is_byte_deterministic_across_runs(self) -> None:
        first = self.normalize(FIXTURE, "deterministic-a")
        second = self.normalize(FIXTURE, "deterministic-b")
        self.assertEqual(first.normalized_sha256, second.normalized_sha256)
        self.assertEqual(first.normalized_path.read_bytes(), second.normalized_path.read_bytes())

    def test_normalization_is_byte_deterministic_across_processes(self) -> None:
        code = (
            "from pathlib import Path; import json,sys; "
            "sys.path.insert(0, sys.argv[1]); "
            "sys.path.insert(0, sys.argv[5]); "
            "from reconstruction.intake import normalize_reference; "
            "r=normalize_reference(Path(sys.argv[2]), Path(sys.argv[3]), "
            "run_contract=json.loads(sys.argv[4])); "
            "print(r.normalized_sha256)"
        )
        hashes = []
        outputs = []
        for label in ("process-a", "process-b"):
            contract, run_dir = self.contract_for(FIXTURE, label)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    code,
                    str(DESIGN_LAB),
                    str(FIXTURE),
                    str(run_dir),
                    json.dumps(contract),
                    str(_PKG_ROOT),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            hashes.append(completed.stdout.strip())
            outputs.append((run_dir / "reference.normalized.png").read_bytes())
        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(outputs[0], outputs[1])
        self.assertRegex(hashes[0], r"^[0-9a-f]{64}$")

    def test_4097_axis_is_tiled_without_scaling_or_cropping(self) -> None:
        source = self.scratch / "wide.png"
        image = Image.new("RGB", (4097, 3), (3, 5, 7))
        image.putpixel((4096, 2), (251, 17, 99))
        image.save(source, format="PNG")
        result = self.normalize(source, "wide", width=4097, height=3)
        self.assertEqual((result.width, result.height), (4097, 3))
        self.assertEqual(
            [(tile.x, tile.y, tile.width, tile.height) for tile in result.tiles],
            [(0, 0, 4096, 3), (4096, 0, 1, 3)],
        )
        with Image.open(result.normalized_path) as normalized:
            self.assertEqual(normalized.size, (4097, 3))
            self.assertEqual(normalized.getpixel((4096, 2))[:3], (251, 17, 99))

    def test_tiles_cover_every_pixel_exactly_once_in_global_coordinates(self) -> None:
        width, height = 9, 7
        tiles = partition_analysis_tiles(width, height, max_axis=4)
        coverage = np.zeros((height, width), dtype=np.uint8)
        for expected_index, tile in enumerate(tiles):
            self.assertEqual(tile.index, expected_index)
            self.assertGreater(tile.width, 0)
            self.assertGreater(tile.height, 0)
            self.assertGreaterEqual(tile.x, 0)
            self.assertGreaterEqual(tile.y, 0)
            self.assertLessEqual(tile.right, width)
            self.assertLessEqual(tile.bottom, height)
            coverage[tile.y : tile.bottom, tile.x : tile.right] += 1
        np.testing.assert_array_equal(coverage, np.ones((height, width), dtype=np.uint8))

    def test_classifier_has_independently_derived_synthetic_expectations(self) -> None:
        flat = np.full((64, 64, 4), (30, 60, 90, 255), dtype=np.uint8)
        ui = np.zeros((64, 64, 4), dtype=np.uint8)
        ui[:, :, 3] = 255
        checker = (np.indices((64, 64)).sum(axis=0) % 2) * 255
        ui[:, :, :3] = checker[:, :, None]
        mixed = np.zeros((64, 64, 4), dtype=np.uint8)
        mixed[:, :, 3] = 255
        mixed[:, :, :3] = np.arange(64, dtype=np.uint8)[None, :, None] * 4
        rng = np.random.default_rng(20260823)
        photographic = np.empty((64, 64, 4), dtype=np.uint8)
        photographic[:, :, :3] = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
        photographic[:, :, 3] = 255

        cases = [
            (flat, ReconstructionProfile.FLAT),
            (ui, ReconstructionProfile.UI),
            (mixed, ReconstructionProfile.MIXED),
            (photographic, ReconstructionProfile.PHOTOGRAPHIC),
        ]
        for pixels, expected in cases:
            with self.subTest(expected.value):
                self.assertEqual(classify_reconstruction_profile(pixels), expected)

    def test_classifier_ignores_rgb_values_of_fully_transparent_pixels(self) -> None:
        baseline = np.zeros((64, 64, 4), dtype=np.uint8)
        baseline[:, :32, :3] = (20, 40, 80)
        baseline[:, :32, 3] = 255
        hidden_noise = baseline.copy()
        rng = np.random.default_rng(404)
        hidden_noise[:, 32:, :3] = rng.integers(0, 256, (64, 32, 3), dtype=np.uint8)
        self.assertEqual(classify_reconstruction_profile(baseline), ReconstructionProfile.FLAT)
        self.assertEqual(
            classify_reconstruction_profile(hidden_noise),
            classify_reconstruction_profile(baseline),
        )

    def test_classifier_and_tiling_reject_invalid_inputs(self) -> None:
        for pixels in (
            np.zeros((0, 1, 4), dtype=np.uint8),
            np.zeros((2, 2, 2), dtype=np.uint8),
            np.zeros((2, 2, 4), dtype=np.float32),
        ):
            with self.subTest(pixels.shape), self.assertRaises(IntakeError):
                classify_reconstruction_profile(pixels)
        for width, height, max_axis in ((0, 1, 4), (1, 0, 4), (1, 1, 0), (1, 1, True)):
            with self.subTest((width, height, max_axis)), self.assertRaises(IntakeError):
                partition_analysis_tiles(width, height, max_axis)

    def test_parent_traversal_and_existing_reparse_destinations_are_rejected(self) -> None:
        traversing = self.scratch / "parent" / ".." / "run"
        traversal_contract, _ = self.contract_for(FIXTURE, "traversal-contract")
        with self.assertRaises(IntakeError):
            normalize_reference(FIXTURE, traversing, run_contract=traversal_contract)

        actual = self.scratch / "actual"
        actual.mkdir()
        link = self.run_dir("linked")
        try:
            _make_directory_reparse(actual, link)
        except OSError as exc:
            self.skipTest(f"directory reparse point unavailable: {exc}")
        try:
            link_contract = _intake_run_contract(FIXTURE, link.name)
            with self.assertRaises(IntakeError):
                normalize_reference(FIXTURE, link, run_contract=link_contract)
            self.assertFalse((actual / "reference.normalized.png").exists())
        finally:
            _remove_directory_reparse(link)

    def test_arbitrary_absolute_and_nested_runtime_destinations_are_rejected(self) -> None:
        arbitrary = self.scratch / "arbitrary-output"
        arbitrary_contract, _ = self.contract_for(FIXTURE, "arbitrary-contract")
        with self.assertRaises(IntakeError):
            normalize_reference(FIXTURE, arbitrary, run_contract=arbitrary_contract)
        self.assertFalse(arbitrary.exists())

        canonical_parent = self.run_dir("nested-parent")
        nested = canonical_parent / "child"
        nested_contract = _intake_run_contract(FIXTURE, canonical_parent.name)
        with self.assertRaises(IntakeError):
            normalize_reference(FIXTURE, nested, run_contract=nested_contract)
        self.assertFalse(nested.exists())

    def test_public_writer_requires_a_valid_run_contract(self) -> None:
        run_dir = self.run_dir("missing-contract")
        with self.assertRaises(TypeError):
            normalize_reference(FIXTURE, run_dir)
        self.assertFalse(run_dir.exists())

        contract, authorized_run = self.contract_for(FIXTURE, "bad-authorization")
        unauthorized = copy.deepcopy(contract)
        unauthorized["writeAuthorization"]["targets"] = [
            unauthorized["roots"]["runtime"] + "other.png"
        ]
        with self.assertRaises(IntakeError):
            normalize_reference(FIXTURE, authorized_run, run_contract=unauthorized)
        self.assertFalse(authorized_run.exists())

        tile_contract, tile_run = self.contract_for(FIXTURE, "tile-mismatch")
        with self.assertRaises(IntakeError):
            normalize_reference(
                FIXTURE,
                tile_run,
                max_axis=2048,
                run_contract=tile_contract,
            )
        self.assertFalse(tile_run.exists())

    def test_source_replacement_after_contract_validation_is_rejected_before_baseline(self) -> None:
        source = self._save("replace-race.png", "RGBA", "PNG")
        contract, run_dir = self.contract_for(source, "replace-race", width=7, height=5)

        def replace_after_validation(_source: Path, _constraints: object) -> None:
            replacement = Image.new("RGBA", (7, 5), (200, 10, 30, 255))
            replacement.save(source, format="PNG")

        with mock.patch.object(
            intake_module,
            "_after_contract_validation",
            replace_after_validation,
        ):
            with self.assertRaises(IntakeError):
                normalize_reference(source, run_dir, run_contract=contract)
        self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_canvas_and_profile_mismatches_never_reach_atomic_replace(self) -> None:
        cases = ((63, 64, "flat", "canvas"), (64, 64, "ui", "profile"))
        for width, height, profile, label in cases:
            contract, run_dir = self.contract_for(
                FIXTURE,
                f"precommit-{label}",
                width=width,
                height=height,
                profile=profile,
            )
            with self.subTest(label), mock.patch.object(
                intake_module.os,
                "replace",
                wraps=os.replace,
            ) as replace:
                with self.assertRaises(IntakeError):
                    normalize_reference(FIXTURE, run_dir, run_contract=contract)
                replace.assert_not_called()
                self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_validated_contract_entrypoint_binds_source_authorization_and_runtime_root(self) -> None:
        run_id = f"test-{self.token}-contract"
        expected_run_dir = self.canonical_runtime_root / run_id
        self.run_dirs.append(expected_run_dir)
        contract = _intake_run_contract(FIXTURE, run_id)
        result = intake_module.normalize_reference_for_contract(FIXTURE, contract)
        self.assertEqual(result.normalized_path, expected_run_dir / "reference.normalized.png")

        invalid = _intake_run_contract(FIXTURE, f"test-{self.token}-invalid")
        invalid.pop("jobId")
        with self.assertRaises(IntakeError):
            intake_module.normalize_reference_for_contract(FIXTURE, invalid)

        mismatched = _intake_run_contract(FIXTURE, f"test-{self.token}-mismatch")
        mismatched["source"]["normalizedReferenceTarget"] = "normalized/source.png"
        mismatch_run = self.canonical_runtime_root / mismatched["runId"]
        self.run_dirs.append(mismatch_run)
        with self.assertRaises(IntakeError):
            intake_module.normalize_reference_for_contract(FIXTURE, mismatched)
        self.assertFalse(mismatch_run.exists())

        wrong_hash = _intake_run_contract(FIXTURE, f"test-{self.token}-wrong-hash")
        wrong_hash["source"]["sha256"] = "0" * 64
        wrong_hash_run = self.canonical_runtime_root / wrong_hash["runId"]
        self.run_dirs.append(wrong_hash_run)
        with self.assertRaises(IntakeError):
            intake_module.normalize_reference_for_contract(FIXTURE, wrong_hash)
        self.assertFalse(wrong_hash_run.exists())

    def test_source_identity_is_rechecked_after_output_commit(self) -> None:
        source = self._save("race.png", "RGBA", "PNG")
        contract, run_dir = self.contract_for(source, "race", width=7, height=5)

        def mutate_after_commit(path: Path, _destination: Path) -> None:
            path.write_bytes(path.read_bytes() + b"source-changed")

        with mock.patch.object(intake_module, "_after_output_commit", mutate_after_commit):
            with self.assertRaises(IntakeError):
                normalize_reference(source, run_dir, run_contract=contract)
        self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_write_and_temporary_cleanup_failures_preserve_both_causes(self) -> None:
        contract, run_dir = self.contract_for(FIXTURE, "temp-cleanup")
        real_unlink = Path.unlink

        def reject_temp_unlink(path: Path, *args, **kwargs) -> None:
            if path.name.startswith(".reference.normalized.") and path.suffix == ".tmp":
                raise OSError("locked temporary residue")
            real_unlink(path, *args, **kwargs)

        with (
            mock.patch.object(intake_module.os, "replace", side_effect=OSError("replace failed")),
            mock.patch.object(Path, "unlink", new=reject_temp_unlink),
        ):
            with self.assertRaises(IntakeError) as caught:
                normalize_reference(FIXTURE, run_dir, run_contract=contract)

        message = str(caught.exception)
        self.assertIn("cannot write normalized output safely: replace failed", message)
        self.assertIn(
            "temporary normalized-output residue cleanup failed: locked temporary residue",
            message,
        )
        chain = caught.exception.__cause__
        self.assertIsInstance(chain, ExceptionGroup)
        self.assertEqual(len(chain.exceptions), 2)
        primary, cleanup = chain.exceptions
        self.assertIsInstance(primary, IntakeError)
        self.assertIn("replace failed", str(primary))
        self.assertIsInstance(primary.__cause__, OSError)
        self.assertIsInstance(cleanup, OSError)
        self.assertIn("locked temporary residue", str(cleanup))
        self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_write_failure_alone_preserves_primary_cause_and_cleans_temp(self) -> None:
        contract, run_dir = self.contract_for(FIXTURE, "write-only-failure")
        with (
            mock.patch.object(
                intake_module.os,
                "replace",
                side_effect=OSError("replace-only failure"),
            ),
            self.assertRaisesRegex(
                IntakeError,
                "cannot write normalized output safely: replace-only failure",
            ) as caught,
        ):
            normalize_reference(FIXTURE, run_dir, run_contract=contract)

        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIn("replace-only failure", str(caught.exception.__cause__))
        self.assertEqual(list(run_dir.glob(".reference.normalized.*.tmp")), [])
        self.assertFalse((run_dir / "reference.normalized.png").exists())

    def test_existing_output_symlink_is_rejected_without_touching_target(self) -> None:
        contract, run_dir = self.contract_for(FIXTURE, "output-link")
        run_dir.mkdir()
        outside = self.scratch / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel.bin"
        sentinel.write_bytes(b"sentinel")
        destination = run_dir / "reference.normalized.png"
        try:
            _make_directory_reparse(outside, destination)
        except OSError as exc:
            self.skipTest(f"output reparse point unavailable: {exc}")
        try:
            with self.assertRaises(IntakeError):
                normalize_reference(FIXTURE, run_dir, run_contract=contract)
            self.assertEqual(sentinel.read_bytes(), b"sentinel")
        finally:
            _remove_directory_reparse(destination)

    def test_root_requirements_install_manifest_resolves_core_dependencies(self) -> None:
        specs = _resolved_requirement_specs(PROJECT_ROOT / "requirements.txt")
        self.assertTrue(
            {
                "Pillow>=11.3,<13",
                "numpy>=2.2,<3",
                "scikit-image>=0.25,<0.27",
                "defusedxml>=0.7,<1",
            }.issubset(specs),
            f"root requirements omit reconstruction dependencies: {sorted(specs)}",
        )


if __name__ == "__main__":
    unittest.main()
