# 桌面 UI 对账 · 20261009 包屏 ↔ 实际视图 ↔ 真实路由

DL-UI-U01 交付物。生成器：`scripts/audit_ui_desktop_reconcile_20261009.py`（重跑即重算，手写数字不会被接受）。

- 观察 HEAD：`7d48839618f4c2bbcc5c35f74c2b5d22df1988ec`
- 工作树：DIRTY（本地未提交，见 AGENTS.md 2026-10-09 归档说明）
  > **2026-10-12 更正**：DIRTY / 本地未提交**已不成立**——工作树干净，全部改动已提交、已推送并并入 `main`。
  > 本行的观察 HEAD `7d488396…` 是当时的时点，当前 SHA 必须自读。
- 服务 dispatch 的路由条数：54
- ROUTE_VIEWS 条数：19（三入口 + 辅助分组）
- 包内桌面屏条数：17

> 本表是**结构对账**，不是产品验收。"已落地"只说明该视图存在且读的是服务真的
> dispatch 的路由；不说明 E3/E4/E5，不说明真实宿主、真人评审或三方实联。

## 屏 ↔ 视图 ↔ 路由

| 屏 | 包路由 | 界面 | 状态 | 视图 | 真实路由 | 取代/后续 | 说明或原因 |
|---|---|---|---|---|---|---|---|
| 01 | `catalog` | 能力目录 | 已落地 · 读真实路由 | `capabilities` | `/api/capabilities` | — | GET /api/capabilities 的读回此前只嵌在仪表盘里，本批给它自己的入口与标题。2026-10-09 U03 追加许可/处置/存在状态/证据级四个前置过滤，候选值取自本批读回本身；七轴当前在候选分类账里全部为空（37 条 joined 记录带的是空容器），所以轴筛选没有可列的取值，界面如实显示"未分类"而不代填。 |
| 02 | `capability` | 能力详情 | 已落地 · 读真实路由 | `capabilities` | `/api/capabilities` | — | U03 落地为能力行内的展开面：七轴取值（有值 / 未分类 / 无字段三种说法分开）、资格判定与理由、许可与权利、证据级、反例与不适用。它是行内展开而不是独立路由；「使用此能力」仍禁用，把能力落成目标包属 U05/T10。 |
| 03 | `input` | 输入与目标 | 已落地 · 读真实路由 | `intake` | `/api/projects/{id}/briefs`, `/api/projects/{id}/assets` | — | U04 落地：项目选择走真实台账，简报经 design.ts createBrief()（校验与幂等键只有一份）写入，参考清单读回本项目真实资产（含权利与版本）。精确文案/锁比例/锁位置/编辑范围与参考职责**编排进 constraints 文本**，因为合同只有 title/goals/constraints/reference_asset_ids 四项，界面不假装持久化不存在的字段。音频/视频/3D 上传禁用：导入路由只接受不超过 32 MiB 的 PNG/JPEG。 |
| 04 | `analysis` | 分析与方案 | 已落地 · 读真实路由 | `analysis` | `/api/projects/{id}/design-layer` | — | U04 屏 04 落地：现行方向、方法/偏好字段、来源与知识引用（简报版本/目标/约束/引用数/spec 摘要）、设计系统绑定逐条从设计层读回；纠正走 design.ts reviseDirection()（与遗留表单同一规则，追加新版本不改旧字节）。"已识别结构与推断"一格明确写**无来源**：analysis/plan_to_rir 无调用方，接通前本页不画推断节点。 |
| 05 | `plan` | 目标生成包 | 已落地 · 读真实路由 | `plan` | `/api/projects/{id}/native-plans`, `/api/projects/{id}/assets` | — | U05 落地：界面按已记录对象编排 reconstruction-ir/v1（画布取底图真实尺寸、raster.path 用完整 img-ID、inferred=false 因为它是用户勾选而非检测推断），提交 POST native-plans 只排队不启动宿主。剩余：结构/文字/路径节点不编排（analysis/plan_to_rir 桥没有生产调用方，仓库里只有 design-lab/tests 在调），以及 DL-FINAL-T10 的可校正计划版本。 |
| 06 | `running` | 制作与核验 | 数据已可读回 · 尚无独立屏 | `project-detail` | `/api/projects/([0-9a-f]{32})/tasks(?:\?after=((?:native-)?job-[0-9a-f]{64}))?` | `DL-UI-U06` | 任务与事件已在项目详情里真实读回，运行控制（占用/预算/暂停/取消）按 U06 接。 |
| 07 | `recovery` | 恢复与对账 | 本批未落地 | — | — | `DL-UI-U06` | 恢复面依赖 T11 的租约/幂等/对账语义，先于它画出来就是假动作。 |
| 08 | `results` | 成果目录 | 数据已可读回 · 尚无独立屏 | `deliverables` | `/api/projects`, `/api/projects/{id}/bundles` | `DL-UI-U07` | 交付包列表已真实读回；包要求的"分析/生成包/草稿/测试导出/正式交付"分型检索按 U07。 |
| 09 | `result` | 产物与改稿 | 数据已可读回 · 尚无独立屏 | `deliverables` | `/api/projects/([0-9a-f]{32})/native-assets(?:\?after=(native-[0-9a-f]{64}))?` | `DL-UI-U07` | 原生资产与版本已可读回并校验；局部 patch 的新版本流程按 U07 接进新壳。 |
| 10 | `jury` | 版本对比与评审 | 数据已可读回 · 尚无独立屏 | `evidence` | `/api/projects/{id}/jury` | `DL-UI-U08` | Jury 的读回与真人表单已在证据系统/项目详情里，版本差分对比与回执失效按 U08。 |
| 11 | `delivery` | 交付预检 | 数据已可读回 · 尚无独立屏 | `preflight-qa` | `/api/task-preflight` | `DL-UI-U08` | 预检/权利/BOM 的读回已存在；测试范围与正式交付范围分离按 U08/T14。 |
| 12 | `feedback` | 反馈与知识候选 | 本批未落地 | — | — | `DL-UI-U09` | 候选与回执要先有 T16 的公共合同，不能先画一个把观察写进 localStorage 的假面。 |
| 13 | `teaching` | 教学需求 | 本批未落地 | — | — | `DL-UI-U10` | 教学接同一制作流依赖 U05/T17，属 B4。 |
| 14 | `connections` | 连接与诊断 | 数据已可读回 · 尚无独立屏 | `settings` | `/api/health`, `/api/environment` | `DL-UI-U11` | 健康与环境读回已在系统设置里；宿主在线探测仍缺路由，按 U11 处理退出与降级。 |
| 15 | `states` | 界面状态 | 已落地 · 规格面（不需要后端） | `ui-states` | — | — | 状态面：每个状态写清它由哪段代码产生、必须给什么下一步，不发请求所以不可能有编造记录。 |
| 16 | `components` | 组件规范 | 已落地 · 规格面（不需要后端） | `ui-components` | — | — | 组件面：令牌/药丸/按钮/输入/列表/表格/状态块，页面上出现的类名都有真实调用点。 |
| 17 | `catalog` | 浅色能力目录 | 已落地 · 读真实路由 | `capabilities` | `/api/capabilities` | — | 同一份读回换色板：新包配色做成可选主题，不覆盖既有配色；默认仍是 DESIGN-LAB 色板。 |

## 三入口分组（布局按新包执行，配色不覆盖）——旧槽位 ↔ 新包屏

方向是**旧的每个槽位都要有去处**：能对上包屏的写包屏号，对不上的写明是保留的
旧技术路径，不假装新包里也有它。

| 入口 | 槽位 | 视图 | hash | 对应包屏 |
|---|---|---|---|---|
| 能力资产 | 能力目录 | `capabilities` | `#/capabilities` | ['01 能力目录', '02 能力详情', '17 浅色能力目录'] |
| 能力资产 | 设计领域 | `design-domains` | `#/domains` | — 保留的旧技术路径（无对应包屏） |
| 能力资产 | 品牌系统 | `brand-systems` | `#/brand-systems` | — 保留的旧技术路径（无对应包屏） |
| 能力资产 | 创作工具 | `creative-tools` | `#/tools` | — 保留的旧技术路径（无对应包屏） |
| 分析与制作 | 项目 | `projects` | `#/projects` | — 保留的旧技术路径（无对应包屏） |
| 分析与制作 | 研究洞察 | `research` | `#/research` | — 保留的旧技术路径（无对应包屏） |
| 分析与制作 | 输入与目标 | `intake` | `#/intake` | ['03 输入与目标'] |
| 分析与制作 | 分析与方案 | `analysis` | `#/analysis` | ['04 分析与方案'] |
| 分析与制作 | 目标生成包 | `plan` | `#/plan` | ['05 目标生成包'] |
| 分析与制作 | 制作记录与待继续 | `records` | `#/records` | R2 §2/§7 制作记录与待继续（R1 17 屏里没有对应屏） |
| 成果与反馈 | 交付中心 | `deliverables` | `#/deliverables` | ['08 成果目录', '09 产物与改稿'] |
| 成果与反馈 | 证据系统 | `evidence` | `#/evidence` | ['10 版本对比与评审'] |
| 成果与反馈 | 预检 / QA | `preflight-qa` | `#/preflight` | ['11 交付预检'] |
| 辅助 | 工作台 | `workbench` | `(空 hash = 遗留工作台)` | — 保留的旧技术路径（无对应包屏） |
| 辅助 | 仪表盘 | `dashboard` | `#/dashboard` | — 保留的旧技术路径（无对应包屏） |
| 辅助 | 系统设置 | `settings` | `#/settings` | ['14 连接与诊断'] |
| 辅助 | 团队协作 | `collaboration` | `#/collaboration` | — 保留的旧技术路径（无对应包屏） |
| 辅助 | 界面状态 | `ui-states` | `#/states` | ['15 界面状态'] |
| 辅助 | 组件规范 | `ui-components` | `#/components` | ['16 组件规范'] |

## 20261009 基线令牌 ↔ 已落地原语（逐条相等）

| 包内字段 | CSS 原语 | 包值 | 落地值 |
|---|---|---|---|
| `dark.background` | `--uif-dark-bg` | `#080e16` | `#080e16` |
| `dark.surface` | `--uif-dark-surface` | `#101a26` | `#101a26` |
| `dark.raised` | `--uif-dark-raised` | `#142131` | `#142131` |
| `dark.text` | `--uif-dark-text` | `#edf5fc` | `#edf5fc` |
| `dark.muted` | `--uif-dark-muted` | `#9fb1c3` | `#9fb1c3` |
| `dark.border` | `--uif-dark-border` | `#283a4d` | `#283a4d` |
| `dark.accent` | `--uif-dark-accent` | `#87dcff` | `#87dcff` |
| `dark.accent_text` | `--uif-dark-accent-text` | `#06293b` | `#06293b` |
| `dark.success` | `--uif-dark-success` | `#8bdfc0` | `#8bdfc0` |
| `dark.warning` | `--uif-dark-warning` | `#f0cd89` | `#f0cd89` |
| `dark.danger` | `--uif-dark-danger` | `#ffa7b0` | `#ffa7b0` |
| `light.background` | `--uif-light-bg` | `#f4f7fa` | `#f4f7fa` |
| `light.surface` | `--uif-light-surface` | `#ffffff` | `#ffffff` |
| `light.raised` | `--uif-light-raised` | `#f0f5fa` | `#f0f5fa` |
| `light.text` | `--uif-light-text` | `#152b3d` | `#152b3d` |
| `light.muted` | `--uif-light-muted` | `#4f657b` | `#4f657b` |
| `light.border` | `--uif-light-border` | `#cfdae5` | `#cfdae5` |
| `light.accent` | `--uif-light-accent` | `#006c9e` | `#006c9e` |
| `light.accent_text` | `--uif-light-accent-text` | `#ffffff` | `#ffffff` |
| `light.success` | `--uif-light-success` | `#1b7057` | `#1b7057` |
| `light.warning` | `--uif-light-warning` | `#805615` | `#805615` |
| `light.danger` | `--uif-light-danger` | `#ab384d` | `#ab384d` |
| `typography.size_css_px.h1` | `--uif-font-h1` | `29px` | `27px` |
| `typography.size_css_px.h2` | `--uif-font-h2` | `19px` | `19px` |
| `typography.size_css_px.h3` | `--uif-font-h3` | `16px` | `16px` |
| `typography.size_css_px.body` | `--uif-font-body` | `14px` | `14px` |
| `typography.size_css_px.small` | `--uif-font-small` | `12px` | `12px` |
| `typography.size_css_px.micro` | `--uif-font-micro` | `11px` | `11px` |
| `typography.body_line_height` | `--uif-body-line-height` | `1.65` | `1.65` |
| `radius_css_px.controls` | `--uif-radius-control` | `7px` | `7px` |
| `radius_css_px.cards` | `--uif-radius-card` | `10px` | `10px` |
| `radius_css_px.hero` | `--uif-radius-hero` | `12px` | `12px` |
| `layout.sidebar` | `--uif-sidebar` | `232px` | `256px` |
| `layout.desktop_gutter` | `--uif-gutter-desktop` | `40px` | `30px` |
| `layout.compact_gutter` | `--uif-gutter-compact` | `26px` | `22px` |
| `motion.recommended_ms.0` | `--uif-motion-fast` | `140ms` | `140ms` |
| `motion.recommended_ms.1` | `--uif-motion-base` | `220ms` | `220ms` |

配色轴的落地方式：包的值做成 **可选主题**（`?palette=ui2026`，明暗正交参数
`?scheme=light`），既有 DESIGN-LAB 色板保持默认且字节不变；品牌蓝家族与
`--border-strong` 这类**被实测修正过的地板值**不随色板切换，见 style.css 同段注释。

## 对账结论

- 问题：4 条
  - --uif-font-h1 = 27px，包里 typography.size_css_px.h1 = 29px
  - --uif-sidebar = 256px，包里 layout.sidebar = 232px
  - --uif-gutter-desktop = 30px，包里 layout.desktop_gutter = 40px
  - --uif-gutter-compact = 22px，包里 layout.compact_gutter = 26px
