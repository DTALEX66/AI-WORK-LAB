# CROSSWALK — 2026-09-24 云端审计（RAW）× live `cb9c3ca` 活核对

> Authority: `/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`) + `.project/governance/authority-index.json` (v2, `TOP_LEVEL_CURRENT`)
> Observed main SHA: `cb9c3ca68a4eb0a12436b719668b16aa09def600`（live `origin/main`，2026-09-24 核对）
> RAW 存档：`docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-24-RAW.md`（NON_AUTHORITATIVE）
> 本文件 = RAW 的事实核对 + 可执行拆解；**不**在 ingest 同一 PR 内执行其任务清单。

## 1. 事实核对（RAW 声称 → live 实测 → 判定）

| # | RAW 声称 | live 实测（`cb9c3ca`） | 判定 |
|---|---|---|---|
| F1 | main = `cb9c3ca` | `origin/main` = `cb9c3ca68a…` | ✓ 一致 |
| F2 | 11 visible branches（10× `codex/*` + main） | 实际 **10** branches，**0 个** `codex/*`（`feat/adapter-locator-audit-b4`、`feat/ci-artifact-proof-h001`、`feat/comfyui-e3`、`feat/evidence-append-only-b5`、`feat/quality-record-schema-b3`、`feat/ucr-activation`、`fix/design-lab-governance-closure-r4`、`fix/r4-h3-prod-e3`、`fix/registry-quarantine-sync`、`main`） | ✗ 分支表整体不符 |
| F3 | 分支表含 `codex/add-csp-csp-router`@`b7b71745…` 等 10 条 | `git ls-remote origin` 无 `codex/*`；`git cat-file -e b7b717456373…` 对象不存在（本地库无此 SHA）；表内个别 SHA（如 `f3c7ed33…`）为真实历史 commit（#143 workbench），但对应分支名为 RAW 侧拼接 | ✗ 分支表为跨环境/幻觉层，**不得继承其"已验证"表述** |
| F4 | open PR = `#149 feat(ai): add declarative ai utilization registry`（head `codex/add-ai-utilization-registry`） | live `#149` = **G-3/B3 封死的 per-artifact QualityRecord schema + 校验器 + CI gate**，head `feat/quality-record-schema-b3`，OPEN，9/9 required 全绿 | ✗ PR 身份不符（RAW 读错仓态或跨仓） |
| F5 | 机器治理层"无机器可读索引" | `.project/governance/authority-index.json`（v2，status=`TOP_LEVEL_CURRENT`）**已存在**且由 "Top-level Authority consistency gate"（9 required 之一）持续校验 | ✗ 已闭 |
| F6 | "path-drift-check 不存在" | `design-lab/scripts/verify_project_drift.py` 存在，但**仅**语言/产品漂移（DL-GOV-130：default-host 措辞、E0/E1 过度声明）；**路径引用漂移检查器确缺**（AGENTS/authority 文档/`paths.json`/`external-assets-index.json` 的 path 引用是否全部命中 tracked 文件，无 CI 校验）；且 `verify_project_drift.py` 本身**未接入 CI 聚合器** | ◑ 部分属实（真缺口 = 路径引用校验 + drift 检查器接 CI） |
| F7 | "无统一环境/工具链注册" | `.project/paths.json` + `docs/LOCAL_ENVIRONMENT.md` + `reports/current/MACHINE_INVENTORY.json` + `external-assets-index.json` + `model-radar.json` **均已存在**；AGENTS.md「模型与工具」已载明"本机外置根以 `.project/paths.json` 为准"、"更新以官方发布为准，不私自打包" | ✗ 已闭；**残留真缺口** = 无 machine-readable `allowAutoInstall=false` 策略字段 + 无 CI 断言 |
| F8 | "无当前集成 TaskPack" | `docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`（`DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2`）= AGENTS.md 唯一 current integrated TaskPack | ✗ 已闭 |
| F9 | 需新建 `EvidenceEnvelope v2` | evidence 合同族已存在（`evidence-record`、`evidence-attestation`、`release-evidence`、`capability-evidence`、`run-receipt`、`operation-receipt` schema）；`verify_evidence_cards.py` B5 已接 CI（#151） | ✗ 不建第二并行系统（反漂移）；真残留 = **Host E3 逐宿主资格数据**（owner-gated，DECLARED） |
| F10 | Workbench UI 缺 Preflight 面板/token 库/host 面板 | **误报（本 CROSSWALK 初版 grep 了不存在的 `apps/workbench/src/`）**：live workbench 是扁平 `apps/workbench/main.ts`（1489 行，8 视图：dashboard / brand-systems / **preflight** / settings / **projects** / creative-tools / **deliverables** / **evidence**），全部绑真实 `/api`（`/health`、`/projects`、`/design-systems`、`/task-preflight`、`/environment`、`/projects/{id}/design-layer`），禁幻影 KPI 纪律写死在代码注释（"读回判定，非统计猜测"）。重造 = 违反反漂移规则 7 | ✗ 已闭（误报）；残余 BOM/rollback/token 库视图：后端 32 条动态路由无对应 `/api` 端点，先建 UI = 幻影 KPI，不立项 |

## 2. 判定（按域）

- **机器治理 / 环境注册 / TaskPack / 证据合同**：RAW 的 P0-T1、P0-T3、P1-T2 大部分 **已被仓内既有设施闭合**（F5/F7/F8/F9）；RAW 基于过时/跨环境仓态。
- **真缺口（agent 授权结构层）**：
  - **G-A（P0-T2 旗舰）**：权威文档路径引用漂移校验器 + 接 CI（fail-closed）。
  - **G-B**：`verify_project_drift.py`（DL-GOV-130）接 CI 聚合器。
  - **G-C**：`paths.json` machine-readable 安装策略（`allowAutoInstall=false` + 官方源约束）+ CI 断言。
  - **G-D**：Host adapter 逐宿主资格矩阵数据（对既有 `readiness-host-matrix.schema.json` 填充 + 校验；E3/E4 腿 = DECLARED，不 EXECUTE）。
  - **G-E（误报纠正）**：审计主张"Workbench UI 缺 preflight/evidence/项目库面板"**不成立**——8 视图已全在仓且绑真实 `/api`（见 F10 修正）；残余 BOM/rollback/token 库视图因后端无对应 `/api` 路由而不立项（先建 UI = 幻影 KPI）。
- **owner-gated（保留任务文档，不执行操作层）**：真实 Host E3 / Human Jury E4 / 商业视觉链 E5 数据腿 / 模型 H3 live / 分支删除 / `#149` 手动合并。

## 3. 执行批次（agent 授权结构层，顺序 = 反漂移优先级"先闭合结构缺口"）

| 批次 | 内容 | 交付 | 实际落地 |
|---|---|---|---|
| **PR-A（#152）** | RAW + 本 CROSSWALK + rebind 投影 | 拆解入账，**不**执行任务清单 | ✓ 合入 `5fd9253` |
| **PR-B（G-A + G-B + G-C 捆绑 #153）** | `scripts/verify_path_refs.py`（GA-1 门：AUTHORITY.md/AGENTS.md 路径引用全命中 + 机器安装策略 `.project/governance/path-ref-policy.json` + DL-GOV-130 接 CI 自举）+ `.project/governance/path-ref-policy.json` + 12 单测 + `top-authority-gate` 接线 | fail-closed 路径漂移门禁 + 环境策略机器化 | ✓ 合入 `80b2ddc` |
| **PR-C（#154）** | `design-lab/scripts/verify_readiness_host_matrix.py`（GD-1 门：复用 `readiness-host-matrix.schema.json`，8 宿主 E1 矩阵 fail-closed 消费者面，jsonschema + stdlib 兜底双路）+ `verify_design_lab.py` 聚合器 +1 项 + 14 单测 | 宿主资格矩阵数据面 | ✓ 合入 `b81c28b` |
| **PR-D（原 G-E，否决）** | ~~Workbench UI 批次~~ | F10 误报纠正 + 幻影 KPI 纪律 | ✗ 不立项 |

**执行规则**：每 PR 独立、合并后 main-tip 9/9 required 全绿再开下一 PR；owner-gated 腿在任何 PR 中只写 DECLARED receipt，不 EXECUTE；`#149`（B3）保持 user-managed 不动。

## 4. 风险矩阵（采纳 RAW 评估，执行判定修正）

| 风险 | RAW 判定 | 本 CROSSWALK 修正 |
|---|---|---|
| Path Drift | 高危 | 确认为**当前最大结构风险**（F6）→ G-A 旗舰直接处置 |
| Host 漂移 | 中 | 降为中低：宿主为 Adapter 非运行依赖（ADR-001），E3 腿 owner-gated → G-D 数据面即可 |
| 模型漂移 | 中 | 高→中：`model-radar.json` + `external-assets-index.json` + doctor 已存在；残留 = 安装策略机器化（G-C） |
| UI 扩张 | 中 | **降级（F10 误报纠正）**：8 视图已全在仓且绑真实 `/api`；残余 BOM/rollback/token 库视图因后端无端点而不立项（先建 UI = 幻影 KPI） |
| 权限扩张 | 中 | 维持中：不新建并行系统；EvidenceEnvelope 诉求并入既有合同族 |

## 5. Rollback 预案

- PR-B（#153，G-A/B/C）：门 + 策略 + 测试均为 additive；revert 单 commit 即还原（CI `top-authority-gate` 的两步删除）。不影响既有 9 required 检查。
- PR-C（#154，G-D）：验证器为 additive（聚合器 `verify_design_lab.py` 删 1 行即还原）；不影响既有 9 required 检查。
- PR-D（G-E，否决）：无落地文件，无 rollback。

## 6. 不采纳项（RAW 提议但否决）

1. 新建 `docs/authority/authority-index.yaml` — 与既有 `.project/governance/authority-index.json`（v2 + CI gate）构成第二 ledger → 反漂移规则否决。
2. 新建 `EvidenceEnvelope v2` 并行系统 — 既有证据合同族 + B5 校验器已覆盖语义 → 否决，仅 G-D 数据面。
3. 按 RAW 分支表清理 `codex/*` 分支 — 该表不存在于 live 仓（F2/F3）→ 无对象可操作；分支清理仍走 owner-gated 既有台账（`reports/current/BRANCH-CLEANUP-CANDIDATES.json`）。
4. Workbench UI 重建批次（RAW P1 使用层诉求）— F10 误报纠正后无对象可建；残余 BOM/rollback/token 库视图须**先**有后端 `/api` 路由才立项（禁幻影 KPI），当前 32 条动态路由面无对应端点 → 不立项。

## 7. 执行终态账（截至 main `b81c28b`）

| 项 | 状态 | 落点 |
|---|---|---|
| G-A 路径引用漂移门禁 | **CLOSED**（`scripts/verify_path_refs.py` 10 项 fail-closed + 12 单测 + CI 接线） | #153 → `80b2ddc` |
| G-B DL-GOV-130 接 CI | **CLOSED**（`top-authority-gate` + GA-1 自举锁死，拆线即 FAIL） | #153 → `80b2ddc` |
| G-C 机器安装策略 | **CLOSED**（`path-ref-policy.json`：allowAutoInstall=false / officialReleaseOnly / E 盘保护 / 双索引一致） | #153 → `80b2ddc` |
| G-D 宿主资格矩阵消费者面 | **CLOSED**（`verify_readiness_host_matrix.py` 7 类不变量 + 14 单测 + 聚合器接线） | #154 → `b81c28b` |
| G-E Workbench UI 批次 | **REJECTED**（F10 误报纠正：8 视图已全在仓；BOM/rollback/token 视图无后端端点，不建幻影 UI） | 本 PR §1/§2/§6 |
| E3 真实 Host / E4 Human Jury | **owner-gated，DECLARED 不 EXECUTE**（矩阵 `verification.state=NOT_VERIFIED` 由 G-D 门锁死假声明） | 不动 |
| G-7 H001 415 / G-9 / G-10 | 用户停车项，未动 | 不动 |
| `#149`（G-3/B3） | user-managed 合并（9/9 全绿就绪） | 不动 |

**agent 授权结构层收口 = main `b81c28b`**；本 PR 之后无 agent-autonomous 结构项剩余。
