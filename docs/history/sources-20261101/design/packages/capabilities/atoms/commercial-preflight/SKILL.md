---
name: commercial-preflight
description: "Run the selected digital, print, spatial, packaging, 3D, motion or document production profile and emit `schemas/preflight.schema.json`."
version: 0.2.0
---

# Commercial Preflight

## Contract

Run the selected digital, print, spatial, packaging, 3D, motion or document production profile and emit `schemas/preflight.schema.json`.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
