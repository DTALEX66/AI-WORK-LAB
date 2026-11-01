# OBJECT_MODEL — 核心对象模型

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：对象契约

## 13 个核心对象

| 对象 | 说明 |
|---|---|
| Brief | 商业目标、受众、渠道、约束、验收标准 |
| ReferenceSet | 来源、权利、用途、hash、提取特征 |
| ResearchFinding | 可引用研究结论，不能直接冒充设计规则 |
| MethodCard | 可复用设计方法；禁止以在世创作者名义模仿 |
| Direction | 互相区分的视觉方向及其理由 |
| DesignSystem | tokens、type、grid、components、asset contracts |
| DomainPack | 专业领域的流程、模板、Rubric、Preflight |
| Artifact | 可编辑源文件/导出文件/派生产物 |
| ToolRun | 可审计的 Adapter 执行记录、版本、参数、输出 |
| QualityAssessment | Rubric 评分、缺陷、人工结论、精修建议 |
| PreflightReport | 可生产检查结果和阻断项 |
| HandoffPackage | 源文件、BOM、许可、版本、回滚、交付清单 |
| EvidenceRecord | E0–E5、bound tree SHA、责任人、时间、读回 |

## 规则

- 所有 adapter 输入输出必须映射到这些对象；
- 不得以 Prompt 文本、私有聊天记录或不带版本的截图充当唯一事实；
- 对象 schema 位于 `design-lab/schemas/`，round-trip 测试必须存在。
