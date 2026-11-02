# 三项目全量审计、定位重载与跨软件连续性整改总报告

审计对象：

- DTALEX66/WORK-LAB
- DTALEX66/ArcheAxis-Knowledge-OS
- DTALEX66/DESIGN-LAB

审计日期：2026-08-24；R4 增量审计日期：2026-08-25  
审计方式：只读；未修改、提交、推送、合并或发布三个仓库  
结论基线：当前 main 精确 SHA + 当前可检索历史对话 + ChatGPT 资料库 + 当前 CI/Release 回读

修订状态：**R4 / ChatGPT 三项目完整对话导出 × 云端仓库 × R3 全仓审计综合裁决版**  
本次补充：完整解析 `WORK-LAB完整项目对话与时间线汇报.md`、`DESIGN-LAB完整项目对话与时间线汇报.md`、`ArcheAxis完整项目对话与时间线汇报.md`，从 1,151,158 行、44,740,080 字节中去除每会话重复 JSON，恢复 40 个逻辑会话、804 条用户消息的原始时间线，并与 2026-08-25 三仓当前 main 及 R3 全仓审计逐项对照。  
执行权威：第 26—37 节是 R4 新增裁决，取代第 21—25 节关于“三份短汇总”和“仍缺完整云端导出”的旧边界；如与前文快照冲突，以用户最新明确决定、第 26—37 节及当前 exact-SHA 可复核事实为准。

---

## 0. 先给结论

你的三点概括方向基本正确，但 WORK-LAB 的表述需要一个关键修正：

> WORK-LAB 应当拥有跨软件、跨项目的全局治理协议、用户级 Desired State、工作流、TaskPack、权限、适配器、分发与审计；但每个项目的专业语义配置、业务事实、数据库和项目内部状态仍由该项目自己拥有。WORK-LAB 管理其指针、合同、约束、执行与回执，不能把三个项目吸收到一个中央仓库。

三个项目应重新锁定为：

| 项目 | 正确定位 | 唯一正式 UI | 明确不是 |
|---|---|---|---|
| WORK-LAB | 面向所有现有及未来工作流软件的用户级全局治理与执行控制面；管理规则、技能、插件/MCP 声明、便携 Memory 元数据、能力、配置覆盖层、TaskPack、权限、适配器、交付与观测 | 控制/配置面负责 Desired State、计划与受控命令；Observer 只读展示真实运行与证据 | Agent Runtime、聊天软件、模型网关、其他项目的业务数据库 |
| ArcheAxis Knowledge | 本地优先、原件保全、证据可追溯的人机双向重型学习与可信知识治理系统；是唯一知识治理与 Candidate→Review→Verified 权威 | ArcheAxis 桌面学习/知识工作台 | 通用 Agent OS、Agent Runtime、普通 RAG/聊天壳、文件管理器 |
| DESIGN-LAB | 面向平面、UI/UX、品牌、电商、包装、空间、3D、动效、音视频、游戏视觉等专业设计的、平台中立的设计智能与生产能力系统；通过适配器操控真实软件并形成可编辑交付 | 轻量 DESIGN-LAB Workbench 负责需求、方向、质量、预检、交付与证据；真正编辑仍在宿主软件 | 第二套设计画布、第二聊天客户端、模型网关、默认绑定 Open Design |

当前最严重的问题不是“AI 有没有读摘要”，而是：

1. 权威内容分散在仓库、资料库、历史对话、生成摘要和本机路径中，没有一个可验证的启动协议。
2. 一些文件自称“唯一权威”，但没有 Owner 确认状态、来源哈希、失效时间和替代关系。
3. WORK-LAB 权威索引指向的唯一当前 WLR 任务包正文不在仓库，只在 ChatGPT 资料库中。
4. WORK-LAB 宣称适配当前七类软件，但当前适配器证据几乎全部为 UNVERIFIED；除 Hermes 外均为 quarantined/blocked。
5. ArcheAxis 历史 UI 契约很清楚，但没有被转成生产前端的强制验收合同；换到 React 后保留了“名称”，没有保留完整交互语义。
6. WORK-LAB Observer 当前生产 React 前端存在会改变事实含义的映射错误，而且 CI 没有构建或测试这套生产前端。
7. DESIGN-LAB 的结构验证很强，但“能操控所有设计软件”目前仍主要是目标能力，不是当前实证能力。

因此，这不是简单补一份更长摘要能解决的问题。需要建立“仓库内可验证的项目连续性协议”，让 Hermes、Codex、DeepSeek Harness、CC Switch、OpenHuman、Open Design、GitHub 以及未来替代软件都从同一权威链生成各自投影。

---

## 1. 审计覆盖范围与证据边界

### 1.1 已完成的覆盖

- 对三个仓库当前 main 共 5,587 个 tracked files 做了机械清单、类型、体积、重复内容、机器路径、Markdown 本地链接和敏感模式扫描。
- 深读根级规则、产品定位、权威索引、TaskPack、跨项目合同、适配器注册表、状态报告、CI、发布台账、生产 UI、Tauri 配置、测试入口及关键实现。
- 回读三个精确 SHA 对应的 GitHub Actions。
- 检索当前账号中可由 Personal Context 检索到的历史对话事实。
- 检索并读取 ChatGPT 资料库中的 WORK-LAB WLR 总任务包、ArcheAxis 项目交接、前端审计/重构、OPEN DESIGN 历史权威上下文等关键材料。
- 将当前仓库事实、用户最新明确表述、历史 Owner 决策、助手生成建议和已过时材料分开定级。

### 1.2 必须诚实说明的边界

本报告不是 ChatGPT 账号全部聊天的原始逐字导出。能够核验的是：

- 当前对话中你的明确决定；
- Personal Context 能检索到的相关历史事实；
- ChatGPT 资料库中可搜索和读取的文件；
- 三个 GitHub 仓库当前及 Git 历史；
- 当前公开 CI/Release。

删除的对话、未被索引的会话、其他软件私有会话正文、OpenHuman/Hermes/Codex 的私有运行记忆不能被本报告假装为已读取。后续应把任何真正必须永久继承的决定迁回项目仓库的权威文件，而不是继续依赖“账号里应该记得”。

### 1.3 本报告使用的权威优先级

| 等级 | 来源 | 用途 |
|---|---|---|
| A0 | 用户最新明确决定 | 产品定位、边界、保留/废止、优先级 |
| A1 | 当前 main 精确 SHA、CI、Release、真实代码与测试结果 | 当前实现事实 |
| A2 | 仓库内 binding/ACTIVE 权威文件与机器注册表 | 稳定产品/治理合同 |
| A3 | 有路径、SHA、哈希、状态和 supersession 的当前 TaskPack/交接 | 当前执行入口 |
| A4 | 历史对话、资料库任务包、旧蓝图 | 需求来源和历史证据 |
| A5 | 助手总结、自动生成报告、Mock UI、规划建议 | 候选，不自动成为权威 |

以后所有重要记录必须显式使用以下状态之一：

- USER_CONFIRMED
- REPO_VERIFIED_FACT
- HISTORICAL_DECISION
- ASSISTANT_PROPOSAL
- SUPERSEDED
- UNKNOWN

文件标题里写“唯一权威”不能替代 Owner 确认和机器可验证的权威链。

---

## 2. 为什么换软件后会丢上下文

### 2.1 产品机制层

OpenAI 官方说明已经明确：

- ChatGPT Web 使用 ChatGPT memory；
- 本地 Codex 客户端使用另一套本地 memory store 与控制；
- 必须遵守的团队规则应放在 AGENTS.md 或已提交文档中，Memory 只能作为辅助回忆层，不能作为唯一规则来源；
- Memory 生成可能延迟，也可能跳过某些会话。

参考：

- [OpenAI Docs：Memories](https://learn.chatgpt.com/docs/customization/memories)
- [OpenAI：Run long horizon tasks with Codex](https://learn.chatgpt.com/blog/run-long-horizon-tasks-with-codex)

第二篇官方材料给出的长期任务做法正是把 spec、plan、constraints、status 和 decisions 外置到仓库文件中，而不是期待模型永久记住一个长对话。

因此，“同一个 GPT 账号”不等于所有软件、所有会话、所有本地 Codex host、所有插件都共享一个完整、实时、无损的上下文数据库。

### 2.2 你这三个项目中的具体断点

| 断点 | 当前证据 | 结果 |
|---|---|---|
| 当前任务包不在仓库 | WORK-LAB 的 taskpack-authority-index.json 声明唯一 CURRENT 为 WORK-LAB-FORWARD-RECONCILIATION-2026-08-20，但对应正文文件不存在；资料库中存在 741 行版本 | Codex 只读仓库时无法恢复 WLR-000～960 的完整约束 |
| 摘要没有权威状态 | 多份资料库文档自称 ACTIVE_CONVERSATION_BASELINE 或“唯一权威”，其中不少是 model_generated | 新软件无法知道它是用户批准、助手建议还是历史阶段产物 |
| 同一决策复制三份 | THREE_PROJECT_LAYERING_DECISION.md 在三个仓库内容相同或仅差末尾换行 | 后续任一仓库修改都会产生三份“都像权威”的分叉 |
| 名称和身份多次迁移 | Cognitive-Loop-OS、ArcheAxis OS、ArcheAxis Knowledge；OPEN-DESIGN-Assistance、Open Design、DESIGN-LAB 同时存在 | 检索召回容易把历史定位当当前定位 |
| 当前适配器没有实证 | WORK-LAB 10 个 adapter 中只有 Hermes status=active，但 detection 仍 UNVERIFIED；其他当前软件为 quarantined 或 blocked | “跨软件加载”目前是合同意图，不是可靠运行能力 |
| UI 只存在于图片/提示词 | ArcheAxis 历史 UI 明确七区 Shell，但生产 React 没有同等级的 UI Contract、截图基线和路由—数据验收 | 换前端技术或执行器时，只保留了六空间名称，交互结构丢失 |
| 报告会过期但 CI 不拦截 | DESIGN-LAB reports/current 仍绑定 a6fdc5e，当前 main 为 9468c40；canonical gate 仍通过 | 新执行器读取“current”报告会得到旧事实 |
| 没有 Resume Receipt | 三仓库没有统一的 active task、HEAD/tree、dirty、UI baseline、测试范围、下一动作交接收据 | 每次换软件都要重新猜测 |

结论：

> AI 不是完全“不看摘要”，而是软件未必拿得到同一摘要；即使拿到，也没有可靠办法判断摘要是否完整、最新、Owner 批准、与当前代码相符。摘要越多、互相越矛盾，错误恢复的概率反而越高。

---

## 3. 第一轮快照基线（不可单独作为当前执行真相）

本节保留第一轮扫描时的可复核快照，便于追踪结论如何形成。三个本地审计副本均为 partial/blobless clone；本轮虽已遍历全部可见 refs、提交元数据和当前树，但部分历史删除文件的 blob 正文不在本地。因此本节不能被理解为“所有历史正文已经逐字读取”。完整边界和缺口见第 19 节。

| 项目 | main HEAD | tree | commits | tracked files | 当前精确 SHA CI | Release |
|---|---|---|---:|---:|---|---|
| WORK-LAB | c2cb6dccf6aad82aa3df5ecebed2383e5ab06d41 | 854a6f9a0a8e6394c542976c6778bdc2dd130d7a | 503 | 1,084 | [work-lab-gate 成功](https://github.com/DTALEX66/WORK-LAB/actions/runs/32652777802) | 有历史 Observer 发布；无统一当前产品 Release |
| ArcheAxis | bf0c48396c751647ac76ee4578bc38f44888a23e | 9ce8ffae2d4766a84880d7249b4cafd3b4a17f55 | 672 | 1,161 | [CI 成功](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/actions/runs/32672672037) | 最新公开 [v0.6.10](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/releases/tag/v0.6.10)，9 个资产 |
| DESIGN-LAB | 9468c40ea8b739499b06e80a7edf5d5542659778 | 4032b10dc842f5949652400647ccda883aac0f24 | 260 | 3,342 | [Canonical Verify 成功](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/32627455106) | 无 tag / Release |

GitHub 报告的仓库 size 分别约为：

- WORK-LAB：418,177 KiB；
- ArcheAxis：39,524 KiB；
- DESIGN-LAB：206,729 KiB。

而当前 tracked worktree 内容约为 8.00 MiB、22.77 MiB、49.84 MiB。WORK-LAB 和 DESIGN-LAB 的 Git 历史/分支/旧对象体量明显大于当前有效产品树，应单独治理，但不能用破坏性历史重写直接处理。

### 3.1 当前验证结果的正确解释

WORK-LAB：

- 当前精确 SHA GitHub Actions 全部 job 为 success。
- 但 advertised canonical 本地命令中的 external-libraries-index gate 在非原开发机运行时失败，因为验证器把索引位置写死为 D:\All projects\WORK-LAB\...。
- GitHub CI 没有调用该 gate。
- Observer job 测试 Python 和 legacy web，不构建 production React frontend。

ArcheAxis：

- 当前精确 SHA CI 包括 Python、浏览器、Windows runtime、desktop build 和 installer lifecycle，整体证据强。
- 但 scripts/ci/run_tests.sh 在 Linux 直接因 pwd -W 失败；这是本地测试入口可移植性缺陷，不否定 GitHub CI 结果。

DESIGN-LAB：

- 统一验证链 43/43 通过。
- 官方选择的 scripts/run_python_tests.py 运行 250 tests，4 skipped，成功。
- 直接在仓库根运行 pytest -q 会在 vendored/imported 子树出现 7 个 collection errors；说明“受控主项目测试”成功，但“全仓任意测试发现”并不成立。
- Evidence Cards 为 12 张，但 authoritative_accepts=0；人类校准仍未完成。

---

## 4. 三项目重新定位与所有权

### 4.1 WORK-LAB

建议冻结为：

> WORK-LAB 是用户所有 AI/工作流软件与所有项目之间的全局治理和执行控制面。它拥有全局协议、用户级配置源、工作流资产、TaskPack、权限、适配器、分发、审计与只读观测；每个项目仍拥有自己的业务语义、PROJECT_OVERLAY、数据库和产品 UI。

WORK-LAB 拥有：

- 全局配置 Schema、field ownership、Desired State 与用户 overlay；
- Rules、Skills、插件/MCP 声明、便携 Memory 元数据和能力目录；
- 软件注册、项目注册、Capability Registration；
- TaskPack、WorkUnit、Approval、Checkpoint、Recovery、Acceptance；
- Adapter contract、生成各软件 native projection 的编译器；
- 跨项目 federation envelope、路由、权限与回执；
- Workflow Assistance 主动控制面；
- Observer 严格只读投影。

WORK-LAB 不拥有：

- ArcheAxis 的 Knowledge/Evidence/Learning 数据库；
- DESIGN-LAB 的专业设计语义、Domain Pack 内容和产品交付事实；
- 各软件的凭据、会话正文、私有 Memory 正文、缓存和账号状态；
- 通用模型调用网关、Agent Runtime 或聊天 UI；
- 项目内部配置的专业含义。

PROJECT_OVERLAY 的正确规则是：

> 项目自己拥有配置内容；WORK-LAB 拥有全局 Schema、边界、注册指针、验证、分发和执行协议。

### 4.2 ArcheAxis Knowledge

建议冻结为：

> ArcheAxis Knowledge 是本地优先、原件永久保全、证据驱动、面向个人的人机双向重型学习和可信知识治理系统。它是三个项目中唯一拥有 Candidate→Review→Verified 知识治理权的项目，但不是 Agent OS。

它拥有：

- Source / RawAsset / Conversion / LossReport / Anchor；
- Claim / Evidence / EvidenceBundle / KnowledgeVersion；
- Human Learning Vault；
- AI Asset Vault 与 Machine Knowledge；
- Provenance、Rights、版本、撤销、弃用和审计；
- Knowledge Query / Projection / Candidate Submission / Receipt；
- 面向人的正式桌面 UI。

它不拥有：

- Hermes/Codex/DSH 等 Agent Runtime；
- WORK-LAB 的任务调度与全局配置；
- DESIGN-LAB 的工具适配器和设计生产执行；
- 所有软件的全局 Memory；
- 通用模型市场、工具市场或自治多 Agent 平台。

“唯一知识总库”的准确含义：

- 可治理、可复用、需要长期可信保留的事实、方法、经验、规范和 Lesson 最终进入 ArcheAxis；
- WORK-LAB 的可执行 Rules/Skills/TaskPack 和 DESIGN-LAB 的 Domain Pack/Adapter 仍由原项目拥有；
- 这些执行资产只能把可抽象的知识提交为 Candidate，经 ArcheAxis 审核后成为知识；
- 不能为了“知识统一”把运行载体、项目数据库或私有配置全部迁入 ArcheAxis。

### 4.3 DESIGN-LAB

建议冻结为：

> DESIGN-LAB 是面向职业视觉设计的 AI 原生、平台中立的设计智能与生产能力系统。它把研究、方法、专业领域、质量、工具适配、生产预检、可编辑交付和证据组织成可组合、可执行、可验证、可回滚的闭环。

它拥有：

- Design Brief、Reference DNA、Direction、Design System；
- Brand/Graphic/UIUX/E-commerce/Editorial/Packaging/Spatial/3D/Motion/Video/Game Visual 等专业 Domain；
- Visual Quality、Jury、Anti-AI-slop、Preflight；
- ToolActionPlan、Adobe/Figma/Penpot/Blender/ComfyUI/FFmpeg/Eagle 等适配器；
- Editable Handoff、BOM、Provenance、Rollback；
- 设计能力证据与人类专业验收。

它不拥有：

- 第二设计画布；
- 默认 Open Design 绑定；
- 通用 Agent Runtime、聊天 UI、模型网关；
- ArcheAxis 的正式知识治理；
- WORK-LAB 的全局软件配置。

当前身份必须严格分开：

- Open Design：外部客户端/可选宿主；
- DESIGN-LAB：当前专业设计项目；
- OPEN-DESIGN-Assistance：历史迁移名称，只能用于历史说明。

---

## 5. 正确的三项目拓扑

~~~mermaid
flowchart TD
    U["用户与项目目标"] --> W["WORK-LAB<br/>治理、TaskPack、权限、路由、回执"]
    W --> A["ArcheAxis<br/>知识、证据、学习、Candidate 治理"]
    W --> D["DESIGN-LAB<br/>设计智能、质量、工具执行、交付"]
    W --> S["可替换软件<br/>Hermes / Codex / DSH / CC Switch / OpenHuman / Open Design / GitHub"]
    D -->|Candidate + Evidence| A
    A -->|Knowledge Projection| D
    S -->|执行结果与证据| W
~~~

硬边界：

1. 三个仓库独立。
2. 不共享数据库。
3. 不跨仓库相对路径 import。
4. 不读取其他项目内部实现目录。
5. 跨项目只使用版本化 API、Schema、Command、Event、Receipt。
6. WORK-LAB 可以拥有联邦注册和传输协议，但不是另外两个项目的父项目。
7. 长期知识进入 ArcheAxis Candidate；执行资产仍留在其项目。
8. 任何软件都是可替换 Adapter，不成为架构中心。

---

## 6. WORK-LAB 全域审计

### 6.1 已经做对的部分

- 当前项目定位已明确 client-neutral、unbound、unlocked。
- config-authority-index.json 已正确区分 UPSTREAM_OFFICIAL、USER_OVERLAY、PROJECT_OVERLAY、TASK_EPHEMERAL、RUNTIME_EPHEMERAL、SECRET。
- PROJECT_OVERLAY 已明确由每个项目自己拥有，WORK-LAB 只读声明指针。
- Workflow Assistance 与 Observer 两活动模块边界清楚。
- Federation Contract 已定义项目所有权、公共信封和禁止耦合。
- 当前 CI 有 gate-plan、workflow、observer、token-monitor、security、integration、aggregate。
- Adapter 设计已区分 detect/capabilities/plan/apply/invoke/observe/rollback。

### 6.2 P0：权威与连续性

#### W-P0-001 唯一当前 TaskPack 正文缺失

00-governance/taskpack-authority-index.json 声明唯一 CURRENT：

WORK-LAB-FORWARD-RECONCILIATION-2026-08-20（WLR-000～960）

但仓库中没有这份文件。ChatGPT 资料库中存在 40,617 字节、741 行版本，并且其中 WLR-010 自己要求“干净 clone 可解析唯一 current taskpack”。

影响：

- 当前仓库不满足自己的 WLR-010；
- 新软件、新机器或 CI 无法从 Git 恢复唯一执行入口；
- Library 文件是 model_generated，未进入 Git 就不能单独承担永久权威。

整改：

- 先由 Owner 确认资料库 WLR 版本；
- 将确认版本写入 50-taskpacks/；
- taskpack-authority-index.json 必须保存 path、sha256、sourceCommit、ownerDecisionId、effectiveAt；
- CI 必须在 clean clone 验证唯一 CURRENT 文件存在且哈希一致。

#### W-P0-002 全局执行标准内部自相矛盾

00-governance/global-execution-standard.md 同时规定：

- 所有检查 fail-open，失败不阻塞；
- 漂移时先报告/收敛，不直接落地，干净才允许合并。

根 README、AGENTS.md、CI 与大部分治理合同又要求 required gate fail-closed。

同一文件还写“并行执行替代单写者”，而当前正式规则是：

- 每个 checkout/worktree 一个 writer；
- 多个隔离 worktree 可并行；
- 目标 tree 最终只有一个 integration writer。

整改：

- 将“探索/诊断检查可 fail-open”和“required landing/release gate 必须 fail-closed”分开；
- 删除“替代单写者”措辞，改为“隔离候选并行 + 单一集成写者”；
- 为每个 gate 增加 required/optional、stage、failurePolicy。

#### W-P0-003 没有跨软件 Context Handshake

当前有 context-control-plane 设计，但没有所有客户端都能执行的：

- 项目身份读取；
- 当前 TaskPack 解析；
- 权威哈希校验；
- UI Baseline 加载；
- HEAD/tree/dirty/CI 对账；
- Resume Receipt 回写。

这正是换软件后漂移的直接工程原因。

### 6.3 P0：Observer 真值与 UI

#### W-P0-101 生产前端和文档不是同一个事实

FRONTEND_ARCHITECTURE_GATE.md 与 Tauri 配置说明：

- React frontend/ 是唯一生产前端；
- Tauri frontendDist 指向 frontend/dist；
- legacy web/ 是 archive。

Observer README 却仍称：

- render-v3.js 是 single production surface；
- frontend 读取 transport.eventsUrl 订阅 SSE；
- bundled snapshot 永远不会被标为 live。

生产 React 代码实际：

- 只有 10 秒轮询，不读取 transport.eventsUrl，不使用 SSE；
- 任何 fetch 到 JSON 的结果都会 setLive(true)；
- 没有验证 transportState、freshness、coverage、schema、revision 或 last-good；
- UI 固定显示 sidecar :61867。

整改：

- README、架构 Gate、Tauri、CI、测试和源码只能指向同一生产前端；
- 删除或明确 archive 文档；
- 先完成 truth contract，再谈视觉。

#### W-P0-102 导航索引错误

React App 定义 10 个 views：

Overview、Agents、Executions、Models、Memory、Tools、Monitoring、Delivery、Trust、Settings。

Sidebar 只有 8 个按钮：

Overview、Agents、Executions、Models、Memory、Tools、Monitoring、Settings。

结果：

- 点击“Settings”实际打开 views[7]，即 Delivery；
- Trust 与真正 Settings 无入口；
- WLR-820 冻结的正式五页 IA（Overview、Executions、Projects、Delivery、Trust）没有实现。

这是直接可复现的生产 UI 错误，不是审美意见。

#### W-P0-103 UNKNOWN 被改造成确定事实

生产 React 中存在：

- 未知 execution state → idle；
- 未知 timeline state → success；
- 每次 snapshot 额外添加一条 success；
- durationSec 固定为 0；
- 缺失 activeExecutionCount → 0；
- 缺失内存/磁盘/网络值 → 0；
- 缺失 dirtyCount → 显示 Git 干净；
- 缺失 singleWriter → 显示“否/未启用”；
- 缺失 eventStreamConnected → 显示“未连接”；
- 任意非 ACTIVE/DEGRADED activity → error；
- 只要 snapshot 存在就把 Sidecar 添加为 healthy。

这些都违反 WLR 的“UNKNOWN 永不伪装为 0/PASS/HEALTHY/LIVE”。

#### W-P0-104 成本与 KPI 被错误推导

- 所有模型/项目都使用固定 DeepSeek input/output rate；
- 固定 CNY_RATE=7.2；
- 没有 provider/model/rate source/rate version；
- “执行中” KPI 使用 agents.length，而不是 running 数量；
- project token 可能被映射到 execution 行。

成本只能在 provider、model、price source、currency rate、observedAt 全部存在时标记为 ESTIMATED；否则必须 UNKNOWN。

#### W-P0-105 CI 没有验证生产 React

当前 Observer CI：

- 运行 Python tests；
- 运行 tests/run_all_tests.js；
- node --check web/scripts/*.js。

它没有：

- npm ci / npm run build（Observer frontend）；
- React unit tests；
- React truth mapping tests；
- 导航可达性测试；
- Tauri 对 production React 的 smoke。

因此当前 exact-SHA CI 绿色不能证明 production Observer UI 正确。

### 6.4 P0/P1：可移植性与 Gate 语义

#### W-P0-201 advertised canonical gate 在干净非 Windows 根失败

verify_external_libraries_index.py 把索引文件写死为：

D:\All projects\WORK-LAB\00-governance\external-libraries-index.json

在当前干净 clone 运行：

python .../run_quality_gate.py external-libraries-index

结果为 FAIL missing index。

但文件明明在当前仓库。失败来自验证器路径，而不是索引缺失。

同时：

- run_quality_gate.py verify 包含这个 gate；
- GitHub workflow 没有运行它；
- 所以“canonical local verify”和“canonical GitHub CI”不是同一个门禁集合。

整改：

- 所有路径从 git rev-parse --show-toplevel 或脚本位置解析；
- shared roots 只能来自 local profile，不能写死进 portable contract；
- CI 与本地 canonical gate 由同一个 GatePlan 生成，禁止手写两套列表。

### 6.5 P1：适配器成熟度与文档

当前 adapter-registry 共 10 个：

| 软件 | 当前状态 | 事实解释 |
|---|---|---|
| Hermes | active / deep | detection 仍 UNVERIFIED，package hash UNAVAILABLE |
| Codex | quarantined / deep | 不是可证明的 live adapter |
| CC Switch | quarantined / deep | 仅 detect/capabilities/observe |
| GitHub | quarantined / deep | static detection，未形成可靠 adapter transaction |
| OpenHuman | quarantined / experimental | 当前应保持观察和候选证据边界 |
| Open Design | quarantined / experimental | 外部 client；DESIGN-LAB 是另一身份 |
| DeepSeek Harness | quarantined / experimental | 可替换 runtime，不是正式第三活动模块 |
| Cursor | blocked / manifest-only | 未来候选 |
| Claude Code | blocked / manifest-only | 未来候选 |
| WorkBuddy | blocked / manifest-only | 未来候选 |

因此“WORK-LAB 管理所有当前软件”当前只能解释为：

> 管理这些软件的目标模型、注册和治理边界；并不代表已经能够安全发现、读写、回滚或同步它们。

其他文档问题：

- 根 AGENTS.md 的 managed client 列表遗漏 DSH，README/PROJECT_POSITIONING 包含 DSH；
- README 的“only active modules”句子把 Workflow Assistance 和客户端列表并列，漏掉 Observer；
- README 有重复残句；
- Observer README 允许 Observer-owned event log，和根级“严格只读、不写第二事实”冲突。

### 6.6 P1/P2：仓库健康

- WORK-LAB 公开仓库没有根 LICENSE，GitHub API 也无法识别 license。
- fresh checkout 中两个 tracked Markdown 因 CRLF/LF 属性立即显示 modified；忽略行尾后没有内容差异。这会污染 dirty truth。
- 40-knowledge 中 210 个本地 Markdown 链接失效，全部位于 asset-provenance skills 投影；大量 SKILL 只复制正文，没有复制 references。
- 至少 219 个 tracked 文件包含机器特定路径模式；其中一部分是历史证据，但 active/current 文件也存在。
- tsconfig.tsbuildinfo 被 tracked。
- GitHub size 约 408 MiB，而当前 tracked 内容约 8 MiB，历史体量需要非破坏性清理计划。

40-knowledge 当前仍按用户决定保持 DEFERRED。整改不得擅自迁移或删除，只先标记其 authority、provenance、broken references 和可重建性。

---

## 7. ArcheAxis Knowledge 全域审计

### 7.1 已经做对的部分

- PRODUCT_IDENTITY_V2 已准确锁定“人机双向学习与可信知识治理工作台”，明确 NOT Agent Runtime。
- 固定六个一级空间：Workspace、Library、Evidence、Learning、AI Assets、Settings。
- Candidate→Review→Verified、原件保全、Evidence、Human Learning、AI Assets 分层清楚。
- 当前精确 SHA CI 强，包括 browser、Windows runtime、desktop build 和 installer lifecycle。
- v0.6.10 有公开 Release、9 个资产、checksum、SBOM、identity 与下载回读。
- frontend/ + root src-tauri/ 已被 docs/SYSTEM_BOUNDARY.md 指定为 canonical desktop implementation。
- 当前 React 有组件和单元测试，不是纯静态 Mock。

### 7.2 P0：历史 UI 契约没有进入生产验收

2026-08-21 的 ArcheAxis 前端重构材料明确写道：

> 历史界面不应推倒。必须保留统一 Desktop App Shell、左侧主导航、情境二级导航、可关闭右侧 Context Inspector、底部 Activity & Receipts Dock，以及 Source→Anchor→Evidence→Conclusion→Learning 的工作方式。

历史冻结布局：

- 60px Top App Bar；
- 92px Primary Rail；
- 220px Context Navigation；
- Main Canvas；
- 300–360px 可收起 Context Inspector；
- 44–56px 可展开 Activity & Receipts Dock。

当前生产 React App 的注释也声称有：

top status bar | left rail | context subnav | center view | right inspector | bottom activity dock

实际 DOM 只有：

- StatusBar；
- 一个 176px SpaceRail；
- Main；
- 永久 240px Inspector；
- 永久展开 ActivityDock。

缺失：

- Context subnav；
- Inspector 收起/关闭；
- Dock 紧凑/展开层级；
- 内容优先全宽 Reader/Canvas 模式；
- 历史设计中的对象上下文连续性。

这就是用户感知“原先定的 UI 前端内容丢了”的直接代码证据。

### 7.3 P0：README 对 UI 的当前声明不真实

README 当前称：

- 动态二级导航已接入；
- 上下文与证据检查器已接入；
- 真实活动坞已接入。

准确说法应为：

- 一级六空间：已接入；
- Context subnav：未实现；
- Inspector：只读固定栏，未实现可关闭/多 Tab 语义；
- ActivityDock：真实 API 与操作已接入，但没有历史规定的 compact→drawer→object inspector 三层；
- 核心 Reader/Evidence/Library UX：未达到历史前端合同。

必须把“源码有组件”和“完整 UX 合同实现”分开。

### 7.4 P1：当前页面偏开发者/治理对象，不是成熟知识产品体验

当前页面主要表现：

- Workspace：状态计数和 recent_activity；
- Library：表格；
- Evidence：锚点和 Bundle 表格；
- Learning：ID、表单、原始关系/掌握信息；
- AI Assets：列表；
- Settings：路径和四库设置。

这些页面已绑定真实 API，工程价值很高；但与历史目标中的以下核心产品面还有明显差距：

- Universal Intake 五步计划；
- Source Archive + 派生物 + Loss Report；
- Focus/Difference Reader；
- Review Queue；
- Evidence Workbench；
- Learning card + Evidence 回链；
- AI Asset provenance/evaluation 生命周期；
- Job Recovery；
- 全局搜索与对象级回跳。

因此判断是：

> 后端闭环与发布工程接近可用产品，前端仍是功能性管理壳，不是历史 UI 蓝图定义的重型学习/知识工作台。

### 7.5 P1：两套 Tauri 根仍存在

当前同时存在：

- root src-tauri/：frontendDist → frontend/dist；
- desktop/src-tauri/：frontendDist → desktop/bootstrap。

两者具有相同：

- productName：ArcheAxis Knowledge；
- identifier：com.archeaxis.workspace；
- version：0.6.11。

虽然 docs/SYSTEM_BOUNDARY.md 已声明 root src-tauri 为 canonical，但第二套仍保留相同产品身份和 bundle 配置，容易被新执行器或发布脚本误选。

整改：

- desktop/src-tauri 必须改为 archive/migration fixture 的唯一可机器识别状态；
- 禁止相同 identifier 的第二 production bundle；
- CI 检查只有一个 release authority。

### 7.6 P1：版本与 current 文档漂移

- README 顶部仍称 v0.6.9 已发布；
- Release Ledger 已确认 v0.6.10 是 Current public stable Release；
- 源码版本为 0.6.11 candidate；
- README 的权威链接列表没有把最新 Release Ledger/current delta 放到首要位置。

正确显示应同时分开：

- Source version：0.6.11 candidate/unreleased；
- Latest public release：v0.6.10；
- Long-term blueprint completion：PARTIAL。

### 7.7 P1/P2：测试、链接与资产

- scripts/ci/run_tests.sh 使用 pwd -W，在普通 Linux Bash 直接 exit 2。
- Markdown 扫描发现 20 个本地失效链接，其中 7 个在 current/core 文档；docs/PROJECT_STATUS.md 与 docs/truth/H0_H1_STATUS_HANDOFF.md 指向 3 份不存在的 taskpacks。
- 当前 tree 仍提交 packaging/release-0.5.0 下的 EXE/MSI。
- 提交了约 5.02 MiB 的 receipt JSON。
- root 与 desktop 的 generated schema 有重复。
- current tracked 内容约 22.77 MiB；可将旧安装器迁至 GitHub Release/历史 manifest，而不是长期放当前源码树。

### 7.8 历史蓝图的处理

旧 V3.0/V3.1 蓝图中包含：

- Model Gateway；
- Tool Registry；
- AgentRouter；
- ToolExecutor；
- 通用 Runtime；
- 多种 OS/Agent 表述。

这些只能保留为历史研究。当前 binding PRODUCT_IDENTITY_V2 已明确 ArcheAxis 不是通用 Agent OS。必须在旧蓝图顶部加 SUPERSEDED_POSITIONING / HISTORICAL_REFERENCE，避免新执行器按旧文档恢复被否决的架构。

---

## 8. DESIGN-LAB 全域审计

### 8.1 已经做对的部分

- 当前 PRODUCT_DEFINITION 清晰、成熟，准确覆盖职业视觉设计和六能力域。
- 明确 host-native first，不建第二画布、聊天客户端、模型网关或通用 SaaS。
- 明确 Open Design 是可选 Host Adapter，不是默认绑定。
- 明确 MiniGame 只是 fixture。
- 有 30 个 adapter 注册、E0～E5 证据模型、Source/Rights/Preflight/Handoff/SBOM。
- unified verify 43/43 通过。
- 受控 Python runner 250 tests 通过，4 skipped。
- 当前精确 SHA Canonical Verify 成功。
- 根 LICENSE 为 MIT，SBOM 与 license gate 通过。

### 8.2 P0：Review Surface 的生产模式绕过人工节点

当前所谓 Review Surface 是 generate_review_surface.py 生成的一份 Markdown，不是正式 UI。

更严重的是：

- production mode 的 approval 列表为空；
- 输出“生产模式：无人工判断节点”。

而 project-memory/USER_MODES.md 明确规定：

> 任何自动化不得跳过步骤 02、05、08、09、10 的授权/人工判断。

包括：

- Rights/Source；
- 人锁定方向；
- 质量 Jury；
- 生产预检；
- 可编辑 Handoff/BOM/Provenance/回滚。

整改：

- mode 只能改变协作密度，不能删除硬授权节点；
- required human gates 从 pipeline contract 读取，不得在 UI generator 中另写一张 mode 表；
- production 应是更严格，不是“无人判断”。

### 8.3 P0/P1：Adapter SSOT 不一致

Open Design 在总 adapter-registry 中：

- status=structural；
- evidence=E1；
- supported capabilities=true。

Open Design 自身 adapter.manifest.json 中：

- status=declared；
- evidenceLevel=E0；
- supported=false；
- runtimeStatus=not-started。

两者不能同时作为 current truth。

正确做法：

- 一个 AdapterRecord 为唯一源；
- registry 只能生成摘要；
- manifest、registry、capability status、Review Surface 全部由同一条记录投影；
- 任一证据升级必须绑定 runtime/version/task/artifact/readback/tree。

### 8.4 P1：总体 E3 掩盖大多数软件未接入

30 个 adapter 当前分布：

- E0：24；
- E1：4；
- E3：2。

creative-toolchain 总能力却被标为 E3，原因是 ComfyUI/H3 的一次运行证据。这个聚合级别容易让人误解为“设计工具链整体 E3”。

应该同时显示：

- aggregate floor；
- best demonstrated adapter；
- 每个 adapter 独立等级；
- 当前机器可用性；
- lastVerified 和 requiresRequalification。

“可以操控所有设计软件”当前不能宣称为事实。准确状态是：

> 已建立平台中立合同和少量真实适配证据；多数专业软件仍是 declared/structural，需要逐个安装、授权、最小任务、产物读回和回滚验证。

### 8.5 P1：Adobe 状态已经过期

ADAPTER_POLICY.md 仍记录：

- Photoshop 2023 本机路径；
- COM + JSX 实测。

但 reports/ADOBE_UNINSTALL_HANDOFF_20260822.md 明确：

- Photoshop、Illustrator、Acrobat 已全部卸载；
- 旧 Photoshop E3 不再可复现；
- 新版本安装后必须重新做 COM/fixture/readback。

总 registry 中 Adobe 已降为 E0，这是正确的；ADAPTER_POLICY 的“运行时入口”必须改成 HISTORICAL/UNAVAILABLE，不能继续作为 current。

### 8.6 P1：current status 报告不 current

reports/current/PROJECT_STATUS.json：

- generatedAt=2026-08-21；
- head=a6fdc5e；
- worktree dirty；
- trackedFiles=3301。

当前：

- head=9468c40；
- trackedFiles=3342；
- checkout clean。

但 canonical verify 仍然通过，说明 current report freshness 没有 fail-closed。

整改：

- current 报告必须在 CI 生成或校验；
- 报告不能提交自称当前、又不绑定当前 tree；
- 旧报告自动移入 reports/history 或标 STALE；
- Review Surface 不得消费过期 current 报告。

### 8.7 P1：Vendored AGENTS 指令污染

DESIGN-LAB 没有根级 AGENTS.md，但 imported intelligence 子树中存在：

- claude-design-skill/AGENTS.md：要求对 jiji262 账号仓库使用外国 author 身份；
- design-system-prompt/codex/AGENTS.md：要求把嵌入 system-prompt.md 当操作指令；
- ultimate-uiux/AGENTS.md：携带第三方默认技术栈和设计偏好。

这些文件作为第三方知识是合理的，但在 agent 层级规则中可能被自动激活。

整改：

- 建立根 AGENTS.md；
- 明确 design-lab/intelligence 与 design-lab/knowledge 下第三方 AGENTS/SKILL 为 vendored data，不获得仓库治理权；
- 禁止第三方内容修改作者身份、提交策略、权限、工具调用和产品边界；
- 增加 imported-instruction quarantine gate。

### 8.8 P1/P2：测试拓扑不完整

两个事实必须同时保留：

- scripts/run_python_tests.py：250 tests，4 skipped，PASS；
- 根目录 pytest -q：7 个 collection errors，来自 motion-forensics 的 ui_clone import 与 game-ui-mobile 缺 Callable。

这表示主项目选择性测试可用，但整个 3,342 文件仓库不能被一个普通测试发现器无错误遍历。

整改选项：

1. 把 imported package tests 排除在根 pytest 配置之外，并明确它们是 vendored upstream tests；或
2. 为每个 imported package 建隔离环境、依赖和独立 gate。

不能继续让“全仓 pytest”看起来像应该可运行、实际却在收集阶段失败。

### 8.9 P1/P2：模板、链接、重复资产与发布

Markdown 本地链接：

- 总失效 266；
- imported/history/knowledge 子树 246；
- current/core 20。

current/core 中主要是 design-lab/templates/INDEX.md 的 19 个错误相对路径，以及一个 MiniGame 历史链接。

重复内容：

- ComfyUI 与 MiniMax H3 重复保存相同 MP4、FLAC、WEBP；
- ui-ux-pro-max 数据在 standalone 与 genjutsu 嵌套目录重复；
- MiniGame Android 与 WebView 生成文件重复。

其他：

- GitHub size 约 202 MiB；
- current tracked 内容约 49.84 MiB；
- 没有 tag/Release；
- E4/E5、独立复审、商业/生产验收未完成；
- Evidence Cards 12，authoritative_accepts=0。

这些不否定结构工程质量，但必须阻止“已形成全面专业生产平台”的过度声明。

---

## 9. 跨项目问题

### 9.1 三份复制的分层决策不是可持续权威

三个仓库都保存 THREE_PROJECT_LAYERING_DECISION.md。

- WORK-LAB 与 DESIGN-LAB 文件字节完全相同；
- ArcheAxis 仅多末尾换行。

文件内容还写：

- DSH/Hermes/Codex 是 Agent 执行；
- Open Design 是模型/视觉宿主；
- 由 WORK-LAB 治理。

这已经不能完整表达当前“Open Design 外部 client/可选 host、DESIGN-LAB 独立、所有软件可替换”的精细边界。

整改：

- WORK-LAB 保留 federation registry 和 transport protocol 的权威；
- 每个项目只保存自己拥有合同的权威内容；
- 跨项目共同决策保留一份 canonical Decision Record；
- 其他仓库只保存 generated read-only projection，包含 sourceRepo、sourceCommit、contentHash、generatedAt、expiresAt；
- CI 验证投影哈希，禁止手工复制后独立维护。

### 9.2 联邦合同存在，但还不是完整运行闭环

WORK-LAB 已有：

- federation-registry.v1.json；
- federation-envelope.v1.schema.json；
- ownership 与 coupling rules。

这是正确基础。

仍缺：

- ArcheAxis/DESIGN-LAB 对来源 SHA/hash 的自动投影；
- schema compatibility matrix；
- contract version negotiation；
- idempotency/retry/dead-letter/receipt 的跨仓 E2E；
- rights/classification 的强制门；
- 每次调用的 exact project/commit identity；
- 当前软件执行器到联邦回执的标准桥接。

### 9.3 三类 Memory 必须分开

| 类型 | 权威项目 | 是否跨软件 |
|---|---|---|
| 软件私有会话/缓存/本地 memory | 软件自己 | 默认不复制、不读取正文 |
| WORK-LAB portable workflow memory | WORK-LAB | 只包含规则、经验、路由、TTL、provenance，不含私有会话正文 |
| 长期知识、人类学习、AI 可复用知识 | ArcheAxis | 通过 Candidate/Review/Projection；受 Rights/Scope 控制 |
| 设计项目经验/方法/失败案例 | DESIGN-LAB 先形成执行资产；可提炼 Candidate | 审核后进入 ArcheAxis，不能自动提升 |

不能把“Memory”作为一个词统一搬运，否则会造成隐私泄漏、知识污染和项目越权。

---

## 10. UI 产品边界总裁决

### 10.1 三种产品界面域、四个正式表面

| UI | 用户目标 | 是否可执行写操作 |
|---|---|---|
| ArcheAxis Workspace | 阅读、证据审核、学习、AI 资产治理 | 可以，只能通过 ArcheAxis 正式 Command/API |
| WORK-LAB Control / Configuration | 管 Desired State、配置差异、任务计划、审批与回滚 | 可以，只能生成或提交受权限约束、可预览、可回滚的正式命令 |
| WORK-LAB Observer | 看项目、执行、交付、可信度 | 绝对只读 |
| DESIGN-LAB Workbench | 输入 Brief、锁定方向、看质量/预检/Adapter/交付/证据 | 只提交明确的设计任务与审核/批准命令；不做编辑画布 |

Hermes、Codex、DSH、OpenHuman、Open Design、Adobe、Figma 等继续使用自己的 native UI。

### 10.2 ArcheAxis UI 恢复原则

必须恢复的不是某一张图片的像素，而是以下交互合同：

1. 一个统一 App Shell；
2. Primary Rail 与 Context Navigation 分离；
3. 当前对象驱动的 Context Inspector，可关闭；
4. Activity Dock 默认紧凑，可展开；
5. Source→Conversion→Anchor→Candidate→Review→Evidence/Verified→Learning→Export 可回跳；
6. Reader/Canvas 内容优先时能占满主工作区；
7. UI 每个状态来自真实 API；
8. Mock/UNBOUND 图只能作为视觉参考，不作为功能完成证据；
9. 历史界面不得被无记录删除，任何替代必须有差异矩阵和 Owner 决定。

### 10.3 WORK 控制面与 Observer 重构原则

完整对话补证后，WORK-LAB 不能只剩 Observer。控制面拥有 Desired State、配置 diff、计划、审批、apply/rollback 命令；Observer 仍然绝对只读。两者可以共用设计系统和同一事实投影，但必须是不同权限域。Observer 必须先修真值，再修视觉：

1. 只保留正式五页：Overview、Executions、Projects、Delivery、Trust；
2. LIVE/SNAPSHOT/OFFLINE/STALE/UNKNOWN 是传输与证据状态，不是颜色装饰；
3. 所有字段使用 Truth Envelope；
4. 不在前端猜状态、成本、运行时间；
5. Snapshot 成功不等于 LIVE；
6. SSE 必须有 Last-Event-ID、revision、heartbeat、gap/resync、last-good；
7. React production build/test 必须进入 CI；
8. legacy web 只作 archive/compat，不能继续自称 production。

### 10.4 DESIGN-LAB Workbench 原则

第一版可以轻，但必须同时提供结构化需求入口和受控事实投影：

- Brief；
- Project/Asset/Reference intake；
- Direction 与人锁定状态；
- Quality/Jury；
- Preflight；
- Rights/Source；
- Adapter 可用性；
- ToolActionPlan；
- Artifact/readback；
- Editable Handoff；
- Evidence 与 rollback；
- 所有 required human gates。

它不能变成第二编辑器，也不能用 Markdown 生成成功冒充 UI 或真实生产能力。

---

## 11. 跨软件上下文连续性协议 v1

这是解决换软件丢上下文的核心工程。

### 11.1 WORK-LAB 拥有协议，不拥有项目内容

WORK-LAB 新增全局协议：

- ContextCapsuleV1
- AuthorityManifestV1
- ActiveTaskpackPointerV1
- DecisionRecordV1
- UiBaselineManifestV1
- ResumeReceiptV1
- ClientProjectionV1

各项目生成自己的内容：

| 项目 | 建议权威位置 |
|---|---|
| WORK-LAB | 00-governance/context-continuity/ |
| ArcheAxis | docs/truth/context/ |
| DESIGN-LAB | project-memory/context/ |

### 11.2 每个项目最小连续性文件组

1. PROJECT_IDENTITY.md  
   一句话定位、非目标、产品名、技术 ID、仓库、所有权。

2. AUTHORITY_INDEX.json  
   每条规则的唯一来源、状态、Owner、替代关系、哈希。

3. CURRENT_CONTEXT.md  
   8～12 KiB 内的稳定启动上下文；只写当前事实和必要边界。

4. ACTIVE_TASKPACK.json  
   taskpackId、path、sha256、sourceCommit、status、nextTask。

5. DECISION_LEDGER.ndjson  
   decisionId、actor、status、supersedes、effectiveAt、evidence。

6. RESUME_RECEIPT.json  
   head、tree、dirty、CI、activeTask、lastVerified、blockers、nextAction。

7. UI_BASELINE/  
   UI_CONTRACT.md、route-data-matrix.json、tokens、screen-registry.json、approved screenshots、rejected variants、visual regression manifest。

8. TEST_AND_RELEASE_CONTRACT.json  
   targeted/stage/release gates，明确 required/optional 和平台。

### 11.3 Context Capsule 最小字段

~~~yaml
schemaVersion: work-lab/context-capsule/v1
projectId: ...
sourceCommit: ...
sourceTree: ...
generatedAt: ...
expiresAt: ...
ownerDecisionVersion: ...
positioning:
  mission: ...
  nonGoals: [...]
authorities:
  - id: ...
    path: ...
    sha256: ...
    status: USER_CONFIRMED
activeTaskpack:
  id: ...
  path: ...
  sha256: ...
currentMilestone: ...
openBlockers: [...]
uiBaseline:
  manifest: ...
  hash: ...
verification:
  requiredGates: [...]
adapterState: [...]
nextAction: ...
~~~

### 11.4 每次换软件的强制启动顺序

1. 确认 Git root 和 projectId。
2. 读取 root AGENTS.md。
3. 读取 AUTHORITY_INDEX。
4. 验证 ACTIVE_TASKPACK 文件与哈希。
5. 读取 CURRENT_CONTEXT。
6. UI 任务额外读取 UI_BASELINE manifest 和批准截图。
7. 读取当前 HEAD/tree/dirty、origin/main、当前 CI/Release。
8. 将历史摘要与当前事实对账，不匹配时标 STALE，不自动覆盖。
9. 输出 Resume Receipt。
10. 只有 authority、taskpack、tree、allowed paths 一致后才允许写入。

如果当前 TaskPack 缺失、哈希不符、存在两个 CURRENT、UI baseline 缺失或项目身份冲突，必须 fail-closed，先报告，不开始重构。

### 11.5 各软件 Adapter 的现实顺序

| 软件 | 第一阶段 |
|---|---|
| Hermes | 从 canonical Capsule 生成 Hermes 原生规则/技能投影 |
| Codex | AGENTS.md + project skills + Resume Receipt；不依赖另一个 host 的 memory |
| DeepSeek Harness | 保持 experimental；只消费批准的投影，不成为权威 |
| CC Switch | 只管理其明确支持的切换/配置指针，不当执行器 |
| OpenHuman | 候选观察与扫描证据；其私有 .openhuman 不读取 |
| Open Design | client 插件与能力分层；DESIGN-LAB 负责设计能力 |
| GitHub | 保存当前代码、Decision、TaskPack、CI、Release 与审计回读 |

新软件接入只需实现同一 ClientProjection/ResumeReceipt contract，不需要重写三项目架构。

---

## 12. 分阶段整改 TaskPack

以下是建议的唯一前向整改图。它是本报告的执行建议，不代表已经写入仓库或获得实施授权。

### Phase G0：冻结权威与恢复连续性

| ID | 任务 | 验收 |
|---|---|---|
| TRI-G0-000 | 锁定三个当前 SHA/tree/CI 与只读备份 | 三仓库无写入；证据完整 |
| TRI-G0-010 | Owner 确认 WLR 资料库版本并恢复到 WORK-LAB | clean clone 可解析唯一 CURRENT |
| TRI-G0-020 | 建立三项目 Authority Status 与 supersession | 不再有两个 ACTIVE/唯一权威 |
| TRI-G0-030 | 建立 Context Continuity schemas | Schema、反例、版本策略通过 |
| TRI-G0-040 | 每项目生成 CURRENT_CONTEXT/RESUME_RECEIPT | 三个软件读取后定位 hash 一致 |
| TRI-G0-050 | 将复制的跨项目决策改为 canonical + generated projections | 来源 SHA/hash 可回读 |

### Phase W：WORK-LAB

| ID | 任务 | 验收 |
|---|---|---|
| TRI-W-000 | 修复 global execution fail-open/fail-closed 与 writer 语义 | 文档、Schema、CI 一致 |
| TRI-W-010 | external-libraries-index 去绝对路径 | Windows/Linux clean clone 均定位文件 |
| TRI-W-020 | 本地 canonical GatePlan 与 GitHub CI 共源 | 无遗漏 gate |
| TRI-W-030 | AdapterRegistry 真值化 | 每 adapter 有 supported operations、evidence、lastVerified |
| TRI-W-100 | Observer 单一生产前端收敛 | README/Tauri/CI/source 一致 |
| TRI-W-110 | 修复 React 导航与正式五页 IA | 五页全部可达，无索引错位 |
| TRI-W-120 | Truth Envelope 与 UNKNOWN 语义 | 缺字段不变 0/success/healthy/live |
| TRI-W-130 | SSE/last-good/freshness/coverage | 断线、gap、乱序、重启 tests 通过 |
| TRI-W-140 | React build/unit/E2E/Tauri smoke 入 CI | 当前 SHA UI gate 可证明 |
| TRI-W-150 | License、CRLF、tracked generated、仓库体量治理 | fresh checkout clean；公开许可明确 |

### Phase A：ArcheAxis

| ID | 任务 | 验收 |
|---|---|---|
| TRI-A-000 | README/Release/current 状态三层对齐 | 0.6.11 source 与 v0.6.10 public 不混淆 |
| TRI-A-010 | root src-tauri 成为唯一 bundle authority | 无相同 identifier 第二生产根 |
| TRI-A-100 | 把历史 UI 交互合同写入 binding UI Contract | Owner 批准、路径和 hash 固定 |
| TRI-A-110 | 恢复 Rail + Context Nav + closable Inspector + compact Dock | 1440/2560/窄窗验收 |
| TRI-A-120 | 实现 Intake/Source/Reader/Evidence/Review/Learning/AI Assets/Recovery 主链 | 每页真实 API、空/错/断网 |
| TRI-A-130 | route-data-action matrix | 无 Mock、无假按钮、可回跳原件/锚点/回执 |
| TRI-A-140 | browser/Tauri E2E + approved screenshot regression | 真实安装版验证 |
| TRI-A-150 | 修复 run_tests.sh 可移植性、broken links、旧安装器入库策略 | Linux/Windows 入口明确；源码树瘦身 |

### Phase D：DESIGN-LAB

| ID | 任务 | 验收 |
|---|---|---|
| TRI-D-000 | 新建根 AGENTS.md，隔离 imported instructions | 第三方 AGENTS 不得获得治理权 |
| TRI-D-010 | AdapterRecord 单一事实源 | registry/manifest/status/review 一致 |
| TRI-D-020 | current status freshness gate | 当前报告绑定当前 tree，否则 fail |
| TRI-D-100 | Review Surface 正式合同 | 不建第二画布；真实数据投影 |
| TRI-D-110 | 修复 production 人工节点绕过 | 02/05/08/09/10 永不可跳过 |
| TRI-D-120 | 按软件逐个 E2/E3 资格化 | 安装、权限、任务、artifact、readback、rollback |
| TRI-D-130 | 隔离 vendored tests | canonical 与 repo-wide 测试边界明确 |
| TRI-D-140 | 修复 core links、重复媒体和数据 | 可重建/Release/LFS 策略明确 |
| TRI-D-150 | E4/E5 与 Release | 独立复审、exact-SHA、人工 Jury、外部验收 |

### Phase X：跨项目真实闭环

| ID | 链路 | 验收 |
|---|---|---|
| TRI-X-000 | WORK WorkUnit → DESIGN DesignBrief/IR | schema/version/hash/rights 完整 |
| TRI-X-010 | DESIGN ToolActionPlan → Adapter → Artifact/readback | 有批准、回滚与 Evidence |
| TRI-X-020 | DESIGN Candidate/Evidence → ArcheAxis | 默认 Candidate，不能自动 Verified |
| TRI-X-030 | ArcheAxis KnowledgeProjection → DESIGN | scope/rights/version/TTL 可验证 |
| TRI-X-040 | 执行结果 → WORK Receipt/Delivery/Trust | Observer 只读显示 |
| TRI-X-050 | Hermes/Codex/DSH 切换恢复测试 | 三端读取定位、TaskPack、UI baseline hash 一致 |

---

## 13. 完成标准

不能再用“摘要已写”“代码存在”“CI 绿色”作为总完成。

### 13.1 上下文连续性

- 任意一个全新软件/新会话只读 clean clone 后，能得到相同的三项目定位 hash。
- 唯一 CURRENT TaskPack 文件存在且哈希一致。
- 历史摘要不会覆盖 USER_CONFIRMED 决定。
- Resume Receipt 明确 HEAD/tree/dirty/CI/nextAction。
- UI 任务自动加载批准的 UI baseline。

### 13.2 WORK-LAB

- advertised canonical gate 与 GitHub CI 同源、同集合。
- 所有路径 portable。
- Adapter 状态不再把 manifest 当 live。
- Observer production React 被构建、测试并证明只读。
- UNKNOWN 不被改写为 0/PASS/HEALTHY/LIVE。

### 13.3 ArcheAxis

- 六空间不仅可达，而且有完整的 Source→Evidence→Learning UX。
- Context Nav、Inspector、Dock 恢复历史交互语义。
- 当前 UI Contract 与截图基线进入 CI。
- 只有一个 production Tauri authority。
- README 不再把部分实现写成全部实现。

### 13.4 DESIGN-LAB

- 所有 required human gates 不能被 mode 跳过。
- 30 个 adapters 逐项诚实显示 E0/E1/E2/E3。
- Adobe 卸载后的状态不再被旧政策覆盖。
- current status 真正 current。
- imported AGENTS 不再影响仓库执行。
- E4/E5 只有真实独立复审和外部/生产验收后才能升级。

---

## 14. 最终裁决

### 14.1 不是三个项目定位整体错误

当前三个项目已经形成合理的三层：

1. ArcheAxis：可信知识与双向重型学习；
2. WORK-LAB：全局治理、执行与跨软件适配；
3. DESIGN-LAB：专业设计智能与生产。

真正的问题是权威链、实现证据和 UI 合同没有同时收敛。

### 14.2 UI 问题不是主观“换风格”

ArcheAxis 的历史材料明确要求：

- Context Navigation；
- 可关闭 Inspector；
- 可展开 Activity Dock；
- Focus/Difference Reader；
- Evidence Workbench；
- 可追溯对象回链。

当前生产 React 只实现了最外层骨架和部分 API 页面。这个差距是可逐项验收的产品合同缺失，不是单纯审美分歧。

WORK-LAB Observer 更严重：当前生产 UI 还会把 UNKNOWN 改成确定状态，并存在导航错位。它必须先修事实语义。

### 14.3 DESIGN-LAB 的方向正确，但能力声明要降到证据层

DESIGN-LAB 当前是结构成熟、运行适配仍早期的专业能力系统。它未来可以控制所有设计类软件，但现阶段不能把 24 个 E0 adapter 写成“已集成”。

### 14.4 正确下一步

不要马上同时重写三个项目，也不要再生成第四份“总摘要”。

第一步必须执行 Phase G0：

1. 恢复 WORK-LAB 唯一 WLR TaskPack 到仓库；
2. 建立三项目 Authority Index 与 Context Capsule；
3. 冻结 ArcheAxis UI Contract；
4. 修正 WORK Observer production truth gate；
5. 隔离 DESIGN-LAB imported instructions。

这些完成后，再开始 ArcheAxis UI 重构和 Adapter 实证。否则换一次软件、开一次新会话，仍会继续丢失同样的内容。

---

## 15. 关键证据索引

WORK-LAB：

- [当前仓库](https://github.com/DTALEX66/WORK-LAB)
- [当前 CI](https://github.com/DTALEX66/WORK-LAB/actions/runs/32652777802)
- 00-governance/PROJECT_POSITIONING.md
- 00-governance/config-authority-index.json
- 00-governance/taskpack-authority-index.json
- 00-governance/global-execution-standard.md
- 00-governance/federation/THREE_PROJECT_FEDERATION_CONTRACT.md
- 30-observer/work-lab-observer/docs/FRONTEND_ARCHITECTURE_GATE.md
- 30-observer/work-lab-observer/frontend/src/App.tsx
- 30-observer/work-lab-observer/frontend/src/lib/api.ts

ArcheAxis：

- [当前仓库](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS)
- [当前 CI](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/actions/runs/32672672037)
- [最新公开 Release v0.6.10](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/releases/tag/v0.6.10)
- docs/truth/PRODUCT_IDENTITY_V2.md
- docs/truth/AUTHORITY_AND_STATUS_RULES_V1.md
- docs/SYSTEM_BOUNDARY.md
- frontend/src/app/App.tsx
- frontend/src/components/Inspector.tsx
- frontend/src/components/ActivityDock.tsx
- frontend/src/design-system/tokens.css

DESIGN-LAB：

- [当前仓库](https://github.com/DTALEX66/DESIGN-LAB)
- [当前 CI](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/32627455106)
- project-memory/PRODUCT_DEFINITION.md
- project-memory/USER_MODES.md
- project-memory/ADAPTER_POLICY.md
- design-lab/adapters/adapter-registry.json
- design-lab/adapters/hosts/open-design/adapter.manifest.json
- design-lab/scripts/generate_review_surface.py
- reports/ADOBE_UNINSTALL_HANDOFF_20260822.md
- reports/current/PROJECT_STATUS.json

历史/资料库关键材料：

- WORK-LAB-FINAL-FORWARD-RECONCILIATION-TASKPACK-2026-08-20.md
- ArcheAxis_Project_Context_Handoff_2026-08-18.md
- Cognitive-Loop-OS-Frontend-System-UI-Audit-and-TaskPack-2026-08-11.md
- ArcheAxis_Frontend_Reconstruction_and_Generation_Prompts_2026-08-21.md
- OPEN-DESIGN-AUTHORITATIVE-CONTEXT-2026-08-07.md

这些历史材料在迁入仓库并由 Owner 确认之前，只能作为历史证据和候选权威，不能继续单独承担跨软件永久记忆。

---

## 16. 开源项目收集历史与供应链深审

### 16.1 统一处置词义

为避免“留着”等于“继续生效”、“去掉”等于“直接丢历史”，本报告只使用以下五种状态：

| 状态 | 含义 | 是否可进入当前执行/索引 |
|---|---|---|
| KEEP-ACTIVE | 当前项目边界内、来源和许可证可接受、确有运行或测试证据 | 可以 |
| KEEP-REFERENCE | 有研究或对标价值，但不是当前实现或依赖 | 不可以 |
| EXTRACT-THEN-ARCHIVE | 只提炼项目所需方法、测试或知识卡；原上游副本转历史归档 | 提炼物可以，原副本不可以 |
| QUARANTINE | 身份、许可证、安全或能力证据不足；待复核 | 不可以 |
| REMOVE-ACTIVE | 越界、重复、虚假、危险或污染指令；立即从自动发现、生成、索引、SBOM 当前面移除 | 不可以；物理删除须走回滚清单 |

“REMOVE-ACTIVE”不是立即清空 Git 历史。物理删除必须满足：提炼完成、依赖反查为零、回滚清单生成、Owner 批准。这个保护也服从 2026-08-20 已确认的迁移约束：ArcheAxis 的稳定知识摄入尚未完成前，不直接清空 WORK-LAB 和 DESIGN-LAB 的历史知识资产。

### 16.2 WORK-LAB：技能、治理工具和外部组件

#### A. 当前应保留

`40-knowledge/asset-provenance/skills/_INDEX.json` 记录 189 个技能快照：Hermes 171、Codex 14、DeepSeek Harness 4。它们是此前“收集高价值开源技能并做快照”的历史成果，而且已被改名为 `.md`，不会被标准 `SKILL.md` 自动发现。因此本轮判定为 **KEEP-REFERENCE / 历史快照**，不是 189 个当前激活技能，也不应删除。

当前 Hermes 源侧 13 个小型技能可 **KEEP-ACTIVE**：

- codex
- github-auth
- github-code-review
- github-issues
- github-pr-workflow
- github-repo-management
- model-switch
- agent-workflow-fortress
- project-data-boundary
- python-testing
- requesting-code-review
- sleep-mode
- windows-development-env

它们仍须补齐统一 Skill ID、版本、来源、适用软件、权限、失效条件和投影测试；不能继续靠文件名或软件私有目录表示权威身份。

OpenTelemetry、OpenInference 映射、Observer 证据链、actionlint、zizmor、Trivy、in-toto 模型、Agent Skills 输出和 promptfoo 风格评测模板，仓库里已有实现或可执行痕迹，判定为 **KEEP-ACTIVE**。其中 `00-governance/source-ledger.json` 把多项仍标成“未实现”，这是账本陈旧，不是实现不存在。

#### B. 只作参考或 PoC

OPA、Conftest、Cosign、SOPS、chezmoi、Dagger、Renovate、MCP Inspector、Superpowers 方法论判定为 **KEEP-REFERENCE**。只有当它们具备明确使用场景、许可证、固定版本/摘要、最小权限和验收证据后，才可晋级 KEEP-ACTIVE。

#### C. 立即移出当前权威面

| 资产/路径 | 判定 | 原因与动作 |
|---|---|---|
| `reports/current/WLR600_SKILLS_REVERIFY.json` | REMOVE-ACTIVE | 声称只有一个 canonical skill，与实际 13 个源技能及 189 个快照矛盾；转历史证据并重建报告 |
| `00-governance/cross-module-source-index.json` | REMOVE-ACTIVE | 33 条 DESIGN 所有的 adopt-now 条目、0 implemented、含陈旧 `D:/All projects/...` 路径；从 WORK 当前真相移除 |
| `10-workflow/workflow-assistance/config/software-registry.json` 的 Hermes 记录 | REMOVE-ACTIVE 后重建 | 官方主仓应校正为 `NousResearch/hermes-agent`，不是 `anthropics/hermes` |
| 同一注册表的 DeepSeek Harness 版本 | REMOVE-ACTIVE 后重建 | 注册表版本落后于仓库可见历史；必须以固定 release/commit 和验证时间生成 |
| 重复 OpenTelemetry ledger 行 | REMOVE-ACTIVE | 合并成一个稳定 Source ID，保留旧 ID alias |
| public-apis、sequential-thinking 等已退役 MCP | KEEP-REFERENCE | 仅保留历史说明，不再作为默认插件/能力 |
| memory/filesystem MCP 默认启用设想 | QUARANTINE | 高权限且放大跨项目污染，只能按任务最小授权临时启用 |

`00-governance/source-ledger.json` 当前 17 条来源全部把 license 写成 UNKNOWN，仓库根也只有 NOTICE、没有统一 LICENSE。17 条逐条状态不能继续用“名字认识”代替许可证证据：在 SPDX、来源 commit/tag、获取时间和可再分发结论补齐前，除纯内部实现外统一降为 **QUARANTINE / KEEP-REFERENCE**。

Trivy 需增加一次历史暴露核验和 action SHA/工具摘要记录。官方曾披露 2026 年供应链事件；即使当前工作流固定的后续版本不在已知受影响范围，也不能只凭版本号推断安全。证据：[Trivy GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)。

### 16.3 ArcheAxis：101 项旧池、46 项当前账本和学习算法来源

#### A. 两套开源清单不能继续并列为当前真相

`docs/truth/SUPPLY_CHAIN_LEDGER.json` 是当前较新的 46 项账本：CURRENT 12、ADOPT 13、EVALUATE 9、SIDECAR 2、REVIEW-BLOCK 9、REJECT-CORE 1。

`inspiration_research/resources/open_source_project_registry.json` 与旧 absorption ledger 共 101 行，生成于 2026-07-22，仍使用 Cognitive-OS、IR、KB、Obsidian-Assistance 等旧目标名；状态为 implemented 8、adapter pending 27、deferred 38、reference 28。它应 **KEEP-REFERENCE / 迁移来源池**，不得继续与 46 项账本共同驱动安装、索引或产品声明。

旧池里的精确重复至少包括 browser-use、Firecrawl、MinerU；规范化名称后还有 Marker、sqlite-vec 等重复组。重复行应从当前视图合并，但旧行和旧 ID 留在历史 provenance，不做无痕删除。

#### B. KEEP-ACTIVE：必须有实际导入、运行或测试证据

当前核心可保留的范围包括 FastAPI、SQLite/sqlite-vec、NetworkX、MarkItDown、Trafilatura、LiteLLM、pytesseract、FSRS、ONNX Runtime，以及本项目已实现并测试的第一方派生模块：

- BKT/学习状态估计（参考 OATutor、pyBKT、pyKT）
- teach-back/费曼回授（参考 Studyield、OpenCognition）
- temporal graph（参考 Graphiti）
- 分层记忆与巩固（参考 MemoryOS、MemOS、Hermes）
- ReasoningBank 方法
- quiz/path（参考 DeepTutor、OpenTutor）
- Cognee ECL、ReMe、GraphRAG、Corpus2Skill、FSRS 等方法的本地化派生

这里“参考”不等于把上游仓库或许可自动继承为当前核心依赖。每个派生模块都要保留 source→claim→local implementation→test 的证据边。

#### C. SIDECAR / RESEARCH，而不是核心内嵌

Crawl4AI、Langfuse、Graphiti、Cognee、Mem0、Letta 以及其他重型 agent-memory/agentic RAG 框架判定为 **KEEP-REFERENCE 或 SIDECAR**。只有部署隔离、数据出站、许可证、资源预算和卸载路径通过后才能启用；源码存在不能写成“CURRENT installed”。

#### D. REMOVE-ACTIVE / REJECT-CORE

| 项目组 | 判定 | 原因与动作 |
|---|---|---|
| “Paperless AI Research Brain” | REMOVE-ACTIVE | 旧资料已承认是假/误命名项目；从活跃清单删除并保留纠错记录 |
| Kùzu | REJECT-CORE | 上游已归档，不再作为核心图库候选；现有研究仅留历史 |
| 23 个 Security Research 工具 | KEEP-REFERENCE | 与重型学习/可信知识主边界不一致；不进入产品 runtime 或 UI |
| 通用 coding agents、RAG UI、聊天壳 | REMOVE-ACTIVE | 与“唯一重型学习知识 OS”定位冲突；保留紧凑对标元数据即可 |
| Phoenix | REVIEW-BLOCK | Elastic License v2，不得用“开源”笼统描述 |
| tldraw | REVIEW-BLOCK | 生产使用受其商业许可边界约束，不可默认为自由嵌入 |
| Firecrawl | REVIEW-BLOCK/SIDECAR | AGPL 义务和网络部署边界需单独评估 |

42 个 dual-learning 命名候选中，除上述 Paperless 误项外其余 41 个可作为真实研究来源；这不代表 41 个都应被安装。重型框架继续维持 H7+ 研究级，优先使用本项目已实现的轻量第一方等价能力。

#### E. 供应链与 UI 新发现

`scripts/release_sbom.py` 读取的是旧路径 `desktop/package-lock.json` 与 `desktop/src-tauri/Cargo.lock`，而真实发布根在 `frontend/package-lock.json` 和 `src-tauri/Cargo.lock`。旧生成器统计 634 个原始条目（197 uv + 12 npm + 425 Cargo），真实三个根锁文件原始总量约 871（197 + 236 + 438）；这使现有 release SBOM 明显漏报。npm PURL 还错误混入 `node_modules/...` 路径，并漏掉 PDF.js、Magika、二进制、模型和资产面。

`THIRD_PARTY_NOTICES.md` 仍写旧版本 0.4.2，并漏列 pymupdf、jiwer、rapidfuzz、fsrs、onnxruntime、striprtf 等当前直接依赖。版本发布前必须让 Notice、锁文件、SBOM 和 release asset 同源生成。

当前 PDF.js 3.11.174 落在官方已披露的受影响范围（≤4.1.392，4.2.67 修复）。P0 动作是升级、禁用动态 eval（`isEvalSupported: false`）并审查错误渲染/`innerHTML` 路径。证据：[PDF.js GHSA-wgrm-67xf-hhpq](https://github.com/mozilla/pdf.js/security/advisories/GHSA-wgrm-67xf-hhpq)。

### 16.4 DESIGN-LAB：162 条隔离登记、44 个 vendored 来源根和 6 个已审核来源

#### A. 当前登记事实

`design-lab/research/global-absorption/QUARANTINE_REGISTRY.json` 共 162 条：adapter 71、vendor-adapt 53、derive 19、reference 13、quarantine 6；但所有条目都缺当前 v3 所需的关键 provenance 字段。

`design-lab/research/global-absorption/SOURCE_REGISTRY.json` 只有 6 个 active、exact-SHA、human-reviewed 来源：ckw-design-skill、pixelmatch、awesome-copilot Illustrator 参考、Photoshop scripts、Illustrator scripts、Inkscape batch export。现有 verifier 只检查字段语法，没有重新计算目标树哈希；`contentHash` 算法也未形成契约。因此 6 项暂定 **CONDITIONAL KEEP-ACTIVE**，只有实际 tree hash 重算通过后才可解除条件。

`design-lab/intelligence` 和 `design-lab/knowledge` 下 44 个 vendored 来源根都有 `SOURCE.md`，但没有一个 `SOURCE.md` 包含精确 40 位 commit SHA。相关目录合计约 2,058 个文件、35.1 MiB。它们不能继续被“有 SOURCE.md”自动视为已审计来源。

#### B. 能力索引目前是语义污染源

`generate_capability_indexes.py` 把 intelligence、atoms、scenarios、bundles、domain-packs、knowledge、quality、production、adapters 下的每个文件都当成 capability。现有约 2,424 条索引包含 210 个 `SKILL.md`、5 个 `CLAUDE.md`、3 个 `AGENTS.md`、9 个 `package.json`、4 个 requirements，以及 LICENSE、README 等元文件。

这导致“文件存在”“第三方说明”“控制指令”“真正可执行能力”被混成一类。53 个 vendor-adapt 名称还进入 SBOM/能力索引，44 个 origin URL 出现在已索引文件中；`ai-product-os` 前端虽处于 quarantine，仍有 8 个 skills 位于 `intelligence/ai-product-os` 并被索引。该索引必须立即停止作为能力真相。

#### C. 立即 REMOVE-ACTIVE 的内容

| 内容 | 当前规模/证据 | 处置 |
|---|---|---|
| `affiliate-skills` | 约 1.98 MiB、171 个被索引文件；含虚假 evergreen 倒计时建议，而自身检查器又禁止 fake urgency | 立即移出自动发现、能力索引和生成；保留审计样本后，进入物理删除候选 |
| `ecommerce-ai` 全运营语料 | 约 7.9 MiB、223 文件，主要是库存、定价、客服、广告运营 | 只提取 PDP、视觉创意、设计评审方法；其余 REMOVE-ACTIVE |
| `ai-product-os` 重复前端与 skills | quarantine 与 active index 相互矛盾 | 取消索引；只保留不可替代的设计评测方法，否则归档 |
| 第三方 `AGENTS.md`、`CLAUDE.md`、插件配置 | 至少 8 个控制文件；例如强制提交作者身份 | 全部当作不可信数据，不可进入根控制链 |
| curl-pipe 安装器和上游安装说明 | 至少 13 个 curl-pipe 模式、166 个安装说明文件 | 从生成/执行上下文隔离；不得自动执行 |
| 第三方 delegation/subagent 指令 | 至少 100 个相关文件 | 从能力索引和 agent 指令加载器排除 |
| 身份/许可证不明项目 | 例如 Flue、未验证的 UIClip 代码/权重 | QUARANTINE，查明前不集成、不宣传 |

一个明确的指令污染证据是 `intelligence/claude-design-skill/AGENTS.md` 强制提交作者为 `jiji262 <jiguofei@msn.com>`。这类文件即使保留作来源研究，也只能作为字节数据读取，不能被 Codex、Hermes 或其他 Agent 当成有效项目指令。

#### D. 提炼后保留，而不是整仓搬运

Hallmark、Taste/UIUX Pro Max、baoyu、genjutsu、motion-forensics 等设计方法或案例集可能有价值，统一判定为 **EXTRACT-THEN-ARCHIVE**：

1. 提取原子化 design principle、反例、测试夹具或 benchmark。
2. 写清 source、commit、license、transformation 和适用设计域。
3. 与已有 first-party atoms/domain packs/gates 去重。
4. 通过能力测试后只索引第一方提炼物。
5. 上游完整副本转 archive；待稳定知识摄入完成、依赖为零和 Owner 批准后再物理删除。

#### E. 外部设计软件只做适配器

| 软件/项目 | 判定 | 边界 |
|---|---|---|
| Penpot | KEEP-REFERENCE/ADAPTER | MCP 具备读写能力；默认只读或小步可逆写入，不把 Penpot 变成 DESIGN-LAB 数据库。证据：[Penpot MCP](https://help.penpot.app/mcp/) |
| Open Design | ADAPTER | 外部宿主 `nexu-io/open-design`，与 DESIGN-LAB 分离；固定能力与版本，不绑定为唯一画布 |
| ComfyUI | SIDECAR | custom node 可执行任意 Python；默认 localhost，拿到 URL 者即被信任。必须隔离节点、目录和网络。证据：[ComfyUI Security](https://github.com/Comfy-Org/ComfyUI/security) |
| Krita AI Diffusion | ADAPTER/SIDECAR | GPL-3.0、依赖 ComfyUI 后端；许可证和节点供应链必须隔离 |
| OpenPencil/OpenPencil 相关 | EVALUATE | 已核对项目为 `HPABio/openpen`、MIT，但上游明确仍非生产就绪；只做实验适配。证据：[HPABio/openpen](https://github.com/HPABio/openpen) |
| OpenCut | EVALUATE | 固定身份为 `opencut-app/opencut`；网络上有大量同名/仿冒下载，必须钉住仓库、commit 和签名。证据：[opencut-app/opencut](https://github.com/opencut-app/opencut) |
| Style Dictionary | KEEP-REFERENCE | 可支持 DTCG v4，但对 DTCG 2025.10 并非完全覆盖；token 导出必须有兼容测试。证据：[Style Dictionary DTCG](https://styledictionary.com/info/dtcg/) |
| UIClip | REFERENCE ONLY | 目前只确认论文/研究价值，未确认可用 OSS 代码、权重和数据授权 |

### 16.5 三仓开源资产的总处置结论

| 仓库 | 保留当前 | 保留参考/归档 | 立即移出当前面 | 物理删除策略 |
|---|---|---|---|---|
| WORK-LAB | 13 个小型源技能、治理/CI/观测实现 | 189 快照、PoC 工具、退役 MCP 历史 | 陈旧 WLR 报告、跨模块 DESIGN 索引、错误软件注册、重复 ledger | 当前不删 189 快照；先完成 ArcheAxis 摄入与快照压缩 |
| ArcheAxis | 真实运行依赖与第一方学习模块 | 101 项旧池、41 个有效 dual-learning 来源、重型框架研究 | Paperless 误项、Kùzu 核心候选、通用 agent/RAG UI 核心声明 | 旧池行保留 provenance；当前视图去重和降级 |
| DESIGN-LAB | 第一方 atoms/domain packs/gates/adapters；6 个条件性已审来源 | 设计方法提炼物、外部软件适配器 | affiliate、非设计电商运营、重复 AI Product OS、第三方控制/安装/委派指令 | 提炼、反查、回滚清单、Owner 批准后再删完整上游副本 |

---

## 17. P0—P2 可执行整改列车

### 17.1 P0：先阻断错误继续传播

1. `WL-P0-01`：停止 `WLR600_SKILLS_REVERIFY.json` 和 `cross-module-source-index.json` 作为当前权威输入。
2. `WL-P0-02`：修正 Hermes/DeepSeek Harness 身份与版本；合并 OTel 重复项；17 个来源补 SPDX 或降级 quarantine。
3. `AA-P0-01`：升级 PDF.js 至已修复线，设置 `isEvalSupported: false`，增加恶意 PDF 回归夹具。
4. `AA-P0-02`：修复 `release_sbom.py` 锁文件路径和 PURL 生成；把 frontend、Rust、Python、PDF.js、模型、二进制、资产纳入发布清单。
5. `DL-P0-01`：能力索引只接受明确 `capability.manifest.*`；排除 README/LICENSE/package/requirements/SKILL/AGENTS/CLAUDE/插件/安装说明。
6. `DL-P0-02`：affiliate、ecommerce ops、AI Product OS、第三方控制文件全部取消自动发现和生成上下文；先不物理删。
7. `DL-P0-03`：重新计算 6 个 active source 的目标树哈希；未通过者自动降级 quarantine。

### 17.2 P1：把跨软件连续性变成可验证协议

1. 建立一个 Owner 确认的 `PROJECT_CONTRACT` schema：定位、不是、唯一 UI、数据边界、权威路径、软件投影、版本、来源哈希、替代关系、失效时间。
2. 三仓根目录分别放置最小 `AGENTS.md`；只引用仓库内正式合同，不加载第三方 vendored 控制文件。
3. WORK-LAB 生成 Hermes/Codex/DeepSeek Harness/CC Switch/OpenHuman/Open Design/GitHub 投影，并做“同一规则跨投影语义一致”测试。
4. 每个 TaskPack 使用稳定 ID、parent ID、supersedes、target SHA、evidence snapshot、owner confirmation；摘要永远不能成为无来源的新权威。
5. 建立 Skill registry：canonical Skill ID 与软件投影分离，快照、激活和安装状态分离。

### 17.3 P1：UI 和能力真相修复

1. ArcheAxis 只保留 root `frontend + src-tauri` 为唯一生产 UI；OSUI 作为迁移基准，旧 `app/workspace/ui` 与 `desktop` 转归档。
2. 将历史 UI 契约转为 Playwright/视觉/可访问性/窄屏强制验收：返回、学习模式、工作区、检查器、活动抽屉、证据溯源和状态语义必须可操作。
3. 补齐当前 CSS 中约 15 个“使用但未定义”类，增加主响应式断点，移除 UI 对裸 ID/hash 的展示依赖。
4. WORK-LAB Observer 的状态映射必须有 schema contract test，生产 React frontend 必须进入 CI 构建和测试。
5. DESIGN-LAB 只展示有 adapter evidence 的可操控软件；“支持所有设计软件”改为目标范围，不再写成已实现事实。

### 17.4 P2：压缩和删除

1. ArcheAxis 稳定摄入来源卡、许可证、哈希、派生关系和测试证据。
2. 为每个删除候选生成：路径、来源、commit、license、大小、重复目标、被引用点、提炼目标、恢复命令、Git 保留点。
3. 依赖反查、索引重建、SBOM、测试、UI 冒烟全部通过。
4. Owner 对清单逐批批准后，才从当前工作树物理删除冗余完整上游副本；Git 历史和 canonical provenance 不删除。

---

## 18. 验收标准：完成不是“又写了一份摘要”

本次问题只有在下列机器可验条件同时成立时才算解决：

- 新软件/新会话只读三仓根合同，就能复述相同的项目定位、边界、唯一 UI 和数据权威。
- 任一事实能追到 owner-confirmed contract、仓库文件、commit/hash 和 supersedes 链；摘要只能引用，不能自封权威。
- 软件注册表不存在错误组织名、漂移版本或未验证却标 active 的适配器。
- 189 个 WORK 技能快照不会被误当作 189 个激活技能。
- ArcheAxis 101 项旧池不再驱动当前安装；46 项当前 ledger 无重复、状态与真实 import/test 一致。
- ArcheAxis 发布 SBOM 从真实锁文件和资产清单生成，Notice 与 release 同步，PDF.js 漏洞回归测试通过。
- DESIGN 能力索引不再包含 README、LICENSE、第三方控制文件、安装器或未经审核的 vendored 内容。
- DESIGN 的外部软件支持声明逐项有：exact identity、version/hash、license、permission、dry-run、rollback 和 editability evidence。
- 三仓没有共用正式数据库、truth store 或 agent runtime；跨项目只交换版本化合同、TaskPack 和证据回执。
- 切换 Hermes、Codex 或未来工具后，golden continuity test 的关键语义差异为零。

---

## 19. 历史对话与 Git 历史的实际覆盖边界

### 19.1 已审计

- 当前可检索的 GPT 历史对话、ChatGPT Library 交接材料、项目摘要和任务包。
- 三个本地仓库的当前树、所有本地可见 refs、提交/树元数据、登记表、锁文件、CI/Release 证据。
- Git 可见规模：WORK-LAB 约 872 commits / 54 branches / 8 tags；ArcheAxis 约 875 / 31 / 17；DESIGN-LAB 约 304 / 29 branches。
- 可见历史中的开源收集、技能快照、供应链 ledger、source registry、quarantine registry、SBOM、Notice 和第三方控制文件。

### 19.2 不能伪装成已完成的部分

本地三个副本是 partial/blobless clone。可达对象与缺失 blob 的扫描约为：WORK 9,121 / 缺 3,302；ArcheAxis 9,246 / 缺 3,282；DESIGN 7,361 / 缺 1,264。提交标题和树结构可见，不代表所有被删除历史文件正文都已下载。因此：

- 本报告不会声称“逐字读完了账户中所有永远不可见/已删除的聊天”。
- 不会声称“已读取所有缺失 Git blob 的正文”。
- 旧对话中没有明确逐项 owner keep/delete 决定的资产，本报告标记的是当前审计建议，不冒充历史授权。
- 如需对已删除 blob 做法证级逐字审计，必须在具备网络/凭据的环境 hydrate 全部对象后再生成 hash manifest；这不影响当前树的 P0 结论。

这一边界不是停止整改的理由。当前树已经有足够证据执行第 17 节 P0；缺失历史正文只阻止“不可逆删除”和“全历史版权清算”，不阻止取消错误索引、修复漏洞和修正权威链。

---

## 20. 本报告的执行地位与下一交付

本报告是只读审计和整改基线，不等于三个仓库已经被修改。下一交付必须是一组可复核的代码变更，而不是第三份总摘要：

1. WORK-LAB：权威输入退役、软件注册/许可证修复、root 投影合同和 continuity tests。
2. ArcheAxis：PDF.js、SBOM/Notice、唯一 UI 构建与契约测试修复。
3. DESIGN-LAB：安全能力索引、第三方控制隔离、source tree hash 和 staged cleanup manifest。

变更按仓库分开提交、互不共享正式数据库或 runtime。任何物理删除单独成批并附恢复清单，不与 P0 安全修复混在同一提交中。

---

## 21. 三份本地汇总文档的证据质量审计

### 21.1 可以交叉分析，但不能把它们直接升级为事实真源

本轮新增的三份材料是：

| 文件 | 行数 | 字节数 | `### 会话` 条目 | 空白“我的结论” | 初步证据类型 |
|---|---:|---:|---:|---:|---|
| `WORK-LAB-SUMMARY.md` | 2,035 | 164,397 | 41 | 40 | DSH 用户消息、Objective、记忆条目、局部工具声明和最终汇总 |
| `DESIGN-LAB-SUMMARY.md` | 566 | 54,845 | 13 | 13 | 以开源调研请求和子任务报告为主，夹杂本地分支状态 |
| `ArcheAxis-Knowledge-OS-SUMMARY.md` | 1,135 | 74,734 | 38 | 37 | DSH 研究/执行请求、记忆条目、历史测试与交接摘要 |
| **合计** | **3,736** | **293,976** | **92** | **90** | 本地执行历史证据，不是完整聊天转录 |

三份材料有价值，因为它们补回了大量 DSH/Hermes/Codex 侧的用户指令、纠错、阶段目标、开源调研对象和本机执行记忆。但其证据上限必须锁死：

1. 92 个会话条目中 90 个“我的结论”为空，缺少助手最终回答、工具原始输出和失败链。
2. 大量条目只是“记忆管家”提示、任务 Objective 或“继续直到全部完成”的用户要求；要求不等于结果。
3. “已 push 双端一致”“全部完成”“全链闭环”等表述通常没有绑定 `repo + exact SHA + evidence path + CI run + runtime environment`。
4. 三份文档没有 `supersedes` 链，旧判断与后续用户纠正混排；不能用最后一段自动总括替代逐条冲突裁决。
5. 它们没有 ChatGPT Project ID、ChatGPT conversation ID 或云端项目会话正文，不能证明三个 ChatGPT 云端项目对话已被完整读取。

因此，三份文档的正确地位是 **A4 历史候选证据**。其中能够被当前 main、精确提交、测试回执或用户最新决定复核的项目，才可提升；无法复核的“完成”只能标记为 `HISTORICAL_CLAIM` 或 `LOCAL_ONLY`。

### 21.2 本轮实际使用的四向对照方法

每一项声明都同时经过四个方向：

| 方向 | 检查问题 | 可给出的最高结论 |
|---|---|---|
| 本地汇总 | 用户当时说了什么、工具声称做了什么、有哪些阶段性记忆 | 历史意图/历史声明 |
| 当前云端仓库 | 当前 main 是否存在对应文件、提交、代码、报告、测试或发布证据 | 当前实现事实 |
| 当前可检索历史决定 | 用户是否后来纠正、废止或重新定义该内容 | Owner 决定及 supersession |
| R2 全仓审计 | 声明是否与供应链、UI、适配器、SBOM、索引和边界证据一致 | 风险与整改判定 |

本轮采用以下状态词，避免再次把“写了”“测了”“推了”“发布了”混为一谈：

- `MATCH`：四向证据一致。
- `PARTIAL`：局部实现/历史测试有效，但不足以支撑整体完成。
- `LOCAL_ONLY`：只能证明某台机器、某个本地分支或某次会话状态。
- `STALE`：曾经可能正确，但已被当前 main 或后续决定替代。
- `CONFLICT`：汇总声明与当前可复核事实直接冲突。
- `UNVERIFIED`：缺少足够证据，不能判真。

### 21.3 仍然缺失的云端对话层

这三份文件显著增强了本地历史覆盖，但没有填上用户最关心的全部缺口：

- 没有 `AAOS项目`、`WORK-LAB`、`DESIGN-LAB` 三个 ChatGPT Project 内的完整云端对话导出。
- 没有 HERMES、OPEN DESIGN、OPEN HUMAN 等软件中所有私有会话的逐字原文与工具回执。
- 当前可检索的 Personal Context 只能返回被索引的决定和事实，不等于账号全部历史记录。
- 本轮没有可复用的已登录 ChatGPT Project 浏览会话，因此不能假装“已经看完云端三组项目对话”。

这不是阻止当前审计的理由，但它阻止两类结论：不能宣布“聊天历史全量审完”，也不能根据汇总去做不可逆删除。

---

## 22. WORK-LAB 四向交叉结果

当前核验基线：`origin/main = c2cb6dc`。该提交标题本身已经把闭环纠正为 `STRUCTURAL_PASS, runtime PENDING`。

| 汇总中的主要声明/决定 | 当前仓库或历史证据 | 判定 | 纠偏 |
|---|---|---|---|
| WORK-LAB 是跨软件、跨项目治理控制面 | `PROJECT_POSITIONING.md`、配置所有权、适配器/TaskPack/Observer 结构与用户最新决定一致 | `MATCH` | 保留定位，但只管理合同、覆盖层、权限、任务和证据，不吞并项目业务真相 |
| 当前软件含 Hermes、Codex、CC Switch、GitHub、Open Design、OpenHuman、DSH | `PROJECT_POSITIONING.md` 与 `software-registry.json` 含 DSH；根 `AGENTS.md` 的 managed client 列表漏 DSH | `CONFLICT` | 修复仓内 SSOT 分裂；同时把“当前软件”与“永久支持范围”分开 |
| “全面闭环完成”“可本地闭环全部完成” | 当前提交明确为结构通过、运行待验；对账仍有 PASS 31、PARTIAL 8、PARTIAL_BLOCKED 2、NOT_RUN 17、READY_FOR_APPROVAL 2、BLOCKED 3、BLOCKED_USER_DECISION 1 | `CONFLICT` | 不得再用单一“完成”覆盖运行、外部软件、人审、发布和迁移门禁 |
| 全量 `979 passed + 62 subtests` | 汇总保留了对应历史回执；当前仓库也保留关单/任务记录 | `PARTIAL` | 只证明对应 SHA/环境的测试集合通过，不证明真实软件适配、UI 语义、长期 soak 或产品完成 |
| G4/CI/行为探针均已闭环 | 汇总后段自己仍记录 `070行为探针未执行`、`G4未merge`；当前关单提交再次纠正运行待验 | `CONFLICT` | 以分层状态表为准，不用更早“全部完成”覆盖后续未完成记录 |
| Observer 已完全可用 | 汇总中用户连续指出数据不准确、布局过重、状态展示错误、需要真实数据和 Windows 风格；R2 又发现生产 React 映射会改变事实语义且未进 CI | `CONFLICT` | 代码存在不等于产品验收；必须做真实数据 schema contract、视觉/交互和生产构建门禁 |
| Observer 应展示全项目运行位置、平台、活跃/阻塞、Token、配置与健康 | 这是多次用户纠正后的稳定 UI 目标 | `MATCH` | 固化为 Owner-confirmed UI contract，不能退回开发者任务矩阵首页 |
| 知识迁移已完成或应立即全面迁移 | 用户历史决定是先暂停，待 ArcheAxis 稳定后再逆向归档可执行资产 | `STALE` | 当前只保留 provenance、候选映射和未来迁移合同，不做大迁移 |
| WORK-LAB 不应保留任何软件配置 | 该旧方向已被用户后续明确推翻 | `STALE` | WORK-LAB 必须保留并治理跨软件全局配置；项目专业配置仍归项目 |
| “官方更新”可用本地重新打包/自制 launcher 代表 | 用户已纠正：必须是厂商正式版本、正式格式和真实官方入口 | `CONFLICT` | 将 official provenance、vendor version、signature/release source 变成门禁 |
| 三项目全局规则已经完全统一部署 | WORK 与 ArcheAxis 当前有根 `AGENTS.md`；DESIGN 当前 main 无根 `AGENTS.md`，相关 DESIGN 提交不在可见 refs | `CONFLICT` | 不能把一次本地多仓写入叙述当作云端完成 |
| WORK 汇总中的 `305bd8d` 与后续 `c2cb6dc` | 两者在当前 WORK 可见 Git 对象中均存在 | `MATCH` | 可作为 WORK 历史证据，但仍须按各自 SHA 解读状态 |

### 22.1 WORK-LAB 新增根因

WORK-LAB 的问题不只是“上下文丢失”，而是同一仓库内部也存在不同权威面的漂移：根规则、项目定位、软件注册表、TaskPack 汇总、运行回执和 Observer UI 没有由同一状态机生成。换软件后只是把这个内部矛盾放大了。

正确修复不是给每个软件再写一份长摘要，而是：

1. 用一个机器可读 `PROJECT_CONTRACT` 声明定位、当前客户端、可替换客户端、数据所有权和唯一 UI。
2. 用一个 `DELIVERY_STATE` 分开 structural、unit/integration、live adapter、human gate、CI、release、deployment。
3. Hermes/Codex/DSH/Open* 等入口只读取同一合同生成的投影。
4. Observer 只消费带 provenance 的状态事件，不从文件名、旧报告或假数据猜状态。

---

## 23. DESIGN-LAB 四向交叉结果

当前核验基线：`origin/main = 9468c40`。

| 汇总中的主要声明/决定 | 当前仓库或历史证据 | 判定 | 纠偏 |
|---|---|---|---|
| DESIGN-LAB 是平台中立的专业设计智能、质量与生产能力所有者 | 用户最新定位、仓库 first-party atoms/domain packs/gates/adapters 基本一致 | `MATCH` | 继续坚持设计域，不扩成通用 Agent OS、知识 OS 或第二聊天软件 |
| 根 `AGENTS.md` 已补并引用全局标准/LESSONS | 当前 main 根目录没有 `AGENTS.md` 或 `LESSONS_LEARNED.md`；只存在 vendored/nested 控制文件 | `CONFLICT` | 汇总描述的是未进入当前 main 的本地/其他分支状态，不能作为云端规则 |
| `648 个设计专家技能库` 是当前云端项目源 | 当前树实测仅 217 个 `SKILL.md`；6 个 active source、162 个 quarantine entry；648 更像旧本地/运行时统计 | `CONFLICT` | 分开 canonical skills、vendored files、运行时投影和 quarantine，禁止拿文件数代表能力数 |
| DESIGN 提交 `022e31d`、`d2488d2` 已 push 双端一致 | 两个提交都不在当前 clone 的可见 refs；当前 main 为 `9468c40` | `CONFLICT` | 在完整 refs/远端找回前，只能标 `LOCAL_ONLY_OR_MISSING_REF` |
| 当前分支 `codex/pixel-perfect-vector-reconstruction` ahead 29/behind 1 | 这是汇总记录的本地分支状态，不是当前云端 main | `LOCAL_ONLY` | 需要单独导出该分支/ref 和未跟踪 handoff，才能决定合并、重做或废止 |
| 已“吸收全部”开源设计项目 | 13 个会话主要是调研请求/子报告；当前适配证据多数为 E0/E1，162 项仍 quarantine | `CONFLICT` | 调研、登记、vendoring、提炼、适配、运行验证必须成为不同状态 |
| 已能完整操作 Photoshop/Illustrator | 当前 Adobe Photoshop 为 declared/E0，Photoshop MCP 与 Illustrator MCP 仅 structural/E1；Illustrator 本机版本兼容问题曾阻塞 | `CONFLICT` | 只有逐命令 capability evidence、可逆写入、回读和 editable handoff 通过后才能宣传 |
| Open Design 已适配 | 当前 Open Design 为 structural/E1 | `PARTIAL` | 可保留适配器方向，但不能写成生产级真实操控 |
| ComfyUI 与 MiniMax H3 已有运行证据 | 当前 reconciliation 为 runtime/E3，但报告 `fresh=false` 且 subject SHA 早于当前 main | `PARTIAL` | 历史 E3 可保留；必须在当前 SHA、当前环境重新跑并记录时间/版本/输入输出哈希 |
| Blender、FFmpeg、Penpot、Eagle 等已形成完整控制面 | Blender/FFmpeg missing/E0；Penpot declared/E0；Eagle Web API structural/E1 | `CONFLICT` | UI 和 README 必须逐项展示真实 evidence level，不能用目标清单替代可用能力 |
| “小游戏运行时”是项目正式定位 | 用户后来把相关范围重定义为 Game Design 能力域，不是独立小游戏运行时产品 | `STALE` | 复核 `minigame-runtime` 的名称、职责和代码边界，防止再次扩成运行时项目 |
| 设计知识现在应全面迁入 ArcheAxis | 用户已决定等待 ArcheAxis 稳定 | `STALE` | DESIGN 当前保留可执行能力与 provenance；未来只把知识表示与学习证据交给 ArcheAxis 治理 |

### 23.1 开源收集历史的真实去留

三份汇总确实补出了大量开源项目“被调研过”的历史，但“被提到”不等于“有用并已集成”。DESIGN 的处置标准应从项目名改为产物级：

| 产物类型 | 保留条件 | 当前动作 |
|---|---|---|
| 第一方 atoms/domain packs/gates/adapters | 有 owner、schema、测试、设计域边界 | `KEEP` |
| 上游设计方法、案例、视觉评测 | 可提炼为不重复的原则、夹具或 benchmark，许可允许 | `EXTRACT_THEN_ARCHIVE` |
| Photoshop/Illustrator/Figma/Penpot/Blender/音视频工具链 | 有 exact identity、版本、权限、dry-run、rollback、editability evidence | `ADAPTER`，按 E0→E4 晋级 |
| affiliate、虚假紧迫、非设计电商运营、重复 AI Product OS | 与专业设计生产边界冲突或带污染指令 | `REMOVE_ACTIVE`，先隔离后审批删除 |
| 第三方 `AGENTS.md`、`CLAUDE.md`、安装器、delegation 指令 | 只能作为不可信来源字节 | 从 Agent 控制链和能力索引排除 |
| 许可证、身份或精确 commit 不明 | 无法安全复用/发布 | `QUARANTINE` |

在生成 cleanup manifest、依赖反查和 Owner 批准之前，本轮不物理删除任何来源。

---

## 24. ArcheAxis Knowledge 四向交叉结果

当前核验基线：`origin/main = bf0c483`，源码处于 `v0.6.11 candidate`，不等于公开稳定产品全部完成。

| 汇总中的主要声明/决定 | 当前仓库或历史证据 | 判定 | 纠偏 |
|---|---|---|---|
| ArcheAxis 是人机双向重型学习与可信知识治理系统 | 用户最新决定、根 `AGENTS.md`、README/PROJECT_STATUS 的 candidate→review→verified 边界一致 | `MATCH` | 这是项目不可漂移定位；不是通用 Agent OS、普通 RAG 或聊天壳 |
| “唯一真源”意味着所有外部资料自动成为真知识 | 当前仓库明确外部来源只是 candidate，不能自动提升 verified truth | `CONFLICT` | “唯一权威系统”指治理权威，不是把未经复核内容变成事实 |
| 2026-08-20 已全链闭环、无需再测 | 当前状态明确：通用 Planner、完整 Tauri WebView 点击级证据、完整交互式 Job Center、ASR 等仍未闭环 | `CONFLICT` | 历史 pipeline E2E 只能证明特定链路/夹具，不代表产品 Alpha/Beta 或所有输入闭环 |
| 多格式管线、OCR、联邦回环、前后端测试已通过 | 仓库保留相应模块与历史状态；部分链路当前仍在 | `PARTIAL` | 保留为历史 exact-SHA 证据；重新绑定数据集、模型、环境、fixture hash 和当前回归结果 |
| `ceshi` 22,422 文件、20,888 转换、93.1% | 这是特定本地数据集和某次管线运行的汇总，不在 Git 中提供可重放原始集与完整回执 | `LOCAL_ONLY` | 不得把本地覆盖率写成全格式/全产品完成；需匿名 manifest 与可复现实验协议 |
| 已完整吸收所有开源知识项目 | 当前仓库 ledger 仍区分 CURRENT/ADOPT/EVALUATE/SIDECAR/REVIEW-BLOCK/REJECT；旧池还有重复与误项 | `CONFLICT` | 研究、候选、已采纳、运行依赖和拒绝必须分层；无用项从 current view 移除但保留 provenance |
| 根 `AGENTS.md` 已引用 WORK-LAB 全局标准，同时项目可独立运行 | 当前根规则存在，但引用 WORK-LAB 外部路径，仓内没有该正式标准副本 | `CONFLICT` | 可选联邦协调可以外链；启动必需规则必须仓内自包含并带版本/hash |
| 汇总中的提交 `3255c1a` 已 push | 当前可见 refs 中缺失该提交；当前 main 为 `bf0c483` | `UNVERIFIED` | 完整 refs 或远端回读找到前，不作为云端完成证据 |
| 0.5.0 installer 已发布 | 当前 README/Release 台账承认 0.5.0 历史发布；当前源码已推进到未发布 0.6.11 candidate | `MATCH/PARTIAL` | 历史发布成立不代表当前 candidate 已发布，也不代表签名、多端与全部产品门禁完成 |
| 当前 SBOM/第三方清单已完全覆盖发布 | `release_sbom.py` 仍读取 legacy `desktop/package-lock.json` 与 `desktop/src-tauri/Cargo.lock`，而当前 UI 根还有 `frontend` 与根 `src-tauri` | `CONFLICT` | SBOM 能运行不等于覆盖正确；必须改为 canonical UI roots 并测试漏报 |
| PDF.js 依赖无需优先处理 | R2 已核出 vendored PDF.js 3.11.174 位于已知漏洞线，三份汇总未覆盖该风险 | `CONFLICT` | 升级、关闭 eval、加恶意 PDF 回归夹具，列为 P0 安全项 |

### 24.1 AAOS 前端为何最容易在换软件后丢语义

汇总主要记录“任务已做/测试已过”，没有把前端的用户语义变成不可绕过的合同。例如：返回动作、学习模式、Workspace、检查器、活动抽屉、证据溯源、Candidate/Verified 区分、窄屏与可访问性，常以聊天决定存在，却没有全部转成路由状态机、Playwright、视觉回归、a11y 和用户级任务测试。

因此，新工具看到 React 组件和几个截图时，容易保留“页面名称”，却重排交互、缩短信息链、展示内部 ID，或把学习工作台改成普通 dashboard。真正解决方法是把 UI 意图编译成验收合同，而不是再写一份只描述风格的摘要。

---

## 25. 跨三个项目的新总诊断与增强方案

### 25.1 这次新增审计出的“不止上下文”的问题

| 维度 | 共同问题 | 造成的后果 |
|---|---|---|
| 权威拓扑 | 多个文件都像权威，没有 owner、版本、hash、supersedes 和失效条件 | 换软件后各读一份，必然得出不同项目定位 |
| 完成语义 | 用户要求、助手承诺、测试通过、push、CI、真实运行、发布被压成“完成” | 大量假闭环和返工 |
| 本地/云端分支 | 汇总记录若干本地提交/分支，当前 main 不存在 | “双端一致”无法复核，规则和 UI 可能只活在旧机器 |
| UI 产品合同 | 设计意图、信息架构和状态语义停留在聊天/截图 | AAOS 与 Observer 换工具后最先漂移 |
| 适配器证据 | 声明支持的软件多，E2/E3/E4 真实回读少 | DESIGN 和 WORK 容易把目标能力写成现状 |
| 开源资产治理 | 调研、登记、vendoring、提炼、运行依赖混在一起 | 数量膨胀、指令污染、许可证/SBOM 漏报 |
| 测试口径 | 测试数量没有绑定 SHA、环境、数据集、覆盖对象和未测门禁 | 979 tests 或 93.1% 转换率被误解为产品完成 |
| 项目自包含 | ArcheAxis 运行规则外链 WORK；DESIGN 当前缺根合同 | 单仓交给新工具时无法独立重载 |
| 安全/发布 | PDF.js、SBOM roots、第三方控制文件、安装器说明等未进入摘要 | 摘要“全绿”，供应链仍有真实风险 |
| 人工门禁 | Owner 视觉验收、真实软件授权、不可逆删除、发布批准未与代码门禁分开 | Agent 容易越权宣布完成 |

### 25.2 三份本地汇总进入长期连续性系统的正确方式

原始文件保持只读，另生成规范化事件账本。每个最小记录至少应包含：

```yaml
record_id: stable-id
source_system: dsh|hermes|codex|chatgpt|github|local
source_session_id: original-id
source_timestamp: iso-8601
project_id: work-lab|archeaxis|design-lab
speaker: owner|assistant|tool|system
claim_type: decision|requirement|attempt|result|correction|deprecation
claim: normalized statement
status: candidate|owner_confirmed|repo_verified|runtime_verified|rejected|superseded
supersedes: [record-id]
target_repo_sha: exact-40-char-sha-or-null
evidence_paths: []
environment_fingerprint: null
owner_confirmation: null
```

流转边界应为：

1. 三份汇总先作为 `candidate/history` 摄入 ArcheAxis，原文与派生摘要分离。
2. 用户明确决定升级为 `owner_confirmed`；仓库/CI/运行证据只能升级“实现事实”，不能代替 Owner 定位决定。
3. WORK-LAB 从已确认记录生成跨软件规则和项目投影，不保存三个项目的专业知识正文。
4. DESIGN-LAB 只消费设计域决策、适配器合同和质量门；不复制全部知识库。
5. 每次工具启动运行 `continuity boot`：读合同 → 读 supersession → 校验 target SHA → 输出已知/未知/冲突 → 再接受任务。

### 25.3 对 ChatGPT 云端历史的补审要求

要达到用户要求的“所有历史对话全量审计”，还需要来自三个 ChatGPT Project 的可读原始导出或逐项目会话清单。最小导出字段应包括：project、conversation ID、created/updated time、speaker、完整 message、attachment refs、tool call/result、引用文件、删除/分支关系。拿到后执行：

1. 与本轮 92 个 DSH 条目去重，不重复计数。
2. 抽取 Owner 决定、纠正、UI 接受/拒绝、未完成项和开源去留意见。
3. 对同一命题建立时间线和 supersession，不采用“最后一份长摘要自动为真”。
4. 与三个仓库 exact SHA、branch/ref、CI、Release 和实际文件路径再次对账。
5. 把不能复核的声明留在 candidate；不因来自 ChatGPT 就自动提高权威级别。

### 25.4 R3 后的执行优先级

**P0：阻止继续误传**

1. WORK：统一 `AGENTS.md`、`PROJECT_POSITIONING.md`、software registry 的当前客户端；发布分层完成状态，废止“一句话全部完成”。
2. DESIGN：在当前 main 建立第一方根合同；隔离所有 third-party `AGENTS/CLAUDE`；重建只索引正式 manifest 的能力索引。
3. ArcheAxis：修复 PDF.js 与 canonical UI SBOM roots；把必需运行规则改成仓内自包含。
4. 三仓：建立 `CLAIM_STATUS` 和 `supersedes` schema，先把本报告列出的冲突登记进去。

**P1：把 UI 与适配能力变成实证**

1. AAOS/ArcheAxis：将历史 UI 契约转成 Playwright、视觉回归、a11y 和用户任务门禁。
2. WORK Observer：真实状态 schema contract、生产 React build/test、零假数据、状态语义回读。
3. DESIGN：按软件建立 E0 声明→E1 结构→E2 dry-run→E3 可逆运行→E4 可编辑交付证据链。

**P2：历史压缩与开源清理**

1. 补入三个 ChatGPT Project 原始会话导出。
2. 生成去重后的 decision/event ledger 与项目投影。
3. 对开源来源执行 `KEEP / EXTRACT / ADAPTER / ARCHIVE / REMOVE_ACTIVE / REJECT`。
4. 只有在来源、许可证、依赖反查、恢复清单和 Owner 批准齐全后，才做物理删除。

### 25.5 R3 的最终结论

三份本地汇总可以并且应该参与交叉审计；它们已经揭示了大量此前未进入 R2 的 DSH 用户纠正、UI 反馈、开源调研和本地分支历史。但它们不能替代 ChatGPT 云端三组项目对话，也不能替代仓库当前事实。

最关键的新结论是：丢上下文只是表象。真正的系统性故障是 **没有把 Owner 决定、当前代码事实、运行证据、UI 验收、软件适配等级和废止关系编译成同一条可验证权威链**。在该权威链建立前，摘要越多，冲突也可能越多。

本 R3 报告已把三份本地汇总纳入证据面并完成第一轮四向纠错；三个源汇总文件保持原样，未被改写。下一轮若获得三个 ChatGPT Project 原始会话导出，可在 R3 的记录模型上继续补审，而不需要推翻本轮仓库证据。

---

## 26. R4：完整 ChatGPT 对话导出的语料审计

### 26.1 输入文件与完整性

本轮收到的是三个项目的 ChatGPT 对话与时间线完整导出，不再是第 21 节审计的三份短汇总：

| 项目 | 文件 | 行数 | 字节数 | SHA-256 |
|---|---|---:|---:|---|
| WORK-LAB | `WORK-LAB完整项目对话与时间线汇报.md` | 432,344 | 15,558,839 | `a3bf2a60c38d6457ba94279d7f7b4323543361e406822992556461109d41916c` |
| ArcheAxis | `ArcheAxis完整项目对话与时间线汇报.md` | 489,390 | 20,219,699 | `fe4d647bb91be8df5f292ed0824b4195e34cca58cd9c19c2e64e159b3211dd1d` |
| DESIGN-LAB | `DESIGN-LAB完整项目对话与时间线汇报.md` | 229,424 | 8,961,542 | `df78b7fe3b109f6d0fdc646147f5c37c476689acca53a816c3a58a959069c0cf` |
| **合计** | 3 个文件 | **1,151,158** | **44,740,080** | 分文件校验如上 |

每个会话在可读转录后又附了一份原始 JSON。R4 只把可读转录作为一次语义实例，原始 JSON 用于结构核对，不重复计数。三个项目文件中共有 58 个项目内会话实例，按相同时间戳与标题去重后为 40 个逻辑会话，时间跨度为 2026-07-02 至 2026-08-24。

| 项目 | 会话实例 | 用户消息实例 |
|---|---:|---:|
| ArcheAxis | 24 | 363 |
| WORK-LAB | 18 | 287 |
| DESIGN-LAB | 16 | 154 |
| **合计** | **58** | **804** |

其中 9 个跨项目会话被三个导出同时收录，例如“DSH 对项目的影响”“项目优先级审计”“AI 视觉需识别吗”“上下文丢失原因分析”等。它们在语料覆盖中保留三份项目归属，在逻辑会话总数中只计算一次。804 条用户消息中有 625 个唯一文本哈希，179 条是跨项目或重复实例。

### 26.2 R3 的证据边界被怎样修正

R3 第 21—25 节关于“仍缺三个 ChatGPT Project 原始导出”的限制，现已由本轮材料补上。下列边界仍然存在：

1. 导出中的图片仅保留 `sediment://` 等资产引用；ArcheAxis 约 32 处、WORK 约 6 处，DESIGN 未检出。没有对应像素文件时，只能审计围绕图片发生的文字反馈，不能声称重新做了像素级视觉检查。
2. Hermes、DSH、Codex、本地工具或第三方软件的私有运行数据库、未写入对话的命令输出和本机文件仍不在导出中。
3. 对话导出证明“当时说过什么”，不能单独证明代码存在于当前 main、真实软件已经执行、CI 通过、发布完成或用户验收。
4. 本轮原始导出保持只读；所有规范化、去重、统计和裁决均写入派生索引与本报告。

### 26.3 完成性措辞只能作为风险信号

机械筛查得到：

| 项目 | 带纠正/否定/强约束信号的用户消息 | 带完成性措辞的助手消息 |
|---|---:|---:|
| ArcheAxis | 121 | 109 |
| WORK-LAB | 94 | 95 |
| DESIGN-LAB | 48 | 46 |
| **合计** | **263** | **250** |

这是关键词命中，不等于 263 次需求变更或 250 次虚假完成。它证明的是：三个项目都存在高密度的“先建议或宣布完成—用户纠正边界/体验/真值—再次实施”的循环。因此，今后必须把“完成”拆为七层：

1. `REQUESTED`：用户提出目标；
2. `PLANNED`：形成方案或 TaskPack；
3. `IMPLEMENTED_LOCAL`：本地文件/代码存在；
4. `TESTED_LOCAL`：绑定环境与输入的本地测试通过；
5. `CI_VERIFIED_EXACT_SHA`：当前精确 SHA 的 CI 通过；
6. `RUNTIME_READBACK`：目标软件、设备或安装态真实回读；
7. `OWNER_ACCEPTED` / `RELEASED`：用户验收或正式发布。

任一低层状态不得自动提升为高层状态。

---

## 27. R4 证据裁决模型

### 27.1 同一命题必须分三种权威

| 命题类型 | 最高权威 | 对话能否直接定案 |
|---|---|---|
| 产品意图、边界、名称、体验取舍、保留/废止 | 用户在时间线上最后一次明确且未被推翻的决定 | 可以，标记 `OWNER_CONFIRMED` |
| 当前实现、文件、版本、适配器、测试、CI、Release | 当前 exact-SHA 仓库、真实运行与发布回执 | 不可以，只能成为核验线索 |
| 审美、可用性、产品是否达到预期 | 用户验收记录＋可复现产品证据 | 助手自评、模型评分、截图生成都不能代替 |

这修正了过去两种相反错误：既不能让较新的 README 覆盖用户原始定位，也不能让较新的聊天总结覆盖当前代码事实。

### 27.2 声明状态机

R4 将所有重要声明归入：

- `OWNER_CONFIRMED`：用户最终明确决定；
- `REPO_VERIFIED`：当前 exact SHA 中可复核；
- `RUNTIME_VERIFIED`：真实目标运行时回读；
- `PARTIAL`：局部成立，不能支持总体完成；
- `HISTORICAL`：曾经成立或曾经提出；
- `SUPERSEDED`：被后续用户决定或实现替代；
- `CONFLICT`：意图、仓库或运行事实之间直接冲突；
- `UNVERIFIED`：证据不足；
- `REJECTED`：明确不再采用，必须进入禁回归清单。

### 27.3 不再信任“最后一段总结”

三个导出均包含助手生成的长总结、任务包、工具输出和阶段性结论。最后出现不代表权威最高。正确恢复顺序是：

1. 找到所有用户原始决定与纠正；
2. 对同一命题按时间建立 supersession 链；
3. 将用户意图与仓库实现分别裁决；
4. 用当前 exact SHA 和真实回读判断“做到了没有”；
5. 只有用户明确接受时，才记录体验完成。

---

## 28. 三项目历史演化与最终定位

### 28.1 WORK-LAB：从工具集合到治理控制面

时间线主干：

1. 2026-07-24 的模型中转讨论开始暴露“多软件配置、模型、上下文不一致”的真实问题。
2. 2026-08-05 的核心会话用 120 条用户消息反复收敛定位、软件清单、官方基线、配置边界、Observer、UI 和知识迁移。
3. 2026-08-10 的 54 条用户消息继续纠正“全部完成”、Observer 数据真值、界面质量和真实部署问题。
4. 2026-08-15 起 DSH 被纳入当前工作流，但应是可替换 Adapter，不是 WORK-LAB 的核心数据模型。
5. 2026-08-16—17 的监测工具调研说明 Observer 需要借鉴控制面与可观测性产品，而不是复制一个 Agent dashboard。

最终 Owner 决定：

- WORK-LAB 不是新的 Agent 软件、聊天客户端或模型网关。
- 它管理所有当前和未来工作流软件的用户级规则、技能、插件/MCP 声明、配置覆盖层、能力映射、任务、权限、回执、审计和跨项目执行。
- 官方软件和官方配置是基线；WORK-LAB 只维护声明过的用户 Overlay，未知字段必须保留。
- 软件/版本可替换，Canonical 配置与合同不能绑死某个客户端。
- 目标是高命中、低消耗、高效率；模型路由必须尊重用户选择、订阅和成本政策。
- Observer 绝对只读、覆盖所有项目、只显示有来源和新鲜度的真值。
- 项目同时需要一个与 Observer 权限隔离的控制/配置面，否则用户无法管理 Desired State、差异、计划、审批与回滚。
- 长期知识迁移等待 ArcheAxis 稳定；WORK 只暂存治理元数据和待迁移候选，不成为第二知识库。

### 28.2 ArcheAxis：从 Obsidian 辅助到双向重型学习系统

时间线主干：

1. 2026-07-02 从 `Obsidian-Assistance` 的安全写入、课程包和 Vault 工作台出发。
2. 2026-07 中旬扩展为 Knowledge、Research、Execution、Learning 的认知闭环，曾采用 Cognitive Loop OS、知行环、元枢等阶段性名称。
3. 2026-08-01—10 用户明确反对把它做成普通 AI OS、普通知识库或单向 RAG，要求“人学习”和“机器学习/复用”双向同等重要。
4. 2026-08-18—19 收敛三项目分层、知识归属和 AAOS/ArcheAxis 产品体验。
5. 最终名称锁定为 `ArcheAxis Knowledge / 星环知识平台`，内部体验可称 `ArcheAxis Learning Workspace`，技术名 `archeaxis-workspace`。

最终 Owner 决定：

- ArcheAxis 是本地优先、原件保全、证据可追溯的人机双向重型学习与可信知识治理系统。
- 原件、定位锚点、知识来源/主张、学习行为/掌握状态必须分开建模。
- OCR/ASR 转写准确度与事实正确性是两层验证，绝不能混为一个“可信度”。
- Obsidian/Markdown/JSON Canvas 是首个高保真垂直切片，不是最终产品边界。
- 核心数据模型、证据链、治理状态和学习生命周期必须稳定；OCR、ASR、模型、调度器、可视化、外部软件都应可替换。
- 初次使用选择 Evidence、Originals、Human Learning、Machine Learning 四个库/根，并明确外部依赖与插件库。
- 正式 UI 是完整桌面工作区，不是仪表盘：统一 Shell、Primary Rail、Context Navigation、可关闭 Inspector、可展开 Activity Dock，以及 Reader→Evidence→Learning 主链。
- 动态课程、动画、模拟、3D 记忆宫殿、VR/AR 等是长期绑定能力；当前可以延后，但合同与能力图谱不能删除。
- 外部知识/媒体获取必须遵守许可、服务条款、隐私与安全边界，“绕过限制”不能成为产品能力目标。

### 28.3 DESIGN-LAB：从 Open Design 附属到平台中立专业设计系统

时间线主干：

1. 2026-07—08 初期围绕 Open Design、3D、小游戏视觉和设计工具展开。
2. 2026-08-07 的核心 DESIGN-LAB 会话以 62 条用户消息明确项目独立身份、专业范围、视觉质量、真实软件控制与可编辑交付。
3. 2026-08-13 的 Adobe 讨论强化“宿主原生编辑、动作前验证、写后回读、可逆操作”。
4. 2026-08-16—17 大规模开源调研增加了能力候选，也引入 vendoring、指令污染、许可和“调研即吸收”的风险。
5. 2026-08-18—24 的跨项目讨论最终确定 DESIGN 拥有专业设计智能，WORK 拥有执行治理，ArcheAxis 拥有长期知识与学习。

最终 Owner 决定：

- 唯一项目身份是 `DESIGN-LAB / 设计实验室 / design-lab`；Open Design/OPEN-DESIGN-Assistance 只保留为历史别名或可选宿主 Adapter。
- DESIGN-LAB 平台中立，不绑定某个 Agent、模型、设计软件或画布。
- 它拥有 Design Intelligence、Design IR、专业领域包、风格/构图/字体/材质/视觉判断、质量评审、生产预检、软件适配与可编辑交付。
- 商业设计必须有人类方向锁定和最终视觉验收；自动评分、VLM 自评和技术测试不能代替审美判断。
- 需要轻量 Workbench 接收需求、资产、参考、方向、质量、预检、交付、Adapter 与证据，但不重复制造 Figma/Adobe/Blender/Open Design 的编辑画布。
- 平面、品牌、UI/UX、电商、编辑出版、包装、空间展陈、3D、动效、视频、音频、游戏视觉均为专业域；成熟度必须逐域、逐工具报告。
- 设计知识将来进入 ArcheAxis 治理；可执行领域包、质量门、Adapter 和生产合同仍归 DESIGN-LAB。
- MiniGame 是游戏设计域/测试夹具，不再是 DESIGN-LAB 的独立游戏运行时产品。

---

## 29. 明确废止与禁止回归的方向

| 历史方向 | 最终状态 | 原因 |
|---|---|---|
| 三个项目各自拥有一套通用 Agent/模型/视觉 Runtime | `REJECTED` | 重复建设、状态冲突、GPU/模型治理失控 |
| WORK-LAB 成为第二操作系统、第二知识库或吞并项目数据库 | `REJECTED` | 越过专业项目所有权，形成中央单点真源污染 |
| WORK-LAB 只做数据库、没有正式控制界面 | `SUPERSEDED` | 用户需要管理配置、计划、审批与回滚；只读 Observer 无法承担 |
| WORK-LAB Observer 可执行重试、审批、apply 或 rollback | `REJECTED` | 破坏只读证据面与信任模型 |
| ArcheAxis 是普通 RAG、聊天壳、文件管理器或通用 Agent OS | `REJECTED` | 偏离双向重型学习与可信知识治理核心 |
| 外部来源自动成为 Verified Knowledge | `REJECTED` | 来源内容最高只能成为 Candidate，需独立证据和人工复核 |
| OCR/ASR 置信度等同事实准确率 | `REJECTED` | 转写准确与事实正确属于不同验证层 |
| DESIGN-LAB 默认绑定 Open Design 或再造第二设计画布 | `REJECTED` | 平台中立与宿主原生编辑是最终边界 |
| 自动质量分或 AI 自评替代人类商业设计审批 | `REJECTED` | 技术正确不等于审美/品牌/商业正确 |
| MiniGame 作为独立运行时产品继续膨胀 | `SUPERSEDED` | 最终仅保留游戏设计域与验证夹具价值 |
| 强制所有任务都经过 WORK→ArcheAxis→DESIGN | `REJECTED` | 简单查询、学习或设计辅助应允许项目直达 |
| 新建第四个 GlobalGovernance 项目 | `REJECTED` | 全局治理协议应归 WORK-LAB，不再制造新权威层 |
| “提到/调研/复制了开源项目”即表示用户批准或能力已吸收 | `REJECTED` | 来源、许可、提炼、运行和验收必须分层 |
| “全功率、无成本上限”作为所有用户和 Provider 的根硬规则 | `CONFLICT` | 与用户低消耗、高效率目标冲突；应是可选策略而非强制基线 |

这些条目必须进入机器可读 `REJECTED_DIRECTIONS`/`supersedes` 账本，并由 CI 阻止 README、AGENTS、TaskPack 或 UI 再把它们写成当前方向。

---

## 30. 2026-08-25 云端 main 差异与 R3 纠偏

### 30.1 当前精确基线

| 项目 | 当前 main | tracked files | 最新提交摘要 | 相对 R3 |
|---|---|---:|---|---|
| WORK-LAB | [`2941412ec88b2b3e278753425255e31d97710295`](https://github.com/DTALEX66/WORK-LAB/commit/2941412ec88b2b3e278753425255e31d97710295) | 1,087 | DSH 2.0.2 cover-install handoff、AGENTS/config ownership 对齐 | 从 `c2cb6dc` 前进 |
| ArcheAxis | [`bf0c48396c751647ac76ee4578bc38f44888a23e`](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/commit/bf0c48396c751647ac76ee4578bc38f44888a23e) | 1,161 | prepare v0.6.11 candidate | 与 R3 相同 |
| DESIGN-LAB | [`38d322affaec163e7c7ca0e3610042285aab1f0f`](https://github.com/DTALEX66/DESIGN-LAB/commit/38d322affaec163e7c7ca0e3610042285aab1f0f) | 3,451 | pixel-perfect vector reconstruction pipeline | 从 `9468c40` 前进 |

本节只证明当前远端 main 与代码树事实；没有在本轮重新宣称三个 SHA 的所有 Actions、目标软件、安装态与发布均已验证。

### 30.2 R3 已被修复的结论

1. DESIGN-LAB 当前 main 已有根 `AGENTS.md` 和 `LESSONS_LEARNED.md`；R3 的“根规则不存在”已过期。
2. DESIGN-LAB 根许可证决定已明确为 MIT，`LICENSING_DECISION_REQUIRED.md` 已标记 resolved；但第三方材料的逐项权利链、REUSE/SPDX 和 Release gate 仍未完成。
3. ArcheAxis 项目状态已明确公开 v0.6.10 已发布、当前源码为 0.6.11 candidate；不能再沿用更早 release 版本描述。

### 30.3 R3 仍然成立的结论

1. WORK-LAB 权威索引仍声明唯一 CURRENT 为 `WORK-LAB-FORWARD-RECONCILIATION-2026-08-20 (WLR-000~960)`，但 `50-taskpacks/` 中仍没有该正文。
2. WORK-LAB `CURRENT_STATE.json` 仍明确 runtime evidence required，13 个技能 `live_readback: not-run`，Hermes live apply、paid provider smoke、真实设备、商业发布等未验证。
3. WORK Observer 的 CI 仍只跑 Python、legacy web 与合同测试，没有 `npm ci`、React production build、TypeScript/Vite 构建或 React 级端到端测试。
4. Observer React 仍在多个位置把缺失 Token 转成 0、把未知 dirty 状态显示为“干净”、把未知执行终态归入 success，并含未明确隔离的 mock 数据模块。
5. ArcheAxis 仍有根 `src-tauri` 与 `desktop/src-tauri` 两个相同 productName/identifier 的产品壳；一个是主前端，一个是 Recovery Shell，权威和发布入口需要进一步消歧。
6. ArcheAxis 的 SBOM 生成器仍只读取 `desktop/package-lock.json` 与 `desktop/src-tauri/Cargo.lock`，会漏掉 canonical `frontend` 与根 `src-tauri` 的依赖面。
7. ArcheAxis 仍 vendored PDF.js 3.11.174；升级、关闭危险兼容行为并加入恶意 PDF 回归仍是安全优先项。
8. DESIGN-LAB 的多数真实软件能力仍为 E0/E1；ComfyUI/MiniMax H3 的历史 E3 不能代表整个 creative toolchain。
9. 三个项目都仍缺统一的 Owner decision ledger、supersession graph、current task、resume receipt 与跨软件启动回读协议。

### 30.4 R4 新发现或新加重的问题

1. WORK-LAB 根 `AGENTS.md` 当前受管工作流列表仍漏 DSH，而 DSH 2.0.2 已进入交接和注册面，说明最新修复后 SSOT 仍未完全收敛。
2. WORK-LAB 根规则把“Full-power model”写成无 rate/cost caps 的强制基线，与用户明确的低消耗、高效率目标冲突。它应变成 Provider/任务级可选策略，并保留预算、质量和隐私三维约束。
3. WORK-LAB 根目录仍没有清晰的项目 License，公开仓库的复用边界未闭合。
4. DESIGN-LAB 新根 `AGENTS.md` 仍外链 WORK-LAB 全局标准，单仓启动并不自包含；还把 `minigame-runtime/` 描述为“小游戏运行时”，与最终游戏设计夹具边界冲突。
5. DESIGN-LAB 根规则绝对禁止设计产物进入共享库，但最终意图是允许经过审查的长期设计知识候选提交到 ArcheAxis；需要 `KnowledgeCandidate` 合同，不应绝对禁止或任意复制。
6. DESIGN-LAB 已把“pixel-perfect vector reconstruction”合入 main，但自身 `RECONSTRUCTION_CAPABILITY.json` 仍为 `NONCURRENT`、`boundSha=null`、全部 lifecycle false。功能名已经超过证据等级。
7. 重建模型注册表中多个默认模型使用全零校验和、绝对本机路径与 `UNQUALIFIED_CHECKSUM`；只有 VTracer 当前 qualified，OmniParser 因许可冲突正确禁用。运行时必须 fail closed，不能因在 main 中出现就自动启用。

---

## 31. WORK-LAB 综合产品、架构与整改裁决

### 31.1 正确产品结构：一个控制域、一个只读证据域

WORK-LAB 应有两个正式表面：

**Control / Configuration**：

- 软件与项目清单；
- 官方 baseline、用户 overlay、项目 overlay 的三方 diff；
- Canonical 配置与各软件投影；
- TaskPack、执行计划、权限、审批、暂停、回滚；
- Adapter 能力、风险、安装/版本、预检；
- 所有写操作先预览、再授权、后回读。

**Observer**：

- Overview、Executions、Projects、Delivery、Trust；
- 软件/Agent/项目当前运行位置、平台、活跃/阻塞、Token/成本、配置漂移、健康与证据新鲜度；
- 永远只读，不调用 apply/approve/retry/rollback，不写 Telemetry Ledger；
- 所有数值有 source、observedAt、freshness、quality、coverage；未知始终是 `UNKNOWN`。

二者的权限边界必须落在不同 Command/API 和 Tauri capability 中，不只靠前端隐藏按钮。

### 31.2 Canonical 配置应采用编译式投影

正确模型：

```text
Official Baseline
  + User Desired State
  + Project Overlay
  -> Canonical Typed Config
  -> Adapter Compiler
  -> Software-native Projection
  -> Dry-run / Diff / Approval
  -> Apply
  -> Native Readback
  -> Receipt / Drift Event
```

不得继续为每个软件手写一套互不相干的全量配置。Adapter 只负责映射、权限、检测、apply/readback 和版本差异；专业语义仍归各项目。

### 31.3 当前 P0

1. 把 WLR-000~960 正文恢复到仓库，绑定 SHA、hash、Owner 状态和 supersedes；索引不得指向仓外唯一正文。
2. 从 PROJECT_CONTRACT 生成根规则、软件注册表、Observer 投影和 Adapter 清单，消除 DSH 漏登记。
3. 把“全功率、无成本上限”改为任务/Provider 策略：至少有 `quality_floor`、`budget_mode`、`privacy_mode`、`latency_target`，默认尊重官方与用户设置。
4. 给根项目明确 License，并对 13 当前技能与 189 历史快照重新闭合 provenance/许可。
5. React production frontend 进入 CI：锁依赖、TypeScript、Vite build、组件合同、Playwright、a11y、Truth fixtures。
6. 删除所有未知→0/成功/干净/健康的映射；前端禁止本地猜价，价格和汇率必须是带版本的定价快照或 `UNKNOWN`。
7. Hermes、Codex、CC Switch、GitHub、Open Design、OpenHuman、DSH 逐个建立 detect→diff→dry-run→apply→readback→rollback 证据；没有 E3 的项目不显示“可用”。

### 31.4 并行执行策略

对同一项目可比“单写者＋只读复核”更快，但必须保留合并唯一性：

- 不相交模块可在独立 worktree 中由多个 bounded writer 并行；
- 每个 writer 有明确文件所有权和验收命令；
- 共享 Schema、锁文件、生成索引、版本文件由专门 owner 串行；
- merge queue 对 exact base 重新验证；
- Observer、审计与证据提取可并行只读；
- 同一工作树或同一文件仍只允许一个 writer。

---

## 32. ArcheAxis 综合产品、架构与整改裁决

### 32.1 四类不可混写的核心对象

| 对象 | 责任 | 不得替代 |
|---|---|---|
| `RawAsset / Original` | 保存原件、内容 hash、媒体类型、权利和版本 | 不能被 OCR 文本或摘要覆盖 |
| `Anchor / Annotation` | 精确定位页、段、时间码、区域、版本 | 不能只存脆弱的字符偏移 |
| `Claim / Provenance / Evidence` | 表达主张、来源、支持/反驳、责任活动和治理状态 | 模型置信度不能变成 Verified |
| `LearningEvent / MasteryState` | 记录学习行为、练习、复习、反馈和记忆调度 | 不能混入软件运行记忆或 WORK 状态 |

这四类对象分别对应原件保全、可定位证据、可信知识和双向学习，是 ArcheAxis 比普通 RAG/知识库更有价值的根基。

### 32.2 UI 合同必须从聊天迁入可执行验收

生产 UI 必须包含：

- 统一 Shell 与空间切换；
- Primary Rail 与 Context Navigation 分离；
- Reader/Canvas 为内容主角；
- Context Inspector 可关闭并随当前对象变化；
- Activity Dock/Transformation Center 默认紧凑、可展开；
- Original→Anchor→Candidate→Review→Evidence/Verified→Learning→Export 可回跳；
- Human Learning 与 Machine Learning 明确但可相互引用；
- 主题/tokens、窄屏、高 DPI、键盘、焦点、reduced motion、读屏均有门禁；
- 未来功能显示 `PLANNED`，不得用空数据或假卡片伪装可用。

历史截图的价值是交互合同与用户反馈，不是要求机械复刻某张图。没有原图像文件的 32 个引用不能进入像素验收；应要求重新绑定可访问的截图、viewport、主题、route 和数据 fixture。

### 32.3 当前 P0/P1

1. 明确 root `src-tauri` 为产品壳、`desktop/src-tauri` 为 Recovery Shell，或合并为一个构建；二者不能继续共享相同 identifier 却没有清晰发布权威。
2. SBOM/Notice 从 canonical frontend、canonical Rust root、Python lock 和 vendored runtime 资产生成；加入“漏掉一个锁文件即失败”的覆盖测试。
3. 升级 PDF.js 3.11.174，关闭不必要的动态执行兼容路径，加入恶意 PDF、超大对象、嵌套对象和 worker 隔离回归。
4. 先关闭 AXR-060 已列出的 SQL 白名单、Bundle/Inspector rights/conflict/history、真实失败→retry→replay、可访问性和干净 Windows Golden Journey。
5. 通用 Planner、ASR、完整 Job Center、Tauri 点击级证据按独立能力推进，不再用首条 `read file:` tracer 或 Chromium 局部链代表产品闭环。
6. 对外部知识/媒体接入增加 Rights Policy、robots/ToS、个人使用/商业使用、下载与缓存范围、撤回和删除合同。
7. 四库 onboarding、外部依赖库和迁移工具必须允许重定位，不能把 `D:\All projects\...` 固化为产品语义。

### 32.4 长期增强但不进入当前完成声明

- 动态课程与自适应学习路径；
- xAPI/FSRS 类学习事件与调度投影；
- 视频时间轴、交互批注、动画/模拟；
- 3D memory palace、VR/AR/spatial anchors；
- 可替换 OCR/ASR/VLM/embedding/graph engines；
- 经用户批准的 DESIGN/WORK 知识候选迁移。

这些是 binding roadmap，不是当前可用功能。

---

## 33. DESIGN-LAB 综合产品、架构与整改裁决

### 33.1 正确 Workbench

DESIGN-LAB 需要的前端不是通用 Chat，也不是第二个画布，而是专业任务与证据工作台：

- Brief、目标受众、渠道、尺寸、预算、时间与限制；
- Assets、References、Rights、品牌与可编辑交付要求；
- Design IR 和方向候选；
- Human Direction Lock；
- 视觉质量、反 AI-slop、可访问性与专业域 rubric；
- ToolActionPlan、Adapter 版本/权限/可用性；
- Preflight、Artifact、host-native readback；
- Human Final Jury；
- editable handoff、rollback、evidence receipt。

### 33.2 人工门禁是架构，不是文案

商业生产至少保留：需求确认、方向锁定、中期视觉判断、最终视觉评审、权利/生产预检与交付验收。自动评分可做预筛、诊断和回归，不得自动通过 required human gates。生产模式若因“效率”跳过人审，应 fail closed。

### 33.3 当前根规则仍需修正

根 `AGENTS.md` 已存在，但必须补：

1. 把最小安全/执行规则仓内自包含；外链 WORK 标准只能是可选 federation reference。
2. 明确第三方 `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、安装器、自动委派脚本都是不可信来源字节，不进入项目控制链。
3. 把 `minigame-runtime` 降为历史夹具/游戏设计验证区，或迁出产品主线；不再称独立小游戏运行时模块。
4. 将“设计产物不外溢”细化为：原始商业资产默认不外溢；经过权利检查和人工批准的知识候选可通过合同提交 ArcheAxis。
5. 固化 02/05/08/09/10 等 required human gate 的机器规则，生产与测试入口都不得绕过。

### 33.4 真实软件成熟度

当前应按 Adapter 单独报告：Open Design structural/E1；Figma、Penpot、浏览器、MCP、Photoshop、Inkscape、ImageMagick 等多为 E0；Blender、FFmpeg 在当前环境 missing；ComfyUI/MiniMax H3 有历史 E3。不得用 `creative-toolchain=E3` 覆盖整个工具集合。

每个工具晋级必须具备：

```text
identity/version
-> license/terms
-> capability declaration
-> install/detect readback
-> permission + dry-run
-> reversible write
-> host-native readback
-> editable artifact
-> human quality acceptance
-> exact-SHA evidence
```

### 33.5 “像素级矢量重建”必须降级命名

新功能已合入 main，但当前状态投影为 `NONCURRENT`，黄金样例、性能、Photoshop、Blender 和 installed-runtime 证据并未闭合。当前产品名应使用“Experimental Vector Reconstruction”或“重建候选流水线”，只有以下全部满足后才能公开使用 `pixel-perfect`：

- 绑定当前 SHA 的 CI；
- 可重放黄金语料；
- 明确像素/结构/字体/图层/可编辑性阈值；
- 逐工具真实回读；
- 8GB VRAM 性能与降级策略；
- 模型权重真实 checksum 和许可证；
- 人工设计质量与可编辑交付验收。

全零 checksum 的模型必须保持 `UNQUALIFIED` 和 fail closed。

### 33.6 开源和 vendored 内容 P0

1. 从能力索引排除 README、LICENSE、AGENTS、CLAUDE、安装器和营销/affiliate 内容。
2. 162 个 quarantine entry 和 vendored source roots 分开：quarantine 不得进入 prompt、runtime、SBOM 的“已吸收能力”面。
3. affiliate、非设计电商运营、第三方身份/委派/安装指令立即 `REMOVE_ACTIVE`；先断开索引和执行，再做物理清理。
4. 只提炼不可替代的设计原则、benchmark、fixture 或 Adapter 方法；原始快照归档并保留来源、commit、许可与提炼映射。

---

## 34. 三项目最终拓扑与数据所有权

### 34.1 不是强制串联，而是三种路径

**ArcheAxis 直达**：阅读、导入、检索、证据审核、学习、复习、知识治理。

**DESIGN 直达**：简单 Brief、方向探索、质量诊断、宿主软件内辅助；不需要 WORK 时不强制绕行。

**受治理生产路径**：

```text
User Brief
  -> WORK-LAB Work Unit / policy / permission / budget
  -> optional ArcheAxis evidence query
  -> DESIGN-LAB Design IR / direction / quality / preflight
  -> external host adapter and native editing
  -> human review / acceptance
  -> WORK-LAB receipt / delivery / audit
  -> approved knowledge candidate to ArcheAxis
```

### 34.2 所有权矩阵

| 对象 | WORK-LAB | ArcheAxis | DESIGN-LAB |
|---|---|---|---|
| Work Unit、TaskPack、权限、预算、执行状态、回滚 | Owner | Consumer/Producer receipt | Consumer/Producer receipt |
| 软件注册、Canonical 配置、Adapter 生命周期 | Global owner | 项目内 Adapter 配置 owner | 项目内专业 Adapter 配置 owner |
| 原件、Anchor、Claim、Evidence、Verified Knowledge | 指针/权限/审计 | Owner | Candidate producer |
| Human Learning、Machine Knowledge、Mastery | 不拥有正文 | Owner | 可提交设计学习事件 |
| Design IR、专业域、视觉判断、质量 rubric | 不拥有 | 可治理长期知识表示 | Owner |
| 设计资产、可编辑交付、宿主 ActionPlan | 执行/权限/回执 | 经批准的长期候选 | Owner |
| Telemetry/Audit | Owner 全局运行账本 | 项目事实回执 | 项目事实回执 |
| UI | Control＋Observer | Learning Workspace | Design Workbench＋宿主软件 |

### 34.3 跨项目只传合同和收据

不共享正式数据库，不复制全部项目内容，不让 WORK 读取专业私有数据。跨项目对象最小化为：

- `KnowledgeQuery / KnowledgeCandidate / EvidenceReceipt`；
- `DesignBrief / DesignIRRef / QualityDecision / EditableHandoffReceipt`；
- `WorkUnit / ActionPlan / Approval / ExecutionEvent / DeliveryReceipt`；
- 所有对象带 schema version、producer、subject SHA、content hash、rights、privacy、freshness 与 supersession。

---

## 35. 开源项目收集历史的完整对话结论

### 35.1 对话提及不等于 Owner 采纳

从可读转录中解析出的 GitHub 仓库身份：

| 项目语料 | 唯一仓库身份 | 用户直接提及 | 仅助手提及 |
|---|---:|---:|---:|
| ArcheAxis | 53 | 8 | 45 |
| WORK-LAB | 82 | 10 | 72 |
| DESIGN-LAB | 50 | 7 | 43 |

这是 URL 解析结果，不等于仓库内全部依赖清单；同名但没有 URL 的 UIClip、OpenCut、Flue 等仍属于“身份未解析候选”。最重要的裁决是：绝大多数链接由助手在调研或方案中提出，不是用户逐项批准。它们默认状态只能是 `RESEARCH_CANDIDATE`。

### 35.2 五级去留模型

| 状态 | 定义 | 处置 |
|---|---|---|
| `KEEP_ACTIVE` | 当前运行依赖或第一方能力，身份/版本/许可/调用/测试闭合 | 保留并锁定 |
| `KEEP_REFERENCE` | 不运行，只提供独特方法、标准或研究证据 | 从执行索引隔离，只读引用 |
| `EXTRACT_THEN_ARCHIVE` | 原仓很大或含污染，但有少量独特可提炼价值 | 提炼产物、保留映射和来源，原快照归档 |
| `QUARANTINE` | 身份、许可、安全、维护或用途不清 | 不进入 prompt/runtime/release，等待裁决 |
| `REMOVE_ACTIVE` | 与定位无关、重复、恶意/越权、affiliate/营销、已替代 | 先断索引/执行，再审批物理删除 |

### 35.3 三项目差异化保留原则

- WORK-LAB 只保留控制面、配置、策略、可观测性、供应链、测试和 Adapter 方法；不复制专业知识库。
- ArcheAxis 只保留原件/解析/证据/学习/知识治理所需引擎和标准；插件/引擎可替换，数据模型不绑定某上游。
- DESIGN-LAB 只保留设计方法、专业 benchmark、质量 rubric、生产预检与真实工具 Adapter；电商运营、affiliate、通用 Agent OS 和重复 UI 技能不进入活跃面。

### 35.4 物理删除前置条件

1. 精确仓库身份、commit、许可和来源路径已解析；
2. 反查代码、文档、CI、索引、prompt、release 和模型是否引用；
3. 有提炼产物、替代关系和内容 hash；
4. 生成 staged cleanup manifest 与可恢复包；
5. Owner 批准具体路径；
6. 删除后跑完整索引、测试、SBOM、License 和 runtime smoke。

在此之前只能“退出活跃面”，不能批量物理清空。

---

## 36. R4 独立整改任务包

### 36.1 TRI-G0：三项目基础治理清零

| ID | 任务 | 验收 |
|---|---|---|
| TRI-G0-001 | 三仓建立自包含 `PROJECT_CONTRACT` | 定位、所有权、UI、数据边界、外部依赖可机器解析 |
| TRI-G0-002 | 建立 Decision/Supersession Ledger | 本报告第 28—29 节所有稳定决定和拒绝项可回读 |
| TRI-G0-003 | 建立 Current Context Capsule | exact SHA、active task、dirty、blocker、next action、evidence scope 完整 |
| TRI-G0-004 | 建立 Resume Receipt | 任一新软件启动后输出已知/未知/冲突，不靠聊天摘要 |
| TRI-G0-005 | 分层完成状态 | 七层状态进入 Schema、UI、报告与 CI；禁止单字段 `complete=true` |
| TRI-G0-006 | 原始对话事件账本 | 40 逻辑会话、625 唯一用户消息可追溯到源文件/hash，不重复计数 |

### 36.2 WLR-R4：WORK-LAB

| 优先级 | 任务 | 完成标准 |
|---|---|---|
| P0 | 恢复 WLR-000~960 正文 | 仓内唯一 current、hash/owner/supersedes 校验通过 |
| P0 | 统一 DSH 与软件注册 SSOT | 根规则、registry、config ownership、UI 投影一致 |
| P0 | 修复模型策略冲突 | 质量/成本/隐私/延迟策略化，不再强制无成本上限 |
| P0 | Observer Truth 修复 | UNKNOWN 不再映射为 0/成功/干净/健康；定价带版本 |
| P0 | React production CI | install/build/type/test/e2e/a11y 全部在 exact SHA 运行 |
| P1 | Control/Observer 权限拆分 | 写命令只在控制面；Observer capability 与 API 只读 |
| P1 | Adapter E0→E3 | 七个当前软件逐项 detect/diff/dry-run/apply/readback/rollback |
| P1 | 根 License/来源治理 | 项目许可、13 active skills、189 snapshots 权利链闭合 |

### 36.3 AXR-R4：ArcheAxis

| 优先级 | 任务 | 完成标准 |
|---|---|---|
| P0 | 冻结 UI Contract v2 | Shell/Nav/Inspector/Dock/Reader/Evidence/Learning 进入 Playwright+a11y+视觉合同 |
| P0 | Canonical 壳裁决 | 主产品与 Recovery Shell identifier/build/release 权威无歧义 |
| P0 | PDF.js 安全升级 | 新版本、危险路径约束、恶意 fixture 与 worker isolation 通过 |
| P0 | SBOM root 修复 | frontend/root Rust/Python/vendored 资产全覆盖，漏报测试通过 |
| P1 | AXR-060 最短未闭环链 | SQL/rights/conflict/history/retry/replay/a11y/clean install 逐项收据 |
| P1 | 四对象模型 | RawAsset、Anchor、Claim/Evidence、LearningEvent 可独立版本与回读 |
| P1 | 外部摄入权利合同 | ToS/rights/privacy/cache/delete/revoke 可审计 |
| P2 | 长期能力接口 | 动态课程、模拟、3D/VR/AR 只冻结合同，不冒充实现 |

### 36.4 DLR-R4：DESIGN-LAB

| 优先级 | 任务 | 完成标准 |
|---|---|---|
| P0 | 根合同自包含与 MiniGame 纠偏 | 不依赖 WORK 才能启动；MiniGame 不再作为产品 Runtime |
| P0 | 第三方指令隔离 | vendored AGENTS/CLAUDE/cursorrules/installer 不进控制链、能力索引或 prompt |
| P0 | Human Gate fail closed | 商业 production 不能绕过方向、质量、权利和交付人审 |
| P0 | Reconstruction 降级与证据绑定 | NONCURRENT 不对外称 pixel-perfect；模型 checksum、golden、性能、host readback 完整后再晋级 |
| P1 | Design Workbench | Brief/Asset/Reference/Direction/Quality/Preflight/Handoff/Evidence 可用 |
| P1 | Adapter 逐软件成熟度 | 不再用总 E3；逐能力 E0—E4 与真实 editable artifact |
| P1 | 开源 Active 面清理 | affiliate/非设计/重复/越权内容退出索引；提炼与恢复清单齐全 |
| P1 | KnowledgeCandidate 出口 | 只把经权利与人审的长期知识候选提交 ArcheAxis |

### 36.5 TRI-X：真实跨项目闭环

1. 创建一个小型、非敏感、有明确权利的设计任务。
2. WORK 建 Work Unit、预算/权限与 TaskPack。
3. ArcheAxis 返回带 Anchor/Claim/Evidence 的候选知识，不自动 Verified。
4. DESIGN 形成 Design IR、方向锁定、宿主 ActionPlan、可编辑交付和人审。
5. WORK 收到 Execution/Delivery Receipt，Observer 只读展示同一事实。
6. 经人审的设计方法/经验作为 KnowledgeCandidate 进入 ArcheAxis。
7. 在 WORK、ArcheAxis、DESIGN 任一侧断开或失败时，均能明确显示 UNKNOWN/BLOCKED、重试/回滚和责任 owner。

只有该 exact-SHA、真实 Adapter、真实 Artifact、人工验收的闭环通过，才能宣称三项目联邦链完成。

---

## 37. R4 最终裁决与禁止过度声明

### 37.1 完整导出确认了什么

1. 三项目最终定位方向是经过多轮用户纠正后形成的稳定决策，不应推翻重做。
2. R3 发现的权威断链、UI 合同丢失、真值映射、适配器证据不足、供应链和发布问题大多成立。
3. 旧总结最大的错误不是漏几个问题，而是把不同完成层压成一句“全部闭环”。
4. WORK-LAB 和 DESIGN-LAB 的前端需求比 R3 判断更明确：WORK 是控制面＋只读 Observer；DESIGN 是轻量专业 Workbench＋宿主原生编辑。
5. 开源收集史大部分是助手提出的候选，不是 Owner 逐项批准；“有用就留、无用去掉”必须通过来源、用途、许可、调用与替代证据裁决。
6. 用户原始决定、当前仓库事实、真实运行证据和产品验收必须成为四条互相引用但不能互相冒充的权威链。

### 37.2 当前不得宣称

- 不得宣称 WORK-LAB 已真实管理全部当前软件；
- 不得宣称 Observer 已达到数据真实、生产 React 受 CI 保护或产品体验完成；
- 不得宣称 ArcheAxis 已完成通用 Planner、完整 ASR、完整 Job Center、Tauri 点击级 Golden Journey 或全部长期学习能力；
- 不得宣称 DESIGN-LAB 已完整操控 Adobe/Figma/Penpot/Blender 等全部软件；
- 不得宣称 pixel-perfect reconstruction 已完成或达到像素级标准；
- 不得宣称三个项目的真实联邦生产闭环已验证；
- 不得宣称所有开源项目已逐项完成许可、安全、维护度、用途和删除裁决；
- 不得再用测试数量、文件数量、技能数量、一次 CI 或一次本地运行代表产品完成。

### 37.3 正确下一步

停止继续扩写平行摘要。先执行 `TRI-G0`，把完整对话中已经稳定的 Owner 决定、废止项、当前 exact SHA、任务入口和恢复协议固化为仓内机器合同；随后三仓并行执行各自 P0，最后用 `TRI-X` 做一次真实小型跨项目闭环。任何开源物理删除放在 Active 面隔离、提炼、依赖反查和 Owner 批准之后。

本 R4 已将完整 ChatGPT 对话导出、R3 全仓审计和 2026-08-25 当前云端 main 合并为同一份执行裁决。三个原始导出文件保持只读，三个项目仓库未因本轮分析被修改、提交、推送、合并或发布。
