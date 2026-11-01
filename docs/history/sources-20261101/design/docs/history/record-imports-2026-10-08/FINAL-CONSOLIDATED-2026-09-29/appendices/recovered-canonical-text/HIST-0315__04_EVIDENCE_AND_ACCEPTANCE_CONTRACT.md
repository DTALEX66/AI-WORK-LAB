# 证据与验收合同

## Evidence Record 必填字段

`capability_id`、`task_id`、`status`、`evidence_level`、`repo_sha`、`tree_hash`、`runtime_name/version`、`os`、`command_or_runtime_task_id`、`started_at/ended_at`、`exit_code`、`artifact_paths/hashes`、`provenance`、`rubric_version`、`machine_metrics`、`human_reviewer/verdict`、`rights_status`、`limitations`。

## UIUX 黄金纵切验收

- 五案例全部完成，三视口；
- 键盘核心路径可完成；
- Axe critical/serious 为 0；
- 可编辑 Artifact、Token、组件、Preview 与 Handoff 齐全；
- 每例三种结构方向，并保留选择和锁定证据；
- baseline/enhanced 盲评偏好率 ≥70%；
- 专业人工评分 ≥82；
- 至少一例 Open Design E3；
- 至少一条失败、取消或工具缺失后的正确恢复证据。

## Domain Pack 完整合同

每个包必须声明并通过：manifest、brief schema、scenario、profile、rubric、preflight、handoff contract、source mapping、benchmark cases、evidence cards。缺一项即不得标记 completed。

## 发布验收

- frozen tree 与 reviewer tree 相同；
- reviewer 无 blocker；
- required CI 对应 exact head SHA，completed/success；
- PR/merge 后 main SHA、tree、Artifact hash 回读一致；
- capability evidence index 无断链；
- README 能力表只展示证据支持的最高等级；
- 第三方 BOM、SBOM、REUSE 与 secret/supply-chain gate 通过；
- MiniGame 边界检查通过。

## 禁止伪证据

文件存在、Schema PASS、mock、skip、固定输出、只生成 Screenshot、合成 fixture、VLM 自评分、模型自我宣称、未完成 CI 和非 exact-SHA 运行均不能替代 E3/E4。

