# SPDX-License-Identifier: MIT
"""Fail-closed local StarVector boundary; no remote inference or implicit model download."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from reconstruction.vector_candidates import VectorCandidate, VectorProviderUnavailable

from .base import FallbackEvent, ProviderDescriptor
from .registry import RegisteredProvider


class StarVectorProvider:
    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        external_roots: Sequence[Path],
        available_vram_mib: int = 8151,
        runner: Callable[[Any], Sequence[VectorCandidate]] | None = None,
    ) -> None:
        self._registered = RegisteredProvider(
            descriptor,
            external_roots=external_roots,
            available_vram_mib=available_vram_mib,
        )
        self._runner = runner

    def propose_candidates(self, request: Any) -> Sequence[VectorCandidate]:
        result = self._registered.preflight(task="vector-candidate")
        if not result.ready:
            raise VectorProviderUnavailable(result.events)
        if self._runner is None:
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "MISSING", "vector-candidate",
                "qualified StarVector runtime is not installed", True,
            ),))
        try:
            return tuple(self._runner(request))
        except MemoryError:
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "OOM", "vector-candidate",
                "local StarVector runtime exhausted its authorized memory", True,
            ),)) from None
