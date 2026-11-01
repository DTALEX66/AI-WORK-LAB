# 三项目联邦契约（TP-20260819 §6）

> 权威位置：WORK-LAB/00-governance/federation/。WORK-LAB 保存联邦注册表和传输协议，不因此成为其他项目的父项目。

## 所有权

| 项目 | 拥有契约 |
|---|---|
| ArcheAxis | KnowledgeQueryV1 / KnowledgeProjectionV1 / CandidateSubmissionV1 / CandidateReceiptV1 / EvidenceIntakeV1 / LearningRecordV1 / ProvenanceRecordV1 / RightsRecordV1 |
| WORK-LAB | WorkUnitV1 / CapabilityRegistrationV1 / SoftwareRegistrationV1 / RuntimeRegistrationV1 / PermissionDecisionV1 / DispatchRequestV1 / DispatchReceiptV1 / CheckpointV1 / ApprovalV1 / RecoveryPlanV1 / AcceptanceResultV1 / EvidenceEnvelopeV1 |
| DESIGN-LAB | DesignBriefV1 / DesignContextV1 / DesignIRV1 / DomainCapabilityPackageV1 / DesignReviewV1 / QualityAssessmentV1 / ProductionPreflightReportV1 / EditableHandoffPackageV1 / ToolActionPlanV1 |

## 公共信封字段（所有跨项目消息）

schemaVersion / messageId / producer / consumer / correlationId / workUnitId（如适用）/ sourceCommit / contentHash / classification / rightsStatus / createdAt / idempotencyKey

## 禁止耦合

1. 禁止共享数据库
2. 禁止跨仓库相对路径导入
3. 禁止读取另一个项目内部实现目录
4. 禁止复制另一个项目权威 Schema 后手工维护
5. WORK-LAB 不得重新拥有 domain-pack；只能引用 CapabilityPackageReference
6. memory-record 限定为带 TTL 的运行上下文，不是长期知识

## 使用

- federation-registry.v1.json：三项目注册表（角色/所有权/耦合规则）
- federation-envelope.v1.schema.json：公共信封 JSON Schema
- 其他仓库只保存自动生成、只读、带来源 SHA 和 content hash 的投影
