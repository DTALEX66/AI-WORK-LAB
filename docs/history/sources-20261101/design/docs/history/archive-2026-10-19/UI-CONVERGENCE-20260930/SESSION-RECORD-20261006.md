# 会话记录 — Workbench 界面多维审计 / 修复 / 证据更新（2026-10-06）

分支 `feat/ui-commercial-workbench-20260930` · PR #213（保持 DRAFT）
本轮提交序列：`389222e → ca67834a → e86d72c8 → f109051 → 3312707`

目的：把这一轮做了什么、错在哪、还剩下什么，一次性写清，供后续会话与 owner 直接消费。
这不是计划文件；每条断言都对应仓内已存在的字节或已跑过的命令。

---

## 1. 输入（四路并行）

| 来源 | 覆盖 | 产出 |
|---|---|---|
| 子代理 · 无障碍 | WCAG 2.1 AA 全量（4 principles × 13 guidelines） | 41 条 finding |
| 子代理 · 文案真值 + 语言治理 | 用户可见断言 vs 服务端真实字段/路由 | 32 条 finding |
| 子代理 · 安全 | DOM sink、令牌生命周期、路径注入、HTTP 边界 | 4 中危 + 6 低危 |
| 本轮新增审计器 | 真实 Chromium 量化测量 | 65 作用域报告 |

关键方法约束：三路子代理均为**只读**；动代码的只有我自己，避免多写者踩踏。
浏览器探针能测的（溢出、对比度、控件命名、触控目标）以实测为准；
探针测不到的（关闭的浮层内部、代码注释与实现是否一致）由静态审计补，
两套结论在 4.45:1 / 4.19:1 / 4.01:1 上互相独立吻合，才认定可信。

---

## 2. 修了什么

### 2.1 虚构数据（本项目红线）

- 仪表盘硬编码进度条 72% / 84% / 65% —— 注释自称「真值条」，且 84% 紧邻「真实读回」、
  72% 紧邻「显式 UNKNOWN」。删除。
- 编造的「设计质量趋势」上升曲线（常量 56→96）。删除后标题带「· 未读回」，
  并注明无质量路由。删除它顺带消除了全仓唯一在跑的 `innerHTML` sink；
  发布产物 `build/main.js` 的 `innerHTML` 命中数由 1 变 **0**。
- 项目台账每行状态写死 `Active`，而 `/api/projects` 只返回 `{id,name}`。→ `未读回`。
- 预检词表 `PASS / BLOCKED`（服务实为 `READY / BLOCKED`）；
  零资源任务会得到绿色 READY（空真）→ 改「无可判定资源」；
  运行失败后 KPI 残留上一次判定 → 三处 `resetKpis()`。
- 外置输入根 `DECLARED_NOT_PROBED` 配绿色 pill → `tag warn`；
  项目根 `writable: True` 是后端常量、无探测 → 「声明可写（未探测）」。
- 交付包 rights 非 NOT_REVIEWED 一律绿色「已登记」→ 中性显示原值。
- PENDING 与 RUNNING 统称「运行中」→ 显示真实轮次状态。
- KPI 说明文字一律套成功绿 `.trend up`（无趋势来源）→ 中性；
  无会话时 `0` 冒充读回 → `kpiCard` 单点 UNKNOWN-not-0 规则。
- 侧栏演示身份 `Alex / Personal Workspace`（无身份路由）→「本地单用户 · 未读回」。
- 交付面板声称含 BOM（`grep BOM src/design_lab/` 零命中）→ 标 PLANNED；
  离线空清单断言「该项目没有交付包」→「未读回，不代表没有」；
  「最近交付」但 BundleRecord 无时间戳且代码从未排序 → 「交付包」，注释同步纠正。
- 阶段导航 Versions 标 IMPLEMENTED 但锚点 `#pd-versions-panel` 从不存在（点击静默无效）；
  Evidence 标 IMPLEMENTED 实为交付包清单 → 均降 PLANNED 并写明真实归属；
  Review 节点改名「资源预检（非设计评审）」。
- 5 个无 handler 的「导出周报/资产/报告/诊断/项目」死按钮删除
  （保留 `workbench.ts` 里真实接线的「导出交付包」）。

### 2.2 功能阻断 + 无障碍

- **命令面板路由是坏的**：写 `'#' + view` 得 `#dashboard`，路由表匹配 `#/dashboard`，
  于是每条命令都落错页；`?dev=1` 下反而看起来正常（dev 默认视图掩盖了它）。
  它是 ≤840px 下唯一路由切换手段（B10 侧栏在该断点 `display:none`）。已修，
  并在审计器里加真实交互断言（打开→点首行→校验 hash 与落地页标题一致）。
- 面板结果行 `div+onclick` → 真 `<button>`（键盘可达）。
- 焦点可见（2.4.7）：`.input` 与 `.palette input` 的 `outline:none` 移除；
  原本唯一提示是 12% alpha box-shadow，实测约 1.13:1；改 3px `--color-secondary`（7.47:1）。
- 减少动效（2.2.2）：`prefers-reduced-motion` 原先只关 transition，
  四类无限 keyframe 动画照跑，且 `box-shadow:none!important` 恰好抹掉当时唯一的焦点提示；
  现覆盖 animation、不再依赖 box-shadow 作焦点，`animateKpiCount` 自行读 `matchMedia`
  ——文本补间 CSS 管不到，原注释「CSS 层已处理」是错的，已改正。
- 对比度（1.4.3）：白字压品牌蓝在 12–16px 全线不达标（按钮渐变两端实测 3.92 / 3.13:1，
  状态药丸 1.83–3.35:1）。改配全部按实测算数落定并断言 ≥4.5。
- 路由切换销毁焦点元素导致焦点掉回 `<body>` → `#route-view tabindex=-1` 并接管焦点；
  阶段跳转滚动后聚焦目标；浮层关闭归还焦点。
- `#route-view` 整体 `aria-live` 撤除（会把整个 KPI 网格与表格朗读一遍，并与面板级 status 双读），
  改窄 `role="status"`；并修复 routed 视图里 `setStatus` 写进被隐藏的 `#status`。
- 侧栏 `div.nav[aria-label]` → 真 `<nav>`（role=generic 不支持可访问名，标签被丢弃）。
- 12 个仅靠 placeholder 的项目详情控件 → `fieldRow()` 生成真实 `<label class="field-label">`；
  规则全 class 化，避开 `label{}` 元素选择器（正是 W02 清掉的 B10 泄漏源）。
- 关闭抽屉不再留在 Tab 序；5 个 `.table-wrap` 加 `tabindex/role/aria-label`；
  表头补 `scope`、空操作列表头命名；阶段 PLANNED 标签不再 `aria-hidden`。
- 项目 id 路由：先校验后解码（`%2f` 解码成 `/` 后被拼进 API 路径；裸 `%` 抛错打断渲染）
  → 解码后用 `/^[0-9a-f]{32}$/` 校验并 try/catch。
- 任何 401 立即清令牌（此前只在首次连接失败时清，服务重启后各视图把 401 文本当数据渲染）。
- 死接口 `openModal(title, bodyHtml)` 改 `Node | string` + `replaceChildren`。
- 用户可见文案去掉仓库内部路径与 Markdown 残留（`job_store.py`、
  `findings/W06-TOKEN-WRITE-GAP.md`、`而**不**计入`）。

### 2.3 量化结果

| 指标 | 修复前 `07127565` | 修复后 |
|---|---|---|
| 硬违规 | 150 | **0**（65 作用域，commit `3312707` 一轮） |
| contrast | 85 | 0（渐变底另计，见 §3） |
| 无可访问名控件 | 60 | 0 |
| cold-start | 5 | 0 |
| keyboard / alt / overflow / touch-target / console / pageerror | 0 | 0 |

---

## 3. 我犯的错（照实记，不修饰）

1. **审计器把隐藏子树量了进去**。`display:none` 只在祖先上，子元素自身 computed display
   不是 none。首跑报出 715 条「键盘不可达」+ 大量对比度失败，全是幽灵元素。
   → 一律以 `getClientRects()` 为准。
2. **审计器无法测渐变底**，而且方向是危险的：修好药丸配色后它反报 180 条 1.06:1 失败
   （渐变在 `background-image`，`backgroundColor` 透明，于是向上取到药丸背后的深色面板）。
   修法不是回退配色，而是让仪器承认测不到：判为 indeterminate、单独计数、
   两个方向都不猜。**因此「0 违规」的口径必须写清：只覆盖探针真能量化的部分。**
3. **我自己改坏了被测对象**：编辑预检表单时误删 `runBtn` 声明，留下悬空引用；
   靠 typecheck 抓到，不是靠记忆。
4. **在 `<body>` 直下放了第二个跳转链接**，它位于 `header/main/footer` landmark 骨架之前，
   会把骨架顺序破坏。撤掉，只留 `<main>` 内那一个（`#content` 由 JS 创建）。
5. **仪器断言写错契约**：cold-start 检查要求 `#login` 可见，但 `show()` 在所有 hash 路由
   上**故意**隐藏 `#login`。真正的契约是「要么能看到连接表单，要么有一个能到它的动作」——
   于是暴露出真实缺陷（冷加载落在 hash 路由上只剩一句「请先连接」却无路可走），
   补了「前往工作台连接」按钮并让审计器真的点它验证生效。
6. **`| tail -20` 截断了后台任务日志**，导致 54 条失败无法定位，只能重跑一遍全套。
   管道截断会把 SIGPIPE 风险带进长任务；证据应完整落盘再读。
7. **文档里写进一个控制字符**：Python 字符串里 `\10` 被当八进制转义，
   把 `10-toolchains` 吃成退格。写盘后必须回读校验，不能只信脚本退出码。
8. **两次把 PATH 少配一项**（node / 工具链 python），导致一次 E2E 门假报「node not on PATH」。
   本机 node 与可用 python 都在 `OS External Configuration/10-toolchains` 下，
   不在默认 PATH；报「环境缺失」前必须先探测外置根。

---

## 4. 仍未解决 / 需 owner 裁决

| 项 | 状态 |
|---|---|
| 1.4.11 边框对比 `#213D66` on `#0D1221` = 1.71:1 | 改品牌 token 属视觉裁决，未动 |
| ≤840px 侧栏 `display:none`（只剩命令面板导航） | 需改 off-canvas/汉堡，属版面裁决 |
| `div.list/.list-item` 应为 `ul/li`；状态机词表来自 gitignore 的 B07 稿 | 结构重排 + 按 LANGUAGE-POLICY §5 由契约生成，独立任务 |
| `localStorage` 简报草稿越出「产物留项目内」边界 | 需决定改内存 Map 还是加 TTL |
| `/api/environment` 向浏览器返回绝对路径 | 仅令牌会话可见，改它要同时调整 settings 契约 |
| `index.html` 用 `type="module"` 而测试断言 classic script | 两者作用域语义不同，需先定哪个是契约 |
| `?dev=1` 可在真实服务上开空数据缝 | 数字已统一显示 `—/未读回`，是否彻底禁用属 owner |
| **分支拓扑** | 本分支与 `qoder/designlab-m1-closeout-20261005` 各自从 `main` 分叉（merge-base `1acbfa15`；彼此 10 / 28 提交互不含）。`cli.py` 的 `workbench/backup/restore` 只在 closeout 上。建议先合本分支再让 closeout rebase，否则 `apps/workbench/*` 与截图证据大冲突。合并动作归 owner |
| 孤儿状态归档 | `.project-local/backups/orphaned-project-state-20261006.zip`（346 文件 / 357,703,756 B）仍在 gitignored 运行根内，需 owner 移出或显式处置 |

**B10 1:1 的故意偏离（4 处）**：进度条、sparkline、死导出按钮、演示身份。
理由是它们在真实产品里承载不存在的数据或动作；仓内无可执行的 B10 dom-diff 门，
所以这类偏离不会被门自动捕获——必须由本文件与代码注释记录。

---

## 5. 证据与其绑定方式

- `ui-audit/report-before-fix.json`（`07127565`，150 违规）与 `ui-audit/report.json`（修复后，0）
  ——含 commit、浏览器可执行路径、Python/Node 版本、逐作用域数值。
- `screenshot/` 40 张 PNG + 40 个 `.license` sidecar + `screenshot-manifest.json`，
  绑定 subject commit `ca67834a` 与 bundle 163,269 B / SHA-256（证据绑**被摄对象**的 commit，
  不是承载文件的 commit）。
- 截图驱动现在把**被拍下来的** KPI 值、面板标题、`未读回` 标记一并写进清单；
  `SCREENSHOTS.md` 的环境块 / 哈希表 / 观察记录改为脚本从清单与审计报告生成。
  这一步立刻证伪了旧文案——它还在描述本轮已删除的 sparkline。
- 本轮 `reports/current/DEEPSEEK-FINAL-TEST-GATE.json`、`LANGUAGE-BOUNDARY-SCAN.json`
  由真实测试运行再生（绑定域 225 tests / 0 failures / 0 errors / 0 skipped，
  run_id `testrun-20261006T051101Z-forward-repeat-91beed9eafb6`）。
  clean-tree 门只钉 `fixtures/domains/game-visual` 与 `apps/workbench/build`，不钉这两个投影，
  故提交它们不会制造 C8 那类自陈旧 paradox。

## 6. 证据等级声明

**E1 结构 + E2 受控运行时**。本轮不主张 E3（未驱动 Photoshop/Illustrator，未产原生可编辑文件）、
不主张 E4（无人工 Jury；界面好不好看、够不够专业不由我判定）。
无障碍合规结论也不等于法务或第三方审计意见。
