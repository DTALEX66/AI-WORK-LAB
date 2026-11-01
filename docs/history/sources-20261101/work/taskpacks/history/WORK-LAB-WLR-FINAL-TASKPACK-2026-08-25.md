# WORK-LAB 最终执行任务包

- TaskPack ID：`WLR-FINAL-20260825-R1`
- 目标仓库：[DTALEX66/WORK-LAB](https://github.com/DTALEX66/WORK-LAB)
- 审计基线：`main@2941412ec88b2b3e278753425255e31d97710295`
- 基线核验时间：`2026-08-25 UTC`
- 状态：`READY_FOR_P0_EXECUTION`
- 前序包：`WL-DEEPEN-20260825-V1`（被本包取代，但保留为历史证据）
- 执行边界：只修改 WORK-LAB；其他项目只通过版本化合同、收据或独立 follow-up 交互。

## 0. 执行者先读

本包是 WORK-LAB 的最终前向整改入口，不是“总体完成”声明。执行者必须先读取当前远端 `main`、根 `AGENTS.md`、`00-governance/`、当前 TaskPack 索引、`10-workflow/workflow-assistance/` 和 `30-observer/work-lab-observer/`，再按本包取证。若本包基线与执行时远端不同，先完成 `WLR-000`，不得把本包 SHA 当作当前事实。

任务状态只允许：

- `TODO`：尚未产生当前 SHA 的验收证据。
- `IN_PROGRESS`：已有唯一 owner 和独立 worktree，尚未通过全部门禁。
- `BLOCKED_RUNTIME`：缺真实软件、账号、设备或人工操作，结构测试不得替代。
- `CONDITIONAL`：只有 bake-off 或 Owner 批准后才进入实现。
- `DONE`：同时满足代码、测试、读回、失败路径、回滚和 exact-SHA CI。
- `REJECTED`：不进入产品；保留裁决与恢复指针。

任何任务不得用旧 handoff、旧测试数、文件存在或 UI 截图代替当前运行证据。

## 1. 不可漂移的产品定位

WORK-LAB 是跨软件、跨项目的轻量治理与执行控制面，拥有：

- 全局 Schema、软件注册、配置所有权、Desired State 与投影规则；
- TaskPack、Work Unit、调度、权限、预算、checkpoint、恢复和验收；
- Hermes、Codex、DeepSeek Harness、GitHub、Open Design、OpenHuman 及未来客户端的 Adapter；
- Context Capsule、Runtime Receipt、Evidence Envelope、漂移与恢复记录；
- 一个可写的 Control/Configuration Surface，以及一个严格只读的 Observer。

WORK-LAB 不拥有：

- Agent、模型、聊天客户端或软件私有数据库；
- ArcheAxis 的 Source/Claim/Evidence/Knowledge/Learning 真值；
- DESIGN-LAB 的 Design IR、领域包、设计质量和专业软件产物；
- 用户凭据、私有会话正文、所有软件的全部配置或大模型资产。

三项目是独立对等仓库。禁止 monorepo、submodule、共享内部数据库、强制所有请求穿过三项目，或新建第四个全局治理项目。

## 2. 本轮云端仓库复审结论

### 2.1 已确认的当前事实

| 事实 | 当前证据 | 裁决 |
|---|---|---|
| 唯一 CURRENT TaskPack 断链 | `00-governance/taskpack-authority-index.json` 指向 `WORK-LAB-FORWARD-RECONCILIATION-2026-08-20 (WLR-000~960)`，正文不在当前树 | P0 恢复/替代并建立哈希、owner、supersedes 校验 |
| DSH 未进入根受管客户端清单 | 根 `AGENTS.md` 仍列 Hermes、Codex、CC Switch、GitHub、Open Design、OpenHuman | P0 统一根规则、registry、config ownership 与 UI 投影 |
| 模型策略违背用户目标 | 根规则强制“无 rate limits、无 cost caps” | P0 改为质量/成本/隐私/延迟四维策略，不再全局强制 |
| Observer 把未知伪装成正常 | `Views.tsx` 多处 `Number(...) || 0`，未知 dirty 显示“干净”，成本按猜测定价 | P0 真值修复；UNKNOWN 必须保持 UNKNOWN |
| 生产 React 未被完整门禁 | 当前 gate 未证明 Observer production React 的 install/build/type/unit/e2e/a11y 全链 | P0 加入 exact-SHA CI |
| 真实客户端证据未闭合 | `CURRENT_STATE` 仍记录 13 个技能 `live_readback:not-run`，Hermes live apply、付费 provider、真实设备、商业发布未验证 | 保持 `BLOCKED_RUNTIME`，不得提升为 DONE |
| 根 License 缺失 | 仓库根没有明确项目许可 | P0 由 Owner 选择许可证；选择前公开复用状态为 `ALL_RIGHTS_UNSPECIFIED` |
| 两个产品表面职责混淆 | 现有 Observer 被历史讨论赋予重试/审批/apply 等写能力 | 正式冻结：Control 可写，Observer 只读 |

### 2.2 旧任务包需要纠正的地方

- 旧包基线 `c2cb6dc...` 已过期；本包以 `2941412...` 为审计基线。
- “Observer 的 token/cost/只读边界已完成”只能视为历史局部修复；当前 React 仍有 UNKNOWN→0/成功/干净的真值缺陷。
- Mission Control 不再是近期主线替换目标。先修复 WORK-LAB 自身权威链、真值、CI 和客户端读回，再做隔离 PoC。
- CC Switch 从“当前主力客户端”降级为 `LEGACY_OBSERVE`，除非执行时证明仍在真实工作流中。
- “默认 fail-open”只适用于非安全提示；权限、写操作、证据、许可证、敏感数据和发布门必须 fail closed。

## 3. 最终产品结构

```text
Canonical Desired State / Authority Index
                 |
        Projection Compiler
                 |
  +--------------+-------------------+
  |              |                   |
Hermes Adapter  Codex/DSH Adapter   Other Adapter
  |              |                   |
  +------ plan / approved apply / readback -------+
                 |
        Runtime Receipt Ledger
                 |
     +-----------+------------+
     |                        |
Control Surface (write)    Observer (strict read-only)
```

关键约束：

1. Canonical 只保存被明确声明的用户层；官方默认与未知字段原样保留。
2. `plan`、`approve`、`apply`、`readback`、`rollback` 是不同状态，不能合并成一个“同步”。
3. Control Surface 只能调用受权 API；Observer 只能消费不可变投影，没有写 token、写路由或重试入口。
4. 每次写入必须有 idempotency key、before/after hash、备份、读回和 rollback receipt。
5. 软件不可用或字段未知时显示 `UNKNOWN/BLOCKED/UNSUPPORTED`，不推断健康、成功、0 或免费。

## 4. 采用的外部规范与开源裁决

以下裁决来自 2026-08-25 对官方仓库/规范的复核。任何代码并入仍须在执行时锁定 tag/commit、复核许可证并进入 SBOM。

| 上游 | 许可/成熟度 | 最终裁决 | 吸收范围 | 禁止范围 |
|---|---|---|---|---|
| [CloudEvents Spec](https://github.com/cloudevents/spec) | Apache-2.0；CNCF graduated；稳定规范 1.0.2 | `ABSORB_SPEC` | 事件 envelope 的 `id/source/type/subject/time/datacontenttype/data` 与扩展字段 | 不引入消息中间件作为前置条件 |
| [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector) | Apache-2.0；成熟生态 | `ABSORB_PROTOCOL + OPTIONAL_SIDECAR` | trace/span/log/metric 语义、OTLP exporter；Collector 仅外置 | 不让 OTel 成为任务真源或 Observer 数据库 |
| [in-toto Attestation](https://github.com/in-toto/attestation) / [SLSA Provenance](https://slsa.dev/spec/v1.2/provenance) | 开放规范；供应链证明成熟 | `ABSORB_SPEC` | artifact/command/materials/products/digest/actor 的可验证收据结构 | P0 不强制部署独立 attestation 服务 |
| [MCP Specification](https://github.com/modelcontextprotocol/modelcontextprotocol) | MIT；工具协议 | `ABSORB_PROTOCOL` | 工具发现与调用边界、能力声明、错误与版本协商 | MCP 返回内容不得自动成为 Authority 或执行许可 |
| [Agent Client Protocol](https://github.com/agentclientprotocol/agent-client-protocol) | Apache-2.0；稳定 wire v1，v2 仍实验 | `ABSORB_PROTOCOL_V1` | 客户端—Agent 会话适配；复用现有 `acp_adapter.py` | 禁止依赖实验 v2 作为发布前置 |
| [Open Policy Agent](https://github.com/open-policy-agent/opa) | Apache-2.0；成熟 | `CONDITIONAL_POC` | 复杂授权矩阵出现维护瓶颈时做 sidecar bake-off | 简单本地规则未证明不足前不替换现有 policy engine |
| [Mission Control](https://github.com/builderz-labs/mission-control) | MIT；功能丰富但上游仍提示 Alpha | `CONDITIONAL_UI_POC` | 合成数据下评估任务/Agent/成本/安全 UI 壳 | 不读取私有会话，不替换 WORK schemas/ledger，不全仓并入 |
| [Dagu](https://github.com/dagucloud/dagu) | GPL-3.0；Windows 单文件、DAG/人工任务完整 | `REFERENCE_OR_EXTERNAL` | 借鉴重试、人工任务、DAG 可视化；必要时独立进程适配 | GPL 代码不嵌入核心，不建立第二调度真源 |
| [Langfuse](https://github.com/langfuse/langfuse) | MIT core，含独立 EE；基础设施较重 | `OPTIONAL_EXTERNAL` | 有真实 LLM tracing/eval 缺口时做 opt-in exporter | 不作为 WORK 核心、默认部署或知识/任务数据库 |

开源状态只有 `ABSORB_SPEC / ABSORB_METHOD / ADAPTER / OPTIONAL_SIDECAR / REFERENCE / QUARANTINE / REMOVE_ACTIVE`。出现过 URL、被复制、被登记或通过静态测试都不等于已吸收。

## 5. 核心合同冻结

### 5.1 `ContextCapsule/v1`

最小字段：

- `capsule_id`、`schema_version`、`project_id`、`repo_url`、`base_sha`、`branch`；
- `dirty_digest` 与逐项 owner 分类，不含私有正文；
- `objective`、`accepted_decisions[]`、`rejected_decisions[]`、`open_tasks[]`、`blockers[]`、`next_action`；
- `authority_refs[]`、`evidence_refs[]`、`test_receipts[]`；
- `created_at`、`expires_at`、`producer`、`sensitivity`、`content_digest`；
- `supersedes[]`、`contradicts[]`、`unknown_fields`。

原始 ChatGPT/Hermes/Codex/DSH 对话只能作为受控导入源。运行时只装载去重后的 capsule，不把全部聊天塞入上下文。

### 5.2 `ExecutionEnvelope/v1`

以 CloudEvents 为外壳，业务数据至少含：

- `work_unit_id`、`taskpack_id`、`task_id`、`attempt`、`idempotency_key`；
- `requested_capability`、`adapter_id`、`permission_scope`、`budget_policy`；
- `input_refs`、`expected_outputs`、`acceptance_refs`、`rollback_ref`；
- `base_sha`、`workspace_id`、`single_writer_lease`、`deadline`。

### 5.3 `RuntimeReceipt/v1`

采用 in-toto/SLSA 的 subject/materials 思路，记录：

- exact command、sanitized args、exit code、start/end、runtime version；
- materials 与 products 的 SHA-256；
- before/after/readback hash；
- permission/approval actor；
- log/screenshot 指针与 hash；
- failure class、retry、rollback 和最终状态；
- `structural/local_runtime/exact_sha_ci/live_installed/release` 证据层。

### 5.4 `Adapter/v1`

统一能力：`discover`、`capabilities`、`plan`、`apply`（可选）、`readback`、`health`、`backup`、`rollback`、`version`、`permissions`。不支持写入的 Adapter 必须明确 `apply_supported:false`，不能静默成功。

## 6. 最终任务 DAG

### WLR-000 — 安装本任务包并冻结当前事实

- 优先级/状态：`P0 / TODO`
- 动作：重新读取远端 `main`、local HEAD、branch、dirty、Actions、Release、运行软件版本、端口和 active TaskPack；把本包复制为仓内唯一 current 前向包，并原子更新 authority index。
- 输出：机器 JSON 与人读 Markdown 共用 digest；authority 记录含 owner、created、expires、supersedes 和本包 SHA-256。
- 验收：索引引用的正文必定存在；缺正文、hash 不符、多个 CURRENT、循环 supersedes 或过期基线均 fail closed。
- 回滚：恢复更新前索引和文件；不删除历史 TaskPack。

### WLR-010 — 根规则、自包含权威与许可证清零

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-000。
- 动作：
  1. 把 DSH 纳入受管客户端，CC Switch 明确 `LEGACY_OBSERVE` 或由证据恢复为 active；
  2. 根规则只内含启动必需约束，不依赖其他仓库才能理解；
  3. 将“full-power/no caps”替换为任务级 `quality/cost/privacy/latency` 策略；
  4. 统一 root、software registry、config ownership、adapter registry 和生成 UI 的 client IDs；
  5. 由 Owner 选择根 License，并补 NOTICE/第三方边界；未选择时明确限制。
- 验收：同一 client 在五个权威面名字、状态和 owner 一致；未知客户端可注册而无需改核心 schema；策略默认不泄露 provider/auth。

### WLR-020 — Authority Index 与生成状态统一

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-010。
- 动作：建立单一 `authority-index.v1`，覆盖 rules/config/skills/plugins/models/taskpacks/ledger/capsules/telemetry/observer/federation；生成 `CURRENT_STATE`，禁止手写重复事实。
- 必须字段：owner、SSOT、generator、consumers、TTL、sensitivity、evidence floor、fallback、backup、supersedes。
- 验收：重复 owner、无 owner、循环、过期、手改 generated 文件、跨项目专业所有权越界均失败。

### WLR-030 — Context Continuity Protocol 实装

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-020。
- 动作：实现 capsule schema、export/import/verify/migrate/redact CLI；为 ChatGPT Export、GitHub、Hermes、Codex、DSH 建 importer；内容哈希去重并保留冲突双方。
- 安全：拒绝 token、cookie、私钥、私有 prompt/response 正文和未经授权的个人目录；只保存来源指针或受控归档 ID。
- 验收：Hermes 导出→Codex 导入→DSH 读回后稳定决定、废止项、下一动作与 exact SHA 一致；旧 schema 可迁移；未知字段无损保留；过期 capsule 明确阻塞。

### WLR-040 — Canonical 配置编译器与 Adapter 收敛

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-020。
- 动作：把配置改为 `canonical intent -> client projection -> plan diff -> approval -> apply -> readback`；首批 Hermes、Codex、DSH、GitHub、Open Design、OpenHuman。
- 保留：官方默认、用户未知字段、provider/model/auth 和客户端私有数据库。
- 验收：六 Adapter 各有 happy/unsupported/failure/rollback；future-client fixture 无需修改核心 schema；重放相同 idempotency key 不产生第二次写入。

### WLR-050 — Observer Truth 与 Control/Observer 权限分离

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-020。
- 动作：
  1. 所有数值使用 `number|null` 与显式 observation state；
  2. dirty 未知不显示“干净”，token/cost 未知不显示 0；
  3. 定价必须有 provider/model/currency/effective_at/source/version；缺项显示 UNKNOWN；
  4. activity/health/success 只按 schema 枚举映射；
  5. 移除 Observer 的 retry/approve/apply/rollback 写入口和写凭据；
  6. Control Surface 写操作全部走 WLR-040 的 plan/approval/readback。
- 验收：schema contract tests 覆盖 null、0、缺失、stale、partial、error；浏览器端无法调用写 API；越权请求 403 并产生安全 receipt。

### WLR-060 — Production React 与多层 CI

- 优先级/状态：`P0 / TODO`
- 依赖：WLR-050。
- 门禁：locked install、typecheck、lint、unit、schema fixtures、production build、Playwright、axe、read-only authorization、Windows path tests。
- 证据分层：结构测试、local runtime、exact-SHA CI、installed runtime、release 分开报告。
- 验收：UNKNOWN 回归夹具、只读越权夹具和过期定价夹具在 CI 必测；CI 产物绑定 commit，不用历史 run 冒充当前。

### WLR-070 — 事件、可观测性与可验证收据标准化

- 优先级/状态：`P1 / TODO`
- 依赖：WLR-030、WLR-040。
- 动作：以 CloudEvents 包装事件；用 OTel trace/span 关联 work unit、adapter attempt 与 receipt；以 in-toto/SLSA 结构记录构建和写操作材料/产物。
- Collector：只作为可删除 sidecar；默认本地、最小字段、无 prompt/body、无凭据。
- 验收：删除 Collector 或 UI 数据库后仍可由 receipt ledger 重建；trace 丢失不影响权威任务状态；敏感字段红线测试通过。

### WLR-080 — 技能、插件、开源与指令供应链治理

- 优先级/状态：`P1 / TODO`
- 依赖：WLR-020。
- 动作：统一 `discovered/installed/enabled/active/disabled/quarantined/removed`；每项绑定 upstream、commit/tag、SPDX、hash、consumer、权限、last_verified、rollback。
- 立即整改：停用错误 Hermes/DSH 身份、重复 OTel ledger、UNKNOWN 许可证 active 来源、跨项目 DESIGN 索引；189 个历史技能快照保留 reference，不激活。
- 指令扫描：第三方 `AGENTS.md/CLAUDE.md/.cursorrules/install` 永远不得自动取得根治理权。
- 验收：active 项必须有消费者与测试；quarantine 不进入 prompt/tool discovery；物理删除前有反向依赖图、提炼物、恢复 commit 和 Owner 批准。

### WLR-090 — 六客户端真实安装、重启和回滚证据

- 优先级/状态：`P1 / BLOCKED_RUNTIME`
- 依赖：WLR-040、WLR-060、WLR-080。
- 场景：discover→plan→approve→apply→完全退出→重启→readback→rollback→再次 readback。
- 必须覆盖：Hermes、Codex、DSH、GitHub、Open Design、OpenHuman；无可用客户端时保持 blocker。
- 验收：真实进程/version/time、公开输入摘要、输出摘要、截图/日志 hash、before/after、失败路径齐全；shell 单测不能替代桌面读回。

### WLR-100 — 备份、恢复、可移植性与灾难演练

- 优先级/状态：`P1 / TODO`
- 依赖：WLR-030、WLR-040。
- 动作：所有机器路径移入未提交 local profile；仓库只保留模板。对 config/capsule/receipt/log/backup 做 secret/path/body 扫描。在空白 Windows 用户上恢复规则、schema、skills 与 adapter，但重新登录各软件。
- 验收：备份加密或明确不含密钥；恢复后 hash/readback 一致；缺 E 盘、用户名变化、软件版本变化和部分备份损坏均有诚实失败与回退。

### WLR-110 — Mission Control/OPA 等条件 PoC

- 优先级/状态：`P2 / CONDITIONAL`
- 依赖：WLR-050、WLR-060。
- Mission Control：只用合成数据，锁 commit，裁决仅 `ACCEPT_UI_PATTERN / ACCEPT_UI_SHELL / REJECT`；不允许 `FULL_REPLACE`。
- OPA：仅当现有 policy tests 证明复杂度/一致性瓶颈时评估；比较启动重量、Windows、调试、离线、升级、回滚。
- 验收：每个 PoC 有退出日期、上游 commit、数据边界、性能、许可、卸载读回；拒绝后 90 天不重复研究。

### WLR-120 — 真实跨软件与三项目小型闭环

- 优先级/状态：`P1 / TODO`
- 依赖：WLR-030、WLR-040、WLR-070、WLR-090。
- 跨软件：Hermes 创建 Work Unit→WORK 生成 TaskPack/Capsule→Codex 或 DSH 执行→GitHub exact-SHA CI→新会话恢复。
- 跨项目：WORK 只传 ExecutionEnvelope/Receipt；ArcheAxis 返回候选证据查询；DESIGN 返回 Artifact/Quality/Production Receipt。任何一方离线都可独立运行。
- 验收：网络失败、旧摘要冲突、重复提交、取消、过期 capsule、回滚和单项目离线全覆盖；第二软件无需重新询问已冻结定位。

### WLR-130 — 收敛发布与短期冻结

- 优先级/状态：`P2 / TODO`
- 依赖：本期批准的 WLR-010～120。
- 动作：生成 exact-SHA Current State、升级/恢复/卸载说明、SBOM/NOTICE、权限矩阵和 Release Receipt；关闭本期 WORK 大改，进入维护窗口，让 ArcheAxis 成为下一主线。
- 验收：没有聚合 `DONE`；每个未完成项保持 `BLOCKED/CONDITIONAL`；公开声明不超过最弱真实证据层。

## 7. 执行波次与并行限制

| 波次 | 任务 | 放行条件 |
|---|---|---|
| G0 | WLR-000、010、020 | 唯一 current 包正文存在；根规则/注册/许可证状态诚实 |
| Truth | WLR-030、050、060 | Capsule 可迁移；Observer 不伪造；React 进 CI |
| Control | WLR-040、070、080 | Adapter、事件、收据、供应链合同冻结 |
| Runtime | WLR-090、100 | 真实客户端或诚实 blocker；恢复演练完成 |
| Proof | WLR-120 | 跨软件与小型三项目闭环可失败、可回滚 |
| Freeze | WLR-110（可选）、130 | WORK 短期收敛，不继续无限扩张 |

同一仓库并行写入必须使用独立 worktree 和单写者 lease；同一文件/生成器不可并行修改。不得一次提交跨三个仓库。

## 8. 每项任务的强制证据包

每个任务目录至少包含：

1. `task.json`：task ID、owner、base SHA、worktree、状态、依赖；
2. `changes.json`：文件、原因、before/after hash；
3. `commands.jsonl`：命令、时间、exit code、sanitized output hash；
4. `tests.json`：分层门禁与失败路径；
5. `readback.json`：真实状态读回；
6. `rollback.json`：步骤、结果、恢复 hash；
7. `oss.json`：上游、commit/tag、SPDX、NOTICE、SBOM、退出策略；
8. `receipt.intoto.json`：subject/materials/products 与 actor；
9. `summary.md`：只引用机器事实，不复制动态数字。

## 9. 最终完成定义

WORK-LAB 本轮只有在以下条件同时成立后才可发布：

- 当前 TaskPack 不断链，Authority Index 可机器验证；
- DSH、六客户端注册、配置 ownership 和 UI 投影一致；
- Observer 对 UNKNOWN/stale/partial/error 诚实，且技术上只读；
- Control 写入具有 plan、approval、idempotency、backup、readback、rollback；
- Context Capsule 跨 Hermes/Codex/DSH 可迁移且不携带私有正文/凭据；
- production React、schema、权限、Windows 路径进入 exact-SHA CI；
- 至少一条真实客户端重启闭环与一条失败/回滚闭环完成；
- License/SBOM/NOTICE/开源 active 面闭合；
- WORK、ArcheAxis、DESIGN 任一离线时不会把 UNKNOWN 显示成成功，也不会破坏其他项目独立运行。

## 10. 明确禁止

- 禁止让 Observer 执行、审批、重试、apply 或 rollback。
- 禁止把 Mission Control、OTel、Langfuse、OPA、Dagu 或 MCP 变成第二任务/知识真源。
- 禁止读取未由用户导出的 ChatGPT/Codex/Hermes 私有会话目录。
- 禁止管理其他项目专业数据库、知识真值和设计质量。
- 禁止默认无成本上限、无隐私约束或无权限门。
- 禁止把测试绿色、静态发现、文件存在、历史 screenshot 或旧 Release 写成“全部软件已管理”。
- 禁止在没有恢复清单和 Owner 批准时物理删除历史开源资产。

## 11. 官方调研来源

- [CloudEvents Specification](https://github.com/cloudevents/spec)
- [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector)
- [in-toto Attestation Framework](https://github.com/in-toto/attestation)
- [SLSA Provenance v1.2](https://slsa.dev/spec/v1.2/provenance)
- [Model Context Protocol](https://github.com/modelcontextprotocol/modelcontextprotocol)
- [Agent Client Protocol](https://github.com/agentclientprotocol/agent-client-protocol)
- [Open Policy Agent](https://github.com/open-policy-agent/opa)
- [Mission Control](https://github.com/builderz-labs/mission-control)
- [Dagu](https://github.com/dagucloud/dagu)
- [Langfuse](https://github.com/langfuse/langfuse)

研究时间点为 2026-08-25；实际并入必须重新锁定不可变 commit/tag，不得引用 `latest` 作为供应链证据。
