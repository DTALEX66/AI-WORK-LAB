## 范围

DESIGN-LAB 仓库级防漂移审计收口轮，分支 `chore/drift-rebind-branch-audit-20260922`（基于 main `d9e2d46`）。用户授权"审计历史文档 + 各环节 + 分支审计合并 + 瘦身 + 追踪外溢"。

### 1. 消除投影漂移（核心交付，随本 PR 入库）
- #139 把 main 推过 8 个 tracked 投影记录点 → `generate_current_reports.py --check` 报 DRIFT。
- 处置：`generate_current_reports.py`（不带 `--check`）rebind → `CURRENT_REPORTS=PASS mode=generate`。
- 10 个投影文件（8 JSON + PROJECT_STATUS/CLOUD_BASELINE 的 .md + current-report-index）随本 PR 提交 = 该 rebind。
- 稳态：commit 后 `--check` 报 `STALE` 属 self-referential 预期（HEAD 已前进过记录点），**非产品失败**，不追 PASS、不手改 index（AUTHORITY §17）。

### 2. 46 远端分支 blob 级审计 + 清零（owner 已授权"分支审计合并"）
- 三层判定（`merge-base` 祖先 / `diff --diff-filter=A` 独有路径 / `log --find-object` blob 在 main 复验）：
  **24 纯残留 + 22 目录迁移挪位 + 0 真独有内容**；`gh pr list --state open` 为空（无悬挂依赖）。
- `git ls-remote origin refs/heads/*` 真值 **35 → 仅 `main`**（34 本轮删 + 先前 PR squash 时 GitHub 已自动删的 head 分支）。
- 删除前每轮 `GENUINE-unique guard = 0`；回滚 manifest（各 tip SHA）存 `.project-local/archive/hermes-legacy/branch-deletion-manifest-20260922.json`（gitignored，`git push origin <sha>:refs/heads/<branch>` 可恢复）。

### 3. 记忆漂移纠正（不照搬记忆）
- `model-radar.json` **非缺失**：实为 `design-lab/readiness/model-radar.json`（17 处引用），上轮 recon 查错路径。
- `paths.json` 4 外置库根（model-library/design-assets/os-toolchain/design-toolchain）全指 `D:`，**0 个 C:/E: 漂移**；`paths.py` junction/reparse 拒读在位。

## 证据（可独立复核）

```
python scripts/verify_top_level_authority.py         # 10/10 PASS
python scripts/verify_authority_gates.py --zero-spill  # 7/7 PASS
python scripts/generate_current_reports.py --check   # 稳态 STALE（预期，非失败）
git ls-remote origin 'refs/heads/*'                   # 仅 main
```

## 未证明边界

- 本轮 E1/E2（门链 live PASS、投影 rebind、blob 分支审计、外溢 digest、远端分支 35→1）。
- **未触及 E3 真实宿主 / E4 人工陪审 / E5 真实 tag 发布**（本轮不做发布与宿主验证）。

## 回滚

- 本 PR = docs + 投影 rebind，未合并时直接删分支即可；远端 46 分支已删，需恢复用 manifest 的 tip SHA。
