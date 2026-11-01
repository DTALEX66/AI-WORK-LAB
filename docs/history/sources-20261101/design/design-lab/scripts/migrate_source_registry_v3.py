#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-KNW-003: migrate legacy source registry (v2 draft) to SourceRecord v3.

One-time, deterministic migration. For every legacy entry:
- maps mechanically derivable facts (sourceId <- id, origin <- url);
- computes the SourceRecord required fields that are MISSING;
- quarantines every entry that lacks any required fact (fail-closed: no
  fabricated author/allowedUsage/contentHash/rights/reviewer);
- preserves the legacy record verbatim under `originalRecord`.

Outputs:
- design-lab/research/global-absorption/SOURCE_REGISTRY.json        (v3, active+reference-only; starts empty until human review)
- design-lab/research/global-absorption/QUARANTINE_REGISTRY.json    (v1, all quarantined entries with missingFields+reason)
- reports/current/DL-KNW-003-SOURCE-MIGRATION.json                  (counts + per-entry mapping)

Run once; idempotent (refuses to re-migrate an already-v3 registry).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "research" / "global-absorption" / "SOURCE_REGISTRY.json"
QUARANTINE = ROOT / "research" / "global-absorption" / "QUARANTINE_REGISTRY.json"
REPORT = ROOT.parent / "reports" / "current" / "DL-KNW-003-SOURCE-MIGRATION.json"

GIT_SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256_PREFIX = re.compile(r"^sha256:[0-9a-f]{64}$")
NOT_LICENSE = {"UNVERIFIED", "REFERENCE-ONLY", ""}


def is_git_source(entry: dict) -> bool:
    return str(entry.get("contentHash") or "").startswith("git:") or "github.com" in str(entry.get("url") or "")


def missing_fields(entry: dict) -> list[str]:
    missing: list[str] = []
    if not entry.get("id"):
        missing.append("sourceId")
    if not entry.get("url"):
        missing.append("origin")
    if not entry.get("author"):
        missing.append("author")
    if entry.get("license") in NOT_LICENSE:
        missing.append("license")
    if not entry.get("licenseStatus"):
        missing.append("licenseStatus")
    if not entry.get("allowedUsage"):
        missing.append("allowedUsage")
    version = entry.get("version")
    if not version:
        missing.append("version")
    elif is_git_source(entry) and not GIT_SHA40.match(str(version)):
        missing.append("version(40-hex-git-sha)")
    if not entry.get("acquiredAt"):
        missing.append("acquiredAt")
    content_hash = entry.get("contentHash")
    if not content_hash or not SHA256_PREFIX.match(str(content_hash)):
        missing.append("contentHash(sha256)")
    for f in ("redistributable", "modelInputAllowed", "commercialUse"):
        if not isinstance(entry.get(f), bool):
            missing.append(f)
    if not entry.get("reviewedBy"):
        missing.append("reviewedBy")
    if not entry.get("reviewedAt"):
        missing.append("reviewedAt")
    return missing


def reason_for(entry: dict) -> str:
    parts: list[str] = []
    if entry.get("license") in NOT_LICENSE:
        parts.append("license is marker-only/UNVERIFIED, not a real license")
    if is_git_source(entry) and entry.get("version") and not GIT_SHA40.match(str(entry.get("version"))):
        parts.append("git version is not a full 40-char commit SHA")
    if not entry.get("reviewedBy"):
        parts.append("no human reviewer recorded")
    if str(entry.get("contentHash") or "").startswith(("git:", "doc-pin:")):
        parts.append("contentHash is a pin/reference, not sha256:<64hex> of the acquired content")
    base = "legacy registry drafted without full SourceRecord facts; human review required before promotion"
    return "; ".join(parts + [base])


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schemaVersion") == "design-lab/source-registry/v3":
        print("MIGRATE_SOURCE_REGISTRY=ALREADY_V3 (no-op)")
        return 0

    entries = data.get("entries", [])
    quarantine_entries: list[dict] = []
    mapping: list[dict] = []

    for e in entries:
        missing = missing_fields(e)
        reason = reason_for(e)
        qe = {
            "sourceId": e.get("id"),
            "name": e.get("name"),
            "origin": e.get("url"),
            "license": None if e.get("license") in NOT_LICENSE else e.get("license"),
            "licenseStatus": e.get("licenseStatus"),
            "version": e.get("version"),
            "contentHashOriginal": e.get("contentHash"),
            "missingFields": missing,
            "reason": reason,
            "quarantinedAt": today,
            "originalRecord": e,
        }
        quarantine_entries.append(qe)
        mapping.append({
            "legacyId": e.get("id"),
            "destination": "QUARANTINE",
            "missingFields": missing,
            "reason": reason,
        })

    counts = {
        "total": len(entries),
        "ACTIVE": 0,
        "REFERENCE_ONLY": 0,
        "QUARANTINE": len(quarantine_entries),
        "missingLicense": sum(1 for e in entries if e.get("license") in NOT_LICENSE),
        "missingReviewer": sum(1 for e in entries if not e.get("reviewedBy")),
        "missingFullVersion": sum(
            1 for e in entries
            if is_git_source(e) and (not e.get("version") or not GIT_SHA40.match(str(e.get("version"))))
        ),
        "missingSha256": sum(
            1 for e in entries
            if not e.get("contentHash") or not SHA256_PREFIX.match(str(e.get("contentHash")))
        ),
        "modelInputAllowed": 0,
        "commercialUse": 0,
    }

    v3 = {
        "$schema": "../../schemas/source-registry.schema.json",
        "schemaVersion": "design-lab/source-registry/v3",
        "generated_at": today,
        "policy": (
            "Only complete, human-reviewed SourceRecords may enter this registry. "
            "Entries lacking any required fact live in QUARANTINE_REGISTRY.json and "
            "must not enter capability loading, model context, or reviewed status. "
            "Migrated from legacy v2 draft on " + today + " (DL-KNW-003)."
        ),
        "entries": [],
    }
    qv1 = {
        "$schema": "../../schemas/quarantine-registry.schema.json",
        "schemaVersion": "design-lab/quarantine-registry/v1",
        "generated_at": today,
        "policy": (
            "Quarantine is not deletion. Each entry preserves its legacy record "
            "verbatim under originalRecord and records missingFields + reason. "
            "Promotion to SOURCE_REGISTRY (ACTIVE/REFERENCE_ONLY) requires a human "
            "to complete every missing fact (DL-KNW-003)."
        ),
        "entries": quarantine_entries,
    }
    report = {
        "report": "DL-KNW-003-SOURCE-MIGRATION",
        "generated_at": today,
        "policy": "逐条迁移，不批量制造字段；缺少任一事实 → quarantine registry",
        "counts": counts,
        "entries": mapping,
    }

    REGISTRY.write_text(json.dumps(v3, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    QUARANTINE.write_text(json.dumps(qv1, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"MIGRATE_SOURCE_REGISTRY=OK total={counts['total']} active={counts['ACTIVE']} "
          f"reference_only={counts['REFERENCE_ONLY']} quarantine={counts['QUARANTINE']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
