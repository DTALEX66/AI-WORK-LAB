# UI_DECISIONS — WORK-LAB Observer 前端升级决策记录

> 按 `01_WORK-LAB_UI开发提示词_CODEX.md`：参考冲突按 B10>B09>…>B01 优先级自动决策，记录于此。
> 视觉唯一真值 = B10 index.html `:root` 变量（与 L4/L7 tokens.json 三处一致）。

## D1 色板：现有 index.css 的 secondary 紫色 → 权威 cyan
- 现状 `--secondary-rgb: 124 108 240`（#7C6CF0 紫）与 light `109 94 240`（紫）= 违规残留
  （CODEX 提示词 §3 禁紫/禁 DESIGN-LAB 紫蓝混入；B10/L4/L7 三处 secondary 均为 #20CDE1）。
- 决策：dark `--secondary-rgb: 32 205 225`（#20CDE1）；light 用 #0E93A5（rgb 14 147 165）保对比度。
- 决策理由：三处权威 token 一致 > 现有实现 > 后续批次。

## D2 背景/表面：GitHub 风 → 深海军蓝控制台
- 现状 `--color-bg:#0d1117 / panel:#161b22`（GitHub 调色板）偏离权威 #050D16/#081420/#0C1B2A。
- 决策：全量替换为 B10 值；新增 `--color-sidebar:#07111C`、`--color-muted:#8EABBC`。

## D3 路由机制：不引入 react-router
- L7 routes.json 是 12 条真实路由，但现有栈无 router 依赖且 lockfile 冻结（冻结 scope，禁新依赖）。
- 决策：沿用 `?view=` 参数 + viewRegistry 扩展 5 条新 lane（rules-policy/audit/approvals/
  integrations/task-packs）。workflow-detail/editor 属执行域（后端无 workflow schema，禁造数据），
  留待 U19 之后的执行契约，本次不做。

## D4 新视图数据源（诚实空态纪律）
| View | 真实数据源（SnapshotV3 字段） | 无数据时 |
|---|---|---|
| rules-policy | `governance.families.{rules,skills,memory,adapters}` | EmptyState"快照未携带治理契约明细" |
| audit | `ci[]` + `executions[]` + `sourceRefs` | EmptyState"无审计记录"，只读禁写操作 |
| approvals | `workspace.plan.approvals`（若存在） | UNKNOWN 说明"审批数据将由审批契约投影" |
| integrations | `governance.families.adapters` + 7 软件 registry 说明文案 | EmptyState |
| task-packs | `tasks` 计数 + `workspace.plan.tasks` | EmptyState |

## D5 主题双套
- dark = 权威 B10 值；light 由本次实施定义（bg #F4F7FA / panel #FFF / primary #1B7FE6 /
  secondary #0E93A5，文字对比度 ≥4.5:1）。token 单一真值 = `src/theme/tokens.ts`（CI 可断言），
  index.css 变量与其同值。

## D6 组件/交互参数（L6 权威）
hover 120-180ms / modal 220ms / drawer 280ms cubic-bezier(.2,0,0,1) / pressed scale .99 80ms /
focus ring 2px offset 2px / toast 4s stack gap 12 / modal backdrop .62 / CommandPalette Ctrl+K /
Esc 关闭 / 断点 tablet 1024 / mobile 767 / 密度 comfortable 68 / default 56 / compact 44。
`prefers-reduced-motion` 降级已存在，保留。

## D7 组件依赖
不新增 npm 依赖。既有 cva/clsx/tailwind-merge/lucide-react + vitest/RTL 足够。（2026-10-25：`recharts` 已从依赖中移除——它在 `src/` 里零 `import`，只是被装着；此句原样保留以免改写当时的决定。）
Modal/Drawer/Toast/CommandPalette 全部手写（L8 可运行原型 `packages/ui-core` 作 API 参考，不照抄）。

## D8 资产边界
`.ui-reference/`（UI套件 提取件）= 设计参考，gitignored，不入 git、不进 dist；产品资产
（logo/图标）如需入源码走 `apps/observer/frontend/public/` 单独评估，本次不动。

## D9 验收
`tsc --noEmit` + `vite build` + vitest 全绿 + 每新 view 冒烟测试 + VISUAL_QA.md（对照 B10/B06/B05）。
检查清单：无 #7C6CF0/紫残留、无 AAOS 金青、无 DESIGN-LAB 紫蓝混入、无 fake KPI、Observer 只读无写按钮。
