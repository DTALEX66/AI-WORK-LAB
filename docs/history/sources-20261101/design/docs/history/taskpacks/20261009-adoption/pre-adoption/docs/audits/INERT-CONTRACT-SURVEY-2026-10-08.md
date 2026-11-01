# INERT 合同普查（生成物，勿手改）

由 `design-lab/scripts/inert_contract_survey.py` 计算生成；重跑：
`python design-lab/scripts/inert_contract_survey.py`，只读校验：加 `--check`。
本页的每个数字都来自仓库本身（schema 属性、`design-lab/schemas/state/*.sql` 的表列、产品源码中
对该表的写入/读取语句），不是从任何 reason 文案抄来的。

判定规则（可反对，但必须显式反对）：一个 schema 与某张表"重叠"，当且仅当它声明的顶层属性名中
至少 1/3 是该表的列。这个三分之一是"大概是同一件事被声明了两次"的门槛，不是产品里的某个测量值；
每行都给出自己的 overlap 与命中的字段名，34% 的匹配可以被 reviewer 直接否掉。

分类含义：
  * `TABLE_WRITES_THIS_ACTIVITY` —— 有产品代码在写这张表：这条 INERT 声明的很可能是同一事物的第二种形状。
  * `TABLE_EXISTS_UNWRITTEN` —— 表在 SQL 里声明了，但没有任何产品代码写它：形状对得上，实现也没有。
  * `ADJACENT_TABLE_WRITTEN` —— 有被写的表但字段重合不足三分之一：相邻，不是重复。
  * `NO_STATE_COUNTERPART` —— 没有任何表对得上。
  * `SCHEMA_FILE_ABSENT` —— 账本还声明着这条合同，文件已经不在仓里：既谈不上接线，退役也要先说明。

标注 `（thin）` 的行：schema 声明的属性 ≤3 且只有 1 个名字与表重合 —— 门槛在这种情况下会被单个
同名列达到，判断请配合 `matched_fields` 一起看，不要只看分类词。

`retire_coherent` 只说明"退役这条在账本与路由清单里没有连带引用"，即该选项可执行，不表示建议执行。

下面这段 JSON 是本页的可校验部分：`--check` 会重算并与此块逐字节比较，改了代码没重跑就是红的。

```json
{
  "contracts": 32,
  "inertRows": 30,
  "productFiles": 206,
  "rows": [
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. plan_id/jobs appear nowhere in src/. The action-plan boundary that does exist is bound by design-lab/schemas/tool-action-plan.schema.json, checked by design-lab/scripts/verify_tool_action_plan.py against design-lab/evals/tool-action-plan/sample-hero.json -- a different document with a different field vocabulary, which this schema does not describe.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/action-plan.schema.json",
        "design-lab/config/contract-bindings.json:action-plan.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/action-plan.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/action-plan/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Two documents claim one version identity. This file requires snake_case manifest_id/assets while design-lab/schemas/asset-manifest.schema.json carries $id design-lab/asset-manifest/v1 and requires camelCase manifestId. The camelCase one is the file scripts/verify_contract_graph.py:79 reads; no src/ module produces either shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/asset-manifest.schema.json",
        "design-lab/config/contract-bindings.json:asset-manifest.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/asset-manifest.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/asset-manifest/v1"
    },
    {
      "best_table": "asset",
      "fields": 6,
      "matched_fields": [
        "asset_id"
      ],
      "overlap": 0.167,
      "reason": "Nothing implements this. content_hash/trait_set/runtime_binding appear nowhere in src/. The asset_ref hits in src/design_lab/interop/timeline.py:607 are a plain string field of the OTIO timeline contract, a different shape under a colliding name; test_illustrator_job_validation.py:67 matches on the word assetId, not on this schema.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/asset-ref.schema.json",
        "design-lab/config/contract-bindings.json:asset-ref.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/asset-ref.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [
        "src/design_lab/assurance/jury_store.py",
        "src/design_lab/assurance/production_preflight.py",
        "src/design_lab/assurance/quality_store.py",
        "src/design_lab/creative/asset_versions.py",
        "src/design_lab/creative/lineage_view.py",
        "src/design_lab/design_layer.py",
        "src/design_lab/image_assets.py",
        "src/design_lab/native_assets.py",
        "src/design_lab/native_delivery.py",
        "src/design_lab/runtime/asset_store.py"
      ],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/asset-ref/v1"
    },
    {
      "best_table": "audit_event",
      "fields": 9,
      "matched_fields": [
        "action",
        "actor",
        "at",
        "audit_id"
      ],
      "overlap": 0.444,
      "reason": "Half of this shape is real and the schema cannot be satisfied by it. The live audit_event table (design-lab/schemas/state/design-lab-state-v1.sql:45, written at src/design_lab/runtime/asset_store.py:144) carries exactly audit_id/actor/action/at -- this schema's four required fields other than schemaVersion -- but never emits a schemaVersion, so a real row fails this closed document. No JSON audit-event payload exists in src/.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/audit-event.schema.json",
        "design-lab/config/contract-bindings.json:audit-event.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/audit-event.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/runtime/audit_trail.py"
      ],
      "table_writers": [
        "src/design_lab/runtime/asset_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/audit-event/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. capability_id plus integration_id as a required pair appears nowhere outside this file. The capability surface the product serves is /api/capabilities (src/design_lab/analysis/capability_library.py), which emits design-lab/capability-library/v1 and is not bound by any schema.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/capability-def.schema.json",
        "design-lab/config/contract-bindings.json:capability-def.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/capability-def.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/capability-def/v1"
    },
    {
      "best_table": "attempt_state",
      "fields": 20,
      "matched_fields": [
        "note"
      ],
      "overlap": 0.05,
      "reason": "Superseded in place. The records the product actually reads and writes are design-lab/capability-evidence-current/v1 (design-lab/config/capability-evidence-current.json) and design-lab/capability-evidence-index/v3, whose fields are capability_id/declared_level/supported_current and actualEvidence/artifact/evidence/run. The only instances of THIS document are the two synthetic fixtures in the tests named above; src/design_lab/governance/reporting.py:337 reads the current record, never this shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/capability-evidence.schema.json",
        "design-lab/config/contract-bindings.json:capability-evidence.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/capability-evidence.schema.json",
      "state": "ADJACENT_TABLE_WRITTEN",
      "table_readers": [
        "src/design_lab/creative/lineage_view.py",
        "src/design_lab/native_patch_submissions.py",
        "src/design_lab/native_tasks.py",
        "src/design_lab/runtime/job_store.py",
        "src/design_lab/runtime/project_backup.py",
        "src/design_lab/task_queries.py"
      ],
      "table_writers": [
        "src/design_lab/runtime/job_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/capability-evidence/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. registry_id and capability_ref appear nowhere outside this file.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/capability-ref.schema.json",
        "design-lab/config/contract-bindings.json:capability-ref.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/capability-ref.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/capability-ref/v1"
    },
    {
      "best_table": null,
      "fields": 3,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. change_set_id/changes appear nowhere in src/. Revision history that does exist is the design-layer superseded_by chain (src/design_lab/design_layer.py), a per-record chain with no change-set document at any boundary.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/change-set.schema.json",
        "design-lab/config/contract-bindings.json:change-set.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/change-set.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/change-set/v1"
    },
    {
      "best_table": "operation_receipt",
      "fields": 6,
      "matched_fields": [
        "receipt_id",
        "status"
      ],
      "overlap": 0.333,
      "reason": "Superseded by a shape this file would reject. The live receipt is design-lab/delivery-receipt/v2, emitted at src/design_lab/interop/delivery_receipt.py:36 and bound by design-lab/schemas/interop-delivery-receipt-v2.schema.json. v2 requires receipt_sha256/job_id/deliverables/axes, none of which this additionalProperties:false document declares, and requires delivery_id/delivered_at/status, which v2 does not carry. Nothing produces the v1 shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/delivery-receipt.schema.json",
        "design-lab/config/contract-bindings.json:delivery-receipt.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/delivery-receipt.schema.json",
      "state": "TABLE_EXISTS_UNWRITTEN",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/delivery-receipt/v1"
    },
    {
      "best_table": null,
      "fields": 3,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. context_id and the revision pairing appear nowhere in src/.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/design-context.schema.json",
        "design-lab/config/contract-bindings.json:design-context.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/design-context.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/design-context/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. allowed_tools/forbidden appear nowhere in src/, apps/, packages/ or integrations/. The MCP surface the product exposes is the host adapter path, which carries no such document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/design-control-mcp.schema.json",
        "design-lab/config/contract-bindings.json:design-control-mcp.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/design-control-mcp.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/design-control-mcp/v1"
    },
    {
      "best_table": null,
      "fields": 4,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. diff_id/before_revision/after_revision appear nowhere in src/.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/design-diff.schema.json",
        "design-lab/config/contract-bindings.json:design-diff.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/design-diff.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/design-diff/v1"
    },
    {
      "best_table": null,
      "fields": 5,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. session_id with lease_state/dirty/checkpoint appears nowhere in src/; DESIGN-LAB holds no document session -- AGENTS.md rules out a second canvas, and no route serves one.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/document-session.schema.json",
        "design-lab/config/contract-bindings.json:document-session.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/document-session.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/document-session/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. ttl_days appears nowhere in src/. Evidence ageing is handled by the ledger projections in src/design_lab/governance/reporting.py, which carry no TTL document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/evidence-ttl.schema.json",
        "design-lab/config/contract-bindings.json:evidence-ttl.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/evidence-ttl.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/evidence-ttl/v1"
    },
    {
      "best_table": "attempt_state",
      "fields": 4,
      "matched_fields": [
        "job_id"
      ],
      "overlap": 0.25,
      "reason": "Nothing implements this. envelope_id and a capability_ref/payload pairing appear nowhere in src/. Execution that exists is recorded in the native_execution_v1 table (src/design_lab/native_bundles.py:101) as request_json/receipt_json per attempt, an envelope-free shape, and design-lab/schemas/execution-result.schema.json is the document that describes it -- which this schema does not describe.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/execution-envelope.schema.json",
        "design-lab/config/contract-bindings.json:execution-envelope.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/execution-envelope.schema.json",
      "state": "ADJACENT_TABLE_WRITTEN",
      "table_readers": [
        "src/design_lab/creative/lineage_view.py",
        "src/design_lab/native_patch_submissions.py",
        "src/design_lab/native_tasks.py",
        "src/design_lab/runtime/job_store.py",
        "src/design_lab/runtime/project_backup.py",
        "src/design_lab/task_queries.py"
      ],
      "table_writers": [
        "src/design_lab/runtime/job_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/execution-envelope/v1"
    },
    {
      "best_table": null,
      "fields": 6,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. session_kind/session_mode/ownership appear nowhere in src/. Host identity that does exist is per-attempt in native_tasks/native_workers, under the job vocabularies, with no host-session document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/host-session.schema.json",
        "design-lab/config/contract-bindings.json:host-session.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/host-session.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/host-session/v1"
    },
    {
      "best_table": null,
      "fields": 4,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. integration_id/executable_ref appear nowhere in src/.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/integration-def.schema.json",
        "design-lab/config/contract-bindings.json:integration-def.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/integration-def.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/integration-def/v1"
    },
    {
      "best_table": "attempt_state",
      "fields": 8,
      "matched_fields": [
        "attempt_id",
        "attempt_no",
        "ended_at",
        "job_id",
        "started_at"
      ],
      "overlap": 0.625,
      "reason": "Contradicted by the store it describes. The live job_attempt table (design-lab/schemas/state/design-lab-state-v1.sql:19, written at src/design_lab/runtime/job_store.py:158) stores job_id/attempt_no/started_at only -- no attempt_id and no status, both required here. The only instances that satisfy this document are the two synthetic fixtures named above; TaskQueries builds attempt records from the DB row, not from this shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/job-attempt.schema.json",
        "design-lab/config/contract-bindings.json:job-attempt.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/job-attempt.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/creative/lineage_view.py",
        "src/design_lab/native_patch_submissions.py",
        "src/design_lab/native_tasks.py",
        "src/design_lab/runtime/job_store.py",
        "src/design_lab/runtime/project_backup.py",
        "src/design_lab/task_queries.py"
      ],
      "table_writers": [
        "src/design_lab/runtime/job_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/job-attempt/v1"
    },
    {
      "best_table": "attempt_state",
      "fields": 3,
      "matched_fields": [
        "attempt_no",
        "job_id"
      ],
      "overlap": 0.667,
      "reason": "One-sided version bump plus a shape nobody emits. src/design_lab/creative/creative_job.py:126 writes design-lab/job-spec/v2 into the job table while design-lab/schemas/state/design-lab-state-v1.sql:16 still defaults the column to v1 and this schema binds v1. The job document that IS validated is design-lab/creative-job/v1 (creative_job.py:27-28 against design-lab/schemas/creative-job.schema.json), whose fields are not job_id/schemaVersion/operation_intent/attempt_no. Only the two synthetic fixtures above satisfy this file.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/job-spec.schema.json",
        "design-lab/config/contract-bindings.json:job-spec.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/job-spec.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/creative/lineage_view.py",
        "src/design_lab/native_patch_submissions.py",
        "src/design_lab/native_tasks.py",
        "src/design_lab/runtime/job_store.py",
        "src/design_lab/runtime/project_backup.py",
        "src/design_lab/task_queries.py"
      ],
      "table_writers": [
        "src/design_lab/runtime/job_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/job-spec/v1"
    },
    {
      "best_table": "rights_decision",
      "fields": 3,
      "matched_fields": [
        "decision"
      ],
      "overlap": 0.333,
      "reason": "Superseded. The jury payload that crosses the boundary is design-lab/assurance-jury-record/v2 (src/design_lab/assurance/human_jury.py:77, bound by design-lab/schemas/assurance-jury-record-v2.schema.json) and the readback envelope design-lab/jury-readback/v1 (src/design_lab/jury_review.py:45). jury_id/score/decision as a required trio appear nowhere in src/; packages/capabilities/quality/jury/JuryRecord.template.json shares the jury_id name but binds design-lab/schemas/jury-record.schema.json instead.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/jury-decision.schema.json",
        "design-lab/config/contract-bindings.json:jury-decision.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/jury-decision.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/assurance/rights_ledger.py",
        "src/design_lab/rights_review.py"
      ],
      "table_writers": [
        "src/design_lab/assurance/rights_ledger.py"
      ],
      "thin_match": true,
      "version": "design-lab/jury-decision/v1"
    },
    {
      "best_table": "approval",
      "fields": 3,
      "matched_fields": [
        "state"
      ],
      "overlap": 0.333,
      "reason": "Superseded. The KnowledgeCandidate exit is bound by design-lab/schemas/candidate-knowledge.schema.json (design-lab/candidate-knowledge/v1) and by assurance-knowledge-candidate-v2.schema.json, named in scripts/deepseek_worktree_reconciliation.py:124. candidate_id/knowledge_type/state as this file requires them appear nowhere in src/.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/knowledge-candidate.schema.json",
        "design-lab/config/contract-bindings.json:knowledge-candidate.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/knowledge-candidate.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/creative/approval.py"
      ],
      "table_writers": [
        "src/design_lab/creative/approval.py"
      ],
      "thin_match": true,
      "version": "design-lab/knowledge-candidate/v1"
    },
    {
      "best_table": "operation_intent",
      "fields": 4,
      "matched_fields": [
        "idempotency_key",
        "idempotency_scope",
        "operation_id",
        "request_hash"
      ],
      "overlap": 1.0,
      "reason": "The concept is live; this document is not. operation_intent is a real table (design-lab/schemas/state/design-lab-state-v1.sql:4, written at src/design_lab/creative/store.py:232) carrying operation_id/idempotency_scope/idempotency_key/request_hash plus created_at -- the same four fields minus schemaVersion, as SQL columns that are never serialised as a JSON document. The idempotency_key the routes accept is checked only by the exact-key-set test in http_service.py body(). This schema is exercised only as the nested $defs of job-spec's synthetic fixture.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/operation-intent.schema.json",
        "design-lab/config/contract-bindings.json:operation-intent.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/operation-intent.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/creative/lineage.py",
        "src/design_lab/creative/store.py",
        "src/design_lab/native_patch_submissions.py",
        "src/design_lab/native_tasks.py",
        "src/design_lab/runtime/job_store.py",
        "src/design_lab/task_queries.py"
      ],
      "table_writers": [
        "src/design_lab/creative/store.py",
        "src/design_lab/runtime/job_store.py"
      ],
      "thin_match": false,
      "version": "design-lab/operation-intent/v1"
    },
    {
      "best_table": "operation_receipt",
      "fields": 4,
      "matched_fields": [
        "attempt_id",
        "operation_id",
        "receipt_id",
        "status"
      ],
      "overlap": 1.0,
      "reason": "Nothing implements this, and the table that shares its name is dead: operation_receipt is created by design-lab/schemas/state/design-lab-state-v1.sql:26 but no INSERT or SELECT for it exists anywhere in src/. Its stale_fence/received_at columns are not declared by this additionalProperties:false document, so a real row would be rejected.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/operation-receipt.schema.json",
        "design-lab/config/contract-bindings.json:operation-receipt.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/operation-receipt.schema.json",
      "state": "TABLE_EXISTS_UNWRITTEN",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/operation-receipt/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. manifest_id with a permissions array appears nowhere in src/. Host authorization that exists is the per-attempt authorization dict built in src/design_lab/native_delivery.py and consumed by the COM adapters, with no permission-manifest document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/permission-manifest.schema.json",
        "design-lab/config/contract-bindings.json:permission-manifest.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/permission-manifest.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/permission-manifest/v1"
    },
    {
      "best_table": null,
      "fields": 3,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. probe_id appears nowhere in src/. Host probing that exists emits design-lab/adobe-host-job/v1 and design-lab/photoshop-native-job/v1 (src/design_lab/adapters/illustrator_com.py:129, src/design_lab/adapters/photoshop_com.py:155), neither of which is this shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/probe-result.schema.json",
        "design-lab/config/contract-bindings.json:probe-result.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/probe-result.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/probe-result/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. cursor_id appears nowhere in src/. Pagination that exists is the opaque after= token on the list routes, carried as a query parameter and never as a document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/projection-cursor.schema.json",
        "design-lab/config/contract-bindings.json:projection-cursor.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/projection-cursor.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/projection-cursor/v1"
    },
    {
      "best_table": null,
      "fields": 2,
      "matched_fields": [],
      "overlap": 0.0,
      "reason": "Nothing implements this. policy_id and max_attempts appear nowhere in src/; retry and requeue behaviour lives as constants inside src/design_lab/native_workers.py and is never published as a policy document.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/retry-policy.schema.json",
        "design-lab/config/contract-bindings.json:retry-policy.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/retry-policy.schema.json",
      "state": "NO_STATE_COUNTERPART",
      "table_readers": [],
      "table_writers": [],
      "thin_match": false,
      "version": "design-lab/retry-policy/v1"
    },
    {
      "best_table": "decision_event",
      "fields": 4,
      "matched_fields": [
        "at",
        "job_id"
      ],
      "overlap": 0.5,
      "reason": "Nothing implements this. The outbox table (design-lab/schemas/state/design-lab-state-v1.sql:52) has event_id/event_type/payload but is created and never written -- no INSERT or SELECT for outbox exists in src/. Events on the wire come from src/design_lab/task_queries.py events(), a different shape with no schemaVersion.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/run-event.schema.json",
        "design-lab/config/contract-bindings.json:run-event.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/run-event.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/creative/decision_ledger.py"
      ],
      "table_writers": [
        "src/design_lab/creative/decision_ledger.py"
      ],
      "thin_match": false,
      "version": "design-lab/run-event/v1"
    },
    {
      "best_table": "operation_receipt",
      "fields": 3,
      "matched_fields": [
        "receipt_id"
      ],
      "overlap": 0.333,
      "reason": "Nothing implements this. run_id paired with a provenance object appears nowhere in src/. Execution records that exist are design-lab/execution-result/v1 and the native_execution_v1 table, neither of which is this shape.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/run-receipt.schema.json",
        "design-lab/config/contract-bindings.json:run-receipt.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/run-receipt.schema.json",
      "state": "TABLE_EXISTS_UNWRITTEN",
      "table_readers": [],
      "table_writers": [],
      "thin_match": true,
      "version": "design-lab/run-receipt/v1"
    },
    {
      "best_table": "design_layer_event",
      "fields": 3,
      "matched_fields": [
        "binding_id"
      ],
      "overlap": 0.333,
      "reason": "Nothing implements this. binding_id/adapter_id/binding as a required trio appear nowhere in src/. src/design_lab/design_layer.py:799 mints a bind id for a design-system binding, an unrelated concept; the adapter contract that is live is design-lab/schemas/adapter-contract.schema.json.",
      "retire_coherent": true,
      "retire_targets": [
        "design-lab/schemas/contracts/runtime-binding.schema.json",
        "design-lab/config/contract-bindings.json:runtime-binding.schema.json row"
      ],
      "route_references": [],
      "schema": "design-lab/schemas/contracts/runtime-binding.schema.json",
      "state": "TABLE_WRITES_THIS_ACTIVITY",
      "table_readers": [
        "src/design_lab/design_layer.py"
      ],
      "table_writers": [
        "src/design_lab/design_layer.py"
      ],
      "thin_match": true,
      "version": "design-lab/runtime-binding/v1"
    }
  ],
  "schemaVersion": "design-lab/inert-contract-survey/v1",
  "stateCounts": {
    "ADJACENT_TABLE_WRITTEN": 2,
    "NO_STATE_COUNTERPART": 17,
    "TABLE_EXISTS_UNWRITTEN": 3,
    "TABLE_WRITES_THIS_ACTIVITY": 8
  },
  "tables": 37
}
```

## 一览表

| schema | 声明字段 | 最相近表 | 重合 | 谁在写这张表 | 分类 | 退役可执行 |
|---|---|---|---|---|---|---|
| `action-plan.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `asset-manifest.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `asset-ref.schema.json` | 6 | asset | 0.17 | — | NO_STATE_COUNTERPART | 是 |
| `audit-event.schema.json` | 9 | audit_event | 0.44 | asset_store.py | TABLE_WRITES_THIS_ACTIVITY | 是 |
| `capability-def.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `capability-evidence.schema.json` | 20 | attempt_state | 0.05 | job_store.py | ADJACENT_TABLE_WRITTEN | 是 |
| `capability-ref.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `change-set.schema.json` | 3 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `delivery-receipt.schema.json` | 6 | operation_receipt | 0.33 | — | TABLE_EXISTS_UNWRITTEN | 是 |
| `design-context.schema.json` | 3 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `design-control-mcp.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `design-diff.schema.json` | 4 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `document-session.schema.json` | 5 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `evidence-ttl.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `execution-envelope.schema.json` | 4 | attempt_state | 0.25 | job_store.py | ADJACENT_TABLE_WRITTEN | 是 |
| `host-session.schema.json` | 6 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `integration-def.schema.json` | 4 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `job-attempt.schema.json` | 8 | attempt_state | 0.62 | job_store.py | TABLE_WRITES_THIS_ACTIVITY | 是 |
| `job-spec.schema.json` | 3 | attempt_state | 0.67 | job_store.py | TABLE_WRITES_THIS_ACTIVITY | 是 |
| `jury-decision.schema.json` | 3 | rights_decision | 0.33 | rights_ledger.py | TABLE_WRITES_THIS_ACTIVITY（thin） | 是 |
| `knowledge-candidate.schema.json` | 3 | approval | 0.33 | approval.py | TABLE_WRITES_THIS_ACTIVITY（thin） | 是 |
| `operation-intent.schema.json` | 4 | operation_intent | 1.00 | store.py, job_store.py | TABLE_WRITES_THIS_ACTIVITY | 是 |
| `operation-receipt.schema.json` | 4 | operation_receipt | 1.00 | — | TABLE_EXISTS_UNWRITTEN | 是 |
| `permission-manifest.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `probe-result.schema.json` | 3 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `projection-cursor.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `retry-policy.schema.json` | 2 | — | 0.00 | — | NO_STATE_COUNTERPART | 是 |
| `run-event.schema.json` | 4 | decision_event | 0.50 | decision_ledger.py | TABLE_WRITES_THIS_ACTIVITY | 是 |
| `run-receipt.schema.json` | 3 | operation_receipt | 0.33 | — | TABLE_EXISTS_UNWRITTEN（thin） | 是 |
| `runtime-binding.schema.json` | 3 | design_layer_event | 0.33 | design_layer.py | TABLE_WRITES_THIS_ACTIVITY（thin） | 是 |
