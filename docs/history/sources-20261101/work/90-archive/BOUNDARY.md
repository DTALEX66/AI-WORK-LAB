# BOUNDARY marker — 90-archive/ (WORK-LAB V2, three-project split)

Classification: HISTORY_ONLY_CONVERGE
Authority: .project/governance/three-project-boundary.json (boundary_splits[ARCHIVE_90])

## Problem
Root-level `90-archive/` is a SECOND history retrieval system alongside
`docs/history/`. Two anchors for one retrieval surface is exactly the
drift the V2 convergence forbids.

## Converge
- 90-archive/ holds frozen historical reports (e.g. reports-history). It is
  evidence, not an active module. No production code imports it (0 refs).
- Single history retrieval anchor = docs/history/. 90-archive/ is recorded
  as a history-only directory that must not grow as an active owner.
- No file moves this round; the boundary verifier forbids a new root-level
  second history system and keeps 90-archive/ as history-only.

## Status: CONVERGED 2026-09-23 (user-authorized, branch post-merge/90-archive-convergence).
- `90-archive/reports-history/2026-09-05/*` (15 files) git-moved to
  `docs/history/archive/reports-history/2026-09-05/` (single history retrieval anchor = docs/history/).
- This directory now retains ONLY this BOUNDARY.md marker, which the three-project boundary
  verifier (`scripts/ci/verify_three_project_boundary.py` SPLIT_DIRS) requires. No active content
  here; no new files may be added (forbiddenNewOwners: '90-archive as a root active dir').
- Migration record: `.project/governance/boundary-migration-manifest.json` MOVE-005 status=EXECUTED_20260923.
