# OPEN-DESIGN → DESIGN-LAB 迁移谱系

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。


| 阶段 | 来源 | 历史含义 | 恢复状态 | 现在如何使用 |
| --- | --- | --- | --- | --- |
| 更早起点 | July等早期3D讨论 | 仅后续修复方案二手概述 | UNRESOLVED | 原始9MB对话恢复前不补写确定时间线 |
| 2026-08-07 | OPEN-DESIGN-AUTHORITATIVE-CONTEXT | 旧Open Design-first增强层 | 历史canonical材料 | 保留专业目标，宿主绑定被后继替代 |
| V2→V2.1 | Global Absorption / Visual Quality | 方法、工具、风格谱系、rubrics、Jury | 两包原始hash已匹配 | 知识/质量池继承，激活需rights门 |
| v3→v4.1→v4.2 | Complete / Authoritative / Final TaskPacks | 设计能力、host/tool执行与handoff演进 | 旧压缩包均恢复 | 历史正文保留，任务调度不直接继承 |
| 2026-08-13 | Identity / Full Product Migration | 正式DESIGN-LAB、平台中立、多领域对象 | 两包及架构规划恢复 | 将Open Design移为外部adapter |
| 2026-08-19/20 | 三项目包/Follow-up V1.1/Converged | 轻量UI、外部Adobe/Eagle、知识边界 | 跨项目与本项目材料恢复 | 三项目Authority分离 |
| 2026-08-25 | FINAL-TASKPACK | 宿主/default选择与完整计划 | 历史包恢复 | 与standalone-first冲突部分以现Authority裁决 |
| 2026-09-01/02 | 目录迁移、MiniMax审计、新chat handoff | 目录清理、四种MiniMax身份区分 | 相关材料恢复 | 不重新执行破坏性迁移 |
| 2026-09-04 | 完整修复迁移/manifest/crosswalk | 历史证据总账和ID碰撞治理 | manifest恢复；旧修复正文hash未恢复 | 新较大版本只能作补充 |
| 2026-09-06→08 | R3→R4→R5 | 单账本、资格/实机/交付四轴 | 当前ledger保留前驱 | 全部状态以当前ledger为准 |
| 2026-09-18 | DL-AUTHORITY-2026-09-18-R2 | 当前顶层收敛 | LIVE exactSHA | 旧任务经index/crosswalk进入 |
| 2026-09-21/22 | UI资产/执行提示/前端包 | 交互视觉规范与实现拆分 | 恢复且与源码对比 | 历史稿不是现运行证明 |
| 2026-09-28/29 | 商业前端闭环包 / PR205/206 | UI审计、bundle query纠错、下一轮计划 | 当前代码+补充资料 | 保留已实现增量，不重复P0工作 |

## 名称歧义消除

旧 OPEN-DESIGN / OPEN-DESIGN-Assistance 是本项目的历史身份；Open Design（nexu-io）是外部客户端/宿主；当前 DTALEX66/DESIGN-LAB 是专业设计项目。名称相似不构成源码或Authority同一性。软件 Launcher 显示 Open Design 图标仅表示进入外部宿主，不能改变产品主身份。

旧方法中的 design skill、pipeline/atoms、Visual DNA、Jury、rights、preflight 和 editable handoff 都值得保留；宿主runtime复制、默认安装所有候选、跨项目全局客户端管理进入 REJECT_CORE。未开发的包装、展陈、出版、3D/视频依旧在atlas，按DEFERRED/EVALUATE承接。
