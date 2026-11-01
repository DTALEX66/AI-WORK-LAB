# WORK-LAB 权威收敛报告（2026-10-19）

## 0. 结论

**PASS（按本轮任务包范围）**：权威/路线图/文档收敛与**一个真实最小问题闭环**均已交付。
闭环对象为 `WORK-LAB-MINIMAL-LOOP-001`（Hermes 适配器声明了没有实现的能力 `resume`），
修复为真实产品代码（`services/execution-federation/hermes_adapter.py`），验证为能力门转绿、
12+49 项回归测试与适配器层真实读回；方案已固化为
`docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md`。
包内 10 项验收标准全部覆盖（逐项见 §12）。

以下状态**不因本轮 PASS 而合并或提前**：exact-SHA CI 未运行（改动未提交），AAOS 候选未提交
（无已接通 API，且提交≠接收），问题中心/解决方案库作为**系统能力**仍是 NOT_IMPLEMENTED——
本轮交付的是其中一条真实闭环，不是这些模块的整体实现。

权威依据：用户 2026-10-19 明确决定“其他任务冻结，以这份任务为当前权威与闭环目标（更新项目内的权威和规划），
未来能力暂时冻结和延期延后”，以及 `docs/history/owner-inputs/20261019/WORK-LAB_权威收敛任务包_20261019.zip`
（`WL-REC-0105`，SHA-256 `36a2614dff217c1f9ad96838ba0304ac3d734e23ad9ebb3e86bb00e2114be2a0`）。

## 1. 仓库基线（编辑前）

| 项 | 值 |
| --- | --- |
| 分支 | docs/handoff-20261018-qoder（分支名，非仓库路径） |
| HEAD | `0369d349d46b75c7048b884331bb40a0f42d4e34` |
| HEAD tree | `d2a0222992f0171e0fc999dd6bb032ccbd40ed1f` |
| `origin/main` | `f6077d18cfc76d588d9315ec0ac82769c3009d9a` |
| `origin/main` tree | `6dcb2094ffa5fdb693e959de5aaa870eea8b1f78` |
| HEAD 与 `origin/main` | HEAD 领先 1 个提交，`f6077d18` 是 HEAD 的祖先 |
| dirty 状态 | 编辑前 59 个 porcelain 条目；含 4 个受保护的并行写者文件 |
| 顶层人类权威 | `WORK-LAB-AUTHORITY.md` |
| 顶层机器权威 | `.project/governance/project-authority-index.json` |
| 作用域任务权威 | `.project/governance/taskpack-authority-index.json` |
| 唯一开放任务账本 | `taskpacks/current/OPEN-TASK-REGISTER.md` |

受保护、未修改的 4 个并行写者文件：`AGENTS.md`、`config/adapter-registry.json`、
`config/client-evidence.json`、`taskpacks/current/error-ledger.json`。
工作树中另有先前 WUI/HUD 未提交改动；本任务没有回退、覆盖或提交它们。
测量时还发现暂存区已含先前 WUI/HUD 改动（不是本任务产生）；本任务只用显式路径追加自己的文件，
没有 `git reset`/取消暂存任何既有条目，也没有 commit。

## 2. 正式定位

WORK-LAB（工作流实验室 / Workflow Lab）是面向个人 AI 工作环境的、客户端中立的
**工作流管理、治理、运行监测与问题闭环系统**。它连接和管理用户使用的 AI Agent、开发工具、
工作流软件、模型服务、插件及相关运行环境；发现和汇总问题，生成解决建议或可交给现有 Agent
的修复任务包/提示词，跟踪验证修复结果，固化可复用解决方案，并把有长期价值的知识候选提交 AAOS
正式审核与接收。

**明确非目标：** WORK-LAB 不是 Agent、不是通用 Agent Runtime、不是模型网关、不是通用聊天客户端，
也不是所有项目的统一专业审计官。它不替代 Codex、Claude Code、Qoder、WorkBuddy 执行实际开发与故障修复；
不接管 DESIGN-LAB 的专业视觉判断；不取代 AAOS 的正式知识真源；不强制所有任务经过 WORK-LAB。

权威落点：`WORK-LAB-AUTHORITY.md` §2；机器索引 `.project/governance/project-authority-index.json`；
路线图 `docs/current/authority-convergence-20261019/ROADMAP.md`。

## 3. 定位冲突矩阵

| # | 旧表述/位置 | 结论 | 理由 | 影响文件/处理 |
| --- | --- | --- | --- | --- |
| 1 | `README.md`：“AI工作观测与配置治理工作台” | AMEND | 只描述观测/配置，缺少问题闭环、修复协作、方案固化与 AAOS 候选出口 | `README.md` 首屏改为新定位并指向新 CURRENT |
| 2 | `WORK-LAB-AUTHORITY.md` §2：观测/配置治理工作台；§3：UI-first current scope | AMEND | 产品本体与当前范围被 2026-10-19 决定取代；UI 不再优先 | 重写 §2/§3，保留 §4-§6 的数据真值、模块、安全和证据规则 |
| 3 | `.project/governance/project-authority-index.json`：`authorityId=...UI-PRIORITY`、`uiFirst=true` | AMEND | 机器权威必须与人类权威同一切换 | 新 `authorityId`、新 CURRENT、新 `currentDecision`，保留历史决定 |
| 4 | `.project/governance/taskpack-authority-index.json`：UI 包为唯一 CURRENT | AMEND | 单一 CURRENT 需要切换；旧包保留为 SUPERSEDED | UI 包移入 `SUPERSEDED`，新收敛包进入 `CURRENT` |
| 5 | `taskpacks/history/pre-convergence-20261019/WORK-LAB-UI-PRIORITY-TASKPACK-20261009.md`：自称唯一 CURRENT、UI-first | FREEZE / SUPERSEDED | 不删除历史，但不能继续派工；未完成 WUI 行不因冻结关闭 | 文件保留，顶部加 SUPERSEDED/FROZEN 提示 |
| 6 | `taskpacks/current/OPEN-TASK-REGISTER.md`：2026-10-09 UI 优先切换、唯一 CURRENT 指向 UI 包 | AMEND（仅表头）/ FREEZE（行） | 账本必须指向新 CURRENT；历史行与证据保留，不无证关闭 | 表头改为 2026-10-19 冻结与新 CURRENT；WUI 行原样保留 |
| 7 | `taskpacks/current/README.md`：唯一 CURRENT 指向 UI 包 | AMEND | 目录入口会误导新会话 | 改为新 CURRENT + 冻结说明 |
| 8 | `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 NEXT-AGENT-PROMPT）：UI 后续交接 | FREEZE / SUPERSEDED | 稳定入口仍指向 UI 任务，需显式失效 | 顶部加冻结横幅并指向新 CURRENT |
| 9 | `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 HANDOFF-20261018-QODER-SESSION）：UI 轮次交接 | FREEZE | 历史交接保留，但不能再作为当前指令 | 顶部加冻结横幅 |
| 10 | `docs/current/workflow-assistance/workflow/active-authority-index.md`：2026-10-09 UI 范围切换 | AMEND | 导航索引不是第二权威，但必须指向当前权威 | 顶部范围说明改为 2026-10-19 |
| 11 | `docs/current/DOCUMENT-CENSUS.md`：UI 当前任务与交接 | AMEND | 文档总索引需要反映新 CURRENT；旧计数仍是其日期快照 | 顶部加 2026-10-19 增量说明，不改旧盘点数字 |
| 12 | `docs/decisions/PROJECT_POSITIONING.md`：2026-10-09 定位 | AMEND | 决策记录是常见入口，必须与顶层权威一致 | 重写为 2026-10-19 收敛定位 |
| 13 | `docs/current/workflow-assistance/workflow/project-definition.md`：2026-10-09 产品定位补充、UI 优先 | AMEND | 作用域定义需要与顶层权威一致；其“非 Agent/非模型网关”边界保留 | 更新定位段落与 UI 状态，保留 Observer/Control/三方边界 |
| 14 | `docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`：超级入口、LAB Router、Agent 调度/执行大脑 | RETIRE（作为产品目标）/ FREEZE（文件） | 与“不是 Agent/Runtime、不是第四产品入口、不做复杂自主编排”的定位冲突；历史研究保留 | 顶部加冻结横幅，不删除原文 |
| 15 | `docs/future/WORK-LAB-BLUEPRINT-20261006.md`：完整未来蓝图 | FREEZE | 已有 FROZEN_ARCHIVED 标记；历史依据，非当前派工 | 不改正文；由新路线图取代其未来范围 |
| 16 | `AGENTS.md`：workflow-assistance 范围、受管客户端与五维底线；第 12 行仍写“唯一CURRENT是 UI 包，UI 优先” | KEEP（规则）/ OWNER DECISION（第 12 行） | 执行规则、模块、安全和五维底线仍有效；第 12 行与 2026-10-19 决定冲突，但该文件是受保护的并行写者文件 | 本任务不修改该文件；机器权威与 verifier 已指向收敛包。建议 owner 授权后把第 12 行改为收敛包 |
| 17 | `docs/history/**`、`taskpacks/history/**`：旧任务/审计/交接 | FREEZE | 冻结历史只作来源，不得据名称重新派工 | 不修改；需要时点名读取 |
| 18 | WUI 报告（含 `docs/history/archive/ui-priority-20261009/WUI-19-FINAL-ACCEPTANCE-20261012.md`） | FREEZE | 记录的是过去轮次与证据；冻结不改写历史字节 | 不修改；其未完成项保持原状态 |
| 19 | HUD 融合/紧凑 HUD 扩展方向 | FREEZE（产品方向） | 既有 HUD 是桌面观测面，可保留；新融合扩展不属于当前问题闭环 | 不新增 HUD 功能；既有代码与测试保留 |
| 20 | 手机端相关表述 | KEEP（不做）/ 不再新建任务 | 2026-10-09 决定仍有效；新包未要求手机端 | 不新建手机端延后/冻结任务 |
| 21 | `docs/current/workflow-assistance-README.md`、`docs/current/workflow-assistance/workflow/codex-global-enhancement.md` 的“非 Runtime/非模型网关”边界 | KEEP | 与新定位兼容，且是重要的反向边界 | 不改正文；由顶层权威统一表述 |
| 22 | `services/memory`、`services/session-federation` 的跨项目记忆/会话联邦能力 | DEFER | 新路线图明确延期研究，不承诺实施 | 保留代码与历史，不将其作为当前前置 |
| 23 | `.agents/skills/work-lab-workflow/SKILL.md`（源 `projections/agents/source/work-lab-workflow/SKILL.md`）：仍把 UI 包写成 current taskpack，产品描述停留在旧定位 | AMEND | 这是新会话默认读取的技能；陈旧的默认材料会让新会话直接继承错误的 CURRENT | 更新源文件的定位、问题闭环、验证范围与冻结规则，运行 `projections/agents/generate.py` 重生成投影，并用 canonical generator 修正 `config/skills-inventory.json` 的 8 条陈旧哈希 |
| 24 | 根目录 6 份历史文档的 disposition banner：权威链仍写 UI 包为 CURRENT | AMEND（仅 banner） | `scripts/ci/verify_root_document_dispositions.py` 实测 6 条 `STALE_POINTER`，新会话读根文件时会看到错误 CURRENT；正文必须保持逐字不变 | 仅改 banner 的权威链并注明 UI 包已 SUPERSEDED/FROZEN；正文与 BEGIN/END 之外字节未动，verifier 与 16 项测试通过 |
| 25 | `scripts/audit/normalise_doc_citations.py` 的默认加载 scope：第 5 步仍写 UI 包，并保留两份已冻结的 UI 入口文档 | AMEND | 该工具自己声明 scope 是 auditBootstrap 的读取顺序；权威切换后它仍在检查一份已 SUPERSEDED 的包，而真正的 CURRENT 任务包与收敛报告/路线图没有被检查 | scope 改为收敛任务包 + 本报告/路线图；删除只被旧 UI 文档使用的一条包内文件允许项（`SOURCE_BASELINE`，不带扩展名，避免再次成为引用）；把 verifier 输出字面量 `OPEN-TASK-REGISTER.md` 登记为不可改写；实测 `docs=9 citations=862 rewritten=0 blocked=0`，9 项测试通过 |
| 26 | `docs/history/archive/ui-priority-20261009/TASK-BREAKDOWN.json`：`currentTaskpack` 仍为 UI 包（无 banner 的 JSON 历史字段） | FREEZE / NON-NORMATIVE | 它是 UI 轮次的机器可读拆解，不是治理索引；改写历史 JSON 会破坏其日期证据 | 不修改；当前权威只由 `.project/governance/taskpack-authority-index.json` 决定 |

## 4. 当前能力映射（2026-10-19 只读核对）

| 能力 | 现状 | 证据 | 缺口 |
| --- | --- | --- | --- |
| 监测数据源 | PARTIAL：仓内有有界 collector、Snapshot v3 和只读 Observer；未证明所有受管客户端端到端 LIVE | `packages/client-neutral-core/scripts/collectors.py`（`collect_task_ledger`、`collect_git_ci`、`collect_usage_files`、`collect_source_quality`、`collect_growth_watcher`）；`packages/client-neutral-core/scripts/snapshot_api.py` 的 `SNAPSHOT_SCHEMA_VERSION = "workflow/snapshot/v3"`；`.project-local/runs/authority-convergence-20261019/collectors.txt`、`snapshot-version.txt` | 未证明每个 Adapter 的真实采集/新鲜度；无统一的 source/freshness 面板；采集失败与 UNKNOWN 的端到端呈现未验证 |
| 问题中心 | NOT_IMPLEMENTED | 对 `services`、`integrations`、`packages/client-neutral-core`、`apps/observer/frontend/src` 检索 `issue[_-]?center|IssueCenter|问题中心`，命中 0；`.project-local/runs/authority-convergence-20261019/issue-center-hits.txt` | 没有问题 ID、去重、分类、优先级、项目/软件/版本关联、日志片段、处理状态或 UI |
| 修复任务包 | PARTIAL：有通用 TaskPack runner、任务协议和账本；本轮人工交付了一份真实修复交接卡 | `services/orchestration/run_taskpack_agent.py`；`services/task-governance/task_protocol.py`；`packages/client-neutral-core/scripts/task_ledger.py`；`.project-local/runs/authority-convergence-20261019/minimal-loop-candidate-acp-hermes-resume-20261019.md`；`docs/current/authority-convergence-20261019/implementation/WORK-LAB-MINIMAL-LOOP-001-ACP-HERMES-RESUME.md` | issue→repair 的自动生成器仍不存在；本轮交接是人工写出的，不是产品功能 |
| 修复验证 | PARTIAL：有完成权威、证据聚合和 CI 门；本轮第一次把真实修复接到可重跑的验证与读回 | `services/task-governance/completion_authority.py`；`services/receipts/evidence_aggregator.py`；`services/receipts/execution_evidence.py`；`.project-local/artifacts/authority-convergence-20261019/minimal-loop/01..04` | 待处理/已交接/处理中/待验证/失败/已解决/已固化的产品状态机仍不存在；本轮状态记在实现卡与方案记录里 |
| 解决方案库 | NOT_IMPLEMENTED（系统能力）/ 首条记录已存在 | 检索 `solution[_-]?library|SolutionLibrary|解决方案库` 命中 0；`docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md` | 无方案 schema 的机器实现、检索与复验；第一条记录是文件，不是可查询的库 |
| AAOS 候选出口 | CONTRACT_ONLY | `integrations/archeaxis/contracts/promotion_contract.py`（`KnowledgeCandidate`、`ArcheAxisHandoffEnvelope`、`export_permission` 默认拒绝）；`services/knowledge/promotion_gate.py`；`services/knowledge/BOUNDARY.md`；`.project-local/runs/authority-convergence-20261019/aaos-contracts.txt` | 没有 AAOS API 客户端/提交回执/接收状态读回；未提交任何候选；AAOS 的正式审核与接收权未变 |
| Control / Observer 分离 | SCAFFOLD | `services/control/control_service.py`（loopback 写边界）；`scripts/ci/verify_observer_readonly.py`；`scripts/ci/verify_observer_readonly_boundary.py` | 问题/修复生命周期尚无 Control 写路径；本次未新增任何写操作 |
| 真实最小闭环 | DELIVERED（`WORK-LAB-MINIMAL-LOOP-001`，适配器层验证） | `scripts/ci/verify_acp_adapter_honesty.py` 从红转绿；`services/execution-federation/hermes_adapter.py` 实改；`.../minimal-loop/01..04` 四份收据；实现卡与 `SOLUTION-001` | 闭环的“发现”来源是仓内 AG-06 能力门（真实、可复现），不是外部已接入客户端；Hermes 原生会话恢复仍不存在，也未被声称存在 |

“命中 0”是上述作用域内的只读检索结果；它证明这些作用域里没有同名实现，不代表所有历史资料或外部项目中不存在相关讨论。

## 5. 路线图收敛结果

完整清单见 `docs/current/authority-convergence-20261019/ROADMAP.md`：

- **CURRENT（9 项）**：权威收敛、真实数据源与诚实 Observer 状态、问题中心、问题摘要/Agent 修复任务包、
  修复跟踪与验证、解决方案库、AAOS 候选出口、Control/Observer 分离、一个真实最小闭环。
  第 9 项已由 2026-10-19 用户指令（“执行所有未完成的任务，按照最新发你的任务包”）作为具体 Task Grant
  交付：`WORK-LAB-MINIMAL-LOOP-001` 完成发现→摘要→历史匹配→交接→修复→验证→固化。
  第 2-8 项仍只是该闭环中被用到或被指出的能力面；它们作为**系统能力**没有获得整体实施授权。
- **NEXT**：更多连接器、聚类与历史检索、受限低风险自动化、方案过期/版本适用性/回归复验、
  真实可获取的成本/Token/资源汇总。
- **FROZEN**：新 Agent/Runtime 框架、全自动多 Agent 编排、大规模插件/MCP/模型/数据库安装、
  全局自动改写配置、重型多租户/Kubernetes、私人会话自动采集、WUI 后续实施。
- **DEFERRED**：跨项目/跨软件长期记忆与会话联邦、复杂跨客户端恢复、广泛高风险自动派发/修复、
  第二套知识真源、企业级部署、全软件实时深度监测。
- **RETIRED**：WORK-LAB 作为 Agent/通用聊天产品、作为全项目专业审计官、以数量证明进度、
  以假数据/自述/HTTP 200/单一退出码伪造成功、超级入口/Command Center/LAB Router 作为执行大脑。
- **解冻门槛**：最小闭环稳定 + 明确用户场景 + 合法接口/权限 + 风险可控 + 维护成本合理 +
  独立验收 + 用户批准；先做小范围试验，未达净收益即停止。

## 6. 来源登记与冻结处理

- 新来源包已登记为 `WL-REC-0105`，归档于
  `docs/history/owner-inputs/20261019/WORK-LAB_权威收敛任务包_20261019.zip`（9,459 B，
  SHA-256 `36a2614dff217c1f9ad96838ba0304ac3d734e23ad9ebb3e86bb00e2114be2a0`），包含 5 个成员，
  ZIP 内顶层目录为 `WORK-LAB_权威收敛任务包/`；五个成员均为 `.md`：
  `README`、`TASKPACK`、`AUTHORITY`、`ROADMAP`、`ACCEPTANCE`（包内文件名，不是仓库路径）。
- 登记结果：105 条资料、2,387 条包内成员；源清单 186 个文件（50 归档 / 136 排除 / 0 未决）。
- 包内程序未执行；包内提示和历史验证不额外授予权限。
- WUI 与历史任务没有关闭、没有改状态、没有清零缺陷；只加冻结/失效提示。
- 没有创建第二任务账本；CURRENT 仍由 `.project/governance/taskpack-authority-index.json` 唯一指定。

## 7. 测试报告

以下命令在编辑后的工作树上运行；精确 HEAD 为编辑前 `0369d349d46b75c7048b884331bb40a0f42d4e34`
（本任务未提交，故工作树内容与该提交不同，差异即本报告 §8 的文件）。结构门读取的是工作树/暂存区，
不是一次新的 CI 运行；因此这些结果**不等于** exact-SHA CI。表 24 是适配器层的真实运行读回，
但它证明的是适配器行为，不证明 Hermes 原生进程或桌面界面。

| # | 命令 | 退出码 | 摘要 |
| --- | --- | --- | --- |
| 1 | `python scripts/ci/verify_project_authority_reference.py` | 0 | `AUTHORITY_REFERENCE_PASS top=WORK-LAB-AUTHORITY.md current=WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019 register=OPEN-TASK-REGISTER.md` |
| 2 | `python scripts/ci/verify_authority_index_paths.py` | 0 | `AUTHORITY_INDEX_PATHS_TOTAL targets=58 refs=1376 broken=0 declared_in_row=17 no_tree_claims=10 failed_targets=0` |
| 3 | `python scripts/ci/verify_refs_surface_policies.py` | 0 | `REFS_SURFACE_POLICIES_PASS head=0369d349d46b surfaces=662 refs=4166 external_surfaces=559 external_refs=3327 external_broken_declared=2871 ratchet_surfaces=103 ratchet_baseline=386 ratchet_broken_today=386 new=0 fixed=0 declaration_problems=0` |
| 4 | `python scripts/audit/normalise_doc_citations.py` | 0 | `DOC_CITATIONS CHECKED docs=9 citations=897 rewritten=0 blocked=0 generic_allowed=16 absent_quoted=9 stale_allowances=0`；首次为 `rewritten=2`（窄引用的方案文件名/路线图简写），按门自身提示 `--apply` 规范化后复跑为 0 |
| 5 | `python scripts/ci/verify_register_table_shape.py` | 0 | `REGISTER_TABLE_SHAPE_PASS tables=1 rows=25 wrong_width=0` |
| 6 | `python tests/ci/test_register_table_shape_is_uniform.py` | 0 | `Ran 9 tests` / `OK`（精确时长随运行波动，以收据原文为准）；随后同一 `REGISTER_TABLE_SHAPE_PASS` 行 |
| 7 | `python scripts/maintenance/owner_material_catalog.py build-index` | 0 | `{"status":"PASS","catalogRows":2492}`；重生成 `docs/history/owner-inputs/INDEX.md`、`docs/history/owner-inputs/CATALOG.html` 与两份 CSV 投影 |
| 8 | `python scripts/maintenance/owner_material_catalog.py verify` | 0 | `{"status":"PASS","registeredMaterials":105,"indexedArchiveMembersIncludingNested":2387,"sourceFilesInventoried":186,"relatedSourceFiles":50,"excludedForeignFiles":136,"mixedRelatedMembers":56,"unresolvedSourceFiles":0,"sourceReadback":"NOT_EXECUTED","sourceModified":false,"productImplementation":"NOT_EXECUTED","errors":[]}` |
| 9 | `python scripts/ci/verify_live_doc_paths_resolve.py` | 0（首次 1） | 最终 `LIVE_DOC_PATHS_PASS every live citation resolves`（`LIVE_DOC_PATHS citations=805 missing=0 stale_exceptions=0`）；首次 FAIL 的实测原因是报告把分支名放在反引号中，被 `PATH_RE` 当作 `docs/...` 路径；改为明示“分支名，非仓库路径”后通过 |
| 10 | Python `json.load` on the two governance indexes + `docs/history/owner-inputs/RECORD-ARCHIVE-REGISTER.json` + `docs/history/owner-inputs/RECORD-SOURCE-CENSUS.json` | 0 | 四份 JSON 全部 `JSON_OK` |
| 11 | `git diff --check` / `git diff --cached --check`（仅本任务路径） | 0 / 0 | 无空白错误 |
| 12 | `env PYTHONIOENCODING=utf-8 .project-local/toolchains/wl-py311/Scripts/python.exe tests/workflow-assistance/test_agent_default_material_is_regenerated_and_current.py` | 0 | 完整文件 `Ran 8 tests` / `OK`；`AgentDefaultMaterialTests` 覆盖源→投影字节一致、两次生成幂等、content_hash、必需定位标记、引用路径可解析与 <10KB 预算；`DerivedProjectionDriftTests` 的 PyYAML 依赖缺口由项目解释器闭合，生成后投影字节未变。UTF-8 绑定是命令的一部分：未绑定时该测试调用的 context pack 会因 GBK stdout 无法编码 U+2194 而中止（本轮实测 1 failure） |
| 13 | `python scripts/ci/verify_root_document_dispositions.py` | 0（修复前 1） | 修复前 6 条 `STALE_POINTER`；最终 `ROOT_DISPOSITIONS_PASS root_md=11 authority=2 convention=3 historical=6` |
| 14 | `python tests/workflow-assistance/test_root_document_dispositions.py` | 0 | `Ran 16 tests` / `OK`；含 banner 外正文逐字不变的守卫 |
| 15 | `python tests/workflow-assistance/test_default_load_doc_citations_resolve.py` | 0 | `Ran 9 tests` / `OK`；断言 9 份默认加载文档的 897 条引用全部唯一可解析且无简写 |
| 16 | `python scripts/ci/verify_observer_readonly_boundary.py` | 0 | `OBSERVER_READONLY_PASS runtime=non-GET-denied data_layer=read_only sources_scanned=82` |
| 17 | `python scripts/ci/verify_model_registry_integrity.py` | 0 | `MODEL_REGISTRY_INTEGRITY_PASS providers=9 models=10 runtimes=3 processLibraries=2 externalAssets=0 served_bindings=0` |
| 18 | `python scripts/ci/verify_acp_adapter_honesty.py` | 0（修复前 1） | **修复前**：`DECLARED_CAPABILITY_WITHOUT_IMPLEMENTATION hermes advertises execution capability 'resume' but resume() produced no real effect`（既有失败，非收敛文档轮次引入）。**修复后**：`ACP_HONESTY_PASS executors=5 operations=40 executable=0 native_verified=0`。修复与收据见 #21 |
| 19 | `.project-local/toolchains/wl-py311/Scripts/python.exe scripts/maintenance/owner_material_catalog.py verify --source-root "D:/All projects/Record"` | 1 | **源目录清单漂移，非本任务引入**：`"status": "FAIL"`、`"sourceReadback": "FAIL"`，唯一错误 `Record file inventory drift; reclassify new/missing materials`。仓内归档与成员校验本身通过（见 #8）；失败仅因源目录相对 2026-10-11 快照新增了未分类文件，见 #20。未重分类：新文件属其他项目/UI/AAOS/ASTRYN/调研材料，超出本收敛任务范围，且来源目录归 owner 管辖 |
| 20 | `.project-local/toolchains/wl-py311/Scripts/python.exe .project-local/runs/authority-convergence-20261019/diff_source_census.py` | 0 | 漂移定量（只读诊断）：`snapshotDate 2026-10-11`、`expected 186 actual 204`、`NEW 18`；脚本仅在存在缺失时打印 MISSING 行，本次无该行（0 缺失由 expected/actual/NEW 推出）；新增项含 UI/Backend/ASTRYN 任务包 ZIP、AAOS ZIP、DESIGN-LAB ZIP、若干图片与 `观猹项目调研与三项目增强评估_20261013.md`。2026-10-19 交付包已在 `incrementalAppends` 中登记（`WL-REC-0105`），不属于这 18 项 |
| 21 | `.project-local/toolchains/wl-py311/Scripts/python.exe scripts/ci/verify_acp_adapter_honesty.py`（修复后） | 0 | `ACP_HONESTY_PASS executors=5 operations=40 executable=0 native_verified=0`；收据 `.../minimal-loop/01-acp-honesty.out`。修复前同一命令为 exit 1（#18） |
| 22 | `.project-local/toolchains/wl-py311/Scripts/python.exe tests/workflow-assistance/test_execution_federation.py` | 0 | `Ran 12 tests` / `OK`；收据 `.../minimal-loop/02-federation-tests.out` |
| 23 | `.project-local/toolchains/wl-py311/Scripts/python.exe tests/workflow-assistance/nf22_registry_and_acp_honesty_gates.py` | 0 | `Ran 49 tests` / `OK`；收据 `.../minimal-loop/03-nf22-tests.out` |
| 24 | `.project-local/toolchains/wl-py311/Scripts/python.exe .project-local/runs/authority-convergence-20261019/minimal_loop_readback.py` | 0 | 适配器层真实读回（伪造可启动二进制使 launchable 分支真的执行）：`verdict=PASS`；`supports` 14 项不含 `resume`；`resumeStatus=NOT_SUPPORTED`、`resumeOk=false`；`launchable/resume_absent/non_execution_planes_intact/execution_planes_intact/no_resume_declaration_in_source` 全真；读回适配器 5,697 B、SHA-256 `1735299435b743cc138a97b13b68bfb1c203130ddd6f6ac1427514418d1c3fe4`；收据 `.../minimal-loop/04-readback.out` |

表 1-14 的机器门原始输出与退出码保存在 `.project-local/artifacts/authority-convergence-20261019/gates/`；
机器索引 `.project-local/artifacts/authority-convergence-20261019/gate-receipts.json` 记录 14 个门的命令、
退出码、输出字节数与 SHA-256，并绑定当前 HEAD `0369d349d46b75c7048b884331bb40a0f42d4e34`
（本次实测 14/14 exit 0，`allPass=true`）。另用独立脚本重算 14 份输出的字节数与 SHA-256、逐门比对
`.exit` 与收据退出码：`GATE_RECEIPT_BINDING gates=14 allPass=True problems=0`
（`.project-local/artifacts/authority-convergence-20261019/gates/binding-check.out`）。表 15-20 的附加只读消费者检查单独保存在
`.project-local/artifacts/authority-convergence-20261019/additional/`：15-18 与 20 退出 0（18 为修复后）；
19（外部来源目录清单漂移）为红色，非本任务引入，也不计入 14 门捆绑。表 21-24 是最小闭环的修复与读回收据，
保存在 `.project-local/artifacts/authority-convergence-20261019/minimal-loop/`，四份均退出 0。
除 #24 外，以上是**工作树门禁/测试收据**，不是 exact-SHA CI。

未执行项及原因：

- 完整本地治理套件：按现行约束不跑，CI 是最终裁判；本轮只跑与改动面相关的最小门。
- 真实运行/桌面/Tauri/键盘/DPI：WUI 已冻结，未重新拉起界面，也未把旧字节上的读数当作当前证据。
- 最小闭环的真实采集/修复/回读：已按用户 2026-10-19 指令执行（`WORK-LAB-MINIMAL-LOOP-001`），
  但来源是仓内 AG-06 能力门而非外部客户端采集，验证到适配器层；Hermes 原生进程的真实会话恢复未做。
- AAOS 提交/接收：没有已接通的 AAOS API，未提交；不伪造回执。
- 来源目录新文件的重新分类：`verify --source-root` 已实测（#19），漂移定量为 18 项新增、0 项缺失（#20）；
  这些文件属于其他项目/UI/AAOS/ASTRYN/调研材料，超出本收敛任务范围，来源目录归 owner 管辖，故未改动。
  2026-10-19 交付 ZIP 的 SHA-256 已单独计算并登记（§6）。
- commit/push/PR/merge/release：未执行，等待 owner 明确授权。

## 8. 修改文件清单

（以实际 `git status` 为准；下列为本任务新增或编辑的文件。）

- `WORK-LAB-AUTHORITY.md`
- `.project/governance/project-authority-index.json`
- `.project/governance/taskpack-authority-index.json`
- `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`（新）
- `taskpacks/current/OPEN-TASK-REGISTER.md`（仅表头冻结说明；行保留）
- `taskpacks/current/README.md`
- `taskpacks/history/pre-convergence-20261019/WORK-LAB-UI-PRIORITY-TASKPACK-20261009.md`（仅顶部失效提示）
- `README.md`
- `docs/decisions/PROJECT_POSITIONING.md`
- `docs/current/authority-convergence-20261019/ROADMAP.md`（新）
- `docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md`（新，本文件）
- `docs/current/authority-convergence-20261019/implementation/WORK-LAB-MINIMAL-LOOP-001-ACP-HERMES-RESUME.md`（新，实现卡）
- `docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md`（新，首条方案记录）
- `services/execution-federation/hermes_adapter.py`（**产品修复**：移除未实现的 `Capability.RESUME` 声明，5 行新增/1 行删除）
- `.project-local/runs/authority-convergence-20261019/minimal_loop_readback.py`（新，适配器层读回脚本）
- `.project-local/artifacts/authority-convergence-20261019/minimal-loop/01-acp-honesty.out`、`02-federation-tests.out`、`03-nf22-tests.out`、`04-readback.out`（新，最小闭环收据）
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 NEXT-AGENT-PROMPT）（仅顶部失效提示）
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 HANDOFF-20261018-QODER-SESSION）（仅顶部失效提示）
- `docs/current/workflow-assistance/workflow/active-authority-index.md`（范围说明）
- `docs/current/workflow-assistance/workflow/project-definition.md`（定位补充）
- `docs/current/DOCUMENT-CENSUS.md`（增量说明）
- `docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`（冻结提示）
- `docs/history/owner-inputs/20261019/WORK-LAB_权威收敛任务包_20261019.zip`（新归档）
- `docs/history/owner-inputs/RECORD-ARCHIVE-REGISTER.json`
- `docs/history/owner-inputs/RECORD-ARCHIVE-MEMBERS.jsonl`
- `docs/history/owner-inputs/RECORD-SOURCE-CENSUS.json`
- `scripts/maintenance/owner_material_catalog.py`（仅把生成索引首屏指向新 CURRENT/路线图/报告，并保留 UI 历史交接链接）
- `scripts/audit/normalise_doc_citations.py`（默认加载 scope 从已失效 UI 包切到收敛任务包 + 本报告/路线图；删除不再使用的包内文件允许项；新增 verifier 输出字面量允许项，防止收据被机械改写）
- `projections/agents/source/work-lab-workflow/SKILL.md`（默认技能源：新定位、问题闭环状态分离、当前任务包与冻结规则；版本 1.2.0）
- `.agents/skills/work-lab-workflow/SKILL.md`（由 `projections/agents/generate.py` 重生成，content_hash 已更新）
- `config/skills-inventory.json`（由 `scripts/ci/generate_skills_inventory.py` 重生成：19 条中 8 条陈旧哈希按磁盘/HEAD 实测修正，含本技能新哈希；无技能增删）
- `docs/history/archive/root-ui-records-20261019/ASSET_REPLACEMENT_MANIFEST.md`、`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 HANDOFF-UI-L10B）、`docs/history/archive/root-ui-records-20261019/UI_DECISIONS.md`、`docs/history/archive/root-ui-records-20261019/UI_IMPLEMENTATION_REPORT.md`、`docs/history/archive/root-ui-records-20261019/UI_REFERENCE_MANIFEST.md`、`docs/history/archive/root-ui-records-20261019/VISUAL_QA_REPORT.md`
  （仅 disposition banner 的权威链改指新 CURRENT；正文与 banner 外字节未动，由 verifier 与 16 项测试守卫）
- 由 `scripts/maintenance/owner_material_catalog.py build-index` 生成的 `docs/history/owner-inputs/INDEX.md`、`docs/history/owner-inputs/CATALOG.html`、`docs/history/owner-inputs/RECORD-ARCHIVE-REGISTER.csv`、`docs/history/owner-inputs/RECORD-ARCHIVE-MEMBERS.csv`

未修改：`AGENTS.md`、`config/adapter-registry.json`、`config/client-evidence.json`、
`taskpacks/current/error-ledger.json`；没有修改 DESIGN-LAB/AAOS；没有覆盖任何未提交工作。

**2026-10-19 归档对齐说明**：本表记录的是权威收敛当时的改动。同日按用户指示执行的归档规范化
（54 项 `git mv`，含本表里的 UI 包目录、UI 任务包与六份根级 UI 记录）把它们的最终位置改到
`docs/history/archive/` 与 `taskpacks/history/pre-convergence-20261019/`；本表路径已随之改指。
逐件移动与哈希见 `docs/history/archive/MOVED-PATHS-20261019.json`，任务包侧记录见
`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` §11。

## 9. 风险与回滚

**风险：**

1. 旧消费者若硬编码 UI 任务包路径，会读到已失效的 UI-first 指令；已在该包、交接、README、账本表头加显式提示。
2. 冻结可能让未完成 WUI 项“消失”；已保留全部行、状态与证据，并在路线图写明冻结不等于关闭。
3. 新来源包已加入资料登记与源清单；`--source-root` 复核实测为红色（#19）：源目录相对 2026-10-11 快照新增
   18 个未分类文件、缺失 0（#20）。这些文件属其他项目且来源目录归 owner 管辖，未重分类，因此该项在 owner
   处理前会持续显示 `FAIL`；它不改变仓内归档与成员的校验结果（#8 通过）。
4. 本任务改了一处产品代码（`services/execution-federation/hermes_adapter.py` 的 `RESUME` 声明）。风险是若有调用方依赖
   `supports` 中出现 `resume` 来选择恢复路径——那样的调用方本来就踩在假声明上，能力门判红；
   移除后它们会得到 `NOT_SUPPORTED`，这是如实的降级而非新的失败。适配器其他能力与行为未动。
   文档与索引切换后，必须由下一次 CI 在提交后的 exact SHA 上重新验证，不能把本报告的结构门结果当作 CI 结果。
5. 工作树含先前未提交改动；本任务只在指定文件上追加编辑，未触碰 4 个受保护并行写者文件。
6. `AGENTS.md` 第 12 行仍写“唯一CURRENT是 UI 包，UI 优先”，该文件是受保护的并行写者文件，未修改；
   `docs/history/archive/ui-priority-20261009/TASK-BREAKDOWN.json` 的 `currentTaskpack` 字段与若干已冻结 taskcard
   也保留历史 UI 指向。这些是残留旧口径，不能作为当前权威：新会话须按 `WORK-LAB-AUTHORITY.md` →
   `.project/governance/project-authority-index.json` → 收敛任务包解析；机器 verifier 已通过。
   若要清理 `AGENTS.md` 这一行，需 owner 明确授权后单独修改。

**回滚：**

- 仅回滚本任务的文件到编辑前字节；不使用 `git reset --hard`、`git clean` 或全仓还原。
- 产品修复单独可回滚：在 `services/execution-federation/hermes_adapter.py` 恢复
  `acp.Capability.RESUME,` 一行并移除说明注释；回滚后 AG-06 能力门会回到实测的红色（预期可伪证）。
- 若要恢复 UI-first：把两个治理索引的 CURRENT/decision 指回 UI 包，并移除本任务新增的冻结横幅；
  历史 UI 包本身未被删除，可直接恢复为 current（需 owner 明确决定）。
- 新归档与登记行是追加式；如撤回归档决定，可整组删除 `WL-REC-0105` 记录、5 条成员行和归档 ZIP，
  然后重跑 `build-index` 与 `verify`。

## 10. 状态区分（不得合并）

| 状态 | 本轮结果 |
| --- | --- |
| 权威更新 | DELIVERED：`WORK-LAB-AUTHORITY.md` 与两个治理索引已切换 |
| 代码实现 | DELIVERED：`services/execution-federation/hermes_adapter.py` 移除未实现的 `RESUME` 声明（ML-001） |
| 真实运行验证 | DELIVERED（适配器层）：能力门转绿 + 适配器 launchable 分支真实读回（`resumeStatus=NOT_SUPPORTED`）；未拉起 Observer/Tauri/桌面，也未证明 Hermes 原生恢复 |
| 受控测试 | 见 §7；14 门 + 附加检查 + ML-001 的 12/49 项回归 |
| 方案固化 | DELIVERED：`docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md`（症状/根因/版本/步骤/证据/失效/回滚） |
| AAOS 接收 | NOT_EXECUTED：只有候选合同，没有提交或接收回执；提交≠接收 |
| 任务关闭 | ML-001 关闭；其余任务保持冻结（冻结≠关闭），未无证改状态 |
| exact-SHA CI | NOT_EXECUTED：改动未提交，工作树门禁≠CI |

## 11. 下一步

1. 等待 owner 对本次权威收敛与 ML-001 修复结果的确认；提交/推送由 owner 另行授权。
2. 在提交后的 exact SHA 上运行 CI，确认两个治理索引、来源登记与产品修复在干净检出中同样通过；
   `services/execution-federation/hermes_adapter.py` 的改动必须进入 exact-SHA CI 才算最终验证。
3. 最小闭环已交付（`WORK-LAB-MINIMAL-LOOP-001` / `SOLUTION-001`）。若 owner 要继续，应给出**下一个**
   具体 Task Grant 并选定问题；问题中心/解决方案库作为系统能力仍未被授权整体实施。
4. AAOS 候选仍不提交：没有已接通 API。只有在存在真实接收回执时才能写“AAOS 已接收”，
   不把“已提交”或“本地方案记录”写成接收。
5. 账本派生投影的重发**不需要 owner 授权**，本段原先的说法是错的，已按代码实测改正并执行：
   `scripts/audit/ledger_regression_command_targets.py` 无条件按 `--audit-out`（默认即出厂投影）写出，
   只有账本才受 `--apply` 控制。先只读预览（`changed_existing=0`，新增行只有 ERR-276 与 ERR-277，
   `repointMap`/`handAdjudicated` 未变），再落地重发两份派生审计（投影 274→276、PATH_GONE 36→38、
   `docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json` 的 unboundPass 94→96），受保护账本字节未动。
   本地门实测 `50 passed, 1 failed`：本轮之前 8 项红里的 4 项成因消除，仍属 owner 的是
   ERR-276/277 的 `fixedCommit` 绑定（必须有真实修复提交才可写）、executor registry pin、DSH 日期合同、
   派生审计幂等（2026-10-20 已裁决：那条引用是机器本地普查，见下节；当时未裁决）。

## 12. 包内 10 项验收标准逐项覆盖

| # | 验收标准（任务包原文要点） | 状态 | 落点/证据 |
| --- | --- | --- | --- |
| 1 | 正式定位：工作流管理/治理/监测/问题闭环，客户端中立 | DONE | §2；`WORK-LAB-AUTHORITY.md` §2；`.project/governance/project-authority-index.json` |
| 2 | 明确非目标：不是 Agent/Runtime/模型网关/聊天客户端/全项目审计官 | DONE | §2；`WORK-LAB-AUTHORITY.md` §2；`README.md` |
| 3 | 问题闭环各阶段分别记录，不合并为“完成” | DONE | 实现卡 §6 状态分离；`SOLUTION-001` §9；本报告 §10 |
| 4 | 状态必须诚实：UNKNOWN/STALE/来源/时间/新鲜度，不补 0 | DONE（规则保留）/ 本轮未新增采集 | `WORK-LAB-AUTHORITY.md` §4；Observer 只读门 #16；ML-001 读回不把 `executable=0` 写成可用 |
| 5 | Observer 只读；写经独立授权 Control | DONE（规则与门保留） | `WORK-LAB-AUTHORITY.md` §5；#16 `OBSERVER_READONLY_PASS`；本轮未新增写路径 |
| 6 | AAOS 保留知识审核/接收权，只提交候选并读状态 | DONE（边界保留） | §4 AAOS 行；`services/knowledge/BOUNDARY.md`；本报告 §10 AAOS=NOT_EXECUTED |
| 7 | 跨项目记忆/会话联邦/自主 Agent 协作冻结或延期 | DONE | `docs/current/authority-convergence-20261019/ROADMAP.md` FROZEN/DEFERRED；§3 行 22 |
| 8 | 复用既有唯一账本与编号，不建第二真相；不无证关闭 | DONE | `OPEN-TASK-REGISTER.md` 表头；`SOLUTION-001` 编号；ML-001 有证据关闭 |
| 9 | 不覆盖 dirty、不改 DESIGN-LAB/AAOS、不伪造测试/功能 | DONE | §1 基线与受保护文件；§8 未修改清单；本报告 §7 证据边界 |
| 10 | 优先交付一个真实最小问题闭环 | DONE | ML-001：AG-06 能力门从红转绿、真实产品修复、12+49 回归、适配器读回、`SOLUTION-001` |

“DONE”指该项在本轮范围内被覆盖并有落点；它不把未做的系统能力（问题中心、方案库、
AAOS 接通、exact-SHA CI）算作已完成。

### exact-SHA CI 证据（0045017a，run 39239568709）

结论 `failure`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；红作业：aggregate / workflow-assistance。
红作业里点名的失败测试共 8 个，其中 **8 个是本轮之前就存在的**（同一批在
本轮起点 `6b6678c3` 的 run 里就已红：DSH 日期回读、executor registry pin、账本 274/276 派生三件、
ERR-276 绑定、派生审计幂等），**本轮新增 0 个**（零回归）。
本地=远端 True（实测）。本行原文里的"工作树干净"是记录器模板常量，不是当次实测——事后核对该 head
提交时工作树确为干净，所以这句话碰巧为真，但一条没量过的断言不该出现在收据里；模板已改为实测该字段。
本轮引入过并已被抓住修掉的回归是
`test_workspace_evidence_loads_plan_governance_and_history_as_typed_sources` 的 `KeyError: 'plan'`
（归档迁移时把证据源指到了 671 B 的桩文件上），它在本 run 的失败清单里已不再出现。

### exact-SHA CI 证据（263cb8f4，run 39241704566）

结论 `failure`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；红作业：aggregate / workflow-assistance。
红作业里点名的失败测试共 9 个，其中 **8 个是本轮之前就存在的**（同一批在
本轮起点 `6b6678c3` 的 run 里就已红：DSH 日期回读、executor registry pin、账本 274/276 派生三件、
ERR-276 绑定、派生审计幂等），**本轮新增 1 个**：test_the_chain_is_normalised_not_merely_resolvable。
本地=远端 True。**这条判决记下的"工作树干净"是假的**：记录当下工作树有 3 份未提交改动（就是下面这项修复
的文档），模板把状态字段写成了常量而没有实测。生成器已改为读 `git status --porcelain -z` 的条数，
后续判决不会再出现未量化的状态断言。
本轮在这个 head 上确实引入并暴露了一个回归：`test_the_chain_is_normalised_not_merely_resolvable` 报
`0 != 1 : 1 citation(s) are still shorthand`。原因是归档轮写进
`docs/current/DOCUMENT-CENSUS.md` 的 owner 段落用裸文件名引用了派生脚本，引用规范化门（本地
`tests/workflow-assistance/test_default_load_doc_citations_resolve.py` 与 CI 的 workflow-assistance 作业）
都判红。修复只走工具自身的通道：`scripts/audit/normalise_doc_citations.py --apply` 改写那一个 token
为 `scripts/audit/triage_unbound_ledger_records.py`，门恢复 9/9 绿、`rewritten=0 blocked=0`，随下一提交
在其 exact SHA 上复验。

### exact-SHA CI 证据（0aa6e2e7，run 39248107323）

结论 `failure`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；红作业：aggregate / workflow-assistance。
红作业里点名的失败测试共 8 个，其中 **8 个是本轮之前就存在的**（同一批在
本轮起点 `6b6678c3` 的 run 里就已红：DSH 日期回读、executor registry pin、账本 274/276 派生三件、
ERR-276 绑定、派生审计幂等），**本轮新增 0 个**（零回归）。
本地=远端 False（记录当下追正提交 `78a26488` 尚未推送，本地领先一格；推送后两端相等），工作树干净。这个 head 就是上一段那条新增红的修复提交：失败清单回到 8 个，全部为本轮之前既有的红，
本轮新增为 0（`failures=8, skipped=13`，与起点 `6b6678c3` 的同名集合逐字相等）。
上一条判决里那条假的"工作树干净"已在本提交内追正，生成器改为实测 `git status --porcelain -z` 的条数。
**本轮的逐 head 证据到此为止**：再为"记录这段证据的那个提交"生成一条新判决，会让记录永远追自己的 CI，
因此随后那个只追加本段的文档提交只由它自己的 run 判定，其结论在会话里读出，不再写进报告。

### exact-SHA CI 证据（1a7db78f，run 39253227445）

结论 `failure`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；红作业：aggregate / workflow-assistance。
红作业里点名的失败测试共 4 个，其中 **4 个是本轮之前就存在的**（同一批在
本轮起点 `6b6678c3` 的 run 里就已红：DSH 日期回读、executor registry pin、账本 274/276 派生三件、
ERR-276 绑定、派生审计幂等），**本轮新增 0 个**（零回归）。
本地=远端 True，工作树干净。这个 head 是"派生投影重发"那一次：与上一个 head 的失败集合按名比对，恰好少 4 项且新增为 0——
消失的四项全部是账本派生红（标签齐全、两次测量同 digest、计数分布、未绑定计数），
剩余 4 项才是真·owner 决定项：ERR-276/ERR-277 的 `fixedCommit` 绑定（要写受保护账本，
且必须有真实修复提交才可写）、executor registry pin、DSH 日期合同、派生审计幂等
（那一项在 2026-10-20 的追修里已解决，见下节；这里保留当时的判断原文）。
本条判决之后的那个提交只是把这段证据写进报告，不再为它自己生成新的判决。

### exact-SHA CI 证据（c22e5347，run 39279477980）

结论 `failure`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 1 处未提交改动。本轮界面改动（证据把手、启动链守卫、可读性滚动扫掠）在该 head 未引入任何新红：四条红全部是本轮之前就存在的基线项。

### exact-SHA CI 证据（861d171f，run 39282431049）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：workflow-assistance/Run workflow structural and contract gates——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 1 个：0 个属于本轮之前就存在的基线
（（无）），本轮新增 1 个：test_the_shipped_inventory_describes_the_tree。
基线里本 run 没有发言的项：test_deepseek_harness_keeps_its_older_dated_readback / test_regenerating_the_record_is_idempotent_apart_from_the_timestamp / test_the_pinned_registry_is_the_one_the_commit_carries / test_the_shipped_bindings_are_valid。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 2 处未提交改动。该 head 的 workflow-assistance 在 preflight 步骤就红掉，红名是 `test_the_shipped_inventory_describes_the_tree`（文档输入迁档后未同批重发的工具清单投影），随后的 contract-gates 步骤被整体跳过，所以基线四项在这个 head 上没有发言——那是读数缺席，不是问题消失。同一支测试在 `2b7cf459` 本地 12 例全绿，即这枚红已由同批重发清单修掉；preflight 按 W03 的设计在十几秒内点了真实缺陷的名字，而不是等 2712 例治理批跑到一半才把它扮成"治理失败"。

判定身份要说清：本 run 由 `pull_request` 触发（PR #178），工作流读到的 checkout 是 merge 提交 `5cff35026be8dbe61f482e0baede0edfd7cbc0b6`，分支 head `861d171f` 只是 PR 头；`.github/workflows/work-lab-gate.yml` 的 W01 注释写明分支 push 不再跑重作业，分支的证据本来就来自 PR run，所以这里的"exact-SHA"名义上绑的是 merge 提交而不是我推上去的那个 SHA。这不必靠说法成立，内容可以比：`origin/main` 现为 `f6077d18`，`git merge-base --is-ancestor f6077d18 2b7cf459` 为真（main 已被我这个 head 包含），PR #178 的 merge ref 现解析到 `d7ddf2368004438ab2a81f1a220e20de57be9eea`，而它的 tree 与 `2b7cf459` 的 tree 同为 `925222f753359e7761d94f10db7d952e0663ec22`——判的就是我这棵树。留一条给后来人：一旦 main 前进而分支没合，merge tree 就不再等于分支 head，那时"exact-SHA"名不副实，读红之前先比 tree。

### exact-SHA CI 证据（2b7cf459，run 39285254929）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / token-monitor；
红作业：aggregate / observer / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：observer/Post Cache Rust build output (observer) / observer/Post Cache Rust dependency sources (observer) / observer/Post Pin Python (locked dependency truth)——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 5 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 1 个：test_every_line_pointer_lands_on_the_code_it_quotes。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 3 处未提交改动。本 head 是界面打磨批次：把手区块从 EvidenceView 拆出成独立组件并配 33 例契约测试、两条真相缺陷（surfaceRoot 声称与缺字段印成 0）就地修掉、过滤参数在构造证据地址时被保留、过期计数注释与 DESIGN/SCREEN_SPEC 的引用口径追正、启动链守卫改为不钉死构建产物、工具清单与它的文档输入同批重发。

本轮新增的那一枚红是我自己造的：`test_every_line_pointer_lands_on_the_code_it_quotes` 点名
`docs/history/archive/ui-priority-20261009/UIV2-INTERFACE-BINDING-MATRIX.csv` 的 B05 行把 `apps/observer/frontend/src/lib/evidenceRange.ts:132`
钉在 `EVIDENCE_PARAM_NAMES` 的声明上，而我这个批次为了加两个过滤参数名在该行上面插了 8 行，声明于是走到 140 行。
修法是重钉行号而不是改引文（该门比较的是引文前 48 个归一化字符，前后都对得上），
重钉脚本先断言"这段前缀在新文件里只出现在唯一一行"才落笔；重钉后
`tests/workflow-assistance/test_ui_v2_csv_citations_resolve.py` 8 例全绿。
教训照旧：行号指针会随文档一样腐烂，改代码上方就是在改别人引用的地址。

### exact-SHA CI 证据（3ee7fed5，run 39288902322）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 2 处未提交改动。本轮界面链在 CI 上的最终判决：红名单回到本轮之前就存在的四项基线（DSH 日期回读、记录重发幂等、钉住的注册表、随包绑定有效性），`test_every_line_pointer_lands_on_the_code_it_quotes` 与 `test_the_shipped_inventory_describes_the_tree` 两枚本轮自造的红都已消失，`observer` 作业转绿；新增红 0。

这一行不是"CI 全绿"：那四项基线仍红，且它们各自等的是 owner 决定（受保护账本的 fixedCommit、注册表钉住的 SHA、以及绑定有效性的裁决），不是本轮可以自行关掉的。判决块由打了步骤级沉默补丁的记录器生成，preflight 与 contract-gates 都跑完了，所以基线四项是真的发言过仍然红，不是没跑到。

### exact-SHA CI 证据（49ecdeb7，run 39291084719）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 4 处未提交改动。这一 head 只含文档与判决记录（§15.2 的渲染复验与 3ee7fed5 的判决块），代码未变；判决回到本轮之前就存在的四项基线红、本轮新增 0，`observer` 作业继续 success。

紧接着的这一批（采样分母入仪器）改的是 `scripts/audit/text_legibility_via_cdp.py` 与它的判定测试，并把工具清单同批重发——上一轮"改了被清单摘要的文件却没重发清单"的红就是这么来的，这次先重发再过门。

### exact-SHA CI 证据（2b3e0f32，run 39293169146）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 1 处未提交改动。这一 head 改的是仪器与文档（采样分母入 `scripts/audit/text_legibility_via_cdp.py`、它的 56 例判定测试、路线图表格补形、工具清单同批重发）。preflight 步骤绿（清单与它摘要的文件同批重发这一步奏效了），治理批红名单仍是本轮之前就存在的四项基线，本轮新增 0。

那四项基线各自等的是 owner 决定：受保护账本里 ERR-276/277 的 fixedCommit 绑定、`config/adapter-registry.json` 钉住的 SHA、DSH 的日期回读、以及随包绑定有效性的裁决——都不是本轮可以自行关掉的，也不该为了凑绿而改判定。

### exact-SHA CI 证据（0108ec8b，run 39294943304）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 1 处未提交改动。这一 head 只含路线图与判决文档（表格补第四列、NEXT 补两条实测代价）。preflight 绿、治理批红名单仍是四项既有基线、`observer` success，本轮新增 0。

这条链到此的诚实读法：每一个被推送的 head 的判决都由"下一次推送"记录下来，所以最新那个 head 的判决天然是欠着的——本轮把欠的那一段读完了（run 39294943304，红名单四项基线、新增 0），并把它写在这里；下一轮从它自己产生的 head 继续这个错位，而不是假装链条已经闭合。

### exact-SHA CI 证据（7bce2e30，run 39297055321）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树干净。这一 head 只含路线图 NEXT 的两条实测代价与 0108ec8b 的判决块，代码未变：preflight 绿、`observer` success、治理批红名单仍是四项既有基线、本轮新增 0。

到这里，本轮每一次推送都有一份对应的 exact-SHA 判决被记进本文件：`2b7cf459`（新增 1，就是那枚行号指针腐烂，随后在 `3ee7fed5` 起消失）、`3ee7fed5`、`49ecdeb7`、`2b3e0f32`、`0108ec8b`、`7bce2e30`，后五份结论一致：红名单四项不变、新增 0。这条链的固有错位仍然成立——记录判决的那次推送本身，其判决要由下一次记录来读；本轮到此为止不再续推，`7bce2e30` 之后唯一的未读 head 就是这份记录产生的那个。

### 本地独有工作物的清理：两条 stash（2026-10-20，owner 指示"有用就留着 没用就删除掉"）

`git stash` 是本地对象，推送不会带走它，所以"云端本地一致"这句话必须单独检查它。仓库里有两条：
第一条（旧列表索引 0，2026-10-07，消息自带 `discard-me`）与第二条（旧索引 1，2026-09-25，
token-monitor 的 `apps/token-monitor/src-tauri/src/lib.rs`）。
先测再删，判据是逐行比对而不是印象：

- 第二条：22 行新增，逐行在 `HEAD:apps/token-monitor/src-tauri/src/lib.rs` 里查找，
  **22/22 已存在**，即它的全部内容早已随提交落地。
- 第一条：35 文件 113 行新增，其中 52 行不在 HEAD。抽样归类成两类，都不是待上传的工作：
  一类是把 `packages/client-neutral-core/` 前缀重复了一遍的双路径腐烂（写成 `…/packages/client-neutral-core/bin/…`，
  这个目录从来不存在，此处只是引用被丢弃的写法，不是声明路径）；
  一类是 2026-09 目录收敛之前的 `${HERMES_HOME}/packages/client-neutral-core/bin/...` 旧写法，
  而现行 `config/config.yaml` 与 `docs/current/workflow-assistance/workflow/project-data-boundary.md`
  用的都是收敛后的 `${HERMES_HOME}/bin/...`。第一条的 untracked 侧（其第三个父提交）实测为空树。

可恢复性先证明再动手：两条的 tracked 差异与头信息已导出为
`.project-local/artifacts/stash-retirement-20261020/stash-{0,1}-tracked.patch`
（第一条 66,263 B / 第二条 3,365 B），drop 之后两个提交对象
`fbb97053c23293889e7f9381a98dc98d851455e5`、`9d393d9ff7951c5f9358c23e20c9361309dce8e1`
经 `git cat-file -t` 仍返回 `commit`，短期内可直接 `git stash apply <sha>` 找回。
这里按 SHA 称呼这两条而不是按 `@` 花括号简写，有两个理由：一、drop 之后旧索引已经不再指向任何东西，
写索引号是一句现在读不出来的话；二、git 的 at-花括号 revision 简写不加引号会被 PowerShell 解析成哈希表字面量，
本仓 hazard 扫描器把它当命令性文本拦（这条段落在 2026-10-20 的全批里被扫出 7 处并因此改掉）。
结果：`git stash list` 为 0 条，工作树 0 处改动，本地与 `origin/docs/handoff-20261018-qoder`
同为 `bc304642`。

## 13. 2026-10-20 追修与清理（owner：该修复的修复，该清理的清理）

四项既有红先各自复现再分类，结论是**一项可自修、一项推导完成只差落笔、两项确实要外部动作**：

- **派生审计幂等：已修。** 红因是 `scripts/audit/project_local_citation_audit.py` 的裁决表里剩一条
  `UNADJUDICATED`：`.project-local/artifacts/wui-20261009/refs-census-20261018.json`。先量清它是什么
  （889,298 B、sha256 前缀 `024d34786ef9feef`、2026-10-18T17:21:26Z 在 head `0369d349` 生成，
  自述规则 `scripts/ci/verify_authority_index_paths.py:check()`，662 面：live 33/512/143 断链、
  dated_archive 70/329/243、external_skill_copy 559/3,327/2,871），再按事实裁决：仓内没有生成它的那个驱动，
  所以欠的是仪器而不是字节。裁决文本写进表里后
  `tests/workflow-assistance/test_project_local_citation_audit.py` **12 例全绿**，审计重发为 676,778 B。
- **ERR-276/277 的 `fixedCommit`：推导完成，等 owner 落笔。** 两条记录承诺的回归脚本
  `scripts/ci/verify_error_ledger.py` 经 `git cat-file -e 13ed879b:scripts/ci/verify_error_ledger.py`
  证实存在于出生提交 `13ed879b`，门要的两件事（提交存在 + 承诺脚本在该提交里）都成立。
  写这两个字段要动受保护账本，按既定边界我不自填；此处给出可直接落笔的结论而不是笼统的"待裁"。
- **executor registry pin：当时判为"需要重跑探针"，本节末尾已被 `--no-launch` 解决。** 当时的判断是
  重钉只能靠真重跑 `scripts/audit/executor_live_probe.py`，而它会执行 codex / gh 的版本命令并对两个
  GUI 入口各等 25 秒超时；不重跑而改摘要就是伪造快照。这个结论方向没错——不能假造——但漏了
  "只跑无界面那两项"这条路径，见本节末「registry pin 不需要拉起任何界面也能修」。
- **DSH 日期合同：需要写受保护注册表。** 门的断言是 `observed_at <= 2026-10-07`，而注册表现在是
  `2026-10-13`——即那条读回被推后了日期却没有可重读的免启动来源。要么按合同退回旧日期，
  要么补一个免启动来源并同步门的口径，两者都要动 `config/adapter-registry.json`。

**顺带重发两份落后的派生审计**：`docs/audits/LEDGER_FIX_COMMIT_BINDING_2026-10-07.json`
（bound 143→151、unboundPass 94→96）与上面那份引用审计——都是"改了被摘要的文件却没重发"的同一类。

**仪器补强**：`scripts/audit/text_legibility_via_cdp.py` 每泳道滚动预算 16→96，并新增
`every_scrollable_range_was_traversed`（没走完滚动范围按泳道点名判红）。实测从 298/564 站变成
**565/565 站、无短程泳道**，代价 46 秒→69 秒；`tests/ci/test_text_legibility_gate.py` 57 例全绿。
同时纠正我自己发布过的一个误读：`sampled/present` 不是行数覆盖率——合并按
(path, text, size, weight, colour) 去重，200 行重复单元格本就只算一次；被保证的是每一段滚动范围都上过屏。
两条新门不会误伤静态消费者，这一点是量出来的不是推的：`scripts/audit/reseal_wui_evidence.py` 会以无后端
模式调 `--all-views`，实跑一趟 `sampled 1,957 / present 1,984`、`stops 217/217`、无短程泳道、退出码 0
（回执 `.project-local/artifacts/standalone-run-20261019/25-legibility-static-views.json`）。

**清理**：删除 8 个"没有任何仓内文件引用、且已被后续回执取代"的本机中间回执，回收 **74.7 MB**
（`.project-local/artifacts` 451.3 MB → 376.6 MB），每个文件的 size+sha256 记在
`.project-local/artifacts/cleanup-20261020-uncited-superseded.json`，且全部可用仓内仪器重生成。
`.project-local/artifacts/LEGIBILITY_SIZES_D.json` 因被仓内引用而**保留**（删除脚本逐条复检引用面）。
体积最大的单项 `.project-local/artifacts/dsh-backup-pre-deploy/DSH-Desktop.exe-pre-deploy-backup`
（225.65 MB）**未动**：那是第三方旧版安装的回滚副本，不是本项目产物，只有 owner 能决定放弃那次回滚。

### exact-SHA CI 证据（bc304642，run 39345008690）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树干净。这一 head 只含"本地 stash 退役"的记录（两条本地独有工作物按逐行比对判为已被取代，补丁与 SHA 先导出再 drop）。判决：`observer` success、红名单仍是四项既有基线、本轮新增 0。

### exact-SHA CI 证据（fd310522，run 39413261299）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 4 个：4 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_regenerating_the_record_is_idempotent_apart_from_the_timestamp、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中账本派生四件已随派生审计重发而消失，
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 1 处未提交改动。这一 head 只含 7bce2e30 的判决块（把"每一次推送对应一份判决"这条链补齐到当时最新的那个 head）。判决：`observer` success、红名单仍是四项既有基线、本轮新增 0。

### exact-SHA CI 证据（3e409f56，run 39427706258）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 3 个：3 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中 5 件已随各自的修复退役
（账本派生四件随派生审计重发消失，引用审计幂等一件随 2026-10-20 的裁决消失并在 CI 里确认转绿），
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树干净。这一 head 含本轮的修复与清理批次（派生审计裁决、扫掠预算 16→96 与两条新覆盖门、两份派生审计重发、74.7 MB 未引用中间回执的退役）。

CI 实测变化：红名单从四项基线缩到**三项**——`test_regenerating_the_record_is_idempotent_apart_from_the_timestamp` 在云端消失，即引用审计那一项的修复不只是本地绿，云端也认了。剩下三项仍是等 owner 的那三件：DSH 日期合同、executor registry pin、ERR-276/277 落笔（推导已完成）。新增红 0，`observer` success，无未发言作业或未发言步骤。

顺带记一笔链条的自我消耗：`2ed1b50d`（修复批次本身）被这次推送取消，没有拿到判决；它的内容作为本 head 的祖先被完整覆盖，所以证据没有丢，丢的只是"那个 SHA 名字上的判决"。

### registry pin 不需要拉起任何界面也能修（2026-10-20 追记）

上一节把 executor registry pin 归给 owner，理由是"重跑探针会启动 GUI"。这个归类当时是对的，但只说了一半：
`scripts/audit/executor_live_probe.py` 的七个 resolver 里只有两个是命令行
（`packages/client-neutral-core/bin/codex.cmd` 与 `gh`），其余五个解析到 Electron/桌面二进制——
2026-10-07 那次 hermes 与 deepseek-harness 各等满 25 秒超时，就是因为 `--version` 被 GUI 忽略而程序真的起来了。
所以补了 `--no-launch`：只执行已被证明无界面的两项，其余按具名类别 `PROBE_SKIPPED_NO_LAUNCH` 记录，
不解析、不执行、更不升级（回执里这些行没有 `command` 也没有 `probe`，门逐条断言这一点）。

新回执 `docs/audits/EXECUTOR_LIVE_PROBE_2026-10-20.json`：`registrySha256` 与索引里的注册表**逐字节相符**
（`4be802ef…`，basis=git-index），十行计数为 skipped 5 / VERSION_MOVED 2 / NOT_PROBED_DECLARATIVE_ONLY 3，
`readOnly=true`。门改指最新回执，旧的 10-07/10-08 留在仓里作为它们那天的证据。
`tests/workflow-assistance/test_executor_live_probe.py` 从 11 例涨到 **15 例全绿**，四例新增：
被跳过的行必须像拒绝而不是像结果（无 `command`、无 `probe`）、无界面白名单只能是 codex 与 github
且回执里被真正执行过的行不得越出它、带构建日期的声明不得被当成版本漂移、以及归一化之后真漂移仍要报红。

顺手抓到一处仪器自己的错：注册表里 github 声明 `2.98.0 (2026-08-20)`（那是从 Windows 版本资源抄来的，
带构建日期），而 `gh --version` 打印 `2.98.0`，旧的逐字符串比较把**同一套装成了漂移**。改为两侧都取
版本 token 再比——它能让装饰对齐，但不会把 0.160.1 说成 0.163.0。种入假数（把 github 的观测改成 3.0.0）
后门立刻点名判红，回执按 sha256 逐字节还原（`80b186441368e3c9…` 前后一致）。

**一条真实的漂移发现，不粉饰**：codex 注册表声明 `0.160.1`，本机现在答
`0.163.0-alpha.10.2`（exit 0）。这是五维基线第 3 维（官方标准 + 用户配置）该看见的事：包装器解析的还是
同一个入口，但底下的 CLI 已经换到了 alpha 通道。是否把注册表的声明改成观测值，是 owner 对"声明基线"的
决定，探针只记录不和解——两串都留在回执里。

### exact-SHA CI 证据（2bbb8b99，run 39431220157）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 3 个：3 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_the_pinned_registry_is_the_one_the_commit_carries、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：（全部发言过）。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中 5 件已随各自的修复退役
（账本派生四件随派生审计重发消失，引用审计幂等一件随 2026-10-20 的裁决消失并在 CI 里确认转绿），
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 4 处未提交改动。这一 head 只含判决记录与静态模式复测（3e409f56 的判决块、无后端 `--all-views` 实跑读数）。判决：红名单三项既有基线（DSH 日期、registry pin、ERR-276/277 落笔），新增红 0，`observer` success，无未发言作业或步骤。

其中 registry pin 那一项在**本工作集里已被 `--no-launch` 解决**（新回执钉住当前注册表字节，门 15 例全绿），所以下一个 head 的名单预期只剩两项；这一项不是被放宽，而是被真正测了一遍。

### 顺手量到的真实漂移：Hermes 又自升级了一次（2026-10-20，不粉饰也不就地掩盖）

跑本轮门集时 `tests/workflow-assistance/test_adapter_version_readback.py` 里那条**只在有安装戳的机器上
才执行**的复读断言转红：本机 `hermes_cli` 安装戳现在答 `0.21.7+472.gcba45e8`，而注册表与
`docs/audits/TOOL_VERSION_METADATA_PROBE_2026-10-07.json` 记的都是 `0.21.5+6948.gedd2476`。
这正是 ERR-158/159 记过的同一类事——自更新机制每次写戳，声明基线就每次落后，而且**CI 看不见**：
安装戳在仓库外，干净检出走的是具名 skip，所以云端名单里从来不会有这一条。

处理方式是不动。把探针重跑一遍只会让回执变成 `0.21.7`，而注册表还钉着 `0.21.5`，于是"声明↔回执"那条门
从绿转红——红被搬了个地方，漂移没有被解决；要真解决，得改 `config/adapter-registry.json` 的
`version_readback`（受保护文件，且这是"声明基线跟不跟机器走"的 owner 决定）。所以这里只把两个字符串、
复读命令和"CI 结构上看不到它"写清楚：复读 = `python scripts/audit/tool_version_metadata_probe.py`
（免启动，读版本资源与安装戳），比对点 = 上述门文件的 `displayVersion` 断言。

### DSH 的红是**真漂移**：我准备放宽门之前先量了一次，结果推翻了自己的判断（2026-10-20）

看到 `test_deepseek_harness_keeps_its_older_dated_readback` 要求 `observed_at <= 2026-10-07`
而注册表写 `2026-10-13` 时，我的假设是"这条日期钉过时了"——因为该行的 method
`windows-installer-registry-and-start-menu-shortcut-readback` 是免启动可复读的，而同一个门正是用这条理由
豁免了 Hermes。**动手改门之前先问机器**，两次独立读法给出同一个答案：

- 仓内仪器 `scripts/audit/tool_version_metadata_probe.py` 的函数：verdict
  `LIVE_VERSION_FROM_FILE_METADATA`，`fileVersion = 0.2.1-rc.2`，`launched = False`；
- 直接 PowerShell 读 HKCU 卸载键与 exe 版本资源：`DisplayName = DeepSeek Harness 0.2.1-rc.2`、
  `DisplayVersion = 0.2.1-rc.2`、`FileVersion = 0.2.1-rc.2`、`ProductVersion = 0.2.1.0`，
  安装根仍是 `C:\Users\ALEX\AppData\Local\Programs\DeepSeek Harness`。

注册表与 `AGENTS.md` 钉的官方构建都是 **0.2.0-rc.2**，而本机已自升级到 **0.2.1-rc.2**。
所以那枚红是仪器在报它该报的事，我的假设被证伪，**门一行没改**。这也说明日期钉在这里没有冤枉谁：
被推后的日期背后是一次没有对齐声明的自升级。

给 owner 的选择题因此变清楚了，两条都是可执行的一次改动：
(1) 接受 0.2.1-rc.2 为新声明基线——改 `config/adapter-registry.json` 的 `provenance.version` 与
`version_readback`（observed_at / verified_version / native_readback），并同步 `AGENTS.md` 里
"official build `0.2.0-rc.2`"那句声明（不写行号，行号会腐烂）；或 (2) 退回 0.2.0-rc.2 重装，声明不动、把这次升级当作越界事件记 ERR。
两条都碰受保护文件，我不自填。顺带一条读数事实供决策：该 exe **有**版本资源（不是 hermes 那种
`FILE_EXISTS_WITHOUT_VERSION_RESOURCE`），所以无论选哪条，复读都不需要启动界面。

### exact-SHA CI 证据（c3e4a6b3，run 39435328246）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / observer / supply-chain-security / token-monitor；
红作业：aggregate / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：（无）——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 2 个：2 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：test_the_pinned_registry_is_the_one_the_commit_carries。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中 5 件已随各自的修复退役
（账本派生四件随派生审计重发消失，引用审计幂等一件随 2026-10-20 的裁决消失并在 CI 里确认转绿），
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 1 处未提交改动。这一 head 含 executor 探针的 `--no-launch` 与重钉后的回执、Hermes 漂移记录、2bbb8b99 判决块。

判决：红名单从三项缩到**两项**——`test_the_pinned_registry_is_the_one_the_commit_carries` 在云端消失，即 registry pin 那枚红被真测量修掉（没有启动任何 GUI）。剩下两项是 DSH 日期合同（本轮已证明是真漂移：本机 0.2.1-rc.2 对声明 0.2.0-rc.2）与 ERR-276/277 落笔。新增红 0，`observer` success，无未发言作业或未发言步骤。

### exact-SHA CI 证据（d30dc80f，run 39444153610）

结论 `failure`；触发 `pull_request`；绿作业：gate-plan / integration / supply-chain-security / token-monitor；
红作业：aggregate / observer / workflow-assistance；
未发言作业：（无）——被取消或跳过的作业**没有测过它自己那块界面**，
所以本轮的红点名单只覆盖仍然跑完的作业，不能据此说"全链已判定"。
未发言步骤：observer/Post Cache Rust build output (observer) / observer/Post Cache Rust dependency sources (observer) / observer/Post Pin Python (locked dependency truth)——一个作业可以在第一个步骤就红掉，
把后面装着其余套件的步骤整体跳过，于是"基线红不见了"是读数缺席而不是问题消失。
红作业里点名的失败测试共 2 个：2 个属于本轮之前就存在的基线
（test_deepseek_harness_keeps_its_older_dated_readback、test_the_shipped_bindings_are_valid），本轮新增 0 个（零回归）。
基线里本 run 没有发言的项：test_the_pinned_registry_is_the_one_the_commit_carries。
基线本身是本轮起点 `6b6678c3` 那次 run 实测出来的 8 项；其中 5 件已随各自的修复退役
（账本派生四件随派生审计重发消失，引用审计幂等一件随 2026-10-20 的裁决消失并在 CI 里确认转绿），
所以这里只列出**本 run 仍然红的那几项**，不复制历史清单。
本地=远端 True，工作树有 3 处未提交改动。这一 head 是纯文档（DSH 真漂移记录 + c3e4a6b3 判决块），但它的 `observer` 作业转红了——不是界面坏了，是几何门自己崩了：`verdict()` 在拼 PASS 明细时写 `measured['.top-actions'][0]`，而 runner 上那次采集返回的不是盒子列表，于是抛 `KeyError: 0`，整个作业带着"什么也没说"就下去了。修法与反例见下一节；本地同一条门 `GEOMETRY_GATE_PASS`。

治理批的红名单仍是两项既有基线，本轮新增 0。

### 门自己崩了比界面坏了更难发现：几何门的形状防御 + 把手可见延迟仪器（2026-10-20）

`d30dc80f` 是纯文档提交，`observer` 作业却转红。不是界面坏了：`scripts/audit/topbar_geometry_via_cdp.py`
在拼一条 PASS 明细时写 `measured['.top-actions'][0]`，而 runner 上那次采集回来的不是盒子列表，
于是 `KeyError: 0` 把整个作业带下去，**回执里一个关于界面的字都没有**。同一函数里还有第二处同族脆弱点：
`actions["display"]` 在一个元素没有 `display` 键时同样会抛。

修法是把"读不懂"变成具名判红，而不是把门放宽：`_first()` 之后一律用 `.get()`；
`.top-actions` 若不是列表，`action_row_inside_viewport` 直接判红并把 `shape=<类型> rows=<数量>` 写进明细，
说明"采集回来的东西读不出盒子，门拒绝把读不懂当作通过"。反例进
`tests/ci/test_topbar_geometry_gate.py`：字典形状必须判红且点名，空列表必须不崩且判绿，
带 `gapToViewportRight: -40` 的列表必须判红——该模块 47 例 → **48 例全绿**，
本地同一条门对已构建包重跑 `GEOMETRY_GATE_PASS`（回执
`.project-local/runs/standalone-20261019/geometry-after-fix.json`）。
runner 上到底是哪种形状，下一次跑会直接把 `shape=` 写在明细里，不用再猜。

另起一支把度量蓝图里最后那条"should"欠账做掉了：新仪器
`scripts/audit/handle_block_visibility_via_cdp.py` 用真实链路（`u19.start_sidecar()` 出真快照，
不是桩）量"证据把手区块多久才可见"。实测 5 次全新加载：中位 **3,260 ms**、最差 3,294 ms、
每次都渲染出 200 行（回执 `.project-local/artifacts/standalone-run-20261019/26-handle-latency.json`），
采样粒度 20 ms 写进收据，因为不看仪器分辨率的阈值就是猜。

这个数字第一版差点被我错标成"渲染慢"。拆开量了一次：同一个 sidecar 的 `/api/v1/snapshot`
首次 31 ms、中位 15 ms、165,108 B、200 行把手俱在——**生产者不是瓶颈**。而当时那句"那 3.26 秒几乎全在
页面一侧（加载 + 挂载 + 应用自己的首帧节奏）"**是错的，2026-10-21 用改造后的仪器重量后在这里更正。

**3,225 ms 量的是仪器自己什么时候醒过来，不是页面什么时候出现东西。** 旧实现把 URL 直接写在 Chrome
命令行上（导航从那一刻开始），随后固定 `sleep(2.0)` 等 CDP 端口、`sleep(1.0)` 再求值，所以它最早的一次
观察已经在导航之后约 3.2 秒。同一批样本自己就供出了这件事：5 次加载里 `rowsMs` 与 `capacityMs` **每次都
完全相等**（20 ms 轮询在第一次迭代就 break），而同样本 `domContentLoadedMs` 只有约 140 ms；极差 14 ms 是
一个 `sleep()` 的形状，不是一个页面的形状。

改造后的仪器把记录器用 `Page.addScriptToEvaluateOnNewDocument` 在**导航之前**装进页面，所有边界用页面自己
的单调时钟 `performance.now()` 打点（`.project-local/artifacts/wl02-and-handle-20261021/handle-latency-attribution-v2.json`，
被测主 JS 包的 sha256 前缀 `8e793275`，产物名只写在那份回执里，dist 本身不入跟踪树；1280×820 → CSS 视口 1262×668，4 次全新加载，
中位/最差）：

| 段 | 定义 | 实测 |
| --- | --- | --- |
| A 快照解析 | navigationStart → 喂给这次渲染的那次解析结束 | **150 / 161 ms** |
| ├ A1 | 导航到请求发出（含 navStart→DCL 59–69 ms） | 134–151 ms |
| ├ A2 | 请求发出 → 响应到达（sidecar 侧） | 13–15 ms |
| └ A3 | fetch 侧的响应体 JSON 解析 | 1–20 ms |
| B React 提交 | 那次解析结束 → `[data-testid="evidence-handles-rows"]` 挂上首个子节点（200 行） | **59.5 / 66 ms** |
| C 到首可见 | 请求滚动 → 真正落屏那一帧（双 rAF） | **54.5 / 58 ms** |
| 合计 | navigationStart → 行在 DOM | **207.5 / 222 ms** |

同一次读数里 `readbackAtMs = 3535`、`rowsAtMs ≈ 208`：**仪器看的时候比事情发生晚了 3.3 秒**，这正是旧数
的来源。另两处顺带量到的事实：4 次加载里 3 次由 `?api=` 的 fetch 解析喂给渲染、1 次由 SSE 帧的
`JSON.parse` 喂给渲染（所以只包 fetch 那一侧的解析会把因果配错，配错就出现负的 B 段——本轮真实
出现过 `-3 ms`，是新增的符号断言把它抓出来的）；把手块提交时行列表 `rect.top = 884`，视口只有 668 高，
**列表起点在屏下 216 px**，列表本身高 23,056 px（与 §15.2 直接读 DOM 量的 23,031 px 同一件事），
滚动之后可见比例 2.2%。所以这条指标的正确写法是"把手块首屏**不可见**是几何问题（200 行未虚拟化），
不是延迟问题；把滚动做起来的那一帧代价 54 ms"，而"页面慢 3.26 秒"这个说法作废。

守卫落在 `tests/ci/test_handle_latency_attribution.py`（15 例，其中"没装记录器"、"时间戳不早于读数"、
"段缺失或为负"、"屏下却报 0 ms 滚动"、"回执不绑包体哈希"、"必测段名与页面表达式漂移"都是植入反例）：
仪器现在必须先能说"我没量到"，才允许说一个数字。

### 三项待批决定的准备状态（2026-10-20，全部"只备不做"）

工具 `.project-local/runs/standalone-20261019/prepare_owner_patches.py` 把该量的都重量了一遍，
并在结尾断言三个受保护权威文件的 sha256 **一字未变**（输出
`TRACKED_AUTHORITY_FILES_MODIFIED: none`）。产物在
`.project-local/artifacts/owner-decisions-20261020/`。

1. **ERR-276 / ERR-277 的 `fixedCommit`——补丁已就绪并验证可干净套用。**
   证据：两条记录 `status_after=PASS`、`date=2026-10-13`、`lifecycle.fixedCommit=null`；
   出生提交 `13ed879b` 存在，且门要求的承诺脚本 `scripts/ci/verify_error_ledger.py`
   确在该提交内（`git cat-file -e` 两项均 0）。
   补丁 `01-err-276-277-fixed-commit.patch`（1,622 B）先把账表按 `json.dumps(indent=2)` 往返证明逐字节可复原，
   才生成差异，因此它只加两个字段、不重排任何一行；`git apply --check` 通过（只检查，未落笔）。
   一句 `git apply .project-local/artifacts/owner-decisions-20261020/01-err-276-277-fixed-commit.patch` 即可落地。
2. **DSH 声明基线——数据已备，方向归你。** 免启动重读（`exe_under` + 版本资源）给出
   `fileVersion=0.2.1-rc.2`、`verdict=LIVE_VERSION_FROM_FILE_METADATA`、`launched=false`，
   而注册表声明 `0.2.0-rc.2`。选"跟机器"就改 `provenance.version` 与 `version_readback`
   的 `observed_at/verified_version/native_readback`，并同步 `AGENTS.md` 里
   "official build `0.2.0-rc.2`"那句；选"守声明"就重装 0.2.0-rc.2 并把这次自升级记成 ERR。
   两条都会让门变绿，但说的是两件不同的事，所以我不替你选。
3. **Hermes 声明基线——同上，且这次连累了一条 CI 看不见的断言。** 安装戳重读
   `displayVersion=0.21.7+472.gcba45e8`（`baseVersion 0.21.7`、`distance 472`、
   `commit cba45e8a…`；戳在仓库外，由 `install_stamp_for()` 按二进制路径解析，完整路径记在
   `.project-local/artifacts/owner-decisions-20261020/02-03-version-rebaseline.evidence.txt`），
   注册表与回执都是 `0.21.5+6948.gedd2476`。这是同类漂移的**再一次**：ERR-158/159 记录时那已经是
   第二次（第一次由 AG-07 `a676e63` 从 0.21.2 纠正），现在是其后的第三次。
   注意：这条在云端不可见（干净检出没有仓库外的戳，走具名 skip），所以它不会靠 CI 变绿来提醒你。

选定 2 / 3 之后，我可以用同一个工具生成与第 1 项同等质量的补丁（往返验证 + `git apply --check`），
仍然不自动落笔。

## 14. 声明基线跟不上机器这件事，一次量清并落地（2026-10-20，owner 全部授权）

把 DSH 那条日期钉换成"必须有免启动来源"之后重跑免启动元数据探针，结果不是修一条红，
而是**把整张声明基线的陈旧度一次量了出来**（全部 launched=false，没有启动任何客户端界面）：

| 客户端 | 注册表原声明 | 2026-10-20 免启动重读 | 处理 |
| --- | --- | --- | --- |
| DeepSeek Harness | 0.2.0-rc.2 | 0.2.1-rc.2（卸载键 + exe FileVersion 一致；厂商更新源自 2026-10-17 起就发布 0.2.1-rc.2） | 改声明，旧值进 `version_historical` 与 `superseded_observation` |
| Hermes | 0.21.5+6948.gedd2476 | 0.21.7+472.gcba45e8（安装戳，更新器 2026-10-13 重写） | 同上；这是同类漂移的第三次（ERR-158/159 记录时已是第二次） |
| CC Switch | 3.20.0 | 4.0.15（卸载键 + exe 版本资源一致） | 同上；`status` 保持 `legacy_observe`——观测到装了什么不等于给它活动状态 |
| OpenHuman | 0.63.12 | **读不到**：卸载键已消失，`%LOCALAPPDATA%\OpenHuman` 只剩运行时代码目录，顶层没有 exe | 值保留为"最后一次已验证观测"，但行上标 `reproducible=false` + 具名 verdict |
| Open Design | 0.24.1 | 0.24.1 | 未变 |

三处声明被改，`AGENTS.md` 里 DSH 的官方构建随之一处两句同步（第 57 行段与五维基线第 1 维那句）。
门侧的改动是把"日期不许新过某天"换成"来源必须免启动可复读 + 注册表必须逐字引用探针读到的值"，
并配了四条植入反例（改成启动式方法、改成没读过的号、删掉被取代记录、探针承认启动过）——
`tests/workflow-assistance/test_adapter_version_readback.py` 8 例 → **12 例全绿**。

**OpenHuman 那条是这轮最重要的门设计教训**：探针读不到版本时，旧门直接 `assertEqual(claim, None)` 报红，
看起来像"注册表错了"。真正的区别是**"数不对"和"读不到"是两种状态**，混在一起就会逼人把一次卸载
当成一次数据错误去"修"。现在不可复读必须写成具名状态（`reproducible=false` +
`not_reproducible_verdict` 必须等于探针实际给出的 verdict），并且有一条反例证明：把标记抹掉，门立刻红——
逃生口本身是被检查的对象，否则"缺失"会变成任何声明都可以留着的借口。

顺带纠正一条写错的旧证据：2026-10-13 那次 DSH 读回的 `source` 里写着"厂商 feed 的 size/sha512
与已安装构建相同"。今天量下来 feed 那个数是 **NSIS 安装包**（289,385,456 B）的，
而已安装 exe 是 246,343,144 B——两者不是同一个产物，那句话把安装器和被安装的二进制混成了一件事。
新记录只声明真正成立的那件：已安装 exe 自己的版本资源与卸载键都读到厂商当前发布的同一个版本号。

## 15. 把这一轮写进账本时，账本门抓到了我自己（2026-10-20）

§14 的重钉落盘后，把这轮的两件事写进 `taskpacks/current/error-ledger.json`：

| 记录 | 内容 | `fixedCommit` 指向 |
| --- | --- | --- |
| ERR-278 | 四个客户端声明基线同时陈旧（DSH / Hermes / CC Switch 值过时，OpenHuman 读不到），根因是门只考"观测日期"而不考"来源形状"，于是最省力的绿灯办法是继续引用旧回执 | `a9110584`——真正改钉 + 12 例门的那次提交 |
| ERR-279 | 写绑定的那两行自己踩了聚合账本门：`fixedCommit` 从日志行手抄成 8 位短 SHA，而 `scripts/ci/verify_error_ledger.py` 要求 introduced/fixed/verifiedCommit 必须是 40 位十六进制或 null | `503c6b43`——补成全 SHA 并重发四张派生回执的那次提交 |

ERR-279 值得单独记，因为它不是"运气不好被抓"：**a9110584 已经推上去了，而 CI 的作业里就有
`python scripts/ci/verify_error_ledger.py` 这一步**——那一版一定会被判红。我在去读云端判决之前
先把这条本地门跑了一遍，于是红在本地就变成了一个还没出厂的缺陷。这里的顺序教训是：
我提交前跑的是单项绑定门（`tests/workflow-assistance/test_ledger_fix_commit_binding.py`，10 例），
它自己会把短 SHA 解析成完整提交，所以它对我抄进去的那个形状完全无感；真正管这条字段线上形状的
是聚合门。**为一个字段重跑"关于它的门"，不等于重跑"读这个字段的所有门"**。修正后的写法是：
提交号一律由 `git rev-parse` 生成并当场断言长度与字符集，再 `git cat-file -e <full>:<path>` 重证
那次绑定成立，手抄日志行这条路径彻底关掉。单项门是否也该要求 40 位（让两个守卫对同一个字段
说同一句话）我没有顺手改——那是另一件事，已写进 ERR-279 的 `remaining_boundary`。

同一轮里还有一条不需要改代码的判据要落字：`config/client-evidence.json` 里 DSH 的 `version`
仍是 `0.2.0-rc.2`。这不是遗漏——该文件顶层 `generated_at` 是 2026-09-02，其 DSH 段的正文自己写明
是 2026-10-13 那次观测的逐字记录，而且**没有任何脚本或门读它**。声明基线的唯一权威是
`config/adapter-registry.json` 加上免启动探针回执；把一份带日期的历史快照当成现行声明去"改齐"，
就是给它凭空造出第二份真相。所以这里做的是判据而不是编辑：它保持为历史观测，`ERR-278` 的
`remaining_boundary` 已把这个处置写死。

写账本时用的护栏值得留一句：追加前先断言 `json.dumps(..., indent=2)` 与磁盘字节完全相等
（第一次断言就因为我漏了文件末尾那个换行而失败，没有把整份账本按生成器的形状重写），
确认这是"只在数组尾部加两项 + 改 summary 计数"的最小改动，而不是格式化重写。
`ERROR_LEDGER_PASS entries=278 classifications=14 counts_consistent=true`。

## 16. 云端判决把同一课教了两遍：改过的字节，所有读它的回执都要重测（2026-10-20）

三次推送的判决逐份对齐（红名单来自作业自己上传的 `ci-summary-*` 回执，不是猜的）：

| head | workflow-assistance 红成员 | integration |
| --- | --- | --- |
| `5c54b5f6` | `test_deepseek_harness_keeps_its_older_dated_readback`、`test_the_shipped_bindings_are_valid`（共 2） | 红 |
| `a9110584` | `test_registry_is_fail_closed_and_traceable`、`test_the_pinned_registry_is_the_one_the_commit_carries`、`test_the_unbound_count_is_the_ledger_own`、`test_records_with_a_gone_guard_are_named_not_absorbed`（共 4） | 红 |
| `ea7fa3a0` | 同上 4 个成员，逐字一致 | **绿** |

先说好消息：`5c54b5f6` 的两枚基线红被 `a9110584` 真的修掉了（日期钉换成来源形状规则、
ERR-276/277 落了 `fixedCommit`），`integration` 作业在 `ea7fa3a0` 转绿——这两件都有回执可查。
再说这一课的第二次：那 4 枚红**没有一枚是产品缺陷，全是"我改了字节却没重测读这些字节的回执"**，
和 §15 那条 ERR-279 是同一件事，只是换了字段。逐条归因（每条都在本地先复现再修）：

- `tests/workflow-assistance/test_adapter_registry.py`：`ADAPTER_REGISTRY_FAIL Additional properties
  are not allowed ('reproducible', 'not_reproducible_since', 'not_reproducible_verdict' were
  unexpected)`。这是四处里唯一一处**必须改合同**的：`ERR-278` 立的是"读不到要写成具名状态"，
  而 `packages/contracts/schemas/workflow/adapter-registry.schema.json` 的 `version_readback`
  是 `additionalProperties: false`——门要求的那个字段，合同不许存在。于是在 schema 里把三兄弟
  按各自语义声明出来（`reproducible` 布尔、另两个是必须非空的字符串，描述里写清"这是
  '数不对' 之外的第二种状态"）。改完 `CONTRACT_CATALOG_PASS contracts=45` 与
  `CONTRACT_SSOT_PASS` 不受影响，说明这三个属性落在既有 contract 之内、没有新增影子合同。
- `tests/workflow-assistance/test_executor_live_probe.py`：回执把 `registrySha256` 钉在改钉之前的
  注册表上（`4be802ef…` 对不上树里的 `a4499aa0…`）。这条门当初就是为了"回执必须说得上是这份注册表"
  而写的，这次它正确地拒绝了我自己的新声明：用 `--no-launch` 重跑 `scripts/audit/executor_live_probe.py`
  重发 `docs/audits/EXECUTOR_LIVE_PROBE_2026-10-20.json`——GUI 客户端记成 `PROBE_SKIPPED_NO_LAUNCH`，
  仍然没有拉起任何界面。
- `tests/workflow-assistance/test_ledger_unbound_triage.py`（两枚）：ERR-276/277 拿到 `fixedCommit`
  之后，"PASS 但没有绑定"的池子从 96 缩到 94，而 `docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json`
  还写着 96。重跑 `scripts/audit/triage_unbound_ledger_records.py` 后 `unboundPass 94`，
  PATH_GONE 那一组也跟着对上。

顺序教训不再是道德劝告，而是有名字的：**`tests/ci/test_shipped_projections_are_current.py`（11 例）覆盖的
那几张回执我重测了，没覆盖的两张（执行器探针、未绑定分诊）就没测**，而它们各自都有一条门在读——
CI 把这套门全跑，本地挑着跑，差值就是这 4 枚红。`services/orchestration/run_quality_gate.py governance`
这一批是把 `tests/workflow-assistance` 下全部强制模块一次跑完的组，改到账本/注册表/schema 这类
多消费者字节之后，该跑的是它而不是自选清单；本轮已在同一棵树跑过一次并把结果记在下面。

在同一棵树上把 `governance` 这一批跑完：**`Ran 2742 tests`，只有 1 枚红**，而且是一枚只在本地存在的红——
`tests/workflow-assistance/test_temp_fixture_residue_is_bounded.py` 的
`test_no_orphaned_fixture_is_older_than_the_floor` 报出 62 个超过 6 小时地板仍未认领的临时 fixture 根
（`a174`、`h175`、`nf23-install-*`、`nf24-tree-*`，1.7 MiB，`nested_git=0`）。先跑 dry-run 拿到清单
（`docs/audits` 之外，落在 `.project-local/artifacts/temp-residue-reclaim/` 的 manifest），再 `--apply` 释放：
`TEMP_RESIDUE_RECLAIM applied=1 dirs=62 freed_bytes=1775959 failures=0`，该模块随后 5 例全绿。
另外必须记一句我自己的操作错误：第一次跑这批的时候我在它运行期间编辑了本文档，回执因此写的是
`GATE_SOURCE_DRIFT=yes`——一次带漂移的 PASS/FAIL 都不能当作终审，清理完 residue 之后必须在不再改动的前提下重跑。

## 17. 两条门要的东西互相矛盾，本轮把它量出来并选了一边（2026-10-20）

`services/orchestration/run_quality_gate.py root-governance-suite` 在本地报出 **3 枚红**，而云端从没报过它们——
原因正是 CI 第 5 步那条命令链停在第一枚红（`governance` 先跑、先红），后面的组根本不执行。
第一次跑连"3 枚"都读不全：`scripts/ci/run_root_governance_suite.py` 在打印失败明细时自己死于
`UnicodeEncodeError: 'gbk' codec can't encode character '\ufffd'`，`modules_failed=3` 后面只跟着一条明细。
这和 `services/orchestration/run_quality_gate.py` 开头记的是同一个坑，修法也一样：父进程把 stdout/stderr
重设为 UTF-8 且 `errors="replace"`（子进程输出里的替换字符是**解码结果**，必须保住；错的只是控制台编码）。
判决打印不出来就不是判决。补完之后 3 条明细才第一次同时可见。

三条各自的判据：

1. **`tests/ci/test_sidecar_documented_launch.py`**：文档里那条 sidecar 启动命令其实跑通了
   （`WORKFLOW_SIDECAR_READY`、`/api/v1/snapshot` 回 200），红在**拆除**：
   `PermissionError: [WinError 32] ... canonical.sqlite`。仪器量了时序——子进程在 t=0 被收尸，
   它的 `runtime/canonical.sqlite` 仍然锁到约 **250 ms** 之后才释放，于是立即删目录必输。
   Linux 允许删除仍被打开的文件，所以云端永远看不见这一类红。
   修法不是加一句 sleep：`release()` 有界重试（12 × 0.25 s），**预算用完仍然锁着就 raise**，
   不 `ignore_errors`——静默留下的残骸在这里不可见，几天后由
   `tests/workflow-assistance/test_temp_fixture_residue_is_bounded.py` 的地板门替我数。
   同一处还顺手纠正一个边界违规：它把沙箱写在 `%TEMP%`（`C:\Users\ALEX\AppData\Local\Temp\tmp*`），
   而本仓的机器合同要求一切产物留在 Git 根内，现在写 `.project-local/runs/sidecar-launch-tests/`。
   两条反例把"有牙"证明出来：只失败一次的删除必须重试到成功（恰好 3 次），永远锁着必须 raise 并报出目录名。
2. **`tests/ci/test_frozen_surfaces_are_intact.py` 与 `tests/ci/test_stale_surface_paths_are_gone.py`**
   一起红，且是**同一处内容改动**造成的：`3ee7fed5` 把
   `docs/history/archive/ui-priority-20261009/UIV2-INTERFACE-BINDING-MATRIX.csv` 里一个腐烂的行号指针
   （`apps/observer/frontend/src/lib/evidenceRange.ts:132`→`:140`）就地重钉了。而这个归档被两份哈希记录
   分别钉住（`docs/history/archive/FROZEN-MANIFEST.json`、`docs/history/archive/MOVED-PATHS-20261019.json`），
   同时 `scripts/ci/repoint_source_pointers.py` 的**默认目标就是这份已冻结的文件**——
   也就是说：一条门要求行号指针永远跟代码对齐，另一条门要求这些字节永远不许变。**两者不可能同时为真**，
   只要源码往上加一行，指针门就会命令我去破冻结门。这正是
   `docs/history/archive/MOVED-PATHS-20261019.json` 自己写的判据
   （frozen history 的旧路径是那句话的历史宾语，"改它会让一条有日期的记录说不实的话，所以移出扫描种群"）
   被违反的现场。
   本轮选的边：**冻结优先**，把 CSV 字节按两份记录共同的 `a1f5eb3be534…`（44,208 B）复原，
   复原前先 `git cat-file` 证明 `3ee7fed5^` 与 `c76f5e2e` 两个 blob 都等于该值、并把当前字节留成
   可回滚副本。根因守卫加在工具里：被任一哈希记录钉住的路径一律
   `REPOINT_FROZEN_REFUSED` 并退出 1——指针可以修，但不能用破冻结的方式修；默认种群改成
   **由 git index 枚举的活文档面**（`docs/current/**`、`taskpacks/current/**`、`WORK-LAB-AUTHORITY.md`），
   手写清单从此不再是输入来源。
   今天这个活文档面里"带引号的代码引文"是 0 条（`REPOINT citations=0 landed=0 drift=0 narrative=67`），
   所以一条对空种群的绿什么也没证明——新加的植入反例把牙找回来了：写一条行号错位但引文可定位的活引文，
   检查模式必须 `DRIFT` 且退出 1。另两条反例断言默认种群不含 `docs/history/`、且那份 CSV 确实还在
   冻结集合里。`tests/ci/test_source_pointers_are_current.py` 由 3 例变 **5 例全绿**，
   两份冻结门随后也绿。
3. 一处读数陷阱值得留字：这三条完整性门**不同源**——两条读暂存区 blob，一条读 `git show HEAD:path`。
   于是"已 `git add` 但未提交"的复原会给出互相矛盾的判决（冻结门绿、移动记录门红）。
   这不是缺陷，但只要按本地部分绿就宣布收口，就会把一个还没生效的状态当成已生效。

补一件当时还不知道的事：`bd043222` 之后 `governance` 全批又报出一枚红，说明对同一份字节提要求的不是两条门而是
**三条**。第三处在 `tests/workflow-assistance/test_ui_v2_csv_citations_resolve.py` 的
`test_every_line_pointer_lands_on_the_code_it_quotes`——它读 checkout，所以它命令两份冻结表永远跟踪 HEAD。
这一枚本地全批才量到、云端从未报过（还是第 5 步链停在第一枚红那个机制）。解法不是再改字节，也不是关掉这条门，
而是**把判读基准换成这条记录自己的署期**：按 `docs/history/archive/MOVED-PATHS-20261019.json` 里每条移动各自记的
`measuredAtHead`，用 `git cat-file -e` / `git show <commit>:<path>` 取当时的 blob 来验。断言因此从"今天也对"
升级为更强的"这份有日期的记录在它署名那棵树上准确"（两份表的每一条行号引文在 `983bf571` 全部落在自己的引文上，
8 例全绿）；若某条移动没有 `measuredAtHead`，测试直接 raise——没有署期就没有判读基准，不允许悄悄退回 checkout。
这就是 §14 那条"数不对 / 读不到是两种状态"的同一形状：**"当时对" 与 "现在还追得上" 也是两种状态**，
把它们混在一条门上，门就只能命令人去改历史。



## 18. 上游红修好之后，下游那枚旧红才第一次露脸（2026-10-20，head `6f70e164`）

`6f70e164` 的 exact-SHA 判决：`integration`、`token-monitor`、`supply-chain-security` 全部 success，
`workflow-assistance` 仍然 failure。这一次红**不是任何一条测试成员**——作业上传的
`ci-summary-workflow-assistance` 与 `gate-stages` 两份回执里 `failing_members=0`，
而 `gate-stages` 的 `failed_gate` 写的是 `security`，判定身份是 PR #178 的合并提交
`75a2193dc69d9abc55430eaaf06939585ead12df`（tree `c64afb0bc957a378221a5ab5211c07556acfbca3`）。
本轮用来读红名单的那个脚本只匹配 `FAIL:` / `ERROR:` 两种行，对这种"非测试组失败"完全无感：
**读不到成员不等于没有失败**，必须去读 `failed_gate` 那一个字段，这也是它自己报 exit=1 的地方。

`security` 组在本机 0.8 秒复现，报出 7 处 git 的 at-花括号 revision 简写未加引号（PowerShell 会把它解析成
哈希表字面量），全部在 §13 那段"两条本地 stash 的判据与退役"里——那是 2026-10-20 早上写下的文本。
前面三次推送都没报它，原因还是 §17 第 0 条那个机制：**CI 第 5 步是一条 shell 链，停在第一枚红**，
`governance` 一直先红，`security` 从未执行。我把上游修绿，它就把自己的旧红抬给我看。
这和 ERR-261/263/264 记的是同一件事的第三个面：链式步骤的"绿"只代表"前面的都绿"。

处理不是加引号糊过去，而是把两条 stash 改按**它们各自的提交对象**称呼（`fbb97053…` / `9d393d9f…`）：
drop 之后旧索引号已经不再指向任何东西，写索引号是一句现在读不出来的话，而 SHA 是那句原意现在的真说法。
改写过程自己又踩了一次——解释"为什么要避免这个形状"的那半句里把字面量原样写了出来，被同一把门第二次拦下，
第二次才改成纯文字描述。这条教训值得留：**否定某个写法的句子，本身也可能是那个写法**。

随后把 CI 第 5 步链上的组**逐个**跑（每组单独要一份判决，不再靠链的传递）：
`security` / `compile` / `runtime-convergence` / `skill-provenance` / `context-pack` /
`client-neutral-manifest` / `core-schemas` / `capability-matrix` / `model-registry-integrity` /
`adapter-conformance` / `protected-drives-consistency` / `external-libraries-index` / `policy-coverage` /
`observer-readonly-boundary` / `evidence-tiering` 十五组全部 `QUALITY_GATE_PASS`，
`governance` 与 `root-governance-suite` 也各自在同一棵树上重跑通过。

## 19. 两条门在作者的机器上为真、在干净检出上为假（2026-10-21，head `a012d073`）

`a012d073` 的判决：`observer` / `integration` / `token-monitor` / `supply-chain-security` 全部 success，
`workflow-assistance` 仍红，红的位置从 `gate-stages` 的 `failed_gate` 读出来是
**`root-governance-suite`** ——也就是 §18 那条链再往下挪了一格才第一次执行到的组。
明细这次是完整的（ERR-281 修好打印之后第一次能一次读全）：`modules_ran=55 modules_failed=2`。

两枚红都不是逻辑错，而是**断言写在了作者的宿主上**：

- `tests/ci/test_observer_launcher_chain_is_runnable.py`：`AssertionError: 0 != 60 —— a lone-LF line in a
  .cmd can silently skip its body`。`apps/observer/start-observer.cmd` 在仓库里存的是 **LF**（blob 60 个
  `\n`、0 个 `\r\n`），Windows 工作树里我看到的 60 个 CRLF 是 `core.autocrlf` 替我转换的结果；
  `*.cmd` 没有 `.gitattributes` 条目，于是干净检出（Linux runner）拿到就是 LF —— 一键启动脚本在那台机器上
  是真的会被 `cmd.exe` 跳掉正文的。这不是"测试太严"，是**被观察的产物本来就是坏的**，只是作者的宿主替它遮了一层。
- `tests/ci/test_stale_surface_paths_are_gone.py`：1 failure + 2 errors，读的是
  `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`。该文件按策略路由给 LFS
  （`*.zip filter=lfs`），而 workflow 的 `actions/checkout` 没有 `lfs: true`，所以作业盘上那 135 字节是
  **指针文本而不是 ZIP**：`zipfile` 抛两次异常，另外一处把成员哈希对不上。一件前置条件缺失，报成三件事。

修的是宿主无关性，不是断言强度：`.gitattributes` 加 `*.cmd text eol=crlf` 与 `*.bat text eol=crlf`
（改后 `git ls-files --eol` 对三个受跟踪的批处理入口都读出 `i/lf w/crlf attr=text eol=crlf`），
跑 root suite 那个作业的 checkout 加 `lfs: true`；两个 ZipFile 直开换成 `open_archive()`，
前置条件缺失时按名字报 `LFS_NOT_FETCHED` / `ARCHIVE_MISSING`。同时把"一个文件"扩成"一族"：
新增的用例从 git index 枚举全部 `*.cmd` / `*.bat`，逐条要求工作树没有孤立 LF **且**声明了 `eol=crlf` ——
后者是关键，因为字节是宿主的函数，属性才是树的函数。两个模块从 7 例、19 例变成 **8 例、21 例全绿**，
另外补了两条植入反例（假指针文件、不存在的归档），证明新守卫会自己开火。
CI 侧的 CRLF 与 LFS 取回只能由下一次 exact-SHA 判决证实，这条留在 ERR-283 的 `remaining_boundary` 里。

最后把 CI 第 5 步那个 shell 块**拆成 46 条命令逐条要判决**（脚本读 workflow 的 YAML，把 `python ...` 行
全部单独跑一遍；第一次跑 46 条全红，因为我把带空格的解释器路径插进了 shell 字符串 —— 修成 argv 之后才是真数据）：
`red=3`，三条同因 —— 我改了跟踪字节而没重发 `.project/governance/generated/CURRENT_STATE.json`，
于是 `test_current_state_projection_is_fresh`、`--check-current` 以及引用它的
`tests/ci/test_ci_invoked_verifiers_have_a_local_route.py` 一起报 `source-digest-mismatch`。
这正是 §16/§17 写过两遍的那件事的第三次显形：**改了字节就要重发所有读它的记录**，
这次轮到界面投影自己。重发后三条一起转绿。

## 20. 这一轮的红数落到 0：`9fbaf09a` 的 exact-SHA 判决（2026-10-21）

`gh run view 39490182776`（event=pull_request，head `9fbaf09aae9ec8e942df8883bffdfcabe4cff04c`）：
**七个作业全 success** —— `gate-plan`、`workflow-assistance`、`integration`、`observer`、`token-monitor`、
`supply-chain-security`、`aggregate`。`gate-stages` 回执写 `exit=0`、`failed_gate=null`，
判定身份是 PR #178 的合并提交 `bfdf2003245884d63df523121b34bc5468af1b91`，
其 tree 为 `9125bffda55f0738785ba79b212c044ab4ca2a2d`，与 head 自己的 tree **逐字相同**
（`gh api repos/.../commits/9fbaf09a` 读出同一个 tree），所以判的就是这棵树，不是别的合并结果。
这一条等价关系必须写在记录里：只看"作业绿"不够，绿的可能是一个含别人改动的 merge tree。

从 `5c54b5f6` 到这里的红数变化，逐份可对账（红名单来自各 head 自己上传的 `ci-summary-*` 与 `gate-stages`）：

| head | 红在 | 成员数 / 组 |
| --- | --- | --- |
| `5c54b5f6` | workflow-assistance | 2 个测试成员（integration 在这一格还是绿的） |
| `a9110584` | workflow-assistance + integration | 4 个测试成员（改字节未重发回执） |
| `ea7fa3a0` | workflow-assistance | 同样 4 个成员；integration 转绿 |
| `6f70e164` | workflow-assistance | `failing_members=0`，红在 `failed_gate=security`（散文里的 PowerShell 危害形状） |
| `a012d073` | workflow-assistance | `failed_gate=root-governance-suite`，`modules_failed=2`（宿主相关断言 + 未取回的 LFS 对象） |
| `9fbaf09a` | —— | **0** |

值得留的是最后两格的**形状**：它们不再是某条测试失败，而是"整组失败但没有成员名"——
读红名单的工具只认 `FAIL:` / `ERROR:` 两种行，对组级失败完全无感，必须去读 `gate-stages` 的
`failed_gate`。把这条写进门的设计里，下一轮遇到同类红时不会又"读出一张空表"当作"读过了"。

本轮还留了三条对"链式步骤"的实证（§17 ①、§18、§19 末段）：CI 第 5 步是一条会在第一枚红处停住的 shell 块，
所以一个 head 的"绿"只说明它前面的都绿；我因此把那个块拆成 46 条命令逐条要判决，
才在同一轮里把 `security`、`root-governance-suite`、CURRENT_STATE 陈旧这三件一次看全。

本地配套读数要说清是哪棵树：`governance 全批 Ran 2742 tests 0 红`、`root-governance-suite 55 模块 PASS`
是在 `9c285d71` 之前那一次（修完 host-shape 断言、写 §19 之前）量的；最后的 `9fbaf09a` 之后我只重跑了受改动
直接读取的那些门（绑定 10、分诊 8、探针 15、投影当前性 11、清单覆盖 12、引用审计 12、
`ERROR_LEDGER_PASS entries=282 classifications=14`、LIVE_DOC_PATHS 831 missing=0、
DOC_CITATIONS rewritten=0 blocked=0）。**整链的全量批跑是在云端那一棵树上完成的**，
`workflow-assistance` 绿即代表 CI 第 5 步那条链上我从 YAML 解析出的 46 条 python 命令在 `9fbaf09a` 的树上
全部退出 0（那个块会在第一枚红处停住，所以走完 = 每条都返回 0）——
这比本地再跑一遍同一条链更强，因为它跑的是判定身份那棵树。
本地与 `origin/docs/handoff-20261018-qoder` 同步：本次提交之前的 HEAD 即 `9fbaf09a`，无未推送提交。

仍未闭合的（都不是本轮可以自行批准的）：PR #178 合入 `main` 由 owner 决定；
浏览器扫掠接入 CI（实测一趟 69 秒）与继续提高采样预算由 owner 决定；
`config/client-evidence.json` 里 DSH 的 2026-10-13 逐字观测保持为历史快照，理由写在 ERR-278 的
`remaining_boundary`；DSH 那份 225.65 MB 的安装回滚副本删除仍属 owner。
**这一段的前三项已被 §21（2026-10-22）按 owner 的全量授权闭合，第四项按实测改判为「对象未能定位，
不删除」；保留原文是为了让读者看到判断是怎么变的，而不是把它抹平。**

## 21. 全量授权轮次：两条缺陷修到产品里，一条被证伪的结论被更正（2026-10-22）

owner 本轮指令逐字：「全部授权 静默执行 不要打扰我要授权 以闭环为目标 完成所有未完成的任务」。
上一轮交接的 7 项待办因此全部推进，其中 2 项以「按实测改判」闭合而不是以动作闭合，逐条写明。

**先复测基线**：`HEAD == origin/docs/handoff-20261018-qoder == a5f14d6980cf82898fa9965f6902f5b2ed8d9512`、tree
`76ca3f4dc27b92d7ec2801f09f39cefe9b697dd2`、脏改 0、stash 0、`main == origin/main == f6077d18…`、
`feat/w06… == 8f6540df…`。两处交接数字要更正：run 39493527142 的 check-run 是 **12 枚全 success**（不是 10），
`tests/ci/test_text_legibility_gate.py` 是 **57 例**（`unittest discover` 实测 `Ran 57 tests / OK`，不是 12），
而且这 57 例已经在 CI 里跑（`.github/workflows/work-lab-gate.yml` 的 root-governance-suite 按 glob 自选发现）。

**owner 送来的独立闭环审计包**（登记为 `WL-REC-0106`，sha256 `09e16ad3…`，72,322 B，包内 28 个成员逐个登记）
先按登记规程比对：与登记册既有 105 条 SHA-256 无一碰撞，是新来源不是别名。包里 9 条 findings 逐条复核：
WL-01 成立（`compare main…a5f14d6` = ahead 50 / 变更 260 个文件，其中 100 个非文档字节，而 PR #178 标题仍写
docs(handoff)）；WL-03/04/05/07、IF-01、OSS-01 的数字全部对上（Control 13 个操作只有 3 个 implemented，
来源账 17 条 = 2 local-verified + 15 not-implemented，跨模块 33 条全未实现，导航 9 组 31 入口且初始全展开）；
包内程序一个都没执行。

### WL-02（P0）：证据摘要假通过，修在产品里
后端 `packages/client-neutral-core/scripts/evidence_range_reader.py` 把调用方给的 `expected_digest`
与同样是调用方给的 `whole_digest` 相比，从不哈希文件本身；`services/orchestration/sidecar.py` 的两个值都取自
URL query，所以整条链是「调用方 vs 调用方」。前端 `apps/observer/frontend/src/lib/evidenceRange.ts` 更直接：
判定函数把结果体里同一个字段读两遍当作两侧，于是任何 status OK 的响应都得 AGREE，界面还写
「返回字节属于被记录的那份产物」。本机独立复现：写一个真实 sha256 为 `e679f17a328e34b0…` 的 fixture，
两个参数都传 `a×64`，照常返回内容并判 AGREE（回执
`.project-local/runs/wl02-repro-20261021/digest-witness-backend-local.json`）。

修法是取消「调用方可以声明实际摘要」这件事本身：读取器在被要求核对身份时自己流式实测整文件摘要，
比较基准只有这一个来源；超过 16 MiB 明说不可核验（新增 `IDENTITY_TOO_LARGE_TO_MEASURE` 拒绝并返回空内容），
而不是静默读全量。结果体把声明值、实测值、来源、verified 拆成四个字段，界面分两格显示
「钉住摘要（调用方声明）」与「实测摘要（读取器计算）」。删除了因这次改动才变得不可达的旧拒绝码，
并补 `tests/ci/test_evidence_reason_codes_are_one_list.py`（6 例）——两侧判定码表此前没有任何东西钉住，
客户端手抄一份镜像，这正是旧码能活到今天的原因。

守卫数量是实测的，不是承诺的：把读取器的实测基准换回调用方提供的摘要，**7 例判红**（含审计包原探针、
改文件后旧身份失效、真 HTTP 路由复现），随后逐字节恢复（sha256 前缀 `b4ee5218`）；
把前端判定改回同一字段自比，**2 例判红**后逐字节恢复（前缀 `0a029b58`）。

### §20 那条「3.26 秒在页面一侧」被自己的仪器量死了

见上一节「门自己崩了比界面坏了更难发现」里的更正：真实三段是 A 快照解析 150/161 ms、B React 提交 59.5/66 ms、
C 到首可见 54.5/58 ms，合计 navStart→行在 DOM 207.5/222 ms，而仪器第一次能看页面是 3.2 秒之后。
顺带量到的产品事实不是延迟而是几何：把手块提交时行列表起点在视口下方 216 px，列表高 23,056 px 未虚拟化，
滚过去之后可见比例只有 2.2%。本轮把这条**判成几何问题并加断言**，没有擅自改界面布局——把 200 行改成
窗口化渲染是产品决定，落在 §21 末尾的待批清单里。

### 采样预算：以证据闭合，不再追问 owner

上一轮交接把它列为「owner 定标准」。实测读回可以直接回答：`every_scrollable_range_was_traversed`
已把「每一段滚动范围都在某个采样步骤上过屏」变成判红条件，本轮重跑仍是 **566/566 站全部走完、无短程泳道**。
把手块的 200 行生活在同一个可滚动范围里，被走完就等价于每一行都上过屏，所以「地板与 AA 覆盖到每一行」
这条标准**已经成立且被门保护**；而 3,923 个 distinct 读数对 8,006 条存在叶子文本的比例不是覆盖率——
合并按（路径、文本、字号、字重、颜色）去重，重复单元格文本本就该只算一次，把它当行数看是误读。
据此判定：不再提高预算，distinct 数继续作为报告量而不是验收量。

### 逐泳道浏览器扫掠接入 CI

`.github/workflows/work-lab-gate.yml` 的 observer 作业在几何门之后新增一步
`python scripts/audit/text_legibility_via_cdp.py --all-views --live-backend --sizes 1280`。
代价是实测的而不是估的：本机两主题 × 31 泳道 × 566 站 = **70 秒**
（回执 `.project-local/artifacts/wl02-and-handle-20261021/legibility-ci-shape.json`，
全部判绿：0 低于地板、0 AA 失败、0 不可解析颜色、0 短程泳道）。
exit 3 是 NOT_RUN 且**故意让它红**——没量到的标准不算通过。回执自己绑包体哈希，
所以判决说的是它加载过的那份字节。

### 两条按实测改判、不执行的动作

`config/client-evidence.json`：本轮用只读检索确认它除文档与账本引用外**无任何脚本或门读取**，
顶层 `generated_at` 仍是 2026-09-02，现行声明唯一权威仍是 `config/adapter-registry.json` 加免启动探针回执。
把它"现行化"要凭空造第二份真相，因此**保持原样**，判定记在这里与 ERR-278 的 `remaining_boundary`。

DSH 的 225.65 MB 安装回滚副本：**未能定位，故不删除**。按 ERR-087 的解析方法读卸载注册表项，
`InstallLocation` 就是活安装根 `C:\Users\ALEX\AppData\Local\Programs\DeepSeek Harness`（0.2.1-rc.2），
该根下只有 `locales` 48.30 MiB 与 `resources` 675.36 MiB，合计 1,043.31 MiB，没有 `$Uninstall` 目录，
也没有任何接近 225.65 MiB 的对象；在 `%LOCALAPPDATA%` 与 `%TEMP%` 的有界扫描里同样没有。
一个找不到对象、收益只有磁盘、且不可逆的动作不在本轮执行——这是按证据改判，不是没做。

### 本轮验证与提交形状

到写这一段为止是三个提交：`04eec5ec…`（产品修复 + 仪器 + 守卫 + 文档更正 + CI 步骤 + 同批重发的派生记录）、
`c1f38188…`（审计包登记 + 入库归档不走 LFS 的有范围例外）、
以及账本提交（`ERR-284`、`ERR-285`，两条 fixedCommit 都指向第一个提交，
`LEDGER_FIX_COMMIT_BINDING` 读回 `promiseInTree=True / verified=PENDING`）。
推送后 runner 又量出一条新的红，追加的两个提交与它的归因见 §22。
改跟踪字节前跑的门与改后重发的记录：`TOOL_INVENTORY`（初量 `trackedTools=79 withLedgerPromise=20 unclaimed=0`，
本轮结束时实测为 `withLedgerPromise=21`，见 §22——同一个数在自己一轮里就变了两次，
这就是"派生记录必须由最后一个写者重发"的实证）、
`PROJECT_LOCAL_CITATION_AUDIT`、`CURRENT_STATE`、三个账本派生审计；
`ERROR_LEDGER_PASS entries=284 classifications=14`（§22 又加了一条，终值 285）；前端 `npm run typecheck` 干净、
`vitest` 68 文件 826 例全绿；后端定向模块 `tests/workflow-assistance/test_evidence_range_reader.py` 30 例、
`tests/ci/test_handle_latency_attribution.py` 15 例、`tests/ci/test_evidence_reason_codes_are_one_list.py` 6 例全绿。
`scripts/maintenance/release_temp_fixture_residue.py --apply` 释放 3 个孤儿临时根共 2.0 MiB（清单落盘），
`§12` 里那条长期红的 `tests/workflow-assistance/test_project_local_citation_audit.py` 本轮 **12 例转绿**——按文档顺序
「先重发派生审计再清残料」做完，而不是绕过它。

仍待 owner 的只剩两件：PR #178 合入 `main` 之后的 main-SHA 重锚，以及把手块 200 行是否改成
窗口化/默认可达（本轮只加断言与几何事实，没动布局）。

> 这句写下之后，第一件已经完成：§22 记了 PR #178 的合并提交与 main 自身运行的绿，`ERR-284/285/286`
> 的 `verifiedCommit` 已钉住。剩下的一件仍归 owner。

## 22. 合入与合并后的独立判决：中间那枚红是 runner 的冷启动（2026-10-22）

> 标题里"runner 的冷启动"是写下这一段时的说法，保留原样以留下判断被修正的过程。按本轮末尾的实测：
> 几何门那一步的缺陷与宿主无关——引导用固定 sleep 代替就绪条件，这个事实在每个宿主上都成立，
> 只是在慢宿主上才现形；而扫掠那三次红的机制是两层超时不一致，也不是冷启动。

PR #178 于 2026-10-21T17:59:36Z 合入，合并提交 `b6f41e99d8ecf53a2c7e33458f9c7ff1f46ee5fc`。
合入方式是一次有理由的偏离：本仓此前四个已合并 PR 的合并提交都只有一个父提交（squash），本轮改用
merge commit。原因是 exact-SHA 判决的可追溯性——CI 判绿的是 `c0f5bf21`，squash 会把它替换成一个
CI 从未运行过的新 SHA 放进 main，而"合并后不得沿用分支 CI 冒充合并后的验证"正是本轮要守的那条；
merge commit 让被判绿的整串提交留在 main 的祖先里。逐个实测确认：
`git merge-base --is-ancestor <sha> origin/main` 对 `04eec5ec`、`c1f38188`、`bf097f45`、`79f48a54`、
`6f753f19`、`c0f5bf21` 六枚全部为真；分支未删除，账本按 SHA 引用它们。

**中间那枚红不在产品里，在仪器的等待里。** 第一个推送的 head `79f48a54` 的 run 39642405874 判 failure：
observer 作业里既有的几何门第一步 exit 1，`full` 视图所有选择器量不到东西
（topbar `element=MISSING`、brand=None、rail=None、content `{absent:true}`），
而同一个作业里紧随其后的 compact 与 floor 两个会话在同一份包体上量到正常数字（gap=130 / gap=404），
同一份包体在本机三视图全绿。根因是共享引导 `serve_and_eval` 用固定 sleep 代替就绪条件
（2.0 s 等端口 + 0.4 s 等 reflow + 1.0 s 就 evaluate），预算写的是开发机的启动时间，
487 kB 的包在冷 runner 上还没挂载就被量。记为 ERR-286（分类 ci_tooling），修成有界就绪轮询
（等 `.app` 出现，预算 24 s、0.5 s 一跳，超时必须返回 False），并把等待本身随数字返回
（`readyWait={ms,mounted,selector,budgetMs}`）。守卫 `tests/ci/test_cdp_harness_waits_for_mount.py` 10 例，
其中一条结构断言钉住 `serve_and_eval` 仍保留截图分支——第一版草稿把那行 `sleep` 连同 `shot` 分支
一起删掉了，这条断言正是为抓住它写的，也确实抓到了。本机重跑三视图 `GEOMETRY_GATE_PASS`，
`readyWait.ms=0 / mounted=true`（本机本来就快，量不出等待是正常结果而不是缺陷）。
诚实的边界：runner 侧那一步究竟等了多久，没有任何上传产物能回答（这一步的收据不在
`ci-summary-observer` 里），能引用的只有"同一步骤、同一族包体，`79f48a54` 红、`c0f5bf21` 与
`b6f41e99` 绿"这一条前后对照。

**新接进 CI 的扫掠第一次在 runner 上给出判决**：`Text legibility sweep` 于 2026-10-21T18:17:02Z
`LEGIBILITY_GATE_PASS`，`every_scrollable_range_was_traversed stops=501/501 lanes_short=[]`、
`no_text_below_the_type_floor offenders=0`、`every_text_node_meets_AA aa_failures=0 invisible=0`、
`sampled=3574 present=6674`。runner 的分母与本机（566/566 站、3,923/8,006）不同，这是两个宿主上两次独立的量，不是同一个数被抄了两遍——
引用的时候必须带宿主。本机这一组出自 `.project-local/artifacts/wl02-and-handle-20261021/legibility-ci-shape.json`
（包体 `7626fd51…`）；同一轮里另两次量落在 565/566 站之间漂移，说明分母跟着快照数据走，不是常数。

**合并后的重锚**：`origin/main` 自己的 push 触发 run 39648708283（work-lab-gate）
与 39648708412（wlr-060-production-gates）均 conclusion=success，前者 7/7 作业绿
（`gate-plan / workflow-assistance / integration / observer / token-monitor / supply-chain-security / aggregate`），
几何门 18:15:38 判绿。`ERR-284`、`ERR-285`、`ERR-286` 的 `verifiedCommit` 钉到 `b6f41e99`——
钉之前先断言每行的 fixedCommit 都是它的祖先、该对象在库、非尾部行未移动、summary 计数未动，
再由
`scripts/audit/ledger_binding_readback.py` 读回三行 `verified=b6f41e99… promiseInTree=True`，
`ERROR_LEDGER_PASS entries=285 classifications=14 counts_consistent=true`。
main 的 SHA 不写进任何权威文件当常量：`project-authority-index.json` 的
`currentMainMustBeResolvedDynamically=true` 就是为这一刻准备的，读者自己 `git rev-parse origin/main`。

§21 里那两个后来变动的数（`withLedgerPromise=20`→21、账本 284→285）已在原段就地标注终值，
没有把它们改回"看起来一直对"的样子。

**这一段的判决还没结束，本仓新接的那一步在下一个 main head 上自己红了。** 合并 §22 之后的
`ed7b8fa6`（run 39655934262）判 failure：同一作业里几何门 18:57:00 已绿，而我新接入的扫掠报
`LEGIBILITY_GATE_NOT_RUN views/light at 1280px TimeoutError('timed out')`。修完 ERR-286 的"等就绪"之后，
同一份引导里还剩第二个隐式宿主常量：**等答案的 60 秒**——那是为"量一个壳"设计的默认值，
而整轨扫掠要在一次会话里点完 31 条泳道并走完每条泳道的每一段滚动范围。本机一个主题约 35 秒，
runner 只要慢过一倍就撞上；所以同一步骤在 `c0f5bf21`/`b6f41e99`/`66b710b2` 三次绿、在 `ed7b8fa6` 一次红，
取决于宿主快慢而不是字节差别。修法与守卫见 ERR-287：预算由调用方显式声明（300 秒）、写进取 receipt，
真实超时的拒收路径一字未动。教训的形状是：把一段采集接进 CI 之前，除了"本机跑多久"，
还必须回答"它每次求值被允许等多久、这个数字属于被测范围的哪一层"。

**上面那句归因也被证伪了，这本身是本轮最值得记的一条。** 再下一个 main head `9513c216`
（run 39663107318）第三次判红，还是这一步：几何门 19:52:33 判绿，扫掠 19:52:49 报
`LEGIBILITY_GATE_NOT_RUN views/dark at 1280px TimeoutError('timed out')`——**相差 16 秒**，
而 300 秒的应答预算不可能是 16 秒的原因。也就是说 ERR-287 把"一次有用的参数化"当成了"那次红的原因"，
而我当时并没有任何证据说明 raise 发生在哪一层：拒收点只 `print(repr(exc))`，traceback 被吞掉，
于是 main 上连着两次红都无法归因（ERR-281 那一族：判决存在，证据不存在）。修的是这两件事
（ERR-288）：两处拒收点补上 `traceback.print_exc()`，整轨会话包一层**有记录**的有界重试
（`run_views_session(attempts=2)`，失败逐次打印，成功那次把 `collected.sweepAttempts` 写进取收据，
两次都失败仍抛出、仍 exit 3）——同一份字节在 runner 上三次过一次红两次、且都发生在另一个浏览器会话
刚关闭的几秒内，开发机从未复现，这是启动竞态的形状而不是被测页面的形状；一次重试正是区分
"页面坏了"与"启动竞态"最便宜的判据。守卫 14→18 例。本机复跑两主题 `sweepAttempts=1`，快路径没有被重试掩盖。

为什么同一份 workflow 在 PR head 绿、在 main 红，本轮**当时**没有结论，两条 `verifiedCommit` 都留空，
等 main 重新变绿的那次运行。这一串的形状值得留着：一次"看起来合理"的归因（预算太小）连着写进账本和
权威叙事，被下一次红推翻，而推翻它的证据本来可以更早出现——只要门自己肯把栈打出来。

**第四枚红把上面两段的两条归因一起推翻，而它之所以可读，唯一原因是上一段刚补的栈。**
PR #181 的 head `ff3348bf`（run 39668208804）observer 作业仍红，这次打出的 raise 位置是：
`run_views_session → serve_and_eval 里的 evaluate → send → _recv_text → one_frame → recv → TimeoutError: timed out`，
并且 `attempt=1/2` 与 `attempt=2/2` 抛出**完全相同**的异常。同一份字节、同一宿主、两次同点同错——那是确定性
阈值到点的形状，不是竞态，所以 ERR-288 的假设同样错了。机制在共享引导的另一层：`ChromeCDP` 建连时把 socket
的**每次读**超时写死成 10 秒，而它的 `timeout` 字段只用于跳帧循环的 deadline。于是外层提到 300 秒，对一次
静默期超过 10 秒的表达式毫无作用：任何一次 recv 到点就抛。ERR-287 修的是可见的那一层，所以修不动；
本机从未复现，是因为开发机上没有这种静默期。上面那句"PR head 绿、main 红没有结论"到这里才有结论——
同一条路径的快慢决定静默期是否越过 10 秒，与分支无关，`cancel-in-progress` 与资源抢占都不是原因。

修法是把这个语义收成一个数：建连时的每次读超时就是调用方声明的应答预算，写死的 10 秒删掉。
守卫 `tests/ci/test_cdp_harness_waits_for_mount.py` 18→21 例（实测 21 例全绿，2026-10-22）：
用打桩记录真正传进建连的超时值，所以断言的是构造期的实际数字而不是源码字符串——声明 300 时 socket 必须
拿到 300、循环 deadline 与 socket 超时必须是同一个数、默认 60 仍是 60、以及构造里不得再出现写死的十秒。
把改动植回去，3 例判红，随后逐字节恢复并复验一致。本机复跑几何门与整轨扫掠均 PASS。
ERR-287 与 ERR-288 被推翻之处只写在它们各自的 `remaining_boundary` 里并点名本行，原始观察、根因与修复
字段一字未改——错误归因必须留在账上，它就是"没有 raise 位置之前不得写归因"这条规则的证据。

诚实边界两条：runner 上是否彻底不再红，只能由下一个 exact-SHA 判决说明，所以 ERR-287、ERR-288、ERR-289
三行的 `verifiedCommit` 都留空；而这层改动也让一次真正卡死的表达式现在要等满声明的 300 秒才失败，
CI 的墙钟代价由作业上限兜住，尚未按 runner 观测重算扫掠耗时。

仍不在本轮范围内、留给 owner 的只剩一件：把手块 200 行 / 23,056 px 列表是否改成窗口化或默认可达。
本轮交付的是断言与几何事实，不是布局决定。

## 23. 把"23,056px 无虚拟化"从散文变成回执里的数（2026-10-22）

上一轮交接把这条列成待办：几何事实已经量出来，但它只活在文档里。本轮把它落成仪器自己会说的数。

**实测事实**（回执 `.project-local/artifacts/wl02-and-handle-20261021/handle-latency-geometry-assertion.json`，
两个样本，包体随那次运行命名在回执里）：DOM 行数 200，快照提供的行数也是 200；列表高 **22,981 px**
对 **668 px** 视口＝**34.4 屏**，每行 **114.9 px**；首屏提交时列表在折叠线以下（`belowFoldAtCommit=true`），
滚动之后 `NOW_VISIBLE`。三段延迟在这一次是解析 155.5/161 ms、提交 61.0/62 ms、滚动到可见 37.5/38 ms，
总计 216.5/221 ms——与 §20 更正过的结论一致，仍然不是"页面慢"。

**要更正的数**：此前引用的 23,056 px 出自更早那份量
（`.project-local/artifacts/wl02-and-handle-20261021/handle-latency-attribution-v2.json`，同一台机器、
不同快照数据）。数字会跟着数据漂，这正是本轮不做成散文常数的理由：`handleGeometry` 逐样本报出
`rowsInDom`、`rowsServedBySnapshot`、`listHeightPx`、`viewportHeightPx`、`pxPerRow`、`viewportsOfScrolling`，
打印行也带上同样的六个数，所以任何"多少屏的行没虚拟化"的说法都必须由当次回执支撑。

**三条新断言**（都在纯函数 `problems()` 里，因此可在 CI 判红而不必开浏览器）：

1. 有 DOM 行但没有快照行数分母 → 判红："这些行没有可对照的总体，'每条把手都显示了'不成立"；
2. DOM 行数**大于**快照提供的行数 → 判红并点名两个数：多出来的行不是从投影读来的，是造出来的；
3. 列表高于视口而滚动根本没执行（`scrollOutcome == NO_SCROLL_HOOK`）→ 判红并报出像素与屏数：
   无虚拟化的尾巴没人量过。

反例守卫 15→23 例（实测 `Ran 23 tests / OK`，2026-10-22）：三条各一种坏样本，另加一条"480 px 短列表
不需要滚动证据"，证明断言不会把正常情形判红——只在真正的缺口上咬。

**判定**：这条泳道的 200 行不是"看不见"，是"要滚 34 屏才看完"，而逐泳道扫掠在两个宿主上都把每一段
滚动范围走完了（runner 501/501、本机 565 或 566/同数）。所以本轮的结论是**可达性已被量到、成本是线性的**，
不是缺陷；要不要窗口化仍是 owner 的产品决定，不是缺一条断言。

**一处真实的自我抓取**：第一版把辅助函数命名为 `geometry`，而 `main()` 里有一个同名局部变量装的是导入进来的
引导模块——真跑一次立刻 `TypeError: 'module' object is not callable`，而守卫套件全绿，因为它直接调那个函数，
从来没经过真调用点。补了一条结构守卫（用 ast 取模块级函数名与 `main()` 的局部绑定求交集，非空即红），
把旧名植回去当场 1 例判红并连带 18 例错误，随后逐字节恢复（`RESTORED_BYTE_IDENTICAL`）。
同一条红里还有一次操作失误：第一眼看成"exit 0"，其实是被 `| tail` 掩掉的管道退出码，改成重定向到文件再取 `$?`。

**残留噪声（如实记下，未修）**：本地静态服务在浏览器关闭时打了一条 `socketserver` 的
`ConnectionResetError` 回溯。它出现在读数之后、不影响退出码与判决，但它说明这一步的错误和真实缺陷共用
同一个输出流——下一次真要归因时得先把它认出来。

**合并后 main 自己的重锚**：`bf3e189c` 的 exact-SHA 运行 12 枚 check-run 全 `completed/success`
（两个 workflow 加两个 aggregate 都在内：`gate-plan`、`workflow-assistance`、`integration`、`observer`、
`token-monitor`、`supply-chain-security`、`aggregate`、`config-compiler`、`schema-fixtures`、
`observer-readonly`、`capsule-cli`、`wlr060-aggregate`），observer 里
`GEOMETRY_GATE_PASS`（21:17:13Z）之后 `LEGIBILITY_GATE_PASS`（21:18:37Z），两主题各 `stops=501/501`、
`sampled=3573` 与 `3575`、`present=6674`，且没有 `LEGIBILITY_SWEEP_ATTEMPT` 行——第一次尝试就走完，
ERR-288 加的有界重试没有救下任何东西，只是被证明无害。扫掠那一步在 runner 上的墙钟约 84 秒
（进步骤与出结果的时间戳相减），共享管道因此付得起。合并提交 `97c9758c` 让 `bf3e189c` 留在 main 的祖先里，
`git merge-base --is-ancestor` 对 `5758d5a4`、`ff3348bf`、`8504aa30`、`bf3e189c` 四枚实测为真。

main 自己那次 push 触发的运行（run 39678850519）7 枚作业全 `success`，其中 observer 里几何门 21:43:04Z 判绿、
扫掠 21:44:36Z 判绿：两主题各 `stops=501/501`、`sampled=3572` 与 `3574`、`present=6674`，地板与 AA 零违例，
日志里没有重试行，那一步的墙钟约 92 秒。三行账本（`ERR-287`、`ERR-288`、`ERR-289`）的 `verifiedCommit`
因此钉到 `97c9758c`——钉之前先断言每行的 `fixedCommit` 都是它的祖先、该对象在库、且除这三行外没有行移动、
`remaining_boundary` 是这三行里唯一变化的字段；钉之后 `LEDGER_FIX_COMMIT_BINDING` 读回三行
`verified=97c9758c… promiseInTree=True`，`ERROR_LEDGER_PASS entries=288 classifications=14 counts_consistent=true`。
被推翻的两条归因仍留在账上，只在各自边界后追加闭合说明，原文一字一字未改。

## 24. 问题中心的第一片后端：把计数变成可重读的问题（2026-10-22）

owner 本轮指令逐字：「现在你按照审计报告来做后端 前端我交给STITCH 做好了 再告诉给你接入」。
这份 STITCH 包（26,177 B，sha256 `a435ea93fe7bd57e…ba32399b`，10 名成员、包内 `SHA256SUMS.txt` 声明的 9 份逐份哈希命中）
锚在 `c35273c6…`，其 17 个来源文件的 sha256 **全部等于该提交里那些 blob 的 sha256**，
它对仓库的每条可机器核对的说法我也逐条复测过（267/31 文件差、定向 80 例 = 30+6+21+23、`apps/observer/frontend/src/views/EvidenceView.test.tsx` 实跑
29 例、`sources_scanned=83`、九组 31 入口、13 动词 3 实现、source-ledger 17 行 derive3/reference13/external-optional1
与 local-verified2/not-implemented15、候选池 22 行 1/1/5/15、九个深色令牌全在源码里），没有一条需要更正。
包本身仍是 `PROPOSAL_NOT_OWNER_APPROVED`，也**尚未登记进 owner 资料册**（登记要动跟踪字节，等一句话）。

它给的「闭环距离」第 2 行——问题中心 NOT_IMPLEMENTED——是本轮动的第一处。

**做的不是新计数，而是把已有事实变成能重读的问题。** `packages/client-neutral-core/scripts/issue_projection.py`
只读 canonical store 已经记下的东西（collector_health、telemetry_events、execution_instances、tasks），
产出 10 类闭合词汇的问题行：每行带 16 位十六进制指纹（同类同项目同主体折叠成一行，`occurrences` 是被折叠的源行数，
`foldedOccurrences` 说这次折叠真发生过）、`evidenceRef` 指回它来自哪张表哪一行，`priority` 必须连着
**产生它的那句规则**一起出现——规则表在模块里写死，不在界面里现算。它不做因果推断（`inferencePerformed=false`），
不带内容（`contentIncluded=false`，`detail` 有 160 字上限），也不写任何账。

三条反例形状是被守卫钉住的，不是被希望的：来源没答→键**缺席**并报出原因；读过且为空→`[]` 且 `complete=true`;
扫描被上限截断→`scanTruncated` 为真且 `complete` 不得为真。运行期 `snapshot_validator._validate_issues`
再拒四件事：清单没带 scope、scope 报的是没有的清单、指纹重复、行里夹带 `content`/`payload` 这类内容字段，
以及任何一处自相不自洽的分母（`emittedCount` 与行数、`distinct = emitted + omitted`、`rowsScanned` 与逐源之和、
`priorityCounts` 之和、`truncated` 却 `omitted=0`、`complete` 却还有源没答）。

**为什么这次必然跨模块：** `tests/workflow-assistance/test_snapshot_v3_schema_is_the_single_shape_authority.py`
断言"schema 顶层键集 == `apps/observer/frontend/src/types.ts` 的 SnapshotV3 声明"两个方向都比，所以加键不能只加一边。
Observer 侧因此只加**合同声明**（两个接口 + 两条编译期 `Refines`），并且**故意不进**
`PINNED_REFINEMENT_PATHS`——那份数组是渲染门要求的消费者总体，22 个键一个不加，界面也就仍然不消费这两个键；
这正对 owner 的分工：契约先存在，画面等 STITCH。卡的正文在
`docs/current/authority-convergence-20261019/CROSS-MODULE-ISSUE-CENTER-20261022.md`，
它写明涉及哪两个规范根、每个路径的单一写者、验收与回滚集合。

**一处顺手抓到的真缺陷（记 `ERR-290`）：** 给投影喂真库样本时第一次写健康表就死在
`sqlite3.OperationalError: incomplete input`。写者的键表是 camelCase、读回的列名是 snake_case，
而未映射键的策略是静默跳过——于是 `ON CONFLICT(name) DO UPDATE SET` 后面什么都没有。
现在未映射键与"只有 name 的空写"都当场拒绝，并把正确名印在错误里；既有调用方全部用已映射键，实测无影响。

**判决分两层，不混着说。** 结构层：新守卫 20 + 17 例全绿，`typecheck` exit 0，前端 `vitest` 68 文件 826 例全绿，
账本 `ERROR_LEDGER_PASS entries=289 classifications=14 counts_consistent=true`。
运行层：真起 `services/orchestration/sidecar.py`（随机端口）取回 `/api/v1/snapshot`，25 键、
`valid=True errors=[]`，`issues` 有 1 行——`SOURCE_INCOMPLETE_COVERAGE` 挂在 work-lab 的 task-ledger 采集器上，
`rowsScanned=8 sourcesRead=4 complete=true`。这台机器上真实存在的问题被真实报出来了，而不是一个演示用的空清单。

**还没做、也不假装做完的：** 问题→修复任务包的生成、修复生命周期与结果读回、可检索的方案库（后三条是
`04` 报告里的第 4–6 行，需要后续卡片）；界面的呈现与可达性（STITCH 那一轮）；`ERR-290` 的 `verifiedCommit`
等 exact-SHA 判绿再钉；`config/adapter-registry.json` 一个字节没动，Control 的 13 个动词一个没加，
Observer 没有任何写路径。

## 25. 问题行的软件与版本归属：能配就配，配不上要说为什么（2026-10-22）

§24 留下的第一条缺口是「软件/版本关联只有 `projectId`」。这一片把它接上，规则是**不猜**。

**做法。** `issue_projection` 多收一个身份来源：composition root 已经建好的 `software[]` 行
（注册表 × 安装发现），不自己发现、不安装、不读凭据。索引把 `softwareId` 与 `displayName` 都做键，
比对前统一去掉空格/连字符/下划线并折叠大小写——因此 `codex` 不是 `codex-desktop` 的匹配（前缀匹配
会把问题挂到碰巧同前缀的产品上）。每个结果落在六个状态之一：
`discovered` / `not-discovered` / `unmatched` / `ambiguous` / `source-names-no-software` /
`identity-source-absent`。一个名字对上两个产品就是 `ambiguous`，`softwareId` 保持 null——
把问题归给错误的已装软件，比不归给任何软件更坏。

**摘要因此多出一个必须自洽的块。** `softwareAttribution` 报
`attributed / unmatched / ambiguous / unattributable / versionKnown / identitySourceAbsent`，
四个桶必须恰好覆盖所有行；运行期 `snapshot_validator` 拒：桶加起来不等于行数、
`versionKnown` 与真带版本的行数不符、有版本却没身份、有身份却说"没匹配上"、
以及 `identitySourceAbsent` 与 `sources` 里 software 那一条的状态不一致。

**一处我自己的语义分歧，被第一次真读回抓到。** 投影说 `complete` 只关于四个问题源，
而验证器原先把 `sources` 里所有条目都算进"没答"，于是 identity 缺席就把一份完整的清单判成不完整——
第一次带身份源跑就红。修法不是放宽断言，而是**两边用同一个定义**：identity 缺席由
`softwareAttribution.identitySourceAbsent` 单独披露，验证器改成同样只看四个问题源，
并新增那条"两处必须一致"的检查。这就是"两边都来自同一个来源的核对不是核对"的反面教材：
这次两处各自表述同一事实，所以它们必须能被证一致。

**本机真实读数（不美化）。** 真起 sidecar 取回：`rowsScanned=15`、`sourcesRead=5`、`complete=True`，
`attribution={attributed:0, unmatched:1, ambiguous:0, unattributable:0, versionKnown:0, identitySourceAbsent:False}`，
唯一那行的 producer 是 `task-ledger-collector`——它是**采集器名**而不是已装软件的身份，
所以正确答案就是 `unmatched`，既不是 0 也不是硬配一个。也就是说：归属的机器到位了，
但这台机器的数据面还没喂给它可配的身份原料；哪些客户端会以软件名出现在 telemetry 里，
取决于采集器写 `producer` 的方式，这一步没做之前不说"软件关联已完成"。

**四地同步的代价，说清楚。** 加三个字段的真实成本是：schema、生成合同
`packages/client-neutral-core/generated/contracts.ts`、手写声明 `apps/observer/frontend/src/types.ts`、
以及生产面静态合同 `apps/observer/tests/test_production_surface_static_contract.js` 的可选键白名单——
少一处就有一枚门红给你看。折叠清单这次**没有**新增：`softwareAttribution` 在 schema 里给了六个真属性，
不做自由映射，所以生成器不折叠它。

**实测。** 守卫 20→28 与 17→21（含归属的 8 条新反例：唯一匹配、前缀不算匹配、歧义不归属、
无版本说 not-discovered、四桶覆盖、注入与缺席两路、以及三处不自洽归属被拒）；
`tsc` exit 0；`vitest` 68 文件 826 例；`tests/workflow-assistance/test_snapshot_validator.py` 16 例；
`tests/workflow-assistance/test_canonical_store_v2.py` 14 例；live `VALIDATE valid=True errors=[]`。

**`ERR-290` 的判决钉下去了，钉的是它有资格用的那个 SHA。** `main` 的 `7ee6ab6b…` 自身那次
`work-lab-gate` 运行里七个作业全部 `success`（含 `aggregate`），而 `workflow-assistance` 作业的日志里
就有本行回归例的第一次真跑：`test_collector_health_refuses_a_name_that_is_not_a_column (test_canonical_store_v2.CanonicalStoreV2Tests…)... ok`。写之前逐条断言：`fixedCommit` 是该提交的祖先、
对象在库、这一行原先 `verifiedCommit` 为空（不许覆盖旧判决）、写后全账本只有这一行移动且只动
`lifecycle.verifiedCommit` 与 `remaining_boundary` 两个键；边界原文一字未改，闭合说明追加在后面。
拿一个更早的 SHA（`c35273c6…`，修复还没进 `main` 的时候）去钉会被当场拒绝，这条断言因此是能失败的对照。
重发读回：`docs/audits/LEDGER_FIX_COMMIT_BINDING_2026-10-07.json` 里这一行现在是
`verified=7ee6ab6b… verifiedTreeChecked=true`，账本仍 `ERROR_LEDGER_PASS entries=289`。
**钉的是哪一次运行，也说清楚。** 同一个 SHA 上其实有两次 `work-lab-gate`：#1536 七个作业全绿，
#1537 的 `observer` 判红。#1537 的红不在源码字节上——那台 win32 runner 没有交互会话
（`DESKTOP_CAPABILITY_FAIL … session=FAIL {"SESSIONNAME": null}`），于是 WebView2 起不来：
`[U19] CDP readback FAILED: no CDP page target`、`GDI render proof: FAIL (windows=4)`、
`GEOMETRY_GATE_NOT_RUN MEASURE_FAILED … no 'DevTools listening on' line within 90s`。
两次运行里 `workflow-assistance` 都是绿的，而本行的回归例正是那一跑的必测集合跑的（回执
`.project-local/artifacts/issue-center-20261022/ci-workflow-assistance-at-7ee6ab6b.log` 与
`ci-observer-FAILED-at-7ee6ab6b-run1537.log`）。所以判决钉在 `7ee6ab6b`，而"这台 win32 runner
跑不了桌面几何"是**另一条独立的边界**，不混进这一行，也不因为它就把已绿的回归说成没跑。
同一次改动里另外两份派生记录**经实测不需要动**：`docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json`
与 `.project/governance/generated/CURRENT_STATE.json` 按 `VOLATILE` 字段归一后与仓库字节逐字段相同，
`.project/governance/generated/CURRENT_STATE.md` 只差那一行 `Generated at`——所以这次提交只动
`taskpacks/current/error-ledger.json` 和那份绑定审计，不为"看起来重发过"去改没有变化的字节。

## 26. 问题→修复任务包的生产通路：准备并导出，不派发（2026-10-22）

审计包「闭环距离」第 3 行的原话是**「案例已有，通用入口缺失：ML-001 人工交接；没有 issue→repair 生产通道」**。
这一片补的就是那个通用入口，并且按审计的要求停在入口处：`05_后续实施建议`写的是
「复用既有 store/Control，接问题记录/去重→修复包导出或复制→外部 Agent 修复→结果导入→独立验证→方案固化/检索」和
**「不要为完成首版而强制实现自动 dispatch」**。所以这一片做的是"导出或复制"，不是"发出去"。

**三条不做就不可信的规则。**
第一，**执行者由人点名，不从归属推断**。软件归属回答的是"这个问题属于哪个软件"，它不是"该由哪个软件来修"的证据。
CLI 的 `--adapter` 是必填语义：`--adapter codex --adapter cc-switch` 里 cc-switch 被拒并报名字，因为
`config/adapter-registry.json` 给它声明的动词集合是 `detect/capabilities/observe`，没有 `invoke`——观测型软件
不能被交接一次修复。注册表里没有的名字也是拒，不是默认给一个。
第二，**包体是既有合同，不是新发明的形状**。`workflow/action-plan/v1` 早就声明过 target/steps/approval/rollback/
constraints，也早就在 canonical store 里有一张 `action_plans` 空表，缺的从来不是形状而是生产者。这一片把包体
交给那份合同，外面只套一层交接信封 `workflow/repair-pack/v1`（绑定哪些问题、谁被点名、验证命令知不知道、
发没发过）。信封的 `plan` 是**逐属性内联**的，因为 `scripts/ci/generate_contract_types.py` 不跟 `$ref`——
留一个 `$ref` 就把包体折叠成 `Record<string, unknown>`，合同还在但形状没人投影。复制的风险用一条守卫钉住：
`test_the_inlined_plan_body_has_not_drifted_from_the_action_plan_contract` 逐属性比对两份 schema 的 `properties`
与 `required`，两处任一改动都会红。
第三，**不知道就说是不知道**。验证命令只有在目标项目根下真的存在那个入口时才写进 `verify` 步骤
（`_verification()` 走 `is_file()` 实测），否则包状态是 `BLOCKED`、理由是 `verification-command-unknown`，
并且步骤里不出现任何命令串——守卫里那条 `assertNotIn("run_quality_gate", ...)` 就是这一句的反例。
项目根不在磁盘上、项目在 `projects` 表里没有、问题不带 projectId：三种各有各的拒因，
落库的是 `refusals[{adapter, projectId, reason}]` 与逐因计数，不是一张空列表。

**界面之外的东西不算界面。** 信封把 `handoff.sent`、`handoff.dispatched`、`provenance.applied` 全部做成
`const false`，`approval.status` 只能是 `PENDING`，`status` 的枚举只有 `WAITING_APPROVAL`/`BLOCKED`——
一份草稿不能在字节里假装自己被批了、发了或跑了。植入 `sent=true` 的包被 `validate_repair_pack` 与 JSON Schema
**两遍都拒**（这是守卫里唯一一处"两个来源各自成立"的断言，因为合同与代码各说各话正是 ERR-225 的形状）。

**回看自己这一片时抓到的两个真缺陷，都记在这儿。**
第一个是规范门替我抓的：`672915c8` 那次 `ran=1 planned=50 failed_gate=governance`、`GATE_EXIT=1`，红的就是
`tests/workflow-assistance/test_core_schemas.py` 里 `SCHEMA_DIR.glob("*.schema.json") == EXPECTED` 这条**精确清单**
——往合同目录放一份新合同，必须同时在那份清单里留评审记录，并且进 `CAMEL_CASE_WIRE_SCHEMAS`：信封与问题行一样是
camelCase 的 `schemaVersion`，而内联包体保留 action-plan 自己的 snake_case，版本字段只能点名，不能让守卫从邻居猜。
第二个是我自己复看代码看出来的，门是红的不起来——因为它每一条单记录检查都过：`--adapter codex --adapter codex`
会铸出**两个 packId 完全相同**的包（包 id 是内容寻址的，重复输入算出同一份内容），并且把同一个问题数两遍，
`boundIssueCount=2` 而 `openIssueCount=1`。单看每个包都无懈可击，分母在说谎。修法是分两层：投影侧按顺序去重并把
丢掉的重复数披露成 `duplicateAdaptersDropped`；再加一层 `validate_repair_pack_set`，专查"一组包"而不是"一个包"——
packId 不许重复、同一指纹不许被两个包绑走、`bound` 不得超过 `open`、`bound + unbound` 必须等于 `open`。
CLI 写盘前先跑这层检查，不过就 `REPAIR_PACKS_BLOCKED`、一个字都不落。实测：三个重复的 `--adapter codex`
→ 1 个包、`duplicateAdaptersDropped=2`、`setProblems=0`；这个数一开始只在摘要 JSON 里，要打开文件才看得见，
所以它现在也印在 CLI 那一行上——`codex codex cc-switch` 实测 `generated=1 refused=1 duplicateAdaptersDropped=1
setProblems=0`，去重这件事得在界面上自己说话，不能只躺在产物文件里。

**实测。** 新守卫 `tests/workflow-assistance/test_repair_pack_projection.py` 26 例；连同
`tests/workflow-assistance/test_core_schemas.py` 与生成合同投影清单三套合跑 42 例绿；合同登记后
`CONTRACT_CATALOG_PASS contracts=46 schemas=46`，`CONTRACT_SSOT_PASS contracts=46`，
`CORE_SCHEMA_CONTRACT_PASS schemas=29`。规范门在 `5d671dcd` 这个头上（合同清单登记已进、集合层去重还没进）
`GATE_EXIT=0`、`ran=50 planned=50`、`GATE_SOURCE_DRIFT=no`；把去重与集合级分母检查加进来之后另跑一次，以那一跑的
`^GATE_EXIT=0$` 作为本片的交付判据。CLI 真跑（dry 与 `--apply` 两趟）：
`generated=1 refused=2 openIssues=1 bound=1 unbound=0 absentSources=None setProblems=0`，
产物在 `.project-local/artifacts/repair-packs/` 下：包 JSON、可复制的交接文本，
以及同目录的 `.project-local/artifacts/repair-packs/repair-packs-summary.json`。数据边界那条也是实测的：
`--out-dir` 指到项目 Git 根外面时 `REPAIR_PACK_REFUSED_OUT_OF_BOUNDARY`、退出码 2，不写任何东西；
存储根里没有库时 `REPAIR_PACK_NO_STORE` 退出 3——`CanonicalStore(path)` 会把文件建出来，
一个猜错的路径于是回报成"读过且为空"，这正是本轮禁止的形状。本机那一个包绑的是 `SOURCE_INCOMPLETE_COVERAGE`/work-lab，
证据条目 `telemetry:task-ledger-…`，验证命令因为 `services/orchestration/run_quality_gate.py` 实测存在才写进步骤；
CLI 还会先印一行 `ISSUE_SOURCE … softwareAttribution={…}`，因为导出这一步不跑安装发现，
`binds.softwareIds` 为空必须看得见是"身份来源缺席"，不是"这问题不属于任何软件"。

**还没做。** 包不落库：`action_plans` 表仍是空的，第 5 行（修复状态跟踪与实际结果验证）才有资格写它——
先有状态机再持久化，反过来就是把"生成过"当成"跟踪中"。Observer 不显示修复包，快照 v3 这轮没加键，
前端仍等 STITCH；`config/adapter-registry.json` 一字节未动，Control 的 13 个动词一个没加，没有自动派发。
`refusal` 词汇表在模块与合同里各存一份，靠 `test_refusal_vocabulary_in_the_module_and_the_schema_are_one_list`
对齐——这是复制，不是共享，改名要同时改两处否则红。

**2026-10-23 更正（上文保留原样作当日记录）。** 上面「包不落库……Observer 不显示修复包……前端仍等 STITCH」三句
已被 §27 的工作集取代：`action_plans` 现有读写方法与 v5 迁移，生命周期在
`packages/client-neutral-core/scripts/repair_state.py`；Observer 在既有「项目监控」页消费
`issues`／`issuesSummary` 并显示修复包交接；`PINNED_REFINEMENT_PATHS` 由 22 增至 24。本机 live canonical store
本轮没有写入任何修复行（CL-09 在夹具运行时根里跑），行数未测，不补 0——「有路径」不等于「有记录」。
Control 的 13 个动词未增、`config/adapter-registry.json` 未动、仍无自动派发。

## 27. 从问题行到可核验交接：CL-03／04／05／07／09 的工作集（2026-10-23）

用户 2026-10-23 以登记材料 `WL-REC-0107` 下达具体 Task Grant，要求按序做 CL-03 → CL-04 → CL-05 → CL-07 → CL-09，
并明确 CL-06／CL-08／CL-10／CL-11／CL-12 是后续独立切片、不得顺带完成。这一节只写这五片**实测到的**东西；
Windows／Tauri 安装层与真实外部 AI 工具腿仍记 NOT_RUN，不以本地退出码冒充。

**交接对象先分家（CL-03）。** `packages/client-neutral-core/scripts/repair_pack_projection.py` 新增
`TARGET_KINDS=("ADAPTER_INVOKE","MANUAL_COPY")` 与对应 operation 映射。人工交接路径**不读**
`config/adapter-registry.json`、不点名适配器、不声明任何 `invoke`——同一问题交给人还是交给适配器是两份不同材料，
不是同一份材料换个收件人。`render_handoff_text` 把绑定的证据引用与「还缺什么条件」逐条写出，四类交接事实分行且互不替代：
`sent=false`、`copiedByUser.declared`、`userDeclaredHandoff.declared`（明写这只是用户说法，不是对方回执）、
`externalReceipt.received`（只有外部系统自己的答复能填）；`validate_handoff_text` 要求每条 `binds.evidenceRefs`
都出现在文本里，并拒发送／执行／已批准一类句子。`packages/contracts/schemas/workflow/repair-pack.schema.json`
用 `allOf` 条件钉住两种目标：ADAPTER_INVOKE 必须非空 adapter 且 `invoke`，MANUAL_COPY 必须 `adapter=null`
且 `copy-handoff`。合同目录仍 46 条，没有新增目录成员。证据：
`tests/workflow-assistance/test_repair_pack_projection.py` 37 例；与后四片五个测试文件合跑 **102 passed（7.76s，2026-10-24 复跑）**。

**状态要有地方落，且命令行不能替人做决定（CL-04）。** 新增
`packages/client-neutral-core/scripts/repair_state.py`：`record` 只接受 WAITING_APPROVAL／BLOCKED，导出没有路径写
APPROVED；`approve` 必须在既有 Control 受信授权记录（`control-trusted-grants`）中解析到未过期且覆盖
`work-unit:<packId>` 或 `*` 的授权，模块只读该记录、从不创建或改写；`declare` 只写 `copiedByUser`／
`userDeclaredHandoff`；`record_outcome` 只从 APPROVED 起，SUCCEEDED 需 reproducible／independent 且至少一条引用，
self 自述只能停在待核验；每次变更都是按 `version` 的 compare-and-swap，重复请求是 no-op。
`packages/client-neutral-core/scripts/canonical_store.py` 的 `action_plans` 从「建表无人读写」变为
`save_action_plan`／`read_action_plan`／`list_action_plans`（写入只认点名的六个键，未知键具名拒绝，payload 走
`secret_value_paths` 值扫描），迁移 v5 增加 `version`／`updated_at` 并由 `created_at` 回填，`action_plans`
进 `RETENTION_EXEMPT_TABLES`（它是当前状态而非事件，裁剪会删掉后续导入结果要比对的那一行）。原计划句
「该表当前零访问方法」已被本片取代；本次**没有**往 live canonical store 写行（CL-09 全链在夹具运行时根里跑），
所以本机 live store 行数本轮未测，不补 0。证据：`tests/workflow-assistance/test_repair_state.py` 20 例。

**导入不是核验（CL-05）。** 新增 `packages/client-neutral-core/scripts/repair_verification.py`：
`validate_external_result` 把结果绑定到这一次交接——`packId`、`projectId`、交接声明的 `targetVersion`、产生时间与
未用过的 `resultId`，错包／错项目／错版本／早于交接（STALE）／重复提交／关闭后晚到（RECORD_CLOSED）逐类具名拒绝；
导入只写 `externalResults` 与 `pendingVerification`，记录状态不变，`receiptAcceptedAsVerification` 恒 false。
`verify_repair_record` 重读 WORK-LAB 自己的 issues 投影：全部绑定指纹不再产生且本轮相关来源都作答→`RESOLVED`；
仍有指纹→`UNRESOLVED`；任一相关来源未答、读被截断或投影缺席→`UNVERIFIABLE` 并点名未答来源，绝不关闭。
证据强度沿用 `services/task-governance/completion_authority.py` 的四档 none／self／reproducible／independent，
不造第五套尺；`RESOLVED+claimed SUCCEEDED→SUCCEEDED`，其余 RESOLVED→FAILED，UNRESOLVED→FAILED，
UNVERIFIABLE 不关闭。`worklab/external-repair-result/v1` 与 `worklab/repair-verification/v1` 是内联载荷形状，
未进合同目录（仍 46 条）。证据：`tests/workflow-assistance/test_repair_verification.py` 34 例。
真实外部 AI 工具的产出本轮未跑，CL-09 记为 NOT_RUN。

**界面只读地把它显示出来（CL-07）。** `services/orchestration/sidecar.py` 新增 GET-only `/api/v1/repair-packs`
（`worklab/repair-packs-view/v1`），四态 `SOURCE_ABSENT`／`NO_OPEN_ISSUES`／`NO_PACK`／`OK`；
`SOURCE_ABSENT` 表示没有来源作答，不是一个空列表的断言。`apps/observer/frontend/src/lib/repairPack.ts`
只接受该形状且逐包复核 `handoff.sent=false`、`handoff.dispatched=false`；`apps/observer/frontend/src/lib/api.ts`
从已验证快照基址派生端点（回环、GET-only），`?api=` 不能把交接读取引到外部主机。
`apps/observer/frontend/src/views/IssueCenter.tsx` 挂在既有「项目监控」页（`apps/observer/frontend/src/views/OverviewView.tsx`）：
问题行显示类别／影响／详情／软件／更新时间／重复次数／证据／下一步；`issues` 缺席画 UNKNOWN 且不造计数；
`issues` 空且 `issuesSummary.complete===true` 才画「当前没有待交接的问题」，空但 `complete!==true` 画
「扫描被截断，不能声称无问题」；交接预览显示包 ID、状态、`readiness.reasons` 与草稿句；包内唯一按钮是
「复制交接材料」，无派发／执行／批准控件，复制后状态行仍写「仍未发送、未执行」。
`apps/observer/frontend/src/contractConformance.ts` 的 `PINNED_REFINEMENT_PATHS` 由 22 增至 24。
实测不是源码自述：`.project-local/runs/cl07_render_probe.py` 起真实 sidecar、已构建 dist 与 headless Chrome，
真鼠标点击两次并读回剪贴板，`.project-local/artifacts/cl07/receipt.json` `verdict=PASS`、12/12 checks：
直读路由包 `rp-work-lab-manual-copy-c59e22542c94e69b`，handoff 1,220 字符／2,390 B／40 换行；
剪贴板 2,430 B 的 `normalizedSha256` 与路由相同，`crlfCount=40`、`bareLfCount=0`，
`bytes=handoffBytes+crlfCount`（Windows 剪贴板 LF→CRLF 是唯一差异）；截图 `.project-local/artifacts/cl07/copied.png`
（181,943 B，已实际查看）。前端两套件：`apps/observer/frontend/src/views/IssueCenter.test.tsx` 10 例、
`apps/observer/frontend/src/lib/repairPack.test.ts` 7 例；`apps/observer/scripts/frontend_toolchain.py contracts`
复跑 **70 文件／843 例**，`OBSERVER_FRONTEND_CONTRACTS_PASS js=0 vitest=0`。

**整条纵线与反例族（CL-09）。** `tests/workflow-assistance/test_closed_loop_vertical_slice.py` 6 例，用真 canonical store、
真 sidecar HTTP、每一步独立 `packages/client-neutral-core/scripts/repair_state.py` 进程（跨进程持久化，不靠同进程缓存）。
主例走完 记录→声明复制→声明交接→授权→确定性本地工具真改 store→导入结果→核验（RESOLVED／independent）→SUCCEEDED→
重启后 `/api/v1/repair-packs` 答 `NO_OPEN_ISSUES`、快照 `issues=[]`、记录仍 SUCCEEDED 且 `externalReceipt.received=true`，
并断言载荷中没有 solution 字样（方案库不假装存在）。反例五例：过期结果拒、重复提交拒、自述不关闭、故障仍在→FAILED、
关闭后晚到拒。回执 `.project-local/artifacts/cl09-vertical-slice/receipt.json`：8 个 CLI 步骤 rc=0，
`restart={repairPacksStatus:NO_OPEN_ISSUES, snapshotIssueCount:0, recordStatus:SUCCEEDED,`
`verificationOutcome:RESOLVED, evidenceLevel:independent}`，`externalAiTool=NOT_RUN`，
`solutionLibrary=NOT_EXECUTED (CL-06 is a later slice)`。Observer 严格只读：写入全部经
`packages/client-neutral-core/scripts/repair_state.py` 与 canonical store，界面只复制文本。
未做且不冒充：真实外部 AI 工具那一腿 NOT_RUN；方案固化／检索属 CL-06 未执行；HUD 摘要属 CL-12 未动；
Windows／Tauri 安装层未测，记 NOT_RUN。故 register 的 CL-09 保持 PARTIAL，不写 EXECUTED。

**边界仍然成立的。** Control 的 13 个动词一个未加，`config/adapter-registry.json` 一字节未动，没有自动派发；
Observer 无 execute／approve／retry／apply／rollback，也没有移交给它任何写路径；没有第二任务账本；
工作集尚未提交，exact-SHA CI 未跑——本地门与守卫的绿不等于 CI 判决。

## 28. 工作流与上下文服务治理并入（2026-10-24）

用户于 2026-10-24 决定：跨软件工作流配置、部署、治理和管理归 WORK-LAB。本轮把两份现行治理文档与一份历史交接并入既有权威／归档结构，不新增 CURRENT、任务账本、第二母版或全局配置执行器。

### 现行规范（`docs/decisions/`）

- `docs/decisions/OPENVIKING_CONTEXT_SERVICE_STANDARD.md`：状态生效。上下文服务只走 `127.0.0.1:1933`
  单端口；嵌入维度 1024；换模型或维度必须走标准 §5 的五步变更（备份、来源切换、重建、回读、归档旧索引）；
  六项验收；验收必须在新会话实际调用检索与读取工具，`health` 成功或配置文件写入不算完成。
- `docs/decisions/OPENVIKING_DEPLOY_HANDBOOK_20261024.md`：操作手册，记录 OpenViking 0.5.1.1 的部署、
  13 类故障的现象／根因／修法、常用命令与验证清单；同时写明 ingest 被 0.5.1.1 阻塞、无 hook 接口的客户端
  只能主动调用、依赖 `127.0.0.1:1234` 本地嵌入等限制。手册中的版本号与 PASS 是记录时点值，不是当前运行验收。
- 两文件由 `AGENTS.md` 顶部指针引用，并在 `docs/current/workflow-assistance/workflow/active-authority-index.md`
  §6 登记；客户端字段所有权仍以 `config/config-ownership.json` 为准（`preserve_unknown`），
  模型、服务商、鉴权与端点不在本规范授权范围内。

### 历史交接（归档，非现行任务权威）

- 交接目录 `docs/history/archive/workflow-assistance/handoffs/agent-rules-governance-20261024/` 含摘要、
  接收提示词、归档收据与来源清单；归档容器
  `docs/history/owner-inputs/20261024/WORK-LAB-AgentRules-Governance-Intake-20261024.zip`
  为 74,576 B、40 个成员、SHA-256 `190d56d69cd8f80efdac68abe393f087a2d4589896490003e50ca50810277fb8`，
  登记为 `WL-STORE-AGENTRULES-20261024`（HISTORICAL_DERIVED_HANDOFF_NOT_TASKPACK）。
- 资料目录校验本轮实测 PASS：107 条登记资料、2,465 个包内成员、188 个来源文件、52 个相关来源、
  136 个排除的外来文件、56 个混合相关成员、0 个未解析来源；来源回读与产品实现为 NOT_EXECUTED。
- 证据边界按原收据保留：21 个规则文件写入与文件回读、4 项原生装载诊断、51 个局部测试 PASS；
  新会话读取与行为验证 NOT_EXECUTED，部署／提交／推送 NOT_EXECUTED。五类状态
  （已写入、文件校验、原生装载诊断、新会话读取、行为验证）不得合并表述。
- 未完成项保持原状：Open Design 0.24.1 daemon 离线 BLOCKED；MiniMax Design 4.0.4 持久入口 UNVERIFIED；
  Claude Chat／Cowork、Cursor 用户全局与新会话验收仍有缺口；`STITCH_API_KEY` 事件只登记位置与风险类型，
  未复制日志或值，轮换未验证。
- 接收实现仍在并行工作区，尚未提交；其测试结果不属于本轮归档判据。
- 归档目录受 `docs/history/archive/FROZEN-MANIFEST.json` 逐字节冻结；本轮新增 4 个文件后，
  按 `scripts/audit/generate_frozen_surface_manifest.py` 重新生成清单，而不是手工改数字。

### 边界

本轮只把资料并入 WORK-LAB 的现有治理与归档，不改 AAOS 或 DESIGN-LAB 仓库；不写客户端模型／鉴权／端点；
不把局部 PASS 表述为 exact-SHA CI 或发布完成；工作集保持未提交，提交与推送须 owner 另行授权。
