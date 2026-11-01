# Quality Pipeline（DL D2）— 质量分层管道契约

> 分层：deterministic → visual-model → expert-agent → human-feedback。
> 纪律：层间证据等级递进（E1→E2→E3→E4）；**human calibration 不可由模型或静态自评替代**（DL-QLT-002）。

## 分层定义

| 层 | 角色 | 证据等级 | 工具 | 门禁 |
|---|---|---|---|---|
| deterministic | 确定性规则 | E1 | preflight / anti-slop / aesthetic-rules(metadata) | fail-closed：已知 blocker 100% 拦截 |
| visual-model | 视觉模型评估 | E2 | LAION / NIMA / Florence-2（provider E0 已声明） | 分数 ≥ profile minimum |
| expert-agent | 专家评审 | E3 | critique rubric / domain jury | 结构化评审记录 |
| human-feedback | 人类反馈 | E4 | 专业 Jury + 偏好测试（DL-QLT-002） | ≥82 分 + 偏好率 ≥70% |

## 关键 KPI

- FalsePassRate = 错误放行数 / 总放行数；生产 profile 目标 < 2%
- 模型层校准：与资深设计师评分相关性、false-pass/false-reject、同输入方差、跨 provider 一致性
- **不得**：单一多模态模型既生成又自评（AI judge 自我循环）；高置信 blocker 被加权平均覆盖

## 与现有资产的关系

- deterministic：verify_quality_gate / verify_production_preflight / verify_aesthetic_rules / check_anti_slop
- visual-model：config/provider-capabilities.json（E0 声明）→ 真实接入需 E2 取证
- expert/human：evals/benchmark-registry + 12 rubrics + evidence cards（12 卡待人工校准）

## 未达成声明

- visual-model 层当前为 E0（provider 已注册，未真实运行）——不得宣称 E2
- human-feedback 层未启动（DL-QLT-002 阻塞，需用户参与）
