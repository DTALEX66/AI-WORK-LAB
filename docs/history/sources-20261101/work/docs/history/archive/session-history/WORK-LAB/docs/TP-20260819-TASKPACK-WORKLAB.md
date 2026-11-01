# WORK-LAB 任务包（TP-20260819 联邦 · WORK-LAB 部分）

> 来源：TP-20260819-TRI-PROJECT-FEDERATION-V2（2026-08-19）。本文件为 WORK-LAB 执行子集。基线 main：7a8c90b（漂移自任务包基线 979ec88，增量=HERMES DSH 交接文档）。

## 状态约定

PASS / PARTIAL / FAIL / NOT_EXECUTED / BLOCKED。禁止用 DONE 代替证据状态。所有完成声明绑定 Exact SHA + 证据路径。

## WL-P0（修复任务）

- [x] WL-P0-001 定位与注册表去硬编码：software-registry.json 已创建（7 软件注册，client-neutral）
- [x] WL-P0-002 纠正专业能力越界：contract-catalog domain-pack owner → external-design-lab + CapabilityPackageReference
- [x] WL-P0-003 运行记忆降级：memory-record → runtime-context-record/v1（TTL 86400 自动 + authoritative=false 强制，schema+growth_watcher 更新，测试 PASS）
- [x] WL-P0-004 Observer 写入否定测试：tests/test_observer_readonly.py（7 写路径拒绝 + 读允许）
- [x] WL-P0-005 配置控制面：config_control_plane.py（六层 + SoftwareRegistration + effective/diff/apply/readback/drift/rollback）

## WL-P1

- [x] WL-P1-001 当前证据真实性：CURRENT_STATE_TP20260819.json（真实 head/remote/dirty/objects 回读）
- [x] WL-P1-002 仓库减重：WORK_LAB_SIZE_REPORT.md（103 objects/278KB，DSH 外置，无重写）

## WL-OSS（开源组件 PoC）

- [x] WL-OSS-001~008：OPEN_SOURCE_ADOPTION_REPORT.md（8 项评估，全部评估态未安装）








## 联邦契约（§6）

- [x] 联邦契约：00-governance/federation/ 三件套已建

## E2E 契约测试（§11）

- [x] E2E 配置闭环 + 失败路径：tests/test_federation_e2e.py（14 测试，含 E2E-004 配置闭环 + 6 失败路径）
- [ ] 15 失败路径 fixtures

## 知识迁移试点（§12）

- [ ] 3 对象试点：**DEFERRED（用户指示：OS 未完善，等指示再做）**
- [ ] 通过条件：可回读/引用可用/原始不丢/权威明确/回滚成功

## 交付文件（reports/current/）

- CLOUD_BASELINE / FEDERATION_MIGRATION_REPORT / EXACT_SHA_VERIFICATION / OPEN_SOURCE_ADOPTION_REPORT / CONTRACT_CONFORMANCE_REPORT / REMAINING_HUMAN_GATES
- CONFIGURATION_INVENTORY.json / CONFIGURATION_MIGRATION_READBACK.json / SOFTWARE_COMPATIBILITY_MATRIX.md / OBSERVER_READ_ONLY_PROOF.json

## 人工批准点（§16）

commit/push/PR/merge/release/迁移/Secret/保护规则/历史重写——均需人工批准。