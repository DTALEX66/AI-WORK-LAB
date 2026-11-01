# ORCA PILOT — 独立待执行任务卡（2026-09-25）

**Task ID:** `ORCA-PILOT-20260925`
**Status:** PLANNED-OPEN（待 individually-authorized 执行；本轮**只建卡，不执行**）
**Priority:** P2-01（GOAL §12 第一优先）
**Owner:** 单写者（执行时指定；本轮 = 规划记录）
**Authority:** `/WORK-LAB-AUTHORITY.md` → taskpack → this card
**Registry entry:** `FUT-001`（`.project/governance/future-candidate-registry.json`）

## 为什么 Orca 第一优先

```text
Windows 成熟度高 / 开源 / Codex 支持强 / Worktree / Terminal / File / Diff /
多 Agent / 用户自己的订阅 / 可省掉 WORK-LAB 大量 IDE 开发
```

## 验证目标（端到端链路）

```text
WORK-LAB
  → Open Workspace
  → Orca
  → current project / worktree
  → Codex
  → git / test / evidence
  → WORK-LAB readback
```

## 第一轮 Pilot 只做四件（不改 Orca 内核）

```text
project launch
worktree identity
task correlation
exit / readback
```

## 执行前置（individually-authorized，缺一不可）

1. **DISCOVER/CLASSIFY 摄取管线**（registry `governance.intake`）：先查
   Orca 真实 repo URL / license / version / Windows 支持 / 安装副作用，
   输出 `SEARCHED / FOUND_COMPATIBLE / ...`，**不自动 git clone / npm install /
   docker pull / download model**。
2. **每步外部写操作单独授权**：project launch、worktree 创建、Codex 调用、
   evidence 落盘，各自 per-operation user approval；E:/F:/ 不碰。
3. **数据边界**：Pilot 产物只落 `.project-local/artifacts/orca-pilot/`，
   不外溢 C 盘用户目录 / 其他项目。
4. **证据纪律**：REAL evidence（verifiable handle / digest / producer /
   observed_at / source SHA），不把 fixture 升成 REAL，不伪造 PASS。

## 成功判据（拿到 REAL evidence 后才可晋升）

```text
project launch        : Orca 从 WORK-LAB 入口真实启动，readback 确认进程/窗口
worktree identity     : worktree 路径 + 分支 + HEAD 可回读并与 WORK-LAB task 关联
task correlation      : 一次 WORK-LAB task_id ↔ Orca 会话 ↔ Codex run 三方对齐
exit / readback       : Orca 退出码 + evidence 落盘 + WORK-LAB snapshot 回读
```

四件全拿到 REAL evidence → registry `FUT-001.status` 由 `PILOT_CANDIDATE`
推进；任一失败 → 停在待授权，记录 fail-closed 证据，**不盲修循环**。

## 明确不做

- 不修改 Orca 内核（第一轮）。
- 不自动安装/下载（需 individually-authorized）。
- 不把 Pilot 成功写成 `UNIVERSAL_WORKFLOW_VERIFIED`（那是 U18 的更强标签，
  需外部项目 + 第二真实执行器）。
- 不安装 Omnigent / OpenViking 等（各自独立卡触发）。

## 与 Future Candidate Registry 的关系

本卡是 registry `FUT-001` 的 `task_card`。执行产生 evidence 后，registry
条目由 `PILOT_CANDIDATE` 推进，并在 `OPEN-TASK-REGISTER.md` 更新本卡
lifecycle（IMPLEMENTED@sha → MERGED@sha → READBACK → ACCEPTED）。
