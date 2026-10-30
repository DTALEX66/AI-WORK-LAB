# SPDX-License-Identifier: MIT
"""Profile-gated local SAM 2 plus BiRefNet foreground-matting adapter."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from reconstruction.matting import LayerProposal, LayerProviderUnavailable

from .base import FallbackEvent, ProviderDescriptor
from .registry import RegisteredProvider


_SUPPORTED_PROFILES = frozenset({"mixed", "poster", "photo", "3d"})


class SamBiRefNetProvider:
    """Use a locally qualified SAM 2 prompt stage followed by local alpha matting."""

    def __init__(
        self,
        sam_descriptor: ProviderDescriptor,
        birefnet_descriptor: ProviderDescriptor,
        *,
        external_roots: Sequence[Path],
        available_vram_mib: int = 8151,
        runner: Callable[[Any], Sequence[LayerProposal]] | None = None,
    ) -> None:
        self._sam = RegisteredProvider(
            sam_descriptor,
            external_roots=external_roots,
            available_vram_mib=available_vram_mib,
        )
        self._birefnet = RegisteredProvider(
            birefnet_descriptor,
            external_roots=external_roots,
            available_vram_mib=available_vram_mib,
        )
        self._runner = runner

    def supports_profile(self, profile: Any) -> bool:
        return profile in _SUPPORTED_PROFILES

    def priority_for_profile(self, _profile: Any) -> int:
        return 20

    def propose_layers(self, request: Any) -> Sequence[LayerProposal]:
        profile = getattr(request, "profile", None)
        if profile not in _SUPPORTED_PROFILES:
            raise LayerProviderUnavailable((FallbackEvent(
                self._sam.describe().provider_id,
                "NO_PROVIDER",
                "foreground-matting",
                "SAM 2 plus BiRefNet is reserved for mixed foreground matte profiles",
                True,
            ),))
        sam = self._sam.preflight(task="layer-decomposition")
        if not sam.ready:
            raise LayerProviderUnavailable(sam.events)
        matte = self._birefnet.preflight(task="foreground-matting")
        if not matte.ready:
            raise LayerProviderUnavailable(matte.events)
        if self._runner is None:
            raise LayerProviderUnavailable((FallbackEvent(
                self._birefnet.describe().provider_id,
                "MISSING",
                "foreground-matting",
                "local SAM 2 plus BiRefNet runtime is not installed",
                True,
            ),))
        try:
            return tuple(self._runner(request))
        except MemoryError:
            raise LayerProviderUnavailable((FallbackEvent(
                self._birefnet.describe().provider_id,
                "OOM",
                "foreground-matting",
                "local SAM 2 plus BiRefNet runtime exhausted its authorized memory",
                True,
            ),)) from None
