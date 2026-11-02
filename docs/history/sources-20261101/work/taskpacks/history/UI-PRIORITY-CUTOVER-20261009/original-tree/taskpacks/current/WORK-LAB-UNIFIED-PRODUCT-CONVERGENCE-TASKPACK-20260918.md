# WORK-LAB UNIFIED PRODUCT CONVERGENCE TASKPACK — 2026-09-18

**TaskPack ID:** `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918`  
**Top authority:** `/WORK-LAB-AUTHORITY.md`  
**Preparation baseline:** `main@803268da9dc356fe63f26b3b5405f724bc06b5b9`

Resolve current `origin/main` again at execution start.

This is the only forward execution TaskPack after landing. Older TaskPacks remain history only.

# A — AUTHORITY RESET

## A00 — Land top authority

Commit:
- `/WORK-LAB-AUTHORITY.md`
- `/.project/governance/project-authority-index.json`
- this TaskPack
- `/taskpacks/current/OPEN-TASK-REGISTER.md`
- `/taskpacks/history/FROZEN-LEGACY-INDEX-20260918.md`

Update existing `taskpack-authority-index.json` so every declared current path exists.

Current preparation-session blocker: connected ChatGPT GitHub App returned 403 for branch creation and file creation. Use a local Codex/Hermes/Git identity with write permission.

## A01 — Restore main enforcement

Using admin-capable GitHub readback, restore/verify:
- PR-first normal delivery;
- required `aggregate` exact-SHA gate;
- configured review requirements;
- no force push;
- no direct-push bypass.

## A03 — Machine authority verifier

CI must fail when:
- top authority missing;
- project authority index missing;
- CURRENT TaskPack missing;
- OPEN register missing;
- multiple CURRENT taskpacks;
- conflicting normative authority;
- frozen history marked normative;
- forbidden legacy active root returns;
- current path/ID mismatch.

## A04 — Migrate CURRENT_STATE before deleting history

Current known dependencies at the preparation baseline:
- `generate_current_state.py` reads `taskpacks/current/WORK-LAB-STAGE-3-TASK-GRAPH.json`;
- it scans `taskpacks/current/WORK-LAB-EXECUTION-EFFICIENCY-REPAIR-HANDOFF.md` as a canonical doc;
- current-state output carries Stage3 taskpack/task-count fields;
- tests assert fixed `skills.count == 13`.

Refactor so current state derives current identity from:
- top project authority;
- current TaskPack/open register;
- current projects/modules/contracts;
- dynamic skills inventory.

If Stage3 history remains visible, move it under an explicit historical section/history location.

Only after exact-SHA CI proves this migration may A02 remove old bodies.

## A02 — Physical history cleanup

After A04:
- converge `taskpacks/current/` to current TaskPack/open register/summary/README plus explicitly allowlisted compatibility files;
- remove obsolete historical TaskPack/Handoff/Complete/Audit bodies from default-branch current paths;
- remove legacy root `50-taskpacks/` / `90-archive/` after caller checks;
- preserve retrieval via frozen commit/tree.

## A05 — Cutover/foreign-history truth

Record without rewriting Git history:
- PR #124 squash-style cutover;
- old r4 ancestry preserved through archive refs/history rather than main ancestry;
- MiniGame is `FOREIGN_HISTORICAL`;
- no old branch becomes future authority.

# U01 — Mandatory test truth

Include `nf*.py` in mandatory discovery or use one canonical test manifest.
Required missing/skip/cancel/fail is not PASS.
Negative NF mutation must fail aggregate CI.

# U02 — Repository convergence

Finish, do not restart, September directory migration:
- README/current paths;
- PROJECT_POSITIONING under top authority;
- manifest baseline semantics;
- project profile roots;
- Token Monitor stale path;
- setup-workflow old `.hermes/task-artifacts` and `scripts/workflow/...`;
- old project skill-call-index path;
- root allowlist/regression;
- frontend package-manager SSOT;
- obsolete ignore compatibility.

Do not move native software Homes into `.project-local`.

# U03 — React/Tauri production UI SSOT

Production target:
- `apps/observer/frontend`
- `apps/observer/src-tauri`

Create static-web -> React parity matrix, migrate valid capability, then retire static web as production.

# U04 — Frontend information architecture

One typed view registry for Overview, Projects, Agents, Executions, Models/Usage,
Memory, Tools/Capabilities, Monitoring/System, Delivery, Trust, Settings.

Fix current Delivery/Trust/Settings reachability and remove array-index coupling.

# U05 — Full/Compact/Theme

React must actually parse and implement full/compact and dark/light modes.
Compact is a dedicated HUD.

# U06 — Runtime Descriptor / Snapshot / SSE

Fix full snapshot URL vs base-URL double append.
Define typed descriptor: schemaVersion, snapshotUrl, eventsUrl, optional metricsUrl,
instance identity/start metadata.
Remove fixed production 61867/9090.
Use Snapshot -> SSE -> revision/reconnect/Last-Event-ID; polling fallback only.

# U07 — Frontend truth discipline

Remove authoritative frontend hard-coding of provider price, FX, quota,
fake duration zero, missing metric/token zero, status fallthrough, fixed sidecar display.
Backend canonical projection owns truth. UNKNOWN remains UNKNOWN.

# U08 — Frontend/Rust/Windows testing

Add React behavior tests and Observer Rust:
`cargo fmt --check`, `cargo check --locked`, `cargo test --locked`.
Real Windows Tauri E2E is required before product convergence.

# U09 — Token Monitor convergence

One canonical token/usage/cost backend.
Observer main UI + specialist helper, or Observer parity then specialist UI retirement.
No deletion before parity.

# U10 — Config transaction truth

Preserve already-correct honest states.
Fix:
- monotonic safety floor;
- MISSING vs explicit null;
- expected-before/expected-after/write-set;
- apply intended after-state;
- typed readback failure;
- only real write + native matching readback = verified commit.

# U11 — REAL evidence binding

REAL requires evidence type, verifiable handle, identity/digest, producer,
verifier/readback, observedAt, source SHA/run identity when applicable.
Empty REAL handle is invalid.

# U12 — Durable Inbox/outbox safety

Reuse TaskLedger.
Add cross-process locking/fencing over full read-modify-write.
ACK exact `task_id + receipt_digest + revision`.
Real multi-process race/crash tests.

# U13 — Project isolation / usage / cost

Approved-project isolation for executions/usage/CI/git/Observer.
No cross-project fallback.
No project total copied into every execution.
Full cost identity; partial/estimated never becomes exact.

# U14 — Session/execution/worker effect truth

PROMPTED/RESUMED/CLOSED/CANCELLED/COMPLETED require native effect + readback.
Capability ladder: DECLARED -> DETECTED -> AVAILABLE -> INVOKED -> VERIFIED.
Handler return is not completion.

# U15 — Language architecture freeze

Create `docs/decisions/language-architecture.md`:
React/TS UI; Rust/Tauri native; Python control plane/adapters/orchestration;
JSON Schema cross-language SSOT; minimal shell/bootstrap.
No big-bang Rust rewrite.

# U16 — Cross-language contract SSOT

JSON Schema SSOT for RuntimeDescriptor, Snapshot, Execution, Usage, Receipt, Task,
Evidence, Project. Add Python/TS/Rust conformance/generated types where practical.

# U17 — Software/skill/model adaptation

Five-dimensional baseline; impact-diff updates.
States: CANDIDATE / POC_WRAPPER / WIRED / VERIFIED_RUNTIME.
Registry entry != runtime integration.
Preserve native provider/model/reasoning/auth choices.

# U18 — Universal Workflow real slices

Do not rerun completed synthetic M0-M3.
When individually authorized, prove real publish/readback, external project,
second real executor (Hermes + Codex first), multi-environment, native shared-rule
readback, zero manual task-body copying, revision/cancel/restart/receipt.

# U19 — Final Windows product E2E

Real chain:
main exact SHA -> worker -> canonical store -> dynamic sidecar -> Snapshot v3 ->
SSE -> Tauri -> React full + compact.

Must cover normal/empty/running/waiting/blocked/failed/cancelled/unknown/stale,
sidecar restart, Tauri restart, SSE reconnect, dynamic port, two projects,
usage/cost quality, CI state.

Final PASS requires:
AUTHORITY_SINGLE_CURRENT
AUTHORITY_REFERENCE_INTEGRITY
MAIN_CI_ENFORCEMENT
MANDATORY_TEST_TRUTH
REPO_STANDARD
FRONTEND_SSOT
FRONTEND_BACKEND_E2E
CONFIG_TRANSACTION_TRUTH
REAL_EVIDENCE_BINDING
DURABLE_INBOX_TRUTH
PROJECT_ISOLATION
SESSION_EXECUTION_TRUTH
LANGUAGE_ARCHITECTURE
WINDOWS_TAURI_E2E
EXACT_SHA_CI
ZERO_NEW_SPILL

Only then: `WORK_LAB_PRODUCT_CONVERGED`.

`UNIVERSAL_WORKFLOW_VERIFIED` is a separate stronger label.

# Legacy open-task mapping

- B1 old path residue -> U02/A04
- B2 Windows flaky/order issues -> U01/U19
- B3 Codex/DSH governance -> U17
- C1 ACP/MCP/AG-UI/model alias -> U17
- C2 paid four-arm experiment -> deferred
- C3 Kimi/Agents API/Bolt -> deferred
- C4 real Codex cancel -> U14/U18
- C5 Universal real external slices -> U18
- C6 real usage workbook/data source -> U13 conditional
- D1 sandbox ACL acceptance -> scoped environment block only
- D2 `.bak` deletion -> explicit user authorization
- Hermes state.db optimize -> optional
- API-key doctor -> optional unless concrete defect makes it blocking

# Execution discipline

At execution start:
1. resolve current main;
2. read top authority + project index + this TaskPack + open register;
3. do not reopen completed branch convergence;
4. short branch -> PR -> exact-SHA CI -> merge;
5. update open register after accepted cards;
6. do not create another top authority/taskpack unless user explicitly changes top-level direction.

Every card returns source SHA/tree, changed paths, before/after, positive/negative test,
runtime readback, frontend effect when applicable, rollback, evidence level,
remaining limitations.
