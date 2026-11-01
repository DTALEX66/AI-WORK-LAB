# WORK-LAB Observer Package — 2026-08-16

本包来自云端基线 `fadcded4c4db8d6e1543e078b67cb746f0159a1f` 的本地审计副本。

内容：

- `observer-web/`：完整 Observer Web/Tauri 静态前端源码，包含黑白主题与本次状态显示修复；
- `observer-tests/`：Observer UI 合同测试与只读测试；
- `workflow-hotfix/`：canonical SQLite、项目级 Git 投影、Snapshot 构建修复；
- `taskpack/`：全量审计、架构重设计、界面设计和执行门禁任务包。

本包不包含 `.git`、凭据、会话、模型权重或其他项目数据，也没有进行 commit/push/PR。

验证记录：Observer UI `76 passed`；Workflow v3 Snapshot/Sidecar 定向测试 `25 passed`。

## 应用方式

1. 先在 WORK-LAB 本地工作树建立独立分支或 worktree；
2. 按 `taskpack/WORK-LAB-OBSERVER-AUDIT-REDESIGN-2026-08-16.md` 审查边界；
3. 将 `observer-web/` 对应内容映射到 `apps/observer/web/`；
4. 将 `workflow-hotfix/` 对应内容映射到 `packages/client-neutral-core/scripts/`；
5. 运行 Windows 完整依赖环境下的 UI、Python、Tauri、exact-SHA 和 canary 验证；
6. 未经明确批准，不执行 commit、push、PR、merge 或 release。
