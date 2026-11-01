# Codex 性能诊断与配置审计（2026-08-10）

## 结论

最近几轮对话中的原方案需要修订。经官方配置文档与真实 `codex exec --ephemeral --json` 时间线复核：

- **没有证据证明 WORK-LAB 全局增强配置或 Cognitive-Loop-OS 项目配置是主要瓶颈。**
- **不能把 `windows.sandbox = "elevated"`、`supports_websockets = false`、`startup_timeout_sec = 120` 直接判为性能问题。**
- 当前可重复测得的主要成本是：每次新进程约 3.8 秒启动/装载、每个模型决策回合约数秒，以及任务中反复发生的模型→工具→模型循环。
- Cognitive-Loop-OS 项目规则只增加约 1,272 个输入 token；其验证策略本身明确要求定向测试和阶段性全量门禁，设计上不是“每改一行跑全量”。

## 配置层次（统一术语）

### L1：全局配置——WORK-LAB 增强模块

由 Workflow 模块 `packages/client-neutral-core`（2026-09 收敛前为 `10-workflow/workflow-assistance`）
管理的声明式 overlay：

- `~/.codex/AGENTS.md` 中的 marker-delimited 受管块；
- `~/.codex/rules/workflow-assistance.rules`；
- 十个明确命名的 `~/.agents/skills/workflow-assistance-*`；
- 仅当字段不存在时写入 `approval_policy`、`sandbox_mode`、`project_doc_max_bytes`。

它不拥有 provider、model、base URL、认证、MCP、插件、Desktop 状态和 sandbox internals。

### L2：项目配置——Cognitive-Loop-OS

- 根 `AGENTS.md`：6,468 bytes / 117 行；
- `<Cognitive-Loop-OS>/docs/VERIFICATION_POLICY.md`：5,698 bytes / 81 行；
- 当前没有项目 `.codex/config.toml`；
- 项目已在 Codex `[projects]` 中标为 `trusted`。

项目验证策略要求：开发中跑定向 RED→GREEN；低风险 checkpoint 不重复全量；阶段 Release Train 才完整验证一次；仅高风险路径独立全量。

### L3：Codex 用户/运行时配置

当前关键值：

```text
Codex CLI               0.147.0-alpha.6.5
model                    gpt-5.6-sol
model_reasoning_effort   medium
approval_policy          on-request
sandbox_mode             workspace-write
windows.sandbox          elevated
provider transport       Responses API via 127.0.0.1:15721
supports_websockets      false
node_repl timeout        120s（失败上限，不是固定启动耗时）
OS kernel build          10.0.26100
```

## 官方语义纠正

1. `windows.sandbox = "elevated"` 是官方推荐的更强 Windows native sandbox。它使用专用低权限 sandbox 用户、文件权限边界、防火墙规则和本地策略；并不表示每条命令都以管理员身份运行。无匹配基准时不得为提速降为 `unelevated`。
2. `supports_websockets = false` 只表示 provider 不使用 Responses API WebSocket transport；不等于“不流式”，也不能据此推导长回复必然更慢。
3. `mcp_servers.<id>.startup_timeout_sec = 120` 是覆盖默认 10 秒的失败超时上限，不代表每次启动等待 120 秒。
4. `projects.<path>.trust_level = trusted` 控制项目 `.codex/config.toml`、hooks 和 rules 是否加载。Cognitive-Loop-OS 已 trusted；给 WORK-LAB 加 trust 不会加速在 Cognitive-Loop-OS 中运行的任务。
5. `approval_policy = on-request` 只在需要批准的动作上暂停；不能描述成“每次写或联网都停”。改为 `never` 会改变安全边界，不应作为默认性能优化。

官方参考：

- <https://learn.chatgpt.com/docs/config-file/config-reference>
- <https://learn.chatgpt.com/docs/windows/windows-sandbox>
- <https://learn.chatgpt.com/docs/agent-configuration/speed>

## 真实测量

全部样本都在 `D:/All projects/Cognitive-Loop-OS`，使用 `codex exec --ephemeral --json`，不持久化会话。

### 无工具最小响应

| 样本 | thread.started | turn.completed | 输入 token | cached token |
|---|---:|---:|---:|---:|
| 当前配置，warm low | — | 12.619s | 19,870 | 9,984 |
| 当前配置，warm medium | — | 14.192s | 19,870 | 9,984 |
| 当前配置，时间线样本 | 3.797s | 9.991s | — | — |
| 临时禁用 node_repl | 3.826s | 9.271s | — | — |

单次样本不足以证明 low 固定快于 medium；两者在这些最小请求中 `reasoning_output_tokens = 0`。禁用 node_repl 后 thread 启动没有可见改善，因此不能把 120 秒超时当作当前瓶颈。

### 项目规则的边际上下文

同一全局 Home、同一 provider/model：

```text
Cognitive-Loop-OS：19,870 input tokens
空 Git canary：     18,598 input tokens
项目层边际：          1,272 tokens（约 6.8%）
```

由于 auth 不可复制到临时 Home，不能在不越过认证边界的情况下构造“无全局 overlay”对照。因此全局 overlay 的独立 token 成本仍是 **NOT EXECUTED**，不能猜测。

### 单次真实工具调用

任务：模型只运行一次 `git status --short`，然后返回 `DONE`。

```text
thread.started               3.830s
command_execution started   11.354s
command_execution completed 12.040s
turn.completed              14.861s
```

分解：

- 会话启动/装载：约 3.8 秒；
- 首次模型决策：约 7.4 秒；
- PowerShell + Git 命令：约 0.686 秒；
- 工具后的最终模型回复：约 2.8 秒。

因此工具循环中模型回合远大于该命令本身；大量细碎工具调用会重复支付模型回合成本。

### 本地代理入口

`http://127.0.0.1:15721/v1/models` 的五次本地连接/响应为约 1.0–1.5ms。这只证明本地 hop 很轻；无法隔离代理向上游转发模型请求的耗时。没有 direct-provider 对照前，不能把 CC Switch 判为主因或排除其上游路由影响。

## 原方案可行性审计

| 原建议 | 结论 | 原因 |
|---|---|---|
| 给 WORK-LAB 加 trusted 以加速 CLO | **不可行/无关** | CLO 已 trusted；运行目录不同 |
| 移除或降级 elevated sandbox | **不建议** | 官方首选 elevated；原“管理员提权”解释错误 |
| 将 supports_websockets 改为 true | **未经验证，不可直接做** | 必须由 provider 真正支持；false 不等于非流式 |
| 因 120s timeout 禁用 node_repl | **当前证据不支持** | 临时禁用后启动 3.797s→3.826s，无改善 |
| medium 改 low | **有条件可行** | 可按低风险任务临时覆盖；收益需多样本，复杂任务可能降质 |
| on-request 改 never | **技术可行但不作为默认方案** | 减少真实审批停顿，但扩大安全风险；仅用于受控非交互任务 |
| 减少全量门禁 | **可行，且项目已规定** | 应执行 CLO 的分级验证策略，不应每轮全量 |
| 合并工具调用/减少 agent 回合 | **可行，优先** | 真实时间线表明每个模型回合约数秒 |

## 修订后的执行方案

### P0：保持安全基线，不改配置

- 保留 `windows.sandbox = "elevated"`、`sandbox_mode = "workspace-write"`、`approval_policy = "on-request"`。
- 保持 Cognitive-Loop-OS trusted；不为性能理由修改 WORK-LAB trust。
- 不伪造 `supports_websockets = true`；不因 timeout 数字禁用 MCP。

### P1：立即执行的流程优化

1. **持续会话**：一个 TaskPack 使用一个持续 writer，避免重复 `codex exec` 冷启动和约 20k token 上下文装载。
2. **批量读取/搜索/状态检查**：独立信息一次并行获取；避免“读一个文件→模型一轮→再读一个文件”。
3. **定向验证优先**：严格执行 `<Cognitive-Loop-OS>/docs/VERIFICATION_POLICY.md`：开发中定向 RED→GREEN，最终聚合树只跑一次完整门禁。
4. **失败门禁只重跑失败项**：修根因后先跑受影响 gate；最终树变化后才执行一次完整聚合门禁。
5. **减少无意义汇报回合**：中间进度不触发额外 agent 重启或 reviewer；高风险边界才独立审查。

### P2：可选、需单独验证

1. **Fast mode**：官方称 GPT-5.6 可达约 1.5× 模型速度，但 GPT-5.6 消耗约 2.5× Standard credits。当前通过自定义 CC Switch provider，必须先验证其是否正确广告/转发 fast tier；未经用户接受成本前不启用。
2. **按任务使用 low reasoning**：仅对机械文档、格式、已明确的单点修改临时覆盖；架构、安全、迁移、复杂调试保持 medium/high。采用至少 5 次同类暖缓存样本比较中位数，而不是单次结果。
3. **代理 A/B**：若要判断 CC Switch 上游路由影响，使用同模型、同 prompt、同缓存条件比较 direct official 与 local relay 的 TTFT/总耗时；这会改变路由与计费，必须另行授权。
4. **升级/稳定性评估**：当前 CLI 为 alpha 构建；只在官方兼容矩阵、变更日志和现有规则安全审查后升级，不把升级本身当成必然提速。

## 验收标准

优化前后用相同任务集，至少记录：

- thread.started 时间；
- 首次 command/tool 开始时间；
- turn.completed 时间；
- 输入/cached/output/reasoning token；
- 工具调用次数；
- 实际审批停顿次数；
- 定向门禁与完整门禁各运行次数。

只有中位数改善且错误率、审批安全、验证覆盖不退化，才接受配置或流程变化。
