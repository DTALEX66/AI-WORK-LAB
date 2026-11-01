# WORK-LAB Stage 3 control-plane and Codex enhancement handoff

> **STATUS: SUPERSEDED / HISTORICAL (2026-08-10)**
>
> 本文件已被 `WORK-LAB-FINAL-MASTER-CONTROL-PLANE` v2.0 取代（权威交接：
> `.hermes/desktop-attachments/WORK-LAB-FINAL-MASTER-HERMES-TASKPACK-2026-08-10.md`，
> tracked 图：`50-taskpacks/WORK-LAB-STAGE-3-TASK-GRAPH.json`，taskpackId=
> `WORK-LAB-FINAL-MASTER-CONTROL-PLANE`）。本文件仅作为历史证据保留，不再作为
> 前向执行权威；其中 PR #33 应标记为 `STAGE3_FOUNDATION_SLICE`，不代表
> WL3-000..WL3-820 全部完成。

## 摘要

本交接描述 WORK-LAB 在 2026-08-10 的 Stage 3 发布候选：项目继续以 Workflow Assistance 为唯一主动工作流控制、治理、任务、交付和可观测层，Observer 保持严格只读；同时交付一套基于 Codex 官方配置面的用户层增强包，使 Codex 能在非 WORK-LAB 项目中复用通用执行、数据、验证和 Git 交付边界，而不覆盖用户 provider、model、MCP、plugin、认证、会话或 Desktop 私有状态。

这不是整个 Stage 3 TaskPack 的完成声明。它是已实现并通过本地 canonical quality gate 的依赖安全切片；未具备 exact-SHA GitHub CI、merge 或远端 main 回读前，不得提升为云端交付完成。

## 交付身份

| 项目 | 值 |
|---|---|
| Repository | `DTALEX66/WORK-LAB` |
| Default branch | `main` |
| Baseline local/remote commit | `a3a6fa63b9548dfc4e4b2390bb9c6257dfacdfa3` |
| Baseline tree | `3f2fa6fdc312eb7b1c556f6a3ff84770f9cceba3` |
| Stage 3 TaskPack | `WORK-LAB-STAGE-3-CANONICAL-CONTROL-PLANE` v1.0 |
| Prepared at | `2026-08-10 00:41 +0800` |
| Writer policy | `SINGLE_WRITER` |
| Publication identity | 以包含本文件的 Git commit、PR 和 exact-SHA CI 为准，不在文件内保存自引用 SHA |

## 项目定位和边界

当前 active modules 只有：

1. `10-workflow/workflow-assistance`：主动控制面，拥有配置合同、Task Ledger、唯一 Telemetry Ledger、Sidecar、Adapter、交付和验证门禁；
2. `30-observer/work-lab-observer`：严格只读投影，可读 Workflow 公开投影，但不能执行、批准、重试、应用、回滚、改变任务状态或写 Telemetry Ledger。

Open Design 已迁至 `DTALEX66/DESIGN-LAB`；MiniGame 仅保留历史 fixture/archive。两者不得由本切片恢复为 active module 或普通 CI Gate。

## 实现总结

### 1. Stage 3 治理与当前状态

- 新增 Stage 3 machine-readable task graph 和 baseline；
- 固定 active-module registry、CURRENT_STATE generator 和测试为 Workflow + Observer；required CI 重新计算 canonical source digest 和 deterministic projection digest，避免 tracked CURRENT_STATE 失鲜；
- 退役普通 CI 中已迁出的 Design/MiniGame 主动 Gate，同时保留明确标注的历史与 archive 证据；
- 修正 CURRENT_STATE、context pack 和 schema 验证的一致性；
- 更新 aggregate gate、release policy、TaskPack summary 和 archive pointer。

### 2. Workflow Assistance 控制面切片

- Platform Identity schema/resolver：脱敏识别 launcher/profile/config root，歧义时 fail-closed；
- Instance reconciler：协调 canonical launcher/profile/config root，不修改认证或平台私有状态；
- Config ownership schema/coordinator：只生成字段级 ActionPlan，未知、内部和秘密字段隔离或禁止；
- Project Profile registry/loader：支持跨项目 profile 与 standalone fallback；
- Telemetry Ledger：Workflow-owned、append-only、拒绝敏感字段和重复事件，可重建 projection；
- loopback-only Sidecar：提供只读 health/projection/snapshot/SSE，真实 SSE frame、`Last-Event-ID` reconnect、精确 loopback CORS，外部 Origin 拒绝，写控制返回 405；
- Sidecar 启动已接入 owner-token single-instance lock、dead-PID stale lock 恢复和项目内 `sidecar-endpoint.json` discovery；
- Telemetry 保留字段和规范化嵌套敏感字段均 fail-closed，调用方不能覆盖权威 producer/sequence/digest；
- Observer read-only projection adapter；
- CI watcher 增加状态、输出和 freshness 投影。

这些能力是基础控制面切片，不代表完整 durable worker lease/fencing/zombie recovery、发布编排或所有 Stage 3 任务均已完成。

### 3. Observer 实时只读投影

- 保持 GET-only API 和 `externalMutation=false`；
- 增强 live/snapshot、SSE reconnect、stale/offline 和 projection freshness 状态；浏览器实际订阅 Workflow Sidecar 的 loopback SSE，断线保留 last-good 但投影显式变为 stale；
- snapshot fallback 永远以 `SNAPSHOT/stale` 展示，不能沿用伪 `LIVE/fresh`；公开任务投影只显示用户可读标题，不暴露内部 `taskId`；
- Full/Compact × Dark/Light 四视图继续共享同一权威 projection；
- 前端、schema、runtime/store 和回归测试同步更新；
- 不增加任务控制、审批、重试、执行、Ledger 写回或第二个控制面。

### 4. Codex 全局工作流增强

仓库新增可审计的 Codex 原生资产和同步器：

- 用户 guidance managed block：`$CODEX_HOME/AGENTS.md`；
- 用户 Skills 官方根：`$HOME/.agents/skills/workflow-assistance-*`，共 8 个；
- 命令策略：`$CODEX_HOME/rules/workflow-assistance.rules`；
- 字段级 config defaults：`approval_policy=on-request`、`sandbox_mode=workspace-write`、`project_doc_max_bytes=65536`；
- `plan/apply/verify/rollback`、冲突阻断、hash readback、旧 state v1/v2 → v3 迁移；v3 增加 mixed-ownership CAS、operation lock、`applying/rolling_back/applied` 恢复阶段、owner/hash fenced rollback、retired Skill 和 Windows reparse-point 防护；
- WORK-LAB 项目专用 skill 位于 `.agents/skills/work-lab-workflow/`，不会被提升成普通项目全局合同。

先前真实本机 v2 回读证明 Codex CLI 使用原有 `cc-switch-official / gpt-5.6-luna`，8 个用户 Skills 可在非 WORK-LAB Git canary 中发现；当前 Hermes 聊天的 `openai-codex / gpt-5.6-sol` 是独立运行层。最新 v3 源码已在项目内隔离 Codex Home 完成 `plan → apply → verify → rollback → reapply → verify`，并回读证明 provider/model/base URL/MCP/plugin/未知字段全部保留。真实用户 Home 仍以先前 v2 readback 为准，未用本轮发布候选覆盖。用户认证、会话和 Desktop 状态从未被仓库接管。

## 本地验证证据

| 检查 | 结果 |
|---|---|
| Workflow 定向测试 | Codex 17、quality-gate discovery 1、Sidecar lock 3、Sidecar 2、Telemetry 3，全部 PASS |
| Observer Python / Node | Python 47；Node 43，全部 PASS |
| Codex v3 isolated lifecycle | `plan/apply/verify/rollback/reapply/verify` PASS，3 managed fields，8 Skills，私有/未知字段保留 |
| Final exact-tree quality gate | 待冻结最终 tracked tree 后重跑；旧后台 `QUALITY_GATE_PASS` 不冒充当前树证据 |
| Codex strict config entry parse | PASS |
| Codex command policy negative control | hard reset forbidden；push prompt |
| 非 WORK-LAB Codex canary | PASS，规则与 8 Skills 可发现 |
| Live rollback → readback → reapply | PASS |
| Core schema contract | 24 schemas，positive/negative controls PASS |
| Candidate secret scan | 待最终 staged candidate 冻结后重跑；早期 0 findings 不冒充当前树证据 |
| `git diff --check` | 待最终 staged candidate 冻结后重跑 |

本地 Gate 不等于 exact-SHA GitHub CI。云端证据必须绑定包含本交接的最终 candidate commit。

## 错误与根因修正摘要

| 症状 | 根因 | 修正 |
|---|---|---|
| 初始 Codex skill 放在 `.codex/skills` | 使用了过时/非官方发现根 | 迁移到官方 `.agents/skills`；新增用户与项目级发现说明 |
| TOML managed 字段最初追加后落入最后一个 table | TOML 顶层键必须在首个 table 之前 | managed block 插入首个 table 前，并用 `tomllib` 回读 |
| 状态加固后旧 live state 暂时无法维护 | v1 缺少 `managed_skill_names` | 升级 state v3，增加受控 v1/v2 迁移、两阶段 apply/rollback 和隔离生命周期回读 |
| 无 state 时 rollback 可能误认同名资产 | 仅按路径/内容推断所有权不安全 | 缺失 ownership state 时对 managed-looking 资产 fail-closed |
| guidance verify 只检查 marker | marker 存在不等于内容未漂移 | 增加 managed block 内容回读与 drift 测试 |
| Sidecar SSE/lock/Origin 存在发布阻断 | 字面量换行、锁未接启动、Origin 前缀判断 | 改为真实 SSE frame、owner-token/PID lock、endpoint discovery 和结构化 loopback Origin 校验 |
| Snapshot/last-good 可能继续显示 LIVE/fresh | 数据 mode 与 freshness 没有在断线时重投影 | 断线和 snapshot 均重建 stale/offline 显示，EventSource reconnect 只触发 GET readback |
| `context_lines` 在 context pack 中未导入 | 新增使用点缺少 import | 修正 import 并纳入 canonical Gate |

## 未完成与不得冒充完成的边界

- Stage 3 task graph 的后续 durable worker、完整 lease/fencing/zombie recovery、全部 Adapter、R3/portable desktop、release qualification 和 human visual acceptance 尚未全部完成；
- WL3-200+ 成长/实时 Observer/CI 收口和 WL3-520+ SSE/交付收口仍需按 task graph 继续，而不是由本交接自动关闭；
- Windows Tauri portable build、WebView/WebDriver/restart readback 没有由本地 Python/JS Gate替代；
- 没有 tag、release、installer 或 live cloud service deployment；
- Codex 用户 Home 的 live overlay 已本地应用并回读，但用户 Home、认证、会话和私有配置绝不进入 Git；仓库上传的仅是可移植源、测试和文档；
- exact-SHA PR CI、merge commit 和 post-merge main CI 必须在云端交付时单独记录。

## 云端交付合同

1. 仅提交本交接声明的受控候选源、测试、CI 和文档路径；以最终 staged name-status 为唯一文件清单；
2. 不提交 `.hermes/`、Codex/Hermes Home、凭据、缓存、日志、session、prompt/response 或 Desktop 私有状态；
3. 由于 `main` 强制线性历史、PR review、`aggregate` required check、禁止 force-push/delete，使用 feature branch → PR → exact-head CI → merge；
4. merge 后验证本地 `main`、`origin/main`、GitHub default branch 指向同一 SHA，并验证该 SHA 的 `work-lab-gate`；
5. 任一 required job 失败、取消、缺失或仍在运行，都不能称为云端同步完成。

## 接手入口

新会话先执行只读身份核验：

```text
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
gh pr list --state open
gh run list --branch main --limit 5
```

然后读取：

1. `AGENTS.md`；
2. 本交接；
3. `50-taskpacks/WORK-LAB-STAGE-3-TASK-GRAPH.json`；
4. `00-governance/generated/STAGE3_BASELINE.json`；
5. `10-workflow/workflow-assistance/docs/workflow/codex-global-enhancement.md`。

只有当前云端 SHA、CI 和 live checkout 与本交接一致时，才从 WL3-200+/WL3-520+ 选择下一个 dependency-safe 单写者切片。
