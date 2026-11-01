# DESIGN-LAB Workbench 状态矩阵（13 面 × 6 态）

**日期**：2026-10-07 · **Authority**：`DL-AUTHORITY-2026-09-18-R2`
**基线 SHA**：`316b0562`（#258 并入后）
**范围**：`apps/workbench/shell.ts` / `workbench.ts` / `contracts.ts` 与 `src/design_lab/http_service.py`
**性质**：只读盘点。本文不含改动；改动另开 PR 并在此登记。

六态定义：① 无 token / 离线 ② 请求返回 HTTP 错误 ③ 成功但集合为空
④ 加载中 ⑤ 返回形状与 UI 预期不符 ⑥ 真实数据。

## 先说结论：三条结构性事实

1. **没有共享的 JS 状态组件。** 只有 CSS 类 `.view-loading` / `.view-hint` /
   `.view-unopened` / `.error` / `.empty`，每个视图各自 `el(...)` 手搓。
   `.empty` 实际只出现在两处（picker 未选体与 `setListNotice`）。
2. **`MISSING` / `DECLARED_NOT_PROBED` / `UNKNOWN` 只在一个地方被区分**：
   `sharedInputRows`（bad / warn / ok）。`renderSettings` 把同样的状态一律渲染成
   中性的 `tag info`；宿主状态是扁平 `UNKNOWN`。同一事实两种表达。
3. **⑤ 在 13 个面里全部 NOT HANDLED。** 仓内没有任何运行期响应形状校验；
   一个 null 字段会让 `.map` 抛出，被 `show()` 的顶层 catch 接成整页
   `视图读回失败：…`。也就是"一个字段坏了 = 整页没了"，不是"这一格诚实留空"。

## 逐面矩阵

| 面 | 取数与捕获粒度 | ① 离线 | ② 失败 | ③ 空 | ④ 加载 | ⑤ 形状异常 |
|---|---|---|---|---|---|---|
| `''` 首屏工作台 | 按 `connected` 开关 | 隐藏 workspace，显示连接面板 | 按钮级 `setStatus(…,true)` | `尚无任务。…` | `正在读取项目资产与任务…` | NOT HANDLED |
| 仪表盘 | `Promise.all` ×4，**整页失败**；探针逐请求 try/catch | 连接门 + `#b10-offline` 横幅 | 整页 `视图读回失败` | `尚无项目` | `正在读回服务状态…` | NOT HANDLED |
| 项目台账 | 单请求，无 catch | 门→`尚无项目。在工作台新建项目后出现。` | 整页错误 | 同上一格 | `正在读回项目台账…` | NOT HANDLED |
| 项目详情 | 列表 + `Promise.all` ×4，无 catch | 门/空 | 整页错误 | 分面板：交付面板区分 `尚无交付包` / `未连接`；素材面板区分 `未读回` / `尚无参考素材` | `正在读回该项目…` | NOT HANDLED；血缘支路是**静默 unhandled rejection** |
| 研究 / 设计领域 / 团队协作 | 无取数 | 门文案 | 不存在 | 静态 `VIEW_NOT_OPEN` + PLANNED 卡 | 不存在 | 不存在 |
| 品牌系统 | 单请求 | 门→`尚无登记设计系统` | 整页错误 | 同上一格 | `正在读回设计系统…` | NOT HANDLED |
| 创作工具 | picker 无 catch + 体内两请求（逐渲染 catch） | `尚无项目。先在工作台新建…` | 体内 `读回失败：…` | `尚无宿主任务。…` | `正在读回该项目…` | NOT HANDLED |
| 交付中心 | picker + `Promise.all[tasks,bundles]`（一个失败拖垮两个） | 同上 | `读回失败：…` | `尚无交付包` / `尚无任务…` | 同上 | NOT HANDLED |
| 证据系统 | picker + `Promise.all` ×2 | 同上 | `读回失败：…` | `（无）` + `空` 标签 | 同上 | NOT HANDLED |
| 预检 / QA | 初始不取数；运行时逐请求 try/catch | 输入框自由填 | `.error` `预检未确认：…服务端拒绝时未写入任何判定。` + KPI 复位 `—` | 零资源：`无可判定资源`，**显式拒绝给 READY** | `正在读回 ${taskId} 的资源判定…` | NOT HANDLED |
| 系统设置 | 单请求 | `环境状态 OFFLINE`，根 `尚无根登记` | 整页错误 | `尚无根登记` / `尚无外置输入` | `正在读回运行环境…` | NOT HANDLED |

后端已核实路由：`/api/health`、`/api/environment`、`/api/task-preflight`、`/api/projects`、
`/api/design-systems`、`/projects/{id}/{tasks|bundles|design-layer}`，全部在 Bearer `guard()` 之后。
**不存在** `/api/quality`、`/api/domains`、研究、协作路由——与 `VIEW_NOT_OPEN` 一致。

## "空" 与 "未读回" 混同的位置（本轮最关心的诚实性缺陷）

KPI 层是防住的：`kpiCard` 会把离线的 `0` 变成 `—` + `未读回：未连接本机设计服务`。
**列表体没防住**：仪表盘 `尚无项目`、项目台账 `尚无项目…`、品牌 `尚无登记设计系统`、
picker `尚无项目。先在工作台新建项目…`、交付 `尚无交付包`——
"服务端说是 0" 与 "我们根本没问" 渲染成同一句话。

## 本轮已复核并立案的两处

- **`交付包（0）` 的空真值通过（vacuous pass）。** 表头用
  `bundlesReadable === probes.length ? \`交付包（${n}）\` : \`交付包（未读回 x/y）\``。
  离线时 `OFFLINE.projects` 为空 → 探针数为 0 → `0 === 0` 成立 → 显示一个像真的 `0`，
  没有未读回标记。修法：`probes.length === 0` 本身即"未读回"。
- **创作工具页自我矛盾。** 上方宿主面板写 `UNKNOWN`、"不假报可用"；
  下方 `adapterGrid` 却对 Illustrator / Photoshop 硬编码
  `el('span', {class:'tag ok'}, '已登记')`（绿标）+ `tag info` 显示 `declared`。
  没有任何探测支撑这个绿色肯定态。修法：把未支撑的肯定色去掉，只留声明语义。

## 未核实与不做的事

- ⑤ 的"整页失败"结论来自代码路径阅读，未逐面注入畸形响应实测。
- 未启动任何真实宿主，未做 Human Jury；本文所有判断最高到 E1（结构），
  两处立案的复现另计。
- 本矩阵由只读子智能体先做全量盘点，再由我对将要用到的结论逐条回源核验：
  `adapterGrid` 的绿标与 `TOOL_ADAPTERS` 硬编码经核验成立；
  仪表盘 `交付包（0）` 的机制经核验为 `0 === 0` 空真值通过，
  而非其最初表述的"探针失败未标记"。

## 立案待修（本轮未改，登记为任务）

1. 创作工具页 `adapterGrid` 对两个宿主硬编码绿标 `已登记`，同页上方却写 `UNKNOWN`。
2. 仪表盘 `交付包（0）` 的 `bundlesReadable === probes.length` 在零探针时空真值通过。

两者都属"未读回被渲染成肯定结论"，修复随状态补齐一并做，需真实渲染复核。

## 追加：立案两项与 ⑤ 的实测收口（2026-10-07，main = 52dfb791）

上面两段是立案当时的状态，保留原文；此处只报告后续事实。

**立案 1 与立案 2 均已在仓内修掉**（逐条回查当前 main 字节，非沿用他处结论）：

- `adapterGrid` 的硬编码绿标已换成 `tag neutral` + 文案 `登记于 adapter-registry`
  （`shell.ts:1360`），肯定色去掉、只留声明语义，与同页 `UNKNOWN` 不再互相打脸。
- `交付包（0）` 的空真值已改成三分支 `bundleHeading`（`shell.ts:615-622`）：零探针时直说
  `交付包（台账无项目可读）`，不再让 `0 === 0` 通过。
- 顺带核对：`shell.ts:669` 仍有一处 `已登记`，但那是 `tag info` 且描述"该项目在台账里"——
  这条是读回本身给出的事实，不属于被立案的"无探测支撑的肯定态"。

**⑤ 的"未逐面注入畸形响应实测"这条限制已经作废。** 现在每个路由都会被逐面喂畸形响应实测：
`appshell.mjs` 从 `ROUTE_VIEWS` 表自身提取路由，逐个注入 `{}`，断言页面既不崩、又说出缺哪个字段；
`shape-notice-coverage.mjs` 用真 AST 按变量名证明 21 处 seam 读回无一遗漏（PR #265，`14d7179a`）。
① 未连接与 ④ 真实空同样按面双向断言（PR #266，`52dfb791`）。

**仍然成立的两条限制**：本矩阵未启动任何真实宿主、未做 Human Jury，判断上限仍是 E1（结构），
两处立案的复现属代码级而非宿主级；"几何门全绿"不等于"界面好"。
