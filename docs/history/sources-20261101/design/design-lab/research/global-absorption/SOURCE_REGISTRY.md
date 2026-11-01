# Source Registry（v3）与 Quarantine 摘要

- 快照：2026-08-16（DL-KNW-003 迁移）
- 登记格式：`design-lab/source-registry/v3`（每条 = 标准 SourceRecord + integration 元数据）
- 隔离格式：`design-lab/quarantine-registry/v1`

## 当前状态（fail-closed）

| 类别 | 数量 |
|---|---:|
| 遗留登记总数（迁移前） | 162 |
| ACTIVE（可进入能力加载/模型上下文） | 0 |
| REFERENCE_ONLY | 0 |
| QUARANTINE（缺少任一必需事实） | 162 |

> 162 条遗留登记逐条迁移至 QUARANTINE_REGISTRY.json：每条保留原始记录（`originalRecord`），记录 `missingFields` 与 `reason`。在人工补齐 author/allowedUsage/acquiredAt/contentHash(sha256)/权利标志/审核人之前，任何来源都**不得**进入能力加载、模型上下文或标记 reviewed。不批量制造字段，不伪造审核人/许可/版本/哈希。

## 主要缺口统计（DL-KNW-003-SOURCE-MIGRATION.json）

- 缺许可证（UNVERIFIED/REFERENCE-ONLY）：12
- 缺审核人（reviewedBy）：124
- 缺完整版本（git 来源非 40 位 SHA）：130
- 缺 SHA-256（contentHash 非 `sha256:<64hex>`）：162
- 允许模型输入：0（未记录）
- 允许商用：0（未记录）

## 相关文件

- `SOURCE_REGISTRY.json` — v3 活动登记（当前为空，等待人工审核提升）
- `QUARANTINE_REGISTRY.json` — 隔离登记（162 条，含原始记录）
- `design-lab/schemas/source-record.schema.json` — 唯一来源对象
- `design-lab/schemas/source-registry.schema.json` — v3 登记 schema（$defs.sourceRecord = $ref）
- `design-lab/schemas/quarantine-registry.schema.json` — 隔离登记 schema
- `design-lab/scripts/verify_source_registry.py` — 严格验证器（DL-KNW-004）
