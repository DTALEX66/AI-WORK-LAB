# DESIGN-LAB 方向对齐验收报告（2026-10-19）

- **报告身份**：`DL-DIRECTION-ALIGNMENT-ACCEPTANCE-2026-10-19`；这是验收记录，不是第二账本、不是派工入口。
- **对应任务包**：`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`（`DL-TP-20261019-DIRECTION-R1`）。
- **Owner 决策**：`docs/taskpacks/20261019-direction/OWNER-DECISION-2026-10-19.md`。
- **来源包**：`DESIGN-LAB_96E591B0E6B4AEE6B4BBE5A18C%85.zip`，7,751 bytes，sha256 `5030488301b36ff0fefa15d0dbc2a3e02e780d3ade22ae548c6100d3e6a84023`；4 个成员逐字节落在 `docs/taskpacks/20261019-direction/source/`，逐成员 bytes/sha256 见 `docs/taskpacks/20261019-direction/SOURCE-MANIFEST.json`。
- **报告基线 SHA**：`05a768521d31379819227e07f378f97a38c542e3`（本批次落地提交的 SHA 由读取者自行 `git rev-parse HEAD`；不要抄本文件）。
- **范围**：只做 Authority/规划对齐、冲突矩阵、能力映射、可行性矩阵、最小真实闭环规划与按范围测试。**不实施产品功能。**

---

## 1. 结论

**PASS（本轮声明的范围：文档与规划闭环）**，但必须按分轴读：

| 轴 | 结论 | 依据 |
|---|---|---|
| 权威与规划对齐 | **PASS** | AUTHORITY/index/AGENTS/产品定义/边界/路线图/manifest/账本状态/文档定态/钉表全部一致；13 项文档闸与 10 项顶层权威闸通过 |
| 8 项必交付 | **PASS** | 见 §0 的交付清单，逐项有本文件小节对应 |
| 9 条验收标准 | **PASS（文档层）** | 见 §0 的逐条判定 |
| 最小真实闭环 | **PLANNED / BLOCKED（未执行）** | 需要真实宿主 E3、人工 E4、AAOS 接收或外部模型服务之一；均属 owner 门 |
| CI（subject `b2cd710c`） | **FAIL（唯一红项：Workbench browser E2E）** | §7.1：main 运行 `39153365631` 的两次 attempt 均为 `failure`；失败行是 palette-route 探针的标题断言，路由本身已落到 `#/capabilities/anydesign`。该 subject 仅改 `RECORD-IMPORT-MANIFEST.json`，未触碰 workbench 运行时或 E2E 代码；Python gate 等其余作业 `success`。该 FAIL 不改变文档范围判定，也不构成产品能力证据 |
| 产品能力 | **未提升** | 本轮没有改运行时代码；能力证据仍 E0/E1（50 条：E1=13 / E0=37），根 `evals/` 为 0、`design-lab/evals/` 仅 63 个受跟踪文件（reconstruction 6 例），无独立 Prompt Intelligence 运行时 |
| 真实运行 / 人工验收 / AAOS 接收 | **NOT_EXECUTED** | 没有真实调用、没有真人署名、没有 AAOS 回执 |

因此：**不能把本报告读成"产品已实现"、"闭环已跑通"或"能力已验收"。**

### 0.1 必交付核对（`source/ACCEPTANCE.md` 第 1–8 项）

| # | 必交付 | 落点 | 状态 |
|---|---|---|---|
| 1 | 基线记录 | §2 | ✅ |
| 2 | 定位冲突矩阵 | §4 | ✅ |
| 3 | 更新后的 Authority 与产品边界 + 差异摘要/替代关系 | §3、§4 | ✅ |
| 4 | 六大能力域能力映射表 | §5 | ✅ |
| 5 | 技术可行性矩阵 | §6 | ✅ |
| 6 | 任务重排建议（复用既有账本与 W00–W17） | §8 | ✅ |
| 7 | 测试/验证报告（命令、退出码、SHA、未执行项） | §7 | ✅ 本地定向闸 exit 0；CI 回执见 §7.1，结论 `FAIL`（唯一红项是 Workbench browser E2E 探针） |
| 8 | 修改文件清单、风险、回滚、下一步 | §3、§6、§8、§9 | ✅ |

### 0.2 验收标准核对（`source/ACCEPTANCE.md` 9 项）

| # | 标准 | 判定 | 证据 |
|---|---|---|---|
| 1 | 定位为专业视觉智能与可复用设计能力系统 | ✅ | AUTHORITY.md 2026-10-19 条；PRODUCT_DEFINITION 首节；AGENTS.md 项目定位 |
| 2 | 排除第二画布/通用编辑器/全流程文件交付平台 | ✅ | AUTHORITY.md、BOUNDARY_CONTRACT.md、product-manifest.json#nonGoals |
| 3 | 六大能力域均有输入/输出/边界/验证方式 | ✅ | 任务包 §3；本报告 §5 |
| 4 | 本地/云端/混合模型可替换，不把推测当已验证 | ✅ | 任务包 §6；本报告 §6；`model-manifest-trust.json#approved` 为空 |
| 5 | API/MCP/插件/脚本/UI 自动化有分层与真实任务验证要求 | ✅ | 任务包 §7；本报告 §6；MCP manifest 明示 `supported:false/E0` |
| 6 | WORK-LAB 通用治理与 DESIGN-LAB 专业能力边界明确 | ✅ | 任务包 §8；BOUNDARY_CONTRACT.md；PRODUCT_DEFINITION |
| 7 | AAOS 知识回流走候选/审核/接收，不直接写可信知识 | ✅ | 任务包 §8；AUTHORITY.md；本报告 §5 第 6 行 |
| 8 | 既有有效实现、历史证据、用户未提交更改得到保护 | ✅ | 本轮未改运行时代码；U09 未提交改动被排除在提交外；`design-lab/core/` 保持冻结 |
| 9 | 无虚构完成状态、虚构测试、未证实"已接入" | ✅ | 本报告 §10 的状态分离；§7 只列本轮实际跑过的命令；未执行项显式列出 |

---

## 2. 基线

- **仓库**：`D:/All projects/DESIGN-LAB`（GitHub `DTALEX66/DESIGN-LAB`）。
- **分支**：`qoder/designlab-backup-consistency-20261007`。
- **HEAD（本批次开始时）**：`05a768521d31379819227e07f378f97a38c542e3`。
- **工作树**：**不干净**。本批次开始时同时存在：
  - 已暂存的方向对齐改动（Authority/规划/注册表/钉表/方向包）；
  - 未暂存的 **U09 在途改动**：`apps/workbench/shell.ts`、`apps/workbench/tests/appshell.mjs`、`design-lab/config/contract-bindings.json`、`design-lab/tests/test_workbench_css_single_definition.py`、`src/design_lab/assurance/__init__.py`、`src/design_lab/http_service.py`、`src/design_lab/runtime/state_resources.py`，以及未跟踪的 U09 schema/SQL/test/module 文件。
  - 这些 U09 改动**不属于本批次**，未被 reset/checkout/清理，也未被提交。
- **Authority**：`/AUTHORITY.md`，稳定 ID `DL-AUTHORITY-2026-09-18-R2`，修订号 `DIRECTION-20261019-R1`。
- **索引**：`.project/governance/authority-index.json`，`currentIntegrated = docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`。
- **任务账本**：`design-lab/config/task-ledger-r3.json`；`currentExecution` 身份仍钉在 `DL-TP-20261009-UI-FIRST-R1`，34 项状态全为 `FROZEN_DEFERRED`。
- **生成投影**：`reports/current/*` 的 `subjectSha=05a768521d31379819227e07f378f97a38c542e3`、`subjectType=WORKTREE`；`generatedAt` 是生成时点值（见 `design-lab/config/current-report-index.json`），读取者应重跑 `--check`，不要抄本行。

---

## 3. 修改文件及每项理由

### 3.1 Authority / 规划面（已暂存）

| 文件 | 修改 | 理由 |
|---|---|---|
| `AUTHORITY.md` | 顶部新增 2026-10-19 owner direction adoption；稳定 ID 不变，修订号 `DIRECTION-20261019-R1`；2026-10-09 条降为前继记录 | Authority §17 要求 owner intent + reason + superseded rule + impact；保留历史而不是改写历史 |
| `.project/governance/authority-index.json` | `authorityRevision` 改为 `DIRECTION-20261019-R1`；`currentIntegrated` 与 `current` 指向新包；UI-FIRST 进 lineage 与 `historicalSpecific`（`SUPERSEDED_SCOPE_PRESERVED`） | 索引必须与 AUTHORITY 的当前包一致；旧的派工入口不能继续看起来像当前入口 |
| `AGENTS.md` | 项目定位/拥有/不拥有改写；新增 2026-10-19 owner 决定；当前任务包段改为新包；旧 2026-10-09 段降为前继 | 根执行规则必须让下一次会话先读到冻结与新方向，而不是继续按 UI-FIRST 派工 |
| `.project/manifest.yaml` | `taskpack: DL-TP-20261019-DIRECTION-R1`；`taskpack_path` 指新包 | 机器入口必须指向唯一当前包 |
| `docs/current/PRODUCT_DEFINITION.md` | 顶部新增 2026-10-19 定义（定位、六域、非目标、模型/工具策略、WORK-LAB/AAOS 边界、冻结）；旧 2026-10-09 定义保留为前继 | 产品定义是 Authority 的当前解释面；冲突条款必须被明确替代而非并存 |
| `docs/architecture/BOUNDARY_CONTRACT.md` | 顶部新增 2026-10-19 边界（禁止/允许/唯一前端壳/宿主/协作/冻结）；旧 2026-10-09 段保留为前继 | 防止"不造第二 Agent/画布"再次被误读或遗忘 |
| `docs/current/ROADMAP.md` | 版本 1.3；新增 R0–R5 当前路线图与"本轮证据边界"；J0–J5 保留为冻结前继 | 路线图必须反映"规划已就绪、执行冻结"的真实状态 |
| `design-lab/config/product-manifest.json` | positioning 改写；nonGoals 追加 6 条永久非目标 | 机器可读的产品定义必须与 AUTHORITY/AGENTS 一致 |
| `docs/current/NEXT-AGENT-PROMPT.md` | 就地重写为 2026-10-19 方向：新读序、冻结范围、六域映射、最小闭环规划、owner 门、工具事实 | 唯一接续入口必须指向新包；不得再铸日期副本 |

### 3.2 账本 / 注册表 / 钉表（已暂存）

| 文件 | 修改 | 理由 |
|---|---|---|
| `design-lab/config/task-ledger-r3.json` | 34 项 `currentExecution.tasks[*].state = FROZEN_DEFERRED`；新增冻结 note；`updated_at` 更新；`tasks/evidence/source/predecessor/taskpack/plan_path/baseline_sha` 与 `legacy_snapshot` 原样不动 | 执行"其他任务冻结"，同时不重写任务定义与历史证据；账本身份保持 UI-FIRST 是设计选择 |
| `design-lab/config/task-document-states.json` | 56 条文档定态 / 6 条前缀规则；UI-FIRST 改为 `SUPERSEDED / LINEAGE` 并带 `supersededBy`；新包成为唯一 `CURRENT / DISPATCH_ENTRY`；新增 `docs/taskpacks/20261019-direction/**` 冻结前缀规则；`why` 与 NEXT-AGENT-PROMPT 指针改指新包 | 文档定态闸要求恰好一个派工入口等于 index.currentIntegrated；旧包必须降级但不能消失 |
| `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` | 追加 2026-10-19 revision（from/to 哈希、why、checks）；`current_pins_note` 更新 | 钉表变更必须留下可审计的移钉理由与旧摘要 |
| `scripts/verify_top_level_authority.py` | `R2_RELEASE_HASHES` 5 → 6：重钉 AUTHORITY.md 与 index，新增新包哈希；旧五个保留；注释说明移钉依据 | Authority/index 字节已变，钉必须同批移动；新包作为冻结件必须被钉住 |

### 3.3 方向包落地（已暂存 / 新增）

| 文件 | 内容 |
|---|---|
| `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` | 集成派工入口：owner 决策、定位、六域、非目标、状态分离、模型/工具策略、WORK-LAB/AAOS 边界、界面方向、执行步骤、映射规则、验收、防漂移、状态声明 |
| `docs/taskpacks/20261019-direction/OWNER-DECISION-2026-10-19.md` | owner 原话、采纳范围、冻结范围、未执行项 |
| `docs/taskpacks/20261019-direction/SOURCE-MANIFEST.json` | ZIP 与 4 个成员的 bytes/sha256、landing 路径、"不是第二账本"声明 |
| `docs/taskpacks/20261019-direction/source/{TASKPACK,AUTHORITY,README,ACCEPTANCE}.md` | 来源包逐字节副本（inert record） |

### 3.4 报告生成物（随本批提交）

`reports/current/ADAPTER_EVIDENCE_RECONCILIATION.json`、`CLOUD_BASELINE.json/md`、
`DEEPSEEK-AUTHORITY-CHAIN.json`、`DOMAIN_PACK_READINESS.json`、`KNOWLEDGE_INVENTORY.json`、
`PROJECT_STATUS.json/md`、`RELEASE_READINESS.json`、`TASK_PROGRESS.json`，
以及 `design-lab/config/current-report-index.json`：由 `scripts/generate_current_reports.py` 在冻结后的账本上重生成；
`TASK_PROGRESS` 的计数为 `{'FROZEN_DEFERRED': 34}`。

### 3.5 本报告

`docs/audits/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`：验收记录，不派工、不覆盖 Authority。

---

## 4. 冲突矩阵与权威优先级

| # | 旧表述/做法 | 冲突原因 | 处理 | 影响文件 |
|---|---|---|---|---|
| 1 | "宿主原生的专业设计智能与生产能力层" | "宿主原生"容易被读成产品本体依赖宿主；新定位要求平台中立 | **AMEND**：定位改为"平台中立的专业视觉智能与可复用设计能力系统"；宿主原生保留为 Adapter 实现方式 | AUTHORITY.md、AGENTS.md、PRODUCT_DEFINITION.md、product-manifest.json |
| 2 | editable delivery / BOM / handoff 作为"拥有"的核心 | 与"不以全流程设计文件交付为产品本体"冲突 | **AMEND**：保留为能力输出、证据与受控交付手段，但不作为产品本体 | AUTHORITY.md、AGENTS.md、BOUNDARY_CONTRACT.md、product-manifest.json |
| 3 | 2026-10-09 "桌面 UI 优先"作为派工主线 | 新方向要求界面服务于能力，且本轮不实施产品功能 | **DEPRECATE（作为派工） / KEEP（作为技术壳）**：UI-FIRST 包降为 `SUPERSEDED / LINEAGE`；`apps/workbench` 仍是唯一前端技术壳 | authority-index、AGENTS.md、task-document-states、UI-FIRST 包 |
| 4 | `currentExecution` 34 项继续派工 | owner 明确"其他任务冻结" | **OWNER DECISION**：全部 `FROZEN_DEFERRED`；解冻需新授权 | task-ledger-r3.json、AGENTS.md、ROADMAP.md |
| 5 | 手机端本轮不实现不验收 | owner 2026-10-19 追加「再说一遍 不做手机端 只做桌面端」→「授权给你 去掉手机端」：它不是待排期项，而是排除项 | **AMEND**：由"冻结待排"改为**排除项**（处置层=现行面+权威条款，历史原文保留不改写，代码不动）；账本 `currentExecution.mobile` 是 schema const `FROZEN_DEFERRED` 且有测试断言，改词属状态词合同变更，本轮未改 | AUTHORITY.md 2026-10-19 条款、AGENTS.md、BOUNDARY_CONTRACT.md、authority-index `directionAdoption.mobile` |
| 6 | release / 安装态分发 / 真实宿主 E3 / 真人 E4 / E5 由 owner 授权 | 无变化 | **KEEP** | AUTHORITY.md、任务包 §10、NEXT-AGENT-PROMPT §7 |
| 7 | AAOS 是长期知识真值 | 与"受控知识回流"方向一致 | **KEEP + 明确候选制**：只提交候选并读取接收状态，不直接写可信知识 | AUTHORITY.md、AGENTS.md、PRODUCT_DEFINITION.md、BOUNDARY_CONTRACT.md |
| 8 | WORK-LAB 拥有通用治理 | 与"不接管 WORK-LAB"一致 | **KEEP + 明确非目标**：不成为通用 Agent Runtime/跨项目调度器 | BOUNDARY_CONTRACT.md、PRODUCT_DEFINITION.md、product-manifest.json |
| 9 | 禁止第二画布/通用 Agent Runtime/模型网关 | 与永久非目标一致 | **KEEP**（并在 AUTHORITY/AGENTS/manifest 三处重述） | 同左 |
| 10 | Open Design 是可选 Host Adapter；MiniGame 是 fixture | 与平台中立、非产品线一致 | **KEEP** | AUTHORITY.md §1、AGENTS.md |
| 11 | 旧 NEXT-AGENT-PROMPT 的下一刀是 D07 拆分 / D08 基准 / U09 切片 | 这些属于已冻结的 UI-FIRST 派工 | **DEPRECATE（本轮）**：入口改为方向对齐与最小闭环规划；旧内容只在历史提示词里保留 | docs/current/NEXT-AGENT-PROMPT.md |
| 12 | 云审计曾建议把 `design-lab/core/` 当死代码删除 | 与 `docs/architecture/DIRECTORY-AUTHORITY.md` 的明文冻结冲突 | **REJECT**：保持冻结；要动先改文档并给出 ADR | DIRECTORY-AUTHORITY.md（未改） |
| 13 | "能力资产/分析制作/成果反馈"作为主旅程 | 方向仍成立，但需要落到六域与新非目标下 | **AMEND**：保留为用户旅程素材，不作为定位句 | PRODUCT_DEFINITION.md、ROADMAP.md |
| 14 | W00–W17 是执行工作分组 | 新方向需要映射，但不能变成第二账本 | **KEEP（仅映射）**：复用 ID，不新增平行总账、不发明编号 | 任务包 §11、AGENTS.md |
| 15 | 账本 `currentExecution.taskpack` = UI-FIRST | 与 `.project/manifest.yaml` 新包指针不同 | **OWNER DECISION**：账本身份字段保持冻结；manifest 指向新包；authority chain 稳定产出恰好 1 条 drift finding，作为"待 owner 后续裁决"的显式记录，不静默改写 | manifest.yaml、task-ledger-r3.json、DEEPSEEK-AUTHORITY-CHAIN.json |
| 16 | ComfyUI/H3 曾有 2026-08-16 `runtime-pass` | 历史记录不等于当前 HEAD 可用性 | **KEEP（历史） / FROZEN（当前）**：不得当作当前可用性 | ROADMAP.md、integration manifests |

**权威优先级（冲突时从高到低）**：
`AUTHORITY.md`（`DIRECTION-20261019-R1`）→ `.project/governance/authority-index.json` →
`AGENTS.md` → 唯一当前包 → 账本 `currentExecution` 状态 → `docs/current/NEXT-AGENT-PROMPT.md` →
历史/交接/记忆/聊天摘要。历史只用于解释血统，不覆盖当前权威。

---

## 5. 六大能力域的实现映射与缺口

> 映射是"新方向落到哪些既有实现/任务"，不是新目录、新账本或新任务编号。
> 运行时规模按 HEAD 口径：`git ls-files 'src/design_lab/**/*.py' | wc -l` = 103 个 .py。

| 能力域 | 现有模块 / Schema / Registry / Adapter | 现有证据 | 缺口 | 既有 W / 任务 ID |
|---|---|---|---|---|
| **Visual Intelligence** | `src/design_lab/analysis/`（decomposition、plan_to_rir、model_cache、model_manifest、capability_library）、`packages/capabilities/reconstruction/`（34 个受跟踪文件）、`design_layer.py`、Reference/Asset 相关 runtime store | E1 结构；`design-lab/evals/reconstruction/` 有 6 例 golden corpus 与 `golden-corpus.json`；无六域级一致性与字段完整性实测 | 观察/推断/不确定性未形成可验证输出；无六域基准集；无真实图像分析运行记录 | W04、W05、W13；DL-FINAL-T09/T10/T11；DL-UI-U04/U05 |
| **Aesthetic Analysis** | `assurance/qa_plane.py`、`quality_record.py`/`quality_store.py`、`human_jury.py`、`jury_store.py`、`src/design_lab/jury_review.py`、`design-lab/config/design-tokens.json` | E1；Jury/质量记录层存在 | 无盲评一致性、维度区分度、反例覆盖；无 E4；无"客观可测/专业判断/个人偏好"三分类的实测 | W06、W08、W09；DL-FINAL-T12；DL-UI-U06 |
| **Prompt Intelligence** | 仅 `generators/comfy_http.py` 的请求字段；`git grep` 未发现独立 Prompt 运行时模块 | E0（结构引用） | 结构化提示词、图像反推、按目标模型/工具转换、不确定性标注、人工可用性评审全部缺失 | W07、W16；DL-FINAL-T09/T10；DL-UI-U04 |
| **Design Capability Library** | `design-lab/config/capability-index.json`、`capability-evidence-current.json`、`capability-status.json`、`packages/capabilities/`（178 个受跟踪文件，atoms 21 个目录，含 bundles/plugins/quality/standards）、`verify_knowledge_lifecycle.py` | 50 条能力证据：E1=13、E0=37；资格状态可追溯 | 去重/分类一致性、许可核验的批量实测；部分来源登记债（如 `tool-control` 长期未重观测）；"发现"与"合格"状态仍需分轴 | W02、W13；DL-FINAL-T05/T06/T07；DL-UI-U03 |
| **Creative Tool Automation** | `adapters/photoshop_com.py`、`adapters/illustrator_com.py`、`adapters/spi.py`、`generators/comfy_http.py`/`comfy_task.py`、`interop/penpot.py`、`integrations/adapter-registry.json`、`integrations/mcp/adapter.manifest.json` | E0/E1 为主；Open Design 为历史 `structural (E1)`（tree 2aca27f）；ComfyUI 2 条为 **2026-08-16 历史 E3**（ComfyUI 0.33.1，未在当前树复验，其中 H3 条目 `BLOCKED_BY_LICENSE`）；Photoshop/Illustrator MCP connect 为历史 E1 smoke（Adobe 已卸载）；Eagle 为 loopback 只读 E1；其余 Figma/Penpot/Blender/ffmpeg/browser/Adobe generator 等为 `declared (E0)`；MCP `E0, supported:false` | 分层选择策略已写、真实任务读回未做；超时/取消、失败模式、恢复/回滚逐项证据缺失 | W07、W10、W16；DL-FINAL-T13/T14；DL-UI-U05/U06 |
| **Knowledge Candidate & Evaluation** | `assurance/`（rights/preflight/jury/quality）、`design-lab/schemas/candidate-knowledge.schema.json`、`design-lab/schemas/contracts/knowledge-candidate.schema.json`、`knowledge-role-classification.json`、`verify_knowledge_lifecycle.py`、`packages/capabilities/schemas/knowledge-record.schema.json` | E1；候选字段与生命周期闸存在 | 无 AAOS 接收回读；无真实验收主体/时间/理由；无脱离人工的可信知识晋升路径 | W08、W17；DL-FINAL-T16/T18；DL-UI-U09 |

**明确缺口（本轮实测，不是推测）**：

- 评测集：根 `evals/` 为 **0**；`design-lab/evals/` 有 **63** 个受跟踪文件（其中 `reconstruction` **20** = 6 例 golden corpus + 索引，另有 rubrics 19、benchmarks 13）。**没有覆盖六域的评测集**，也没有 Visual Intelligence 的字段级一致性基准。
- Prompt Intelligence：只有 ComfyUI 请求字段；**没有独立运行时模块**。
- OCR：`Plan.from_ocr` 文本入口/对象计划存在，但**没有真实 OCR 引擎实现与生产调用方**；这不是接线问题，是产品判断。
- 真实宿主：没有当前 SHA 的 E3；Adobe adapter 的 E1 不能替代真实任务读回。
- 人工验收：`human_jury` 记录层存在，但没有 E4 的独立人审记录。
- AAOS：只有候选 schema/生命周期闸；没有接收状态回执。

---

## 6. 技术可行性与风险

| 能力 | 现有基础 | 可行性 | 需要的证据 | 阻塞 / owner 门 |
|---|---|---|---|---|
| 本地模型视觉分析 | `model_manifest.py`、`model_cache.py`、`readiness/model_radar.py`；`model-manifest-trust.json#approved` 为空 | 中 | 固定 fixture + 字段完整性 + 观察/推断分离 + 低置信标注 + 硬件/版本记录 | 需要已批准模型与硬件；ComfyUI/H3 已冻结 |
| 云端多模态分析 | `provider-capabilities.json`（全部 E0）；无运行时调用 | 中 | 目标模型/版本、请求/响应哈希、数据外发授权、失败/降级记录 | 数据外发与外部服务授权 |
| 混合路由 | 策略已写入任务包 §6；无路由运行时 | 中低 | 路由规则、回退、成本/延迟记录、隐私边界 | 需先有至少一条已验证的本地/云端路径 |
| 视觉分析字段抽取 | `analysis/decomposition.py`、`plan_to_rir.py`、`packages/capabilities/reconstruction/`、`design-lab/evals/reconstruction/`（6 例 golden corpus） | 中 | 六域字段级 golden fixture、跨样本一致性、失败样本 | 现有 6 例只覆盖 reconstruction，需扩为六域最小基准 |
| 提示词结构化与图像反推 | 无独立模块 | 中（结构可做，反推需模型） | 结构 schema、跨模型转换对照、人工可用性评审 | 模型/工具授权；不能宣称精确还原原始 Prompt |
| 官方 API/SDK（Adobe） | `photoshop_com.py`、`illustrator_com.py`、`integrations/hosts/adobe/**`；Adobe 已卸载，MCP connect 仅历史 E1 smoke | 中 | host/version、权限、调用、读回、失败/回滚 | 真实宿主 E3；GUI 启动需 owner 明确授权 |
| 原生插件（SPI） | `adapters/spi.py` | 中低 | 插件宿主版本、安装/卸载、读回 | 无当前真实宿主证据 |
| MCP | `integrations/mcp/adapter.manifest.json` | 低（当前） | 真实 MCP server 握手 + 工具执行 + 读回 | manifest 自己写明 `E0 / supported:false / 未接入真实 server` |
| 脚本/CLI | 仓库内 `scripts/`、`design-lab/scripts/` | 高（本地、可复算） | 退出码、stdout/stderr、产物哈希、幂等性 | 无外部服务，可先做最小闭环的"可验证输出"段 |
| 受控 UI 自动化 | 无生产实现 | 低 | 窗口/版本、权限、点击/输入、截图与读回、失败恢复 | 高风险，需 owner 明确授权；截图不等于成功 |
| 读回 / 恢复 / 回滚 | `runtime/native_recovery_lock.py`、`operation_coordinator.py`、`project_backup.py`、`migration_preview.py`、`audit_trail.py` | 中 | 真实操作后的读回、失败注入、恢复/回滚记录 | E1 结构层已有；缺真实任务证据 |
| AAOS 候选接收 | `candidate-knowledge.schema.json`、`knowledge-candidate.schema.json`、`verify_knowledge_lifecycle.py` | 中低 | 候选字段完整性、验收身份、哈希/撤回、接收状态回读 | AAOS 联调与写权限属 owner 门 |

**主要风险**：

1. **"文档已对齐"被误读成"产品已实现"**：本轮没有改运行时；所有能力仍是 E0/E1。报告与提交信息必须分轴写。
2. **账本身份与 manifest 指针不一致**：这是有意的冻结结果，authority chain 会稳定报 1 条 drift finding；若后续 owner 决定让 manifest 也回指 UI-FIRST，必须同批处理，不能双写。
3. **新包被钉住**：任何对 `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` 的编辑都必须走移钉流程，否则顶层权威闸红。
4. **U09 在途改动**：与本批次同一工作树；误用 `git add -A` 会把未完成的 U09 代码混进方向批次。提交时必须按显式路径 staging。
5. **评测集不完整**：根 `evals/` 为空，`design-lab/evals/` 的 63 个文件主要服务既有 reconstruction/rubrics/benchmarks；任何六域"固定样本集验证"都必须先扩基准，不能先宣称再补。
6. **历史运行记录**：ComfyUI/H3 的 2026-08-16 `runtime-pass` 不在当前 HEAD 复验，且已被 owner 冻结；不能作为当前可用性。
7. **许可/权利**：能力库条目、生成素材与第三方资源仍受 rights 约束；未核验不得标"合格"。

---

## 7. 测试命令、退出码、证据位置

**执行时点**：本批次提交前，工作树字节（含本报告与重生成的 `reports/current/*`）。
**证据日志**：`.project-local/runs/20261019-direction/minimal-gates.log`（gitignored 的本地运行产物；本文件引用其输出，不把它当受跟踪证据）。
**解释器**：`.venv/Scripts/python.exe`（系统 Python 缺 `jsonschema`）。

| # | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| 1 | `.venv/Scripts/python.exe scripts/verify_top_level_authority.py` | 0 | `TOP_AUTHORITY_GATE=PASS checks=10 failed=none` |
| 2 | `.venv/Scripts/python.exe design-lab/scripts/verify_task_document_states.py` | 0 | `TASK_DOC_STATE_GATE=PASS checks=13 failed=none` |
| 3 | `PYTHONPATH="design-lab;src" .venv/Scripts/python.exe design-lab/tests/test_current_execution.py` | 0 | `Ran 5 tests ... OK` |
| 4 | `PYTHONPATH="design-lab;src" .venv/Scripts/python.exe design-lab/tests/test_ledger_schema.py` | 0 | `Ran 40 tests ... OK` |
| 5 | `PYTHONPATH="design-lab;src" .venv/Scripts/python.exe design-lab/tests/test_task_ledger_contract_gate.py` | 0 | `Ran 4 tests ... OK` |
| 6 | `.venv/Scripts/python.exe design-lab/scripts/verify_product_manifest_v3.py` | 0 | `VERIFY_PRODUCT_MANIFEST_V3=OK total=493 failed=0` |
| 7 | `.venv/Scripts/python.exe scripts/deepseek_authority_chain.py --check` | 0 | `AUTHORITY_CHAIN=PASS (classification matches for 151 entries; ...)` |
| 8 | `.venv/Scripts/python.exe scripts/generate_current_reports.py --check` | 0 | `CURRENT_REPORTS=PASS mode=check scope=bound-input-integrity current-git-and-cloud=NOT_VERIFIED` |

**已知且被记录的 drift finding（不是失败）**：

`reports/current/DEEPSEEK-AUTHORITY-CHAIN.json#drift_findings` 恰好 1 条：

```json
{"path": ".project/manifest.yaml", "field": "taskpack",
 "recorded": "DL-TP-20261019-DIRECTION-R1",
 "current_authority": "DL-TP-20261009-UI-FIRST-R1",
 "action": "reconcile in DLDS-B040/B010; not silently rewritten by A010"}
```

原因：账本 `currentExecution` 的身份字段按任务包 §11 保持冻结，`manifest.yaml` 已指向新包。
`deepseek_authority_chain.py --check` 仍通过；这条 finding 是"待 owner 后续裁决"的显式记录。

**未执行项（以及原因）**：

| 未执行 | 原因 |
|---|---|
| 全量 Python 套件 / 大聚合闸（含 `verify_authority_gates.py --zero-spill`） | owner 明确要求"不要无限跑各类全量测试和各类大型闸门"；本批只改文档/注册表，定向闸已覆盖变更面 |
| 浏览器 E2E / UI 量化审计 | 本批未改前端运行时；U09 在途改动不属于本批 |
| 真实宿主 E3（Photoshop/Illustrator/ComfyUI/H3） | owner 门；H3/ComfyUI 已冻结；GUI 启动需明确授权 |
| 独立人审 E4 | owner 门；本轮没有真人参与 |
| release / 安装态分发 / E5 | owner 门 |
| AAOS 联调 / 接收回执 | owner 门；本轮不写 AAOS |
| 手机端 | **排除项**（owner 2026-10-19）；不再是"待排期冻结"。账本状态词仍是 schema const `FROZEN_DEFERRED`，未改 |
| E 盘访问 | 受保护；无精确授权不访问 |

**CI 回执**：本批次提交并推送后，按精确 SHA 逐作业读取，追加在本节（见 §7.1）。
**本地结论永远不是 CI 结论。**

### 7.1 CI 回执（提交后追加）

- **被验证提交（subject）**：`b2cd710c765ef4ce681ef891abb17779c7fbcabe`（`fix(records): declare the six files the direction batch rewrote`）；推送后工作分支与 `origin/main` 均指向它。
- **main 运行**：`39153365631`（Canonical Verify，event=`push`，ref=`refs/heads/main`，attempt=`2`，headSha=`b2cd710c765ef4ce681ef891abb17779c7fbcabe`）：`conclusion=failure`，https://github.com/DTALEX66/DESIGN-LAB/actions/runs/39153365631。
- **工作分支运行**：`39153360501`（event=`push`，branch=`qoder/designlab-backup-consistency-20261007`）：`conclusion=success`，https://github.com/DTALEX66/DESIGN-LAB/actions/runs/39153360501。开发分支按工作流条件跳过 11 个重型作业，不能当作全量证据。
- **同链前一轮失败（如实保留）**：run `39151365200`（headSha=`bb514458f6c47b746bbb3d49f38a7cfe55df3417`，本回执 subject 的父提交 `bb514458`）：`conclusion=failure`，https://github.com/DTALEX66/DESIGN-LAB/actions/runs/39151365200；失败作业：`Python gate (V3 verifiers + unit tests)` (failure)。CI 日志可读到 `PYTHON_TESTS_SHARD_RESULT shard=2/3 exit=1 tests=1083 wall_seconds=237.756 outcomes={'FAIL': 3, 'PASS': 1075, 'SKIP': 5}`；失败用例 id 不出现在 CI 日志中（模块计时行只到 `PYTHON_TESTS_MODULE_ALL     1.847s tests=4 test_record_import_fidelity`；`run_python_tests_all.py` 捕获并丢弃各 shard 的 stdout）。在干净 worktree `.project-local/worktrees/bb514458` 按 CI 同一分片命令复现出的 3 个失败用例全部属于 `test_record_import_fidelity`：`test_every_repo_held_row_is_accounted_for`, `test_recorded_hashes_match_the_files_on_disk`, `test_the_archive_still_equals_what_the_manifest_recorded`。根因是方向提交改写了 6 个 ALREADY-IN-REPO 文件却没有更新 `RECORD-IMPORT-MANIFEST.json` 的导入后演化声明。
- **修复提交（本回执 subject）**：`b2cd710c765ef4ce681ef891abb17779c7fbcabe` 仅更新该 manifest 六行的 `repoBytesAfterImport` / `repoCrc32AfterImport` / `repoSha256AfterImport` / `evolvedBy` / `evolution`；归档 `bytes` / `crc32` / `sha256` 未动，leg 1 仍校验 ZIP。修复后本机 `scripts/record_import_verify.py --head`：`RECORD_VERIFY scope=source+repo rows=492 source_verified=492 source_unreachable=0 worktree_verified=479 mapped_copies_verified=220 blob_verified=469 blob_eol_only=10 blob_absent=0 skipped=0`；本地 `test_record_import_fidelity`：`Ran 4 tests in 13.154s / OK`（`record-fidelity-tests.log`）。
- **同一 run 的 E2E 作业：逐 attempt 记录**：`Workbench browser E2E (exact-SHA controlled-runtime, no-skip)` 的 GitHub 作业尝试：attempt 1 `failure`（job `117751417448`）；attempt 2 `failure`（job `117754680652`）。attempt 1 的失败行：`palette-route: 1920 landed on #/capabilities/anydesign but the heading is "能力目录" not "anydesignsource · MIT"`；`BROWSER_E2E ran=9 skipped=0 failed=1`（归档 `ci-main2-failed.log`）。随后对同一 run 执行了一次单作业重跑；最后一次 attempt 的 gh 结论 = `failure`。本回执不判定首次失败的原因；重跑后仍未通过。
- **CI 结论（本回执）**：`FAIL`。本表只记录 gh 在该 SHA 上返回的逐作业结论；没有把 skipped 当 success，也没有把本地读数当 CI 读数。

**main 运行逐作业**：

| 作业 | 结论 |
|---|---|
| `Workbench browser E2E (exact-SHA controlled-runtime, no-skip)` | `failure` |
| `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)` | `success` |
| `Branch light gate (compile + identity boundary; development branches only)` | `skipped` |
| `License & secret hygiene gate` | `success` |
| `MiniGame node gate (+ drift check)` | `success` |
| `Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)` | `success` |
| `Python gate (V3 verifiers + unit tests)` | `success` |
| `DeepSeek authority gate chain (DLDS-H010 / DL-AUDIT-20260914-07)` | `success` |
| `Open Design host adapter gate` | `success` |
| `Generated-artifact clean-tree gate` | `success` |
| `Clean wheel install + Workbench launch gate` | `success` |
| `CI artifact proof (H001: main-run upload readback)` | `success` |

**工作分支运行逐作业**：

| 作业 | 结论 |
|---|---|
| `Branch light gate (compile + identity boundary; development branches only)` | `success` |
| `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)` | `skipped` |
| `CI artifact proof (H001: main-run upload readback)` | `skipped` |
| `Generated-artifact clean-tree gate` | `skipped` |
| `Workbench browser E2E (exact-SHA controlled-runtime, no-skip)` | `skipped` |
| `MiniGame node gate (+ drift check)` | `skipped` |
| `Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)` | `skipped` |
| `DeepSeek authority gate chain (DLDS-H010 / DL-AUDIT-20260914-07)` | `skipped` |
| `Python gate (V3 verifiers + unit tests)` | `skipped` |
| `License & secret hygiene gate` | `skipped` |
| `Open Design host adapter gate` | `skipped` |
| `Clean wheel install + Workbench launch gate` | `skipped` |

- **skipped 说明**：main 运行跳过 1 个作业（`Branch light gate (compile + identity boundary; development branches only)`）；工作分支运行跳过 11 个作业。skipped 不计入 success。
- **时点说明**：§7 第 8 条是提交前工作树字节上的读数。提交后在同一 HEAD 重跑会得到 `CURRENT_REPORTS=STALE ... stored_subject=05a76852… current_head=b2cd710c765e…`（exit 0）；这是生成器的时点语义（`subjectSha` 绑定工作树基线），不是失败。CI 不运行该命令（`canonical-verify.yml` 注释已说明 clean checkout 上无法 PASS）。
- **回执提交自身**：本回执作为独立 docs 提交推送；其 CI 结果另行读取，不作为 subject `b2cd710c765ef4ce681ef891abb17779c7fbcabe` 的替代证据。

---

## 8. 未完成事项、阻塞原因与建议下一步

### 8.1 未完成事项

1. 最小真实闭环的**执行**（分析 → 提示词 → 工具调用/可验证输出 → 验收 → 知识候选）。
2. 六域级最小评测集（现有 `design-lab/evals/reconstruction/` 6 例 golden corpus 可作起点）。
3. 独立 Prompt Intelligence 运行时（结构、反推、跨模型转换）。
4. 真实宿主 E3 与读回/恢复证据。
5. 独立人审 E4。
6. AAOS 候选接收回读。
7. 34 项冻结任务的解冻与新派工（需 owner 授权）。

### 8.2 阻塞原因

- **owner 门**：E3/E4/E5、发布/安装、AAOS、外部服务、E 盘、GUI 启动。手机端不在这里——它是排除项，不是等人点头的待办。
- **冻结令**：未来能力"暂时冻结和延期延后"；本轮不解冻。
- **证据缺口**：无六域级评测集（仅 `reconstruction` 6 例）、无 Prompt 运行时、无真实 OCR、无当前宿主证据。
- **数据/许可**：客户/私有素材默认不外传；未核验权利的能力不得标"合格"。

### 8.3 任务重排建议（复用既有账本与 W00–W17，不新增编号）

> 以下只是**建议顺序**；本轮全部 `FROZEN_DEFERRED`，执行需新的 owner 授权。

| 切片 | 内容 | 复用映射 | 需要的 owner 决定 |
|---|---|---|---|
| S0（可先做） | 固定 fixture + 本地确定性分析 + 结构化提示词 + 差异/读回工件；不依赖外部服务 | W04/W05/W13；DL-FINAL-T09/T10/T11；DL-UI-U04/U05 | 解冻这些任务 |
| S1 | 最小评测集与样本一致性（扩展现有 `reconstruction` 6 例 golden corpus 到六域） | W13；DL-FINAL-T06/T07 | 解冻 |
| S2 | 一个工具适配器的受控运行（E2）：脚本/CLI 优先，官方 API/SDK 次之 | W07/W16；DL-FINAL-T13 | 外部服务/宿主授权 |
| S3 | 真实宿主 E3 + 读回/恢复 | W07/W10；DL-FINAL-T13/T14 | E3 授权 |
| S4 | 人工验收 E4 | W08；DL-FINAL-T12 | 真人评审授权 |
| S5 | 知识候选 → AAOS 接收 | W17；DL-FINAL-T16/T18；DL-UI-U09 | AAOS 授权 |
| S6 | 发布 / 安装态 | — | 当前 `FROZEN_DEFERRED`（手机端不在本序列：已按 owner 2026-10-19 排除） |

**顺序理由**：S0/S1 不需要外部服务，能先把"可复算的视觉分析 + 提示词结构 + 读回工件"做实；
S2 之后每一步都跨一个 owner 门，不能靠文档或截图冒充。

### 8.4 建议下一步（给下一会话）

1. 先按 `docs/current/NEXT-AGENT-PROMPT.md` 的自读顺序核对 HEAD/CI，不抄本报告的数字。
2. 如果 owner 解冻：从 S0 开始，只改必要的运行时文件，交付"可审阅读回 + 真实数据源 + 可复现测试"。
3. 如果未解冻：保持本报告的"规划已就绪、执行冻结"状态，不把 PLANNED 写成 IMPLEMENTED。
4. 解冻后第一批应同时扩展 `design-lab/evals/` 的最小基准，否则"固定样本集验证"无从谈起。

---

## 9. 回滚方式

- **按批次回滚**：对本批次的落地提交执行 `git revert <sha>`（不要 `reset --hard`，不要改写历史）。
- **按文件回滚**：方向包、Authority/规划面、报告生成物分别 revert；顺序必须是
  `reports/current/*` → `task-document-states.json` → 账本状态 → manifest → 钉表/Authority/index → 方向包。
- **钉表回滚**：必须同时还原 `scripts/verify_top_level_authority.py` 的 `R2_RELEASE_HASHES` 与
  `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` 的 revision；只还原文件会让顶层权威闸红。
- **账本回滚**：把 34 项状态恢复到冻结前的值（从 git 历史读取），但**不得改写** `tasks/evidence` 冻结证据区与身份字段。
- **U09 在途改动**：本批次未触碰；回滚本批次不应影响它们。若工作树出现冲突，先备份再处理，禁止 `git checkout --` 覆盖用户工作。
- **冻结件**：`docs/history/taskpacks/20261009-adoption/**`、旧 UI-FIRST 包、R5 证据区按原字节保留；回滚不删除历史。

---

## 10. 状态分离声明（强制）

以下状态**互不替代**，本报告逐轴记录：

| 状态 | 本轮结果 |
|---|---|
| 文档修订 | ✅ 已完成（Authority/规划/注册表/报告） |
| 规划完成 | ✅ 已完成（六域映射、可行性矩阵、最小闭环规划、任务重排建议） |
| 代码实现 | ❌ 未实施（本批未改运行时代码；U09 在途改动不属于本批） |
| 真实运行 | ❌ 未执行（无真实宿主/模型/外部服务调用） |
| 人工验收 | ❌ 未执行（无独立人审 E4） |
| AAOS 接收 | ❌ 未执行（无候选提交/接收回执） |

**结论的边界**：本报告只能证明"方向已对齐、规划已就绪、定向闸通过"。
它不能证明任何能力已 Qualified、Accepted 或 Ingested；也不能证明最小闭环已跑通。
下一轮若引用本报告，必须同时引用其基线 SHA 与本轮未执行项。
