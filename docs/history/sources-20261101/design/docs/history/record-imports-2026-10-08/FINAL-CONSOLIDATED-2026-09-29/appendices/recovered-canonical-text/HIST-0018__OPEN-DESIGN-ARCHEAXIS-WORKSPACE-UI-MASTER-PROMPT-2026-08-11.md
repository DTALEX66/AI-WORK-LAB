# OPEN-DESIGN 执行提示词：ArcheAxis Workspace / 元枢工作台前端设计

将下面内容原样作为 Open Design 的主设计 Brief。它只授权设计与可编辑交付，不授权修改 Cognitive-Loop-OS、WORK-LAB 或全局配置。

---

你是 OPEN-DESIGN-Assistance 的专业 UI/UX 设计执行系统。请基于当前 Open Design UI/UX domain pack、visual-quality-core、anti-AI-slop、design-direction-jury、typography-composition-director、color-material-light-director、micro-detail-finisher、commercial-preflight 和 production-handoff，为下面产品完成一套可开发、可验证、可编辑的桌面端前端设计。

## 一、产品事实

产品名：**ArcheAxis Workspace / 元枢工作台**。

固定定位：**本地优先、证据驱动的 Human–AI 学习与知识工作台。**

固定短句：**同一份可信知识，人学得更深，AI 用得更准。**

旧名 `Cognitive-Loop-OS` 仅是 Git/历史兼容技术 ID，不得作为默认 UI 品牌。产品不是通用 Agent、聊天软件、模型网关或企业知识 SaaS。

核心闭环：

`Source / Evidence → Candidate → Governed Knowledge → Human Learning / AI Use → Trace / Evaluation → Candidate Lesson → Human Approval`

未经人工治理的 Candidate 不得显示为 verified truth；未实现能力不得显示为 AVAILABLE、LIVE、精确进度或成功。

当前真实阶段：Obsidian-compatible Workspace 纵切；Vault 读取优先，编辑/双向兼容必须按真实能力状态显示。设计未来完整产品，但页面必须使用 `AVAILABLE / PARTIAL / PLANNED / BLOCKED / UNKNOWN` 显式区分能力成熟度。

## 二、固定信息架构

一级空间只能是以下六项，不得增加诗性别名替代：

1. **Workspace**：首页、导入、当前工作、任务与最近活动。
2. **Library**：Source、文件、网页、PDF、音视频、Vault、知识候选。
3. **Evidence**：Claim–Evidence、冲突、来源、质量、人工复核队列。
4. **Learning**：学习路线、练习、复习、掌握度、Teach Back、知识宫殿/画布。
5. **AI Assets**：已批准的机器知识、Context Pack、Rules、Skills、Memory candidates；Agent 只是消费者。
6. **Settings**：本地存储、隐私、Adapter、备份、诊断、能力状态。

二级页面至少覆盖：

- Workspace Overview
- Universal Intake
- Library Browser / Vault Workbench
- Document Reader + Evidence Side Panel
- Claim–Evidence Review Queue
- Knowledge Canvas
- Learning Route + Review Session
- Memory Palace / spatial learning view
- AI Assets / Context Pack Inspector
- Task & Delivery Receipts
- Settings / Privacy / Backup
- Diagnostics / Capability Matrix

## 三、设计方向

项目明确采用“克制的 Apple 液态玻璃 + 专业研究工作台”作为项目风格，但不得照抄 Apple 产品或形成通用 Open Design 默认风格。

先生成三套结构明显不同的方向：

- A：Calm Research — 浅色、高留白、半透明层级、纸张与玻璃结合。
- B：Deep Knowledge — 深色、低眩光、沉浸阅读、证据链强调。
- C：Adaptive Dual — 同一 Token 系统下完整 Light/Dark，自适应 Full/Compact。

使用 design-direction-jury 按产品匹配、信息效率、可访问性、实现风险、抗 AI 味、跨页面一致性评分；选择一套主方向，同时保留另外两套方向的差异说明，不把三套混成折中拼盘。

## 四、视觉约束

- 气质：安静、可信、精密、长期使用不疲劳；避免游戏 HUD、赛博朋克、黑金奢侈风、科技蓝模板、霓虹光污染。
- 液态玻璃只用于导航、Inspector、浮层和局部上下文，不给所有卡片叠加 blur。
- 内容层优先实体表面和清晰边界；信息密度可调，不靠大量悬浮卡片堆砌。
- 不使用无意义渐变球、AI 星光、发光脑、人形机器人、随机网格、虚假 3D 图标。
- 图标使用统一 SVG 线性/面性系统，不用 Unicode 符号代替正式图标。
- 中文是主语言，英文用于模块名和专业字段；中文排版必须真实、克制、可读。
- 状态色必须同时有文字和图形，不只依赖颜色。
- 数值缺失时显示 `— / UNKNOWN / 尚未采集`，绝不显示 0 或伪百分比。

## 五、桌面壳布局

目标平台：Windows 本地 Tauri 桌面端 + Web，同一前端设计系统。

推荐骨架：

- 顶部：品牌、当前 Workspace、全局搜索/命令、连接与本地状态。
- 左侧：六个一级空间；二级导航按当前空间展开。
- 中央：主要任务区域，优先支持阅读、对比、治理和学习。
- 右侧：可折叠 Context & Evidence Inspector，显示来源、Claim、质量、冲突、版本和操作边界。
- 底部：仅在有真实任务时出现的 Activity/Receipt Dock；无任务时折叠。

必须设计：Dark/Light × Full/Compact 四种状态；1440×900、1280×800、1920×1080；窄窗口不得简单压缩桌面布局，需要重排。提供 390px 响应式参考，但桌面端为主。

## 六、核心页面细节

### Workspace Overview

先回答“我现在有什么资料、有什么待复核、接下来学什么、AI 能使用什么”。不要做企业 BI 大盘。仅显示真实数据和明确下一步。

### Universal Intake

拖放/选择本地文件、URL、GitHub、Vault；显示格式识别、转译引擎、处理阶段、失败原因、重试边界。明确区分“识别转译质量”和“内容事实验证”，两者绝不能合并为一个准确率。

### Document Reader + Evidence Inspector

左侧文档结构，中间原文/转译对照，右侧 Claim–Evidence；支持来源定位、OCR/ASR 置信、公共事实核验、冲突、人工决定。识别置信度不能代表事实正确性。

### Evidence Review

队列按风险、证据缺口、冲突、来源质量筛选；每项提供原文定位、支持/反对证据、不可查证标记和人工决定。默认记录差异，不自动覆盖。

### Learning

把 Knowledge Unit 转为学习路线、练习、复习、Teach Back 与迁移任务；提供时间线、掌握度证据和复习建议。不要用虚假游戏化积分替代学习证据。

### AI Assets

只展示已批准或候选状态明确的 Context Pack、Rules、Skills、Memory candidate。显示来源、版本、TTL、污染/隔离、适用范围和回滚；不得把聊天会话正文当作可同步资产。

## 七、组件与 Token 交付

输出：

1. Product UI brief 与假设清单。
2. 三套方向板及 jury 评分。
3. 选定方向的 Light/Dark Token：颜色、字体、字号、间距、圆角、边框、阴影、玻璃、层级、动效、状态色。
4. 导航、Command、Card、Table、Tree、Reader、Evidence Item、Status Badge、Timeline、Canvas Node、Inspector、Dock、Dialog、Toast、Empty/Error/Loading/Skeleton 组件规范。
5. 上述核心页面的高保真桌面设计；Full/Compact 与关键窄窗口状态。
6. 交互状态：hover/focus/pressed/selected/disabled/loading/partial/stale/offline/conflict/error。
7. 可访问性报告：WCAG 2.2 AA、键盘路径、焦点、对比度、reduced motion、200% zoom。
8. 可编辑交付：Open Design 原生工程 + design tokens JSON + component manifest + SVG 图标 + 页面导出图 + HTML/CSS 原型或 Figma/Penpot handoff。
9. provenance、字体/图标/素材版权状态、商业 preflight。
10. 开发 handoff：组件映射、响应式规则、数据状态合同、不得伪造的数据清单。

## 八、质量门禁

使用 OPEN-DESIGN 的 visual-quality-core 和 anti-AI-slop 对所有页面逐项审查：

- 信息层级清晰，不靠装饰制造重点。
- 同一字段和状态在所有页面语义一致。
- 数据密集但不拥挤；长时间阅读不疲劳。
- 中文排版、表格、树、证据链、空状态达到产品级精度。
- 玻璃、阴影、渐变、圆角均有功能理由。
- 不出现模板化 AI Dashboard、虚假统计、伪进度或无来源示例数据。
- 实现成本与 Tauri/Web 技术栈匹配。

凡无法从仓库或 Brief 确认的事实，标记 `ASSUMPTION` 或 `UNKNOWN`，不得自行补成产品事实。

## 九、执行边界

本轮仅设计与输出可编辑交付物。不得修改 Cognitive-Loop-OS、WORK-LAB、全局配置或 Open Design runtime；不得 commit、push、PR、merge、release。需要写入仓库、应用主题、安装插件或调用付费 API 时，输出 ActionPlan 并标记 `WAITING_APPROVAL`。

---

