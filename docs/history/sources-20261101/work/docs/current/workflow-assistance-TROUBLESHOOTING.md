# 部署排坑手册

> 记录 DTALEX66/Workflow-assistance（Hermes Agent + CC Switch + Codex + GitHub 全局、可迁移、可审计工作流增强项目）部署和迁移过程中遇到的错误及解决方法。2026-07-28 那一轮的 GitHub workflow 错误总结已归档在 [`docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-28.md`](docs/history/archive/workflow-assistance/error-fixes/error-fixes-2026-07-28.md)，仅作历史参考，不是现行规范。

---

## 1. Git Clone HTTPS 被重置

**现象：**
```
fatal: unable to access 'https://github.com/DTALEX66/Workflow-assistance.git/': Recv failure: Connection was reset
```

**原因：** 网络环境（被墙/代理）导致 HTTPS 连接被重置。

**解决：** 根据用户已经授权的 GitHub 认证方式选择 SSH 或 HTTPS；不要把某一种协议、CLI 或 credential helper 写成唯一方案。
```bash
git clone git@github.com:DTALEX66/Workflow-assistance.git
```
如果选择 SSH，必须由用户自行确认 exact key path、检查目标文件是否已存在并交互输入 passphrase；Agent 不读取或生成空 passphrase 私钥。

---

## 2. setup.ps1 编码错误

**现象：**
```
powershell.exe -File setup.ps1
# 大量乱码 + ParserError: MissingEndParenthesisInFunctionParameterList
```

**原因：** PowerShell 脚本含中文注释，从 bash (MSYS) 调用时编码不兼容。

**历史状态：** 旧版 setup 入口曾有编码兼容问题。当前应使用仓库提供的 canonical setup 入口和同步器；不要把 bash 手工复制、明文配置或未审阅的独立安装命令当作默认修复。

---

## 3. setup.ps1 路径错误（已修复）

**现象（旧版本）：**
```
$PackDir = Join-Path $RepoRoot "Workflow-assistance"  # 旧版本误以为仓库根下还有子目录；当前仓库根就是打包内容
```

**当前状态：** 已修复。`setup.ps1` 第 27 行改为 `$PackDir = $RepoRoot`，无需手动修改。

---

## 4. .env 缺少代理配置

**现象：** 部署保留了现有 `.env`，但 CC Switch 代理变量未写入。

**当前规则：** 不在排坑文档中追加或打印 `.env`、代理凭据或任何真实环境变量。同步器只部署无密钥模板并保留 live 本机路由；代理是否可用必须通过脱敏 doctor 或用户授权的连通性检查确认。

---

## 5. OAuth 认证超时

**现象：**
```
hermes auth add openai-codex
# [Command timed out after 30s]
```

**原因：** OAuth 设备码流程需要用户在浏览器中完成授权，前台 30s 超时不够。

**解决：** 后台运行 + 加长超时 + 设置代理
```bash
export HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890
hermes auth add openai-codex &  # 或 background=true
```
然后在浏览器打开 `https://auth.openai.com/codex/device` 输入验证码。

---

## 6. OAuth 页面被 Cloudflare 拦截

**现象：** 浏览器打开 `auth.openai.com/codex/device` 显示"正在进行安全验证"（Cloudflare 质询）。

**原因：** 沙箱浏览器 / 非代理浏览器无法通过 Cloudflare 验证。

**解决：** 在用户自己的浏览器中完成，确保浏览器走 CC Switch 代理（127.0.0.1:7890）。

---

## 7. python3 命令不可用

**现象：**
```
Python was not found; run without arguments to install from the Microsoft Store
```

**原因：** Windows 上 `python3` 被 Microsoft Store 占位，实际 Python 是 `python`。

**解决：** 使用 `python` 而非 `python3`。

---

## 8. Git 提交缺少身份信息

**现象：**
```
Author identity unknown
fatal: unable to auto-detect email address
```

**解决：** 使用仓库局部、用户授权的身份设置；不默认修改全局 Git 配置。
```bash
# 临时（单次提交）
git -c user.name="DTALEX66" -c user.email="your@email.com" commit -m "..."

# 当前仓库局部
git config --local user.name "DTALEX66"
git config --local user.email "your@email.com"
```

---

## 9. 模型切换必须 /reset

**现象：** 改了 `hermes config set model.provider` 后模型没变。

**原因：** Hermes 在会话启动时锁定 Provider，中途改配置不影响当前会话。

**解决：** 改完配置后执行 `/reset` 或重启 Hermes。

---

## 10. Windows MCP wrapper 指到 bash 脚本导致 Hermes 闪退/断连

**现象：**
```text
MCP server initial connection failed: [WinError 193] %1 不是有效的 Win32 应用程序
GUI/TUI WebSocket client_disconnect(code=1006)
```

**原因：** Windows 上 Hermes 直接 spawn MCP `command` 时，不能把命令指向 POSIX bash 脚本 `bin/hermes-npx`；必须指向 `packages/client-neutral-core/bin/hermes-npx.cmd`，否则 MCP 初始化失败，严重时会造成界面断连/闪退。

**解决：**
```yaml
mcp_servers:
  context7:
    command: <HERMES_HOME>/bin/hermes-npx.cmd
```

如果 Hermes bundled Node 不存在，但 PATH 中存在兼容的 Node 与 `npx`，`hermes-npx.cmd` 会自动回退到 PATH `npx`。不要在项目文档中写死用户目录或 Node 版本。修复后运行：

```bash
hermes mcp test context7
```

---

## 快速参考

| 想做什么 | 命令 |
|----------|------|
| 切到 DeepSeek | `hermes config set model.provider deepseek` + `/reset` |
| 切到 GPT | `hermes config set model.provider openai-codex` + `/reset` |
| 检查连通性 | `curl -x http://127.0.0.1:7890 -sI https://chatgpt.com` |
| 环境健康 | `hermes doctor` |
| 查看 OAuth | `hermes auth list` |
