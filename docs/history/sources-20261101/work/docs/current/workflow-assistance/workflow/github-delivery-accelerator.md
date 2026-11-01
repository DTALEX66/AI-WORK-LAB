# GitHub 交付加速器（GitHub Delivery Accelerator）

> 2026-08-16 · workflow-assistance 增强 · 凭据走 git credential（不硬编码）
> 目的：加速各项目上传 GitHub + 强化上传审核速度

## 1. 上传加速（github_upload_accelerator.py）

一键完成：状态检查 → 提交（规范化 message）→ 推送 → 可选 PR。

```bash
# 全部托管仓库（WORK-LAB/DESIGN-LAB/ArcheAxis/Obsidian/OS External）状态体检
python packages/client-neutral-core/scripts/github_upload_accelerator.py

# 单仓库提交+推送（自动加 conventional 前缀）
python packages/client-neutral-core/scripts/github_upload_accelerator.py --repo WORK-LAB -m "feat: add dashboard"

# 只提交不推送（安全预览）
python packages/client-neutral-core/scripts/github_upload_accelerator.py --repo DESIGN-LAB -m "docs: fix readme" --no-push
```

**安全设计**：
- 无 -m 时 **DIRTY_NO_ACTION**（只报告，绝不 add/commit/push）
- 不 force-push；message 自动前缀 feat/fix/docs/chore
- 输出 JSON 报告（status/steps/commit/push）

## 2. 审核加速（github_review_accelerator.py）

一键聚合 PR 审核信号：mergeable + checks + 本地 gate → 建议 APPROVE/BLOCK。

```bash
python packages/client-neutral-core/scripts/github_review_accelerator.py --repo DTALEX66/WORK-LAB --pr 118
# 输出: mergeable/mergeable_state/checks/local_gate/recommendation/reasons
```

**判定逻辑**（全部满足才 APPROVE）：
- mergeable = true 且 mergeable_state = clean
- 所有 check-runs success/neutral/skipped
- （WORK-LAB）本地 QUALITY_GATE_PASS

**审核加速点**：一次调用拿到全部审核信号 + 理由，不用逐项查 CI/冲突/本地门禁。

## 3. 共享层（github_common.py）

- `credential()`：git credential fill 取 token（安全，不硬编码）
- `request()`：GitHub REST API（Bearer auth）
- `MANAGED_REPOS`：5 个托管仓库清单（本地路径 ↔ owner/repo）

## 4. 托管仓库清单

| local | GitHub repo |
|---|---|
| WORK-LAB | DTALEX66/WORK-LAB |
| DESIGN-LAB | DTALEX66/DESIGN-LAB |
| ArcheAxis-Knowledge-OS | DTALEX66/ArcheAxis-Knowledge-OS |
| Obsidian-Assistance | DTALEX66/Obsidian-Assistance |
| OS External Configuration | DTALEX66/OS-configuration |

## 5. 验证

```bash
python services/orchestration/run_quality_gate.py github-delivery   # 12 测试（离线）
python services/orchestration/run_quality_gate.py verify            # 37 gates
```
