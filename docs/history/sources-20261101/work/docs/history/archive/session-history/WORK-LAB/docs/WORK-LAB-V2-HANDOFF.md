# WORK-LAB v2 handoff

**Repository:** `DTALEX66/WORK-LAB`
**Authority:** `WORK-LAB-HERMES-TASKPACK-v2.0.0`
**Current branch:** `main`
**Canonical positioning:** `00-governance/PROJECT_POSITIONING.md`

## One-sentence project identity

WORK-LAB is a v2 monorepo control plane for client-neutral AI workflow governance, Open Design production knowledge, and strictly read-only evidence observation; it is not an agent runtime, product platform, or fourth product.

## Only active canonical modules

| Module | Path | Boundary |
|---|---|---|
| Workflow-assistance | `10-workflow/workflow-assistance` | Client-neutral workflow governance, contracts, task control and delivery boundaries |
| Open Design | `20-design/open-design` | Open Design-first design knowledge, visual quality, production handoff and provenance |
| WORK-LAB Observer | `30-observer/work-lab-observer` | Strictly read-only derived events, projections, reports and evidence |

`30-products/minigame` is retained as product history, fixture/reference material and archive evidence. It is not an active v2 canonical module. No merge, deletion, platform selection, real-device validation or commercial claim is implied.

## Published implementation and verification

- Workflow continuity/ledger, core schemas, adapter registry and seven-interface conformance are implemented locally and pushed.
- Open Design benchmark registry, fail-closed verifier and MINIGAME design domain pack are implemented; current evidence is isolated/local unless explicitly marked otherwise.
- Observer schema, skeleton verifier and read-only runtime are implemented; this does not claim full Tauri UI, live clients, budgets or production projection integration.
- Contract catalog: `20` contracts / `20` schemas.
- Error ledger: `17` sanitized entries, counts consistent.
- MiniGame local product gate: `321/321 PASS`; this is product-local evidence only.
- GitHub Actions exact-SHA run `31091566287` passed Workflow, Open Design, Observer, Integration and Aggregate on the preceding code baseline. A later documentation commit requires its own CI readback.

## Open or approval-gated work

| Area | Current boundary |
|---|---|
| Hermes live | `WAITING_APPROVAL`; no live apply, reload, global skill/config or provenance mutation |
| Workflow | Growth discovery/promotion, Git/GitHub delivery reconciliation and large-module split remain incomplete |
| Observer | Full Tauri UI, real Client/Git/CI projections, budgets, quality-state persistence and failure isolation remain incomplete |
| Open Design | Dual MINIGAME fact-source migration, full master-method cards, human calibration, license decision and product acceptance remain incomplete |
| MINIGAME | Duplicate-source resolution, platform choice, real-device/platform lifecycle, advertising and commercial experiments remain blocked/pending decision |
| Integration | Second reference client and final cross-module acceptance remain pending |
| Token Monitor | Real npm/Tauri build, installer, signing and release are not claimed |

## Evidence language

`LOCAL_PASS`, focused/isolation evidence, exact-SHA GitHub Actions, Hermes live, real-device/platform, license, commercial and release evidence are separate claims. A local or isolated PASS never promotes an unverified live/release task.

## Recovery / continuation order

1. Read this file, `00-governance/PROJECT_POSITIONING.md`, `00-governance/projects.json`, `50-taskpacks/TASKPACK_SUMMARY.md` and the v2 reconciliation.
2. Confirm `git status --short --branch`, `git rev-parse HEAD` and `git ls-remote origin refs/heads/main`.
3. Run the affected module gates and root aggregate gate from the repository root.
4. Read the latest GitHub Actions run for the exact pushed SHA; do not reuse historical CI output after a later commit.
5. Keep live Hermes, destructive/archive decisions, real platforms/devices, license choices and commercial experiments as separately approved tasks.

## Safety boundary

Do not read or publish credentials, `.env`, auth stores, browser data, prompt/response bodies, private keys, tokens or session databases. Do not access `E:\`. Keep generated evidence under ignored `.hermes/` or `80-evidence/`. Preserve the single-writer rule and never overwrite the independent MINIGAME fact source without an explicit decision.
