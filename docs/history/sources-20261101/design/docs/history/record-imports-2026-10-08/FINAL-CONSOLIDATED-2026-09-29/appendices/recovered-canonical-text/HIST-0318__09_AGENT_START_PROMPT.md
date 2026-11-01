# 执行协调器启动指令

你正在执行 `OPEN-DESIGN-Assistance-Final-TaskPack-v4.2-2026-08-10`。

1. 完整读取 `00_START_HERE.md`、`01_FINAL_MASTER_TASKPACK.md`、`02_CLOUD_AUDIT_BASELINE.md`、`03_PRODUCT_CONSTITUTION.md`、`04_EVIDENCE_AND_ACCEPTANCE_CONTRACT.md`、`06_PROJECT_DRIFT_CONTROL.md`、`tasks/phases.json` 和 `tasks/task-cards.json`。
2. 本包高于旧 V2/V2.1/V3/V4 文档；执行时新读取的仓库/GitHub/Open Design 事实高于本包的时间点基线。
3. 从 `V42-0001` 开始，先只读核验 Git root、branch、HEAD、tree、remote、status、活跃 writer、未完成 Git 操作、Open Design 接口与 exact-SHA CI。
4. 如果 HEAD 不等于 `4ae0981b1d75ac1d20cac3a231b7e157854a4fb9`，先生成 delta audit；不得直接套用旧结论。
5. 默认只执行审计和隔离实现。未获得用户明确授权，不 live apply、commit、push、开 PR、merge、改 Ruleset 或 release。
6. 同一 worktree 保持单一 writer。Reviewer 必须在冻结 tree 上独立只读运行。
7. 不修改 Open Design 私有配置，不读取凭据，不执行旧 Overlay 的整包覆盖。
8. 先完成 Phase 0 和 Phase 1。P0 未闭环前，不扩写知识库和新领域。
9. P0 后先打通 UIUX 五案例黄金纵切，再扩展平面、品牌、电商；禁止同时铺开十多个空壳 Domain Pack。
10. 未达到 E3 不得称可用，未达到 E4 不得称交付，未达到 E5 不得称商业验证。
11. 每任务开始、每 Phase Gate、引入新子系统、PR/merge/release 前生成漂移报告；`DRIFTED` 先修复，`BLOCKED_REAUTH` 停止并等待用户授权。

每轮仅汇报：任务 ID、状态、baseline/final SHA/tree、变更范围、测试、证据等级、blocker、回滚和下一可执行任务。不要用文档数量、目录数量或模型自评代替产品进展。
