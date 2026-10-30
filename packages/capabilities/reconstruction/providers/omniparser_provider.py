# SPDX-License-Identifier: MIT
"""Commercial-disabled OmniParser adapter restricted to UI proposal routing."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .base import FallbackEvent, PreflightResult, ProposalRequest, ProposalResult, ProviderDescriptor, ProviderError
from .paddleocr_provider import _write_fallback
from .registry import RegisteredProvider


class OmniParserProvider:
    """Never executes under the current registry's commercial-use policy."""

    def __init__(self, descriptor: ProviderDescriptor, *, external_roots: Sequence[Path], available_vram_mib: int = 8151) -> None:
        self._registered = RegisteredProvider(descriptor, external_roots=external_roots, available_vram_mib=available_vram_mib)

    def describe(self) -> ProviderDescriptor:
        return self._registered.describe()

    def preflight(
        self, *, task: str, contract: dict[str, Any] | None = None, profile: str | None = None
    ) -> PreflightResult:
        if task != "ui-analysis" or profile != "ui":
            event = FallbackEvent(
                self.describe().provider_id,
                "NO_PROVIDER",
                task,
                "OmniParser is restricted to the ui profile and ui-analysis task",
                True,
            )
            return PreflightResult(self.describe().provider_id, "NO_PROVIDER", False, (event,), None, 0)
        result = self._registered.preflight(task=task, contract=contract)
        if "ui-analysis" not in self.describe().tasks:
            return result
        # The adapter is intentionally quarantined even if a future registry edit
        # accidentally marks its artifact qualified. Commercial enablement needs a
        # separate, explicit policy change and cannot happen as a side effect.
        event = FallbackEvent(
            self.describe().provider_id,
            "LICENSE_DENIED",
            task,
            "OmniParser execution is commercial-disabled by registry policy",
            True,
        )
        return PreflightResult(result.provider_id, "LICENSE_DENIED", False, (event,), result.observed_sha256, result.available_vram_mib)

    def propose(self, request: ProposalRequest) -> ProposalResult:
        descriptor = self.describe()
        if request.provider_id != descriptor.provider_id or request.provider_version != descriptor.provider_version:
            raise ProviderError("request provider identity does not match OmniParser descriptor")
        if request.profile != "ui":
            event = FallbackEvent(descriptor.provider_id, "NO_PROVIDER", request.task, "OmniParser is restricted to the ui profile", True)
            return _write_fallback(request, descriptor, event)
        preflight = self.preflight(task=request.task, profile=request.profile)
        if not preflight.ready:
            return _write_fallback(request, descriptor, preflight.events[0])
        event = FallbackEvent(descriptor.provider_id, "LICENSE_DENIED", request.task, "OmniParser execution is commercial-disabled by registry policy", True)
        return _write_fallback(request, descriptor, event)
