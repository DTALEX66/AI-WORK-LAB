---
name: workspace-hygiene
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/workspace-hygiene/SKILL.md
---

---
name: workspace-hygiene
description: Audit and safely reclaim project-generated external artifacts, temporary test data, duplicate worktree-like copies, and stale build caches without touching protected data or active runtime assets.
version: 1.1.0
metadata:
  hermes:
    tags: [workspace, hygiene, cleanup, audit, boundary, containment]
---

# Workspace Hygiene

## Trigger

Use for requests to scan C/D drives or other approved locations for project-generated garbage, remove leaked test/build data, audit duplicate project copies, or reclaim space after completed work.

Use alongside `project-data-boundary` for prevention. Prevention means the launcher must create and inject project-local temp/cache/build/log paths **before** starting the child process; cleanup is the recovery path, not a substitute for containment. This skill governs **forensic discovery and safe cleanup** after an overflow has already happened.

### Project-local routing before cleanup

When a project has leaked to roots such as `D:\\a`, `D:\\d`, `D:\\dev`, or `D:\\tmp`, do not solve the problem by merely banning those names. First bind the child environment to the owning project’s ignored `.hermes/task-runtime/`:

- `TMP`, `TEMP`, `TMPDIR`, `XDG_CACHE_HOME`, pip/uv, npm/yarn, Playwright, Cargo/Rust, Ruff/mypy/pre-commit, and Python bytecode must each point below that project root;
- all wrappers that launch tests, agents, quality gates, or builds must use the same mapping, not maintain partial per-script defaults;
- a hard-coded legacy spill path is a bypass and may fail closed with a redirect message, but normal commands should be routed rather than rejected;
- verify the resolved mapping by reading the child environment back and asserting every path is contained by the canonical Git project before claiming the boundary is active.

After routing is fixed, audit and recover historical files by ownership. Never move caches from one project into another merely to empty a spill root; delete regenerable build/cache data after a quiescence check, and migrate only durable evidence into the owning project’s `.hermes/task-artifacts/` with a handoff manifest.

## Non-negotiable boundaries

1. Obtain current-request authorization for the exact drive/path scope and requested action. A read authorization does not authorize deletion.
2. Bind every inventory or cleanup script to an explicit canonical root obtained from the caller or `git rev-parse --show-toplevel`; never infer scope with `Path(__file__).parents[N]`. Assert the expected absolute root **before enumeration as well as before deletion** so an indexing error cannot turn a project audit into a parent-directory scan. Discard any data collected outside the authorized root and report the scope error.
3. Treat user-designated protected volumes as out of bounds unless the request names the exact path and operation. Never broaden a cleanup to another drive.
4. Do not read secrets, credential stores, private config, or authentication databases while assigning ownership.
5. Never delete canonical project roots, registered Git worktrees, active project-local runtime data, source archives, or items with Git metadata unless separately proven redundant and explicitly approved.
6. An active lock or ACL/access-denied result means **preserve and report**. Do not force-kill a process, change ACLs, or bypass the lock without explicit direction.
7. Windows test-temp trees may contain nested Git object files marked read-only. Only after proving the exact directory is project-local, ignored, quiescent, older than the retention window, and fully regenerable may a targeted `shutil.rmtree(..., onerror=...)` handler clear `stat.S_IWRITE` on the failing entry and retry. Do not change ACLs, apply this to a broader parent, or report success without confirming the exact root is absent afterward.

## Procedure

### 0. Git linked-worktree cleanup and durable evidence handoff

When the approved cleanup scope contains multiple directories for one repository, classify them as linked worktrees before treating them as duplicate projects. Capture `git worktree list --porcelain`, branch/HEAD, remote tracking, dirty/staged/untracked status, open PRs, and scheduler/cron workdirs. Never delete a registered worktree, canonical checkout, dirty WIP, open-PR checkout, active writer checkout, or a checkout referenced by a paused job until its ownership is reconciled.

For a clean, merged worktree that is approved for removal:

1. Inventory `.hermes/` separately from tracked source. Durable handoffs, unique task inputs, release readbacks, identity/checksum reports, and sleep ledgers are evidence; `.venv`, `build`, `target`, `node_modules`, bytecode, and caches are regenerable.
2. Migrate only an explicit allowlist of durable files into the owning canonical project’s ignored `.hermes/task-artifacts/<recovery-id>/`; do not merge whole worktrees or copy caches into another project.
3. Write a migration manifest containing source, destination, byte count, and SHA-256; re-hash destination before deletion. Preserve duplicate inputs only once and record their original hashes.
4. Check running processes and the scheduler before removal. A paused cron job is still a dependency signal: if its workdir would disappear, either retire/repoint that obsolete job under its own governance or preserve the directory and report the blocker. Never leave an enabled writer pointed at a deleted checkout.
5. Remove one worktree at a time with normal `git worktree remove`; do not force-remove a dirty worktree. If Git leaves a residual empty/temp tree, delete only the exact allowlisted path and re-scan. Broken Windows symlinks/junctions require a non-following literal-path cleanup; stop on unexpected content.
6. Keep branch refs unless branch deletion is separately authorized. Post-check `git worktree list --porcelain`, all remaining statuses, migration hashes, cron state, and exact directory absence.

### Workspace governance and source-tree hygiene

For a canonical workflow workspace such as WORK-LAB, separate the root control plane from its delivery modules before calling anything redundant: root task packs/governance/evidence contracts and the workflow module's portable global-workflow source are owned project content, while Hermes Home configuration, auth, sessions, cron, provider state, skills/plugins, backups, and host caches remain global platform state. Do not delete a project-named global directory by name alone; require provenance and a quiescence check. An empty, exact project-spill directory may be deleted only after confirming zero files/links and preserving its parent/global state. Protected recovery backups are retained unless independent redundancy evidence and explicit approval exist.

### Placeholder-file hygiene: annotate deferred, delete docstring-only shells

Tracked source can accumulate placeholder modules that are easy to misread as working implementations. Sweep them once per project (2026-08-12 Cognitive-Loop-OS #129):

```bash
git ls-files '*.py' | grep -v __pycache__ | grep -v "__init__" \
  | while read f; do s=$(wc -c < "$f"); [ "$s" -lt 50 ] && echo "TINY($s): $f"; done
```

Classify each hit, never delete by size alone:

- **0-byte / near-empty module with NO references** that is a reserved future surface (e.g. `app/agent/tool_router.py`, `app/core/attention.py` — deferred Agent Runtime / attention-scorer blueprints) → **annotate, don't delete**: a module docstring stating the DEFERRED intent and what IS live (so it is never misread as an empty working implementation). Deleting removes the reservation; leaving it bare invites a future agent to claim it works.
- **Docstring-only shell whose implementation lives in the package `__init__.py`** (e.g. `knowledge_base/taskpack/builder.py` containing only `"""TaskPack builder core."""` while `build_taskpack` is defined in `taskpack/__init__.py`) → **delete** — it is a misleading pointer with zero references and zero content. Verify zero imports first (`grep -rn "taskpack.builder\|from .* import.*builder"` across the repo) and run the package's tests + an imported-modules gate after.
- **Tiny design-index READMEs** (55-64 bytes like `# A-12: Teaching/Output System\n\n> Ref: CC Skill/Plugin`) are legitimate directory navigation, not placeholders — keep them.

Two further gotchas from the same sweep: (1) the bash loop above word-splits on non-ASCII filenames (Chinese/emoji paths) — use a Python one-liner (`os.path.getsize`) instead when the repo has such files; (2) check for OTHER TINY files in the same class (the sweep found both a reserved-module and a dead-shell pair) before declaring the class clean.

### Byte-exact emptiness audit: `st_size == 0`, never `st_size // 1024` (near data loss 2026-08-14)

Auditing for "empty/placeholder" files by **rounded size in KB** is a data-loss trap: `p.stat().st_size // 1024` returns 0 for ANY file under 1 KB, so a real 209–966 byte export (Open Design `artifact.json`, `critique.json`, `project.json`, `implementation-handoff.md`) displays as "0KB" and gets misclassified as a 0-byte placeholder. Acting on that misclassification — writing placeholder content over the file — **overwrites genuine data**.

Rules:

1. **Emptiness is `st_size == 0`, period.** When scanning for placeholders, compare exact byte counts (`if p.stat().st_size == 0`), or report raw bytes (`f"{size}B"`), never `size // 1024` or "0KB" derived from it. A file under 1 KB is NOT empty.
2. **Before writing over any file an audit flagged as a placeholder, verify against git.** If the file is tracked, `git show HEAD~1:<path>` reveals prior content; a diff showing deletions (e.g. "4 files changed, 72 insertions(+), 58 deletions(-)" when you expected pure additions from empty files) is the smoking gun that real content existed. Never `write_file` a replacement over a tracked file without checking what is already there.
3. **Recovery is immediate and lossless when the bad commit never left the machine:** `git checkout HEAD~1 -- <paths>` restores each overwritten file; then delete the local feature branch carrying the bad commit (`git checkout main && git branch -D <branch>`). The commit is gone with the branch — zero data lost, origin untouched. If the bad commit was already pushed, fix with a corrective revert commit, not history surgery.
4. **Sanity-check your own commit stats after an "add content" commit.** A commit that should be pure insertions (0-byte → filled) but reports hundreds of deletions means the files were NOT empty before. Stop and inspect `git show --stat HEAD` before pushing.

When auditing `.gitignore`, inspect ignored-but-present files before cleanup. Broad patterns such as `*token*`, `*oauth*`, `*cookie*`, or `*credentials*` can hide legitimate token-monitor source, design-token assets, component tokens, and governance docs. Replace them with exact secret-bearing filenames/extensions, keep `.hermes/` fully ignored, then re-run status, blob/tree comparison, security scans, and tests before deleting anything.

### Textual placeholder markers: scan for "建设中/TODO/待补" in project-owned files (validated PR #76)

Byte-size tiers (0-byte, <100-byte) miss a third placeholder class: **content that is a stub by its own words**. A tracked README can be 21 bytes of real text `# core — 建设中` — non-empty, but explicitly declaring itself unfinished. Add a text-marker sweep tier next to the size tiers:

```python
patterns = re.compile(r'建设中|待补充|待补全|TODO|FIXME|TBD|待完善|未完成', re.IGNORECASE)
# scan project-owned files only — EXCLUDE vendored trees (knowledge/, intelligence/,
# node_modules) where 'todo'/'placeholder' are legitimate upstream instruction words,
# and exclude .hermes/task-runtime history dumps.
```

Rules:
1. **Whitelist before classifying.** The sweep hits legitimate text everywhere: vendored skill files teaching "make a todo list", briefs stating "禁用程序占位", policy docs saying "未完成能力…回滚", release-gate READMEs describing their own pending status, registry evidence notes (E0 占位). Each hit must be judged by file ownership + intent — a hit inside `knowledge/`/`intelligence/` is upstream content, not your gap.
2. **The real signal is project-owned + self-declaring-unfinished**: a README that literally says 建设中/待完善 in a directory that otherwise has no implementation (e.g. `core/README.md` = `# core — 建设中`, the ONLY file in `design-lab/core/`, from the initial migration commit). Complete it or remove the marker — a stub that admits it is a stub invites future agents to treat the directory as not-yet-built.
3. **Same pre-write guard as byte audit**: before `write_file` over anything the marker sweep flags, check `git show HEAD~1:<path>` — a file that only ever had the stub marker in history is safe to fill; one with prior real content needs a diff review, not blind overwrite.

### Never `git add -A` on a repo co-located with large binary trees (validated 2026-08-13)

A configuration repo that lives next to toolchain directories (e.g. `OS External Configuration/` with a 3.4 GB `toolchains/vs-build-tools/`, scoop apps) can be catastrophically over-staged: one `git add -A` put **14,812 toolchain files into a local commit**. The `.gitignore` covered `scoop/`, `rust/`, `downloads/`, `playwright/` but **not** `vs-build-tools/` — the one directory that mattered. User reaction was immediate and strong; treat this as a hard discipline.

Rules:
1. **Stage explicit paths only** (`git add EXTERNAL_DEPENDENCIES.md README.md scripts/...`). Never `-A`/`.` on a repo whose working tree contains gigabytes of untracked binaries.
2. Before any bulk staging, confirm `.gitignore` covers **every** binary root: `git status --short | grep -c toolchains/` should be 0 untracked, and `git add --dry-run` must show only intended files.
3. **Recovery** when the over-staged commit exists locally but was NOT pushed: `git reset --mixed HEAD~1` unstages everything while keeping the files on disk; re-add only the intended config files; verify `git show --name-only HEAD` lists ONLY intended files and `git ls-files | grep -c toolchains/` == 0 before pushing.
4. If the bad commit already reached the remote, `git ls-files`/`git show --name-only` counts on the remote tell you the damage — fixing requires the filter-repo history-rewrite path (see section above), never papering over with a follow-up commit.
5. Immediately add the missing ignore entries (`toolchains/vs-build-tools/` and every other binary root), commit the `.gitignore` fix separately, and push both.

Treat test/build side effects as workspace hygiene defects. If tests rewrite tracked fixtures or generated platform configs, fix the launcher or test lifecycle to snapshot and restore the exact tracked fixture at the outer test-runner boundary; do not repeatedly hand-restore after each run and do not accept a green test with a dirty source tree. Re-run the official launcher and assert the generated path is clean.

### Canonical project consolidation (not cache-only cleanup)

When the user requires all project code and project-owned runtime data to live under one canonical root, a cache-only cleanup is incomplete. Treat registered linked worktrees as ownership-bearing checkouts: snapshot each dirty/staged/untracked WIP inside the canonical project, compare branch/HEAD/PR/CI ancestry, migrate durable evidence with per-file hashes, and reconcile scheduler workdirs before removal. Merge only audited commits; reapply user WIP with explicit conflict handling rather than letting a branch or stash overwrite it. Update every writer's `project_root`, `writer_worktree`, prompt, and runtime/artifact mapping to the canonical root, keep Hermes global auth/config/session/cron/backups outside the project, then remove old worktrees one at a time and verify both Git registration and physical path absence. A single green test slice does not prove consolidation: post-check the whole external root, remaining worktrees, scheduler references, project-local state, and unresolved review gates. If a deep-path copy fails, stop, preserve the source, and migrate only a durable allowlist; do not report completion from a partial copy.

### 1. Read-only inventory

#### Cross-root project/workflow reconciliation

When a request names multiple similarly named project directories plus a tool home (for example `D:\\d`, several Git worktrees, and `%LOCALAPPDATA%\\hermes`), treat it as one boundary audit with separate ownership domains, not as a wildcard deletion request:

1. Enumerate only the exact named roots and capture top-level entries, file counts, bytes, newest mtime, symlink/reparse status, Git worktree registration, branch/HEAD/status, and scheduler/cron workdirs.
2. Classify each checkout before calling it redundant: canonical, registered linked worktree, clean-and-merged, dirty WIP, active writer, paused-job dependency, or unverified copy. A clean linked worktree is not automatically disposable if a paused job still points at it; preserve the root or reconcile/retire that job under its own governance first.
3. For Hermes or another workflow home, separate global runtime/infrastructure (`config`, credentials, session/state databases, cron metadata, skills, profiles, backups, gateway logs) from project-owned spill (`<project>/.hermes/task-runtime`, exact project-named artifact roots). Filenames containing the project name are not enough to establish ownership. Preserve global state and protected backups unless separately proven redundant and explicitly authorized.
4. For external spill roots such as `D:\\d`, inspect only the named project subtree. If a generated cache contains mixed provenance (for example paths from multiple project roots or user-profile roots), classify it as `unverified` and retain it unless the current request explicitly covers that exact spill root and the artifact is fully regenerable.
5. Never report “cleaned the project” after deleting only one cache class. Re-scan the named roots for remaining `.venv`, `build`, `egg-info`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, task-runtime, runtime, attachment, artifact, and evidence directories, then explain each retained class.

- Inspect the explicitly approved roots first; do not recursively sweep whole drives.
- List candidate path, type, byte size, file count, modified time, and top-level contents.
- Size routines must count **both** ordinary files directly under the candidate root and files in descendant directories. Before treating a file as empty or deletable, read its actual byte size; a directory-only recursive accumulator can silently report top-level logs as zero bytes.
- Attribute candidates using concrete evidence: project-specific names, task/test naming, adjacent build outputs, timestamps, repository/worktree registration, or verified provenance.
- Classify every item as: `project-spill`, `canonical/project-local`, `unverified`, `system/application`, or `active/locked`.
- Add a separate ownership class for workflow infrastructure: Hermes, CC Switch, Codex, Workflow-assistance, and GitHub orchestration data (`session`, `delegation`, `Kanban`, `cron`, `handoff`, review transcript, cache). These are not project-spill and must never be migrated to or deleted from a project root. A filename such as `cognitive-*` or `review-*` is not sufficient evidence; `HERMES_HANDOFF.md`, workflow markers, a different Git workdir, or mixed provenance means preserve as `workflow-owned`/`unverified`.
- Before any delete, require at least two independent ownership signals (content/provenance plus Git workdir, generating command, or process chain). If the signals conflict, stop and retain the item.

### Staging snapshot versus durable archive classification

When the user names both a timestamped staging checkout and an archive root, never treat them as one cleanup candidate. Classify them separately before deletion:

- A staging checkout is removable only when it is a clean, unregistered Git worktree; its tracked file set has no files absent from the canonical checkout; every differing blob is either already absorbed or explicitly preserved elsewhere; no scheduler/process/PR references it; and the canonical project has a verified remote/readback state.
- A durable archive is preservational by default when it contains source checkouts, physical checkouts, manifests, hashes, final migration state, rollback handles, or recovery notes. A large size, old timestamp, or duplicate-looking source tree is not evidence of redundancy. Delete archive content only by an explicit per-artifact retention decision with independently verified equivalent recovery evidence.
- Before declaring an archive redundant, grep the canonical repo's **tracked** governance for the archive path (`migration-status.json`, handoff docs, recovery instructions). An explicit "do not delete" instruction or a referenced recovery path makes retention mandatory regardless of size/age; the archive may also hold the only full `.git` history of absorbed repos.

Use a file-set/blob comparison, not only directory names or HEAD strings, to distinguish an old staging snapshot from unabsorbed work. Before deleting a clean staging checkout, capture its HEAD/status and compare its tracked paths and blob hashes with canonical HEAD. After deletion, re-scan exact absence, verify archive evidence remains, and confirm canonical `HEAD == origin/<branch>` and a clean tree.

On Windows, a clean staging checkout may contain read-only Git object files. If deletion is explicitly authorized and the exact root has passed the redundancy/quiescence checks, a narrowly scoped `shutil.rmtree(..., onerror=...)` may clear only the read-only attribute (`os.chmod(..., stat.S_IWRITE | stat.S_IREAD)`) and retry. Do not change ACLs, use force-delete, remove a dirty/registered worktree, or broaden the retry outside the exact approved root. If the retry still fails, preserve and report the path.

### 2. Prove cleanup eligibility

For every candidate intended for deletion:

- Verify it is inside an exact allowlist root and is not a symlink/reparse point.
- Check Git metadata and canonical repository `git worktree list`; a name match alone is insufficient.
- Preserve non-Git test/runtime folders only when evidence ties them to a completed, reproducible project task.
- Preserve source archives, Git-containing audit folders, and unique evidence until their redundancy is independently established.
- Check active-use signals. If the platform reports a lock, leave the item untouched and record the blocking path.

### 2a. When reclaiming a reusable runtime by externalizing it

Use this only when the user has approved both the project source path and the external destination.

1. Check that no compiler, test runner, browser, or package-manager process is executing below the old path.
2. Copy to an initially empty destination; compare regular-file count and total bytes, and reject symlink/reparse-point sources unless their handling is explicit.
3. Update the canonical activation scripts and persistent environment variable if one exists; do not rely on a one-off shell export.
4. Run a real functional smoke against the destination (for example, launch the browser runtime or invoke the compiler), then remove the old project copy.
5. Repeat the same functional smoke after removal. If the destination is inside a configuration repository, ensure the binary directory is ignored so it cannot be staged accidentally.

### 2b. Project-contained transient caches and interrupted Git transfer files

A project-local artifact directory can contain both recovery evidence and safe-to-delete transient files. Do not delete the directory as a unit.

On Windows Git-Bash, use POSIX null redirection (`>/dev/null 2>&1`), not `>NUL` or `2>NUL`: MSYS can create a real repository file named `NUL`. If a diagnostic creates `NUL`, confirm it is the just-created untracked file, remove only that exact path, and re-run `git status --short`.

After tests or quality gates, perform a second targeted cache scan. Remove only proven-regenerable caches (`.pytest_cache`, `__pycache__`, and equivalent allowlisted directories); preserve task artifacts, runtime state, logs, session stores, recovery backups, and unique audit evidence unless separate retention evidence proves them redundant.

After a requested merge/upload/cleanup cycle, re-scan only the canonical project root: remove explicitly regenerable caches such as `.pytest_cache` and `__pycache__` after the final verification pass, while retaining `.hermes/task-artifacts`, task runtime/state, logs, session evidence, plans, and unique recovery backups unless separate retention evidence proves them redundant. Never use broad `git clean -fdx` or delete `.hermes/` as a unit.

- Treat `tmp_pack_*` as deletion candidates only when each file is inside an isolated, Git-ignored project artifact root; verify it is a regular file (not a symlink or hardlink), confirm the associated Git operation is no longer active, and re-scan the exact pattern after deletion.
- Treat `__pycache__` and `.pytest_cache` as regenerable only after the final test/quality-gate pass; remove them as the final cleanup step, because tests can recreate them.
- Do not infer that a current application log is stale merely from size. Preserve logs that are actively changing, and preserve session stores, installers needed by an approved recovery task, and uniquely recoverable backup archives until a separate retention decision proves them redundant.
- Keep generated cleanup evidence under the owning project’s ignored runtime/artifact root, not in the user profile or global Temp directory.

### 2c. Reclaiming stale smoke-test databases from `.hermes/task-runtime/`

When running recurring audit/smoke cycles (e.g. sleep-mode's `live-state-audit`), `.hermes/task-runtime/` accumulates regenerable smoke-test databases that can be safely cleaned during audit cycles. These are **not** user data or persistent evidence — they are test artifacts from previous bounded runs.

**Safe-to-delete categories** (all under `.hermes/task-runtime/`):

| Path | Justification |
|---|---|
| `api-smoke/` — entire directory | Smoke-test SQLite DB + lock files + logs from a prior bounded test run |
| `browser-smoke-final/` — entire directory | Same pattern: test SQLite + lock files |
| `desktop-dev/backups/` — entire directory | Pre-migration backups; superseded by each subsequent smoke run |
| `desktop-dev/output/`, `reports/`, `intake_uploads/` | Regenerable test artifacts — empty output after a clean run |
| `desktop-dev/*.lockdb`, `*.runtime.lock`, `.cognitive-volume-id` | Stale process-lock files from terminated test processes |
| `tmp/cognitive-core-smoke-*.log` | Prior-cycle smoke session logs |
| `tmp/cognitive-pytest-*/` | Prior-cycle pytest temporary directories |

**Preserve unconditionally:**
- `desktop-dev/cognitive_os.sqlite` (+ wal/shm) — active project-local test database
- `desktop-dev` directory itself — structure may be referenced in setup scripts
- `cache/`, `pip-cache/`, `pycache/` — dependency caches
- `state.json`, `activity.jsonl`, `activity.log` — control-plane files
- `lifecycle-e2e/`, `playwright-*` dirs modified within the last 60 minutes

**Procedure:**
1. Confirm target path starts with `.hermes/task-runtime/`.
2. Verify the directory is not currently in use (check file timestamps; skip items modified < 60m ago).
3. Remove only the allowlisted subdirectory/file, not the parent.
4. Record paths deleted, total reclaimed size, and "regenerable from next test run" as evidence.
5. Do not use `rm -rf .hermes/task-runtime/` — target specific subpaths only.

This pattern turns an otherwise-passive audit cycle into a provable small fix with measurable space reclaimed.

### 2d. Duplicate project build targets and active desktop runtimes

A project can accumulate multiple legitimate but regenerable build roots when direct Cargo/Tauri commands and the project data-boundary wrapper use different target directories. Inventory these separately instead of treating the whole workspace as one cache:

- `desktop/src-tauri/target/debug/` and `release/` are regenerable Cargo/Tauri outputs.
- `.hermes/task-runtime/cache/cargo-target/` and `tauri-target/` are also regenerable wrapper-scoped build outputs.
- `.hermes/task-runtime/cache/playwright-browsers/`, project toolchains, portable packages, WebView profiles, evidence, and active runtime roots are not disposable merely because they are large.

Before reclaiming build targets:

1. Freeze the project writer/scheduler or otherwise prove no compiler, test runner, or Tauri build is using the exact target paths; do not kill unrelated Chrome/WebView processes merely to make the scan quiet.
2. Use an exact allowlist of target directories, verify each is a real non-symlink directory under the project root, and record pre-delete bytes per directory.
3. Delete only the approved regenerable targets, not the parent `.hermes/task-runtime/` or the complete `.hermes/` tree.
4. Re-scan sizes, verify runtime/evidence/ledger retention, and confirm `git status`/`git diff --check` were not altered by the cleanup.
5. Expect the next Tauri/Rust run to rebuild these directories. If the writer is resumed afterward and cadence stability matters, use a fixed-wall-clock cron expression rather than a relative interval so pause/resume does not silently move the next tick.

A branch merge is a separate operation: do not infer that a large dirty worktree should absorb every local feature branch. Perform a read-only three-way merge preflight first; if overlapping architecture, UI, or test files conflict, preserve the dirty WIP and report the exact conflict set instead of blindly merging.

### 2e. User-requested attachment deletion

When the user says an attachment was sent by mistake and asks to remove it, treat that as explicit deletion authorization for the named attachment paths only:

1. Resolve the exact attachment paths from the current project context; do not infer neighboring files or delete the whole `desktop-attachments` directory.
2. Delete each named regular file independently, never with a broad wildcard.
3. Immediately verify every requested path is absent and report any `NOT_FOUND` item separately.
4. Preserve other attachments, extracted copies, task artifacts, and runtime state unless they are separately named and authorized.

### 2f. External toolchain root rename/migration (directory moved, refs go stale)

When the user renames/moves the shared external config root (e.g. `D:\All projects\OS configuration` → `D:\All projects\OS External Configuration`), a chain of stale references survives the rename — each one breaks a different tool. Run the whole chain in one pass, not just the directory move:

1. **User-level env vars** (`SCOOP`, `TESSDATA_PREFIX`, `CARGO_HOME`, `RUSTUP_HOME`, `PLAYWRIGHT_BROWSERS_PATH`, `NPM_CONFIG_CACHE`, `NPM_CONFIG_PREFIX`) still point at the old path. Update via `[Environment]::SetEnvironmentVariable(v, new, 'User')` and read back — but note **current shells keep the old PATH**; only new processes get the new values, so a stale shell is NOT proof the fix failed.
2. **Scoop `current` junctions are absolute** → dangling after rename (visible in `ls`, but content access fails). Rebuild with PowerShell `New-Item -ItemType Junction -Path <link> -Target <real>`. Do NOT use `mklink /J` from git-bash — MSYS mangles the target into a `D:\D:\...` double-drive prefix.
3. **Scoop shims** (`shims/*.exe`) hardcode the absolute target path → all fail with "Shim: Could not create process". Fix with the project's `scripts/rebuild-scoop-shims.ps1` (external dir usually has one).
4. **Activate scripts** using `cygpath -w` produce Windows paths that MSYS PATH splits at the drive letter (`D` + `\All projects\...` as two entries) → `which ffmpeg` fails while direct path works. Build PATH from the MSYS-form root (`$ROOT/toolchains/...`), not cygpath -w output.
5. **Git credentials break** ("could not read Username") when the PATH change orphans the credential-manager helper → fix with `gh auth setup-git`.
6. **ACL-denied deletions**: toolchain dirs (VS Build Tools) contain Administrators/SYSTEM-owned files; non-elevated shells get "Access denied" on rmdir even with `-Force`. Don't force ACLs. Copy with `shutil.copytree(..., onerror=chmod-retry)` + file-count/byte verification, then leave an admin-only `.bat` (`rd /s /q "..."`) for the user to run elevated.
7. **Missing historical git tree** (`git fsck` → "missing tree", often from an old PR commit): verify HEAD tree intact (`git cat-file -e HEAD^{tree}`); fetch does NOT fix it if the remote lacks it too; normal dev/CI unaffected — don't rewrite history to repair.

Verify with functional smoke on the migrated root (`tesseract --version` with TESSDATA_PREFIX, `ffmpeg -version`), then the full test suite through the external venv. Full recipe with commands: `references/external-toolchain-root-rename.md`.

### 2g. `.hermes/cache` + `.hermes/task-artifacts` third-party build-product accumulation

The project-ignored `.hermes/` tree can silently accumulate **hundreds of MB of
third-party package sources and build intermediates** (validated 2026-08-15 on
ArcheAxis-Knowledge-OS: `.hermes/cache` = 17,191 files / 452 MB and
`.hermes/task-artifacts` = 20,919 files / 513 MB — guardrails/policy/numpy/tcl/
rrule config+source dumps, `numpy-config.exe`, `rules.vc`, dozens of duplicate
`config.py` copies). This is NOT evidence and NOT a build target of the project —
it is dependency/build-tool output that fell into the wrong root.

Audit pattern (do not delete by size alone):

1. Inventory the two dirs separately: file count, total bytes, and the
   **vendor fingerprint** — third-party module names (guardrails, numpy, tcl,
   rrule, realtime_*), build artifacts (`*.exe`, `*.vc`, `*.h`, `config.*`),
   and exact-duplicate groups (`config.py` ×20, identical `VERIFICATION_POLICY*`
   snapshots).
2. Classify every candidate as `third-party-build-product` (regenerable via the
   real package manager), `evidence` (unique task artifacts, manifests,
   readbacks — retain), or `unverified`. Duplicates with identical hashes are
   regenerable by construction.
3. Check quiescence and provenance: nothing in the tree is referenced by
   tracked source (`git grep` for a representative filename returns zero hits in
   `app/`, `scripts/`, `tests/`), and no active process is writing there.
4. Reclaim only the regenerable vendor class (exact allowlist per directory),
   never the parent `.hermes/` unit, and never `git clean -fdx` (it would also
   hit task-runtime evidence). Keep `.hermes/task-artifacts` durable handoffs
   and task evidence.
5. Report per-directory before/after bytes and confirm `git status` unchanged.

The fix-forward counterpart: verify the launcher maps `TMP/TEMP/TMPDIR`,
`PYTHONPYCACHEPREFIX`, pip/uv, npm, cargo, and Playwright caches BELOW the
project root (see Project-local launcher environment closure) so dependency
builds cannot fall into `.hermes/cache` again.

### 3. Delete in independently auditable units

- Delete one allowlisted candidate at a time rather than using a broad wildcard or drive-level recursive command.
- Record path and pre-delete byte size after each successful unit.
- If one target fails, stop only that target; re-scan before continuing with unrelated approved candidates.
- Remove an empty parent directory only after confirming it has no remaining children.

### 3a. Pruning skill/reference libraries after a completed change

When removing stale skill content or references from a repository, treat the cleanup as a tracked-source change, not as cache deletion:

1. Enumerate candidates under the exact skill root and search the whole repository for each basename/path before deletion.
2. Classify each candidate as `referenced`, `governance-required`, `orphaned`, or `unverified`. Keep files referenced by tests, manifests, provenance checks, or public documentation until those consumers are updated or intentionally retired.
3. Delete only repository-owned, unreferenced, session-specific material. Do not remove a user drift copy, official bundled skill, live profile asset, or a reference merely because it is large or old.
4. Run the narrow governance/reference-integrity test after deletion, then run the complete quality gate. A passing pre-cleanup gate does not validate the post-cleanup tree.
5. Recompute the exact diff identity and obtain a fresh review after any deletion. Do not reuse review evidence from the pre-cleanup tree.
6. Report three evidence classes separately: tracked source changes, project-ignored `.hermes` verification artifacts, and host toolchain paths. Ignored artifacts may be regenerated; neither they nor host paths prove that tracked cleanup touched user data.

This prevents deleting a useful reference because its parent skill no longer links it, while still reclaiming genuinely orphaned project-specific material.

### 4. Verify and report

- Re-scan every approved root.
- State exact successful deletions, remaining items, and reason for each retention.
- Report recovered bytes exactly when captured; otherwise label it an estimate based on rounded pre-scan figures.
- Confirm protected volumes were not touched.

### Project-local launcher environment closure

When cleanup work reveals project outputs escaping to Windows `%TEMP%`, user-profile caches, or default package-manager homes, add a project-scoped launcher environment rather than changing global variables. Map `COGNITIVE_DATA_DIR`, `TMP/TEMP/TMPDIR`, `PYTHONPYCACHEPREFIX`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `NPM_CONFIG_CACHE`, `PLAYWRIGHT_BROWSERS_PATH`, and `CARGO_HOME` below `<project>/.hermes/task-runtime/`; source/call the same mapping from PowerShell, `.bat`, and Git-Bash launchers. In Git-Bash, use `pwd -W` before passing paths to Windows Python—`/d/...` can become `D:\\d\\...`. Verify resolved paths from both shells. For fresh-runtime smoke tests, run the real migration operator against the same project-local `COGNITIVE_DATA_DIR` before starting the server. Keep Hermes global sessions, credentials, Gateway, cron, and toolchains outside this project boundary.

### 1a. Windows user-profile spill audit after migration

When checking whether a project was fully moved off `C:\Users\<user>`, do not treat every name match as current-project data. Build a compact, metadata-only inventory of exact candidates under the user profile and classify them separately:

- **Repository copy:** run read-only `git rev-parse --show-toplevel`, compare the remote repository identity, branch, HEAD, and dirty-entry count. A similarly named checkout may be a different repository and must not be deleted or merged by name alone.
- **Test spill:** inspect `AppData\Local\Temp\pytest-of-*` after test runs. Aggregate file count, byte size, and newest mtime instead of dumping thousands of paths. If the files are from the current project, fix the future temp/cache boundary first; only remove exact, quiescent, regenerable test directories with explicit cleanup authorization.
- **Desktop runtime:** treat `AppData\Local\<app-id>\EBWebView` as shared WebView2 state until ownership is proved. Compare recent mtimes and the actual `msedgewebview2.exe` command lines for the profile's `--user-data-dir`; absence of active use makes it a stale-remnant candidate, not an automatic deletion authorization. Cold-launch/readback verification is required before removal.

Always compare the C-drive candidates with the project-local `.hermes/task-runtime/` and the approved external software/environment directory. Report exact candidates, evidence, and unresolved ownership; do not silently claim migration complete. Keep the audit output aggregated and secret-free. See `references/windows-user-profile-project-spill.md` for the reusable evidence matrix.

### 1b. Cross-root drive spill audit (C:\ + D:\ roots)

When the user names a list of spill paths at drive roots (e.g. `D:\clo-*`,
`C:\wa-review-*`, single-letter dirs) and asks "怎么解决" (how to solve),
run the full read-only audit before proposing deletion:

1. **Inventory the named paths** — per-path recursive file count, bytes
   (including subdirs), newest mtime, and top-level contents. Report
   DIR/FILE/SYMLINK; a symlink is reported, never followed. Dedupe the
   user's list (the same path may appear twice).
2. **Scan drive roots for undiscovered spills** — single-letter dirs
   (`D:\a`, `C:\c`) are pytest/tempfile classic roots; name-pattern spills
   (`clo-*`, `wa-*`, `tmp`, `scratch`, `review-*`) and any alpha single
   letter. Compare against a keep-list of legitimate roots (Windows,
   Program Files, Users, ProgramData, project dirs, tools, backups).
3. **Attribute with two independent signals** — content/provenance PLUS one
   of: repo scripts referencing the pattern, a Git workdir, or the
   generating command. `git grep -l 'spill-name|basetemp' -- '*.py' '*.sh'
   '*.toml' '*.yml' '*.json'` across every project repo: **zero hits means
   the spill came from agent/CI direct commands (e.g.
   `--basetemp=D:\clo-xxx`), not repo config** — fix forward by routing
   future runs through the project wrapper, not by patching repo scripts.
4. **Spill checkout attribution (predecessor-repo trap)** — a spill dir
   containing `.git` may belong to a DIFFERENT repo than assumed. Read
   `git remote -v` and `git -C <checkout> status --porcelain` BEFORE
   classifying: uncommitted WIP (hundreds of lines across
   scripts/tests/config) forces retention, not deletion. A remote pointing
   at a predecessor/original repo (e.g. `DTALEX66/Workflow-assistance`
   while the active project is the successor `WORK-LAB`) means the WIP may
   be the only surviving copy — retain and offer to archive a diff first.
5. **Quiescence and active signals** — a lock-file mtime fresh within the
   same day is an ACTIVE signal even when no matching process exists
   (processes die but the runtime was recently used) ⇒ retain.
   `pre_migration_*.sqlite` and similar backup files inside spill dirs are
   protected recovery backups ⇒ retain, regardless of size/age.
6. **Classify and wait for authorization** — present the full table
   (path, size, attribution, 删/保留/阻塞) and await explicit confirmation
   before deleting ANY item. "怎么解决" is a request for the plan, not a
   deletion authorization.

See `references/cross-root-spill-audit.md` for the concrete session recipe
and classification table.

## Deduplicating Git-tracked build-generated artifacts

When a monorepo carries duplicate media because a build script copies canonical
assets into per-platform export dirs (`android-minigame/visual`, `wechat/…`,
`douyin/…`, webview asset copies), the duplicate files are often **already
tracked in Git**, which means `.gitignore` rules for those dirs are silently
ignored (`.gitignore` does not untrack an already-tracked file). The waste can
be tens of MB and is a real repo-volume defect.

Procedure:

1. **Quantify by content hash, not by name.** Hash every tracked media file
   (`git show HEAD:<path>` piped to sha256) and group by digest. Report unique
   vs duplicate groups and the exact wasted bytes (sum of `(copies-1) × size`).
   A name-based scan misses cross-dir duplicates and over-attributes.
2. **Classify canonical vs derived.** A dir is *canonical* when the build
   regenerates the *derived* copies from it (`build.js` `syncAssetDirectory`
   from `assets/…` into each `${platform}-minigame/…`). Verify this by reading
   the build script's source→output mapping before deleting anything.
3. **Untrack, don't delete.** `git rm --cached <derived dirs>` removes them
   from the index while keeping files on disk. Confirm the file count of `D`
   entries matches the duplicate count. Keep canonical copies tracked.
4. **Add/confirm ignore rules** for the derived dirs so a rebuild does not
   re-stage them.
5. **Prove regeneration.** Rebuild all platforms and confirm the derived files
   come back on disk from canonical sources, and that a **drift gate** (a script
   comparing rebuilt bundles to `git show HEAD:...` byte-for-byte) still passes
   for the committed core files. A deterministic build gate prevents the exact
   recurrence this cleanup fixes.
6. Verify `npm test`/unit gates still pass and the worktree stays clean after
   a rebuild (test/builid must not re-dirty the tree).

This is the *build-governance* fix (source of truth + regeneration), distinct
from cache cleanup. Do not delete canonical large files (single-copy GIFs/PNGs)
just because they are big; they are not duplicates.

### Removing an obsolete tracked asset class (visual/binary media retirement)

When a whole asset class is retired — "these game CCTV visuals / audio / release
assets are no longer needed" — this is **not** cache cleanup and **not** dedup:
it is a tracked-source removal with a rebuild + test-fix loop. Never delete by
directory name alone; the removal must keep the design spec while dropping the
asset files.

1. **Classify before deleting.** Read-only inventory first (`git ls-files`,
   disk size, sha256). Split candidates into: `asset files` (delete),
   `design spec / state manifest` (KEEP — a code file listing the 24 CCTV state
   IDs is a spec, not an asset), `historical docs` (keep or annotate), `build
   outputs` (regenerate, don't hand-edit). Keeping the state manifest after the
   PNGs are gone is correct: the manifest describes WHAT states exist, so
   runtime degrades to empty instead of crashing.
2. **`git rm`, not `rm`, and record the baseline HEAD first.** `git rm` keeps
   every blob reachable from history, so the whole removal rolls back with one
   `git checkout <baseline> -- <paths>`.
3. **Grep both the asset root names AND their file extensions across the whole
   repo** before deleting, to find every consumer: source imports, CSS
   `url(...)`, build scripts' `syncAssetDirectory`/`copyFileSync`, test
   assertions, doc references. `var(--name)` refs degrade to empty after the
   variable is removed (safe, no request); literal `url("...png")` refs WILL 404
   and must be removed.
4. **CSS url refs are scattered across blocks** (`:root`,
   `[data-skin=...]`, and `@media ... { :root { ... } }` overrides). Patching
   only the `:root` block misses the `@media` override. After patching, re-grep
   the CSS for the asset dir name / `url(` — never assume one patch got them all.
5. **Build scripts that copy the assets break after removal** (e.g.
   `syncAssetDirectory(visualSource, ...)` now copies a nonexistent dir; a
   `prepare-*-webview` script that `copyFileSync`s the asset files). Update them
   in the same pass, and delete now-dead asset-generation scripts whose source
   AND output dirs are both gone.
6. **Regenerate tracked build outputs** (bundled game.js, webview asset copies)
   after editing shared sources, else the tracked copies stay stale with old
   references. Note a multi-platform build may inline a shared module into only
   SOME outputs (android inlined `audio.js`; wechat/douyin used platform audio),
   so only some game.js files change — don't expect all-or-nothing diffs.
7. **Tests are the leak detector.** Run the suite; failures point at every
   remaining reference AND at anti-drift tests that assert README/docs still
   describe the removed assets. Update those assertions to reflect the removal
   (e.g. assert "assets removed" instead of "visual CCTV monitor").
8. **Final whole-repo grep for the deleted dir names** to confirm only
   historical docs (non-runtime) still mention them, then `git diff --check`.

### `git gc` does not reclaim history-referenced blobs

After dedup/cleanup, `.git/objects` may still be large (e.g. 350 MB) even after
`git gc --aggressive --prune=now` returns with no change. Root cause: the big
blobs are **reachable from historical commits** (e.g. old `cctv-*-loop.gif`
versions replaced by smaller `*-lite-loop.gif` copies). `gc --prune` only drops
*unreachable* objects; anything still in a commit's tree is kept, so the pack
stays the same size.

Rules:
- **Verify reachability first**: `git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)'` then, for each large path, `git cat-file -e "HEAD:<path>"` to tell "in HEAD" from "historical only".
- Historical-only blobs referenced by commits cannot be removed without **rewriting history** (BFG / filter-repo), which changes every downstream SHA and requires a force-push.
- Do **not** rewrite history or force-push to shrink `.git` when the project enforces exact-SHA alignment / no-history-rewrite (task-pack discipline). Report the large history as an accepted cost instead of attempting a destructive rewrite.
- `git gc --aggressive` is safe (does not change SHAs) but will *not* fix a history-referenced large pack — set that expectation honestly rather than claiming cleanup succeeded.
- A large current-HEAD tracked asset (single-copy game media, canonical sources) is legitimate content, not cleanup fodder.

### Authorized history rewrite (filter-repo) to reclaim a history-referenced pack

When the user **explicitly authorizes** history rewrite + force-push (overriding
the exact-SHA / no-rewrite discipline above), you CAN shrink a
history-referenced large `.git` pack. This is a validated end-to-end workflow
(e.g. 351 MB → 185 MB by stripping 9 obsolete historical GIFs). Sequence and
the non-obvious pitfalls:

1. **Identify exact paths to strip** — only historical-only blobs NOT in HEAD:
   ```
   git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
     | awk '$1=="blob" && $3>5000000 {print $4}' | while read f; do git cat-file -e "HEAD:$f" 2>/dev/null || echo "$f"; done | sort -u
   ```
   Sanity: for every path, confirm `git cat-file -e "HEAD:<path>"` FAILS (i.e.
   none is in HEAD) before rewriting.
2. **Install** `python -m pip install git-filter-repo` if missing.
3. **Path file MUST be a Windows path.** `--paths-from-file /tmp/...` fails with
   `FileNotFoundError: b'/tmp/...'` because filter-repo runs under Windows
   Python which cannot resolve the MSYS `/tmp` path. Write the list under the
   project's ignored `.hermes/task-runtime/` and pass `$(cygpath -w <path>)`.
   ```
   git filter-repo --invert-paths --paths-from-file "$WINPATH" --force
   ```
4. **filter-repo removes the `origin` remote** by design — re-add it after:
   `git remote add origin <url>`.
5. **force-push**: `--force-with-lease` will be REJECTED with "stale info"
   because the local rewritten ref no longer matches remote. First confirm the
   remote HEAD is your own last-push SHA (`git ls-remote origin <branch>`),
   then use plain `git push --force origin <branch>`.
6. **Do not trust a single `git gc` after the rewrite.** A later `git fetch
   origin` can re-import the large objects via OTHER remote branches (e.g. an
   old `main` / a redundant feature branch that still reference the stripped
   history). After promoting the clean history and deleting redundant branches:
   `git remote prune origin`, `git branch -f main <clean-sha>`, `git reflog
   expire --expire=now --all`, then `git gc --prune=now` to actually drop them.
7. **Verify content completeness** after rewrite: tracked file count, key
   tracked files still present (`git cat-file -e "HEAD:<path>"`), and that no
   legitimate asset (e.g. `-lite-loop.gif`) was accidentally matched by a broad
   glob. Use exact per-path lists, never a glob that would catch HEAD files.
8. When multiple cloud branches are "fat", promote the clean branch as the new
   `main` (`git push --force origin HEAD:main`) and delete redundant branches
   (only after proving they carry no unique commits:
   `git rev-list --count origin/main..origin/<branch>` == 0). Confirm the branch
   topology, `.git` size, local/remote alignment, and a clean worktree after.

See `references/git-history-rewrite-filter-repo.md` for the full transcript-style
recipe including the Windows path pitfall and the post-fetch re-bloat trap.

See `references/git-tracked-build-artifact-dedup.md` for the content-hash
detection snippet, the exact `git rm --cached` sequence, and the pitfalls
(`r"D:\"` syntax error, docstring-vs-codepath security asserts).

## Cloud and local branch pruning (GitHub merged-branch cleanup)

When the user asks to "clean up redundant branches" on the cloud and locally,
do not delete by name or intuition. The reusable audit:

1. Enumerate every remote branch and, for each, compute ahead/behind against the
   default branch:
   ```bash
   git ls-remote --heads origin | awk '{print $2}' | sed 's|refs/heads/||' | sort
   for b in <branches-except-main>; do
     ahead=$(git rev-list --count origin/main..origin/$b)
     behind=$(git rev-list --count origin/$b..origin/main)
     last=$(git log -1 --format='%cr' origin/$b)
     echo "$b ahead=$ahead behind=$behind last=$last"
   done
   ```
2. **`ahead=0` ⇒ safe to delete** (fully merged). But do not trust a single
   "tree differs" signal on the `ahead>0` set: those branches are behind main by
   many commits so their whole tree differs by construction. For each `ahead>0`
   branch, list the unique commits (`git log origin/main..origin/$b --oneline`)
   and, before deciding, confirm the content was superseded — e.g. a v1 branch
   superseded by a v2 branch that merged, a stale PR branch replaced by later
   work, or a docs-only/duplicate commit. Present the table and get the user to
   pick scope; **default to deleting only `ahead=0` merged branches and keeping
   superseded/unmerged ones** unless ownership is proven.
3. **Squash-merged branches look `ahead>0` but are safe to delete via the
   absorption check.** A squash-merge never brings the PR branch's original
   commits into main, so `ahead>0` by construction — and a per-file
   `git diff origin/main...origin/<branch>` shows the whole tree differing.
   The decisive test is which files are MISSING from main:
   ```bash
   git diff --name-only origin/main...origin/<branch> | while read f; do
     git cat-file -e "origin/main:$f" 2>/dev/null || echo "BRANCH-ONLY: $f"
   done
   ```
   **0 branch-only files ⇒ content fully absorbed by the squash commit ⇒ safe
   to delete**, even with `ahead>0`. This cleared 62+ merged-PR residue
   branches in one 2026-08-12 sweep (all `feat/h2-*`, `fix/*`, `docs/*`). Note
   "differs" ≠ "unabsorbed": main's copy is usually a SUPERSEDED-banner /
   evolved superset of the branch's, so per-file diffs show additions, not
   branch-only losses. Treat a file that exists on both sides as absorbed
   regardless of how different the content is.
4. **`gh pr list --head <branch>` returns NULL for merged PRs** — the head-branch
   query only matches open/closed state by default, so a bulk script using plain
   `--head` reports every merged branch as "NO PR FOUND". Use
   `gh pr list --state merged --head <branch> --json number,mergedAt --jq '.[0]'`
   to resolve merged-ness, and a separate `--state open` call before treating a
   branch as an orphan. In the 2026-08-12 sweep this flipped the result from
   "67 no-PR branches, delete nothing" to "62 merged → delete, 5 investigate".
   Delete via `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`
   (batchable, works for any branch name), then `git fetch --prune origin`.
5. **Retention classes survive cleanup.** Keep, regardless of age: the default
   branch, authority/blueprint branches (`codex/frozen-*` — the append-only
   truth log), release-contract branches (`release/v0.4.0-contract` — historical
   release identity), branches owned by OTHER concurrent sessions, and a branch
   holding the ONLY copy of a historical doc (e.g. a closed-PR
   `docs/verification-summary-*` — deleting the branch risks GC reclaiming the
   only retained snapshot; offer to archive its file into `docs/` and get Owner
   approval first). A closed-but-unmerged branch with 1-5 unique commits whose
   files are absent from main is NOT automatically safe — it may be the only
   copy of that work; investigate before deleting.
6. Check no open PR references a branch before deleting (`gh pr list`). Delete
   with `git push origin --delete <branch>` one at a time (a bash loop with an
   inline `sed` transform can break on `[`/`]` in a branch name — use a plain
   loop and confirm via `git ls-remote --heads origin` after), or batch via the
   `gh api -X DELETE .../git/refs/heads/<branch>` endpoint (step 4).
7. Locally, delete only branches that are actually merged into main
   (`git branch --merged main | grep -v main`), never the unmerged set
   (`git branch --no-merged main`), which may carry unique commits (WIP/feature
   work). Then `git fetch --prune origin` to drop gone remote-tracking refs.
8. Treat a `C:\Users\<user>\scoop`-style path that resolves to a **Junction**
   (ReparsePoint) pointing at the external config root as *already migrated*, not
   as 6 GB of reclaimable C-space: `Get-Item ... -Force | fl FullName,LinkType,Target`
   shows LinkType=Junction, and deleting the link recovers nothing (the data is
   on the other drive) while breaking old-path compatibility. Verify the junction
   target exists and is active before reporting "no C-drive space to reclaim".

## Legacy checkout archive and absorption proof

See `references/legacy-archive-and-absorption.md` for the per-file monorepo absorption matrix and the Windows `git archive HEAD` fallback when a clean legacy checkout cannot be renamed because of an active directory lock.

## Pitfalls

- **Run-conclusion vs job-log contradiction in CI.** A run can finish `failure`
  while the job log tail shows tests all passed (`1085 passed, 1 skipped`), and
  the aggregate `a0-gates` also passes. This is a real signal to investigate,
  not a green flag: read the failing job's log for `exit code`/`failed` across
  ALL test steps (OS-level/KB/integration), not just the tail, and query
  `gh run view <run> --json conclusion,attempt`. A single attempt with a hidden
  failing test that later steps mask is common. Never merge on "logs look green"
  when the run conclusion is `failure`.
- When a canonical verifier enforces a `required_refs` check ("docs must mention <path>"), rewriting/slimming a README or positioning doc can silently fail the whole gate (e.g. 456→FAIL) because you removed lines that listed required doc paths. Before treating it as a verifier bug, re-read the verifier's `required_refs` list and restore those paths — conventionally in a "complete doc index" code block that lists every required path verbatim. Fixing the gate by re-adding the exact referenced paths is correct; editing the verifier to drop the check is not (the check keeps docs discoverable). Run the full gate after any doc rewrite, not just `git diff --check`.
- Do not classify a large project-local `.hermes`, virtual environment, toolchain, or runtime directory as external garbage solely due to size.
- Root-level recovery markers and system DLLs are not project artifacts; leave them alone.
- **A spill checkout may belong to a predecessor repo.** Read `git remote -v`
  inside the spill dir before attributing it to the project you assume — a
  `wa-review-*` dir pointed at `DTALEX66/Workflow-assistance`, not the
  successor `WORK-LAB`. Uncommitted WIP in it (+1800 lines in one case)
  forces retention and a diff archive, never deletion.
- **A fresh lock file is an active signal even with no matching process.**
  Same-day lock mtime inside a spill runtime (e.g. browser-smoke) means
  retain — never delete on "no process found" alone.
- **Repo grep for the spill pattern returning zero hits means the spill came
  from agent/CI direct commands** (`--basetemp=D:\clo-*`), not repo config —
  fix forward by routing future runs through the project wrapper.
- A failed recursive delete can still have removed earlier siblings. Never report all-or-nothing cleanup without a post-delete scan.
- Generic operating-system temp files may coexist with project artifacts. Delete only explicitly attributable names/paths, not all of `%TEMP%`.
- **A tool-reported junction/symlink is a claim, not a fact.** Before "cleaning duplicate junction entries", verify each path with Windows-native authorities: `fsutil reparsepoint query "<p>"` returns error 4390 for a plain directory (a real junction returns its reparse tag); `Get-Item` shows the Reparse attribute unset; a true junction shows identical content on both sides. This session a scan tool reported two junctions that did not exist — acting on the false premise would have deleted the real WORK-LAB repo and a toolchain project. Refuse the deletion and present the proof when the claim fails verification. Full recipe in the `windows-development-environment` skill.
- **Deleting a REAL junction from git-bash: use `rm <link>`, not the obvious tools.** git-bash renders a Windows junction as a symlink (`lrwxrwxrwx`), so `rmdir <link>` fails with "Not a directory", PowerShell `Remove-Item -LiteralPath` throws `NullReferenceException`, and `cmd //c "rmdir ..."` from git-bash mangles the args (`//c` + unquoted path breaks into an interactive prompt). Plain `rm <link>` removes the link only, never the target tree. When cmd is unavoidable, use `MSYS_NO_PATHCONV=1 cmd /c '...'`. (Same lesson applies after a project-directory rename interlude: the junction alias must be removed before the physical dir takes the name.)
- **Archive sensitive-data audit**: when asked to inspect user data inside an archive, classify paths by category (credentials/env/keys → sessions/memory DBs → skills/plugins/config/rules → browser-profile artifacts) and report paths + classes only, never values. Chrome test profiles (`Login Data`/`Cookies`/`History`/`Web Data`/`Sessions` under `.tmp-chrome-*`/`chrome-v5*`) are the realistic sensitive class; real `.env`/auth.json are often absent. An archive containing browser artifacts is local-only — never upload it. See `references/sensitive-data-archive-audit.md`.
- **Bash passes a leading `--` into `$@` when a wrapper is invoked with `-- args`.** Calling `run_tests.sh -- -k smoke` on a non-builtin script delivers `--` as `$1`; a naive `exec pytest ... "$@"` then emits `pytest ... tests -- -x ...`, and pytest treats the mid-args `--` as an end-of-options marker → `ERROR: file or directory not found: -x` while the session still "runs". Strip a leading `--` inside the wrapper (`if [ "${1:-}" = "--" ]; then shift; fi`) before forwarding.
- **A MSYS `/d/...` path in a wrapper silently nullifies pytest basetemp.** `$(pwd)` under Git-Bash returns `/d/All projects/...`; Windows Python/uv cannot resolve it, so `--basetemp=/d/...` is ignored and pytest reports `collected 0 items` with NO error — the containment fix appears to work but writes nothing project-local. Diagnose by tracing the exec line (`bash -x`) and checking for a `/d/` prefix; fix by computing a Windows-form root for child-tool args (`ROOT_WIN="$(cd ... && pwd -W | sed 's|\\\\|/|g')"`) while `cd`/existence checks use the POSIX form. See `templates/run_tests.sh` for a known-good project-local pytest entry script embedding both fixes.
- **MSYS `/d/...` mis-resolution has a nastier second variant: `PYTHONPYCACHEPREFIX`.** Unlike basetemp (silently ignored), the pycache prefix IS honored but resolved from the MSYS form — Windows Python turns `/d/All projects/<repo>/.hermes/task-runtime/pycache` into `D:\d\All projects\<repo>\...`, recursively mirroring the project-relative structure at the drive root (`D:\d\All projects\<repo>\.hermes\task-runtime\pycache\All projects\<repo>\app\...pyc`) AND polluting the project-internal pycache dir with `All projects`/`Users` child dirs. Diagnostic signals: project pycache contains `All projects`/`Users` subdirs; a drive-root `D:\d\...` tree whose leaf pyc files duplicate module paths; pyc version matches the venv Python (e.g. `cpython-312` when uv runs 3.12). Fixes: resolve the prefix at conftest time (`_TASK_PYCACHE = (_TASK_RUNTIME / "pycache").resolve()`) and always launch tests with a Windows-form cwd (`cd "D:/..."`, verify with `pwd -W`) — launching from `/d/...` in git-bash is what feeds the MSYS form into child processes. Cleanup: such trees are pure regenerable pyc — verify non-git + no writes in the last ~60s, delete, then `rmdir` the emptied parent chain (it is a spill mirror, not evidence).
- **`git fetch origin '+refs/*:refs/remotes/origin/*'` can break `origin/main` resolution.** The all-refs refspec overwrites the remote-tracking layout and `git rev-parse origin/main` then fails with `ambiguous argument 'origin/main': unknown revision`. This surfaces mid-audit as a "cloud updated" false alarm. Repair with the standard refspec `git fetch origin '+refs/heads/*:refs/remotes/origin/*' --prune`, then re-verify `git rev-parse --short refs/remotes/origin/main`.
- **GitHub `pushed_at` is the authoritative "did the other machine really push" proof.** When a user insists a second machine pushed updates but local fetch shows nothing, query `gh api repos/<owner>/<repo> --jq .pushed_at` (live timestamp, updates on ANY ref push). If it equals your last merge time, nothing reached the cloud — the other machine's push failed or never ran. This outranks branch listings, open-PR queries, and fetch results as cloud-sync evidence.

## Related reference

See `references/external-artifact-cleanup.md` for the compact evidence and reporting checklist.
See `references/smoke-test-cleanup-and-ledger-drift.md` for autonomous audit-cycle cleanup patterns and state-ledge drift recovery.
See `references/recurring-boundary-audit-patterns.md` for the sleep-mode recurring boundary audit checklist covering gitignore completeness, root-level empty dirs, non-standard runtime subdirectories, and cache-vs-stale discrimination.
See `references/ownership-classification.md` for the project-vs-workflow ownership matrix, two-signal delete gate, and cross-volume recovery procedure.
See `references/path-safe-vault-import-adapter.md` for building a path-safe vault/asset import adapter that reuses `ApprovedRoots`, is idempotent and revisioned, and never writes governed tables (Compatibility-Kernel pattern).
See `references/windows-external-artifact-recovery.md` for copy/hash/verify/delete, reparse-point rejection, deep-path cleanup, handoff manifests, and post-migration verification.
See `references/sensitive-data-archive-audit.md` for the read-only sensitive-data classification matrix and the MAX_PATH/regenerable spill-cleanup refinement (archive durable evidence only; delete regenerable pycache directly with hashes).
See `references/project-local-routing.md` for the complete pre-launch cache/build environment mapping and the containment verification probe.
See `references/project-local-launcher-windows.md` for the Windows PowerShell/Git-Bash launcher mapping, `pwd -W` path verification, and fresh-runtime smoke prerequisite.
See `references/project-local-test-wrapper.md` for the validated wrapper's full trap analysis (MSYS-path nullification, leading-`--` pass-through, spill attribution, and `--collect-only` count comparison as the wrapper-correctness probe).
