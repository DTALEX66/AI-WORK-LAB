# 2026-07-28 全局 GitHub 工作流描述更新与错误总结

## 文档目的

本记录汇总本轮将 GitHub 工作流能力纳入 `Workflow-assistance` 全局治理层时发现的错误、根因、修复和真实证据。

项目定位保持为：

> **Hermes Agent + CC Switch + Codex + GitHub 的全局、可迁移、可审计工作流增强项目。**

本仓库是 portable source of truth；live Hermes Home 是运行时落点；GitHub `main` 是跨设备源代码、发布和 exact-SHA CI 证据面。

## 错误与修复

### 1. 五个 GitHub skill 原先没有仓库 source ownership

**问题：**

`github-auth`、`github-code-review`、`github-issues`、`github-pr-workflow` 和 `github-repo-management` 原先被当作 profile-live-only 能力，仓库无法完整复现、审计和 portable 部署。

**修复：**

- 将五个 `SKILL.md` 纳入 `skills/github/`；
- 移除 provenance 的 live-only 特殊排除；
- 纳入 `config/skill-provenance.yaml`；
- 纳入同步 backup、atomic apply、portable install 和治理测试；
- README 明确 13 个 skill 都是 repository-controlled portable source。

### 2. GitHub skill 的凭据指导存在不安全或不真实路径

**问题：**

复审发现旧指导可能暗示 plaintext credential store、process-local token helper、未认证 curl 写操作或从凭据文件提取 token。

**修复：**

- GitHub API 未通过已认证 `gh` 或用户批准客户端时 fail-closed；
- 不读取、复制、打印或持久化 token、`.env`、auth store、OAuth 数据库或私钥；
- 不把 token 放进 URL、命令参数、日志、Issue 或 PR body；
- one-shot HTTPS 凭据明确标为用户自行交互，不能假设会持久化；
- remote 和 commit identity 改为 repository-local，并要求用户单独授权；
- PR comment/review 使用 authenticated `gh`，不提供未认证 curl fallback。

### 3. PR review 的 changed-files 示例只读取第一页

**问题：**

默认 REST response 可能只包含前 30 个 changed files，较大的 PR 会被错误地当成完整审查。

**修复：**

改为使用 authenticated `gh api --paginate` 获取完整 changed-file 集合；单页公共 curl 只允许作为 metadata convenience，不能作为完整 review 证据。

### 4. SSH key 示例会无授权写入用户 profile

**问题：**

旧示例可能在没有确认外部路径、没有冲突检查、使用空 passphrase 的情况下写入 `~/.ssh`。

**修复：**

- 生成步骤改为 user-operated only；
- 先检查私钥和公钥是否已存在；
- 禁止覆盖现有 key；
- 不再传递空 passphrase 参数；
- 要求用户明确授权 exact path 并交互输入 passphrase；
- Agent 不读取或处理私钥。

### 5. Windows 文档混用 POSIX 命令

**问题：**

`GIT_CONFIG_GLOBAL=/dev/null`、`sed` 和 `cut` 在标准 PowerShell 中不可直接执行。

**修复：**

- clone 隔离配置补充 POSIX 与 Windows PowerShell 两套命令；
- GitHub owner/repo parsing 补充 PowerShell 版本；
- curl 示例明确要求 Git Bash，Windows 优先使用跨平台 `gh`。

### 6. 项目描述曾弱化 GitHub 的全局角色

**问题：**

仓库简介、README 和 PR 描述没有完全同步“GitHub skill ownership、provenance、portable sync、exact-SHA CI”这套定位。

**修复：**

统一更新：

- GitHub repository description；
- README 项目定位和发布状态；
- `docs/workflow/project-definition.md`；
- `TROUBLESHOOTING.md`；
- 已合并 PR #4 描述。

### 7. CI Node.js 20 弃用提示被误解为项目必须写死 Node 版本

**事实：**

GitHub Actions 曾报告 checkout/setup-python action 的 Node.js 20 runtime 弃用提示，但 Linux/Windows quality gate 均成功。

**处理原则：**

- 不在项目 workflow 中硬编码 `node-version: 24`；
- 不为了消除提示随意替换或取消 action SHA；
- 将其记录为 GitHub Actions 上游的非阻断维护提示；
- 后续若处理，应采用审阅后的自动依赖更新策略，而不是手工写死版本。

## 最终证据

- 本地全量测试：`Ran 111 tests; OK (skipped=1)`；
- 本地 quality gate：`QUALITY_GATE_PASS`；
- source/live provenance：`SKILL_PROVENANCE_PASS skills=13 live_checked=True`；
- Codex exact-tree review：GO；
- PR #4：已合并；
- feature commit：`8c96189e793c539c276cd8ed8c7927378fd312d0`；
- merge commit：`cbaa58ba93de6f776afd4bb47d02314f6aa7055a`；
- PR head Linux/Windows checks：通过；
- merge-SHA workflow `30358439937`：通过；
- merge-SHA Linux job：`90272026936`；
- merge-SHA Windows job：`90272026975`；
- merge commit tree 与 review tree：一致；
- 当前 `main == origin/main`，工作树干净；
- 未读取、输出或提交任何凭据、token、私钥或 auth store。

## 验证边界

这些证据证明本仓库、portable install、项目 bootstrap、live sync、Linux/Windows CI 和当前发布闭环通过；不等于对未来所有未知业务项目作出无条件保证。新项目仍应先执行 bootstrap、项目 runtime check、定向测试和 quality gate。

## 8. 2026-07-29 Codex Desktop 登录、sandbox 与外观审计

### 现象

用户报告 Windows Codex Desktop 在开机或重新打开后：

- 反复要求登录；
- sandbox/Ask for approval 需要重新开启；
- 外观 → 主题 → Codex 自定义主题不能稳定保存。

本节记录已核验的 Codex/ChatGPT 官方规则、本项目静态配置、Desktop 日志时间线，以及正常退出和多轮冷启动后的最终边界。

### 官方规则

官方 Codex/ChatGPT 文档确认：

- 用户默认配置为 `~/.codex/config.toml`，项目覆盖文件为 `<project>/.codex/config.toml`；
- `approval_policy` 与 `sandbox_mode` 是全局权限默认键；
- `[windows].sandbox = "elevated"` 选择 Windows 原生 sandbox 实现，不等于 Desktop composer 下的 Ask for approval 开关；
- Windows Desktop 与原生 Codex 共享 Codex Home；
- 官方公开的 `tui.theme` 仅用于 CLI 语法高亮，没有公开 Desktop 自定义主题的 `config.toml` 键。

官方来源：

- https://learn.chatgpt.com/docs/config-file/config-basic
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://learn.chatgpt.com/docs/windows/windows-sandbox
- https://learn.chatgpt.com/docs/windows/windows-app

### 项目配置核对

没有发现 `Workflow-assistance` 覆盖 Codex Desktop 的证据：

- 仓库没有 `.codex/config.toml`；
- 项目 wrapper 只定位 Codex 可执行文件，不设置 `CODEX_HOME`、`approval_policy`、`sandbox_mode` 或主题；
- TaskPack reviewer 先通过 `codex exec --help` 做能力发现，再使用 `--sandbox read-only --ephemeral` 和结构化输出参数；它保留用户配置、规则与 plugin discovery，不使用 `--ignore-user-config` 或 `--ignore-rules`；
- 全局 guidance 安装器只管理规则文件，不修改登录、sandbox 或 Desktop 外观；
- 未发现项目级 `CODEX_HOME`、Codex `requirements.toml` 或启动清理任务。

因此，项目工作流不是本次 Desktop 设置重置的直接根因。

### 本机日志时间线与根因

已确认的重复登录与权限配置变化分别落在 Codex Desktop 的认证 bootstrap 和共享配置状态层；自定义主题的持久化机制仍未确认。Hermes 更新与这些现象同时发生，但没有直接写入关系：

1. **登录 bootstrap 未附加现有 token。** Desktop 日志先记录 `auth_token_missing`、`hadToken=false`、`no_token_attached` 和 401，随后才进入 `account/login/start`。认证文件当时仍存在，因此不是项目删除认证，也不能仅归因于代理启动较晚。
2. **共享配置原子替换与 bundled-plugin reconcile 同窗口发生。** marketplace 重建、`config.toml` 原子替换和 reconcile 完成时间紧邻；替换后早期人工补入的 `approval_policy` 和 `sandbox_mode` 消失。现有日志不能独立识别执行替换的具体进程，因此只记录时间相关性。这两个键不再被描述为最终修复，也没有通过只读锁阻断官方 plugin 更新。
3. **Hermes 自动更新是独立事件。** Hermes installer 同时检测到 managed checkout 的本地改动并执行 stash/reset，但代码和日志中没有发现它写入 Codex 登录、Desktop profile 或共享配置的证据。项目 wrapper、TaskPack 和 guidance installer 也没有对应写路径。

### 实际修复

- Hermes managed checkout 恢复为干净的官方 `origin/main`；冲突本地 UI 改动导出为项目忽略区中的离线恢复补丁，没有重新应用到 managed install。
- 删除会抢占 PATH 的旧用户级 `codex.exe`，并删除两个与 Hermes managed wrapper 逐字节相同的重复 wrapper；保留 Codex 官方 plugin app-server executable。
- 通过 Codex Desktop 官方“完成 Windows 设置”流程创建 Windows sandbox，没有手工构造 sandbox 状态；配置最终由官方流程保留：

  ```toml
  [windows]
  sandbox = "elevated"
  ```

- Desktop 权限 UI 最终显示官方“替我审批”，没有选择“完全访问权限”。
- 保留认证、sessions、archived sessions、SQLite/WAL/SHM、skills、rules、bundled marketplace、Chromium profile、LevelDB 和用户配置；只迁移或删除经哈希、引用和解析路径证明为重复或可恢复的对象。

### 冷启动与完整性证据

- 多次 `Ctrl+Q` 正常退出后，`ChatGPT.exe`/`codex.exe` 进程归零；多轮冷启动均无需重新登录，`codex login status` 持续返回 `Logged in using ChatGPT`。
- 新启动日志中 `auth_token_missing=0`、登录 401 为 0、sandbox failure 为 0、LevelDB corruption/recovery 为 0；账号 bootstrap 成功。
- Codex sessions 为 167 个、archived sessions 为 9 个、skills 为 54 个；相对修复前基线没有修改或减少。
- 四个 Codex SQLite 数据库的 `PRAGMA quick_check` 均为 `ok`。
- 三个 bundled plugins 最终均为 `installed, enabled`；marketplace resolve/write failure 为 0。
- `codex --strict-config doctor --json` 最终 `overallStatus=ok`，无 fail/warn；Windows sandbox smoke 返回 `FINAL_CODEX_SANDBOX_OK`。
- 当时审计中 Store 包与 AppX 状态正常；CLI 通过 `codex --version` 发现，并由 Bash/CMD/PowerShell 解析到 Hermes managed wrapper。具体 runtime/package 版本只作该次审计的历史证据，不作为 workflow compatibility requirement；后续更新必须重新执行版本、帮助和能力发现。
- 仓库未提交任何认证、profile、日志、session、数据库或恢复材料；任务证据位于 Git 忽略的 `.project-local/artifacts/`。

### 已知上游边界

- 当前 Desktop 每次冷启动的第一轮 reconcile 可能短暂卸载 `browser`，第二轮会自动恢复；最终配置和 plugin list 稳定。内部触发条件尚未独立确认，因此只把它记录为可重复观察到的启动中间态，不通过修改官方包或锁死配置掩盖。
- Codex Doctor 的 provider HTTP 探针使用约 3 秒超时，在本机代理链上偶发刚好超时；代理端口、ChatGPT/OpenAI HTTP、Desktop 账号与 WebSocket 均可达，安静窗口的最终 strict-config Doctor 全绿。
- 即使通过官方 `Ctrl+Q` 且进程完全退出，Chromium Preferences 仍可能保留 `profile.exit_type="Crashed"`；实际冷启动没有 LevelDB corruption/recovery。不能直接编辑 Preferences/LevelDB 伪造 `Normal`。
- Desktop 自定义主题没有已确认的官方 `config.toml` 持久化键；本轮没有编辑 LevelDB，也没有把 CLI `tui.theme` 冒充 Desktop 主题修复。因此登录、sandbox 和配置完整性已经验证，Desktop 自定义主题仍属于官方产品状态边界。

以上结论区分“已修复且实测通过”“启动中间态会自愈”和“当前官方包仍未提供可验证持久化契约”的三类状态，不把一次 Doctor、单次 HTTP 响应或人工配置写入当成完整修复。
