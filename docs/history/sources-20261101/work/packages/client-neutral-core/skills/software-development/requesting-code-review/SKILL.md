---
name: requesting-code-review
description: "Thin compatibility entry for pre-commit or release review; delegates all review, frozen-tree, writer, commit and CI rules to agent-workflow-fortress."
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-review, verification, security, pre-commit]
    related_skills: [agent-workflow-fortress]
---

# Requesting Code Review

This is a compatibility trigger only. Load and follow `agent-workflow-fortress`; this skill defines no second review pipeline.

Required invariants:

1. One writer per checkout; writers use isolated worktrees.
2. Explicitly stage intended paths and run project-specific tests/security scans.
3. Record the exact candidate with `git write-tree`.
4. The independent reviewer reviews that tree; any edit/rebase/rebuild/amend invalidates the verdict.
5. Verification/review does not authorize commit, push, merge, PR creation, or auto-fix.
6. Never use `git add -A`, stash-based baseline mutation, or a write-capable reviewer/fix agent in the owned checkout as an automatic review step.

For the full procedure, load `agent-workflow-fortress`; this compatibility entry intentionally carries no separate attachments or pipeline.
