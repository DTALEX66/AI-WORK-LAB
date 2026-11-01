# DESIGN-LAB 参考源清单（DESIGN_LAB_REFERENCE_MANIFEST）

权威顺序：B10 > B09 > B08 > B07 > B06 > B05 > B04 > B03 > B02 > B01

## 解包提取（scratch 工作区）

| 批次 | 文件 | SHA-256 | 大小 | 用途 |
|---|---|---|---|---|
| B10 | `index.html` | `bcecffe937fe…` | 39,288 B | **最终视觉权威** |
| B09 | `interactive-demo.html` | `68a5bb004578…` | 21,032 B | 交互趋向权威 |
| B08 | `app/src/App.tsx` | `db255b536a2e…` | 4,537 B | React+TS 工程参考 |
| B07 | `routes/routes.json` | `c3b5c8c9a820…` | 958 B | 路由 + 权限 + 状态机权威 |
| B05-L5 | ZIP（12 张高保真页） | `bcb2eb2e9956…` | 1.14 MB | 页面视觉细节 |
| B04-L4 | ZIP（16 组件 + tokens） | `4be8aff0a6d8…` | 1.58 MB | 组件 + Design Tokens |
| B06-L6 | ZIP（18 交互状态） | `473ce4043507…` | 110 KB | 交互状态系统 |
| B02-L2 | ZIP（36 VI+UI 细节） | — | 1.8 MB | Logo/Fibonacci/VI |

## B07 工程包（权威结构来源）

- `routes/routes.json` / `routes.ts`：12 路由（含 `/projects/:id`）
- `routes/navigation.ts`：primaryNav（排除 `:id`）
- `pages/page-map.json`：每页 states（loading/empty/error/permission/ready）
- `theme/tokens.json`：色值（#060A14 / #316CFF / #4BAFFF 等）
- `shared-ui-core/component-registry.json`：30+ 组件契约
- `permissions/permissions.json`：6 角色 × 9 域权限
- `state/domain-state-machine.json`：brief→research→designing→review→qa→approved→delivered→archived
- `docs/acceptance-checklist.md`：14 项验收清单
- `docs/frontend-architecture.md`：模块 + 角色 + 响应式断点

## B10 最终版视觉系统（决定最终视觉）

- 色：`--bg:#060A14` `--sidebar:#090E1A` `--surface:#0D1221` `--surface2:#11182A`
- 主色：`--primary:#316CFF`（Electric Blue）`--secondary:#4BAFFF`
- 状态：`--success:#2FC58D` `--warning:#F4B942` `--error:#F05252`
- 几何：`--radius:18px` `--radius-sm:12px` `--blur:18px`
- 光效：ambient radial-gradient + 面板内高光 + KPI 发光文字 + 侧栏选中渐变 + 扫光 sweep
- 响应式：`≤1160px` 2列 `≤840px` 单列 + 侧栏隐藏

## B05 高保真页（12 张，决定页面细节）

01 仪表盘 / 02 项目 / 03 项目详情 / 04 研究洞察 / 05 品牌系统 / 06 设计领域 /
07 创作工具 / 08 预检QA / 09 交付中心 / 10 证据系统 / 11 团队协作 / 12 系统设置

## B01/B02 Logo 构造（黄金比例 + Fibonacci）

- VI/03_主标志_Primary_Logo.png：D + L + Frame + Canvas + Grid + Bezier + Golden Ratio
- VI/04_横版图标单色反白.png：Monochrome + Reverse 变体
- VI/05_黄金比例Fibonacci构造.png：螺旋构造线
- VI/06_网格构建_Grid.png / VI/07_安全空间 / VI/08_错误用法

## 工程落点（真实仓库）

- `apps/workbench/`：Vanilla TS + Vite（**非** React）
- `shell.ts`：B07 12-route AppShell + B10 视图渲染器
- `style.css`：B04 tokens + B10 视觉层
- `main.ts`：mount guard + 真实 API 绑定
- `workbench.ts`：API + 项目/任务/事件/资产
- `design.ts`：Brief/Direction/DesignSystem 设计层
- `contracts.ts`：严格 TS 类型（无 any）
