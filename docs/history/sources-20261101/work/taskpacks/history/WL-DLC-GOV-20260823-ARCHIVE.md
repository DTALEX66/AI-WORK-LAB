# WL-DLC-GOV-20260823 任务包原文归档

> DESIGN-LAB 反馈：原任务包从工作区消失。此文件归档任务包原文（来自 2026-08-23 交接）。
> 任务包 ID：WL-DLC-GOV-20260823，发起方 DESIGN-LAB，执行责任方 WORK-LAB。
> 完整任务包内容见 2026-08-23 交接（目标/架构边界/证据基线/任务 DAG/批准门 G0-G4/测试矩阵/回滚）。

## 核心要点（归档）

1. 目标：DSH 规则回收 + Codex 覆盖层去漂移 + DESIGN-LAB 独立所有权 + DSH 适配器事实化 + 技能索引/漂移基线 + 四类证据关单
2. 批准门：G0 只读 / G1 跨仓库写入 / G2 sync apply（plan_digest）/ G3 发布 / G4 合并
3. 关键边界：WORK-LAB 治理控制面、DESIGN-LAB 设计能力 IGNORE、用户配置保留、凭据边界
4. 任务 DAG：000 预检 → 010 取证 → 020 吸收 → 030 apply → 040 DESIGN-LAB → 050 索引/基线 → 060 DSH 适配器 → 065 worktree → 070 行为探针 → 080 交付

## 执行状态（2026-08-24 核验）

- 000/010/020/040/050/060/065 完成
- 030 sync apply：verify PASS（历史回读）
- 070 行为探针：NOT EXECUTED
- 080 G4 merge/CI：NOT EXECUTED