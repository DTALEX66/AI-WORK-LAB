# Codex Desktop audit publication pattern

Use this pattern when a repository documents a desktop/CLI configuration audit whose live state is outside the repository.

## Evidence boundary

Publish:

- official documentation URLs and the supported configuration model;
- repository search results showing whether project files override the tool;
- redacted command outcomes such as config parse status, login-status classification, and Doctor pass/fail summaries;
- exact version/package identity when needed to explain an alpha/stable boundary;
- verified fixes, hypotheses, and pending reboot/UI checks as separate categories.

Do not publish or copy:

- auth files, tokens, cookies, browser databases, Local Storage contents, private keys, or user-profile backups;
- private live paths when a generic `~/.tool/config.toml` form is sufficient;
- a local configuration backup created for rollback.

## Minimal publication sequence

1. Read the existing error-summary document and record the clean starting branch.
2. Check the repository for project-level config/env/wrapper overrides before blaming the workflow.
3. Apply a user-level fix only after explicit authorization; use backup, parse-before-write, staging, atomic replacement, and readback.
4. Document the live fix as local evidence, not as a repository change.
5. Add a repository-local summary with official URLs and a clear verification boundary.
6. Run `git diff --check`, the canonical quality gate, and a staged-tree review.
7. Commit only the intended documentation/config-source files; keep external backups and ignored artifacts out of Git.
8. Push and open a PR. A request to upload does not authorize merging.
9. Verify `gh pr view` reports the expected `headRefOid`, and `gh run view` reports that same `headSha` for every required Linux/Windows job.

## Truthful status vocabulary

- **Applied and verified:** local config readback or Doctor confirms the exact change.
- **Current-session verified:** login/network works now; this does not prove cold-boot persistence.
- **Pending reboot/UI verification:** Desktop or startup behavior has not yet been tested after restart.
- **Pushed:** remote branch contains the commit.
- **PR open:** GitHub review object exists and exact-head checks pass.
- **Merged:** only say this after a separately authorized merge and exact merge-SHA main-branch verification.
