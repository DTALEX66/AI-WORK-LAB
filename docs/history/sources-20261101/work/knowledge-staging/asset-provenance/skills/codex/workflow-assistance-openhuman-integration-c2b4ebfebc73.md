---
name: workflow-assistance-openhuman-integration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-openhuman-integration/SKILL.md
---

---
name: workflow-assistance-openhuman-integration
description: "Use when OpenHuman scans or audits the workspace."
---

# OpenHuman integration

## What OpenHuman is

OpenHuman is a separate local-first desktop AI agent (tinyhumansai/openhuman) on
the same machine. It can scan workspaces, maintain its own users/skills/memory,
and produce audit-style reports (e.g. junction/duplicate/path findings). It is
an independent runtime, not part of Workflow Assistance.

## Workflow role

- OpenHuman is an observation/scan input, never a workflow owner. Workflow
  Assistance remains the sole active controller of task state, the Telemetry
  Ledger, delivery gates, and single-writer checkouts.
- OpenHuman may read the workspace read-only. It must not execute, approve,
  retry, apply, rollback, or change task state in a Workflow-owned checkout.
- One writer owns a checkout. If OpenHuman holds a checkout open, coordinate
  with the user before writing to the same tree; never double-write.

## Private runtime boundary (never read, print, copy, or commit)

`C:\Users\<user>\.openhuman\` is OpenHuman's private runtime, same class as
`.codex` and `.hermes`:

- `dev-keychain.json` — credentials; hard boundary, never inspect;
- `users/`, `logs/`, `memory`, `workspace/`, `cache/`, `skill-registry/`,
  `active_user.toml`, `window_state.toml` — user data and app state;
- the app install root (e.g. `C:\Users\<user>\OpenHuman\`) is app-owned.

Do not copy any of it into a project, Git, evidence, or a handoff. Do not
redact-and-paste its contents either.

## Consuming OpenHuman findings (candidate claims, not facts)

OpenHuman's scan output is a candidate claim until verified with native
evidence. The 2026-08-10 regression: OpenHuman reported two "duplicate
junction entries" (`OS configuration` → `Cognitive-Loop-OS`, `WORK-LAB` →
`Star-Trails-Log`) that did not exist; the paths were plain directories.

Verification ladder before ANY action:

1. Windows-native reparse check on the exact reported path:
   `fsutil reparsepoint query "<path>"` — a junction/symlink returns a tag;
   "not a reparse point" (error 4390) refutes the junction claim.
2. PowerShell attribute check:
   `Get-Item -LiteralPath "<path>" | Select Attributes, LinkType, Target`
   — `ReparsePoint` bit set + `LinkType=Junction` + `Target` = junction;
   plain `Directory, Archive` with empty Target = real directory.
3. Content comparison: a junction's two sides expose the SAME tree; if the
   reported pair has different top-level entries, the claim is refuted.
4. For deletion/cleanup claims, additionally verify: git HEAD/branch of any
   repository involved, cloud preservation of any history, hash-verify before
   deleting, read back after.

Classify each finding `CONFIRMED` / `REFUTED` / `NEEDS_PATH` (when OpenHuman
did not give an exact path) and record the classification. Never act on an
unverified claim, and never "clean up" a path because a scanner labelled it a
junction or duplicate.

## Pitfalls

- Trusting a scanner's label instead of the filesystem's reparse data.
- Reading OpenHuman's keychain/users/logs to "understand" it.
- Letting OpenHuman and a Workflow writer mutate the same checkout.
- Deleting a path that a scanner called a "duplicate entry" without native
  verification (in the 2026-08-10 case the supposed junctions were the real
  WORK-LAB repository and the OS configuration toolchain project).
- Copying `.openhuman` state into a repo, handoff, or evidence pack.

## Verification

- A junction claim is CONFIRMED only when `fsutil reparsepoint query` returns
  a tag AND `Get-Item` shows LinkType+Target for the exact path.
- A cleanup is done only when the source is gone AND read back shows absence
  AND the canonical/cloud copies are intact.
