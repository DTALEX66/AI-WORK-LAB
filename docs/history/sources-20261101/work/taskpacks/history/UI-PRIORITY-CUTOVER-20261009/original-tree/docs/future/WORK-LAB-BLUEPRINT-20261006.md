# WORK-LAB 完整项目描述与未来蓝图（仓库承接）

Workflow Lab · 客户端中立的工作流治理、控制与交付 · 状态：**Ongoing**

- 承接基准：2026-10-06（Asia/Shanghai）。
- 输入原件：`02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx`，字节 SHA-256
  `f3784a9950adce06e8d87015a0ecb39d1ed4fdb3b93d5ccd3c9b40398bea3440`（本次实测一致）。
- 执行提示词：`02_WORK-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt`，字节 SHA-256
  `8d4a48185357aeadb99d9a2760a9ba05e6ab4fc744c0e3cb48a12904cf565247`。
- 本文性质：**仓库内承接层**。它把 owner 整理稿的规范性主张落到仓库锚点上，不替代
  `WORK-LAB-AUTHORITY.md`，不新建 current、不新建任务状态枚举、不宣告产品完成。
  逐行映射与处置见 `.project/governance/blueprint-coverage.json`（唯一可变源）及其投影
  [`WORK-LAB-BLUEPRINT-COVERAGE.md`](WORK-LAB-BLUEPRINT-COVERAGE.md)（由
  `python scripts/ci/verify_blueprint_coverage.py --write` 生成，勿手改）。
- 权威顺序（不变）：最新明确用户决定 ＞ `WORK-LAB-AUTHORITY.md` ＞
  `.project/governance/project-authority-index.json` ＞ current TaskPack 与唯一
  `taskpacks/current/OPEN-TASK-REGISTER.md` ＞ `AGENTS.md` 与范围内机器合同 ＞
  当前精确提交代码与 CI/运行时读回 ＞ 历史资料。

## 1. 口径与命名

对外名 **工作流实验室 / Workflow Lab**，对内保留 `WORK-LAB`；展示状态一律 `Ongoing`（来源 C01
`sources/CONTENT-COPY-V2.md`，SHA-256 `7d475862…fbeb2`）。AG/U/T/W/C/OD 编号只用于追溯，
不是新任务号、新运行时或可执行配置；不得用视图数量、客户端数量或测试数量定义项目本体。
锚点：本文件、`README.md` 首屏。

## 2. 母定义

WORK-LAB 是**客户端中立的个人 AI 工作流治理、控制与交付系统**（个人 AI 工程控制平面），
回答六个问题：谁在什么边界内执行、用什么规则与技能、任务如何流转、权限与预算如何裁决、
证据与完成如何判定、换客户端后方法能否带走。核心价值是**工作方法的可迁移**。
两条反向边界同等有效：不得缩成一个 Agent Dashboard，也不得扩成新的通用 Agent OS；
企业化、K8S、集中账号**不是**前置条件。锚点：`WORK-LAB-AUTHORITY.md` §3、`README.md`。

## 3. 所有权与不可混同的领域

七域划分（工作流 / 配置 / 权限预算 / 执行 / 观测 / 长期知识 / 设计）在
`config/config-ownership.json` 与 `.project/governance/module-ownership.json` 落地。
硬性结论：AAOS 的 Evidence 与 WORK-LAB 的 Evidence System 同名不同域，
**相同单词不赋予跨项目写权**；DESIGN-LAB 的设计方法、参数、IR、质量门与可编辑交付归
`DTALEX66/DESIGN-LAB`；不共享业务数据库、不合并三仓、不反向接管各领域 Authority。
锚点：`.project/governance/project-data-boundary.json`、`knowledge-staging/BOUNDARY.md`。

## 4. 五项核心能力与完整控制面

历史五核（Agent/Client Registry、Work Unit Engine、Runtime/Execution Control、Governance
Engine、Evidence System）保留，但 Runtime Control 按当前边界解释为**外部执行协作**，
不得重新拥有推理循环（其 2026-08-18 原始表述是修订前的读法）。完整能力集还包括
Context/交接、会话与执行联邦、模型与 Provider 策略、Token/Cost、版本冲击适配、雷达、
安全、清理、历史追溯；这些是同一系统的能力面，**不得变成多个平行产品或账本**。
锚点：`packages/client-neutral-core`、`services/`、`apps/observer`。

## 5. Canonical Source：规则、技能与配置

5.1 受管内容共 9 类（Rules / Skills / Plugins·MCP 声明 / Portable Memory / Capabilities /
Workflow Policy / Permissions / Budget·Cost Policy / Task·Work Unit / Delivery Rules），
最小治理形态为「一条全局用户规则 + 项目增量 + Adapter + 按需 Skill」。Portable Memory 是
工作流经验层，**不是**与 AAOS 竞争的跨领域知识真值，也不自动导入原生私人聊天。

5.2 配置事务八步：发现 → 有效配置 → ownership → 精确 diff → 恢复句柄 → 适用授权 →
原生写入 → 原生 readback →  verified 提交或诚实失败/回滚。Plan≠write、回调返回≠已验证写入、
写入无 readback≠成功。未知字段保留（`preserve_unknown: true`），不得整文件覆盖用户的
provider/model/auth/desktop 状态。锚点：`config/config-ownership.json`、
`scripts/sync_hermes_workflow_assets.py`。

5.3 软件基线与入口：每个受管软件一个官方/原生入口，任务级模型策略，`UPDATE ≠ RELOCATION`；
2026-10-01 移交中的启动器归属、受管块缺失、重装保全保留为行为案例，不作未经核对的旧结论。

## 6. Skills、Plugins、MCP 与能力生命周期

治理十步：发现 → 分类 → 原生重叠检查 → 来源/版本/许可 → 权限与数据范围 → Windows/原生探测
→ 隔离样本 → 原生加载与调用读回 → 回滚与证据 → 按需启用。状态阶梯七层各不相同且不可互证：
Registered / Installed / Loaded·Connected / Qualified / Enabled for Task / Native Projection /
Observed in Execution。仓库里有 `SKILL.md` 或界面显示 enabled 不证明实际生效；
不得把能力削成最低共同分母，也不得伪造平台没有的原生能力。锚点：
`scripts/ci/verify_skill_mcp_consistency.py`、`scripts/ci/verify_capability_conformance.py`、
`.project/governance/model-capability-matrix.json`。

## 7. Task / Work Unit

Work Unit 是主对象，聊天只是输入与载体。十二行字段职责表（Goal/Project 直到 Completion）
是**整理用**字段职责，不等于擅自发布新 JSON Schema；生命周期必须表达真实状态，
执行器不能自报 `done` 就把 Task Ledger 改成已完成；修订、取消、重试、恢复与迟到回执按既有
合同继承。唯一 writer + lease + 隔离 worktree；只读审计可并行；临时隔离不产生长期 shadow-main。
锚点：`packages/client-neutral-core`（Task Ledger 与交付门）、
`scripts/ci/verify_contract_ssot.py`。

## 8. 原生执行器、Adapter 与会话联邦

主执行器按八项因素逐任务选择，**任何单一品牌都不是永久唯一执行器**；原生客户端继续拥有自己的
会话、认证、模型、工具、子代理、worktree 与进程。Adapter 必须逐项声明八个动词
（发现 / 能力探测 / 计划 / 调用 / 观察 / 取消 / 恢复 / 回滚），未实现者必须在 UI、Resolver 与
任务计划里保持 `NOT_IMPLEMENTED` 可见。会话联邦记录与 handoff 载荷字段按合同登记。
现存张力如实保留：owner 历史已卸载 Hermes，而 2026-10-06 任务包要求 Hermes＋Codex 双执行器验收——
该要求只是该包的验收目标，替代选择必须留证，**不得暗中降标**。
锚点：`integrations/`、`scripts/ci/verify_acp_adapter_honesty.py`。

## 9. Context、记忆、交接与中断恢复

治理目标是丢失、失忆、路径错误、摘要漂移，读取保持最小。`ContextEnvelope` 携带版本与摘要、
有边界的产物句柄 + digest + 区间读回；恢复记录字段完备才可续跑。示例路径（如 `D:/WSL`）
不是现场事实；dirty/untracked 先保护再对账。OpenViking / Graphiti / Supermemory / Mem0 /
Hindsight 均为分层候选，**不是**已定的记忆底座。锚点：`packages/client-neutral-core`、
`.project/governance/future-candidate-registry.json`。

## 10. 统一入口：网页规划 → 原生执行

10.1 十一项闭环：轻入口 → ContextEnvelope/TaskPack → 网页规划审计 → `PlanningCandidate` →
原生执行器 → 测试/readback/回执 → Completion → Observer 展示。`PlanningCandidate` 是需按合同
接受的计划，不是执行命令，不取得 main 写权。

10.2 当前路径按 owner 默认裁决 OD02 取**结构化人工 handoff**；官方连接器 / Remote MCP 是独立
升级项，需七项验证（真实客户端、同任务同会话身份、范围鉴权、取消与幂等、断线恢复、回读、
计费解释与退出路径）。网页额度 ≠ API 配额 ≠ OAuth 原生会话；人工粘贴 ≠ 自动 transport；
禁止用网页抓取、cookie/session 复用或私人会话转发冒充。

10.3 轻入口 + 重工作区：不需要自建 IDE、终端或完整聊天产品。
锚点：`docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`。

## 11. Control 与 Observer：界面统一，权限分离

11.1 Control Surface 是唯一真写入口，2026-10-06 默认方案 OD01 为 **loopback-only** 控制服务/合同，
调用既有 Permission Gate、Task Protocol、Completion Authority、Config Control Plane；
后端未就绪时显示 disabled + 原因，**不存在前端模拟成功**；授权已覆盖时不机械重复询问。
默认方案的来源类别是「任务包默认」，不伪称用户已再次永久批准。

11.2 Observer 严格只读：不 Approve/Reject、不 Retry/Cancel/Rollback/Install、不改配置。
同一产品可同时提供两种面，但只读服务与凭证不得持有写权；UI 统一不得绕过授权边界。

11.3 数据必须诚实，六条等式不可违反：`UNKNOWN ≠ 0`、`STALE ≠ LIVE`、`HTTP 200 ≠ 任务完成`、
`Client reported completed ≠ Completion PASS`、`UI success ≠ 原生副作用`、`estimated usage ≠ 实付`。
锚点：`apps/observer/AGENTS.md`、`scripts/ci/verify_observer_readonly_boundary.py`、
`scripts/ci/verify_evidence_tiering.py`。

## 12. 模型、用量、费用与共享运行环境

模型选择由能力资格、原生可选性与授权决定；八个维度（模型选择 / 能力资格 / 资源 / Provider /
成本 / 额度 / 数据范围 / 故障）逐一可表达。预算压力允许可解释的免费或低价路由，
但**不得静默降低质量或隐私**；免费转付费、跨 Provider 外发、模型降级都必须在可见策略里。
登记为 `ready` 不等于进程已加载。2026-09-29 的 LM Studio / llama.cpp / ASR 进程快照只是该时点
环境，不含重装或删除授权。OD03/04 默认收敛（binary rerank 核心 + continuous 按需、
登录后自启动与自愈）属当前无运维范围，session-0 真服务留作未来验证。
Token Monitor 是支撑面，**不得**成为第二套费用真值。锚点：`.project/governance/model-registry.json`、
`scripts/ci/verify_model_registry_integrity.py`、`scripts/verify_usage_rollup.py`、
`apps/token-monitor`。

## 13. 完成裁决、证据、交付与恢复

13.1 完成度由目标与验证导出，绝不来自 `exit 0` 或模型措辞。证据词汇为
`NO_EVIDENCE / SIMULATED / SYNTHETIC / INTEGRATED / REAL`，REAL 必须有可核验句柄、身份与读回；
它与 DESIGN-LAB 的 `E0—E5` 是不同合同，不可互换。被跳过、取消或缺失的必需作业不计聚合 PASS。

13.2 回执必须关联（任务、修订、attempt、来源、命令、退出码、环境、产物句柄与摘要），
来源 / 执行事实 / 最终裁决三者分列；迟到回执不得覆盖新修订。

13.3 Git 交付合同：短分支 → PR → exact-SHA CI → 必要评审 → main → 短分支收口；main 是长期代码
Authority，R5/R6/恢复分支不自动成为新 main；PR 绿色不宣告产品发布。**本轮文档交付不执行
合并、安装或全局写入。** 锚点：`WORK-LAB-AUTHORITY.md` §11、`services/orchestration/`。

## 14. 产品界面、技术栈与数据组织

14.1 现有七个导航（Home / Work / Agents / Projects / Governance / Integrations / System）职责分区
保留；Lite、托盘 HUD、Quick Entry、Control、Observer 是同一系统的界面模式，**不是五套业务数据**；
DESIGN-LAB 的设计 Workbench/Launcher 不在 WORK-LAB 复制。

14.2 技术职责：React + TypeScript + Vite → Tauri 2 / Rust 原生壳 → 只读 Runtime Descriptor /
Snapshot / SSE → Python 控制平面与规范存储与 Adapter；跨语言真值用 JSON Schema。Rust 只在原生
API、进程身份、锁/围栏、IPC/安全、打包或实测性能处扩张，**不全仓重写**。活动代码面：
`packages/client-neutral-core`、`packages/contracts`、`services/`、`integrations/`、`config/`、
`apps/observer`、`apps/token-monitor`、`scripts/`、`tests/`、`.project/`；运行时与证据根
`.project-local/`。前端不得推断价格、汇率、配额、端口或成功状态。
锚点：`docs/decisions/language-architecture.md`。

## 15. 未来蓝图：六个分阶段（阶段名是本文的组织，不是新 CURRENT，也不承诺工期）

15.1 基础收敛——把已有实现变成可信执行事实（本机完整门、真实桌面 U19、Adapter 声明与能力、
配置读回、实际模型消费者、数据归属、分支遗留）。缺证据补证据，缺实现开发，真实缺陷修复，
不统一从零重做；放行标准是一条真实旅程 + 回执 + 恢复能力，不以注册数量或按钮数量计。
15.2 统一薄入口与真实 Control——放行条件为覆盖输入修订、权限拒绝、客户端不可用、失败恢复与取消。
15.3 多执行器与跨会话工作流——两个真实可用执行器在同一真实项目内各产出原生会话身份、损失报告与副作用。
15.4 跨项目协作与受管能力部署——Schema/API/Manifest/Adapter/Receipt/Candidate 的版本引用需验证
有效期、授权、幂等、拒绝、取消与最少上下文；外部项目 unavailable 只阻塞联邦路径。
15.5 官方网页桥接与远程接入——前置是人工 handoff 已稳定；七项验证见 §10.2。
15.6 自适应路由、演进与长期个人运维——影响分析与回归队列、雷达字段、安全与清理记录字段；
真正无人登录服务、额外网关、复杂 Context 后端、Harness Benchmark、安全隔离管理为条件性增强，
原文未给场景、验收、阶段槽位或退出条件，本文不予补全。

## 16. 未来候选池

原文表格 19 行（候选 / 家族、有边界的角色、触发条件与验收合一列），来源日期 9/23—9/29，
上游身份、版本、支持度与许可**本轮未在线复核**。仓库侧唯一落点是
`.project/governance/future-candidate-registry.json`（现 14 条，状态词表
`DEFERRED / PILOT_CANDIDATE`）。**覆盖差集**：原文 19 行 vs 注册表 14 条，差 5 条尚未登记——
逐条名单与补登记动作见覆盖矩阵 `§16` 行，不得把数量差当作完成，也不得按名单全部部署。
保留规则：收敛时不删除候选，不把旧角色恢复为 current；四条默认停止条件
（无净收益 / 重复已有能力 / 维护成本过高 / 许可·权限不可满足）；失败即回到原生或人工路径，
不触发第二次副作用。`MissionControl`、`Dagu`、`TokenTelemetry`、MCP/skill/plugin/provider 研究池、
`Strata`/`Qwen` 在原文是段落而非表格行，无候选字段，状态记为未结构化。

**【2026-10-07 更正，原文保留不改】** 上文“差 5 条未登记”是按 `19 − 14` 的算术差，不是名单差。逐行核对后的真实差集：14 条注册项只覆盖 19 行中的 **13 行**（`16.10` 由 Supermemory 与 Mem0 两条共同承接），**未承接行 6 条**（`16.11`、`16.15`、`16.16`、`16.17`、`16.18`、`16.19`），另有 `16.05` 行内的 n8n 未单列。本次按行补 7 条，注册表 21 条，19 行全部有承接项；行键即承接锚点，由 `scripts/ci/verify_future_candidate_registry.py` 核对。

### 16.1 原文表格逐行承接（19 行，行键 16.NN 为文档顺序）

下表逐行转录整理稿 §16 的候选池表格（候选/家族 ‖ 有边界的角色 ‖ 触发条件与验收），行键由本文按文档顺序赋名 `16.01…16.19`，作为注册表 `blueprint_row` 字段的唯一锚点。上游身份、版本、支持度与许可**本轮未在线复核**，一律记 `NOT_VERIFIED`；登记不等于部署，逐行状态见 `.project/governance/future-candidate-registry.json`。

| 行键 | 候选/家族 | 有边界的角色 | 触发条件与验收 |
|---|---|---|---|
| 16.01 | Orca | 外部人类工作区/原生执行器工作台 pilot | 现有入口有缺口；实际 Windows、原生执行与回读 |
| 16.02 | Omnigent | 外部编排对照 | 单任务收益与退出路径，不替代 WORK 任务真值 |
| 16.03 | Argos | 与工作区候选对照 | 实际能力、许可与维护成本，不能默认永久依赖 |
| 16.04 | OpenHands Agent Canvas | 并行工作区候选 | 原生会话/隔离/恢复与真实产物 |
| 16.05 | OpenMausBot、n8n | 辅助入口/桥接或外部流程候选 | 具体缺口、版本、取消/幂等与实际净收益 |
| 16.06 | ChatGPT Web Remote MCP | 官方获准规划—执行桥 | 认证、同任务回读、计费与权限清楚 |
| 16.07 | OpenViking | 分层 Context 检索后端 | 中文、当前事实、引用、隔离、恢复对照 |
| 16.08 | ContextForge | MCP/协议/认证网关候选 | 多身份痛点成立，权限贯通与退出 |
| 16.09 | Graphiti | 时态关系/来源派生检索 | 真实跨时间查询收益、可回读重建 |
| 16.10 | Supermemory、Mem0 | 至多一个记忆对照后端 | 召回缺口明确，成本、导出、隔离和恢复 |
| 16.11 | Hindsight | 后续检索到的长期记忆候选 | 不是已选底座；验证具体范围与本机路径 |
| 16.12 | Beacon | 必要日志字段采集 Adapter | 原生采集缺字段，数据最小化与身份绑定 |
| 16.13 | SoL / artifact handles | 大结果句柄和精确日志切片方法 | digest/range、过期/失败和成本收益 |
| 16.14 | Jev | 旁路语义评价候选 | 独立任务评价，不替代确定性门与人审 |
| 16.15 | Oh-My-Hermes | 少量技能/方法供体 | 只验证净新增方法，不恢复 Hermes 唯一中心 |
| 16.16 | Paperclip、Orca、agent-skills、OpenPencil 等近期材料 | 分别为治理/执行/技能/设计宿主研究线索 | 按项目归属核验，不将材料组合直接变成生产基线 |
| 16.17 | Prompts.chat、GEP/EvoMap 等 | 资料/经验方法来源 | 长期知识可归 AAOS；工作流仅留引用/合同 |
| 16.18 | ChatCut | 视频 Host 研究方向 | 专业设计能力归 DESIGN-LAB |
| 16.19 | EigenFlux、Dream-RSI、cc-haha、免费 Provider 与安全课程案例 | 历史研究保留 | 身份、许可、授权环境与需求逐项复核 |
## 17. 一一映射

17.1 `T01—T09`（2026-10-06 闭环包）在仓库内没有独立账本，其可执行落点是唯一 open register 的
对应行；每条只有「保留范围」与「不可替代的验收」两个字段，其余字段原文未给，本文不补。
17.2 `AG-09—AG-20` 与横切项映射到仓库现有 `AG-01…AG-20`（唯一真源
`taskpacks/current/WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md`）。
必须如实记录的原文缺陷：原文标题声称 AG-09—AG-20，但**无 AG-14 行**，且 `AG-16/AG-17` 合写成
一行；AG-01—AG-08 在该文档中根本不出现（仓库侧存在且仍在册）；`U02`、`U04`—`U17`、`U20+` 未被
提及；`W09` 缺号；`OD03/04` 只以联合引用出现，无法拆分各自含义。这些一律记为 `SOURCE_GAP`，
不得推测补圆，也不得据此删减仓库在册项。未被本文列出的 current 项继续依唯一 open register。

## 18. 当前证据边界、历史缺口与禁止漂移

18.1 原文所述状态**均为文件中的观察值**，须以实时值为准。本次重新观察（2026-10-06T22:20 +08:00）：
`origin/main = cd4daa83e107afab8438c0e85f63a10e75314d5a`（与原文一致，仍为当前默认分支），
交付分支 `task-decomposition/atlas-gap-archive-20261001` 远端 `f3b5dec…`；PR #162 仍 OPEN、
base main、mergeable，但其 head 已从原文记载的 `6f323a318a9db1c3a3ed4429bab0d4eff129876c`
前进到 `f3b5decf31ac6094d23dc4b77cec27a040b23d99` —— 该差异已在矩阵与审计快照中登记为更正。
2026-10-05 本机 full gate FAIL（1903 tests / 9 skipped / 12 errors / 22 failures，runtime 修复后未重跑）
与 exact-SHA CI 记录**同时保留**：CI 绿不抹去本机失败，历史失败也不自动证明今天仍失败。
未重验不得升级：真 Windows 桌面 U19、其他客户端 live 部署、新会话行为、性能、合并。

18.2 历史缺口：2026-09-29 总图声称 WORK-LAB 原始长聊天与 `WORK-LAB-SUMMARY` 不可访问，
2026-10-06 仍需恢复它们及 9/28 的 startup / final execution 特定附件；历史报告里的字节与行数
是**该报告值**而非逐行证明；不得以新写文档冒充原件，不得改写冻结历史；恢复的原件按
来源路径 / 日期 / hash / 原始位置 / canonical·alias / 能力覆盖增量登记。

18.3 十条禁止漂移原文保留，逐条落为可核验约束（见覆盖矩阵 `§18.3` 行与
`scripts/ci/verify_blueprint_coverage.py` 的反漂移断言）。

## 19. 项目描述与覆盖检查

可采用的一段式对外描述（与 GitHub About 同源）：

> Client-neutral workflow governance, control and delivery: portable rules, native client
> adapters, task coordination, permissions and evidence-based completion. Ongoing.

当前推进优先补本机 / 桌面 / 双执行器 / Control / 模型 consumer 与真实配置 readback，
再扩大自动桥接与条件性服务；领域知识与设计生产仍由各领域项目拥有；不以愿景描述宣称
Universal Workflow 已完成。完整逐行覆盖与处置：
[`WORK-LAB-BLUEPRINT-COVERAGE.md`](WORK-LAB-BLUEPRINT-COVERAGE.md)。
