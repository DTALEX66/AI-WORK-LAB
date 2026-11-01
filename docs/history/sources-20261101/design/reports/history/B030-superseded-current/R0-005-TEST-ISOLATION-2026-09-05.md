# R0-005 测试隔离实证报告（2026-09-05）

> 任务：DL-TP-R0-005（测试隔离）。DoD：Python 全套在固定/倒序/随机顺序全绿；污染敏感模块重复 20 次；工作树干净。
> 工具：`design-lab/scripts/run_test_isolation.py`（本分支新增）。

## 结果

| 顺序 | seed | 运行数 | failures | errors | 结论 |
|---|---|---|---|---|---|
| forward | — | 580 | 0 | 0 | ✅ PASS |
| reverse | — | 580 | 0 | 0 | ✅ PASS |
| random | 20260905 | 580 | 0 | 0 | ✅ PASS |

- 污染敏感模块重复 20 次（asset_store / job_store / state_store / operation_coordinator / profile_resolver / doctor）：每轮 24 tests，0 失败，共 20 轮 ✅。
- 工作树：干净（git status --porcelain 空）。

## 说明

- 首次 forward 运行曾报 1 error + 1 failure，系运行期间仍在编辑/提交测试文件的脏树自伤（reconstruction 执行源闭包对比 HEAD blobs），非真实顺序依赖；在静止树上重跑 forward 通过，reverse/random 同样通过。三序均以静止树最终结果为准。
- 运行器已入库，支持 `--order forward|reverse|random --seed N` 与 `--modules ... --repeat N`，作为后续隔离回归的证据工具。
