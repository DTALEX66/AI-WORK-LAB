# Workflow-assistance

[![work-lab-gate](https://github.com/DTALEX66/WORK-LAB/actions/workflows/work-lab-gate.yml/badge.svg)](https://github.com/DTALEX66/WORK-LAB/actions/workflows/work-lab-gate.yml)

面向 Windows、Linux 与 macOS 的 **客户端中立工作流控制、治理、任务、交付与可观测层**：以可迁移合同和 Adapter 连接 Hermes、Codex、CC Switch、GitHub 与未来客户端入口；集中维护无密钥配置、ActionPlan、项目边界、任务证据、链路诊断、Context7 MCP、Agent Skills、治理测试和跨平台 CI。

## 项目定位

`Workflow-assistance` 不是 Agent Runtime、聊天软件、模型网关，也不是 Hermes、Codex 或 CC Switch 的安装包。它是一个**客户端中立的工作流控制与治理层**：核心只解析 manifest、合同、任务、证据和边界；具体执行入口通过可替换 Adapter 接入。Hermes 当前仍是一级深度支持 Adapter，但不是核心架构前提。

当前一级 Adapter：`Hermes`、`Codex`、`CC Switch`、`GitHub`。Cursor、Claude Code、WorkBuddy 先以 manifest-only/只读检测方式登记，必须有真实证据后才升级支持级别。Open Design 已迁出并由独立仓库维护，不再是本模块 Adapter。

跨电脑配置审查采用项目级随机 opaque `machine_id`，只用于识别当前项目副本并触发只读 `plan/verify`；它不是认证、授权或硬件指纹。状态模型、只读计划命令和配置升级边界见
[`docs/current/workflow-assistance/workflow/machine-identity-and-config-review.md`](docs/current/workflow-assistance/workflow/machine-identity-and-config-review.md)，实现入口为
`services/authority/machine_identity.py`。设备切换不会自动 apply、覆盖 OBSERVE/SECRET 字段、清认证或执行 Windows Reset。

核心不负责：Agent 人格、聊天/Prompt 输入、模型推理、Provider 路由、凭据管理、自动批准外部写入。每个写操作都必须从用户批准的 ActionPlan 进入对应 Adapter。

全局增强范围包括：跨客户端任务生命周期、配置/权限边界、项目数据隔离、ActionPlan 与回滚、交付和 evidence envelope、token/网络/GitHub/artifact 观测，以及各 Adapter 的安全接入。任何新增能力都必须先判断它增强的是这条通用工作流，还是只对本仓库有用；只对本仓库有用的临时脚本不得被包装成默认全局能力。

Codex 增强模块的责任和能力已单独冻结为合同：
[`docs/current/workflow-assistance/workflow/codex-enhancement-boundary.md`](docs/current/workflow-assistance/workflow/codex-enhancement-boundary.md)，机器可读权威为
[`config/codex-enhancement-boundary.json`](config/codex-enhancement-boundary.json)。该模块只管理官方 Codex 配置面上的明确用户 overlay，不拥有 Codex runtime、provider/model、认证、MCP/plugin、会话、Desktop 状态、项目 Task Ledger 或外部写入能力；新增全局能力必须先更新该合同和测试。

```text
Client-neutral workflow control plane
├─ Core contracts     manifest, adapters, domain packs, plans, runs, events, evidence
├─ Adapter boundary   Hermes / Codex / CC Switch / GitHub / future clients
├─ Governance         approval, project containment, rollback, redaction, exact-SHA CI
└─ Replaceable entry  client-specific runtime remains optional and independently verified
```

本仓库承载的全局增强资产包括：

```text
Workflow-assistance
├─ portable config        客户端中立、无密钥的核心基线与可选 Adapter overlay
├─ safe deployment        repo → live 单向同步、备份、保留本机状态
├─ route operations       GPT OAuth / DeepSeek 切换与链路诊断
├─ coding-agent workflow  Codex launcher、任务票据、单写者与冻结复审
├─ MCP policy             默认只启用 Context7，其他能力按需开启
├─ token monitor          本地实时读取真实 usage，不做字符估算
├─ reusable skills        Agent、测试、Windows、代码复审等知识资产
└─ governance             安全扫描、治理测试、Linux/Windows CI、吸收审计
```

它保存可以安全提交到 Git 的工作流资产；不会安装 Hermes、Codex 或 CC Switch 主体，也不会保存 OAuth 状态、API Key、会话数据库、日志、缓存、模型权重或用户数据。

## 2026-07-28 发布状态与错误总结

本轮已将 `github-auth`、`github-code-review`、`github-issues`、`github-pr-workflow` 和
`github-repo-management` 纳入仓库托管的全局 GitHub 工作流资产。当前 13 个 skill 都是
`repository-controlled` portable source，经过 provenance、repo → live atomic sync、隔离
portable install、Linux/Windows CI 和 live runtime 回归。

下面这段是 2026-07-28 那一轮的复审记录，仅作归档参考，不是当前规范：该轮修正了 GitHub skill 的 source
ownership 缺口、未认证 curl/凭据持久化误导、PR changed-files 分页缺失、SSH 私钥无授权写入、
PowerShell/POSIX 命令不兼容和文档定位不一致，完整的错误、根因、修复和证据记录见
[`docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-28.md`](docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-28.md)。

Token Monitor 本轮的交接、验证证据、错误根因、剩余事项和恢复顺序见
[`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`](docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip)（成员 token-monitor-handoff-2026-08-05）
（已归档，2026-08-05，非现行规范）。

GitHub Actions 曾报告 action 自身的 Node.js 20 runtime 弃用提示；它是非阻断上游维护提示。
本项目不在 workflow 中硬编码 Node 版本，也不为了消除提示随意替换 action；若后续处理，必须
走审阅后的自动依赖更新策略。

## 功能总览

| 功能域 | 当前能力 | 主要入口 |
|---|---|---|
| Portable 配置 | 无密钥 Hermes 基线、中文 CLI、原生工具集、Context7、低风险插件默认值 | `config/config.yaml` |
| 安全部署 | Windows / Bash 安装入口、自动备份、单向同步、保留 live Provider 与自定义能力 | `setup.ps1`、`setup.sh` |
| 模型切换 | GPT OAuth 与 DeepSeek 官方 Provider 状态检查和安全切换 | `integrations/executors/hermes/switch_model.py` |
| 全链路诊断 | Hermes、认证、MCP、代理端口、Node、Codex 版本和可选真实执行 smoke | `integrations/executors/hermes/hermes_workflow_doctor.py` |
| Codex 执行 | 跨平台 launcher、非交互执行规则、只读审查、隔离 worktree、TaskPack exact-tree runner；默认只冻结，需显式 `--publish` 才可发布 | `packages/client-neutral-core/bin/codex*`、`services/orchestration/run_taskpack_agent.py`、`packages/client-neutral-core/skills/autonomous-ai-agents/codex/` |
| GitHub 交付 | `main` 作为跨设备 SSOT；仅以 exact-SHA CI 与目标分支包含关系确认发布闭环 | `../../.github/workflows/work-lab-gate.yml`、`agent-workflow-fortress` |
|| 睡眠模式 | 项目级持久 cron 队列、单 writer、依赖顺序、账本恢复与高风险阻断 | `packages/client-neutral-core/skills/software-development/sleep-mode/` |
||| Growth candidates | 候选发现、来源摘要 intake、隔离、扫描、评估、显式审批晋级、隔离阻断、精确 readback 与退役回滚；默认不自动批准 | `packages/contracts/schemas/workflow/growth-candidate.schema.json`、`packages/client-neutral-core/scripts/growth_candidates.py` |
|| Gateway/Cron 投递 | 区分 Gateway 运行、消息平台配置、TUI 本地输出和 sleep-mode 项目账本 | `docs/current/workflow-assistance/workflow/gateway-cron-delivery.md` |
| 项目数据边界 | fail-closed Git-ignore 检查，将任务临时文件、缓存、日志、测试环境和产物锁进本地项目 | `packages/client-neutral-core/bin/hermes-project-data.py`、`packages/client-neutral-core/skills/software-development/project-data-boundary/` |
| 执行预检 | 只读分离当前分支/upstream/main、解释器与可选依赖、Markdown 相对链接；输出无密 JSON，不读取 auth/session/memory | `packages/client-neutral-core/scripts/execution_preflight.py`、`docs/current/workflow-assistance/workflow/codex-execution-reliability.md`、`docs/current/workflow-assistance/workflow/codex-performance-diagnosis.md` |
| Token 监视器 | Windows Tauri 2 Dashboard，实时扫描本地 JSON/JSONL usage，按 GPT/Codex、DeepSeek 和模型显示输入/输出/缓存/reasoning/总 token；无 usage 时不估算 | `apps/token-monitor/`、`packages/client-neutral-core/scripts/token_monitor.py`、`docs/current/workflow-assistance/workflow/token-monitor.md` |
| MCP | 默认固定 Context7 包版本；候选 MCP 另行执行 pinned provenance 审计 | `docs/current/workflow-assistance/mcp/workflow-mcp-stack.md`、`docs/current/workflow-assistance/mcp/mcp-catalog-governance.md`、`packages/client-neutral-core/scripts/mcp_candidate_audit.py` |
| Agent 治理 | TDD、单写者、Task Ticket、结构化状态、fail-closed 契约、exact-tree 复审、CI 闭环 | `agent-workflow-fortress` |
| Context Pack | repomix/gitingest 风格的安全上下文包，输出到项目 `.project-local/artifacts/`，用于新会话与 Codex handoff | `packages/client-neutral-core/scripts/build_context_pack.py`、`docs/current/workflow-assistance/workflow/context-pack.md` |
| Context Control Plane | 跨客户端稳定前缀 + 缓存命中真值 + 防漂移压缩（§12）；客户端配置建议 | `packages/client-neutral-core/scripts/context_control_plane.py`、`context_bundle.py`、`context_drift_guard.py`、`docs/current/workflow-assistance/workflow/context-control-plane-design.md`、`context-control-plane-client-config.md` |
| External Libraries Index | 共用/私用库链接与资产列表（内容不上传）；JSON 校验 gate | `.project/governance/external-libraries-index.json`、`packages/client-neutral-core/scripts/verify_external_libraries_index.py` |
| GitHub Delivery | 上传加速（状态→提交→推送→PR）+ 审核加速（checks+mergeable+本地 gate 聚合判定） | `packages/client-neutral-core/scripts/github_upload_accelerator.py`、`github_review_accelerator.py`、`github_common.py` |
| Agent 行为评估 | promptfoo 风格声明式 smoke cases，评估工作流边界回答；不默认安装 runner/provider | `docs/current/workflow-assistance/workflow/agent-evaluation.md`、`packages/client-neutral-core/templates/evals/agent-behavior-smoke.yaml` |
| UI/Skin 系统 | Catppuccin、shadcn/ui、assistant-ui 风格吸收，提供主题 token、Agent UI patterns 和 Windows Terminal scheme；不默认安装 UI runtime | `docs/current/workflow-assistance/workflow/ui-skin-system.md`、`packages/client-neutral-core/templates/ui/`、`packages/client-neutral-core/templates/windows-terminal/` |
| 本地质量门禁 | 跨平台 canonical gate runner，统一治理测试、语法、安全扫描、Context Pack、MCP 候选审计、Shell/PowerShell 解析 | `services/orchestration/run_quality_gate.py`、`Justfile`、`docs/current/workflow-assistance/workflow/local-quality-gates.md` |
| 安全扫描 | Prompt/规则隐藏字符、注入特征和疑似硬编码秘密扫描 | `packages/client-neutral-core/scripts/security/scan_agent_rules.py` |
| 模板库 | AGENTS/CODEX/DESIGN/SECURITY 规则模板及多类任务票据 | `packages/client-neutral-core/templates/` |
| 审计与证据 | 开源能力吸收记录、固定上游 SHA、机器可读清单、明确排除项 | `docs/history/archive/workflow-assistance/audit/` |
| 跨平台验证 | Python 治理测试、语法检查、Shell/PowerShell 解析、Linux/Windows Actions | `../../.github/workflows/work-lab-gate.yml` |

## Portable 部署与安全同步

### 新机器部署

先通过官方方式独立安装 Hermes Agent，再克隆本仓库：

部署脚本需要 Python 和 `PyYAML>=6,<7`。它不会自动修改全局 Python 环境；
依赖缺失时会在任何 Hermes Home 写入前 fail-closed。

```bash
git clone git@github.com:DTALEX66/WORK-LAB.git
cd WORK-LAB

# Linux / macOS / Git Bash
bash scripts/setup-workflow.sh

# Windows PowerShell
.\scripts\setup-workflow.ps1
```

两个 setup 入口默认只生成 ActionPlan，不写 live Home。显式传入
`scripts/setup-workflow.sh --apply` 或 `setup-workflow.ps1 -Apply` 后才会调用：

```bash
python integrations/executors/hermes/sync_hermes_workflow_assets.py --apply --approved
```

### 单向同步模型

同步脚本只执行 **repo → live Hermes Home**：

```bash
# 预览，不写入
python integrations/executors/hermes/sync_hermes_workflow_assets.py

# 备份后应用
python integrations/executors/hermes/sync_hermes_workflow_assets.py --apply --approved
```

实际行为：

- 在 Hermes Home 下创建时间戳备份；
- 从 `config/managed-config-schema.yaml` 读取精确的 13 个 managed skill 根并逐根事务替换，删除这些子树中已不在权威源里的旧附件；不提升整个 `$HERMES_HOME/skills/` 根，因此 staging 后新增的 Hermes bundled 或用户 skill 也会保留；
- 逐文件部署 schema 声明的 6 个 managed launcher/guard，保留 live `$HERMES_HOME/bin/` 中其它 Hermes 官方或用户入口；同时部署无密钥 `.env.template`；
- **绝不 promotion live `config.yaml`**：它同时包含用户的 provider/model、认证、MCP、plugin、hook、会话与未来字段，无法对外部写入实现可移植的原子 compare-and-replace。同步器只输出“skip mixed-ownership live config.yaml”；用户若要调整这些设置，必须明确使用官方 Hermes 配置入口并自行复核；
- `config/config.yaml` 只作为无密钥 portable baseline，由空的 isolated Home verifier 构造并验证，不能据此声称已部署到真实 profile；
- `mcp_servers.owned_names` 仅定义 baseline 的结构所有权与 isolated 验证范围，不授权同步器替换或删除真实 Home 中的 MCP；历史或用户 MCP（例如 `public-apis`、`sequential-thinking`）不受同步器影响；
- plugin migration state 同属 mixed-ownership config，不会由同步器写入真实 Home；
- 只删除有明确路径登记的退役 skill 资产；
- 输出 repo/live 目录哈希和文件数用于核验；
- 使用 `config/managed-config-schema.yaml` 声明哪些非秘密体验字段由包管理、哪些本机路由/认证字段必须保留；
- 绝不把 live skills、`.env`、认证、会话或日志反向复制到仓库。

### 可复制性与兼容性验证

每次发布前，质量门禁都会在一个空的、隔离 Hermes Home 中执行 portable sync：

```bash
python packages/client-neutral-core/scripts/verify_portable_install.py
```

它不调用模型、不读取现有 Hermes Home、不读取认证文件；它会 fail-closed 验证
`workflow-manifest.yaml` 声明的 config compatibility/runtime features、model/provider-neutral
portable config、13 个 managed skill 根、6 个 managed binary、Context7 的 copied wrapper 与 pinned package 都可部署。它不把
结构检查伪装成 MCP spawn 或 `hermes config check`；后二者只能在明确启用的隔离 integration
gate 中执行。兼容性承诺和功能清单位于 `workflow-manifest.yaml`。

新项目应先忽略 `.project-local/`，再使用最小项目初始化器：

```bash
python services/orchestration/bootstrap_project.py D:/All-projects/NewProject --dry-run
python services/orchestration/bootstrap_project.py D:/All-projects/NewProject --agent-rules
```

该入口只写目标项目的 Git-ignored `.project-local/` 运行时说明和 bootstrap manifest，绝不复制 OAuth、API key、provider route、会话或用户数据。

### Portable Hermes 基线

`config/config.yaml` 当前定义：

- Hermes CLI 中文界面；
- 忙时输入默认排队：`display.busy_input_mode = queue`，避免新输入隐式打断当前 turn；
- 原生 `browser`、`clarify`、`code_execution`、`computer_use`、`cronjob`、`delegation`、`file`、`image_gen`、`memory`、`session_search`、`skills`、`terminal`、`todo`、`vision`、`web` 工具集；
- 默认 MCP 仅 Context7；
- 默认插件为 `security-guidance` 与 `web/ddgs`；
- 会话不自动裁剪，并启用用户记忆与 profile；
- **不定义** Provider、模型、base URL、API key、fallback、model picker lane 或模型切换命令；这些值完全由官方 Hermes setup 和 live 用户状态负责。repo→live sync 不读取、合并或写回 live config；
- `hooks.pre_tool_call` 默认注册项目 terminal guard；它只允许 canonical project wrapper，阻止未声明
  workdir、shell chaining 和项目外输出。该 hook baseline 仅在 isolated verifier 中构造；真实 profile 的 hook
  由用户使用官方入口显式管理与批准，不能通过同步器静默绕过 Hermes hook trust。

`config/SOUL.md` 保存可迁移的 Agent 行为风格，并通过
`managed-config-schema.yaml` 的 `owned_file_mappings` 以
`config/SOUL.md → $HERMES_HOME/SOUL.md` 的明确单文件映射进入同一套
backup → staging → atomic promotion 流程；`config/.env.template` 只列环境变量名称，不含真实值。

### 软件更新与升级后恢复

本项目不是 Hermes、Codex、CC Switch、Open Design 或 OpenHuman 的日常软件更新器。
软件升级由用户决定，或由官方稳定版渠道推送；版本提示只能作为只读兼容性事实，不能自动
转化为项目的 apply 任务。

若用户升级后报告工作流损坏，可在其明确授权下，按“只读发现 → 无密 ActionPlan → 最小
受管 apply/rollback → verify 与幂等 plan 回读”的顺序恢复本项目明确拥有的 Rules、Skills、
字段级配置和已声明的 Hermes 受管文件映射。恢复绝不替代官方安装/更新，也不接管
Provider、模型、认证、Token、会话、私有记忆、Desktop 内部状态、CC Switch 路由或 Open
Design 的设计能力配置。上面那条恢复顺序就是当前的流程；下面这份是 2026-08-13 那一轮的
基线结论与已处理事项记录，仅作归档参考，不是当前规范：
[`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`](docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip)（成员 workflow-baseline-and-recovery-handoff-2026-08-13）。

## 模型切换与路由诊断

### 安全切换

`packages/client-neutral-core/skills/model-switch/SKILL.md` 与切换脚本共同定义这条路线的操作边界。

模型切换完全由用户决定：仓库不设置默认模型，也不会替用户选择 DeepSeek 或 GPT 的具体模型。`gpt` 和 `deepseek` 只是 Provider 路线别名；每次切换必须通过 `--model` 或对应的 `HERMES_*_MODEL` 显式提供模型 ID。脚本只在用户明确执行时工作，不会自动更改当前会话；切换后必须新建会话或执行 `/reset`。

```bash
python integrations/executors/hermes/switch_model.py status
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
```

也可以先在当前进程环境中设置用户自己的模型 ID：

```bash
export HERMES_DEEPSEEK_MODEL='<user-selected-deepseek-model>'
export HERMES_GPT_MODEL='<user-selected-openai-codex-model>'
```

支持能力：

- `status`：显示脱敏后的 Hermes Provider/模型配置、认证清单和关键端口状态；
- `gpt`：切换到 Hermes 官方 `openai-codex` OAuth 路线；
- `deepseek` / `dp`：切换到 DeepSeek 官方 Provider；
- 切换前检查所需代理端口或环境变量；
- 通过 `hermes config set` 官方入口写配置，不直接改认证文件；
- 支持环境变量覆盖 live 模型名，避免把易变名称复制到多处；
- 所有输出经过 token、Key、JWT、GitHub/npm/Slack 等常见秘密模式脱敏；
- `--no-verify` 只用于明确需要跳过前置检查的场景。

切换后需新建会话或执行 `/reset`，让 Provider 变更进入新的 Hermes Session。

### Workflow Doctor

结构诊断：

```bash
python integrations/executors/hermes/hermes_workflow_doctor.py
```

它会检查：

1. Hermes 版本、配置、认证 inventory 和 MCP inventory；
2. CC Switch 网络代理与 Codex Router 端口；
3. DeepSeek 与 ChatGPT 的 HTTP 传输可达性；
4. Node 版本和已配置的 Context7 MCP；
5. Codex desktop/plugin/PATH 候选二进制与版本漂移；
6. Codex 私有配置不读取，以可执行文件、监听和可选 live smoke 作为链路证据。

真实执行 smoke：

```bash
python integrations/executors/hermes/hermes_workflow_doctor.py --live
```

`--live` 会实际调用 GPT、DeepSeek 和 Codex，并要求输出独立 marker。普通端口、HTTP 状态和结构检查不等于真实模型执行；只有 live marker 通过才能证明当前执行链路可用。`--live` 可能产生网络请求或模型用量，因此不会默认运行。必须从 Git 项目根目录运行：Codex smoke 的临时 Git 仓库默认只会创建在当前项目 `.project-local/runs/`，运行后自动清除；如需指定其父目录，传入同一项目范围内的 `--codex-workdir .project-local/runs/<name>`，项目外路径会被拒绝。

### Provider / 模型健康库存

默认只生成不含秘密、不会发起请求的模型库存：

```bash
python packages/client-neutral-core/scripts/provider_health.py \
  --config config/config.yaml \
  --output .project-local/artifacts/provider-health.json
```

默认状态为 `UNVERIFIED`，只表示显式提供或从当前运行时发现的模型尚未做真实调用；model/provider-neutral overlay 自身允许库存为空。只有明确传入 `--live` 才逐一执行 marker 请求并消耗额度。报告不包含 token、OAuth 内容、cookie、API key、base URL 或凭据文件内容。

## Codex 编码执行器

Codex 会在新任务启动时读取用户目录 `$CODEX_HOME/AGENTS.md`，再由项目内更具体的
`AGENTS.md` 继续约束；Codex 原生用户 skill 目录是 `$HOME/.agents/skills`，项目 skill
目录是 `<project>/.agents/skills`，命令规则位于 `$CODEX_HOME/rules/*.rules`。不要把
`.codex/skills` 当成当前官方 skill 发现根。

完整的配置矩阵、所有权、验证证据和日常使用说明见
[`docs/current/workflow-assistance/workflow/codex-global-enhancement.md`](docs/current/workflow-assistance/workflow/codex-global-enhancement.md)。
Windows Desktop 更新后的登录、外观、项目索引、线程权限与用户配置必须分层判断；当前调查摘要和跨机器只读采样清单见
[`docs/current/workflow-assistance/workflow/codex-desktop-update-state-investigation-2026-08-13.md`](docs/current/workflow-assistance/workflow/codex-desktop-update-state-investigation-2026-08-13.md)。

本仓库现在提供可回读、可回滚的 Codex 用户层增强包：

```bash
# 只生成不含秘密的写入计划
python integrations/executors/codex/sync_codex_global_assets.py plan \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

# 用户明确批准后应用
python integrations/executors/codex/sync_codex_global_assets.py apply \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

# 精确回读或撤销本包拥有的部分
python integrations/executors/codex/sync_codex_global_assets.py verify \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"
python integrations/executors/codex/sync_codex_global_assets.py rollback \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"
```

同步器只拥有：

- `$CODEX_HOME/AGENTS.md` 中带开始/结束标记的 Workflow Assistance block；
- `.codex/config.toml` 中带标记的三个默认字段：`approval_policy=on-request`、
  `sandbox_mode=workspace-write`、`project_doc_max_bytes=65536`；
- `.codex/rules/workflow-assistance.rules`；
- `.agents/skills/workflow-assistance-*` 的十四个 Codex 原生 skill 根（具体集合由机器合同和源目录共同校验）。

若这些 config 字段已有不同的用户值，同步器保留用户值而不是覆盖。Provider、model、base URL、
认证、MCP、plugin、Desktop 状态、session、sandbox 内部状态和其它用户 skill 均不在写入集；
状态文件只保存所管理文件的 hash 与字段名，不复制混合所有权 config 或凭据。冲突、目标漂移、
格式错误和非本包拥有的同名 skill 都会 fail-closed。`rollback` 只删除仍与最后一次应用 hash
一致的本包资产，避免覆盖后续人工修改。

`install_codex_global_guidance.py` 仍保留为“目标完全不存在时”的最小原子 bootstrap：它先把完整内容写入 Windows
私有或 POSIX 匿名 staging 对象，再以不替换已有名称的原子操作发布缺失的 `AGENTS.md`；公开名称存在期间
不会继续写入内容。已有的零字节文件、hardlink、symlink/reparse point 或并发创建文件都不会
被填充或替换。安装器要求 Codex Home 已由官方 Codex 应用初始化，绝不自行创建缺失目录；
应用期间固定 Codex Home 目录身份，并在 staging 写完前后及公开发布后复核优先级更高的
`AGENTS.override.md`、Home 身份和公开目标身份。若检测到已有文件、目录重定向竞态或
override，则 fail-closed，不伪造“已生效”。先预览，再显式应用：

```powershell
python integrations/executors/codex/install_codex_global_guidance.py --codex-home "$env:USERPROFILE\.codex"
python integrations/executors/codex/install_codex_global_guidance.py --codex-home "$env:USERPROFILE\.codex" --apply
```

Windows staging HANDLE 不共享写入或删除，且在创建后立即标为 delete-pending，阻断新的打开和
hardlink；写完并完成预发布检查后才清除该状态，再通过当前 HANDLE 的
`FileRenameInfo(ReplaceIfExists=False)` 发布。转换、写入、override 或发布失败只通过该 HANDLE
的 delete disposition 精确撤销，不执行 close 后的路径删除。POSIX 必须使用 `O_TMPFILE` 匿名
inode，并通过 `linkat(AT_EMPTY_PATH)` 无覆盖发布；不支持匿名 inode 时，安装器会在写入前以
`CODEX_GUIDANCE_ATOMIC_PUBLISH_UNSUPPORTED` 非零退出，绝不降级为可被替换的 named staging。

`CODEX_GUIDANCE_ATOMIC_PUBLISH_UNSUPPORTED`、`CODEX_GUIDANCE_STAGING_CREATE_FAILED_CLEANED`、`CODEX_GUIDANCE_WRITE_FAILED_CLEANED`、
`CODEX_GUIDANCE_WRITE_INCOMPLETE`、`CODEX_GUIDANCE_OVERRIDE_BEFORE_PUBLICATION`、
`CODEX_GUIDANCE_OVERRIDE_AFTER_PUBLICATION`、`CODEX_GUIDANCE_HOME_CHANGED`、
`CODEX_GUIDANCE_PUBLIC_TARGET_CHANGED`、`CODEX_GUIDANCE_PUBLISH_FAILED`、
`CODEX_GUIDANCE_HOME_MISSING`、`CODEX_GUIDANCE_HOME_INVALID`、`CODEX_GUIDANCE_CLEANUP_INCOMPLETE`、
`CODEX_GUIDANCE_DIRECTORY_PIN_FAILED`、`CODEX_GUIDANCE_DIRECTORY_FINALIZE_INCOMPLETE` 或 `CODEX_GUIDANCE_FINALIZE_INCOMPLETE`
都不表示已生效；按输出确认公开目标和可能保留的私有 staging 后再重试。
`CODEX_GUIDANCE_HOME_MISSING` 与 `CODEX_GUIDANCE_HOME_INVALID` 在 preview 模式仅表示诊断完成并返回
`0`；使用 `--apply` 时返回 `1`，且不会创建或修改 Codex Home。
在 `--apply` 中，`CODEX_GUIDANCE_OVERRIDE_BEFORE_PUBLICATION` 和
`CODEX_GUIDANCE_DIRECTORY_PIN_FAILED` 也都返回 `1`：它们表示请求的安装没有完成，而不是成功的 no-op。

安装或同步后必须新开一个 Codex 任务，才能重建规则和 skill 发现链。全局增强只负责通用
执行、数据、验证和交付边界；项目根的 `AGENTS.md` 与 `.agents/skills` 继续负责该项目的
具体规则。WORK-LAB 的项目 skill 位于仓库根 `.agents/skills/work-lab-workflow/`，不会被
错误提升成所有项目的全局合同。

仓库不捆绑 Codex，可通过 launcher 定位本机已安装版本：

- `packages/client-neutral-core/bin/codex`：Bash/Git Bash launcher；
- `packages/client-neutral-core/bin/codex.cmd`：Windows launcher；
- Windows 优先动态解析唯一的 `OpenAI.Codex` Store package，使 CLI 与桌面 GUI 使用同一 runtime 层；不锁定具体版本，也不静默切换到 plugin app-server。

TaskPack 的高风险冻结复审默认由 Hermes 完成；需要独立第二执行体时可显式
选择 Codex 原生 review（不改变默认行为）：

```bash
python services/orchestration/run_taskpack_agent.py \
  --repo . --remote-ref origin/main --risk high --reviewer codex \
  --required-workflow work-lab-gate \
  --mission "<明确任务>"
```

该路径会先通过当前 Codex 的 `codex exec --help` 做能力 preflight，仅在确认存在所需的
read-only sandbox、ephemeral 和结构化输出参数后，才使用等价的 `codex exec` 调用；
不会把任何具体 Codex runtime 版本或固定 flag 集合写成长期兼容契约。它默认保留用户配置、
用户/项目规则及 plugin discovery，不使用 `--ignore-user-config` 或 `--ignore-rules`。
任务 prompt 与临时 JSON Schema 一起交给 Codex；不会使用危险 sandbox/approval
bypass，不创建 Codex 会话产物。TaskPack 只读取并删除项目 runtime 中的最终消息与
schema 临时文件；任何 finding 都 fail-closed 为 `NO-GO`。`--reviewer codex` 仅适用于
high-risk TaskPack；TaskPack 仍会在每次复审前后核对 `git write-tree` 与工作区状态。

只有显式 `--publish` 才允许 TaskPack 提交、推送和等待 CI。高风险发布会把
release commit 的 `HEAD^{tree}` 与 reviewer GO 时的 frozen tree 逐字节绑定；不一致即
拒绝交付。`--remote-ref <remote>/<branch>` 同时决定 fetch 的 remote 与需要相等的远端
HEAD，不再隐式假定 `origin`。exact-SHA CI 默认必须有名为 `work-lab-gate` 的成功
run；可重复传入 `--required-workflow <name>` 增加额外门禁。缺失、等待中、取消、失败或
仅有无关 workflow 的 success 都不会通过发布验证。

远端 `main` 的保护规则由 GitHub 管理：禁止删除和非快进更新，并要求当前项目 profile
声明的 `work-lab-gate` exact-SHA aggregate 证据。ruleset
状态必须通过 GitHub API 读取核验，不能用本地配置或旧 run 摘要替代。

`packages/client-neutral-core/skills/autonomous-ai-agents/codex/SKILL.md` 定义：

- `codex exec` / `codex review` 使用非交互模式；
- 交互 TUI 才使用 PTY；
- 只读复审使用 read-only sandbox；
- 写任务必须在独立 Git worktree 或 clone 中执行；
- 一个 checkout 只能有一个 writer；
- 不自动绕过 sandbox；
- Codex 不得在未授权时提交、推送、合并或创建 PR；
- 复审绑定 exact staged tree，任何修改都会使 verdict 失效。

## MCP 与 Hermes 原生工具

### 默认 MCP：Context7

Context7 用于查询公开软件库的当前文档，降低使用过期 API 的风险：

```bash
hermes mcp test context7
```

通过 `packages/client-neutral-core/bin/hermes-npx*` 优先调用 Hermes bundled Node，减少系统 Node/PATH 漂移。

> Context7 查询会外发数据。不得发送私有代码、密钥、客户资料或内部项目名称。

### 为什么其他 MCP 不默认启用

| MCP/能力 | 不默认启用原因 | 当前替代 |
|---|---|---|
| sequential-thinking | 与模型推理和 plan/debug/TDD skills 重叠 | 原生推理 + 专门 skill |
| public-apis | 使用频率低，可直接搜索 | `web_search` / GitHub 公共目录 |
| Playwright MCP | 与 Hermes browser/computer_use 重叠且扩大权限面 | Hermes 原生浏览器工具 |
| filesystem MCP | 与 Hermes file tools 重叠 | Hermes 原生文件工具 |
| memory MCP | 与 Hermes memory 重叠 | Hermes 原生记忆工具 |

新增候选 MCP（不含当前 Context7 portable baseline 的官方包名例外）必须固定 candidate 版本、核验来源/许可证、真实运行 `hermes mcp test`、说明数据外发与权限，并测量工具 schema 对 Prompt 大小的影响；Context7 runtime 由 resolver 选择版本。

新增候选先走审计器，不直接写默认配置：

```bash
python packages/client-neutral-core/scripts/mcp_candidate_audit.py --write-template .project-local/artifacts/mcp-candidate.yaml
python packages/client-neutral-core/scripts/mcp_candidate_audit.py .project-local/artifacts/mcp-candidate.yaml
```

`MCP_CANDIDATE_AUDIT_PASS` 只表示候选元数据完整，不等于 server 已配置、已运行、已安全或已默认启用。候选治理细则见 `docs/current/workflow-assistance/mcp/mcp-catalog-governance.md`。

## Agent 工作流治理

`packages/client-neutral-core/skills/software-development/agent-workflow-fortress/` 是本仓库的统一工作流治理入口，覆盖：

- 证据优先的缺口扫描；
- TDD 的 RED → GREEN → REFACTOR；
- 单写者和隔离 worktree；
- 快速并行侦察与串行集成；
- Task Ticket 的允许路径、禁止路径、输入资料、验证命令和输出契约；
- 后台任务的结构化状态、进程句柄和单调终态；
- 完成信号、有界恢复和“无真实证据不算完成”；
- 对 prompt、plan mode、hook、路径声明与 worktree 的非安全边界说明；
- 外部 sandbox/tool deny/OS 支持与负控证据要求；
- `git write-tree` exact-tree 冻结复审；
- 异步旧 verdict 的对象绑定和 superseding-tree 复核；
- commit、push 和 exact-SHA CI 闭环；
- 开源能力“吸收方法、不盲目 vendor”的治理；
- repomix/gitingest 风格 Context Pack，用项目内忽略产物承载新会话和 Codex handoff 摘要；
- MCP candidate audit，用 fail-closed 元数据检查约束新增 MCP 的版本、许可证、权限、数据外发、原生工具重叠和 smoke 证据；
- promptfoo 风格 Agent 行为评估模板，用声明式 cases 检查边界回答但不默认引入外部 runner；
- Catppuccin / shadcn-ui / assistant-ui 风格 UI/Skin 吸收，用 token 和 patterns 统一工作流可视状态但不默认安装前端 runtime；
- 本地质量门禁统一入口，用 Python runner 作为 canonical command，`Justfile` 仅作可选快捷方式；
- 上下文/token 卫生、可持续后台队列和真实任务计数。

### 项目任务数据锁定

所有会生成临时文件、缓存、测试环境、日志、下载物或 review 产物的任务都必须先使用：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . check
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest
python "$HERMES_HOME/bin/hermes-project-data.py" --project . kanban -- boards list
```

该执行器以 Git 根为边界，要求 `.project-local/` 已被 Git 忽略，并在子进程启动前把 `TMP`、`TEMP`、`TMPDIR`、XDG/pip/uv/npm/yarn/Playwright/Cargo home+target/Rust/Ruff/mypy/pre-commit cache 与 Python bytecode 指向 `<project>/.project-local/runs/`。它同时将原生 Kanban 的 `HERMES_KANBAN_HOME` 固定在 `<project>/.project-local/kanban/`；禁止直接创建全局项目 board。只有显式硬编码项目外输出路径、绕过项目环境绑定时才拒绝并提示改用项目目录；它不是 OS sandbox，不能替代路径审查。项目证据归档到同项目 `.project-local/artifacts/`；认证、会话库、全局 config/skills 和 cron scheduler 元数据仍属于 Hermes 全局运行时，禁止误迁移。同步器仅保留最近两份自身生成的 workflow backup，避免每次部署重复膨胀全局 backup 目录。

### 模型/API 中立任务契约

`packages/client-neutral-core/templates/task-tickets/model-neutral-agent-task.md` 提供不绑定特定模型或收费 API 的任务票据：

- Completion Contract；
- Run State Contract；
- Allowed/Forbidden Paths；
- 读、写、执行与网络权限；
- 外部执行机制和 Tool deny list；
- OS sandbox 支持验证；
- Shell 写入、链式命令与子 Agent 写入负控；
- 缺少执行证据时必须 `blocked`；
- 测试、产物、tree identity、回滚与日志输出契约。

它是治理契约，不是运行时 sandbox。相关 Grok Build 方法吸收已固定上游 SHA，并登记在 `docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.yaml`；本轮没有引入模型、Provider、付费 API、外部二进制或运行时资产。

## Skills 能力库

| Skill | 功能 |
|---|---|
| `codex` | 调用 Codex 进行有边界的实现或只读审查，规范 PTY、sandbox 和 worktree |
| `github-auth` | 全局 GitHub 认证前置检查与安全的 `gh` / Git 认证流程 |
| `github-code-review` | 本地 diff、PR diff、CI 和 exact-tree 代码审查 |
| `github-issues` | GitHub Issue 的读取、创建、分类、标签、分配和闭环管理 |
| `github-pr-workflow` | 分支、commit、PR、exact-SHA CI、review 和 merge 生命周期 |
| `github-repo-management` | GitHub 仓库 clone、remote、fork、Actions 和 release 管理 |
| `model-switch` | GPT OAuth / DeepSeek 安全切换、代理与 Provider 真实 marker 诊断 |
| `agent-workflow-fortress` | 多 Agent 编排、TDD、单写者、冻结复审、发布和开源吸收治理 |
| `sleep-mode` | 项目级持久自动推进：cron 调度、单 writer、状态账本、恢复与安全阻断 |
| `project-data-boundary` | 项目任务数据 containment：Git-ignore fail-closed、受控临时目录、缓存、日志和产物路径 |
| `python-testing` | unittest/pytest 模式、测试隔离、fixture 和常见陷阱 |
| `requesting-code-review` | 代码复审兼容入口，统一转入 fortress 的 exact-tree 流程 |
| `windows-development-environment` | PowerShell 编码、PATH 遮蔽、spawn/lockfile、路径和 Windows 环境问题 |

这 13 个 skill 都是本项目全局工作流增强的 repository-controlled portable source；同步脚本会把每个仓库负责的 skill 目录作为完整子树精确部署到 Hermes Home，不保留同目录里的旧 references、scripts 或 provenance 残片。其它 Hermes bundled 和用户安装 skills 保持原样，也不会把 live 私有 skill 或运行数据反向吸收到仓库。

## 安全与隐私

### 永不提交

- `.env` 和真实环境变量值；
- `auth.json`、OAuth Token、Bearer Token、API Key；
- SSH 私钥、cookies、浏览器状态；
- Hermes `state.db`、会话、日志、缓存；
- Codex 会话和认证文件；
- 模型权重、安装器、大型二进制或真实用户数据。

### Agent 规则扫描

```bash
python packages/client-neutral-core/scripts/security/scan_agent_rules.py templates skills docs scripts
```

扫描内容包括：

- Zero-width/BOM 隐藏字符；
- 常见 prompt-injection 特征；
- 管道执行 Shell 的危险文本模式；
- 疑似硬编码 secret/token/password。

运行期输出由 switcher 和 doctor 的脱敏器再次处理。`security-guidance` 提供非阻断提示，治理测试和 CI 才是仓库阻断门禁。

## 模板、文档与审计

### Agent 规则模板

`packages/client-neutral-core/templates/agent-rules/`：

- `AGENTS.md`：跨 Agent 项目规则；
- `CODEX_GLOBAL_AGENTS.md`：仅在 Codex Home 没有用户规则时安全新建的全局基线；
- `CODEX.md`：Codex 专用规则；
- `DESIGN.md`：设计约束与结构说明；
- `SECURITY.md`：项目安全边界。

### Task Ticket 模板

`packages/client-neutral-core/templates/task-tickets/`：

- `cc-switch-agent-task.md`：通用编码 Agent 任务；
- `model-neutral-agent-task.md`：模型/API 中立、证据驱动的执行契约；
- `public-workflow-audit-ticket.md`：公开工作流审计任务。

### Agent 行为评估模板

`packages/client-neutral-core/templates/evals/`：

- `agent-behavior-smoke.yaml`：promptfoo 风格、模型/provider 中立的 Agent 行为 smoke cases，用于检查 repo/live/session、Gateway delivery、持久任务、interrupted delegation、PowerShell 选择和验证诚实等全局工作流边界；模板不包含真实 provider、密钥、trace 或运行时依赖。

### UI / Skin 模板

`packages/client-neutral-core/templates/ui/` 与 `packages/client-neutral-core/templates/windows-terminal/`：

- `packages/client-neutral-core/templates/ui/skin-presets.yaml`：Catppuccin Mocha/Frappe、Nord、Dracula 的 portable 主题 token 和状态语义；
- `packages/client-neutral-core/templates/ui/agent-chat-ui-patterns.md`：assistant-ui / shadcn-ui 风格的 Agent thread、tool call timeline、status rail 和 command palette 信息架构；
- `packages/client-neutral-core/templates/ui/terminal-theme-checklist.md`：终端/Hermes skin 应用边界、证据要求和可访问性检查；
- `packages/client-neutral-core/templates/windows-terminal/catppuccin-mocha.json`：Windows Terminal scheme 示例；模板可复制，但不会自动改用户 settings。

### 文档和审计

- `docs/current/workflow-assistance/runtime-adapters/deepseek-harness.md`：DeepSeek Harness agent-runtime adapter 的安装/启动/停止/健康、权限边界、证据与回滚（WL-DSH）；
- `docs/current/workflow-assistance/runtime-adapters/deepseek-harness-config-guide.md`：DeepSeek Harness 配置指南——规则、技能、边界与模型下载（供 Hermes/Codex/CC Switch 等其他软件接入）；
- `docs/current/workflow-assistance/workflow/project-definition.md`：项目定义与职责边界；
- `docs/current/workflow-assistance/workflow/error-governance.md`：错误入口、根因、回归验证、证据等级和防复发规则；
- `docs/current/workflow-assistance/workflow/agent-evaluation.md`：Agent 行为评估边界、promptfoo 方法吸收和默认不安装策略；
- `docs/current/workflow-assistance/workflow/context-pack.md`：安全 Context Pack 生成器、输出边界和 handoff 使用方式；
- `docs/current/workflow-assistance/workflow/context-control-plane-design.md`：跨客户端上下文控制面设计方案（稳定前缀/缓存真值/防漂移压缩）；
- `docs/current/workflow-assistance/workflow/context-control-plane-client-config.md`：上下文控制面客户端配置建议（DSH/Hermes/Codex 参数）；
- `.project/governance/external-libraries-index.json`：共用/私用库链接与资产列表（内容不上传，JSON 校验 gate）；
- `packages/client-neutral-core/scripts/github_upload_accelerator.py` / `github_review_accelerator.py` / `github_common.py`：GitHub 上传与审核加速器（凭据走 git credential，不硬编码）；
- `docs/current/workflow-assistance/workflow/github-delivery-accelerator.md`：GitHub 交付加速器使用说明；
- `docs/current/workflow-assistance/workflow/local-quality-gates.md`：本地 canonical quality gate runner、Justfile 快捷入口和 CI 对齐方式；
- `docs/current/workflow-assistance/workflow/active-authority-index.md`：活跃权威/兼容/历史分类索引（WLG-110），README 只链接权威文件；
- `docs/history/archive/workflow-assistance/audit/wlg130-delivery-verdict-2026-08-13.md`：WLG-130 交付裁决（Authority Matrix、批次状态、GO/NO-GO；已归档，2026-08-13，非现行规范）；
- `docs/current/workflow-assistance/workflow/ui-skin-system.md`：UI/Skin 分层、主题 token、Agent UI 状态表达与 runtime-neutral 边界；
- `docs/current/workflow-assistance/workflow/project-data-boundary.md`：项目任务数据归属、迁移、保留与 fail-closed 执行器；
- `docs/current/workflow-assistance/workflow/token-monitor.md`：本地 Token Monitor 的真实 usage 口径、启动方式和 Codex OAuth 限制；
- `docs/current/workflow-assistance/workflow/hermes-runtime-layout.md`：Hermes 全局运行目录分层、可恢复迁移、升级验证与清理边界；
- `docs/current/workflow-assistance/workflow/gateway-cron-delivery.md`：Gateway、cron、sleep-mode、TUI 与外部消息平台的投递边界；
- `docs/current/workflow-assistance/workflow/user-environment-profile.md`：字段级 allowlist 的用户覆盖层、plan-only 导出器与机器私有状态排除边界；
- `docs/current/workflow-assistance/workflow/official-plus-user-configuration-standard-2026-08-11.md`：官方基线、用户覆盖层、项目覆盖层和任务临时态的 Stage 3 配置标准；
- `docs/current/workflow-assistance/workflow/dual-entry-install.md`：setup/sync/bootstrap 入口矩阵与职责边界对账；
- `docs/current/workflow-assistance/workflow/codex-performance-diagnosis.md`：Codex 性能分层诊断（项目/全局/客户端配置）、审计状态与解决方案；
- `docs/current/workflow-assistance/workflow/managed-software-and-assets.md`：受管软件与内容总清单（Hermes/Codex/CC Switch/GitHub/OpenHuman/Open Design 及未来客户端的管理面总账）；
- `docs/current/workflow-assistance/workflow/gpt-deepseek-ccswitch-codex-upgrade.md`：全链路工作流和路由矩阵；
- `docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-04.md`：Windows/Git/Python/GitHub CLI 实际故障记录（已归档：那一轮的记录，不是现行规范）；
- `docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-08-13-wlg.md`：WLG 治理 TaskPack 执行错误总结（CRLF provenance、force-push CI 陷阱、gh 卸载、多分支串扰等）（已归档：那一轮的记录，不是现行规范）；
- `docs/history/archive/workflow-assistance/error-fixes/memory-compaction-2026-08-13.md`：Hermes 记忆压缩与优化归档（合并策略、精简记录、记忆治理规则）（已归档：那一轮的记录，不是现行规范）；
- `docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-08-14-guard.md`：pre_tool_call 终端守卫正则防护三缺陷（路径穿越绕过、含空格路径误拦、scheme:// URL 误判）修复归档（已归档：那一轮的记录，不是现行规范）；
- `docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-08-14-r2.md`：R2 重审计修复批次错误归档（Guard 前缀两连坑、zizmor Docker action、schema 四方同步、SQL 表名、fail-closed 契约、验证脚本 bug、graphql 瞬断、cargo 检测）（已归档：那一轮的记录，不是现行规范）；
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 audit-r2-fixes-handoff-2026-08-14）：R2 修复批次交接（PR #97~#101、验证证据、剩余事项与恢复顺序）；
- `docs/current/workflow-assistance/workflow/wloss-reference-decisions.md`：WLOSS-100/300/510 开源能力处理决定（OPA/Conftest=REFERENCE、in-toto=DERIVE、Cosign/Promptfoo=REFERENCE、Superpowers=方法吸收）；
- `docs/current/workflow-assistance/mcp/workflow-mcp-stack.md`：MCP 默认策略；
- `docs/current/workflow-assistance/mcp/mcp-catalog-governance.md`：MCP 候选审计 schema、阻断规则和默认启用边界；
- `docs/current/workflow-assistance/absorption/open-source-workflow-absorption.md`：开源工作流吸收清单；
- `docs/history/archive/workflow-assistance/audit/workflow-absorption-audit-2026-07.md`：总体吸收审计；
- `docs/history/archive/workflow-assistance/audit/hermes-workflow-recovery-2026-07-22.md`：Hermes Desktop、CC Switch、Codex、GitHub 全链路故障、执行错误、恢复过程和数据保护证据；
- `docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.md`：模型/API 中立 Agent Harness 审计；
- `docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.yaml`：固定来源和本地落点的机器可读证据；
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 project-data-boundary-handoff-2026-08-02）：本次项目数据边界审计、交接、错误总结和上传前验证；
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 project-data-boundary-handoff-2026-08-02）：本次审计的机器可读 manifest；
- `docs/history/archive/workflow-assistance/audit/workflow-baseline-audit-2026-08-06.md`：官方 Hermes 基线、全局规则、技能/插件部署、同步边界与 Windows 目录锁的脱敏综合审计；
- `docs/history/archive/workflow-assistance/handoffs/workflow-assistance-2026-07-23.md`：无密阶段交接、恢复顺序、已发布基线与会话卫生边界；
- `docs/history/archive/workflow-assistance/handoffs/hermes-desktop-source-root-repair-2026-07-24.md`：Desktop source-root/canonical runtime 修复的无密 Codex 交接、验证与回滚边界。
- `docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 audit-prevention-controls-handoff-2026-08-13）：供应链、配置最小写入、Hermes 路径围栏和全局/项目所有权边界的交接；明确本地候选验证与 PR/CI/跨机器验证的证据分级。

- `docs/current/workflow-assistance-TROUBLESHOOTING.md`：常见部署、代理、认证和工具链问题。

## 测试与持续集成

### 本地门禁

```bash
python services/orchestration/run_quality_gate.py verify
```

可选快捷方式（如果本机已安装 `just`）：

```bash
just verify
```

`just` 不是默认依赖；缺少时直接使用 Python runner。`verify` 在依赖预检后运行客户端中立的结构、治理、Adapter、遥测、账本、可移植安装和运行时收敛门；`portable-install-runtime` 只作为显式的可选 Hermes Adapter 兼容性门，不进入默认验证，也不会促使核心 CI 安装或固定 Hermes 版本。PowerShell gate 优先 `pwsh`，仅在缺少时回退 `powershell.exe`，并且只用 AST parser 解析 `setup.ps1`，不执行安装动作。Shell/PowerShell 工具不可用时对应 gate 会显式 skip。

治理测试覆盖：

- portable config 默认 MCP/插件边界；
- 同步时保留 live Provider 与自定义能力；
- 退役资产的一次性安全迁移；
- 缺少 live config 时的基线初始化；
- setup 不默认开启高权限可选能力；
- doctor 结构检查与 live marker 区分；
- secret redaction；
- Context Pack 输出路径、Git-ignore fail-closed、秘密脱敏和项目内 artifact 边界；
- MCP 候选审计器的 pinned version、许可证、权限、native overlap、default-enable 阻断和输出 marker；
- 本地 quality gate runner 命令顺序、fail-fast 语义、Justfile 可选性和 CI 对齐；
- UI/Skin token JSON/YAML 解析、开源吸收来源、runtime-neutral 边界和“不自动应用用户 UI 设置”；
- skills 引用完整性；
- Codex 非交互和单写者边界；
- model routing 单一可执行事实源；
- 模型/API 中立任务模板的完整安全语义；
- promptfoo 风格 Agent 行为评估模板的 provider/model/secret/runtime 中立边界；
- 固定上游 SHA/SOURCE_REV、local artifact 范围和空 runtime assets。

### GitHub Actions

WORK-LAB 根目录的 `../../.github/workflows/work-lab-gate.yml` 在每次 push 和 pull request 上运行，是唯一活跃的 GitHub workflow 权威；模块级的治理工作流已移入 `docs/current/workflow-assistance/workflow/examples/governance.yml.example`，仅作 documented example / reusable source（WLG-080），不是活跃的第二 CI：

- Ubuntu / Windows：调用同一个 `python services/orchestration/run_quality_gate.py verify`；
- 平台工具缺失时 shell / powershell 子 gate 显式 skip，而不是伪装通过；
- CI verdict 绑定提交 SHA，不能用旧 run 证明新提交。

## 仓库结构

```text
.github/workflows/   Linux/Windows 治理 CI
apps/                Observer 只读投影、Token 监视器、桌面入口
config/              无密钥 Hermes 基线、环境变量模板、SOUL、字段级所有权
integrations/        受管客户端执行器（Hermes/Codex 同步与切换）
packages/            client-neutral-core：账本、sidecar、适配器、合同、技能与 launcher 源
projections/         对外只读投影产物
reports/             审计与证据归档
scripts/             audit（读回与证伪）、ci（治理门禁）、maintenance、security、setup-workflow.sh/.ps1
services/            编排、策略、回执与控制面
taskpacks/           当前任务包、错误台账、开放任务登记
tests/               仓库治理与模块回归测试
docs/                当前规范、历史归档与审计记录

scripts/setup-workflow.sh                       plan-first 安装入口（bash / Git Bash）
scripts/setup-workflow.ps1                      plan-first 安装入口（Windows PowerShell）
docs/current/workflow-assistance-TROUBLESHOOTING.md   故障排查
```

## 常用操作

```bash
# 查看当前 Provider、认证和代理前置条件
python integrations/executors/hermes/switch_model.py status

# 切换 Provider（仅在用户明确决定后；必须显式提供自己的模型；切换后新建会话或执行 /reset）
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"

# 结构诊断；不产生模型调用
python integrations/executors/hermes/hermes_workflow_doctor.py

# 真实执行诊断；可能产生网络/模型用量
python integrations/executors/hermes/hermes_workflow_doctor.py --live

# 检查默认 MCP
hermes mcp test context7

# 预览 / 应用 portable 同步
python integrations/executors/hermes/sync_hermes_workflow_assets.py
python integrations/executors/hermes/sync_hermes_workflow_assets.py --apply --approved

# 生成新会话 / Codex handoff 上下文包；输出到 .project-local/artifacts/context-pack.md
python packages/client-neutral-core/scripts/build_context_pack.py

# 生成 / 审计 MCP 候选；只写项目内忽略产物，不默认启用
python packages/client-neutral-core/scripts/mcp_candidate_audit.py --write-template .project-local/artifacts/mcp-candidate.yaml
python packages/client-neutral-core/scripts/mcp_candidate_audit.py .project-local/artifacts/mcp-candidate.yaml

# 仓库完整门禁
python services/orchestration/run_quality_gate.py verify
just verify  # optional; only if just is installed
```

## 使用边界

- 本仓库不会安装或升级 Hermes、Codex、CC Switch 或其他应用主体；
- 不会把 live Provider、凭据、会话和用户自定义配置反向上传；
- 默认配置不会启用与 Hermes 原生工具重复或权限面更大的 MCP；
- 普通 doctor 只证明结构与传输可达，结构检查不等于真实模型执行；
- `--live`、Provider 切换和外部 MCP 可能产生网络请求，应由用户明确执行；
- Task Ticket、plan mode、hook、路径声明和 worktree 都不是安全 sandbox；
- 模型/API 中立吸收只保留通用方法，不引入模型、收费服务或外部执行器；
- README 负责解释功能，机器可读事实仍以 `config/`、脚本、skills、manifest 和治理测试为准。
