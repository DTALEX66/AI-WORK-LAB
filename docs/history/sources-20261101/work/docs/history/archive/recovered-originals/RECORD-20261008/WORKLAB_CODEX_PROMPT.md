# WORK-LAB 新分支 Codex 执行提示词

你在 WORK-LAB 独立仓库与独立新分支工作。请把这次任务限定为：基于真实仓库状态，对照最新 WORK-LAB Authority/TaskPack，重新规划并分阶段完成产品前端，不重写或合并其他项目。

## 权威和资料读取顺序

1. 用户本轮明确指令；
2. 当前仓库顶层规则、Authority、唯一 open/current register、相关 TaskPack 与真实 API/schema/permission/completion contracts；
3. 2026-10-06 `02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx`（整理稿，不替代仓库 Authority；只用其方向/边界，刷新其中时间性事实）；
4. 当前分支实现、测试、运行/读回证据；
5. `WORK-LAB_UI开发资料总包_按批次.zip`：图稿冲突采用 B10>B09>B08>B07>B06>B05>B04>B03>B02>B01。此序列只表示设计引用权重，不升级为项目 Authority。
6. 本包 `UI_KIT_AUDIT.md`、`SHARED_ORDER_AND_GOVERNANCE.md`。

不得把“昨天23:40”标成已读的原始对话：目前未检索到精确聊天。不得宣称 10/6 旧 HEAD/CI 状态是当前状态；开工先获取真正 HEAD、dirty 状态、开放项和本机/CI证据。

## 产品身份与边界

WORK-LAB 是客户端中立的个人 AI 工作流治理、控制与交付系统。它负责 Work Unit/依赖/handoff/租约/完成裁决；声明受管的 Rules/Skills/Plugins/MCP 配置字段及事务；任务风险、权限、预算、Adapter 路由；可观察快照、事件、用量、回执与可携带 workflow context。原生客户端保有自己的推理循环、会话、认证、模型选择、执行器进程、私人记忆和未知配置字段。

它不是通用聊天、IDE、Agent runtime、模型网关、第二个知识库或普通项目管理器。不合并仓库、业务数据库或 AAOS/DESIGN-LAB Authority。跨项目只通过授权、版本化 schema/API/manifest/receipt/candidate 与最少引用。

## UI 方向

- 维持 WORK-LAB 自己的深黑/深海军蓝+Electric Blue `#2A91FF` / Cyan `#20CDE1`；B07参考底色 `#050D16`、surface `#081420/#0C1B2A`、文本 `#EEF6FC`。先检查仓库现有 tokens，再校准差异；不把 AAOS 的珍珠白/深空三主题或星环视觉搬过来。
- 蓝青是品牌/焦点的少量强调，成功/告警/危险保持语义与对比度。避免大面积霓虹、金色或装饰性 KPI。
- B01/B02 本项目 VI 可作为 logo/icon/grid/source reference；图像要指回原始包和许可。页面数据来自真实 API 状态，不硬编码截图指标。
- 支持高信息密度桌面控制台，遵循当前 shell 和响应式基线；全键盘、清晰焦点、Esc/返回、命令面板、Reduced Motion、Loading/Empty/Offline/Unknown/Stale/Partial/Error。

## 产品信息架构 / 黄金流程

从当前路由、领域对象和 TaskPack 映射，不照抄旧图稿导航数。确保用户可以：

目标与项目 → 有效 Authority/Context → Work Unit/PlanningCandidate → 能力/原生 Executor → 授权的 Control 动作 → 执行事件/真实产物 → Tests/Readback/Receipt → Completion 判定与只读 Observer。

围绕这条主流程逐步覆盖 Overview、Workflows、Workflow Editor、TaskPacks、Execution/Timeline、Approval、Rules/Policy、Integration/MCP/Models/Tools、Audit/Evidence、Settings。旧 UI 的 Memory Registry 只能呈现 workflow context/获准经验的引用、来源与适用范围，不能演变为 AAOS 知识库。

## Control / Observer 硬约束

- Control 是写动作入口：调用当前实际 Permission Gate、Task Protocol、Config Control Plane 和 Completion Authority。每次真实副作用有任务身份、授权、幂等/租约、回执、原生 readback、恢复范围。
- Observer 严格只读：显示来源、observedAt、新鲜度、未知原因、快照/事件/成本/用量/运行证据；不能有 Approve/Reject/Retry/Cancel/Rollback/Install/Apply 等写操作。
- 缺数据=`UNKNOWN`，陈旧=`STALE`，部分来源=`PARTIAL`，错误=`ERROR`；绝不把缺失转成 0/idle/healthy 或假实时流。
- 后端合同未实现时禁用按钮并解释原因。禁止 localStorage/临时 mock/固定时间/绿色 toast 冒充配置、执行、审批、完成或审计事实。
- 原生客户端授权与登录仍在原生软件。WORK-LAB 只管理明确归属的字段，不写用户私有字段/未知配置/auth。

## 执行步骤

1. 生成只读审计：仓库 HEAD/branch/dirty、入口、页面、组件/tokens、服务/API、任务和状态合同、测试/CI、平台运行、证据缺口；先保护未提交工作。
2. 建立 UI 页面—领域对象—API/命令—permission/receipt—当前测试映射。把已实现、partial、stub、mock、unknown 分开标记。
3. 确认已有组件、图标、样式、可访问性基础和依赖；在 `UI_COMPONENT_ADOPTION_PLAN.md` 的小范围对比后只选一个符合现有栈的 primitive 路线，不把 Demo `@three/ui-core` 搬进生产仓库。
4. 用现有技术栈修正 tokens/AppShell/导航与真实状态投影；不大迁移、不新增全局安装、不重造已有 API/状态机。
5. 按一条可重复 golden path 完成薄入口→任务合同→授权控制→真实执行→读回/回执→Observer只读投影。优先解决缺失值/错误状态被展示为绿色的情况。
6. 逐页补强高频治理组件：状态标签、权限上下文、审批差异、执行时间线、任务详情、配置 diff/readback、错误恢复、审计记录。
7. 建立与实际页面一致的组件/状态图库；加入键盘/焦点、缩放、视觉回归；验证真实 Windows/Tauri 和相应 CI，而非只运行 Vite。
8. 输出 `UI_IMPLEMENTATION_REPORT.md`：HEAD、变更、页面/API映射、组件来源/版本/license、真实证据、验证命令/结果、未完成项和回滚方式。只有符合当前项目 Authority 时才写回正式记录。

## 验收门

- 无未经授权写入/跨项目数据访问；Observer 写权限为零。
- Unknown/offline/stale/partial/error 视觉和屏幕阅读器能区分。
- Keyboard-only 能打开/关闭 palette、dialog/drawer、移动焦点并返回焦点；Reduced Motion 有效。
- 至少覆盖成功、无数据、加载、断网、权限不足、后端未实现、真实失败/恢复状态。
- Work Unit/Approval/Config/Receipt 均能读回真实后端状态；写动作可按权限和幂等约束验证。
- UI截图、CI绿灯或静态本地存储均不得单独作为产品完成证明。
