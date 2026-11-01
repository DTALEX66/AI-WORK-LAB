# BOUNDARY marker — services/knowledge (WORK-LAB V2, three-project split)

Classification: SPLIT_GUARD_AND_SEMANTICS
Authority: .project/governance/three-project-boundary.json (boundary_splits[KNOWLEDGE_TRUTH])

## What WORK-LAB keeps (the export guard, enforcement layer)
`promotion_gate.py` stays, RELOCATED semantically to "knowledge export guard":
- content-level FORBID checks: secrets / raw bash / all-chat / unverified / temp logs
- provenance-required, evidence level, source identity, payload integrity
- fail-closed last-door behaviour (rejects promotion into another project's store)

WORK-LAB emits **KnowledgeCandidate**, never Knowledge Truth.

## What migrates to DTALEX66/ArcheAxis-Knowledge-OS (semantics + truth)
- KnowledgeCategory truth, knowledge acceptance, verified-lesson adjudication,
  architecture-knowledge, promotion DECISION, classification, long-term status.
- i.e. the part of this module that DECIDES a record is knowledge truth, not just
  "allowed to cross".

## Seam / compatibility
- The thin emitted contract is in
  integrations/archeaxis/contracts/promotion_contract.py (KnowledgeCandidate + guard verdict).
- Existing tests load promotion_gate.py via importlib path-load; this marker adds no
  import, so they remain green (P2/P3: no code move this round — marked + gated only).
- verifier: scripts/ci/verify_three_project_boundary.py

## Status: NOT split this round. Marked + gated; migration is the C2 P3 step.
