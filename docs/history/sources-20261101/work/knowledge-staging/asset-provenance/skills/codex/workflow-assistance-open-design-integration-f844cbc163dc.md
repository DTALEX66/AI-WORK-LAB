---
name: workflow-assistance-open-design-integration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-open-design-integration/SKILL.md
---

---
name: workflow-assistance-open-design-integration
description: "Use when a task references Open Design, its migration pointer, or read-only collaboration."
---

# Open Design integration

## What Open Design is now

Open Design (`20-design/open-design`) was transferred out of WORK-LAB to
`DTALEX66/DESIGN-LAB` on the authorized migration branch. WORK-LAB
retains only:

- the one-time handoff pointer and migration evidence under
  `90-archive-manifests/` and ignored `.hermes/` artifacts;
- a read-only observation declaration in
  `config/config-ownership.json`:
  `open-design` -> `PROJECT_OVERLAY / OBSERVE`,
  `open-design.read_only_mcp` -> `OBSERVE`.

Open Design is an independent repository owned by its own workflow. It is
**not** an active WORK-LAB module and must never be re-absorbed into this
monorepo.

## Workflow role

- Open Design is an observation/input surface only. Workflow Assistance never
  executes, approves, retries, applies, or rolls back changes inside
  `DTALEX66/DESIGN-LAB`.
- Read-only collaboration is allowed: reviewing its public tree, reading its
  canonical docs, and using its read-only MCP surface for evidence.
- Do not copy Open Design assets, fixtures, or runtime state into WORK-LAB
  evidence, Git, or handoffs.
- Do not move or re-host the transferred module; do not restore
  `20-design/open-design` here.

## Handling Open Design claims

Open Design output (reports, audits, design deliverables) is a candidate
claim until verified with native evidence:

1. Prefer the canonical repository (`DTALEX66/DESIGN-LAB`) as the
   source of truth for its own state; never rely on WORK-LAB's stale copies or
   migration pointers for current facts.
2. Verify any path, artifact, or checksum claim against the live remote
   (exact SHA / CI / release) before acting on it.
3. If a claim contradicts WORK-LAB ownership rules (e.g. suggests Open Design
   becomes an active module or writes WORK-LAB state), classify it
   `REFUTED_BY_BOUNDARY` and record the boundary rule cited.

## Pitfalls

- Treating the migration pointer or archive manifest as current Open Design
  state.
- Copying Open Design deliverables into WORK-LAB task packs as if they were
  Workflow-owned assets.
- Re-creating `20-design/open-design` trees in this repo.
  repo.
- Acting on an Open Design audit report without verifying its exact SHA/CI.

## Verification

- A claim about Open Design is verified only against its canonical remote
  repository, not against WORK-LAB's historical snapshots.
- WORK-LAB's tree contains no active Open Design module: `git grep` for
  `open-design` returns only boundary/config/archive references.
