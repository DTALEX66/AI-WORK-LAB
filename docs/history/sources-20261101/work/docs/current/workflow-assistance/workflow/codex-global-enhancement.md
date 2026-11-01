# Codex 全局工作流增强

## 目标

以 Workflow Assistance 的定位为标准，让 Codex 在任意 Git 项目中获得可迁移的执行、数据、验证和交付边界，同时保留 Codex 官方运行时与用户私有配置的所有权。

该增强层不是 Codex Runtime、模型网关、认证管理器或 Desktop 状态管理器。它只写明确声明的用户 overlay，并允许项目内 `AGENTS.md` 与 `.agents/skills` 继续缩小规则范围。

## 官方配置面与所有权

| 配置面 | 官方位置 | 本包行为 | 所有权 |
|---|---|---|---|
| 用户规则 | `$CODEX_HOME/AGENTS.md` | 合并带标记的 managed block | 字段级 overlay |
| 项目规则 | `<project>/AGENTS.md` | 只读发现，不全局复制 | 项目 |
| 用户 Skills | `$HOME/.agents/skills` | 管理五个 `workflow-assistance-*` 根 | 精确目录 |
| 项目 Skills | `<project>/.agents/skills` | 只读发现 | 项目 |
| 命令规则 | `$CODEX_HOME/rules/*.rules` | 管理 `workflow-assistance.rules` | 精确文件 |
| 用户配置 | `$CODEX_HOME/config.toml` | 只管理三个顶层默认字段 | 字段级 overlay |
| Provider / model | `$CODEX_HOME/config.toml` | 保留，不选择、不统一 | 用户 |
| MCP / plugins | `$CODEX_HOME/config.toml` | 保留，不增删 | 用户 |
| 认证、会话、Desktop、sandbox 内部状态 | Codex 私有目录 | 禁止读取、复制或写入 | Codex/用户私有 |

> 当前 Codex 官方 skill 发现根是 `.agents/skills`；`.codex/skills` 不是本增强包的目标。

## 管理字段

同步器只在字段不存在时写入：

```text
approval_policy        = on-request
sandbox_mode           = workspace-write
project_doc_max_bytes  = 65536
```

如果用户已设置不同值，计划会列为 `preserved_user_config_fields`，应用不会覆盖。非交互 `codex exec` 可按该命令自身语义显示 `approval: never`；这不表示交互式 Codex 的 `on-request` 默认值丢失。

## 安装的用户 Skills

- `workflow-assistance-safe-project-execution`
- `workflow-assistance-project-data-boundary`
- `workflow-assistance-single-writer-delivery`
- `workflow-assistance-evidence-verification`
- `workflow-assistance-observer-delivery`
- `workflow-assistance-open-design-integration`
- `workflow-assistance-systematic-debugging`
- `workflow-assistance-python-testing`
- `workflow-assistance-github-delivery`
- `workflow-assistance-windows-development`
- `workflow-assistance-openhuman-integration`
- `workflow-assistance-self-improvement`
- `workflow-assistance-update-safety`
- `workflow-assistance-verification-hardening`

这些是 Codex 原生、客户端中立的 skill，不包含 Hermes 工具调用，也不会把 WORK-LAB 的模块规则提升到普通项目。WORK-LAB 自己的项目 skill 位于仓库根 `.agents/skills/work-lab-workflow/`。

`workflow-assistance-openhuman-integration` 定义与本地 OpenHuman 桌面 agent 的协作边界：`~/.openhuman/` 私密运行时（keychain/users/logs/memory/workspace）与 `.codex`/`.hermes` 同级不可读取；OpenHuman 的扫描输出只是候选证据，junction/重复/路径类结论必须用 `fsutil reparsepoint query`、`Get-Item` LinkType/Target 与内容对比原生核验后才可行动（2026-08-10 OpenHuman 误报两个不存在 junction 的回归案例已写入）。

`workflow-assistance-self-improvement` 以中立形态吸收个人 agent 的技能自动成长模式（usage sidecar + active/stale/archived + pin 豁免 + 只归档不删除 + 转变前备份 + provenance 过滤），配套 `packages/client-neutral-core/scripts/skill_lifecycle.py`（stdlib-only，可对任意 skills 根运行）；自动生长的知识通过 PR 提升进模块 codex-assets，仓库即跨机器持久存储。

## 用户环境画像（跨机器留存）

`packages/client-neutral-core/scripts/user_profile_export.py` 以只读、无密方式导出 Hermes/Codex 用户配置与技能清单到 tracked `config/user-environment-profile.json`；具体数量以当次导出和同步器读回为准，不在文档中冻结。配置键值会脱敏，凭据一律 `[REDACTED]`，发现未脱敏值即拒绝写入。恢复流程见 `docs/current/workflow-assistance/workflow/user-environment-profile.md`：新机器 `sync apply` 部署模块 skills 后，按画像键名重建配置、重填凭据。

跨电脑识别不依赖用户画像或凭据：`services/authority/machine_identity.py` 只在项目本地维护随机 opaque `machine_id`，并以非敏感画像摘要判断是否需要复核。它只能输出 `KNOWN_MACHINE`、`NEW_MACHINE` 或 `CONFIGURATION_REVIEW_REQUIRED` 等只读状态，不能证明账户身份，也不会因换机自动 apply、重登、清理或覆盖用户配置。完整边界和显式命令见 `docs/current/workflow-assistance/workflow/machine-identity-and-config-review.md`。

## 命令策略

`workflow-assistance.rules` 提供以下边界：

- 禁止 `git reset --hard`、`git clean` 和 force-push；
- 普通 `git push`、PR 创建/合并、release 创建要求提示批准；
- GitHub 只读查询不被规则阻断；
- 规则不代替 sandbox、项目 `AGENTS.md`、代码审查或用户批准。

## Shell 可移植性加固（2026-08-10）

增强模块对 Windows 下的 Git/命令行陷阱做了系统化吸收，并纳入安全门禁：

- **Git 修订简写**：upstream、push、reflog、上一检出分支及带日期等 `@`-brace
  形式在 PowerShell 下未加引号会被解析为哈希表字面量，命令在 git 执行前就失败；
  规则要求显式 ref（`git rev-parse origin/main`）或单引号简写（`'@{upstream}'`）。
- **方言对照**：cmd.exe / PowerShell / Git Bash(MSYS) / WSL 的引号、转义、插值与
  停止解析（`--%`）差异已写入全局指导与 Windows 开发 Skill。
- **MSYS 路径转换**：`/foo` 会被自动转成 Windows 路径；使用
  `MSYS2_ARG_CONV_EXCL=*` / `MSYS_NO_PATHCONV=1` / 原生 `C:\...` 路径。
- **行尾与编码**：shell 脚本 CRLF 导致 "bad interpreter"（保持 LF +
  `.gitattributes`）；PowerShell 5.1 重定向默认 UTF-16；中文 Windows 用 UTF-8
  （`chcp 65001`）与 `core.quotepath false`。
- **文件系统**：长路径（`core.longpaths`）、大小写（`core.ignorecase`）、
  文件锁（`BLOCKED_PROCESS_LOCK`，不杀共享进程）。
- **门禁**：`scan_agent_rules.py` 新增两项可执行检查 —— 裸 `@`-brace 修订简写
  与 shell 脚本 CRLF，全量 quality gate 的 security gate 自动执行。

## 同步、验证与回滚

从 WORK-LAB Git 根运行（`10-workflow/workflow-assistance` 已在 2026-09 目录收敛中拆分，不再是
被跟踪路径；下面每条命令都是仓库根相对路径）：

```bash
python integrations/executors/codex/sync_codex_global_assets.py plan \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

python integrations/executors/codex/sync_codex_global_assets.py apply \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

python integrations/executors/codex/sync_codex_global_assets.py verify \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

python integrations/executors/codex/sync_codex_global_assets.py rollback \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"
```

Windows Git Bash 也可显式使用：

```bash
--codex-home 'C:/Users/ALEX/.codex' --agent-home 'C:/Users/ALEX/.agents'
```

安全特性：

1. `plan` 不写文件，也不输出 config 正文、连接地址或凭据；
2. 应用前预检所有同名目标，未知冲突 fail-closed；
3. config 使用 TOML 解析回读，混合所有权内容不复制到备份；
4. 状态文件只保存管理字段名和文件 hash；
5. 再次应用幂等；
6. rollback 只删除仍与状态 hash 一致的本包文件和标记 block；
7. 人工修改后的受管文件不会被静默覆盖或删除。

## 日常使用

1. 配置变更后关闭旧 Codex 任务并新开任务，使规则和 skill 列表重新发现；
2. 在任意项目 Git 根启动 Codex；
3. 项目有特殊要求时，在项目根维护 `AGENTS.md`；
4. 可复用项目流程放入 `<project>/.agents/skills/<name>/SKILL.md`；
5. 让 Codex 实际运行测试、构建和 readback，不接受仅凭代码或说明宣称完成；
6. commit、push、PR、merge、release 仍需用户明确授权。

更新后若出现重新登录、外观、项目索引、线程权限或 `config.toml` 变化，必须先按存储层分诊，不得把一次重登解释为整体配置重置。当前调查结论和另一台电脑只读采样清单见 `codex-desktop-update-state-investigation-2026-08-13.md`。

## 2026-08-09 本机真实回读

| 验证项 | 结果 |
|---|---|
| Codex CLI runtime | `codex-cli 0.147.0-alpha.6.5` |
| Codex 用户 provider/model | 原值 `cc-switch-official / gpt-5.6-luna` 被保留 |
| 当前 Hermes 聊天 runtime | 独立层：`openai-codex / gpt-5.6-sol` |
| Config TOML 严格入口解析 | PASS |
| 全局 managed config 回读 | PASS，3 个字段 |
| 用户 MCP / plugin 名称 | 保留，未增删 |
| 用户 Skills 发现 | PASS，8/8 |
| Command rule 负控 | PASS：hard reset forbidden，push prompt |
| Live rollback → readback → reapply | PASS |
| 非 WORK-LAB 独立 Git canary | PASS |
| Canary 默认 sandbox | `workspace-write` |
| Canary 规则回读 | 中文、单 writer、全局配置需精确授权、四类证据状态均被正确回读 |

## 能力边界

全局增强完成后，可以把 Codex 作为任意项目的日常编码和任务执行入口，但不能把以下事项虚构为自动完成：

- 普通项目没有 Workflow Task Ledger 时，不会凭空获得 durable Ledger；
- Telemetry Ledger 和 Sidecar 仍由接入 Workflow Assistance profile 的项目显式提供；
- Observer 始终是只读投影，不能执行、审批、重试、回滚或写 Ledger；
- 本地测试不等于 exact-SHA CI、merge、release 或公开 URL 回读；
- Codex 与 Hermes 的私有会话、memory、provider、认证和 Desktop 状态保持分离。

因此当前结论是：**Codex 全局规则、原生 Skills、sandbox 默认值、命令策略、回读和回滚均已建立；项目专属 Ledger/Telemetry 仍采用显式 profile 接入，而不是全局强制。**

## Responsibility and capability boundary

本增强模块的责任与能力不得从本段自由扩张。冻结合同见：

- 人类交接：`docs/current/workflow-assistance/workflow/codex-enhancement-boundary.md`
- 机器可读权威：`config/codex-enhancement-boundary.json`
- 回归合同：`tests/workflow-assistance/test_codex_enhancement_boundary.py`

合同固定以下结论：该模块只提供官方 Codex 配置面上的 secret-free 用户 overlay，具备
`detect/plan/apply/verify/rollback` 的受限能力；`apply` 必须由用户明确授权，`rollback`
必须通过 owned-hash fence，`invoke` 明确为 `NOT_PROVIDED`。它不拥有 Codex runtime、
provider/model、认证、MCP/plugin、会话、memory、Desktop 私有状态、项目 Task Ledger、
Telemetry Ledger、Sidecar、Git 发布或外部项目写入能力。任何新增全局能力必须先修改
机器合同、文档和测试，不能仅通过增加脚本或 Skill 实现。

> 2026-10-05 技能收敛：本机全局个性化规则使用 personal-guidance.md 的单一文件；只更新技能时运行同步器 --skills-only，保留 config/AGENTS/rules。普通全量 overlay 不应重建已由用户替换的旧 managed block。项目专属说明见 docs/current/workflow-assistance/skill-references/。历史运行记录不代表本次部署。
