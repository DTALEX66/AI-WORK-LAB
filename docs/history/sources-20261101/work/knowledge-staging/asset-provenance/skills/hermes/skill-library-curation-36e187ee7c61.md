---
name: skill-library-curation
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/skill-library-curation/SKILL.md
---

---
name: skill-library-curation
description: "Use when curating Hermes skills by ownership and overlap."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
tags: [skills, curation, ownership, overlap, provenance, governance]
metadata:
  hermes:
    tags: [skills, curation, ownership, overlap, provenance, governance]
    related_skills: [hermes-agent-skill-authoring, agent-workflow-fortress]
---

# Skill Library Curation

## Overview

This skill governs class-level skill-library maintenance. It prevents a portable workflow pack from becoming a flat collection of one-session notes while protecting bundled, hub-installed, pinned, externally owned, and user-owned skills from autonomous edits.

The goal is not maximum deletion. The goal is one durable umbrella per capability class, with thin entries for intent/platform/project context and `references/` for session-specific detail.

## When to Use

Use when the user asks to:

- audit, merge, optimize, prune, or clean up skills;
- decide whether a skill is useful, duplicated, stale, or user-customized;
- compare repository authority with a live profile;
- reorganize a long skill into an umbrella plus references;
- preserve a drifted or user-owned live skill while improving repository authority.

Do not use for changing providers, MCP, plugins, authentication, sessions, memory, or live config unless a separate explicit request authorizes that exact operation.

## Ownership gate

Before writing anything, classify the target:

1. bundled/official Hermes skill;
2. hub-installed skill;
3. external-directory skill;
4. pinned skill;
5. user-owned skill (`created_by=None`, hand-written, URL-installed, or explicitly foreground-created);
6. curator-managed repository or adopted skill.

Only curator-managed targets may be changed autonomously. If the only relevant target is protected, report:

> Nothing to save.

For a user-owned skill that needs maintenance, recommend `hermes curator adopt <name>` instead of patching it.

Never treat being loaded or referenced as proof of edit authority.

## Evidence-first audit

1. Resolve the active profile and skill roots; remain profile-scoped.
2. Inventory names, enabled state, source, frontmatter, related skills, and hashes for managed roots.
3. Compare repository authority and live files only when the user explicitly authorizes live inspection. Hash difference means drift, not uselessness.
4. Search governance tests, manifests, provenance files, deployment mappings, and peer references before deleting or renaming a skill or paragraph.
5. Separate existence, installation, enabled state, and runtime behavior. A disk file is not proof that Hermes loaded or used it.
6. Keep credentials, tokens, auth stores, browser state, sessions, memory, MCP data, and provider routing out of the audit artifacts.

Completion: every proposed keep, merge, reference, delete, or protect decision has an ownership and evidence reason.

## Class-level consolidation

Use this decision table for each candidate block:

| Decision | Use when | Action |
|---|---|---|
| Keep/merge | reusable behavior changes agent action across projects | place one canonical rule in the class umbrella |
| Thin entry | the item only selects platform, intent, or project context | retain a short trigger and link to the umbrella |
| Reference | durable but bulky, version-specific, or reproduction-specific detail | write `references/<topic>.md` and add a one-line pointer |
| Delete | stale, duplicated, project-specific, provider-specific, or no-op prose | remove after checking contracts and references |
| Protect | user-owned, drifted, bundled, pinned, or externally owned | do not overwrite; report separately |

Do not merge skills merely because their names are similar. Merge only when triggers, permissions, verification, ownership, and failure boundaries are compatible. Keep separate skills when merging would reduce discoverability or combine unrelated permissions.

## Contract-aware pruning

A shorter skill can still break the workflow if it removes exact markers consumed by governance tests or other automation.

Before deleting established content:

1. search tests and manifests for exact strings and required behaviors;
2. retain canonical wording when the behavior still belongs to the class;
3. delete obsolete narrative around the marker instead of deleting the marker blindly;
4. validate frontmatter and related-skill resolution;
5. run the narrow governance suite and then the canonical quality gate.

A failed string-contract test means the canonical contract must be restored; it does not justify restoring unrelated sections. Record the exact test and path in the audit artifact.

### Provenance-registry hash + version contracts

Some repos register each managed skill in a provenance manifest that records `source_sha256` + `version` per SKILL.md (e.g. WORK-LAB `config/skill-provenance.yaml`, enforced by a `skill-provenance` gate; the managed-skill list lives in `config/managed-config-schema.yaml`). Rewriting the SKILL.md body without recomputing `source_sha256` and bumping `version` leaves that gate red — this is a **hash contract**, distinct from the string contract above. After any body rewrite: recompute the file's sha256, bump `version` (+1), and commit both in the same change. The registry tracks the SKILL.md path only; new/deleted `references/` files do not need registry entries, but the SKILL.md must carry a pointer line to each reference so future sessions discover it.

## Safe edit workflow

1. Read the complete target and 2–3 peer skills.
2. Write a keep/reference/delete/protect matrix with exact paths.
3. Make one coherent class-level edit. Avoid mixing unrelated skills in one rewrite.
4. Put session-specific transcripts, one-off application instructions, and bulky recipes in `references/`; do not preserve them as permanent rules.
5. When pruning a skill, search its complete reference directory and every repository consumer. Delete only orphaned, stale, project-specific, provider-specific, or duplicated references; retain any reference named by tests, manifests, or another document.
6. Update all cross-surface contracts in the same change: README capability tables, handoffs, Justfile targets, quality-gate documentation, manifests, and governance expectations. A skill rewrite is incomplete while these surfaces describe removed content or omit newly registered checks.
7. Validate frontmatter at byte zero, closing delimiter, description trigger, name, body, related skill names, and size.
8. Run provenance, targeted tests, canonical quality gate, and `git diff --check` serially when gates share project-local runtime state.
9. Recompute the exact diff/tree identity before review. Any later edit, rebase, or amend invalidates review evidence.
10. Treat any independent-review warning as NO-GO when the release standard requires C0/W0. Fix the warning, rerun the gates, compute a new identity, and obtain a fresh review; never reuse a prior review hash after editing.
11. Do not deploy live drift automatically. A repository authority update and a live profile update are separate operations.

## Common pitfalls

1. **Deleting by hash difference.** Drift is evidence for review, not evidence of uselessness.
2. **Merging by name.** Similar names can hide different permissions and triggers.
3. **Restoring a whole obsolete section after a contract failure.** Restore only the required canonical marker and behavior.
4. **Copying user-local or official skills into the repository.** Preserve source ownership and provenance.
5. **Turning a platform skill into a provider/router skill.** Keep model, proxy, MCP, and auth workflows in their owning skills.
6. **Keeping session sediment in the umbrella.** Move durable detail to a reference or delete it.
7. **Calling a quality gate while another gate writes the same runtime.** Run gates serially when they share project-local runtime state.
8. **Claiming live parity from repository provenance.** `live_checked=False` or `pending-live-sync` is an honest unknown, not a pass.
9. **Auditing size by directory total instead of SKILL.md body.** A size budget (e.g. skills <10 KB) applies to the SKILL.md **body** — the always-injected payload — not the whole directory. A ~50 KB SKILL.md with no `references/` is the "should have been split" signal; a small SKILL.md plus large on-demand `references/`/`scripts/` is healthy. Measure body and auxiliary as two numbers.
10. **Cutting before researching the authoritative size standard.** For slimming: first read the repo's own authoring standard and size target, survey same-source peers that are already compliant, and check the upstream official model (Anthropic's progressive disclosure — concise instructions + on-demand resources), THEN write a keep-vs-move plan. Split by "move, don't delete" so content is zero-loss, and surface the keep/move boundary for approval before executing.

## Verification checklist

- [ ] Target ownership and protection status are known.
- [ ] Active profile scope is explicit.
- [ ] Every keep/merge/reference/delete/protect decision has evidence.
- [ ] No duplicate canonical rule remains across the class.
- [ ] References are linked from the umbrella and contain no credentials.
- [ ] Frontmatter and related skills validate.
- [ ] Governance tests and canonical quality gate pass serially.
- [ ] Exact diff/tree identity is recorded before review.
- [ ] No protected live asset was overwritten.
- [ ] Final report distinguishes repository authority, live state, and unverified behavior.

See [`references/contract-aware-pruning.md`](references/contract-aware-pruning.md) for the reusable pruning checklist and the failure pattern from a contract-sensitive skill rewrite.
