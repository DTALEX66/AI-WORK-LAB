# SPDX-License-Identifier: MIT
"""Explicit, measurement-honest routing and timing contracts.

This module selects provider *capability* only.  It deliberately does not
claim throughput or downgrade a reference image: performance thresholds become
usable only after the corpus has produced matched measurements.
"""
from __future__ import annotations

from dataclasses import dataclass


_PROFILES = frozenset({"flat", "ui", "mixed", "poster", "photo", "3d"})
_STAGES = frozenset(
    {"intake", "model-load", "inference", "render", "compare", "repair", "host-wait", "host-execution"}
)
_TEMPERATURES = frozenset({"cold", "warm"})


@dataclass(frozen=True)
class HardwareProfile:
    """Declared hardware facts used for deterministic routing."""

    vram_mib: int
    hardware_id: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        if self.vram_mib < 0:
            raise ValueError("vram_mib must not be negative")

    @property
    def vram_mb(self) -> int:
        """Compatibility spelling used by the original task-pack prose."""

        return self.vram_mib


@dataclass(frozen=True)
class RuntimePlan:
    required_providers: tuple[str, ...]
    optional_providers: tuple[str, ...]
    tile_size: int
    resolution_scale: float


@dataclass(frozen=True)
class TimingEvent:
    stage: str
    duration_ms: float
    temperature: str
    profile: str | None = None
    hardware_id: str | None = None

    def as_json(self) -> dict[str, object]:
        validated = validate_event(self)
        return {
            "schemaVersion": "design-lab/reconstruction-timing-event/v1",
            "stage": validated.stage,
            "durationMs": validated.duration_ms,
            "temperature": validated.temperature,
            "profile": validated.profile,
            "hardwareId": validated.hardware_id,
        }


def select_runtime_plan(hardware: HardwareProfile, profile: str) -> RuntimePlan:
    """Select providers without silently changing reference resolution.

    Optional GPU layers are only eligible when the declared VRAM reaches the
    measured routing threshold.  The returned plan still requires registry
    qualification before a provider can actually execute.
    """

    if profile not in _PROFILES:
        raise ValueError(f"unsupported reconstruction profile: {profile}")
    required = ("geometry", "paddleocr", "layerd", "vtracer")
    optional = ("sam2", "birefnet", "starvector-1b") if hardware.vram_mib >= 7500 else ("sam2-cpu",)
    return RuntimePlan(
        required_providers=required,
        optional_providers=optional,
        tile_size=1024 if hardware.vram_mib < 10000 else 2048,
        resolution_scale=1.0,
    )


def validate_event(event: TimingEvent) -> TimingEvent:
    """Accept only observed positive timing events with named lifecycle stages."""

    if event.stage not in _STAGES:
        raise ValueError(f"unsupported timing stage: {event.stage}")
    if event.temperature not in _TEMPERATURES:
        raise ValueError(f"unsupported temperature: {event.temperature}")
    if not isinstance(event.duration_ms, (int, float)) or isinstance(event.duration_ms, bool) or event.duration_ms <= 0:
        raise ValueError("duration_ms must be an observed positive number")
    if event.profile is not None and event.profile not in _PROFILES:
        raise ValueError(f"unsupported reconstruction profile: {event.profile}")
    return event
