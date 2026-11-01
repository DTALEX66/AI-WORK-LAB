# SPDX-License-Identifier: MIT
"""Behavioral contracts for local transparent-layer reconstruction."""
from __future__ import annotations

import shutil
import sys
import unittest
from dataclasses import dataclass
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / ".project-local" / "task-runtime" / "a3-layer-tests"
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


@dataclass(frozen=True)
class _FixtureRequest:
    run_root: Path
    source_path: Path
    profile: str = "flat"


class ReconstructionLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)

    def test_transparent_layers_are_tightly_cropped_sorted_and_recompose_source(self) -> None:
        """Removing alpha normalization, ordering, or source preservation breaks this fixture."""
        from reconstruction.matting import LayerProposal, composite_layers, decompose_layers

        source = Image.new("RGBA", (24, 18), "#f5f5f5")
        ImageDraw.Draw(source).rectangle((4, 3, 15, 12), fill="#114477")
        ImageDraw.Draw(source).ellipse((10, 7, 20, 16), fill="#ee9933")
        source_path = RUNTIME_ROOT / "source.png"
        source.save(source_path)

        background = Image.new("RGBA", source.size, "#f5f5f5")
        blue = Image.new("RGBA", source.size)
        ImageDraw.Draw(blue).rectangle((4, 3, 15, 12), fill="#114477")
        orange = Image.new("RGBA", source.size)
        ImageDraw.Draw(orange).ellipse((10, 7, 20, 16), fill="#ee9933")
        provider = _StaticProvider(
            (
                LayerProposal("orange", "foreground", 20, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "orange.png", False, 0.9, orange),
                LayerProposal("background", "background", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "background.png", False, 1.0, background),
                LayerProposal("blue", "shape", 10, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "blue.png", False, 0.95, blue),
            )
        )

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path), (provider,))

        self.assertEqual([layer.id for layer in layers], ["background", "blue", "orange"])
        self.assertEqual(layers[1].crop, (4, 3, 16, 13))
        self.assertEqual(layers[2].crop, (10, 7, 21, 17))
        self.assertTrue(all(layer.asset_path.is_relative_to(RUNTIME_ROOT) for layer in layers))
        self.assertEqual(composite_layers(layers, source.size).tobytes(), source.tobytes())

    def test_occlusion_completion_is_explicitly_inferred(self) -> None:
        """An inferred completion must never be silently represented as observed pixels."""
        from reconstruction.matting import LayerProposal, decompose_layers

        source = Image.new("RGBA", (8, 8), "#ffffff")
        source_path = RUNTIME_ROOT / "occluded-source.png"
        source.save(source_path)
        inferred = Image.new("RGBA", (8, 8))
        ImageDraw.Draw(inferred).rectangle((2, 2, 5, 5), fill="#000000")
        provider = _StaticProvider((
            LayerProposal("completed", "occluded-object", 1, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "completed.png", True, 0.4, inferred),
        ))

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path), (provider,))

        self.assertTrue(layers[0].inferred)

    def test_missing_layerd_runtime_is_an_explicit_recoverable_fallback(self) -> None:
        """A missing local model must not silently yield an empty trusted layer set."""
        from reconstruction.matting import LayerProviderUnavailable
        from reconstruction.providers.layerd_provider import LayerDProvider

        descriptor = self._descriptor("layerd-local", "layer-decomposition")
        provider = LayerDProvider(descriptor, external_roots=(RUNTIME_ROOT,))
        with self.assertRaises(LayerProviderUnavailable) as raised:
            provider.propose_layers(_FixtureRequest(RUNTIME_ROOT, RUNTIME_ROOT / "missing.png"))

        self.assertEqual(raised.exception.events[0].code, "MISSING")
        self.assertTrue(raised.exception.events[0].recoverable)

    def test_provider_oom_records_event_then_uses_next_local_provider(self) -> None:
        """A recoverable LayerD failure must not prevent the approved local matte fallback."""
        from reconstruction.matting import LayerProposal, LayerProviderUnavailable, decompose_layers
        from reconstruction.providers.base import FallbackEvent

        source = Image.new("RGBA", (6, 6), "#123456")
        source_path = RUNTIME_ROOT / "fallback-source.png"
        source.save(source_path)
        fallback = _StaticProvider((
            LayerProposal("fallback", "foreground", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "fallback.png", False, 1.0, source),
        ))
        unavailable = _UnavailableProvider(LayerProviderUnavailable((FallbackEvent(
            "layerd-local", "OOM", "layer-decomposition", "fixture OOM", True,
        ),)))
        events: list[FallbackEvent] = []

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path), (unavailable, fallback), event_log=events)

        self.assertEqual([layer.id for layer in layers], ["fallback"])
        self.assertEqual([event.code for event in events], ["OOM"])

    def test_sam_birefnet_is_profile_gated_and_missing_weights_are_recoverable(self) -> None:
        """The foreground-matte fallback must be local, profile-bound, and explicit on absence."""
        from reconstruction.matting import LayerProviderUnavailable
        from reconstruction.providers.sam_birefnet_provider import SamBiRefNetProvider

        sam = self._descriptor("sam2-local", "layer-decomposition")
        birefnet = self._descriptor("birefnet-local", "foreground-matting")
        provider = SamBiRefNetProvider(sam, birefnet, external_roots=(RUNTIME_ROOT,))
        flat_request = _FixtureRequest(RUNTIME_ROOT, RUNTIME_ROOT / "missing.png", "flat")
        with self.assertRaises(LayerProviderUnavailable) as flat:
            provider.propose_layers(flat_request)
        self.assertEqual(flat.exception.events[0].code, "NO_PROVIDER")
        mixed_request = _FixtureRequest(RUNTIME_ROOT, RUNTIME_ROOT / "missing.png", "mixed")
        with self.assertRaises(LayerProviderUnavailable) as missing:
            provider.propose_layers(mixed_request)
        self.assertEqual(missing.exception.events[0].code, "MISSING")
        self.assertTrue(missing.exception.events[0].recoverable)

    def test_profile_routing_skips_ineligible_provider_without_fallback_noise(self) -> None:
        """A flat request must route past a foreground-only provider before invoking it."""
        from reconstruction.matting import LayerProposal, decompose_layers
        from reconstruction.providers.base import FallbackEvent

        source = Image.new("RGBA", (4, 4), "#778899")
        source_path = RUNTIME_ROOT / "routing-source.png"
        source.save(source_path)
        skipped = _ProfileUnavailableProvider(False, FallbackEvent(
            "sam2-local", "NO_PROVIDER", "foreground-matting", "must not be called", True,
        ))
        fallback = _StaticProvider((
            LayerProposal("flat", "background", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "routing.png", False, 1.0, source),
        ))
        events: list[FallbackEvent] = []

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path, "flat"), (skipped, fallback), event_log=events)

        self.assertEqual([layer.id for layer in layers], ["flat"])
        self.assertEqual(skipped.calls, 0)
        self.assertEqual(events, [])

    def test_rejected_provider_cleans_its_partial_run_assets_before_fallback(self) -> None:
        """A malformed second layer must not leave the first provider asset behind on fallback."""
        from reconstruction.matting import LayerProposal, decompose_layers

        source = Image.new("RGBA", (5, 5), "#445566")
        source_path = RUNTIME_ROOT / "cleanup-source.png"
        source.save(source_path)
        partial_path = RUNTIME_ROOT / "partial.png"
        malformed = _StaticProvider((
            LayerProposal("first", "background", 0, (0, 0, 0, 0), (0, 0, 0, 0), partial_path, False, 1.0, source),
            LayerProposal("wrong-size", "bad", 1, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "bad.png", False, 1.0, Image.new("RGBA", (1, 1))),
        ))
        fallback = _StaticProvider((
            LayerProposal("fallback-after-reject", "background", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "cleanup-fallback.png", False, 1.0, source),
        ))

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path), (malformed, fallback))

        self.assertEqual([layer.id for layer in layers], ["fallback-after-reject"])
        self.assertFalse(partial_path.exists())

    def test_profile_routing_uses_lowest_provider_priority_first(self) -> None:
        """Mixed profiles must prefer LayerD-class priority before the heavier matte fallback."""
        from reconstruction.matting import LayerProposal, decompose_layers

        source = Image.new("RGBA", (4, 4), "#112233")
        source_path = RUNTIME_ROOT / "priority-source.png"
        source.save(source_path)
        first = _PrioritizedProvider(10, "layerd", LayerProposal(
            "layerd", "background", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "layerd-priority.png", False, 1.0, source,
        ))
        second = _PrioritizedProvider(20, "sam", LayerProposal(
            "sam", "foreground", 0, (0, 0, 0, 0), (0, 0, 0, 0), RUNTIME_ROOT / "sam-priority.png", False, 1.0, source,
        ))

        layers = decompose_layers(_FixtureRequest(RUNTIME_ROOT, source_path, "mixed"), (second, first))

        self.assertEqual([layer.id for layer in layers], ["layerd"])
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 0)

    def _descriptor(self, provider_id: str, task: str):
        from reconstruction.providers.base import ProviderDescriptor

        path = RUNTIME_ROOT / f"{provider_id}.manifest"
        return ProviderDescriptor(
            "model", provider_id, provider_id, "test-v1", "test-v1", "local-fixture", "MIT", "ALLOWED",
            hashlib.sha256(b"fixture").hexdigest(), "test", path, False, "cuda", 0,
            (task,), False, 1, (), "QUALIFIED",
        )


@dataclass(frozen=True)
class _StaticProvider:
    layers: tuple[object, ...]

    def propose_layers(self, _request: object) -> tuple[object, ...]:
        return self.layers


@dataclass(frozen=True)
class _UnavailableProvider:
    error: Exception

    def propose_layers(self, _request: object) -> tuple[object, ...]:
        raise self.error


class _ProfileUnavailableProvider:
    def __init__(self, allowed: bool, event: object) -> None:
        self._allowed = allowed
        self._event = event
        self.calls = 0

    def supports_profile(self, _profile: str) -> bool:
        return self._allowed

    def propose_layers(self, _request: object) -> tuple[object, ...]:
        self.calls += 1
        from reconstruction.matting import LayerProviderUnavailable
        raise LayerProviderUnavailable((self._event,))


class _PrioritizedProvider:
    def __init__(self, priority: int, name: str, layer: object) -> None:
        self._priority = priority
        self._name = name
        self._layer = layer
        self.calls = 0

    def supports_profile(self, _profile: str) -> bool:
        return True

    def priority_for_profile(self, _profile: str) -> int:
        return self._priority

    def propose_layers(self, _request: object) -> tuple[object, ...]:
        self.calls += 1
        return (self._layer,)


if __name__ == "__main__":
    unittest.main()
