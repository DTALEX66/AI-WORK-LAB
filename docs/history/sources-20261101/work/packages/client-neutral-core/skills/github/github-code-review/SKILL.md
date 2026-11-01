---
name: github-code-review
description: "Review PRs: diffs, inline comments via gh or REST."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Code-Review, Pull-Requests, Git, Quality]
    related_skills: [github-auth, github-pr-workflow]
---

# GitHub Code Review

Perform code reviews on local changes before pushing, or review open PRs on GitHub. Most of this skill uses plain `git`; PR-level reads and writes require an authenticated `gh` client or another explicitly approved client. This skill never constructs or extracts credentials for a curl fallback.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Inside a git repository

### Setup (for PR interactions)

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="none"
  # Fail closed: never read .env/.git-credentials or extract tokens.
  # Ask the user to authenticate with the supported `gh auth login` flow.
fi

REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\\.com[:/]||; s|\\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

In Windows PowerShell, use the equivalent parsing before running a REST example:

```powershell
$REMOTE_URL = git remote get-url origin
$OWNER_REPO = $REMOTE_URL -replace '^.*github\.com[:/]', '' -replace '\.git$', ''
$OWNER, $REPO = $OWNER_REPO -split '/', 2
```

The `curl` snippets below use POSIX shell syntax; on Windows run them in Git
Bash, or prefer the cross-platform `gh` commands.

---

## 1. Reviewing Local Changes (Pre-Push)

This is pure `git` — works everywhere, no API needed.

### Get the Diff

```bash
# Staged changes (what would be committed)
git diff --staged

# All changes vs main (what a PR would contain)
git diff main...HEAD

# File names only
git diff main...HEAD --name-only

# Stat summary (insertions/deletions per file)
git diff main...HEAD --stat
```

### Review Strategy

1. **Get the big picture first:**

```bash
git diff main...HEAD --stat
git log main..HEAD --oneline
```

2. **Review file by file** — use `read_file` on changed files for full context, and the diff to see what changed:

```bash
git diff main...HEAD -- src/auth/login.py
```

3. **Check for common issues:**

```bash
# Debug statements, TODOs, console.logs left behind
git diff main...HEAD | grep -n "print(\\|console\\.log\\|TODO\\|FIXME\\|HACK\\|XXX\\|debugger"

# Large files accidentally staged
git diff main...HEAD --stat | sort -t'|' -k2 -rn | head -10

# Secrets or credential patterns
git diff main...HEAD | grep -in "password\\|secret\\|api_key\\|token.*=\\|private_key"

# Merge conflict markers
git diff main...HEAD | grep -n "<<<<<<\\|>>>>>>\\|======="
```

4. **Present structured feedback** to the user.

### Review Output Format

```
## Code Review Summary

### Critical
- **src/auth.py:45** — SQL injection: user input passed directly to query.
  Suggestion: Use parameterized queries.

### Warnings
- **src/models/user.py:23** — Password stored in plaintext. Use bcrypt or argon2.
- **src/api/routes.py:112** — No rate limiting on login endpoint.

### Suggestions
- **src/utils/helpers.py:8** — Duplicates logic in `src/core/utils.py:34`. Consolidate.
- **tests/test_auth.py** — Missing edge case: expired token test.

### Looks Good
- Clean separation of concerns in the middleware layer
- Good test coverage for the happy path
```

---

## 2. Reviewing a Pull Request on GitHub

### View PR Details

**With gh:**

```bash
gh pr view 123
gh pr diff 123
gh pr diff 123 --name-only
```

**With git + curl:**

```bash
PR_NUMBER=123

# Get PR details
curl -s \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER \
  | python3 -c "
import sys, json
pr = json.load(sys.stdin)
print(f\"Title: {pr['title']}\")
print(f\"Author: {pr['user']['login']}\")
print(f\"Branch: {pr['head']['ref']} -> {pr['base']['ref']}\")
print(f\"State: {pr['state']}\")
print(f\"Body:\\n{pr['body']}\")"

# List the complete changed-file set (authenticated and paginated)
gh api --paginate "repos/$OWNER/$REPO/pulls/$PR_NUMBER/files?per_page=100" \
  --jq '.[] | "\(.status) +\(.additions) -\(.deletions)  \(.filename)"'
```

The curl details example above is a read-only convenience for public metadata;
never treat a single default-page response as a complete changed-file review.

### Check Out PR Locally for Full Review

This works with plain `git` — no `gh` needed:

```bash
# Fetch the PR branch and check it out
git fetch origin pull/123/head:pr-123
git checkout pr-123

# Now you can use read_file, search_files, run tests, etc.

# View diff against the base branch
git diff main...pr-123
```

**With gh (shortcut):**

```bash
gh pr checkout 123
```

### Leave Comments on a PR

**General PR comment — with gh:**

```bash
gh pr comment 123 --body "Overall looks good, a few suggestions below."
```

**Without `gh`:**

Do not send an unauthenticated HTTP request. Stop and ask the user to authenticate
`gh` or provide an already-approved GitHub client; never put a token in a URL,
command argument, file, or request body.

### Submit a Formal Review

**With gh:**

```bash
gh pr review 123 --approve --body "LGTM!"
gh pr review 123 --request-changes --body "See inline comments."
gh pr review 123 --comment --body "Some suggestions, nothing blocking."
```

Only submit a review after reading the exact PR diff and checking the target commit SHA.

---

## 3. Review Checklist

When performing a code review (local or PR), systematically check:

### Correctness
- Does the code do what it claims?
- Edge cases handled (empty inputs, nulls, large data, concurrent access)?
- Error paths handled gracefully?

### Security
- No hardcoded secrets, credentials, or API keys
- Input validation on user-facing inputs
- No SQL injection, XSS, or path traversal
- Auth/authz checks where needed

### Code Quality
- Clear naming and focused functions
- No unnecessary complexity or premature abstraction
- No duplicated logic that should be consolidated

### Testing
- New code paths tested
- Happy path and error cases covered
- Tests readable and maintainable

### Documentation
- Public APIs documented
- README updated if behavior changed

---

## 4. Pre-Push Review Workflow

When the user asks to review code before pushing:

1. Inspect branch, remote, status, staged diff, and `git write-tree`.
2. Read the full changed-file diff and relevant surrounding code.
3. Run the narrowest tests, then the project quality gate.
4. Apply the checklist above.
5. Report Critical / Warnings / Suggestions / Looks Good.
6. Never approve, push, or merge merely because tests pass; those are separate user-authorized actions.

## 5. Safety Boundary

Never read `.env`, credential stores, OAuth files, SSH private keys, browser data, or token values while reviewing a repository. Never post a GitHub review or comment without explicit user authorization for that remote write.
