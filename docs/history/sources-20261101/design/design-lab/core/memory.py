#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-D: Design Memory ingestion rules.

写入必须经过：candidate -> dedup -> evidence/confidence -> validation -> active。
防止把模型幻觉沉淀为知识（fail-closed）。
"""
from __future__ import annotations

from datetime import datetime, timezone

VALID_TYPES = {"semantic", "procedural", "episodic", "visual", "failure_pattern"}
VALID_STATUS = {"candidate", "validated", "active", "rejected", "expired"}


def validate_record(rec: dict) -> list[str]:
    errs: list[str] = []
    if not rec.get("id"):
        errs.append("id required")
    if rec.get("schemaVersion") != "design-lab/design-memory/v1":
        errs.append("schemaVersion must be design-lab/design-memory/v1")
    if rec.get("type") not in VALID_TYPES:
        errs.append(f"invalid type: {rec.get('type')}")
    if rec.get("status") not in VALID_STATUS:
        errs.append(f"invalid status: {rec.get('status')}")
    if not rec.get("statement") or len(rec["statement"]) < 10:
        errs.append("statement required (>=10 chars)")
    conf = rec.get("confidence")
    if conf is None or not (0 <= conf <= 1):
        errs.append("confidence must be 0..1")
    if rec.get("status") in ("validated", "active") and not rec.get("validated_by"):
        errs.append(f"status {rec.get('status')} requires validated_by (human or rule)")
    # 幻觉防护：high-confidence 必须带 evidence
    if conf is not None and conf >= 0.9 and not rec.get("evidence"):
        errs.append("confidence>=0.9 requires evidence (anti-hallucination gate)")
    return errs


def dedup_key(rec: dict) -> str:
    """去重键：type + domain + statement 规范化。"""
    stmt = " ".join(str(rec.get("statement", "")).lower().split())
    return f"{rec.get('type')}|{rec.get('domain', '')}|{stmt}"


def ingest(candidate: dict, existing: list[dict], validator: str = "rule:kernel") -> tuple[str, str]:
    """返回 (status, message)。不满足门槛的候选拒绝（fail-closed）。"""
    errs = validate_record(candidate)
    if errs:
        return "rejected", "; ".join(errs)
    key = dedup_key(candidate)
    for rec in existing:
        if dedup_key(rec) == key:
            return "rejected", f"duplicate of {rec.get('id')}"
    if candidate.get("status") != "candidate":
        return "rejected", "ingest input must be status=candidate"
    rec = dict(candidate)
    rec["status"] = "validated"
    rec["validated_by"] = validator
    rec.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    return "validated", "accepted"
