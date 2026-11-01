# gh pr merge benign worktree warning

When another worktree locally checks out `main`, `gh pr merge --squash` prints:

```
failed to run git: fatal: 'main' is already used by worktree at 'D:/All projects/.../full-materials-fix'
```

The SQUASH MERGE **succeeds on GitHub** but `gh` cannot update the local
`main` ref.  Verify with:

```bash
gh pr view <N> --json state --jq '.state'    # → MERGED
git ls-remote origin main | head -1           # → new SHA
```

Do NOT retry, force-merge, or treat this as a failure.  The GitHub merge
went through; only the local ref update was blocked.
