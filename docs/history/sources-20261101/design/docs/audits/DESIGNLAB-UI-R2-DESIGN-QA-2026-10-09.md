# Design QA Verdict: Pass with warnings

对象：DESIGN-LAB Workbench 桌面 UI 本批（三入口壳层、可选配色主题、能力目录前置过滤、
`#/intake` `#/analysis` `#/plan`、`#/states` 状态矩阵、`#/components` 组件规范）。
判定基准：R2 包 `docs/history/taskpacks/20261009-r2-inputs/ui-r2/specs/01_UI_SCHEME.md`
＋ `specs/design_tokens.json` ＋ 包内 22 张效果图，与仓库 `DESIGN.md`。

## Summary

本批**已落地部分**在两套配色下都能通过仓库自己的确定性闸门（19 条路由 × 2 主题：0 裁切、
0 不可达、0 小于 11px；对比度 AA 双主题通过），实拍与几何读数一致，没有发现深浅主题之间的
语义漂移。真正的偏差是**覆盖度**：R2 的信息架构里有五块在本批完全不存在（资产类型 tabs、
已选条件条、450px 详情抽屉与独立地址、草稿自动保存、制作记录与任务条），`#/intake` 只做到
R2 §6 四组输入里的两组。这些不是还原度缺陷，而是尚未开工的增量，已按卡折进
DL-UI-U03/U04/U05 与 DL-FINAL-T08/T09，不在本文件里当作"已通过"。

审查过程中被**推翻**的两条初判，连同推翻它的测量一起记在下方"已排除"一节：一条来自我
自己的裁剪图误读，一条来自对未接线控件的猜测。

## Evidence Reviewed

- 设计契约：`DESIGN.md` §1–§4（含 2026-10-09 复测后的实测存量）、
  `docs/taskpacks/20261009-r2-ui/CROSSWALK.md`（R1/R2 取舍与三处待 owner 裁决的令牌冲突）。
- 源视觉真值：R2 `specs/01_UI_SCHEME.md` §2/§3/§4/§5/§6/§7/§9/§10/§11；
  R2 效果图 22 张（`.project-local/task-artifacts/taskpacks-20261009-r2/extracted/screens/`），
  其中浅色基准 `14_catalog_light.png`。
- 渲染实现：`.project-local/task-artifacts/ui-first-20261009/screens/default/` 19 张 @1920
  ＋ 16 张 @960；`screens/ui2026-light/` 19 张 @1920（**本批重拍**，见 Blockers 前置说明）。
  两套 manifest 的 subject 同为 `apps/workbench/build/main.js`
  sha256 `10776c22…`、307355 字节。
- 视图/内容一致性：两套 manifest 的 `rendered.host/#route-view`、`headings`、`kpis` 逐条相同，
  即两主题渲染的是同一 DOM，差别只在令牌。
- 确定性报告：`OV_OUT` 溢出/几何报告（两份，各自带 `uiPalette/uiScheme`）、
  对比度 AA 报告（`test_workbench_contrast_gate` 的双主题用例）、
  `.project-local/runs/design-review/.design-qa/reports/design-debt.json`（findings=706）、
  `scripts/design_debt_baseline.py --check` = `DESIGN_DEBT_BASELINE=PASS`、
  `scripts/archive_ui_desktop_reconcile_20261009.py --check` = 17 屏 / 18 路由 / 53 断言 / 37 令牌。
- 源码：`apps/workbench/shell.ts`（`ROUTE_VIEWS`、`STATE_SPECS`、`renderCapabilityLibrary`、
  `intakeForm`、`analysisPanel`、`planComposer`、命令面板）、`apps/workbench/style.css`
  （`:root` 令牌块 + 两个 `:root[data-palette=…]` 主题块 + 本批新增组件块）。

## 先说证据本身的缺陷（已修）

- Severity: blocker（针对**证据**，不是产品）
- Evidence：`screens/ui2026-light/screenshot-manifest.json` 旧副本记的 subject 是
  `bundleBytes=281680`、sha256 `4ce45da3…`、generatedAt 15:00，而当时的 bundle 已是
  `307355`/`10776c22…`；且只有 16 张，缺 `intake`/`plan`/`analysis` 三屏。
- Observed：浅色主题下本批新增的三屏**没有任何同字节实拍**。
- 影响：上一版浅色证据不能为本批背书。
- 处置：用同一隔离入口重跑浅色集，现 19 张全部绑定 `10776c22…`；`SUBJECT.json` 逐条记
  `head` ＋ `worktree_digest` ＋ `apps_workbench_dirty=true` ＋ deviation 原文（tracked 的
  `scripts/capture_workbench_screenshots.py` 仍拒绝未提交 bundle，本会话无 commit 授权，
  守卫未动）。
- Verification：新 manifest `uiPalette=ui2026 uiScheme=light shots=19 subject=10776c22…`。

## Blockers

无。本批已落地的界面没有阻止设计验收的缺陷。

## Major Issues

### 1. `#/intake` 只覆盖 R2 §6 四组输入中的两组
- Severity: major
- Evidence：`screens/ui2026-light/16-intake@1920@ui2026-light.png` 与
  `screens/default/16-intake@1920.png`；`shell.ts` `intakeForm()`。
- Observed：页面上是「需求与目标」「参考素材与职责」两组；R2 §6 表的
  **交付目标**（分析 / 目标包 / 原生工程 / 最终媒体 + 工具、格式、尺寸、时长）与
  **能力与知识**（资产 revision、获准知识 revision、教学需要）都没有落点。
  右栏在 1920 下约 60% 高度是空的——正是这两组该在的位置。
- 影响：从输入面进不到交付范围，`#/plan` 的目标包只能靠默认值，U04 的"输入→分析→目标包"
  旅程断在第二环。
- 建议修法：按 R2 §6 的分组补两块面板进右栏（沿用 `.intake-grid` 的既有卡片），
  交付目标只列**已有资格证据**支持的路线，未知项显示"待核验"而不是灰掉消失。
- Verification：新屏进 `capture_workbench_screenshots.mjs` 的 PAGES 与 overflow 的 ROUTES，
  两主题各一张实拍。
- 归属：DL-UI-U04（已写入 `currentExecution` 的 notes）。

### 2. 强约束与偏好无法分别保存（合同缺口，不是前端缺口）
- Severity: major / needs-design-decision
- Evidence：`#/intake` 页面自述"简报合同记录 title / goals / constraints /
  reference_asset_ids 四项；下面的输入属性会编排进 constraints 文本，不是四个独立字段"。
- Observed：R2 §6 要求"强约束与偏好分别保存"；当前简报 schema 只有一个 `constraints` 文本。
- 影响：前端无论怎么改分组，落库都会把两者混成一段话，下游无法据此判定违约。
- 建议修法：先裁决 schema（新增 `hard_constraints` / `preferences` 两个数组，或声明
  本轮仍走合成文本并把它标成已知损失），再动界面。不自行扩 schema。
- 归属：owner 裁决 + DL-FINAL-T07。

### 3. R2 §4/§5 的目录三件套缺失：资产类型 tabs、已选条件条、详情抽屉与独立地址
- Severity: major
- Evidence：`renderCapabilityLibrary()` 现有的是关键词 + 5 个前置过滤 select + 表格；
  `grep` 无 `drawer`/`asset-type` 相关实现，路由表里也没有详情地址。
- Observed：R2 §4 的"资产类型 tabs / 已选条件与结果数 / 卡片或列表切换"和 §5 的
  "450px 右侧抽屉、保留目录领域·条件·位置和焦点、完整详情有独立地址"都未实现。
  当前"查看详情"是行内展开，关闭即回到列表，无法把某条详情重新找回来。
- 影响：目录→详情→"用于本次制作"这条 R2 主旅程只能走一半。
- 建议修法：抽屉用 `#/<route>/<id>` 形式的可分享地址；已选条件条上每个 chip 可单独移除，
  计数按当前组合去重（R2 §4 末段）。
- 归属：DL-UI-U03 + DL-FINAL-T08。

### 4. 草稿自动保存与"正在保存/已保存/保存失败"缺失
- Severity: major
- Evidence：`intakeForm()` 只在提交时写服务；页面文案"提交即写入本机服务"。
- Observed：R2 §6 要求变更自动保存到正确任务身份并显示三态，未保存离开给恢复机会。
- 影响：长表单中途离开即丢失，且用户无法区分"已存"和"没存"。
- 建议修法：接既有草稿接口（不新建第二套存储），三态各一条真实状态；服务不可用时显示
  失败而不是静默本地保存。
- 归属：DL-UI-U04。

### 5. R2 §7「制作记录与待继续」与页面底部任务条缺失
- Severity: major
- Evidence：`ROUTE_VIEWS` 的"分析与制作"入口下只有 新建需求 / 分析与方案 / 目标生成包；
  无记录列表、无任务条组件。
- Observed：R2 §7 要求找回工作的入口（任务、领域标签、真实状态、最近确认点、继续操作）
  ＋ 底部持续任务条（只在实际存在任务时出现）。
- 影响：跨页浏览后无法回到"哪一个任务"，U05 的恢复语义没有承载面。
- 建议修法：任务条只在真实存在当前/待继续任务时渲染；R2 原型里的三条示例记录不得当作
  真实排队状态。
- 归属：DL-UI-U04 + DL-FINAL-T09。

### 6. 全局搜索只有路由启动器，没有 R2 §9 的三对象组
- Severity: major
- Evidence：`shell.ts:5320-5356`——命令面板项是 `dataset.go` 路由，`input` 事件按标签子串
  过滤，`Ctrl/Cmd+K` 开合、Esc 归还焦点（这两点已符合 §9）。
- Observed：没有能力资产 / 制作记录 / 成果三组，没有按权限过滤的服务端检索，也没有
  "对象类型与去向"。
- 影响：§9 的"搜索后进入正确对象"目前只能到"进入正确页面"。
- 建议修法：分组渲染 + 先按权限过滤再计数返回；无权限对象不得出现标题或计数。
  面板不得宣称它做的是远程检索。
- 归属：DL-FINAL-T08。

### 7. 11 个领域没有成为可导航入口
- Severity: major
- Evidence：`ROUTE_VIEWS` 里"能力资产"入口下是 能力目录 / 设计领域 / 品牌系统 / 创作工具；
  R2 §2 要求二级导航直接列出 11 个领域并读现有领域配置与稳定 ID。
- Observed：领域是一页汇总，不是一组入口。
- 建议修法：领域项从既有领域配置生成（含稳定 ID），空领域保留入口显示空结果，不因零条
  移除分类（R2 §2 末段）。
- 归属：DL-UI-U03。

## Minor Issues

### 侧栏底部区域没有可发现性，且闸门看不见"重叠"
- Severity: minor / needs-design-decision
- Evidence：`default/14-states@1920.png`、`ui2026-light/18-analysis@1920@ui2026-light.png`
  里导航溢出指示（▼）落在"辅助"分组线附近；几何闸门两主题 19 路由均报 0 裁切 / 0 不可达 /
  0 小于 11px，即它**没有**任何元素间重叠断言，这类问题目前只能靠人眼。
- Observed：我在实拍上看出"▼ 压在分组标题同线""主题说明被折到视口外"两件事，其中第二件
  随后被源码否定（见"已排除"3）。第一件没有测量支持，因此不作为缺陷断言，只作为断言缺口记账。
- 建议修法：给闸门补一条 rect 重叠 + `elementFromPoint` 断言（先证明栽进去的能量红），
  再据此判断侧栏底部是否需要常驻可见区。R2 §3 只写了反向要求（内容保留底部留白，
  最后一个按钮能滚动到任务条上方），侧栏自身没有写，所以这是设计缺口，需要 owner 定。
- 归属：DL-FINAL-T08（已写入 TASK-CARDS 的 QA 增量段）。

## Design Debt

- 本批 `字面 px` 存量 516→532（+16），实测全部落在 `apps/workbench/style.css` 的新组件块；
  色值成员换了一对（`#1d4fc4` 令牌化后登记行删除，新增 `#4bafff` 即 `--tag-info-from`），
  总数仍 26。两处 `adjudication` 均留给 owner，代理未填。已写进 `DESIGN.md` §4，
  `--check` = `DESIGN_DEBT_BASELINE=PASS`。
- 外部 design-review 插件报 706 条（hard-coded-color 38 / functional-color 14 /
  px-magic-number 625 / custom-shadow 27 / tailwind-arbitrary-value 2），与仓库规则读数
  （26 / 532 / 24）不同源：插件按声明计数、仓库按"非令牌且非注释"计数，且本仓库无 Tailwind。
  分歧逐条仍记在 `docs/audits/DESIGNLAB-EXTERNAL-DESIGN-REVIEW-2026-10-09.md`，不合并读数。
- 组件拆分：R2 §11 列的 25 个组件名里，本批真正成形的只有 AppShell/PrimaryNav/ContextNav/
  GlobalSearch/TaskRecordList(缺)/BriefForm/DeliveryTarget(缺)/StepNavigation/
  ConnectionStatus/Empty·ErrorState 等一部分，其余仍以 `shell.ts` 内联函数存在。
  不要求照搬组件名，但要求同一语义不再各写一份——已折进 DL-FINAL-T08。

## Acceptable Differences

- 浅色主题把导航侧栏一起翻浅：与 R2 浅色基准一致（实测 `14_catalog_light.png`
  侧栏 (234,240,246)、画布 (244,247,250)，同为浅色，仅差一档表面层级）。
- `--color-secondary` / `--color-info` / info 药丸填充在浅色下重指到包自己声明的 light accent：
  深色下的 `#4BAFFF` 压白底只有 2.37:1，被 AA 闸门按路由报红后修正，取值来自包，未造新色。
- 状态矩阵 11 项 ≥ R2 §10 的 8 项：多出的 未读回 / 未判定 / 取消已请求 是仓库真实词汇，
  不是照抄原型。
- 手机端（R2 §3 <768 列与底部四入口）：owner 决定 FROZEN_DEFERRED，本批不实现、不验收。

## 已排除（初判被测量推翻，留作方法记录）

1. "浅色主题下能力表被挤成一列列竖排文字" —— 来自我对一张裁剪图的读法。三个独立测量都反对：
   浏览器内 rect 探针（rail 280 / main 1584 / table 1546 @1920，两主题逐路由相同）、
   PNG 墨迹横向范围（default 19..1619、light 28..1619）、两主题整幅实拍。产品没有这个缺陷；
   错的是我的裁剪回读。**几何断言优先于图片回读**这条规则再次成立。
2. "顶栏搜索框是装饰" —— `#openPalette` 有 `onclick`、`Ctrl/Cmd+K` 与 Esc 归还焦点，
   已接线；真实缺口是它只检索路由（见 Major 6），不是假控件。
3. "浅色主题下主题控件的说明文字被折到视口外" —— 源码 `themeControlNodes()` 是
   `spec.schemes.length > 1 ? '' : spec.missingScheme`：ui2026 声明了浅色，所以那一行**本
   就该是空的**；design-lab 没声明浅色才印"这套色板没有声明过浅色值，不自造一套"。
   两主题各自正确，不是折叠。
4. "组件规范页的色块在浅色下仍显示深色值" —— 直接取像素：浅色实拍
   `15-components@1920@ui2026-light.png` 在色块带 (y=300..330) 上依次为
   (244,247,250)/(255,255,255)/(240,245,250)/(207,218,229)，正是 `--uif-light-*` 四档，
   色块刷的是当前主题算出来的值。

方法记录：本文件里所有"看出来的"结论都被改写成可复算的测量（rect、像素、源码行）之后才保留；
四条初判在这一步被推翻。缩放后的整幅预览不足以支撑还原度断言，这一点比任何单条发现都更该记住。

## Automation Artifacts

- Expected（源真值）：R2 `extracted/screens/*.png` 22 张；未做像素级 diff（本仓库无 R2 基线快照，
  且 R2 效果图是设计意图而非像素合同）。
- Actual：`screens/default/`（19@1920 + 16@960）、`screens/ui2026-light/`（19@1920，本批重拍）。
- Diff：无图像 diff——两套实拍主题不同源，逐像素差会把"换了颜色"当成缺陷；改用
  `rendered` 结构等价 + 两主题各自的 rect 普查作为对照。
- JSON：`browser-e2e/workbench-overflow-gate.json`（含 `uiPalette/uiScheme` 与 per-route
  `layout`）、`browser-e2e/*contrast*.json`、`runs/design-review/.design-qa/reports/design-debt.json`、
  `task-artifacts/ui-first-20261009/reconcile.json`。
- 本闸门化了两件此前只能靠人眼的事：溢出/几何闸门现在**逐主题**跑（此前只跑默认配色），
  并在每条路由记录 `railW/mainW/mainLeft/tableW/narrow760`。

## Verification Checklist

- [x] 两主题 @1920 实拍均绑定当前 bundle（`10776c22…`），manifest 各自记 subject
- [x] 溢出/几何闸门两主题各跑一遍：19 路由 × 2 = 0 clipped / 0 stray / 0 tiny
- [x] 对比度 AA 两主题各跑一遍（含浅色专用用例，回执点名自己的 subject）
- [x]  typography / spacing / colors-tokens / assets / copy 五个面逐条看过：见 Major 1–7 与 Minor
- [x] 状态：default / hover / focus-visible / disabled / loading / empty / unread / unknown /
  offline / forbidden / error / timeout / conflict / queued / cancelled —— `#/states` 11 项齐，
  disabled 用非透明度去 cues（AA 实测驱动）
- [ ] 键盘全程走查、减少动画、200% 缩放：需要真人，未做，不代签
- [ ] 真实宿主执行与真人 Jury（E3/E4）：不在本批授权内
- [x] 无新增未登记字面色：`design_debt_baseline --check` PASS，26 处逐条在案
- [ ] commit / push / CI：本会话无该授权，全部改动仍是工作树未提交状态

## 批次后追记（同日第三批，本报告不改判，只标已消化项）

判定仍是 **Pass with warnings**：上面列的是当时那批字节的覆盖差，追记只说明其中两条已经做掉，
避免下一个人按旧清单重复派工。新证据绑定重建后的 bundle
`fd0e67d9…`（314,344 字节），两主题各 19 张实拍、各 19 路由 0 裁切 / 0 不可达 / 0 小于 11px。

- **Major 1（输入四组缺两组）→ 已落地。** `#/intake` 现在是六个 h3：
  需求与目标 / 参考素材与职责 / **交付目标** / **能力与知识** / 已提交的简报。
  交付目标四档各自标注接线状态并注明依据（分析与方向=已接线、目标生成包=只排队、
  原生可编辑工程=未取证、最终媒体=未接线）；能力与知识读 `GET /design-layer` 的
  现行方向 revision、活动绑定与简报版本链，获准知识 revision 明确标未接线并说明归 ArcheAxis，
  教学需要禁用并说明属 U06/U07。两组输入一律编排进合同真正记录的那条 `constraints`，
  没有假装合同长出新字段。
- **Major 3 的一半（已选条件条 + 去重计数）→ 已落地。** `#/capabilities` 增加
  `#capability-active`：每个不等于「全部」的取值一枚可单独移除的 chip，关键词也算一枚；
  「清除检索条件」只清检索，不清领域选择、不删任务（§4 末段那条边界）；
  结果计数改为按 ID 收敛，并在有重复时说明去掉了多少条。
  §4 剩下的资产类型 tabs 与 §5 的 450px 抽屉／独立地址仍未实现，Major 3 不整条关闭。
- **证据侧新增一条改进**：溢出/几何闸门的报告现在自带 `subject.bundleSha256/bundleBytes`。
  此前它只记主题与宽度，一份「0 裁切」无法证明测的是哪一版字节；账本写入器现在按
  报告里的 subject 与磁盘上的 bundle 是否一致来定 PASS/FAIL，测旧字节即 FAIL。
- 仍开着的：Major 2（强约束/偏好分字段，待 owner 裁决 schema）、Major 4（草稿自动保存）、
  Major 5（制作记录与任务条）、Major 6（全局搜索三对象组）、Major 7（11 领域二级入口）、
  Minor（闸门缺元素重叠断言），以及键盘／减少动画／200% 的真人验收。

## 第四批追记（同日，R2 §5 详情地址 + 遮挡断言）

新证据绑定 bundle `5af19a1e…`（320,873 字节），两主题各 20 路由、各 20 张实拍。

- **Major 3 的另一半（450px 抽屉 + 独立地址）→ 已落地。** `#/capabilities/<id>` 成为真实地址，
  沿用 `#/projects/<id>` 的加固形状（解码后校验；实测 60 条 id 字符集 `[a-z0-9-]`、最长 27）。
  面板由地址决定存不存在，列表仍在原位 → 它是面板不是 dialog，未改挂 role。
  七轴空值显示"该记录无此字段"而不是 0；「用于本次制作」禁用并说明归属。
- **Minor（闸门无重叠断言）→ 已补，并且当场抓到真缺陷。** 新增
  `elementFromPoint` 命中测试后，第一次跑就报
  `#topNotice covered by button#capability-drawer-close`：抽屉压在顶栏右端两个按钮上。
  这条**不是**我先前那种看图误判——它有可复算的命中测试与栽桩复现
  （`qa-20261009d/geometry-assertions-falsification.log`：栽 8px → 红，栽 500px 宽 → 红，
  还原后字节一致且绿）。修法是把顶栏高度抽成 `--uif-topbar` 令牌并从它下方起算。
- 顺带的存量变化：字面 px 532→531（顶栏高度令牌化，少一处字面量），
  阴影声明 24→25 且新增那条读 `var(--shadow-soft)`；`DESIGN.md` §4 与
  `ui-layering.json`（`--layer-detail-panel:70`，name/purpose/note 齐全）同步。
- 至此 Major 3 关闭（tabs 仍属 §4 的另一条，见下），Minor 关闭。仍开着的：
  Major 2（schema 待裁决）、Major 4（草稿自动保存）、Major 5（制作记录与任务条）、
  Major 6（全局搜索三对象组）、Major 7（11 领域二级入口）、§4 的资产类型 tabs，
  以及键盘／减少动画／200% 的真人验收。

## 第五批追记（同日，R2 §7 制作记录与待继续）

新证据绑定 bundle `bb95a58b…`（328,929 字节），两主题各 21 路由、各 21 张实拍。

- **Major 5 → 已落地。** `#/records` 读既有 `GET /projects/{id}/tasks`：状态词原样出现
  （不翻译、不合并），取消的 `requested` 与宿主 `acknowledged` 分成两段事实，
  `TaskRecord` 没有的领域字段显示"无该字段"而不是按 `kind` 猜，
  "最近确认点"只在展开那一行时发一次 `…/tasks/{job}/events` 读回，
  底部任务条只数进行中与待人工核对的作业（三条种子里报 2 条，已回执的不计）。
- **一条方法结论**：实拍用的合成项目台账是空的，所以**行的渲染无法由截图证明**。
  这一屏改由 appshell ⑩ 用三条真实形状的 `TaskRecord` 驱动，并栽三种桩各红一次
  （任务条数成 3、领域按 kind 编造、取消两段并成一句），还原后绿且字节一致。
  教训与"未挂载的组件不算功能"同源：能渲染到屏幕上的才叫交付，
  渲染不到就用真实数据在 vm 里驱动并证明断言能红。
- 仍开着的：Major 2（schema 待裁决）、Major 4（草稿自动保存——已核实服务**没有**任何
  draft 路由，要先补后端再谈三态）、Major 6（全局搜索三对象组）、
  Major 7（11 领域二级入口——实测能力记录的 `domain` 是模型雷达 slug，与设计域只有一个
  字面巧合 `3d`，按它 join 会把"没有能力"说成 0 条）、§4 的资产类型 tabs
  （七轴在 60 条记录里全为空，tabs 必须能显示真实空态），以及键盘／减少动画／200% 的真人验收。

## 第六批追记（同日，R2 §9 全局搜索分组）

新证据绑定 bundle `e9b74265…`（333,652 字节），两主题各 22 个测量键、各 21 张实拍。

- **Major 6 → 已落地。** 命令面板按对象类型分四组读真实对象：能力资产（结果直接落到
  `#/capabilities/<id>`）、项目、设计领域（13 个真实域包）、设计系统，每条显示类型与去向，
  超过每组上限只画前若干条并明说还剩多少。三条边界写死：只查当前令牌已能读到的路由，
  服务没有对象级读权限模型所以**不声称"已按权限过滤"**；某组没答回来就说未读回，不显示 0 条；
  对象组首次打开才读并缓存。
- **浮层现在可测了。** 溢出/几何闸门新增 `global-search` 交互态：点 `#openPalette` → 等四组都
  给出可行动答案 → 量浮层几何 → Esc 关闭，避免打开的浮层污染后续路由。settle 谓词要求每组必须
  落在「有行 / 明确 0 个 / 明确未读回」三态之一，并栽桩证明它会红：让一组读回 0 且删掉空态文字
  → `OV_INTERACTION_UNMEASURED`，还原后绿且源码字节一致。
- 遮挡断言在模态浮层打开时按设计跳过，并在回执里写 `occludedSkipped: div.palette open`，
  而不是静默通过。
- **同一批里被实拍抓出来的真缺陷（blocker，已修）**：分组面板自己把尾巴裁掉了。首张
  `21-search-groups` 里只有『页面』一组 19 行，四组对象全在 `overflow:hidden` 之下不可达，
  而几何闸门照旧全绿——没有横向溢出，也没有元素被自身盒子裁断，纵向超出视口这件事它本来不建模。
  修法三件：面板定高 `max-height:78vh`、`#paletteItems` 变成滚动区、对象组排在页面组之前
  （§9 说的是搜对象，页面是兜底）；并给闸门加一条"滚到底后最后一行必须命中测试可达"的断言，
  栽桩（去掉滚动区）复现 `reached:false hit:null` → `OV_SPEC_BROKEN`，还原后绿且 CSS 字节一致
  （`qa-20261009f/palette-scroll-falsification.log`）。
- **回执绑定的一条改进**：几何回执的 `subject` 现在同时点名 bundle 与 stylesheet。CSS 是独立
  文件，改布局时 `main.js` 字节不变——只绑 bundle 的回执区分不出改过没改过，这一批就实测到了：
  重排面板后 bundle 从 `e9b74265` 变 `c3f16dc8`，而改 CSS 时它没变。
- 仍开着的：Major 2（schema 待裁决）、Major 4（草稿自动保存，需先补后端）、
  Major 7（11 领域二级入口）、§4 的资产类型 tabs、nav 内部排版断言，
  以及键盘／减少动画／200% 的真人验收。

## 需要 owner 裁定的清单（2026-10-09 汇总；界面不替这些决定猜）

每条都给了"不裁定时界面的当前行为"，这样等待不会变成停滞。

### A. R2 §2 二级导航的领域标签（4 处，算术见 `qa-20261009g/r2-domain-nav-mapping.log`）

§2 的 11 个中文名与读回的 12 个 slug 对不上：

1. **平面设计** → `graphic` 还是 `visual`？两个包都在，都通过校验。
   当前行为：两个各自成一条入口，用读回的 `displayName` 显示。
2. **UI 与交互** → `ui-ux` 还是 `product-ui`？同上。
   当前行为：两条入口并列。
3. **字体与出版** 没有任何域包声明它。
   当前行为：不出现这条入口（出现即等于凭空造一个域包）。
4. **游戏视觉** 唯一候选 `minigame-design` 声明 `workflow/domain-pack/v1`，
   `domain=null` 且被仓内校验器拒绝（11 条原因）。
   当前行为：它在列表与详情里如实显示为 `INVALID` + 未声明领域，不冒充可用领域。

反向也有一条：`ecommerce` 有包、无 §2 名字。当前行为：照常显示，不删。

### B. R2 §3 的三处令牌冲突（2026-10-11 按字节重量，原文是半成品）

原写法：h1 27/29px、侧栏 256/232/280px、内容边距 30/40 与 22/26。实测：

- **包值**（`docs/history/taskpacks/20261009-r2-inputs/ui-r2/specs/design_tokens.json`）：
  `typography.size_css_px.h1=27`、`layout.sidebar=256`、`compact_sidebar=216`、
  `desktop_gutter=30`、`compact_gutter=22`、`topbar=64`。
- **界面实际值**：导航轨 `168px`（`.app-nav`，fixed），内容让位 `192px`（`.dl-shell > main`），
  页头 `.page-head h2{32px}`、`.route-view h2{24px}`。
- **当时登记在 `--uif-*` 里的"包值"有三个根本不是包值**：h1 登记 29（包 27）、侧栏登记 232
  （包 256/216，且 232 在全仓与包里都搜不到）、沟槽登记 40/26（包 30/22）。
  而且 h1/h2/sidebar/两个沟槽**没有任何规则读取**——"登记"在界面上不可见。
- 唯一真正活在渲染里的冲突是顶栏：`--uif-topbar:78px` 被三条规则读取，包里是 64px。
  这一条仍然需要裁定，因为两边都要动已落地布局。
- 侧栏宽度已按 owner 的"新值做成可选主题"处理：默认配色保持 168/192 一字节不变，
  `data-palette="ui2026"` 在包自己的断点上取 256/30（≥1200）与 216/22（768–1199），
  <768 与默认一致（移动端 FROZEN_DEFERRED），由
  `design-lab/tests/test_workbench_theme_geometry_gate.py` 在真实浏览器里量 `getBoundingClientRect`
  与内容 `margin-left` 证明。**h1/h2 的尺度仍只登记不生效**：界面对应角色没有唯一答案
  （`.brand h1` 17px、`body > header h1` 26px、`.page-head h2` 32px、`.route-view h2` 24px），
  "包的 h1/h2 是界面上的哪一个"需要设计裁定，不裁定就继续只是登记。
当前行为：默认配色与既有尺度不变；可选主题按包值改轨宽与沟槽；顶栏与 h1/h2 映射待裁定。

### C. 26 处字面色值的 adjudication 字段

`design_debt_baseline.py` 明确 "an agent must not fill this field"。
当前行为：全部登记在案、逐处可查，不自动令牌化。

### D. 品牌主色 #316CFF 承载不下白色正文（对比度上限 4.45:1）

当前行为：按面解决（新增 `--border-strong`），品牌令牌本身不动。

### E. §6 草稿自动保存要不要服务端持久化

界面已有 localStorage 草稿（遗留简报面板），`#/intake` 的显式保存已写入本机服务。
自动保存若要跨重载/跨机器可靠，需要一条**可变草稿行**路由；
不能改写成简报修订（修订是不可变版本，逐键保存会灌爆版本链）。
当前行为：`#/intake` 只在用户点"保存为简报"时写一次；屏上说明这一点。

### F. U05 结构/文本节点的来源

`Plan.from_ocr` + `plan_to_rir` 已实现且 39 条本地测试通过，但没有生产调用方；
主机资格回放依赖 `.project-local/task-artifacts/ocr-qualification/` 的实测回执，
本机这些回执不存在，所以 `CONTROLLED_OCR_PASS` 在当前机器上不可复现（不是失败）。
当前行为：`#/plan` 只画底图一个节点（`inferred:false`），没有真实底图就不编排。

### G. 干净 clone 上无法复现的真值闸债（第十四、十五批实测，需要裁定）

CI run `38057782601` @ `aa3cb307` 的三个红里，两个不是缺陷而是同一个结构问题：
**受跟踪的判定去重算被 gitignore 掉的机器字节**。修掉契约漏项后再推一轮（run `38061750943`
@ `c46a4525`）剩下三条红**全部**落回这一个根因，实测读数见第十四批追记末段。

- `CURRENT_EXECUTION=FAIL [Errno 2] … /.project-local/task-artifacts/ui-first-20261009/u06/implementation.json`
  —— 账本 155 条证据里 **150 条**的 artifact 指向 `.project-local`（125 个不同路径），
  5 条指向受跟踪文档。投影在读时逐条重算 SHA，所以在 clone 上必然读不到。
- `VERIFY_PROJECTION_FRESHNESS=FAIL FRESHNESS-RECEIPT-DRIFT scripts/deepseek_content_audit.py --check
  exited 1: CONTENT_AUDIT=FAIL records=2 findings=2 notices=1` —— 在 `aa3cb307` 的干净 detached
  worktree 里复现：37 个 vendor 树在 clone 中不存在，判定词从
  `NO_FULL_THIRD_PARTY_SOURCE_TREES_TRACKED` 翻成 `REVIEW_ABSORBED_TREES_OUTSIDE_LOCK`，
  `full_copy_in_ignored_cache` 37→0、`missing_absorbed_tree` 0→37。

以下修法每一条都会动一个闸的判定词，我没有自行选（编号到 5，其中 1–3 是三种改法，4–5 是同一根因
另外两个实例的处置）：

1. 把回执字节搬进 Git。体量实测 `size-pack=242.71 MiB`；`origin/main` 可达 9430 个 blob 的
   **未压缩原始字节合计 = 360.1 MiB**——这是"全部 blob 求和"，既不是 pack 压缩量，也不是
   按路径归属的那条 minigame-runtime 182.19 MiB，别把三个数当一个用。
   这是先前明确避开的方向。
2. 给投影加一个与 `MISMATCH` 分开的具名状态（例如 `ARTIFACTS_ABSENT_IN_CLONE`），
   让"这台机器没有那份字节"不再读成"回执被改过"。
3. 把 content audit 的 presence 改成 SPILL-CENSUS 的形状：按版本化记录判定，
   实时普查只作为机器状态上报。
4. （2026-10-11 追加，同一个根因的第三个实例）`AUTHORITY_CHAIN` 也按字节摘要**活账本**
   `design-lab/config/task-ledger-r3.json`，所以任何一条新回执都会让 authority chain 作业红。
   本轮实测：链重生成并同批提交后 CI 从 13 条漂移项缩到 1 条，但那 1 条就是账本自己。
   现用的做法是"链排在账本定型之后、与账本同批提交"，可用但脆。要根治需要把活账本在链里
   标成 `mutable_state`（已有机制，用于 basis 是 requested 工作包的条目：摘要按生成时刻、
   **类别仍逐条比对**）——这是改权威记录的语义，需要 owner 裁定，我没有自行做。
5. （同一天，第四个实例，就在我要"顺手把链回执绑紧一点"时撞上的）**链记录本身不能被账本里的
   回执摘要**。我先写的链回执把 artifact 指向 `reports/current/DEEPSEEK-AUTHORITY-CHAIN.json`，
   而链按字节摘要活账本：重封回执→改账本→链漂移→重生成链→回执摘要又漂移，**没有不动点**。
   该回执的 artifact 已改绑本报告（判据文字一字未动，我的封存工具本来也拒绝改判据），
   `AUTHORITY_CHAIN=WRITTEN/PASS` 与 `AUTHORITY_GATES=PASS gates=7 failed=none` 靠重跑生成器复现。
   一般规则：**回执只能绑"被摘要的对象之外"的文档**；这条与第 1–4 项是同一个形状——
   受跟踪的记录去摘要会彼此改写的字节。

当前行为（2026-10-11 第十九批复测，本地）：`VERIFY_DESIGN_LAB=OK total=75 failed=0`——比上一行的
74 多出的那一个阶段是新登记的 `verify_selected_source_adaptation.py`（DL-FINAL-T07），不是判据变化；
`CURRENT_EXECUTION=PASS tasks=34 counts={'NOT_STARTED': 24, 'PARTIAL': 10}` 回执 172 条；
`AUTHORITY_CHAIN=WRITTEN entries=144` 后 `--check PASS`；`AUTHORITY_GATES=PASS gates=7 failed=none`。
CI 实测：@ `c46a4525` 三条聚合红全部来自这一条根因（读数见第十四批追记末段）；
@ `4453177c`（run 38071427909）失败作业从 2 个降到 **1 个**——authority chain 作业转绿
（链排在账本定型之后重生成并同批提交），剩下的就是 Python gate 里那 3 条聚合红。
不靠调低判据、摘掉闸或让 `--check` 读磁盘缓存来变绿。

### 本清单新增两项需要裁定的（第十九批，来自来源提炼，界面与闸都不替 owner 猜）

- **H：加权求和 vs「各维度独立、不许平均」。** `packages/capabilities/quality/jury/JURY_MODEL.md`
  与 13 个 DomainPack 的 `rubric.json` 用的是「各轴权重相加 + pass_threshold」。逐包实测：
  13 份 rubric 权重合计**全为 100**，轴数 5–7 不等（ecommerce/graphic 7 轴，minigame 5 轴，其余 6 轴），
  `scale` 全为 `0-100`，`pass_threshold` 为 82（minigame 80）；`JuryRecord.template.json` 的数值轴是
  5 个（antiSlop/layout/material/readability/commercial），JURY_MODEL 说的「六轴」把第 6 轴计为人审轴。
  而 `visual-quality__dataviz-critique` 的方法明文「Score each dimension independently — do not average
  them out… 不要因整体还行就统一给 7-8」，并给了 9-10/7-8/5-6/3-4/1-2 的**分档锚点**。两者不是同一件事：
  加权求和会把一轴的短板摊平，锚点制不会。改判据属 Quality Gate 语义变更，且会让既有评审读回的历史
  分数换含义，所以我只在 `packages/capabilities/selected-sources.json` 里把落点登记为
  `REGISTERED_ONLY` 并写明缺什么，没有自行给 rubric 加轴锚点。**要裁的是：是否改用分档锚点、
  是否取消加权求和（以及 13 份 rubric 的轴数不一致是否要统一）。**
- **I：12 套启发式框架与既有六轴的关系。** 同一来源（`ux-audit-skill`）一次引入 Nielsen 10、
  Shneiderman 8、Gerhardt-Powals、Bastien-Scapin、行为法则、Fogg、Cialdini、Gestalt、Norman、
  Tognazzini、WCAG 静态可检子集、内容启发式共 12 套，并要求每条发现按「框架#编号」引用。
  本项目六轴 + 人审门已经在评同一件事。并进来会有两套评分真相，不并进来则「引用具名启发式」这条
  取证纪律拿不到（它正是我要借的那条，已提炼但不落文档）。
  **要裁的是：把它当引用词汇表（不改六轴）还是当第二评分体系。**
- **J：`aside#drawer` 的触发器在桌面宽度上不可点（第二十批实测，原因未定位）。** 想把抽屉的
  开启几何做成常设断言时，Playwright 在 **1920 / 960 / 1440** 三个宽度都对 `#openDrawer` 报
  `element is not visible`（locator 已解析到 `<button id="openDrawer" class="ghost-btn">工作区</button>`
  本身，日志在 `.project-local/task-artifacts/ui-first-20261009/b20-20261011/drawer-trigger-probe-*.log`），
  而 `apps/workbench/style.css:1264` 在 `@media (max-width:840px)` 里显式写了 `.top-actions{display:none}`。
  也就是说：窄屏按规则隐藏，宽屏按渲染不可见，**我这个会话测过的每个宽度上都点不到它**，
  而 `wireB10Topbar()` 仍给它挂了 handler。未定位的是"宽屏为什么不可见"（我没找到隐藏它的规则，
  所以这条不是结论而是缺口）。**要裁的是：抽屉在桌面是否应当可达**——应当则补一个可达触发器并把
  断言做成常设闸；不应当则该组件与其 CSS 是移除候选，我不会自行删。
  本批因此**回退了那段断言**，而不是留一具永不通过的闸。

## 第七批追记（2026-10-09 深夜，Major 7：领域成为二级入口）

- **先量再做，量出来的结论改变了设计**：R2 §2 要 11 个领域成为二级导航。读回给的是
  13 个目录、12 个声明 slug（`minigame-design` 声明 v1 清单，`domain=null`，校验 INVALID）。
  §2 自己写了"不是永久硬编码的总共 11 类……生产读取现有领域配置和稳定 ID"，所以入口按读回生成，
  不写死 11。
- **领域→能力没有关联轴**：60 条能力的 `domains` 分类轴全为空；能力记录的 `domain` 字段装的是
  模型雷达 family（`video-generation`/`asr`/`3d`…），与包 slug 的唯一字面重合是字符串巧合。
  于是第七批把"按该领域筛选能力"做成禁用按钮 + 屏上写明原因。这里有一个容易被误读的点：
  §2 说"领域没有资产时显示空结果"，但**把"没有已接线关联"显示成"该领域 0 条资产"本身就是一种
  伪造**——0 条是一个判定，而服务没有给出任何可供判定的字段。真正的空结果资产面仍待做，
  且必须先第二次读回 `GET /api/capabilities` 并区分这两种措辞。
- **§2 的中文名与真实 slug 对不上（owner 裁决，已算术化）**：2 个名字无域包
  （字体与出版、游戏视觉），2 个名字各命中 2 个包（平面设计→graphic/visual，
  UI 与交互→ui-ux/product-ui），1 个包无人认领（ecommerce）。界面不替这四处猜。
  名字清单是从冻结规格逐字解析的，不是手抄；脚本在名字解析不出对应行时直接拒绝出数。
- **组件复用而非新样式**：详情面板复用既有 `.cap-drawer`，本批零新增 CSS，
  债务普查保持 26 色值／531 px／25 阴影不变。
- **顺带修掉的既有导航缺陷**：`#/projects/:id` 此前会让侧栏丢掉当前项高亮。三个参数化详情地址
  现在统一由 `DETAIL_NAV_OWNER` 认领父项，辅助技术读到的 `aria-current` 与真实位置一致。
- **一次把旧账挖出来的收获**：本批把 `test_contract_bindings` 加进静态电池，立刻红 24 条——
  根因是一条 `emitter` 行号指针 `capability_library.py:210`。HEAD 上那一行确实是
  `"schemaVersion": SCHEMA_VERSION,`，但本线程更早一批给该文件加了 ~47 行，指针就落到注释上了。
  该门此前"仍未注册"（见 `DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md`），所以没人在本地跑它。
  指针改指 247 行后 32 条全绿。这说明"行号型指针"是会被正常功能开发撞坏的，注册进电池才算有人守。
- **读渲染图找到的第二个缺陷：行内动作不成列。** 实拍里 13 行的"查看详情"落在好几列上。
  根因不是裁切也不是溢出——几何闸全绿——而是 `.list-item` 用 `justify-content:space-between`
  排三个子元素，中间那个的位置由两侧内容的宽度决定。第一次修只加了
  `.list-item:has(> button)>div:first-child{flex:1}`，栽桩后测得按钮仍差 14px：真正推着它的是
  **判定药丸自己的宽度**（VALIDATES 比 INVALID 宽）。所以修法是把药丸排到动作之前，让两列都
  右锚定；CSS 只多一条不含任何字面量的吸收规则，债务普查仍是 26／531／25。
- **这条断言本身被推翻过两次，两次都是先怀疑断言而不是放宽它**：
  1. 初版只比按钮的 left 边缘，于是 `display:none` 的按钮以 (0,0) 处 0×0 的矩形"完美对齐"——
     不可达被当成整齐。现在 DOM 里有、宽度为 0 直接判红。
  2. 药丸分支最初用 `.list-item > .tag`，把没有动作的行也扫进来，在**正确的**布局上报出
     656px 的假阳性。改成 `.list-item:has(> button) > .tag` 后才对上。
  四次种植各红在自己那条分支上（撑宽一个动作→23px；隐藏动作→13/13 零宽；去掉 flex→药丸 7px；
  给一个药丸加 margin→药丸 60px），还原后 style.css 字节一致（`9be8d6ea0a53`）。
  注意其中两次种植一开始是**种错的**：去掉 flex 只会让药丸散开（`space-between` 永远把最后
  一个子元素钉在右边缘），而给右锚定的药丸加 padding 根本不移动它的右边缘。改的是种植，
  不是阈值。
- 证据目录 `.project-local/task-artifacts/ui-first-20261009/qa-20261009g/`：两套配形的几何回执
  （23 条键，`1920:domain-detail` 抽屉实测 450px、clipped/stray/tiny/遮挡全 0）、AA 回执、
  两次栽桩日志（合同面 6 次、浏览器闸 4 次，均红在种下的原因上、还原后字节一致）、
  关联轴测量、命名算术、以及把每张 PNG 的 sha256 与 bundle/stylesheet 摘要钉在一起的
  `SHOTS.json`（上一批的实拍回执只绑了 manifest 自己，没有把像素和字节绑上）。


## 第八至十一批追记（2026-10-10 补写；本报告此前停在第七批，是三批的欠账）

补写而不是重写：第七批以上的判定不变，下面只记此后四批改了什么、量到了什么、以及本报告
自己该早点发现的问题。

- **第八批（R2 §4 资产类型 tabs）** 与 **第九批（U05 目标生成包编排面）** 的结论已落在
  `TASK-CARDS.md` 与账本里，此处不重复。要说的是两批各留下一个本报告没抓到的东西：
  tabs 的判据字段一开始选错（`kind` 而不是"资格"），靠"某张 tab 命中 100% 记录"这个
  不合理信号才发现；U05 的五个服务端拒绝一开始塌成一张「未受理」卡。两者都在第十批补了
  断言与种植。
- **第十批（`planRefusal` 五种拒绝）里有一个本报告应当当场拦下的缺陷，是我自己带进来的**：
  409 `NATIVE_PLAN_IDEMPOTENCY_CONFLICT` 用了 `kind: 'forbidden'`。屏上标题写"冲突"，
  状态类别却是"无权进行"，读者会被导向申请权限，而正确动作是**不要再复用同一个键**。
  `STATE_SPECS` 里本来就有 `conflict` 这一类，U05 的验收也点名 conflict。第十一批改为
  `conflict`，并加一条断言：两种 409 必须落在**不同**类别（忙可重试，幂等冲突不可），
  否则把两者并成一个词就会判红。`NATIVE_SUBMISSION_BUSY` 维持 `unknown`——那是服务
  什么都没决定，不是拒绝也不是许可。
  教训：字符串断言全绿并不能保护分类字段。标题对、类别错，是这一类缺陷的固定形状。
- **一条验收条款连续十批没有浏览器证据**：U05 与 U04 的验收都写"200%缩放"，而
  每批矩阵把 `OV_WIDTHS` 钉在 `1920`，闸自己的默认也是 `1440,1280,1920`——三个都不算窄口。
  1920 的 200% 是 960 CSS px，所以此前没有任何一份回执能替这条说话。第十一批两套主题都扫
  `1920,960,620`：69 条路由样本 clean、抽屉 450px、clipped/stray/tiny/遮挡全 0。
  判据也一并改严：新的 `zoom_passed` 除了要求 `1920:domain-detail` 干净，还要求三个宽度
  都出现过；只看一个固定键的判据永远注意不到扫描范围在缩小。
- **`navCue.hiddenPx` 在三个宽度上完全一样（759/749）不是探针坏了**：它是
  `scrollHeight − clientHeight`，而侧栏是固定 168px 的列，纵向溢出只随**高度**变化；
  闸在测这条时单独把高度设成 620。同理，同一宽度下两套主题相差 26px，所以
  `shell.ts` 的注释里不抄任何数字，只指向闸自己的记录。
- **「禁用」的理由必须指向被禁的那个效果。** `#/records` 的「继续该任务」以宿主副作用为由
  禁用，但跳到编排面没有宿主效果；`#/intake` 的「继续做目标生成包」引用的依赖已经在第九批
  落地，理由过期。第十一批各拆成两个控件：跳转可用（行为证明＝只改 hash 且发出 0 个请求），
  启动/取消仍禁用并说明为什么；导入行没有对应的目标包，就不给它入口，并把这个"为什么没有"
  写在屏上。
- **一处错误的负面断言在仓库里活了四批**：`plan_to_rir 在仓库里没有任何调用方` 出现在
  `shell.ts` 四处（其中两处是屏上文字）与生成器 `audit_ui_desktop_reconcile_20261009.py:86`，
  另有 `TASK-CARDS.md` 一处。而 `design-lab/tests/test_plan_to_rir.py` 有 8 处 import。
  正确说法是"没有**生产**调用方"。这属于同一类问题：负面断言没人证伪就当成事实复用，
  并且它会自己复制到界面文本和对账表里。
- **看渲染图抓到的第三个缺陷，是这一批自己带进去的**：`#/records` 的"这个入口现在能说什么、
  不能说什么"面板里，继续操作那一行还写着 **「未接线」**，而同一页已经画出了能点的接续按钮。
  页面自相矛盾，而几何闸、对比度闸、vm 断言全都没看见——因为它们各自看的是布局、颜色和字符串，
  没有把"面板的声明"和"面板所在页面上的控件"放在一起对。修法是拆成两行：
  接续到目标生成包「已接线」（并写明只跳转、不发请求、简报字段不会自动变成包结构）与
  启动 / 取消「未接线」（那才是本会话没有授权的真实宿主副作用）。⑮ 里加了对应断言，
  种植从八株加到十株。定位这两行时又踩了一次自己的坑：两条路由共用同一个 `route-view`
  元素，断言必须排在重渲染 `#/intake` 之前；而按"启动 / 取消"文字找 LI 会先命中作业行里
  那个同名禁用按钮，改成按该行独有的"本会话无该授权"定位。
- 证据目录 `.project-local/task-artifacts/ui-first-20261009/qa-20261009m/`（`qa-20261009l` 是
  加入这两条断言之前的同一批屏）：两套配形的三宽度几何回执、AA 回执、16 个块的 vm 日志
  （新增 ⑮）、十株种植日志（`falsify-continue`，全部红在种下的原因上，`shell.ts` 还原为
  `e87b2b17228f`、bundle `d5c7c1bf4b8b`）、以及 23×2 张把 PNG 摘要与 bundle/stylesheet
  绑在一起的 `SHOTS.json`。
- **实拍有一个说不出口的空白**：捕获用的项目 `制作记录（0）`——每个捕获/闸都自己起一份
  临时 state.db（`.project-local/task-runtime/tmp*/`），所以截图里永远没有原生作业行，
  新接的接续按钮在 46 张 PNG 里一张都没出现。它的证据目前只有 vm 的行为证明。
  要补像素，就得在那份一次性 state 里 POST 一个 native-plans（只排队、不起宿主、随临时目录
  丢弃），并在 `SUBJECT.json` 标成捕获脚手架。
  其中两次种植一开始是废的：这个文件是 CRLF，跨行锚点匹配不到（`count=0`）；另一株只改了
  被拼接字符串的前半句，被钉住的后半句还在，于是页面仍然诚实、判据仍然绿。改的是种植。
- 还有一处**判据自身的错，而且它被"修好"过一次又复发**：新记录器要的成句子写成
  `STATIC_BATTERY GREEN`，而电池一直写 `STATIC_BATTERY ALL_GREEN`（步骤 `EXIT=0`），
  于是一道通过的闸被记成 FAIL。第一次只改了账本里那一行，没改记录器里的错句子，
  所以同一批重测时它又红了，并且把共用这一步判据的另一条记录
  （`DL-UI-U05-stale-claims-corrected`）一起带成 FAIL。教训是：修一条被误判的记录时，
  必须同时修产生这个误判的规则，否则"修好"只是把那一行字改对。
  取证方式保持不变——`fix_static_record.py` / `fix_record_verdicts.py` 先重算回执与产物摘要，
  再只允许 `outcome`/`exit_code` 两个字段变动，并打印它依据的那一行——不是手改结论。
  现在 `currentExecution` 的 143 条证据里非 PASS 为 0。顺带修掉两个 `-r9-r9` 的双后缀记录 id；
  账本里另有 12 条历史 id 带 `-r7-r2` / `-r8-r2` 形态，属于可读出"哪一批 + 第几次重测"的
  旧命名，不改动历史。

## 第十三批追记（2026-10-10，U06 观察面 + 一次我自己造成的静默事故）

- **U06 缺的是读面，不是动作。** `native_tasks.py` 一直记着宿主占用、静默回执、对账与恢复
  协议，`http_service.py` 里却没有任何路由投影它们（实测 grep 零命中），所以界面能说出作业
  状态词，却说不出"Photoshop 现在被占着"。新增 `GET /api/projects/{id}/native-runtime`：
  只读、`mode=ro`、**绝不建表**——建表是 `native_tasks._connect` 的职责，读侧一旦建表，
  "这台服务从未跑过原生作业"就会变成"宿主空闲"，正是本仓库已犯过两次的错。
  `budget` 恒为 null 并带理由，不写 0；不造 IDLE/HEALTHY/READY 这类判定词。
- **接缝闸先把我拦下了一次**：新的 `apiOrEmpty` 读取必须有自己的 `shapeNotice`，
  报错原文是 "runtime read through apiOrEmpty but no shapeNotice call reports its missing
  fields"。按要求把 notice 移到读取点，接缝数 36→37，全部有主。
- **⑮/⑯ 的种植里有两株是我自己的断言无效**：一株的期望写成了产品文案而不是抛错原文；
  另一株在整个视图里 grep「未读回」，而作业行的 events 占位句本来就含这四个字——页面坏了
  它也不会红。后者改成把断言限定在面板内，并补一条反向检查（完整读回不得被当成未读回）。
- **一次静默事故 + 一次更糟的"修复"**：某个 scratch 用 `Path.write_text()` 重写受跟踪文件，
  在 Windows 上把 `shell.ts` 等 **9 个文件、23190 行**从 LF 转成 CRLF。`.gitattributes` 明明
  写着 `* text=auto eol=lf`，而 `core.autocrlf=true` 让 `git status` 一声不响——先暴露的居然是
  三株种植突然 `count=0`：**闸还在退出 0，却已经不守卫了**。我随后想用一条正则给所有 scratch
  脚本补 `newline='
'`，结果把 390 个文件里的 148 个改出语法错误（比原 bug 更糟），只能
  逐字节回退成"删掉我插入的那段字节"。最终交付的是门而不是笔记：
  `design-lab/tests/test_working_tree_line_endings.py` 最终形态是"被脚本按字符串锚点匹配的
  8 个文件必须是纯 LF"，并自带一株种植验证。前两版都被实测否掉：diff 版不可行
  （`core.autocrlf=true` 下纯换行改动产生的 patch 是 0 字节，git 根本看不见）；全仓字节比对
  版一上来就红 2,729 个历史 CRLF 文件（连 `.gitattributes` 自己在内），这种门下一个接手的人
  只会把它改成永真。第三版才既 satisfiable 又能命中本次事故。  行分割吃掉），比对工作树与属性，并按 63 条既有偏差的基线判定——**新增即红，已修却仍留在
  表里也红**（只能缩）。种植：把 README.md 改成 CRLF → 点名定罪，还原后字节一致。
  写这个门时自己也错了一次：只取 `parts[2]` 会把 `attr/text=auto eol=lf` 里的 `eol=lf` 丢掉，
  那样整道门会变成永真。
- **一个红步骤按瞬时中断处理，而不是放宽判据**：矩阵里浅色主题的溢出闸报
  `OV_SPEC_BROKEN 1920/960:domains showed 0 row action(s)`，但两份回执在该路由上字节一致，
  日志里有 `WinError 10053` 连接中止；空闲复跑 80.5s 通过，于是重新落这份回执并把它记在
  证据里，而不是把那条"必须看到行内动作"的判据调松。
- 证据目录 `.project-local/task-artifacts/ui-first-20261009/qa-20261009p/`：三宽度 × 23 路由
  = 69 个样本两套配色全清（含带新面板的 `#/records`）、AA 回执、17 块 vm 日志、五株运行时
  种植日志、13 项电池（含新增的门与 native-runtime 模块）、23×2 张与 bundle
  `6ff8532de49a` 绑定的 PNG。账本 153 条证据、非 PASS 0 条。
- **本轮以 owner 指令收尾**："完成当天跑的任务就停止任务"。因此提交并推送后停在
  `qoder/designlab-backup-consistency-20261007`，`main` 未合并（该分支领先 origin/main
  190 个提交），CI 结论、真实宿主 E3、真人评审 E4 与手机端仍为未做/未签。
  （第十四批追正：这个 190 是写句子时想出来的数，不是量出来的。`aa3cb307` 实测
  `git rev-list --count origin/main..aa3cb307` = **195**。）

## 第十四批追记（2026-10-10，把 CI 的三个红闸拆开：一个是我自己的契约漏项，两个是同一台机器的问题）

上一批我只在本地判定就结束了，这次把 CI 的真实读数拉回来逐条对照。run `38057782601` @
`aa3cb307`：`VERIFY_DESIGN_LAB=FAIL total=74 failed=3`，Python gate 的三条原文是

```
VERIFY_ROUTE_PAYLOAD_CONTRACTS=FAIL bindings=7 failures=121
CURRENT_EXECUTION=FAIL [Errno 2] No such file or directory:
  '/home/runner/work/DESIGN-LAB/DESIGN-LAB/.project-local/task-artifacts/ui-first-20261009/u06/implementation.json'
VERIFY_PROJECTION_FRESHNESS=FAIL FRESHNESS-RECEIPT-DRIFT scripts/deepseek_content_audit.py --check
  exited 1: CONTENT_AUDIT=FAIL records=2 findings=2 notices=1
```

- **第一个红是我的漏项，不是环境差异。**`capability-library.schema.json` 关闭了
  `additionalProperties`，而 `GET /api/capabilities` 从 DL-FINAL-T06 起每条记录多带 `axes` 和
  `qualificationReason`。CI 的 121 = 60 条 `SCHEMA_VIOLATION` + 60 条 `UNDECLARED_BY_SCHEMA`
  + 1 条 evidence-projection 拒答。控制种植（`.project-local/tmp/falsify_schema_fix_batch14.py`）
  把 schema 换回 HEAD 字节后在本地复现 `failures=120`，错误行与 CI 逐字一致；还原后按 digest
  断言字节一致（`3190c87bfa89`，9460 B）。修复面：capability 记录声明并必填这 2 个键
  （`required` 24→26），新增 `$defs.axisValues`（7 个轴，值可以是 null / 字符串数组 / 对象），
  `qualified` 从 `const null` 放开为 `boolean|null`，`qualificationEvidence` 放开为
  `null|array`。
- **放开 `const null` 之前先确认它没有打开伪造通道。**`capability_library.py:70` 的
  `UNQUALIFIED = None`，`_qualification()` 只有在记录自带 `qualification.qualified` 是 bool 时
  才写 true/false，否则写 null + 原因；`design-lab/readiness/model-radar.json` 里
  `"qualification"` 出现 **0** 次，所以今天 60 条全是 null + reason。契约放开的是"以后允许读回
  一个真实判定"，不是"界面可以把它当成成功"。
- **第二和第三个红是同一件事的两面：受跟踪的判定去重算被 gitignore 掉的机器字节。**我在
  `aa3cb307` 的干净 detached worktree（`.project-local/worktrees/ci-repro`，工作树 0 行改动）里
  复现了 content audit：`CONTENT_AUDIT=FAIL records=2 findings=2 notices=1`，37 个 vendor 树在
  clone 里不存在，判定词从 `NO_FULL_THIRD_PARTY_SOURCE_TREES_TRACKED` 翻成
  `REVIEW_ABSORBED_TREES_OUTSIDE_LOCK`，NOTICE 里 `full_copy_in_ignored_cache` 从 37 变 0、
  `missing_absorbed_tree` 从 0 变 37。同一个 worktree 逻辑就解释了上面那条 `[Errno 2]`。
- 数字摆在这里：账本证据里 **150 条的 artifact 指向 gitignored `.project-local`**（125 个不同路径）。
  追加本批两条回执前的普查是 153 条 / 3 条受跟踪（本报告 1 + 对账表 2），追加后是
  **155 条 / 5 条受跟踪**（本报告 3 + 对账表 2）——两个数都是量出来的，差别就是本批新写的两条
  改 seal 受跟踪文档。
- **这两条我没有自行修**，因为三种可能修法都要动真值闸的判定词：把回执字节搬进 Git（本仓库
  实测 `git count-objects -v -H` 的 `size-pack` = **242.71 MiB**，而 `origin/main` 可达的
  9430 个 blob 的**未压缩原始字节合计** = **360.1 MiB**（全部 blob 求和，既不是 pack 压缩量，
  也不是按路径归属的 minigame-runtime 182.19 MiB）；把 125 个 gitignored 回执路径搬进 Git 是往这个方向加，
  这是先前明确要避开的）；给投影加一个与 MISMATCH 分开的具名状态（例如
  `ARTIFACTS_ABSENT_IN_CLONE`）；或把 content audit 的 presence 从"重算磁盘"改成 SPILL-CENSUS
  那种"按版本化记录判定、实时普查只作为机器状态上报"。
  这属于 owner 裁定，不属于收尾轮里顺手放宽。
- 修复后、推送前的本地实测：`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=7 failures=0`，
  `CURRENT_EXECUTION=PASS tasks=34 counts={'NOT_STARTED': 25, 'PARTIAL': 9}`，
  `VERIFY_DESIGN_LAB=OK total=74 failed=0`。

## 第十五批追记（2026-10-11，把 owner 清单逐条按字节重量，结果修掉两个真缺陷）

owner 说"修复发现的问题"。先把 A–F 每一条重新量了一遍（脚本
`.project-local/tmp/remeasure_owner_list_20261011.py`，只读），量出来的东西有一半确实是裁定，
**但有一条是我的缺陷**：

- **A 项按实测确认仍缺数据**，不是代码缺失：`build()` 出 60 条能力记录，七个轴
  **全部 0/60 非空**，每条 `unclassifiedAxes` 长度都是 7，`qualified` 全是 `None`
  （`.project-local/tmp/measure_axis_population_20261010.py`）。13 个域包目录、12 个声明 slug、
  `minigame-design` 的 manifest 里没有 `domain` 键。所以那 4 条命名仍是裁定。
- **C/D/E/F 量下来与原写法一致**：`DESIGN_DEBT_BASELINE=PASS`、字面色值 26 处；
  `#316CFF` 压 `#FFFFFF` 按 WCAG 相对亮度算就是 **4.45**；`/api/…` 路由里 `draft_routes=[]`
  （可变草稿面确实不存在）；`design-lab/tests/test_plan_to_rir.py` 退出 0，
  而 `.project-local/task-artifacts/ocr-qualification/` **不存在**（`is_dir()=False`），
  所以 F 的"当前机器不可复现"是事实而不是失败。
- **B 项是缺陷**，已按上面的 B 段重写。三处登记值不是包值（h1 29、侧栏 232、沟槽 40/26），
  而 232/29 在全仓与包里都搜不到——写它的人（我）把记住的数当成了包值；同时侧栏与两个沟槽
  没有任何规则读取，"登记"等于没做。

**修的部分**：

1. `--uif-font-h1` 改回 27，布局行改回 256/216/30/22（新增 `--uif-sidebar-compact`），
   注释写明逐字段来源，并把 78 vs 64 顶栏明确标成"活冲突，属裁定"而不是登记错误。
2. 可选主题真的读这些值：`@media (min-width:1200px)` 取轨 256 + 沟槽 30，
   `@media (min-width:768px) and (max-width:1199px)` 取轨 216 + 沟槽 22，两条规则都只在
   `:root[data-palette="ui2026"]` 下生效；导航轨是 fixed，所以内容列的 `margin-left` 同步改，
   否则内容会钻到轨下面。默认配色一字节不变。
3. 新门 `design-lab/tests/test_workbench_theme_tokens.py`（8 项）：登记的令牌必须被读或在
   "只许缩"的登记表里有理由；声称包出处的值必须等于包；被记成偏差的必须仍是偏差。
   它当场抓到我自己两处写错：我把六个 `--uif-font-*` 都说成未读，实际 body/small/h3/micro
   在被 UI-first 面读取；以及"未读"集合应是 8 个而不是我记忆的 11 个（改动后）。
   种植四株都有罪：值改回 232/40 → 按名点罪；新增无主令牌 → 点罪；把已接线的令牌留在登记表 →
   点罪；把 78 悄悄对齐成 64 → 点罪。
4. 新浏览器闸 `design-lab/tests/test_workbench_theme_geometry_gate.py` +
   `e2e/audit_workbench_theme_geometry.mjs`：真实 Chromium 里逐宽度量 `.app-nav` 的
   `getBoundingClientRect().width`、内容列 `margin-left`/`padding-right`，三套主题
   （design-lab/dark、ui2026/dark、ui2026/light）× 五个宽度（1920/1200/960/768/700）。
   实测：默认恒为 168/192/0；ui2026 在 1920 与 1200 为 256/286/30，在 960 与 768 为 216/238/22；
   700 时两套主题读数相同（轨吃满 700、让位 16），证明 min-width 没有漏进移动端。
   回执把量到的 `style.css`/`build/main.js` 摘要写进 JSON，findings 也写进 JSON——
   第一版只在 stdout 里报，wrapper 截了尾部 3000 字，把 @1920 的定罪行截掉了，
   于是种植"看起来"只在 @1200 有罪：**读数不在产物里，等于没测到**。
5. 种植定罪复现：删掉 1200 那条主题规则 → 闸退出 1，findings 覆盖 @1920 与 @1200 两个宽度、
   三个罪名（`THEME_RAIL_NOT_APPLIED` / `CONTENT_OFFSET_MISMATCH` / `GUTTER_NOT_APPLIED`）；
   还原后字节一致（`f5410c1ad591`，101,028 B），再跑为绿。

**回归面**：溢出闸按两套配色各重跑 1920/960/620（69 样本/套），`Ran 1 test OK` 各 84s/83s，
clipped/stray/tiny 均为 0；appshell vm 合同面退出 0（①–⑯ 全过）；
`test_workbench_css_single_definition` 17 项 OK；`design_debt_baseline --check` 由红转 PASS——
+3 是媒体查询断点（CSS 不支持 `var()`），已按规则的措辞把 DESIGN.md §4 的数字改成 534 并写明原因。
**界面文案没动**：`#/components` 把这一轴描述成"配色与明暗"，现在它还会改轨宽与沟槽，
那句话不完整了；但改文案会换 bundle 字节，把与 `6ff8532de49a` 绑定的整套截图作废，
所以这条记成有理由的后续，等下一次界面批次一起做。
- **推送后 CI 的真实读数**（`gh run view 38061750943 --log-failed` @ `c46a4525`）：
  `VERIFY_DESIGN_LAB=FAIL total=74 failed=3`，但组成变了——
  `VERIFY_ROUTE_PAYLOAD_CONTRACTS=FAIL bindings=7 failures=1`（121→**1**，剩下那条是
  evidence-projection 在 clone 上拒答），`CURRENT_EXECUTION=FAIL [Errno 2] …u06/implementation.json`
  仍红，`VERIFY_PROJECTION_FRESHNESS=FAIL … deepseek_content_audit.py --check` 仍红。
  于是**三个红现在是同一个根因**：受跟踪的判定去重算 gitignored 机器字节（上面 G 项）。
  契约漏项已在 runner 上确认修掉，不是只在我机器上绿。

## 第十六批追记（2026-10-11，补界面文案 + 试图补上接续入口的像素证据）

- **做成的一半**：`#/components` 原本把这条轴描述成"配色与明暗"，而第十五批之后它还会改导航轨宽与
  内容沟槽，那句话不完整了。屏上现在写明：≥1200 轨 256/槽 30、768–1199 轨 216/槽 22、窄于此沿用
  既有折叠（手机端 FROZEN_DEFERRED）、默认主题仍是轨 168/让位 192；并写明包里的排印尺度只有
  body/small/h3/micro 已接到界面，h1/h2 等角色裁定。bundle 重建为 `12647eb8ec78`（354,258 B），
  `shell.ts` = `5716e15eee79`。
- **新 bundle 上的回归**：appshell 17 块全过；shape-notice 37 接缝全有主；
  css-single-definition + contract-bindings + theme-tokens 共 57 项 OK；
  两套配色各 69 样本的溢出闸两次都是 `Ran 1 test OK`；theme-geometry + contrast 4 项 OK（139s）。
- **没做成的一半，原因量到了**：接续入口的像素证据。我给 `capture_workbench_screenshots.py`
  加了 `--seed-native-plan`（在一次性临时态里提交一个从未运行的 native plan，
  `task_kind=photoshop-native` / `attempt_state=PENDING`，并写 `capture-scaffold.json` 明标脚手架）。
  实拍回来仍是空态，读图确认：页面上是"未选择项目"。原因是**捕获驱动自己会新建并选中一个
  `Closeout <stamp>` 项目**（`capture_workbench_screenshots.mjs:178-189`），我先种的那个成了第二个；
  而 records 只在"恰好一个项目"时自动选中（`shell.ts` 的 `sole` 分支）。
  再把驱动改成"给了 `CAP_SEED_PROJECT` 就复用不新建"，bootstrap 直接 `CAP_BOOTSTRAP_FAILED`——
  第一屏没有可选项，选不中。**于是这两处工具改动退回 HEAD**：留一个红着的捕获工具比少一组截图更糟。
  下一步明确：让驱动在**它自己建的项目**上种 native plan（顺序反过来），重拍后读图确认按钮真在画面里。
- 账本没被这条未完成的改动污染：本轮没有写任何"截图里能看到接续入口"的回执，因为图里没有。

## 第十七批追记（2026-10-11，接续入口的像素证据拿到了）

- 按上一批量到的原因改顺序：种计划这一步搬进**驱动内部**，在它自己建好并选中
  `Closeout <stamp>` 项目之后再做；Python 侧那份"先建一个项目"的辅助函数**删除**而不是留着——
  它会静默产出两个项目、然后拍到一张只有选择器的图。
- 驱动里的三道硬检查：服务必须回 202；投影出来的 `kind` 必须以 `-native` 结尾；
  页面真正读的 `GET /api/projects/{id}/tasks` 必须列出这一行。任何一条不满足就 `CAP_FAIL`，
  不会留下一张什么都证明不了的截图。`capture-scaffold.json` 与 PNG 同目录，写明这是
  一个 `layers: []`、从未运行、无宿主副作用的合成脚手架。
- 实拍（绑 `2b59765d`，两套配色各 46 张，1920/960）后**读图确认**：
  `21-records@1920.png` 与 `21-records@1920@ui2026-light.png` 上都有
  `native-job-…` 行的「接续：打开目标生成包」可用按钮 + 旁边仍禁用的「启动 / 取消」，
  素材导入行按理由不给入口，下方声明面板三项（状态词 来自服务 / 领域标签 无该字段 /
  接续到目标生成包 已接线）与画面控件一致。浅色那组同时看得第十五批的轨宽（1920 下 256）。
- 产物目录：`.project-local/task-artifacts/ui-first-20261009/qa-20261011e/screens/{design-lab-dark,ui2026-light}/`
  （gitignored 证据根，随 `screenshot-manifest.json` 与 `capture-scaffold.json` 一起留档）。
- 这一件结掉的是"界面控件有没有被渲染出来"，不是"宿主接续能用"：按钮只做地址跳转，
  真实运行/取消仍未授权，`native cancel` 也仍没有 ack 事件。

## 第十八批追记（2026-10-11，R2 §2 领域↔能力关联面：四种"空"被分开说）

- 领域详情地址现在做**第二次读回** `GET /api/capabilities`，把"这个领域有几个能力"换成
  这次读回量出来的关联状态；列表页仍然只读一次（vm 里钉着，第二次读泄漏到列表就是红）。
- 屏上区分五种说法，各说各的：**未读回**（seam 得替它补那个集合，此时一个数都不报）、
  **无关联键**（该域包没声明领域，minigame-design 就是这种）、**还没有分类**
  （0 条命中且 60/60 都把 `domains` 列在自己的未分类轴里）、**目录为空**（读回 0 条）、
  **无已接线关联**（已分类的里面没有一条声明本领域）。只有最后一种是真的"暂无关联"，
  而任何一种都不许写成"该领域没有能力"。
- **写这套断言时我自己错了一次，而且是两次**：先 vm 里用 `includes('该领域没有能力')` 一刀切，
  结果产品因为要否定引用这句话而被判红；改成"提及数 vs 否定式提及数"之后，我在溢出闸里
  又写了另一种错形式（`[^不]` 负向断言——引号不是"不"）。两处现在同一形状，
  并且这条教训单独进了记忆。
- **vm 合同面抓到产品里一个真缺陷**：新按钮我只写了启用/禁用与 title，**没写 onclick**——
  一个"已接线"却点了没反应的控件。现在它跳 `#/capabilities`，块里同时证明点击不发出任何请求。
- 溢出闸的 R2 §2 规格随之升级：从"必须永远禁用 + 出现未接线字样"改成
  "禁用状态必须与面板声称的状态一致"（有 `已接线 N 条` 才可点；否则必须禁用），
  并要求至少出现一个状态词。两套配色 × 1920/960/620 重跑：各 69 样本，
  clipped/stray/tiny 0，spec 0 条。
- 三株种植各自由自己的罪名定罪（肯定式断言、第二次读回被删、禁用规则被翻），
  还原后 `shell.ts` 字节一致（`875d61cf475b`）。
- 实拍（绑 `8fc04680`，两套配色各 46 张，1920/960）后读图确认：
  `15-domain-detail@1920.png` 上 Brand Design 面板的「能力关联」行是
  `还没有分类 · 能力目录 60 条读回里，声明该领域的有 0 条；而 60/60 条的 domains 轴都在服务自己的未分类轴清单里`，
  动作禁用，来源行写明数字出自第二次读回；同一屏的 MINIGAME 行如实显示 `领域 未声明`。
  证据目录 `.project-local/task-artifacts/ui-first-20261009/qa-20261011g/screens/`。

## 第十九批追记（2026-10-11，DL-FINAL-T07 来源提炼：闸能判的三件事，和它量出的两处真偏差）

- **本批不动任何界面字节**，所以没有新实拍可看，这一点用摘要证明而不是用话说：
  `apps/workbench/build/main.js` 仍是 `255e992ac03b3c06…`（358,028 B）、`style.css`
  `f5410c1ad591a080…`（101,028 B）、`shell.ts` `875d61cf475bb730…`（428,853 B），
  与第十八批被审阅的那套截图所绑的字节同一三枚摘要；改的是
  `packages/capabilities/`（新增 1 个数据记录 + 2 份标准文档各 1 条）、`design-lab/scripts`、
  `design-lab/tests`。上一批的桌面实拍对本批仍然是可审阅面，不需要为凑数重拍一遍。
- **做了什么**：从 980 条候选里 owner 已记为 CONDITIONAL_POC 的 37 条中选 6 条真读，
  逐条写用途/来源版本/许可/方法与反例/落点/执行资格/撤回+恢复，落在
  `packages/capabilities/selected-sources.json`（38 KB，由一次性采集脚本按引用生成：
  `pinnedCommitSHA`、`rights.license`、`removalPath`、adoption 数字全部从
  `CANDIDATE-TAXONOMY.json` 复制，13 条方法引文按行号从本地 vendored blob 读出，没有一处手写）。
- **闸把三条验收线变成可判定的**（`design-lab/scripts/verify_selected_source_adaptation.py`，
  已接进 canonical 聚合，`total=74 → 75` 是阶段数增加，不是判据变化）：
  1. 热度只作筛选：star/fork 只能待在 `adoptionFilter(usedFor=FILTER_ONLY, qualitySignal=false)`，
     `selectionBasis` 里把热度当理由即红；明确否述热度的句子不判红（提及数 vs 否定式提及数分别计——
     这条纪律来自本会话前两次子串禁令误判正确文案的教训）。
  2. 登记不算接入：`REGISTERED_ONLY` 8 条（必须写"还缺什么"）/ `MAPPED` 2 条（只有当目标文件里
     真的写着该 ruleId 才成立：`MOTION_ACCESSIBILITY.md`、`DESIGN_TOKEN_INTEROP.md`）/
     `CONSUMED` 0 条（还额外要 E2 以上 + 真驱动它的测试）。翻转任一档都会判红。
  3. 执行资格只能用 `capability-status.json` 公布的词表，且不得越过 `promotionLevel` 的上限；
     高于 `declared-only` 的每条 evidenceRef 都要通过**账本读取根策略同一个谓词**
     （复用 `src/design_lab/governance/reporting._safe`，不再抄一份根清单）。
- **量出来的两处真偏差（不是判据问题，是我借来的规则打到自己产品）**：
  由动效方法提炼的确定性检查对 `apps/workbench/style.css` 实测 **2 处动画 `right`**
  （1061、1065 行：`transition: right .28s cubic-bezier(.2,0,0,1),visibility 0s linear …`），
  与 `visual-quality__taste-skill` L522「Animate ONLY transform and opacity. Never animate
  top/left/width/height」和 LottieFiles 清单「No layout-triggering properties animated」直接冲突。
  我没有静默放宽规则，也没在本批顺手改 CSS：改法（`right:-256px` → `transform:translateX(-100%)`）
  会动到溢出闸测的 rail 几何与两套配色实拍，必须整批重测，故登记为**有界偏差**并留下一批。
  闸是双向的：多出第 3 处判红，旧偏差已修却未删条目同样判红（`knownDeviations` 与实测逐条比对）。
- **负面样本特意留着**：`tool-control` 的 `pinnedCommitSHA` 为空，被强制 `quarantined`
  （`capabilityState=missing`，唯一一档），落点只是既有 COM 模块且全部 `REGISTERED_ONLY`。
  它同时暴露两处来源侧事实：其 `README.md` 首行宣称"来源与许可逐项核实"，同文第 20 行却把
  photoshop-automator 标为"未核实/仅参考不吸收"；其运行时路径写在 `.hermes/task-runtime/…`，
  而本项目的运行/证据根是 `.project-local`。许可门与撤回门因此不是空转——没有这一条，
  "许可未核实只能参考"的规则永远不会被真实数据触发。
- **我自己的初稿错了两处，都在闸的第一次运行里被撞出来**（不是产品缺陷，是我的判定式缺陷）：
  (1) 我按 `designQuality is None` 判"未测量"，而分类表里该字段实际是**空对象 `{}`**——
  真值反了会导致没评过分的行为"已测量"，且"声称测量需人审引用"那条规则永不触发；
  现改为 `unmeasured()` 统一覆盖 `null/{}/[]/""`，两个方向各有种植。
  (2) 我在 packages/ 下新增一个数据文件，使 `inert_contract_survey` 的 `productFiles` 由 208 变 209，
  该闸按自身规则把整条聚合判红（`VERIFY_PROJECTION_FRESHNESS=FAIL … 改了代码没重跑就是红的`）。
  按其文档化路径重跑生成器后 `--check` 复绿，**INERT 状态分布一字未变**
  （`NO_STATE_COUNTERPART=17 TABLE_WRITES_THIS_ACTIVITY=8 ADJACENT_TABLE_WRITTEN=2 TABLE_EXISTS_UNWRITTEN=3`），
  即没有第二条 INERT 合同因此被我新文件"命名"。
- **第三方 SKILL.md 一律按惰性素材读，没有执行**（AGENTS.md 的 inert source blobs 规定）。
  要一份"执行级"的供应链判定，本机已装 `research-copilot:skill-criticagent` 是现成路径，
  但它会真实拉起被审对象，属宿主副作用，留给 owner 点名后再做，我不自行开这扇门。
- 回执 3 条入 `currentExecution`（implementation 1 / unit 2，全部 exit 0，
  绑 `head=835fa880`）：闸输出、38 项任务测试、动效偏差实测 JSON。
  `DL-FINAL-T07` 由 `NOT_STARTED` 迁 `PARTIAL`：其余 4 条 `REGISTERED_ONLY` 升 `MAPPED`
  属质量/标准文档语义变更（见新增裁定项 H、I），真实宿主 E3 与真人 E4 一项未做，不代签。
- 复测读数：`VERIFY_DESIGN_LAB=OK total=75 failed=0`、
  `python -m unittest design-lab.tests.test_selected_source_adaptation` → `Ran 38 tests OK`、
  `CURRENT_EXECUTION=PASS tasks=34 counts={'NOT_STARTED': 24, 'PARTIAL': 10}` 回执 172、
  `AUTHORITY_CHAIN=WRITTEN entries=144` 后 `--check PASS`、`AUTHORITY_GATES=PASS gates=7 failed=none`、
  `CANDIDATE_TAXONOMY=OK entries=980 domain_packs=13 errors=0`、`CAPABILITY_EVIDENCE_V4=PASS records=8`。
- **CI 实读（@ `2d9ab95a`，run 38129189122，逐作业照抄）**：
  `MiniGame node gate`、`DeepSeek authority gate chain`、`Top-level Authority consistency gate`、
  `License & secret hygiene gate`、`Open Design host adapter gate`、`Workbench strict-TS product gate`、
  `Clean wheel install + Workbench launch gate`、`Workbench browser E2E (no-skip)`、
  `Generated-artifact clean-tree gate` **全部 success**；
  仅 `Python gate (V3 verifiers + unit tests)` failure，失败步骤是 `DESIGN-LAB unified verify`，
  `VERIFY_DESIGN_LAB=FAIL total=75 failed=3`，三条红分别是
  `verify_route_payload_contracts.py`（bindings=7 failures=1）、
  `scripts/verify_current_execution.py`（`[Errno 2] …/.project-local/task-artifacts/ui-first-20261009/u06/implementation.json`）、
  `verify_projection_freshness.py`（`FRESHNESS-RECEIPT-DRIFT scripts/deepseek_content_audit.py`）。
  **与本批无关、与第十八批同集合**：三条都是 owner 裁定项 G 的同一根因（受跟踪记录去重算 Git 忽略字节）。
  新登记的 `verify_selected_source_adaptation.py` 在 CI 里 `PASS`——vendored blob 不在场时它按
  `SKIPPED` 语义如实报告而不是判红，这正是设计意图（本地 `VERIFIED(13)`，CI `SKIPPED(13)`）。
- **一条必须说清的覆盖事实（不是本批造成的，但本批让它可见）**：该作业的
  `Python unit tests` 步骤排在 `DESIGN-LAB unified verify` **之后**，聚合链一红就 `skipped`。
  实测同样读数 @ `835fa880`（run 38126320592）也是 `failure` + `skipped`。所以
  在 G 未裁之前，**CI 从不执行那 578 个 unittest 模块，本批的 38 项任务测试只是本地证据**，
  不能写成"CI 已通过"。`run_python_tests.py` 用 `discover(design-lab/tests, test_*.py)`，
  本地一跑就全收；要在 CI 里拿到测试结论，需要 owner 允许把该步骤改成
  `if: always()` 或把聚合链拆开——那是动 CI 拓扑，我不自行做。

## 第二十批追记（2026-10-11，把第十九批量出的两处布局动画改掉，并且真的去数像素）

- 补一条更完整的 CI 读数（@ `c8139060`，run 38129638692，逐作业照抄）：与 `2d9ab95a` 同形——
  9 个作业 success，只有 `Python gate` failure，三条红仍是
  `verify_route_payload_contracts.py` / `scripts/verify_current_execution.py` /
  `verify_projection_freshness.py`，`VERIFY_DESIGN_LAB=FAIL total=75 failed=3`，
  `Python unit tests` 步骤继续 `skipped`。
- **改了什么**：`apps/workbench/style.css` 的抽屉从 `right:-540px` ↔ `right:0` 改成
  `right:0` + `transform:translateX(540px)` ↔ `transform:none`，transition 列表里 `right` → `transform`；
  `visibility` 的"关闭延迟 .28s / 打开立即"机制一字未动（那是 Tab 可达性的修复，不能被顺手改掉）。
  等值性是可算的：同一个 540px、同一个 `width:min(520px,95vw)`，所以闭屏矩形
  `left = innerWidth - width + 540` 与改前完全一致。`style.css` 新字节 `295676ceb2a7…`
  （101,549 B，原 101,028 B，多出来的是注释）。
- **闸先证明自己会红**：改完后 `verify_selected_source_adaptation.py` 立刻报两条
  `recorded deviation … no longer exists`（`knownDeviations` 里还留着已修掉的条目），
  重采集生成后才 `motion_deviations=0`。判定范围同时从 1 个文件扩到 **7 个前端字节面**
  （样式表、已提交构建产物 `build/main.js`、`shell/workbench/design/contracts/main` 五个 TS 源），
  实测总偏差 0；空清单里写了 `deviationLedgerNote` 说明它不是"从未测过"，并由测试钉住
  （`test_composited_motion_counts_the_real_stylesheet` 要求 scope 含 `build/main.js`，
  且注释里必须留 1061/1065/translateX(540px) 三个记号）。
- **浏览器侧复跑**：`E2E_REQUIRED=1 python design-lab/scripts/verify_browser_e2e_ran.py` →
  `BROWSER_E2E ran=7 skipped=0 failed=0`（四份套件全跑，无跳过）；
  `workbench-overflow-gate.json` 与 `workbench-theme-geometry-gate.json` 两份报告都把
  `style.css 295676ceb2a7` 写进自己的字节（`styleSha256`），所以它们测的就是改后的树。
- **两套配色 × 1920/960 各 46 张重拍**
  （`.project-local/task-artifacts/ui-first-20261009/b20-20261011/`）。逐张 sha256 与 owner 已审的
  `qa-20261011g` 集合对比：`design-lab/dark` **29/46** 摘要变了，`ui2026/light` **27/46** 变了。
  **这个计数本身不能当"像素变了"的证据**——采集每次都新建自己的项目（清单里 `project.name`
  带毫秒时间戳），落地页内容本来就随运行变。于是改成逐点像素差：`15-domain-detail@1920` 差
  **0 像素**（`getbbox()` 为 null，逐像素等同，它也在未变的那 17 张里）；`00-workbench@1920` 差
  **14.149%**，差异框 `x174..1461 / y222..1080`——导航栏（x<174）与右边缘（抽屉所在侧）分毫未动；
  浅色同形 **13.771%**。结论按证据写：改动没有触及任何被审阅的版面几何；摘要计数变动是运行期
  内容使然。两份读数在回执 `pixel-digest-comparison.json` 里并存，不用其中一份掩盖另一份。
- **一次失败尝试换回一条真缺口（见 owner 清单 J）**：我原打算把"抽屉开启后的几何 +
  computed transitionProperty"做成常设断言（因为路由扫描看不见离屏差异）。它在
  1920/960/1440 都点不到 `#openDrawer`（Playwright：`element is not visible`，locator 已解析到按钮），
  而 ≤840 是规则里显式隐藏的。我没有留一具永不通过的闸，也没有把断言改成 JS 直调来"过"，
  而是回退断言、把三份探针日志与三份宽度读数存档，并把"桌面是否应当可达"作为 J 交给 owner。
- 本批不动 bundle（`build/main.js` 仍是 `255e992ac03b…`）、不动配色、不碰手机端。
  回执 7 条：browser 2 / visual_review 3 / implementation 1 / unit 1，全部 exit 0，账本共 179 条；
  `DL-FINAL-T07` 与 `DL-UI-U02` 仍 PARTIAL，不自行升档。

## 第二十一批追记（2026-10-11，云端审计 D13 落地：主题按钮第一次真的改绘制）

- **审计的观测点是 `835fa880`，不是今天的 HEAD**。我用 `git diff 835fa880..HEAD` 逐文件核对：
  `apps/workbench/shell.ts`、`src/design_lab/http_service.py`、`native_submissions.py`、
  `adobe_lowering.py`、`pyproject.toml` 在今天两批里**一字未动**，所以它报的 D01-D09/D11-D13
  不能当作"已被今天修掉"，只有 D10 的"packs0 被误读成没有域包"那一半在 `835fa880` 内已被 U03 修好。
- **D13 的两处根因，各自独立**：
  ① 前端 `themeControlNodes()` 的两个 `onclick` 都是"先 `writeUrlParam`，再
  `applyTheme(readThemeChoice())`"。而 `readThemeChoice()` 按它自己 6098-6100 行的注释**故意**
  优先读已应用的 `<html>` 属性（对比度闸就是直接设属性的），于是它读回还没写进去的旧值，
  再把这个旧值应用一遍——两个按钮在真实浏览器里都是空转。改成"先应用意图值，再写 URL"。
  ② 服务端 `dispatch` 用 `self.path` 与路由表比较，而 `BaseHTTPRequestHandler` 给的
  `self.path` **含 query**，所以 `/workbench?palette=ui2026` 不是已知页面，落到需要鉴权的分支，
  浏览器导航没有 token → 401。现在页面路由按 `urlsplit(self.path).path` 匹配。
- **为什么今天所有绿聚合都没抓到它**：新增第五份浏览器闸
  `design-lab/tests/test_workbench_theme_affordance_gate.py`（已登记进
  `verify_browser_e2e_ran.TEST_MODULES`——不登记就永远 skip，这正是缺陷躲过去的方式）。
  它点当前 bundle 里的真控件，读数：`data-palette design-lab → ui2026`、
  `--surface #0D1221 → #101a26`、`body rgb(6,10,20) → rgb(8,14,22)`、
  `location.search "" → "?palette=ui2026"`、`statuses ["200 (no query)","200 ?palette=ui2026&scheme=light"]`，
  `findings=0`。第十八批我加"领域关联"按钮时是 vm 合同面抓到缺 onclick；这次 vm 面**根本没有**
  主题断言（`grep theme apps/workbench/tests/appshell.mjs` 为空），所以属性级合同也无从证伪——
  只有"点了之后绘制变没变"这一种断言能守它。
- **第一版探针超时，原因也是要断言的东西**：屏上同时存在两套 `.theme-toggle`（遗留视图那套不可见），
  Playwright 默认点了隐藏的那条。现在断言"每个动作恰好一条可见"，出现隐藏孪生即罪名。
- **真值测试的改动如实交代**：`test_service_http.py` 原本把 `/workbench?file=AGENTS.md` 断言成
  **404**——那正是缺陷的指纹（带 query 的页面路径不被认成页面）。安全属性换成可证的正面断言：
  页面 200、字节与 `/workbench` **完全相同**、且不含 `# AGENTS.md`；两条 traversal 路径
  （`/workbench/../../AGENTS.md`、`/workbench/main.ts`）仍必须 404。没有放松任何一项。
  `Ran 29 tests OK`。
- **实拍**：本批重建了 bundle（`255e992ac03b…` → `5829f52a4fa7…`，358,130 B），所以第二十批那
  92 张已绑旧 bundle 的实拍对当前字节作废；两套配色 × 1920/960 各 46 张按新 bundle 重拍
  （`b21-20261011/`，deviation 照旧记：从工作树拍摄，tracked 的 exact-commit 守卫未动）。
  另有一张**从点击路径本身**产生的 `clicked-design-lab-to-ui2026@1440.png`，我读过图：左下角控件
  文字变成"UI-20261009 基线"并多出"深色"，与 `--surface` 变色一致；同一屏显示
  "请先在工作台连接本机设计服务，再读回此视图。"的空态，所以它证明的是**主题接线**，
  不证明能力目录读回，两者不混用。
- 探针自身缺陷也记一条：`--primary` 在 `documentElement` 上读回空串（该令牌定义在 `.dl-shell`
  作用域），所以闸不以 `primaryVar` 单独判色变，用 `--surface` + `body background` 两条。
- 复跑读数：`tsc --noEmit` 0；`vite build` 0 且**重构建字节与提交字节相同**
  （`dirty_after_rebuild=0`，这条是我自己第一次跑 recorder 时把 cwd 与相对脚本路径配错、
  写出一条假 FAIL 回执之后重做的——撤账本、修调用、重封，不把工具缺陷留在账上）；
  node `unit/appshell/shape-notice-coverage` 三组 0；`E2E_REQUIRED=1` 五份浏览器套件
  `ran=8 skipped=0 failed=0`（读数取自日志里的 `E2E_EXIT`，不读 wrapper 状态）。
- 审计其余条目本批**未动**，按依赖排到下一批：D02（默认 Illustrator 计划 `locked=true` →
  `adobe_lowering.py:118` 拒绝 → 400，默认关键路径不能排队）→ D01/D03（重试现生成新
  `idempotency_key`，而界面写着"同键安全"）→ D09（wheel 未随包两份 schema →
  research/rights 500；旁边 `runtime/state_resources.py` 已有正确的包资源机制）→
  D04/D05/D06/D07/D08（其中 D08 的"跳转不带领域条件"是我第十八批引入的）→
  D11/D12 仍属 owner 裁定项 G。AAOS 与 WORK 的条目不计入本项目待办。
- 回执 8 条：browser 2 / visual_review 3 / unit 2 / implementation 1，全部 exit 0，账本 187 条。
  `DL-UI-U02` 与 `DL-FINAL-T08` 仍 PARTIAL；真实宿主 E3、真人 E4 未做，手机端 FROZEN_DEFERRED。

## 第二十二批追记（2026-10-12，D02 / D01+D03 / D04 / D09+D10：四处"界面承诺 ≠ 代码行为"）

本批把第二十一批排队的四个可逆工程项做掉。四条都是同一形状的缺陷：**页面对用户说了它做不到的事**，
而每一处修法都只动**调用方**，不动合同。

### D02：Illustrator 的默认目标包从来排不进队

- 三段链条逐段量过：`composeTargetPlan` 写 `locked: host === 'illustrator'` →
  `adobe_lowering.lower()` 要求 `not n['locked']`（"explicit fallback required"）→
  `http_service` 把它折成 400 INVALID_REQUEST。Photoshop 能过**只是因为 UI 恰好发了 `false`**，
  不是因为两条路径都对。
- 修法：`locked: false`，两侧宿主一致。**没有**放宽 lowering 合同——新路由测试里显式提交一个
  `locked: true` 的层，仍然必须是 400，这条拒绝本身被钉住了（审计判据"不放宽 lowering 合同"
  如果只靠注释，就等于没有）。
- 跨层读数（真 CLI 进程 + loopback，不是 mock）：两条宿主各 202、`job_id` 合 `native-job-[0-9a-f]{64}`、
  attempt `PENDING`、随后 `GET /api/projects/{id}/tasks` 能读回同一个 job、**相同 body 的第二次 POST
  返回完全相同的响应**（幂等重放，不是第二个 job）。

### D01 / D03：幂等键每次点击现生成，于是"同键安全"是假的

- 服务端按 `sha256(project_id:host:key)`（native_submissions）与 `sha256(project_id:key)`
  （image_assets）认身份；页面在两处按点击调 `uuid()`。丢响应后重试 = 第二个 job / 第二份素材，
  而界面写着"直接重试同内容是安全的（同键）"和"失败项未写入服务端"。
- 修法：键**绑内容**。计划用 `sha256(项目 ‖ 宿主 ‖ 编排结果 ‖ 文字样式)`，导入用文件字节自身的
  `sha256`，都是 64 位十六进制，正好落在服务端的 `[A-Za-z0-9_-]{1,64}` 内。同一意图 → 同一键 →
  同一个记录；内容变了 → 新键 → 新记录。
- **文案也一起改**。"失败项未写入服务端"从来不是客户端能证明的（丢的是*响应*，写入照样发生）；
  客户端能承诺的只有键。现在写的是"失败项按失败记，同一文件重试不会变成第二份素材"。
  这不是把缺陷说得好听一点，是把断言换成它真正成立的那一条。
- vm 合同面实测：`contentKey` 同输入同输出、换宿主即换键、形状恒为 64 hex。

### D04：202 把任务嵌在 `task` 里，页面读的是顶层字段

- `TaskQueries.get` 返回 `{'task': {...}}`，`shell.ts` 读 `data.task_id ?? data.job_id`，
  于是**每一次被受理的提交**都显示"未给出任务号"。同一屏另一处读 `asset.version_no`，
  而 `/assets` 的载荷里根本没有这个字段（旁边 4611 行已有守卫，这一处没有）→ 渲染出 `vundefined`。
- 修法：`readPlanReceipt()` 一处构造回执行，版本行回退到 `version_id`。合同面断言
  `readPlanReceipt({task:{job_id,state}})` 读出嵌套值，`readPlanReceipt({})` 与 `(null)` 退回"未给出任务号"，
  **没有**把缺失当成成功。

### D09 / D10：装态的 PROJECT_ROOT 指向 `Lib/`

- `runtime/paths.py:17` 的 `PROJECT_ROOT = parents[3]`：源码树里是 checkout，装进 wheel 后是
  `<venv>/Lib`。于是 `research_store` / `rights_ledger` 读裸路径 → 装版 GET 500；域包投影报
  `rootState MISSING`。三者说的其实都是同一句"这些字节不在这里"，不是"答案为否"。
- 修法：**复用旁边已经正确的机制**（`state_resources.state_schema` 的 packaged-first），抽成
  `repo_resource()`；`pyproject` force-include 补上两份 schema、`domain-packs/` 与
  `design-lab/scripts/verify_domain_pack_v2.py`（投影复用仓库自己的 checker，少了它每包都会变
  NOT_CHECKED，"VALIDATES 就等于 CI 也会接受"这个保证就没了）。
- `domain_packs.py` 里用的是**绝对导入**：`design_lab` 是 namespace package，`..` 相对导入在这里
  会抛 "attempted relative import beyond top-level package"——第一次就踩到了。
- `test_workbench_served_bundle.py` 原来 `@skipIf(INSTALLED_MODE)`。那是唯一能抓住"site-packages
  里躺着一份旧 bundle"的断言，而它恰好在缺陷**第一次被发现的地方**不测量。现在按模式决定
  应该服务**哪一份**已声明的 bundle，而不是决定要不要测。

### 本批的读数与两处不粉饰的地方

- `tsc --noEmit` 0；`vite build` 0；浏览器五件套 `ran=8 skipped=0 failed=0`（取自日志里的 `E2E_EXIT`）；
  单元 127 项绿，唯一一条 ERROR 是 `test_native_submissions` 自己的 sys.path（`import test_native_plan`），
  与本批无关。
- 聚合闸 85 项里 `verify_reconstruction_pipeline` 与 `verify_reconstruction_bundle` 红。**与本批改动无关**，
  并且我在 HEAD 对照复跑过：同一形状的失败在未改动的 HEAD 上同样出现（`failures=1, errors=57`）。
  两条都是**环境**问题，不是判据问题：一个是 Windows 权限语义下 `RollbackBlockedError` 不触发，
  另一个是本机 sandbox 的 safe-delete 批量确认守卫在 `shutil.rmtree` 上拦截（截图里能看到
  `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=50 threshold=50`）。**没有**为了让聚合变绿去动判据。
- 回执 7 条：browser 1 / visual_review 2 / unit 3 / implementation 1，账本 187 → 194。
  另外**重封**了两条 `DL-UI-U02-theme-affordance-*-r21`：本批浏览器电池把那个文件按新 bundle
  重测了一遍（findings 仍为 0），所以只有实测的 `artifact_sha256` 移动，闸名与主张一字未改，
  并且在 `command` 里写明为什么动。
- 实拍：bundle 从 `5829f52a4fa7…` 变成 `91235532ca42…`（359,816 B），第二十一批那 92 张对当前字节作废；
  两套配色 × 1920/960 各 46 张重拍（`b22-20261012/`，deviation 照旧记在工作树，tracked 的
  exact-commit 守卫未动）。我读过 `19-plan@1920.png`：目标生成包屏正常渲染，选中态与"排队这份目标
  生成包"都在；它证明的是**屏还在**，不是队列链路——队列链路由上面的路由测试证明，两者不混用。
- 仍未做：真实宿主 E3（需 owner 明确授权）、真人 E4、merge 到 main、release、手机端（FROZEN_DEFERRED）。
  D05/D06/D07/D08（前端发现性与过滤，D08 是我第十八批引入的）按依赖排到下一批；
  owner 清单 A–J 一条未动，本批没有替任何一条猜答案。

### CI 抓到的两处（本地全绿之后）

推送后读 `17d3139f` 的 CI，两个作业红，**两处都是我自己引入的**，而且本地复跑抓不到：

1. **`Workbench strict-TS product gate`** —— `node tests/appshell.mjs`：
   `NATIVE_PLAN_IDEMPOTENCY_CONFLICT: 一次点击应恰好一个请求，实得 0 个`。
   根因在**测试脚手架**，不在产品代码：vm context 里有 `crypto.randomUUID`（给旧的 `uuid()` 用），
   但没有 `crypto.subtle` 和 `TextEncoder`。本批把幂等键改成内容摘要之后，每次提交都在 fetch **之前**
   抛 `crypto.subtle is not a function`——而"fetch 之前抛出"在断言里读起来就是"没有发出请求"，
   于是**五个拒绝分支被跳过而不是被测**。补上真实的 SHA-256 与 `TextEncoder` 后 `APPSHELL_EXIT=0`。
   这条要记住：**同一批里"闸全绿"和"覆盖被静默跳过"可以同时成立**，本地跑同一套 node 用例也不会发现。
2. **`Python gate` → `DESIGN-LAB unified verify`** —— `VERIFY_CONTRACT_BINDINGS=FAIL`，
   三条 `EMITTER_POINTER_NOT_THE_VERSION`：rights / research / domain-packs 的绑定按**行号**指向
   "写出该版本的那一行"，而我加的注释把 `CONTRACT_VERSION` / `CONTRACT_ID` / `SCHEMA_VERSION`
   的行号整体推下去了。改的是 `design-lab/config/contract-bindings.json` 里的**指针**，
   不是删注释、也不是改闸的判据。

CI 同期报的另外三条（`verify_route_payload_contracts`、`verify_current_execution`、
`verify_projection_freshness`）在**本地全 PASS**——它们绑的证据在 `.project-local/` 里，
干净 clone 上没有这些字节，属交接提示词里点名的 G（干净 clone 无法复现的真值闸债）。
`VERIFY_DESIGN_LAB=FAIL total=75 failed=2`，剩下的两条（`verify_reconstruction_pipeline`、
`verify_reconstruction_bundle`）是本机环境问题，已在 HEAD 对照复跑确认同形，不是本批回归。

### `90124f7f` 的 CI 实读（逐作业）

| 作业 | 结论 |
|---|---|
| Workbench strict-TS product gate | **success**（本批两处修复之一生效） |
| Workbench browser E2E（exact-SHA, no-skip） | **success** |
| Clean wheel install + Workbench launch gate | **success**（D09/D10 的装态读数） |
| DeepSeek authority gate chain | success |
| Top-level Authority consistency gate | success |
| Generated-artifact clean-tree gate | success |
| License & secret hygiene gate | success |
| MiniGame node gate | success |
| Open Design host adapter gate | success（无 Open Design 面变化，正常跳过内部步骤） |
| CI artifact proof (H001) | skipped（main-run 上传读回，本分支不适用） |
| Python gate (V3 verifiers + unit tests) | **failure** |

Python 闸的失败面回到**本批开始前的那三条**（`4e5ef345` 的读数逐字相同）：
`VERIFY_ROUTE_PAYLOAD_CONTRACTS=FAIL bindings=7 failures=1`、
`CURRENT_EXECUTION=FAIL [Errno 2] … u06/implementation.json`、
`VERIFY_PROJECTION_FRESHNESS=FAIL records=14 … findings=1`（内含 `CONTENT_AUDIT=FAIL records=2 findings=2`）。
`VERIFY_DESIGN_LAB=FAIL total=75 failed=3`——**本批新增的那条（contract_bindings）已消失**，
剩下三条全部指向 `.project-local/` 里干净 clone 不存在的字节，也就是 owner 清单里的 G。
处置仍属 owner：搬字节进 Git、加具名状态、改 presence 形状，或把活账本标 `mutable_state`；
**禁止**用调低判据、摘闸、或让 `--check` 读磁盘缓存来换绿。

## 第二十三批追记（2026-10-12，owner 裁定项 G 落地：把证据字节搬进 Git）

**先纠正一个流传的错误数字。** 本清单第 G 条写的是"搬 242.71 MiB 字节进 Git"。
实测：那 194 条回执里 175 条绑定 `.project-local`，它们**只引用 1.13 MiB / 175 个小文件**
（JSON 清单、闸日志、一张 115 KiB 的 PNG，最大单个 115.2 KiB）；`.project-local` 整体 5.2 GB，
其中绝大部分不被任何闸引用。242.71 MiB 是当时整个归档目录的体量，**不是闸真正需要的那部分**。
这个差别决定了 A 方案是可行的，所以必须先量再让owner 选。

### owner 选择：A（把字节搬进 Git），而不是 B/C/D

- 175 个文件复制到受跟踪根 `design-lab/evidence/current-execution/`，**保持原 `.project-local` 相对形状**
  （`design-lab/evidence/current-execution/task-artifacts/...`），便于逐条对照来源。
- 194 条回执的 `artifact_path` 全部改指受跟踪副本；`artifact_sha256` **一个都没动**，
  因为复制是逐字节的（脚本对每个副本重算哈希，不符即报错中止）。`command` 追加了迁移说明，
  原命令与原结论保留。
- `.gitignore` 补了 `!design-lab/evidence/**/*.log`。全局 `*.log` 规则对游离运行输出是对的，
  它只是没考虑"会被回执逐次重算哈希的证据"这种文件。

### 途中撞上的真实规则冲突（没有绕过，如实记）

搬完字节后 `verify_projection_freshness` 反而红了：
`SUPPLY_CHAIN=DRIFT ... fresh_failures=['G040_generated_artifacts']`。
`scripts/verify_supply_chain.py` 的 `generated_artifact_audit` 把任何受跟踪的 `.log`
判为生成物（`GENERATED_MARKERS = ('.pyc', '.pyo', '.log', '.tmp', '.bak')`）——
**而A 方案恰恰要求跟踪 82 个 `.log`**。两条规则直接对撞。

处置（这是执行 A 的必要后果，不是一次独立的判据松动）：
- `verify_supply_chain.py` 增加 `TRACKED_EVIDENCE_ROOT` 豁免，**且只豁免该根下的 `.log`**。
- **第一版写宽了**：我最初写成"evidence 根下所有 marker 全豁免"，自己的探针立刻抓到
  `design-lab/evidence/a/x.pyc` 返回 `ok=True`——`.pyc` 根本不该被豁免。已收窄。
- 收窄后的边界由 6 条探针钉住，全部符合预期：
  `evidence/x.log →豁免`、`scratch/x.log →仍红`、`evidence/x.pyc →仍红`、
  `evidence/__pycache__/x.py →仍红`、`evidence/x.tmp →仍红`、`dist/x.log →仍红`。
  豁免宽到能盖住整个 marker 元组，就是"挂着名字的判据降级"，所以这条边界必须有反例。

### G 落地后的闸读数

原本在干净 clone 上必然失败的三条，现在本地全绿：
`CURRENT_EXECUTION=PASS tasks=34`、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=7 failures=0`、
`VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=19 receipts=5 findings=0`、
`VERIFY_SUPPLY_CHAIN=PASS (verdict, failure list and every check agree)`。

**仍然未做**：真实宿主 E3、真人 E4、release；owner 清单 A–F、H–J 未动；
移动端 FROZEN_DEFERRED。`rescue/designlab-personal-audit-dirty-20261007` 经比对**保留**——
它独有 4 个 HEAD 完全没有的文件（个人产品审计报告、UI 实施报告 A 版、两个 personal_workbench E2 测试），
不是可删的旧快照。

## 第二十四批追记（2026-10-13，D05 / D06 / D07 / D08：前端发现性与过滤）

第二十一、二十二批排到本批的四项。四条同样是"界面承诺 ≠ 代码行为"，四处修法都只动**调用方**，
不动服务端合同；`GET /api/capabilities`、`/api/domains`、`/api/design-systems` 的响应形状一字未改。

### D05：搜索里有两处字段名从来没有对过

- 调色板的"设计系统"组读 `d.systems`，而该路由答的是 `{design_systems: […]}`
  （`design_layer.py`，也就是 `DesignSystemListResponse` 自己声明的那个名字）。没有任何响应携带过
  `systems`，所以**一次成功的读回被画成"这一组当前读回 0 个对象"**——一个言之凿凿的零，盖住了真正返回的对象。
  同一行还把版本读成 `version_no`，而合同里是字符串 `version`，于是版本号从不出现。
- 修法：把四组的投影移出浏览器专用作用域，导出 `searchGroupRows(path, data)`，四个键各自钉在自己的路由上
  （`capabilities` / `projects` / `packs` / `design_systems`）。这既是修 bug，也是让字段名**从此可测**：
  这段代码此前只在真实 DOM 里存在，所以没有任何测试能看见它。

### D06：失败的读回既不可重试，也不被单独呈现

- `objectsLoaded = true` 写在**任何 await 之前**，且整段没有 try/catch。一次抛错的读取于是有三个后果：
  半张面板留在屏上；面板被钉死在"已加载"，重开也不再试；而读不到的组与"读到 0 个"长得一模一样。
- 修法：状态从布尔量改成 `'idle' | 'loading' | 'done'`。只有**全部**组给出终态才算 `done`；任一组抛错就退回
  `idle`（下一次打开面板会重试它），并在该组位置渲染 `读取失败：…`＋「重试这一组」，绝不把失败写进缓存。
  已读回的组在重试时跳过，不重复请求。

### D07：`qualified` 是三值判定，`!== null` 把"已判不合格"算成了"可调用"

- 服务端发 `true` / `false` / `null`（未判定）。`qualified !== null` 于是把服务端**明确判为不可调用**的记录
  和被判定可调用的记录并排放进"可调用能力"这一类——而这一类存在的唯一目的就是回答"我能调什么"。
- 修法：`qualified === true`。`false`（已判不合格）与 `null`（未判定）都不进这一类，两者也不互相冒充。
  测试用**三类取值同时在场的读回**把两个谓词分开——只有 `true/false/null` 同时出现，`!== null` 与 `=== true`
  才会给出不同的数字。
- 三个产物 tab 共用一个谓词这件事**没有**顺手改掉：那条轴上没有任何取值，把它们拆开就得先替它发明一套词表，
  而这一段原本就写着"不替它猜词表"。改为在注释与屏上文案里写明"三类的谓词是同一个，所以三个数字必然相等；
  这不是三种各自的读数"。

### D08：跳转不带领域条件，而 tooltip 说它按声明领域过滤

- 领域详情抽屉的「按该领域查看能力」把地址写成固定的 `#/capabilities`，而同一按钮的 tooltip 写着
  "能力目录侧按声明领域过滤"。读者因此落到**未过滤**的能力库上，且屏上没有任何东西说明他问的是哪个领域。
- 条件**走 hash**（`#/capabilities?domain=<slug>`），不走 `location.search`：本文件里每一次跳转都是
  `window.location.hash = …`，而只有这个赋值会触发路由；把条件放进 search 会改地址却不重画视图。
  路由表按 `hashPath()` 匹配，所以**条件改的是视图显示什么，从不改它是哪个视图**——按原始 hash 精确匹配会让
  带条件的地址落到遗留工作台页上，也就是条件悄悄弄丢了载它的那条路由。
- 能力目录侧把它当一等条件：条件条上一枚可单独移除的 chip、把命中数与"自己记着 domains 轴未分类"的条数
  **分开报**（"被过滤掉"与"没人分类过"是两个答案），过滤本身跑在**整组读回**上、用 `axes.domains`
  ——也就是记录自己声明的那个轴，而不是拿 `capability.domain` 与 pack slug 的字符串巧合当关系。
- 「清除检索条件」**不动**领域条件（R2 §4 末段：那个按钮只清检索）；移除条件只由 chip 的 × 做，它把地址收回
  `#/capabilities`。

### 顺带修掉的一处"桩的属性冒充 DOM 的属性"

挂载守卫此前问一个**临时创建的元素**有没有 `querySelector`，而那是 vm 桩的属性，不是文档的属性。
本批为了让调色板的投影可测而给桩的元素补了一个选择器方法，**这个守卫当场翻转**，整层 B10 外壳开始往一个
连 `navigator` 都没有的桩里挂载。守卫已改为问 `document`——两个环境下的语义一字未变（真实浏览上下文有
`document.querySelector`，桩没有），但从此只有一处可看。

### 本批读数

- `tsc --noEmit` 0；`vite build` 0，bundle `main.js` 重建字节与提交字节相同。
- 三份 node 套件全过，本批新增 3 条断言：⑰（四组投影按各自路由的合同字段取行）、⑱（`qualified === true`，
  三类取值同时在场的读回）、⑲（条件随跳转进地址、带条件地址仍解析成能力目录、条件上屏且分开报命中与未分类、
  「清除检索条件」不清领域、chip 的 × 才收回条件）。
- 本机聚合闸 `VERIFY_DESIGN_LAB=FAIL total=75 failed=2`——两条仍是既有的沙箱 safe-delete 守卫
  （`verify_reconstruction_pipeline` / `verify_reconstruction_bundle`），在未改动的 HEAD 上同形，不是本批引入。
- **未做**：真实宿主 E3、真人 E4、release、手机端（FROZEN_DEFERRED）；owner 清单 A–F、H–J 一条未动，
  本批没有替任何一条猜答案。
- **一处诚实的覆盖边界**：调色板只在真实 DOM 里挂载（那是 `mountB10Overlays` 的文档级守卫决定的），
  所以 D06 的**失败态与重试**没有 vm 断言——它靠的是一次读取抛错后的行为，而桩里没有调色板。
  本批没有为它造一个假的绿：D06 修了什么写在上面的代码注释里，可测的是 D05 的字段名与 D07/D08 的行为。
