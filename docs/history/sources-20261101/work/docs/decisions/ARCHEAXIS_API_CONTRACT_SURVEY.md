# ArcheAxis API 契约调研（阶段 2 逆向归档准备 · 2026-08-18）

> 目的：为 v5 阶段 2（ArcheAxis 完整后，WORK-LAB/DESIGN-LAB 逆向归档知识）调研 ArcheAxis 现有知识 API 形态。来源：ArcheAxis 本地源码（app/facades/ + README 端点）。

## 1. 现有 API 形态（已核实）

### Facade 接口（app/facades/）
| Facade | 接口 | 用途 |
|---|---|---|
| knowledge.py | query_knowledge（KnowledgeQueryResult / KnowledgeHit）| 知识查询（读） |
| research.py | ingest_candidate（ResearchIntakeResult）| 候选摄入（写，回写归档）|
| research.py | research_github_repository / get_research_package | GitHub 仓库研究摄入 |
| research_runtime.py | run_reviewed_artifact_task（ArtifactRuntimeResult）| 受治理工件任务 |

### HTTP 端点（README 核实）
| 端点 | 用途 |
|---|---|
| POST /kb/pipeline | 提取/标签/摘要/事实候选 |
| POST /kb/search | 关键词/向量/混合检索 |
| POST /run | route 到 retrieve 到 plan 到 permission 到 tool 到 evaluation 到 lesson（受限执行 tracer）|
| POST /research/github-repository | GitHub 研究摄入 |
| GET /health /diagnostics | 健康/诊断 |

## 2. 与阶段 2 逆向归档的对应

| 阶段 2 动作 | 对应 API |
|---|---|
| WORK-LAB 技能知识（SKILL.md 提炼）提交归档 | ingest_candidate 或 /kb/pipeline |
| 规则知识（AGENTS.md/rules 提炼）提交归档 | ingest_candidate 或 /kb/pipeline |
| 归档后查询验证 | query_knowledge 或 /kb/search |
| 双向学习闭环（经验回写）| /run 的 lesson 环节 + ingest_candidate |

## 3. 阶段 2 缺口（需要 ArcheAxis 侧补充）

1. Machine Knowledge Unit 写入 API（当前 facade 未暴露专门的 machine knowledge 写入口，需确认）
2. Candidate 提交的批量/结构化接口（逆向归档 62 个 SKILL.md 需要批量）
3. 明确的验证/回读契约（归档成功可回读确认）
4. 鉴权/API key 约定（ArcheAxis 生产模式需要 COGNITIVE_API_KEY）

## 4. 结论

ArcheAxis 已具备阶段 2 逆向归档的基础（ingest_candidate 写 + query_knowledge 读 + /kb/pipeline 摄入），但需补充 Machine Knowledge Unit 批量写入与验证契约。阶段 2 触发条件：H1 merge + candidate 到 verified 闭环 + 本调研的缺口补全 + 稳定 API 契约。

## 5. 后续

- 阶段 2 前与 ArcheAxis 协调补全缺口（Machine Knowledge Unit 写 API + 批量 Candidate + 验证契约）
- 逆向归档流程模板（下一个任务）将基于本调研设计