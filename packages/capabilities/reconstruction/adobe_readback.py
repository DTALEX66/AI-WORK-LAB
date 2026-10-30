# SPDX-License-Identifier: MIT
"""Authorization and exact-state aggregation for Illustrator host read-back evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence


class AuthorizationExpired(ValueError):
    """A host authorization cannot launch the requested job."""


@dataclass(frozen=True)
class HostRun:
    status: str
    svg_sha256: str
    readback_sha256: str
    residue: tuple[str, ...]
    observed_at: str


@dataclass(frozen=True)
class HostQualification:
    state: str
    reason: str | None = None


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise AuthorizationExpired("authorization expiry is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AuthorizationExpired("authorization expiry is invalid") from None
    if parsed.tzinfo is None:
        raise AuthorizationExpired("authorization expiry lacks a timezone")
    return parsed.astimezone(timezone.utc)


def verify_launch_authorization(value: dict[str, Any], job_id: str, *, now: datetime | None = None) -> None:
    """Fail before host launch unless this exact job has an unexpired single-session approval."""

    if not isinstance(value, dict) or value.get("jobId") != job_id or value.get("approved") is not True:
        raise AuthorizationExpired("authorization does not approve this exact job")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _parse_time(value.get("expiresAt")) <= current:
        raise AuthorizationExpired("authorization has expired")


def qualify_host(runs: Sequence[HostRun]) -> HostQualification:
    """Return PASS only for exactly three clean, identical host read-backs."""

    if len(runs) != 3:
        return HostQualification("PARTIAL", "requires exactly three clean runs")
    if any(run.status != "PASS" or run.residue for run in runs):
        return HostQualification("PARTIAL", "host run failed or left residue")
    if len({run.svg_sha256 for run in runs}) != 1 or len({run.readback_sha256 for run in runs}) != 1:
        return HostQualification("PARTIAL", "host output is not reproducible")
    return HostQualification("PASS")
