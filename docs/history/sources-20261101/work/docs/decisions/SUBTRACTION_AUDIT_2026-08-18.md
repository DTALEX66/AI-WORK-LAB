# WORK-LAB 减法审计（v5 分层 · 2026-08-18）

> 目的：按 v5 分层（WORK-LAB = 控制平面 + 转化器，不存知识）盘点现有资产，区分阶段 1 自有与阶段 2 逆向归档候选。

## 1. 结论概要

WORK-LAB 现有资产几乎全部是控制配置 + 可执行技能/规则（已转化沉淀的产物），阶段 1 归 WORK-LAB 自有（保留）。WORK-LAB 本质上没有行业知识/模板/案例本体（40-knowledge 只是知识索引边界），无需立即删除知识。

## 2. 资产分类 inventory

### A. 控制配置（阶段 1 自有，保留，非知识）
- AGENTS.md 规则（根 + 10-workflow + 30-observer）：执行规则
- 治理规则（00-governance/rules/：asset-routing / instruction-precedence / release-policy）
- 工作流配置（10-workflow/workflow-assistance/config/：config-ownership / adapter-registry / skill-provenance / capability-matrix 等）
- 知识边界（40-knowledge/README：知识索引边界，无知识本体）

### B. 可执行技能/规则（阶段 1 自有保留，阶段 2 逆向归档候选）
- 项目技能 .agents/skills/：1 个
- 工作流技能 10-workflow/workflow-assistance/skills/：44 个
- Codex 技能 codex-assets/skills/：17 个
- Codex 规则 codex-assets/rules/ + global-guidance

### C. 证据/执行数据（非知识，不归档）
- 任务台账/证据：.hermes/task-runtime/（canonical.sqlite 等）
- 观测数据：.hermes/task-runtime/agent-observability/

## 3. v5 阶段归属

- 阶段 1（现在）：A 类 + B 类全部归 WORK-LAB 自有，照常使用
- 阶段 2（OS 完整后）：B 类的知识定义（技能 SKILL.md 方法/规则内容）逆向提炼归档 ArcheAxis；A 类中可提炼的规则知识同样逆向归档
- 无需立即删除任何内容

## 4. 逆向归档候选（阶段 2 触发）

1. 技能知识定义：62 个 SKILL.md（.agents 1 + 10-workflow 44 + codex-assets 17）逆向提炼为 Machine Knowledge Unit
2. 规则知识：AGENTS.md + 00-governance/rules 逆向提炼为 Knowledge Unit
3. 触发条件：ArcheAxis H1 merge + candidate 到 verified 闭环 + 稳定知识 API 契约

## 5. 后续建议

- WORK-LAB 保持减法：不新增知识内容，只做控制配置 + 技能 + 治理
- 新产生的知识在 ArcheAxis 归档（阶段 2 后），不再沉淀到 WORK-LAB