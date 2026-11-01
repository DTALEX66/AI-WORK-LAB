---
name: github-branch-hygiene
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/github/github-branch-hygiene/SKILL.md
---

---
name: github-branch-hygiene
description: "Clean up remote branches safely after squash-merged PRs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Git, Branches, Cleanup, Merge, Squash]
    related_skills: [github-pr-workflow, github-repo-management]
---

# GitHub Branch Hygiene — cleaning up remote branches safely

Use when a repo has accumulated remote branches after many PRs (squash-merged,
closed, or orphaned), and you need to reclaim them without losing unmerged
content. Triggered by noticing stale `feat/*`/`fix/*`/`docs/*` refs on origin,
or after a merge campaign.

## Core principle

A branch that no longer exists as an open PR is NOT automatically deletable.
Triage by PR state, then verify content absorption before deleting. Delete
only what is provably absorbed or provably empty; keep anything that is the
sole copy of real content.

## Step 1 — Enumerate remote branches

```bash
git ls-remote origin 'refs/heads/feat/*' 'refs/heads/fix/*' 'refs/heads/docs/*'
```

## Step 2 — Triage each branch against its PR state

**The critical gotcha: `gh pr list --head <branch>` returns NOTHING for
merged PRs.** The default query only covers open PRs. You must pass the state:

```bash
# merged PRs (the bulk of leftovers after a squash-merge campaign):
gh pr list --state merged --head <branch> --json number,mergedAt --jq '.[0]'

# closed-but-never-merged PRs (orphans — investigate before deleting):
gh pr list --state all --head <branch> --json number,state --jq '.[0]'
```

Categories:

| PR state | Branch fate |
|---|---|
| MERGED | Safe to delete after verifying absorption (step 3) |
| CLOSED (never merged) | Investigate: does main already contain the content? |
| No PR at all | Check unique commits; 0 unique = empty branch, delete; else investigate |

## Bulk cleanup: API `merged_at` is the authoritative triage, not git ancestry

When cleaning a repo with 50+ leftover branches after a merge campaign, do
NOT triage one-by-one with git ancestry or `git branch --merged` — squash
merges break ancestry, so git says "not fully merged" for every absorbed
branch (2026-08-14, DESIGN-LAB 55→3 cleanup). The GitHub REST API already
has the ground truth: a PR with a non-null `merged_at` means its content IS
on main. Two API calls enumerate the whole decision:

```python
# 1. all remote branches (exclude main)
GET /repos/{owner}/{repo}/branches?per_page=100

# 2. all closed PRs (paginate if >100)
GET /repos/{owner}/{repo}/pulls?state=closed&per_page=100
merged_heads = {pr['head']['ref'] for pr in pulls if pr.get('merged_at')}

# 3. deletable = branches that are merged PR head branches
to_delete = [b for b in branches if b in merged_heads]
survivors = [b for b in branches if b not in merged_heads]  # investigate/keep
```

- **A branch with no merged PR is NOT auto-deletable** — two classes survive:
  closed-never-merged PR branches (superseded work, keep as history evidence)
  and branches with no PR record at all (manual pushes / migration remnants;
  keep unless proven empty).
- **Batch-delete via the refs API** (no `gh` needed, works with a token):
  `DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}` in a loop with
  `time.sleep(0.15)` between calls to stay under the rate limit. A branch
  deleted between enumeration and DELETE returns 422 — treat as success
  (already gone), not failure.
- **After deletion, `git fetch origin --prune`** clears stale local
  `origin/*` refs. Expect a long deletion list in the prune output — that is
  the local mirror syncing, not new damage.
- **`git push origin --delete <branch>` failing with "remote ref does not
  exist" means GitHub already auto-deleted it** (some merges remove the head
  branch, some don't — do not assume which). Skip it and let `--prune` clean
  the local ref. The API `branches` list is the source of truth for what
  actually exists remotely.

## Step 3 — Verify content absorption (squash-merge remnant check)

A branch with unique commits vs main is NOT proof of unmerged content:
squash-merge folds everything into one commit on main, and the branch's
original commits are never referenced again — they appear as "unique" forever.

```bash
# 1. unique commits on the branch:
git log --oneline origin/main..origin/<branch>

# 2. files that differ between branch and main:
git diff --name-only origin/main...origin/<branch>

# 3. files present on the branch but MISSING from main (the real risk):
for f in $(git diff --name-only origin/main...origin/<branch>); do
  git cat-file -e origin/main:$f 2>/dev/null || echo "BRANCH-ONLY: $f"
done
```

- **0 branch-only files** = every file on the branch exists on main with
  equal-or-newer content → fully absorbed, safe to delete.
- **Diff direction matters**: `git diff origin/<branch>:<file> origin/main:<file>`
  should show main as a superset (additions like SUPERSEDED banners, new
  imports). If the branch carries files/versions absent from main, keep it.

## Step 4 — Batch-delete the verified-absorbed branches

```bash
gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>
```

Batch with a loop over the merged/absorbed list; collect failures. After
deleting, `git fetch --prune origin` to drop local refs. Keep the deletion
list as evidence (count + which categories).

## What to KEEP (do not delete without Owner)

- **Release-contract branches** (`release/v*`): historical release contract
  refs. Never touch.
- **Sole copy of a historical snapshot**: a closed PR's doc (e.g. a dated
  verification summary) that exists nowhere on main. The branch is the only
  reference; deleting loses the content. Keep, or offer to archive the file
  into `docs/` first (Owner decision).
- **Other active sessions' branches**: `codex/*` or similarly named refs may
  belong to a different working session. Leave them alone.
- **Closed PRs with unique unabsorbed content**: content never reached main;
  deleting is a real loss. Keep until Owner decides.

## Pitfalls

- **`git branch --merged main` is useless after squash merges** — squash folds
  the branch's commits into one new commit on main, so the branch tip is never
  an ancestor of main. `--merged` will report every squash-merged branch as
  "not merged". Use content-level checks instead (step 3) or REST PR triage.
- **Plain `git branch -d <branch>` ALSO refuses on squash-merged branches**
  (same ancestry test): it prints `error: the branch 'X' is not fully merged`
  with a hint to use `-D`. That refusal is expected, not evidence the branch
  holds unmerged content — once the REST API has confirmed the PR's
  `merged_at`, delete with `git branch -D` (validated 2026-08-14, DESIGN-LAB:
  3 local branches deleted this way after API triage).
- **`gh pr list --head` without `--state merged` silently returns nothing**
  for merged PRs — you will misclassify every merged branch as "no PR" and
  either keep junk or delete without evidence. Always pass the state.
- **`git fetch --prune` deletes local remote-tracking refs for branches you
  deleted on the server** — expected, but note it (you may see unrelated
  refs disappear, e.g. a stale `origin/fix/...` you forgot about).
- **A closed PR's branch with 1-3 unique commits is the dangerous case**:
  its content may have been superseded by a later PR (verify per-file via
  `cat-file -e`) or may be genuinely lost (keep). Verify before deciding.
- **Don't delete from the canonical worktree if another worktree holds the
  branch** — remove the other worktree first (`git worktree remove --force`),
  or the delete will not be clean.
- **Filename globs with CJK content break bash `ls-files` loops** — the shell
  expands `*.md` patterns against filenames containing Chinese characters and
  errors with "No such file or directory" per line. Use `git ls-files | while
  read` piped to a Python/size check, or `git ls-files -z | xargs -0`, never a
  bare `for f in $(git ls-files ...)` when CJK filenames are possible.

## Append-only log dedup (EXECUTION_STATUS_LOG pattern)

Append-only status logs accumulate duplicate entries across sessions (the same
PR logged twice with two LOG numbers, or the same LOG number written twice).
Periodically verify and dedupe:

```bash
grep '### LOG-' docs/truth/EXECUTION_STATUS_LOG.md | sort | uniq -d
```

When a duplicate exists, remove the LATER block (keep the first occurrence),
then re-verify the number sequence is unique and contiguous. Commit the dedupe
as its own docs commit on the authority branch. A duplicate-free log is what
makes "LOG-004..130" usable as a continuity index.

## Verification

- After cleanup: `git ls-remote origin 'refs/heads/*'` should show only
  `main`, authority branches, release-contract refs, and the few legitimate
  survivors.
- Record: how many branches deleted per category (merged / absorbed-orphan /
  squash-remnant / empty), what was kept and why.
