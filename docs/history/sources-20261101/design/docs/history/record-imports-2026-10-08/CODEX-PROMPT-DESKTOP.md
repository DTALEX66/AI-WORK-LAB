# DESIGN-LAB 新分支 Codex 执行提示词

你在 DESIGN-LAB 独立仓库与独立新分支工作。请对照当前产品 Authority/W00—W17/Source Registry，把前端和可操作设计工作台按真实职业设计链推进。不得与 WORK-LAB 或 AAOS 合仓、共享业务数据库、品牌主题或领域写权。

## 权威和资料顺序

1. 用户本轮明确指令；
2. 当前仓库顶层 Authority、唯一 current ledger、W00—W17 对应任务、现有 contracts/registries/schema；
3. 2026-10-06 `03_DESIGN-LAB_完整项目描述与未来蓝图_20261006.docx`（整理稿，不代替仓库 Authority，需刷新日期相关状态）；
4. 当前仓库真实前端、Host/Adapter、实现、运行与证据；
5. `DESIGN-LAB_UI开发资料总包_按批次.zip`：视觉资料引用权重 B10>B09>B08>B07>B06>B05>B04>B03>B02>B01；不是实施队列。
6. 本包 `UI_KIT_AUDIT.md`、`SHARED_ORDER_AND_GOVERNANCE.md`、`UI_COMPONENT_ADOPTION_PLAN.md`。

目前没有找到“昨天 23:40”精确原始聊天；不要声称已读取。10/6 蓝图里提及的仓库 HEAD、CI 和实现范围只是当时文件证据，不是实时结果。

## 产品身份与边界

DESIGN-LAB 是 AI 原生、平台中立、宿主原生的职业视觉设计智能与生产能力系统，采用 standalone-first + host-native editing。它拥有 Brief、ReferenceSet、ResearchFinding、MethodCard/Visual DNA/Direction、DesignSystem、Design IR、DomainPack、Asset/Artifact/ToolRun、Quality/Critique/Human Jury、Rights、Preflight、BOM/Handoff、Readback/Rollback/Evidence。

它不再造第二个 Photoshop/Figma/Blender 画布，不成为通用聊天、模型网关、Agent OS 或 WORK-LAB 的策略/任务权威。Host/Skill/Plugin/组件来源、版本、许可、权限和真实资格都要明确，候选不等于已安装/已通过。

## 视觉方向与资源

- 只保留 DESIGN-LAB 自己的黑/深灰、冷白、中性灰和 Electric Blue `#316CFF` / Secondary `#4BAFFF` 的品牌方向；B07 示例表面为 `#0D1221/#11182A`，文本 `#F5F7FC`。先核对实际 Authority/tokens。
- AAOS 的 pearl-white、深空/星环主题，WORK-LAB 青色或其他仓库客户品牌不可复用成 DESIGN-LAB system theme。紫色只作为具体作品素材或极少创意焦点，不作为全局主色。不要用暖金/暖白营造豪华模板感；告警状态依据语义，不要混入品牌主色。
- 复用 DESIGN-LAB 自己的 Logo、VI 网格、Bezier/裁切/字体/图标和可授权设计样例；查来源、rights、源文件/透明通道。图稿/缩略图是参考，不等于源设计或授权客户资产。
- 精致视觉要服务专业对象操作：方向对比、画布局部焦点、对象选取、可编辑结构、评论/缺陷定位、预检阻断和交付版本。不要用大面积发光或空卡片代替生产结果。

## 产品 IA 必须围绕设计旅程

把当前用户模式、W00—W17 与现有页面映射到：真实 Project/Brief→Constraints/Rights→Reference/Research→Method/Visual DNA→Directions（由人选择并锁定）→DesignSystem/Domain Pack→Design IR/ToolActionPlan→获准 Host/Generator 执行→原生 Readback/局部编辑→Quality/Critique/Human Jury→Rights/Preflight→Editable Handoff/BOM/Receipt/Recovery。

可在产品现有路由里提供 Dashboard/Projects、Research & Capability Library、Project Workbench、Brand/DesignSystem、Domains、Host/Tools、Quality/Jury、Rights/Preflight、Deliverables/Handoff、Evidence/Settings，但不要因 UI 套件旧导航数而新建重复模块。主导航先展示用户任务与当前状态，术语在需要时展开。

## Design Capability Library（10/6 最新重点）

这条线收集组件/设计系统/Skill/插件/MCP/方法/案例/审美知识等可重用“设计能力”，不是全网链接或自动安装市场。UI 至少有：

- SourceRecord：来源、作者/上游、URL/提交/版本/hash、发现时间、license、用途和权利范围；热度值要记录平台、采集时间、单位，不把 star/like/favorite 混成质量分。
- 多轴分类：专业域、产物类型、审美家族、视觉构成、阶段、实现形式、Host、成熟度、rights/deploy 范围。
- ResearchFinding/MethodCard/Capability Contract：输入/输出/约束/资源/权限/适用范围/禁用范围/变更损失。
- Host/Agent Projection：版本与能力探测、原生投影差异、安装/loaded/connected/qualified/task-enabled 分开显示；未知就显示未知。
- 样例验证、Readback、专业人评、失败模式、升级/撤回与来源引用。热度不是审美，也不是商用许可。

优先挂接现有 Source Registry、Method、Domain、capability/schema；不要新造平行 catalog/runtime 或一次部署全量插件。真实 OSS 组件的详细评估和部署见随包方案。

## 质量/许可/可编辑性

- 自动视觉分数只定位候选问题，不能自动替代 Human Jury/用户选择。
- QualityAssessment/PreflightReport/HandoffPackage 绑定 Artifact/version/hash/host version；源文件、生成文件、字体/模型/图像/插件许可分别追溯。
- DesignIR/ToolActionPlan 要能说明对象/文本/矢量/图片/布局/锁定区域和 Host 损失。整图当背景、扁平化导出或 localStorage 不能称为可编辑/可交付。
- 对 AI 图、客户源资产与参考素材采用最小范围存储和展示；客户文件默认不向 AAOS/WORK-LAB 发出。
- 未被 Host/权限/许可证支持的动作明确列 unsupported/blocked，不用 mock 按钮完成。

## 执行步骤

1. 只读盘点 branch/dirty/Authority/current ledger/W00—W17/入口与运行方式；保护未提交内容。记录 10/6 蓝图和当前仓库实际不一致之处。
2. 做页面→领域对象→API/schema→Host→Rights/permission→artifact/evidence→状态矩阵。区分真实可用、partial、E0候选、静态假数据。
3. 核对已有组件库/ tokens /图标/Storybook/测试、许可证和 React/Vite/Tauri/Python 版本。用一小片高密度项目列表/Brief/对话框来判定单一组件底座；不同时安装 Semi+Mantine+Ant，方案见 `UI_COMPONENT_ADOPTION_PLAN.md`。
4. 沿当前组件栈完善 Workbench shell、品牌/客户 tokens 隔离、Project/Brief/Reference 浏览；建立真空态、权限、离线、损坏素材与加载态。
5. 先让一个真实 Brief→方向选择/锁定→design system/DesignIR→当前可用 Host 的编辑/保存/readback→用户评审→Rights/Preflight→可重开 Handoff 跑通；复用现有 W 任务和 contract，不另创账本。
6. 再把 Design Capability Library 加入实际工作流：可检索、可分类、可追来源/权利、可对一项候选做受控适配/资格化/撤回。
7. 验证 Human Jury、QA问题定位、源文件编辑、拒绝/再提交/版本失效、Preflight硬阻断与恢复。跑当前仓库的 test/build/Windows/host readback 与实际视觉检查。
8. 输出 `UI_IMPLEMENTATION_REPORT.md`：分支/HEAD、工作树、映射、组件选择/版本/license、能力库状态、Host读回、当前产品轴/E级证据、测试/截图/日志/产物哈希、未完成与回滚。只按 Authority 更新正式记录。

## 验收门

- 一个真实用户 Brief 能完整绑定方向、引用来源、Host 产物和版本；方向更换会使依赖结论适当过期。
- 至少一个真实原生 Host 保存并能重开/局部继续编辑，记录 Readback；Host 调用失败后能恢复或清楚退出。
- 人可以对方向/质量作出 Accept/Reject/Change 请求并有版本与理由；自动评分不得强行放行。
- Rights 与 Preflight 有一个明确阻断、修复、重新检查案例；过期证据不能覆盖新版本。
- Handoff 交付真实 source/export/manifest/BOM/许可/字体与恢复信息。
- Component Library 原生接入与自研规则有来源/许可/版本/差异；未授权素材不外传；无静态假 KPI/虚假 Host connected。
