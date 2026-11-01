# Open Design 更新复验记录（2026-08-12）

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


- 任务：OP 更新后本仓库集成的全项复验
- 证据等级：E3（真实 daemon 运行验证）

## 更新迹象

| 项 | 值 |
|---|---|
| `resources/app/prebundled/` 更新时间 | 2026-08-11 17:38（晚于主体文件 7月2日） |
| 命令面变化 | 新增 `od plugin publish-repo <folder>`、`od plugin open-design-pr <folder>`（社区发布） |
| 桌面应用本体 | 运行中（9 个 Electron 进程），未干预 |

## 复验结果（全部真实执行）

| 检查 | 结果 |
|---|---|
| daemon 启动 | ✅ `ELECTRON_RUN_AS_NODE=1 "Open Design.exe" daemon-cli.mjs --port 7456 --no-open`（stdout 落文件防 EPIPE），health 200 |
| 插件注册保留 | ✅ 10 插件（3 bundles + 7 atoms）全部在册，trust=trusted，source=local |
| doctor | ✅ commercial-design-core / visual-quality-core / production-handoff 仅 warnings（pipeline:/media: 词汇 + skill-ref 未解析），**无 error** |
| 命令面兼容 | ✅ plugin / artifacts / project / tools / mcp / research 全在 |
| Codex 连接 | ✅ `POST /api/test/connection` → `{"ok":true, agentName:"Codex CLI", model:"gpt-5.5", latencyMs:~12s}` |
| app-config | ✅ CODEX_BIN 指向当前版本 `8e8bf206e63ac436`、默认项目 = DESIGN-LAB（备份 1 份留存） |

## 版本标识注意点

- `resources/open-design-config.json`：`appVersion: "0.13.0"`
- 此前 E3 实测（About 界面 + 官方插件源路径）：**0.18.1**
- 二者矛盾；不影响已验证功能（注册/doctor/Codex 全部实测正常），建议下次打开应用时核对设置页版本号

## 边界遵守

- 全程只读复验 + 临时 daemon（验证后已终止，无残留监听）
- 未读取凭据、未修改 Open Design 私有配置
- 仓库工作树保持 clean（复验不产生仓库改动，除本记录）
