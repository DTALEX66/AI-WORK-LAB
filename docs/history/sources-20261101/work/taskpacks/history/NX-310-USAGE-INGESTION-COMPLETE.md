# NX-310 — Cross-Agent Usage Ingestion Adapter Pack

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Read-only, incremental, budgeted ingestion of agent-local public usage data,
normalized into versioned observer events. Never reads Prompt/Response bodies,
credentials, or token-refresh code.

## Data flow

```text
Agent local usage -> read-only probe + incremental cursor
-> workflow producer (clean/dedup/sanitize/normalize)
-> versioned event -> Observer store/projection/UI (strictly read-only)
```

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/usage_ingestion.py`**
   - `UsageReader`: read-only incremental reader with size-budget (5MB), line
     budget (100k), symlink-boundary check, malformed-line isolation.
   - Field allowlist (15 fields): provider/model/operation/tokens/cache/latency/
     outcome/error/task·source digest/run·task·project ids.
   - Privacy: prompt/response/message/session/secret/api-key/token-refresh are
     never read into output (`_sanitize_record` drops blocked keys).
   - Coverage matrix (7 agents): Hermes/Codex/Claude/Kimi `supported`;
     Cursor/WorkBuddy/Qwen `unknown` (no official public source → never fake).
   - `normalize_event` → versioned observer event with privacy flags.

2. **`verify_usage_ingestion.py`** — read-only/incremental/privacy/coverage probe.

3. **`tests/test_usage_ingestion.py`** (10 tests) — valid/malformed, privacy,
   incremental cursor, coverage matrix, unknown/unsupported agent, subagent/dup.

4. **`run_quality_gate.py`** — `usage-ingestion` gate; wired into CI.

## Verification

```text
USAGE_INGESTION_PASS agents=7 allowlist=15 read_only=true incremental=true privacy=ok coverage=honest
test_usage_ingestion: Ran 10 tests OK
QUALITY_GATE_PASS gates=usage-ingestion
```

## Honesty

- Missing/unknown coverage is reported as `unknown/partial`, never fake 0/success.
- Cursor/WorkBuddy/Qwen with no official source are `unsupported/unknown`, not claimed.

## Rollback

Remove `usage_ingestion.py`, `verify_usage_ingestion.py`, `test_usage_ingestion.py`,
the `usage-ingestion` gate + CI step. No runtime dependency.
