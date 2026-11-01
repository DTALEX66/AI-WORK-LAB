---
name: cloud-delivery-boundary-closure
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/cloud-delivery-boundary-closure/SKILL.md
---

---
name: cloud-delivery-boundary-closure
description: "Use when closing project data boundaries and cloud delivery."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [cloud-delivery, pull-request, ci, project-boundary, windows, containment]
    related_skills: [github-pr-workflow, project-data-boundary, agent-workflow-fortress]
---

# Cloud Delivery and Project Boundary Closure

## Purpose

Use this class-level workflow when a repository task combines two promises that are easy to confuse:

- project-owned code, tests, runtime data, caches, and desktop profiles must stay inside the agreed project boundary; and
- a verified change must become visible in the cloud repository's default-branch view or connected code index.

A feature-branch push is not cloud-delivery closure. A local test pass is not boundary closure. Close both evidence chains independently.

## Operating principles

1. Establish the live Git root, branch, remote, default branch, and user-requested scope before editing.
2. Classify ownership before moving or deleting anything. Same-name paths are not proof of ownership.
3. Keep project-generated data in the project's ignored runtime root, normally `<project>/.hermes/task-runtime/`.
4. Preserve Hermes, Gateway, authentication, browser, session, scheduler, and other shared workflow state unless the user explicitly names an exact owned path and action.
5. Never call a feature branch “visible from the repository” until the default branch or the explicitly selected connected branch has been updated and read back.
6. Treat every external write, move, delete, commit, push, PR, and merge as a separate auditable action.

## Phase A — Discover and classify

1. Run `git status --short`, `git branch --show-current`, `git remote -v`, and resolve the default branch from the remote API.
2. Read the repository rules and locate the runtime/path resolver, test bootstrap, desktop runtime resolver, ignore rules, and existing boundary tests.
3. For each path outside the repository, record only safe metadata: absolute path, type, file count, size, newest modification time, Git root/remote/dirty state if applicable, and active-process evidence. Do not read credentials, cookies, browser databases, or secret values.
4. Classify each candidate as:
   - current project-owned data/temporary output;
   - external software, SDK, portable tool, or shared configuration;
   - Hermes/Gateway/shared workflow infrastructure;
   - a different repository or ambiguous user data;
   - regenerable cache; or
   - credential/private data that must not be uploaded.
5. A same-name old repository with a different remote or dirty worktree is not safe to treat as the current project. Preserve and report it pending an exact-path ownership decision.

## Phase B — Close the Windows project-data boundary

1. Put test/runtime outputs under ignored project paths such as `.hermes/task-runtime/tmp`, `pytest-tmp`, `pycache`, `cache`, `logs`, and `artifacts`.
2. On Windows, setting `TMP`, `TEMP`, and `TMPDIR` alone may not move pytest `tmp_path`: Python `tempfile` can cache the user Temp root before test fixtures execute. In the real test bootstrap, set all three variables, explicitly set `tempfile.tempdir`, and set `PYTHONPYCACHEPREFIX` to the project pycache path.
3. Add a regression test asserting that `tempfile.gettempdir()`, pytest `tmp_path`, and bytecode cache paths are descendants of the project runtime root.
4. Verify the regression RED before the fix and GREEN after the fix. Run the full test suite afterward.
5. After all test processes exit, rescan `%LOCALAPPDATA%\Temp` for project markers. Clean only exact directories proven to belong to the closed project run. If Windows read-only attributes block deletion, retry with an `onerror` handler that restores write permission, then rescan the exact prefix; never report a failed deletion as success.
6. For project-specific AppData/WebView profiles, verify runtime source code points to the project target, the target exists, no active process uses the old path, and the old path has no recent writes. Only then remove the exact stale source; do not blindly copy browser profiles or cookies into the repository.

## Phase C — Close cloud delivery

When the user requests “上传云端”, “更新仓库描述”, or an equivalent outcome that must be visible to a connected repository reader:

1. Finish the complete verified change set. Do not open a PR from an earlier commit while current verified WIP remains uncommitted.
2. Scan the intended files for secrets, credentials, `.env`, auth/session files, databases, caches, installers, and private user data. Stage explicit paths only.
3. Run the relevant local gates and record real output: tests, lint, architecture/convention checks, packaging/runtime smoke, and exact changed-file checks.
4. Commit and push the feature branch. Verify local HEAD equals `origin/<branch>` and the worktree is clean.
5. Create a PR against the repository default branch. Record the PR number, head SHA, base SHA, and URL.
6. Wait for CI and inspect the actual check runs. A local pass does not replace CI. A PR in `UNSTABLE`, `PENDING`, or `FAILURE` is not merge-ready.
7. Merge only when CI is green and merge authorization is clear. If authorization to merge is ambiguous, stop after creating the PR and report the exact pending decision.
8. After merge, read back the default branch SHA and key files through the GitHub API. Only then claim that default-branch readers or connected code indexes can see the update. Allow for connector/index cache delay and distinguish it from branch visibility.

### Cross-repository cutover guard

When source and target are different repositories, keep separate absolute checkout paths and verify `git rev-parse --show-toplevel` plus `git remote -v` in the target checkout immediately before every target commit/push. A target refspec executed from the source checkout is a routing error even if Git safely rejects it. “Push to the repository” means feature-branch upload by default; do not infer main-branch promotion or merge authorization unless the user explicitly says so. If main promotion is explicitly authorized, require a fast-forward push and read back both the feature ref and `refs/heads/main`.

For an ignored/untracked source subtree, inspect the target tree first and create an explicit source→target crosswalk. Record a non-secret file-level SHA-256 manifest, classify ignore rules with `git check-ignore -v`, force-add only the intended audited prefixes, run target tests, then re-check for test-generated mutations before committing. Delete the exact source prefix only after remote exact-SHA/tree readback succeeds; rescan the prefix and remove an empty parent only after confirming it contains no other content. See `references/cross-repository-cutover.md`.

## Verification checklist

- [ ] Current Git root, branch, remote, and default branch recorded
- [ ] External paths classified without reading secrets
- [ ] Project test/temp/pycache paths proven inside ignored runtime
- [ ] Boundary regression observed RED then GREEN
- [ ] Closed-run external temp directories removed only by exact ownership
- [ ] Stale AppData profile cleanup proved by code target, process, and recency evidence
- [ ] Full local test and static gates pass
- [ ] Explicit staging and clean worktree verified
- [ ] Branch push read back by SHA
- [ ] PR exists with correct base/head SHAs
- [ ] CI status read back
- [ ] Default branch read back after merge before claiming cloud visibility

## Common failure modes

- “Push succeeded” mistaken for “main is updated”.
- Repository description updated while repository files remain on an unmerged branch.
- PR created from a stale commit while dirty verified fixes remain local.
- `TMP` variables set but pytest `tmp_path` still uses `%TEMP%` because `tempfile.tempdir` was cached.
- Same-name old repo deleted even though its remote differs or its worktree is dirty.
- WebView2/AppData profile deleted without checking active process use or authoritative D-drive target.
- CI pending or unstable reported as green because local tests passed.

See `references/windows-cloud-closure-2026-07.md` for a compact reproduction and evidence pattern from a Windows repository boundary repair.
