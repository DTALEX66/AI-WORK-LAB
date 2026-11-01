# WORK-LAB Master TaskPack v2.0 — 交付总结与错误记录（2026-08-10）

> 状态：`MERGED_TO_MAIN`（PR #34 / #35 / #36）
> 最终 main head：`a4c67e9c836d7b8e1a794aa16316575b3d2e91d1`
> 本地/远端：已同步，工作树干净

## 1. 交付摘要

### 已合并到 main 的 PR

| PR | 标题 | merge commit | CI |
|---|---|---|---|
| #34 | feat(wl3): master taskpack 2.0 full local implementation batch | `1160acc` | 5/5 success |
| #35 | chore: regenerate CURRENT_STATE for merged main head | `008d588` | 5/5 success |
| #36 | feat(wl3-300): growth watcher trigger chain wired into worker | `a4c67e9` | 4/5 success（integration 按 path-aware 正确跳过） |

### 28 个 WL3 任务最终状态

```text
VERIFIED_LOCAL:                      26（WL3-000..710、800、810）
BLOCKED (toolchain):                  1（WL3-620 Windows portable：cargo/rustc 缺失）
LOCAL_VERIFIED_READY_FOR_APPROVAL:    1（WL3-820 批准包）
RECONCILE_REQUIRED:                   0
```

### 核心交付物

**Wave 0（事实重置）**
- CURRENT_STATE freshness 修复：git identity（head/tree/remote_main）+ CI 证据 + ancestor 语义
- STAGE3_BASELINE 刷新至真实 head，候选树冻结 `f1578cbd`（475 文件）

**Wave 1（运行时收敛）**
- `canonical_store.py`：SQLite WAL 唯一事实库（11 表、事务、lease/fencing/heartbeat/zombie 恢复、token allowlist）
- `durable_worker.py`：acquire→heartbeat→checkpoint→side-effect→reconcile→release，bounded retry→BLOCKED_POLICY
- `project_registry.py`：跨项目发现（真实 MINIGAME canary）+ 极简 Profile
- `collectors.py`：五类真实 collector（task/git/usage/quality/growth-watcher）
- `sse_hub.py`：真实长连接 SSE（heartbeat/cursor/续传/慢消费者上限）
- Observer：canonical projection 消费唯一事实源；`observer-events.jsonl` 权威退役

**Wave 2（治理）**
- 真实平台发现（codex/hermes UNIQUE）、fail-closed reconciler、受控复现
- config-ownership v2 唯一注册表（8 层/30 字段/5 禁止）+ 三方协调器
- 13 Skills 完整包 digest、growth 状态机（project/global 分门）、记忆治理（TTL/supersedes/隔离/pinned）、供应链扫描、模型 lane/billing

**Wave 3（可移植/收口）**
- 四真实 Adapter conformance、未来 Agent 分级（L0-L4）、6 换平台演练、WL3-800 集成门禁、只读体积审计、批准包

### 清理

- 删除废弃 `MIGRATION_LEDGER.json`（2026-08-05 一次性迁移台账，零引用）
- 清理全部 `__pycache__`

## 2. 本轮发现并修复的错误（ERR-018..ERR-023）

| ID | 分类 | 症状 | 根因 | 修复 |
|---|---|---|---|---|
| ERR-018 | contract_drift | freshness 允许旧 branch/head/CI 通过 | 校验排除 git/CI | 完整 git identity + CI 证据 + ancestor 语义 |
| ERR-019 | ci_configuration | workflow 解析失败（0 job） | `defaults.run.env` 未加引号路径值 | job 级 env + 引号 |
| ERR-020 | ci_configuration | freshness 在 CI 误判 not-ancestor | 浅克隆缺历史 | workflow job `fetch-depth: 0` |
| ERR-021 | feature_gap | growth watcher 未接入 worker | 离线函数未接触发链 | 第五 collector + 状态机分类 |
| ERR-022 | test_behavior_alignment | baseline/current-state 测试断言过期 | 未随 Master 2.0 同步 | 断言更新（28 任务/dirty=5） |
| ERR-023 | test_behavior_alignment | telemetry event_id 重复 | 时间戳 ID 碰撞 + 双写 | UUID ID + 单写者契约 |

错误完整记录见 `50-taskpacks/error-ledger.json`（总计 23 条）。

## 3. 验证证据（全部真实执行）

```text
Full quality-gate verify: 21 gates PASS（governance 443 + runtime-convergence 95 等）
Observer: Python 57 tests OK · JS 43 passed 0 failed
Root CI suite: 14/14（exact-tree clean-tree 前置在提交后转绿）
GATE-RUNTIME-CONVERGENCE: claimable=True（9/10，#1/6/9 环境 PENDING 按 §15 不阻塞）
CURRENT_STATE freshness: PASS（head a4c67e9）
浏览器验收: R2 阶段 console=0/errors=0；本轮 HTTP 200 资源加载确认
真实双项目 canary: WORK-LAB + MINIGAME（collector + SSE LIVE）
CI exact-SHA: PR #34/#35/#36 全部通过
```

## 4. 剩余边界（诚实声明，不冒充完成）

```text
WL3-620 Windows portable EXE:  BLOCKED（本机无 cargo/rustc；需批准安装工具链）
WL3-820 release approval:      PENDING_HUMAN_APPROVAL（批准清单 7 项均未授权）
GATE-RUNTIME-CONVERGENCE #9:   环境 PENDING（Tauri 真实 Sidecar，同工具链）
未执行: paid provider smoke、live/global apply、真实外部项目 profile 写入、
       归档删除/Git 历史减重（仅只读审计）、正式 production release
```

## 5. 关键文档索引

- 任务台账（唯一）：`.hermes/task-runtime/task-ledger/ledger.json`
- 状态快照：`00-governance/generated/CURRENT_STATE.json` + `.md`
- 基线：`00-governance/generated/STAGE3_BASELINE.json`
- 任务图：`50-taskpacks/WORK-LAB-STAGE-3-TASK-GRAPH.json`
- 批准包：`50-taskpacks/WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md`
- 错误台账：`50-taskpacks/error-ledger.json`
