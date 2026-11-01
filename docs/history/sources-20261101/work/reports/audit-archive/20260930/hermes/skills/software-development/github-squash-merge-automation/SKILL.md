---
name: github-squash-merge-automation
description: "Use when automating GitHub PR merge loops via REST API."
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [github, rest-api, pr, squash-merge, ci, branch-hygiene]
---

# GitHub Squash-Merge Automation (no gh CLI)

## When to use

- Automating PR create → CI verify → squash merge → branch cleanup loops via GitHub REST API (gh CLI not installed).
- Cleaning up 50+ leftover head branches after squash-merged PRs.
- Polling CI run status without exhausting the anonymous rate limit.

## Core recipe (validated DESIGN-LAB 2026-08-14, PR #50–#76 loop)

### 1. Token (never printed)

```python
cred = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                      capture_output=True, text=True, cwd=repo)
token = next(l.split('=', 1)[1] for l in cred.stdout.splitlines() if l.startswith('password='))
```

### 2. Create PR

```python
POST https://api.github.com/repos/{owner}/{repo}/pulls
{"title": "...", "head": branch, "base": "main", "body": "..."}
```

### 3. Wait for CI + verify by jobs API, then merge with expected_head_sha

- Sleep ~175s (canonical-verify-v4 takes ~3min), then check **actions/runs** filtered by branch.
- **The check-run aggregation can be stale/unstable** — trust the **latest workflow run's `conclusion`** via `GET actions/runs?per_page=3&branch=<branch>`, not the PR `mergeable_state` (`unstable` is a check-run aggregation race).
- Merge with `expected_head_sha` to force the exact head:

```python
PUT /repos/{owner}/{repo}/pulls/{n}/merge
{"merge_method": "squash", "expected_head_sha": head_sha}
```

## Branch cleanup (squash-merge makes git ancestry unreliable)

- `git branch --merged main` and `merge-base --is-ancestor` **lie** for squash-merged PR branches (their commits are not in main history).
- Authoritative check: `GET /repos/{owner}/{repo}/pulls?state=closed&per_page=100` → `merged_at` non-null + `head.ref` match = safe to delete.
- Delete: `DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}` (batch, ~0.15s sleep between).
- Keep branches whose PR was **not merged** (e.g. superseded PR #51) as historical evidence.
- `git fetch --prune` only clears local refs of **remote-deleted** branches — cannot remove remote branches that still exist.

## Pitfalls

- **force-pushed (rebased) branch head can wedge the PR check rollup on shallow-clone CI runners**: the push-event run computes `git diff <BEFORE_SHA>..<HEAD>`, but the rewritten pre-force SHA is not fetched on the runner -> `fatal: bad object <sha>` -> gate-plan fails -> `mergeStateStatus=BLOCKED` stays for a long time even after a new head's PR-event run is green. **Fix: add one more plain (non-force) commit on the branch** so the next push-event run has a reachable BEFORE_SHA; the new run supersedes the wedged aggregation. Avoid force-push on branches that already have a live PR when the CI runner uses shallow clones. (WORK-LAB 2026-09-25: #132 rebase 54add19->e025772 wedged; appended real commit b98b23f -> CLEAN. #133 rebase onto 8044fb1 same wedge; appended 80cfd16 -> CLEAN.)
- `gh pr merge --match-head-commit` requires the FULL 40-char SHA; a short 7-char SHA fails with `Could not coerce value "..." to GitObjectID`. Get it via `gh pr view N --json headRefOid --jq .headRefOid`.
- Older `gh` versions: `gh api` does NOT accept `--repo` — pass the full endpoint path: `gh api repos/OWNER/REPO/branches --jq .[].name`.
- **GitHub does NOT auto-delete head branches on merge** (unless auto-delete enabled) — 50+ leftovers accumulate; clean periodically.
- **Anonymous API rate limit 60/hr** — authenticate every repeated call.
- **api.github.com direct, NOT the push proxy**; fetch/push via SSH or `http.proxy=127.0.0.1:7890` for git protocol.
- After merge: `git fetch origin main && git reset --hard origin/main` (destructive — only when working tree is clean and changes committed).
- Verify双端一致: local HEAD == origin/main == merge response sha.
