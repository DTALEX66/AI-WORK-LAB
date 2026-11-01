# W00 交付物 —— 继承当前实现 + 差异映射

**轮次：** goal `全部开始` round 1
**观察 SHA：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15`（main == 本地 HEAD）
**性质：** 只读分析。**本轮未修改任何 tracked 文件、未提交、未推送。**
**工具：** `.project-local/task-artifacts/external-recovery-2026-09-27/w00-crosswalk-v6.py`（带断言，可重跑）
**机读产出：** `.project-local/task-artifacts/designlab-followup-taskpack-20260928/W00-CROSSWALK.json`

---

## 0. 开工回执（按包内 `03_EXECUTOR_PROMPT.txt` 要求的极短格式）

| 项 | 值 |
|---|---|
| 当前 main SHA | `d116b14995fcdbba1b165ec5bc3124f5daed3d15` |
| 本地 HEAD | 同上（`HEAD == origin/main`，ahead/behind `0/0`） |
| protected dirty | **无**（`git status --porcelain` 空；0 stash；1 worktree；**0 未推送提交**） |
| 当前可用纵切 | `Project → Brief → Reference → Direction → DesignSystem` 已贯通（E 段 CLOSED_WITH_REGRESSION_GUARD）；Workbench strict TS + browser E2E + B10 1:1 视觉已知可用 |
| 第一批工作 | **W00（本轮完成）→ W01 → W02 → W03** |
| WORK-LAB 阻塞 | 单机链**不阻塞**；W11/W12 为联邦支线 |
| Host 阻塞 | **R5-011/012（Illustrator/Photoshop）无实机条件 → `HOST_BLOCKED`**；W07 需 owner 择一 |

---

## 1. 必读文档核对（W00「读取」项）

包内提到的文档**全部存在**，但 3 处路径与包内写法不同（包内未给路径，属我定位）：

| 包内称 | 实际路径 |
|---|---|
| Neutrality | `docs/decisions/NEUTRALITY_POLICY.md` ✅ |
| Evidence | `docs/decisions/EVIDENCE_POLICY.md` ✅ |
| Adapter | `docs/decisions/ADAPTER_POLICY.md` ✅ |
| Adapter Registry | `integrations/adapter-registry.json` ✅ |
| 产品 / 架构 / 边界 | `docs/current/PRODUCT_DEFINITION.md`、`docs/architecture/ARCHITECTURE.md`、`docs/architecture/BOUNDARY_CONTRACT.md` ✅ |
| paths / 本机环境 | `.project/paths.json` ✅、`docs/LOCAL_ENVIRONMENT.md` ✅ |

`.project/paths.json` 的 `shared_inputs`：`model-library`、`design-assets`、`os-toolchain`、`design-toolchain`（均在 `D:/All projects/…`）。

**路径存在性审计：包内点名的 17 条真实路径，0 缺失。**

---

## 2. Crosswalk：`DL-*(41) → W(18) → DL-R5-*(28)`

> **来源与位阶：** 本 crosswalk 是**从任务包自身推导**的（§1 各 W 的「映射：」行给出 `W→R5`；§2 表给出 `DL-*→W`）。
> 它**不是**权威 crosswalk。`AGENTS.md` 强制「旧任务 ID 必须经 crosswalk 映射后才可执行」，
> 故本文件是**待 owner 批准的候选**，不是既成映射。

### 2.1 计数（全部由断言保证）

| 项 | 值 | 断言 |
|---|---|---|
| W 工作包 | 18（W00–W17） | — |
| 包内 §2 的 distinct `DL-*` | **41** | == 包内声称的 41 ✅ |
| 包内 §1 引用的 distinct `R5-*` | **28** | == 账本 28 项 ✅ |
| 包内引用了但账本不存在的 R5 | **none** | ✅ |
| 账本 28 项中未被包映射的 | **none** | ✅ |

→ **包的映射覆盖是完备的**：28 个账本任务全部被某个 W 引用。

### 2.2 但这不等于"全部可做"——调度上必须分三层

| 层 | 数量 | 含义 |
|---|---|---|
| **MAINLINE**（W00–W15 映射） | **17 / 28** | P0/P1 主线计划内可推进 |
| **EXTENSION-ONLY**（**仅** W16/W17 映射） | **11 / 28** | P2，且包内明文以 **W15 单机黄金流程通过**为前置 |
| **FEDERAL**（W11/W12） | 2（R5-006、R5-021） | 跨项目支线，**不得阻塞单机** |

**「被映射」≠「已排期」**。11 项扩展任务现在**不可动**（前置未满足）。

### 2.3 MAINLINE 17 项 → W

| R5 | 标题 | W |
|---|---|---|
| DL-R5-001 | 分支收敛、账本与增量接入 | W00 |
| DL-R5-002 | 仓库路径规范与旧运行根治理 | W00 |
| DL-R5-003 | CI 与验证环境补齐 | W00, W15 |
| DL-R5-004 | 运行状态与宿主异常恢复 | W07 |
| DL-R5-005 | 资产原子版本与完整交付清单 | W04, W07, W10 |
| DL-R5-006 | 软件与模型资格选择 | W12 |
| DL-R5-007 | Doctor 与本机证据接续 | W00 |
| DL-R5-009 | Python 安装包与 RIR 门面 | W07, W14 |
| DL-R5-010 | 工作台执行、修改、取消与导出 | W01, W02, W03, W06, W07, W14 |
| **DL-R5-011** | **Illustrator 产品链路** | **W07** |
| **DL-R5-012** | **Photoshop 产品链路** | **W07** |
| DL-R5-013 | 真实参考到可修正对象计划 | W04, W05, W06, W13 |
| DL-R5-014 | 局部对比、Human Jury 与生产预检 | W08, W09, W10, W13, W15 |
| DL-R5-015 | M1 首个可用研究版 | W10, W14, W15 |
| DL-R5-021 | 可选宿主与 Agent 收敛 | W11, W16, W17 |
| DL-R5-023 | 历史完整性、维护与扩展交付预检 | W09, W13, W17 |
| DL-R5-028 | 语言治理与渐进迁移 | W00, W01, W02, W14 |

### 2.4 EXTENSION-ONLY 11 项（P2，前置未满足 → 现在不动）

`DL-R5-008`（ComfyUI）、`016`（本地语音）、`017`（音乐与音轨）、`018`（H3 本地专项）、
`019`（Premiere 可编辑视频）、`020`（Blender 可编辑场景）、`022`（跨媒体依赖更新）、
`024`（UIA 与视觉控制后备）、`025`（Comfy 短视频动效）、`026`（Comfy 提取与透明资产）、
`027`（游戏交互资产交付）—— 全部由 **W16** 承载。

---

## 3. 推导过程中发现的 4 处记法/解析陷阱（会静默误排期，已全部消除）

| # | 陷阱 | 若忽略的后果 |
|---|---|---|
| N-1 | 包写 `R5-010`，账本写 `DL-R5-010`（同一实体两种拼法） | 不归一化则匹配数 **0/28**，看起来"包与账本完全无关" |
| N-2 | §2 有**多 W 单元格**（`\|DL-UI-09 / DL-UI-10\|W02/W03/W14\|`） | 只认单 W 会**静默丢掉 7 行**，漏掉 `DL-UI-04/09/10`、`DL-BE-01/03/05/06` —— 恰是首批核心 |
| N-3 | §1 用**中文连接词**（`R5-…011或012`、`R5-006及已有provider模块映射`） | 会漏掉 **R5-011/012（两条 Adobe 宿主链路）与 R5-006** —— 恰是宿主选型依据 |
| N-4 | W16 用 **en dash 区间**（`R5-008/016–022/024–027`） | 会误报"10 项未被包覆盖"，导致**扩展范围被低估** |

**这 4 条都是"看起来对、实际错"的静默错误**，不会报错、只会给出错误范围。已在 v6 用断言封住。

---

## 4. 首批（Wave A = W00–W03）范围与真实路径

| W | 标题 | 依赖 | R5 | 目标路径（已核验存在） |
|---|---|---|---|---|
| **W00** | 继承当前实现并生成差异映射 | 无 | R5-001/002/003/007/028 | 本文件 + `W00-CROSSWALK.json` |
| **W01** | 视觉资产与 Token 基线 | W00 | R5-010/028 | `apps/workbench/style.css` ✅；原稿源 `D:/All projects/UI套件` ✅（含 `04_B04_组件系统与DesignTokens_L4`、`10_B10_最终版高保真可部署UI`） |
| **W02** | 组件体系生产兼容验证与裁决 | W00/W01 | R5-010/028 | `src/design_lab/workbench.py` ✅、`apps/workbench/vite.config.ts` ✅、`packages/design-system` ✅ |
| **W03** | 项目中心与壳统一（**首个用户可见交付**） | W02 | R5-010 | `apps/workbench/{shell,main,workbench,design}.ts`、`index.html`、`src/design_lab/design_layer.py` ✅ |

**W02 的具体硬阻塞（本轮实测，包内未点出）：**
`src/design_lab/workbench.py` 的 `ROUTES` **只有 3 条固定路径**
（`/workbench`、`/workbench/main.js`、`/workbench/style.css`）→ 任何组件体系的
CSS/图标/字体/chunk **不会自动被服务**，会 404；需同步扩 `ROUTES` + `pyproject` force-include + CSP 实测。

**W00 验收对照：**
- ✅ 每个首批项有真实路径（上表，17/17 路径已核验）
- ✅ 已关闭项（strict TS D 段、首条设计链 E 段）**未重开**
- ✅ 无 hard reset、无覆盖（本轮 0 tracked 改动、0 未推送提交、工作区干净）
- ✅ 极短回执已出（§0）→ 可进入产品任务

---

## 5. 28 项账本的「补实现 / 修缺陷 / 补证据」初判

> ⚠️ **诚实标注：** 这是**初判**，依据是 (a) 包内各 W 的「动作」表述 + (b) 我已核实的仓库事实。
> **完整的逐项代码级取证仍未做**——那是 W00 剩余部分，需下一轮继续。**不要把本表当结论。**

| 分类 | R5 | 依据 |
|---|---|---|
| **补证据**（实现存在、证据缺） | `001`、`002`、`003`、`007`、`028` | W00 自身定位即"补证据"；其中 001/002/003/028 已在 PR #174/#175 绑定 receipt（`evidence` 数组，均 `PARTIAL`） |
| **补证据** | `010` | 已绑定 `r5-workbench-native-task-ui-tests-20260927`（`test_workbench_native_ui.py` 随 1755 测试套件通过） |
| **补实现**（页面/交互面） | `013`、`014`、`015`、`023` | 包内 W04/W05/W08/W09/W10 多为"新增页面与对象" |
| **修缺陷 / 补实现**（待代码取证） | `004`、`005`、`009` | W07/W14 涉及运行状态恢复、资产版本、wheel/RIR 门面；包内自标"应继续查现有实现后补缺口" |
| **HOST_BLOCKED** | `011`、`012` | 无 Adobe 实机条件；W07 需 owner 择一宿主 |
| **不可动（P2 前置未满足）** | `008`、`016`–`020`、`022`、`024`–`027` | 见 §2.4 |

---

## 6. 下一轮（W00 收尾 → W01）

1. **W00 剩余**：对 28 项做**代码级逐项取证**（找真实文件/接口/测试），把 §5 初判替换为带路径的证据表
2. **W01**：读 `D:/All projects/UI套件` 中**仅 DESIGN-LAB 相关**原稿，核对 B04/B07/B10；
   建立 `原稿 → 页面 → 组件 → Token → 当前实现 → 差异` 矩阵；
   区分**工作台 Token** 与**项目 DesignSystem** 两个作用域；原件缺失标 `MISSING_SOURCE`，**不声明 1:1**
3. 需 owner 决策（阻塞项，仍未解）：**D-1** crosswalk 是否按本文件批准；**D-2** W 编号落点（仅挂 evidence / 正式迁移）；**D-3** W02 组件选型路径；**D-5** 本包是否落仓

---

**END — W00 交付物。本轮为只读分析，未修改仓库。exact SHA `d116b14995fcdbba1b165ec5bc3124f5daed3d15`。**
