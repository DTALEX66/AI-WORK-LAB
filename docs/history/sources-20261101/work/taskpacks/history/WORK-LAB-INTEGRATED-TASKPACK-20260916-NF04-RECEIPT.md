# INTEGRATED-TASKPACK-20260916 · NF-04 收口回执（可解释的轻量配置变更闭环）

- 生成：2026-09-16 · 执行者：Hermes
- 范围：定点核对现有 preview/apply/readback/rollback 调用链与契约测试，只补真实缺口；零真实全局写、零付费、零凭据正文。
- 入口实现（已存在，未重写）：`services/policy/config_control_plane.py`（ConfigControlPlane.transaction：Discover→Effective→Diff→Backup→Approval→Apply→Readback→Commit/Rollback）+ `services/policy/config_coordinator.py`（three_way_compare/QUARANTINE/PRESERVE/rollback_plan）+ `services/receipts/action_receipt.py` + `config/config-ownership.json`（single_authority，observe-only 平台 adapter_defaults=OBSERVE+preserve_unknown）。

## 定点核对结论（"能直接通过的子项不重写"）
既有 `test_config_transaction.py` 已覆盖 4/6 场景：未批准不写(WAITING_APPROVAL)、提交(COMMITTED)、回读漂移(ROLLBACK_REQUIRED)、缺适配器(UNSUPPORTED_APPLY)。`test_config_coordinator.py` 已覆盖字段不归属/隔离(QUARANTINE)/rebase/哈希围栏回滚。`test_apply_safety.py` 已锁定 7 步序列 + 5 不变量。**这三项未重写**，仅在 `transaction()` 补 3 条诚实态契约 + 4 条对应合成测试。

## 本卡新增（最小差异，3 处实现 + 4 条测试）
实现（`config_control_plane.py` `transaction()`，保持既有 4 个断言不变）：
1. **无变更 NOOP**：approved 且 `changeCount==0` 的空 diff 早退，不进 backup/apply/readback，不上报为写。
2. **写失败 APPLY_FAILED**：`apply_fn` 抛异常时捕获，返回 `written="UNDETERMINED"` + `restored=False` + 仅 `errorType`（不泄漏异常文本，避免适配器把私密配置值带进回执）；**绝不伪造 ROLLED_BACK/COMMITTED/成功**。
3. **SIMULATED 打标**：新增 `simulated: bool` 入参，成功态拼为 `COMMITTED_SIMULATED` / `APPLIED_NO_READBACK_SIMULATED` / `ROLLED_BACK_SIMULATED`，且每个结果都带 `simulated` 布尔字段；模拟适配器无法混入真实 applied-success 统计（只数 `status=="COMMITTED"` 的项）。

测试（`test_config_transaction.py` +4）：
- `test_noop_on_empty_diff`（apply_fn 置为断言必炸，验证空 diff 根本不调用它）
- `test_apply_failure_is_honest_undetermined`（写失败=UNDETERMINED，errorType 不含异常文本）
- `test_rollback_failure_is_honest`（恢复失败=ROLLBACK_FAILED·restored=False，不伪造 ROLLED_BACK）
- `test_simulated_success_is_tagged_and_not_real`（SIMULATED 成功与真实成功可区分，真实成功统计只含非模拟项）

## 验证（隔离 venv，与 gate 命令对齐）
- `pytest tests/workflow-assistance/test_config_transaction.py`：**8/8 PASSED**。
- 全量 `pytest tests/workflow-assistance`：**1259 passed / 8 skipped / 0 failed / 0 errors**（较 P0 的 1255 +4，即本卡新增 4 条）。
- 全为合成 in-memory 输入 + 项目内 `.project-local/runs/config-transaction-tests/` 备份目录，无真实全局写。

## 验收核对
- 模拟适配器明确标 SIMULATED、不入真实应用成功统计 ✅
- 覆盖 无变更/缺适配器/字段不归属/写失败/回读不符/恢复失败 六场景 ✅（前 3 + 提交 + 漂移由既有测试，后 3 由本卡补测）
- 操作状态可追溯真实动作；observe-only 客户端（cc-switch/github/openhuman/open-design，OBSERVE+preserve_unknown）完全没有可写入口 ✅

## 剩余与阻塞
- 真实字段级全局写留待 **NF-07**（明确字段级授权后）；本卡未做任何真实写。
- 下一张可独立继续的卡：**NF-05**（各客户端原生接口与能力最小适配，只读/合成验证）或 **NF-06**（一个真实客户端的只读价值闭环）。
