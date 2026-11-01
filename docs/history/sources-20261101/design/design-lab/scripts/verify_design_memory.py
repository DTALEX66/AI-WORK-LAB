#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-D: verify design memory (fail-closed).

1. memory/records.json 每条满足 design-memory schema + core.memory 规则
2. 至少一条 active 与一条 validated（样例基线）
3. 摄入规则拒绝：无证据高置信、重复、非 candidate 输入
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "design-memory.schema.json"
RECORDS = ROOT / "memory" / "records.json"
CORE = ROOT / "core"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    records = json.loads(RECORDS.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) < 3:
        errors.append(f"records must be a list >=3 (got {len(records) if isinstance(records, list) else 'n/a'})")

    import importlib.util
    spec = importlib.util.spec_from_file_location("dl_core_memory", str(CORE / "memory.py"))
    mm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mm
    spec.loader.exec_module(mm)

    for rec in records:
        try:
            jsonschema.validate(rec, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{rec.get('id')}: schema: {exc.message}")
            continue
        errs = mm.validate_record(rec)
        for e in errs:
            errors.append(f"{rec.get('id')}: {e}")
    if not any(r.get("status") == "active" for r in records):
        errors.append("no active memory record")
    if not any(r.get("status") == "validated" for r in records):
        errors.append("no validated memory record")

    # 摄入规则 fail-closed 自检
    good = {"id": "mem_test_1", "schemaVersion": "design-lab/design-memory/v1", "type": "semantic",
            "domain": "test", "title": "x", "statement": "a test rule statement", "confidence": 0.5,
            "created_by": "t", "created_at": "2026-08-16T00:00:00Z", "status": "candidate"}
    st, _ = mm.ingest(good, [], "rule:self-test")
    if st != "validated":
        errors.append(f"valid candidate rejected: {st}")
    bad_high = dict(good, confidence=0.95, evidence=[])
    st2, _ = mm.ingest(bad_high, [], "rule:self-test")
    if st2 != "rejected":
        errors.append("high-confidence no-evidence must be rejected")
    dup = dict(good, id="mem_test_dup")
    st3, _ = mm.ingest(dup, [good], "rule:self-test")
    if st3 != "rejected":
        errors.append("duplicate must be rejected")
    not_candidate = dict(good, status="active")
    st4, _ = mm.ingest(not_candidate, [], "rule:self-test")
    if st4 != "rejected":
        errors.append("non-candidate input must be rejected")

    print(f"DESIGN_MEMORY={'FAIL' if errors else 'PASS'} records={len(records)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
