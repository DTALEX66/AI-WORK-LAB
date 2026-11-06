# 独立复审第一轮（复审者原文，逐字摘录）

工具：codex-cli（`codex exec --sandbox read-only`），与被审代码的作者是不同上下文。
本文件不含任何改写：下面的段落是复审者自己打印的报告，起止由脚本在原始 stdout 里定位。
原文完整 stdout 留在 `.project-local/audit/20261106-independent/REVIEW-raw.txt`（运行产物，不入 Git）。

结论：**FAIL，但本次复审未完整完成**。已直接证实当前工作树的三个入口数字与现算值不符；其余未完成验证的部分不能视为通过。仓库存在多处未提交修改，本结论针对当前工作树，不等同于该 SHA 的干净提交。

实际执行及结果：

| 命令或检查 | 实际读数 |
|---|---|
| `git rev-parse HEAD` | 上述 40 位 SHA |
| `git status --porcelain=v1` | 12 个已跟踪文件修改、2 个未跟踪文件 |
| 读取 `AGENTS.md`、`PROJECT_CURRENT.md`、`INTEGRATION_POLICY.md`、审计入口尾部、`AUDIT-STATE.json` | 已执行；部分输出被截断，因此不能声称全部读完 |
| `.venv/Scripts/python.exe -B -X utf8 scripts/check_project_current.py --check` | `FAIL`，3 条 `FIGURE_STALE` |
| 同上：登记维护归属 | `tracked=35, undeclared=0` |
| 同上：历史文件登记 | `tracked_files=5965, named_by_a_ledger=5961, self_claimed_ledgers=4` |
| `scripts/check_workbench_bundle_drift.py`（使用上述解释器参数） | `BUILD_FAILED`，`build_rc=1`；不能据此认定 DRIFT |
| `git ls-files apps/workbench/build/main.js` | 返回该文件路径 |
| `git check-ignore -v --no-index apps/workbench/build/main.js` | 命中 `.gitignore:16` 的反选规则 |
| `scripts/build_blocker_register.py --check` | `matches=true, items=7, blocking=1` |
| `scripts/build_deferral_register.py --check` | `matches=true, entries=15` |
| 直接调用 `staleness_assessment`，分别传入缺席、`bad`、过早、正常时间 | 分别为 `NOT_EVALUATED_PRODUCED_AT_ABSENT`、`NOT_EVALUATED_PRODUCED_AT_INVALID`、`STALE`、`CURRENT` |
| `scripts/build_source_coverage.py --check` | 未取得结果，已中止；后续两个登记检查单独重跑 |

**阻断发现 F1：入口现值已经失真。**

`PROJECT_CURRENT.md:63`、`:68`、`:71` 分别声明：

| 字段 | 文档 | 检查器现算 |
|---|---:|---:|
| `lf_tracked_files` | 728 | 729 |
| `spdx_claimed_files` | 226 | 227 |
| `suite_test_nodes` | 572 | 575 |

这是一个维护一致性问题，包含三项错误数字。检查器确实能红，不能说它是假绿；但当前工作树没有满足项目要求的入口防漂移检查。无需另造反例，当前工作树就是反例。

代码检查另得到以下有限结论：

- `scripts/check_workbench_bundle_drift.py:67–81`：忽略且未跟踪、可见但未跟踪、已跟踪但磁盘缺失分别有独立返回；不能仅凭这些分支断言全部类别已经实测可达。
- `scripts/check_workbench_bundle_drift.py:81`：名为 `committed_digest` 的值实际读取**工作树文件**，没有读取 HEAD 或 index 的 blob。该命名不能作为“已提交字节得到核验”的证据。
- `backend/core/binding.py:267`：`RESULT_STALE` 拒判代码仍存在；本次没有完成 HTTP 201 与拒判的端到端验证。
- `scripts/build_source_coverage.py:1096–1100`：比较字段来自被检查 CSV 自己的表头。这存在枚举面风险：**删除整个 `class` 列后，该比较函数也不再比较 class**。这是代码推导的反例，尚未实际构造执行，暂不计为确认发现。
- `scripts/build_deferral_register.py` 的 human gate 枚举写在常量散文中；`test_v24` 新节点另从参照 manifest 和磁盘缺席文件计算列表并比较。应区分“测试现算核对”与“生成器现算生成”，两者不是一回事。

以下五组要求未能完整核实：

1. bundle 全部类别、死分支及 MATCH/DRIFT 反例。
2. 201 回执、工作面与设计面不对称的实际测试。
3. 32 行 pending、`decided_by=null` 全量统计及手改 class 的实际反例。
4. human gate 新节点的实际运行。
5. 文档硬抄现值的完整扫描，以及审计最后三节全部机械断言。

因此，本报告提供的是**已确认 FAIL 的有限复审证据**，没有满足你要求的完整逐项审计。没有修改仓库文件，也没有提供修复补丁。

```text
INDEPENDENT_REVIEW_VERDICT: FAIL
reviewed_sha: 14f383c86672e63c6def5f89b75399829285a52b
blocking_findings: 1
non_blocking_findings: 0
checks_actually_run: 8
unverified_claims: 5
```
