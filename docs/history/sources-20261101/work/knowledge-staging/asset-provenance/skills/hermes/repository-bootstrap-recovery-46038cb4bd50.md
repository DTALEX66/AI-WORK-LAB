---
name: repository-bootstrap-recovery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/github/repository-bootstrap-recovery/SKILL.md
---

---
name: repository-bootstrap-recovery
description: "Use for slow GitHub checkout bootstrap."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [github, git, clone, bootstrap, snapshot, recovery, windows]
    related_skills: [github-repo-management, project-data-boundary, audited-project-delivery]
---

# Repository Bootstrap and Transport Recovery

## Purpose

Use this class-level skill when a user gives a GitHub repository and a local destination, especially for a new/empty checkout, a monorepo with project rules, or a repository whose normal Git transport is slow. The deliverable is a verified local working tree, not a claim that a command merely started.

## Safety and scope

1. Confirm the exact owner/repository, branch, local destination, and whether the destination is empty or contains user work.
2. Inspect remote metadata and tree contents read-only before writing. Look for root and module `AGENTS.md`, `CLAUDE.md`, `.hermes.md`, README, `.gitignore`, and governance files.
3. Never read or print credentials, `.env`, auth stores, private keys, browser data, tokens, prompts, or response bodies. Do not access protected volumes unless the user explicitly names an exact path and operation.
4. Treat clone/fetch, snapshot extraction, Git initialization, remote configuration, commit, and push as separate side effects. Never push or overwrite a non-empty local destination without explicit scope.
5. Keep temporary archives and extraction scratch under the owning project's ignored runtime boundary, then remove only the exact transient files after verification.

## Standard sequence

### 1. Discover and load rules

- Verify the remote exists and identify the authoritative branch and current remote commit SHA using `gh repo view` / read-only API calls.
- Read the remote tree before cloning when the local directory is empty or the repository is large. Load root rules first, then module rules; module rules may narrow but never weaken root rules.
- Determine whether local project context will be auto-discovered after checkout. Do not assume a parent/home rule file applies if the project context contract says cwd-only or Git-root-bounded discovery.

### 2. Attempt the normal path once

- Use an explicit destination and branch.
- On Windows/Git-Bash, quote paths containing spaces and use a credential-free URL. Read back `git status`, branch, HEAD, and remote URLs after completion.
- If a global HTTPS→SSH rewrite can redirect the URL unexpectedly, inspect the effective URL and use a one-command clean Git config only when needed; never embed credentials in the URL.
- Do not repeatedly restart a full-history transfer while the same pack is progressing slowly. Observe progress and preserve failure evidence.

### 3. Transport fallback ladder

Choose the least-lossy working fallback:

1. **Shallow Git fetch/clone**: use `--depth=1` when current files are sufficient and history is not required immediately.
2. **Official codeload snapshot**: use `https://codeload.github.com/OWNER/REPO/tar.gz/refs/heads/BRANCH` when Git pack transport remains throttled. Extract only after download success; reject path traversal, absolute paths, symlinks/reparse points, and unexpected archive layout.
3. **Local repository reconstruction**: if the snapshot is the only viable path, initialize a local Git repository on the requested branch, add the verified snapshot, and create an explicitly named import/snapshot commit. Never claim this commit equals the remote commit SHA. Preserve the remote URL and record that history objects are absent.

Use the exact recovery recipe in [`references/slow-git-snapshot-recovery.md`](references/slow-git-snapshot-recovery.md).

### 4. Verify the resulting checkout

A successful bootstrap requires all applicable checks:

- root and module rule files exist;
- required root files and expected module roots exist;
- `git status --porcelain` is empty after the import commit or checkout;
- branch name is explicit and remote URL is read back;
- `git diff --check` passes;
- structural/security/governance checks run from the exact module or repository path and their exit codes are captured;
- local HEAD and remote HEAD are reported separately when a snapshot/import commit was used;
- archive, temporary extraction files, and interrupted Git pack scratch are not left in the project source tree.

Structural checks prove local integrity only. They do not prove remote history parity, CI, publication, or deployment.

## Claim discipline

Use precise labels:

- `REMOTE_HEAD_RESOLVED`: authoritative branch SHA read from GitHub;
- `LOCAL_CHECKOUT_MATCHES_TREE`: current file tree verified against the downloaded branch snapshot;
- `LOCAL_GIT_INITIALIZED`: local repository exists and is clean;
- `HISTORY_AVAILABLE`: remote history objects are present locally;
- `LOCAL_CHECKS_PASS`: local structural/security/tests passed.

A codeload import normally proves the first, second, third and fifth labels, but not `HISTORY_AVAILABLE`. Do not report “pulled full repository history” unless `git rev-parse` and the remote refs prove it.

## Pitfalls

- Do not confuse a remote tree listing with a local checkout; a read-only API response is not a pull.
- Do not report a timed-out or background fetch as complete merely because it is still running.
- Do not use broad `rm -rf`, `git clean -fdx`, reset, or force-push operations to recover an interrupted transfer. Remove only a confirmed incomplete transfer directory or exact project-local scratch file, and preserve user work.
- Do not silently convert a full clone into a snapshot. State the loss of history and offer `git fetch --unshallow` as a later operation.
- Do not use a locally generated import SHA as evidence for exact-SHA CI or as proof of the cloud commit.
- Normal Windows LF→CRLF warnings during `git add` are cosmetic; report them separately from functional failures.

## References

- [`references/slow-git-snapshot-recovery.md`](references/slow-git-snapshot-recovery.md) — reproducible fallback ladder, archive safety, and verification matrix.
