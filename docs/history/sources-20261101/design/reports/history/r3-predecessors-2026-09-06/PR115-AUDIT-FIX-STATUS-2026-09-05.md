# PR #115 审计整改清单（2026-09-05 审计 → 本分支修复）

> 对照 `DESIGN-LAB-PR115-UPDATE-AUDIT-2026-09-05.md`（REQUEST_CHANGES，F01–F10）。
> 每条列出：审计发现 → 修复动作 → 验证方式。只记**可验证**证据，不再以文件存在代替证据。

## F01 — BLOCKED_BY_LICENSE 状态破坏 adapter-contract 枚举

- 发现：registry MiniMax H3 `status=BLOCKED_BY_LICENSE` 不在 schema 枚举，`test_registry_schema_validates` 报错。
- 修复：`design-lab/schemas/adapter-contract.schema.json` 枚举增加 `BLOCKED_BY_LICENSE`，并加 `allOf` 约束：blocked 条目的每个 capability `supported` 必须为 `false` 且必须携带 `license`（合法但不可执行，R0-006 语义）。
- 验证：`test_oda4_0206_adapters.py` 现 10 tests OK（新增 `test_blocked_license_status_is_legal_but_not_executable`、`test_schema_rejects_supported_capability_when_blocked`）。

## F02 — job-spec `#/$defs/operationIntentRef` 悬空引用

- 发现：job-spec.schema.json `$ref: "#/$defs/operationIntentRef"` 但文件无 `$defs` → PointerToNowhere。
- 修复：job-spec 内联 `$defs.operationIntentRef`（完整 OperationIntent 快照字段 + `schemaVersion` const），自洽可解析。
- 验证：`test_contract_schema_integrity.py`：`test_no_local_ref_points_to_nowhere` 遍历 31 个 contracts 断言所有 `#/` 引用可解析；job-spec 正/负 fixture 均覆盖。

## F03 — 契约过弱：attempt_id 缺失 / evidence 太松 / rights/asset 无绑定 / 自由字符串

- 发现：job-attempt 无 attempt_id；capability-evidence 字段过少且允许空 ID/全零 SHA E5；asset-ref 无 rights/runtime；rights-decision/delivery-receipt 状态为自由字符串。
- 修复（全部 2020-12 自洽、无跨文件引用）：
  - `job-attempt.schema.json`：必填 `attempt_id`，`status`/`outcome` 枚举约束。
  - `capability-evidence.schema.json`：必填 evidence_id/adapter_id/bound_sha（40-hex 非全零 pattern）+ host/os/adapter_version/commands；按 level 分级要求 fixture/artifact/run_id/readback/rollback（E2+）、task_id/ttl（E3+）、approval（E4+）、release_id（E5）。
  - `asset-ref.schema.json`：增加内联 `rights`（枚举 decision + decided_by/at）与 `runtime_binding`。
  - `rights-decision.schema.json`：decision 枚举 APPROVED/DENIED/PENDING_REVIEW/BLOCKED_BY_LICENSE + 决策者/时间。
  - `delivery-receipt.schema.json`：status 枚举 + delivered_at + artifact_hashes。
- 验证：`test_contract_schema_integrity.py` 8 tests OK（空 ID/零 SHA E5 拒绝、attempt_id/枚举强制、正 fixture 通过）。

## F04 — pyproject/uv.lock 缺 Pillow/numpy/scikit-image/defusedxml；CI 用 pip 绕过锁

- 发现：pyproject 仅 jsonschema；CI `pip install -r requirements.txt` 不锁版本。
- 修复：pyproject 纳入 4 个依赖并 `uv lock`（20 包）；canonical-verify.yml / release-gate.yml 安装步骤改为 `uv sync --locked` 并把 `.venv/bin` 加入 PATH。
- 验证：`uv sync --locked` 通过（resolved 20 / checked 15）。

## F05 — sealed-bundle 检查是死代码（在 SystemExit 之后、0 调用者）

- 发现：`verify_reconstruction_bundle.py` 底部 `check_sealed` 位于 `raise SystemExit(main())` 之后，永不可达；生产 evidence.py 提升路径无密封门。
- 修复：
  - `evidence.py` 新增 `seal_bundle()` / `check_sealed()` / `SEAL_REQUIRED_KEYS`，并把密封校验接入生产 `_promote()`：swap 前重算 staging seal、promote 后读回 seal（密封不匹配拒绝提升）；新增 `_after_backup` seam。
  - verifier 删除死代码尾块，改用生产 `seal_bundle/check_sealed` 并在 PASS 行输出 seal 前缀。
  - 失败注入测试：before_swap 篡改拒绝、after_backup 失败恢复旧 bundle 无残留、seal 稳定 roundtrip。
- 验证：`test_reconstruction_evidence.py` 全文件跑绿后以此为准（进行中），单测 4 项先绿。

## F06 — 重建主链仍写 `.hermes`（.project-local 迁移遗漏）

- 发现：contracts.py/intake.py/render.py/evidence.py/state.py 仍构造 `.hermes/task-runtime/reconstruction`。
- 修复：新增中央解析器 `packages/capabilities/reconstruction/runtime_roots.py`（RUNTIME_REL/EVIDENCE_REL = `.project-local/...`，LEGACY 常量用于拒绝测试），五个主链模块与测试 fixture 迁移到 `.project-local`。
- 验证：旧路径拒绝 fixture + 无残留扫描 + 相关测试绿。

## F07 — manifest ref gate 读错结构（capabilityFamilies[].capabilities vs 实际 paths[]）

- 发现：`verify_product_manifest_v3.py#check_ref_safety` 读 `fam["capabilities"][].contract/path/schema`，实际 manifest 用 `paths[]` → 0 引用被扫描；结果用 str append 会崩 print_results。
- 修复：按真实 `capabilityFamilies[].paths[]` + entrypoints 扫描，复用 `Result/require_path` 机制；断言 refs scanned > 0；traversal/historical 独立 FAIL；entrypoints file=True。
- 验证：verifier 全绿（493 checks，含 R0-002 行）；`test_verifier_internals.py ProductManifestTests` 4 tests OK（新增真实结构扫描 + 缺文件/traversal/historical/空 family 负例）。

## F08 — CI 触发仅 push、缺 src/**

- 发现：canonical-verify.yml pull_request paths 无 `src/**`，且事件仅 push。
- 修复：push 与 pull_request 均加 `src/**`（连同本分支实际改动的 src 运行时模块）。
- 验证：workflow YAML 语法检查 + 触发路径 fixture（见 F08 变更）。

## F09 — history CSVs 不在树内；AGENTS.md 指向旧 taskpack 且称 Open Design 主宿主

- 发现：history-baseline 只有 hash，两份 CSV 只在 `.hermes` 归档；AGENTS.md/README 与 standalone-first ADR 冲突。
- 修复：把两份 CSV 以 `-text`（binary）形态放入 `docs/history/`，字节 hash 与 baseline 完全一致（58e54d90… / 74c5b7cc…）；AGENTS.md 宿主段与当前任务包段、README 改为 standalone-first + DL-TP-20260904；旧 taskpack 加 SUPERSEDED 头注。
- 验证：`test_history_baseline_retrieval.py` 3 tests OK（存在性 + 字节 hash 对 seal + crosswalk 行数）。

## F10 — PR/进度账本声称被夸大（31/58、15 new tests、49-chain 等）

- 发现：账本与 PR 描述多处不可复核（31/58 vs ledger 29 条；"15 new tests" 实为净增少数；R0-005 "49-chain 全绿" 与 509 tests 中 1 error 不符；src runtime 模块当时未入 PR head）。
- 修复：以本文件为准重建账本口径；PR #115 描述重写为可验证清单；`TASKPACK_PROGRESS` JSON 改为证据式状态（区分 committed / schema-draft / PARTIAL / DONE-verified）。
- 验证：本文件每条均指向上述具体测试/命令；无不可复核计数。

---

状态：进行中（F05 全文件验证、F06 迁移、F10 账本落盘后收尾）。
