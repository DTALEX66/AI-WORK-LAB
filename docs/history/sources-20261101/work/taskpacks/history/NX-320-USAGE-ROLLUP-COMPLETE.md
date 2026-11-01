# NX-320 — Usage Rollup / Retention / Freshness Semantics

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Idempotent, rebuildable usage rollup with honest cost semantics:
subscriptions are not-metered (never fabricated USD), stale pricing auto-downgrades
to `stale`/`unknown`, and raw sensitive bodies never enter the retention chain.

## Deliverables

1. **`30-observer/work-lab-observer/scripts/usage_rollup.py`**
   - `rollup()`: idempotent aggregate (dedup by fingerprint), rebuildable from events.
   - Tokens / cache / reasoning / tool / outcome kept separate.
   - Subscription model → `not-metered`, no USD.
   - Stale pricing → `costStatus=stale`, no current USD (freshness downgrade).
   - `price_status_for()` exposes source / coverage / freshness / effective_at.
   - Privacy: raw bodies never in retention.

2. **`verify_usage_rollup.py`** — idempotency + pricing-freshness + privacy probe.

3. **`tests/test_usage_rollup.py`** (10 tests) — idempotent, dedup, rebuildable,
   subscription no-USD, stale downgrade, fresh estimated, tokens separate,
   price status, unknown model, privacy.

4. **CI** observer job runs the verifier + tests.

## Verification

```text
USAGE_ROLLUP_PASS models=3 idempotent=true rebuildable=true subscription=not-metered stale=downgraded privacy=no-bodies
test_usage_rollup: Ran 10 tests OK
```

## Honesty

- Same fixture re-ingested → identical aggregate (idempotent).
- Subscription / stale cost never fabricated as current USD.
- Aggregates are rebuildable from events, never stored-as-fact.

## Rollback

Remove `usage_rollup.py`, `verify_usage_rollup.py`, `test_usage_rollup.py`, and
the two CI steps. No runtime dependency.
