# WORK-LAB TOP-LEVEL AUTHORITY

**Authority ID:** `WORK-LAB-AUTHORITY-20260918-V2`  
**Repository:** `DTALEX66/WORK-LAB`  
**Authority level:** TOP / NORMATIVE  
**Preparation baseline:** `main@803268da9dc356fe63f26b3b5405f724bc06b5b9`  
**Frozen pre-cleanup tree:** `606db598abd3724baf6a45ffcfb319f9b0a4d550`

> Every cloud GPT, Codex, Hermes, DSH, reviewer, auditor, or future executor MUST read this file first.
> Historical conversations, taskpacks, handoffs, reports, archived branches and old READMEs are evidence only. They never override current explicit user direction, this document, the project authority index, or current exact-SHA repository truth.

## 1. Mandatory cloud-audit bootstrap

Every WORK-LAB audit MUST execute in this order:

1. Resolve current `origin/main` exact commit and tree.
2. Read `WORK-LAB-AUTHORITY.md`.
3. Read `.project/governance/project-authority-index.json`.
4. Read `AGENTS.md`.
5. Read the CURRENT taskpack referenced by `.project/governance/taskpack-authority-index.json`.
6. Read `taskpacks/current/OPEN-TASK-REGISTER.md`.
7. Read current machine contracts relevant to the audit scope.
8. Only then consult a specifically named historical record or prior conversation when needed.

Forbidden:
- treating an old TaskPack/Handoff/README as current because it says COMPLETE/CURRENT;
- reconstructing a new authority from historical fragments before reading current authority;
- using branch age/commit count as product truth;
- promoting compile/unit/synthetic results into REAL evidence;
- allowing a frozen historical record to overwrite current `main`.

Precedence:

```text
latest explicit user decision
> WORK-LAB-AUTHORITY.md
> project-authority-index.json
> current taskpack / current open-task register
> AGENTS.md + scoped machine authorities/contracts
> current exact-SHA code + CI/runtime readback
> historical conversations/taskpacks/handoffs/audits
```

## 2. Authority hierarchy

Top-level human authority:
- `WORK-LAB-AUTHORITY.md`

Top-level machine authority:
- `.project/governance/project-authority-index.json`

Scoped subordinate authorities:
- `.project/governance/taskpack-authority-index.json`
- `.project/governance/config-authority-index.json`
- `config/config-ownership.json`
- `.project/governance/projects.json`
- `.project/governance/module-ownership.json`
- `.project/governance/project-data-boundary.json`

Current execution plan:
- `taskpacks/current/WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918.md`

Single live open-task register:
- `taskpacks/current/OPEN-TASK-REGISTER.md`

No subordinate file may silently redefine WORK-LAB.

## 3. Project identity

WORK-LAB is the user's **client-neutral AI workflow / Agent Operations / governance / federation control plane**.

It owns:
- cross-software/cross-project workflow coordination;
- Rules, Skills, plugin/MCP declarations and capability policy;
- Task protocol, Task Ledger, receipts, checkpoints, leases and completion authority;
- session/execution federation contracts;
- configuration ownership and safe diff/apply/readback/rollback;
- permissions, risk, budget and approval boundaries;
- telemetry/canonical projections and read-only observability;
- software adapters and update/model/version impact adaptation;
- Universal Workflow handoff and receipt return;
- radar/evolution/security/cleanup control-plane capabilities.

It does NOT own:
- another agent's inference loop;
- user credentials/provider secrets/private auth/browser state;
- a second Agent runtime;
- ArcheAxis knowledge truth;
- DESIGN-LAB design-domain truth/assets;
- external software internals;
- a general chat product.

Open Design client and DESIGN-LAB project are distinct identities.

## 4. Canonical active repository architecture

Current active source surfaces:

```text
packages/client-neutral-core/
packages/contracts/
services/
integrations/
config/
apps/observer/
apps/token-monitor/
scripts/
tests/
.project/
taskpacks/
docs/
```

Legacy active roots such as:

```text
00-governance/
10-workflow/
30-observer/
50-taskpacks/
80-evidence/
90-archive/
```

are historical only and MUST NOT be treated as current.

Project-owned runtime/evidence root:

```text
.project-local/
```

Hermes/Codex/DSH native Homes remain software-owned native locations.

## 5. Governance model

Hard principle: **governance minimization**.

Preferred form:

```text
one global user rule
+ project delta
+ software adapter
+ on-demand skill
```

Do not create duplicate ledgers, duplicate authorities, duplicate sync/publish engines, another Agent runtime, or long-lived shadow-main branches.

One task has one writer. Parallel read-only review is allowed. Parallel writers require isolated ownership/worktrees.

Observer is always read-only.

## 6. Five-dimensional managed-software baseline

Every managed software surface preserves:

1. one canonical official/native entry;
2. working desktop/native entry where applicable;
3. official baseline + user configuration, preserving unknown/user provider/model/auth state;
4. lean non-blocking rules/skills loaded on demand;
5. task-level model policy; provider/model/reasoning follow user-native selection with no global cost/rate clamp by default.

Pricing/usage claims require provider/model/currency/effective_at/source/quality. Missing is UNKNOWN, never fabricated as zero.

## 7. Product frontend/backend architecture

WORK-LAB **has a frontend**.

Normative product direction:

```text
React + TypeScript + Vite
        ↓
Tauri 2 / Rust native desktop shell
        ↓
read-only Runtime Descriptor / Snapshot / SSE
        ↓
Python control plane / canonical store / adapters
```

Production frontend targets:
- `apps/observer/frontend`
- `apps/observer/src-tauri`

`apps/observer/web` is legacy/static compatibility material until parity cutover. It must not remain a second production UI.

Frontend renders backend truth; it must not invent provider prices, FX, quotas, fake zeroes, fixed production ports, or success states.

Token Monitor is a specialist application pending convergence with Observer. Duplicate usage/cost truth engines are not allowed long-term.

## 8. Language architecture

No repository-wide Rust rewrite.

| Layer | Normative language |
|---|---|
| Product UI | TypeScript + React |
| Native desktop/native-sensitive boundary | Rust + Tauri |
| Workflow/config/policy/adapters/orchestration | Python |
| Cross-language truth | JSON Schema |
| Bootstrap only | minimal PowerShell / Shell |

Rust expands only where native APIs, process identity, locking/fencing, IPC/security, packaging, or measured performance justify it.

Every language migration is contract-first, parity-tested, rollbackable, then retires the superseded implementation.

## 9. Configuration truth

Official standard + user state is baseline.

WORK-LAB manages only declared overlay fields. Unknown/user-owned provider/model/auth/runtime state is preserved.

Config write truth:

```text
discover
→ effective config
→ exact diff
→ recovery handle
→ approval when required
→ adapter write
→ native readback
→ verified commit OR honest failure/rollback state
```

Plan ≠ write. Callback return ≠ verified write. Write without readback ≠ verified success.

## 10. Evidence truth

Evidence levels:

```text
NO_EVIDENCE
SIMULATED
SYNTHETIC
INTEGRATED
REAL
```

REAL requires verifiable handle/identity and readback. Empty REAL handle is invalid.

Compile PASS ≠ behavior PASS.  
Unit PASS ≠ integration PASS.  
CI PASS ≠ Windows desktop PASS.  
Synthetic fixture ≠ external project.  
Command construction ≠ native side effect.  
Handler return ≠ completed execution.

UNKNOWN remains UNKNOWN.

## 11. Git/delivery authority

Permanent code authority is `main`.

Normal delivery:

```text
short-lived branch
→ PR
→ exact-SHA CI
→ review where required
→ merge main
→ remove short-lived branch
```

No `r5`, `r6`, `main2`, or long-lived recovery shadow-main.

2026-09-17 branch convergence is historical-complete and must not be reopened.

Direct main push must not bypass required checks.

## 12. Explicit supersession anchors

The following are permanently non-normative unless a future explicit user decision changes them:

- `r4-recovery-exec`, `migration/wl-directory-convergence-r1`, PR #123 and retired long-lived branches;
- MiniGame history is `FOREIGN_HISTORICAL`; ancestry does not make it a WORK-LAB capability;
- project-owned `.hermes/task-runtime`, `.hermes/task-artifacts`, numbered active roots, old `10-workflow`/`30-observer` layouts;
- old broad OpenHuman/Open Design `MANAGE` claims; current scoped ownership governs;
- WLR/NX/R3/R4/Stage2/Stage3/Integrated/Universal/branch-convergence taskpacks as forward authority;
- static Observer web as a long-term second production UI;
- repository-wide Rust rewrite.

## 13. Historical record policy

Historical records are frozen, non-normative evidence.

The default branch must not keep obsolete historical taskpack bodies mixed into `taskpacks/current/`.

Frozen pre-cleanup retrieval anchor:

```text
commit: 803268da9dc356fe63f26b3b5405f724bc06b5b9
tree:   606db598abd3724baf6a45ffcfb319f9b0a4d550
```

A removed historical file remains recoverable as:

```text
803268da9dc356fe63f26b3b5405f724bc06b5b9:<original-path>
```

Cloud GPT audits MUST NOT bulk-search historical corpora by default. Consult history only for a specifically identified question after current authority is read.

## 14. Current unresolved work

The current taskpack owns all remaining work:
- authority reference integrity and main CI enforcement;
- Current-State generator decoupling from Stage3/current historical docs;
- mandatory NF/test discovery;
- repository/path/current-directory convergence;
- React/Tauri production UI convergence;
- endpoint descriptor/SSE/UNKNOWN/null/cost truth;
- Observer Rust CI and Windows E2E;
- Token Monitor convergence;
- Config transaction safety/readback truth;
- REAL evidence binding;
- Durable Inbox/outbox concurrency and exact ACK;
- project isolation and usage/cost attribution;
- session/execution/worker effect truth;
- language architecture and cross-language contract SSOT;
- adapter/skill/model impact-diff adaptation;
- Universal Workflow real external slices;
- final Windows product E2E.

Paid experiments and optional POCs do not block core product convergence.

## 15. Authority change procedure

This file changes only when:
1. the user explicitly changes a project-level decision; or
2. current exact-SHA implementation proves a fact obsolete and the change is accepted through the current taskpack.

Every authority change updates this file, `project-authority-index.json`, and affected current task/open-register records, while preserving the previous version in Git history.
