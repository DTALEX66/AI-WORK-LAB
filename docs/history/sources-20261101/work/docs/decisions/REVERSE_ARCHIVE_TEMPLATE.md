# 逆向归档流程模板（阶段 2 · 规则/技能/插件 → 知识 → 归档 ArcheAxis）

> 用途：v5 阶段 2（ArcheAxis 完整后），WORK-LAB/DESIGN-LAB 将现有可执行资产（规则/技能/插件）逆向提炼为知识，归档 ArcheAxis 治理。

## 1. 触发条件（全部满足才执行）

1. ArcheAxis H1 后端已 merge
2. candidate 到 review 到 verified 治理闭环完整可用
3. 知识 API 契约稳定（含 Machine Knowledge Unit 批量写入 + 验证回读）
4. 本模板评审通过

## 2. 流程（每个资产重复）

### 步骤 1：资产清点
- 输入：WORK-LAB 62 个 SKILL.md（.agents 1 + 10-workflow 44 + codex-assets 17）+ AGENTS.md + 00-governance/rules
- 输出：资产清单（路径、类型、用途、知识含量）

### 步骤 2：知识提炼（资产 → 知识）
- 从每个 SKILL.md/规则提取可复用知识：方法、规则、约束、示例、决策逻辑
- 输出：KnowledgeUnitDraft（标题、内容、来源资产、领域标签、证据）
- 原则：提炼知识定义，不含可执行代码（代码作为机器资产留在项目）

### 步骤 3：候选提交（知识 → Candidate）
- 调用 ArcheAxis ingest_candidate 或 /kb/pipeline 提交为 Candidate
- 批量提交（62 个技能 + 规则）
- 输出：candidate IDs + 提交回执

### 步骤 4：治理等待（Candidate → verified）
- ArcheAxis 人工审核 + 来源独立性验证
- 未升级的 candidate 保留等待，不自动成为事实

### 步骤 5：验证与回读
- 归档成功后，用 query_knowledge 回读验证（按 candidate ID 或领域标签）
- 输出：归档验证报告（数量、状态、回读命中）

### 步骤 6：项目侧调整
- 知识已归档的资产：项目保留可执行载体（技能继续用），标注知识源头
- 项目不再重复维护知识定义（引用 ArcheAxis）

## 3. 产出物

- 资产清单（步骤 1）
- 知识提炼草稿库（步骤 2）
- 归档验证报告（步骤 5）

## 4. 质量控制

- 只归档知识定义，不归档凭据/密钥/私有数据
- 来源可追溯（每个 KnowledgeUnitDraft 记录来源资产路径）
- 验证用真实回读（非自述）