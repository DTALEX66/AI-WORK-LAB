# SPDX-License-Identifier: MIT
"""Rights-cleared reconstruction golden corpus loading and lineage checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


_KINDS = frozenset({"logo", "ui", "poster", "flat-illustration", "complex-illustration", "mixed-media"})


@dataclass(frozen=True)
class GoldenExpectation:
    profile: str
    pixelmatch_min: float
    ssim_min: float
    raster_budget: float
    required_editable_types: tuple[str, ...]
    rights_status: str


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    kind: str
    reference_sha256: str
    actual_reference_sha256: str
    allowed_output_asset_hashes: tuple[str, ...]
    expectation: GoldenExpectation

    @property
    def rights_status(self) -> str:
        return self.expectation.rights_status


@dataclass(frozen=True)
class GoldenCorpus:
    cases: tuple[GoldenCase, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_corpus(path: Path) -> GoldenCorpus:
    """Load only complete, hash-bound, rights-cleared golden inputs."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schemaVersion") != "design-lab/reconstruction-golden-corpus/v1":
        raise ValueError("unsupported golden corpus schema")
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for item in raw.get("cases", []):
        case_id = item.get("caseId")
        kind = item.get("kind")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("golden case IDs must be non-empty and unique")
        if kind not in _KINDS:
            raise ValueError(f"unsupported golden case kind: {kind}")
        seen.add(case_id)
        case_dir = path.parent / "cases" / case_id
        reference = case_dir / "reference.png"
        expectations = json.loads((case_dir / "expectations.json").read_text(encoding="utf-8"))
        rights = expectations.get("rights", {})
        allowed = tuple(expectations.get("allowedOutputAssetHashes", ()))
        declared_sha = item.get("referenceSha256")
        if not isinstance(declared_sha, str) or len(declared_sha) != 64:
            raise ValueError(f"{case_id} needs a frozen reference SHA-256")
        if rights.get("status") != "cleared":
            raise ValueError(f"{case_id} is not rights-cleared")
        cases.append(
            GoldenCase(
                case_id=case_id,
                kind=kind,
                reference_sha256=declared_sha,
                actual_reference_sha256=_sha256(reference),
                allowed_output_asset_hashes=allowed,
                expectation=GoldenExpectation(
                    profile=str(expectations["profile"]),
                    pixelmatch_min=float(expectations["pixelmatchMin"]),
                    ssim_min=float(expectations["ssimMin"]),
                    raster_budget=float(expectations["rasterBudget"]),
                    required_editable_types=tuple(expectations["requiredEditableTypes"]),
                    rights_status=str(rights["status"]),
                ),
            )
        )
    if {case.kind for case in cases} != _KINDS or len(cases) != 6:
        raise ValueError("corpus must contain exactly one case for every required kind")
    return GoldenCorpus(tuple(cases))
