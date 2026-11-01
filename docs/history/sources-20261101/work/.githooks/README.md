# .githooks — WORK-LAB 本地 Git hooks

## 启用（每个 clone 一次）

```bash
git config core.hooksPath .githooks
```

## pre-commit：自动同步 CURRENT_STATE

- 提交时自动检测 tracked 改动 → 重生成 CURRENT_STATE（digest）→ stage
- **效果**：不再需要手动 `python scripts/ci/generate_current_state.py --root .`
- 跳过：`git commit --no-verify`（需显式理由，不推荐）

## 为什么

手动重生成 CURRENT_STATE 是哈希噪音来源（每次改 tracked 文件都要跑）。
此 hook 把重生成自动化到提交环节，开发者无感，main digest 不再 stale
（#58 根因：只改 ledger 未重生成 → 下游 PR CI 全挂）。
