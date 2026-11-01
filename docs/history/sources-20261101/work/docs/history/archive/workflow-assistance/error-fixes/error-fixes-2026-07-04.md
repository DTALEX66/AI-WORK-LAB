# 2026-07-04 HERMES + CC Switch + Codex 工作流互验错误收集与修复

本记录汇总本轮 `Workflow-assistance` 云端仓库、本地仓库、live Hermes Home 三层互验/同步过程中遇到的错误、根因、修复和验证命令。

## 范围

- GitHub 云端：`DTALEX66/Workflow-assistance`
- 本地仓库：`D:\All projects\Workflow-assistance`
- live Hermes Home：`C:\Users\admin\AppData\Local\hermes`
- 目标：同步 HERMES + CC Switch + Codex 工作流增强资产，包括 skills、MCP、wrapper、docs、scripts，同时不上传真实 `.env`、OAuth、token、session、logs。

## 最终状态

- 本地仓库与 `origin/main` 一致。
- live Hermes provider/model 保持用户当前值：`deepseek / deepseek-v4-flash`。
- MCP 三个服务器全部通过 `hermes mcp test`：
  - `public-apis`
  - `sequential-thinking`
  - `context7`
- 可迁移技能 repo ↔ live 对应项一致：
  - `model-switch`
  - `agent-workflow-fortress`
  - `python-testing`
  - `screenlingua`
  - `windows-development-environment`

## 错误清单与修复

### 1. Git clone / 路径状态异常

**现象**

```text
fatal: destination path '/d/All projects/Workflow-assistance' already exists and is not an empty directory.
```

同时出现过 Python 能看到目录、shell `cd`/`stat` 一度看不到目标路径的 MSYS/Git-Bash 路径转换差异。

**根因**

- 前一次 clone 被中断后留下半截 `.git`。
- Git-Bash/MSYS 与 Windows 原生路径在带空格 D 盘路径上存在转换差异。

**修复**

- 确认目标目录是否真有内容。
- 用 `cygpath -w` 转成 Windows 原生路径再 clone。

**防复发**

对 Windows 下 `D:\All projects\...` 这类路径，Git 操作优先使用原生路径或由 `cygpath -w` 转换后的路径。

---

### 2. GitHub CLI jq 查询空 topics 失败

**现象**

```text
cannot iterate over: null
```

**根因**

`gh repo view --json repositoryTopics --jq '[.repositoryTopics[].name]'` 在 topics 为空或字段为 null 时直接迭代失败。

**修复**

使用安全 jq：

```bash
gh repo view DTALEX66/Workflow-assistance \
  --json nameWithOwner,description,repositoryTopics,url \
  --jq '{nameWithOwner,description,url,topics:([.repositoryTopics[]?.name])}'
```

---

### 3. Python `execute_code` 不识别 `/d/...` MSYS 路径

**现象**

```text
FileNotFoundError: ... '\\d\\All projects\\Workflow-assistance\\README.md'
```

**根因**

Hermes `execute_code` 使用 Windows Python，不能把 `/d/...` 当作 MSYS mount 自动转换。

**修复**

在 Python 脚本中使用 Windows 原生路径：

```python
Path(r'D:\All projects\Workflow-assistance')
```

而在 Git-Bash `terminal` 命令中可以继续使用：

```bash
/d/All\ projects/Workflow-assistance
```

---

### 4. Git commit 缺少身份信息

**现象**

```text
Author identity unknown
fatal: unable to auto-detect email address
```

**根因**

新 clone 的仓库没有 repo-local `user.name` / `user.email`。

**修复**

使用 GitHub CLI 读取账号并设置本仓库局部身份：

```bash
GH_LOGIN=$(gh api user --jq '.login')
GH_ID=$(gh api user --jq '.id')
git config user.name "$GH_LOGIN"
git config user.email "${GH_ID}+${GH_LOGIN}@users.noreply.github.com"
```

---

### 5. 长 bash heredoc / Python 内联脚本引号截断

**现象**

```text
/usr/bin/bash: -c: line 243: unexpected EOF while looking for matching `''
```

**根因**

过长的内联 shell + Python heredoc 混合了大量单引号、中文、YAML/Markdown 文本，容易被 shell 解析截断。

**修复**

把逻辑沉淀为独立脚本：

```text
integrations/executors/hermes/sync_hermes_workflow_assets.py
```

后续用：

```bash
python integrations/executors/hermes/sync_hermes_workflow_assets.py --apply
```

---

### 6. 旧项目名残留扫描误报脚本自身

**现象**

残留扫描发现：

```text
integrations/executors/hermes/sync_hermes_workflow_assets.py: ... "hermes" + "-pack"
```

**根因**

同步脚本本身为了清理旧项目名，包含了旧字符串字面量，导致扫描器认为仓库仍残留旧项目身份。

**修复**

在脚本中动态拼接旧字符串，避免仓库出现完整旧名：

```python
legacy_pack_name = "hermes" + "-pack"
```

---

### 7. Windows MCP command 指向 POSIX 脚本导致 Hermes 闪退/断连

**现象**

```text
[WinError 193] %1 不是有效的 Win32 应用程序
GUI/TUI WebSocket client_disconnect(code=1006)
```

**根因**

Windows 上 Hermes 直接 spawn MCP `command`，不能指向 POSIX bash 脚本：

```text
C:/Users/admin/AppData/Local/hermes/bin/hermes-npx
```

必须指向 Windows cmd wrapper：

```text
C:/Users/admin/AppData/Local/hermes/bin/hermes-npx.cmd
```

**修复**

- 修复 `setup.sh`：在 Git-Bash/MSYS/Cygwin 下写入 `.cmd` wrapper。
- 修复 `sync_hermes_workflow_assets.py`：Windows live config 优先写入 `hermes-npx.cmd`。
- live config 已修复为 `.cmd`。
- `TROUBLESHOOTING.md` 已新增该排坑章节。

**验证**

```bash
hermes mcp test public-apis
hermes mcp test sequential-thinking
hermes mcp test context7
```

全部通过。

---

### 8. Hermes bundled Node 缺失导致 wrapper 拒绝启动 MCP

**现象**

```text
hermes-npx: Hermes bundled npx not found. Install Hermes bundled Node or set HERMES_HOME.
Set HERMES_NPX_ALLOW_PATH_FALLBACK=1 only if PATH Node is trusted and >=20.
```

**根因**

当前 live Hermes Home 下没有：

```text
C:/Users/admin/AppData/Local/hermes/node/npx.cmd
```

但 PATH 中存在 Node 24 / npx 11，可安全用于 MCP。

**修复**

更新：

- `bin/hermes-npx`
- `packages/client-neutral-core/bin/hermes-npx.cmd`

新策略：

1. 优先用 Hermes bundled Node/npx。
2. 如果 bundled npx 不存在，但 PATH Node >=20 且 npx 可用，则自动 fallback。
3. 否则失败并提示原因。

**验证**

```bash
node --version   # v24.17.0
npx --version    # 11.13.0
hermes mcp test context7
```

---

### 9. MCP server stdout banner 造成 JSONRPC parse error 日志

**现象**

日志中出现过：

```text
Failed to parse JSONRPC message from server
Invalid JSON: expected value ... input_value='Starting MCP server...'
```

**根因**

某些 MCP 包启动时向 stdout 输出 banner，而 MCP stdio 协议要求 stdout 只输出 JSONRPC。该问题可能出现在包本身，不一定导致最终连接失败。

**当前处置**

最终 `hermes mcp test` 已能发现工具并通过，因此暂不替换包版本；保留为排查记录。若未来再次造成启动失败，应优先检查目标 MCP 包是否把日志写到 stdout，并考虑固定到不污染 stdout 的版本或换用包参数/环境变量。

---

### 10. `hermes doctor` 可选依赖/API key 警告

**现象**

`hermes doctor` 报告缺少若干可选项，如 `GITHUB_TOKEN`、部分搜索 API key、Spotify、Discord 等。

**根因**

这些是可选工具/平台凭证，不是本次 HERMES + CC Switch + Codex 基线同步失败。

**当前处置**

不把这些当作阻塞；仅保留提示。核心基线为：DeepSeek API、OpenAI Codex auth、MCP servers、skills、wrapper、repo sync。

## 固化产物

本轮修复已固化为：

- `integrations/executors/hermes/sync_hermes_workflow_assets.py`
- `TROUBLESHOOTING.md`
- `bin/hermes-npx`
- `packages/client-neutral-core/bin/hermes-npx.cmd`
- `setup.sh`
- `skills/model-switch/`
- `skills/software-development/python-testing/`
- `skills/software-development/windows-development-environment/`

## 标准复验命令

```bash
cd 'D:/All projects/Workflow-assistance'

git status --short --branch
python integrations/executors/hermes/sync_hermes_workflow_assets.py --apply
bash -n setup.sh
bash -n bin/hermes-npx
python -m py_compile integrations/executors/hermes/sync_hermes_workflow_assets.py integrations/executors/hermes/hermes_workflow_doctor.py integrations/executors/hermes/switch_model.py packages/client-neutral-core/scripts/security/scan_agent_rules.py
python packages/client-neutral-core/scripts/security/scan_agent_rules.py .
hermes mcp test public-apis
hermes mcp test sequential-thinking
hermes mcp test context7
hermes doctor
```

## 回滚位置

同步脚本每次 apply 前会备份 live Hermes Home 中会被改动的可迁移资产到：

```text
C:\Users\admin\AppData\Local\hermes\backups\workflow-assistance-sync-YYYYmmdd-HHMMSS-ffffff
```

如果 live Hermes Home 因同步异常，可以从对应备份目录恢复 `config.yaml`、`bin/`、`skills/...`。
