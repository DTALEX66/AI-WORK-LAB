# 20260928 后续任务包 —— 分析拆解与任务对齐

- **包来源：** `DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928.zip`
  sha256 `70592198dbd4ea0228ab1714143ec9e230f90237d19247b8831d586d64cfae85`，25,061 B，5 文件
- **解包位置（只读分析，未执行包内任何脚本）：**
  `.project-local/task-artifacts/designlab-followup-taskpack-20260928/`
- **包内研究基线：** `main@d116b14995fcdbba1b165ec5bc3124f5daed3d15`
- **本仓库 live HEAD：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15` → **完全一致**
  （即：本包是针对我上一轮 PR #175 合并后的 main 做的研究）

---

## 1. 包的性质（必须先定性）

| 属性 | 值 |
|---|---|
| 自称 | 增量研究与执行**建议**；**不是**产品验收报告、**不是**顶层 Authority、**不创建**第二任务账本 |
| 权威位阶 | 低于 `/AUTHORITY.md`、`authority-index.json`、`AGENTS.md`、当前 TaskPack 与唯一 ledger |
| 可执行性 | **有条件**：包内 41 个 `DL-*` ID 与本项目的执行 ID 体系**尚无 crosswalk**（见 §4-C1） |
| 状态写入路径 | 包内明文要求「执行状态继续写 `design-lab/config/task-ledger-r3.json`」——但该账本**契约上无法容纳新任务**（见 §4-C2） |

**结论：本包是"需求与建议输入"，不是可直接派工的任务包。** 必须先解决 §4 的 4 个冲突，才能进入执行。

---

## 2. 拆解

### 2.1 结构总览

```
00_README.md              阅读顺序 + 优先结论 + 核验限制
01_RESEARCH_AND_PRODUCT   决策摘要 / 云端核验事实 / 组件候选裁决 / 工作台形态 /
                          全部能力域路线 / AI·Skills·MCP / 旧UI资产处理
02_EXECUTION_TASKS        18 工作包 W00–W17 + 原41任务映射 + 5 波次 + 验收格式
03_EXECUTOR_PROMPT        可直接交给执行器的接管指令
04_SOURCES                30 条来源 + 核验边界声明
```

### 2.2 18 个工作包（按依赖拓扑）

| 包 | 标题 | 优先级 | 依赖 | 映射到 R5 |
|---|---|---|---|---|
| **W00** | 继承当前实现并生成差异映射 | P0 | — | R5-001/002/003/007/028 |
| **W01** | 视觉资产与 Token 基线 | P0 | W00 | R5-010/028 |
| **W02** | 组件体系生产兼容验证与裁决 | P0 | W00/W01 | R5-010/028 |
| **W03** | 项目中心与壳统一（**首个用户可见交付**） | P0 | W02 | R5-010 |
| **W04** | 参考与资产管理 | P0 | W03 | R5-005/013 |
| **W05** | Direction 与可修正对象计划 | P0 | W04 | R5-013 |
| **W06** | DesignSystem/Token 编辑与读回 | P0 | W05 | R5-010/013 |
| **W07** | 生产任务与**一个真实宿主** | P0 | W06 | R5-004/005/009/010/011或012 |
| **W08** | Review / Quality / Human Jury | P0 | W07 | R5-014 |
| **W09** | 真实生产预检 | P0 | W08 | R5-014/023 |
| **W10** | 可编辑 Handoff 与恢复 | P0 | W09 | R5-005/014/015 |
| **W11** | WORK-LAB 边界契约 | P1 | W00（不阻塞单机） | R5-021/023 |
| **W12** | 共享 FAST/DEEP 消费与故障 | P1 | W11 契约 | R5-006 |
| **W13** | 研究与领域能力产品化 | P1 | W04/W08 | R5-013/014/023 |
| **W14** | Windows 交互、性能与安装态（**横切**） | P0 | W03 起持续 | R5-009/010/015/028 |
| **W15** | 两条黄金流程与证据复审（**收口**） | P0 | W10/W14（联邦另需 W11/12） | R5-003/014/015 |
| **W16** | 按需扩展专业工具与媒介 | P2 | W15 单机链通过 | R5-008/016–022/024–027 |
| **W17** | 可选知识桥接与清理 | P2/条件 | W15 | R5-021/023 |

依赖链：`W00→W01→W02→W03→W04→W05→W06→W07→W08→W09→W10→W15`；`W11/W12` 联邦支线可与 W03 起交错但**不得阻塞单机**；`W13/W14` 并行；`W16/W17` 条件性。

### 2.3 5 个交付波次

| 波次 | 任务 | 用户可见 | 放行条件 |
|---|---|---|---|
| **A** | W00–03 | 统一可操作的项目/Brief 页面 | 继承真值、选型过门、真实保存 |
| **B** | W04–06 | 参考/方向/Token 编辑 | 数据版本读回、状态真实 |
| **C** | W07–10 | 工具生成、修改、审查、可编辑交付 | 真实宿主/失败修复/重开 |
| 联邦支线 | W11–12 | WORK-LAB 入口 + FAST/DEEP | 合同一致、双侧权限、故障可见 |
| **D** | W13–15 | 研究来源、Windows 稳定、两条黄金例 | 证据复审、视觉与安装态验收 |
| **E** | W16–17 | 按需扩展媒介与知识桥接 | 前链完成、真实业务需求 |

### 2.4 包内新引入的约定（TaskPack 里没有）

1. **5 个终态轴**：`DESIGNLAB_PRODUCT_VERTICAL_SLICE`、`DESIGNLAB_WORKBENCH_BACKEND`、
   `DESIGNLAB_SHARED_AI_CONSUMPTION`、`DESIGNLAB_WORKLAB_INTEGRATION`、`DESIGNLAB_PREFLIGHT_HANDOFF`
   → 输出 `PASS/PARTIAL/BLOCKED`
2. **11 个产品轴**：`CONTRACT/BACKEND/FRONTEND/PERSISTENCE/HOST_OR_GENERATOR/READBACK/QUALITY/
   RIGHTS/PREFLIGHT/DELIVERY/EVIDENCE`，**附在证据中、不得直接改账本四轴字段**
3. **12 态状态矩阵**：`empty/loading/partial/offline/tool-unavailable/provider-degraded/
   permission-denied/error/retry/long-running/cancelled/version-conflict`
4. **新性能目标**（**包内自标为"项目拟定目标，非现有实测"**）：热路由交互 P95≤200ms、
   本地首屏可交互≤2s、千资产索引不全量加载原图

---

## 3. 对齐：三类映射

### 3.1 可直接对齐（包内主张与本仓库一致，已核实）

| 包内主张 | 本仓库实测 | 判定 |
|---|---|---|
| 研究基线 `d116b14995fc…` | live HEAD 相同 | ✅ 一致 |
| CI run `36336694172` success，2 个 artifact | 同样读到；`workbench-e2-d116b14995…` + `secret-history-report`，均未过期 | ✅ 一致 |
| open PR 为空 | `gh pr list --state open` = `[]` | ✅ 一致 |
| 保留 strict TS/Vite/pnpm/browser E2E 与首条 Project→DesignSystem 链，不得重做 | TaskPack C 段 + AUTHORITY §15 均为 `CLOSED_WITH_REGRESSION_GUARD` | ✅ 一致 |
| 账本 28 项四轴全 PARTIAL = 复审待定，不等于未实现 | 实测 28 项、四轴全 `PARTIAL`、`reassessment` 全 `PENDING_EVIDENCE_REVIEW` | ✅ 一致 |
| `research`/`design-domains`/`collaboration` 明确未开放 | `shell.ts` 的 `VIEW_NOT_OPEN` 三槽 | ✅ 一致 |
| 资源路由仅固定 HTML/main.js/style.css，组件 CSS/图标/chunk 不能假设被服务 | `src/design_lab/workbench.py` `ROUTES` **只有 3 条** | ✅ **已在代码核实（硬约束）** |
| CSP 限制 self 样式/脚本 | `CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; ..."` | ✅ **已核实** |
| 构建兼容 classic-script VM 测试且不压缩 | `vite.config.ts` `minify:false`、D004 契约 + `unit.mjs` 断言 | ✅ 一致 |
| 深色品牌 `#060A14 / #0D1221 / #316CFF`，不得套库默认紫 | `style.css` `:root` 实测同值 | ✅ 一致 |
| GOLDEN-001/002 | = TaskPack **K 段**（当前 **NOT EXECUTED**） | ✅ 一致，且未虚报 |
| W01 原稿来源 `D:\All projects\UI套件` | **实测存在**，含 `04_B04_组件系统与DesignTokens_L4`、`10_B10_最终版高保真可部署UI` 等 12 项 | ✅ **可及**（包内称"仅定位未解包"） |

### 3.2 包内限制**已被本环境解决**

| 包内限制 | 现状 |
|---|---|
| 「分支保护端点返回 **403**（集成无该管理读取权限）」→ *"不能将 AUTHORITY 里的历史 9 个 checks 冒充今天实读"* | **本环境可读**：`gh api .../branches/main/protection` → **9 项 required checks**，`enforce_admins=true`、`strict=true`。**这是 live 实读，不是历史值。** |
| 用户 Windows 本地 dirty/未推送不可见 | 本环境可见：工作区**干净**、**0 未推送提交**、0 stash、1 worktree |
| CI artifact 只查元数据未下载校验 | 本环境可下载+hash（尚未执行，属新增动作，需授权） |

### 3.3 映射到 TaskPack A–O 段（本包相对既有 TaskPack 的**增量**）

| 本包 | 对应 TaskPack 段 | 增量性质 |
|---|---|---|
| W00 | A/B/C 段（继承与映射） | 补充"生成差异映射"的产出物要求 |
| W01/W02/W03/W14 | **D 段（Workbench 产品化）的细化** | **D 段原文只有 D001–D006 六条**；本包把 D 段展开为 4 个可验收工作包 + 11 个产品轴 |
| W04–W10 | **E 段（首条垂直切片）→ F/G 段（Native/Quality/Rights/Preflight/Handoff）** | E 段已 CLOSED；本包把 F/G 段细化为 7 个工作包 |
| W11/W12 | 不在 TaskPack 主体；属 AUTHORITY §1「不拥有」边界内的**联邦链** | **新增**（TaskPack L/J 段未覆盖） |
| W13 | G 段 + L 段 | 部分新增（ResearchFinding/MethodCard 持久化） |
| W15 | **K 段 GOLDEN-001/002** + H 段证据 | 新增 G-C（WORK-LAB 联邦黄金例） |
| W16/W17 | L 段（P2 扩展） | 细化 |

→ **本包实质上是把 TaskPack 的 D/E/F/G/K 段"展开成 18 个可验收工作包"。** 这与 TaskPack 不冲突，但**粒度和 ID 体系是新的**。

---

## 4. 关键冲突与缺口（实测发现，包内未解决）

### 🔴 C1 — 包内 41 个 `DL-*` ID **没有 crosswalk**，按项目规则**不可派工**

包内 §2「原41任务的完整覆盖」列了 41 个 ID：`DL-00/01`、`DL-WL-01…06`、`DL-AI-01…05`、
`DL-UI-01…10`、`DL-BE-01…07`、`DL-GJ-01…11`。

**实测：这 41 个 ID 在本仓库零命中**（对 `DL-UI-01`/`DL-BE-01`/`DL-GJ-01`/`DL-WL-01`/`DL-AI-01`
全仓 grep `*.json/*.md/*.py`（排除 node_modules/.venv/.project-local）= **NONE**）。

而 `AGENTS.md` 明文：**「旧任务 ID 必须经 crosswalk/current-capability 映射后才可执行」**；
`AUTHORITY.md` §12 同义。账本里只有 `R3-* → DL-R5-*` 的 `SUCCESSORS` 映射，**没有 `DL-UI-*` 这一族**。

→ **包的 41→W 映射表是自洽的，但它与仓库的执行 ID 体系之间缺一层映射。缺这层，W 包无法派工。**

### 🔴 C2 — 账本**契约上无法容纳** W00–W17（包内要求"写回该账本"）

包内 §0.1 与 §4 要求：*「执行状态继续写 `design-lab/config/task-ledger-r3.json`」*
且 *「新需求按其 schema 和现有管理流程映射/扩展」*。

**实测契约硬约束**（`src/design_lab/governance/r5_contract.py`）：
- `:55` `props['tasks']['minItems'] = props['tasks']['maxItems'] = 28` → **任务数必须恰为 28**
- `:88-92` 每项的 `definition`/`title`/`depends_on`/`predecessor_task_ids`/`required_axes`
  **必须与冻结源 `docs/history/taskpacks/r5-20260908/tasks.json` 完全相等**，否则抛错
- schema `task_schema['additionalProperties'] = False` → **不能加新字段**
- 唯一白名单式扩展点：**`condition_decisions`**，且**仅**对 `definition.conditional_dependencies` 非空的任务有效
  → 实测 28 项中**只有 1 项**具备该字段

→ **W00–W17 无法作为新任务行写入账本。** 合法落点只有两条：
  **(a)** 作为 **evidence receipt** 挂到既有 28 项（本轮已做，3→10 轴）；或
  **(b)** 走**正式迁移**（改 `r5_contract.py` + 冻结源 + schema），这需要 owner 决定，且属"变更冻结定义"级别。

包内说"按其 schema 和现有管理流程映射/扩展"——**该表述在契约层面是不成立的**，必须显式决策走 (a) 还是 (b)。

### 🟠 C3 — W02 引入组件体系会同时触碰 **4 道现有硬门禁**

包内首选 **Spectrum Web Components**、备选 Web Awesome Core。实测当前状态：

| 门禁 | 现状 | W02 的影响 |
|---|---|---|
| **依赖** | `apps/workbench/package.json` 只有 `typescript`/`vite`/`playwright` | 新增运行时依赖 → AUTHORITY §9 要求 `source/revision/license/mapping/destination/implementation/tests/evidence/rollback` 全套；§3 要求明确需求 + ADR |
| **资源路由** | `workbench.py ROUTES` **仅 3 条固定路径** | 组件 CSS/图标/字体/chunk **不会自动被服务**，会 404 |
| **CSP** | `style-src 'self'`（无 `unsafe-inline`）、`script-src 'self'` | 组件运行时样式/adoptedStyleSheets/外部资源需实测；包内已禁止 `unsafe-inline` 绕行（**正确**） |
| **打包** | `pyproject` force-include `design_lab/resources/workbench/` | 新资源需同步 wheel 打包，否则安装态失效 |
| **测试契约** | `build/main.js` 必须无 top-level import/export、可 classic-script 加载、`minify:false` | 引入组件可能破坏单文件 VM 契约；包内已禁止"删旧测试逃避"（**正确**） |

→ W02 不是"选个库"，而是**一次需要 ADR + 资源路由扩展 + wheel 打包同步 + CSP 实测的架构变更**。
包内已识别大部分风险，但**未指出 `ROUTES` 只有 3 条这一具体阻塞点**。

### 🟠 C4 — 新的终态轴/产品轴与既有汇报格式的关系未定义

包内引入 5 个 `DESIGNLAB_*` 终态轴 + 11 个产品轴 + 12 态状态矩阵。
TaskPack **N 段**已固定一套 17 字段汇报格式。两者关系（并存？替换？谁是机读真值？）**未定义**，
且**没有任何 verifier 会校验这 5 个轴** → 存在"报告自由发挥、CI 不设防"的空档。

### 🟡 C5 — 包内一处措辞不精确

包内 §2 说 *"不能将 AUTHORITY 里的历史『9个required checks』冒充今天实读结果"*。
AUTHORITY 里是 **§13.1**，我在 PR #174 已把它写成**带日期与观察 SHA 的 live 读回**（不是历史断言）；
§15 的现在时陈述也已同步。**本环境实测确为 9 项**。故该警示在当前 main 上已不适用，但**结论值相同**。

---

## 5. 包内声称的"具体缺口"与本仓库核对

| 包内观察 | 核对结果 |
|---|---|
| 「`design_layer.py` 未见完整 Token CRUD 接口」 | 包内自称"检查范围未见"，属**待查**，非已确认缺陷。需实测 `src/design_lab/design_layer.py` 方法表 |
| 「28 项 PARTIAL 是证据复审状态，不代表未实现」 | ✅ 正确（本轮已按此原则回填，未越权置 PASS） |
| 「部分 Adapter 仅 E0/E1，ComfyUI 记录历史 E3」 | ✅ 与账本 3 条既有 receipt（`r5-comfy-*`、`r5-ps-*`，均 `PARTIAL`）一致 |
| 「Evidence 下层文档与顶层 E4/E5 措辞存在差异」 | 需实测 `EVIDENCE_POLICY` vs `AUTHORITY.md` §6 |
| 「旧47包UI总归档仅定位未解包」 | ✅ 我实测 `D:\All projects\UI套件` **存在且可读**，W01 可立即开展 |

---

## 6. 首批可执行动作（W00–W03）—— 但**先解 C1/C2**

### 若 C1/C2 走"evidence 挂靠 + 不新增任务行"（推荐，成本最低）

| 步 | 动作 | 落点 | 验收 |
|---|---|---|---|
| **W00-1** | 读 live main / 本地 HEAD / dirty，记录 worktree | 已具备（本报告 §0） | ✅ 已完成 |
| **W00-2** | 28 项逐条找现有证据、分"补实现/修缺陷/补证据"三类 | 账本 `evidence` | 每条有真实路径 |
| **W00-3** | 建立 **`DL-*`(41) → `DL-R5-*`(28) crosswalk** | 见下方 D-1 | crosswalk 可机器校验 |
| **W00-4** | 产出映射：原41 → R5 → 真实文件/接口 → 缺口 → 首批范围 | `.project-local/` + 落仓 | 每首批项有真实路径 |
| **W01-1** | 读 `D:\All projects\UI套件` 中**仅 DESIGN-LAB 相关**原件，核对 B04/B07/B10 | 只读 | 建立 原稿→页面→组件→Token→实现→差异 矩阵 |
| **W01-2** | 区分**工作台 Token** 与**项目 DesignSystem** 两个作用域 | `apps/workbench/style.css` + `packages/design-system` | 无跨项目串色；Electric Blue 延续；**原件缺失标 `MISSING_SOURCE`，不声明 1:1** |
| **W02-1** | 先做**兼容试验**（非选型结论）：生产 Python 服务下加载 + CSP + Shadow DOM + 中文 IME + 焦点归还 | 一个真实 Project/Brief 页面 | 记录实测开销；**未过门则回退现有组件** |
| **W02-2** | 若过门：扩 `ROUTES` + wheel 打包 + CSP 变更（带资源理由与回归测试） | `workbench.py` / `pyproject` | CI 9 门禁仍全绿 |
| **W03** | 交付真实可用 Project/Brief 页面（create/open/edit/save/version/error/restart 读回） | `shell.ts`/`main.ts`/`workbench.ts`/`index.html`/`design.ts` | 从项目卡进真实 Brief 并保存读回；刷新保留上下文；**失败不弹"保存成功"**；**无假 KPI** |

### 硬门禁（不得绕过）

- 不 re open 已关闭 P0（strict TS / 首条设计链）
- 不 hard reset、不覆盖用户 dirty/资产
- 不新增第二 runtime/ledger/模型底座
- 不用 `unsafe-inline`、不开放任意目录、不删旧测试来"通过"
- 不把 PARTIAL 当从零开发

---

## 7. 需 owner 决策（阻塞执行）

| # | 决策点 | 选项 | 影响 |
|---|---|---|---|
| **D-1** | 41 个 `DL-*` ID 的 crosswalk 来源 | (a) 由本包作为**唯一权威**建立并落仓；(b) 提供既有的原任务清单文件；(c) 忽略 41 ID，只用 W00–W17 | **不决定则 W 包不可派工**（AGENTS.md 强制） |
| **D-2** | W00–W17 的落点 | (a) 仅作 evidence 挂既有 28 项（**不改冻结定义**）；(b) 正式迁移账本契约以容纳新任务 | (b) 属"变更冻结定义"，需 owner + 迁移记录 |
| **D-3** | W02 组件体系 | (a) 先做兼容试验再 ADR；(b) 直接引入 Spectrum；(c) 暂不引入 | (b) 跳过 §3/§9 的 ADR 与 REUSE 登记要求 |
| **D-4** | 5 个 `DESIGNLAB_*` 终态轴 | (a) 并存于 TaskPack N 段格式之下；(b) 纳入 CI 校验（需新增 verifier）；(c) 仅作人工阅读 | 不定则"报告无门禁" |
| **D-5** | 本包是否落仓 | (a) 落 `docs/taskpacks/` 并冻结分类；(b) 仅留 `.project-local/` 证据根 | 落仓需权威分类（否则违反 B002"不 mass 新增"） |

---

## 8. 风险提示（给执行器）

1. **本包不是一号权威**，与 AUTHORITY 冲突时以 AUTHORITY 为准；包内自己声明了这一点。
2. **包内 41 ID 无 crosswalk** 是最容易被忽略、又最致命的一条——直接执行会违反 AGENTS.md。
3. **W02 的资源路由阻塞点是具体的**（`ROUTES` 3 条），不是"可能需要适配"。
4. **W07「一个真实宿主」是 E3 的唯一入口**，也是当前最大 blocker（无 Adobe 实机条件时须标 `HOST_BLOCKED`，
   不得以静态测试或 PNG 冒充）。
5. **W15 har 要求 E2/E3/E4/E5 分别记录**，且**明文"不借其他能力历史证据晋级"**——与 AUTHORITY §6 一致，
   执行器不得用旧 SHA 证据提升新 SHA。
6. 本包 **17 处自标"未实测/未核验/拟定目标"**（性能目标、组件开销、47 包归档、Blender/DTCG 抓取失败等），
   执行时**必须实测后再落结论**。

---

**END — 只读分析。未修改仓库、未安装组件、未执行包内任何脚本。**
