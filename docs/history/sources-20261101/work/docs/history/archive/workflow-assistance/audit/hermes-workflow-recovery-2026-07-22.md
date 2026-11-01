# Hermes + CC Switch + Codex + GitHub 工作流恢复审计（2026-07-22）

## 摘要

本轮工作从 Hermes Desktop 更新后持续停在 `CONNECTING` 开始，最终扩展为对
Hermes、CC Switch、Codex、GitHub、模型 Provider、技能、插件、会话库和项目临时
数据边界的完整恢复。

最终状态：Hermes Desktop 由单一新版实例启动，后端正常监听；受保护数据完成冷备份
和一致性核验；工作流仓库成为无密钥、可复制、可升级的便携事实源；Kimi、DeepSeek、
GPT/Codex 共 14 条模型通道全部通过真实请求；Linux 和 Windows CI 均通过。

本报告是故障与修复摘要，不包含对话原文、账号、会话正文、API Key、OAuth token、
认证文件内容或其他秘密。

## 数据保护边界

以下路径始终按不可替代数据处理，未纳入 Git，也未被旧版本清理：

- `%LOCALAPPDATA%\hermes\config.yaml`、`.env`、`auth.json`；
- `%LOCALAPPDATA%\hermes\state.db`、`sessions/`；
- `%LOCALAPPDATA%\hermes\skills/`、`plugins/`、`profiles/`；
- `cron/`、`memories/`、`hooks/`、`pairing/`、`pets/`、`skins/`；
- `%APPDATA%\Hermes` 的桌面 UI 状态。

冷备份保存在：

```text
%LOCALAPPDATA%\hermes\backups\protected-state-20260722-222039
```

备份包含优化前和优化后的会话数据库、桌面 UI 状态、配置、技能、插件及重建源码补丁。
文件数、字节数和数据库 SHA-256 均完成匹配验证。它是本机恢复资产，不进入公开仓库。

## 事故链与根因

### 1. 桌面快捷方式仍指向旧包

系统中同时存在旧桌面构建和重建后的新桌面构建。桌面及开始菜单快捷方式原先仍指向
旧 `win-unpacked`，因此更新了 Python Agent 后，实际启动的 Electron 包仍是旧版本。
旧包的日志和新版运行时日志混在同一个 `desktop.log` 中，造成“已更新但仍卡住”的假象。

修复：两个快捷方式统一指向当前重建包，并验证只有一个 Hermes Desktop 根进程。

### 2. 超长会话自动恢复放大启动压力

一个历史桌面会话拥有数百条消息、数百次工具调用和超大上下文。旧桌面在启动时自动
恢复并触发压缩、Provider 解析和连接重试，使 `CONNECTING` 停留时间进一步增加。

修复：会话未删除；使用官方导出能力建立脱敏 handoff，并通过新的短会话验证桌面。
会话库仍保持统一全局数据库，不按项目粗暴拆分。

### 3. 微信开发者工具 Node 16 污染旧终端 PATH

旧终端曾优先解析微信开发者工具附带的 Node 16，而当前 Desktop/MCP 构建包含 Node 22
语法。它导致现代 ESM JSON import 语法失败，也拖慢 Context7 等 npm/npx 工作流。

修复：`hermes-npx` 和 `hermes-npx.cmd` 强制把 Hermes 托管的 Node 22 放在当前子进程
PATH 首位。工作流不再依赖系统 Node 顺序，也不要求通过删除第三方应用才能运行。
已经打开的旧终端仍可能保留旧 PATH；新 wrapper 和新会话不受影响。

### 4. Codex OAuth 与 CC Switch 路由状态不同步

CC Switch UI 显示已登录账号时，Codex CLI 仍可能报告未登录；UI 账号存在不等于 CLI
OAuth token 已被当前 Codex 运行时接受。

修复：使用官方 Codex 登录流程重新建立会话，并分别验证原生 Codex OAuth、CC Switch
本地路由端口和 `codex exec`。不复制、不解析、不回写 OAuth token。

### 5. 历史 401 与 dashboard token 404 被误认为当前启动失败

日志中存在旧会话调用过期 OpenAI API Key 的 401，也存在 Desktop 探测 headless
`hermes serve` dashboard token 时的预期 404。二者都不是当前 Desktop 无法完成启动的
充分证据。

最终判断以同一次启动中的以下证据为准：

```text
HERMES_BACKEND_READY port=...
Hermes backend is ready. Finalizing desktop startup
```

模型可用性另由真实 marker 请求验证，不再用历史日志或端口可达性代替。

### 6. 运行时、源码、备份和用户数据混放

Hermes Home 中一度同时存在旧源码、旧 `.git`、旧 `node_modules`、旧 Desktop 构建、
活动 venv、重建源码和多个恢复包。目录深度本身不是问题，角色混淆才是升级风险。

修复：

- 活动 venv 保留在旧路径，因为当前入口仍使用它；
- Python import 已验证来自重建源码；
- 当前 Desktop 使用重建包；
- 删除旧 `apps/`、`node_modules/`、旧 `.git/` 和旧项目 `repo-sync`；
- 删除前确认存在预修复源码归档和重建源码补丁。

本轮移除约 3.63GB 可再生旧运行物。删除是永久的，但可从本机预修复归档恢复；会话、
技能、插件、配置和认证不在删除范围。

## 执行过程中发现并纠正的错误

这些错误均在继续操作前被识别，没有造成用户数据丢失。

### 日志时间范围判断不充分

初期筛选 `desktop.log` 时把旧包的超时和 401 与当前启动混在一起。纠正后只使用最新
进程、最新端口和同一次启动的 readiness marker 作为事实。

### E2E 测试遗留重复 Electron 实例

Desktop fresh-install E2E 测试成功后留下一个测试实例，使进程列表短时间出现两个根
实例。纠正方式是按父子树精确终止测试实例，再只从正式快捷方式启动一次。

### 项目清理器出现一次 `uv trampoline` 启动失败

同一命令随后分别用 Hermes Python 和系统 Python 复测均成功，项目
`.project-local/runs` 清理结果为 0 字节，说明没有隐藏临时垃圾。该瞬时失败未触发
外部目录写入或删除。

### 删除旧 `.git` 时遇到后台 fetch 文件锁

第一次删除在 `tmp_pack_*` 被 Git fetch 占用时安全中止。检查确认该 fetch 只属于待
退役的 Hermes 旧仓库后，按精确进程树终止它并继续删除；其他项目的 Git 进程未受影响。

### 会话统计口径产生“数量下降”误判

`hermes sessions stats` 的可见会话子集在优化前后显示不同数字，曾被误读为会话丢失。
随后直接对冷备份和优化后数据库按 `source` 分组，只读核验：两者都包含 666 条原始
会话记录，分类完全相同。官方 FTS merge + VACUUM 没有删除会话；后续增加的是本轮
真实链路测试产生的 CLI 会话。

### PowerShell 内联 SQLite 查询两次转义错误

两条只读核验命令分别因字符串引号和不存在的 `updated_at` 字段失败。命令在任何导出、
删除或数据库修改前退出；随后读取表字段名并改用 `started_at`，恢复验证成功。

### GitHub 推送在所有权核验前被安全策略拒绝

第一次组合命令把“核验仓库”和“推送”放在同一步，因无法预先证明远端信任边界而被
拒绝，远端没有变化。纠正后先只读确认当前账号、仓库所有者、SSH remote 和公开属性，
再单独推送。

### 模型健康报告字段读取错误

首次收口脚本读取了不存在的 `status` 顶层字段，并把 `models` 映射误计为一个对象。
随后按实际 schema 的 `overall_status` 和 `models` properties 读取，确认 14 个模型、
0 个非 `LIVE_OK`，并确认报告标记为 `secret_free: true`。

## 已完成修复

- Desktop/开始菜单快捷方式统一到当前重建包；
- Desktop 单实例启动，后端 readiness marker 和本地监听验证通过；
- Hermes Agent v0.19.0、Python 3.11、OpenAI SDK 2.24.0 可用；
- Codex CLI 登录、CC Switch 路由、GitHub SSH/HTTPS、Context7 MCP 可用；
- Hermes 托管 Node v22 被 wrapper 固定使用；
- 模型切换脚本、快速命令、自定义 lane 和文档统一到一份配置事实源；
- 同步器只管理仓库拥有的配置/技能资产，保留活动 provider、模型、凭据和自定义 MCP；
- 同步备份只轮转自身创建的最近两份目录，不触碰人工升级备份；
- 项目临时数据被限制到 `<project>/.project-local/runs/`；
- Hermes 重建源码修复保存为本地恢复提交和冷备份补丁；
- Workflow-assistance 修复分支已推送到 GitHub 草稿 PR。

## 验证证据

### 会话、技能与插件

- 冷备份与活动数据逐项文件数、字节数匹配；
- 优化前后数据库均为 666 条原始会话记录；
- 一条真实 Desktop 会话完成脱敏导出，验证非空后立即清理临时目录；
- 86 个技能启用，0 个技能禁用；
- bundled 插件目录和 enable/disable 状态可由官方 CLI 枚举；
- 配置版本 33 通过 `hermes config check`。

### 模型和工具链

以下 14 条通道全部返回 `LIVE_OK`：

- Kimi：K3、K2.7 Code HighSpeed、K2.7 Code、K2.6、K2.5；
- DeepSeek：V4 Pro、V4 Flash、Chat、Reasoner；
- GPT/Codex：GPT-5.6 Sol、Terra、Luna、GPT-5.5、GPT-5.3 Codex Spark。

此外，Hermes GPT OAuth、DeepSeek、Codex exec、Context7、CC Switch 网络代理和 Codex
路由均通过真实 smoke test。

### 仓库治理

- 52 项治理、项目数据边界和终端 guard 测试通过；
- 隔离空 Hermes Home 安装验证通过，且不会创建 `.env` 或 `auth.json`；
- 完整 portable quality gate 通过；
- `git diff --check` 与 Git 完整性检查通过；
- GitHub Linux 和 Windows CI 通过。

## 当前恢复点

- 便携工作流提交：`69bb91f`；
- 便携工作流分支：`codex/hermes-workflow-hardening`；
- GitHub 草稿 PR：`DTALEX66/Workflow-assistance#1`；
- Hermes 重建源码本地恢复提交：`5d9fb10`；
- 本机冷备份：`protected-state-20260722-222039`。

公开 Git 只保存无密钥的工作流源、测试和本文档。本机冷备份、认证、会话、日志和模型
健康运行产物均不进入提交。

## 仍需遵守的升级规则

1. 升级前先停止 Desktop/Gateway writer，再建立冷备份；不能只复制活动中的 SQLite 主文件。
2. 先在隔离空 Hermes Home 执行 portable install 验证，再同步到 live Home。
3. 同步完成后依次验证 config、auth inventory、session list、skills、plugins 和 live doctor。
4. 新 Desktop、新会话、真实模型请求均通过后，才退役旧构建和可再生缓存。
5. 不通过删除 `%APPDATA%\Hermes` 或 Hermes Home 来修复启动；先备份、再定位快捷方式、
   单实例、Python 来源、Node 来源和 readiness marker。
6. CC Switch“关于”页面若仍因非标准重建路径显示 Hermes 未安装，应修正检测逻辑以识别
   `HERMES_HOME`/实际 CLI；不能为了迎合 UI 检测移动会话、技能或认证数据。
7. 公开仓库只接收无密钥便携资产；本机状态永远不反向同步到 Git。
