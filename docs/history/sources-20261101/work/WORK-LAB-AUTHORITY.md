# WORK-LAB TOP-LEVEL AUTHORITY

**Authority ID:** `WORK-LAB-AUTHORITY-20261019-CONVERGENCE`
**Repository:** `DTALEX66/WORK-LAB`
**Authority level:** TOP / NORMATIVE
**Decision:** 用户2026-10-19冻结其他任务，以《WORK-LAB 权威收敛任务包（2026-10-19）》为当前权威与闭环目标，更新项目权威与规划；未来能力暂时冻结和延后。UI优先任务包不再独立派工。
**Document delivery is not implementation:** 上轮只做权威/路线图/索引/交接与来源登记。用户2026-10-19指令“执行所有未完成的任务，按照最新发你的任务包”作为具体Task Grant，交付了唯一一个真实最小问题闭环`WORK-LAB-MINIMAL-LOOP-001`（产品修复一处：Hermes适配器不再声明未实现的`resume`；能力门转绿、12+49回归测试、适配器层读回；方案`SOLUTION-001`）。其余产品实现仍NOT_EXECUTED；未提交、未跑exact-SHA CI、未提交AAOS候选。

## 1. Current authority and bootstrap

每次审计/执行先动态读取origin/main精确commit/tree，再读本文件、`.project/governance/project-authority-index.json`、AGENTS.md、
`.project/governance/taskpack-authority-index.json`指向的唯一CURRENT、`taskpacks/current/OPEN-TASK-REGISTER.md`及作用域机器合同。
优先级：最新明确用户决定 > 本文件 > project-authority-index > CURRENT/OPEN > AGENTS及作用域合同 > exact-SHA代码/CI/运行读回 > 冻结历史。
当前计划：`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`；当前路线图：
`docs/current/authority-convergence-20261019/ROADMAP.md`。除该收敛任务外，其他任务一律冻结、不派工。
历史记录只在具体问题需要时读取；缺引用报告AUTHORITY_REFERENCE_MISSING，不从历史拼造新权威。

## 2. Product identity and boundaries

WORK-LAB（工作流实验室 / Workflow Lab）是面向个人AI工作环境的、客户端中立的**工作流管理、治理、运行监测与问题闭环系统**。
它连接和管理用户使用的AI Agent、开发工具、工作流软件、模型服务、插件及相关运行环境；持续收集已接入系统的状态与异常，
汇总重复问题和阻塞，生成解决建议或可交给现有Agent的修复任务包/提示词，跟踪修复结果，将经过验证的解决方案固化为可复用的维护方案；
有长期价值的经验形成知识候选，提交AAOS正式审核与接收。

**WORK-LAB不是Agent、不是通用Agent Runtime、不是模型网关、不是通用聊天客户端，也不是所有项目的统一专业审计官。**
它不替代Codex、Claude Code、Qoder、WorkBuddy等工具执行实际开发与故障修复；它负责发现、归并、解释、协调、跟踪和复用问题解决过程。
它不接管DESIGN-LAB的专业视觉判断，不取代AAOS的正式知识真源，不强制所有工作创建/派发/审批。

核心职责：
1. **工作流管理与治理**：维护归属WORK-LAB的通用规则、任务状态、受管配置、权限/预算策略、软件与Adapter登记；只改明确受管字段，不覆盖未知配置或原生认证。
2. **监测与告警**：观察已接入客户端、Agent、CI、工作流、服务和工具的可用性、失败、阻塞、版本变化及可读取的资源信号；显示来源、时间、新鲜度和UNKNOWN。
3. **问题汇总**：去重和关联重复告警，汇总项目、软件/版本、时间、影响、日志片段、错误码、复现条件、已尝试方案和相关任务。
4. **解决建议与Agent任务包**：优先检索已验证方案；否则生成含证据、范围、风险、禁止操作、测试与验收条件的修复提示词/任务包。真实接口未接通时提供人工复制交接，不得伪称自动派发。
5. **修复跟踪与验证**：区分待处理、已交接、处理中、待验证、修复失败、已解决、已固化；依据测试、运行读回和实际结果验证，不凭Agent自述、HTTP 200或单一退出码判定成功。
6. **方案固化与知识候选**：成功修复后记录根因、软件/版本、适用条件、步骤、验证证据、失效条件和回滚方法；精选有复用价值的经验提交AAOS。
7. **界面**：提供概览、问题/告警、软件/Agent/集成状态、修复队列、解决方案库、可获取的成本/资源、系统诊断和日志；Observer只读，写操作必须经过独立授权的Control。

AAOS拥有完整知识生命周期、人的知识工作/研究/学习、AI学习资产、人机双向学习和长期项目记忆，并保留知识审核、分类、接收与状态决定权。
DESIGN-LAB拥有全品类专业设计、原生作品、设计专用内核及专业验收。Open Design客户端与DESIGN-LAB项目是不同身份。
WORK-LAB只提交知识候选并读取AAOS返回状态，不直接写入或伪造可信知识。
三方独立运行与发布，通过版本化API/Schema/Manifest/Receipt/Candidate按需协作；不共享私有业务数据库，不建总控制器或本地知识/学习/课件主库。
本仓开发TaskLedger/单写者/门禁不自动成为被观察业务项目的使用义务。

## 3. Current scope and freeze

用户2026-10-19的决定是当前最高依据：其他任务冻结，本收敛包为唯一当前权威与闭环目标；未来能力暂时冻结和延期延后。
当前范围只包含：
1. 权威定位、职责边界和路线图收敛；
2. 记录真实基线（分支、HEAD、dirty、Authority/索引/唯一账本）；
3. 建立定位冲突矩阵、当前能力映射和未来能力清单；
4. 复用现有唯一任务账本与编号，不建第二份任务真相；
5. 把“一个真实最小问题闭环”列为当前主线第一项；用户2026-10-19指令已作为Task Grant交付`WORK-LAB-MINIMAL-LOOP-001`（实现卡与`SOLUTION-001`），其余任务仍冻结。

当前主线的问题闭环是：
`发现 → 去重/关联 → 问题摘要 → 匹配历史方案 → 建议或Agent修复任务包 → 用户/授权策略交接 → Agent实际修复 → 测试与运行读回 → 关闭或继续 → 方案固化 → 必要时AAOS知识候选`。
必须分别记录发现、分析、建议生成、已交接、Agent声称完成、技术验证通过、方案固化、候选提交、AAOS接收/审核；不能统一成一个“完成”状态。

已冻结、不再独立派工：WUI-00..WUI-21及OPEN账本中的其他任务、`WORK-LAB-UI-PRIORITY-TASKPACK-20261009`（SUPERSEDED_20261019）、
旧蓝图/Atlas/ORCA/Qoder等历史计划。冻结不等于关闭，既有状态、证据和原缺陷保留；不得无证改为完成。
UI代码、HUD融合、新页面、新Agent/Runtime、全自动多Agent编排、模型网关、跨项目记忆/会话联邦等均不在当前范围。
手机端仍不作为当前目标，不新建手机端任务；桌面main与既有compact HUD保留，HUD不是手机端。
React/TS/Vite + Tauri/Rust + Python + JSON Schema分工不换栈；无全仓Rust重写、第二UI/运行时/TaskLedger/Usage真源。
有效已实现功能与安全门保留；文档更新不等于产品完成。

## 4. Runtime and data truth

项目身份支持非Git、多目录/worktree及同名；参与软件集合及工作/健康/观测三轴不混。
断连不推出软件停止，无日志不判失败，turn_end不判项目完成；源/接收/可见时间、序列及last-good有明确限制。
默认最小字段白名单，不采集私人提示词/回复/工具载荷/完整子Agent轨迹；诊断按项目/问题/时间/保留范围授权。
Token/Credits/费用/额度/资源分开，真实0/缺失/不可计算分开；字段精度/完整性、增量累计/修订/重试fork去重守恒。
缓存输入占比按完整同口径总分子/总分母，请求命中率按可判断请求；缓存写入不是读命中，不造全局覆盖率。
受管软件仍遵守五维底线：官方唯一入口、GUI桌面可达、官方基准+声明overlay、按需精简不阻塞、用户原生任务级模型选择。
常态观测不调用LLM；单适配器故障局部，窗口/采集/原生软件生命周期分开。
UNKNOWN不等于正常/零，STALE不等于LIVE；Agent声称完成不等于验证通过，修复通过不等于方案已固化，候选提交不等于AAOS已接收。
所有状态必须有来源、时间、版本和证据范围；没有数据时写UNKNOWN，不用假数据冒充接通。

## 5. Module, write and safety boundaries

规范模块由`.project/governance/module-ownership.json`确定：packages/client-neutral-core与apps/observer。
services/integrations/config/apps/token-monitor/scripts/tests是支撑面；现有Control服务不是新运行时。
一个write set一个writer，保护dirty修改；并行writer需要隔离worktree，跨模块按明确任务合同。
所有缓存/临时环境/日志在`.project-local/runs`，证据在`.project-local/artifacts`，持久文档在仓库声明位置。
Record原料根只读；E/F无exact path+operation授权禁止任何访问。不得读/打印/复制凭据、.env、认证库、私人session/memory。
不reset --hard/clean/force push/改Git历史，不擅自升级安装/改PATH/ACL/服务/全局配置或删除资产。
只管理声明字段，preserve_unknown=true；软件版本/路径/模型/CI动态核对，不把旧固定数字当现场事实。
Observer与sidecar严格只读，不执行/apply/rollback/批准/重试或写业务状态；正常搜索筛选复制展开可用。
获准配置/资产写复用既有独立Control边界，服务端检查主体、范围、前态、版本、幂等、原生读回和恢复。
只修改WORK-LAB；不修改DESIGN-LAB/AAOS仓库或其内部状态，不覆盖未提交改动。

## 6. Evidence, archive and delivery

证据等级NO_EVIDENCE/SIMULATED/SYNTHETIC/INTEGRATED/REAL；REAL需可核验身份、摘要/句柄、producer、observedAt与读回。
实现、受控测试、真实客户端、Windows/Tauri、人工专业接受、发布分别报告；build≠runtime、fixture≠REAL、push≠merge、merge≠installed。
必要fail/missing/skip/cancel不PASS。UNKNOWN不是0。技术通过不等于知识可信、设计接受、真人学会或工作效果。
旧任务逐行保留ID/状态/证据，并账不代表实现完成；无用旧规划冻结归档，不继续派工。原缺陷/失败不清零。
原字节快照：`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/FROZEN-MANIFEST.json`；任务处置：`docs/history/archive/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json`。
本轮来源包：`docs/history/owner-inputs/20261019/WORK-LAB_权威收敛任务包_20261019.zip`（`WL-REC-0105`），原件完整归档，不执行包内任何程序。
不可变来源不改字节；更正旁置；有消费者的旧路径保留非执行兼容入口。
本轮已按用户2026-10-19 Task Grant交付唯一一个真实最小问题闭环（ML-001，产品修复一处，方案`SOLUTION-001`）；其余产品实现NOT_EXECUTED。下一Agent仅按其具体用户Task Grant推进。
commit/push/PR/merge/release/安装/全局/跨项目/付费/发送分别判断；验证不自动授予这些权限。
main仍是唯一永久代码权威；正常短分支→PR→exact-SHA CI→review→merge，禁止直推绕过门禁。
