---
name: reference-dna-analyzer
description: "Analyze owned or authorized references into transferable structure and explicit do-not-copy boundaries using `schemas/reference-dna.schema.json`."
version: 0.2.0
---

# Reference DNA Analyzer

## Contract

Analyze owned or authorized references into transferable structure and explicit do-not-copy boundaries using `schemas/reference-dna.schema.json`.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
