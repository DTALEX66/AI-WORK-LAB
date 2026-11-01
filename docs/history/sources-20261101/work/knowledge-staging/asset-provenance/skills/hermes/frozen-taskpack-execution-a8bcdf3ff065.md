---
name: frozen-taskpack-execution
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/frozen-taskpack-execution/SKILL.md
---

---
name: frozen-taskpack-execution
description: Resume frozen TaskPack baselines with append-only status.
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [taskpack, frozen-baseline, evidence-ladder, status-log, governance, cognitive-loop-os]
---

# Frozen TaskPack Execution

Use when a project runs a **frozen execution baseline** (an immutable task-definition doc plus mandatory addenda, an append-only status log, and a strict evidence-ladder completion protocol). The user expects every session to resume the DAG from the last recorded state — not to re-plan, re-freeze, or rewrite frozen definitions.

## When to Use

- The user points you at a TaskPack / frozen baseline file and says "重新载入项目" / "resume" / "继续".
- The repo has a `FROZEN_EXECUTION_BASELINE_*` file, an append-only `EXECUTION_STATUS_LOG.md`, and `docs/VERIFICATION_POLICY.md`.
- You need to pick the next task to execute among a fixed ID set (`AXW-*`, etc.).

## Load order (before any execution)

1. `AGENTS.md` / project context.
2. The frozen baseline's first sections + the current Horizon/task row.
3. Every mandatory addendum relevant to the current Horizon (web-ingestion tasks require the Web addendum; search→intake→course→learning→AI-reuse tasks require the Capability-first addendum).
4. **Only the last relevant record** of the append-only status log — not the whole history.
5. `docs/VERIFICATION_POLICY.md`.
6. `git status --short`, branch, HEAD, origin, divergence, and worktree list.
7. The implementation/tests/manifest/call sites directly touching the current task.

Canonical files for Cognitive-Loop-OS live on cloud branch `codex/frozen-roadmap-deepseek-v1`, NOT `main`. Fetch them into `.hermes/task-runtime/` via raw.githubusercontent.com, then verify SHA-256.

## Non-negotiable rules

1. **Frozen files are immutable.** Baseline, addenda, and their SHA files are never edited. All progress, `DEVIATION`/`BLOCKED`/`SUPERSEDED_PROPOSAL`/`CHANGE_PROPOSAL` records **append** to the status log only.
2. **Evidence ladder (low→high):** `STRUCTURAL < LOCAL_RUNTIME < EXACT_SHA_CI < PUBLICATION < LIVE_INSTALLED`. A lower level never substitutes for a higher one.
   - CI must correspond to the exact candidate SHA; skipped/required-but-skipped/cancelled/failed is NOT pass.
   - Native Windows install-state (`LIVE_INSTALLED`) is required for runtime/installer claims; WSL is not a substitute.
3. **Next task = first whose dependencies are all PASS** per the DAG. Resume an existing `IN_PROGRESS` before starting a new one. Dependencies are frozen task IDs only — never milestone/Program/object names.
4. **Dirty canonical checkout ⇒ isolated worktree.** When the main worktree carries unknown WIP, build an isolated worktree from the latest remote `main` and leave unknown changes untouched. Never work in-place over unknown dirty state; never reset/clean.
5. **One task = one `IN_PROGRESS`** at a time. Single integrated writer; reviewers are read-only or use separate branch/worktree.
6. **Status vocabulary:** `UNASSESSED` / `IN_PROGRESS` / `PASS` / `PARTIAL` / `FAIL` / `BLOCKED` / `DEFERRED` / `DEVIATION` / `CHANGE_PROPOSAL` / `CORRECTION`. `PARTIAL` is never reported as done.
7. **Stop conditions** (any of): H0–H5 + all mandatory addenda PASS; real user authorization/decision/material needed; data-corruption/secret-exposure risk; a genuine frozen contradiction (append `DEVIATION/BLOCKED` + minimal `CHANGE_PROPOSAL`); or user abort. "Code written / most tests pass / docs updated / model thinks done" are NOT stop reasons.

## Governance-layer task pattern: append-only tables + supersede chains (validated 2026-08-14)

H3/H4 governance tasks (AXW-024C/024D, 050A/050B, 051B, 052B, 053, 054A/054B,
043B) all follow one reusable skeleton — implement it once, reuse across tasks:

1. **Append-only SQLite record/event table** — every mutation INSERTs a new
   row; ``superseded_by`` column marks the old row when a new version replaces
   it (history is never overwritten; audit = full table scan).
2. **Candidate by default** — new records are `reviewed=0`; projection
   (active set) = `reviewed=1 AND superseded_by IS NULL`; unreviewed output is
   never directly active (GOV-001 / approved-only semantics).
3. **Fail-closed projection** — unknown/absent governance rows are EXCLUDED
   from retrieval (never guessed active).
4. **"Latest wins" ordering must use `ORDER BY rowid`, NOT
   `created_at, <random-id>`** — created_at collides within the same
   millisecond and random ids sort arbitrarily (freshness/relations tables
   hit this; rowid is the monotonic insertion order).
5. **Pydantic contracts with `extra="forbid"`**; fail-closed raises for
   invalid kinds/empty ids/unknown supersede targets.
6. **Per-task triple of functions** — record / review-flip / project (or
   status / history / active) + one same-shaped test file (6-8 tests: happy
   path, supersede preserves history, invalid input fails closed, active
   projection excludes superseded).
7. **SQLite multi-statement schema** via `conn.executescript` (see Pitfalls).
8. Tests must use `copy.deepcopy(FIXTURE)` for nested shared fixtures — a
   shallow `dict(FIXTURE)` lets one test's nested mutation poison later tests.

This pattern closes AXW-024C/024D/050A/050B/051B/052B/053 in one batch with a
single PR and exact-SHA CI, leaving only install-state/Owner-gated EXITs.

## Self-verifying export/backup manifests (AXW-094A/094B pattern, validated 2026-08-15)

Any open-exchange export or backup snapshot needs integrity verification with
fail-closed semantics. The working pattern (took 4 iterations to get right):

1. **Manifest written LAST** — a crashed/partial export has no manifest, so
   verification fails explicitly ("manifest.json missing (partial export)").
2. **Manifest self-hash covers the body WITHOUT the self-referential field**:
   set `manifest_path` FIRST (it participates in the hashed body), compute
   `sha256(json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False))`,
   then write the FULL manifest (including `manifest_sha256`) to disk.
   Verify by reading the file, stripping `manifest_sha256`, recomputing the
   SAME serialization, and comparing. Two bugs that bit:
   - writing only the pre-hash body → the field is missing on disk and
     verification compares against None → perpetual "hash mismatch";
   - setting `manifest_path` AFTER hashing → export and verify hash different
     bodies (field present in one, absent in the other) → mismatch.
3. **Verify re-hashes every item file** against per-item `sha256`, collecting
   failures (item id + expected/actual prefix) into ONE aggregated explicit
   error — never a silent partial verdict.
4. **Backup restore is rehearsable** — `dry_run=True` returns the plan
   (create/overwrite per file) without writing; real restore is atomic
   (temp-then-replace) + writes a restore receipt; clobbering requires
   explicit `overwrite=True`. A restored target is NOT a backup (no
   backup-manifest), so verify restored content against the RECEIPT's
   recorded hashes, not with the backup verifier.
5. Windows: never use `sha256:`-style colons in FILENAMES — `:` starts an
   NTFS alternate data stream; `"sha256:abc"` creates an empty file named
   `sha256` with stream `abc` (see windows-development-environment).

## Threaded batch executor with pause/resume/safe-exit (AXW-096C pattern, validated 2026-08-15)

A long-task batch controller (imports/conversions) needs these semantics and
their implementation gotchas:

1. **Pause = stop task pickup, allow in-flight to finish.** Gate the worker
   loop with a `threading.Event` (`wait()` before claiming a task); pause
   clears it, resume sets it. Tests must tolerate `completed <= paused+1`
   after a pause — the in-flight task may legally finish — never assert an
   exact frozen count.
2. **Global rate limiting: advance the clock INSIDE the claim lock.**
   `next_start` is shared across workers — read/wait/advance it under the
   same lock as task claiming, and declare it `nonlocal` in the worker
   closure. Advancing outside the lock races; forgetting `nonlocal` silently
   creates a per-worker local that never throttles anything.
3. **Safe shutdown**: set a stop event, set the pause event (unblock
   waiters), `join(timeout=...)` every worker, persist state. No orphan
   threads; assert `not t.is_alive()` in tests.
4. **Bounded retries**: per-task attempt counter; failures beyond
   `max_retries` are recorded (with error text truncated), never retried
   forever.
5. **Append-only JSONL checkpoint ledger** — each event (`tasks_added`,
   `task_completed` w/ result digest, `task_failed`, `pause`, `resume`,
   `shutdown`, `batch_end`) is APPENDED, never rewritten. `from_checkpoint`
   rehydrates: completed tasks keep their digests (silent corruption detectable
   by re-reading), uncompleted tasks re-queue. **Rehydration must be
   self-consistent (fixed 2026-08-15): recompute `completed`/`failed` counts
   from the ledger's per-task events AND restore the terminal state from the
   ledger's LAST `batch_end` event** — defaulting to `idle` made a finished
   batch report `idle` with `completed=0` while its results dict showed 2
   completed tasks (the async API's status poll read the ledger after the
   background thread finished and returned the inconsistent rehydrated state).
   interrupted batches (no `batch_end`) stay `idle`/resumable; finished ones
   report `finished`. Test ledger append-onlyness by asserting the head lines
   are byte-identical after a rehydrate run.
   **`tasks_added` must record the FULL task list, not just count/total**
   (fixed 2026-08-15): a ledger whose `tasks_added` event only carries
   `{"count": N, "total": N}` cannot re-queue never-run tasks — the
   rehydrated controller's `total` collapses to completed-only (200→36) and
   the un-run tasks silently vanish, breaking the "interrupted batch is
   resumable" promise. Record `"tasks": [<ids>]` in the event; restore
   `_tasks = [t for t in all_tasks if t not in completed and t not in
   failed]` and set `total = len(all_tasks)` (fall back to the recorded
   `total` only for old ledgers whose task list is unrecoverable). A
   mid-run shutdown test (200 tasks → shutdown → readback) is the regression
   probe: assert `total == 200` and `0 < completed < 200`.
6. Worker results: when a worker returns a dict, record its
   `result_digest` key in the ledger so content integrity is checkable
   after the fact.

## Library code is not a feature until it is reachable (API surface pattern, validated 2026-08-15)

The AXW-022B lesson (file exists ≠ feature usable) applies at the API layer
too: an H5 implementation that ships only as library functions (export/
backup/batch control) is not yet operable. Wire a Workspace API surface with
explicit error semantics, then let the wiring tests find the real defects:

1. **Add endpoints for every library-only capability** (e.g. exchange
   export/verify, backup create/verify/restore(dry-run), batch import/status/
   pause/resume/shutdown). Control endpoints for long tasks must be ASYNC:
   `POST /import` starts a daemon thread over a module-level registry
   (`_ACTIVE_BATCHES` dict + `threading.Lock`) and returns immediately;
   `GET /status` reads the live controller while active, the ledger after it
   finishes (rehydrated via from_checkpoint); pause/resume/shutdown operate
   the registry (404 unknown batch, 409 duplicate active). Daemon threads die
   with the process — no orphans, ledger survives.
2. **Wiring the surface surfaces real library defects** (2026-08-15, three):
   - a collector helper's root argument may mean "store root" while the
     endpoint passed the subdirectory (`extract_exchange_items(raw_root)`
     internally appends `originals/` → export was always empty);
   - the resumable converter requires the artifacts parent dir to EXIST
     before the worker runs (`output root parent not found`) — pre-create it
     in the endpoint;
   - wrapping an endpoint in a command-error adapter that converts
     `ValueError→422` makes any hand-written `except X → HTTPException(400)`
     around it DEAD CODE — drop the custom branch, let the adapter speak.
3. **Explicit error semantics, never silent**: validation/domain failures →
   422 (or the adapter's convention), missing resource → 400/404, duplicate →
   409. Tests cover success round-trips AND every error path.
4. Test isolation for env-resolved runtime roots: if the config helper reads
   the env var per call (`resolve_runtime_path` style), `monkeypatch.setenv`
   in a fixture isolates every endpoint into tmp without reloading modules —
   but module-level constants (DB_PATH) are NOT isolated; keep their use
   read-only in tests. Use `TestClient(app)` (full app), never
   `TestClient(router)` — a bare router raises
   `AssertionError: fastapi_middleware_astack not found in request scope`.
5. Asynchronous endpoint tests poll `GET /status` with a deadline
   (`while state not in ("finished","shutdown") and monotonic()<deadline`)
   instead of asserting a synchronous result; pause assertions tolerate
   in-flight completions (`after <= before + max_concurrent`).
6. **"可校验/可恢复"承诺必须用反例测试证明，不能只测 happy path**
   (validated 2026-08-15, API test-completion rounds). Three counter-
   example tests that turn a claim into a proven fact:
   - **篡改检测**: seed data → export/backup → corrupt ONE payload file
     (exclude the manifest!) → verify must fail (422) with an explicit
     reason ("corrupted" / "hash mismatch"). Without this, "verifiable"
     is a slogan. Backup manifest filename is `backup-manifest.json`;
     exchange manifest is `manifest.json` — corrupt the payload, not the
     manifest, or you test the wrong failure branch.
   - **实恢复（非 dry-run）**: restore with `dry_run: false` → data comes
     back byte-identical + receipt asserts `restored_files >= 1` and a
     `create` action; the backup stays verifiable afterwards. dry-run
     alone proves nothing about recovery.
   - **拒绝静默覆盖**: re-create the live file with different content →
     restore without `overwrite=true` → 422 "restore refused" AND the
     live file is proven untouched (read back original content). Safe
     restore = never clobber without an explicit flag.
   - **错误语义逐路径穷尽**: one test per status code across the whole
     surface — 400 missing source, 404 unknown batch (status AND each
     control endpoint: pause/resume/shutdown), 409 duplicate active,
     422 domain failures. A control-endpoint 404 test loops the actions.
   - **断言键名/消息按真实实现校准**: run once, read the REAL response,
     then assert — restore returns `plan` with `action` keys (not
     entries/state); exchange tampering reports "hash mismatch" (not
     corrupt); control 404 reports "no active batch" (not "not active").
     Guessing key names always goes red once; reading the actual output
     once makes the assertions pass immediately.

## Performance-benchmark data collection ahead of EXIT (AXW-096A pattern, validated 2026-08-15)

A "large-corpus / CPU-only performance" gate needs REAL measured data, and the
data-collection layer is self-executable even when the gate's acceptance (real
user corpus, H4-EXIT) is Owner-gated:

1. **Baseline §12 explicitly requires supplementing public-domain corpora**
   ("用户资料不完整且不具代表性，因此必须补充合法公开 corpus"). Download Project
   Gutenberg books (`https://www.gutenberg.org/files/<id>/<id>-0.txt`,
   plain-text public domain) through the configured proxy; record
   source/license/acquired-at/sha256 per sample in `sources.json`. Layer the
   corpus small/medium/large by file count; keep corpus TEXT out of the repo
   (`.hermes/task-runtime/corpus/`), commit only metrics + provenance.
   - **Bilingual coverage**: the baseline wants zh AND en. Discover Chinese
     public-domain titles via the gutendex API
     (`https://gutendex.com/books?languages=zh`) before downloading — known
     working zh ids: 西游记 23962, 红楼梦 24264, 儒林外史 24032, 警世通言 24141.
     Record a `language` field per sample in sources.json and layer mixed:
     small 1en+1zh / medium 4en+2zh / large all (identify language by book
     id in the filename, never by filename patterns like `-0`).
2. **Reproducible toolchain, not one-off measurements**: a prepare script
   (download + layering + provenance) and a run script (measure + report) so
   the baseline can be re-run on the real corpus later.
3. **Measure the REAL pipeline** (`convert_directory_resumable` latency via
   `measure_latency_ms` with warmup, tracemalloc peak memory, cold start =
   fresh interpreter `subprocess.run([sys.executable, "-c", "import ..."])`),
   plus corpus size + hardware identity (cpu_count/platform) in the report
   header.
4. **Fail-closed degradation thresholds**: explicit `DegradationThreshold`
   (latency_ms / memory_mib / cold-hot ratio) evaluated per run; a crossed
   threshold reports `degraded`, never "passed with caveats". Verdict table in
   the committed record (docs/truth/PERFORMANCE_BENCHMARK_096A.md style), full
   JSON in `.hermes/task-runtime/benchmark/`.
5. Benchmark scripts are plain scripts run by CI — remember the sys.path
   anchor + architecture-guard whitelist rules from `ci-browser-smoke-testing`.
6. **Project the new capability honestly in the capability atlas** (e.g.
   `docs/truth/CAPABILITY_ATLAS_V2.yaml`): when implementation lands but
   acceptance is still Owner/EXIT-gated, move the capability's
   `technical_state` `planned -> in_progress` — NEVER `supported`.
   `supported` is reserved for verified capability only (AXW-010B "仅把已
   验证能力投影到 Truth"): check the atlas's state vocabulary first
   (planned/in_progress/supported), `git grep` for tests referencing the
   atlas before editing it, and record the projection in the LOG entry.

## 全量推进的停止判定（validated 2026-08-14，EXIT 分类已修正 2026-08-15）

When the user says "全量推进任务，直到工具调用上限（无任务可做即停止）":

0. **Quick audit before classifying** (cheap, catches lost work):
   - `git branch -vv` — local branches showing `[origin/main: ahead N, behind M]`
     are usually stale PR leftovers; confirm nothing is lost with
     `git rev-list --count main..<branch>` == 0 before dismissing them.
   - Re-scan PARTIAL-marked frontend tasks with a real browser — **file exists
     ≠ feature usable** (AXW-022B: PDF.js canvas without text layer left the
     annotate button permanently disabled; only browser-level testing caught it).
1. **Sweep the frozen baseline and classify every remaining task**:
   - **self-executable** (pure code/tests/docs, no E:\ / real-Vault /
     Windows-install-state / Owner-gate dependency) → implement to closure;
   - **EXIT/verdict-gated ≠ implementation-gated** (CORRECTED 2026-08-15): a
     task whose frozen dependency is a Horizon-EXIT (H2/H3/H4-EXIT) or an
     Owner verdict (AXW-045, AXW-055) can STILL be implemented ahead of the
     gate. EXITs are *acceptance/qualification* criteria, not implementation
     prerequisites — precedent: 023A-F / 043B / 050A / 054A-B, and the whole
     H5 implementation layer (094A/094B/096A/096B/096C) shipped ahead of
     H4-EXIT (commit 5dc3d9b, browser-smoke CI green, LOG-148). The EXIT
     record itself stays UNASSESSED/owner-deferred; only the implementation
     completes early.
   - **install-state/Owner-gated** (AXW-095 Windows install-state, AXW-097
     release qualification, AXW-060 v1.0 release pack; RC-stage
     full-qualification per AXC-060 is a logical profile — never
     force-triggered in dev) → genuinely needs Windows install-state +
     Owner/release flow; do NOT attempt in a source-only session.
2. **Stop when every self-executable task is PASS** — do not invent filler
   work; the remaining list is a real external-dependency wall, not a gap.
3. Close with: final report separating implemented (with commits + CI runs)
   from gated (with the exact dependency each needs), confirm
   local=origin, and note the append-only LOG entries added.

## Per-Horizon batching (multi-horizon baseline)

A frozen baseline spanning H0→H5 executes one Horizon at a time, each as its
own isolated worktree and its own PR:

1. **Fresh worktree per Horizon.** Re-create the execution worktree from the
   *latest* `origin/main` merge SHA for each Horizon. Do not keep stacking
   commits on the previous Horizon's branch — a worktree whose base is an
   already-merged PR head is stale and must be re-created (`git worktree add -b
   axw/execution-hN <dir> origin/main`).
   Concretely after a Horizon PR merges: `git fetch origin main`, confirm
   `git rev-parse origin/main` is the new merge SHA, then
   `git worktree add -b axw/execution-hN <dir> origin/main` and **re-apply the
   next Horizon's new edits on that fresh base** (e.g. `cp` the changed files
   into the new worktree and run their tests there). The previous Horizon's
   worktree branch is now stale relative to main; leaving it as the base for
   new work produces a PR that drifts from main.
2. **One small checkpoint commit per task.** Each `AXW-*` task = one commit with
   RED→GREEN + changed-file Ruff + architecture guard + convention. Do not push
   every micro-commit as its own PR; batch a Horizon's commits into one PR.
3. **Exact-SHA CI before merge.** `gh pr checks <N> --watch`; confirm run
   `conclusion == success` and `mergeStateStatus == CLEAN`. Job-level
   `SKIPPED` is legitimate when the path classifier (AXW-003C) correctly omits
   unrelated heavy lanes — not a failure.
4. **Independent read-only review for high-risk changes.** Contract/schema/
   migration/security work: dispatch `delegate_task` with explicit per-checkpoint
   PASS/FAIL/WARNING output before merge. Act on review WARNINGs (e.g. a lossy
   round-trip → add a fail-closed raise) in a follow-up commit.
   - **Retrieving the async review result:** the review completes asynchronously
     and its `subagent-summary-*` file under the delegation cache may not be
     written yet when you first look. Don't block — keep working, then read the
     summary via the **live transcript** at
     `C:/Users/ALEX/AppData/Local/hermes/cache/delegation/live/deleg_<id>/task-0.log`
     (find the line starting `final    | status=completed ... summary:`), or
     glob `subagent-summary-*` newest-first and read the newest one. Confirm the
     summary is for THIS delegation (it may mention the reviewed commit), not a
     stale file from an earlier review.
5. **Merge is owner-gated even when CI is green.** Squash-merge a Horizon PR
   only after explicit owner authorization (a `clarify` asking for it). Merge
   with the API when a worktree holds the target branch name (see pitfalls);
   then record merge-SHA and run merge-SHA main CI.

## Per-task state machine

`DISCOVER → CONTRACT → RED → GREEN → TARGETED → REVIEW → CHECKPOINT → QUALIFY → APPEND`

Documentation-only tasks skip RED/GREEN but still need convention check, `git diff --check`, frozen-hash check, and link checks. Dependency/packaging/security/db/migration/desktop-lifecycle tasks must run the full gates plus independent read-only review.

## Test & evidence protocol

- Regular code: one provable RED → minimal GREEN → rerun + adjacent regression → Ruff on changed Python + `git diff --check` → checkpoint or full gate per policy.
- Evidence record must include: candidate tree/commit SHA; exact command + exit code; pass/fail/skip counts; CI run URL + its head SHA; bundle/installer hash; Windows version + install-state result; unverified items + rollback method.
- Don't paste long logs into the status file — save them to `.hermes/task-artifacts/`, put only the hash/path in the status record.

## Horizon handoff / task document (when the user asks to "完成任务文档")

When execution reaches a natural stop — a Horizon's backend is done but a
frontend slice is blocked on a separate batch, or the user repeatedly asks to
finalize the task document — produce a **single structured handoff doc** and
push it to the authority branch. Do NOT stop at per-task status-log lines; the
user wants one readable artifact that lets any future session resume cold.

Build `docs/truth/<STAGE>_STATUS_HANDOFF.md` with, in order:

1. **Baseline block** — taskpack file, baseline ID, authority branch, execution
   worktree(s), status-log file, and current date. State merge status explicitly
   (e.g. H0 merged to main, H1 PR OPEN unmerged).
2. **Status table per Horizon** — every task ID, `PASS`/`PARTIAL`/`UNASSESSED`,
   evidence level, and the LOG entry / CI run / review that backs it. Every
   PASS must bind a real evidence handle; mark incomplete items `PARTIAL` /
   `UNASSESSED` honestly.
3. **Independent-review record** — each read-only review (skill dispatch):
   conclusion and whether WARNINGs were fixed.
4. **Decision & deviation record** — taskpack-mandated `DEVIATION` /
   `CHANGE_PROPOSAL` entries (e.g. a frontend slice deferred to a separate
   batch while a backend slice ships first), plus any owner-gated action held
   (e.g. a merge not authorized → kept OPEN, fail-closed).
5. **Blocked/exit section** — which Horizon-EXIT is blocked and by which frozen
   dependency; the exact task IDs already PASS vs the one still open.
6. **Actionable execution queue** — the NEXT concrete steps a fresh session
   runs (e.g. the 7-step frontend batch: integrate lib → license/NOTICE →
   backend endpoint → frontend page → annotation → pytest+browser smoke →
   PR/CI/merge). Give exact file paths and reuse pointers (`pdf_serve`,
   `anchor.py`, `conversion_run.py`).
7. **Deliverable inventory** — map each new module/test file to its task ID so
   a future session knows what already exists and where. Derive it from
   `git diff --stat <base>..<head>`.
8. **Boundary confirmation** — E:\ untouched, no credentials read, frozen
   files unmodified, status log append-only, canonical WIP untouched.
9. **Future-Horizon overview** — one line per H2–H10 + addenda with their
   dependency gating and forced addenda prerequisites.

Re-verify the doc's accuracy before pushing: authority-branch SHA, status-log
range, and PR merge state all drift as you work. Keep the header's authority
SHA and log range current or the doc contradicts the repo.

Two finalization extras make the handoff doc self-navigating and auditable, and
both are worth adding once the doc is otherwise complete:

- **Authority-source-link header block.** After the intro paragraph, add a
  short `**权威源文件（相对本文件）：**` list of relative markdown links to the
  frozen baseline, append-only status log, authority contract, current-state
  truth, the execution taskpack, and each mandatory addendum (e.g.
  `[../../taskpacks/...](../../taskpacks/...)` from `docs/truth/`). Verify every
  target path exists (`test -f ...`) before committing — a dead link in the
  authority handoff is worse than none.
- **Evidence-index appendix.** Append `## 附录 A：证据索引（任务 → commit → CI）`
  mapping each Horizon's task group to its candidate commit(s) and CI run(s)
  (`H0 merge <sha> + main CI <run>`, each H1 task → its commit + `PR #72 CI`),
  plus the authority-branch commit chain and the still-open PR. This satisfies
  the taskpack's "stable record of task→commit→test→CI" Evidence-Index intent
  without duplicating long logs.

If you insert a numbered section, renumber every subsequent `## N.` heading
(incl. any appendix) and scan `grep '^## '` so the doc reads 1..N with no
duplicates.

## Autonomous continued-run + document-finalization convergence

When the user repeats a loop like `继续推进，工具调用上限为止（最终目标完成任务文档）`
several times, they want you to **keep advancing the DAG autonomously until the
tool budget is exhausted**, and when execution reaches a natural wall, to
**converge on the handoff document** rather than brute-forcing a heavy blocked
slice in the remaining budget.

**Owner's standing authorization (2026-08-12 onward):** the user explicitly
said `后续任务不要再问，再让我选择了，按你理解最有方案执行` — stop asking, stop
offering clarify choices; pick the best plan and execute. A repeated
`继续执行，直到工具调用上限（如果没有任何任务，问题需要修复，请停止）` means:
advance the DAG autonomously to the tool budget, and **stop when there is no
remaining eligible task or no problem to fix** — do not invent filler work to
keep going, and do not re-ask for direction. Document-layer / low-risk PRs
(truth docs, naming doc alignment, README text) may be squash-merged WITHOUT a
per-PR clarify once CI is green; keep explicit owner gates only for high-risk
change (schema/migration/security, naming of repository/package/CLI/bundle/data
root, release tags, destructive history rewrites). Verify the merged PR state
and origin/main SHA after each auto-merge and record LOG entries as usual.

Each cycle, in order:

1. **Continue the DAG**: pick the next eligible task (first with all deps PASS),
   run RED→GREEN → changed-file Ruff + architecture + convention → one checkpoint
   commit → push the Horizon branch → start `gh pr checks --watch` (background).
2. **While CI waits**, do the next independent thing that doesn't need the CI
   result: write the next task's RED test, or start the next Horizon-scope work,
   or append the completed task's status-log record.
3. **Act on exact-head CI**: if a job fails (e.g. a stale assertion that pinned
   the pre-fix dependency string), fix the test (not the code), push, and
   re-watch the NEW run — never reuse the old run's green as the new head's proof.
4. **Push status-log records** to the authority branch as tasks complete, so a
   hard tool-budget stop never loses recorded progress.
5. **On a hard wall** — a heavy cross-cutting slice (frontend/WebView, large
   external lib) that cannot be closed in the remaining budget, or a merge the
   owner has not authorized — **stop starting new implementation** and switch to
   document finalization. The blocked slice stays honestly `PARTIAL`/`BLOCKED`;
   do not fake it done.

Document finalization loop (repeat until the user's doc goal is satisfied):

- Re-verify handoff-doc accuracy every cycle: authority-branch SHA, status-log
  range (`LOG-004~N`), and PR merge state all drift as you work. Fix the stale
  values before/with each doc commit.
- Add one meaningful section/appendix per cycle when the doc is otherwise done:
  e.g. authority-source-link header block, evidence-index appendix, local
  test-result summary appendix, execution-protocol-compliance appendix,
  decision-and-deviation record, H0+H1 deliverable inventory. Derive inventory
  from `git diff --stat <base>..<head>`.
- After inserting any numbered section, renumber all `## N.` headings and scan
  `grep '^## '` so the doc reads 1..N with no duplicates (an appendix appended
  after `## 11.` does not disturb numbering; a mid-doc insert does).
- Append a status-log record for each doc finalization commit, so the authority
  branch's log range stays in sync with the doc header.

Convergence cue: once the doc covers status tables, reviews, decisions,
deliverables, blocked/exit state, actionable queue, evidence index, test
results, and protocol compliance, the task-document goal is met — give a final
summary separating PASS/PARTIAL/BLOCKED and stop, rather than inventing new work.

## Reading these files on Windows

`read_file` may report a UTF-8 Markdown file (full-width CJK punctuation like `：`/`→`, non-ASCII content) as **binary** and return nothing. Recovery: UTF-8 byte-decode it instead, e.g. via `execute_code`:

```python
from pathlib import Path
t = Path("...").read_bytes().decode("utf-8")
```

then split on line boundaries / scan headings and task IDs.

For Cognitive-Loop-OS specifics (canonical file list, frozen SHA-256, status-log state as of 2026-08-09, git divergence, next eligible task `AXW-BASE-0`), see `references/cognitive-loop-os-frozen-baseline.md`.

## Multi-task frozen gates: implementation present ≠ PASS — log PARTIAL with an evidence matrix

A frozen gate covering several sub-tasks (e.g. `AXW-023A~F` format adapters +
`AXW-H2-EXIT`) can look done because every sub-task's implementation and
contract tests are already in `main` — while the gate's acceptance criteria
(exact-SHA install-state qualification per format, bundle/SBOM/NOTICE parity)
were NEVER audited. 2026-08-12: the H2 adapters all had real engines
(markitdown/docling chains, pytesseract+rapidocr bake-off, ffmpeg+faster-whisper)
and 84 contract tests, yet `AXW-H2-EXIT` remained unqualified — only `AXW-023A`
had a merge record. The correct log entry is **PARTIAL with a per-row evidence
matrix** (implementation / contract-tests / install-state-evidence), marking
un-audited cells `未核录` and stating the qualification verdict is deferred to
Owner/release flow. Do not write "done" because code exists; do not skip
logging because evidence is incomplete.

- Sweep the frozen baseline's gate rows against the status log: any task ID
  with no LOG entry (or only an indirect "merged" mention) is an audit gap even
  when the code shipped under another PR.
- A PARTIAL matrix row needs three columns: what exists (impl + tests), what
  evidence is missing (install-state), and who decides the gate (Owner).
- Distinguish "framework-layer integration done" (H2 pipeline wiring) from the
  frozen per-format qualification — they are different gates; shipping one does
  not close the other.

## Intake records lag framework-direction batches

AGENTS.md (Cognitive-Loop-OS) requires a note under `workspace/intake/` when a
change affects framework direction. A multi-PR milestone (e.g. an H2 pipeline
integration batch: evidence/learning/bakeoff + compliance fixes) can land with
NO intake record — the directory simply stops at the previous week's files.
Before closing a milestone: `ls workspace/intake/ | tail` — if the newest entry
predates your batch, backfill ONE dated intake file covering the whole batch
(summary, per-PR notes, pending Owner items, rollback = revert each merge
commit). It is cheap and closes an AGENTS.md compliance gap the status log does
not cover.

## Stale historical status docs: append a dated note, never rewrite the body

Frozen-era handoff/status documents (e.g. `H0_H1_STATUS_HANDOFF.md`) record a
DECISION STATE at their date — "PR #72 未 merge / merge 未获授权, fail-closed"
was true on 2026-08-09. Weeks later the same doc can contradict itself: early
lines still say "未 merge" while a later section was updated to "merged
(fba208f), H1-EXIT PASS". This is not a lie to fix by editing the old lines —
the old record is the historical audit trail (who authorized what, when).

- Verify the truth first: `gh pr view <n> --json mergeCommit --jq '.mergeCommit.oid'`
  and `git log --oneline origin/main --grep="#<n>"` — confirm the actual merge
  SHA before writing anything.
- Fix = **append a dated update note at the top** (under the header block):
  state the merge SHA, the LOG entry that recorded it, branch cleanup dates,
  and "current truth = EXECUTION_STATUS_LOG". Leave every historical line
  untouched so the decision trail survives.
- Sweep ALL historical handoffs for the same contradiction class
  (`grep -n "未 merge\|待 merge" docs/HANDOFF_*.md`) — but treat docs dated
  weeks earlier with no self-contradiction as historical snapshots that need no
  note (CURRENT_STATE_TRUTH rule: old handoffs are migration input only).
- Same principle applies to status-log fixes: dedupe by removing the LATER
  duplicate block (keep first occurrence), never renumber/rewrite history.

## Pitfalls

- **Session-level handoff docs (HERMES_HANDOFF.md) go stale fast; rewrite
  to current state, then micro-sync on every significant round** (validated
  2026-08-15). A handoff generated weeks earlier can point at a dead branch
  (`feat/runtime-evaluation-sleep-leases`) and completed tasks — a resume
  session would chase ghosts. Rewrite it with a fixed skeleton: current
  continuation point (branch/HEAD/cloud/test-baseline), closed-work list
  (with commits + CI run ranges), Owner-gated remaining work (with the exact
  dependency each needs), non-negotiable environment facts, boundaries. Then
  after every few LOG entries or CI-run advances, micro-sync ONLY the range
  numbers (LOG a..b, CI runs x..y) and add one line per new closed item —
  never let it drift a full session again. Before rewriting, grep the doc for
  branch names/SHAs and check whether they still exist.
- Re-planning the whole DAG each session instead of reading the last status-log record → wastes tokens and can contradict recorded decisions. Read the tail only.
- Treating a milestone label as a dependency → use only frozen task IDs.
- Calling a lower evidence level PASS (e.g. module import or unit test standing in for bundle/installer/LIVE_INSTALLED).
- Forgetting that the canonical files live on a non-`main` cloud branch → fetch explicitly.
- Working directly in a dirty canonical worktree → must isolate.
- **`gh pr merge --squash --delete-branch` fails with `fatal: '<branch>' is already used by worktree`** when any worktree holds the branch name. Merge via the API instead: `gh api -X PUT repos/<owner>/<repo>/pulls/<N>/merge -f merge_method=squash`, then `git fetch origin main` and `git rev-parse origin/main` to capture the merge SHA.
- **`MigrationOperator(db_path=..., backup_dir=...).apply(owner_name)` needs the DB file to already exist** — it raises `FileNotFoundError` otherwise. In a test, create a sentinel table first (`conn.execute("CREATE TABLE IF NOT EXISTS sentinel(id TEXT PRIMARY KEY)")`) before migrating.
- **SQLite schema with multiple statements**: `conn.execute(schema_string)` raises `ProgrammingError: You can only execute one statement at a time`. Use `conn.executescript(schema)` for multi-statement `CREATE TABLE`/`CREATE INDEX` blocks.
- **Adding a field to a Pydantic `extra="forbid"` contract model is backward-compatible** when it has a default (`field: T | None = None`), but every serialization point must be audited: an adapter round-trip that drops the new field on a legacy row silently loses data. Fail closed (raise) on that path rather than silently dropping, and add an adapter behaviour test.
- **Scope-gated retrieval (governed assets like MachineKnowledge) needs a fail-closed filter, not just a scope column.** Adding `scope: str | None = None` to a governed model is only half the contract. The retrieval query must take an optional `scope` argument and return only items whose `scope` is `None` (generic, visible to any retrieval) OR equals the requested scope — never a scoped item leaking into a different-scope retrieval. Keep the default (no scope arg) returning everything for backward compatibility. Add tests for: exact-scope match returns scoped+generic; different-scope request hides the scoped item; default returns all. And on the legacy row adapter, fail closed (`ContractMappingError`) if a scoped item would be round-tripped to a row that cannot represent scope.
- **CI aggregator gating on a GitHub job name instead of the GatePlan semantic ID** silently lets a required gate fail green. The ci-verdict must `require <gate-id>` (e.g. `py-primary`, `static`, `lint`), never the job name (`test`), and map the result via the correct job's env var.
- **A dependency extra change (e.g. `markitdown` → `markitdown[pdf]`) breaks exact-head CI through a stale test assertion, not the code.** The bare `markitdown` package ships no PDF backend, so installed-runtime PDF conversion fails with `MissingDependencyException`; the fix is `markitdown[pdf]>=0.1` in the product + `ci-adapters` groups and `requirements.txt`. But the `tests/test_ci_a0_gates.py` `test_runtime_policy...` test still asserts the OLD bare string, so exact-head CI fails on exactly that one test. Sequence when changing a dependency extra: (1) edit `pyproject.toml` + `requirements.txt`; (2) `uv lock` and confirm the extra's transitive deps appear (e.g. `pdfminer-six`/`pdfplumber`/`pypdfium2`); (3) update the stale test assertion to the new string; (4) bump `app/release-manifest.json` `dependency_lock.digest` + `revision`; (5) push and watch the NEW exact-head CI, never reuse the old run's green.
- **A PR whose branch is already merged to `main` is stale for the next Horizon.** Re-check `git rev-parse origin/main`; if your worktree HEAD is the old merge SHA, create a fresh worktree from the new SHA before continuing.
- **A SQLite "transaction" that also writes a filesystem file is NOT atomic across the two stores.** If a handler writes immutable original bytes (`store_original`) then a converter/conflict path fails and the `BEGIN IMMEDIATE`/`commit()` SQLite block rolls back, the bytes file is left orphaned (content-addressed, but referenced by no job/receipt). This is a real consistency gap an independent review will flag. Fix pattern: track `wrote_original = True` after the file write, and in the `except` cleanup path call `store.remove_original(digest)` before re-raising, so a failed import leaves no orphaned file. Also catch `store_original` write failures and re-raise as the task's own error type (a `RawAssetStoreError`/`ValueError` escaping a caller expecting `ImportJobError` is an inconsistent error contract). Add tests asserting NO raw files remain after both a conversion-failure and a same-command-id-different-input conflict rollback, not just that DB rows are 0/0/0.
- **Appending a status-log record via a heredoc whose body contains `&&` or `&` can be rejected by the terminal backgrounding guard** ("Foreground command uses '&' backgrounding"). The same content with `&` inside the LOG record text triggers it. Split the operation: append the record with `printf '\n### LOG-... \n...' >> docs/truth/EXECUTION_STATUS_LOG.md` (no shell `&`), then `git add` + `git commit` + `git push` as separate terminal calls, not one chained `... && git commit ... && git push` line. This also keeps a failing diff-check from aborting the whole append.
- **Inserting a new numbered section mid-document leaves duplicate `## N.` headers** (e.g. adding a new "## 5. Decisions" before an existing "## 5. AXW-H1-EXIT"). After inserting, renumber every subsequent `## N.` heading in order; verify with a heading scan (grep `^## `) before committing so the handoff doc reads 1..N with no repeats.
- **A frontend reader task (PDF.js etc.) can be split into a backend slice that is independently provable.** Before the full web/WebView rendering work, deliver the backend that serves the original bytes to the reader: a content-addressed endpoint/module (e.g. `pdf_serve` backed by the RawAsset store) returning bytes by `sha256:`-prefixed key, read-only and size-bounded, so the reader never sees the storage path. This backend slice gets its own RED→GREEN + checkpoint, and the task is honestly marked `PARTIAL` (backend done, frontend pending) in the status log rather than claimed complete. Only finish the frontend rendering/annotation in a dedicated frontend batch with real browser/WebView click-level verification.
- **Generate real binary fixtures (PDF/Office) with `uv run --with`, never by editing the lockfile.** When a task needs a real binary sample (not a renamed text file) that must pass a semantic Oracle, inject the generator without polluting `uv.lock`:
  `env -u PYTHONPATH uv run --frozen --only-group ci --with reportlab --with pypdf python <script>`
  This works even when the project's `ci`/`ci-adapters` groups don't declare those libraries. Record the sample's SHA-256 + license + expected semantics in a manifest, and write the generated corpus only under the project's ignored `.hermes/` runtime dir.
- **reportlab CJK and "scanned" PDF fixture gotchas.** A real-PDF Oracle (e.g. AXW-011A) has two silent failures that look like converter bugs but are fixture bugs: (1) the default `Helvetica` font cannot render CJK — Chinese pages come out with `has_chinese=False`; register `pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))` and pass `chinese=True` to the canvas `setFont`. (2) a "scanned / no text layer" fixture must draw ONLY vector/graphic content — if you `drawString` a label like `"SCANNED IMAGE (no text layer)"`, the Oracle's `text_len == 0` assertion fails. Both are caught by running the Oracle on every regenerated corpus, not by eyeballing the PDF.
