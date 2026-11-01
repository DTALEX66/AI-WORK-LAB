# 跨软件 Agent 规则部署、工作流治理与管理交接摘要

归档日：2026-10-24。归属：WORK-LAB。资料状态：历史执行快照与接收输入，不是新 CURRENT、第二任务账本或全局配置执行器。

## 用户决定与职责

用户最终要求：“总结内容，工作流配置部署治理和管理等 归WORKLAB项目 给我并入WORKLAB的提示词，归档到项目里”。本次完成归档和接收交接；后续执行仍读取项目当时有效的权威、具体授权和机器合同。

- WORK-LAB 负责跨软件工作流、通用协作规范、规则适配、声明范围内的配置部署、漂移检查、备份回退及证据管理。这与项目既有职责一致，不另造产品或控制器。
- 各项目继续拥有业务、项目事实、项目任务与本项目约束。全局规范与项目规则按职责融合，不能直接拼接过时状态、路径与任务指令。
- AAOS 的入口冲突、历史状态与 WORK-LAB 旧路径修复由 AAOS 项目自行执行。本轮未改 AAOS 仓库；WORK-LAB 也不接管 AAOS 的知识领域。
- 一次明确授权的跨项目规则写入，不等于未来对所有项目持续写入的永久授权；适配器的 MANAGE/OBSERVE、字段所有权与 apply_supported 仍以现行合同为准。

## 规则架构与来源

采用四层：统一母版 → 软件原生适配 → 项目约束 → 当前任务与按需工作流。不能假定所有软件读取 AGENTS.md，也不能假定换软件、模型或会话自动继承规则。

当前母版为 `C:/Users/ALEX/AgentRules/AGENT_CORE.md`，v1.0.0，14 条，SHA-256 `e180ea6cff9cceba7009cfc717debcf3de335b911c65c9265cb744d704b7b38a`。`WORKFLOW_MODULES.md` 保持五个按需模块，不将全部工作流灌进每次上下文。WORK-LAB 中 `config/universal-agent/AGENT_CORE.md` 与 `source.json` 是带来源校验的派生快照；当前不能把两者描述成两个独立母版。

治理维护权归 WORK-LAB 不代表本次已迁移 C 盘生效母版。若后续将母版正式纳入仓库，必须一次协调来源声明、renderer、同步器和已部署来源标识，并保留回退链；不得先复制出第二个权威来源。

## 前轮已完成与证据边界

以下是归档收据中的部署结果，来自 2026-10-23 前轮；本次没有重新执行部署或新会话验收。

| 项目 | 收据记录 | 本次归档应如何表述 |
| --- | --- | --- |
| 原生规则写入 | 21 个文件，11 类软件；含 5 个项目的 Cursor/CodeBuddy IDE 各一个规则文件 | 已写入并做文件摘要回读 |
| 文件一致性 | 21/21 回读，母版区段仅一份 | 当时文件检查 PASS，不代表会话加载 |
| 原生装载诊断 | Codex、Hermes、DSH、MiniMax Code 共 4 项，无模型调用 | 安装版原生装载路径诊断 PASS |
| 本地回归 | 51 个投影/同步测试 PASS | 局部测试，不是全产品质量门或 CI |
| 结构与保全检查 | 扩展 159 项、基础 28 项 PASS | 检查有重叠，不累加为独立测试数 |
| 新会话与行为 | NOT_EXECUTED / UNVERIFIED | 不宣称所有软件已实际遵从 |
| 提交、推送、发布 | NOT_EXECUTED | 不能宣称 exact-SHA CI 或发布完成 |

已写入软件与实测版本：Codex Desktop 26.1016.8622.0 / CLI 0.163.0-alpha.11.2、Claude Desktop 2.42304.0.0 的 Code 相关入口、Hermes 0.22.2、DSH 0.2.1-rc.2、CodeBuddy CLI 2.167.0 / IDE 1.106.1、TRAE CN 3.4.4、Qoder CN 0.4.11 Agent 工作台、MiniMax Code 3.1.4、VS Code 1.131.0 内置 Copilot 0.59.0、WorkBuddy 5.8.3、Cursor 3.24.12。版本仅代表前轮发现时点，后续按实际安装版重新核对。

原生入口分别涉及 `.codex/AGENTS.md`、`.claude/CLAUDE.md`、Hermes `SOUL.md`、`.dsh/AGENTS.md`、`.codebuddy/CODEBUDDY.md`、`.trae-cn/user_rules.md`、`.qoder-cn/AGENTS.md`、`.minimax/AGENTS.md`、`.copilot/instructions/*.instructions.md`、WorkBuddy 两层 `SOUL.md`、项目 `.cursor/rules/*.mdc` 与 `.codebuddy/rules/*/RULE.mdc`。保留已有 persona、项目规则与未知字段；具体路径、版本依据、摘要及备份位置见随包报告。

五个项目为 WORK-LAB、ASTRYN、DESIGN-LAB、Obsidian-Assistance、OS External Configuration；各项目既有根 AGENTS/Authority 未因本轮规则直接替换。

WORK-LAB 已有母版快照校验、Codex/Hermes renderer、幂等区段合并与本地测试等未提交改动。本次归档前核对 source-convergence.json 的 13 个源文件摘要仍匹配；不要因接收交接而覆盖或重新生成所有 dirty 文件。Hermes SOUL 经既有受管同步流程发布，混合所有权 config.yaml 未整体覆盖。没有提高适配器 apply_supported 或将规则部署能力泛化成全部业务能力。

## 未完成与接收顺序

1. 先将现有成果纳入 WORK-LAB 的规则来源、适配入口、版本、备份、漂移与验证状态管理；复用现有配置所有权与 Adapter 合同，避免另建台账。
2. Open Design 0.24.1：安装版支持原生 customInstructions，daemon 离线导致只读连接失败，BLOCKED，未写入。待应用在线并核对授权后，只合并该字段并回读；避免 set 的 JSON 输出打印整份配置。
3. MiniMax Design 4.0.4（@hilo）：持久全局入口未确认，UNVERIFIED；可使用单任务全文粘贴，不冒称永久部署。
4. 普通 Claude Chat 账户 UI、Cowork 实际可见路径、Cursor 五个项目以外的用户全局设置，以及其他账户、云端、WSL、新会话加载与行为仍有缺口。按报告中的具体人工步骤执行，不扩展成无边界扫描。
5. Gemini CLI/.gemini 当时未发现，没有创建假配置；OpenHuman 未检测到不等于全机证明不存在。CC Switch、LM Studio 仅为辅助发现，未改模型与配置。
6. 前轮一次环境诊断回显了继承的 STITCH_API_KEY 到工具日志。这里只记录变量名与风险，未复制值或原始日志。原服务端轮换与旧日志处置尚未验证，不能宣称已消除；不擅自修改鉴权。

人工操作和未来验收细节以归档快照中的 `MANUAL_STEPS.md` 为线索，执行前核实现状。没有建立后台自动治理、调度、监控或通知。

## 归档与接收基线

归档容器 ID：`WL-STORE-AGENTRULES-20261024`。规范存储：`docs/history/owner-inputs/20261024/WORK-LAB-AgentRules-Governance-Intake-20261024.zip`。包内保留五份原始规则/任务书、报告、必要收据及部署/验证脚本，逐文件摘要见包内 `MANIFEST.json`。脚本仅保存为来源，未在本次执行。

未批量复制用户规则备份、私有会话、环境输出、凭证、浏览器或模型资料；C 盘原件与前轮备份保留原位。该包为项目派生交接容器，登记在既有 storageContainers 与成员表中，不虚构为 Record 新来源，不改 Record 的 188 文件盘点范围。

归档启动时 HEAD 为 `b5b3a3190e725cf6737372ee7e4f73f12fac584b`，origin/main 为 `6be44584241e7507b8c9f2b81fddd99de7580acc`。工作区包含其他进行中修改；本次仅写归档、导航与必要的派生容器索引展示。历史 SHA 不约束接收方的当前代码，应重新读取实时权威。

完整接收提示词见同目录 `WORK-LAB-INTAKE-PROMPT.md`；本次实际归档检查见 `ARCHIVE-RECEIPT.json`。这些文件不替代唯一 CURRENT，不解除旧任务冻结，不扩大后续执行授权。
