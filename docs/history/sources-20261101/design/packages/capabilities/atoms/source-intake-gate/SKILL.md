---
name: source-intake-gate
description: "Inspect external sources for identity, license, provenance, security and allowed integration mode before any absorption."
version: 0.2.0
---

# Source Intake Gate

## Contract

Inspect external sources for identity, license, provenance, security and allowed integration mode before any absorption.

## Required behavior

- Read the current project state before acting.
- Emit machine-readable JSON that validates against the referenced local schema.
- Record evidence and source paths for every material claim.
- Never invent assets, metrics, approvals, licenses or production facts.
- Preserve existing files; destructive actions require explicit approval.
- Update the project state and artifact provenance after success.
