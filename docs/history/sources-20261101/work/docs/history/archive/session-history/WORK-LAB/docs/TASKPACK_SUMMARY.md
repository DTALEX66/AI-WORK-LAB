# Task-pack summary

WORK-LAB is the global project-workflow control plane plus two canonical
active modules. The root task-pack system owns task scope, writer/reviewer
boundaries, evidence contracts, recovery and cross-module integration; it does
not own a fourth product implementation.

The active module registry is authoritative:

- `10-workflow/workflow-assistance` — client-neutral workflow governance;
- `30-observer/work-lab-observer` — strictly read-only observation and evidence.

Open Design was transferred to `DTALEX66/DESIGN-LAB`; the one-time
pointer and migration evidence are retained under `90-archive-manifests/` and
ignored `.hermes/` artifacts.

`30-products/minigame` is product history/fixture/archive material, not an
active v2 canonical module. See `00-governance/PROJECT_POSITIONING.md`.

Historical migration/governance snapshot (not the current attachment task-pack
completion state):

- `HIST-MIG-001..HIST-MIG-008`: historical migration evidence, recoverable
  bundles, dirty-state preservation, candidate and collision records.
- `HIST-GOV-001..HIST-GOV-008`: historical governance evidence for root layout,
  instruction precedence, contracts, CI and privacy-safe evidence.
- The old `MIG-*` and `GOV-*` names are deliberately namespaced as `HIST-*` in
  this active summary because the attached task-pack reuses some IDs with
  different acceptance criteria.

Current forward authority:

- **Tracked forward authority**: `00-governance/PROJECT_POSITIONING.md` plus the
  machine-readable `00-governance/config-authority-index.json` (single-source
  inventory). Both resolve from a clean clone.
- **Candidate execution blueprint (LOCAL_CANDIDATE, not yet tracked)**:
  `WORK-LAB-FINAL-MASTER-EXECUTION-TASKPACK-R6-2026-08-15.md` lives under the
  ignored `.hermes/desktop-attachments/` path; it becomes the tracked forward
  authority only after user approval writes it under `50-taskpacks/` and this
  summary records its blob SHA, base SHA and approval record.
- Tracked graph: `50-taskpacks/WORK-LAB-STAGE-3-TASK-GRAPH.json` (28 tasks,
  5 waves, `initialState=RECONCILE_REQUIRED`).
- Baseline: `00-governance/generated/STAGE3_BASELINE.json`.
- The former Stage 3 handoff and delivery manifest are
  `SUPERSEDED / HISTORICAL` evidence; PR #33 is a `STAGE3_FOUNDATION_SLICE`,
  not a claim that WL3-000..WL3-820 are complete.
- Machine-readable delivery manifest:
  `50-taskpacks/WORK-LAB-STAGE-3-CONTROL-PLANE-CODEX-DELIVERY.json`.
- Stage 2 and the v2 attachment/reconciliation are historical predecessor
  evidence. They are `SUPERSEDED` for forward execution and cannot restore the
  old three-module architecture or active design gates.

## Historical Master TaskPack v2.0 local snapshot (2026-08-10)

The following was the 2026-08-10 local snapshot. It is historical evidence and
does not prove the current checkout, exact-SHA CI, publication, or release:

```text
VERIFIED_LOCAL:                      26 (WL3-000..710, 800/810)
BLOCKED (toolchain):                  1 (WL3-620 Windows portable: cargo/rustc absent)
LOCAL_VERIFIED_READY_FOR_APPROVAL:    1 (WL3-820 approval package)
RECONCILE_REQUIRED:                   0
```

Historical local evidence reported by that batch:

```text
Full quality-gate verify sequence: 21 gates PASS
  governance 443 tests OK (skipped=4) · runtime-convergence 91 tests OK
  compile/security/schemas/adapters/ACL/OTel/usage/memory/ledger/portable/shell/pwsh PASS
Observer: Python 57 tests OK (incl. canonical projection + events retirement)
          JS 43 passed, 0 failed
Browser visual acceptance: console_messages=0 js_errors=0 (dark dashboard)
Real dual-project canary: WORK-LAB + MINIGAME (collector + SSE LIVE frame)
Swap drills: 6/6 core-not-forked
Repo size audit: tracked=438 files, 2.65 MiB, duplicate groups=1
WL3-800 integration gate: 6/6 checks passed
CURRENT_STATE freshness: PASS (head 699ab50, branch main, CI run 31344245919)
```

Remaining external gates are explicit and unclaimed:

```text
exact-SHA CI of this batch        PENDING (not pushed)
Windows portable EXE build        BLOCKED (Rust/Tauri toolchain approval)
release / live apply / paid smoke PENDING_HUMAN_APPROVAL
commit / push / PR                PENDING_HUMAN_APPROVAL
```

The single approval package is `50-taskpacks/WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md`.

The historical delivery summary and error record (ERR-018..ERR-023) for this
batch is `50-taskpacks/WORK-LAB-MASTER-2.0-DELIVERY-SUMMARY-2026-08-10.md`;
the current machine-readable error ledger is `50-taskpacks/error-ledger.json`
(36 entries through ERR-036).

Evidence generated under the ignored local `.hermes/task-artifacts` path is not
published as source content. The committed handoff records reproducible source
tips, module paths, recovery locations and remaining approval gates. Hermes
global config, auth, sessions, cron, skills, plugins and caches remain platform
state and are never absorbed by a task pack.

## Stage 3 contract reconciliation (2026-08-11)

`WORK-LAB-STAGE3-CONTRACT-RECONCILIATION-2026-08-11` repairs ERR-024..ERR-036
across the root control plane, Workflow-owned runtime/configuration contracts,
and the strictly read-only Observer projection. The tracked CURRENT_STATE no
longer embeds checkout/CI identity; exact checkout facts belong to ignored
runtime attestation. Local verification is recorded separately from exact-SHA
CI, publication, release, live/global apply and paid-provider evidence.

Local implementation verification for this reconciliation: Workflow canonical
quality gate 20/20 PASS (489 governance tests, 4 declared skips); Observer
Python 45/45 PASS; Observer UI/component 43 + 4 PASS; CURRENT_STATE freshness
PASS. The root publication suite is PARTIAL because its exact-tree test requires
a committed clean checkout; commit/push and remote exact-SHA CI remain pending
separate approval.

## Local deployment smoothness (2026-08-11)

`WORK-LAB-LOCAL-DEPLOYMENT-SMOOTHNESS-2026-08-11` closes the project-local
runtime wiring gaps found during a real load: the worker CLI now registers the
explicit project and runs the standard collectors, the Sidecar observes
cross-process canonical writes and publishes real SSE deltas, and Observer uses
a Windows read-only PID query with validated dynamic loopback endpoints. Static
desktop entries start UNKNOWN and may become LIVE only through a discovered
read-only endpoint.

The local stack is deployed under ignored `.hermes/task-runtime/` state with
dynamic loopback ports. Readback is `PASS`: Sidecar `ok/LIVE`, canonical
integrity `ok`, Observer `ok/readOnly/LIVE`, one registered project, and no
SQLite/WAL metadata change across ten Observer GETs. Current regression totals
are Workflow focused 6 + 3 PASS, canonical Workflow quality gate PASS, Observer
Python 47/47 PASS, and Observer UI/component 44/44 PASS. The root suite remains
publication-partial at 71/72 because an uncommitted checkout is intentionally
not an exact clean tree.

Native Tauri compilation is `NOT EXECUTED`: this machine currently has neither
Rust/Cargo nor MSVC Build Tools. Global Codex/Hermes apply, commit, push,
exact-SHA CI, publication and release remain explicit external gates and are
not inferred from the working local runtime.

## Hermes / DeepSeek handoff (2026-08-11)

The executable remaining-work packet is
`50-taskpacks/WORK-LAB-HERMES-DEEPSEEK-HANDOFF-2026-08-11.md`. It freezes the
current checkout identity, local verification, Hermes managed-asset deployment
boundary, Codex user-overlay write set, native Tauri prerequisite/build gate,
and Git/exact-SHA delivery contract. It explicitly excludes provider auth,
sessions, credentials, tokens and prompt/response bodies. Hermes real-Home
managed assets were deployed to `C:\Users\admin\AppData\Local\hermes` after
exact authorization; atomic apply and ActionPlan readback passed, independent
hashes matched, the rollback backup was preserved and `config.yaml` remained
outside the deployment. Codex overlay, native Tauri build, Git delivery and
exact-SHA publication remain pending gates.

## Historical local predecessor slice (`SUPERSEDED`)

`WL-300` is locally implemented as an offline model/context/cost policy
contract. It uses capability classes instead of permanent model or provider
IDs, enforces context overflow fail-closed behavior, keeps unknown cost as
`UNKNOWN_COST` rather than inventing a zero value, and allowlists numeric usage
fields while excluding prompt/response bodies and credentials.

- Contract: `10-workflow/workflow-assistance/schemas/workflow/model-policy.schema.json`.
- Evaluator: `10-workflow/workflow-assistance/scripts/workflow/model_policy.py`.
- Tests: `10-workflow/workflow-assistance/tests/test_model_policy.py`.
- Local evidence: `.hermes/task-artifacts/wl300-model-policy.json` (ignored).
- Scope: local and fixture-only; no live provider, credential, prompt body,
  Hermes live apply, commit, push, PR, merge, release, or paid-provider smoke.

`WL-400` now adds memory-layer metadata, explicit candidate quarantine, manual
promotion boundaries, and report-only rule-drift projection. Memory and rule
content bodies are not stored; only digests, layer/state metadata, and redaction
flags are retained. Evidence is `.hermes/task-artifacts/wl400-growth-watch.json`
and remains ignored.

`WL-500` now projects normalized Token Monitor usage summaries through the
strictly read-only Observer event store. The adapter accepts only explicit
non-negative usage integers, excludes model IDs and raw log/prompt/response
content, and exposes aggregate input/output/total/record counts in the
rebuildable Observer projection. Evidence is
`.hermes/task-artifacts/wl500-observer-usage.json`; no live log was read and no
external or authoritative state was mutated.

`WL-600` is retained only as historical predecessor evidence. Its visual
benchmark cards, human-calibration language and design verifier are not Stage 3
WORK-LAB Gates and do not represent an active module or current capability.
No visual score or human review was fabricated.

`WL-720` is retained only as a historical non-destructive size/duplicate audit
across predecessor scopes, the preserved MiniGame fixture, and archive
manifests. The proposal recorded five scopes and 23 duplicate content groups; every group
is manual-review-only, and the archive proposal retains both the fixture source
and its manifest. Evidence is `.hermes/task-artifacts/wl720-audit-proposal.json`.

## Current successor and Observer component status

The successor attachment
`.hermes/desktop-attachments/WORK-LAB-STAGE-2-ABSORPTION-INTEROPERABILITY-HERMES-TASKPACK.md`
has been reconciled and completed through `NX-720`.

The tracked reconciliation is
`50-taskpacks/WORK-LAB-STAGE-2-ABSORPTION-INTEROPERABILITY-HANDOFF.md`.
It records the two-module boundary, the strictly read-only Observer, explicit
publication/live/paid-provider approval gates, and the remaining
`PENDING_HUMAN_APPROVAL` release state.

The current Observer visual/desktop component implementation is documented in
`50-taskpacks/WORK-LAB-OBSERVER-VISUAL-ASSETS-R2-STATUS.md`. It records the R2
brand asset intake, fixed Tauri Full/Compact windows, GET-only projection
boundary, test evidence, corrected implementation errors, and the explicit
Rust/Tauri portable-build limitation.

The completed ordered successor queue is:

```text
NX-000 → NX-100/NX-110 → NX-200/NX-210 → NX-300/NX-310/NX-320
→ NX-400/NX-410 → NX-500/NX-510/NX-520 → NX-600
→ NX-700/NX-710/NX-720
```

The queue does not add a fourth active module, a second Observer UI, another
Task Ledger/runtime, a memory service, an Agent/chat product, or a default
cloud/paid provider. Commit, push, PR, merge, release, live/global apply,
paid-provider smoke, real-device validation, human visual calibration, and the
portable Windows artifact remain separately evidenced gates; none is inferred
from a task-pack summary alone.

## 2026-08-12 status update

- **PR chain (all merged to main, local==remote)**: #51 stage3 continuation +
  Codex overlay + native Tauri; #52 workspace active-project discovery +
  Observer canonical render fix; #53 delivery summary/error ledger/handoff;
  #63 local-config claim corrections; #64 managed-assets doc drift fix; #65
  skill absorption (12->13 skills).
- **WL3-620 native Tauri closed**: rustc 1.88 toolchain (contract floor),
  EXE + MSI + NSIS bundles, install/uninstall cycle verified, Release
  v0.1.0-native-observer.
- **Workspace discovery (user requirement)**: active_projects.py scans the
  user-specified total workspace (D:\All projects), registers every Git
  project, marks ACTIVE when a workflow agent is running with fresh evidence.
- **Observer live chain verified**: canonical store -> sidecar SSE -> dashboard
  (mode=LIVE), browser-verified full/compact views.
- **Skill absorption**: observer-delivery (new), windows-development += MSYS
  interop, self-improvement += config comparison, safe-project-execution +=
  risk-tiered model. Local apply/verify PASS (13 skills).
- **Active handoff**: 50-taskpacks/WORK-LAB-HERMES-HANDOFF-2026-08-11-FINAL.md
  (supersedes DEEPSEEK + EVENING variants).
- **Standing gates**: commit/push/PR/release/live-apply remain per-action
  authorized; WL3-820 formal release PENDING_HUMAN_APPROVAL; error-ledger 42
  entries contract-verified.
