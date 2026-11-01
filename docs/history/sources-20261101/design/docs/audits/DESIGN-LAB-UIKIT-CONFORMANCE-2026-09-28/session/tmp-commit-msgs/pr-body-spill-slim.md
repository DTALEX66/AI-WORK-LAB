## 范围

DESIGN-LAB 后续任务收口轮（本轮三项），分支 `chore/spill-census-after-hermes-slim`：

1. **任务① 合并审计分支**：`codex/design-lab-audit-20260922`（exact-SHA `abd3b51`，CI 9/9）经 PR #138 squash 并入 main `0c41175`，远端审计分支已删除。
2. **任务② 瘦身项目本体**：AGENTS.md 明令 `.hermes` 非活跃写入路径，本轮 241.57 MiB 运行数据违规写入 `.hermes/task-runtime`。用项目自带 `deepseek_hermes_migration.py`（copy→digest 校验→删源→恢复 manifest）把 99 个 DESIGN-LAB 自有 RUNTIME_STATE 对象迁至 `.project-local/archive/hermes-legacy/`。`.hermes` 241.8MB → 13KB（仅剩 Hermes 原生 `skill-call-index.json`，DO_NOT_TOUCH）。`--verify` PASS（109 对象）。
3. **任务③ 追踪外溢数据**：刷新 tracked `reports/current/SPILL-CENSUS.json`（迁移后 objects=1 / 0.01 MiB），`deepseek_spill_census.py --check` → SPILL_CENSUS=PASS（零漂移）。库索引交叉核验：`paths.json` 4 个 shared_inputs 根全指 `D:`，0 C:/E: 漂移。

## 改动面

- `reports/current/SPILL-CENSUS.json`：台账刷新（迁移后零 DESIGN-LAB 遗留外溢）
- `docs/handoffs/DESIGN-LAB-SPILL-SLIM-CLOSURE-2026-09-22.md`：新增交接（根因/处置/回滚/未证明边界/复核命令集）

## 证据（可独立复核）

```
python scripts/deepseek_spill_census.py --check    # SPILL_CENSUS=PASS
python scripts/deepseek_hermes_migration.py --verify  # MIGRATION_VERIFY=PASS
git ls-remote origin main                           # main=0c41175
```

## 回滚

- 瘦身迁移可逆：`python scripts/deepseek_hermes_migration.py --restore`
- 本 PR 为 docs/ledger-only，未合并时可直接删分支，无副作用。

## 未证明边界

- 本轮证据均为 digest/ls-remote/SPILL_CENSUS=PASS 级；未触及 E3 真实宿主 / E4 人工陪审 / E5 tag 发布。
- git-tracked 大块资产（32 文件 / 19.6MB evidence PNG/MP4/registry）经引用核验全部保留，未误删。
- `.venv` / `node_modules` / `.project-local` runtime 证据未删除（可再生或持久证据，非污染）。
