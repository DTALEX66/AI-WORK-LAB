---
name: design-direction-jury
description: "Generate and compare three materially distinct design directions, then persist the approved direction and rejected rationale."
version: 0.2.0
---

# Design Direction Jury

## Contract

Generate and compare three materially distinct design directions, then persist the approved direction and rejected rationale.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
