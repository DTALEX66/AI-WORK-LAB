---
name: workflow-assistance-project-data-boundary
description: "Use when selecting task output paths or cleaning named project artifacts."
---

# Project data boundary

Resolve the current Git root and its data-boundary contract. WORK-LAB uses
`.project-local/runs/` for transient state and `.project-local/artifacts/` for evidence.
Other projects define their own paths; do not impose WORK-LAB paths on them.

Verify the resolved destination stays in the authorized root; runtime-only state
must be Git-ignored. Reject traversal and reparse paths that escape that root.
Protected drives, cross-project writes and software-owned paths require the task's
exact authorization. Credentials and private sessions/memory are not project evidence.

For cleanup, confirm the exact target, authorization and regenerability, then check
the filesystem postcondition. A lock/permission denial stays a blocker; do not kill
shared processes or bypass permissions. Trace a stray directory's creator before
claiming the boundary worked or failed; historical examples are not current proof.
