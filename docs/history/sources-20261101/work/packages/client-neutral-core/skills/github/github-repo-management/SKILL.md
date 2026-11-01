---
name: github-repo-management
description: "Clone/create/fork repos; manage remotes, releases."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Repositories, Git, Releases, Secrets, Configuration]
    related_skills: [github-auth, github-pr-workflow, github-issues]
---

# GitHub Repository Management

Create, clone, fork, configure, and manage GitHub repositories. Each section shows `gh` first, then the `git` + `curl` fallback.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Confirmed target owner/repository and local destination before writes

## 1. Cloning Repositories

```bash
git clone https://github.com/owner/repo-name.git
git clone --depth 1 https://github.com/owner/repo-name.git ./repo-name
git clone --branch develop https://github.com/owner/repo-name.git
git clone git@github.com:owner/repo-name.git
```

Do not embed credentials in a remote URL. If a global HTTPS→SSH rewrite may cause a one-off clone to hang, use a clean, credential-free Git configuration for that single command and verify the destination afterward.

On POSIX shells:
```bash
GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 git clone https://github.com/owner/repo-name.git ./repo-name
```

On Windows PowerShell:
```powershell
$env:GIT_CONFIG_GLOBAL = 'NUL'
$env:GIT_TERMINAL_PROMPT = '0'
git clone https://github.com/owner/repo-name.git ./repo-name
Remove-Item Env:GIT_CONFIG_GLOBAL, Env:GIT_TERMINAL_PROMPT
```

With `gh`:

```bash
gh repo clone owner/repo-name
```

## 2. Creating and Forking Repositories

These are remote writes and require explicit authorization:

```bash
gh repo create my-new-project --private --clone
gh repo fork owner/repo-name --clone
```

Before creating or forking, confirm visibility, owner, local path, and whether a remote push is intended.

## 3. Repository Information

Read-only examples:

```bash
gh repo view owner/repo-name
gh repo list --limit 20
gh search repos "query" --language python --sort stars
```

## 4. Remotes and Fork Sync

```bash
git remote -v
git remote get-url origin
git remote add upstream https://github.com/owner/repo-name.git
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

Do not change a project's remote or push a fork without explicit authorization. Check `git status`, branch, and remote URLs before and after.

## 5. Releases and Actions

Release publication and workflow operations are remote writes:

```bash
gh release list
gh release view v1.0.0
gh workflow list
gh run list --limit 10
gh run view <RUN_ID> --log-failed
```

Create or rerun a release/workflow only after verifying the exact commit SHA, target repository, and rollback plan. Never handle GitHub secret values through this skill; use the official interactive GitHub secret flow and report only names/status.

## 6. Global Workflow Safety Boundary

- Never read `.env`, auth.json, credential stores, OAuth files, browser data, SSH private keys, or token values.
- Never put credentials in URLs, command arguments, logs, issue bodies, or repository files.
- Keep project-generated artifacts under `<project>/.hermes/task-artifacts/`.
- Treat clone/create/fork/remote/release/push/settings/Actions operations as separate, explicit side effects.
- Verify remote writes by reading back the repository/PR/release identifier and exact commit SHA.

## Quick Reference

| Action | Command |
|---|---|
| Clone | `gh repo clone owner/repo` |
| Create repo | `gh repo create name --private --clone` |
| Fork | `gh repo fork owner/repo --clone` |
| Repo info | `gh repo view owner/repo` |
| Releases | `gh release list` |
| Workflows | `gh workflow list` |
| CI run | `gh run view RUN_ID --log-failed` |
