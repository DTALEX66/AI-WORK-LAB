# DL-KB-02/03/06 — 视觉复核（第二轮，2026-10-24）

复核对象：commit `967d3eed550f5de819f57006530cb4738a491df0`，
bundle `apps/workbench/build/main.js` bytes 485752，sha256
`929d030ca430c571d16e183510d9775cb64894ebe6f10ef05aae98c0e47ba215`
（回执 `kb-03-visual-receipt-20261024.json`，由真实 Chromium 149.0.7827.55
headless 对 `http://127.0.0.1:54066` 的回环服务读回；不是效果图）。

截图字节存放在 `.project-local/task-runtime/kb-visual-20261024/`（Git 忽略），
每张图的 bytes 与 sha256 逐张登记在回执里；本文件引用的是回执所绑字节。

## 看过什么

| 状态 | 视口 | 文件 |
|---|---|---|
| 写入 2 条后的列表（推荐徽章合并后） | 1440×900 | `knowledge-list@1440.png` |
| 非推荐条目详情 | 1440×900 / 1280×800 | `knowledge-detail@1440.png`、`knowledge-detail@1280.png` |
| 推荐条目详情（点击列表行进入） | 1440×900 | `knowledge-detail-recommended@1440.png` |
| 新增表单 | 1280×800 | `knowledge-form@1280.png` |
| 零结果 | 1440×900 | `knowledge-noresult@1440.png` |
| 50/60 分页与展开后 | 1440×900 | `knowledge-more@1440.png`、`knowledge-more-expanded@1440.png` |

## 本轮修复的可见缺陷（已在 967d3eed 字节里复核）

1. **列表行推荐徽章把修订号印了两遍** — 上一轮截图是 `r1` + `推荐 r1`。现在推荐且最新
   只印一个 `最新 r1 · 推荐版本`，另一行印 `r1` + `无推荐版本`；两行各自只出现一次 `r1`
   （`knowledge-list@1440.png`，并由 `apps/workbench/tests/appshell.mjs` 同时断言
   「包含合并文案」与「不包含 `推荐 r2`、`r2` 只出现一次」）。
2. **详情头徽章同样重复** — 推荐条目详情显示 `最新 r1 · 推荐版本`，其后的字段区
   只保留 `推荐版本 r1` 一处（`knowledge-detail-recommended@1440.png`）。
3. **窄视口下当前项不在侧栏视口内** — 侧栏内容在 1280×800 下高 1267px、可视 516px，
   点击「知识与提示词库」后 `scrollTop=751`，按钮矩形 593.5–640.5 落在导航视口
   124.5–641 内（`kb-03-browser-e2e-summary-20261024.json#navVisibility`）。
   E2E 场景 `desktop-nav-active-visible` 在滚动失效时退出码 13。

## 设计审查插件的读数（`design-review-20261024/`）

- **a11y**：26 次扫描、0 findings、`ok=true`。这是自动扫描的通过，不是 WCAG 认证，
  也不是真人验收。
- **design debt**：713 findings、`ok=false`、10 个文件、27 个 token 值。分布：
  px-magic 630 / hard-coded-color 38 / functional-color 14 / custom-shadow 28 /
  tailwind-arbitrary 3；severity minor 630 / major 52 / debt 31。按文件：
  `style.css` 683、`shell.ts` 28、`workbench.ts` 2。
- 这一条按**未关闭的登记**记录，不按通过记录。`style.css` 同时是 token 声明处与
  组件规则所在地，原始值里有一部分就是 token 定义；`shell.ts` 的 28 条里 17 条是
  注释命中（`35px`、`840px` 等讨论文字），非注释的 11 条中：
  `5985` 是 token 预览样例 JSON，`9273` 是资源 ID 正则，两者为误报；
  `5475`/`5477`（`gap:10px`）、`6856`/`6860`/`6870`（抽屉内联 margin）是真实内联样式；
  `6418`/`6692` 是 760/840px 断点常量。`workbench.ts:377` 是路由正则，误报。
  真实内联样式共 5 个位置，属版式轮次的清理范围，本轮不装作已清零。

## 仍然未证

- 1920 只在本轮之前的空库轮次截过；写入态的列表/详情在 1920 没有单独截图，
  1280 与 1440 已覆盖。125%/150% 的缩放读数是上一轮 `zoom-scales.json`，
  本轮未重测。
- 语料仍是探针合成的 2 条 + 分页 58 条，不含 owner 的真实条目。
- 修改与导入路径本轮没有逐屏截图；其覆盖在单元/接口层。
- 以上全部是 E1/E2 证据，不是 E3，也不是具名真人验收。
- 手机端不在本项目范围（owner 2026-10-19：只做桌面端）；840px 以下的抽屉样式
  只作为桌面窗口缩窄时的既有实现被复核到，不构成手机端交付。
