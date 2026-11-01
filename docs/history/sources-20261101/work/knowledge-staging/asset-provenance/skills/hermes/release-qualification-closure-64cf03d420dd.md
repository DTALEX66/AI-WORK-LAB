---
name: release-qualification-closure
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/release-qualification-closure/SKILL.md
---

---
name: release-qualification-closure
description: "Use for exact-SHA release qualification."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [release, qualification, exact-sha, installer, provenance, checksums]
    related_skills: [exact-sha-ci-delivery, frozen-release-verification, desktop-build-verification]
---

# Release Qualification Closure

## Purpose

Use this class-level skill when a project must prove a release candidate end to end: exact source identity, full qualification, desktop/installer construction, asset integrity, artifact identity, and draft/public Release readback. It prevents a local green test or selective CI run from being promoted into a release claim.

## Release-gate evidence contract (fail closed)

A release gate that checks only a human acceptance marker is bypassable: an
operator could write `DL-REL-001: ACCEPTED` while capability evidence is still
below its declared floor and every Evidence Card remains `not-run`. The release
gate must independently validate:

1. Every capability's `actualEvidence` is at least its authoritative
   `minimumRequiredEvidence`; emit one finding per deficit.
2. The complete Evidence Card set exists, human calibration is finished, and
   every card is authoritative/accepted. Card presence or a
   `human_calibration_required` flag is not acceptance evidence.
3. The human acceptance marker is checked separately and cannot satisfy either
   evidence condition.
4. Pure helper tests cover floor comparison, card-state comparison, malformed
   input, and the negative case where the acceptance marker exists but the gate
   remains blocked.
5. After every commit that changes HEAD, including docs-only commits, rerun any
   canonical aggregate that writes a HEAD-bound marker before invoking the
   release gate. A stale marker is a freshness failure, never a reason to reuse
   the previous green result.

The compact implementation checklist and validated output interpretation are in
[`references/release-gate-evidence-contract.md`](references/release-gate-evidence-contract.md).

### Structural evidence promotion without overclaiming

When a capability is below its minimum only because its repository artifacts
lack a deterministic structural verifier, inspect the actual records first. If
counts, schemas, unique IDs, safety markers, and cross-file cardinality really
pass, add a small standalone verifier, add a regression test for its exact
summary, and include it in the canonical aggregate. Promote only the structural
floor (for example E0 -> E1); keep source provenance, live runtime, human Jury,
preference tests, and production evidence explicitly pending. Update every
current SSOT that declares the level (detailed evidence index, capability
status, human-readable index, and roadmap); historical reports remain
reference-only. A structural pass is evidence for that floor, never a shortcut
to E2/E3.

### Keep ordinary CI green while making release qualification fail closed

Do not add a currently-unmet human/production release gate as a required step of
the ordinary push/PR verification workflow: that converts an honest product
blocker into permanent main-CI failure and destroys the distinction between
structural health and release readiness. Instead, provide a dedicated
`workflow_dispatch` release workflow that runs the canonical aggregate, then
runs `verify_release_gate.py` **without** `--skip-dirty`, then requires a fixed
machine-readable release-evidence path and validates it with
`verify_release_evidence.py`. Keep the dispatch workflow fail-closed and
unprivileged (`contents: read`, pinned action SHAs). Document the manual entry
point in the release-gate README and scripts README. When a docs-only commit
changes HEAD, re-read the new exact SHA and poll its own CI; never reuse the
previous implementation commit's run as evidence for the new tree.

### Revalidate asynchronous findings against the current tree

An asynchronous audit may have inspected an older SHA or a concurrent dirty
worktree. Treat its findings as hypotheses until reproduced against the current
candidate: capture `git rev-parse HEAD`, `git status --short --branch`, and the
exact workflow/script blobs (`git show HEAD:<path>`), then classify each finding
as `CURRENT`, `ALREADY-FIXED`, `STALE-OLD-TREE`, or `UNREPRODUCED`. Never patch
based only on a historical report. If a finding is current, add a deterministic
negative-control regression before changing the implementation.

Release-gate subprocess boundaries must fail closed. A command returning a
non-zero status is itself a blocking finding even when its output is empty; do
not treat `git status`, `git rev-parse`, evidence parsing, or child-verifier
failure as equivalent to "no findings". Test the final gate behavior with
injected command failure, not only by testing the helper's happy-path output.
A diagnostic bypass such as `--skip-dirty` may be used to inspect other findings,
but must never emit a release-ready result or hide a failed required command.

Synthetic contract smoke is not product capability evidence. A verifier may
emit isolated samples to prove schema/scoring behavior, but samples explicitly
labelled synthetic, skipped, or contract-only cannot promote an E1 capability
to E2/E3. Promote only when the repository's stated E2/E3 evidence contract is
fulfilled by the actual runtime/provenance/read-back boundary; otherwise keep
the release gate blocked and report the missing external condition.

### Cross-SSOT floors, generated projections, and provider attestation

When a release gate reads a machine-readable capability/evidence index while a
product manifest or human-readable generated index also declares floors, compare
all declarations before trusting a green result. A gate that reads only the most
permissive source can silently under-enforce the product contract. Parse the
current candidate blobs and report every `(capability_id, manifest_floor,
evidence_floor)` mismatch; add a negative test that makes the mismatch fail
closed. Treat tracked projections as derived state: locate their generator and
require CI to regenerate them and fail on a non-empty diff. A stale projection
is a release-facing Warning even when its generator is correct.

Promotion ladders such as E0→E5 require cumulative prerequisites, not merely the
artifact list for the target level. An E5 record containing `external_acceptance`
without a same-capability E4 chain is not evidence. Exercise synthetic E4/E5
records through the real verifier and require non-empty failures for skipped
predecessors. Likewise, an ancestor `boundTree` may be valid historical
provenance but must not be treated as current exact-tree release evidence unless
the contract explicitly says so.

For installer-backed bundles, resource registration and source mirroring are two
separate release obligations. A scenario listed in a bundle context but absent
from the installer registry, or registered but omitted from the copied source
closure, is an unresolved dependency even when the source file exists locally.
Require a registry→mirror→manifest regression, not only a resource-count
assertion.

A release-evidence JSON record is not provider CI proof merely because it says
`conclusion: success`. The release verifier must bind workflow name, run ID,
run attempt, repository, exact head SHA, and terminal conclusion to an
authoritative provider readback; otherwise a self-authored fake workflow/run can
satisfy local schema checks. Keep local Git/tree validation and provider-run
attestation as separate evidence rows, and fail closed when the provider query
is unavailable.

When a new regression test changes the full-suite count, refresh current
README/ROADMAP/status counts from the real entrypoint. Preserve old reports as
historical; do not edit them to make the latest count appear retroactively true.
If a follow-up docs commit records the implementation SHA and CI run, it creates
another candidate: rerun the aggregate, release gate, and exact-SHA CI for that
final documentation tree.

Use the compact revalidation worksheet in
[`references/current-tree-release-audit.md`](references/current-tree-release-audit.md).
For capability-floor parity, generated-index freshness, promotion-ladder negatives, and provider CI attestation, use [`references/capability-release-gate-audit.md`](references/capability-release-gate-audit.md).

### Required-step SKIP is a block, not a pass

A composite acceptance command must fail closed when a required platform step
cannot execute. If an Android build or APK metadata inspection is required but
its project-local toolchain is absent, emit `BLOCKED`, return non-zero, and do
not print `all checks passed`. A green unit/bundle suite proves only the
surfaces it actually exercised; it cannot promote an unexecuted platform gate.
Add a regression that checks both the diagnostic and exit behavior. In nested
packages, invoke the real launcher from the package directory (or use an
absolute-path bootstrap) and require a meaningful nonzero test count: `0 tests`,
path-not-found, and selector errors are no evidence. The validated MiniGame
reproduction and output matrix are in
[`references/nested-package-acceptance-gates.md`](references/nested-package-acceptance-gates.md).

## Required evidence chain

1. Establish repository root, remote, branch, dirty WIP, and current version truth. Work in a fresh isolated worktree from the latest `origin/main`; never mutate a dirty user checkout.
2. Run focused and broad local tests with the project's declared dependency groups. Classify optional-dependency and Windows path/harness noise separately; retry from a short disposable runtime path when MAX_PATH is plausible. Restore test-mutated tracked fixtures before any commit.
3. Create one candidate commit and obtain PR exact-head CI. Verify every required job by exact `headSha`; a watcher exit code or partial run is not evidence.
4. Merge only after exact-head success. Verify the merge SHA and a new main-branch CI run whose `headSha` equals that merge SHA.
5. If the path classifier legitimately skips heavy gates, use the repository's explicit fail-closed full-run control on the exact merge SHA. Read and preserve the previous control state, set it only for the authorized rerun, require all heavy jobs (`browser`, Windows runtime, wheel, desktop-fast, desktop-build, installer lifecycle, and aggregate gates as applicable) to complete successfully, then remove a newly-created temporary control or restore its prior value. Verify the final variable inventory.
6. Treat local and CI desktop evidence separately. Official runtime staging plus Rust tests prove local source/build behavior. A successful clean Windows CI `desktop-build` and `installer-lifecycle` prove runner packaging and lifecycle. Do not delete bundled runtime files or weaken resource maps to work around a deep local detached-worktree NSIS path failure.
7. Before a version promotion, parser-check the full matrix: `pyproject.toml`, editable `uv.lock` stanza and digest, `package.json`, both root `package-lock.json` versions, `Cargo.toml`, local `Cargo.lock` stanza, Tauri config, release manifest, identity injector, installer identity readback, version tests, README/status/ledger. Keep the source manifest `unreleased/development/public:false` until artifact identity is injected.
8. After merge-SHA full qualification, create the immutable tag only if the version candidate is intentional and all release contracts match. Require the tag dereference to equal the qualified merge SHA.
9. Build wheel and installer from that same exact tree. Inject artifact identity containing tag/version, commit/tree, verification CI run, release run, and canonical URLs. Use an explicit allowlist for assets.
10. Create a draft Release first. Compare asset names bidirectionally with the allowlist, verify provider digests and downloaded bytes against `SHA256SUMS`, and validate identity readback against exact commit/tree/tag/CI/release URLs. Publish only after every check passes. A successful build with no retained Release assets is not a downloadable release.
11. After publication, re-read the public Release and assets from GitHub, download every allowlisted asset into the project's ignored runtime/evidence area, and recompute SHA-256. For annotated tags, resolve both the tag object and peeled `^{}` commit; the ref API's object SHA is not the release commit. Confirm the peeled commit remains the qualified merge SHA even if post-release documentation commits advance `main`.
12. Reconcile post-publication documentation as a separate, narrow PR: update README/status/changelog/ledger/operator notes so delivered capabilities and public Release facts are current, while preserving explicit deferred capabilities and the source manifest's unreleased placeholder. Run docs-only exact-head CI and merge-SHA main CI; do not retag or rewrite the immutable Release.

## Failure and safety rules

- Never reuse PR-head CI for a merge or release claim.
- Never treat full qualification as publication; it is only the source qualification gate.
- Never convert a local deep-path NSIS failure into a packaging-code change without reproducing under the CI-equivalent path convention.
- Never overwrite a user's dirty WIP or stage test fixtures, caches, runtime data, credentials, or generated reports. Tests can rewrite line endings on Windows; restore those files and re-check status before staging.
- Preserve historical Releases/tags; repair a bad published version with a new version rather than rewriting history.

## Pre-first-run local verification of the release pipeline (validated 2026-08-15)

A Release workflow that has NEVER run (GitHub: "This workflow has no runs yet.")
must be audited for first-run-guaranteed failures BEFORE the tag is pushed —
same discipline as the nightly zero-collection lesson (see
`ci-browser-smoke-testing` pitfalls). Everything except the actual NSIS
build + install can be proven locally:

1. **Dependency inventory**: every file the workflow invokes must exist
   (prepare_bundle.py, verify_nsis_install.ps1, release_inject_identity.py,
   release_checksum.py, package.json/package-lock, tauri.conf.json). One
   missing file = first real run fails at that step.
2. **Dry-run the pure scripts with dummy artifacts** in a temp dir (never
   against real assets): a fake wheel/installer/identity JSON → checksum
   script must emit exactly 3 `64-hex  name` lines with the payload names
   matching; identity injector must output a valid JSON manifest. Two input
   contracts that bite dry-runs:
   - the identity injector VALIDATES the commit/tree format — a short dummy
     like `deadbeef` is rejected (`invalid commit SHA`); use 40-hex strings.
   - it reads `GITHUB_RUN_ID` from the ENV (not a flag) — set it in the
     dry-run's env or it fails (`GITHUB_RUN_ID must be a positive integer`).
   - its output nests: `source.commit/tree/release_run_id/
     verification_ci_run_id` and `release.version/tag` — assert those keys.
3. **prepare_bundle.py end-to-end locally**: it stages a relocatable Python
   runtime (copies `sys.base_prefix` EXCLUDING site-packages/pycache into
   `.hermes/task-runtime/<dest>`, destination MUST stay under `.hermes`),
   `uv export --frozen --no-dev --no-emit-project` locked requirements,
   downloads wheels, builds the project wheel, installs it into the staged
   runtime. This takes minutes and downloads packages — run it once. Then
   PROVE the staged runtime standalone:
   `env -u PYTHONPATH .hermes/task-runtime/<dest>/runtime/python/python.exe -c "import app.workspace.router, shared.config"`.
4. **PowerShell syntax check without executing** (guard rejects inline `$vars`):
   write a tiny `.ps1` to `.hermes/task-runtime/` that calls
   `[System.Management.Automation.Language.Parser]::ParseFile(...)` and
   print errors, then run it with `powershell.exe -NoProfile -ExecutionPolicy
   Bypass -File ...`. Real install lifecycle still needs a real installer.
5. **Version consistency**: the workflow's hardcoded `--version` must equal
   `pyproject.toml`'s version and the wheel name expected in the readback
   step (`archeaxis_workspace-<version>-py3-none-any.whl`).
6. What remains genuinely unverifiable locally: NSIS build, silent install,
   and install-state lifecycle — those run on a real Windows runner at
   release time; say so explicitly rather than claiming full pipeline proof.

## References

- [`references/full-qualification-and-version-promotion.md`](references/full-qualification-and-version-promotion.md) — exact merge-SHA full qualification, temporary CI control cleanup, Windows NSIS evidence classes, and polyglot version promotion.
