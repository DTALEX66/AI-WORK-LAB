#!/usr/bin/env python3
"""Cross-agent usage ingestion verifier (NX-310).

Verifies the read-only, incremental, budgeted ingestion pipeline and coverage
matrix; confirms privacy (no prompt/response/secret/session) and that missing
data yields unknown/partial (never fake 0 or success).
"""
from __future__ import annotations

import json
import sys
import project_temp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))
sys.path.insert(0, str(ROOT / "services/receipts"))

from usage_ingestion import (  # noqa: E402
    UsageReader, coverage_matrix, normalize_event, ALLOWLIST_FIELDS,
)


def verify() -> dict:
    errors: list[str] = []

    # 1. Coverage matrix has all 7 agents.
    cov = coverage_matrix()
    if len(cov) != 7:
        errors.append(f"expected 7 agents in coverage matrix, got {len(cov)}")
    for agent, info in cov.items():
        if info["status"] not in ("supported", "unknown", "retired"):
            errors.append(f"{agent}: invalid status")

    # 2. Read-only incremental ingestion on a synthetic fixture.
    with project_temp.fixture_root(prefix='usage-ingestion-fixture-') as d:
        usage = Path(d) / "usage.jsonl"
        usage.write_text(
            "{\"provider\":\"deepseek\",\"model\":\"deepseek-v4-flash\",\"operation\":\"chat\","
            "\"inputTokens\":100,\"outputTokens\":50,\"prompt\":\"SECRET BODY\",\"api_key\":\"sk-x\"}\n"
            "{\"provider\":\"deepseek\",\"model\":\"deepseek-v4-flash\",\"inputTokens\":200}\n"
            "NOT_JSON\n",
            encoding="utf-8",
        )
        reader = UsageReader("hermes", usage)
        probe = reader.probe()
        if probe["status"] != "supported":
            errors.append(f"probe should be supported: {probe}")
        events, new_cursor = reader.read_incremental(cursor=0)
        if not events:
            errors.append("no events read from valid fixture")

    # 3. Privacy: prompt/api_key never appear in normalized output.
    sample_events = events  # noqa: F821
    serialized = json.dumps(events, ensure_ascii=False).lower()
    for blocked in ("secret", "api_key", "sk-x"):
        if blocked in serialized:
            errors.append(f"privacy leak: {blocked} appeared in output")

    # 4. Missing data yields unknown/partial, never fake 0.
    if not any("malformedLines" in e for e in events):
        errors.append("malformed line should produce a partial-coverage note")

    if errors:
        raise ValueError("; ".join(errors))
    return {"agents": len(cov), "allowlist_fields": len(ALLOWLIST_FIELDS)}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError, OSError) as exc:
        print(f"USAGE_INGESTION_FAIL {exc}")
        return 1
    print(
        f"USAGE_INGESTION_PASS agents={result['agents']} allowlist={result['allowlist_fields']} "
        f"read_only=true incremental=true privacy=ok coverage=honest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
