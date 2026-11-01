# BOUNDARY marker — services/memory (WORK-LAB V2, three-project split)

Classification: MIGRATION_CANDIDATE_TO_ARCHEAXIS
Authority: .project/governance/three-project-boundary.json (boundary_splits[MEMORY_BACKEND])

## What stays in WORK-LAB (control plane, keep-set)
These are WORK-LAB's own execution/governance contracts — NOT a memory system:
- SessionPrivacyBoundary, ContextExportBoundary, ContextCapsule
- MemoryQueryContract (the thin query interface only)
- ArcheAxisClient / ArcheAxisHandoff (adapter that CALLS ArcheAxis, does not store)
- Provenance, PermissionGate, Receipt

## What migrates to DTALEX66/ArcheAxis-Knowledge-OS (move-set)
The actual memory semantics:
- retain / recall / reflect, long-term memory store, memory provider,
  repo-import, docs-import, knowledge record/storage, memory promotion.

## Seam / compatibility
- This directory is a MIGRATION CANDIDATE, not an active WORK-LAB-owned memory
  system. No new caller may import it as a memory backend.
- The query surface is reduced to MemoryQueryContract (see
  integrations/archeaxis/contracts/memory-query-contract.py).
- verifier: scripts/ci/verify_three_project_boundary.py (fail-closed).
- migration manifest: .project/governance/boundary-migration-manifest.json

## Status: NOT moved this round (P2/P3 no new features). Marked + gated only.
