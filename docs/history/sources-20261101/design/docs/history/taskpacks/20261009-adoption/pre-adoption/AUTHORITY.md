# DESIGN-LAB TOP-LEVEL AUTHORITY

**Authority ID:** `DL-AUTHORITY-2026-09-18-R2`  
**Status:** `TOP_LEVEL_CURRENT`  
**Repository:** `DTALEX66/DESIGN-LAB`  
**Effective date:** `2026-09-18`

> 本文件是 DESIGN-LAB 所有人类、GPT、Codex、DeepSeek、Hermes、CI/Agent 在审计、规划和修改项目时的第一权威入口。

## 0. 云端审计强制启动顺序

每次“审计云端 / 重新审计 / 全量审计 / 检查漂移”必须先读**实时远端仓库**：

1. `/AUTHORITY.md`
2. `/.project/governance/authority-index.json`
3. `/AGENTS.md`
4. Authority Index 指定的当前 Product/Boundary/Architecture 文档
5. 当前 TaskPack 与机器 Ledger
6. GitHub 实时 `main`、Open PR/head、exact SHA、branch protection
7. 最新 CI jobs / artifacts
8. `reports/current/**`（仅在 freshness 校验后）
9. 历史 crosswalk/history（只用于解释血统，不用于覆盖当前权威）

Memory、聊天摘要、handoff、旧 TaskPack、旧 report、branch 名称、commit 数量，都不能单独成为当前 Authority。

每份云端审计必须写明实际读取的 exact SHA。

## 1. 项目身份

DESIGN-LAB 是 **AI-native、Agent-platform-neutral、host-native 的职业视觉设计智能与生产能力层**。

拥有：Brief、ReferenceSet、Research/Methods、Direction、Design System、Design IR、Domain Pack、Quality/Critique/Jury、rights/preflight、Host/Tool/Generator Adapter、editable delivery、BOM、provenance、readback、rollback、evidence。

不拥有：第二 Photoshop/Figma/Blender、通用聊天、通用 Agent Runtime/Model Gateway、WORK-LAB 全局治理、ArcheAxis 长期知识真值、宿主私有数据库。

Open Design = 可选 Host Adapter；MiniGame = game-visual fixture/domain，不是产品线。

## 2. 产品完成语义

能力必须分轴记录：

`CONTRACT / BACKEND / FRONTEND / PERSISTENCE / HOST_OR_GENERATOR / READBACK / QUALITY / RIGHTS / PREFLIGHT / DELIVERY / EVIDENCE`

Backend-only 只能叫 `BACKEND_IMPLEMENTED`，不得叫 `PRODUCT_COMPLETE`。

默认研发单位：

`Workbench -> Contract/API -> Python Design Engine -> State -> Host/Generator -> Readback -> Quality -> Preflight/Handoff`

除真实 blocker 外，不允许连续多个产品 Wave 只扩治理/后端而没有用户可见设计进展。

## 3. 前端权威

DESIGN-LAB **有前端**：`apps/workbench/`。

Workbench 是用户可见设计控制面：Projects、Brief、References、Research、Directions、Design System、Create/Production、Versions、Review/Jury、Preflight、Handoff、Evidence。

它不是第二通用画布。真正原生编辑仍在 Photoshop、Illustrator、Figma、Blender 等专业 Host。

前端技术权威：TypeScript；目标为 strict TypeScript + Vite + pnpm + browser E2E。React/Vue/Electron/Tauri/Avalonia 只有明确需求 + ADR 才可引入。Raw RIR/Patch/Styles JSON 归 Advanced/Developer Mode。

## 4. 后端权威

Python 继续负责 orchestration、runtime/state、creative/design services、providers、reconstruction、QA/preflight、CLI/HTTP、analysis。

优先扩展 `src/design_lab/` 与 `src/design_lab/creative/`，禁止创建平行 v2 runtime，也不进行 Rust/C#/Go/Java 全仓重写。

## 5. Host/Tool 权威

Adapter 生命周期：`probe -> prepare -> execute -> observe/readback -> failure/recovery -> rollback`。

Adobe 继续使用 host-native JSX/UXP。静态 Adapter 存在只能证明 E1，不等于真实 Host E3。

## 6. Evidence 权威

- E0 DECLARED
- E1 STRUCTURAL
- E2 CONTROLLED_RUNTIME
- E3 REAL_WORKFLOW
- E4 INDEPENDENT_ACCEPTANCE
- E5 RELEASED/REPEATABLE

历史证据不能自动提升新的 SHA/Host/Adapter/Tool 版本。

## 7. 仓库责任

- `apps/`：runnable frontend
- `src/design_lab/`：Python runtime
- `packages/`：可复用能力/协议
- `integrations/`：Host/Tool/Model/Agent 边界
- `design-lab/`：内容/config/schema/domain/eval/production/template/test，**不是第二 Runtime**
- `fixtures/`：fixture/regression
- `research/`：intake/research
- `vendor/`：审阅后的最小第三方来源
- `docs/`：current authority + history
- `reports/`：projection/evidence index，低于 live code/CI
- `scripts/`：repo tooling
- `.project/`：tracked policy/governance
- `.project-local/`：唯一 active runtime/state/cache/artifact/log root

`.hermes` 不是 DESIGN-LAB 活跃写入根。禁止为了目录好看做全仓暴力搬迁。

## 8. 语言权威

- Python >=3.11：backend/runtime/QA/provider/reconstruction/CLI
- Canonical CI 可用 Python 3.12
- TypeScript：Workbench/Web/IPC/MCP client
- Host-native JS/JSX/UXP：宿主自动化
- JSON/JSON Schema：跨语言 contract truth
- SQL/SQLite：local state
- Shell/PowerShell：thin launcher
- Rust：NOT_PRIMARY，仅 benchmark + ADR 后的有界性能 helper

当前 Ruff 事实：`CONFIGURED_NOT_ENFORCED`。下层文档中仍写 `DECLARED_NOT_ENFORCED` 的单句属于 stale wording，应修正但不改变本 Authority。

## 9. REUSE / Source / Rights

原则：REUSE-FIRST / OPEN-SOURCE-FIRST / PLUGIN-FIRST / LOCAL-FIRST WHEN POSSIBLE。

第三方来源最终必须进入：`ABSORBED / REFERENCE_ONLY / REJECTED / DEFERRED`。

登记不等于吸收。ABSORBED 必须有 source/revision/license/mapping/destination/implementation/tests/evidence/rollback。Unknown rights 不得 production-certify。

## 10. Branch 权威

收口后 `main` 是唯一长期正式代码真值。FINAL/AUTHORITY/R4/MIGRATION 等 branch 名称没有天然权威。

历史 diverged branch 按语义分类：`ABSORBED / PARTIAL_ABSORBED / REIMPLEMENT / SUPERSEDED / HISTORICAL_ONLY / REJECTED / ACTIVE_RESIDUAL`。

禁止因为 unique commits 直接 whole-merge 旧 R4 governance、directory migration 或 UXP branch。

Merge/delete/release/force-push 仍属于 owner-authorized destructive actions。

## 11. 历史记录权威

所有审计必须服从 `/.project/governance/authority-index.json`：

`CURRENT / CURRENT_BUT_DRIFTED / PROJECTION / SUPERSEDED / HISTORICAL / REFERENCE / NON_AUTHORITATIVE`

**Handoff 永远不是顶层 Authority。** 它只记录时间点执行状态，后续 merge/branch/CI 可立即使它过时。

`docs/handoffs/DESIGN-LAB-UCR-CONVERGENCE-20260918-HANDOFF.md` 明确分类为 `HISTORICAL_EXECUTION_RECORD`；即使文件自己写“tracked 权威交接”，也不得覆盖本 Authority。

未来 GPT 不得因为某个旧文档更详细，就拿它重建当前架构。

## 12. 执行血统

顶层 Authority：本文件。

保留血统：
- `DL-TP-20260908-R5`：产品血统
- `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1`：结构/治理前序
- `DL-TP-20260917-BRANCH-CONVERGENCE-R1`：分支收口前序

本轮统一剩余任务入口（落仓后）：
`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`

旧任务 ID 必须经 crosswalk/current-capability 映射后才可执行。

## 13. Authority 建立时的云端已核实基线

实时读取到：`main@0e9f687ca306226f984f9ac49d222c0d8ff8a1e5`。

已核实：
- PR #116 已 MERGED；旧 head `fc4aa0f775c102d18365c386fe712b42fd9d018a` 不再是当前产品真值
- PR #120 已 MERGED 到当前 main
- main 已 protected
- main 当前 required checks 包含 Python、MiniGame、generated-artifact、license/secret、Open Design structural；**未包含 DeepSeek Authority gate**
- Canonical Verify `35289564056` / #182 对 `0e9f687ca306226f984f9ac49d222c0d8ff8a1e5` = SUCCESS
- run #182 Actions artifacts = 0
- 当前 main 尚无 `/AUTHORITY.md`
- 当前 `AGENTS.md` 仍把 2026-09-14 DeepSeek 包写为 current DeepSeek authority
- 当前 `apps/workbench/` 仍只有 `index.html / main.ts / style.css`
- 建立 Authority 时实时远端 branch 数 = 28（仅 snapshot，永远不得作为静态权威）

以后必须重新实时读取这些动态事实。

### 13.1 动态事实的最新 live 读回（不是 Authority 变更，是对 §13 快照的刷新）

> §13 是 **Authority 建立时**的历史快照，保留原文不改写。以下为**重新实时读取**的结果，
> 用于避免读者把 §13 的旧值当成当前事实。动态事实**永远以每次审计的 live 读回为准**。

- 观察时间：`2026-09-27`；观察 exact SHA：`634071f3c8ffa87e08fa1386f49c185ff6fa36d8`（`main` = `origin/main`）
- main required checks = **9 项**（`gh api /repos/DTALEX66/DESIGN-LAB/branches/main/protection` 实读）：
  Python gate、MiniGame node gate、Generated-artifact clean-tree gate、License & secret hygiene gate、
  Open Design host adapter gate、Top-level Authority consistency gate、Workbench strict-TS product gate、
  Workbench browser E2E、DeepSeek authority gate chain
  （相对 §13 的变化：**已包含** DeepSeek Authority gate，并新增 Workbench strict-TS 与 Workbench browser E2E）
- 远端分支数 = **1**（仅 `main`）；open PR = **0**（§13 建立时为 28）
- `apps/workbench/` = **10 个文件**（§13 建立时仅 `index.html / main.ts / style.css`）
- 最近合并：PR #173（`2026-09-27T14:40:41Z`）→ #172 → #171 → #170 → #169
- 以上仅为该时刻读数；下一次审计必须重新 live-read。

## 14. 已关闭且禁止无证据重开的事项

当前 main 已核实：
- ACTIVE `ARCHITECTURE.md` 已对齐当前真实目录
- product-manifest version 已对齐 `0.1.0-alpha.0`
- Product Definition / Boundary 路径已修
- `/api/task-preflight` 已使用 URL parser + 正确 `.runtime` import
- FA-03 report-truth、FA-05 zero-spill 已在 UCR 收口并应以 regression guard 维护
- current-report truth 已改向 input/tree-digest 语义

这些属于 `CLOSED_WITH_REGRESSION_GUARD`，不得继续当成待实现 P0 重做。

## 15. 当前剩余工作

### P0 — Authority/防漂移 [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
> 全部 9 项已在 main 落地（逐项证据见下），不得再作为待实现 P0 重做。
> 守卫：`scripts/verify_top_level_authority.py`（CI `canonical-verify.yml` 第 116 行）+ main required check
> `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)`。
1. 落仓 `/AUTHORITY.md` — CLOSED（本文件；R2 byte-pin `49e21069…`）
2. 落仓 authority-index — CLOSED（`.project/governance/authority-index.json`）
3. 修改 `AGENTS.md`，Authority 强制第一读 — CLOSED（`AGENTS.md` MUST READ FIRST；verifier check `agents-authority-first` PASS）
4. 落仓统一最终 TaskPack — CLOSED（`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`）
5. 分类/冻结所有 active-looking 历史文档/TaskPack/Handoff — CLOSED（index `historicalGlobs` + `historicalSpecific` + `taskpackClassificationRule`）
6. 将 PR #120 Handoff 首屏明确标为 HISTORICAL/NON_AUTHORITATIVE — CLOSED（`docs/handoffs/DESIGN-LAB-UCR-CONVERGENCE-20260918-HANDOFF.md` 首屏 banner）
7. 接入现有 authority-chain，不建第二 ledger — CLOSED（`scripts/deepseek_authority_chain.py` + `reports/current/DEEPSEEK-AUTHORITY-CHAIN.json`）
8. 新增 Authority/index consistency verifier — CLOSED（`scripts/verify_top_level_authority.py`，10 checks）
9. main required checks 加入 Authority gate — CLOSED（gh 读回 main protection：含 `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)`；该门禁落地时为 7 项，截至 §13.1 观察时点为 9 项）

### P0 — Frontend [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
> 守卫：main required check `Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)` + `git diff --exit-code -- apps/workbench/build` + `design-lab/scripts/verify_workbench_packaging.py`。
- strict TypeScript product workspace — CLOSED（D003：`apps/workbench/main.ts` strict TS）
- pnpm 单一产品依赖真值 — CLOSED（`pnpm-workspace.yaml` + `pnpm-lock.yaml`）
- Vite build — CLOSED（`apps/workbench/build/main.js`，构建产物受 `git diff --exit-code` 守卫）
- browser E2E — CLOSED（`workbench-browser-e2e` job + `design-lab/tests/e2e/browser_design_layer_e2e.mjs`；P0-G 已加入证据 JSON 与 artifact 上传）
- 独立 Workbench CI gate — CLOSED（main protection 含 Workbench strict-TS gate；截至 §13.1 观察时点 required checks 共 9 项）
- built resources 正确 package — CLOSED（pyproject force-include + P0-H wheel 隔离安装态完整纵切验证）
- 默认 UI 不再 JSON-centric — CLOSED_WITH_REGRESSION_GUARD（Workbench 面板/选择器交互；**残留**：无人工视觉验收记录，属 E4）

### P0 — 第一条全栈设计 Vertical Slice [CLOSED_WITH_REGRESSION_GUARD 2026-09-20]
`Project -> Brief -> Reference -> Direction -> DesignSystem` 已贯通 Workbench/API/Python backend/state/readback/evidence：
E-SLICE-01（PR #123/#124）+ 不变量修复（Reference 资产校验、DB 级单选择不变量、`constraints` 对称序列化、`active_binding` 跟随当前 chosen、方向级 partial unique index）。
守卫：`design-lab/tests/test_design_layer_http.py`（18 用例）、浏览器 E2E、`verify_workbench_packaging.py`。
**残留**：Reference → DesignIR → 可编辑产物链路未接入；真实 Host E3 / 人工 E4 未做（见下 P1）。

### P1 — Native production / quality / delivery
- DesignSystem -> DesignIR -> Photoshop/Illustrator
- editable artifact/readback/patch/recovery
- Automated Quality 与 Human Jury 分离
- Rights/Preflight/Handoff
- real Host E3
- independent/human E4

### P1 — CI/Evidence
- 如需要 artifact proof，必须真实 upload/query/download/hash — 部分 CLOSED（`workbench-browser-e2e` 已真实上传浏览器 E2 证据 JSON + 失败截图：固定 SHA 的 `upload-artifact` + `if-no-files-found: error`）；其余 release claim 仍须逐项证明
- run #182 无 artifact，不能冒充 artifact readback — 保留（记录性事实，非待办项）
- 修 LANGUAGE-POLICY 中残留 `DECLARED_NOT_ENFORCED` 单句 — CLOSED（tracked `docs/architecture/LANGUAGE-POLICY.md` 已无该串；`verify_top_level_authority.py` stale-wording check 守卫）
- Ruff 是否真正 enforce 单独决策，不重开全语言迁移 — OPEN（决策未做）
- Workbench gate 建成后加入 required checks — CLOSED（main protection 已含 Workbench strict-TS gate；截至 §13.1 观察时点 required checks 共 9 项）

### P1 — Branch cleanup
实时重读 branch。合并后的 UCR 短分支与旧 candidate 进入 cleanup candidate；旧 S2/S3 继续 semantic residual/equivalence 检查。远端删除仍需 owner 授权。

## 16. 未来 GPT 云端审计协议

1. fetch live main
2. fetch open PR/head
3. fetch AUTHORITY
4. fetch authority-index
5. fetch AGENTS
6. fetch current TaskPack/Ledger
7. fetch latest CI/artifacts
8. fetch branch protection
9. compare to Authority
10. history only via index/crosswalk
11. report exact SHA(s)
12. never memory-only current state

## 17. Authority 修改规则

修改本 Authority 必须有：owner intent、reason、superseded rule、impact note、repository commit、authority-index update、必要 CI/readback。

**END — DL-AUTHORITY-2026-09-18-R2**
