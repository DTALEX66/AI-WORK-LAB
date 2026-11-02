# DESIGN-LAB FINAL AUTHORITY CONVERGENCE TASKPACK

**TaskPack ID:** `DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2`  
**Authority:** `DL-AUTHORITY-2026-09-18-R2`  
**Status:** `FINAL_INTEGRATED_REMAINING_WORK`  
**Formal truth target:** `main`  
**Prepared against:** `main@0e9f687ca306226f984f9ac49d222c0d8ff8a1e5`

当前已核实：PR #116 已合并；PR #120 已合并；main protected；Canonical Verify #182 = SUCCESS；#182 artifacts=0；main 尚无 AUTHORITY.md；Workbench main 仍只有 index.html/main.ts/style.css；建立时远端 branches=28（动态 snapshot）。

本包整合 R5、DeepSeek Authority、Branch Convergence、UCR、前后端审计、语言/仓库/Host/Quality/Evidence 历史范围，不创建第二 Ledger/Runtime/Governance。

## A. P0 — 顶层 Authority 落仓与激活

A001 添加 `/AUTHORITY.md`、authority-index、HISTORY-FREEZE-RULES、本 TaskPack。  
A002 修改 root `AGENTS.md`：live remote -> AUTHORITY -> index -> AGENTS -> current TaskPack/Ledger -> live CI -> history。  
A003 接入现有 authority-chain；R5/DeepSeek/Branch-Convergence 只作为前序血统；不新建第二 mutable ledger。  
A004 新增 Authority consistency verifier：文件存在、ID 一致、index current path 存在、AGENTS Authority first、HISTORICAL 不得同时 CURRENT。  
A005 当前 main required checks 未包含 Authority gate；Authority landing 稳定后将其加入 required checks。未来 Workbench gate 建成后也加入。

> 用户本轮已明确授权建立新的顶层 Authority、更新/冻结冲突记录；不应再次因“是否允许修改 AGENTS/Authority 文档”而停住。工具/仓库自身保护机制仍需正常通过。Merge/delete/release 等 destructive action 仍单独受 owner 控制。

## B. P0 — 历史/冲突冻结

B001 给 `docs/handoffs/DESIGN-LAB-UCR-CONVERGENCE-20260918-HANDOFF.md` 首屏加 `HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE / CURRENT -> /AUTHORITY.md`；保留正文作为历史证据。  
B002 全量分类 `docs/taskpacks/`：CURRENT_INTEGRATED / LINEAGE / SUPERSEDED_SCOPE_PRESERVED / HISTORICAL / REFERENCE。  
B003 继续为 active-looking versioned docs 加 HISTORICAL/SUPERSEDED banner 或迁 history；不 mass-delete。  
B004 branch count/open PR/CI 状态一律 live-read，不写成静态 Authority。

## C. CLOSED — 只做 regression guard，不再重做

当前 main 已核实/已落地：ARCHITECTURE 真实树、product-manifest 0.1.0-alpha.0 与当前路径、task-preflight URL/query/import、FA-03、FA-05、report input/tree-digest truth、PR #116 收口。

这些若无新 regression evidence，不得再次作为“待实现 P0”重开。

## D. P0 — Workbench strict TypeScript 产品化

当前 main Workbench 仍只有三个文件。

D001 建立单一 pnpm product workspace；MiniGame Node package 保持 fixture-scoped。  
D002 strict TS：strict/noImplicitAny/strictNullChecks/noImplicitReturns/noFallthroughCasesInSwitch；跨语言 enum 从 schema/generated type。  
D003 先统一 build output contract。历史 WIP 记录了 `dist/main.js` vs Vite `build` vs `.gitignore dist` 矛盾；必须选择一个 build root 并同步 Vite/Python resource lookup/packaging/gitignore/tests/CI。  
D004 `TS source -> typecheck -> Vite build -> packaged Workbench resources`；停止生产路径把 `.ts` 当 `.js`。  
D005 独立 `workbench-gate`：pnpm frozen install/typecheck/Vite/unit/Playwright Chromium/package smoke/clean tree。  
D006 UX 主面：Projects/Brief/References/Research/Directions/Design System/Create/Versions/Review/Preflight/Handoff/Evidence；raw JSON 下沉 Advanced。

## E. P0 — 第一条真正全栈设计 Vertical Slice

实现 `Project -> Brief -> Reference -> Direction -> DesignSystem`，贯通 Workbench/API/contracts/Python creative backend/persistence/version/readback/evidence。

复用 `src/design_lab/creative/`，禁止 creative_v2/new runtime。

每阶段必须有 state/version/hash/owner/evidence/failure state。

## F. P1 — Native production Vertical Slice

`DesignSystem -> DesignIR -> Photoshop/Illustrator -> editable artifact -> readback -> patch/revision -> failure/recovery/rollback`。

Photoshop 只吸收旧 UXP 有价值 residual，不恢复旧目录架构；Illustrator 同样要求原生可编辑与 object/text readback。静态 test 不得称 E3。

## G. P1 — Quality / Jury / Rights / Preflight / Handoff

Automated Assessment 与 Human Jury 分离。支持 Critique -> Apply/Reject -> Revision -> Compare -> Re-score。Unknown rights 不 production-certify。

Preflight 覆盖 dimensions/resolution/color/bleed/fonts/links/rights/editability/BOM/limitations。Handoff 包含 editable source + preview + manifests + provenance + evidence。

## H. P1 — Evidence / CI

H001 main run #182 artifacts=0。如要求 artifact proof，必须真实 `upload -> GitHub API query -> identity -> download/readback -> hash -> run/SHA binding`。  
H002 E3=真实 Host workflow；E4=independent/human；E5=exact release/install/repeatability。  
H003 Authority gate 纳入 main required checks；Workbench gate 建成后纳入 required checks。

## I. P1 — Language 小收口

当前 Ruff 真值 = `CONFIGURED_NOT_ENFORCED`。修 LANGUAGE-POLICY 中仍写 `DECLARED_NOT_ENFORCED` 的残留单句。

是否真正 enforce Ruff 单独决策：pin dev dependency -> uv.lock -> explicit CI -> license/rollback。不要借此重开全语言迁移。

## J. P1 — Branch cleanup

建立时远端 28 branches（动态）。明显的 merged short-lived cleanup candidates 包括：`docs/ucr-handoff-20260918`、`feat/ucr-convergence`、`feat/ucr-p0a-truth`、`feat/ucr-report-truth`、已合并前序 `codex/deepseek-authority-r1`。

删除前仍需 branch tip、open PR/tag/automation/worktree、semantic residual、history preservation、owner authorization。

旧 R4/directory/UXP/S2 branches 继续 semantic equivalence/residual，不 whole-merge。

## K. P1 — Golden Workflows

GOLDEN-001：DESIGN-LAB designs DESIGN-LAB：Brief -> References -> Research -> 3 Directions -> Human Choice -> DesignSystem -> Workbench Implementation -> Browser E2E -> Quality -> Accessibility -> Human Jury -> Preflight -> Handoff。

GOLDEN-002：Professional commercial visual：Brief -> References -> Directions -> DesignSystem -> DesignIR -> Photoshop/Illustrator -> editable artifact -> readback -> patch -> critique -> Human Jury -> preflight -> handoff。PNG-only 不算完成。

## L. P2 — Core 稳定后扩展

UI/UX、Packaging、Spatial/Exhibition、Motion、Video、Audio、3D/VFX、additional hosts/providers。核心 Vertical Slice 未工作前禁止再次“全都支持”。

## M. Permanent anti-drift gates

1. audit 必须 live remote AUTHORITY first  
2. exact SHA 必须写  
3. handoff 永不成为顶层 Authority  
4. history 只能经 index/crosswalk  
5. old TaskPack 不经 mapping 不复活  
6. 不跨 ledger 假算总完成度  
7. E1 不冒充 E3  
8. VLM 不冒充 Human E4  
9. old/candidate PASS 不冒充 current main PASS  
10. commit/branch 数不等于 capability  
11. 不建第二 runtime/backend/ledger  
12. 没用户可见设计进展不得无限扩治理  
13. 禁旧架构回流  
14. merge/delete/release/force-push 保持 owner control  
15. REUSE-FIRST = 真吸收，不是 Registry 堆积  
16. 动态 branch/PR/CI 数永远 live-read  
17. 已关闭问题无 regression evidence 不重开

## N. 固定执行汇报

Authority ID / current main SHA / open PR-head / branch protection / frontend / backend / host / tests-CI / artifacts / evidence level / Human Gate / rights / blockers / predecessor mapping / rollback / branch-worktree / next。

## O. Closeout

Authority/index committed；AGENTS Authority first；历史冲突冻结；Authority gate required。  
Frontend strict TS/build/browser E2E/packaged Workbench/真实设计 workflow。  
Product Brief->Direction->DesignSystem->DesignIR->Host/readback/revision->Jury->rights/preflight->editable handoff。  
E3/E4/E5 必须分别用真实证据。

**END — DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2**
