## 背景

W00 的代码级取证证明：**28 项 R5 任务每一项都有真实实现模块 + 真实测试模块**（候选路径 0 缺失、**28/28 有测试**）。但 **112 个轴里只有 3 个**带证据。**缺口在证据绑定，不在实现**——正是 W00 派工的「补证据」。

## 做了什么

**新增 28 条 receipt**（共 36 条）。每条以该任务的**真实实现模块 + 测试模块**（含 sha256）为 `subject_files`，以 W00 取证 JSON 为 artifact。

**绑定轴：implementation +22、unit +25 → 10/112 ⇒ 57/112。**

## **刻意不绑定**的两类

| 轴 | 原因 |
|---|---|
| `host_live` | **没有真实 Adobe 宿主运行** —— 无可诚实引用的证据 |
| `delivery` | **没有已交付包** —— 同上 |

即：账本最难的部分**保持未绑定**，而不是用静态证据冒充运行时证明。

## **不宣称任何完成**

- 所有轴状态**仍为 `PARTIAL`**、`reassessment` **仍为 `PENDING_EVIDENCE_REVIEW`** —— `r5_contract.py:100-101` 禁止在 `!= REVIEWED` 时置 `PASS`/`IMPLEMENTED_LOCAL`，本 PR **不动 `reassessment`**
- 冻结字段（`definition`/`title`/`depends_on`/`predecessor_task_ids`/`required_axes`）**未动**，R5 契约校验器 **VALID**
- `subject_sha` = `4c9f1849…` —— **实际跑套件的那个 HEAD**（exit 0），不是把旧 SHA 提升为新 SHA（AUTHORITY §6）

## 过程中发现的一条真实约束

**`subject_files` 只能是文件。** 投影管线会逐个读它们（`reporting.Reader.read`），而**目录在 Windows 上抛 `PermissionError`** → 我第一次把 `src/design_lab/readiness/` 放进 `subject_files`，直接让 `generate_current_reports.py` 变红。现已改为把目录展开为其内文件。记录此点，因为它会把一个绿账本变成红投影门禁。

## 验证

| 门 | 结果 |
|---|---|
| R5 契约校验器 | **VALID** |
| `test_r5_migration` + `test_current_reporting`（账本契约测试） | **43 tests, OK** |
| `run_python_tests.py`（全量套件） | **exit 0 at 4c9f184** |
| `generate_current_reports.py --check` | `CURRENT_REPORTS=PASS` |
| `verify_authority_gates.py --zero-spill` | `AUTHORITY_GATES=PASS gates=7` |
| `verify_top_level_authority.py` | `TOP_AUTHORITY_GATE=PASS checks=10` |
| `verify_project_drift.py` | `PROJECT_DRIFT=PASS findings=0` |
| `verify_no_overclaim.py` | `NO_OVERCLAIM=PASS unsupported=0` |

同 PR 重生成 `reports/current/**`（13 文件）+ `current-report-index.json` + `DEEPSEEK-AUTHORITY-CHAIN.json`（其记录的账本摘要随账本漂移）。
