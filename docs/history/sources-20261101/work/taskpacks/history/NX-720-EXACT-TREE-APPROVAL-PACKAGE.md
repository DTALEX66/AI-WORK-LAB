# NX-720 — Exact-Tree Review & Release Approval Package

**Package status:** `COMPLETED`
**Release approval:** `PENDING_HUMAN_APPROVAL`
**Date:** 2026-08-08

## Scope

This package is the final WORK-LAB exact-tree review artifact. It freezes the
current Git tree for a fresh read-only review and records evidence, boundaries,
rollback, and deferred items. It does not perform live provider execution,
paid smoke, global Hermes apply, OS-profile writes, or destructive cleanup.

## Active tree boundary

Exactly two active modules remain:

- `10-workflow/workflow-assistance`
- `30-observer/work-lab-observer`

Open Design and MiniGame are transferred scopes. Their old WORK-LAB roots are
not active and are not reintroduced.

## Completed evidence chain

- NX-000 predecessor/Gate A coverage;
- NX-100 cross-module source index;
- NX-110 source governance;
- NX-200 ACP compatibility;
- NX-210 Skill/MCP consistency;
- NX-300 OTel/OpenInference mapping;
- NX-310 usage ingestion;
- NX-320 usage rollup/freshness;
- NX-400 memory contamination controls;
- NX-410 Task Ledger replay;
- NX-500 DTCG/DESIGN.md contract;
- NX-510 production evidence;
- NX-520 sourced standards validators;
- NX-600 offline source health;
- NX-700 three-branch offline pilot;
- NX-710 size/performance/boundary regression.

Each task has a handoff, verifier/test evidence, and its applicable CI gate.
The local ignored Task Ledger is the authoritative task-state store for this
checkout; its NX-720 entry is written only after the review package is frozen.

## Review procedure

1. Confirm `HEAD == origin/main` and clean worktree.
2. Compute the tracked-path tree digest.
3. Confirm the two-module boundary and absence of transferred roots.
4. Confirm no tracked credentials, node_modules, build caches, binaries, or
   nested forbidden artifacts.
5. Confirm completed Task Ledger entries, handoffs, verifiers, and CI workflow.
6. Run the exact-tree verifier and unit tests from a fresh read-only reviewer.
7. Record the independent reviewer result before any release decision.

Machine-readable output is emitted by:

- `scripts/ci/exact_tree_review.py`
- `scripts/ci/verify_exact_tree_review.py`
- `tests/ci/test_exact_tree_review.py`

## Evidence classification

| Area | Status |
|---|---|
| Offline local fixtures | `VERIFIED` |
| PR aggregate CI | `VERIFIED` per merged task PR |
| Real external provider execution | `UNKNOWN_NOT_RUN` |
| External agent control | `UNKNOWN_NOT_RUN` |
| Paid smoke/commercial provider | `UNKNOWN_NOT_RUN` |
| Human visual calibration | `PENDING` |
| Global Hermes/live apply | `NOT_PERFORMED` |
| Destructive cleanup | `NOT_PERFORMED` |
| Release approval | `PENDING_HUMAN_APPROVAL` |

Automatic scores are regression signals only and never replace human visual
calibration or release approval.

## Security/privacy/license boundary

- No credentials, prompt/response bodies, or complete sessions are retained.
- Observer remains projection-only/read-only with empty mutation surface.
- New candidates are quarantined; OSV monitoring is offline/read-only and never
auto-fixes; Scorecard is signal-only.
- No complete upstream repository, node_modules, downloaded binary, or unknown
license source is intentionally vendored by these tasks.

## Rollback

Rollback is per merged PR. The final package itself can be reverted without
altering the transferred Open Design/MiniGame repository. Preserve the last
approved main commit and Task Ledger evidence before any release cleanup.

## Approval action boundary

A human may separately approve or reject release, live provider smoke, global
configuration apply, real OS-profile writes, paid execution, human calibration,
and archival cleanup. This package does not silently treat those actions as
approved.
