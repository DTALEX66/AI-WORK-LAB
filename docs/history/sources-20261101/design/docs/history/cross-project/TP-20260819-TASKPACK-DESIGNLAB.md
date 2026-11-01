# DESIGN-LAB 任务包（TP-20260819 联邦 · DESIGN-LAB 部分）

> 来源：TP-20260819-TRI-PROJECT-FEDERATION-V2（2026-08-19）。本文件为 DESIGN-LAB 执行子集。基线 main：275702b。执行器：DESIGN-LAB 侧 Agent（WORK-LAB 推送本任务包供检测）。

## 状态约定

PASS / PARTIAL / FAIL / NOT_EXECUTED / BLOCKED。所有完成声明绑定 Exact SHA + 证据路径。不自动 commit/push（需人工批准）。

## 唯一定位（不可漂移）

面向职业视觉设计全链路的设计智能、专业判断、质量控制、生产预检和可编辑交付能力系统。不得变成第二套 PS/Figma/Blender/Agent Runtime/模型网关/Prompt 仓。

## DL-P0（修复任务）

- [ ] DL-P0-001 彻底完成身份中立化：活动身份统一 DESIGN-LAB/设计实验室/design-lab；OPEN DESIGN/OPEN-DESIGN-Assistance 不得作活动产品名；Open Design 只能可选 Adapter
- [ ] DL-P0-002 知识角色重分类：先生成 design-lab/knowledge 依赖图再迁移；权威可复用知识→ArcheAxis；只读投影→非权威；编译 Domain Pack→DESIGN-LAB
- [ ] DL-P0-003 证据状态对齐：当前 Exact SHA 上重核验测试总数/Adapter Registry/Evidence Card/Open Design E1E2/PS Smoke/ComfyUI/H3/MiniGame fixture/162 quarantined/包体积
- [ ] DL-P0-004 MiniGame 边界：minigame-runtime 保留为游戏视觉 fixture，不得恢复独立产品
- [ ] DL-P0-005 外置设计资料转化链：Design assets 的 SourceRecord/RightsRecord/ExtractionJob/CandidateKnowledge/编译产物；大原件外置；未明确版权保持 QUARANTINED

## DL-P1（增强任务）

- [ ] DL-P1-001 Design Token 和 UI/UX 质量底座：评估采用 style-dictionary / storybook / playwright / axe-core（先许可证/依赖体积/锁文件/离线/撤销审计）
- [ ] DL-P1-002 专业工具 Adapter：分级（STABLE: Penpot MCP/ComfyUI API/Style Dictionary；VALIDATION: Blender MCP/Krita AI Diffusion/OpenPencil；QUARANTINED: Flue）；写操作遵循 Brief→IR→ToolActionPlan→Permission→DryRun→人工→执行→回读→Review→Preflight→Handoff
- [ ] DL-P1-003 OpenPencil 试点：仅可选 AI 原生 UI/UX 画布试点；.fig/.pen 读写/设计树/Lint/Token/HTML-CSS/导出/MCP-CLI/Windows-Tauri/回滚哈希；E0→E3 逐级
- [ ] DL-P1-004 Flue 隔离试验：受限 Adapter 后（禁止任意脚本/白名单/参数Schema/路径沙箱/人工批准/备份/JSON回读/无损 smoke）

## DL-P2（研究而非并入）

- [ ] DL-P2-001 Open AI Design Agent（提炼 Brief 分解思想，不并入依赖）/ UIClip（UI 质量信号，不替代人工 Jury）/ OpenCut（等 API 稳定）/ Remotion（许可证后）/ Backstage/Temporal/Kestra（不属于）

## 联邦角色（§6.1）

DESIGN-LAB 拥有：DesignBriefV1 / DesignContextV1 / DesignIRV1 / DomainCapabilityPackageV1 / DesignReviewV1 / QualityAssessmentV1 / ProductionPreflightReportV1 / EditableHandoffPackageV1 / ToolActionPlanV1

## E2E 参与（§11）

- E2E-002 直接设计辅助（Brief → IR → Knowledge Query → Quality → Handoff）
- E2E-003 受治理生产的 Design Review 环节

## 交付文件（reports/current/）

- CLOUD_BASELINE / FEDERATION_MIGRATION_REPORT / EXACT_SHA_VERIFICATION / OPEN_SOURCE_ADOPTION_REPORT / REMAINING_HUMAN_GATES
- ADAPTER_EVIDENCE_RECONCILIATION.json / DESIGN_KNOWLEDGE_ROLE_MAP.md / EXTERNAL_ASSET_INDEX_REPORT.json / DESIGN_TOOL_POC_MATRIX.md

## 人工批准点（§16）

commit/push/迁移/写真实 Adobe 文件/Secret/保护规则/历史重写——均需人工批准。

---

## 执行状态（DESIGN-LAB 侧，2026-08-19）

- DL-P0-001 身份中立化：PASS（FIGMA_PLATFORM_RULES 中立性勘误 + 核验报告）
- DL-P0-002 知识角色重分类：PASS（DESIGN_KNOWLEDGE_ROLE_MAP.md）
- DL-P0-003 证据状态对齐：PASS（CLOUD_BASELINE-EXACT-SHA-VERIFICATION.md，Exact SHA 275702b）
- DL-P0-004 MiniGame 边界：PASS（fixture 300/300，未恢复产品）
- DL-P0-005 外置资料转化链：PASS（extraction-job + candidate-knowledge schema + EXTERNAL_ASSET_INDEX_REPORT）
- DL-P1-001 token/UIUX 底座评估：PASS（OPEN_SOURCE_ADOPTION_REPORT）
- DL-P1-002 Adapter 分级：PASS（DESIGN_TOOL_POC_MATRIX）
- DL-P1-003 OpenPencil 试点：评估完成，待用户批准后进 adapter 开发
- DL-P1-004 Flue 隔离：隔离（不并入）
- DL-P2 研究项：归档（不并入）
- 交付文件 9 份：reports/current/ 下全部产出；聚合链 33/33、Python 248/248
