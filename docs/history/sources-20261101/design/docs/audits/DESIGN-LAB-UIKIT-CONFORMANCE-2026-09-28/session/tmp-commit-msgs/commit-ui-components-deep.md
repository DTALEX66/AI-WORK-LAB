feat(workbench): UI 组件深化 — PreflightIssue + LibraryIndex 的 B07 4 态契约

DESIGN-LAB 专属组件深化（handoff §4 / UI audit §5 backlog 第 3 项，
前置 Slice 2 已落）。按 B07 组件契约 + 提示词 §0「有真实数据协议必须适配它」，
只深化能绑定真实 /api 读回的 2 个领域组件，不造幻影 KPI：

- PreflightIssue（预检 / QA 页，/api/task-preflight）：
  判定改显式 verdict pill（PASS=绿 / BLOCKED=红，颜色+文案双编码，色不作唯一信号），
  元数据（登记/机器/权限）排成一行；零阻塞也如实说「只读预检，不等同质量/rights 验收」。
- LibraryIndex（系统设置页，/api/environment）：
  外置库索引表行加 status pill（DECLARED_NOT_PROBED 等只读态），项目根行加
  可写/只读 pill；表头改「外置库索引」明确红线，UI 绝不暗示可写外部根。

新增 CSS：.pill / .pill-pass / .pill-block / .pill-info / .verdict-line，
全部走 B04 tokens（#060A14 深黑 + Electric Blue #316CFF），无第二套皮肤。

未做（诚实边界，非本轮范围）：QualityScore / ControlMatrix 等剩余专属组件
没有真实 /api 数据源（quality 无端点；控制能力矩阵是 config 文件无路由），
要真实数据视图需先加后端端点 = 后端批，按用户约束「后端延后/并行」暂不动，
避免凭空造数据。

验证（真实执行，非声明）：
- typecheck（tsc -p workbench/tsconfig.json）PASS
- vite build PASS（build/main.js 61.45 kB，较 #141 的 60.72 略增 = 深化增量）
- test:unit（unit.mjs）PASS：build/main.js 无顶层 import/export、vm 执行、路由前缀
- appshell.mjs PASS（12 路由 / 选择器超集 / 未开放页回归）
