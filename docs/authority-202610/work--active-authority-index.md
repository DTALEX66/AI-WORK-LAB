# Active Authority Index

> 历史资料定位与来源登记：`docs/history/owner-inputs/INDEX.md`。这是导航，不是第二Authority。

> 2026-10-19权威收敛：其他任务冻结，唯一CURRENT为`taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`；
> 路线图`docs/current/authority-convergence-20261019/ROADMAP.md`，报告`docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md`。
> UI包与`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 NEXT-AGENT-PROMPT）为SUPERSEDED_20261019/FROZEN，仅作历史；手机端不做。
> 旧任务归档与逐条继承：`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/FROZEN-MANIFEST.json`、`docs/history/archive/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json`。
> 2026-10-19 第四次修正（任务包 §15，用户原话"本项目按照独立运行先运行跑通起来   项目联动延后冻结"）：
> 先跑通本仓独立链（`services/orchestration/sidecar.py` 回环快照 + 已构建 Observer 投影，只读），
> AAOS 候选提交与接收读取、DESIGN-LAB 设计能力、外部 source-root 清点、跨项目记忆与会话联邦一律冻结；
> 冻结不关闭账本行，也不把独立运行已实测通过之外的部分算作完成。


> **NON-AUTHORITY VIEW** — 本文件是只读分类索引，不是第二顶层 Authority。
>
> **Top authority = `/WORK-LAB-AUTHORITY.md`**
> Machine authority = `.project/governance/project-authority-index.json`
> 本文件仅供快速导航；若与上述两份冲突，以上述两份为准。

## 1. 活跃权威（Active — 唯一规范来源）

| 领域 | 权威文件 | 角色 |
|---|---|---|
| 文档与任务定位 | `docs/current/DOCUMENT-CENSUS.md` | 非权威索引：每个文档面的位置、数量、状态、守卫与冻结候选；权威顺序仍由本索引上方各行与 `WORK-LAB-AUTHORITY.md` 决定 |
| 字段级配置所有权 | `config/config-ownership.json` | 唯一字段权威（`single_authority: true`） |
| 外部项目端点 | `config/project-profiles.json` | 只读端点声明（地址 + 协议元数据） |
| 项目 profile 合同 | `packages/contracts/schemas/workflow/project-profile.schema.json` | 外部项目声明 schema |
| Gate 计划合同 | `packages/contracts/schemas/workflow/gate-plan.schema.json` | 计划合同 |
| Gate 注册合同 | `packages/contracts/schemas/workflow/gate-registry.schema.json` | 语义 gate 注册 |
| Task Ledger 真值 | `packages/client-neutral-core/scripts/task_ledger.py` | WORK-LAB 自身任务真值 |
| 全局 runner | `services/orchestration/run_taskpack_agent.py` | 唯一全局 TaskPack runner |
| 全局 gate 词汇 | `services/policy/gate_vocabulary.py` | 全局 tier 词汇（TARGETED/STAGE/NIGHTLY/RC/RELEASE） |
| 全局 hash 预算 | `services/policy/hash_budget.py` | 三层 digest 预算 |
| 审计触发 | `packages/client-neutral-core/scripts/audit_triggers.py` | 全仓审计触发去重 |
| Apply 安全 | `services/policy/apply_safety.py` | plan→diff→approval→backup→apply→readback→rollback |
| 官方基准 | 各客户端官方配置 | 官方 schema 优先，不可被 overlay 覆盖 |

## 2. 兼容/参考（Compatible — 引用权威，不重复定义）

- `docs/current/workflow-assistance/workflow/official-plus-user-configuration-standard-2026-08-11.md`：只解释 `config/config-ownership.json`，不重复字段表。
- `docs/current/workflow-assistance/workflow/managed-software-and-assets.md`：受管软件/资产清单，引用字段权威。
- `docs/current/workflow-assistance/workflow/examples/governance.yml.example`：documented example，非活跃 CI（WLG-080）。

- **规划/研究层（非执行权威）**：`docs/future/`。当前唯一 OPEN 的未来规划是 `docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`（超级入口 / Command Center / LAB Router）。2026-10-12 并入 §10「统一目标入口」、§11「外部多智能体能力吸收的候选池判据」；2026-10-13 并入 §12「Agent Studio — Visual Collaboration Experience」、§13 后续任务分解（A–G 非活动候选工作包）、§14 未来阶段与验收、 §15 与 AAOS/DESIGN-LAB 的长期边界。**不另立第二份路线图**。 同目录另两份按其自身抬头执行：`docs/future/WORK-LAB-BLUEPRINT-20261006.md` 已标 `FROZEN_ARCHIVED / NO_EXECUTION_AUTHORITY`；`docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md` 是 `scripts/ci/verify_blueprint_coverage.py --write` 的生成投影，勿手改。 登记在此是为了让换会话、换软件的读者能从索引直接找到它—— `docs/future/` 此前不在任何默认加载链上，内容在却找不到，与丢失无异。
## 3. 已取代/历史（Superseded / Archive）

- 历史 handoff 与审计：`docs/history/archive/workflow-assistance/handoffs/`、
  `docs/history/archive/workflow-assistance/audit/` 中带日期的交接文档（如
  `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 workflow-baseline-and-recovery-handoff-2026-08-13））
  记录当时状态，**不构成当前规范**，仅作归档。
  2026-10-08 更正：本条原写作 docs/handoffs/ 与 docs/audit/ 两个裸路径，而它们在 2026-09 目录收敛后
  就不存在了（`ls` 实测两者皆无），索引因此把读者指向空路径；现改写为收敛后的真实归档根。旧写法在此
  不加反引号，因为反引号在本文件里就是「这是一条可解析的路径」的记号。
- `taskpacks/history/`：完成 taskpack、旧 release、dated closure。
- `docs/history/archive/workflow-assistance/error-fixes/`：2026-10-08 起收纳带日期的错误与压缩记录
  （`error-fixes-2026-07-04.md`、`error-fixes-2026-07-28.md`、`error-fixes-2026-08-13-wlg.md`、
  `error-fixes-2026-08-14-guard.md`、`error-fixes-2026-08-14-r2.md`、`memory-compaction-2026-08-13.md`）。
  这六份原先位于 `docs/current/workflow-assistance/workflow/`，即「当前规范」目录里放着只描述过去某一轮
  的记录；README 与 TROUBLESHOOTING 各有一段把它们写成「本轮」，读者会当成现行流程执行。现已 `git mv`
  保留历史，并在每条链接处逐行标明「已归档，非现行规范」。
  同一原因，归档件内部的前收敛路径（skills/model-switch/、docs/workflow/…、contracts/… 等，实测共 10 条）
  **不改写也不纳入引用门禁**：把它们改成今天的路径会让一份带日期的记录说假话；这些示意名称在此不加反引号，
  理由与上面那条相同。`scripts/ci/verify_authority_index_paths.py` 的默认目标自 2026-10-08 起是
  `docs/current/` 下全部受跟踪的 markdown，外加三份面外严格面：`taskpacks/current/OPEN-TASK-REGISTER.md`、
  `apps/observer/frontend/DESIGN.md`、`apps/observer/frontend/SCREEN_SPEC.md`（不是四个手点名面）。
  不在树里的名称由所在句的 `[no-tree-claim <CODE> ref=<名字>]` 就地声明，且每条声明每次运行都要重新证伪；
  引用先按仓库根解析、解不到再按所在文档自己的目录解析，所以"同目录写法"不会被当成死链。
  具体计数写进本轮台账记录而不写在这里——本文件正是被点数的那份文档，在这里报数会立刻失真。
- `docs/history/archive/session-history/`：跨机迁移、旧产品（minigame）、历史状态清单。
- `taskpacks/history/CODEX-DESKTOP-STORE-UPDATE-BEHAVIOR-20260812.md`：历史调查记录，部分表述已由
  `docs/current/workflow-assistance/workflow/codex-desktop-update-state-investigation-2026-08-13.md`
  降级，仅作归档。

## 4. README 链接规则

- README 不得把历史记录当作当前规范来源：链接进 `docs/history/` 或 `taskpacks/history/` 的每一行，
  要么在本行文字里、要么在它所隶属的标题里标明那是归档/历史/审计/证据；归档索引小节可以列历史件，
  操作手册不可以「今日流程见某份归档交接」。可执行形式：
  `python scripts/ci/verify_readme_history_labels.py`（由 `tests/ci/test_readme_history_links_are_labelled.py`
  在 root-governance 套件里跑）。
  2026-10-08 更正：本条原写作「README 只链接权威文件（上表 Active 列），不链接历史记录」——字面禁令与
  树里实测的 14 条历史链接同时存在且无任何守卫，规则因此从未生效；改为可判定的形式而不是删除链接，
  因为指向归档证据的索引本身是有用的，被误用的只是「把归档当作今日规范」这一种。
- 新增权威文件时必须登记到本索引；历史文件不得回链为规范来源。
- 归档操作：移入 `taskpacks/history/` 或 `docs/history/`（保留 Git 历史），不删除。

## 5. Agent 规则与工作流治理接收归档（2026-10-24，非现行任务权威）

用户将跨软件工作流配置、部署、治理和管理归属 WORK-LAB；沿用既有配置所有权与 Adapter 合同，各项目保留领域规则，AAOS 自行修复本项目入口。
既有执行事实和未验证项见[归档摘要](../../../history/archive/workflow-assistance/handoffs/agent-rules-governance-20261024/SUMMARY.md)，并入操作见[接收提示词](../../../history/archive/workflow-assistance/handoffs/agent-rules-governance-20261024/WORK-LAB-INTAKE-PROMPT.md)。
派生资料容器 `WL-STORE-AGENTRULES-20261024` 登记于既有 owner-inputs 目录与成员表；这份导航不新增 CURRENT、任务账本或全局配置授权。

## 6. 上下文服务（OpenViking）标准与手册（2026-10-24，生效）

跨会话记忆与召回的外部基础设施由 WORK-LAB 维护治理边界。现行规范是 `docs/decisions/OPENVIKING_CONTEXT_SERVICE_STANDARD.md`（单端口 127.0.0.1:1933、嵌入维度 1024、五步变更流程、六项验收），操作细节与已知故障见 `docs/decisions/OPENVIKING_DEPLOY_HANDBOOK_20261024.md`。两份文件不新增任务权威或第二账本；客户端配置仍按 `config/config-ownership.json` 的字段所有权处理，模型、服务商、鉴权与端点不在本规范授权范围内。
