---
name: references
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-observer-delivery/references/dashboard-schema-drift-2026-08.md
---

# Dashboard schema-drift debugging transcript (2026-08-11)

## Symptom
Observer dashboard (`http://127.0.0.1:6522/`) showed:
- "暂无观测事件 · 等待 Workflow Assistance evidence envelope"
- All KPIs 0 (任务 0 / 事件 0 / Token 0)
- User: "我安装了，又运行了一个别的项目，为什么没有显示其他项目，你这项目运行全景是假的信息吗？"

## First check (do this FIRST, it decides everything)
Read the canonical store directly — it is the single source of truth:
```sql
-- .hermes/task-runtime/workflow/canonical.sqlite
SELECT * FROM projects;                    -- 2 rows: work-lab ACTIVE, open-design-assistance REGISTERED
SELECT COUNT(*) FROM telemetry_events;     -- 13
SELECT * FROM tasks;                       -- 3 rows (COMPLETED_LOCAL / BLOCKED / APPROVAL_PENDING)
SELECT * FROM usage_samples;               -- 2 rows
SELECT * FROM ci_runs;                     -- 1 row success
```
Store had real data → the UI was NOT lying about data absence; it was reading the WRONG schema.

## Root cause chain
1. `ObserverStore.rebuild_projection()` returns `to_dashboard()` (canonical schema v2):
   `summary` / `projects` / `usage` / `ci` / `quality` / `mutationSurface`
2. But `scripts/observer_dashboard.py` `_render_full` / `_render_compact` were reading the RETIRED
   event-rebuild schema: `overview.taskCount` / `tasks[]` / `dataQuality` — all missing → zeros.
3. Web frontend (`web/scripts/render.js`) rendered `p.state` (running/waiting/blocked/...),
   but canonical projection only emitted `p.status` (ACTIVE/REGISTERED) → undefined → "unknown" / no rows.
4. Usage: `to_dashboard()` hardcoded `inputTokens: None, series: []`; and projection does
   `SUM(total_tokens)` while `record_usage_sample` callers often omit `total_tokens` → NULL.

## Fixes (projection-side, not UI-side — keep the UI vocabulary stable)
1. `observer_canonical.py` project rows: add
   `"state": _dashboard_project_state(status)` mapping ACTIVE→running, REGISTERED→idle,
   BLOCKED→blocked, WAITING_APPROVAL→waiting, FAILED→failed, COMPLETED→completed, else unknown.
   Also add `agentPlatform: None`, `ciState: None` so the frontend has its fields.
2. `observer_canonical.py` usage: emit `inputTokens`/`outputTokens`/`series` from the usage rows
   (one point per row; bucket = observed_at) instead of None/[].
3. `canonical_store.py` `record_usage_sample`: when `total_tokens` is None, derive
   `(input_tokens or 0) + (output_tokens or 0)` so `SUM(total_tokens)` is real.
4. `observer_dashboard.py` `_render_full` / `_render_compact`: rewrite against canonical schema —
   project table (displayName / state pill / projectId), usage tokens, quality integrity,
   CI runs. Removed "由事件重建" wording; now "canonical".

## Verification that actually convinced
- `browser_navigate http://127.0.0.1:6522/?view=full` → snapshot showed:
  WORK-LAB | running | work-lab ; DESIGN-LAB | idle | open-design-assistance ;
  输入/输出/总 Token 2050 ; 趋势点 1
- `?view=compact` → same data
- Observer Python 48/48 OK; Node UI 44+4 OK; `test_observer_dashboard_render.py` 4/4
  (regression tests lock the canonical render contract; SkipTest when canonical.sqlite absent)

## Environment notes
- Windows does not expose a process working directory via tasklist/wmic.
  Active-project detection = agent process running (tasklist) AND fresh evidence files in
  the project's `.hermes` / `.codex` / `.agents` (mtime ≤ 120 min). Never fabricate "active".
- Existing services: check `.hermes/task-runtime/*/sidecar-process.json` and
  `.hermes/task-runtime/observer/dashboard-process.json` for PID/port BEFORE starting a new
  sidecar/dashboard (else `sidecar_already_running`).
- `record_usage_sample` exists (not `append_usage_sample`); `update_project_status` was added
  to `canonical_store.py` for ACTIVE/REGISTERED transitions.
