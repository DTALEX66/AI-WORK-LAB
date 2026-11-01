# Reproducible Dependencies & Test Entrypoints (ODA4-0103)

## Python

- Canonical dependencies: root `pyproject.toml` and `uv.lock`; CI uses `uv sync --locked`.
- `requirements.txt` is a compatibility installation input, not the lockfile.
- Install into the owning project environment, then run its exact Python interpreter.
- Test entrypoint: `python scripts/run_python_tests.py`
  - Discovers all `design-lab/tests/test_*.py` (unittest).
  - Before discovery, resolves `.project/paths.json` / `PROJECT_LOCAL_ROOT`, creates project-local temporary/cache directories, and passes them to child processes. Cached `tempfile` state is overridden during execution and restored afterwards.
  - Empty discovery exits 2; test failures exit 1; passing suites exit 0. Skips remain explicitly reported and are not proof of the skipped capability.
  - Counts and results come from that execution, not a hard-coded historical count in this README.
  - Scoped order/repeat checks: `python design-lab/scripts/run_test_isolation.py --modules test_project_paths --order random --repeat 2`. An unmatched module selection exits 2.
  - Runtime roots stay under `.project-local/`; no global profile or user cache configuration is changed. Native applications' private scratch settings are outside this Python environment guarantee.

## Node (MiniGame runtime)

- MiniGame is a game-visual fixture, not a separate product runtime.
- Test: `npm test` (in `fixtures/domains/game-visual/`) → `node scripts/run-tests.cjs`; read the current run for test counts.
- Verify: `npm run verify` → `node scripts/verify-all.cjs`.
- Drift gate: `node scripts/check-android-drift.mjs` — ensures committed bundles
  match rebuilt output (deterministic). Verified: `npm test` does NOT dirty the
  worktree / regenerate committed bundles post-ODA4-0105.

## Root CI usage (ODA4-0104)

- Python: `uv sync --locked`, then the project environment's `python scripts/run_python_tests.py`.
- Node: from `fixtures/domains/game-visual/`, run `node scripts/run-tests.cjs` and `node scripts/check-android-drift.mjs`.
- Unified verifiers: `python design-lab/scripts/verify_design_lab.py`; do not pass a wildcard as if Python executes every matching script.
- Release attempt: manually dispatch `.github/workflows/release-gate.yml`; it is
  fail-closed and requires the release gate plus a validated
  `design-lab/config/release-evidence.json`.
