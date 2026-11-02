# UI 套件包拆解与可复用性判断

## 证据与边界

本次已在 Library 找到并展开两份项目级总包，逐个检查内层压缩包目录、README、token、B07 规范、B08 原型、B09 Demo、B10 `index.html` 及 L5 页面总览。检查的是资料包字节，不是 WORK-LAB/DESIGN-LAB 当前仓库；因此没有推断当前仓库缺哪些组件、当前分支或任何构建状态。

项目蓝图：`02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx`、`03_DESIGN-LAB_完整项目描述与未来蓝图_20261006.docx`。两者均写明整理稿不替代仓库 Authority；10/6 中的分支/CI/实现状态也不是今天实时核验结果。

精确 2026-10-06 23:40 Asia/Shanghai 原聊天未找到。更近的主题来源是 10/6 项目蓝图；8/31 三项目审计属于历史依据，不能作为今日代码状态。

## 两份总包的内容和作用

| 批次 | 内容 | 推荐用途 | 不能推出 |
|---|---|---|---|
| B01 | VI、Logo、主视觉、图形语言、基础页面拆图，各项目约 24 张 | 品牌资产/早期概念/图标与构图参考 | 不能独立决定当前 IA、组件 API 或真实仓库状态 |
| B02 | VI/UI 深度拆图，各项目 36 张，含图标、导航、局部、Logo 细节 | 精确查看原始视觉并挑选可迁移源图 | 不能直接用截图替代可访问组件或原始矢量 |
| B03 | 10 张页面级 UI | 对照页面结构、层级与布局关系 | Worklab/DL 的页面不得套 AAOS 配色修正；跨项目只共享规则 |
| B04 | 16 张组件系统图 + `design_tokens.json` | 组件目录、状态、排版、间距、颜色 role 参考 | 不是已安装的代码组件库，也未证实和当前 React/Tauri/CSS 版本兼容 |
| B05 | 12 张 1920×1080 高保真产品页 | 页面布局参考与路由覆盖基线；包内带页面总览图 | 截图中的指标、项目、状态均为演示数据，不是 API 合同 |
| B06 | 18 张交互状态：Hover、Focus、Modal、Drawer、Empty、Loading、Error、Permission、Approval、Responsive 等 | 状态矩阵和验收清单 | 不能仅凭静态画面判断键盘/读屏/焦点陷阱已实现 |
| B07 | 主题 tokens、路由树、导航、状态机、权限矩阵、AppShell 示例、验收项 | 对接工程的初始规格输入，逐条对照最新 Authority | 不是当前仓库既有路由或真实后端合同；逐条重新映射 |
| B08 | React + TypeScript + Vite 原型，含 demo `packages/ui-core` | 查找可借鉴的布局/数据模型/交互样例 | `@three/ui-core` 是演示包：private 0.1、没有发布治理；不要跨仓复制成公共依赖 |
| B09 | 一个 HTML 交互演示，localStorage 状态 | 快速体验导航、弹窗、筛选/表格等交互概念 | 它不是生产数据层；演示操作成功不代表 Control/Host 真写入 |
| B10 | 单 HTML/CSS/JS 高保真静态前端，带 hover、modal、drawer、command palette 等演示 | 主视觉、密度、表面、品牌氛围的最高视觉参考；可拆其纯视觉资产 | 无 API 接入；部分页面为 generic fallback；localStorage 不能作为任务/项目领域真值 |

资料包目录都把 B10 标作最高视觉权重，并按 B10>B09>B08>B07>B06>B05>B04>B03>B02>B01 处理“图稿冲突”。此序列是**设计资料的引用权重**，不是开发实施顺序，也不是领域 Authority 优先级。

## WORK-LAB：适用性与拆解

### 有参考价值

- 视觉是深海军蓝/深黑底，Electric Blue `#2A91FF` 与 Cyan `#20CDE1` 做有限强调；B07 的基色为背景 `#050D16`、surface `#081420/#0C1B2A`、文本 `#EEF6FC`。这一方向和 10/6 蓝图的执行治理层身份相容。
- L5/B10 给出 11 个导航区：总览、工作流、工作流编辑器、任务包、观察者、规则与策略、集成/MCP、记忆管理、审计追踪、审批中心、设置。工作流图、执行时间线、审批上下文、审计回执、观察者只读视图有可复用的结构参考。
- UI 适合数据密度高的控制台；细边框、蓝色活动状态和小面积发光可保留。柔和蓝色流线/网格可以用于背景纹理，不要让动效压过运行状态阅读。

### 必须按 10/6 产品边界纠正

- 10/6 定义 WORK-LAB 为客户端中立的工作流治理、控制与交付系统，不是通用聊天、IDE 或 Agent runtime。首页应该围绕用户目标/项目/Work Unit/任务计划、当前阻塞和可信状态，不能只展示虚构 KPI。
- Control 与 Observer 是同一产品中的两种权限面。Observer 对运行快照、事件、成本/用量、回执、历史只读；不得 Approve/Reject、Retry、Cancel、Rollback、Install 或写配置。写动作必须接既有 Permission Gate、Task Protocol、Completion Authority/Config Control Plane，后端未就绪时禁用并显示原因。
- 把 `记忆管理` 收窄成允许携带的工作流上下文、handoff/恢复提示、已批准经验的引用；不构造第二套 AAOS 知识库，不采集客户端私人会话。
- 原型里流图拖动/保存、审批/设置等 localStorage 操作都属于体验样例；真正配置必须执行 discover→ownership→diff→授权→apply→原生 readback→恢复/回滚。
- 全局入口应表达“目标→项目 Authority/上下文→PlanningCandidate→显式验证和权限→原生执行器→Receipt/测试/读回→Completion”。候选方案不能直接获得主分支写权。
- 把缺失数据显示为 UNKNOWN/STALE/PARTIAL/ERROR，而不是 0、Healthy 或空白。按实际数据新鲜度、来源、观察时间与理由渲染；动态价格、模型、费用、运行状态均不得前端造数。

### 视觉资产

优先检查 WORK-LAB 自己 B01/B02 的 Logo、W 节点/路由线、品牌图形、图标、暗纹；可重新裁剪成应用小标、导航 icon、状态图和空态插画。B10 发光网格只做弱背景，不迁移 AAOS 星环、宇宙主图或 DESIGN-LAB 客户作品。

## DESIGN-LAB：适用性与拆解

### 有参考价值

- 黑/深灰加冷白文本、Electric Blue `#316CFF`、Secondary `#4BAFFF`，表面 `#0D1221/#11182A`。这是 DL 的独立品牌方向。紫色只能属于具体创意素材或极小范围视觉提示，不作为系统主色。
- L5/B10 有项目、研究、品牌系统、设计领域、创作工具、预检 QA、交付、证据、协作、设置等路线；项目详情、研究参考、预检阻断、交付清单值得做信息层级参考。
- 画布、版式网格、选区、曲线和局部焦点可以形成 DESIGN-LAB 的识别元素，但不要把它做成游戏仪表盘，也不要用炫光代替可编辑作品。

### 必须按 10/6 产品边界补齐

- DESIGN-LAB 是职业视觉设计智能与生产系统，必须有自己的 Workbench（standalone-first + host-native editing）。不做第二个 Photoshop/Figma/Blender 画布、通用聊天、模型网关或执行 OS。
- 核心旅程为 Brief → Rights/约束 → ReferenceSet/ResearchFinding → MethodCard/Visual DNA/方向 → DesignSystem/Design IR/ToolActionPlan → 合格 Host 真实执行 → Native Readback → Critique/Human Jury → Rights/Preflight → 可编辑 Handoff/BOM/回执/恢复。
- 页面应围绕项目当前设计任务与可修改成果，不能让静态模块清单/11 张空领域卡片成为产品本体。项目信息、参考素材、方向锁定、可编辑对象/版本、质量问题定位、源文件与交付状态之间必须保持同一项目上下文。
- 新增主线 Design Capability Library 是“设计能力”库，不是插件链接目录：来源/作者/版本/许可/热度与采样时间→去重分类→方法提炼→中立能力合同→宿主投影和损失说明→真实任务资格→反馈/撤回。高星/收藏只当发现信号，不等于审美质量、可商用或已兼容。
- 多维分类轴至少包括专业域、产物类型、审美家族、视觉构成、工作阶段、实现形式、Host、成熟度和权利/部署范围。沿用现有 Source Registry / Method / Domain / Schema，不另起十个服务或影子数据库。
- 人类对方向、审美和最终交付的判断不能被自动分数替代；质量/权益/preflight 绑定具体 artifact/version，旧版本 PASS 不继承。

### 视觉资产

先复用 DESIGN-LAB 自己的 Logo/图标/色彩/网格/Bezier/字体与 VI 拆图。B05 contact sheet 里可见的若干波形/圆环缩略内容过于通用，不能当成已批准的品牌作品或客户素材。主图应是有来源、授权、可编辑文件和真实项目语境的设计结果；来源不明就做占位并清晰标为样例。

## 开源 UI 组件与原型风险

- 旧 UI 提示词说 `@shadcn/ui` 可以直接当稳定 npm UI 库安装，这是不准确的使用方式。官方描述是组件/代码分发模式；应采用 CLI/registry 复制需要的源码，并在项目内审阅、定制和维护，不能照搬那条 `pnpm add @shadcn/ui`。
- B08 虽然 WORK-LAB 与 DESIGN-LAB 都带同名 `@three/ui-core`，但属于两个独立 ZIP 的私有 demo 包，并不构成真正的共享库版本/测试/发布治理。不要直接把此包拷入两个产品。
- B09/B10 体验主要靠浏览器 localStorage，产品级状态、审计、文件编辑、权限、事件、回执都尚需接真实服务/Host contract。
- 总包是丰富的**设计素材池**，不是开源组件库本体；许可证只按上游项目与具体版本审查，不能由 PNG/项目归档包的存在推出可二次商用权利。

## 原始资料指纹

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| WORK-LAB_UI开发资料总包_按批次.zip | 37,048,117 B（Library 元数据） | `c94ff634dad3fa47cd843493c5f3b59c946fd987295085b8c821febba13eef48` |
| DESIGN-LAB_UI开发资料总包_按批次.zip | 44,241,260 B（Library 元数据） | `b57108c2ba44bfb5d43f5c540c89feaa766c4a5ba60228e62d7b6ec73484869e` |

内容总长度和 Library 字节大小会因 ZIP 外层目录/归档封装略有差别。下载后以 SHA-256 对照确认文件身份。

## 视觉总览

![WORK-LAB L5 页面总览](visual_refs/WORK-LAB_L5_12页面总览.jpg)

![DESIGN-LAB L5 页面总览](visual_refs/DESIGN-LAB_L5_12页面总览.jpg)
