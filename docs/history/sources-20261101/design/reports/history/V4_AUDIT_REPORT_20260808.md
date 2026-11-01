# 项目审计报告（Audit Report）— 2026-08-08

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


## 审计范围
- 仓库：`D:\All projects\DESIGN-LAB` @ `migration/work-lab-minigame-cutover-20260807`
- 基线 HEAD：`5744b3f`（main = migration = 云端一致）
- 维度：Git 一致性、验证链、CI、测试、安全、文档、体积

## 发现与修复

### ✅ P0 — V4 Canonical CI 红（已修复，2 个提交）
**症状**：`Canonical Verify (V4)` 在 main/migration 上 FAIL，V2/V2.1 绿。
**根因 1**：`configure_open_design_windows.py` 在 SECURITY_BLOCK 宽根守卫**之前**调用 `find_codex_bin()`。CI runner 无 Codex CLI → 脚本在守卫前退出，安全测试断言 `SECURITY_BLOCK` 失败。
**修复 1**（`52a6894`）：安全边界前置（fail-closed），Codex 探测移到守卫后；dry-run 容忍无 Codex（仅 `--apply` 强制）。`test_user_home_blocked` 改用 `Path.home()`（跨机器自洽）。

**根因 2**：Windows 专用脚本的路径语义测试（`E:\`、`D:\All projects`）在 `ubuntu-latest` runner 上被解析为相对路径，SECURITY_BLOCK 不触发。
**修复 2**（`5744b3f`）：CLI 路径测试加 `@skipUnless(sys.platform == "win32")`，仅在 Windows 运行。

**验证**：修复后 V4 CI 全部 4 job 绿（Python/Node/License-secret/Generated-artifact），V2/V2.1 绿，双端 `5744b3f` 一致。

### ✅ 清理
- `__pycache__` 清除（测试后的可再生缓存）

### ℹ️ 保留（设计合理，非问题）
- `.hermes/` 证据目录（ignored，不上传）
- 构建生成物（android/wechat/douyin 的 audio/visual，ignored，由 build 重建）
- V3 历史文档引用（PROJECT_DEFINITION_V3 等，历史兼容 + verifier 强制引用）
- `.git` 186M（历史已瘦身，含保留的合法游戏资产）

## 最终验证链（全绿）
```
VERIFY_RESULT=OK total=456 failed=0
Python: 42/42
Node:   321/321
drift:  OK
V4 CI:  4/4 jobs success (main + migration)
```

## 边界遵守
- 无 E:\、无凭据、无破坏性历史操作
- P0 修复均为根因级，非掩盖
- 双端 exact-SHA 一致（`5744b3f`）

## 遗留待办（非缺陷）
- ODA4-0304（UI/UX E3）：依赖 0401/0404/0501/0902（后续阶段），当前无法独立执行
- ODA4-0305：依赖 0304
- ODA4-0306：依赖已满足（0206+0302），可推进
