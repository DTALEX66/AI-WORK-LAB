---
name: exact-sha-ci-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/exact-sha-ci-delivery/SKILL.md
---

---
name: exact-sha-ci-delivery
description: "Use for exact-SHA CI delivery."
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [ci, github, exact-sha, supported-runtimes, fail-closed]
    related_skills: [github-pr-workflow, cognitive-loop-os-delivery-boundaries]
---

# Exact-SHA CI delivery

## Use when

Use for repository changes where a local test, PR check, merge, or main run can be mistaken for release evidence—especially workflow changes, supported-version compatibility fixes, desktop/installer changes, and fail-closed gates.

## Core contract

Keep these claims separate:

- local focused tests;
- local broad-suite results and environment limitations;
- PR exact-head CI;
- merged commit identity;
- post-merge main CI for the merge SHA;
- formal release qualification.

Never promote one level into another. A green partial job, stale run, or local pass is not proof of the current tree.

## Workflow

1. Freeze the checkout with `git status --short --branch`; protect dirty WIP and stage only explicit agent files.
2. Read the minimum-runtime declaration and the failing job log before changing code. If an API is newer than the declared minimum, reproduce in the minimum-version lane and replace it with a compatible primitive.
3. Add or retain a focused regression contract before the fix. Run the focused test, syntax/format checks, and the smallest relevant project gate.
4. Push a single candidate commit and query the PR's `headRefOid`. Use only runs whose `headSha` exactly equals that candidate.
5. Inspect every job's `status` and `conclusion`, including skipped and required-gate semantics. Do not treat a watcher timeout as a result; query the run directly. If a job fails on dependency-layer or lock-digest contracts, wait until the run is `completed` before requesting `--log-failed`; keep adapter-only packages in `ci-adapters`, restore the tracked lock digest recorded by the release manifest, and create a superseding candidate rather than weakening the contract or reusing old checks.
6. Merge only after exact-head evidence is green and the merge action is authorized by the task scope. If `gh pr merge --squash` fails with `fatal: '<branch>' is already used by worktree at ...` (an existing worktree holds the target branch name) or requires a git checkout, merge via the API instead and read the merge SHA back:
   ```bash
   gh api -X PUT repos/<owner>/<repo>/pulls/<N>/merge -f merge_method=squash
   # -> {"merged":true,"sha":"<merge-sha>"}
   git fetch origin main && git rev-parse origin/main
   ```
   The API path is branch-name-agnostic and does not need a local checkout of the target branch. Record the merge SHA, then query the new main run and verify its exact `headSha` independently.
7. If a newer merge-SHA run is queued behind an older run for a superseded commit, compare both SHAs and cancel only the obsolete run. Never cancel the only run proving the current main tree.
8. After a final green verdict, check the worktree, remote branch, PR state, merge SHA, and main SHA. Do not leave watchers or stale generated files behind.

## PR base and workflow-trigger triage

Before interpreting missing checks or a dirty PR, inspect the PR metadata and workflow trigger filters:

- A repository workflow may run `pull_request` only when the PR base is `main`. A stacked PR based on another feature branch can legitimately show `no checks reported` and still have no CI evidence at all; this is neither pass nor failure.
- **Merge API 405 "Required status check 'aggregate' is expected" after the base advanced.** If another PR merged after this PR was created, `mergeStateStatus` can become `UNKNOWN` and the merge API rejects even though the head's checks were green for the old base. Do not force-push. Fix: `git merge origin/main` into the feature branch (a real merge commit), push — the new head re-runs every check against the current base, `mergeStateStatus` returns to CLEAN, then merge via the API. Re-verify the aggregate on the new head SHA, not the old one.
- **Merge API 405 "Pull Request has merge conflicts" on tracked generated state.** When two PRs both regenerate a tracked digest file (e.g. `CURRENT_STATE.{json,md}`) whose source digest covers code (`scripts/ci/`, `scripts/workflow/`, `config/`) and config, the second PR to merge always reports merge conflicts even when source files don't overlap. Resolution loop (recurred 3× in one session): `git merge origin/main` → conflict only in the generated files → `git checkout --theirs` them → `git add` → **regenerate with the full generator, never `--check-current`** (the theirs copy carries an old digest, so `--check-current` fails `source-digest-mismatch` against the live tree) → `git add` + commit merge + push → re-wait CI on the new head SHA → then merge via API. See `references/ci-failure-repro-and-merge-loop.md`.
- **Tracked generated-state freshness breaks after a squash merge.** If a PR regenerates a tracked projection (e.g. `CURRENT_STATE.json`) on the feature branch, the recorded head is the branch head; the squash merge replaces the branch history, so the recorded head is NOT an ancestor of the merged main head and the post-merge freshness gate fails (`git-head tracked=<old> actual=<merged> (not an ancestor of HEAD)`). Fix (established repo pattern — chore PRs like #35/#38/#44): after the merge, make a follow-up "chore: regenerate CURRENT_STATE for merged main head <sha>" PR regenerated on the CURRENT main head and squash-merge it — the recorded head becomes the parent of the squash commit, which IS an ancestor, and the gate passes. Two corollaries: (a) regenerate against main, never against a feature branch you are about to squash; (b) any PR that changes a canonical digest-input file must include its own regeneration, or the PR's own CI fails with `CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch` (check which tracked files feed the digest before deciding a docs-only PR is digest-safe).
- **A PR CI checkout is a MERGE REF, not the branch head — ancestor-chain checks report false STALE on PR runs** (2026-08-14, DESIGN-LAB boundTree freshness). GitHub Actions checks out `refs/pull/N/merge` (a synthetic merge of the PR head into the base), whose commit is NOT a descendant of `main`. Any gate that asserts "recorded tree SHA is an ancestor of HEAD" (e.g. `git merge-base --is-ancestor <boundTree> HEAD`, or `git branch --contains`) therefore fails on every PR run even when the tree is perfectly fresh, while passing locally where HEAD is the real branch tip. Two-layer fix: (a) gate the freshness step to `if: github.event_name == 'push'` only (main-run checks); (b) when a unit test exercises the ancestor logic, make it tolerate a PR merge-ref HEAD (assert the function does not crash and returns a sane verdict for either a real ancestor or a merge-ref), or skip the ancestor assertion when `GITHUB_REF` matches `refs/pull/*`. Do NOT weaken the check itself — the false STALE is a test/harness artifact, not a freshness defect. Corollary: a local green + CI red on a freshness-style gate, with the CI log showing `current=<boundTree> head=<merge-sha>`, is this pitfall until proven otherwise; inspect `GITHUB_REF` before touching the gate logic.
- **A stale digest on main makes UNRELATED PRs fail** (learned 2026-08-12): a merged chore PR that changed a digest-input file (e.g. error-ledger.json) without regenerating CURRENT_STATE leaves main with a stale digest; every later PR then fails `CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch` in the job that runs the freshness gate (workflow-assistance) while jobs that skip it (observer, gate-plan) stay green. That asymmetric job signature is the tell: if an unrelated PR's CI fails only on the freshness gate, check whether main itself went stale — first merge a "chore: regenerate CURRENT_STATE" PR, then rebase/merge the target PR and re-run.
- For dependent work, prefer an isolated worktree and rebase the dependent branch onto the actual merge target (`origin/main`) unless stacked CI is explicitly supported. Resolve UI/manifest conflicts by preserving the current product contract, then run `git diff --check` before continuing the rebase.
- Update the PR base to `main`, push the rebased head with `git push --force-with-lease`, and verify `headRefOid`, `baseRefName`, `mergeStateStatus`, and the newly created run before monitoring.
- Distinguish `mergeStateStatus: DIRTY`, `checks: []`, and watcher exit code 1. They describe conflict state, absent checks, and watcher result respectively; none substitutes for a completed exact-head run.
- A stale UI smoke assertion or test contract is a changed-path regression: update it only when the product naming/contract change is intentional, and add the corrected assertion to both the dependent branch and its base branch if both PRs run CI.

## Compatibility triage

When the broad local suite fails after a focused change, classify failures before editing:

- changed-path failure: investigate and fix;
- missing optional dependency: use the project's CI dependency lane or install only inside the project environment if authorized; do not modify unrelated adapters;
- test-state pollution: restore only files generated by the test and rerun cleanly;
- unsupported local environment: record it separately from feature evidence.

For Python projects declaring `requires-python >=3.11`, do not use APIs introduced in 3.12+ merely because the agent's interpreter accepts them. Matrix CI is the authority for compatibility.

## Evidence record

Keep a compact record containing:

- candidate commit and PR URL;
- exact PR run ID and `headSha`;
- all required job conclusions and skipped semantics;
- merge SHA;
- post-merge main run ID and `headSha`;
- local focused test command/result;
- unresolved environment-only limitations.

A detailed reproduction and failure-classification template is in `references/exact-sha-ci-evidence.md`; PR base/check-trigger and test-state-pollution details are in `references/pr-base-and-ci-trigger.md`; the Cognitive-Loop-OS frozen-taskpack delivery loop, GatePlan CI fix, and file/SQLite atomicity fix are in `references/cognitive-loop-os-frozen-taskpack.md`. For frozen-candidate backend attack reviews that must not checkout or create files, use `references/read-only-exact-head-attack-review.md`; it covers exact-object inspection, in-memory executable probes, additive/idempotent identity attacks, worker-generation coverage, and outer-wrapper shutdown fencing. The product display-name rename surface inventory (Rust chunk hex, smoke scripts, registry, manifest LF trap) is in `references/product-display-name-migration.md`. Maintenance sweeps for Cognitive-Loop-OS (uv.lock drift classes + release-manifest digest, REVIEW-BLOCK engine-chain compliance with ledger-driven assertions, EXECUTION_STATUS_LOG dedupe, frozen-baseline PARTIAL audits, CI infrastructure vs code failure triage, bash commit-message parentheses trap) are in `references/cognitive-loop-os-maintenance-sweeps.md`. For protected-branch aggregate audits, use `references/protected-aggregate-reachability-audit.md`: compare declared jobs, GatePlan-required gates, aggregate-reachable result channels, and live provider-required contexts; one all-green run does not prove fail-closed enforcement. For WORK-LAB's concrete aggregate gaps (A1-A8: plan_id, repository, tree OID vs `HEAD^{tree}`, skipped_gates coverage, risk/effect/platform/timestamp, critical-path forcing, changed_paths re-derivation), the WL3-800/810 simplification plan, and the WL3-810 perf-asset inventory, use `references/work-lab-gate-aggregate-map.md`. For locally reproducing CI job failures that a bare local tool can't see (actionlint+shellcheck integration), the wait-runs timeout/`{}`-poll semantics, step-level failure localization via the jobs API (logs endpoint 401s), and the recurring CURRENT_STATE merge-conflict loop (checkout --theirs + full regenerate + re-wait), use `references/ci-failure-repro-and-merge-loop.md`.

## Pitfalls

- Reusing a successful run from a previous SHA.
- Treating `gh run watch` timeout as pass/fail.
- **Treating a watcher's exit 1 as a CI verdict.** `wait-runs` exits 1 with "The read operation timed out" (often after `{}` empty poll responses) or "timed out waiting for exact-head runs" when a run is slow/queued — that is a polling failure, not a pass/fail signal. Query the runs directly with the full 40-char `head-sha` (short SHAs return `[]` / HTTP 422) before concluding anything.
- **Trusting a locally-clean lint when CI's lint step fails.** A GitHub Actions `actionlint`-style job on Linux integrates shellcheck, which a bare local binary does not — `git rev-parse HEAD^{tree}` in a run-block passes bare actionlint but trips shellcheck SC1083 (`{`/`}` literal), SC2034 (unused var), SC2155 (export combined with assignment). Reproduce with `actionlint -shellcheck=<shellcheck-binary>`; the clean form is `'HEAD^{tree}'` quoted, then `export` on its own line. See `references/ci-failure-repro-and-merge-loop.md`.
- Cancelling an old run before proving a newer current-tree run exists.
- Fixing optional-dependency failures by changing unrelated production code.
- Staging pytest fixtures, caches, runtime databases, or line-ending changes generated during tests.
- Claiming a task package is complete when later phases (for example release qualification or product UI) have not passed their own gates.
- **Gating a CI aggregator on a job name instead of the semantic GatePlan ID.** When a changed-path classifier emits IDs like `py-primary`, `static`, `windows-runtime`, the aggregator must `require <semantic-id>` mapped to the real job-result env var (e.g. `require py-primary "$TEST_RESULT"` where the result arrives from the `test` job). Requiring a bare job name (`require test`) is a silent no-op that lets a required gate failure pass as green. Add a path-mutation regression test that maps every emitted ID to its job-result variable.
- **Trusting a candidate-controlled GatePlan because its digest is self-consistent.** The plan JSON, digest output, `run_*` job conditions, and aggregate input commonly come from the same mutable PR code, so checking the digest echoed by that producer is not independent validation. The aggregate must reject a missing/JSON-`null` plan (never fall back to a legacy fixed gate set), validate the complete schema, and independently rederive required gates from authoritative changed paths/profile or compare against a protected/base-owned classifier. Add negative controls proving that (a) `gate_plan: null`, (b) a schema-invalid but self-digested plan, and (c) a schema-valid critical-path plan with only one required gate all fail. Run those controls in a job whose reachability does not itself depend on the untrusted plan.
- **Collapsing PR head SHA and PR merge-ref SHA into one “exact SHA.”** On `pull_request`, `github.sha` is the synthetic `refs/pull/<n>/merge` commit, while `github.event.pull_request.head.sha` is the candidate head. Record both identities explicitly: use base→merge for the tested integration tree, but bind protected PR evidence to the head OID expected by policy. A plan that records only `github.sha` cannot later be claimed as exact `headRefOid` evidence.
- **Trusting selective job SKIPs without checking the diff class.** A pure Python/docs PR correctly `skipping` browser-smoke / desktop-build / installer-lifecycle / py-compat / windows-runtime; the expected green profile for a backend-only change is `gateplan`+`lint`+`test`+`wheel-smoke`+`a0-gates` PASS and everything else skipping. Verify the diff really only touched Python+docs before treating the SKIPs as correct.
- **Treating a content-addressed file write and SQLite row write as one atomic transaction.** Inside one `BEGIN IMMEDIATE`, `store_original` (writes a file) plus `record_command_in_transaction` (writes rows) are NOT transactionally coupled. A later failure rolls back SQLite but **orphans the just-written file** — and a conflict retry (same id, different input) leaks a second file. On any failure: (a) write a durable failure record (failures must be auditable), (b) delete the orphaned file written by this attempt, (c) re-raise. Assert both "no orphan file" and "failure record exists" in the test.
- **Staging untracked files that appeared in a clean worktree mid-session.** A repo-local file the user or another process added is not agent-owned; never stage or commit it.
- **Changing a contract vocabulary without syncing gate-script assertions.** When a canonical projection changes its output vocabulary (e.g. freshness strings from source-mode `STALE`/`LIVE` to dashboard-mode `stale`/`fresh`), grep EVERY gate script and test for stale literals of the old vocabulary. A stale assertion inside an environment gate (e.g. `verify_gate_runtime_convergence.py check_5_no_fabricated_exact` asserting `freshness.state == "STALE"`) makes the gate report `environment_limited_pending=False` + `claimable=False` and fails the whole job (`QUALITY_GATE_FAIL gate=runtime-convergence`) even though the change is correct — the gate's env-limited escape hatch only applies when ALL pending checks are in the declared env-limited id set (e.g. `{1, 6, 9}`). The failing gate log shows `passed=N/10`; diff the pending list against that env-limited id set to spot the stale-assertion check, then update the assertion to the new vocabulary and re-run the gate before pushing.
- **Reading a tracked `.md` that `read_file` flags as binary.** Decode with `Path.read_bytes().decode('utf-8')` to edit or inspect it instead of concluding it is unreadable.
- **Renaming the product name without syncing every surface.** The display-name rename (e.g. `ArcheAxis Workspace` → `ArcheAxis Learning Workspace` / `星轨学习工作台`) breaks CI on multiple jobs if any surface is missed: Python tests assert the name in README/manifest/registry/UI, `scripts/a0_browser_smoke.py` + `scripts/runtime_http_smoke.py` fail browser-smoke/windows-runtime-smoke, and `desktop/src-tauri/src/backend.rs` chunked-body test fails desktop-fast because the chunk-size hex prefix (e.g. `63`→`6C`) must track the new payload byte length (108 bytes → hex `6C`; old 99 bytes → `63`). Recompute with `len(payload.encode('utf-8')):X`. Also `app/release-manifest.json` rewritten via Python `json.dump` loses its trailing LF → convention-check `missing-final-newline`; re-append `\n`. Historical docs get a SUPERSEDED banner instead of in-place rewrite (taskpack rule: 不删除历史). See the naming-migration checklist in the Cognitive-Loop-OS delivery skill's references when available.
- **`patch` tool double-escapes Rust string literals containing `\\r\\n`.** Editing a Rust test that embeds literal `\r\n` sequences via the patch tool turns them into double backslashes and corrupts the source. Fix the line with a Python string replace on the exact broken line instead.


## 合并来源: frozen-release-verification (2026-08-21 合并优化)

---
name: frozen-release-verification
description: "Use for exact-tree release review and CI verification."
version: 1.3.2
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [release, verification, exact-tree, ci, rollback, security]
    related_skills: [agent-workflow-fortress, codex, project-data-boundary, systematic-debugging]
---

# Frozen Release Verification

## Purpose

Use this class-level skill for high-risk release candidates, portable workflow packs, staged Git reviews, deployment synchronizers, and any task where a local green result could diverge from CI, the live runtime, or the reviewed tree. It governs evidence identity and failure handling; the owning project remains responsible for product-specific behavior.

## Mandatory sequence

0. **Admit repository identity before evidence.** Resolve and record the exact Git root, requested project/repository name, remote URL, branch, HEAD, and status before reading candidate-dependent files or interpreting any prior handoff. In a multi-project workspace, never carry a previous project's path, PR, SHA, CI run, or completion state into the current task. If the user corrects the project identity, invalidate the old project's evidence immediately, reload that root's policy file, and rebaseline. A pushed branch, ignored local handoff, mergeable PR, or ancestor's green CI is not proof of the current requested delivery.

1. **Discover the live state.** Read repository policy, branch/remote, current status, existing tests, CI workflow, required workflow contract, and deployment entry point. Do not infer CI or live-runtime behavior from local configuration alone.
2. **Create negative controls first.** For each suspected gap, add a failing test or deterministic fault injection through the real entry point. Cover both the reported failure and the nearest bypass path.
3. **Make the smallest coherent fix.** Keep source, contract, documentation, and tests synchronized. Do not mix unrelated refactors into the candidate.
4. **Close dependency gaps.** Every command in the canonical gate must be executable on a clean CI runner or have an explicit `verified`, `unverified`, or `blocked` result. A runtime gate must not silently depend on software installed only on the maintainer machine.
5. **Verify local gates.** Run the canonical quality command, compilation, security/provenance scans, deployment smoke, and platform syntax checks. Save only redacted, project-local evidence.
6. **Freeze intentionally.** For a commit/release candidate, explicitly stage intended paths, inspect cached status, forbidden artifacts and whitespace, then record `git write-tree`. For a user-requested no-staging working-tree review, leave the index untouched and record the tracked diff digest plus explicit untracked inventory as described below.
7. **Review the frozen candidate.** Give a read-only, ephemeral reviewer the exact staged tree or the explicitly identified no-staging working-tree snapshot, plus forbidden paths/actions. The reviewer must not edit, commit, push, or read credentials.
8. **Resolve findings as controls.** Every Blocker/High finding becomes a regression test or a documented exception. After any edit, rerun gates, compute a new candidate identity, and review the superseding candidate; stage again only when the delivery mode uses a staged tree. A verdict never transfers across identities.
9. **Publish only after evidence closure.** Commit only the reviewed tree, push only when authorized, then verify local HEAD, remote HEAD, workflow name, exact head SHA, run attempt, database ID, URL, and required job conclusions. When review identity was an unstaged tracked-diff digest, stage only the reviewed paths and require the SHA-256 of `git diff --cached --binary HEAD --` to equal that reviewed digest; also require zero residual unstaged, conflicting, or untracked candidate files before committing. This is the explicit identity bridge from read-only review to commit.
10. **Close the requested delivery mode.** If the user asks for PR/merge, continue through PR creation or lookup, exact-head CI, merge, and post-merge verification. Report the PR URL and merge commit SHA; a local commit, push exit code, or PR creation response alone is not a merge proof. PR-head CI proves only the reviewed head. After merge, wait for and verify a new required-workflow run whose `headSha` is the merge commit on the base branch; never reuse the PR-head result as post-merge proof. If limits interrupt the sequence, state the exact missing evidence and keep the result explicitly unpublished.

**`gh pr merge` worktree-conflict fallback.** `gh pr merge` shells out to local `git` and can fail with `failed to run git: fatal: '<branch>' is already used by worktree at '<path>'` when any worktree already holds the base branch name (common in multi-worktree setups). The PR is fine — only the local checkout step fails. Do not switch branches or delete the worktree just to merge. Merge through the GitHub API directly:

```bash
gh api -X PUT repos/<owner>/<repo>/pulls/<NUMBER>/merge -f merge_method=squash
```

Then verify remote advanced and PR closed: `git fetch origin <base>`, `git rev-parse origin/<base>` equals the returned `sha`, and `gh pr view <NUMBER> --json state` is `MERGED`. The API merge does NOT delete the head branch, so clean up the remote head branch separately if desired.

## Closure continuity and interruption handling

A release or delivery review is not complete while any required evidence is queued, running, cancelled, abandoned, failed, or not yet read back. Do not stop at local green tests, a pushed commit, a PR URL, a partial CI pass, or a watcher/tool timeout. Continue the exact-tree/exact-SHA chain through all required jobs, aggregate gates, PR state, merge, and post-merge base-branch CI readback.

If a tool-calling iteration limit interrupts execution, treat the task as paused—not complete. Preserve the current candidate identity, branch, commit SHA, PR/run ID and attempt, job conclusions, and exact next gate in the handoff; resume from that identity. A queued or in-progress remote run must continue to be monitored. Cancelled/abandoned jobs fail the aggregate gate and must be rerun or otherwise remediated before merge. Use completed logs to distinguish runner/service failures from product failures, but neither permits a premature GO. After each remote state change, query the authoritative state and advance to the next unresolved closure step.

### Durable handoff and user-directed continuation

When the user says an unfinished loop must not stop, continue polling and advancing the exact-SHA chain; a tool iteration limit, queued run, partial green result, or watcher timeout is not completion. If the user explicitly chooses another computer, stop only at a durable handoff boundary: verify local and remote candidate SHA plus clean-tree state, preserve PR/run URLs and attempt IDs, write a project-local ignored handoff under `.hermes/task-runtime/`, and list the exact remaining gate. State separately that the branch is uploaded/pushed, the PR is unmerged, and release/post-merge CI are incomplete. If the user asks to skip validation, do not bypass required checks or claim completion; preserve the uploaded candidate for the next owner and carry the failed/blocked gate forward.

For a stale PR-triggered run that reports `queued/running` with `jobs=[]` for an extended period, record `status`, `attempt`, `headSha`, `updatedAt`, and job inventory. Do not create a meaningless empty commit. Prefer a reversible PR close/reopen event only when continued delivery is authorized and the candidate SHA remains unchanged; bind any new evidence to the fresh run ID. Contradictory rerun/cancel API responses are infrastructure evidence, not a pass, and merge remains blocked until a complete required-check set is green.


When reproducing a Windows Tauri NSIS release build from Git-Bash/MSYS, do not pass a POSIX-style `$PWD/...` value through `CARGO_TARGET_DIR`. MSYS can rewrite it into a malformed native path such as `D:\\d\\...`, while Tauri/NSIS resource paths remain rooted at `D:\\...`; makensis then reports a misleading missing bundled-resource error. Reproduce the CI build with its default Cargo target directory, or run the build from native PowerShell with an explicitly native absolute target path. Treat this as an invocation/path-boundary control first; do not remove bundled files or modify product packaging until the same command has failed under the CI-equivalent path convention.

For a Tauri desktop candidate whose frontend has LIVE data and a bundled fallback, verify the product state rather than only the source contract: run `cargo check --locked`, `cargo build --release --locked`, then probe `cargo tauri build --help` before invoking the bundler. `--locked` is a Cargo flag and is not accepted as a top-level `cargo tauri build` flag; use the CLI's actual syntax (for example `cargo tauri build --ci --no-sign`, or pass Cargo arguments only through the supported separator). After bundling, cold-launch the generated EXE and record the visible state with the service unavailable; it must say `SNAPSHOT`/equivalent, never `LIVE`. Start the documented local read-only projection service, refresh the same EXE, and record that the badge changes to `LIVE` with Schema v2 data. Stop only processes started by the verification run and leave user-owned desktop windows untouched. A successful local bundle and runtime smoke remain local evidence; they do not satisfy cloud exact-SHA CI, release-asset, or public-download proof.

Whenever a desktop repair changes frontend contracts, add the UI contract runner and JavaScript syntax checks to the same required Observer CI job that runs the Python tests. Re-run the local commands after the workflow edit, parse the workflow, and treat the prior candidate's CI result as superseded. The exact-SHA closure still requires commit/push authorization followed by a fresh remote run and check-readback; never report a local working tree as cloud-delivered.

If bundle preparation refuses an existing destination, preserve it: that guard prevents silently mixing source revisions or overwriting a protected bundled runtime. Do not delete the destination to unblock a local preflight. Use a fresh isolated verification checkout/runtime root, or explicitly establish that the existing staged runtime was built from the exact candidate before reusing it.

### Windows read-only test evidence and path-length noise

For a no-staging/no-edit review, run candidate-dependent tests from a disposable copy of the exact tree, never from the candidate checkout if the suite creates ignored runtime data. On Windows, keep that copy and its isolated Home under a short non-user path (for example a short root-level directory) because a deep `%TEMP%` path can push nested staging paths past MAX_PATH. If a deep temporary copy fails with path-length `FileNotFoundError`/equivalent but the same exact tree passes from a short path, classify the first result as harness/path-length noise, retain it in the evidence log, and do not convert it into a product Warning. Use the repository's real discovery entry point (for example `python -m unittest discover -s tests -p 'test_*.py'`), not an assumed package import; a selector/import invocation error is not a code finding when the canonical entry subsequently runs successfully.

For Windows/MSYS, a `/tmp/...` or `/d/...` path created by Git Bash may not be addressable by native Python. Create disposable copies with native Python under a short drive-root path and pass native `D:/...` paths to Git/Python. If the suite assumes project-local ignored runtime directories, precreate `.hermes/task-runtime/{tmp,cache,logs,artifacts,pycache}` before raw discovery. If a Git-dependent quality gate fails because an archive copy has no `.git`, either initialize/commit metadata only inside that disposable copy or report that gate as harness-blocked; never weaken the gate or claim the full quality suite passed. A corrected canonical test run can close a selector/runtime-directory harness failure, but not a later unexecuted Git-dependent gate.

### Strict no-network/no-user-config review boundary

When the caller explicitly forbids network, user configuration, and candidate-checkout writes, make that boundary operational rather than merely documenting it: set `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null` for Git probes, do not run live/provider/network smoke, and run mutating-looking gates only from a disposable exact-tree copy. After the copy passes, recheck the owning checkout's branch, HEAD, status, `git diff --check`, and caller-supplied digest. On Windows, if the canonical runner resolves Python, PowerShell, or another helper under `C:\Users\...`, preserve the gate result as evidence but classify the user-profile toolchain as a Warning and do not issue GO; environment redirection alone does not prove executable containment. A short-path retry can downgrade deep-path `MAX_PATH` failures to harness noise, but it cannot erase the separate user-profile executable warning.

## Cross-platform command-parser controls

For terminal guards that inspect a command before wrapper execution, test the raw command string before shell tokenization. `shlex.split(posix=True)` can strip Windows UNC backslashes, so checking only parsed argv is insufficient. Cover Windows drive paths, UNC paths, POSIX paths, and embedded option values such as `--output=/tmp/x`, `--output=C:/x`, and `--output=\\server\\share\\x`; also reject shell redirection/chaining. On POSIX, treat foreign Windows absolute paths as external; on Windows, compare normalized drive/UNC paths to the canonical Git root. Re-run these negative controls after every review finding and after every tree supersession.

## Boundary rules

### Wrapper is not an OS sandbox

A project-data wrapper that redirects TMP/cache/artifact variables is a path convention, not arbitrary child-process confinement. The real `run --` path needs negative controls for external absolute output flags, child code containing absolute paths, and symlink/junction escapes. Reject unsafe paths before execution or require a genuine OS sandbox; never document environment-variable injection as an OS security boundary.

### Atomic deployment and rollback

For repo-to-live synchronization, prepare a complete staging tree without mutating live state, then replace managed roots transactionally. Exercise failure after an earlier root is installed and also inject restoration failure. The rollback copy is the last recovery evidence: preserve it and emit a durable failure marker if restoration fails. Delete rollback material only after all replacements and post-apply checks succeed; never remove it unconditionally from a `finally` block on failure.

### Evidence classes stay separate

Report these independently:

- source contract contains the capability;
- isolated portable install materializes it;
- current live profile contains it;
- hook/script trust is approved for its current content;
- transport is reachable;
- a real provider/model smoke succeeded.

Structural checks do not prove live execution. HTTP 401/403 can prove transport reachability but not authentication or model success. A configured hook whose content changed after approval is not fully trusted until explicit re-approval.

### GitHub Release asset closure beyond build CI

A successful desktop/installer CI job proves that the runner built an artifact; it does **not** prove that a user can download, verify, install, or roll back a GitHub Release. Treat an absent `upload-artifact`/release-upload step as zero retained public assets, even if the job's local NSIS lifecycle test passed.

For a versioned GitHub Release, close this separate chain after the post-merge exact-SHA CI is successful:

1. Bind the release candidate to the merged base-branch commit and its successful exact-SHA workflow run; do not reuse PR-head CI.
2. Build the wheel and installer from that same frozen source commit in an isolated project-local artifact directory. Never mix an installer from a feature-branch run with a `main` tag.
3. Run the repository's real installer lifecycle verification (install, launch/readiness, normal shutdown, forced-process cleanup if applicable, uninstall) against the exact installer before publication.
4. Generate a SHA-256 manifest over every asset to be uploaded and a separate artifact identity manifest containing exact commit, Git tree, branch, and CI run. Keep a tracked source manifest intentionally marked `unreleased` only when its documented contract says artifact identity is injected separately. The installer’s bundled runtime must be able to read a strict artifact identity (version/tag, stable/public state, commit/tree, CI run URL/ID, and canonical Release URL) and fail closed for missing, malformed, or mismatched identity; a source checkout must retain its placeholder truth.

   **Packaging-boundary and provenance controls:** Trace the identity file from injection output through the packager resource map to the exact installed path read by the runtime. An identity emitted beside a staged `runtime/` directory is not included when the packager maps only `runtime/`; require either injection inside the mapped root or an explicit resource mapping for the identity. Test the installed `/version` route, not only a monkeypatched identity loader, and require it to report the released state and the installer capability before checksum generation. Runtime validation must reject URLs that are merely well-formed: parse both canonical Release and Actions-run URLs, require the expected GitHub host and the same owner/repository path, then bind the release tag and run ID to their corresponding path segments. Add a negative control with syntactically valid URLs from a foreign or mismatched repository; it must fail closed. Generate checksums for every uploaded payload, including the identity file itself (the checksum manifest need not self-hash). **Treat names as integrity data:** before upload, parse checksum-manifest payload names and require their set to equal the exact explicit staged payload allowlist (same names, no duplicates, no extras). Avoid public-upload globs; an accidentally staged placeholder or ignored file is a release-integrity failure even when every intended artifact has a digest. After upload, perform the same bidirectional set comparison against the GitHub Release asset inventory, excluding only the checksum manifest itself. A provider-reported digest for an asset is complementary evidence, not a substitute for checksum-manifest coverage. If this audit discovers a mismatch in an already-published version, preserve its tag, Release, and assets as historical fact; remediate with a new version/tag/Release that completes the whole exact-SHA and download-readback chain rather than silently replacing old assets. A tag-only trigger is not branch provenance: before building, require the tag target SHA to equal the current protected base branch SHA (for example `origin/main`); a `--branch main` argument or log line is not evidence.
5. Make pre-existing exact-SHA CI an executable gate before release construction. Query the required CI workflow by the exact candidate SHA (for example, `gh run list --commit "$GITHUB_SHA" --workflow CI --json headSha,status,conclusion,workflowName,url`) and fail closed unless a run for that same SHA is `completed` and `success`. The tag-triggered Release workflow's own run cannot satisfy this prerequisite.
6. Create the tag, then create a **draft** GitHub Release containing only the exact verified asset allowlist plus checksum and identity manifests. Before public exposure, read back that same draft: require `isDraft`, compare provider inventory/digests and downloaded bytes against the checksum manifest, and validate artifact identity provenance. Publish only after every readback succeeds (for GitHub CLI, `gh release edit <tag> --draft=false`). A failed readback must leave a non-public draft rather than an already-public immutable Release.
7. Read the draft Release object back: tag target, target commit metadata, asset names, sizes, and release URL. Download the uploaded assets into a project-local ignored verification directory and recompute their hashes against the uploaded checksum manifest.

   **GitHub target semantics:** `gh release view --json targetCommitish` can report the canonical branch name (for example `main`) even when the tag resolves to an exact commit. Do not make a false-blocking literal-SHA comparison against that field. Require the dereferenced annotated tag target (`refs/tags/<tag>^{}`) to equal the exact workflow SHA; accept `targetCommitish` only when it is the canonical base branch or that same SHA, and reject every other value. Add a regression control for this API behavior before relying on the release gate.
8. Audit product-facing release metadata for contradictions. A static source placeholder can be deliberate, but a shipped product claim such as `public_installer: not_implemented` cannot coexist with a release that presents a public installer unless the release contract expressly scopes it away or a reviewed source change resolves it.

If any item is missing, report the source/CI portion as verified and the GitHub Release as **unpublished**; never present CI-built runner files as downloadable release assets.

### Static version-and-lock closure for polyglot desktop releases

For a version-bump candidate spanning Python and a Tauri desktop shell, do a parser-only consistency probe before any mutating build or package-manager command. Compare the intended version across: `pyproject.toml`; the editable project stanza in `uv.lock`; `package.json`; both root-package version fields in `package-lock.json`; `[package].version` in `Cargo.toml`; the matching local-package stanza in `Cargo.lock`; `tauri.conf.json`; and the tracked release manifest. If the manifest records a SHA-256 for `uv.lock`, recompute it and require equality. Then inspect the release workflow, identity-injection validator, and installed-runtime identity loader as one chain: the tag must bind to the injected version, and the injected version must bind to the packaged manifest version. Keep historical or deliberately malformed versions in test fixtures separate from production drift; classify them only when they weaken a real release assertion. Under an explicit no-write review, use JSON/TOML parsing, lock-stanza matching, hashing, and `git diff --check`; do not run `npm ci`, `uv sync`, Cargo builds, or test commands in the candidate checkout unless their writes are explicitly allowed.

### Required workflow and ruleset

The required workflow list must be non-empty. CI evidence must filter by exact commit SHA and required workflow name, then require complete run identity (`workflowName`, attempt/runAttempt, database ID, URL, head SHA) and successful conclusion. Verify the remote ruleset through the provider API; a local manifest or an old run summary is not proof of current enforcement. GitHub Actions conclusions live in the Checks API; a combined legacy commit-status response may remain `pending` with zero statuses even when all Actions check runs succeeded, so verify named check runs and required contexts directly. For product publication, separately require retained run artifacts or Release assets: a successful build job with zero uploaded artifacts proves buildability, not a downloadable release.

### Candidate-aware repository convention checks

A repository convention command that scans `HEAD` does **not** verify newly staged candidate files: it can pass locally while CI fails immediately after commit on a missing final LF, invalid encoding, or path convention. Before committing a staged candidate, run the checker against the index when it supports an index source; otherwise run it against the worktree only after proving the worktree exactly matches the staged path set, or reconstruct the staged tree in a disposable checkout. Record which source was checked. After commit, rerun the same checker against `HEAD` before treating the local proof as closed, and treat the remote CI run as the authoritative clean-runner confirmation. A final-newline remediation is not “too trivial to review”: freeze the narrow blob-only diff, run the candidate-aware convention gate GREEN, and obtain a fresh review identity before its follow-up commit.

## Read-only review of an unstaged working tree

When the user asks for an exact-tree review of current uncommitted work and forbids staging or edits, do not call `git add` or `git write-tree`: both change repository state or describe only the index. Record the resolved repository root, branch, HEAD, porcelain status, staged and unstaged path sets, conflicts, and untracked paths. Bind the review to a SHA-256 of `git diff --binary HEAD --`; because that digest covers tracked changes only, require zero untracked files or hash each permitted untracked file separately.

If task metadata and a supplied repository path disagree, resolve the repository before inspecting code: prefer the task-explicit repository, confirm its Git root/branch/HEAD, and require the expected digest. A similarly named repository or unrelated workspace that does not match the expected identity is not review evidence.

### Historical-claim triangulation under a moving checkout

A read-only reviewer may share a checkout with an active writer. Freeze branch, `HEAD`, status, changed paths, and candidate identity before inspecting claims, then repeat them before the verdict. If an unstaged candidate becomes a commit, push, or PR during review, do not silently switch baselines or discard already gathered evidence: identify the superseding candidate, prove which diff it contains, and report the concurrency event. Bind each test count, artifact, PR, CI run, and delivery statement to the exact tree/SHA that produced it.

A previously merged PR proves only its own files and verification counts. Do not let a current document attach later test counts, ledger entries, runtime fixes, or artifacts to that PR without tree-level evidence. Compare the historical PR summary/checks with the current changed-file set and local test structure. UI readback of an approval/status document is parser/rendering evidence, not independent proof that the source document is truthful. Likewise, a schema/count verifier proves structure only unless it explicitly checks the named PR, SHA, CI run, or external state.

For ignored build outputs, existence plus size/hash proves the local object only. Build duration, source-tree provenance, same-process desktop transitions, publication, and release identity require a durable manifest/log or another evidence source bound to the candidate. Use `references/moving-checkout-historical-claim-audit.md` for the compact matrix.

### Caller-supplied dirty-diff hash gate and Windows text provenance

When the caller supplies an exact SHA-256 and says to proceed only on a match, make that the first repository action: record branch, HEAD, porcelain status, then run the caller-specified command verbatim (commonly `git diff --binary | sha256sum`). Stop before source inspection, tests, or other candidate-dependent probes on mismatch. After a match, also record staged paths, conflicts, and untracked paths; an unstaged-only digest does not cover untracked files.

Treat the initial match as an identity admission, not proof that the checkout is quiescent. Before candidate-dependent reads or probes, take a short read-only quiescence snapshot of branch, HEAD, porcelain status, changed-path inventory, and the exact digest. Prefer serial probe batches over parallel long-running candidate probes. Recompute the same identity after each batch and immediately before the verdict. If any external edit adds, removes, or changes a tracked path—even an unrelated documentation/config path—stop, mark the prior evidence superseded, and do not inspect or test the new candidate under the old identity; report the new digest and request/restart review from that identity.

#### Windows repository-root resolution before the hash gate

If the task gives a workspace/home path that is not itself a Git worktree, do not hash that directory or silently choose a similarly named checkout. Perform only bounded, read-only repository discovery within the explicitly permitted scope, enumerate candidate Git roots, and run the caller-specified identity/hash command independently in each candidate until exactly one matches. Bind the review to the matching root's branch, HEAD, porcelain status, and digest; record the path mismatch as identity-resolution context, not as a source finding. Do not inspect candidate source, run tests, or create verification artifacts before an exact match. If zero or multiple candidates match, stop as review-blocked and request a disambiguated repository path or identity.

If the task's nominal workspace path is not itself a Git worktree, do not silently treat that as the candidate or begin source inspection. Resolve the actual repository by checking only Git metadata and candidate diff digests in explicitly permitted workspace roots (and, when the task context independently names one, the current project directory); select a repository only when its identity and caller-supplied digest agree. Record the resolved root and the path discrepancy. Do not enumerate or inspect user-profile runtime/config trees while searching, and never use a similarly named repository whose digest does not match.

On Windows, `.gitattributes` may require LF while the working copy is CRLF. `git diff --binary` can emit CRLF conversion warnings on stderr while still producing the expected normalized diff digest on stdout. Report the raw working-copy EOL state and the attribute rule, but do not classify it as content drift when the requested diff hash remains identical and `git diff --check` is clean. Recommend LF normalization before staging to remove audit noise. For skill provenance, distinguish a raw-byte hash from a canonical-text (CRLF/LF-normalized) hash; if the verifier intentionally canonicalizes text, compare the manifest to that canonical hash. A `pending-live-sync` marker proves neither current live parity nor deployment. Isolated-install materialization, source provenance, and live-profile parity remain separate evidence classes.

Recompute identity and status after every test and immediately before the verdict. Branch, HEAD, porcelain status, and changed-path inventory can all remain identical while tracked content changes, so neither a status digest nor an unchanged path set substitutes for the tracked diff digest. Any digest drift immediately invalidates prior static reads and test evidence: stop launching probes, establish quiescence on the superseding digest, and do not run tests against it under the original exact-diff request. Report the identity mismatch as release-blocking and request a fresh review identity instead of combining evidence across candidates; the first exact-match candidate must not receive a final GO/NO-GO verdict after drift, and newly appearing paths must not be inspected or attributed to the reviewer. Run tests in a disposable location outside the candidate identity; when project policy requires an ignored project-local runtime, verify the ignore rule first, redirect temp/cache/bytecode there, and disclose refreshed ignored artifacts separately from candidate drift.

## Lightweight final arbitration of an unchanged candidate

When an exact no-staging working-tree candidate has already completed the full gate and independent review, and the user asks only for a lightweight final verdict:

1. Re-read the live branch, HEAD, porcelain status, staged/conflict/untracked inventories, and `git diff --binary HEAD --` SHA-256 before inspecting evidence. Require exact agreement with the supplied context; do not transfer a verdict across any drift.
2. Read the tail of the named reviewer/delegation transcript from its original file and inspect the current implementations on the changed safety-critical paths. Treat session summaries as context, not as a substitute for the live tree.
3. Do not repeat an expensive full gate merely for ceremony when it already passed on the identical candidate. Run only a short directed probe if a concrete unresolved risk requires it.
4. A failed attempt caused solely by the wrong test import/module entry is not a code warning when the correct project entry subsequently runs the intended tests successfully. Record the successful entry and avoid turning transient invocation mistakes into persistent release findings.
5. Immediately before the verdict, recompute branch, HEAD, status inventories, conflicts, untracked files, `git diff --check`, and the tracked diff digest. The first output line must honor the user's literal `GO`/`NO-GO` contract; when the rubric says GO requires zero Critical and zero Warnings, Suggestions may remain but may not conceal either class.
6. Keep the report narrow: exact identity, Critical, Warnings, Suggestions, and Looks Good. State explicitly when the full gate was intentionally not rerun and which prior exact-tree evidence was relied upon.

## Selective migration from an obsolete PR

When an old PR contains a valuable product slice but its CI, dependency, runtime, or configuration changes have been superseded:

1. Enumerate the complete changed-file set and classify every path as `migrate`, `superseded`, or `reimplement-on-current-tree`; never merge or rebase the obsolete PR wholesale merely to recover a useful slice.
2. Transplant the narrow verification contract first and run it against the current base for a real RED. If the smoke entry requires isolated runtime variables, use a project-local ignored runner that sets the data root and adds the script directory to `sys.path`; do not weaken the production smoke entry for invocation convenience.
3. Apply only the approved source/docs slice, then run the same contract GREEN plus focused API/unit checks, syntax/lint, and `git diff --check`.
4. Treat `git checkout <commit> -- <paths>` as an index mutation: it writes both working tree and index. If freezing belongs to a later cycle, immediately run `git restore --staged <paths>` and verify `git diff --cached --name-only` is empty.
5. Record omitted superseded surfaces explicitly. A green migrated UI/browser slice does not validate old requirements, workflows, release manifests, or runtime configuration.
6. Preserve the result as a controlled dirty set until the separate full-gate and candidate-freeze cycle; do not collapse migration, full verification, staging, review, publication, and merge into one unbounded task.

## Read-only staged-candidate audit against an obsolete PR

When asked to independently review a supplied staged tree and prove that an obsolete PR was not reintroduced, remain read-only: do not stage, restore, commit, push, fetch, or inspect credentials. First bind the review with `git diff --cached --quiet <expected-tree>` and record the staged path inventory; enumerate every staged path explicitly, not only matching paths. Locate the obsolete PR head/base from local history or a public PR page, enumerate its full changed-path set, and classify the legacy CI/dependency/runtime/config/release surfaces separately. Prove each legacy path is excluded with `git diff --cached --quiet -- <path>` and also scan the staged path set for those path families. A staged runtime source file is not itself evidence of configuration migration: inspect the exact hunks and distinguish formatting/equivalent syntax from behavior or config changes. Check staged whitespace and parse staged script blobs through stdin or another disposable read-only path; do not run a browser/runtime gate if it writes fixtures, databases, caches, or other candidate-adjacent state. Before the verdict, repeat the expected-tree comparison and state any unrelated unstaged paths as out of candidate scope rather than silently adopting them.

### Desktop/runtime documentation truth audit

For a narrow migration-PR audit that includes desktop/runtime/docs, report three independent rows: (1) runtime behavior and boundary changes, (2) UI/browser evidence class, and (3) public documentation truth. Cite candidate blob line numbers for each finding or pass. A UI smoke source or Chromium static/browser result does not prove current Tauri/WebView execution; preserve that distinction and mark a runtime gate deliberately skipped when it would create migrations, databases, fixtures, caches, or other state under a read-only mandate. Audit README/product-positioning claims against the candidate's explicit limitations: it must not turn plans, route shells, candidate data, Chromium evidence, or an unreleased manifest into completed desktop/public-release claims. Conversely, an intentionally unchanged `unreleased` / `public=false` release manifest, absent release assets, or incomplete public publication is out of scope for a migration PR unless the user explicitly makes public release readiness a gate; report it as an excluded/unchanged surface, never as the reason for a migration `NO-GO`. Prove CI, release-manifest, and dependency exclusion both from the full staged-path inventory and with per-path `git diff --cached --quiet HEAD -- <path>` checks. If `git write-tree` would create an index lock under the no-mutation constraint, do not call it; the supplied-tree comparison is the read-only identity proof.

## Local filesystem race controls

Installers and repo-to-live synchronizers need adversarial filesystem probes, not only happy-path atomicity tests. Existing-zero-byte-file writes must account for hard links, link/reparse swaps, concurrent population after `fstat`, late override creation, short writes, and preparation failures. Whole-root staged promotion must either hold an ownership lock, revalidate the live snapshot, or replace only managed subtrees; otherwise concurrent non-managed additions can be silently discarded even though rollback succeeds.

### Configuration-ownership TOCTOU control

A preservation assertion over a **staging copy** is not proof that current live user configuration will survive promotion. If a synchronizer copies `live/config.yaml` into staging, merges it, and later replaces the live path, a provider route, auth-related top-level field, custom MCP, non-owned hook, plugin, or future field can change after the copy but before promotion and be silently overwritten.

Bind the prepared config to the live version read at the start (for example, a content digest plus file identity where supported), then immediately before replacing `config.yaml` either hold the ownership lock or re-read and compare the complete user-owned projection. On mismatch, refuse promotion and preserve the current live file. Test the real orchestration path: pause after staging/snapshot, mutate representative user-owned surfaces in live config, then prove promotion fails without replacing it. An in-memory snapshot-vs-mutated-object unit test does not cover this TOCTOU boundary. Documentation may claim fail-closed preservation only when this pre-promotion control exists.

For POSIX single-file publication, add distinct negative controls for: (1) no attacker-raceable named staging fallback, (2) unavailable `O_TMPFILE` producing zero public/private writes plus an explicit nonzero unsupported result, (3) a user target appearing before staging and being preserved with a non-destructive marker, (4) `linkat(AT_EMPTY_PATH)` no-replace `EEXIST`, and (5) cleanup that closes anonymous staging without unlinking any contested public target. Probe anonymous-staging support on the actual test directory, skip only the tests that require a successful anonymous inode, and retain an unsupported-capability test that runs even where the feature is absent. Bind the review to a pre/post SHA-256 of the exact working diff; a changed digest invalidates all earlier evidence. See [`references/dirty-working-tree-and-filesystem-race-review.md`](references/dirty-working-tree-and-filesystem-race-review.md).

## Review-finding remediation and UI truth controls

When an exact-tree reviewer returns a terminal NO-GO with warnings, treat the reviewed identity as rejected even if there are zero Critical findings. Preserve the rejected tree and report, then use one bounded remediation cycle:

1. Translate each warning into an observable contract and its nearest bypass regression. For UI truth findings, distinguish a capability available somewhere in the product from the specific navigation route being directly usable; a route badge must describe the route the user will reach, not a nested feature on another page.
2. Keep terminology synchronized across visible text, accessibility names, toggle labels, tests, and positioning documentation. An ARIA label using the retired term is still a product-contract regression.
3. For responsive state initialized at script load, distinguish two contracts: **cold-load defaults** and **live breakpoint transitions**. Clear only the relevant test-owned storage key, then perform a real reload/navigation before asserting the mobile default; separately prove the explicit reopen path. Also cross the breakpoint without reloading and require the production `matchMedia`/resize handler to resynchronize visibility, focusability, `inert`, `aria-hidden`, and trigger state. A reload-only smoke can pass while desktop→mobile leaves visually hidden controls keyboard-focusable. Do not weaken production initialization merely to make the test convenient.

   Treat breakpoint updates as asynchronous browser behavior. In Playwright, wait on the observable DOM contract with web-first assertions such as `expect(locator).to_have_attribute(...)` before checking focus or `inert`. Avoid string-based `page.wait_for_function(...)` on applications with a strict Content Security Policy: Playwright's string evaluation can require `unsafe-eval` and turn a correct responsive fix into a test-harness failure. Do not add `unsafe-eval` or weaken CSP to accommodate the smoke test.
4. Rerun the narrow browser/syntax/lint gates, stage only the authorized remediation paths, and compute a new `git write-tree`. Record it as a **superseding candidate awaiting review**, not as approved or frozen-review-complete.
5. Require a fresh read-only verdict bound to the new tree before commit or publication. Never transfer the prior reviewer’s zero-Critical count, partial approval, or test evidence across the identity change.
6. For delegated click handlers, review selector ownership across the full ancestor chain. A broad `closest('[data-module]')`-style selector can match both the intended control and a containing navigation group, causing a child route click to run two handlers and redirect to the group default. Scope handlers to the actual control class/role (for example, `.rail-item[data-module]`) and test nested descendants as well as direct button targets.
7. Browser smoke must exercise behavior, not merely metadata. For each non-leading route whose badge or availability claim matters, click it and assert the resulting URL/page/state; include at least one second-position route in another group so ancestor-selector collisions cannot hide behind a correct badge.
8. Treat responsive secondary navigation as an explicit state machine, not a hover adaptation. A rail/module activation must open the drawer through durable application state and move focus to a usable secondary control; selecting a route and pressing Escape must close it. Do not rely on `:hover` or `:focus-within` as the only reveal mechanism, because they make non-leading routes unreachable on touch devices. The rail trigger must expose `aria-controls` and dynamic `aria-expanded`; retain the exact trigger element so both route selection and Escape restore focus to it. ARIA must describe the rendered state on every layout: on desktop, the trigger controlling the visibly expanded active module reports `aria-expanded=true`; on mobile, only the currently open drawer trigger reports true. While closed on mobile, make the secondary navigation non-interactive with `inert` and expose `aria-hidden=true`; remove both closed-state restrictions when opened. Scope global Escape focus restoration to a drawer that was actually open—otherwise a stale rail trigger can steal focus restored by an unrelated modal. At a real mobile viewport, assert drawer-open state, focused route, at least two second-position destinations from different groups, exact URL/page results, close-after-selection, Escape close, trigger focus restoration, `aria-expanded`/`aria-hidden`/`inert` transitions, and no horizontal overflow. Then cross desktop↔mobile without reload and repeat the accessibility-state assertions so breakpoint transitions cannot preserve stale semantics.
9. Audit every off-canvas responsive surface independently—secondary navigation, inspector, filters, job panels, and similar drawers do not inherit one another's accessibility proof. A collapsed panel must have a visible, in-viewport external trigger; a toggle located inside the translated-offscreen panel is not a reopen path. Synchronize the panel's `inert` and `aria-hidden` with the external trigger's `aria-controls` and `aria-expanded`, place focus inside on open, and restore focus to that trigger on close. Run that panel-state synchronizer on **every responsive breakpoint transition**, not only on initial load or the panel's own toggle: otherwise a mobile-closed panel can remain `inert aria-hidden` after becoming a visible desktop-collapsed surface, while a desktop-collapsed panel can become off-canvas on mobile without either restriction. Browser smoke must use normal actionability checks to click the visible trigger and verify focus/order transitions; forced clicks, DOM-dispatched clicks, or clicks on offscreen controls can conceal the exact reachability defect under review. For every off-canvas panel, explicitly test both `mobile closed → desktop` and `desktop collapsed → mobile` without reload, asserting rendered visibility plus `aria-hidden`, `inert`, trigger actionability, and the valid reopen route. Add a geometry assertion for the closed mobile state: its bounding rectangle must be fully outside the viewport (for example, `rect.left >= window.innerWidth`). This catches CSS-specificity regressions where an `inert aria-hidden` panel leaves a visible but unusable strip. When the panel uses CSS transitions, avoid asserting an intermediate transform frame immediately after resize: emulate `prefers-reduced-motion: reduce` if the product honors it, or wait for a stable observable layout endpoint without relaxing CSP or dispatching synthetic clicks. If an exact-SHA CI run reports an intermediate geometry (for example, a still-visible off-canvas panel) while local runs pass, treat it as a smoke synchronization failure only after reproducing the same entry point; wait for the final geometry predicate, retain the original physical-layout assertion, and repeat the isolated browser smoke more than once before replacing the CI candidate.

   In Playwright, an element with `aria-hidden=true` is intentionally absent from the accessibility tree, so `get_by_role(...)` may time out even though the DOM node correctly exists. Inspect closed-panel state through a stable structural locator such as `#inspector`, then use role/actionability locators for the visible external trigger and the opened panel. This distinction prevents a correct accessibility fix from being misclassified as missing DOM while still proving that hidden content is unavailable to assistive technology.

   **State-sequencing pitfall:** do not reopen a mobile-collapsed panel before exercising its mobile→desktop transition: that changes the state under test and can make a broken breakpoint handler appear green. In one real browser document, explicitly keep the panel collapsed for `mobile closed → desktop`, assert desktop removes `aria-hidden`/`inert`, and prove the internal desktop trigger can reopen it. Then collapse it again on desktop before `desktop collapsed → mobile`; assert the off-canvas panel gains `aria-hidden`/`inert`, then use the visible external mobile trigger to reopen it. A smoke that only checks panel metadata or a pre-opened transition is not regression coverage.

## Codex review contract

Use the narrowest available read-only sandbox and ephemeral mode. Bind the prompt to the frozen candidate tree. Do not use credential files, broad filesystem access, approval bypass, or automatic fixes. If the reviewer reports findings, preserve the report, turn findings into tests, and invalidate the old tree/review before editing.

A read-only sandbox may prevent `git write-tree` because Git attempts to create `index.lock`. Compute the tree in the owning writer before delegation. Inside the reviewer, prove equivalence without mutation using `git diff --cached --quiet <expected-tree>` (exit 0) and prove rejection/supersession with a nonzero comparison to the prior tree; then inspect only cached diffs and index blobs. The sandbox failure to recompute is not candidate drift when these read-only comparisons agree.

For portable Codex/agent packs, do not treat a documented runtime-discovery rule as implemented merely because the skill text says to run `--version` and `--help`. Audit the canonical runner and README examples for hard-coded flags. Every run should record a non-empty `codex --version` result as transient evidence, then parse `codex exec --help` before invocation; version/help failure or a missing required flag must fail closed before the reviewer starts. Every flag used by the real runner—including sandbox, ephemeral, config/rules, output, and schema flags—needs a preflight capability check or an explicit compatibility branch. Add negative tests proving failed/empty version probes do not reach `exec --help` or the real operation. A runtime update path is incomplete when only the prose skill performs discovery while the production entry point invokes the old flag set directly.

When a portable runtime intentionally uses an official package name without a version pin, keep that exception explicit and narrow. Candidate supply-chain audits may still require pinned package/version provenance and reject `latest`; runtime verifier, candidate audit, README, and all current-status/audit docs must state the two-layer distinction. A quality PASS produced through a user-profile interpreter or external temp/cache root is valid execution evidence but not proof of a fully project-isolated harness; report structural, live-runtime, and harness-boundary evidence separately. Treat a resolved external Windows interpreter path as an environment-evidence boundary, not a source-code defect: preserve the gate result, count the boundary as a Warning under zero-Warning GO rubrics, and do not relabel it as a product failure. If a direct unittest module selector/import fails, rerun the repository canonical discovery entry before classifying it; when canonical discovery passes, record the first result as harness noise rather than a code finding.

## References

- [`references/review-blocker-negative-controls.md`](references/review-blocker-negative-controls.md) — reusable CI, sandbox-boundary, rollback, and exact-tree negative controls.
- [`references/dirty-working-tree-and-filesystem-race-review.md`](references/dirty-working-tree-and-filesystem-race-review.md) — read-only dirty-tree identity, bounded active-writer quiescence, and installer/synchronizer race probes.
- [`references/reviewed-working-tree-to-merge-closure.md`](references/reviewed-working-tree-to-merge-closure.md) — bind an approved unstaged diff to explicit staging, commit, PR-head CI, merge, and merge-SHA CI.
- [`references/github-release-gap-audit.md`](references/github-release-gap-audit.md) — read-only audit of source publication versus installable GitHub releases, concurrent worktree drift, exact-SHA checks, retained artifacts, rulesets, tags, and Release assets.
- [`references/draft-release-readback-closure.md`](references/draft-release-readback-closure.md) — draft-first GitHub Release publication, exact-SHA CI closure, downloaded-asset and identity-tree negative controls.
- [`references/taskpack-release-governance-audit.md`](references/taskpack-release-governance-audit.md) — evidence order and fail-closed criteria for auditing TaskPack release specifications against historical Releases and live branch governance.
- [`references/codex-runtime-and-mcp-compatibility-review.md`](references/codex-runtime-and-mcp-compatibility-review.md) — per-run Codex version/help preflight, MCP runtime-vs-candidate pinning, exact-tree identity, and evidence-boundary notes.
- [`references/ci-evidence-supersession.md`](references/ci-evidence-supersession.md) — exact-SHA CI evidence ownership, source-sensitive convention repairs, and PR-head-to-merge-SHA handoff.
- [`references/generated-projection-freshness.md`](references/generated-projection-freshness.md) — deterministic tracked-projection regeneration, required-CI wiring, stale-source negative controls, and fail-closed aggregation.
- [`references/ci-handoff-recovery.md`](references/ci-handoff-recovery.md) — durable handoff, stale PR-run recovery, evidence-state separation, and graceful Windows lifecycle failure handling.
- [`references/frozen-taskpack-horizon-execution.md`](references/frozen-taskpack-horizon-execution.md) — isolated execution worktree per horizon, authority-branch separation, one-task-one-checkpoint, selective-CI-SKIP-is-correct, file-vs-SQLite transaction atomicity, and `gh pr merge` worktree fallback.
- [`references/tauri-live-snapshot-verification.md`](references/tauri-live-snapshot-verification.md) — Windows Tauri build syntax, bundled fallback truth, live-service smoke, and exact-SHA evidence boundaries.

## Skill-pack and portable workflow content audits

When the exact candidate is a repository-maintained skill or portable workflow pack, extend the frozen-tree review beyond source syntax:

1. Bind the supplied identity before inspection. For a no-staging request, record branch, HEAD, porcelain status, and the caller's exact `git diff --binary` digest; stop on mismatch. Recompute the digest and status immediately before the verdict.
2. Validate frontmatter with the repository's real provenance checker and pass every required argument (commonly both `--repo` and `--manifest`). A checker invocation that exits with CLI usage error is not provenance evidence.
3. Resolve `metadata.hermes.related_skills` against the current repository skill set and the checker's explicitly allowed profile-skill names. Resolve every `references/...` link relative to the skill directory; do not infer availability from a similarly named file elsewhere.
4. Compare source SHA/version, README inventory, provenance manifest, managed-root lists, and tests against the exact current tree. Treat a passing provenance hash as source identity evidence only; it does not prove live-profile parity or full governance execution.
5. Audit examples as executable contracts on the target OS. For Windows `netstat`, use the actual `LISTENING` state rather than POSIX-style `LISTEN`; test shell pipelines and path conversion semantics instead of trusting prose.
6. Compare the documented canonical gate list with the runner's registered and default gate list. Check every user-facing projection separately: quality-gate docs, README summaries, optional convenience wrappers such as `Justfile`, CI workflow invocations, and any generated PASS example. A gate added to the runner but missing from any maintained projection is release-facing drift and should be reported separately from implementation correctness. Also check that pruning a large skill did not leave orphaned references under its directory (especially references naming removed toolchain, Desktop, proxy, or provider scope) when the public docs claim retired material is no longer retained.
7. Separate version semantics before classifying leftovers: (a) a current compatibility requirement such as `hermes-agent==...` in a manifest/CI file, (b) a runtime-discovered, intentionally unpinned executable/package whose `--version`/`--help` is checked per run, (c) a pinned candidate-audit fixture or policy requirement, and (d) explicitly labeled historical audit evidence. Do not infer that all version strings are stale, and do not let a runtime-unpinned change silently weaken a candidate-audit pinning rule. When these layers differ, require docs and tests to state the distinction explicitly. A normative document that still says the runtime package is pinned after the implementation accepts an official unpinned name is a Warning, even if the old pinned string is harmless.
8. Add or inspect paired regression coverage for the separation: candidate audit must reject missing/`latest` versions, while the runtime verifier may accept only the documented official unpinned package form and must still reject `latest`/foreign packages. Treat a test that checks only the MCP name or key as insufficient evidence for package-version semantics.
9. Under strict read-only constraints, prefer provenance, parser, hash, and static checks. Do not run a full governance suite in the candidate checkout when tests create `.hermes`, caches, databases, reports, or bytecode; use a disposable exact-tree copy or report the gate as unexecuted. Treat portable-install/sync verifiers as potentially mutating even when invoked as checks: they may rewrite tracked files or normalize EOLs. Run them only from a disposable exact-tree copy, then recompute the caller-supplied identity in the owning checkout. Never convert an unexecuted gate into a pass claim. A direct read-only provenance checker invocation is useful evidence, but it does not replace the governance suite.
10. For a disposable exact-tree test copy, change directory into the reconstructed copy before every candidate-dependent command; otherwise a shell script can silently run tests or the quality gate against the owning checkout and create ignored runtime artifacts there. Preserve each gate's redacted log and terminal summary until the evidence matrix and final test/skip counts have been extracted; only then remove the copy and recheck the owning checkout's status/digest. If a convenience selector fails because tests are not importable as a package, rerun through the repository's canonical discovery command and report the selector failure as harness noise only when canonical discovery passes.
11. Check numbering and section structure after large pruning operations. An out-of-sequence heading is usually a maintainability Suggestion; stale public scope, a misleading executable command, or a stale gate summary is a Warning.
12. When a compatibility change removes a runtime pin, scan all maintained documents—not only changed files—for normative wording that contradicts the new contract. A document marked `current`, `status`, or equivalent that still says the default runtime is pinned is a Warning even if README, implementation, tests, and candidate-audit policy are correct. Keep runtime-unpinned selection, candidate-audit pinned provenance, and explicitly historical evidence as separate rows in the review.

## Read-only review hygiene

Before running verification, capture `git status --short`; capture it again afterward because tests may mutate tracked fixtures or generated files. Keep narrow changed-surface tests separate from the full suite. Attribute full-suite failures only with baseline evidence, and distinguish unrelated missing dependencies or pre-existing runtime failures from regressions in the reviewed slice. An unexpected post-test tracked-file mutation is a candidate-hygiene blocker for an exact-tree verdict; do not silently repair it during a read-only review.

## Final checklist

- [ ] Current repository/remote/CI state inspected
- [ ] RED tests and fault injection exist for confirmed gaps
- [ ] Canonical local gate passes on the candidate
- [ ] Clean-runner dependencies are closed or explicitly unverified/blocked
- [ ] No credentials, auth databases, caches, or runtime state staged
- [ ] Candidate identity recorded immediately before review (`git write-tree` for an intentionally staged candidate, or tracked diff digest plus explicit untracked inventory for a no-staging working-tree review)
- [ ] Read-only review completed against that exact tree
- [ ] Every Blocker/High resolved or explicitly blocked
- [ ] Any post-review edit triggered a new tree and new review
- [ ] Exact-SHA CI and remote governance evidence verified before claiming release


## 合并来源: merge-verification-workflow (2026-08-21 合并优化)

---
name: merge-verification-workflow
description: "Use for stale-PR slicing, safe merges, and real verification."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [git, merge, verification, dirty-worktree, ci, scheduling]
    related_skills: [agent-workflow-fortress, github-pr-workflow, systematic-debugging, project-data-boundary]
---

# Merge and Verification Workflow

Use this skill when a user asks to merge branches, reconcile parallel work, or prove that a merge/build/runtime actually works. A merge preflight, a clean status response, or a scheduler API response is not the deliverable; the deliverable is a preserved worktree, a real merge decision, and exercised verification evidence.

## Core contract

- Protect user changes before changing checkout state.
- Keep one writer per checkout; pause write-capable automation during merge and manual repair.
- Resolve conflicts by functional freshness, not by blindly selecting one side.
- Verify the exact resulting tree with real tests and runtime smoke paths.
- Restore the user's WIP and report precisely what was committed, what remains dirty, and what was not merged.

## Procedure

### 1. Establish scope and live state

1. Read repository policy files and run `git status --short`, `git branch --show-current`, `git worktree list`, and the relevant branch log.
2. Identify the requested source branch and whether it is stale, already functionally absorbed, or contains distinct behavior.
3. Do not assume “merge” means upload, push, squash, or merging into `main`; only perform those actions when explicitly requested.

### 2. Freeze concurrent writers

Pause cron/sleep workers, background writers, and local agents that can mutate the same checkout. Do not kill unrelated Gateway, browser, session, or workflow infrastructure. Resume only after the merge and verification boundary is complete.

### 3. Protect dirty WIP

If the worktree is dirty, preserve it with an explicit named stash:

```bash
git stash push --include-untracked -m "pre-merge <scope>"
```

Record the stash reference. Never use broad cleanup or `git clean` as a substitute for WIP protection. After the merge commit, restore the exact stash and check for conflicts, missing untracked files, and unexpected staged paths.

### 4. Preflight without mutating the checkout

Use ancestry, changed-file comparison, and `git merge-tree` to understand conflicts. A conflict list is not a reason to stop if the user asked for the merge. Conversely, a clean merge-tree is not proof that the resulting runtime works.

When the user asks for a **read-only migratable-slice audit** rather than a merge:

1. Record `HEAD`, base, remote-tracking feature head, PR API head/base OIDs, and `git merge-base`; do not fetch, checkout, create a worktree, or write merge objects unless the user authorized those actions.
2. Use `git diff base...feature` for the PR-authored slice. Use `git diff base..feature` only to reveal final-tree drift and base-only advances that a careless tree replacement would erase; never report the two-dot view as the migration patch.
3. Map each changed file to its introducing commit so product/UI work can be separated from CI-repair, dependency, policy, runtime, or configuration work.
4. Prefer the three-input read-only form `git merge-tree "$(git merge-base base feature)" base feature`. Distinguish textual conflicts from semantic conflicts that auto-merge while regressing locks, manifests, runtime baselines, or configuration.
5. Classify every PR file as: retain atomically, retain with manual replay, discard, or separate follow-up. Explicitly inventory main-only files that must be protected.
6. Prove path-level transplantability without applying anything by piping a path-filtered triple-dot diff to `git apply --check -`; check coupled UI/source/smoke files as one unit.
7. Treat green CI on the old head as historical evidence only. A transplanted slice needs the current base's targeted tests, dependency/config anti-regression gates, browser/runtime smoke, and exact-SHA CI.
8. Re-run `git status --short --branch` and verify the original `HEAD` before reporting that the audit remained read-only.

See `references/gh-less-github-rest-via-credential-manager.md` for the full
gh-less REST recipe (git credential manager token, create/merge/delete PR
ops, quota and proxy routing) used when `gh` is unavailable.
See `references/stale-pr-migration-slice.md` for the compact command and reporting pattern.
See `references/post-squash-followup-generated-files.md` for safe follow-up branching after squash merge, generated-projection conflicts, pre-commit file expansion, non-self-referential delivery docs, and reconciliation when a read-only reviewer mutates the checkout.

### 5. Perform and resolve the merge

Use an explicit, inspectable merge:

```bash
git merge --no-ff --no-commit <source-branch>
```

For each conflict:

- preserve the newer current architecture when the source branch is stale;
- carry over genuinely new tests, gates, or behavior from the source branch;
- manually union compatible changes in CI/config/docs;
- never use `git checkout --ours` or `--theirs` across an entire architecture without first comparing the functional content.

If the source branch's behavior is already present and the resolved tree is byte-identical to the current HEAD, an ancestry merge can still be valid when explicitly requested. Verify both parents and report that the merge added history, not source-tree changes.

### 6. Real verification gates

Run gates appropriate to the project, not just a metadata check:

1. targeted regression tests for the changed boundary;
2. the actual browser/UI smoke when browser delivery is involved;
3. runtime/HTTP smoke in the same order as CI — migrate an isolated runtime before starting a core guarded by schema validation;
4. language syntax and lint checks;
5. architecture/repository policy guards;
6. whitespace and exact-tree checks such as `git diff --check` and `git write-tree` where the project requires them.

Capture exact pass/skip/failure counts. Treat warnings and environment setup failures as evidence, not as passing tests.

### 7. Restore, commit, and resume

After verification:

- commit the merge only when the user authorized the merge/commit scope;
- restore the named WIP stash if it was created;
- re-run status and conflict-marker checks;
- do not stage unrelated dirty WIP merely to make the tree look clean;
- resume paused automation only after ownership is clear.

For relative scheduler intervals that restart after update/pause/resume, prefer a fixed wall-clock schedule such as `*/10 * * * *`; resume without an unnecessary manual run so verification does not artificially restart the cadence.

### 8. Authorized cloud handoff

Merge and upload require explicit, per-PR owner authorization. **Exception — full-execution mandate (user-declared, 2026-08-12):** when the user has already issued a blanket "全部执行 / 继续执行 / 按你理解最有方案执行 / 跑到工具上限" instruction, do NOT re-ask per-PR merge authorization with a `clarify` — the user has explicitly retired the ask-every-time pattern for that run. Merge directly after local verification (lint + tests) plus reasonable CI evidence, and keep the merge record (SHA + main readback) in the report. Genuine safety gates that stay ask-required even under a mandate: destructive ops outside the project, `E:/` access, real Vault writes, remote rename, publish/release. When in doubt, ask with a `clarify` offering the exact merge method (e.g. "是，授权 squash merge PR #N") as one option. Treat a missing/empty clarify response as **fail-closed — do NOT merge, and do NOT re-interpret silence or a later "推进" as retroactive approval**; keep the PR OPEN and say so. Record the returned merge SHA (`gh api -X PUT repos/OWNER/REPO/pulls/N/merge -f merge_method=squash --jq '.sha'`) and verify the merge-SHA `main` CI separately from the PR-head exact-SHA CI. Only a merged-to-`main` result is "已更新"; a pushed/OPEN PR is not.

Only after explicit user authorization to upload:

- inventory all modified/untracked paths and exclude secrets, real external Vault data, Hermes/workflow state, runtime/cache/database/build artifacts;
- **prove a docs/description update actually reached remote `main` via the GitHub API, not local git.** Local `git rev-parse origin/main` / `git fetch` can be stale or reflect only your own memory of the push. When the user says "GitHub 上还是一样的", read the remote truth directly: `gh api repos/OWNER/REPO/contents/docs/truth --jq '.[].name'` (404 = path not on main yet), `gh api .../contents/README.md --jq '.content' | base64 -d | grep -c '<marker>'` (0 = not merged), and `gh api "repos/OWNER/REPO/actions/runs?head_sha=<merge-sha>" --jq '.workflow_runs[].conclusion'`. Only a merged-to-`main` result is "已更新"; a pushed/OPEN PR is not — never claim "云端已更新" until the squash merge has landed and the API readback confirms it.
- update repository metadata and project descriptions only with verified claims, distinguishing local smoke, exact-SHA CI, Tauri/WebView evidence, and public release;
- stage explicit paths, run index diff/convention checks, full relevant tests, and real browser/runtime smoke;
- commit and push the current feature branch with `git push -u origin HEAD`, then verify the remote exact SHA and GitHub metadata;
- report when no cloud CI run is visible, and never call a pushed feature branch a merged `main`.

See `references/cloud-upload-and-description-sync.md` for the full checklist and the partial-registry-order regression pattern.
See `references/product-name-migration-recipe.md` for a full-stack display-name/product-identity migration (docs → UI → Rust → tests → smoke scripts → naming registry v3): the five-phase approval ladder, SUPERSEDED banners for historical docs, in-sync surface list, Rust chunked-body hex-length recompute, the `patch`-tool Rust-literal escape corruption, smoke scripts not covered by pytest, and the `git add -A` user-WIP sweep.

## Failure handling

- If a branch contains stale conflicting architecture, do not silently discard it; explain which behavior was already absorbed and which source files were retained.
- If a smoke script requires migration or another setup step, run the canonical setup first and then rerun the smoke; do not label the first setup-order failure as a product regression.
- If targeted tests fail at collection due import-path assumptions, fix the import boundary or invoke the repository's canonical test environment; do not bypass collection and claim verification.
- If lint exposes pre-existing dirty-WIP defects, fix only the scoped defects needed for the requested gate and keep the remaining WIP boundary explicit.

## References

See `references/dirty-worktree-merge-and-smoke.md` for a concise command recipe and evidence checklist distilled from a Windows project merge.
See `references/cloud-upload-and-description-sync.md` for explicit-path bulk upload, public-description synchronization, secret/runtime boundaries, remote exact-SHA verification, and partial-registry-order regressions.
See `references/axdesk-and-windows-ci.md` for the A2/A3 workspace delivery sequence, post-merge main readback, and the Windows desktop-shell retry rule.

### Branch protection: single-owner deadlock + linear-history merge rejection

When a repo enables `main` branch protection, two non-obvious GitHub behaviors routinely block the very merge you are trying to land:

1. **`required_approving_review_count: 1` deadlocks a single-owner repo.** GitHub refuses author self-approval with HTTP 422 `Review Can not approve your own pull request`. On a repo where one account owns everything there is no second reviewer, so the PR is stuck `REVIEW_REQUIRED` / `mergeStateStatus=BLOCKED` forever. The fix is not a human workaround — it is to set `required_approving_review_count: 0` and let the mandatory required status check (e.g. `aggregate`) be the quality gate. Verify the repo is single-owner BEFORE enabling a review requirement.
2. **`required_linear_history: true` rejects merge commits.** `gh pr merge --merge` fails with GraphQL `Merge commits are not allowed on this repository.` even when the repo setting `allow_merge_commit=true`, because linear-history protection overrides it. Use `--rebase` (preserves individual commits, satisfies linear history) or `--squash` (collapses to one) instead.
3. **A local worktree holding the base branch name breaks `gh pr merge` before it reaches the remote.** `gh pr merge --squash` shells out to `git` and fails with `fatal: 'main' is already used by worktree at 'D:/...'` when ANY worktree (e.g. an isolated build/verification checkout) currently has `main` checked out. This is a **local** collision — the PR is still healthy and mergeable; do not delete the worktree or treat it as a repo problem. Merge through the REST API instead (still requires the explicit merge authorization):
   ```bash
   gh api -X PUT repos/OWNER/REPO/pulls/NUMBER/merge -f merge_method=squash --jq '{merged, sha}'
   ```
   Then verify: `git fetch origin main && git rev-parse origin/main` equals the returned `sha`, and `gh pr view NUMBER --json state,mergeCommit` shows `MERGED`. Note this API merge does NOT auto-delete the remote head branch, so also confirm whether branch deletion was expected.

Canonical close sequence for a protected single-owner repo:

```bash
# set protection (approval 0, aggregate as the enforced check, linear history, block force-push/delete)
python - <<'PY' | gh api repos/OWNER/REPO/branches/main/protection --method PUT --input -
import json; print(json.dumps({
  "required_status_checks": {"strict": True, "contexts": ["aggregate"]},
  "enforce_admins": True,
  "required_pull_request_reviews": {"dismiss_stale_reviews": True,
    "require_code_owner_reviews": False, "required_approving_review_count": 0,
    "require_last_push_approval": False},
  "restrictions": None, "required_linear_history": True,
  "allow_force_pushes": False, "allow_deletions": False, "block_creations": False,
  "required_conversation_resolution": True, "lock_branch": False, "allow_fork_syncing": False}))
PY
# merge the PR with rebase (linear history compatible)
gh pr merge PR_NUM --rebase --delete-branch
```

Always read back `gh api repos/OWNER/REPO/branches/main --jq .commit.sha` and confirm the post-merge exact-SHA workflow run reaches `success` on `main`. The PR run and the merge-commit run are separate evidence records.

### Exact-SHA CI and flaky Windows desktop gates

- A watch timeout (`124`) is not a CI conclusion. Read the run's `status`, `conclusion`, `headSha`, and every job independently before classifying it.
- **`gh pr checks` saying "no checks reported" while `mergeStateStatus=CLEAN` is NOT verification — it is the branch never having run CI at all.** Merging such a PR is safe from a merge-state perspective but defers the entire lint/test debt to the NEXT PR that does run full CI (typically the following branch, where all the skipped lint errors surface at once). Real failure (2026-08-11): PR #83 (bake-off framework) showed "no checks reported ... FINAL: CLEAN" and was merged; PR #84's full CI then failed on 14 ruff errors in #83's files (N806 uppercase locals, B904 missing `raise ... from None`, E741 ambiguous `l`, N814 camelcase import alias). Recovery took a whole extra PR cycle. When `gh pr checks` reports "no checks reported", run the repo lint locally before merging (`uv run --frozen --only-group ci python -m ruff check app shared`) or expect a forced follow-up lint PR.
- Keep PR-head evidence, merge SHA, and post-merge `main` evidence as separate records. A 9/9 PR run does not prove the merge commit is Green.
- If `desktop-shell` fails at the installed NSIS `WM_CLOSE` lifecycle check while all other jobs pass, read the failed log and compare the failing source line with the last known-good desktop lifecycle commit before editing code.
- When the failure is identical to a previously passing lifecycle gate and the changed slice does not touch desktop lifecycle code, rerun only the failed job. Do not weaken the gate or add a timing workaround without a reproducible source-level regression.
- A rerun is evidence only when the same exact SHA reaches a completed `success`; report the first failure and the successful rerun separately.

### Non-interactive CI polling from a background terminal

`gh pr checks --watch` blocks interactively and its timeout (`124`) says
nothing about the CI conclusion. For agent-driven PR loops (multiple PRs in
one autonomous run), poll the branch's LATEST run in a bounded background
loop instead — validated on ~10 PRs (2026-08-12), every run green:

```bash
for i in $(seq 1 30); do sleep 30
  RUN=$(gh run list --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId')
  CONCL=$(gh run view "$RUN" --json conclusion --jq '.conclusion // "running"' 2>/dev/null)
  echo "run=$RUN concl=$CONCL"
  [ "$CONCL" = "success" ] || [ "$CONCL" = "failure" ] && break
done
```

Launch it with `terminal(background=true, notify_on_complete=true)`, then
block with `process(action=wait, timeout=180)` while continuing other work
(prepare the next PR's tests) — do not sit idle on the wait. Scope by
`--branch` when several PR branches share the runner pool. The `desktop-build`
job routinely outlives a single 180s wait window; poll again rather than
assuming failure. Merge only after `conclusion=success` for the PR branch's
run, and keep PR-head evidence separate from post-merge `main` evidence.

### Canonical-verifier drift when a delivery adds schemas/contracts

When a taskpack/PR adds new canonical schemas or contract IDs (e.g. a new `config-ownership` / `platform-identity` contract), two things routinely go stale together and turn the integration gate red:

1. **The canonical verifier's hardcoded `EXPECTED` dict / `CANONICAL_SCHEMA_PREFIXES`.** e.g. `scripts/ci/verify_contract_catalog.py` keeps a hardcoded `EXPECTED` of known contract ids and a schema-prefix map. Adding a contract to `contract-catalog.json` without adding it to BOTH maps fails `catalog ids must equal [...]; got [...]`.
2. **Any test asserting a hardcoded count string.** e.g. `self.assertIn("CONTRACT_CATALOG_PASS contracts=28 schemas=28", ...)` — this exact-string assertion must be bumped to `30` in the same commit.

Pitfall: these are two separate edits in two files (`verify_contract_catalog.py` + `test_governance_gate.py`). Fixing only the verifier leaves the count-string test red. When a delivery adds schema/contract ids, grep for BOTH the verifier's expected-id list AND any test that hardcodes the resulting count, and update both in the same commit. Also re-run `generate_current_state.py` (and any freshness `--check-current`) so the regenerated `CURRENT_STATE` reflects the new count — otherwise a CI `--check-current` step fails next.

### Post-squash merge: local `main` cannot fast-forward

After `gh pr merge --squash` lands a protected-branch PR, the remote `main` points at a brand-new squash commit whose history is collapsed, so local `main` (still on the feature branch's pre-merge commits) **cannot** fast-forward: `git merge --ff-only FETCH_HEAD` fails with `Not possible to fast-forward, aborting.`. That is expected, not a problem — the feature commits are already absorbed into the squash commit.

### Post-merge remote branch hygiene: `gh pr merge --delete-branch` can leave the REMOTE ref

`gh pr merge --squash --delete-branch` deletes the LOCAL branch but can silently
leave the REMOTE branch behind (ref-deletion failures are not always surfaced).
Over many merges these accumulate — 2026-08-12: one sweep found 62 stale remote
branches (plus one empty orphan and 4 closed-but-never-merged orphans).

- **`gh pr list --head <branch>` returns null for MERGED PRs.** After a merge,
  the PR's head-branch link is dropped, so a bare `--head` query finds nothing
  and every merged branch looks like "no PR". Use `--state merged` explicitly:
  `gh pr list --state merged --head <branch> --json number,mergedAt --jq '.[0]'`.
- Classification sweep (per remote branch, in order):
  1. `gh pr list --state merged --head <b>` → MERGED = safe to delete;
  2. `gh pr list --state all --head <b>` → CLOSED with unique commits
     (`git log --oneline origin/main..origin/<b>`) = orphan — KEEP only if
     its content was never absorbed into main; see the absorption check
     below before deciding; never bulk-delete on "CLOSED" alone;
  3. no PR + 0 unique commits = empty orphan, safe to delete.
- **Squash-merge remnants are a separate class.** A branch whose PR is
  MERGED but still has unique commits (`git log --oneline origin/main..origin/<b>`
  non-empty) is usually the pre-squash history of a squash merge — the
  content already landed in main as ONE collapsed commit. Verified
  2026-08-12 (axw/execution-h0 #71, axw/execution-h1 #72): 8 and 16 unique
  commits respectively, yet `0 files missing from main` → safe to delete.
- **Absorption check — the decisive test for ANY branch with unique
  commits (closed orphan OR squash remnant):**
  ```bash
  # files the branch differs on vs main:
  git diff --name-only origin/main...origin/<b>
  # for each differing file: does main have it at all?
  git cat-file -e origin/main:<file>   # exit 0 = exists on main
  # for files main has: is main a SUPERSET (evolution) of the branch?
  git diff origin/<b>:<file> origin/main:<file>   # diff should be main ADDING/CHANGING, not branch-only content
  ```
  `0 files missing from main` (every differing file exists there, diffs are
  main-side evolution) = content absorbed → safe to delete without Owner.
  Only a file ABSENT from main (e.g. a historical doc snapshot that never
  landed) warrants keeping the branch / surfacing to Owner. 2026-08-12
  sweep: deleted 3 absorbed closed orphans (k2-compat, pdf-runtime-deps,
  a1-violet-core — diffs were main-side SUPERSEDED banners / later deps) +
  2 squash remnants; kept 1 genuine orphan
  (`docs/verification-summary-2026-08-09`, whose VERIFICATION_SUMMARY file
  is absent from main).
- Enumerate ALL stale refs first (merged-branch deletes plus PR-closed
  branches accumulate):
  ```bash
  git ls-remote origin 'refs/heads/feat/*' 'refs/heads/fix/*' 'refs/heads/docs/*'
  ```
  then bulk-classify with the sweep above. Delete confirmed refs one at a
  time via `gh api -X DELETE "repos/<owner>/<repo>/git/refs/heads/<branch>"`
  (works for branch names containing `/`, unlike `git push origin --delete`
  under some credential setups); count successes/failures and re-list after.
- Delete a confirmed ref (plain deletion, not force-push):
  `gh api -X DELETE "repos/<owner>/<repo>/git/refs/heads/<branch>"`.
- After the sweep: `git fetch --prune origin` drops the deleted refs locally —
  but prune may also drop locally-unreferenced refs you did not intend to
  touch, and `git status` can show an unrelated CRLF-dirty fixture again;
  re-check both before reporting a clean tree.
- **Local `git branch -d` says "not fully merged" for EVERY squash-merged
  branch — trust the PR API, not git ancestry (validated 2026-08-14,
  DESIGN-LAB 55→3).** Squash merges collapse the branch history, so git's
  local ancestry check (`branch -d` requires the branch to be an ancestor of
  HEAD) fails for any branch whose PR was squash-merged — `error: the branch
  '<b>' is not fully merged` even though the content is fully on main. The
  authoritative check is the GitHub API `merged_at` field on the closed PR,
  never `git merge-base --is-ancestor` and never `git branch -d`'s verdict.
  Full-repo sweep pattern:
  1. enumerate remote branches via
     `GET /repos/{owner}/{repo}/branches?per_page=100`;
  2. fetch all closed PRs via
     `GET /repos/{owner}/{repo}/pulls?state=closed&per_page=100`;
  3. delete-set = branches whose name ∈
     `{pr['head']['ref'] for pr in closed_prs if pr.get('merged_at')}`;
  4. PRESERVE (a) branches whose PR is CLOSED but `merged_at` is null
     (superseded head kept as history, e.g. PR #51 replaced by #52) and
     (b) branches with NO PR record at all (migration evidence, keep
     conservatively);
  5. local: after API-verified merged, `git branch -D` (force) is CORRECT —
     do not let `-d`'s ancestry refusal block the cleanup;
  6. delete remote refs one at a time via
     `DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}` (REST handles
     branch names containing `/` reliably);
  7. then `git fetch --prune origin` clears the stale `origin/*` refs — but
     only AFTER the REST deletions; prune does not remove refs whose remote
     branch still exists (and API squash-merge does NOT auto-delete the head
     branch, so without the explicit delete step the refs stay forever).
  A 55-branch repo with 52 merged-PR remnants cleaned to 3 (main + 1
  no-PR migration branch + 1 unmerged #51) in one sweep, 51 REST deletes with
  zero failures — batch the deletes with a small sleep between calls.

### Multi-PR delivery trains: cross-PR dependency deltas, shared worktree, rebase force-push

When one TaskPack ships as several sequential PR batches (A adds a file B must
touch, B's file C extends), the batches form a dependency train. Validated
2026-08-13 (WORK-LAB WLG TaskPack, PRs #81→#82→#83 + archive #84):

1. **Branch each batch from `main` at its own point; rebase later batches onto
   the merged `main` BEFORE their CI matters.** A batch that only touches a
   file an earlier (still unmerged) PR introduced must NOT carry that whole
   file. Keep only the delta, then after the dependency merges, `git rebase
   origin/main` and re-apply the delta (`git checkout origin/main -- <file>`
   resolves the resulting conflict to the dependency's version, then re-add
   your 1-2 line delta). This keeps the dependent PR's diff minimal and its
   CI honest against the real base.
2. **Rebase resolves `CURRENT_STATE`-style generated-file conflicts by
   REGENERATING, not by choosing a side.** Two batches both regenerate the
   same projection → conflict. Fix: `python scripts/ci/generate_current_state.py --root .` (the canonical generator) and `git add` its output — never hand-merge the JSON.
3. **A pre-commit hook that auto-stages + regenerates state contaminates
   cross-branch commits.** If `.githooks/pre-commit` runs `git add` on all
   tracked changes and regenerates CURRENT_STATE, an ordinary `git commit`
   on branch B silently sweeps branch A's unstaged edits into B's commit
   (observed: WLG-080's rename landed in a WL-PR-A commit). Use
   `git commit --no-verify` when you must control the exact staged set, and
   **stash/backup before every branch switch** (`git stash -u`, or `cp` the
   changed files to the ignored runtime dir) — a shared worktree carries
   uncommitted edits across `git checkout`.
4. **`--force-with-lease` after rebase makes the PUSH-event CI run fail on a
   dead `before` sha — that is a trap, not a code bug.** GitHub's push-event
   workflow computes `git diff "$BEFORE_SHA" "$HEAD_SHA"`; after a force-push
   `before` is the pre-rebase sha that no longer exists, so "Discover changed
   paths" (or equivalent) fails and `aggregate` turns red. The **pull_request**
   run for the same head stays green. Read only the pull_request run's
   check-runs for the merge decision. If branch protection still blocks on the
   stale push run: push an empty commit (`git commit --allow-empty -m "ci:
   retrigger"`) to supersede it, or merge via REST while the pull_request
   checks are green.
5. **Merge a fully-green dependent PR via REST** when `gh` is unavailable
   (uninstalled / shim dead) — see the branch-protection section: `curl -X PUT
   repos/OWNER/REPO/pulls/N/merge` with a bearer token from
   `git credential fill` (host=github.com) and `{"merge_method":"squash"}`.
   Then sync local main with `git reset --hard origin/main` when the local
   pre-squash commit and the remote squash commit are byte-identical
   (`git diff HEAD origin/main --stat` empty) — ff-only fails by design after
   squash merges.

### Sequential merges of INDEPENDENT parallel PRs: generated-file conflicts + the new-head CI trap

When several independent PRs (no shared code regions) are merged one after
another in one run, EVERY subsequent merge can come back
`GitHub API HTTP 405: Pull Request has merge conflicts` — even though the
code auto-merges cleanly. Root cause: each PR regenerates the digest-scoped
projection (`CURRENT_STATE.json/.md`), so the generated files ALWAYS conflict
between any two PRs regardless of code overlap. Validated 3× in one session
(2026-08-15, PRs #111→#112→#113→#114): `canonical_store.py` auto-merged fine;
only the generated pair conflicted.

The merge-based resolution loop (differs from the rebase variant above):

```bash
git switch <pr-branch> && git merge origin/main      # conflict ONLY in CURRENT_STATE.*
git checkout --theirs 00-governance/generated/CURRENT_STATE.json 00-governance/generated/CURRENT_STATE.md
git add 00-governance/generated/CURRENT_STATE.json 00-governance/generated/CURRENT_STATE.md
# EXPECTED: `--check-current` now FAILS with `source-digest-mismatch` —
# theirs' digest predates YOUR branch's code. That failure is the signal to
# REGENERATE, not a problem to chase:
python scripts/ci/generate_current_state.py            # writes the merged-tree digest
git add 00-governance/generated/CURRENT_STATE.json 00-governance/generated/CURRENT_STATE.md
git commit -m "merge origin/main (<latest PR>) into <branch>"
git push origin <branch>
```

Then the merge endpoint rejects AGAIN with
`HTTP 405: Required status check "aggregate" is expected` — the NEW head's CI
has not run yet. Start a wait-runs poll on the new head, and only merge once
its exact-head runs are terminal-success. This makes each sequential PR cost
one extra merge-origin/main + one fresh CI cycle; budget for it when stacking
parallel PRs.

API facts that waste turns if missed (all hit 2026-08-15):

- The merge endpoint requires the FULL 40-char SHA: `--sha 90d730a` →
  `HTTP 422: The sha parameter must be exactly 40 characters`.
- A `runs`/`wait-runs` query with a short SHA returns EMPTY `[]` — resolve the
  full SHA (`git rev-parse origin/<branch>`) before querying.
- `wait-runs` exiting `1` with `The read operation timed out` /
  `timed out waiting for exact-head runs` (or a burst of `{}` responses) is a
  POLLING timeout, NOT a CI failure — confirm with one explicit `runs`
  query before classifying the PR.
- Order matters when both remaining PRs are green: merge the one whose base
  is the current `main` first, so the other absorbs one conflict resolution
  instead of two.
- **A wait-runs process for a SUPERSEDED head exits `1` later — treat the
  notification as a stale drain, not a new event.** After a branch moves to a
  new head (fix push, conflict-resolution merge), the old head's wait-runs
  keeps polling until its timeout and then exits `1` with
  `timed out waiting for exact-head runs` / a burst of `{}` lines. Same for
  a wait-runs on a branch whose PR already merged and was deleted. When such
  a notification arrives, verify the CURRENT head's runs before acting —
  usually no action is needed. Only the LATEST head's wait-runs is meaningful.
- **Fetching CI job logs via REST: the token from `git credential fill`
  needs `cwd=<repo-root>` (otherwise `InvalidAuthenticationInfo` 401), and
  even then `actions/jobs/<id>/logs` can 401 (needs a `read:actions` scope
  the credential-manager token typically lacks) while
  `actions/jobs/<id>` (step conclusions) works fine.** So: use the jobs
  endpoint for step-level pass/fail triage; fall back to local reproduction
  for log text. `git credential fill` is host- and cwd-sensitive — always
  pass `cwd` to the subprocess or the wrong (or no) credential is returned.

### CI workflow-run gates: actionlint+shellcheck and cross-platform test collection

**actionlint's shellcheck integration is OFF in a plain local run but ON in the CI action** (`rhysd/actionlint`). A workflow edit can pass `actionlint` (exit 0, silent) yet fail the CI `supply-chain-security` job's actionlint step. Reproduce locally with the exact CI semantics: `actionlint -shellcheck=/path/to/shellcheck .github/workflows/<file>.yml` — plain actionlint alone cannot see shellcheck diagnostics, so "actionlint clean locally" proves nothing.

Real failure (WORK-LAB PR #113, 2026-08-15): `git rev-parse HEAD^{tree}` inside a run block triggered shellcheck SC1083 ("This { is literal") ×2 + SC2034 (EXPECTED_HEAD_TREE appears unused) + SC2155 (declare and assign separately). Shellcheck warnings count as actionlint failures (exit 1). Fix pattern:
```bash
EXPECTED_HEAD_TREE="$(git rev-parse 'HEAD^{tree}')"
export EXPECTED_HEAD_TREE
```
single-quote the ref (kills SC1083), assign and export in separate statements (kills SC2155, and the separate export kills SC2034). Local repro downloads (Windows): actionlint `actionlint_1.7.12_windows_amd64.zip` + shellcheck `shellcheck-v0.10.0.zip` from their GitHub releases, unzip into `.hermes/task-runtime/`.

**New test files run on CI even when the workflow job does not list them.** The workflow-assistance job's `run_quality_gate.py governance` runs `python -m unittest test_*` over the whole tests dir (sets `PYTHONPATH=<ROOT>/tests`), so a brand-new test file absent from the job's explicit `python tests/test_x.py` lines STILL executes on CI. Consequences (both hit 2026-08-15, PR #115):

1. **Windows-only probes must be mocked, never left to the real environment.** `os.name != "nt"`-guarded functions (`_hermes_gui_launcher`, `_windows_start_menu_shortcuts`, ...) return None/[] on ubuntu runners, silently failing assertions written against Windows behavior. Mock the probe (`mock.patch.object(module, "_hermes_gui_launcher", return_value=launcher)`); the test then passes on both OSes.
2. **importlib-loaded modules need an explicit sys.path for sibling imports.** `spec_from_file_location` does NOT add the module's dir to `sys.path`, so a module that `import platform_identity` fails with ModuleNotFoundError under a spec loader even though pytest imports the file fine. `sys.path.insert(0, str(scripts_dir))` before loading.
3. **Two DISTINCT local-test failure modes — do not conflate them.** (a) **Hermes-venv PYTHONPATH pollution**: `uv run` inherits the ambient `PYTHONPATH` pointing at the Hermes venv, producing `ModuleNotFoundError: No module named 'rpds.rpds'` (jsonschema stack) or spurious sidecar/`_revision` test failures. Fixed by `env -u PYTHONPATH`. (b) **A genuinely empty `uv run --project` env**: a module with NO `pyproject.toml` (e.g. `10-workflow/workflow-assistance/`) makes `uv run --project <dir>` create an env WITHOUT its `requirements.lock` deps — `import yaml`/`import jsonschema` are `None` even AFTER `env -u PYTHONPATH`. This one is NOT a PYTHONPATH problem. It surfaces as `run_quality_gate.py`'s `dependency_preflight()` (`importlib.util.find_spec("yaml")`/`"jsonschema"`) printing `QUALITY_GATE_DEPENDENCY_FAIL missing=PyYAML...,jsonschema...` and exiting 2. CI is unaffected because its job does `python -m pip install -r requirements.lock` with system python, not `uv run --project`. To reproduce gates locally: either `pip install -r requirements.lock` into the active python first, or bypass the gate and run the specific test file directly (`env -u PYTHONPATH uv run --frozen pytest <file>` — pytest itself resolves; only the `run_quality_gate` dependency-preflight needs the pip-installed deps). Wrapper form: `python <wrapper> run -- env -u PYTHONPATH uv run --project ... --frozen pytest ...`.

### Verify a PR head in the REAL repo checkout, not a nested worktree

Before merging a PR whose branch adds or touches path-sensitive workflow/gate code (WORK-LAB 2026-08-13, PR #80), running the canonical quality gate inside a verification worktree under the ignored dir (`git worktree add .hermes/task-runtime/<name> origin/pr-<n>`) produces **false failures**: the gate's `ROOT = Path(__file__).resolve().parents[2]` resolves into the nested worktree, `machine_identity._project_root` fails to walk up to the monorepo root from inside `.hermes/…`, and `sync_hermes_workflow_assets.replace_managed_skill_trees`'s `shutil.copytree` hits nested-path assumptions. Every one of those passed in the real checkout on the SAME head. Do not chase these as PR bugs, and do not present them as PR failures to the user.

Proven verification path (main-branch baseline `git diff`/`merge-base` first, then):

```bash
git fetch origin pull/<n>/head:refs/remotes/origin/pr-<n>
git branch -f test-pr< n >-verify origin/pr-< n >   # local only, never pushed
git checkout test-pr< n >-verify
# run the canonical gates from the REAL repo path (e.g. workflow-assistance/)
PYTHONDONTWRITEBYTECODE=1 python scripts/workflow/run_quality_gate.py governance compile runtime-convergence
git checkout main && git branch -D test-pr< n >-verify
```

Also note the quality-gate test discovery contract: `run_quality_gate.py` sets `PYTHONPATH=<ROOT>/tests` and runs `python -m unittest -v test_*` from `ROOT` — replicate that env (`PYTHONPATH='<repo>/10-workflow/workflow-assistance/tests'`) or `-m unittest` reports `ModuleNotFoundError: No module named 'test_*'` even though the file imports fine by path. Clean up the abandoned worktree dir afterwards (`git worktree remove --force`, retry `rm -rf` if a held handle keeps it busy).

### Delivering a change when the canonical workspace has drifted from `main`

A recurring pattern when the canonical local branch has accumulated commits that already landed in `origin/main` (identical tree, different SHAs — e.g. a long autonomous-run session merging PR after PR): rebasing the canonical branch onto `main` produces conflicts or a no-op, and `git worktree add` may refuse `main` because an old worktree holds it. Do NOT fight the drift. The proven delivery path (used repeatedly 2026-08-12, PRs #88–#93):

1. Commit the change in the canonical workspace: `git add <explicit paths> && git commit -m "..."`.
2. Create a fresh worktree on `origin/main` and cherry-pick that one commit:
   ```bash
   git worktree add -b <branch> .hermes/task-runtime/<name> origin/main
   cd .hermes/task-runtime/<name>
   git cherry-pick "$(cd <canonical-root> && git log -1 --format=%H)"
   ```
3. Push + PR: `git push origin HEAD:<branch>` then `gh pr create --base main --head <branch> ...`.
4. Watch CI; merge (squash) from the worktree; then clean up:
   ```bash
   cd <canonical-root> && rm -rf .hermes/task-runtime/<name>
   git worktree prune && git branch -D <branch>
   ```
5. Verify canonical == main: `git diff origin/main --stat` shows 0 lines when the tree is identical.

The same commit SHA is available with `git log -1 --format=%H -- <path>` for path-scoped picks. Never `git add .` from the canonical workspace — user WIP fixtures (e.g. `tests/fixtures/readability_article.html`) re-dirty with CRLF/LF normalization after test runs and must be restored with `git checkout --` before committing.

The reliable close sequence (works whether or not a local worktree holds `main`):

```bash
git fetch git@github.com:OWNER/REPO.git main        # or: git fetch origin main
git checkout main                                   # if not already on it
git reset --hard FETCH_HEAD                         # align local main to cloud squash SHA
# verify dual-end exact-SHA
git rev-parse main
git ls-remote git@github.com:OWNER/REPO.git main | awk '{print $1}'
```

Notes:
- `git reset --hard FETCH_HEAD` works even when `main` is the current worktree branch (unlike `git branch -f main FETCH_HEAD`, which fails with `cannot force update the branch 'main' used by worktree`).
- Because squash merges delete the remote head branch, run `git remote prune origin` and `git branch -D <feature>` locally if the remote auto-delete didn't clear the local ref.
- Report dual-end exact-SHA equality as the "本地云端一致" proof.

### `-X ours` vs `-X theirs` direction in a conflict merge (relative to the CURRENT branch)

When resolving a divergent branch merge with `-X`, the words are relative to the branch you are **currently on**, not which branch you want to win:

- On branch `feature`, `git merge -X theirs main` makes **`main` (the incoming side) win**. If you wanted YOUR `feature` content to win, this is backwards and silently resurrects the opposing content.
- On branch `feature`, `git merge -X ours main` makes **`feature` (your current side) win** — `ours` = current branch, `theirs` = incoming branch.

Real failure (WORK-LAB, 2026-08-11): while on a `revert-open-design-boundary` feature branch trying to absorb an opposing `main`, I ran `git merge -X theirs main`, expecting my branch's correct content to win. Because `theirs` = `main`, the WRONG direction content (the very fields I was reverting) came back into the tree and `AGENTS.md`/`config-ownership.json` flipped to the opposite semantics. Fix: `git reset --hard <my-clean-sha>` to drop the bad merge, then `git merge -X ours main` so the feature branch wins. **Always verify field markers by content after ANY `-X` merge** (e.g. `grep -c 'design_capability' config-ownership.json`), never trust that the flag did what you intended — its meaning depends on which branch you ran it from.

### GitHub repo rename (packaging/identity step-2): cache, path, and gate traps

Executed 2026-08-12 on Cognitive-Loop-OS (`Cognitive-Loop-OS` → `archeaxis-workspace`, PRs #131–#135). Step-1 (display names) is covered in `references/product-name-migration-recipe.md`; these are the step-2 traps that only appear once the REPO itself is renamed:

1. **`actions/cache` payloads pin the old runner checkout path.** After `gh repo rename`, cached Rust `target/` (and any cached path-based content) references the pre-rename checkout dir (`D:\a\Cognitive-Loop-OS\...`). desktop-fast/build then fail with `os error 3` reading `...\target\debug\build\tauri-...\out\permissions\...\app_hide.toml` — the build dir moved, the cache payload didn't. **Bumping only the cache `key` is NOT enough**: the `restore-keys` prefix fallback (e.g. `${{ runner.os }}-cargo-`) still resurrects the stale payload. Bump BOTH the key AND the restore-keys prefix (e.g. `-naming-v2`) in the same edit, or the identical failure recurs on the rerun. First cold build after invalidation takes 15–25 min for desktop jobs — slow ≠ hung; check the active step name (`gh api .../actions/jobs/<id> --jq '.steps[] | select(.status=="in_progress") | .name'`) before assuming failure.
2. **A repo-name sweep also rewrites LOCAL absolute paths that did not move.** Replacing `Cognitive-Loop-OS` → `archeaxis-workspace` across docs/code rewrites `D:\All projects\Cognitive-Loop-OS` fixture paths too (the on-disk directory was NOT renamed). Silent symptom: tests reading those paths skip (e.g. `test_workspace_pdf_endpoint.py` "no real PDF fixture present" — 1461 passed → 1459 passed + 2 extra skips). Recovery: `git grep -l 'All projects/<newname>'` and restore the real directory name. Always exclude local absolute paths AND the naming contract's legacy-mapping table (which must KEEP the old name) from name sweeps; verify test skip counts before/after.
3. **Parallel-session direct pushes to main can violate the repo gates and block every PR.** Another session pushing straight to main (e.g. `feat(osui)` commits, no PR gating) can ship files that fail `check_repository_conventions.py` (34× `missing-final-newline` on `*.artifact.json`). Every subsequent PR's lint/a0-gates then fails with a BASE-induced defect, not a PR defect. On seeing an unexpected cloud main SHA: inspect the new commits' file scope, run the convention gate on the merged tree, and ship a mechanical repair PR (append `\n`) FIRST; merge the fix, THEN rebase/re-run the blocked PRs on the clean main. Merge order matters — merging a PR whose only red job is a base-induced lint failure is still merging red.
4. **`git fetch` over SSH can hang (`early EOF` / `invalid index-pack`).** Workaround that keeps the origin ref fresh without touching the SSH remote: `git fetch https://github.com/OWNER/REPO.git main:refs/remotes/origin/main`. The remote config stays SSH; the one-off HTTPS fetch only updates the ref.
5. **`gh pr merge` inside a worktree fails when another worktree holds `main`** (`fatal: 'main' is already used by worktree at ...`) — use the REST API: `gh api -X PUT repos/OWNER/REPO/pulls/N/merge -f merge_method=squash`. (Full branch-protection context in the earlier section.)
6. **Working-directory drift between terminal calls is a user-corrected hazard.** The session cwd can silently land in a SIBLING project (`D:/All projects/WORK-LAB`, `.../OPEN-DESIGN-Assistance`) even when `workdir` was passed — the user has corrected this harshly ("别在漂移了"). Every repo-touching command must begin with an explicit `cd "<canonical-root>"` (or worktree path) and the same invocation should `pwd`/`git status` to confirm where it ran; never rely on the previous call's cwd.

### Dependency lock drift: phantom package names and never-locked deps

`pyproject.toml` can declare a package name that does not exist on PyPI (real failure 2026-08-12: `httpx2` instead of `httpx`). uv.lock carries the phantom name in a requires list while the real package is pulled in transitively, and CI `uv export --frozen` keeps working — so nothing flags it until you inspect the lock. Separately, deps added to pyproject in one PR are sometimes never re-locked (manually installed only): the lock silently misses them (2026-08-12: faster-whisper + rapidocr-onnxruntime added in #98/#99 but never locked until a later `uv lock`).

Detection and repair sequence:

```bash
grep -n "<name>" uv.lock        # phantom: in a requires list, but NO `name = "<pkg>"` package entry
uv lock                          # regenerate; watch the Added/Removed lines for unexpected churn
```

After regenerating the lock, ALWAYS re-run the manifest-digest test (e.g. `tests/test_release_manifest.py`): release manifests record the sha256 of uv.lock and must be bumped (digest + revision+1) in the SAME commit, or the full suite turns red on a stale digest.

Two gates that routinely bite after touching the lock/manifest:

1. **`missing-final-newline` conventions-gate failure on regenerated JSON.** Writing `release-manifest.json` via `write_text` without a trailing `\n` trips the repository conventions gate (`missing-final-newline: text must end with LF`). Append `\n` before committing. If CI already failed on it, amend the unmerged PR commit and force-push (`git push origin HEAD:<branch> --force` — fine for unmerged PR branches; the new run is fresh evidence).
2. **Conventions gate locally must use `--source head`.** A bare run of the repo conventions script checks the WORKING TREE — on Windows with `core.autocrlf=true` every file reads CRLF on disk, producing false CRLF hits while CI (which checks git blobs via `--source head`) stays green. Match CI: `python scripts/check_repository_conventions.py --source head`. Disk CRLF is autocrlf's checkout artifact, blobs are LF — do NOT "fix" tracked files over it.

CI infrastructure transient (not code): `self-signed certificate` / `Github API request failed while getting latest release` inside the `Set up uv` step is GitHub Actions infrastructure failing to reach its own API — every other job can be green and the failure is unrelated to the diff. Wait for the run to complete, then `gh run rerun <run-id> --failed`; merge only on the rerun's success.

### Activating previously-excluded test dirs: testpaths + DB isolation

A repo with `testpaths = ["tests"]` in `[tool.pytest.ini_options]` silently never collects tests in any other directory — fully written, never run (2026-08-12: `knowledge_base/tests/` held 38 dead tests). Fix = add the dir to `testpaths` AND provide isolation, or the newly-activated tests break under the full suite:

- Tests sharing the real SQLite DB (e.g. FTS candidate count assertions) fail when the full suite leaves documents behind. A conftest that COPIES the real DB fails too — the pollution is copied along. The working pattern is a per-test FRESH empty DB:
  ```python
  @pytest.fixture(autouse=True)
  def _isolated_db(tmp_path: Path) -> None:
      real = Path(storage.DB_PATH)
      target = tmp_path / "cognitive_os_test.sqlite"
      storage.DB_PATH = target
      storage.init()          # creates IR_KB_TABLES incl. FTS5 virtual tables (IF NOT EXISTS)
      yield
      storage.DB_PATH = real
  ```
- Verify the whole suite goes green before claiming the tests are "activated" — `knowledge_base/tests/` alone passing is not enough; the full-suite run is what exposes cross-directory DB pollution.

### Ledger-driven tests catch compliance leaks

A test that computes a set (e.g. REVIEW-BLOCK components from a supply-chain ledger) but asserts a hard-coded subset silently rots: the computed set becomes dead code and the assertion misses NEW blockers leaking into default engine chains. Drive the assertion FROM the computed set (`for name in blocked: assert name not in chain`), keep the hard-coded list only as a guard that each known blocker is still in the ledger, and fix stale guard names against the ledger's actual values (2026-08-12: the guard listed `zotero`, which was never REVIEW-BLOCK — the assertion only passed because the computed set was unused). Real catch: `marker-pdf` registered as a default PDF engine while the ledger marks Marker REVIEW-BLOCK (modified OpenRAIL-M weights). After fixing the flagged one, scan ALL blocked components across code AND docs — not just the flagged name.

### Wiring a scheduler in: grep for hard-coded schedule values first

When connecting a scheduler module to an existing call path, check whether the target writes hard-coded schedule values (`interval_days=1, ease_factor=2.5, next_review_at=now`) — the loop may have never actually scheduled (2026-08-12: `record_practice_evidence` inserted kb_reviews with fixed one-day cadence; SM-2 never ran). Wire the real scheduler and assert interval GROWTH in tests (quality=5 consecutive → `[1, 6, 16]`), not just row presence.

### Delivery hygiene during long autonomous runs: placeholders, frozen-task audits, handoff drift

Three repository-hygiene patterns that surface in long "continue until done" runs (validated 2026-08-12, PRs #124-#130):

1. **Dead placeholder shells rot silently — sweep for them.** After a stretch of delivery work, scan for empty/dead modules: 0-byte non-`__init__` `.py` files (`wc -c`) and docstring-only shells (a file whose whole body is `"""..."""`). Verified: `knowledge_base/taskpack/builder.py` + `context_pack/builder.py` were docstring-only shells while the real `build_taskpack`/`build_context_pack` lived in the package `__init__.py` — zero imports, safe to `git rm`. BEFORE deleting, prove zero references (`grep -rln <basename> app/ shared/ knowledge_base/ tests/`), and distinguish legitimate tiny files: design-index READMEs (title + `> Ref:` line) are navigation, not placeholders — keep them. For genuinely deferred modules (0-byte, referenced by a future blueprint), add a `DEFERRED` docstring naming what it is reserved for rather than deleting — an empty module misreads as a working implementation.
2. **Frozen-baseline task status audits: mark PARTIAL, never fabricate PASS.** When auditing frozen-baseline tasks against current code (e.g. AXW-023A-F adapters, AXW-040+ vault C4, AXW-051 learning), implementation + source tests ≠ frozen acceptance. Frozen gates demand exact-SHA installation evidence (real Windows install, installer lifecycle, readback). Record an evidence TABLE per task (`ID | 格式 | 实现 | 契约测试 | 安装态证据`) with `PARTIAL` where source evidence exists but installation evidence doesn't, and leave the EXIT-gate verdict to the Owner/release flow. Writing "已完成" off source tests alone is the exact false-PASS the authority contract forbids.
3. **Historical handoff docs keep their authoring-date decision state — append a note, don't rewrite.** A handoff written 2026-08-09 saying "PR #72 未 merge（未授权）" stays true-to-date even after #72 merged (it records the fail-closed decision at that time). Don't rewrite history (append-only rule); prepend a `> **后续更新（date）**` note stating the later fact (merge SHA, branch cleanup) and pointing to EXECUTION_STATUS_LOG as current truth. Same pattern as SUPERSEDED banners for old product docs, but for handoffs the note is the migration pointer, not a deprecation.

Also: the append-only status log can accumulate duplicate entries across context compactions (`### LOG-...` for the same PR twice). Grep for duplicate log numbers and dedupe, keeping sequence contiguous — a log with dupes reads as two different events.

## Completion checklist
- [ ] Source branch and merge scope confirmed from live Git state
- [ ] Concurrent writers paused and later resumed
- [ ] Dirty WIP protected and restored
- [ ] Actual merge completed or a justified no-op ancestry merge recorded
- [ ] Conflict resolution preserved functional freshness
- [ ] Targeted tests and runtime/browser smoke actually executed
- [ ] Lint/static/architecture/whitespace gates recorded
- [ ] Commit/tree identity and remaining dirty state reported honestly


## 合并来源: risk-selective-ci-gating (2026-08-21 合并优化)

---
name: risk-selective-ci-gating
description: "Design deterministic path-classifier CI that fails closed."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ci, github-actions, gateplan, classifier, fail-closed, selective]
    related_skills: [ci-release-triage, workflow-verification-and-risk-controls, audited-project-delivery]
---

# Risk-Selective CI Gating

## Purpose

Design and debug a deterministic changed-path risk classifier that decides which
CI gates run per change, while keeping a stable aggregator verdict and failing
closed on any uncertainty. Use when a repo wants ordinary PRs to stop paying the
full-matrix cost (desktop/installer/browser/windows) but must never silently skip
a required gate.

This is the *builder's* skill (make the classifier and routing correct). Use
`ci-release-triage` for diagnosing already-failed release trains, and
`workflow-verification-and-risk-controls` for fail-closed verification of the
resulting pipeline.

## Core architecture

1. **Deterministic classifier** — pure function `path -> {risk_class, gate set}`.
   Never let an LLM decide required gates; only a versioned path→gate matrix may.
2. **GatePlan artifact** — JSON with `matched_classes`, `reason_codes`,
   `unknown_paths`, `required_gates`, `full_qualification`, and a stable digest
   (sha256 over the sorted decision payload). Emit `required_gates` and
   `full_qualification` as job outputs (`$GITHUB_OUTPUT`) so downstream jobs gate on them.
3. **Selective routing** — each heavy job's `if:` runs the job when
   `contains(needs.gateplan.outputs.required_gates, '<gate>')`.
4. **Stable aggregator** (`a0-gates`/`ci-verdict`) with `if: always()` that
   validates the GatePlan: every REQUIRED gate must be `success`; a
   legitimately-not-required gate may be `skipped`; a not-required job that RAN
   and failed is still a failure.
5. **PR-only concurrency** — cancel stale runs for the same PR; never
   auto-cancel main/full/release.

## Fail-closed rules (non-negotiable)

- Unknown path, missing diff, or classifier failure → force `full-qualification`.
- `.github/**`, `.worklab/**`, classifier scripts, lockfiles, release scripts,
  security/permission/schema/migration paths → `full-qualification`.
- CI self-modification must run the full matrix at least once.
- A `CI_FORCE_FULL=true` kill switch only adds validation; it can never skip a gate.

### Variant: unclassified-block (AXC-060 style)

Some repos deliberately relax the unknown-path rule: unknown paths run a safe
default set (`static`+`lint`+`py-primary`), are marked `unclassified`, and the
**merge is blocked until the profile gains a classification** — instead of
paying the full matrix on every new directory. This is still fail-closed
(blocked merge, never silent skip) but trades CI cost for a manual/tooling
classification step. If you adopt it:

- Keep `full-qualification` as a logical stage/RC profile only — never the
  unknown fallback. `force_full` (CI_FORCE_FULL / missing diff / untrusted
  refs) MUST still force full; only *classified-vs-unclassified* paths change.
- The profile needs an explicit `unclassified:` block (`gates` + `action:
  block-until-classified`) so tooling can consume it deterministically.
- Update the RED tests that asserted unknown→full to assert
  unknown→unclassified-block (gates present, `full_qualification is False`,
  no desktop/installer gates). These tests WILL fail after the policy change —
  that is the signal to update them in the same commit.

## Pitfalls (each cost a real CI round-trip)

1. **Leading `**/` globs don't match root files.** `fnmatch` treats `**/*.md`
   as "at least one directory". A root `AGENTS.md`/`README.md` will NOT match and
   becomes `unknown` → forces full. Fix `_path_matches`: when a pattern starts
   with `**/`, strip it and re-match against the bare path too, so
   `**/*.md` covers both `docs/x.md` and root `README.md`. Regression-test root-level docs.
2. **`tests/**` must be an explicit ordinary-python class.** If test files match
   no class they become `unknown` → full. Add `tests/**` to the ordinary-python
   gate set so a test-only change stays light.
3. **`full-qualification` collapses `required_gates` to just `ci-verdict`.**
   If you fold `full-qualification` out of `required_gates` (it's a logical
   profile, not a runnable job), heavy jobs' `contains()` checks go false and
   they WRONGLY skip under full. Every heavy job's `if:` must ALSO run when
   `needs.gateplan.outputs.full_qualification == 'true'`, not only when its own
   gate name appears. Emit an explicit `full_qualification` boolean from the
   classifier — do not infer it from `matched_classes`.
4. **GitHub `pull_request` events check out the merge ref, not the head.**
   A 3-dot diff (`base...head`) can resolve empty or fail there. Use a 2-point
   diff (`git diff --name-only base head`); if the diff is empty while
   `base != head`, or `git diff` errors, force `full-qualification`. Never
   silently treat an empty diff as "no change".
5. **Aggregator must be `if: always()` and depend on `gateplan`.** If the
   aggregator only runs on success, a classifier failure lets the whole check
   disappear (bypass). It must always appear and validate required-gate success,
   allowing only explicit not-required skips.
6. **Values do not survive across `run:` steps.** Each step is its own process;
   a shell/PowerShell variable set in one step is empty in the next. Use a step
   `id:` + `$GITHUB_OUTPUT` to hand any value (run IDs, URLs, digests) to a
   later step. A workflow-contract test should assert the consumer references
   `steps.<id>.outputs.<name>` and the bare variable does not appear past the
   step boundary.
7. **Do not conflate `push` events with an unavoidable full run.** A `push`
   event has no `pull_request.base.sha`, but GitHub provides `github.event.before`
   and `github.sha`; the workflow must use those two-point commit identities to
   compute a trustworthy diff. If the project deliberately requires every main
   push to run full qualification, state that as an explicit product policy and
   measure the cost. Do not accidentally force full because `BASE_SHA`/`HEAD_SHA`
   are empty, because the workflow compares the ref names `origin/main` and
   `HEAD`, or because an empty diff is treated as uncertainty after checkout
   already points at the new main commit. Add a regression for a docs-only push:
   either it must produce the explicitly documented full policy, or it must route
   to the docs/static profile. A selective classifier is not actually selective
   if every main push reaches the full desktop/installer path.
8. **A breaking identity field change must bump `schema_version`.** Splitting
   `ci_run/ci_url` into `verification_ci_run_id` + `release_run_id` while
   keeping `schema_version: 1.0.0` is an undeclared contract break. Ship v2 and
   keep a v1 reader (dual-read) so old artifacts stay readable.
9. **Create the output dir before writing an artifact.** A fresh checkout has no
   `.hermes/`; writing `gateplan.json` there fails with `FileNotFoundError`
   unless you `os.makedirs(..., exist_ok=True)` first. Local runs mask this.
10. **`require()` keys are semantic gate IDs; `needs.*.result` lookups are job
    names — do not swap the two.** The aggregator must gate on the *classifier's*
    IDs (the strings `classify.py` emits from the profile union, e.g. `py-primary`,
    `static`, `lint`), never the GitHub job name (`test`). Requiring `test` is a
    silent no-op: GatePlan never emits `test`, so `grep` never matches and a
    required `py-primary` failure passes as green. Conversely, the
    not-required-but-failed loop iterates job results, which are keyed ONLY by
    job name (`${{ needs.<job>.result }}`), so it must use the real job names
    (`windows-runtime-smoke`, `py-compat`, `lint`, `test`) — a gate ID
    (`windows-runtime`) there silently fails to detect a ran-and-failed job.
    Rules: enumerate the full gate-ID set from the profile's risk_class `gates`
    union (minus `full-qualification`, plus `ci-verdict`) and assert every one
    has a `require <id>`; enumerate every non-gateplan `needs` job and assert
    each appears in the not-required loop under its job name. Reverse-regression
    tests: one asserting `require <semantic-id>` is present for all profile IDs,
    and one asserting `require <job-name>` (e.g. `require test `) is ABSENT.
11. **A dependency-manifest change is not an unknown path — classify it, don't
    fall through to full.** If `requirements.txt` (and `pyproject.toml`,
    `uv.lock`) has no risk_class, it becomes `unknown` and the classifier forces
    `full-qualification` — an over-trigger that makes a selective pipeline
    non-selective on every dep bump. Map `requirements*.txt` into the
    `python-compat` class (alongside `pyproject.toml`/`uv.lock`) so a dependency
    change runs `wheel-smoke` + `py-compat` instead of the whole matrix. When you
    then re-run `uv lock`, also bump the `dependency_lock.digest` + `revision` in
    the release manifest — a packaged-truth test asserts manifest digest == lock
    digest, so a lockfile change without the manifest sync is a real CI failure.
12. **A format-parser file must trigger `wheel-smoke`, not only `py-primary`.**
    Editing the parser/converter (`app/ingestion/*.py`, PDF/Office/OCR engines)
    changes what the *installed wheel* can convert, so the wheel must be rebuilt
    and smoked. If the parser falls into the generic ordinary-python class it
    runs the source suite only and misses install-state regressions. Add a
    dedicated `format-parser` class (paths → `static, lint, py-primary,
    wheel-smoke`), and write a path-mutation regression for each parser file
    asserting `wheel-smoke` is present and `unknown_paths == []`.
13. **First-match-wins ordering: specific classes BEFORE broad globs.** When
    the classifier matches the FIRST risk class whose paths contain the file
    (then breaks), a broad glob class (`ci-policy` with `.github/**`) listed
    before a specific class (`release-workflow` with
    `.github/workflows/release.yml`) silently swallows it — release.yml changes
    never get `release-verify`. Order classes most-specific-first
    (exact paths, then globs), and add a regression asserting each exact-path
    class wins over its broad glob siblings.
14. **Convention gates that check `--source head` read git HEAD, not the
    working tree.** A repo-convention scanner (`check_repository_conventions.py
    --source head`) validates the committed tree: an edit that passes locally
    still FAILS CI until committed, and a fix appears "still failing" until the
    next commit lands. Verify such gates with a commit, or check them against
    the working tree explicitly — never declare "gate green" from a
    working-tree run of a `--source head` gate.
15. **`utf-8-sig` writes add a BOM that repo-convention gates reject.** Writing
    markdown banners/headers with `encoding='utf-8-sig'` prepends a UTF-8 BOM;
    scanners that forbid BOM (`unexpected-bom`) fail CI. Use plain `utf-8` for
    repo text files; if a file already has a BOM, strip the first three bytes
    on rewrite (`raw[3:]`).
16. **CI ruff can fail where local ruff passes (version/config drift).** A
    lint rule (e.g. N817 `CamelCase as acronym` for `ElementTree as ET`)
    fires on CI's pinned ruff but not the local one. Before pushing a
    doc/config refactor, run the EXACT CI lint command locally
    (`python -m ruff check <dirs>`) with the CI-pinned ruff version; when a
    pre-existing violation is intentional, carry `# noqa: <code>` on the line.
17. **Registered gates that GatePlan can require but nothing executes/verifies
    are fail-open phantom gates.** Audit the three-way closure: every gate ID
    the profile can emit into `required_gates` must have (a) a job whose
    `if:` runs when that ID is required (or a job whose condition covers it
    as a superset) AND (b) a `require <id>` entry in the ci-verdict step.
    Session case (LOG-169): four targeted gates (`py-targeted`,
    `format-targeted`, `migration-targeted`, `security-targeted`) existed in
    the registry and the profile emitted them (e.g. `app/ingestion/pdf.py` →
    `format-targeted`), but the test job's `if:` only checked `py-primary`
    and the verdict `require` list omitted all four — a format-parser change
    planned targeted tests that never ran, and the verdict passed regardless
    (fail-open). Fix: extend the test job's `if:` with
    `contains(required_gates, '<targeted>')` for each targeted ID (its full
    suite conservatively covers all targeted semantics) and add
    `require <targeted> "$TEST_RESULT"` to the verdict. Pitfall 10's
    require-list regression test should enumerate gate IDs FROM THE PROFILE
    UNION, not from a hand-maintained list — a new class added later with a
    new gate ID silently re-opens the phantom.
18. **Probe `classify_paths([real_path])` for every semantically-important
    real path — the class's DESCRIPTION is a contract its `paths` list can
    violate.** A class described as "UI resources, interaction, BFF/API
    consumed by UI" that lists only `app/workspace/ui/**` silently
    under-classifies `app/workspace/router.py` (the BFF/API itself) into
    ordinary-python — API changes then never trigger the real-browser gate
    (a silent gap, merge NOT blocked). Likewise the browser-smoke SCRIPT
    itself (`scripts/a0_browser_smoke.py`) matched nothing → unclassified-
    block (fail-closed but its own edits can't re-verify it). Session case
    (LOG-168): add both paths to the ui class; re-probe. Run a probe matrix
    for the paths that matter: UI tree, API router, smoke script, test
    files, each parser/engine file, migration files — assert the expected
    gate set per path and zero `unknown_paths` for anything that has an
    intended class.
19. **Exhaustive per-class probe audit: one real path per class, then triage
    benign FAILs BEFORE touching the profile.** After the semantic probes,
    run the full matrix — for EVERY risk class pick one real repo path and
    assert (a) the class id is in `matched_classes` AND (b) every gate the
    class declares is present in `required_gates`. Three apparent FAILs are
    BENIGN under first-match-wins and must be triaged before editing:
    1) the probe path is swallowed by an EARLIER broader class — re-probe
    with the class's UNIQUE path (e.g. `desktop/src-tauri/tauri.conf.json`
    matches `installer` first, but `desktop/src-tauri/icons/**` is
    desktop-build's exclusive path); 2) the earlier class is a gate
    SUPERSET (e.g. `uv.lock`/`requirements.txt` match `python-compat`
    whose gates include `dependency-change`'s — the dependency class is
    dead but fail-safe); 3) the probe was simply the wrong file for the
    class (e.g. `shared/storage.py` is ordinary Python, not
    windows-runtime). Session case (LOG-170): 16 classes probed, 13 PASS,
    3 apparent FAILs all triaged benign — classification verified
    fail-safe and complete with ZERO profile changes. Dead-but-fail-safe
    classes (fully shadowed by a broader class) are redundancy, not bugs;
    do not churn the profile to delete them.
20. **Jobs without `timeout-minutes` can hang and burn the 360-minute
    GitHub default runner limit.** When auditing a workflow, check timeout
    coverage job-by-job — it is common for desktop/installer jobs to carry
    timeouts while every Python job (`test`, `py-compat`, `lint`,
    `wheel-smoke`, `browser-smoke`, `windows-runtime-smoke`, the verdict
    aggregator) has none. A hung dependency resolve or a stuck pytest then
    occupies a runner for up to 6 hours before GitHub kills it. Fix
    (LOG-173 / `24606db`): add bounded `timeout-minutes` aligned with
    OBSERVED run times (5-10x headroom — CI full ~2-3 min, nightly full
    ~3.5 min → 10-20 min per job), and note which jobs run on
    `windows-latest` vs `ubuntu-latest` while patching (the runner line is
    part of the anchor). After patching, validate the YAML parses; the
    timeouts are a fail-fast backstop, not a behavioral change to
    well-behaved jobs.
21. **`git diff --name-only` can hide the OLD side of a rename.** With rename
    detection enabled, a critical-path rename may appear only as the destination
    path. Moving `.github/**`, governance policy, or classifier code into an
    ordinary classified module can therefore route as medium risk and skip the
    security/full gates. This is directly reproducible by comparing
    `git diff --name-status` (`Rnnn old new`) with `git diff --name-only` (new
    path only). Discover paths with `git diff --no-renames --name-only` so a
    rename becomes delete+add, or parse `--name-status -z` and include BOTH old
    and new paths for every rename/copy. Add a regression for
    critical-source→ordinary-destination and require the full gate set.
22. **A PR-controlled aggregate is not an immutable branch-protection gate.**
    If branch protection requires only an `aggregate` job whose workflow and
    verifier are read from the candidate PR tree, a hostile PR can retain the
    required check name but replace its body with unconditional success or
    weaken the candidate-side verifier. Correct selected/result wiring does not
    close this trust-boundary attack. For adversarial enforcement, use a
    repository/ruleset required workflow controlled from protected default-branch
    authority (or an equivalent external check), and protect changes to the CI
    enforcement surface with the repository's review policy. Report separately:
    honest-workflow fail-closed behavior versus whether the required check itself
    is immutable against the PR being evaluated.
23. **Plan identity absence must fail, not disable comparison.** An aggregator
    must require a schema-valid plan with commit identity, digest, and the known
    gate vocabulary before considering job results. Code shaped like
    `if plan_commit is not None and expected != plan_commit: fail` accepts a
    missing commit and silently removes the HEAD binding. Validate the whole plan
    schema at the aggregate boundary and unconditionally require
    `plan_commit == expected_head_sha`. Also probe every selected gate over
    `success/failure/cancelled/skipped/missing`, and require that any known
    not-selected job which nevertheless ran and failed/cancelled still fails the
    aggregate.

## Dedup maintenance: one gate-selection authority

When a selective pipeline matures, gate-selection rules accrete in 4-5 places
(hardcoded critical prefixes, hardcoded gate-name tuples, local path-scope
tables, profile risk zones). Collapse them to ONE authority (the project
profile's `gates:`/`risk_zones` consumed by the classifier) — validated
2026-08-15 (WORK-LAB PR #116, WL3-800 dedup):

1. **Before deleting a hardcoded rule, prove the authority already covers
   it.** The classifier's hardcoded critical prefixes
   (`00-governance/**`, `.github/**`, `scripts/ci/**`) were byte-identical to
   `risk_zones.critical` — deleting them changed nothing because the risk-zone
   match already fired. Keep only the fail-closed part the authority does NOT
   cover (unknown paths → critical). Verify with the planner's existing tests
   (17 passed) plus a tests/ci regression run before pushing.
2. **Generate CI outputs from the authority's keys, not a hardcoded tuple.**
   `run_<gate>` GitHub outputs generated from `sorted(profile["gates"])`
   instead of a 5-gate literal — adding/renaming a gate then never requires
   touching CI emit code. Output order changes (sorted) but is irrelevant for
   env-var consumers.
3. **Local convenience tables stay, annotated, not deleted.** A
   `GATE_PATH_SCOPES`-style local mapping that CI never reads is a UX shortcut
   for humans running one gate; deleting it breaks the local workflow for zero
   CI gain. Annotate it as "LOCAL convenience mapping; canonical authority is
   profile `gates:` consumed by <planner> + <emit>; CI never reads this
   table" so future readers don't treat it as a second source of truth.

## Gate-cost and heavy-proof budgeting

A fail-closed pipeline can still be operationally over-heavy. Audit wall-clock
critical path and runner duplication separately from correctness:

- Record per-job start/end times and identify the critical-path job; do not
  optimize the short `a0-gates` aggregator while ignoring a 10-minute desktop
  installer job.
- Keep `wheel-smoke`, browser smoke, Windows runtime smoke, and exact-SHA
  aggregation when their evidence boundaries are real; reduce frequency and
  scope before deleting them.
- Split desktop proof into `desktop-fast` (Rust/library/backend lifecycle),
  `desktop-build`, and `installer-lifecycle` (NSIS install/upgrade/close/uninstall).
  Route installer lifecycle only for desktop/installer/release-risk paths and
  on an explicitly scheduled main/nightly/release policy. A desktop source
  change does not automatically imply a fresh NSIS install test unless the
  changed surface can affect packaging or lifecycle.
- Treat a multi-version matrix as a compatibility contract, not a reason to
  repeat every expensive suite three times. One version may run the full
  integration suite while other supported versions run focused compatibility
  tests on PRs; main/nightly/release can restore the full matrix.
- Preserve a small final verdict job (`if: always()`); it validates results and
  should not duplicate test execution.

The audit output must state both: (1) which gates are security/product evidence
that must remain, and (2) which frequency/job aggregation choices create avoidable
cost. Recommend routing changes rather than deleting release evidence.

## Companion full-matrix (nightly) tier

The selective pipeline usually has a scheduled full-matrix workflow (nightly)
that runs every test, the real browser, the compat matrix, and Windows.
Before its FIRST scheduled tick, treat it like a never-run workflow (see
ci-browser-smoke-testing for the timezone/timeline verification), AND audit
three green-by-configuration traps that make a green run a false signal:

1. **"Full suite" is only as full as pytest's collection config.** `pytest -q`
   from the repo root collects `testpaths` only — if `pyproject.toml`
   `testpaths` lists `tests/` + `knowledge_base/tests` but the repo has
   `integration-tests/`, the nightly's full job NEVER runs those tests while
   ci.yml runs them as a separate step. A green nightly is then
   green-by-configuration for the integration layer (LOG-166: 35 tests
   missed). Fix: enumerate directories explicitly in the full job —
   `pytest tests/ integration-tests/ knowledge_base/tests/` — mirroring
   every test step of the fast pipeline, and cross-check the nightly job's
   coverage against ci.yml's step list, not against "pytest runs everything".
2. **Name-check every job against what it actually runs.** A job named
   `browser-smoke` that only runs `pytest tests/test_workspace_api.py` has no
   playwright and no browser — the nightly tier never regresses the UI even
   though the graph looks covered. Mirror the real gate (browser group +
   `playwright install` + the real smoke script) into the nightly tier.
3. **Pick ONE interpreter model per job — venv or `pip --system`, never a
   mix.** If the smoke script spawns `sys.executable -m app.runtime_entrypoint
   migrate` (it does — the app needs a server), then every step must run
   under the same python that has the deps. Nightly's first real-browser
   attempt installed ci/ci-adapters into the venv (`uv sync`) but ran the
   script under the system interpreter (browser group `pip install --system`
   only) → the spawned migrate crashed with missing deps (LOG-167). The
   ci.yml gate used `pip --system` for everything, so it never exposed this.
   Fix for the nightly tier: all-venv — `uv sync --frozen --group ci --group
   ci-adapters --group browser`, `uv run ... python -m playwright install
   --with-deps chromium`, and `env -u PYTHONPATH uv run ... python
   scripts/a0_browser_smoke.py` so `sys.executable` IS the venv python.
   Verify locally with the EXACT command before dispatching.
4. **Pre-verify with a manual `workflow_dispatch` instead of waiting for the
   tick.** Static pre-audit is not decisive (the OCR-engine gap below was
   invisible to every push path because gateplan never selected media tests).
   Dispatch via API (token from `git credential fill`, api.github.com
   direct, POST → 204) and require an all-green run before trusting the
   schedule. Only for workflows whose dispatch cannot publish artifacts —
   tag-push-only release workflows must NOT be dispatched (never create a
   release tag without Owner action).

These audits found, in one session (LOG-164..169): missing OCR engine in
full-suite (mirror the apt install step: ffmpeg + tesseract-ocr +
tesseract-ocr-eng + fonts-dejavu-core + `tesseract --list-langs | grep eng`),
excluded integration-tests, a browser-smoke job with no browser, an
interpreter mismatch, plus the two classifier gaps in pitfalls 17-18. See
`references/nightly-tier-and-phantom-gates.md` for the run-by-run transcript.

## Desktop/installer flaky note

Windows NSIS `WM_CLOSE` lifecycle and `backend_lifecycle` launch races are known
non-deterministic. A same-tree run that passed on one attempt and failed on
another is a flake, not a regression — rerun the failed job, do not change code.
The correct long-term fix is splitting desktop into `desktop-fast` /
`desktop-build` / `installer-lifecycle` and excluding desktop proofs from tree
reuse until N consecutive clean runs.

## CI watcher notification vs authoritative run conclusion

A background `gh pr checks --watch` / `gh run watch --exit-status` process
reflects the state at the moment it printed. If you have since rerun the run
(`gh run rerun <run> --failed`), or a concurrency group cancelled the old run
and a new one started, an `exit 1` notification or a printed `fail` line is
frequently a **pre-rerun snapshot**, not the current truth. Before treating any
watcher notification as a real failure: re-query the run by exact run id and
read the final `status`/`conclusion`, and check whether the head SHA still
matches the branch's current head. A run whose attempt was superseded (rerun,
or concurrency-cancelled then re-pushed) can legitimately show `fail` in an old
notification while the authoritative final run is `success`. When several
stale `--watch` processes from earlier in a session drain late, do not treat
each as a new event — verify against `gh run view <id>` before acting.

## Verified event-ref and desktop-lane pattern

For GitHub event-aware classification, keep ref resolution in a pure,
unit-tested helper rather than embedding fallback logic only in YAML. The
helper should return `(base, head, trusted)`: push uses
`github.event.before -> github.sha`, pull requests use the prospective
base/head SHAs, and missing/zero/untrusted refs force full qualification. Do
not use `origin/main -> HEAD` as an apparently valid selective push diff.

For desktop proof, separate semantic gates and preserve the artifact boundary:

- `desktop-fast`: Rust fmt/test and backend lifecycle;
- `desktop-build`: Python runtime staging, dependency audit, Tauri/NSIS build,
  exact installer count/name validation, and upload of the built installer;
- `installer-lifecycle`: download the exact build artifact and run install,
  launch, graceful WM_CLOSE, forced cleanup, and uninstall verification.

The lifecycle job must not rebuild a second installer or accept a broad glob as
release evidence. Full qualification and installer-risk paths must run all
three lanes; lighter desktop changes may run only the lanes selected by the
classifier. Keep `a0-gates` mapped to each semantic gate and fail closed on
build/lifecycle skips or failures.

## Verification sequence

- RED contract tests: every risk class truth table, mixed-union, rename/delete,
  unknown→full, classifier self-change→full, missing-diff→full, force-full,
  and trusted push/PR event-ref resolution.
- Run the classifier as a script against the exact PR paths and assert
  `full_qualification` + `required_gates` match the matrix.
- Validate the workflow YAML parses; assert heavy jobs carry both the
  `contains(required_gates, ...)` and `full_qualification == 'true'` branches,
  and that desktop build/lifecycle artifact handoff is explicit.
- For Windows close changes, run Rust format/unit checks plus a real NSIS
  lifecycle smoke; static contracts alone do not prove WM_CLOSE behavior.
- After merge, confirm the merge-SHA main CI is green (or the flake was rerun).

## Evidence boundary

A green PR exact-head run proves only that candidate SHA. It does not prove
merge-SHA main, branch protection, TreeProof/Main Bind, or Release
qualification. Report those as separate evidence layers and never substitute
one for another.

See `references/gateplan-classifier-pitfalls.md` for the full bug→fix transcripts and the `classify.py` shape. See `references/rename-and-aggregate-trust-boundary.md` for the rename old/new reproduction, complete aggregate result matrix, and the candidate-controlled required-check trust test. See `references/gate-cost-audit.md` for the reusable wall-clock/runner-cost audit and desktop-fast versus installer-lifecycle matrix. See `references/ci-gate-cost-optimization-verified.md` for the verified event-ref helper, exact installer artifact handoff, and native close lifecycle evidence.
and the `classify.py` shape. See `references/release-identity-and-workflow-wiring.md`
for the cross-step `$GITHUB_OUTPUT` leak, the main-push `force_full` behavior, the
release-identity schema-v2 separation (verification vs release run), and the
fresh-checkout output-dir pitfall. See `references/gate-identity-audit.md` for the
job-name-vs-gate-ID aggregator review checklist (AXW-003A). See
`references/binary-fixture-and-installed-state-evidence.md` for generating real
binary format fixtures (reportlab CID fonts for CJK, scanned/encrypted/corrupt
variants + semantic Oracle), the `markitdown[pdf]` extra requirement, and running
installed-state evidence from a downloaded exact-SHA installer without merge.
