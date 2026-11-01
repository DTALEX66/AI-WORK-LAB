---
name: delivery-packager
description: "Create editable-source, preview, asset-license, preflight and approval manifests using `schemas/design-handoff.schema.json`."
version: 0.2.0
---

# Delivery Packager

## Contract

Create editable-source, preview, asset-license, preflight and approval manifests using `schemas/design-handoff.schema.json`.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
