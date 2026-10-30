# SPDX-License-Identifier: MIT
"""Bounded selection of untrusted vector reconstruction candidates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .providers.base import FallbackEvent

from .svg_safety import UnsafeSVGError, sanitize_svg


@dataclass(frozen=True)
class LocalMetrics:
    match_ratio: float
    safe: bool


@dataclass(frozen=True)
class VectorCandidate:
    provider_id: str
    object_id: str
    svg_fragment: bytes
    node_count: int
    local_metrics: LocalMetrics
    svg_path: Path | None = None


class VectorProviderUnavailable(RuntimeError):
    """A local candidate provider failed with recoverable evidence for fallback routing."""

    def __init__(self, events: tuple[FallbackEvent, ...]) -> None:
        self.events = events
        super().__init__(events[0].message if events else "vector provider unavailable")


def _is_passing(candidate: VectorCandidate) -> bool:
    metrics = candidate.local_metrics
    if not (
        isinstance(candidate.provider_id, str)
        and candidate.provider_id
        and isinstance(candidate.object_id, str)
        and candidate.object_id
        and isinstance(candidate.node_count, int)
        and not isinstance(candidate.node_count, bool)
        and candidate.node_count > 0
        and isinstance(candidate.svg_fragment, bytes)
        and metrics.safe
        and 0.995 <= metrics.match_ratio <= 1.0
    ):
        return False
    try:
        sanitize_svg(candidate.svg_fragment)
    except (UnsafeSVGError, TypeError, ValueError):
        return False
    return True


def select_candidate(candidates: tuple[VectorCandidate, ...] | list[VectorCandidate]) -> VectorCandidate | None:
    """Return the smallest safe candidate meeting the deterministic local quality floor."""

    passing = [candidate for candidate in candidates if _is_passing(candidate)]
    if not passing:
        return None
    return min(
        passing,
        key=lambda candidate: (
            candidate.node_count,
            len(candidate.svg_fragment),
            candidate.provider_id,
            candidate.object_id,
        ),
    )


def select_candidates_by_object(candidates: tuple[VectorCandidate, ...] | list[VectorCandidate]) -> tuple[VectorCandidate, ...]:
    """Select independently per semantic object while preserving first-observed scene order."""

    grouped: dict[str, list[VectorCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.object_id, []).append(candidate)
    return tuple(
        selected
        for values in grouped.values()
        if (selected := select_candidate(values)) is not None
    )
