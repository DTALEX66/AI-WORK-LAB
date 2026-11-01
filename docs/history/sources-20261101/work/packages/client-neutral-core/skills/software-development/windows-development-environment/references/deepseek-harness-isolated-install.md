# DeepSeek Harness isolated install + loopback launch (validated 2026-08-15, WL-DSH-030)

Upstream agent-runtime接入项目为隔离 runtime 的完整 recipe。DSH 升级 / 重装 / 同类
agent-runtime（其他 monorepo CLI 工具）接入时复用。核心原则：pin immutable commit、
逐次 pnpm 不改全局、一切状态在项目 `.hermes/task-runtime/` 内、loopback-only、遥测禁用。

## 完整流程（可复制）

```bash
# 1. partial clone + checkout pin（blob:none 省流量，pin 不用 master）
git clone --filter=blob:none <upstream-repo>.git .hermes/task-runtime/<name>/source
git -C .hermes/task-runtime/<name>/source checkout <immutable-commit-sha>
git -C .hermes/task-runtime/<name>/source rev-parse HEAD   # 验证 pin

# 2. 逐次 pnpm 不改全局（见 run-pnpm.js 模式；corepack enable 会改 Hermes node 目录）
node .hermes/task-runtime/run-pnpm.js .hermes/task-runtime/<name>/source install --frozen-lockfile

# 3. build（注意嵌套 --filter 陷阱，见下）
node .hermes/task-runtime/run-pnpm.js .hermes/task-runtime/<name>/source --filter <web-frontend-pkg> run build

# 4. dump-config 验证 CLI + 脱敏（default-only 不含 user layer/secret）
node .hermes/task-runtime/run-dsh.js <source> <dsh-home> --dump-default-config --profile web

# 5. 启动 loopback（DSH_HOME 隔离 + 遥测禁用）
node .hermes/task-runtime/run-dsh.js <source> <dsh-home> web

# 6. 三重验证（服务 + 绑定 + UI 身份）
curl -s -o <health.html> -w "%{http_code}" http://127.0.0.1:3080/   # 200
netstat -ano | grep ':3080' | grep LISTENING                          # 必须是 127.0.0.1，非 0.0.0.0
# UI：浏览器打开 127.0.0.1:3080，确认 <title> 和交互元素真实渲染（browser_navigate 返回元素树即可）
```

`run-dsh.js` / `run-pnpm.js` 脚本模式：项目内脚本用 `path.dirname(process.execPath)` 推导
node 目录下的工具 JS 入口（`corepack/dist/corepack.js`、CLI 的 `apps/cli/src/bin.ts`），
`spawnSync` 时设 `DSH_HOME`、`DSH_TELEMETRY_DISABLED=1`、`cwd=<source>`。这样绕开 wrapper
对 `.cmd` 和项目外绝对路径的拦截。

## 关键陷阱（都实测踩过）

### 1. `pnpm run build` 嵌套 `--filter` 报 ELIFECYCLE，单独跑却成功

大型 monorepo 的根 `build` script 常是 `pnpm run build:lib && pnpm --filter <pkg> run build`
——根 build 里再嵌套 `pnpm --filter` 会 `[ELIFECYCLE] Command failed with exit code 1`，
但日志里 build:lib 全部 `Build complete`，真正失败点在嵌套的 `--filter` 子进程（wrapper
下嵌套 pnpm spawn 问题，非源码构建缺陷）。**修复：跳过根 build，直接单独跑
`pnpm --filter <pkg> run build`**，前端 dist 正常产出。

### 2. web 启动报 "frontend dist not built; run pnpm run build first"

CLI 的 web profile 启动时检查前端 dist，dist 未构建就报这个错（不是 CLI 坏，是没 build）。
先跑 `<pkg> run build` 产出 dist，再启动 web。

### 3. loopback_only 校验不能把 RFC1918 private IP 当合法

安全校验若写成 `host not in LOOPBACK and not PRIVATE_IP_RE.match(host)`，会把
`192.168.x.x`/`10.x.x.x` 当合法放行——违反 loopback_only 契约。**正确逻辑：只允许
`127.0.0.1` / `localhost` / `::1`，其余（含 private LAN IP、公网、0.0.0.0）一律拒绝。**
用测试锁死：`for host in ("0.0.0.0","example.com","203.0.113.5","8.8.8.8","192.168.1.10"): assert not ok`。

### 4. DSH_HOME 隔离 + 遥测禁用

- `DSH_HOME=<project>/.hermes/task-runtime/<name>/dsh-home`（profiles/storages/sessions 都在此，绝不外溢）。
- `DSH_TELEMETRY_DISABLED=1` 摘除 session-telemetry-otel row（默认 exporter 指向
  `https://harness-telemetry.deepseeksvc.com/v1/logs`，必须禁）。
- DSH_HOME 初始化会在 `dsh-home/profiles/node_modules` 建 pnpm junction 树（Windows
  符号链接循环，`rglob` 会 `FileNotFoundError` 绊到，无害，用 `iterdir()` 顶层列出即可）。

### 5. 契约默认值与任务包吻合

DSH web profile 的 `dump-default-config` 直接暴露契约事实：webserver `host ?? '127.0.0.1'`、
`port ?? 3080`、sandbox `workspace-write`、approval `ask`、默认模型 `deepseek-v4-flash`、
credentials `dsh-credentials-local`（本地，Agent 不读）。接入前先 dump-config 核对默认值，
不要猜。

## 回滚

停止：kill 启动进程（记 PID）+ 确认端口关闭。回滚：停进程 → 保留 source + receipt 只读 →
标记 runtime QUARANTINED；不杀未知 PID，不在 source checkout 里 `git reset/clean`。
