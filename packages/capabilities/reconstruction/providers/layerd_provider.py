# SPDX-License-Identifier: MIT
"""Fail-closed local LayerD adapter for transparent reconstruction proposals."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from reconstruction.matting import LayerProposal, LayerProviderUnavailable

from .base import FallbackEvent, ProviderDescriptor
from .registry import RegisteredProvider


class LayerDProvider:
    """LayerD boundary which requires both qualified local weights and an injected local runner."""

    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        external_roots: Sequence[Path],
        available_vram_mib: int = 8151,
        runner: Callable[[Any], Sequence[LayerProposal]] | None = None,
    ) -> None:
        self._registered = RegisteredProvider(
            descriptor,
            external_roots=external_roots,
            available_vram_mib=available_vram_mib,
        )
        self._runner = runner

    def describe(self) -> ProviderDescriptor:
        return self._registered.describe()

    def supports_profile(self, profile: Any) -> bool:
        return profile in {"flat", "ui", "mixed"}

    def priority_for_profile(self, _profile: Any) -> int:
        return 10

    def preflight(self):
        return self._registered.preflight(task="layer-decomposition")

    def propose_layers(self, request: Any) -> Sequence[LayerProposal]:
        result = self.preflight()
        if not result.ready:
            raise LayerProviderUnavailable(result.events)
        if self._runner is None:
            raise LayerProviderUnavailable((FallbackEvent(
                self.describe().provider_id,
                "MISSING",
                "layer-decomposition",
                "local LayerD runtime is not installed",
                True,
            ),))
        try:
            return tuple(self._runner(request))
        except MemoryError:
            raise LayerProviderUnavailable((FallbackEvent(
                self.describe().provider_id,
                "OOM",
                "layer-decomposition",
                "local LayerD runtime exhausted its authorized memory",
                True,
            ),)) from None
