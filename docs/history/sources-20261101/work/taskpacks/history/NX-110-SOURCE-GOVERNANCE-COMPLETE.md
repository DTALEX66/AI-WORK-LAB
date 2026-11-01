# NX-110 — Source Governance Gate (License / NOTICE / Size)

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Enforce that every copied/referenced source is traceable, permissibly licensed,
with complete NOTICE attribution, and that no node_modules / build cache /
downloaded binary / vendored upstream repository enters Git.

## Deliverables

1. **`scripts/ci/verify_source_governance.py`**
   - Rejects tracked `node_modules/`, `__pycache__`/bytecode, `dist/`/`build/`,
     `.exe/.dll/.bin/.wasm/.jar`, nested `.git/`, and `vendor/` upstream repos.
   - Requires `NOTICE.md` present and non-empty.
   - For every cross-module source index entry: requires a `license` declaration
     and an explicit `licenseVerified` flag (honest `UNKNOWN` allowed, never invented).
   - An *implemented* entry must have `licenseVerified=true` and a permissive
     license (not proprietary / non-commercial / unknown).

2. **`tests/ci/test_source_governance.py`** (6 tests)
   - Real repo passes; implemented-without-license-verified fails;
     non-permissive license fails; forbidden artifacts matched; clean paths not
     flagged; NOTICE missing fails.

3. **CI** integration job now runs the source governance verifier + tests.

## Baseline

- Tracked forbidden artifacts in repo: **0** (node_modules=0, pyc=0, binary=0, vendor=0, dist/build=0).
- `NOTICE.md`: present and non-empty.
- Cross-module index: 33 entries, all license-verified or explicit.

## Verification

```text
SOURCE_GOVERNANCE_PASS tracked=328 forbidden=0 notice=ok entries=33 license=honest
tests/ci/test_source_governance.py: Ran 6 tests OK
```

## Rollback

Remove the verifier, test, and the two CI steps. No runtime dependency.
