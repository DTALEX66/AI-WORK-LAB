# SPDX-License-Identifier: MIT
"""Deterministic normalization for untrusted local RGBA layer proposals."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol, Sequence

from PIL import Image

from reconstruction.providers.base import FallbackEvent


class LayerProposalError(ValueError):
    """An untrusted layer proposal cannot be kept inside its run boundary."""


class LayerProviderUnavailable(LayerProposalError):
    """A local provider declined work with explicit, recoverable fallback events."""

    def __init__(self, events: Sequence[FallbackEvent]) -> None:
        self.events = tuple(events)
        super().__init__(self.events[0].message if self.events else "layer provider unavailable")


class NoLayerProviderSucceeded(LayerProposalError):
    """Every ordered local provider failed; callers receive the complete event history."""

    def __init__(self, events: Sequence[FallbackEvent]) -> None:
        self.events = tuple(events)
        super().__init__("no local layer provider succeeded")


@dataclass(frozen=True)
class LayerProposal:
    """One editable semantic layer; the raster itself is always run-local."""

    id: str
    semantic_name: str
    z_index: int
    crop: tuple[int, int, int, int]
    alpha_bounds: tuple[int, int, int, int]
    asset_path: Path
    inferred: bool
    confidence: float
    image: Image.Image | None = None


class LayerProvider(Protocol):
    def propose_layers(self, request: Any) -> Sequence[LayerProposal]: ...


def _providers_for_profile(profile: Any, providers: Sequence[LayerProvider]) -> tuple[LayerProvider, ...]:
    """Keep caller order while omitting providers that explicitly reject this profile."""

    ranked: list[tuple[int, int, LayerProvider]] = []
    for index, provider in enumerate(providers):
        supported = getattr(provider, "supports_profile", None)
        if supported is None or supported(profile):
            priority_for_profile = getattr(provider, "priority_for_profile", None)
            priority = priority_for_profile(profile) if priority_for_profile is not None else 1000
            if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 10000:
                raise LayerProposalError("layer provider priority must be a bounded integer")
            ranked.append((priority, index, provider))
    return tuple(item[2] for item in sorted(ranked))


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _run_local_target(path: Path, root: Path) -> Path:
    root = root.resolve(strict=False)
    target = path.resolve(strict=False)
    if not _within(target, root):
        raise LayerProposalError("layer asset escapes the declared run root")
    if target.suffix.lower() != ".png":
        raise LayerProposalError("layer asset must use a PNG path")
    return target


def _alpha_crop(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise LayerProposalError("layer has no visible alpha pixels")
    return tuple(int(value) for value in bounds)


def _normalize_layer(layer: LayerProposal, run_root: Path, canvas: tuple[int, int]) -> LayerProposal:
    if not isinstance(layer.id, str) or not layer.id or len(layer.id) > 128:
        raise LayerProposalError("layer id must be a non-empty bounded string")
    if not isinstance(layer.semantic_name, str) or not layer.semantic_name or len(layer.semantic_name) > 256:
        raise LayerProposalError("layer semantic name must be a non-empty bounded string")
    if isinstance(layer.z_index, bool) or not isinstance(layer.z_index, int):
        raise LayerProposalError("layer z index must be an integer")
    if not isinstance(layer.inferred, bool) or not isinstance(layer.confidence, (int, float)):
        raise LayerProposalError("layer inference and confidence fields are malformed")
    if not 0.0 <= float(layer.confidence) <= 1.0:
        raise LayerProposalError("layer confidence must be within [0, 1]")
    if layer.image is None:
        raise LayerProposalError("local provider did not supply an RGBA layer image")
    image = layer.image.convert("RGBA")
    if image.size != canvas:
        raise LayerProposalError("layer dimensions must match the normalized source canvas")
    crop = _alpha_crop(image)
    target = _run_local_target(layer.asset_path, run_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise LayerProposalError("layer asset target already exists")
    image.crop(crop).save(target, format="PNG")
    return replace(
        layer,
        crop=crop,
        alpha_bounds=crop,
        asset_path=target,
        confidence=float(layer.confidence),
        image=None,
    )


def _cleanup_normalized_assets(layers: Sequence[LayerProposal]) -> None:
    """Remove only assets created and recorded during this rejected provider attempt."""

    for layer in layers:
        path = layer.asset_path
        try:
            if path.is_symlink() or not path.is_file():
                raise LayerProposalError("rejected provider asset is no longer a regular file")
            path.unlink()
            if path.exists() or path.is_symlink():
                raise LayerProposalError("rejected provider asset remains after cleanup")
        except OSError as exc:
            raise LayerProposalError("rejected provider asset cannot be cleaned up") from exc


def decompose_layers(
    request: Any,
    providers: Sequence[LayerProvider],
    *,
    event_log: list[FallbackEvent] | None = None,
) -> list[LayerProposal]:
    """Accept the first local proposal, crop it deterministically, and persist only PNG assets."""

    ordered = _providers_for_profile(getattr(request, "profile", None), providers)
    if not ordered:
        raise NoLayerProviderSucceeded(())
    run_root = Path(request.run_root)
    source_path = Path(request.source_path)
    with Image.open(source_path) as source:
        canvas = source.size
    events: list[FallbackEvent] = []
    failures: list[Exception] = []
    for provider in ordered:
        normalized: list[LayerProposal] = []
        try:
            raw_layers = tuple(provider.propose_layers(request))
            if not raw_layers:
                raise LayerProposalError("provider returned no layers")
            for layer in raw_layers:
                normalized.append(_normalize_layer(layer, run_root, canvas))
            ids = [layer.id for layer in normalized]
            if len(ids) != len(set(ids)):
                raise LayerProposalError("provider returned duplicate layer ids")
            if event_log is not None:
                event_log.extend(events)
            return sorted(normalized, key=lambda layer: (layer.z_index, layer.id))
        except LayerProviderUnavailable as exc:
            events.extend(exc.events)
            failures.append(exc)
        except LayerProposalError as exc:
            _cleanup_normalized_assets(normalized)
            failures.append(exc)
    if event_log is not None:
        event_log.extend(events)
    raise NoLayerProviderSucceeded(events) from failures[-1]


def composite_layers(layers: Sequence[LayerProposal], canvas: tuple[int, int]) -> Image.Image:
    """Recompose persisted, tightly cropped layers in their explicit z order."""

    composite = Image.new("RGBA", canvas)
    for layer in sorted(layers, key=lambda item: (item.z_index, item.id)):
        left, top, right, bottom = layer.crop
        if not (0 <= left < right <= canvas[0] and 0 <= top < bottom <= canvas[1]):
            raise LayerProposalError("layer crop is outside the target canvas")
        with Image.open(layer.asset_path) as stored:
            raster = stored.convert("RGBA")
        if raster.size != (right - left, bottom - top):
            raise LayerProposalError("persisted layer dimensions do not match its crop")
        composite.alpha_composite(raster, (left, top))
    return composite
