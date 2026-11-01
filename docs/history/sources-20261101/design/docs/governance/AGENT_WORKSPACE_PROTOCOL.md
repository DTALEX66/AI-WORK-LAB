# Agent Workspace Protocol（DL-TP-R1-006）
- One task = one branch = one Git worktree = one owner.
- Branch: agent/<agent-id>/<task-id>-<slug>; declare base SHA, owned/forbidden paths, depends_on, validation, rollback.
- Worktree root: .project-local/agent-workspaces/ (ignored).
- Authoritative paths (manifest, lockfile, schema index, generated reports) updated by merge coordinator only.
- Same authoritative scope cannot be held in parallel; conflicts rejected before dispatch.
- After merge: full re-verify from latest main.
