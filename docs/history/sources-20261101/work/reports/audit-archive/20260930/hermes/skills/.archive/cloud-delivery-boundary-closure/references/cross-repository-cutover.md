# Cross-repository cutover reference

Use this recipe when a user asks to move an untracked or ignored subtree from repository A into repository B and then remove A's local copy.

## Safe sequence

1. Discover both roots independently: absolute path, `git rev-parse --show-toplevel`, branch, `git remote -v`, target default branch, and clean/dirty state. Never infer the active remote from the shell's current directory.
2. Inspect the target tree before copying. Build an explicit source→target path crosswalk; do not add a duplicate top-level directory merely because names differ.
3. Inventory source files without reading secrets. Record count, bytes, path, and SHA-256 in ignored project evidence. Classify ignored files with `git check-ignore -v`; force-add only the audited target prefixes when the user explicitly wants those artifacts published.
4. Copy into a target feature branch first. Run the target's relevant tests before commit; tests may mutate generated/ignored or newly tracked bundles, so re-check the worktree after tests and stage the final reviewed tree.
5. Commit and push the feature branch. Read back remote branch SHA and target tree paths. Do not infer that “push to repository” authorizes a main-branch update; ask or keep the feature branch unless the user explicitly authorizes default-branch promotion.
6. If default-branch promotion is explicitly authorized, verify the target checkout remote again immediately before pushing, require a fast-forward update, and read back both `refs/heads/main` and the feature ref. Never run a target refspec from the source checkout.
7. Delete only the exact source subtree after remote readback succeeds. Preserve a non-secret file-level manifest and re-scan the exact source prefix. Remove an empty parent only after confirming it contains nothing else.
8. Report separately: local source removed, target branch uploaded, default branch promoted, local tests, remote exact SHA, and any CI/PR state not actually verified.

## Common traps

- A target repository may already contain the migrated content under a reorganized path; compare hashes before overwriting.
- Broad `.gitignore` rules can hide real product assets. `git status` alone is not a complete inventory.
- A test/build can rewrite tracked files after staging. Re-check `git status`, diff, and manifest hashes before the commit.
- A clean target branch does not prove the source was removed; re-scan the source path after deletion.
