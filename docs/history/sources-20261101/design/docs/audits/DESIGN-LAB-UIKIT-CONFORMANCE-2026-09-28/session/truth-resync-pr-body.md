## 背景

项目梳理发现**三个「任务真值」面系统性落后于已交付事实**（详见 .project-local/task-artifacts/project-survey-2026-09-27/PROJECT-SURVEY-2026-09-27.md，只读报告，未入仓）。本 PR 只做真值对齐，**不改任何产品行为**。

## 1. 投影漂移（高）

eports/current/PROJECT_STATUS.md 观察 SHA = 6ba2578a…（main 已是 634071f3…），且写的是任务包 DL-TP-20260908-R5 而非 current integrated 包。按 uthority-index.projectionRule，eports/current/** 属 PROJECTION，**须经 fresh 校验才可用** → 当时不可用。

→ 用 scripts/generate_current_reports.py 重生成；--check 现为 CURRENT_REPORTS=PASS（bound-input integrity）。13 个投影文件 + design-lab/config/current-report-index.json。

## 2. R5 账本几乎没有证据绑定（高）

design-lab/config/task-ledger-r3.json：28 任务、四个轴**全部 PARTIAL**、全部 PENDING_EVIDENCE_REVIEW、**112 个轴中仅 3 个有证据**——而 AUTHORITY §15 已把多个 P0 记为 CLOSED_WITH_REGRESSION_GUARD。

→ 为本次会话在 exact SHA 634071f3c8ffa87e08fa1386f49c185ff6fa36d8 实测的事实新增 3 条 receipt，并从对应轴引用（DL-R5-001 / -002 / -003）：分支收敛（远端 28→1、open PR 0、单 worktree、0 stash）、运行根/数据边界（.hermes 非活跃写入根，按所有权清理且 sha256 移前=移后）、required-check 面（9 项，该 SHA 全绿）。

**契约遵从**（src/design_lab/governance/r5_contract.py）：definition/	itle/depends_on/predecessor_task_ids/equired_axes 逐字节冻结、未改动；:100-101 禁止在 eassessment != REVIEWED 时把轴置 PASS/IMPLEMENTED_LOCAL，故**所有轴状态保持 PARTIAL**——receipt 记录「验证到什么」，不宣称任务完成。

**刻意未绑定**：Workbench strict-TS receipt。src/design_lab/governance/reporting.py:52 的证据根 llowed 集合**不含 pps**，因此任何 receipt 都无法引用 pps/workbench/**。记为**治理缺口**，而非在无 owner intent 的情况下放宽策略。

## 3. AUTHORITY.md 断言了过时动态事实（高）

§13（建立时快照）被当作现状读：7 项 required checks / 28 分支 /「workbench 仍只有三个文件」；live 读回为 **9 / 1 / 10**。

- §13 **原文保留**（它明确是建立时基线，改写即伪造历史）
- 新增 **§13.1**：带观察 SHA 与日期的显式 live 读回
- 修正 §15 中 3 处**现在时**的「7 项 required checks」陈述
- 按 §17，scripts/verify_top_level_authority.py **同步再钉** AUTHORITY.md byte-pin（7c1e6ad… → 7b29d3ea…），并在原地记录 owner intent / reason / superseded / impact，沿用既有 2026-09-20 先例。checks 数仍为 10。

顺带重生成 eports/current/DEEPSEEK-AUTHORITY-CHAIN.json（其记录的账本摘要随 (2) 漂移）。

## 本地验证（全部 on this tree）

| 门 | 结果 |
|---|---|
| scripts/verify_top_level_authority.py | TOP_AUTHORITY_GATE=PASS checks=10 |
| scripts/verify_authority_gates.py --zero-spill | AUTHORITY_GATES=PASS gates=7 |
| scripts/generate_current_reports.py --check | CURRENT_REPORTS=PASS |
| design-lab/scripts/verify_project_drift.py | PROJECT_DRIFT=PASS findings=0 |
| scripts/verify_path_refs.py | PATH_REF_GATE=PASS checks=10 |
| update_evidence_binding.py --check | HISTORICAL_VALID（未重绑，遵守 DL-EVD-002） |
| scripts/run_python_tests.py | **Ran 1755 tests — OK (skipped=37)** |
| identity / design_lab / adapter_matrix / product_manifest_v3 / runtime_contracts_v3 / visual_scoring_v3 / source_registry / v2_protocols / visual_quality_v21 / library_index_consistency / anti-slop / compileall | 全 OK |
| workbench tsc + vite build + unit.mjs + appshell.mjs | 全绿，pps/workbench/build 无漂移 |

## 兼容性

- 未改任何 product 行为、未改 R5 任务定义/依赖/必需轴。
- AUTHORITY 的静态 release 内容未删除；仅新增 §13.1 并修正现状陈述，同步再钉。
