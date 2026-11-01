# DL-V2 调研报告收敛与后续任务（2026-08-17）

> 输入：外部调研报告（生态盘点/五层架构/协议定义/技术蓝图/V1.0 产品设计）+ 真实仓库现状（26 验证器、V2 九项、E0–E3 证据）。
> 方法：逐条对照（主张 vs 现状 vs 收敛判断），只保留符合项目定位且为真实缺口的任务。

## 一、定位锚点（筛选标准）

- DESIGN-LAB = AI 原生、平台中立的职业视觉设计**能力与生产基础设施**（能力/契约/证据，不是软件产品）
- 不做：绘图工具、Figma/Adobe 复刻、单一生成产品、通用 Agent 运行时、知识图谱通用治理（ArcheAxis 边界）
- 纪律：契约优先、fail-closed、不重命名现有架构、不引入运行时依赖

## 二、收敛矩阵（报告主张 vs 现状）

| 报告主张 | 现状核实 | 收敛判断 |
|---|---|---|
| Design Intent Schema | design-brief.schema.json 已有（objective/audience/deliverables/constraints/must_keep/must_avoid） | ✅ 已覆盖，不重复 |
| Creative Tool Contract | adapter-contract + capability-based DesignCommand + 9 适配器注册表 | ✅ 已覆盖 |
| Design Memory | P1-D（candidate→dedup→validate→active） | ✅ 已覆盖 |
| Design Evaluation | P1-E 分层评分 + hard blockers + 12 rubrics（evals/） | ✅ 已覆盖 |
| Design CI/CD | 26 验证器链 + CI 四门 + evidence binding | ✅ 已覆盖 |
| Evidence Graph | provenance + attestation + CURRENT_EXACT/HISTORICAL_VALID | ✅ 已覆盖 |
| Agent Team（Supervisor+多 Agent） | 边界契约：Agent 调度属 WORK-LAB | ❌ 不做 |
| Tauri/Qdrant/Neo4j/LangGraph 技术栈 | 当前为契约仓库，无运行时 | ❌ 不做 |
| 五层架构 L0–L5 重命名 | 现有 ARCHITECTURE 分层已冻结 | ❌ 不重命名 |
| **Design IR 中间表示** | artifact.schema.json 仅文件级描述（id/kind/path/format），无可编辑文档对象模型 | 🔴 **缺口：新增契约** |
| **生产校验细化**（CMYK/出血/PDF-X/字体嵌入） | preflight.schema.json 结构薄（required_checks 未定义）；domain packs preflight.json 有部分清单 | 🔴 **缺口：契约增强** |
| **经验语料库（Experience Corpus）** | knowledge/ 为静态资料吸收；memory 为规则级；无项目级原始语料（源文件+决策+版本+评审） | 🔴 **缺口：新增契约** |
| **Design Action Language** | DesignCommand 为 capability 层（image.layer.mask）；无原子动作词汇表（move/align/set-font） | 🟡 **缺口：动作词汇契约** |
| **质量分层管道**（规则→视觉模型→专家→人类反馈） | evals 12 rubrics + jury 分层思路已存；缺分层管道契约文档 | 🟡 **缺口：管道定义** |
| **开源组件能力地图**（CLIP/SAM/OCR/布局） | 无候选清单归档 | 🟢 **低风险：知识资产** |

## 三、符合定位的后续任务（收敛后）

### P0 契约级（延续 schema 驱动，fail-closed 验证）

| 任务 | 交付 | 验收 |
|---|---|---|
| **T1 Design IR 契约** | design-ir.schema.json：可编辑文档对象模型（画布 + 图层节点：text/image/vector/3d + 样式/变换/约束属性 + 版本化） | schema 有效；正/负 fixture；与 artifact.schema.json 引用关系明确（artifact=文件资产，IR=文档对象） |
| **T2 生产校验契约增强** | preflight.schema.json 定义 required_checks 结构（id/severity/tool/标准 ref）；印刷/数字/视频三个 profile | 已知 blocker 样本（无出血/缺字体/色域错）100% 被预检标记；机器可读报告 |
| **T3 经验语料库契约** | experience-record.schema.json：项目级语料（project refs + directions + variants + critique + decision log + 评审记录 + 源文件 refs） | schema 有效；与 memory-record 引用关系明确（memory=规则级，corpus=项目级原始数据） |

### P1 能力增强（低代码/文档级）

| 任务 | 交付 | 验收 |
|---|---|---|
| **T4 Design Action Language 词汇表** | design-action.schema.json：原子动作动词表（move/align/set-font/export/…）作为 DesignCommand.args 的规范化层 | 与 command 契约兼容；动作不绑定工具名（中立性检查） |
| **T5 质量分层管道定义** | quality/pipeline.md：deterministic→visual model→expert→human feedback 分层契约 + 与 evals rubrics 对齐 | 文档 + 分层可追溯；human calibration 步骤明确（待用户执行） |
| **T6 开源组件候选映射** | research/adapters-roadmap.md：报告能力地图 → 未来 adapter/provider capability 候选（E0 未接入标注） | 只归档不实施；标注证据等级 E0 |

## 四、不做清单（明确排除）

- Agent Team 多 Agent 运行时、Tauri/Qdrant/Neo4j/LangGraph 技术栈、五层架构重命名（边界冲突）
- 新领域包批量铺开（packaging/spatial/3D/motion…需要时逐域按十要素补）
- 人工 Jury / E4 发布链（需用户参与，非代码任务）

## 五、执行顺序建议

T1 → T2 → T3（P0 契约三连，可并行设计、串行提交）→ T4/T5/T6（P1 增强）。
每项独立提交 + fail-closed 验证；执行前无需新增运行时/依赖。
