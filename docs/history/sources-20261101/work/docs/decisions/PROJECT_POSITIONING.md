# WORK-LAB 项目定位（2026-10-19）

WORK-LAB（工作流实验室 / Workflow Lab）是面向个人 AI 工作环境的、客户端中立的
**工作流管理、治理、运行监测与问题闭环系统**。它连接和管理用户使用的 AI Agent、开发工具、
工作流软件、模型服务、插件及相关运行环境；发现和汇总问题，生成解决建议或可交给现有 Agent
的修复任务包/提示词，跟踪验证修复结果，固化可复用方案，并把有长期价值的知识候选提交 AAOS
正式审核与接收。

**不是：** Agent、通用 Agent Runtime、模型网关、通用聊天客户端、所有项目的统一专业审计官。
不替代 Codex、Claude Code、Qoder、WorkBuddy 执行实际开发与故障修复；不接管 DESIGN-LAB 的
专业视觉判断；不取代 AAOS 的正式知识真源；不强制所有任务经过 WORK-LAB。

## 问题闭环

`发现 → 去重/关联 → 问题摘要 → 匹配历史方案 → 建议或 Agent 修复任务包 → 用户/授权策略交接 → Agent 实际修复 → 测试与运行读回 → 关闭或继续 → 方案固化 → 必要时 AAOS 知识候选`

发现、分析、建议生成、已交接、Agent 声称完成、技术验证通过、方案固化、候选提交、
AAOS 接收/审核必须分别记录，不能合并成一个“完成”。Agent 自述、HTTP 200、单一退出码、
文档更新或候选提交都不单独构成验证通过或接收。

## 当前范围（2026-10-19）

其他任务冻结，以 `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`
为唯一 CURRENT；UI 优先任务包已 SUPERSEDED，WUI 与其他任务不继续派工。冻结不等于关闭，
既有状态、证据和缺陷保留。未来能力按 `docs/current/authority-convergence-20261019/ROADMAP.md`
归入 NEXT / FROZEN / DEFERRED / RETIRED，解冻需满足门槛并获得用户明确批准。
当前主线优先验证一个真实最小问题闭环，不以模拟数据冒充接通。

## 三项目边界

AAOS 负责正式知识、来源/证据治理、审核、长期学习与长期项目记忆，保留知识审核、分类、
接收与状态决定权。DESIGN-LAB 负责专业视觉智能、审美方法、Prompt Intelligence、设计能力库、
原生作品与设计专业自动化。WORK-LAB 负责通用工作流管理、治理、运行监测、问题归并、修复协调、
维护方案与通用回执。三方通过版本化 API/Schema/Manifest/Receipt/Candidate 协作，
不共享私有业务数据库，不直接修改其他项目内部目录。

## 数据与读写边界

默认最小采集；详细诊断限定项目/问题/时间/保留期。单位、精度、完整性、新鲜度各自独立表达；
UNKNOWN 不等于正常/零，STALE 不等于 LIVE；断连不判停止，无日志不判失败，`turn_end` 不判项目完成。
Observer 与 sidecar 只读，允许搜索、筛选、复制、展开；写操作必须经过独立授权的 Control，
服务端检查主体、范围、前态、版本、幂等、原生读回和恢复。不得读/打印/复制凭据、`.env`、
认证库、私人 session/memory。只修改 WORK-LAB，不修改 DESIGN-LAB/AAOS，不覆盖未提交改动。

## 架构与权威

保留 React/TS/Vite、Tauri/Rust、Python、JSON Schema；模块与配置权威仍分别由
`.project/governance/module-ownership.json` 与 `config/config-ownership.json` 定义。
顶层依据：`WORK-LAB-AUTHORITY.md` 与 `.project/governance/project-authority-index.json`；
唯一 CURRENT 见 `.project/governance/taskpack-authority-index.json`。
旧蓝图、Atlas、ORCA、Qoder、UI/HUD 计划与历史实现保留为历史或冻结证据，不因名称重新派工；
新计划不证明实现，结构、受控测试、真实客户端、桌面安装、专业接受与发布分别核实。
