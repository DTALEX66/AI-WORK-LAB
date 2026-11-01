# 项目定义：客户端中立工作流控制与治理层

## 一句话定位

`Workflow-assistance` 是一个**客户端中立的工作流控制、治理、任务、交付与可观测层**：用 manifest、Adapter、Domain Pack、ActionPlan、Run Ledger、事件和 evidence envelope 连接不同执行入口。Hermes、Codex、CC Switch、GitHub、OpenHuman、Open Design 是当前一级可替换 Adapter（`packages/client-neutral-core/workflow-manifest.yaml` 的 `first_class_adapters`：前四者 support=deep，OpenHuman / Open Design support=experimental）；Hermes 不是核心运行前提。DSH（DeepSeek Harness / DSH Desktop）通过同一 Adapter 合同作为受管 agent runtime client 管理，不在 manifest 的 `adapters.entries` 内单独登记。

**Open Design client ≠ DESIGN-LAB project（两个不同身份，不得混用）：**

- Open Design 是 WORK-LAB 的**外部 client identity**（`nexu-io/open-design`）：WORK-LAB 管理其 USER_GLOBAL desired state（rules、skills、plugins、workflow policy、capability mapping）为 `MANAGE`，`apply_supported=false`；2026-08-21 起用户授权管理 Open Design **plugins**（install/update/inventory of the client plugin layer）。Open Design 在 manifest 中仍登记为 `experimental` adapter（read-only observe，writes=unavailable）。
- 设计 **capability**（models/tools、generation params、design assets、specs、design systems、quality gates、editable handoff）属于**独立的 `DTALEX66/DESIGN-LAB` 项目**，在本仓库**既不收集也不管理（`IGNORE`）**。字段级所有权在 `config/config-ownership.json`（adapter `open-design`，external project `design-lab-project`）。

核心不是 Agent、聊天软件或模型网关，不负责 Prompt 输入、模型推理、Provider 路由、凭据管理或自动批准外部写入。核心在没有 Hermes 安装的隔离环境中也必须能够解析 manifest、验证合同并列出 Adapter 状态。

本仓库是可审计的 portable source：保存合同、治理规则、适配器声明、任务边界、项目内 evidence 规范、脚本、模板和 CI。具体客户端的安装、登录、模型与私有运行时状态由对应 Adapter/官方入口独立管理，不能反向成为核心依赖。

## 产品边界

属于核心：

- 客户端中立的 manifest、Domain Pack、ActionPlan、Run/Event、Evidence 合同；
- detect/capabilities/plan/apply/invoke/observe/rollback 的 Adapter 边界；
- 用户批准、精确目标、before/after hash、权限、回滚和失败分类；
- 项目数据边界、任务恢复、Token 真实 usage、网络/Git/artifact 观测；
- 可替换入口和真实证据驱动的支持级别。

不属于核心：

- Agent 人格、聊天 UI、Prompt 编排或模型执行；
- Provider/API 路由、凭据、登录态、会话库和用户级私有配置；
- 任一客户端的安装主体或只能服务单台机器的路径；
- 没有证据的“可用”声明，或未经批准的 live apply。

## Adapter 支持级别

对齐 `packages/client-neutral-core/workflow-manifest.yaml` 的 `adapters.entries`：

| Adapter | 当前级别 | 检测/能力原则 |
|---|---|---|
| Hermes | deep | 保留现有 portable overlay、项目边界和显式 runtime 检查；核心不要求安装 |
| Codex | deep | launcher、TaskPack、review 和 worktree 通过 Adapter 合同接入 |
| CC Switch | deep（LEGACY_OBSERVE） | 仅做明确的本地路由/网络前置检查，不读取认证数据库；默认 observe-only，无活动写入 |
| GitHub | deep | 复用只读状态、exact-SHA CI、分支和交付证据 |
| OpenHuman | experimental | 本地 app 探测；写操作不可用（writes=unavailable） |
| Open Design | experimental | 远程仓库只读探测；写操作不可用；client desired state + plugins 由 WORK-LAB 管理，设计 capability 归外部 DESIGN-LAB 项目（IGNORE） |
| Cursor | manifest-only | 只登记能力，缺少真实证据时不可宣称可用 |
| Claude Code | manifest-only | 只登记能力，缺少真实证据时不可宣称可用 |
| WorkBuddy | manifest-only | 只登记能力，缺少真实证据时不可宣称可用 |


## 项目边界

本项目保存的是“全局工作流增强资产”，不是任何运行时主体的安装包，也不是只对本仓库生效的局部工具集：

- 不包含 Hermes Agent 安装主体。
- 不包含 CC Switch 安装主体。
- 不包含 Codex CLI / ChatGPT OAuth 的真实凭证。
- 不包含业务项目的 GitHub 私有数据、Actions secrets、release artifact 或运行日志。
- 不提交 `.env`、`auth.json`、API Key、Token、会话数据库、缓存或日志。

## 全局增强边界

| 范围 | 属于本项目 | 不属于本项目 |
|---|---|---|
| Hermes Agent | 可迁移配置基线、skills、MCP 默认策略、Gateway/cron/sleep-mode 说明、live 同步脚本 | Hermes Agent 核心源码、真实凭据、会话数据库、运行日志 |
| CC Switch | 代理端口/网络路径排错、Provider 前置检查、环境变量模板 | CC Switch 主程序安装包、用户真实代理凭据 |
| Codex | launcher、任务票据、单写者/worktree 规范、只读复审与 exact-tree 证据规则 | Codex CLI 主体、OpenAI OAuth token、模型服务凭据 |
| GitHub | `main` 跨设备 SSOT、提交/分支治理、exact-SHA CI、发布与恢复证据 | GitHub Actions secrets、业务项目 release artifact、业务仓库私有数据 |
| 任意业务项目 | `.project-local/` 项目数据边界、任务 artifact/ledger 规范、可复制 Agent rules | 业务项目源码本身、项目私有数据、临时一次性修复 |
| Workflow-assistance 仓库 | 全局增强资产源、文档、治理测试、同步/doctor 脚本 | 把本仓库当成唯一使用场景或运行时 sandbox |

新增内容必须回答两个问题：

1. 它是否增强 **Hermes Agent + CC Switch + Codex + GitHub 的全局工作流**，而不是只方便当前仓库一次操作？
2. 它是否可以安全迁移到其他机器/项目，而不携带密钥、会话、日志、缓存或用户私有数据？

如果答案是否定的，只能放在项目本地 `.project-local/` 或一次性任务 artifact 中，不得进入默认 portable config、全局 skill、默认 MCP 或同步脚本。

## Core 与 Adapter 职责

| 层级 | 责任 | 本仓库沉淀内容 |
|---|---|---|
| Core control plane | manifest、合同、任务、计划、审批、恢复、观测、证据和项目边界 | `packages/client-neutral-core/workflow-manifest.yaml`、`packages/client-neutral-core/scripts/`、`services/`、`docs/`、治理测试 |
| Hermes Adapter | Hermes 配置基线、skills、MCP 默认策略、Gateway/cron/sleep-mode 和显式 runtime 检查 | `config/`、`packages/client-neutral-core/skills/`、`packages/client-neutral-core/bin/hermes-npx*`、`integrations/executors/hermes/`（sync/doctor/switch-model 脚本） |
| Codex / CC Switch Adapters | launcher、路由/网络前置检查、官方 CLI 只读验证、任务与复审边界 | `integrations/executors/codex/`（adapter 声明、全局 guidance、policy renderer）、任务票据、只读审计和证据模板 |
| GitHub Adapter | 跨设备源代码事实源、分支、提交、CI 与发布证据 | `.github/` CI、exact-SHA 门禁、交接与恢复规范 |

## 当前同步状态

运行时状态必须由现场 doctor/marker 重新验证；本文件不保存机器专属路径、凭据状态或历史 smoke 结论。

- 本地仓库：`D:\All projects\WORK-LAB`（monorepo root；canonical modules =
  `packages/client-neutral-core`、`apps/observer`；supporting surfaces =
  `services/`、`integrations/`、`config/`、`apps/token-monitor/`、`scripts/`、`tests/`）
- 旧本地来源：`D:\All projects\Workflow-assistance`（legacy，保持只读 dirty 状态）
- 云端仓库：`https://github.com/DTALEX66/WORK-LAB`
- live Hermes Home：`%LOCALAPPDATA%\hermes`（或 `$HERMES_HOME`）。
- Git / live / provider 状态：用 `git status`、`integrations/executors/hermes/hermes_workflow_doctor.py` 与需要时的 `--live` marker 现场确认。
- 同步保留当前 provider/model、OAuth/API key、私有 MCP 和用户自定义命令；同步 portable 的模型 picker、快捷命令与速度策略。
- 默认 MCP：仅 `context7`；其他 MCP 必须按任务审计后启用。

## 可迁移资产清单

| 资产 | 仓库位置 | live Hermes 目标 | 说明 |
|---|---|---|---|
| Hermes 配置模板 | `config/config.yaml` | `config.yaml` | 新机器基线；同步脚本合并时保留 live provider/model，并管理已声明 overlay 字段（其余 Hermes 字段一律 OBSERVE，绝不全量覆盖） |
| 环境变量模板 | `config/.env.template` | `.env.template` | 只放占位说明，不放真实密钥 |
| MCP wrapper | `packages/client-neutral-core/bin/hermes-npx*` | `bin/hermes-npx*` | Windows live config 指向 `.cmd`；优先 bundled Node，缺失时可在用户信任且兼容的 PATH Node 环境中回退 |
| 技能 | `packages/client-neutral-core/skills/` | `$HERMES_HOME/skills/` | 仓库受控 skill 集（codex、五个 GitHub workflow skills、model-switch、agent-workflow-fortress、project-data-boundary、python-testing、sleep-mode、windows-development-environment、requesting-code-review 等）；清单以 `config/skill-provenance.yaml` 为准；sleep-mode 通过项目 `.project-local/sleep-mode/` 状态账本和 Hermes cron 管理持久队列，不复制运行时或凭据 |
| 项目数据执行器 | `packages/client-neutral-core/bin/hermes-project-data.py` | `packages/client-neutral-core/bin/hermes-project-data.py` | fail-closed 验证 Git ignore，并把任务临时文件、缓存、日志、测试环境与产物锁到 `<project>/.project-local/runs/` |
| 同步脚本 | `integrations/executors/hermes/sync_hermes_workflow_assets.py` | 手动运行 | repo ↔ live 定向同步；每次 apply 前备份可迁移资产 |
| 排错记录 | `docs/current/workflow-assistance-TROUBLESHOOTING.md`、`docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-04.md`、`docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-28.md`、`docs/current/workflow-assistance/workflow/gateway-cron-delivery.md` | 仓库文档 | 记录 Windows MCP、路径、GitHub CLI、GitHub skill ownership、凭据安全、PowerShell、Gateway/cron delivery、验证等已踩坑 |

## 本地项目定义

- 本地路径：`D:\All projects\WORK-LAB`（monorepo root；canonical modules =
  `packages/client-neutral-core`、`apps/observer`；supporting surfaces =
  `services/`、`integrations/`、`config/`、`apps/token-monitor/`、`scripts/`、`tests/`）
- 本地角色：可编辑、可验证、可提交的工作流增强资产源目录。
- 本地操作原则：先检查 → 小步修改 → 语法/安全/MCP 或 ad-hoc 验证 → commit → push。

## GitHub 云端项目定义

- 云端仓库：`https://github.com/DTALEX66/WORK-LAB`
- 云端角色：跨电脑同步的 HERMES + CC Switch + Codex 工作流增强资产库。
- 云端应保持：README 定位清晰、部署命令指向 `Workflow-assistance`、topics/description 能反映 Hermes、CC Switch、Codex、GitHub skills、MCP、provenance、workflow automation 和 exact-SHA CI。

## 验证基线

修改仓库后至少根据变更类型运行以下检查：

```bash
git status --short --branch
bash -n scripts/setup-workflow.sh
bash -n packages/client-neutral-core/bin/hermes-npx
python -m py_compile integrations/executors/hermes/sync_hermes_workflow_assets.py integrations/executors/hermes/hermes_workflow_doctor.py integrations/executors/hermes/switch_model.py packages/client-neutral-core/scripts/security/scan_agent_rules.py
python packages/client-neutral-core/scripts/security/scan_agent_rules.py .
hermes mcp test context7
```

隔离 ad-hoc 验证也必须通过 `packages/client-neutral-core/bin/hermes-project-data.py --project . run -- ...`，使临时脚本和所有运行数据保留在当前项目的 `.project-local/runs/`，不得写入用户 Temp。

## 标准闭环

1. 在本地仓库修改配置、技能、脚本或文档。
2. 运行语法检查、安全扫描和 Git 状态检查。
3. Windows 上 Hermes terminal 默认是 Git-Bash/MSYS；需要 PowerShell 时优先显式使用 PowerShell 7：`pwsh -NoProfile -Command ...`，只有旧模块/COM/Desktop edition 兼容问题才回退 `powershell.exe` 5.1。
4. 用 conventional commit 提交。
5. 推送到 GitHub。
6. 新电脑 clone 后执行 `scripts/setup-workflow.ps1` 或 `scripts/setup-workflow.sh`，再手动补齐本机私密凭证和 OAuth。
7. 对 live Hermes Home 做同步时优先使用 `integrations/executors/hermes/sync_hermes_workflow_assets.py --apply --approved`，不要全量覆盖真实 `.env`、auth、session、logs。

## 目标状态

这个项目的目标不是“只备份配置”，而是逐步成为 DTALEX66 的 Agent 工作流中枢：

- Hermes：稳定模型/provider/MCP/skills 配置。
- CC Switch：稳定代理与网络路径。
- Codex：稳定 GPT OAuth 与 coding-agent 协作路径。
- Workflow：把可复用经验沉淀为脚本、模板、技能和排错手册。
- Sync：让 repo、GitHub、live Hermes Home 之间形成可审计、可回滚、可复验的闭环。
