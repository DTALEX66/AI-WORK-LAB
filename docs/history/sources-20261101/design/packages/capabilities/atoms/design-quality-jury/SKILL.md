---
name: design-quality-jury
description: "Run discipline rubric, deterministic checks and an independent critique; emit `schemas/design-critique.schema.json`."
version: 0.2.0
---

# Design Quality Jury

## Contract

Run discipline rubric, deterministic checks and an independent critique; emit `schemas/design-critique.schema.json`.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
