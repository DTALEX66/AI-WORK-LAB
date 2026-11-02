# GPT CODEX UI 开发任务包｜DESIGN-LAB

你负责 **DESIGN-LAB** 正式 UI/前端设计开发。目标是把仓库做成 AI-native、platform-neutral 的专业设计智能与生产实验室，而不是普通作品集网站、通用 AI 聊天界面或简单素材库。

## 0. 先审计仓库

读取真实仓库并生成 `UI_IMPLEMENTATION_AUDIT.md`：
- 技术栈、路由、组件、数据层、设计工具适配层、Adobe/Figma/3D/视频等集成现状。
- Research / Evidence / Preflight / Delivery 已有哪些真实后端能力。
- 当前 UI 与参考包的差距。

不破坏现有设计执行链，不为了 UI 重写 Tool Adapter/API。存在真实数据协议时必须适配它。无前端基座时才参考 B08 React/TS。

## 1. 包内资料读取顺序

1. `10_B10_最终版高保真可部署UI/design-lab_最终版_高保真可部署UI.zip`
2. `09_B09_交互式真实Demo/design-lab_L9_交互式真实Demo.zip`
3. `08_B08_ReactTypeScript可运行原型/design-lab_L8_React_TypeScript_可运行原型.zip`
4. `07_B07_前端开发规范/DESIGN-LAB_L7_前端开发规范工程包.zip`
5. `06_B06_交互状态系统/DESIGN-LAB_L6_18张交互状态+Tokens.zip`
6. `05_B05_高保真产品页面/DESIGN-LAB_L5_12张高保真产品页面.zip`
7. `04_B04_组件系统与DesignTokens/DESIGN-LAB_L4_组件系统_16张+Tokens.zip`
8. `03_B03_页面级UI与AAOS配色纠正_L3/DESIGN-LAB_10张页面级UI_统一体系.zip`
9. `02_B02_深度细节_L2/DESIGN-LAB_L2_VI+UI_36张细节图.zip`
10. `01_B01_基础视觉拆图_L1/DESIGN-LAB_VI+UI_24张全套.zip`
11. `01_B01_基础视觉拆图_L1/DESIGN-LAB_VI_12张独立图.zip`
12. `01_B01_基础视觉拆图_L1/DESIGN-LAB_UI_12张独立图.zip`

B10 是最终视觉权威；B01/B02 主要用于 VI、Logo 黄金比例/Fibonacci 构造、图形语言和细节参考。

## 2. 产品定义

DESIGN-LAB 是 **设计智能 + 专业工具适配 + 生产/质检/交付** 的工作平台。

核心不是“AI 帮我画一张图”，而是完整能力链：
`Research/Evidence → Brief/Project → Domain Methods → Tools/Generation/Edit → Visual QA/Preflight → Version/Review → Deliverables/Handoff`

领域覆盖：Branding / Graphic / UI/UX / E-commerce / Spatial / 3D / Motion / Video / Audio / Research / Production / Handoff。

## 3. 最终视觉约束

- 背景黑/深灰 `#060A14` 左右。
- Surface `#0D1221/#11182A`。
- 主色 Electric Blue `#316CFF`。
- Secondary 蓝 `#4BAFFF`。
- 文本白/冷灰。
- 紫色只允许出现在“创意内容/素材本身”或非常有限的视觉能量中，**不能成为系统主色**。
- Logo/品牌几何可借鉴黄金比例/Fibonacci/Bezier/Grid/Frame，但不要在每个页面展示构造线。
- 光效体现“设计焦点、画布、框选、Bezier、生产能量”，不要像游戏UI。

## 4. 正式信息架构

至少：
1. Dashboard
2. Projects
3. Project Detail
4. Research
5. Brand Systems
6. Design Domains
7. Creative Tools / Tool Adapters
8. Preflight / QA
9. Deliverables / Handoff
10. Evidence
11. Collaboration
12. Settings

## 5. 页面重点

### Dashboard
- 正在进行项目
- 待审核
- Visual Quality
- 最近项目
- Domains
- Tool status
- Delivery status

### Project Detail
必须成为真正工作台，而不是卡片列表：
- Brief / constraints / references
- assets
- current outputs
- versions
- comments/approval
- QA score
- delivery checklist

### Brand Systems
不是展示品牌海报；要可以管理：
- Logo assets
- color tokens
- typography
- icons
- graphic language
- templates
- exportable assets

### Design Domains
每个领域至少包含：方法/模板/工具/质量规则/案例入口，而不是只做 11 个空卡片。

### Tool Adapters
- 显示安装/连接/能力/权限/版本/路径。
- 遵守真实项目既有 Adapter。
- 如果某工具支持操作 PS/Adobe/Figma，要明确“连接方式/权限/当前状态/可执行能力”，不要只写 Connected。

### Preflight / QA ——核心差异化页面
必须真实、有层级：
- Asset：分辨率、缺图、链接、色彩模式。
- Typography：缺字体、许可、嵌入。
- Layout：出血、安全区、尺寸、像素密度。
- Brand：Logo、色彩、间距、规则。
- Copyright/Compliance：来源/授权/AI生成记录。
- Export：命名、格式、尺寸、可编辑性。
- 结果分为 Pass / Warning / Error，并可定位到具体文件/画板/图层。

### Deliverables
- Editable source
- Preview
- Exports
- Package manifest
- version
- handoff checklist
- share/download

## 6. 组件和交互

通用组件继承 B04/B06。
DESIGN-LAB 专属：
- AssetGrid
- ProjectCard
- DomainBadge
- ToolAdapterCard
- QualityScore
- PreflightIssue
- Layer/Artboard locator
- VersionPreview
- DeliverableManifest
- EvidenceRecord
- ApprovalThread

动效：
- Electric Blue 柔和 glow。
- Hover 轻微浮起。
- Preflight 扫描可有细线 sweep，但扫描结果来自真实检查流程/Mock Adapter，而非纯动画。
- 页面切换不要过度做大幅转场。
- `prefers-reduced-motion`。

## 7. 工程与工具适配

- 首先复用当前项目已有工具适配架构。
- UI 只消费标准化 Tool Capability Model：`installed / connected / version / path / permissions / capabilities / health`。
- 不在组件内部直接 shell 调用外部软件。
- Preflight / Tool action / Export 使用 service/action layer。
- 长任务显示 progress + cancel + retry + logs。

## 8. 品牌与 UI 的关系

VI 不是另一个独立网页。需要把 VI 落到产品：
- Logo → App Shell / icon / loading mark。
- Grid/Frame/Bezier → subtle layout language。
- Electric Blue → action/focus/selection。
- 黄金比例/螺旋 → Logo 构造和少量品牌视觉，不要作为每页背景纹理。

## 9. 响应式、性能、可访问性

- Desktop 优先，专业设计软件允许高密度，但不能小于可读范围。
- Tablet：Inspector/Sidebar 可折叠。
- Mobile：主要用于 review/approval/status，不强行移植复杂设计工作台。
- 大 Asset Grid 虚拟化。
- 图片 thumbnail lazy load。
- 44px hit target；键盘 focus；对比度达标。

## 10. 验收

必须输出：
- `UI_IMPLEMENTATION_REPORT.md`
- `DESIGNLAB_VISUAL_QA.md`
- `TOOL_ADAPTER_UI_MATRIX.md`
- `PREFLIGHT_UI_COVERAGE.md`

测试：
- Build/typecheck/lint。
- 主要路由 smoke。
- Preflight 状态和定位逻辑测试。
- Tool Adapter 状态转换测试。
- 不得只交静态 demo。

视觉 QA：
- 不得出现 AAOS 金青宇宙体系。
- 不得把紫色升级成系统主色。
- 不得变成通用 SaaS 卡片站或作品集网站。

## 11. 执行顺序

仓库审计 → Token/AppShell → Projects/Project Detail → Research/Evidence → Brand System/Domain → Tool Adapter → Preflight QA → Deliverables/Collaboration → 状态/响应式 → 测试与视觉 QA。直接实施，普通决策自行完成。
