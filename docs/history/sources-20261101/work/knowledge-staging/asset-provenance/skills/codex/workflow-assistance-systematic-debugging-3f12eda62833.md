---
name: workflow-assistance-systematic-debugging
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-systematic-debugging/SKILL.md
---

---
name: workflow-assistance-systematic-debugging
description: "Use for bugs, failing tests, crashes, regressions, flaky behavior, incorrect output, or environment-specific failures."
---

# Systematic debugging

1. Reproduce the failure with the smallest real command and capture the exact error.
2. Establish scope: environment, version, working directory, inputs, and the last known-good path.
3. Trace data and control flow to the first incorrect state. Do not patch only the final symptom.
4. Check sibling call paths for the same defect class.
5. Add a failing regression test or deterministic negative control before the fix when code behavior changes.
6. Implement the narrow root-cause fix, run the regression test, related tests, and the project gate.
7. Verify the original user-visible failure path, not only the new unit test.

After roughly three unsuccessful lint/type-fix attempts on the same file, stop and report the blocker instead of looping.
