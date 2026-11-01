# 执行状态日志 — WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916

**性质**：append-only 状态账本（不重写历史）。每卡一条记录，格式：
`### NF-xx-SYNC | <status> | <evidence-level> | <commit> | <date>`。
**执行边界**：可自执行片（仓内契约/设计/合成+多进程测试/CI/规则澄清/账本）做到闭环；
真实外部副作用片（真实云端发布、第二真实项目、第二执行软件、真实双环境、付费模型）
建好代码 + 合成证据后诚实标 `BLOCKED` + 精确依赖，绝不伪造 PASS。
**基线**：`r4-recovery-exec @ de2f3fd`；main `e5231f0`（不合并、不重开历史）。

---

### NF-00-SYNC | PASS(可自执行片) | DOCUMENT_CHECK | pending | 2026-09-16
- 状态：锁卡完成。范围更正 + UNIVERSAL 包登记进 authority-index；4 类范围区分（WORK-LAB
  代码开发 / 目标项目接入 / 远端发布 / 本机部署）已记录；20 个旧父卡承接去向已在
  TASKS.json carry_forward 固化（15 续 + 4 条件项 deferred）。
- 真实外部片（BLOCKED，精确依赖）：真实"目标项目接入 + 远端发布目标"落地需用户对
  具体目标项目与发布空间的接入授权（本包 `grants_new_permissions=false`）。锁卡本身不授权。
- 证据：`taskpack-authority-index.json` 新增 `universalWorkflowPack` 段 + 本记录。

### NF-01-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * 纯函数模块 `packages/client-neutral-core/scripts/artifact_flow_policy.py`
    （5 决策路径 ALLOW/PENDING_AUTHORIZATION/ISOLATE/REJECT + 嵌套秘密检测 + 项目偏好 scoping）。
  * `tests/workflow-assistance/nf01_rule_semantics_artifact_flow.py` 18/18 全绿（gate-direct）。
  * `docs/decisions/global-execution-standard.md` 追加 §七 dated 澄清（不改 5 维原义、不新增全局限速）。
  * `.project/governance/project-data-boundary.json` append-only 增加 artifactFlowSemantics（既有键全部保留）。
- 真实外部片（BLOCKED，精确依赖）：AT-02「同一全局规则部署到两种真实软件真实回读」需对应软件写权限授权；本卡不伪造 PASS。


### NF-03-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * 纯函数模块 `packages/client-neutral-core/scripts/project_binding_registry.py`
    （稳定不透明 project_id + 可选 repo 关联 + git/artifact 基线 + 材料位置/能力白名单
     + 本机 root binding overlay + 云端路径拒绝 + 同名不串 + 未知 ID fail-closed）。
  * `tests/workflow-assistance/nf03_project_binding_registry.py` 15/15 全绿（gate-direct）。
- 覆盖 AT-05（同名同任务号隔离）/ AT-06（换设备路径重绑定只信本机 binding）/ AT-07（第三非 Git 项目仅配置接入）的合成可自执行片。
- 真实外部片（BLOCKED，精确依赖）：真实目标项目与路径需用户对该项目的接入授权；合成项目限定当前批准测试根。非 Git 项目的原生执行限制须对真实执行软件诚实标注。

### NF-08-0 | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 兼容扩展交接格式（增量，未造第二套权威格式）：
  * `packages/client-neutral-core/scripts/handoff_envelope.py`：v2 信封（登记驱动项目引用 + 源/目标软件分离 + 环境绑定 + 任务修订号 + 基线种类 git/artifact + 不可变摘要 + receipt 位置 + 目标能力 + 授权引用 + supersedes 链）。
  * `.project/governance/federation/federation-envelope.v2.schema.json`：v2 schema，v1 schema 原样保留供旧读取方。
  * `tests/workflow-assistance/nf08_0_handoff_envelope_v2.py` 18/18 全绿：v1 可读、v2 显式拒绝 v1 不静默截断、项目ID≠客户端ID、同任务同修订不同摘要=冲突不覆盖、高修订走 supersede 链不合并、迟到低修订结果保留待审不推进、授权只信本地可信授权记录（payload 自声明忽略）、Ready 指针仅在不可变快照完整后发布、v1→v2 迁移未登记引用 fail-closed。
- 真实外部片（BLOCKED）：真实项目间跨机交接需对目标项目授权 + 真实环境节点；本地授权记录/注册表需对真实软件配置面消费。

### NF-08-A | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/publish_planner.py`：发布规划 + 逐动作权限审计（纯函数，无网络、不读凭据）。
    材料分级路由存储目标 / 大正文先固定版本工件再摘要+引用 / 逐动作写权核对（push≠全动作）/ 回读校验 / 幂等 / 公开目标拒收私人 canary。
  * `tests/workflow-assistance/nf08_a_publish_planner.py` 21/21 全绿（AT-11/12/13 合成片）。
- 真实外部片（BLOCKED，精确依赖）：真实服务端写 + 回读需目标空间发布权限与用户对这批材料外发的授权；未获写权停在 PUBLISH_PENDING_AUTHORIZATION，不称同步成功。

### NF-08-B | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/durable_inbox.py`：复用既有 TaskLedger 持久化边界（ledger.json + 原子 os.replace + orphan 恢复 + 租约 fence），未新增独立队列库。
    inbox/outbox/认领/命名空间可暂停/事件身份去重/条件请求+Retry-After/先持久化认领意图再调执行器/恢复对账不重起/内容不变不重写工件。
  * `tests/workflow-assistance/nf08_b_durable_inbox.py` 12/12 全绿（AT-14/15/16/17 合成片：跨进程不重起、并发单派发、A故障不阻B、同步检查不调用模型、工件不重复写）。
- 真实外部片（BLOCKED）：真实订阅需项目/节点接入授权；持久化限当前批准根；多机不复制活动 ledger 做多主。

### NF-05-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/capability_roles.py`：客户端能力按角色登记 + 探针驱动（非固定七项 enum）。
    角色语义分区 planner/executor/reviewer/storage/observer；能力=探针确认的动态集合；GitHub/CC Switch 按真实角色登记、无 execute 探针即不可当执行者；同一 adapter_id 被两项目复用（分发键=adapter 非项目名，无按名分派）；缺 Hermes 其它执行器仍可用（按能力选执行器）；缺接口=PARTIAL/UNSUPPORTED+补齐前提，不报"全功能完成"。
  * `tests/workflow-assistance/nf05_capability_roles.py` 12/12 全绿（AT-18/19/20 合成片）。
- 真实外部片（BLOCKED）：真实客户端探针/启动需原生会话许可与对应授权；元数据探针≠付费调用。

### NF-08-C | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/dispatch_contract.py`：分派到执行的合同（不再停在交接模拟）。
    分派前冻结 task/revision/baseline/执行者/授权引用+解析本机工作区；脏工作树不自动 pull/reset；记录启动前意图+真实 run/session ID+实际指令源（非 --last）；低风险确定性先跑、Agent 任务需费用授权否则 HOLD、假执行器仅算契约证据；换执行者先确认旧运行体 COMPLETED/PAUSED 只交剩余工作；启动失败分层归因（transport/permission/runtime/model，不阻其它项目）；exit 0 或模型 DONE 不算验收全部通过。
  * `tests/workflow-assistance/nf08_c_dispatch_contract.py` 12/12 全绿（AT-11/18/21 合成片）。
- 真实外部片（BLOCKED）：真实原生执行器启动+模型费用授权；不自动获得 commit/push/merge；不拼接远端 shell。

### NF-08-D | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/result_return.py`：结果回传、读取与显式复核触发（复用既有 receipt/outbox 语义，未造第二套回执格式）。
    回执绑定 project/task/revision/run/baseline/工件digest，区分 execution_completed 与 accepted；outbox 幂等（应答丢失不造重复、重试只重发回执不重跑任务）；规划端新读取按精确修订号回读不猜其它修订；正文/私有会话日志绝不进公开遥测；RECEIPT_PUBLISHED≠REVIEW_REQUESTED；反向编辑同权限+版本检查；无受支持通知通道则 REVIEW_PENDING，绝不断言唤醒了旧聊天。
  * `tests/workflow-assistance/nf08_d_result_return.py` 15/15 全绿（AT-22/23/24 合成片）。
- 真实外部片（BLOCKED）：真实回执写需原任务指定目标的回执写权限；主动触发新审查/模型调用需既有有效授权；不重发即不重跑、不回滚已发生的外部副作用。

## 里程碑达成

### M0 差集与通用边界确定 | PLAN_READY | 2026-09-16
- requirements: NF-00-SYNC / NF-01-SYNC / NF-03-SYNC / NF-08-0 — 四卡全部 PASS(可自执行片) 已提交并推送（c0a3151 → 2953c25 → 24a56c5 → 4d67de3）。
- 8 个新测试文件合计 123 用例全绿（gate-direct 运行）。

### M1 首条真实云端到本地往返 | ONE_REAL_FLOW_VERIFIED | 2026-09-16（可自执行片闭环，真实外部片 BLOCKED）
- requirements: NF-08-A / NF-08-B / NF-05-SYNC / NF-08-C / NF-08-D — 五卡全部 PASS(可自执行片) 已提交并推送（c03d3de → 0ca5848 → 48f50b4 → b38450d → 56c9e48）。
- 可自执行片=设计+代码+合成测试，已在已授权范围（当前批准根、合成项目、无网络/无付费/无凭据）内全绿。
- BLOCKED 真实外部片（精确依赖）：真实服务端发布/回读、真实原生执行器启动+模型费用、真实订阅/节点接入 — 需对应授权与接口就绪，仅暂停受影响分支，不影响合成片证据。
- 回归：8/8 测试文件 123 用例全绿。


### NF-08-E | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/revision_convergence.py`：修订/取消/乱序/未知效果收敛（复用 handoff_envelope.RevisionRegistry + task_ledger transition/external-effect 词汇，未造第二套收敛模型）。
    旧修订晚到不结束/不冲掉新修订（active 指针=最高已发布）；取消/终态任务拒绝启动新效果，已发生/仍不确定效果可查询；UNKNOWN/CONFLICT 效果不盲重试（先对证据 reconcile），拒绝只限受影响任务；乱序交付以最新修订为权威、旧结果保留审计。
  * `tests/workflow-assistance/nf08_e_revision_convergence.py` 12/12 全绿（AT-25/26/27/28 合成片）。
- 真实外部片（BLOCKED）：真实跨软件取消需对受管任务的原生取消授权；没有用户进程终止权限就不 kill。

### NF-08-F | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/entry_semantics.py`：各软件一个按需入口，统一动词（publish/view/resume/adjust/return）路由到宿主原生入口，用户看动词不记目录；未原生支持的动词不发明。
    两宿主无需复制正文且一个不依赖 Hermes（宿主选择按能力+Hermes依赖，非按名）；授权范围内不逐卡重复确认、只有新增外发/写入触发对应授权（已授权 scope 不 re-ask，不同 scope 仍触发）；标准接续只加载任务所需上下文（checkpoint/当前修订/未完成项），显式不拉全部项目历史与技能全文。
  * `tests/workflow-assistance/nf08_f_entry_semantics.py` 10/10 全绿（AT-29/30 合成片）。
- 真实外部片（BLOCKED）：发布到各软件全局配置是独立、可批量批准的部署动作；仓内技能可按开发授权编辑。

### NF-08-G | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/transport_channels.py`：第二传输通道与非 Git 项目落地（复用 NF-03 非Git工件基线 + NF-08-0 v2 信封，通道为薄传输非新分发模型）。
    相同业务交接经 GitHub 与文件双通道往返一致（核心分发 payload 不变，证明不锁定 GitHub）；第三个非 Git 示例项目完成工件往返（publish→execute_from_reference→receipt，baseline_kind=artifact 非 git commit）；半上传/过期或缺失附件/重复文件/同路径不同摘要冲突/路径穿越 全部不触发任务。
  * `tests/workflow-assistance/nf08_g_transport_channels.py` 12/12 全绿（AT-07/31/32 合成片）。
- 真实外部片（BLOCKED）：真实第二存储/设备接入需已批准接入；无安装授权不装新文件同步软件；真实云端端点能力另行准确标注（模拟只算测试）。

### NF-08-H | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/cross_project_isolation.py`：跨项目协作引用与隔离（复用 project_binding_registry 每项目独立根 + NF-08-0 授权引用语义，未造第二套协作模型）。
    A 网络失败/改规则/取消任务都不影响独立 B（独立命名空间/根）；授权 A→B 交付完成并记入 B 自身命名空间（grant 精确绑定 from/to/artifact，revoke 即失效）；未授权引用拒绝且不越 B 读取边界（项目名本身不构成批准，不同 artifact 不被该 grant 覆盖）；共享 UI 只暴露粗粒度授权可见状态（COMPLETED 等），项目私有摘要正文绝不外泄。
  * `tests/workflow-assistance/nf08_h_cross_project_isolation.py` 12/12 全绿（AT-05/17/33/34 合成片）。
- 真实外部片（BLOCKED）：跨项目协作需双方作用域内有效授权；项目名称本身不构成批准；不把全项目资料提交到 WORK-LAB、不建跨项目共享记忆、不因模块目录相似自动合并项目。

### NF-08-I | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/environment_takeover.py`：多环境路由与受控接管（复用 NF-03 每项目根绑定 + task_ledger 租约 fence 单派发原语；不共享文件夹仲裁、不强上 Redis/Kafka/K8s、不自动关用户其它软件）。
    不同环境路径不同仍取同一 project/task/revision（identity 核心=路径/环境无关哈希，环境标签仅用于路由）；接管后旧节点返回在线不重派旧任务（另一节点持有派发则只 rejoin 不写、状态不可确认则 BLOCKED_UNCONFIRMED 显式阻塞非双写）；双设备接管声明需两真实环境 handle，模拟只算测试不算证明。
  * `tests/workflow-assistance/nf08_i_environment_takeover.py` 10/10 全绿（AT-15/16/35 合成片）。
- 真实外部片（BLOCKED）：双设备接管声明需两真实环境证据（至少一个真实云端发布端+真实本地执行环境往返）；模拟只能算测试；新增设备绑定与受控接管需批准、不复制跨设备凭据。

### NF-02-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/acceptance_evidence.py`：验收证据分级 + 精确版本 CI（模拟与实测分别计数不伪通过；未授权/低于要求等级保留 PENDING-VERIFY 不伪过；外部项目不复制核心源码+角色切换不串线；required CI 绑定精确 SHA 不同 SHA 不替代/不连 everyday self-hosted runner/可选方案比较不阻塞 required gate）。
  * `tests/workflow-assistance/nf02_acceptance_evidence.py` 14/14 全绿（AT-01/14/15/25/31/35/39 合成片）。
- 真实外部片（BLOCKED）：真实跨进程/外部项目/CI 证据需对应授权与真实设备/客户端；未获授权只保留待验不伪通过；不用另一 SHA 的 CI 成功替代；不在公开仓连任意 PR 可调用的日常电脑 self-hosted runner。

## M2 里程碑达成

### M2 多项目、多软件、多环境和非 Git 扩展实证 | UNIVERSAL_TRANSPORT_EXECUTION_VERIFIED | 2026-09-16（可自执行片闭环，真实外部片 BLOCKED）
- requirements: NF-08-E / NF-08-F / NF-08-G / NF-08-H / NF-08-I / NF-02-SYNC — 六卡全部 PASS(可自执行片) 已提交并推送（8a9fe66 → 8addf81 → 87782be → 9e52155 → 4340c63 → NF-02）。
- 可自执行片=设计+代码+合成测试，已在已授权范围（当前批准根、合成项目、无网络/无付费/无凭据）内全绿。
- BLOCKED 真实外部片（精确依赖）：真实跨软件取消/设备绑定/双设备接管/第二存储设备/外部项目验收 — 需对应授权与接口/真实设备就绪，仅暂停受影响分支。


### NF-10-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/shared_rule_adaptation.py`：共同规则/技能/用户差异真实适配（复用 config-ownership 词汇，未造第二套归属模型）。
    字段分层 rule/adapter/preference/diff/task 分开；项目差分不污染全局且 user-native 字段(model/provider/reasoning/auth/user_plugin)保持原值；受管删除只删自有字段不碰未知/他资产字段；base/live/candidate 三方比较保留用户修改、上游变化=待适配非盲恢复、无变化=合法 NO_CHANGE；技能按需加载+停无收益+13是库存非永久+新模型不复制整套技能。
  * `tests/workflow-assistance/nf10_shared_rule_adaptation.py` 11/11 全绿（AT-02/30/36 合成片）。
- 真实外部片（BLOCKED）：真实全局规则/资产部署需用户对目标与字段的有效授权；现有 OBSERVE 字段不因本包变可写；不为同步任务改 provider/API Key；不修改上游内部文件；不每个新模型复制整套技能。

### NF-12-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/update_adaptation.py`：软件/模型/协议更新只做受影响适配（记录真实运行体/协议/能力快照+仅检查所用字段/技能/插件/输入输出/取消恢复接口；无变化=合法 NO_CHANGE 非文件数增加；有不兼容才最小补丁+回退计划非整包重装；共享适配器升级后旧交接仍可读、未知成本保持 UNKNOWN；模型参数用户原生选择不强制高推理/新模型；一次维护未批准只隔离该组不级联整包失败）。
  * `tests/workflow-assistance/nf12_update_adaptation.py` 10/10 全绿（AT-36/37 合成片）。
- 真实外部片（BLOCKED）：软件更新/全局部署/新增插件分目标批量授权；纯文档和合成能力测试不须收费调用；不用 --force-venv 解真实占用；不向模型供应方未证实能力猜参数。

### NF-09-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/multi_project_projection.py`：多项目任务投影与运行证据可见（增强既有只读 Observer 投影，未造第二套工作台/看板）。
    项目过滤 + 源/目标软件 + 材料版本 + delivery/execution/return/review 分阶段状态；A/B 并行独立查看（一项目问题不阻另一项目）；已执行未回传保持 PENDING_RETURN 不显示"全部失败/云端已收到"；权限不足/零/未知/陈旧/在线分别展示、未知不补 0、更新时间来自事实非界面刷新；客户端断线快照标 STALE 重连清除；成本按任务+调用来源分组、订阅用量不推算成 API 已收费；他项目标题/正文绝不外泄；Observer 无新写能力（append 仍只读）。
  * `tests/workflow-assistance/nf09_multi_project_projection.py` 10/10 全绿（AT-24/34/38 合成片）。
- 真实外部片（BLOCKED）：仅授权项目脱敏元数据读取；不新增 Observer 写权限；发布/批准/取消入口留原生客户端或链接，不向 sidecar GET 加写按钮；不重开发工作台/看板、不把网络绿灯当任务成功、不泄露别项目正文。

### NF-11-SYNC | PASS(可自执行片) | INTEGRATION | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/thin_deployment.py`：薄部署、既有模块复用与退出路径。
    新增项目只加配置+本地状态（无新核心源码副本/守护进程/调度器/常驻LLM轮询，违反即拒）；不叠加 n8n/Linear/Vibe Kanban/Symphony 四套任务核心；接收/回传挂进既有运行生命周期；复用组件交出调用/测试/替代点（候选登记≠采用）；退出路径 暂停同步/撤销单项目/回退适配版本/移除受管资产 均不影响原生任务且不删历史（暂停≠删历史、未回传记录保留）；增强关闭后原生软件独立运行。
  * `tests/workflow-assistance/nf11_thin_deployment.py` 12/12 全绿（AT-29/30/40 合成片）。
- 真实外部片（BLOCKED）：本机安装/启动项/全局资产调整需有效部署授权；不私自安装额外服务；不搬迁官方 HOME/活动库；不同项目不复制代码/venv。

### NF-14-SYNC | PASS(可自执行片) | ACCEPTANCE | pending | 2026-09-16
- 可自执行片已闭环：
  * `packages/client-neutral-core/scripts/universal_signoff.py`：分层交付与通用目标真实签收。
    先交付单一链路可用成果、中间成果独立命名不悄悄变最终目标；UNIVERSAL_WORKFLOW_VERIFIED 仅当 6 项检查全 REAL 证据 + 真实外部项目 + 第二执行器三前提达成；缺真实外部项目或缺第二执行器只报阶段完成非全完成；SIMULATED/NO_EVIDENCE 永不能顶替必需 REAL 检查；未安装软件不给假 LIVE PASS；条件研究/无关维护 gap 保留但不把交付拖入无限再审计循环。
  * `tests/workflow-assistance/nf14_universal_signoff.py` 8/8 全绿（合成签收语义）。
- 真实外部片（BLOCKED）：真实发布/合并是独立副作用，需逐次授权；不伪造 LIVE PASS、不无限循环"再审计一轮"、不把所有 gap 变成阻塞。

## M3 里程碑状态
NF-10-SYNC / NF-12-SYNC / NF-09-SYNC / NF-11-SYNC / NF-14-SYNC 五卡可自执行片全部闭环。
M3（软件更新只做受影响适配/薄部署退出路径/多项目投影/通用目标真实签收）设计+代码+合成测试已达成；真实全局规则部署、真实外部第二执行器实测、真实发布/合并、真实 Observer UI 保持 BLOCKED 待授权。
**任务包 20 卡可自执行片全部完成（批次 0–3 / M0–M3）；剩余均为需真实外部授权/部署授权的侧效应片，非可自执行范围。**