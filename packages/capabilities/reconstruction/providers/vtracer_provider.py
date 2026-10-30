# SPDX-License-Identifier: MIT
"""Fail-closed local VTracer boundary; execution is injected after binary qualification."""
from __future__ import annotations

from collections.abc import Callable, Sequence
import re
import subprocess
from pathlib import Path
from typing import Any

from reconstruction.svg_safety import UnsafeSVGError, sanitize_svg
from reconstruction.vector_candidates import LocalMetrics, VectorCandidate, VectorProviderUnavailable

from .base import FallbackEvent, ProviderDescriptor
from .registry import RegisteredProvider


class VTracerProvider:
    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        external_roots: Sequence[Path],
        runner: Callable[[Any], Sequence[VectorCandidate]] | None = None,
        subprocess_run: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._registered = RegisteredProvider(descriptor, external_roots=external_roots)
        self._runner = runner
        self._subprocess_run = subprocess_run

    def propose_candidates(self, request: Any) -> Sequence[VectorCandidate]:
        result = self._registered.preflight(task="vector-candidate")
        if not result.ready:
            raise VectorProviderUnavailable(result.events)
        if self._runner is None:
            return self._run_binary(request)
        return tuple(self._runner(request))

    def _run_binary(self, request: Any) -> Sequence[VectorCandidate]:
        try:
            run_root = Path(request.run_root).resolve(strict=False)
            source = Path(request.source_path).resolve(strict=True)
            object_id = str(getattr(request, "object_id", "scene"))
        except (AttributeError, OSError, RuntimeError) as exc:
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "PROVIDER_DEGRADED", "vector-candidate",
                "VTracer request has no stable local source binding", True,
            ),)) from exc
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", object_id):
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "PATH_DENIED", "vector-candidate",
                "VTracer object id cannot form a run-local output name", True,
            ),))
        output = (run_root / "vector-candidates" / f"{object_id}.vtracer.svg").resolve(strict=False)
        try:
            output.relative_to(run_root)
        except ValueError:
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "PATH_DENIED", "vector-candidate",
                "VTracer output escaped the declared run root", True,
            ),)) from None
        if output.exists() or output.is_symlink():
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "PATH_DENIED", "vector-candidate",
                "VTracer output target is already occupied", True,
            ),))
        output.parent.mkdir(parents=True, exist_ok=True)
        binary = self._registered.describe().local_path
        assert binary is not None
        arguments = [str(binary), "--input", str(source), "--output", str(output)]
        try:
            completed = self._subprocess_run(
                arguments,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if completed.returncode != 0 or not output.is_file() or output.is_symlink():
                raise RuntimeError("VTracer did not produce one regular SVG output")
            payload = output.read_bytes()
            sanitize_svg(payload)
        except (OSError, RuntimeError, UnsafeSVGError, subprocess.TimeoutExpired):
            try:
                if output.is_file() and not output.is_symlink():
                    output.unlink()
            except OSError:
                pass
            raise VectorProviderUnavailable((FallbackEvent(
                self._registered.describe().provider_id, "PROVIDER_DEGRADED", "vector-candidate",
                "local VTracer execution or SVG validation failed", True,
            ),)) from None
        return (VectorCandidate(
            self._registered.describe().provider_id,
            object_id,
            payload,
            1,
            LocalMetrics(0.0, True),
            output,
        ),)
