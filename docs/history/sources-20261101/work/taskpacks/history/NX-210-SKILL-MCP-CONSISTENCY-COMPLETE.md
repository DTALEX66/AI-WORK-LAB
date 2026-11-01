# NX-210 — Agent Skills Structure + MCP Consistency

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Verify all 13 repo-managed skills pass the official Agent Skills base-structure
check, keep security/source/scope fields in the WORK-LAB extension namespace,
and validate MCP candidates by protocol/capabilities/transport/permission —
never trusting a successful connection as security trust. Add malicious
Skill/MCP fixtures for prompt injection, tool poisoning, hidden shell, secret
reference, out-of-bounds path, oversized context, and recursive loading.

## Deliverables

1. **`scripts/ci/verify_skill_mcp_consistency.py`**
   - Verifies every repo-managed `SKILL.md` has `name`/`description`/`version`
     + `metadata.hermes` (WORK-LAB extension namespace).
   - Malicious-fixture detector (7 categories), fail-closed with reason.
   - MCP consistency: `capability-conformance.json` mcp status enum + execute
     permission cannot auto-trust.
   - Guardrail-aware: security-prohibition sentences are not false-flagged.

2. **`tests/ci/test_skill_mcp_consistency.py`** (8 tests)
   - All 13 skills pass; 4 malicious patterns detected; benign guardrail not
     flagged; missing required field fails; fixture count = 7.

3. **CI** integration job runs the verifier + tests.

## Verification

```text
SKILL_MCP_CONSISTENCY_PASS skills=13 malicious_fixtures=7 all_validated=true
test_skill_mcp_consistency: Ran 8 tests OK
```

## Honesty

- A skill must be complete AND safe; a missing required field fails.
- Malicious patterns are surfaced with a reason; unknown extensions are kept but
  never auto-granted permissions.
- Guardrail text (e.g. "禁止读取凭证") is not falsely flagged as malicious.

## Rollback

Remove the verifier, test, and the two CI steps. No runtime dependency.
