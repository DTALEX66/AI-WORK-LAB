
## 共享铁律（四个 spec 全部适用）
repo: D:/All projects/WORK-LAB（git-bash；terminal 调用必须 workdir='D:/All projects/WORK-LAB'，
wrapper 形式: python "C:/Users/ALEX/AppData/Local/hermes/bin/hermes-project-data.py" --project . run -- <单命令>；
多命令用 execute_code + subprocess(list args, 无 shell)）。
前端目录: apps/observer/frontend（React18+Vite5+Tailwind3+vitest，node_modules 已装好）。
UI 设计权威（已入项目，gitignored）: .ui-reference/WORK-LAB/
  - 10_B10_最终版高保真可部署UI/  = 视觉最高权威
  - 07_B07_前端开发规范_L7/       = 路由/权限/组件契约/治理规范
  - 04_B04_组件系统与DesignTokens_L4/WORK-LAB_design_tokens.json
  - 06_B06_交互状态系统_L6/WORK-LAB_interaction_tokens.json
  - _meta/WORK-LAB_CODEX_prompt.md = CODEX 任务包（产品定位/视觉硬约束/验收）
## 权威 Design Tokens（B10=L4=L7 三处一致，唯一真值，全部 CSS 变量化）
dark(默认): --color-bg:#050D16 --color-sidebar:#07111C --color-panel:#081420
  --color-panel2:#0C1B2A --color-border:#17435D --color-ink:#EEF6FC --color-muted:#8EABBC
  primary #2A91FF (rgb 42 145 255) / secondary #20CDE1 (rgb 32 205 225)
  success #22C55E / warning #F59E0B / error #EF4444 / info #3882F6
  radius sm4/md10/lg16/xl22 / shadow 0 20px 80px rgba(0,0,0,.35) / blur 18px
  motion fast120 base180 modal220 drawer280 slow(强调)420 pressed80 scale .99
  density comfortable68/default56/compact44
light(由 SPEC-A 定义翻转; 对比度>=4.5:1, primary 加深保对比)
## 视觉硬约束（CODEX 提示词）
深海军蓝控制台质感；禁暖橙/米金/杂志风；禁紫色（现有 index.css secondary=#7C6CF0 是违规残留，
SPEC-A 换成 #20CDE1 cyan）；禁三项目混色；连线可做慢速虚线流动/脉冲；尊重 prefers-reduced-motion。
## 数据契约铁律（现有代码已建立，不得破坏）
快照类型 src/types.ts SnapshotV3：backend 只有 transport/coverage/governance/workspace/projects/
executions/tasks/tokenSummary/git/ci/sourceRefs/software。没有 rules[]/approvals[]/integrations[]/
audit[] 数组 → 相关新页面必须渲染**诚实的 EMPTY/UNKNOWN 态**（页面标题+说明+真实可用数据如
governance family 状态、ci runs、sourceRefs、workspace.plan），禁止编造 KPI/数据。
## 依赖铁律（冻结 scope，不动 lockfile）
不新增任何 npm 依赖（react-router 禁止！沿用现有 ?view= 参数路由机制 + viewRegistry；
recharts/cva/clsx/tailwind-merge/lucide-react 已可依赖）。package.json/package-lock.json 一律不动。
## 验证铁律
每个 spec 完成必须: cd apps/observer/frontend && node node_modules/typescript/bin/tsc --noEmit
(禁用 tsc -b, 避免 tsbuildinfo 并发冲突) 通过 + 自己的 vitest 测试通过
(npx vitest run <你自己的测试文件>)。不要跑 vite build（mainline 最后统一跑）。
## 边界
只改自己 spec 列出的文件；git add 仅限自己新增/修改的文件；不 commit 不 push 不切分支。

# SPEC C — 新页面 Views + 路由注册（12 路由对齐 L7）
你独占: apps/observer/frontend/src/lib/viewRegistry.ts（修改）+ src/views/ 下**新建**的
*.tsx 文件（不得改 MonitoringView/TrustView/SettingsView/AgentsView 等既有 view 的行为，
只能在 Views.tsx 里新增导出如果必须 — 优先新建独立文件）。
新建 views（全部从 types.ts SnapshotV3 取真实数据; 无对应后端字段=诚实空态, 禁编造）:
1. RulesPolicyView.tsx — 数据: snap.governance.families(rules/skills/memory/adapters 的
   current/drift/state)。渲染 4 张 governance family 卡 + state badge + drift 数字;
   无数据→EmptyState"当前快照未携带治理契约明细"。
2. AuditTrailView.tsx — 数据: snap.ci[]（runId/headSha/status/conclusion/sourceRef）+
   snap.executions[] + snap.sourceRefs。只读表(用既有 ExecutionTable 模式或新 DataTable 行渲染,
   不依赖 SPEC-B 的组件 — 直接写 table 样式, 避免跨 spec 依赖): 可筛选(select 状态)、按 runId 排序、
   显示 sourceRef; 空→EmptyState"无审计记录"。禁止写操作按钮。
3. ApprovalsView.tsx — 无后端 approvals[] → 页面说明"审批数据将由 Uxx 审批契约投影" +
   显示 snap.workspace.plan?.approvals（如果存在, 真实渲染）否则 EmptyState UNKNOWN 纪律说明。
4. IntegrationsView.tsx — 无 integrations[] → 显示 governance.families.adapters +
   已知 7 软件 registry 说明文案（只文案, 不造数据）+ EmptyState。
5. TaskPacksView.tsx — 数据: snap.tasks（Record<string,number> 真实计数）+
   snap.workspace.plan?.tasks。渲染 task family 计数卡 + plan tasks 表（若存在）。
注册: viewRegistry.ts 增加 5 条 lane: rules-policy / audit / approvals / integrations / task-packs
（lucide 图标: ScrollText, History, CheckCircle2, Plug, PackageCheck）。保留既有 10 条不动。
验证: tsc --noEmit; 新建 src/views/views.test.tsx: 每个新 view 用最小 fake SnapshotV3 渲染
（断言空态文案出现、断言含真实字段值如 ci runId、断言无编造 KPI: 用 vi.spyOn console 或
 简单断言文本）→ vitest run 通过。
