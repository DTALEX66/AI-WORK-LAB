# V42 E3 Runtime Evidence — Open Design daemon 真实注册与回读（2026-08-11）

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This is a dated runtime
> record from 2026-08-11. It does not requalify the current checkout or
> override the current capability index, which remains authoritative for
> present E-level assignments.

- 任务：V42-0303（三 Bundle 注册）、V42-0304（任务/Artifact 回读）、V42-0305（失败/恢复）
- 证据等级：**E3**（真实运行时执行，非静态声明）
- 本文件是 `.hermes/task-runtime/` 中 E3 证据的 **tracked 镜像**（原证据保留于 gitignored 运行时目录）
- 源证据：`.hermes/task-runtime/drift-report-V42-0303-0305.json`、`V42-0301-interface-discovery.md`、`e3-artifacts/`

## 1. 运行环境

| 项 | 值 |
|---|---|
| daemon 启动方式 | `ELECTRON_RUN_AS_NODE=1 "D:\Programs\Open Design\Open Design.exe" daemon-cli.mjs --port 7456 --no-open` |
| 健康检查 | `GET http://127.0.0.1:7456/api/health` → **200** |
| Open Design 基线 | 0.18.1（stable / packaged / win32 / x64，About 界面确认） |
| 启动原因 | ELECTRON_RUN_AS_NODE 提供 Electron ABI node（better-sqlite3 NODE_MODULE_VERSION 145）；系统 node 127 直接运行报 ERR_DLOPEN_FAILED |

## 2. V42-0303 — 三 Bundle 真实注册（E3）

| 插件 | 版本 | trust | source | doctor |
|---|---|---|---|---|
| commercial-design-core | 0.2.0 | trusted | local | warnings-only（无 error） |
| visual-quality-core | 0.2.2 | trusted | local | warnings-only |
| production-handoff | 0.1.0 | trusted | local | warnings-only |
| + 7 依赖 atoms | 0.2.0 | trusted | local | — |

- `od plugin list` → 10 个插件（3 bundles + 7 atoms）
- `od plugin info commercial-design-core` → 完整 manifest + capabilitiesGranted（connector:*/pipeline:*/prompt:inject 等）
- 注册前修复：2 插件补 tags、visual-quality-core/production-handoff 的 taskKind 修正为上游枚举值、bundle context.atoms 改为 daemon builtin + assets 引用本地专业原子

## 3. V42-0304 — 任务生命周期与 Artifact 回读（E3）

| 步骤 | 命令 | 结果 |
|---|---|---|
| 项目创建 | `od project create --name "ODA4-E3-Verification"` | ✅ `944d1c7f-...` + conversation `a029dc6b-...` |
| Artifact 创建 | `od artifacts create --name proof/oda4-e3-proof.html --input ... --project <id>` | ✅ `{"ok":true, "file":{...}}` |
| Manifest 回读 | artifact 响应含完整 manifest | ✅ status=complete、createdAt/updatedAt |
| 磁盘读回 | `.od/projects/<id>/proof/oda4-e3-proof.html` + `.artifact.json` sidecar | ✅ 逐字节读回 |

## 4. V42-0305 — 失败 / 取消 / 恢复闭环（E3）

| 路径 | 命令 | 结果 |
|---|---|---|
| 失败（重复路径） | 同名 artifact 二次创建 | ✅ 409 `FILE_EXISTS` |
| 失败（非法项目） | 不存在的 project id | ✅ `no project matches` |
| 取消 | `od project delete <id>` | ✅ deleted |

## 5. 边界遵守

- 全程走 Open Design 公开 `od` 命令面，未修改任何私有 app-config/launcher
- 未读取凭据/认证值
- 验证用临时 daemon 已终止（无残留进程、7456 端口释放）
- daemon 经管道启动的 EPIPE 弹窗已识别（管道 stdout 断开导致），后续改用文件重定向 stdout

## 6. 一致性说明

- `capability-evidence-index.json` 中 runtime-integration 记录此前标记 E0（另一 writer 会话未访问本机 .hermes 证据，诚实降级）；本文件为树内 tracked 证据，使 **E3 升级具备 exact-tree 依据**
- visual-quality 的 Axe E3 证据（5 案例 0 violations，axe-core 4.9.1 真实浏览器）已在树内：`domain-packs/uiux-design/evidence/axe-scan-20260811.json` + 5 张案例证据卡
