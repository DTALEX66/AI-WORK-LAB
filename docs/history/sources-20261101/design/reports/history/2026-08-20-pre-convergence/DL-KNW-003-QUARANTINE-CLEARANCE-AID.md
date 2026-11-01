# 隔离来源人工补全辅助清单（DL-KNW-003 / DL-AST-001，2026-08-17）

> 目的：把 162 条隔离来源的补全工作分组，便于逐批人工审核（author/权利标志/reviewedBy）。

## 规模

- 隔离总数：162 条（QUARANTINE_REGISTRY.json）
- 按缺失字段分组：

| 缺失字段 | 数量 |
|---|---|
| author,allowedUsage,version(40-hex-git-sha),acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse,reviewedBy,reviewedAt | 87 |
| author,allowedUsage,version(40-hex-git-sha),acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse | 37 |
| author,allowedUsage,acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse,reviewedBy,reviewedAt | 26 |
| author,license,allowedUsage,acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse,reviewedBy,reviewedAt | 6 |
| author,license,allowedUsage,version(40-hex-git-sha),acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse,reviewedBy,reviewedAt | 5 |
| author,license,allowedUsage,version(40-hex-git-sha),acquiredAt,contentHash(sha256),redistributable,modelInputAllowed,commercialUse | 1 |

## 补全流程（每批）

1. 打开 QUARANTINE_REGISTRY.json，取一批（建议 10–20 条）
2. 补：author / license / commercialUse / modelInputAllowed / reviewedBy / reviewedAt
3. 运行 verify_source_registry.py 确认无 GOVERNANCE_GAPS
4. 将补全条目标记可出隔离 → 迁移到 SOURCE_REGISTRY（ACTIVE）

## 注意

- 不得批量自动签署权利（人工逐条）；
- 未核实的来源保持隔离（fail-closed）。
