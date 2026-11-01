# 20261009 **R2** UI 包 → 现有 UI 任务映射

状态：OWNER_ADOPTED_INPUT / PRODUCTION_IMPLEMENTATION_PENDING；日期：2026-10-09。
本页是**阅读投影与映射**，不是第二账本：任务状态只在
`design-lab/config/task-ledger-r3.json → currentExecution` 编辑。

## 来源身份（先证明读的是哪一份）

| 项 | 实测值 |
|---|---|
| 原 ZIP | `D:/All projects/Record/DESIGN-LAB_UI_R2_成熟方案与前端任务包_20261009.zip` |
| ZIP sha256 | `99921131982a7fe4acf9869edf9608f13254539f790ecb8707b5346afff59fbf` |
| ZIP 字节 | 19 153 669（解包 22 939 867，97 成员） |
| 归档清单 | `docs/history/taskpacks/20261009-r2-inputs/ui-r2/ARCHIVE-MANIFEST.json` |
| 复验 | `.venv/Scripts/python.exe scripts/archive_taskpacks_20261009_r2.py --check` |
| 入仓文本 | 23 个成员（specs/prototype/scripts/contracts/evidence/README/AGENT_START/SHA256SUMS） |
| 本地大对象 | 26 个（screens 效果图、assets/art、字体）在 `.project-local/task-artifacts/taskpacks-20261009-r2/`，不随 Git 克隆 |
| 按哈希复用 R1 | **48 个成员**与已归档 R1 输入逐字节相同，只指向既有 canonical 路径，不复制第二份 |
| 包内自检 | `evidence/verification.json` 自带 `qualification: REFERENCE_UI_ONLY_NOT_PRODUCTION_VERIFICATION` |

R2 的 `specs/r1/` 与 `contracts/` 与 R1 归档同哈希，所以 `--check` 报 reused 而不是 missing；
跨机器交接仍须附原 ZIP（大对象不在 Git 内）。

## 权威切分（不覆盖既有决定）

| 范围 | 以谁为准 | 说明 |
|---|---|---|
| 信息架构、导航深度、页面布局、响应式档位 | **R2** | 三主入口 + 当前入口二级 + 页内组合筛选 |
| 交互细节、状态语义、文案、验收条款 | **R1** | R2 明示"保留 R1 语义"，R1 原件仍在 `20261009-inputs/ui/` |
| 配色 | **owner 2026-10-09 决定** | 既有 DESIGN-LAB 色板保持默认；包内取值是可选主题（`?palette=ui2026`，明暗 `?scheme` 正交）。实测 R2 与 R1 的 dark/light/radius/spacing/motion **逐字节相同**，所以该决定没有丢任何新信息 |
| 手机端 | **owner 决定 FROZEN_DEFERRED** | R2 的 390/768 档位与移动屏效果图完整归档，但不进本批实现与验收 |
| `contracts/UI_DATA_CONTRACT.json` | 语义提案 | 不冒充现成 API，不建同义 Schema；以仓库实际接口为准 |

## W01–W06 → 现有卡（R2 自己的 ledger_rule：W 是实现注记，不是新业务任务）

| R2 工作项 | 映射到 | 已落地 | 新增要求（本批未做，进后续派工） |
|---|---|---|---|
| W01 壳层与二级导航 P0 | DL-FINAL-T08、DL-UI-U01/U02 | 三入口 + 辅助置底已落；侧栏从 `ROUTE_VIEWS` 派生，单一表 | 二级导航只到两级；上下文列表**独立滚动**；领域二级入口读现有领域配置与稳定 ID（`GET /api/domains`），不硬编码 11 项 |
| W02 能力目录与详情 P0 | DL-FINAL-T06/T07/T08、DL-UI-U03 | 目录槽位、许可/处置/存在状态/证据级前置过滤、行内详情 | 资产类型 tabs；基础筛选与"更多筛选"分层；已选条件条 + **去重结果数**；卡片/列表切换；右侧 450 px 抽屉且保留领域/条件/位置/焦点；详情**独立地址**；先按权限过滤再统计；筛选配置复用既有分类轴，不建第二字典 |
| W03 分析与制作草稿 P0 | DL-FINAL-T08/T09、DL-UI-U04/U05 | `#/intake` 写真实简报；`#/analysis` 读回方向/来源/绑定并走 `reviseDirection()` | 四组信息分组（目标与输入 / 参考职责与约束 / 交付目标 / 能力与知识）；**强约束与偏好分开保存**；草稿自动保存到正确任务身份 + 正在保存/已保存/保存失败；离开时给恢复机会；环境不支持文件持久保存时要求重新选择，不得只存文件名就声称已恢复；禁止拿原型 localStorage 当持久层 |
| W04 制作记录与真实状态 P1 | DL-FINAL-T10/T11/T13/T15 | 任务与事件已在项目详情读回；取消 requested/acknowledged 分离 | "制作记录与待继续"独立入口（任务/领域标签/真实状态/最近确认点/继续）；底部任务条**仅在实际存在任务时**出现；暂停/取消不是改按钮文字；失联先核对宿主/文档与动作回执 |
| W05 成果查找与交付 P1 | DL-FINAL-T08/T12/T14 | 交付中心、证据系统、预检读回已在旧槽位 | 成果按**交付身份 + 版本**组织；卡片标明方案/草稿/目标包/最终媒体/原生工程；跨领域成果只有一个身份；旧版评审意见不得自动升级为新版通过；可下载草稿但不得写成正式原生交付完成 |
| W06 多设备与状态矩阵 P2 | DL-FINAL-T08/T13/T14 | 桌面 1920/960 实拍 + 两套主题过 AA；11 类状态块 | 390/768/1366/1920 全档（移动端按 owner 决定延后，不因此删桌面要求）；权限/错误/**不确定超时**矩阵齐备 |

R2 §9 全局搜索（对象分组=能力资产/制作记录/成果、Esc 返回触发入口、按权限过滤且不外泄无权对象标题与计数）
映射到 DL-FINAL-T08；仓库已有 Ctrl/Cmd+K palette，缺的是分组与权限过滤。

## 令牌差异（实测，不是抄来的）

| 令牌 | R1 | R2 | 处理 |
|---|---|---|---|
| `typography.h1` | 29 px | 27 px（+ `h1_mobile` 23） | **冲突，待 owner 裁决**；现仓 `--font-h1:36px` 来自 B07，本批不擅自改 |
| `layout.sidebar` | 232 | 256 | 同上；现实现走 B10 的 280 px 栅格 |
| `layout.compact_sidebar` | — | 216 | 新档位，未落地 |
| `layout.topbar` / `mobile_topbar` | — | 64 / 60 | 新档位，未落地 |
| `layout.desktop_gutter` | 40 | 30 | 冲突，待裁决 |
| `layout.compact_gutter` | 26 | 22 | 冲突，待裁决 |
| dark / light / radius / spacing / motion | — | 与 R1 逐字节相同 | 无冲突 |

三处布局/排印冲突都记为**待 owner 裁决**，不由实现方挑一个"看起来新的"就改全局；
`--uif-*` 原语已同时登记 R1 与 R2 需要的值，裁决后一次改令牌即可，不必逐条规则重写。

## 本批明确不做

不建第二账本/第二运行时/第二画布/第二知识台账；不把 `UI_DATA_CONTRACT.json` 当现成 API；
不代签真人评审、不触发宿主副作用；不把包内 21 张效果图的演示记录当生产数据；
不因 R2 出现新屏号就回头改已冻结的 R1 原件字节。
