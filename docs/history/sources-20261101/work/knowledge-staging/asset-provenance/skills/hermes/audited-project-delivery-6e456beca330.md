---
name: audited-project-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/audited-project-delivery/SKILL.md
---

---
name: audited-project-delivery
description: "Use for project audit, handoff, exact-evidence Git delivery."
version: 1.0.3
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [audit, handoff, project-boundary, git, github, exact-sha, delivery]
    related_skills: [project-data-boundary, agent-workflow-fortress, github-pr-workflow]
---

# Audited Project Delivery

## Purpose

Use this class-level skill when a task combines project-data containment, external-artifact recovery, audit/handoff writing, error summarization, commit/push, or GitHub PR delivery. The goal is a reproducible evidence chain, not a status narrative.

This skill complements the existing project-data and workflow-fortress skills. It does not replace their ownership, deployment, or runtime-specific rules.

Re-verify prior audit claims against newer main: `references/audit-claim-reverification.md`.

## Exact-head closure and multi-entry runtime checks

A delivery is not closed when the pre-commit tree is green. Freeze the final
commit first, then re-run any verifier that writes an exact-HEAD marker and only
then run the release gate. A new commit makes a previously written `ok <sha>`
marker stale even

The same post-commit rule applies to tracked evidence indexes and handoff
metadata: after every commit, search normative files for embedded HEADs, tested
SHAs, run IDs, counts, and generated dates. A CI-success result for the parent
commit does not make a newly committed evidence index current. Prefer wording
such as `audited revision <sha>` for recorded evidence rather than claiming the
file describes the current HEAD; if the index is changed, validate it, commit it,
re-run exact-SHA CI, refresh the exact-HEAD marker, and re-run the release gate.

Do not “fix” this by making a self-referential commit hash. Bind the index to the
latest independently audited revision and prove that revision is an ancestor of
the final delivery tree; keep the final release gate fail-closed.

See `references/evidence-index-freshness.md` for the reusable post-commit evidence-index and exact-SHA closure checklist. when the code change is unrelated to evidence.

1. Before edits, capture `git status --short --branch`, `git rev-parse HEAD
   origin/main`, and `git diff --check`.
2. Treat every public launcher as an entrypoint: invoke it from the repository
   root as well as its module directory. For Node scripts, resolve runtime roots
   from `__dirname`/`import.meta.url` and pass an explicit `cwd`; never assume
   the caller's `process.cwd()`.
3. Re-run the exact root-level reproducer after the fix, then run the complete
   test suite and the aggregate verifier. A module-local green run does not
   prove the repository-level launcher works.
4. After the final commit, run the aggregate verifier again so its marker is
   bound to the final HEAD. Then run the release gate and distinguish stale or
   dirty-tree findings from genuine capability/human-evidence blockers.
5. Derive the CI target with `git rev-parse HEAD`; never synthesize a full SHA
   from a short SHA or guess a run ID. Poll by the exact 40-character SHA and
   record the run id, status, conclusion, and `head_sha`.

A concise session-specific reproduction and evidence table is in
`references/exact-head-and-cwd-entrypoints.md`.

## Primary rule: route data, do not merely reject it

Before launching any child process, bind temporary files, caches, build outputs, logs, package-manager state and test artifacts to the owning Git project's ignored runtime:

```text
<project>/.hermes/task-runtime/
<project>/.hermes/task-artifacts/
```

Inject project-local `TMP`, `TEMP`, `TMPDIR`, XDG/pip/uv/npm/yarn, Playwright, Cargo/Rust, Python bytecode, Ruff/mypy and pre-commit paths before starting the child process. Legacy spill roots such as `D:\a`, `D:\d`, `D:\dev` and `D:\tmp` are recovery inputs, not normal output destinations. A guard may fail closed only when an explicit command hard-codes a legacy external path and bypasses the project-local binding; the diagnostic must direct the operator to `.hermes/task-runtime`, not present rejection as the containment strategy.

## External-artifact audit and recovery

1. Record the live branch, HEAD, worktree state and task scope before touching artifacts.
2. Inventory each candidate by absolute path, owner/project, file type, size, timestamp, active-process relationship, reparse/symlink state and likely purpose.
3. Preserve useful evidence only in the owning project, never in a convenient central project. Use:

   ```text
   <owner>/.hermes/task-artifacts/external-recovery-<date>/
   ```
4. For every recovered item, copy without overwrite, hash the source, read back and hash the destination, then record source/destination/size/hash/use/retention decision in a human handoff and machine-readable manifest.
5. Delete only exact, proven regenerable or useless items after active-process checks. Do not broad-delete a mixed root. Unknown ownership is preserve-and-report, not move-and-guess.
6. Final-scan the legacy roots and report their state separately from protected independent projects intentionally left in place.

## Cross-repository cutover and freshness closure

When a user requests migration of a local legacy subtree into another repository followed by local removal, bind the source and destination checkouts independently before any write. Record each absolute Git root, branch, HEAD, status, and remote URL in the same command immediately before the destination push; a branch name is never enough to identify the repository. Compare source files against the destination by intended mapped paths and hashes, classify same/changed/missing/unmapped files, and do not blind-copy into a guessed prefix. Stage only the reviewed destination roots (force-add ignored product assets only when explicitly in scope), run the destination's real test entry point, push a dedicated migration branch, and read back the exact remote commit/tree before updating the requested destination default branch with a fast-forward. Before deleting the source, write a project-local ignored file-level SHA-256 manifest, delete only the authorized exact subtree, verify source absence and source-repository cleanliness, and re-read the destination default-branch SHA. Keep upload, default-branch publication, local deletion, and test evidence as separate claims. The reusable matrix and commands are in [`references/monorepo-cutover-and-freshness.md`](references/monorepo-cutover-and-freshness.md).

A green exact-SHA aggregate proves only the jobs declared by that workflow. For audit closure, independently run tracked generated-state checks, source-ledger verification/tests, and every root test script when package discovery is not reliable; compare generated projections with tracked JSON/Markdown and inspect the workflow to confirm those checks are actually required. A zero-test discovery result is selector evidence, not a pass. Retry CLI invocation errors against the current `--help` contract before classifying product behavior. Report stale projections, omitted freshness gates, user-profile interpreters, `UNVERIFIED` provider/runtime checks, and absent branch protection as separate warnings; do not let a CI green run promote stale metadata to PASS.

## Generated-state and CI freshness portability

Generated governance state and source-ledger reviews must be designed around claims that can remain valid after the next governance commit. Do not require a tracked `reviewedCommit` or `CURRENT_STATE.git.head` to equal the commit containing that same file: that is a self-referential invariant that becomes false whenever the file is updated. Store the review baseline and validate freshness by checking whether the reviewed `targetPaths` and their declared tests changed between the baseline and current HEAD; changes outside that scope may remain local-verified. Add a regression test for both the unchanged-scope and changed-scope cases.

A migration/verification gate that byte-compares a deployed managed asset
against the CURRENT source — instead of against hashes recorded at apply time
— permanently wedges the moment the source advances after a legacy apply
(observed live: `sync_codex_global_assets.py` plan blocked under a v1/v2
state once the guidance/rules source had moved on). Design state transitions
so ownership is proven by what was recorded, not by equality with today's
source: record target/block hashes at apply time; for legacy states that
predate hash recording, prove ownership with managed markers; treat a
dissolved managed block whose managed fields the user has not re-set as a
benign config rewrite (re-append per the "write missing fields only"
contract — nothing user-set is overwritten), while a present-but-mismatched
block or an unmarked block still fails closed. Add one positive migration
test (legacy state + advanced source + dissolved block → clean migration)
and two negative controls (edited block → still blocked; unmarked guidance
block → still blocked).

When a verifier compares against an earlier commit, the CI checkout must contain that history. A default shallow `actions/checkout` can make a valid reviewed commit appear missing and turn `git diff <reviewed>..HEAD` into a false stale result; set `fetch-depth: 0` on the job that reads historical review baselines. Re-run the verifier on the actual post-commit HEAD, not only on the pre-commit working tree.

Squash-merge ancestry: a tracked generated projection (e.g. CURRENT_STATE) that records `git.head` breaks the post-merge freshness gate on `main` after a squash merge — the recorded PR-branch head is not an ancestor of the merge commit. This is expected, not a bug; budget for a follow-up chore PR that regenerates the projection on the merged main head (verified pattern: #34→#35, #37→#38, #42→#44). Run the freshness verifier locally on the final main head before reporting closure, and expect one extra chore round per squash-merged delivery that touches the projection's inputs. Regenerating inside the delivery PR fixes the branch's digest but not the post-squash ancestry, so the chore is unavoidable when the base uses squash merges.

JSON Schema used in offline CI must use an absolute `$id` URI. Relative IDs can resolve differently across `jsonschema` versions and cause an otherwise local `#/$defs/...` reference to trigger an invalid remote lookup. Add an offline validator regression test and inspect the exact failed CI log when local and runner results differ.

After a failure on a newly pushed SHA, read `gh run view <run> --log-failed`, identify the failing job/step, patch the root portability or contract issue, and create a new commit. Never reuse the failed run or a prior green SHA as evidence for the repaired tree.

## Error summary contract

A useful error summary records the original symptom, root cause, corrective change, verification command/result and remaining boundary. Distinguish invocation/selector errors from implementation failures; missing layout declarations from external-tool failures; provenance or documentation-index drift from code regressions; branch-protection rejection from test/CI failure; local repository proof from live Hermes/Home deployment proof; and pending CI from failed CI.

Do not convert a resolved retry into a permanent tool limitation. Capture the durable fix or workflow lesson instead.

## TaskPack identity and first-slice selection

When a project handoff names TaskPack IDs but the authoritative archive, manifest, or machine-readable task graph is missing or disagrees with a visible local ZIP, stop treating the ID prose as canonical.

When multiple TaskPacks arrive over time, the newest live-audit TaskPack supersedes older planning prose only where it explicitly revises the baseline, blockers, ordering, or acceptance contract. Reconcile the older package against the newer one before acting: preserve stable boundaries, record changed decisions, and do not execute the older sequence merely because it was already started. Validate every claimed blocker against the live repository. For CI/release work, inspect the actual workflow step boundaries and schema fields; a value assigned in one GitHub Actions step does not exist in a later step unless passed through `$GITHUB_OUTPUT`/step outputs, and a breaking identity-field change requires a schema major/version bump plus a backward-compatible reader or migration. A pushed branch is only `REMOTE_BRANCH_UPLOADED`; it is not a PR, exact-head CI pass, merge, or release-eligible artifact. Keep those evidence levels separate and stop merge/release claims when the remote branch has no PR or exact-SHA checks. When the user supplies an authoritative TaskPack ZIP that is actually present and asks to load it as the execution entrypoint, validate with the pack's own `scripts/verify_taskpack.py` (read-only, hash-checks against `PACK_MANIFEST.json`), then read the MASTER brief and summarize the machine-readable task graph from `tasks/task-cards.json`/`phases.json` via Python (group by phase; do not inline raw JSON). A long-line UTF-8 Markdown brief may misdetect as "binary" in `read_file` — decode `utf-8-sig`/`utf-16` and wrap lines before reading. See [`references/taskpack-authoritative-ingestion.md`](references/taskpack-authoritative-ingestion.md) for the packaging convention and full safe ingestion sequence.

Before implementation:

1. Confirm the claimed authority archive exists at the referenced path; if absent, record an unresolved identity boundary.
2. Inspect ZIP members and machine-readable manifest/task cards without executing embedded scripts or broadly extracting opaque content. Record version/hash/member identity without copying private attachment paths into tracked docs.
3. Compare each task ID's title, acceptance, allowed paths, forbidden paths, and baseline SHA against the tracked matrix/handoff. A matching ID with a different title is a contradiction, not permission to choose the convenient definition.
4. Select the first dependency-safe slice that is fully specified and needs no user policy decision. Prefer a local contract vertical slice with real RED→GREEN tests, explicit quarantine/rollback, and no external mutation; keep live deployment, product policy, license choice, and release signing as separate gates.
5. Update the current matrix with the evidence actually produced and the unresolved identity boundary. Never promote a partial local slice to full TaskPack completion merely because its helper schema exists or the legacy full gate is green.

Before the final commit, audit root/module tests for stale expectations. A test that reads a historical ignored artifact while the canonical verifier reads a tracked source is not reproducible on a clean checkout; align the test with the verifier's canonical path and retain negative controls against a temporary tampered copy.

### License/REUSE header backfill is language-specific

When backfilling `SPDX-License-Identifier` headers across a mixed Python+JS repo (REUSE closure / ODA4-0114-style license sweep), the comment token is language-dependent — a single `#` header breaks every JS/MJS file with `SyntaxError: Invalid or unexpected token`:

- **Python**: `# SPDX-License-Identifier: MIT`
- **JS / MJS / TS**: `// SPDX-License-Identifier: MIT`

Write the backfill script per-extension and **preserve shebang, `# -*- coding` / encoding declaration, BOM, and leading docstring/comment blocks** above the header. Two follow-ups when backfilling source headers:
1. **Regenerate committed bundles** — if any checked-in artifact is built from the edited sources (e.g. a minigame bundle), rebuild it and commit alongside, or the deterministic drift gate (`git cat-file` HEAD-vs-worktree) goes red.
2. **Idempotent + verify** — skip files already carrying the header, then re-run a coverage checker (`grep SPDX-License-Identifier` on head of every tracked source file) and `node --check`/`ast.parse` on a sample to prove nothing broke.

### Contract catalog + governance-test expected lists move together

Adding a new contract/schema to a repo that has a `verify_contract_catalog.py`-style verifier requires syncing **three** stale expected-lists in the SAME commit or CI goes red with a `catalog ids must equal [...] got [...]` failure:
1. the verifier's `EXPECTED` id→owner dict,
2. its `CANONICAL_SCHEMA_PREFIXES` path map,
3. **any governance test that hard-asserts the total count** (`assertIn("CONTRACT_CATALOG_PASS contracts=28 ...", ...)` → bump to the new count).

Also check for a companion governance test that asserts the CI workflow itself contains certain commands (`assertIn("generate_current_state.py --check-current", workflow_text)`) — if the taskpack's gate requires a freshness/baseline check in CI, add the actual command lines to the workflow too, or that test fails even though the verifier passes.

### Local main ahead of remote by an OPEN-PR intermediate commitWhen reconciling dual-end consistency, a local `main` that is `ahead 1` of remote is not automatically "push it". The extra commit may be the **intermediate head of an OPEN pull request** that a prior local op merged into local main — pushing it to a protected `main` both fails (required check) and would bypass the PR. Diagnose before pushing:
1. Check if the commit is an ancestor of the PR's current head: `git merge-base --is-ancestor <local-main-commit> <pr-head>` → if yes, its content is already preserved in the OPEN PR.
2. If so, the correct action is `git reset --hard <remote-main-sha>` on local main (content safely lives in the PR), NOT `git push`. The open PR carries the work to main through its own merge.
3. When concurrent writers are actively pushing the same branch/PR (new runs keep appearing, PR head advances), stop forcing/merging — report the live state and let the owning writer close it.

For monorepo cutovers and audit repair follow-ups, reconcile successor handoffs and current/status documents against the live active-module registry before claiming closure.

### Merge-side semantics: `-X ours` vs `-X theirs` (branch direction matters)

When reconciling two diverged branches by merging one into the other with a
`-X` conflict-resolution strategy, the resolver refers to the **merge command's
own sides**, not to "the branch I like". For `git merge -X theirs main` run while
`HEAD` is on the feature branch:
- `ours` = the current branch (`HEAD`, the feature branch)
- `theirs` = the argument branch (`main`)

So to let the *current* branch win on conflicts, use `-X ours`; to let the
*other* branch win, use `-X theirs`. Inverting this silently picks the wrong
content and can resurrect the very version you are trying to replace (observed:
a `-X theirs` merge into a revert branch pulled the reverted-on-main phrasing
back in). After the merge, always re-grep the resolved files for the marker
content you intended to win (e.g. the correct two-tier boundary line) before
committing, and run `git merge --abort` / `git reset --hard <target-sha>` to
redo it cleanly when the side was wrong. A "merge made by 'ort' strategy" with
zero conflict markers does NOT mean the side you wanted won — verify the actual
bytes.

### "Evidence absent" means search the whole tracked tree, not just one runtime dir

Before declaring runtime/E3 evidence "missing from the repo" (which lowers a
capability's honest E-level), search the full tracked tree, not only the
conventional ignored runtime path. Evidence frequently lives under domain
packs, benchmarks, or an `evidence/` subdirectory rather than `.hermes/task-runtime/`
(observed: Axe scan + per-case E3 evidence under
`domain-packs/uiux-design/evidence/` while `.hermes/task-runtime/` held only
backfill scripts). Establish the search set with `git ls-files` filtered by
name/keyword, and check whether the file is tracked in the current main
(`git log --oneline -1 -- <path>` and `git ls-tree main -- <path>`) before
declaring it absent or lowering the evidence claim. Only genuine absence — file
untracked AND unreachable in main history — justifies a downgrade, and even then
state "recorded but not re-verified" rather than silently downgrading.

### `gh pr merge --squash` "not possible to fast-forward" is local noise, not a merge failure

After a successful squash merge you will often see
`fatal: Not possible to fast-forward, aborting` plus
`! warning: not possible to fast-forward to: "main"`. This is git trying to
fast-forward your *local* `main` branch to the merged head and is NOT a merge
failure — the remote merge already happened. Confirm success via the PR API
(`gh pr view <N> --json state,mergedAt,mergeCommit` → `state=MERGED` with a
merge SHA), then sync the local `main` yourself with
`git fetch origin && git reset --hard <merged-sha>` (a squash merge is not a
fast-forward, so `--ff-only` will fail by design).

### SSH-URL push fallback when the https origin has no credential helper

When `git push origin <branch>` fails on auth and `gh auth status` reports
`git operations protocol: ssh` while `origin` is an https URL with no
credential helper, do not assume push is blocked. Verify ssh auth once
(`ssh -T -o StrictHostKeyChecking=accept-new git@github.com` →
`Hi <user>! You've successfully authenticated`), then push by explicit ssh URL
without changing the configured remote:
`git push git@github.com:<owner>/<repo>.git HEAD:<branch>`.
 Update normative active-module lists when scope changes; retain removed paths only in documents explicitly labeled historical, archive, migration evidence, or fixtures. Regenerate tracked projections after the doc repair and run the exact-SHA gate on the new commit. Treat GitHub branch protection/rulesets, repository settings, releases, and other remote policy changes as separate settings side effects: a generic request to continue a repair does not silently authorize them. Inspect and report the current policy first, then request explicit authorization for the settings write and read back the resulting policy.

## Continuous local TaskPack execution and silent batch mode

For an authoritative TaskPack that explicitly authorizes continuous local safe execution, interpret “全部执行/静默执行/直到任务包完成或工具达到上限” as an execution mode, not a request for another plan. Batch tool calls without per-command narration while maintaining an internal task list and the ignored project-local Ledger. Advance dependency-safe local tasks in order, but never promote a partial implementation to full TaskPack completion merely because its unit suite is green.

Use this loop:

1. Mark exactly one writer task `in_progress`; read the live task graph, applicable instructions, and relevant source before editing.
2. Implement the smallest real vertical slice with a regression test and a runtime/entrypoint check where applicable. A schema or stub alone is not completion.
3. Run the module gate through the project-data wrapper so temp/cache/runtime outputs stay under `.hermes/task-runtime` and `.hermes/task-artifacts`; direct module execution is acceptable only when the wrapper cannot express the module cwd, and then bind the script directory explicitly for direct imports.
4. Freeze the candidate with a temporary Git index after each dependency-safe batch and record the actual evidence filename emitted by the freeze script; do not guess artifact names.
5. Reconcile asynchronous read-only findings against the current tree before marking a task complete. Re-run active-surface scans after edits and preserve only historical/transfer declarations.
6. Update the ignored Ledger with checkpoint, tests, candidate tree and file hashes only after verification. Keep `COMPLETED` limited to the implemented acceptance slice; leave later tasks pending when their acceptance is not actually met.
7. At the tool-call limit, report the exact completed/pending matrix and separate `LOCAL_TEST_PASS`, `LOCAL_VERIFIED_READY_FOR_APPROVAL`, commit, remote, CI, live-apply and release evidence levels.

Common pitfalls: treating an old remote CI run as proof for a dirty tree; using a stale artifact path in a completion script; declaring an entire TaskPack complete after implementing only identity/config/sidecar slices; and narrating every command after the user requested silent batch execution.

## Verifier-chain design traps (validated 2026-08-14)

When an aggregate verifier chain grows (e.g. `verify_design_lab.py` now runs identity/manifest/contracts/comfy/release gates), three failure classes bite:

1. **Nested aggregate invocation = infinite recursion.** A per-domain gate (e.g. `verify_release_gate.py`) that internally invokes the aggregate (`verify_design_lab.py`) to "confirm the chain is green" recurses forever — the aggregate runs the gate, which runs the aggregate... and the shell times out with no output. Never call the aggregate from inside a gate it is part of. Instead, have the aggregate **drop a marker file** (`config/.verify-chain-ok`) after a successful run; gates that need "chain green" check the marker's existence, and the release gate documents "run the aggregate first". Replacing the nested call with the marker fixed the timeout immediately.
2. **Prohibition statements self-trigger forbidden-pattern regexes.** A policy doc that states "禁止绑定 0.0.0.0" / "no auto-install" gets flagged as a violation by a gate that scans for `0.0.0.0` / `auto-install` patterns. Fix the gate, not the doc: strip lines containing negation markers (`禁止`, `不得`, `不自动`, `not`, `无`) from the scanned text before matching forbidden patterns (keep required-pattern checks on the original text). Same class as the identity-gate "退出活动命名" exemption — a fail-closed gate must distinguish a policy *declaring* a prohibition from actually containing it.
3. **Generated index files need deterministic output.** A generator that embeds a second-resolution `generated_at` timestamp (or unsorted entries) produces a diff on every run, dirtying the tree and tripping clean-tree CI gates. Use date-only timestamps (`%Y-%m-%d`) and sort entries by path so identical trees regenerate byte-identical output. Regenerate before committing the generator itself, then verify the file is stable across a second run.

## Post-review P1 closure loop

Treat asynchronous read-only review findings as new correctness work, not as commentary after delivery:

1. Reproduce each finding with a focused probe or regression test; do not dismiss a passing prior gate.
2. Fix the contract at its narrowest root: strict boolean/enum checks instead of truthiness, state invariants in the validator rather than only in happy-path transitions, and canonical-root/path identity checks rather than filename-marker checks.
3. Run RED→GREEN targeted tests, then the module canonical gate and root integration gate.
4. Re-freeze the changed tree, stage only audited files, commit and push a new SHA, and query CI by that exact SHA. Previous CI success is historical evidence only.
5. Report the finding, root-cause fix, new regression, and post-fix exact-SHA evidence separately.

### Active-module retirement closure

When a module or product has been transferred out of a monorepo, a broad keyword scan is not a closure proof. Reconcile the current tree in layers:

1. Define the active execution surface first: ordinary CI workflow steps, release prefixes, module registries, generated current-state projections, TaskPack entrypoints/summaries, runtime project registries, and governance test assertions.
2. Search those active surfaces for retired module IDs, names, Gate names, pilot commands, and old module counts. Fix every executable or normative hit at its root; do not remove historical migration pointers, archive manifests, or explicit `SUPERSEDED_MOVED` records merely because they contain the old name.
3. Check both direct and indirect CI execution. Removing a command from one job is insufficient if an integration verifier, regression wrapper, or test entrypoint still invokes the retired pilot.
4. Regenerate tracked projections after changing their generator. Do not hand-edit `CURRENT_STATE.json`/`.md` without also fixing the generator, or the next run will resurrect the stale capability name.
5. Add or update governance assertions so the active Adapter/module list contains only the current modules and does not accidentally re-promote the retired one.
6. Run the canonical tests, stale-projection check, `git diff --check`, and a final active-surface scan. Classify remaining mentions as `ACTIVE`, `HISTORICAL`, `TRANSFER_POINTER`, `FIXTURE`, or `ARCHIVE_ONLY`; only the first class blocks closure.

When the user orders a **full reference scrub** ("remove all their content/history/indexes from this project"), the layered recipe and the observed WORK-LAB MINIGAME/OPEN-DESIGN case are in `references/retired-module-reference-scrub.md`. The load-bearing gotchas:

- **Never line-scrub code files.** Removing any line matching the names breaks syntax, indentation, or orphaned references (`NameError` on a constant whose definition was removed but a usage survived). Scrub code with targeted patches: delete whole functions/fixtures; re-add definitions still referenced; neutralize guards with *generic* retired markers (`retired`, `retired-module`) so the fail-closed mechanism survives without the old names.
- **Negative-control tests carry the names as fixtures.** Guard tests ("retired job does not satisfy the gate", "retired source not in active ledger") use the transferred names as sample data. Rename the fixtures to generic retired ids, keep the assertions — the guard stays armed, the names leave the tree. Watch argument order in fixture helpers (e.g. `ev(pid, task, source)` — changing the wrong arg changes which id the guard sees).
- **JSON entry removal leaves summary counters stale** (error-ledger `summary.total`, index counts, manifest totals). Refresh every aggregate counter after structural scrubs or the verifier fails with `summary.total does not match errors length`.
- **Governance tests assert marker strings in docs.** A doc line containing BOTH a required marker and the removed name gets deleted wholesale; the test then fails on the marker. Restore each required marker without the old name (positioning line, adapter list, scope statement).
- **Pure index artifacts whose entire purpose was the transferred module get deleted** (file + verifier + tests + their CI steps), not emptied.
- **Indexed references to deleted pilots break verifiers** — anything that indexed `pilots[2]`/a removed fixture must drop the field and its assertions together (report generator + verifier + its test).
- **CURRENT_STATE after the scrub**: scrubbing canonical digest inputs requires regenerating the tracked state in the same PR; after squash-merge the recorded head stays an ancestor (no extra chore) only when the regen ran against the pre-merge main head.
- Verify closure with `git grep -il '<name1>|<name2>'` over tracked files (excluding `.git`) returning zero, then run the full gate + root CI suite. Git history is the hard boundary — no force-push, so historical commits keep the names; state this explicitly rather than claiming total erasure.

A prior audit may have been performed against an earlier dirty tree. Always re-check its findings against the current worktree before editing: the correct outcome may be “already fixed,” but that must be proven by the current workflow/config/source, not inferred from the earlier report.

## System-blueprint documentation taskpack (Owner ZIP → doc-governance package)

When the user drops an Owner **system blueprint / naming / product-identity taskpack** ZIP (e.g. `ArcheAxis_Learning_Workspace_System_Blueprint_and_HERMES_Update_TaskPack_v1_2026-08-11.zip`) and says "阅读这个 / 全部执行", the deliverable is a **documentation-governance package**, not code. Observed shape (AXW-1200~1210, 17 files):

1. **Extract and read first.** The single `.md` inside may misdetect as binary in `read_file` (CJK full-width punctuation). Decode via `execute_code` with `Path.read_text(encoding="utf-8")` and read it fully before acting — the taskpack IS the authority and carries the "do not drift" naming/locking rules.
2. **Snapshot before writing** — `AXW1200_SNAPSHOT_RECEIPT` with current main SHA, merged PR list, worktree state, and supersession relations.
3. **Fixed directory layout** (keep the taskpack's file names even if the repo has similar legacy docs — supersede, don't duplicate authorities):
   - `docs/truth/` — `PRODUCT_IDENTITY_V2`, `NAMING_CONTRACT_V1`, `AUTHORITY_AND_STATUS_RULES_V1`, `CAPABILITY_ATLAS_V2.yaml`, `REQUIREMENT_TRACE_V2.yaml` (schema-validated YAML)
   - `docs/current/` — `CURRENT_PRODUCT_PLAN_V2`, `SCOPE_LEDGER_V2.yaml`, `TASK_GRAPH_V2.yaml`
   - `docs/blueprint/` — `SYSTEM_MASTER_BLUEPRINT_V2`, `LER_VISUAL_SPATIAL_LEARNING_V1`
   - `docs/architecture/`, `docs/migration/`, `docs/decisions/` — policy + 5-phase naming migration plan + ADRs
4. **Locked homepage contract** (user-declared, 2026-08-12): README top section + GitHub About description are **定死 (locked, no drift)** with: product identity, absorbed-projects list, **non-absorbable projects table** (license/blocked reason + upstream link), and external-dependency links. Stage descriptions may update; identity tables may not. `gh repo edit --description "..."` applies to About; keep the README table and the About string in sync.
5. **Non-absorbable ≠ missing:** license-blocked OSS (AGPL/GPL/OpenRAIL/Elastic/archived) goes into the README's "吸收不了 / 许可阻断" table with reason + link — never silently dropped, never absorbed.
6. **Verify machine-readable outputs:** every YAML must pass `yaml.safe_load`; capability/requirement/task counts are asserted by later contract tests — validate locally before the PR.
7. **Lint debt from doc-only merges still lands:** a documentation PR whose CI skips lint can inherit ruff errors merged by a previous code PR that showed "no checks reported" (see merge-verification-workflow) — run `uv run --frozen --only-group ci python -m ruff check app shared` locally before merging.

## Full-authorization silent-delivery mode (“授权都给，只要结果”)

When the user adds “全部授权给你 / 授权都给 / YOLO模式 / 只要结果” and says to run
until the tool-call limit, they are contracting a specific *reporting* mode, not
just granting permissions:

- **Batch to the limit; report staged, not per-step.** Do not narrate every
  command or file edit. Give a compact stage/slot/state matrix at meaningful
  milestones (a merged PR, a closed M-batch, a fixed CI regression) and one
  consolidated summary at the end / when the limit is hit. The user explicitly
  asked to avoid “实时汇报/事事汇报” and to “只做阶段性汇报，最后补一份摘要”.
- **Full authorization ≠ skipping gates.** Still preserve the checkout, keep
  single-writer, run the exact-SHA CI gate before declaring a merge green,
  redact credentials, and stop at real external evidence (paid smoke, live
  runtime) rather than fabricating it. Authorization lets you proceed without
  re-asking, not skip verification.
- **Honestly mark what is deferred, never claim it closed.** If a full
  migration is too large for the remaining budget, ship the safe boundary
  increment (contract + runtime-enforced read-only wrapper + tests + its own
  PR), then state the full item is deferred. Do not do a destructive
  half-migration that breaks the suite.
- **A merged PR making `main` CI red is a stop-and-fix, not an accumulate.**
  Rebase merges shift reviewed-scope SHAs; a freshness *test* that hard-asserts
  `local-verified` will red on `main` even when nothing is wrong. Fix the whole
  class (allow `STALE_REVIEW` for every module entry) via its own PR before
  piling more green PRs on a red `main`.
- **An explicit “execute until fully closed” mandate must cross every delivery
  level, not stop at a local technical PASS.** After the working artifact and
  local canonical gate pass, reconcile checkout ownership, freeze and stage the
  exact candidate, commit on a feature branch, push, create the PR, require both
  push- and pull-request-event checks for the captured full head SHA, merge only
  when the PR is clean, then require a separate post-merge `main` run for the
  returned merge SHA. Finally fast-forward/synchronize local `main`, restart the
  ordinary runtime from that merged tree, and freeze process/port/health/artifact
  evidence again. A local artifact, open PR, green PR-head CI, or successful
  merge API response is only an intermediate state. Tags, Releases, remote
  policy/settings, and deletion of unrelated or remote branches remain separate
  side effects unless the mandate names them.

## Horizon-gated TaskPack execution (multi-horizon release train)

When a frozen baseline defines Horizons (H0, H1, H2…) that each gate the next, and the user says "全量执行 / 继续推进，工具调用上限为止", run one horizon at a time with a clean branch boundary — do not pile every checkpoint onto one branch and merge once at the very end:

1. **One worktree + branch per horizon, from the latest `origin/main`.** For H0, `git worktree add -b axw/execution-h0 <path> origin/main`; when H0 merges, H1 starts from the new main SHA, not from the stale H0 base. A `git status` on a canonical worktree with unrelated dirty WIP is not a reason to start dirty — always isolate.
2. **Every task is its own checkpoint commit** (`fix/feat/test/docs` per AXW-ID) with RED→GREEN, changed-file Ruff, architecture guard, convention. Append a `LOG-YYYYMMDD-NNN` record to the append-only status log after each task (or each small batch) on the authoritative branch.
3. **Per-horizon PR is the exact-head CI gate.** Push the horizon branch, create one PR, and require exact-head CI green before merge. A green PR-exact-head run proves only that candidate SHA; it does not prove merge-SHA main (see Evidence levels). When the horizon contains only Python+docs, expect the selective classifier to SKIP desktop/UI/windows jobs — that is the classifier working, not a gap.
4. **Merge to main requires explicit owner authorization.** Before `gh pr merge`, ask via `clarify` with explicit options (merge + run merge-SHA CI / keep open / docs-only). Do not infer merge authorization from "继续推进" — merge is an owner-gated operation in the frozen-taskpack protocol. If the user gives no clear answer, fail closed: keep the PR open.
5. **After merge, run and read merge-SHA main CI** (`gh run list --branch main` then `gh run view <id>`), then start the next horizon from that exact SHA. The Hn-EXIT verdict depends on the horizon's frozen acceptance criteria, not on the number of green PRs.
6. **Mark heavy-frontend/desktop tasks PARTIAL honestly.** If a task needs a downloaded library + WebView click-level verification (e.g. PDF.js reader) that cannot close in the remaining budget, deliver the backend-ready subset (e.g. content-addressed PDF byte serving) with tests, mark the task `PARTIAL` in the status log and handoff, and defer the frontend to an explicit independent batch. Never present a backend subset as the full frontend task.

### gh pr merge worktree-collision workaround

`gh pr merge --squash` can fail with `fatal: 'main' is already used by worktree at <path>` when another worktree (e.g. an older feature worktree) holds the `main` branch name. Do not delete that worktree or force anything. Merge via the REST API instead, which bypasses the local checkout entirely:

```bash
gh api -X PUT repos/<owner>/<repo>/pulls/<N>/merge -f merge_method=squash \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['merged'], d['sha'])"
```

Then `git fetch origin main`, read back `git rev-parse origin/main`, and confirm the PR is `state=MERGED` with the expected merge commit before treating the merge as done.

### PR merge 405 after the base advanced (required-check retrigger)

When a PR's base advances after its checks ran (a previous PR merged), GitHub
branch protection can reject the merge with HTTP 405 `Required status check
"<name>" is expected` and `mergeStateStatus: UNKNOWN` — even though the head's
aggregate was SUCCESS — because the checks are stale for the new base. Do not
force, and do not close/reopen blind. Fix by giving the PR a NEW head that
gets re-checked against the current base:

```bash
git switch <feature-branch>
git merge origin/main -m "merge: refresh against main to re-trigger PR checks"
git push                      # normal push, no force needed
gh pr checks <N> --watch      # exact-head checks re-run on the new head
gh pr view <N> --json mergeStateStatus,statusCheckRollup   # wait for CLEAN + aggregate SUCCESS
gh api -X PUT repos/<owner>/<repo>/pulls/<N>/merge -f merge_method=squash
```

A normal merge commit of `origin/main` into the branch (not a rebase) is
enough — it changes the head SHA so checks re-run, and no force-push is
involved. Read the merged SHA back and re-verify main alignment afterwards.

## Upload and exact-evidence sequence

When the user asks to audit, hand off, summarize errors and upload:

1. Inspect `git status --short --branch`, branch tracking, remote URLs, recent HEAD, changed files, untracked files and ignored runtime artifacts. Never read credential values.
2. Scan candidate files for secrets, auth/session databases, caches, installers, binaries and accidental generated data.
3. Run targeted tests, the canonical quality gate, syntax/compile checks, security/rule scans and the project doctor where applicable.
4. Write the handoff summary and machine-readable manifest into tracked docs only when intentionally part of the repository contract; keep runtime evidence in ignored `.hermes/`.
5. Stage only the audited scope. Review `git diff --cached --name-status`, `git diff --cached --check`, staged stat, staged binary diff hash and `git write-tree`.
6. Commit the reviewed staged tree. Any edit, amend, rebase or generated tracked change invalidates the staged review and requires repeating it. If `git commit` fails with `unable to auto-detect email address`, the repo has no `user.name`/`user.email`; read the historical author from `git log -1 --format="%an <%ae>"` and set the same identity repo-locally (`git config user.name/email`) so the handoff commit matches the repo's existing authorship instead of inventing a new one.
7. Push only after the user explicitly requests upload. If protected `main` rejects a direct push because required checks are expected, never force-push or bypass protection: push the exact commit to a feature branch and create a PR.
   If a direct push is rejected because the remote advanced (`fetch first` / non-fast-forward), do not force-push. Create a backup branch at the reviewed candidate, fetch the target branch, record remote-only and local-only commits, and rebase only from a clean worktree when linear-history integration is appropriate. Any rebase/cherry-pick/edit invalidates previous exact-SHA evidence: rerun the full local gate, refreeze the new HEAD/tree, then push and read back the remote SHA.
8. Read back the PR/remote head SHA, base branch, check names/status/conclusions and final local worktree. Wait for exact-SHA required checks; do not report pending as pass.
9. Keep merge, release and live-profile deployment as separate operations unless separately requested and verified.

## Handoff contents

The handoff should include date/timezone, repository, branch and baseline HEAD; scope grouped by coherent themes; artifact ownership and recovery destinations; implementation and test evidence; errors found and root-cause fixes; unresolved/deferred boundaries; commit SHA, remote branch, PR URL and exact-SHA CI results; and an explicit statement that secrets and protected runtime state were not included.

Provide a JSON manifest alongside the Markdown handoff when the audit has multiple artifacts, projects or retention decisions.

## Promoting a reviewed staging tree to the main worktree

When a large TaskPack/overlay has been reviewed in an isolated staging checkout and the user authorizes upload/handoff, promote the exact reviewed tree instead of recopying files ad hoc:

1. In staging, `git add -A`, run the full candidate gates, run `git diff --cached --check`, and freeze `candidate_tree=$(git write-tree)`.
2. Create a binary-safe patch from the staged index: `git diff --cached --binary > <project>/.hermes/task-artifacts/<scope>/reviewed-candidate.patch`.
3. In the main worktree, require `git status --short` to be empty before applying.
4. Apply with index preservation: `git apply --index --whitespace=warn <patch>`.
5. Immediately compare `git write-tree` in main to the reviewed `candidate_tree`; a mismatch is a NO-GO and must be investigated before commit.
6. Re-run the canonical gates on the main worktree, write the handoff summary, restage, run a final precommit review, then commit/push only with explicit upload authorization.

Do not treat staging gate results as sufficient after promotion; they prove the candidate, while main gates prove the applied checkout and handoff file.

## Handoff takeover and tool-specific resume chains

When the user provides an `@file` handoff or says a project has a new handoff, treat that exact handoff as an active recovery input—not as optional background. Before changing anything:

1. Read the root `AGENTS.md`, every applicable module `AGENTS.md`, and the exact local handoff path. If the text reader reports a Markdown handoff as binary, use a read-only byte/decode fallback; do not skip it and do not copy it into a public artifact.
2. Extract and follow the handoff's Resume prompt literally. If it says “first report status only,” stop after read-only identity checks; do not inspect the next PR, run mutating gates, edit, commit, push, or clean up.
3. Inventory tool-specific handoffs as well as the project handoff: Codex, Hermes, desktop, gateway, provider, or module-specific recovery docs. A generic project handoff does not replace a Codex/Hermes operational handoff.
4. Reconcile every recorded SHA, branch, worktree state, process state, PR state, and CI claim against live read-only evidence. A newer live HEAD supersedes an older handoff SHA; a historical “CI passed” claim must not be reused for a later commit.
5. Report the baseline, active modules, tool-specific open item, stale-document conflicts, and explicit non-actions separately. Preserve local Git-ignored handoffs; never commit, upload, or expose their personal paths, credentials, auth state, sessions, prompts, or responses.

This is a takeover gate, not a delivery authorization. If the handoff says the next external item is a PR or live runtime check, stop at the requested status-only boundary and wait for explicit permission before any external mutation.

## Migration handoff versus live-state reconciliation

When a handoff document claims that a monorepo migration, archive, or publication is complete, treat the document as a historical/declarative input rather than proof of the current state. Before any legacy cleanup or cloud-repository archival:

1. Read the handoff, migration ledger, recovery guide, and task-pack summary, recording their claimed source tips, candidate paths, archive paths, approval gates, and explicit `NOT_EXECUTED` items.
2. Reconcile those claims against live evidence without mutating anything: current local `HEAD`, parent count/history shape, branch/worktree cleanliness, remote URL, GitHub default-branch SHA, branch/tag/release existence, and exact source/archive path existence.
3. Keep these states separate: current file-tree snapshot, full imported Git history, local-only dirty/WIP state, recoverable archive, remote migration branch/tag, and old repository archive. A locally-created root commit over an extracted snapshot is not equivalent to a history-preserving migration commit.
4. If a referenced archive or staging path is absent, record an evidence gap; do not recreate, infer, delete, or claim recoverability from the handoff text. If the handoff says active-path switching or legacy cleanup is `NOT_EXECUTED`, preserve that boundary until the live comparison and rollback evidence are complete.
5. Produce the comparison matrix before any destructive step, with per-item source path, target path, exact source/target identity, overlap/difference classification, archive handle, restore test status, and deletion approval. Never let a successful snapshot download or clean worktree silently promote a candidate to authoritative history.

This reconciliation pattern is detailed in `references/migration-handoff-live-reconciliation.md`.

## Migration archive retirement (split-repo evidence routing)

When a monorepo absorption left an external migration archive (full checkouts
with `.git`, source copies, manifests) and the user asks to "merge the useful
into this project, clear the rest", route evidence **by ownership** before any
merge or deletion:

1. Check whether the documented repos were split out to their own homes
   (`AGENTS.md`, module registry, `migration-status.json`, cloud repo
   existence). Evidence about a split-out repo belongs in THAT repo — do not
   re-absorb it into the absorbing monorepo. A user correction to this effect
   ("已经分库了，不该并入该项目") is a governance signal, not a preference to
   argue with: keep the split, and route each repo's manifests to its own home
   (or leave them with the cloud repo), merging into the monorepo only the
   evidence of repos actually absorbed into it.
2. Prove preservation before deleting anything, with reachability not
   existence: the archive HEAD commit exists in its cloud repo
   (`gh api repos/<owner>/<repo>/commits/<sha>` returns the sha) and
   absorbed-into-monorepo histories are contained in canonical `main`
   (`git branch --contains <sha>` — `git cat-file -e` proves existence, not
   reachability; the commit may be a dangling object).
3. Secret-scan the archive read-only before merging or deleting: classify
   `.hermes` (project runtime — check top-level entries for `state.db`,
   `sessions/`, `memory/`, `auth.json`; project `.hermes` is NOT the global
   Hermes home), `.codex`, browser test profiles (Chrome `Login Data` /
   `Cookies` / `History` / `Web Data` — real browsing artifacts even in
   "test" profiles), `.env`/key material. Report classes and counts, never
   values.
4. Classify regenerable content (pycache, caches) BEFORE archiving: deep
   target paths can exceed Windows MAX_PATH and abort the copy; regenerable
   content is deleted directly with a hash record instead of archived.
5. Merge evidence in-repo with per-file SHA-256 verification and a secret
   scan; update every tracked governance reference to the external archive
   (paths → in-repo copies; do-not-delete boundaries → retirement notes) in
   the SAME change; ship via PR; delete the external archive only after the
   PR merges (never before — the archive is the fallback if the PR fails).
6. If the user then narrows scope ("确定好没有<X>能用的就删除了吧，其他的你不要
   管，重新载入项目定位"), verify against EXACTLY the stated criterion (strict-
   subset comparison), reload AGENTS.md positioning, stop re-litigating the
   evidence-placement questions you raised, and execute the deletion with
   readback — the already-merged evidence PR stays unless redirected.

Full recipe and the observed case: `references/migration-archive-retirement.md`.

## Secret scan false-positive discipline

Candidate upload reviews should scan both path names and staged blob contents, but avoid blocking on policy vocabulary alone. Terms like `design token`, `credential`, `cookie`, or `private key` inside governance docs, schema enums, redaction policies, or safety-boundary lists are not secrets unless they are paired with an assigned secret-looking value. Prefer fail-closed patterns for real literals (private-key blocks, provider key prefixes, bearer tokens, long assigned token/password/secret values) and record known false positives separately from real hits. Never print matched secret values; report only the path and the class of issue.

## Read-only Git/GitHub/Release audit mode

When the user requests a read-only reconciliation of Git, PR, CI, Release, registry or ledger state, switch from delivery mode to audit mode and explicitly prohibit writes. Do not run `git fetch`, because it changes local refs; instead, record local worktree and tracking-ref state separately, then use read-only `gh` API commands for authoritative current remote state when authenticated. Never switch branches, clean/reset, commit, push, merge, download Release assets to disk, or edit a Release.

Use this evidence sequence:

1. For every relevant worktree, record `git status --short --branch`, `git rev-parse HEAD`, `git rev-parse --show-toplevel`, `git remote -v`, `git worktree list --porcelain`, and recent log entries. Record tracked changes and untracked files as separate counts.
2. Reconcile the local tracking ref with GitHub's current branch/commit API; do not assume `origin/main` is fresh merely because it exists locally. Report divergence counts, but label them as local-ref evidence unless confirmed remotely.
3. Query all PRs in the relevant class with `gh pr list --state all --json ...`; for each important PR preserve exact head SHA, merge SHA, state, merge time and URL. A branch remaining locally or remotely after merge is not an open PR.
4. Query CI by exact SHA and retain run ID, workflow, run URL, head SHA and job-level conclusions. A green PR workflow does not prove the post-merge push workflow is green; a failed job on the merge commit remains a failure even if the PR run passed.
5. For a Release, reconcile the tag ref, annotated-tag target commit, commit tree, published Release metadata, Release workflow run and public identity/checksum assets. Compare the identity asset's commit/tree/run against Git objects and the Release run. Keep historical Release identity separate from current `main` identity; do not treat `targetCommitish` alone as the source commit proof.
6. For JSON registries/ledgers, parse the exact tracked file at the authoritative remote ref when possible, count records and status/state distributions, and report the snapshot timestamp. Do not infer an external “Research Master” input count from an opaque archived ZIP; report the archive's presence/hash and the missing manifest/statistics as an evidence gap.
7. End with separate facts, candidates, and evidence gaps. Include a Not performed list covering fetch, writes, branch changes, Release mutations, asset downloads, extraction/execution of opaque research packages, and secret inspection.

Useful read-only commands include:

```bash
git status --short --branch
git rev-parse HEAD origin/main
git rev-list --left-right --count main...origin/main
git worktree list --porcelain
gh pr list --state all --json number,title,state,headRefOid,mergeCommit,url
gh run list --json databaseId,workflowName,headSha,status,conclusion,url
gh release view <tag> --json tagName,targetCommitish,isDraft,isPrerelease,publishedAt,url,assets
```

## Monorepo legacy reconciliation: tree truth versus worktree WIP

For a monorepo assembled from several legacy repositories, never use a clean
worktree or a handoff document as the sole uniqueness proof. Freeze and report
four separate identities:

1. the live cloud default-branch commit/tree;
2. the current local Git commit/tree and tracked status;
3. files physically present but ignored/untracked in the target worktree;
4. the legacy local/cloud source commit/tree and recoverable archive handle.

Before copying or deleting, compare legacy blobs against the target tree both by
intended mapped path and by SHA-1 blob at any target path. Cross-path matches are
valid evidence that content was absorbed under a new module prefix, but they do
not migrate PRs, releases, branch rules, or Git history. Report unmatched local
WIP separately from unmatched cloud-main content: a local feature branch may be
newer than the legacy cloud default branch and must not be discarded as a
“duplicate”.

Always inspect `git status --ignored` and `git check-ignore -v` for candidate
module paths. Broad rules such as `*token*`, `*oauth*`, or `*apps*` can hide real
source, tests, documentation, and assets, creating a false impression that the
tracked monorepo is complete. Treat ignored-but-present files as WIP until they
are explicitly classified and either promoted into the reviewed tree or
preserved in a hashed archive; never call them migrated merely because they are
visible on disk.

When the local target is a codeload/snapshot reconstruction, compare its exact
HEAD/tree with the live cloud default branch before promoting it to canonical.
A locally created root commit over a snapshot is not history-preserving and is
not equivalent to the cloud branch. Reconcile current cloud tree first in an
isolated staging directory; do not overwrite a dirty or WIP-bearing target
checkout to make the counts line up.

When staging from a public codeload snapshot, do not rely on a normal `git add -A` until you have checked ignore behavior: force-add the intended snapshot tree (or reconstruct the index from the remote tree), then require the staging tree SHA to equal the authoritative remote commit tree SHA. A normal clean status can still omit tracked remote files whose names match broad local ignore rules such as `*token*`.

For local cleanup, first create a separate file-level archive with source/destination SHA-256 readback, then prefer moving the original checkout—including its `.git` history—into a non-colliding archive path. If Windows returns `Device or resource busy`, inspect lock candidates and relevant process names; do not kill shared Hermes/Node/Python processes or force-delete the source. Record `BLOCKED_PROCESS_LOCK` and retry after the owning processes exit.

See `references/monorepo-legacy-reconciliation.md` for the compact evidence
matrix, commands, and deletion gate.

## Repository description versus formal project README

When a user asks to “update the repository description” and provides a Markdown project document, first distinguish two publication surfaces:

1. GitHub About metadata (`repos/<owner>/<repo>.description`): a short public summary;
2. the tracked formal README/module README: the authoritative positioning and capability contract.

Do not silently satisfy the request by changing only the About field. Read the supplied file and the current tracked README, then classify whether the user intends metadata, the formal README, or both. If the supplied document is a positioning README, preserve its canonical positioning at the top while merging—not blindly replacing—the existing operational feature index, tested links, evidence references, and documented boundaries. Replacing a mature README with a shorter positioning document can make governance tests fail even when implementation code is unchanged.

### Multi-surface positioning alignment (README + pyproject + About + naming matrix)

A positioning change rarely touches only one file. “全面更新描述，本地云端都要有” means align **every outward-facing surface** to the same canonical sentence, while leaving **internal/compatibility identifiers untouched**:

- Tracked README positioning line;
- `pyproject.toml` `project.description`;
- GitHub About `description` (via `gh api -X PATCH repos/<owner>/<repo> -f description=...`);
- any naming-alignment matrix (e.g. `docs/NAMING_ALIGNMENT_MATRIX.md`) user-facing target column;
- the authoritative positioning doc (`docs/PRODUCT_POSITIONING.md`), which is the source of the canonical wording.

Rules that make this safe:

1. **A truth contract test locks a substring prefix, not an exact string.** E.g.
   `EXPECTED_POSITIONING = "ArcheAxis OS is a local-first, evidence-driven Human–AI Learning Workspace"`
   asserted with `assert EXPECTED_POSITIONING in readme_head`. You can append
   wording (“— a bidirectional learning and knowledge system for individuals and
   AI”) as long as the locked prefix remains. Read the test before rewriting, and
   keep the prefix intact.
2. **pyproject `description` changes do not touch `uv.lock`** — the lock hashes
   dependencies, not metadata. No lock regen needed; run the product-truth test to confirm.
3. **Keep internal/compatibility identifiers as-is even when the outward name changes.** Tauri
   bundle id (`com.archeaxis.cognitive-workspace`), Python docstrings on internal
   modules, and historical handoff/blueprint docs are compatibility/historical
   surfaces — do not mass-rename them. Grep to confirm the old name only survives
   in those internal/historical places, then state that retention explicitly in
   the handoff so a future session does not “finish” the job by deleting them.
4. After aligning, `git diff --check`, run the product-truth/naming/release
   contract tests, and confirm the grep for the old outward name is empty across
   *current* docs (historical handoffs excepted).

### Tool config-management boundary written into the bottom layer

When the user states a scope rule for a transferred/external tool's config
management — e.g. "本项目不管理 OPEN DESIGN 全局配置（只管理设计相关的配置，任何能
提升设计的能力）" — treat it as a durable governance boundary, not a one-off note,
and write it into the BOTTOM layer across every surface in the SAME change:

1. `AGENTS.md` scope block and `00-governance/PROJECT_POSITIONING.md` — a
   human/agent-readable one-liner: "does NOT manage <tool> global config; manages
   only <design-relevant> config and any capability that improves <output>."
2. `config/config-ownership.json` adapter entry — add a `scope_note` clarifying
   the split, plus two scoped fields: `design_config` (MANAGE, project-overlay,
   explicit `scope` listing what IS managed) and `global_config` (OBSERVE, platform-
   internal, "NEVER managed, read-only version/digest"). The whole point is
   global/app state stays untouched while the capability-enabling subset is owned.
3. The owning JSON **schema** — a strict `additionalProperties: false` schema
   will reject the new `scope`/`scope_note` keys and flip the config-ownership
   test. Extend the schema's `properties` (adapter `scope_note`, field `scope`)
   as optional strings in the same commit, then rerun the schema test.
4. Regenerate tracked projections (`CURRENT_STATE`) that digest these inputs.

Verify with the config-ownership test + schema test + `core-schemas` gate. When a
concurrent writer has already pushed a partial version of the same boundary, check
whether its claimed fields actually landed (`git show <sha> -- <file>` — a commit
message can claim a field change that the diff does not contain); reconcile to the
user's latest instruction, which wins over the earlier partial phrasing.

### Machine identity vs user-facing name (rename scope + cutover window)

When the user says “项目名称还是旧的，全部更新” / “rename the project everywhere”,
do **not** mass-rename every occurrence. Split the name into two layers with very
different blast radii, and get the user to choose the scope:

| Layer | Examples | Blast radius if renamed |
|---|---|---|
| User-facing | GitHub About `description`, README positioning, `pyproject.description`, naming-matrix target column | Low — safe to align now |
| Machine identity | `pyproject` package `name`, wheel filename, GitHub **repository name**, release-identity `product.id`, `_RELEASE_REPOSITORY_URL`, Tauri bundle id, internal docstrings, historical handoff/blueprint docs | High — breaks wheel/checksum/release asset chain, every clone/PR/CI URL, and must not touch historical published asset names |

The outward name (`product.english_name` / README / About) may already be the
new name while the machine identity still carries the old internal name. When the
user asks to “change it all”, present this table, confirm the scope, and default
to: **align user-facing now, keep machine identity**, then offer a **cutover
window** instead of doing it mid-development.

A clean rename cutover exists only at a release boundary (e.g. the next
unreleased-dev version being promoted to Alpha), because:

- Historical already-published asset names (e.g. `cognitive_loop_os-0.4.4-*.whl`)
  are frozen by the no-rewrite-history rule; a package rename does not
  retroactively rename them, so old and new names would coexist for a while.
- Renaming `pyproject` `name` requires a chained change: `uv.lock` package name,
  wheel asset name in the release workflow, checksum/allowlist assertions, CI
  references, and `release-manifest.json` `product.id` — a full re-verify, not a
  one-line edit.
- Renaming the GitHub repository additionally requires updating
  `_RELEASE_REPOSITORY_URL`, every clone command, and PR references; GitHub 301s
  old URLs but the hardcoded repo URL in release identity must be synchronized.

Recommended sequencing to state: **align user-facing now; keep machine identity
through K1–K6; at the R1/0.5.0 release-cutover do the full package/repo rename as
one atomic migration with a chained-change checklist and full CI re-verify**,
leaving historical v0.4.x asset names frozen. If the user insists on renaming the
package now (dev line is unreleased), do it but warn about the coexistence period
and the chained edits.

When local history is not a safe fast-forward of the remote branch, do not force-push a reconstructed snapshot. For a narrowly scoped documented file update, use the remote file's current blob SHA as a compare-and-swap guard with the GitHub Contents API, then read back the returned commit SHA, public raw-file SHA-256, required marker strings, and exact-head CI run. Keep broader local staged candidates separate until their tree/history integration is independently reviewed.

### Full machine-identity rename, executed (repo + package + CLI)

When the Owner authorizes the full rename (repo name, package name, CLI entry, schema URIs), the executed 2026-08-12 sequence (Cognitive-Loop-OS → archeaxis-workspace, PRs #131/#132/#133) and its traps:

1. **Package identity first, repo rename last.** Step 1: `pyproject` name → new name, `uv.lock` regen (`uv lock`), CLI entry point (`[project.scripts]`), `release-manifest.json` `product.id`, schema URIs (e.g. `cognitive-loop-os.local` → `archeaxis.local` — sync app/contracts/v1.py AND every contract test in the SAME change or tests fail), CI `installed_version(...)` assertions, wheel names in `release.yml` and `prepare_bundle.py` globs. Bump `release-manifest` dependency_lock digest (lock changed → digest check fails otherwise). Full suite must stay green before the next step.
2. **Repo rename:** `gh repo rename <new> --repo owner/old --yes` → verify `gh repo view` → `git remote set-url origin git@github.com:owner/new.git` → `git fetch origin main` to prove it works.
3. **Reference sweep traps (the ones that actually bit):**
   - **Never replace local absolute paths.** On-disk dirs do not rename with the repo: `D:/All projects/<old>` stays. A sweep that rewrites them silently breaks real lookups (observed: `test_workspace_pdf_endpoint.py` fixture paths → 2 tests flipped to skip with zero error, suite went 1461→1459). After any sweep, `git grep -n 'All projects/<newname>'` and restore.
   - **Legacy/alias mapping tables are inverse whitelists.** A naming contract §3 table exists to record old→new; a blanket replace corrupts it. Restore the old name in that table + append a revision row instead.
   - **Frozen/authority artifacts keep the old name**: baseline SHA docs, frozen taskpacks, `AUTHORITY_CONTRACT`, `.sha256`, `.zip` (binary), machine-generated `.txt`/`.stat` reports. Editing breaks integrity checks / the no-rewrite rule.
   - Verify after sweep: `git grep -l '<old>'` must match ONLY the frozen/legacy list; tests/scripts zero old-name assertions.
4. **CI cargo-cache trap after repo rename:** `actions/cache` restores a cache whose entries embed the OLD checkout path (`D:\a\old-repo\...\desktop\src-tauri\target\...`); the renamed repo checks out to `D:\a\new-repo\...` → Rust/Tauri build fails `os error 3: cannot find the path` inside `target/`. NOT a code bug. Fix: bump the cache key prefix (e.g. `v2-`) so the stale cache misses; do not touch code.
5. **CI-status API lag:** `gh run view` can show `in_progress` for a job that actually finished (runner completes, API lags). Query `gh pr checks <N>` for authoritative per-job conclusions instead of trusting the aggregate.
6. **Split the sweep into its own PR** (docs sweep of 60 files) separate from the code/reference PR (7 files) so a doc-sweep mistake doesn't block the code rename.

Full commands and the observed failure/skip signatures: `references/repo-rename-playbook.md`.

## Remote-tree promotion and safe local cutover

For a reviewed candidate whose local history is not a safe fast-forward of the remote default branch, use the Git Data API with the remote tree as `base_tree`: upload only audited staged blobs, re-check the remote commit before creating the commit, update the branch with `force=false`, and verify exact commit/tree/CI. If the local index/worktree tree already equals the published remote tree, create a recovery ref and update only the local branch ref with an old-value guard; do not reset or clean. Keep historical publication fields separate from current live HEAD fields, and treat Windows `Device or resource busy` during legacy checkout movement as a preserved `BLOCKED_PROCESS_LOCK`, not permission to kill or delete. Verify public files with a commit-pinned URL or Git blob when a branch raw URL may be CDN-stale. See `references/remote-tree-promotion-and-cutover.md`.

## Observable feature entry: skeleton PASS is not a user-visible entry

An observability/observer module is not closed when its structural verifier, unit tests, and skeleton pass. The user-facing demand is "怎么观测 / 界面入口在哪里". A class-level rule: a read-only dashboard/observer feature is closed only when it has

1. a documented, reproducible launch command (stdlib HTTP server is enough; bind `sys.path` to the module `src/` so the documented root-level command runs without test-only path injection);
2. fixed, documented GET-only routes (`/`, a JSON projection route, `/healthz`);
3. live HTTP smoke evidence (all routes return 200) and a rendered-browser snapshot;
4. a runtime regression test that boots the in-process server (port `0`) and hits the routes;
5. that regression test wired into the CI job, not just the local suite.

When a CLI script crashes on the *documented* launch path (e.g. `ModuleNotFoundError` on a module-internal package) but passed when tests injected `sys.path`, the entry point is broken even though tests are green — fix the script's own import binding, not the tests. A feature's user entry must work exactly as documented, independently of test scaffolding.

Also embed the approved visual direction so the next dashboard starts there: near-black precision surfaces (Linear), translucent glass navigation + large whitespace (Apple), restrained shadow-as-boundary (Vercel), single interaction accent, mono technical labels. Avoid generic admin-template chrome and decorative gradients.

## Closing an UNVERIFIED provider/runtime audit item credential-free

When an audit item (e.g. W5 provider runtime) needs real "provider is live" evidence but the project overlay deliberately ships no provider/model/keys (fail-closed), do not inject credentials into the project to make it pass. Instead:

1. Confirm the project's credential-free `config.yaml` is an intentional design boundary, not an evidence gap.
2. Probe the global Hermes runtime's login state without reading auth contents (`hermes auth status <provider>` reports logged-in/out only).
3. Run the same marker contract used by the repo's `--live` path against the global provider:
   `hermes chat --provider <p> -m <m> -q "Reply exactly: <MARKER>" -Q --toolsets safe` → exact marker + exit 0 is real runtime evidence.
4. Report three separate claims: project overlay (`UNVERIFIED`, correct fail-closed), global provider (`LIVE_OK`), credentials (`[REDACTED]`, never read or persisted). Do not call a structural/credential-free inventory a `LIVE_OK`, and do not treat the project overlay's `UNVERIFIED` as "not done."

## P0 upstream selection: ADR + feasibility spike before implementing

When a stage requires choosing reusable upstream libraries (e.g. an
Obsidian/Markdown/JSON-Canvas compatibility slice: Markdown AST, YAML
round-trip, JSON Canvas spec, FSRS scheduling), do not implement from a
candidate's reputation or a demo. Follow the reuse-ladder selection workflow:

1. **Audit candidates read-only via the GitHub API** before any code. For each
   repo: `gh api repos/<owner>/<repo> --jq '{name:.full_name,license:(.license.spdx_id//"none"),pushed:.pushed_at,stars:.stargazers_count,archived}'`.
   Record license SPDX, last-push activity, and archived flag. This catches
   dead/archived picks (e.g. `lezer-parser/markdown` archived) and license
   mismatches before they're pinned.
2. **Write a Decision Record (ADR)** with, per P0 component: preferred pick,
   license, activity, **reuse mode** (direct dep / SDK / fork / adapter /
   self-build), and the rejected alternatives with reasons. State the technical
   stack so the pick matches it (Python backend + Tauri shell → prefer Python
   libs for backend truth; JS only where the frontend actually consumes it).
   For a JSON/format *spec* (JSON Canvas), self-build against the official spec
   is correct — it is not "reinventing", it avoids a heavy third-party renderer
   dependency. Name it explicitly as a data contract.
3. **Run a minimum feasibility spike that is read-only and adds no deps.** A
   spike that requires editing `pyproject.toml`/`uv.lock` is not "minimum" —
   verify against whatever the toolchain already has (project venv, or a
   checked-in runtime that ships the candidate), or use `PYTHONPATH` into an
   existing venv that has it. Prove the claims that matter (e.g. YAML
   round-trip preserves comments/key-order/multiline; Markdown AST parses
   headings/lists; frontmatter separates from body). A spike is evidence the
   *choice is feasible*, not that the feature works.
4. **Defer actual dependency injection to the implementing TaskPack.** The
   selection ADR records the choice and the spike proves feasibility; the
   next TaskPack fixes the exact commit/tag + `uv.lock` + release-manifest
   digest per the dependency-pinning policy. Do not add deps during selection.
5. Close the selection TaskPack with the ADR as its deliverable; do not claim
   the component is implemented. The green gate for a selection-only change is
   the contract test that reads the ADR, not a feature demo.

This keeps selection decisions auditable and prevents "we picked a library so
the feature exists" overreach.

## Truth-doc consistency: partial data updates leave contradictions (validated 2026-08-15)

When a data-driven truth document (benchmark report, capability matrix,
metrics doc) receives NEW data, audit the WHOLE document for old-number
carryover, not just the section you are editing. Observed: a benchmark
report's measurement table was updated to a zh/en hybrid corpus, but the
corpus layer table and the leading quote block still carried the initial
English-only figures (5 books / 147.6 KiB / 4.5 MiB vs the new 14 books /
2.3–12.5 MiB) — an internal contradiction that stayed latent for four
rounds until a targeted re-read caught it. Procedure:

1. After any data update, grep the doc for the OLD distinctive numbers
   (file counts, byte sizes, book IDs) and for every place the metric
   appears: quote/status blocks, tables, prose intervals ("scale→latency
   (X→Y MiB, A→B ms)"), and reproduction notes.
2. Cross-check every number against the actual data source
   (e.g. `benchmark.json` + `corpus/sources.json` + per-layer directory
   stats), never against memory of the earlier edit.
3. Fix in ONE commit with the LOG entry; a report that contradicts itself
   is worse than a report that is merely outdated.

Related: a long multi-round baseline can leave handoff documents stale —
the HERMES_HANDOFF.md may still point at a dead branch and completed
completed tasks (observed 2026-08-15: a handoff from 2026-07-23 referencing
`feat/runtime-evaluation-sleep-leases` while main had advanced ~60
commits). When continuing an extended baseline, refresh the handoff
(continuation point, closed LOG range, CI run window, remaining
Owner-gated items, environment facts) as part of closure work — a stale
handoff misroutes the next session's first actions.

Handoff baseline NUMBERS go stale too: the header's full-suite count
(e.g. "1532 passed") drifts as tests are added across a long session —
re-run the full suite locally before updating it and record the run
date; never carry the old number forward (observed +48 tests in one
session). Sync HANDOFF + CHANGELOG [Unreleased] + the append-only LOG in
ONE commit so the three documents agree; the handoff header's LOG
interval and CI run window are the first fields to go stale, so grep the
whole doc for old intervals/counts (a stale-check pass) after each sync
rather than trusting the header alone.

## Canonical verifier extension and nested package closure

When adding a verifier to an existing aggregate, update the executable child list, summary/count assertion, identity/old-name scan coverage, focused negative regressions, and the CI path/filter contract together. A verifier that exists but is only conditionally run can leave manifest/schema/verifier changes outside the gate. A docstring or policy phrase can also trigger a naive forbidden-pattern scanner; run identity checks after aggregate edits and use neutral wording or a tested scanner exemption.

Under the guarded project-data wrapper, nested Node launchers may run from the Git root even when the call names a module directory. Resolve the launcher cwd from `__dirname` (or use a real bootstrap), require a meaningful nonzero test count, and treat `0 tests`, path-not-found, or selector success as no evidence. After local verification, commit before rerunning the release gate so `DIRTY-WORKTREE` is not confused with a product finding; then query CI by the exact full SHA captured from `git rev-parse HEAD`. The reusable checklist and reproduction signatures are in [`references/canonical-verifier-extension.md`](references/canonical-verifier-extension.md).

## Evidence-index consistency and governance-drift audit

When a project uses capability, evidence, status, manifest, or roadmap files as release truth, audit them as one contract rather than trusting a single green verifier:

### Exact-SHA query and non-self-referential binding guard

After a delivery commit, obtain the candidate identity from the checkout itself (`git rev-parse HEAD`) and use that exact 40-character SHA for GitHub Actions/API queries. Never expand a short SHA by hand or infer its full value; an API response of `workflow_runs: []` for a guessed SHA is selector failure, not evidence that CI did not trigger. Compare the returned run's `head_sha` to the locally captured SHA before interpreting status or conclusion.

Tracked evidence indexes must not require `boundTree == HEAD` when the index is committed into the tree it describes. Bind the index to the last fully verified input tree, validate that it is an ancestor of the current HEAD, and refresh it in a follow-up docs commit when the new baseline itself must be recorded. This avoids a self-referential freshness invariant while keeping the evidence binding current. After a rebind-only commit, rerun the aggregate verifier, root tests, exact-SHA CI, and release gate; a clean release gate may still remain blocked solely by an explicit human/live-acceptance item.

Nested frontend packages require an explicit package-directory execution strategy. When the project-data wrapper starts from the repository root, use a real Node bootstrap that changes into the nested package and invokes its actual launcher; require a meaningful nonzero test count and treat `0 tests`, path-not-found, or a selector error as no evidence. Run the package's verification summary in addition to its unit suite so strict bundle, schema/content, and platform-specific checks are not silently omitted.

### Aggregate-verifier coverage and read-only audit discipline

For a verification-surface audit, build a coverage matrix rather than trusting the aggregate's headline count. Enumerate executable verifier scripts, the aggregate verifier's explicit child list, every CI job/step, root/module test entrypoints, adapter manifests/registries, and README/ROADMAP commands. Classify each verifier as `aggregate`, `CI-only`, `test-only`, `release-only`, `conditional`, or `unreferenced`; an actual production fixture is not covered merely because a unit test exercises synthetic temporary fixtures. Compare registry IDs against manifest IDs and report missing manifests separately from intentional declaration-only states. Treat documented test counts as observations that must be refreshed from the real entrypoint, not as permanent contracts.

A read-only audit must inspect whether an aggregate writes a HEAD marker, generated bundle, or other ignored evidence before running it. If the user forbids file modifications, do not invoke a marker-writing aggregate just to obtain a green headline: run safe child verifiers directly, inspect write-on-pass/fail behavior, and state that the final aggregate was not rerun under the no-write constraint. Never reuse a pre-commit aggregate result after HEAD changes; concurrent commits require a fresh HEAD/status snapshot and a new evidence classification. A current marker proves only the exact tree it names, not that every component was run in the present audit.

1. Read live `HEAD`, tracking branch, worktree status, current CI workflow, and the active task matrix before interpreting any historical report. A report bound to an ancestor SHA can remain valid as historical evidence, but it must not be presented as proof for the current tree.
2. Cross-check every detailed evidence record against the top-level capability's current `actualEvidence`, the capability-status entry, and the product manifest ID. A record must never claim a higher level than the current capability; stale E3 records after an E1 requalification are an internal contradiction, not usable runtime proof.
3. Make the aggregate verifier execute the consistency check. Add a regression for the bad-data path, including invalid enum/evidence values; malformed governance data must return a diagnostic failure, not a `KeyError`/traceback or silent skip.
4. When adding a new verifier to the aggregate chain, update the documented verifier count and the focused test count only as a dated/read-back observation. Run the real project test entrypoint and the module-specific runtime test from the module's actual working directory. A zero-test discovery result is selector evidence, never a passing suite.
5. Treat GitHub Actions version tags as mutable supply-chain inputs. Pin every action to an official full commit SHA with a human-readable version comment, then grep the workflow for remaining floating `@vN` references.
6. Keep the release gate honest: local tests, committed tree, remote branch, exact-head CI, merged main, live runtime, human acceptance, and commercial acceptance are separate levels. A dirty worktree or pending human/live gate must remain BLOCKED even when all structural verifiers pass.

This audit class is complementary to the exact-SHA CI delivery skill: it closes stale projections and cross-file evidence drift before any PR/merge claim, while exact-SHA delivery proves the resulting candidate and merge trees.

## Structural capability evidence promotion and multi-SSOT closure

When an audit finds a capability marked below its minimum level, do not either
leave a verifiable structural floor unrecorded or promote it based on prose and
counts alone. Separate the evidence classes first:

1. **E0/declaration** — scope, artifacts, or intended work only;
2. **E1/structural** — deterministic schema/shape/count/uniqueness/eligibility
   checks pass against tracked artifacts;
3. **E2+** — requires the repository's stated stronger evidence (for example
   source provenance, isolated runtime, human review, or live registration).

For a legitimate E1 promotion, inspect the whole tracked evidence surface, not
just the capability index: registry JSON, method/card/lineage artifacts, schemas,
existing tests, status files, human-readable capability tables, and roadmap notes.
Write a small deterministic verifier that fails closed on missing files, malformed
objects, count drift, duplicate IDs, invalid enum/eligibility values, and unsafe
or direct-generation markers. Emit a stable machine-readable summary with actual
counts and `errors=0`; do not turn a draft source collection into E2/E3 merely
because its structure is complete. Add one focused regression test and add the
verifier to the aggregate chain so CI exercises the same proof.

Synchronize every current SSOT in one change: detailed evidence index, capability
status, human-readable capability index, aggregate verifier list/summary parser,
focused tests, and roadmap/handoff status. Historical reports stay historical;
do not rewrite them to make the current level look better. Re-run the focused
verifier, evidence verifier, aggregate gate, focused tests, and release gate. The
correct outcome may be `RELEASE_GATE=BLOCKED` with one fewer finding; that is a
successful honest repair, not a failed delivery.

Delivery sequence:

1. Capture the candidate SHA with `git rev-parse HEAD`; never expand a short SHA
   by hand or invent its remaining characters.
2. Commit only the audited implementation/index/test scope, push it, and query
   CI by the exact full SHA. Compare the returned `head_sha`, workflow,
   conclusion, and run ID before recording success.
3. If a follow-up documentation commit records that CI result, it creates a new
   SHA. Re-run the aggregate and release gate on that final tree and query CI
   again by the final exact SHA; the previous green run remains historical.
4. Keep tracked evidence binding non-self-referential: an index committed into
   the tree it describes must not require `boundTree == HEAD`. Bind it to a
   verified ancestor or use a reviewed-scope freshness rule, then revalidate
   ancestry and the final tree.

A common observability defect is adding a verifier to the aggregate while the
aggregate's summary-prefix parser ignores its output. Add the new stable prefix
(e.g. `STYLE_MASTER_METHOD=`) and a regression that asserts the summary is
visible. For nested package gates, use the real package working-directory
bootstrap and require a meaningful nonzero test count; selector/cwd success is
not product evidence.

## Runtime evidence promotion is fail-closed


When a repository contains adapter registries, manifests, evidence READMEs, and runtime candidate records, treat the whole runtime-evidence surface as one contract. A stale E3-looking file is not current proof merely because it is tracked or because a structural gate is green.

1. Establish the current full `HEAD`, target branch, worktree status, and exact CI baseline before interpreting any runtime record. Short SHAs, ancestor-bound records, old run URLs, and external paths are historical clues until requalified against the current tree.
2. Cross-check the registry, independent adapter manifest, evidence README, capability index/status, and verifier code. For a frozen or unexecuted adapter, every active surface must say `E0`/declared/not-supported (or the repository's equivalent), while historical candidates must be explicitly marked invalidated and non-promotable.
3. Keep historical records for auditability, but do not preserve active prose such as "runtime verified", "weights downloaded", "registered", or "E3" unless it is bound to the current exact SHA and an actually accepted run. Never inspect or reproduce external runtime paths just to make a stale record look current.
4. An E3 promotion must require, at minimum: the current full 40-character HEAD, runtime identity/version, task identity, artifact provenance, read-back/integrity evidence, and a matching E3 evidence record. A keyword-only README check is not a sufficient gate; add a regression that rejects stale short-SHA evidence and accepts a valid current-tree fixture.
5. Run the focused evidence gate, aggregate verifier, root tests, module/runtime tests, `git diff --check`, and exact-SHA CI after every evidence-level repair. Re-run the release gate only after the final marker/HEAD is fresh; pending human or live-runtime acceptance remains BLOCKED.

The reusable checklist and the observed E0/E3 stale-record repair are in [`references/runtime-evidence-promotion.md`](references/runtime-evidence-promotion.md).

## Platform acceptance and human-evidence gates are fail-closed

When a verification contract includes a platform-specific acceptance step (for example, Android APK build/metadata/install) or human-calibrated Evidence Cards, absence of the required execution environment is a blocking result, not a successful skip. A structural/unit suite can remain green while the platform acceptance is unexecuted; report those evidence levels separately.

1. Read the acceptance contract and aggregator implementation before interpreting `SKIP`, `NOT_RUN`, or zero-test output. If the contract requires the platform step, missing JDK/SDK/build tools, missing APK, or missing metadata read-back must return a nonzero/fail-closed result. Never manufacture an APK, runtime ID, latency, visual score, or install read-back.
2. Keep automated structural evidence, isolated runtime evidence, platform evidence, live runtime registration, human calibration, and production acceptance as separate gates. A successful canonical verifier or exact-SHA CI run does not promote any missing later level.
3. Release gates must validate human Evidence Card records structurally: count only records with the expected accepted state and a dictionary-shaped `human_calibration` whose explicit status is `completed`. Missing, `null`, or malformed calibration is pending/blocking, not accepted and not a verifier traceback.
4. Add regression tests for both false-green paths: a required platform check incorrectly treated as `SKIP`, and an Evidence Card with a truthy/accepted marker but absent or malformed calibration. Re-run the module gate, aggregate verifier, exact-SHA CI, and release gate after the fix; the release gate should remain blocked when real human/live evidence is absent.

## Active SSOT positioning and evidence-surface closure

When an audit also reloads a project's positioning, do not stop at the main product-definition file. Treat the active positioning as a multi-surface contract:

1. Read the binding product definition, boundary contract, machine-readable manifest, active entrypoint, active profiles, and current capability/evidence status. Historical V2/V3/V4/V4.2 documents, migration records, and old reports are traceability inputs, not current authority.
2. Scan active surfaces for superseded filenames, retired product identity, old verifier counts, and claims such as "registered", "integrated", or "E3". Exclude only explicitly historical/archive/report paths; a stale reference in an active profile or launcher is a real drift finding.
3. Cross-check prose claims against the current evidence index. Static files, old Axe output, or a passed structural verifier may support E1/E2, but must not be described as current Host registration, live execution, E3, E4, or production readiness. Downgrade the active claim or add an explicit requalification boundary; do not rewrite historical evidence.
4. Re-run the real canonical entrypoint after the repair and inspect its summary count. If it writes a HEAD-bound marker, rerun it after every commit that changes the tree before invoking a release gate. A release gate that reports stale marker/SHA is a freshness signal, not a reason to reuse the previous green result.
5. For nested JavaScript projects under a guarded Windows monorepo, assume the project-data wrapper may execute from the Git root rather than the nested package directory. A path-not-found result or `0 tests` is selector/cwd evidence, never a pass. Use the real launcher with an explicit nested working-directory strategy (for example, a Node bootstrap that `process.chdir()`s into the package and loads the launcher via `path.join`), then verify the expected nonzero test count.
6. After delivery, fetch and compare full `HEAD` and `origin/<branch>`, query GitHub Actions by the exact full SHA, wait for the exact run, and keep human acceptance/live-runtime/commercial gates separate from structural CI.

See [`references/active-positioning-and-wrapper-workarounds.md`](references/active-positioning-and-wrapper-workarounds.md) for the compact checklist and the validated Windows nested-test reproduction.

## Fail-closed release contracts and nested package execution

A machine-readable schema file is not evidence that the verifier enforces the schema. A release-evidence verifier must load and execute the validator, fail when the validator dependency or schema is unavailable, and enforce the release invariants that generic schema shape cannot express: `state=PASS`, `worktree=clean`, CI `conclusion=success`, and explicit `read_back.verified=true`. Add a schema-valid negative fixture with a failed CI conclusion; it must fail before live Git facts are treated as proof.

For manifest fields that point to collections (`benchmarks/`, `evidence/`), require `is_dir()` and at least one file; for file elements require `is_file()`, not merely `exists()`. Add the verifier for at least one real tracked pack to Canonical CI instead of relying only on temporary fixtures. The full reproduction and recovery recipe is in [`references/fail-closed-evidence-and-nested-runtime.md`](references/fail-closed-evidence-and-nested-runtime.md).

Under a guarded project-data wrapper, a nested Node launcher may execute from the repository root even when the tool call names a module working directory. A launcher that resolves `tests/*.test.js` from `process.cwd()` can therefore return `0 tests` or a path-not-found error with exit 0/1. Both are selector/cwd evidence, never a pass. Inspect the launcher, enumerate tracked test paths, use an explicit nested-package bootstrap or tracked paths, and require a meaningful nonzero summary (`1..N`, `pass N`, `fail 0`). Re-run the package's strict bundle/platform verifier separately.

After every implementation or documentation follow-up commit, capture the full SHA from `git rev-parse HEAD`, query CI by that exact SHA, compare returned `head_sha`, and rerun current local aggregate/release gates. A prior green SHA is historical only; a correctly blocked human/live gate remains blocked.

## Manifest file-kind and path-containment audits

When a verifier consumes a manifest containing paths, `Path.exists()` is too weak: a directory can masquerade as a file, and a relative path such as `../../README.md` can escape the owning pack while still resolving to an existing object. For each declared file, require `is_file()`; for collections require `is_dir()` plus the required non-empty structure. Resolve the path and prove it is inside an explicit allowlist of roots with `candidate.relative_to(allowed_root)` (or an equivalent path-segment-aware check), not with string-prefix matching.

Do not over-tighten containment by assuming every asset must live beside its manifest. First read the repository contract: if the project intentionally stores generated assets in a shared runtime root, pass that exact root as a second allowlisted base. Reject all other roots, absolute paths, and traversal destinations. Add both negative controls (directory masquerading as a file; traversal to an unrelated existing file) and a positive fixture for every legitimate shared asset root. Run the real tracked-pack verifier, not only temporary fixtures, because fixtures may miss cross-module layout contracts.

## Evidence levels

Keep these claims separate:

- `LOCAL_TEST_PASS`: local tests and quality gate;
- `REPOSITORY_COMMITTED`: commit SHA exists locally;
- `REMOTE_BRANCH_UPLOADED`: remote branch contains the SHA;
- `PR_CI_PASS`: required checks for that exact SHA passed;
- `MERGED`: target branch contains the merge commit;
- `LIVE_DEPLOYED`: a live profile was changed and read back.

Never infer a later level from an earlier one.

## References

- Use [`references/historical-report-boundary.md`](references/historical-report-boundary.md) when dated reports contain stale E3/E4/E5 or runtime wording: establish a tracked historical boundary, mark sensitive snapshots, add a negative-control verifier, and query CI only with a captured full 40-character SHA.
- Use [`references/concurrent-writer-candidate-reconciliation.md`](references/concurrent-writer-candidate-reconciliation.md) when HEAD/index/status changes during an audit or asynchronous review; freeze reviewers to immutable trees, reconcile without destructive cleanup, and compare the full candidate against the intended remote base rather than the new HEAD.
- Use [`references/generated-state-ci-portability.md`](references/generated-state-ci-portability.md) for reviewed-scope freshness, non-self-referential tracked JSON/Markdown projection checks, portable curated `unittest` selection, shallow-checkout, and offline-schema failures.
- Use [`references/audit-handoff-template.md`](references/audit-handoff-template.md) for the reusable handoff/manifest checklist and evidence table.
- Use [`references/readonly-github-audit.md`](references/readonly-github-audit.md) for the no-write Git/PR/CI/Release/registry reconciliation recipe.
- Use [`references/governance-doc-live-state-reconciliation.md`](references/governance-doc-live-state-reconciliation.md) when final-reviewing approval/status/CURRENT_STATE/ledger documents during concurrent commit/push/PR/CI transitions; it covers exact-SHA rebinding, count-vs-closure semantics, future timestamps, and historical Release versus current-candidate truth.
- Use [`references/taskpack-staging-promotion.md`](references/taskpack-staging-promotion.md) for exact-tree promotion of reviewed TaskPack/overlay staging candidates into the main worktree.
- Use [`references/release-identity-and-ci-workflow-authoring.md`](references/release-identity-and-ci-workflow-authoring.md) when editing release-identity schemas or CI workflows: cross-step `$GITHUB_OUTPUT` passing, schema-version bumps with backward-compat readers, `Cargo.lock` root-package drift, fresh-checkout missing runtime dir, YAML comment/glob quoting, deterministic path→risk→gate classifiers, PR-only concurrency cancellation, selective heavy-job routing under full-qualification (§8), two-point-diff fail-closed GatePlan diffing (§9), validating selective routing in real CI (§10), and distinguishing a known-flaky CI job from a regression (§11).
- Use [`references/axw-main-chain-e2e.md`](references/axw-main-chain-e2e.md) when delivering or extending ArcheAxis-Knowledge-OS main-chain integration tests (ingestion → conversion → evidence ledger → human learning → AI assets): the real module/table map, format support matrix (txt/md/html zero-dep; docx via optional markitdown), the mastery-3-practices rule, the validated E2E recipe with wrapper commands, and the sqlite3.Row / mammoth-underscore / other-batch-WIP pitfalls.
- Use [`references/repo-rename-playbook.md`](references/repo-rename-playbook.md) when executing an Owner-authorized full rename (repo + package + CLI): the package-identity-first sequence, reference-sweep whitelist (never local paths / legacy mapping tables / frozen artifacts), the post-rename CI cargo-cache path trap (`os error 3`), and naming-contract maintenance.
