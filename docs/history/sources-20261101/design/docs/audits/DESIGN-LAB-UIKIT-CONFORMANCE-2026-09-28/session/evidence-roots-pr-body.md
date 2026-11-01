## 授权

Owner intent 2026-09-27：「**加入**，全部开始」。这正是上一轮 PR #174 刻意**不**擅自处理、留给 owner 决定的那一项（survey 发现 F-6）。

## 为什么

`src/design_lab/governance/reporting.py:_safe` 决定证据 receipt / 投影输入**可以引用哪些路径**。它的 `allowed` 集合原本只覆盖 AUTHORITY §7「仓库责任」声明的 13 个根中的 8 个：

- **缺 `apps`** → **任何** receipt 都无法引用 `apps/workbench/**`，即 AUTHORITY §3 声明为第一等公民的前端（「DESIGN-LAB 有前端：apps/workbench/」）。R5 账本**无法记录任何前端事实**。这是**治理缺口，不是安全属性**。
- 拿 `allowed` 与 §7 逐项比对，发现 `research` 与 `vendor` **同样缺失** —— **完全相同的缺陷类**。只补 `apps` 会立刻为 §7 自己的声明根重建同一缺口。

## 做了什么

- `allowed` 现等于 §7 声明的根（12 项）+ `.project-local`（由既有独立分支接纳，且**仅限** `task-artifacts/`）→ 有效覆盖 = §7 全 13 根
- 新增 `apps` / `research` / `vendor`，无其他放宽
- 原地记录 owner intent / reason / superseded / impact（沿用 AUTHORITY byte-pin 再钉的同一先例）

## 安全面：**刻意未放宽**

- `denied`（`.git`/`.hermes`/`.openhuman`/`auth.json`/`credentials.json`/`tokens.json`/`id_rsa`）与 `.env*` 前缀规则**对每个路径分量生效**。实测：`.env`、`apps/workbench/.env`、`apps/auth.json` **变更后仍全部 DENY**。
- 放宽前审计了新增可引用根：`apps/`（仅源码 + tests + `build/main.js`）、`research/`（2 文件）、`vendor/`（1 文件）、`services/`（0 文件）—— **无凭据类文件名**。
- 即：放宽的是「**可以引用什么**」，不是「**可以泄露什么**」。

## 解锁：两条此前**被迫跳过**的 receipt 终于可绑定

账本 receipt 3 → 8，绑定轴 **10 / 112**：

| receipt | 绑定轴 | kind |
|---|---|---|
| `r5-workbench-strict-ts-build-truth-20260927` | DL-R5-028 implementation + unit | local_test |
| `r5-workbench-native-task-ui-tests-20260927` | DL-R5-010 implementation + unit | local_test |

均为 `outcome=PARTIAL`，锚定 exact SHA `634071f3c8ffa87e08fa1386f49c185ff6fa36d8`。
契约（`r5_contract.py`）：`definition`/`title`/`depends_on`/`predecessor_task_ids`/`required_axes` **逐字节冻结、未动**；`:100-101` 禁止在 `reassessment != REVIEWED` 时置 `PASS`/`IMPLEMENTED_LOCAL`，故**所有轴保持 PARTIAL** —— receipt 记录「验证到什么」，**不**宣称任务完成。

## 同 PR 附带

- **`docs/handoffs/DESIGN-LAB-PROJECT-SURVEY-TRUTH-RESYNC-2026-09-27.md`**：tracked 交接 + 总结，带 `HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE` banner。含 **HERMES 任务面普查结论**（无 cron 作业 / 无看板任务 / 无 DESIGN-LAB 的 project-local-run）、审计发现、未处理项、以及下一会话会重新踩的环境坑。
- 重生成投影与 authority chain（随账本一起漂移）。

## 审计发现但**未**擅自处理（记录在案，owner 决定）

- `services/` 存在于顶层但 **§7 未声明**，且当前 **0 文件** → **未**加入允许集合（它不是 §7 的根）。要么在 §7 声明，要么删掉空目录。
- `LICENSES/` 同样存在但 §7 未声明。
- R5 账本仍**无「已完成」语义**（全 `PLANNED_DELTA` + `PARTIAL`）；正式的 evidence reassessment 属 owner 主导，本轮刻意不越权。

## 本地验证

| 门 | 结果 |
|---|---|
| `run_python_tests.py` | **exit 0**（1755 tests） |
| `verify_top_level_authority.py` | `TOP_AUTHORITY_GATE=PASS checks=10` |
| `verify_authority_gates.py --zero-spill` | `AUTHORITY_GATES=PASS gates=7` |
| `generate_current_reports.py --check` | `CURRENT_REPORTS=PASS` |
| `verify_project_drift.py` | `PROJECT_DRIFT=PASS findings=0` |
| `verify_path_refs.py` | `PATH_REF_GATE=PASS checks=10` |
| `update_evidence_binding.py --check` | `HISTORICAL_VALID`（未重绑，遵守 DL-EVD-002） |
| workbench tsc / build / unit / appshell | 全绿，`apps/workbench/build` 无漂移 |
