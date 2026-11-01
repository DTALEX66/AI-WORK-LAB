# 决策继承与取代账

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。


| ID | 历史主张 | 历史来源 | 当前裁决 | 依据 | 状态 | 保留/改变 |
| --- | --- | --- | --- | --- | --- | --- |
| DEC-01 | 早期 OPEN-DESIGN-Assistance 依附 Open Design | Aug7/8/10 | 平台中立、standalone-first | Sep18 Authority | SUPERSEDED | 保留适配器，废弃强制宿主依赖 |
| DEC-02 | OPEN-DESIGN 项目名 | Aug13 identity migration | DTALEX66/DESIGN-LAB；Open Design 为外部宿主 | product definition | RENAMED / MIGRATED | 不删除旧证据 |
| DEC-03 | MiniGame 可独立增长为游戏产品 | 旧任务/fixture | Game Visual 领域样例 | boundary contract | REJECT_CORE | 视觉资产能力保留，游戏引擎/商业产品不进入核心 |
| DEC-04 | V2 全局吸收池 adopt-now | V2 pack | SourceRecord + quarantine + rights review | source registry policy | SUPERSEDED_FOR_LOADING | 162候选不得默认激活 |
| DEC-05 | V2.1视觉质量总分门槛 | V2.1 pack | 24轴+硬失败+人工专业判定 | visual-quality model | RETAIN / EVOLVE | 旧82阈值不是所有域通用验收 |
| DEC-06 | 每包独立任务ID和状态 | v3/v4/R3/R4/R5 | 9/18统一入口+唯一machine ledger | Authority | CONVERGED | 历史ID必须带source-qualified key |
| DEC-07 | 默认接管WORK用户客户端状态 | 跨项目讨论 | 仅设计领域工作流；全局归WORK | boundary contract | REJECT_CORE | 设计MCP诊断保留 |
| DEC-08 | 设计资产自动沉淀知识库 | 历史跨项目设想 | rights + human gate的KnowledgeCandidate | boundary contract | RESTRICTED | 禁止原始客户资产默认外溢 |
| DEC-09 | Lite/Launcher/MCP入口 | 用户最新方向 | 单产品轻量入口+局部适配诊断 | 本次建议，待映射 | PROPOSED_COMPATIBLE | 不建立第二runtime |
| DEC-10 | 组件库数量覆盖意味着成熟 | 9/28 W02 | 兼容性+可访问性+安装后体验共同验收 | 本次研究建议 | CHALLENGE_NOT_OVERRIDE | 对现有方案做小范围benchmark |
| DEC-11 | 下位E4=release/E5=商业 | 旧EVIDENCE_POLICY | E4独立接受/E5发布可重复 | Authority | LOWER_DOC_DRIFT | 只修下位描述，不调高现有证据 |
| DEC-12 | bundle kind design-bundle用作DB筛选 | 旧后续计划 | DB other+bundle-%；API label design-bundle | main PR206 | CORRECTED | 列表route仍未实现 |
| DEC-13 | H3安装文件=完整本地设计链 | 历史模型目标 | IR hosted与本地Base拆分资格 | MiniMax官方README+本地报告 | NOT_ESTABLISHED | 不安装模型、不承诺8GB全链 |
| DEC-14 | Avalonia/React/Tauri立刻重写 | UI候选方案 | 保留strictTS，真实需新增时ADR | Authority+本次建议 | DEFERRED | 原生壳是部署选择不是产品核心 |


日期链只说明证据顺序；本报告没有修改任何决策。更早 July 起点依赖未恢复对话，不能用现有二手摘要补写成确定事件。