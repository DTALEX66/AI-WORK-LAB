# BOUNDARY marker — knowledge-staging/ (WORK-LAB V2, three-project split)

Classification: HISTORY_ONLY_CONVERGE
Authority: .project/governance/three-project-boundary.json (boundary_splits[KNOWLEDGE_STAGING])

## Problem
Root-level `knowledge-staging/` reads as an active, long-lived WORK-LAB-owned
knowledge asset. It is NOT a canonical active module. It holds staging
subtrees: archive / asset-provenance / candidates / catalog / migration /
research / troubleshooting / workflow.

## Converge (C2: do not delete; converge root ownership)
- knowledge-staging/ is a STAGING / EVIDENCE directory, not an active
  knowledge-truth owner. Knowledge truth belongs to ArcheAxis; design
  research belongs to DESIGN-LAB.
- Root-level presence is recorded as "converged out of active ownership":
  the boundary verifier treats it as history/staging only and forbids any
  new root-level active knowledge owner from appearing.
- No code here is imported by production; callers are 0 (verified by grep).

## Status: marked + gated. No file moves this round.
