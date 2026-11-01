---
name: github-pr-workflow
description: "GitHub PR lifecycle: branch, commit, open, CI, merge."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Pull-Requests, CI/CD, Git, Automation, Merge]
    related_skills: [github-auth, github-code-review]
---

# GitHub Pull Request Workflow

Complete guide for managing the PR lifecycle. Local Git operations work without
`gh`; GitHub API operations (PR creation, checks, review, and merge) require an
authenticated `gh` client or another explicitly approved client. This skill does
not provide an unauthenticated curl fallback and never extracts credentials.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Inside a git repository with a GitHub remote

### Quick Auth Detection

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="none"
  # Fail closed: never read .env/.git-credentials or extract tokens.
  # Local Git work may continue; stop before GitHub API writes and ask the user
  # to authenticate with the supported `gh auth login` flow.
fi
```

## 1. Branch Creation

```bash
git fetch origin
git checkout main && git pull origin main
git checkout -b feat/description
```

Branch naming conventions:

- `feat/description` — new features
- `fix/description` — bug fixes
- `refactor/description` — code restructuring
- `docs/description` — documentation
- `ci/description` — CI/CD changes

## 2. Making Commits

Use the agent's file tools to make changes, then inspect the staged tree:

```bash
git add <explicit-files>
git diff --cached --stat
git write-tree
git commit -m "type(scope): short description"
```

Do not stage credentials, runtime state, generated caches, or unrelated files.

## 3. Push and Create a PR

Pushing and PR creation are remote writes and require explicit user authorization:

```bash
git push -u origin HEAD
gh pr create --title "Change summary" --body-file pr-body.md
```

The PR body should state the scope, tests, risk, rollback, and exact candidate commit SHA.

## 4. Monitor CI Status

```bash
gh pr checks
gh pr checks --watch
gh run list --branch "$(git branch --show-current)" --limit 5
gh run view <RUN_ID> --log-failed
```

For this repository, only the exact commit SHA's required workflow and job results count as release evidence. Old or similarly named runs do not satisfy the gate.

## 5. Review and Fix CI

1. Identify the exact failing run, attempt, workflow, and job.
2. Read only the relevant failure logs.
3. Write a regression test first when behavior changes.
4. Fix the smallest root cause.
5. Rerun local tests and quality gates.
6. Rebuild the staged tree; previous review evidence is invalid after edits.
7. Push the new commit and verify its exact-SHA CI.

## 6. Merge

Merge is a separate remote write. Only merge after required checks, review, branch protection, and the target commit identity are verified:

```bash
gh pr merge <NUMBER> --squash
```

Never enable auto-merge or merge a PR merely because a local test passed.

## 7. Complete Workflow Checklist

- [ ] Clean starting tree and correct base branch
- [ ] Task scope and allowed paths recorded
- [ ] RED regression test observed when behavior changes
- [ ] Local tests and quality gate pass
- [ ] Staged tree reviewed and `git write-tree` recorded
- [ ] Remote write explicitly authorized
- [ ] PR checks verified for the exact commit SHA
- [ ] Merge decision separately authorized
- [ ] Post-merge SHA and branch state verified

## Safety Boundary

Never read `.env`, auth.json, credential stores, OAuth files, browser data, SSH private keys, or token values. Do not use `--yolo`, `--admin`, force-push, destructive reset, or auto-merge as a shortcut. Keep all temporary logs and review artifacts under the target project's `.hermes/task-artifacts/`.
