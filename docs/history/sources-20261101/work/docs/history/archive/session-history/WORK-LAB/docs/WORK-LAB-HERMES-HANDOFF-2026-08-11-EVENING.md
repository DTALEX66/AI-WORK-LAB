# WORK-LAB 交接（2026-08-11 晚）— Hermes/DeepSeek 续接

> 上一交接：`WORK-LAB-HERMES-DEEPSEEK-HANDOFF-2026-08-11.md`
> 本交接基准：main HEAD `e783e470bccdf0622d5f4422695e70a69a0429d1`（= origin = GITHUB）
> 工作树：干净（0 项未提交）· AHEAD_BEHIND=0/0

## 已完成（本交接覆盖范围）

| # | 任务 | 结果 | 证据 |
|---|---|---|---|
| 一 | Codex 用户覆盖配置 | ✅ PASS | apply(10 技能) + verify，用户 config 字段保留，auth/session 未触碰 |
| 二 | Observer 原生 Tauri | ✅ PASS | rustc 1.88 + MSVC 14.44 → EXE/MSI/NSIS → 安装/运行/卸载闭环 → Release v0.1.0-native-observer |
| 三 | 完整验证 | ✅ PASS | Observer 48/48 · Node 44+4 · runtime-convergence 104 · diff clean |
| 四 | Git 与发布 | ✅ PASS | PR #51(`1bda8ed`) + #52(`e783e470`) → CI 5/5 + 5/5 → 本地同步 |
| 五 | 实时链路验证 | ✅ PASS | SSE 实测：写入即推送（13→15），dashboard mode=LIVE |
| 六 | 总工作区发现 | ✅ PASS | `D:\All projects` 注册 2 项目，work-lab ACTIVE（Hermes 运行+证据新鲜） |

## 运行时状态（本机，交接有效）

```text
sidecar:            PID 23692，http://127.0.0.1:2660（动态端口，SSE /api/v1/events）
observer dashboard: http://127.0.0.1:6522/（PID 8992 本轮启动，/api/dashboard）
canonical store:    .hermes/task-runtime/workflow/canonical.sqlite（13 telemetry，2 projects，3 tasks）
Rust 工具链:        D:\All projects\OS Environment\.rustup（rustc 1.88.0）+ .cargo + BuildTools
构建缓存:           .hermes/task-runtime/cargo-target
Release:            v0.1.0-native-observer（app.exe/MSI/NSIS/SHA256SUMS）
```

## 续接任务（按序）

### 1. freshness 标签语义优化（低优先）
dashboard 的 `freshness.state` 在 LIVE 模式下显示 STALE——快照语义导致。建议：LIVE 模式且 SSE 连接存活时标 FRESH。涉及 `observer_canonical.py` freshness 计算 + 前端渲染。

### 2. 活跃检测增强（中优先，可选）
`active_projects.py` 的 120 分钟 freshness 窗口是启发式。可选：把 freshness 证据扩展到 git reflog/status 修改时间，或让 Workflow worker 周期性调用 `sync_workspace_projects` 维持 ACTIVE 状态。

### 3. WL3-820 release approval（待人工）
批准包 `WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md` 状态 LOCAL_VERIFIED_READY_FOR_APPROVAL。正式生产 release（非 alpha/native 前缀）需用户批准。

### 4. Observer 常驻进程管理（运维）
sidecar（23692）与 dashboard（6522）是交接部署的常驻进程。若重启机器需重新拉起。启动命令：
```bash
# sidecar
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/workflow python scripts/workflow/sidecar.py --project-root "D:\All projects\WORK-LAB" --runtime-root "D:\All projects\WORK-LAB\.hermes\task-runtime\workflow" --host 127.0.0.1 --port 0
# observer dashboard
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src;../../10-workflow/workflow-assistance/scripts/workflow python scripts/observer_dashboard.py --project-root "D:\All projects\WORK-LAB" --canonical-store "D:\All projects\WORK-LAB\.hermes\task-runtime\workflow\canonical.sqlite" --host 127.0.0.1 --port 6522
```

## 边界与纪律（延续）

- Observer 严格只读（projection-only），所有写面归 workflow-assistance
- commit/push/PR/release/global apply 需逐项授权
- 不得访问 E:\；不读凭据/会话/正文；敏感值 `[REDACTED]`
- error-ledger 契约：枚举合法（7 分类/5 phase/4 evidence/6 status），raw_sensitive_data=false
- CURRENT_STATE 每次代码改动后重新生成（否则 integration gate freshness 失败）
- 工具链版本：tauri 2.11.x 需要 rustc ≥1.88（合同 1.77.2 仅为下限文档值）

## 本机配置修复（2026-08-12 复查）

- Codex overlay：本机 10 skills → apply 同步为 **12 skills**（补 github-delivery/open-design-integration/update-safety，云端 #61 新增），verify PASS issues=[]
- 僵尸 sidecar 锁清理：旧 endpoint pid=23692 被 Codex 桌面 renderer 复用导致 sidecar_already_running 误判；删锁后重启 sidecar → http://127.0.0.1:3525，dashboard :6522 mode=LIVE 恢复
- reasoning_effort = medium（live 实测，官方默认；不在 config-ownership 受管清单，preserve_unknown 保留用户值）
