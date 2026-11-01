# ODA4-0303 — Runtime Registration & Version Readback（E3）

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


- 状态：**PARTIAL E3**（运行时识别 + 版本回读 + 本仓库产物运行时使用 = 已达成；三公开入口 bundle 注册 = 待办）
- 运行时：Open Design **0.18.1**（stable / packaged / win32 / x64）
- 证据文件：`.hermes/task-artifacts/open-design-v4/runtime-registration-evidence.json`

## 已达成（E3 证据）

| 验收项 | 证据 | 状态 |
|---|---|---|
| 真实 Open Design 进程可识别 | 9 个 `Open Design.exe` 进程 + 3 个命名管道（daemon/web/desktop） | ✅ |
| runtime ID / version 可回读 | `0.18.1`（About 界面 + 官方插件源路径 `versions\0.18.1` + config） | ✅ |
| 本仓库注册为项目位置 | `projectLocations` 含 `DESIGN-LAB -> D:\All projects\DESIGN-LAB` | ✅ |
| 真实项目数据 | `项目初筛`（baseDir 在本仓库下）+ 应用插件快照 `f1a22a65` | ✅ |
| **本仓库产物被运行时真实使用** | `anomaly-monitor-dark` 设计系统：`status=published`、`designSystemId=user:anomaly-monitor-dark`（当前活动设计系统）、provenance="Imported from D:\All projects\DESIGN-LAB\design-system\DESIGN.md" | ✅ |

## 待办（三公开入口 bundle 注册）

- `commercial-design-core`、`visual-quality-core`、`production-handoff` **尚未**在 0.18.1 运行时注册。
- 障碍：Open Design daemon 走**命名管道**私有协议，不暴露 HTTP 端点；`daemon-cli` 需 `OD_DAEMON_URL`（由应用在 agent run 时注入），系统 Node 直接 `plugin install` 因 `ECONNREFUSED 7456` 失败。
- 获取方式：需在应用内通过官方插件安装（`od plugin install --source <path>`，需 daemon 暴露 HTTP），或应用 UI 注册。

## 技术结论（E3 关键学习）

1. Open Design 0.18.1 的 daemon **仅命名管道通信**，不监听任何 TCP 端口（已扫描 7400-7599 全部关闭）。
2. `daemon-cli.mjs` 设计为"daemon 启动 code-agent 时注入 `OD_DAEMON_URL` + `OD_PROJECT_ID`"，供 agent 回调。
3. 本仓库产物（design-system）已被运行时真实导入 + 发布，证明**仓库→运行时链路已通**。
4. 数据库 `app.sqlite` 可只读访问（项目/插件/快照元数据），提供真实运行时证据。

## 边界
- 全程只读数据库与运行时数据，未修改任何 Open Design 私有配置。
- 未读取任何凭据/认证值。
- Open Design 保持运行，未强制关闭。

## 下一步
- 三公开入口注册需应用侧 daemon HTTP 暴露。若用户开启一次 agent run 或允许 `od plugin install` 连接，可补全 bundle 注册证据至完整 E3。
