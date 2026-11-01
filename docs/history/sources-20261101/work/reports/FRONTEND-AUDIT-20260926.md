# WORK-LAB 前端功能真实性侦查审计（2026-09-26 · 第二批侦察交付）

> 对象：`apps/observer/frontend`（WORK-LAB 主产品前端，15 个一级 lane → 规划 7 项一级导航）。
> 方法：主线程源码级只读侦查（子代理 free 通道 503 不可用，未依赖）。全部结论带 文件:行 铁证。
> 纪律：只读审计，未修改任何前端代码，未 commit/push 前端改动。

## 0. 结论摘要（先说结论）

1. **数据层 REAL**：前端唯一数据源 = sidecar v3 snapshot API（`/api/v1/snapshot` + SSE `/api/v1/events`），
   后端权威投影在 `packages/client-neutral-core/scripts/snapshot_api.py::build_snapshot`
   （`apps/observer/frontend/src/lib/api.ts:1-9, 83-91` fetchSnapshot；`api.ts:105-139` SSE；
   `api.ts:300-371` useLiveSnapshot 首 poll + SSE + 诚实纪律：无数据=UNKNOWN，不伪造 agent/模型/成本/资源）。
2. **构建/运行 REAL**：`node_modules` 已装；本地实测 `tsc -b` rc=0 + `vite build` 1598 模块
   → 237 kB js / 22 kB css，1.77 s（2026-09-26 10:15 本机铁证，非声称）。
3. **测试 REAL**：本地 `npx vitest run` 实测 8 文件 / 47 测试全通过（api 8 / viewRegistry 5 /
   views 10 / truth 5 / components 5 / a11y 5 / tokens 6 / App.smoke 3）——真断言运行，无假绿。
4. **15 lane 逐个定级：0 个写死 mock、0 个 TODO 占位、0 个假完成**。全部为**真实 snapshot 字段的
   只读投影**；3 个后端投影缺口（approvals[] / software[] / workspace.plan.tasks）**全部在代码里
   显式 UNKNOWN（UnknownState/EmptyState），如实披露，不是假绿**（各视图头部注释自我声明）。
5. **交互全部真实**：Sidebar 折叠/分组/mobile 抽屉、Ctrl+K 命令面板、审计筛选/排序、
   URL deep-link（?view=/theme=/layout=）均为真实状态机，无 console.log 式伪交互。
6. **导航现状 vs 目标**：Sidebar 现 4 组（概览/执行/洞察/治理，`Sidebar.tsx:28-33`），
   P1-D 架构定义 7 项一级（`docs/decisions/WORK-LAB-LITE-AND-PARALLEL-WORKSPACE-ARCHITECTURE.md:77-87`：
   Home/Work/Agents/Projects/Governance/Integrations/System）→ **15→7 是纯 IA regroup，
   不加一级执行/审批/写操作**（Observer 永久只读，§8）。

## 1. 逐 lane 定级（5 级证据：REAL / REAL-FIXTURE / LOCAL / SYNTHETIC / UNSUPPORTED）

| # | lane (id) | 组件 | 数据源（snapshot 字段） | 数据可得性 | 定级 | 铁证 |
|---|---|---|---|---|---|---|
| 0 | overview（合成落地页） | App.tsx KPI+ExecTable+ProjectPanel+TokenPanel | projects / executions / tokenSummary / transport | sidecar 运行时有数据；无=UNKNOWN | **LOCAL**（运行数据）代码 **REAL-FIXTURE** | App.tsx:169-202, 184-191 |
| 1 | agents | AgentsView | snap.projects（平台/活动/执行/token/git 真值表） | 真 registry | **LOCAL** | Views.tsx:36-85 |
| 2 | executions | ExecutionsView | snap.executions + transport 水位 + tasks 桶 | 真 | **LOCAL** | Views.tsx:88-144 |
| 3 | models | ModelsView | tokenSummary + projects[].token（仅质量标签，不算 $） | 真 | **LOCAL** | Views.tsx:147-195 |
| 4 | memory | MemoryView | governance.families（rules/skills/memory/adapters）+ workspace.history | families 真投影；history 依赖 workspace 投影 | **LOCAL**（families）/ **REAL-FIXTURE**（history 缺口时 UNKNOWN） | Views.tsx:198-229; snapshot_api.py:218+ |
| 5 | tools | ToolsView | executions[].workingArea + governance.families | 真 | **LOCAL** | Views.tsx:232-247 |
| 6 | monitoring | MonitoringView | transport（永不伪造 LIVE）+ coverage | 真 | **LOCAL** | Views.tsx:250-266 |
| 7 | delivery | DeliveryView | snap.git（local/remote/ci SHA + matchState）+ snap.ci[] | 真 | **LOCAL** | Views.tsx:269-292; snapshot_api.py:79-95 |
| 8 | trust | TrustView | tokenSummary.costQuality + transport + coverage + sourceRefs | 真 | **LOCAL** | Views.tsx:295-316 |
| 9 | settings | SettingsView | window.__OBSERVER_CONFIG__ + transport + revision/schema | 真 | **LOCAL** | Views.tsx:319-340 |
| 10 | rules-policy | RulesPolicyView | governance.families（CLEAN/DRIFT/UNKNOWN + drift 数） | 真投影；无明细→EmptyState | **LOCAL** | RulesPolicyView.tsx:39-96 |
| 11 | audit | AuditTrailView | snap.ci[] + snap.executions + sourceRefs | 真；筛选/排序=真实本地 view state（非写操作） | **LOCAL** | AuditTrailView.tsx:40-144, 45-81 |
| 12 | approvals | ApprovalsView | workspace.plan.approvals（**快照当前未携带 approvals[]**） | **投影缺口**：显式 UnknownState，无 approve/deny 按钮（只读纪律自我声明） | **REAL-FIXTURE**（代码真）数据 **UNSUPPORTED**（缺口如实） | ApprovalsView.tsx:1-5, 18-21, 50-53 |
| 13 | integrations | IntegrationsView | governance.families.adapters（真）+ 7 客户端**静态文档块**（明确标注"文档·非实时状态"，不伪造健康度） | adapters 真；静态文档=产品事实 | **LOCAL**（adapters）+ **REAL-FIXTURE**（静态文档，标签诚实） | IntegrationsView.tsx:1-23, 46-63, 77-84 |
| 14 | software | SoftwareView | snap.software（仅后端提供时携带；LOCATION_DRIFT/DUAL_INSTALLATION 如实显示不伪装 Healthy） | **投影缺口**：后端未 wire 时 UNKNOWN by design，"不自动迁移/删除" | **REAL-FIXTURE**（代码真）数据 **UNSUPPORTED**（缺口如实） | SoftwareView.tsx:1-7, 50-64; snapshot_api.py:97 |

定级说明：
- **LOCAL** = 代码真实 + 数据路径真实（数据可得性取决于 sidecar 是否在跑；本机 dev 走
  `http://127.0.0.1:61867` 非权威 static-preview，`api.ts:67-76` 显式 `authoritative:false`，不冒充生产真值）。
- **REAL-FIXTURE** = 代码/契约真实，但数据源尚未由后端携带，UI 显式 Unknown/Empty（**这是诚实设计，不是 mock**）。
- **SYNTHETIC**（合成假数据）：**0 个**。全仓 views/components 无写死假数据、无 TODO 占位、
  无未接 handler；唯一静态数据块（IntegrationsView GOVERNED_CLIENTS）是受治理客户端的**产品事实文档**，
  标注"文档·非实时状态"，合规。
- 防假绿机制在测试里：`truth.test.tsx`（5 测试）+ `views.test.tsx`（10 测试）专门验证
  UNKNOWN/EmptyState/OFFLINE 行为。

## 2. 构建 / 运行 / 测试 铁证（本机 2026-09-26 实跑）

- `package.json` scripts：`dev`=vite / `test`=vitest run / `build`=tsc -b && vite build / `typecheck`=tsc --noEmit。
- 依赖齐全（react18/vite5/vitest2/tailwind3/recharts/lucide；devDeps 含 RTL + jsdom）；`node_modules` 已安装。
- `npx tsc -b --noEmit` → **rc=0**；`npx vite build` → **1598 模块，dist 237.13 kB js + 22.14 kB css，1.77 s**。
- `npx vitest run` → **Test Files 8 passed / Tests 47 passed**（1.76 s 运行，非声称）。
- 可用但**未发布**（区分铁律）：前端可 build/dev 实测可用；"已发布"需 Tauri 壳 + tag + 安装回读（本轮不涉）。

## 3. 15 lane → 7 一级导航聚合草案（P1-01，严格对齐 P1-D §3.1，纯 IA regroup）

目标 7 项（P1-D L78）：`Home / Work / Agents / Projects / Governance / Integrations / System`。

| 一级入口 | 折叠二级（全部 15 lane 保持可达，P1-B 契约无数据丢失） | 依据 |
|---|---|---|
| **Home** | overview（落地页 KPI + 执行表 + 项目面板 + Token 面板） | P1-D L78 |
| **Work** | executions（含 tasks 桶 L134-140）· task-packs · delivery | P1-D L84：Work→Tasks/Executions/Task Packs/Delivery |
| **Agents** | agents（agent 实例视图） | P1-D L78 |
| **Projects** | projects 面板（现折叠在 AgentsView L36-85 的"项目平台"表） | P1-D L78 把 Projects 提为一级；viewRegistry L42-43 已记录"Projects 折叠"决策，本草案把它独立 |
| **Governance** | rules-policy · approvals · audit · trust（Evidence=sourceRefs，现 trust L308） | P1-D L85：Governance→Rules & Skills/Approvals/Audit/Trust/Evidence |
| **Integrations** | integrations（adapters 族 + 静态客户端文档） | P1-D L78 |
| **System** | software · models（含 Usage 面板）· monitoring · memory · tools · settings | P1-D L86：System→Software/Models/Usage/Settings；monitoring/memory/tools 为扩展二级（"示例"可扩） |

实施面（仅 IA，不动数据/写操作）：
- `Sidebar.tsx:28-33` GROUPS 4 组 → 7 组（二级折叠）；`viewRegistry.ts` 不动 id/lane 稳定契约（U04 deep-link 不破坏）；
- 命令面板（App.tsx:80-111）items 按 7 组 regroup；CompactHUD / TopStatusBar 不动；
- **零新增执行/审批/重试/apply/rollback 能力**（§8 只读铁律）；`?view=` 机制保留（D3 决策）。

## 4. 第二批执行建议（下一步）

1. P1-01 nav7 regrouping = 纯 IA 变更（Sidebar GROUPS + palette 分组 + Projects 独立面板），
   验收：7 一级入口 + 15 lane 全可达 + `tsc/vitest/vite build` 本地全绿 + CI observer 组绿。
2. 时序依赖：#135（P0-02/03/04）先合 main → P1-01 短命分支基于新 main 开（§26 顺序 P0→P1）。
3. 投影缺口三项（approvals/software/plan.tasks）属**后端 sidecar 契约扩展**，不在 P1-01 范围；
   保持 UNKNOWN 现状即合规，不伪造。

---
*证据索引：本审计全部 文件:行 引用可逐条回读；build/test 命令输出为本机 2026-09-26 实跑（非 CI 声称）。*
