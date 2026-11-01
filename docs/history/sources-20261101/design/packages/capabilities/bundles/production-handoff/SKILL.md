---
name: production-handoff
description: Production preflight and editable multi-format delivery with provenance. Use when a design must become a production-ready, editable, evidence-backed delivery package.
---

# Production Handoff

## When to use
A design direction is approved and must move into production handoff: preflight
checks, editable source export, BOM, and provenance-bounded delivery.

## Flow
1. Run `commercial-preflight` on the approved design (dimensions, bleed, color
   space, fonts, assets, BOM, accessibility).
2. Package via `delivery-packager`: editable source, preview, asset manifest,
   font/license list, versions, rollback.
3. Run `cross-format-coherence-critic` to keep consistency across formats.
4. Bind provenance and release-evidence; do not overclaim E-level.

## Outputs
- `preflight` report
- `design-handoff` package
- `provenance` record
- `release-evidence` record (for release)

## Safety
- Never claim runtime/commercial readiness from files alone.
- No project-external writes, no secrets, no E: drive access.
