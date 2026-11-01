# Portable Open Design Setup｜换电脑复用指南

这个文档用于在新电脑上复用 `DESIGN-LAB`，让 Open Design 软件继续使用本仓库作为增强资料库，并通过本机 Codex CLI 调用 GPT 订阅能力。

## 目标

```text
Open Design 软件
  → 打开/关联 DESIGN-LAB 仓库
  → 使用本机 Codex CLI
  → 读取本机 CODEX_HOME OAuth 登录态
  → 调用 GPT 订阅能力
```

本仓库不会提交 API Key、OAuth token 或任何私密凭据。

## 新电脑准备

### 1. 安装 Open Design

推荐路径仍使用：

```text
D:\Programs\Open Design\Open Design.exe
```

如果换路径，后续脚本传入：

```bash
--open-design-exe "你的 Open Design.exe 路径"
```

### 2. 安装并登录 Codex CLI

确认本机能运行：

```bash
codex --version
```

并完成 ChatGPT/Codex 订阅登录，使本机存在：

```text
%USERPROFILE%\.codex\auth.json
```

> 注意：ChatGPT/Codex 订阅不是 OpenAI API Key。本项目默认走 Codex CLI OAuth/订阅路线，不需要 `OPENAI_API_KEY`。

### 3. 克隆本仓库

```bash
git clone git@github.com:DTALEX66/DESIGN-LAB.git "D:\All projects\DESIGN-LAB"
```

## 一键配置 Open Design

在仓库根目录运行：

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB"
```

脚本会：

1. 找到 Open Design 的 `app-config.json`。
2. 备份原配置。
3. 设置 `agentId = codex`。
4. 设置 Codex 模型，默认 `gpt-5.5`。
5. 写入本机 `CODEX_BIN` 和 `CODEX_HOME`。
6. 把 Open Design 默认项目位置设为本仓库。
7. 把 `D:\All projects` 注册为 Open Design 可选项目位置，并写入 Codex `config.toml` 的 writable/trusted root，避免 Open Design 调 Codex 时被目录权限拦截。
8. 创建代理启动器：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

## 配置后诊断

配置完成后运行只读 doctor：

```bash
python design-lab/scripts/doctor_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB"
```

doctor 会检查 Open Design 配置、Codex CLI、Codex 登录态、默认项目位置、启动器、Git 状态和本地端口探测；它不会打印 OAuth token 或 API key。

## 常用参数

### 指定 Open Design 路径

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --open-design-exe "D:\Programs\Open Design\Open Design.exe"
```

### 指定 Codex CLI 路径

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --codex-bin "C:\Users\admin\AppData\Local\OpenAI\Codex\bin\xxxx\codex.exe"
```

### 不写入代理启动器中的代理变量

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --no-proxy
```

### 只验证不写入

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --dry-run
```

### 调整 Codex 权限覆盖根

默认权限覆盖根是：

```text
D:\All projects
```

如果 Open Design 调 Codex 时提示目录权限不足，重新运行：

```bash
python design-lab/scripts/configure_open_design_windows.py \
  --project-root "D:\All projects\DESIGN-LAB" \
  --permission-root "D:\All projects"
```

这会修改本机 `%USERPROFILE%\.codex\config.toml`，同时写入总权限根和自动发现到的 `.od-skills` 精确子目录：

```toml
[sandbox_workspace_write]
writable_roots = ['D:\All projects', 'D:\All projects\...\.od-skills']

[projects.'d:\all projects']
trust_level = "trusted"

[projects.'d:\all projects\...\.od-skills']
trust_level = "trusted"
```

不要把 `C:\`、`D:\` 整盘、Windows 系统目录或 `E:\` 加进 writable roots；只给明确需要的项目根目录。

### PowerShell 读取 `.od-skills` 的安全写法

不要在 Codex/Open Design 调用里裸写带空格路径：

```powershell
# 容易被拆成 D:\All，表现为权限/策略失败
Get-ChildItem D:\All projects\xxx\.od-skills
```

推荐通过环境变量传路径，再用 `-LiteralPath`：

```powershell
$env:OD_SKILLS_PATH = 'D:\All projects\xxx\.od-skills'
Get-ChildItem -LiteralPath $env:OD_SKILLS_PATH -Force
```

如果 PowerShell 仍不稳定，Node 只读路径可作为备用探针：

```bash
node -e "const fs=require('fs'); console.log(fs.readdirSync(process.env.OD_SKILLS_PATH))"
```

## 配置成功输出

成功时会看到类似：

```text
OPEN_DESIGN_ASSISTANCE_CONFIG_OK
agentId=codex
model=gpt-5.5
codex_version=codex-cli ...
launcher=D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

## 启动方式

优先使用脚本创建的启动器：

```text
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat
```

如果电脑需要代理，启动器会设置：

```text
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=socks5://127.0.0.1:7890
```

## 验证 Open Design 连接

打开 Open Design 后，可以在软件里测试 Codex/GPT 连接。

如果要从本地 API 验证：

1. 查看 daemon 日志中的端口：

```text
%APPDATA%\Open Design\namespaces\release-stable-win\logs\daemon\latest.log
```

2. 调用：

```bash
curl http://127.0.0.1:<port>/api/app-config
```

确认：

```text
agentId = codex
projectLocations 包含 D:\All projects\DESIGN-LAB
projectLocations 包含 D:\All projects
CODEX_HOME 指向本机 %USERPROFILE%\.codex
```

同时运行 doctor 确认：

```text
PASS Codex permission root writable: D:\All projects
PASS Codex permission root trusted: D:\All projects
```

技能/连接器状态不要混淆“当前会话可用”“本地 `.od-skills` 可读”“Codex 自动注册/自动触发”。详见：

```text
design-lab/usage-notes/OPEN_DESIGN_SKILL_STATUS.md
```

## 不要提交的内容

永远不要提交：

```text
%USERPROFILE%\.codex\auth.json
OpenAI API Key
OAuth token
.env
release.config.json
任何真实 AppID / adUnitId / 私密配置
```

## 故障排查

### Open Design 要求 API Key

说明你走到了 BYOK/provider 路线。当前推荐路线是：

```text
Open Design → Codex CLI → ChatGPT/Codex OAuth 订阅
```

重新运行配置脚本，并确认 `agentId=codex`。

### 找不到 Codex CLI

先在新电脑安装并登录 Codex，再运行：

```bash
codex --version
```

如果仍找不到，显式传入：

```bash
--codex-bin "C:\path\to\codex.exe"
```

### 没有 `.codex/auth.json`

先完成 Codex 登录。没有订阅登录态时，脚本默认会拒绝写入，以免配置出一个看起来可用但实际不能调用 GPT 的 Open Design。
