---
name: brief-normalizer
description: "Convert client notes, files and constraints into `schemas/design-brief.schema.json` without inventing missing facts."
version: 0.2.0
---

# Brief Normalizer

## Contract

Convert client notes, files and constraints into `schemas/design-brief.schema.json` without inventing missing facts.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
