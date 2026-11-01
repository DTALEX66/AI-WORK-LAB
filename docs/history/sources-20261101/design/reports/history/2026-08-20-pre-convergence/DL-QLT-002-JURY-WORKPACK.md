# 人工专业 Jury 评分工作包（DL-QLT-002 准备材料，2026-08-17）

> 目的：为 E4 发布链的人工验收准备索引（评分需你执行，本包不代替评分）。

## 验收标准

- 五域专业评分 ≥82/100；偏好测试 ≥70%
- 12 证据卡人工校准；FalsePassRate 目标 <2%

## 评分材料索引

| 材料 | 路径 | 数量 |
|---|---|---|
| Benchmark briefs | design-lab/evals/benchmarks/ | 12 |
| Rubrics | design-lab/evals/rubrics/ | 19 |
| Evidence cards | design-lab/evals/evidence/evidence-cards.json | 12 |
| 评分单模板 | design-lab/evals/templates/score-sheet.template.json | 1 |

## Evidence cards（待人工校准）

- `evidence-layout-hierarchy`
- `evidence-typography-system`
- `evidence-color-logic`
- `evidence-material-credibility`
- `evidence-lighting-motivation`
- `evidence-spatial-coherence`
- `evidence-motion-pacing`
- `evidence-interaction-feedback`
- `evidence-accessibility-readability`
- `evidence-cross-format-coherence`
- `evidence-originality-non-imitation`
- `evidence-production-readiness`

## 执行步骤（需你）

1. 打开评分单模板，逐卡评分（按 rubric 维度）
2. 汇总五域分数（≥82）
3. 偏好测试（≥70%）
4. 结果写入 evals/evidence/ 并标记 human_calibrated
