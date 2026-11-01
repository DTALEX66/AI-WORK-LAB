# WORK-LAB v2 task matrix and status summary

This is a handoff index, not a replacement for the authoritative v2 task graph. Statuses are evidence-scoped and must not be promoted across layers.

**2026-08-06 current-tree note:** the authoritative v2 task graph attachment is not
present in the local attachment directory. A visible older taskpack maps `WA-003`
and `WA-004` to different titles than the v2 handoff. The rows below therefore keep
the v2 labels as unresolved identity, while recording only evidence produced by the
current tree; no taskpack identity is inferred from the older ZIP.

| Scope | Current status | Evidence | Remaining boundary |
|---|---|---|---|
| ROOT governance/contracts/dependencies | `LOCAL_PASS` | Root gates, contract catalog `20/20`, module dependencies PASS | Fresh CI must match the final pushed SHA |
| ROOT error ledger | `LOCAL_PASS` | `ERROR_LEDGER_PASS entries=17 classifications=5 raw_sensitive_data=false counts_consistent=true` | Keep sanitized canonical copy in `50-taskpacks/error-ledger.json` |
| CONT-005..008 continuity | `LOCAL_PARTIAL` | Focused ledger/reconciliation implementation and tests | Canonical assessment/reconciliation writeback not independently confirmed |
| WA core/schema/adapter conformance | `LOCAL_PASS` | Current Workflow `QUALITY_GATE_PASS`; adapter focused tests and core schema checks pass | Growth input discovery and Git/GitHub delivery reconciliation remain open |
| WA-003 / WA-004 | `LOCAL_PARTIAL` / task identity unresolved | `growth_candidates.py`; 5 lifecycle tests; compile/governance gate pass | Authoritative v2 task mapping, real discovery/scanning input, and delivery reconciliation |
| WA-007 / WA-008 | `PARTIAL` / incomplete | Delivery boundary and existing workflow assets | Git/GitHub evidence reconciliation and responsibility split |
| OD domain pack/benchmark registry | `LOCAL_PASS` / `E2 isolated-runtime` | Domain boundary verifier PASS; Open Design verifier `460/460`; benchmark registry `12`, human calibration required | E3 live runtime and human calibration not complete |
| OD-002 / OD-007 | `BLOCKED_USER_DECISION` | Dual-source and license boundaries documented | Select source-of-truth and license policy |
| OD-004 / OD-006 / OD-008 | `PARTIAL` / incomplete | Design contracts and verifier exist | Master method cards, human QA, product receipt and device regression |
| Observer skeleton/runtime | `LOCAL_PASS` / `LOCAL_PARTIAL` | Skeleton/runtime, persistent store and cross-module evidence projection tests pass | Tauri UI, continuously supervised projections, budgets, quality persistence and isolation |
| OBS-001 / OBS-005..009 | `PARTIAL` / incomplete | Structural/runtime evidence only | Full runtime integrations and UI are not implemented |
| MINIGAME local analytics | `LOCAL_PASS` | `321/321 PASS`; generated files restored | Product is archive/fixture only in v2 root |
| MG-003 / MG-004 / MG-005 / MG-007 / MG-008 | `BLOCKED` / `BLOCKED_USER_DECISION` | Boundaries and duplicate-source counts recorded | Fact-source decision, platform/device/commercial/product acceptance |
| INT-001 | `BLOCKED_USER_DECISION` | No second client selected | User selects reference client |
| INT-002..006 | `LOCAL_PASS` / E2 isolated-runtime | `INT-002-006-READONLY-EVIDENCE-PROJECTION.md`; Workflow/Open Design summaries persist and rebuild in Observer | Real continuously supervised runtime, UI/readback and final acceptance |
| Hermes live plan | `WAITING_APPROVAL` | No live mutation performed | Explicit independent approval required |
| Token Monitor release | `BLOCKED` | Self-test only; real npm/Tauri path unavailable | Dependency/build/signing/release evidence |

## Evidence scale

- `LOCAL_PASS`: current worktree command or test passed.
- `E2 isolated-runtime`: isolated/staging runtime passed; not live runtime.
- `CLOUD_CI_PASS`: exact pushed SHA passed GitHub Actions.
- `PARTIAL`: some contract or implementation layers exist, downstream acceptance is absent.
- `BLOCKED`: prerequisite, environment or external boundary prevents execution.
- `BLOCKED_USER_DECISION`: user must select policy/source/platform/license/client.
- `NOT_RUN`: no current evidence; do not infer from historical output.

## Current canonical references

- Positioning: `00-governance/PROJECT_POSITIONING.md`
- Module registry: `00-governance/projects.json`
- Ownership: `00-governance/module-ownership.json`
- Task summary: `50-taskpacks/TASKPACK_SUMMARY.md`
- Reconciliation: `50-taskpacks/WORK-LAB-HERMES-TASKPACK-RECONCILIATION.md`
- Handoff: `50-taskpacks/WORK-LAB-V2-HANDOFF.md`
- Sanitized ledger: `50-taskpacks/error-ledger.json`
