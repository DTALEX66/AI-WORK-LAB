# SPDX-License-Identifier: MIT
"""Behavioral contracts for bounded reconstruction semantic proposals."""
from __future__ import annotations

import errno
import hashlib
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / ".project-local" / "task-runtime" / "a2-semantics-tests"

# The reconstruction package lives under packages/capabilities, and this module bootstraps its own
# import path exactly the way its sibling test_reconstruction_evidence.py does. Without these two
# inserts all 13 cases here died with `ModuleNotFoundError: No module named 'reconstruction'` --
# thirteen errors that read as "the capability is missing" while the code they exercise is present at
# packages/capabilities/reconstruction/{geometry,font_match,providers}/. A test that cannot import the
# thing it tests has measured nothing, and reporting that as a capability finding would be the wrong
# conclusion, so the path is fixed here rather than the assertion being removed.
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


class ReconstructionSemanticTests(unittest.TestCase):
    """These tests describe observable proposal and fallback behavior."""

    def setUp(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)

    def test_text_normalization_preserves_global_canvas_coordinates_for_latin_and_chinese(self) -> None:
        # A broken pixel-to-global conversion must make these literal coordinates fail.
        from reconstruction.geometry import normalize_text_detection

        latin = normalize_text_detection(
            {"text": "DESIGN", "polygon": [[20, 10], [180, 10], [180, 50], [20, 50]], "confidence": 0.98},
            (200, 100),
        )
        chinese = normalize_text_detection(
            {"text": "设计", "polygon": [[20, 60], [100, 60], [100, 90], [20, 90]], "confidence": 0.91, "direction": "ltr"},
            (200, 100),
        )

        self.assertEqual(latin.polygon, ((0.1, 0.1), (0.9, 0.1), (0.9, 0.5), (0.1, 0.5)))
        self.assertEqual(chinese.polygon[0], (0.1, 0.6))
        self.assertEqual(chinese.direction, "ltr")

    def test_text_validation_rejects_invalid_confidence_non_finite_and_degenerate_polygon(self) -> None:
        # Removing any validation branch must let malformed untrusted output through.
        from reconstruction.geometry import ProposalValidationError, normalize_text_detection

        for raw in (
            {"text": "bad", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": 1.1},
            {"text": "bad", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": float("nan")},
            {"text": "bad", "polygon": [[0, 0], [10, 0], [20, 0]], "confidence": 0.5},
            {"text": 7, "polygon": [[0, 0], [10, 0], [10, 10]], "confidence": 0.5},
            {"text": "bad", "polygon": [[0, 0], [10, 0], [10, 10]], "confidence": 0.5, "direction": []},
        ):
            with self.assertRaises(ProposalValidationError):
                normalize_text_detection(raw, (20, 20))

    def test_primitive_analysis_is_deterministic_for_rectangle_circle_and_gradient(self) -> None:
        # Using only the top-left pixel as background breaks touching/full-canvas fixtures.
        from reconstruction.geometry import analyze_primitives, normalize_primitive_detection

        rectangle = Image.new("RGBA", (32, 32), "white")
        ImageDraw.Draw(rectangle).rectangle((4, 6, 20, 18), fill="#123456")
        circle = Image.new("RGBA", (32, 32), "white")
        ImageDraw.Draw(circle).ellipse((6, 6, 24, 24), fill="#123456")
        gradient = Image.new("RGBA", (32, 32), "white")
        pixels = gradient.load()
        for x in range(4, 28):
            for y in range(6, 22):
                pixels[x, y] = (x * 8, 20, 80, 255)

        self.assertEqual(analyze_primitives(rectangle)[0].kind, "rectangle")
        self.assertEqual(analyze_primitives(circle)[0].kind, "circle")
        detected_gradient = analyze_primitives(gradient)[0]
        self.assertEqual(detected_gradient.kind, "gradient")
        self.assertEqual(detected_gradient.bounds, (0.125, 0.1875, 0.875, 0.6875))
        top_left_touching = Image.new("RGBA", (40, 30), "white")
        ImageDraw.Draw(top_left_touching).rectangle((0, 0, 12, 18), fill="#123456")
        self.assertEqual(analyze_primitives(top_left_touching)[0].bounds, (0.0, 0.0, 0.325, 19 / 30))
        self.assertEqual(analyze_primitives(Image.new("RGBA", (40, 30), "#123456"))[0].kind, "rectangle")
        full_gradient = Image.new("RGBA", (40, 30))
        for x in range(40):
            for y in range(30):
                full_gradient.putpixel((x, y), (x * 6, y * 8, 30, 255))
        self.assertEqual(analyze_primitives(full_gradient)[0].kind, "gradient")
        horizontal_gradient = Image.new("RGBA", (40, 30))
        vertical_gradient = Image.new("RGBA", (40, 30))
        for x in range(40):
            for y in range(30):
                horizontal_gradient.putpixel((x, y), (x * 6, 20, 80, 255))
                vertical_gradient.putpixel((x, y), (20, y * 8, 80, 255))
        for fixture in (horizontal_gradient, vertical_gradient):
            first, second = analyze_primitives(fixture), analyze_primitives(fixture)
            self.assertEqual(first, second)
            self.assertEqual(first[0].kind, "gradient")
            self.assertEqual(first[0].bounds, (0.0, 0.0, 1.0, 1.0))
        wide_circle = normalize_primitive_detection(
            {"kind": "circle", "bounds": [50, 20, 40, 40], "fill": "#123456", "stroke": None, "radius": 20, "confidence": 1.0},
            (200, 100),
        )
        self.assertEqual(wide_circle.bounds, (0.25, 0.2, 0.45, 0.6))
        self.assertEqual(wide_circle.radius, (0.1, 0.2))

    def test_ui_controls_are_valid_primitive_proposals_but_unknown_fields_are_rejected(self) -> None:
        # A loose schema would accept model-specific fields or lose the UI-control geometry.
        from reconstruction.geometry import ProposalValidationError, normalize_primitive_detection

        control = normalize_primitive_detection(
            {"kind": "rectangle", "bounds": [10, 20, 80, 30], "fill": "#102030", "stroke": "#ffffff", "radius": 6, "confidence": 0.8},
            (200, 100),
        )
        self.assertEqual(control.bounds, (0.05, 0.2, 0.45, 0.5))
        with self.assertRaises(ProposalValidationError):
            normalize_primitive_detection(
                {"kind": "rectangle", "bounds": [0, 0, 1, 1], "fill": "#000000", "stroke": None, "radius": 0, "confidence": 1, "model_debug": "leak"},
                (20, 20),
            )

    def test_enumerated_font_is_editable_only_for_an_exact_rendered_crop(self) -> None:
        # Permitting a merely similar face would make a typography substitution silently editable.
        from reconstruction.font_match import FontFace, match_font, render_text_crop

        font_root = RUNTIME_ROOT / "authorized-fonts"
        font_root.mkdir()
        font_path = font_root / "candidate.font"
        font_path.write_bytes(b"test metadata, not a font file")
        face = FontFace("safe-face-id", font_path, font_root, 24)
        crop = RUNTIME_ROOT / "exact.png"
        with mock.patch("reconstruction.font_match.ImageFont.truetype", return_value=ImageFont.load_default()):
            render_text_crop("DESIGN", face).save(crop)
            result = match_font("DESIGN", crop, [face], crop_root=RUNTIME_ROOT)

        self.assertEqual(result.face_id, "safe-face-id")
        self.assertTrue(result.keep_editable_text)
        self.assertIsNone(result.fallback)

    def test_font_paths_require_explicit_authorized_roots_regular_files_and_stable_reads(self) -> None:
        # Removing any containment, reparse, hardlink, or TOCTOU check leaks untrusted font/crop state.
        from reconstruction.font_match import FontFace, match_font, render_text_crop

        font_root = RUNTIME_ROOT / "authorized-fonts"
        font_root.mkdir()
        font_path = font_root / "candidate.font"
        font_path.write_bytes(b"test metadata, not a font file")
        exact = FontFace("safe-face-id", font_path, font_root, 24)
        crop = RUNTIME_ROOT / "chinese.png"
        with mock.patch("reconstruction.font_match.ImageFont.truetype", return_value=ImageFont.load_default()):
            render_text_crop("设计", exact).save(crop)
            wrong = FontFace("different-face-id", font_path, font_root, 25)
            wrong_crop = RUNTIME_ROOT / "wrong.png"
            with Image.open(crop) as source:
                changed = source.convert("RGBA")
            changed.putpixel((0, 0), (255, 0, 0, 255))
            changed.save(wrong_crop)
            self.assertEqual(match_font("设计", wrong_crop, [wrong], crop_root=RUNTIME_ROOT).fallback, "outline")
            outside = RUNTIME_ROOT / "outside.png"
            outside.write_bytes(crop.read_bytes())
            self.assertEqual(match_font("设计", outside, [exact], crop_root=RUNTIME_ROOT / "only-this").fallback, "outline")
            crop_hardlink = RUNTIME_ROOT / "crop-hardlink.png"
            os.link(crop, crop_hardlink)
            self.assertEqual(match_font("设计", crop_hardlink, [exact], crop_root=RUNTIME_ROOT).fallback, "outline")
            font_hardlink = font_root / "font-hardlink.font"
            os.link(font_path, font_hardlink)
            hardlinked_face = FontFace("hardlinked-face", font_hardlink, font_root, 24)
            regular_crop = RUNTIME_ROOT / "regular-crop.png"
            regular_crop.write_bytes(crop.read_bytes())
            self.assertEqual(match_font("设计", regular_crop, [hardlinked_face], crop_root=RUNTIME_ROOT).fallback, "outline")
            ancestor = RUNTIME_ROOT / "ancestor"
            ancestor.mkdir()
            nested_crop = ancestor / "nested.png"
            nested_crop.write_bytes(regular_crop.read_bytes())
            with mock.patch("reconstruction.font_match._is_reparse", side_effect=lambda path: path == ancestor):
                self.assertEqual(match_font("设计", nested_crop, [exact], crop_root=RUNTIME_ROOT).fallback, "outline")
            from reconstruction.font_match import _sha256_file
            mutated = False
            def mutate_after_hash(path):
                nonlocal mutated
                digest = _sha256_file(path)
                if path == regular_crop and not mutated:
                    mutated = True
                    regular_crop.write_bytes(b"mutated")
                return digest
            with mock.patch("reconstruction.font_match._sha256_file", side_effect=mutate_after_hash):
                self.assertEqual(match_font("设计", regular_crop, [exact], crop_root=RUNTIME_ROOT).fallback, "outline")
        self.assertEqual(list(RUNTIME_ROOT.glob("*.ttf")), [])

    def test_paddle_preflight_and_proposal_are_structured_fallbacks_without_a_local_runtime(self) -> None:
        # A provider that reports READY or writes outside its proposal target breaks the SPI boundary.
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        descriptor = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED")
        provider = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,))
        preflight = provider.preflight(task="ocr")
        self.assertFalse(preflight.ready)
        self.assertEqual(preflight.status, "MISSING")
        request = self._request(descriptor, "ocr")
        result = provider.propose(request)
        self.assertEqual(result.events[0].code, "MISSING")
        self.assertTrue(result.proposal_path.is_file())
        self.assertTrue(result.proposal_path.is_relative_to(request.run_root))
        self.assertNotIn(b"PASS", result.proposal_path.read_bytes())

    def test_paddle_oom_and_omniparser_license_policy_fail_closed(self) -> None:
        # Removing resource/license policy checks must never make either provider ready.
        from reconstruction.providers.omniparser_provider import OmniParserProvider
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        paddle = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED", minimum_vram_mib=8192)
        self.assertEqual(PaddleOCRProvider(paddle, available_vram_mib=1, external_roots=(RUNTIME_ROOT,)).preflight(task="ocr").status, "OOM")
        omni = self._descriptor("omniparser-local", "ui-analysis", commercial_use="DENIED", qualification="DISABLED_LICENSE_CONFLICT")
        provider = OmniParserProvider(omni, external_roots=(RUNTIME_ROOT,))
        self.assertEqual(provider.preflight(task="ui-analysis", profile="ui").status, "LICENSE_DENIED")
        result = provider.propose(self._request(omni, "ui-analysis", profile="ui"))
        self.assertEqual(result.events[0].code, "LICENSE_DENIED")
        self.assertFalse(result.events[0].recoverable is False)
        policy_bypass = self._descriptor("omniparser-local", "ui-analysis", commercial_use="ALLOWED", qualification="QUALIFIED")
        policy_bypass.local_path.write_bytes(b"fixture")
        self.assertEqual(
            OmniParserProvider(policy_bypass, external_roots=(RUNTIME_ROOT,)).preflight(task="ui-analysis", profile="ui").status,
            "LICENSE_DENIED",
        )

    def test_paddle_runner_bounds_oom_classification_and_postwrite_boundary_validation(self) -> None:
        # Generators/oversized output must degrade; only recognized CUDA/backend OOM becomes OOM.
        from reconstruction.providers.base import ProposalBoundaryError
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        descriptor = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED")
        descriptor.local_path.write_bytes(b"fixture")
        valid = {"text": "DESIGN", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": 1.0}
        generator = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: iter((valid,)))
        generator_request = self._request(descriptor, "ocr", suffix="generator")
        self.assertEqual(generator.propose(generator_request).events[0].code, "PROVIDER_DEGRADED")
        self.assertFalse(generator_request.outputs[0].path.exists())
        oversized = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: [valid] * 257)
        oversized_request = self._request(descriptor, "ocr", suffix="oversized")
        self.assertEqual(oversized.propose(oversized_request).events[0].code, "PROVIDER_DEGRADED")
        self.assertFalse(oversized_request.outputs[0].path.exists())
        oom = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: (_ for _ in ()).throw(RuntimeError("CUDA out of memory")))
        self.assertEqual(oom.propose(self._request(descriptor, "ocr", suffix="oom")).events[0].code, "OOM")
        generic = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: (_ for _ in ()).throw(RuntimeError("bad backend response")))
        with self.assertRaises(RuntimeError):
            generic.propose(self._request(descriptor, "ocr", suffix="generic"))
        boundary = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: [valid])
        rejected_request = self._request(descriptor, "ocr", suffix="postwrite")
        with mock.patch("reconstruction.providers.paddleocr_provider.validate_proposal_result", side_effect=ProposalBoundaryError("reject")):
            rejected = boundary.propose(rejected_request)
        self.assertEqual(rejected.events[0].code, "PROVIDER_DEGRADED")
        self.assertFalse(rejected_request.outputs[0].path.exists())
        self.assertEqual(boundary.propose(rejected_request).events, ())
        byte_limited_request = self._request(descriptor, "ocr", suffix="bytes")
        with mock.patch("reconstruction.providers.paddleocr_provider.MAX_PROPOSAL_BYTES", 1):
            byte_limited = boundary.propose(byte_limited_request)
        self.assertEqual(byte_limited.events[0].code, "PROVIDER_DEGRADED")
        self.assertFalse(byte_limited_request.outputs[0].path.exists())

    def test_paddle_staging_write_flush_fsync_and_close_failures_leave_no_owned_residue_and_retry(self) -> None:
        # Recording ownership only after close leaves a stage file behind on any earlier I/O error.
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        descriptor = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED")
        descriptor.local_path.write_bytes(b"fixture")
        valid = {"text": "DESIGN", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": 1.0}
        real_open = Path.open

        class FailingStageStream:
            def __init__(self, stream, phase):
                self._stream, self._phase = stream, phase

            def write(self, data):
                if self._phase == "write":
                    raise OSError("injected write failure")
                return self._stream.write(data)

            def flush(self):
                if self._phase == "flush":
                    raise OSError("injected flush failure")
                return self._stream.flush()

            def fileno(self):
                return self._stream.fileno()

            def close(self):
                self._stream.close()
                if self._phase == "close":
                    raise OSError("injected close failure")

        for phase in ("write", "flush", "fsync", "close"):
            provider = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: [valid])
            request = self._request(descriptor, "ocr", suffix=f"stage-{phase}")
            self.assertTrue(provider.preflight(task="ocr").ready, phase)
            def open_with_failure(path, *args, **kwargs):
                stream = real_open(path, *args, **kwargs)
                if path.name.endswith(".stage"):
                    return FailingStageStream(stream, phase)
                return stream
            with mock.patch("reconstruction.providers.paddleocr_provider.Path.open", new=open_with_failure), mock.patch(
                "reconstruction.providers.paddleocr_provider.os.fsync",
                side_effect=OSError("injected fsync failure") if phase == "fsync" else os.fsync,
            ):
                result = provider.propose(request)
            self.assertEqual(result.events[0].code, "PROVIDER_DEGRADED", (phase, result.events[0]))
            self.assertFalse(request.outputs[0].path.exists())
            self.assertEqual(list(request.run_root.rglob("*.stage")), [])
            self.assertEqual(provider.propose(request).events, ())

    def test_paddle_staging_path_stat_failure_leaves_no_owned_residue_and_retries(self) -> None:
        # Recording ownership through the path loses the exclusively created stage if that stat fails.
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        descriptor = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED")
        descriptor.local_path.write_bytes(b"fixture")
        valid = {"text": "DESIGN", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": 1.0}
        provider = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: [valid])
        request = self._request(descriptor, "ocr", suffix="stage-path-stat")
        real_stat = Path.stat
        failed = False

        def fail_first_stage_stat(path, *args, **kwargs):
            nonlocal failed
            if path.name.endswith(".stage") and not failed:
                failed = True
                raise OSError(errno.EIO, "injected stage path stat failure")
            return real_stat(path, *args, **kwargs)

        with mock.patch("reconstruction.providers.paddleocr_provider.Path.stat", new=fail_first_stage_stat):
            result = provider.propose(request)
        self.assertTrue(failed)
        self.assertEqual(result.events[0].code, "PROVIDER_DEGRADED")
        self.assertFalse(request.outputs[0].path.exists())
        self.assertEqual(list(request.run_root.rglob("*.stage")), [])
        self.assertEqual(provider.propose(request).events, ())

    def test_paddle_staging_handle_path_identity_mismatch_hard_fails_without_deleting_path(self) -> None:
        # Trusting the path stat as the owner would delete a path whose identity differs from the open handle.
        from reconstruction.providers.base import ProviderError
        from reconstruction.providers.paddleocr_provider import PaddleOCRProvider

        descriptor = self._descriptor("paddleocr-local", "ocr", qualification="QUALIFIED")
        descriptor.local_path.write_bytes(b"fixture")
        valid = {"text": "DESIGN", "polygon": [[0, 0], [1, 0], [1, 1]], "confidence": 1.0}
        provider = PaddleOCRProvider(descriptor, external_roots=(RUNTIME_ROOT,), runner=lambda request: [valid])
        request = self._request(descriptor, "ocr", suffix="stage-identity-mismatch")
        real_open = Path.open
        real_stat = os.stat

        class FailingWriteStream:
            def __init__(self, stream):
                self._stream = stream

            def write(self, data):
                raise OSError("injected write failure")

            def flush(self):
                return self._stream.flush()

            def fileno(self):
                return self._stream.fileno()

            def close(self):
                return self._stream.close()

        def open_with_write_failure(path, *args, **kwargs):
            stream = real_open(path, *args, **kwargs)
            if path.name.endswith(".stage"):
                return FailingWriteStream(stream)
            return stream

        def displaced_stage_stat(path, *args, **kwargs):
            state = real_stat(path, *args, **kwargs)
            try:
                candidate = Path(os.fspath(path))
            except TypeError:
                return state
            if not candidate.name.endswith(".stage"):
                return state
            fields = list(state)
            fields[1] = state.st_ino + 1
            return os.stat_result(fields)

        with mock.patch("reconstruction.providers.paddleocr_provider.Path.open", new=open_with_write_failure), mock.patch(
            "reconstruction.providers.paddleocr_provider.os.stat", side_effect=displaced_stage_stat
        ), self.assertRaises(ProviderError):
            provider.propose(request)
        stages = list(request.run_root.rglob("*.stage"))
        self.assertEqual(len(stages), 1)
        stages[0].unlink()
        self.assertEqual(provider.propose(request).events, ())

    def test_omniparser_rejects_wrong_task_or_profile_before_registry_and_forces_license_denied_for_ui(self) -> None:
        # Moving the registry call before profile/task routing could activate the forbidden adapter.
        from reconstruction.providers.omniparser_provider import OmniParserProvider

        descriptor = self._descriptor("omniparser-local", "ui-analysis", qualification="QUALIFIED")
        descriptor.local_path.write_bytes(b"fixture")
        provider = OmniParserProvider(descriptor, external_roots=(RUNTIME_ROOT,))
        with mock.patch.object(provider._registered, "preflight", side_effect=AssertionError("registry must not be called")):
            self.assertEqual(provider.preflight(task="ocr", profile="ui").status, "NO_PROVIDER")
            self.assertEqual(provider.preflight(task="ui-analysis", profile="flat").status, "NO_PROVIDER")
            self.assertEqual(provider.preflight(task="ui-analysis", profile=None).status, "NO_PROVIDER")
        self.assertEqual(provider.preflight(task="ui-analysis", profile="ui").status, "LICENSE_DENIED")
        wrong_task = provider.propose(self._request(descriptor, "ocr", profile="ui", suffix="wrong-task"))
        self.assertEqual(wrong_task.events[0].code, "NO_PROVIDER")

    def _descriptor(self, provider_id: str, task: str, *, qualification: str, commercial_use: str = "ALLOWED", minimum_vram_mib: int = 0):
        from reconstruction.providers.base import ProviderDescriptor

        path = RUNTIME_ROOT / f"{provider_id}.manifest"
        return ProviderDescriptor(
            "model", provider_id, provider_id, "test-v1", "test-v1", "local-fixture", "MIT", commercial_use,
            hashlib.sha256(b"fixture").hexdigest(), "test", path, False, "cuda", minimum_vram_mib,
            (task,), False, 1, (), qualification,
        )

    def _request(self, descriptor, task: str, *, profile: str = "flat", suffix: str = ""):
        from reconstruction.providers.base import AuthorizedOutput, ProposalRequest

        run_root = RUNTIME_ROOT / f"run{suffix}"
        proposal = run_root / "proposals" / f"{descriptor.provider_id}.json"
        source = RUNTIME_ROOT / "source.png"
        Image.new("RGBA", (1, 1), "white").save(source)
        run_root.mkdir(exist_ok=True)
        return ProposalRequest(
            "run-a2", "job-a2", run_root, source, hashlib.sha256(source.read_bytes()).hexdigest(), profile, task,
            "local", "contract", (AuthorizedOutput("proposal", "provider-proposal", proposal, None),),
            descriptor.provider_id, descriptor.provider_version,
        )


if __name__ == "__main__":
    unittest.main()
