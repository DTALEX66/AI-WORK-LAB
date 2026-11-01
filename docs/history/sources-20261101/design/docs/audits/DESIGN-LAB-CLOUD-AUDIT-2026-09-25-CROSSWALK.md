# DESIGN-LAB CLOUD AUDIT 2026-09-25 (POST-FULL-SWEEP) — CROSSWALK

Supersedes no TaskPack; subordinates to `/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`).
This document is the **ingest + fact-check + disposition record** for the external
cloud audit pasted 2026-09-25 (RAW archived byte-level in
`docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-25-RAW.md`).

Per the anti-drift ingest rule ("先活对账、不实读则不立项"), every self-declared
fact of the audit was re-verified against live `origin/main` **before** any item
was itemized. No item executed blind.

## §1 Baseline fact-check (audit vs live)

Audit baseline `main@43003618...` (tree `6799f1f4...`, PR #157 squash) was verified
byte-exact against live `origin/main` on 2026-09-25 — the audit was run against
the current tip, so its fact layer is **current** (unlike the 09-24 audit, whose
fact layer was stale). Verified: open PR = 0, releases = 0, issues = 0, local =
remote = `main` only + 5 `archive-evidence/2026-09-25/*` tags.

Two named live defects, both confirmed on `origin/main@4300361`:

| # | Audit claim | Live fact (re-verified) | Verdict |
|---|---|---|---|
| F1 | `docs/LOCAL_ENVIRONMENT.md` still labels the 09-06 R3 TaskPack "当前 R3 任务包", conflicting with the 09-18 single current TaskPack | `docs/LOCAL_ENVIRONMENT.md:43` `- [当前 R3 任务包](taskpacks/DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.md)` — CONFIRMED live; the AGENTS.md current TaskPack is `DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md` | **REAL, agent-authorized** (docs-only current-looking text fix) |
| F2 | `configure_open_design_windows.py:49` and `doctor_open_design_windows.py:47` hardcode `D:\Programs\Open Design\Open Design.exe` | CONFIRMED live; B4 locator gate (`verify_adapter_locator_audit.py`) records these as `violations=2` and the inventory (`adapter-locator-inventory.json`) states "the refactor is the owner-gated TaskPack handoff this inventory defines; the entry is un-pinned when the refactor lands" | **REAL root-cause fix; agent-authorized minimal slice** (the gate's own contract anticipates landing + un-pinning); a *full* unified Tool Resolution Contract + resolver receipts + install-authorization receipt system is a larger product surface, owner-gated |

By-design / parked / owner-gated (re-confirmed, not reworked):

- **F3 H001 download-leg HTTP 415** — latest main-run `36084929153` @ `4300361` = `failure`
  solely on the non-required H001 artifact-proof lane. PARKED by design; audit's
  Prompt G ("fix or cleanly isolate from the required-green signal") is
  **owner-gated** — changing CI lane semantics or the artifact download protocol
  touches release gating, not a docs-only slice.
- **F4 `reports/current` subject SHA lag** (`bc71fcc` < live `4300361`) — self-referential
  rebind steady-state (the rebind generator writes subject = pre-rebind HEAD); the
  next rebind after a merge advances it. Not a defect.
- **F5 `authority-index.json` snapshot fields** (`observedMainSha=0e9f...`,
  `remoteBranchCountObserved=28`) — the file itself declares `snapshot only; refetch
  on every audit`. Not a defect; correctly treated as non-authoritative.
- **F6 Host Matrix E3/E4 `DECLARED-UNPROVEN`** — GD-1 gate (`verify_readiness_host_matrix.py`)
  already locks any fake `verified=true` claim; real-Host E3 / human-jury E4 are
  owner-gated by TaskPack. Not an agent-executable slice.
- **F7 `design-lab/core/` 7 modules, zero consumers** — classified
  `INFORMATIONAL-KEPT` in the 2026-09-25 close-out ledger; src/ migration is an
  owner architectural decision. The audit's "freeze; no new consumers without an
  ADR" is consistent and requires no code change.

## §2 Disposition of the audit's ten Agent Prompts

| Prompt | Scope | Disposition |
|---|---|---|
| **A — cloud truth re-audit** | re-verify live facts; minimal docs fix for current-looking refs | **EXECUTED (agent-authorized slice)**: RAW + this crosswalk; F1 `LOCAL_ENVIRONMENT.md` current-looking text fixed; F1–F6 re-verified against live; projection rebind scheduled on merge |
| **B — path drift + No-Download-On-Miss gate** | fix the 2 hardcoded Open Design defaults; locate via env → registry → PATH → fail-closed; shared deduped helper | **EXECUTED (agent-authorized minimal root-cause slice)**: `resolve_open_design_exe()` shared helper (env `OPEN_DESIGN_EXE` → `shutil.which("Open Design")`/`OPEN_DESIGN_EXE.exe` → fail-closed `None`), both scripts now import it, `--open-design-exe` explicit value still wins (no behavior regression), B4 inventory un-pinned; **the full Tool Resolution Contract + resolver receipts + install-authorization receipt system = owner-gated product work, NOT executed** |
| **C — Lite Workbench productization** (76 KB `main.ts` → AppShell/features) | UI product IA rebuild | **OWNER-GATED** (UI governance rule: product-IA decisions are owner calls; 禁幻影 KPI; no auto-commit before visual acceptance). Not an agent structural slice. |
| **D — in-Workbench Software Launcher / Host Center** | new product surface | **OWNER-GATED** (depends on the B-full contract + UI decisions). |
| **E — Agent / MCP Console** | new product surface | **OWNER-GATED**. |
| **F — Context Capsule / Env Snapshot** | new generated-context contract | **OWNER-GATED** (touches authority-boundary semantics; must not create a second SSOT — owner call). |
| **G — H001 HTTP 415 fix / isolation** | CI lane semantics + download protocol | **PARKED / OWNER-GATED** (F3 above). |
| **H — Photoshop / Illustrator current E3 Golden Workflow** | real-Host E3 | **OWNER-GATED** (TaskPack gate; GD-1 locks fake claims). |
| **I — Quality / Human Jury / Rights / Preflight / Handoff loop** | E4 + rights | **OWNER-GATED**. |
| **J — external project intake (Flow / ChatCut / Prompts / Jev / Jan / Witsy / Pinokio / …)** | external absorption | **OWNER-GATED** (no auto-install/auto-clone; owner authorization required per the audit's own rule). |

## §3 Agent-authorized execution this session

1. RAW audit archived byte-level: `docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-25-RAW.md`
   (54,223 bytes, sha256 `8ba4e014c74f16d9`, verified identical to the attachment).
2. F1 fix: `docs/LOCAL_ENVIRONMENT.md` current-looking line now points at the 09-18
   current TaskPack; the 09-06 R3 pack is labelled `SUPERSEDED` (historical pointer).
3. F2 fix: `design-lab/scripts/resolve_open_design_locator.py` (shared, MIT,
   fail-closed, env + PATH + explicit, registry noted as a documented extension point
   that requires `winreg` which the stdlib-only gate policy avoids on non-Windows);
   both Open Design scripts import it; B4 inventory entry un-pinned (gate now
   expects the refactor to have landed).
4. `reports/current` + `design-lab/config/current-report-index.json` rebound to the
   new main tip on merge (this PR).

Not executed (owner-gated): C / D / E / F / G / H / I / J. The larger Tool
Resolution Contract surface that Prompt B also describes is explicitly **deferred**,
not silently done.

## §4 Rollback

- F1/F2 are surgical, additive, and gated by CI: revert = `git revert` of the merge
  commit; B4 gate re-pins the two entries automatically (its drift guard is
  fail-closed in both directions: untriaged new hit FAILs; pinned-but-gone FAILs).
- No branch was created, deleted, or renamed; no remote ref touched.
- `.project-local` and `D:\tmp` are untouched this session.
