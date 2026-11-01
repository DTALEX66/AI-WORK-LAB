---
name: github-issues
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/github/github-issues/SKILL.md
---

---
name: github-issues
description: "Create, triage, label, assign GitHub issues via gh or REST."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Issues, Project-Management, Bug-Tracking, Triage]
    related_skills: [github-auth, github-pr-workflow]
---

# GitHub Issues Management

Create, search, triage, and manage GitHub issues. Each section shows `gh` first, then the `curl` fallback.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Inside a git repo with a GitHub remote, or specify the repo explicitly

### Setup

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

## 1. Viewing Issues

**With gh:**

```bash
gh issue list
gh issue list --state open --label "bug"
gh issue list --assignee @me
gh issue list --search "authentication error" --state all
gh issue view 42
```

**With curl:**

```bash
curl -s \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&per_page=20" \
  | python3 -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:
        labels = ', '.join(l['name'] for l in i['labels'])
        print(f\"#{i['number']:5}  {i['state']:6}  {labels:30}  {i['title']}\")"
```

## 2. Creating Issues

**With gh:**

```bash
gh issue create --title "Describe the issue" --body-file issue-body.md
```

Use a descriptive title, reproduction steps, expected behavior, actual behavior, and environment. Confirm the target repository before creating a remote issue.

## 3. Managing Issues

```bash
# Labels and assignment
gh issue edit 42 --add-label "priority:high,bug"
gh issue edit 42 --remove-label "needs-triage"
gh issue edit 42 --add-assignee @me

# Comment, close, reopen
gh issue comment 42 --body "Investigated — root cause is being tracked."
gh issue close 42
gh issue reopen 42
```

Equivalent REST operations require authenticated `gh api` or an already-approved API client. Never put credentials in a URL, shell argument, file, or issue body.

## 4. Issue Triage Workflow

When asked to triage issues:

1. List open issues with the agreed triage label.
2. Read and categorize each issue.
3. Apply labels and priority only with explicit remote-write scope.
4. Assign only when the owner is clear.
5. Comment with concise triage evidence.
6. Link a fix through `Closes #N`, `Fixes #N`, or `Resolves #N` only when the PR actually closes it.

## 5. Safety Boundary

- Listing and reading issues is read-only.
- Creating, editing, commenting, assigning, labeling, closing, and reopening issues are remote writes.
- Ask for explicit authorization before those writes.
- Never read `.env`, credential files, OAuth stores, browser data, or token values.
- Do not bulk-edit issues without a bounded list and a reversible plan.

## Quick Reference

| Action | gh |
|---|---|
| List issues | `gh issue list` |
| View issue | `gh issue view N` |
| Create issue | `gh issue create --title ... --body-file ...` |
| Add labels | `gh issue edit N --add-label ...` |
| Assign | `gh issue edit N --add-assignee ...` |
| Comment | `gh issue comment N --body ...` |
| Close | `gh issue close N` |
| Search | `gh issue list --search ...` |
