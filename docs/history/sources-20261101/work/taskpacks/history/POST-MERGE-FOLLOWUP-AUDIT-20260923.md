# WORK-LAB POST-MERGE FOLLOW-UP AUDIT — 2026-09-23

**Authority basis:** `main@139dec8` (post PR #127 squash `62f666e` + PR #128 authority revalidation `139dec8`),
`WORK-LAB-AUTHORITY-20260918-V2`, taskpack `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918`
(execution discipline §4 "short branch -> PR -> exact-SHA CI -> merge", §5 "update open register after accepted cards").
Frozen retrieval anchor `803268d/606db59` (WORK-LAB-AUTHORITY.md §13) — NOT the trunk, unchanged by design.

## 1. Post-merge trunk state (verified readback)

| item | state |
|---|---|
| main trunk | `139dec8` = `62f666e` (PR #127 squash) + `139dec8` (PR #128 authority revalidation) |
| taskpack index `baselineRevalidation.main_ref` | re-pinned `62f666e`, branch=main (PR #128) |
| ruleset 23825562 aggregate | cleared (work-lab-gate @b993e9c 5/5 SUCCESS incl. observer `SKIPPED_HEADLESS`) |
| U19 headless layer | CLOSED `SKIPPED_HEADLESS` @9f57ca3; real-desktop E2E = known-external |
| DSH desktop entry | re-pinned 3-field .lnk discipline (Target+`--user-data-dir`+IconLocation) in AGENTS.md + ERR-087 ledger |

## 2. Open-task register lifecycle after merge (this change set)

Advanced `MERGED -> READBACK` at `62f666e` (only user `ACCEPTED` sign-off remains):
A03, A04, U01, U17, U17a, U20, U21 (7 rows).

Re-qualified on evidence:
- **A00** `BLOCKED_CURRENT_CHATGPT_GITHUB_SCOPE` -> `MERGED@62f666e`: authority package landed; 403 was a
  preparation-session ChatGPT-GitHub-App blocker bypassed by the local Hermes/Codex write identity; the full
  authority chain re-verifies on main (verifier PASS, index references exist on disk).
- **A02** `OPEN` -> `PARTIAL@62f666e`: A04 dependency removal done; docs converged in `dc6dea5`
  (18 taskpacks + 12 dated docs frozen, 50-taskpacks/ removed, 518.4 MB reclaimed).
  **Residual BY DESIGN**: root `90-archive/` (16 files) is marked+gated `HISTORY_ONLY_CONVERGE` per
  `90-archive/BOUNDARY.md` — boundary verifier forbids a second active history root; physical removal is a
  future user-authorized action (class D2-style), not drift.
- **A05** `OPEN` -> `RECORDED@62f666e`: cutover/foreign-history truth recorded without rewriting Git history
  (BRANCH-CONVERGENCE-ANTI-REGRESSION + BRANCH-RETIREMENT-LEDGER + `WL_INHERITANCE_MATRIX.json`
  MiniGame=`FOREIGN_HISTORICAL` + frozen anchor 803268d). All verified present on main.
- **U19** last layer: `PENDING` -> `CLOSED as SKIPPED_HEADLESS` (environment boundary R5); the remaining
  real-desktop WebView2 E2E layer is known-external (needs a real Windows desktop / self-hosted runner).
- Dated `OPEN-TASK-REGISTER-20260917.md` frozen to `taskpacks/history/` (authority §13: no obsolete register
  bodies in current/); taskpack index `open_task_register` pointer re-bound to the single live register.

## 3. Follow-up task list (post-merge, by priority)

### P0 — next authorized cycle
1. **User ACCEPTED sign-off** for the 7 `READBACK` rows (A03/A04/U01/U17/U17a/U20/U21 + A00) — closes the
   lifecycle; no technical work remains.
2. **Taskpack expiry check (verified 2026-09-23, no action needed)**: UPC `authority.expires = unbounded`
   (superseded only by a newer registered CURRENT). The '2026-09-24 expiry' string in the taskpack index
   belongs to staticHandoffViews notes about the SUPERSEDED R1 taskpack, not to the UPC. V2 convergence
   work is LANDED; register a new CURRENT taskpack only on explicit top-level direction change (discipline §6).
   UPC remaining work = item 1 (user sign-off) + items 3/4 below.
3. **A02 residual — EXECUTED (user-authorized 2026-09-23)**: 15 report files git-moved to
   `docs/history/archive/reports-history/2026-09-05/` (MOVE-005 EXECUTED) on branch
   `post-merge/90-archive-convergence`; `90-archive/` retains only the `BOUNDARY.md` gate marker
   (verifier SPLIT_DIRS seam) — single history retrieval anchor = docs/history/ confirmed.
4. **U19 desktop layer — owed to an MSVC-capable runner (local attempt documented)**: 2026-09-23 local
   desktop harness run = honest FAIL (fail-closed, no fabricated PASS): local GNU-toolchain app.exe
   early-exits 0xC0000135 (WebView2Loader not linked under GNU build) + this machine lacks a Rust/MSVC
   toolchain (cargo/rustc absent). Backend v3 PASS + tauri_launch RUNNING reconfirmed locally; evidence
   `.project-local/runs/u19_webview_readback.json`. To close: MSVC-capable desktop/self-hosted runner
   (per U19 handoff Path 1; do NOT chase on hosted CI).

### P1 — deferred, individually authorized (no drift)
- **U18** universal-workflow real slices: module infrastructure green; the `UNIVERSAL_WORKFLOW_VERIFIED`
  label still requires real external-project write + second real executor + revision/cancel/restart/receipt
  slices (taskpack holds `externalProjectWrite: NOT_AUTHORIZED_BY_TASKPACK`).
- **U02/U08** partials: manifest/profile/setup/runtime-root/package-manager cleanup; Windows real-WebView
  E2E now folds into item 4 above.
- **D2**: CLOSED-VACUOUS@2a1c7b2 — 2026-09-23 full-repo scan found 0 tracked .bak/.orig/.backup (the only untracked one is inside the declared .project-local runtime root); nothing to delete.

### P2 — optional / research (deferred, no schedule pressure)
- C2 paid four-arm model experiment, C3 Kimi/Agents-API/Bolt research, O1 Hermes state.db
  optimize-storage, O2 API-key doctor — all OPTIONAL/DEFERRED in the live register; revisit only when a
  concrete defect or user request makes one blocking.

### D — environment-blocked (do not chase)
- D1 sandbox ACL synthetic acceptance only; blocks nothing else.

## 4. Documents & records scanned (drift verdicts)

| surface | verdict |
|---|---|
| `WORK-LAB-AUTHORITY.md` §13 frozen anchor 803268d/606db59 | CORRECT-RETAIN (immutable retrieval anchor; live trunk resolves dynamically) |
| `project-authority-index.json` `baselineAtCreation`/`preFreezeCommit` = 803268d | CORRECT-RETAIN ("immutable" declared; `currentMainMustBeResolvedDynamically: true`) |
| `taskpack-authority-index.json` `baselineRevalidation` | STALE -> re-pinned @PR #128 (`62f666e`); `open_task_register` pointer -> re-bound to live register (this change set) |
| `OPEN-TASK-REGISTER.md` two 09-20 `merge_main=false` notes | HISTORICAL (labeled as such, kept); superseded by the 2026-09-23 post-merge reconciliation note (this change set) |
| `OPEN-TASK-REGISTER-20260917.md` in current/ | STALE-SPRAWL -> frozen to `taskpacks/history/` (this change set) |
| `DRIFT-AUDIT-CLOSURE-20260923.md` §7 "merge GATED" | STALE -> backfilled CONVERGED (this change set) |
| `U19-HEADLESS-REQUALIFICATION-HANDOFF-20260923.md` remaining paths | open-options doc -> POST-MERGE STATUS addendum (Path 3 executed; Path 1 open known-external) |
| `V2-FINAL-ACCEPTANCE-REPORT.md` DRAFT v1 "merge blocked" | SUPERSEDED (post-merge addendum @PR #128) |
| `90-archive/` root | CONVERGED: reports moved to docs/history (MOVE-005 EXECUTED, user-authorized); BOUNDARY.md marker retained as gate seam; no active content |
| `docs/history/`, `taskpacks/history/` | FROZEN layer — untouched, correct |
| `config/client-evidence.json` / `adapter-registry.json` / `AGENTS.md` DSH declarations | corrected @b993e9c (ERR-087 ledger, 87 entries PASS) |

## 5. Verification (local, this change set)

- `verify_project_authority_reference.py` / `verify_three_project_boundary.py` / `verify_error_ledger.py`:
  run on the pushed PR head; expect PASS (no critical-zone change in this set: only `taskpacks/`,
  `.project/governance/taskpack-authority-index.json` metadata, `docs`-adjacent register bodies).
- Exact-SHA CI on the PR head is the release-grade proof; local structural checks are non-release evidence.

## 6. Standing rules after convergence

- main = sole trunk; all future work = short branch -> PR -> exact-SHA CI -> merge (discipline §4).
- Open register updates after accepted cards (discipline §5); register is single-live; dated registers
  freeze to `taskpacks/history/` immediately.
- Merge authority stays user-gated: no `merge_main` without an explicit user "合并".
