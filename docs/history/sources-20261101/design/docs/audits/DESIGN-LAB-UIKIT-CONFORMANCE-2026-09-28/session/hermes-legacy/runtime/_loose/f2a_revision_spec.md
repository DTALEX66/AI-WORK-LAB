# Batch F-2a 规格：真实 revision（append-only 事件 + 内容 immutable）

## 背景（事实，先读代码再动）
- `src/design_lab/design_layer.py` 所有写路径只 `INSERT ... version=1`；`superseded_by` 恒 NULL；无事件表 → 审计所称 "version-ready schema, not complete versioning"。
- 报告 `docs/research/full-maturity-audit-2026-09-19.md` 第 257–267 行要求：`Brief v1→v2`、`Direction v1→v2`、`Binding v1→v2`；**内容对象 immutable + choice/binding/revision 事件 append-only**；`chosen` 可作 materialized state；不得用 `superseded_by` 把 append-only history 偷换成随意可变的行。

## 交付物
1. 迁移 v3：`design-lab/schemas/state/design-lab-state-design-layer-v3.sql`
   - 新增 append-only 事件表 `design_layer_event`：`event_id TEXT PRIMARY KEY`、`project_id TEXT NOT NULL`、`kind TEXT NOT NULL`（`brief-created`/`brief-revised`/`direction-created`/`direction-revised`/`direction-chosen`/`direction-unchosen`/`binding-created`/`binding-rebound`）、`brief_id`/`direction_id`/`binding_id`（可空）、`payload_json TEXT NOT NULL`、`actor TEXT`、`actor_kind TEXT`、`created_at TEXT NOT NULL`；建索引 `(project_id, created_at)`。
   - 注册：`src/design_lab/runtime/state_resources.py` 的 `_NAMES` + `src/design_lab/creative/store.py` 的 `GUARDED_MIGRATIONS`（追加在 v2 之后）。
2. `design_layer.py`
   - 每个写路径在同一事务内追加事件：`create_brief`→`brief-created`；`create_direction`→`direction-created`；`choose_direction`→`direction-chosen`（payload 含前一个 chosen 的 direction_id，或 null）；`bind_design_system`→`binding-created` / `binding-rebound`（rebind 时含被替换的 binding_id）。
   - 新增 `revise_brief(...)` / `revise_direction(...)`：**INSERT 新行（version = 旧 version + 1）**；旧行**只**更新 `superseded_by` 指针（**任何内容列不得 UPDATE**）；同事务追加 `brief-revised`/`direction-revised`（payload 含 old_id/new_id/version）。
   - 幂等沿用 `_record_intent`（同 key 同内容 → 同一身份；同 key 不同内容 → 409）。
   - 新增只读 `lineage_brief(project_id, brief_id)` / `lineage_direction(project_id, direction_id)`：按 version 升序返回版本链（含 superseded_by）。
   - `get_design_layer` 既有「取最新 revision」行为**不得回归**。
3. HTTP（先读现有路由注册与错误映射再动，沿用既有 token/项目守卫与 4xx 语义）
   - `POST /api/design-briefs/{brief_id}/revisions`、`POST /api/design-directions/{direction_id}/revisions`
   - `GET /api/design-briefs/{brief_id}/lineage`、`GET /api/design-directions/{direction_id}/lineage`
   - 不存在/跨项目/未选定一律 fail-closed（404/409/400）
4. 新增测试 `design-lab/tests/test_design_layer_revision.py`
   - revise 后 version 递增、旧行 `superseded_by` 指向新行、**旧行内容列逐字节未变**（断言内容 JSON 与 `spec_sha256` 未动）
   - 事件流：kind 序列与 payload 正确（`direction-chosen` 记录 prev chosen）；append-only（同一 event_id 重复写入不得覆盖/静默成功）
   - 幂等：同 key 重放 → 同一新 id；同 key 不同内容 → 409
   - 既有 18 个 design-layer 契约测试保持全绿
5. **不做**：不改 Workbench 前端（F-2b 由主线随后做）；不改 `reports/`、`AUTHORITY.md`、`.project/`、`docs/`、`AGENTS.md`、LANGUAGE-POLICY。

## 验证（贴原始输出）
- `.venv/Scripts/python.exe design-lab/tests/test_design_layer_revision.py`
- `.venv/Scripts/python.exe design-lab/tests/test_design_layer_http.py` → 18/18
- `.venv/Scripts/python.exe design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`
- `.venv/Scripts/python.exe scripts/verify_authority_gates.py --zero-spill` → 新增 state SQL **预期**触发 `contract-graph` DRIFT（`declared_tables`）；**不要改 reports/**，把该 DRIFT 原样报告给主线重录
- `git status --short` + `git diff --stat`

## 命令纪律
- 全部经 wrapper 单命令：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`，workdir=`D:/All projects/DESIGN-LAB`；禁 shell 串联（`&&`/`;`/`|`/`>`）。
- 不 commit / stash / push / 建分支；不装依赖；不联网。
- 每个「通过」必须配真实输出；无法完成写「未完成：<原因>」，不得虚构。
