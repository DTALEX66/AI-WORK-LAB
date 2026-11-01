# Kimi / CC Switch → Hermes 接入与验证

## 适用场景

用户已自行在 Hermes 配好 Kimi/Moonshot provider，希望确认 Hermes 是否真实路由到用户指定的 Kimi 模型。CC Switch 仅作为本机网络/路由前置条件，不是凭据来源。

## 安全边界

- 不读取 CC Switch 数据库、Hermes `.env`、`auth.json`、OAuth token、浏览器 cookie 或 Windows Credential Store。
- 不从任一配置文件复制或转换 API key。凭据必须由用户通过其受控环境/官方配置流程处理。
- 诊断仅报告“已配置/缺失”、监听状态和 marker 结果；不得输出 credential、base URL 的私有部分或原始 provider 配置。

## 接入步骤

1. 用户先在其受控 Hermes 环境完成 Kimi 凭据配置；Agent 不读取或写入该秘密。
2. 运行 `python integrations/executors/hermes/switch_model.py status`，只确认 Kimi prerequisite 是否存在、相关监听是否正常。
3. 运行 `python integrations/executors/hermes/switch_model.py kimi --model "$HERMES_KIMI_MODEL" --live`，以独立 marker 验证用户选定的 Kimi 路由。
4. `/reset` 或新会话后生效；当前已启动的会话模型/provider 已冻结。

## 用户选定的 Provider 线与 Kimi 速度线

```bash
python integrations/executors/hermes/switch_model.py kimi --model "$HERMES_KIMI_MODEL"
python integrations/executors/hermes/switch_model.py kimi-fast --model "$HERMES_KIMI_FAST_MODEL"
python integrations/executors/hermes/switch_model.py kimi-turbo --model "$HERMES_KIMI_TURBO_MODEL"
python integrations/executors/hermes/switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"
python integrations/executors/hermes/switch_model.py gpt --model "$HERMES_GPT_MODEL"
```

`kimi-fast` 与 `kimi-turbo` 只是用户可以自行命名的 Kimi 速度入口，不绑定
任何仓库默认模型。它们不会自动切换当前模型或会话；只有用户明确提供模型
ID 后才执行切换。每次切换后用 `hermes chat -q` marker 验证真实推理，并提示
用户 `/reset` 或新会话。

## 重要陷阱：模型列表 ≠ 实际可用模型全集

Hermes 的 `/model` / picker 使用本仓库管理的 curated list，不会自动从其他应用导入模型。模型是否可用必须通过受控配置与 live marker 验证，不能从别的应用的内部数据库推断。

判断标准不是“列表里有没有”，而是 API / Hermes live marker 是否真实成功。

## 用户选定模型的真实性验证模式

不要问模型“你是谁”。应直接验证服务端响应：

1. 直接请求 Moonshot OpenAI-compatible endpoint：
   - `POST {KIMI_BASE_URL}/chat/completions`
   - body 中 `model: "<user-selected-model>"`
2. 模型专属参数必须以该模型当前官方文档为准，不把另一模型的约束复制过来。
3. 验证返回中：
   - HTTP 200
   - `response_model == "<user-selected-model>"`
   - `object == "chat.completion"`
   - usage 字段（若出现）可作为辅助证据
4. 再请求一个明确不存在的模型名，应返回 404 `resource_not_found_error`，证明服务端没有静默把任意 model string 映射成另一个模型。

可确认的结论：`Hermes → Moonshot/Kimi API → 用户请求模型 → 服务端响应模型`。
不要夸大为“外部可证明后端内部权重等级”；外部只能证明 API 暴露并服务端
确认的模型 ID 与路由。

## Brotli streaming decode 报错

症状：

```text
API call failed after 3 retries: brotli: decoder process called with data when 'can_accept_more_data()' is False
```

已知触发条件：Kimi/Moonshot OpenAI-compatible streaming + 超大上下文/长 SSE 响应 + Python 环境安装了 `brotlicffi` 时，httpx/openai 的 streaming Brotli 解码路径可能在响应中途失败。日志通常显示：

- `provider=kimi-for-coding` 或 `kimi-coding`
- `base_url=https://api.moonshot.cn/v1`
- `model=<user-selected-kimi-model>`
- `tokens=~150k+` 或更大上下文

判断：这不是 Kimi key 错，也不能据此判断用户选择的模型不存在；小请求和同会话后续请求可成功，失败点是 HTTP Brotli 解码。

修复/规避：对 Kimi-family endpoint 禁用 `br` 协商，让服务端返回 gzip/deflate：

```text
Accept-Encoding: gzip, deflate
```

Hermes core 已在 `agent/agent_init.py` 对 `api.moonshot.cn`、`api.moonshot.ai`、`api.kimi.com` 自动注入该 header，并保留既有 provider headers（例如 `api.kimi.com` 的 `User-Agent`）。修改运行时代码后必须重启 Desktop/backend；单独 `/reset` 只刷新会话，不一定重载已运行 backend 代码。

验证：

```bash
PYTHONPATH=. python -m pytest tests/agent/test_kimi_brotli_headers.py -q --tb=short -n 0
hermes chat --provider kimi-for-coding -m "$HERMES_KIMI_MODEL" -q "Reply exactly: KIMI_BROTLI_FIX_OK" -Q --toolsets safe
```

## 推荐汇报格式

- CC Switch 侧模型名列表：只列模型名，不输出 key。
- Hermes config：provider/model/base_url。
- Live marker：`hermes chat --provider kimi-coding -m "$HERMES_KIMI_MODEL" ...` 或用户显式选定的模型 marker。
- Direct API proof：request_model、response_model、HTTP status、usage keys；key 前缀最多脱敏显示，不显示完整值。
