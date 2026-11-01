# PR #123 Final Audit — WL-000

**Date**: 2026-09-13 14:14 UTC
**PR**: #123 `migration/wl-directory-convergence-r1`
**Base**: `e5231f0` (main)
**Head**: `c6b7e8f` (PR head)
**Current HEAD**: `d893072` (recovery branch, 23 commits ahead of PR)

---

## Executive Summary

**VERDICT: DO NOT MERGE** — Runtime boundary migration incomplete. PR migrates directory structure cleanly (1087 files, zero old-path references) but **fails to migrate the runtime boundary** from `.hermes/` to `.project-local/`. Three core components still enforce `.hermes/` as the runtime root, creating a dual-runtime-root violation that blocks WL-P0-003 Zero-Spill Gate.

---

## Findings Summary

| Check | Status | Critical |
|-------|--------|----------|
| Directory structure migration | ✅ PASS | — |
| Old directory references removed | ✅ PASS | — |
| Runtime boundary migrated | ❌ FAIL | **YES** |
| Hermes guard migrated | ❌ FAIL | **YES** |
| Evidence paths migrated | ❌ FAIL | — |
| AGENTS.md vs implementation alignment | ❌ FAIL | — |
| CI paths | ⚠️ PARTIAL | — |
| .gitignore | ✅ PASS | — |
| Old directory cleanup | ✅ PASS | — |

---

## Critical Blockers (Must Fix Before Merge)

### 1. Runtime Boundary Not Migrated (CRITICAL)

Three core components still enforce `.hermes/` as runtime root:

| Component | Current Behavior | Required |
|-----------|------------------|----------|
| `run_quality_gate.py` | `project_runtime_environment()` creates `.hermes/task-runtime/{tmp,cache,logs,artifacts,pip-cache,pycache}`; sets `HERMES_PROJECT_RUNTIME_ROOT=.hermes/task-runtime` | Use `.project-local/runs/` |
| `scripts/ci/generate_current_state.py` | `DEFAULT_CI_EVIDENCE = .hermes/task-artifacts/...`; validator enforces `.hermes/task-artifacts` | Use `.project-local/artifacts/` |
| `hermes-project-data.py` (guard) | `require_contained(project_root, hermes_root / "task-runtime")`; `TASK_DATA_POLICY.md` documents `.hermes/` as project-local dir | Enforce `.project-local/` |

**Impact**: Dual runtime roots exist simultaneously:
- **Enforced by guard**: `.hermes/task-runtime/` (live, active)
- **Documented in AGENTS.md**: `.project-local/runs/` (claimed but not implemented)

This violates WL-P0-003 Zero-Spill Gate and WL-ARCH-001 architecture.

### 2. Hermes Guard Contradicts Migration

The guard at `packages/client-neutral-core/bin/hermes-project-data.py` is **deployed to HERMES_HOME/bin** and intercepts ALL terminal commands. It:
- Only accepts `.hermes/task-runtime/` as valid runtime root
- Documents `.hermes/` as the project-local directory in `TASK_DATA_POLICY.md`
- Cleans only `.hermes/task-runtime/`

This guard is **live-deployed** and will reject any command writing to `.project-local/` unless the guard itself is migrated first.

### 3. Evidence Paths Still Point to .hermes/

```python
# generate_current_state.py
DEFAULT_CI_EVIDENCE = Path(".hermes/task-artifacts/current-state-ci.json")
DEFAULT_RUNTIME_ATTESTATION = Path(".hermes/task-artifacts/current-state-runtime-attestation.json")
# Validator: "runtime attestation output must stay under .hermes/task-artifacts"
```

### 4. AGENTS.md Claims Migration Complete — Code Disagrees

AGENTS.md states:
> build/cache/temp roots live under `.project-local/runs/` ... evidence under `.project-local/artifacts/`

But runtime code implements `.hermes/task-runtime/` and `.hermes/task-artifacts/`.

---

## Non-Critical Issues

### CI Runtime Environment Variables
`run_quality_gate.py` injects these into every subprocess:
- `HERMES_PROJECT_RUNTIME_ROOT=.hermes/task-runtime`
- `HERMES_PROJECT_ARTIFACTS=.hermes/task-artifacts`
- `HERMES_KANBAN_HOME=.hermes`

These must be updated to `.project-local` equivalents.

### .project-local Has Zero Tracked Files
Both main and PR branch have 0 tracked files under `.project-local/` (it's gitignored by design). The migration created the directory structure in documentation but not in the runtime enforcement layer.

---

## Required Fixes Before Merge

1. **Migrate `run_quality_gate.py:project_runtime_environment()`** → `.project-local/runs/`
2. **Migrate `generate_current_state.py`** evidence paths → `.project-local/artifacts/`
3. **Migrate `hermes-project-data.py` guard** → enforce `.project-local/` as runtime root
4. **Update `TASK_DATA_POLICY.md`** → document `.project-local/` as project-local directory
5. **Sync HERMES_HOME guard** → deploy migrated `hermes-project-data.py` to `HERMES_HOME/bin/`
6. **Update AGENTS.md** → ensure documentation matches implementation
7. **Update CI runtime env vars** → `.project-local` paths
8. **Re-run full CI on exact-SHA** after all migrations

---

## Appendix: Test Results

- PR #123 CI (on `c6b7e8f`): **wlr-060-production-gates ✅ / work-lab-gate ✅** (both green)
- Current recovery branch (`d893072`): **Both gates ✅** (NF-02/03/04/09 fixes applied)

**Note**: Current CI passes because it runs on the OLD runtime boundary (.hermes/). The audit is about whether the NEW boundary (.project-local/) is actually implemented — it is not.

---

## Recommendation

**Do not merge PR #123** until the runtime boundary migration is complete. The directory structure migration is done; the runtime enforcement migration is not. Merging now would cement the dual-runtime-root violation and make future cleanup harder.

Estimated effort: 3-5 focused commits + guard redeployment + full CI verification.

---

*Generated by WL-000 audit at 2026-09-13 14:14 UTC*
