# 全局配置开销审计（2026-08-23）

> 用户反馈：项目执行费劲——动不动构建版本、动不动跑全量审计。
> 审计 WORK-LAB 管理的全局规则/配置，定位开销源 + 精简建议。

## 1. 审计发现（实测数据）

| 开销源 | 实测 | 问题 |
|---|---|---|
| Hermes skills 规模 | 82 个文件 / 866KB | 基线④要求 skills <10KB each、guidance+rules <20KB total——超 43 倍；每次会话加载/评估负担巨大 |
| 测试规模 | 111 个 test 文件（983 tests）| 每次全量审计跑 2 分钟+；other 类 92 个文件是大头 |
| 质量门数量 | run_quality_gate 10+ Gate（governance/compile/skill-provenance/security/context-pack/core-schemas/adapter-registry/capability-matrix/context-control-plane/external-libraries-index）| 每次 verify 全跑——变更一处也要全量 |
| 构建版本检查 | bundle-skew：桌面每次启动检测 install-stamp vs HEAD | 源码 main 天天前进（官方 update 频繁）→ exe 跟不上 → 频繁构建过旧警告 |
| 五维基线 | mandatory + audited | 每次变更全维度审计负担 |
| CI | work-lab-gate.yml 单 gate 全量（111 测试 + observer JS + cargo）| 每次 push 全跑几分钟 |
| 全局规则量 | AGENTS.md：五维基线 + 单写者 + 只读 + 审批 + 审计 | 执行方（Codex）遵守成本高 |

## 2. 根因分析

1. skills 失控：吸收归档（192 skills）后 Hermes 侧 skills 膨胀到 866KB——超出基线④设计上限
2. 全量一刀切：质量门/CI/审计都是全量跑——没有按变更域分层（改一个文件也跑全部）
3. 构建检查过频：bundle-skew 每次启动检测源码 HEAD 前进（官方 main 高频更新）→ 频繁误报
4. 规则叠加：单写者+只读+审计+批准 叠加 → 每次执行多个约束

## 3. 精简建议（按收益排序）

### A. Hermes skills 瘦身（收益最大）
- 82 个 skills → 精简到 ~20 个核心（每 <10KB）
- 其余归档到 40-knowledge（已归档 192 个，本地只留激活集）
- 立即减会话加载负担

### B. 测试/质量门分层
- 快速层（<30s）：变更模块相关测试 + smoke（每次变更跑）
- 全量层（nightly/合并前）：111 测试 + 全 gate（不每次跑）
- 质量门支持 --module 参数（只跑相关 gate）

### C. 构建版本检查降噪
- bundle-skew：源码前进但 exe 未重建 → 降为提示级（不阻塞启动/使用）
- 仅在跨版本差异大时警告（如 tag 变化）

### D. 五维基线按需审计
- 变更触发相关维度（入口变更→①、配置变更→③），不每次全维度

### E. CI 分层
- PR/快速路径：仅变更模块测试（约1min）
- main 合并：全量（现状）

### F. 规则精简（配合并行框架）
- 单写者 → 路径所有权（提案中）——减少互等
- 审计合并集中到落地前（不是每次提交）

## 4. 立即可以做（不改规则）

1. Hermes skills 瘦身（82到约20核心）
2. 质量门加 --module（按变更域跑）
3. bundle-skew 降提示级（配置）

## 5. 状态

- 审计完成（数据实测）
- 精简建议待用户选择执行项