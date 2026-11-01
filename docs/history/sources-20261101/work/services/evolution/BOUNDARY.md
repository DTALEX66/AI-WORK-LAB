# BOUNDARY marker — services/evolution (WORK-LAB V2, three-project split)

Classification: BOUNDARY_SPLIT
Authority: .project/governance/three-project-boundary.json (boundary_splits[EVOLUTION])

## Semantics (ch 31 + user instruction)
- WORK-LAB Evolution = self-modification governance of WORKFLOW / RUNTIME /
  CONFIG / SKILL / PROMPT (M1..M5 mutation levels, sandbox, security-eval,
  approval, rollback, receipt). This is execution governance, not knowledge.
- ArcheAxis Evolution = knowledge/memory/learning evolution: continual
  learning, knowledge evolution, memory consolidation, human-learning,
  long-term cognitive growth.

## What stays in WORK-LAB (all 5 modules here are the keep-set)
- mutation_policy.py (M1..M5 gate), exo_sandbox.py, independent_eval.py,
  provider.py — these are the WORKFLOW improvement machinery.

## What migrates to DTALEX66/ArcheAxis-Knowledge-OS
- The learning/memory/consolidation semantics that are NOT workflow/runtime/
  config governance. None of the 5 current modules claim those today, so the
  move-set is empty at code level; the split is recorded as semantics here and
  enforced as "no new knowledge-evolution owner may appear in WORK-LAB".

## Seam / compatibility
- mutation_policy.py is the governance-scope assertion: any new M-level that
  targets knowledge/memory/learning must be routed to ArcheAxis, not added here.
- tests load these modules via importlib path-load; marker adds no import.
- verifier: scripts/ci/verify_three_project_boundary.py

## Status: NOT moved this round. Marked + gated.
