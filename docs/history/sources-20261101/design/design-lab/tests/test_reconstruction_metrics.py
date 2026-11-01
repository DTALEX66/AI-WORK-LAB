# SPDX-License-Identifier: MIT
"""Deterministic renderer and fidelity-gate regression tests."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "design-lab"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "capabilities"))

from reconstruction.metrics import (  # noqa: E402
    FidelityError,
    compare_images,
    pixelmatch_masks,
)
from reconstruction.render import (  # noqa: E402
    RenderError,
    load_render_profile,
    render_svg,
)
from reconstruction.svg import serialize_svg  # noqa: E402

REGISTRY = REPO_ROOT / "design-lab" / "config" / "reconstruction-tools.json"
if os.name == "nt":
    REAL_RESVG = Path(
        r"D:\All projects\Design External Configuration\toolchains\resvg\v0.47.0\resvg.exe"
    )
    REAL_RESVG_SHA256 = "433a7c744cff561ed64fcf73c7c04e239d7a07ae5f0aadbf1ba8471d63707402"
else:
    REAL_RESVG = Path("/opt/resvg/v0.47.0/resvg")
    REAL_RESVG_SHA256 = "a53a45eafcaf3c04ceefc0c150c3d10fdf582d143d1ca5e4a7a64e661c55f02e"
# Fixed Windows resvg executable SHA used to assert the resvgWindows registry entry.
EXPECTED_RESVG_SHA256 = (
    "433a7c744cff561ed64fcf73c7c04e239d7a07ae5f0aadbf1ba8471d63707402"
)
APPROVED_ICC_ID = "canonical-srgb-pillow-12.3.0-lcms-2.19"
ICC_CANONICALIZATION = "zero-icc-header-creation-date-v1"
APPROVED_ICC_SHA256 = "215d9fadbfc938862a82f2633b51fee128b58767f7d7ac55d32cb7e00031bb0d"
FLAT_FIXTURE = REPO_ROOT / "design-lab" / "tests" / "fixtures" / "reconstruction" / "flat-64.png"


def _rgba(width: int, height: int, value=(0, 0, 0, 255)) -> np.ndarray:
    pixels = np.empty((height, width, 4), dtype=np.uint8)
    pixels[:, :] = value
    return pixels


def _save_rgba(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(pixels, mode="RGBA").save(path, format="PNG", optimize=False)


def _official_yiq_delta(gray_delta: int) -> float:
    """Literal v7.2.0 opaque-gray formula, independent of production code."""

    dr = dg = db = float(gray_delta)
    y = dr * 0.29889531 + dg * 0.58662247 + db * 0.11448223
    i = dr * 0.59597799 - dg * 0.27417610 - db * 0.32180189
    q = dr * 0.21147017 - dg * 0.52261711 + db * 0.31114694
    return 0.5053 * y * y + 0.299 * i * i + 0.1957 * q * q


def _run_contract(
    run_root: Path,
    artifacts: dict[Path, str],
    *,
    width: int,
    height: int,
    lifecycle_state: str = "authorized",
    expired: bool = False,
    normalized_reference: Path | None = None,
    artifact_metadata: dict[Path, dict] | None = None,
) -> dict:
    run_id = run_root.name
    runtime_root = f".project-local/task-runtime/reconstruction/{run_id}/"
    evidence_root = f".project-local/task-artifacts/reconstruction/{run_id}/"
    now = datetime.now(timezone.utc)
    targets = [path.relative_to(REPO_ROOT).as_posix() for path in artifacts]
    history = [
        {
            "from": "created",
            "to": "authorized",
            "at": (now - timedelta(minutes=2)).isoformat(),
        }
    ]
    if lifecycle_state == "running":
        history.append(
            {
                "from": "authorized",
                "to": "running",
                "at": (now - timedelta(minutes=1)).isoformat(),
            }
        )
    normalized_target = (
        runtime_root + "reference.normalized.png"
        if normalized_reference is None
        else normalized_reference.relative_to(REPO_ROOT).as_posix()
    )
    metadata_overrides = artifact_metadata or {}
    evidence_paths = [path for path, kind in artifacts.items() if kind == "evidence"]

    def artifact_record(index: int, path: Path, kind: str, target: str) -> dict:
        if kind == "normalized-source":
            role, producer = "normalized-reference", "intake-normalizer-v1"
        elif kind == "vector-output":
            role, producer = "sanitized-svg", "rir-svg-serializer-v1"
        elif "diff" in path.name.casefold() or (
            len(evidence_paths) > 1 and path == evidence_paths[-1]
        ):
            role, producer = "diff-evidence", "fidelity-metrics-v1"
        else:
            role, producer = "render-preview", "resvg-v0.47.0"
        record = {
            "id": f"artifact-{index}",
            "kind": kind,
            "path": target,
            "role": role,
            "producer": producer,
        }
        if path.is_file():
            record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        record.update(metadata_overrides.get(path, {}))
        return record

    return {
        "schemaVersion": "design-lab/reconstruction-run/v1",
        "runId": run_id,
        "jobId": f"job-{run_id}",
        "source": {
            "sourceId": "source-c4",
            "path": "design-lab/tests/fixtures/reconstruction/flat-64.png",
            "sha256": "a" * 64,
            "profileMetadata": {"name": "reference", "version": "1"},
            "normalizedReferenceTarget": normalized_target,
        },
        "profile": "flat",
        "canvasPolicy": {
            "width": width,
            "height": height,
            "colorSpace": "srgb",
            "globalCoordinates": "source-pixel",
            "tilePolicy": {
                "enabled": False,
                "tileWidth": width,
                "tileHeight": height,
                "overlap": 0,
            },
        },
        "roots": {"runtime": runtime_root, "evidence": evidence_root},
        "providerPolicy": {
            "defaultProvider": "local",
            "providerAllowlist": ["local"],
            "selectedProvider": "local",
            "remoteConsents": [],
        },
        "writeAuthorization": {
            "authorizationId": f"auth-{run_id}",
            "jobId": f"job-{run_id}",
            "runId": run_id,
            "targets": targets,
            "issuedAt": (now - timedelta(minutes=3)).isoformat(),
            "expiresAt": (
                now - timedelta(minutes=1) if expired else now + timedelta(hours=1)
            ).isoformat(),
            "state": "authorized",
        },
        "registries": {
            "toolRegistry": "design-lab/config/reconstruction-tools.json",
            "modelRegistry": "design-lab/config/reconstruction-models.json",
        },
        "lifecycle": {"state": lifecycle_state, "history": history},
        "requestedOperations": ["reconstruct", "verify"],
        "cancellationPolicy": {
            "cancelable": True,
            "resume": "checkpoint",
            "checkpointPath": runtime_root + "checkpoints/state.json",
        },
        "artifacts": [
            artifact_record(index, path, kind, target)
            for index, ((path, kind), target) in enumerate(zip(artifacts.items(), targets))
        ],
    }


def _header_only_png(width: int, height: int) -> bytes:
    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 6, 0, 0, 0))
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", b"")
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return len(payload).to_bytes(4, "big") + kind + payload + crc.to_bytes(4, "big")


def _streamed_zero_png(width: int, height: int, *, color_type: int = 6) -> bytes:
    channels = 4 if color_type == 6 else 3
    compressor = zlib.compressobj()
    compressed = bytearray()
    row = bytes(1 + width * channels)
    for _ in range(height):
        compressed.extend(compressor.compress(row))
    compressed.extend(compressor.flush())
    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, color_type, 0, 0, 0))
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", bytes(compressed))
        + _png_chunk(b"IEND", b"")
    )


def _approved_icc_profile_bytes(
    creation_date: bytes = bytes.fromhex("07ea000800160015002f0002"),
) -> bytes:
    from reconstruction.intake import _canonical_srgb_profile_bytes

    profile = bytearray(_canonical_srgb_profile_bytes())
    profile[24:36] = creation_date
    payload = bytes(profile)
    assert len(payload) == 588
    canonical = bytearray(payload)
    canonical[24:36] = bytes(12)
    assert hashlib.sha256(canonical).hexdigest() == APPROVED_ICC_SHA256
    return payload


class ReconstructionMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        safe_name = "".join(c if c.isalnum() else "-" for c in self._testMethodName)
        self.run_root = (
            REPO_ROOT
            / ".project-local"
            / "task-runtime"
            / "reconstruction"
            / f"c4-{os.getpid()}-{safe_name}"
        )
        if self.run_root.exists():
            shutil.rmtree(self.run_root)
        self.run_root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.run_root, True)
        self.profile = load_render_profile(128, 128, REAL_RESVG)

    def compare(
        self,
        reference: np.ndarray,
        actual: np.ndarray,
        *,
        profile=None,
        diff_name: str = "diff.png",
    ):
        reference_path = self.run_root / "reference.png"
        actual_path = self.run_root / "actual.png"
        _save_rgba(reference_path, reference)
        _save_rgba(actual_path, actual)
        active_profile = profile or dataclasses.replace(
            self.profile,
            width=reference.shape[1],
            height=reference.shape[0],
        )
        diff_path = self.run_root / diff_name
        contract = _run_contract(
            self.run_root,
            {
                reference_path: "normalized-source",
                actual_path: "evidence",
                diff_path: "evidence",
            },
            width=reference.shape[1],
            height=reference.shape[0],
            normalized_reference=reference_path,
        )
        return compare_images(
            reference_path,
            actual_path,
            profile=active_profile,
            diff_output_path=diff_path,
            run_contract=contract,
        )

    def test_registry_and_profile_pin_every_fixed_gate_owner(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["schemaVersion"], "design-lab/reconstruction-tools/v1")

        resvg = registry["renderers"]["resvgWindows"]
        self.assertEqual(resvg["repository"], "linebender/resvg")
        self.assertEqual(resvg["version"], "0.47.0")
        self.assertEqual(resvg["asset"], "resvg-win64.zip")
        self.assertEqual(
            resvg["url"],
            "https://github.com/linebender/resvg/releases/download/v0.47.0/resvg-win64.zip",
        )
        self.assertEqual(
            resvg["archiveSha256"],
            "5684e59ceaa53ce720b49efb441b0918ae99d04e8ce3f6f753664524592d67f1",
        )
        self.assertEqual(resvg["executableSha256"], EXPECTED_RESVG_SHA256)
        self.assertEqual(resvg["license"], "Apache-2.0 OR MIT")
        self.assertEqual(
            resvg["storageClass"], "Design External Configuration/toolchain"
        )
        self.assertEqual(registry["upstreamStable"]["version"], "0.48.1")
        self.assertEqual(
            registry["upstreamStable"]["windowsX86_64OfficialBinary"],
            "WINDOWS_X86_64_OFFICIAL_BINARY_UNAVAILABLE",
        )

        pixelmatch = registry["metrics"]["pixelmatch"]
        self.assertEqual(pixelmatch["package"], "mapbox/pixelmatch")
        self.assertEqual(pixelmatch["version"], "7.2.0")
        self.assertEqual(pixelmatch["algorithm"], "YIQ-v7.2.0")
        self.assertEqual(pixelmatch["license"], "ISC")
        self.assertEqual(
            pixelmatch["source"],
            "https://raw.githubusercontent.com/mapbox/pixelmatch/v7.2.0/index.js",
        )
        self.assertNotIn("OKLab", json.dumps(pixelmatch))
        self.assertNotIn("HyAB", json.dumps(pixelmatch))
        self.assertEqual(pixelmatch["attribution"], "Copyright (c) 2025, Mapbox")

        self.assertEqual(
            registry["approvedIccProfiles"],
            [
                {
                    "id": APPROVED_ICC_ID,
                    "source": "Pillow ImageCms.createProfile('sRGB')",
                    "generator": "Pillow.ImageCms.ImageCmsProfile.tobytes/v1 then canonicalize",
                    "pillowVersion": "12.3.0",
                    "lcmsVersion": "2.19",
                    "byteLength": 588,
                    "sha256": APPROVED_ICC_SHA256,
                    "colorSpace": "sRGB IEC61966-2.1",
                    "canonicalization": ICC_CANONICALIZATION,
                }
            ],
        )

        profile = load_render_profile(64, 96, REAL_RESVG)
        self.assertEqual(profile.profile_id, "design-lab/render-profile/v1")
        self.assertEqual((profile.width, profile.height), (64, 96))
        self.assertEqual(profile.color_space, "sRGB IEC61966-2.1")
        self.assertEqual(profile.rgba_background, (255, 255, 255, 255))
        self.assertEqual(profile.renderer_id, "linebender/resvg")
        self.assertEqual(profile.renderer_version, "0.47.0")
        self.assertEqual(profile.renderer_sha256, REAL_RESVG_SHA256)
        self.assertEqual(profile.pixelmatch_version, "7.2.0")
        self.assertEqual(profile.pixel_threshold, 0.1)
        self.assertTrue(profile.anti_alias_detection)
        self.assertEqual(profile.match_minimum, 0.995)
        self.assertEqual(profile.ssim_minimum, 0.995)
        self.assertEqual(profile.mae_limit_version, "uncalibrated-v1")
        self.assertIsNone(profile.mae_limit)
        self.assertEqual(profile.edge_metric, "sobel-rgb-l1/v1")
        self.assertEqual(profile.dense_connectivity, 8)
        self.assertEqual(profile.dense_bbox_exclusive_limit, 32)
        self.assertEqual(profile.dense_density_minimum, 0.25)
        self.assertEqual(profile.metric_max_pixels, 4_194_304)
        self.assertEqual(profile.metric_max_bytes, 67_108_864)
        self.assertEqual(profile.metric_budget_version, "c4-metric-memory-v1")

    def test_public_writes_require_valid_exact_run_contract_before_creation(self) -> None:
        source = self.run_root / "source.svg"
        source.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"></svg>',
            encoding="utf-8",
        )
        unauthorized_root = (
            REPO_ROOT
            / ".project-local"
            / "task-runtime"
            / "reconstruction"
            / f"c4-no-contract-{os.getpid()}"
        )
        self.addCleanup(shutil.rmtree, unauthorized_root, True)
        output = unauthorized_root / "preview.png"
        impostor = self.run_root / "impostor.exe"
        impostor.write_bytes(b"impostor")
        profile = load_render_profile(64, 64, impostor)
        with self.assertRaisesRegex(RenderError, "run contract"):
            render_svg(source, output, profile)
        self.assertFalse(unauthorized_root.exists())

        reference = _rgba(64, 64)
        reference_path = self.run_root / "reference-no-contract.png"
        actual_path = self.run_root / "actual-no-contract.png"
        _save_rgba(reference_path, reference)
        _save_rgba(actual_path, reference)
        diff = self.run_root / "diff-no-contract.png"
        with self.assertRaisesRegex(FidelityError, "run contract"):
            compare_images(
                reference_path,
                actual_path,
                profile=dataclasses.replace(self.profile, width=64, height=64),
                diff_output_path=diff,
            )
        self.assertFalse(diff.exists())

    def test_authorized_writes_reject_undeclared_or_wrong_role_inputs_and_outputs(self) -> None:
        pixels = _rgba(64, 64)
        reference = self.run_root / "normalized.png"
        actual = self.run_root / "preview.png"
        diff = self.run_root / "diff.png"
        _save_rgba(reference, pixels)
        _save_rgba(actual, pixels)
        profile = dataclasses.replace(self.profile, width=64, height=64)
        compare_contract = _run_contract(
            self.run_root,
            {actual: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
        )
        with self.assertRaisesRegex(FidelityError, "normalized-source|input artifact"):
            compare_images(
                reference,
                actual,
                profile=profile,
                diff_output_path=diff,
                run_contract=compare_contract,
            )
        wrong_actual_role = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "vector-output", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
        )
        with self.assertRaisesRegex(FidelityError, "actual preview.*evidence"):
            compare_images(
                reference,
                actual,
                profile=profile,
                diff_output_path=diff,
                run_contract=wrong_actual_role,
            )

        svg = self.run_root / "undeclared.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"></svg>',
            encoding="utf-8",
        )
        output = self.run_root / "authorized.png"
        with self.assertRaisesRegex(RenderError, "vector-output|input artifact"):
            render_svg(
                svg,
                output,
                profile,
                run_contract=_run_contract(
                    self.run_root,
                    {output: "evidence"},
                    width=64,
                    height=64,
                ),
            )

        wrong_output = self.run_root / "authorized-output.svg"
        with self.assertRaisesRegex(RenderError, r"evidence|\.png"):
            render_svg(
                svg,
                wrong_output,
                profile,
                run_contract=_run_contract(
                    self.run_root,
                    {svg: "vector-output", wrong_output: "evidence"},
                    width=64,
                    height=64,
                ),
            )

    def test_registry_trust_anchor_rejects_self_consistent_threshold_tampering(self) -> None:
        import reconstruction.render as render_module

        tampered = json.loads(REGISTRY.read_text(encoding="utf-8"))
        tampered["renderProfile"]["matchMinimum"] = 0.0
        tampered["renderProfile"]["ssimMinimum"] = 0.0
        tampered_path = self.run_root / "tampered-registry.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        with mock.patch.object(render_module, "_REGISTRY_PATH", tampered_path):
            with self.assertRaisesRegex(RenderError, "trusted|digest|anchor"):
                load_render_profile(64, 64)

    def test_contract_expected_input_hashes_are_authoritative_and_returned(self) -> None:
        pixels = _rgba(64, 64)
        reference = self.run_root / "hash-reference.png"
        actual = self.run_root / "hash-preview.png"
        diff = self.run_root / "hash-diff.png"
        _save_rgba(reference, pixels)
        _save_rgba(actual, pixels)
        contract = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
            artifact_metadata={actual: {"sha256": "b" * 64}},
        )
        with self.assertRaisesRegex(FidelityError, "expected.*sha256|SHA-256|hash"):
            compare_images(
                reference,
                actual,
                profile=load_render_profile(64, 64),
                diff_output_path=diff,
                run_contract=contract,
            )

        wrong_diff = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
            artifact_metadata={diff: {"sha256": "c" * 64}},
        )
        with self.assertRaisesRegex(FidelityError, "diff output.*expected sha256"):
            compare_images(
                reference,
                actual,
                profile=load_render_profile(64, 64),
                diff_output_path=diff,
                run_contract=wrong_diff,
            )
        self.assertFalse(diff.exists())

        svg = self.run_root / "expected-render.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"></svg>',
            encoding="utf-8",
        )
        preview = self.run_root / "expected-render.png"
        wrong_render = _run_contract(
            self.run_root,
            {svg: "vector-output", preview: "evidence"},
            width=64,
            height=64,
            artifact_metadata={preview: {"sha256": "d" * 64}},
        )
        with self.assertRaisesRegex(RenderError, "render output.*expected sha256"):
            render_svg(
                svg,
                preview,
                load_render_profile(64, 64, REAL_RESVG),
                run_contract=wrong_render,
            )
        self.assertFalse(preview.exists())

    def test_raw_png_ceiling_preflight_runs_before_pillow_metadata_handlers(self) -> None:
        from PIL import PngImagePlugin

        oversized = self.run_root / "oversized-with-icc.png"
        base = _header_only_png(10_001, 10_000)
        iend_offset = len(base) - 12
        payload = b"ICC\x00\x00" + zlib.compress(b"profile")
        kind = b"iCCP"
        chunk = (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
        )
        oversized.write_bytes(base[:iend_offset] + chunk + base[iend_offset:])
        with mock.patch.object(
            PngImagePlugin.PngStream,
            "chunk_iCCP",
            side_effect=AssertionError("Pillow metadata parsed before C4 ceiling"),
        ) as metadata:
            with self.assertRaisesRegex(FidelityError, "pixel ceiling"):
                compare_images(oversized, oversized)
        metadata.assert_not_called()

    def test_every_png_chunk_crc_is_verified_before_pillow(self) -> None:
        valid = self.run_root / "valid-crc.png"
        _save_rgba(valid, _rgba(1, 1))
        payload = bytearray(valid.read_bytes())
        offset = 8
        while offset < len(payload):
            length = int.from_bytes(payload[offset : offset + 4], "big")
            kind = bytes(payload[offset + 4 : offset + 8])
            if kind == b"IDAT":
                crc_offset = offset + 8 + length
                payload[crc_offset] ^= 0x01
                break
            offset += 12 + length
        corrupt = self.run_root / "bad-idat-crc.png"
        corrupt.write_bytes(payload)
        with mock.patch.object(
            Image,
            "open",
            side_effect=AssertionError("Pillow opened CRC-invalid PNG"),
        ) as pillow_open:
            with self.assertRaisesRegex(FidelityError, "CRC"):
                compare_images(corrupt, corrupt)
        pillow_open.assert_not_called()

    def test_registry_anchor_is_validated_before_any_png_or_pillow_access(self) -> None:
        import reconstruction.metrics as metrics_module
        import reconstruction.render as render_module

        tampered = json.loads(REGISTRY.read_text(encoding="utf-8"))
        tampered["renderProfile"]["metricMaxPixels"] = 1
        tampered_path = self.run_root / "tampered-registry-order.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        with (
            mock.patch.object(render_module, "_REGISTRY_PATH", tampered_path),
            mock.patch.object(
                metrics_module,
                "_open_checked_png_header",
                side_effect=AssertionError("PNG opened before registry anchor"),
            ) as png_open,
            mock.patch.object(
                Image,
                "open",
                side_effect=AssertionError("Pillow opened before registry anchor"),
            ) as pillow_open,
        ):
            with self.assertRaisesRegex(FidelityError, "trusted|digest|anchor"):
                compare_images(FLAT_FIXTURE, FLAT_FIXTURE)
        png_open.assert_not_called()
        pillow_open.assert_not_called()

    def test_png_strict_subset_and_deflate_are_rejected_before_pillow(self) -> None:
        ihdr = (
            (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + bytes((8, 6, 0, 0, 0))
        )
        ihdr_rgb = ihdr[:9] + bytes((2, 0, 0, 0))
        valid_scanline = zlib.compress(b"\x00\x00\x00\x00\x00")
        valid_rgb_scanline = zlib.compress(b"\x00\x00\x00\x00")
        signature = b"\x89PNG\r\n\x1a\n"
        cases = {
            "non-letter chunk type": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"12CD", b"")
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"IEND", b""),
                "ASCII letters|chunk type",
            ),
            "reserved bit": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"abca", b"")
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"IEND", b""),
                "reserved",
            ),
            "unknown critical": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"ABCD", b"")
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"IEND", b""),
                "unknown critical",
            ),
            "unknown ancillary": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"abCd", b"")
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"IEND", b""),
                "unknown ancillary",
            ),
            "PLTE after IDAT": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"PLTE", b"\x00\x00\x00")
                + _png_chunk(b"IEND", b""),
                "PLTE.*before IDAT|out of order",
            ),
            "duplicate PLTE": (
                signature
                + _png_chunk(b"IHDR", ihdr_rgb)
                + _png_chunk(b"PLTE", b"\x00\x00\x00")
                + _png_chunk(b"PLTE", b"\xff\xff\xff")
                + _png_chunk(b"IDAT", valid_rgb_scanline)
                + _png_chunk(b"IEND", b""),
                "duplicate PLTE",
            ),
            "duplicate ancillary": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"sRGB", b"\x00")
                + _png_chunk(b"sRGB", b"\x00")
                + _png_chunk(b"IDAT", valid_scanline)
                + _png_chunk(b"IEND", b""),
                "duplicate sRGB",
            ),
            "bad deflate": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", b"not-zlib")
                + _png_chunk(b"IEND", b""),
                "deflate|zlib",
            ),
            "trailing deflate stream": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", valid_scanline + b"trailing")
                + _png_chunk(b"IEND", b""),
                "trailing|deflate",
            ),
            "wrong scanline length": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00"))
                + _png_chunk(b"IEND", b""),
                "scanline|length",
            ),
            "invalid filter": (
                signature
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", zlib.compress(b"\x05\x00\x00\x00\x00"))
                + _png_chunk(b"IEND", b""),
                "filter",
            ),
        }
        for name, (payload, reason) in cases.items():
            path = self.run_root / f"strict-{name.replace(' ', '-')}.png"
            path.write_bytes(payload)
            with self.subTest(name=name), mock.patch.object(
                Image,
                "open",
                side_effect=AssertionError("Pillow opened invalid strict-subset PNG"),
            ) as pillow_open:
                with self.assertRaisesRegex(FidelityError, reason):
                    compare_images(path, path)
                pillow_open.assert_not_called()

        split = max(1, len(valid_scanline) // 2)
        multi_idat = self.run_root / "valid-multi-idat.png"
        multi_idat.write_bytes(
            signature
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", valid_scanline[:split])
            + _png_chunk(b"IDAT", valid_scanline[split:])
            + _png_chunk(b"IEND", b"")
        )
        multi_metrics = compare_images(multi_idat, multi_idat)
        self.assertTrue(multi_metrics.passed)
        self.assertEqual(multi_metrics.lifecycle_status, "MEASURED")

    def test_png_accepts_legal_rgba_plte_and_streamed_srgb_iccp(self) -> None:
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = (
            (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + bytes((8, 6, 0, 0, 0))
        )
        rgba_plte = self.run_root / "rgba-suggested-plte.png"
        rgba_plte.write_bytes(
            signature
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"PLTE", b"\x00\x00\x00\xff\xff\xff")
            + _png_chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03\xff"))
            + _png_chunk(b"IEND", b"")
        )
        plte_metrics = compare_images(rgba_plte, rgba_plte)
        self.assertTrue(plte_metrics.passed)
        self.assertEqual(plte_metrics.lifecycle_status, "MEASURED")

        srgb_chrm = (31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)
        calibrated = self.run_root / "rgba-explicit-srgb-metadata.png"
        calibrated.write_bytes(
            signature
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"gAMA", (45455).to_bytes(4, "big"))
            + _png_chunk(
                b"cHRM", b"".join(value.to_bytes(4, "big") for value in srgb_chrm)
            )
            + _png_chunk(b"sRGB", b"\x00")
            + _png_chunk(b"PLTE", b"\x00\x00\x00")
            + _png_chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03\xff"))
            + _png_chunk(b"IEND", b"")
        )
        calibrated_metrics = compare_images(calibrated, calibrated)
        self.assertTrue(calibrated_metrics.passed)

        icc_profile = _approved_icc_profile_bytes()
        iccp = self.run_root / "pillow-srgb-iccp.png"
        Image.fromarray(_rgba(1, 1, (1, 2, 3, 255)), mode="RGBA").save(
            iccp,
            format="PNG",
            icc_profile=icc_profile,
        )
        iccp_metrics = compare_images(iccp, iccp)
        self.assertTrue(iccp_metrics.passed)
        self.assertEqual(iccp_metrics.lifecycle_status, "MEASURED")
        self.assertEqual(iccp_metrics.reference_icc_profile_id, APPROVED_ICC_ID)
        self.assertEqual(iccp_metrics.reference_icc_profile_sha256, APPROVED_ICC_SHA256)
        self.assertEqual(
            iccp_metrics.reference_canonical_icc_sha256, APPROVED_ICC_SHA256
        )
        self.assertEqual(
            iccp_metrics.reference_raw_icc_sha256,
            hashlib.sha256(icc_profile).hexdigest(),
        )
        self.assertEqual(
            iccp_metrics.reference_icc_canonicalization, ICC_CANONICALIZATION
        )
        self.assertEqual(iccp_metrics.actual_icc_profile_id, APPROVED_ICC_ID)
        self.assertEqual(iccp_metrics.actual_icc_profile_sha256, APPROVED_ICC_SHA256)

        second_date_profile = _approved_icc_profile_bytes(
            bytes.fromhex("07ea000800160015002f0003")
        )
        second_date = self.run_root / "pillow-srgb-iccp-second-date.png"
        Image.fromarray(_rgba(1, 1, (1, 2, 3, 255)), mode="RGBA").save(
            second_date,
            format="PNG",
            icc_profile=second_date_profile,
        )
        second_metrics = compare_images(second_date, second_date)
        self.assertNotEqual(
            iccp_metrics.reference_raw_icc_sha256,
            second_metrics.reference_raw_icc_sha256,
        )
        self.assertEqual(
            second_metrics.reference_canonical_icc_sha256, APPROVED_ICC_SHA256
        )
        self.assertEqual(
            second_metrics.reference_icc_canonicalization, ICC_CANONICALIZATION
        )

        iccp_actual = self.run_root / "pillow-srgb-iccp-preview.png"
        shutil.copyfile(iccp, iccp_actual)
        bound = compare_images(
            iccp,
            iccp_actual,
            profile=load_render_profile(1, 1),
            run_contract=_run_contract(
                self.run_root,
                {iccp: "normalized-source", iccp_actual: "evidence"},
                width=1,
                height=1,
                normalized_reference=iccp,
            ),
        )
        self.assertEqual(
            tuple(binding.icc_profile_id for binding in bound.input_bindings),
            (APPROVED_ICC_ID, APPROVED_ICC_ID),
        )
        self.assertTrue(
            all(
                binding.icc_profile_sha256 == APPROVED_ICC_SHA256
                for binding in bound.input_bindings
            )
        )
        self.assertTrue(
            all(
                binding.canonical_icc_sha256 == APPROVED_ICC_SHA256
                and binding.icc_canonicalization == ICC_CANONICALIZATION
                and binding.raw_icc_sha256 is not None
                for binding in bound.input_bindings
            )
        )

        implicit = compare_images(rgba_plte, rgba_plte)
        self.assertEqual(implicit.reference_icc_profile_id, "implicit-sRGB-none")
        self.assertIsNone(implicit.reference_icc_profile_sha256)
        self.assertIsNone(implicit.reference_raw_icc_sha256)
        self.assertIsNone(implicit.reference_canonical_icc_sha256)
        self.assertEqual(implicit.reference_icc_canonicalization, "none")

    def test_png_rejects_color_metadata_conflicts_and_bad_iccp_before_pillow(self) -> None:
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = (
            (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + bytes((8, 6, 0, 0, 0))
        )
        idat = _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff"))
        iend = _png_chunk(b"IEND", b"")
        valid_iccp = (
            b"ICC Profile\x00\x00" + zlib.compress(_approved_icc_profile_bytes())
        )
        cases = {
            "color chunk after PLTE": (
                _png_chunk(b"PLTE", b"\x00\x00\x00")
                + _png_chunk(b"sRGB", b"\x00"),
                "sRGB.*before PLTE",
            ),
            "zero gamma": (_png_chunk(b"gAMA", b"\x00\x00\x00\x00"), "gAMA.*positive|gamma"),
            "nonsrgb gamma": (
                _png_chunk(b"gAMA", (100_000).to_bytes(4, "big")),
                "gAMA.*sRGB|gamma",
            ),
            "iccp srgb conflict": (
                _png_chunk(b"iCCP", valid_iccp) + _png_chunk(b"sRGB", b"\x00"),
                "iCCP.*sRGB|mutually exclusive|conflict",
            ),
            "duplicate iccp": (
                _png_chunk(b"iCCP", valid_iccp) + _png_chunk(b"iCCP", valid_iccp),
                "duplicate iCCP",
            ),
            "bad keyword spacing": (
                _png_chunk(
                    b"iCCP", b"ICC  Profile\x00\x00" + zlib.compress(b"profile")
                ),
                "keyword|space",
            ),
            "bad compression method": (
                _png_chunk(b"iCCP", b"ICC Profile\x00\x01" + zlib.compress(b"profile")),
                "compression method",
            ),
            "truncated iccp zlib": (
                _png_chunk(b"iCCP", b"ICC Profile\x00\x00x"),
                "iCCP.*zlib|deflate|truncated",
            ),
            "trailing iccp stream": (
                _png_chunk(
                    b"iCCP",
                    b"ICC Profile\x00\x00" + zlib.compress(b"profile") + b"trailing",
                ),
                "iCCP.*trailing|concatenated",
            ),
        }
        for name, (metadata, reason) in cases.items():
            path = self.run_root / f"color-{name.replace(' ', '-')}.png"
            path.write_bytes(
                signature + _png_chunk(b"IHDR", ihdr) + metadata + idat + iend
            )
            with self.subTest(name=name), mock.patch.object(
                Image,
                "open",
                side_effect=AssertionError("Pillow opened invalid color metadata"),
            ) as pillow_open:
                with self.assertRaisesRegex(FidelityError, reason):
                    compare_images(path, path)
                pillow_open.assert_not_called()

    def test_png_plte_color_type_and_iccp_resource_boundaries_precede_pillow(self) -> None:
        signature = b"\x89PNG\r\n\x1a\n"

        def ihdr(bit_depth: int, color_type: int) -> bytes:
            payload = (
                (1).to_bytes(4, "big")
                + (1).to_bytes(4, "big")
                + bytes((bit_depth, color_type, 0, 0, 0))
            )
            return _png_chunk(b"IHDR", payload)

        cases = {
            "indexed missing PLTE": (
                ihdr(1, 3)
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00")),
                "type 3 requires PLTE",
            ),
            "indexed PLTE entry overflow": (
                ihdr(1, 3)
                + _png_chunk(b"PLTE", b"\x00\x00\x00" * 3)
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00")),
                "PLTE.*bit-depth|entry limit",
            ),
            "grayscale forbids PLTE": (
                ihdr(8, 0)
                + _png_chunk(b"PLTE", b"\x00\x00\x00")
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00")),
                "color type 0 forbids PLTE",
            ),
            "gray alpha forbids PLTE": (
                ihdr(8, 4)
                + _png_chunk(b"PLTE", b"\x00\x00\x00")
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\xff")),
                "color type 4 forbids PLTE",
            ),
            "cHRM drift": (
                ihdr(8, 6)
                + _png_chunk(b"cHRM", b"\x00" * 32)
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff")),
                "cHRM.*sRGB",
            ),
            "iCCP decoded over limit": (
                ihdr(8, 6)
                + _png_chunk(
                    b"iCCP",
                    b"ICC Profile\x00\x00"
                    + zlib.compress(b"x" * (4 * 1024 * 1024 + 1)),
                )
                + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff")),
                "iCCP profile exceeds",
            ),
        }
        iend = _png_chunk(b"IEND", b"")
        for name, (chunks, reason) in cases.items():
            path = self.run_root / f"plte-boundary-{name.replace(' ', '-')}.png"
            path.write_bytes(signature + chunks + iend)
            with self.subTest(name=name), mock.patch.object(
                Image,
                "open",
                side_effect=AssertionError("Pillow opened invalid PLTE/ICC boundary"),
            ) as pillow_open:
                with self.assertRaisesRegex(FidelityError, reason):
                    compare_images(path, path)
                pillow_open.assert_not_called()

    def test_icc_structure_and_exact_registry_digest_are_authoritative_before_pillow(self) -> None:
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = _png_chunk(
            b"IHDR",
            (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + bytes((8, 6, 0, 0, 0)),
        )
        idat = _png_chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03\xff"))
        iend = _png_chunk(b"IEND", b"")
        canonical = _approved_icc_profile_bytes()
        fake_lab = bytearray(canonical)
        fake_lab[16:20] = b"LAB "
        mutated = bytearray(canonical)
        mutated[500] ^= 0x01
        invalid_date = bytearray(canonical)
        invalid_date[24:36] = bytes.fromhex("07ea000d0001000000000000")
        malformed_tag = bytearray(canonical)
        malformed_tag[136:144] = (130).to_bytes(4, "big") + (200).to_bytes(4, "big")
        cases = {
            "fake LAB description": (bytes(fake_lab), "data color space.*RGB|ICC.*RGB"),
            "one byte digest mutation": (bytes(mutated), "approved|digest|SHA-256"),
            "invalid creation date": (
                bytes(invalid_date),
                "creationDate.*invalid",
            ),
            "tag table mutation rejected by allowlist first": (
                bytes(malformed_tag),
                "canonical digest|approved registry",
            ),
        }
        for name, (profile, reason) in cases.items():
            path = self.run_root / f"icc-authority-{name.replace(' ', '-')}.png"
            path.write_bytes(
                signature
                + ihdr
                + _png_chunk(
                    b"iCCP", b"ICC Profile\x00\x00" + zlib.compress(profile)
                )
                + idat
                + iend
            )
            with self.subTest(name=name), mock.patch.object(
                Image,
                "open",
                side_effect=AssertionError("Pillow opened unauthorized ICC profile"),
            ) as pillow_open:
                with self.assertRaisesRegex(FidelityError, reason):
                    compare_images(path, path)
                pillow_open.assert_not_called()

    def test_renderer_binary_type_and_post_replace_tampering_fail_without_residue(self) -> None:
        import reconstruction.render as render_module

        svg = self.run_root / "bound.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"></svg>',
            encoding="utf-8",
        )
        output = self.run_root / "bound.png"
        contract = _run_contract(
            self.run_root,
            {svg: "vector-output", output: "evidence"},
            width=64,
            height=64,
        )
        invalid = dataclasses.replace(
            load_render_profile(64, 64, REAL_RESVG),
            renderer_binary=os.fspath(REAL_RESVG),
        )
        with self.assertRaisesRegex(RenderError, "renderer_binary|Path"):
            load_render_profile(64, 64, os.fspath(REAL_RESVG))  # type: ignore[arg-type]
        with self.assertRaisesRegex(RenderError, "renderer_binary|Path"):
            render_svg(svg, output, invalid, run_contract=contract)
        self.assertFalse(any(path.name.startswith(".bound.png.") for path in self.run_root.iterdir()))

        profile = load_render_profile(64, 64, REAL_RESVG)
        real_replace = render_module.os.replace

        def replace_then_tamper(source: Path, target: Path) -> None:
            real_replace(source, target)
            Path(target).write_bytes(b"post-replace attacker bytes")

        with mock.patch.object(render_module.os, "replace", new=replace_then_tamper):
            with self.assertRaisesRegex(RenderError, "commit|readback|integrity"):
                render_svg(svg, output, profile, run_contract=contract)
        self.assertFalse(output.exists())

    def test_diff_post_replace_tampering_fails_and_removes_invalid_target(self) -> None:
        import reconstruction.metrics as metrics_module

        real_replace = metrics_module.os.replace

        def replace_then_tamper(source: Path, target: Path) -> None:
            real_replace(source, target)
            Path(target).write_bytes(b"post-replace attacker bytes")

        with mock.patch.object(metrics_module.os, "replace", new=replace_then_tamper):
            with self.assertRaisesRegex(FidelityError, "commit|readback|integrity"):
                self.compare(_rgba(64, 64), _rgba(64, 64), diff_name="tampered-diff.png")
        self.assertFalse((self.run_root / "tampered-diff.png").exists())

    def test_bound_inputs_and_registry_are_revalidated_immediately_before_commit(self) -> None:
        import reconstruction.metrics as metrics_module
        import reconstruction.render as render_module

        pixels = _rgba(64, 64)
        reference = self.run_root / "bound-reference.png"
        actual = self.run_root / "bound-actual.png"
        diff = self.run_root / "bound-diff.png"
        _save_rgba(reference, pixels)
        _save_rgba(actual, pixels)
        contract = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
        )
        original_diff_png = metrics_module._diff_png

        def mutate_actual_then_encode(mask, excluded):
            actual.write_bytes(reference.read_bytes() + b"attacker mutation")
            return original_diff_png(mask, excluded)

        with mock.patch.object(metrics_module, "_diff_png", new=mutate_actual_then_encode):
            with self.assertRaisesRegex(FidelityError, "bound input changed"):
                compare_images(
                    reference,
                    actual,
                    profile=load_render_profile(64, 64),
                    diff_output_path=diff,
                    run_contract=contract,
                )
        self.assertFalse(diff.exists())

        svg = self.run_root / "registry-bound.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"></svg>',
            encoding="utf-8",
        )
        preview = self.run_root / "registry-bound.png"
        render_contract = _run_contract(
            self.run_root,
            {svg: "vector-output", preview: "evidence"},
            width=64,
            height=64,
        )
        registry_copy = self.run_root / "trusted-registry-copy.json"
        registry_copy.write_bytes(REGISTRY.read_bytes())
        original_run = render_module._run_renderer
        mutated = False

        def mutate_registry_then_run(command: list[str], *, cwd: Path):
            nonlocal mutated
            completed = original_run(command, cwd=cwd)
            if not mutated and len(command) > 1 and command[1] != "--version":
                registry_copy.write_bytes(registry_copy.read_bytes() + b" ")
                mutated = True
            return completed

        with (
            mock.patch.object(render_module, "_REGISTRY_PATH", registry_copy),
            mock.patch.object(render_module, "_run_renderer", new=mutate_registry_then_run),
            self.assertRaisesRegex(RenderError, "trusted|digest|anchor"),
        ):
            render_svg(
                svg,
                preview,
                load_render_profile(64, 64, REAL_RESVG),
                run_contract=render_contract,
            )
        self.assertFalse(preview.exists())

    def test_invalid_post_replace_target_cleanup_failure_reports_exact_residue(self) -> None:
        import reconstruction.metrics as metrics_module

        target = self.run_root / "locked-invalid-diff.png"
        real_replace = metrics_module.os.replace
        real_unlink = Path.unlink

        def replace_then_tamper(source: Path, output: Path) -> None:
            real_replace(source, output)
            Path(output).write_bytes(b"invalid committed bytes")

        def reject_invalid_target_cleanup(path: Path, *args, **kwargs):
            if path == target:
                raise OSError("locked invalid target residue")
            return real_unlink(path, *args, **kwargs)

        with (
            mock.patch.object(metrics_module.os, "replace", new=replace_then_tamper),
            mock.patch.object(Path, "unlink", new=reject_invalid_target_cleanup),
            self.assertRaisesRegex(
                FidelityError,
                r"integrity mismatch.*invalid diff output target residue.*locked-invalid-diff\.png",
            ) as captured,
        ):
            self.compare(_rgba(64, 64), _rgba(64, 64), diff_name=target.name)
        self.assertIsInstance(captured.exception.__cause__, RenderError)
        self.assertIsInstance(captured.exception.__cause__.__cause__, ExceptionGroup)
        self.assertTrue(target.exists())

    def test_write_contract_binds_artifact_target_expiry_lifecycle_and_canvas(self) -> None:
        pixels = _rgba(64, 64)
        reference = self.run_root / "reference-contract.png"
        actual = self.run_root / "actual-contract.png"
        _save_rgba(reference, pixels)
        _save_rgba(actual, pixels)
        authorized = self.run_root / "authorized-diff.png"
        other = self.run_root / "other-diff.png"
        contract = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence", authorized: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference,
        )
        profile = dataclasses.replace(self.profile, width=64, height=64)
        with self.assertRaisesRegex(FidelityError, "artifact|target|authorized"):
            compare_images(
                reference,
                actual,
                profile=profile,
                diff_output_path=other,
                run_contract=contract,
            )
        for mutation, reason in (
            ({"expired": True}, "expired"),
            ({"lifecycle_state": "completed"}, "lifecycle"),
        ):
            invalid = _run_contract(
                self.run_root,
                {reference: "normalized-source", actual: "evidence", authorized: "evidence"},
                width=64,
                height=64,
                normalized_reference=reference,
                **mutation,
            )
            with self.subTest(reason=reason), self.assertRaisesRegex(FidelityError, reason):
                compare_images(
                    reference,
                    actual,
                    profile=profile,
                    diff_output_path=authorized,
                    run_contract=invalid,
                )
        wrong_canvas = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence", authorized: "evidence"},
            width=63,
            height=64,
            normalized_reference=reference,
        )
        with self.assertRaisesRegex(FidelityError, "canvas|dimensions"):
            compare_images(
                reference,
                actual,
                profile=profile,
                diff_output_path=authorized,
                run_contract=wrong_canvas,
            )

    def test_fixed_profile_rejects_float_dimensions_and_all_gate_tampering(self) -> None:
        with self.assertRaisesRegex(RenderError, "integer"):
            load_render_profile(64.0, 64, REAL_RESVG)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RenderError, "integer"):
            load_render_profile(True, 64, REAL_RESVG)  # type: ignore[arg-type]
        pixels = _rgba(64, 64)
        path = self.run_root / "profile-probe.png"
        _save_rgba(path, pixels)
        base = dataclasses.replace(self.profile, width=64, height=64)
        probes = (
            dataclasses.replace(base, width=64.0),
            dataclasses.replace(base, mae_limit_version="caller-null", mae_limit=None),
            dataclasses.replace(base, mae_limit_version="caller-weak", mae_limit=1.0),
            dataclasses.replace(base, match_minimum=0.0),
        )
        for probe in probes:
            with self.subTest(probe=probe), self.assertRaisesRegex(FidelityError, "profile mismatch|integer"):
                compare_images(path, path, profile=probe)

    def test_small_canvas_ssim_fallback_is_finite_and_deterministic(self) -> None:
        for width, height in ((1, 1), (1, 9), (2, 9), (9, 1), (9, 2)):
            same = _rgba(width, height)
            different = same.copy()
            different[height // 2, width // 2, :3] = 255
            profile = load_render_profile(width, height)
            same_metrics = self.compare(
                same, same, profile=profile, diff_name=f"same-{width}x{height}.png"
            )
            diff_metrics = self.compare(
                same,
                different,
                profile=profile,
                diff_name=f"different-{width}x{height}.png",
            )
            self.assertEqual(same_metrics.ssim, 1.0)
            self.assertTrue(math.isfinite(diff_metrics.ssim))
            self.assertGreaterEqual(diff_metrics.ssim, -1.0)
            self.assertLess(diff_metrics.ssim, 1.0)

    def test_c4_operational_ceiling_is_below_c3_geometry_and_predecode(self) -> None:
        import reconstruction.metrics as metrics_module
        from reconstruction.svg_safety import MAX_CANVAS_PIXELS

        self.assertEqual(MAX_CANVAS_PIXELS, 100_000_000)
        boundary = load_render_profile(2_048, 2_048, REAL_RESVG)
        self.assertEqual(boundary.width * boundary.height, 4_194_304)
        with self.assertRaisesRegex(RenderError, "operational|metric.*pixel|pixel ceiling"):
            load_render_profile(2_049, 2_048)

        source = self.run_root / "canvas-ceiling.svg"
        source.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="2048"></svg>',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RenderError, "run contract"):
            render_svg(source, self.run_root / "boundary.png", boundary)
        with self.assertRaisesRegex(RenderError, "pixel ceiling"):
            render_svg(
                source,
                self.run_root / "over-ceiling.png",
                dataclasses.replace(boundary, width=2_049),
            )

        boundary_header = self.run_root / "boundary-header.png"
        boundary_header.write_bytes(_streamed_zero_png(2_048, 2_048))
        with mock.patch.object(
            metrics_module,
            "_decode_rgba",
            side_effect=AssertionError("boundary passed header checks before decode"),
        ) as boundary_decode:
            with self.assertRaisesRegex(AssertionError, "boundary passed"):
                compare_images(boundary_header, boundary_header, profile=boundary)
        boundary_decode.assert_called_once()

        oversized = self.run_root / "oversized-header.png"
        oversized.write_bytes(_header_only_png(2_049, 2_048))
        with mock.patch.object(
            Image.Image,
            "load",
            side_effect=AssertionError("pixel allocation/decode occurred"),
        ) as loaded:
            with self.assertRaisesRegex(FidelityError, "pixel ceiling"):
                compare_images(oversized, oversized)
        loaded.assert_not_called()

        oversized_file = self.run_root / "oversized-file.png"
        oversized_file.write_bytes(_header_only_png(1, 1))
        with oversized_file.open("r+b") as stream:
            stream.truncate(67_108_865)
        with self.assertRaisesRegex(FidelityError, "file-size|metric.*bytes"):
            compare_images(oversized_file, oversized_file)

    def test_identical_images_pass_and_promote_only_to_deterministic_status(self) -> None:
        pixels = _rgba(64, 64, (17, 34, 51, 127))
        metrics = self.compare(pixels, pixels)
        self.assertEqual(metrics.match_ratio, 1.0)
        self.assertEqual(metrics.ssim, 1.0)
        self.assertEqual(metrics.mean_rgba_error, 0.0)
        self.assertEqual(metrics.alpha_mean_error, 0.0)
        self.assertEqual(metrics.edge_error, 0.0)
        self.assertEqual(metrics.mismatch_count, 0)
        self.assertEqual(metrics.mismatch_mask, bytes(64 * 64))
        self.assertTrue(metrics.passed)
        self.assertEqual(metrics.lifecycle_status, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertNotIn("ILLUSTRATOR", metrics.lifecycle_status)
        self.assertEqual(metrics.failure_reasons, ())

    def test_two_argument_compare_interface_uses_fixed_repository_profile(self) -> None:
        metrics = compare_images(FLAT_FIXTURE, FLAT_FIXTURE)
        self.assertTrue(metrics.passed)
        self.assertEqual(metrics.profile_id, "design-lab/render-profile/v1")
        self.assertEqual(metrics.match_ratio, 1.0)
        self.assertIsNone(metrics.diff_path)
        self.assertEqual(metrics.lifecycle_status, "MEASURED")
        self.assertEqual(metrics.input_authority, "UNBOUND_LOCAL_COMPARISON")
        self.assertEqual(metrics.input_bindings, ())

        one_pixel = self.run_root / "unbound-one-pixel.png"
        _save_rgba(one_pixel, _rgba(1, 1, (7, 8, 9, 255)))
        one_pixel_metrics = compare_images(one_pixel, one_pixel)
        self.assertTrue(one_pixel_metrics.passed)
        self.assertEqual(one_pixel_metrics.lifecycle_status, "MEASURED")
        self.assertEqual(
            one_pixel_metrics.input_authority, "UNBOUND_LOCAL_COMPARISON"
        )

    def test_contract_bound_comparison_without_diff_can_promote(self) -> None:
        pixels = _rgba(1, 1, (7, 8, 9, 255))
        reference = self.run_root / "bound-reference-no-diff.png"
        actual = self.run_root / "bound-preview-authoritative.png"
        _save_rgba(reference, pixels)
        _save_rgba(actual, pixels)
        contract = _run_contract(
            self.run_root,
            {reference: "normalized-source", actual: "evidence"},
            width=1,
            height=1,
            normalized_reference=reference,
        )
        metrics = compare_images(
            reference,
            actual,
            profile=load_render_profile(1, 1),
            run_contract=contract,
        )
        self.assertTrue(metrics.passed)
        self.assertEqual(metrics.lifecycle_status, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertEqual(metrics.input_authority, "CONTRACT_BOUND_AUTHORITATIVE")
        self.assertEqual(
            tuple(binding.role for binding in metrics.input_bindings),
            ("normalized-reference", "render-preview"),
        )

    def test_pixelmatch_v7_2_literal_yiq_threshold_boundary(self) -> None:
        official_limit = 35215 * 0.1 * 0.1
        self.assertLessEqual(_official_yiq_delta(26), official_limit)
        self.assertGreater(_official_yiq_delta(27), official_limit)

        reference = _rgba(64, 64)
        below = reference.copy()
        below[32, 32, :3] = 26
        above = reference.copy()
        above[32, 32, :3] = 27

        below_metrics = self.compare(reference, below, diff_name="below.png")
        above_metrics = self.compare(reference, above, diff_name="above.png")
        self.assertEqual(below_metrics.mismatch_count, 0)
        self.assertEqual(above_metrics.mismatch_count, 1)
        mask = np.frombuffer(above_metrics.mismatch_mask, dtype=np.uint8).reshape(64, 64)
        self.assertEqual(int(mask[32, 32]), 1)
        self.assertEqual(int(mask.sum()), 1)

    def test_pixelmatch_v7_2_literal_antialias_vector_is_excluded(self) -> None:
        # The center is between a three-pixel dark plateau and a three-pixel light
        # plateau. The official v7.2.0 intensity-slope detector classifies it AA.
        reference = _rgba(5, 5, (255, 255, 255, 255))
        reference[0:3, 0:2, :3] = 0
        reference[2, 2, :3] = 128
        actual = reference.copy()
        actual[2, 2, :3] = 255

        metrics = self.compare(reference, actual)
        mismatch = np.frombuffer(metrics.mismatch_mask, dtype=np.uint8).reshape(5, 5)
        excluded = np.frombuffer(metrics.excluded_aa_mask, dtype=np.uint8).reshape(5, 5)
        self.assertEqual(metrics.mismatch_count, 0)
        self.assertEqual(metrics.excluded_aa_count, 1)
        self.assertEqual(int(mismatch[2, 2]), 0)
        self.assertEqual(int(excluded[2, 2]), 1)

        included_mask, included_excluded = pixelmatch_masks(
            reference, actual, threshold=0.1, include_aa=True
        )
        self.assertEqual(int(included_mask.sum()), 1)
        self.assertEqual(int(included_excluded.sum()), 0)

    def test_ssim_uses_background_composite_but_mae_retains_original_rgba(self) -> None:
        reference = _rgba(64, 64, (255, 0, 0, 0))
        actual = _rgba(64, 64, (0, 0, 255, 0))
        metrics = self.compare(reference, actual)
        self.assertEqual(metrics.match_ratio, 1.0)
        self.assertEqual(metrics.ssim, 1.0)
        self.assertEqual(metrics.mean_rgba_error, 0.5)
        self.assertEqual(metrics.alpha_mean_error, 0.0)
        self.assertTrue(metrics.passed)

    def test_recorded_nonwhite_background_is_owned_and_used_by_profile(self) -> None:
        profile = load_render_profile(
            64,
            64,
            REAL_RESVG,
            rgba_background=(12, 34, 56, 255),
        )
        reference = _rgba(64, 64, (255, 0, 0, 0))
        actual = _rgba(64, 64, (0, 0, 255, 0))
        metrics = self.compare(reference, actual, profile=profile)
        self.assertEqual(profile.rgba_background, (12, 34, 56, 255))
        self.assertEqual(metrics.match_ratio, 1.0)
        self.assertEqual(metrics.ssim, 1.0)
        self.assertEqual(metrics.pixelmatch_version, "7.2.0")
        self.assertEqual(metrics.pixel_threshold, 0.1)
        self.assertTrue(metrics.anti_alias_detection)
        self.assertEqual(metrics.match_minimum, 0.995)
        self.assertEqual(metrics.ssim_minimum, 0.995)
        self.assertEqual(metrics.mae_limit_version, "uncalibrated-v1")
        self.assertIsNone(metrics.mae_limit)
        self.assertEqual(metrics.edge_metric, "sobel-rgb-l1/v1")

    def test_mae_is_informative_when_null_and_required_when_calibrated(self) -> None:
        reference = _rgba(64, 64, (255, 0, 0, 0))
        actual = _rgba(64, 64, (0, 0, 255, 0))
        informative = self.compare(reference, actual)
        self.assertNotIn("MAE_LIMIT_EXCEEDED", informative.failure_reasons)

        caller_calibrated = dataclasses.replace(
            self.profile,
            width=64,
            height=64,
            mae_limit_version="golden-corpus-v1",
            mae_limit=0.49,
        )
        with self.assertRaisesRegex(FidelityError, "profile mismatch"):
            self.compare(reference, actual, profile=caller_calibrated, diff_name="mae.png")

    def test_dense_component_rule_has_literal_32_33_and_sparse_boundaries(self) -> None:
        reference = _rgba(128, 128)

        square32 = reference.copy()
        square32[10:42, 10:42, :3] = 255
        metrics32 = self.compare(reference, square32, diff_name="dense32.png")
        self.assertEqual(metrics32.components[0].bounds, (10, 10, 32, 32))
        self.assertEqual(metrics32.components[0].density, 1.0)
        self.assertEqual(metrics32.max_diff_window, 1024)
        self.assertEqual(metrics32.dense_regions, ())
        self.assertNotIn("DENSE_DIFF_REGION", metrics32.failure_reasons)

        square33 = reference.copy()
        square33[10:43, 10:43, :3] = 255
        metrics33 = self.compare(reference, square33, diff_name="dense33.png")
        self.assertEqual(metrics33.components[0].bounds, (10, 10, 33, 33))
        self.assertEqual(metrics33.components[0].density, 1.0)
        self.assertEqual(metrics33.max_diff_window, 1024)
        self.assertEqual(metrics33.dense_regions, metrics33.components)
        self.assertIn("DENSE_DIFF_REGION", metrics33.failure_reasons)
        self.assertFalse(metrics33.passed)

        sparse = reference.copy()
        sparse[10, 10, :3] = 255
        sparse[43, 43, :3] = 255
        sparse[76, 76, :3] = 255
        metrics_sparse = self.compare(reference, sparse, diff_name="sparse.png")
        self.assertEqual(len(metrics_sparse.components), 3)
        self.assertTrue(all(component.bounds == (c, c, 1, 1) for component, c in zip(metrics_sparse.components, (10, 43, 76))))
        self.assertEqual(metrics_sparse.dense_regions, ())
        self.assertNotIn("DENSE_DIFF_REGION", metrics_sparse.failure_reasons)

    def test_diff_heatmap_bytes_hash_and_mask_evidence_are_deterministic(self) -> None:
        reference = _rgba(64, 64)
        actual = reference.copy()
        actual[12:16, 20:24, :3] = (255, 0, 0)
        first = self.compare(reference, actual, diff_name="diff-first.png")
        second = self.compare(reference, actual, diff_name="diff-second.png")
        self.assertEqual(first.diff_sha256, second.diff_sha256)
        self.assertEqual(first.diff_path.read_bytes(), second.diff_path.read_bytes())
        self.assertEqual(first.diff_sha256, hashlib.sha256(first.diff_path.read_bytes()).hexdigest())
        self.assertEqual(first.mismatch_mask_sha256, hashlib.sha256(first.mismatch_mask).hexdigest())
        self.assertEqual(len(first.mismatch_mask), 64 * 64)
        with Image.open(first.diff_path) as diff:
            self.assertEqual(diff.mode, "RGBA")
            self.assertEqual(diff.size, (64, 64))

    def test_dimensions_profile_and_nonfinite_metrics_fail_closed(self) -> None:
        reference = _rgba(64, 64)
        actual = _rgba(65, 64)
        with self.assertRaisesRegex(FidelityError, "dimensions"):
            self.compare(reference, actual)

        wrong_profile = dataclasses.replace(self.profile, width=63, height=64)
        with self.assertRaisesRegex(FidelityError, "profile dimensions"):
            self.compare(reference, reference, profile=wrong_profile)

        import reconstruction.metrics as metrics_module

        with mock.patch.object(metrics_module, "structural_similarity", return_value=math.nan):
            with self.assertRaisesRegex(FidelityError, "non-finite"):
                self.compare(reference, reference.copy(), diff_name="nan.png")

    def test_diff_output_rejects_outside_and_reparse_paths(self) -> None:
        reference = _rgba(64, 64)
        reference_path = self.run_root / "reference.png"
        actual_path = self.run_root / "actual.png"
        _save_rgba(reference_path, reference)
        _save_rgba(actual_path, reference)
        profile = dataclasses.replace(self.profile, width=64, height=64)
        authorized = self.run_root / "authorized-diff.png"
        contract = _run_contract(
            self.run_root,
            {reference_path: "normalized-source", actual_path: "evidence", authorized: "evidence"},
            width=64,
            height=64,
            normalized_reference=reference_path,
        )
        with self.assertRaisesRegex(FidelityError, "artifact|target|authorized"):
            compare_images(
                reference_path,
                actual_path,
                profile=profile,
                diff_output_path=REPO_ROOT / ".project-local" / "outside-diff.png",
                run_contract=contract,
            )

        target = self.run_root / "plain-target"
        target.mkdir()
        link = self.run_root / "linked"
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode != 0:
                self.skipTest("junction creation unavailable")
        else:
            link.symlink_to(target, target_is_directory=True)
        try:
            with self.assertRaisesRegex(FidelityError, "reparse|symlink"):
                compare_images(
                    reference_path,
                    actual_path,
                    profile=profile,
                    diff_output_path=link / "diff.png",
                    run_contract=_run_contract(
                        self.run_root,
                        {reference_path: "normalized-source", actual_path: "evidence", link / "diff.png": "evidence"},
                        width=64,
                        height=64,
                        normalized_reference=reference_path,
                    ),
                )
        finally:
            if os.name == "nt" and link.exists():
                os.rmdir(link)
            elif link.is_symlink():
                link.unlink()

    def test_renderer_rejects_unpinned_binary_without_touching_output(self) -> None:
        svg = self.run_root / "source.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect x="0" y="0" width="64" height="64" fill="#123456"/></svg>',
            encoding="utf-8",
        )
        output = self.run_root / "preview.png"
        output.write_bytes(b"sentinel")
        impostor = self.run_root / "resvg.exe"
        impostor.write_bytes(b"not the pinned binary")
        profile = load_render_profile(64, 64, impostor)
        with self.assertRaisesRegex(RenderError, "SHA-256"):
            render_svg(
                svg,
                output,
                profile,
                run_contract=_run_contract(
                    self.run_root,
                    {svg: "vector-output", output: "evidence"},
                    width=64,
                    height=64,
                ),
            )
        self.assertEqual(output.read_bytes(), b"sentinel")

    @unittest.skipUnless(REAL_RESVG.is_file(), "pinned external resvg is not installed")
    def test_renderer_executes_verified_run_local_copy_when_source_path_is_swapped(self) -> None:
        import reconstruction.render as render_module

        source_binary = self.run_root / "source-resvg.exe"
        shutil.copyfile(REAL_RESVG, source_binary)
        svg = self.run_root / "source-swap.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect x="0" y="0" width="64" height="64" fill="#123456"/></svg>',
            encoding="utf-8",
        )
        output = self.run_root / "swap-preview.png"
        contract = _run_contract(
            self.run_root,
            {svg: "vector-output", output: "evidence"},
            width=64,
            height=64,
        )
        profile = load_render_profile(64, 64, source_binary)
        original_run = render_module._run_renderer
        observed_commands: list[list[str]] = []
        swapped = False

        def swap_source_then_run(command: list[str], *, cwd: Path):
            nonlocal swapped
            observed_commands.append(command)
            if not swapped:
                backup = self.run_root / "source-resvg.original"
                source_binary.replace(backup)
                source_binary.write_bytes(b"attacker replacement")
                swapped = True
            return original_run(command, cwd=cwd)

        with mock.patch.object(render_module, "_run_renderer", new=swap_source_then_run):
            result = render_svg(svg, output, profile, run_contract=contract)
        self.assertEqual(result.output_path, output)
        self.assertTrue(observed_commands)
        self.assertTrue(
            all(Path(command[0]) != source_binary for command in observed_commands),
            observed_commands,
        )
        self.assertEqual(source_binary.read_bytes(), b"attacker replacement")

    @unittest.skipUnless(REAL_RESVG.is_file(), "pinned external resvg is not installed")
    def test_renderer_cleanup_failure_without_primary_error_fails_with_residue_path(self) -> None:
        svg = self.run_root / "cleanup-source.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"></svg>',
            encoding="utf-8",
        )
        output = self.run_root / "cleanup-preview.png"
        contract = _run_contract(
            self.run_root,
            {svg: "vector-output", output: "evidence"},
            width=64,
            height=64,
        )
        profile = load_render_profile(64, 64, REAL_RESVG)
        real_unlink = Path.unlink

        def reject_svg_cleanup(path: Path, *args, **kwargs):
            if path.parent == self.run_root and path.suffix == ".svg" and path.name.startswith("."):
                raise OSError("locked render staging residue")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", new=reject_svg_cleanup):
            with self.assertRaisesRegex(
                RenderError,
                r"cleanup.*residue.*\.svg|residue.*\.svg.*cleanup",
            ) as captured:
                render_svg(svg, output, profile, run_contract=contract)
        self.assertIsInstance(captured.exception.__cause__, OSError)

    def test_diff_primary_and_cleanup_failures_preserve_both_causes_and_residue(self) -> None:
        import reconstruction.metrics as metrics_module

        pixels = _rgba(64, 64)
        real_unlink = Path.unlink

        def reject_diff_cleanup(path: Path, *args, **kwargs):
            if path.parent == self.run_root and path.name.startswith(".diff-cleanup.png"):
                raise OSError("locked diff staging residue")
            return real_unlink(path, *args, **kwargs)

        with (
            mock.patch.object(
                metrics_module.os,
                "replace",
                side_effect=OSError("diff replace primary failure"),
            ),
            mock.patch.object(Path, "unlink", new=reject_diff_cleanup),
            self.assertRaisesRegex(
                FidelityError,
                r"replace primary failure.*additionally.*cleanup.*residue",
            ) as captured,
        ):
            self.compare(pixels, pixels, diff_name="diff-cleanup.png")
        self.assertIsInstance(captured.exception.__cause__, ExceptionGroup)
        self.assertEqual(len(captured.exception.__cause__.exceptions), 2)

    @unittest.skipUnless(REAL_RESVG.is_file(), "pinned external resvg is not installed")
    def test_real_resvg_64_roundtrip_uses_explicit_authorized_binary(self) -> None:
        self.assertEqual(hashlib.sha256(REAL_RESVG.read_bytes()).hexdigest(), REAL_RESVG_SHA256)
        svg = self.run_root / "source.svg"
        layers = []
        for index, (x, y, fill) in enumerate(
            (
                (0, 0, "#142850ff"),
                (32, 0, "#e64632ff"),
                (0, 32, "#28be6ec0"),
                (32, 32, "#f5d23c40"),
            )
        ):
            layers.append(
                {
                    "id": f"quadrant-{index}",
                    "type": "primitive",
                    "name": f"quadrant-{index}",
                    "opacity": 1.0,
                    "bounds": {"x": x, "y": y, "width": 32, "height": 32},
                    "inferred": False,
                    "zOrder": index,
                    "visible": True,
                    "locked": False,
                    "blendMode": "normal",
                    "primitive": {
                        "kind": "rect",
                        "parameters": {"x1": x, "y1": y, "x2": x + 32, "y2": y + 32},
                    },
                    "style": {
                        "fill": fill,
                        "stroke": None,
                        "strokeWidth": 0,
                        "fillRule": "nonzero",
                        "lineCap": "butt",
                        "lineJoin": "miter",
                    },
                    "masks": [],
                }
            )
        rir = {
            "schemaVersion": "design-lab/reconstruction-ir/v1",
            "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
            "layers": layers,
        }
        svg.write_bytes(serialize_svg(rir, REPO_ROOT))
        output = self.run_root / "preview.png"
        profile = load_render_profile(64, 64, REAL_RESVG)
        diff = self.run_root / "diff.png"
        normalized_reference = self.run_root / "normalized-reference.png"
        shutil.copyfile(FLAT_FIXTURE, normalized_reference)
        contract = _run_contract(
            self.run_root,
            {svg: "vector-output", normalized_reference: "normalized-source", output: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=normalized_reference,
        )
        result = render_svg(svg, output, profile, run_contract=contract)
        self.assertEqual(result.output_path, output)
        self.assertEqual(result.output_sha256, hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual((result.width, result.height), (64, 64))
        self.assertEqual(result.renderer_version, "0.47.0")
        self.assertEqual(result.renderer_sha256, REAL_RESVG_SHA256)
        self.assertEqual(result.registry_digest, self.profile.registry_sha256)
        self.assertEqual(
            [(item.role, item.producer, item.sha256) for item in result.input_bindings],
            [
                (
                    "sanitized-svg",
                    "rir-svg-serializer-v1",
                    hashlib.sha256(svg.read_bytes()).hexdigest(),
                )
            ],
        )
        self.assertEqual(result.metric_max_pixels, 4_194_304)
        self.assertEqual(result.metric_max_bytes, 67_108_864)
        self.assertEqual(result.metric_budget_version, "c4-metric-memory-v1")
        self.assertEqual(result.output_icc_profile_id, "implicit-sRGB-none")
        self.assertIsNone(result.output_icc_profile_sha256)
        self.assertIsNone(result.output_raw_icc_sha256)
        self.assertIsNone(result.output_canonical_icc_sha256)
        self.assertEqual(result.output_icc_canonicalization, "none")
        self.assertEqual(result.lifecycle_status, "RENDERED")
        compare_contract = _run_contract(
            self.run_root,
            {svg: "vector-output", normalized_reference: "normalized-source", output: "evidence", diff: "evidence"},
            width=64,
            height=64,
            normalized_reference=normalized_reference,
        )
        metrics = compare_images(
            normalized_reference,
            output,
            profile=profile,
            diff_output_path=diff,
            run_contract=compare_contract,
        )
        self.assertTrue(metrics.passed, metrics.failure_reasons)
        self.assertEqual(metrics.registry_digest, profile.registry_sha256)
        self.assertEqual(metrics.reference_icc_profile_id, "implicit-sRGB-none")
        self.assertEqual(metrics.actual_icc_profile_id, "implicit-sRGB-none")
        self.assertEqual(
            [(item.role, item.producer) for item in metrics.input_bindings],
            [
                ("normalized-reference", "intake-normalizer-v1"),
                ("render-preview", "resvg-v0.47.0"),
            ],
        )
        self.assertEqual(metrics.metric_max_pixels, 4_194_304)
        self.assertEqual(metrics.match_ratio, 1.0)
        self.assertGreaterEqual(metrics.ssim, profile.ssim_minimum)


if __name__ == "__main__":
    unittest.main(verbosity=2)
