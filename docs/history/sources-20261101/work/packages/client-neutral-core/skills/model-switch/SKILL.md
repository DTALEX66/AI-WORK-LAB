---
name: model-switch
description: 在 Hermes 的用户自选 Provider/模型之间安全切换，并用真实 marker 诊断 Hermes/Codex/CC Switch 路由。
version: 1.3.1
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
tags: [hermes, provider, routing, deepseek, openai, codex, proxy, cc-switch]
metadata:
  hermes:
    tags: [hermes, provider, routing, deepseek, openai, codex, proxy, cc-switch]
    related_skills: [project-data-boundary, agent-workflow-fortress, codex]
---

# Hermes Provider 路由切换

## 唯一职责

这是当前 profile 中 provider、CC Switch 与 Codex 路由诊断的唯一技能。

- Hermes 官方命令/字段：以官方文档和 `hermes-agent` skill 为准。
- 模型值和切换写入：仅由 `integrations/executors/hermes/switch_model.py` 定义。
- 结构与真实执行诊断：仅由 `hermes_workflow_doctor.py` 定义。
- `agent-workflow-fortress` 只负责单写者、冻结审查、提交/推送/CI。
- `codex` skill 只负责调用 Codex CLI。

禁止读取、复制或转换 Hermes/Codex `auth.json`、`.env`、Windows Credential Store、浏览器 cookie 或 token。禁止把 ChatGPT OAuth 当 OpenAI API key。历史 Codex++/custom localhost 路由不是默认方案。

## 触发

| 请求 | 动作 |
|---|---|
| 整理/切换用户当前模型线 | Provider 路线只作为入口，具体模型必须由用户通过 `--model` 或 `HERMES_*_MODEL` 选择；脚本入口是 `python integrations/executors/hermes/switch_model.py deepseek|gpt --model <用户选择的模型>`；每次切换后用 `hermes chat -q` marker 验证，并提示 `/reset` 或新会话 |
| 检查模型/CC Switch/Codex | 结构 doctor；需要证明可执行时加 `--live` |
| 图片/截图分析 | 确认当前 provider 有视觉能力；必要时切 GPT 后新会话 |
| GPT 慢 | 先做同提示、同工具集、串行真实基准，不自动改配置 |

## 唯一操作入口

```bash
# 从 WORK-LAB 仓库根目录运行（scripts/workflow 位于仓库内）
python integrations/executors/hermes/switch_model.py status
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"

# 配置、监听、版本、MCP；不证明 provider 执行
python integrations/executors/hermes/hermes_workflow_doctor.py

# GPT、DeepSeek、Codex 各自必须返回独立 marker
python integrations/executors/hermes/hermes_workflow_doctor.py --live
```

模型/provider/toolset 在会话启动时冻结。切换后必须 `/reset` 或新会话；代理环境变量变化需完整重启 Hermes。

## 判定边界

1. HTTP 200/401/403 只能证明网络链路到达，不能证明 provider 可推理。
2. 只有 `--live` marker 成功才可报告 GPT/DeepSeek/Codex 可执行。
3. CC Switch 网络代理与 API router 是不同角色；仅在用户明确要求代理诊断时，才检查端口和协议 smoke。`openai-codex` OAuth 切换不依赖 `127.0.0.1:7890`，不能因该端口关闭而阻断。
4. Codex 优先使用桌面插件执行体；PATH 版本漂移只报 WARN，不自动删除旧 exe。
5. Context7 是默认 MCP；其他 MCP/插件按任务启用，不能因“已安装”声称当前可调用。

## 速度与视觉

- 图片能力先做真实视觉 smoke，不能仅凭模型标签断言。
- 速度诊断顺序：压缩/新会话 → `agent.reasoning_effort=low`/fast 模式 → 精简 toolset → 在用户选定的同 provider 模型之间做同提示基准 → 最后切 provider。历史延迟基准见 `references/latency-tuning.md`。
- `model_picker` 不由 portable overlay 写入；如果用户在官方 Hermes 配置中启用自定义 lanes，列表只能反映用户自己的模型选择，不构成仓库默认。
- 系统代理细节见 `references/proxy-system-config.md`。

## 输出要求

汇报三层矩阵：

| 层 | 必须给出的证据 |
|---|---|
| Hermes | provider/model、auth inventory（脱敏）、live marker |
| CC Switch | 网络代理与 router 角色、监听/连通证据 |
| Codex | 实际执行体版本、`exec` marker、版本漂移 |

绝不输出密钥、token、bearer、auth 文件内容或凭据路径中的内容。
