# WORK-LAB Observer 3.0 路线图（OBSERVER_3_ROADMAP）

> 2026-08-16 · 战略文档 · 基于真实基线核验
> 云端 main：`fadcded4c4db`（protected=true）· 本地 HEAD 一致 ✅
> 依据：Observer 3.0 云端审计方案 + 本会话 CC2 已交付 + 后端 execution 模型实测

## 1. 战略判断（一句话）

WORK-LAB Observer 的正确演进是：**从 Project-centric Dashboard 升级为 Execution-centric AI Workflow Control Plane**，
而不是继续做 fusion-v4 页面拼装、也不是 Fork SigNoz/Langfuse/Grafana。

## 2. 关键事实（决定路线可行性的实测结论）

| 事实 | 实测 | 含义 |
|---|---|---|
| 后端 execution 模型 | `execution_instances`/`agent_instances`/`sessions`/`execution_evidence` 表已存在 | ✅ Execution 是既有实体，非从零建 |
| 字段完整性 | execution_id+agent+session+anchor_project+state+heartbeat+evidence 关联 | ✅ 足够支撑 Trace/Waterfall |
| 当前数据量 | execution/agent/session 表均 **0 行** | ⚠️ 缺真实采集，UI 做了也是空的 |
| snapshot 投影 | 已含 `executions` 字段，但**无 spans/events/measurements** | 投影模型需升级 V3 |
| Truth boundary | api.js/state.js 冻结（GET-only/loopback/last-good/fail-closed） | ✅ 最值钱资产，必须保留 |
| 前端现状 | CC2 已收敛重复项目视图，但仍是 Project-centric | 需向 Execution-centric 迁移 |
| 云端保护 | main protected=true（你方案里的 5fc107b/protected=false 已过时） | ✅ 已解决 P1 治理风险 |

## 3. 三阶段路线图

```
阶段1（已完成✅）          阶段2（P0 下一步）              阶段3（P1）
视觉收敛                  Projection V3 + View Model      Execution-centric UI
─────────────────       ─────────────────────────       ─────────────────
CC2: 消除重复项目视图     后端: snapshot 加 Span/         五入口 IA:
  统一状态 token          Event/Measurement 投影          Overview/Executions/
  6 层级 IA             前端: model/selectors.js          Projects/Delivery/Trust
  Truth-first             + freshness.js + view-model    Execution 一等公民
                        关键: execution 表接线           Trace waterfall
                        （解决 0 行问题）                删残留项目重复
```

## 4. 阶段 2 详细步骤（P0，下一步执行）

### Step 2.1 — Gate Zero 审计（锁定基线 + 完整证据）
```
输入: main@fadcded（已锁定，protected=true）
产出: docs/observer/OBSERVER_3_BASELINE.md
       docs/observer/CSS_CURRENT_INVENTORY.md
任务: 枚举全部 remote 分支 ahead/behind
       枚举 open PR + main check-runs
       inventory .project/governance/10-workflow/30-observer
       提取 CSS token + 硬编码色
       对比上传前端 blob 与 main SHA
```

### Step 2.2 — Truth Contract 冻结（先写回归测试）
```
冻结: api.js / state.js / LIVE validation / snapshot validation
新增测试: unknown≠0 / stale≠live / offline≠fixture /
          failed-refresh 保留 last-good / 非 loopback 拒绝
```

### Step 2.3 — Projection V3（后端 schema 升级）
```
新增实体: Span / Event / Measurement / Resource / DataQuality
Execution 已是实体，加: spans[] + measurements[] + reasonCodes[]
安全: Span.attributes allowlist-only（禁 prompt/response/secret）
关键: 保留 V2 schema，加 compatibility adapter
```

### Step 2.4 — execution 数据源接线（解决 0 行）
```
问题: execution_instances 0 行 = collector 未采集真实执行
行动: workflow 侧 executor 写 execution_instances
      DSH/Hermes/Codex 真实 run → execution_id + agent + state + heartbeat
      若无可靠 correlation key → 标 uncorrelated，不靠时间猜
```

### Step 2.5 — Frontend View Model（消除 renderer 重复）
```
新增: web/scripts/model/selectors.js（canonical 状态映射）
       web/scripts/model/freshness.js（per-source age）
       web/scripts/model/view-model.js（raw → UI model）
目标: renderer 不自行定义业务规则，统一走 selectors
```

## 5. 阶段 3 详细步骤（P1）

### Step 3.1 — 五入口信息架构
| 入口 | 回答 | 数据源 |
|---|---|---|
| Overview | 3秒判断: live/active/attention/project/recent | 全局 + 活跃执行 |
| Executions | 谁在做、哪一步、为什么卡住 | Execution+Span+Event |
| Projects | 静态上下文 + 当前事实 | project+git+delivery |
| Delivery | Git/CI/Artifact 统一 | git+ci |
| Trust | 数据可信度 + governance | freshness+coverage+evidence |

### Step 3.2 — Executions Trace Waterfall
```
Execution / exec_829
  Hermes   ████████
  Codex      ████████████
  Git              ██
  CI                 ████
  Selected span: Codex · RUNNING · evidence ev_9281
```

## 6. 禁止事项（红线）

```
不做 fusion-v4 页面拼装
不 Fork SigNoz/Langfuse/Grafana/ClickHouse
不重写 api.js/state.js
不引入 React/Vue（除非架构 gate 通过）
不引入 ECharts/Chart.js/D3（保持 native SVG）
UNKNOWN ≠ 0，stale ≠ live，无证据 ≠ healthy
Span.attributes allowlist，禁 prompt/response/secret
```

## 7. 风险与回滚

| 风险 | 控制 | 回滚 |
|---|---|---|
| Correlation 造假 Trace | 可靠 ID 才关联，否则 uncorrelated | 禁用 correlator |
| UI 破坏 last-good | truth 回归测试 | restore 冻结 state.js |
| Sensitive 泄漏 | allowlist + 负向 fixture | 关闭 span attribute |
| V3 schema 不兼容 | V2/V3 adapter | 切回 V2 renderer |

## 8. 六份交付物映射

| 交付物 | 状态 |
|---|---|
| WORK-LAB_OBSERVER_3_AUDIT_REPORT.md | 待 Gate Zero 补全（云端已核验 baseline=fadcded） |
| PROJECTION_SCHEMA_DIFF.md | 待 Step 2.3 产出 |
| UI_DESIGN_SPEC.md | 你方案已提供，落地时对齐 |
| TASKPACK_WL-OBS-3.0.yaml | 你方案已提供，baseline 更新为 fadcded |
| CHANGED_FILES_PROPOSAL.md | 待 Gate Zero 后细化 |
| VISUAL_VERIFICATION_PLAN.md | 待 Playwright/截图评估 |

## 9. 立即行动（下一步）

按序执行，每步可回滚：
1. **Gate Zero**：生成 OBSERVER_3_BASELINE.md + CSS_CURRENT_INVENTORY.md（锁定 fadcded 基线）
2. **Truth Contract**：先写回归测试，冻结 api/state
3. **execution 数据源接线**：让真实执行写进 execution_instances（解决 0 行）
4. **Projection V3**：snapshot 加 Span/Event/Measurement
5. **View Model**：selectors/freshness/view-model 三层
6. **五入口 UI**：Overview/Executions/Projects/Delivery/Trust

## 10. 结论

**不要再做 fusion-v4。** 正确的下一步是：以 Execution 为架构中心，以 Provenance/Freshness 为数据可信度基础，
以五入口 IA 为产品形态，以 quiet/precise/developer-grade 为视觉语言。
这样'数据准、结构对、布局稳、有质感'才会同时成立。
