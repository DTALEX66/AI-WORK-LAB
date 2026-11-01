# OPEN-DESIGN-Assistance 唯一权威 HERMES 总任务书 V4.1

状态：`AUTHORITATIVE_ACTIVE_TASKPACK`  
版本：`4.1.0-authoritative`  
形成日期：`2026-08-08`  
目标仓库：`DTALEX66/OPEN-DESIGN-Assistance`  
本地目标：`D:\All projects\OPEN-DESIGN-Assistance`  
任务命名空间：`ODA4-*`  
唯一用户入口：`HERMES`

---

## 0. 总执行指令

HERMES 是本任务唯一总控。必须先完整读取：

1. `00_START_HERE.md`；
2. 本文件；
3. `02_CLOUD_DRIFT_AUDIT_20260808.md`；
4. `tasks/phases.json`；
5. `tasks/task-cards.json`；
6. 执行时的当前仓库、分支、工作树、CI 与 Open Design 事实。

正确执行链为：

```text
当前 exact tree
→ 旧任务/当前资产/当前证据继承矩阵
→ V4.1 云端事实纠偏（ODA4-0110…0118）
→ 专业设计公共内核（Phase 04）
→ UI/UX 黄金纵切（Phase 05 首项）
→ 平面/品牌/电商 Wave A
→ 展馆/3D/动效视频/音频/游戏视觉 Wave B
→ 包装/印刷/编辑/出版/插画/IP/数据可视化 Wave C
→ 来源、标准、大师方法与风格证据化
→ 真实 Benchmark、人类 Jury、Open Design E3
→ frozen exact tree 独立复审
→ READY_FOR_USER_APPROVAL
```

未经用户逐项授权，不得 commit、push、创建 PR、merge、修改 ruleset、tag 或 release。

---

## 1. 权威顺序与旧包处置

冲突时按以下顺序解释：

1. 执行时读取到的当前事实；
2. 本 V4.1 总任务包；
3. `02_CLOUD_DRIFT_AUDIT_20260808.md`；
4. V4.0 中未被 V4.1 推翻的任务和合同；
5. `OPEN-DESIGN-AUTHORITATIVE-CONTEXT-2026-08-07.md` 中仍有效的边界；
6. V3 已实现且可验证的资产；
7. V2/V2.1 研究资料和历史候选方案。

V2、V2.1、V3、V4.0、旧 `OD-*`、旧 `V4-OD-*`、旧 WORK-LAB 长期耦合方案统一为 `SUPERSEDED/REFERENCE_ONLY`。旧成果不删除，但不得作为并行活动入口。

HERMES 必须建立 `inheritance-matrix.json`，每项只能标为：

- `INHERITED_VERIFIED`
- `INHERITED_NEEDS_REVERIFY`
- `PARTIAL`
- `SUPERSEDED`
- `NOT_APPLICABLE`
- `NET_NEW`
- `BLOCKED`

只有 `PARTIAL`、`NET_NEW`、`BLOCKED` 修复和必要的 `INHERITED_NEEDS_REVERIFY` 进入执行队列。禁止机械重跑 V3 的 90 张旧任务卡。

---

## 2. V4.1 云端事实基线

以下是 2026-08-08 的只读观察值，不是永久事实；HERMES 启动时必须刷新。

| 项目 | 观察值 |
|---|---|
| 默认分支 | `main` |
| 远端 `main` | `d053a9b7feb966a0dedcd63ebf51356787661da8` |
| 最新提交 | `docs: upgrade project positioning to V4 (neutral design platform)` |
| 远端分支 | `main`、`migration/work-lab-minigame-cutover-20260807` |
| 分支关系 | 观察时均指向 `d053a9b7…` |
| PR | 未读到 PR |
| 仓库元数据体积 | 约 `358108 KB`，远端瘦身未独立证实 |
| Open Design | 观察为 `0.18.1` |
| 已完成重心 | Phase 00–02，Phase 03 部分完成 |
| 未发现提交 | Phase 04、05、06 |
| 显式 Domain Pack | 当前继承矩阵报告 1 个：MiniGame |

V4.0 的观察基线 `345684153ad05b5bffaead8d66308bd2ad437811` 与当前 main 已无共同祖先，因为仓库历史已被重写。V4.0 的旧 SHA、旧分支关系和旧 handoff 状态全部降级为历史参考。

当前定位是正确的，但交付重心约 `70%` 为治理/工程/运行准备，少于 `30%` 为真实职业设计能力。V4.1 只允许一个有限纠偏波；完成后必须立即进入 Phase 04/05。

---

## 3. V4.1 必须关闭的事实漂移

完整证据见 `02_CLOUD_DRIFT_AUDIT_20260808.md`。以下 13 项组成 Gate 0 重开原因：

1. Open Design 兼容矩阵仍写 `0.13.0`，其他 SSOT 已写 `0.18.1`；
2. 旧 handoff 报告的分支、SHA、main 和历史状态已失真；
3. README 使用不存在的 `--permission-root` 参数；
4. Windows configure 的 `--apply` 会写 Open Design 私有配置，违背安全声明；
5. MIT 根许可已选择，但 SPDX、REUSE、二进制 sidecar、SBOM 和第三方 BOM 未闭环；
6. Canonical CI 的 clean-tree 步骤只打印计数，不会在脏树时失败；
7. CI 许可门禁没有执行 REUSE、sidecar、SBOM/BOM 覆盖；
8. `capability-evidence-index.json` 未在当前 main 读到；
9. Figma、Penpot、browser 等 Adapter 在无 live 证据时被标成 `available`；
10. 当前 SHA 没有可读回的 E4 证据；
11. 本地历史瘦身和 GitHub 元数据体积未形成同口径证明；
12. Product Manifest 仍引用状态已过期的许可决定文件；
13. 插件/manifest 数量口径不一致。

HERMES 必须执行 `ODA4-0110…0118`，逐项关闭或以可复验证据标记 `BLOCKED`。不得用文档声明直接把 Gate 0 改回 PASS。

---

## 4. 最终产品定义

### 4.1 中文定位

> 以 Open Design 为主入口，模型中立、风格中立、领域中立、工具中立、权利安全的专业设计智能与视觉质量平台。

### 4.2 英文定位

> Open Design-first Neutral Professional Design Intelligence & Visual Quality Platform.

### 4.3 核心承诺

把 Brief、业务目标、现有资产和许可安全参考转化为：

- 有专业判断的设计方向；
- 有构图、字体、色彩、材质、光影、空间和节奏质量的视觉结果；
- 可编辑源文件与结构化资产；
- 可进入开发、印刷、包装、施工、视频、音频、3D 和游戏制作的生产交付；
- 有来源、权利、版本、评分、预检、证据和回滚的交付包。

### 4.4 五种中立

| 维度 | 定义 |
|---|---|
| 模型中立 | 不把一家模型写死为产品能力；通过受控 Agent/媒体适配器接入 |
| 风格中立 | 不以 Apple、黑金、科技蓝、玻璃或 HUD 为全局默认 |
| 领域中立 | 公共内核服务全部职业设计领域 |
| 工具中立 | Open Design 为主入口，下游按证据接入 Figma、Penpot、Blender、FFmpeg 等 |
| 权利中立 | 来源、素材、字体、模型、标准和参考均有权利状态与使用模式 |

### 4.5 非目标

- 不替代 Open Design 主应用、Studio/画布、daemon、模型路由或 Artifact；
- 不创建第四个聊天入口、Agent runtime 或模型网关；
- 不成为素材镜像、大型第三方仓库或大师签名风格生成器；
- 不以文件数量、Prompt 长度、静态验证、synthetic 或 VLM 自评冒充能力；
- 不把 MiniGame 的玩法、广告、变现、上架和发布作为平台主线；
- 不恢复与 WORK-LAB 的运行时、同步、Observer 或 Adapter 耦合。

---

## 5. 组件所有权与七层架构

| 组件 | 唯一职责 |
|---|---|
| Open Design | 项目、Studio/画布、Agent 启动、插件/Scenario/Atom 运行、Stage、GenUI、Artifact、预览和导出 |
| HERMES | 唯一用户入口、任务编排、状态、风险、审批、工具路由和证据汇总 |
| Codex writer | 单 writer 修改 Schema、脚本、测试、Manifest、Domain Pack 和文档 |
| Codex reviewer | 对 frozen exact tree 做全新进程、只读、独立复审 |
| OPEN-DESIGN-Assistance | 专业方法、Domain Pack、视觉质量、来源权利、Preflight、Handoff、Benchmark 和能力证据 |
| GitHub | 分支、PR、exact-SHA CI、远端事实和发布证据 |
| WORK-LAB | 完全切割，仅可保留历史迁移指针 |

目标架构：

```text
Open Design Studio / Agent Entry
          ↓
Neutral Intake & Design Router
          ↓
Professional Design Core
          ↓
Domain Packs
          ↓
Media Pipelines & Tool Adapters
          ↓
Quality / Rights / Preflight / Evidence
          ↓
Editable Multi-format Delivery
```

对外能力只保留三个公开入口：

1. `commercial-design-core`
2. `visual-quality-core`
3. `production-handoff`

旧插件作为兼容 Profile/Adapter 保留，不扩张为重复产品入口。Adapter 必须区分 `declared`、`structural`、`isolated-runtime`、`live-runtime`；没有版本、task/run、artifact 和 readback 时不得标为 `available`。

---

## 6. Domain Pack 完成合同与职业优先级

每个 Domain Pack 必须包含：

- manifest；
- brief schema；
- scenario；
- profile；
- rubric；
- preflight；
- handoff contract；
- source mapping；
- benchmark cases；
- evidence cards。

只增加 Prompt、README、模板、人物名单或素材链接不算完成。

### P0：第一交付波

1. UI/UX 与设计系统；
2. 平面与视觉设计；
3. 品牌/VI/KV；
4. 电商与商业视觉。

UI/UX 必须第一个形成完整纵切。五个固定 Benchmark：

1. B2B 数据仪表板；
2. 消费者移动应用核心流程；
3. 电商 PDP 与 Checkout；
4. 设置、权限与无障碍复杂状态；
5. 复杂响应式内容页面。

每案必须有 baseline/enhanced、三档视口、键盘路径、axe critical `0`、视觉回归、CJK/长文本压力、DTCG Tokens、可编辑产物、DESIGN.md、人类 Jury 和证据卡。至少一个取得真实 Open Design E3。

平面/视觉必须证明三方向为结构差异而非换色，并覆盖中文排版、网格、构图张力、缩略图识别和跨尺寸系列一致性。

品牌必须覆盖策略输入、视觉命题、VI/KV、字体、色彩、图形、摄影、动效/声音、治理和跨媒介手册，并纳入商标、字体和品牌资产权利预检。

电商必须覆盖主图、详情、商品卡、活动、广告、移动长页和多平台规格，并对人物、食物、产品比例、包装文字、透视、反射、材质和锐化建立真实性回归。

### P1：跨媒体职业波

- 展厅、展馆、导视和环境视觉；
- 3D 产品/空间/展陈/实时与离线渲染；
- 动画、动态品牌、视频和多比例交付；
- UI/品牌/环境/游戏音频和版权/响度预检；
- 游戏视觉、UI、HUD、动效、声音、控制器、可访问性与性能预算。

展馆交付不能只有效果图，必须有动线、内容矩阵、平/立/节点逻辑、屏幕规范、AV、照明、材料、BOM 和安装说明。

3D 必须覆盖尺度、拓扑、UV、PBR、灯光、相机、色彩管理、LOD、glTF/USD/MaterialX/OpenPBR/OCIO 等适用合同与可编辑交付。

视频必须覆盖分镜、时间线、运动层级、字幕、色彩、音画同步、编码、封面、多比例和 OpenTimelineIO/FFmpeg 边界。

音频最低合同包括 LUFS、EBU R128/ITU-R BS.1770、采样率、声道、True Peak、循环点、点击爆音、字幕/转写和来源权利。

### P2：专业版图补齐

- 包装与印刷；
- 编辑与出版；
- 插画、角色与 IP；
- 数据可视化。

---

## 7. 专业视觉质量系统

100 分模型：

| 维度 | 权重 |
|---|---:|
| 设计命题与具体性 | 10 |
| 设计感觉、张力与记忆点 | 12 |
| 构图、比例与视觉节奏 | 12 |
| 字体工艺与信息层级 | 10 |
| 色彩关系 | 7 |
| 材质、光影与空间层次 | 8 |
| 图像/人物/产品真实性 | 8 |
| 原创转化与风格纯度 | 9 |
| 品牌/项目一致性 | 7 |
| 商业与生产现实性 | 8 |
| 跨尺寸/跨媒介一致性 | 5 |
| 微观细节完成度 | 4 |

通过条件：总分 `>=82/100`，且领域 Rubric、权利门禁、无障碍和 Production Preflight 无 blocker。关键 Benchmark 必须由至少三名评审做盲测成对比较；V4.1 相对 baseline 的偏好率目标为 `>=70%`。

以下为硬 blocker：随机玻璃/渐变球/光晕、模板化 Hero+卡片+CTA、只换色三方向、过锐/塑料皮肤、手部/食物/产品/透视/反射错误、包装文字畸变、无物理依据材质灯光、像素级照搬、把大师姓名直接放入最终生成提示、以黑金/科技蓝/Apple/玻璃冒充高级感。

自动评分只做筛选，不得替代人类 Jury、领域评审、可访问性、权利和生产可行性判断。

---

## 8. 来源、开源资料、大师方法与风格治理

现有 112 条通用来源和 22 条视觉来源全部保留，迁移到 `SOURCE_REGISTRY_V3`。每项记录：固定来源、版本、最后验证日期、许可证、权利状态、证据链接、吸收模式、成熟度、领域、能力、测试、责任人和禁用条件。

吸收模式只允许：`vendor-adapt | adapter | derive | reference | quarantine`。成熟度只允许：`research-only | curated-draft | runtime-eligible`。

优先继承和补齐 UI/UX、设计系统、WCAG/ARIA、CJK 排版、浏览器测试、印前/PDF、动效/视频、音频、3D、展馆/施工、游戏可访问性、C2PA、SPDX/REUSE/CycloneDX/SLSA/Sigstore 等来源。新代码、字体、数据集、媒体、模型权重和安装器在许可与安全审查前全部进入 quarantine。

大师/工作室/流派研究只抽取可解释的决策方法，不复制签名作品和受保护元素。事实、观察、来源与推断分开。最终运行指令匿名化，不包含大师姓名。

每张 runtime 方法卡至少：两个可信来源、一个主要/机构/第一手来源、两个作品/时期/语境比较、适用/失效/禁用条件、身份消歧、权利与非模仿审查、一个真实案例验证。V1 最多晋级 20 张；420 条未核验种子继续隔离。

---

## 9. MiniGame 最终边界与功能冻结

MiniGame 已迁移到 `OPEN-DESIGN-Assistance/minigame-runtime`。它不会移回 WORK-LAB，也不会再成为平台主线或公共内核。

角色固定为：`reference-product + cross-media benchmark`。

允许工作：

- 安全修复；
- 可复现构建、平台导出与 drift gate；
- 资产去重、权利 sidecar、LFS/Artifact 与包体治理；
- 现有测试、CI 和兼容修复；
- Game Domain Pack 所需 HUD/UI/图标/动效/声音/皮肤/视觉规范/Fixture/失败案例；
- 只读拆仓成本报告。

禁止工作：新玩法、广告、变现、商店、运营、上架、产品发布扩张；把 Runtime、默认主题或资产反向 import 到公共 Core；把 MiniGame 测试冒充 UI/UX、品牌、电商或平台能力证据。

完成生成物治理和逻辑隔离后可产出拆仓成本报告，但物理拆仓需要新的用户授权。

---

## 10. Open Design 真实运行合同

执行时从官方来源确认当前稳定版本、Windows 安装状态、CLI/schema 和插件协议。V4.1 观察基线为 `0.18.1`，所有 SSOT 必须一致。

第一个 E3 黄金场景固定为：

```text
真实 UI/UX Brief
→ commercial-design-core
→ 三个结构差异方向
→ 人工选择
→ DESIGN.md + DTCG Tokens + 响应式 HTML
→ visual-quality-core
→ browser/axe/visual regression
→ production-handoff
→ Artifact + Provenance + 失败恢复读回
```

E3 必须包含真实 runtime ID、版本、task/run ID、Artifact 路径或 ID、Stage event、Provenance、失败注入与恢复。V4.1 观察到的部分 E3 只证明进程、命名管道、项目位置和 `anomaly-monitor-dark` 导入；三个公开 Bundle 注册、黄金场景和恢复证据仍未完成。

---

## 11. 安全、许可、CI 与证据门禁

### 11.1 安全边界

- Windows 原生优先；
- Git root 必须精确等于 `D:\All projects\OPEN-DESIGN-Assistance`；
- 不访问、枚举或修改 `E:\`；
- 不读取 `.env`、auth、token、credential、cookie、SSH key 或认证数据库；
- 不写用户 Home、Codex Home、Open Design 私有数据或项目外目录；
- 不把 `D:\All projects` 设为 writable/trusted root；
- configure 默认只允许项目内 dry-run；任何私有 `app-config.json` 写入必须从安全入口删除或单独授权；
- 未知脏状态、活跃 Git 操作、其他 writer 或不可回滚时停止写入；
- 不使用 `git reset --hard`、广域 clean、历史重写或项目外删除。

### 11.2 许可闭环

根 MIT 已选择，但 Gate 0 只有在以下全部完成后才可 PASS：逐文件 SPDX/REUSE、二进制 `.license` sidecar、NOTICE/第三方 BOM、SPDX/CycloneDX SBOM、运行时资产 100% 权利状态、未知/受限内容隔离、发布包来源与许可清单。

### 11.3 Canonical CI

根 CI 必须实际运行完整协议验证、Python 全部单测、MiniGame 受控子门禁、生成物 rebuild 后 `git diff --exit-code`、JSON/Schema/Markdown/链接、secret、REUSE/license、dependency、SBOM/BOM 和 V4.1 verifier。Clean-tree 步骤必须在任何非预期差异时非零退出，不能只打印计数。

Windows 是主兼容环境，Linux 只作结构/协议辅助。嵌套 workflow 不视为根 GitHub Actions。E4 需要 PR head/frozen tree/exact-SHA CI/远端读回一致。

### 11.4 证据等级

| 等级 | 可证明内容 |
|---|---|
| E0 DECLARED | 文档、计划或声明 |
| E1 STRUCTURAL | Schema、Manifest、语法和静态结构 |
| E2 ISOLATED_RUNTIME | 隔离环境真实命令与产物读回 |
| E3 LIVE_RUNTIME | Open Design/Agent 真实 task/run、Artifact、Stage/Provenance 与恢复 |
| E4 RELEASE | frozen reviewed tree、commit/push/PR、exact-SHA CI 和远端读回 |
| E5 COMMERCIAL | 客户、开发、印刷、施工或生产方真实验收 |

允许状态：`NOT_RUN | PASS | FAIL | BLOCKED | UNVERIFIED | SKIPPED_OPTIONAL`。没有 E3 不得称运行可用；没有 E4 不得称发布完成；没有 E5 不得称商业验证完成。

---

## 12. V4.1 执行阶段与关键路径

12 个阶段和 81 张任务卡的机器定义见 `tasks/phases.json`、`tasks/task-cards.json`。

| Phase | 目标 | Gate |
|---:|---|---|
| 00 | 当前事实与继承矩阵 | `BASELINE_TRUSTED` |
| 01 | V4.1 事实纠偏、安全、许可、CI、生成物与体量 | `GATE_0_TRUSTED_FOUNDATION` |
| 02 | V4 产品定义、三入口、Domain Pack/Evidence 合同 | `GATE_1_V4_ARCHITECTURE` |
| 03 | Open Design 兼容与真实运行 | `OPEN_DESIGN_E3` |
| 04 | 专业设计公共内核与视觉质量 | `PROFESSIONAL_CORE_READY` |
| 05 | UI/UX、平面、品牌、电商 Wave A | `GATE_2_UIUX_AND_WAVE_A` |
| 06 | 展馆、3D、动效视频、音频、游戏 Wave B | `GATE_3_CROSS_MEDIA` |
| 07 | 包装、印刷、编辑、出版、插画/IP、数据可视化 | `DOMAIN_PORTFOLIO_COMPLETE` |
| 08 | 开源、标准、大师与风格证据化 | `RESEARCH_EVIDENCE_READY` |
| 09 | Benchmark、人类 Jury 与失败回归 | `QUALITY_EVIDENCE_READY` |
| 10 | MiniGame 冻结、隔离与资产治理 | `MINIGAME_ISOLATED_REPRODUCIBLE` |
| 11 | Canonical Gate、冻结、复审与审批 | `READY_FOR_USER_APPROVAL` |

严格关键路径：

```text
ODA4-0001 → 0002 → 0003 → 0004 → 0005
→ 继承并复核 0101…0108 / 0201…0207 / 0301…0306
→ ODA4-0110…0118（有限纠偏波）
→ ODA4-0401…0406
→ ODA4-0501（UI/UX 五案例黄金纵切）
→ ODA4-0304…0306（以 UI/UX 完成真实 E3）
→ ODA4-0502…0504（平面、品牌、电商）
→ ODA4-0901/0902/0905/0907
→ ODA4-0601…0605 / 0701…0704 / 0801…0807
→ ODA4-1101…1104
→ READY_FOR_USER_APPROVAL
```

V4.1 防偏规则：

- 纠偏波后，除阻断 Phase 04/05 的安全、许可、构建问题外，暂停新增治理和基础设施；
- 每新增 1 个治理/文档/CI 修复提交，必须先完成或同时交付至少 1 个 Phase 04/05 真实能力提交；
- UI/UX 首个 E3 之前不得新增第二个参考产品；
- Wave A 完成前，不得把 MiniGame 或基础设施作为版本主叙事；
- 同一 checkout 始终只有一个 writer。

---

## 13. 阶段门禁

### Gate 0：可信底座重开

13 项事实漂移已关闭；危险配置写入已删除/隔离；许可链、REUSE、sidecar、SBOM/BOM 完整；依赖可复现；真实 clean-tree gate 有效；MiniGame 导出安全且测试后树干净；capability evidence index 存在；Adapter 状态按证据降级；远端历史/体积报告同口径；当前 exact tree 有证据。

### Gate 1：V4 架构

`PRODUCT_DEFINITION_V4`、product manifest、capability catalog、Domain Pack Spec、Evidence index、兼容矩阵和 handoff 相互一致；公开入口只有三个；MiniGame 与公共 Core 无反向依赖；WORK-LAB 无耦合。

### Gate 2：UI/UX 黄金纵切

五个固定案例完成；至少一个 E3；三视口、键盘、axe critical 0、视觉回归、CJK/长文本、可编辑交付、DESIGN.md、Tokens、Provenance 可读回；人类评分 `>=82`，相对 baseline 偏好 `>=70%`。

### Gate 3：多领域专业性

Wave A 四领域完整；Wave B 至少覆盖空间/展馆、3D、动效/视频、音频和游戏视觉；每个领域都有完整 Domain Pack 合同；不得用 MiniGame 证据替代其他领域。

### Gate 4：发布候选

Canonical local gate 全绿；测试后树符合冻结合同；来源、许可、SBOM、Provenance 完整；frozen exact tree 经独立只读 reviewer GO；未授权远端动作时停在 `READY_FOR_USER_APPROVAL`。

---

## 14. 每任务执行模板

1. 读取任务卡、依赖、风险、allowed paths 和 acceptance；
2. 记录 baseline branch/HEAD/tree/status；
3. 确认没有其他 writer；
4. 先增加或锁定测试/fixture；
5. 证明当前缺口或失败；
6. 由唯一 writer 实现；
7. 运行定向测试与阶段 gate；
8. 保存命令、退出码、产物、diff、证据和证据等级；
9. 检查 allowed paths、工作树和 MiniGame 冻结边界；
10. 更新 capability evidence 与任务状态；
11. 最多三轮有限修复；仍失败则 `BLOCKED`；
12. 进入下一依赖任务。

不得用计划、文件存在、代理口头声明、测试数量或旧成功替代当前 exact-tree 证据。

---

## 15. HERMES 启动提示词

```text
你现在执行 OPEN-DESIGN-Assistance 唯一权威 V4.1 总任务包。

目标仓库：D:\All projects\OPEN-DESIGN-Assistance
GitHub：DTALEX66/OPEN-DESIGN-Assistance
任务命名空间：ODA4-*

先完整读取 00_START_HERE.md、01_MASTER_HERMES_TASKPACK.md、02_CLOUD_DRIFT_AUDIT_20260808.md、tasks/phases.json、tasks/task-cards.json，再读取当前仓库 README、project-memory、product-manifest、capability/evidence、workflows、tests、Git 状态和 Open Design 事实。

从 ODA4-0001 重新读取当前 exact tree。建立 V2/V2.1/V3/V4.0 与当前树的继承矩阵，只执行净缺口。不得因为历史提交存在就把 task 或 gate 自动标为 PASS。

当前云端观察基线 d053a9b7feb966a0dedcd63ebf51356787661da8 已发生历史重写。刷新 branch/HEAD/tree/remote/status 后，执行 ODA4-0110…0118，修复 13 项事实漂移和虚假门禁。纠偏完成后立即进入 Phase 04/05，不得继续用治理、文档、CI 或 MiniGame 工作替代职业设计能力。

产品定位：以 Open Design 为主入口的中立专业设计智能与视觉质量平台。Open Design 拥有主应用、画布、Agent、Artifact、预览和导出；本仓库只做专业方法、Domain Pack、视觉质量、来源权利、Production Preflight、可编辑交付、Benchmark 与证据。不得新建第四个平台，不得恢复 WORK-LAB 耦合。

职业优先级：UI/UX 第一；随后平面/视觉、品牌、电商；再到展馆、3D、动画/视频、音频、游戏视觉/UI/音频；最后包装/印刷、编辑/出版、插画/IP、数据可视化。UI/UX 五个固定 Benchmark 至少一个取得真实 E3。

MiniGame 永久留在 OPEN-DESIGN-Assistance/minigame-runtime，角色固定为 reference-product + cross-media benchmark。实施功能冻结，只允许安全、构建、资产、测试、兼容和 Game Domain Pack fixture；禁止玩法、广告、商业化、上架和平台产品扩张；不移回 WORK-LAB。

保持 HERMES 唯一入口、单 writer、Windows 原生优先、audit/plan/staging 默认。禁止访问 E:\，禁止读取凭据，禁止写项目外、用户 Home、Codex Home 或 Open Design 私有配置。configure --apply 或任何私有配置写入必须单独授权，不能属于默认安全路径。

没有 E3 不得说运行可用，没有 E4 不得说发布完成，没有 E5 不得说商业验证完成。Adapter 无 live 证据时只能 declared/structural/unverified。

默认不 commit、不 push、不创建 PR、不 merge、不修改 ruleset、不 tag、不 release。完成本地 frozen exact tree 和独立只读复审后停在 READY_FOR_USER_APPROVAL，等待用户分项授权。
```

---

## 16. 最终验收合同与汇报格式

只有以下全部成立，才能报告“V4.1 本地深化闭环完成”：

1. 继承矩阵完成，旧任务未机械重跑；
2. 13 项事实漂移和 Gate 0 阻断关闭；
3. V4 定位、七层架构、三公开入口与 Domain Pack/Evidence 合同一致；
4. Open Design 当前稳定版兼容矩阵一致；
5. 专业设计公共内核真实可用；
6. UI/UX 五案完成且至少一个真实 E3；
7. 平面、品牌、电商 Domain Pack 完整；
8. Wave B/C 达到阶段要求；
9. 112+22 来源完成 V3 治理，最多 20 张方法卡 runtime-eligible，420 种子隔离；
10. 真实 Benchmark、失败回归和人类 Jury 证明质量提升；
11. 可编辑源、预览、字体/资产清单、尺寸/色彩、BOM、Preflight、Provenance、版本和回滚完整；
12. MiniGame 保持冻结、隔离、可复现，不污染 Core；
13. Canonical gate 对 frozen exact tree 通过；
14. 独立只读 reviewer 对同一 tree 输出 GO；
15. 没有访问 E 盘、读取凭据、项目外写入或未经授权发布。

最终只输出：

```text
状态：READY_FOR_USER_APPROVAL / BLOCKED

Baseline：branch / HEAD / tree / worktree / remote relation
Final：HEAD / frozen tree / clean-or-expected-dirty
已完成：按 ODA4 任务 ID
继承未重跑：旧资产、证据与理由
未完成或阻断：任务 ID / 根因 / 所需用户决定
证据：E1 / E2 / E3 / E4 / E5 分开
变更：文件范围 / 安全 / 许可 / 兼容影响
产品重心：治理修复 vs Phase 04/05 能力提交
MiniGame 冻结：允许变更 / 实际变更 / 越界检查
回滚：回滚点 / 回滚方法
等待授权：live apply / commit / push / PR / merge / ruleset / tag / release
```

不得把本地迁移、分支交付、main 合并、E3、E4、E5 混为一个结论。
