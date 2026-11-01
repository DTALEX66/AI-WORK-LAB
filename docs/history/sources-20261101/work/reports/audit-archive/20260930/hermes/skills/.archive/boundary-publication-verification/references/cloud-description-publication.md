# Cloud/public description publication reference

Use this when a user asks to update all GitHub-facing descriptions, summarize errors, or align repository metadata with a merged governance change.

## Public surface

Treat these as one synchronized surface:

- repository description: `gh repo view OWNER/REPO --json description,url`;
- README and project-definition/architecture entrypoints;
- troubleshooting and class-level error-summary docs;
- existing merged PR body when historical correction is authorized;
- new documentation PR body and its exact-SHA CI evidence.

Do not change topics, rulesets, repository settings, or workflow/runtime versions unless separately requested.

## Safe sequence

1. Read current local docs and current GitHub metadata/PR bodies.
2. Write one canonical identity and explicitly separate completed evidence, non-blocking upstream warnings, and unverified coverage.
3. Remove stale/unsafe examples: plaintext secret writes, default global config mutation, fixed user-profile paths, and unapproved credential handling.
4. Do not hardcode an arbitrary Node/action/runtime choice to silence an upstream annotation. Record it as an upstream warning and preserve the existing reproducible CI contract.
5. Run `git diff --check`, security/documentation scans, affected tests, and the canonical quality gate when governance or release claims change.
6. Commit and push repository docs through a normal PR. Verify required checks against the PR head SHA, not merely a similarly named or older run.
7. Merge only after required checks pass. Read back the merge SHA and main-branch workflow; require `headSha == mergeSha`, successful required jobs, and the exact workflow/run/attempt/job identifiers.
8. Read back repository description and PR bodies; verify `git rev-parse HEAD == git rev-parse origin/main` and a clean tree.

## Evidence language

Use exact identifiers only when read back from GitHub. Do not claim all unknown external projects are validated merely because local tests, portable install, sample bootstrap projects, or CI passed. Never include credentials, auth stores, tokens, private keys, cookies, session data, or private live paths.
