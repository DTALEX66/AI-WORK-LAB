# Upload / Commit Workflow for Portable Packs

Companion reference for `agent-workflow-fortress`. Read when the user says
"上传" for a workflow pack, or when preparing a portable pack for remote
delivery.

## Upload sequence

When the user says "上传" for a workflow pack, complete the remote delivery rather than stopping after local fixes:

1. Inspect branch, remote, local-vs-origin HEAD, tracked diff, untracked files, ignored generated files, and unusual file sizes.
2. Scan candidate files for forbidden artifacts (`.env`, `auth.json`, databases, installers, binaries, caches) and obvious token/API-key patterns before staging.
3. Run repo validation: syntax checks, YAML/frontmatter checks, prompt/rule security scanner, wrapper smoke tests, workflow doctor, MCP smoke, and provider smoke where available.
4. Fetch/rebase before the **final** review. After conflict resolution, regenerate tracked bundles/assets from merged source and rerun the canonical verification.
5. Stage only intended portable assets, then inspect both `git diff --cached --name-status` and porcelain status. Treat `RM`/`MM`, rename-only index entries with unstaged target edits, or untracked package files as an incomplete candidate: do not commit until each logical slice is fully staged. Re-run staged forbidden-file and whitespace checks, then record the candidate tree ID (`git write-tree`).
6. Dispatch independent review against that exact tree and **wait for the asynchronous verdict**. Any rebase, rebuild, edit, or amend invalidates the verdict and requires re-review.
7. Commit only the reviewed tree. Push, fetch, and verify local HEAD equals `origin/<branch>`; finish with the commit SHA and clean/dirty status.

## Python/FastAPI release-candidate additions

For Python/FastAPI release candidates, additionally verify sidecar authentication, dashboard allowlists, secret/config fail-closed rules, restore maintenance isolation, non-root containers, package-qualified imports, console-entry collisions, clean dependency/wheel/CLI proofs, runtime-root checks, and environment normalization after background review fixtures.
