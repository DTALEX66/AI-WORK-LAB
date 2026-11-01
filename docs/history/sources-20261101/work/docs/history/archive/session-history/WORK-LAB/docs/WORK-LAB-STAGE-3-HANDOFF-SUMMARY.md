# WORK-LAB Stage 3 交接摘要（Stage 3 Handoff Summary）

- 日期：2026-08-08
- 任务包：`WORK-LAB-STAGE-3-CANONICAL-CONTROL-PLANE`（v1.0，2026-08-08）
- 仓库：`DTALEX66/WORK-LAB`｜分支：`main`｜HEAD：`a3a6fa6`
- 状态：这是 2026-08-08 的历史本地快照，已由 2026-08-10 control-plane/Codex handoff 取代；当前发布状态以 PR #33 的新 exact-SHA CI 和 post-merge readback 为准。

## 一、定位（不漂移）

WORK-LAB 是面向多个 Agent、IDE、GitHub 和项目仓库的**本地、客户端中立、可迁移、可审计、可恢复的工作流增强控制面**。不是智能体、聊天软件、模型网关、凭据中心、LLMOps 平台或项目运行时。

只有两个活动模块：
- `10-workflow/workflow-assistance`：唯一主动后端（配置/资产治理、平台适配、任务恢复、规则/技能/记忆、项目注册、CI、唯一 Telemetry Ledger 与 Canonical Projection）。
- `30-observer/work-lab-observer`：严格只读桌面观测面（任务、平台身份、配置漂移、Token/费用、CI、证据）。

Open Design 与 MINIGAME 已完全切割，仅保留历史归档指针。

## 二、本批交付（前序 writer 已完成并通过测试）

### 基线（WL3-000）
- `00-governance/generated/STAGE3_BASELINE.json`：真实 head=`a3a6fa6`、dirty 分类（PREDECESSOR_OUTPUT=Observer 组）、writer 唯一、前序 CLOSED/COMPLETED。
- `CURRENT_STATE` 已重新生成（head `f141946→a3a6fa6`，contracts 28→30）。
- `50-taskpacks/WORK-LAB-STAGE-3-TASK-GRAPH.json`：Stage 3 机器可读任务图（WL3-000…820）。
- `tests/ci/test_stage3_baseline.py`：2 passed。

### 范围收口（WL3-010）
- `work-lab-gate.yml`：移除 `design-contract`、`production-evidence`、`standard-validators` 与三分支离线 pilot；2026-08-10 修正后 required integration job 已明确运行 Stage 3 baseline、CURRENT_STATE freshness 与 Observer Web/desktop 契约检查。
- `run_quality_gate.py`：同步移除已废弃子命令。

### 平台实例唯一性（WL3-100/110/120）
- `scripts/workflow/platform_identity.py` + `schemas/workflow/platform-identity.schema.json`
- `scripts/workflow/instance_reconciler.py`
- `scripts/workflow/controlled_repro.py`
- 测试：`test_platform_identity.py`、`test_instance_reconciler.py`（OK）

### 配置所有权（WL3-200/210/220）
- `config/config-ownership.json` + `schemas/workflow/config-ownership.schema.json`
- `scripts/workflow/config_coordinator.py`
- `scripts/workflow/sync_codex_global_assets.py`
- `codex-assets/`（global-guidance、rules、8 个 skills）
- 测试：`test_config_ownership.py`、`test_config_coordinator.py`、`test_codex_global_asset_sync.py`（OK）

### 本地控制面（WL3-400/410/420）
- `scripts/workflow/sidecar.py` + `sidecar_lock.py`（单实例锁）
- `scripts/workflow/telemetry_ledger.py`（唯一 Ledger）
- `scripts/workflow/project_profile.py` + `config/project-profiles.json`（跨项目微型 profile）
- `scripts/workflow/observer_projection_adapter.py`
- 测试：`test_sidecar.py`、`test_sidecar_lock.py`、`test_telemetry_ledger.py`、`test_project_profile.py`、`test_observer_projection_adapter.py`（OK）

### Observer 只读 + 权威投影（WL3-500/600）
- `observer_runtime.py` 新增 `project_authority_dashboard`（从真实事件聚合权威投影，只读计算）。
- `observer_store.py` 改用 authority dashboard（schema v2）。
- Web 前端 api.js/app.js/render.js/state.js、live-snapshot.json 更新。
- 当前回归：Observer Python 47 OK、Node 43 OK；此计数取代历史较小套件。

## 三、验证证据（本会话复跑）

| 检查 | 结果 |
|---|---|
| `run_quality_gate.py verify`（canonical 20 gates） | **QUALITY_GATE_PASS** |
| workflow Stage 3 测试（identity/reconciler/config/sidecar/ledger/profile 等 11 个） | 全部 OK |
| observer 测试 | Python 47 OK、Node 43 OK |
| `test_stage3_baseline.py` | 2 passed |
| `work-lab-gate` CI（HEAD a3a6fa6） | 历史 baseline success；不作为 2026-08-10 发布候选的 exact-SHA 证据 |

## 四、未授权项（诚实标注，不伪造完成）

以下均未执行，按任务包 `publication/live/destructive` 策略保持 pending：
- 2026-08-10 corrective candidate 的最终 commit/push/PR merge（基础 PR #33 已存在，但最新修复尚需新 head CI）
- 最新 Codex state v3 对真实用户 Home 的 apply（先前 v2 已 readback；v3 仅在项目内隔离 Home 完成生命周期验证）
- 双入口卸载 / 配置迁移
- Windows portable Tauri build（无 Rust/Tauri toolchain，`PENDING_TOOLCHAIN_APPROVAL`）
- 付费 provider smoke
- 真实 OS / 外部项目 profile canary
- 归档删除 / Git 历史减重

## 五、边界遵守
- 未访问 E:\、未读凭据、未改 Codex/Hermes 全局 state。
- Observer 保持只读（authority dashboard 是只读投影计算，非写权限）。
- 未做任何历史重写。
