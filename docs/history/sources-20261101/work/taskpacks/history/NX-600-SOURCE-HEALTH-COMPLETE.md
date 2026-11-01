# NX-600 — Offline Source Health, Vulnerability & Upstream Monitoring

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Provide deterministic, read-only supply-chain monitoring. OSV-style advisories
are consumed offline, OpenSSF Scorecard is only a health signal, and upstream
changes that affect trust or compatibility block automatic updates while
preserving the last approved version for rollback.

## Deliverables

1. **`scripts/ci/source_health_monitor.py`**
   - offline OSV-style scan with `OFFLINE_READ_ONLY` and no auto-fix;
   - Scorecard signal with `SIGNAL_ONLY` decision role;
   - upstream comparison for license changes, postinstall addition, API
     removal, repository archival, and package ownership takeover;
   - `UPSTREAM_CHANGED` + `BLOCK_UPDATE` on any trust/compatibility change;
   - `DISCOVERED`/`QUARANTINED` candidate registration with installation and
     auto-enable forbidden;
   - rollback evidence retained as approved commit/version/reference.

2. **`scripts/ci/verify_source_health.py`** — verifies all five upstream change
   controls, quarantine behavior, offline OSV semantics, Scorecard signal use,
   and rollback preservation.

3. **`tests/ci/test_source_health.py`** — 7 tests covering unchanged sources,
   all change classes, quarantine, OSV no-fix, Scorecard signaling, and
   fail-closed source mismatch.

4. **Integration CI** — verifier and test run in the root integration job.

## Verification

```text
SOURCE_HEALTH_PASS upstream_change_controls=5 quarantined_candidates=1 osv=offline_read_only scorecard=signal_only rollback=preserved
Ran 7 tests in 0.001s — OK
```

## Honesty and boundaries

- No network access, installation, vendoring, automatic upgrade, or automatic
  `fix` is performed.
- A Scorecard value cannot alone authorize absorption.
- Observer-facing status remains informational; no install/upgrade control is
  introduced.

## Rollback

Remove the monitor, verifier, test, CI steps, this handoff, and ledger entry.
Existing approved source/version evidence remains in Git history.
