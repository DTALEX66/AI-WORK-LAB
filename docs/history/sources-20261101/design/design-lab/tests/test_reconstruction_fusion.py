# SPDX-License-Identifier: MIT
"""Behavioral contracts for bounded vector-candidate selection and scene fusion."""
from __future__ import annotations

import sys
import unittest
import hashlib
from dataclasses import dataclass
from pathlib import Path
import shutil
from types import SimpleNamespace

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))
RUNTIME_ROOT = PROJECT_ROOT / ".project-local" / "task-runtime" / "a4-fusion-tests"


_SAFE_SVG = b'<svg width="10" height="10" viewBox="0 0 10 10"><rect x="0" y="0" width="10" height="10" fill="#123456" /></svg>'


class ReconstructionFusionTests(unittest.TestCase):
    def test_smallest_safe_passing_vector_candidate_wins(self) -> None:
        """Changing quality, safety, or tie-break ordering must make this selection fail."""
        from reconstruction.vector_candidates import LocalMetrics, VectorCandidate, select_candidate

        large = VectorCandidate("vtracer-local", "shape", _SAFE_SVG, 20, LocalMetrics(0.997, True))
        failing = VectorCandidate("starvector-local", "shape", _SAFE_SVG, 1, LocalMetrics(0.994, True))
        small = VectorCandidate("starvector-local", "shape", _SAFE_SVG, 3, LocalMetrics(0.996, True))
        unsafe = VectorCandidate("unsafe-local", "shape", b'<svg width="10" height="10" viewBox="0 0 10 10"><script /></svg>', 1, LocalMetrics(1.0, True))

        selected = select_candidate((large, failing, small, unsafe))

        self.assertIs(selected, small)

    def test_full_canvas_reference_layer_is_rejected_for_flat_profile(self) -> None:
        """An opaque raster reference cannot be smuggled into a flat/UI RIR as a layer."""
        from reconstruction.fusion import ReferenceOverlayError, SceneAnalysis, fuse_scene
        from reconstruction.matting import LayerProposal

        reference = LayerProposal(
            "reference", "reference-overlay", 0, (0, 0, 100, 100), (0, 0, 100, 100),
            PROJECT_ROOT / ".project-local" / "task-runtime" / "fusion" / "reference.png", False, 1.0,
        )

        with self.assertRaises(ReferenceOverlayError):
            fuse_scene(SceneAnalysis(100, 100, "flat"), (reference,), ())

    def test_mixed_profile_allows_semantic_full_canvas_background_but_flat_rejects_raster_over_budget(self) -> None:
        """Raster exceptions are profile-bound; changing this leaks a reference overlay into flat/UI work."""
        from reconstruction.fusion import RasterBudgetExceeded, SceneAnalysis, fuse_scene
        from reconstruction.matting import LayerProposal

        background = LayerProposal(
            "background", "semantic-background", 0, (0, 0, 100, 100), (0, 0, 100, 100),
            PROJECT_ROOT / ".project-local" / "task-runtime" / "fusion" / "background.png", False, 1.0,
        )
        mixed = fuse_scene(SceneAnalysis(100, 100, "mixed"), (background,), ())

        self.assertEqual(mixed["layers"][0]["type"], "raster")
        with self.assertRaises(RasterBudgetExceeded):
            fuse_scene(SceneAnalysis(100, 100, "flat"), (background,), ())

    def test_selected_safe_rect_candidate_becomes_editable_rir_primitive(self) -> None:
        """A selected vector proposal must become an editable RIR node, not merely pass a sanitizer."""
        from reconstruction.fusion import SceneAnalysis, fuse_scene
        from reconstruction.vector_candidates import LocalMetrics, VectorCandidate

        candidate = VectorCandidate(
            "vtracer-local", "logo", b'<svg width="100" height="80" viewBox="0 0 100 80"><rect x="10" y="20" width="30" height="40" fill="#abcdef" /></svg>',
            1, LocalMetrics(0.999, True),
        )

        rir = fuse_scene(SceneAnalysis(100, 80, "flat"), (), (candidate,))

        self.assertEqual(rir["layers"][0]["id"], "logo")
        self.assertEqual(rir["layers"][0]["type"], "primitive")
        self.assertEqual(rir["layers"][0]["primitive"]["kind"], "rect")
        self.assertEqual(rir["layers"][0]["bounds"], {"x": 10.0, "y": 20.0, "width": 30.0, "height": 40.0})

    def test_fusion_selects_one_safe_candidate_per_object(self) -> None:
        """A global winner would drop other scene objects, so selection is scoped to object identity."""
        from reconstruction.fusion import SceneAnalysis, fuse_scene
        from reconstruction.vector_candidates import LocalMetrics, VectorCandidate

        first_large = VectorCandidate("vtracer-local", "first", _SAFE_SVG, 8, LocalMetrics(0.999, True))
        first_small = VectorCandidate("starvector-local", "first", _SAFE_SVG, 3, LocalMetrics(0.998, True))
        second = VectorCandidate("vtracer-local", "second", _SAFE_SVG, 4, LocalMetrics(0.997, True))

        rir = fuse_scene(SceneAnalysis(100, 80, "flat"), (), (first_large, second, first_small))

        self.assertEqual([node["id"] for node in rir["layers"]], ["first", "second"])

    def test_missing_local_vector_providers_are_explicit_recoverable_fallbacks(self) -> None:
        """Neither VTracer nor StarVector may silently claim vector output without local artifacts."""
        from reconstruction.vector_candidates import VectorProviderUnavailable
        from reconstruction.providers.starvector_provider import StarVectorProvider
        from reconstruction.providers.vtracer_provider import VTracerProvider

        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        vtracer = VTracerProvider(self._descriptor("vtracer-local", "external-binary"), external_roots=(RUNTIME_ROOT,))
        starvector = StarVectorProvider(self._descriptor("starvector-local", "cuda"), external_roots=(RUNTIME_ROOT,))
        with self.assertRaises(VectorProviderUnavailable) as first:
            vtracer.propose_candidates(_FixtureRequest())
        with self.assertRaises(VectorProviderUnavailable) as second:
            starvector.propose_candidates(_FixtureRequest())

        self.assertEqual(first.exception.events[0].code, "MISSING")
        self.assertEqual(second.exception.events[0].code, "MISSING")

    def test_vtracer_executes_fixed_official_input_output_arguments_inside_run_root(self) -> None:
        """The binary may only receive the bound source and a newly-created run-local SVG target."""
        from reconstruction.providers.vtracer_provider import VTracerProvider

        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        descriptor = self._descriptor("vtracer-local", "external-binary")
        descriptor.local_path.write_bytes(b"fixture")
        source = RUNTIME_ROOT / "source.png"
        Image.new("RGBA", (10, 10), "#123456").save(source)
        run_root = RUNTIME_ROOT / "run"
        run_root.mkdir()
        calls: list[list[str]] = []

        def fake_run(arguments: list[str], **_kwargs: object) -> SimpleNamespace:
            calls.append(arguments)
            Path(arguments[arguments.index("--output") + 1]).write_bytes(_SAFE_SVG)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        candidates = VTracerProvider(
            descriptor, external_roots=(RUNTIME_ROOT,), subprocess_run=fake_run,
        ).propose_candidates(_VTracerRequest(run_root, source, "icon", "flat"))

        self.assertEqual(len(candidates), 1)
        self.assertEqual(calls[0][1:5], ["--input", str(source), "--output", str(candidates[0].svg_path)])
        self.assertTrue(candidates[0].svg_path.is_relative_to(run_root))

    def _descriptor(self, provider_id: str, device: str):
        from reconstruction.providers.base import ProviderDescriptor

        return ProviderDescriptor(
            "binary" if device == "external-binary" else "model", provider_id, provider_id, "test-v1", "test-v1",
            "local-fixture", "MIT", "ALLOWED", hashlib.sha256(b"fixture").hexdigest(), "test",
            RUNTIME_ROOT / f"{provider_id}.artifact", False, device, 0, ("vector-candidate",), False, 1, (), "QUALIFIED",
        )


@dataclass(frozen=True)
class _FixtureRequest:
    profile: str = "flat"


@dataclass(frozen=True)
class _VTracerRequest:
    run_root: Path
    source_path: Path
    object_id: str
    profile: str


if __name__ == "__main__":
    unittest.main()
