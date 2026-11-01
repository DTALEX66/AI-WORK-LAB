# Observer 生产界面渲染审计 — 2026-10-07

> 对象：`apps/observer/frontend/dist`（Vite 产物），由 `services/orchestration/sidecar.py
> --frontend-root` 在 `http://127.0.0.1:61911/` 只读服务；数据是真 sidecar v3 快照
> （1 个项目 work-lab、0 执行、token 全 null、transport OFFLINE/DELAYED、revision 0）。
> 方法：**无窗口的 headless Chromium 真实视口渲染**（声明根
> `10-toolchains/playwright/chromium_headless_shell-1228`），逐车道截图 + 哈希比对，
> 再用眼睛判断版式。脚本：`.project-local/runs/convergence-20261007-c/ui_render_shots.py`；
> 证据：`.project-local/artifacts/ui-audit-20261007/`（26 张 PNG + `render-inventory.json`）。

## 为什么不用 `--dump-dom`

带 `--virtual-time-budget` 的 `--dump-dom` 会**挂死**（实测 120s 超时）：应用持有 SSE 长连接，
虚拟时间等不到静默。只用 `--screenshot` 则正常渲染并退出。这条写在这里是为了下次不再试错。

## 机器判定的结论（不需要眼睛）

- 26 次渲染**全部产出可信 PNG**（最小 50 KB），`thin=[]`；
- **没有任何两条车道产出逐字节相同的 PNG**（`duplicate_renders={}`）——这抓的是"路由没真的切换"；
- 深色总览 ≠ 浅色总览 ⇒ 主题开关有效；深色总览 ≠ 紧凑总览 ⇒ 布局开关有效；
- 320 / 820 / 1440 三档 work 车道各自不同 ⇒ 视口确实参与布局。

## 用眼睛看到的（按严重度）

1. **窄屏顶栏堆叠**（320px）：汉堡、搜索、`通知/工作区/紧凑/浅色` 四个动作各占一行，
   顶栏吃掉约 40% 首屏高度。功能没坏（导航抽屉存在、按钮仍可达，
   `test_desktop_component_contract.js` 的窄屏动作簇断言守着可达性），
   但这是**商业级观感的头号短板**：≤560px 应把动作簇收进抽屉或降为图标，
   搜索框应缩略而不是截断成 `搜...`。
2. **车道标题在窄栏里折行**（320px 的"执行详情" + `0 条 · 真实投影`）：
   标题与副信息并排导致双双折行；应改为窄屏堆叠。
3. **诚实性表现良好**（这是本项目最在意的一条，逐屏核对）：
   Token KPI 显示 `UNKNOWN`、覆盖显示 `UNKNOWN` 而不是 `0/0`、
   趋势面板写"无趋势数据（UNKNOWN）"、空执行列表写
   `暂无执行记录（registry 中无 active execution）`，
   没有任何一处把缺失渲染成 0 或"正常"；`revision 0` 是真值不是伪造。
4. **禁用的 `导出状态 / 新建执行` 按钮**：外观与可用按钮一致（b10.css 无 `:disabled` 规则），
   靠 Tooltip 说明原因。已知的遗留观感债，非本次引入。
5. `无告警信号` 是绿色 chip：文字准确（确实没有告警），但在满屏 UNKNOWN 的语境里
   绿色容易被读成"系统健康"。属可选优化，不改事实。

## 未做的事（明确记录）

- 没有改 CSS：本轮只出审计结论。第 1、2 条是下一步的 UI 工单，
  动之前必须先跑 `test_desktop_component_contract.js` 与
  `test_production_surface_static_contract.js`（字号/溢出/微角色白名单都在那里）。
- 品牌 SVG 已迁入 `frontend/src/assets/brand/` 但**未挂载**到头部（现头部是文字锁扣）。

---

## 第二轮：把"看起来不对"变成量出来的数（同日）

先说失败的方法：`--dump-dom --virtual-time-budget` 挂死（SSE 长连接），
所以截图给不了数值；in-app 浏览器是 0×0 视口，也没有布局。
于是写了一个**零依赖 CDP 探针**（Node 22 自带全局 `WebSocket` 与 `fetch`）：
`.project-local/runs/convergence-20261007-c/cdp_layout_probe.mjs`，
用 `Emulation.setDeviceMetricsOverride` 在 320/560/840/1440 四档量真实盒模型。

**量出来的根因（不是顶栏，是整个应用列）**：

| 视口 | 修复前 `.app` 计算网格 | `.main` 宽 | 顶栏高 | 四个动作按钮 |
|---|---|---|---|---|
| 320 | `210px 110px` | **210** | 263 | 各占一行（y=118/152/186/220） |
| 560 | `210px 350px` | **210** | 263 | 各占一行 |
| 840 | `210px 630px` | **210** | 305 | 各占一行 |
| 1440 | `244.8px 1195.2px` | 1195 | — | 一行（正常） |

机制：≤840px 时导航栏 `display:none` —— **display:none 的网格子项根本不参与布局**，
于是 `main.main` 被自动放进了**第一根轨道（210px 的栏轨）**，右边 1fr 空着。
所以窄屏看到的"顶栏堆叠""内容挤成一条"其实是同一个缺陷：整个应用列被压成 210px。
b10 里那条 `@media (max-width:840px){.app{grid-template-columns:1fr}}` 是有效的，
但壳层后面有一条**无条件的** `.app{grid-template-columns:clamp(210px,17vw,280px) minmax(0,1fr)}`
（同特异性、位置更后）把它覆盖了——那条规则当初是为了让内容轨可收缩而故意写成无条件的，
写的时候没人量过 ≤840px 的情形。

**修复**：把两轨形式收进 `@media (min-width: 841px)`，默认单轨 `minmax(0,1fr)`；
另加 ≤560px 一档让动作簇整行横排、搜索框按剩余空间收缩。
**修完再量**：320/560/840 的 `.app` 都是单轨＝视口宽，`.main`＝视口宽，
四个按钮全部回到同一行（320：x=14/56/110/152，顶栏高从 263 降到 ~104）；
1440 的两轨不变（244.8 + 1195.2），桌面端无回归。

**回归锁**：`test_production_surface_static_contract.js` 新增
`the shell keeps a single app track below the rail breakpoint`（22 条全绿），
两种注入各自变红：把单轨改回无条件两轨；把某一处 clamp 声明移出 841 门
（第一版我写成"clamp 声明只能出现一次"，被自己打脸——壳层本来就在两个小节各写一次且都在门内，
改成"每一条都必须处在 `@media (min-width: 841px)` 里"才是这条规则真正要守的东西）。

**顺带纠正本轮先前两处判断**：
① 我在上文把 320px 的顶栏堆叠当成"顶栏自身的问题"，实为应用列被压成 210px 的下游症状；
② 我第一次用 `closest()` 探测按钮归属时，选择器列表里没写 `.top-actions`，
于是误读成"按钮不在 `.top-actions` 里"——**探针的选择器集合会决定你能看见什么**，
与"grep 把定义处过滤掉"是同一类错误。

复现命令（sidecar 起在 61912，服务 `frontend/dist`）：
`node .project-local/runs/convergence-20261007-c/cdp_layout_probe.mjs`。
现状：vitest 17 文件 114 条、node 契约 33 条（静态 22＋桌面 11）、电池 0 失败、
`vite build` 绿；`dist` 已用修复后的源重建，release 二进制仍未重建。

## 第四轮：截图里读出来的两处自相矛盾（同日，已修）

看渲染图能看见源码看不见的东西。两条都是从 PNG 里发现的：

1. **总览状态条在"无数据源"时亮绿灯**：alerts 由 `snap?.ci` 与执行行迭代得出，
   没有快照时两者皆空 ⇒ chip 显示绿色`无告警信号`，而它正下方的面板写着
   `数据源未接入 — 无法判断告警（保持 UNKNOWN，不伪造「全部正常」）`。
   同一面屏幕的两半互相打脸，而颜色比文字先被读到。
   改成三态：无快照→`告警状态 UNKNOWN`（muted）、有告警→`N 条告警信号`（warning）、
   确有快照且无告警→`无告警信号`（success）。
   这与 ERR-120 的 dirtyCount 是同一类错误：**对缺失数据做计数，不等于测得零**。
2. **永久禁用的 `导出状态 / 新建执行` 与可用按钮长得一模一样**：b10.css 没有 `:disabled` 规则，
   还保留 `button{cursor:pointer}` 与 hover 抬起；D-11 锁住 b10 逐字，所以只能由壳层补——
   现加 `cursor:not-allowed` ＋ 降透明度 ＋ 取消 hover 抬起。

回归锁：vitest 新增 `the alert chip has three states…`（三态各自断言），
node 静态契约新增 `a disabled control is visually disabled`（三条形状检查）。
**证伪 3/3**（`falsify_ui_round4.py`：把 chip 改回两态、删掉 `cursor:not-allowed`、
删掉 disabled 的 hover 覆盖），每次注入后按字节复原核对 SHA-256。
台账 **ERR-124**。

两处过程教训：① 用 heredoc 往 CRLF 工作树里追加会造出混合换行——
我自己的两条证伪针因此连续 NEEDLE-ERROR，归一化换行后才命中（内容不变）；
② 台账校验器要求 `repeat_prevention` 含祈使词（must/never/必须…），
第一版写成陈述句被 `ERROR_LEDGER_FAIL … not enforceable` 拦下——门是活的，它拦的就是我。

现状：vitest 17 文件 **115** 条、node 契约 **34** 条（静态 23＋桌面 11）、
`tsc --noEmit` 干净、`vite build` 绿、电池 **BATTERY_FAILURES=0**；
CI 在退役提交 `891c871` 上两条工作流全部 job completed/success。
仍未做：品牌 SVG 挂载到头部；禁用态是 CSS 形状契约而非渲染后计算样式（CDP 探针能量但没接进 CI）。

> **2026-10-07 下午更正（本文件按快照保留原文，不改写历史）**：上面三条"仍未做/修复方式"里有两条已被同日的
> 后续工作取代。(1) 本文第 76 行的修复形式——把两轨收进 `@media (min-width: 841px)`——按 owner 的桌面唯一化
> 指令在 `71b1ae8` 被删除，现在 `.app` 无条件声明 `clamp(...) minmax(0, 1fr)`，不变量改由重锚定的契约测试
> 与 `tests/ci/test_desktop_only_shell.py` 守（ERR-123 的 bindingNote 记录了这次换据）。(2) CDP 几何探针已接成
> observer 作业的**必需步骤**，并在 runner 上给出实测读数（`17eb5b6` 与 `95c62a4` 两个头全绿；读数见
> `UI_IMPLEMENTATION_REPORT.md` §13–§14）。(3) 顶栏品牌已落：几何门禁在 runner 上量到 `brand_mark_present
> PASS brand=91`（紧凑态 `brand=22`）。仍成立的只有"禁用态是 CSS 形状契约而非渲染后计算样式"这一条。


