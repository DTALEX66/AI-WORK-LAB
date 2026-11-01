# core — 核心对象模型

本目录是 DESIGN-LAB **13 个核心对象的规范入口**（对象契约）。

## 13 核心对象

| 对象 | 说明 |
|---|---|
| Brief | 商业目标、受众、渠道、约束、验收标准 |
| ReferenceSet | 来源、权利、用途、hash、提取特征 |
| ResearchFinding | 可引用研究结论 |
| MethodCard | 可复用设计方法 |
| Direction | 互相区分的视觉方向 |
| DesignSystem | tokens、type、grid、components、asset contracts |
| DomainPack | 专业领域的流程、模板、Rubric、Preflight |
| Artifact | 可编辑源文件/导出文件/派生产物 |
| ToolRun | 可审计的 Adapter 执行记录 |
| QualityAssessment | Rubric 评分、缺陷、人工结论 |
| PreflightReport | 可生产检查结果和阻断项 |
| HandoffPackage | 源文件、BOM、许可、版本、回滚 |
| EvidenceRecord | E0–E5、bound tree SHA、责任人、读回 |

## 权威来源

- 对象定义：`docs/OBJECT_MODEL.md`
- 对象 schema：`design-lab/schemas/`（13 份，round-trip 测试存在）
- 适配器映射：`integrations/adapter-registry.json`（DL-DIR-MIG-R1 迁出 design-lab/adapters/）

## 规则

- 所有 adapter 输入输出必须映射到这些对象
- 不得以 Prompt 文本/私有聊天记录/无版本截图充当唯一事实
