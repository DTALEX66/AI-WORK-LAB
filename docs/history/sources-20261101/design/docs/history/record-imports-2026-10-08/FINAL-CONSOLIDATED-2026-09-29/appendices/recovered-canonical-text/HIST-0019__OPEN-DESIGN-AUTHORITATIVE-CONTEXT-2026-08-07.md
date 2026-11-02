# OPEN DESIGN 当前对话唯一权威上下文

> 状态：`ACTIVE_CONVERSATION_BASELINE`  
> 基线日期：2026-08-07  
> 项目：`DTALEX66/OPEN-DESIGN-Assistance`  
> 本地目标：`D:\All projects\OPEN-DESIGN-Assistance`  
> 用途：把历史对话、V2/V2.1/V3/V4 任务包、WORK-LAB 最终分库决定、完整 Overlay、任务卡和当前 GitHub 只读观察收束为本对话唯一工作基线。

## 1. 权威顺序与冲突处理

后来的明确决定覆盖早期方案，执行时按下列顺序解释：

1. **当前 GitHub 事实**：以执行时重新读取的 `main`、迁移分支、文件和 CI 为准；旧 SHA 只是历史观察值。
2. **2026-08-07 最终切割决定**：Open Design 已与 WORK-LAB 完全切割，独立归属 `DTALEX66/OPEN-DESIGN-Assistance`。
3. **V4 Open Design 仓库纠错项**：保留 `V4-OD-001`～`V4-OD-010` 的安全、证据、CI、瘦身、许可和真实 E3 要求；废止 V4 中长期双仓耦合、持续 Adapter/Observer/监控关系。
4. **V3 深化优化包**：保留 16 阶段、90 张任务卡、199 文件 Overlay、质量模型、领域能力、生产交付和评测合同；执行前必须对当前树做继承矩阵，不得机械重跑全部任务。
5. **V2/V2.1 研究资产**：作为研究与候选实现来源，不自动等于运行时能力、商业能力或权威知识。

以下旧内容只作 `REFERENCE_ONLY/SUPERSEDED`：

- “Workflow Assistance＋Open Design＋Observer”三模块方案；
- WORK-LAB 内长期维护 Open Design Adapter、事件、Projection、Observer 页面、CI、同步或升级；
- 把两个仓库视为需要永久绑定的双仓产品；
- 旧文件名复用产生的 `01_MASTER_HERMES_TASKPACK.md` 混淆；
- V4 的 `OD-001`～`OD-010` 与 V3 的 `OD-0001`～`OD-1504` 不是同一编号空间，本文件统一称前者为 `V4-OD-*`。

## 2. 最终项目定位

`OPEN-DESIGN-Assistance` 的最终定位是：

> **Open Design-first、Agent-compatible 的商业设计智能、视觉质量、专业生产与可编辑交付增强层。**

一句话目标：

> 让 Open Design 和兼容 Agent 从“会生成设计”升级为“具备专业判断、视觉质感、生产约束和商业交付能力的 AI 设计团队”。

职责分工：

| 组件 | 唯一职责 |
|---|---|
| Open Design | 项目、Studio/画布、模型与 Agent 启动、插件/Scenario/Atom 运行、Stage event、GenUI、Artifact、预览和导出 |
| 兼容 Agent | 推理、执行、受控工具调用与阶段任务 |
| OPEN-DESIGN-Assistance | Domain Pack、专业方法、风格/大师研究、Rubric、来源权利门禁、视觉质量、生产预检、交付合同、Benchmark 和能力证据 |
| GitHub | 远端事实源、分支、PR、exact-SHA CI 与发布证据 |

非目标：

- 不替代 Open Design 主应用、画布、daemon 或模型路由；
- 不新建 Agent runtime、聊天 UI、模型网关或第四个平台；
- 不做“大师风格生成器”，不复制受保护作品和签名元素；
- 不以模板、文档、人物名单或 Prompt 长度冒充能力；
- 不以 VLM 自评、静态文件或 synthetic 测试冒充真实运行；
- 不把 MINIGAME 产品 Runtime、广告、上架、变现和运营并入本项目主线。

## 3. 最终所有权边界

2026-08-07 后：

- Open Design 不再是 WORK-LAB 模块、支撑区或子产品；
- WORK-LAB 不保留设计代码、Skills、插件、大师资料、风格研究、模板、Rubric、资产、专属 Adapter、事件、Projection、Observer 页面或 CI；
- WORK-LAB 不再同步、监控、更新、执行或维护本仓库；
- WORK-LAB 只允许保留一次性迁移指针和 Git 历史；
- 未来如需重新接入，只能按普通外部项目重新登记，不能恢复旧耦合。

MINIGAME 仅保留设计边界：HUD、UI、图标、视觉规范、Prompt、Skin、设计 Fixture 和运行时参考；平台工程、广告、商业化、发布和完整产品逻辑排除。

## 4. 目标商业设计闭环

```text
Brief / 资产 / 参考
→ 来源、权利与安全门禁
→ Brief 标准化与任务路由
→ 专业调研、竞品、策略、Reference DNA
→ 风格谱系与大师方法证据
→ 三个结构上不同的方向
→ 人工选择并锁定方向
→ DESIGN.md / DTCG Tokens / Components / Asset Contracts
→ 图片 / HTML / PPTX / PDF / Motion / 3D / Spatial 多产物生成
→ Domain Jury + Visual Quality Jury + 确定性检查
→ 最多三轮有界精修
→ 数字 / 印刷 / 包装 / 空间 / 动效 / 3D 生产预检
→ 可编辑交付 + BOM + Provenance + 版本 + 回滚
→ Benchmark + 人工评审 + 客户/生产反馈 + 能力证据
```

交付不能只有合层图片；完整商业交付应包含可编辑源、预览、字体与素材清单、尺寸与色彩、版本、生产说明、评分、预检、BOM、Provenance 和回滚信息。

## 5. 七层目标架构

1. 治理层：来源、许可、安全、证据、风险、审批；
2. 知识层：专业设计、风格谱系、大师方法、标准和行业规则；
3. 协议层：Brief、DNA、方向、状态、评分、预检、交付 Schema；
4. 能力层：可测试的 Atom、Bundle 和 Profile；
5. 编排层：Scenario、Pipeline、GenUI、恢复与 devloop；
6. 执行层：Open Design、兼容 Agent、媒体/代码工具和外部 Adapter；
7. 证据层：Eval、案例、人工评审、生产反馈和发布证据。

目标单一事实源：

- `product-manifest.json`
- `SOURCE_REGISTRY_V3.json`
- `MASTER_REGISTRY_V3.json`
- `STYLE_ONTOLOGY_V3.json`
- `design-project-state.json`
- `artifact-provenance.json`
- `capability-evidence.json`

## 6. 设计领域范围

必须覆盖并逐步形成可交付能力：

1. 品牌策略、VI、KV 与跨媒介视觉系统；
2. 平面与整合传播；
3. UI/UX、网站、应用和设计系统；
4. 产品、电商和商业摄影视觉；
5. 文化墙、展厅、展陈与环境图形；
6. 包装、印刷与货架视觉；
7. 编辑出版和长文排版；
8. 动效、动态品牌与视频视觉；
9. 3D 产品、空间、材质与灯光；
10. 插画、角色与 IP 系统。

每个领域必须同时具有 Scenario、Schema、Rubric、Profile、Case 和 Handoff；只增加 Prompt 不算完成。

## 7. 视觉质量硬门槛

### 7.1 100 分模型

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

通过条件：总分 `>=82/100`，领域 Rubric 无 blocker，资产权利无 blocker，Production Preflight 无 blocker。

### 7.2 “有感觉”的可观察定义

- 命题：有清晰、具体、不可互换的主张；
- 张力：尺度、疏密、动静、规则与破格受控；
- 节奏：视线、重复与变化有明确逻辑；
- 克制：主动删除低价值装饰；
- 记忆点：缩略图和短时观看仍可识别；
- 语境：符合品牌、行业、地域、媒介和观众；
- 完成度：对齐、间距、边缘、材质、图片、状态与输出全部收口。

### 7.3 去 AI 味阻断项

- 无语义渐变球、光晕、随机玻璃和悬浮；
- 所有卡片同圆角、阴影、间距和权重；
- 只换配色的 Hero/四卡片/CTA 模板；
- 过度锐化、塑料皮肤、错误手部、食物、透视、反射和产品比例；
- 没有真实物理来源的材质与发光；
- 每个区域都抢焦点；
- 伪造数据、Logo、评价、案例或“用户认可”；
- 参考图像素级照搬；
- 用大师姓名充当风格滤镜；
- 把“黑金、科技蓝、渐变、玻璃”直接等同于高级。

### 7.4 精修规则

每轮只解决最高影响的 3～5 个问题，最多三轮；评分不升、主体漂移或破坏锁定元素时立即停止并回滚该轮。

## 8. 风格与大师研究规则及真实成熟度

原则：

- 可研究所有年代、地域、媒介、专业领域的大师、工作室、流派和工艺传统；
- 研究目的是提炼可迁移的决策方法，不是复制签名作品；
- 正式方法卡需身份消歧、至少两个可靠来源、至少两个作品/阶段比较、观察与推断分离、适用条件和失效条件；
- 最终生成指令必须匿名化，不含大师姓名；
- 项目/品牌 DNA 至少 50%，大师方法合计原则上不超过 35%；
- 一个方向最多一个主谱系、两个辅助谱系，禁止平均混合五六种风格。

已导入的研究资产：

| 资产 | 数量 | 当前真实状态 |
|---|---:|---|
| 大师/工作室发现记录 | 497 | 77 条为本地方法卡草稿；420 条为未验证 research seed |
| Anchor Method Cards | 77 | 全部需要补来源后才能成为权威声明 |
| Style Lineages | 47 | 全部为需补证据的 curated draft |
| Style Analysis Cards | 47 | 全部为本地综合草稿 |
| V2 全局来源 | 112 | 需按许可、模式和证据逐项晋级 |
| V2.1 视觉来源 | 22 | 以 reference/derive 为主，不 vendoring 受保护内容 |

V1 运行时目标：`runtime-eligible` 大师方法不超过 20 个，每项至少两个来源，其中至少一个为主要或机构来源。当前不得把 497 条名单整体加载到运行 Prompt。

## 9. 开源、网站与资料吸收原则

五种模式：

| 模式 | 处理 |
|---|---|
| `vendor-adapt` | 仅明确宽松许可、小体量、必要且审查过的结构/代码 |
| `adapter` | 大型工具、独立运行工具或许可证边界复杂项目，保持进程/依赖隔离 |
| `derive` | 从资料中抽取通用方法，用本项目自己的表达和 Schema |
| `reference` | 标准、论文、品牌手册和受保护规范，只记录来源与适用结论 |
| `quarantine` | 许可、身份、安全或质量不明，禁止运行时加载 |

V2 全局来源当前分布：`adapter 69`、`derive 19`、`quarantine 4`、`reference 11`、`vendor-adapt 9`。状态为 `adapter-next 54`、`adopt-now 33`、`reference-now 12`、`review-required 13`；这些是历史决策标签，不等于已实现，后续必须重新映射为 `research-only / curated-draft / runtime-eligible` 和真实证据级别。

明确禁止：整仓复制第三方 Skill；自动下载/执行字体、素材、数据集、模型权重或新发现代码；把 GPL/AGPL、非商业许可或未知权利内容直接放进商业核心；把品牌资产或大师作品作为发行素材；未经审查直接进入 Agent 上下文。

## 10. 已完整拉取的 V3 包

完整任务包已在当前工作区展开并通过自带校验：

```text
TASKS=90
OVERLAY_FILES=199
ERRORS=0
VERIFY_COMPLETE_TASKPACK=OK
```

V3 资产概况：

- 16 个阶段、90 张结构化任务卡；
- 199 个无同路径冲突的 V2+V2.1 Overlay 文件；
- 21 个 Atom；
- 2 个现有 Bundle：`commercial-design-core`、`visual-quality-core`；
- 6 个 Scenario；
- 19 个领域/视觉 Rubric；
- 12 个 Profile；
- 24 个 Schema；
- 28 个 Knowledge 文件；
- 112 条全局来源、497 条大师发现、77 张方法卡、47 条风格谱系；
- 任务、风险、审批、证据、复审、回滚和发布 Schema。

V4 目标要求对外最终收缩为三个入口：

1. `commercial-design-core`
2. `visual-quality-core`
3. `production-handoff`

原七个插件应转为 Profile，21 个 Atom 保持内部 Pipeline 组件。当前 V3 Overlay 只有前两个 Bundle；`production-handoff` 仍需形成明确、可验证的公开入口。

## 11. 证据等级

| 等级 | 含义 |
|---|---|
| E0 | 声明或文件存在 |
| E1 | Schema、Manifest、结构和静态验证通过 |
| E2 | 隔离环境命令成功且有产物读回 |
| E3 | 当前 Open Design/Agent 实际运行、产生 task/run ID、Artifact、Stage/Provenance 读回 |
| E4 | Frozen exact tree 经独立复审、提交/推送并有 exact-SHA CI 与远端读回 |
| E5 | 客户、开发、印刷、施工或生产方真实验收 |

静态文件不能证明 E3；旧 SHA 的绿色 CI 不能证明当前树 E4；内部 Demo 不能证明 E5。

## 12. 当前 GitHub 只读事实（2026-08-07）

### 12.1 `main`

- 当前观察到的 `main` HEAD：`c8212401e891e7c3f0e4a6f36cdb11dbcca24e27`；
- 最新 main 提交信息：`docs: clarify Open Design V3 repository description`；
- `main` 已包含早期 V3 合同、V2/V2.1 研究资产、`design-system/`、`minigame-runtime/` 和 `project-memory/`；
- 根级 `LICENSE`/`NOTICE` 未建立，仍只有 `LICENSING_DECISION_REQUIRED.md`；
- 没有 PR。

### 12.2 迁移分支

- 分支存在：`migration/work-lab-design-extraction-20260807`；
- 相对 `main`：ahead 4、behind 0；
- 当前差异共 32 个文件：31 个迁移候选能力/测试文件＋1 份最终 Handoff；
- 主要新增：MINIGAME Design Domain Pack、12 个 Benchmark brief、12 张非权威 Evidence Cards、4 个 Schema、3 个 verifier、3 个 test；
- 分支未合并到 `main`，未创建 PR；
- Handoff 报告的迁移分类：`IDENTICAL 442`、`SOURCE_ONLY 31`、`SEMANTIC_CONFLICT 13`、`HISTORICAL_ONLY_NOT_MIGRATED 4`、`LICENSE_BLOCKED 3`、`TARGET_ONLY 3`；
- Handoff 报告源候选范围 493 个文件，无敏感文件迁移；
- 分支报告的验证均为 E1/E2，明确没有 E3/E4/E5。

### 12.3 迁移证据缺口

Handoff 声称根目录存在并引用：

- `WORK-LAB-OPEN-DESIGN-EXTRACTION-MANIFEST.json`
- `WORK-LAB-OPEN-DESIGN-CONFLICTS.md`
- `THIRD-PARTY-LICENSE-DELTA.md`

当前迁移分支读取这三项均为 404，且 `main..migration` 文件清单中不存在它们。现有 Handoff 仅保留 Manifest digest 和统计，未保留可复核的逐文件 Manifest、冲突清单和许可差异原文。因此“远端完整交接证据”不能视为闭环，需要修复文件缺失或纠正文档声明后再复核。

## 13. 当前仍未关闭的关键问题

### P0 安全

当前 `main` 仍保留并在 README 推荐：

- `configure_open_design_windows.py`
- `doctor_open_design_windows.py`

已只读确认配置脚本仍会：

- 读取 `CODEX_HOME/auth.json` 并检查 access token；
- 修改 Codex `config.toml`；
- 修改 Open Design 私有 `app-config.json`；
- 默认把 `D:\All projects` 作为 writable/trusted root；
- 扫描该宽根下的 `.od-skills`。

这说明 `V4-OD-001/002` 尚未完成。迁移分支没有修改这些文件，因此同样继承该风险。当前禁止运行这两个脚本。

### P0 证据与发布

- 迁移 Manifest/冲突/许可差异文件远端缺失；
- V3 结构/合成验证不能冒充 live runtime；
- 尚无 Open Design 官方注册、真实 task/run ID、Artifact/Provenance 读回与恢复证据；
- 尚无当前 exact-SHA 的完整 V3 Windows/Linux CI；
- 尚无独立 frozen-tree GO、正式 release 或商业验收；
- `capability-status.json` 定义了等级和规则，但不是 per-capability 真实状态账本。

### P0/P1 许可与体量

- 根级许可尚未决定；
- 三项迁移内容因许可被阻断；
- 2026-08-05 审计记录：工作树约 68.75 MiB、GitHub 仓库约 310 MiB、六个 GIF 约 61 MiB；`V4-OD-007` 瘦身目标尚未证实完成；
- 默认 Domain Pack 目标应小于 5 MiB，主线不新增大于 1 MiB 的二进制，GIF/视频/高分辨率示例应转 LFS/Release。

### P1 审美与评测

- 497 条大师记录中 420 条未验证；77 张方法卡和 47 条风格谱系均未达到权威状态；
- 迁移分支的 12 个 Benchmark 均要求人工标定；当前 Evidence Cards 为 `not-run`，`authoritative_accepts=0`；
- 自动评分只能筛选和校验，不能代替用户审美标定；
- 真实失败回归集必须覆盖：AI 味、廉价感、没感觉、层级差、字体/留白差、透视错误、材质/灯光假、人物/食物假、过锐、品牌系统不一致和小游戏 UI 失真。

## 14. 当前正确后续顺序

以下是未授权写入前的任务顺序，不代表已经执行：

1. 重新读取当前 `main`、迁移分支和现场本地树，建立一次继承矩阵；
2. 修复迁移 Handoff 的三项缺失证据，或明确撤销不实的“文件存在”声明；
3. 完成 `V4-OD-001/002`：移除凭据读取、私有配置写入和宽根权限，并同步修正文档；
4. 完成真实 per-capability evidence index；
5. 建立包含 V2/V2.1/V3、官方 plugin validation、Windows/Linux 和安全检查的 canonical CI；
6. 收缩到三个公开入口，隔离 `research-only / curated-draft / runtime-eligible`；
7. 完成仓库/安装包瘦身和根级许可决定；
8. 以一个最小真实黄金场景取得 E3：Brief → `commercial-design-core` → DESIGN.md → HTML → visual-quality report → production handoff；
9. 完成真实失败案例回归、人类成对比较与评审校准；
10. 再按 V3 90 张任务卡补净缺口，不重复已经真实验证且 subject/tree/policy/profile/workflow/gate/environment 均一致的工作；
11. Frozen exact tree 独立只读复审后停在 `READY_FOR_USER_APPROVAL`；commit、push、PR、merge、ruleset、release 继续分别授权。

## 15. 执行安全边界

- Windows 原生优先；
- 同一 checkout 同时只有一个 writer；
- 默认 plan/dry-run/staging；
- 禁止访问或修改 `E:\`；
- 禁止读取凭据、OAuth、API Key、Cookie、SSH 私钥、token 和认证数据库；
- 禁止默认写用户 Home、Codex Home、Open Design 安装/数据目录或整个 `D:\All projects`；
- 禁止未授权 commit、push、PR、merge、ruleset、tag 或 release；
- required gate 未运行、被 mock、skip 或硬编码时只能是 `UNVERIFIED/BLOCKED`；
- 所有第三方内容先做来源、许可、安全和运行隔离审查；
- 所有缓存、日志、测试、备份和评审输出进入项目 Git-ignored `.hermes/`。

## 16. 本对话已拉取的原始资料

当前工作区已包含：

- `OPEN-DESIGN-Assistance-V2-Global-Absorption-Pack.zip`
- `OPEN-DESIGN-Assistance-V2.1-Visual-Quality-Pack.zip`
- `OPEN-DESIGN-Assistance-Complete-TaskPack-v3.0.zip`
- V3 完整展开目录（233 个文件，含 199 文件 Overlay）
- V3 90 张完整任务卡与 Task Matrix
- V4 双仓包中的 Open Design 执行包、跨仓包、运行手册和 Manifest
- WORK-LAB 2026-08-07 唯一权威总包及最终切割原文
- 当前 GitHub `main`、迁移分支、Handoff 和分支差异的只读核对结果

原始资料不因进入本对话而自动获得更高证据等级。后续所有 OPEN DESIGN 工作均以本文件为上下文入口，以执行时仓库事实为最终依据；不再把旧包分别当作多个活动任务入口。
