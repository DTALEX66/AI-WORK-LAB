# NX-300 — OpenTelemetry / OpenInference Mapping

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Map WORK-LAB canonical events to versioned OTel/OpenInference semantic fields
and back losslessly (for allowed fields), while permanently excluding message
bodies, secrets, full paths, and session content. Local event contract only —
no Collector/Langfuse/Phoenix/OpenLIT install.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/otel_mapper.py`**
   - `canonical_to_otel` / `otel_to_canonical` / `roundtrip_lossless`.
   - Records OTel (`1.27.0`) + OpenInference (`0.1.0`) version snapshot.
   - Allowed fields: operation, provider, model, tokens, cache, latency,
     outcome, error class, task/source digest, low-cardinality labels.
   - Privacy negative control: `gen_ai.input.messages`, `gen_ai.output.messages`,
     prompt/response bodies, tool args/result, api_key, secrets — raise
     `PrivacyBlockedError`, never exported.
   - Unknown fields preserved in isolated `_extensions` zone (does not break
     older projections).
   - Token-metric fields (`inputTokens`/`outputTokens`/`cacheReadTokens`) are NOT
     blocked (word-boundary matching avoids false positives).

2. **`scripts/workflow/verify_otel_mapping.py`** — roundtrip + privacy negative probe.

3. **`tests/test_otel_mapping.py`** (8 tests) — lossless roundtrip, model/token
   mapping, message/prompt/secret blocking, unknown-field extension, otel→canonical.

4. **`run_quality_gate.py`** — `otel-mapping` gate; wired into CI.

## Verification

```text
OTEL_MAPPING_PASS lossless=true privacy_blocked=ok otel=1.27.0 openinference=0.1.0
test_otel_mapping: Ran 8 tests OK
QUALITY_GATE_PASS gates=otel-mapping
```

## Honesty

- No message body, secret, full path, or session content ever enters the mapped
  output (privacy negative control).
- Unknown fields are preserved, not dropped, and do not break older projections.

## Rollback

Remove `otel_mapper.py`, `verify_otel_mapping.py`, `test_otel_mapping.py`, the
`otel-mapping` gate + CI step. No runtime dependency.
