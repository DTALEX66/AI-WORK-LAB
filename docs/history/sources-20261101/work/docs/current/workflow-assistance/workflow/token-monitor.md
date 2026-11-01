# Hermes Token Monitor

交接与验证摘要见 [`docs/history/archive/HANDOFFS-AND-PROMPTS-20261019.zip`（成员 token-monitor-handoff-2026-08-05）](../../../history/archive/workflow-assistance/handoffs/token-monitor-handoff-2026-08-05.md)（已归档，2026-08-05）。

本项目提供两个层次的本地监视器：

- `apps/token-monitor/`：主版本，Windows Tauri 2 Dashboard，按 Provider/模型实时展示；
- `packages/client-neutral-core/scripts/token_monitor.py`：兼容性探针和无 GUI 自检工具。

主版本默认面向 Codex session JSON/JSONL，也可以扫描多个本地 JSON/JSONL 目录。多个目录使用分号分隔，适合分别接入 GPT/Codex、DeepSeek、Kimi 或本地 Router 导出的 usage 文件。

## 设计边界

- 只统计日志中明确出现的 `prompt_tokens`、`input_tokens`、`completion_tokens`、`output_tokens`、`total_tokens`；
- 不根据字符数、字节数或文本长度估算 token；
- `total_tokens` 缺失时，仅在 input 和 output 都是明确整数时计算二者之和；
- 没有 usage 的行只计入“未识别行”，不计入 token；
- 不显示原始 prompt、response、日志行、API key、OAuth、Cookie 或认证内容；
- 文件以只读方式跟踪，支持追加；检测到 truncate、轮转、删除或替换时会暂停实时模式并要求重新建立基线，避免把历史数据误报为新增 usage；
- 默认不会打开或读取日志，必须在窗口点击“开始监控”。
- 主版本点击“开始监控”后每 3 秒刷新；停止窗口即停止读取。
- 主版本默认显示“本次新增” usage；“历史累计”是显式切换，不把历史数据伪装成当前调用。
- Provider 由模型名和来源路径脱敏归类为 `GPT / Codex`、`DeepSeek`、`Kimi` 或 `Other`。
- Windows 窗口可关闭到通知区域；托盘菜单支持显示、隐藏和退出。

## 启动

### Tauri 桌面主版本

先安装 Node.js、Rust 和 Windows WebView2，然后从应用目录运行：

```powershell
cd apps/token-monitor-desktop
npm install
npm run tauri dev
```

生产前端构建：

```powershell
npm run build
```

数据源输入支持单个路径或多个以分号分隔的路径，例如：

```text
%USERPROFILE%\.codex\sessions;%LOCALAPPDATA%\my-router\usage
```

主版本只读取 `.json` / `.jsonl`，不会读取 OAuth、Cookie、API key 或 provider credential 文件。

从仓库根目录运行：

```powershell
python packages/client-neutral-core/scripts/token_monitor.py
```

指定日志：

```powershell
python packages/client-neutral-core/scripts/token_monitor.py `
  --file "$env:LOCALAPPDATA\hermes\logs\agent.log"
```

默认路径为：

```text
%LOCALAPPDATA%\hermes\logs\agent.log
```

窗口显示：

- 输入 token；
- 输出 token；
- 总 token；
- 已识别请求数；
- 未识别日志行数；
- 按模型聚合统计。

Tauri 主版本额外显示：

- GPT / Codex、DeepSeek、Kimi、Other Provider 卡片；
- 每个 Provider 的输入、输出、请求数和总 token；
- 3 秒刷新状态；
- 14 日 usage 趋势；
- Provider + 模型联合排行。

## 自检与测试

不打开 GUI 的自检：

```powershell
python packages/client-neutral-core/scripts/token_monitor.py --self-test
```

预期：

```text
TOKEN_MONITOR_SELF_TEST_PASS
```

项目测试：

```powershell
python tests/workflow-assistance/test_token_monitor.py -v
```

## 重要限制

### API 路由

如果 Kimi、DeepSeek 或 OpenAI API 返回标准 usage 字段，监视器可以记录实际 usage。

### Codex OAuth

`openai-codex` OAuth 链路不保证把完整 usage 字段写入 Hermes 日志。如果日志没有真实 usage，窗口会显示未识别行，不会制造一个看似精确的估算数字。

当前 Hermes `agent.log` 可能只包含 workflow 事件或上下文估计字段；这类日志不是模型响应 usage 数据。要显示 GPT / DeepSeek / Kimi 的真实 token，应选择包含明确 `usage` 对象或 token 字段的 session/Router JSONL 来源。

因此本软件区分：

```text
真实 usage：计入
缺少 usage：不计入，只提示未识别
字符估算：不支持
```

### 隐私

监视器不会上传日志，也不会写入 Hermes Home。日志路径由用户在本机选择；请不要把包含真实凭据或敏感 prompt 的日志复制到仓库。运行时临时文件遵循项目 `.project-local/runs/` 边界。
