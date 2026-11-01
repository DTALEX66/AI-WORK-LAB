# DESIGN-LAB｜商业级个人工作台调研与产品优化

日期：2026-09-28。性质：基于当前云端代码的研究与执行建议，不是产品验收报告，不替代仓库顶层Authority，不创建第二任务账本。主执行器、Agent及模型由Owner选择。

## 1. 决策摘要

保留 apps/workbench 的 TypeScript/Vite 和 Python业务后端；以现有DESIGN-LAB视觉Token为品牌基础，引入一个主组件体系，补齐真正的设计生产与交付。优先验证 Adobe Spectrum Web Components；Web Awesome Core为同路线备选。React + shadcn/ui作为有ADR依据的迁移备选，不能因为组件热门就换栈。

商业级个人使用的目标是：界面精致、一致、可预测，真实项目可恢复，产物可编辑，错误可定位，日常动作少。不是建设团队账号、计费、多人在线、通用Agent平台或第二设计画布。

先交付两条黄金链：GOLDEN-001 DESIGN-LAB设计自身工作台；GOLDEN-002 一份实际海报/展架/品牌物料完成原生可编辑交付。UI/UX、包装、空间、3D、动效、视频、游戏视觉都保留在能力版图，按真实案例逐步扩展。

## 2. 云端核验事实与限制

- 仓库 DTALEX66/DESIGN-LAB；观察 main exact SHA：d116b14995fcdbba1b165ec5bc3124f5daed3d15。
- Open PR集合实读为空；Canonical Verify #407，run 36336694172，head绑定上述SHA，completed/success。
- 本次API查到两个未过期artifact：workbench-e2-d116b149…、secret-history-report；只读元数据，没有下载校验，不能写artifact回读通过。
- 分支保护端点返回403（集成无该管理读取权限）。不能将AUTHORITY里的历史“9个required checks”冒充今天实读结果。
- 用户Windows本地dirty/untracked、未推送代码、Adobe版本和实机结果，本次不可见。云端结论不覆盖这些状态。
- 本次是权威文档、关键源码、API、账本、CI的定向审查，未运行项目、未做全仓逐行安全审计或逐页视觉验收。

### 2.1 已有能力应继承

读取的顶层Authority明确：strict TS、pnpm、Vite、浏览器E2E与首条Project→Brief→Reference→Direction→DesignSystem链已关闭并保留回归守卫。源码存在真实项目、Brief和Direction修订/选择、DesignSystem目录与绑定、原生任务/导出/验证路由。不能重新当成全部TODO。

但“DesignSystem可选择绑定”不等于“Token任意编辑、版本化、重启读回”全部完成。design_layer.py当前方法包括design_systems、bind_design_system；本次检查范围未见完整Token CRUD接口，应继续查现有实现后补缺口。

### 2.2 具体缺口与风险

|观察|依据|任务含义|
|---|---|---|
|已有12路由壳和B07/B10视觉对齐代码|shell.ts|保留路由语义，逐页完成业务，而非重建AppShell|
|research、design-domains、collaboration明确未开放|VIEW_NOT_OPEN|研究/领域按需要补真实对象；个人版暂缓协作|
|主流程和旧单页工作台共存|main.ts、shell.ts、index.html|将操作逐步迁入项目上下文，保留兼容入口直至测试切换|
|深色主题已有品牌值|style.css|背景#060A14、面板#0D1221、主色#316CFF；不得套库默认紫色或Adobe品牌替换|
|资源路由仅固定HTML、main.js、style.css|workbench.py|组件CSS、图标、字体、chunk不能假设自动被服务和wheel打包|
|CSP限制self样式/脚本、data图像|workbench.py|第三方运行时样式、blob预览、外部CDN需要实测与最小化适配|
|构建兼容classic-script VM测试且不压缩|vite.config.ts|引入组件可能影响单文件/全局测试契约，不能删除旧测试逃避|
|28个R5任务四轴均PARTIAL、复审待定|ledger解析|这是证据复审状态，不代表28项都未实现，也不能虚算百分比|
|部分Adapter仅E0/E1，ComfyUI记录历史E3|adapter-registry.json|工具名称或旧证据不等于当前SHA可用；按实机重新资格化|
|Evidence下层文档与顶层E4/E5措辞存在差异|EVIDENCE_POLICY vs AUTHORITY|以顶层定义执行，做小范围语义对齐，不重建治理体系|

资源路径是可核实代码事实；是否导致实际组件故障尚需兼容试验，不将风险直接判定成已发生缺陷。仓库注册表中“未安装”仅是记录，不等于今天用户电脑实际未安装。

## 3. UI组件候选与裁决

来源编号见04_SOURCES.md。以下优先级是对本项目技术约束、创意工作台场景、维护与预算的判断，不是通用排行榜。

|候选|适用技术|价值|本项目裁决|许可/边界|
|---|---|---|---|---|
|Spectrum Web Components|Web Components / Lit|创意软件式控件、主题/尺度、菜单、对话框、表单；官方AI技能|首选兼容验证；选稳定一代，禁止混抄Gen1/Gen2 API|上游Apache-2.0；保留通知[S01–04]|
|Web Awesome Core|标准Web Components|框架中立、通用交互、主题化；接现有TS方便|备选；若Spectrum生产包兼容代价过高则切换|Core MIT；Pro组件/模板不默认免费[S05–06]|
|Fluent UI Web Components|Web Components|Windows语义、控件与主题|候选第三位；逐组件核对成熟度与需求覆盖|MIT；React版和Web版覆盖不可混同[S07]|
|shadcn/ui|主要为React组件源码生态|品牌定制和AI检索/registry支持好|若迁移获ADR采用，作为React路线首选；本轮不直接引入|主仓MIT；第三方registry单独核验[S08–09]|
|Radix Primitives|React无样式|焦点、弹窗、菜单等行为基础|React方案中的底层选项；不与另一套基础行为重复叠加|具体锁定包核验；官方无样式行为说明[S10]|
|Base UI|React无样式|可组合、可访问、视觉自由|React路线另一底层选项，不支持当Vanilla库使用|MIT；官方明确React限定[S11]|
|React Aria / Spectrum|React|可访问性、集合/交互与Adobe设计体系|React ADR备选；不是Spectrum Web Components同一包|锁定包逐项核验[S12]|
|Mantine|React|丰富表单/布局和hooks，集成速度快|快速构建备选，但仍需迁移与品牌覆盖|@mantine包MIT[S13]|
|Ant Design|React|表格/表单/复杂管理界面成熟|更适合数据后台；不作为创意工作台默认视觉|主仓MIT；模板另核验[S14]|
|MUI / MUI X|React|系统性组件和复杂数据控件|不为少量表单引入整套；付费数据能力非本期必需|Community与Pro/Premium分开[S15]|
|Vaadin组件|Web Components|数据密集表格/表单|仅有明确复杂表格缺口时评估，不迁Java后端|核心Apache-2.0；部分商业组件[S16]|

不使用“个人使用”作为跳过许可证的理由；也不将使用免费组件误判为必须购买企业版。商业级质量不要求商业订阅。

### 3.1 最小依赖组合

第一批：一个主组件体系 + 现有CSS/Token + 现有Playwright。对话框/菜单/选择/提示/加载/错误/列表行为先统一。图标优先审计复用已存在素材，缺失再选一套许可证清晰的SVG图标，避免多套线宽。

第二批按真实需求单选：

|需求|候选|引入条件|
|---|---|---|
|资产/任务表格|TanStack Table core|排序筛选/列状态超出现有实现；其headless核心不替你生成UI和可访问性[S17]|
|特别复杂的表格|AG Grid Community|只有上项维护负担过高才比较；不用Enterprise试用功能进入产品[S21]|
|大批量导入|Uppy|需要队列/预览/上传状态时；必须适配现有JSON/API或新增受控传输契约，不能直接假设multipart可用[S18]|
|图片放大浏览|PhotoSwipe|需要缩放/键盘浏览；只做预览，不做第二画布；鉴权与CSP验证[S19]|
|复杂Brief文档|Tiptap OSS|结构化表单与普通文本不足时；不引入云协作和付费AI[S20]|
|可访问性检查|axe + Playwright|复用现有测试环境，增加对话框/菜单等关键状态；仍需人工键盘验证[S22]|

暂缓：通用节点编辑器、全功能Canvas、重型Docking、多租户、聊天框架、大型图表。专业工作台不是把更多库装齐。

### 3.2 组件接入前的硬验证

在同一个真实“Project/Brief + 资产选择抽屉”页面验证两候选，而非各做一套样板产品。验证控件至少包括按钮、文本输入、Select/Combobox、Dialog、Menu、Tabs、Toast/Alert、Tooltip、列表选择、loading/error。

1. 生产Python服务下加载，不只Vite dev；检查网络资源、console、CSP、离线可用。
2. 校验Shadow DOM事件、表单提交、焦点归还、Escape、Tab、中文输入法；截图测试选择器避免过度绑定DOM内部。
3. 同步Vite产物、资源白名单、Python wheel打包和测试；不能开放任意目录或直接加unsafe-inline/*绕过。
4. 若库使用额外样式/图标资源，采用受控本地打包；必要的CSP变更有具体资源理由和回归测试。
5. 记录bundle大小、启动时间、内存和键盘操作；没有数据时不声称“更轻/更快”。
6. 优先保持现有classic-script契约；如确需改成模块单测+真实浏览器测试，先形成build/test ADR，保留行为覆盖而非机械锁全局变量。

建议决策权重：兼容性30%、交互与可访问性25%、品牌适配20%、依赖与维护15%、预算许可10%。先过硬门，再评分；尚未实测，不预填得分。

## 4. 商业级个人工作台形态

### 4.1 保留DESIGN-LAB品牌，减少控制台噪声

沿用现有深色Electric Blue Token，统一间距、字号、边框、圆角、图标和状态色；当前代码8/14px圆角不是凭旧聊天改成4px。紫色不自动成为系统主色。客户项目自己的DesignSystem与工作台品牌Token是两个作用域，不能互相覆盖。

主要界面以作品与任务为中心：左侧导航，顶部项目/版本/全局搜索，中部参考或产物预览，右侧属性/权利/检查，底部按需任务状态。首页显示“继续项目、待确认、失败待修、最近交付”，不摆假KPI和无用成本大图。

图片默认contain不裁剪；缩略图裁剪模式与完整预览明确分开。透明棋盘只用于有alpha资产。中文长标题截断有全称入口；表单保存有dirty、saving、saved、conflict状态，离开未保存页有恢复策略。

### 4.2 现有导航怎么落地

|现有入口|个人版目标|真实动作|
|---|---|---|
|Dashboard|继续工作|打开最近项目、处理阻塞和待审|
|Projects|项目工作区|create/open；Brief编辑与版本；Reference、Direction入口|
|Research|项目研究|ResearchFinding/MethodCard与来源绑定；无后端时不显示假结论|
|Brand systems|DesignSystem/Token|目录与绑定继承；增加项目级可编辑版本、对比、回滚|
|Domains|能力目录|依据真实DomainPack列出可用/结构/未资格化；不是虚构数据库|
|Creative tools|生产与宿主|探测、准备、执行、取消、重试、结果；安装与授权状态分开|
|Preflight / QA|审查与预检|自动检查、人工意见、修订、失败定位和重跑|
|Deliverables|交付中心|源文件、预览、依赖清单、hash、重新打开验证|
|Evidence|证据回看|项目/版本/动作/失败/审批来源；默认简明，技术细节折叠|
|Collaboration|暂缓|个人模式隐藏或解释未开放，不建设账号/聊天/计费|
|Settings|个人设置|主题、语言、快捷键、获准宿主、逻辑Provider状态|
|Legacy workbench|过渡兼容|操作逐页迁入；没有完成替换前保留可工作的旧入口|

Cmd/Ctrl+K只搜索/执行DESIGN-LAB域内动作；WORK-LAB的跨项目入口不能在这里复制一套。原始RIR/patch JSON放Advanced，常用改字/换图/改色/位置以表单或属性面板提供。

### 4.3 Windows落地

第一阶段直接完善现有本地Python服务+浏览器入口。Windows并不妨碍高质量Web UI；先解决排版、控件、内容层级、持久化与错误恢复。

当确有托盘、文件关联、原生文件对话框、可靠宿主启动等需求，再比较薄Tauri壳与现有启动器。Tauri用WebView2、需同步IPC权限、Python sidecar生命周期与安装恢复；不是仅加一个壳就变成原生专业编辑器[S23–24]。Electron/WinUI/Avalonia不在本轮默认引入；换栈需要ADR、明确收益和回滚。先验证Windows LTSC机器上的实际WebView2/字体/缩放状态，不假设预装齐全。

## 5. 全部能力域的优化路线

|能力域|本期必须补的价值|后续扩展与验收|
|---|---|---|
|Design Intelligence|Brief/Reference→有来源的候选Direction；人选；DesignSystem→可修正对象计划|ResearchFinding/MethodCard与项目关联；不要新建ArcheAxis式知识底座|
|Professional Visual Domains|品牌/平面/电商的首条真实交付；工作台自身UI黄金例|UI/UX、包装、空间/展陈、3D、动效、视频、游戏视觉各有规格/案例/失败样本；按需放行|
|Visual Quality|构图/层级/文字/一致性检查；A/B对比、区域或对象批注|人工Jury和确定性规则分离；VLM只建议；拒绝→修订→再审|
|Creative Toolchain|当前最成熟Adobe链先闭合；标准Adapter生命周期|Figma/Penpot、Blender、ComfyUI按证据接入；不嵌入其整个编辑器|
|Production & Handoff|原生源文件、字体/链接、尺寸/色彩/出血/权利/可编辑性预检|按交付域配置；pack manifest、BOM、hash、限制声明、恢复|
|Research & Evidence|来源/revision/license、运行receipt和版本关联|旧证据复审、可撤销桥接；原始客户资产不自动外发|

### 5.1 优先宿主与生产能力

Adobe优先理由来自本仓库已有Photoshop/Illustrator脚本与native task链，不是全局默认宿主绑定。先probe真实机器，再根据当前可用性和案例选一个。Photoshop官方UXP与Illustrator官方脚本/面板机制是首选；必须按已安装版本适配，不能假设同一插件代码通吃[S25–26]。

首个商业案例建议选择你常用的海报/展架：可编辑标题、独立图片/蒙版、图形、规范尺寸、明确来源。完成改字、改色或换图、保存副本、关闭重开与结构读回。整张参考图贴底不算分层，RGBA图层不自动等于可编辑文字/矢量。

Figma/Penpot属于后续UI可编辑宿主。Figma官方Plugin API可读写节点，但需用户发起、不能当后台常驻插件；其文件字体/库访问有边界。不要把REST或某MCP的能力推断成任意后台写入[S27]。Penpot作为外部宿主可评估，不复制其编辑器[S29]。

ComfyUI复用现有实例，使用prompt/history/ws等官方接口；记录workflow、节点、模型、seed、input/output hash。interrupt可能影响当前实例运行任务，取消必须与任务归属/独占调度相匹配，不可无差别停止别人任务[S28]。8GB GPU条件下将并发和模型切换交给WORK-LAB资源治理；未经测量不承诺分辨率或速度。

Blender、音频、Premiere、视频、游戏资产均保留R5依赖；先有可编辑工程、依赖回读和失败恢复，再谈批量生产。AI分层、OCR、矢量描摹先申请真实任务所需能力，不能默认下载一套全管线。

### 5.2 与WORK-LAB/ArcheAxis的关系

Standalone-first仍有效：WORK-LAB不可用时能启动、编辑、保存、审查，已授权本地宿主可工作；依赖共享Provider的AI动作明确degraded/blocked。另设联邦集成验收，而不是把WORK-LAB在线作为全部测试前置。

WORK-LAB提供逻辑fast/deep及资源调度，DESIGN-LAB不维护第二模型库/通用runtime，前端不放API Key。Provider client位于Python侧，Workbench通过自身API访问。请求仅携带必要上下文和授权引用，记录Provider/model来源、取消/超时/失败，不静默fallback。

新建ResultRef/EvidenceRef之前先复用现有schema。跨项目只读观察凭证不能执行写动作；高风险控制动作需两侧授权。增加request_id、schema_version、expiry、幂等键等语义时先映射现有字段，避免自创第二合同。

## 6. AI、Skills、MCP怎样真正提高前端质量

可用官方Spectrum Agent Skills/llms.txt指导选定代际的控件实现；shadcn官方MCP仅在采用其生态时启用；Spectrum Design Data工具用于查设计规则，不能当成组件生成器。Playwright用于真实页面操作、截图与可访问性测试。

推荐执行回路：读取当前模块与Token → 按官方组件文档实现一个真实页面 → 生产服务运行 → 操作/异常/截图验收 → 修复 → 绑定证据。AI工具不锁定某一家模型。

仓库要求第三方SKILL/AGENTS保持inert来源，不能从网页直接变根指令。技能接入须审查来源/revision/权限，并映射为受控项目工作流；不批量安装陌生技能、MCP和组件模板。本次没有安装或执行这些第三方技能。

## 7. 旧UI资产的处理

本次找到47包总归档，但未解包读取。仓库style.css和shell.ts已给出B04/B07/B10血统和当前Token；这足以避免无依据换配色，不足以证明原始设计一比一。执行阶段应读取D:\All projects\UI套件中仅DESIGN-LAB相关原件，建立原稿文件→页面→组件→Token→当前实现→差异映射。若路径不可用先核对项目paths记录，不自动下载工具链或拿AAOS/WORK-LAB素材替代。

原稿里的演示数字不进入真实运行数据；原稿中的协作/未开发入口保留设计语义但不得假装可用。资产缺失时标MISSING_SOURCE，能用SVG/CSS精确重建的才重建，并保留来源和差异。用户视觉验收前不声明1:1完成。
