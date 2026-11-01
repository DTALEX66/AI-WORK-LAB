---
name: workflow-assistance-github-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-github-delivery/SKILL.md
---

---
name: workflow-assistance-github-delivery
description: "Use for GitHub repositories, issues, pull requests, checks, Actions, releases, remotes, or exact-SHA cloud readback."
---

# GitHub delivery

Use `git` for local identity and `gh` or the GitHub API for remote state. Never read or print authentication files or tokens.

1. Inspect remote, branch, status, HEAD/tree, current upstream, explicit
   `origin/main`, and divergence. Report each pair separately; do not say only
   "local equals remote".
2. Fetch before relying on remote state; preserve local WIP.
3. For PR or release work, inspect the exact diff and required checks.
4. Treat commit, push, PR creation/comment/merge, tag, release, and remote deletion as distinct side effects requiring the user's requested scope.
5. Never force-push or rewrite history.
6. After an authorized push, fetch and verify local HEAD equals the remote branch SHA.
7. Bind CI and release evidence to that exact SHA and include URLs or IDs in the result.

A squash merge creates a new main SHA, so the PR head need not be an ancestor of
main. Confirm `state=MERGED`, read the PR `mergeCommit`, find that commit on main,
and verify main CI against the merge SHA. Keep branch publication, PR merge, and
post-merge main CI as distinct states.

## Exact-SHA CI traps (absorbed from CLO delivery experience)

1. **Tracked generated-state freshness breaks after squash merge.** If a PR
   regenerates a tracked projection (`CURRENT_STATE.json`), the recorded head
   is the branch head; the squash merge replaces branch history, so that head
   is NOT an ancestor of the merged main head and the freshness gate fails.
   Fix: after merging, make a follow-up "chore: regenerate CURRENT_STATE for
   merged main head <sha>" PR regenerated on the CURRENT main head.
   Corollaries: (a) regenerate against main, never against a feature branch
   you are about to squash; (b) any PR that changes a canonical digest-input
   file MUST include its own regeneration, or the PR's own CI fails with
   `CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch`.
2. **Merge API 405 after base advanced.** If another PR merged after this PR
   was created, `mergeStateStatus` becomes UNKNOWN and the merge API rejects
   even though the head's checks were green for the old base. Do not
   force-push: `git merge origin/main` into the feature branch (real merge
   commit), push — checks re-run against the current base — then merge and
   re-verify aggregate on the new head SHA.
3. **Semantic gate IDs, not job names.** A changed-path classifier that
   emits IDs like `py-primary`/`static` must map each ID to its job-result
   env var; requiring a bare job name is a silent no-op that lets a required
   gate failure pass green.
4. **Trust selective SKIPs only after checking the diff class.** Pure
   Python/docs PRs correctly skip browser/desktop/installer lanes; verify the
   diff really only touched those paths before treating SKIPs as correct.
5. **Never reuse a successful run from a previous SHA**; query the run
   directly instead of treating a watcher timeout as pass/fail; cancel only
   obsolete runs, never the only run proving the current tree.

If remote access or auth is unavailable, report the blocker rather than inventing repository state.
