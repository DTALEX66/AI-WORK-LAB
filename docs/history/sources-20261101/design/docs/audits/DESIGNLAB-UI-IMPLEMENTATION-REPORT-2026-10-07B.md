# DESIGN-LAB UI 实施收敛报告 B

**日期** 2026-10-07 · **Authority** `DL-AUTHORITY-2026-09-18-R2`
**基线** `main = 72d6ae4b`（#259 并入后）· 本报告随 `#260` 落地
**接手** CODEX 分支 `qoder/designlab-picker-autoselect-20261007` 的未提交移动端改动
**与 CODEX 报告的关系** 取代 `DESIGNLAB-UI-IMPLEMENTATION-REPORT-2026-10-07.md` 中"远端状态 UNKNOWN"
与"Chromium 不可用"两节——那两条是它的 sandbox 限制，不是仓库事实；本文给出实测值。

## 一、桌面端 UI 现在能做什么（有证据）

| 能力 | 证据 | 等级 |
|---|---|---|
| 13 个面在 1280/1920/2560 全部渲染，无溢出/无对比度违规 | `AUDIT_SCOPES 39 violations=0 ok=True` | E2 |
| 真实设计链：建项目→导入参考→建 Brief→建方向→选定→绑定设计系统→改 Brief→改已选方向→重建绑定读回→**重开页面后仍读回** | `browser-e2e-summary.json`：12 场景 `result=PASS`，`consoleErrors=0` | E2 |
| 每面首屏截图 + 机读清单（headings/KPIs/unread 计数随图存档） | `CAP_DONE shots=39`，manifest 绑定 commit | E1–E2 |
| 移动端链（appshell 布局） | 同一 E2E 的 `mobile-appshell-layout` 场景 | E2 |

E2 的限定：`subjectSha` 本地记为 `"local"`，CI 上才绑 exact SHA；本地这份证据不绑 SHA，引用时须说明。

## 二、本轮真实改掉的东西

| 缺陷 | 为什么之前的门看不见 | 落点 |
|---|---|---|
| 侧栏身份块在 4 条长页路由掉出折叠线 | 拉伸网格项不是溢出，是比屏高 | #258 |
| 台账只有 1 项目时三个 picker 面是死路 | 空态环"可滚动即合法" | #258 + 新审计项 |
| `.kpi-grid` 固定 4 列，3 计数器留 ~240px 空洞 | 空洞不是违规 | #258 |
| 共享输入零行仍标"服务端环境读回" | 空列表与读到空同形 | #258 |
| 未开放页 1 卡 / 宿主 2 卡塞三栏 | 同上 | #258 |
| 移动端滚动提示会随菜单滚走 | 类/aria 检查两种写法都绿 | #259（CODEX 提出，实测后改 sticky） |
| 宿主网格无据绿标"已登记"，同页却写 UNKNOWN | 颜色语义不在任何门的断言里 | #260 |
| `交付包（0）` 的 `0 === 0` 空真值通过 | 计数看着合法 | #260 |
| 200 响应缺集合 → 整页 TypeError 失败（⑤） | 崩溃点离原因几层远，消息只剩 TypeError | #261 |

配套守卫：`picker-dead-end`（先证伪：旧 bundle 3 违规）、`test_workbench_sidebar_pinning.py`
（4 处变异致死）。

## 三、明确未完成

1. **⑤ 响应形状异常**：崩溃面已在 seam 归一化修掉（#261）——200 响应缺列表/缺映射不再在
   后续字段访问处抛错、不再让顶层 catch 把整页变成"视图读回失败"。
   **范围限制**：归一化覆盖全部 21 个 `apiOrEmpty` 站点的崩溃面，但
   "未读回：响应缺少 …"这条**文字只接到 项目 与 仪表盘 两面**；其余面不再崩，
   但仍会把"缺字段"显示成"空集合"。铺 notice 是同一模式的机械活，本轮未做完。
   第一版（抛错式守卫）已回滚：它比 appshell 的部分 mock 更严，见 §五。
2. **Rights / Preflight 阻断案例、Handoff 可重开**：界面存在、我已逐屏读过，
   但**没有浏览器链覆盖**（E2E 的 12 场景不含它们）。
3. **首屏仍是第二套壳**（D-6 未决）：legacy 导航 + "本机已连接" vs B10 侧栏 +
   "本地单用户 / 无身份路由 · 未读回"。本轮只补了它的移动端 affordance，没有替 owner 统一。
4. **移动端已无 CI 覆盖**：证据口径按指令收到 ≥1024，代码保留。恢复用 env，已实测。

## 四、需要 owner 才能推进的（不是我的进度问题）

- 真实宿主 E3（Illustrator / Photoshop 保存 + 重开局部编辑）：需明确授权拉起宿主窗口。
- Human Jury E4、release E5、发布：需真人 / 决定。
- D-1 Inter、D-3 规格矛盾、品牌蓝 `#316CFF`、中英标题政策、首页坏消息权重、
  INSPECTOR 空环、D-6 壳统一。

## 五、回滚范围

本轮全部改动集中在 `apps/workbench/{shell.ts,style.css,build/main.js}`、
三道门的宽度默认值、`design-lab/tests/` 两个测试文件、以及 `docs/audits/` 三份记录；
无依赖变更、无 lockfile 变更、无数据库或外部副作用。逐 commit 可 revert。

## 六、并入后的收敛（#262、#263，main = a9e4398c）

§三 写下的两项已有实质推进，此处更新记录，避免报告停在旧状态。

**Preflight 的阻断→修复→重新检查已进入真实浏览器链（#262）。**
`design-lab/tests/e2e/browser_preflight_handoff.mjs` 由 shell 门驱动，对真实 loopback 服务
与真实 `design-lab/config/task-resources.json` fixture 执行 5 个断言步：视图挂载且输入框可见；
可解析工具 → READY 且判定 KPI 填充；缺失工具 → BLOCKED、点名被阻塞 ref 与 UNAVAILABLE、
并断言上一个 READY 已被清除而非留在屏上；改声明后同一 task id 复检 → READY；
交付中心在已连接且零交付包时读作真 0 而非未读回。shell 门断言**步数恰好为 5**，
少一步即变红，防止某步悄悄不再被执行。
该门的 skip 路径（无 node / 无 playwright / 无 Chromium / fixture 的 git 前提不成立）
是照抄同族门构造出来的，本轮未单独实测，记为未验证。

**能力库已成为真实读回并带上可得的分类轴（#263）。** 60 条记录（46 源 + 14 模型），
精确仓库路径连接 37/46。先测量后动手的结论值得留档：候选分类账 26 个字段里
`domains`、`artifactTypes`、`capabilityLayers`、`aestheticAxes`、`styleArchetypes`、`tier`、
`designQuality`、`currentVersion`、`referenceLineages`、`reviewedBy`、`reviewedAt`、
`humanApprovalRef` 在 980 条中**全空**，而 `sourceType`、`rights`、`evidenceLevel`、
`adoption`、`removalPath` 等 980/980 有值。因此提示词的"多轴分类"是**人工录入缺口**，
不是界面缺口；界面不代填，并把空轴显式列为未分类。
`evidenceLevel` 全部为 E0，按"仅声明"渲染为警示而非中性事实；热度带观测时间、来源与
`isNotQuality`，因为分类账策略写明 popularityIsNotQuality。

**仍开放（且不是我能替完成的）**：对某一项候选真实做适配 / 资格化 / 撤回——需要宿主运行
与人工验收；Human Jury 的 Accept/Reject/Change 面——`human_jury.py` 合同完备但无路由无 UI，
且其人工字段按铁律永不由 agent 填写；⑤ 的"未读回：响应缺少 X"文案目前只接到项目与仪表盘两面。

**本轮收尾证据（a9e4398c）**：`AUDIT_SCOPES 39 violations=0 ok=True`、`CAP_DONE shots=39`、
`test_capability_library.py` OK、`test_workbench_preflight_handoff_e2e.py` OK。

## 七、⑤/①/④ 三面收口、桌面端口径、开源池实测（2026-10-07，main = 52dfb791）

§六 的"仍开放"三项在本轮收掉两项，另一项被实测证明不是 agent 能做的。此处**追加**而非改写
§六——那一段是当时状态的记录，改写它会让"当时确实没做完"这件事失去痕迹。

**⑤ 形状异常（已并入 14d7179a / PR #265）。** `未读回：响应缺少 X` 从 2 面铺到 **21 处 seam 读回**。
两道门互补：AST 门按变量名证明每个 `apiOrEmpty` 绑定值都被引用，`ROUTE_VIEWS` 扫描门证明这句话
真的进了 DOM。扫描门当场逮到 AST 门看不见的一处谎——`projectPickerPanel` 空台账时提前 return，
把"服务没返回 projects"说成 `尚无项目`。六项变异逐一跑过两道门，结果记在 PR #265。

**① 未连接 与 ④ 真实空（已并入 52dfb791 / PR #266）。** 离线兜底载荷在 seam 源头打标，13 处空行
按读回状态措辞；`projectPickerPanel` 现在区分**三种**空（真 0 / 响应缺字段 / 未连接）。门是双向的：
未连接时 13 个路由零条"实况专属"措辞泄漏，而已连接且服务真答空集时必须照实说 `尚无项目`——
只有前半句的门，删光空态句子就能变绿。

**桌面端口径（owner 2026-10-07 裁定：只收口径，不删代码）。** 当前视口口径为
**1440 / 1280 / 1920 / 2560**，capture 入口只产出这四面 × 13 路由。`@390`、`@768` 的截图、
license 记录与 overflow 报告**作为历史证据原样保留在仓内**，不删除；移动端布局代码与样式
一律未动。§视口清单（本文档 §一 与视觉审计 §12 行）里出现的 390/768 数字属于该历史批次，
不代表当前口径。

**预检解析器一致性（已并入 aae165cc / PR #267）。** `doctor.probe_tools` 与
`task_resources._probe_tool` 对"这台机器有没有 node"给出过互相矛盾的答案，而
`/api/task-preflight` 的注释声称两者永不一致的情况不存在。#267 把 `preflight()` 里从未被使用的
`paths_describe` 形参接上。**本机判定一项未变**：剩余 BLOCKED 全部来自 `python-project-venv`，
它在 `paths.json` 中没有注册，而其登记说明明确拒绝硬编码 `Scripts/python.exe`，`paths.json` 又是
带绝对路径的受版本控制文件——**以何种平台中立方式声明项目 venv 属 owner 裁决**，未自采基线。

**开源池吸收实测（并行只读子智能体，结论逐条回查过 HEAD 字节）。** 结论：**本轮没有 agent 可完成
的吸收动作**，且"未吸收"这个状态本身是被正确记录的，不是缺口。依据：46 条源的 presence 为
`LOCAL_CACHE_ONLY` 37 / `ABSENT_FROM_GIT` 6 / `IN_REPO` 3；三条 `IN_REPO` 里两条落在
`test_inert_blob_placement.py` 认定的 inert quarantine 根内，第三条
`packages/capabilities/standards/front-end-design-checklist` 只有 LICENSE/README/SOURCE.md 三个
文件、在 `src/` 与 `apps/` 中零引用——即"随仓携带"，不是"已并入"。`src/` 下没有任何 per-file
upstream SPDX；真正的吸收登记册 `design-lab/research/global-absorption/SOURCE_REGISTRY.json` 6 条
全部 `review-required`，且 6 个 `integration.targetPath` 指向的 `design-lab/knowledge/…` 目录
**全部不存在**，与那 46 条完全不相交；晋升需要 `reviewedBy`，而分类账策略
`humanReviewOnly: true` 与 `verify_candidate_taxonomy.py` 写明 agent 不得设置该字段。
两条权利字段为非 SPDX 自由文本（`ui-ux-pro-max` = `MIT License`、`tool-control` =
`MIT / Apache-2.0 per-subtree`），后者是真实的按子树双许可，**不可归一**；二者一律交权利门，
不由 agent 改写观测到的值。

**两道门当场拦下我自己的两处错（门均未修改）。** 真实浏览器 overflow 门在 1440/1280/1920 各报一个
`<11px` 节点，来自我在表格单元里放的 `<small>`；词表门两次变红，一次因为我把 state 写成内联三元
表达式（它的文本扫描读不到 `UNAVAILABLE`），一次因为我在解释这件事的注释里写了它扫描的那个式样，
`X`/`Y` 被当成状态词。另有一处**度量**修正：list 行计数从"字面量出现次数"改为"渲染行数"
（字面量 + `emptyLi` 调用点，各减定义本身），**阈值 50 未动**——降阈值就是我在放宽断言。

**仍未开放**：候选的真实适配 / 资格化 / 撤回（宿主运行 + 人工验收）；Human Jury 的
Accept/Reject/Change 面（合同完备、无路由无 UI，人工字段按铁律永不由 agent 填写）；
`python-project-venv` 的平台中立声明方式（owner）；两条自由文本判决（权利门）。

**一条截图证据的结构性边界（本轮实测得出，不是推测）。** 视觉审计 §十五 对宿主 adapter 行留着
"未单独截图复核，按同一机制推定"。本轮想把它补成像素证据，结论是**当前证据工具做不到**：
`capture_workbench_screenshots.mjs:216` 固定 `fullPage: false`，每面只拍视口顶部，而 adapter 网格
在 `宿主 / Capability 状态` 面板之后——**低于 fold 的内容在全部 39 张已提交截图里都不存在**。
`audit_workbench_ui` 的 `report.json` 只记 `violations`，健康节点不留几何，所以也无法事后量。
因此这不是"再拍一张"能收的，而是截图口径本身的选择（加滚动帧 ≈ 提交集翻倍、约 +5 MiB；
或改 full-page ≈ 换掉整批证据的类别）。**属 owner 口径裁决，本轮只登记，不自行改证据工具。**
推广一句：本应用任何低于 fold 的内容，都不在现有截图证据的覆盖范围内。

**外溢数据实测（并行只读 + 逐条回查）。** 写路径治理是干净的：`runtime/paths.py` 的
`_local_path` / `checked_path` 把每个可写根限制在 `.project-local` 之下并拒绝外来盘符，
资产、bundle、报告、作业存储全部走这条路；`.project/paths.json` 的四个外置根在
`describe()` 里一律 `writable:false`。仓内所有硬编码的兄弟目录路径经逐条判读均为**读输入**。
三条需要记录的结果：

1. **唯一确认过的外溢已在此前清掉**：8 张 ComfyUI 生成图曾落在共享工具根
   `…/ComfyUI/output`，由 `scripts/clean_nebula_spill.py` 处理，manifest 在
   `.project-local/task-artifacts/spill-cleanup-20261007/`。
2. 同一根下还剩 `test_render_00001_.png`（352,325 B，mtime 2026-08-28）。**本轮不删。**
   依据是内容而非猜：读它自己的 `tEXt prompt` 块，是一张 SDXL 工作流
   （`sd_xl_base_1.0` + `clip_l/clip_g` + `sdxl_vae`，512×512，提示词
   "a beautiful modern corporate lobby, premium interior design…"），该提示词与文件名
   在本仓全文检索**零命中**（`test_render` 的命中全是无关的 `test_renderer_*` 测试名）。
   不可归因于 DESIGN-LAB 的文件，不因为"看起来像我们的"就从别人共享根里删掉。
3. `cli.py` 的 `backup --out` 与 `restore --into` 确实绕过 `checked_path`，但这是**有意的
   用户显式目标**（默认落在 `local_root/backups`，即受管内），备份到外部正是该功能的用途；
   给它加约束会砍掉一个真实特性。记录为"规则的显式例外"，不是缺陷。

反向泄漏仍在（已知、非本轮新增，数字为本机实测）。`.gitignore:71` 忽略整个 `.project-local/`；
其中 `projects/` 实测 **341.1 MiB**（最大两个工作区 281.7 MiB / 49.1 MiB），`task-artifacts/`
实测 **115.1 MiB**（含 `04-deliverables@*.png` 及其 `.license`）。这两个工作区里**不是缓存**：
按文件排出的前几名是 `assets/versions/<id>/delivery.zip`（单个 30.19 MiB，多版本并存）、
`native-plans/<id>/master.png`（18.51 MiB）与 `master.illustrator.svg`（3.46 MiB）——
即真实交付物与原生工程文件只活在单机，而 `reports/current/**` 的账本又引用它们。
需要的是"哪些进仓、进仓后多大"的口径裁决（本机 `git count-objects -vH` 实测
`size-pack` 为 **238.91 MiB**，一次性并入 341 MiB 交付物不是可逆动作），不是再删一次缓存。

## 八、② 补齐、六列成门、模型线索实测（2026-10-07，main = 2e634524）

**② 请求失败态已按路由实测（PR #270，并入 2e634524）。** 此前这一列只对连接流程断言过。
现在每个路由都被扫一遍：会读服务的 8 面在请求被拒时**只**渲染 `视图读回失败：<原因>`，
不残留上一面内容；不读服务的 3 面不得谎报失败。两种失败按**路由**交替注入——
传输层拒绝（vm 外创建，页面里 `instanceof Error` 为假，走 `String(error)`）与服务错误信封
（`api()` 在 realm 内 throw，走 `error.message`）是两条不同代码路径，且"两条都测到"由计数断言
自证，不靠意图。变异测试 3/3：吞掉失败留旧页 / 只说失败不说原因 / 报成未连接。

过程中我公开更正过一次：把 `Error: ` 前缀当成产品措辞问题写进了 PR 描述，实际是我探针
跨 realm 造成的夹具性质；追下去还发现当时只测了一条错误路径。

**状态矩阵六列现在全部有门。** ① 未连接（`appshell.mjs` 未连接扫描，13 路由）、
② 请求失败（同上，双向）、③ 加载中（路由切换后立即 `正在读回当前视图`，且旧 generation 的
迟到成功不得覆盖）、④ 真实空（正向对照：服务真答空集必须说 `尚无X`）、
⑤ 形状异常（`shape-notice-coverage.mjs` 按 AST 逐绑定 + 路由级畸形注入）、
⑥ 真实数据（`browser_design_layer_e2e.mjs` 全纵切，含 `reload persisted readback`）。
"几何门全绿≠界面好"这条限制不变。

**模型线索实测：本轮不哈希，理由是先量了再动手。** `design-lab/readiness/model-radar.json`
14 条：4 条 `WEIGHTS_COMPLETE`（minimax-h3 的 diffusion / text-encoder / video-vae / audio-vae，
合计 **39.55 GiB**，确实落在声明库根 `D:/All projects/Model library`），2 条 `METADATA_ONLY`，
8 条 `ABSENT`。那 4 条 `weights_sha256` 全空，看着像"该补没补"。两处实测否掉了动手：

- 该文件自己的 `policy[0]`：*"This registry records what is present and what is claimed;
  it never loads, downloads, **hashes**, or runs a model."* —— 往里写哈希违反它声明的合同；
- 4 条全部 `radar_state=BLOCKED_BY_LICENSE`、`license_id=PENDING-OWNER-ADJUDICATION`，
  其中 3 条硬件 `EXCEEDS`（需 20/12/8 GiB）。**阻塞不是缺 checksum**，补上也解不开任何东西。

所以模型线索剩下的工作是权利裁决（owner）与宿主验证（E2+），不是我能靠读盘完成的。

**capture 记录改为仓内相对路径（PR #271，并入 13e8cc94）。** `screenshot-manifest.json` 之前记的是解析后的
绝对路径，导致同样一次 capture 从 linked worktree 跑出来就和主 checkout 的记录不同——本轮
因此把一份 39 张的批次留在了仓外。改为按仓内相对路径记录（与 PNG sidecar 一致），确实指向
仓外时保留绝对形式。

**仍未收口、且需要 owner 拍的一条**：截图证据刷新遇到分叉。页序自 #259 起变化使旧的已提交 PNG
全部成为孤儿，要么并存（≈ +5 MiB）、要么删受版本控制的旧图。新生成的 78 个文件已移到
`.project-local/tmp/cap-orphans-270/` **备查未删**，仓库里的 manifest 未动。

## 九、并入后的全量复观测（exact SHA ae309cef，本机）

上面每一条都是分项证据；这里把整面重跑一遍，避免"每扇门各自绿、合起来没人验过"。

| 面 | 命令 | 结果 |
|---|---|---|
| 统一校验器 | `python design-lab/scripts/verify_design_lab.py` | 56 项 PASS，exit 0 |
| 溢出/裁切门 | `test_workbench_overflow_gate.py` | OK，43.2 s |
| 对比度门 | `test_workbench_contrast_gate.py` | OK，57.2 s |
| 浏览器纵切 | `test_workbench_design_layer_e2e.py`（`E2E_REQUIRED=1`） | PASS |
| 预检交接 | `test_workbench_preflight_handoff_e2e.py` | OK |
| node 三门 | `unit.mjs` / `shape-notice-coverage.mjs` / `appshell.mjs` | 全过，含 ⑤8 / ①7+零泄漏8 / ④2 / ②8双路径 |

**两处我拒绝轻信的读数。** 纵切与预检两条"浏览器"测试只用了 2.7 s / 2.5 s，而对比度门要 57 s——
这个差值可疑，所以没有直接采信。去读测试自己落盘的
`.project-local/task-artifacts/browser-e2e/browser-e2e-summary.json`：`result: PASS`、
`consoleErrors: 0`、12 个场景逐条在列（create-project → … → `reload-persisted-readback` →
`mobile-appshell-layout`），浏览器是 headless shell。快是真的快（loopback + 无 sleep），不是没跑。

同一份 summary 里 `subjectSha: "local"`——本机跑不绑定 SHA，只有 CI 会填。所以这条复观测的证据
类别是"本机当前 SHA 的一次通过"，不能当 E3/E4，也不该被引用成 CI 结论。

## 十、settled main 的全量收尾复观测（exact SHA `dcc9d12e96fa`，本机）

260–273 这批 UI PR 到这里全部并入，开放 PR 归零，没有待合分支，
所以这一节不是又一项分项证据，而是把整面在**稳定后的 main 字节**上重跑一遍。

### 并入清单（从 `git log --first-parent` 生成，不手抄）

| PR | merge SHA | 来源分支 |
|---|---|---|
| #260 | `22fddb3958f9` | DTALEX66/qoder/designlab-desktop-evidence-scope |
| #261 | `0d82428f5c3e` | DTALEX66/qoder/designlab-shape-degradation |
| #262 | `b846937482ce` | DTALEX66/qoder/designlab-preflight-chain |
| #263 | `a9e4398cc6b6` | DTALEX66/qoder/designlab-capability-library |
| #264 | `5e03117cdaab` | DTALEX66/qoder/designlab-ui-record-convergence |
| #265 | `14d7179a5b5c` | DTALEX66/qoder/designlab-notice-rollout |
| #266 | `52dfb791d0c9` | DTALEX66/qoder/designlab-readstate |
| #267 | `aae165ccdc35` | DTALEX66/qoder/designlab-declared-tool-roots |
| #268 | `f4f236a92015` | DTALEX66/qoder/designlab-ui-closeout-266 |
| #269 | `81f6615847a4` | DTALEX66/qoder/designlab-project-venv |
| #270 | `2e634524c563` | DTALEX66/qoder/designlab-failed-state |
| #271 | `13e8cc9496a8` | DTALEX66/qoder/designlab-manifest-relpath |
| #272 | `868dc9f7e7e8` | DTALEX66/qoder/designlab-ui-closeout-final |
| #273 | `dcc9d12e96fa` | DTALEX66/qoder/designlab-unreachable-diagnosis |

### node 侧（在 `dcc9d12e96fa` 上直接跑）

- `tsc --noEmit` → exit 0
- `vite build` → 产物与已提交 `apps/workbench/build` 逐字节相同（`git diff --exit-code -- apps/workbench/build` → 0）
- `unit.mjs` 过；`shape-notice-coverage.mjs` 过，21 个 seam 读回点全部有归属；
  `appshell.mjs` 过：⑤ 8 视图、① 未读回+零泄漏、④ 真实空正向对照、
  ② 8 视图三条失败路径（传输被拒 + 回复不可解析 + 服务错误）都实测到

### 浏览器门（真实 Chromium，经仓库自己的绑定跑器）

`python scripts/run_bound_test_suite.py --modules test_workbench_overflow_gate
test_workbench_contrast_gate test_workbench_ui_audit_gate
test_workbench_design_layer_e2e test_workbench_preflight_handoff_e2e`
（`E2E_REQUIRED=1`）→ Ran 7, OK, 108.7 s, skipped=0。
纵切自己落盘的 summary 是本轮新写的：`result: PASS`、`scenario: 12`、`consoleErrors: 0`、
`subjectSha: "local"` —— 本机跑不绑 SHA，只有 CI 会填，所以这条的类别是"本机当前 SHA 一次通过"。

### Python 全量绑定跑

记录器（`last-run.json`）自己写的字段：

| 字段 | 值 |
|---|---|
| run_id | `testrun-20261007T073246Z-forward-90ab9ebc04ed` |
| tests_run / failures / errors / skipped | 1939 / 0 / 0 / 4 |
| result / exit_code | `OK` / 0 |
| duration | 1377.306 s |
| 起讫 | 2026-10-07T07:32:46+00:00 → 2026-10-07T07:55:43+00:00 |
| test manifest | `sha256:562ecf713…` |
| subject / worktree_clean | `dcc9d12e96fa` / false |

**`worktree_clean=false` 的解释，不藏。** 跑完后工作树里 `reports/current/` 三个投影被测试就地重写，
差异只是 `audited_at` / `generated_at` 三个时间戳（我已把这三份还原成提交态）。这正是"投影绑定自己的
commit、生成时间不是测试时间"那条口径的表现，不影响被选中的用例集（`test_manifest_sha256` 是同一份）。

**这个记录器现在给不出的东西**：它记录 skip 的**数量**，不记录是哪 4 条、为什么跳。
所以上表里 `skipped=4` 只能读成"有 4 条没跑"，不能读成"4 条无关紧要"。这是仪器的缺口，不是结论。

**同日补记（缺口已修，且对 §十 那次跑做了补跑）**：`scripts/run_bound_test_suite.py` 现在把每条 skip
记成"用例 id + 该用例自己声明的原因"，stdout 逐条 `SKIP …` 打出，列表超过上限时明确说被截断，
并且当"计数有、身份没有"时以 `BOUND_SKIP_IDENTITY=DEFECT` 退 3 —— 那种组合只可能是记录器没读到自己
的输入，不能让一整面绿把它盖过去。

用改好的记录器在同一分支 head（`0b844b70`）上补跑了整面：`Ran 1946, OK, skipped=5`（1946 = 1939 +
本改动的 7 条；5 = 原 4 条 + 本改动自带的一条命名 fixture skip）。四条环境性 skip 被点到名：

| 用例 | 用例自己说的原因 |
|---|---|
| `test_model_manifest…test_cache_symlink_to_own_blob_supported_but_escape_and_broken_rejected` | `ENVIRONMENT_FAIL: native symlink creation lacks Windows privilege (1314)` |
| `test_visual_quality_scan_boundary…test_source_link_is_rejected_without_reading_target` | 同上，WinError 1314（客户端没有所需的特权） |
| `test_source_lock_presence…test_cache_digest_is_verified_only_when_this_machine_has_the_bytes` | `this machine has no vendor cache; cache integrity is NOT_VERIFIED here` |
| `test_workbench_launch…test_packaged_install_serves_the_committed_bundle` | `source checkout: no packaged workbench resource to verify` |

**读数**：这四条没有一条是"真检查悄悄不见了"。两条是 Windows 建符号链接需要
`SeCreateSymbolicLinkPrivilege`，本机按策略不用管理员权限去绕（提权跑不在授权范围内）；一条是这台机器
没有 vendor cache，缓存完整性在这里就是 `NOT_VERIFIED`；一条是源码检出根本没有"已打包安装"这件事可验。
所以 §十 那个 `skipped=4` 现在可以读成"4 条环境边界"，而不是"4 个未知"。

**口径**：这四条身份是**补跑**给的，不是从 `dcc9d12e` 那份旧记录里读出来的——旧记录器没写身份，
补跑的 head 也比它多 7 条用例。两者用例集的差就是本改动自己，所以可以合理判为同一组，但这句话是推断，
不是原记录的内容。缺口对未来的跑关闭；已落盘的旧记录不追溯改写，这是口径不是谦虚。

### 工具腿：实测无缺口

`python scripts/design_lab_doctor.py`（仓库自己的入口，不是裸调用）→ 4 个声明工具全部
`found=true` + `VERSION_VERIFIED` + `drift=[]`：`uv`←shutil.which; `git`←shutil.which; `ffmpeg`←declared:.project/paths.json#tools.ffmpeg; `node`←declared:.project/paths.json#tools.node。
即 ffmpeg 与 node 由 `.project/paths.json` 的声明根回答，uv 与 git 由当前进程 PATH 回答。

### 模型腿：仍是 owner 的权利门，我没有动

`design-lab/config/external-assets-index.json` 当前 24 条，
状态分布 {'review-required': 20, 'active': 4}，`generated_at` 仍是 `2026-08-16`。
这 20 条 `review-required` 是许可归属队列（openRAIL-M / Qwen / sherpa 各类条款都不是本项目的 MIT），
按铁律只能 owner 裁；我不刷新这份索引（会把本机绝对路径写进受版本控制的文件），
也不复制或散列权重（文件政策禁止，且阻塞项是许可与硬件，不是"找不到文件"）。

### README ↔ GitHub About：核对一致，无改动

逐条比对了仓库 About 与 `README.md` 开头的自我描述（定位、闭环序列、E0–E5 口径、
"不做第二画布/通用 Agent runtime"）——两边说法一致，没有需要改的一面。
交接里那条"待复核"到此关闭。**说明这是人读核对，不是门**：仓库里没有一条 CI 检查会因 About 漂移而变红。

### 清洁腿：四项仍待 owner，未删任何东西

保留点：`.project-local/tmp/cap-orphans-270/`（78 个新生成但已成孤儿的截图文件，备查未删）；
仓库内的 manifest 与受版本控制的旧图未动。其余三项（`.project-local/projects/` 的 341.1 MiB
交付物口径、需要 junction 拆除的 worktree 清理、6 个悬空 review-required 吸收目标与
`tool-control`/`omniparser` 的双许可）都记在 §四、§七、§八，同样没有被我"顺手清掉"。

### 这一节没有声称的

- 不是 E3：没有真实宿主里的 brief→原生可编辑产物→重开读回；
- 不是 E4：Jury 的人工字段一个都没由我填；
- 不是 E5：没有 tag、没有 release、没有安装/升级复现；
- 全绿的是"门的口径"，不是"界面好不好"——后者需要 owner 逐屏看渲染，§七已把口径写清。
