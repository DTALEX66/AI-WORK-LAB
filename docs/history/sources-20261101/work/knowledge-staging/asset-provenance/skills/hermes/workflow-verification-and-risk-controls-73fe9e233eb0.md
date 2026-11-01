---
name: workflow-verification-and-risk-controls
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/workflow-verification-and-risk-controls/SKILL.md
---

---
name: workflow-verification-and-risk-controls
description: "Use for fail-closed workflow verification and rollback."
version: 1.8.3
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, verification, risk, rollback, taskpack, security]
    related_skills: [agent-workflow-fortress, test-driven-development, systematic-debugging, project-data-boundary, github-branch-hygiene]
---

# Workflow Verification and Risk Controls

## Purpose

Use this skill when a Hermes/Codex/CC Switch workflow pack claims to be portable, safe, auditable, or releasable. It specializes in the boundary between implementation and proof: no hard-coded green checks, no caller-controlled risk downgrade, no required subprocess failures swallowed, and no in-place deployment without recovery.

This skill complements `agent-workflow-fortress` (overall orchestration) and `test-driven-development` (RED→GREEN discipline). It does not replace them.

## Operating contract

1. Establish the live repository baseline before edits: branch, HEAD, worktree status, relevant test command, and the exact task scope.
2. Read the manifest, policy, runner, verifier, deployment entry point, and existing tests before changing behavior.
3. Convert every suspected gap into a behavioral negative control. Prefer a real subprocess, filesystem, or deployment boundary over a source-string assertion.
4. Run RED and confirm the failure is the intended contract failure—not an import error, wrong test selector, syntax error, or missing environment dependency.
5. Implement the smallest fix, run GREEN, then run the affected suite and canonical full gate.
6. Keep evidence levels distinct: structural proof, runtime proof, network reachability, provider execution, and exact-SHA CI are different claims.
7. Do not commit, push, apply to a live home, or alter remote policy unless separately authorized.

## Moving software baselines and user overlays

For workflow packs spanning Hermes, Codex, Node/npm, Python, GitHub CLI, or MCP packages, do not hardcode the currently observed runtime or package version into the configuration contract. Resolve executables through PATH or supported launchers, record `--version` only as run-specific evidence, and discover flags/capabilities from current `--help`, schemas, or manifests before relying on them. A future update is a new compatibility candidate: rerun discovery, isolated portable verification, quality gates, and exact-tree review.

Keep three layers separate: the official product baseline, the repository's explicitly Workflow-owned overlay, and user-owned config/skills/plugins/MCP/provider/model/auth/session/memory state. Preserve user customization and live drift; fail closed on ownership mismatch rather than overwriting it. A candidate-package audit may require a pinned provenance version for supply-chain evidence, but that must remain distinct from live runtime version selection. Verify the official package name, wrapper/launcher boundary, and isolated-home behavior without forcing a runtime pin merely to satisfy a structural verifier.

When implementing a Codex-backed runner, make capability discovery executable rather than documentary: invoke the resolved binary's current `exec --help`, parse long options in both `--flag` and `-s, --flag` forms, require only the flags the runner truly needs, and fail closed before creating/launching the review if any required capability is absent. Keep a fake-CLI regression test that returns help first and then the review process; assert the runner does not pass `--ignore-user-config` or `--ignore-rules` when the requested contract is to preserve the user layer. Recompute the review digest after changing the runner or its fixture.

Before deleting local or remote branches, verify the GitHub PR is merged, no open PR uses the branch, and it is not the current or a recovery branch. For a squash merge, do **not** require `git log main..branch` to be empty or rely on `git branch --merged`: the original commits are intentionally not ancestors of `main`. Instead bind the PR head SHA and merge SHA, require their tree IDs to match (or an explicit content diff to be zero), and confirm GitHub/main/origin all resolve to the merge SHA. Delete local and remote refs separately, query the remote to prove the ref is gone, then prune local tracking refs. For non-squash merges, ancestry remains useful but still does not replace PR-state and remote readback.

## Fail-closed gate design

### Structural versus runtime proof

A portable verifier may prove copied trees, parsed configuration, pinned wrappers, manifest declarations, and absence of credentials in an isolated home. It must not set a required runtime check to `True` merely because the manifest names it.

Use an explicit result contract:

- `STRUCTURAL_PORTABLE_PASS`: structural checks only;
- `RUNTIME_COMPATIBILITY_UNVERIFIED`: the real runtime command was not run;
- `PORTABLE_INSTALL_VERIFY_PASS`: structural plus real isolated runtime check passed.

The runtime gate must invoke the real application against a fresh temporary home, set the home variable to that isolated path, avoid credentials/network unless explicitly requested, and be registered as a separate required local gate. A default structural run that silently claims runtime compatibility is a false positive.

### Required command propagation

Every required subprocess must have its return code propagated into the final status. A doctor that prints a failed `config check`, auth inventory, or MCP inventory and still returns zero is invalid. Optional provider/network checks may be `UNVERIFIED`, but they must be visibly labeled and never counted as required PASS.

Use a small `required_command()` boundary and test it with failure injection. Test the final process exit or summary where practical, not just the helper's Boolean return.

### Retired compatibility paths are negative contracts

When an endpoint, helper, or launcher is marked retired, retirement is an enforced negative contract—not permission to proxy to a replacement. Trace all callers, make the retired path fail closed without a network request or `ok=true` result, and add an executable regression that proves rejection. A compatibility stub that silently forwards to the new API can hide migration omissions and produce false success. Keep the replacement path's validation and evidence separate from the retired path's rejection.

### Acceptance markers: match explicit tokens, never prose substrings

When a gate decides "human acceptance done" or "chain verified" by scanning a document, **never test for keyword presence in prose** — discipline/evidence text almost always contains the words you're looking for and produces false positives. Real case: a release gate checked `"通过" in readme or "PASS" in text.upper()`; the evals README's own discipline line "不用单张 AI 图作为**通过**证据" matched 通过, so the gate reported `RELEASE_GATE=READY` on a release that was explicitly not accepted yet. The fix is a two-part contract:

1. **Writer side**: the aggregate verifier writes an explicit marker file (`config/.verify-chain-ok`) containing `ok <HEAD-SHA>`; consumers never re-invoke the aggregate (recursion guard) and never re-derive status from prose.
2. **Consumer side**: match a structured marker regex scoped to a marker line (e.g. `DL-REL-001:\s*(ACCEPTED|验收通过|DONE)`), and reject stale bindings — `VERIFY-CHAIN-STALE marker=<sha> head=<sha>` when the marker's SHA differs from HEAD.

Marker lifecycle pitfalls (all hit in one session, PR #41–#42): the marker must be added to `.gitignore` or its own untracked `??` entry permanently trips the gate's DIRTY-WORKTREE check; the writer script's `ROOT` may be `scripts/` not the module dir, so a `ROOT.parent / "design-lab/config"` path silently writes one level too deep — resolve repo root as `root.parent.parent` from `scripts/`; and never wrap the marker write in a bare `except Exception: pass`, which hides exactly these path bugs — write, then assert `marker.exists()` and print the resolved path.

### Scanner coverage

Security/rule scanners must cover all rule-bearing text and executable files, including Markdown/config plus `.py`, `.sh`, `.bash`, `.ps1`, `.psm1`, `.cmd`, and `.bat`. If scanner source contains its own detection literals, exclude only the scanner file itself or construct literals safely; never reduce the scan set to avoid a self-scan false positive.

### Text-vs-binary read-failure handling (fail-closed nuance)

When hardening a scanner so unreadable files fail closed instead of being
silently skipped, distinguish text from binary BEFORE deciding what a
violation is. First attempt in a real session flagged 405 binary assets
(PNG/WebP/JPG) as "unreadable" because the UTF-8 read fails by design on
binaries — a false-positive flood that breaks the gate. Correct pattern:

1. Skip binary suffixes explicitly (`BINARY_SUFFIXES` set: images, media,
   archives, fonts, executables, `.fig`/`.psd`/`.sketch` source files).
   Skipping binaries is NOT fail-open — text identity patterns cannot
   occur in them.
2. Then treat unreadable TEXT files as violations (fail-closed).

The same rule applies to `stat()` in size/asset gates: a tracked file that
cannot be stat'ed must record an error, never `continue` silently (a
file that escapes the size cap via stat failure is a real bypass).
Quarantine/isolated-dir stat errors must surface too, not `pass`.

### Governance-gate semantics: subset required, not full set

A verifier demanding "at least one of N hard gates" can be too weak, but
demanding ALL N can be too strong when cards use domain-specific gates
(typography cards use `language-and-script-valid`, motion cards use
`medium-production-check`). Correct contract, validated in a Codex review
round:

- Split gates into a **governance subset** (originality +
  source/license-record, e.g. `no-signature-copy` OR
  `source-and-license-record`) required as "at least one";
- **Domain gates** are per-benchmark and never universally required;
- Backfill missing governance gates on existing cards as honest
  `not-run` entries — never invent pass/fail state to make the gate green;
- Successful summary counts (`cards=N`, `accepted=M`) must be computed from
  the data, not hardcoded — a hardcoded count silently lies when data
  changes.

When a registry carries two spellings of the same field (legacy singular
`category` on 124 entries vs canonical plural `categories` on all 162,
with 73 conflicting), unify by deleting the legacy field with
indentation-preserving line edits; verify JSON parses and the diff is
purely deletive before commit. Never rewrite the whole file to fix one
field (see L-006 JSON-indentation lesson).

## Placeholder/E0 contract completion: the verifier defines the contract

When a governed repo has adapter/tool contract surfaces (manifest, policy,
evidence) left as 0-byte placeholders while the surrounding registry already
validates them, completing them is a gate-driven loop — the verifier IS the
contract, and you fix the ARTIFACT, never the verifier. Validated 2026-08-14
(DESIGN-LAB, PR #69, adapter-registry 6→9):

1. **Scan for 0-byte files to find true placeholders.** A rglob over the
   module's dirs for `stat().st_size == 0` surfaces every empty contract file.
   Distinguish legit empty files (`__init__.py` module markers, `.nojekyll`
   Pages flags) from real gaps (manifest.json / policy.md / evidence README
   that must carry content).
2. **Cross-check registry vs directory completeness.** Directories for
   comfyui/adobe/minimax-h3 existed under `creative-tools/` but
   `adapter-registry.json` only listed 6 of 9 adapters — the registry is the
   source of truth for what is REGISTERED, and it silently lagged the dirs.
   Verify every contract dir has a registry entry before declaring the surface
   complete.
3. **Write the contracts to the verifier's vocabulary, then let the gate
   audit them.** verify_comfyui_gate REQUIRES the policy to contain
   `loopback`, `127.0.0.1`, and `手动启动|manual` (its REQUIRED list) and
   forbids auto-install/download/bind-0.0.0.0 (FORBIDDEN list). The first
   policy draft missed 127.0.0.1 + manual launch → gate FAIL findings=2 →
   fix the POLICY to name the loopback bind and manual-launch requirement.
   The gate catching keyword gaps is the mechanism working, not a bug.
4. **E0 honesty: never claim availability without runtime evidence.** New
   adapters are status=declared, capabilities supported=false, evidence
   level E0 — the registry's status model explicitly forbids labelling
   anything 'available' without a task ID, artifact path/hash, and exit code.
5. **Existing tests are the first contract enforcement layer.** The benchmark
   briefs (12 files, previously 0-byte) were filled in once, and
   test_benchmark_registry + verify_benchmark_registry immediately rejected
   the first draft (missing `benchmark_id`/`seed`/`viewport` repeatability
   controls) — align every filled artifact to what the registry verifier
   checks, not to an invented schema.

## Risk must be detected, not self-reported

Treat declared task risk as a lower bound. Normalize mission paths and operations and compute:

```text
effective_risk = max(declared_risk, detected_risk)
```

Force high-risk review for repository policy/config paths, setup scripts, security/workflow scripts, manifests and dependency files, credentials/authentication/permissions, provider or dependency changes, migrations, deletes/moves, external writes, packaging/deployment, commit/push/PR/merge/release, GitHub ruleset changes, and live apply. Critical operations such as force-push, history rewrite, production write, credential export, and external project deletion must never be downgraded by a `low` label.

Test both positive and negative cases: a config/deployment mission declared low must route through the high-risk path; a pure adapter or documentation-only mission may remain low when no forced-high signal is present.

## Reversible deployment

For repo→live synchronization:

1. Keep dry-run side-effect free.
2. Define the exact managed file/tree inventory in one machine-readable ownership contract. Backup, staging, promotion, verification, and documentation must consume that same inventory; broad parent directories are not a substitute.
3. Stage only those exact managed items on the same filesystem. Do **not** copy an entire mixed-ownership live parent and later promote the whole parent: a bundled/user file or skill created after staging would be silently lost.
4. Replace each managed subtree or file independently. Exact subtree replacement may remove stale descendants inside that owned subtree, while unrelated siblings remain untouched. Apply the same rule to launcher directories such as `bin/`; manage exact wrapper paths instead of deleting official runtime entries.
5. A mixed-ownership config file is non-promotable by default. Key-level merging and a last-minute snapshot check do not create a portable atomic compare-and-replace against external application writers. Exclude the whole live config and any state encoded in it from automatic sync; construct the reviewed, credential-free baseline only in a newly created isolated verifier home. Real-home config changes require an explicitly user-directed official application workflow.
6. Run structural and post-apply validation against staging.
7. Create a timestamped backup before apply.
8. Record every move during promotion. Support both desired-present replacements and explicitly retired desired-absent paths in the same rollback ledger.
9. Fault-inject prepare failure, a later managed-item failure, and a later failure after a retired-item removal. Verify every earlier move is restored, partial staging is removed, rollback material is retained when cleanup fails, and concurrent non-managed siblings survive.
10. Prune only backups created by this synchronizer, never arbitrary user backups.

A backup copy without an automatic failure-path restore is not rollback proof. Direct `copytree(..., dirs_exist_ok=True)` or `write_text()` into live managed paths is not atomic deployment. A whole-parent replacement is unsafe whenever that parent has mixed ownership, even when staging initially copied all visible siblings.

Verify preservation without touching real credentials or a live profile: build an isolated synthetic home containing placeholder model/provider/base-URL/API-key/fallback/picker/quick-command values plus sentinel `auth.json`, session, and database files. Hash the sentinels before and after the real merge entry point, assert every unmanaged semantic value is equal, and assert only explicitly managed preferences changed. Report hashes/equality booleans, never placeholder or credential values. This proves non-ownership behavior without reading protected runtime state.

## Existing-path bootstrap safety

An existing zero-byte config or rule file is **not** equivalent to an absent file. Repeated `lstat`/`fstat`/link-count checks cannot make later in-place writing race-free: a hardlink or compatible writer can arrive after the last check. For strict installers, the durable architecture is **write complete private content first, then publish the public name atomically without replacement**. The public target must never be the write surface.

For a strict “never overwrite user state and never continue writing through an out-of-root alias” contract:

1. Reject linked/reparse ancestors and linked targets during classification, but do not treat a clean result as write authorization. Preserve every existing target, including a regular single-link zero-byte file.
2. Require the application home to pre-exist as a real directory, or create components only relative to a separately pinned trusted ancestor. Never perform checked-then-path-based `mkdir`; refusing a missing application home is the safest default.
3. Pin the destination directory through staging creation, writing, publication, identity checks, file finalization, and directory finalization. POSIX uses `O_DIRECTORY | O_NOFOLLOW` and dirfd-relative operations. Windows holds `CreateFileW` with `GENERIC_READ` and omits `FILE_SHARE_DELETE`; `FILE_READ_ATTRIBUTES` alone does not reliably pin rename.
4. Create a private or anonymous staging object, never the public target. Write through an explicit full-write loop and do not expose `AGENTS.md`/the final config name until all bytes are present. If a test can open the public name while `write_all()` is active, the architecture is still unsafe.
5. On Windows, create random staging with `GENERIC_WRITE | DELETE`, no write/delete sharing, and immediately set `FileDispositionInfo(DeleteFile=True)`. Delete-pending blocks new opens and hardlinks while bytes are being written. Only after the content and pre-publication checks pass should code clear the disposition and call `SetFileInformationByHandle(FileRenameInfo, ReplaceIfExists=False)`. Do not write any byte after clearing delete-pending. If publication fails, restore delete disposition and close the exact handle.
6. Treat `msvcrt.open_osfhandle()` as an ownership-transfer boundary. Before successful conversion the raw Win32 HANDLE remains the caller’s responsibility; conversion failure must close that exact delete-pending HANDLE with correctly declared `CloseHandle.argtypes/restype` and return non-zero. Never report the conversion failure as a harmless race or success.
7. For Windows same-directory handle rename, use `RootDirectory=NULL` with the full destination path. A relative `FileName` with `RootDirectory=NULL` resolves relative to process CWD, not the source file’s directory; blindly setting a directory RootDirectory for a same-directory user-mode rename can return `ERROR_INVALID_PARAMETER`. Allocate space for the terminating WCHAR while keeping `FileNameLength` equal to the UTF-16 byte count excluding the terminator.
8. On Linux/POSIX, require `O_TMPFILE` for an unnamed inode, write it completely, then publish with dirfd-relative `linkat(AT_EMPTY_PATH)` so an existing target wins without replacement. A random named staging file in a concurrently writable directory is **not** a safe fallback: its pathname can be renamed and replaced between link-count inspection and `os.link()`, publishing attacker-controlled bytes. Unless the source name is protected by a separately proven non-writable private directory and source identity is atomically bound to publication, lack of `O_TMPFILE` must produce a non-zero `ATOMIC_PUBLISH_UNSUPPORTED`-style result with zero public/private writes. Do not silently downgrade to check-then-rename, stat-then-unlink, or named fallback retention.
9. Recheck override/opt-out and pinned Home identity after staging is complete immediately before publication, then verify override, Home identity, and public-target identity after publication. Cross-name atomicity is generally unavailable: if a late override wins after POSIX publication and exact rollback is unavailable, retain the complete public object, return non-zero, and require inspection rather than delete a possibly replaced path.
10. Every cleanup/finalization uncertainty after staging creation is non-zero. Keep Windows cleanup handle-bound; POSIX must never treat `fstat(fd) → stat(name) → unlink(name)` as atomic. Distinguish cleaned private staging, retained private staging, published-but-unverified target, target replacement, Home replacement, file-close failure, and directory-close failure with truthful markers.
11. Add real negative controls for: unavailable `O_TMPFILE` (assert a non-zero marker and zero public/private entries); raw-HANDLE→fd conversion failure; compatible concurrent writer against staging; hardlink attempt against delete-pending staging; no public target during `write_all`; concurrent public target at atomic publication; true pre- and post-publication override; Home rename/junction replacement at final hooks; public-target replacement after publication; partial write; target close; directory close; and template-read failure. Assert filesystem bytes, entries, return codes, and markers—not only mock call counts. When an implementation rechecks a function such as `plan()` after a race hook, make the mock inject only the first state transition and delegate subsequent calls to the real function; a permanently canned READY result can hide the repair. Filesystem-specific race tests must probe required primitives at runtime and skip only when unavailable with a precise reason; never reinterpret an unavailable primitive as a passing publication path. A probe that opens Windows staging by path must use compatible share flags or inspect metadata; otherwise the test itself may manufacture `PermissionError` and leak the test handle.
12. Do not add an “explicit apply” flag that restores in-place writing. Explicit intent does not eliminate hardlink, writer, parent-identity, or cleanup races.

If product requirements demand automatic migration of an existing entry, design a separate claim/publication protocol that never writes the old inode and preserves competing content. Do not describe repeated checks, descriptor checks plus public-name writing, or close→path cleanup as race-free.

### Conflicting exact-tree reviews

An exact diff hash binds a verdict to bytes, but not to probe strength. If two independent reviews of the same hash conflict and either supplies a deterministic Critical reproduction, immediately downgrade the release to `REOPENED / NO-GO-PENDING-FIX`. Reproduce the stronger probe in the writer session, convert it into a formal RED test, and invalidate every prior GO until a new tree receives Critical `0` and Warning `0`. Do not dismiss a slower or earlier review as stale when branch/HEAD/status/diff hash are identical.

Every post-review edit—including a new fault-injection test or adjacent cleanup hardening—invalidates the reviewed hash. Re-run the canonical gate, compute a new diff hash, and re-dispatch review before commit/push. A reviewer blocked by a provider safety filter, timeout, or infrastructure failure produced **no verdict**; it neither clears nor technically rejects the candidate, so release remains review-blocked.

If successive fixes keep revealing new race windows in the same check→act→rollback design, stop adding checks. Revisit the architecture: shrink the write surface, require pre-existing trusted roots, remove unsafe automatic cleanup, or change the publication protocol. The safe recovery may be a non-zero state with a retained newly created object and explicit manual inspection; a tidy but racy rollback is worse.

See [`references/filesystem-entry-bootstrap-safety.md`](references/filesystem-entry-bootstrap-safety.md) for the reusable race matrix, [`references/exact-overlay-promotion.md`](references/exact-overlay-promotion.md) for mixed-ownership parent deployment controls, and [`references/mixed-ownership-config-boundary.md`](references/mixed-ownership-config-boundary.md) for the non-promotable config decision and regression recipe.

## Managed single-file mappings and provenance refresh

A portable overlay may own exact root-level files (for example, a behavioral baseline) without owning the whole application home. Declare every such item as an explicit `source -> target` mapping in the same machine-readable ownership contract that defines managed trees and launchers. Validate both paths narrowly (relative, no traversal, expected source domain, unique target), then drive **backup, staging, dry-run reporting, atomic promotion, rollback, and isolated verification** from that one mapping list. Never add a special-case copy in only one phase: a file that is documented but absent from promotion, or promoted but absent from backup/verifier inventory, is an incomplete ownership contract.

When a repository-controlled skill changes, update its frontmatter version and source provenance hash together, then run the repository-only provenance checker. Distinguish source provenance from live provenance: a manifest rebuild that lacks an explicitly authorized live root may intentionally mark every live hash as `pending-live-sync`. That is an honest unknown state, not proof of deployment or a reason to invent replacement live hashes. Review the scope of that bulk metadata change before release; if preserving prior live evidence is required, use a narrow reviewed source-hash update instead of an indiscriminate manifest rebuild. Never read a live profile solely to make a manifest look green.

## Root-workspace cleanup boundary

When a request includes project, Hermes root, Codex root, or non-project workspace cleanup, classify ownership before path. Inventory names/types/sizes and active process ownership first. Preserve active SQLite databases and WAL/SHM, sessions, logs, cron/Gateway, auth/config, locks, recovery backups, and active runtime directories. Only remove proven regenerable stale artifacts after the owning process is quiescent. A `git clean` candidate or empty directory does not prove safe deletion.

## Cloud update → local/live adoption gate

When `origin/main` has a governance update and the user asks whether it fits the local runtime, separate three states: repository parity, managed live parity, and live trust/allowlist. Do not equate a green remote CI run with an approved local hook.

1. Refresh refs and record branch/HEAD/worktree status. Fast-forward a clean local `main` only; never overwrite uncommitted work.
2. When using an official updater, capture its terminal process status. A progress marker such as `Code updated!`, a rebuilt UI, or a GUI reopening is not the updater's final exit proof. After completion, fetch again, assert the managed checkout is clean and `HEAD == upstream`, and record the installed version/SHA before claiming parity.
3. Run the full unittest suite and canonical quality gate on the adopted tree. On Windows, initialize project-local `.hermes/task-runtime/{tmp,cache,logs,artifacts}` before raw unittest when the test suite assumes those directories; keep this as a helper precondition, not a system-Temp workaround.
4. Use a short, project-local isolated worktree for remote-update review. A nested long path can create Windows copy/length failures that are evaluation noise; distinguish those from code failures and remove the worktree afterward.
5. Before repo→live apply, run the synchronizer dry-run and review the exact managed inventory. Require backup → staging → post-staging validation → per-item atomic replace → cleanup/rollback evidence. Verify provider/model preservation without printing credential values.
6. Treat `profile-live-only` entries as a separate trust domain. Preserve live-only skill content when the repo has no source; do not overwrite it merely to clear a manifest drift, and do not silently rewrite the manifest to match live content. Report repo-controlled and live-only drift separately.
7. Provenance hashes must use the project’s canonical UTF-8 text normalization (`CRLF`/`CR` to `LF`) so Windows line endings do not create false drift. After updater completion or live apply, rerun official provenance, config check, wrapper resolution, Doctor, staging/backup cleanup, and protected-state integrity checks. If a desktop process was restarted, require cold-start/session visibility evidence separately.
8. A deployed hook is not an active hook until `hermes hooks doctor` confirms allowlisting. If it reports `not allowlisted`, require the user’s explicit TTY/new-session approval (`hermes --accept-hooks`) and rerun doctor; never silently bypass trust or click permission UI on the user’s behalf.
9. Final reports must label repository tests, updater completion, managed live sync, live-only provenance, runtime cold start, and hook trust independently. The reusable evidence layout and failure interpretation are in `references/cloud-update-adoption.md`.

## Deterministic changed-path classifier & selective CI (fail-closed)

When building a risk-selective CI workflow driven by a deterministic
changed-path classifier (a GatePlan producer feeding per-job `if:` conditions),
keep every heavy gate fail-closed. Five traps seen on live runs:

1. **`full-qualification` collapses `required_gates`** to just `["ci-verdict"]`;
   heavy jobs whose `if` only checks `contains(required_gates, '<gate>')` will
   wrongly skip under full. Each heavy job `if` must ALSO fire on an explicit
   `full_qualification == 'true'` flag (and on `needs.gateplan.result != 'success'`).
2. **`git diff base...head` (3-dot) can resolve EMPTY** in a CI merge-ref
   checkout; never let an empty/uncertain diff become a light lane — force
   `full-qualification` (fail-closed), and use the 2-point diff.
3. **Root-level `**/*.md` does not match root files** in Python `fnmatch`; strip
   a leading `**/` and re-match so `AGENTS.md`/`README.md` classify as docs.
4. **`tests/**` must be its own ordinary-python path**, else every test-only PR
   becomes `unknown → full-qualification`.
5. **PowerShell vars do not survive between workflow steps**; pass values via a
   producing step's `id` + `$GITHUB_OUTPUT`, consume as `steps.<id>.outputs.*`.

Also: `.worklab/*.yaml` written through write_file can trip the YAML linter on
real traps — quote version floats (`"1.0"`), quote glob values containing `*` or
`:`, and `#`-prefix EVERY comment line (unprefixed continuation lines become a
bare scalar). Land these via a terminal heredoc and verify with
`yaml.safe_load`. Desktop `WM_CLOSE`/`backend_lifecycle` flaky: rerun the failed
job (`gh run rerun <run> --failed`) and confirm the rerun passes — do not
rewrite code or add force-kill fallbacks. A CI-self-change PR (edits
`.github/**`, `.worklab/**`, `scripts/ci/**`) legitimately runs ALL heavy jobs;
a test/docs PR showing heavy jobs `skipped` is the signal routing works.

### Branch-protected aggregate completeness

A job that appears in a workflow or finishes green is not necessarily enforced. Query the live branch protection/ruleset and identify the actual required context; when the only required context is an aggregate job, trace every required security, supply-chain, integration, runtime, and platform gate through the full chain:

```text
policy/profile gate declaration
→ changed-path/GatePlan selection
→ workflow job `if:`
→ aggregate `needs`
→ real `needs.<job>.result` payload
→ aggregate verifier required-set comparison
→ branch-protected context
```

Every link is mandatory. A security job omitted from `aggregate.needs` can fail while the sole protected aggregate remains green. Do not accept source-string presence as proof. Add three executable layers: (1) planner tests proving critical paths select the gate; (2) workflow-wiring tests proving the real job result reaches the aggregate; (3) aggregate negative controls proving failed, missing, skipped, and cancelled selected jobs all return non-zero while an unselected skipped job remains allowed. On GitHub, verify job timestamps/order and the exact-head run, then separately verify the squash/rebase merge SHA on `main`; any repair commit invalidates older PR-run evidence.

#### Immutable gate universe, full qualification, and event identity

Treat the canonical gate universe as an immutable lower bound, not as data a changed project profile may shrink. A parser that merely checks `gates` is a mapping permits `gates: {}`; if critical/full planning then does `affected.update(profile["gates"])`, a governance self-change can produce `risk=critical`, `required_gates=[]`, skip every real job, and let an aggregate that only rejects unknown *extra* gates pass. Enforce the boundary independently at three layers:

1. Profile validation requires the exact mandatory gate IDs, or at least a non-removable mandatory subset.
2. Planner emits an explicit qualification mode; `full`/`critical` requires the canonical set regardless of profile omissions.
3. Aggregate validates the complete GatePlan schema plus cross-field invariants and rejects missing canonical gates for full/critical plans. Repository, commit, tree, digest, and plan identity are mandatory, never optional.

Run the exact negative controls: mutate a loaded profile in memory to an empty gate map, classify the profile path itself, and feed the resulting self-consistent plan to the real aggregate; then feed a digest-valid but schema-incomplete plan with an empty required set. Both must return non-zero before job evaluation.

Required-check identity is normally context/app based, not event-qualified. An unscoped workflow with both `push` and `pull_request` can attach two same-name aggregate checks from the same GitHub Actions App to one PR head SHA. Their diffs may differ: the PR run sees the whole PR while a later feature-branch push sees only the newest push range and can select a lighter lane. Restrict protected-context `push` runs to the protected branch (for example `main`), keep manual/tag/dispatch checks on distinct non-required names, and use required-workflow/ruleset identity where available. App binding alone does not distinguish two runs from the same Actions App. Query check-runs for the PR head and group by `(name, app.id, event)`; a protected context must have no cross-event collision.

Derived-state freshness must be outside the mutable selection it attests. Run it unconditionally in or before the aggregate, and include the planner, profile loader, emitter, aggregate verifier, workflow, and schemas in the source digest. A freshness check selected by the profile can be disabled by the same profile edit; a digest that omits emitter/aggregate code does not attest gate behavior.

#### Aggregate plan-tamper hardening (A1–A8, validated 2026-08-15, WORK-LAB PR #113)

When the aggregate verifier is the sole protected check, a self-editing planner can select a light gate set and still go green. Concrete hardening set, all fail-closed (missing expected field = FAIL):

- **A1 plan identity**: `plan_id` must equal the fixed workflow value (`work-lab-gate`), never caller-supplied.
- **A2 repository**: `source_identity.repository` must equal the workflow-injected `expected_repository` (`github.repository`).
- **A3 tree identity**: `source_identity.tree.oid` must equal `expected_head_tree`, injected by the aggregate job from `git rev-parse HEAD^{tree}` after checkout — existence of a tree OID is not enough; it must match the checkout's actual tree.
- **A4 skipped coverage**: `{gate_id for skipped_gates}` must EXACTLY equal `PLAN_GATES - required` with non-empty reasons; a skipped list omitting a non-required gate is a silent omission → FAIL.
- **A5 risk/delivery/platform/time**: `risk` and `delivery_effect` enums, non-empty unique `platform_scope`, ISO-8601 `generated_at` all re-validated.
- **A6 critical re-derivation**: the aggregate NEVER trusts `plan.risk`. It re-derives critical from `changed_paths` against the project profile's `risk_zones.critical` (fnmatch + startswith, same matcher as the planner); critical + `required != PLAN_GATES` → FAIL even with green jobs. Missing profile → FAIL (cannot re-derive). Do not hardcode the critical prefixes in the aggregate; read the profile so planner and aggregate cannot drift.
- **A8 explicit skipped**: every non-selected gate job must be literally `"skipped"` in the payload; a job that ran (`success`) or is absent → FAIL.

Workflow side: the aggregate job injects `expected_repository` and `expected_head_tree` (bash `EXPECTED_HEAD_TREE="$(git rev-parse HEAD^{tree})"`) into the JSON payload alongside the existing expected digest/head SHA.

Test-side gotchas: an old test asserting a critical change with a single selected gate passes is now WRONG — rewrite it to require all gates; a payload built with `list(set(...)).index(id)` silently looks up the WRONG adapter (set iteration order is arbitrary) — always index by `{id: entry}` dict. Semantic-ownership changes (e.g. a client config field moving `OBSERVE` → `MANAGE` desired-state) make the module's OWN contract test fail on the old literal — update the assertion in the same batch as the config change, then re-run.

The WORK-LAB reproductions, cloud proof, and closure checklist are recorded in [`references/single-owner-branch-protection-and-merge.md`](references/single-owner-branch-protection-and-merge.md).

Full detail and reproduction: [`references/ci-classifier-selective-routing.md`](references/ci-classifier-selective-routing.md).

## Scheduled workflow first-run audit and GitHub schedule behavior

Scheduled/dispatch-only workflows (nightly crons, tag-triggered releases) can sit in the repository for weeks with zero runs, hiding first-run-must-fail defects. Before relying on one, audit it like a release gate:

1. **Marker-filtered test selectors are the classic zero-collection trap.** A job running `pytest tests/x.py -m "browser or workspace"` where no test registers those markers (and pyproject/pytest.ini registers none) collects ZERO tests → pytest exit code 5 → the first real schedule run fails. Check every `-m` selector against actual `@pytest.mark` usage; when the file is already the full intended surface, drop the dead selector and say why.
2. **Verify every script/asset the workflow invokes exists** (prepare/inject/verify/checksum scripts, package.json, tauri.conf.json, installer scripts) and dry-run the pure-Python steps locally with synthetic artifacts — checksum generators and identity injectors accept dummy inputs; assert output shape, hashes format, and exit code. A bundle-prepare script (`prepare_bundle.py` → stage Python runtime + `uv export` locked requirements + wheel download/build + install into the staged runtime) can run END-TO-END locally under `.hermes/task-runtime/`; then validate the staged runtime standalone (`<dest>/runtime/python/python.exe -c "import <core modules>"` with `env -u PYTHONPATH`) — that proves the publish-form runtime, not the dev venv. A PowerShell installer-verify script that cannot run without a real installer can still be syntax-checked without execution via `[System.Management.Automation.Language.Parser]::ParseFile(<path>,[ref]$null,[ref]$errs)` and asserting `$errs.Count -eq 0`. Leave only real-runner-dependent steps (NSIS build, install verification) to the first real execution.
3. **Simulate version-matrix jobs locally**: export the job's requirements (`uv export --frozen --only-group ci --format requirements-txt --output-file <file>`), then `uv run --python <target-version> --with-requirements <file> python -m compileall -q <packages>` plus the import/compat test. Pitfall: **`uv run --python <other-version>` REBUILDS `.venv`** (the current environment is replaced) — always `uv sync --frozen` afterwards to restore the standard environment before further local work.
4. **Before concluding a `schedule` tick was skipped, verify timezone semantics.** GitHub cron expressions are UTC, but the Actions web page displays times in the LOCAL timezone (browser/local +0800 for this user). Cross-check with the committer timestamp of a known commit (`git log -1 --format=%cI <sha>` — ISO 8601 with offset): if the Actions page shows the same wall-clock time as the commit's +0800 timestamp, the page is local and a cron like `03:17 * * * *` (UTC) fires at **local 11:17**, NOT local 03:17. Real case: "nightly skipped the 03:17 tick" was concluded from a local 03:17–05:00 observation window that never reached UTC 03:17 at all — the conclusion was retracted (project LOG-161). Relative times ("2 minutes ago") carry no timezone; always cross-check with a commit timestamp before asserting a tick was skipped or delayed.
5. **"Never ran" may be fully explained by the add-time vs tick timeline.** Before treating zero runs as anomalous, run `git log --format=%h %cI -- <workflow.yml>` and compare the file's first add time against the last and next cron ticks: added after the last tick and before the next one means zero runs is the EXPECTED state, with the next tick as the sole verification point (project LOG-162: nightly.yml added 8/13 UTC 14:48, next UTC 03:17 tick pending — nothing wrong). Only after the next tick passes with no run should scheduler-side behavior be considered.

## CI dependency layering and rule reconciliation

When a full test suite exercises optional/heavy adapters but a repository performance guard requires a minimal CI requirements file:1. Keep `requirements-ci.txt` minimal and preserve the guard; do not solve missing imports by adding heavy packages to the base list.
2. Create a dedicated adapter/test requirements file, such as `requirements-ci-adapters.txt`, containing only the optional packages exercised by the relevant test job.
3. Install that file only in the test matrix that executes those adapter paths. Keep lint, wheel-smoke, and runtime smoke on the minimal dependency surface.
4. Include all CI requirement files in the package-manager cache dependency glob. Validate both lists with a dry-run resolver before committing.
5. Preserve OS-level prerequisites in the workflow when tests call external binaries; Python packages do not replace tools such as `ffmpeg` or OCR engines.
6. If a test invokes a subprocess and asserts behavior without CI metadata, explicitly remove inherited CI variables in that subprocess environment. Do not change production identity semantics to make the test pass.
7. After pushing a repair, identify the run by both `headSha` and run ID. Older runs are historical evidence only; a `gh run watch` timeout does not establish failure, so poll `gh run view` until every job has a terminal conclusion.

When reconciling project rules with global workflow rules:

1. Inventory actual project rule files first; do not infer rules from filenames or stale handoffs.
2. Build a matrix separating exact conflict, semantic duplication, project-specific constraint, and obsolete guidance.
3. Keep project-specific boundaries and architecture facts; remove or compress generic global procedures into a precedence/reference statement.
4. Prefer the stricter global project-data boundary over project paths that permit broader locations. Resolve `.tmp/` versus `.hermes/task-runtime/` in favor of the task-runtime boundary.
5. Re-run rule/performance tests, syntax/config checks, architecture guards, and `git diff --check`; restore unrelated fixture-only line-ending noise before staging.

See [`references/ci-dependency-layering-and-rule-harmonization.md`](references/ci-dependency-layering-and-rule-harmonization.md) for the decision matrix and verification recipe.

## Settle-window and post-cleanup gates

Eventual or multi-pass systems must not be evaluated from an in-flight snapshot. Identify the authoritative completion marker, wait for queued passes to finish, require a quiet interval with stable config/artifact identity, and only then compare expected state. A plugin disappearing during pass one and returning during pass two is a startup-ordering observation; it is neither final data loss nor permission to hand-edit managed cache.

Cleanup invalidates earlier runtime evidence. After deleting a duplicate executable, migrating backups, dropping recovery refs, or changing PATH/config ownership, rerun resolution, Doctor/integrity checks and the complete cold-start or deployment acceptance path against the cleaned state. Historical pre-cleanup green output cannot close the final gate.

If time, tool-call limits, process interruption or user steering occurs before this final post-cleanup verification, report the highest proven state precisely—such as `REPAIR_APPLIED_FINAL_COLD_START_PENDING`—and list the missing gate. Never translate partial completion into “perfect,” “fully fixed,” “published,” or “zero errors.”

## Schema compatibility and artifact-name discipline

When hardening a workflow pack, preserve machine-readable schema identifiers unless the parser, fixtures, documentation, and every compatibility gate are updated in the same RED→GREEN batch. Do not rename an internal strategy merely to make its isolated-only meaning clearer; keep the stable value and express the boundary in comments/docs or in a separate explicit scope field. Before final review, compare every cleanup glob, emitted marker, staging prefix, backup name, and expected exit code in tests directly with the current production constant and call sites. A stale assertion that matches no artifact is a false green and must be treated as a Warning until corrected.

## Derived-state freshness and contract-vocabulary change discipline

Two closely related ways a healthy suite lets a whole PR pipeline go red; both
occur when a change lands without updating EVERYTHING that pins the old shape.

**Derived-state freshness (e.g. a generated CURRENT_STATE digest).** If a commit
changes tracked source without regenerating the derived state that hashes it,
every subsequent PR based on that commit fails CI with something like
`CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch` — even PRs that only touch
a workflow YAML. Diagnostic signature: jobs that do NOT check the digest
(observer, gate-plan) pass while the job that runs the freshness gate
(workflow-assistance) fails. Fix: regenerate the derived state and commit it in
the SAME commit as the code change; never let a "small" commit (e.g. a ledger
row, a workflow file) land without re-running the generator. When a PR CI shows
the mismatch, the fix is regenerate → commit → push, not editing the digest by
hand.

**Contract-vocabulary changes.** When a contract's vocabulary changes (for
example a projection that emitted source-mode strings `LIVE/STALE/SNAPSHOT` now
emits the UI vocabulary `fresh/delayed/stale` via a single mapping function),
the module's own tests passing is NOT enough. Cross-module quality gates pin the
old literal and will fail with an environment-limited=false style verdict.
Before pushing a vocabulary change:
- `grep -rn '<old-token>'` across `scripts/`, `tests/`, and gates in OTHER
  modules, not just the changed module.
- Distinguish assertions that legitimately keep the old vocabulary (an internal
  snapshot/reader contract) from assertions on the changed output surface — the
  former stay, the latter must be updated in the same batch.
- Update the gate in the same commit; a gate that reports
  `environment_limited_pending=false` because one PENDING check is a code-fail
  (not environment) will block merge.

Design pattern that prevents the drift class: keep the internal source-mode
vocabulary on the low-level snapshot, and map to the display vocabulary at
exactly one projection boundary (a dict + tiny function), so renderers and
gates never see an unmapped string. Verify with a regression test per mapped
value (LIVE→fresh, OFFLINE→offline, SNAPSHOT→stale, …).

See [`references/derived-state-and-contract-vocabulary.md`](references/derived-state-and-contract-vocabulary.md) for the concrete 2026-08-11 session signatures and the Windows sqlite test-lock note.

## Fail-closed scope-gating and optional-field contract audit

When reviewing a change that adds a retrieval-scope gate to a governed data
surface (e.g. "AI retrieval may only use approved, not-revoked, scope-matching
assets"), verify fail-closed correctness plus contract/round-trip compatibility
in this order:

1. **Optional field on a strict pydantic contract.** Adding `scope: str | None = None`
   to a model with `extra="forbid"` is backward compatible: existing serialized
   payloads lacking the key validate (default None), unknown fields are still
   rejected, and new writes carry `"scope": null`. Confirm the field has a
   default (so old rows round-trip) and is placed before required/`Literal`
   fields without breaking positional ordering.
2. **Double-guard filter semantics.** The canonical fail-closed predicate is
   `if scope is not None and unit.scope is not None and unit.scope != scope: continue`.
   Check all three cases:
   - *scoped unit never leaks to another scope* (skip when mismatch);
   - *scope-less/generic unit stays visible to any scope* (the `unit.scope is not None`
     guard keeps it);
   - *default None callers stay backward compatible* (the whole filter short-circuits).
   A single-guard version (e.g. `if unit.scope != scope`) is wrong: it drops generic
   units from scoped retrievals and throws `None != str` on default calls.
3. **Filter must sit on top of existing governance checks**, not replace them
   (approval status, human-review flag, row/payload identity). The scope gate narrows
   an already-approved set; it must not become the only gate.
4. **Caller compatibility.** Grep every caller that does NOT pass the new param —
   they must default to the old behavior (no scope → no filtering). Round-trip/state
   transitions that rebuild from `{**current.model_dump(), ...}` preserve the new
   field for free; confirm they do.
5. **Other serialization points.** Check every adapter round-trip, JSON schema
   generation, and migration. If a legacy-row adapter has an explicit `_ROW_FIELDS`
   whitelist that omits the new field, the round-trip is **lossy** for the new field.
   That is acceptable only when state constraints (e.g. scoped units are always
   `candidate`/`approved`, and the legacy-row writer raises for non-legacy statuses)
   make it unreachable — flag it as a WARNING with the recommendation to fail closed
   (explicitly raise) rather than silently drop the field, and to add an adapter
   assertion. JSON schema generated by pydantic needs no separate file sync; only a
   static `.schema.json` would. Candidates stored as a JSON column (`unit_json`)
   persist the new field with **no migration**.
6. **Coverage.** The regression test should assert the three retrieval scenarios —
   scoped request returns scoped+generic, other-scope request returns generic but
   NOT the scoped unit (the fail-closed assertion), and default-no-scope returns all.
   Empirically run the targeted suite plus the contract/round-trip suite.

Report the verdict per checkpoint (PASS/FAIL/WARNING + line + reason), and run the
targeted tests to confirm behavior rather than reading the filter alone.

## Independent exact-tree review reporting

For an independent read-only release review, bind the verdict to a reproducible candidate identity before inspecting behavior:

1. Resolve the user-specified workspace and candidate identity before using any ambient/current checkout. Confirm the requested path is the actual Git worktree with `git rev-parse --show-toplevel`, confirm branch/HEAD, and confirm the requested exact diff digest exists as the intended diff/tree identity (not merely that some local checkout is available). Delegated reviewers can start in a different repository or inherited cwd; require them to print and verify the absolute worktree root before reading files. If the path, HEAD, or digest cannot be bound, stop with `NO-GO`; discard the entire verdict rather than salvaging observations from the wrong checkout. Do not silently substitute the agent's current directory, another branch, or a clean tree; report the mismatch and the unreviewed scope explicitly.
2. Record branch, `HEAD`, worktree status, changed-file list, and an uncommitted-diff digest such as `git diff --binary | sha256sum`. Recompute the same digest after all tests and source reads; a changed digest invalidates the verdict.
3. Keep the review harness inside the permitted project boundary too: set `TMP`/`TEMP`/`TMPDIR` and test-specific cache/output roots to a project-local ignored runtime before running tests or probes. Do not let Python `tempfile`, subprocesses, fixtures, interpreter discovery, package managers, or shell wrappers default to the user profile. Preflight the actual executable paths (`python`, `pwsh`, helper tools) and reject the run if they resolve under a forbidden user directory; environment variables alone do not prove containment. Prefer a project-local shell command for digesting and probes over an orchestration helper that may materialize scripts in a user temp directory. If a probe already touched a forbidden user path, disclose that as a process-boundary violation, count at least one Warning, and do not claim a clean no-user-directory review. Treat ignored project-runtime artifacts created by a supposedly read-only gate as a side-effect boundary to report as well, even when tracked files and the reviewed diff are unchanged.
5. Report **Critical**, **Warning**, and **Suggestion** counts explicitly. Give `GO` only when the final candidate digest is identical to the initial digest and both Critical and Warning are zero. Otherwise report `NO-GO` without softening the gate merely because tests passed.
6. Reconcile claimed test counts against the live canonical run output, not stale project artifacts or handoff summaries. If the requester names an expected count that differs from the current run, report the actual count and classify the older count as stale evidence; never force the report to match it.
7. For compatibility changes that separate a runtime-unpinned dependency from a pinned candidate-audit policy, inspect every maintained README/docs/manifest projection for stale normative wording. Require paired regression coverage: the runtime verifier accepts only the documented official unpinned form while candidate audit rejects missing, `latest`, foreign, or otherwise unpinned provenance. A generic candidate-audit test is insufficient proof of this semantic split.
8. Review documentation and handoff consistency as a first-class gate when the change touches governance or quality-gate docs. Compare README, handoff, canonical gate documentation, runner/Justfile entry points, and the changed implementation; stale gate lists or direct-apply examples that bypass the documented dry-run/backup/rollback sequence are Warnings, not Suggestions. For version/workflow updates, scan all tracked README, handoff, release-status, error-summary, and current-state documents for superseded version strings and CLI flags. Historical records may retain old versions only when explicitly historical; a document labeled current/status/live that retains an older version is a Warning and must be resolved or clearly re-labeled before GO.
7. When the requester specifies a compact review schema such as `C/W/S`, use that exact schema in the final report. Bind the verdict to the requested candidate digest, state the no-go rule explicitly, and keep evidence and findings separate from remediation proposals.

### Compatibility-layer documentation and gate-evidence closure

For a compatibility change that makes a default runtime dependency intentionally unpinned while retaining pinned candidate-audit provenance, scan every normative projection—not only changed files—for the old pin requirement. This includes README policy text, default-enable gates, current/status audit docs, manifests, tests, and generated quality-gate summaries. A statement such as “all default MCPs must be pinned” contradicts an explicitly unpinned default runtime unless it clearly scopes itself to new candidates or the candidate-audit layer; classify the contradiction as a Warning and block GO.

Keep these evidence classes separate in the final matrix: implementation/static proof, targeted tests, canonical quality-gate PASS, and deliberately unexecuted gates. Never report the full quality gate as passed when it was skipped to preserve a strict no-write review. If test output shows project-external temporary paths or runtime artifacts under the user profile, disclose the boundary violation and do not claim a clean isolated review; prefer a disposable exact-tree copy with project-local runtime roots for the rerun.

4. Treat test assertions as executable evidence only after reconciling them with the implementation's current artifact names and paths. Compare staging/rollback prefixes, cleanup globs, emitted markers, and expected exit codes directly against production constants and call sites; a stale glob that matches nothing can create a false passing cleanup test. Flag such mismatches as coverage warnings and do not credit the intended negative control.
5. For stateful installers, build a marker matrix: every emitted outcome marker needs a defined exit code, documented operator meaning, and a behavioral/fault-injection test where it represents a failure, retained object, race, or uncertain finalization.
4. Treat capability skips as evidence boundaries, not passes. Report the exact skip reason, which platform/path it covers, and whether the platform-specific safety tests actually ran. Do not generalize a POSIX-only skip into Windows proof, or vice versa.
For an exact dirty-tree review, preflight the canonical quality runner's resolved interpreter and helper executables before execution. Environment variables alone are insufficient: if the runner selects a user-profile venv, user temp/cache path, or other forbidden external runtime, either redirect it to a project-local toolchain or count the boundary violation as a Warning and do not claim a clean isolated review. Also report ignored project-runtime artifacts created by the gate as review side effects, even when tracked status and the bound diff digest remain unchanged.

### Windows exact-review boundary probe

On Windows, inspect the actual executable paths printed by the canonical gate, not only `TMP`/`TEMP`/`PYTHONPYCACHEPREFIX`. A gate can correctly place its generated artifacts under `<repo>/.hermes/task-runtime/` while still resolving Python or PowerShell from `C:\Users\...`; that is a user-profile runtime boundary and must remain a Warning unless the runner is redirected to a project-owned toolchain. If the gate otherwise passes, preserve its quality result as evidence but do not issue GO: the final verdict requires both a stable exact digest and zero boundary warnings. Record the exact resolved path and the ignored artifact side effect without reading the user profile's configuration, credentials, or auth state.
6. After implementation/tests change governance or compatibility semantics, scan all maintained README, handoff, status, error-summary, and canonical-gate documents for superseded normative wording—not only the files in the diff. Historical mentions are acceptable only when explicitly labeled historical; a current/status section that still advertises removed flags or old pinning semantics is a Warning and blocks GO until reconciled.
7. When isolated tests need temporary paths on Windows, keep them under the project task-runtime boundary but choose a short child path. If a long temporary-root run hits path-length noise and a short project-local retry passes, retain the successful result and label the former as harness/path-length noise rather than an implementation regression.

For an exact dirty-tree review, a disposable copy made with `git archive` plus the working diff is not itself a Git repository. If the canonical quality runner includes a Git-dependent gate (for example, context-pack generation), do not weaken or skip that gate and do not run it in the owning checkout. Initialize Git metadata only inside the disposable copy, commit the reconstructed exact candidate there, then run the full runner and remove the copy afterward. Record the temporary-repository workaround as harness setup, not candidate provenance; recheck the owning checkout's branch, status, and caller-supplied diff digest before the verdict.

## Gateway ownership disambiguation

Treat “Gateway” as a named service identity, not a generic dependency. A project's FastAPI/API gateway (for example its own `127.0.0.1:8000` runtime) is project-owned; Hermes Gateway (`hermes gateway ...`, `gateway_state.json`, cron heartbeat) is cross-project global workflow infrastructure; a model/provider gateway such as LiteLLM is a separate provider boundary. Search the project's launchers and imports before deciding whether Hermes Gateway is required. A project-local API gateway, rate limiter, or model gateway does not justify installing Hermes Gateway. If the project's writer/cron is paused or durable workflow execution is not required, leave Hermes Gateway stopped; a stale global Gateway marker is an operational warning, not a project runtime blocker. Starting, stopping, installing, or repairing Hermes Gateway requires separate explicit global authorization and must use official CLI/readback rather than hand-editing state. Report project-runtime health and global workflow health as separate verdicts.

## Registry provenance and exact-review controls

When a registry/ledger tracks open-source candidates, preserve a strict boundary between raw inventory, provenance, and implementation truth. Missing source URL, revision, license snapshot, implementation path, test evidence, runtime evidence, or rollback handle is `unknown`, never guessed. `recorded` requires at least one type-valid, non-empty evidence field; `verified` is valid only when the complete evidence tuple exists, including test and runtime evidence. Malformed provenance must downgrade or reject, and adding metadata must not upgrade the governance status. **Fail closed on the whole evidence field:** do not filter invalid list members and then accept the remaining values as verified; any non-string, empty/whitespace-only, wrong-container, or otherwise malformed required value must make the entire verified claim `unknown` (or produce a structured rejection). Preserve legacy positional constructor ordering when extending dataclasses or public APIs; append new optional fields after the existing positional prefix and add a regression test. Identity gates must return structured failures—not exceptions—for empty/non-string/duplicate IDs, missing shared fields, status/source-status mismatch, malformed state values, and invalid execution states. Current JSON pair parity proves only data consistency, not installation or absorption; prove it against the actual current registry and ledger, and separately verify that no JSON payload bytes changed when the review is read-only.

For project data containment, make every launcher load its project environment boundary before creating a virtual environment, installing dependencies, or starting a runtime. Verify launcher-contained and raw-shell-contained states separately; a correct launcher does not make an unwrapped command safe. For Hermes global audits, save metadata-only before/after manifests: official status/list/doctor calls may update `state.db` or cron bookkeeping even when config, auth, skills, rules, and profiles are unchanged. Report observed content-scope stability separately from absolute zero-write claims, never hand-edit stale global state, and do not start/install Gateway merely to clear a stale marker without explicit authorization.

Bind independent review to the exact candidate tree/diff. Any post-review edit—including a test addition, fixture restoration, or documentation adjustment—invalidates the verdict and requires a new review. Reconcile actual test counts and restore test-generated fixture noise before review; stale summaries and status labels are not evidence. If a test mutates a tracked fixture as a side effect, record it as review noise and restore it before final status inspection; do not leave the checkout dirtier than the requested review scope.

## Operator-facing status discipline

When a gate fails or an independent review returns `NO-GO`, say so directly and stop release actions. Do not describe a candidate as "nearly released" or "fixed" while any required gate, exact-hash review, staging proof, or exact-SHA CI remains open. If a later edit invalidates prior evidence, state the old candidate as superseded, report the new digest, and continue from the new candidate rather than narrating progress from stale evidence. Keep status updates short: current proven state, blocking gate, and the next executable verification step.

## Exact-tree release and owned-only deployment closure

For a candidate that has passed local gates, freeze `git diff --binary | sha256sum` together with branch, HEAD, status, and `git diff --check`. Bind every independent read-only review to that exact digest and require Critical=0 and Warning=0. Any tracked edit afterward—including a provenance refresh, documentation change, or test assertion—invalidates the review and requires a new digest, affected gates, and review. Keep “repair complete”, “merged”, and “deployed to a live profile” as separate claims.

After merge, run the synchronizer dry-run and inspect every target. If a live managed-looking skill/rule differs from repository authority and may be user customization, preserve it by default. Do not broad-copy the managed inventory or use a temporary schema edit as a bypass. Deploy only the explicitly owned, non-drift roots/files; retain a backup; exclude mixed-ownership config/state, provider/model/auth, user MCPs/plugins, sessions, memories, and routing. Read back hashes for every deployed item and assert no staging residue remains. Record the skipped drift, backup path, deployment counts, and verification result in ignored project-local evidence.

A local quality gate passing does not replace an independent C/W review, and CI on an older SHA does not prove the current commit. Before reporting success, verify the PR head SHA, all required exact-SHA jobs, merge SHA, post-merge branch state, and the actual deployment readback.

## Skill/plugin/rule inventory and consolidation

When the user asks to merge or optimize existing skills, plugins, and rules, begin with a read-only profile-scoped inventory. Separate repository-owned overlay assets, official bundled assets, user-owned assets, and live drift; do not treat a deployed item or a relationship field as proof of ownership or activation. Count and classify enabled skills, plugin source/status, MCP servers, and static hooks without reading secret-bearing files or running hook/MCP connectivity tests.

Consolidate only within one ownership domain. Keep skills separate when their triggers, permissions, provenance, or rollback scope differ; merge only genuinely duplicate workflow contracts into a class-level umbrella, with session evidence under `references/`. Do not import official/bundled plugins into a repository overlay, enable user plugins, or overwrite a drifted skill/rule merely to restore byte parity. For deployment, dry-run the exact inventory, preserve drift by default, back up, deploy only non-drift owned roots/files, and read back hashes plus staging cleanup. Report protected drift and unperformed mutations explicitly.

For skill relationship metadata, distinguish installed/global references from repository-owned skills: unresolved local names may be valid global or bundled dependencies, while duplicate names and top-level metadata drift are actionable. A parser must isolate Hermes frontmatter before YAML validation; parsing the whole Markdown file as one YAML document can create a false malformed-frontmatter finding.

## Release-gate evidence-chain audit pattern

When auditing a release gate rather than implementing one, trace the complete enforcement topology: canonical workflow -> aggregate verifier -> release verifier -> machine-readable evidence -> human/runtime boundary. A verifier file that exists is not a wired gate; search active workflows and aggregate entrypoints for its invocation and record absent call sites as a release gap.

Freeze the requested exact commit/tree before reading behavior. If concurrent WIP appears afterward, capture its paths and diff but audit only `git show <HEAD>:<path>`/the frozen tree; do not credit or blame uncommitted changes. Re-check HEAD, status, and tree identity at the end.

Use negative controls that do not require real Host, production, or fabricated human acceptance: (1) an in-memory `accepted` evidence card with `E0` must fail; (2) a release record with CI `failure` or `read_back.verified=false` must fail; (3) a configured preference threshold with no script/test consumer must be reported as declarative-only. Schema presence is not enforcement: check runtime schema validation, cross-field constraints, exact 40-hex tree binding, artifact existence/hash, and whether the release gate actually consumes the result. Keep thresholds such as `preference_rate_min` separate from measured vote records; a config key without a producer and verifier is not a tested gate.

A diagnostic bypass such as `--skip-dirty` must never be able to emit a release-ready result; separate diagnostic output from release verdicts and propagate subprocess failures fail-closed. For Windows/project-boundary audits, execute read-only probes through the project-data wrapper and keep all generated runtime data under the project-local ignored boundary.

## Manifest path and object-type hardening

When a verifier consumes repository manifests, declared paths are untrusted data even when the manifest itself is tracked. `Path.exists()` is insufficient: it accepts directories where a file is required and permits `../` or symlink-resolved escapes.

Use this reusable fail-closed pattern:

1. Build a tight RED fixture for each boundary: directory masquerading as a file, missing file, `../` traversal, absolute path, and symlink escape where the platform supports it.
2. Resolve the candidate before checking it. Require `candidate.relative_to(allowed_root.resolve())` for every allowed root; reject anything outside the explicit root set.
3. Use `is_file()` and `is_dir()` according to the contract. A path that exists with the wrong object type is a failure, not a partial pass.
4. If the architecture intentionally stores assets in a second tree, encode that second tree as an explicit allowlist. Never replace containment with arbitrary `exists()`.
5. Keep schema/dependency failures fail-closed. Run both negative fixtures and the real positive fixture, then run the full suite, aggregate verifier, release gate, and exact-SHA CI.
6. Reconcile changed check counts and test baselines from live output; stale handoff numbers are not evidence. Any marker or derived evidence bound to an older HEAD must be regenerated before release-gate readback.

This hardening pattern applies to Domain Packs, Product Manifest roles/entrypoints/capability paths, Open Design visual-pack assets, release evidence, adapter policies, and any future manifest-controlled surface.

## Capability-level read-only SQLite access

When a read-only consumer (an Observer/derived projection) must open a
writer-owned SQLite store, do not give it the writer constructor: a normal open
runs schema migration (CREATE TABLE + `schema_migrations` INSERT) and sets the
WAL pragma — a write surface inside the "read-only" reader. Give the store a
`readonly: bool = False` constructor flag that:

1. opens via `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` — any write
   statement fails closed with `OperationalError` ("attempt to write a readonly
   database"), so no per-method write guards are needed;
2. skips directory creation, schema migration, and `PRAGMA journal_mode=WAL`
   (WAL is a writer pragma) — but still sets `PRAGMA foreign_keys=ON`;
3. keeps read paths (`seed_revision()`, projections) working unchanged.

Add a regression that opens readonly, asserts reads work, then calls a write
method and asserts the error mentions `readonly`. This is the Observer-side
half of "capability-level read-only" enforcement (WL3-605).

## Verification checklist

- [ ] Baseline branch/HEAD/worktree recorded
- [ ] Manifest/policy and deployment entry point read
- [ ] RED failed for the intended behavioral reason
- [ ] Required subprocess failures propagate non-zero
- [ ] Structural and runtime evidence are separate
- [ ] Scanner covers executable rule files without self-scan weakening
- [ ] Declared low cannot bypass forced-high risk
- [ ] Live branch protection/ruleset contexts are read back rather than inferred from workflow names
- [ ] Every selected security/supply-chain/runtime gate reaches the protected aggregate through planner selection, workflow `needs`, real result payload, and verifier required-set checks
- [ ] Selected failed/missing/skipped/cancelled jobs fail aggregate; unselected skipped jobs remain allowed
- [ ] Any repair commit invalidates older exact-head runs, and the merge SHA receives a separate post-merge `main` run
- [ ] Staging and atomic replacement exist
- [ ] Exact managed subtree/file inventory drives backup, staging, promotion, and verification
- [ ] Mixed-ownership parents (`skills/`, `bin/`, etc.) are not promoted as whole roots
- [ ] Existing-path installers preserve every existing entry and never write through the public target name
- [ ] Destination root pre-exists or is created only relative to a pinned trusted ancestor; no checked-then-path-based `mkdir`
- [ ] Destination parent identity is pinned through staging/write/publication/finalization; path checks alone are not treated as authorization
- [ ] Windows private staging is delete-pending while writing, blocks concurrent open/hardlink, and is published with no-replace handle rename only after content is complete
- [ ] POSIX publication requires `O_TMPFILE + linkat(AT_EMPTY_PATH)`; if the atomic primitive is unavailable, the installer makes zero public/private writes and returns a truthful non-zero unsupported marker—no named fallback in a concurrently writable directory
- [ ] Override, Home identity, and public-target identity are checked at the real pre/post-publication hooks
- [ ] Raw HANDLE→fd conversion, concurrent staging writer/hardlink, no-public-name-during-write, public replacement, partial write, target close, directory close, and cleanup/retention paths are fault-injected with truthful statuses
- [ ] Windows cleanup is exact-handle-bound; POSIX never treats stat→pathname-unlink as atomic cleanup
- [ ] Conflicting same-hash review verdicts remain NO-GO until the stronger deterministic probe is resolved on a new hash
- [ ] Mid-transaction and retired-removal rollback are fault-injected and verified
- [ ] Official updater claims include terminal status, post-fetch HEAD parity, and post-update runtime checks
- [ ] User-owned config/data survives
- [ ] No secrets or live-home state were read/copied into evidence
- [ ] Targeted tests, canonical quality gate, and diff checks pass
- [ ] Remaining P0/P1 items are reported honestly

## References

- See [`references/browser-smoke-playwright-traps.md`](references/browser-smoke-playwright-traps.md) for real-browser UI gate pitfalls (keyboard.type append, attribute selectors, state-dump diagnostics, CI gate triggering).
- See [`references/taskpack-p0-regressions.md`](references/taskpack-p0-regressions.md) for the reusable failure matrix and Windows-friendly command patterns from the first implementation.
- See [`references/codex-compatibility-and-branch-cleanup.md`](references/codex-compatibility-and-branch-cleanup.md) for the Codex help-preflight/user-layer fixture and stale remote-ref cleanup recipe.
- See [`references/codex-windows-guarded-review.md`](references/codex-windows-guarded-review.md) for running an independent Codex read-only review on Windows behind a project-data guard (`codex.cmd` vs WSL wrapper, launcher-script pattern, freeze-tree discipline, PARTIAL verdict interpretation).