# OpenViking 部署与排障手册

> 环境：Windows 11 · OpenViking 0.5.1.1（uv tool）· VLM=DeepSeek v4-flash · Embedding=本地 Qwen3-Embedding-0.6B（LM Studio, 1024 维）
> 最后更新：2026-10-23

## 1. 最终架构

```
客户端（Claude Code / Codex / Cursor / TRAE / Qoder / DSH / Hermes / CodeBuddy / MiniMax / WorkBuddy）
        │  MCP(http)  +  Hooks(stdio 脚本)
        ▼
OpenViking Server  127.0.0.1:1933
   /api  /mcp  /studio  /gateway（可选，同端口）
        │
        ├── VLM：https://api.deepseek.com/anthropic  → deepseek-v4-flash
        └── Embedding：http://127.0.0.1:1234/v1 → text-embedding-qwen3-embedding-0.6b (1024d)
```

**只有一个端口 1933**。1934 是 docker compose 的 Caddy 兼容反代（pip 部署无此物）；1935 是已废弃的旧网关端口。

## 2. 关键文件

| 用途 | 路径 |
|---|---|
| 模型与服务配置 | `~/.openviking/ov.conf` |
| 客户端连接配置 | `~/.openviking/ovcli.conf`（`url` 必须显式写，Helper 靠它判断） |
| 数据 | `~/.openviking/data` |
| 插件源码（多客户端共用） | `~/.openviking/openviking-repo` |
| 服务启动器 | `~/.openviking/start-openviking.cmd` |
| 开机自启 | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\OpenViking Server.cmd` |
| Hooks 日志 | `~/.openviking/logs/cc-hooks.log`（Claude）、`codex-hooks.log`（Codex） |

## 3. 各客户端接入方式

| 客户端 | 配置文件 | 机制 |
|---|---|---|
| Claude Code | `~/.claude/settings.json`（市场+插件）、插件自带 stdio MCP | 插件 `openviking-memory` 0.7.17，9 组 hooks |
| Codex | `~/.codex/config.toml`（`plugin_hooks=true`+marketplace）、插件 | 插件 0.11.14，stdio MCP 代理 |
| Cursor | `~/.cursor/mcp.json` + `~/.cursor/hooks.json` | agent-hook-plugin，7 事件 |
| TRAE CN | `~/.trae-cn/mcp.json` + `~/.trae-cn/hooks.json` | 4 事件（clientId `trae-cn`） |
| Qoder CN | `~/.qoder/settings.json`（`mcpServers` + `hooks`） | 复用 trae 适配器，clientId `qoder`（前缀 `qd-`） |
| DeepSeek Harness | `~/.dsh/profiles/desktop/`：`package.json` + `cordis.patch.yml` | `@openviking/dsh-memory-plugin` + `@deepseek-ai/dsh-mcp-client` |
| Hermes | `~/AppData/Local/hermes/config.yaml` → `mcp_servers` | http MCP |
| CodeBuddy / MiniMax / WorkBuddy | `~/.codebuddy/mcp.json`、`~/.minimax/mcp.json`、`~/.workbuddy/mcp.json` | 仅 MCP，无 hook 接口 |

## 4. 问题汇总（现象 → 根因 → 修法）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 启动报 `EmbeddingRebuildRequiredError: 512 differs from 1024` | 旧 512 维空集合残留 | 归档 `data` 目录后重建，`dimension=1024` |
| 2 | 服务起不来 / 模型段报错 | `ov.conf` 缺 vlm/embedding | 写全两段；本地 embedding 必须 `input:"text"` |
| 3 | Claude Code `MCP endpoint not found at 127.0.0.1:1933` | 其健康检查 `GET /mcp` 得到 406、`HEAD` 405 | 不用 HTTP MCP，改用插件 stdio 代理 |
| 4 | Codex `rmcp ... HTTP 404 NOT_FOUND` worker 退出 | 手写 `[mcp_servers.openviking]` 与插件自带代理冲突 | 删除手写条目，只留插件 |
| 5 | Codex hooks 不触发 | 未信任 hooks | 交互式 `codex` 选 Trust all；自动化加 `--dangerously-bypass-hook-trust` |
| 6 | Codex 调 MCP 工具报 approval 错误 | `exec` 模式 approval=never | 交互模式逐次批准，或加 `--dangerously-bypass-approvals-and-sandbox` |
| 7 | `openviking-server ingest backfill` 全部 `Resource not found` | 0.5.1.1 服务端只接受 `memory_types/peer/self/working_memory`，而 ingest（0.5.2 代码）传 `commit_token_threshold` 等 → 400 | 关闭 ingest，等 0.5.2 上 PyPI 再跑 |
| 8 | Claude Code CLI 401/403 | 中转 token 属 `claude kiro` 分组，Base URL 必须是 `https://kiro.yzzt.top` | 改 Base URL；`cc.yzzt.top` 只适用满血稳定claude 分组 |
| 9 | Helper 目录页 `files:get-tree HTTP 404` | Helper 的 active profile 被配成 `https://api.deepseek.com`（managed 模式） | 新建 `selfHosted` profile 指向 `http://127.0.0.1:1933` 并激活 |
| 10 | Helper 不自动识别本地服务 | `ovcli.conf` 未显式写 `url`（等于默认值被省略），Helper 判断 `"url" in config` 失败 | 手动补 `"url": "http://127.0.0.1:1933"` |
| 11 | Windows 上官方 bash 安装器直接退出 | `install.sh` 按 `uname -s` 判断，MINGW 报 Unsupported OS | 手写各客户端 JSON/TOML，或用 Helper 按钮 |
| 12 | 无法给 Qoder 装 hook | OpenViking 无 qoder host 适配器 | 复用 trae 适配器；在 `hosts/index.mjs` 注册 `qoder = {...traeCn, prefix:"qd-"}` |
| 13 | 服务会话结束就停 | 进程挂在当前会话 | 双击 `start-openviking.cmd` 常驻；开机由 Startup 项拉起 |

## 5. 常用运维命令

```bash
# 服务
openviking-server --host 127.0.0.1 --port 1933      # 启动
curl http://127.0.0.1:1933/health                   # 健康检查
ov config add custom --name local --url http://127.0.0.1:1933 --activate

# 导入与检索
ov add-resource ./doc.md --to viking://resources/demo --wait
ov find "问题" --uri viking://resources/demo
ov read "viking://user/default/memories/preferences/user/xxx.md"
ov tree viking://user/default -L 3

# 记忆
ov add-memory "记住：..."      # 直接写
ov rm "viking://..."           # 删除

# 日志与诊断
tail -n 20 ~/.openviking/logs/cc-hooks.log
tail -n 20 ~/.openviking/logs/codex-hooks.log
```

## 6. 残留与限制

- **ingest 归档导入**：175 个历史会话（claude_code 7 / codex 149 / workbuddy 19）已扫描成功，写入被版本阻塞，等 0.5.2。
- **Cursor 历史归档**：官方标注暂缓（`state.vscdb` 无文档、随版本漂移）。
- **无 hook 接口**：CodeBuddy、Qoder 之外的 MiniMax Code、WorkBuddy 只能靠模型主动调工具。
- **无扩展点**：豆包 App、MiniMax Design、Open Design、ComfyUI、Grok Bot、CC Switch 无法接入任何记忆产品。
- **DeepSeek 无视觉**：图片、扫描版 PDF 解析会失败；需要时把 VLM 换成本地 Qwen2.5-VL。
- **依赖 LM Studio**：`127.0.0.1:1234` 不在线则 embedding 不可用（导入、检索全失败）。

## 7. 验证清单

| 项 | 命令 | 期望 |
|---|---|---|
| 服务 | `curl 127.0.0.1:1933/health` | `healthy:true` |
| 工具 | MCP `tools/list` | 21 个工具 |
| 检索 | `ov find "..."` | 命中并带 score |
| 写入 | `ov add-resource --wait` | `status success` |
| Hooks | `tail logs/cc-hooks.log` | 出现 `auto-recall` / `auto-capture` / `commit` |
| 召回生效 | 在任意客户端问曾说过的事 | 无需解释即答对 |
