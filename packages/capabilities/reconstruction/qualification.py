# SPDX-License-Identifier: MIT
"""Exact-state aggregation for local reconstruction repeatability qualification."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class QualificationRun:
    status: str
    deterministic_preview_sha256: str
    readback_sha256: str
    residue: tuple[str, ...]


@dataclass(frozen=True)
class QualificationReport:
    status: str
    reason: str | None = None


def run_from_record(raw: Mapping[str, Any]) -> QualificationRun:
    """Decode a host-produced run record without turning local tests into host evidence."""

    try:
        status = raw["status"]
        preview = raw["deterministicPreviewSha256"]
        readback = raw["readbackSha256"]
        residue = raw["residue"]
    except KeyError as exc:
        raise ValueError(f"qualification record missing {exc.args[0]}") from None
    if not isinstance(status, str):
        raise ValueError("qualification status must be a string")
    if not isinstance(preview, str) or not _SHA256.fullmatch(preview):
        raise ValueError("deterministicPreviewSha256 must be lowercase SHA-256")
    if not isinstance(readback, str) or not _SHA256.fullmatch(readback):
        raise ValueError("readbackSha256 must be lowercase SHA-256")
    if not isinstance(residue, list) or not all(isinstance(item, str) for item in residue):
        raise ValueError("residue must be a list of strings")
    return QualificationRun(status, preview, readback, tuple(residue))


def aggregate(runs: Sequence[QualificationRun]) -> QualificationReport:
    """Qualify only three clean, hash-identical passes; all weaker evidence remains PARTIAL."""

    if len(runs) != 3:
        return QualificationReport("PARTIAL", "requires exactly three clean passes")
    if any(run.status != "PASS" or run.residue for run in runs):
        return QualificationReport("PARTIAL", "run failed or left residue")
    if len({run.deterministic_preview_sha256 for run in runs}) != 1:
        return QualificationReport("PARTIAL", "preview hashes differ")
    if len({run.readback_sha256 for run in runs}) != 1:
        return QualificationReport("PARTIAL", "read-back hashes differ")
    return QualificationReport("PASS")
