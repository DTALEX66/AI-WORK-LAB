# UI / Skin 系统

本文记录 Workflow-assistance 对 Hermes Agent + CC Switch + Codex 全局工作流的视觉增强规则。目标是吸收 Catppuccin、shadcn/ui、assistant-ui 等开源项目的**主题 token、组件信息架构和 Agent UI 状态表达方法**，但不把任何 Web UI、组件库、Node 包、数据库、认证系统或遥测服务设为默认依赖。

简短边界：**不默认安装 UI runtime**；模板可复制，不代表已应用。

## 定位

UI/Skin 增强覆盖的是全局工作流体验，不是只美化本仓库：

- Hermes CLI/TUI 的 `display.skin` 与 `/skin` 使用边界；
- Windows Terminal / VS Code / Codex 终端视觉一致性；
- Hermes Desktop / dashboard / Observer 相关界面的设计 token 和组件规范；
- Agent 任务状态、tool call、verification evidence、Gateway、cron、sleep-mode 和 repo/live/session 分层的可视化表达。

## 已吸收的开源方法

| 来源 | 吸收内容 | 默认运行时 |
|---|---|---|
| `catppuccin/catppuccin` | Mocha/Frappe 风格的低干扰暗色 token、语义色和终端配色 | none |
| `catppuccin/windows-terminal` | Windows Terminal color scheme 结构 | none |
| `shadcn-ui/ui` | copy-paste 组件思想、settings panel、command palette、status card 信息架构 | none |
| `assistant-ui/assistant-ui` | Agent message thread、tool call timeline、composer/action 状态表达 | none |
| `headlessui/headlessui` | dialog/menu/combobox/tabs 的可访问交互边界 | none |

不默认吸收：Open WebUI、NextChat、Vercel AI Chatbot。它们适合作为研究对象，但会引入 Web app runtime、provider/auth/session/db 边界，不能进入 portable 默认能力。

## Surface 分层

| Surface | 可做 | 不做 |
|---|---|---|
| Hermes CLI/TUI | 记录 `display.skin`、busy indicator、status bar、中文界面和主题选择边界 | 不假设当前会话已加载新 skin；需要 `/skin`、`/reset` 或新会话证据 |
| Windows Terminal | 提供可复制 color scheme JSON | 不自动改用户 settings.json |
| VS Code / Codex 终端 | 提供主题建议和 token 对齐 | 不安装扩展、不改全局编辑器配置 |
| Hermes Desktop / dashboard | 提供 UI pattern、状态卡片和 Agent thread 信息架构 | 不 vendor React/Next.js/shadcn runtime |

## 推荐默认预设

优先提供三个可选 skin preset，不强制应用：

1. `catppuccin-mocha`：默认推荐，适合长时间 agent/coding 会话；
2. `catppuccin-frappe`：更亮一点，适合白天/投屏；
3. `nord-quiet`：低刺激冷色备用；
4. `dracula-dark`：高对比备用。

机器可读 token 在：

```text
packages/client-neutral-core/templates/ui/skin-presets.yaml
```

Windows Terminal 示例在：

```text
packages/client-neutral-core/templates/windows-terminal/catppuccin-mocha.json
```

## Agent UI 必须表达的状态

任何 Hermes/Codex/CC Switch 工作流 UI 不应只做“聊天框”。至少需要表达：

- 当前 project root、branch、HEAD、dirty status；
- repo updated / live Hermes Home synced / current session loaded 三层状态；
- provider/model、CC Switch proxy、Codex binary/source；
- Gateway process、messaging platform configured、cron delivery target；
- sleep-mode state、active job、last artifact path；
- tool call timeline：pending/running/succeeded/failed/blocked；
- verification evidence：命令、exit code、artifact、CI SHA；
- secret boundary：不展示 `.env`、`auth.json`、token、headers、raw traces；
- warning/blocker/high-risk 状态需要比普通信息更突出。

## 应用规则

1. 主题 token 可以进入 `packages/client-neutral-core/templates/`；运行时应用必须由用户或具体项目显式执行。
2. 不把 UI 框架写入 `config/config.yaml`、默认 MCP、全局 plugin 或 setup 脚本。
3. 不自动修改 Windows Terminal、VS Code、Hermes live config、用户 dashboard 或 desktop app。
4. 任何 UI 改动都要区分：主题 token、终端色彩、Hermes skin、Web dashboard、Agent chat thread。
5. 如果真的实现可视化 UI，必须做视觉验收；纯文档/token 变更只需结构、JSON/YAML、治理和安全扫描验证。

## 验证

```bash
python - <<'PY'
import json, yaml
json.load(open('packages/client-neutral-core/templates/windows-terminal/catppuccin-mocha.json', encoding='utf-8'))
yaml.safe_load(open('packages/client-neutral-core/templates/ui/skin-presets.yaml', encoding='utf-8'))
PY
python tests/workflow-assistance/test_workflow_governance.py -v
python packages/client-neutral-core/scripts/security/scan_agent_rules.py templates skills docs scripts README.md
```

如果系统要求 fresh ad-hoc evidence，用 `C:\Users\admin\AppData\Local\Temp\hermes-verify-*` 临时脚本验证 JSON/YAML 解析、关键 token、runtime-neutral 边界和治理测试方法。
