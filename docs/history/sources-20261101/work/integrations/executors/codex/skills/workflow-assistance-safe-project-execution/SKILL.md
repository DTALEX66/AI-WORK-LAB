---
name: workflow-assistance-safe-project-execution
description: "Use when a project execution contract needs scope or ownership resolution."
---

# Project execution contract

For ordinary edits, use the current user request and applicable project rules directly.
When scope or ownership is unclear, resolve the current authority, affected module,
existing dirty paths and test entry before writing. Preserve unrelated user work.
One writer owns each write set; independent work may use separate worktrees.

Permissions come from the current task. Existing authorization remains valid within
its scope; a skill does not add permissions or require a second approval for an
already authorized action. Validate the affected behavior, then run required project
checks once on the final tree. Report local, CI and installed evidence separately.
