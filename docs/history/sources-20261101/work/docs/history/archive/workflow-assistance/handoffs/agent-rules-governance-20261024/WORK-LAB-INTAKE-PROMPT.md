# 给 WORK-LAB 的接收与并入提示词

请接收跨软件 Agent 通用规则部署的既有成果。用户于 2026-10-24 明确决定：工作流配置、部署、治理和管理等归 WORK-LAB。请将这项成果并入 WORK-LAB 现有治理与受管配置体系，继续处理已授权且可实际完成的部分，不另起产品、账本、规则母版或 CURRENT。

## 先读这些实际文件

工作根：`D:\All projects\WORK-LAB`。

1. 按项目 AGENTS 的顺序，重新核对当前 origin/main 精确提交、WORK-LAB-AUTHORITY.md、机器权威索引、AGENTS、唯一 CURRENT 任务包、OPEN-TASK-REGISTER 及作用域相关合同。保留所有并发 dirty 改动，不使用历史交接重置现场。
2. 阅读 `D:\All projects\WORK-LAB\docs\history\archive\workflow-assistance\handoffs\agent-rules-governance-20261024\SUMMARY.md` 与同目录 `ARCHIVE-RECEIPT.json`。
3. 在现有资料系统查 `WL-STORE-AGENTRULES-20261024` 或 `AgentRules`，校验归档 ZIP 与包内 MANIFEST.json。容器为 `D:\All projects\WORK-LAB\docs\history\owner-inputs\20261024\WORK-LAB-AgentRules-Governance-Intake-20261024.zip`。按需读其中 DEPLOYMENT_REPORT.md、MANUAL_STEPS.md、RULES_INTEGRATION_PLAN.md 与 evidence；不要把原报告的旧日期 PASS 当成当前结果，也不要自动运行包内脚本。
4. 活母版仍为 `C:\Users\ALEX\AgentRules\AGENT_CORE.md` v1.0.0，SHA-256 `e180ea6cff9cceba7009cfc717debcf3de335b911c65c9265cb744d704b7b38a`；WORKFLOW_MODULES.md 为按需工作流。仓内 config/universal-agent 是校验快照，检查 source.json、services/policy/universal_agent_core.py、既有 Codex/Hermes renderer/sync 及相关测试，优先接收已有实现。

## 要并入的内容

- 把跨软件规则、工作流部署、配置来源、原生入口、备份与回退、漂移与验证状态归入 WORK-LAB 既有职责、配置所有权和 Adapter 资料；按现有结构补齐需要的登记与追踪，避免再造管理系统。
- 保持“统一母版 → 软件原生适配 → 项目约束 → 当前任务/按需模块”的结构。软件入口依安装版本与实际运行模式确认，不统一硬塞 AGENTS.md。项目事实、历史状态、权限与业务目标不能混进全局规则。
- 维护单一来源。若需要将 C 盘母版正式迁入 WORK-LAB，先给出具体读写集、兼容路径和可回退的来源切换，再在已授权范围执行；来源标识、renderer、派生快照与生效入口必须一致。不可无声创建第二个权威母版或删除现有 C 盘原件。
- 将前轮 21 个规则文件、4 个原生装载诊断、51 个局部测试等证据接入现有状态表达。必须区分已写入、文件校验、原生装载诊断、新会话实际读取、行为验证；后两者当前尚未完成。不得把局部 PASS 变成全量 CI/运行验收。
- 核对规则融合：全局仅存稳定通用约束，项目保留本项目权威与领域规则，按需模块按任务加载；先消除过时路径和重复段，再合并兼容内容。各项目内部改写仍尊重项目所有者与具体跨项目授权。
- 对 Open Design daemon 离线、MiniMax Design 持久入口不明、Claude Chat/Cowork、Cursor 用户全局、新会话验证等缺口，先核实现状，再完成可做部分；需要 UI、额外授权或新会话的项目保留具体步骤与验收标准，不因此搁置其他可完成项。

## 必须保持的边界

AAOS 项目只改自己的入口冲突和旧路径；本接收任务不要修改 AAOS 仓库，不复活其历史任务。WORK-LAB 维护通用规范与部署治理，各项目继续拥有其业务、知识与设计领域。

按现行 config/config-ownership.json 保留未知字段，不修改模型、服务商、鉴权、权限、端点或未声明全局参数，不覆盖混合所有权的配置全文。过去一次具体规则写入不构成未来永久跨项目写权限，也不改变 apply_supported。

不全盘扫描，不读私有会话、认证库或环境凭证明文；E/F 未获精确授权不得访问。所有新增输出留在本项目。原工具日志曾回显 STITCH_API_KEY，交接只保留位置与风险类型，不复制日志或值，不宣称已轮换。

本提示词授予接收与并入既有治理资料的任务范围；后续全局部署、项目业务实现、付费调用、提交、推送和发布分别依当前用户授权判断。普通可逆且已授权的必要工作直接推进，不重复索要已有授权。

## 交付要求

先实际核对再改动。完成治理并入与可做的必要检查，给出具体写入清单、来源链与回退位置、测试/回读结果、未完成项和接续步骤；继续使用现有唯一任务登记及证据系统。保留 dirty 工作，不自动提交或推送。对无法完成的 UI/新会话验收写明入口、操作内容、预期结果与当前状态，不以建议代替已授权可完成工作。
