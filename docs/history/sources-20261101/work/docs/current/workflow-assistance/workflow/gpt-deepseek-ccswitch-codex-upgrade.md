# Hermes + DeepSeek / ChatGPT + CC Switch + Codex 工作流

> **状态：current（2026-07）**。运行时可用性必须由当前机器上的
> `hermes_workflow_doctor.py --live` 或独立 marker 证明；本文件不保存历史
> token、固定用户名、端口“已可用”的结论。

## 职责边界

```text
Hermes      编排、skills、工具、会话与审计
DeepSeek    V4 深度推理；Codex 负责代码写入
DeepSeek    官方直连的备用/低延迟路线
ChatGPT     openai-codex OAuth 路线
CC Switch   网络代理和 Codex/ChatGPT 生态连通，不持有 Hermes OAuth 真相
Codex       独立编码/复审执行面
```

## Provider / 模型选择

仓库不设置默认模型，也不替用户决定 DeepSeek 或 ChatGPT/Codex 的具体
model ID。三条 Provider 路线只是可选入口；用户必须通过官方 Hermes 配置、
`switch_model.py --model` 或当前进程的 `HERMES_*_MODEL` 环境变量显式选择。

```bash
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"
```

这些命令只在用户明确决定切换时执行；不会自动更改当前会话，切换后必须
新建会话或执行 `/reset`。未提供模型 ID 时脚本应 fail-closed，而不是猜测
默认模型。

## 验证层级

1. **结构**：`python integrations/executors/hermes/hermes_workflow_doctor.py`
2. **真实推理**：`python integrations/executors/hermes/hermes_workflow_doctor.py --live`
3. **切换后单线 marker**：
   ```bash
   python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL" --live
   python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL" --live
   python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL" --live
   ```

配置写入、端口监听和 HTTP 200/401 只证明部分链路，不能替代 marker。

## GPT OAuth 故障

`token_revoked` / HTTP 401 表示 Hermes 的 OAuth 凭据失效。CC Switch 显示
“已连接”只证明网络路线可用，不证明 Hermes 有可推理的 token。

```bash
hermes auth add openai-codex
```

在用户浏览器完成官方 device-code 登录后，`/reset` 或新建会话，并运行：

```bash
hermes chat --provider openai-codex -m "$HERMES_GPT_MODEL" \
  -q "Reply exactly: GPT-OAUTH-LIVE-OK" -Q --toolsets safe
```

不得读取、复制、导入或打印 `auth.json`、refresh token、browser cookie 或
Credential Manager 内容。

## 默认 MCP

默认仅启用 Context7：

```bash
hermes mcp test context7
```

`public-apis` 和 `sequential-thinking` 是历史方案，已经退役；如某项目确有
缺口，先用 `mcp_candidate_audit.py` 审计，再按需启用，不能回写为默认项。

## 标准项目循环

1. `git status --short --branch`。
2. 通过 `hermes-project-data.py --project . check/run` 锁定任务产物。
3. 用 doctor 检查结构；需要证明执行时再用 `--live`。
4. 编码写入在独立 worktree/单 writer 中完成；复审绑定 frozen tree。
5. 运行 `python services/orchestration/run_quality_gate.py verify`、相关测试和 `git diff --check`。
6. 提交、推送，并以 exact SHA CI 作为最终门禁。
