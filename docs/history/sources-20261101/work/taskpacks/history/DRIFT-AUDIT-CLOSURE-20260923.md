# WORK-LAB DRIFT AUDIT — 2026-09-23 (closure ledger)

> Read-only audit of every authority index, external index, path, doc, handoff,
> summary and summary surface that can drift; executed classification into
> FREEZE / MIGRATE / REBIND / KEEP / PRUNE. Scope: u17 (audit branch).
> Anchor: main=803268d, u17=dc6dea5. No merge without user "合并".
> Evidence tier: LOCAL-STRUCTURAL PASS (verifiers) + git-rename audit.
> CI exact-SHA readback for this batch: PENDING.

## 1. Branch audit (audit-then-merge)
| branch | state | verdict |
|---|---|---|
| main (origin) | 803268d, protected by ruleset 23825562 (aggregate exact-SHA) | KEEP (single trunk) |
| u17/global-agent-policy-20260918 | 493be49→dc6dea5, local=remote, ahead main 55→56 | AUDIT BRANCH (all V2+drift work folds here) |
| canonical/main | stale remote-tracking ref, remote `canonical` already deleted | PRUNED (kept as tag `canonical-main-stale-d3f1f23` for recovery) |

- 远端仅 main + u17，单写者模型保持。canonical 孤儿 ref 已 update-ref -d，SHA 由 tag 保留。

## 2. Authority index drift (5 machine indices)
| index | drift found | action |
|---|---|---|
| external-libraries-index.json | 4 D: external-lib targets — ALL EXIST | KEEP (no drift) |
| cross-module-source-index.json | source_of_truth pointed at DESIGN-LAB `opendesign-assistance/` (deleted in DESIGN-LAB restructure) | REBIND → `design-lab/research/global-absorption/SOURCE_REGISTRY.json` (verified exists + tracked in DESIGN-LAB d9e2d46+) |
| config-authority-index.json | capsule-registry / telemetry-authority / federation-protocol = status PENDING (WLR-030/050 planned) | KEEP as honest PENDING (planned, not drift) |
| project-authority-index.json | coherent (single CURRENT + register + allowlist paths) | KEEP |
| taskpack-authority-index.json | re-baselined in 6fd51d9 (main_note unmerged-lane fix) | KEEP |

- 40 cross-module refs describing DESIGN-LAB internal structure (scenarios/, evals/, knowledge/...) are cross-repo descriptors with no local entity — NOT in-repo drift, by design.

## 3. Historical doc convergence (frozen + migrated)
| surface | moved | refs rebound |
|---|---|---|
| taskpacks/current/ → taskpacks/history/ | 18 files (08-10~09-14 handoffs/closures superseded by 09-18 UPC taskpack) | 0 exact-path refs (verified pre-move) |
| docs/current/workflow-assistance/{audit,handoffs}/ → docs/history/archive/workflow-assistance/ | 12 dated audit + handoff files | README 12 refs + test_workflow_governance 3 refs (L2301/L3078/L3079) + yaml self-ref 2 = 17 rebinds, all re-pointed |
| taskpacks/current/ (kept LIVE) | 8 authority-pinned files (OPEN-TASK-REGISTER.md, UPC-20260918, BRANCH-RETIREMENT-LEDGER, error-ledger, HERMES-UPDATE-AND-FIXES, README, V2-REPORT, RECONCILIATION.json) | untouched |
| docs/current/workflow-assistance/workflow/ | kept in current (build_context_pack.py + tests pin the LIVE subtree) | drift noted, not migrated (rebind surface too broad this pass) |

MASTER-2.0-APPROVAL-PACKAGE.md (taskpacks/current) is FUNCTIONALLY CONSUMED, not drift:
`workspace_evidence.py` reads it via the `PLAN_PATH` constant and `test_render_v3.js`
registers it as `evidenceKind: "PLAN"` — both live code that require the file at
`taskpacks/current/`. Classification: KEEP-LIVE. Do NOT migrate to history/
(moving it would break the PLAN evidence contract the observer render gate asserts).
The 2 references stay as-is; rebind is only ever needed if that contract changes.

## 4. Data spill tracking (re-verified)
- forbidden E: / F: — 0 access, 0 footprint ✅
- `.project-local/` run-roots compliant (runs/artifacts/quarantine), quarantined = restore-class KEEP
- `.hermes/task-runtime` + `.hermes/task-artifacts` — HOOK-ESCAPE landings → **now declared** as `secondaryRuntimeRoots` in project-data-boundary.json (declaration-vs-reality gap closed; slimmable caches only)
- 本批 before/after: `.hermes/task-runtime` 96MB→0.7MB (pycache/uv/node-compile caches reclaimed, all regenerable)

## 5. Project slimming
- Reclaimed 518.4 MB earlier (Rust debug build 423MB + pycache 65MB + uv 27MB + node 2.5MB)
- `.project-local/` now 2.72GB (quarantine 2.43GB is restore-class, kept per user rule; of which 1.6GB is regenerable node_modules — slimmed only on explicit request)
- CURRENT_STATE timestamp churn: discard on every gate run (no re-commit)

## 6. Verifier readback (LOCAL-STRUCTURAL PASS)
- verify_project_authority_reference.py: PASS
- verify_three_project_boundary.py: PASS (splits=6 markers=5 seams=3)
- test_workflow_governance: Ran 98 OK (skipped=5)
- authority + boundary + cross-module JSON: valid

## 7. Merge chain status (fold-into-audit-branch done; merge GATED)
- All drift work folded into u17 (audit branch) ✅
- **RESOLVED 2026-09-23 (CONVERGED):** U19 re-qualified as R5 headless-session environment boundary (NOT a code bug); headless-conditional verdict `SKIPPED_HEADLESS` landed in 9f57ca3. work-lab-gate @b993e9c 5/5 SUCCESS (incl. observer SKIPPED_HEADLESS exit 0), aggregate green at ruleset 23825562 → gate cleared. User authorized "合并" → u17 merged to main via PR #127 (squash) at 62f666e. Post-merge authority revalidation via PR #128 (taskpack index baselineRevalidation re-pinned + V2 acceptance addendum). Real-Desktop WebView2 E2E remains a known-external layer (needs a real desktop/self-hosted runner), out of scope on hosted CI by design.

## 8. Drift prevention (why large-scale drift stops now)
- Every authority index now resolves (0 dead in-repo refs)
- current/ surfaces contain only LIVE authority-pinned files; frozen evidence lives in history/
- boundary declaration matches runtime reality (secondaryRuntimeRoots added)
- stale remote ref pruned; single-write model enforced
- P2 surfaces CLOSED by mainline takeover (free pool 3x 503-dead):
  * docs/current/workflow-assistance/workflow/ (37 files): 10 KEEP-LIVE
    (code/authority-pinned), 2 NO-REF, 25 PROSE-ONLY; 9 dated-archive + 2 no-ref
    = 11 P3 candidates ENUMERATED but NOT moved (README doc-index rebind surface
    too broad — 治理最小化; see .project-local/runs/drift-scan-sa.md)
  * taskpacks/current/ re-verify: 0 unclassified residuals (12 root files all
    KEEP-classified; universal pack intact)
  * knowledge-staging provenance: "mismatch" = by-design indexing difference
    (yaml keys on name+sha256; files are content-addressed hash names) — recorded
    to prevent a future false-positive alarm
- MASTER-2.0 rebind: RETIRED as P2 — file reclassified KEEP-LIVE (functional PLAN evidence contract, §3 above). quarantine node_modules slim: P3, on request.

## 9. SA-2 legacy 8-digit re-audit (mainline takeover, post-freeze)
- HEAD tree: `10-workflow`/`30-observer`/`40-knowledge`/`50-taskpacks`/`80-evidence`
  all ABSENT (directory convergence confirmed) ✅; `90-archive` = HISTORY_ONLY
  (BOUNDARY.md + 15× reports-history/2026-09-05, no active owner)
- 149 files mention legacy 8-digit strings; classified:
  * 89 in frozen dirs (90-archive/docs-history/taskpacks-history) — historical, untouched
  * ~60 narrative-only (AGENTS.md, error-ledger entrypoints, taskpack prose) — description
    of the pre-convergence layout, not live pointers, untouched
  * 4 needing decision:
    - tests/ci/test_project_authority_reference.py L148 `50-taskpacks` = NEGATIVE CONTROL
      (asserts verifier rejects forbidden-root reactivation) — CORRECT, kept
    - WORK-LAB-AUTHORITY.md L114-125 + project-authority-index forbiddenActiveRoots
      = forbidden-roots declaration — CORRECT, kept
    - data-ownership.yaml legacy_aliases `80-evidence` = historical mapping doc — kept
    - RECONCILIATION.json:26 `worklab_root` stale D:/.../10-workflow path = frozen 09-17
      observation record (file is authority-pinned) — documented, not modified
  * 2 LIVE DRIFT fixed in this pass:
    - asset-routing.yaml route `generated-evidence: ignored-80-evidence` → now routes to
      .project-local/artifacts (canonicalEvidenceRoot) + legacy-alias comment
    - .gitignore dead rule `80-evidence/` removed (dir absent on disk, verified)
  * authority verifier + 3-project-boundary verifier: PASS; 17 negative-control tests OK
