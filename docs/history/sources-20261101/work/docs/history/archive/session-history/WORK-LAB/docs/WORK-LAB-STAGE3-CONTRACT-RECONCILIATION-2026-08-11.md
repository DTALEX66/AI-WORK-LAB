# WORK-LAB Stage 3 Contract Reconciliation — 2026-08-11

**Status:** `LOCAL_IMPLEMENTATION_COMPLETE / PUBLICATION_GATE_PENDING`

## Authority and objective

This cross-module task reconciles the sanitized 2026-08-11 handoff inputs with
the tracked WORK-LAB Stage 3 contracts. The input error ledger defines the
repair scope `ERR-024..ERR-036`; it is evidence and task input, not proof that
the current checkout already contains or passes those fixes.

## Ownership and boundaries

- Writer: the current Codex task; one writer owns this checkout.
- Read-only reviewer: none assigned.
- Cross-module permission: explicit for the root control plane,
  `10-workflow/workflow-assistance`, and the strictly read-only implementation
  surface of `30-observer/work-lab-observer` required by ERR-027/030/036.
- Observer may be changed only to remove writes and consume Workflow-owned
  canonical projections read-only. It must not gain execution, approval,
  retry, apply, rollback, task-state, or Telemetry Ledger authority.
- External inputs under `D:\All projects` are read-only and must not be moved,
  overwritten, deleted, or treated as runtime state.
- Runtime evidence belongs under ignored `.hermes/task-artifacts/` or
  `.hermes/task-runtime/` paths.

## Allowed source paths

- `00-governance/generated/CURRENT_STATE.md`
- `00-governance/generated/CURRENT_STATE.json`
- `scripts/ci/generate_current_state.py`
- `tests/ci/test_current_state.py`
- `.github/workflows/work-lab-gate.yml`
- `10-workflow/workflow-assistance/config/`
- `10-workflow/workflow-assistance/schemas/workflow/`
- `10-workflow/workflow-assistance/scripts/workflow/`
- `10-workflow/workflow-assistance/tests/`
- `10-workflow/workflow-assistance/docs/workflow/`
- `10-workflow/workflow-assistance/README.md`
- `10-workflow/workflow-assistance/.github/workflows/governance.yml`
- `10-workflow/workflow-assistance/workflow-manifest.yaml`
- `10-workflow/workflow-assistance/requirements.txt`
- `30-observer/work-lab-observer/src/`
- `30-observer/work-lab-observer/scripts/`
- `30-observer/work-lab-observer/schemas/`
- `30-observer/work-lab-observer/web/`
- `30-observer/work-lab-observer/tests/`
- `50-taskpacks/error-ledger.json`
- `50-taskpacks/TASKPACK_SUMMARY.md`
- this task pack

Any additional tracked path requires an amendment here before it is edited.

## Repair waves

1. Root/configuration truth: ERR-024, ERR-025, ERR-029, ERR-031, ERR-032,
   ERR-034, ERR-035.
2. Workflow runtime/adapters: ERR-026, ERR-028, ERR-033.
3. Observer read-only/evidence semantics: ERR-027, ERR-030, ERR-036.
4. Reconcile sanitized state, normative documentation, error ledger, task
   summary, and verification evidence.

## Completion contract

- Add or update focused regression tests before or with each behavioral fix.
- Run every regression command recorded for ERR-024..ERR-036 from its owning
  module.
- Run `git diff --check` and the canonical Workflow quality gate:
  `python 10-workflow/workflow-assistance/scripts/workflow/run_quality_gate.py verify`.
- Run applicable root and Observer suites.
- Record failed, skipped, missing, or environment-limited checks honestly.
- Inspect final `git diff --stat` and `git status --short`.

## Approval and recovery boundary

No global Codex/Hermes configuration apply, dependency installation, external
project write, commit, push, PR, merge, release, paid-provider call, or E-drive
access is authorized by this task. Recovery is the exact task-owned diff; no
reset, clean, restore, deletion, or overwrite of unknown work is permitted.

## Local verification result

- `PASS`: canonical Workflow quality gate, 20/20 gates; governance ran 489
  tests with 4 declared skips.
- `PASS`: Observer Python suite, 45/45 tests.
- `PASS`: Observer UI/component suite, 43 + 4 contract tests.
- `PASS`: tracked CURRENT_STATE freshness check and ignored runtime attestation
  generation.
- `PARTIAL`: root CI contract suite ran 72 tests; 71 passed and the
  publication-only exact-tree test correctly rejected this uncommitted dirty
  checkout.
- `NOT EXECUTED`: exact-SHA remote CI, publication, release, live/global apply,
  paid-provider smoke and Tauri packaging.
