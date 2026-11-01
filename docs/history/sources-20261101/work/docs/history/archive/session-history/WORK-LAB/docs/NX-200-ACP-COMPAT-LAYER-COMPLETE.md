# NX-200 — ACP Compatibility Layer

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Add an ACP (Agent Client Protocol) protocol/capability mapping layer on top of
the existing Adapter SDK — without creating a second execution platform.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/acp_adapter.py`**
   - Protocol identity + version negotiation (`init`); unknown protocol version
     degrades fail-closed to the supported base.
   - Capability negotiation (`negotiate`) — unsupported features reported as
     unsupported, never a crash.
   - Read-only ACP operations (`detect`, `capabilities`, `observe`).
   - Mutation operations (`plan`/`apply`/`invoke`/`rollback`) respect the existing
     approval boundary — mutations require explicit approval, fail closed otherwise.
   - Unified capability model maps Hermes/Codex/Cursor/Claude Code/WorkBuddy via
     `internal-bridge` (never claims native ACP); Qwen Code is a `native-acp-pilot`
     that returns `unavailable` when not installed.

2. **`10-workflow/workflow-assistance/scripts/workflow/verify_acp_conformance.py`**
   - Static ACP conformance for all 6 clients + Qwen Code pilot probe.

3. **`10-workflow/workflow-assistance/tests/test_acp_adapter.py`** (9 tests)
   - init supported / unknown-version degrade; unsupported-feature negotiate;
     read-only no-approval; mutation plan/apply approval boundary; Qwen pilot
     unavailable/available; unknown client rejected.

4. **`run_quality_gate.py`** — new `acp-conformance` gate; wired into CI.

5. **`config/capability-conformance.json`** — `acp-compat-layer` entry added
   (capabilities `detect/capabilities/observe/negotiate/init`).

## Verification

```text
ACP_CONFORMANCE_PASS clients=6 ok=5 unavailable=1 protocol=['0.1.0'] degradation=fail-closed
test_acp_adapter: Ran 9 tests OK
QUALITY_GATE_PASS gates=acp-conformance
CAPABILITY_CONFORMANCE_PASS protocols=3 entries=5
```

## Honesty

- No client is claimed to speak native ACP unless it does (`internal-bridge` for
  Hermes/Codex/Cursor/Claude Code/WorkBuddy).
- Qwen Code is a pilot; if the CLI is absent it returns `UNAVAILABLE` and never
  fails the project.
- Mutations remain gated behind explicit approval.

## Rollback

Remove `acp_adapter.py`, `verify_acp_conformance.py`, `test_acp_adapter.py`, the
`acp-conformance` gate + CI step, and the capability-conformance entry. No runtime
dependency.
