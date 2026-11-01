# DESIGN_KNOWLEDGE_ROLE_MAP（TP-20260819 DL-P0-002）

> 知识角色重分类：权威可复用 → ArcheAxis；只读投影 → 非权威；编译 Domain Pack → DESIGN-LAB。

| knowledge 目录 | 文件数 | 角色 | 处置 |
|---|---|---|---|
| curated | 1 | 权威可复用（DESIGN-LAB 保留） | 阶段2按联邦决策逆向归档 ArcheAxis |
| derived | 1 | 权威可复用（DESIGN-LAB 保留） | 阶段2按联邦决策逆向归档 ArcheAxis |
| ecommerce-ai | 223 | 只读投影 | 阶段2按联邦决策逆向归档 ArcheAxis |
| governance | 5 | 权威可复用（DESIGN-LAB 保留） | 阶段2按联邦决策逆向归档 ArcheAxis |
| methods | 1 | 权威可复用（ArcheAxis 候选） | 阶段2按联邦决策逆向归档 ArcheAxis |
| production | 36 | 编译规则（Domain Pack 对齐） | 阶段2按联邦决策逆向归档 ArcheAxis |
| registries | 1 | 只读投影 | 阶段2按联邦决策逆向归档 ArcheAxis |
| sources | 18 | 权威可复用（ArcheAxis 候选） | 阶段2按联邦决策逆向归档 ArcheAxis |
| standards | 9 | 权威可复用（ArcheAxis 候选） | 阶段2按联邦决策逆向归档 ArcheAxis |
| typography | 1 | 编译规则（Domain Pack 对齐） | 阶段2按联邦决策逆向归档 ArcheAxis |
| visual-quality | 1055 | 编译规则（Domain Pack 对齐） | 阶段2按联邦决策逆向归档 ArcheAxis |

## 处置原则

- 权威可复用 → 阶段2（ArcheAxis OS 成熟后）逆向归档；当前阶段1保留 DESIGN-LAB
- 只读投影 → 明确非权威，不作为运行时证据
- 编译 Domain Pack → 保持 DESIGN-LAB（domain-packs 12 个已编译）
- 依赖图：knowledge 被 domain-packs/quality/scripts 引用；无循环依赖

