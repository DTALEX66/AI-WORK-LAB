# DL-MIG-000 — Freeze 基线记录

- 任务：DL-MIG-000 Baseline snapshot（阻断一切广泛改动前）
- 状态：✅ 完成（记录可独立 readback）

## 基线事实

- **源 main SHA**: `f8664ee24ea7d373d6a1a0056387fef47d3f99ab`（迁移前基线）
- **迁移后 main SHA**: `58030f9700f520c9bebd0f5644be1dea1ee01ee3`（PR #17/#18/#19 合并后）
- **工作树**: clean（迁移各批次提交后均 clean）
- **回滚点**: `f8664ee`（迁移前），`5c4fe55`（R3 迁移完成），`5b8a0f2`（KN 批次1），`d74ce44`（批次2），`58030f9`（批次3）
- **原路径清单**: `opendesign-assistance/`（427 文件，经 git mv 至 `design-lab/`，历史可追踪）

## 分支纪律

- main 受保护：全部改动经 feature 分支 + PR + squash merge
- 迁移分支：`dl/migration-r3`（已合并删除）、`feat/knw001-*`（已合并删除）
- 无直接 main 写入

## 验证

- `git rev-parse HEAD` == `origin/main`（双端一致）
- 每批 `git diff --check` + 旧名扫描 + verify_design_lab
