# WORK-LAB 收敛版路线图（2026-10-19）

本路线图替代此前过度扩张的未来愿景，不删除历史资料。它是规划与状态视图，不是第二 Authority，
也不是新的任务账本；当前任务真值仍是 `taskpacks/current/OPEN-TASK-REGISTER.md`，当前计划是
`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`。

权威链：最新明确用户决定 > `WORK-LAB-AUTHORITY.md` > `.project/governance/project-authority-index.json`
> 当前任务包与唯一 open register > `AGENTS.md` 与作用域合同 > exact-SHA 代码/CI/运行读回 > 冻结历史。

## CURRENT — 当前主线

当前主线优先交付**一个真实最小问题闭环**，不以模拟数据、Agent 自述或单一退出码冒充接通。
下列条目的“现状”是 2026-10-19 对仓库的只读核对结果。用户 2026-10-19 指令
“执行所有未完成的任务，按照最新发你的任务包”作为具体 Task Grant，只授权并交付了第 9 项
（一个真实最小问题闭环，ML-001）；第 2-8 项作为系统能力仍**未获得实施授权**。
2026-10-23 用户以登记材料 `WL-REC-0107` 下达新的具体 Task Grant：按序授权 CL-03 → CL-04 → CL-05 → CL-07 → CL-09
五片，成果归入本路线图第 3-5 行；CL-06（方案库）、CL-08（导航）、CL-10（性能基线）、CL-11（上游基线）、
CL-12（HUD 摘要）仍是独立切片，**未获本轮授权**。下表逐行标注各自的复测日期。

| 次序 | 当前条目 | 现状（逐行标注复测日期） | 证据/缺口 |
| --- | --- | --- | --- |
| 1 | 权威定位、职责边界和路线图收敛 | 本次交付（文档） | 本文件、`WORK-LAB-AUTHORITY.md`、`docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md` |
| 2 | 真实数据源接入；Observer 诚实呈现状态、错误、阻塞、来源、时间、新鲜度与 UNKNOWN | PARTIAL：仓内有有界 collector、Snapshot v3 与只读 Observer；未证明所有受管客户端端到端 LIVE | `packages/client-neutral-core/scripts/collectors.py`、`packages/client-neutral-core/scripts/snapshot_api.py`、`apps/observer`；缺口见收敛报告能力映射 |
| 3 | 问题中心：去重、分类、优先级、项目/软件/版本关联、关键日志和处理状态 | PARTIAL（2026-10-22 后端；2026-10-23 界面接入）：`packages/client-neutral-core/scripts/issue_projection.py` 从 canonical store 已记事实派生 10 类闭合词汇的问题行，带 16 位指纹去重、`occurrences`/`foldedOccurrences`、声明式优先级规则句、`evidenceRef` 回指来源行；快照成对携带 `issues`+`issuesSummary`（缺席≠为空、截断不得自称完整），运行期由 `snapshot_validator._validate_issues` 拒不自洽。软件/版本归属已接 `software[]` 身份：`softwareId`/`softwareVersion`/`softwareVersionSource` 六态闭合词汇，唯一匹配才归属，一名多品记 `ambiguous` 不猜，前缀不算匹配 | 守卫 `tests/workflow-assistance/test_issue_projection.py` 28 例 + `tests/workflow-assistance/test_snapshot_issue_section.py` 21 例；真起 sidecar 读回 25 键、`valid=True`、`issues=1`（`SOURCE_INCOMPLETE_COVERAGE`/work-lab）、`rowsScanned=15 sourcesRead=5 complete=True`、`attribution={attributed:0, unmatched:1}`。缺口已变（2026-10-23）：界面在既有「项目监控」页消费 `issues`／`issuesSummary`，`PINNED_REFINEMENT_PATHS` 由 22 增至 24，真实渲染与剪贴板读回 12/12 见 `.project-local/artifacts/cl07/receipt.json`；处理状态仍无 Control 写路径（投影只报 OPEN，Control 的 13 动词未增未改）；本机那行的 producer 是采集器名 `task-ledger-collector` 而非已装软件身份，归属实测 `unmatched`——归属的机器到位、数据面还没有可配的原料，不称"软件关联已完成"；问题→修复任务包生成与方案库见 `docs/current/authority-convergence-20261019/CROSS-MODULE-ISSUE-CENTER-20261022.md` §4 |
| 4 | 问题摘要与 Agent 修复任务包生成；优先可靠人工交接，只有已验证连接才允许自动派发 | PARTIAL（2026-10-22 导出；2026-10-23 交接对象分家）：`packages/client-neutral-core/scripts/repair_pack_projection.py` 把 OPEN 问题行按（项目 × 人点名的执行者）折成交付包。包体仍是既有合同 `workflow/action-plan/v1`，信封 `workflow/repair-pack/v1` 已进合同目录（46 个，`CONTRACT_CATALOG_PASS contracts=46 schemas=46`）。执行者不从软件归属推断——归属说的是问题属于谁，不是该由谁修；注册表里没声明 `invoke` 的适配器一律拒并报名字。验证命令只在目标根真的存在那个入口时才写进步骤，否则包是 `BLOCKED` 且理由 `verification-command-unknown`。导出 JSON 与可复制交接文本，`sent`/`dispatched`/`applied` 三个 const false，不自动派发 | `tests/workflow-assistance/test_repair_pack_projection.py` 26 例（植入 `handoff.sent=true` 被校验器与合同**双双**拒；植入 `status=SUCCEEDED` 同样拒；内联包体逐属性与 `packages/contracts/schemas/workflow/action-plan.schema.json` 比对，防复制漂移；集合级检查 `validate_repair_pack_set` 专查 packId 重复、同一指纹被两个包绑走、`bound` 超过 `open`、`bound+unbound≠open`——重复的 `--adapter` 曾在每条单记录检查全绿的情况下把分母数成 2/1）；CLI 实测 `generated=1 refused=2 bound=1 unbound=0 setProblems=0`（cc-switch、cursor 为观测型），`--out-dir` 出根当场拒写退出码 2，产物在 `.project-local/artifacts/repair-packs/`。缺口（2026-10-23）：人工交接与适配器交接已分家（`MANUAL_COPY` 不读适配器注册表、不声明 `invoke`），交接后状态落库与结果核验归第 5 行；真实外部 AI 工具腿 NOT_RUN；仍不自动派发；Observer 已显示修复包交接（`.project-local/artifacts/cl07/receipt.json`） |
| 5 | 修复状态跟踪与实际结果验证；记录测试、运行读回、版本和失败原因 | PARTIAL（2026-10-23 实测）：状态机与结果核验已接入——`packages/client-neutral-core/scripts/repair_state.py` 20 例、`packages/client-neutral-core/scripts/repair_verification.py` 34 例、纵线 `tests/workflow-assistance/test_closed_loop_vertical_slice.py` 6 例；重启后记录仍可读回（SUCCEEDED／RESOLVED／independent）。外部 AI 工具与 Windows／Tauri 均 NOT_RUN，live store 本轮未写行 | `services/task-governance/completion_authority.py`、`services/receipts/evidence_aggregator.py`；四档证据强度沿用前者，未造第五套尺；结果导入绑定包／项目／版本／时间／未用过的 resultId，自述不能关闭。缺口：真实外部工具读回、live 库行数未测（不补 0）、方案固化属 CL-06 未授权 |
| 6 | 解决方案库最小闭环：成功方案带适用条件、步骤、证据、回滚和失效条件 | NOT_IMPLEMENTED | 没有解决方案库模块或视图；`services/knowledge/promotion_gate.py` 只是知识提升闸门，不是方案库 |
| 7 | AAOS 知识候选出口：只提交精选候选并读取正式接收状态 | FROZEN_20261019（项目联动延后，用户指示）；合同层仍是 CONTRACT_ONLY：候选/回执合同与提升闸门存在，未接通 AAOS API，未读取正式接收状态 | `integrations/archeaxis/contracts/promotion_contract.py`、`services/knowledge/promotion_gate.py`、`services/knowledge/BOUNDARY.md`；冻结不撤销合同，也不声称接收 |
| 8 | 保持 Control/Observer 权限分离，保护用户配置和未提交改动 | SCAFFOLD：Control 是 loopback 写边界，Observer 有只读门；尚无问题/修复写路径 | `services/control/control_service.py`、`scripts/ci/verify_observer_readonly.py`、`scripts/ci/verify_observer_readonly_boundary.py` |
| 9 | 验证一个真实最小闭环，不以模拟数据冒充接通 | DELIVERED（2026-10-19，`WORK-LAB-MINIMAL-LOOP-001`）：AG-06 能力门从红转绿；产品修复 `services/execution-federation/hermes_adapter.py`；12+49 回归测试；适配器 launchable 分支真实读回；固化 `SOLUTION-001`。AAOS 候选 NOT_SUBMITTED，exact-SHA CI 未跑 | 不是外部客户端采集来源，而是仓内可复现的能力门；Hermes 原生会话恢复仍不存在，也未声称存在 |
| 10 | 本仓独立运行跑通（不依赖任何其它项目） | DELIVERED（2026-10-19 实测，非文档）：`services/orchestration/sidecar.py` 在随机回环端口 READY；`/healthz` = `{"ledgerOwner":"workflow-assistance","observerMutation":false,"readOnlyControl":true}`；`/api/v1/snapshot` 200、schema `workflow/snapshot/v3`、152,058 B；同一进程 `--frontend-root apps/observer/frontend/dist` 服务已构建 UI（200）；渲染出的 Observer 读数随快照前进（revision 7→12→17），缺数据保持 UNKNOWN。 | 缺口：一键入口 `apps/observer/start-observer.cmd` 原本指向不存在的路径且写死端口，已修并加守卫 `tests/ci/test_observer_launcher_chain_is_runnable.py`（6 例，种回原缺陷可判红）；Task Ledger 源 `.hermes/task-runtime/task-ledger/ledger.json` [no-tree-claim CLIENT_HOME ref=.hermes/task-runtime/task-ledger/ledger.json] 本机缺失→计数 UNKNOWN；Tauri 桌面 exe 与像素级视觉 QA 本轮未启动 |
| 11 | 快照声明的每一项事实都要有界面消费（不许"后端有、界面不说"） | DELIVERED（2026-10-19 实测）：契约钉住 22 个 v3 键，界面源码此前只消费 20 个——`artifactHandles`/`artifactHandlesSummary` 零消费（快照已发 200 行把手、枚举 5024、省略 4824、敏感名拒 231、剪枝 114、有摘要 40/无摘要 160）。现补证据泳道把手块，并加机器门 `scripts/ci/verify_snapshot_keys_rendered.py` + `tests/ci/test_snapshot_keys_are_rendered.py`（6 例，其中 4 例是"必须能判红"的植入反例；套件自选发现 56 模块含此门）。 | 活链探针实测：按 unrecorded 过滤渲染 160 行=后端 rowsWithoutDigest、行先于事实格、最小计算字号 12px、无内容读取/重试控件、错误过滤值被显式拒绝 |
| 12 | 界面仪器的绿必须带分母，也不许把没走完的滚动当成看过 | DELIVERED（2026-10-20 实测）：`scripts/audit/text_legibility_via_cdp.py` 每条泳道现报 `presentNodes`、`sweepStopsUsed`/`sweepStopsNeeded` 与 `scrollRangeCovered`，缺任一项由 `coverage_was_reported` 判红；`sampled_nodes_stay_within_the_measured_population` 抓合并去重双计（采样数不得高于页面实际存在的叶子文本）；`every_scrollable_range_was_traversed` 把"没走到滚动范围尽头"按泳道点名判红；`tests/ci/test_text_legibility_gate.py` 57 例全绿 | 每泳道预算 16→96 后实测 565/565 站全部走完、无短程泳道，两主题一趟 69 秒（预算 16 时 46 秒、只走 298/564 站），distinct 读数 3,901 / 存在叶子文本 8,006，回执 `.project-local/artifacts/standalone-run-20261019/24-legibility-budget96.json`；直接读 DOM 另证把手泳道实有 200 行 / 1,200 个 `data-origin` 格 / 23,031px 列表。distinct 数低于存在数是对的——合并按 (path, text, size, weight, colour) 去重，重复单元格文本本就只算一次，所以它不是行数；被保证的是"每一段滚动范围都在某次采样里上过屏" |

最小闭环的固定顺序：
`发现 → 去重/关联 → 问题摘要 → 匹配历史方案 → 建议或 Agent 修复任务包 → 用户/授权策略交接 → Agent 实际修复 → 测试与运行读回 → 关闭或继续 → 方案固化 → 必要时 AAOS 知识候选`。
发现、分析、建议、已交接、Agent 声称完成、技术验证通过、方案固化、候选提交、AAOS 接收/审核必须分开记录。

## NEXT — 当前闭环稳定后再考虑

- 按真实需求增加更多软件、Agent、CI 和服务连接器；每个连接器必须有官方接口或可核验读回。
- 提升重复问题聚类和历史方案检索；先做可解释的规则/索引，不把向量库当默认前置。
- 在明确授权、幂等、回滚和验证条件下，对低风险维护动作做有限自动化。
- 解决方案过期检测、版本适用性提醒和回归复验。
- 按需补充成本/Token/资源汇总，只呈现真实可获取的数据；缺失写 UNKNOWN，不补 0。
- 把手摘要的字段进生成 schema（`digest`/`digestSource`、`generatedAt`、`orderingRule`、`cost`、
  `contentIncluded`、`enumerationScope`、`digestIndex` 子键、`order` 与 `orderingKey` 的一致性），
  之后才能撤掉 `apps/observer/frontend/src/contractConformance.ts` 里对 `artifactHandlesSummary.refused`
  的豁免行。这是**跨模块**改动（生产者在 workflow-assistance 侧），需要一张显式跨模块任务卡。
- 把逐泳道的**浏览器扫掠**接进 CI 作业 —— **已交付并有 runner 判决（2026-10-22，owner 本轮授权）**：
  `.github/workflows/work-lab-gate.yml` 的 observer 作业新增 `Text legibility sweep` 一步
  （`--all-views --live-backend --sizes 1280`，应答预算由调用方显式声明），
  在 `bf3e189c` 上 `LEGIBILITY_GATE_PASS`：两主题各 `stops=501/501`、`sampled=3573` 与 `3575`、
  `present=6674`、地板与 AA 零违例，墙钟约 84 秒；算术与判定仍由 `tests/ci/test_text_legibility_gate.py`
  （实测 57 例，`unittest discover` 计数，2026-10-21 重量；此处曾写 56）钉住。
  这一步接入后连着红过三次，两次归因（应答预算、启动竞态）都被下一次红推翻，机制最后落在"同一个
  等待语义在两层各有一份实现、紧的那层看不见"——见收敛报告 §22 末与 `ERR-287/288/289`。
  `scripts/audit/evidence_handles_render_via_headless_chromium.py` 仍只是本机取证，未接入。
- 手区块的无虚拟化几何已进回执（收敛报告 §23：`rowsInDom`/`rowsServedBySnapshot`/`listHeightPx`/
  `viewportHeightPx`/`pxPerRow`/`viewportsOfScrolling` 六个数与三条判红断言）。**留下的不是断言而是决定**：
  200 行 ≈34 屏的列表要不要窗口化或默认可达，属 owner 的产品判断，本轮不动布局。

NEXT 不是实施承诺；启动任一项仍需用户明确 Task Grant 和独立验收。

## FROZEN — 暂时冻结，不进入当前开发

- 新增与当前问题闭环无直接关系的 Agent/Runtime 框架。
- 全自动自主多 Agent 编排、复杂 Agent 群和自我扩张能力。
- 大规模插件/MCP/模型/数据库批量安装或统一替换。
- 全局自动改写所有客户端配置，或强制所有任务通过 WORK-LAB。
- 重型多租户、集中身份中心、Kubernetes、复杂分布式调度。
- 把全软件私人会话自动采集、跨会话自动拼接作为当前功能。
- WUI-00..WUI-21 及其他 OPEN 账本任务、旧 UI/HUD 扩展、`WORK-LAB-UI-PRIORITY-TASKPACK-20261009` 的后续实施。
- **项目联动（用户 2026-10-19 指示：本项目按照独立运行先运行跑通起来，项目联动延后冻结）**：AAOS 候选提交与
  正式接收状态读取、DESIGN-LAB 设计能力、外部 source-root（owner 的 Record 资料）清点与分类、跨项目记忆与
  会话联邦，全部冻结在本仓独立运行跑通之前。冻结≠关闭：相关账本行、状态与证据原样保留，不因冻结标记为完成。

## DEFERRED — 延后研究，不承诺实施

- 跨项目、跨软件的长期上下文记忆与会话联邦。
- 自动恢复复杂跨客户端任务、跨 Agent 状态同步。
- 广泛自动派发和自动修复高风险问题。
- 自建长期记忆/向量数据库或第二套知识真源。
- 企业级部署、团队协作和远程集中治理。
- 对所有软件的实时深度监测；仅在有官方接口、明确权限和成本收益时逐步接入。

## RETIRED / 不作为产品目标

- 将 WORK-LAB 做成 Agent 本身或通用聊天产品。
- 将 WORK-LAB 定位为所有项目的统一专业审计官。
- 以目录/页面/插件数量证明产品进度。
- 用假数据、Agent 自述、HTTP 200 或单一退出码伪造成功。
- “超级入口 / Command Center / LAB Router”作为系统级执行大脑、Agent 调度器或第四个产品入口的设想；
  该历史设想保留在 `docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`，
  不再作为当前产品目标。

## 解冻门槛

冻结/延期项目只有在以下条件全部满足后才能进入正式路线图：
当前最小闭环稳定；存在明确用户场景；接口和权限合法；风险可控；维护成本合理；能独立验收；用户批准。
解冻前先做小范围试验；未达到净收益即停止。代码存在不等于功能接通，文档更新不等于产品完成，
候选提交不等于 AAOS 接收。

## 路线图管理规则

每项能力必须标注：用户价值、依赖、风险、数据权限、实际证据、维护成本、退出路径和验收标准。
候选名单不等于实施承诺；研究不等于采用；代码存在不等于功能接通；文档更新不等于产品完成。
每次状态变化都必须在唯一 open register 或本次收敛报告中留下证据路径和日期，不得无证关闭历史任务。
