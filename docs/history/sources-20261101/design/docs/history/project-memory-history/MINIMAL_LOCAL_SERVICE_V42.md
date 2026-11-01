# MINIMAL_LOCAL_SERVICE_V42 — 最小本地服务与禁止独立后端决策

- 版本：`4.2`｜任务：`V42-0306`｜状态：`ACTIVE`｜证据：E2
- 依赖：V42-0305 ✅（E3 注册/生命周期/恢复已验证）
- 现场证据：`.hermes/task-runtime/V42-0301-interface-discovery.md`、
  `.hermes/task-runtime/drift-report-V42-0303-0305.json`

## 决策

**本仓库不运行、不部署、不维护任何独立后端服务。**

Open Design 桌面应用自带本地 daemon（`daemon-cli.mjs`，默认
`http://127.0.0.1:7456`，Electron ABI node 运行），这是**唯一允许的本地
服务**，且属于 Open Design 上游能力，不是本仓库的产物。

## 现场事实（V42-0301/0303 实测）

| 项 | 值 |
|---|---|
| daemon 入口 | `D:\Programs\Open Design\resources\app\prebundled\daemon\daemon-cli.mjs` |
| 启动方式 | `ELECTRON_RUN_AS_NODE=1 "Open Design.exe" daemon-cli.mjs --port 7456 --no-open` |
| 默认端口 | `7456`（env `OD_PORT`，默认绑定 127.0.0.1，`OD_BIND_HOST` 可限制接口） |
| 健康检查 | `GET /api/health` → 200 |
| 核心能力 | 插件安装/apply/doctor、项目 CRUD、artifact 创建/回读、automation、memory、MCP |
| 依赖约束 | better-sqlite3 编译目标是 Electron ABI（NODE_MODULE_VERSION 145），**系统 node（127）无法直接运行**，必须用 `ELECTRON_RUN_AS_NODE=1` |

## 边界规则（Gate）

1. **只允许上游 daemon**：本仓库不得实现自己的 daemon、事件循环、任务调度器、
   HTTP 服务或 WebSocket 服务；
2. **无独立后端**：不建 SaaS、不部署云端服务、不引入后端框架（FastAPI/Express 等）
   作为产品运行时；
3. **无独立账号系统**：登录态复用 Open Design 本机会话/Codex 订阅，不新建账号体系；
4. **headless 服务仅在上游合同要求时**：`od` CLI 暴露的 daemon 包装命令
   （plugin/artifacts/automation 等）由外部 agent 按需调用，不常驻本仓库进程；
5. **端口与绑定**：任何上游 daemon 使用必须显式 `--host 127.0.0.1`（或更严），
   不暴露到局域网/公网；
6. **不修改上游私有配置**：只通过 `od` 公开命令面操作，不写 Open Design
   app-config/launcher。

## 与职责边界合同的关系

`BOUNDARY_CONTRACT_V42` 已声明"无第二前端、Agent runtime、模型网关"。
本文件是其运行时层面的具体化：本地服务方面同样无第二实现，全部复用上游 daemon。

## 验证（E2）

- 本阶段 E3 验证全程使用上游 daemon（`od` CLI），未启动任何本仓库进程；
- daemon 健康检查、插件注册、项目/artifact 操作均通过 `http://127.0.0.1:7456` 完成；
- 验证结束后 daemon 保持运行（用户桌面应用正常服务），无本仓库残留进程。

## Gate 判定

- 最小本地服务决策完成 ✅
- 无独立后端：符合 ✅（全仓无后端框架依赖、无服务端代码、无账号系统）
