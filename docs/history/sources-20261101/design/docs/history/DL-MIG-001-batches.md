# DL-MIG-001 — 迁移分支与变更批次清单

- 任务：DL-MIG-001 Migration branches and batch plan
- 状态：✅ 完成（批次全部合并）

## 批次清单

| 批次 | 分支 | 内容 | 验证 | 回滚 |
|---|---|---|---|---|
| J0-J2 | dl/migration-r3 | 身份迁移 R3（目录/SSOT/契约/MiniGame fixture） | verify_design_lab + 96 tests | f8664ee |
| J3-J5 | dl/migration-r3 | evidence index + identity gate + schema 补齐 | 同上 | 5c4fe55 |
| 自检修复 | fix/selfcheck-r3 | 6 schema + CI 工作流归档 | CI 4 gate | 5c4fe55 |
| KN 批次1 | feat/knw001-absorption | 4 设计 SKILL vendoring | CI 4 gate | 5b8a0f2 |
| KN 批次2 | feat/knw001-batch2 | 动效×2 + shipit-ui | CI 4 gate | d74ce44 |
| KN 批次3 | feat/knw001-batch3 | design-checklist + tokens 候选 | CI 4 gate | 58030f9 |

## 规则

- 每批有目标、影响、验证、回滚 SHA
- 禁止"大爆炸"重命名提交（全部小步）
