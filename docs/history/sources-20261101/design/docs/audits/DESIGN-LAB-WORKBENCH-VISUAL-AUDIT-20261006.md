# DESIGN-LAB Workbench 视觉自审 · 2026-10-06

> 触发：owner 反馈「文字都溢出了 / 没有审美吗 / 没有视觉设计规范吗 / 没有相关技能和插件调用吗 /
> 界面需要显示那么后端对接的内容吗」。
> 本文只记录**实测**结论。所有数字来自真实 Chromium 对真实 loopback 服务的测量，不来自阅读代码后的推断。

- **审计对象**：`apps/workbench`（index.html / main.ts / shell.ts / workbench.ts / design.ts / style.css）
- **基线 commit**：`734269367a96ef68841d9d0a81b85cbdf61608ab`
- **分支**：`qoder/designlab-workbench-visual-audit-20261006`
- **服务**：`python -m design_lab --project <dir> workbench --port 8787`，本机 token（一次性，不入仓）
- **浏览器**：Chromium 1228（`%LOCALAPPDATA%/ms-playwright/chromium-1228/chrome-win64/chrome.exe`）
- **视口**：1440 / 1280 / 1024 / 768 / 390 × 12 条路由
  > **2026-10-07 口径更新（owner 裁定：只收口径，不删代码）**：当前视口口径为
  > **1440 / 1280 / 1920 / 2560**，capture 入口只产出这四面。上面这行是本次审计当时的覆盖面，
  > 保留不改；`@390` / `@768` 的截图、license 记录与 overflow 报告作为历史证据原样留在仓内，
  > 移动端布局代码与样式一律未删。引用"当前"证据时以四面桌面口径为准。
- **证据产物**：`.project-local/tmp/overflow-*.json`（修复前）、`gate-red.json`（证伪）、`gate-final.json`（修复后）

---

## 一、方法论（为什么可信）

不用「读 CSS 猜哪里会溢出」。判定分两类，只有这两类算缺陷：

| 类别 | 判定条件 | 为什么算缺陷 |
|---|---|---|
| `CLIPPED` | `scrollWidth > clientWidth` 且该元素 `overflow-x: hidden/clip` | 内容被**静默裁掉**，用户永远看不到 |
| `STRAY` | 元素右边界超出视口，且**没有任何** `overflow:auto/scroll` 祖先 | 用户**滚不到**，等于丢失 |

不算缺陷的两类，但**照样计数并打印**，避免用「未发现」掩盖事实：

- `.sr-status`：路障公告的屏幕阅读器专用区域，CSS 本来就 `clip-path:inset(50%)`。显式 allowlist，不静默跳过。
- 位于真实滚动容器内的元素（`.table-wrap` 表格、移动端 `.app-nav`）：记为 `SCROLL_OK`，可横向滚动到达。

**闸门已证伪后启用**（项目铁律：新门必须先看到它变红）。
注入 `.panel{max-width:220px}` 后闸门输出 `OV_SUMMARY clipped=4` 并 `OV_FAIL`，退出码 1；
移除注入后 `clipped=0 stray=0 tiny=0` 并 `OV_OK`，退出码 0。

---

## 二、实测发现（修复前）

| # | 发现 | 证据 | 严重度 |
|---|---|---|---|
| F-1 | **系统设置页 `div.panel` 文字被裁掉 388px**（1440 视口），390 视口裁掉 391px | `overflow-report.json` `settings` 路由 | 高 · 内容不可见 |
| F-2 | 项目根面板被裁掉 94px | 同上 | 高 |
| F-3 | `grid` / `flex` 子项缺 `min-width:0`，无法收缩，宽内容顶破面板 | 1024 视口表格外溢 23px | 中 |
| F-4 | legacy 工作台页 **16 处文字为 10px**，其中一处 `.eyebrow` 被当正文塞了 60 个汉字 | `tiny=16` | 中 · 可读性 |
| F-5 | 侧栏品牌副标题 `.brand small` 10px | `tiny` 计数 | 低 |
| F-6 | **31 处 `/api/...` 路由串直接写在用户可见文案里**（KPI 卡片注解、页面说明、能力卡） | `grep -c '/api/' shell.ts` | 中 · 信息层级 |
| F-7 | 设置页整页是服务端诊断（schema id / roots / shared_inputs / write_trace / migration） | 页面结构 | 中 |
| F-8 | RIR JSON（`maxlength=3800000`）与 Patch JSON（`maxlength=900000`）文本域直接铺在主流程里 | `index.html` | 中 |

### F-1 根因链（不是猜的）

```
.tag { white-space: nowrap }              ← 短状态药丸，nowrap 本身是对的
   ↓ 但被拿来承载完整文件系统路径
.list-item { display:flex; ... }          ← 子项默认 min-width:auto，无法收缩
   ↓ 行被撑到 ~600px
.three-col > *                            ← grid 子项同样 min-width:auto
   ↓
.panel { overflow: hidden }               ← B10 面板静默裁掉超出部分
   ↓
结果：C:/Users/ALEX/... 这条路径，用户只看到前面一小截
```

---

## 三、修复（只做三件事）

### 1. 让宽内容可收缩、让长值换行 —— `apps/workbench/style.css`

```css
.two-col>*,.three-col>*,.split>*,.kpi-grid>*{min-width:0}
.list-item,.list-item>*{min-width:0}
.list-item{flex-wrap:wrap}                 /* 兜底：nowrap 药丸放不下时换到下一行 */
.list-item.value-row{flex-direction:column;align-items:stretch;gap:6px}
.value-mono{ font-family:ui-monospace,…; overflow-wrap:anywhere; word-break:break-word; max-width:100% }
.list-item small{overflow-wrap:anywhere;word-break:break-word}
.table-wrap{max-width:100%}
```

长值（路径 / hash / schema id）改用新类 `.value-mono` 承载，与 `.tag`（短状态药丸）职责分离。
**不改 B10 结构类名、不改 B10 声明值、不引入第二套色板。**

### 2. 字号回到项目自己声明的 token 尺度 —— 不是发明新值

`:root` 早已声明 `--font-caption:13px` / `--font-body:16px`，但实现侧实际用的是
10px（`.eyebrow`）、13px（legacy 正文）、11px（`.mono`/`.badge`）、10px（`.brand small`）。
修复方式是**让实现服从已有规范**：

| 选择器 | 前 | 后 | 依据 |
|---|---|---|---|
| `.eyebrow` | 10px / letter-spacing 2px | 12px / .08em | 标签仍小于正文；2px 字距在中文下过宽 |
| `body > header p, body > main p, body > footer p` | 13px | 14px | 仍低于 `--font-body:16px`，不改信息密度层级 |
| `.mono` / `.badge` | 11px | 12px | 全站最小可见文本统一到 12px |
| `.brand small` | 10px | 12px | 同上 |

`index.html` 中那条 60 字的 `.eyebrow` 改回 `.note`（13px 说明文本），不再用标签样式承载正文。

### 3. 收敛后端对接内容

- `shell.ts`：移除用户可见文案中的 `/api/...`（13 处替换，脚本带计数校验，任一项计数不符即中止不落盘）。
  改为「服务端项目台账读回」「服务端目录读回」「服务自检读回」等人类可读描述。
  **实际 fetch 路径与请求数量、顺序完全未改** —— `appshell.mjs` 依赖 dashboard 恰好 4 个请求且顺序固定。
- 设置页：路径诊断（`项目根` / `外置输入` 两块）移入 `<details class="advanced">`，默认收起。
- 能力卡：路由 / 合同引用 / owner / 下一动作移入「接入明细」折叠；
  **状态标签（PLANNED / BLOCKED）保持可见** —— 诚实标注是这张卡存在的理由，不能折起来。
- `index.html`：RIR 对象计划、Adobe 局部修改两块移入 `<details class="advanced">`，默认收起。

---

## 四、修复后实测（同一脚本、同一服务）

| 视口 | CLIPPED | STRAY | SCROLL_OK | tiny(<11px) |
|---|---|---|---|---|
| 1440 | 0 | 0 | 0 | 0 |
| 1024 | 0 | 0 | 7（表格，可滚） | 0 |
| 390  | 0 | 0 | 21（表格 13 + 移动导航 8，均可滚） | 0 |

`OV_SUMMARY clipped=0 stray=0 tiny=0` → `OV_OK`，退出码 0。
12 条路由 × 3 档视口，`documentElement.scrollWidth - clientWidth` 全程为 0（无横向整页溢出）。

设置页裁切：**388px → 0**。页面级横向溢出：**全程 0**。

---

## 五、可复跑入口

```bash
# 与既有 capture_workbench_screenshots.mjs 同一套 env 约定
E2E_SERVICE_URL=http://127.0.0.1:8787 \
E2E_TOKEN=<64-hex> \
E2E_NODE_MODULES=<abs>/apps/workbench/node_modules \
E2E_BROWSER=<abs>/chrome.exe \
OV_WIDTHS=1440,1024,390 OV_STRICT=1 \
node design-lab/tests/e2e/audit_workbench_overflow.mjs
```

`E2E_NODE_MODULES` **必须是绝对路径**（`createRequire` 不接受相对路径，否则 `MODULE_NOT_FOUND`）。
`OV_STRICT=1` 额外把「正文小于 11px」判为失败。

---

## 六、未做 / 待 owner 裁决（不自行决定）

| # | 事项 | 为什么不能自决 |
|---|---|---|
| D-1 | **字体栈首位 `Inter` 未随包分发**。本机 `document.fonts.check('12px Inter')` 为 true 只是因为系统装了 Inter；换机即退化到 Segoe UI。 | 字体属品牌决策；且 frontend-design 规范明确禁用 Inter/system 字体堆 |
| ~~D-2~~ | **已裁决并部分落地**（owner 2026-10-07：「批准拆类，我按新类名做」）。`.items` 拆成 `.items-stack`（纵向整宽按钮列表，legacy workspace）与 `.items-chips`（真实数据路由的换行药丸行）；`.mono` 三处、`.error` 两处合并为各一处权威定义，合并值等于**原先实际生效**的样式，界面零变化。新增 `design-lab/tests/test_workbench_css_single_definition.py`：任何同类选择器重复定义即失败，确有意的层级覆盖必须写进 `SANCTIONED` 并给理由（该表是双向的，条目修好后不删也会失败）。 | 剩余一半是 `.list-item` 的**重载语义**拆分（列表成员 vs 带边框行卡片），见 §十 |
| D-3 | 原稿自相矛盾项 X-1（正文 18 vs 16px）、X-2（caption 14 vs 13px）、X-3/X-4（断点 767/760/840）、X-7（`--radius-sm` 12px 冲突） | 文件内已记录但未裁决 |
| D-4 | 移动端 12 项导航在 390 视口需横向滚动（1059px 内容 / 390px 视口） | 是可滚动容器，不算缺陷；但是否改为抽屉/分段导航属产品决策 |
| ~~D-5~~ | **已裁决并落地**（owner 2026-10-06：「现在接，并先证伪」）| 见 §八。闸门已进入 required CI job，workflow 文件本身未被改动（该文件被 SHA-256 钉在两份账本里）|
| D-6 | 首屏工作台是**另一套壳**：legacy `.app-nav` + "本机已连接"脚注 + 390 底部横滚条，而 12 条路由页是 B10 `.sidebar` + "本地单用户/无身份路由 · 未读回" + 顶部「导航」抽屉 | 方向裁决，见 §十五（该面此前从未被捕获，所以从未进入清单）|

---

## 七、诚实边界

- 本次**没有**做视觉主观评审（构图、留白节奏、色彩情绪）。只修了可测量的缺陷：
  内容被裁、内容不可达、字号低于可读下限、后端细节过度暴露。
- 「好不好看」没有结论，也没有被声称有结论。
- 截图已抓取至 `.project-local/tmp/workbench-shots/`（16 张），但审计者**未对截图做视觉判读**
  （当前模型不读图），本报告结论全部来自 DOM 几何测量，不来自看图。

---

## 八、D-5 落地：闸门进入 CI（owner 2026-10-06 裁决「现在接，并先证伪」）

**CI 是否具备真实服务 + Chromium** —— 具备，不需要新 job：
`canonical-verify.yml` 的 `workbench-browser-e2e` job（ubuntu-latest）已用 lockfile 钉住的
playwright + `playwright install chromium`，并由
`design-lab/tests/test_workbench_design_layer_e2e.py:108-130` 起真实 loopback
`ProjectService`（OS 选端口、内存 token），注入的 env 恰好是本闸门读的四个变量。
该 job 在 branch protection 的 required contexts 里（实测 `gh api branches/main/protection`）。

**改动最小化**：`canonical-verify.yml` 本身**未改** —— 它被 SHA-256 钉在
`design-lab/config/task-ledger-r3.json` 与 `current-report-index.json` 两份账本里，
动它会破坏 pin。只改：

1. 新增 `design-lab/tests/test_workbench_overflow_gate.py`（复用既有 probe-driven 工具链探测与
   合成项目根 harness；Windows 下用 `Popen` + 文件重定向 + `wait(timeout)` 而非
   `capture_output`，避免管道句柄永久阻塞）。
2. `design-lab/scripts/verify_browser_e2e_ran.py`：`TEST_MODULE` → `TEST_MODULES`，
   对每个模块累计 ran/skipped/failed，任一模块 skip 或 fail 即 exit 1。该脚本未被任何账本钉住。

**纳入前先证伪**（同一合成根 harness，2026-10-06 实测）：

| UI | 结果 | 退出码 |
|---|---|---|
| pre-fix 检出（main `f2172744`） | `OV_SUMMARY clipped=5 stray=8 tiny=70` → `OV_FAIL` | 1（红）|
| post-fix 检出（本分支） | `OV_SUMMARY clipped=0 stray=0 tiny=0` → `OV_OK` | 0（绿）|

第二行同样用新写的 unittest 模块跑出 `OK`，第一行跑出 `FAILED (failures=1)`，
失败信息里带着真实裁切明细（`CLIPPED 390:settings +97px div.panel`）。
**所以 CI 上的绿不是因为合成项目空**，闸门在 CI 形态下仍然有牙。

**环境分歧：记录已被后续实测推翻（同日更正）**。本节原先写下：本机 Windows 跑
`test_workbench_design_layer_e2e.py` 在 `import reference` 步骤 20s 超时失败，
而同一 SHA `5dd36046` 在 CI（Linux）上该 job 实测 `success`
（run 37457793767，job 级结论，不是 workflow rollup），并标注"原因未查明"。

复验结果：在**主检出**上用 python 3.13.14 连续跑两次，**两次都通过**（3.496s / 3.235s，
`Ran 2 tests OK`）。失败没有复现，所以它**不是 Windows/Linux 分歧**。

两次之间的已知差异（不足以定因，只作线索）：失败那次跑在已删除的 worktree 里，
合成项目根长 139 字符（`C:\Users\ALEX\WorkBuddy\Worktrees\DESIGN-LAB\qoder-designlab-m1-closeout-20261005-12871b2c\…`），
且用 python 3.12.13 + venv312；复验这次在主检出，根路径更短，python 3.13.14 + venv313
（与投影记录的 `environmentFingerprint.python` 一致）。

保留原观测而不删，是为了不掩盖"曾经红过一次且原因不明"这个事实；
但结论口径改为：**不可复现的单次超时**，而非跨平台缺陷。
本闸门自身不受该步骤影响（只做导航 + 几何测量，不导入 reference）。

---

## 九、第二轮：真的读图（owner 2026-10-06「界面呢」）

§七 的诚实边界是"审计者未对截图做视觉判读（当前模型不读图）"。这个前提对后续执行者**不成立**，
所以本轮做了上一轮放弃的那一半：**headless Chromium 对真实 loopback 服务**抓 8 页 × 3 视口
（390 / 1280 / 1440）= 24 张 PNG，逐张判读，同一轮再跑几何闸门交叉核对。

### 测不到但看得见的缺陷

这一类的共同点是：内容没被裁、能滚到、字号也达标，所以 `CLIPPED/STRAY/tiny` 全为 0，
**上一轮的闸门对它们完全无感**。

| # | 缺陷 | 屏幕上读到的样子 | 根因 |
|---|---|---|---|
| V-1 | KPI 卡的 label 与来源说明挤成一行且无分隔 | `项目服务端项目台账读回，非统计猜测`、`设计系统资源登记的设计系统总数`、`服务版本服务自检读回` —— label 被当成说明的开头，读起来像坏掉的模板 | `.kpi small` 是 `inline`，`.kpi .trend` 是 `inline-flex`，同处一个行盒 |
| V-2 | 非计数值套用 35px 大数字排版 | `0.1.0-alpha.0` 在 1440 断成 `0.1.0-alpha.` + `0`；`OK` 看起来像"变好了的指标" | 所有 KPI `strong` 同一字号，不区分是不是计数 |
| V-3 | 一个药丸里同一个状态词出现两次 | `NOT_EXECUTED · 迁移 NOT_EXECUTED` | 设置页插值时只给后半截加了"迁移"标签 |
| V-4 | 平台符号错误 | Windows/Linux 上搜索位显示 `⌘K`，那类键盘上没有这个键 | 硬编码 macOS 符号 |
| V-5 | 设置页 ~950px 死白 | 面板是 `.three-col` 的**唯一子元素**，只占 1/3 宽，右侧整片空 | 单元素套了三列栅格 |

### 修复

V-1：label 与说明各自成行、各给权重（label `--ink`，说明 `--muted`）。
V-2：非计数值走 `.kpi strong.is-text`（19px 标签尺度），判定条件与 count-up 动画已有的"是否数字"一致。
V-3：两半分别标注为 `写入 … · 迁移 …`。
V-4：`/Mac|iPhone|iPad|iPod/` 判平台，macOS 保留 ⌘，其余显示 `Ctrl`。
V-5：设置页面板改为整幅，让 `.list-item` 已有的 `space-between` 把标签推左、状态药丸推右。

验证：`tsc --noEmit` 0、`vite build` 0、`unit.mjs` 0、`appshell.mjs` 0；
重抓 24 张并逐张复读，五处均已消失；同一构建重跑几何闸门仍
`clipped=0 stray=0 tiny=0` / `OV_OK`（即修复没有把裁切引回来）。

### 本轮**没有**改、留给 owner 的

- **语言策略**：三张能力卡标题是英文 `Research / Brand / Delivery`，而页面其余标题是中文。
  这是有意的双语层级还是漂移，属品牌判断，不由执行者定。
- **信息架构**：这三张卡内容全是坏消息（未接入 / 未读回），却摆在首页正中、与已可用面同权重。
- **侧栏**：12 项一层、圆点样式全同、不区分"已开放/未开放"；390 首屏**看不到任何导航入口**。
- **项目详情**：tab 行末位 `资源预检（非设计评审）` 顶到右边缘；INSPECTOR 里一个**空圆环**（只有描边 + 一个点）。
- **品牌蓝** `#316CFF` 仍无法承载白色正文（另案记录）。

### 一次副作用，以及对本节初稿一处错误归因的更正

本轮抓图留下 2 条项目记录：`.project-local/task-runtime/service/state.db` 的 `project` 表——

```
6474cccad81645df8993bfd806bb0c13  Closeout 1791294101099  2026-10-06T13:41:41Z
ec92b251ceee483099fe33ca06155513  Closeout 1791294601059  2026-10-06T13:50:01Z
```

它们会出现在仪表盘的「最近项目」里。**没有代为删除**：`asset / design_brief / design_direction`
等表按 project_id 关联，删行会牵动它们，且该库也可能有非本轮数据，所以留给 owner 决定。

**更正一处错误归因**：本节日初稿写成"`capture_workbench_screenshots.mjs` 不是只读导航，
任何一次截图运行都会改动真实项目状态，应当改成挂临时根"。**这个说法是错的。**
仓内官方入口 `scripts/capture_workbench_screenshots.py:121-130` 已经正是那么做的——
`tempfile.TemporaryDirectory()` + 写入合成 `AGENTS.md` + 把 `PROJECT_LOCAL_ROOT` 指向该临时目录，
再 `ProjectService(str(root))`。驱动脚本创建项目是**设计如此**（否则没有真实可截的详情页），
而它落在哪里由入口决定，入口已经隔离了。

真实原因是我自己写的临时 runner 用了 `python -m design_lab --project <仓库根> workbench`
且没有覆盖 `PROJECT_LOCAL_ROOT`，于是状态写进了主检出的 `.project-local`。
**结论不是"去修脚本"，而是"抓图一律走 `scripts/capture_workbench_screenshots.py`，
不要手起服务指向真实根"**。这段更正留在记录里，是为了不让一条错误的"待修项"被后人当指令执行。

---

## 十、D-2 的另一半：`.list-item` 拆分，以及一条被引用的依据并不存在

owner 已裁决「批准拆类」，因此这里记录**拆分前提**，而不是再次讨论要不要拆。

### 10.1 我先纠正自己引用过的依据

`docs/handoffs/DESIGN-LAB-WORKBENCH-VISUAL-AUDIT-HANDOFF-2026-10-06.md` 里我写"不可机械化"的
**第二个**理由是：改 B10 结构类名会破坏"由 B10 dom-diff 验证的 1:1"。2026-10-07 逐条查证后，
这个理由**不成立**：

- 全仓唯一会读 B10 参考稿的可运行代码是两份**一次性审计脚本**，位于
  `docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/harness/`：
  `w02-component-coverage.py:24-33`（正则抽类名，只 `print` + 落 JSON）、
  `w01-extract-and-compare.py:87`（只打印 `:root` 行）。两者**没有 assert、没有非零退出**，
  也**不在 CI 里**。
- 被当作证据引用的 `dom-diff.json` 是**冻结产物**（`.project-local/.../b10-1to1-handoff/audit/
  evidence/dom-diff.json:38-48`，比较的是类名与每类计数），**生成它的脚本不在仓内**。
- `style.css` 里"145 rules / 4 keyframes"只存在于注释本身（`style.css:421`、`:427`），
  没有任何机器可读副本。
- CI 里真实存在的硬数字断言只有一个、且与此无关：`.app-nav-item === 12`
  （`design-lab/tests/e2e/browser_design_layer_e2e.mjs:373`）。
- `list-item` 在 `design-lab/tests`、`apps/workbench/tests`、`scripts`、`packages`、`src`、
  `fixtures` 里**作为选择器出现 0 次**，所以改名不会撞到任何断言。

**结论**：阻止拆分的"1:1 保真闸门"是我继承来的一条口头依据，落不到可运行代码上。
真正的约束只剩两条：`build/main.js` 是无差异重建产物（CI `git diff --exit-code`），
以及 `.app-nav-item` 必须是 12 个。

### 10.2 拆分方案（下一波实施）

`list-item` 全部 70 处都在 `apps/workbench/shell.ts`，`class:'list'` 容器 30 处。两类语义混在
一个类上：

- **真正的列表成员**：`valueRow()`（`shell.ts:880-888`，用于 `:930`、`:2343`）——应成为
  `<li class="list-item">`，父容器 `<ul class="list">`；读屏软件因此能报出"共 N 项"。
- **独立的表单/操作卡片**：`shell.ts:1761`、`:1763`、`:1984`、`:1986`、`:2117`、`:2210` 这 6 处
  **直接 append 到 `.panel`**，不在任何 `.list` 内；`briefFieldRow()`（`:1463`）产出的
  `.list-item` 还被当作另一个 `.list-item` 的子元素用。这些若强改成 `<li>` 会落在 `<ul>` 外
  （非法 HTML）或产生 `li` 套 `li`。它们应改为新类 **`.row-card`**（保留现有边框/内距/悬停）。

即：`div.list` → `ul.list`、其成员 `div.list-item` → `li.list-item`；6 处游离卡片与
`briefFieldRow` → `.row-card`。这一步会改变**无障碍树**（多了 `list`/`listitem` 角色）而不改变
像素布局——`§五` 的溢出闸门与 `test_workbench_contrast_gate.py` 必须在改后重跑取证。

### 10.3 落地进度（2026-10-07）

**卡片半边已完成**：`.list-item` 的重载被拆成两个名字。卡片是**可机械识别**的那一半——
判据就是"自带 inline `display`"（列表成员从不这样），所以 `class: 'list-item', style: 'display:grid…'`
这个形状精确命中 7 处（6 个直接 append 到 `.panel` 的卡片 + `briefFieldRow` 的 row）。

拆分**不是改样式**：原来给 `.list-item` 的每一条规则都改成 `.row-card,.list-item` 成对选择器，
两个名字共享同一组表面声明，所以计算值不可能变。这一半的正确性由**真实浏览器闸门**取证
（溢出闸门 + 对比度闸门在改动前后都必须绿），而不是由"看起来一样"取证。
`test_workbench_css_single_definition.py` 里钉住两条防回退断言：`shell.ts` 不得再出现
`class: 'list-item', style: 'display:` 这个形状（否则 ul/li 改造会产出落在 `ul` 外的 `li`），
以及 `.row-card` 必须带着卡片表面那组声明。两条断言都在改动前的树上验证过会失败
（旧树命中 7 次、且完全没有 `.row-card`），不是空转。

**未完成的半边**：`div.list` → `ul.list`、成员 `div.list-item` → `li.list-item`。
63 处成员里有 30 个 `.list` 容器，且成员并非都在创建点就地内联（例如 `directionRow()`、
`briefRows` 先建成变量再展开进容器），所以标签必须跟着**归属**走而不是跟着创建点走。
这是下一步，且现在才真正可做：卡片已经搬走，容器里剩下的就都是成员。

---

## 十一、第三轮：D-2 落地后重读渲染，以及"绿"为什么仍然不算审计

**观测 SHA**：起点 `main` = `a3716751`（#243 D-2 半边落地后），修复落在
`d957e1e8` → `e5868976` → `1b165c24` → `7b7168d5` → `856e2cca` → `49a676e3`（PR #254 分支）。
**取证方式**：`scripts/capture_workbench_screenshots.py` 出图，清单绑 exact commit；
本轮 32 张图**刻意不提交**，写进 `.project-local/task-artifacts/ui-visual-audit-20261007/`
等目录——`docs/UI-CONVERGENCE-20260930/screenshot` 那 81 个路径自 2026-10-05 起
新增了 24.6 MB 的版本堆积，而仓 pack 已到 236.4 MiB（硬预算 256，见 PR #253）。

### 先更正我自己写过的话

我在 #254 的评论里写过「16 张逐屏读过，正是这样发现两个缺陷」——**当时只看了 4 张**。
把这句话补成事实之后（逐张看过 dashboard / projects / project-detail / preflight / settings /
creative-tools / deliverables / evidence，桌面与 390 各半），才发现的**不是同一个缺陷，而是另两个**：
预检页那个空面板和占位符截断。计数清单（`kpis` / `headings` / `unreadBack`）两次都没报过它们。
所以"我审计过了"的门槛是**看**，不是跑探针。

### 渲染看得到、闸门看不到的四个

| 编号 | 缺陷 | 为什么闸门看不见 | 处置 |
|---|---|---|---|
| R-1 | 项目详情 1280 下阶段导航九项溢出，最后两项**切在右边缘外**（资源预检切半、Handoff/Evidence 不可见） | `audit_workbench_overflow.mjs:66` 把"祖先有 `overflow-x:auto\|scroll`"记作 `scrollOk`——对 `.table-wrap`、移动端抽屉成立，对**主导航**不成立：没有滚动条也没有渐隐提示 | 已修 `d957e1e8`：`.stage-nav` 改为换行；并补结构断言 `test_workbench_stage_nav_reachability.py`（含"改动前那串字节必须被判违规"的证伪用例） |
| R-2 | 预检 / QA 的结果面板构造时为空，渲染成一个**大号空白边框盒**，挨着四个 `—` 计数，读起来像坏了 | 空面板不是溢出条件，任何几何闸门都不覆盖"空白但带边框" | 已修 `49a676e3`：构造即带一句说明，写明此处将读回什么 |
| R-3 | 任务全 ID 输入框唯一的示例写在 placeholder 里，而 placeholder **不能换行**，1280 下被截到只剩一个全角逗号——格式看得见，示例看不见 | 同上，不是溢出也不是对比度 | 已修 `49a676e3`：示例移到面板首条消息里（可换行、可选中） |
| R-4 | 390 下预检页首屏被四个空计数器占满，输入框掉到折叠线以下 | 布局密度不是任何现有闸门的对象 | **部分**：数字 35→26px、`.panel` 内边距收紧，卡片约 140→105px（`7b7168d5`、`856e2cca`）。再往下要二选一——手机端 KPI 改 2 列（会让项目详情那条长 hash 卡片反而变很高），或输入框先于计数器（破坏 `shell.ts:804` 记录的 B10 四计数器对齐意图）。这是两个**已记录意图**之间的取舍，留 owner 排序，不自行决定 |

另记一条不算缺陷的观察：`创作工具 / 交付中心 / 证据系统` 三个导航项在未选项目时渲染
**同一个空状态**，只差一个名词。是否该在空态下区分或收拢入口，属产品判断，同样留给 owner。

### 我第一版修错了对象，值得记下来

R-4 的第一次尝试改的是 `.kpi-card/.kpi-value/.kpi-note`，重拍后**像素完全没变**——
因为产物里根本没有这三个类：计数器是 `.panel.kpi` + `strong/small/.trend`
（`grep -o "kpi[a-z-]*" apps/workbench/build/main.js` 只有 `kpi` 与 `kpi-grid`）。
那三个选择器是 B10 原型留下的**死 CSS**。修法改成收紧数字与内边距，
并且**不**把 label 与出处注记合并回一行——那正是第二轮（§九）特意拆开的东西，
合并会把一个缺陷换成另一个。死选择器只记录、不删除。

### 本轮复核过、仍然成立的既有结论

§九 的 V-1…V-5 与 §二 的 F-1…F-8 在 `a3716751` 的渲染里逐屏确认已落地
（截断值进药丸 + `全称` 控件、`未读回` 而非 0、`0.1.0-alpha.0` 不再折行、
Windows 端不再显示 `⌘K`、设置页服务端诊断已折叠）。
owner 未裁决项不变：D-1 Inter、品牌蓝 `#316CFF`、中英标题政策、首页坏消息权重、
INSPECTOR 空环。

---

## 十二、审计面本身的洞：捕获清单只覆盖 12 条路由里的 8 条

§十一 写完回头看工具，发现一个更基础的问题：`capture_workbench_screenshots.mjs` 的
`PAGES` 只有 8 项，而 `shell.ts` 的 `ROUTE_VIEWS` 有 12 项。**研究洞察 / 品牌系统 /
设计领域 / 团队协作**四条路由从未被任何一轮截图渲染过——没被截过的页面同样不会在几何闸门里
报错，所以"界面已审计"这个结论从工具层面就是虚的。本轮把清单补全。

### 补清单时先撞出一个事实

第一版把 `工作台`（`hash: ''`）也加了进去，结果整轮捕获超时失败：
`locator('#route-view')` 43 次解析到 **存在但为空且 hidden** 的节点。
即落地页不是 `#route-view` 路由页，而是 app 外壳本身（由浏览器 E2E 覆盖）。
所以它被移出清单，并把原因写进注释——否则下一轮还会有人加回去。

### 新覆盖到的四屏（`53306b89`，12 张 @1280）

| 屏 | 实况 | 处置 |
|---|---|---|
| 设计领域 | 顶部横幅写「领域划分尚无独立后端模型」，而**同一屏下方 40px 处的能力卡自己反驳了它**：schema、`DOMAIN_PACK_SPEC_V2`、13 个域包目录都在仓内且有 `verify_domain_pack_v2.py` 校验，缺的只是 `GET /api/domains` 读回 | **已修**：横幅与 `shell.ts:162-165` 那条同样口径的英文注释都改成"模型在仓内、缺读回路由"；bundle 重新构建并核对含新串 |
| 品牌系统 | 这套屏里**唯一数据全真**的页：`4 设计系统 / 8 VI 模块 / — 活跃绑定` 均为服务端读回，8 张模块卡各重复同一句「视觉占位 · 资产与版本由服务端目录读回」；卡标题是英文（Logo / Color / Typography / Icon / Graphic Language / Templates …） | 未改。这是**中英标题政策未裁决**所覆盖的最大单页面积，政策一定就得整页改，属 owner 判断 |
| 研究洞察 | 虚线横幅 + PLANNED 卡，口径一致，无自相矛盾 | 无需动作 |
| 团队协作 | 横幅与卡一致：「本地单用户模型；协作是后续独立立项，不做假入口」 | 无需动作 |

另记一条小的视觉一致性问题，**本轮已修**（`d160676d`）：`capabilityCard` 把状态标签映射成
`BLOCKED→warn`、**其余一律 `info`**，于是 `PLANNED`（"此处服务没有答案"）用的是与真状态
同样饱和的主色实心药丸。而 `style.css:734` 早已为这件事定义了 `.tag.neutral`
（"非判定不得借用判定的重量"），仪表盘蓝图卡也已经在用它——只是这一个调用点没跟上。
现在按三态显式映射：`BLOCKED→warn`、`IMPLEMENTED→ok`、`PLANNED→neutral`，
重拍 `d160676d` 后核对：药丸变为描边弱化样式且仍可读，对比度闸门实跑通过。

### 补全后的覆盖

12 条路由视图中，11 条进入截图清单并被渲染读取，`工作台` 外壳由浏览器 E2E 覆盖；
`tsc --noEmit` rc 0、vite 构建 167.39 kB、`tests/unit.mjs` 与 `tests/appshell.mjs` 全通过，
且产物里同时核对到本轮新串与 §十一 的预检新串（防止补丁跨分支搬错 bundle）。

---

## 十三、一个跑了但没人看的量化审计：手机唯一导航控件只有 23px 高

`scripts/audit_workbench_ui.py` 早就存在，量的是**溢出、对比度、键盘可达、触摸目标、
可访问名、降级态措辞、控制台噪声**，跨 5 个视口共 65 个 scope。本轮第一次跑它：

```
AUDIT_SCOPES 65 violations=12 ok=False      # 修复前
  touch-target: 390 #/dashboard 1 targets under 24px
  touch-target: 390 #/projects 1 targets under 24px
  … 12 条路由每条 1 个
```

**全仓检索确认：没有任何 workflow 跑它**（`.github/workflows/` 里 `audit_workbench_ui` 零命中）。
所以这不是"缺陷刚出现"，而是**一个已存在、能发现、但没人执行的审计**——它守的东西一直是裸的。

### 报出来的数字当时还不可行动

违规串只有 `1 targets under 24px`，没有元素身份，12 条路由各报一次也看不出是同一个东西。
于是先改探针：`audit_workbench_ui.mjs` 现在连同**测量盒**一起报出身份：

```
touch-target: 390 #/brand-systems 1 targets under 24px:
  button#navToggle.nav-toggle.ghost-btn 62x23 "导航"
```

### 真凶是一次"好心的修复"留下的过校正

`#navToggle` 是 840px 以下**唯一**的导航入口（侧栏此时是 off-canvas 抽屉）。
`style.css:1033` 写着 `.nav-toggle{…padding:0 14px}`——那条注释说明它当初是为了解决
"作为全宽搜索框的 flex 兄弟被挤到只剩两个字、导航竖排换行"。
但真正解决挤压的是同一行里的 `flex:0 0 auto` 与 `white-space:nowrap`；
`padding:0 14px` 顺带把 `.ghost-btn` 的 `padding:10px 14px` 竖向清零，
于是控件从约 41px 高被压成 **23px**，低于审计用的 24px 触摸目标下限。
修法就是删掉这个多余的 padding 覆盖，两个真正的守卫保留。

### 修完与固化

```
AUDIT_SCOPES 65 violations=0 ok=True        # 五视口全量，修复后
```

并把该审计接进 CI：`design-lab/tests/test_workbench_ui_audit_gate.py`
（经 `run_python_tests.py` 发现，与 §八 D-5 同一套"不改被哈希钉死的 workflow"的路径）。
**双向证伪**：固定后的树上 `OK`（3.5s，两视口）；把那一行 padding 还原后同一测试变红，
且失败信息直接点名 `button#navToggle… 62x23`。测试还拒绝两种假绿：
stdout 出现 `AUDIT_BLOCKED` 判失败，`AUDIT_SCOPES` 缺失或为 0 也判失败——
空违规列表和"什么都没测"在报告里长得一样。


## 十四、#249 合并后重读 12/12：量化审计仍然看不见的三件事

基线 `main = af9a27cc`（#249 ul/li 已并入）。先复跑两套既有证据，确认合并没有把
"绿" 变成假绿：

```
AUDIT_SCOPES 65 violations=0 ok=True          # 1440/1280/1024/840/390 × 13 作用域
CAP_DONE shots=12                              # 12 条路由全部捕获，绑定该 commit
```

然后逐屏读渲染像素（1280 视口）。三处缺陷没有一处能被上述任何一道门表达。

### 1. 侧栏身份块在四条路由上根本不在屏幕上

`.sidebar` 是 `.app{display:grid}` 的**被拉伸网格项**：它的高度等于整篇文档的高度，
而 `.sidebar-footer{margin-top:auto}` 因此被推到文档底部。页面一旦超过视口，
"本地单用户 / 无身份路由 · 未读回" 这块身份读回就落在折叠线以下——用户滚到页面底
才能看见自己是谁，而首屏看不见。

用像素计数把范围量化（x10..270 × y700..795 亮度 >90 的点数，`af9a27cc` 捕获）：

```
NO-META   dashboard  project-detail  brand-systems  settings     (4/12)
HAS-META  其余 8 条路由，bright=1274（完全一致的同一位置）
```

发现者是并行只读子智能体，但它把范围报成"仅 brand-systems 一屏"——**错**，实测是
四条。修法是把它变成 `position:sticky;top:0;height:100vh;overflow-y:auto`，也就是
`<=840px` 抽屉早就在用的同一套声明；修复后同一测点 **12/12 HAS-META**。

### 2. 台账只有一个项目时，三个 picker 路由仍是一屏死路

创作工具 / 交付中心 / 证据系统共用 `projectPickerPanel`。占位 option
（`选择项目（共 1 个）`）默认选中，于是页面显示"未选择项目 …… 没有可读回的记录"
加一个空态环——而**同一次读回刚刚告诉我们台账里只有这一个项目**。
现在只有一个项目时不再放占位项，直接打开它；离线路径的 `OFFLINE.projects` 是空数组，
所以这条分支只可能由真实读回进入，不会把演示数据当读回展示。

这道检查已经做成审计项 `picker-dead-end`，并且**先证伪再用**：在 `af9a27cc` 的旧
bundle 上跑新审计器，`AUDIT_SCOPES 13 violations=3 ok=False`，三条正是
`#/tools`、`#/deliverables`、`#/evidence`；换成修复后的 bundle 则
`AUDIT_SCOPES 65 violations=0 ok=True`。

### 3. 固定 4 列的 KPI 网格，和一个自己打脸的计数注释

`.kpi-grid{grid-template-columns:repeat(4,minmax(0,1fr))}` 对四个计数器的路由是对的，
但品牌系统只有三个，右侧于是留下约 240px 的空洞，卡片行的右边缘和下方模块网格对不齐。
改为 `repeat(auto-fit,minmax(210px,1fr))`：三个就铺三份，四个仍铺四份。

同一屏的 `VI 模块` 计数卡写着 `Logo / Color / Typography / … / Assets`——数字说 8，
注释用省略号藏掉 8 个里的 5 个。改为直接 `BRAND_MODULES.join(' / ')`，注释与常量不
再可能漂移。

### 一条被推翻的怀疑

读 `project-detail` 时我以为第四张计数卡把 `direction-6de…4646c6` 截断了（旁边的
设计层契约面板同一字符串多出一行 `c6`）。实测该 direction_id 全长 42 字符，卡片里
是完整的，面板那行 `c6` 只是它自己更窄导致的换行点不同。**不是缺陷，记录以免重查**。

修复后（`438dbaa7`）：`AUDIT_SCOPES 65 violations=0 ok=True`，身份块 12/12，
证据系统首屏直接给出 `1 briefs / 1 directions / 4 设计系统 / 0 交付包` 与证据绑定链
四行真实读回。

### 追加（同一波次，#258 后续三个 commit）

继续逐屏读 `8225d01a`/`820881a9` 的 12/12 捕获，又找到两处"卡片说了但没给值"：

1. **共享输入卡是空的，却顶着"服务端环境读回"的标题。** 创作工具页把
   `environment.shared_inputs` 直接 map 成 `<li>`，零条时就是一个空框——看起来像
   "服务查过了，什么都没有"，而实际语义是"这个服务根没有声明任何外置输入"。
   现在两处调用点收敛成一个 `sharedInputRows()`，零条时输出与系统设置页同一句话：
   `尚无外置输入 / 服务未返回 shared_inputs`。
   **审查看这里必须记住**：捕获跑在合成的临时根上，机器本地值（路径、共享根）为空是
   捕获环境的属性，不是产品缺陷；它能证明视图会渲染，不能证明数据正确。
2. **两样东西塞进三栏网格。** `.three-col{repeat(3,minmax(0,1fr))}` 对 3 的倍数是对的，
   但"未开放"三页（研究洞察 / 设计领域 / 团队协作）各只有 **1 张**能力卡，
   创作工具的宿主 Adapter 网格只有 **2 个**宿主——剩下的 1/3 行就是死白。
   新增 `.card-flow{repeat(auto-fit,minmax(280px,1fr))}` 只给这两类站点用：
   1 张铺满、2 张平分、3 张与原来一致，390px 下靠 280px 下限自动单列，不需要媒体查询。
   `820881a9` 的 1280 捕获已确认研究洞察的卡现在与它上面的横幅同宽。
   宿主 Adapter 那一行在首屏折叠线以下，未单独截图复核，按同一机制推定。

`blueprintCards`（仪表盘，2–3 张）故意**没有**改：它常态是 3 张，改成 auto-fit 会让
1024 宽度从"三列等宽"变成"2+1 参差"，那是拿确定的改动去赌一个只在登记表查不到时才出现的
空洞。

复测：`8225d01a` 与 `820881a9` 各跑一次全量审计，均
`AUDIT_SCOPES 65 violations=0 ok=True`（1440/1280/1024/840/390）。

## 十五、首屏工作台从来没被任何一次捕获拍过

§十二 补的是"12 条路由里只捕了 8 条"。这次往上追一层：`capture_workbench_screenshots.mjs`
的注释写着首屏 `''`（工作台）"由 browser E2E 捕获"，所以不在这个循环里。
**那句话是错的**：`browser_design_layer_e2e.mjs` 只在**失败**时写 PNG（`fail.png`）。
一次全绿的运行里，产品的主操作面从未被渲染给人看过。

补法不是加一行 `goto`。`show()` 里 `workspace.hidden = !connected`，而 token 只活在
当前 document 的闭包里——`page.goto` 重新加载文档必然拍到的是连接表单，却会被当成
"工作台"。所以该页先同文档跳到 `#/dashboard` 再跳回 `''`，让 hashchange 真的触发、
token 不丢。清单里同时记下每屏量的是哪个宿主（`#workspace` / `#route-view`）。
现在 `CAP_DONE shots=65`（13 面 × 5 视口）。

### 拍出来才知道：首屏是另一套壳

`26-workbench@1280.png`：左侧导航是 legacy `.app-nav`（纯文字项、底部"本机已连接"），
而其余 12 条路由全是 B10 `.sidebar`（圆点项、底部"本地单用户 / 无身份路由 · 未读回"）。
`00-workbench@390.png`：首屏在 390 下的导航变成**贴在屏幕底部、横向滚动**的条目条，
一屏只露出 5 项（工作台 / 仪表盘 / 项目 / 研究洞察 / 品牌系统），第 6 项起在屏幕外；
路由页在 390 用的是顶部「导航」抽屉 + off-canvas。
溢出审计把"可横向滚动"记成 SCROLL_OK，所以这条在量化报告里永远是绿的——
捕获里看不到任何指示还有右侧内容的 affordance（无渐隐、无箭头、无计数）。

代码上这是刻意的（`show()` 的注释：legacy header/main/footer/nav 拥有空哈希视图，
B10 `.app` 拥有路由页），所以**不是 bug，是一次未收敛的双壳**：同一个产品在首屏和
其余页面给用户两套导航、两种身份脚注、两种移动端范式。这属于方向裁决，不该由我替
owner 定，记录在此并列入待裁清单：

> **待裁 D-6**：首屏工作台是否并入 B10 壳（统一侧栏 + 身份脚注 + 移动端抽屉）？
> 若保留 legacy 壳，390 底部导航条需要可见的横向滚动 affordance。
> 这与既有的 **D-4**（路由页 stage-nav 在 390 横向滚动）是同一类问题的两个面，
> 但 D-4 只覆盖了路由页；首屏那条此前无人拍过，所以也没进过任何决策清单。

本轮没有改首屏的任何样式。

### 追加：D-6 的移动端那一半已由 CODEX 分支处理，本仓接并

上一节末句"本轮没有改首屏的任何样式"只对那一轮成立；下一轮改了，记录如下。

`qoder/designlab-nav-cue-pinned-20261007` 并入 CODEX 的首屏底部导航滚动提示
（`has-scroll-more` + `›`，滚到末尾或不溢出时隐藏，JS 断点与其配对的样式表规则同为 760px）。
其字节在隔离副本里逐哈希复现：`shell.ts 8de8f983…` / `style.css 07973804…` /
`build/main.js fc725c57…`（与它报告中的 SHA-256 一致）。

接并时真实渲染查出该提示**会随菜单一起滚走**：`.app-nav` 本身就是滚动容器，
绝对定位的 `::after` 贴的是内容盒。按箭头自身颜色计像素，
`scrollLeft=0/300/600` 处为 **13 / 0 / 0**，而右侧仍有 670 / 370 / 70px 菜单未露出；
改为 sticky flex item 后为 **10 / 10 / 10**。守卫写进
`test_workbench_sidebar_pinning.py`（sticky + `right:0` 必在，`position:absolute`
与可吞点击的覆盖层必无），并做了致死验证。

两条方法论教训记在此处，因为它们都曾产出过看似干净的假结论：
(a) 用"右边缘 40px 条带是否逐像素相同"来问"箭头还在不在"是错的度量——条带里同时滑过菜单文字；
(b) 合成复现页漏掉 `*{box-sizing:border-box}` 后，与真机截图在"滚动起点"这个已知真值点上矛盾，
说明复现不忠实；补上重置、复现与真机一致之后，其余数据点才可用。

**未做**：真实 app 在非零 `scrollLeft` 下的中段实测（现有捕获/审计 harness 不滚动）。
D-6 的另一半——首屏是否并入 B10 壳——仍是 owner 裁决，本分支未替它决定。

## 十六、证据面收到桌面端：一条需要写清代价的取舍

owner 2026-10-07 指令："优先跑通全量执行桌面端电脑端UI，先删除手机端其他端等"。
经确认取 **"只收口径，不删代码"**，且"其他端"仅指手机 / 平板（未开放路由与宿主入口卡保留）。

### 改了什么

9 处宽度默认值，全部是口径，不是能力：

| 位置 | 旧 | 新 |
|---|---|---|
| `audit_workbench_ui.mjs` / `capture_workbench_screenshots.mjs` | `390,768,1280,1920,2560` | `1280,1920,2560` |
| `audit_workbench_contrast.mjs` | `1440,390` | `1440,1920` |
| `audit_workbench_overflow.mjs` | `1440,1024,390` | `1440,1280,1920` |
| `scripts/audit_workbench_ui.py` / `capture_workbench_screenshots.py` | 同上五宽 | `1280,1920,2560` |
| `test_workbench_ui_audit_gate.py` | `390,1280` | `1280,1920` |
| `test_workbench_overflow_gate.py` | `1440,1024,390` | `1440,1280,1920` |
| `test_workbench_contrast_gate.py` | `1440,390` | `1440,1920` |

CI 的证据面由这三道 python 门决定（`canonical-verify.yml` 不写宽度，且被 SHA-256 钉死，
本轮未触碰）。量化作用域从 13 面 × 5 宽 = 65 缩到 13 面 × 3 宽 = 39。

### 没删什么，以及代价

7 个宽度媒体查询、off-canvas 抽屉、`#navToggle`、§十三 修好的 23px 触摸目标、
#259 刚并入的移动端滚动提示、审计里的 `touch-target(<=430)` 与 `palette(<=840)` 检查、
`test_workbench_sidebar_pinning.py` 的抽屉断言——**代码全部留在仓里**。

代价必须说明白：新宽度里已无 <1024，所以这些移动专用分支从此在 CI 中**不被触发**。
也就是说 #254 与 #259 那两次修复的门禁保护消失了，未来任何一次移动端回归都不会变红。
这是"不删代码"的直接后果，不是疏漏。

### 需要恢复移动证据时（无需改代码）

三道门都读环境变量，不改代码即可把口径调回去。已实测：

```
UI_AUDIT_WIDTHS=390,1280 python -m unittest discover -s design-lab/tests \
  -t design-lab/tests -p 'test_workbench_ui_audit_gate.py'      # → OK
OV_WIDTHS=1440,1024,390  … -p 'test_workbench_overflow_gate.py'
CT_WIDTHS=1440,390       … -p 'test_workbench_contrast_gate.py'
```

### 本轮实测

| 运行 | 结果 |
|---|---|
| 三道门在新桌面默认值下 | overflow OK（42.8s）、contrast OK（57.2s，2 项）、ui audit OK（3.9s） |
| 三道门把移动宽度调回去 | overflow OK（42.7s）、contrast OK（57.7s）、ui audit OK（4.9s） |
| 量化审计默认口径 | `AUDIT_SCOPES 39 violations=0 ok=True` |
| 捕获默认口径 | `CAP_DONE shots=39`，`@390` / `@768` 计数为 0 |

即：口径收窄没有让任何一道门变红，也没有让任何一道门失去可执行性——
它只是不再在 CI 里覆盖 <1024。
