# 待判定的来源文件（按组，不是逐条）

口径：`migration/source-coverage-*.csv` 中 `class` 为 `REGISTERED_GAP` 或
`OWNER_DECISION_PENDING` 的全部行；字节与修改时间取自来源仓盘面（只读，未改动）。
「同名文件」= 本仓的 Git 文件清单里已有同名文件；「代码引用数」= `git grep` 在
`*.py`/`*.ts`/`*.mjs` 里命中该文件名的文件数。两列都只是名字的迹象，
不证明该能力需要这个文件，也不构成迁移理由。

| 仓 | 类别 | 组（前两级路径） | 文件 | 合计 | 最近修改 | 同名文件 | 代码引用数 | 例子 |
|---|---|---|---:|---:|---|---|---:|---|
| work | REGISTERED_GAP | `packages/client-neutral-core` | 107 | 0.9 MiB | 2026-10-26 | 没有 | 0 | `packages/client-neutral-core/scripts/active_projects.py` |
| work | REGISTERED_GAP | `taskpacks/current` | 1 | 0.4 MiB | 2026-10-28 | 没有 | 2 | `taskpacks/current/OPEN-TASK-REGISTER.md` |
| work | OWNER_DECISION_PENDING | `scripts/audit` | 4 | 0.2 MiB | 2026-10-28 | 没有 | 1 | `scripts/audit/hud_strip_geometry_via_cdp.py` |
| work | REGISTERED_GAP | `services/orchestration` | 10 | 0.2 MiB | 2026-10-27 | 没有 | 0 | `services/orchestration/canary_runner.py` |
| work | REGISTERED_GAP | `services/session-federation` | 15 | 0.2 MiB | 2026-10-26 | 没有 | 0 | `services/session-federation/agui_projection.py` |
| work | OWNER_DECISION_PENDING | `apps/observer` | 7 | 0.1 MiB | 2026-10-26 | 没有 | 1 | `apps/observer/scripts/usage_rollup.py` |
| work | REGISTERED_GAP | `.project/governance` | 3 | 0.1 MiB | 2026-10-19 | 没有 | 0 | `.project/governance/future-candidate-registry.json` |
| work | REGISTERED_GAP | `services/policy` | 13 | 0.1 MiB | 2026-10-27 | 没有 | 0 | `services/policy/config_compiler.py` |
| work | REGISTERED_GAP | `services/receipts` | 11 | 0.1 MiB | 2026-10-26 | 没有 | 0 | `services/receipts/error_ledger_summary.py` |
| work | REGISTERED_GAP | `services/execution-federation` | 8 | 0.1 MiB | 2026-10-18 | 没有 | 2 | `services/execution-federation/codex_adapter.py` |
| work | REGISTERED_GAP | `services/radar` | 6 | 0.1 MiB | 2026-09-17 | 没有 | 0 | `services/radar/price_validation.py` |
| work | REGISTERED_GAP | `services/authority` | 7 | 0.0 MiB | 2026-10-12 | 没有 | 0 | `services/authority/agent_registry.py` |
| work | REGISTERED_GAP | `config/adapter-registry.json` | 1 | 0.0 MiB | 2026-10-24 | 有 | 19 | `config/adapter-registry.json` |
| work | REGISTERED_GAP | `services/memory` | 6 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/memory/hermes_builtin.py` |
| design | OWNER_DECISION_PENDING | `scripts/collect_design_capability_candidates.py` | 1 | 0.0 MiB | 2026-10-06 | 没有 | 1 | `scripts/collect_design_capability_candidates.py` |
| work | REGISTERED_GAP | `services/cleanup` | 4 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/cleanup/outdated_archive.py` |
| work | REGISTERED_GAP | `services/evolution` | 4 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/evolution/independent_eval.py` |
| work | OWNER_DECISION_PENDING | `scripts/maintenance` | 4 | 0.0 MiB | 2026-10-19 | 没有 | 1 | `scripts/maintenance/converge_u02_runtime_paths.py` |
| work | REGISTERED_GAP | `services/security` | 3 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/security/skillspector_gate.py` |
| design | OWNER_DECISION_PENDING | `scripts/deepseek_test_gate_report.py` | 1 | 0.0 MiB | 2026-10-13 | 没有 | 1 | `scripts/deepseek_test_gate_report.py` |
| work | REGISTERED_GAP | `config/capability-matrix.json` | 1 | 0.0 MiB | 2026-10-25 | 有 | 8 | `config/capability-matrix.json` |
| design | OWNER_DECISION_PENDING | `scripts/amend_source_lock_presence.py` | 1 | 0.0 MiB | 2026-10-08 | 没有 | 1 | `scripts/amend_source_lock_presence.py` |
| design | OWNER_DECISION_PENDING | `scripts/run_python_tests.py` | 1 | 0.0 MiB | 2026-10-15 | 没有 | 1 | `scripts/run_python_tests.py` |
| work | REGISTERED_GAP | `services/task-graph` | 1 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/task-graph/beads_poc.py` |
| work | REGISTERED_GAP | `apps/observer` | 1 | 0.0 MiB | 2026-10-28 | 没有 | 0 | `apps/observer/frontend/src/lib/viewRegistry.ts` |
| design | OWNER_DECISION_PENDING | `design-lab/core` | 6 | 0.0 MiB | 2026-09-17 | 有 | 9 | `design-lab/core/commands.py` |
| work | REGISTERED_GAP | `services/knowledge` | 1 | 0.0 MiB | 2026-09-17 | 没有 | 0 | `services/knowledge/promotion_gate.py` |
| design | OWNER_DECISION_PENDING | `design-lab/scripts` | 2 | 0.0 MiB | 2026-09-25 | 没有 | 1 | `design-lab/scripts/resolve_open_design_locator.py` |
| work | OWNER_DECISION_PENDING | `integrations/archeaxis` | 2 | 0.0 MiB | 2026-09-23 | 没有 | 1 | `integrations/archeaxis/contracts/promotion_contract.py` |
| work | REGISTERED_GAP | `services/task-governance` | 1 | 0.0 MiB | 2026-09-17 | 没有 | 2 | `services/task-governance/task_protocol.py` |
| design | OWNER_DECISION_PENDING | `scripts/generate_current_reports.py` | 1 | 0.0 MiB | 2026-09-17 | 没有 | 1 | `scripts/generate_current_reports.py` |
| design | OWNER_DECISION_PENDING | `scripts/archive_records.py` | 1 | 0.0 MiB | 2026-10-19 | 没有 | 1 | `scripts/archive_records.py` |
| design | REGISTERED_GAP | `packages/capabilities` | 1 | 0.0 MiB | 2026-09-03 | 没有 | 0 | `packages/capabilities/quality/jury/check_anti_slop.py` |
| work | OWNER_DECISION_PENDING | `services/policy` | 1 | 0.0 MiB | 2026-10-23 | 没有 | 1 | `services/policy/universal_agent_core.py` |

合计 237 个文件、34 组；按仓与类别：design/OWNER_DECISION_PENDING=14、design/REGISTERED_GAP=1、work/OWNER_DECISION_PENDING=18、work/REGISTERED_GAP=204。

来源盘面上已找不到的行：0 条。

逐条明细（含来源摘要、字节、修改时间与登记理由）见同目录 `source-unsettled-detail-20261101.json`。
本文件不替你判定，也不把任何组写成「已迁」或「可删」。
